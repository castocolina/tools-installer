"""Timestamped JSON cache of last-known latest versions.

The document lives at ~/.local/state/tools-installer/versions.json and is
written through installer.atomic.atomic_replace_entry. Every persisted timestamp
is read through `_parse_iso`: naive, non-ISO, and implausibly-future values
degrade to "no usable timestamp" rather than crashing the refresh worker or
suppressing checks forever.

The manager snapshot lives under the same envelope's `managers` key and reuses
this module's staleness model rather than inventing a second one. The window
is deliberately SHORTER than the GitHub cache's seven days: a manager report
describes THIS machine's local state, which the user changes far more often
than a repo publishes a release, and the queries are local and cheap rather
than rate-limited. It is bounded rather than zero because a fresh session
should refetch only what is stale, and a burst of tier navigation must not
launch three child processes per view entry.

The snapshot is cached as ONE UNIT, not per manager: the three outdated
queries and the five inventory queries always run together in one pass, so a
per-manager window would add state without removing a single child process
in the common case; and ownership resolution needs the whole inventory at
once, so a partially-refreshed snapshot has no consumer.

A key an older version wrote and this one does not is ignored on load and
dropped by the next save.
"""

from __future__ import annotations

import json
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, cast

from installer.atomic import atomic_replace_entry, read_capped
from installer.locations import ensure_dir
from installer.manager_versions import ManagerVersion, OutdatedReport
from installer.ownership import ManagerInventory

CACHE_CAP: Final = 4 * 1024 * 1024
FUTURE_SKEW = timedelta(minutes=5)
STALE_AFTER = timedelta(days=7)
RETRY_BACKOFF = timedelta(hours=6)
MANAGER_STALE_AFTER = timedelta(hours=6)
MANAGER_RETRY_BACKOFF = timedelta(minutes=30)


def _empty_digest_map() -> dict[str, str]:
    return {}


def _empty_manager_stamps() -> dict[str, str | None]:
    return {}


@dataclass(frozen=True)
class VersionCacheEntry:
    latest_version: str | None
    checked_at: str | None
    failed_at: str | None = None
    digests: Mapping[str, str] = field(default_factory=_empty_digest_map)


@dataclass(frozen=True)
class ManagerSnapshot:
    inventory: ManagerInventory
    outdated: OutdatedReport
    checked_at: str | None
    failed_at: str | None = None
    manager_checked_at: Mapping[str, str | None] = field(default_factory=_empty_manager_stamps)


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
    try:
        aware = parsed.astimezone(UTC)
    except OverflowError:
        return None
    if aware > now + FUTURE_SKEW:
        return None
    return aware


def stamp_time(value: str | None, *, now: datetime) -> datetime | None:
    """Return a validated cache timestamp, normalized to UTC."""
    return _parse_iso(value, now=now)


def attempted_at(entry: VersionCacheEntry | None, *, now: datetime) -> datetime | None:
    """Return the most recent usable attempt timestamp."""
    if entry is None:
        return None
    stamps = (stamp_time(entry.checked_at, now=now), stamp_time(entry.failed_at, now=now))
    return max((stamp for stamp in stamps if stamp is not None), default=None)


def _as_object(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[str, object], value)


_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _digests_from_raw(raw: object) -> dict[str, str]:
    """Decode digests pair-by-pair; a bad pair drops alone, never the whole entry."""
    mapping = _as_object(raw)
    if mapping is None:
        return {}
    digests: dict[str, str] = {}
    for key, value in mapping.items():
        if isinstance(value, str) and _SHA256_HEX.fullmatch(value) is not None:
            digests[key] = value
    return digests


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
    digests = _digests_from_raw(mapping.get("digests"))
    return VersionCacheEntry(
        latest_version=latest,
        checked_at=checked,
        failed_at=failed,
        digests=digests,
    )


def _tools_mapping(raw: object) -> dict[str, object] | None:
    mapping = _as_object(raw)
    if mapping is None:
        return None
    if "tools" in mapping:
        return _as_object(mapping["tools"])
    return mapping


