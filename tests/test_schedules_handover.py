"""The switch from Policies to Schedules: the headless route, the TUI reconciles, the uninstall.

Every service-manager call goes to the recording fakes of `test_schedules_engine`; every file lands
under the scratch HOME. The composition root is driven in-process through its own test seams.
"""

import io
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from textual.widgets import DataTable

import setup
from installer import daemon, policy, runlock, schedules
from installer.app import (
    UninstallDecision,
    perform_uninstall,
    removal_result_lines,
    run_uninstall,
)
from installer.diskusage import DiskPressure
from installer.enums import DaemonState, MutationHolder
from installer.execute_screen import InstallRunFinished
from installer.guidance import disk_pressure_guidance
from installer.model import Method, Tool
from installer.platform import Platform
from installer.policy import Policy
from installer.schedules import (
    ReconcileReport,
    ScheduleContext,
    ScheduleDefaultWarnings,
    ScheduleRecord,
    update_state,
)
from installer.session import Disposition, PlanRow, RowOutcome
from installer.systemd_daemon import CompetingUnit
from installer.systemd_daemon import decided as systemd_decided
from installer.ui_common import BASE_VIEW
from installer.uninstall import SweepResult
from installer.wizard_app import SchedulesScreen, UnifiedApp
from tests import test_setup
from tests.screen_family import settle, wait_until
from tests.state_doubles import FrozenStateService
from tests.test_schedules_engine import (
    CLAUDE_BASENAME,
    TMP_BASENAME,
    Env,
    Install,
    make_env,
    seed_legacy_tmp,
)
from tests.test_schedules_lifecycle import unit_files
from tests.test_uninstall import plant_raw_yq, write_receipt

TURNED_ON = (
    "Turned on schedules: tmp cleanup, cache cleanup, claude update. Change them in Schedules."
)
REFUSAL = "A scheduled run is running; try again when it finishes."
FEDORA = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def _claude_only(tool_id: str) -> bool:
    return tool_id == "claude"


def _no_tools(_registry: object) -> list[Tool]:
    return []


class _Refresh:
    """The one method the headless reconcile reads from the refresh service."""

    def installed_or(self, launch: dict[str, bool]) -> Callable[[str], bool]:
        return lambda tool_id: launch.get(tool_id, False)


def _headless(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    env: Env,
    buffer: io.StringIO,
    *,
    during_wizard: list[str] | None = None,
) -> list[bool]:
    """Wire `setup.main(["--all", "--yes"])` onto a fake wizard and `env`'s schedule context."""
    ran: list[bool] = []

    def fake_run_wizard(*_args: object, **_kwargs: object) -> list[RowOutcome]:
        ran.append(True)
        held = runlock.holder(runlock.run_lock_path())
        if during_wizard is not None and held is not None:
            during_wizard.append(held.job)
        return [RowOutcome(PlanRow("claude", Disposition.INSTALL, ""), "done")]

    def schedule_context(_platform: Platform, _present: Callable[[str], bool]) -> ScheduleContext:
        return replace(env.ctx, present=_claude_only)

    def services(
        _tools: list[Tool], _platform: Platform
    ) -> tuple[_Refresh, object, object, object]:
        return _Refresh(), object(), object(), object()

    def nothing(*_args: object, **_kwargs: object) -> None:
        return None

    settings = tmp_path / "settings.json"
    monkeypatch.setattr(setup, "load_tools", _no_tools)
    monkeypatch.setattr(setup, "detect", lambda: FEDORA)
    monkeypatch.setattr(setup, "_build_services", services)
    monkeypatch.setattr(setup, "_schedule_context", schedule_context)
    monkeypatch.setattr(setup, "run_wizard", fake_run_wizard)
    monkeypatch.setattr(setup, "configure_path", nothing)
    monkeypatch.setattr(setup, "_verify_and_clean", nothing)
    monkeypatch.setattr(setup, "_sync_terminals_and_report", nothing)
    monkeypatch.setattr(setup, "render_troubleshooting", nothing)
    monkeypatch.setattr("installer.settings.default_settings_path", lambda: settings)
    monkeypatch.setattr(setup, "default_settings_path", lambda: settings)
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=200, no_color=True))
    return ran


