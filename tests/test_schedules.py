"""The Schedules core: the closed table, the slot grid, the state file and the log reader."""

import json
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Literal

import pytest

from installer import receipts
from installer.daemon import DaemonScheduleError
from installer.ownership import NATIVE_OWNERS
from installer.schedules import (
    INTERVAL_MESSAGE,
    MODEL_CHARSET_MESSAGE,
    MODEL_SHAPE_MESSAGE,
    SCHEDULES,
    START_MESSAGE,
    UPDATE_SCHEDULE_IDS,
    ScheduleRecord,
    ScheduleState,
    calendar_dicts,
    clean_unit_path,
    clear_damage,
    damaged_path,
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
    update_result_line,
    update_state,
    validate_interval,
    validate_model_id,
    validate_start,
)
from installer.update import UpdateOutcome

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


@pytest.mark.parametrize("value", (1, 2, 3, 4, 6, 8, 12, 24, "6"))
def test_interval_validation_accepts(value: int | str) -> None:
    assert validate_interval(value) == int(value)


@pytest.mark.parametrize("value", (0, 5, 25, -6, "", "x", True))
def test_interval_validation_rejects(value: int | str) -> None:
    with pytest.raises(DaemonScheduleError) as raised:
        validate_interval(value)
    assert str(raised.value) == INTERVAL_MESSAGE
    assert INTERVAL_MESSAGE == "Interval must be 1, 2, 3, 4, 6, 8, 12 or 24 hours."


@pytest.mark.parametrize(
    ("value", "parsed"), (("00:00", (0, 0)), ("01:30", (1, 30)), ("23:59", (23, 59)))
)
def test_start_validation_accepts(value: str, parsed: tuple[int, int]) -> None:
    assert validate_start(value) == parsed


@pytest.mark.parametrize(
    "value", ("24:00", "7:5", "07:5", "ab:cd", "", "0730", " 07:30", "07:30\n")
)
def test_start_validation_rejects(value: str) -> None:
    with pytest.raises(DaemonScheduleError) as raised:
        validate_start(value)
    assert str(raised.value) == START_MESSAGE
    assert START_MESSAGE == "Start must be HH:MM from 00:00 to 23:59, for example 01:30."


@pytest.mark.parametrize(
    "value",
    ("gpt-5.6-sol-xhigh", "auto", "claude-opus-4-8[context=1m,effort=high,fast=false]", "a" * 128),
)
def test_model_id_validation_accepts(value: str) -> None:
    assert validate_model_id(value) == value


@pytest.mark.parametrize("value", ("bad id!", "a'b", "$(x)", "a;b", "a\nb"))
def test_model_id_validation_rejects_the_charset(value: str) -> None:
    with pytest.raises(DaemonScheduleError) as raised:
        validate_model_id(value)
    assert str(raised.value) == MODEL_CHARSET_MESSAGE
    assert MODEL_CHARSET_MESSAGE == "Model ids use letters, digits and . _ - [ ] = , only."


@pytest.mark.parametrize("value", ("--foo", "-m", ".x", "[a]", "a" * 129, ""))
def test_model_id_validation_rejects_the_shape(value: str) -> None:
    with pytest.raises(DaemonScheduleError) as raised:
        validate_model_id(value)
    assert str(raised.value) == MODEL_SHAPE_MESSAGE
    assert (
        MODEL_SHAPE_MESSAGE
        == "Model ids start with a letter or digit and are at most 128 characters."
    )


_GOOD_RECORD: dict[str, object] = {"decided": True, "interval": 6, "start": "00:00", "files": []}


def _records(**override: object) -> dict[str, object]:
    return {"schedules": {"update-claude": {**_GOOD_RECORD, **override}}}


