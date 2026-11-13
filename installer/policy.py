"""Generic environment-policy model, parallel to Tool.

A Policy bundles its identity (id/label/description), a snapshot of whether it is
currently active, and two idempotent closures — apply and remove — that each
return a structured per-layer PolicyResult. The pure layer owns the composition
of installer.guards; the IO boundary (setup.py) binds the real shim dir and rc
paths. The pip/npm ban is the first and only instance; future env tweaks slot in
with no screen changes.
"""

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from installer import env_redirect
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
from installer.locations import display_path as _display_path
from installer.locations import zshrc_path
from installer.omz import (
    apply_theme,
    default_theme,
    omz_root,
    owned_plugins,
    plugins_owned,
    remove_plugins,
    write_plugins,
)
from installer.run import CommandError
from installer.shellrc import ShellrcRefusal, ensure_source
from installer.terminal_shell import terminal_sync_warning
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
# environment.d is read by the systemd user manager's environment generator,
# which runs when that manager starts — at login, not when a shell starts.
# 15.7-RESEARCH.md Pitfall 2: a live probe showed systemctl --user
# show-environment does not see a freshly written file, so a hint that says
# "open a new shell" would overstate how soon the redirect becomes live.
_CACHE_REDIRECT_LINUX_HINT = (
    "Takes effect at the next login: the systemd user manager reads its "
    "environment.d directory only when it starts."
)
# IN-02: removal needs the same login cycle, and saying "open a new shell"
# here (the wording every other tweak uses) is wrong for environment.d --
# the variable stays in every process the user manager already started.
_CACHE_REDIRECT_LINUX_REMOVE_HINT = (
    "Log out and back in to drop the variable: the systemd user manager exported it "
    "to every process it has already started, and no new shell can undo that."
)
_CACHE_REDIRECT_MACOS_HINT = _TWEAK_ENABLE_HINT


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
    # False: nothing changed, so the screen must not flip the row's state (settings refusals).
    changed: bool = True


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
    is_active: Callable[[], bool] | None = None
    missing_requires_now: Callable[[], tuple[str, ...]] | None = None
    # New optional fields are APPENDED, never inserted: Policy is frozen and a
    # field placed mid-list silently renumbers every positional construction.
    # CR-01: "is anything of ours still on disk", for the uninstall sweep.
    # Distinct from is_active, which may answer a RUNTIME question (the Linux
    # timer's is-active state): a stopped-but-enabled timer, or one whose user
    # manager is unreachable, is not running yet still has files that restart
    # it at the next login. None means is_active/active already answers the
    # footprint question for this policy.
    owned: Callable[[], bool] | None = None
    # 17-08 D-09 (RUN-LEDGER Q2 refinement): only link-mode-dependent policies
    # move on a link-mode change — the ones whose blocks land in files the mode
    # selects. omz-plugins and the Linux environment.d cache
    # redirect never depend on the mode, so re-applying them would re-bootstrap
    # services and rewrite .zshrc for nothing.
    link_mode_aware: bool = False
    # Settings rows (23-11): the Effect column prefix, the read state (on/yours/off/drift)
    # and the detail panel's own lines. Each is None for every other policy.
    effect_kind: str | None = None
    state: Callable[[], str] | None = None
    detail_lines: Callable[[], tuple[str, ...]] | None = None

    def missing_requirements(self) -> tuple[str, ...]:
        """Read prerequisites at the point a policy is rendered or applied."""
        if self.missing_requires_now is not None:
            return self.missing_requires_now()
        return self.missing_requires


@dataclass(frozen=True)
class PolicyMove:
    """One policy's outcome in a link-mode move (17-08 D-09).

    New on purpose: `uninstall.SweepResult` cannot be imported here because
    installer/uninstall.py already imports installer/policy.py, and
    `PolicyResult` is one apply/remove's layers, not a per-policy moved/failed
    status.
    """

    policy_id: str
    status: Literal["moved", "failed"]
    detail: str


