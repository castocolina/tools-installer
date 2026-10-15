"""Generic environment-policy model, parallel to Tool.

A Policy bundles its identity (id/label/description), a snapshot of whether it is
currently active, and two idempotent closures — apply and remove — that each
return a structured per-layer PolicyResult. The pure layer owns the composition
of installer.guards; the IO boundary (setup.py) binds the real shim dir and rc
paths. The pip/npm ban is the first and only instance; future env tweaks slot in
with no screen changes.
"""

import contextlib
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from installer import daemon, env_redirect, systemd_daemon
from installer.agent_env import AgentAdapter
from installer.atomic import atomic_write_bytes
from installer.enums import DaemonState
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
from installer.run import CommandError, OutputRunner, Runner, run_captured
from installer.shellrc import ensure_source
from installer.terminal_shell import terminal_sync_warning
from installer.tweaks import (
    TweakBundle,
    install_tweak_executables,
    remove_tweak,
    remove_tweak_executables,
    tweak_present,
    write_tweak,
)

if TYPE_CHECKING:
    from installer.agent_policy import AgentAudit, AuditState

# The wrapper's installed filename, imported (not re-declared) for the
# validation-only render_plist call daemon_policy's apply/set_schedule make
# BEFORE install_wrapper has (re)created the real file: a hand-duplicated copy
# here previously risked silent drift from installer.daemon's own value
# (post-implementation review finding WR-03) -- daemon.WRAPPER_COMMAND is now
# the single source of truth for both modules.
_DAEMON_WRAPPER_COMMAND = daemon.WRAPPER_COMMAND

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
    missing_requires_now: Callable[[], tuple[str, ...]] | None = None
    # D-01e: the shared TimerStateCache the Linux daemon Policy was injected
    # with, exposed here so a cross-plan identity invariant (this Policy and
    # plan 15.7-06's disk-pressure probe hold the SAME instance) is
    # checkable by a test (`policy.state_cache is probe_cache`) rather than
    # only asserted in prose. Not what makes the sharing WORK -- injection at
    # the composition root is -- but it is the OBSERVATION point. Optional
    # and defaults to None so every other Policy factory in this module
    # (ban_policy, tweak_policy, omz_plugins_policy, daemon_policy) is
    # unaffected.
    state_cache: systemd_daemon.TimerStateCache | None = None
    # New optional fields are APPENDED, never inserted: Policy is frozen and a
    # field placed mid-list silently renumbers every positional construction.
    decided: Callable[[], bool] | None = None
    clear_decided: Callable[[], None] | None = None
    # CR-01: "is anything of ours still on disk", for the uninstall sweep.
    # Distinct from is_active, which may answer a RUNTIME question (the Linux
    # timer's is-active state): a stopped-but-enabled timer, or one whose user
    # manager is unreachable, is not running yet still has files that restart
    # it at the next login. None means is_active/active already answers the
    # footprint question for this policy.
    owned: Callable[[], bool] | None = None
    # 17-08 D-09 (RUN-LEDGER Q2 refinement): only link-mode-dependent policies
    # move on a link-mode change — the ones whose blocks land in files the mode
    # selects. The daemon, omz-plugins and the Linux environment.d cache
    # redirect never depend on the mode, so re-applying them would re-bootstrap
    # services and rewrite .zshrc for nothing.
    link_mode_aware: bool = False

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


def move_link_mode(
    policies: Sequence[Policy],
    new_mode: str,
    set_link_mode: Callable[[str], None],
    *,
    old_mode: str,
) -> tuple[PolicyMove, ...]:
    """Move active link-mode-aware policies from `old_mode` to `new_mode` (D-09).

    Removes each policy while the old mode is still live, saves the new mode,
    then applies each in the new mode, returning one entry per policy. Callers
    pass only link-mode-aware, active policies; the function trusts that (no
    second active filter). With an empty list it only saves the mode.
    """
    for policy in policies:
        policy.remove()
    set_link_mode(new_mode)
    for policy in policies:
        policy.apply()
    return tuple(
        PolicyMove(policy.id, "moved", f"moved from {old_mode} to {new_mode}")
        for policy in policies
    )


@dataclass(frozen=True)
class AgentEnvironmentPolicy:
    """One audited agent row and its optional safe apply action."""

    id: str
    label: str
    state: "AuditState"
    detail: str
    apply: Callable[[], PolicyResult] | None
    refresh: Callable[[], "AgentEnvironmentPolicy"] | None = None
    guidance_pending: bool = False
    action_detail: str | None = None