def test_headless_route_turns_schedules_on_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, present=frozenset())
    buffer = io.StringIO()
    during_wizard: list[str] = []
    _headless(monkeypatch, tmp_path, env, buffer, during_wizard=during_wizard)
    during_reconcile: list[str] = []
    real = schedules.ensure_schedule_defaults

    def watching(ctx: ScheduleContext) -> ReconcileReport:
        held = runlock.holder(runlock.run_lock_path())
        if held is not None:
            during_reconcile.append(held.job)
        return real(ctx)

    monkeypatch.setattr(schedules, "ensure_schedule_defaults", watching)

    assert setup.main(["--all", "--yes"]) == 0

    assert buffer.getvalue().count(TURNED_ON) == 1
    assert len(unit_files(env.ctx, CLAUDE_BASENAME)) == 3
    assert during_wizard == ["installer"]
    assert during_reconcile == ["installer"]
    assert runlock.holder(runlock.run_lock_path()) is None

    again = io.StringIO()
    monkeypatch.setattr(setup, "Console", lambda: Console(file=again, width=200, no_color=True))
    assert setup.main(["--all", "--yes"]) == 0
    assert "Turned on schedules" not in again.getvalue()


def test_headless_route_refuses_during_a_scheduled_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, present=frozenset())
    buffer = io.StringIO()
    ran = _headless(monkeypatch, tmp_path, env, buffer)
    held = runlock.try_acquire(runlock.run_lock_path(), "update-claude")
    assert held is not None
    try:
        assert setup.main(["--all", "--yes"]) == 1
    finally:
        held.release()

    assert REFUSAL in buffer.getvalue()
    assert ran == []
    assert not unit_files(env.ctx, CLAUDE_BASENAME)


def test_schedule_default_warnings_moved() -> None:
    assert not hasattr(policy, "DaemonDefaultWarnings")
    unarmed = ScheduleDefaultWarnings()
    assert unarmed.wait(0.0) == ((), True)
    armed = ScheduleDefaultWarnings()
    armed.arm()
    armed.append("note")
    assert armed.wait(0.01) == (("note",), False)
    armed.finish()
    assert armed.wait(0.01) == (("note",), True)


# -- the TUI reconciles at mount and after each install run --------------------------------


def no_competitors(*, blocking: bool = True) -> tuple[CompetingUnit, ...]:
    del blocking
    return ()


def _tui_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    env: Env,
    present: set[str],
    *,
    initial_view: str = BASE_VIEW,
    warnings: ScheduleDefaultWarnings | None = None,
) -> UnifiedApp:
    """The real `_build_app` on a scratch HOME, wired to `env`'s fake schedule seams."""
    sandbox: Callable[[pytest.MonkeyPatch, Path], None] = vars(test_setup)["_sandbox"]
    bind_refresh: Callable[..., object] = vars(test_setup)["_bind_refresh"]
    sandbox(monkeypatch, tmp_path)
    make_env_home = env.home  # make_env pointed HOME at its own scratch dir; keep that
    monkeypatch.setenv("HOME", str(make_env_home))
    bind_refresh(monkeypatch, FrozenStateService)

    def schedule_context(_platform: Platform, _present: Callable[[str], bool]) -> ScheduleContext:
        return replace(env.ctx, present=present.__contains__)

    monkeypatch.setattr(setup, "_schedule_context", schedule_context)
    return setup._build_app(  # pyright: ignore[reportPrivateUsage]
        [],
        FEDORA,
        initial_view=initial_view,
        apply_schedule_defaults=True,
        schedule_default_warnings=warnings,
        competing=no_competitors,  # the Schedules view warms this probe; never the host's
    )


async def test_mount_reconcile_turns_undecided_schedules_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, present=frozenset())
    app = _tui_app(monkeypatch, tmp_path, env, {"claude"})
    holders: list[object] = []
    real = schedules.ensure_schedule_defaults

    def watching(ctx: ScheduleContext) -> ReconcileReport:
        holders.append(app.mutation_holder)
        return real(ctx)

    monkeypatch.setattr(schedules, "ensure_schedule_defaults", watching)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        assert app.view(BASE_VIEW).status.text == TURNED_ON
        assert len(unit_files(env.ctx, CLAUDE_BASENAME)) == 3
        assert not app.mutation_in_flight
    assert holders == [MutationHolder.SCHEDULE_DEFAULTS]
    assert MutationHolder.SCHEDULE_DEFAULTS == "A schedule setup"
    assert "DAEMON_DEFAULT" not in MutationHolder.__members__


async def test_the_mount_reconcile_releases_the_lock_when_it_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, present=frozenset())
    app = _tui_app(monkeypatch, tmp_path, env, {"claude"})

    def boom(_ctx: ScheduleContext) -> ReconcileReport:
        raise RuntimeError("the reconcile broke")

    monkeypatch.setattr(schedules, "ensure_schedule_defaults", boom)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        assert not app.mutation_in_flight
        assert app.view(BASE_VIEW).status.text == ""


