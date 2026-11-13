"""The Schedules lifecycle: the default-on reconcile, adoption, target removal and the sweep.

Every service-manager call goes to the recording fakes of `test_schedules_engine`; every file
lands under `tmp_path`. Private names are read through `vars(schedules)`.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from installer import schedules, systemd_daemon
from installer.schedules import (
    ReconcileReport,
    ScheduleContext,
    ScheduleRecord,
    clear_damage,
    damaged_path,
    ensure_schedule_defaults,
    load_state,
    reconcile_lines,
    turn_off,
    turn_on,
    update_state,
)
from tests.test_schedules_engine import (
    CLAUDE_BASENAME,
    TMP_BASENAME,
    Env,
    make_env,
)

STICKY_DAMAGE = "schedules.json was damaged; nothing turns on until you change a schedule."


@dataclass
class Lab:
    """An engine scratch HOME whose installed tools can change between passes."""

    env: Env
    ctx: ScheduleContext
    live: set[str]


def make_lab(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    present: Iterable[str] = ("claude",),
    os_key: str = "fedora",
    fail_on: frozenset[tuple[str, int]] = frozenset(),
) -> Lab:
    env = make_env(tmp_path, monkeypatch, os_key=os_key, present=frozenset(), fail_on=fail_on)
    live = set(present)
    return Lab(env, replace(env.ctx, present=live.__contains__), live)


def unit_files(ctx: ScheduleContext, basename: str) -> list[Path]:
    service, timer = systemd_daemon.unit_paths(ctx.unit_dir, basename=basename)
    link = systemd_daemon.wants_link_path(ctx.unit_dir, basename=basename)
    return [path for path in (service, timer, link) if path.exists() or path.is_symlink()]


CACHE_BASENAME = "tools-installer-schedule-cache-cleanup"


def test_first_run_turns_on_and_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    assert not ctx.state_path.exists()

    report = ensure_schedule_defaults(ctx)

    assert len(unit_files(ctx, CLAUDE_BASENAME)) == 3
    assert len(unit_files(ctx, CACHE_BASENAME)) == 3
    assert len(unit_files(ctx, TMP_BASENAME)) == 3
    records = load_state(ctx.state_path).state.records
    assert sorted(records) == ["cache-cleanup", "tmp-cleanup", "update-claude"]
    assert records["update-claude"].decided is True
    assert records["cache-cleanup"].decided is True
    assert systemd_daemon.decided(ctx.myshellrc_path)
    assert report.turned_on == ("tmp-cleanup", "cache-cleanup", "update-claude")
    assert reconcile_lines(report) == (
        (
            "Turned on schedules: tmp cleanup, cache cleanup, claude update. "
            "Change them in Schedules.",
            "ok",
        ),
    )


def test_second_run_changes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ensure_schedule_defaults(lab.ctx)
    lab.env.run.calls.clear()

    report = ensure_schedule_defaults(lab.ctx)

    assert report == ReconcileReport()
    assert reconcile_lines(report) == ()
    assert lab.env.run.calls == []


def test_mid_pass_decision_is_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    systemd_daemon.record_decided(ctx.myshellrc_path)  # tmp cleanup is decided: cache is first
    fired: list[bool] = []

    def other_process_turns_claude_off(_cmd: list[str]) -> None:
        if fired:
            return
        fired.append(True)
        off = ScheduleRecord(False, 6, "00:00", ())
        update_state(
            ctx.state_path,
            lambda state: replace(state, records={**state.records, "update-claude": off}),
        )

    lab.env.run.hooks["enable"] = other_process_turns_claude_off

    report = ensure_schedule_defaults(ctx)

    assert fired == [True]
    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert load_state(ctx.state_path).state.records["update-claude"].decided is False
    assert report.turned_on == ("cache-cleanup",)


def test_damaged_state_turns_nothing_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    turn_off(ctx, "update-claude")
    ctx.state_path.write_bytes(b"{not json")

    first = ensure_schedule_defaults(ctx)

    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert first.turned_on == ()
    assert len(first.warnings) == 1
    assert first.warnings[0].startswith("Could not read schedules.json (")
    assert first.warnings[0].endswith("); using defaults.")
    assert damaged_path(ctx.state_path).read_bytes() == b"{not json"

    turn_on(ctx, "cache-cleanup")  # a toggle of another row saves valid defaults
    second = ensure_schedule_defaults(ctx)

    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert second.turned_on == ()
    assert second.warnings == (STICKY_DAMAGE,)

    clear_damage(ctx.state_path)  # what the view does on a user action
    third = ensure_schedule_defaults(ctx)

    assert len(unit_files(ctx, CLAUDE_BASENAME)) == 3
    assert "update-claude" in third.turned_on


def test_a_users_off_survives_every_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    turn_off(ctx, "update-claude")
    turn_off(ctx, "tmp-cleanup")
    lab.env.run.calls.clear()

    for _ in range(2):
        report = ensure_schedule_defaults(ctx)
        assert report == ReconcileReport()
        assert reconcile_lines(report) == ()

    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert unit_files(ctx, TMP_BASENAME) == []
    assert lab.env.run.calls == []
    assert vars(schedules)["_tmp_decided"](ctx)
