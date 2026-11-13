"""The Schedules lifecycle: the default-on reconcile, adoption, target removal and the sweep.

Every service-manager call goes to the recording fakes of `test_schedules_engine`; every file
lands under `tmp_path`. Private names are read through `vars(schedules)`.
"""

import os
import plistlib
import shutil
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from installer import daemon, receipts, runlock, schedules, systemd_daemon
from installer.cursor_shim import is_our_shim
from installer.run import CommandError
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
    sweep_adapters,
    turn_off,
    turn_on,
    update_state,
)
from installer.uninstall import SweepResult, active_policies, sweep_policies
from tests.test_schedules_engine import (
    CHECKOUT,
    CLAUDE_BASENAME,
    TMP_BASENAME,
    Env,
    Install,
    legacy_wrapper,
    make_env,
    no_process_ctx,
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
    wrapper = legacy_wrapper(ctx)
    log = ctx.home / "Library/Logs/tools-installer/prune-daemon.log"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(  # the previous installer's plist: the wrapper drives the script
        plistlib.dumps(
            {
                "Label": "com.tools-installer.prune-tmpdir",
                "ProgramArguments": [
                    str(lab.env.uv),
                    "run",
                    "--no-cache",
                    "--no-project",
                    "--script",
                    str(wrapper),
                    "--script",
                    str(CHECKOUT / "scripts" / "prune-user-tmpdir.sh"),
                    "--log",
                    str(log),
                    "--cap-bytes",
                    "262144",
                    "--",
                    "--apply",
                    "--days",
                    "3",
                ],
                "StartCalendarInterval": {"Hour": 5, "Minute": 15},
                "StandardOutPath": str(log),
                "StandardErrorPath": str(log),
                "RunAtLoad": False,
                "EnvironmentVariables": {
                    "PATH": "/usr/bin",
                    "TMPDIR": ctx.tmpdir,
                    "HOME": str(ctx.home),
                },
            }
        )
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


# --- Task 3: uninstall-sweep adapters that leave no schedule file, script or record ---

LOCK_NAMES = frozenset(
    {"schedules.json.lock", "schedules.log.lock", "schedules.reconcile.lock", "run.lock"}
)
ALL_IDS = ("schedule:tmp-cleanup", "schedule:cache-cleanup", "schedule:update-claude")


def sweep(lab: Lab) -> SweepResult:
    ctx = lab.ctx
    policies = active_policies(
        (),
        rc_path=ctx.myshellrc_path,
        bin_dir=ctx.legacy_bin_dir,
        extra_policies=sweep_adapters(ctx),
    )
    return sweep_policies(policies)


def plant_logs(ctx: ScheduleContext) -> list[Path]:
    """The logs a host holds after some runs: the schedule log, launchd's, and the old tmp one."""
    paths = [ctx.log_path, ctx.launchd_log_path, ctx.log_path.with_name("prune-daemon.log")]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("an old line\n")
    return paths


def leftovers(home: Path) -> list[str]:
    """Every file or link under `home`; the lock files and the rc file may stay."""
    names = [
        str(path.relative_to(home))
        for path in sorted(home.rglob("*"))
        if (path.is_file() or path.is_symlink()) and path.name not in LOCK_NAMES | {".myshellrc"}
    ]
    return names


def test_sweep_adapters_cover_every_owned_schedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    assert sweep_adapters(ctx) == ()  # nothing on and no state file

    ensure_schedule_defaults(ctx)
    adapters = sweep_adapters(no_process_ctx(ctx))  # every predicate below starts no process
    assert tuple(policy.id for policy in adapters) == ALL_IDS
    assert all(policy.owned is not None and policy.owned() for policy in adapters)


def test_sweep_adapters_with_every_schedule_off_give_the_state_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    for schedule_id in ("tmp-cleanup", "cache-cleanup", "update-claude"):
        turn_off(ctx, schedule_id)
    assert ctx.state_path.exists()

    adapters = sweep_adapters(ctx)

    assert tuple(policy.id for policy in adapters) == ("schedule:state",)


def test_sweep_adapters_for_a_legacy_only_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=())
    seed_legacy_tmp(lab.env)
    plant_logs(lab.ctx)
    assert not lab.ctx.state_path.exists()

    adapters = sweep_adapters(lab.ctx)

    assert tuple(policy.id for policy in adapters) == ("schedule:tmp-cleanup",)


@pytest.mark.parametrize("os_key", ["fedora", "debian", "arch", "macos"])
def test_full_uninstall_leaves_nothing(
    os_key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, os_key=os_key)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    plant_logs(ctx)
    legacy_wrapper(ctx)
    damaged_path(ctx.state_path).write_bytes(b"{old damage")
    assert leftovers(lab.env.home)

    result = sweep(lab)

    assert result.swept == ALL_IDS
    assert result.failed == ()
    assert leftovers(lab.env.home) == []
    assert not (ctx.data_dir).exists()
    marker_present = (
        daemon.decided(ctx.myshellrc_path)
        if os_key == "macos"
        else systemd_daemon.decided(ctx.myshellrc_path)
    )
    assert not marker_present


def test_full_uninstall_with_every_schedule_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    for schedule_id in ("tmp-cleanup", "cache-cleanup", "update-claude"):
        turn_off(ctx, schedule_id)
    plant_logs(ctx)
    policies = active_policies(
        (),
        rc_path=ctx.myshellrc_path,
        bin_dir=ctx.legacy_bin_dir,
        extra_policies=sweep_adapters(ctx),
    )
    assert [policy.id for policy in policies] == ["schedule:state"]
    assert policies[0].label == "Schedules state and logs"
    assert policies[0].description == "removes schedules.json and the schedule logs"

    result = sweep_policies(policies)

    assert result.swept == ("schedule:state",)
    assert result.failed == ()
    assert leftovers(lab.env.home) == []
    assert not systemd_daemon.decided(ctx.myshellrc_path)


def test_adapter_remove_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=("claude", "cursor-agent"))
    ctx = lab.ctx
    Install(lab.env.home)
    ensure_schedule_defaults(ctx)
    adapters = sweep_adapters(ctx)  # built before any removal
    after_target_removed(ctx, "claude")
    after_target_removed(ctx, "cursor-agent")

    for policy in adapters:
        policy.remove()
    assert not ctx.state_path.exists()
    assert not ctx.data_dir.exists()
    assert not list(ctx.unit_dir.glob("*.timer"))
    before = tree(lab.env.home)
    for policy in adapters:
        policy.remove()  # a second call, and one after after_target_removed: nothing to change
    assert tree(lab.env.home) == before


