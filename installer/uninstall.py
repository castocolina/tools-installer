"""Registry-driven uninstall: remove the userspace artifacts install_download
and install_app create, and — for a full uninstall — perform the symmetric
teardown of every still-enabled shell tweak, reusing the same policy remove
path the Policies view uses (CONTEXT D-04). Cask/brew/native-managed artifacts
are left alone."""

import contextlib
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, cast

from installer import receipts
from installer.download import (
    DOWNLOAD_KINDS,
    artifact_paths,
    expand_script_token,
    is_still_proven,
)
from installer.model import HARNESS_MARKER_DIRS, Method, Tool, method_package
from installer.policy import Policy, omz_plugins_policy, tweak_policy
from installer.postinstall import hook_method, unregister_argvs, unregister_hosts
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


RemovalLevel = Literal["manager", "artifacts", "recipe", "none"]


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
    # How the tool is removed (D-06): `manager` (argv = the manager's uninstall for the
    # receipt's package), `recipe` (argv = the vendor `remove`, bound to a proven leaf,
    # or none, plus the proven paths), `artifacts` (proven paths only), or `none`.
    level: RemovalLevel = "none"
    argv: tuple[str, ...] = ()
    # Declared config entries that exist now, expanded; never deleted by this module.
    config: tuple[Path, ...] = ()
    hint: str | None = None
    # D-04: the undo argvs for the hosts the receipt's hook records, first word the proven
    # executable; and those hosts (sorted, filtered through the target map).
    unregister: tuple[tuple[str, ...], ...] = ()
    hook_hosts: tuple[str, ...] = ()


# The argv prefix that uninstalls a package of each manager kind (L1, D-06). The package
# is appended from the receipt, and only when that receipt names a package the tool declares.
MANAGER_UNINSTALL_ARGV: dict[str, tuple[str, ...]] = {
    "brew": ("brew", "uninstall"),
    "cask": ("brew", "uninstall", "--cask"),
    "uv-tool": ("uv", "tool", "uninstall"),
    "node": ("pnpm", "remove", "--global"),
}


def config_targets(tool: Tool) -> tuple[tuple[str, Path], ...]:
    """Each declared config entry as (its `~` form, its expanded path), in declaration order."""
    return tuple((entry, Path(entry).expanduser()) for entry in tool.config_paths)


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


# A removal captures a directory under a unique sibling of its own before
# re-checking and deleting it. Never `.tools-installer.old`, which
# `atomic.recover_update_remnants` would restore over a live path.
_QUARANTINE_SUFFIX = ".tools-installer.rm"


def _quarantined(tools: list[Tool], default_bin_dir: Path) -> list[Path]:
    """Find interrupted-removal siblings beside a tool dir (RR3-02, P3-05).

    List them for the preview, never delete them here (L-19-06: they are in no
    receipt and in no `artifact_paths`).
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for tool in tools:
        for method in tool.methods:
            for artifact in artifact_paths(method, default_bin_dir):
                if artifact.kind not in ("dir", "tree"):
                    continue
                for path in sorted(
                    artifact.path.parent.glob(f".{artifact.path.name}.*{_QUARANTINE_SUFFIX}")
                ):
                    if path not in seen:
                        seen.add(path)
                        found.append(path)
    return found


def plan_removal(tools: list[Tool], default_bin_dir: Path, *, verify: bool = False) -> RemovalPlan:
    """Prove removability by receipt, else by the archive layout; name the rest.

    A tool with a receipt file is proven by that receipt alone (L-19-14); an
    unreadable receipts dir counts as a receipt file (G23). The receipt
    artifacts `artifact_paths` also names, unless the receipt is corrupt or any
    artifact drifted — then nothing, with no layout fallback. `verify=True`
    re-hashes every recorded file and the layout key file (the deletion-time
    re-proof).

    A tool with no receipt file keeps the archive-layout proof. For each
    download method, the (link, opt dir) pair comes from
    `download.artifact_paths` (D-07) — the same placement install uses. The
    opt dir is keyed by the member the link points to. A
    method is proven when its link is a symlink whose target is a regular
    file inside this tool's own opt_dir(<link name>) — so a uv/pip file at a
    matching name, or a link into another tool's opt dir, is never proven.
    Raw methods have no link artifact and are never layout-proven. Unproven
    matches and quarantine siblings left by an interrupted removal are listed
    as `yourself`. Discovery costs one small-directory glob per dir artifact.
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
            proven_dir = receipts.fingerprint(
                opt, "dir", key=receipts.link_key(opt, link), rehash=verify
            )
            if proven_link is None or proven_dir is None:
                continue
            for artifact in (proven_link, proven_dir):
                if artifact.path not in seen:
                    seen.add(artifact.path)
                    removable.append(artifact.path)
                    artifacts[artifact.path] = artifact
    yourself = tuple(
        p
        for p in (*plan_uninstall(tools, default_bin_dir), *_quarantined(tools, default_bin_dir))
        if p not in seen
    )
    return RemovalPlan(tuple(removable), yourself, by_tool, artifacts)


