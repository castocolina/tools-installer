import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from installer.manager_versions import ManagerVersion, OutdatedReport
from installer.ownership import ManagerInventory
from installer.version_cache import (
    RETRY_BACKOFF,
    STALE_AFTER,
    ManagerSnapshot,
    VersionCacheEntry,
    decode_manager_snapshot,
    default_cache_path,
    encode_manager_snapshot,
    is_manager_stale,
    is_stale,
    load_version_cache,
    save_version_cache,
    should_fetch,
)


def test_round_trip_through_the_versioned_envelope(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    entry = VersionCacheEntry(
        latest_version="v1.6.0",
        checked_at="2026-09-01T00:00:00+00:00",
        failed_at=None,
    )
    save_version_cache(path, {"codegraph": entry})
    raw = json.loads(path.read_text())
    assert raw["version"] == 1
    assert raw["managers"] == {}
    assert raw["tools"]["codegraph"]["latest_version"] == "v1.6.0"
    assert raw["tools"]["codegraph"]["checked_at"] == "2026-09-01T00:00:00+00:00"
    loaded = load_version_cache(path)
    assert loaded["codegraph"] == entry


def test_legacy_flat_mapping_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    path.write_text(
        json.dumps(
            {
                "codegraph": {
                    "latest_version": "v1.6.0",
                    "checked_at": "2026-09-01T00:00:00+00:00",
                    "failed_at": None,
                }
            }
        )
    )
    loaded = load_version_cache(path)
    assert loaded["codegraph"].latest_version == "v1.6.0"


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_version_cache(tmp_path / "missing.json") == {}


def test_malformed_json_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    path.write_text("{not json")
    assert load_version_cache(path) == {}


def test_default_cache_path_follows_userspace_state_convention(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    expected = tmp_path / ".local" / "state" / "tools-installer" / "versions.json"
    assert default_cache_path() == expected


def _entry(*, checked_at: str | None, failed_at: str | None = None) -> VersionCacheEntry:
    return VersionCacheEntry(latest_version="v1.6.0", checked_at=checked_at, failed_at=failed_at)


def test_exactly_seven_days_is_stale() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    entry = _entry(checked_at=(now - STALE_AFTER).isoformat())
    assert is_stale(entry, now=now) is True


def test_non_iso_checked_at_is_stale_rather_than_raising() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    assert is_stale(_entry(checked_at="not-a-timestamp"), now=now) is True


def test_naive_checked_at_is_stale_rather_than_raising() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    assert is_stale(_entry(checked_at="2026-09-06T00:00:00"), now=now) is True


def test_offset_timestamp_is_normalized_to_utc() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    plus_five = timezone(timedelta(hours=5))
    six_days = datetime(2026, 9, 1, 5, 0, tzinfo=plus_five)
    assert is_stale(_entry(checked_at=six_days.isoformat()), now=now) is False
    # 2026-08-31 01:00+05:00 is 2026-08-30 20:00 UTC (7d 4h, stale). Treating
    # the same clock as UTC would be 6d 23h and wrongly fresh.
    boundary = datetime(2026, 8, 31, 1, 0, tzinfo=plus_five)
    assert is_stale(_entry(checked_at=boundary.isoformat()), now=now) is True


def test_far_future_checked_at_is_stale() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    future = (now + timedelta(days=365)).isoformat()
    assert is_stale(_entry(checked_at=future), now=now) is True


def test_wrong_field_types_are_skipped_entry_by_entry(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "tools": {
                    "bad-latest": {
                        "latest_version": 16,
                        "checked_at": "2026-09-01T00:00:00+00:00",
                    },
                    "bad-checked": {"latest_version": "v1.0.0", "checked_at": ["x"]},
                    "good": {
                        "latest_version": "v1.6.0",
                        "checked_at": "2026-09-01T00:00:00+00:00",
                    },
                },
                "managers": {},
            }
        )
    )
    loaded = load_version_cache(path)
    assert set(loaded) == {"good"}
    assert loaded["good"].latest_version == "v1.6.0"


