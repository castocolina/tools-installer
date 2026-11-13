"""Unified Textual shell hosting the wizard views behind one app.

The app owns navigation and the screen stack. The base view, doctor, uninstall,
and policies are all functional views. Execution stays behind the pure
`installer/` core invoked from `setup.py`, with one deliberate exception: the
doctor, uninstall, and policies views apply their changes live through
injected closures. The app's run value stays the catalog decision
(`list[str] | None`).

Textual's empty default screen is the neutral root; every view is installed
once and reached through `show_view`. Navigation is therefore a stack with the
root at the bottom: the stack is always `[root, <one view>]` once mounted.
"""

import asyncio
import contextlib
import shlex
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from rich.cells import cell_len
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Input, Label, ListItem, ListView, OptionList, Select, Static
from textual.widgets.option_list import Option
from textual.worker import Worker, WorkerCancelled, WorkerFailed

from installer import cursor_shim, daemon, env_redirect, receipts, runlock, schedules
from installer.agent_settings import ledger_summary
from installer.app import (
    UninstallDecision,
    path_writer_lines_for,
    pnpm_removal_packages,
    removal_change_lines,
    removal_result_lines,
    removal_runs_line,
    settings_change_lines,
    unregister_runs_line,
)
from installer.catalog_tui import CatalogScreen, RefreshRequested, ToolUpdated, health_cell
from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport
from installer.enums import MutationHolder, Severity, Tier, UninstallState
from installer.execute_screen import (
    ExecuteInputs,
    ExecuteScreen,
    InstallRunFinished,
    InstallRunStarted,
)
from installer.guidance import (
    GUARD_ENTER_HINT,
    SAFE_FIX_ENTER_HINT,
    Guidance,
    competing_mechanism_guidance,
    disk_pressure_guidance,
    doctor_guidance,
    guard_guidance,
)
from installer.locations import bin_dir, display_path
from installer.model import Tool
from installer.pnpm_globals import (
    PNPM_SMOKE_FAILED,
    PNPM_SPLIT_GROUP,
    NodeGlobalsReport,
    co_install_warnings,
    reinstall_preview,
)
from installer.pnpm_globals import node_globals as declared_node_globals
from installer.policy import (
    Policy,
    PolicyMove,
    PolicyResult,
    lost_policy_ids,
    move_link_mode,
)
from installer.postinstall import host_labels
from installer.rcclean import PathWriterLine, group_writer_lines
from installer.render import fold_reason, guidance_text, outcome_detail_text, outcome_word
from installer.resolve import UnavailableReason
from installer.run import CommandError
from installer.sanitize import sanitize_log_line
from installer.session import (
    Disposition,
    PlanRow,
    RowOutcome,
    first_line,
    ran_anything,
    retained,
    summary_counts,
)
from installer.shellrc import PathGuardOutcome, guard_path_writers, path_export_guard
from installer.systemd_daemon import SCOPE_SYSTEM, CompetingUnit
from installer.terminal_shell import terminal_sync_warning
from installer.tool_browser import BrowserAdapter, Section, ToolBrowser
from installer.ui_common import (
    BASE_VIEW,
    VIEW_ORDER,
    VIEWS,
    AppScreen,
    WayfindingHeader,
    highlighted_key,
    mark,
    multiline_summary,
    run_live,
)
from installer.uninstall import (
    RemovalPlan,
    SweepResult,
    config_targets,
    policy_owned,
    removal_plan,
    reverse_dependencies,
)
from installer.update import UpdateService
from installer.version_status import (
    Health,
    ToolState,
    VersionRefreshService,
    pnpm_findings,
    uninstall_detail,
    uninstall_group,
    uninstall_label,
)


@dataclass(frozen=True)
class UninstallInputs:
    """Everything the UninstallScreen needs besides the published tool state:
    the active ban names, whether a managed PATH block exists, the active
    shell-tweak ids, and the live removal closure bound by the composition root.

    `ban_names`, `has_path_block`, `tweak_ids` and `retired` are PREDICATES, not their
    results, because each is mutated live by another view in the same process:
    the Policies view writes the ban's shims and aliases and toggles the tweaks,
    and the Doctor view writes the very managed PATH block `has_path_block`
    detects. A value frozen at construction goes stale the moment the user
    does. `UninstallScreen` re-reads all four on every entry and on every
    publish. `retired` re-lists the receipts whose tool id left the catalog (D-09).
    The tool rows are not an input: they are a projection of the
    published state (`version_status.uninstall_group`, `uninstall_label` and
    `uninstall_detail`), so no second classification can disagree with it."""

    ban_names: Callable[[], list[str]]
    has_path_block: Callable[[], bool]
    remove: Callable[[UninstallDecision], SweepResult]
    tweak_ids: Callable[[], tuple[str, ...]] = tuple
    retired: Callable[[], Sequence[Tool]] = tuple
    # D-01/15.6-06 Task 3: the SAME composition-root closure Policies, the
    # direct `u` update, unattended installation, the CLI uninstall route,
    # and interactive ExecuteScreen close already reuse. Called from
    # `on_removal_finished` only after `remove` reports a sweep, so a
    # completed removal always leaves terminal shell configuration in sync
    # (or safely reverted when zsh itself was just removed).
    terminal_sync: Callable[[], str | None] | None = None


# The composition root's disk probe (D-03): callable with no arguments, plus
# one optional keyword, `blocking`, that picks the daemon-state cache verb.
# blocking=True (the default) may run one bounded systemd query, right for a
# Doctor entry; blocking=False never queries at all, which is what a render on
# the Textual event loop needs. `...` rather than a Protocol spelling out that
# keyword: a Protocol method's parameter reads as dead code to vulture.
DiskPressureProbe = Callable[..., DiskPressure]
# The composition root's competing-mechanism probe (WR-10), same
# call shape and same blocking rule as DiskPressureProbe: blocking=True
# may issue bounded read-only systemctl queries, blocking=False peeks
# a memo and never spawns. Read-only in both systemd scopes.
CompetingProbe = Callable[..., tuple[CompetingUnit, ...]]


@dataclass(frozen=True)
class PolicyInputs:
    """The policies the PoliciesScreen renders, each carrying its own bound
    apply/remove closures. The composition root builds these from the pure core.

    `disk_pressure` is the ONE seam the route's single probe travels through:
    UnifiedApp hands it to both DoctorScreen and PoliciesScreen, so no second
    field or UnifiedApp parameter carries the same closure."""

    policies: list[Policy]
    link_mode: Callable[[], str] | None = None
    set_link_mode: Callable[[str], None] | None = None
    disk_pressure: DiskPressureProbe | None = None
    # WR-10: the same seam reasoning as disk_pressure -- one closure, both
    # the Doctor's durable disclosure and the Policies row's detail line.
    competing: CompetingProbe | None = None


@dataclass(frozen=True)
class ScheduleInputs:
    """What the Schedules view renders and acts on. A None `context` is a host with no
    timer manager: every row reads unavailable and nothing is ever written. `disk_pressure`
    and `competing` are the same seams the Policies tmp row used (D-21)."""

    context: schedules.ScheduleContext | None
    present: Callable[[str], bool] | None = None
    disk_pressure: DiskPressureProbe | None = None
    competing: CompetingProbe | None = None
    now: Callable[[], datetime] = datetime.now


# The l log-view toggle's tail length — a plain, bounded slice of the raw log,
# never a re-parse into structured blocks (that is last_run_summary's own job).
_LOG_TAIL_LINES = 20

_NOTHING_TO_REINSTALL = "Nothing to reinstall — pnpm manages no globals here."
# Distinct from _NOTHING_TO_REINSTALL on purpose: an unanswered `pnpm list -g`
# is not an empty global set, and the machine whose pnpm has just replaced
# itself is exactly the one that must not be told there is nothing to restore.
_GLOBALS_UNKNOWN = "pnpm's global set could not be read — install or repair pnpm, then retry."
_GLOBALS_UNKNOWN_COUNT = "pnpm's global set could not be read (pnpm missing, or the query failed)."
_GLOBALS_CHECKING = "Checking pnpm's global set..."
_GLOBALS_UNKNOWN_YET = "Still checking pnpm's global set — press r again in a moment."
# An audit that could not run answers the same question as a pnpm that could not
# be asked: nothing was learned. One shape, so no consumer has to handle two.
_GLOBALS_UNREADABLE = NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)
# A plain constant, never a second call to the injected preview closure: that
# closure is exactly what may have just raised inside the guarded audit call,
# so calling it again for the fallback path would reopen the same hazard.
_GLOBALS_UNREADABLE_PREVIEW = _GLOBALS_UNKNOWN_COUNT

# The console next step installer/guidance.py writes for a low disk with an
# INACTIVE daemon, and its TUI form. Only INACTIVE starts with this prefix:
# the UNAVAILABLE wording (D-03c) names no row, because on that host there is
# no row to enable, so it is deliberately never rewritten into one.
_DISK_PRESSURE_ENABLE_PREFIX = "Turn on tmp cleanup"
_POST_APPLY_REWRITES = (
    (
        f"{SAFE_FIX_ENTER_HINT}, then open a new terminal",
        "The safe fix was applied; open a new terminal",
    ),
    (GUARD_ENTER_HINT, "The guard is offered again after restarting the installer"),
    (SAFE_FIX_ENTER_HINT, "The safe fix was applied"),
)
# The console sentence's own tail names the platform's real one-off command
# (WR-08), so only its leading clause is rewritten for the TUI -- rebuilding
# the whole sentence here would re-introduce a second, platform-blind copy of
# that command.
_DISK_PRESSURE_TUI_PREFIX = "Open the Schedules view and turn on the tmp cleanup row;"


class GlobalsReinstalled(Message):
    """The threaded pnpm-globals reinstall finished; `error` is None on success.

    post_message is Textual's thread-safe hand-off back to the event loop, so
    the worker never touches a widget from its own thread.
    """

    def __init__(self, error: str | None, invalidate_error: str | None = None) -> None:
        self.error = error
        self.invalidate_error = invalidate_error
        super().__init__()


class GlobalsAudited(Message):
    """The threaded `pnpm list -g --json` finished; the screen may now render it.

    Same hand-off as GlobalsReinstalled, for the same reason: the audit spawns a
    subprocess, so it cannot run on the event loop, and its result cannot be
    written into a widget from the worker's own thread. `preview` travels with
    the report because building it also needs to resolve pnpm.
    """

    def __init__(
        self, report: NodeGlobalsReport, preview: str, error: str | None, generation: int
    ) -> None:
        self.report = report
        self.preview = preview
        self.error = error
        # Two audit workers can be in flight at once (e.g. a stale one from
        # screen entry still running when a reinstall finishes and starts a
        # fresh one): exclusive=True only marks the older worker cancelled, it
        # cannot stop a thread already inside subprocess.run. The generation
        # lets on_globals_audited tell which post_message is the one anyone
        # asked for and discard the other, rather than whichever lands last
        # silently overwriting fresher state with stale state.
        self.generation = generation
        super().__init__()


class DiskPressureProbed(Message):
    """The Doctor's threaded blocking disk-pressure read finished (WR-02).

    Carries nothing: the worker's only job is to warm the shared
    TimerStateCache off the event loop, and the render path then reads the
    fresh answer through the non-blocking peek.
    """


class CompetingProbed(Message):
    """The Policies screen's competing-mechanism warm-up worker finished.

    Carries nothing: the worker only fills the shared memo, and the detail
    line then reads it through the non-blocking peek (WR-10).
    """


class JobStatesRead(Message):
    """The Policies screen's threaded read of the systemd-backed rows finished.

    `states` maps a policy id to (active, owned) for every row that read
    cleanly; a row the worker could not read is absent. `generation` is the
    read this answers: the handler drops any other, so a slow older read
    finishing last cannot repaint a stale cell.
    """

    def __init__(
        self,
        generation: int,
        states: dict[str, tuple[bool, bool]],
        error: str | None,
    ) -> None:
        self.generation = generation
        self.states = states
        self.error = error
        super().__init__()


class PolicyToggled(Message):
    """A scheduled-job toggle finished on its thread worker (WR-02).

    `was_active` is the row state the toggle started from; `result` is None
    exactly when run_live reported `error`.
    """

    def __init__(
        self, policy_id: str, was_active: bool, result: PolicyResult | None, error: str | None
    ) -> None:
        self.policy_id = policy_id
        self.was_active = was_active
        self.result = result
        self.error = error
        super().__init__()


@dataclass(frozen=True)
class ScheduleChange:
    """One user change to a schedule: the verb and the values it carries."""

    schedule_id: str
    verb: Literal["on", "off", "retime", "model"]
    was_drift: bool = False
    interval: int = 0
    start: str = ""
    model: str = ""


class ScheduleChanged(Message):
    """A schedule change finished on its thread worker; `report` is None exactly when
    run_live reported `error`."""

    def __init__(
        self, change: ScheduleChange, report: schedules.ApplyReport | None, error: str | None
    ) -> None:
        self.change = change
        self.report = report
        self.error = error
        super().__init__()


class ScheduleManagerProbed(Message):
    """The Schedules screen's threaded timer-manager probe finished."""

    def __init__(self, reachable: bool) -> None:
        self.reachable = reachable
        super().__init__()


class _BodyStatic(Static):
    """Static with a small public render seam for headless tests."""

    @property
    def renderable(self) -> Any:
        return self.render()


_DOCTOR_READ_ERROR = "Could not read the doctor state: "