def _manager_argv(tool: Tool, receipt: receipts.Receipt | None) -> tuple[str, ...]:
    """L1: the manager's uninstall, only for a package this receipt names and the tool declares."""
    if receipt is None or receipt.method.kind not in MANAGER_UNINSTALL_ARGV or not receipt.package:
        return ()
    declared = any(
        method.kind == receipt.method.kind and method_package(method) == receipt.package
        for method in tool.methods
    )
    if not declared:
        return ()
    return (*MANAGER_UNINSTALL_ARGV[receipt.method.kind], receipt.package)


def _recipe_argv(
    tool: Tool, receipt: receipts.Receipt | None, plan: RemovalPlan
) -> tuple[str, ...]:
    """L3: the vendor `remove`, its first word bound to a receipt-proven leaf (R2-03).

    shortcut: no registry method declares `remove` today (opencode's was dropped, UI-SPEC
    amendment 2026-11-04), so only test-local recipes reach this; kept by that recorded
    decision (review PT-04), delete it if no vendor ships a safe uninstall.

    Needs a script receipt that proves at least one artifact (an empty legacy receipt
    never authorizes the vendor command, R1-08). The first word must name a proven leaf,
    by its absolute path or by a bare name only one leaf has; it is then replaced by that
    leaf's absolute path, so no PATH copy ever runs."""
    if receipt is None or receipt.method.kind != "script" or not plan.by_tool.get(tool.id):
        return ()
    method = hook_method(tool, receipt)
    remove = method.params.get("remove") if method is not None else None
    if not isinstance(remove, list) or not remove:
        return ()
    words: list[str] = []
    for token in cast(list[object], remove):
        expanded = expand_script_token(str(token))
        if expanded is None:
            return ()
        words.append(expanded)
    head, *rest = words
    leaf = _proven_named(plan, tool.id, head, ("leaf",))
    if leaf is None:
        return ()
    return (str(leaf.path), *rest)


def _proven_named(
    plan: RemovalPlan, tool_id: str, name: str, types: tuple[str, ...]
) -> receipts.ReceiptArtifact | None:
    """The one receipt-proven artifact of `tool_id` with this name (a bare name or an absolute
    path) and one of these types. A name two artifacts share proves neither: None."""
    matches = [
        artifact
        for path in plan.by_tool.get(tool_id, ())
        if (artifact := plan.artifacts[path]).type in types
        and name in (artifact.path.name, str(artifact.path))
    ]
    return matches[0] if len(matches) == 1 else None


def _hook_undo(
    tool: Tool, receipt: receipts.Receipt | None, base: RemovalPlan
) -> tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]:
    """D-04: the undo for the hosts `receipt.hooks[tool.postinstall]` records, run by the
    receipt-proven executable (the one proven artifact named `tool.cmd`), else nothing.
    Hosts come from the receipt alone, never from the hosts present now."""
    name = tool.postinstall
    if receipt is None or name is None or not receipt.hooks.get(name):
        # shortcut: a receipt written before hooks were recorded holds hooks={} (review R1-39),
        # so its removal unregisters nothing; 23-07's RECONFIGURE records those hosts first.
        return (), ()
    executable = _proven_named(base, tool.id, tool.cmd, ("link", "leaf", "file"))
    if executable is None:
        # shortcut: no proven executable means no unregister, also when a vendor self-upgrade
        # moved the binary (codegraph upgrade into ~/.codegraph/versions, R1-40); upgrade when
        # the receipt learns that moved path.
        return (), ()
    recorded = tuple(receipt.hooks[name])
    return (
        unregister_argvs(name, str(executable.path), recorded),
        tuple(sorted(unregister_hosts(name, recorded))),
    )