NOT_RESTORED_MARK = "; not restored: "


class PolicyRestoreError(OSError):
    """A link-mode move ended with at least one removed policy absent from
    both modes (WR-02). The ids travel in the message (run_live hands screens
    a str, and the text names them) and in `lost` for a caller that holds the
    exception itself."""

    def __init__(self, message: str, lost: Sequence[str]) -> None:
        super().__init__(message)
        self.lost = tuple(lost)


def lost_policy_ids(message: str) -> tuple[str, ...]:
    """The ids a PolicyRestoreError named in its message, for a caller that
    only received the flattened text (installer.ui_common.run_live)."""
    if NOT_RESTORED_MARK not in message:
        return ()
    tail = message.rpartition(NOT_RESTORED_MARK)[2]
    return tuple(part.strip() for part in tail.split(",") if part.strip())


def _rollback(policies: list[Policy]) -> tuple[str, ...]:
    """Re-apply every removed policy in the LIVE mode: remove() then apply(),
    both closures reading the live mode. remove() is mode-independent for the
    link-mode-aware policies (the ban strips the remove_rc_paths union, the
    tweak its fixed rc_path), so it also takes an already-moved block back out
    of the new mode's files, and it is a no-op for a policy that is still
    removed. Each policy's rollback error is caught so it can never replace
    the original exception the caller re-raises. Returns the ids whose
    re-apply failed: those policies are gone from both modes and the caller
    must say so."""
    lost: list[str] = []
    for policy in policies:
        try:
            policy.remove()
            policy.apply()
        except (OSError, CommandError, ShellrcRefusal):
            lost.append(policy.id)
    return tuple(lost)


def move_link_mode(
    policies: Sequence[Policy],
    new_mode: str,
    set_link_mode: Callable[[str], None],
    *,
    old_mode: str,
) -> tuple[PolicyMove, ...]:
    """Move active link-mode-aware policies from `old_mode` to `new_mode` (D-09).

    Removes each policy while the old mode is still live, saves the new mode,
    then applies each in the new mode, returning one entry per policy. Picking
    the mode that is already live is a no-op (ponytail #5): the mode is only
    saved (which also clears SettingsStore's invalid-on-disk flag) and no
    policy is touched. A policy whose new-mode apply fails is restored by
    remove() (which clears any partial new-mode write, ponytail #4) followed
    by an apply in the old mode, and is reported `failed`; the others still
    move. Callers pass only link-mode-aware, active policies; the function
    trusts that (no second active filter). With an empty list it only saves
    the mode.

    Both raise paths re-raise instead of reporting: when the save of the new
    mode fails, or when re-saving the new mode after an apply-failure restore
    fails, the live mode is the old one (SettingsStore.set_link_mode saves
    before it assigns) and every removed policy is rolled back to it via
    _rollback, then the original error propagates so run_live shows it.

    When the live mode is NOT the old one — the restore's own save failed, so
    SettingsStore kept the new mode — the rollback runs in the new mode, and
    a policy whose re-apply fails there is gone from both modes. That must
    never be silent (WR-02): the raised PolicyRestoreError names every such
    id after `"; not restored: "`, so a screen can flip its row OFF.
    """
    expected = (OSError, CommandError, ShellrcRefusal)
    if new_mode == old_mode:
        set_link_mode(new_mode)
        return ()
    removed: list[Policy] = []
    report: list[PolicyMove] = []
    for policy in policies:
        try:
            policy.remove()
        except expected as exc:
            report.append(PolicyMove(policy.id, "failed", f"{exc}; left as it was"))
            continue
        removed.append(policy)
    try:
        set_link_mode(new_mode)
    except expected as save_exc:
        lost = _rollback(removed)
        if lost:
            raise PolicyRestoreError(
                f"{save_exc}; not restored: {', '.join(lost)}", lost
            ) from save_exc
        raise
    for policy in removed:
        try:
            policy.apply()
        except expected as exc:
            try:
                set_link_mode(old_mode)
                policy.remove()
                policy.apply()
                set_link_mode(new_mode)
            except expected as restore_exc:
                lost = _rollback(removed)
                if lost:
                    raise PolicyRestoreError(
                        f"{restore_exc}; not restored: {', '.join(lost)}", lost
                    ) from restore_exc
                raise restore_exc
            report.append(PolicyMove(policy.id, "failed", f"{exc}; old block restored"))
            continue
        report.append(PolicyMove(policy.id, "moved", f"moved from {old_mode} to {new_mode}"))
    return tuple(report)