def test_sweep_refuses_a_changed_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    timer = ctx.unit_dir / f"{CLAUDE_BASENAME}.timer"
    edited = timer.read_bytes() + b"# edited after recording\n"
    timer.write_bytes(edited)

    result = sweep(lab)

    assert result.failed == ("schedule:update-claude",)
    assert result.swept == ("schedule:tmp-cleanup", "schedule:cache-cleanup")
    assert timer.read_bytes() == edited
    assert unit_files(ctx, CACHE_BASENAME) == []
    assert ctx.state_path.exists()  # the changed file is still recorded


def test_sweep_refuses_a_changed_tmp_unit_and_keeps_the_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    service = ctx.unit_dir / f"{TMP_BASENAME}.service"
    edited = service.read_bytes() + b"# edited after recording\n"
    service.write_bytes(edited)

    result = sweep(lab)

    assert result.failed == ("schedule:tmp-cleanup",)
    assert result.swept == ("schedule:cache-cleanup", "schedule:update-claude")
    assert service.read_bytes() == edited
    assert systemd_daemon.decided(ctx.myshellrc_path)  # a unit of it remains: the decision stays


def test_sweep_restores_the_cursor_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=("cursor-agent",))
    install = Install(lab.env.home)
    turn_on(lab.ctx, "update-cursor-agent")
    assert is_our_shim(install.link)

    result = sweep(lab)

    assert result.failed == ()
    assert install.link.is_symlink()
    assert os.readlink(install.link) == os.readlink(install.agent)


def test_full_uninstall_of_a_legacy_only_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=())
    ctx = lab.ctx
    seed_legacy_tmp(lab.env)
    plant_logs(ctx)

    result = sweep(lab)

    assert (result.swept, result.failed) == (("schedule:tmp-cleanup",), ())
    assert leftovers(lab.env.home) == []
    assert not systemd_daemon.decided(ctx.myshellrc_path)


