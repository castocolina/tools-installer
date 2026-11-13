"""The Schedules core: the closed table, the slot grid, the state file and the log reader."""

import json
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from installer import receipts
from installer.schedules import (
    SCHEDULES,
    UPDATE_SCHEDULE_IDS,
    ScheduleRecord,
    ScheduleState,
    calendar_dicts,
    default_data_dir,
    default_log_path,
    default_state_path,
    load_state,
    next_run,
    on_calendar,
    record_for,
    save_state,
    schedule_by_id,
    slots,
    update_state,
)

DEFAULT_GRID = ((0, 0), (6, 0), (12, 0), (18, 0))
OS_KEYS = ("debian", "arch", "fedora")


def test_default_schedule_round_trips(tmp_path: Path) -> None:
    grid = slots(6, "00:00")
    assert grid == DEFAULT_GRID
    assert on_calendar(grid) == "*-*-* 00,06,12,18:00:00"
    assert calendar_dicts(grid) == [
        {"Hour": 0, "Minute": 0},
        {"Hour": 6, "Minute": 0},
        {"Hour": 12, "Minute": 0},
        {"Hour": 18, "Minute": 0},
    ]
    assert next_run(grid, datetime(2026, 11, 13, 7, 0)) == datetime(2026, 11, 13, 12, 0)

    recorded = tmp_path / "unit.service"
    recorded.write_text("[Service]\n")
    artifact = receipts.fingerprint(recorded, "file")
    assert artifact is not None
    state = ScheduleState(
        records={
            "update-claude": ScheduleRecord(
                decided=True, interval=8, start="01:30", files=(artifact,)
            )
        },
        shared=(artifact,),
        cursor_shim="listed",
        checkout="/work/tools-installer",
        uv="/usr/bin/uv",
    )
    path = tmp_path / "state" / "schedules.json"
    save_state(path, state)
    loaded = load_state(path)
    assert loaded.state == state
    assert loaded.warning is None
    assert loaded.damaged is False
    assert path.stat().st_mode & 0o777 == 0o600

    saved = update_state(
        path,
        lambda current: ScheduleState(
            records={**current.records, "update-pi": ScheduleRecord(False, 12, "02:00", ())},
            shared=current.shared,
        ),
    )
    assert load_state(path).state == saved
    assert record_for(saved, "update-pi").decided is False
    assert record_for(saved, "update-copilot") == ScheduleRecord(None, 6, "00:00", ())


def test_the_table_is_closed_and_ordered() -> None:
    assert tuple(s.id for s in SCHEDULES) == (
        "tmp-cleanup",
        "cache-cleanup",
        "update-claude",
        "update-opencode",
        "update-pi",
        "update-cursor-agent",
        "update-copilot",
    )
    assert tuple(s.label for s in SCHEDULES) == (
        "tmp cleanup",
        "cache cleanup",
        "claude update",
        "opencode update",
        "pi update",
        "cursor-agent update",
        "copilot update",
    )
    assert UPDATE_SCHEDULE_IDS == (
        "update-claude",
        "update-opencode",
        "update-pi",
        "update-cursor-agent",
        "update-copilot",
    )
    assert [s.target for s in SCHEDULES] == [
        None,
        None,
        "claude",
        "opencode",
        "pi",
        "cursor-agent",
        "copilot",
    ]
    assert schedule_by_id("update-pi").target == "pi"
    with pytest.raises(KeyError):
        schedule_by_id("nope")


@pytest.mark.parametrize("interval", (1, 2, 3, 4, 6, 8, 12, 24))
def test_slot_grid_table(interval: int) -> None:
    grid = slots(interval, "00:00")
    assert len(grid) == 24 // interval
    assert list(grid) == sorted(grid)
    assert {minute for _hour, minute in grid} == {0}
    assert "/" not in on_calendar(grid)


def test_slot_grid_wraps_past_midnight() -> None:
    assert slots(8, "01:30") == ((1, 30), (9, 30), (17, 30))
    assert slots(6, "23:30") == ((5, 30), (11, 30), (17, 30), (23, 30))
    assert slots(24, "03:30") == ((3, 30),)
    assert on_calendar(slots(8, "01:30")) == "*-*-* 01,09,17:30:00"


def test_next_run_wraps_midnight() -> None:
    assert next_run(DEFAULT_GRID, datetime(2026, 11, 13, 23, 45)) == datetime(2026, 11, 14, 0, 0)
    # A slot equal to now is not "next".
    assert next_run(DEFAULT_GRID, datetime(2026, 11, 13, 6, 0)) == datetime(2026, 11, 13, 12, 0)


@pytest.fixture
def berlin_clock() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("TZ", "Europe/Berlin")
        time.tzset()
        yield
    time.tzset()


@pytest.mark.parametrize("day", (datetime(2026, 3, 29, 1, 0), datetime(2026, 10, 25, 1, 0)))
def test_next_run_keeps_wall_clock_across_dst(berlin_clock: None, day: datetime) -> None:
    grid = slots(6, "00:00")
    seen: list[tuple[int, int]] = []
    now = day
    for _ in range(5):
        now = next_run(grid, now)
        seen.append((now.hour, now.minute))
    assert seen == [(6, 0), (12, 0), (18, 0), (0, 0), (6, 0)]


def test_paths_follow_the_sandboxed_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    seen: list[tuple[Path, Path, Path]] = []
    for name in ("one", "two"):
        home = tmp_path / name
        monkeypatch.setenv("HOME", str(home))
        seen.append((default_state_path(), default_data_dir(), default_log_path("fedora")))
        assert seen[-1] == (
            home / ".local/state/tools-installer/schedules.json",
            home / ".local/share/tools-installer/schedules",
            home / ".local/state/tools-installer/schedules.log",
        )
    assert seen[0] != seen[1]

    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    assert default_data_dir() == xdg / "tools-installer/schedules"


@pytest.mark.parametrize("os_key", OS_KEYS)
def test_default_log_path_is_the_same_on_every_linux_key(
    os_key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_log_path(os_key) == tmp_path / ".local/state/tools-installer/schedules.log"
    assert default_log_path("macos") == tmp_path / "Library/Logs/tools-installer/schedules.log"


def test_saved_state_is_sorted_json(tmp_path: Path) -> None:
    path = tmp_path / "schedules.json"
    save_state(path, ScheduleState())
    data = json.loads(path.read_text())
    assert list(data) == sorted(data)
