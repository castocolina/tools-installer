"""Thin IO adapter over unchanged pure core.

`resolve_dependencies`, `audit`, `run_installs`, `install_tool`,
`configure_path` and `run_doctor` remain the sole owners of install decision
logic. This is deliberate: audit finding C records three modules independently
deciding control flow in the abandoned `feat/install-experience` branch. That
branch is a design reference only, never a code source (D-04).
"""

from __future__ import annotations

import io
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, ClassVar, Literal

from rich.console import Console
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, RichLog, Static

from installer.audit import audit
from installer.deps import resolve_dependencies
from installer.engine import ChecksumPolicy, InstallOutcome, install_tool
from installer.enums import InstallStatus, Severity
from installer.model import Tool
from installer.platform import Platform
from installer.render import (
    render_audit,
    render_dependency_notice,
    render_failure_details,
    render_handoff,
    render_postinstall_warnings,
    render_skipped,
    render_summary,
    render_verification,
)
from installer.resolve import resolve_methods
from installer.run import Runner, StreamingRunner
from installer.sanitize import sanitize_log_line
from installer.selection import select_tools
from installer.session import (
    Install,
    MismatchChoice,
    Summary,
    order_for_install,
    run_installs,
    summarize,
)
from installer.status import is_installed
from installer.ui_common import SEVERITY_STYLE, StatusLine, run_live
from installer.update import UpdateService, UpdateTarget
from installer.version_status import VersionRefreshService
from installer.versions import TagResolver, resolve_github_tag

_MISMATCH_CHOICES: frozenset[str] = frozenset({"retry", "skip", "fallback"})
_DISMISSAL_SKIP = "{tool_id}: checksum-mismatch prompt dismissed; the tool was therefore skipped."
_EXECUTE_KEYS = (
    "enter start · esc does not leave or stop during a run · "
    "c stops between tools, in-flight finishes · "
    "ctrl+c aborts the app and may leave a tool half-installed"
)
_CANCEL_AVAILABLE = "Press c to stop after the current tool; nothing further will start."
_CANCEL_ARMED = "The current tool will finish and nothing further will start."
_CANCEL_IDLE = "No install is running."
_DONE_STATUSES = frozenset({InstallStatus.INSTALLED, InstallStatus.ALREADY_INSTALLED})
ProgressState = Literal["pending", "done", "not-done", "skipped"]
_PROGRESS_GLYPH: dict[ProgressState, tuple[str, str, str]] = {
    "pending": ("○", "dim", "pending"),
    "done": ("●", SEVERITY_STYLE[Severity.OK], "done"),
    "not-done": ("✖", SEVERITY_STYLE[Severity.ERROR], "not done"),
    "skipped": ("○", "dim", "not attempted"),
}