def agent_environment_policy(
    audit: "AgentAudit",
    *,
    home: Path,
    audit_agent: Callable[[AgentAdapter, Path], "AgentAudit"],
    apply_agent: Callable[[AgentAdapter, Path], PolicyResult],
    apply_guidance: Callable[[AgentAdapter, Path], PolicyResult] | None = None,
) -> AgentEnvironmentPolicy:
    """Bind permission and guidance actions according to their separate audits."""

    if apply_guidance is None:
        from installer.agent_policy import apply_agent_guidance

        apply_guidance = apply_agent_guidance

    permission_pending = (
        audit.state == "fixable" if audit.permission_pending is None else audit.permission_pending
    )

    def _apply() -> PolicyResult:
        layers: list[PolicyLayer] = []
        if audit.guidance_pending:
            layers.extend(apply_guidance(audit.adapter, home).layers)
        if permission_pending:
            layers.extend(apply_agent(audit.adapter, home).layers)
        return PolicyResult(tuple(layers), reload_hint=None, warning=None)

    actionable = audit.guidance_pending or permission_pending
    action = _apply if actionable else None
    if audit.guidance_pending and permission_pending:
        action_detail = "write shared guidance/reference and apply read-only permissions"
    elif audit.guidance_pending:
        action_detail = "write shared guidance/reference"
        if audit.state == "manual-required":
            action_detail += "; permissions remain manual/audit-only"
    elif permission_pending:
        action_detail = "apply read-only permissions"
    else:
        action_detail = None
    return AgentEnvironmentPolicy(
        id=audit.adapter.id,
        label=audit.adapter.label,
        state=audit.state,
        detail=audit.detail,
        apply=action,
        refresh=lambda: compose_agent_environment_policy(
            audit.adapter,
            home=home,
            audit_agent=audit_agent,
            apply_agent=apply_agent,
            apply_guidance=apply_guidance,
        ),
        guidance_pending=audit.guidance_pending,
        action_detail=action_detail,
    )


def compose_agent_environment_policy(
    adapter: AgentAdapter,
    *,
    home: Path,
    audit_agent: Callable[[AgentAdapter, Path], "AgentAudit"],
    apply_agent: Callable[[AgentAdapter, Path], PolicyResult],
    apply_guidance: Callable[[AgentAdapter, Path], PolicyResult] | None = None,
) -> AgentEnvironmentPolicy:
    """Audit one adapter without allowing an invalid path to abort the whole UI."""

    try:
        audit = audit_agent(adapter, home)
    except (OSError, RuntimeError, ValueError) as error:
        from installer.agent_policy import AgentAudit

        audit = AgentAudit(
            adapter,
            "manual-required",
            f"manual setup required: {error}",
        )
    return agent_environment_policy(
        audit,
        home=home,
        audit_agent=audit_agent,
        apply_agent=apply_agent,
        apply_guidance=apply_guidance,
    )


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
        link_mode_aware=True,
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
    ensure_sourced_from: tuple[Path, ...] | Callable[[], tuple[Path, ...]] = (),
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
        link_mode_aware=True,
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
    ``setup.py::_build_daemon_policy``: compare against ``macos``, never
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
        added = write_plugins(zshrc_path, state_path)
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
        requires=("oh-my-zsh",),
        missing_requires=read_missing_requires(),
        missing_requires_now=read_missing_requires,
    )


def _record_decided_durably(record: Callable[[], None]) -> None:
    """Retry a "decided" marker write once after a brief pause before giving up.

    A failed marker write after a MANUAL disable is worse than the symmetric
    failure after apply: it leaves the marker False, so the next interactive
    setup run's ensure_daemon_default silently re-applies (and re-registers)
    a daemon the user explicitly just turned off -- a reversal of user
    intent, not merely a lost audit trail (post-implementation review
    finding). The write is a single atomic rename against a small text file,
    so a real failure is almost always a transient one (a momentary lock/
    EINTR on a network home directory); retrying once cheaply closes most of
    that window without a larger state-machine change.

    `record` is a zero-argument recording callable (e.g.
    `lambda: daemon.record_decided(state_path)`) rather than a state_path
    argument bound to one module's own `record_decided`, so this ONE retry
    policy serves both the macOS (`installer.daemon.record_decided`) and
    Linux (`installer.systemd_daemon.record_decided`) markers -- each daemon
    factory passes its own module's recorder rather than this helper
    hardcoding one.
    """
    try:
        record()
    except OSError:
        time.sleep(0.05)
        record()


