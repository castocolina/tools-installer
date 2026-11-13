"""The Schedules lifecycle: the default-on reconcile, adoption, target removal and the sweep.

Every service-manager call goes to the recording fakes of `test_schedules_engine`; every file
lands under `tmp_path`. Private names are read through `vars(schedules)`.
"""

import plistlib
import shutil
import threading
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from installer import daemon, receipts, schedules, systemd_daemon
from installer.cursor_shim import is_our_shim
from installer.schedules import (
    ReconcileReport,
    ScheduleContext,
    ScheduleRecord,
    after_target_removed,
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
    CHECKOUT,
    CLAUDE_BASENAME,
    TMP_BASENAME,
    Env,
    Install,
    make_env,
    seed_legacy_tmp,
    tree,
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
    systemctl: bool = True,
    fail_on: frozenset[tuple[str, int]] = frozenset(),
) -> Lab:
    env = make_env(
        tmp_path,
        monkeypatch,
        os_key=os_key,
        present=frozenset(),
        systemctl=systemctl,
        fail_on=fail_on,
    )
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


# --- Task 2: target removal, reinstall, in-place refresh and adoption, failures, the hook ---


def decide_off(ctx: ScheduleContext, schedule_id: str) -> None:
    """Record a user's off without any engine call, so no verb reaches the recorder."""
    off = ScheduleRecord(False, 6, "00:00", ())
    update_state(
        ctx.state_path, lambda state: replace(state, records={**state.records, schedule_id: off})
    )


def verbs(lab: Lab) -> list[str]:
    return lab.env.run.text()


def test_target_gone_removes_files_and_keeps_the_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    assert load_state(ctx.state_path).state.records["update-claude"].files
    lab.live.discard("claude")

    report = ensure_schedule_defaults(ctx)

    assert report.removed == ("update-claude",)
    assert reconcile_lines(report) == (
        ("Removed the claude update timer because claude is gone.", "ok"),
    )
    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert len(unit_files(ctx, CACHE_BASENAME)) == 3  # only claude's files went
    state = load_state(ctx.state_path).state
    record = state.records["update-claude"]
    assert (record.decided, record.files) == (True, ())
    claude = schedules.schedule_by_id("update-claude")
    assert schedules.row_state(
        ctx, state, claude, manager=True, present=ctx.present
    ) == schedules.RowState("n/a", "unavailable: claude not installed")


def test_reinstall_turns_it_back_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    lab.live.discard("claude")
    ensure_schedule_defaults(ctx)
    lab.live.add("claude")

    report = ensure_schedule_defaults(ctx)

    assert report.turned_on == ("update-claude",)
    assert len(unit_files(ctx, CLAUDE_BASENAME)) == 3
    record = load_state(ctx.state_path).state.records["update-claude"]
    assert record.decided is True
    assert record.files


def test_drift_is_left_for_the_view(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    timer = ctx.unit_dir / f"{CLAUDE_BASENAME}.timer"
    edited = timer.read_bytes() + b"# edited by hand\n"
    timer.write_bytes(edited)
    lab.env.run.calls.clear()

    report = ensure_schedule_defaults(ctx)

    assert report == ReconcileReport()
    assert timer.read_bytes() == edited
    assert lab.env.run.calls == []
    state = load_state(ctx.state_path).state
    claude = schedules.schedule_by_id("update-claude")
    assert schedules.row_state(ctx, state, claude, manager=True, present=ctx.present) == (
        schedules.RowState("drift")
    )


def test_moved_checkout_refreshes_units_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ensure_schedule_defaults(lab.ctx)
    moved = tmp_path / "moved-checkout"
    shutil.copytree(CHECKOUT / "scripts", moved / "scripts")
    ctx_b = replace(lab.ctx, checkout=moved)
    lab.env.run.calls.clear()

    report = ensure_schedule_defaults(ctx_b)

    service = lab.ctx.unit_dir / f"{CLAUDE_BASENAME}.service"
    assert f'"--installer" "{moved}"' in service.read_text()
    assert verbs(lab) == [
        "daemon-reload",
        f"enable {CLAUDE_BASENAME}.timer",
        f"restart {CLAUDE_BASENAME}.timer",
    ]
    assert report == ReconcileReport()
    record = load_state(lab.ctx.state_path).state.records["update-claude"]
    assert all(receipts.matches(artifact, rehash=True) for artifact in record.files)

    lab.env.run.calls.clear()
    assert ensure_schedule_defaults(ctx_b) == ReconcileReport()
    assert lab.env.run.calls == []


def test_old_tmp_units_are_adopted_on_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=())
    ctx = lab.ctx
    old = seed_legacy_tmp(lab.env)
    decide_off(ctx, "cache-cleanup")

    report = ensure_schedule_defaults(ctx)

    assert report == ReconcileReport()  # the user already had it on: nothing to announce
    assert verbs(lab) == [
        "daemon-reload",
        f"enable {TMP_BASENAME}.timer",
        f"restart {TMP_BASENAME}.timer",
    ]  # no disable or stop: the running timer is never off, even for a moment
    service = ctx.unit_dir / f"{TMP_BASENAME}.service"
    assert service.read_bytes() != old[service]
    assert not (ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND).exists()
    record = load_state(ctx.state_path).state.records["tmp-cleanup"]
    assert record.decided is True
    assert len(record.files) == 3

    lab.env.run.calls.clear()
    assert ensure_schedule_defaults(ctx) == ReconcileReport()
    assert lab.env.run.calls == []