class DoctorScreen(AppScreen):
    """PATH audit and safe PATH repair in one view."""

    # Narrow .app from App[Unknown] (MessagePump default) so push_screen is typed.
    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "apply", "apply", show=True),
        Binding("r", "reinstall_globals", "reinstall pnpm globals", show=True),
    ]
    DEFAULT_CSS = """
    DoctorScreen {
        align: center top;
    }
    DoctorScreen #doctor-body {
        width: 76;
        max-width: 90%;
        height: auto;
        margin: 2 0;
        padding: 1 2;
        border: round $accent;
    }
    /* Docked so the card cannot cover it at 80x20; docks overlap, so clear the footer. */
    DoctorScreen > StatusLine {
        dock: bottom;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        report: DoctorReport,
        guard_state: Callable[[], tuple[dict[str, bool], str | None]],
        fix_preview: str | Callable[[], str],
        fix: Callable[[], None],
        *,
        node_globals: Callable[[], NodeGlobalsReport],
        globals_preview: Callable[[NodeGlobalsReport], str],
        reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]],
        disk_pressure: DiskPressureProbe | None = None,
        competing: CompetingProbe | None = None,
        duplicate_writers: Mapping[Path, tuple[Path, ...]] | None = None,
        writer_lines: Sequence[PathWriterLine] = (),
        rescan_writer_lines: Callable[[], Sequence[PathWriterLine]] | None = None,
        guard_file: Callable[[Path, Sequence[PathWriterLine]], PathGuardOutcome] | None = None,
        tools: Sequence[Tool] = (),
        version_refresh: VersionRefreshService | None = None,
    ) -> None:
        super().__init__(view="doctor")
        self._report = report
        # Doctor reads the pnpm findings the tiers read (ToolState.reasons) and
        # records its own audit as session evidence; with no service it does neither.
        self._node_entries = declared_node_globals(tools)
        self._version_refresh = version_refresh
        # Computed ONCE by the composition root, which already does IO, and
        # held as data. _refresh_guidance is IO-free by construction and runs
        # on every navigation, so it must never be the thing that reads rc
        # files off disk.
        self._writer_lines = list(writer_lines)
        self._duplicate_writers = duplicate_writers or {}
        self._rescan_writer_lines = rescan_writer_lines
        self._guard_file = guard_file
        self.guard_results: list[str] = []
        self._pending_guards: list[tuple[Path, tuple[PathWriterLine, ...]]] = []
        # A predicate, not its result, for the guard_state reason: the
        # Policies view can enable the background cleanup one navigation step
        # away, so every entry re-reads it. WR-02: the daemon half of the
        # blocking read may spawn `systemctl --user is-active` (bounded, but
        # a frozen UI for its duration), so the event loop only ever calls it
        # with blocking=False (TimerStateCache.peek). The blocking read runs in
        # _probe_disk_pressure_worker, which then asks for a re-render.
        self.disk_pressure = disk_pressure
        self.disk_probing = False
        # WR-10: read-only competing-mechanism detection. Same split as
        # disk_pressure: the render path peeks, the worker below does the
        # blocking read that may issue `systemctl list-unit-files`.
        self.competing = competing
        # A predicate, not its result: the Policies view installs and removes the
        # pip/npm ban live, one nav step away, and guard_guidance renders exactly
        # that state. The PATH audit beside it stays a snapshot on purpose — the
        # process PATH cannot change until the shell restarts.
        self._guard_state = guard_state
        # Same predicate-not-its-result reasoning the guard_state parameter
        # already carries three lines above: the Policies view changes
        # something the Doctor renders, one navigation step away.
        if callable(fix_preview):
            self._fix_preview = fix_preview
        else:
            preview_text = fix_preview
            self._fix_preview = lambda: preview_text
        self._fix = fix
        # node_globals shells out to `pnpm list -g --json`, so it is NEVER
        # called from the event loop: _audit_globals_worker calls it on a thread
        # and posts GlobalsAudited back. The result is held here rather than
        # re-derived per render, which is what makes every render IO-free.
        # globals_preview takes the report for the same reason — building the
        # preview from a fresh audit would put the subprocess back on the loop.
        # reinstall_globals takes its package list for the same reason again,
        # and it removes the last shared cell two threads could race on.
        self._node_globals = node_globals
        self._globals_preview = globals_preview
        self._reinstall_globals = reinstall_globals
        # None until the first audit lands: "not asked yet" is not "pnpm manages
        # nothing" any more than "could not be asked" is (NodeGlobalsReport.known).
        self._globals_report: NodeGlobalsReport | None = None
        self._globals_preview_text = ""
        self.guidance: list[Guidance] = []
        self.applied = False
        self.error: str | None = None
        # Own flags, not a reuse of applied/error: action_apply opens with
        # `if self.applied: return`, so sharing them would make each action
        # silently suppress the other and each section render the other's outcome.
        self.globals_done = False
        self.globals_error: str | None = None
        self.globals_invalidate_error: str | None = None
        # The reinstall is the only subprocess a view starts, and `pnpm add -g`
        # of a Puppeteer-carrying package is minutes, not seconds. It runs in a
        # thread worker so the event loop keeps painting; this flag is what the
        # body renders while it does, and what stops a second `r` stacking a
        # concurrent install.
        self.globals_running = False
        # The audit's own in-flight flag. It cannot share globals_running: the
        # two workers run for different reasons, and a render that cannot tell
        # them apart would say "Reinstalling" for a read.
        self.globals_auditing = False
        # Not globals_error: "nothing to reinstall" is not a failure, and the
        # error branch renders "Reinstall failed." in red.
        self.globals_note: str | None = None
        # The two live reads' failures, and the status line this screen last wrote
        # for them (cleared only while it still holds that copy).
        self._guard_error: str | None = None
        self._preview_error: str | None = None
        self._read_line: str | None = None
        # Bumped every time an audit worker is actually started; carried on
        # its GlobalsAudited message so a superseded worker's result (one
        # started before a newer request, still running when the newer one
        # lands) is recognisably stale and discarded rather than clobbering
        # fresher state.
        self._globals_audit_generation = 0
        # The service epoch the current audit started at: its findings are
        # dropped when a mutation invalidated the cache meanwhile (C-09).
        self._globals_audit_epoch = 0

    def compose_body(self) -> ComposeResult:
        yield _BodyStatic(id="doctor-body")

    def enter_view(self) -> None:
        """Re-read the ban state on every entry, and re-ask pnpm off the loop.

        Installed screens are suspended, not unmounted: without this, Policies
        → toggle the ban → Doctor reports the state from before the toggle. The
        globals audit needs the same freshness but cannot be taken here
        synchronously, so it is started as a worker and rendered when it lands.
        The screen is mounted before entry, so the first entry starts it too.
        """
        super().enter_view()
        self._start_globals_audit()
        self._start_disk_probe()

    def state_refreshed(self) -> None:
        self._refresh_guidance()
        self._refresh_body()

    def _start_disk_probe(self) -> None:
        if self.disk_pressure is None:
            return
        self.disk_probing = True
        self._probe_disk_pressure_worker()

    @work(thread=True, exclusive=True, group="disk-pressure", exit_on_error=False)
    def _probe_disk_pressure_worker(self) -> None:
        """Take the blocking background-state reads off the event loop (WR-02).

        The answer is not carried back: the read's purpose is to refresh the
        shared TimerStateCache, which the render path then peeks. The same
        (OSError, ValueError) second layer _disk_pressure_items uses applies,
        and the message is posted in a finally so disk_probing always clears.
        """
        try:
            probe = self.disk_pressure
            if probe is not None:
                with contextlib.suppress(OSError, ValueError):
                    probe()
            competing = self.competing
            if competing is not None:
                # WR-10: warmed here for the same reason -- the detection
                # spawns bounded read-only systemctl queries.
                with contextlib.suppress(OSError, ValueError, CommandError):
                    competing()
        finally:
            self.post_message(DiskPressureProbed())

    def on_disk_pressure_probed(self, _message: DiskPressureProbed) -> None:
        self.disk_probing = False
        self._refresh_guidance()
        if self.is_mounted:
            self._refresh_body()

    def _start_globals_audit(self) -> None:
        if self.globals_running:
            # A reinstall in flight re-audits when it finishes.
            return
        # Deliberately NOT guarded on globals_auditing: the post-reinstall
        # re-audit must always get a fresh worker, even if an older one
        # (started on screen entry) is still running. exclusive=True cancels
        # the older Worker on the Textual side, but a thread already inside
        # subprocess.run keeps running to completion regardless — its result
        # is still delivered. Bumping the generation here is what lets
        # on_globals_audited recognise that stale delivery and drop it.
        self._globals_audit_generation += 1
        service = self._version_refresh
        self._globals_audit_epoch = service.epoch if service is not None else 0
        self.globals_auditing = True
        self._audit_globals_worker(self._globals_audit_generation)

    def _refresh_guidance(self) -> None:
        # IO-free by construction. The pnpm findings are not here: they are the
        # published ToolState reasons, rendered by _refresh_body.
        read, self._guard_error = run_live(self._guard_state)
        # A failed read contributes nothing: the earlier answer is not kept (B3).
        status, warning = read if read is not None else ({}, None)
        # Position is a decision, pinned by a test: disk pressure follows the guard items.
        self.guidance = (
            doctor_guidance(self._report, self._duplicate_writers, self._writer_lines)
            + guard_guidance(status, warning)
            + self._disk_pressure_items()
            + self._competing_items()
        )

    def _disk_pressure_items(self) -> list[Guidance]:
        if self.disk_pressure is None:
            return []
        # Plan 15.7-02's D-03b already makes probe_disk_pressure TOTAL over
        # filesystem and probe-conversion failure, and any other exception
        # (a programming error) propagates uncaught. This guard is the
        # documented second layer over the INJECTED closure a caller composes
        # -- the same named set run_doctor uses, never a blanket except.
        try:
            pressure = self.disk_pressure(blocking=False)
        except (OSError, ValueError):
            return []
        return disk_pressure_guidance(pressure)

    def _competing_items(self) -> list[Guidance]:
        if self.competing is None:
            return []
        # peek only: this runs on the event loop, and a blocking read here
        # would spawn the very systemctl queries WR-02 moved off it.
        try:
            units = self.competing(blocking=False)
        except (OSError, ValueError, CommandError):
            return []
        return competing_mechanism_guidance(units)

    def _refresh_body(self) -> None:
        # A worker result can land after the app stopped running, when the
        # body may already be gone (the 765c0e5 shutdown race).
        if not self.app.is_running:
            return
        body = self.query_one("#doctor-body", _BodyStatic)
        text = Text()
        text.append("PATH Doctor\n", style="bold")
        text.append("Audit\n", style="bold")
        text.append(guidance_text(self._tui_guidance()))
        text.append("\n\nSafe fix preview\n", style="bold")
        preview, self._preview_error = run_live(self._fix_preview)
        text.append(preview or "")
        text.append("\n\nAction\n", style="bold")
        if self.applied:
            text.append("PATH wired.", style="green")
            text.append("\nRestart your shell or run `source ~/.myshellrc` to apply.")
            # The audit above is a process-lifetime snapshot (setup.py::_build_app
            # reads os.environ["PATH"] once) -- it genuinely cannot reflect this
            # fix yet. Say so explicitly, framed as expected rather than as a
            # second warning, only once there is something frozen to explain.
            text.append(
                "\nThe audit above still describes the PATH this process started "
                "with -- that's expected until you open a new shell or run "
                "`source ~/.myshellrc`."
            )
        elif self.error is not None:
            text.append("Fix failed.", style="red")
            text.append(f"\n{self.error}")
            text.append("\nCheck the target is writable, then press enter to retry.")
        else:
            text.append("Press enter to wire the managed PATH into your shells.", style="yellow")
            text.append("\nViewing this screen did not change your shell files.")
        for line in self.guard_results:
            text.append(f"\n{line}")
        report = self._globals_report
        text.append("\n\npnpm-managed globals\n", style="bold")
        # Both counts come from pnpm's own global list, never from the catalog:
        # a registry entry declares that a tool CAN install this way, which is
        # not evidence that it did. A count is only printable when the list was
        # actually read: report None means the audit has not landed yet and
        # report.known False means it landed empty-handed, and "0 package(s)"
        # would state either of those unknowns as a fact.
        if report is None:
            text.append(f"{_GLOBALS_CHECKING}\n", style="yellow")
        elif report.known:
            text.append(
                f"{len(report.managed)} package(s) in pnpm's global set, "
                f"{len(report.entries)} of them catalog tool(s).\n"
            )
        else:
            text.append(f"{_GLOBALS_UNKNOWN_COUNT}\n", style="yellow")
        # Print the core's preview string verbatim, as resolved by the audit
        # worker. Do not call reinstall_argv here: a non-empty set with no
        # resolvable pnpm is a returned string, never an argv and never an
        # exception (architecture rule 3).
        # Skipped when the count line above already said the same thing: a
        # known=False preview is the identical "could not be read" sentence
        # with only the tail changed, and printing both reads like a stutter.
        for entry in self._node_entries:
            service = self._version_refresh
            state = service.state_of(entry.tool_id) if service is not None else None
            if state is None or state.health in (Health.CHECKING, Health.UNAVAILABLE):
                continue
            for reason in pnpm_findings(entry.tool_id, state.reasons):
                # Plain text, never markup: a reason can carry child-process output.
                text.append(sanitize_log_line(f"{entry.tool_id}: {reason}") + "\n", style="yellow")
        if report is None or report.known:
            text.append(self._globals_preview_text)
        text.append("\n")
        if self.globals_running:
            text.append("Reinstalling the pnpm global set...", style="yellow")
            text.append("\nOutput is captured; this can take several minutes.")
        elif self.globals_done:
            text.append("pnpm globals reinstalled.", style="green")
        elif self.globals_error is not None:
            text.append("Reinstall failed.", style="red")
            text.append(f"\n{self.globals_error}")
        elif self.globals_note is not None:
            text.append(self.globals_note, style="yellow")
        else:
            text.append("Press r to reinstall the pnpm-managed global set.", style="yellow")
        if self.globals_invalidate_error is not None and not self.globals_running:
            text.append(
                f"\nversion cache invalidation failed: {self.globals_invalidate_error}",
                style="yellow",
            )
        body.update(text)
        self._sync_read_status()

    def _sync_read_status(self) -> None:
        error = self._guard_error or self._preview_error
        if error is not None:
            self._read_line = f"{_DOCTOR_READ_ERROR}{error.partition(chr(10))[0]}."
            self.status.set(self._read_line, "error")
        elif self._read_line is not None:
            self.status.retract(self._read_line)
            self._read_line = None

    def _tui_guidance(self) -> list[Guidance]:
        """Keep CLI doctor wording unchanged while the TUI points to the live apply action."""
        rewritten: list[Guidance] = []
        for item in self.guidance:
            if item.next_step.startswith("Run `make fix`"):
                rewritten.append(
                    replace(
                        item,
                        next_step=(
                            f"{SAFE_FIX_ENTER_HINT}, then open a new terminal "
                            "(or `source ~/.myshellrc`)."
                        ),
                    )
                )
            elif item.next_step.startswith(_DISK_PRESSURE_ENABLE_PREFIX):
                tail = item.next_step[len(_DISK_PRESSURE_ENABLE_PREFIX) :]
                tail = tail.split(";", 1)[1].strip() if ";" in tail else tail.strip()
                rewritten.append(replace(item, next_step=f"{_DISK_PRESSURE_TUI_PREFIX} {tail}"))
            else:
                rewritten.append(item)
        if not self.applied:
            return rewritten
        settled: list[Guidance] = []
        for item in rewritten:
            step = item.next_step
            for old, new in _POST_APPLY_REWRITES:
                step = step.replace(old, new)
            settled.append(item if step == item.next_step else replace(item, next_step=step))
        return settled

    def action_apply(self) -> None:
        if self.applied:
            return
        if self.app.refuse_if_mutating(self):
            return
        # Never write rc files the user was not shown (T-21-41, C-11): the
        # re-render re-reads the preview, and a failure keeps the error status.
        if self._preview_error is not None:
            self._refresh_body()
            self.post_message(RefreshRequested())
            return
        _, self.error = run_live(self._fix)
        self.applied = self.error is None
        # Unconditional, not success-gated: run_live runs the callable BEFORE
        # mapping an exception to self.error, so a failed fix can already have
        # moved the guard state by the time we get here. Recompute the
        # guidance list before rendering it, exactly like the three sibling
        # events (on_mount, enter_view, on_globals_audited) already do.
        self._refresh_guidance()
        self._refresh_body()
        # Guarding a foreign line is independent of the managed-block fix. The
        # fix error still renders first; the fresh re-scan below reads whatever
        # the fix left on disk, so a grown managed block cannot shift a foreign
        # line out from under its record.
        if self._guard_file is None:
            self.post_message(RefreshRequested())
            return
        rescan = self._rescan_writer_lines
        self._adopt_writer_lines(rescan() if rescan is not None else self._writer_lines)
        self._pending_guards = self._guardable_files()
        if not self._pending_guards:
            self.post_message(RefreshRequested())
            return
        self._guard_next()

    def _adopt_writer_lines(self, lines: Sequence[PathWriterLine]) -> None:
        self._writer_lines = list(lines)
        self._duplicate_writers = group_writer_lines(self._writer_lines)

    def _guardable_files(self) -> list[tuple[Path, tuple[PathWriterLine, ...]]]:
        grouped: dict[Path, list[PathWriterLine]] = {}
        for record in self._writer_lines:
            grouped.setdefault(record.rc_path, []).append(record)
        return [
            (path, tuple(record for record in records if record.guardable))
            for path, records in grouped.items()
            if any(record.guardable for record in records)
        ]

    def _guard_next(self) -> None:
        if not self._pending_guards:
            self._finish_guard_chain()
            return
        path, records = self._pending_guards.pop(0)
        self.app.push_screen(ConfirmGuardFile(path, records), self._guard_callback(path, records))

    def _guard_callback(
        self, path: Path, records: Sequence[PathWriterLine]
    ) -> Callable[[bool | None], None]:
        # Same strict callback type as UninstallScreen._on_confirm: Textual
        # passes Optional[ScreenResultType], so a bare nested function is Unknown.
        def answer(confirmed: bool | None) -> None:
            self._guard_answered(path, records, confirmed)

        return answer

    def _guard_answered(
        self, path: Path, records: Sequence[PathWriterLine], confirmed: bool | None
    ) -> None:
        if confirmed:
            self._record_guard(path, records)
        else:
            self.guard_results.append(f"skipped {path}")
        self._guard_next()

    def _record_guard(self, path: Path, records: Sequence[PathWriterLine]) -> None:
        guard = self._guard_file
        if guard is None:
            return
        outcome, error = run_live(lambda: guard(path, records))
        if error is not None:
            self.guard_results.append(f"refused {path}: {error}")
            return
        if outcome is not None and outcome.status == "guarded":
            self.guard_results.append(f"guarded {path}")
            return
        reason = outcome.reason if outcome is not None and outcome.reason else "nothing to guard"
        self.guard_results.append(f"refused {path}: {reason}")

    def _finish_guard_chain(self) -> None:
        rescan = self._rescan_writer_lines
        if rescan is not None:
            self._adopt_writer_lines(rescan())
        # No render here: this runs from the last modal's callback, and the
        # resume that follows renders Doctor once (C-08, RR-04).
        self.post_message(RefreshRequested())  # the whole mutation has ended

    def action_reinstall_globals(self) -> None:
        # globals_done needs no message: the body already renders the success
        # line, so a repeat press is answered by what is on screen.
        if self.globals_done:
            return
        if self.app.refuse_if_mutating(self, cross_process=True):
            return
        if self.globals_running:
            return
        if self.globals_auditing:
            # Covers both "no audit has ever landed" (self._globals_report is
            # still None: on_mount starts the first audit synchronously, so
            # that window and this flag are the same window) and "a fresher
            # audit is now re-asking pnpm" (screen entry, or a just-finished
            # reinstall) while an older report is still what's on screen.
            # Acting on that report here is exactly how a reinstall could
            # once run against a superseded package list. Refuse and let the
            # in-flight audit's own landing (on_globals_audited) answer this
            # note.
            self.globals_note = _GLOBALS_UNKNOWN_YET
            self._refresh_body()
            self.post_message(RefreshRequested())  # a refusal still ends with one pass
            return
        # Not auditing, past __init__: an audit has landed and set this.
        report = self._globals_report
        if report is None:
            return  # unreachable: globals_auditing is False only once one has
        # The footer advertises `r` (ui_common.VIEWS), so a keypress that
        # changes nothing on screen reads as a broken binding. The two
        # answers are not interchangeable: one is a fact about the machine,
        # the other is an admission that the machine was not readable.
        if not report.known:
            # There is nothing to retry a fixed message against: the last
            # read simply failed, and the only screen action that changes
            # that is asking again.
            self.globals_note = _GLOBALS_UNKNOWN
            self._refresh_body()
            self._start_globals_audit()
            self.post_message(RefreshRequested())
            return
        if not report.managed:
            self.globals_note = _NOTHING_TO_REINSTALL
            self._refresh_body()
            self.post_message(RefreshRequested())
            return
        self.globals_note = None
        self.globals_invalidate_error = None
        if not self.app.begin_mutation(MutationHolder.GLOBALS_REINSTALL, screen=self):
            return
        self.globals_running = True
        self._refresh_body()
        # The package list is passed in rather than re-derived inside the
        # worker: re-deriving would put `pnpm list -g --json` on a second
        # thread, and the set the user consented to is the one on screen.
        self._reinstall_globals_worker(report.managed)

    # Distinct groups: `exclusive` cancels within a group, so leaving both
    # workers in the default one would let a reinstall cancel an in-flight
    # audit and vice versa.
    @work(thread=True, exclusive=True, group="globals-reinstall", exit_on_error=False)
    def _reinstall_globals_worker(self, packages: tuple[str, ...]) -> None:
        """Run the reinstall off the event loop, then hand the outcome back to it.

        A synchronous subprocess here would freeze every frame for the length of
        a `pnpm add -g`. Widgets may only be touched from the app's own thread,
        hence a posted message rather than a direct refresh.
        """
        error: str | None = "the reinstall did not complete"
        invalidate_error: str | None = None
        service = self._version_refresh
        try:
            _, error = run_live(lambda: self._reinstall_globals(packages))
        finally:
            # A failed or crashed `pnpm add -g` can write before it fails, so the
            # cache is invalidated either way.
            try:
                if service is not None:
                    invalidate_error = "the cache invalidation did not complete"
                    _, invalidate_error = run_live(
                        lambda: service.invalidate(reason="pnpm globals reinstalled")
                    )
            finally:
                # Always posted: the handler releases the app lock.
                self.post_message(GlobalsReinstalled(error, invalidate_error))

    @work(thread=True, exclusive=True, group="globals-audit", exit_on_error=False)
    def _audit_globals_worker(self, generation: int) -> None:
        """Ask pnpm what it manages globally, off the event loop.

        `pnpm list -g --json` is a subprocess like the reinstall is, and it was
        the last one still running on the loop: on a cold cache every Doctor
        render blocked the whole UI for its duration, with no timeout and no
        interruptible path (Textual holds the terminal in raw mode, so a Ctrl+C
        arrives as a byte on a queue the blocked loop is not draining). It runs
        here for the same reason the reinstall does, and hands its result back
        the same way. `generation` travels with the result so a superseded
        worker's answer can be told apart from the one anyone is waiting on.
        """
        # Both the audit and the preview it feeds must sit inside the SAME
        # guarded call: self._globals_preview also resolves pnpm (real_pnpm ->
        # Path.home()), so it can raise for the same reasons _node_globals
        # can. Guarding only the first left the second free to turn a
        # resolver failure into an uncaught WorkerFailed that kills the app,
        # rather than the "could not be read" text this worker exists to
        # show instead.
        report, preview = _GLOBALS_UNREADABLE, _GLOBALS_UNREADABLE_PREVIEW
        error: str | None = "the audit did not complete"
        try:
            outcome, error = run_live(self._audit_globals)
            if outcome is not None:
                report, preview = outcome
        finally:
            # Always posted, even on an exception run_live does not map (C-13):
            # the handler is what clears globals_auditing.
            self.post_message(GlobalsAudited(report, preview, error, generation))

    def _audit_globals(self) -> tuple[NodeGlobalsReport, str]:
        report = self._node_globals()
        return report, self._globals_preview(report)

    def on_globals_audited(self, message: GlobalsAudited) -> None:
        if message.generation != self._globals_audit_generation:
            # A stale worker's answer, superseded by a newer audit request
            # (e.g. the post-reinstall re-audit) already in flight. The
            # current generation's own message is still coming; do not clear
            # globals_auditing or apply this outdated report over it.
            return
        self.globals_auditing = False
        self._globals_report = message.report
        self._globals_preview_text = message.preview
        self._record_pnpm_evidence(message.report)
        # Any note naming the audit itself (waiting for it, or the previous
        # one having failed) is answered by this landing one way or another:
        # the fresh report is what the screen now shows instead. A note
        # about the REINSTALL's own outcome is a different lifecycle
        # (globals_done/globals_error), never written here, so this cannot
        # clear one of those by mistake.
        if self.globals_note in (_GLOBALS_UNKNOWN_YET, _GLOBALS_UNKNOWN):
            self.globals_note = None
        self._refresh_guidance()
        self._refresh_body()

    def _record_pnpm_evidence(self, report: NodeGlobalsReport) -> None:
        """Hand the audit's findings to the next pass (D-13); ask for one only
        when what is stored changed. An unreadable audit stores nothing."""
        service = self._version_refresh
        if service is None or not report.known:
            return
        changed = False
        for entry in self._node_entries:
            # Child output: sanitized once here, so every view renders clean text.
            broken = tuple(
                sanitize_log_line(PNPM_SMOKE_FAILED.format(tool_id=entry.tool_id, reason=reason))
                for tool_id, reason in report.unhealthy
                if tool_id == entry.tool_id
            )
            notes = tuple(
                PNPM_SPLIT_GROUP.format(names=", ".join(group))
                for group in report.split_groups
                if entry.npm_pkg in group
            )
            changed |= service.record_evidence(
                entry.tool_id, epoch=self._globals_audit_epoch, broken=broken, notes=notes
            )
        if changed and not self.app.quitting:
            self.app.request_refresh()

    def on_globals_reinstalled(self, message: GlobalsReinstalled) -> None:
        self.app.end_mutation()
        self.globals_running = False
        self.globals_error = message.error
        self.globals_invalidate_error = message.invalidate_error
        self.globals_done = message.error is None
        self._refresh_body()
        # The globals audit is a live `shutil.which` probe whose answer this
        # action just tried to change — unlike the PATH audit, which is a
        # deliberate snapshot. Without this the screen renders "mmdc went
        # missing" directly above "pnpm globals reinstalled." Re-asking is a
        # subprocess, so it goes back through the worker rather than being
        # taken inline here, where it would block the loop twice over.
        self._start_globals_audit()
        self.post_message(RefreshRequested())


@dataclass(frozen=True)
class _UninstallEntry:
    """A browsable uninstall row: either a classified tool or an environment
    pseudo-row (the pip/npm ban, the managed PATH block, or the shell tweaks).

    `key` is the stable id (a tool id, or "#ban"/"#path-block"/"#tweaks"). `cells`
    are the pre-rendered columns. `selectable` gates toggling (removable tools and
    the env rows are selectable; managed/absent/unavailable tools are not).
    `detail` is the detail-bar line. `paths` are the tool's removable artifacts
    (empty for env rows). `is_ban`/`is_path_block`/`is_tweaks` flag the env rows
    so a selection maps back to the UninstallDecision levers. `tool` is the
    tool for a tool row, None for an environment row. `group` is the section a
    tool row sits in (`uninstall_group`), None for an environment row."""

    key: str
    cells: list[Text]
    selectable: bool
    detail: str
    paths: tuple[Path, ...]
    is_ban: bool
    is_path_block: bool
    is_tweaks: bool = False
    is_settings: bool = False
    tool: Tool | None = None
    group: UninstallState | None = None
    # The command the row's preview showed (L1/L3); the decision hands it back to the remover.
    argv: tuple[str, ...] = ()
    # The hook undo the row's preview showed (D-04); the decision hands it back the same way.
    unregister: tuple[tuple[str, ...], ...] = ()
    # A retired receipt's row (D-09): `tool` is set, `group` is None, there is no catalog state.
    is_retired: bool = False
    # The removal plan a retired row shows; the detail bar and the confirm review read it.
    retired_plan: RemovalPlan | None = None


# Section titles per state, in display order. The "environment" section holds the
# ban/PATH pseudo-rows.
_STATE_TITLES: tuple[tuple[UninstallState, str], ...] = (
    (UninstallState.REMOVABLE, "removable here"),
    (UninstallState.MANAGED, "managed elsewhere"),
    (UninstallState.ABSENT, "nothing to do"),
    (UninstallState.UNAVAILABLE, "nothing to do"),
)
# CR-03: the "What gets removed" cell has a fixed budget because left/right switch
# views, so a too-wide table can never be scrolled on the screen whose Enter
# deletes files; ConfirmUninstall still lists every path.
_REMOVES_CELL_MAX = 40
_NOTHING_TO_UNINSTALL = "Nothing to uninstall."
_BAN_KEY = "#ban"
_BLOCK_KEY = "#path-block"
_TWEAK_KEY = "#tweaks"
_SETTINGS_KEY = "#settings"
_ENV_KEYS = (_BAN_KEY, _BLOCK_KEY, _TWEAK_KEY, _SETTINGS_KEY)
# (ban names, PATH block present, active tweak ids, ledgered settings files, retired receipts
# with the removal plan each one shows)
_EnvState = tuple[
    list[str],
    bool,
    tuple[str, ...],
    tuple[Path, ...],
    tuple[tuple[Tool, RemovalPlan], ...],
]
_REMOVAL_QUIT_WAIT = "Waiting for the removal to finish…"
_REMOVAL_QUIT_CUT = "Quit before the removal finished; some files may remain."


def _has_daemon_id(ids: tuple[str, ...]) -> bool:
    """True when any id in ids is the background daemon's own namespaced id.

    Mirrors `installer.app._has_daemon_id` exactly: a tiny, named predicate
    rather than an inline generator expression repeated at every daemon-aware
    copy call site (preview row + success summary), keeping both byte-for-byte
    consistent with each other and with the CLI's own equivalent wording.
    """
    return any(policy_id.startswith("daemon:") for policy_id in ids)


def config_split(
    flagged: Sequence[Tool],
    catalog: Sequence[Tool],
    state_of: Callable[[Tool], ToolState | None],
) -> tuple[dict[str, tuple[Path, ...]], dict[str, tuple[str, ...]]]:
    """Which declared config each flagged tool deletes, and which it keeps (UI-SPEC A5).

    The first map is tool id -> its existing expanded config paths that every catalog
    tool declaring the path has flagged. The second maps a kept path's declared `~`
    form to the declaring tool ids that stay. Existence comes from each flagged tool's
    published state, so this never touches the filesystem on the UI thread.
    """
    flagged_ids = {tool.id for tool in flagged}
    deleted: dict[str, tuple[Path, ...]] = {}
    kept: dict[str, tuple[str, ...]] = {}
    for tool in flagged:
        state = state_of(tool)
        if state is None:
            continue
        for entry, path in config_targets(tool):
            if path not in state.removable.config:
                continue
            declaring = [other for other in catalog if path in dict(config_targets(other)).values()]
            staying = tuple(other.id for other in declaring if other.id not in flagged_ids)
            if staying:
                kept[entry] = tuple(dict.fromkeys((*kept.get(entry, ()), *staying)))
            else:
                deleted[tool.id] = (*deleted.get(tool.id, ()), path)
    return deleted, kept


_REVIEW_COLUMN = 54  # the confirm modal's text column: width 60 less the border and padding


def _review_line(text: str, style: str = "") -> Text:
    """One review line, folded at the text column with a 2-cell hanging indent (UI-SPEC)."""
    line = fold_reason(Text(), text, 2, _REVIEW_COLUMN)
    line.stylize(style)
    return line


def _retired_detail(tool_id: str, plan: RemovalPlan) -> str:
    """A retired row's detail bar (UI-SPEC section 2): what is proven and what the user removes."""
    head = f"retired: {tool_id} is no longer in the catalog"
    if plan.hint is not None:  # a manager kind: the user removes the package, nothing runs
        return f"{head} · {plan.hint}"
    if plan.yourself:
        leftover = f"remove it yourself: {', '.join(str(path) for path in plan.yourself)}"
        proven = " · recorded files re-checked before deletion" if plan.removable else ""
        return f"{head}{proven} · {leftover}"
    if plan.removable:
        return f"{head} · recorded files re-checked before deletion"
    return f"{head} · nothing to delete; confirming retires the receipt"


def _retired_review_lines(tool_id: str, plan: RemovalPlan) -> list[str]:
    """A selected retired row's confirm-review lines, in a catalog row's `<id>: ...` shape."""
    if plan.hint is not None:  # a manager kind: the user removes the package
        return [f"{tool_id}: {plan.hint}"]
    lines: list[str] = []
    if plan.removable:
        lines.append(f"{tool_id}: deletes {', '.join(str(path) for path in plan.removable)}")
    if plan.yourself:
        kept = ", ".join(str(path) for path in plan.yourself)
        lines.append(f"{tool_id}: remove it yourself: {kept}")
    return lines or [f"{tool_id}: nothing to delete; confirming retires the receipt"]