def removal_plan(
    tool: Tool, default_bin_dir: Path, *, verify: bool = False, hint: str | None = None
) -> RemovalPlan:
    """The one per-tool removal decision: its level, its argv, and what it proves (D-06).

    Built on `plan_removal`, so every path still comes from receipt proof or the archive
    layout. A manager argv needs this installer's own receipt to name a package the tool
    declares; a recipe argv needs a script receipt with a proven artifact. Everything else
    is `artifacts` (proven paths) or `none` (nothing to remove, hint only). `verify=True`
    re-hashes what the proof rests on, which is the post-confirm re-plan."""
    base = plan_removal([tool], default_bin_dir, verify=verify)
    receipt = receipts.read(tool.id)
    config = tuple(path for _entry, path in config_targets(tool) if _exists(path))
    manager = _manager_argv(tool, receipt)
    recipe = () if manager else _recipe_argv(tool, receipt, base)
    level: RemovalLevel = "none"
    if manager:
        level = "manager"
    elif base.removable and receipt is not None and receipt.method.kind == "script":
        level = "recipe"
    elif base.removable:
        level = "artifacts"
    unregister, hook_hosts = _hook_undo(tool, receipt, base)
    return replace(
        base,
        level=level,
        argv=manager or recipe,
        config=config,
        hint=hint,
        unregister=unregister,
        hook_hosts=hook_hosts,
    )


def manager_name(method: Method, param: str, fallback: str) -> str:
    # brew/cask uninstall takes the formula/cask name (in the method params),
    # NOT the runnable cmd — they differ for e.g. rg/ripgrep, code/visual-studio-code.
    value = method.params.get(param)
    return value if isinstance(value, str) and value else fallback


def reverse_dependencies(tools: list[Tool]) -> dict[str, list[str]]:
    """Map each tool id to the ids of tools that declare it in ``requires``.

    Used by the Uninstall view to warn (but allow) when removing a tool others
    depend on — never a cascade or a block. Ids with no dependents are omitted."""
    rev: dict[str, list[str]] = {}
    for tool in tools:
        for dep_id in tool.requires:
            rev.setdefault(dep_id, []).append(tool.id)
    return rev


def _put_back(quarantine: Path, path: Path) -> None:
    """Rename the captured tree back to `path`, or say exactly where it is.

    Nothing is deleted when the put-back fails: the tree stays at the
    quarantine path and the error names both paths (T-19-109)."""
    try:
        os.rename(quarantine, path)
    except OSError as exc:
        raise OSError(f"{path} changed during removal; it is kept at {quarantine}") from exc


def _remove_dir(artifact: receipts.ReceiptArtifact) -> bool:
    """Capture `artifact`'s directory by an exclusive rename, re-verify it, delete it.

    RR-01: the tree that is deleted is the tree that was verified. Checking the
    proof and then calling `rmtree` on the *name* would delete whatever a
    vendor updater swapped in between, so the directory is first renamed to a
    unique quarantine sibling created exclusively under the same parent (the
    rename never crosses a filesystem and never follows a planted link), the
    key file is re-hashed inside the captured tree, and only then is that tree
    deleted. A captured tree that no longer matches is renamed back untouched
    and the artifact is refused; an interruption after the capture puts the
    tree back too; only a kill can leave the quarantine sibling behind.
    """
    quarantine = Path(
        tempfile.mkdtemp(
            prefix=f".{artifact.path.name}.",
            suffix=_QUARANTINE_SUFFIX,
            dir=artifact.path.parent,
        )
    )
    try:
        os.rename(artifact.path, quarantine)
    except OSError:
        with contextlib.suppress(OSError):
            quarantine.rmdir()
        raise
    try:
        verified = receipts.matches(replace(artifact, path=quarantine), rehash=True)
        if verified:
            shutil.rmtree(quarantine)
    except BaseException:
        # Catchable cancellation (Ctrl+C, SystemExit) and a failed delete alike
        # put the remainder back before the exception leaves; SIGKILL leaves a
        # sibling, which plan_removal lists (RR3-02).
        interruption = sys.exception()
        try:
            _put_back(quarantine, artifact.path)
        except OSError as put_back_error:
            put_back_error.__context__ = interruption
            raise put_back_error from None
        raise
    if not verified:
        _put_back(quarantine, artifact.path)
        return False
    return True


