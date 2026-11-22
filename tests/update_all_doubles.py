"""Offline fixtures for update-all planning."""

from collections.abc import Iterable

from installer.model import Method, Tool
from installer.ownership import Confidence, ManagerOwnership, Owner
from installer.platform import Platform
from installer.update import UpdateOutcome
from installer.version_status import ToolState, VersionStatus
from tests.state_doubles import pass_state

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
