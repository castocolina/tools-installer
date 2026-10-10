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
from dataclasses import dataclass, replace
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
from installer.versions import meets_minimum

Owner = Literal[
    "installer",
    "brew",
    "cask",
    "pnpm",
    "uv",
    "sdkman",
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
    "sdkman": "sdkman",
}
_INSTALLER_KINDS = frozenset((*DOWNLOAD_KINDS, *APP_KINDS, "script"))
_CANDIDATE_ORDER: tuple[Owner, ...] = ("installer", "brew", "cask", "pnpm", "uv", "sdkman")

# 15.4-02/D-01 (second half): the closed, declared set of method kinds allowed
# on the ownership-only path (`_ownership_only_methods` below), mapped to the
# `resolve.py::_applies` dimensions each kind's bypass MIRRORS. Every row's own
# comment states the ONE `_applies` clause it deliberately SKIPS. A kind absent
# from this table can never reach `_ownership_only_methods`, regardless of what
# `_method_targets_platform` would say about it -- adding a new ownership-only
# class is therefore a visible declaration edit here, not a silent widening
# (Round-2 review MEDIUM).
_OWNERSHIP_ONLY_KINDS: dict[str, tuple[str, ...]] = {
    # Mirrors os/arch/min_os_version through _method_targets_platform; skips
    # only resolve.py:67-69's `platform.os == "macos" and platform.has_brew`
    # kind-gate -- the exact verdict this ownership-only path exists to bypass
    # for ATTRIBUTION while leaving INSTALL behaviour on Linux untouched.
    "cask": ("os", "arch", "min_os_version"),
    # WR-04 (15.4-REVIEW.md). Mirrors `os` only; skips `_applies`'s `arch` and
    # `min_os_version` clauses, because those two bear on INSTALLABILITY and
    # this module answers what actually owns the installed copy. The registry
    # has three such rows today -- gnu-bash's two arch-split brew methods and
    # `container`'s `min_os_version` one -- so on a macOS arm64 host below
    # `container`'s floor, a genuinely brew-installed `container` used to
    # resolve to `unknown` (no candidate, `removal_hint` -> None) and report
    # "managed outside this installer" instead of `brew uninstall container`.
    # The `os` dimension is still mirrored: a macOS-only formula on Linux is
    # not evidence of anything, and this is attribution, not a guess. The
    # evidence rule is unchanged -- a candidate produced here still has to be
    # CONFIRMED by the real `brew list --versions` inventory in
    # `_collect_candidates` before it becomes ownership, which is the same
    # argument 15.4-02 made for cask.
    "brew": ("os",),
}

# The dimensions `_method_targets_platform` checks when a caller names none --
# every one of `resolve.py::_applies`'s three, i.e. the strictest reading.
_APPLICABILITY_DIMENSIONS: tuple[str, ...] = ("os", "arch", "min_os_version")


def _method_targets_platform(
    method: Method, platform: Platform, dimensions: tuple[str, ...] = _APPLICABILITY_DIMENSIONS
) -> bool:
    """Ownership-only mirror of `resolve.py::_applies`'s os/arch/min_os_version
    gate, covering the same three dimensions in the same order with the
    identical `meets_minimum` comparison `resolve.py:7` imports -- so the two
    functions never compare a `min_os_version` through two different parsers.

    This is a PARALLEL predicate, not a call into `resolve._applies`: that
    function returns `False` for every cask method outside macOS, which is
    exactly the verdict this path must bypass, so it cannot be reused
    wholesale. `installer/resolve.py` is deliberately left unmodified by this
    plan, so no public applicability helper is extracted there either.

    The drift risk this duplication carries is closed by this module's own
    tests: a table-driven parity gate evaluates this function and
    `resolve._applies` over a `kind = "script"` method -- the kind `_applies`
    accepts unconditionally once these three checks pass, making the two
    functions directly comparable -- across every combination of declared
    os/arch/min_os_version and platform os/arch/os_version the gate
    enumerates. A future fourth dimension added to one function and
    forgotten in the other fails that gate.

    `dimensions` names the subset to CHECK, and defaults to all three so the
    parity gate above compares like with like. Each row of
    `_OWNERSHIP_ONLY_KINDS` supplies its own subset: a dimension left out is a
    DECLARED bypass for that kind, never an accident (WR-04).
    """
    if "os" in dimensions and method.os and platform.os not in method.os:
        return False
    if "arch" in dimensions and method.arch and platform.arch not in method.arch:
        return False
    if "min_os_version" not in dimensions:
        return True
    min_version = method.params.get("min_os_version")
    return min_version is None or (
        platform.os_version is not None and meets_minimum(platform.os_version, str(min_version))
    )


