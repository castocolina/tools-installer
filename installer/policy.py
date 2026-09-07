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
    install_global_redirect_shims,
    install_redirect_shims,
    install_shims,
    remove_ban_aliases,
    remove_shims,
    write_ban_aliases,
)
from installer.omz import owned_plugins, plugins_owned, remove_plugins, write_plugins
from installer.shellrc import ensure_source
from installer.tweaks import (
    TweakBundle,
    install_tweak_executables,
    remove_tweak,
    remove_tweak_executables,
    tweak_present,
    write_tweak,
)

_RELOAD_HINT = "Open a new shell or run `hash -r` so cached command paths refresh."
# hash -r is about cached command PATH lookups and says nothing useful about a
# plugin array; a plugin change needs a new zsh or a sourced .zshrc.
_ZSH_RELOAD_HINT = "Open a new zsh shell, or run `source ~/.zshrc`, so Oh-My-Zsh loads the plugins."
# `hash -r` only refreshes cached PATH lookups; a freshly written alias or
# shell function needs the rc file re-sourced (or a new shell) to be loaded at
# all, so tweak_policy uses these two constants instead of _RELOAD_HINT, which
# stays correct for ban_policy's own PATH shims. The disable hint deliberately
# never contains the substring "source ~/.myshellrc": remove_tweak only
# deletes rc-file text, it cannot un-define something already loaded into the
# current shell, so re-sourcing is not valid advice after disabling — only a
# fresh shell drops it.
_TWEAK_ENABLE_HINT = (
    "Open a new shell, or run `source ~/.myshellrc`, so the new alias or function is loaded."
)
_TWEAK_DISABLE_HINT = (
    "Open a new shell so the disabled alias or function is no longer active in this "
    "session (re-sourcing your shell config cannot undefine something already "
    "loaded — you need a fresh shell, not a re-source)."
)


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
    hard_requires: bool = True
    log_path: Path | None = None
    set_schedule: Callable[[int, int], PolicyResult] | None = None
    read_schedule: Callable[[], tuple[int, int] | None] | None = None
    is_active: Callable[[], bool] | None = None


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
        # Hard blocks first, unconditional redirects second, argv-conditional
        # redirects third; each later writer owns the names it declares and
        # leaves the earlier, safer body in place whenever its own target is
        # unresolvable.
        shim_results = install_shims(shim_dir)
        shim_results.update(install_redirect_shims(shim_dir, path_value=path_value))
        shim_results.update(install_global_redirect_shims(shim_dir, path_value=path_value))
        active = sum(
            1
            for state in shim_results.values()
            if state.startswith(("created", "refreshed", "blocked"))
        )
        shim_detail = f"{active} active in {_display_path(shim_dir)}"
        degraded = [
            f"{name} {state}"
            for name, state in shim_results.items()
            if not state.startswith(("created", "refreshed"))
        ]
        if degraded:
            shim_detail += f" ({'; '.join(degraded)})"
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
        description=(
            "blocks bare pip/pip3, redirects npx to pnpm dlx, and wraps npm/pnpm "
            "so global installs run volta install instead (shims + aliases)"
        ),
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
    ensure_sourced_from: tuple[Path, ...] = (),
) -> Policy:
    """A curated shell-tweak bundle as a Policy, parallel to ban_policy.

    apply writes the bundle's marker block into rc_path; remove strips it. `active`
    is "the bundle's block is present in rc_path". Idempotent (reuses tweaks'
    block machinery). The id is namespaced `tweak:<id>` so it never collides with
    the ban or another bundle in the Policies tab.

    `ensure_sourced_from`, when non-empty, is the split-mode rc file list: apply
    also wires each one to `source rc_path` via installer.shellrc.ensure_source —
    the same idempotent primitive installer.app.configure_path already uses for
    centralized/single mode — so the tweak actually reaches a real shell under
    split PATH mode too. remove needs no symmetric undo: the harmless, idempotent
    source line may still be load-bearing for another still-enabled tweak.
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
        if ensure_sourced_from:
            for target in ensure_sourced_from:
                ensure_source(target, rc_path)
            wired = ", ".join(_display_path(p) for p in ensure_sourced_from)
            layers.append(
                PolicyLayer(
                    "Split-mode sourcing",
                    f"wired {wired} to source {_display_path(rc_path)}",
                )
            )
        return PolicyResult(
            layers=tuple(layers),
            reload_hint=_TWEAK_ENABLE_HINT,
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
            reload_hint=_TWEAK_DISABLE_HINT,
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


def omz_plugins_policy(*, zshrc_path: Path, state_path: Path, present: bool) -> Policy:
    """Oh-My-Zsh bundled git/docker plugins as a Policy, parallel to tweak_policy.

    apply/remove edit the single-line plugins=(...) array in zshrc_path in place
    and keep the ownership record in state_path (the ~/.myshellrc this installer
    owns; .zshrc never carries a marker). `active` is that record, not the array
    contents — the array cannot tell a machine this installer edited from one
    where the user wrote `plugins=(git docker)` themselves, and only the record
    can, which is what keeps remove from deleting names it never added.

    requires/missing_requires are the fields Policy already has and that
    PoliciesScreen already renders and enforces, so the detection predicate is
    new while the UX is not. The id is deliberately not namespaced tweak:
    because this is not a TweakBundle and must not read as one.
    """

    def _apply() -> PolicyResult:
        added = write_plugins(zshrc_path, state_path)
        display = _display_path(zshrc_path)
        if added:
            detail = f"added {' '.join(added)} to {display}"
        else:
            detail = f"already in {display} — nothing added, nothing to undo later"
        return PolicyResult(
            layers=(PolicyLayer("Oh-My-Zsh plugins", detail),),
            reload_hint=_ZSH_RELOAD_HINT,
            warning=None,
        )

    def _remove() -> PolicyResult:
        removed = remove_plugins(zshrc_path, state_path)
        display = _display_path(zshrc_path)
        if removed:
            detail = f"removed {' '.join(removed)} from {display}"
        else:
            detail = f"nothing to remove — this installer added no plugins to {display}"
        return PolicyResult(
            layers=(PolicyLayer("Oh-My-Zsh plugins", detail),),
            reload_hint=_ZSH_RELOAD_HINT,
            warning=None,
        )

    return Policy(
        id="omz-plugins",
        label="Oh-My-Zsh plugins",
        description="enables the bundled git and docker plugins in .zshrc's plugins=(...) array",
        active=plugins_owned(state_path),
        apply=_apply,
        remove=_remove,
        requires=("oh-my-zsh",),
        missing_requires=() if present else ("oh-my-zsh",),
    )


def omz_removal_detail(*, zshrc_path: Path, state_path: Path) -> str | None:
    """One line naming the plugins and the file a teardown would edit, or None.

    A preview that says only "omz-plugins" tells the user nothing about which
    names leave which file, which is the whole question when the file is one
    the installer does not own. None when there is nothing of ours to remove.
    """
    owned = owned_plugins(state_path)
    if not owned:
        return None
    return f"removes {', '.join(owned)} from the plugins=(...) array in {_display_path(zshrc_path)}"