def daemon_policy(
    *,
    plist_path: Path,
    log_path: Path,
    wrapper_bin_dir: Path,
    script_path: Path,
    state_path: Path,
    installed_tools: Mapping[str, bool],
    path_value: str,
    tmpdir_value: str,
    home_value: str,
    uv_path: Path,
    uid: int,
    days: int = daemon.DEFAULT_DAYS,
    run: Runner = run_captured,
) -> Policy:
    """The background tmpdir-prune LaunchAgent as a Policy, parallel to
    omz_plugins_policy: a single artifact to write/remove plus a state_path
    ownership record for the "has any decision ever been made" marker.

    apply/remove/set_schedule are fully transactional: each snapshots the
    plist's prior bytes (or absence) before any launchctl call and, on a real
    launchctl failure, rolls back to that snapshot -- restoring the file via
    installer.atomic's crash-safe atomic_write_bytes and, whenever a
    prior working registration existed, making a best-effort daemon.bootstrap
    call with the restored content -- so a failed apply/remove/reschedule
    never leaves the plist file and the real registration disagreeing with
    each other (daemon.bootstrap's own internal bootout-then-bootstrap
    pre-clear unconditionally tears the OLD registration out before every
    attempt, reapply or not). A marker-write (record_decided) failure AFTER
    an already-successful launchctl call degrades to PolicyResult.warning
    instead of rolling back or propagating: the plist and the real
    registration already agree with each other at that point, so undoing a
    working registration over a bookkeeping-only failure would be strictly
    worse.

    `active`/`is_active()` are both plist_path.exists(), never a parsed
    `launchctl print` (its own man page disclaims that output as non-API).
    `fd`/`rg` are declared `requires`, but `hard_requires` is False: a missing
    fd/rg never blocks `apply` (REQ-daemon-dependency-gating) -- the wrapped
    script's own find/grep fallback degrades silently instead.
    """

    def _validate_and_write(hour: int, minute: int) -> None:
        # Validation gate FIRST, discarding the result: a DaemonScheduleError
        # here propagates with ZERO filesystem side effects at all, before
        # install_wrapper/ensure_log_path ever run (11-REVIEWS.md cycle 2
        # finding #6).
        daemon.render_plist(
            uv_path=uv_path,
            wrapper_path=wrapper_bin_dir / _DAEMON_WRAPPER_COMMAND,
            script_path=script_path,
            log_path=log_path,
            hour=hour,
            minute=minute,
            days=days,
            tmpdir=tmpdir_value,
            home=home_value,
            path_value=path_value,
        )
        installed_wrapper = daemon.install_wrapper(wrapper_bin_dir)
        daemon.ensure_log_path(log_path)
        daemon.write_plist(
            plist_path,
            uv_path=uv_path,
            wrapper_path=installed_wrapper,
            script_path=script_path,
            log_path=log_path,
            hour=hour,
            minute=minute,
            days=days,
            tmpdir=tmpdir_value,
            home=home_value,
            path_value=path_value,
        )

    def _apply() -> PolicyResult:
        previous: bytes | None = plist_path.read_bytes() if plist_path.exists() else None
        wrapper_existed_before = daemon.wrapper_present(wrapper_bin_dir)
        log_existed_before = log_path.exists()
        schedule = daemon.read_schedule(plist_path)
        default_schedule = (daemon.DEFAULT_HOUR, daemon.DEFAULT_MINUTE)
        hour, minute = schedule if schedule is not None else default_schedule
        # The rollback below must also cover _validate_and_write itself, not
        # only daemon.bootstrap: on a first-ever apply, install_wrapper/
        # ensure_log_path/write_plist can each raise OSError (disk full,
        # EACCES, a read-only LaunchAgents dir) AFTER install_wrapper has
        # already created a brand-new wrapper executable -- leaving it
        # orphaned on disk with no plist and no registration if only the
        # bootstrap call were guarded (post-implementation review finding
        # CR-01). DaemonScheduleError is itself an OSError subclass raised
        # by render_plist's pure validation half, before any write, so
        # catching OSError here is safe: wrapper_existed_before/
        # log_existed_before are still accurate and the rollback is a no-op
        # against artifacts that were never created.
        try:
            _validate_and_write(hour, minute)
            daemon.bootstrap(uid, plist_path, run=run)
        except (CommandError, OSError):
            if previous is not None:
                # A reapply: bootstrap's own internal pre-clear already tore
                # the old registration out before this attempt, so restoring
                # only the plist FILE would make `active` a false positive.
                atomic_write_bytes(plist_path, previous, mode=0o644)
                with contextlib.suppress(CommandError):
                    daemon.bootstrap(uid, plist_path, run=run)
            else:
                # A first-ever apply: roll back everything THIS call created,
                # never an artifact that legitimately predates it.
                plist_path.unlink(missing_ok=True)
                if not wrapper_existed_before:
                    daemon.remove_wrapper(wrapper_bin_dir)
                if not log_existed_before:
                    log_path.unlink(missing_ok=True)
            raise
        warning: str | None = None
        try:
            _record_decided_durably(lambda: daemon.record_decided(state_path))
        except OSError as exc:
            warning = f"decision not recorded: {exc}"
        return PolicyResult(
            layers=(PolicyLayer("Schedule", f"scheduled daily at {hour:02d}:{minute:02d}"),),
            reload_hint=None,
            warning=warning,
        )

    def _remove() -> PolicyResult:
        daemon.bootout(uid, run=run)
        try:
            plist_path.unlink(missing_ok=True)
        except OSError:
            with contextlib.suppress(CommandError):
                daemon.bootstrap(uid, plist_path, run=run)
            raise
        warnings: list[str] = []
        try:
            daemon.remove_wrapper(wrapper_bin_dir)
        except OSError as exc:
            warnings.append(f"wrapper removal failed: {exc}")
        try:
            # A retried write here matters more than the symmetric one in
            # _apply: a failure that leaves daemon.decided() False after a
            # manual disable lets the NEXT interactive setup silently
            # re-enable the daemon the user just turned off.
            _record_decided_durably(lambda: daemon.record_decided(state_path))
        except OSError as exc:
            warnings.append(f"decision not recorded: {exc}")
        return PolicyResult(
            layers=(PolicyLayer("Schedule", "unregistered; the plist was removed"),),
            reload_hint=None,
            warning="; ".join(warnings) if warnings else None,
        )

    def _set_schedule(hour: int, minute: int) -> PolicyResult:
        if not plist_path.exists():
            raise daemon.DaemonScheduleError(
                "cannot set a schedule for an inactive policy; enable it first"
            )
        previous = plist_path.read_bytes()
        _validate_and_write(hour, minute)
        try:
            daemon.bootstrap(uid, plist_path, run=run)
        except CommandError:
            atomic_write_bytes(plist_path, previous, mode=0o644)
            with contextlib.suppress(CommandError):
                daemon.bootstrap(uid, plist_path, run=run)
            raise
        return PolicyResult(
            layers=(PolicyLayer("Schedule", f"scheduled daily at {hour:02d}:{minute:02d}"),),
            reload_hint=None,
            warning=None,
        )

    missing_requires = tuple(
        tool_id for tool_id in ("fd", "rg") if not installed_tools.get(tool_id, False)
    )
    return Policy(
        id="daemon:prune-tmpdir",
        label="Background tmpdir cleanup",
        description=(
            "runs scripts/prune-user-tmpdir.sh daily via a macOS LaunchAgent, deleting "
            "orphaned agent-runtime temp files"
        ),
        active=plist_path.exists(),
        apply=_apply,
        remove=_remove,
        requires=("fd", "rg"),
        missing_requires=missing_requires,
        hard_requires=False,
        log_path=log_path,
        set_schedule=_set_schedule,
        read_schedule=lambda: daemon.read_schedule(plist_path),
        is_active=lambda: plist_path.exists(),
        decided=lambda: daemon.decided(state_path),
        clear_decided=lambda: daemon.clear_decided(state_path),
    )


