"""Unified Textual shell hosting the wizard views behind one app.

The app owns navigation and the screen stack. The base view, doctor, uninstall,
and policies are all functional views. Execution stays behind the pure
`installer/` core invoked from `setup.py`, with one deliberate exception: the
doctor, uninstall, and policies views apply their changes live through
injected closures. The app's run value stays the catalog decision
(`list[str] | None`).

The first registered view is the base screen (`get_default_screen`); it cannot
be switched out. Navigation is therefore a stack with the base view at the
bottom: the stack is always `[base]` or `[base, <one other view>]`.
"""

import contextlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from installer import daemon, env_redirect
from installer.app import UninstallDecision, path_writer_lines_for
from installer.catalog_tui import CatalogScreen, OwnershipRefreshed
from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport
from installer.enums import Tier, UninstallState
from installer.execute_screen import ExecuteInputs, ExecuteScreen, InstallRunFinished
from installer.guidance import (
    GUARD_ENTER_HINT,
    SAFE_FIX_ENTER_HINT,
    Guidance,
    competing_mechanism_guidance,
    disk_pressure_guidance,
    doctor_guidance,
    guard_guidance,
    node_globals_guidance,
)
from installer.model import Tool
from installer.pnpm_globals import NodeGlobalsReport, reinstall_preview
from installer.policy import Policy, PolicyMove, PolicyResult, move_link_mode
from installer.rcclean import PathWriterLine, group_writer_lines
from installer.render import guidance_text
from installer.resolve import UnavailableReason
from installer.run import CommandError
from installer.session import Summary, fold_run
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
from installer.uninstall import SweepResult, ToolRow
from installer.update import UpdateService
from installer.version_status import VersionRefreshService


@dataclass(frozen=True)
class UninstallInputs:
    """Everything the UninstallScreen needs: every classified tool (catalog
    parity, not just the removable ones), the active ban names, whether a managed
    PATH block exists, the active shell-tweak ids, the live removal closure bound
    by the composition root, and an optional post-removal invalidate seam.

    All four of `rows`/`ban_names`/`has_path_block`/`tweak_ids` are PREDICATES,
    not their results, for the same reason: each is mutated live by another view
    in the same process (or, for `rows`, by this screen's own removal action).
    `rows` used to be documented as a safe snapshot on the claim that nothing
    installs or removes a tool while the app runs -- that claim became false the
    moment Phase 13 shipped live in-TUI install execution, and a frozen list is
    exactly the stale-snapshot failure the other three fields already guard
    against: the Policies view writes the ban's shims and aliases and toggles
    the tweaks, the Doctor view writes the very managed PATH block
    `has_path_block` detects, and an install or removal performed anywhere in
    the session changes what `rows` should return next. A value frozen at
    construction goes stale the moment the user does -- stale-False leaves the
    lever for something they just enabled/installed unreachable, and stale-True
    offers a lever that removes nothing while the summary claims it did.
    `UninstallScreen._resync` re-evaluates all four on every entry and on every
    completed background ownership refresh.

    `rows` is deliberately typed as strictly a callable rather than
    `list[ToolRow] | Callable[[], list[ToolRow]]`: a union would keep the
    stale-snapshot shape representable and type-checkable forever, so the next
    construction site would get to reintroduce exactly the bug this migration
    removes. Migrating every existing construction site once is cheaper than a
    permanently ambiguous field (Round-1 review HIGH)."""

    rows: Callable[[], list[ToolRow]]
    ban_names: Callable[[], list[str]]
    has_path_block: Callable[[], bool]
    remove: Callable[[UninstallDecision], SweepResult]
    tweak_ids: Callable[[], tuple[str, ...]] = tuple
    invalidate: Callable[[], Any] | None = None
    # WR-01 (15.4-REVIEW.md): the pass that REPLACES what `invalidate` drops.
    # Without it, `_apply_removal`'s invalidate degraded every managed row's
    # attribution to the generic registry phrase with nothing on this screen
    # able to restore it: `OwnershipRefreshed` is posted only from
    # `CatalogScreen`, so a user who went Uninstall -> remove -> Policies ->
    # Uninstall never visited a catalog tab and saw generic phrases for the
    # rest of the session. BLOCKING when called -- `_apply_removal` runs it
    # on a thread worker, never on the message loop.
    refresh: Callable[[], Any] | None = None
    # D-01/15.6-06 Task 3: the SAME composition-root closure Policies, the
    # direct `u` update, unattended installation, the CLI uninstall route,
    # and interactive ExecuteScreen close already reuse. Called from
    # `_apply_removal` only after `remove` reports a successful sweep, so a
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
_DISK_PRESSURE_ENABLE_PREFIX = "Enable the background cleanup policy"
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
_DISK_PRESSURE_TUI_PREFIX = "Open the Policies view and turn on the Background tmpdir cleanup row;"


class GlobalsReinstalled(Message):
    """The threaded pnpm-globals reinstall finished; `error` is None on success.

    post_message is Textual's thread-safe hand-off back to the event loop, so
    the worker never touches a widget from its own thread.
    """

    def __init__(self, error: str | None) -> None:
        self.error = error
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


class _BodyStatic(Static):
    """Static with a small public render seam for headless tests."""

    @property
    def renderable(self) -> Any:
        return self.render()


