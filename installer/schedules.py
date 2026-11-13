"""The Schedules core: the closed table of built-in schedules, the slot grid, the state file.

Pure: no process is started and every HOME- or XDG-derived path is computed when a
function is called, never held as a module constant.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

from installer import daemon, receipts, runlock
from installer.atomic import atomic_write_bytes, atomic_write_text, read_capped
from installer.locations import ensure_dir
from installer.receipts import ReceiptArtifact


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

# Needs the user's confirmation (D-20, UI-SPEC P7): the user asked for `gpt-6.1-sol`,
# which `cursor-agent --list-models` lacks.
DEFAULT_CURSOR_MODEL: Final = "gpt-5.6-sol-xhigh"
RUNNER_NAME: Final = "runner.py"
LOG_CAP_BYTES: Final = daemon.DEFAULT_CAP_BYTES

Slot = tuple[int, int]


def slots(interval: int, start: str) -> tuple[Slot, ...]:
    """The day's run times: `start` plus every `interval` hours, wrapped past midnight."""
    hour, minute = int(start[:2]), int(start[3:])
    return tuple(sorted(((hour + k * interval) % 24, minute) for k in range(24 // interval)))


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
    if not isinstance(interval, int) or isinstance(interval, bool) or interval not in INTERVALS:
        raise _StateError("interval is not an allowed value")
    start = data.get("start")
    if not isinstance(start, str) or not _START_RE.fullmatch(start):
        raise _StateError("start is not HH:MM")
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
