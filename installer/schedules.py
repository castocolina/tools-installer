"""The Schedules core: the closed table of built-in schedules, the slot grid, the state file.

Pure: no process is started and every HOME- or XDG-derived path is computed when a
function is called, never held as a module constant.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, cast

from installer import daemon, receipts, runlock, systemd_daemon
from installer.atomic import atomic_write_bytes, atomic_write_text, read_capped
from installer.locations import ensure_dir
from installer.ownership import NATIVE_OWNERS, OS_PACKAGE_OWNER
from installer.receipts import ReceiptArtifact
from installer.run import OutputRunner, Runner, run_captured
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
            ScheduleState(), _warning(str(exc) or "unreadable"), damaged_path(path).exists()
        )
    if raw is None:
        return LoadedState(
            ScheduleState(),
            _warning("not a regular file, or too large"),
            damaged_path(path).exists(),
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
    """Apply `change` to the stored state under the writer lock, so no decision is lost."""
    with runlock.hold(state_lock_path(path)):
        state = change(load_state(path).state)
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
        tmpdir=environ.get("TMPDIR") or tempfile.gettempdir(),
        uid=os.getuid(),
        environ=environ,
        run=run,
        read_output=read_output,
        which=which,
        present=present,
        read_models=read_models,
    )