def test_a_disable_failure_fails_the_adapter_and_keeps_the_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A timer that is provably still running is never swept away: its adapter fails and the
    decision it recorded stays (the old daemon policy's CR-01 guarantee)."""
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    lab.env.run.arm(frozenset({("disable", 1)}))

    result = sweep(lab)

    assert result.failed == ("schedule:tmp-cleanup",)
    assert unit_files(ctx, TMP_BASENAME)  # the units that restart it were not deleted
    assert systemd_daemon.decided(ctx.myshellrc_path)


def test_a_stopped_timer_with_unit_files_is_still_owned_and_swept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`owned` answers "is a file of ours still here", never "is it running"."""
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)

    def all_inactive(_cmd: list[str]) -> str:
        return "inactive"

    quiet = replace(ctx, read_output=all_inactive)

    policies = active_policies(
        (),
        rc_path=quiet.myshellrc_path,
        bin_dir=quiet.legacy_bin_dir,
        extra_policies=sweep_adapters(quiet),
    )
    assert [policy.id for policy in policies] == list(ALL_IDS)
    result = sweep_policies(policies)

    assert result.failed == ()
    assert leftovers(lab.env.home) == []


def test_an_unreachable_manager_removes_the_files_and_discloses_the_missing_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-01: with no user bus the files still go (they would restart the timer at the next
    login) and the result says no daemon-reload could run."""
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    lab.env.run.calls.clear()
    lab.env.run.arm(frozenset({("disable", 1)}))

    def no_bus(cmd: list[str]) -> str:
        raise CommandError(cmd, 1)

    unreachable = replace(ctx, read_output=no_bus)
    report = turn_off(unreachable, "tmp-cleanup")

    assert unit_files(ctx, TMP_BASENAME) == []
    assert any("could not be reached" in warning for warning in report.warnings)
    assert "daemon-reload" not in lab.env.run.text()


def test_an_unreadable_state_refuses_the_write_instead_of_saving_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=("claude", "opencode"))
    ensure_schedule_defaults(lab.ctx)
    turn_off(lab.ctx, "update-opencode")
    before = lab.ctx.state_path.read_bytes()
    real_read = schedules.read_capped

    def unreadable(path: Path, cap: int, *, follow_symlinks: bool) -> bytes | None:
        if path == lab.ctx.state_path:
            raise PermissionError("transient")
        return real_read(path, cap, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(schedules, "read_capped", unreadable)
    with pytest.raises(OSError, match="transient"):
        update_state(lab.ctx.state_path, lambda state: state)
    monkeypatch.undo()
    assert lab.ctx.state_path.read_bytes() == before
    assert not schedules.damaged_path(lab.ctx.state_path).exists()
    assert load_state(lab.ctx.state_path).state.records["update-opencode"].decided is False


def test_macos_reconcile_honours_a_time_recorded_before_the_first_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=(), os_key="macos")
    ctx = lab.ctx
    plist_path = ctx.launch_agents_dir / "com.tools-installer.prune-tmpdir.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(  # the previous installer's plist, at its own daily time
        plistlib.dumps(
            {
                "Label": "com.tools-installer.prune-tmpdir",
                "ProgramArguments": ["/bin/true"],
                "StartCalendarInterval": {"Hour": 5, "Minute": 15},
            }
        )
    )
    daemon.record_decided(ctx.myshellrc_path)
    decide_off(ctx, "cache-cleanup")
    schedules.retime(ctx, "tmp-cleanup", 24, "04:30")  # saved while the row is not on yet

    ensure_schedule_defaults(ctx)

    assert plistlib.loads(plist_path.read_bytes())["StartCalendarInterval"] == [
        {"Hour": 4, "Minute": 30}
    ]
    assert load_state(ctx.state_path).state.records["tmp-cleanup"].start == "04:30"


def damage_state(ctx: ScheduleContext) -> None:
    """A newer checkout's schema: unreadable to this one, so the load answers defaults."""
    ctx.state_path.write_text('{"version": 2}')


def test_a_damaged_state_still_reads_live_timers_as_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ensure_schedule_defaults(lab.ctx)
    damage_state(lab.ctx)
    state = load_state(lab.ctx.state_path).state
    for schedule_id in ("update-claude", "cache-cleanup", "tmp-cleanup"):
        row = schedules.row_state(
            lab.ctx,
            state,
            schedules.schedule_by_id(schedule_id),
            manager=True,
            present=lab.ctx.present,
        )
        assert row.word == "on"