class ChecksumMismatchScreen(ModalScreen[str | None]):
    """Three-way checksum-mismatch prompt, word-for-word from setup.py::_ask_mismatch.

    Letter-prefixed ListItem ids (`opt-retry`) because a raw value like a
    leading-digit id is an invalid Textual identifier — the same convention
    TimePickerScreen uses.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    ChecksumMismatchScreen { align: center middle; }
    ChecksumMismatchScreen > Label { width: 72; padding: 1 1 0 1; }
    ChecksumMismatchScreen > ListView { width: 72; height: 8; border: round $accent; }
    """

    def __init__(self, tool_id: str) -> None:
        super().__init__()
        self.tool_id = tool_id

    def compose(self) -> ComposeResult:
        yield Label(
            f"Checksum mismatch for {self.tool_id} — "
            "the download may be corrupted or tampered with."
        )
        yield ListView(
            ListItem(Label("Retry the download"), id="opt-retry"),
            ListItem(Label("Skip this tool"), id="opt-skip"),
            ListItem(Label("Fall back to another install method (brew/native)"), id="opt-fallback"),
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id is None:
            return
        choice = item_id.removeprefix("opt-")
        if choice not in _MISMATCH_CHOICES:
            return
        self.dismiss(choice)

    def action_cancel(self) -> None:
        self.dismiss(None)


def ask_from_worker(app: App[object], screen: ModalScreen[str | None]) -> str | None:
    """Ask the user from a thread worker via MECHANISM=A (call_from_thread + push_screen_wait).

    The choice was made by a spike rather than assumed; see
    `.planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-VALIDATION.md`
    section ``## Worker-to-modal mechanism``. This is the documented exception
    to `.claude/architecture.md` rule 2: rule 2 governs main-thread callers; a
    thread worker has no callback to return into.
    """

    async def coro_fn() -> str | None:
        return await app.push_screen_wait(screen)

    return app.call_from_thread(coro_fn)


def attributed_install(
    streaming: StreamingRunner,
    install: Install = install_tool,
    on_outcome: Callable[[InstallOutcome], None] | None = None,
) -> Install:
    """Return an Install that attributes every call to `streaming` first.

    Attribution is driven by the tool `run_installs` is about to install,
    through the existing Install seam, so there is no optional parameter whose
    absence can silently drop it (D-05.2 / audit finding B). `on_outcome`,
    when given, is invoked with each returned InstallOutcome so a screen can
    update a running status list without the worker touching widgets.
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
        outcome = install(
            tool,
            platform,
            runner,
            resolve_tag,
            checksum_policy=checksum_policy,
            tools=tools,
        )
        if on_outcome is not None:
            on_outcome(outcome)
        return outcome

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


class InstallToolFinished(Message):
    """One tool's install() returned; posted from the worker thread."""

    def __init__(self, tool_id: str, status: InstallStatus) -> None:
        self.tool_id = tool_id
        self.status = status
        super().__init__()


class MismatchPromptOpen(Message):
    """The worker is blocked on (or has just left) the checksum-mismatch modal."""

    def __init__(self, tool_id: str, waiting: bool) -> None:
        self.tool_id = tool_id
        self.waiting = waiting
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
        path_error: str | None = None,
        verify_error: str | None = None,
    ) -> None:
        self.summary = summary
        self.outcomes = outcomes
        self.not_attempted = not_attempted
        self.path_text = path_text
        self.verify_text = verify_text
        self.error = error
        self.path_error = path_error
        self.verify_error = verify_error
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
    version_refresh: VersionRefreshService | None = None
    updates: UpdateService | None = None


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
    The mid-run status line and the execute-keys hint disclose that cost.
    The weak cancel is `c`: it stops new tools being queued and lets the
    in-flight one finish.
    """

    if TYPE_CHECKING:
        app: App[object]

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "start", "start", show=True, priority=True),
        Binding("escape", "close", "close", show=True),
        Binding("c", "cancel_run", "cancel", show=True),
    ]
    DEFAULT_CSS = """
    ExecuteScreen {
        background: $surface;
        layout: vertical;
    }
    ExecuteScreen #execute-head { height: auto; padding: 1 2; }
    ExecuteScreen #execute-progress { height: auto; padding: 0 2; }
    ExecuteScreen #execute-log { height: 1fr; padding: 0 1; }
    ExecuteScreen #execute-keys { height: auto; padding: 0 1; }
    """

    def __init__(self, ids: list[str], inputs: ExecuteInputs) -> None:
        super().__init__()
        self._ids = list(ids)
        self._inputs = inputs
        self._ordered: list[Tool] = []
        self._to_update: list[Tool] = []
        self._by_id: dict[str, Tool] = {}
        self._last_tool_id: str | None = None
        self._progress: dict[str, ProgressState] = {}
        self._waiting_prompt: str | None = None
        self.cancel_event = threading.Event()
        self.status = StatusLine()
        self.started = False
        self.finished = False
        self.summary: Summary | None = None
        self.not_attempted: list[str] = []
        self.update_skips: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static(id="execute-head")
        yield Static(id="execute-progress")
        yield RichLog(
            id="execute-log",
            markup=False,
            highlight=False,
            auto_scroll=True,
        )
        yield self.status
        yield Static(_EXECUTE_KEYS, id="execute-keys")

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
        self._to_update = self._update_targets(selected)
        self._by_id = {tool.id: tool for tool in self._inputs.catalog}
        self._progress = {tool.id: "pending" for tool in self._ordered}
        self._refresh_progress()

        def render_head(console: Console) -> None:
            render_dependency_notice(resolved.dragged_in, resolved.warnings, console)
            render_audit(audit(self._ordered, self._inputs.installed), console)
            console.print(f"Install {len(self._ordered)} tools? enter start · esc cancel")

        self.query_one("#execute-head", Static).update(self._render_captured(render_head))
        if self._inputs.unattended:
            self.action_start()

    def _update_targets(self, selected: list[Tool]) -> list[Tool]:
        refresh = self._inputs.version_refresh
        updates = self._inputs.updates
        if refresh is None or updates is None:
            return []
        statuses = refresh.statuses
        targets: list[Tool] = []
        for tool in selected:
            if not self._inputs.installed(tool):
                continue
            status = statuses.get(tool.id)
            if status is not None and status.outdated is False:
                continue
            targets.append(tool)
        return targets

    def action_start(self) -> None:
        if self.finished:
            self.dismiss()
            return
        if self.started:
            return
        self.started = True
        self.status.set(_CANCEL_AVAILABLE, "ok")
        self._execute_worker()

    def action_cancel_run(self) -> None:
        if self._waiting_prompt is not None:
            self.status.set(
                f"Run paused on a question for {self._waiting_prompt}; answer it before cancel.",
                "warn",
            )
            return
        if not self.started or self.finished:
            self.status.set(_CANCEL_IDLE, "warn")
            return
        self.cancel_event.set()
        self.status.set(_CANCEL_ARMED, "warn")

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
        path_error: str | None = None
        verify_error: str | None = None
        try:

            def emit(tool_id: str, line: str) -> None:
                self.post_message(InstallLogLine(tool_id, line))

            runner = StreamingRunner(emit)

            def on_outcome(outcome: InstallOutcome) -> None:
                self.post_message(InstallToolFinished(outcome.tool_id, outcome.status))

            on_mismatch = None if self._inputs.unattended else self._ask_mismatch
            result, message = run_live(
                lambda: run_installs(
                    self._ordered,
                    self._inputs.platform,
                    runner,
                    self._inputs.resolve_tag,
                    attributed_install(runner, self._inputs.install, on_outcome),
                    on_mismatch=on_mismatch,
                    catalog=self._by_id,
                    should_continue=self._should_continue,
                )
            )
            if result is None:
                error = message
            else:
                outcomes = result
                summary = summarize(outcomes)
                seen = {outcome.tool_id for outcome in outcomes}
                not_attempted = [tool.id for tool in self._ordered if tool.id not in seen]
                self._run_updates()
                path_result, path_fail = run_live(self._inputs.wire_path)
                if path_result is None:
                    path_error = path_fail
                    if error is None:
                        error = path_fail
                else:
                    path_text = path_result
                verify_result, verify_fail = run_live(self._inputs.verify)
                if verify_result is None:
                    verify_error = verify_fail
                    if error is None:
                        error = verify_fail
                else:
                    verify_text = verify_result
        finally:
            self.post_message(
                InstallRunFinished(
                    summary,
                    outcomes,
                    not_attempted,
                    path_text,
                    verify_text,
                    error,
                    path_error,
                    verify_error,
                )
            )

    def _run_updates(self) -> None:
        refresh = self._inputs.version_refresh
        updates = self._inputs.updates
        if refresh is None or updates is None:
            return
        for tool in self._to_update:
            if not self._should_continue():
                return
            ownership = refresh.ownership_of(tool.id)
            if ownership is None:
                refresh.refresh([tool])
                ownership = refresh.ownership_of(tool.id)
            if ownership is None:
                continue
            if not updates.begin(tool.id):
                in_flight = updates.in_flight or "another tool"
                self.update_skips.append(f"update already in flight for {in_flight}")
                continue
            try:
                target = UpdateTarget(tool=tool, ownership=ownership)
                run_live(partial(updates.run, target))
            finally:
                updates.end()

    def _should_continue(self) -> bool:
        return not self.cancel_event.is_set()

    def _ask_mismatch(self, tool_id: str) -> MismatchChoice:
        self.post_message(MismatchPromptOpen(tool_id, True))
        try:
            answer = ask_from_worker(self.app, ChecksumMismatchScreen(tool_id))
        finally:
            self.post_message(MismatchPromptOpen(tool_id, False))
        if answer == "retry" or answer == "skip" or answer == "fallback":
            return answer
        sentence = _DISMISSAL_SKIP.format(tool_id=tool_id)
        self.post_message(InstallLogLine(tool_id, sentence))
        return "skip"

    def on_install_log_line(self, message: InstallLogLine) -> None:
        log = self.query_one("#execute-log", RichLog)
        if message.tool_id != self._last_tool_id:
            log.write(f"── {message.tool_id} ──")
            self._last_tool_id = message.tool_id
        cleaned = sanitize_log_line(message.line)
        log.write(f"{message.tool_id} │ {cleaned}")
        if message.line == _DISMISSAL_SKIP.format(tool_id=message.tool_id):
            self.status.set(cleaned, "warn")

    def on_install_tool_finished(self, message: InstallToolFinished) -> None:
        self._progress[message.tool_id] = "done" if message.status in _DONE_STATUSES else "not-done"
        self._refresh_progress()

    def on_mismatch_prompt_open(self, message: MismatchPromptOpen) -> None:
        if message.waiting:
            self._waiting_prompt = message.tool_id
            self.status.set(
                f"Run paused on a question for {message.tool_id}; answer the prompt to continue.",
                "warn",
            )
            return
        self._waiting_prompt = None
        if self.started and not self.finished and not self.cancel_event.is_set():
            self.status.set(_CANCEL_AVAILABLE, "ok")

    def on_install_run_finished(self, message: InstallRunFinished) -> None:
        self.finished = True
        self.summary = message.summary
        self.not_attempted = list(message.not_attempted)
        for outcome in message.outcomes:
            self._progress[outcome.tool_id] = (
                "done" if outcome.status in _DONE_STATUSES else "not-done"
            )
        for tool_id in message.not_attempted:
            self._progress[tool_id] = "skipped"
        self._refresh_progress()
        log = self.query_one("#execute-log", RichLog)

        def render_report(console: Console) -> None:
            render_summary(message.summary, console)
            render_failure_details(message.outcomes, console)
            render_skipped(message.outcomes, console)
            render_handoff(message.outcomes, console)
            render_postinstall_warnings(message.outcomes, console)
            render_verification(message.outcomes, console)

        log.write(self._render_captured(render_report))
        if message.not_attempted:
            log.write("Not attempted: " + ", ".join(message.not_attempted))
        if message.path_text:
            log.write("PATH wiring")
            log.write(message.path_text)
        elif message.path_error:
            log.write(f"PATH wiring could not be completed: {message.path_error}")
        if message.verify_text:
            log.write("PATH audit")
            log.write(message.verify_text)
        elif message.verify_error:
            log.write(f"PATH audit could not be completed: {message.verify_error}")
        if message.error and not message.path_error and not message.verify_error:
            log.write(message.error)
        self.status.set("Done. enter or esc returns to the catalog.", "ok")
        self.query_one("#execute-keys", Static).update("enter / esc return to catalog")
        # Do not event.stop(): this message must keep bubbling to UnifiedApp,
        # which records the summary for the process exit code. A future stop()
        # added for tidiness would silently break that exit code.

    def action_close(self) -> None:
        if not self.started or self.finished:
            self.dismiss()
            return
        self.status.set(
            "Installation is still running. Press c to stop after the current tool. "
            "ctrl+c aborts the whole app and can leave the current tool half-installed.",
            "warn",
        )

    def _refresh_progress(self) -> None:
        rows = Text()
        for index, tool in enumerate(self._ordered):
            if index:
                rows.append("\n")
            state = self._progress.get(tool.id, "pending")
            glyph, style, label = _PROGRESS_GLYPH[state]
            rows.append(f"{glyph} {tool.id} [{label}]", style=style)
        self.query_one("#execute-progress", Static).update(rows)

    def _render_captured(self, render: Callable[[Console], None]) -> str:
        buffer = io.StringIO()
        render(Console(file=buffer, width=80, no_color=True))
        # Defense-in-depth: render() prints outcome.errors, which carries
        # untrusted child-process output (CommandError.detail). run.py
        # already sanitizes its own tail; this catches any other producer
        # that writes into the report console without going through it.
        return sanitize_log_line(buffer.getvalue())
