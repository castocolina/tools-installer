"""Generic environment-policy model, parallel to Tool.

A Policy bundles its identity (id/label/description), a snapshot of whether it is
currently active, and two idempotent closures — apply and remove — that each
return a structured per-layer PolicyResult. The pure layer owns the composition
of installer.guards; the IO boundary (setup.py) binds the real shim dir and rc
paths. The pip/npm ban is the first and only instance; future env tweaks slot in
with no screen changes.
"""

from collections.abc import Callable, Mapping
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
from installer.tweaks import (
    TweakBundle,
    install_tweak_executables,
    remove_tweak,
    remove_tweak_executables,
    tweak_present,
    write_tweak,
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
    requires: tuple[str, ...] = ()
    missing_requires: tuple[str, ...] = ()


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


def _required_bin_dir(bundle: TweakBundle, bin_dir: Path | None) -> Path | None:
    if bundle.executables and bin_dir is None:
        raise ValueError(f"bundle '{bundle.id}' requires a managed bin_dir")
    return bin_dir


def tweak_policy(
    bundle: TweakBundle,
    *,
    rc_path: Path,
    bin_dir: Path | None = None,
    installed_tools: Mapping[str, bool] | None = None,
) -> Policy:
    """A curated shell-tweak bundle as a Policy, parallel to ban_policy.

    apply writes the bundle's marker block into rc_path; remove strips it. `active`
    is "the bundle's block is present in rc_path". Idempotent (reuses tweaks'
    block machinery). The id is namespaced `tweak:<id>` so it never collides with
    the ban or another bundle in the Policies tab.
    """

    def _apply() -> PolicyResult:
        target_bin_dir = _required_bin_dir(bundle, bin_dir)
        written = (
            install_tweak_executables(bundle, target_bin_dir) if target_bin_dir is not None else ()
        )
        write_tweak(bundle, rc_path, bin_dir=target_bin_dir)
        layers = [PolicyLayer(bundle.label, f"written to {_display_path(rc_path)}")]
        if target_bin_dir is not None and bundle.executables:
            names = ", ".join(path.name for path in written) or "0 managed helpers"
            layers.append(
                PolicyLayer("Executable", f"installed {names} in {_display_path(target_bin_dir)}")
            )
        return PolicyResult(
            layers=tuple(layers),
            reload_hint=_RELOAD_HINT,
            warning=None,
        )

    def _remove() -> PolicyResult:
        target_bin_dir = _required_bin_dir(bundle, bin_dir)
        remove_tweak(bundle, rc_path)
        removed = (
            remove_tweak_executables(bundle, target_bin_dir) if target_bin_dir is not None else ()
        )
        layers = [PolicyLayer(bundle.label, f"cleared from {_display_path(rc_path)}")]
        if target_bin_dir is not None and bundle.executables:
            layers.append(
                PolicyLayer(
                    "Executable",
                    f"{len(removed)} removed from {_display_path(target_bin_dir)}",
                )
            )
        return PolicyResult(
            layers=tuple(layers),
            reload_hint=_RELOAD_HINT,
            warning=None,
        )

    installed_tools = installed_tools or {}
    missing_requires = tuple(
        tool_id for tool_id in bundle.requires if not installed_tools.get(tool_id, False)
    )
    return Policy(
        id=f"tweak:{bundle.id}",
        label=bundle.label,
        description=bundle.description,
        active=tweak_present(bundle, rc_path),
        apply=_apply,
        remove=_remove,
        requires=bundle.requires,
        missing_requires=missing_requires,
    )
