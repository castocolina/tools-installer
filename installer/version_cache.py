"""Timestamped JSON cache of last-known latest versions.

The document lives at ~/.local/state/tools-installer/versions.json and is
written through installer.atomic.atomic_write_text. Every persisted timestamp
is read through `_parse_iso`: naive, non-ISO, and implausibly-future values
degrade to "no usable timestamp" rather than crashing the refresh worker or
suppressing checks forever.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from installer.atomic import atomic_write_text
from installer.locations import ensure_dir

FUTURE_SKEW = timedelta(minutes=5)
STALE_AFTER = timedelta(days=7)
RETRY_BACKOFF = timedelta(hours=6)


@dataclass(frozen=True)
class VersionCacheEntry:
    latest_version: str | None
    checked_at: str | None
    failed_at: str | None = None


def _parse_iso(value: object, *, now: datetime) -> datetime | None:
    """The one place any persisted timestamp is read.

    Returns None (meaning "no usable timestamp") when `value` is not a str,
    when datetime.fromisoformat raises, when the parsed value is naive
    (subtracting it from an aware `now` raises TypeError), or when it is more
    than FUTURE_SKEW ahead of `now` (a clock-skewed or tampered future
    timestamp would otherwise suppress every future check forever). A valid
    aware value is normalized to UTC so a +05:00 offset is arithmetic-compatible
    with an aware-UTC `now`.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    aware = parsed.astimezone(UTC)
    if aware > now + FUTURE_SKEW:
        return None
    return aware


def _as_object(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[str, object], value)


def _str_field(mapping: dict[str, object], key: str) -> str | None | object:
    if key not in mapping:
        return None
    value = mapping[key]
    if value is None or isinstance(value, str):
        return value
    return object()


def _entry_from_raw(raw: object) -> VersionCacheEntry | None:
    mapping = _as_object(raw)
    if mapping is None:
        return None
    latest = _str_field(mapping, "latest_version")
    checked = _str_field(mapping, "checked_at")
    failed = _str_field(mapping, "failed_at")
    if not isinstance(latest, (str, type(None))):
        return None
    if not isinstance(checked, (str, type(None))):
        return None
    if not isinstance(failed, (str, type(None))):
        return None
    return VersionCacheEntry(latest_version=latest, checked_at=checked, failed_at=failed)


def _tools_mapping(raw: object) -> dict[str, object] | None:
    mapping = _as_object(raw)
    if mapping is None:
        return None
    if "tools" in mapping:
        return _as_object(mapping["tools"])
    return mapping


def _existing_managers(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    mapping = _as_object(raw)
    if mapping is None or "tools" not in mapping:
        return {}
    return _as_object(mapping.get("managers", {})) or {}


def load_version_cache(path: Path) -> dict[str, VersionCacheEntry]:
    """Read the cache. Missing, unreadable, or malformed input yields {} / skips."""
    try:
        raw: object = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    tools_raw = _tools_mapping(raw)
    if tools_raw is None:
        return {}
    out: dict[str, VersionCacheEntry] = {}
    for key, value in tools_raw.items():
        entry = _entry_from_raw(value)
        if entry is not None:
            out[key] = entry
    return out


def save_version_cache(
    path: Path,
    cache: Mapping[str, VersionCacheEntry],
    *,
    managers: Mapping[str, object] | None = None,
) -> None:
    """Write the versioned envelope. managers=None preserves the existing key."""
    managers_out = dict(managers) if managers is not None else _existing_managers(path)
    payload = {
        "version": 1,
        "tools": {
            tool_id: {
                "latest_version": entry.latest_version,
                "checked_at": entry.checked_at,
                "failed_at": entry.failed_at,
            }
            for tool_id, entry in cache.items()
        },
        "managers": managers_out,
    }
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")


def is_stale(entry: VersionCacheEntry | None, *, now: datetime) -> bool:
    if entry is None:
        return True
    checked_at = _parse_iso(entry.checked_at, now=now)
    if checked_at is None:
        return True
    return now - checked_at >= STALE_AFTER


def should_fetch(entry: VersionCacheEntry | None, *, now: datetime) -> bool:
    if not is_stale(entry, now=now):
        return False
    if entry is None:
        return True
    failed_at = _parse_iso(entry.failed_at, now=now)
    return not (failed_at is not None and now - failed_at < RETRY_BACKOFF)


def default_cache_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "versions.json"
