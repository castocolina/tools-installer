"""Generic environment-policy model, parallel to Tool.

A Policy bundles its identity (id/label/description), a snapshot of whether it is
currently active, and two idempotent closures — apply and remove — that each
return a structured per-layer PolicyResult. The pure layer owns the composition
of installer.guards; the IO boundary (setup.py) binds the real shim dir and rc
paths. The pip/npm ban is the first and only instance; future env tweaks slot in
with no screen changes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from installer.guards import (
    guard_path_warning,
    guard_status,
    install_shims,
    remove_ban_aliases,
    remove_shims,
    write_ban_aliases,
)

_RELOAD_HINT = "Open a new shell or run `hash -r` so cached command paths refresh."


def _display_path(path: Path) -> str:
    """Collapse a HOME-relative path to ~/… so feedback reads as a shell path
    rather than a long absolute (or pytest temp) dump; leave others verbatim."""
    home = Path.home()
    return f"~/{path.relative_to(home)}" if path.is_relative_to(home) else str(path)


@dataclass(frozen=True)
class PolicyLayer:
    """One independently-reported layer of a policy (e.g. shims vs aliases)."""

    name: str
    detail: str


@dataclass(frozen=True)
class PolicyResult:
    """The outcome of an apply/remove: per-layer details plus guidance."""

    layers: tuple[PolicyLayer, ...]
    reload_hint: str | None
    warning: str | None


@dataclass(frozen=True)
class Policy:
    """A toggleable environment policy with idempotent apply/remove closures."""

    id: str
    label: str
    description: str
    active: bool
    apply: Callable[[], PolicyResult]
    remove: Callable[[], PolicyResult]


def ban_policy(
    *,
    shim_dir: Path,
    apply_rc_paths: list[Path],
    remove_rc_paths: list[Path],
    path_value: str,
    which: Callable[[str], str | None],
) -> Policy:
    """The pip/npm ban as a Policy, composing installer.guards.

    apply writes shims into shim_dir and aliases into apply_rc_paths; remove
    clears shims and strips aliases from remove_rc_paths (the union of every
    location, so disabling leaves no stragglers regardless of link mode).
    """

    def _apply() -> PolicyResult:
        shim_results = install_shims(shim_dir)
        active = sum(1 for state in shim_results.values() if state in ("created", "refreshed"))
        skipped = sum(1 for state in shim_results.values() if state.startswith("skipped"))
        shim_detail = f"{active} active in {_display_path(shim_dir)}"
        if skipped:
            shim_detail += f" ({skipped} skipped — real binary present)"
        for rc_path in apply_rc_paths:
            write_ban_aliases(rc_path)
        alias_detail = "written to " + ", ".join(_display_path(p) for p in apply_rc_paths)
        return PolicyResult(
            layers=(PolicyLayer("Shims", shim_detail), PolicyLayer("Aliases", alias_detail)),
            reload_hint=_RELOAD_HINT,
            warning=guard_path_warning(shim_dir, path_value, which),
        )

    def _remove() -> PolicyResult:
        shim_results = remove_shims(shim_dir)
        removed = sum(1 for state in shim_results.values() if state == "removed")
        shim_detail = f"{removed} removed from {_display_path(shim_dir)}"
        for rc_path in remove_rc_paths:
            remove_ban_aliases(rc_path)
        alias_detail = "cleared from " + ", ".join(_display_path(p) for p in remove_rc_paths)
        return PolicyResult(
            layers=(PolicyLayer("Shims", shim_detail), PolicyLayer("Aliases", alias_detail)),
            reload_hint=_RELOAD_HINT,
            warning=None,
        )

    return Policy(
        id="ban",
        label="pip/npm ban",
        description="blocks bare pip/npm so installs go through uv/pnpm (shims + aliases)",
        active=any(guard_status(shim_dir).values()),
        apply=_apply,
        remove=_remove,
    )
