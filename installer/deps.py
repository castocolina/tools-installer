"""Pure dependency resolution: transitive drag-in + deps-first topological order.

Mirrors uzkit's engine (with_required / order_for_install) but adds two things
the PRD requires: a cycle is REPORTED (DependencyCycleError), not silently
broken; and a dependency that is unavailable on this platform (and not already
installed) is dropped with a warning, skipping every tool that transitively
needs it. Availability and install-state are injected so the module stays pure
and terminal-free.
"""

from collections.abc import Callable
from dataclasses import dataclass

from installer.model import Tool


class DependencyCycleError(ValueError):
    """A `requires` cycle was found — a registry/config error, never a hang."""


@dataclass(frozen=True)
class Resolution:
    """order: deps-first install order. dragged_in: ids auto-added (not selected).
    warnings: human-readable notices (drag-ins, and skipped unavailable deps)."""

    order: tuple[Tool, ...]
    dragged_in: tuple[str, ...]
    warnings: tuple[str, ...]


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

    Already-installed tools are satisfied as-is: they are excluded from the
    returned order (nothing to do) and are not counted in dragged_in.
    """
    by_id = {t.id: t for t in catalog}
    selected_ids = {t.id for t in selected}

    # 1. Transitive closure over requires, preserving first-seen order.
    #    We walk every dep; already-installed ones are included so we can check
    #    their availability status, but they are filtered from the final order.
    wanted: list[Tool] = []
    seen: set[str] = set()
    warnings: list[str] = []

    def collect(tool: Tool) -> None:
        if tool.id in seen:
            return
        seen.add(tool.id)
        wanted.append(tool)
        for dep_id in tool.requires:
            dep = by_id.get(dep_id)
            if dep is None:
                warnings.append(f"{tool.id} requires unknown tool '{dep_id}' — ignored")
                continue
            collect(dep)

    for tool in selected:
        collect(tool)

    # 2. Identify blocked tools: a dep that is unavailable here AND not installed
    #    cannot be provided; it and every (transitive) dependent are skipped.
    #    We use an explicit visited set to avoid infinite recursion on cycles
    #    (cycles are reported in Step 3, not here).
    blocked: set[str] = set()
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
        dep_blocked = any(
            (dep := by_id.get(dep_id)) is not None and is_blocked(dep) for dep_id in tool.requires
        )
        visiting_block.discard(tool.id)
        if unsatisfiable or dep_blocked:
            blocked.add(tool.id)
            return True
        return False

    for tool in wanted:
        if is_blocked(tool):
            if not available(tool) and not is_installed(tool):
                warnings.append(f"{tool.id} is not available on this platform — skipped")
            else:
                warnings.append(f"{tool.id} skipped — a dependency is unavailable")

    # Tools that need no installation action: already installed AND not blocked.
    # These satisfy dependency edges but are excluded from the output order.
    satisfied_by_install = {t.id for t in wanted if is_installed(t) and t.id not in blocked}

    runnable = [t for t in wanted if t.id not in blocked and t.id not in satisfied_by_install]

    # 3. Deps-first topological sort over `runnable`, cycle-detecting.
    ordered: list[Tool] = []
    placed: set[str] = set()
    visiting: set[str] = set()
    runnable_ids = {t.id for t in runnable}

    def visit(tool: Tool) -> None:
        if tool.id in placed:
            return
        if tool.id in visiting:
            raise DependencyCycleError(f"dependency cycle involving '{tool.id}'")
        visiting.add(tool.id)
        for dep_id in tool.requires:
            if dep_id in runnable_ids:
                visit(by_id[dep_id])
        visiting.discard(tool.id)
        placed.add(tool.id)
        ordered.append(tool)

    for tool in runnable:
        visit(tool)

    dragged_in = tuple(t.id for t in ordered if t.id not in selected_ids)
    return Resolution(order=tuple(ordered), dragged_in=dragged_in, warnings=tuple(warnings))
