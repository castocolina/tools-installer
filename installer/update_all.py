"""Update-all planning and result formatting, without starting processes."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, cast

from installer import schedules
from installer.deps import DependencyCycleError, resolve_dependencies

if TYPE_CHECKING:
    from installer.model import Tool
    from installer.ownership import ManagerOwnership
    from installer.update import UpdateOutcome
    from installer.version_status import ToolState

# Each command is bounded like the stdlib runner's manager bound (D-11).
COMMAND_TIMEOUT: Final = 1200
KILL_GRACE: Final = 3
CLEANUP_BUDGET: Final = 4 * KILL_GRACE

RESULT_LIMIT = 300
FIRST_FAILED_LIMIT = 40
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def plain_line(text: str, limit: int = RESULT_LIMIT) -> str:
    """Remove terminal escapes and controls, then bound the resulting single line."""
    return " ".join(_CONTROLS.sub("", _ANSI.sub("", text)).split())[:limit]


def summary_line(
    *,
    updated: int,
    skipped: int,
    unchanged: int = 0,
    failed: int = 0,
    first_failed: str = "",
    clauses: Sequence[str] = (),
) -> str:
    """Format one bounded result, preserving the counts and trimming only clauses."""
    if failed:
        name = plain_line(first_failed, FIRST_FAILED_LIMIT)
        line = f"failed: {failed} failed ({name}), {updated} updated, {skipped} skipped"
    elif updated or skipped or unchanged:
        line = f"ok: {updated} updated, {skipped} skipped"
    else:
        line = "ok: 0 updated"
    if unchanged:
        line += f"; {unchanged} unchanged"
    for clause in clauses:
        value = plain_line(clause)
        room = RESULT_LIMIT - len(line) - 2
        if room <= 0:
            break
        value = value[:room].rstrip()
        if value:
            line += f"; {value}"
    return line


# Managers are catalog tools named by an Owner value, not a registry category.
MANAGER_IDS: Final[tuple[str, ...]] = ("brew", "uv", "bun", "pnpm", "sdkman", "volta")
GROUP_MANAGERS = "managers"
GROUP_INSTALLER = "installer"
SKIP_MANAGER_CYCLE = "manager ownership cycle"
SKIP_CYCLE_BLOCKED = "owner is in a manager ownership cycle"
SKIP_DEPENDENCY_CYCLE = "dependency cycle"
SKIP_CASK = "cask excluded"
SKIP_NO_UPDATE_PATH = "no unattended update path"
SKIP_UPDATED_TODAY = "updated today"
SKIP_UNCONFIRMED = "latest version not confirmed"
SKIP_NOT_EVALUATED = "refusal not evaluated"
PLAN_NOTE = (
    "note: a real run refreshes data older than 20 hours, judges dependents again after "
    "the managers update and checks installed files again before it updates a tool"
)


@dataclass(frozen=True)
class PlanEntry:
    """One deterministic plan row."""

    tool_id: str
    group: str
    action: Literal["update", "skip"]
    reason: str
    owner_manager: str | None


def owner_manager(owner: str) -> str | None:
    """Map an ownership label to its catalog manager, if any."""
    if owner == "cask":
        return "brew"
    return owner if owner in MANAGER_IDS else None


def _manager_order(
    tools: Sequence[Tool], states: Mapping[str, ToolState | None]
) -> tuple[list[str], set[str], set[str]]:
    present = {
        tool.id
        for tool in tools
        if tool.id in MANAGER_IDS and (state := states.get(tool.id)) is not None and state.present
    }
    edges: dict[str, str] = {}
    for tool_id in present:
        state = states[tool_id]
        if state is None:
            continue
        ownership = cast("ManagerOwnership | None", state.ownership)
        owner = owner_manager(ownership.owner) if ownership is not None else None
        if owner is not None and owner in present and owner != tool_id:
            edges[tool_id] = owner
    cyclic: set[str] = set()
    for tool_id in sorted(present):
        path: list[str] = []
        current = tool_id
        while current not in path and current in edges:
            path.append(current)
            current = edges[current]
        if current in path:
            cyclic.update(path[path.index(current) :])
    depths: dict[str, int] = dict.fromkeys(cyclic, 0)
    blocked: set[str] = set()

    def depth(tool_id: str) -> int:
        if tool_id not in depths:
            owner = edges.get(tool_id)
            depths[tool_id] = 0 if owner is None else depth(owner) + 1
            if owner in cyclic or owner in blocked:
                blocked.add(tool_id)
        return depths[tool_id]

    return sorted(present, key=lambda item: (depth(item), item)), cyclic, blocked


def exclusion(
    platform_os: str, ownership: ManagerOwnership, refusal: UpdateOutcome | None
) -> str | None:
    """Apply batch exclusions in cask, refusal, unattended-path order."""
    if platform_os == "macos" and ownership.owner == "cask":
        return SKIP_CASK
    if refusal is not None:
        return schedules.update_result_line(refusal, None, None)[0].removeprefix("skipped: ")
    method = ownership.method
    if (
        ownership.owner == "installer"
        and method is not None
        and method.kind == "script"
        and not isinstance(method.params.get("update"), list)
    ):
        return SKIP_NO_UPDATE_PATH
    return None


def blocking_manager(
    tool: Tool, owner_manager: str | None, failed: Mapping[str, str], catalog: Sequence[Tool]
) -> str | None:
    """Find the first failed owner or dependency; skipped managers are not keys in failed."""
    if owner_manager is not None and owner_manager in failed:
        return failed[owner_manager]
    by_id = {item.id: item for item in catalog}
    visited = {tool.id}

    def walk(item: Tool) -> str | None:
        for dependency in item.requires:
            if dependency in visited:
                continue
            visited.add(dependency)
            if dependency in failed:
                return failed[dependency]
            child = by_id.get(dependency)
            if child is not None:
                result = walk(child)
                if result is not None:
                    return result
        return None

    return walk(tool)


def _decide(
    tool: Tool,
    state: ToolState,
    *,
    platform_os: str,
    updated_today: Collection[str],
    refusals: Mapping[str, UpdateOutcome | None],
    confirmed: Collection[str] | None,
) -> tuple[Literal["update", "skip"], str]:
    """Check ownership, exclusion, today's updates, then confirmation in that order."""
    ownership = cast("ManagerOwnership | None", state.ownership)
    if ownership is None:
        return "skip", SKIP_NOT_EVALUATED
    if tool.id not in refusals:
        reason = exclusion(platform_os, ownership, None)
        return "skip", SKIP_CASK if reason == SKIP_CASK else SKIP_NOT_EVALUATED
    reason = exclusion(platform_os, ownership, refusals[tool.id])
    if reason is not None:
        return "skip", reason
    if tool.id in updated_today:
        return "skip", SKIP_UPDATED_TODAY
    if confirmed is not None and tool.id not in confirmed:
        return "skip", SKIP_UNCONFIRMED
    return "update", ""


