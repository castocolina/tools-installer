"""The install-plan screen: an IO adapter over `build_plan` and `execute_plan`.

`build_plan` (installer/session.py) decides every row's disposition from the
published state, and `execute_plan` runs the settled rows and returns one
outcome per row. This module owns only the widgets, the worker thread and the
messages between them. The worker never touches a widget: it posts messages
and the event loop paints them.
"""

from __future__ import annotations

import io
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from rich.cells import cell_len
from rich.console import Console
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.events import Resize
from textual.message import Message
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Label, ListItem, ListView, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from installer.engine import install_tool
from installer.enums import Severity
from installer.model import Tool
from installer.platform import Platform
from installer.render import (
    display_order,
    id_width,
    outcome_row_text,
    plan_head,
    plan_row_text,
    render_run_report,
    running_row_text,
    summary_head,
)
from installer.run import StreamingRunner
from installer.sanitize import sanitize_log_line
from installer.session import (
    Disposition,
    MismatchChoice,
    PlanRow,
    RowOutcome,
    RunContext,
    SensitiveInstall,
    build_plan,
    execute_plan,
    exit_code,
    ran_anything,
    retained,
)
from installer.ui_common import SEVERITY_STYLE, StatusLine, run_live
from installer.update import UpdateService
from installer.version_status import VersionRefreshService
from installer.versions import TagResolver, resolve_github_tag

_MISMATCH_CHOICES: frozenset[str] = frozenset({"retry", "skip", "fallback"})
_SENSITIVE_CHOICES: frozenset[str] = frozenset({"yes", "no"})
_DISMISSAL_SKIP = "{tool_id}: checksum-mismatch prompt dismissed; the tool was therefore skipped."
_DISMISSAL_SENSITIVE = "{tool_id}: sensitive-action prompt dismissed; the answer was therefore no."
# The rows the worker runs; SKIP and BLOCKED rows never reach an engine.
_RUNNABLE: frozenset[Disposition] = frozenset(
    {
        Disposition.INSTALL,
        Disposition.UPDATE,
        Disposition.REPAIR,
        Disposition.RECONFIGURE,
        Disposition.REINSTALL,
    }
)
# UI-SPEC Interaction contract: one keys line per screen state.
_KEYS_EMPTY = "esc close"
_KEYS_RUNNING = "c stop after this tool · ctrl+c aborts and can leave a tool half-installed"
_KEYS_FINISHED = "enter / esc return to catalog"
_KEYS_WAITING = "waiting for the state check · esc cancels the wait"
_KEYS_RETRY = "enter retries · esc closes"
_STATUS_WAITING = "Waiting for the state check; nothing starts until it finishes. esc cancels."
_WAIT_CANCELLED = "Wait cancelled; nothing started. enter waits again · esc closes."
_STATE_CHECK_FAILED = "State check failed: {error}. enter retries · esc closes."
_R_REFUSED = "{tool_id}: r needs a current tool this installer owns."
_STATE_CHECK_ERROR_BUDGET = 78 - cell_len(_STATE_CHECK_FAILED.format(error=""))
_CANCEL_AVAILABLE = "Press c to stop after the current tool; nothing further will start."
_CANCEL_ARMED = "The current tool will finish and nothing further will start."
_CANCEL_IDLE = "No install is running."
SILENCE_SECONDS = 2.0
_WAITING_OUTPUT = "-- still running; waiting for output --"
_UPDATE_STARTED = "-- updating --"


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


