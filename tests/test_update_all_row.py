"""Contracts for the opt-in update-all schedule."""

import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from installer import receipts, runlock, schedules
from installer.helper_assets import schedule_runner
from tests.test_schedules_engine import make_env
from tests.test_schedules_lifecycle import leftovers, make_lab, plant_logs, sweep, unit_files


def test_the_update_all_row_fields_and_ids() -> None:
    row = schedules.schedule_by_id("update-all")
    assert schedules.SCHEDULES[-1] == row
    assert (
        row.kind,
        row.target,
        row.default_interval,
        row.default_start,
        row.daily,
        row.default_on,
        row.label,
    ) == (schedules.JobKind.UPDATE_ALL, None, 24, "03:00", True, False, "update all")
    assert all(item.default_on for item in schedules.SCHEDULES[:-1])
    assert schedules.UPDATE_SCHEDULE_IDS == (
        "update-claude",
        "update-opencode",
        "update-pi",
        "update-cursor-agent",
        "update-copilot",
    )
    assert (
        *schedules.UPDATE_SCHEDULE_IDS,
        "check-updates",
        "update-all",
    ) == schedules.RUN_SCHEDULE_IDS
    for item in reversed(schedules.SCHEDULES):
        assert schedules.schedule_by_id(item.id) == item


@pytest.mark.parametrize(
    ("default_on", "decided", "has_files", "expected"),
    [
        (True, None, False, "turn-on"),
        (True, False, False, "none"),
        (True, True, True, "refresh"),
        (True, True, False, "turn-on"),
        (False, None, False, "none"),
        (False, False, False, "none"),
        (False, True, True, "refresh"),
        (False, True, False, "turn-on"),
    ],
)
def test_row_action_truth_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    default_on: bool,
    decided: bool | None,
    has_files: bool,
    expected: str,
) -> None:
    path = tmp_path / "unit"
    path.write_text("unit")
    artifact = receipts.fingerprint(path, "file")
    assert artifact is not None
    row = replace(schedules.schedule_by_id("update-all"), default_on=default_on)
    record = schedules.ScheduleRecord(decided, 24, "03:00", (artifact,) if has_files else ())
    env = make_env(tmp_path, monkeypatch)
    assert vars(schedules)["_row_action"](env.ctx, row, record) == expected


def test_held_by_proves_the_kernel_lock_not_text(tmp_path: Path) -> None:
    path = tmp_path / "lock"
    assert not runlock.held_by(path, "update-all", os.getpid())
    assert not path.exists()
    lock = runlock.try_acquire(path, "update-all")
    assert lock is not None
    try:
        assert runlock.held_by(path, "update-all", os.getpid())
        assert not runlock.held_by(path, "other", os.getpid())
        assert not runlock.held_by(path, "update-all", None)
        assert not runlock.held_by(path, "update-all", os.getpid() + 1)
    finally:
        lock.release()
    assert not runlock.held_by(path, "update-all", os.getpid())
    data = f"update-all {os.getpid()} 2026-01-01\n".encode()
    path.write_bytes(data)
    assert not runlock.held_by(path, "update-all", os.getpid())
    assert path.read_bytes() == data
    link = tmp_path / "link"
    link.symlink_to(path)
    assert not runlock.held_by(link, "update-all", os.getpid())
    path.write_text("update-all 999999999 2026-01-01\n")
    assert not runlock.held_by(path, "update-all", 999999999)


def test_a_fresh_home_seeds_update_all_off_and_every_other_row_as_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, present in (
        ("full", frozenset({"claude", "opencode", "cursor-agent", "copilot", "pi"})),
        ("empty", frozenset[str]()),
    ):
        env = make_env(tmp_path / name, monkeypatch, present=present)
        report = schedules.ensure_schedule_defaults(env.ctx)
        assert "update-all" not in report.turned_on
        assert (
            schedules.record_for(
                schedules.load_state(env.ctx.state_path).state, "update-all"
            ).decided
            is None
        )
        assert not any("update-all" in path.name for path in env.home.rglob("*"))
        assert set(report.turned_on) == {
            s.id
            for s in schedules.SCHEDULES[:-1]
            if s.kind is not schedules.JobKind.UPDATE or s.target in present
        }


