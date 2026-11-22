"""The Schedules view: each built-in schedule's state, timing and last result, toggled live."""

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.widgets import DataTable, Static

from installer import cursor_shim, schedules
from installer.diskusage import DiskPressureProbe
from installer.enums import MutationHolder
from installer.modals import CursorModelScreen, ScheduleTimeScreen
from installer.run import CommandError
from installer.sanitize import sanitize_log_line
from installer.systemd_daemon import SCOPE_SYSTEM, CompetingProbe
from installer.ui_common import (
    TIMES_LISTED,
    AppScreen,
    Rows,
    fit,
    highlighted_key,
    run_live,
    sentence,
)

if TYPE_CHECKING:
    from installer.wizard_app import UnifiedApp


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


_LINGER_SENTENCE = (
    "The timer runs while you are logged in. For always-on operation, run"
    " `loginctl enable-linger $USER` yourself; this installer does not run that"
    " command for you, because it is a system-wide setting for the whole account."
)


def _competing_line(competing: CompetingProbe | None) -> str | None:
    """Name a system-scope competitor on the background-cleanup row.

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
      cost as the schedule log read, and it spawns
      no process, unlike the pnpm audit the Doctor runs on a worker. A
      worker here would buy nothing and cost a cross-thread hand-off plus a
      stale-value window on a number whose whole point is being current.
    - The daemon-state half is a `systemctl --user is-active` SUBPROCESS,
      so this path does not run it AT ALL:
      blocking=False makes the closure read TimerStateCache.peek(), which
      never probes. Memoization alone is not the answer, although "it's
      cached" reads like one: a memo still has a cold first read and a TTL
      expiry, and on those a read() blocks the Textual event loop for up to
      systemd_daemon.SYSTEMCTL_QUERY_TIMEOUT (5 s) -- bounded, but a frozen UI. Nor is "move it
      to a worker": the daemon state is not even shown on this line, so a
      worker would add async plumbing to fetch a value nothing renders.

    Failures: probe_disk_pressure is TOTAL over
    filesystem and probe-conversion failure, and any other exception
    propagates uncaught. This guard is the documented second layer over the
    injected closure, the same pairing the adjacent reads use.

    Only a number the probe actually measured is stated: the temp-directory
    usage (measured on macOS too), else -- only when the temp
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
_CHECK_WHAT = (
    "checks for new versions once a day, never changes a tool, and notifies when the list of "
    "outdated tools changes"
)
_CHECK_PERMISSION = (
    "Notifications come from Script Editor: allow them once in System Settings > Notifications."
)
_CHECK_NOTIFIER_LINUX = "notifies: notify-send, on your desktop session"
_CHECK_NOTIFIER_MACOS = "notifies: osascript"
_CHECK_LIMITS_SHORT = "limits: any run may notify; empty resets silently; ok is not delivery"
_CHECK_LIMITS_MORE = (
    "more limits: a changed non-empty list triggers a notification attempt on any run, manual or "
    "catch-up, not once a day; an empty list resets silently; a shrinking list notifies again; "
    "a successful command does not prove delivery; brew tools show only what brew already knows, "
    "the check runs no brew update; a catch-up run at login can notify a day late"
)


_CURSOR_SCHEDULE_ID = "update-cursor-agent"


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
    SchedulesScreen DataTable { height: auto; max-height: 9; }
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
        """Ask whether a user timer manager exists, off the event loop (D-24), and warm the
        competing-mechanism memo the tmp row's detail line only peeks at."""
        reachable = False
        try:
            ctx = self._ctx
            if ctx is not None:
                answer, _error = run_live(lambda: schedules.manager_reachable(ctx))
                reachable = bool(answer)
            if self._inputs.competing is not None:
                with contextlib.suppress(OSError, ValueError, CommandError):
                    self._inputs.competing()
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
            problem = sentence(error or "unknown error").rstrip(".")
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
            else f"Could not read the schedule log: {sentence(self._log_error)}"
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
        interval = 24 if schedule.daily else record.interval
        return schedules.slots(interval, record.start)

    def _cells(self, schedule: schedules.Schedule) -> list[Text]:
        row = self._row_state(schedule)
        word, style = _STATE_CELLS[row.word]
        dim = "dim" if row.word in ("off", "n/a", "unknown") else ""
        record = schedules.record_for(self._state, schedule.id)
        if self._is_linux_tmp(schedule):
            every = "10 min"
        else:
            every = f"{24 if schedule.daily else record.interval}h {record.start}"
        job = "update" if schedule.kind is schedules.JobKind.UPDATE else schedule.label
        upcoming = self._next_text(schedule, row)
        return [
            Text(fit(job, 13), style="bold"),
            Text(fit(self._target(schedule), 12)),
            Text(word, style=style),
            Text(fit(every, 9), style=dim),
            Text(upcoming, style="" if upcoming != "–" else "dim"),
            self._last_cell(schedule.id),
            Text(fit(schedules.RUNNER_NAME, 9, from_left=True), style="dim"),
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
        if schedule.kind is schedules.JobKind.CHECK_UPDATES:
            return "installed"
        return " ".join(name for name, _command in self._managers()) or "none"

    def _managers(self) -> list[tuple[str, str]]:
        ctx = self._ctx
        if ctx is None:
            return []
        return [(name, command) for name, command in _CACHE_PRUNES if ctx.which(name)]

    def _set_detail(self) -> None:
        schedule = self._highlighted_schedule()
        self.detail_text = "" if schedule is None else self._detail(schedule)
        detail = self.query_one("#schedule-detail", Static)
        # The panel keeps the rows it has; the last one ends in `…` when text is cut.
        detail.update(Rows(Text(self.detail_text), max(detail.size.height, 1)))

    def on_resize(self) -> None:
        if self.is_mounted:
            self._set_detail()

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
        elif schedule.kind is schedules.JobKind.CHECK_UPDATES:
            what = _CHECK_WHAT
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
        if schedule.kind is schedules.JobKind.CHECK_UPDATES:
            lines.append(_CHECK_LIMITS_SHORT)
            if self._ctx is not None and self._ctx.platform_os == "macos":
                lines.insert(0, _CHECK_PERMISSION)
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
        if schedule.daily:
            return f"times: daily at {names[0]} (local)"
        if len(names) <= TIMES_LISTED:
            return f"times: {', '.join(names)} (local)"
        interval = schedules.record_for(self._state, schedule.id).interval
        every = "hour" if interval == 1 else f"{interval} hours"
        return f"times: {', '.join(names[:3])} … {names[-1]}, every {every} (local)"

    def _extra_lines(self, schedule: schedules.Schedule) -> list[str]:
        """The row-specific lines: what a cache prune runs, the cursor model, the tmp notes."""
        if schedule.kind is schedules.JobKind.CHECK_UPDATES:
            macos = self._ctx is not None and self._ctx.platform_os == "macos"
            return [_CHECK_NOTIFIER_MACOS if macos else _CHECK_NOTIFIER_LINUX, _CHECK_LIMITS_MORE]
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
        daily = schedule.daily
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
            # Acting here is the user's decision that ends the damaged-state guard.
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
        reason = sentence(error)
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
        daily = schedule.daily
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