class RemovalFinished(Message):
    """The removal worker ended. `swept` is None when the remover failed or raised
    (then `error` says why); `invalidate_error` is the post-removal cache failure."""

    def __init__(
        self,
        decision: UninstallDecision,
        swept: SweepResult | None,
        error: str | None,
        invalidate_error: str | None,
    ) -> None:
        super().__init__()
        self.decision = decision
        self.swept = swept
        self.error = error
        self.invalidate_error = invalidate_error


class UninstallScreen(AppScreen):
    """Full catalog-parity uninstall browser. Every tool is listed with its
    removability state; only removable tools (and the env rows) toggle. Enter
    removes exactly the selected artifacts + env levers, applied live."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("c", "toggle_config", "config"),
    ]

    # Narrow .app from App[Unknown] (MessagePump default) to the concrete host
    # app so push_screen() is typed without an Unknown generic param.
    # UnifiedApp is defined later in this module; the string forward reference is
    # resolved by pyright (which analyses all module-level names together).
    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    def __init__(
        self,
        inputs: UninstallInputs,
        *,
        tools: Sequence[Tool],
        version_refresh: VersionRefreshService | None = None,
    ) -> None:
        super().__init__(view="uninstall", accent="red")
        # Tool ids whose "delete config too" flag is on (D-11). Never persisted:
        # cleared on leave (`clear_transient`) and kept in step with the marks.
        self._config_on: set[str] = set()
        self._version_refresh = version_refresh
        self._tools = list(tools)
        # The catalog does not change in a session, so this is computed once.
        self._required_by = reverse_dependencies(self._tools)
        # The last entry built from a KNOWN state: a row whose state is unknown
        # again (a removal in flight) keeps its section and selectability.
        self._painted: dict[str, _UninstallEntry] = {}
        self._ban_names_of = inputs.ban_names
        self._has_path_block_of = inputs.has_path_block
        self._tweak_ids_of = inputs.tweak_ids
        self._retired_of = inputs.retired
        # Evaluated THROUGH run_live (.claude/architecture.md rule 3), not
        # bare: construction happens outside the nav path `enter_view` guards,
        # so a bare call would let an OSError from the filesystem reads escape
        # before any screen or status line exists to report it. On failure the
        # screen still constructs with no environment rows and the message
        # stashed on `self._startup_error`; the first `enter_view` surfaces it
        # as a one-time warn and re-reads, so the screen self-heals.
        env, env_error = run_live(self._env_state)
        empty_env: _EnvState = ([], False, (), (), ())
        (
            self._ban_names,
            self._has_path_block,
            self._tweak_ids,
            self._settings_files,
            self._retired,
        ) = env if env is not None else empty_env
        self._startup_error: str | None = env_error
        self._remove = inputs.remove
        self._terminal_sync = inputs.terminal_sync
        self.applied = False
        self.error: str | None = None
        # tool id -> its last `remove_failed` outcome; kept across navigation and
        # publishes, dropped when a removal naming the tool starts or its state
        # shows nothing left (see `_with_failure`).
        self._failed_lines: dict[str, RowOutcome] = {}
        # True until a published state has been painted: the rows before it are
        # placeholders, so the cursor is not kept on one of them.
        self._placeholders = True
        self._entries = self._build_entries()
        self._by_key = {entry.key: entry for entry in self._entries}
        self._browser: ToolBrowser[_UninstallEntry] = ToolBrowser(self._adapter())

    # -- entry construction ------------------------------------------------
    def _build_entries(self) -> list[_UninstallEntry]:
        entries = [self._with_failure(self._tool_entry(tool), tool) for tool in self._tools]
        # Built from the pairs the last re-read stored, so painting never reads the filesystem.
        entries.extend(self._retired_entry(tool, plan) for tool, plan in self._retired)
        if self._ban_names:
            entries.append(self._ban_entry())
        if self._has_path_block:
            entries.append(self._block_entry())
        if self._tweak_ids:
            entries.append(self._tweak_entry())
        if self._settings_files:
            entries.append(self._settings_entry())
        return entries

    def _state_of(self, tool: Tool) -> ToolState | None:
        return self._version_refresh.state_of(tool.id) if self._version_refresh else None

    def _tool_entry(self, tool: Tool) -> _UninstallEntry:
        """One tool row, drawn from its published state alone (D-07)."""
        state = self._state_of(tool)
        group = uninstall_group(state)
        if state is None or group is None:
            return self._unknown_entry(tool, state)
        selectable = group is UninstallState.REMOVABLE
        style = "" if selectable else "dim"
        paths = state.removable.removable if selectable else ()
        argv = state.removable.argv if selectable else ()
        unregister = state.removable.unregister if selectable else ()
        shown = ([shlex.join(argv)] if argv else []) + [str(path) for path in paths]
        flagged = selectable and tool.id in self._config_on
        removes = Text(("config + " if flagged else "") + (", ".join(shown) or "—"), style=style)
        removes.truncate(_REMOVES_CELL_MAX, overflow="ellipsis")
        config = self._config_clause(tool, state, flagged) if selectable else ""
        entry = _UninstallEntry(
            key=tool.id,
            cells=[
                mark(False) if selectable else Text(""),
                Text(tool.id, style="bold" if selectable else "dim"),
                health_cell(state),
                Text(tool.category, style=style),
                Text(uninstall_label(state), style=style),
                removes,
            ],
            selectable=selectable,
            detail=sanitize_log_line(
                uninstall_detail(tool, state, self._required_by.get(tool.id, ()), config=config)
            ),
            paths=tuple(paths),
            is_ban=False,
            is_path_block=False,
            tool=tool,
            group=group,
            argv=argv,
            unregister=unregister,
        )
        self._painted[tool.id] = entry
        return entry

    def _config_clause(self, tool: Tool, state: ToolState, flagged: bool) -> str:
        """The detail clause for a removable row's declared config (UI-SPEC, How a row shows it)."""
        if not tool.config_paths:
            return ""
        existing = [entry for entry, path in config_targets(tool) if path in state.removable.config]
        where = ", ".join(existing) or "none on disk"
        if flagged:
            return f"config deleted too: {where} (c keeps it)"
        return f"config kept: {where} (c deletes it too)"

    def _mark_cell(self, item_id: str, selected: bool) -> Text:
        """The sel cell: `[c]` on a marked row whose config flag is on (UI-SPEC A2)."""
        if selected and item_id in self._config_on:
            return Text("[c]", style="bold red")
        return mark(selected)

    def _with_failure(self, entry: _UninstallEntry, tool: Tool) -> _UninstallEntry:
        """The row of a tool whose last removal failed: the failed word and the
        reason ahead of what the state says. A tool whose state shows nothing left
        to retry or explain (gone, no `removable`, no `yourself`) drops its line."""
        outcome = self._failed_lines.get(tool.id)
        if outcome is None:
            return entry
        state = self._state_of(tool)
        gone = state is not None and uninstall_group(state) is UninstallState.ABSENT
        if (
            gone
            and state is not None
            and not (state.removable.removable or state.removable.yourself)
        ):
            del self._failed_lines[tool.id]
            return entry
        word, style = outcome_word(outcome)
        detail = f"{word} — {outcome_detail_text(outcome)}"
        if not gone:
            detail += f" · {entry.detail}"
        elif state is not None and state.removable.yourself:
            detail += (
                f" · remove it yourself: {', '.join(str(p) for p in state.removable.yourself)}"
            )
        cells = [*entry.cells]
        cells[5] = Text(word, style=style)
        return replace(entry, cells=cells, detail=sanitize_log_line(detail))

    def _unknown_entry(self, tool: Tool, state: ToolState | None) -> _UninstallEntry:
        """A tool whose state is not known yet: what it was last painted with,
        its Health cell set to `…`; a row never painted before is an unselectable
        `nothing to do` row (T-21-18)."""
        painted = self._painted.get(tool.id)
        if painted is not None:
            cells = [*painted.cells]
            cells[2] = health_cell(state)
            return replace(painted, cells=cells)
        return _UninstallEntry(
            key=tool.id,
            cells=[
                Text(""),
                Text(tool.id, style="dim"),
                health_cell(state),
                Text(tool.category, style="dim"),
                Text("—", style="dim"),
                Text("—", style="dim"),
            ],
            selectable=False,
            detail=uninstall_detail(tool, state),
            paths=(),
            is_ban=False,
            is_path_block=False,
            tool=tool,
            group=UninstallState.ABSENT,
        )

    def _ban_entry(self) -> _UninstallEntry:
        return _UninstallEntry(
            key=_BAN_KEY,
            cells=[
                mark(False),
                Text("pip/npm ban", style="bold yellow"),
                Text(""),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text(f"shims + aliases ({', '.join(self._ban_names)})", style="dim"),
            ],
            selectable=True,
            detail=f"pip/npm ban — shims + interactive aliases ({', '.join(self._ban_names)})",
            paths=(),
            is_ban=True,
            is_path_block=False,
        )

    def _block_entry(self) -> _UninstallEntry:
        return _UninstallEntry(
            key=_BLOCK_KEY,
            cells=[
                mark(False),
                Text("PATH wiring", style="bold yellow"),
                Text(""),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text("managed block in ~/.myshellrc", style="dim"),
            ],
            selectable=True,
            detail="PATH wiring — the managed block in ~/.myshellrc",
            paths=(),
            is_ban=False,
            is_path_block=True,
        )

    def _tweak_entry(self) -> _UninstallEntry:
        # Byte-identical to today when no daemon: id is among the offered ids
        # (Linux, or the daemon never enabled) -- the label/detail only name
        # the background job when one is actually present.
        has_daemon = _has_daemon_id(self._tweak_ids)
        linux_daemon = any(policy_id == "daemon:prune-tmp-linux" for policy_id in self._tweak_ids)
        has_redirect = any(policy_id.startswith("cache-redirect:") for policy_id in self._tweak_ids)
        label = "shell tweaks + background jobs" if has_daemon else "shell tweaks"
        detail = (
            "Disables every enabled shell tweak — the ~/.myshellrc blocks, "
            "the managed helper executables, and the Oh-My-Zsh plugin names "
            "this installer added to .zshrc (never ones you added yourself)"
        )
        if linux_daemon:
            detail += (
                " — and unregisters the systemd user timer (its unit files and wrapper executable)"
            )
        elif has_daemon:
            detail += (
                " — and unregisters the background maintenance LaunchAgent"
                " (its plist and wrapper executable)"
            )
        if has_redirect:
            detail += "; the environment cache redirect is removed too"
        return _UninstallEntry(
            key=_TWEAK_KEY,
            cells=[
                mark(False),
                Text(label, style="bold yellow"),
                Text(""),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text(f"blocks + helpers ({', '.join(self._tweak_ids)})", style="dim"),
            ],
            selectable=True,
            detail=detail,
            paths=(),
            is_ban=False,
            is_path_block=False,
            is_tweaks=True,
        )

    def _settings_entry(self) -> _UninstallEntry:
        """The agent and editor settings row (UI-SPEC section 6, O5): one revert for every key
        the ledgers record, which never touches a key the user changed since."""
        files = ", ".join(display_path(path) for path in self._settings_files)
        return _UninstallEntry(
            key=_SETTINGS_KEY,
            cells=[
                mark(False),
                Text("agent/editor settings", style="bold yellow"),
                Text(""),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text(
                    f"keys this installer wrote in {len(self._settings_files)} file(s)", style="dim"
                ),
            ],
            selectable=True,
            detail=f"reverts only keys that still hold this installer's value: {files}",
            paths=(),
            is_ban=False,
            is_path_block=False,
            is_settings=True,
        )

    def _retired_entry(self, tool: Tool, plan: RemovalPlan) -> _UninstallEntry:
        """A retired receipt's row (D-09, UI-SPEC section 2): removal only, no install or update."""
        selectable = plan.level != "none"
        shown = ", ".join(str(path) for path in plan.removable) or "—"
        removes = Text(sanitize_log_line(shown))
        removes.truncate(_REMOVES_CELL_MAX, overflow="ellipsis")
        name = Text(sanitize_log_line(tool.id), style="bold")
        name.append(" (retired)", style="dim")
        return _UninstallEntry(
            key=tool.id,
            cells=[
                mark(False) if selectable else Text(""),
                name,
                Text(""),
                Text("retired", style="dim"),
                Text(""),
                removes,
            ],
            selectable=selectable,
            detail=sanitize_log_line(_retired_detail(tool.id, plan)),
            paths=plan.removable,
            is_ban=False,
            is_path_block=False,
            tool=tool,
            argv=plan.argv,
            unregister=plan.unregister,
            is_retired=True,
            retired_plan=plan,
        )

    # -- browser adapter ---------------------------------------------------
    def _adapter(self) -> BrowserAdapter[_UninstallEntry]:
        return BrowserAdapter(
            items=self._entries,
            columns=(
                ("Sel", "sel"),
                ("Tool", "tool"),
                ("Health", "health"),
                ("Cat", "cat"),
                ("Installed via", "via"),
                ("What gets removed", "removes"),
            ),
            item_id=lambda entry: entry.key,
            row_cells=lambda entry: entry.cells,
            detail_text=lambda entry: entry.detail,
            groups=self._groups,
            views=(("all", "All"),),
            detail_is_markup=False,
            selectable=lambda entry: entry.selectable,
            mark_cell=self._mark_cell,
        )

    def _groups(self, _view: str) -> list[Section[_UninstallEntry]]:
        by_title: dict[str, list[_UninstallEntry]] = {}
        for state, title in _STATE_TITLES:
            by_title.setdefault(title, []).extend(
                entry for entry in self._entries if entry.group is state
            )
        sections: list[Section[_UninstallEntry]] = [
            (title, title, members) for title, members in by_title.items() if members
        ]
        retired = sorted(
            (entry for entry in self._entries if entry.is_retired), key=lambda entry: entry.key
        )
        if retired:
            title = "retired — no longer in the catalog"
            sections.append((title, title, retired))
        env = [
            entry
            for entry in self._entries
            if entry.is_ban or entry.is_path_block or entry.is_tweaks or entry.is_settings
        ]
        if env:
            sections.append(("environment", "shell config the installer manages", env))
        return sections

    def compose_body(self) -> ComposeResult:
        yield self._browser

    def _repaint(self) -> None:
        """Rebuild the entries from the stored values and repaint the browser."""
        # A flag follows its mark (UI-SPEC A1): every repaint drops the flags of unmarked rows.
        self._config_on.intersection_update(self._browser.selected)
        self._entries = self._build_entries()
        self._by_key = {entry.key: entry for entry in self._entries}
        self._browser.reload(self._adapter(), keep_cursor=not self._placeholders)
        if any(uninstall_group(self._state_of(tool)) is not None for tool in self._tools):
            self._placeholders = False

    def _env_state(self) -> _EnvState:
        """The environment predicates another view can change while this one is
        suspended, as one tuple.

        Every one of them touches the FILESYSTEM and can therefore raise
        (CR-01, 15.4-REVIEW.md): `has_path_block` -> `shellrc.has_managed_block`
        -> `Path.read_text()`; `tweak_ids` -> `active_tweak_ids` -> the rc files
        and the managed bin dir; `ban_names` -> `guard_state`, which probes that
        same bin dir; the settings files -> the ledgers. That is why this tuple is its own seam:
        every caller evaluates it through `run_live`, so a failure degrades to the last known
        values plus a warn rather than escaping the nav path.
        """
        settings_files = tuple(
            path
            for agent in receipts.CONFIG_AGENTS
            for path, _keys in ledger_summary(agent, home=Path.home())
        )
        managed = (
            self._version_refresh.managed_bin_dir
            if self._version_refresh is not None
            else bin_dir(None)
        )
        # D-09: the retired receipts re-listed live, each with the plan its row will show.
        retired = tuple((tool, removal_plan(tool, managed)) for tool in self._retired_of())
        return (
            self._ban_names_of(),
            self._has_path_block_of(),
            self._tweak_ids_of(),
            settings_files,
            retired,
        )

    def _reread_env(self) -> str | None:
        """Re-read the environment predicates and the retired receipts; the error text when that
        failed (the last values are kept). A publish can follow a mutation that changed
        them while this view is the visible one (D-06), so both `enter_view` and
        `state_refreshed` call it."""
        env, error = run_live(self._env_state)
        if env is not None:
            (
                self._ban_names,
                self._has_path_block,
                self._tweak_ids,
                self._settings_files,
                self._retired,
            ) = env
        return error

    def enter_view(self) -> None:
        """Re-read the environment and repaint each time this view is opened.

        A nav entry is D-06's trigger for a same-session removal summary to stop
        being claimed once it no longer describes the screen, so `applied` is
        cleared. Over an empty line only: a warning flushed by show_view or
        written here must not be replaced by the standing text.
        """
        error = self._reread_env()
        stashed, self._startup_error = self._startup_error, None
        self.applied = False
        self._repaint()
        if error is not None:
            self.status.set(f"Could not read the uninstall state: {error}.", "warn")
        elif stashed is not None:
            self.status.set(f"Could not read the uninstall state at startup: {stashed}.", "warn")
        if not self.status.text:
            self._show_standing_status()

    def state_refreshed(self) -> None:
        """A publish landed while this view may be open (D-06): re-read the
        environment, repaint every row, and never clear or replace a status
        someone else wrote. `applied` stays, so a removal summary stands."""
        error = self._reread_env()
        self._repaint()
        if error is not None and not self.status.text:
            self.status.set(f"Could not read the uninstall state: {error}.", "warn")
        if self.is_mounted:
            self._show_standing_status()

    def clear_transient(self) -> None:
        """Leaving the view forgets every config flag: a destructive choice is never remembered."""
        super().clear_transient()
        self._config_on.clear()

    def _nothing_to_uninstall(self) -> bool:
        """True only when every tool's state is known and none is removable or
        managed, and there is no environment row (RESEARCH P7)."""
        known = all(uninstall_group(self._state_of(tool)) is not None for tool in self._tools)
        idle = all(
            entry.group in (UninstallState.ABSENT, UninstallState.UNAVAILABLE)
            for entry in self._entries
        )
        return known and idle

    def _show_standing_status(self) -> None:
        """Write the standing copy into an empty line while it is true, and
        retract it only while the line still holds exactly that copy."""
        if self._nothing_to_uninstall():
            if not self.status.text:
                self.status.set(_NOTHING_TO_UNINSTALL, "ok")
        else:
            self.status.retract(_NOTHING_TO_UNINSTALL)

    # -- public seams the tests assert on ----------------------------------
    @property
    def selected(self) -> set[str]:
        """Selected *tool* ids (the env pseudo-rows are reported separately)."""
        return {key for key in self._browser.selected if key not in _ENV_KEYS}

    @property
    def remove_ban(self) -> bool:
        return _BAN_KEY in self._browser.selected

    @property
    def remove_path_block(self) -> bool:
        return _BLOCK_KEY in self._browser.selected

    @property
    def remove_tweaks(self) -> bool:
        return _TWEAK_KEY in self._browser.selected

    @property
    def remove_settings(self) -> bool:
        return _SETTINGS_KEY in self._browser.selected

    @property
    def detail_text(self) -> str:
        return self._browser.detail_text

    # -- messages from the browser -----------------------------------------
    def on_tool_browser_selection_changed(self, event: ToolBrowser.SelectionChanged) -> None:
        event.stop()
        # A mark is for the next removal; the running one keeps its status (D-05).
        if self.app.mutation_holder is not MutationHolder.REMOVAL:
            self.status.clear()
        # An unmarked row loses its flag, so its detail and cells must be repainted.
        if self._config_on - self._browser.selected:
            self._repaint()

    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        event.stop()
        if not any(entry.selectable for entry in self._entries):
            return
        if not event.ids:
            self.status.set("Select at least one item to remove.", "warn")
            return
        # Refuse before the modal; _apply_removal checks again, because a
        # mutation can start while the modal is open.
        if self.app.refuse_if_mutating(self):
            return
        # Built now, before the modal opens, so a publish during the confirm cannot
        # change what the user confirmed (review R1-20).
        decision, kept, flagged = self._decision(event.ids)
        self.app.push_screen(
            ConfirmUninstall(
                self._accept_summary(event.ids), self._review(decision, kept, flagged)
            ),
            self._on_confirm(decision),
        )

    def _review(
        self,
        decision: UninstallDecision,
        kept: Mapping[str, tuple[str, ...]],
        flagged: frozenset[str],
    ) -> tuple[Text, ...]:
        """Blocks 3-7 of the review (UI-SPEC, ConfirmUninstall), built from the one snapshot
        `_decision` took: the decision, the `config_split` kept map and the flagged ids. Nothing
        is recomputed after the confirm (review R1-20). Every id, command and path is data:
        it goes through `sanitize_log_line` and is appended as plain `Text`, never markup."""
        lines: list[Text] = []
        for tool in decision.tools:
            # A hook tool's undo runs first, so its line comes before its own command (A24).
            for undo in decision.unregister.get(tool.id, ()):
                lines.append(_review_line(sanitize_log_line(unregister_runs_line(tool.id, undo))))
            if argv := decision.argv.get(tool.id):
                lines.append(_review_line(sanitize_log_line(removal_runs_line(tool.id, argv))))
            # A retired row's facts take the same place as its runs line, in the `<id>: ...` shape.
            entry = self._by_key.get(tool.id)
            if entry is not None and entry.retired_plan is not None:
                for line in _retired_review_lines(tool.id, entry.retired_plan):
                    lines.append(_review_line(sanitize_log_line(line)))
        # Block 3b, what changes (UI-SPEC section 6): the same lines the CLI previews.
        changes = removal_change_lines(decision.tools, active_tweaks=self._tweak_ids)
        if decision.revert_settings:
            changes += settings_change_lines(receipts.CONFIG_AGENTS)
        lines.extend(_review_line(sanitize_log_line(line)) for line in dict.fromkeys(changes))
        deleted = [
            _review_line(sanitize_log_line(f"  {entry} ({tool.id})"))
            for tool in decision.tools
            for entry, path in config_targets(tool)
            if path in decision.config.get(tool.id, ())
        ]
        shared = [
            _review_line(sanitize_log_line(f"  {entry} kept, also used by {', '.join(ids)}"), "dim")
            for entry, ids in kept.items()
        ]
        if deleted or shared:
            lines.append(_review_line("Config deleted too:", "bold red"))
            lines.extend(deleted)
            lines.extend(shared)
        unflagged = [
            tool.id for tool in decision.tools if tool.config_paths and tool.id not in flagged
        ]
        if unflagged:
            lines.append(_review_line(sanitize_log_line(f"Config kept: {', '.join(unflagged)}.")))
        # The frozen decision's argv, like the `runs` lines above (review C-13).
        packages = pnpm_removal_packages(decision.argv.values())

        def present(tool: Tool) -> bool:  # an unknown state counts as present (22-UAT F-3)
            return uninstall_group(self._state_of(tool)) is not UninstallState.ABSENT

        for warning in co_install_warnings(packages, self._tools, present=present):
            line = _review_line(sanitize_log_line(warning))
            line.stylize("yellow", 0, len("Warning:"))
            lines.append(line)
        return tuple(lines)

    def _highlighted_entry(self) -> _UninstallEntry | None:
        key = self._browser.highlighted_id()
        return None if key is None else self._by_key.get(key)

    def action_toggle_config(self) -> None:
        """`c`: flag a removable row's config on (marking it too) or off (D-11, UI-SPEC A1).

        A flag is not a mutation, so the lock never refuses it.
        """
        entry = self._highlighted_entry()
        if entry is None or entry.tool is None or entry.is_retired:
            self._config_refused("This row has no config to delete.")
        elif entry.group is not UninstallState.REMOVABLE:
            self._config_refused(f"{entry.key} cannot be removed here, so its config stays.")
        elif not entry.tool.config_paths:
            self._config_refused(f"{entry.key} declares no config to delete.")
        else:
            if entry.key in self._config_on:
                self._config_on.discard(entry.key)
            else:
                if entry.key not in self._browser.selected:
                    self._browser.action_toggle_selected()
                self._config_on.add(entry.key)
            self._repaint()  # the row's cells and detail bar name the flag

    def _config_refused(self, text: str) -> None:
        """A refusal is a warn line, but it never replaces `Removing…` (D-05): during a removal
        it shows in the detail bar instead, so the key never looks broken (review C-15)."""
        if self.app.mutation_holder is not MutationHolder.REMOVAL:
            self.status.set(text, "warn")
        else:
            self._browser.show_detail(text)

    def _accept_summary(self, ids: list[str]) -> str:
        tool_count = sum(1 for key in ids if key not in _ENV_KEYS)
        parts: list[str] = []
        if tool_count:
            parts.append(f"{tool_count} tool(s)")
        if _BAN_KEY in ids:
            parts.append("the pip/npm ban")
        if _BLOCK_KEY in ids:
            parts.append("the PATH wiring")
        if _TWEAK_KEY in ids:
            parts.append("the shell tweaks")
        if _SETTINGS_KEY in ids:
            parts.append("the agent/editor settings")
        return ", ".join(parts)

    def _decision(
        self, ids: list[str]
    ) -> tuple[UninstallDecision, Mapping[str, tuple[str, ...]], frozenset[str]]:
        """The removal the selected ids name, with the config the flags agreed to delete.

        Also returns the config `config_split` kept and the flagged ids, from the same
        `config_split` call, so the review and the decision cannot disagree."""
        tools: dict[str, Tool] = {}  # by id, in selection order; env rows carry no tool
        for key in ids:
            entry = self._by_key[key]
            if entry.tool is not None:
                tools.setdefault(entry.tool.id, entry.tool)
        flagged = [tool for tool in tools.values() if tool.id in self._config_on]
        deleted, kept = config_split(flagged, self._tools, self._state_of)
        decision = UninstallDecision(
            tools=tuple(tools.values()),
            paths={tool_id: self._by_key[tool_id].paths for tool_id in tools},
            argv={tool_id: self._by_key[tool_id].argv for tool_id in tools},
            unregister={tool_id: self._by_key[tool_id].unregister for tool_id in tools},
            remove_ban=self.remove_ban,
            remove_path_block=self.remove_path_block,
            remove_tweaks=self.remove_tweaks,
            revert_settings=self.remove_settings,
            config=deleted,
        )
        return decision, kept, frozenset(tool.id for tool in flagged)

    def _on_confirm(self, decision: UninstallDecision) -> Callable[[bool | None], None]:
        # Callable[[bool | None], None] is the correct pyright-strict type:
        # ScreenResultCallbackType (textual/screen.py:83) passes Optional[ScreenResultType]
        # to the callback, i.e. bool | None for ModalScreen[bool].
        def run(confirmed: bool | None) -> None:
            if confirmed:
                self._apply_removal(decision)

        return run

    def _apply_removal(self, decision: UninstallDecision) -> None:
        if self.app.refuse_if_mutating(self, cross_process=True):
            return
        if not self.app.begin_mutation(MutationHolder.REMOVAL, screen=self):
            return
        for tool in decision.tools:
            self._failed_lines.pop(tool.id, None)
        if self._version_refresh is not None and decision.tools:
            self._version_refresh.mark_pending([tool.id for tool in decision.tools])
        self._repaint()
        self.status.set("Removing…", "warn")
        self._remove_worker(decision)

    def _config_lines(self, decision: UninstallDecision, swept: SweepResult) -> list[str]:
        """UI-SPEC Removal results: what became of each tool's config, in the order deleted,
        kept, not deleted. Kept means a removed tool whose declared config is still on disk and
        was not flagged. The check reads the disk now: the cache invalidation that follows a
        removal leaves no published state to read it from (its epoch moved on)."""
        kept = [
            tool.id
            for tool in decision.tools
            if tool.id in swept.removed
            and tool.id not in decision.config
            and any(path.is_symlink() or path.exists() for _, path in config_targets(tool))
        ]
        lines: list[str] = []
        if swept.config_deleted:
            lines.append(f"Config deleted for {', '.join(swept.config_deleted)}.")
        if kept:
            lines.append(f"Config kept for {', '.join(kept)}.")
        if swept.config_not_deleted:
            lines.append(
                f"Config not deleted for {', '.join(swept.config_not_deleted)}: the removal failed."
            )
        return [sanitize_log_line(line) for line in lines]

    def _applied_summary(self, decision: UninstallDecision, swept: SweepResult) -> str:
        parts: list[str] = []
        if decision.remove_ban:
            parts.append(
                "pip/npm ban removed — open a new shell or run `hash -r` so cached"
                " command paths refresh."
            )
        if decision.remove_path_block:
            parts.append("PATH wiring removed — restart your shell to drop the managed dirs.")
        if decision.remove_tweaks:
            # From the sweep's own result, never from the row's snapshot: the
            # snapshot describes what was offered, not what came off.
            if swept.swept:
                # Byte-identical to today when no daemon: id is among what was
                # actually swept. When one is present, name it explicitly and
                # append the shell-reload hint only if a real, non-daemon
                # tweak was ALSO swept -- a LaunchAgent needs no shell reload
                # at all (11-REVIEWS.md cycle 2 finding #19).
                has_daemon = _has_daemon_id(swept.swept)
                linux_daemon = "daemon:prune-tmp-linux" in swept.swept
                has_redirect = any(sid.startswith("cache-redirect:") for sid in swept.swept)
                has_other = any(not sid.startswith("daemon:") for sid in swept.swept)
                prefix = (
                    "shell tweaks and the background maintenance job"
                    if has_daemon
                    else "shell tweaks"
                )
                if linux_daemon and has_redirect:
                    reload_hint = " — log out and back in so the environment redirect is dropped."
                elif not has_daemon or has_other:
                    reload_hint = " — open a new shell so functions and aliases refresh."
                else:
                    reload_hint = "."
                parts.append(f"{prefix} disabled ({', '.join(swept.swept)}){reload_hint}")
            if swept.failed:
                parts.append(
                    f"could not disable {', '.join(swept.failed)} — check permissions and re-run."
                )
            if not swept.swept and not swept.failed:
                parts.append("no shell tweaks were still enabled — nothing to disable.")
        # Refused paths travel here too, so they show whatever levers were chosen.
        parts.extend(f"warning: {sanitize_log_line(warning)}." for warning in swept.warnings)
        # One line per outcome: a single joined line overflows the terminal width and
        # truncates the reload guidance, so the "needs a new shell" steps go unseen.
        return multiline_summary(parts)

    # exit_on_error=False: a crash must leave a usable app; RemovalFinished is
    # posted from `finally`, so the lock cannot stay held on any outcome. The
    # delete runs on a daemon thread this worker awaits: a forced quit (a second
    # ctrl+c, D-10) drops the wait, and the process exits without joining it.
    @work(exclusive=True, group="uninstall-removal", exit_on_error=False)
    async def _remove_worker(self, decision: UninstallDecision) -> None:
        loop = asyncio.get_running_loop()
        done: asyncio.Future[None] = loop.create_future()

        def finish() -> None:
            if not done.done():
                done.set_result(None)

        def run() -> None:
            try:
                self._run_removal(decision)
            finally:
                with contextlib.suppress(RuntimeError):  # the loop closed: a forced quit
                    loop.call_soon_threadsafe(finish)

        threading.Thread(target=run, name="uninstall-removal", daemon=True).start()
        await done

    def _run_removal(self, decision: UninstallDecision) -> None:
        swept: SweepResult | None = None
        error: str | None = "removal did not complete"
        invalidate_error: str | None = None
        try:
            try:
                swept, error = run_live(lambda: self._remove(decision))
            except Exception as exc:
                error = first_line(exc)
            # Also after a crash: only `invalidate` clears the pending ids (D-09).
            service = self._version_refresh
            if service is not None and decision.tools:
                _, cache_error = run_live(
                    lambda: service.invalidate(reason="uninstall run finished")
                )
                if cache_error is not None:
                    invalidate_error = f"version cache invalidation failed: {cache_error}"
        finally:
            self.post_message(RemovalFinished(decision, swept, error, invalidate_error))

    def on_removal_finished(self, message: RemovalFinished) -> None:
        self.app.end_mutation()
        if not self.app.is_running:  # the app is shutting down: nothing to render
            return
        swept = message.swept
        self.error = message.error
        if swept is None:
            self.app.show_result(
                self,
                f"Uninstall failed: {self.error}. Check permissions, then press enter.",
                "error",
                elsewhere=(
                    f"Uninstall failed: {self.error}."
                    " Check permissions, then open Uninstall and press enter."
                ),
            )
            self._request_pass()
            return
        self.applied = True
        # A receipt-only retirement (no path, no command) reports its own sentence, not a count.
        receipt_only = {
            tool.id
            for tool in message.decision.tools
            if tool.retired
            and not message.decision.paths.get(tool.id)
            and not message.decision.argv.get(tool.id)
        }
        outcomes = [
            RowOutcome(PlanRow(tool_id, Disposition.REMOVE, ""), "done")
            for tool_id in swept.removed
            if tool_id not in receipt_only
        ] + [
            RowOutcome(PlanRow(tool_id, Disposition.REMOVE, ""), "remove_failed", detail=line)
            for tool_id, line in swept.remove_failed
        ]
        for tool_id, line in swept.remove_failed:
            self._failed_lines[tool_id] = RowOutcome(
                PlanRow(tool_id, Disposition.REMOVE, ""), "remove_failed", detail=line
            )
        self._browser.selected -= set(swept.removed)
        self.app.unstage(swept.removed)
        self._repaint()
        summary_parts = [summary_counts(outcomes)] if outcomes else []
        summary_parts.extend(sanitize_log_line(line) for line in swept.with_group)
        summary_parts.extend(sanitize_log_line(line) for line in swept.receipt_retired)
        failed = len(swept.remove_failed)
        fix_here = f"{failed} remove failed. Fix the cause and press enter to try again."
        if failed:
            summary_parts.append(fix_here)
        summary_parts.extend(self._config_lines(message.decision, swept))
        if labels := host_labels(swept.unregistered):
            summary_parts.append(f"Unregistered from agent hosts: {labels}.")
        summary_parts.extend(removal_result_lines(swept))
        # Empty when no lever was chosen; a blank line would cost a status row.
        if applied := self._applied_summary(message.decision, swept):
            summary_parts.append(applied)
        if message.invalidate_error is not None:
            summary_parts.append(message.invalidate_error)
        # D-01/15.6-06 Task 3: called unconditionally on every successful
        # sweep (never gated on tools -- a terminal reapply/reversion is
        # warranted even when only an env lever came off, since
        # sync_terminal_shells' own no-zsh branch is exactly what a
        # zsh-removing sweep needs). WR-03/WR-04: the one shared failure
        # contract (terminal_sync_warning); a failure renders "warn", never
        # the "ok" success color, and never flips `applied`.
        terminal_warning = terminal_sync_warning(self._terminal_sync)
        if terminal_warning:
            summary_parts.append(terminal_warning)
        if swept.remove_failed or swept.config_not_deleted:
            severity = "error"
        elif terminal_warning or swept.warnings:  # a config delete warning is a warn too
            severity = "warn"
        else:
            severity = "ok"
        summary = multiline_summary(summary_parts)
        fix_elsewhere = (
            f"{failed} remove failed. Fix the cause, then open Uninstall and press enter"
            " to try again."
        )
        self.app.show_result(
            self,
            summary,
            severity,
            elsewhere=summary.replace(fix_here, fix_elsewhere) if failed else None,
        )
        self._request_pass()

    def _request_pass(self) -> None:
        """D-05: every removal, environment-only ones included, ends with one app
        pass; the publish re-renders this view. A quit in progress exits instead."""
        if not self.app.quitting:
            self.app.request_refresh()