def test_a_users_decision_survives_reseeding_and_reconfigure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch)
    ctx = env.ctx
    schedules.turn_on(ctx, "update-all")
    basename = schedules.basename_for("update-all")
    before = schedules.record_for(schedules.load_state(ctx.state_path).state, "update-all")
    assert before.decided is True and before.files and unit_files(ctx, basename)
    for _ in range(2):
        schedules.ensure_schedule_defaults(ctx)
        assert (
            schedules.record_for(schedules.load_state(ctx.state_path).state, "update-all") == before
        )
    schedules.retime(ctx, "update-all", 24, "04:15")
    moved = tmp_path / "moved"
    shutil.copytree(ctx.checkout / "scripts", moved / "scripts")
    moved_ctx = replace(ctx, checkout=moved)
    schedules.ensure_schedule_defaults(moved_ctx)
    record = schedules.record_for(schedules.load_state(ctx.state_path).state, "update-all")
    assert record.decided is True and record.start == "04:15"
    assert str(moved) in (ctx.unit_dir / f"{basename}.service").read_text()
    schedules.turn_off(moved_ctx, "update-all")
    off = schedules.ScheduleRecord(False, 24, "05:30", ())
    schedules.update_state(
        ctx.state_path, lambda state: replace(state, records={**state.records, "update-all": off})
    )
    for _ in range(2):
        schedules.ensure_schedule_defaults(moved_ctx)
        assert schedules.record_for(schedules.load_state(ctx.state_path).state, "update-all") == off
        assert not unit_files(ctx, basename)


def test_the_state_artifacts_hold_the_two_new_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    schedules.ensure_schedule_defaults(ctx)
    paths = (schedules.updated_today_path(ctx), schedules.update_all_log_path(ctx))
    assert paths == (
        ctx.state_path.with_name("updated-today.json"),
        ctx.log_path.with_name("update-all.log"),
    )
    assert all(path in vars(schedules)["_state_artifacts"](ctx) for path in paths)
    plant_logs(ctx)
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("old")
    assert not sweep(lab).failed
    assert not leftovers(lab.env.home)


@pytest.mark.parametrize("os_key", ["fedora", "macos"])
def test_update_all_runner_argv_parses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, os_key: str
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key=os_key)
    argv = schedules.runner_argv(env.ctx, schedules.schedule_by_id("update-all"), Path("/u/uv"))[6:]
    job, run_id, options, _ = vars(schedule_runner)["_parse"](argv)
    assert (job, run_id, options["--installer"], options["--uv"]) == (
        "update-all",
        "update-all",
        str(env.ctx.checkout),
        "/u/uv",
    )
    index = argv.index("--uv")
    with pytest.raises(Exception, match="needs --uv"):
        vars(schedule_runner)["_parse"](argv[:index] + argv[index + 2 :])


def test_the_summary_line_shapes() -> None:
    from installer import update_all

    assert update_all.summary_line(updated=0, skipped=0) == "ok: 0 updated"
    assert update_all.summary_line(updated=2, skipped=1) == "ok: 2 updated, 1 skipped"
    assert (
        update_all.summary_line(updated=2, skipped=1, unchanged=3)
        == "ok: 2 updated, 1 skipped; 3 unchanged"
    )
    assert (
        update_all.summary_line(updated=2, skipped=1, failed=2, first_failed="uv")
        == "failed: 2 failed (uv), 2 updated, 1 skipped"
    )
    assert update_all.plain_line("a\tb\x1b[31mred\x1b[0m\nc") == "a bred c"
    line = update_all.summary_line(
        updated=2, skipped=1, clauses=("notify\tskipped: \x1b[31mx", "x" * 400)
    )
    assert line.startswith("ok: 2 updated, 1 skipped; notify skipped: x; ") and len(line) <= 300
    assert "\x1b" not in line and "\t" not in line
    line = update_all.summary_line(
        updated=2,
        skipped=1,
        failed=1,
        first_failed="a" * 400,
        clauses=("updated-today record unreadable", "run log not saved"),
    )
    assert (
        "(" + "a" * 40 + ")" in line
        and "updated-today record unreadable; run log not saved" in line
    )


async def test_update_all_is_not_a_policies_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import Any

    from textual.widgets import DataTable

    import setup
    from installer import tweaks
    from tests import test_setup

    assert all("update-all" not in bundle.id for bundle in tweaks.BUNDLES)
    env = make_env(tmp_path / "env", monkeypatch)
    assert schedules.sweep_adapters(env.ctx) == ()
    schedules.turn_on(env.ctx, "update-all")
    assert [policy.id for policy in schedules.sweep_adapters(env.ctx)] == ["schedule:update-all"]
    test_setup.__dict__["_sandbox"](monkeypatch, tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    platform = test_setup.__dict__["_platform"]()
    app = vars(setup)["_build_app"]([], platform, initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        table = app.screen.query_one(DataTable[Any])
        assert table.rows and all("update-all" not in str(key.value) for key in table.rows)