def test_turn_off_under_a_damaged_state_removes_the_live_timer_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ensure_schedule_defaults(lab.ctx)
    damage_state(lab.ctx)

    turn_off(lab.ctx, "update-claude")

    assert unit_files(lab.ctx, CLAUDE_BASENAME) == []
    assert len(unit_files(lab.ctx, CACHE_BASENAME)) == 3  # only the one asked for


def test_the_sweep_under_a_damaged_state_removes_every_timer_before_the_damaged_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ensure_schedule_defaults(lab.ctx)
    damage_state(lab.ctx)
    load_state(lab.ctx.state_path)  # keeps the `.damaged` copy
    damaged = schedules.damaged_path(lab.ctx.state_path)
    seen: list[bool] = []
    lab.env.run.hooks["disable"] = lambda _cmd: seen.append(damaged.exists())

    sweep_policies(list(sweep_adapters(lab.ctx)))

    for basename in (CLAUDE_BASENAME, CACHE_BASENAME, TMP_BASENAME):
        assert unit_files(lab.ctx, basename) == []
    assert seen
    assert all(seen)  # the copy outlived every unit removal
    assert not damaged.exists()
    assert not lab.ctx.state_path.exists()


def shared_files(ctx: ScheduleContext) -> list[Path]:
    return [ctx.data_dir / name for name in ("runner.py", "prune-tmp-linux.sh")]


def test_turning_off_the_last_schedule_keeps_the_shared_files_while_a_run_holds_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    turn_on(ctx, "update-claude")
    held = runlock.try_acquire(ctx.lock_path, "update-claude")  # a scheduled run in flight
    assert held is not None
    try:
        turn_off(ctx, "update-claude")
    finally:
        held.release()

    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert all(path.exists() for path in shared_files(ctx))  # a run may be reading them
    assert load_state(ctx.state_path).state.shared  # still recorded, so a later off can remove

    turn_on(ctx, "update-claude")
    turn_off(ctx, "update-claude")  # idle now: the last off removes them
    assert not any(path.exists() for path in shared_files(ctx))
    assert load_state(ctx.state_path).state.shared == ()


def test_shared_files_stay_while_any_unit_exists_on_disk_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    turn_on(ctx, "update-claude")

    def another_process_adopts_the_assets(_cmd: list[str]) -> None:
        # a unit pair another process wrote and has not recorded yet
        systemd_daemon.write_unit_pair(
            ctx.unit_dir, basename=CACHE_BASENAME, service_text="s\n", timer_text="t\n"
        )

    lab.env.run.hooks["daemon-reload"] = another_process_adopts_the_assets
    turn_off(ctx, "update-claude")

    assert all(path.exists() for path in shared_files(ctx))


def test_the_sweep_reports_a_busy_run_and_keeps_the_shared_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    held = runlock.try_acquire(ctx.lock_path, "update-claude")
    assert held is not None
    try:
        result = sweep_policies(list(sweep_adapters(ctx)))
    finally:
        held.release()

    assert result.failed
    assert all(path.exists() for path in shared_files(ctx))
    assert ctx.state_path.exists()  # not removed under a run

    result = sweep_policies(list(sweep_adapters(ctx)))
    assert not result.failed
    assert not any(path.exists() for path in shared_files(ctx))


def test_the_installers_own_run_lock_does_not_block_removing_the_shared_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    turn_on(ctx, "update-claude")
    mine = runlock.try_acquire(ctx.lock_path, runlock.INSTALLER_JOB)  # a REMOVAL in flight
    assert mine is not None
    try:
        lab.live.discard("claude")
        after_target_removed(ctx, "claude")
    finally:
        mine.release()

    assert not any(path.exists() for path in shared_files(ctx))


def ship_new_sources(
    monkeypatch: pytest.MonkeyPatch, ctx: ScheduleContext, tmp_path: Path, *names: str
) -> dict[str, bytes]:
    """The checkout now ships changed copies of these shared assets (after a `git pull`)."""
    original: Callable[[ScheduleContext], tuple[tuple[Path, Path], ...]] = vars(schedules)[
        "_shared_pairs"
    ]
    new_bytes: dict[str, bytes] = {}
    swapped: dict[Path, Path] = {}
    for _source, target in original(ctx):
        if target.name in names:
            replacement = tmp_path / f"new-{target.name}"
            replacement.write_bytes(target.read_bytes() + b"\n# a bug fix\n")
            new_bytes[target.name] = replacement.read_bytes()
            swapped[target] = replacement

    def patched(context: ScheduleContext) -> tuple[tuple[Path, Path], ...]:
        return tuple((swapped.get(target, source), target) for source, target in original(context))

    monkeypatch.setitem(vars(schedules), "_shared_pairs", patched)
    return new_bytes