_UNREACHABLE_MANAGER_WARNING = (
    "the systemd user manager could not be reached, so `systemctl --user daemon-reload` "
    "did not run; the unit files are removed, but a timer it already loaded may keep "
    "running until you log out, or until you run `systemctl --user daemon-reload` yourself"
)


def linux_daemon_policy(
    *,
    unit_dir: Path,
    log_path: Path,
    wrapper_bin_dir: Path,
    script_path: Path,
    state_path: Path,
    installed_tools: Mapping[str, bool],
    path_value: str,
    tmpdir_value: str,
    home_value: str,
    uv_path: Path,
    age_minutes: int = systemd_daemon.DEFAULT_AGE_MINUTES,
    run: Runner = run_captured,
    read_output: OutputRunner = systemd_daemon.query_systemctl,
    timer_cache: systemd_daemon.TimerStateCache | None = None,
) -> Policy:
    """The background tmp-prune systemd user timer as a Policy, the Linux
    mirror of daemon_policy (D-01): same ownership-marker convention, same
    wrapper-executable pattern, same Policies-screen wiring -- only the
    backend verbs differ (systemctl --user instead of launchctl).

    apply/remove are transactional: each snapshots the prior unit-file bytes
    (or absence) before any systemctl call and, on a real backend failure,
    rolls back to that snapshot -- restoring the unit files via
    installer.atomic's crash-safe write and, whenever a prior working
    registration existed, making a best-effort systemd_daemon.bootstrap call
    with the restored content, plus a compensating daemon-reload -- so a
    failed apply/remove never leaves the unit files and the real
    registration disagreeing with each other. A marker-write (record_decided)
    failure AFTER an already-successful systemctl call degrades to
    PolicyResult.warning instead of rolling back or propagating: the unit
    files and the real registration already agree with each other at that
    point, so undoing a working registration over a bookkeeping-only failure
    would be strictly worse.

    D-01c/D-01e: `active`/`is_active()` are bound to the shared
    TimerStateCache's runtime-truthful answer, never unit-file presence
    alone. Per D-01e this factory does NOT construct the cache when one is
    injected: `timer_cache` is None means "build your own" (used by
    `_run_uninstall`'s existing call site, which renders no probe, so
    identity is moot there); otherwise the SAME injected instance is used
    for both the frozen `active` field (a construction-time `read()`, which
    also WARMS the cache before the first TUI frame) and the `is_active`
    closure, and exposed on `Policy.state_cache` so a test can assert
    identity with plan 15.7-06's disk-pressure probe.

    CR-01: `owned()` is the separate FOOTPRINT answer the uninstall sweep
    reads -- either unit file, the enablement symlink or the owned wrapper on
    disk -- so a stopped-but-enabled timer, or one whose user manager is
    unreachable, is still torn down. `remove` then deletes the files even when
    the manager cannot be reached, and discloses that no daemon-reload ran.

    `installed_tools` is accepted for signature symmetry with daemon_policy
    and because setup.py's composition root already computes it uniformly
    for every Policy factory -- unused here because `requires` is
    deliberately left empty (the Linux cleanup script uses only find and rm,
    so fd/rg are genuinely not prerequisites here, unlike the macOS script).
    """
    del installed_tools
    cache = (
        timer_cache
        if timer_cache is not None
        else systemd_daemon.TimerStateCache(
            lambda: systemd_daemon.timer_state(unit_dir, read_output=read_output)
        )
    )

    def _validate_and_write() -> None:
        # Validation gate FIRST, discarding the result: a DaemonScheduleError
        # here propagates with ZERO filesystem side effects, before
        # install_wrapper/ensure_log_path ever run -- mirrors
        # daemon_policy._validate_and_write's own ordering.
        systemd_daemon.render_service(
            uv_path=uv_path,
            wrapper_path=wrapper_bin_dir / systemd_daemon.WRAPPER_COMMAND,
            script_path=script_path,
            log_path=log_path,
            tmpdir=tmpdir_value,
            home=home_value,
            path_value=path_value,
            age_minutes=age_minutes,
        )
        installed_wrapper = systemd_daemon.install_wrapper(wrapper_bin_dir)
        systemd_daemon.ensure_log_path(log_path)
        systemd_daemon.write_units(
            unit_dir,
            uv_path=uv_path,
            wrapper_path=installed_wrapper,
            script_path=script_path,
            log_path=log_path,
            tmpdir=tmpdir_value,
            home=home_value,
            path_value=path_value,
            age_minutes=age_minutes,
        )

    def _snapshot_units() -> dict[Path, bytes | None]:
        service_path, timer_path = systemd_daemon.unit_paths(unit_dir)
        return {
            path: path.read_bytes() if path.exists() else None
            for path in (service_path, timer_path)
        }

    def _restore_units(snapshot: dict[Path, bytes | None]) -> None:
        # Back to exactly the snapshot: a file that existed is rewritten with
        # its prior bytes, and one that did not is deleted. IN-05: a first
        # apply over a half-removed install must not delete the one unit file
        # that predates it.
        for path, previous in snapshot.items():
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write_bytes(path, previous, mode=0o644)

    def _detect_and_take_over_competitors() -> tuple[PolicyLayer | None, str | None]:
        """D-02: detect a pre-existing competing cleanup mechanism in BOTH
        systemd scopes, disable the user-scope one(s) (D-02a), and disclose
        -- never mutate -- the system-scope one(s).

        Called from `_apply` only AFTER this project's own registration has
        already succeeded: D-02's requirement is that two mechanisms never
        run side by side, and a takeover-first ordering that then failed to
        register would leave the machine with NO cleanup at all, which is
        strictly worse than a few milliseconds of overlap (T-15.7-13).

        Returns (layer, warning), both None when nothing was detected -- the
        no-competitor case must keep producing exactly the layers/warning it
        produced before this feature existed. Every branch inside is guarded
        -- the detection half against CommandError, OSError and ValueError,
        the mutation half per unit inside disable_competing plus the
        structural ValueError refusal here -- so a bookkeeping-tier
        detection/takeover failure never undoes an already-working
        registration (T-15.7-13). The guards are deliberately NOT one outer
        try: everything already learned (which units were disabled, and the
        system-scope disclosure that needed no mutation at all) must survive
        a failure in the step after it (IN-07).
        """
        try:
            competitors = systemd_daemon.detect_competing(read_output=read_output)
        except (CommandError, OSError, ValueError):
            return None, None
        if not competitors:
            return None, None
        # IN-07: resolved BEFORE the mutation half, and never inside its
        # guard: a takeover failure must not take the system-scope
        # disclosure (which needed no mutation at all) down with it.
        system_warning = systemd_daemon.system_scope_warning(competitors)
        system_names = sorted(
            {c.name for c in competitors if c.scope == systemd_daemon.SCOPE_SYSTEM}
        )
        user_scope = [c for c in competitors if c.scope == systemd_daemon.SCOPE_USER]
        disabled: tuple[str, ...] = ()
        failed: tuple[str, ...] = ()
        if user_scope:
            try:
                disabled, failed = systemd_daemon.disable_competing(user_scope, run=run)
            except ValueError:
                # The structural refusal disable_competing raises for a
                # system-scope entry, which this function never hands it. It
                # can only fire on a programming error, and it fires BEFORE
                # any argv, so nothing was disabled: report every unit as
                # still running rather than crashing a live policy apply.
                failed = tuple(unit.name for unit in user_scope)
        detail_parts: list[str] = []
        if disabled:
            detail_parts.append(f"disabled: {', '.join(disabled)}")
        if failed:
            detail_parts.append(f"disable failed, still running: {', '.join(failed)}")
        if system_names:
            detail_parts.append(f"system-scope, left running: {', '.join(system_names)}")
        layer = PolicyLayer("Competing mechanism", "; ".join(detail_parts))
        # CR-02: a SUCCESSFUL takeover is a disclosure too. The layers
        # never reach ensure_daemon_default's on_warning sink (the one
        # apply path with no human watching), so the warning must say
        # which unit was disabled and how to re-enable it.
        #
        # Lane-2 HIGH-02: all three sentences are emitted together, so a
        # PARTIAL takeover names BOTH halves -- what was disabled (with the
        # `enable --now` that puts it back) and what survived (with the
        # `disable --now` that stops it) -- and the user can tell which is
        # which. D-02c is what makes that the right shape: a partial
        # takeover proceeds and is disclosed, never rolled back. Both name
        # lists arrive name-sorted from disable_competing, so the sentence
        # a user reads is the same on every run.
        warning_parts = [
            sentence
            for sentence in (
                systemd_daemon.takeover_disclosure(disabled),
                system_warning,
                systemd_daemon.user_scope_failure_warning(failed),
            )
            if sentence
        ]
        return layer, (" ".join(warning_parts) if warning_parts else None)

    def _apply() -> PolicyResult:
        # invalidate() is called from a `finally` at the bottom of this
        # closure (D-01e/D-01c) -- on the success AND the failure path
        # alike, so a toggle or a rollback is never reported through a
        # stale memoized answer.
        had_prior_registration = systemd_daemon.units_present(unit_dir)
        snapshot = _snapshot_units()
        link_existed_before = systemd_daemon.wants_link_path(unit_dir).is_symlink()
        wrapper_existed_before = systemd_daemon.wrapper_present(wrapper_bin_dir)
        log_existed_before = log_path.exists()
        try:
            try:
                _validate_and_write()
                systemd_daemon.bootstrap(unit_dir, run=run)
            except (CommandError, OSError):
                if had_prior_registration:
                    # A reapply: bootstrap's own daemon-reload already made
                    # the user manager read the NEW (possibly broken)
                    # content before this attempt failed, so restoring only
                    # the FILES would leave the manager holding a
                    # definition the disk no longer matches. Restore, then
                    # a compensating reload, then a best-effort
                    # re-bootstrap of the restored content.
                    _restore_units(snapshot)
                    with contextlib.suppress(CommandError):
                        systemd_daemon.daemon_reload(run=run)
                    with contextlib.suppress(CommandError):
                        systemd_daemon.bootstrap(unit_dir, run=run)
                else:
                    # A first-ever apply: roll back everything THIS call
                    # created, never an artifact that legitimately
                    # predates it. The apply path reloaded systemd BEFORE
                    # enabling, so the user manager is already holding the
                    # definition about to be deleted -- the compensating
                    # reload keeps `systemctl --user list-units` honest
                    # (review MEDIUM 15.7-01). Best-effort: a write_units
                    # failure this early can leave unit_dir in an unusual
                    # state (e.g. never created at all), and a secondary
                    # OSError while cleaning up must never mask the
                    # ORIGINAL failure being unwound, nor abort the rest of
                    # this rollback (wrapper/log cleanup still below).
                    # WR-01: `enable` may already have created the
                    # timers.target.wants symlink before a later verb
                    # failed; undo it before the unit it points at is gone,
                    # or it dangles and nothing ever removes it.
                    with contextlib.suppress(CommandError):
                        systemd_daemon.disable_timer(run=run)
                    with contextlib.suppress(OSError):
                        _restore_units(snapshot)
                        link = systemd_daemon.wants_link_path(unit_dir)
                        if not link_existed_before and link.is_symlink():
                            link.unlink()
                    with contextlib.suppress(CommandError):
                        systemd_daemon.daemon_reload(run=run)
                    if not wrapper_existed_before:
                        systemd_daemon.remove_wrapper(wrapper_bin_dir)
                    if not log_existed_before:
                        log_path.unlink(missing_ok=True)
                raise
            warning: str | None = None
            try:
                _record_decided_durably(lambda: systemd_daemon.record_decided(state_path))
            except OSError as exc:
                warning = f"decision not recorded: {exc}"
            layers = [
                PolicyLayer(
                    "Schedule",
                    f"runs every {systemd_daemon.DEFAULT_INTERVAL} via a systemd user timer",
                ),
            ]
            # D-02: detection and takeover run only AFTER the two lines
            # above -- this project's own registration is already real and
            # the marker already (best-effort) recorded -- see
            # _detect_and_take_over_competitors's own docstring for why.
            competing_layer, competing_warning = _detect_and_take_over_competitors()
            if competing_layer is not None:
                layers.append(competing_layer)
            if competing_warning:
                warning = f"{warning}; {competing_warning}" if warning else competing_warning
            return PolicyResult(
                layers=tuple(layers),
                reload_hint=None,
                warning=warning,
            )
        finally:
            cache.invalidate()

    def _remove() -> PolicyResult:
        # Same invalidate()-in-`finally` discipline as _apply above.
        try:
            snapshot = _snapshot_units()
            reached = systemd_daemon.bootout(unit_dir, run=run, read_output=read_output)
            try:
                systemd_daemon.remove_units(unit_dir)
            except OSError:
                # WR-01: remove_units may have deleted the service before the
                # timer unlink failed. Re-registering a half-deleted pair
                # would enable a timer whose service no longer exists, so the
                # files come back first, and only a complete restore is
                # re-bootstrapped.
                try:
                    _restore_units(snapshot)
                except OSError:
                    pass
                else:
                    if reached:
                        with contextlib.suppress(CommandError):
                            systemd_daemon.bootstrap(unit_dir, run=run)
                raise
            warnings: list[str] = []
            if reached:
                # _remove's own unit-file deletion just changed what the user
                # manager's already-loaded definition was read from -- the
                # same compensating-reload reasoning the rollback branches
                # above apply (review MEDIUM 15.7-01).
                with contextlib.suppress(CommandError):
                    systemd_daemon.daemon_reload(run=run)
            else:
                # CR-01: the files are gone, so nothing restarts the timer at
                # the next login, but a manager this process could not reach
                # may still hold the loaded unit until it reloads.
                warnings.append(_UNREACHABLE_MANAGER_WARNING)
            try:
                systemd_daemon.remove_wrapper(wrapper_bin_dir)
            except OSError as exc:
                warnings.append(f"wrapper removal failed: {exc}")
            try:
                # A retried write here matters more than the symmetric one
                # in _apply: a failure that leaves systemd_daemon.decided()
                # False after a manual disable lets the NEXT interactive
                # setup silently re-enable the daemon the user just turned
                # off.
                _record_decided_durably(lambda: systemd_daemon.record_decided(state_path))
            except OSError as exc:
                warnings.append(f"decision not recorded: {exc}")
            return PolicyResult(
                layers=(PolicyLayer("Schedule", "unregistered; the unit files were removed"),),
                reload_hint=None,
                warning="; ".join(warnings) if warnings else None,
            )
        finally:
            cache.invalidate()

    def _is_active() -> bool:
        # The Policies row: is the timer RUNNING right now.
        return cache.read() is DaemonState.ACTIVE

    def _owned() -> bool:
        # The uninstall sweep: is anything this policy installed still on
        # disk (CR-01). File reads only, so it never spawns systemctl.
        return systemd_daemon.footprint_present(unit_dir) or systemd_daemon.wrapper_present(
            wrapper_bin_dir
        )

    return Policy(
        id="daemon:prune-tmp-linux",
        label="Background tmpdir cleanup",
        description=(
            f"runs scripts/prune-tmp-linux.sh every {systemd_daemon.DEFAULT_INTERVAL} via a "
            "systemd user timer, deleting orphaned Bun runtime-cache files"
        ),
        active=_is_active(),
        apply=_apply,
        remove=_remove,
        log_path=log_path,
        is_active=_is_active,
        state_cache=cache,
        decided=lambda: systemd_daemon.decided(state_path),
        clear_decided=lambda: systemd_daemon.clear_decided(state_path),
        owned=_owned,
    )


