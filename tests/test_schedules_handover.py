"""The switch from Policies to Schedules: the headless route, the TUI reconciles, the uninstall.

Every service-manager call goes to the recording fakes of `test_schedules_engine`; every file lands
under the scratch HOME. The composition root is driven in-process through its own test seams.
"""

import io
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from rich.console import Console

import setup
from installer import policy, runlock, schedules
from installer.model import Tool
from installer.platform import Platform
from installer.schedules import ReconcileReport, ScheduleContext, ScheduleDefaultWarnings
from installer.session import Disposition, PlanRow, RowOutcome
from tests.test_schedules_engine import CLAUDE_BASENAME, Env, make_env
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
