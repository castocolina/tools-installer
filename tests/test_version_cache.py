import json
from pathlib import Path

import pytest

from installer.version_cache import (
    VersionCacheEntry,
    default_cache_path,
    load_version_cache,
    save_version_cache,
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