def _ownership_only_methods(tool: Tool, platform: Platform) -> tuple[Method, ...]:
    """Methods that count as OWNERSHIP evidence but never as install
    candidates -- 15.4-RESEARCH.md Open Question 2, resolved as option (b),
    the narrower fork: `resolve.py::_applies`'s cask branch stays untouched
    (macOS-and-brew only), so `resolve_methods` still returns no cask method
    on Linux and this installer never offers `brew install --cask` there.
    Option (a) -- loosening `_applies` itself -- was rejected because it would
    additionally change INSTALL behaviour on Linux, which 15.4-CONTEXT.md's
    decisions never asked for.

    This module's own docstring already draws the line this helper reaches
    across: `resolve_methods` answers "what could this installer install
    here", this module answers "what actually owns the installed copy". The
    precedent for reading a declared method row for ownership purposes on a
    kind `_applies` unconditionally refuses to install already exists in
    `_os_package_owner`'s sibling `_native_owner` machinery (`rpm_ostree`,
    `resolve.py:70-73`), so this is a continuation of an existing shape, not
    a new one.

    Gated on `platform.has_brew`: both kinds in the table are Homebrew ones,
    and without brew there is no formula or cask inventory to have read, so
    there is nothing to attribute either.

    A method `resolve_methods` ALREADY returned is excluded by identity --
    `resolve_methods` filters `tool.methods`, so the objects are the same
    ones. That is what keeps `_collect_candidates` from seeing one method
    twice for a tool, and it replaces the blanket `platform.os == "macos"`
    gate this helper used to carry (WR-04, 15.4-REVIEW.md). The old gate was
    a proxy for the same idea -- on macOS every applicable cask is already an
    install candidate -- but it also excluded macOS entirely, which is
    exactly where the `brew` row's arch/min_os_version bypass has to work.
    The proxy is replaced by the thing it was standing in for; the cask
    verdict is unchanged on every platform.

    Only methods whose `kind` is a key of `_OWNERSHIP_ONLY_KINDS` are
    reachable here, each checked against its OWN declared dimension subset --
    read from the table rather than hard-coded, so the declaration is
    load-bearing rather than decorative.
    """
    if not platform.has_brew:
        return ()
    installable = resolve_methods(tool, platform)
    return tuple(
        method
        for method in tool.methods
        if method.kind in _OWNERSHIP_ONLY_KINDS
        and not any(method is candidate for candidate in installable)
        and _method_targets_platform(method, platform, _OWNERSHIP_ONLY_KINDS[method.kind])
    )


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
    off_policy: bool = False


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
    for method in (*resolve_methods(tool, platform), *_ownership_only_methods(tool, platform)):
        mapped = _KIND_TO_OWNER.get(method.kind)
        if mapped is not None:
            owners.add(mapped)
        elif method.kind in _INSTALLER_KINDS:
            owners.add("installer")
    return frozenset(owners)


def _brew_cellar_formula(active_path: Path | None, inventory: ManagerInventory) -> str | None:
    """Formula named by a path that resolves under `<prefix>/Cellar/<formula>/`.

    A claim needs the live file (dangling links are not proof), a Cellar
    segment that fullmatches `_BREW_NAME_RE`, and that formula in the inventory
    already read from `brew list`. The name is never taken from the tool id.
    """
    if active_path is None or inventory.brew_prefix is None or inventory.brew_formulae is None:
        return None
    try:
        resolved = active_path.resolve()
        cellar = (inventory.brew_prefix / "Cellar").resolve()
    except OSError:
        return None
    if cellar not in resolved.parents:
        return None
    name = resolved.relative_to(cellar).parts[0]
    if not _BREW_NAME_RE.fullmatch(name) or name not in inventory.brew_formulae:
        return None
    if not active_path.is_file():
        return None
    return name