_LINGER_SENTENCE = (
    "The timer runs while you are logged in. For always-on operation, run"
    " `loginctl enable-linger $USER` yourself; this installer does not run that"
    " command for you, because it is a system-wide setting for the whole account."
)


def _competing_line(competing: CompetingProbe | None) -> str | None:
    """WR-10: name a system-scope competitor on the background-cleanup row.

    Peek only -- this runs on every row highlight -- so it says nothing
    until the screen's own warm-up worker has landed an answer. Only
    system-scope units appear: a user-scope one is taken over by the
    apply, so repeating it here would describe a stopped mechanism.
    """
    if competing is None:
        return None
    try:
        units = competing(blocking=False)
    except (OSError, ValueError, CommandError):
        return None
    names = sorted({unit.name for unit in units if unit.scope == SCOPE_SYSTEM})
    if not names:
        return None
    return (
        f"Also installed system-wide: {', '.join(names)} (root-owned; this installer "
        "cannot stop it without sudo)"
    )


def _temp_usage_line(disk_pressure: DiskPressureProbe | None) -> str | None:
    """The live temp-usage line for a background-cleanup row, or None.

    This runs on EVERY row-highlight, i.e. on every arrow key, so the two
    halves of the probe are handled differently on purpose:

    - The mount reads stay synchronous and un-cached. `shutil.disk_usage`
      is one statvfs on an already-mounted filesystem -- the same order of
      cost as the read_schedule/last_run_summary reads above, and it spawns
      no process, unlike the pnpm audit the Doctor runs on a worker. A
      worker here would buy nothing and cost a cross-thread hand-off plus a
      stale-value window on a number whose whole point is being current.
    - The daemon-state half is a `systemctl --user is-active` SUBPROCESS
      (plan 15.7-01's D-01c), so this path does not run it AT ALL:
      blocking=False makes the closure read TimerStateCache.peek(), which
      never probes. Memoization alone is not the answer, although "it's
      cached" reads like one: a memo still has a cold first read and a TTL
      expiry, and on those a read() blocks the Textual event loop for up to
      systemd_daemon.SYSTEMCTL_QUERY_TIMEOUT (5 s) -- bounded, but a frozen UI. Nor is "move it
      to a worker": the daemon state is not even shown on this line, so a
      worker would add async plumbing to fetch a value nothing renders.

    Failures follow plan 15.7-02's D-03b: probe_disk_pressure is TOTAL over
    filesystem and probe-conversion failure, and any other exception
    propagates uncaught. This guard is the documented second layer over the
    injected closure, the same pairing the adjacent reads use.

    Only a number the probe actually measured is stated: the temp-directory
    usage (measured on macOS too, per D-03d), else -- only when the temp
    mount was unreadable -- the free space on the filesystem holding the
    user's home directory, labelled as such, else no line at all.
    """
    if disk_pressure is None:
        return None
    try:
        pressure = disk_pressure(blocking=False)
    except (OSError, ValueError):
        return None
    if pressure.tmp_used_percent is not None:
        return f"Current temp-directory usage: {pressure.tmp_used_percent:.1f}%"
    if pressure.home_free_percent is not None:
        return f"Current home filesystem free space: {pressure.home_free_percent:.1f}%"
    return None


_POLICY_READ_ERROR = "Could not read the policy state: "


def _read_failure(error: str) -> str:
    """The status copy for a failed live read: the first line of the message."""
    return f"{_POLICY_READ_ERROR}{error.partition(chr(10))[0]}."


_DRIFT_DETAIL = (
    "Drift: this installer enabled it, but it is not active now. space applies it again."
)
_JOB_READ_INCOMPLETE = "the job state read did not complete"


def _read_active_owned(policy: Policy) -> tuple[tuple[bool, bool] | None, str | None]:
    """One policy's (active, owned) through run_live, or the failure text.

    `owned` is read only when the policy binds it; either read failing fails
    the pair, so a row is never half-painted from one answer.
    """
    if policy.is_active is None:
        return None, None
    active, error = run_live(policy.is_active)
    if active is None:
        return None, error
    owned = False
    if policy.owned is not None:
        read, error = run_live(policy.owned)
        if read is None:
            return None, error
        owned = read
    return (active, owned), None


