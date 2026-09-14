"""Thin IO adapter over unchanged pure core.

`resolve_dependencies`, `audit`, `run_installs`, `install_tool`,
`configure_path` and `run_doctor` remain the sole owners of install decision
logic. This is deliberate: audit finding C records three modules independently
deciding control flow in the abandoned `feat/install-experience` branch. That
branch is a design reference only, never a code source (D-04).
"""

from __future__ import annotations

import io
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import ClassVar

from rich.console import Console
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import RichLog, Static

from installer.deps import resolve_dependencies
from installer.engine import ChecksumPolicy, InstallOutcome, install_tool
from installer.model import Tool
from installer.platform import Platform
from installer.render import render_summary
from installer.resolve import resolve_methods
from installer.run import Runner, StreamingRunner
from installer.selection import select_tools
from installer.session import Install, Summary, order_for_install, run_installs, summarize
from installer.status import is_installed
from installer.ui_common import StatusLine, run_live
from installer.versions import TagResolver, resolve_github_tag

_C0_EXCEPT_TAB = frozenset(range(32)) - {9}
_DEL = 127


def sanitize_log_line(line: str) -> str:
    """Strip ASCII control characters other than tab from child-process output.

    An install script's escape sequences must not be able to reposition the
    cursor or recolour the running frame.
    """
    return "".join(
        ch for ch in line if ord(ch) != _DEL and (ord(ch) not in _C0_EXCEPT_TAB or ch == "\t")
    )


