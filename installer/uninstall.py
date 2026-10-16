"""Registry-driven uninstall: remove the userspace artifacts install_download
and install_app create, and — for a full uninstall — perform the symmetric
teardown of every still-enabled shell tweak, reusing the same policy remove
path the Policies view uses (CONTEXT D-04). Cask/brew/native-managed artifacts
are left alone."""

import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from installer import receipts
from installer.download import DOWNLOAD_KINDS, artifact_paths, is_still_proven
from installer.enums import UninstallState
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


def plan_uninstall(tools: list[Tool], default_bin_dir: Path) -> list[Path]:
    """Existing artifacts the download/raw/app executors would have created.

    The paths come from `download.artifact_paths` (D-07) — the same formula
    install uses for placement, so removal never computes paths separately
    from install. Only paths that currently exist (including dangling
    symlinks) are returned, in a stable de-duplicated order.
    """
    found: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path not in seen and _exists(path):
            seen.add(path)
            found.append(path)

    for tool in tools:
        for method in tool.methods:
            for artifact in artifact_paths(method, default_bin_dir):
                add(artifact.path)
    return found


@dataclass(frozen=True)
class RemovalPlan:
    """The strict split of a tool set's on-disk matches (CONTEXT D-04).

    `removable` holds only proven artifacts: receipt artifacts the registry
    formula agrees on (D-10), or — for a tool with no receipt file — a bin
    link that is a symlink resolving to a regular file inside the same tool's
    opt dir, plus that opt dir. `artifacts` carries the authorized artifact of
    every path in `removable`, so the type that proved a path travels with it
    to the delete instead of being rediscovered from the live path (G1).
    Everything else `plan_uninstall` still matches by name — uv/pip files,
    foreign symlinks, shared files, app bundles — lands in `yourself`: listed
    for the user, never deleted by this installer. `by_tool` maps a tool id
    to its receipt-proven paths, so the remover retires a receipt only once
    all of them are gone.
    """

    removable: tuple[Path, ...]
    yourself: tuple[Path, ...]
    by_tool: Mapping[str, tuple[Path, ...]] = field(default_factory=dict[str, tuple[Path, ...]])
    artifacts: Mapping[Path, receipts.ReceiptArtifact] = field(
        default_factory=dict[Path, receipts.ReceiptArtifact]
    )


def _receipt_proof(
    tool: Tool, default_bin_dir: Path, *, verify: bool
) -> tuple[receipts.ReceiptArtifact, ...]:
    """The artifacts a tool's receipt proves: receipt ∩ `artifact_paths` (L-19-06).

    The receipt is user-writable JSON, so it is never the authority on its
    own: only an artifact whose (path, type) PAIR the registry formula names
    for one of the tool's methods of the receipt's kind is proven (19-RESEARCH
    Pitfall 8; the pair, not the path, so a receipt cannot retype a raw file
    into a recursive directory delete, review H6). A corrupt receipt, or any
    drifted artifact — authorized or not (review H7) — proves nothing. The
    proven artifact itself is returned, so the type that authorized a path
    reaches the delete."""
    receipt = receipts.read(tool.id)
    if receipt is None or receipts.drifted(receipt, rehash=verify):
        return ()
    allowed = {
        (artifact.path, artifact.kind)
        for method in tool.methods
        if method.kind == receipt.method.kind
        for artifact in artifact_paths(method, default_bin_dir)
    }
    return tuple(a for a in receipt.artifacts if (a.path, a.type) in allowed)