class PoliciesScreen(AppScreen):
    """Toggle environment policies (the pip/npm ban) on/off, applied live.

    Each toggle is an immediate, idempotent, reversible mutation — there is no
    select-then-commit step. `space` toggles the highlighted policy (matching the
    "act on this row" meaning of `space` in the catalog/uninstall browsers);
    `enter` is inert here because there is no staged batch to commit.
    """

    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_policy", "toggle policy", show=True, priority=True),
        Binding("l", "toggle_log", "view log", show=True),
        Binding("t", "pick_time", "set time", show=True),
        Binding("m", "pick_link_mode", "link mode", show=True),
    ]
    DEFAULT_CSS = """
    PoliciesScreen DataTable { height: 1fr; }
    PoliciesScreen #link-mode-line {
        height: auto; padding: 0 1;
    }
    PoliciesScreen #policy-detail {
        height: 11; padding: 0 1; background: $surface; overflow-y: auto;
    }
    """

    def __init__(self, inputs: PolicyInputs) -> None:
        super().__init__(view="policies")
        self._policies = inputs.policies
        self._link_mode = inputs.link_mode
        self._set_link_mode = inputs.set_link_mode
        # The SAME closure UnifiedApp hands the Doctor: one field, two screens.
        self._disk_pressure = inputs.disk_pressure
        self._competing = inputs.competing
        self.active_state: dict[str, bool] = {
            policy.id: policy.active for policy in inputs.policies
        }
        # Policies whose last read said owned-but-not-active.
        self._drift: set[str] = set()
        # Settings rows whose keys all hold our values with no record: nothing to write.
        self._yours: set[str] = set()
        # Bumped by every render and mutation completion that supersedes a
        # job-state read in flight; JobStatesRead carries the one it began with.
        self._job_state_generation = 0
        # Each policy's prerequisites as last read; no entry means not (yet) readable.
        self._missing: dict[str, tuple[str, ...]] = {}
        self._read_error: str | None = None
        self.error: str | None = None
        self.detail_text = ""
        # True while the one-shot competing-mechanism warm-up worker runs.
        self.competing_probing = False
        # Explicit, not left to on_data_table_row_highlighted's own reset as the
        # sole assignment point: an AttributeError would otherwise be reachable
        # if action_toggle_log ever ran before any row-highlight event has fired
        # (11-REVIEWS.md cycle 2 finding #12).
        self._log_view: bool = False

    def compose_body(self) -> ComposeResult:
        yield Static("", id="link-mode-line")
        yield DataTable()
        yield Static("", id="policy-detail")

    def on_mount(self) -> None:
        table = self.query_one(DataTable[Any])
        table.cursor_type = "row"
        table.add_column("State", key="state")
        table.add_column("Policy", key="policy")
        table.add_column("Requires", key="requires")
        table.add_column("Effect", key="effect")
        for policy in self._policies:
            effect_kind = policy.effect_kind or (
                "scheduled job" if policy.log_path is not None else "shell config"
            )
            table.add_row(
                Text(""),
                Text(policy.label, style="bold yellow"),
                Text(""),
                Text(f"{effect_kind}: {policy.description}", style="dim"),
                key=policy.id,
            )
        table.focus()
        if self._competing is not None:
            self.competing_probing = True
            self._probe_competing_worker()

    @work(thread=True, exclusive=True, group="policies-competing", exit_on_error=False)
    def _probe_competing_worker(self) -> None:
        """Warm the competing-mechanism memo off the event loop (WR-02/WR-10),
        then ask for a repaint so the detail line appears."""
        try:
            probe = self._competing
            if probe is not None:
                with contextlib.suppress(OSError, ValueError, CommandError):
                    probe()
        finally:
            self.post_message(CompetingProbed())

    def on_competing_probed(self, _message: CompetingProbed) -> None:
        self.competing_probing = False
        if self.is_mounted:
            self._set_detail(self._highlighted_policy())

    def _refresh_link_mode_line(self) -> None:
        line = self.query_one("#link-mode-line", Static)
        if self._link_mode is None:
            line.update("")
            return
        line.update(f"PATH link mode: {self._link_mode()}  (press m to change)")

    def enter_view(self) -> None:
        """An entry blanks the job rows until their worker read answers: the
        last answer is from a previous visit. A publish keeps it (C-21)."""
        for policy in self._policies:
            if policy.state_cache is not None:
                self._record_state(policy.id, None)
        self.state_refreshed()

    def state_refreshed(self) -> None:
        """Render every row from a fresh read of the machine (D-04, D-12).

        `enter_view` calls this on every entry and the app calls it on every
        publish while Policies is on top. A job row keeps its last answer while
        the worker re-reads it.
        """
        if not self.is_mounted:
            return
        table = self.query_one(DataTable[Any])
        errors: list[str] = []
        for policy in self._policies:
            errors += filter(None, (self._read_live_state(policy), self._read_requirements(policy)))
            table.update_cell(policy.id, "state", self._state_cell(policy.id), update_width=True)
            table.update_cell(policy.id, "requires", self._requires_cell(policy), update_width=True)
        self._set_detail(self._highlighted_policy())
        self._refresh_link_mode_line()
        self._start_job_state_read()
        if errors:
            self._show_read_error(errors[0])
        elif self._read_error is not None:
            self.status.retract(self._read_error)
            self._read_error = None

    def _read_live_state(self, policy: Policy) -> str | None:
        """Re-read one policy's state; the error text when the read failed.

        A state_cache policy is read on a worker (21-18); one without
        is_active keeps the state its last toggle left. A failed read drops the
        remembered answer: the row is never painted from a previous read.
        """
        if policy.state is not None:
            state, error = run_live(policy.state)
            self._record_settings_state(policy.id, state)
            return error
        if policy.is_active is None or policy.state_cache is not None:
            return None
        read, error = _read_active_owned(policy)
        self._record_state(policy.id, read)
        return error

    def _record_settings_state(self, policy_id: str, state: str | None) -> None:
        """A settings row's read: on, yours, off or drift. None (unreadable) drops it."""
        self._yours.discard(policy_id)
        if state is None:
            self._record_state(policy_id, None)
            return
        self._record_state(policy_id, (state == "on", state == "drift"))
        if state == "yours":
            self._yours.add(policy_id)

    def _record_state(self, policy_id: str, read: tuple[bool, bool] | None) -> None:
        """Keep one policy's (active, owned) answer; None drops it (blank cell)."""
        if read is None:
            self.active_state.pop(policy_id, None)
            self._drift.discard(policy_id)
            return
        active, owned = read
        self.active_state[policy_id] = active
        if owned and not active:
            self._drift.add(policy_id)
        else:
            self._drift.discard(policy_id)

    def _start_job_state_read(self) -> None:
        """Supersede any job-state read in flight and start a fresh one."""
        self._job_state_generation += 1
        if any(policy.state_cache is not None for policy in self._policies):
            self._read_job_states_worker(self._job_state_generation)

    @work(thread=True, exclusive=True, group="policies-job-state", exit_on_error=False)
    def _read_job_states_worker(self, generation: int) -> None:
        """Read the systemd-backed rows off the event loop (WR-02)."""
        states: dict[str, tuple[bool, bool]] = {}
        error: str | None = _JOB_READ_INCOMPLETE
        try:
            errors: list[str] = []
            for policy in self._policies:
                if policy.state_cache is None:
                    continue
                read, failure = _read_active_owned(policy)
                if read is not None:
                    states[policy.id] = read
                if failure is not None:
                    errors.append(failure)
            error = errors[0] if errors else None
        finally:
            self.post_message(JobStatesRead(generation, states, error))

    def on_job_states_read(self, message: JobStatesRead) -> None:
        if message.generation != self._job_state_generation:
            return
        if not self.is_mounted or not self.app.is_running:
            return
        table = self.query_one(DataTable[Any])
        for policy in self._policies:
            if policy.state_cache is not None:
                self._record_state(policy.id, message.states.get(policy.id))
                table.update_cell(
                    policy.id, "state", self._state_cell(policy.id), update_width=True
                )
        self._set_detail(self._highlighted_policy())
        if message.error is not None:
            self._show_read_error(message.error)

    def _show_read_error(self, error: str) -> None:
        """Over an empty status or this screen's own earlier error only: another
        writer's result stands, the same rule as the app's state line (RR-03)."""
        previous, self._read_error = self._read_error, _read_failure(error)
        if not self.status.text or self.status.text == previous:
            self.status.set(self._read_error, "error")

    def _read_requirements(self, policy: Policy) -> str | None:
        missing, error = run_live(policy.missing_requirements)
        if missing is None:
            self._missing.pop(policy.id, None)
        else:
            self._missing[policy.id] = missing
        return error

    def _refuse_unreadable(self) -> None:
        """A row whose state or prerequisites could not be read is never acted
        on, never treated as OFF; the refusal still ends with one pass."""
        self.status.set(self._read_error or f"{_POLICY_READ_ERROR}not read yet.", "error")
        self.post_message(RefreshRequested())

    def _state_cell(self, policy_id: str) -> Text:
        # A ●/○ glyph carries the state independent of color: the lone row is
        # always focused, so the selection highlight flattens the green/dim cue.
        active = self.active_state.get(policy_id)
        if active is None:
            return Text("")
        if policy_id in self._yours:
            return Text("● [yours]", style="green")
        if policy_id in self._drift:
            return Text("! [drift]", style="yellow")
        label = "● [on]" if active else "○ [off]"
        return Text(label, style="green" if active else "dim")

    def _requires_cell(self, policy: Policy) -> Text:
        missing_requires = self._missing.get(policy.id)
        if missing_requires is None:
            return Text("")
        if missing_requires and policy.hard_requires:
            return Text("missing: " + ", ".join(missing_requires), style="bold yellow")
        if missing_requires:
            return Text("recommended: " + ", ".join(missing_requires), style="yellow")
        if policy.requires:
            return Text(", ".join(policy.requires), style="dim")
        return Text("none", style="dim")

    def _highlighted_policy(self) -> Policy | None:
        # highlighted_key is None on an empty table, matching no policy id.
        policy_id = highlighted_key(self.query_one(DataTable[Any]))
        return next((policy for policy in self._policies if policy.id == policy_id), None)

    def _policy_detail(self, policy: Policy) -> str:
        missing_requires = self._missing.get(policy.id)
        details = {
            "ban": (
                "Blocks bare pip and pip3, redirects npx to pnpm dlx, and routes"
                " npm/pnpm global installs to volta install.",
                "Wraps your pnpm binary with a PATH shim: only global adds are"
                " rerouted, every other pnpm command passes straight through.",
                "Global installs then run npm's install scripts unrestricted, which"
                " pnpm gates — keep untrusted packages on a project-local pnpm add.",
                "Writes PATH shims plus interactive aliases, then asks for a shell reload.",
                "Use when humans or agents keep reaching for unmanaged package installers.",
            ),
            "tweak:docker": (
                "Adds docker-ps, a watch-powered live table of names, status, and ports.",
                "Adds docker-stats and docker-memory for quick memory inspection.",
                "Install the catalog's watch tool first when your platform does not ship it.",
            ),
            "tweak:countdown": (
                "Adds wait_time for seconds, 1d10m15s, 23h 49m, 10am, tomorrow 10am,"
                " and compact dates.",
                "Use wait_time --seconds to preview the parsed delay without sleeping.",
                "Requires uv at runtime so the Python helper runs through the managed toolchain.",
            ),
            "tweak:apt-upgrade": (
                "Adds apt-upgrade for upgrading only packages that already have updates.",
                "Keeps the command narrower than a broad apt upgrade flow.",
                "Offered on Linux only; it is harmless until run on an apt-based distro.",
            ),
            "omz-plugins": (
                "Adds Oh-My-Zsh's bundled git and docker plugins to the"
                " plugins=(...) array in ~/.zshrc.",
                "Disabling removes only the names this enable actually added — a"
                " plugin you put in that array yourself is never touched.",
                "Needs Oh-My-Zsh installed; only the single-line plugins=(...) form is edited.",
                "Reads ON only once this installer has enabled it, so a"
                " plugins=(git docker) you wrote by hand shows OFF and is left alone.",
            ),
            "daemon:prune-tmpdir": (
                "Runs scripts/prune-user-tmpdir.sh once a day via a macOS LaunchAgent,"
                " deleting orphaned agent-runtime temp files.",
                "Degrades gracefully without fd/rg — the script falls back to its own"
                " find/grep search, just slower.",
                "Disabling only unregisters the LaunchAgent: it never touches your temp"
                " files directly, only through the unchanged script's own dry-run/apply"
                " modes while the LaunchAgent is registered.",
                "Press t to set the daily run time; press l to view the run log.",
            ),
            "daemon:prune-tmp-linux": (
                "Deletes orphaned Bun runtime-cache files from the OS temp dir, every ten minutes.",
                _LINGER_SENTENCE,
                "Disabling only unregisters the timer and its unit files: it never deletes"
                " temp files directly.",
                "The daily time picker does not apply to this row.",
            ),
            "cache-redirect:bun": (
                f"Sets {env_redirect.BUN_CACHE_REDIRECT.variable} so Bun's transpiler cache"
                " lands in ~/.cache/bun instead of the OS temp dir.",
                "On Linux this is an environment.d file the systemd user manager reads only"
                " when it starts, so the change takes effect at the next login, not in a"
                " new terminal tab.",
                "Disabling removes the redirect but never deletes the cache directory itself.",
                env_redirect.BUN_CACHE_REDIRECT.coverage_caveat,
            ),
        }
        if policy.detail_lines is not None:
            # A settings row's own lines replace the generic drift and label lines.
            lines = list(policy.detail_lines())
        else:
            lines = [_DRIFT_DETAIL] if policy.id in self._drift else []
            lines.append(f"{policy.label} — {policy.description}")
        if missing_requires and policy.hard_requires:
            lines.append(
                "Missing required tool(s): "
                f"{', '.join(missing_requires)}. Install from Catalog before enabling."
            )
        elif missing_requires:
            lines.append(
                "Recommended tool(s): "
                f"{', '.join(missing_requires)}. Not required — apply still runs and "
                "falls back automatically."
            )
        elif policy.requires and missing_requires is not None:
            lines.append(f"Required tool(s): {', '.join(policy.requires)}.")
        if policy.detail_lines is None:
            lines.extend(details.get(policy.id, ("Space toggles this reversible shell policy.",)))
        if policy.id.startswith("tweak:") and policy.detail_lines is None:
            lines.append(
                "This alias/function needs ~/.myshellrc to be sourced; in split PATH mode,"
                " enabling this Policy also wires that sourcing into your rc files"
                " automatically, so it still works after your next new shell."
            )
        # Both calls are already total/never-raising in installer/daemon.py itself
        # (11-01's own mechanism-tier fix); this is a SECOND, independent guard
        # directly around these two call sites, on the NORMAL render path (mount,
        # row-highlight), not only the `l` toggle's own read — belt-and-suspenders
        # against a future regression in that guarantee or an unanticipated
        # malformed-input shape (11-REVIEWS.md cycle 2 finding #10).
        if policy.log_path is not None:
            try:
                summary = daemon.last_run_summary(policy.log_path)
            except (OSError, ValueError, UnicodeDecodeError):
                summary = None
            if summary is not None:
                lines.append(summary)
        if policy.set_schedule is not None and policy.read_schedule is not None:
            try:
                schedule = policy.read_schedule()
            except (OSError, ValueError, UnicodeDecodeError):
                schedule = None
            if schedule is not None:
                hour, minute = schedule
                lines.append(f"scheduled daily at {hour:02d}:{minute:02d}")
        if _has_daemon_id((policy.id,)):
            usage = _temp_usage_line(self._disk_pressure)
            if usage is not None:
                lines.append(usage)
            competing = _competing_line(self._competing)
            if competing is not None:
                lines.append(competing)
        return "\n".join(lines)

    def _set_detail(self, policy: Policy | None) -> None:
        if policy is not None and self._log_view and policy.log_path is not None:
            self.detail_text = self._log_tail(policy.log_path)
        else:
            self.detail_text = "" if policy is None else self._policy_detail(policy)
        self.query_one("#policy-detail", Static).update(Text(self.detail_text))

    def _log_tail(self, log_path: Path, *, lines: int = _LOG_TAIL_LINES) -> str:
        try:
            text = log_path.read_text()
        except FileNotFoundError:
            return "log file does not exist yet"
        except (OSError, UnicodeDecodeError) as exc:
            return f"log could not be read: {exc}"
        return "\n".join(text.splitlines()[-lines:])

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Navigating away from a log-view row and back must always start from
        # the normal detail view, never a stale log left toggled on from
        # whatever row was highlighted before.
        self._log_view = False
        policy = next((item for item in self._policies if item.id == event.row_key.value), None)
        self._set_detail(policy)

    def action_toggle_log(self) -> None:
        policy = self._highlighted_policy()
        if policy is None or policy.log_path is None:
            return
        self._log_view = not self._log_view
        self._set_detail(policy)

    def live_state(self, policy_id: str) -> bool | None:
        """The matching Policy's own is_active() answer, or None when there is
        no such policy or it binds no is_active closure.

        Touches no widget, so a thread worker may call it -- and only a worker
        should: for the Linux daemon it may spawn a bounded
        `systemctl --user is-active` (WR-02). A failed read is None too: the
        caller then keeps the row as it is.
        """
        policy = next((p for p in self._policies if p.id == policy_id), None)
        if policy is None or policy.is_active is None:
            return None
        return run_live(policy.is_active)[0]

    def refresh_daemon_state(self, policy_id: str, applied: bool, live: bool | None) -> None:
        """Explicit UI refresh after an on-by-default worker run completes.

        `live` is the policy's own is_active() answer, resolved by the worker
        through live_state() BEFORE it posted (WR-02: this runs on the event
        loop, which must never probe systemd). It wins over `applied` --
        `applied=False` means only "no apply() call was made this run", which
        is equally true whether the policy is already ACTIVE-and-decided or
        already DISABLED-and-decided; conflating the two would incorrectly
        flip an already-on daemon's row to OFF on every ordinary second run
        (11-REVIEWS.md cycle 3 finding #11). `applied` is used only for a
        policy with no is_active closure; a policy that has one but whose
        answer the worker could not resolve keeps its row as it is.
        An unchanged value still supersedes every older job-state read: one
        that began before this apply must not repaint its pre-apply answer.
        """
        policy = next((p for p in self._policies if p.id == policy_id), None)
        if policy is None:
            return
        resolved = applied if policy.is_active is None else live
        if resolved is not None:
            self.active_state[policy_id] = resolved
            if resolved:
                self._drift.discard(policy_id)
        if self.is_mounted and self.app.is_running:
            if resolved is not None:
                self.query_one(DataTable[Any]).update_cell(
                    policy_id, "state", self._state_cell(policy_id)
                )
                highlighted = self._highlighted_policy()
                if highlighted is not None and highlighted.id == policy_id:
                    self._set_detail(highlighted)
            # Every completion supersedes older reads, even an unresolved one (T-21-52).
            self._start_job_state_read()
        else:
            self._job_state_generation += 1

    def action_toggle_policy(self) -> None:
        policy = self._highlighted_policy()
        if policy is None:
            return
        if self.app.refuse_if_mutating(self):
            return
        # Re-read at the mutation point: a prerequisite can land after the render.
        requirements_error = self._read_requirements(policy)
        active = self.active_state.get(policy.id)
        missing_requires = self._missing.get(policy.id)
        if active is None or missing_requires is None:
            if requirements_error is not None:
                self._read_error = _read_failure(requirements_error)
            self._refuse_unreadable()
            return
        if not active and missing_requires and policy.hard_requires:
            self.status.set(
                "Install required tool(s) first: "
                f"{', '.join(missing_requires)}. Open Catalog, install them, then retry.",
                "warn",
            )
            self.query_one(DataTable[Any]).update_cell(
                policy.id, "requires", self._requires_cell(policy)
            )
            self._set_detail(policy)
            return
        action = policy.remove if active else policy.apply
        if policy.log_path is not None:
            # WR-02: a scheduled job's apply/remove issues unbounded
            # launchctl/systemctl mutations, plus (Linux) the bounded
            # competing-mechanism probes -- seconds of frozen UI on a wedged
            # user manager. It runs on a thread worker through the same
            # run_live, and the outcome comes back as PolicyToggled.
            self.app.begin_mutation(MutationHolder.POLICY_TOGGLE)
            self.status.set(f"Applying {policy.label}...", "warn")
            self._toggle_policy_worker(policy, active, action)
            return
        result, self.error = run_live(action)
        self._finish_toggle(policy, active, result)

    @work(thread=True, exclusive=True, group="policy-toggle", exit_on_error=False)
    def _toggle_policy_worker(
        self, policy: Policy, active: bool, action: Callable[[], PolicyResult]
    ) -> None:
        result: PolicyResult | None = None
        error: str | None = "the policy change did not complete"
        try:
            result, error = run_live(action)
        finally:
            self.post_message(PolicyToggled(policy.id, active, result, error))

    def on_policy_toggled(self, message: PolicyToggled) -> None:
        self.app.end_mutation()
        policy = next((item for item in self._policies if item.id == message.policy_id), None)
        if policy is None:
            return
        self.error = message.error
        self._finish_toggle(policy, message.was_active, message.result)

    def _finish_toggle(self, policy: Policy, active: bool, result: PolicyResult | None) -> None:
        # A read begun before this completion must not repaint its older answer.
        self._job_state_generation += 1
        if result is None:
            self.app.show_result(
                self,
                f"Policy change failed: {self.error}. Check permissions, then press space.",
                "error",
                elsewhere=(
                    f"Policy change failed: {self.error}."
                    " Check permissions, then open Policies and press space."
                ),
            )
            self.app.request_refresh()
            return
        if not result.changed:  # a refused or no-op settings write: the row keeps its state
            self.app.show_result(self, result.warning or "", "warn")
            self.app.request_refresh()
            return
        new_active = not active
        self.active_state[policy.id] = new_active
        self._drift.discard(policy.id)
        self.query_one(DataTable[Any]).update_cell(policy.id, "state", self._state_cell(policy.id))
        self._read_requirements(policy)
        self.query_one(DataTable[Any]).update_cell(
            policy.id, "requires", self._requires_cell(policy)
        )
        self._set_detail(policy)
        verb = "enabled" if new_active else "disabled"
        self.app.show_result(
            self, self._summary(policy, verb, result), "warn" if result.warning else "ok"
        )
        self.app.request_refresh()

    def _summary(self, policy: Policy, verb: str, result: PolicyResult) -> str:
        # One line per outcome: a single joined line overflows the terminal width
        # and truncates the reload guidance (the Phase 3 fix).
        parts = [f"{policy.label} {verb}."]
        parts.extend(f"{layer.name}: {layer.detail}" for layer in result.layers)
        if result.reload_hint:
            parts.append(result.reload_hint)
        if result.warning:
            parts.append(result.warning)
        return multiline_summary(parts)

    def action_pick_time(self) -> None:
        policy = self._highlighted_policy()
        if policy is None or policy.set_schedule is None:
            return
        # Refuse before the picker; _time_picked checks again, because a
        # mutation can start while the picker is open.
        if self.app.refuse_if_mutating(self):
            return
        active = self.active_state.get(policy.id)
        if active is None:
            self._refuse_unreadable()
            return
        if not active:
            self.status.set(
                "Enable this policy first, then press t to set its schedule.",
                "warn",
            )
            self._set_detail(policy)
            return
        self.app.push_screen(TimePickerScreen(), self._time_picked(policy, policy.set_schedule))

    def _time_picked(
        self, policy: Policy, set_schedule: Callable[[int, int], PolicyResult]
    ) -> Callable[[str | None], None]:
        # A closure supplying the mutation and the messages, never its own
        # try/except OSError — set_schedule is called through run_live below,
        # exactly like action_toggle_policy already calls apply/remove
        # (.claude/architecture.md rule 3), never directly from this callback.
        # set_schedule is threaded in as its own parameter (not re-read from
        # policy inside the closure) so there is no reachable path where it
        # could be None here — action_pick_time already confirmed it isn't,
        # once, before this closure is ever built.
        def picked(value: str | None) -> None:
            if value is None:
                return
            # Checked HERE, at the actual mutation point, not only when the
            # picker was opened: the picker can stay on screen for as long as
            # the user takes to choose a time, and any worker mutation (the
            # on-by-default daemon apply, a removal, an update) can start
            # during that window (post-implementation review finding CR-02).
            if self.app.refuse_if_mutating(self):
                return
            hour_text, minute_text = value.split(":")
            hour, minute = int(hour_text), int(minute_text)
            result, error = run_live(lambda: set_schedule(hour, minute))
            if result is None:
                self.status.set(
                    f"Policy change failed: {error}. Check permissions, then press t.",
                    "error",
                )
                return
            self.status.set(self._summary(policy, "rescheduled", result), "ok")
            self._set_detail(policy)

        return picked

    def action_pick_link_mode(self) -> None:
        if self._set_link_mode is None:
            self.status.set(
                "Link mode cannot be changed from this entry point.",
                "warn",
            )
            return
        if self.app.refuse_if_mutating(self):  # before the picker, as t does
            return
        self.app.push_screen(LinkModeScreen(), self._link_mode_picked)

    def _link_mode_picked(self, value: str | None) -> None:
        if value is None:
            self.status.set(
                "Link mode unchanged because the picker was cancelled.",
                "warn",
            )
            return
        setter = self._set_link_mode
        if setter is None:
            return
        # At the mutation point, like the time picker: the modal can outlive a
        # mutation that started after it opened.
        if self.app.refuse_if_mutating(self):
            return
        aware_active = self.link_mode_aware_active()
        old = self._link_mode() if self._link_mode is not None else "centralized"
        report, error = run_live(lambda: move_link_mode(aware_active, value, setter, old_mode=old))
        if error is not None:
            self.mark_lost_policies_off(error)
            self.status.set(error, "error")
            return
        text, severity = _link_mode_status(value, report or (), old_mode=old)
        self.status.set(text, severity)
        self._refresh_link_mode_line()

    def mark_lost_policies_off(self, error: str) -> None:
        """WR-02: a failed move whose error names policies gone from both
        modes flips their rows OFF, so the table never claims a policy that
        is no longer on disk."""
        for policy_id in lost_policy_ids(error):
            self.active_state[policy_id] = False

    def link_mode_aware_active(self) -> list[Policy]:
        """The active, link-mode-aware policies: the ones a mode change moves.

        The live truth is each policy's own on-disk activity, re-probed at the
        moment of the change through the same predicate the uninstall sweep
        uses (installer.uninstall.policy_owned; 17-20, opencode H2). The
        cached active_state is only the table's last paint: another view can
        remove a policy without this screen ever hearing about it, and moving
        on a stale cache would resurrect it.
        """
        return [
            policy for policy in self._policies if policy.link_mode_aware and policy_owned(policy)
        ]


def _link_mode_status(
    value: str, report: Sequence[PolicyMove], *, old_mode: str
) -> tuple[str, str]:
    """(text, severity) both link-mode pickers show after a move: the saved
    mode, the policies moved, every failure named, and — when the move left
    split mode, whose aliases live in the rc files themselves — the exact
    action that refreshes the PATH wiring so the shells source ~/.myshellrc
    (17-20, opencode M1). Severity is warn when any entry failed (the mode
    itself was still saved), ok otherwise."""
    parts = [f"Link mode saved: {value}."]
    moved = [entry.policy_id for entry in report if entry.status == "moved"]
    failed = [entry for entry in report if entry.status == "failed"]
    if moved:
        parts.append(f" Moved: {', '.join(moved)}.")
    if old_mode == "split" and value != "split" and moved:
        parts.append(
            " The moved aliases now live in ~/.myshellrc, which the shells may not"
            f' source yet; refresh the PATH wiring: make fix ARGS="--link-mode {value}".'
        )
    for entry in failed:
        parts.append(f" Failed: {entry.policy_id} ({entry.detail}).")
    return "".join(parts), ("warn" if failed else "ok")


_STILL_CHECKING = "Still checking for a user timer manager; try again in a moment."
_REFRESH_SECONDS = 30
_SCHEDULE_COLUMNS = (
    ("schedule", "Schedule", 13),
    ("target", "Target", 12),
    ("state", "State", 9),
    ("every", "Every", 9),
    ("next", "Next", 5),
    ("last", "Last", 7),
    ("script", "Script", 9),
)
_STATE_CELLS = {
    "on": ("● [on]", "green"),
    "off": ("○ [off]", "dim"),
    "drift": ("! [drift]", "yellow"),
    "n/a": ("– [n/a]", "dim"),
    "unknown": ("…", "dim"),
}
_LAST_STYLES = {"ok": "green", "skipped": "yellow", "failed": "red", "interrupted": "red"}
_CHECKING_NOTE = "Checking for a user timer manager…"
_NO_MANAGER_NOTE = "unavailable: no user timer manager — nothing is scheduled on this machine."
_LINUX_NOTE = "Timers run while you are logged in; a missed run catches up once at login."
_MACOS_NOTE = "Missed during sleep: runs once at wake. Missed while shut down: skipped."
_SCHEDULE_DRIFT = "Drift: its timer files are missing or changed. space writes them again."
_DAMAGED_COPY = "schedules.json was damaged earlier; the damaged copy is kept beside it."
# The cache cleanup managers in the UI's target order, with the command each one runs.
_CACHE_PRUNES = (
    ("uv", "uv cache prune"),
    ("pnpm", "pnpm store prune"),
    ("brew", "brew cleanup"),
    ("npm", "npm cache verify"),
)
_TMP_WHAT = "deletes orphaned Bun runtime files from the temp dir"
_CACHE_WHAT = "runs each installed package manager's prune command"
_TIMES_LISTED = 8  # more slots than this are shown as a compressed range
_CURSOR_SCHEDULE_ID = "update-cursor-agent"


def _fit(text: str, width: int, *, from_left: bool = False) -> str:
    """`text` cut to `width` cells with an ellipsis, at the end (or the start with `from_left`)."""
    if cell_len(text) <= width:
        return text
    kept = text
    while kept and cell_len(kept) > width - 1:
        kept = kept[1:] if from_left else kept[:-1]
    return f"…{kept}" if from_left else f"{kept}…"


