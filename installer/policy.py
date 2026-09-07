"""Generic environment-policy model, parallel to Tool.

A Policy bundles its identity (id/label/description), a snapshot of whether it is
currently active, and two idempotent closures — apply and remove — that each
return a structured per-layer PolicyResult. The pure layer owns the composition
of installer.guards; the IO boundary (setup.py) binds the real shim dir and rc
paths. The pip/npm ban is the first and only instance; future env tweaks slot in
with no screen changes.
"""

import contextlib
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from installer import daemon
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
from installer.run import CommandError, Runner, run_captured
from installer.shellrc import ensure_source
from installer.tweaks import (
    TweakBundle,
    install_tweak_executables,
    remove_tweak,
    remove_tweak_executables,
    tweak_present,
    write_tweak,
)

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


def _record_decided_durably(state_path: Path) -> None:
    """Retry daemon.record_decided once after a brief pause before giving up.

    A failed marker write after a MANUAL disable is worse than the symmetric
    failure after apply: it leaves daemon.decided() False, so the next
    interactive setup run's ensure_daemon_default silently re-applies (and
    re-registers) a daemon the user explicitly just turned off -- a reversal
    of user intent, not merely a lost audit trail (post-implementation review
    finding). The write is a single atomic rename against a small text file,
    so a real failure is almost always a transient one (a momentary lock/
    EINTR on a network home directory); retrying once cheaply closes most of
    that window without a larger state-machine change.
    """
    try:
        daemon.record_decided(state_path)
    except OSError:
        time.sleep(0.05)
        daemon.record_decided(state_path)


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
    installer.daemon's own crash-safe _atomic_write helper and, whenever a
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
                daemon._atomic_write(  # pyright: ignore[reportPrivateUsage]
                    plist_path, previous, mode=0o644
                )
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
            _record_decided_durably(state_path)
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
            _record_decided_durably(state_path)
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
            daemon._atomic_write(plist_path, previous, mode=0o644)  # pyright: ignore[reportPrivateUsage]
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
    )


def ensure_daemon_default(policy: Policy, *, state_path: Path) -> bool:
    """Auto-apply a policy's default exactly once, ever, per machine.

    Returns False without calling apply() when daemon.decided(state_path) is
    already True -- this covers BOTH "already explicitly enabled" and
    "already explicitly disabled" (11-RESEARCH.md Pitfall 2's own
    distinction: a plist's mere absence cannot tell those two apart, but the
    decided marker can). Otherwise calls policy.apply(), catching
    (OSError, CommandError) and returning False on failure WITHOUT the
    marker being recorded -- so a transient first-run failure (including a
    DaemonScheduleError, an OSError subclass per 11-01, from an unresolvable
    uv or an empty TMPDIR) is retried on the NEXT run, per 11-RESEARCH.md's
    Open Question 1 recommendation -- and returning True on success.

    A no-op call (already decided) and a genuinely failed apply both return
    False; callers that need to tell those two apart re-probe the policy's
    own live state (Policy.is_active), never this return value alone.
    """
    if daemon.decided(state_path):
        return False
    try:
        policy.apply()
    except (OSError, CommandError):
        return False
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