def plan_managers(
    tools: Sequence[Tool],
    states: Mapping[str, ToolState | None],
    *,
    platform_os: str,
    updated_today: Collection[str],
    refusals: Mapping[str, UpdateOutcome | None],
) -> tuple[PlanEntry, ...]:
    """Plan present managers in ownership order, skipping ownership cycles."""
    order, cyclic, blocked = _manager_order(tools, states)
    by_id = {tool.id: tool for tool in tools}
    entries: list[PlanEntry] = []
    for tool_id in order:
        state = states[tool_id]
        if state is None:
            continue
        if tool_id in cyclic:
            action, reason = "skip", SKIP_MANAGER_CYCLE
        elif tool_id in blocked:
            action, reason = "skip", SKIP_CYCLE_BLOCKED
        else:
            action, reason = _decide(
                by_id[tool_id],
                state,
                platform_os=platform_os,
                updated_today=updated_today,
                refusals=refusals,
                confirmed=None,
            )
        ownership = cast("ManagerOwnership | None", state.ownership)
        entries.append(
            PlanEntry(
                tool_id,
                GROUP_MANAGERS,
                action,
                reason,
                owner_manager(ownership.owner) if ownership is not None else None,
            )
        )
    return tuple(entries)


def plan_dependents(
    tools: Sequence[Tool],
    states: Mapping[str, ToolState | None],
    outdated: Collection[str],
    *,
    confirmed: Collection[str],
    platform_os: str,
    updated_today: Collection[str],
    refusals: Mapping[str, UpdateOutcome | None],
) -> tuple[PlanEntry, ...]:
    """Plan outdated dependents by owner and dependency order."""
    order, _, _ = _manager_order(tools, states)
    groups: dict[str | None, list[Tool]] = {}
    for tool in tools:
        state = states.get(tool.id)
        if (
            tool.id not in MANAGER_IDS
            and tool.id in outdated
            and state is not None
            and state.present
        ):
            ownership = cast("ManagerOwnership | None", state.ownership)
            owner = owner_manager(ownership.owner) if ownership is not None else None
            groups.setdefault(owner, []).append(tool)
    other_managers = sorted(group for group in groups if group is not None and group not in order)
    entries: list[PlanEntry] = []
    for group in [*order, *other_managers, None]:
        members = sorted(groups.get(group, ()), key=lambda tool: tool.id)
        if not members:
            continue
        member_ids = {tool.id for tool in members}
        try:
            result = resolve_dependencies(
                members, list(tools), available=lambda _tool: True, is_installed=lambda _tool: True
            )
            ordered = [tool for tool in result.closure if tool.id in member_ids]
            cycle = False
        except DependencyCycleError:
            ordered = members
            cycle = True
        for tool in ordered:
            state = states[tool.id]
            if state is None:
                continue
            ownership = cast("ManagerOwnership | None", state.ownership)
            label = (
                group
                if group is not None
                else (ownership.owner if ownership is not None else "unknown")
            )
            if cycle:
                action, reason = "skip", SKIP_DEPENDENCY_CYCLE
            else:
                action, reason = _decide(
                    tool,
                    state,
                    platform_os=platform_os,
                    updated_today=updated_today,
                    refusals=refusals,
                    confirmed=confirmed,
                )
            entries.append(PlanEntry(tool.id, label, action, reason, group))
    return tuple(entries)


def plan_line(entry: PlanEntry) -> str:
    """Render one preview row."""
    if entry.action == "skip":
        return f"{entry.tool_id}: skipped: {entry.reason}"
    return f"{entry.tool_id} ({entry.group}): would update"


def plan_summary(update: int, skipped: int) -> str:
    """Render preview counts."""
    return f"ok: plan {update} to update, {skipped} skipped"