def _sentence(text: str) -> str:
    """The first line of `text` as one sentence with a single closing period."""
    lines = sanitize_log_line(text).strip().splitlines()
    return f"{(lines[0] if lines else 'unknown error').rstrip('.')}."


def _tilde(path: Path, home: Path) -> str:
    """`path` with a leading `home` shown as `~`."""
    if path == home or home in path.parents:
        return f"~/{path.relative_to(home)}" if path != home else "~"
    return str(path)


class SchedulesScreen(AppScreen):
    """The built-in schedules: state, timing and last result, toggled live (D-21).

    `space` turns the highlighted schedule on or off now; every change runs on a thread
    worker through `run_live` under the in-app mutation lock only, so a scheduled run in
    flight is never touched (SPEC edge R5). Render reads files only: the manager probe and
    the change are the only workers that start a process (D-13).
    """

    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_schedule", "toggle schedule", show=True, priority=True),
        Binding("e", "edit_time", "time", show=True),
        Binding("m", "set_model", "model", show=True),
    ]
    DEFAULT_CSS = """
    SchedulesScreen #schedule-note { height: 1; padding: 0 1; }
    SchedulesScreen DataTable { height: auto; max-height: 8; }
    SchedulesScreen #schedule-detail {
        height: 1fr; padding: 0 1; background: $surface; overflow-y: auto;
    }
    """

    def __init__(self, inputs: ScheduleInputs) -> None:
        super().__init__(view="schedules")
        self._inputs = inputs
        self._ctx = inputs.context
        # None until the probe answers; a host with no context never probes.
        self._manager: bool | None = None if inputs.context is not None else False
        self._state = schedules.ScheduleState()
        self._last: dict[str, schedules.LastRun] = {}
        self._log_error: str | None = None
        self._log_line: str | None = None
        self._damage: str | None = None
        # The damage warning shows once per entry, never on a refresh.
        self._announce_damage = False
        self.note_text = ""
        self.detail_text = ""

    def compose_body(self) -> ComposeResult:
        yield Static("", id="schedule-note")
        yield DataTable()
        yield Static("", id="schedule-detail")

    def on_mount(self) -> None:
        table = self.query_one(DataTable[Any])
        table.cursor_type = "row"
        for key, label, width in _SCHEDULE_COLUMNS:
            table.add_column(label, width=width, key=key)
        for schedule in schedules.SCHEDULES:
            table.add_row(*self._cells(schedule), key=schedule.id)
        table.focus()
        self.set_interval(_REFRESH_SECONDS, self.tick)

    def enter_view(self) -> None:
        self._announce_damage = True
        if self._ctx is not None:
            self._probe_worker()
        self.state_refreshed()

    def tick(self) -> None:
        """The periodic refresh: only while this view is on top and nothing is mutating."""
        if self.is_mounted and self.app.screen is self and not self.app.mutation_in_flight:
            self.state_refreshed()

    @work(thread=True, exclusive=True, group="schedule-probe", exit_on_error=False)
    def _probe_worker(self) -> None:
        """Ask whether a user timer manager exists, off the event loop (D-24)."""
        reachable = False
        try:
            ctx = self._ctx
            if ctx is not None:
                answer, _error = run_live(lambda: schedules.manager_reachable(ctx))
                reachable = bool(answer)
        finally:
            self.post_message(ScheduleManagerProbed(reachable))

    def on_schedule_manager_probed(self, message: ScheduleManagerProbed) -> None:
        self._manager = message.reachable
        self.state_refreshed()

    def state_refreshed(self) -> None:
        """Re-read the state file, the run log and the holder line, then repaint (files only)."""
        self._reread()
        announce, self._announce_damage = self._announce_damage, False
        if announce and self._damage is not None:
            self.status.set(self._damage, "warn")
        if not self.is_mounted:
            return
        table = self.query_one(DataTable[Any])
        for schedule in schedules.SCHEDULES:
            for (column, _label, _width), text in zip(
                _SCHEDULE_COLUMNS, self._cells(schedule), strict=True
            ):
                table.update_cell(schedule.id, column, text)
        self.note_text = self._note()
        self.query_one("#schedule-note", Static).update(Text(self.note_text, style="dim"))
        self._set_detail()
        self._show_log_error()

    def _reread(self) -> None:
        ctx = self._ctx
        if ctx is None:
            return
        loaded, error = run_live(lambda: schedules.load_state(ctx.state_path))
        if loaded is None:
            self._state = schedules.ScheduleState()
            problem = _sentence(error or "unknown error").rstrip(".")
            self._damage = f"Could not read schedules.json ({problem}); using defaults."
        else:
            self._state = loaded.state
            self._damage = loaded.warning or (_DAMAGED_COPY if loaded.damaged else None)
        last, self._log_error = run_live(
            lambda: schedules.read_last_runs(ctx.log_path, ctx.lock_path)
        )
        self._last = last or {}

    def _show_log_error(self) -> None:
        """Over an empty status or this screen's own earlier line only (Policies' rule)."""
        previous = self._log_line
        self._log_line = (
            None
            if self._log_error is None
            else f"Could not read the schedule log: {_sentence(self._log_error)}"
        )
        if self._log_line is None:
            if previous is not None:
                self.status.retract(previous)
        elif not self.status.text or self.status.text == previous:
            self.status.set(self._log_line, "error")

    def _note(self) -> str:
        ctx = self._ctx
        if self._manager is None:
            return _CHECKING_NOTE
        if not self._manager or ctx is None:
            return _NO_MANAGER_NOTE
        return _MACOS_NOTE if ctx.platform_os == "macos" else _LINUX_NOTE

    def _row_state(self, schedule: schedules.Schedule) -> schedules.RowState:
        ctx = self._ctx
        if ctx is None:
            return schedules.RowState("n/a", schedules.NO_MANAGER_REASON)
        return schedules.row_state(
            ctx, self._state, schedule, manager=self._manager, present=self._inputs.present
        )

    def _is_linux_tmp(self, schedule: schedules.Schedule) -> bool:
        ctx = self._ctx
        is_macos = ctx is not None and ctx.platform_os == "macos"
        return schedule.kind is schedules.JobKind.TMP_CLEANUP and not is_macos

    def _grid(self, schedule: schedules.Schedule) -> tuple[schedules.Slot, ...] | None:
        """The run times from the record; None for Linux tmp cleanup's fixed monotonic timer."""
        if self._is_linux_tmp(schedule):
            return None
        record = schedules.record_for(self._state, schedule.id)
        interval = 24 if schedule.kind is schedules.JobKind.TMP_CLEANUP else record.interval
        return schedules.slots(interval, record.start)

    def _cells(self, schedule: schedules.Schedule) -> list[Text]:
        row = self._row_state(schedule)
        word, style = _STATE_CELLS[row.word]
        dim = "dim" if row.word in ("off", "n/a", "unknown") else ""
        record = schedules.record_for(self._state, schedule.id)
        if self._is_linux_tmp(schedule):
            every = "10 min"
        else:
            tmp = schedule.kind is schedules.JobKind.TMP_CLEANUP
            every = f"{24 if tmp else record.interval}h {record.start}"
        job = "update" if schedule.kind is schedules.JobKind.UPDATE else schedule.label
        upcoming = self._next_text(schedule, row)
        return [
            Text(_fit(job, 13), style="bold"),
            Text(_fit(self._target(schedule), 12)),
            Text(word, style=style),
            Text(_fit(every, 9), style=dim),
            Text(upcoming, style="" if upcoming != "–" else "dim"),
            self._last_cell(schedule.id),
            Text(_fit(schedules.RUNNER_NAME, 9, from_left=True), style="dim"),
        ]

    def _next_text(self, schedule: schedules.Schedule, row: schedules.RowState) -> str:
        """HH:MM of the next run for an on row, from the unit's own slot function (D-04)."""
        if row.word != "on":
            return "–"
        grid = self._grid(schedule)
        if grid is None:  # Linux tmp cleanup: its last result plus the fixed 10 minutes
            last = self._last.get(schedule.id)
            if last is None or last.at is None:
                return "–"
            return f"{last.at + timedelta(minutes=10):%H:%M}"
        return f"{schedules.next_run(grid, self._inputs.now()):%H:%M}"

    def _last_cell(self, schedule_id: str) -> Text:
        if self._log_error is not None:
            return Text("…")
        last = self._last.get(schedule_id)
        text = schedules.last_cell(last, self._inputs.now())
        if last is None:
            return Text(text, style="dim")
        return Text(text, style=_LAST_STYLES.get(last.word, ""))

    def _target(self, schedule: schedules.Schedule) -> str:
        if schedule.kind is schedules.JobKind.UPDATE:
            return schedule.target or ""
        if schedule.kind is schedules.JobKind.TMP_CLEANUP:
            return "$TMPDIR"
        return " ".join(name for name, _command in self._managers()) or "none"

    def _managers(self) -> list[tuple[str, str]]:
        ctx = self._ctx
        if ctx is None:
            return []
        return [(name, command) for name, command in _CACHE_PRUNES if ctx.which(name)]

    def _set_detail(self) -> None:
        schedule = self._highlighted_schedule()
        self.detail_text = "" if schedule is None else self._detail(schedule)
        self.query_one("#schedule-detail", Static).update(Text(self.detail_text))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        del event  # the highlighted row is read back from the table
        self._set_detail()

    def _detail(self, schedule: schedules.Schedule) -> str:
        """The panel for one row, most important line first (UI-SPEC section 4)."""
        row = self._row_state(schedule)
        if schedule.kind is schedules.JobKind.UPDATE:
            what = f"runs {schedule.target}'s update the way the catalog's u does"
        elif schedule.kind is schedules.JobKind.TMP_CLEANUP:
            what = _TMP_WHAT
        else:
            what = _CACHE_WHAT
        if row.word == "drift":
            lines = [_SCHEDULE_DRIFT]
        elif row.word == "n/a":
            lines = [row.reason or schedules.NO_MANAGER_REASON, f"{what}."]
        elif row.word == "unknown":
            lines = [f"{schedule.label} — checking its state…"]
        else:
            lines = [f"{schedule.label} is {row.word} — {what}."]
        lines += [self._last_line(schedule.id), self._times_line(schedule)]
        lines += self._extra_lines(schedule)
        ctx = self._ctx
        if ctx is not None:
            runner = _tilde(ctx.data_dir / schedules.RUNNER_NAME, ctx.home)
            job = f"update {schedule.target}" if schedule.target else schedule.kind.value
            lines.append(f"runs: uv run --no-project --script {runner} {job}")
        return "\n".join(sanitize_log_line(line) for line in lines)

    def _last_line(self, schedule_id: str) -> str:
        if self._log_error is not None:
            return "last: could not be read"
        last = self._last.get(schedule_id)
        if last is None:
            return "last: never"
        if last.word == "running":
            return f"last: running since {last.at:%H:%M}" if last.at else "last: running"
        if last.at is None:
            return f"last: {last.text}"
        return f"last: {last.at.astimezone().isoformat(timespec='seconds')} {last.text}"

    def _times_line(self, schedule: schedules.Schedule) -> str:
        grid = self._grid(schedule)
        if grid is None:
            return "times: every 10 min, first run 2 min after login"
        names = [f"{hour:02d}:{minute:02d}" for hour, minute in grid]
        if schedule.kind is schedules.JobKind.TMP_CLEANUP:
            return f"times: daily at {names[0]} (local)"
        if len(names) <= _TIMES_LISTED:
            return f"times: {', '.join(names)} (local)"
        interval = schedules.record_for(self._state, schedule.id).interval
        every = "hour" if interval == 1 else f"{interval} hours"
        return f"times: {', '.join(names[:3])} … {names[-1]}, every {every} (local)"

    def _extra_lines(self, schedule: schedules.Schedule) -> list[str]:
        """The row-specific lines: what a cache prune runs, the cursor model, the tmp notes."""
        if schedule.kind is schedules.JobKind.CACHE_CLEANUP:
            commands = [command for _name, command in self._managers()]
            if not commands:
                return ["prunes: nothing — no uv, pnpm, brew or npm found"]
            return [f"prunes: {' · '.join(commands)}"]
        if schedule.id == _CURSOR_SCHEDULE_ID:
            model = self._state.cursor_default_model
            lines = [f"model: {model} — press m to change"]
            shim = self._state.cursor_shim
            if shim == "not-listed":
                lines.append(
                    f"! {model} is not in your model list; the shim passes arguments through."
                )
            elif shim == "unverified":
                lines.append(
                    f"model unverified: could not read the cursor-agent model list; using {model}."
                )
            elif shim == "kept-foreign":
                lines.append(
                    "your own ~/.local/bin/cursor-agent is kept: it has no installer sentinel."
                )
            return lines
        if schedule.kind is schedules.JobKind.TMP_CLEANUP:
            lines = [_LINGER_SENTENCE] if self._is_linux_tmp(schedule) else []
            usage = _temp_usage_line(self._inputs.disk_pressure)
            competing = _competing_line(self._inputs.competing)
            return [*lines, *filter(None, (usage, competing))]
        return []

    def _highlighted_schedule(self) -> schedules.Schedule | None:
        key = highlighted_key(self.query_one(DataTable[Any]))
        return next((item for item in schedules.SCHEDULES if item.id == key), None)

    def action_toggle_schedule(self) -> None:
        schedule = self._highlighted_schedule()
        if schedule is None or self.app.refuse_if_mutating(self):
            return
        row = self._row_state(schedule)
        if row.word == "unknown":
            self.status.set(_STILL_CHECKING, "warn")
            return
        if row.word == "n/a":
            self.status.set(f"Cannot turn on {schedule.label}: {row.reason}.", "warn")
            return
        verb: Literal["on", "off"] = "off" if row.word == "on" else "on"
        self._start_change(ScheduleChange(schedule.id, verb, was_drift=row.word == "drift"))

    def _refuse_change(self, schedule: schedules.Schedule) -> bool:
        """The shared refusal for `e` and `m` on a row that is still unknown or unavailable."""
        row = self._row_state(schedule)
        if row.word == "unknown":
            self.status.set(_STILL_CHECKING, "warn")
            return True
        if row.word == "n/a":
            self.status.set(f"Cannot change {schedule.label}: {row.reason}.", "warn")
            return True
        return False

    def action_edit_time(self) -> None:
        schedule = self._highlighted_schedule()
        if schedule is None or self.app.refuse_if_mutating(self) or self._refuse_change(schedule):
            return
        if self._is_linux_tmp(schedule):
            self.status.set(schedules.TMP_FIXED_CADENCE_MESSAGE, "warn")
            return
        record = schedules.record_for(self._state, schedule.id)
        daily = schedule.kind is schedules.JobKind.TMP_CLEANUP
        modal = ScheduleTimeScreen(
            f"When {schedule.label} runs", None if daily else record.interval, record.start
        )
        self.app.push_screen(modal, self._time_saved(schedule.id))

    def _time_saved(self, schedule_id: str) -> Callable[[tuple[int, str] | None], None]:
        def saved(value: tuple[int, str] | None) -> None:
            # Checked at the mutation point too: a mutation can start while the modal is open.
            if value is None or self.app.refuse_if_mutating(self):
                return
            interval, start = value
            self._start_change(
                ScheduleChange(schedule_id, "retime", interval=interval, start=start)
            )

        return saved

    def action_set_model(self) -> None:
        schedule = self._highlighted_schedule()
        if schedule is None or self.app.refuse_if_mutating(self):
            return
        if schedule.id != _CURSOR_SCHEDULE_ID:
            self.status.set(
                "m sets the cursor-agent model; move to the cursor-agent row first.", "warn"
            )
            return
        ctx = self._ctx
        if self._refuse_change(schedule) or ctx is None:
            return
        agent = cursor_shim.shim_paths(ctx.home)[1]
        modal = CursorModelScreen(self._state.cursor_default_model, lambda: ctx.read_models(agent))
        self.app.push_screen(modal, self._model_saved)

    def _model_saved(self, model: str | None) -> None:
        if model is None or self.app.refuse_if_mutating(self):
            return
        self._start_change(ScheduleChange(_CURSOR_SCHEDULE_ID, "model", model=model))

    def _start_change(self, change: ScheduleChange) -> None:
        self.app.begin_mutation(MutationHolder.SCHEDULE_CHANGE)
        self._change_worker(change)

    @work(thread=True, exclusive=True, group="schedule-change", exit_on_error=False)
    def _change_worker(self, change: ScheduleChange) -> None:
        report: schedules.ApplyReport | None = None
        error: str | None = "the schedule change did not complete"
        try:
            ctx = self._ctx
            if ctx is None:  # unreachable: every action refuses an n/a row first
                error = schedules.NO_MANAGER_REASON
            elif change.verb == "on":
                report, error = run_live(lambda: schedules.turn_on(ctx, change.schedule_id))
            elif change.verb == "off":
                report, error = run_live(lambda: schedules.turn_off(ctx, change.schedule_id))
            elif change.verb == "retime":
                report, error = run_live(
                    lambda: schedules.retime(ctx, change.schedule_id, change.interval, change.start)
                )
            else:
                report, error = run_live(lambda: schedules.set_cursor_model(ctx, change.model))
        finally:
            self.post_message(ScheduleChanged(change, report, error))

    def on_schedule_changed(self, message: ScheduleChanged) -> None:
        self.app.end_mutation()
        ctx = self._ctx
        if ctx is not None and message.error is None:
            # Acting here is the user's decision that ends the damaged-state guard (R2-11).
            run_live(lambda: schedules.clear_damage(ctx.state_path))
        self.state_refreshed()
        text, severity = self._change_line(message)
        self.app.show_result(self, text, severity)

    def _upcoming(self, schedule: schedules.Schedule) -> str:
        """`next run at HH:MM`, or the fixed cadence for Linux tmp cleanup."""
        grid = self._grid(schedule)
        if grid is None:
            return "runs every 10 min"
        return f"next run at {schedules.next_run(grid, self._inputs.now()):%H:%M}"

    def _change_line(self, message: ScheduleChanged) -> tuple[str, str]:
        """The status for a finished change (UI-SPEC section 5); the state is already re-read."""
        change, error = message.change, message.error
        schedule = schedules.schedule_by_id(change.schedule_id)
        label = schedule.label
        if error is not None:
            return self._failure_line(change, error, label), "error"
        report = message.report or schedules.ApplyReport(False)
        # Warnings the lines below do not already say (the kept-file sentence they do).
        extra = [
            sanitize_log_line(warning)
            for warning in report.warnings
            if not warning.startswith("your own ~/.local/bin/cursor-agent")
        ]
        if change.verb == "off":
            line = f"Turned off {label}; its timer files are removed."
            if schedule.id == _CURSOR_SCHEDULE_ID:
                line = "Turned off cursor-agent update; cursor-agent is a plain link again."
            severity = "ok"
        elif change.verb == "retime":
            line, severity = self._retime_line(change, schedule, report)
        elif change.verb == "model":
            line, severity = self._model_line(change.model, report)
        else:
            line, severity = self._on_line(change, schedule, report)
        if extra:
            return " ".join([line, *extra]), "warn"
        return line, severity

    @staticmethod
    def _failure_line(change: ScheduleChange, error: str, label: str) -> str:
        reason = _sentence(error)
        if change.verb in ("on", "off"):
            return f"Could not turn {change.verb} {label}: {reason}"
        if change.verb == "retime":
            return f"Could not change {label}: {reason}"
        return f"Could not set the cursor-agent model: {reason}"

    def _on_line(
        self, change: ScheduleChange, schedule: schedules.Schedule, report: schedules.ApplyReport
    ) -> tuple[str, str]:
        label, when = schedule.label, self._upcoming(schedule)
        if change.was_drift:
            return f"Rewrote the {label} timer files: {when}.", "ok"
        if schedule.id != _CURSOR_SCHEDULE_ID or report.shim is None:
            return f"Turned on {label}: {when}.", "ok"
        model, shim = self._state.cursor_default_model, report.shim
        if shim.write == "kept-foreign":
            return f"Turned on {label}; your own cursor-agent file was kept.", "warn"
        if shim.check == "not-listed":
            return f"Turned on {label}; {model} is not listed, so the shim passes through.", "warn"
        if shim.check == "unverified":
            return f"Turned on {label}: {when}; model {model} (unverified).", "warn"
        return f"Turned on {label}: {when}; model {model}.", "ok"

    def _retime_line(
        self, change: ScheduleChange, schedule: schedules.Schedule, report: schedules.ApplyReport
    ) -> tuple[str, str]:
        label = schedule.label
        daily = schedule.kind is schedules.JobKind.TMP_CLEANUP
        phrase = (
            f"daily at {change.start}"
            if daily
            else f"every {change.interval} h from {change.start}"
        )
        if not report.changed:
            return f"No change: {label} already runs {phrase}.", "ok"
        if schedules.record_for(self._state, schedule.id).decided is True:
            return f"{label} now runs {phrase}; {self._upcoming(schedule)}.", "ok"
        return f"Saved: {label} will run {phrase} once it is on.", "ok"

    def _model_line(self, model: str, report: schedules.ApplyReport) -> tuple[str, str]:
        record = schedules.record_for(self._state, _CURSOR_SCHEDULE_ID)
        if record.decided is not True:
            return f"Saved: cursor-agent will default to {model} once its schedule is on.", "ok"
        shim = report.shim
        if shim is not None and shim.write == "kept-foreign":
            return (
                f"cursor-agent now defaults to {model}; your own cursor-agent file was kept.",
                "warn",
            )
        if shim is not None and shim.check == "not-listed":
            return (
                f"cursor-agent: {model} is not in your model list; the shim passes through.",
                "warn",
            )
        if shim is not None and shim.check == "unverified":
            return (
                f"cursor-agent now defaults to {model}; model unverified (list unreadable).",
                "warn",
            )
        return f"cursor-agent now defaults to {model}.", "ok"