def ban_policy(
    *,
    shim_dir: Path,
    apply_rc_paths: list[Path] | Callable[[], list[Path]],
    remove_rc_paths: list[Path],
    path_value: str,
    which: Callable[[str], str | None],
) -> Policy:
    """The pip/npm ban as a Policy, composing installer.guards.

    apply writes shims into shim_dir and aliases into apply_rc_paths; remove
    clears shims and strips aliases from remove_rc_paths (the union of every
    location, so disabling leaves no stragglers regardless of link mode).

    apply_rc_paths is re-read at apply time (a list or a zero-argument
    callable returning one) because the link mode is now adjustable while the
    app is running. A ban whose aliases land in a ~/.myshellrc that split
    mode never sources is a silent no-op the user has no way to notice.
    """
    if isinstance(apply_rc_paths, list):
        captured_apply = cast("list[Path]", apply_rc_paths)

        def read_apply_rc_paths() -> list[Path]:
            return captured_apply
    else:
        read_apply_rc_paths = apply_rc_paths

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
        targets = read_apply_rc_paths()
        for rc_path in targets:
            write_ban_aliases(rc_path)
        alias_detail = "written to " + ", ".join(_display_path(p) for p in targets)
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
        # Live re-probe (17-20, opencode H2): a construction-time snapshot goes
        # stale the moment another view (Uninstall) sweeps the shims, and a
        # stale snapshot would make a link-mode change resurrect the ban.
        is_active=lambda: any(guard_status(shim_dir).values()),
        link_mode_aware=True,
    )


def _installed_predicate(
    installed_tools: Mapping[str, bool] | Callable[[str], bool] | None,
) -> Callable[[str], bool]:
    """A live predicate as-is; a mapping (or None) as a lookup that defaults to False."""
    if callable(installed_tools):
        return installed_tools
    snapshot = installed_tools or {}
    return lambda tool_id: snapshot.get(tool_id, False)


def _required_bin_dir(bundle: TweakBundle, bin_dir: Path | None) -> Path | None:
    if bundle.executables and bin_dir is None:
        raise ValueError(f"bundle '{bundle.id}' requires a managed bin_dir")
    return bin_dir


def _starship_theme(bundle: TweakBundle, rc_path: Path, name: str) -> tuple[PolicyLayer, ...]:
    """Starship owns the prompt: on, it empties the installer's theme; off, it restores the
    installer's default. A theme the user set is never touched (one path for every entry
    point: the install-time yes, the Policies row and the removal sweep, CR-08)."""
    if bundle.id != "starship":
        return ()
    zshrc = zshrc_path(Path.home(), os.environ)
    result = apply_theme(zshrc, rc_path, name)
    if result.outcome not in ("added", "replaced"):
        return ()
    return (PolicyLayer("Theme", f'ZSH_THEME="{name}" in {_display_path(zshrc)}'),)