def remove_paths(
    artifacts: Sequence[receipts.ReceiptArtifact], *, trees: Sequence[Path] | None = None
) -> tuple[Path, ...]:
    """Delete each authorized artifact; return the paths it refused.

    The authorized type picks the operation, never what the path is now: a
    `dir` or `tree` is removed recursively, and only after it has been captured
    under a quarantine sibling and re-verified there (RR-01); a `file`, `link`
    or `leaf` is only ever unlinked (G1). `trees` names the receipt's trees a
    leaf link may resolve into; None means the `tree` paths among `artifacts`.
    `receipts.matches` re-checks the artifact right before the delete and
    re-hashes files; a dir is re-hashed inside its quarantine. A path that
    changed since the proof is refused and never touched (RR-02). A failed
    delete still raises, before any receipt is touched.
    """
    tree_paths = (
        tuple(a.path for a in artifacts if a.type == "tree") if trees is None else tuple(trees)
    )
    refused: list[Path] = []
    for artifact in artifacts:
        # A dir's authoritative re-hash is inside the quarantine (RR-01); here it
        # only has to remain a real directory whose key file stat-matches, so the
        # rename cannot land on a non-dir. A file keeps its RR-02 re-hash.
        if not receipts.matches(artifact, rehash=artifact.type != "dir", trees=tree_paths):
            refused.append(artifact.path)
            continue
        if artifact.type in ("dir", "tree"):
            if not _remove_dir(artifact):
                refused.append(artifact.path)
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
    # Both plan_removal branches put every removable path into artifacts.
    kept = [path for path in paths if path in fresh.artifacts]
    changed = remove_paths([fresh.artifacts[path] for path in kept])
    removed = set(kept) - set(changed)
    refused = tuple(
        f"changed since the preview; not removed: {path}" for path in paths if path not in removed
    )
    for tool_id, tool_paths in fresh.by_tool.items():
        if all(path in removed and not _exists(path) for path in tool_paths):
            receipts.delete(tool_id)
    return tuple(path for path in kept if path in removed), refused


def delete_config_path(path: Path) -> None:
    """Delete one declared config path, or refuse (SPEC R6, review R1-17 and R2-06).

    The parent is resolved first: it must stay inside the real HOME and must not be, or lie
    under, a harness marker dir, so a symlinked `~/.config` cannot route a delete into one.
    A missing path is a no-op. A link is unlinked and never followed. A real file or directory
    is refused when a harness marker resolves to it or under it (a dotfiles layout that points
    a harness dir at a config dir). Other OSErrors propagate; the caller turns them into a
    warning."""
    real_home = Path(os.path.realpath(Path.home()))
    markers = tuple(
        Path(os.path.realpath(Path.home() / marker))
        for group in HARNESS_MARKER_DIRS.values()
        for marker in group
    )
    parent = Path(os.path.realpath(path.parent))
    if not parent.is_relative_to(real_home) or any(
        parent.is_relative_to(marker) for marker in markers
    ):
        raise OSError(
            f"a parent of {path} resolves outside HOME or into a harness directory; not deleted"
        )
    if not _exists(path):
        return
    if path.is_symlink():
        path.unlink()
        return
    target = Path(os.path.realpath(path))
    if any(marker.is_relative_to(target) for marker in markers):
        raise OSError(f"{path} is or holds a harness directory; not deleted")
    if path.is_dir():
        shutil.rmtree(path)
    else:
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
    # "<policy id>: <warning>" for every swept policy whose remove() succeeded
    # but still had something to disclose (CR-01: the unreachable-manager
    # case). Dropping these would report a clean teardown that was not one.
    warnings: tuple[str, ...] = ()
    # Ids of the tools whose every previewed path was removed.
    removed: tuple[str, ...] = ()
    # (tool id, first line) of each tool that was refused or whose delete raised.
    remove_failed: tuple[tuple[str, str], ...] = ()
    # Tool ids whose listed config was deleted, or was already gone (D-07 step 4).
    config_deleted: tuple[str, ...] = ()
    # Tool ids that asked for their config to go, but whose removal failed (SPEC R6).
    config_not_deleted: tuple[str, ...] = ()
    # "<id>: removed with the <group> group" for each unselected pnpm group member whose
    # receipt the run retired because pnpm took it along (22-UAT F-2).
    with_group: tuple[str, ...] = ()


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