def _undeclared_brew_candidate(
    tool: Tool,
    inventory: ManagerInventory,
    active_path: Path | None,
) -> tuple[OwnershipCandidate, bool] | None:
    """First Cellar proof among the active path, brew's bin link, and keg-only opt links.

    The bool is True when the winning path was not the active binary, so a
    shadowed brew copy can stay out of the native/os-package gate (D-06).
    """
    prefix = inventory.brew_prefix
    formulae = inventory.brew_formulae
    proofs: list[tuple[Path, str | None, bool]] = []
    if active_path is not None:
        proofs.append((active_path, None, False))
    if prefix is not None and formulae is not None:
        proofs.append((prefix / "bin" / tool.cmd, None, True))
        # shortcut: opt/<formula>/bin/<cmd> is stat'ed for every listed formula; build a
        # cmd->formula index once per inventory if this shows up in a profile.
        for formula in sorted(formulae):
            proofs.append((prefix / "opt" / formula / "bin" / tool.cmd, formula, True))
    for proof_path, required, via_link in proofs:
        name = _brew_cellar_formula(proof_path, inventory)
        if name is None or formulae is None or name not in formulae:
            continue
        if required is not None and name != required:
            continue
        return (
            OwnershipCandidate(
                owner="brew",
                method=None,
                package=name,
                current_version=formulae[name],
                evidence=f"Homebrew formula {name} owns {proof_path}",
            ),
            via_link,
        )
    return None


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
    methods = (*applicable, *_ownership_only_methods(tool, platform))
    active_path = _resolve_active_path(which(tool.cmd))
    candidates = _collect_candidates(tool, methods, inventory, artifacts)
    undeclared_brew = False
    shadow_brew: OwnershipCandidate | None = None
    if not any(candidate.owner == "brew" for candidate in candidates):
        proof = _undeclared_brew_candidate(tool, inventory, active_path)
        if proof is not None:
            brew_candidate, via_link = proof
            undeclared_brew = True
            order = {owner: index for index, owner in enumerate(_CANDIDATE_ORDER)}
            candidates = tuple(
                sorted((*candidates, brew_candidate), key=lambda item: order[item.owner])
            )
            # D-06: link-proven brew is not the live binary, so it must not block native/os-package.
            if via_link and active_path is not None:
                shadow_brew = brew_candidate
    unreadable = _unreadable(tool, platform, inventory)
    dirs = owner_dirs(inventory=inventory, managed_bin_dir=managed_bin_dir, platform=platform)
    for owner, prefixes in _location_dirs(tool, methods).items():
        dirs[owner] = dirs.get(owner, ()) + prefixes
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
            off_policy=undeclared_brew and winner.owner == "brew",
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
    gated = candidates
    if shadow_brew is not None:
        gated = tuple(candidate for candidate in candidates if candidate is not shadow_brew)
    native = _native_owner(tool, native_probe, gated, unreadable, active_path, platform)
    if native is not None:
        if shadow_brew is None:
            return native
        return replace(native, candidates=(*native.candidates, shadow_brew), shadowed=True)
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
    os_package = _os_package_owner(tool, native_probe, gated, unreadable, active_path, platform)
    if os_package is not None:
        if shadow_brew is None:
            return os_package
        return replace(os_package, candidates=(*os_package.candidates, shadow_brew), shadowed=True)
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
            off_policy=undeclared_brew and candidates[0].owner == "brew",
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
            off_policy=False,
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
    # Round-3 review HIGH: a wrong package name is worse than no package name
    # on this screen -- the hint sits beside a control that deletes files, and
    # a user who copies `dnf remove git` on a host where the binary belongs to
    # `git-core` either gets an error or removes something they did not mean
    # to. The guard immediately above is UNCHANGED and still decides WHETHER
    # this branch may claim the tool; this resolution only decides WHAT NAME
    # the claim carries -- deliberately two separate calls, because the guard
    # must stay a fail-closed confirmation of a DECLARED name, while the
    # inverse query below is a discovery whose answer may legitimately differ
    # from every declared name (the git / git-core case, and exactly why
    # reusing the guard's boolean here would not work).
    package = None
    if active_path is not None:
        package = path_owner_package(platform.os, str(active_path), probe)
    if package is None:
        package = verified.package
    synthetic = OwnershipCandidate(
        owner=owner,
        method=None,
        package=package,
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
        off_policy=False,
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
        off_policy=False,
    )


