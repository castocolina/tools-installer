"""Offline fixtures for update-all planning."""

import os
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from installer import runlock, schedules
from installer.model import Method, Tool
from installer.notify import Notifier
from installer.ownership import Confidence, ManagerOwnership, Owner
from installer.platform import Platform
from installer.schedule_run import RunDeps, run_schedule
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.update_check import Refresher
from installer.version_cache import ManagerSnapshot, VersionCacheEntry
from installer.version_status import FailureSink, ToolState, VersionStatus
from tests.state_doubles import pass_state
from tests.update_check_doubles import FakeNotifier

FEDORA = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def catalog_tool(
    tool_id: str, *, requires: tuple[str, ...] = (), update: bool = True, kind: str = "script"
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind=kind, params={"update": [tool_id, "update"]} if update else {}),),
        requires=requires,
    )


def owned(
    tool: Tool,
    owner: Owner,
    *,
    package: str | None = None,
    confidence: Confidence = "direct",
    method: Method | None = None,
) -> ManagerOwnership:
    return ManagerOwnership(
        tool_id=tool.id,
        owner=owner,
        method=method
        if method is not None
        else (tool.methods[0] if owner == "installer" else None),
        package=package,
        current_version=None,
        confidence=confidence,
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )


def state(
    tool: Tool,
    owner: Owner,
    *,
    outdated: bool = False,
    present: bool = True,
    platform: Platform = FEDORA,
    package: str | None = None,
    method: Method | None = None,
) -> ToolState:
    return pass_state(
        tool,
        platform=platform,
        present=present,
        ownership=owned(tool, owner, package=package, method=method),
        version=VersionStatus(
            tool.id, "1.0", "2.0" if outdated else "1.0", outdated, False, "github"
        ),
    )


def states_of(*states: ToolState) -> dict[str, ToolState]:
    return {item.tool_id: item for item in states}


def no_refusals(tools: Iterable[Tool]) -> dict[str, UpdateOutcome | None]:
    return {tool.id: None for tool in tools}


def confirmed_all(states: Iterable[ToolState]) -> frozenset[str]:
    return frozenset(item.tool_id for item in states)


class SequenceRefresher:
    def __init__(
        self,
        cache_path: Path,
        passes: Sequence[Mapping[str, ToolState]],
        *,
        clock: Callable[[], datetime],
        ages: Sequence[Mapping[str, timedelta]] | None = None,
        snapshots: Sequence[ManagerSnapshot | None] | None = None,
        raises_on: frozenset[int] = frozenset(),
        on_call: Callable[[int], None] | None = None,
    ) -> None:
        self.cache_path = cache_path
        self.passes = passes
        self.clock = clock
        self.ages = ages
        self.snapshots = snapshots
        self.raises_on = raises_on
        self.on_call = on_call
        self.warning: str | None = None
        self.calls: list[tuple[tuple[str, ...], timedelta]] = []

    def refresh(
        self, tools: Sequence[Tool], *, stale_after: timedelta, on_failure: FailureSink | None
    ) -> tuple[dict[str, ToolState], dict[str, VersionCacheEntry], ManagerSnapshot | None]:
        del on_failure
        i = len(self.calls)
        self.calls.append((tuple(tool.id for tool in tools), stale_after))
        if self.on_call is not None:
            self.on_call(i)
        if i in self.raises_on:
            raise OSError("boom")
        states = dict(self.passes[min(i, len(self.passes) - 1)])
        ages = (
            self.ages[min(i, len(self.ages) - 1)]
            if self.ages is not None
            else dict.fromkeys(states, timedelta())
        )
        entries = {
            key: VersionCacheEntry("2", (self.clock() - age).isoformat())
            for key, age in ages.items()
        }
        snapshot = (
            self.snapshots[min(i, len(self.snapshots) - 1)] if self.snapshots is not None else None
        )
        return states, entries, snapshot

    def state_of(self, tool_id: str) -> ToolState | None:
        return self.passes[min(max(len(self.calls) - 1, 0), len(self.passes) - 1)].get(tool_id)


@contextmanager
def held_by_parent(context: schedules.ScheduleContext) -> Generator[int]:
    lock = runlock.try_acquire(context.lock_path, "update-all")
    assert lock is not None
    try:
        yield os.getpid()
    finally:
        lock.release()


def run_update_all(deps: RunDeps) -> tuple[str, int]:
    assert deps.context is not None
    with held_by_parent(deps.context) as pid:
        return run_schedule("update-all", deps, parent_holds_lock=True, lock_holder_pid=pid)


class SpyService(UpdateService):
    def __init__(self, outcomes: Mapping[str, UpdateOutcome] | None = None) -> None:
        def refuse(_tool: Tool) -> ManagerOwnership:
            raise AssertionError("unexpected ownership lookup")

        super().__init__(
            platform=FEDORA,
            managed_packages=lambda: (),
            replay_globals=lambda _packages: (),
            reresolve_ownership=refuse,
        )
        self.outcomes = dict(outcomes or {})
        self.runs: list[str] = []
        self.fresh: dict[str, ManagerOwnership] = {}

    def run_guarded(
        self, target: UpdateTarget, guard: Callable[[ManagerOwnership], UpdateOutcome | None]
    ) -> UpdateOutcome:
        refusal = guard(self.fresh.get(target.tool.id, target.ownership))
        return refusal if refusal is not None else self.run(target)

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        self.runs.append(target.tool.id)
        return self.outcomes.get(
            target.tool.id,
            UpdateOutcome(
                tool_id=target.tool.id, status="updated", owner=target.ownership.owner, mutated=True
            ),
        )


class ScriptedProbe:
    def __init__(self, values: Mapping[str, Sequence[str | None | Exception]]) -> None:
        self.values = {key: list(value) for key, value in values.items()}

    def __call__(self, tool: Tool, _ownership: ManagerOwnership) -> str | None:
        pending = self.values.get(tool.id, [])
        value = pending.pop(0) if pending else None
        if isinstance(value, Exception):
            raise value
        return value


def run_deps(
    tools: Sequence[Tool],
    context: schedules.ScheduleContext | None,
    *,
    service: UpdateService,
    owners: Mapping[str, ManagerOwnership],
    probe: Callable[[Tool, ManagerOwnership], str | None] | None = None,
    now: Callable[[], datetime] | None = None,
    notify: Notifier | None = None,
    refresh: Refresher | None = None,
    euid: Callable[[], int] | None = None,
) -> RunDeps:
    from datetime import datetime as clock

    return RunDeps(
        tools,
        service,
        lambda tool: owners[tool.id],
        probe or ScriptedProbe({}),
        context,
        notify or FakeNotifier(),
        refresh,
        now=now or (lambda: clock.now().astimezone()),
        euid=euid or (lambda: 1000),
    )