class DoctorScreen(AppScreen):
    """PATH audit and safe PATH repair in one view."""

    # Narrow .app from App[Unknown] (MessagePump default) so push_screen is typed.
    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "apply", "apply", show=True),
        Binding("a", "apply", "apply", show=False),
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
    ) -> None:
        super().__init__(view="doctor")
        self._report = report
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
        # Bumped every time an audit worker is actually started; carried on
        # its GlobalsAudited message so a superseded worker's result (one
        # started before a newer request, still running when the newer one
        # lands) is recognisably stale and discarded rather than clobbering
        # fresher state.
        self._globals_audit_generation = 0

    def compose_body(self) -> ComposeResult:
        yield _BodyStatic(id="doctor-body")

    def on_mount(self) -> None:
        self._refresh_guidance()
        self._refresh_body()
        self._start_globals_audit()
        self._start_disk_probe()

    def enter_view(self) -> None:
        """Re-read the ban state on every entry, and re-ask pnpm off the loop.

        Installed screens are suspended, not unmounted, so `on_mount` fires once
        for the life of the app: without this, Policies → toggle the ban →
        Doctor reports the state from before the toggle. The globals audit needs
        the same freshness but cannot be taken here synchronously, so it is
        started as a worker and rendered when it lands.

        The audit is not started on the first entry: this runs BEFORE the screen
        is pushed, and `on_mount` starts it a moment later.
        """
        self._refresh_guidance()
        if self.is_mounted:
            self._refresh_body()
            self._start_globals_audit()
            self._start_disk_probe()

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
        self.globals_auditing = True
        self._audit_globals_worker(self._globals_audit_generation)

    def _refresh_guidance(self) -> None:
        # IO-free by construction: the globals half reads the last audited
        # report, never the closure that would spawn `pnpm list -g --json`.
        # Before the first audit lands there is nothing to say about the
        # globals, which is honest — node_globals_guidance only ever speaks
        # about a set it has seen.
        status, warning = self._guard_state()
        globals_report = self._globals_report
        # Position is a decision, pinned by a test: disk pressure follows the
        # guard items and precedes the pnpm-globals items.
        self.guidance = (
            doctor_guidance(self._report, self._duplicate_writers, self._writer_lines)
            + guard_guidance(status, warning)
            + self._disk_pressure_items()
            + self._competing_items()
            + (node_globals_guidance(globals_report) if globals_report is not None else [])
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
        body = self.query_one("#doctor-body", _BodyStatic)
        text = Text()
        text.append("PATH Doctor\n", style="bold")
        text.append("Audit\n", style="bold")
        text.append(guidance_text(self._tui_guidance()))
        text.append("\n\nSafe fix preview\n", style="bold")
        text.append(self._fix_preview())
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
        body.update(text)

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
                # Ordering is load-bearing: this branch must stay BEFORE the
                # generic `Run `make setup`` branch below, or a later edit to
                # the console wording could let that prefix capture this item
                # and answer a full disk with pnpm-reinstall advice.
                tail = item.next_step[len(_DISK_PRESSURE_ENABLE_PREFIX) :]
                tail = tail.split(";", 1)[1].strip() if ";" in tail else tail.strip()
                rewritten.append(replace(item, next_step=f"{_DISK_PRESSURE_TUI_PREFIX} {tail}"))
            elif item.next_step.startswith("Run `make setup`"):
                rewritten.append(
                    replace(
                        item,
                        next_step="Press r to reinstall the pnpm-managed global set.",
                    )
                )
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
            return
        rescan = self._rescan_writer_lines
        self._adopt_writer_lines(rescan() if rescan is not None else self._writer_lines)
        self._pending_guards = self._guardable_files()
        if not self._pending_guards:
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
        self._refresh_guidance()
        self._refresh_body()

    def action_reinstall_globals(self) -> None:
        # globals_done needs no message: the body already renders the success
        # line, so a repeat press is answered by what is on screen.
        if self.globals_done or self.globals_running:
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
            return
        if not report.managed:
            self.globals_note = _NOTHING_TO_REINSTALL
            self._refresh_body()
            return
        self.globals_note = None
        self.globals_running = True
        self._refresh_body()
        # The package list is passed in rather than re-derived inside the
        # worker: re-deriving would put `pnpm list -g --json` on a second
        # thread, and the set the user consented to is the one on screen.
        self._reinstall_globals_worker(report.managed)

    # Distinct groups: `exclusive` cancels within a group, so leaving both
    # workers in the default one would let a reinstall cancel an in-flight
    # audit and vice versa.
    @work(thread=True, exclusive=True, group="globals-reinstall")
    def _reinstall_globals_worker(self, packages: tuple[str, ...]) -> None:
        """Run the reinstall off the event loop, then hand the outcome back to it.

        A synchronous subprocess here would freeze every frame for the length of
        a `pnpm add -g`. Widgets may only be touched from the app's own thread,
        hence a posted message rather than a direct refresh.
        """
        _, error = run_live(lambda: self._reinstall_globals(packages))
        self.post_message(GlobalsReinstalled(error))

    @work(thread=True, exclusive=True, group="globals-audit")
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
        outcome, error = run_live(self._audit_globals)
        if outcome is None:
            report, preview = _GLOBALS_UNREADABLE, _GLOBALS_UNREADABLE_PREVIEW
        else:
            report, preview = outcome
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

    def on_globals_reinstalled(self, message: GlobalsReinstalled) -> None:
        self.globals_running = False
        self.globals_error = message.error
        self.globals_done = message.error is None
        self._refresh_body()
        # The globals audit is a live `shutil.which` probe whose answer this
        # action just tried to change — unlike the PATH audit, which is a
        # deliberate snapshot. Without this the screen renders "mmdc went
        # missing" directly above "pnpm globals reinstalled." Re-asking is a
        # subprocess, so it goes back through the worker rather than being
        # taken inline here, where it would block the loop twice over.
        self._start_globals_audit()


@dataclass(frozen=True)
class _UninstallEntry:
    """A browsable uninstall row: either a classified tool or an environment
    pseudo-row (the pip/npm ban, the managed PATH block, or the shell tweaks).

    `key` is the stable id (a tool id, or "#ban"/"#path-block"/"#tweaks"). `cells`
    are the pre-rendered columns. `selectable` gates toggling (removable tools and
    the env rows are selectable; managed/absent/unavailable tools are not).
    `detail` is the detail-bar line. `paths` are the tool's removable artifacts
    (empty for env rows). `is_ban`/`is_path_block`/`is_tweaks` flag the env rows
    so a selection maps back to the UninstallDecision levers."""

    key: str
    cells: list[Text]
    selectable: bool
    detail: str
    paths: tuple[Path, ...]
    is_ban: bool
    is_path_block: bool
    is_tweaks: bool = False


# Section titles per state, in display order. The "environment" section holds the
# ban/PATH pseudo-rows.
_STATE_TITLES: tuple[tuple[UninstallState, str], ...] = (
    (UninstallState.REMOVABLE, "removable here"),
    (UninstallState.MANAGED, "managed elsewhere"),
    (UninstallState.ABSENT, "not installed"),
    (UninstallState.UNAVAILABLE, "not available"),
)
_BAN_KEY = "#ban"
_BLOCK_KEY = "#path-block"
_TWEAK_KEY = "#tweaks"
_ENV_KEYS = (_BAN_KEY, _BLOCK_KEY, _TWEAK_KEY)

# The "Installed via" cell's three non-attributed labels (CR-03). The first
# two are byte-identical to the pre-15.4-05 enum's values for the same two
# cases, so this column's width budget is the one it was designed with; only
# an ATTRIBUTED managed row now reads differently, which is the whole of what
# D-03 asked for. See `_tool_entry` for why the cell is a label and not the
# hint.
_VIA_USERSPACE = "userspace"
_VIA_UNATTRIBUTED = "package manager"
_VIA_NONE = "—"


def _has_daemon_id(ids: tuple[str, ...]) -> bool:
    """True when any id in ids is the background daemon's own namespaced id.

    Mirrors `installer.app._has_daemon_id` exactly: a tiny, named predicate
    rather than an inline generator expression repeated at every daemon-aware
    copy call site (preview row + success summary), keeping both byte-for-byte
    consistent with each other and with the CLI's own equivalent wording.
    """
    return any(policy_id.startswith("daemon:") for policy_id in ids)


class UninstallScreen(AppScreen):
    """Full catalog-parity uninstall browser. Every tool is listed with its
    removability state; only removable tools (and the env rows) toggle. Enter
    removes exactly the selected artifacts + env levers, applied live."""

    # Narrow .app from App[Unknown] (MessagePump default) to the concrete host
    # app so push_screen() is typed without an Unknown generic param.
    # UnifiedApp is defined later in this module; the string forward reference is
    # resolved by pyright (which analyses all module-level names together).
    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    def __init__(self, inputs: UninstallInputs) -> None:
        super().__init__(view="uninstall", accent="red")
        self._rows_predicate = inputs.rows
        self._ban_names_of = inputs.ban_names
        self._has_path_block_of = inputs.has_path_block
        self._tweak_ids_of = inputs.tweak_ids
        self._invalidate = inputs.invalidate
        self._refresh = inputs.refresh
        # Evaluated THROUGH run_live (.claude/architecture.md rule 3), not
        # bare: construction happens outside the nav path `enter_view` guards,
        # so a bare call would let an OSError from the per-tool filesystem
        # reads escape before any screen or status line exists to report it
        # (Round-1 review MEDIUM). On failure the screen still constructs,
        # with an empty row list and the message stashed on
        # `self._startup_error`; the first `enter_view`/`_resync` surfaces it
        # as a one-time warn status and the empty list makes that same entry's
        # comparison differ from a real reading, so the screen self-heals on
        # its first display rather than staying empty forever.
        rows, rows_error = run_live(self._rows_of)
        self._rows: list[ToolRow] = rows if rows is not None else []
        # `_resync`'s own two warn-status writes must not be silently
        # dropped when the very first `enter_view` runs BEFORE this screen
        # is ever mounted (`show_view` calls `entering.enter_view()` before
        # `push_screen`, matching the ordinary standing-status guard below):
        # `on_mount`'s own call would otherwise immediately overwrite an
        # unconditional pre-mount `status.set()` with the ordinary standing
        # text. `_set_status` stashes here instead of writing directly when
        # not yet mounted, and `on_mount` applies the stash before falling
        # back to `_show_standing_status`.
        self._pending_status: tuple[str, str] | None = None
        # Through the SAME seam as the rows predicate above, and for the same
        # reason (CR-01, 15.4-REVIEW.md): these three are filesystem reads,
        # not in-memory ones -- `has_managed_block` does `path.read_text()`,
        # `active_tweak_ids` reads the rc files and stats the bin dir, and
        # `guard_state` probes the managed bin dir. A bare call here raised
        # OSError straight out of `UninstallScreen.__init__`, i.e. out of
        # `_build_app`, before any screen existed to report it.
        env, env_error = run_live(self._env_state)
        empty_env: tuple[list[str], bool, tuple[str, ...]] = ([], False, ())
        self._ban_names, self._has_path_block, self._tweak_ids = (
            env if env is not None else empty_env
        )
        # One stash for BOTH construction-time reads: `_resync` surfaces it
        # once on the first entry and then clears it, and a machine whose
        # $HOME just became unreadable typically fails both predicates, so
        # two separate one-time statuses would mean the user only ever sees
        # whichever one won the precedence ladder.
        self._startup_error: str | None = (
            "; ".join(part for part in (rows_error, env_error) if part is not None) or None
        )
        self._remove = inputs.remove
        self._terminal_sync = inputs.terminal_sync
        self.applied = False
        self.error: str | None = None
        self._entries = self._build_entries()
        self._by_key = {entry.key: entry for entry in self._entries}
        self._browser: ToolBrowser[_UninstallEntry] = ToolBrowser(self._adapter())

    # -- entry construction ------------------------------------------------
    def _build_entries(self) -> list[_UninstallEntry]:
        entries = [self._tool_entry(row) for row in self._rows]
        if self._ban_names:
            entries.append(self._ban_entry())
        if self._has_path_block:
            entries.append(self._block_entry())
        if self._tweak_ids:
            entries.append(self._tweak_entry())
        return entries

    def _tool_entry(self, row: ToolRow) -> _UninstallEntry:
        selectable = row.state == UninstallState.REMOVABLE
        style = "" if selectable else "dim"
        # 15.4-05/D-03: the cell names the REAL manager rather than collapsing
        # every managed tool into the identical "package manager" text -- but
        # from `row.manager`, the TERSE register, not from `row.hint`.
        #
        # CR-03 (15.4-REVIEW.md): rendering `row.hint` here sized the column
        # to the longest hint in the catalog -- including `_managed_hint`'s
        # trailing "— found at /abs/path" and `classify_tools`' "· required by
        # a, b, c" suffix -- which measured 120 columns wide at the project's
        # own minimum tested size (80x24) and pushed "What gets removed" to
        # x=174. The column was not merely truncated but UNREACHABLE:
        # `tool_browser.py` binds `left`/`right` to view switching with
        # `priority=True`, so those keys never reach the DataTable for
        # horizontal scrolling, and this is the screen whose Enter key deletes
        # files. The full sentence is not lost -- it is `detail` below, which
        # is where it already went, so the cell is a LABEL and the detail bar
        # is the prose, the same split `OWNER_LABELS`/`OWNER_DETAIL_LABELS`
        # already runs for the catalog's Owner column.
        #
        # `_VIA_UNATTRIBUTED` and `_VIA_USERSPACE` are byte-identical to the
        # pre-15.4-05 enum's values for those two cases: a managed row the
        # ownership seam could not attribute is exactly what that text always
        # meant, and D-03 asked only for the ATTRIBUTED rows to stop
        # collapsing into it.
        installed_via = {
            UninstallState.REMOVABLE: _VIA_USERSPACE,
            UninstallState.MANAGED: row.manager or _VIA_UNATTRIBUTED,
            UninstallState.ABSENT: _VIA_NONE,
            UninstallState.UNAVAILABLE: _VIA_NONE,
        }[row.state]
        removes = (
            f"{len(row.paths)} artifact(s)"
            if selectable
            else {
                UninstallState.MANAGED: "nothing (managed elsewhere)",
                UninstallState.ABSENT: "nothing (not installed)",
                UninstallState.UNAVAILABLE: "nothing (unavailable)",
            }[row.state]
        )
        cells = [
            mark(False) if selectable else Text(""),
            Text(row.tool.id, style="bold" if selectable else "dim"),
            Text(row.tool.category, style=style),
            Text(installed_via, style=style),
            Text(removes, style=style),
        ]
        return _UninstallEntry(
            key=row.tool.id,
            cells=cells,
            selectable=selectable,
            detail=row.hint,
            paths=tuple(row.paths),
            is_ban=False,
            is_path_block=False,
        )

    def _ban_entry(self) -> _UninstallEntry:
        return _UninstallEntry(
            key=_BAN_KEY,
            cells=[
                mark(False),
                Text("pip/npm ban", style="bold yellow"),
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

    # -- browser adapter ---------------------------------------------------
    def _adapter(self) -> BrowserAdapter[_UninstallEntry]:
        return BrowserAdapter(
            items=self._entries,
            columns=(
                ("Sel", "sel"),
                ("Tool", "tool"),
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
        )

    def _groups(self, _view: str) -> list[Section[_UninstallEntry]]:
        by_state: dict[UninstallState, list[_UninstallEntry]] = {}
        for row, entry in zip(self._rows, self._entries, strict=False):
            by_state.setdefault(row.state, []).append(entry)
        sections: list[Section[_UninstallEntry]] = [
            (title, title, by_state[state]) for state, title in _STATE_TITLES if by_state.get(state)
        ]
        env = [
            entry
            for entry in self._entries
            if entry.is_ban or entry.is_path_block or entry.is_tweaks
        ]
        if env:
            sections.append(("environment", "shell config the installer manages", env))
        return sections

    def compose_body(self) -> ComposeResult:
        yield self._browser

    def on_mount(self) -> None:
        if self._pending_status is not None:
            text, severity = self._pending_status
            self._pending_status = None
            self.status.set(text, severity)
        else:
            self._show_standing_status()

    def _set_status(self, text: str, severity: str) -> None:
        """Write a status line even before this screen has ever mounted.

        `Textual`'s own `on_mount` fires on FIRST PUSH, not at
        `install_screen` time, and `show_view` calls `entering.enter_view()`
        BEFORE `push_screen` (the single nav path's own ordering, unrelated
        to this screen). A warn status written on that very first entry
        would otherwise be overwritten by `on_mount`'s subsequent call to
        `_show_standing_status`, silently dropping it. Stashed here instead
        when not yet mounted; `on_mount` applies it.
        """
        if self.is_mounted:
            self.status.set(text, severity)
        else:
            self._pending_status = (text, severity)

    def _rows_of(self) -> list[ToolRow]:
        """Bare read of the rows predicate -- no failure isolation of its own.

        Every caller wraps this in `ui_common.run_live` (.claude/architecture.md
        rule 3): `__init__` directly (construction sits outside the nav path),
        and `_resync` via `_live_state`, which is what makes this call the
        one that touches the filesystem once per catalog tool.
        """
        return self._rows_predicate()

    def _env_state(self) -> tuple[list[str], bool, tuple[str, ...]]:
        """The three environment predicates another view can change while
        this one is suspended, as one tuple.

        Every one of them touches the FILESYSTEM and can therefore raise
        (CR-01, 15.4-REVIEW.md): `has_path_block` -> `shellrc.has_managed_block`
        -> `Path.read_text()`; `tweak_ids` -> `active_tweak_ids` ->
        `active_policies` -> `tweak_present`/`tweak_executables_present`,
        which read the rc files and stat the managed bin dir; `ban_names` ->
        `guard_state`, which probes that same bin dir. They read the same
        `$HOME` the rows predicate does, so a permission/IO fault under it
        fails them in a CORRELATED way, never independently.

        That is why this tuple exists as its own seam: both call sites
        (`__init__` and `_resync`) evaluate it through `run_live`, so a
        failure degrades to the last known values plus a warn status rather
        than escaping the nav path.
        """
        return (
            self._ban_names_of(),
            self._has_path_block_of(),
            self._tweak_ids_of(),
        )

    def _live_state(self) -> tuple[list[ToolRow], list[str], bool, tuple[str, ...]]:
        """Every input another view can change while this one is suspended,
        plus the row list itself -- now a live predicate rather than a
        construction-time snapshot (D-06), read through `_rows_of`.

        This method itself can raise, from EITHER half: the row list comes
        from `_rows_of`'s bare predicate call and the other three come from
        `_env_state`'s. `_resync` is the caller that wraps the WHOLE tuple in
        `run_live` and, on the exception that wrapping catches, retries
        `_env_state` alone through a SECOND `run_live` -- never bare, since
        the three environment predicates are filesystem reads correlated
        with the rows failure rather than the "cheap, non-failing in-memory
        reads" a deferred Round-3 finding claimed them to be.
        """
        return (self._rows_of(), *self._env_state())

    def _resync(self, *, clear_applied: bool) -> None:
        """Re-derive every live-state predicate and rebuild if it changed.

        PRECEDENCE (Round-2 review MEDIUM), a single ordered rule rather than
        an emergent one: the three outcomes of a re-derivation -- a predicate
        FAILURE, a CHANGED comparison, and an UNCHANGED comparison -- can all
        coexist with a standing `applied` summary, and nothing said which
        wins before this rule existed.

        1. A rows-predicate FAILURE wins the status line, over both the
           ordinary standing status and a standing `applied` summary, and it
           NEVER clears `applied`. Rationale: a warning about data the
           screen could not refresh outranks a repetition of an older
           result, and a failed read is not evidence that the removal
           summary stopped being true. The other three predicates are still
           evaluated and can still rebuild the environment rows on their
           own -- a rows failure suppresses only the row list's update, not
           the whole entry.
        2. Otherwise a CHANGED comparison rebuilds, conditionally clears
           `applied` (only when `clear_applied` is true AND `applied` was
           set), and writes the ordinary standing status.
        3. Otherwise an UNCHANGED comparison returns early with whatever
           message is standing -- this is what preserves the standing
           result message after an apply.

        `clear_applied` is the ONE thing the two callers legitimately
        differ on: `enter_view` passes True (a NAV ENTRY is D-06's explicit
        trigger for a same-session removal to stop being claimed once it no
        longer describes the screen). `ownership_refreshed` passes False --
        the user has not navigated, they are reading the summary of the
        removal they just performed, and a background repaint that wipes
        that sentence would be a regression: the fresh rows and the summary
        agree, they do not conflict.
        """
        refreshed, error = run_live(lambda: self._live_state())
        if error is not None:
            # A rows-predicate failure must not also freeze the three
            # environment predicates, so they are re-derived here rather
            # than through `_live_state`, whose whole tuple was discarded by
            # the exception `run_live` just caught -- but through the SAME
            # `run_live` seam (.claude/architecture.md rule 3), never bare.
            # CR-01 (15.4-REVIEW.md): all three are filesystem reads (see
            # `_env_state`'s docstring), so the very fault that triggers this
            # branch is the one most likely to make them raise too. A bare
            # call here escaped `enter_view` AFTER `show_view` had already
            # popped the previous screen, leaving the stack popped and
            # `current_view` un-updated -- a crash on the single nav path,
            # reachable from a background `ownership_refreshed()` repaint the
            # user never initiated. On failure the last known values are kept
            # and both messages are reported together.
            fallback, env_error = run_live(self._env_state)
            if fallback is None:
                fallback = (self._ban_names, self._has_path_block, self._tweak_ids)
                error = f"{error}; {env_error}"
            refreshed = (self._rows, *fallback)
        # run_live always pairs a None result with a non-None error, so
        # `refreshed` is never None here: either run_live's own call
        # succeeded, or the `error is not None` branch above just
        # reassigned it -- a static hint only (bandit B101 rejects a
        # runtime assert here, and none is needed: the invariant already
        # holds structurally, not because an assert enforces it), since
        # pyright cannot correlate the two independent tuple-unpacked
        # variables across the branch on its own.
        refreshed = cast(
            "tuple[list[ToolRow], list[str], bool, tuple[str, ...]]",
            refreshed,
        )
        stored = (self._rows, self._ban_names, self._has_path_block, self._tweak_ids)
        changed = refreshed != stored
        if changed:
            self._rows, self._ban_names, self._has_path_block, self._tweak_ids = refreshed
            self._entries = self._build_entries()
            self._by_key = {entry.key: entry for entry in self._entries}
            self._browser.reload(self._adapter())
        if error is not None:
            self._set_status(f"Could not refresh the tool list: {error}.", "warn")
            return
        if self._startup_error is not None:
            # The one-time construction-time failure (Round-1 review
            # MEDIUM, T-15.4-19), now covering the environment predicates
            # too (CR-01): surfaced on the first entry only, then cleared.
            # The fresh read above already re-derived (self-healed or not)
            # regardless -- this only controls what the status line says
            # about THIS entry.
            stashed = self._startup_error
            self._startup_error = None
            self._set_status(f"Could not read the uninstall state at startup: {stashed}.", "warn")
            return
        if not changed:
            return
        if clear_applied and self.applied:
            self.applied = False
        # A background repaint (clear_applied=False) that finds `applied`
        # still set must rebuild the rows -- already done above -- WITHOUT
        # touching the status line: `_show_standing_status` would otherwise
        # overwrite the sentence describing the removal the user just
        # performed with the ordinary "Nothing to uninstall." / cleared
        # standing text. A nav entry always reaches this with `applied`
        # already False (either it was never set, or the branch above just
        # cleared it), so the guard changes nothing on that path.
        if self.is_mounted and not self.applied:
            self._show_standing_status()

    def enter_view(self) -> None:
        """Re-derive every live-state predicate each time this view is opened.

        The Policies view toggles the ban and the tweaks live, the Doctor
        view writes the managed PATH block, and this screen's own removal
        action changes what `rows` should return -- all one nav step away
        at most -- so every row's existence and label must be read at entry
        rather than frozen in `__init__`. `clear_applied=True`: a nav entry
        is D-06's trigger for a same-session removal to stop being claimed
        once it no longer describes the screen.
        """
        self._resync(clear_applied=True)

    def ownership_refreshed(self) -> None:
        """Completion signal for an asynchronous ownership refresh landing
        while this screen may already be open.

        `installer/catalog_tui.py`'s threaded version-refresh worker
        repopulates the shared ownership map this screen's rows ultimately
        derive from; a screen entered BEFORE that worker committed shows an
        honest-but-stale fallback with nothing to tell it the real answer
        later arrived. `UnifiedApp` wires this as that completion signal
        (task 3), calling it only when this screen is the current view.

        Safe to call regardless of mount state (`ToolBrowser.reload` no-ops
        when unmounted) and safe to call when nothing changed (the ordinary
        unchanged comparison inside `_resync` returns early). `clear_applied
        =False`: this is a background repaint, not a navigation, so it must
        never wipe the sentence describing a removal the user just
        performed.
        """
        self._resync(clear_applied=False)

    def _show_standing_status(self) -> None:
        if not self._entries:
            self.status.set("Nothing to uninstall.", "ok")
        else:
            self.status.clear()

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
    def detail_text(self) -> str:
        return self._browser.detail_text

    # -- messages from the browser -----------------------------------------
    def on_tool_browser_selection_changed(self, event: ToolBrowser.SelectionChanged) -> None:
        event.stop()
        self.status.clear()

    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        event.stop()
        if self.applied or not self._entries:  # nothing to uninstall: keep the standing message
            return
        if not event.ids:
            self.status.set("Select at least one item to remove.", "warn")
            return
        self.app.push_screen(
            ConfirmUninstall(self._accept_summary(event.ids)),
            self._on_confirm(event.ids),
        )

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
        return ", ".join(parts)

    def _on_confirm(self, ids: list[str]) -> Callable[[bool | None], None]:
        # Callable[[bool | None], None] is the correct pyright-strict type:
        # ScreenResultCallbackType (textual/screen.py:83) passes Optional[ScreenResultType]
        # to the callback, i.e. bool | None for ModalScreen[bool].
        def run(confirmed: bool | None) -> None:
            if confirmed:
                self._apply_removal(ids)

        return run

    def _apply_removal(self, ids: list[str]) -> None:
        # Gated DIRECTLY on the in-flight boolean, unconditionally -- never
        # additionally on self.remove_tweaks or whether a daemon: id already
        # appears in self._tweak_ids. On a fresh machine with no OTHER active
        # tweaks, the daemon starts inactive at screen-construction time, so
        # _build_entries never offers a tweaks row at all (self._tweak_ids is
        # empty) -- self.remove_tweaks can then never become True through
        # this screen, so a condition on it would never fire in exactly the
        # scenario it exists to guard: the on-by-default worker can still
        # register the daemon during or after this uninstall completes with
        # no user-visible way to have prevented it (post-implementation
        # review finding, previously 11-REVIEWS.md cycle 3 finding #12's
        # narrower self._tweak_ids-based guard).
        if getattr(self.app, "daemon_default_in_flight", False):
            self.status.set(_DAEMON_DEFAULT_IN_FLIGHT_MESSAGE, "warn")
            return
        paths: list[Path] = []
        for key in ids:
            paths.extend(self._by_key[key].paths)
        decision = UninstallDecision(
            paths=tuple(paths),
            remove_ban=self.remove_ban,
            remove_path_block=self.remove_path_block,
            remove_tweaks=self.remove_tweaks,
        )
        swept, self.error = run_live(lambda: self._remove(decision))
        if swept is None:
            self.status.set(
                f"Uninstall failed: {self.error}. Check permissions, then press enter.",
                "error",
            )
            return
        self.applied = True
        tool_count = sum(1 for key in ids if key not in _ENV_KEYS)
        summary_parts = [self._applied_summary(tool_count, swept)]
        # WR-01 (15.4-REVIEW.md): gated on `tool_count`, not called
        # unconditionally. A sweep that removed only the pip/npm ban or the
        # PATH block and no tool at all changes nothing any ownership record
        # describes, so bumping the epoch for it degraded every managed row's
        # attribution to the generic registry phrase in exchange for nothing.
        # The invariant `version_status.py` states is "every MUTATION calls
        # invalidate" -- an env-lever sweep is not a mutation of tool
        # ownership, and reading it as one is what made this case a pure loss.
        if self._invalidate is not None and tool_count:
            # version_status.py:26-30's own invariant: every mutation this
            # app performs calls invalidate. This screen's removal was the
            # second hole in it (alongside install, closed by
            # on_install_run_finished below) -- without this call, a tool
            # the user just deleted keeps its pre-removal owner and version
            # for up to MANAGER_STALE_AFTER, on a screen whose adjacent
            # control deletes files. Mirrors on_install_run_finished's own
            # both-directions contract exactly: a raising seam never flips
            # a completed removal into a reported failure, and it is never
            # swallowed -- it is appended to the status line instead.
            try:
                self._invalidate()
            except Exception as exc:  # noqa: BLE001 -- post-mutation side effect, appended below
                summary_parts.append(f"version cache invalidation failed: {exc}")
            else:
                # WR-01: pair the invalidate with the pass that replaces what
                # it dropped. Nothing else can: `OwnershipRefreshed` is posted
                # only from `CatalogScreen`, so a session that never visits a
                # catalog tab again would show the degraded generic phrase for
                # every managed row until it exits. Only on the success path
                # -- an invalidate that raised did not drop anything, so there
                # is nothing to replace.
                self._refresh_ownership_worker()
        # D-01/15.6-06 Task 3: called unconditionally on every successful
        # sweep (never gated on tool_count -- unlike invalidate above, a
        # terminal reapply/reversion is warranted even when only an env
        # lever came off, since sync_terminal_shells' own no-zsh branch is
        # exactly what a zsh-removing sweep needs). A raised OSError is a
        # secondary, non-fatal warning appended to the same completed-removal
        # summary, mirroring the invalidate seam's own both-directions
        # contract: never swallowed, never flips `applied` or the primary
        # outcome.
        # WR-03: the one shared failure contract (terminal_sync_warning), not a
        # local try/except -- it is total and None-tolerant by construction.
        # WR-04: a terminal-sync failure must render with "warn" styling, not
        # the "ok" success color -- the text alone (appended above) is not
        # enough to distinguish it from a clean run at a glance. Mirrors the
        # Policies screen and _install_closed, both of which already use
        # "warn" for this exact class of failure.
        terminal_warning = terminal_sync_warning(self._terminal_sync)
        terminal_failed = terminal_warning is not None
        if terminal_warning:
            summary_parts.append(terminal_warning)
        self.status.set(multiline_summary(summary_parts), "warn" if terminal_failed else "ok")

    @work(thread=True, exclusive=True, group="uninstall-ownership-refresh", exit_on_error=False)
    def _refresh_ownership_worker(self) -> None:
        """Re-resolve ownership after this screen's own invalidate (WR-01).

        BLOCKING: the seam re-probes every manager, which is why this is a
        thread worker and not an inline call on the message loop. Failure is
        deliberately silent -- the screen is already showing the removal
        summary the user asked for, the degraded-but-honest registry phrase is
        what it falls back to, and a second error line about a background
        repaint would bury the result they are reading. `OwnershipRefreshed`
        is posted only when the pass actually committed, exactly as
        `CatalogScreen` posts it, so `UnifiedApp.on_ownership_refreshed`
        routes it back here through the one path that already exists.
        """
        refresh = self._refresh
        if refresh is None:
            return
        _result, error = run_live(refresh)
        if error is None:
            self.post_message(OwnershipRefreshed())

    def _applied_summary(self, tool_count: int, swept: SweepResult) -> str:
        parts: list[str] = []
        if tool_count:
            parts.append(f"Removed {tool_count} tool(s).")
        if self.remove_ban:
            parts.append(
                "pip/npm ban removed — open a new shell or run `hash -r` so cached"
                " command paths refresh."
            )
        if self.remove_path_block:
            parts.append("PATH wiring removed — restart your shell to drop the managed dirs.")
        if self.remove_tweaks:
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
            parts.extend(f"warning: {warning}." for warning in swept.warnings)
            if not swept.swept and not swept.failed:
                parts.append("no shell tweaks were still enabled — nothing to disable.")
        # One line per outcome: a single joined line overflows the terminal width and
        # truncates the reload guidance, so the "needs a new shell" steps go unseen.
        return multiline_summary(parts)


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
        self.error: str | None = None
        self.detail_text = ""
        # True while a scheduled-job toggle runs on its thread worker (WR-02);
        # a second toggle or a reschedule waits for it.
        self.toggle_in_flight = False
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
            effect_kind = "scheduled job" if policy.log_path is not None else "shell config"
            table.add_row(
                self._state_cell(self.active_state[policy.id]),
                Text(policy.label, style="bold yellow"),
                self._requires_cell(policy),
                Text(f"{effect_kind}: {policy.description}", style="dim"),
                key=policy.id,
            )
        table.focus()
        self._set_detail(self._policies[0] if self._policies else None)
        self._refresh_link_mode_line()
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

    def _state_cell(self, active: bool) -> Text:
        # A ●/○ glyph carries the state independent of color: the lone row is
        # always focused, so the selection highlight flattens the green/dim cue.
        label = "● [on]" if active else "○ [off]"
        return Text(label, style="green" if active else "dim")

    def _requires_cell(self, policy: Policy) -> Text:
        missing_requires = policy.missing_requirements()
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
        missing_requires = policy.missing_requirements()
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
            "tweak:claude-skip": (
                "Aliases claude to claude --dangerously-skip-permissions.",
                "Useful only in trusted, disposable workspaces where confirmation prompts are"
                " intentional noise.",
                "Disable it when you need normal Claude Code permission prompts back.",
            ),
            "tweak:codex-skip": (
                "Aliases codex to codex --dangerously-bypass-approvals-and-sandbox.",
                "Useful only in trusted, disposable workspaces where confirmation and sandbox"
                " prompts are intentional noise.",
                "Disable it when you need normal Codex confirmation/sandboxing prompts back.",
            ),
            "tweak:opencode-auto": (
                "Aliases opencode to opencode --auto.",
                "Narrower than claude-skip's/codex-skip's full bypass: explicit deny rules in"
                " your own opencode config still apply.",
                "Disable it when you want normal per-permission prompting back.",
            ),
            "tweak:cursor-agent-model": (
                "Injects --model gpt-5.6-sol-high into a bare cursor-agent/cursor call, and"
                " never overrides an already-passed --model (either --model X or --model=X).",
                "This tweak only requests, per Cursor's own headless-mode changelog fix, this"
                " model's full context — this installer does not independently verify the"
                " context window reached in a given response.",
                "Requires a Cursor plan that actually includes this model; an unsupported plan"
                " may error or silently downgrade.",
                "Enabling this tweak automatically removes (via unalias) a cursor-agent/cursor"
                " alias that is active before this block loads — not any alias anywhere in your"
                " config — so the tweak's own function takes effect over whatever was defined"
                " earlier. A same-named alias or function defined later in your own sourced"
                " files still wins, since shell source order — not unalias — controls the final"
                " definition.",
                "Disable it to keep using whatever model was last selected.",
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
                "The timer runs while you are logged in. For always-on operation, run"
                " `loginctl enable-linger $USER` yourself; this installer does not run that"
                " command for you, because it is a system-wide setting for the whole account.",
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
        lines = [f"{policy.label} — {policy.description}"]
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
        elif policy.requires:
            lines.append(f"Required tool(s): {', '.join(policy.requires)}.")
        lines.extend(details.get(policy.id, ("Space toggles this reversible shell policy.",)))
        if policy.id.startswith("tweak:"):
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
            usage = self._temp_usage_line()
            if usage is not None:
                lines.append(usage)
            competing = self._competing_line()
            if competing is not None:
                lines.append(competing)
        return "\n".join(lines)

    def _competing_line(self) -> str | None:
        """WR-10: name a system-scope competitor on the background-cleanup row.

        Peek only -- this runs on every row highlight -- so it says nothing
        until the screen's own warm-up worker has landed an answer. Only
        system-scope units appear: a user-scope one is taken over by the
        apply, so repeating it here would describe a stopped mechanism.
        """
        if self._competing is None:
            return None
        try:
            units = self._competing(blocking=False)
        except (OSError, ValueError, CommandError):
            return None
        names = sorted({unit.name for unit in units if unit.scope == SCOPE_SYSTEM})
        if not names:
            return None
        return (
            f"Also installed system-wide: {', '.join(names)} (root-owned; this installer "
            "cannot stop it without sudo)"
        )

    def _temp_usage_line(self) -> str | None:
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
        if self._disk_pressure is None:
            return None
        try:
            pressure = self._disk_pressure(blocking=False)
        except (OSError, ValueError):
            return None
        if pressure.tmp_used_percent is not None:
            return f"Current temp-directory usage: {pressure.tmp_used_percent:.1f}%"
        if pressure.home_free_percent is not None:
            return f"Current home filesystem free space: {pressure.home_free_percent:.1f}%"
        return None

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
        `systemctl --user is-active` (WR-02).
        """
        policy = next((p for p in self._policies if p.id == policy_id), None)
        if policy is None or policy.is_active is None:
            return None
        return policy.is_active()

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
        Idempotent: a no-op when the resolved value does not actually
        change anything, so calling this unconditionally is harmless.
        """
        policy = next((p for p in self._policies if p.id == policy_id), None)
        if live is not None:
            resolved = live
        elif policy is not None and policy.is_active is not None:
            return
        else:
            resolved = applied
        if policy_id not in self.active_state or self.active_state[policy_id] == resolved:
            return
        self.active_state[policy_id] = resolved
        if self.is_mounted:
            self.query_one(DataTable[Any]).update_cell(
                policy_id, "state", self._state_cell(resolved)
            )
            highlighted = self._highlighted_policy()
            if highlighted is not None and highlighted.id == policy_id:
                self._set_detail(highlighted)

    def action_toggle_policy(self) -> None:
        policy = self._highlighted_policy()
        if policy is None:
            return
        if policy.id == getattr(self.app, "_daemon_default_policy_id", None) and getattr(
            self.app, "daemon_default_in_flight", False
        ):
            self.status.set(_DAEMON_DEFAULT_IN_FLIGHT_MESSAGE, "warn")
            return
        if self.toggle_in_flight:
            self.status.set(_TOGGLE_IN_FLIGHT_MESSAGE, "warn")
            return
        active = self.active_state[policy.id]
        missing_requires = policy.missing_requirements()
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
            self.toggle_in_flight = True
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
        self.toggle_in_flight = False
        policy = next((item for item in self._policies if item.id == message.policy_id), None)
        if policy is None:
            return
        self.error = message.error
        self._finish_toggle(policy, message.was_active, message.result)

    def _finish_toggle(self, policy: Policy, active: bool, result: PolicyResult | None) -> None:
        if result is None:
            self.status.set(
                f"Policy change failed: {self.error}. Check permissions, then press space.",
                "error",
            )
            return
        new_active = not active
        self.active_state[policy.id] = new_active
        self.query_one(DataTable[Any]).update_cell(policy.id, "state", self._state_cell(new_active))
        self.query_one(DataTable[Any]).update_cell(
            policy.id, "requires", self._requires_cell(policy)
        )
        self._set_detail(policy)
        verb = "enabled" if new_active else "disabled"
        self.status.set(self._summary(policy, verb, result), "warn" if result.warning else "ok")

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
        if not self.active_state[policy.id]:
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
            # the user takes to choose a time, and the on-by-default worker
            # can start racing to reapply/reschedule the SAME policy at any
            # point during that window (a machine where the plist already
            # exists -- so this policy reads active=True at construction --
            # but daemon.decided() is still False, e.g. an upgrade that
            # registered the LaunchAgent before the "decided" marker existed).
            # Guarding only action_pick_time would leave that whole window
            # open; action_toggle_policy and UninstallScreen._apply_removal
            # already guard their own mutation points the same way
            # (post-implementation review finding CR-02).
            if policy.id == getattr(self.app, "_daemon_default_policy_id", None) and getattr(
                self.app, "daemon_default_in_flight", False
            ):
                self.status.set(_DAEMON_DEFAULT_IN_FLIGHT_MESSAGE, "warn")
                return
            if self.toggle_in_flight:
                self.status.set(_TOGGLE_IN_FLIGHT_MESSAGE, "warn")
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
        aware_active = self.link_mode_aware_active()
        old = self._link_mode() if self._link_mode is not None else "centralized"
        report, error = run_live(lambda: move_link_mode(aware_active, value, setter, old_mode=old))
        if error is not None:
            self.status.set(error, "error")
            return
        text, severity = _link_mode_status(value, report or ())
        self.status.set(text, severity)
        self._refresh_link_mode_line()

    def link_mode_aware_active(self) -> list[Policy]:
        """The active, link-mode-aware policies: the ones a mode change moves.

        The live truth is this screen's own active_state (refreshed by every
        toggle), never uninstall.active_policies, which rebuilds its own policy
        objects from bundles and cannot see the ban (17-08 D-09).
        """
        return [
            policy
            for policy in self._policies
            if policy.link_mode_aware and self.active_state.get(policy.id, False)
        ]


def _link_mode_status(value: str, report: Sequence[PolicyMove]) -> tuple[str, str]:
    """(text, severity) both link-mode pickers show after a move: the saved
    mode, the policies moved, and every failure named. Severity is warn when
    any entry failed (the mode itself was still saved), ok otherwise."""
    parts = [f"Link mode saved: {value}."]
    moved = [entry.policy_id for entry in report if entry.status == "moved"]
    failed = [entry for entry in report if entry.status == "failed"]
    if moved:
        parts.append(f" Moved: {', '.join(moved)}.")
    for entry in failed:
        parts.append(f" Failed: {entry.policy_id} ({entry.detail}).")
    return "".join(parts), ("warn" if failed else "ok")


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
    ConfirmUninstall > Static { width: 60; border: round red; padding: 1 2; }
    """

    def __init__(self, summary: str) -> None:
        super().__init__()
        self.summary = summary  # public test seam

    def compose(self) -> ComposeResult:
        yield Static(
            Text.from_markup(
                f"[bold red]Remove {self.summary}?[/]\n\n"
                "This deletes installed artifacts and is not undoable.\n"
                "[dim]enter remove · esc cancel[/]"
            )
        )

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


_DAEMON_DEFAULT_IN_FLIGHT_MESSAGE = (
    "Applying the on-by-default daemon setting; wait a moment, then try again."
)
_TOGGLE_IN_FLIGHT_MESSAGE = "A background job change is still applying; wait a moment, then retry."


class DaemonDefaultApplied(Message):
    """The threaded on-by-default auto-apply worker finished; `applied` is
    whether apply() actually ran (True) or was a no-op/failure (False).

    Posted unconditionally from UnifiedApp's own worker, in a finally block,
    regardless of outcome -- mirroring GlobalsAudited/GlobalsReinstalled's same
    thread -> post_message hand-off shape, for the identical reason: widgets
    may only be touched from the app's own thread.
    """

    def __init__(self, policy_id: str, applied: bool, live: bool | None = None) -> None:
        self.policy_id = policy_id
        self.applied = applied
        # The policy's own is_active() answer, resolved on the worker thread
        # (WR-02), or None when there was none to resolve.
        self.live = live
        super().__init__()


class UnifiedApp(App[list[str] | None]):
    """One app hosting the wizard views. run() returns the catalog selection
    (ids in catalog order) on accept, or None when aborted. `current_view` and
    `catalog` are public for headless tests."""

    ENABLE_COMMAND_PALETTE = False  # replace Textual's dead-ending default palette
    BINDINGS: ClassVar[list[BindingType]] = [
        # ctrl+c is the hard abort: unguarded, so it quits from anywhere — even on
        # top of the NavScreen modal. q is the soft quit: priority so it fires on
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
        installed: Mapping[str, bool],
        blurbs: Mapping[str, str],
        *,
        report: DoctorReport,
        guard_state: Callable[[], tuple[dict[str, bool], str | None]],
        fix_preview: str | Callable[[], str],
        fix: Callable[[], None],
        uninstall: UninstallInputs,
        policies: PolicyInputs,
        node_globals: Callable[[], NodeGlobalsReport] | None = None,
        globals_preview: Callable[[NodeGlobalsReport], str] | None = None,
        reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
        unavailable: Mapping[str, bool | UnavailableReason] | None = None,
        initial_view: str = BASE_VIEW,
        daemon_default: Callable[[], bool] | None = None,
        daemon_default_policy_id: str | None = None,
        version_refresh: VersionRefreshService | None = None,
        updates: UpdateService | None = None,
        execute: ExecuteInputs | None = None,
        prompt_link_mode: bool = False,
        terminal_sync: Callable[[], str | None] | None = None,
    ) -> None:
        super().__init__()
        self._staged: set[str] = set()
        self._execute = execute
        self._prompt_link_mode = prompt_link_mode
        self._set_link_mode = policies.set_link_mode
        self._read_link_mode = policies.link_mode
        self._link_mode_prompted = False
        # The exit code answers "did everything this session asked for succeed",
        # not "did the last thing succeed" — merge each run field-wise in order.
        self.install_summary: Summary | None = None
        self._version_refresh = version_refresh
        self._updates = updates
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
        # Set by on_install_run_finished when the post-run cache invalidation
        # fails, consumed (and cleared) by the _install_closed that follows:
        # the execute screen is still on top when the failure happens, so
        # there is no catalog status line to write to yet.
        self._invalidate_warning: str | None = None
        # WR-07 (15.6-REVIEW.md): set by on_install_run_finished whenever a
        # run in this ExecuteScreen session actually installed something
        # (Summary.installed non-empty -- real disk/config mutation, unlike
        # `already`/`failed`/`no_method`/etc., which are no-ops or failures),
        # consumed and reset by _install_closed. Gates the terminal
        # re-synchronization on a real state change: merely opening and
        # dismissing the Execute screen with nothing selected/changed
        # otherwise rewrote kitty.conf, created a brand-new wezterm.lua
        # (CR-03), and wrote konsolerc for a session where the user selected
        # and changed nothing.
        self._install_state_changed: bool = False
        # The WHOLE catalog, not a tier slice. `_install_closed` re-derives the
        # installed map from this list because the map is resolved against the
        # full catalog by deps.missing_requires / selection.unstaged_recommends,
        # while each screen's own `tools` is the tier filter -- which narrows
        # what is DISPLAYED and never what is resolved (.claude/architecture.md).
        self._catalog_tools: list[Tool] = list(tools)
        self._catalogs: dict[str, CatalogScreen] = {
            tier.value: CatalogScreen(
                [tool for tool in tools if tool.tier == tier],
                installed,
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
        # Non-base views, installed on mount and pushed by value.
        self._views: dict[str, AppScreen] = {
            name: screen for name, screen in self._catalogs.items() if name != BASE_VIEW
        }
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
                ),
                "uninstall": UninstallScreen(uninstall),
                "policies": PoliciesScreen(policies),
            }
        )
        self._initial_view = initial_view
        self.current_view = BASE_VIEW
        self._daemon_default = daemon_default
        self._daemon_default_policy_id = daemon_default_policy_id
        # True from construction time whenever a real auto-apply callback was
        # wired, so there is no window between __init__ and the worker
        # actually starting inside on_mount where this reads False while an
        # auto-apply is nonetheless about to run (11-REVIEWS.md cycle 2
        # finding #15). Permanently False -- a no-op state -- for every
        # construction site that never wires daemon_default at all.
        self.daemon_default_in_flight: bool = self._daemon_default is not None

    # Textual annotates install_screen with a bare (unparameterized) Screen, which
    # pyright-strict reports as partially unknown at the call site. Re-declare it
    # precisely for type checking only — zero runtime cost, no suppression — the
    # same pattern as the UninstallScreen.app narrowing above.
    if TYPE_CHECKING:

        def install_screen(self, screen: Screen[None], name: str) -> None: ...

    async def on_mount(self) -> None:
        # Install every view screen: an installed screen is SUSPENDED when popped;
        # an uninstalled one is REMOVED (App._replace_screen) — its whole widget
        # tree destroyed. Re-pushing the same instance then re-composes onto stale
        # state: pending callbacks lose their widgets, and screen.focused can point
        # at a detached widget, collapsing the binding chain so the App's priority
        # number keys stop matching — later keys in a fast burst were silently
        # dropped (the "press 2 for Doctor but land elsewhere" bug). The catalog
        # needs no install: it is the base screen and is never popped.
        for name, screen in self._views.items():
            self.install_screen(screen, name)
        if self._initial_view != BASE_VIEW:
            await self.show_view(self._initial_view)
        if self._daemon_default is not None:
            self._apply_daemon_default_worker()
        # Last in on_mount so a first-run user answers exactly one question;
        # the daemon worker's completion status lands behind this picker, not
        # on top of it.
        if (
            self._prompt_link_mode
            and self._set_link_mode is not None
            and not self._link_mode_prompted
        ):
            self._link_mode_prompted = True
            self.push_screen(LinkModeScreen(), self._first_link_mode_picked)

    # exit_on_error=False (Textual's own worker.py defaults this True, which
    # calls App._handle_exception -- crashing the whole app -- on any
    # exception a threaded worker raises): an exception outside
    # ensure_daemon_default's own except (OSError, CommandError) tuple must
    # still leave a usable, running app (the finally block below already
    # guarantees the in-flight flag clears); Worker.state/.error still record
    # it for diagnosis, this only suppresses the exit-the-app side effect.
    @work(thread=True, exclusive=True, group="daemon-default", exit_on_error=False)
    def _apply_daemon_default_worker(self) -> None:
        """Auto-apply the daemon's on-by-default policy off the event loop.

        Mirrors DoctorScreen._audit_globals_worker/_reinstall_globals_worker's
        own thread-worker + post_message shape, for the identical reason: a
        real launchctl bootstrap call (run_captured's underlying
        subprocess.run has no timeout) must never freeze frame rendering or
        keypress handling. The body is wrapped in try/finally so the
        completion message is ALWAYS posted -- regardless of whether
        self._daemon_default() returns normally or raises ANYTHING, including
        an exception outside ensure_daemon_default's own
        except (OSError, CommandError) tuple -- so daemon_default_in_flight
        can never get stuck True (11-REVIEWS.md cycle 3 finding #15). An
        exception raised inside the try still propagates normally after the
        finally runs and is recorded on the Worker itself (state=ERROR,
        .error); exit_on_error=False is what keeps that from also crashing
        the app, so this fix only ever ADDS the guaranteed message post, it
        never swallows or hides a genuine bug.
        """
        applied = False
        live: bool | None = None
        try:
            if self._daemon_default is not None:
                applied = self._daemon_default()
            # Resolved HERE, on the worker thread, never in the handler: the
            # apply's own finally just invalidated the timer cache, so this
            # read is guaranteed to spawn `systemctl --user is-active` (WR-02).
            policies_screen = self._views.get("policies")
            if self._daemon_default_policy_id is not None and isinstance(
                policies_screen, PoliciesScreen
            ):
                live = policies_screen.live_state(self._daemon_default_policy_id)
        finally:
            if self._daemon_default_policy_id is not None:
                self.post_message(
                    DaemonDefaultApplied(self._daemon_default_policy_id, applied, live)
                )

    def on_daemon_default_applied(self, message: DaemonDefaultApplied) -> None:
        # Cleared FIRST, unconditionally: this is the ONE place the flag is
        # ever cleared, and the ALWAYS-post-message guarantee above is what
        # makes that safe on every outcome, not only a successful apply.
        self.daemon_default_in_flight = False
        policies_screen = self._views.get("policies")
        if isinstance(policies_screen, PoliciesScreen):
            policies_screen.refresh_daemon_state(message.policy_id, message.applied, message.live)

    @property
    def catalog(self) -> CatalogScreen:
        """The base (first-registered tier) screen."""
        return self._catalogs[BASE_VIEW]

    def catalog_for(self, view: str) -> CatalogScreen:
        """Headless-test seam for the two non-base tier screens."""
        return self._catalogs[view]

    def get_default_screen(self) -> CatalogScreen:
        # The first registered tier is the app's base screen, so App-level queries
        # (the tests' app.query_one) resolve against it. It reports its decision
        # via the Decided message rather than dismissing the only screen on the stack.
        return self._catalogs[BASE_VIEW]

    async def show_view(self, name: str) -> None:
        # Await each stack mutation so a transition fully settles before the next
        # runs: this prevents a queued second nav from popping/pushing onto an
        # in-flight stack and breaking the [catalog] / [catalog, <view>] invariant.
        if name == self.current_view:
            return
        # An actual view change ends the selection moment the view being left was
        # describing, so its transient prompt/notice go with it. This is the one
        # navigation path (.claude/architecture.md rule 2), which makes it the only
        # correct trigger: a screen-suspend handler would also fire for the nav
        # palette opening on top, wiping state for a view the user never left.
        leaving = self._catalogs.get(self.current_view)
        if leaving is not None:
            leaving.clear_transient()
        # A view (Uninstall) may have changed the machine; no catalog shows a stale ✓.
        if name in self._catalogs:
            recheck_error = self._rederive_installed()
            if recheck_error is not None:
                self._pending_warnings.append(recheck_error)
        if self.current_view != BASE_VIEW:
            await self.pop_screen()
        if name == BASE_VIEW:
            # The base catalog is never pushed, so it re-derives here or never.
            self._catalogs[BASE_VIEW].enter_view()
        else:
            entering = self._views[name]
            # The single navigation path is also the single refresh point: a
            # view holding state another view can change live re-derives it
            # here, before it is shown (rule 2).
            entering.enter_view()
            await self.push_screen(entering)
        self.current_view = name
        # T-15.6-13: this is also the one place a warning queued because no
        # AppScreen was resolvable when it arrived can finally be delivered.
        visible = self._catalogs.get(name) or self._views.get(name)
        if visible is not None:
            self._flush_pending_warnings(visible)

    def _flush_pending_warnings(self, screen: AppScreen) -> None:
        if not self._pending_warnings:
            return
        pending, self._pending_warnings = self._pending_warnings, []
        screen.status.set(" · ".join(pending), "warn")

    def _navigable(self) -> bool:
        # ctrl+p and the number keys are priority App bindings, so they fire even
        # while a NavScreen modal is open. Navigate only when the catalog or a
        # placeholder is the active screen — never on top of the palette, which
        # would push onto a live modal and break the [catalog] / [catalog, <view>]
        # stack invariant.
        return self.screen is self._catalogs[BASE_VIEW] or self.screen in self._views.values()

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
            target.status.set(
                f"Link mode unchanged; this run uses {mode}. "
                f"Press {policies_key} then m to change it later.",
                "warn",
            )
            return
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
            target.status.set(error, "error")
            return
        text, severity = _link_mode_status(value, report or ())
        target.status.set(text, severity)

    def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
        if self._execute is None or message.result is None:
            self.exit(message.result)
            return
        self.push_screen(ExecuteScreen(message.result, self._execute), self._install_closed)

    def _install_closed(self, _result: None) -> None:
        self._staged.clear()
        # ExecuteScreen is modal: _navigable() returns False while it is on
        # top, so current_view still names the catalog tier the run was
        # launched from, and _catalogs has an entry for every tier including
        # the base one -- no base/non-base branch needed here, unlike
        # show_view (that method branches because it pushes/pops screens;
        # this callback does neither).
        #
        # Re-derive every catalog's installed map from the run's own live
        # presence predicate BEFORE the refresh below repaints. self._execute
        # is guaranteed non-None whenever this callback can run at all --
        # on_catalog_screen_decided only pushes ExecuteScreen when it is set.
        # Presence is answered by the presence predicate and
        # version-readability by the version probe, so this is correct in
        # both directions (a tool installed by the run stops being
        # suppressed; a tool whose --version stopped parsing keeps its mark)
        # for every installation shape, including a detect_path-only tool no
        # manager inventory lists and no `--version` probe will ever answer
        # (oh-my-zsh, SDKMAN).
        #
        # The map is derived over self._catalog_tools -- the WHOLE catalog --
        # and the identical map is handed to every screen. Deriving it per
        # screen from `screen.tools` would drop every id belonging to another
        # tier, and `set_installed` is a plain replacement, so the two
        # consumers that read this map against the full catalog
        # (deps.missing_requires and selection.unstaged_recommends, both via
        # `installed.get(dep_id, False)`) would silently read an installed
        # cross-tier dependency as missing -- "mmdc also needs pnpm" with pnpm
        # already installed. The tier filter narrows what is DISPLAYED and
        # never what is resolved (.claude/architecture.md).
        #
        # Rule 3 (.claude/architecture.md): the sweep goes through run_live
        # like every other live core read a screen triggers. The predicate
        # defaults to installer.status.is_installed, which touches PATH, `~`
        # paths and /Applications once per catalog tool -- 89 of them in
        # production -- so a failure here is an ordinary environment failure
        # (an OSError stat'ing a disconnected network path), and an OSError
        # out of a bare comprehension in a screen-result callback crashes the
        # message pump rather than being surfaced. Through run_live it leaves
        # the previous map in place and reports itself, exactly as the
        # invalidate failure folded in below does.
        warnings: list[str] = []
        recheck_error = self._rederive_installed()
        if recheck_error is not None:
            warnings.append(recheck_error)
        # D-01/15.6-06 Task 1: the shared terminal synchronizer runs after a
        # close event that actually changed installed-tool state -- never
        # only a selected tool id (WR-07: merely opening and dismissing the
        # Execute screen with nothing selected/changed otherwise rewrote
        # kitty.conf, created a brand-new wezterm.lua (CR-03), and wrote
        # konsolerc for a session that installed nothing). The zsh-removal
        # revert case is independently covered by
        # UninstallScreen._apply_removal and _run_uninstall, so this gate
        # does not lose coverage for that scenario. Through run_live like
        # every other live core read this callback triggers (rule 3): an
        # OSError is a secondary, non-fatal warning and must never flip an
        # already-recorded run into a reported failure.
        # WR-03: not run_live -- terminal_sync_warning IS this seam's live
        # guard, and routing through both produced the one message whose
        # casing had already drifted from the other four call sites.
        if self._install_state_changed:
            self._install_state_changed = False
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
        # catalog on top means nothing to re-enter (enter_view is a catalog
        # tier's own version-refresh trigger, not a generic "screen visible"
        # signal), and the installed maps above were still replaced either way.
        active = self._catalogs.get(self.current_view)
        if active is not None:
            active.enter_view()
        # Both post-run failures land on one line, and both are written after
        # enter_view so the refresh it starts cannot repaint over them.
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
        pending, self._pending_warnings = self._pending_warnings, []
        visible.status.set(" · ".join(pending + warnings), "warn")

    def _rederive_installed(self) -> str | None:
        """Re-read every catalog's installed map from the live presence predicate.

        One body for every moment the machine may have changed under the catalogs
        (an install run closing, a catalog view being shown after an uninstall).
        Returns a warning line on failure, None otherwise.
        """
        if self._execute is None:
            return None
        installed = self._execute.installed
        fresh, error = run_live(lambda: {tool.id: installed(tool) for tool in self._catalog_tools})
        if fresh is not None:
            for screen in self._catalogs.values():
                screen.set_installed(fresh)
            return None
        return f"installed-state re-check failed: {error}" if error is not None else None

    def _visible_app_screen(self) -> AppScreen | None:
        screen = self.screen
        return screen if isinstance(screen, AppScreen) else None

    def on_install_run_finished(self, message: InstallRunFinished) -> None:
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
        if self._version_refresh is not None:
            try:
                self._version_refresh.invalidate(reason="install run finished")
            except Exception as exc:  # noqa: BLE001 -- post-mutation side effect, reported below
                self._invalidate_warning = f"version cache invalidation failed: {exc}"
        incoming = fold_run(
            message.summary,
            not_attempted=message.not_attempted,
            update_outcomes=message.update_outcomes,
            update_errors=message.update_errors,
            error=message.error,
        )
        # WR-07: `installed` is the one Summary bucket that means a real
        # mutation happened (a tool actually installed) -- `already` is a
        # confirmed-no-op, and `failed`/`no_method`/`mismatched`/
        # `dependency_failed`/`manual_required` are all failures, never a
        # state change. `|=` because a session can run ExecuteScreen more
        # than once before closing it; any one of those runs installing
        # something is enough.
        self._install_state_changed = self._install_state_changed or bool(incoming.installed)
        existing = self.install_summary
        if existing is None:
            self.install_summary = incoming
            return
        # Exit code answers "did everything this session asked for succeed",
        # not "did the last thing succeed" — do not simplify this back to an
        # assignment.
        self.install_summary = Summary(
            installed=existing.installed + incoming.installed,
            already=existing.already + incoming.already,
            failed=existing.failed + incoming.failed,
            no_method=existing.no_method + incoming.no_method,
            mismatched=existing.mismatched + incoming.mismatched,
            dependency_failed=existing.dependency_failed + incoming.dependency_failed,
            manual_required=existing.manual_required + incoming.manual_required,
            not_attempted=existing.not_attempted + incoming.not_attempted,
            update_failed=existing.update_failed + incoming.update_failed,
            crash_error=existing.crash_error or incoming.crash_error,
        )

    def on_ownership_refreshed(self, message: OwnershipRefreshed) -> None:
        """The completion signal for an asynchronous ownership refresh that
        just committed (`installer/catalog_tui.py`'s `OwnershipRefreshed`,
        posted only from its commit path).

        Hands it to the Uninstall screen ONLY when that view is the current
        one, and does nothing at all otherwise (Round-2 review HIGH). The
        single nav path (`show_view` -> `entering.enter_view()`) already
        re-derives every OTHER view before it is shown, so a full-catalog
        filesystem sweep for a screen nobody is looking at buys nothing.
        This patches exactly one hole -- a screen entered BEFORE the async
        refresh landed -- and is a completion callback for an in-flight
        read, not a second navigation trigger; it does not contradict rule
        2 or `_install_closed`'s own no-new-coupling comment above, which
        deliberately refreshes nothing here because at THAT moment there is
        nothing fresh yet to hand over.
        """
        del message  # carries no payload; its arrival is its whole meaning
        if self.current_view != "uninstall":
            return
        screen = self._views.get("uninstall")
        if isinstance(screen, UninstallScreen):
            screen.ownership_refreshed()

    def action_abort(self) -> None:
        # The soft quit (q). Guarded so a priority q binding does not quit out from
        # under the NavScreen palette; ctrl+c (action_hard_abort) stays unguarded.
        if not self._navigable():
            return
        self.exit(None)

    def action_hard_abort(self) -> None:
        # The hard quit (ctrl+c): always exits, including on top of the palette.
        self.exit(None)