DAMAGED_STATES: dict[str, str | bytes] = {
    "invalid-json": "{not json",
    "invalid-utf8": b"\xff\xfe{}",
    "not-an-object": "[]",
    "interval-5": json.dumps(_records(interval=5)),
    "start-24": json.dumps(_records(start="24:00")),
    "unknown-schedule": json.dumps({"schedules": {"update-nope": _GOOD_RECORD}}),
    "unknown-key": json.dumps({"surprise": 1}),
    "unknown-record-key": json.dumps(_records(extra=1)),
    "bad-model": json.dumps({"cursor_default_model": "--x"}),
    "decided-yes": json.dumps(_records(decided="yes")),
    "shim-maybe": json.dumps({"cursor_shim": "maybe"}),
    "bad-artifact": json.dumps(_records(files=[{"path": "relative", "type": "file"}])),
    "files-not-list": json.dumps(_records(files="x")),
    "unknown-version": json.dumps({"version": 2}),
}


@pytest.mark.parametrize("name", sorted(DAMAGED_STATES))
def test_damaged_state_falls_back_with_one_warning(name: str, tmp_path: Path) -> None:
    path = tmp_path / "schedules.json"
    original = DAMAGED_STATES[name]
    path.write_bytes(original if isinstance(original, bytes) else original.encode())

    loaded = load_state(path)

    assert loaded.state == ScheduleState()
    assert loaded.warning is not None
    assert loaded.warning.startswith("Could not read schedules.json (")
    assert loaded.warning.endswith("); using defaults.")
    assert "\n" not in loaded.warning
    assert loaded.damaged is True
    assert damaged_path(path).read_bytes() == path.read_bytes()
    first_write = damaged_path(path).stat().st_mtime_ns
    assert load_state(path).warning == loaded.warning
    assert damaged_path(path).stat().st_mtime_ns == first_write


def test_a_missing_file_loads_defaults_without_a_copy(tmp_path: Path) -> None:
    path = tmp_path / "schedules.json"
    loaded = load_state(path)
    assert (loaded.state, loaded.warning, loaded.damaged) == (ScheduleState(), None, False)
    assert not damaged_path(path).exists()


def test_a_directory_in_place_of_the_file_is_one_warning(tmp_path: Path) -> None:
    path = tmp_path / "schedules.json"
    path.mkdir()
    loaded = load_state(path)
    assert loaded.warning is not None
    assert loaded.warning.startswith("Could not read schedules.json (")
    assert loaded.state == ScheduleState()