def test_should_fetch_backs_off_inside_retry_window() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    stale = _entry(
        checked_at=(now - STALE_AFTER).isoformat(),
        failed_at=(now - timedelta(hours=1)).isoformat(),
    )
    assert should_fetch(stale, now=now) is False
    cooled = _entry(
        checked_at=(now - STALE_AFTER).isoformat(),
        failed_at=(now - (RETRY_BACKOFF + timedelta(hours=1))).isoformat(),
    )
    assert should_fetch(cooled, now=now) is True


def _snapshot() -> ManagerSnapshot:
    return ManagerSnapshot(
        inventory=ManagerInventory(
            brew_formulae={"ripgrep": "14.1.0"},
            brew_casks=None,
            pnpm_globals=frozenset({"vercel"}),
            uv_tools={"ruff": "0.6.0"},
            brew_prefix=Path("/opt/homebrew"),
        ),
        outdated=OutdatedReport(
            brew={"ripgrep": ManagerVersion("14.1.0", "14.1.1")},
            cask=None,
            pnpm={},
            uv={"ruff": ManagerVersion("0.6.0", "0.6.1")},
        ),
        checked_at="2026-09-07T00:00:00+00:00",
        failed_at=None,
    )


def test_manager_snapshot_round_trips_none_fields() -> None:
    encoded = encode_manager_snapshot(_snapshot())
    decoded = decode_manager_snapshot(encoded)
    assert decoded is not None
    assert decoded.inventory.brew_formulae == {"ripgrep": "14.1.0"}
    assert decoded.inventory.brew_casks is None
    assert decoded.inventory.pnpm_globals == frozenset({"vercel"})
    assert decoded.inventory.uv_tools == {"ruff": "0.6.0"}
    assert decoded.inventory.brew_prefix == Path("/opt/homebrew")
    assert decoded.outdated.brew is not None
    assert decoded.outdated.brew["ripgrep"] == ManagerVersion("14.1.0", "14.1.1")
    assert decoded.outdated.cask is None
    assert decoded.outdated.pnpm == {}
    assert decoded.checked_at == "2026-09-07T00:00:00+00:00"


def test_manager_snapshot_wrong_inventory_type_degrades_to_none() -> None:
    decoded = decode_manager_snapshot(
        {
            "inventory": ["not", "an", "object"],
            "outdated": {},
            "checked_at": "2026-09-07T00:00:00+00:00",
            "failed_at": None,
        }
    )
    assert decoded is not None
    assert decoded.inventory.brew_formulae is None
    assert decoded.inventory.brew_casks is None
    assert decoded.inventory.pnpm_globals is None
    assert decoded.inventory.uv_tools is None
    assert decoded.inventory.brew_prefix is None


def test_manager_snapshot_naive_or_future_checked_at_is_stale() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    naive = ManagerSnapshot(
        inventory=_snapshot().inventory,
        outdated=_snapshot().outdated,
        checked_at="2026-09-07T00:00:00",
    )
    future = ManagerSnapshot(
        inventory=_snapshot().inventory,
        outdated=_snapshot().outdated,
        checked_at=(now + timedelta(days=365)).isoformat(),
    )
    assert is_manager_stale(naive, now=now) is True
    assert is_manager_stale(future, now=now) is True


def test_managers_and_tools_keys_survive_each_other(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    tools = {
        "codegraph": VersionCacheEntry(
            latest_version="v1.6.0",
            checked_at="2026-09-01T00:00:00+00:00",
            failed_at=None,
        )
    }
    save_version_cache(path, tools, managers=encode_manager_snapshot(_snapshot()))
    raw = json.loads(path.read_text())
    assert "codegraph" in raw["tools"]
    assert raw["managers"]["inventory"]["brew_formulae"]["ripgrep"] == "14.1.0"
    save_version_cache(
        path,
        {
            **tools,
            "rg": VersionCacheEntry(
                latest_version="14.1.1",
                checked_at="2026-09-07T00:00:00+00:00",
                failed_at=None,
            ),
        },
    )
    raw = json.loads(path.read_text())
    assert "rg" in raw["tools"]
    assert raw["managers"]["inventory"]["brew_formulae"]["ripgrep"] == "14.1.0"