def _location_proof(tool: Tool, method: Method) -> Path | None:
    """Declared install location as ownership proof, for kinds with no inventory.

    Same `<bin_dir>/<cmd>` `is_file()` rule as `status.is_installed`. Brew,
    cask, node, and uv-tool keep their inventory proof: a stray file in those
    directories must not impersonate the manager.
    """
    if method.kind != "sdkman" and method.kind not in _INSTALLER_KINDS:
        return None
    bin_dir = method.params.get("bin_dir")
    if not isinstance(bin_dir, str) or not bin_dir:
        return None
    expanded = Path(bin_dir).expanduser()
    if (expanded / tool.cmd).is_file():
        return expanded
    return None


def _location_dirs(tool: Tool, methods: Sequence[Method]) -> dict[Owner, tuple[Path, ...]]:
    found: dict[Owner, list[Path]] = {}
    for method in methods:
        proven = _location_proof(tool, method)
        if proven is None:
            continue
        owner: Owner = "sdkman" if method.kind == "sdkman" else "installer"
        found.setdefault(owner, []).append(proven)
    return {owner: tuple(paths) for owner, paths in found.items()}


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
        proven = _location_proof(tool, method)
        if proven is not None:
            owner: Owner = "sdkman" if method.kind == "sdkman" else "installer"
            declared = method.params.get("bin_dir")
            found.setdefault(
                owner,
                OwnershipCandidate(
                    owner=owner,
                    method=method,
                    package=(
                        manager_name(method, "candidate", tool.cmd) if owner == "sdkman" else None
                    ),
                    current_version=None,
                    evidence=f"{tool.cmd} present at the method's declared location {declared}",
                ),
            )
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
    off_policy: bool = False,
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
        off_policy=off_policy,
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
    "sdkman": "SDKMAN",
    "dnf": "dnf",
    "apt": "apt",
    "pacman": "pacman",
    "rpm-ostree": "rpm-ostree",
    "os-package": "OS package",
    # Fallback only: `owner_label` below prefers a resolved method's own kind
    # label (github release / tarball / app / own installer) for an
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
    "script": "own installer",
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


# 15.4-03/D-02/D-02a: the focused-row detail bar's PROSE register -- a SEPARATE
# table from `OWNER_LABELS` above (the terse COLUMN register). Both are
# declared here, side by side, so neither surface can hand-write its own owner
# vocabulary (`installer/catalog_tui.py`'s local `labels` dict, pre-this-plan,
# is deleted in favor of reading this table through `owner_detail` below) and
# neither can drift out of sync unnoticed. Exhaustiveness over `Owner` is
# enforced by this module's own test, the same gate shape `OWNER_LABELS`
# already carries (Round-1 review 15.4-03 HIGH/MEDIUM).
#
# The two registers are ALLOWED to differ, because a ~12-character cell and a
# full sentence have different jobs: the column must distinguish `cask` from
# `brew`, while the detail bar's pre-existing, test-asserted sentence for
# BOTH is the identical "managed by Homebrew" string -- a cask IS a Homebrew
# installation, so that prose is not wrong, and this phase does not change
# user-visible copy for brew or cask. Sharing is legal but must be DECLARED:
# see `DETAIL_PHRASE_COLLISIONS` below.
#
# Eight of these ten entries are lifted BYTE-IDENTICAL from
# `catalog_tui.py`'s pre-this-plan local `labels` dict (brew, cask, pnpm, uv,
# dnf, apt, pacman, rpm-ostree) -- pinned by `tests/test_ownership.py`'s
# byte-identity assertions, so a later edit here that changes this
# user-visible copy is a failing test, not a silent change. The remaining two
# are TEMPLATES, changed deliberately (`owner_detail` interpolates them):
# `os-package` now names the actual package the record carries (this is copy
# 15.4-01 introduced one plan ago as a flat, non-interpolating placeholder,
# not pre-phase copy, so the byte-identity rule does not protect it), and
# `installer` now names the resolved placement mechanism rather than the bare
# catch-all word "installer" (D-02a) -- mirroring `owner_label`'s own
# `_INSTALLER_KIND_LABELS` lookup above.
OWNER_DETAIL_LABELS: dict[Owner, str] = {
    "brew": "managed by Homebrew",
    "cask": "managed by Homebrew",
    "pnpm": "managed by pnpm",
    "uv": "managed by uv",
    "sdkman": "managed by SDKMAN",
    "dnf": "managed by dnf — this installer will not update it",
    "apt": "managed by apt — this installer will not update it",
    "pacman": "managed by pacman — this installer will not update it",
    "rpm-ostree": "managed by rpm-ostree — this installer will not update it",
    "os-package": "managed by the OS package {package} — this installer will not update it",
    "installer": "installed via {mechanism}",
}