class ConfirmGuardFile(ModalScreen[bool]):
    """Confirm one foreign rc file before rewriting its PATH lines in place.

    enter/y guard this file; escape/n skip it and leave the file untouched.
    One file per modal: declining one never edits it and never cancels the rest.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "guard", "guard", show=True, priority=True),
        Binding("y", "guard", "guard", show=False),
        Binding("escape", "skip", "skip", show=True),
        Binding("n", "skip", "skip", show=False),
    ]
    DEFAULT_CSS = """
    ConfirmGuardFile { align: center middle; }
    ConfirmGuardFile > Static { width: 76; height: auto; border: round yellow; padding: 1 2; }
    """

    def __init__(self, path: Path, records: Sequence[PathWriterLine]) -> None:
        super().__init__()
        lines = [f"Guard PATH lines in {path}?"]
        for index, record in enumerate(records):
            after = path_export_guard(record.directory)
            lines.append(f"  {index + 1}: {record.text}  ->  {after}")
        lines.append(
            f"A backup of the original is saved as {path}.tools-installer.old first. "
            "Nothing is deleted."
        )
        self.summary = "\n".join(lines)

    def compose(self) -> ComposeResult:
        # File text is untrusted; Text() does not parse markup.
        yield Static(Text(self.summary))

    def action_guard(self) -> None:
        self.dismiss(True)

    def action_skip(self) -> None:
        self.dismiss(False)


class ConfirmUninstall(ModalScreen[bool]):
    """Confirm the one destructive, hard-to-reverse commit: deleting installed
    artifacts. enter/y confirm; escape/n cancel. Reversible actions (policies)
    deliberately get no modal — over-confirming trains click-through."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "confirm", "remove", show=True, priority=True),
        Binding("y", "confirm", "remove", show=False),
        Binding("escape", "cancel", "cancel", show=True),
        Binding("n", "cancel", "cancel", show=False),
    ]
    DEFAULT_CSS = """
    ConfirmUninstall { align: center middle; }
    ConfirmUninstall > Vertical {
        width: 60; height: auto; max-height: 18; border: round red; padding: 1 2;
    }
    ConfirmUninstall #confirm-body { height: auto; max-height: 13; }
    """

    def __init__(self, summary: str, review: Sequence[Text] = ()) -> None:
        super().__init__()
        self.summary = summary  # public test seam
        self.review = tuple(review)  # public test seam: blocks 3-7, each folded `Text`

    def compose(self) -> ComposeResult:
        body = Text("\n").join(
            [
                Text(f"Remove {self.summary}?", style="bold red"),
                Text(""),
                Text("This deletes installed artifacts and is not undoable."),
                *self.review,
            ]
        )
        with Vertical(id="confirm-box"):
            with VerticalScroll(id="confirm-body"):
                yield Static(body)
            yield Static(Text("enter remove · esc cancel", style="dim"), id="confirm-keys")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class NavScreen(ModalScreen[str | None]):
    """Our command palette: a modal list of views, dismissing the chosen one.

    Replaces Textual's default palette (disabled on the app), whose options
    dead-end by closing the screen. Selecting an item dismisses with the view
    name; Escape dismisses with None (no navigation).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    NavScreen { align: center middle; }
    NavScreen > ListView { width: 60; height: auto; border: round $accent; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(*[ListItem(Label(view.palette), id=view.name) for view in VIEWS])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TimePickerScreen(ModalScreen[str | None]):
    """Quantized 30-minute time-of-day picker: dismisses with an "HH:MM"
    string, or None on escape/cancel. Structurally mirrors NavScreen's
    ModalScreen[str | None] + ListView/ListItem shape, except every widget id
    is letter-prefixed and colon-free ("time-HH-MM") since a raw "HH:MM" id
    (e.g. "03:30") is an invalid Textual identifier — it begins with a digit
    and contains ":" — while the DISPLAY text stays the plain "HH:MM" string.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    TimePickerScreen { align: center middle; }
    TimePickerScreen > ListView { width: 20; height: 20; border: round $accent; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(
            *[
                ListItem(Label(f"{hour:02d}:{minute:02d}"), id=f"time-{hour:02d}-{minute:02d}")
                for hour in range(24)
                for minute in (0, 30)
            ]
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id is None:  # unreachable: every item above is constructed with one
            return
        self.dismiss(item_id.removeprefix("time-").replace("-", ":"))

    def action_cancel(self) -> None:
        self.dismiss(None)


class LinkModeScreen(ModalScreen[str | None]):
    """Three-option PATH link-mode picker. Labels are the wording the retired
    pre-TUI questionary prompt used, so moving the question into the app is a
    UI relocation, not a behaviour change.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    LinkModeScreen { align: center middle; }
    LinkModeScreen > ListView { width: 80; height: 8; border: round $accent; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(
            ListItem(
                Label("Centralized: one ~/.myshellrc, sourced from .zshrc and .bashrc"),
                id="link-centralized",
            ),
            ListItem(
                Label("Single shell: source ~/.myshellrc from your current shell only"),
                id="link-single",
            ),
            ListItem(
                Label("Split: write PATH directly into each rc file (no ~/.myshellrc)"),
                id="link-split",
            ),
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id is None:  # unreachable: every item above is constructed with one
            return
        self.dismiss(item_id.removeprefix("link-"))

    def action_cancel(self) -> None:
        self.dismiss(None)


class ScheduleTimeScreen(ModalScreen[tuple[int, str] | None]):
    """When a schedule runs: an interval (one of eight) and a start time, validated in place.

    A rejected value keeps the modal open with the validator's message and nothing leaves it
    (P6); `escape` returns None. macOS tmp cleanup passes `interval=None`: a daily time only.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "cancel", show=False),
    ]
    DEFAULT_CSS = """
    ScheduleTimeScreen { align: center middle; }
    ScheduleTimeScreen > Vertical {
        width: 60; height: auto; border: round $accent; padding: 0 1; background: $surface;
    }
    ScheduleTimeScreen Label { height: 1; }
    """

    def __init__(self, title: str, interval: int | None, start: str) -> None:
        super().__init__()
        self._title = title
        self._interval = interval
        self._start = start

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Text(self._title, style="bold"), id="time-title")
            if self._interval is not None:
                yield Label("Every")
                yield Select[int](
                    [(f"{hours} h", hours) for hours in schedules.INTERVALS],
                    value=self._interval,
                    allow_blank=False,
                    id="time-interval",
                )
            label = "Starting at" if self._interval is not None else "Daily at"
            yield Label(f"{label} (HH:MM, local time)")
            yield Input(self._start, placeholder="00:00", max_length=5, id="time-start")
            yield Label("", id="time-preview")
            yield Label("", id="time-error")
            yield Label(Text("enter save | esc cancel", style="dim"), id="time-keys")

    def on_mount(self) -> None:
        self._refresh_preview()

    def _chosen_interval(self) -> int | None:
        if self._interval is None:
            return 24
        value = self.query_one(Select[int]).value
        return value if isinstance(value, int) else None

    def _refresh_preview(self) -> None:
        start = self.query_one(Input).value
        interval = self._chosen_interval()
        try:
            grid = schedules.slots(interval if interval is not None else 0, start)
        except daemon.DaemonScheduleError:
            text = "Runs at: enter a time as HH:MM"
        else:
            names = [f"{hour:02d}:{minute:02d}" for hour, minute in grid]
            if self._interval is None:
                text = f"Runs daily at {names[0]}"
            elif len(names) <= _TIMES_LISTED:
                text = f"Runs at {', '.join(names)}"
            else:
                text = f"Runs at {', '.join(names[:3])} … {names[-1]} ({len(names)} times a day)"
        self.query_one("#time-preview", Label).update(Text(text, style="dim"))

    def on_select_changed(self, event: Select.Changed) -> None:
        del event
        self._refresh_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        del event
        self._refresh_preview()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        start = self.query_one(Input).value
        interval = self._chosen_interval()
        try:
            hours = schedules.validate_interval(interval if interval is not None else 0)
            schedules.validate_start(start)
        except daemon.DaemonScheduleError as exc:
            self.query_one("#time-error", Label).update(Text(str(exc), style="red"))
            return
        self.dismiss((hours, start))

    def action_cancel(self) -> None:
        self.dismiss(None)


class CursorModelsRead(Message):
    """The threaded `cursor-agent --list-models` read finished; `models` is None on failure."""

    def __init__(self, models: tuple[str, ...] | None, error: str | None) -> None:
        self.models = models
        self.error = error
        super().__init__()


class CursorModelScreen(ModalScreen[str | None]):
    """The cursor-agent default model: a filter field over the listed ids, or free text.

    The list is read on a thread worker when the modal opens; an answer that lands after the
    modal closed is dropped. An unlisted but well-formed id is accepted (D-18, offline edits).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "cancel", show=False),
    ]
    DEFAULT_CSS = """
    CursorModelScreen { align: center middle; }
    CursorModelScreen > Vertical {
        width: 64; height: 16; border: round $accent; padding: 0 1; background: $surface;
    }
    CursorModelScreen Label { height: 1; }
    CursorModelScreen OptionList { height: 1fr; }
    """

    def __init__(self, current: str, read_models: Callable[[], tuple[str, ...] | None]) -> None:
        super().__init__()
        self._current = current
        self._read_models = read_models
        self._dismissed = False
        # The ids the worker read, in list order; empty until the list lands.
        self.listed: tuple[str, ...] = ()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                Text("Model cursor-agent uses when no --model is given", style="bold"),
                id="model-title",
            )
            yield Input(self._current, id="model-input")
            yield Label(Text("Reading your cursor-agent models…", style="dim"), id="model-status")
            yield OptionList(id="model-list")
            yield Label("", id="model-error")
            yield Label(Text("enter use | esc cancel", style="dim"), id="model-keys")

    def on_mount(self) -> None:
        self.query_one(OptionList).display = False
        self._read_worker()

    @work(thread=True, exclusive=True, group="schedule-models", exit_on_error=False)
    def _read_worker(self) -> None:
        models: tuple[str, ...] | None = None
        error: str | None = "the model list did not load"
        try:
            models, error = run_live(self._read_models)
            if models is None and error is None:
                error = "cursor-agent --list-models gave no list"
        finally:
            self.post_message(CursorModelsRead(models, error))

    def on_cursor_models_read(self, message: CursorModelsRead) -> None:
        if self._dismissed:
            return
        status = self.query_one("#model-status", Label)
        if message.models is None:
            reason = _sentence(message.error or "unknown error")
            status.update(
                Text(f"Could not read the model list: {reason} Type a model id.", "yellow")
            )
            return
        self.listed = tuple(dict.fromkeys(message.models))
        status.display = False
        self.query_one(OptionList).display = True
        self._fill()

    def _fill(self) -> None:
        typed = self.query_one(Input).value
        needle = "" if typed == self._current else typed.lower()
        options = self.query_one(OptionList)
        options.clear_options()
        options.add_options(
            Option(
                Text(f"{'● ' if model == self._current else '  '}{sanitize_log_line(model)}"),
                id=model,
            )
            for model in self.listed
            if needle in model.lower()
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        del event
        if self.listed:
            self._fill()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._use(self.query_one(Input).value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option.id is not None:  # every option is built with its model id
            self._use(event.option.id)

    def _use(self, model: str) -> None:
        try:
            schedules.validate_model_id(model)
        except daemon.DaemonScheduleError as exc:
            self.query_one("#model-error", Label).update(Text(str(exc), style="red"))
            return
        self._dismissed = True
        self.dismiss(model)

    def action_cancel(self) -> None:
        self._dismissed = True
        self.dismiss(None)


MUTATION_REFUSAL = "{holder} is running; wait for it to finish. Navigation still works."
# Nothing in the app ever holds this noun: only a scheduled runner holds the run lock, so it
# is a refusal, not a MutationHolder.
SCHEDULED_RUN_REFUSAL = MUTATION_REFUSAL.format(holder="A scheduled run")


class ScheduleDefaultsApplied(Message):
    """The threaded schedule-defaults reconcile finished; `report` is what it did (an empty
    report when it did nothing or raised).

    Posted unconditionally from UnifiedApp's own worker, in a finally block,
    regardless of outcome -- mirroring GlobalsAudited/GlobalsReinstalled's same
    thread -> post_message hand-off shape, for the identical reason: widgets
    may only be touched from the app's own thread.
    """

    def __init__(self, report: schedules.ReconcileReport) -> None:
        self.report = report
        super().__init__()


class RefreshPublished(Message):
    """The refresh worker published a pass. `error` is the pass's first error;
    a clean publication means the pass succeeded."""

    def __init__(self, error: str | None, warning: str | None) -> None:
        super().__init__()
        self.error = error
        self.warning = warning


class RefreshFinished(Message):
    """The refresh worker ended; `error` is the pass's first failure, if any."""

    def __init__(self, error: str | None) -> None:
        super().__init__()
        self.error = error


class MutationLock:
    """The one app mutation lock: a holder noun while a mutation runs, else None.
    A plain base so `UnifiedApp` and a test host share it instead of copying it.

    The four holders that change installed tools also take the cross-process run lock, so a
    scheduled run and the app never mutate at once (D-12); toggles and schedule changes stay
    in-app only."""

    _mutation_holder: MutationHolder | None = None
    _run_lock: runlock.RunLock | None = None
    _CROSS_PROCESS = frozenset(
        {
            MutationHolder.INSTALL_RUN,
            MutationHolder.UPDATE,
            MutationHolder.REMOVAL,
            MutationHolder.GLOBALS_REINSTALL,
        }
    )

    @property
    def mutation_in_flight(self) -> bool:
        return self._mutation_holder is not None

    @property
    def mutation_holder(self) -> MutationHolder | None:
        return self._mutation_holder

    def begin_mutation(
        self, holder: MutationHolder, *, screen: AppScreen | ExecuteScreen | None = None
    ) -> bool:
        """Take the lock; False when a scheduled run holds the run lock (refusal on `screen`)."""
        # Every caller refuses first; a second take would let one end_mutation
        # release both (C-30), so it is a bug, never a queue.
        if self._mutation_holder is not None:
            raise RuntimeError(f"{self._mutation_holder} already holds the mutation lock")
        if holder in self._CROSS_PROCESS:
            run_lock = runlock.try_acquire(runlock.run_lock_path(), runlock.INSTALLER_JOB)
            if run_lock is None:
                if screen is not None:
                    self._refuse(screen, SCHEDULED_RUN_REFUSAL)
                return False
            self._run_lock = run_lock
        self._mutation_holder = holder
        return True

    def end_mutation(self) -> None:
        if self._run_lock is not None:
            self._run_lock.release()
            self._run_lock = None
        self._mutation_holder = None

    def refuse_if_mutating(
        self, screen: AppScreen | ExecuteScreen, *, cross_process: bool = False
    ) -> bool:
        """Refuse a second mutation while the lock is held: the one template on
        `screen`'s status, true when refused. `cross_process` also refuses while a
        scheduled run holds the run lock; it reads the holder line and never probes the
        flock (a probe could make a starting runner see busy)."""
        if self._mutation_holder is not None:
            self._refuse(screen, MUTATION_REFUSAL.format(holder=self._mutation_holder))
            return True
        if cross_process and runlock.holder(runlock.run_lock_path()) is not None:
            self._refuse(screen, SCHEDULED_RUN_REFUSAL)
            return True
        return False

    @staticmethod
    def _refuse(screen: AppScreen | ExecuteScreen, sentence: str) -> None:
        screen.status.set(sentence, "warn")
        screen.post_message(RefreshRequested())  # SPEC R2: a refusal still ends with one pass


