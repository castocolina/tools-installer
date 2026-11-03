"""Helpers shared by the screen-family pilots: poll until a condition holds."""

from collections.abc import Callable
from typing import Any

from textual.app import App
from textual.worker import WorkerState


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
