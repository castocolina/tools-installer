"""D-12: the app's mutations and a scheduled run serialize on one cross-process run lock.

A test "scheduled run" is a `runlock.try_acquire` the test itself holds under the scratch HOME.
"""

import fcntl
import importlib
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from installer import runlock
from installer.engine import InstallOutcome
from installer.enums import InstallStatus, MutationHolder, Severity
from installer.execute_screen import ExecuteInputs, ExecuteScreen
from installer.locations import ensure_dir
from installer.model import Tool
from installer.platform import Platform
from installer.uninstall import SweepResult
from installer.wizard_app import SCHEDULED_RUN_REFUSAL, MutationLock
from tests.screen_family import HeldRemover, settle, wait_until
from tests.state_doubles import presence_service

# The family helpers are private to their module; read them by name.
_FAMILY = vars(importlib.import_module("tests.test_screen_family"))

_SENTENCE = "A scheduled run is running; wait for it to finish. Navigation still works."


def _scheduled_run() -> runlock.RunLock:
    held = runlock.try_acquire(runlock.run_lock_path(), "update-claude")
    assert held is not None
    return held


def _installer_holds() -> bool:
    holder = runlock.holder(runlock.run_lock_path())
    return holder is not None and holder.job == "installer" and holder.pid == os.getpid()


def _update_app(tmp_path: Path, updates: Any) -> Any:
    app, _service = _FAMILY["_update_app"](tmp_path, updates, HeldRemover())
    return app


async def test_update_refused_while_a_scheduled_run_holds_the_lock(tmp_path: Path) -> None:
    updates = _FAMILY["_HeldUpdates"]()
    app = _update_app(tmp_path, updates)
    scheduled = _scheduled_run()
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            await settle(app, pilot)
            _FAMILY["_catalog_cursor"](app, "rg")
            await pilot.press("u")
            assert not updates.started.is_set()
            assert updates.targets == []
            assert app.catalog.status.text == _SENTENCE
            assert not app.mutation_in_flight
            scheduled.release()
            await pilot.press("u")
            await wait_until(pilot, updates.started.is_set)
            assert _installer_holds()
        finally:
            scheduled.release()
            updates.release.set()
        await settle(app, pilot)
        assert not app.mutation_in_flight


async def test_begin_mutation_reports_a_lost_race(tmp_path: Path) -> None:
    app = _FAMILY["_family_app"]()
    path = runlock.run_lock_path()
    # A runner between its flock and its holder line: locked, no line to read.
    ensure_dir(path.parent)
    racer = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(racer, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        async with app.run_test(size=(80, 20)) as pilot:
            await settle(app, pilot)
            assert not app.refuse_if_mutating(app.catalog, cross_process=True)
            assert app.begin_mutation(MutationHolder.UPDATE, screen=app.catalog) is False
            assert app.catalog.status.text == _SENTENCE
            assert (app.catalog.status.severity) == Severity.WARN
            assert not app.mutation_in_flight
    finally:
        os.close(racer)
    lock = MutationLock()
    assert lock.begin_mutation(MutationHolder.UPDATE) is True
    with pytest.raises(RuntimeError, match="An update"):
        lock.begin_mutation(MutationHolder.REMOVAL)
    lock.end_mutation()


def test_begin_mutation_ignores_the_lock_for_in_app_holders(tmp_path: Path) -> None:
    lock = MutationLock()
    assert lock.begin_mutation(MutationHolder.POLICY_TOGGLE) is True
    assert not runlock.run_lock_path().exists()
    lock.end_mutation()
    assert lock.begin_mutation(MutationHolder.SCHEDULE_CHANGE) is True
    assert not runlock.run_lock_path().exists()


def test_lock_is_released_after_each_mutation(tmp_path: Path) -> None:
    lock = MutationLock()
    assert lock.begin_mutation(MutationHolder.REMOVAL) is True
    assert _installer_holds()
    lock.end_mutation()
    again = runlock.try_acquire(runlock.run_lock_path(), "update-claude")
    assert again is not None
    again.release()
    assert runlock.run_lock_path().read_bytes() == b""


def test_holder_nouns() -> None:
    assert MutationHolder.SCHEDULE_CHANGE == "A schedule change"
    assert "A scheduled run" not in {holder.value for holder in MutationHolder}
    assert SCHEDULED_RUN_REFUSAL == _SENTENCE


async def test_removal_refused_during_a_scheduled_run(tmp_path: Path) -> None:
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, _service = _FAMILY["_removal_app"](tmp_path, remover)
    scheduled = _scheduled_run()
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            await _FAMILY["_confirm_removal"](app, pilot, "yq")
            assert remover.calls == []
            assert app.view("uninstall").status.text == _SENTENCE
            assert not app.mutation_in_flight
            scheduled.release()
            await pilot.press("enter")
            await pilot.press("enter")
            await wait_until(pilot, remover.started.is_set)
            assert _installer_holds()
        finally:
            scheduled.release()
            remover.release.set()
        await settle(app, pilot)
        assert not app.mutation_in_flight


async def test_globals_reinstall_refused_during_a_scheduled_run(tmp_path: Path) -> None:
    started, release = threading.Event(), threading.Event()
    app, _service = _FAMILY["_reinstall_app"](
        tmp_path, HeldRemover(), _FAMILY["_held_reinstall"](started, release)
    )
    scheduled = _scheduled_run()
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _FAMILY["_open_view"](app, pilot, "doctor")
            await pilot.press("r")
            assert app.view("doctor").status.text == _SENTENCE
            assert not started.is_set()
            assert not app.mutation_in_flight
        finally:
            scheduled.release()
            release.set()


def _install_app(
    installs: list[str], outcome: InstallStatus, started: threading.Event, release: threading.Event
) -> Any:
    rg: Tool = _FAMILY["_tool"]("rg")
    platform = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)

    def install(tool: Tool, *_args: Any, **_kwargs: Any) -> InstallOutcome:
        installs.append(tool.id)
        started.set()
        assert release.wait(timeout=10)
        return InstallOutcome(tool.id, outcome)

    service = presence_service([rg], platform=platform)
    inputs = ExecuteInputs(
        catalog=[rg],
        platform=platform,
        wire_path=lambda: "PATH wired",
        verify=lambda: "PATH verified",
        install=install,
        version_refresh=service,
    )
    return _FAMILY["_family_app"](tools=[rg], version_refresh=service, execute=inputs)


