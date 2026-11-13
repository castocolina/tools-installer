"""D-12: the app's mutations and a scheduled run serialize on one cross-process run lock.

A test "scheduled run" is a `runlock.try_acquire` the test itself holds under the scratch HOME.
"""

import fcntl
import importlib
import os
from pathlib import Path
from typing import Any

import pytest

from installer import runlock
from installer.enums import MutationHolder, Severity
from installer.locations import ensure_dir
from installer.wizard_app import SCHEDULED_RUN_REFUSAL, MutationLock
from tests.screen_family import HeldRemover, settle, wait_until

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
