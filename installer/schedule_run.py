"""The headless single-tool update a schedule timer runs (SPEC R6).

`setup.py --run-schedule update-<tool>` lands here: one tool is updated through the same
ownership-first `UpdateService` the catalog's `u` uses, and the outcome becomes one plain result
line with a matching exit code. This module decides; `setup.py` only wires the real services.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from installer import schedules
from installer.model import Tool
from installer.ownership import ManagerOwnership
from installer.run import CommandError
from installer.sanitize import sanitize_log_line
from installer.update import UpdateError, UpdateService, UpdateTarget

_REASON_LIMIT = 300


@dataclass(frozen=True)
class RunDeps:
    """The seams a run needs; `context` carries the shim paths, the state and lock paths."""

    tools: Sequence[Tool]
    updates: UpdateService
    resolve_owner: Callable[[Tool], ManagerOwnership]
    probe_version: Callable[[Tool, ManagerOwnership], str | None]
    context: schedules.ScheduleContext | None


def _reason(error: Exception) -> str:
    """The first non-empty line of the error, sanitized and bounded."""
    lines = (line.strip() for line in sanitize_log_line(str(error)).splitlines())
    return next((line for line in lines if line), "")[:_REASON_LIMIT] or type(error).__name__


def _update(schedule: schedules.Schedule, deps: RunDeps) -> tuple[str, int]:
    tool = next((tool for tool in deps.tools if tool.id == schedule.target), None)
    if tool is None:
        return f"failed: {schedule.target} is not in the catalog", 1
    try:
        ownership = deps.resolve_owner(tool)
        before = deps.probe_version(tool, ownership)
        outcome = deps.updates.run(UpdateTarget(tool=tool, ownership=ownership))
        after = (
            deps.probe_version(tool, deps.resolve_owner(tool))
            if outcome.status == "updated"
            else None
        )
    except (UpdateError, CommandError, OSError) as error:
        return f"failed: {_reason(error)}", 1
    return schedules.update_result_line(outcome, before, after)


def run_schedule(schedule_id: str, deps: RunDeps, *, parent_holds_lock: bool) -> tuple[str, int]:
    """Run one update schedule and return its result line and exit code."""
    schedule = schedules.schedule_by_id(schedule_id)
    if schedule.kind is not schedules.JobKind.UPDATE:
        return f"failed: {schedule_id} is not an update schedule", 2
    del parent_holds_lock  # the run lock is taken in a later step of this plan
    return _update(schedule, deps)