async def test_the_reconcile_closure_finishes_the_warning_collector_when_it_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The console waits on the collector after the app exits: an exception outside the
    reconcile's own handling must still signal it, or the wait runs its full timeout."""
    env = make_env(tmp_path, monkeypatch, present=frozenset())
    collector = ScheduleDefaultWarnings()
    app = _tui_app(monkeypatch, tmp_path, env, {"claude"}, warnings=collector)

    def boom(_ctx: ScheduleContext) -> ReconcileReport:
        raise RuntimeError("outside the reconcile's own handling")

    monkeypatch.setattr(schedules, "ensure_schedule_defaults", boom)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
    messages, completed = collector.wait(0.05)
    assert messages == ()
    assert completed is True


async def test_install_run_then_reconcile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SPEC edge R3: a tool the run installs gets its update schedule in the same session."""
    env = make_env(tmp_path, monkeypatch, present=frozenset())
    present: set[str] = set()
    app = _tui_app(monkeypatch, tmp_path, env, present)
    opencode = "tools-installer-schedule-update-opencode"
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        assert not unit_files(env.ctx, opencode)
        present.add("opencode")  # the fake run put it on PATH
        done = RowOutcome(PlanRow("opencode", Disposition.INSTALL, ""), "done")
        app.post_message(InstallRunFinished([done], None, "", ""))
        # settle alone can return before the message's worker exists; wait for its result.
        await wait_until(pilot, lambda: len(unit_files(env.ctx, opencode)) == 3)
        await settle(app, pilot)
        assert not app.mutation_in_flight


async def test_an_on_daemon_stays_on_across_the_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC R9 / T-24.2-43: today's live tmp units are rewritten in place with one restart and
    never disabled or stopped; Schedules row 1 then toggles those very units."""
    env = make_env(tmp_path, monkeypatch, present=frozenset())
    old = seed_legacy_tmp(env)
    off = ScheduleRecord(False, 6, "00:00", ())
    update_state(
        env.ctx.state_path,
        lambda state: replace(state, records={**state.records, "cache-cleanup": off}),
    )
    app = _tui_app(monkeypatch, tmp_path, env, set(), initial_view="schedules")
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        assert env.run.text() == [
            "daemon-reload",
            f"enable {TMP_BASENAME}.timer",
            f"restart {TMP_BASENAME}.timer",
        ]  # no disable or stop: the running timer is never off, even for a moment
        service = env.ctx.unit_dir / f"{TMP_BASENAME}.service"
        assert service.read_bytes() != old[service]
        assert not (env.ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND).exists()
        screen = app.screen
        assert isinstance(screen, SchedulesScreen)
        table = screen.query_one(DataTable[Any])
        assert table.get_cell("tmp-cleanup", "state").plain == "● [on]"

        table.move_cursor(row=0)
        await pilot.press("space")
        await settle(app, pilot)
        assert table.get_cell("tmp-cleanup", "state").plain == "○ [off]"
        assert not unit_files(env.ctx, TMP_BASENAME)
        await pilot.press("space")
        await settle(app, pilot)
        assert table.get_cell("tmp-cleanup", "state").plain == "● [on]"
        assert len(unit_files(env.ctx, TMP_BASENAME)) == 3


def test_disk_pressure_points_at_schedules() -> None:
    """R1-17: the Doctor's next step names the Schedules tmp cleanup row, not the Policies one."""
    pressure = DiskPressure(
        home_free_percent=5.0,
        tmp_used_percent=10.0,
        daemon=DaemonState.INACTIVE,
        tmp_threshold=True,
    )
    [item] = disk_pressure_guidance(pressure)
    assert item.next_step.startswith("Turn on tmp cleanup in `make setup`'s Schedules view; a ")
    assert "Policies" not in item.next_step


# -- removals take their target's timer, and the uninstall sweeps every schedule --------------


def _receipted(env: Env, tool_id: str, file_name: str) -> tuple[Tool, Path]:
    """A receipt-proven raw download named `tool_id` under the scratch HOME's bin dir."""
    yq, bin_dir = plant_raw_yq(env.home, with_receipt=False)
    raw = Method(
        kind="github_release",
        params={"repo": f"a/{tool_id}", "asset": file_name, "member": file_name, "raw": True},
    )
    tool = replace(yq, id=tool_id, name=tool_id, cmd=tool_id, methods=(raw,))
    binary = bin_dir / file_name
    binary.write_text(f"{tool_id} raw binary")
    write_receipt(tool, [(binary, "file")])
    return tool, binary