class UnifiedApp(MutationLock, App[list[str] | None]):
    """One app hosting the wizard views. run() returns the catalog selection
    (ids in catalog order) on accept, or None when aborted. `current_view` and
    `catalog` are public for headless tests."""

    ENABLE_COMMAND_PALETTE = False  # replace Textual's dead-ending default palette
    BINDINGS: ClassVar[list[BindingType]] = [
        # ctrl+c is the hard abort: unguarded, so it quits from anywhere — even on
        # top of the NavScreen modal; during a removal the first one waits and a
        # second one exits (D-10, C-26). q is the soft quit: priority so it fires on
        # every view, but guarded (see action_abort) to no-op under the palette.
        Binding("ctrl+c", "hard_abort", "quit", show=False, priority=True),
        Binding("q", "abort", "quit", show=True, priority=True),
        # esc is NOT priority: NavScreen's own escape->cancel must win while the
        # palette is open; elsewhere no screen binds escape, so it bubbles to back.
        Binding("escape", "back", "back", show=True),
        Binding("ctrl+p", "open_nav", "navigate", priority=True),
        *[
            Binding(str(i + 1), f"show('{name}')", name, priority=True)
            for i, name in enumerate(VIEW_ORDER)
        ],
    ]

    def __init__(
        self,
        tools: list[Tool],
        blurbs: Mapping[str, str],
        *,
        report: DoctorReport,
        guard_state: Callable[[], tuple[dict[str, bool], str | None]],
        fix_preview: str | Callable[[], str],
        fix: Callable[[], None],
        uninstall: UninstallInputs,
        policies: PolicyInputs,
        schedules: ScheduleInputs | None = None,
        node_globals: Callable[[], NodeGlobalsReport] | None = None,
        globals_preview: Callable[[NodeGlobalsReport], str] | None = None,
        reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
        unavailable: Mapping[str, bool | UnavailableReason] | None = None,
        initial_view: str = BASE_VIEW,
        schedule_defaults: Callable[[], schedules.ReconcileReport] | None = None,
        version_refresh: VersionRefreshService | None = None,
        updates: UpdateService | None = None,
        execute: ExecuteInputs | None = None,
        prompt_link_mode: bool = False,
        terminal_sync: Callable[[], str | None] | None = None,
        startup_warning: str | None = None,
    ) -> None:
        super().__init__()
        self._staged: set[str] = set()
        self._execute = execute
        self._prompt_link_mode = prompt_link_mode
        self._set_link_mode = policies.set_link_mode
        self._read_link_mode = policies.link_mode
        self._link_mode_prompted = False
        # A first-run pick made while the launch schedule setup held the lock;
        # on_schedule_defaults_applied moves it (C-18).
        self._deferred_link_mode: str | None = None
        # The exit code answers "did everything this session asked for succeed":
        # the latest outcome per tool id wins, so a cancel followed by a retry
        # never leaks an earlier not_attempted. None until the first run finishes.
        self.outcomes: dict[str, RowOutcome] | None = None
        # A crash or a PATH/verify failure that no row outcome carries (L-20-08).
        self.run_errors: list[str] = []
        # WR-06: set by InstallRunStarted (ExecuteScreen.action_start),
        # cleared by on_install_run_finished. A hard abort inside the window
        # exits before the finish message can arrive, so the flag is the only
        # witness that the session was interrupted mid-run -- and the exit
        # code must treat that as a failure, never a clean abort.
        self.run_in_flight: bool = False
        self._version_refresh = version_refresh
        self._updates = updates
        # D-05: one full-catalog pass at a time; a request during a pass sets
        # pending and the finish handler runs exactly one more. Both flags live
        # on the event loop (the worker thread only posts messages).
        self._tools = list(tools)
        self._refresh_running = False
        self._refresh_pending = False
        # Callbacks waiting for the next publication; served once no pass is pending.
        self._publication_waiters: list[Callable[[str | None], None]] = []
        # The app's own state line: (screen, shown text, the text a retraction
        # restores), or (None, line, "") while it waits in _pending_warnings.
        # A clean publish clears only its own line, never one a view wrote.
        self._state_line: tuple[AppScreen | None, str, str] | None = None
        # D-01/15.6-06: the SAME composition-root closure Plans 04/05 wired for
        # Policies' OMZ-plugin apply and the direct `u` update -- called from
        # _install_closed on EVERY close event, never only a selected tool id
        # or a successful outcome. None at every one of the fifteen other
        # UnifiedApp(...) construction sites outside setup.py, matching the
        # default-no-op contract every other optional closure here already has.
        self._terminal_sync = terminal_sync
        # T-15.6-13: a follow-up warning that arrived while no AppScreen was
        # resolvable (current_view names neither a tier nor a registered view)
        # is queued here rather than dropped, and flushed to the next screen
        # that becomes visible (show_view) or the next _install_closed render.
        self._pending_warnings: list[str] = []
        # D-11: a damaged settings.json reaches the first screen through the
        # SAME T-15.6-13 queue as every other warning, never a side channel.
        self._startup_warning = startup_warning
        if startup_warning is not None:
            self._pending_warnings.append(startup_warning)
        # Set by on_install_run_finished when the post-run cache invalidation
        # fails, consumed (and cleared) by the _install_closed that follows:
        # the execute screen is still on top when the failure happens, so
        # there is no catalog status line to write to yet.
        self._invalidate_warning: str | None = None
        # D-04: no tier keeps a presence copy. Each tier renders from the one
        # tool state (`state_of`); a mutation invalidates its epoch, rows read
        # `…`, and the next refresh pass repaints every tier in one swap. So an
        # install close and a view switch only re-enter (`enter_view`); nothing
        # sweeps the presence predicate over the catalog.
        self._catalogs: dict[str, CatalogScreen] = {
            tier.value: CatalogScreen(
                [tool for tool in tools if tool.tier == tier],
                blurbs,
                view=tier.value,
                catalog=list(tools),
                staged=self._staged,
                unavailable=unavailable or {},
                version_refresh=version_refresh,
                updates=updates,
            )
            for tier in Tier
        }
        # Every view, installed on mount and pushed by value (tiers first).
        self._views: dict[str, AppScreen] = dict(self._catalogs)
        # Fifteen UnifiedApp(...) constructions exist outside setup.py. Required
        # kwargs would TypeError at every one of them; those modules are
        # deliberately not edited here. The cost of the default is that a
        # UnifiedApp built without the closures silently reports a healthy set,
        # so setup.py wiring is what makes the feature real in production.
        read_node_globals = (
            node_globals
            if node_globals is not None
            else (lambda: NodeGlobalsReport(entries=(), missing=(), managed=()))
        )

        def _default_preview(report: NodeGlobalsReport) -> str:
            return reinstall_preview(report.managed, known=report.known)

        def _no_reinstall(_packages: Sequence[str]) -> tuple[str, ...]:
            return ()

        read_preview = globals_preview if globals_preview is not None else _default_preview
        run_reinstall = reinstall_globals if reinstall_globals is not None else _no_reinstall
        writer_lines = path_writer_lines_for(report)
        self._views.update(
            {
                "doctor": DoctorScreen(
                    report,
                    guard_state,
                    fix_preview,
                    fix,
                    duplicate_writers=group_writer_lines(writer_lines),
                    writer_lines=writer_lines,
                    rescan_writer_lines=lambda: path_writer_lines_for(report),
                    guard_file=guard_path_writers,
                    node_globals=read_node_globals,
                    globals_preview=read_preview,
                    reinstall_globals=run_reinstall,
                    # Read off PolicyInputs rather than a new UnifiedApp
                    # parameter, on purpose: PolicyInputs already exists to
                    # carry composition-root closures to the screens, and a
                    # parallel kwarg would make every UnifiedApp(...) site in
                    # the tests grow an argument for a value with a home.
                    # PoliciesScreen reads the same field, so one closure
                    # reaches both screens.
                    disk_pressure=policies.disk_pressure,
                    competing=policies.competing,
                    tools=self._tools,
                    version_refresh=version_refresh,
                ),
                "uninstall": UninstallScreen(
                    uninstall, tools=self._tools, version_refresh=version_refresh
                ),
                "policies": PoliciesScreen(policies),
                "schedules": SchedulesScreen(schedules or ScheduleInputs(context=None)),
            }
        )
        self._initial_view = initial_view
        # "" is the root sentinel: on_mount's show_view is never an early return.
        self.current_view = ""
        self._schedule_defaults = schedule_defaults
        # Held from construction whenever a real reconcile callback was wired,
        # so there is no window between __init__ and the worker starting in
        # on_mount where a mutation could slip in (11-REVIEWS.md cycle 2
        # finding #15). on_schedule_defaults_applied releases it.
        if self._schedule_defaults is not None:
            self.begin_mutation(MutationHolder.SCHEDULE_DEFAULTS)
        # True once a quit waits on a running removal: no follow-up pass then.
        self.quitting = False

    # Textual annotates install_screen with a bare (unparameterized) Screen, which
    # pyright-strict reports as partially unknown at the call site. Re-declare it
    # precisely for type checking only — zero runtime cost, no suppression — the
    # same pattern as the UninstallScreen.app narrowing above.
    if TYPE_CHECKING:

        def install_screen(self, screen: Screen[None], name: str) -> None: ...

    async def on_mount(self) -> None:
        # Install every view: an installed screen is SUSPENDED when popped; an
        # uninstalled one is REMOVED (App._replace_screen) and re-pushing it
        # re-composes onto stale state, dropping later keys in a fast burst. The
        # empty default screen is the neutral root under all of them.
        for name, screen in self._views.items():
            self.install_screen(screen, name)
        await self.show_view(self._initial_view)
        if self._schedule_defaults is not None:
            self._apply_schedule_defaults_worker()
        # Last in on_mount so a first-run user answers exactly one question;
        # the schedule worker's completion status lands behind this picker, not
        # on top of it.
        if (
            self._prompt_link_mode
            and self._set_link_mode is not None
            and not self._link_mode_prompted
        ):
            self._link_mode_prompted = True
            self.push_screen(LinkModeScreen(), self._first_link_mode_picked)
        self.request_refresh()  # the launch pass

    def request_refresh(self) -> None:
        """Run one full-catalog refresh pass, or queue exactly one more behind
        the running one (D-05). No service: nothing to refresh."""
        if self._version_refresh is None:
            return
        if self._refresh_running:
            self._refresh_pending = True
            return
        self._refresh_running = True
        self._refresh_worker()

    def await_publication(self, callback: Callable[[str | None], None]) -> None:
        """Call `callback(error)` once a pass has finished with none pending: a
        running pass is joined, otherwise one starts. No service: answer at once."""
        if self._version_refresh is None:
            callback(None)
            return
        self._publication_waiters.append(callback)
        if not self._refresh_running:
            self.request_refresh()

    @work(thread=True, exclusive=True, group="full-catalog-refresh", exit_on_error=False)
    def _refresh_worker(self) -> None:
        service = self._version_refresh
        pass_error: str | None = "state check did not complete"
        try:
            if service is not None:
                _result, error = run_live(lambda: service.refresh(self._tools))
                self.post_message(
                    RefreshPublished(error, service.warning if error is None else None)
                )
                pass_error = error
        except Exception as exc:
            pass_error = first_line(exc)
            # The one status path: an unexpected failure shows the retry copy too.
            self.post_message(RefreshPublished(pass_error, None))
        finally:
            self.post_message(RefreshFinished(pass_error))

    def on_refresh_published(self, message: RefreshPublished) -> None:
        self._render_published()
        line: str | None = None
        if message.error is not None:
            line = f"tool state check failed: {message.error} — the next change retries it"
        elif message.warning is not None:
            line = f"{message.warning} — marks are current; the next start checks again"
        self._write_state_line(line)

    def on_refresh_finished(self, message: RefreshFinished) -> None:
        self._refresh_running = False
        pending, self._refresh_pending = self._refresh_pending, False
        # A shutdown or a quit in progress drops the queued pass; waiters still hear.
        if pending and self.is_running and not self.quitting:
            self.request_refresh()
            return
        waiters, self._publication_waiters = self._publication_waiters, []
        for waiter in waiters:
            waiter(message.error)

    def _render_published(self) -> None:
        """Re-render the visible view only (D-06); a view under a modal renders
        the published state when the modal closes (`AppScreen.on_screen_resume`)."""
        screen = self._visible_app_screen()
        if screen is not None:
            screen.state_refreshed()

    def unstage(self, ids: Iterable[str]) -> None:
        """Drop removed tools from the tiers' shared selection (in place: the
        tier browsers hold this set)."""
        self._staged.difference_update(ids)

    def show_result(
        self,
        origin: AppScreen,
        text: str,
        severity: Severity | str,
        *,
        elsewhere: str | None = None,
    ) -> None:
        """Write a mutation's result where the user is looking (C-28): on the
        current view, which is `origin` unless the user left it meanwhile.
        `elsewhere` replaces `text` on another view when `text` names a key
        only `origin` handles."""
        screen = self._views.get(self.current_view, origin)
        if elsewhere is not None and screen is not origin:
            text = elsewhere
        screen.status.set(text, severity)

    def _write_state_line(self, line: str | None) -> None:
        """Replace the app's previous state line with `line` (None: retract it).
        It is written over an empty status only; a status another writer left
        stands, and the line waits in _pending_warnings for the next entry."""
        previous, self._state_line = self._state_line, None
        if previous is not None:
            where, shown, rest = previous
            if where is None:
                if shown in self._pending_warnings:
                    self._pending_warnings.remove(shown)
            elif where.status.text == shown:
                if rest:
                    where.status.set(rest, "warn")
                else:
                    where.status.clear()
        if line is None:
            return
        screen = self._visible_app_screen()
        if screen is None or screen.status.text:
            if line not in self._pending_warnings:
                self._pending_warnings.append(line)
            self._state_line = (None, line, "")
            return
        # Plain text through StatusLine.set, never markup (T-19-40).
        screen.status.set(line, "warn")
        self._state_line = (screen, line, "")

    # exit_on_error=False (Textual's own worker.py defaults this True, which
    # calls App._handle_exception -- crashing the whole app -- on any
    # exception a threaded worker raises): an exception from the reconcile must
    # still leave a usable, running app (the finally block below already
    # guarantees the lock releases); Worker.state/.error still record
    # it for diagnosis, this only suppresses the exit-the-app side effect.
    @work(thread=True, exclusive=True, group="schedule-defaults", exit_on_error=False)
    def _apply_schedule_defaults_worker(self) -> None:
        """Turn on the schedules nobody has decided about, off the event loop.

        Mirrors DoctorScreen._audit_globals_worker/_reinstall_globals_worker's
        own thread-worker + post_message shape, for the identical reason: a
        real systemctl or launchctl call (run_captured's underlying
        subprocess.run has no timeout) must never freeze frame rendering or
        keypress handling. The body is wrapped in try/finally so the
        completion message is ALWAYS posted -- regardless of whether
        self._schedule_defaults() returns normally or raises ANYTHING -- so the
        app mutation lock the constructor (or the install run's end) took can
        never stay held (11-REVIEWS.md cycle 3 finding #15). An exception
        raised inside the try still propagates normally after the finally runs
        and is recorded on the Worker itself (state=ERROR, .error);
        exit_on_error=False is what keeps that from also crashing the app, so
        this only ever ADDS the guaranteed message post, it never swallows or
        hides a genuine bug.
        """
        report = schedules.ReconcileReport()
        try:
            if self._schedule_defaults is not None:
                report = self._schedule_defaults()
        finally:
            self.post_message(ScheduleDefaultsApplied(report))

    def on_schedule_defaults_applied(self, message: ScheduleDefaultsApplied) -> None:
        # Released FIRST, unconditionally: the worker posts this on every
        # outcome, so a crash never leaves the lock held.
        self.end_mutation()
        lines = schedules.reconcile_lines(message.report)
        if lines:
            severity = "warn" if any(kind == "warn" for _text, kind in lines) else "ok"
            self._announce_startup_line(" · ".join(text for text, _kind in lines), severity)
        # The reconcile changes the rows Schedules shows and the tweak rows the
        # Uninstall view lists: repaint whichever view is up, without a pass.
        schedules_screen = self._views.get("schedules")
        if isinstance(schedules_screen, SchedulesScreen) and schedules_screen.is_mounted:
            schedules_screen.state_refreshed()
        if self._visible_app_screen() is not schedules_screen:
            self._render_published()
        value, self._deferred_link_mode = self._deferred_link_mode, None
        if value is not None:
            self._move_first_link_mode(value, self._views.get(self.current_view, self.catalog))

    def _announce_startup_line(self, text: str, severity: Severity | str) -> None:
        """The reconcile's lines ride the startup-warning path: over an empty status of the
        visible view, else queued for the next view that becomes visible (T-15.6-13)."""
        screen = self._visible_app_screen()
        if screen is None or screen.status.text:
            self._pending_warnings.append(text)
            return
        screen.status.set(text, severity)

    @property
    def catalog(self) -> CatalogScreen:
        """The base (first-registered tier) screen."""
        return self._catalogs[BASE_VIEW]

    def catalog_for(self, view: str) -> CatalogScreen:
        """Headless-test seam for the two non-base tier screens."""
        return self._catalogs[view]

    def view(self, name: str) -> AppScreen:
        """Headless-test seam: the installed screen for any of the six views."""
        return self._views[name]

    async def show_view(self, name: str) -> None:
        # Await each stack mutation so a transition fully settles before the next
        # runs: the stack stays [root, <one view>].
        if name == self.current_view:
            return
        # This is the one navigation path (.claude/architecture.md rule 2), so it
        # is the only correct place to end the leaving view's transient state.
        leaving = self._views.get(self.current_view)
        if leaving is not None:
            leaving.clear_transient()
            await self.pop_screen()
        target = self._views[name]
        await self.push_screen(target)
        self.current_view = name
        # Flush before entry: a status written by enter_view wins over a queued
        # warning. T-15.6-13: also where an early warning is finally delivered.
        self._flush_pending_warnings(target)
        target.enter_view()

    def _flush_pending_warnings(self, screen: AppScreen, extra: Sequence[str] = ()) -> None:
        """Write the queued warnings (and `extra`) on one line of `screen`. A
        queued state line moves with them, so a clean publish still retracts it
        (RR-02), leaving the other warnings standing."""
        parts = [*self._pending_warnings, *extra]
        self._pending_warnings = []
        if not parts:
            return
        text = " · ".join(parts)
        screen.status.set(text, "warn")
        if self._state_line is not None and self._state_line[0] is None:
            line = self._state_line[1]
            if line in parts:
                rest = " · ".join(part for part in parts if part != line)
                self._state_line = (screen, text, rest)

    def _navigable(self) -> bool:
        # ctrl+p and the number keys are priority App bindings, so they fire even
        # while a NavScreen modal is open. Navigate only when a view is the active
        # screen, never on top of the palette (it would break the stack invariant).
        return self.screen in self._views.values()

    async def action_show(self, name: str) -> None:
        if not self._navigable():
            return
        await self.show_view(name)

    async def on_wayfinding_header_navigate(self, event: WayfindingHeader.Navigate) -> None:
        event.stop()
        if self._navigable():
            await self.show_view(event.view)

    async def action_back(self) -> None:
        # One-deep stack: from a pushed view, esc goes home to the catalog; on the
        # catalog itself there is nowhere further back, so esc is inert. async to
        # match App.action_back's signature (pyright-strict rejects a sync override).
        if self._navigable() and self.current_view != BASE_VIEW:
            await self.show_view(BASE_VIEW)

    def action_open_nav(self) -> None:
        if not self._navigable():
            return
        self.push_screen(NavScreen(), self._navigate)

    async def _navigate(self, name: str | None) -> None:
        # Textual awaits async screen-result callbacks: textual/screen.py:83 defines
        # ScreenResultCallbackType as a Union including Callable[[Optional[T]], Awaitable[None]],
        # and textual/_callback.py's invoke does `if isawaitable(result): result = await result`.
        # Using async here means the pilot awaits this callback fully before resuming, so
        # palette tests asserting current_view immediately after enter do not need pilot.pause().
        if name is not None:
            await self.show_view(name)

    def _first_link_mode_picked(self, value: str | None) -> None:
        # make fix opens with initial_view="doctor", so the Doctor AppScreen is
        # on top and the catalog is hidden. Write D-05.3's explanation onto
        # the screen the user is looking at, never a hard catalog fallback:
        # if a future Textual version fired this callback while LinkModeScreen
        # were still current, self.screen would not be an AppScreen and a hard
        # catalog fallback would reintroduce the silent-dismissal defect.
        current = self.screen
        target = (
            current
            if isinstance(current, AppScreen)
            else (self._views.get(self.current_view) or self.catalog)
        )
        if value is None:
            mode = self._read_link_mode() if self._read_link_mode is not None else "centralized"
            policies_key = str(VIEW_ORDER.index("policies") + 1)
            unchanged = (
                f"Link mode unchanged; this run uses {mode}. "
                f"Press {policies_key} then m to change it later."
            )
            # D-11: dismissing the one first-run question must not erase the
            # only notice that the settings file was ignored. Same separator
            # _flush_pending_warnings uses.
            if self._startup_warning is not None:
                unchanged = f"{self._startup_warning} · {unchanged}"
            target.status.set(unchanged, "warn")
            return
        if self._set_link_mode is None:
            return
        # C-18: the launch daemon apply rewrites ~/.myshellrc as the move does,
        # so the pick waits for it instead of making the user answer again. It
        # is the only holder possible here: the picker opens at launch.
        if self.mutation_in_flight:
            self._deferred_link_mode = value
            # The move's own status replaces this line once the apply ends.
            target.status.set(
                f"Link mode {value} will be saved when the background apply finishes.", "warn"
            )
            return
        self._move_first_link_mode(value, target)

    def _move_first_link_mode(self, value: str, target: AppScreen) -> None:
        setter = self._set_link_mode
        if setter is None:
            return
        policies_screen = self._views.get("policies")
        aware_active = (
            policies_screen.link_mode_aware_active()
            if isinstance(policies_screen, PoliciesScreen)
            else []
        )
        old = self._read_link_mode() if self._read_link_mode is not None else "centralized"
        report, error = run_live(lambda: move_link_mode(aware_active, value, setter, old_mode=old))
        if error is not None:
            policies_screen = self._views.get("policies")
            if isinstance(policies_screen, PoliciesScreen):
                policies_screen.mark_lost_policies_off(error)
            target.status.set(error, "error")
            return
        text, severity = _link_mode_status(value, report or (), old_mode=old)
        target.status.set(text, severity)
        if isinstance(target, DoctorScreen) and self._visible_app_screen() is target:
            target.enter_view()  # the status survives: enter_view writes none

    def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
        if self._execute is None or message.result is None:
            self.exit(message.result)
            return
        self.push_screen(ExecuteScreen(message.result, self._execute), self._install_closed)

    def _install_closed(self, result: list[RowOutcome] | None) -> None:
        # Only the rows that still need the user stay selected (D-10, L-20-07).
        # intersection_update, never a rebind: the tier browsers hold this set.
        # None (closed before a run) leaves the selection untouched.
        if result is not None:
            self._staged.intersection_update(retained(result))
        # ExecuteScreen is modal: _navigable() returns False while it is on
        # top, so current_view still names the catalog tier the run was
        # launched from, and _catalogs has an entry for every tier including
        # the base one -- no base/non-base branch needed here, unlike
        # show_view (that method branches because it pushes/pops screens;
        # this callback does neither). Presence is re-read by the refresh pass
        # `request_refresh` starts below, never swept here (D-04, see __init__).
        warnings: list[str] = []
        # D-01/15.6-06 Task 1: the shared terminal synchronizer runs after a
        # close event that actually changed installed-tool state -- never
        # only a selected tool id (WR-07: merely opening and dismissing the
        # Execute screen with nothing selected/changed otherwise rewrote
        # kitty.conf, created a brand-new wezterm.lua (CR-03), and wrote
        # konsolerc for a session that installed nothing). The zsh-removal
        # revert case is independently covered by
        # UninstallScreen.on_removal_finished and _run_uninstall, so this gate
        # does not lose coverage for that scenario. Through run_live like
        # every other live core read this callback triggers (rule 3): an
        # OSError is a secondary, non-fatal warning and must never flip an
        # already-recorded run into a reported failure.
        # WR-03: not run_live -- terminal_sync_warning IS this seam's live
        # guard, and routing through both produced the one message whose
        # casing had already drifted from the other four call sites.
        # D-11: the gate is "a row actually ran", so an update counts too.
        if result is not None and ran_anything(result):
            sync_warning = terminal_sync_warning(self._terminal_sync)
            if sync_warning:
                warnings.append(sync_warning)
        # A .get(), not an index: _catalogs is keyed by tier only
        # (system/user/ai) while current_view ranges over all six VIEWS
        # (doctor, uninstall and policies included). Only a catalog tier
        # pushes ExecuteScreen today, but that is one call site's behaviour
        # rather than an enforced invariant -- nothing structurally stops a
        # future caller pushing it with this callback from the uninstall or
        # doctor view -- and a KeyError raised inside a Textual screen-result
        # callback takes the message pump down instead of degrading. No
        # catalog on top means the warnings go to the visible view below.
        active = self._catalogs.get(self.current_view)
        # The revealed view renders itself on resume (C-08); ask for the pass
        # that publishes what the run changed (A11: only if it ran something).
        if result is not None and ran_anything(result):
            self.request_refresh()
        # Both post-run failures land on one line, written after the re-render.
        if self._invalidate_warning is not None:
            warnings.append(self._invalidate_warning)
            self._invalidate_warning = None
        # WR-08: also checks _pending_warnings, not just this close's own
        # `warnings` -- __init__'s own documented contract is that a queued
        # warning flushes on "the next _install_closed render", but a close
        # that produces no NEW warning of its own used to return here before
        # ever reaching the drain below, so a previously-queued warning was
        # never actually delivered by this path -- only a subsequent
        # show_view navigation flushed it.
        if not warnings and not self._pending_warnings:
            return
        # T-15.6-13: render on WHICHEVER AppScreen is actually visible right
        # now -- a catalog tier (active, above) or the Doctor/Uninstall/
        # Policies screen the run was launched over -- never dropped merely
        # because current_view names a non-tier key. Only when no AppScreen
        # is resolvable at all (not reachable in the current call graph) does
        # the warning queue for the next screen that becomes visible.
        visible = active if active is not None else self._visible_app_screen()
        if visible is None:
            self._pending_warnings.extend(warnings)
            return
        self._flush_pending_warnings(visible, warnings)

    def _visible_app_screen(self) -> AppScreen | None:
        # Before mount there is no stack; during shutdown the app stops running
        # before it prunes the screens, and a late pass must not render into them.
        if not self.screen_stack or not self.is_running:
            return None
        screen = self.screen
        return screen if isinstance(screen, AppScreen) else None

    def on_install_run_started(self, message: InstallRunStarted) -> None:
        del message  # its arrival is its whole meaning
        # run_in_flight stays the exit-code witness; the lock is the mutation guard,
        # taken by ExecuteScreen._begin_run before the run starts.
        self.run_in_flight = True

    def on_install_run_finished(self, message: InstallRunFinished) -> None:
        self.end_mutation()
        self.run_in_flight = False
        # SPEC edge R3: a tool this run just installed gets its update schedule in the same
        # session. Taken after the run's own end_mutation, released by the worker's message.
        if self._schedule_defaults is not None:
            self.begin_mutation(MutationHolder.SCHEDULE_DEFAULTS)
            self._apply_schedule_defaults_worker()
        # Every mutation this app performs calls invalidate
        # (installer/version_status.py:26-30's own invariant); the install
        # path was the one mutation that skipped it, so a tool the run just
        # handed to brew/cask/pnpm/uv was resolved against a manager
        # inventory read BEFORE the run for up to MANAGER_STALE_AFTER (6h).
        # Mirrors UpdateService's own call (installer/update.py:436-443) in
        # BOTH directions, which is the whole point of the try/except: a
        # cache-write failure is a post-mutation side effect and must never
        # flip an already-recorded run into a reported failure, AND it is
        # never swallowed. UpdateService folds the failure into
        # outcome.detail; this folds it into the status line the next
        # _install_closed writes, because a silently discarded invalidate
        # means the manager-snapshot staleness this call exists to close
        # comes back for up to MANAGER_STALE_AFTER with nothing on screen.
        # It is also the only thing standing between a future signature
        # change to invalidate() and a feature that quietly stops working.
        #
        # The message is held rather than shown here: ExecuteScreen is still
        # on top at this point (InstallRunFinished is posted from
        # _execute_worker's finally, before the user closes the screen), so
        # the first moment a catalog status line is visible again is the
        # close callback.
        if self._version_refresh is not None and ran_anything(message.outcomes):
            try:
                self._version_refresh.invalidate(reason="install run finished")
            except Exception as exc:  # noqa: BLE001 -- post-mutation side effect, reported below
                self._invalidate_warning = f"version cache invalidation failed: {exc}"
        for outcome in message.outcomes:
            self._record(outcome)
        if ran_anything(message.outcomes) or message.run_error:
            self.run_errors = [
                error
                for error in (message.run_error, message.path_error, message.verify_error)
                if error
            ]

    def on_tool_updated(self, message: ToolUpdated) -> None:
        """opencode H3: a failed DIRECT update (a `u` press on the catalog)
        never reaches an ExecuteScreen, so nothing else would record it and
        the process would exit 0 after a failed update. The failure is folded
        here as a plan-shaped outcome, so _session_exit_code needs no second
        rule. Successful updates record `done`, allowing latest-wins to clear
        an earlier failure; unknown-owner/unsupported refusals record nothing."""
        self.end_mutation()
        failed = message.error is not None or (
            message.outcome is not None and message.outcome.status == "failed"
        )
        if failed:
            detail = message.error or (
                message.outcome.detail if message.outcome is not None else ""
            )
            row = PlanRow(message.tool_id, Disposition.UPDATE, "")
            self._record(RowOutcome(row, "failed", detail=detail))
        elif message.outcome is not None and message.outcome.status == "updated":
            row = PlanRow(message.tool_id, Disposition.UPDATE, "")
            self._record(RowOutcome(row, "done"))
        self._render_published()
        # An update that ran and failed may still have changed the machine.
        self.request_refresh()

    def _record(self, outcome: RowOutcome) -> None:
        """Latest outcome per tool id wins (cancel-then-retry, D-09)."""
        if self.outcomes is None:
            self.outcomes = {}
        self.outcomes[outcome.row.tool_id] = outcome

    def on_refresh_requested(self, message: RefreshRequested) -> None:
        """A refused mutation still ends with one pass (SPEC R2)."""
        del message  # payload-free
        self.request_refresh()

    def action_abort(self) -> None:
        # The soft quit (q). Guarded so a priority q binding does not quit out from
        # under the NavScreen palette; ctrl+c (action_hard_abort) stays unguarded.
        if not self._navigable():
            return
        self._quit()

    async def action_quit(self) -> None:
        # Textual's inherited ctrl+q calls exit() directly, which would abandon a
        # removal's daemon delete thread (RR-01); it is the soft quit, like q.
        self.action_abort()

    def action_hard_abort(self) -> None:
        # The hard quit (ctrl+c): exits from anywhere, including on top of the
        # palette. The first one during a removal waits for it; a second one
        # stops waiting and says the removal may be partial (D-10, C-26).
        if self.quitting and self._mutation_holder is MutationHolder.REMOVAL:
            self.exit(None, message=_REMOVAL_QUIT_CUT)
            return
        self._quit()

    def _quit(self) -> None:
        if self._mutation_holder is MutationHolder.REMOVAL:
            self._exit_after_removal()
        else:
            self.exit(None)

    def _exit_after_removal(self) -> None:
        """Never cut a delete: say so, then exit once the removal worker returns.
        With a modal on top the copy is queued for the next visible view. The wait
        runs on its own worker, so the key handler returns at once and a shutdown
        cancels the wait instead of hanging on it."""
        self.quitting = True
        screen = self._visible_app_screen()
        if screen is not None:
            screen.status.set(_REMOVAL_QUIT_WAIT, "warn")
        else:
            self._pending_warnings.append(_REMOVAL_QUIT_WAIT)
        removals = [w for w in self.workers if w.group == "uninstall-removal"]
        self.run_worker(self._exit_when_done(removals), group="quit-wait", exit_on_error=False)

    async def _exit_when_done(self, removals: Sequence[Worker[None]]) -> None:
        for worker in removals:
            with contextlib.suppress(WorkerFailed, WorkerCancelled):
                await worker.wait()
        self.exit(None)