def tweak_policy(
    bundle: TweakBundle,
    *,
    rc_path: Path,
    bin_dir: Path | None = None,
    installed_tools: Mapping[str, bool] | Callable[[str], bool] | None = None,
    ensure_sourced_from: tuple[Path, ...] | Callable[[], tuple[Path, ...]] = (),
) -> Policy:
    """A curated shell-tweak bundle as a Policy, parallel to ban_policy.

    apply writes the bundle's marker block into rc_path; remove strips it. `active`
    is "the bundle's block is present in rc_path". Idempotent (reuses tweaks'
    block machinery). The id is namespaced `tweak:<id>` so it never collides with
    the ban or another bundle in the Policies tab.

    `installed_tools` is a mapping or a live predicate; prerequisites are read
    when rendered or applied (`missing_requires_now`), not frozen at build time.

    `ensure_sourced_from`, when non-empty, is the split-mode rc file list: apply
    also wires each one to `source rc_path` via installer.shellrc.ensure_source —
    the same idempotent primitive installer.app.configure_path already uses for
    centralized/single mode — so the tweak actually reaches a real shell under
    split PATH mode too. remove needs no symmetric undo: the harmless, idempotent
    source line may still be load-bearing for another still-enabled tweak.

    ensure_sourced_from is re-read at apply time (a tuple or a zero-argument
    callable returning one) because the link mode is now adjustable while the
    app is running. A tweak sourced only into a ~/.myshellrc that split mode
    never sources is a silent no-op the user has no way to notice.
    """
    if isinstance(ensure_sourced_from, tuple):
        captured_sourced = cast("tuple[Path, ...]", ensure_sourced_from)

        def read_ensure_sourced_from() -> tuple[Path, ...]:
            return captured_sourced
    else:
        read_ensure_sourced_from = ensure_sourced_from

    def _apply() -> PolicyResult:
        target_bin_dir = _required_bin_dir(bundle, bin_dir)
        written = (
            install_tweak_executables(bundle, target_bin_dir) if target_bin_dir is not None else ()
        )
        write_tweak(bundle, rc_path, bin_dir=target_bin_dir)
        layers = [PolicyLayer(bundle.label, f"written to {_display_path(rc_path)}")]
        layers.extend(_starship_theme(bundle, rc_path, ""))
        if target_bin_dir is not None and bundle.executables:
            names = ", ".join(path.name for path in written) or "0 managed helpers"
            layers.append(
                PolicyLayer("Executable", f"installed {names} in {_display_path(target_bin_dir)}")
            )
        sourced = read_ensure_sourced_from()
        if sourced:
            for target in sourced:
                ensure_source(target, rc_path)
            wired = ", ".join(_display_path(p) for p in sourced)
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
        # The block is gone, so the default is the installer's own theme again, never bare.
        layers.extend(_starship_theme(bundle, rc_path, default_theme(rc_path)))
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

    is_installed = _installed_predicate(installed_tools)

    def _missing() -> tuple[str, ...]:
        return tuple(tool_id for tool_id in bundle.requires if not is_installed(tool_id))

    return Policy(
        id=f"tweak:{bundle.id}",
        label=bundle.label,
        description=bundle.description,
        active=tweak_present(bundle, rc_path),
        apply=_apply,
        remove=_remove,
        # Live re-probe (17-20, opencode H2): the frozen snapshot goes stale
        # after a toggle or another view's sweep, and a link-mode change that
        # trusted it would move the wrong set.
        is_active=lambda: tweak_present(bundle, rc_path),
        requires=bundle.requires,
        missing_requires=_missing(),
        missing_requires_now=_missing,
        link_mode_aware=True,
    )


