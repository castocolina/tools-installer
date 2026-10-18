"""Pure dependency resolution: transitive drag-in + deps-first topological order.
`Resolution.closure` is the deps-first row order of the install plan (Phase 20).

Mirrors uzkit's engine (with_required / order_for_install) but adds two things
the PRD requires: a cycle is REPORTED (DependencyCycleError), not silently
broken; and a dependency that is unavailable on this platform (and not already
installed) is dropped with a warning, skipping every tool that transitively
needs it. Availability and install-state are injected so the module stays pure
and terminal-free.
"""

from collections import deque
from collections.abc import Callable, Container, Mapping
from dataclasses import dataclass

from installer.model import Tool


class DependencyCycleError(ValueError):
    """A `requires` cycle was found — a registry/config error, never a hang."""


@dataclass(frozen=True)
class Blocked:
    """A blocked tool and its first unsatisfied dependency, if any."""

    tool_id: str
    needs: str | None


@dataclass(frozen=True)
class Resolution:
    """Dependency closure, unavailable rows, and each dragged tool's requester."""

    closure: tuple[Tool, ...]
    blocked: tuple[Blocked, ...]
    requested_by: Mapping[str, str]


def resolve_dependencies(
    selected: list[Tool],
    catalog: list[Tool],
    *,
    available: Callable[[Tool], bool],
    is_installed: Callable[[Tool], bool],
) -> Resolution:
    """Expand `selected` with its transitive `requires`, order deps-first, and
    drop branches blocked by an unavailable dependency.

    `selected` is consumed in its given order; pass it pre-sorted (e.g. by
    priority) and independents keep that order — a dependency is only ever moved
    earlier than a tool that needs it.

    Returns the full deps-first closure, including installed tools, plus blocked
    rows and the first selected requester for every dragged dependency.
    """
    by_id = {t.id: t for t in catalog}
    selected_ids = {t.id for t in selected}

    # 1. Transitive closure over requires, preserving first-seen order.
    #    We walk every dependency, including installed tools, for the full plan.
    wanted: list[Tool] = []
    seen: set[str] = set()
    requested_by: dict[str, str] = {}

    def collect(tool: Tool, root: Tool) -> None:
        if tool.id in seen:
            return
        seen.add(tool.id)
        wanted.append(tool)
        for dep_id in tool.requires:
            dep = by_id.get(dep_id)
            if dep is None:
                continue
            if dep.id not in selected_ids:
                requested_by.setdefault(dep.id, root.id)
            collect(dep, root)

    for tool in selected:
        collect(tool, tool)

    # 2. Identify blocked tools: a dep that is unavailable here AND not installed
    #    cannot be provided; it and every (transitive) dependent are skipped.
    #    We use an explicit visited set to avoid infinite recursion on cycles
    #    (cycles are reported in Step 3, not here).
    blocked: set[str] = set()
    blocked_needs: dict[str, str | None] = {}
    visiting_block: set[str] = set()

    def is_blocked(tool: Tool) -> bool:
        if tool.id in blocked:
            return True
        # Already-installed tools are always satisfiable, regardless of availability.
        if is_installed(tool):
            return False
        # Guard against cycles — they won't be counted as blocked here; the
        # cycle-detection DFS in Step 3 raises DependencyCycleError instead.
        if tool.id in visiting_block:
            return False
        visiting_block.add(tool.id)
        unsatisfiable = not available(tool)
        needs = next(
            (
                dep_id
                for dep_id in tool.requires
                if (dep := by_id.get(dep_id)) is not None and is_blocked(dep)
            ),
            None,
        )
        visiting_block.discard(tool.id)
        if unsatisfiable or needs is not None:
            blocked.add(tool.id)
            blocked_needs[tool.id] = None if unsatisfiable else needs
            return True
        return False

    blocked_rows: list[Blocked] = []
    for tool in wanted:
        # Runs once per `wanted` entry, so each blocked tool yields exactly one row.
        if is_blocked(tool):
            blocked_rows.append(Blocked(tool.id, blocked_needs.get(tool.id)))

    # 3. One deps-first topological sort over every non-blocked tool, including
    #    installed tools. It detects every cycle in the reachable closure.
    def topo(members: list[Tool]) -> list[Tool]:
        ordered: list[Tool] = []
        placed: set[str] = set()
        visiting: set[str] = set()
        member_ids = {t.id for t in members}

        def _place(tool: Tool) -> None:
            if tool.id in placed:
                return
            if tool.id in visiting:
                raise DependencyCycleError(f"dependency cycle involving '{tool.id}'")
            visiting.add(tool.id)
            for dep_id in tool.requires:
                if dep_id in member_ids:
                    _place(by_id[dep_id])
            visiting.discard(tool.id)
            placed.add(tool.id)
            ordered.append(tool)

        for tool in members:
            _place(tool)
        return ordered

    closure = topo([t for t in wanted if t.id not in blocked])
    return Resolution(
        closure=tuple(closure),
        blocked=tuple(blocked_rows),
        requested_by=requested_by,
    )


def requires_integrity_errors(catalog: list[Tool]) -> list[str]:
    """Every `requires` id must resolve to a real catalog tool. Returns a list of
    human-readable errors (empty = clean). Used by a registry-integrity test so a
    typo'd dependency id fails CI instead of shipping a broken install."""
    ids = {t.id for t in catalog}
    errors: list[str] = []
    for tool in catalog:
        for dep_id in tool.requires:
            if dep_id not in ids:
                errors.append(f"tool '{tool.id}' requires unknown tool '{dep_id}'")
    return errors


def missing_requires(
    tool: Tool,
    catalog: list[Tool],
    *,
    staged: Container[str],
    installed: Mapping[str, bool],
) -> tuple[str, ...]:
    """Name what `resolve_dependencies` will drag in, so a tier-scoped view can
    show a cross-tier dependency at mark time.

    This is a read-only preview: it performs no ordering, makes no availability
    judgement, raises no cycle error, and drags nothing in.
    `resolve_dependencies` remains the single mechanism that decides what
    installs and in what order, per `.claude/architecture.md`'s tier rule.
    """
    by_id = {entry.id: entry for entry in catalog}
    seen: set[str] = {tool.id}
    missing: list[str] = []
    queue: deque[str] = deque(tool.requires)
    while queue:
        dep_id = queue.popleft()
        if dep_id in seen:
            continue
        seen.add(dep_id)
        dep = by_id.get(dep_id)
        if dep is None:
            continue
        if dep_id not in staged and not installed.get(dep_id, False):
            missing.append(dep_id)
        queue.extend(dep.requires)
    return tuple(missing)
