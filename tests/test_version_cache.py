import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from installer.version_cache import (
    RETRY_BACKOFF,
    STALE_AFTER,
    VersionCacheEntry,
    default_cache_path,
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
