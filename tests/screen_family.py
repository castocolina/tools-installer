"""Helpers shared by the screen-family pilots: poll until a condition holds."""

import threading
from collections.abc import Callable
from typing import Any

from textual.app import App
from textual.worker import WorkerState

from installer.app import UninstallDecision
from installer.uninstall import SweepResult


async def wait_until(pilot: Any, predicate: Callable[[], bool], tries: int = 400) -> None:
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause()
    raise AssertionError("condition never became true within the polling budget")


async def settle(app: App[Any], pilot: Any) -> None:
    """Wait until no worker is pending or running, then pause once."""
    busy = (WorkerState.PENDING, WorkerState.RUNNING)
    await wait_until(pilot, lambda: not any(w.state in busy for w in app.workers))
    await pilot.pause()


class HeldRemover:
    """A removal closure that waits until the test releases it (never hangs the suite)."""

    def __init__(self, result: SweepResult | None = None, *, raising: Exception | None = None):
        self.result = result if result is not None else SweepResult()
        self.raising = raising
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls: list[UninstallDecision] = []

    def __call__(self, decision: UninstallDecision) -> SweepResult:
        self.calls.append(decision)
        self.started.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("HeldRemover was never released")
        if self.raising is not None:
            raise self.raising
        return self.result