def test_a_symlinked_file_is_one_warning(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text("{}")
    path = tmp_path / "schedules.json"
    path.symlink_to(real)
    loaded = load_state(path)
    assert loaded.warning is not None
    assert loaded.state == ScheduleState()


def test_damage_is_sticky_until_cleared(tmp_path: Path) -> None:
    path = tmp_path / "schedules.json"
    path.write_text("{not json")
    assert load_state(path).damaged is True

    save_state(path, ScheduleState())
    after_save = load_state(path)
    assert after_save.warning is None
    assert after_save.damaged is True
    assert damaged_path(path).read_text() == "{not json"

    clear_damage(path)
    clear_damage(path)  # nothing left to remove is not an error
    assert load_state(path).damaged is False


def test_clean_unit_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    checkout = tmp_path / "checkout"
    existing = {home / ".volta/bin", home / ".bun/bin", Path("/home/linuxbrew/.linuxbrew/bin")}
    environ = {
        "PATH": f"{checkout}/.venv/bin:/run/user/1000/fnm_multishells/1_2/bin:relative/bin:/usr/bin"
    }
    results = {
        key: clean_unit_path(
            home, platform_os=key, environ=environ, is_dir=lambda path: path in existing
        )
        for key in OS_KEYS
    }
    assert len(set(results.values())) == 1

    entries = results["fedora"].split(":")
    assert entries == [
        f"{home}/.local/bin",
        f"{home}/.local/share/pnpm",
        f"{home}/.volta/bin",
        f"{home}/.bun/bin",
        "/home/linuxbrew/.linuxbrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    assert all(entry.startswith("/") for entry in entries)
    assert len(entries) == len(set(entries))
    assert not any(".venv" in entry or entry.startswith("/run/user/") for entry in entries)


def test_clean_unit_path_on_macos_and_with_pnpm_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    macos = clean_unit_path(
        home,
        platform_os="macos",
        environ={},
        is_dir=lambda path: str(path) == "/opt/homebrew/bin",
    ).split(":")
    assert macos == [
        f"{home}/.local/bin",
        f"{home}/Library/pnpm",
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    pnpm = clean_unit_path(
        home, platform_os="debian", environ={"PNPM_HOME": "/opt/pnpm"}, is_dir=lambda _path: False
    ).split(":")
    assert pnpm[1] == "/opt/pnpm"
    relative = clean_unit_path(
        home, platform_os="debian", environ={"PNPM_HOME": "pnpm"}, is_dir=lambda _path: False
    ).split(":")
    assert relative[1] == f"{home}/.local/share/pnpm"


def _outcome(
    status: Literal["updated", "failed", "unknown-owner", "unsupported"],
    owner: str = "uv",
    detail: str = "",
    postinstall_warning: str | None = None,
) -> UpdateOutcome:
    return UpdateOutcome("opencode", status, owner, detail, postinstall_warning=postinstall_warning)


RESULT_CASES = (
    (_outcome("updated"), "1.0", "1.1", ("ok: updated 1.0 → 1.1", 0)),
    (_outcome("updated"), "1.0", "1.0", ("ok: up to date", 0)),
    (_outcome("updated"), None, "1.0", ("ok: updated", 0)),
    (_outcome("updated"), "1.0", None, ("ok: updated", 0)),
    (_outcome("updated"), None, None, ("ok: updated", 0)),
    (
        _outcome("unsupported", "sdkman", "SDKMAN owns it"),
        None,
        None,
        ("skipped: sdkman owns opencode", 0),
    ),
    (
        _outcome("unsupported", "os-package", "an OS package"),
        None,
        None,
        ("skipped: os-package owns opencode", 0),
    ),
    (
        _outcome("unsupported", "volta", "managed by Volta\nsecond"),
        None,
        None,
        ("skipped: managed by Volta", 0),
    ),
    (
        _outcome("unsupported", "installer", "pinned; update outside or re-pin"),
        None,
        None,
        ("skipped: pinned; update outside or re-pin", 0),
    ),
    (
        _outcome("unknown-owner", "unknown", "no manager claimed this tool"),
        None,
        None,
        ("skipped: no manager claimed this tool", 0),
    ),
    (_outcome("failed", "brew", "boom\nsecond line"), None, None, ("failed: boom", 1)),
    (_outcome("failed", "brew", "bad\x1b[31m\x07ness"), None, None, ("failed: bad[31mness", 1)),
    (
        _outcome("updated", postinstall_warning="hook\nlater"),
        "1",
        "1",
        ("ok: up to date; postinstall warning: hook", 0),
    ),
)


@pytest.mark.parametrize(("outcome", "before", "after", "expected"), RESULT_CASES)
def test_update_result_line_is_total(
    outcome: UpdateOutcome, before: str | None, after: str | None, expected: tuple[str, int]
) -> None:
    assert update_result_line(outcome, before, after) == expected


@pytest.mark.parametrize("owner", NATIVE_OWNERS)
def test_native_owners_are_skipped_by_name(owner: str) -> None:
    assert update_result_line(_outcome("unsupported", owner, "x"), None, None) == (
        f"skipped: {owner} owns opencode",
        0,
    )


def test_update_result_line_bounds_the_detail() -> None:
    assert update_result_line(_outcome("failed", "brew", "x" * 400), None, None) == (
        "failed: " + "x" * 300,
        1,
    )
    assert update_result_line(_outcome("failed", "brew", ""), None, None) == (
        "failed: update failed",
        1,
    )
