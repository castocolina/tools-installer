"""The headless single-tool update a schedule timer runs (SPEC R6).

`setup.py --run-schedule update-<tool>` lands here: one tool is updated through the same
ownership-first `UpdateService` the catalog's `u` uses, and the outcome becomes one plain result
line with a matching exit code. This module decides; `setup.py` only wires the real services.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from installer import cursor_shim, runlock, schedules
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


def _first_line(text: str) -> str:
    """The first non-empty line of `text`, sanitized and bounded; empty when there is none."""
    lines = (line.strip() for line in sanitize_log_line(text).splitlines())
    return next((line for line in lines if line), "")[:_REASON_LIMIT]


def _reason(error: Exception) -> str:
    return _first_line(str(error)) or type(error).__name__


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
    line, code = schedules.update_result_line(outcome, before, after)
    if outcome.receipt_warning:
        line += f"; warning: {_first_line(outcome.receipt_warning)}"
    return line, code


def _agent_resolves(agent: Path) -> bool:
    try:
        agent.resolve(strict=True)
    except (OSError, RuntimeError):  # a symlink loop is a RuntimeError before Python 3.13
        return False
    return True


def _shim_note(report: cursor_shim.ShimReport) -> str:
    if report.write == "kept-foreign":
        return "; your own cursor-agent was kept"
    if report.check == "not-listed":
        return f"; {report.model} is not in your model list, the shim passes arguments through"
    if report.check == "unverified":
        return "; model unverified"
    return ""


def _refresh_cursor_shim(context: schedules.ScheduleContext) -> str:
    """Put the shim back after a cursor-agent update, only while the row is decided on.

    The decision is read and the shim written in one critical section under the state lock, the
    one `turn_off` restores the link under, so an off pressed during the update is never undone
    (R1-08). The slow model list is read before the lock is taken. Returns the warning to append
    to the result line; an OSError from the refresh propagates.
    """
    link, agent = cursor_shim.shim_paths(context.home)
    models = context.read_models(agent)  # up to 40 s: never inside the lock
    # Not `update_state`: it opens this same lock file again, which would block against ours.
    with runlock.hold(schedules.state_lock_path(context.state_path)):
        state = schedules.load_state(context.state_path).state
        if schedules.record_for(state, "update-cursor-agent").decided is not True:
            return ""
        report = cursor_shim.refresh_shim(
            link=link, agent=agent, model=state.cursor_default_model, models=models
        )
        status = "kept-foreign" if report.write == "kept-foreign" else report.check
        if state.cursor_shim != status:
            schedules.save_state(context.state_path, replace(state, cursor_shim=status))
    return _shim_note(report)


def _update_cursor_agent(
    schedule: schedules.Schedule, deps: RunDeps, context: schedules.ScheduleContext
) -> tuple[str, int]:
    _link, agent = cursor_shim.shim_paths(context.home)
    if not _agent_resolves(agent):  # SPEC edge R7 empty: nothing is updated or rewritten
        return "failed: ~/.local/bin/agent is missing or dangling", 1
    line, code = _update(schedule, deps)
    try:
        return line + _refresh_cursor_shim(context), code
    except OSError as error:
        return f"failed: {_reason(error)}", 1


def _run_unlocked(schedule: schedules.Schedule, deps: RunDeps) -> tuple[str, int]:
    if schedule.target == "cursor-agent" and deps.context is not None:
        return _update_cursor_agent(schedule, deps, deps.context)
    return _update(schedule, deps)


def run_schedule(schedule_id: str, deps: RunDeps, *, parent_holds_lock: bool) -> tuple[str, int]:
    """Run one update schedule and return its result line and exit code.

    The schedule runner that spawned a timer's run already holds the run lock
    (`parent_holds_lock`); a manual run takes it itself and skips when it is held (D-12).
    """
    schedule = schedules.schedule_by_id(schedule_id)
    if schedule.kind is not schedules.JobKind.UPDATE:
        return f"failed: {schedule_id} is not an update schedule", 2
    if parent_holds_lock:
        return _run_unlocked(schedule, deps)
    lock_path = deps.context.lock_path if deps.context is not None else runlock.run_lock_path()
    try:
        lock = runlock.try_acquire(lock_path, schedule_id)
    except OSError as error:
        return f"failed: {_reason(error)}", 1
    if lock is None:
        return "skipped: busy", 0
    try:
        return _run_unlocked(schedule, deps)
    finally:
        lock.release()