def plan_removal(tools: list[Tool], default_bin_dir: Path, *, verify: bool = False) -> RemovalPlan:
    """Prove removability by receipt, else by the archive layout; name the rest.

    A tool with a receipt file is proven by that receipt alone (L-19-14); an
    unreadable receipts dir counts as a receipt file (G23). The receipt
    artifacts `artifact_paths` also names, unless the receipt is corrupt or any
    artifact drifted — then nothing, with no layout fallback. `verify=True`
    re-hashes every recorded file (the deletion-time re-proof).

    A tool with no receipt file keeps the archive-layout proof. For each
    download method, the (link, opt dir) pair comes from
    `download.artifact_paths` (D-07) — the same placement install uses. The
    opt dir is keyed by the member the link points to. A
    method is proven when its link is a symlink whose target is a regular
    file inside this tool's own opt_dir(<link name>) — so a uv/pip file at a
    matching name, or a link into another tool's opt dir, is never proven.
    Raw methods have no link artifact and are never layout-proven. Unproven
    matches keep the lenient `plan_uninstall` list as `yourself`.
    """
    removable: list[Path] = []
    seen: set[Path] = set()
    by_tool: dict[str, tuple[Path, ...]] = {}
    artifacts: dict[Path, receipts.ReceiptArtifact] = {}
    for tool in tools:
        if receipts.receipt_exists(tool.id):
            proven = _receipt_proof(tool, default_bin_dir, verify=verify)
            if proven:
                by_tool[tool.id] = tuple(a.path for a in proven)
            for artifact in proven:
                if artifact.path not in seen:
                    seen.add(artifact.path)
                    removable.append(artifact.path)
                    artifacts[artifact.path] = artifact
            continue
        for method in tool.methods:
            if method.kind not in DOWNLOAD_KINDS:
                continue
            method_artifacts = artifact_paths(method, default_bin_dir)
            link = next((a.path for a in method_artifacts if a.kind == "link"), None)
            opt = next((a.path for a in method_artifacts if a.kind == "dir"), None)
            if link is None or opt is None or not is_still_proven(link):
                continue
            proven_link = receipts.fingerprint(link, "link")
            proven_dir = receipts.fingerprint(opt, "dir", key=receipts.link_key(opt, link))
            if proven_link is None or proven_dir is None:
                continue
            for artifact in (proven_link, proven_dir):
                if artifact.path not in seen:
                    seen.add(artifact.path)
                    removable.append(artifact.path)
                    artifacts[artifact.path] = artifact
    yourself = tuple(p for p in plan_uninstall(tools, default_bin_dir) if p not in seen)
    return RemovalPlan(tuple(removable), yourself, by_tool, artifacts)


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
# seam to `VersionRefreshService.state_of` plus `installer.ownership
# .removal_hint`.
OwnerHint = Callable[[Tool], str | None]

# The TERSE half of the same seam (CR-03, 15.4-REVIEW.md), bound in `setup.py`
# to `VersionRefreshService.state_of` plus `installer.ownership
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
            # ownership.py can now attribute SDKMAN by location. This
            # registry-derived phrase remains the fallback when no ownership
            # record is passed.
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

    Uses plan_removal's proof (CONTEXT D-04): a tool is removable only when
    its bin link is a symlink resolving to a regular file inside its own
    opt dir; every other name match is listed as "remove it yourself" and
    the row is inert. The installed map, the platform resolver and `which`
    still resolve where a managed tool lives, so the Uninstall view keeps
    full catalog parity: removable-here vs managed-elsewhere vs not-installed
    vs unavailable.

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
        plan = plan_removal([tool], default_bin_dir)
        if plan.removable:
            hint = "installed in userspace — removable here"
            if plan.yourself:
                hint += f" · remove it yourself: {', '.join(str(p) for p in plan.yourself)}"
            rows.append(ToolRow(tool, UninstallState.REMOVABLE, list(plan.removable), hint, True))
        elif plan.yourself:
            yourself_hint = f"remove it yourself: {', '.join(str(p) for p in plan.yourself)}"
            if installed.get(tool.id, False):
                yourself_hint = (
                    f"{_managed_hint(tool, which, platform, owner_hint)} · {yourself_hint}"
                )
            rows.append(ToolRow(tool, UninstallState.MANAGED, [], yourself_hint, False))
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


def remove_paths(artifacts: Sequence[receipts.ReceiptArtifact]) -> tuple[Path, ...]:
    """Delete each authorized artifact; return the paths it refused.

    The authorized type picks the operation, never what the path is now: only
    a `dir` artifact reaches `rmtree`, and a `file` or `link` is only ever
    unlinked (G1). `receipts.matches` re-checks the artifact right before the
    delete, so a path that changed since the proof is refused and never
    touched. A failed delete still raises, before any receipt is touched.
    """
    refused: list[Path] = []
    for artifact in artifacts:
        if not receipts.matches(artifact):
            refused.append(artifact.path)
            continue
        if artifact.type == "dir":
            shutil.rmtree(artifact.path)
        else:
            artifact.path.unlink()
    return tuple(refused)