# A wedged or never-dispatched worker costs this delay, never a hang.
DAEMON_DEFAULT_WAIT_SECONDS = 5.0


class DaemonDefaultWarnings:
    """Collects warnings from the on-by-default apply and says when it finished.

    The daemon default runs on a Textual thread worker that ``app.run()`` does
    not join. Without this event the competing-mechanism disclosure is printed
    only when that worker happens to finish before the CLI's next line, and the
    ``summary is None`` abort branch returns before any later print at all.
    ``wait`` returns immediately, with completion True, when the collector was
    never armed, so a run with no auto-apply pays nothing.
    """

    def __init__(self) -> None:
        self._messages: list[str] = []
        self._armed = False
        self._finished = threading.Event()

    def append(self, message: str) -> None:
        self._messages.append(message)

    def arm(self) -> None:
        self._armed = True

    def finish(self) -> None:
        self._finished.set()

    def wait(self, timeout: float) -> tuple[tuple[str, ...], bool]:
        if not self._armed:
            return (), True
        completed = self._finished.wait(timeout)
        return tuple(self._messages), completed


def ensure_daemon_default(
    policy: Policy, *, on_warning: Callable[[str], None] | None = None
) -> bool:
    """Auto-apply a policy's default exactly once, ever, per machine.

    Returns False without calling apply() when the policy has no ``decided``
    closure (a policy with no ownership record has no once-per-machine default)
    or when that closure already answers True -- this covers BOTH "already
    explicitly enabled" and "already explicitly disabled" (11-RESEARCH.md
    Pitfall 2's own distinction: a plist's mere absence cannot tell those two
    apart, but the decided marker can). Otherwise calls policy.apply(),
    catching (OSError, CommandError) and returning False on failure WITHOUT
    the marker being recorded -- so a transient first-run failure (including a
    DaemonScheduleError, an OSError subclass per 11-01, from an unresolvable
    uv or an empty TMPDIR) is retried on the NEXT run, per 11-RESEARCH.md's
    Open Question 1 recommendation -- and returning True on success.

    ``on_warning`` is called with ``policy.apply()``'s warning whenever that
    warning is not None. This function is the ONLY apply path with no human
    present: the Linux daemon is on by default from the interactive wizard,
    and the competing-mechanism disclosure is produced by that apply. The
    result used to be discarded, so a first-run takeover of another tool's
    user-scope timer would happen with nothing said to anyone.

    A no-op call (already decided) and a genuinely failed apply both return
    False; callers that need to tell those two apart re-probe the policy's
    own live state (Policy.is_active), never this return value alone.
    """
    if policy.decided is None or policy.decided():
        return False
    try:
        result = policy.apply()
    except (OSError, CommandError):
        return False
    if on_warning is not None and result.warning is not None:
        on_warning(result.warning)
    return True


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