def _removal_hook(ctx: ScheduleContext) -> Callable[[str], tuple[str, ...]]:
    def hook(tool_id: str) -> tuple[str, ...]:
        report = schedules.after_target_removed(ctx, tool_id)
        return tuple(text for text, _severity in schedules.reconcile_lines(report))

    return hook


def _perform(
    env: Env,
    decision: UninstallDecision,
    *,
    extras: tuple[Policy, ...] = (),
    hook: Callable[[str], tuple[str, ...]] | None = None,
) -> SweepResult:
    return perform_uninstall(
        decision,
        bin_dir=env.home / ".local" / "bin",
        myshellrc_path=env.ctx.myshellrc_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=env.home / ".zshrc",
        extra_policies=extras,
        runner=_no_command,
        catalog=decision.tools,
        schedule_removed=hook,
    )


def _absent(_tool_id: str) -> bool:
    return False


def _no_command(cmd: list[str]) -> None:
    raise AssertionError(f"no removal command expected: {cmd}")


def _decision(tool: Tool, binary: Path, *, tweaks: bool = False) -> UninstallDecision:
    return UninstallDecision(
        tools=(tool,),
        paths={tool.id: (binary,)},
        remove_ban=False,
        remove_path_block=False,
        remove_tweaks=tweaks,
    )


