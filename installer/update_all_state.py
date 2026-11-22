"""Link-safe daily update records for schedule rows and the batch executor; starts no process."""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final, cast

from installer import schedules
from installer.atomic import atomic_replace_entry, read_capped
from installer.locations import ensure_dir
from installer.model import TOOL_ID_RE
from installer.update_all import plain_line

LOG_TEXT_LIMIT: Final = 300
STORE_CAP: Final = 64 * 1024
_DATE_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}")
UPDATE_BY: Final[frozenset[str]] = frozenset(
    row.id
    for row in schedules.SCHEDULES
    if row.kind in (schedules.JobKind.UPDATE, schedules.JobKind.UPDATE_ALL)
)


@dataclass(frozen=True)
class UpdatedEntry:
    day: date
    by: str


def read_updated(path: Path) -> tuple[dict[str, UpdatedEntry], bool]:
    try:
        data = read_capped(path, STORE_CAP, follow_symlinks=False)
    except FileNotFoundError:
        return {}, True
    except OSError:
        return {}, False
    try:
        raw: object = json.loads(data.decode("utf-8")) if data is not None else None
        if not isinstance(raw, dict):
            return {}, False
        mapping = cast(dict[str, object], raw)
        version, updated = mapping.get("version"), mapping.get("updated")
        if type(version) is not int or version != 1 or not isinstance(updated, dict):
            return {}, False
        entries: dict[str, UpdatedEntry] = {}
        for key, value in cast(dict[object, object], updated).items():
            if (
                not isinstance(key, str)
                or not TOOL_ID_RE.fullmatch(key)
                or not isinstance(value, dict)
            ):
                return {}, False
            item = cast(dict[str, object], value)
            if set(item) != {"date", "by"}:
                return {}, False
            day, by = item["date"], item["by"]
            if not isinstance(day, str) or not isinstance(by, str):
                return {}, False
            if not _DATE_SHAPE.fullmatch(day) or by not in UPDATE_BY:
                return {}, False
            entries[key] = UpdatedEntry(date.fromisoformat(day), by)
        return entries, True
    except (ValueError, RecursionError, OverflowError):
        return {}, False


def updated_on(entries: Mapping[str, UpdatedEntry], today: date) -> dict[str, str]:
    return {key: entry.by for key, entry in entries.items() if entry.day == today}


def record_updated(path: Path, tool_id: str, *, today: date, by: str) -> None:
    if not TOOL_ID_RE.fullmatch(tool_id) or by not in UPDATE_BY:
        raise ValueError("invalid tool or schedule id")
    entries, _healthy = read_updated(path)
    current = updated_on(entries, today)
    current[tool_id] = by
    payload = {
        key: {"date": today.isoformat(), "by": value} for key, value in sorted(current.items())
    }
    data = (json.dumps({"version": 1, "updated": payload}) + "\n").encode("utf-8")
    if len(data) > STORE_CAP:
        raise OSError("updated-today record exceeds size limit")
    ensure_dir(path.parent)
    atomic_replace_entry(path, data, mode=0o600)


def start_run_log(path: Path) -> None:
    ensure_dir(path.parent)
    atomic_replace_entry(path, b"", mode=0o600)


def append_run_log(path: Path, line: str) -> None:
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    fd = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("run log is not a regular file")
        data = (line + "\n").encode("utf-8")
        written = 0
        while written < len(data):
            count = os.write(fd, data[written:])
            if count == 0:
                raise OSError("run log write made no progress")
            written += count
    finally:
        os.close(fd)


def log_line(now: datetime, tool_id: str, text: str) -> str:
    if not TOOL_ID_RE.fullmatch(tool_id):
        raise ValueError("invalid tool id")
    return f"{now.isoformat(timespec='seconds')} {tool_id} {plain_line(text, LOG_TEXT_LIMIT)}"
