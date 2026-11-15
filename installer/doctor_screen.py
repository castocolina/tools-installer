"""The Doctor view: PATH audit, safe PATH repair and the pnpm globals audit."""

import contextlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.widgets import Static

from installer.catalog_tui import RefreshRequested
from installer.diskusage import DiskPressureProbe
from installer.doctor import DoctorReport
from installer.doctor_messages import DiskPressureProbed, GlobalsAudited, GlobalsReinstalled
from installer.enums import MutationHolder
from installer.guidance import (
    GUARD_ENTER_HINT,
    SAFE_FIX_ENTER_HINT,
    Guidance,
    competing_mechanism_guidance,
    disk_pressure_guidance,
    doctor_guidance,
)
from installer.modals import (
    ConfirmGuardFile,
)
from installer.model import Tool
from installer.pnpm_globals import (
    PNPM_SMOKE_FAILED,
    PNPM_SPLIT_GROUP,
    NodeGlobalsReport,
)
from installer.pnpm_globals import node_globals as declared_node_globals
from installer.rcclean import PathWriterLine, group_writer_lines
from installer.render import guidance_text
from installer.run import CommandError
from installer.sanitize import sanitize_log_line
from installer.shellrc import PathGuardOutcome
from installer.systemd_daemon import CompetingProbe
from installer.ui_common import (
    AppScreen,
    run_live,
)
from installer.version_status import (
    Health,
    VersionRefreshService,
    pnpm_findings,
)

if TYPE_CHECKING:
    from installer.wizard_app import UnifiedApp


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
# The console sentence's own tail names the platform's real one-off command,
# so only its leading clause is rewritten for the TUI -- rebuilding
# the whole sentence here would re-introduce a second, platform-blind copy of
# that command.
_DISK_PRESSURE_TUI_PREFIX = "Open the Schedules view and turn on the tmp cleanup row;"


_DOCTOR_READ_ERROR = "Could not read the doctor state: "


def _smoke_findings(tool_id: str, findings: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """The audit's smoke failures for one tool, as Doctor evidence lines.

    Child output: sanitized once here, so every view renders clean text.
    """
    return tuple(
        sanitize_log_line(PNPM_SMOKE_FAILED.format(tool_id=tool_id, reason=reason))
        for found_id, reason in findings
        if found_id == tool_id
    )


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
    /* The card scrolls inside this area, under the fixed chrome; it takes focus so the
       keyboard (down, pagedown, end) scrolls it. */
    DoctorScreen #doctor-scroll {
        align-horizontal: center;
    }
    DoctorScreen #doctor-body {
        width: 76;
        max-width: 90%;
        height: auto;
        margin: 1 0;
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
        # A predicate, not its result: the Policies view can enable the
        # background cleanup one navigation step away, so every entry re-reads
        # it. The daemon half of the
        # blocking read may spawn `systemctl --user is-active` (bounded, but
        # a frozen UI for its duration), so the event loop only ever calls it
        # with blocking=False (TimerStateCache.peek). The blocking read runs in
        # _probe_disk_pressure_worker, which then asks for a re-render.
        self.disk_pressure = disk_pressure
        self.disk_probing = False
        # Read-only competing-mechanism detection. Same split as
        # disk_pressure: the render path peeks, the worker below does the
        # blocking read that may issue `systemctl list-unit-files`.
        self.competing = competing
        # A predicate, not its result, for the same reason as disk_pressure:
        # the Policies view changes something the Doctor renders, one
        # navigation step away. The PATH audit stays a snapshot on purpose —
        # the process PATH cannot change until the shell restarts.
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
        # The live preview read's failure, and the status line this screen last wrote
        # for it (cleared only while it still holds that copy).
        self._preview_error: str | None = None
        self._read_line: str | None = None
        # Bumped every time an audit worker is actually started; carried on
        # its GlobalsAudited message so a superseded worker's result (one
        # started before a newer request, still running when the newer one
        # lands) is recognisably stale and discarded rather than clobbering
        # fresher state.
        self._globals_audit_generation = 0
        # The service epoch the current audit started at: its findings are
        # dropped when a mutation invalidated the cache meanwhile.
        self._globals_audit_epoch = 0

    def compose_body(self) -> ComposeResult:
        with VerticalScroll(id="doctor-scroll"):
            yield Static(id="doctor-body")

    def enter_view(self) -> None:
        """Re-read the live state on every entry, and re-ask pnpm off the loop.

        Installed screens are suspended, not unmounted: without this, a change
        made in another view would show in Doctor as the state from before it.
        The globals audit needs the same freshness but cannot be taken here
        synchronously, so it is started as a worker and rendered when it lands.
        The screen is mounted before entry, so the first entry starts it too.
        """
        super().enter_view()
        self.query_one("#doctor-scroll", VerticalScroll).focus()
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
        """Take the blocking background-state reads off the event loop.

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
                # Warmed here for the same reason -- the detection
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
        # Position is a decision, pinned by a test: disk pressure follows the PATH items.
        self.guidance = (
            doctor_guidance(self._report, self._duplicate_writers, self._writer_lines)
            + self._disk_pressure_items()
            + self._competing_items()
        )

    def _disk_pressure_items(self) -> list[Guidance]:
        if self.disk_pressure is None:
            return []
        # probe_disk_pressure is already TOTAL over
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
        # would spawn the very systemctl queries the worker moved off it.
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
        body = self.query_one("#doctor-body", Static)
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
        elif report is None or report.known:  # an unread set has nothing to reinstall
            text.append("Press r to reinstall the pnpm-managed global set.", style="yellow")
        if self.globals_invalidate_error is not None and not self.globals_running:
            text.append(
                f"\nversion cache invalidation failed: {self.globals_invalidate_error}",
                style="yellow",
            )
        body.update(text)
        self._sync_read_status()

    def _sync_read_status(self) -> None:
        error = self._preview_error
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
        # Never write rc files the user was not shown (T-21-41): the
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
        # resume that follows renders Doctor once.
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
            # Always posted, even on an exception run_live does not map:
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
        when what is stored changed.

        Each manager's part is stored under its own source, and only when this audit read
        that manager (`known` for pnpm, `bun_known` for bun): an audit replaces evidence only
        for the managers it read, so an unreadable manager keeps its earlier findings and an
        audit that read neither stores nothing.
        """
        service = self._version_refresh
        if service is None:
            return
        changed = False
        for entry in self._node_entries:
            if report.known:
                changed |= service.record_evidence(
                    entry.tool_id,
                    epoch=self._globals_audit_epoch,
                    broken=_smoke_findings(entry.tool_id, report.unhealthy),
                    notes=tuple(
                        PNPM_SPLIT_GROUP.format(names=", ".join(group))
                        for group in report.split_groups
                        if entry.npm_pkg in group
                    ),
                    source="pnpm",
                )
            if report.bun_known:
                changed |= service.record_evidence(
                    entry.tool_id,
                    epoch=self._globals_audit_epoch,
                    broken=_smoke_findings(entry.tool_id, report.bun_unhealthy),
                    source="bun",
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