def test_the_reconcile_refreshes_a_shared_asset_that_differs_from_its_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    new = ship_new_sources(monkeypatch, ctx, tmp_path, "runner.py", "prune-tmp-linux.sh")

    report = ensure_schedule_defaults(ctx)

    assert (ctx.data_dir / "runner.py").read_bytes() == new["runner.py"]
    assert (ctx.data_dir / "prune-tmp-linux.sh").read_bytes() == new["prune-tmp-linux.sh"]
    assert report.warnings == ()
    shared = load_state(ctx.state_path).state.shared
    assert all(receipts.matches(a, rehash=True) for a in shared)
    assert ensure_schedule_defaults(ctx) == ReconcileReport()  # and then it is quiet


def test_the_reconcile_restores_a_deleted_shared_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    runner = ctx.data_dir / "runner.py"
    original = runner.read_bytes()
    runner.unlink()

    ensure_schedule_defaults(ctx)

    assert runner.read_bytes() == original
    assert os.access(runner, os.X_OK)
    shared = load_state(ctx.state_path).state.shared
    assert all(receipts.matches(a, rehash=True) for a in shared)


def test_the_reconcile_refuses_and_warns_for_a_user_edited_shared_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    ensure_schedule_defaults(ctx)
    edited = ctx.data_dir / "prune-tmp-linux.sh"
    mine = edited.read_bytes() + b"# my own tweak\n"
    edited.write_bytes(mine)
    new = ship_new_sources(monkeypatch, ctx, tmp_path, "runner.py", "prune-tmp-linux.sh")

    report = ensure_schedule_defaults(ctx)

    assert edited.read_bytes() == mine  # never overwritten
    assert any("prune-tmp-linux.sh" in warning for warning in report.warnings)
    assert (ctx.data_dir / "runner.py").read_bytes() == new["runner.py"]  # the others refresh


def test_a_user_off_that_lands_mid_reconcile_stays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch, present=("cursor-agent",))
    ctx = lab.ctx
    basename = "tools-installer-schedule-update-cursor-agent"
    schedule_id = "update-cursor-agent"
    entered, release = threading.Event(), threading.Event()

    def hold_after_the_units_are_written() -> None:
        # The model list is read after the units are registered and before the decision is saved.
        if not entered.is_set():
            entered.set()
            assert release.wait(10)

    lab.env.models.on_call = hold_after_the_units_are_written
    errors: list[BaseException] = []

    def run(action: Callable[[], object]) -> threading.Thread:
        def guarded() -> None:
            try:
                action()
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=guarded)
        thread.start()
        return thread

    reconcile = run(lambda: ensure_schedule_defaults(ctx))
    assert entered.wait(10)  # the pass is mid-flight: claude's units written, not yet recorded
    off = run(lambda: turn_off(ctx, schedule_id))
    time.sleep(0.3)  # without the reconcile lock the off would complete (and be undone) here
    release.set()
    reconcile.join(10)
    off.join(10)

    assert errors == []
    state = load_state(ctx.state_path).state
    assert state.records[schedule_id].decided is False
    assert unit_files(ctx, basename) == []
    cursor = schedules.schedule_by_id(schedule_id)
    assert schedules.row_state(ctx, state, cursor, manager=True, present=ctx.present).word == "off"


def test_a_reconcile_turn_on_whose_decision_moved_undoes_what_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = make_lab(tmp_path, monkeypatch)
    ctx = lab.ctx
    turn_on_for_pass = vars(schedules)["_turn_on"]
    seen_before_the_off = ScheduleRecord(None, 6, "00:00", ())
    off = ScheduleRecord(False, 6, "00:00", ())
    update_state(
        ctx.state_path,
        lambda state: replace(state, records={**state.records, "update-claude": off}),
    )

    report = turn_on_for_pass(ctx, "update-claude", seen=seen_before_the_off)

    assert report.changed is False
    assert unit_files(ctx, CLAUDE_BASENAME) == []  # what the call wrote is undone
    assert load_state(ctx.state_path).state.records["update-claude"].decided is False