def _read_json(path: Path) -> object | None:
    # Read through a final symlink for merging; the writer replaces it. Nonblocking avoids FIFOs.
    try:
        data = read_capped(path, CACHE_CAP, follow_symlinks=True)
        return json.loads(data.decode("utf-8")) if data is not None else None
    except (OSError, ValueError, RecursionError, OverflowError):
        return None


def _envelope(path: Path) -> dict[str, object] | None:
    mapping = _as_object(_read_json(path))
    if mapping is None or "tools" not in mapping:
        return None
    return mapping


def _existing_managers(path: Path) -> dict[str, object]:
    mapping = _envelope(path)
    if mapping is None:
        return {}
    return _as_object(mapping.get("managers", {})) or {}


def load_version_cache(path: Path) -> dict[str, VersionCacheEntry]:
    """Read the cache. Missing, unreadable, or malformed input yields {} / skips."""
    tools_raw = _tools_mapping(_read_json(path))
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
    """Write the versioned envelope. managers=None preserves the stored key."""
    managers_out = dict(managers) if managers is not None else _existing_managers(path)
    payload = {
        "version": 1,
        "tools": {
            tool_id: {
                "latest_version": entry.latest_version,
                "checked_at": entry.checked_at,
                "failed_at": entry.failed_at,
                "digests": dict(entry.digests),
            }
            for tool_id, entry in cache.items()
        },
        "managers": managers_out,
    }
    data = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    if len(data) > CACHE_CAP:
        raise OSError("version cache exceeds size limit")
    ensure_dir(path.parent)
    try:
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode) if stat.S_ISREG(info.st_mode) else 0o600
    except FileNotFoundError:
        mode = 0o600
    atomic_replace_entry(path, data, mode=mode)


def is_stale(
    entry: VersionCacheEntry | None, *, now: datetime, stale_after: timedelta = STALE_AFTER
) -> bool:
    if entry is None:
        return True
    checked_at = _parse_iso(entry.checked_at, now=now)
    if checked_at is None:
        return True
    return now - checked_at >= stale_after


def should_fetch(
    entry: VersionCacheEntry | None, *, now: datetime, stale_after: timedelta = STALE_AFTER
) -> bool:
    if not is_stale(entry, now=now, stale_after=stale_after):
        return False
    if entry is None:
        return True
    failed_at = _parse_iso(entry.failed_at, now=now)
    return not (failed_at is not None and now - failed_at < RETRY_BACKOFF)


def default_cache_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "versions.json"


def _str_map(raw: object) -> dict[str, str] | None:
    mapping = _as_object(raw)
    if mapping is None:
        return None
    out: dict[str, str] = {}
    for key, value in mapping.items():
        if isinstance(value, str):
            out[key] = value
        else:
            return None
    return out


def _str_set(raw: object) -> frozenset[str] | None:
    if not isinstance(raw, list):
        return None
    names: list[str] = []
    for item in cast(list[object], raw):
        if not isinstance(item, str):
            return None
        names.append(item)
    return frozenset(names)


def _version_map(raw: object) -> dict[str, ManagerVersion] | None:
    mapping = _as_object(raw)
    if mapping is None:
        return None
    out: dict[str, ManagerVersion] = {}
    for key, value in mapping.items():
        item = _as_object(value)
        if item is None:
            return None
        current = item.get("current")
        latest = item.get("latest")
        if current is not None and not isinstance(current, str):
            return None
        if not isinstance(latest, str) or not latest:
            return None
        out[key] = ManagerVersion(current if isinstance(current, str) else None, latest)
    return out


def _decode_inventory(raw: object) -> ManagerInventory:
    mapping = _as_object(raw)
    if mapping is None:
        return ManagerInventory(
            brew_formulae=None,
            brew_casks=None,
            pnpm_globals=None,
            uv_tools=None,
            brew_prefix=None,
        )
    prefix_raw = mapping.get("brew_prefix")
    prefix = Path(prefix_raw) if isinstance(prefix_raw, str) and prefix_raw else None
    return ManagerInventory(
        brew_formulae=_str_map(mapping.get("brew_formulae")),
        brew_casks=_str_map(mapping.get("brew_casks")),
        pnpm_globals=_str_set(mapping.get("pnpm_globals")),
        uv_tools=_str_map(mapping.get("uv_tools")),
        brew_prefix=prefix,
    )