# The product rule behind the one declared sharing above: the prose register
# MAY share a sentence between owners, but only where it is declared HERE,
# because the alternatives are worse -- forcing column-style distinctness
# would rewrite user-visible copy this phase has no mandate to touch (the
# brew/cask sentence is not wrong, see the module comment above), and
# dropping the no-duplicate rule outright would let a future eleventh owner
# value silently borrow another owner's sentence, which is the exact D-02
# failure ("didn't bother labeling this case") the rule exists to catch. The
# COLUMN register (`OWNER_LABELS`) carries no equivalent constant because it
# permits no sharing at all -- its whole job is to distinguish a cask from a
# formula in a ~12-character cell.
DETAIL_PHRASE_COLLISIONS: frozenset[frozenset[Owner]] = frozenset({frozenset({"brew", "cask"})})


def owner_detail(ownership: ManagerOwnership) -> str | None:
    """D-02/D-02a: the PROSE register counterpart to `owner_label` above --
    `owner_label` is the terse COLUMN register (`OWNER_LABELS`), this is the
    full-sentence detail-bar register (`OWNER_DETAIL_LABELS`), declared
    adjacent to it so neither can drift unnoticed. They are allowed to differ
    because a ~12-character cell and a full sentence have different jobs.

    `None` for an `unknown` record; otherwise the resolved phrase, with the
    `os-package` and `installer` templates interpolated from the record's own
    package name / resolved placement mechanism (D-02a) -- the same
    `_INSTALLER_KIND_LABELS` lookup `owner_label` uses, so the two registers
    can never name a different mechanism for the same record.
    """
    if ownership.owner == "unknown":
        return None
    template = OWNER_DETAIL_LABELS[ownership.owner]
    if ownership.owner == "os-package":
        package = ownership.package if ownership.package is not None else "an unnamed package"
        return template.format(package=package)
    if ownership.owner == "installer":
        mechanism = None
        if ownership.method is not None:
            mechanism = _INSTALLER_KIND_LABELS.get(ownership.method.kind)
        if mechanism is None:
            mechanism = OWNER_LABELS["installer"]
        return template.format(mechanism=mechanism)
    return template