def attributed_install(streaming: StreamingRunner, install: Install = install_tool) -> Install:
    """Return an Install that attributes every call to `streaming` first.

    Attribution is driven by the tool `run_installs` is about to install,
    through the existing Install seam, so there is no optional parameter whose
    absence can silently drop it (D-05.2 / audit finding B).
    """

    def wrapped(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        streaming.set_tool(tool.id)
        return install(
            tool,
            platform,
            runner,
            resolve_tag,
            checksum_policy=checksum_policy,
            tools=tools,
        )

    return wrapped


class InstallLogLine(Message):
    """One attributed line of child-process output, posted from the worker thread.

    post_message is Textual's thread-safe hand-off back to the event loop, so
    the worker never touches a widget from its own thread.
    """

    def __init__(self, tool_id: str, line: str) -> None:
        self.tool_id = tool_id
        self.line = line
        super().__init__()


class InstallRunFinished(Message):
    """The install worker finished; `error` is None on a fully successful batch.

    Same hand-off as InstallLogLine, for the same reason: the worker must not
    touch widgets. `summary` is never None — a torn batch still carries
    summarize([]) so handlers can read buckets without an AttributeError.
    """

    def __init__(
        self,
        summary: Summary,
        outcomes: list[InstallOutcome],
        not_attempted: list[str],
        path_text: str,
        verify_text: str,
        error: str | None,
    ) -> None:
        self.summary = summary
        self.outcomes = outcomes
        self.not_attempted = not_attempted
        self.path_text = path_text
        self.verify_text = verify_text
        self.error = error
        super().__init__()


@dataclass(frozen=True)
class ExecuteInputs:
    """Everything ExecuteScreen needs, bound by the composition root.

    Optional closures default so a test can construct one without setup.py.
    """

    catalog: list[Tool]
    platform: Platform
    wire_path: Callable[[], str]
    verify: Callable[[], str]
    installed: Callable[[Tool], bool] = is_installed
    resolve_tag: TagResolver = resolve_github_tag
    install: Install = install_tool
    unattended: bool = False


class ExecuteScreen(ModalScreen[None]):
    """Pushed, non-navigable install run. ModalScreen, not AppScreen.

    AppScreen.__init__ requires a view name in VIEW_BY_NAME, so a subclass
    would force a seventh VIEWS row and a number-key destination the user
    could jump to mid-install, breaking the [catalog] / [catalog, <view>]
    stack invariant UnifiedApp._navigable protects. ModalScreen is this
    codebase's established shape for a pushed, non-navigable screen
    (ConfirmUninstall, NavScreen, TimePickerScreen) and makes _navigable()
    return False while it is on top, so the App's priority number keys and q
    are inert during a run with no new guard. D-01 requires push_screen /
    pop_screen rather than an overlay; this satisfies it.

    ctrl+c is NOT the weak cancel. UnifiedApp.action_hard_abort is unguarded
    and always calls exit(None); during a live run that tears the app down on
    top of a running Popen, so the in-flight child is orphaned mid-install.
    The mid-run status line discloses that cost. The weak cancel (c) arrives
    in plan 13-05; until then the run cannot be stopped safely.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "start", "start", show=True, priority=True),
        Binding("escape", "close", "close", show=True),
    ]
    DEFAULT_CSS = """
    ExecuteScreen {
        background: $surface;
        layout: vertical;
    }
    ExecuteScreen #execute-head { height: auto; padding: 1 2; }
    ExecuteScreen #execute-log { height: 1fr; padding: 0 1; }
    ExecuteScreen #execute-keys { height: auto; padding: 0 1; }
    """

    def __init__(self, ids: list[str], inputs: ExecuteInputs) -> None:
        super().__init__()
        self._ids = list(ids)
        self._inputs = inputs
        self._ordered: list[Tool] = []
        self._by_id: dict[str, Tool] = {}
        self._last_tool_id: str | None = None
        self.status = StatusLine()
        self.started = False
        self.finished = False
        self.summary: Summary | None = None
        self.not_attempted: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static(id="execute-head")
        yield RichLog(
            id="execute-log",
            markup=False,
            highlight=False,
            auto_scroll=True,
        )
        yield self.status
        yield Static("enter start · esc cancel", id="execute-keys")

    def on_mount(self) -> None:
        selected = select_tools(self._inputs.catalog, self._ids)
        platform = self._inputs.platform
        resolved = resolve_dependencies(
            order_for_install(selected),
            self._inputs.catalog,
            available=lambda tool: bool(resolve_methods(tool, platform)),
            is_installed=self._inputs.installed,
        )
        self._ordered = list(resolved.order)
        self._by_id = {tool.id: tool for tool in self._inputs.catalog}
        count = len(self._ordered)
        self.query_one("#execute-head", Static).update(
            f"Install {count} tools? enter start · esc cancel"
        )

    def action_start(self) -> None:
        if self.finished:
            self.dismiss()
            return
        if self.started:
            return
        self.started = True
        self.status.set(f"Installing {len(self._ordered)} tools...", "ok")
        self.query_one("#execute-keys", Static).update("esc close (run in flight)")
        self._execute_worker()

    @work(thread=True, exclusive=True, group="install-execute", exit_on_error=False)
    def _execute_worker(self) -> None:
        """Run confirm -> install -> wire -> verify off the event loop.

        A worker exception must not take the whole app down (exit_on_error=
        False, same reason as _apply_daemon_default_worker). The body is
        wrapped in try/finally so InstallRunFinished is posted on every path
        — a screen stuck on "Installing..." forever is the worst failure mode.
        """
        summary = summarize([])
        outcomes: list[InstallOutcome] = []
        not_attempted = [tool.id for tool in self._ordered]
        path_text = ""
        verify_text = ""
        error: str | None = None
        try:

            def emit(tool_id: str, line: str) -> None:
                self.post_message(InstallLogLine(tool_id, line))

            runner = StreamingRunner(emit)
            result, message = run_live(
                lambda: run_installs(
                    self._ordered,
                    self._inputs.platform,
                    runner,
                    self._inputs.resolve_tag,
                    attributed_install(runner, self._inputs.install),
                    on_mismatch=None,
                    catalog=self._by_id,
                    should_continue=lambda: True,
                )
            )
            if result is None:
                error = message
            else:
                outcomes = result
                summary = summarize(outcomes)
                seen = {outcome.tool_id for outcome in outcomes}
                not_attempted = [tool.id for tool in self._ordered if tool.id not in seen]
                path_result, path_error = run_live(self._inputs.wire_path)
                if path_result is None:
                    if error is None:
                        error = path_error
                else:
                    path_text = path_result
                verify_result, verify_error = run_live(self._inputs.verify)
                if verify_result is None:
                    if error is None:
                        error = verify_error
                else:
                    verify_text = verify_result
        finally:
            self.post_message(
                InstallRunFinished(summary, outcomes, not_attempted, path_text, verify_text, error)
            )

    def on_install_log_line(self, message: InstallLogLine) -> None:
        log = self.query_one("#execute-log", RichLog)
        if message.tool_id != self._last_tool_id:
            log.write(f"── {message.tool_id} ──")
            self._last_tool_id = message.tool_id
        log.write(f"{message.tool_id} │ {sanitize_log_line(message.line)}")

    def on_install_run_finished(self, message: InstallRunFinished) -> None:
        self.finished = True
        self.summary = message.summary
        self.not_attempted = list(message.not_attempted)
        log = self.query_one("#execute-log", RichLog)
        log.write(self._render_captured(lambda console: render_summary(message.summary, console)))
        if message.path_text:
            log.write(message.path_text)
        if message.verify_text:
            log.write(message.verify_text)
        if message.error:
            log.write(message.error)
        self.status.set("Done. enter or esc to return.", "ok")
        self.query_one("#execute-keys", Static).update("enter / esc return")
        # Do not event.stop(): this message must keep bubbling to UnifiedApp,
        # which records the summary for the process exit code. A future stop()
        # added for tidiness would silently break that exit code.

    def action_close(self) -> None:
        if not self.started or self.finished:
            self.dismiss()
            return
        self.status.set(
            "Installation is still running. The run cannot be stopped safely yet. "
            "ctrl+c aborts the whole app and can leave the current tool half-installed.",
            "warn",
        )

    def _render_captured(self, render: Callable[[Console], None]) -> str:
        buffer = io.StringIO()
        render(Console(file=buffer, width=80, no_color=True))
        return buffer.getvalue()