class SensitiveActionScreen(ModalScreen[str | None]):
    """Yes/no prompt for a sensitive post-install action.

    Letter-prefixed ListItem ids (`opt-yes`) because a raw value can be an
    invalid Textual identifier — the same convention ChecksumMismatchScreen
    uses. Dismisses with the string values the shared worker-to-modal helper
    is typed for; the screen's ask method converts them to bool.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    SensitiveActionScreen { align: center middle; }
    SensitiveActionScreen > Label { width: 72; padding: 1 1 0 1; }
    SensitiveActionScreen > ListView { width: 72; height: 6; border: round $accent; }
    """

    def __init__(self, tool_id: str) -> None:
        super().__init__()
        self.tool_id = tool_id

    def compose(self) -> ComposeResult:
        yield Label(
            f"Show a reviewed command to change the login shell to zsh for {self.tool_id}, "
            "which you run in your own terminal after the installer exits?"
        )
        yield ListView(
            ListItem(Label("Yes, show the reviewed command"), id="opt-yes"),
            ListItem(Label("No, skip this"), id="opt-no"),
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id is None:
            return
        choice = item_id.removeprefix("opt-")
        if choice not in _SENSITIVE_CHOICES:
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


class InstallLogLine(Message):
    """One attributed line of child-process output, posted from the worker thread.

    post_message is Textual's thread-safe hand-off back to the event loop, so
    the worker never touches a widget from its own thread.

    A transient line (``transient=True``) is written to the log for the user
    to read and is NOT output: nothing downstream may treat it as evidence
    that the child said something. ``generation`` is the silence generation
    it was minted under -- the token the handler uses to tell a still-true
    transient from one the world has moved past. ``generation`` is
    meaningless on a non-transient line and stays None there.
    """

    def __init__(
        self,
        tool_id: str,
        line: str,
        *,
        transient: bool = False,
        generation: int | None = None,
    ) -> None:
        self.tool_id = tool_id
        self.line = line
        self.transient = transient
        self.generation = generation
        super().__init__()


class PromptOpen(Message):
    """The worker is blocked on (or has just left) a question modal."""

    def __init__(self, tool_id: str, waiting: bool) -> None:
        self.tool_id = tool_id
        self.waiting = waiting
        super().__init__()


class RowStarted(Message):
    """The worker is about to run this row; posted from the worker thread."""

    def __init__(self, tool_id: str) -> None:
        self.tool_id = tool_id
        super().__init__()


class RowFinished(Message):
    """One row's outcome is final; posted from the worker thread."""

    def __init__(self, outcome: RowOutcome) -> None:
        self.outcome = outcome
        super().__init__()


class StateSettled(Message):
    """The refresh joined by the review screen has finished."""

    def __init__(self, token: int, error: str | None) -> None:
        self.token = token
        self.error = error
        super().__init__()


class InstallRunFinished(Message):
    """The worker finished; `outcomes` holds exactly one outcome per plan row.

    `run_error` is a crash that escaped `execute_plan`. `path_error` and
    `verify_error` are the PATH wiring and verify failures. Each of the three
    makes the run failed (L-20-08), and UnifiedApp keeps them beside the row
    outcomes for the exit code.
    """

    def __init__(
        self,
        outcomes: list[RowOutcome],
        run_error: str | None,
        path_text: str,
        verify_text: str,
        path_error: str | None = None,
        verify_error: str | None = None,
    ) -> None:
        self.outcomes = outcomes
        self.run_error = run_error
        self.path_text = path_text
        self.verify_text = verify_text
        self.path_error = path_error
        self.verify_error = verify_error
        super().__init__()


def _complete(
    rows: Sequence[PlanRow], collected: Sequence[RowOutcome], run_error: str | None
) -> list[RowOutcome]:
    """One outcome per plan row: a row the run never reached is not_attempted (D-10)."""
    done = {outcome.row.tool_id for outcome in collected}
    missing = [
        RowOutcome(row, "not_attempted", detail=run_error or "")
        for row in rows
        if row.tool_id not in done
    ]
    return [*collected, *missing]


class InstallRunStarted(Message):
    """The user confirmed; the run is now in flight (WR-06).

    Posted from action_start so UnifiedApp can record the in-flight window:
    a hard abort inside it exits before InstallRunFinished can arrive, and
    the exit-code readers must see the run was interrupted, not clean.
    """


@dataclass(frozen=True)
class ExecuteInputs:
    """Everything ExecuteScreen needs, bound by the composition root.

    Presence is read from `version_refresh` alone (L-20-09): there is no second
    predicate that could disagree with the published state. `terminal_sync` is
    the terminal synchronizer the composition root wires; None runs none.
    Optional closures default so a test can construct one without setup.py.
    """

    catalog: list[Tool]
    platform: Platform
    wire_path: Callable[[], str]
    verify: Callable[[], str]
    version_refresh: VersionRefreshService
    resolve_tag: TagResolver = resolve_github_tag
    install: SensitiveInstall = install_tool
    unattended: bool = False
    updates: UpdateService | None = None
    now: Callable[[], float] = time.monotonic
    terminal_sync: Callable[[], str | None] | None = None


class ExecuteScreen(ModalScreen[list[RowOutcome] | None]):
    """Pushed, non-navigable install run over one `build_plan`. ModalScreen, not
    AppScreen: a pushed screen with no view name keeps the [catalog] /
    [catalog, view] stack invariant UnifiedApp._navigable protects.

    The screen dismisses with the run's outcomes, or None when it closes before
    a run starts; UnifiedApp keeps the retained selection from them.

    ctrl+c is NOT the weak cancel. UnifiedApp.action_hard_abort tears the app
    down on top of a running child, which can orphan a half-installed tool. The
    weak cancel is `c`: it lets the in-flight tool finish and queues nothing new.
    """

    if TYPE_CHECKING:
        app: App[object]

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "start", "start", show=True, priority=True),
        Binding("r", "toggle_reinstall", "reinstall", show=False),
        Binding("escape", "close", "close", show=True),
        Binding("c", "cancel_run", "cancel", show=True),
    ]
    DEFAULT_CSS = """
    ExecuteScreen {
        background: $surface;
        layout: vertical;
    }
    ExecuteScreen #execute-head { height: auto; max-height: 3; padding: 0 1; }
    ExecuteScreen #plan-rows { height: 1fr; }
    ExecuteScreen #execute-log { display: none; height: 1fr; padding: 0 1; }
    ExecuteScreen #execute-keys { height: 1; padding: 0 1; }
    ExecuteScreen.-running #plan-rows, ExecuteScreen.-finished #plan-rows {
        height: auto;
        max-height: 8;
    }
    ExecuteScreen.-running #execute-log, ExecuteScreen.-finished #execute-log {
        display: block;
    }
    """

    def __init__(self, ids: list[str], inputs: ExecuteInputs) -> None:
        super().__init__()
        self._ids = list(ids)
        self._inputs = inputs
        self._rows: list[PlanRow] = []
        self._reinstall: set[str] = set()
        self._start_requested = False
        self._cancelled_wait = False
        self._wait_token = 0
        self._waiting = False
        self._waiting_prompt: str | None = None
        self._in_flight: str | None = None
        self._last_tool_id: str | None = None
        self._last_output_at: float | None = None
        self._silence_noted = False
        self._silence_generation = 0
        self._silence_timer: Timer | None = None
        self.cancel_event = threading.Event()
        self.status = StatusLine()
        self.started = False
        self.finished = False
        self.outcomes: list[RowOutcome] | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="execute-head")
        yield OptionList(id="plan-rows")
        yield RichLog(
            id="execute-log",
            markup=False,
            highlight=False,
            auto_scroll=True,
        )
        yield self.status
        yield Static(_KEYS_EMPTY, id="execute-keys")

    def on_mount(self) -> None:
        self._replan()
        if any(row.disposition is Disposition.WAIT for row in self._rows):
            self._await_state()
        if self._inputs.unattended:
            self.action_start()

    def on_resize(self, _event: Resize) -> None:
        options = self.query_one("#plan-rows", OptionList)
        if self.finished:
            idw = id_width(self._rows)
            width = self._fold_width()
            for outcome in self.outcomes or ():
                options.replace_option_prompt(
                    outcome.row.tool_id, outcome_row_text(outcome, idw, width)
                )
            return
        if self.started:
            return
        self._paint_review()
        if self._start_requested:
            self.query_one("#execute-keys", Static).update(_KEYS_WAITING)

    def _platform(self) -> Platform:
        """The live platform: the service's own (D-14)."""
        return self._inputs.version_refresh.platform

    def _replan(self) -> None:
        """Rebuild the rows from the latest published state, then repaint the review."""
        self._rows = build_plan(
            self._ids,
            self._inputs.catalog,
            self._inputs.version_refresh.state_of,
            self._platform(),
            reinstall=frozenset(self._reinstall),
        )
        self._paint_review()

    def _fold_width(self) -> int:
        """Plan-row budget: the list's width less its padding, 78 before layout."""
        width = self.query_one("#plan-rows", OptionList).size.width
        return width - 2 if width > 2 else 78

    def _paint_review(self) -> None:
        head = self.query_one("#execute-head", Static)
        options = self.query_one("#plan-rows", OptionList)
        keys = self.query_one("#execute-keys", Static)
        highlighted_id = None
        if options.highlighted is not None:
            highlighted_id = options.get_option_at_index(options.highlighted).id
        options.clear_options()
        if not self._rows:
            head.update("Nothing selected.")
            keys.update(_KEYS_EMPTY)
            return
        width = self._fold_width()
        idw = id_width(self._rows)
        for row in display_order(self._rows):
            options.add_option(
                Option(
                    plan_row_text(row, idw, width, hint=row.disposition is Disposition.SKIP),
                    id=row.tool_id,
                )
            )
        highlighted_index = (
            options.get_option_index(highlighted_id) if highlighted_id is not None else None
        )
        options.highlighted = highlighted_index if highlighted_index is not None else 0
        head.update(plan_head(self._rows))
        keys.update(self._idle_keys())

    def _idle_keys(self) -> str:
        runnable = any(row.disposition in _RUNNABLE for row in self._rows)
        parts = ["enter start" if runnable else "enter continue"]
        if any(row.can_reinstall for row in self._rows):
            parts.append("r reinstall")
        parts.extend(("up/down move", "esc cancel"))
        return " · ".join(parts)

    def _row_for(self, tool_id: str) -> PlanRow | None:
        return next((row for row in self._rows if row.tool_id == tool_id), None)

    def action_toggle_reinstall(self) -> None:
        if self.started or self.finished or self._start_requested:
            return
        options = self.query_one("#plan-rows", OptionList)
        if options.highlighted is None:
            return
        option = options.get_option_at_index(options.highlighted)
        tool_id = option.id
        if tool_id is None:
            return
        row = self._row_for(tool_id)
        if row is None:
            return
        if not (row.can_reinstall or tool_id in self._reinstall):
            self.status.set(_R_REFUSED.format(tool_id=tool_id), "warn")
            return
        self._reinstall ^= {tool_id}
        self.status.clear()
        self._replan()

    def action_start(self) -> None:
        if self.finished:
            self.dismiss(self.outcomes)
            return
        if self.started:
            return
        # D-14 "after Enter": a tool published since mount is read now, so
        # a row that went stale while the review was open is rebuilt first.
        # A refresh cancelled with esc may still publish to the service; don't
        # consume that publication on the next Enter before its new token settles.
        if self._cancelled_wait:
            self._cancelled_wait = False
        else:
            self._replan()
        if not self._rows:
            return
        if any(row.disposition is Disposition.WAIT for row in self._rows):
            if self._start_requested:
                return
            self._start_requested = True
            self.status.set(_STATUS_WAITING, "warn")
            self.query_one("#execute-keys", Static).update(_KEYS_WAITING)
            self._await_state()
            return
        self._begin_run()

    def _await_state(self) -> None:
        if self._waiting:
            return
        self._waiting = True
        token = self._wait_token
        self._wait_worker(token)

    @work(thread=True, exclusive=True, group="execute-wait", exit_on_error=False)
    def _wait_worker(self, token: int) -> None:
        """Join the version and skill checks; always settle so Enter can retry."""
        error: str | None = "state check did not complete"
        try:
            _result, live_error = run_live(
                lambda: (
                    self._inputs.version_refresh.refresh(self._inputs.catalog),
                    self._inputs.version_refresh.refresh_skills(self._inputs.catalog),
                )
            )
            error = live_error
        except Exception as exc:
            lines = str(exc).splitlines()
            error = lines[0] if lines and lines[0] else type(exc).__name__
        finally:
            self.post_message(StateSettled(token, error))

    def on_state_settled(self, message: StateSettled) -> None:
        if message.token != self._wait_token:
            return
        self._waiting = False
        if self.started or self.finished:
            return
        if message.error is not None:
            self._start_requested = False
            detail = Text(message.error.splitlines()[0])
            detail.truncate(_STATE_CHECK_ERROR_BUDGET, overflow="ellipsis")
            self.status.set(_STATE_CHECK_FAILED.format(error=detail.plain), "error")
            self.query_one("#execute-keys", Static).update(_KEYS_RETRY)
            return
        self._replan()
        if not self._start_requested:
            return
        if not any(row.disposition is Disposition.WAIT for row in self._rows):
            self._start_requested = False
            self._begin_run()
            return
        ids = ", ".join(row.tool_id for row in self._rows if row.disposition is Disposition.WAIT)
        self._start_requested = False
        detail = Text(f"no state for {ids}")
        detail.truncate(_STATE_CHECK_ERROR_BUDGET, overflow="ellipsis")
        self.status.set(_STATE_CHECK_FAILED.format(error=detail.plain), "error")
        self.query_one("#execute-keys", Static).update(_KEYS_RETRY)

    def _begin_run(self) -> None:
        self.started = True
        self.add_class("-running")
        self.post_message(InstallRunStarted())
        self.query_one("#plan-rows", OptionList).can_focus = False
        self.status.set(_CANCEL_AVAILABLE, "ok")
        self.query_one("#execute-keys", Static).update(_KEYS_RUNNING)
        self._last_output_at = self._inputs.now()
        self._arm_silence_timer(SILENCE_SECONDS)
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
        """Run the settled plan off the event loop and always report back.

        A crash that escapes `execute_plan` is caught here, and every row it
        never reached is completed as not_attempted (D-10), so the finished
        message always carries one outcome per row. PATH wiring and verify run
        only when a row actually ran (L-20-08). The body is wrapped in
        try/finally so InstallRunFinished is posted on every path: a screen
        stuck on a running plan forever is the worst failure mode.
        """
        rows = list(self._rows)
        collected: list[RowOutcome] = []
        run_error: str | None = None
        path_text = ""
        verify_text = ""
        path_error: str | None = None
        verify_error: str | None = None
        try:

            def emit(tool_id: str, line: str) -> None:
                self.post_message(InstallLogLine(tool_id, line))

            runner = StreamingRunner(emit, unbuffer=True)

            def announce_row(row: PlanRow) -> None:
                # The only set_tool site. It runs before every command a row
                # issues (install, UPDATE and RECONFIGURE steps alike), so the
                # streamed lines are attributed to the row that printed them.
                runner.set_tool(row.tool_id)
                self.post_message(RowStarted(row.tool_id))
                if row.disposition is Disposition.UPDATE:
                    self.post_message(InstallLogLine(row.tool_id, _UPDATE_STARTED))

            def record(outcome: RowOutcome) -> None:
                collected.append(outcome)
                self.post_message(RowFinished(outcome))

            attended = not self._inputs.unattended
            outcomes = execute_plan(
                rows,
                RunContext(
                    catalog={tool.id: tool for tool in self._inputs.catalog},
                    platform=self._platform(),
                    runner=runner,
                    resolve_tag=self._inputs.resolve_tag,
                    install=self._inputs.install,
                    updates=self._inputs.updates,
                    terminal_sync=self._inputs.terminal_sync,
                    on_mismatch=self._ask_mismatch if attended else None,
                    confirm_sensitive=self._ask_sensitive_action if attended else None,
                    should_continue=self._should_continue,
                    on_row_started=announce_row,
                    on_outcome=record,
                ),
            )
            collected = list(outcomes)
            if ran_anything(collected):
                path_result, path_fail = run_live(self._inputs.wire_path)
                if path_result is None:
                    path_error = path_fail or "PATH wiring did not complete"
                else:
                    path_text = path_result
                verify_result, verify_fail = run_live(self._inputs.verify)
                if verify_result is None:
                    verify_error = verify_fail or "PATH audit did not complete"
                else:
                    verify_text = verify_result
        except Exception as exc:  # noqa: BLE001 -- the run must report, not die
            # D-07: a crash keeps the rows that finished; the rest are completed
            # as not_attempted in the finally block, so none is dropped.
            first = (str(exc).splitlines() or [""])[0]
            run_error = f"{type(exc).__name__}: {first}"
        finally:
            self.post_message(
                InstallRunFinished(
                    _complete(rows, collected, run_error),
                    run_error,
                    path_text,
                    verify_text,
                    path_error,
                    verify_error,
                )
            )

    def _should_continue(self) -> bool:
        return not self.cancel_event.is_set()

    def _note_output(self, tool_id: str) -> None:
        """Establish tool_id as the in-flight tool and reset the silence window.

        The in-flight tool is established by the first NON-TRANSIENT
        InstallLogLine for that tool, and by nothing else. Installs satisfy
        that because install_tool calls runner.method_started(method.kind)
        before every method (installer/engine.py:137-138), which emits
        "-- trying {method} --" through this same path before the child is
        ever launched; updates satisfy it because the row callback posts
        _UPDATE_STARTED before updates.run. A caller that streams nothing at
        all never establishes an in-flight tool and therefore never shows an
        indicator -- the deliberate D-08 consequence that the screen refuses
        to name a tool it has not heard from.
        """
        self._in_flight = tool_id
        self._last_output_at = self._inputs.now()
        self._silence_noted = False
        self._silence_generation += 1

    def _clear_in_flight(self) -> None:
        self._in_flight = None
        self._last_output_at = None
        self._silence_noted = False
        self._silence_generation += 1

    def _transient_is_current(self, message: InstallLogLine) -> bool:
        return (
            not self.finished
            and self._waiting_prompt is None
            and message.tool_id == self._in_flight
            and self._silence_noted
            and message.generation == self._silence_generation
        )

    def _arm_silence_timer(self, delay: float) -> None:
        """Arm the one-shot silence check, replacing any timer already pending.

        Overwriting the attribute without stopping first is safe only under an
        invariant that is implicit and fragile: today the sole caller other
        than action_start is _check_output_silence, which nulls the attribute
        on its own first line AFTER its own timer has already fired. A second
        arming site -- re-arming on a real log line, or arming again from
        on_prompt_open's close branch -- would orphan a live Timer that
        on_install_run_finished can no longer stop, because it only ever holds
        the newest reference. Enforcing the invariant here costs one branch and
        removes the trap.
        """
        if self._silence_timer is not None:
            self._silence_timer.stop()
        self._silence_timer = self.set_timer(delay, self._check_output_silence)

    def _check_output_silence(self) -> None:
        """One-shot silence check that re-arms itself; never a poll body.

        Re-arming from inside this callback -- rather than resetting a timer
        on every real log line -- keeps exactly one pending Timer at a time.
        A 500-line burst from a chatty installer creates zero extra timers.
        """
        self._silence_timer = None
        if self.finished:
            return
        in_flight = self._in_flight
        last_output_at = self._last_output_at
        if (
            in_flight is None
            or last_output_at is None
            or self._waiting_prompt is not None
            or self._silence_noted
        ):
            self._arm_silence_timer(SILENCE_SECONDS)
            return
        elapsed = self._inputs.now() - last_output_at
        if elapsed < SILENCE_SECONDS:
            self._arm_silence_timer(SILENCE_SECONDS - elapsed)
            return
        self._silence_noted = True
        self.post_message(
            InstallLogLine(
                in_flight, _WAITING_OUTPUT, transient=True, generation=self._silence_generation
            )
        )
        self._arm_silence_timer(SILENCE_SECONDS)

    def _ask_mismatch(self, tool_id: str) -> MismatchChoice:
        self.post_message(PromptOpen(tool_id, True))
        try:
            answer = ask_from_worker(self.app, ChecksumMismatchScreen(tool_id))
        finally:
            self.post_message(PromptOpen(tool_id, False))
        if answer == "retry" or answer == "skip" or answer == "fallback":
            return answer
        sentence = _DISMISSAL_SKIP.format(tool_id=tool_id)
        self.post_message(InstallLogLine(tool_id, sentence))
        return "skip"

    def _ask_sensitive_action(self, tool_id: str, _action: str) -> bool:
        self.post_message(PromptOpen(tool_id, True))
        try:
            answer = ask_from_worker(self.app, SensitiveActionScreen(tool_id))
        finally:
            self.post_message(PromptOpen(tool_id, False))
        if answer == "yes":
            return True
        if answer is None:
            sentence = _DISMISSAL_SENSITIVE.format(tool_id=tool_id)
            self.post_message(InstallLogLine(tool_id, sentence))
        return False

    def on_install_log_line(self, message: InstallLogLine) -> None:
        if message.transient and not self._transient_is_current(message):
            # A transient's world has moved on: a real line, a terminal
            # message, a prompt transition or the run's end was handled
            # between the post and this write. Drop it entirely -- no
            # header, no line -- rather than render a stale reassurance.
            return
        log = self.query_one("#execute-log", RichLog)
        if message.tool_id != self._last_tool_id:
            log.write(f"── {message.tool_id} ──")
            self._last_tool_id = message.tool_id
        cleaned = sanitize_log_line(message.line)
        log.write(f"{message.tool_id} │ {cleaned}")
        dismissed = message.line == _DISMISSAL_SKIP.format(
            tool_id=message.tool_id
        ) or message.line == _DISMISSAL_SENSITIVE.format(tool_id=message.tool_id)
        if dismissed:
            self.status.set(cleaned, "warn")
        if not message.transient:
            self._note_output(message.tool_id)

    def on_row_started(self, message: RowStarted) -> None:
        row = self._row_for(message.tool_id)
        if row is None:
            return
        options = self.query_one("#plan-rows", OptionList)
        prompt = running_row_text(row, id_width(self._rows), self._fold_width())
        options.replace_option_prompt(row.tool_id, prompt)
        options.highlighted = options.get_option_index(row.tool_id)

    def on_row_finished(self, message: RowFinished) -> None:
        outcome = message.outcome
        # A terminal message for some OTHER tool must never clear the actual
        # in-flight tool's silence window; only the matching id clears it.
        if outcome.row.tool_id == self._in_flight:
            self._clear_in_flight()
        options = self.query_one("#plan-rows", OptionList)
        idw = id_width(self._rows)
        options.replace_option_prompt(
            outcome.row.tool_id, outcome_row_text(outcome, idw, self._fold_width())
        )

    def on_install_run_finished(self, message: InstallRunFinished) -> None:
        self.finished = True
        self.remove_class("-running")
        self.add_class("-finished")
        if self._silence_timer is not None:
            self._silence_timer.stop()
            self._silence_timer = None
        self._clear_in_flight()
        self.outcomes = list(message.outcomes)
        options = self.query_one("#plan-rows", OptionList)
        options.can_focus = True
        idw = id_width(self._rows)
        width = self._fold_width()
        for outcome in message.outcomes:
            options.replace_option_prompt(
                outcome.row.tool_id, outcome_row_text(outcome, idw, width)
            )
        failed = (
            exit_code(message.outcomes) != 0
            or message.run_error is not None
            or message.path_error is not None
            or message.verify_error is not None
        )
        severity = Severity.ERROR if failed else Severity.OK
        head = Text(summary_head(message.outcomes), style=SEVERITY_STYLE[severity])
        self.query_one("#execute-head", Static).update(head)
        if failed:
            prefix = "Failed."
        elif ran_anything(message.outcomes):
            prefix = "Done."
        else:
            prefix = "Nothing ran."
        kept = retained(message.outcomes) & set(self._ids)
        still = f" Still selected: {len(kept)}." if kept else ""
        self.status.set(f"{prefix}{still} enter or esc returns to the catalog.", severity)
        self.query_one("#execute-keys", Static).update(_KEYS_FINISHED)
        log = self.query_one("#execute-log", RichLog)
        log.write(
            self._render_captured(lambda console: render_run_report(message.outcomes, console))
        )
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
        if message.run_error:
            log.write(message.run_error)
        # Do not event.stop(): this message must keep bubbling to UnifiedApp,
        # which records the outcomes for the process exit code.

    def action_close(self) -> None:
        if self.finished:
            self.dismiss(self.outcomes)
            return
        if self._start_requested:
            self._wait_token += 1
            self._waiting = False
            self._start_requested = False
            self._cancelled_wait = True
            self.status.set(_WAIT_CANCELLED, "warn")
            self.query_one("#execute-keys", Static).update(self._idle_keys())
            return
        if not self.started:
            self.dismiss(None)
            return
        self.status.set(
            "Installation is still running. Press c to stop after the current tool. "
            "ctrl+c aborts the whole app and can leave the current tool half-installed.",
            "warn",
        )

    def on_prompt_open(self, message: PromptOpen) -> None:
        if message.waiting:
            self._waiting_prompt = message.tool_id
            self._silence_generation += 1
            self.status.set(
                f"Run paused on a question for {message.tool_id}; answer the prompt to continue.",
                "warn",
            )
            return
        self._waiting_prompt = None
        self._last_output_at = self._inputs.now()
        self._silence_noted = False
        self._silence_generation += 1
        if self.started and not self.finished and not self.cancel_event.is_set():
            self.status.set(_CANCEL_AVAILABLE, "ok")

    def _render_captured(self, render: Callable[[Console], None]) -> str:
        buffer = io.StringIO()
        render(Console(file=buffer, width=self._fold_width() + 2, no_color=True))
        # Defense-in-depth: render() prints outcome.errors, which carries
        # untrusted child-process output (CommandError.detail). run.py
        # already sanitizes its own tail; this catches any other producer
        # that writes into the report console without going through it.
        return sanitize_log_line(buffer.getvalue())
