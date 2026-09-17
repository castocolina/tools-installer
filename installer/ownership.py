"""Which manager actually owns an installed tool.

`installer/resolve.py::resolve_methods` answers "which methods could install
this here, best first" and its ordering is the `_RANK` install-preference
ladder. This module answers a different question: which manager actually owns
the installed copy. The two must never be conflated, because a tool such as
`rg` declares `github_release` (rank 20) and `brew` (rank 40) and a
brew-installed copy would otherwise be treated as a GitHub download.

`dnf`, `apt`, `pacman`, and `rpm_ostree` are valid `METHOD_KINDS`. Phase 12 left
them out of scope: a tool installed through a Linux system package manager
resolved to `owner="unknown"` by design. Phase 15 (D-05) closes that gap with
an ADAPTER, not a native probe: `_native_owner` below calls
`install_ownership.detect_owner` -- which already has working `apt`/`dnf`/
`pacman`/`rpm-ostree` probes of its own -- and maps its `"verified"`
confidence to this module's `"direct"`. The claim is still refused by the
update action for these four managers specifically (`installer/update.py`'s
`NATIVE_OWNERS` refusal branch), because mutating a system package needs
privilege escalation this installer has never required; only ATTRIBUTION
correctness is in scope here.

Ownership feeds a mutating action that runs with no confirmation, so a claim
is only made on an active-path match or on complete negative evidence, and
everything else is `unknown`. This installer will not mutate a tool it cannot
prove it owns, and every branch that is not a proof produces `unknown`. A
live, unattributable active path is checked and can force `unknown` BEFORE
the by-elimination branch is ever reached, so by-elimination can never
override contradictory live-PATH evidence. `_native_owner` is the one branch
that runs ABOVE that check -- it has to, or it would never fire on a real
machine -- so it enforces the same rule itself, by asking the claimed manager
whether its package owns the live binary before making a claim.
The concrete failure this prevents
is a stale artifact this installer left in `~/.local/bin` months ago, a brew
inventory that could not be read this pass, and a live `/opt/homebrew/bin/<cmd>`,
which the previous design would have resolved as installer-owned and then
overwritten. `MUTATION_GRADE` is the single place the permitted confidence
values are listed, so Plan 12-03 imports the rule rather than restating it.

`pnpm_global_packages` returns names only, so a pnpm-owned tool absent from
the outdated report has no manager-reported current version and falls back
to the local probe. That fallback is sound because of the evidence rule
above — a pnpm candidate only becomes the owner when the pnpm shim is the
live binary or when every competitor was cleared — so the probe reads the
copy pnpm actually placed. Writing a second pnpm list parser to recover
versions is explicitly rejected: `.claude/architecture.md` rule 5 forbids
the duplicate.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from installer.apps import APP_KINDS
from installer.download import DOWNLOAD_KINDS
from installer.install_ownership import (
    ProbeRunner,
    detect_owner,
    package_owns_path,
    path_owner_package,
)
from installer.locations import applications_dir, opt_dir
from installer.model import Method, Tool
from installer.platform import Platform
from installer.pnpm_globals import pnpm_global_packages
from installer.resolve import resolve_methods
from installer.run import CommandError, run_query
from installer.status import is_installed
from installer.uninstall import manager_name

Owner = Literal[
    "installer",
    "brew",
    "cask",
    "pnpm",
    "uv",
    "unknown",
    "dnf",
    "apt",
    "pacman",
    "rpm-ostree",
    "os-package",
]
Confidence = Literal["direct", "by-elimination", "none"]

MUTATION_GRADE: frozenset[str] = frozenset({"direct", "by-elimination"})
_NATIVE_PACKAGE_MANAGER_KINDS = frozenset({"dnf", "apt", "pacman"})

# D-05: the four OS package managers `install_ownership.detect_owner` can verify
# ownership for. Declared once here and consumed by both this module's adapter
# translation table AND installer/update.py's refusal condition, so the set of
# owners the catalog can attribute and the set the update path refuses cannot
# drift apart -- a fifth name added later is refused automatically.
#
# 15.4-01/D-01: the shared-set invariant now has TWO members, not one.
# NATIVE_OWNERS stays exactly the four managers `detect_owner` can verify
# membership for (its own probes, above); UNMANAGEABLE_OWNERS (below) is the
# wider set installer/update.py actually refuses, which also carries the new
# `os-package` value -- a base-image tool no tracked manager claims, attributed
# by `_os_package_owner` below rather than by `detect_owner`. Both are declared
# exactly once so attribution and refusal still cannot drift apart.
NATIVE_OWNERS: tuple[Owner, ...] = ("dnf", "apt", "pacman", "rpm-ostree")
# 15.4-01/D-01: the OS-package owner -- a live binary the package database
# attributes to a real package name no tracked manager (installer/brew/cask/
# pnpm/uv) or native probe (dnf/apt/pacman/rpm-ostree) claims. Declared as its
# own name, not folded into NATIVE_OWNERS, because it is discovered by the
# INVERSE query `install_ownership.path_owner_package` (no declared candidate)
# rather than by `detect_owner`'s CONFIRM-a-candidate probes.
OS_PACKAGE_OWNER: Owner = "os-package"
# The set installer/update.py's refusal branch actually reads: attribution
# correctness is in scope for every member of this set, but mutating any of
# them needs privilege escalation (native) or is simply not a package this
# installer's own artifact tracking owns (os-package) -- this installer has
# never required either, so every member here is refused outright.
UNMANAGEABLE_OWNERS: frozenset[Owner] = frozenset({*NATIVE_OWNERS, OS_PACKAGE_OWNER})
# install_ownership.Ownership.manager happens to spell these four identically
# to the Owner values above, but the annotation is written out explicitly
# (rather than inferred from a comprehension over NATIVE_OWNERS) because a
# comprehension would infer dict[Owner, Owner], which pyright --strict
# rejects where a dict[str, Owner] is required for the Ownership.manager
# (str | None) lookup below.
_NATIVE_OWNER_TRANSLATION: dict[str, Owner] = {name: name for name in NATIVE_OWNERS}

_UV_NAME_VERSION = re.compile(r"^(\S+) v(\S+)$")
_UV_NO_TOOLS = "no tools installed"
_BREW_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+@-]*$")
_BREW_VERSION_RE = re.compile(r"^(?:latest|[0-9][A-Za-z0-9.+_,-]*)$")
_BREW_ENV = {"HOMEBREW_NO_AUTO_UPDATE": "1", "HOMEBREW_NO_ENV_HINTS": "1"}
_PNPM_DEFAULTS: dict[str, str] = {
    "macos": "~/Library/pnpm",
    "debian": "~/.local/share/pnpm",
    "arch": "~/.local/share/pnpm",
    "fedora": "~/.local/share/pnpm",
    "linux": "~/.local/share/pnpm",
}
_KIND_TO_OWNER: dict[str, Owner] = {
    "brew": "brew",
    "cask": "cask",
    "node": "pnpm",
    "uv-tool": "uv",
}
_INSTALLER_KINDS = frozenset((*DOWNLOAD_KINDS, *APP_KINDS, "script"))
_CANDIDATE_ORDER: tuple[Owner, ...] = ("installer", "brew", "cask", "pnpm", "uv")


@dataclass(frozen=True)
class ManagerInventory:
    brew_formulae: Mapping[str, str] | None
    brew_casks: Mapping[str, str] | None
    pnpm_globals: frozenset[str] | None
    uv_tools: Mapping[str, str] | None
    brew_prefix: Path | None


@dataclass(frozen=True)
class OwnershipCandidate:
    owner: Owner
    method: Method | None
    package: str | None
    current_version: str | None
    evidence: str


@dataclass(frozen=True)
class ManagerOwnership:
    tool_id: str
    owner: Owner
    method: Method | None
    package: str | None
    current_version: str | None
    confidence: Confidence
    shadowed: bool
    candidates: tuple[OwnershipCandidate, ...]
    active_candidate: Owner | None
    active_path: Path | None
    unknown_reason: str | None


def parse_brew_list_versions(raw: str) -> dict[str, str] | None:
    """Parse `brew list --versions` output; None when any line is unrecognized.

    Empty input is `{}` (asked, found nothing), distinct from `None`. A line
    with 2+ tokens is not enough evidence on its own — a warning or notice
    line (e.g. "warning: inventory format changed") also splits into 2+
    tokens and must not be read as `{name: version}`. The first token must
    look like a real formula/cask name (no colon or other stray punctuation)
    and every remaining token must look like a real version string (starts
    with a digit, or the literal `latest`); anything else fails the WHOLE
    parse closed rather than skipping just that line.
    """
    mapping: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        tokens = stripped.split()
        if len(tokens) < 2:
            return None
        name, *versions = tokens
        if not _BREW_NAME_RE.fullmatch(name):
            return None
        if not all(_BREW_VERSION_RE.fullmatch(version) for version in versions):
            return None
        mapping[name] = versions[-1]
    return mapping


def parse_uv_tool_list(raw: str) -> dict[str, str] | None:
    """Parse `uv tool list` output; None when any unrecognized line appears.

    Empty or all-whitespace input is `{}`. An indented entry-point line or a
    `- name` line is only ever valid immediately after a matched `name vX.Y`
    line — one appearing anywhere else (no preceding match to belong to) is
    unrecognized structure, not benign noise, and fails the whole parse
    closed. uv's own no-tools-installed notice is recognized only when it is
    the first content line.
    """
    mapping: dict[str, str] = {}
    expect_entrypoint = False
    for line in raw.splitlines():
        if not line.strip():
            continue
        stripped = line.strip()
        if not mapping and not expect_entrypoint and _UV_NO_TOOLS in stripped.lower():
            return {}
        if line[:1].isspace() or stripped.startswith("- "):
            if not expect_entrypoint:
                return None
            continue
        match = _UV_NAME_VERSION.fullmatch(stripped)
        if match is None:
            return None
        mapping[match.group(1)] = match.group(2)
        expect_entrypoint = True
    return mapping


def read_inventory(
    *,
    has_brew: bool,
    query: Callable[..., str] = run_query,
    pnpm_packages: Callable[[], tuple[str, ...] | None] = pnpm_global_packages,
) -> ManagerInventory:
    """Ask each manager once. A failed or unparseable query is `None`, never empty."""
    brew_prefix: Path | None = None
    brew_formulae: dict[str, str] | None = None
    brew_casks: dict[str, str] | None = None
    if has_brew:
        brew_prefix = _query_brew_prefix(query)
        brew_formulae = _query_brew_list(query, "--formula")
        brew_casks = _query_brew_list(query, "--cask")
    pnpm_raw = pnpm_packages()
    pnpm_globals = None if pnpm_raw is None else frozenset(pnpm_raw)
    uv_tools = _query_uv_tools(query)
    return ManagerInventory(
        brew_formulae=brew_formulae,
        brew_casks=brew_casks,
        pnpm_globals=pnpm_globals,
        uv_tools=uv_tools,
        brew_prefix=brew_prefix,
    )


def _query_brew_prefix(query: Callable[..., str]) -> Path | None:
    try:
        raw = query(["brew", "--prefix"], env=_BREW_ENV)
    except (CommandError, OSError):
        return None
    text = raw.strip()
    return Path(text) if text else None


def _query_brew_list(query: Callable[..., str], flag: str) -> dict[str, str] | None:
    try:
        raw = query(["brew", "list", "--versions", flag], env=_BREW_ENV)
    except (CommandError, OSError):
        return None
    return parse_brew_list_versions(raw)


def _query_uv_tools(query: Callable[..., str]) -> dict[str, str] | None:
    try:
        raw = query(["uv", "tool", "list"])
    except (CommandError, OSError):
        return None
    return parse_uv_tool_list(raw)


def owner_dirs(
    *,
    inventory: ManagerInventory,
    managed_bin_dir: Path,
    platform: Platform,
) -> dict[Owner, tuple[Path, ...]]:
    """Directory-membership attribution per candidate owner.

    `applications_dir()` (`~/Applications`) is deliberately listed for BOTH
    "installer" and "cask": Homebrew installs casks there too
    (`installer/executors.py`'s cask executor), so a bundle under it is not
    proof of installer ownership on its own. Listing it for both owners makes
    `attribute_path` return `{"installer", "cask"}` for any path under it,
    which — when both an installer-artifact candidate and a cask-inventory
    candidate exist for the same tool — makes `resolve_ownership`'s
    single-candidate-wins branch see two matching candidates instead of one
    and fall through to `unknown` rather than picking one arbitrarily. A tool
    genuinely owned by only one of the two still resolves `direct`, because
    only that one owner appears among `candidates` in the first place.
    """
    installer_dirs = (managed_bin_dir, opt_dir("x").parent, applications_dir())
    brew_dirs: tuple[Path, ...] = ()
    if inventory.brew_prefix is not None:
        brew_dirs = (inventory.brew_prefix,)
    cask_dirs = (*brew_dirs, applications_dir())
    pnpm_home = os.environ.get("PNPM_HOME")
    if pnpm_home:
        pnpm_dir = Path(pnpm_home).expanduser()
    else:
        declared = _PNPM_DEFAULTS.get(platform.os, "~/.local/share/pnpm")
        pnpm_dir = Path(declared).expanduser()
    uv_bin = os.environ.get("UV_TOOL_BIN_DIR")
    uv_dir = Path(uv_bin).expanduser() if uv_bin else Path.home() / ".local" / "bin"
    return {
        "installer": installer_dirs,
        "brew": brew_dirs,
        "cask": cask_dirs,
        "pnpm": (pnpm_dir,),
        "uv": (uv_dir,),
    }


def attribute_path(path: Path | None, dirs: Mapping[Owner, tuple[Path, ...]]) -> frozenset[Owner]:
    if path is None:
        return frozenset()
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    owners: set[Owner] = set()
    for owner, prefixes in dirs.items():
        for prefix in prefixes:
            try:
                prefix_resolved = prefix.resolve()
            except OSError:
                prefix_resolved = prefix
            if resolved == prefix_resolved or prefix_resolved in resolved.parents:
                owners.add(owner)
    return frozenset(owners)


def competing_owners(tool: Tool, platform: Platform) -> frozenset[Owner]:
    owners: set[Owner] = set()
    for method in resolve_methods(tool, platform):
        mapped = _KIND_TO_OWNER.get(method.kind)
        if mapped is not None:
            owners.add(mapped)
        elif method.kind in _INSTALLER_KINDS:
            owners.add("installer")
    return frozenset(owners)


def resolve_ownership(
    tool: Tool,
    *,
    platform: Platform,
    inventory: ManagerInventory,
    artifacts: Sequence[Path],
    managed_bin_dir: Path,
    which: Callable[[str], str | None] = shutil.which,
    native_probe: ProbeRunner | None = None,
) -> ManagerOwnership:
    applicable = resolve_methods(tool, platform)
    candidates = _collect_candidates(tool, applicable, inventory, artifacts)
    unreadable = _unreadable(tool, platform, inventory)
    active_path = _resolve_active_path(which(tool.cmd))
    dirs = owner_dirs(inventory=inventory, managed_bin_dir=managed_bin_dir, platform=platform)
    attributed = attribute_path(active_path, dirs)
    matching = [candidate for candidate in candidates if candidate.owner in attributed]
    active_candidate: Owner | None = matching[0].owner if len(matching) == 1 else None

    if active_candidate is not None:
        winner = next(candidate for candidate in candidates if candidate.owner == active_candidate)
        return _owned(
            tool,
            winner,
            confidence="direct",
            shadowed=len(candidates) > 1,
            candidates=candidates,
            active_candidate=active_candidate,
            active_path=active_path,
        )
    # D-05: consult the native-package-manager adapter HERE -- immediately
    # after the tracked-candidate active-path branch above and immediately
    # BEFORE the active-path unknown branch below. 15-RESEARCH.md's Pattern 3
    # sketch places a fallback before the FINAL `return _unknown(...)` at the
    # bottom of this function; on a real machine a dnf-installed tool has a
    # live `/usr/bin/<cmd>` that `attribute_path` cannot attribute to any
    # tracked owner, so this function returns from the branch immediately
    # below and a fallback placed at the end would never execute. This one
    # call site covers both unknown branches, both by-elimination branches,
    # and the real-machine case.
    native = _native_owner(tool, native_probe, candidates, unreadable, active_path, platform)
    if native is not None:
        return native
    # 15.4-01/D-01: the same call-site reasoning as `_native_owner` above, one
    # rung lower. This is the plan's resolution of 15.4-RESEARCH.md Open
    # Question 3: a base-image tool's live `/usr/bin/<cmd>` is attributable to
    # no tracked owner and no native manager either, so the active-path
    # unknown branch below returns first on a real machine and a fallback
    # placed after it would never run -- the same fact that forced
    # `_native_owner`'s own placement. It runs AFTER `_native_owner` on
    # purpose: an explicitly layered or explicitly installed manager is the
    # more actionable answer, and both branches are gated on the identical
    # complete-negative-evidence condition, so only one can ever fire for a
    # given tool. CR-01 survives here in its STRONGEST form: unlike
    # `_native_owner`, which proves only package membership and has to ask
    # `package_owns_path` a second question about a possibly-different file,
    # this branch's evidence IS the live active path itself, so it can never
    # rest on a different file than the one it claims to own.
    #
    # Deliberately NOT gated on `platform.immutable`. The evidence is
    # identical on a mutable host: 15.4-RESEARCH.md Pitfall 1's split-package
    # case (the declared `dnf` package name and the database's real answer
    # differ) is just as real there, `_native_owner`'s own `package_owns_path`
    # check correctly refuses it either way, and this branch is the only
    # remaining honest answer. Gating on immutability would render the same
    # fact as an empty cell on a mutable Fedora box, which is the failure
    # D-02's principle forbids. `test_os_package_owner_resolves_git_shaped_tool_on_fedora`
    # (tests/test_ownership.py) is the parametrized immutable/mutable pair
    # that pins this -- a reader tempted to add the gate should find that test
    # failing before writing it.
    os_package = _os_package_owner(
        tool, native_probe, candidates, unreadable, active_path, platform
    )
    if os_package is not None:
        return os_package
    if active_path is not None:
        return _unknown(
            tool,
            candidates=candidates,
            active_candidate=None,
            active_path=active_path,
            unknown_reason=_unknown_reason(
                unreadable=unreadable,
                active_path=active_path,
                candidates=candidates,
                applicable=applicable,
            ),
        )
    if len(candidates) == 1 and not unreadable:
        return _owned(
            tool,
            candidates[0],
            confidence="by-elimination",
            shadowed=False,
            candidates=candidates,
            active_candidate=None,
            active_path=None,
        )
    script_method = next((method for method in applicable if method.kind == "script"), None)
    if not candidates and script_method is not None and is_installed(tool) and not unreadable:
        synthetic = OwnershipCandidate(
            owner="installer",
            method=script_method,
            package=None,
            current_version=None,
            evidence="vendor install script with no competing manager claim",
        )
        return _owned(
            tool,
            synthetic,
            confidence="by-elimination",
            shadowed=False,
            candidates=(synthetic,),
            active_candidate=None,
            active_path=None,
        )
    return _unknown(
        tool,
        candidates=candidates,
        active_candidate=None,
        active_path=active_path,
        unknown_reason=_unknown_reason(
            unreadable=unreadable,
            active_path=active_path,
            candidates=candidates,
            applicable=applicable,
        ),
    )


def _native_owner(
    tool: Tool,
    probe: ProbeRunner | None,
    candidates: tuple[OwnershipCandidate, ...],
    unreadable: frozenset[Owner],
    active_path: Path | None,
    platform: Platform,
) -> ManagerOwnership | None:
    """D-05 adapter: `install_ownership.detect_owner` for the four native
    package managers, never a re-implemented probe (`.claude/architecture.md`
    rule 5).

    Last-resort evidence source, gated on COMPLETE negative evidence -- the
    same evidence rule the by-elimination branches already follow, applied to
    a new source of positive evidence. Returns `None` unless a probe was
    injected, no tracked manager produced a candidate, and no tracked
    manager's inventory was unreadable: a readable brew inventory that lists
    the tool, or an unreadable one, both mean this adapter must not run --
    the tracked managers' own evidence always outranks or blocks it.

    `platform.immutable` is forwarded to `detect_owner`, which stands the
    dnf/apt/pacman probes down on an ostree host (D-06/CR-02): the rpm
    database there answers for the whole base image, so those probes cannot
    tell a package the host merely ships from one a manager actually manages.
    """
    if probe is None or candidates or unreadable:
        return None
    verified = detect_owner(tool, probe, immutable=platform.immutable)
    if verified.confidence != "verified" or verified.manager is None:
        return None
    owner = _NATIVE_OWNER_TRANSLATION.get(verified.manager)
    if owner is None:
        # A verified NON-native manager (Homebrew, pnpm, SDKMAN, managed
        # download, host setup) has its own evidence path elsewhere in this
        # module; this adapter only ever claims the four native names.
        return None
    # CR-01: apply the module's own live-PATH rule here rather than relying on
    # the branch below to apply it. This adapter must run ABOVE the
    # active-path unknown branch (a dnf-installed tool's `/usr/bin/<cmd>` is
    # attributable to no tracked owner, so that branch would return first and
    # this would never fire), which means the rule -- "a live, unattributable
    # active path forces `unknown` before any inference runs" -- is this
    # function's to enforce. `detect_owner` proves only that the package is
    # INSTALLED; `package_owns_path` asks the manager whether that package put
    # THIS binary here. A hand-built copy earlier in PATH than the packaged
    # one is contradictory evidence, and falling through to the unknown branch
    # is the honest answer -- both because the user is told the truth about the
    # copy they run, and because `direct` is MUTATION_GRADE and must never
    # rest on evidence about a different file.
    if active_path is not None and not package_owns_path(tool, owner, str(active_path), probe):
        return None
    synthetic = OwnershipCandidate(
        owner=owner,
        method=None,
        package=None,
        current_version=None,
        evidence=verified.detail,
    )
    # Mirrors the synthetic-script by-elimination branch above: `_owned`
    # copies `candidates` through verbatim, so the winner must be present in
    # its own candidate list (`candidates=(synthetic,)`, `shadowed=False`),
    # never the empty tuple this guard just proved -- otherwise the record
    # would claim an owner while its own candidate list said nobody claims
    # this tool, and catalog_tui.py's candidate-iteration loop would have
    # nothing to iterate.
    #
    # `active_candidate` stays `None` and `active_path` passes through
    # unchanged: the claim rests on package-database membership plus the
    # manager's own file query, never on this module's directory-based path
    # attribution, and `active_candidate` names a TRACKED candidate that owns
    # the live path. Nothing here should overstate the evidence.
    return _owned(
        tool,
        synthetic,
        confidence="direct",
        shadowed=False,
        candidates=(synthetic,),
        active_candidate=None,
        active_path=active_path,
    )


def _os_package_owner(
    tool: Tool,
    probe: ProbeRunner | None,
    candidates: tuple[OwnershipCandidate, ...],
    unreadable: frozenset[Owner],
    active_path: Path | None,
    platform: Platform,
) -> ManagerOwnership | None:
    """D-01's dated correction: the base-image case `_native_owner` cannot
    reach. `install_ownership.path_owner_package` -- an INVERSE query, no
    declared candidate -- rather than a re-implemented probe
    (`.claude/architecture.md` rule 5).

    Same parameter shape and same complete-negative-evidence gate as
    `_native_owner`: returns `None` when no probe was injected, when any
    tracked candidate exists, when any tracked manager's inventory was
    unreadable, or when there is no live active path to ask about. Only then
    does it call `path_owner_package(platform.os, ...)`, and only a positive,
    singular answer becomes a claim.

    Note the call deliberately never reads `platform.immutable` -- see the
    comment at this function's one call site in `resolve_ownership` for why.
    """
    if probe is None or candidates or unreadable or active_path is None:
        return None
    package = path_owner_package(platform.os, str(active_path), probe)
    if package is None:
        return None
    synthetic = OwnershipCandidate(
        owner=OS_PACKAGE_OWNER,
        method=None,
        package=package,
        current_version=None,
        evidence=f"OS package database reports {package} owns {active_path}",
    )
    # Mirrors _native_owner's self-consistency reasoning immediately above:
    # the winner is present in its own single-element candidates tuple, never
    # the empty tuple this guard just proved, and active_candidate stays None
    # because the claim rests on the package database plus the live active
    # path itself, never on this module's directory-based path attribution.
    return _owned(
        tool,
        synthetic,
        confidence="direct",
        shadowed=False,
        candidates=(synthetic,),
        active_candidate=None,
        active_path=active_path,
    )


def _collect_candidates(
    tool: Tool,
    applicable: Sequence[Method],
    inventory: ManagerInventory,
    artifacts: Sequence[Path],
) -> tuple[OwnershipCandidate, ...]:
    found: dict[Owner, OwnershipCandidate] = {}
    installer_method = next(
        (
            method
            for method in applicable
            if method.kind in DOWNLOAD_KINDS or method.kind in APP_KINDS
        ),
        None,
    )
    if artifacts:
        found["installer"] = OwnershipCandidate(
            owner="installer",
            method=installer_method,
            package=None,
            current_version=None,
            evidence=f"installer artifact at {artifacts[0]}",
        )
    for method in applicable:
        if method.kind == "brew" and inventory.brew_formulae is not None:
            name = manager_name(method, "formula", tool.cmd)
            if name in inventory.brew_formulae:
                found["brew"] = OwnershipCandidate(
                    owner="brew",
                    method=method,
                    package=name,
                    current_version=inventory.brew_formulae[name],
                    evidence=f"Homebrew formula inventory lists {name}",
                )
        elif method.kind == "cask" and inventory.brew_casks is not None:
            name = manager_name(method, "cask", tool.cmd)
            if name in inventory.brew_casks:
                found["cask"] = OwnershipCandidate(
                    owner="cask",
                    method=method,
                    package=name,
                    current_version=inventory.brew_casks[name],
                    evidence=f"Homebrew cask inventory lists {name}",
                )
        elif method.kind == "node" and inventory.pnpm_globals is not None:
            pkg = method.params.get("npm_pkg")
            if isinstance(pkg, str) and pkg in inventory.pnpm_globals:
                found["pnpm"] = OwnershipCandidate(
                    owner="pnpm",
                    method=method,
                    package=pkg,
                    current_version=None,
                    evidence=f"pnpm global inventory lists {pkg}",
                )
        elif method.kind == "uv-tool" and inventory.uv_tools is not None:
            pkg = method.params.get("pypi_pkg")
            if isinstance(pkg, str) and pkg in inventory.uv_tools:
                found["uv"] = OwnershipCandidate(
                    owner="uv",
                    method=method,
                    package=pkg,
                    current_version=inventory.uv_tools[pkg],
                    evidence=f"uv tool inventory lists {pkg}",
                )
    return tuple(found[owner] for owner in _CANDIDATE_ORDER if owner in found)


def _unreadable(tool: Tool, platform: Platform, inventory: ManagerInventory) -> frozenset[Owner]:
    missing: set[Owner] = set()
    for owner in competing_owners(tool, platform):
        if owner == "installer":
            continue
        if owner == "brew" and inventory.brew_formulae is None:
            missing.add("brew")
        elif owner == "cask" and inventory.brew_casks is None:
            missing.add("cask")
        elif owner == "pnpm" and inventory.pnpm_globals is None:
            missing.add("pnpm")
        elif owner == "uv" and inventory.uv_tools is None:
            missing.add("uv")
    return frozenset(missing)


def _resolve_active_path(found: str | None) -> Path | None:
    if not found:
        return None
    path = Path(found)
    try:
        return path.resolve()
    except OSError:
        return path


def _owned(
    tool: Tool,
    winner: OwnershipCandidate,
    *,
    confidence: Confidence,
    shadowed: bool,
    candidates: tuple[OwnershipCandidate, ...],
    active_candidate: Owner | None,
    active_path: Path | None,
) -> ManagerOwnership:
    if confidence not in MUTATION_GRADE:
        raise RuntimeError(f"owned result must use MUTATION_GRADE, not {confidence}")
    return ManagerOwnership(
        tool_id=tool.id,
        owner=winner.owner,
        method=winner.method,
        package=winner.package,
        current_version=winner.current_version,
        confidence=confidence,
        shadowed=shadowed,
        candidates=candidates,
        active_candidate=active_candidate,
        active_path=active_path,
        unknown_reason=None,
    )


def _unknown(
    tool: Tool,
    *,
    candidates: tuple[OwnershipCandidate, ...],
    active_candidate: Owner | None,
    active_path: Path | None,
    unknown_reason: str,
) -> ManagerOwnership:
    return ManagerOwnership(
        tool_id=tool.id,
        owner="unknown",
        method=None,
        package=None,
        current_version=None,
        confidence="none",
        shadowed=len(candidates) > 1,
        candidates=candidates,
        active_candidate=active_candidate,
        active_path=active_path,
        unknown_reason=unknown_reason,
    )


def _unknown_reason(
    *,
    unreadable: frozenset[Owner],
    active_path: Path | None,
    candidates: tuple[OwnershipCandidate, ...],
    applicable: Sequence[Method] = (),
) -> str:
    if unreadable:
        names = ", ".join(sorted(unreadable))
        return f"the {names} inventory could not be read"
    # No tracked manager (brew/cask/pnpm/uv/installer) claims this tool at all,
    # but the registry declares a native package-manager method for it -- the
    # live binary almost certainly came from dnf/apt/pacman, which this module
    # deliberately doesn't track (see module docstring). Naming the likely
    # source beats the generic "not attributable to any candidate" below,
    # which told the user nothing about how the tool actually got there.
    if not candidates and any(m.kind in _NATIVE_PACKAGE_MANAGER_KINDS for m in applicable):
        return (
            "likely installed via the OS package manager (dnf/apt/pacman); "
            "this installer does not track that manager's inventory"
        )
    if active_path is not None:
        return f"the active binary at {active_path} is not attributable to any candidate"
    if len(candidates) > 1:
        names = ", ".join(candidate.owner for candidate in candidates)
        return (
            f"more than one manager claims the tool ({names}) "
            "and PATH does not resolve which one is live"
        )
    return "no manager claimed the tool"


# D-02/D-02a (15.4-01): the Owner COLUMN register only -- one terse label per
# non-unknown `Owner` value, exhaustiveness-tested against `typing.get_args
# (Owner)` so an eleventh owner value cannot ship without one.
#
# This is a SEPARATE table from the focused-row detail bar's prose register
# (`installer/catalog_tui.py`'s local `labels` dict today; 15.4-03 lifts it
# into this module's own `OWNER_DETAIL_LABELS`, declared beside this one).
# The two registers exist because the column must distinguish `cask` from
# `brew` inside a ~12-character cell while the detail bar's existing,
# test-asserted sentence for BOTH is the identical "managed by Homebrew"
# string -- a cask IS a Homebrew installation, so that prose is not wrong,
# and this phase does not change user-visible copy for brew or cask. The
# anti-duplication rule this phase enforces is therefore "neither surface
# hand-writes its own dict in catalog_tui.py; both read tables declared side
# by side in this module, and both are exhaustiveness-tested over `Owner`" --
# NOT "one table drives both surfaces" (Round-1 review 15.4-03 HIGH/MEDIUM).
OWNER_LABELS: dict[Owner, str] = {
    "brew": "Homebrew",
    # PINNED, not left to judgement (Round-2 review MEDIUM): three plans
    # constrain this literal at once. 15.4-03 requires the column register's
    # values to be pairwise distinct, so cask cannot reuse "Homebrew". 15.4-05
    # requires the cask REMOVAL phrase to stay byte-identical to
    # uninstall.py:139-141's current text, which contains only "Homebrew" and
    # "--cask". 15.4-05's label-agreement rule requires a removal phrase to
    # contain its owner's label. "Homebrew cask" satisfies the first two and
    # deliberately fails the third, which is why 15.4-05 T1 carries cask in a
    # declared `_LABEL_AGREEMENT_EXEMPT` set with a bespoke assertion rather
    # than a skip. Do not "fix" this by renaming the label to the bare word
    # "cask" -- the column sits beside "Homebrew", "dnf" and "pnpm", and a
    # bare "cask" there reads as a different product rather than as a
    # Homebrew artifact.
    "cask": "Homebrew cask",
    "pnpm": "pnpm",
    "uv": "uv",
    "dnf": "dnf",
    "apt": "apt",
    "pacman": "pacman",
    "rpm-ostree": "rpm-ostree",
    "os-package": "OS package",
    # Fallback only: `owner_label` below prefers a resolved method's own kind
    # label (github release / tarball / app / install script) for an
    # installer-owned record, and reaches this entry only when no method is
    # resolved.
    "installer": "installer artifact",
}

# The four `ManagerOwnership.method.kind` values an installer-owned record can
# carry (`ownership.py:517-532` and `:396-413`), mapped to human text for the
# Owner column.
_INSTALLER_KIND_LABELS: dict[str, str] = {
    "github_release": "GitHub release",
    "tarball": "tarball download",
    "app": "downloaded app",
    "script": "install script",
}


def owner_label(ownership: ManagerOwnership) -> str | None:
    """D-02: `None` is the only permitted empty cell, and it means genuinely
    unknown -- every other `Owner` value has a label, enforced by this
    module's own exhaustiveness test over `OWNER_LABELS`."""
    if ownership.owner == "unknown":
        return None
    if ownership.owner == "installer":
        if ownership.method is not None:
            kind_label = _INSTALLER_KIND_LABELS.get(ownership.method.kind)
            if kind_label is not None:
                return kind_label
        return OWNER_LABELS["installer"]
    return OWNER_LABELS[ownership.owner]
