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
from installer.diskusage import DiskPressure
from installer.enums import DaemonState, MutationHolder
from installer.execute_screen import InstallRunFinished
from installer.guidance import disk_pressure_guidance
from installer.model import Tool
from installer.platform import Platform
from installer.schedules import (
    ReconcileReport,
    ScheduleContext,
    ScheduleDefaultWarnings,
    ScheduleRecord,
    update_state,
)
from installer.session import Disposition, PlanRow, RowOutcome
from installer.ui_common import BASE_VIEW
from installer.wizard_app import SchedulesScreen, UnifiedApp
from tests import test_setup
from tests.screen_family import settle
from tests.state_doubles import FrozenStateService
from tests.test_schedules_engine import (
    CLAUDE_BASENAME,
    TMP_BASENAME,
    Env,
    make_env,
    seed_legacy_tmp,
)
from tests.test_schedules_lifecycle import unit_files

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


def _tui_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    env: Env,
    present: set[str],
    *,
    initial_view: str = BASE_VIEW,
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
        [], FEDORA, initial_view=initial_view, apply_schedule_defaults=True
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
        await settle(app, pilot)
        assert len(unit_files(env.ctx, opencode)) == 3
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