def _decode_outdated(raw: object) -> OutdatedReport:
    mapping = _as_object(raw)
    if mapping is None:
        return OutdatedReport(brew=None, cask=None, pnpm=None, uv=None, greedy=None)
    # A cache written before `greedy` existed reads as no auto-updating cask; JSON null or a
    # malformed value is unknown, so the pass re-reads it (review C-16).
    greedy_raw = mapping.get("greedy", [])
    return OutdatedReport(
        brew=_version_map(mapping.get("brew")),
        cask=_version_map(mapping.get("cask")),
        pnpm=_version_map(mapping.get("pnpm")),
        uv=_version_map(mapping.get("uv")),
        greedy=_str_set(greedy_raw),
    )


def encode_manager_snapshot(snapshot: ManagerSnapshot) -> dict[str, object]:
    inventory = snapshot.inventory
    outdated = snapshot.outdated

    def versions(mapping: Mapping[str, ManagerVersion] | None) -> dict[str, object] | None:
        if mapping is None:
            return None
        return {
            name: {"current": version.current, "latest": version.latest}
            for name, version in mapping.items()
        }

    return {
        "inventory": {
            "brew_formulae": (
                dict(inventory.brew_formulae) if inventory.brew_formulae is not None else None
            ),
            "brew_casks": dict(inventory.brew_casks) if inventory.brew_casks is not None else None,
            "pnpm_globals": (
                sorted(inventory.pnpm_globals) if inventory.pnpm_globals is not None else None
            ),
            "uv_tools": dict(inventory.uv_tools) if inventory.uv_tools is not None else None,
            "brew_prefix": (
                str(inventory.brew_prefix) if inventory.brew_prefix is not None else None
            ),
        },
        "outdated": {
            "brew": versions(outdated.brew),
            "cask": versions(outdated.cask),
            "pnpm": versions(outdated.pnpm),
            "uv": versions(outdated.uv),
            "greedy": sorted(outdated.greedy) if outdated.greedy is not None else None,
        },
        "checked_at": snapshot.checked_at,
        "failed_at": snapshot.failed_at,
        "manager_checked_at": dict(snapshot.manager_checked_at),
    }


def decode_manager_snapshot(raw: object) -> ManagerSnapshot | None:
    mapping = _as_object(raw)
    if mapping is None:
        return None
    checked = mapping.get("checked_at")
    failed = mapping.get("failed_at")
    if checked is not None and not isinstance(checked, str):
        checked = None
    if failed is not None and not isinstance(failed, str):
        failed = None
    return ManagerSnapshot(
        inventory=_decode_inventory(mapping.get("inventory")),
        outdated=_decode_outdated(mapping.get("outdated")),
        checked_at=checked if isinstance(checked, str) else None,
        failed_at=failed if isinstance(failed, str) else None,
        manager_checked_at={
            key: value
            for key, value in (_as_object(mapping.get("manager_checked_at")) or {}).items()
            if isinstance(value, (str, type(None)))
        },
    )


def load_manager_snapshot(path: Path) -> ManagerSnapshot | None:
    envelope = _envelope(path)
    return decode_manager_snapshot(envelope.get("managers")) if envelope is not None else None


def is_manager_stale(snapshot: ManagerSnapshot | None, *, now: datetime) -> bool:
    if snapshot is None:
        return True
    checked_at = _parse_iso(snapshot.checked_at, now=now)
    if checked_at is None:
        return True
    return now - checked_at >= MANAGER_STALE_AFTER


def should_fetch_managers(snapshot: ManagerSnapshot | None, *, now: datetime) -> bool:
    if not is_manager_stale(snapshot, now=now):
        return False
    if snapshot is None:
        return True
    failed_at = _parse_iso(snapshot.failed_at, now=now)
    return not (failed_at is not None and now - failed_at < MANAGER_RETRY_BACKOFF)