def remove_proven(
    tools: list[Tool], paths: list[Path], bin_dir: Path
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    """Delete the previewed `paths` that are still proven now; refuse the rest.

    The one remover for the CLI and the TUI (L-19-06). The preview is not a
    permission slip: the proof is recomputed at deletion time with a re-hash
    of every recorded file (`verify=True`), so bytes swapped in place since
    the preview are refused even with size and mtime restored. The type that
    proved a path travels to its delete, and a path that changed after that
    proof is refused too (G1). A tool's receipt is deleted only after every
    path it proved is gone (D-08); a failed delete raises before any receipt
    is touched. Returns the removed paths and one refusal line per path no
    longer proven."""
    fresh = plan_removal(tools, bin_dir, verify=True)
    proven = set(fresh.removable)
    kept = [path for path in paths if path in proven and path in fresh.artifacts]
    changed = remove_paths([fresh.artifacts[path] for path in kept])
    removed = set(kept) - set(changed)
    refused = tuple(
        f"changed since the preview; not removed: {path}" for path in paths if path not in removed
    )
    for tool_id, tool_paths in fresh.by_tool.items():
        if all(path in removed and not _exists(path) for path in tool_paths):
            receipts.delete(tool_id)
    return tuple(path for path in kept if path in removed), refused


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
    # "<policy id>: <warning>" for every swept policy whose remove() succeeded
    # but still had something to disclose (CR-01: the unreachable-manager
    # case). Dropping these would report a clean teardown that was not one.
    warnings: tuple[str, ...] = ()


def policy_owned(policy: Policy) -> bool:
    """The daemon arm's "is this ours" rule, shared with every extra policy.

    ``owned()`` when the policy binds a footprint predicate (CR-01: the Linux
    timer, whose ``is_active`` answers "is it running", which is the wrong
    question for a teardown), else ``is_active()`` when it binds one, else the
    frozen ``.active`` snapshot. A construction-time snapshot goes stale once
    another thread enables the same object.
    """
    if policy.owned is not None:
        return policy.owned()
    return policy.is_active() if policy.is_active is not None else policy.active


def active_policies(
    bundles: tuple[TweakBundle, ...],
    *,
    rc_path: Path,
    bin_dir: Path,
    zshrc_path: Path | None = None,
    daemon_policy: Policy | None = None,
    extra_policies: tuple[Policy, ...] = (),
) -> list[Policy]:
    """Every policy whose footprint is still on this machine, built exactly once.

    Public because a caller that previews and then sweeps must hold ONE list
    across both: `active_tweak_ids` reads the ids off these objects and
    `sweep_policies` calls remove on the very same ones, so nothing between the
    two reads can change what the second sees. `run_uninstall` needs that — it
    deletes paths, strips the managed block and removes shims and alias blocks
    between its preview and its sweep, all from the same rc file and bin dir the
    predicate below reads.

    `daemon_policy`, when given, is appended last when `policy_owned` says
    its footprint is still here -- its `owned()` footprint predicate when it
    binds one (CR-01), else `is_active()` (11-REVIEWS.md cycle 2 finding #13),
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
    if daemon_policy is not None and policy_owned(daemon_policy):
        policies.append(daemon_policy)
    for extra in extra_policies:
        if policy_owned(extra):
            policies.append(extra)
    return policies


def active_tweak_ids(
    bundles: tuple[TweakBundle, ...],
    *,
    rc_path: Path,
    bin_dir: Path,
    zshrc_path: Path | None = None,
    daemon_policy: Policy | None = None,
    extra_policies: tuple[Policy, ...] = (),
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
            extra_policies=extra_policies,
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
    warnings: list[str] = []
    for policy in policies:
        try:
            result = policy.remove()
        except (OSError, CommandError):
            failed.append(policy.id)
        else:
            swept.append(policy.id)
            if result.warning:
                warnings.append(f"{policy.id}: {result.warning}")
    return SweepResult(swept=tuple(swept), failed=tuple(failed), warnings=tuple(warnings))


def sweep_tweaks(
    bundles: tuple[TweakBundle, ...],
    *,
    rc_path: Path,
    bin_dir: Path,
    zshrc_path: Path | None = None,
    daemon_policy: Policy | None = None,
    extra_policies: tuple[Policy, ...] = (),
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
            extra_policies=extra_policies,
        )
    )