def desktop_shell_policy(*, zsh_path: str | None, conf_dir: Path, home: Path) -> Policy:
    """The desktop-session SHELL row: one environment.d conf that names the real zsh."""
    zsh = zsh_path or "zsh"  # never SHELL=None: the Requires cell already reads missing: zsh
    redirect = env_redirect.shell_redirect(zsh_path) if zsh_path is not None else None

    def _is_active() -> bool:
        return redirect is not None and env_redirect.linux_applied(redirect, home, conf_dir)

    def _apply() -> PolicyResult:
        if redirect is None:  # the screen refuses first: the row requires zsh
            raise OSError("zsh is not installed")
        env_redirect.write_linux_redirect(redirect, home, conf_dir)
        return PolicyResult(
            layers=(PolicyLayer("environment.d", f"wrote {env_redirect.DESKTOP_SHELL_CONF}"),),
            reload_hint="Log out and back in for desktop apps to see it.",
            warning=None,
        )

    def _remove() -> PolicyResult:
        if not env_redirect.remove_owned_conf(conf_dir, env_redirect.DESKTOP_SHELL_CONF):
            return PolicyResult(
                layers=(),
                reload_hint=None,
                warning=(
                    f"{env_redirect.DESKTOP_SHELL_CONF} was not ours or is already gone; "
                    "nothing removed."
                ),
                changed=False,
            )
        return PolicyResult(
            layers=(PolicyLayer("environment.d", f"removed {env_redirect.DESKTOP_SHELL_CONF}"),),
            reload_hint=None,
            warning=None,
        )

    missing = () if zsh_path is not None else ("zsh",)
    return Policy(
        id="desktop-shell",
        label="SHELL for desktop apps",
        description=f"SHELL={zsh} in ~/.config/environment.d",
        active=_is_active(),
        apply=_apply,
        remove=_remove,
        requires=("zsh",),
        missing_requires=missing,
        missing_requires_now=lambda: missing,
        is_active=_is_active,
        # The sentinel alone: a file pointing at a removed or moved zsh is still ours.
        owned=lambda: env_redirect.conf_owned(conf_dir, env_redirect.DESKTOP_SHELL_CONF),
        effect_kind="desktop session",
        detail_lines=lambda: (
            f"Writes SHELL={zsh} to ~/.config/environment.d/{env_redirect.DESKTOP_SHELL_CONF} "
            "for apps started from the desktop menu.",
            "Takes effect at your next login; terminals already get SHELL from ~/.zshenv.",
        ),
    )


def _competing_conf_warning(
    redirect: env_redirect.CacheRedirect, written: Path, competing: tuple[Path, ...]
) -> str | None:
    """Say which way precedence actually goes, never assert it (WR-05).

    environment.d applies files in basename order and the last assignment
    wins, so a competing file that sorts BEFORE ours is overridden by this
    redirect, while one that sorts AFTER it overrides this redirect.
    """
    earlier = [path for path in competing if path.name < written.name]
    later = [path for path in competing if path.name > written.name]
    sentences: list[str] = []
    if earlier:
        names = ", ".join(_display_path(path) for path in earlier)
        sentences.append(
            f"{names} also sets {redirect.variable}; left in place. "
            f"{written.name} takes precedence because it sorts later."
        )
    if later:
        names = ", ".join(_display_path(path) for path in later)
        sentences.append(
            f"{names} also sets {redirect.variable} and sorts after {written.name}, so it "
            "overrides this redirect; left in place. Remove or rename it for the redirect "
            "to take effect."
        )
    return " ".join(sentences) if sentences else None