def test_tui_removal_takes_the_timer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F3: removing a receipted claude takes its timer files, keeps its decision, says so, and
    the Schedules row then reads unavailable at once."""
    env = make_env(tmp_path, monkeypatch, present=frozenset({"claude"}))
    ctx = env.ctx
    claude, binary = _receipted(env, "claude", "claude")
    schedules.turn_on(ctx, "update-claude")
    assert len(unit_files(ctx, CLAUDE_BASENAME)) == 3

    result = _perform(env, _decision(claude, binary), hook=_removal_hook(ctx))

    assert not binary.exists(), (result.warnings, result.remove_failed)
    assert unit_files(ctx, CLAUDE_BASENAME) == []
    state = schedules.load_state(ctx.state_path).state
    assert state.records["update-claude"].decided is True
    assert "Removed the claude update timer because claude is gone." in removal_result_lines(result)
    after = replace(ctx, present=_absent)
    row = schedules.row_state(
        after, state, schedules.schedule_by_id("update-claude"), manager=True, present=after.present
    )
    assert (row.word, row.reason) == ("n/a", "unavailable: claude not installed")


def test_cli_removal_takes_the_timer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, present=frozenset({"claude"}))
    ctx = env.ctx
    claude, _binary = _receipted(env, "claude", "claude")
    schedules.turn_on(ctx, "update-claude")
    buffer = io.StringIO()

    _removed, failed = run_uninstall(
        [claude],
        Console(file=buffer, width=200, no_color=True),
        default_bin_dir=env.home / ".local" / "bin",
        myshellrc_path=ctx.myshellrc_path,
        rc_paths=[],
        confirm=lambda _message: True,
        bundles=(),
        zshrc_path=env.home / ".zshrc",
        extra_policies=(),
        runner=_no_command,
        schedule_removed=_removal_hook(ctx),
    )

    assert failed == ()
    assert unit_files(ctx, CLAUDE_BASENAME) == []
    assert "Removed the claude update timer because claude is gone." in buffer.getvalue()


@pytest.mark.parametrize("foreign", [False, True])
def test_cursor_removal_removes_the_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign: bool
) -> None:
    """Our cursor-agent shim goes with the tool; a file that is not ours stays."""
    env = make_env(tmp_path, monkeypatch, present=frozenset({"cursor-agent"}))
    install = Install(env.home, foreign=foreign)
    cursor, _binary = _receipted(env, "cursor-agent", "cursor-agent-launcher")
    schedules.turn_on(env.ctx, "update-cursor-agent")
    assert install.link.exists() or install.link.is_symlink()

    _perform(env, _decision(cursor, _binary), hook=_removal_hook(env.ctx))

    if foreign:
        assert install.link.read_text() == "#!/bin/sh\necho mine\n"
    else:
        assert not install.link.exists()
        assert not install.link.is_symlink()


def _on_lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, os_key: str) -> tuple[Env, list[str]]:
    env = make_env(tmp_path, monkeypatch, os_key=os_key, present=frozenset({"claude"}))
    ensure = schedules.ensure_schedule_defaults(env.ctx)
    assert ensure.turned_on == ("tmp-cleanup", "cache-cleanup", "update-claude")
    return env, ["schedule:tmp-cleanup", "schedule:cache-cleanup", "schedule:update-claude"]


def _schedule_leftovers(ctx: ScheduleContext) -> list[str]:
    found = [
        str(path)
        for root in (ctx.unit_dir, ctx.launch_agents_dir, ctx.data_dir)
        if root.exists()
        for path in sorted(root.rglob("*"))
        if path.is_file() or path.is_symlink()
    ]
    found += [
        str(path) for path in (ctx.state_path, ctx.log_path, ctx.launchd_log_path) if path.exists()
    ]
    marker = daemon.decided if ctx.platform_os == "macos" else systemd_decided
    if marker(ctx.myshellrc_path):
        found.append("the tmp decided marker")
    return found


@pytest.mark.parametrize("os_key", ["fedora", "macos"])
def test_full_uninstall_sweeps_schedules_tui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, os_key: str
) -> None:
    env, ids = _on_lab(tmp_path, monkeypatch, os_key)
    ctx = env.ctx
    claude, binary = _receipted(env, "claude", "claude")
    extras = schedules.sweep_adapters(ctx)  # built before the removal (R1-19)
    assert [policy.id for policy in extras] == ids

    result = _perform(
        env, _decision(claude, binary, tweaks=True), extras=extras, hook=_removal_hook(ctx)
    )

    # The removal hook took claude's timer first, so the sweep finds nothing left to sweep for it.
    assert set(ids[:2]) <= set(result.swept)
    assert "Removed the claude update timer because claude is gone." in removal_result_lines(result)
    assert result.failed == ()
    assert _schedule_leftovers(ctx) == []


@pytest.mark.parametrize("os_key", ["fedora", "macos"])
def test_full_uninstall_sweeps_schedules_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, os_key: str
) -> None:
    env, ids = _on_lab(tmp_path, monkeypatch, os_key)
    ctx = env.ctx
    claude, _binary = _receipted(env, "claude", "claude")
    buffer = io.StringIO()

    run_uninstall(
        [claude],
        Console(file=buffer, width=300, no_color=True),
        default_bin_dir=env.home / ".local" / "bin",
        myshellrc_path=ctx.myshellrc_path,
        rc_paths=[],
        confirm=lambda _message: True,
        bundles=(),
        zshrc_path=env.home / ".zshrc",
        extra_policies=schedules.sweep_adapters(ctx),
        runner=_no_command,
        schedule_removed=_removal_hook(ctx),
    )

    text = buffer.getvalue()
    assert "These shell tweaks and the background maintenance jobs will also be disabled" in text
    assert "Shell tweaks and the background maintenance jobs disabled:" in text
    assert all(schedule_id in text for schedule_id in ids)
    assert _schedule_leftovers(ctx) == []


def test_cli_uninstall_refuses_during_a_scheduled_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox: Callable[[pytest.MonkeyPatch, Path], None] = vars(test_setup)["_sandbox"]
    sandbox(monkeypatch, tmp_path)
    state = schedules.default_state_path()
    schedules.save_state(state, schedules.ScheduleState())
    buffer = io.StringIO()
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=200, no_color=True))

    def boom(*_args: object, **_kwargs: object) -> tuple[list[Path], tuple[str, ...]]:
        raise AssertionError("the teardown must not start while a scheduled run holds the lock")

    monkeypatch.setattr(setup, "run_uninstall", boom)
    held = runlock.try_acquire(runlock.run_lock_path(), "update-claude")
    assert held is not None
    try:
        assert setup.main(["--uninstall", "--yes"]) == 1
    finally:
        held.release()

    assert REFUSAL in buffer.getvalue()
    assert state.exists()


def test_a_non_utf8_rc_breaks_neither_the_sweep_nor_the_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An rc file that cannot be read is never a crash and never an invitation to turn tmp on."""
    env = make_env(tmp_path, monkeypatch, present=frozenset())
    env.ctx.myshellrc_path.write_bytes(b"# caf\xe9\n")

    assert schedules.sweep_adapters(env.ctx) == ()
    report = schedules.ensure_schedule_defaults(env.ctx)

    assert "tmp-cleanup" not in report.turned_on
    assert not unit_files(env.ctx, TMP_BASENAME)
    assert env.ctx.myshellrc_path.read_bytes() == b"# caf\xe9\n"