async def _accept_rg(app: Any, pilot: Any) -> None:
    _FAMILY["_catalog_cursor"](app, "rg")
    await pilot.press("space", "enter")


@pytest.mark.parametrize("outcome", [InstallStatus.INSTALLED, InstallStatus.FAILED])
async def test_install_run_never_starts_when_refused(
    tmp_path: Path, outcome: InstallStatus
) -> None:
    installs: list[str] = []
    started, release = threading.Event(), threading.Event()
    app = _install_app(installs, outcome, started, release)
    scheduled = _scheduled_run()
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            # Refused at the accept point.
            await _accept_rg(app, pilot)
            assert app.catalog.status.text == _SENTENCE
            assert not isinstance(app.screen, ExecuteScreen)
            scheduled.release()
            # The runner wins the race between the accept and the start.
            await pilot.press("enter")
            await wait_until(pilot, lambda: isinstance(app.screen, ExecuteScreen))
            scheduled = _scheduled_run()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await pilot.press("enter")
            assert not screen.started
            assert installs == []
            assert not app.mutation_in_flight
            assert not app.run_in_flight
            assert screen.status.text == _SENTENCE
            # With the lock free the same screen starts the run.
            scheduled.release()
            await pilot.press("enter")
            await wait_until(pilot, started.is_set)
            assert screen.started
            assert _installer_holds()
            release.set()
            await wait_until(pilot, lambda: not app.mutation_in_flight)
            probe = runlock.try_acquire(runlock.run_lock_path(), "update-claude")
            assert probe is not None
            probe.release()
        finally:
            scheduled.release()
            release.set()


async def test_toggles_never_take_the_run_lock(tmp_path: Path) -> None:
    applied: list[str] = []

    def apply() -> Any:
        applied.append("job")
        return _FAMILY["_policy_result"]()

    app, _service = _FAMILY["_policy_app"](
        tmp_path,
        [_FAMILY["_policy"](tmp_path, "job", apply=apply)],
        HeldRemover(),
    )
    scheduled = _scheduled_run()
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await _FAMILY["_open_view"](app, pilot, "policies")
            _FAMILY["_policy_cursor"](app, "job")
            await pilot.press("space")
            await settle(app, pilot)
            assert applied == ["job"]
            assert app.begin_mutation(MutationHolder.SCHEDULE_CHANGE) is True
            app.end_mutation()
        finally:
            scheduled.release()
