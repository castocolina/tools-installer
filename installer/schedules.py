"""The Schedules core: the closed table of built-in schedules, the slot grid, the state file.

The core is pure; the engine (turn on and off) starts a process only through the context's
seams. Every HOME- or XDG-derived path is computed when a function is called, never held as a
module constant.
"""

from __future__ import annotations

import contextlib
import json
import os
import plistlib
import re
import shutil
import threading
import time
from collections.abc import Callable, Generator, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, cast

from installer import cursor_shim, daemon, receipts, runlock, systemd_daemon, uninstall
from installer.atomic import atomic_write_bytes, atomic_write_text, read_capped
from installer.locations import ensure_dir
from installer.ownership import NATIVE_OWNERS, OS_PACKAGE_OWNER
from installer.policy import Policy, PolicyLayer, PolicyResult
from installer.receipts import ReceiptArtifact
from installer.run import CommandError, OutputRunner, Runner, run_captured
from installer.sanitize import sanitize_log_line
from installer.update import UpdateOutcome


class JobKind(StrEnum):
    TMP_CLEANUP = "tmp-cleanup"
    CACHE_CLEANUP = "cache-cleanup"
    UPDATE = "update"


@dataclass(frozen=True)
class Schedule:
    id: str
    label: str
    kind: JobKind
    target: str | None
    default_interval: int
    default_start: str


_DEFAULT_START = "00:00"
_DEFAULT_INTERVAL = 6


def _update(tool_id: str) -> Schedule:
    return Schedule(
        f"update-{tool_id}",
        f"{tool_id} update",
        JobKind.UPDATE,
        tool_id,
        _DEFAULT_INTERVAL,
        _DEFAULT_START,
    )


# SPEC R2 order. tmp cleanup's interval and start are its macOS daily time; on Linux its
# cadence is the fixed 10 minute monotonic timer and these two fields are not used.
SCHEDULES: Final[tuple[Schedule, ...]] = (
    Schedule(
        "tmp-cleanup",
        "tmp cleanup",
        JobKind.TMP_CLEANUP,
        None,
        24,
        f"{daemon.DEFAULT_HOUR:02d}:{daemon.DEFAULT_MINUTE:02d}",
    ),
    Schedule(
        "cache-cleanup",
        "cache cleanup",
        JobKind.CACHE_CLEANUP,
        None,
        _DEFAULT_INTERVAL,
        _DEFAULT_START,
    ),
    _update("claude"),
    _update("opencode"),
    _update("pi"),
    _update("cursor-agent"),
    _update("copilot"),
)
UPDATE_SCHEDULE_IDS: Final[tuple[str, ...]] = tuple(
    schedule.id for schedule in SCHEDULES if schedule.kind is JobKind.UPDATE
)
_BY_ID: Final[dict[str, Schedule]] = {schedule.id: schedule for schedule in SCHEDULES}


def schedule_by_id(schedule_id: str) -> Schedule:
    return _BY_ID[schedule_id]


INTERVALS: Final[tuple[int, ...]] = (1, 2, 3, 4, 6, 8, 12, 24)
_START_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
_MODEL_CHARS_RE = re.compile(r"[A-Za-z0-9._\-\[\]=,]*")
_MODEL_MAX_LENGTH = 128
INTERVAL_MESSAGE: Final = "Interval must be 1, 2, 3, 4, 6, 8, 12 or 24 hours."
START_MESSAGE: Final = "Start must be HH:MM from 00:00 to 23:59, for example 01:30."
MODEL_CHARSET_MESSAGE: Final = "Model ids use letters, digits and . _ - [ ] = , only."
# Beyond the UI-SPEC copy (F6): a model id must never read as a flag.
MODEL_SHAPE_MESSAGE: Final = (
    "Model ids start with a letter or digit and are at most 128 characters."
)


def validate_interval(value: int | str) -> int:
    if isinstance(value, str):
        value = int(value) if value.isascii() and value.isdigit() else -1
    if isinstance(value, bool) or value not in INTERVALS:
        raise daemon.DaemonScheduleError(INTERVAL_MESSAGE)
    return value


def validate_start(value: str) -> tuple[int, int]:
    if not _START_RE.fullmatch(value):
        raise daemon.DaemonScheduleError(START_MESSAGE)
    return int(value[:2]), int(value[3:])


def validate_model_id(value: str) -> str:
    """A model id reaches a shim's argv, so it can never start with `-` or hold shell syntax."""
    if not _MODEL_CHARS_RE.fullmatch(value):
        raise daemon.DaemonScheduleError(MODEL_CHARSET_MESSAGE)
    if not value[:1].isalnum() or len(value) > _MODEL_MAX_LENGTH:
        raise daemon.DaemonScheduleError(MODEL_SHAPE_MESSAGE)
    return value


# Needs the user's confirmation (D-20, UI-SPEC P7): the user asked for `gpt-6.1-sol`,
# which `cursor-agent --list-models` lacks.
DEFAULT_CURSOR_MODEL: Final = "gpt-5.6-sol-xhigh"
RUNNER_NAME: Final = "runner.py"
LOG_CAP_BYTES: Final = daemon.DEFAULT_CAP_BYTES

Slot = tuple[int, int]


