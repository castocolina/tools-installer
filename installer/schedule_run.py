"""The headless single-tool update and daily update check a schedule timer runs (SPEC R6).

`setup.py --run-schedule update-<tool>` lands here: one tool is updated through the same
ownership-first `UpdateService` the catalog's `u` uses, and the outcome becomes one plain result
line with a matching exit code. This module decides; `setup.py` only wires the real services.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from types import FrameType

from installer import cursor_shim, runlock, schedules, update_all, update_all_state, update_check
from installer.model import Tool
from installer.notify import Notifier, no_notifier
from installer.ownership import ManagerOwnership
from installer.run import TIMEOUT_CODE, CommandError, apply_child_env
from installer.sanitize import sanitize_log_line
from installer.update import (
    GuardFn,
    UpdateError,
    UpdateOutcome,
    UpdateService,
    UpdateTarget,
    update_refusal,
)
from installer.version_cache import (
    MANAGER_STALE_AFTER,
    ManagerSnapshot,
    VersionCacheEntry,
    load_version_cache,
    stamp_time,
)
from installer.version_status import ToolState, outdated_ids

_REASON_LIMIT = 300


@contextmanager
def update_all_stdin_closed() -> Generator[None]:
    """Close stdin for the update-all route, including its bounded queries."""
    try:
        saved = os.dup(0)
    except OSError:
        yield
        return
    try:
        null = os.open(os.devnull, os.O_RDONLY)
        try:
            os.dup2(null, 0)
            yield
        finally:
            os.dup2(saved, 0)
            os.close(null)
    finally:
        os.close(saved)


def _end_update_group(child: subprocess.Popen[str]) -> bool:
    """End the group with four bounded waits; report whether it vanished."""

    def send(sig: signal.Signals) -> None:
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(child.pid, sig)

    send(signal.SIGTERM)
    with suppress(subprocess.TimeoutExpired):
        child.wait(timeout=update_all.KILL_GRACE)
    send(signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        child.wait(timeout=update_all.KILL_GRACE)
    try:
        child.communicate(timeout=update_all.KILL_GRACE)
    except subprocess.TimeoutExpired:
        for pipe in (child.stdout, child.stderr):
            if pipe is not None:
                pipe.close()
    deadline = time.monotonic() + update_all.KILL_GRACE
    while True:
        try:
            os.killpg(child.pid, 0)
        except (ProcessLookupError, PermissionError):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.05, remaining))
    send(signal.SIGKILL)
    print("update-all: a command group did not end after SIGKILL", file=sys.stderr)
    return False


def update_all_runner(
    cmd: list[str], *, timeout: float | None = update_all.COMMAND_TIMEOUT
) -> None:
    """Run a bounded command in its own session, with closed stdin and a copied child policy.

    The group is ended and awaited on timeout or interruption; main-thread TERM and HUP
    are forwarded through cleanup. Descendants starting new sessions can escape the group.
    Manager and postinstall queries, probes, version probes, pnpm list and bin, smoke
    checks, cursor model lists and GitHub lookups have their own bounds.
    """
    env = os.environ.copy()
    apply_child_env(env)
    env["UV_NO_MODIFY_PATH"] = "1"
    try:
        child = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            start_new_session=True,
        )
    except OSError as exc:
        raise CommandError(cmd, 127, detail=str(exc)) from exc

    def interrupted(signum: int, _frame: FrameType | None) -> None:
        raise SystemExit(128 + signum)

    previous: dict[signal.Signals, int | None | Callable[[int, FrameType | None], None]] = {}
    try:
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM, signal.SIGHUP):
                previous[sig] = signal.signal(sig, interrupted)
        try:
            _, stderr = child.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            ended = _end_update_group(child)
            detail = (
                f"timed out after {timeout:g}s"
                if ended and timeout is not None
                else ("command group did not end after SIGKILL")
            )
            raise CommandError(cmd, TIMEOUT_CODE, detail=detail) from exc
        except BaseException:
            _end_update_group(child)
            raise
        if child.returncode:
            raise CommandError(
                cmd,
                child.returncode,
                detail=stderr.strip().splitlines()[0] if stderr.strip() else "",
            )
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _euid() -> int:
    return os.geteuid()


@dataclass(frozen=True)
class RunDeps:
    """The seams a run needs; `context` carries the shim paths, the state and lock paths."""

    tools: Sequence[Tool]
    updates: UpdateService
    resolve_owner: Callable[[Tool], ManagerOwnership]
    probe_version: Callable[[Tool, ManagerOwnership], str | None]
    context: schedules.ScheduleContext | None
    # The default never reaches the host.
    notify: Notifier = no_notifier
    refresh: update_check.Refresher | None = None
    git: update_check.GitRunner | None = None
    # Inject the clock so the calendar day is a test input.
    now: Callable[[], datetime] = _local_now
    # Injected so root refusal is a test input.
    euid: Callable[[], int] = _euid


def _first_line(text: str) -> str:
    """The first non-empty line of `text`, sanitized and bounded; empty when there is none."""
    lines = (line.strip() for line in sanitize_log_line(text).splitlines())
    return next((line for line in lines if line), "")[:_REASON_LIMIT]


def _reason(error: Exception) -> str:
    return _first_line(str(error)) or type(error).__name__


@dataclass(frozen=True)
class ToolRun:
    line: str
    code: int
    mutated: bool


class _BatchGuard:
    def __init__(
        self,
        tool: Tool,
        platform_os: str,
        failed_managers: Mapping[str, str],
        completed_managers: set[str],
        catalog: Sequence[Tool],
        evidence_owner: str,
    ) -> None:
        self.tool = tool
        self.platform_os = platform_os
        self.failed_managers = failed_managers
        self.completed_managers = completed_managers
        self.catalog = catalog
        self.evidence_owner = evidence_owner
        self.root: str | None = None
        self.refused = False

    def __call__(self, fresh: ManagerOwnership) -> UpdateOutcome | None:
        refusal = update_refusal(self.tool, fresh)
        reason = update_all.exclusion(self.platform_os, fresh, refusal)
        if reason is not None:
            self.refused = True
            if refusal is not None and reason != update_all.SKIP_CASK:
                return refusal
            return UpdateOutcome(self.tool.id, "unsupported", fresh.owner, reason)
        manager = update_all.owner_manager(fresh.owner)
        self.root = update_all.blocking_manager(
            self.tool, manager, self.failed_managers, self.catalog
        )
        if self.root is not None:
            reason = f"{self.root} failed"
        elif (
            manager is not None
            and manager != self.tool.id
            and manager not in self.completed_managers
        ):
            reason = f"{manager} did not run first"
        elif fresh.owner != self.evidence_owner:
            reason = "owner changed since the evidence"
        else:
            return None
        self.refused = True
        return UpdateOutcome(self.tool.id, "unsupported", fresh.owner, reason)


def _update_tool(tool: Tool, deps: RunDeps, *, guard: GuardFn | None = None) -> ToolRun:
    try:
        ownership = deps.resolve_owner(tool)
        before = deps.probe_version(tool, ownership)
        target = UpdateTarget(tool=tool, ownership=ownership)
        outcome = (
            deps.updates.run(target) if guard is None else deps.updates.run_guarded(target, guard)
        )
    except (UpdateError, CommandError, OSError) as error:
        return ToolRun(f"failed: {_reason(error)}", 1, False)
    try:
        after = (
            deps.probe_version(tool, deps.resolve_owner(tool))
            if outcome.status == "updated"
            else None
        )
    except (UpdateError, CommandError, OSError) as error:
        return ToolRun(f"failed: {_reason(error)}", 1, True)
    line, code = schedules.update_result_line(outcome, before, after)
    if outcome.receipt_warning:
        line += f"; warning: {_first_line(outcome.receipt_warning)}"
    return ToolRun(line, code, outcome.mutated)


def _update(
    schedule: schedules.Schedule, deps: RunDeps, *, guard: GuardFn | None = None
) -> ToolRun:
    tool = next((tool for tool in deps.tools if tool.id == schedule.target), None)
    if tool is None:
        return ToolRun(f"failed: {schedule.target} is not in the catalog", 1, False)
    return _update_tool(tool, deps, guard=guard)


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
    schedule: schedules.Schedule,
    deps: RunDeps,
    context: schedules.ScheduleContext,
    *,
    guard: GuardFn | None = None,
) -> ToolRun:
    _link, agent = cursor_shim.shim_paths(context.home)
    if not _agent_resolves(agent):  # SPEC edge R7 empty: nothing is updated or rewritten
        return ToolRun("failed: ~/.local/bin/agent is missing or dangling", 1, False)
    run = _update(schedule, deps, guard=guard)
    if guard is not None and run.line.startswith("skipped:"):
        return run
    try:
        return ToolRun(run.line + _refresh_cursor_shim(context), run.code, run.mutated)
    except OSError as error:
        return ToolRun(f"failed: {_reason(error)}", 1, run.mutated)


def _check(deps: RunDeps) -> tuple[str, int]:
    if deps.refresh is None or deps.git is None or deps.context is None:
        return "failed: the update check is not wired", 2
    return update_check.run_check(
        deps.tools, refresh=deps.refresh, notify=deps.notify, context=deps.context, git=deps.git
    )


# Mirrors update_check._MANAGER_SOURCES.
MANAGER_SOURCES = frozenset({"brew", "cask", "pnpm", "uv"})
MANAGER_OF_SOURCE = {"brew": "brew", "cask": "brew", "pnpm": "pnpm", "uv": "uv"}


@dataclass(frozen=True)
class RefreshPass:
    states: dict[str, ToolState]
    entries: dict[str, VersionCacheEntry]
    snapshot: ManagerSnapshot | None
    started: datetime


def _refresh_pass(
    deps: RunDeps, *, stale_after: timedelta = update_check.CHECK_STALE_AFTER
) -> RefreshPass:
    refresh = deps.refresh
    if refresh is None:
        raise ValueError("refresh is not wired")
    started = deps.now()
    cache = load_version_cache(refresh.cache_path)
    ordered = update_check.oldest_checked_first(deps.tools, cache, now=started)
    result = refresh.refresh(ordered, stale_after=stale_after, on_failure=None)
    states, entries, snapshot = result if result is not None else ({}, {}, None)
    return RefreshPass(states, entries, snapshot, started)


def _confirmed(
    deps: RunDeps,
    refresh_pass: RefreshPass,
    *,
    stale_after: timedelta = update_check.CHECK_STALE_AFTER,
) -> frozenset[str]:
    refresh = deps.refresh
    if refresh is None:
        raise ValueError("refresh is not wired")
    now = deps.now()

    def fresh(window: timedelta) -> frozenset[str]:
        return update_check.fresh_ids(
            deps.tools,
            refresh_pass.states.get,
            refresh.cache_path,
            started=now - window,
            now=now,
            pass_cache=refresh_pass.entries,
            pass_snapshot=refresh_pass.snapshot,
        )

    managers, others = fresh(MANAGER_STALE_AFTER), fresh(stale_after)
    result: set[str] = set()
    for tool_id, state in refresh_pass.states.items():
        if state.version is None:
            continue
        source = state.version.source
        if source not in MANAGER_SOURCES:
            if tool_id in others:
                result.add(tool_id)
            continue
        snapshot = refresh_pass.snapshot
        if tool_id not in managers or snapshot is None:
            continue
        failed = stamp_time(snapshot.failed_at, now=now)
        stamp = stamp_time(snapshot.manager_checked_at.get(source), now=now)
        if stamp is not None and (failed is None or failed <= stamp):
            result.add(tool_id)
    return frozenset(result)


def _refusal_evidence(
    tools: Sequence[Tool], states: Mapping[str, ToolState]
) -> dict[str, UpdateOutcome | None]:
    return {
        tool.id: update_refusal(tool, states[tool.id].ownership)
        for tool in tools
        if tool.id in states and states[tool.id].present
    }


def _update_all(deps: RunDeps) -> tuple[str, int]:
    if deps.refresh is None or deps.context is None:
        return "failed: update-all is not wired", 2
    ctx = deps.context
    try:
        first = _refresh_pass(deps)
    except (CommandError, OSError):
        return "failed: refresh failed", 1
    store = schedules.updated_today_path(ctx)
    entries, healthy = update_all_state.read_updated(store)
    clauses: list[str] = [] if healthy else ["updated-today record unreadable"]
    log = schedules.update_all_log_path(ctx)
    log_ok = True
    try:
        update_all_state.start_run_log(log)
    except OSError:
        log_ok = False
        clauses.append("run log not saved")
    updated = unchanged = skipped = 0
    failed: list[str] = []
    failed_managers: dict[str, str] = {}
    completed: set[str] = set()
    mutated_managers: set[str] = set()
    by_id = {tool.id: tool for tool in deps.tools}

    def today_map(day: date) -> dict[str, str]:
        return update_all_state.updated_on(entries, day)

    def run_entries(
        plan: Callable[[date], tuple[update_all.PlanEntry, ...]], states: Mapping[str, ToolState]
    ) -> None:
        nonlocal updated, unchanged, skipped, log_ok
        day = deps.now().date()
        queue = list(plan(day))
        processed: set[str] = set()
        while queue:
            current_day = deps.now().date()
            if day != current_day:
                day = current_day
                queue = [entry for entry in plan(day) if entry.tool_id not in processed]
                if not queue:
                    break
            entry = queue.pop(0)
            tool = by_id[entry.tool_id]
            processed.add(tool.id)
            manager = tool.id in update_all.MANAGER_IDS
            guard = _BatchGuard(
                tool,
                ctx.platform_os,
                failed_managers,
                completed,
                deps.tools,
                states[tool.id].ownership.owner,
            )
            if entry.action == "skip":
                run = ToolRun(f"skipped: {entry.reason}", 0, False)
                if manager:
                    owner = update_all.owner_manager(states[tool.id].ownership.owner)
                    root = update_all.blocking_manager(tool, owner, failed_managers, deps.tools)
                    if root is not None:
                        failed_managers[tool.id] = root
                    elif entry.reason not in (
                        update_all.SKIP_MANAGER_CYCLE,
                        update_all.SKIP_CYCLE_BLOCKED,
                    ) and (owner is None or owner == tool.id or owner in completed):
                        completed.add(tool.id)
            else:
                run = (
                    _update_cursor_agent(
                        schedules.schedule_by_id("update-cursor-agent"), deps, ctx, guard=guard
                    )
                    if tool.id == "cursor-agent"
                    else _update_tool(tool, deps, guard=guard)
                )
                if manager:
                    if run.line.startswith("failed:"):
                        failed_managers[tool.id] = tool.id
                    elif guard.root is not None:
                        failed_managers[tool.id] = guard.root
                    elif not guard.refused:
                        completed.add(tool.id)
                    if run.mutated:
                        mutated_managers.add(tool.id)
            if run.line.startswith("failed:"):
                failed.append(tool.id)
            elif run.line.startswith("skipped:"):
                skipped += 1
            elif run.line.startswith("ok: up to date"):
                unchanged += 1
            else:
                updated += 1
            if run.mutated:
                record_day = deps.now().date()
                entries[tool.id] = update_all_state.UpdatedEntry(record_day, "update-all")
                try:
                    update_all_state.record_updated(
                        store, tool.id, today=record_day, by="update-all"
                    )
                except OSError:
                    if "updated-today record not saved" not in clauses:
                        clauses.append("updated-today record not saved")
            if log_ok:
                try:
                    update_all_state.append_run_log(
                        log, update_all_state.log_line(deps.now(), tool.id, run.line)
                    )
                except OSError:
                    log_ok = False
                    clauses.append("run log not saved")

    refusals = _refusal_evidence(deps.tools, first.states)
    run_entries(
        lambda day: update_all.plan_managers(
            deps.tools,
            first.states,
            platform_os=ctx.platform_os,
            updated_today=today_map(day),
            refusals=refusals,
        ),
        first.states,
    )
    try:
        chosen = _refresh_pass(deps)
        confirmed = _confirmed(deps, chosen)
    except (CommandError, OSError):
        chosen = first
        confirmed = frozenset(
            tool_id
            for tool_id in _confirmed(deps, first)
            if (version := first.states[tool_id].version) is None
            or MANAGER_OF_SOURCE.get(version.source) not in mutated_managers
        )
        clauses.append("second refresh failed; dependents judged on the first pass")
    refusals = _refusal_evidence(deps.tools, chosen.states)
    run_entries(
        lambda day: update_all.plan_dependents(
            deps.tools,
            chosen.states,
            outdated_ids(chosen.states.values()),
            confirmed=confirmed,
            platform_os=ctx.platform_os,
            updated_today=today_map(day),
            refusals=refusals,
        ),
        chosen.states,
    )
    return update_all.summary_line(
        updated=updated,
        skipped=skipped,
        unchanged=unchanged,
        failed=len(failed),
        first_failed=failed[0] if failed else "",
        clauses=clauses,
    ), int(bool(failed))


def _run_update_row(schedule: schedules.Schedule, deps: RunDeps) -> tuple[str, int]:
    context = deps.context
    healthy = True
    path = schedules.updated_today_path(context) if context is not None else None
    if path is not None:
        entries, healthy = update_all_state.read_updated(path)
        if (
            update_all_state.updated_on(entries, deps.now().date()).get(schedule.target or "")
            == "update-all"
        ):
            return "skipped: updated today", 0
    run = (
        _update_cursor_agent(schedule, deps, context)
        if schedule.target == "cursor-agent" and context is not None
        else _update(schedule, deps)
    )
    clauses = [] if healthy else ["updated-today record unreadable"]
    if path is not None and run.mutated:
        try:
            update_all_state.record_updated(
                path, schedule.target or "", today=deps.now().date(), by=schedule.id
            )
        except OSError:
            clauses.append("updated-today record not saved")
    return run.line + "".join(f"; {clause}" for clause in clauses), run.code


def _run_unlocked(schedule: schedules.Schedule, deps: RunDeps) -> tuple[str, int]:
    if schedule.kind is schedules.JobKind.UPDATE_ALL:
        return _update_all(deps)
    if schedule.kind is schedules.JobKind.CHECK_UPDATES:
        return _check(deps)
    return _run_update_row(schedule, deps)


def run_schedule(
    schedule_id: str, deps: RunDeps, *, parent_holds_lock: bool, lock_holder_pid: int | None = None
) -> tuple[str, int]:
    """Run one update or check schedule and return its result line and exit code.

    The schedule runner that spawned a timer's run already holds the run lock
    (`parent_holds_lock`); a manual run takes it itself and skips when it is held (D-12).
    """
    schedule = schedules.schedule_by_id(schedule_id)
    if schedule.kind not in (
        schedules.JobKind.UPDATE,
        schedules.JobKind.CHECK_UPDATES,
        schedules.JobKind.UPDATE_ALL,
    ):
        return f"failed: {schedule_id} is not an update schedule", 2
    if schedule.kind is schedules.JobKind.UPDATE_ALL and deps.euid() == 0:
        return "failed: update-all refuses to run as root", 1
    lock_path = deps.context.lock_path if deps.context is not None else runlock.run_lock_path()
    if parent_holds_lock:
        if schedule.kind is schedules.JobKind.UPDATE_ALL and not runlock.held_by(
            lock_path, schedule_id, lock_holder_pid
        ):
            return "failed: update-all refuses an unverified parent run lock", 1
        return _run_unlocked(schedule, deps)
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