# 15.4-05/D-03/D-04: `removal_hint` -- the Uninstall screen's per-owner removal
# phrase -- lives HERE, not in `installer/uninstall.py`, and the reason is
# structural, not stylistic: this module already imports `manager_name` FROM
# `installer.uninstall` (`ownership.py:74`), so the dependency runs
# ownership-to-uninstall. A removal-hint builder living on the uninstall side
# would have to import back into this module to reuse `owner_label` and
# `ManagerOwnership`, creating the import cycle `.claude/architecture.md`
# rule 5 forbids. Task 2's `classify_tools` seam is a plain callable for
# exactly this reason: `installer/uninstall.py` never imports this module.
#
# Removal COMMAND template per owner, `{package}` interpolated from the
# record's OWN verified package name -- never the tool's own registry
# command, which is exactly the wrong string for a split package (Round-3
# review HIGH: `dnf remove rg` for `ripgrep`, `dnf remove git` for
# `git-core`). `None` for `os-package`: its removal command is the HOST's own
# and differs by host, so this module can never emit one -- the entry still
# exists as a KEY so the exhaustiveness gate below still requires it to carry
# a `_REMOVAL_DESCRIPTIONS` entry.
_REMOVAL_COMMANDS: dict[Owner, str | None] = {
    "brew": "brew uninstall {package}",
    # PINNED byte-identical to `installer/uninstall.py`'s current cask
    # sentence (Round-2 review MEDIUM): see `_LABEL_AGREEMENT_EXEMPT` below
    # for why this phrase deliberately says "Homebrew", not the Owner
    # column's "Homebrew cask" label, for this one owner.
    "cask": "brew uninstall --cask {package}",
    "pnpm": "pnpm remove --global {package}",
    "uv": "uv tool uninstall {package}",
    "sdkman": "sdk uninstall {package} <version>",
    "dnf": "dnf remove {package}",
    "apt": "apt remove {package}",
    "pacman": "pacman -R {package}",
    "rpm-ostree": "rpm-ostree uninstall {package}",
    "os-package": None,
}

# The package-LESS degradation, one entry per `_REMOVAL_COMMANDS` key
# (including `os-package`, which never has a command entry above but always
# has one here). `{label}` is the same `owner_label` result the command
# branch below prefixes its phrase with; `{name}` is the caller-supplied
# `fallback_name` -- a TOOL identifier for PROSE, never interpolated into a
# command (the previous revision of this plan had it standing in for the
# package name, which is the defect the Round-3 review caught).
_REMOVAL_DESCRIPTIONS: dict[Owner, str] = {
    "brew": "managed by {label} — remove {name} with Homebrew (no verified formula name)",
    "cask": "managed by {label} — remove {name} with Homebrew (no verified cask name)",
    "pnpm": "managed by {label} — remove {name} with pnpm (no verified package name)",
    "uv": "managed by {label} — remove {name} with uv (no verified package name)",
    "sdkman": "managed by {label} — remove {name} with SDKMAN (no verified candidate name)",
    "dnf": "managed by {label} — remove {name} with dnf (no verified package name)",
    "apt": "managed by {label} — remove {name} with apt (no verified package name)",
    "pacman": "managed by {label} — remove {name} with pacman (no verified package name)",
    "rpm-ostree": "managed by {label} — remove {name} with rpm-ostree (no verified package name)",
    # {package} here, not {name}: os-package records always carry the REAL
    # package name (`_os_package_owner` only synthesizes a record once the
    # inverse query has resolved one) and the behavior contract requires
    # naming it -- "removal_hint for an OS-package-owned record names the
    # package and states this installer will not remove it". `removal_hint`
    # below falls back to `fallback_name` only for the synthetic, package-less
    # records a test can construct directly.
    "os-package": "managed by {label} — this installer will not remove the package {package}",
}

# The two owners `removal_hint` has nothing to say for: `unknown` has no
# manager to name, and `installer` is the case the removable-here path
# already handles -- a managed installer-owned row must keep falling back to
# the registry-derived phrase rather than claiming a manager that does not
# exist.
_NO_REMOVAL_HINT: frozenset[Owner] = frozenset({"unknown", "installer"})

# The label-agreement rule below -- a removal phrase contains its owner's
# `owner_label` -- is satisfiable for every owner but `cask`, where three
# constraints collide: 15.4-03 requires the Owner column's labels to be
# pairwise distinct, so cask cannot reuse "Homebrew"; 15.4-01 pins the column
# label to the exact literal "Homebrew cask"; and this phrase must stay
# byte-identical to `installer/uninstall.py`'s pre-existing cask sentence,
# which contains "Homebrew" and "--cask" and no word joining them into
# "Homebrew cask". Two alternatives were rejected in favor of a declared
# exemption: renaming the column label to a bare "cask" (it sits beside
# "Homebrew", "dnf" and "pnpm" in a ~12-character cell and would read as a
# different product), and rewriting the frozen removal phrase (a user-visible
# copy change in a phase scoped to attribution). Declaring the exemption
# costs nothing real -- the two surfaces still name the same manager, they
# just do not share a substring.
_LABEL_AGREEMENT_EXEMPT: frozenset[Owner] = frozenset({"cask"})