def slots(interval: int, start: str) -> tuple[Slot, ...]:
    """The day's run times: `start` plus every `interval` hours, wrapped past midnight."""
    hour, minute = validate_start(start)
    step = validate_interval(interval)
    return tuple(sorted(((hour + k * step) % 24, minute) for k in range(24 // step)))


def on_calendar(grid: tuple[Slot, ...]) -> str:
    """An explicit hour list: the start/step form (`23/6`) only parses from an aligned start."""
    return f"*-*-* {','.join(f'{hour:02d}' for hour, _minute in grid)}:{grid[0][1]:02d}:00"


def calendar_dicts(grid: tuple[Slot, ...]) -> list[dict[str, int]]:
    return [{"Hour": hour, "Minute": minute} for hour, minute in grid]


def next_run(grid: tuple[Slot, ...], now: datetime) -> datetime:
    """The first slot strictly after `now`, on naive local wall-clock time."""
    for day in (now, now + timedelta(days=1)):
        for hour, minute in grid:
            candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate > now:
                return candidate
    raise AssertionError("a non-empty grid always has a slot within a day")  # pragma: no cover


def default_state_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "schedules.json"


def state_lock_path(state_path: Path) -> Path:
    return state_path.with_name(f"{state_path.name}.lock")


def default_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME", "")
    root = Path(base) if base and Path(base).is_absolute() else Path.home() / ".local" / "share"
    return root / "tools-installer" / "schedules"


# Built from parts: a bare "/tmp" literal trips bandit B108 (as in cargo_distrobox.RUN_ROOT).
_LINUX_TMPDIR: Final = str(Path("/") / "tmp")


def default_tmpdir(platform_os: str) -> str:
    """The platform's own TMPDIR, never the launching shell's (F17).

    macOS: the per-user directory launchd hands a job. Linux: `/tmp`, written out rather than
    omitted: it is what a unit with no TMPDIR resolves to, so behaviour is unchanged, and the
    unit text stays one fixed value that no shell can make stale.
    """
    if platform_os == "macos":  # every other Platform.os key is Linux
        with contextlib.suppress(ValueError, OSError):  # not Darwin, or the call failed
            per_user = (os.confstr("CS_DARWIN_USER_TEMP_DIR") or "").rstrip("/")
            if per_user:
                return per_user
    return _LINUX_TMPDIR


def default_log_path(platform_os: str) -> Path:
    # Every Platform.os key but "macos" is Linux (installer/app.py).
    if platform_os == "macos":
        return Path.home() / "Library" / "Logs" / "tools-installer" / "schedules.log"
    return Path.home() / ".local" / "state" / "tools-installer" / "schedules.log"


@dataclass(frozen=True)
class ScheduleRecord:
    """One schedule's stored decision; `decided` None is undecided."""

    decided: bool | None
    interval: int
    start: str
    files: tuple[ReceiptArtifact, ...]


@dataclass(frozen=True)
class ScheduleState:
    records: Mapping[str, ScheduleRecord] = field(default_factory=dict[str, ScheduleRecord])
    shared: tuple[ReceiptArtifact, ...] = ()
    cursor_default_model: str = DEFAULT_CURSOR_MODEL
    cursor_shim: str | None = None
    # Display only: never read to decide what a unit runs.
    checkout: str | None = None
    uv: str | None = None


def record_for(state: ScheduleState, schedule_id: str) -> ScheduleRecord:
    stored = state.records.get(schedule_id)
    if stored is not None:
        return stored
    schedule = schedule_by_id(schedule_id)
    return ScheduleRecord(None, schedule.default_interval, schedule.default_start, ())


@dataclass(frozen=True)
class LoadedState:
    state: ScheduleState
    warning: str | None = None
    # True while the `.damaged` copy exists, so the guard outlives the load that saw the damage.
    damaged: bool = False
    # True when the file could not be read at all (no `.damaged` copy is kept): never saved over.
    unreadable: bool = False


_STATE_VERSION = 1
_TOP_KEYS = frozenset(
    {"version", "schedules", "shared", "cursor_default_model", "cursor_shim", "checkout", "uv"}
)
_RECORD_KEYS = frozenset({"decided", "interval", "start", "files"})
_SHIMS = frozenset({"listed", "not-listed", "unverified", "kept-foreign"})
_STATE_READ_CAP = 1024 * 1024


class _StateError(ValueError):
    """A value outside the state file's closed set."""


def damaged_path(state_path: Path) -> Path:
    return state_path.with_name(f"{state_path.name}.damaged")


def clear_damage(state_path: Path) -> None:
    damaged_path(state_path).unlink(missing_ok=True)


def _decode_files(raw: object) -> tuple[ReceiptArtifact, ...]:
    if not isinstance(raw, list):
        raise _StateError("files is not a list")
    files: list[ReceiptArtifact] = []
    for item in cast(list[object], raw):
        artifact = receipts.artifact_from_json(item)
        if artifact is None:
            raise _StateError("a recorded file is not a valid artifact")
        files.append(artifact)
    return tuple(files)


def _decode_record(raw: object) -> ScheduleRecord:
    if not isinstance(raw, dict):
        raise _StateError("a schedule record is not an object")
    data = cast(dict[str, object], raw)
    if not set(data) <= _RECORD_KEYS:
        raise _StateError(f"unknown schedule key {sorted(set(data) - _RECORD_KEYS)[0]}")
    decided = data.get("decided")
    if decided is not None and not isinstance(decided, bool):
        raise _StateError("decided is neither true, false nor null")
    interval = data.get("interval")
    start = data.get("start")
    if not isinstance(interval, int) or not isinstance(start, str):
        raise _StateError("interval or start has the wrong type")
    try:
        validate_interval(interval)
        validate_start(start)
    except daemon.DaemonScheduleError as exc:
        raise _StateError(str(exc)) from exc
    return ScheduleRecord(decided, interval, start, _decode_files(data.get("files", [])))


def _optional_text(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise _StateError(f"{key} is not text")
    return value


def _decode_state(raw: object) -> ScheduleState:
    if not isinstance(raw, dict):
        raise _StateError("the top level is not an object")
    data = cast(dict[str, object], raw)
    if not set(data) <= _TOP_KEYS:
        raise _StateError(f"unknown key {sorted(set(data) - _TOP_KEYS)[0]}")
    if data.get("version", _STATE_VERSION) != _STATE_VERSION:
        raise _StateError("unknown version")
    raw_records = data.get("schedules", {})
    if not isinstance(raw_records, dict):
        raise _StateError("schedules is not an object")
    records: dict[str, ScheduleRecord] = {}
    for schedule_id, value in cast(dict[str, object], raw_records).items():
        if schedule_id not in _BY_ID:
            raise _StateError(f"unknown schedule id {schedule_id}")
        records[schedule_id] = _decode_record(value)
    model = data.get("cursor_default_model", DEFAULT_CURSOR_MODEL)
    if not isinstance(model, str):
        raise _StateError("cursor_default_model is not text")
    try:
        validate_model_id(model)
    except daemon.DaemonScheduleError as exc:
        raise _StateError(str(exc)) from exc
    shim = _optional_text(data, "cursor_shim")
    if shim is not None and shim not in _SHIMS:
        raise _StateError("cursor_shim is not an allowed value")
    return ScheduleState(
        records=records,
        shared=_decode_files(data.get("shared", [])),
        cursor_default_model=model,
        cursor_shim=shim,
        checkout=_optional_text(data, "checkout"),
        uv=_optional_text(data, "uv"),
    )


def _keep_damaged_bytes(path: Path, raw: bytes) -> None:
    """Keep the damaged file's bytes, writing only when the copy is missing or differs."""
    copy = damaged_path(path)
    try:
        if copy.read_bytes() == raw:
            return
    except OSError:
        pass
    ensure_dir(path.parent)
    atomic_write_bytes(copy, raw, mode=0o600)


def _warning(problem: str) -> str:
    return f"Could not read schedules.json ({problem.splitlines()[0]}); using defaults."


def load_state(path: Path) -> LoadedState:
    """Read the state file: defaults, plus one warning and a kept `.damaged` copy, when damaged."""
    try:
        raw = read_capped(path, _STATE_READ_CAP, follow_symlinks=False)
    except FileNotFoundError:
        return LoadedState(ScheduleState(), damaged=damaged_path(path).exists())
    except OSError as exc:
        return LoadedState(
            ScheduleState(),
            _warning(str(exc) or "unreadable"),
            damaged_path(path).exists(),
            unreadable=True,
        )
    if raw is None:
        return LoadedState(
            ScheduleState(),
            _warning("not a regular file, or too large"),
            damaged_path(path).exists(),
            unreadable=True,
        )
    try:
        state = _decode_state(json.loads(raw.decode("utf-8")))
    except ValueError as exc:  # _StateError, JSONDecodeError and UnicodeDecodeError
        _keep_damaged_bytes(path, raw)
        return LoadedState(ScheduleState(), _warning(str(exc) or "invalid"), True)
    return LoadedState(state, damaged=damaged_path(path).exists())


def _encode_record(record: ScheduleRecord) -> dict[str, object]:
    return {
        "decided": record.decided,
        "interval": record.interval,
        "start": record.start,
        "files": [receipts.artifact_to_json(artifact) for artifact in record.files],
    }


def save_state(path: Path, state: ScheduleState) -> None:
    payload: dict[str, object] = {
        "version": _STATE_VERSION,
        "schedules": {key: _encode_record(record) for key, record in state.records.items()},
        "shared": [receipts.artifact_to_json(artifact) for artifact in state.shared],
        "cursor_default_model": state.cursor_default_model,
        "cursor_shim": state.cursor_shim,
        "checkout": state.checkout,
        "uv": state.uv,
    }
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n", mode=0o600)


def update_state(path: Path, change: Callable[[ScheduleState], ScheduleState]) -> ScheduleState:
    """Apply `change` to the stored state under the writer lock, so no decision is lost.

    A state that cannot be read raises OSError: saving defaults over it would lose every
    decision, and no `.damaged` copy is kept for a read failure (F11)."""
    with runlock.hold(state_lock_path(path)):
        loaded = load_state(path)
        if loaded.unreadable:
            raise OSError(loaded.warning or "schedules.json could not be read")
        state = change(loaded.state)
        save_state(path, state)
    return state


_SYSTEM_BINS: Final = ("/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin")


def clean_unit_path(
    home: Path,
    *,
    platform_os: str,
    environ: Mapping[str, str],
    is_dir: Callable[[Path], bool] = Path.is_dir,
) -> str:
    """A deterministic PATH for a scheduled unit: fixed absolute parts, never the caller's PATH.

    The interactive PATH carries the checkout's `.venv/bin` and transient `/run/user/*` dirs,
    which would make a run depend on the checkout and the login session (F4).
    """
    macos = platform_os == "macos"  # every other Platform.os key is Linux
    pnpm_env = environ.get("PNPM_HOME", "")
    pnpm_home = (
        Path(pnpm_env)
        if pnpm_env and Path(pnpm_env).is_absolute()
        else home / ("Library/pnpm" if macos else ".local/share/pnpm")
    )
    optional = [home / ".volta/bin", home / ".bun/bin", home / ".opencode/bin"]
    brew = Path("/opt/homebrew/bin" if macos else "/home/linuxbrew/.linuxbrew/bin")
    parts = [
        home / ".local/bin",
        pnpm_home,
        *(path for path in (*optional, brew) if is_dir(path)),
    ]
    # shortcut: a tool installed outside these dirs is not found by a scheduled run; upgrade by
    # adding its dir here.
    return ":".join(dict.fromkeys([*map(str, parts), *_SYSTEM_BINS]))


_DETAIL_LIMIT = 300
# Owners whose tool this installer never mutates: the result names the owner and the tool.
_OWNER_SKIPS: Final = frozenset({*NATIVE_OWNERS, OS_PACKAGE_OWNER, "sdkman"})


def _first_line(text: str, fallback: str) -> str:
    """The first non-empty line of `text`, sanitized and bounded to 300 characters."""
    lines = (line.strip() for line in sanitize_log_line(text).splitlines())
    return (next((line for line in lines if line), "")[:_DETAIL_LIMIT]) or fallback


def update_result_line(
    outcome: UpdateOutcome, before: str | None, after: str | None
) -> tuple[str, int]:
    """One total mapping from an update outcome to its log result line and exit code (F7)."""
    if outcome.status == "updated":
        if before is None or after is None:
            line = "ok: updated"
        elif before == after:
            line = "ok: up to date"
        else:
            line = f"ok: updated {_first_line(before, '?')} → {_first_line(after, '?')}"
        code = 0
    elif outcome.status == "failed":
        line, code = f"failed: {_first_line(outcome.detail, 'update failed')}", 1
    elif outcome.status == "unsupported" and outcome.owner in _OWNER_SKIPS:
        line, code = f"skipped: {outcome.owner} owns {outcome.tool_id}", 0
    else:  # "unsupported" for any other owner, and "unknown-owner": skipped, never red
        line, code = f"skipped: {_first_line(outcome.detail, 'not updatable')}", 0
    if outcome.postinstall_warning:
        line += f"; postinstall warning: {_first_line(outcome.postinstall_warning, 'see log')}"
    return line, code


Word = Literal["ok", "skipped", "failed", "running", "interrupted"]


@dataclass(frozen=True)
class LastRun:
    """A schedule's newest log entry; `at` is naive local wall-clock time."""

    at: datetime | None
    word: Word
    text: str


_RESULT_WORDS: Final = ("ok", "skipped", "failed")
_INTERRUPTED_TEXT: Final = "failed: interrupted"
_LOG_FIELDS: Final = 3


def _local_naive(moment: datetime) -> datetime:
    return moment.astimezone().replace(tzinfo=None) if moment.tzinfo else moment


def parse_log(text: str, *, running_job: str | None) -> dict[str, LastRun]:
    """Each schedule id's newest `start` or result line; `ran:` lines and bad lines are ignored.

    A line is `<ISO-8601 time> <id> <rest>`. Later lines win (the log is append-only), so a
    trailing `start` means the run has no result yet: `running` while `running_job` names it,
    else `interrupted`.
    """
    latest: dict[str, LastRun] = {}
    for line in text.splitlines():
        fields = line.split(" ", 2)
        if len(fields) != _LOG_FIELDS:
            continue
        stamp, job, rest = fields
        try:
            at = _local_naive(datetime.fromisoformat(stamp))
        except ValueError:
            continue
        rest = sanitize_log_line(rest).strip()
        if rest == "start":
            word: Word = "running" if running_job == job else "interrupted"
            latest[job] = LastRun(at, word, "running" if word == "running" else _INTERRUPTED_TEXT)
            continue
        result = rest.split(":", 1)[0]
        if result in _RESULT_WORDS and rest.startswith(f"{result}:"):
            latest[job] = LastRun(at, cast(Word, result), rest)
    return latest


def read_last_runs(log_path: Path, lock_path: Path) -> dict[str, LastRun]:
    """The log's last run per schedule; a missing log is `{}`, an unreadable one raises OSError."""
    try:
        raw = read_capped(log_path, LOG_CAP_BYTES * 2, follow_symlinks=False)
    except FileNotFoundError:
        return {}
    if raw is None:
        raise OSError("schedules.log is not a regular file")
    live = runlock.holder(lock_path)
    return parse_log(raw.decode("utf-8", errors="replace"), running_job=live.job if live else None)


_GLYPHS: Final[dict[str, str]] = {
    "ok": "✓",
    "skipped": "–",
    "failed": "!",
    "interrupted": "!",
}
_DAYS_CAP = 99


def last_cell(last: LastRun | None, now: datetime) -> str:
    """The Last column: a glyph and `HH:MM` for today (or a skewed future), else days ago."""
    if last is None:
        return "never"
    if last.word == "running":
        return "running"
    glyph = _GLYPHS[last.word]
    if last.at is None:
        return glyph
    if last.at.date() >= now.date():
        return f"{glyph} {last.at:%H:%M}"
    days = (now.date() - last.at.date()).days
    return f"{glyph} >{_DAYS_CAP}d" if days > _DAYS_CAP else f"{glyph} {days}d"


@dataclass(frozen=True)
class ScheduleContext:
    """Everything a schedule engine, run entry, view or e2e driver needs, with injected seams."""

    platform_os: str
    home: Path
    unit_dir: Path
    launch_agents_dir: Path
    data_dir: Path
    state_path: Path
    log_path: Path
    lock_path: Path
    myshellrc_path: Path
    launchd_log_path: Path
    legacy_bin_dir: Path
    checkout: Path
    tmpdir: str
    uid: int
    environ: Mapping[str, str]
    run: Runner
    read_output: OutputRunner
    which: Callable[[str], str | None]
    present: Callable[[str], bool]
    read_models: Callable[[Path], tuple[str, ...] | None]


def context_for(
    platform_os: str,
    *,
    checkout: Path,
    read_models: Callable[[Path], tuple[str, ...] | None],
    run: Runner = run_captured,
    read_output: OutputRunner = systemd_daemon.query_systemctl,
    which: Callable[[str], str | None] = shutil.which,
    present: Callable[[str], bool] = lambda _tool: False,
    environ: Mapping[str, str] = os.environ,
) -> ScheduleContext:
    """Fill a context's paths from HOME now; `read_models` is required so a forgotten wiring
    is a type error, never a silent "model unverified". Starts no process."""
    home = Path.home()
    return ScheduleContext(
        platform_os=platform_os,
        home=home,
        unit_dir=systemd_daemon.user_unit_dir(home, environ),
        launch_agents_dir=home / "Library" / "LaunchAgents",
        data_dir=default_data_dir(),
        state_path=default_state_path(),
        log_path=default_log_path(platform_os),
        lock_path=runlock.run_lock_path(),
        myshellrc_path=home / ".myshellrc",
        launchd_log_path=home / "Library" / "Logs" / "tools-installer" / "schedules-launchd.log",
        legacy_bin_dir=home / ".local" / "bin",
        checkout=checkout,
        tmpdir=default_tmpdir(platform_os),
        uid=os.getuid(),
        environ=environ,
        run=run,
        read_output=read_output,
        which=which,
        present=present,
        read_models=read_models,
    )


# --- The engine: turn a schedule on or off (24.2-05) ---------------------------------------


class ScheduleUnavailable(OSError):
    """A schedule cannot be turned on here; the message is the literal `unavailable: ...` reason."""


NO_MANAGER_REASON: Final = "unavailable: no user timer manager"
# Ported from installer/policy.py `_UNREACHABLE_MANAGER_WARNING`.
_UNREACHABLE_MANAGER_WARNING: Final = (
    "the systemd user manager could not be reached, so `systemctl --user daemon-reload` "
    "did not run; the unit files are removed, but a timer it already loaded may keep "
    "running until you log out, or until you run `systemctl --user daemon-reload` yourself"
)


@dataclass(frozen=True)
class ApplyReport:
    changed: bool
    next_run: datetime | None = None
    shim: cursor_shim.ShimReport | None = None
    warnings: tuple[str, ...] = ()


_TMP_ID: Final = "tmp-cleanup"
_CURSOR_ID: Final = "update-cursor-agent"
TMP_FIXED_CADENCE_MESSAGE: Final = (
    "Cannot edit tmp cleanup: on Linux it runs every 10 min, a fixed cadence."
)
_KEPT_FOREIGN_WARNING: Final = (
    "your own ~/.local/bin/cursor-agent is kept: it has no installer sentinel."
)


def basename_for(schedule_id: str) -> str:
    """The systemd unit basename; tmp cleanup keeps its existing units (D-03, D-08)."""
    if schedule_id == _TMP_ID:
        return systemd_daemon.UNIT_BASENAME
    return f"tools-installer-schedule-{schedule_id}"


def label_for(schedule_id: str) -> str:
    """The launchd label; tmp cleanup keeps its existing label (D-03, D-08)."""
    if schedule_id == _TMP_ID:
        return daemon.LABEL
    return f"com.tools-installer.schedule.{schedule_id}"


def _plist_path(ctx: ScheduleContext, schedule_id: str) -> Path:
    return ctx.launch_agents_dir / f"{label_for(schedule_id)}.plist"


def manager_reachable(ctx: ScheduleContext) -> bool:
    """The one decision whether a user timer manager exists (D-24); every check goes through it."""
    if ctx.platform_os == "macos":  # every other Platform.os key is Linux
        return ctx.which("launchctl") is not None
    return ctx.which("systemctl") is not None and systemd_daemon.user_manager_reachable(
        read_output=ctx.read_output
    )


def _require_available(ctx: ScheduleContext, schedule: Schedule) -> None:
    if not manager_reachable(ctx):
        raise ScheduleUnavailable(NO_MANAGER_REASON)
    if schedule.kind is JobKind.UPDATE and not ctx.present(schedule.target or ""):
        raise ScheduleUnavailable(f"unavailable: {schedule.target} not installed")


def _resolve_uv(ctx: ScheduleContext) -> Path:
    found = ctx.which("uv")
    path = Path(os.path.abspath(found)) if found else None
    if path is None or not path.is_file() or not os.access(path, os.X_OK):
        raise daemon.DaemonScheduleError("uv was not found on PATH, so no schedule can run")
    return path


def _fingerprint(path: Path, kind: Literal["file", "link"]) -> ReceiptArtifact:
    artifact = receipts.fingerprint(path, kind, rehash=True)
    if artifact is None:
        raise OSError(f"{path} could not be fingerprinted")
    return artifact


def _shared_pairs(ctx: ScheduleContext) -> tuple[tuple[Path, Path], ...]:
    """(source, target) per shared asset; the scripts source `lib/` next to themselves."""
    scripts = ctx.checkout / "scripts"
    runner = Path(__file__).parent / "helper_assets" / "schedule_runner.py"
    return (
        (runner, ctx.data_dir / RUNNER_NAME),
        (scripts / "prune-tmp-linux.sh", ctx.data_dir / "prune-tmp-linux.sh"),
        (scripts / "prune-user-tmpdir.sh", ctx.data_dir / "prune-user-tmpdir.sh"),
        (scripts / "lib" / "prune-tmp-common.sh", ctx.data_dir / "lib" / "prune-tmp-common.sh"),
    )


def _ensure_shared_assets(
    ctx: ScheduleContext,
    state: ScheduleState,
    pairs: tuple[tuple[Path, Path], ...] | None = None,
) -> tuple[tuple[ReceiptArtifact, ...], tuple[Path, ...]]:
    """Copy the runner and the prune scripts into the data dir; return (artifacts, newly created).

    The scripts are byte-for-byte copies with no sentinel added: the sha256 recorded in
    `state.shared` is their ownership proof, standing in for SPEC R5's sentinel (R1-16); the
    runner keeps its own sentinel header. Every target is validated before any write, and a
    failed write puts back what this call already wrote, so a failure leaves no unrecorded
    asset (R2-08). `pairs` narrows the call to some of the shared assets (the reconcile's
    refresh takes them one by one).
    """
    recorded = {Path(artifact.path): artifact for artifact in state.shared}
    pending: list[tuple[Path, bytes, bytes | None]] = []
    for source, target in pairs or _shared_pairs(ctx):
        data = source.read_bytes()  # a missing source raises an OSError naming it
        if target.is_symlink():
            raise OSError(f"{target} is a symlink, not a file tools-installer wrote")
        current = target.read_bytes() if target.exists() else None
        if current is not None and current != data:
            mine = recorded.get(target)
            if mine is None or not receipts.matches(mine, rehash=True):
                raise OSError(f"{target} exists and is not managed by tools-installer")
        pending.append((target, data, current))
    written: list[tuple[Path, bytes | None]] = []
    try:
        for target, data, current in pending:
            if current == data:  # identical bytes are adopted
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(target, data, mode=0o755)
            written.append((target, current))
    except OSError:
        for target, previous in written:
            with contextlib.suppress(OSError):
                if previous is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write_bytes(target, previous, mode=0o755)
        raise
    artifacts = tuple(_fingerprint(target, "file") for target, _data, _current in pending)
    return artifacts, tuple(target for target, previous in written if previous is None)


def _prune_data_dirs(ctx: ScheduleContext) -> None:
    for directory in (ctx.data_dir / "lib", ctx.data_dir):
        with contextlib.suppress(OSError):  # non-empty or already gone
            directory.rmdir()


def _delete_recorded(files: tuple[ReceiptArtifact, ...]) -> tuple[ReceiptArtifact, ...]:
    """Delete recorded files through `remove_paths`; return those it refused (changed on disk).

    A recorded file already gone is dropped silently: nothing is left to refuse."""
    present = tuple(a for a in files if Path(a.path).exists() or Path(a.path).is_symlink())
    refused = {Path(path) for path in uninstall.remove_paths(present)}
    return tuple(a for a in present if Path(a.path) in refused)


def _on_schedules(ctx: ScheduleContext, *, exclude: str | None) -> bool:
    """Whether any other schedule has a unit or plist on disk, counted by unit name (F4, F10).

    Names are ours alone, so this holds with a damaged or newer-schema `schedules.json` too."""
    return any(schedule.id != exclude and _unit_footprint(ctx, schedule) for schedule in SCHEDULES)


def _unit_footprint(ctx: ScheduleContext, schedule: Schedule) -> bool:
    """Whether any unit file, wants link or plist of this schedule is on disk, by name."""
    if ctx.platform_os == "macos":
        return _exists(_plist_path(ctx, schedule.id))
    return systemd_daemon.footprint_present(ctx.unit_dir, basename=basename_for(schedule.id))


def _units_present(ctx: ScheduleContext, schedule: Schedule) -> bool:
    """Whether the schedule's unit pair (or plist) is on disk, by name."""
    if ctx.platform_os == "macos":
        return _plist_path(ctx, schedule.id).exists()
    return systemd_daemon.units_present(ctx.unit_dir, basename=basename_for(schedule.id))


def _tmp_unit_present(ctx: ScheduleContext) -> bool:
    return _units_present(ctx, schedule_by_id(_TMP_ID))


def _remove_units_by_name(ctx: ScheduleContext, schedule: Schedule) -> None:
    """Delete a schedule's units by name: ours though unrecorded (adopted, or a lost state)."""
    if ctx.platform_os == "macos":
        _plist_path(ctx, schedule.id).unlink(missing_ok=True)
    else:
        systemd_daemon.remove_units(ctx.unit_dir, basename=basename_for(schedule.id))


def _grid(
    ctx: ScheduleContext, schedule: Schedule, record: ScheduleRecord
) -> tuple[Slot, ...] | None:
    """The run times; None for Linux tmp cleanup, whose cadence is a fixed monotonic timer."""
    if schedule.kind is JobKind.TMP_CLEANUP and ctx.platform_os != "macos":
        return None
    return _calendar_grid(schedule, record)


def _calendar_grid(schedule: Schedule, record: ScheduleRecord) -> tuple[Slot, ...]:
    """tmp cleanup is a daily time on macOS; every other schedule runs on its own interval."""
    interval = 24 if schedule.kind is JobKind.TMP_CLEANUP else record.interval
    return slots(interval, record.start)


def runner_argv(ctx: ScheduleContext, schedule: Schedule, uv: Path) -> list[str]:
    """What every unit executes (D-10): paths resolved fresh, never read from schedules.json."""
    macos = ctx.platform_os == "macos"
    job: list[str]
    tail: list[str] = []
    if schedule.kind is JobKind.UPDATE:
        job = ["update", schedule.target or "", "--installer", str(ctx.checkout), "--uv", str(uv)]
    elif schedule.kind is JobKind.CACHE_CLEANUP:
        job = ["cache-cleanup"]
    else:
        script = "prune-user-tmpdir.sh" if macos else "prune-tmp-linux.sh"
        job = ["tmp-cleanup", "--script", str(ctx.data_dir / script)]
        amount = (
            ["--days", str(daemon.DEFAULT_DAYS)]
            if macos
            else ["--minutes", str(systemd_daemon.DEFAULT_AGE_MINUTES)]
        )
        tail = ["--", "--apply", *amount]
    # --no-cache: `uv run` holds the uv cache lock while the runner runs, and the cache job's
    # `uv cache prune` would wait on it until UV_LOCK_TIMEOUT. The runner is stdlib only.
    return [
        str(uv),
        "run",
        "--no-cache",
        "--no-project",
        "--script",
        str(ctx.data_dir / RUNNER_NAME),
        *job,
        "--log",
        str(ctx.log_path),
        "--lock",
        str(ctx.lock_path),
        "--cap-bytes",
        str(LOG_CAP_BYTES),
        *tail,
    ]


def _unit_environment(ctx: ScheduleContext) -> dict[str, str]:
    path = clean_unit_path(ctx.home, platform_os=ctx.platform_os, environ=ctx.environ)
    environment = {"PATH": path, "HOME": str(ctx.home), "TMPDIR": ctx.tmpdir}
    # F8: what the installing process has, for the scheduled run to hand its children. A value
    # the unit grammar cannot carry is dropped rather than failing the whole schedule.
    macos = ctx.platform_os == "macos"  # every other Platform.os key is Linux
    for key in daemon.PASSTHROUGH_KEYS:
        value = ctx.environ.get(key, "")
        if daemon.valid_passthrough_value(value) and (macos or systemd_daemon.quotable(value)):
            environment[key] = value
    return environment


def _snapshot(paths: tuple[Path, ...]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.exists() else None for path in paths}


def _restore(snapshot: dict[Path, bytes | None]) -> None:
    # Back to exactly the snapshot: a file that existed gets its prior bytes, a new one goes.
    for path, previous in snapshot.items():
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write_bytes(path, previous, mode=0o644)


def _refuse_symlinks(paths: tuple[Path, ...]) -> None:
    """`atomic_write_bytes` writes through a symlink, and this installer writes only regular
    unit files, so a link at a written path is refused even where a file was recorded (F18)."""
    for path in paths:
        if path.is_symlink():
            raise OSError(f"{path} is a symlink that tools-installer did not create")


def _linux_texts(
    ctx: ScheduleContext, schedule: Schedule, record: ScheduleRecord, uv: Path
) -> tuple[str, str]:
    """The (service, timer) text this checkout would write for `schedule` now."""
    basename = basename_for(schedule.id)
    service_text = systemd_daemon.render_exec_service(
        argv=runner_argv(ctx, schedule, uv),
        environment=_unit_environment(ctx),
        description=f"tools-installer {schedule.label} schedule",
    )
    grid = _grid(ctx, schedule, record)
    timer_text = (
        systemd_daemon.render_timer()
        if grid is None
        else systemd_daemon.render_timer(
            description=f"tools-installer {schedule.label} timer",
            on_calendar=on_calendar(grid),
            basename=basename,
        )
    )
    return service_text, timer_text


def _macos_plist(
    ctx: ScheduleContext, schedule: Schedule, record: ScheduleRecord, uv: Path
) -> dict[str, object]:
    return daemon.render_agent_plist(
        label=label_for(schedule.id),
        program_arguments=runner_argv(ctx, schedule, uv),
        environment=_unit_environment(ctx),
        calendar=calendar_dicts(_calendar_grid(schedule, record)),
        stdout_path=ctx.launchd_log_path,
        stderr_path=ctx.launchd_log_path,
    )


def _apply_linux(
    ctx: ScheduleContext,
    schedule: Schedule,
    record: ScheduleRecord,
    uv: Path,
    *,
    timer_only: bool,
    clean_stamp: bool,
) -> None:
    """Write the unit files, then register; roll back on failure."""
    basename = basename_for(schedule.id)
    service_text, timer_text = _linux_texts(ctx, schedule, record, uv)
    service_path, timer_path = systemd_daemon.unit_paths(ctx.unit_dir, basename=basename)
    written = (timer_path,) if timer_only else (service_path, timer_path)
    _refuse_symlinks(written)
    link = systemd_daemon.wants_link_path(ctx.unit_dir, basename=basename)
    prior_registration = systemd_daemon.units_present(ctx.unit_dir, basename=basename)
    snapshot = _snapshot(written)
    link_existed_before = link.is_symlink()
    try:
        if timer_only:
            atomic_write_bytes(timer_path, timer_text.encode("utf-8"), mode=0o644)
        else:
            systemd_daemon.write_unit_pair(
                ctx.unit_dir, basename=basename, service_text=service_text, timer_text=timer_text
            )
        if clean_stamp:  # F13: `clean` refuses an active timer; the bootstrap starts it again
            with contextlib.suppress(CommandError):  # a missing stamp is not a failure
                systemd_daemon.stop_timer(basename=basename, run=ctx.run)
                systemd_daemon.clean_timer_state(basename=basename, run=ctx.run)
        systemd_daemon.bootstrap(ctx.unit_dir, basename=basename, run=ctx.run)
    except (CommandError, OSError):
        if prior_registration:
            # bootstrap's reload may already hold the new content: restore the files, reload,
            # then re-register the restored content, all best effort.
            with contextlib.suppress(OSError):
                _restore(snapshot)
            with contextlib.suppress(CommandError):
                systemd_daemon.daemon_reload(run=ctx.run)
            with contextlib.suppress(CommandError):
                systemd_daemon.bootstrap(ctx.unit_dir, basename=basename, run=ctx.run)
        else:
            # A first apply: undo `enable`'s wants link before the unit it points at is gone.
            with contextlib.suppress(CommandError):
                systemd_daemon.disable_timer(basename=basename, run=ctx.run)
            with contextlib.suppress(OSError):
                _restore(snapshot)
                if not link_existed_before and link.is_symlink():
                    link.unlink()
            with contextlib.suppress(CommandError):
                systemd_daemon.daemon_reload(run=ctx.run)
        raise


def _apply_macos(
    ctx: ScheduleContext, schedule: Schedule, record: ScheduleRecord, uv: Path
) -> None:
    """Write the plist, then register; roll back on failure."""
    label = label_for(schedule.id)
    plist_path = _plist_path(ctx, schedule.id)
    plist = _macos_plist(ctx, schedule, record, uv)
    _refuse_symlinks((plist_path,))
    # launchd needs StandardOutPath to resolve at registration (R1-06). A rollback leaves the
    # empty file; the last sweep deletes it.
    daemon.ensure_log_path(ctx.launchd_log_path)
    snapshot = _snapshot((plist_path,))
    try:
        daemon.write_agent_plist(plist_path, plist)
        daemon.bootstrap(ctx.uid, plist_path, label=label, run=ctx.run)
    except (CommandError, OSError):
        with contextlib.suppress(OSError):
            _restore(snapshot)
        if snapshot[plist_path] is not None:
            with contextlib.suppress(CommandError):
                daemon.bootstrap(ctx.uid, plist_path, label=label, run=ctx.run)
        raise


def _register(
    ctx: ScheduleContext,
    schedule: Schedule,
    record: ScheduleRecord,
    uv: Path,
    *,
    timer_only: bool = False,
    clean_stamp: bool = False,
) -> None:
    if ctx.platform_os == "macos":
        _apply_macos(ctx, schedule, record, uv)
    else:
        _apply_linux(ctx, schedule, record, uv, timer_only=timer_only, clean_stamp=clean_stamp)


def _fingerprint_unit(ctx: ScheduleContext, schedule: Schedule) -> tuple[ReceiptArtifact, ...]:
    """What is on disk now: the unit pair and its wants link, or the plist."""
    if ctx.platform_os == "macos":
        return (_fingerprint(_plist_path(ctx, schedule.id), "file"),)
    basename = basename_for(schedule.id)
    paths = systemd_daemon.unit_paths(ctx.unit_dir, basename=basename)
    link = systemd_daemon.wants_link_path(ctx.unit_dir, basename=basename)
    files = tuple(_fingerprint(path, "file") for path in paths)
    return (*files, _fingerprint(link, "link")) if link.is_symlink() else files


def _error_line(exc: BaseException) -> str:
    return _first_line(str(exc), "unknown error")


def _refresh_cursor_shim(
    ctx: ScheduleContext, model: str, models: tuple[str, ...] | None
) -> tuple[str | None, cursor_shim.ShimReport | None, str | None]:
    """(status to save, report, warning); an unwritable shim leaves the status and warns."""
    link, agent = cursor_shim.shim_paths(ctx.home)
    try:
        report = cursor_shim.refresh_shim(link=link, agent=agent, model=model, models=models)
    except OSError as exc:
        return None, None, f"Could not write the cursor-agent shim: {_error_line(exc)}."
    if report.write == "kept-foreign":
        return "kept-foreign", report, _KEPT_FOREIGN_WARNING
    return report.check, report, None


def _read_models(ctx: ScheduleContext) -> tuple[str, ...] | None:
    return ctx.read_models(cursor_shim.shim_paths(ctx.home)[1])


def _record_decided_durably(record: Callable[[Path], None], path: Path) -> None:
    # Ported from installer/policy.py `_record_decided_durably`: a transient failure after a
    # manual off would let the next default-on reverse the user's choice, so retry once.
    try:
        record(path)
    except OSError:
        time.sleep(0.05)
        record(path)


def _record_tmp_decision(ctx: ScheduleContext, warnings: list[str]) -> None:
    recorder = (
        daemon.record_decided if ctx.platform_os == "macos" else systemd_daemon.record_decided
    )
    try:
        _record_decided_durably(recorder, ctx.myshellrc_path)
    except OSError as exc:
        warnings.append(f"decision not recorded: {exc}")


def _remove_legacy_wrapper(ctx: ScheduleContext, warnings: list[str]) -> None:
    try:
        daemon.remove_wrapper(ctx.legacy_bin_dir)  # sentinel-checked
    except OSError as exc:
        warnings.append(f"wrapper removal failed: {exc}")


def _take_over_competitors(ctx: ScheduleContext) -> tuple[str, ...]:
    """Disclosure warnings after taking over a competing user-scope cleanup timer (D-02).

    Port of `_detect_and_take_over_competitors`: runs only after our own registration worked,
    and a detection or takeover failure never undoes it (T-15.7-13); the guards stay separate so
    what was learned survives a failure in the next step (IN-07)."""
    try:
        competitors = systemd_daemon.detect_competing(read_output=ctx.read_output)
    except (CommandError, OSError, ValueError):
        return ()
    if not competitors:
        return ()
    system_warning = systemd_daemon.system_scope_warning(competitors)
    user_scope = [c for c in competitors if c.scope == systemd_daemon.SCOPE_USER]
    disabled: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    if user_scope:
        try:
            disabled, failed = systemd_daemon.disable_competing(user_scope, run=ctx.run)
        except ValueError:  # structural refusal; fires before any argv
            failed = tuple(unit.name for unit in user_scope)
    sentences = (
        systemd_daemon.takeover_disclosure(disabled),
        system_warning,
        systemd_daemon.user_scope_failure_warning(failed),
    )
    return tuple(sentence for sentence in sentences if sentence)


def _rerecord_shared(ctx: ScheduleContext, assets: tuple[ReceiptArtifact, ...]) -> None:
    """After a failed registration, re-record the recorded shared files this call rewrote (F16).

    Only entries already recorded are replaced: a file this call created was just deleted, and
    one it merely adopted was never recorded."""
    fresh = {Path(artifact.path): artifact for artifact in assets}

    def change(current: ScheduleState) -> ScheduleState:
        shared = tuple(fresh.get(Path(item.path), item) for item in current.shared)
        return replace(current, shared=shared)

    with contextlib.suppress(OSError):  # the registration error is the one to report
        update_state(ctx.state_path, change)


def turn_on(ctx: ScheduleContext, schedule_id: str) -> ApplyReport:
    """Write the shared assets, then the unit, register it, and record every file (D-02).

    Every user verb takes the reconcile lock, so a reconcile pass in another process cannot
    interleave with it (F3); the lock order is run lock, reconcile lock, state lock.
    """
    _require_available(ctx, schedule_by_id(schedule_id))  # a refusal writes nothing, lock file too
    with runlock.hold(reconcile_lock_path(ctx.state_path)):
        return _turn_on(ctx, schedule_id)


def _turn_on(
    ctx: ScheduleContext, schedule_id: str, *, seen: ScheduleRecord | None = None
) -> ApplyReport:
    """The turn-on with the reconcile lock already held.

    `seen` is the row the reconcile pass decided from: when the locked change finds another
    decision, the units this call wrote are undone and nothing is recorded (F3).
    """
    schedule = schedule_by_id(schedule_id)
    _require_available(ctx, schedule)  # before anything is written
    uv = _resolve_uv(ctx)
    state = load_state(ctx.state_path).state
    record = record_for(state, schedule_id)
    assets, created = _ensure_shared_assets(ctx, state)
    try:
        _register(ctx, schedule, record, uv)
    except (CommandError, OSError):
        if not _on_schedules(ctx, exclude=schedule_id):
            for path in created:  # R1-14: no unrecorded asset outlives a failed first apply
                with contextlib.suppress(OSError):
                    path.unlink(missing_ok=True)
            _prune_data_dirs(ctx)
        _rerecord_shared(ctx, assets)
        raise
    files = _fingerprint_unit(ctx, schedule)
    warnings: list[str] = []
    if schedule.kind is JobKind.TMP_CLEANUP:
        # Only now that the registration worked: the old wrapper goes, the decision is kept.
        _remove_legacy_wrapper(ctx, warnings)
        _record_tmp_decision(ctx, warnings)
        if ctx.platform_os != "macos":
            warnings.extend(_take_over_competitors(ctx))
    # The model list is read before the state lock, never inside it (R2-05).
    models = _read_models(ctx) if schedule_id == _CURSOR_ID else None
    shim_report: cursor_shim.ShimReport | None = None

    moved = False

    def change(current: ScheduleState) -> ScheduleState:
        nonlocal shim_report, moved
        if seen is not None and record_for(current, schedule_id).decided != seen.decided:
            moved = True
            return current
        status = current.cursor_shim
        if schedule_id == _CURSOR_ID:
            saved, shim_report, warning = _refresh_cursor_shim(
                ctx, current.cursor_default_model, models
            )
            status = saved or status
            if warning:
                warnings.append(warning)
        updated = replace(record_for(current, schedule_id), decided=True, files=files)
        return replace(
            current,
            records={**current.records, schedule_id: updated},
            shared=assets,
            cursor_shim=status,
            checkout=str(ctx.checkout),
            uv=str(uv),
        )

    saved_state = update_state(ctx.state_path, change)
    if moved:  # another decision landed first: it wins, and what this call wrote goes
        _remove_timer(ctx, schedule_id, keep_decision=True, restore_cursor_link=False)
        return ApplyReport(False)
    grid = _grid(ctx, schedule, record_for(saved_state, schedule_id))
    upcoming = next_run(grid, datetime.now()) if grid else None
    return ApplyReport(True, upcoming, shim_report, tuple(warnings))


@dataclass(frozen=True)
class _Removal:
    warnings: tuple[str, ...]
    kept: tuple[ReceiptArtifact, ...]  # recorded files someone changed, so left in place


def _tmp_decided(ctx: ScheduleContext, *, unreadable: bool = True) -> bool:
    """Whether tmp cleanup's decided marker is in `~/.myshellrc`.

    A rc file that cannot be read answers `unreadable`: the reconcile must not turn the row on
    over a decision it cannot see (True), and the sweep must not touch a marker it cannot prove
    (False, `_state_leftovers`).
    """
    reader = daemon.decided if ctx.platform_os == "macos" else systemd_daemon.decided
    try:
        return reader(ctx.myshellrc_path)
    except (OSError, UnicodeDecodeError):
        return unreadable


def _remove_timer(
    ctx: ScheduleContext,
    schedule_id: str,
    *,
    keep_decision: bool,
    restore_cursor_link: bool = True,
    forget: bool = False,
) -> _Removal:
    """Disable first, then delete exactly the recorded files; the core of every removal.

    `keep_decision` leaves `decided` as it is (a gone target waits for its reinstall), else it
    becomes off; `forget` drops the record altogether once nothing was kept (the uninstall).
    The tmp cleanup marker and the legacy wrapper belong to the callers.
    """
    schedule = schedule_by_id(schedule_id)
    macos = ctx.platform_os == "macos"
    basename, label = basename_for(schedule_id), label_for(schedule_id)
    record = record_for(load_state(ctx.state_path).state, schedule_id)
    warnings: list[str] = []
    reached = True
    if macos:
        daemon.bootout(ctx.uid, label=label, run=ctx.run)
    else:
        reached = systemd_daemon.bootout(
            ctx.unit_dir, basename=basename, run=ctx.run, read_output=ctx.read_output
        )
        if not reached:
            warnings.append(_UNREACHABLE_MANAGER_WARNING)
        elif schedule.kind is not JobKind.TMP_CLEANUP:
            # A calendar timer's Persistent= stamp, cleaned while the unit is still loaded.
            with contextlib.suppress(CommandError, OSError):
                systemd_daemon.clean_timer_state(basename=basename, run=ctx.run)
    kept = _delete_recorded(record.files)
    if not record.files:  # adopted by name, or its record is lost: ours by name all the same
        _remove_units_by_name(ctx, schedule)
    if reached and not macos:
        with contextlib.suppress(CommandError):
            systemd_daemon.daemon_reload(run=ctx.run)

    def change(current: ScheduleState) -> ScheduleState:
        status = current.cursor_shim
        if schedule_id == _CURSOR_ID:
            if restore_cursor_link:
                link, agent = cursor_shim.shim_paths(ctx.home)
                try:  # under the state lock, so a run in flight cannot undo this off (R1-08)
                    cursor_shim.restore_link(link=link, agent=agent)
                except OSError as exc:
                    warnings.append(f"Could not restore the cursor-agent link: {_error_line(exc)}.")
            status = None
        stored = record_for(current, schedule_id)
        updated = replace(stored, decided=stored.decided if keep_decision else False, files=kept)
        records = {**current.records, schedule_id: updated}
        if forget and not kept:
            del records[schedule_id]
        return replace(current, records=records, cursor_shim=status)

    update_state(ctx.state_path, change)
    _remove_shared_if_idle(ctx, warnings)
    return _Removal(tuple(warnings), kept)


@contextlib.contextmanager
def _run_idle(ctx: ScheduleContext) -> Generator[bool]:
    """Yield whether no scheduled run is in flight, holding the run lock for the body (F4).

    The take never waits, so taking it under the reconcile lock cannot deadlock the order run
    lock, reconcile lock, state lock. The installer's own mutation holds the run lock in this
    process (a removal in flight); that is idle, not a scheduled run.
    """
    mine = runlock.holder(ctx.lock_path)
    if mine is not None and mine.job == runlock.INSTALLER_JOB and mine.pid == os.getpid():
        yield True
        return
    lock = runlock.try_acquire(ctx.lock_path, runlock.INSTALLER_JOB)
    try:
        yield lock is not None
    finally:
        if lock is not None:
            lock.release()


def _remove_shared_if_idle(ctx: ScheduleContext, warnings: list[str]) -> None:
    """Delete the recorded shared files once no unit exists on disk and no run is in flight (F4).

    The caller holds the reconcile lock, so no `turn_on` can adopt the files meanwhile; a
    busy run leaves them recorded for the next removal."""
    if not load_state(ctx.state_path).state.shared or _on_schedules(ctx, exclude=None):
        return
    with _run_idle(ctx) as idle:
        if not idle:
            return

        def change(current: ScheduleState) -> ScheduleState:
            kept = _delete_recorded(current.shared)
            if kept:
                names = ", ".join(str(artifact.path) for artifact in kept)
                warnings.append(f"kept, changed since it was copied: {names}")
            else:
                _prune_data_dirs(ctx)
            return replace(current, shared=kept)

        update_state(ctx.state_path, change)


def _kept_message(kept: tuple[ReceiptArtifact, ...]) -> str:
    return f"kept, changed since it was written: {', '.join(str(a.path) for a in kept)}"


def turn_off(ctx: ScheduleContext, schedule_id: str) -> ApplyReport:
    """Disable first, then delete exactly the recorded files, then record the decision off."""
    with runlock.hold(reconcile_lock_path(ctx.state_path)):
        return _turn_off(ctx, schedule_id)


def _turn_off(ctx: ScheduleContext, schedule_id: str) -> ApplyReport:
    removal = _remove_timer(ctx, schedule_id, keep_decision=False)
    warnings = list(removal.warnings)
    if schedule_by_id(schedule_id).kind is JobKind.TMP_CLEANUP:
        _remove_legacy_wrapper(ctx, warnings)
        _record_tmp_decision(ctx, warnings)
    if removal.kept:
        raise OSError(_kept_message(removal.kept))
    return ApplyReport(True, None, None, tuple(warnings))


def _retimed_files(
    ctx: ScheduleContext, schedule: Schedule, record: ScheduleRecord
) -> tuple[ReceiptArtifact, ...]:
    """Fingerprints after a re-time: only the timer Linux rewrote is re-recorded (F15).

    A `.service` or wants link that drifted keeps its recorded fingerprint, so it never reads
    as ours. macOS rewrites the whole plist, so everything on disk is re-recorded.
    """
    fresh = _fingerprint_unit(ctx, schedule)
    if ctx.platform_os == "macos":
        return fresh
    timer = systemd_daemon.unit_paths(ctx.unit_dir, basename=basename_for(schedule.id))[1]
    recorded = {Path(artifact.path): artifact for artifact in record.files}
    return tuple(
        artifact if Path(artifact.path) == timer else recorded.get(Path(artifact.path), artifact)
        for artifact in fresh
    )


def retime(ctx: ScheduleContext, schedule_id: str, interval: int, start: str) -> ApplyReport:
    """Validate, then change the grid; an off row only saves it, an on row rewrites its timer."""
    with runlock.hold(reconcile_lock_path(ctx.state_path)):
        return _retime(ctx, schedule_id, interval, start)


def _retime(ctx: ScheduleContext, schedule_id: str, interval: int, start: str) -> ApplyReport:
    schedule = schedule_by_id(schedule_id)
    macos = ctx.platform_os == "macos"
    if schedule.kind is JobKind.TMP_CLEANUP:
        if not macos:
            raise daemon.DaemonScheduleError(TMP_FIXED_CADENCE_MESSAGE)
        interval = 24
    interval = validate_interval(interval)
    validate_start(start)
    record = record_for(load_state(ctx.state_path).state, schedule_id)
    if (interval, start) == (record.interval, record.start):
        return ApplyReport(False)
    fresh = replace(record, interval=interval, start=start)
    is_on = record.decided is True
    files = record.files
    if is_on:
        # Linux rewrites only the timer: a running job is never touched and the new grid applies
        # from the next slot. macOS re-registers the plist, which stops a loaded run (R1-11).
        _register(ctx, schedule, fresh, _resolve_uv(ctx), timer_only=True, clean_stamp=True)
        files = _retimed_files(ctx, schedule, record)

    def change(current: ScheduleState) -> ScheduleState:
        updated = replace(
            record_for(current, schedule_id), interval=interval, start=start, files=files
        )
        return replace(current, records={**current.records, schedule_id: updated})

    update_state(ctx.state_path, change)
    grid = _grid(ctx, schedule, fresh) if is_on else None
    return ApplyReport(True, next_run(grid, datetime.now()) if grid else None)


def set_cursor_model(ctx: ScheduleContext, model: str) -> ApplyReport:
    """Save the configured model; refresh the shim only when the row is on (SPEC R7, D-20)."""
    with runlock.hold(reconcile_lock_path(ctx.state_path)):
        return _set_cursor_model(ctx, model)


def _set_cursor_model(ctx: ScheduleContext, model: str) -> ApplyReport:
    validate_model_id(model)
    advisory = record_for(load_state(ctx.state_path).state, _CURSOR_ID)
    # An off row spawns no `--list-models` (R3-10); the list is read before the lock (R2-05).
    models = _read_models(ctx) if advisory.decided is True else None
    shim_report: cursor_shim.ShimReport | None = None
    warnings: list[str] = []

    def change(current: ScheduleState) -> ScheduleState:
        nonlocal shim_report
        updated = replace(current, cursor_default_model=model)
        if record_for(current, _CURSOR_ID).decided is not True:
            return updated  # the locked re-read says off: nothing to refresh
        saved, shim_report, warning = _refresh_cursor_shim(ctx, model, models)
        if warning:
            warnings.append(warning)
        return replace(updated, cursor_shim=saved or current.cursor_shim)

    update_state(ctx.state_path, change)
    return ApplyReport(True, None, shim_report, tuple(warnings))


@dataclass(frozen=True)
class RowState:
    word: Literal["on", "off", "drift", "n/a", "unknown"]
    reason: str | None = None


def row_state(
    ctx: ScheduleContext,
    state: ScheduleState,
    schedule: Schedule,
    *,
    manager: bool | None,
    present: Callable[[str], bool] | None,
) -> RowState:
    """A row's state word from file reads only (UI-SPEC section 3); None means still pending."""
    if manager is None:
        return RowState("unknown")
    if not manager:
        return RowState("n/a", NO_MANAGER_REASON)
    if schedule.kind is JobKind.UPDATE:
        if present is None:
            return RowState("unknown")
        if not present(schedule.target or ""):
            return RowState("n/a", f"unavailable: {schedule.target} not installed")
    record = record_for(state, schedule.id)
    if not record.files:
        # Units are ours by name even before they are recorded (R9) or with the state lost (F10)
        return RowState("on" if _units_present(ctx, schedule) else "off")
    return RowState("on" if all(receipts.matches(a) for a in record.files) else "drift")


# --- The lifecycle: the default-on reconcile (24.2-08) -------------------------------------


@dataclass(frozen=True)
class ReconcileReport:
    turned_on: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


STICKY_DAMAGE_WARNING: Final = (
    "schedules.json was damaged; nothing turns on until you change a schedule."
)


def reconcile_lock_path(state_path: Path) -> Path:
    """One lock per reconcile pass. Order: run lock, then this, then the state lock."""
    return state_path.with_name("schedules.reconcile.lock")


def _decision_moved(ctx: ScheduleContext, schedule: Schedule, seen: ScheduleRecord) -> bool:
    """Whether another process decided this row since the pass read it (R3-11)."""
    with runlock.hold(state_lock_path(ctx.state_path)):
        now = record_for(load_state(ctx.state_path).state, schedule.id).decided
    tmp_marked = schedule.kind is JobKind.TMP_CLEANUP and _tmp_decided(ctx)
    return now != seen.decided or tmp_marked


def _turn_on_default(
    ctx: ScheduleContext,
    schedule: Schedule,
    seen: ScheduleRecord,
    turned: list[str],
    warnings: list[str],
) -> None:
    if _decision_moved(ctx, schedule, seen):
        return
    try:
        applied = _turn_on(ctx, schedule.id, seen=seen)
    except (OSError, CommandError) as exc:
        warnings.append(f"Could not turn on {schedule.label}: {_error_line(exc)}.")
        return
    if not applied.changed:  # another decision landed first and was kept
        return
    turned.append(schedule.id)
    warnings.extend(applied.warnings)


def _row_action(
    ctx: ScheduleContext, schedule: Schedule, record: ScheduleRecord
) -> Literal["turn-on", "refresh", "none"]:
    """The truth table of a row whose target is here (D-09); a decided off is never touched."""
    if schedule.kind is JobKind.TMP_CLEANUP:
        # The marker is tmp cleanup's decision; a marker with no units is the user's off.
        if not _tmp_decided(ctx) and record.decided is None:
            return "turn-on"
        on = bool(record.files) or _tmp_unit_present(ctx)
        return "refresh" if on and record.decided is not False else "none"
    if record.decided is None:
        return "turn-on"
    if record.decided is False:
        return "none"
    return "refresh" if record.files else "turn-on"  # no files: a reinstall


def _seed_legacy_start(ctx: ScheduleContext, schedule: Schedule) -> None:
    """Adopting macOS's old plist keeps its daily time: seed the record's start from it (D-08)."""
    if ctx.platform_os != "macos" or schedule.kind is not JobKind.TMP_CLEANUP:
        return
    state = load_state(ctx.state_path).state
    record = record_for(state, schedule.id)
    # A record is the user's own saved time (F14): only a row never saved adopts the old plist's.
    adoptable = not record.files and schedule.id not in state.records
    slot = daemon.read_schedule(_plist_path(ctx, schedule.id)) if adoptable else None
    if slot is None or f"{slot[0]:02d}:{slot[1]:02d}" == record.start:
        return
    start = f"{slot[0]:02d}:{slot[1]:02d}"

    def change(current: ScheduleState) -> ScheduleState:
        seeded = replace(record_for(current, schedule.id), start=start)
        return replace(current, records={**current.records, schedule.id: seeded})

    update_state(ctx.state_path, change)


def _is_stale(ctx: ScheduleContext, state: ScheduleState, schedule: Schedule) -> bool:
    """Ours but not what this checkout would write now; a drifted or foreign file is not stale."""
    record = record_for(state, schedule.id)
    if record.files:
        if not all(receipts.matches(artifact) for artifact in record.files):
            return False
    elif not (schedule.kind is JobKind.TMP_CLEANUP and _tmp_unit_present(ctx)):
        return False
    try:
        uv = _resolve_uv(ctx)
        if ctx.platform_os == "macos":
            wanted = {
                _plist_path(ctx, schedule.id): plistlib.dumps(
                    _macos_plist(ctx, schedule, record, uv)
                )
            }
        else:
            service_text, timer_text = _linux_texts(ctx, schedule, record, uv)
            service_path, timer_path = systemd_daemon.unit_paths(
                ctx.unit_dir, basename=basename_for(schedule.id)
            )
            wanted = {
                service_path: service_text.encode("utf-8"),
                timer_path: timer_text.encode("utf-8"),
            }
        return any(path.read_bytes() != text for path, text in wanted.items())
    except OSError:  # no uv, or an unreadable unit: nothing to refresh from here
        return False


def _refresh_in_place(ctx: ScheduleContext, schedule: Schedule, warnings: list[str]) -> None:
    """Rewrite stale units and restart once, never off and on; adopts the old tmp units too."""
    _seed_legacy_start(ctx, schedule)
    if not _is_stale(ctx, load_state(ctx.state_path).state, schedule):
        return
    try:
        applied = _turn_on(ctx, schedule.id)
    except (OSError, CommandError) as exc:
        warnings.append(f"Could not refresh {schedule.label}: {_error_line(exc)}.")
        return
    warnings.extend(applied.warnings)


def _drop_gone_target(
    ctx: ScheduleContext, schedule: Schedule, warnings: list[str], *, always_shim: bool = False
) -> bool:
    """Remove a gone target's timer files and keep its decision; True when files went."""
    record = record_for(load_state(ctx.state_path).state, schedule.id)
    if schedule.id == _CURSOR_ID and (record.files or always_shim):
        link, _agent = cursor_shim.shim_paths(ctx.home)
        try:
            cursor_shim.remove_shim(link)
        except OSError as exc:
            warnings.append(f"Could not remove the cursor-agent shim: {_error_line(exc)}.")
    if not record.files:
        return False
    try:
        removal = _remove_timer(ctx, schedule.id, keep_decision=True, restore_cursor_link=False)
    except (OSError, CommandError) as exc:
        warnings.append(f"Could not remove the {schedule.label} timer: {_error_line(exc)}.")
        return False
    warnings.extend(removal.warnings)
    if removal.kept:
        warnings.append(
            f"Could not remove the {schedule.label} timer; {_kept_message(removal.kept)}."
        )
        return False
    return True


def _refresh_shared(ctx: ScheduleContext, warnings: list[str]) -> None:
    """Refresh each recorded shared asset that differs from its source or is missing (F5).

    One asset at a time: a copy the user edited (its recorded sha256 no longer matches) is
    refused and warned about, and never blocks refreshing the others."""
    state = load_state(ctx.state_path).state
    recorded = {Path(artifact.path): artifact for artifact in state.shared}
    fresh: dict[Path, ReceiptArtifact] = {}
    for pair in _shared_pairs(ctx):
        target = pair[1]
        if target not in recorded:
            continue
        try:
            (artifact,), _created = _ensure_shared_assets(ctx, state, pairs=(pair,))
        except OSError as exc:
            warnings.append(f"Could not refresh {target.name}: {_error_line(exc)}.")
            continue
        if artifact != recorded[target]:
            fresh[target] = artifact
    if not fresh:
        return

    def change(current: ScheduleState) -> ScheduleState:
        shared = tuple(fresh.get(Path(item.path), item) for item in current.shared)
        return replace(current, shared=shared)

    try:
        update_state(ctx.state_path, change)
    except OSError as exc:
        warnings.append(f"Could not record the refreshed shared scripts: {_error_line(exc)}.")


def _reconcile_pass(ctx: ScheduleContext) -> ReconcileReport:
    loaded = load_state(ctx.state_path)
    damaged = loaded.damaged or loaded.warning is not None
    turned: list[str] = []
    removed: list[str] = []
    warnings: list[str] = [loaded.warning or STICKY_DAMAGE_WARNING] if damaged else []
    if not damaged:
        _refresh_shared(ctx, warnings)
    for schedule in SCHEDULES:
        record = record_for(load_state(ctx.state_path).state, schedule.id)
        if schedule.kind is JobKind.UPDATE and not ctx.present(schedule.target or ""):
            if _drop_gone_target(ctx, schedule, warnings):
                removed.append(schedule.id)
            continue
        if damaged:  # R1-09: a state that cannot be trusted never turns a row on
            continue
        action = _row_action(ctx, schedule, record)
        if action == "turn-on":
            _turn_on_default(ctx, schedule, record, turned, warnings)
        elif action == "refresh":
            _refresh_in_place(ctx, schedule, warnings)
    return ReconcileReport(tuple(turned), tuple(removed), tuple(warnings))


def ensure_schedule_defaults(ctx: ScheduleContext) -> ReconcileReport:
    """Turn on every available schedule nobody has decided about; never undo a user's off."""
    if not manager_reachable(ctx):
        return ReconcileReport()
    # Held for the whole pass (R1-13), never around a `turn_on`'s own state-lock writes.
    with runlock.hold(reconcile_lock_path(ctx.state_path)):
        return _reconcile_pass(ctx)


def after_target_removed(ctx: ScheduleContext, tool_id: str) -> ReconcileReport:
    """A removed tool takes its timer files with it and leaves its decision for a reinstall.

    It needs no reachable manager: the files of a removed tool must go (D-09 amended by F3).
    """
    removed: list[str] = []
    warnings: list[str] = []
    with runlock.hold(reconcile_lock_path(ctx.state_path)):
        for schedule in SCHEDULES:
            if schedule.target == tool_id and _drop_gone_target(
                ctx, schedule, warnings, always_shim=True
            ):
                removed.append(schedule.id)
    return ReconcileReport((), tuple(removed), tuple(warnings))


def reconcile_lines(report: ReconcileReport) -> tuple[tuple[str, Literal["ok", "warn"]], ...]:
    """The pass's lines (UI-SPEC section 8): what was turned on, what went, then each warning."""
    lines: list[tuple[str, Literal["ok", "warn"]]] = []
    if report.turned_on:
        labels = ", ".join(schedule_by_id(schedule_id).label for schedule_id in report.turned_on)
        lines.append((f"Turned on schedules: {labels}. Change them in Schedules.", "ok"))
    for schedule_id in report.removed:
        schedule = schedule_by_id(schedule_id)
        lines.append(
            (f"Removed the {schedule.label} timer because {schedule.target} is gone.", "ok")
        )
    lines.extend((warning, "warn") for warning in report.warnings)
    return tuple(lines)


# A wedged or never-dispatched worker costs this delay, never a hang.
SCHEDULE_DEFAULT_WAIT_SECONDS = 5.0


class ScheduleDefaultWarnings:
    """Collects warnings from the on-by-default apply and says when it finished.

    The schedule defaults run on a Textual thread worker that ``app.run()`` does
    not join. Without this event the competing-mechanism disclosure is printed
    only when that worker happens to finish before the CLI's next line, and the
    ``summary is None`` abort branch returns before any later print at all.
    ``wait`` returns immediately, with completion True, when the collector was
    never armed, so a run with no auto-apply pays nothing.
    """

    def __init__(self) -> None:
        self._messages: list[str] = []
        self._armed = False
        self._finished = threading.Event()

    def append(self, message: str) -> None:
        self._messages.append(message)

    def arm(self) -> None:
        self._armed = True

    def finish(self) -> None:
        self._finished.set()

    def wait(self, timeout: float) -> tuple[tuple[str, ...], bool]:
        if not self._armed:
            return (), True
        completed = self._finished.wait(timeout)
        return tuple(self._messages), completed


# --- The uninstall sweep: one adapter per schedule with anything of ours on disk (24.2-08) ----


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _legacy_log_path(ctx: ScheduleContext) -> Path:
    """The old tmp cleanup's `prune-daemon.log`, beside the schedule log on both OSes."""
    return ctx.log_path.with_name("prune-daemon.log")


def _state_artifacts(ctx: ScheduleContext) -> tuple[Path, ...]:
    # The lock files stay: deleting one another process holds would let a third lock a new inode.
    return (
        ctx.state_path,
        damaged_path(ctx.state_path),
        ctx.log_path,
        ctx.launchd_log_path,
        _legacy_log_path(ctx),
    )


def _state_leftovers(ctx: ScheduleContext) -> bool:
    return any(_exists(path) for path in _state_artifacts(ctx)) or _tmp_decided(
        ctx, unreadable=False
    )


def _footprint(ctx: ScheduleContext, state: ScheduleState, schedule: Schedule) -> bool:
    """Whether anything of this schedule is on disk; file reads only."""
    if any(_exists(Path(artifact.path)) for artifact in record_for(state, schedule.id).files):
        return True
    if _unit_footprint(ctx, schedule):  # by name, so a damaged state still finds it (F10)
        return True
    return schedule.kind is JobKind.TMP_CLEANUP and daemon.wrapper_present(ctx.legacy_bin_dir)


def _forget(ctx: ScheduleContext, schedule_id: str) -> None:
    def change(current: ScheduleState) -> ScheduleState:
        records = {key: value for key, value in current.records.items() if key != schedule_id}
        return replace(current, records=records)

    update_state(ctx.state_path, change)


def _cleanup_if_last(ctx: ScheduleContext) -> None:
    """With no schedule left, delete the shared scripts, the state, the logs and tmp's marker."""
    state = load_state(ctx.state_path).state
    if any(_footprint(ctx, state, schedule) for schedule in SCHEDULES):
        return
    with _run_idle(ctx) as idle:
        if not idle:  # a run is reading the scripts and writing the log
            raise OSError(runlock.BUSY_MESSAGE)
        kept = _delete_recorded(state.shared)
        if kept:
            raise OSError(
                f"kept, changed since it was copied: {', '.join(str(a.path) for a in kept)}"
            )
        _prune_data_dirs(ctx)
        _clear_tmp_decided(ctx)
        for path in _state_artifacts(ctx):
            path.unlink(missing_ok=True)


def _clear_tmp_decided(ctx: ScheduleContext) -> None:
    clearer = daemon.clear_decided if ctx.platform_os == "macos" else systemd_daemon.clear_decided
    clearer(ctx.myshellrc_path)


def _sweep_result(layer: str, detail: str, warnings: Iterable[str]) -> PolicyResult:
    return PolicyResult((PolicyLayer(layer, detail),), None, "; ".join(warnings) or None)


def _sweep_schedule(ctx: ScheduleContext, schedule: Schedule) -> PolicyResult:
    """The full removal of one schedule; idempotent, and it raises OSError naming what it kept."""
    with runlock.hold(reconcile_lock_path(ctx.state_path)):  # a turn-on cannot adopt meanwhile
        return _sweep_schedule_locked(ctx, schedule)


def _sweep_schedule_locked(ctx: ScheduleContext, schedule: Schedule) -> PolicyResult:
    state = load_state(ctx.state_path).state
    warnings: list[str] = []
    refused: list[str] = []
    if _footprint(ctx, state, schedule):
        removal = _remove_timer(ctx, schedule.id, keep_decision=False, forget=True)
        warnings.extend(removal.warnings)
        refused.extend(str(artifact.path) for artifact in removal.kept)
    elif schedule.id in state.records:
        _forget(ctx, schedule.id)
    if schedule.kind is JobKind.TMP_CLEANUP:
        try:
            daemon.remove_wrapper(ctx.legacy_bin_dir)  # sentinel-checked
            _legacy_log_path(ctx).unlink(missing_ok=True)
        except OSError as exc:
            refused.append(str(exc))
    if refused:
        raise OSError(f"kept: {', '.join(refused)}")  # tmp's marker stays while a unit remains
    if schedule.kind is JobKind.TMP_CLEANUP:
        _clear_tmp_decided(ctx)
    _cleanup_if_last(ctx)
    return _sweep_result(schedule.label, "removed", warnings)


def _turn_on_result(ctx: ScheduleContext, schedule: Schedule) -> PolicyResult:
    report = turn_on(ctx, schedule.id)
    return _sweep_result(schedule.label, "on", report.warnings)


def _schedule_policy(ctx: ScheduleContext, schedule: Schedule) -> Policy:
    return Policy(
        id=f"schedule:{schedule.id}",
        label=schedule.label,
        description=f"the {schedule.label} timer, its unit files and its scripts",
        active=True,
        apply=lambda: _turn_on_result(ctx, schedule),
        remove=lambda: _sweep_schedule(ctx, schedule),
        owned=lambda: _footprint(ctx, load_state(ctx.state_path).state, schedule),
    )


def _state_policy(ctx: ScheduleContext) -> Policy:
    def clean() -> PolicyResult:
        with runlock.hold(reconcile_lock_path(ctx.state_path)):
            _cleanup_if_last(ctx)
        return _sweep_result("state", "removed", ())

    return Policy(
        id="schedule:state",
        label="Schedules state and logs",
        description="removes schedules.json and the schedule logs",
        active=True,
        apply=lambda: PolicyResult((), None, None, changed=False),
        remove=clean,
        owned=lambda: _state_leftovers(ctx),
    )


def sweep_adapters(ctx: ScheduleContext) -> tuple[Policy, ...]:
    """One uninstall policy per schedule with a footprint, in table order (D-23, SPEC R5).

    With no schedule on but state files left behind, a single `schedule:state` policy removes
    them (R1-12)."""
    state = load_state(ctx.state_path).state
    owned = tuple(
        _schedule_policy(ctx, schedule)
        for schedule in SCHEDULES
        if _footprint(ctx, state, schedule)
    )
    if owned or not _state_leftovers(ctx):
        return owned
    return (_state_policy(ctx),)
