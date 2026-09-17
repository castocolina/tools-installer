"""Registry-driven uninstall: remove the userspace artifacts install_download
and install_app create, and — for a full uninstall — perform the symmetric
teardown of every still-enabled shell tweak, reusing the same policy remove
path the Policies view uses (CONTEXT D-04). Cask/brew/native-managed artifacts
are left alone."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from installer.apps import APP_KINDS, cli_spec
from installer.download import DOWNLOAD_KINDS
from installer.enums import UninstallState
from installer.executors import ExecutorError
from installer.locations import applications_dir, opt_dir
from installer.model import Method, Tool
from installer.platform import Platform
from installer.policy import Policy, omz_plugins_policy, tweak_policy
from installer.resolve import resolve_methods
from installer.run import CommandError
from installer.tweaks import TweakBundle, tweak_executables_present, tweak_present

# No import cycle: installer.policy imports guards, tweaks and omz, none of
# which import uninstall.


def _exists(path: Path) -> bool:
    # is_symlink catches dangling links (exists() is False when the target is gone).
    return path.exists() or path.is_symlink()


def _plan_app(method: Method, default_bin_dir: Path, add: Callable[[Path], None]) -> None:
    """Plan the ~/Applications bundle and the cli symlink an app method created.

    Only the userspace bundle is planned — a copy in /Applications was never
    ours to manage. The cli symlink name comes from the same validator the
    installer uses (apps.cli_spec), so an invalid cli that install_app would
    have rejected — and therefore never symlinked — plans nothing.
    """
    app = method.params.get("app")
    if not isinstance(app, str) or not app:
        return
    if PurePosixPath(app).name != app or app in (".", ".."):
        return
    add(applications_dir() / app)
    try:
        spec = cli_spec(method)
    except ExecutorError:
        return
    if spec is None:
        return
    add(default_bin_dir / spec[1])


def plan_uninstall(tools: list[Tool], default_bin_dir: Path) -> list[Path]:
    """Existing artifacts the download/raw/app executors would have created.

    The registry is the manifest: every download/raw method maps to opt_dir(binname)
    and <bin_dir>/binname, where binname is the basename of the method's member;
    every app method maps to ~/Applications/<app> and <bin_dir>/<cli basename>.
    Only paths that currently exist (including dangling symlinks) are returned, in a
    stable de-duplicated order.
    """
    found: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path not in seen and _exists(path):
            seen.add(path)
            found.append(path)

    for tool in tools:
        for method in tool.methods:
            if method.kind in APP_KINDS:
                _plan_app(method, default_bin_dir, add)
                continue
            if method.kind not in DOWNLOAD_KINDS:
                continue
            member = method.params.get("member")
            if not isinstance(member, str) or not member:
                continue
            binname = PurePosixPath(member).name
            if binname in ("", ".", ".."):
                # Defensive: a traversal/empty basename would resolve opt_dir/bin
                # paths up to ~/.local and risk deleting far more than one tool.
                # Members come from the trusted registry, but this code deletes files.
                continue
            declared = method.params.get("bin_dir")
            base = (
                Path(declared).expanduser()
                if isinstance(declared, str) and declared
                else default_bin_dir
            )
            add(opt_dir(binname))
            add(base / binname)
    return found


@dataclass(frozen=True, init=False)
class ToolRow:
    """A tool annotated with its removability on this machine + platform.

    States: removable (userspace artifacts on disk -> selectable, has paths),
    managed (installed but no userspace artifacts -> inert, manager hint),
    absent (resolvable here but not installed -> inert), unavailable (no method
    applies to this platform -> inert)."""

    tool: Tool
    state: UninstallState
    paths: list[Path]
    hint: str
    selectable: bool
    # CR-03 (15.4-REVIEW.md): the TERSE register beside `hint`'s prose one --
    # the manager's bare name ("Homebrew", "dnf", "GitHub release"), for the
    # table CELL, while `hint` stays the full sentence the detail bar shows.
    # `None` means "no attribution for this row", which the screen renders as
    # its own generic label; only the managed branch ever sets it.
    manager: str | None

    def __init__(
        self,
        tool: Tool,
        state: UninstallState | str,
        paths: list[Path],
        hint: str,
        selectable: bool,
        manager: str | None = None,
    ) -> None:
        object.__setattr__(self, "tool", tool)
        object.__setattr__(self, "state", UninstallState(state))
        object.__setattr__(self, "paths", paths)
        object.__setattr__(self, "hint", hint)
        object.__setattr__(self, "selectable", selectable)
        object.__setattr__(self, "manager", manager)


def manager_name(method: Method, param: str, fallback: str) -> str:
    # brew/cask uninstall takes the formula/cask name (in the method params),
    # NOT the runnable cmd — they differ for e.g. rg/ripgrep, code/visual-studio-code.
    value = method.params.get(param)
    return value if isinstance(value, str) and value else fallback


# The ownership seam `classify_tools` accepts (15.4-05/D-03/D-04): a plain
# callable from `Tool` to `str | None`, never `ManagerOwnership` -- not even
# under a `TYPE_CHECKING` guard. 15.4-RESEARCH.md Pitfall 3 offered threading
# `platform`/`inventory`/`native_probe` into this module's own signature
# instead; that is the shape D-05 explicitly rejects, because it would make
# this screen run its own resolution pass. `installer/ownership.py` already
# imports `manager_name` FROM this module (`ownership.py:74`), so the
# dependency runs ownership-to-uninstall; importing `ManagerOwnership` here
# would import back and create the cycle `.claude/architecture.md` rule 5
# forbids. A plain callable keeps this module free of that import in either
# direction -- the composition root (`setup.py`) is what actually binds the
# seam to `VersionRefreshService.ownership_of` plus `installer.ownership
# .removal_hint`.
OwnerHint = Callable[[Tool], str | None]

# The TERSE half of the same seam (CR-03, 15.4-REVIEW.md), bound in `setup.py`
# to `VersionRefreshService.ownership_of` plus `installer.ownership
# .removal_label` exactly as `OwnerHint` is bound to `removal_hint`. Two
# callables rather than one returning a pair, for the same reason
# `installer/ownership.py` keeps `OWNER_LABELS` and `OWNER_DETAIL_LABELS` as
# two declared tables: a ~14-character cell and a removal sentence have
# different jobs, and deriving one from the other by string surgery is the
# coupling both registers exist to avoid.
OwnerLabelHint = Callable[[Tool], str | None]


def _manager_hint(tool: Tool, platform: Platform) -> str:
    """The registry-derived removal phrase for a managed tool, consulted only
    when the ownership seam has nothing to say for it.

    Scans `resolve_methods(tool, platform)` -- already imported at :20 and
    already called by `classify_tools` for its absent/unavailable branch, so
    this introduces no new dependency and no second copy of `_applies` --
    rather than a raw `tool.methods` scan (Round-2 review HIGH). The raw scan
    used to return "managed by Homebrew — `brew uninstall --cask codex`" on a
    Linux host for codex, whose cask is gated `os = ["macos"]`
    (`installer/registry.toml:1343-1350`) and excluded there by
    `installer/resolve.py:67-69` -- and this is the exact path taken when the
    ownership seam is absent or epoch-invalidated, so the "degradation is
    generic, never wrong" claim was false until this filter.

    Deliberately NOT `installer/ownership.py`'s `_method_targets_platform`:
    importing it would create the cycle noted on `OwnerHint` above, and the
    two helpers answer different questions -- that one deliberately WIDENS
    attribution past the install gate for ownership evidence backed by a real
    inventory reading, while this is a registry-only GUESS with no evidence
    behind it and must therefore be NARROWER, not wider. A linuxbrew-cask
    tool gets its specific attribution from the ownership seam and the
    generic phrase from here, which is the correct division.

    One deliberate narrowing versus the pre-filter behaviour: a tool
    declaring only a brew method on a host with no brew now gets the generic
    phrase instead of a `brew uninstall` line that was never runnable there.
    That is the fix, not a regression -- the existing brew/cask hint tests
    all use a macOS-with-brew platform and stay green.

    WR-04 (15.4-REVIEW.md): `resolve_methods` also filters on `arch` and
    `min_os_version`, a SECOND narrowing the Round-2 fix did not name. The
    registry has three rows it bites -- gnu-bash's two arch-split brew
    methods and `container`'s `min_os_version` one -- so on a macOS arm64
    host below `container`'s floor a brew-installed `container` fell all the
    way through to the generic phrase. `_ownership_only_methods` in
    `installer/ownership.py` now covers those rows on the evidence side, so
    the seam rescues them with a real, inventory-backed attribution and this
    registry-only GUESS is deliberately left as the narrower of the two --
    per this docstring's own rule that it must be NARROWER, not wider.
    """
    for method in resolve_methods(tool, platform):
        if method.kind == "cask":
            name = manager_name(method, "cask", tool.cmd)
            return f"managed by Homebrew — `brew uninstall --cask {name}`"
        if method.kind == "brew":
            name = manager_name(method, "formula", tool.cmd)
            return f"managed by Homebrew — `brew uninstall {name}`"
        if method.kind == "sdkman":
            # No `Owner` value can ever carry "sdkman" (installer/ownership.py
            # task 1's own docstring): no registry row declares
            # `owner_probes = ["sdkman"]`, so `install_ownership._sdkman`
            # never runs and the ownership seam can never produce this
            # phrase itself. This is registry-derived, exactly like the two
            # branches above it -- no probe, no resolver. `_applies` accepts
            # `sdkman` unconditionally, so the platform filter above leaves
            # this branch reachable on every platform.
            candidate = manager_name(method, "candidate", tool.cmd)
            return f"managed by SDKMAN — `sdk uninstall {candidate} <version>`"
    return "managed outside this installer — remove with your package manager"


def _managed_hint(
    tool: Tool,
    which: Callable[[str], str | None],
    platform: Platform,
    owner_hint: OwnerHint | None,
) -> str:
    # The seam's phrase wins when it has one; a tool it cannot attribute (or
    # no seam at all) falls back to the platform-filtered registry guess --
    # per tool, not per call, so one unattributable tool does not degrade the
    # rest. Surfaces where the tool actually resolves on PATH (e.g.
    # /opt/homebrew/bin/rg) so "managed elsewhere" is concrete: the user sees
    # it is a real, brew/system install this installer did not place and
    # should not delete.
    hint = owner_hint(tool) if owner_hint is not None else None
    if hint is None:
        hint = _manager_hint(tool, platform)
    path = which(tool.cmd)
    return f"{hint} — found at {path}" if path else hint


def reverse_dependencies(tools: list[Tool]) -> dict[str, list[str]]:
    """Map each tool id to the ids of tools that declare it in ``requires``.

    Used by the Uninstall view to warn (but allow) when removing a tool others
    depend on — never a cascade or a block. Ids with no dependents are omitted."""
    rev: dict[str, list[str]] = {}
    for tool in tools:
        for dep_id in tool.requires:
            rev.setdefault(dep_id, []).append(tool.id)
    return rev


def classify_tools(
    tools: list[Tool],
    default_bin_dir: Path,
    *,
    installed: dict[str, bool],
    platform: Platform,
    which: Callable[[str], str | None] = shutil.which,
    reverse_deps: dict[str, list[str]] | None = None,
    owner_hint: OwnerHint | None = None,
    owner_label_hint: OwnerLabelHint | None = None,
) -> list[ToolRow]:
    """Classify every tool by removability, one ToolRow per tool in input order.

    Reuses plan_uninstall (userspace artifacts), the installed map, the platform
    resolver, and `which` (to resolve where a managed tool lives) so the Uninstall
    view shows full catalog parity: removable-here vs managed-elsewhere vs
    not-installed vs unavailable.

    When ``reverse_deps`` is provided, any tool that other tools depend on gets a
    "required by …" note appended to its hint — warn-but-allow, no cascade or
    block.

    ``owner_hint``, when given, is consulted ONLY for the managed branch: a
    phrase it returns for a tool wins over the platform-filtered registry
    guess (``_manager_hint``); ``None`` for a tool (or no seam at all) falls
    back to that guess, per tool. Removable, absent and unavailable rows never
    consult it (see ``OwnerHint``'s own docstring for why this stays a plain
    callable rather than an ownership resolver).

    ``owner_label_hint`` is that seam's TERSE counterpart (CR-03), consulted
    under exactly the same managed-only condition and stored on
    ``ToolRow.manager`` for the table CELL, while ``hint`` keeps the full
    sentence for the detail bar. There is no registry-derived fallback for
    it: a row this seam cannot attribute carries ``None`` and the screen
    renders its own generic label, because the registry guess behind
    ``_manager_hint`` is a GUESS and a bare manager name in a cell reads as a
    verified fact."""
    rows: list[ToolRow] = []
    for tool in tools:
        paths = plan_uninstall([tool], default_bin_dir)
        if paths:
            rows.append(
                ToolRow(
                    tool,
                    UninstallState.REMOVABLE,
                    paths,
                    "installed in userspace — removable here",
                    True,
                )
            )
        elif installed.get(tool.id, False):
            rows.append(
                ToolRow(
                    tool,
                    UninstallState.MANAGED,
                    [],
                    _managed_hint(tool, which, platform, owner_hint),
                    False,
                    owner_label_hint(tool) if owner_label_hint is not None else None,
                )
            )
        elif resolve_methods(tool, platform):
            rows.append(ToolRow(tool, UninstallState.ABSENT, [], "not installed", False))
        else:
            rows.append(
                ToolRow(
                    tool, UninstallState.UNAVAILABLE, [], f"not available on {platform.os}", False
                )
            )
    if reverse_deps:
        rows = [
            replace(
                row,
                hint=f"{row.hint} · required by {', '.join(reverse_deps[row.tool.id])}",
            )
            if reverse_deps.get(row.tool.id)
            else row
            for row in rows
        ]
    return rows


def remove_paths(paths: list[Path]) -> None:
    """Delete each path: a symlink is unlinked (target preserved), a dir is removed
    recursively, a file is unlinked."""
    for path in paths:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _omz_policy(zshrc_path: Path, state_path: Path) -> Policy:
    # Per CONTEXT D-04/D-05/D-06: present drives missing_requires, which gates
    # ENABLING the tweak (D-05/D-06); a teardown must never be gated on it,
    # because a machine being uninstalled may have had oh-my-zsh removed already
    # and refusing to undo our own .zshrc edit would strand exactly the stray
    # state this module exists to remove (D-04's symmetric teardown). Removal is
    # total regardless -- omz.remove_plugins no-ops on a missing file or missing
    # array -- so present=True can never raise here.
    #
    # state_path is the managed rc file: the sweep already binds it as rc_path,
    # and it is where the enable path recorded which names it added. Reading it
    # is what keeps the sweep off a .zshrc this installer never edited.
    return omz_plugins_policy(zshrc_path=zshrc_path, state_path=state_path, present=True)


@dataclass(frozen=True)
class SweepResult:
    """What a teardown actually did: the ids it disabled, and the ids it could not.

    The sweep's return value is the only ground truth about its effect. Every
    id a caller could otherwise report comes from a separate, earlier
    `active_tweak_ids` call, which is structurally incapable of reflecting what
    happened — so reporting from anything but this is reporting the preview.
    """

    swept: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()


def active_policies(
    bundles: tuple[TweakBundle, ...],
    *,
    rc_path: Path,
    bin_dir: Path,
    zshrc_path: Path | None = None,
    daemon_policy: Policy | None = None,
) -> list[Policy]:
    """Every policy whose footprint is still on this machine, built exactly once.

    Public because a caller that previews and then sweeps must hold ONE list
    across both: `active_tweak_ids` reads the ids off these objects and
    `sweep_policies` calls remove on the very same ones, so nothing between the
    two reads can change what the second sees. `run_uninstall` needs that — it
    deletes paths, strips the managed block and removes shims and alias blocks
    between its preview and its sweep, all from the same rc file and bin dir the
    predicate below reads.

    `daemon_policy`, when given, is appended last when it is currently active
    -- evaluated as `daemon_policy.is_active() if daemon_policy.is_active is
    not None else daemon_policy.active` (11-REVIEWS.md cycle 2 finding #13),
    NEVER the frozen `.active` field alone: `daemon_policy` is a frozen
    dataclass instance shared with the Policies list and the on-by-default
    worker, which may enable it on a separate thread AFTER construction --
    reading `is_active()` re-probes the real, current state instead of
    trusting a stale construction-time snapshot. Every other policy kind is
    unaffected (`is_active` is `None` for all of them, so the `.active`
    fallback runs, unchanged from today).
    """
    policies: list[Policy] = []
    for bundle in bundles:
        if tweak_present(bundle, rc_path) or tweak_executables_present(bundle, bin_dir):
            policies.append(tweak_policy(bundle, rc_path=rc_path, bin_dir=bin_dir))
    if zshrc_path is not None:
        policy = _omz_policy(zshrc_path, rc_path)
        if policy.active:
            policies.append(policy)
    if daemon_policy is not None:
        is_active = (
            daemon_policy.is_active()
            if daemon_policy.is_active is not None
            else daemon_policy.active
        )
        if is_active:
            policies.append(daemon_policy)
    return policies


def active_tweak_ids(
    bundles: tuple[TweakBundle, ...],
    *,
    rc_path: Path,
    bin_dir: Path,
    zshrc_path: Path | None = None,
    daemon_policy: Policy | None = None,
) -> tuple[str, ...]:
    """Ids of tweaks still present on this machine.

    A tweak is active when its rc block is present OR an owned helper
    executable is on disk. The block alone misses a helper left behind after a
    hand-edited rc file (the REQ's literal orphaned-executable case), and the
    helper alone misses every bundle that has none. This is a read-only
    predicate: it opens files but writes none.

    Every arm answers "is this ours", never "does this exist". The helper arm
    proves it with tweaks._is_our_executable's sentinel; the Oh-My-Zsh arm with
    the record the enable path wrote into rc_path. Neither reads mere presence,
    because .zshrc's plugins=(...) array and a same-named file in bin_dir are
    both things a user can have without this installer ever running.

    The ids are Policy ids, never raw TweakBundle ids: `tweak_policy` namespaces
    a bundle as `tweak:<id>` precisely so it cannot collide with the ban or with
    another policy, and returning the bare id would both throw that away — the
    Policies view would list `tweak:docker` while the Uninstall row said
    `docker` — and let a future bundle named `omz-plugins` make the two arms
    below fire off one another's entry in a flat set.

    The None default on zshrc_path/daemon_policy exists for unit tests and any
    caller working only with bundles; production callers MUST pass the real
    values, because omitting them silently narrows the sweep and leaves the
    Oh-My-Zsh plugins=(...) edit / an active daemon registration on the
    machine with nothing reporting it.
    """
    return tuple(
        policy.id
        for policy in active_policies(
            bundles,
            rc_path=rc_path,
            bin_dir=bin_dir,
            zshrc_path=zshrc_path,
            daemon_policy=daemon_policy,
        )
    )


def sweep_policies(policies: list[Policy]) -> SweepResult:
    """Disable exactly these policies, via Policy.remove.

    This is D-04's symmetric teardown: it writes no removal logic of its own,
    it calls the exact same Policy.remove closures the Policies view calls when
    the user toggles a tweak off, so "full uninstall" and "toggle off" are the
    same operation by construction.

    It takes the list rather than re-deriving it so a caller that previewed from
    `active_policies` can hand over the very objects it showed the user. That is
    what makes "the preview and its effect cannot diverge" a property of the
    code rather than a claim about it: no read happens between the two.

    Failures are isolated per policy. A read-only ~/.local/bin, an
    immutable-flagged rc file or an EACCES on an unlink raises OSError, and a
    real `launchctl` failure from the daemon's own `.remove()` raises
    CommandError (11-02's transactional design) -- letting either propagate
    would abandon every later bundle and the .zshrc arm after it, leaving a
    half-torn-down machine with no record of what had already gone. Each
    failure is collected and the sweep continues, so the caller can name what
    did not come off.
    """
    swept: list[str] = []
    failed: list[str] = []
    for policy in policies:
        try:
            policy.remove()
        except (OSError, CommandError):
            failed.append(policy.id)
        else:
            swept.append(policy.id)
    return SweepResult(swept=tuple(swept), failed=tuple(failed))


def sweep_tweaks(
    bundles: tuple[TweakBundle, ...],
    *,
    rc_path: Path,
    bin_dir: Path,
    zshrc_path: Path | None = None,
    daemon_policy: Policy | None = None,
) -> SweepResult:
    """Read what is active right now and disable it: `active_policies` + `sweep_policies`.

    The convenience form for a caller with nothing to do between the read and
    the sweep. `run_uninstall` is not such a caller and must not use it — it
    deletes user artifacts in between — so it holds the list itself and calls
    the two halves directly.

    Idempotent: a second call finds nothing active and reports nothing.

    The None default on zshrc_path/daemon_policy exists for unit tests and any
    caller working only with bundles; production callers MUST pass the real
    values, because omitting them silently narrows the sweep and leaves the
    Oh-My-Zsh plugins=(...) edit / an active daemon registration on the
    machine with nothing reporting it.
    """
    return sweep_policies(
        active_policies(
            bundles,
            rc_path=rc_path,
            bin_dir=bin_dir,
            zshrc_path=zshrc_path,
            daemon_policy=daemon_policy,
        )
    )