def removal_hint(ownership: ManagerOwnership, fallback_name: str) -> str | None:
    """The Uninstall screen's per-owner removal phrase, built over the shared
    `owner_label` result plus the per-owner tables declared above.

    `None` for `unknown` (nothing to say) and `installer` (the removable-here
    path already covers it) -- `_NO_REMOVAL_HINT`. Otherwise: when the record
    carries a resolved `package` name AND this owner has a removal command
    template, the phrase carries a backticked command built from that real
    package name. When it does not -- `package` is `None`, or this owner's
    command is host-specific (`os-package`) -- the phrase degrades to
    `_REMOVAL_DESCRIPTIONS`' package-less sentence instead: it names the
    manager, names the TOOL via `fallback_name`, and contains no backtick.
    `fallback_name` is a prose identifier for the tool, never a stand-in for
    the package name in a command -- the tool's own registry command is
    exactly the wrong string for a split package (Round-3 review HIGH).
    """
    owner = ownership.owner
    if owner in _NO_REMOVAL_HINT:
        return None
    label = owner_label(ownership)
    # `_LABEL_AGREEMENT_EXEMPT`'s sole member: the byte-identical pin above
    # requires "Homebrew", not `owner_label`'s "Homebrew cask" column text,
    # as this phrase's prefix -- see that constant's comment for why.
    prefix = "Homebrew" if owner in _LABEL_AGREEMENT_EXEMPT else label
    command_template = _REMOVAL_COMMANDS[owner]
    if command_template is not None and ownership.package is not None:
        command = command_template.format(package=ownership.package)
        return f"managed by {prefix} — `{command}`"
    if owner == "os-package":
        # The REAL package name, never `fallback_name`: `_os_package_owner`
        # only ever synthesizes a record once the inverse query resolved one,
        # so this is reachable with `package=None` only from a test building
        # a `ManagerOwnership` directly -- degrading to `fallback_name` there
        # keeps the phrase non-empty rather than raising a KeyError.
        package = ownership.package if ownership.package is not None else fallback_name
        return _REMOVAL_DESCRIPTIONS[owner].format(label=prefix, package=package)
    return _REMOVAL_DESCRIPTIONS[owner].format(name=fallback_name, label=prefix)


def removal_label(ownership: ManagerOwnership) -> str | None:
    """The Uninstall screen's "Installed via" CELL register -- the terse
    counterpart to `removal_hint`'s full sentence, declared here beside it.

    CR-03 (15.4-REVIEW.md). The same split this module already runs between
    `OWNER_LABELS` (the ~14-character COLUMN register) and
    `OWNER_DETAIL_LABELS` (the PROSE register), now applied to the second
    screen that needs both: `removal_hint` builds the sentence the detail bar
    shows, this builds the label the table cell shows. Rendering the sentence
    into the cell instead sized the column to the longest hint in the catalog
    -- 120 columns wide at 80x24, which pushed "What gets removed" to x=174,
    off a viewport with no horizontal scroll to reach it (`left`/`right` are
    `priority=True` view-switch bindings on `ToolBrowser`) on a screen whose
    Enter key deletes files.

    Answers `None` for exactly the two owners `removal_hint` is silent for
    (`_NO_REMOVAL_HINT`), so the two functions speak for the same set of
    records and a caller can pair them without a second condition. Otherwise
    it is literally `owner_label`'s result, so the catalog's Owner column and
    this cell name a manager with the identical string rather than with two
    vocabularies that can drift.
    """
    if ownership.owner in _NO_REMOVAL_HINT:
        return None
    return owner_label(ownership)