def test_macos_adoption_keeps_the_daily_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=(), os_key="macos")
    ctx = lab.ctx
    plist_path = ctx.launch_agents_dir / "com.tools-installer.prune-tmpdir.plist"
    daemon.write_plist(
        plist_path,
        uv_path=lab.env.uv,
        wrapper_path=daemon.install_wrapper(ctx.legacy_bin_dir),
        script_path=CHECKOUT / "scripts" / "prune-user-tmpdir.sh",
        log_path=ctx.home / "Library/Logs/tools-installer/prune-daemon.log",
        hour=5,
        minute=15,
        days=3,
        tmpdir=ctx.tmpdir,
        home=str(ctx.home),
        path_value="/usr/bin",
    )
    daemon.record_decided(ctx.myshellrc_path)
    decide_off(ctx, "cache-cleanup")

    report = ensure_schedule_defaults(ctx)

    assert report == ReconcileReport()
    assert plistlib.loads(plist_path.read_bytes())["StartCalendarInterval"] == [
        {"Hour": 5, "Minute": 15}
    ]
    record = load_state(ctx.state_path).state.records["tmp-cleanup"]
    assert (record.decided, record.start) == (True, "05:15")
    assert not (ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND).exists()


def test_failed_default_records_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch, fail_on=frozenset({("enable", 1)}))
    ctx = lab.ctx
    systemd_daemon.record_decided(ctx.myshellrc_path)
    decide_off(ctx, "cache-cleanup")

    report = ensure_schedule_defaults(ctx)

    assert report.turned_on == ()
    assert len(report.warnings) == 1
    assert report.warnings[0].startswith("Could not turn on claude update: ")
    assert reconcile_lines(report)[0][1] == "warn"
    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert "update-claude" not in load_state(ctx.state_path).state.records

    retry = ensure_schedule_defaults(ctx)  # the next pass retries
    assert retry.turned_on == ("update-claude",)


def test_same_run_install_is_turned_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=())
    ensure_schedule_defaults(lab.ctx)
    assert unit_files(lab.ctx, CLAUDE_BASENAME) == []

    lab.live.add("claude")  # the headless run just installed it
    report = ensure_schedule_defaults(lab.ctx)

    assert report.turned_on == ("update-claude",)
    assert len(unit_files(lab.ctx, CLAUDE_BASENAME)) == 3


def test_concurrent_reconciles_write_one_unit_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    barrier = threading.Barrier(2)
    local = threading.local()

    def meet_then_reachable(_ctx: ScheduleContext) -> bool:
        # One-shot per thread: `turn_on` asks again inside the lock and must never wait there.
        if not getattr(local, "met", False):
            local.met = True
            barrier.wait(timeout=10)
        return True

    monkeypatch.setattr(schedules, "manager_reachable", meet_then_reachable)
    reports: list[ReconcileReport] = []
    errors: list[BaseException] = []

    def reconcile() -> None:
        try:
            reports.append(ensure_schedule_defaults(ctx))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=reconcile, daemon=True) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads)
    assert errors == []

    turned = sorted(schedule_id for report in reports for schedule_id in report.turned_on)
    assert turned == ["cache-cleanup", "tmp-cleanup", "update-claude"]
    bases = (CLAUDE_BASENAME, CACHE_BASENAME, TMP_BASENAME)
    names = sorted(path.name for path in ctx.unit_dir.iterdir())
    wanted = [f"{base}.{kind}" for base in bases for kind in ("service", "timer")]
    assert names == sorted(["timers.target.wants", *wanted])
    for base in bases:
        assert verbs(lab).count(f"enable {base}.timer") == 1
    loaded = load_state(ctx.state_path)
    assert loaded.warning is None
    assert {key: record.decided for key, record in loaded.state.records.items()} == {
        "tmp-cleanup": True,
        "cache-cleanup": True,
        "update-claude": True,
    }


def test_after_target_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=("claude", "cursor-agent"))
    ctx = lab.ctx
    install = Install(lab.env.home)
    ensure_schedule_defaults(ctx)
    assert is_our_shim(install.link)

    claude = after_target_removed(ctx, "claude")

    assert claude.removed == ("update-claude",)
    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert load_state(ctx.state_path).state.records["update-claude"].decided is True

    cursor = after_target_removed(ctx, "cursor-agent")

    assert cursor.removed == ("update-cursor-agent",)
    assert not install.link.exists()
    assert not install.link.is_symlink()
    assert load_state(ctx.state_path).state.records["update-cursor-agent"].decided is True
    assert after_target_removed(ctx, "ripgrep") == ReconcileReport()


def test_after_target_removed_keeps_a_foreign_cursor_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=("cursor-agent",))
    install = Install(lab.env.home, foreign=True)
    turn_on(lab.ctx, "update-cursor-agent")

    report = after_target_removed(lab.ctx, "cursor-agent")

    assert report.removed == ("update-cursor-agent",)
    assert install.link.read_text() == "#!/bin/sh\necho mine\n"


def test_no_manager_reconcile_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, systemctl=False)
    before = tree(lab.env.home)

    report = ensure_schedule_defaults(lab.ctx)

    assert report == ReconcileReport()
    assert tree(lab.env.home) == before
    assert lab.env.run.calls == []
