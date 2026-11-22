"""Offline fixtures for update-all planning."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime

from installer import schedules
from installer.model import Method, Tool
from installer.notify import Notifier
from installer.ownership import Confidence, ManagerOwnership, Owner
from installer.platform import Platform
from installer.schedule_run import RunDeps
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.update_check import Refresher
from installer.version_status import ToolState, VersionStatus
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
    )