def cache_redirect_policy(
    redirect: env_redirect.CacheRedirect,
    *,
    platform_os: str,
    conf_dir: Path,
    rc_path: Path,
    home: Path,
    ensure_sourced_from: tuple[Path, ...] | Callable[[], tuple[Path, ...]] = (),
    system_conf_dirs: tuple[Path, ...] = (),
) -> Policy:
    """One tool's cache redirect as a Policy.

    macOS writes an exported marker block into ``rc_path``; every other OS
    writes an ``environment.d`` conf. The branch matches
    ``schedules.context_for``: compare against ``macos``, never
    against a ``linux`` string.

    ``ensure_sourced_from`` is re-read at apply time (a tuple or a
    zero-argument callable returning one) because the link mode is adjustable
    while the app runs. A redirect sourced only into a file split mode never
    reads is a silent no-op.

    ``system_conf_dirs`` are the read-only system environment.d directories
    scanned for a competing assignment (WR-05); the composition root passes
    ``env_redirect.SYSTEM_ENVIRONMENT_D_DIRS``.
    """
    if isinstance(ensure_sourced_from, tuple):
        captured_sourced = cast("tuple[Path, ...]", ensure_sourced_from)

        def read_ensure_sourced_from() -> tuple[Path, ...]:
            return captured_sourced
    else:
        read_ensure_sourced_from = ensure_sourced_from

    macos = platform_os == "macos"

    def _apply() -> PolicyResult:
        if macos:
            env_redirect.write_rc_redirect(redirect, home, rc_path)
            layers = [
                PolicyLayer(redirect.label, f"written to {_display_path(rc_path)}"),
            ]
            sourced = read_ensure_sourced_from()
            if sourced:
                for target in sourced:
                    ensure_source(target, rc_path)
                wired = ", ".join(_display_path(path) for path in sourced)
                layers.append(
                    PolicyLayer(
                        "Split-mode sourcing",
                        f"wired {wired} to source {_display_path(rc_path)}",
                    )
                )
            return PolicyResult(
                layers=tuple(layers),
                reload_hint=_CACHE_REDIRECT_MACOS_HINT,
                warning=None,
            )
        written = env_redirect.write_linux_redirect(redirect, home, conf_dir)
        competing = env_redirect.competing_conf_paths(redirect, home, conf_dir, system_conf_dirs)
        return PolicyResult(
            layers=(PolicyLayer(redirect.label, f"written to {_display_path(written)}"),),
            reload_hint=_CACHE_REDIRECT_LINUX_HINT,
            warning=_competing_conf_warning(redirect, written, competing),
        )

    def _remove() -> PolicyResult:
        if macos:
            env_redirect.remove_rc_redirect(redirect, rc_path)
            detail = f"cleared from {_display_path(rc_path)}"
        else:
            env_redirect.remove_linux_redirect(redirect, conf_dir)
            detail = f"cleared from {_display_path(conf_dir / redirect.conf_basename)}"
        return PolicyResult(
            layers=(PolicyLayer(redirect.label, detail),),
            reload_hint=None if macos else _CACHE_REDIRECT_LINUX_REMOVE_HINT,
            warning=None,
        )

    def _is_active() -> bool:
        if macos:
            return env_redirect.rc_applied(redirect, home, rc_path)
        return env_redirect.linux_applied(redirect, home, conf_dir)

    target = home.joinpath(*redirect.target_parts)
    return Policy(
        id=f"cache-redirect:{redirect.id}",
        label=redirect.label,
        description=(
            f"sets {redirect.variable} to {_display_path(target)}. {redirect.coverage_caveat}"
        ),
        active=_is_active(),
        apply=_apply,
        remove=_remove,
        is_active=_is_active,
        link_mode_aware=(platform_os == "macos"),
    )


def omz_plugins_policy(
    *,
    zshrc_path: Path,
    state_path: Path,
    present: bool | Callable[[], bool],
    terminal_sync: Callable[[], str | None] | None = None,
) -> Policy:
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

    def read_missing_requires() -> tuple[str, ...]:
        available = present() if callable(present) else present
        return () if available else ("oh-my-zsh",)

    def _apply() -> PolicyResult:
        added = write_plugins(zshrc_path, state_path, root=omz_root(Path.home(), os.environ))
        display = _display_path(zshrc_path)
        if added:
            detail = f"added {' '.join(added)} to {display}"
        else:
            detail = f"already in {display} — nothing added, nothing to undo later"
        # WR-03: the one shared failure contract, never a local try/except --
        # it is total by construction, so a synchronization failure can never
        # downgrade the plugin edit that already committed above.
        warning = terminal_sync_warning(terminal_sync)
        return PolicyResult(
            layers=(PolicyLayer("Oh-My-Zsh plugins", detail),),
            reload_hint=_ZSH_RELOAD_HINT,
            warning=warning,
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
        is_active=lambda: plugins_owned(state_path),
        requires=("oh-my-zsh",),
        missing_requires=read_missing_requires(),
        missing_requires_now=read_missing_requires,
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
