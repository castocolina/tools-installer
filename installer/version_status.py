"""Resolve installed-vs-latest status from a tool's real owning manager.

Refresh fires automatically on catalog view entry for entries that are stale,
mirroring DoctorScreen._start_globals_audit's own screen-entry audit. That is
the answer to 12-RESEARCH.md open question 2: the user does not press a key
to start a version check.

github_repo() selects a latest-version SOURCE and is not an ownership claim.
Ownership is installer/ownership.py's job, and resolve_methods() ordering
must never be read as "this is what installed the tool".

A first-run empty cache across ~40 github_release tools would otherwise burn
most of the unauthenticated 60-requests-per-hour GitHub budget in a single
view entry, so MAX_FETCHES_PER_REFRESH caps resolve_tag calls per pass.
Budget-deferred rows keep their last known comparison with stale=True.

Refresh is blocking and belongs on a Textual thread worker, never the event
loop. The merge guarantee is scoped to ONE process holding ONE
VersionRefreshService instance, which is the production topology (setup.py
builds one service, three CatalogScreens share it). A second concurrently
running copy of this app is not a supported topology; its worst case is one
entry lost to a last-writer-wins merge, self-healed on that entry's next
refresh. The unique sibling temp name in installer.atomic means even that
case cannot corrupt the file.

`invalidate` bumps the epoch AND drops the persisted manager snapshot so the
next refresh re-queries. Every mutation this app performs calls it, so the
cache can only ever be stale about changes made OUTSIDE this app. Residual:
a `brew upgrade` the user ran in another terminal within MANAGER_STALE_AFTER
is reported from the snapshot until it expires.

A refresh that started before an `invalidate` can still finish after it.
Immediately before persisting, under the same lock, the current epoch is
compared against the epoch captured before the slow manager queries; a
mismatch discards the write so a pre-update snapshot cannot resurrect the
evidence the update just invalidated. The published tool states are the
second thing this epoch gates (D-02, D-03): a raced pass publishes no state
at all, and `state_of` answers `None` for any state whose generation is not
the CURRENT epoch, so a mutation this app performed makes every existing
state report as unavailable until a fresh pass commits one.
"""

from __future__ import annotations

import os
import re
import shutil
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, cast

import installer.locations
from installer import receipts
from installer.download import ExecContext, artifact_paths, resolve_target
from installer.executors import ExecutorError
from installer.guards import look_through_shim, real_pnpm
from installer.install_ownership import ProbeRunner, native_index
from installer.manager_versions import OutdatedReport, read_outdated
from installer.model import SKILL_HARNESSES, ConfigStep, Method, Tool
from installer.ownership import (
    ManagerInventory,
    ManagerOwnership,
    active_path_note,
    also_installed_note,
    attribute_path,
    declared_manager_label,
    owner_detail,
    owner_dirs,
    owner_label,
    query_uv_tool_dir,
    read_inventory,
    resolve_ownership,
)
from installer.platform import Platform
from installer.pnpm_globals import (
    incomplete_install_groups,
    node_install_policy,
    pnpm_global_packages,
)
from installer.receipts import Receipt
from installer.resolve import resolve_methods, unavailable_reason
from installer.run import CommandError, run_query
from installer.skill_lifecycle import (
    SKILL_HARNESS_LABELS,
    HarnessStatus,
    ProjectPackReport,
    inspect_project_pack,
    inspect_skill_reports,
    partial_harnesses,
    partial_steps,
    present_harnesses,
)
from installer.status import is_installed
from installer.terminal_shell import TerminalShellResult
from installer.uninstall import RemovalPlan, plan_removal, plan_uninstall
from installer.version_cache import (
    ManagerSnapshot,
    VersionCacheEntry,
    encode_manager_snapshot,
    is_stale,
    load_manager_snapshot,
    load_skill_statuses,
    load_version_cache,
    save_version_cache,
    should_fetch,
    should_fetch_managers,
)
from installer.versions import (
    Release,
    TagResolver,
    VersionError,
    extract_observed_version,
    is_outdated,
    probe_version_output,
    release_resolver,
    resolve_github_tag,
)

MAX_FETCHES_PER_REFRESH = 20

_EMPTY_INVENTORY = ManagerInventory(
    brew_formulae=None,
    brew_casks=None,
    pnpm_globals=None,
    uv_tools=None,
    brew_prefix=None,
)
_EMPTY_OUTDATED = OutdatedReport(brew=None, cask=None, pnpm=None, uv=None)


def _merge_inventory(fresh: ManagerInventory, previous: ManagerSnapshot | None) -> ManagerInventory:
    """Keep every fresh, successfully-read field; backfill a failed one from
    the last known-good snapshot (or leave it `None` when there is none)."""
    fallback = previous.inventory if previous is not None else _EMPTY_INVENTORY
    return ManagerInventory(
        brew_formulae=fresh.brew_formulae
        if fresh.brew_formulae is not None
        else fallback.brew_formulae,
        brew_casks=fresh.brew_casks if fresh.brew_casks is not None else fallback.brew_casks,
        pnpm_globals=fresh.pnpm_globals
        if fresh.pnpm_globals is not None
        else fallback.pnpm_globals,
        uv_tools=fresh.uv_tools if fresh.uv_tools is not None else fallback.uv_tools,
        brew_prefix=fresh.brew_prefix if fresh.brew_prefix is not None else fallback.brew_prefix,
    )


def _merge_outdated(fresh: OutdatedReport, previous: ManagerSnapshot | None) -> OutdatedReport:
    fallback = previous.outdated if previous is not None else _EMPTY_OUTDATED
    return OutdatedReport(
        brew=fresh.brew if fresh.brew is not None else fallback.brew,
        cask=fresh.cask if fresh.cask is not None else fallback.cask,
        pnpm=fresh.pnpm if fresh.pnpm is not None else fallback.pnpm,
        uv=fresh.uv if fresh.uv is not None else fallback.uv,
    )


@dataclass(frozen=True)
class VersionStatus:
    tool_id: str
    installed: str | None
    latest: str | None
    outdated: bool | None
    stale: bool
    source: str
    pinned_spec: str | None = None


class Health(StrEnum):
    """One mark per tool; declaration order IS precedence for a present tool.

    MISSING and UNAVAILABLE are the two absent states.
    """

    CHECKING = "checking"
    BROKEN = "broken"
    MISCONFIGURED = "misconfigured"
    OUTDATED = "outdated"
    OK = "ok"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Evidence:
    """Per-tool facts collected by the refresh pass, never stored (D-01).

    Each fact is one sentence. Shadowing, off-policy state, unknown owner
    and unreadable versions are notes, never states.
    """

    present: bool
    available: bool
    checking: tuple[str, ...] = ()
    broken: tuple[str, ...] = ()
    misconfigured: tuple[str, ...] = ()
    outdated: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    absent_reason: str | None = None


def tool_health(ev: Evidence) -> tuple[Health, tuple[str, ...]]:
    """Map one Evidence to exactly one Health plus ordered reasons.

    A present tool takes the first non-empty of checking > broken >
    misconfigured > outdated, else OK; reasons put the winner's facts
    first, then the other states' facts in precedence order, then notes.
    An absent tool is MISSING when a method applies, else UNAVAILABLE; its
    present-only facts are dropped, its notes survive in the given order
    (the 19-08 builder passes configuration facts as the first notes).
    """
    if not ev.present:
        reasons: tuple[str, ...] = ()
        if ev.available:
            state = Health.MISSING
        else:
            state = Health.UNAVAILABLE
            if ev.absent_reason is not None:
                reasons = (ev.absent_reason,)
        return state, tuple(dict.fromkeys(reasons + ev.notes))

    groups = (
        (Health.CHECKING, ev.checking),
        (Health.BROKEN, ev.broken),
        (Health.MISCONFIGURED, ev.misconfigured),
        (Health.OUTDATED, ev.outdated),
    )
    winner = next(((s, f) for s, f in groups if f), (Health.OK, ()))
    reasons = winner[1]
    for state, facts in groups:
        # Compare the Health, not the tuple: two groups can hold one object
        # (G17), and an identity check would drop the other's facts.
        if state is not winner[0]:
            reasons = reasons + facts
    return winner[0], tuple(dict.fromkeys(reasons + ev.notes))


def github_repo(tool: Tool, platform: Platform) -> tuple[Method, str] | None:
    """The first applicable github_release method and its repo string.

    Used ONLY to find the latest-version SOURCE. This is not an ownership claim.
    """
    for method in resolve_methods(tool, platform):
        if method.kind != "github_release":
            continue
        repo = method.params.get("repo")
        if isinstance(repo, str) and repo:
            return method, repo
    return None


def resolve_github_release_status(
    tool: Tool,
    *,
    repo: str,
    entry: VersionCacheEntry | None,
    now: datetime,
    probe_output: Callable[[list[str]], str | None],
    resolve_tag: TagResolver,
    allow_fetch: bool = True,
    ownership: ManagerOwnership | None = None,
    unresolved: str | None = None,
) -> tuple[VersionStatus, VersionCacheEntry | None]:
    """Probe the installed tool, optionally fetch the latest tag, build status.

    `stale` is False only after a successful `resolve_tag` in THIS pass; every
    other path uses `is_stale(entry, now=now)` so a failed fetch that preserved
    an older `latest`, and a fetch skipped by backoff, both surface as stale.
    `allow_fetch=False` skips the network even when `should_fetch` is True
    (the per-pass GitHub budget) and forces stale=True.
    """
    output = probe_output(_version_argv(tool, ownership, unresolved=unresolved))
    installed = extract_observed_version(output) if output else None
    now_iso = now.astimezone(UTC).isoformat()
    fetched = False
    latest: str | None
    new_entry: VersionCacheEntry | None
    if allow_fetch and should_fetch(entry, now=now):
        try:
            release = release_resolver(resolve_tag)(repo)
            latest = release.tag
            new_entry = VersionCacheEntry(
                latest_version=latest,
                checked_at=now_iso,
                failed_at=None,
                digests=release.digests,
            )
            fetched = True
        except (VersionError, OSError):
            latest = entry.latest_version if entry is not None else None
            prior_digests: Mapping[str, str] = (
                entry.digests
                if entry is not None
                else VersionCacheEntry(latest_version=None, checked_at=None).digests
            )
            new_entry = VersionCacheEntry(
                latest_version=entry.latest_version if entry is not None else None,
                checked_at=entry.checked_at if entry is not None else None,
                failed_at=now_iso,
                digests=prior_digests,
            )
    else:
        latest = entry.latest_version if entry is not None else None
        new_entry = None
    if not allow_fetch and should_fetch(entry, now=now):
        stale = True
    else:
        stale = False if fetched else is_stale(entry, now=now)
    outdated = (
        is_outdated(installed, latest) if installed is not None and latest is not None else None
    )
    status = VersionStatus(
        tool_id=tool.id,
        installed=installed,
        latest=latest,
        outdated=outdated,
        stale=stale,
        source="github",
    )
    return status, new_entry


def _pinned_spec(ownership: ManagerOwnership) -> str | None:
    if ownership.owner != "pnpm" or ownership.method is None:
        return None
    raw = ownership.method.params.get("versions")
    if not isinstance(raw, dict):
        return None
    for name, spec in cast(dict[object, object], raw).items():
        if isinstance(name, str) and isinstance(spec, str) and name and spec:
            return f"{name} {spec}"
    return None


def _version_argv(
    tool: Tool, ownership: ManagerOwnership | None, *, unresolved: str | None = None
) -> list[str]:
    # A Volta shim or a host-setup launcher resolves to a dispatcher, not the
    # tool: probe the PATH hit itself (19-RESEARCH Pitfall 6).
    if unresolved is not None and (
        (ownership is not None and ownership.owner == "volta")
        or any(method.kind == "host_setup" for method in tool.methods)
    ):
        return [unresolved, "--version"]
    if ownership is not None and ownership.active_path is not None:
        return [str(ownership.active_path), "--version"]
    methods: list[Method] = []
    if ownership is not None and ownership.method is not None:
        methods.append(ownership.method)
    methods.extend(tool.methods)
    for method in methods:
        bin_dir = method.params.get("bin_dir")
        if not isinstance(bin_dir, str) or not bin_dir:
            continue
        candidate = Path(bin_dir).expanduser() / tool.cmd
        if candidate.is_file():
            return [str(candidate), "--version"]
    return [tool.cmd, "--version"]


def _version_file(ownership: ManagerOwnership) -> str | None | Literal[False]:
    if ownership.method is None:
        return False
    raw = ownership.method.params.get("version_file")
    if not isinstance(raw, str) or not raw:
        return False
    try:
        text = Path(raw).expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.splitlines()
    return extract_observed_version(lines[0] if lines else "")


def _probed_version(
    tool: Tool,
    ownership: ManagerOwnership,
    probe_output: Callable[[list[str]], str | None],
    *,
    unresolved: str | None = None,
) -> str | None:
    from_file = _version_file(ownership)
    if from_file is not False:
        return from_file
    output = probe_output(_version_argv(tool, ownership, unresolved=unresolved))
    return extract_observed_version(output) if output else None


def _resolved_hit(found: str | None) -> Path | None:
    """The active path exactly as `resolve_ownership` resolves it, so the native
    index is keyed by the strings its per-path lookups ask about."""
    if not found:
        return None
    try:
        return Path(found).resolve()
    except OSError:
        return Path(found)


def _sdkman_current_version(ownership: ManagerOwnership) -> str | None:
    if ownership.method is None:
        return None
    bin_dir = ownership.method.params.get("bin_dir")
    if not isinstance(bin_dir, str) or not bin_dir:
        return None
    bin_path = Path(bin_dir).expanduser()
    if not bin_path.is_dir():
        return None
    current = bin_path.parent
    try:
        target = os.readlink(current)
    except OSError:
        return None
    return extract_observed_version(Path(target).name)


def resolve_status(
    tool: Tool,
    *,
    ownership: ManagerOwnership,
    outdated: OutdatedReport,
    entry: VersionCacheEntry | None,
    now: datetime,
    probe_output: Callable[[list[str]], str | None],
    resolve_tag: TagResolver,
    platform: Platform,
    allow_fetch: bool = True,
    unresolved: str | None = None,
) -> tuple[VersionStatus, VersionCacheEntry | None]:
    """Pick the latest-version source from ownership.owner, never from rank.

    `unresolved` is the pass's PATH hit, forwarded to every version probe.
    """
    pin = _pinned_spec(ownership)
    owner = ownership.owner
    if owner == "installer":
        found = github_repo(tool, platform)
        if found is not None:
            _method, repo = found
            status, new_entry = resolve_github_release_status(
                tool,
                repo=repo,
                entry=entry,
                now=now,
                probe_output=probe_output,
                resolve_tag=resolve_tag,
                allow_fetch=allow_fetch,
                ownership=ownership,
                unresolved=unresolved,
            )
            if pin is None:
                return status, new_entry
            pinned = VersionStatus(
                tool_id=status.tool_id,
                installed=status.installed,
                latest=status.latest,
                outdated=status.outdated,
                stale=status.stale,
                source=status.source,
                pinned_spec=pin,
            )
            return pinned, new_entry
        probed = _probed_version(tool, ownership, probe_output, unresolved=unresolved)
        return (
            VersionStatus(
                tool_id=tool.id,
                installed=probed,
                latest=None,
                outdated=None,
                stale=True,
                source="installer",
                pinned_spec=pin,
            ),
            None,
        )
    if owner in ("brew", "cask", "pnpm", "uv"):
        mapping = {
            "brew": outdated.brew,
            "cask": outdated.cask,
            "pnpm": outdated.pnpm,
            "uv": outdated.uv,
        }[owner]
        probed = _probed_version(tool, ownership, probe_output, unresolved=unresolved)
        if mapping is None:
            return (
                VersionStatus(
                    tool_id=tool.id,
                    installed=ownership.current_version or probed,
                    latest=None,
                    outdated=None,
                    stale=True,
                    source=owner,
                    pinned_spec=pin,
                ),
                None,
            )
        package = ownership.package
        if package is None or package not in mapping:
            installed = ownership.current_version or probed
            return (
                VersionStatus(
                    tool_id=tool.id,
                    installed=installed,
                    latest=installed,
                    outdated=False,
                    stale=False,
                    source=owner,
                    pinned_spec=pin,
                ),
                None,
            )
        version = mapping[package]
        installed = version.current or ownership.current_version or probed
        return (
            VersionStatus(
                tool_id=tool.id,
                installed=installed,
                latest=version.latest,
                outdated=True,
                stale=False,
                source=owner,
                pinned_spec=pin,
            ),
            None,
        )
    if owner == "sdkman":
        return (
            VersionStatus(
                tool_id=tool.id,
                installed=_sdkman_current_version(ownership),
                latest=None,
                outdated=None,
                stale=False,
                source="sdkman",
                pinned_spec=None,
            ),
            None,
        )
    probed = _probed_version(tool, ownership, probe_output, unresolved=unresolved)
    return (
        VersionStatus(
            tool_id=tool.id,
            installed=probed,
            latest=None,
            outdated=None,
            stale=True,
            source="unknown",
            pinned_spec=None,
        ),
        None,
    )


def default_skill_home() -> Path:
    """The home whose skill and project-pack evidence a service reads by
    default. A function, resolved at construction, so the test suite can
    redirect it in one place (checker W5)."""
    return Path.home()


@dataclass(frozen=True)
class SkillHostStatus:
    """One pack's host answers plus its D-18 reasons and steps.

    Only the hosts are persisted: a cache-seeded status has no reasons or
    steps until the first `refresh_skills` of the launch.
    """

    hosts: dict[str, str]
    stale: bool
    reasons: tuple[str, ...] = ()
    steps: tuple[ConfigStep, ...] = ()


SKILL_NOT_CHECKED = "skill configuration not checked: "


@dataclass(frozen=True)
class _PackScan:
    """The lock-free pack inputs of one pass, read from the skill home only.

    `present` are the harnesses on this machine; `projects` each project
    pack's D-21 report; `failures` the `not checked` note of a pack whose
    helper raised (review M11).
    """

    present: frozenset[str]
    projects: Mapping[str, ProjectPackReport]
    failures: Mapping[str, str]


BROKEN_SHIM_REASON = (
    "shim present, package missing — select it and press enter to reinstall and repair"
)
NEEDS_BREW_REASON = "needs Homebrew, which is not on PATH"
SKILL_CHECKING_REASON = "checking which hosts have it"
SKILL_SEEDED_NOTE = "host status from the previous run, re-checking"
# 19-UI-SPEC locked copy (D-08, D-09, SPEC R4).
CHANGED_SINCE_INSTALL = "changed since install"
RECEIPT_UNREADABLE_NOTE = "install receipt unreadable — treated as unproven"
ADOPTED_NOTE = "adopted: the file matches the release checksum"
# SPEC-locked text; this phase adds no `r` binding (Phase 20 does).
UNPROVEN_NOTE = "not proven: reinstall with r to adopt"
# D-16, L-19-10: a drifted terminal -> (the row it lands on, its label). Konsole
# has no catalog row; the zsh row carries it.
_TERMINAL_ROWS: dict[str, tuple[str, str]] = {
    "kitty": ("kitty", "Kitty"),
    "wezterm": ("wezterm", "WezTerm"),
    "konsole": ("zsh", "Konsole"),
}


@dataclass(frozen=True)
class _ConfigFacts:
    """One row's configuration facts from the pass's secondary checks.

    `unchecked` notes say a check could not run; they apply to present rows only.
    """

    misconfigured: tuple[str, ...] = ()
    steps: tuple[ConfigStep, ...] = ()
    unchecked: tuple[str, ...] = ()

    def plus(self, other: _ConfigFacts) -> _ConfigFacts:
        return _ConfigFacts(
            self.misconfigured + other.misconfigured,
            self.steps + other.steps,
            self.unchecked + other.unchecked,
        )


_NO_FACTS = _ConfigFacts()


def _merge_facts(*maps: Mapping[str, _ConfigFacts]) -> dict[str, _ConfigFacts]:
    merged: dict[str, _ConfigFacts] = {}
    for facts in maps:
        for tool_id, fact in facts.items():
            merged[tool_id] = merged.get(tool_id, _NO_FACTS).plus(fact)
    return merged


PNPM_GROUP_UNREADABLE_NOTE = "pnpm group not checked: the pnpm inventory is unreadable"
# The missing names reach the step text, so only plain npm names get a step.
_NPM_NAME_RE = re.compile(r"^[A-Za-z0-9@][A-Za-z0-9@._/-]*$")


def _pnpm_group_facts(
    tools: Sequence[Tool], packages: frozenset[str] | None
) -> dict[str, _ConfigFacts]:
    """D-19: each incomplete co-install group, on the tool that declares it.

    The declaring tool's first `node` method names the group's first member,
    which `incomplete_install_groups` only reports when present (checker I6).
    """
    declaring: dict[str, str] = {}
    for tool in tools:
        method = next((m for m in tool.methods if m.kind == "node"), None)
        pkg = method.params.get("npm_pkg") if method is not None else None
        if method is not None and isinstance(pkg, str) and method.params.get("co_install"):
            declaring.setdefault(pkg, tool.id)
    if packages is None:
        note = (PNPM_GROUP_UNREADABLE_NOTE,)
        return {tool_id: _ConfigFacts(unchecked=note) for tool_id in declaring.values()}
    facts: dict[str, _ConfigFacts] = {}
    for group in incomplete_install_groups(node_install_policy(tools), packages):
        tool_id = declaring.get(group.present[0])
        if tool_id is None:
            continue
        names = ", ".join(group.missing)
        steps: tuple[ConfigStep, ...] = ()
        if all(_NPM_NAME_RE.fullmatch(name) for name in group.missing):
            # Empty argv (review H10): Phase 20 runs `executors.execute` on the
            # declaring tool's first node method -- the same pinned group,
            # --allow-build, real pnpm and smoke check as install and update.
            steps = (ConfigStep(f"install {names} with pnpm", "pnpm_group_install"),)
        fact = _ConfigFacts((f"pnpm group incomplete: missing {names}",), steps)
        facts[tool_id] = facts.get(tool_id, _NO_FACTS).plus(fact)
    return facts


def _run_nothing(cmd: list[str]) -> None:
    """Adoption only renders an asset name; it never runs a command (D-09)."""
    raise ExecutorError(f"adoption runs no command: {cmd}")


_PRESENT_HEALTH = frozenset({Health.BROKEN, Health.MISCONFIGURED, Health.OUTDATED, Health.OK})


@dataclass(frozen=True)
class ToolState:
    """Everything every view knows about one tool, from one pass (D-02).

    `generation` is the epoch the pass started at; `seq` is the pass's
    monotonic sequence number, which orders passes at one epoch.
    """

    tool_id: str
    generation: int
    seq: int
    health: Health
    reasons: tuple[str, ...]
    ownership: ManagerOwnership
    version: VersionStatus | None
    skill_hosts: SkillHostStatus | None
    receipt: Receipt | None
    removable: RemovalPlan
    unconfigured: tuple[ConfigStep, ...]

    @property
    def present(self) -> bool:
        """Known presence only: CHECKING is not an answer yet."""
        return self.health in _PRESENT_HEALTH


def tool_state(
    tool: Tool,
    *,
    generation: int,
    platform: Platform,
    present: bool,
    ownership: ManagerOwnership,
    version: VersionStatus | None,
    removable: RemovalPlan,
    seq: int = 0,
    skill_hosts: SkillHostStatus | None = None,
    receipt: Receipt | None = None,
    checking: tuple[str, ...] = (),
    broken: tuple[str, ...] = (),
    misconfigured: tuple[str, ...] = (),
    unconfigured: tuple[ConfigStep, ...] = (),
    notes: tuple[str, ...] = (),
) -> ToolState:
    """Gather one tool's facts into Evidence and let `tool_health` decide. Pure.

    Availability is the CURRENT answer, `resolve_methods` with this pass's
    platform: `unavailable_reason` is brew-blind (it answers None for a tool
    that could install once Homebrew is present), so it only words the reason.
    """
    absent_reason: str | None = None
    available = bool(resolve_methods(tool, platform))
    if not available:
        reason = unavailable_reason(tool, platform)
        absent_reason = reason.detail if reason is not None else NEEDS_BREW_REASON
    broken_facts = ((BROKEN_SHIM_REASON,) if ownership.broken else ()) + broken
    outdated: tuple[str, ...] = ()
    if version is not None and version.outdated:
        outdated = (f"{version.installed} -> {version.latest} available",)
    if not present:
        # An absent tool keeps its configuration facts, first (L-19-18, L-19-23).
        notes = misconfigured + notes
        misconfigured = ()
    health, reasons = tool_health(
        Evidence(
            present=present,
            available=available,
            checking=checking,
            broken=broken_facts,
            misconfigured=misconfigured,
            outdated=outdated,
            notes=notes,
            absent_reason=absent_reason,
        )
    )
    return ToolState(
        tool_id=tool.id,
        generation=generation,
        seq=seq,
        health=health,
        reasons=reasons,
        ownership=ownership,
        version=version,
        skill_hosts=skill_hosts,
        receipt=receipt,
        removable=removable,
        unconfigured=unconfigured,
    )


def _is_skill_pack(tool: Tool) -> bool:
    return any(method.kind == "skill_pack" for method in tool.methods)


def ownership_notes(tool: Tool, ownership: ManagerOwnership, platform: Platform) -> tuple[str, ...]:
    """The catalog detail bar's owner sentences, raw, in its order (D-15).

    A skill pack gets none: they describe a binary on PATH, and the resolver
    answers `unknown` for every pack (checker W1).
    """
    if _is_skill_pack(tool):
        return ()
    notes: list[str] = []
    if ownership.owner != "unknown":
        label = owner_detail(ownership)
        if label:
            notes.append(label)
        if ownership.off_policy:
            declared = declared_manager_label(tool, platform)
            real = owner_label(ownership)
            if declared is not None and real is not None:
                notes.append(
                    f"{real} owns this copy; the catalog's policy installs {tool.id} via {declared}"
                )
        if ownership.shadowed:
            also = also_installed_note(ownership)
            live = ownership.active_path
            if also is not None and live is not None:
                notes.append(f"{also} — live copy at {live}")
            elif also is not None:
                notes.append(also)
            elif live is not None:
                notes.append(f"shadowed — live copy at {live}")
            else:
                notes.append("shadowed")
    elif ownership.unknown_reason:
        notes.append(ownership.unknown_reason)
    path_note = active_path_note(ownership)
    if path_note:
        notes.append(path_note)
    return tuple(notes)


def version_notes(
    tool: Tool, status: VersionStatus, ownership: ManagerOwnership, *, present: bool
) -> tuple[str, ...]:
    """The catalog's version sentences plus the facts its dim Ver labels
    carried (D-15). None for a skill pack (checker W1)."""
    if _is_skill_pack(tool):
        return ()
    notes: list[str] = []
    if present and status.installed is None:
        notes.append("version unreadable")
    elif present and (status.latest is None or status.outdated is None):
        notes.append("no latest version to compare against")
    if status.source == "installer" and status.outdated is None and ownership.owner == "installer":
        notes.append(
            "latest version cannot be determined for this install method — "
            "pressing u re-runs the same install path this tool was originally installed with"
        )
    if status.pinned_spec:
        notes.append(
            f"this project pins {status.pinned_spec} and constrains the version deliberately"
        )
    if status.stale and status.latest is not None:
        notes.append(
            "the shown latest version came from a cache entry at or past STALE_AFTER "
            "and a re-check is pending"
        )
    return tuple(notes)


# One in-flight refresh: (epoch, seq, done, failure). The failure list gets the
# pass's exception, if any, before `done` is set (checker W11).
_Flight = tuple[int, int, threading.Event, list[BaseException]]


class VersionRefreshService:
    """Blocking refresh of version status, shared by three screens."""

    def __init__(
        self,
        *,
        platform: Platform,
        cache_path: Path,
        resolve_tag: TagResolver = resolve_github_tag,
        probe_output: Callable[[list[str]], str | None] = probe_version_output,
        now: Callable[[], datetime] | None = None,
        managed_bin_dir: Path | None = None,
        which: Callable[[str], str | None] = shutil.which,
        query: Callable[..., str] | None = None,
        pnpm_packages: Callable[[], tuple[str, ...] | None] = pnpm_global_packages,
        resolve_pnpm: Callable[[], str | None] = real_pnpm,
        artifacts_for: Callable[[Tool], Sequence[Path]] | None = None,
        read_inventory_fn: Callable[..., ManagerInventory] | None = None,
        read_outdated_fn: Callable[..., OutdatedReport] | None = None,
        native_probe: ProbeRunner | None = None,
        skill_probe: Callable[[list[str]], str] | None = None,
        skill_home: Path | None = None,
        present: Callable[[Tool], bool] | None = None,
        path_value: Callable[[], str] | None = None,
        terminal_drift: Callable[[Platform], TerminalShellResult] | None = None,
    ) -> None:
        self._platform = platform
        self._cache_path = cache_path
        self._resolve_tag = resolve_tag
        self._probe_output = probe_output
        self._now = now if now is not None else (lambda: datetime.now(UTC))
        # Module-attribute read: the conftest sandbox patches locations.bin_dir,
        # so a test-built service never reads the real ~/.local/bin (checker W2).
        self._managed_bin_dir = (
            managed_bin_dir if managed_bin_dir is not None else installer.locations.bin_dir(None)
        )
        self._which = which
        self._path_value = (
            path_value if path_value is not None else (lambda: os.environ.get("PATH", ""))
        )
        self._present = present if present is not None else self._default_present
        self._query = query if query is not None else run_query
        self._pnpm_packages = pnpm_packages
        self._resolve_pnpm = resolve_pnpm
        self._artifacts_for = artifacts_for
        self._read_inventory = (
            read_inventory_fn if read_inventory_fn is not None else read_inventory
        )
        self._read_outdated = read_outdated_fn if read_outdated_fn is not None else read_outdated
        # Deliberately None by default, breaking the surrounding query/which
        # convention: those defaults predate the D-05 native probes, and a
        # real default here would put rpm -q / dpkg-query / pacman -Qq /
        # rpm-ostree status subprocesses inside unit tests that construct
        # this service over registry-shaped tools, which .claude/testing.md
        # forbids ("tests must be deterministic and offline"). Production
        # (setup.py) supplies the real runner explicitly.
        self._native_probe = native_probe
        self._skill_probe = skill_probe
        self._skill_home = skill_home if skill_home is not None else default_skill_home()
        # D-16: a dry run only; production passes `sync_terminal_shells(write=False)`.
        self._terminal_drift = terminal_drift
        self._lock = threading.Lock()
        # The one per-tool record (D-03): a seq-gated snapshot, never mutated
        # after assignment. Each commit assigns a new dict under `_lock`, so
        # `state_of`, an unlocked read from the UI thread, holds either the
        # old snapshot or the new one, never a torn mix; each state carries
        # its pass's epoch (`generation`) and sequence number (`seq`).
        self._states: dict[str, ToolState] = {}
        self._skills: dict[str, SkillHostStatus] = {}
        # Seq and scan of the latest pass that published pack states.
        # `refresh_skills` rebuilds only those, with that scan.
        self._pack_scan: tuple[int, _PackScan] | None = None
        self._skills_probed = False
        self._skills_pass_lock = threading.Lock()
        self._epoch = 0
        self._seq = 0
        self._inflight: dict[frozenset[str], _Flight] = {}
        self._warning: str | None = None
        # D-09 non-match memo: (path, size, mtime_ns, asset, expected digest).
        self._adopt_misses: set[tuple[str, int | None, int | None, str, str]] = set()

    @property
    def platform(self) -> Platform:
        return self._platform

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def managed_bin_dir(self) -> Path:
        return self._managed_bin_dir

    @property
    def warning(self) -> str | None:
        """Why the last committed pass could not save the cache, else None."""
        return self._warning

    def state_of(self, tool_id: str) -> ToolState | None:
        """The current state, or None (never covered, or from an older epoch).

        Both `None` cases mean "do not know" to a caller. The state is read
        first and the epoch second, so an `invalidate` landing between the
        two reads answers `None` -- the fail-closed direction (D-03).
        """
        state = self._states.get(tool_id)
        if state is None or state.generation != self._epoch:
            return None
        return state

    def is_present(self, tool: Tool) -> bool:
        """The current state's presence; probe when there is no settled state."""
        state = self.state_of(tool.id)
        if state is None or state.health is Health.CHECKING:
            return self._present(tool)
        return state.present

    def _default_present(self, tool: Tool) -> bool:
        return is_installed(tool, which=self._looked_through, default_bin_dir=self._managed_bin_dir)

    def _looked_through(self, name: str) -> str | None:
        """The `which` hit, or the real binary behind this installer's own shim (D-13)."""
        return look_through_shim(
            self._which(name), name, shim_dir=self._managed_bin_dir, path_value=self._path_value()
        )

    def seed_skills_from_cache(self) -> None:
        """Load persisted skill answers as stale. Composition root only, never paint."""
        loaded = load_skill_statuses(self._cache_path)
        seeded = {
            tool_id: SkillHostStatus(hosts=dict(hosts), stale=True)
            for tool_id, hosts in loaded.items()
        }
        with self._lock:
            self._skills = seeded

    def refresh_skills(self, tools: Sequence[Tool]) -> dict[str, SkillHostStatus]:
        """Probe every skill pack once per launch. BLOCKING — worker thread only.

        A second caller waits on `_skills_pass_lock` for the in-flight pass,
        then returns that pass's map. `invalidate` must not take this lock:
        a probe may call it, and the pass lock is held across the probe.

        The worker owns host answers only (G9): project facts belong to the
        pass that published them, so the rebuild uses that pass's scan and
        never reads the home again.
        """
        packs = [tool for tool in tools if tool.skill_lifecycle is not None]
        probe = self._skill_probe
        if probe is None or not packs:
            return dict(self._skills)
        with self._skills_pass_lock:
            with self._lock:
                if self._skills_probed:
                    return dict(self._skills)
                started_epoch = self._epoch
            probed = inspect_skill_reports(packs, probe, self._skill_home)
            fresh = {
                tool_id: SkillHostStatus(
                    hosts=dict(report.hosts),
                    stale=False,
                    reasons=report.reasons,
                    steps=report.steps,
                )
                for tool_id, report in probed.items()
            }
            with self._lock:
                if self._epoch != started_epoch:
                    return dict(self._skills)
                merged = {**self._skills, **fresh}
                save_version_cache(
                    self._cache_path,
                    load_version_cache(self._cache_path),
                    skills={tool_id: dict(status.hosts) for tool_id, status in merged.items()},
                )
                self._skills = merged
                self._skills_probed = True
                published = self._pack_scan
                rebuilt = {
                    tool.id: self._skill_state(
                        tool,
                        generation=state.generation,
                        seq=state.seq,
                        platform=self._platform,
                        ownership=state.ownership,
                        version=state.version,
                        removable=state.removable,
                        scan=published[1],
                    )
                    for tool in packs
                    if (state := self._states.get(tool.id)) is not None
                    and state.generation == started_epoch
                    and published is not None
                    and state.seq == published[0]
                }
                if rebuilt:
                    self._states = {**self._states, **rebuilt}
                return dict(merged)

    def invalidate(self, *, reason: str) -> int:
        """Bump the epoch and drop the manager snapshot under the merge lock."""
        del reason
        with self._lock:
            self._epoch += 1
            tools = load_version_cache(self._cache_path)
            save_version_cache(self._cache_path, tools, managers={})
            self._skills_probed = False
            self._skills = {
                tool_id: replace(entry, stale=True) for tool_id, entry in self._skills.items()
            }
            return self._epoch

    def _scan_packs(self, packs: Sequence[Tool]) -> _PackScan:
        """Harnesses and project reports, read once, outside `_lock` (D-17, D-21).

        Every scan takes `self._skill_home` explicitly (checker W5).
        """
        failures: dict[str, str] = {}
        if not packs:
            return _PackScan(present=frozenset(), projects={}, failures=failures)
        try:
            present = present_harnesses(self._skill_home, self._looked_through)
        except Exception as exc:  # a read-only secondary fact must never fail the pass
            present = frozenset[str]()
            failures = {tool.id: f"{SKILL_NOT_CHECKED}{exc}" for tool in packs}
        projects: dict[str, ProjectPackReport] = {}
        for tool in packs:
            lifecycle = tool.skill_lifecycle
            if lifecycle is None or lifecycle.scope != "project":
                continue
            try:
                projects[tool.id] = inspect_project_pack(tool, self._skill_home, present)
            except Exception as exc:  # a read-only secondary fact must never fail the pass
                failures.setdefault(tool.id, f"{SKILL_NOT_CHECKED}{exc}")
        return _PackScan(present=present, projects=projects, failures=failures)

    def _user_pack_facts(
        self, tool: Tool, hosts: SkillHostStatus | None, present: frozenset[str]
    ) -> tuple[tuple[str, ...], tuple[ConfigStep, ...], tuple[str, ...]]:
        """(facts, steps, notes) of a user-scope pack: D-18 first, then D-17 partials."""
        lifecycle = tool.skill_lifecycle
        if hosts is None or lifecycle is None or not hosts.hosts:
            return (), (), ()
        notes: tuple[str, ...] = ()
        partial: tuple[tuple[str, ...], tuple[ConfigStep, ...]] = ((), ())
        try:
            # A harness whose D-18 fix already has a step is not also partial.
            fixed = {step.harness for step in hosts.steps}
            missing = partial_harnesses(
                cast(Mapping[str, HarnessStatus], hosts.hosts),
                lifecycle.supported_harnesses,
                present,
            )
            partial = partial_steps(tool, [h for h in missing if h not in fixed])
        except Exception as exc:  # a read-only secondary fact must never fail the pass
            notes = (f"{SKILL_NOT_CHECKED}{exc}",)
        if not hosts.stale:
            # Review C2-M3: an unreadable answer from a harness this machine has.
            notes += tuple(
                f"{SKILL_NOT_CHECKED}no readable answer from "
                f"{SKILL_HARNESS_LABELS.get(harness, harness)}"
                for harness in SKILL_HARNESSES
                if harness in present and hosts.hosts.get(harness) == "unknown"
            )
        return hosts.reasons + partial[0], hosts.steps + partial[1], notes

    def _skill_state(
        self,
        tool: Tool,
        *,
        generation: int,
        seq: int,
        platform: Platform,
        ownership: ManagerOwnership,
        version: VersionStatus | None,
        removable: RemovalPlan,
        scan: _PackScan,
    ) -> ToolState:
        """A skill pack's state from the host answers held now (call under
        `_lock`) and the pass's scan. Every configuration fact goes through
        here, so `refresh_skills`'s rebuild keeps it.

        A user-scope pack with probes is CHECKING until the current probe has
        answered for it (G8): stale answers, including a cache-seeded
        `present`, add only the seeded note. Once it has, presence is any
        fresh `present` answer, else MISSING; an unreadable present harness
        adds its not-checked note, so mixed absent/unknown is never a
        note-less MISSING (G24), agreeing with `skill_lifecycle.inspect_status`.
        """
        hosts = self._skills.get(tool.id)
        failure = scan.failures.get(tool.id)
        notes: tuple[str, ...] = (failure,) if failure is not None else ()
        report = scan.projects.get(tool.id)
        if report is not None:
            # D-21: presence is "installed in N repos" or a global leftover,
            # never the global install-state hosts.
            repos = sum(1 for _repo, runtimes in report.repos if runtimes)
            if repos:
                notes = (f"installed in {repos} repo{'' if repos == 1 else 's'}",) + notes
            notes += tuple(f"{SKILL_NOT_CHECKED}cannot read ~/{path}" for path in report.unchecked)
            return tool_state(
                tool,
                generation=generation,
                seq=seq,
                platform=platform,
                present=bool(repos or report.leftovers),
                ownership=ownership,
                version=version,
                removable=removable,
                skill_hosts=hosts,
                misconfigured=report.reasons,
                unconfigured=report.steps,
                notes=notes,
            )
        if tool.skill_lifecycle is not None and not tool.skill_lifecycle.status_probes:
            # No host probe will ever answer for this pack: presence is the
            # presence predicate, as for any binary, never CHECKING forever.
            facts, steps, pack_notes = self._user_pack_facts(tool, hosts, scan.present)
            return tool_state(
                tool,
                generation=generation,
                seq=seq,
                platform=platform,
                present=self._present(tool),
                ownership=ownership,
                version=version,
                removable=removable,
                misconfigured=facts,
                unconfigured=steps,
                notes=notes + pack_notes,
            )
        # The current probe has answered only when its answers are stored fresh
        # (`refresh_skills` writes stale=False; the cache and `invalidate` write
        # stale=True). Stale answers never settle presence, facts or steps.
        if hosts is None or hosts.stale:
            if hosts is not None and hosts.stale:
                notes = (SKILL_SEEDED_NOTE,) + notes
            return tool_state(
                tool,
                generation=generation,
                seq=seq,
                platform=platform,
                present=True,
                ownership=ownership,
                version=version,
                removable=removable,
                skill_hosts=hosts,
                checking=(SKILL_CHECKING_REASON,),
                notes=notes,
            )
        answered = hosts
        facts, steps, pack_notes = self._user_pack_facts(tool, answered, scan.present)
        return tool_state(
            tool,
            generation=generation,
            seq=seq,
            platform=platform,
            present="present" in answered.hosts.values(),
            ownership=ownership,
            version=version,
            removable=removable,
            skill_hosts=answered,
            misconfigured=facts,
            unconfigured=steps,
            notes=notes + pack_notes,
        )

    def _receipt_evidence(
        self,
        tool: Tool,
        *,
        present: bool,
        entry: VersionCacheEntry | None,
        platform: Platform,
    ) -> tuple[Receipt | None, tuple[str, ...], tuple[str, ...]]:
        """(receipt, broken facts, notes) from the tool's receipt (D-08, SPEC R4).

        An artifact that no longer matches its receipt is BROKEN; a receipt
        file that does not parse proves nothing and says so as a note. An
        inaccessible receipts dir is that same unreadable note, with no
        adoption (G23). A receipt whose every artifact is gone is retired, and
        the tool then reads from current evidence (G10). A present tool with
        no receipt file may be adopted (D-09)."""
        if not receipts.receipt_exists(tool.id):
            adopted = self._adopt(tool, entry, platform) if present else None
            return adopted, (), (ADOPTED_NOTE,) if adopted is not None else ()
        receipt = receipts.read(tool.id)
        if receipt is None:
            return None, (), (RECEIPT_UNREADABLE_NOTE,)
        if receipts.all_gone(receipt) and receipts.retire(tool.id, receipt):
            return None, (), ()
        if receipts.drifted(receipt):
            return receipt, (CHANGED_SINCE_INSTALL,), ()
        return receipt, (), ()

    def _adopt(
        self, tool: Tool, entry: VersionCacheEntry | None, platform: Platform
    ) -> Receipt | None:
        """Adopt a raw github_release file whose sha256 is the cached digest (D-09).

        No network: the asset name is rendered from the cached tag and digests.
        ONE fingerprint is compared and handed to `receipts.adopt`, which
        re-checks it under its lock (review H9). A non-match is remembered per
        (path, size, mtime_ns, asset, expected digest), so a changed file, tag
        or digest is checked again (review M10)."""
        found = github_repo(tool, platform)
        if found is None or entry is None or entry.latest_version is None or not entry.digests:
            return None
        method = found[0]
        if method.params.get("raw") is not True:
            return None
        release = Release(tag=entry.latest_version, digests=entry.digests)
        ctx = ExecContext(
            runner=_run_nothing, platform=platform, resolve_release=lambda _repo: release
        )
        try:
            asset = resolve_target(method, ctx).asset
            expected = entry.digests.get(asset)
            files = [
                a.path for a in artifact_paths(method, self._managed_bin_dir) if a.kind == "file"
            ]
            if expected is None or not files:
                return None
            st = files[0].lstat()
            if (str(files[0]), st.st_size, st.st_mtime_ns, asset, expected) in self._adopt_misses:
                return None
            artifact = receipts.fingerprint(files[0], "file")
            if artifact is None:
                return None
            if artifact.sha256 != expected:
                self._adopt_misses.add(
                    (str(files[0]), artifact.size, artifact.mtime_ns, asset, expected)
                )
                return None
            return receipts.adopt(tool, method, artifact, package=None)
        except (ExecutorError, OSError):
            return None

    def _terminal_facts(self, platform: Platform) -> dict[str, _ConfigFacts]:
        """D-16: ONE dry-run sync per pass; each drifted terminal is its row's fact.

        A warning is a note, never a step (G11): the synchronizer cannot handle
        that shape. Its prefix before the first colon names the terminal; an
        unknown prefix lands on every terminal row.
        """
        if self._terminal_drift is None:
            return {}
        try:
            result = self._terminal_drift(platform)
        except Exception as exc:  # a read-only secondary fact must never fail the pass
            # Review M11: a drop without a note would let a drifted terminal read OK.
            note = (f"terminal shell not checked: {exc}",)
            return {row: _ConfigFacts(unchecked=note) for row, _label in _TERMINAL_ROWS.values()}
        facts: dict[str, _ConfigFacts] = {}
        for name in result.drifted:
            if name not in _TERMINAL_ROWS:
                continue
            row, label = _TERMINAL_ROWS[name]
            fact = _ConfigFacts(
                (f"{label} does not start zsh",),
                (ConfigStep(f"point {label} at zsh", "terminal_sync"),),
            )
            facts[row] = facts.get(row, _NO_FACTS).plus(fact)
        rows = tuple(dict.fromkeys(row for row, _label in _TERMINAL_ROWS.values()))
        for warning in result.warnings:
            prefix = warning.split(":", 1)[0]
            targets = (_TERMINAL_ROWS[prefix][0],) if prefix in _TERMINAL_ROWS else rows
            note = _ConfigFacts(unchecked=(f"terminal shell not checked: {warning}",))
            for row in targets:
                facts[row] = facts.get(row, _NO_FACTS).plus(note)
        return facts

    def _artifacts(self, tool: Tool) -> Sequence[Path]:
        if self._artifacts_for is not None:
            return self._artifacts_for(tool)
        return plan_uninstall([tool], self._managed_bin_dir)

    def resolve_owner(self, tool: Tool) -> ManagerOwnership:
        """One tool's owner from fresh evidence: the update path (D-14). BLOCKING.

        The same evidence the pass uses, gathered now: the platform with brew
        re-read, a FRESH manager inventory (never the cached snapshot), `uv
        tool dir` when uv is on PATH, the look-through `which` and the native
        probe. Nothing is published.
        """
        platform = replace(self._platform, has_brew=self._which("brew") is not None)
        inventory = self._read_inventory(
            has_brew=platform.has_brew, query=self._query, pnpm_packages=self._pnpm_packages
        )
        uv_tool_dir = query_uv_tool_dir(self._query) if self._which("uv") is not None else None
        return self._resolve_owner_from(
            tool,
            platform=platform,
            inventory=inventory,
            which=self._looked_through,
            uv_tool_dir=uv_tool_dir,
            native_probe=self._native_probe,
        )

    def _resolve_owner_from(
        self,
        tool: Tool,
        *,
        platform: Platform,
        inventory: ManagerInventory,
        which: Callable[[str], str | None],
        uv_tool_dir: Path | None,
        native_probe: ProbeRunner | None,
    ) -> ManagerOwnership:
        """The one owner resolution, over evidence the caller gathered (review M12)."""
        return resolve_ownership(
            tool,
            platform=platform,
            inventory=inventory,
            artifacts=self._artifacts(tool),
            which=which,
            managed_bin_dir=self._managed_bin_dir,
            native_probe=native_probe,
            uv_tool_dir=uv_tool_dir,
        )

    def _load_or_query_snapshot(
        self, *, now: datetime, platform: Platform
    ) -> tuple[ManagerSnapshot | None, bool, bool]:
        """Return (snapshot, persist, failed). persist means this pass queried.

        A fresh snapshot is reused only when its brew evidence agrees with
        the pass's `has_brew`, or when it records a failure (the retry
        backoff stays in charge): brew appearing or vanishing reaches
        ownership on the next pass, not after the 6-hour window (review M6).
        """
        snapshot = load_manager_snapshot(self._cache_path)
        if not should_fetch_managers(snapshot, now=now) and (
            snapshot is None
            or snapshot.failed_at is not None
            or (snapshot.inventory.brew_prefix is not None) == platform.has_brew
        ):
            return snapshot, False, False
        now_iso = now.astimezone(UTC).isoformat()
        try:
            inventory = self._read_inventory(
                has_brew=platform.has_brew,
                query=self._query,
                pnpm_packages=self._pnpm_packages,
            )
            outdated = self._read_outdated(
                has_brew=platform.has_brew,
                query=self._query,
                resolve_pnpm=self._resolve_pnpm,
            )
        except (CommandError, OSError):
            previous = snapshot
            failed = ManagerSnapshot(
                inventory=previous.inventory if previous is not None else _EMPTY_INVENTORY,
                outdated=previous.outdated if previous is not None else _EMPTY_OUTDATED,
                checked_at=previous.checked_at if previous is not None else None,
                failed_at=now_iso,
            )
            return failed, True, True
        if self._partial_manager_failure(inventory, outdated, platform=platform):
            # W3 (12-REVIEW.md, codex-sol-high): each manager reader swallows
            # its own CommandError/OSError into a `None` field rather than
            # raising, so a single transient brew/pnpm/uv failure never trips
            # the `except` branch above — it would otherwise be cached with
            # `checked_at=now_iso, failed_at=None` and read as a confirmed-
            # fresh snapshot for a full MANAGER_STALE_AFTER (6h), including by
            # the update-enablement gate that reads cached ownership. Treat a
            # confirmed-present manager returning `None` the same as the
            # outright-exception case: keep whatever DID come back fresh this
            # pass, backfill the failed field(s) from the previous snapshot
            # when one exists, and mark `failed_at` so the 30-minute
            # `MANAGER_RETRY_BACKOFF` applies instead of the full 6-hour
            # freshness window.
            previous = snapshot
            merged = ManagerSnapshot(
                inventory=_merge_inventory(inventory, previous),
                outdated=_merge_outdated(outdated, previous),
                checked_at=previous.checked_at if previous is not None else None,
                failed_at=now_iso,
            )
            return merged, True, True
        return (
            ManagerSnapshot(
                inventory=inventory,
                outdated=outdated,
                checked_at=now_iso,
                failed_at=None,
            ),
            True,
            False,
        )

    def _partial_manager_failure(
        self, inventory: ManagerInventory, outdated: OutdatedReport, *, platform: Platform
    ) -> bool:
        """True when a manager CONFIRMED present on this machine came back
        `None` on at least one of its fields — a swallowed transient query
        failure, never "this manager just isn't installed"."""
        if platform.has_brew and (
            inventory.brew_formulae is None
            or inventory.brew_casks is None
            or inventory.brew_prefix is None
            or outdated.brew is None
            or outdated.cask is None
        ):
            return True
        if self._resolve_pnpm() is not None and (
            inventory.pnpm_globals is None or outdated.pnpm is None
        ):
            return True
        return self._which("uv") is not None and (inventory.uv_tools is None or outdated.uv is None)

    def refresh(self, tools: Sequence[Tool]) -> None:
        """Resolve every tool once and publish the pass with one swap.

        BLOCKING — call only from a worker thread. Read the result through
        `state_of`. A call over the same tool-id set as a pass already in
        flight at the current epoch joins that pass (or raises its error):
        no second fetch, probe or publication. It never joins across an
        `invalidate`.
        """
        key = frozenset(tool.id for tool in tools)
        with self._lock:
            flight: _Flight | None = self._inflight.get(key)
            joining = flight is not None and flight[0] == self._epoch
            if flight is None or not joining:
                self._seq += 1
                flight = (self._epoch, self._seq, threading.Event(), [])
                self._inflight[key] = flight
        started_epoch, seq, done, failure = flight
        if joining:
            done.wait()
            if failure:
                raise failure[0]
            return
        try:
            self._pass(tools, seq=seq, started_epoch=started_epoch)
        except BaseException as exc:
            failure.append(exc)
            raise
        finally:
            with self._lock:
                if self._inflight.get(key) is flight:
                    del self._inflight[key]
            done.set()

    def _pass(self, tools: Sequence[Tool], *, seq: int, started_epoch: int) -> None:
        # D-14: brew is re-read every pass. Every helper of this pass gets this
        # one value; none reads the shared `self._platform`, which an
        # overlapping pass may replace mid-pass (review M5).
        platform = replace(self._platform, has_brew=self._which("brew") is not None)
        with self._lock:
            self._platform = platform
        # L-19-01: `uv tool dir`, asked once per pass and only when uv is on PATH.
        uv_tool_dir = query_uv_tool_dir(self._query) if self._which("uv") is not None else None
        now = self._now()
        cache = load_version_cache(self._cache_path)
        snapshot, persist_snapshot, _failed = self._load_or_query_snapshot(
            now=now, platform=platform
        )
        inventory = snapshot.inventory if snapshot is not None else _EMPTY_INVENTORY
        outdated = snapshot.outdated if snapshot is not None else _EMPTY_OUTDATED
        config = _merge_facts(
            self._terminal_facts(platform), _pnpm_group_facts(tools, inventory.pnpm_globals)
        )
        which = self._looked_through
        native = self._native_probe
        if native is not None and platform.os != "macos":
            # D-11: ONE batched path query per pass, over the live paths no tracked
            # owner claims; the index also memoizes every other native argv.
            dirs = owner_dirs(
                inventory=inventory,
                managed_bin_dir=self._managed_bin_dir,
                platform=platform,
                uv_tool_dir=uv_tool_dir,
            )
            hits = (_resolved_hit(which(tool.cmd)) for tool in tools)
            paths = [str(hit) for hit in hits if hit is not None and not attribute_path(hit, dirs)]
            native = native_index(platform.os, paths, native)
        produced: dict[str, VersionCacheEntry] = {}
        states: dict[str, ToolState] = {}
        packs: list[tuple[Tool, ManagerOwnership, VersionStatus, RemovalPlan]] = []
        fetches = 0
        for tool in tools:
            ownership = self._resolve_owner_from(
                tool,
                platform=platform,
                inventory=inventory,
                which=which,
                uv_tool_dir=uv_tool_dir,
                native_probe=native,
            )
            entry = cache.get(tool.id)
            allow_fetch = fetches < MAX_FETCHES_PER_REFRESH
            would_fetch = (
                allow_fetch
                and ownership.owner == "installer"
                and github_repo(tool, platform) is not None
                and should_fetch(entry, now=now)
            )
            status, new_entry = resolve_status(
                tool,
                ownership=ownership,
                outdated=outdated,
                entry=entry,
                now=now,
                probe_output=self._probe_output,
                resolve_tag=self._resolve_tag,
                platform=platform,
                allow_fetch=allow_fetch,
                unresolved=which(tool.cmd),
            )
            if tool.skill_lifecycle is not None:
                # Built at commit, from the host answers held then.
                packs.append((tool, ownership, status, plan_removal([tool], self._managed_bin_dir)))
            else:
                present = self._present(tool)
                # Before the removal plan, so an adopted tool is removable now.
                receipt, broken, receipt_notes = self._receipt_evidence(
                    tool,
                    present=present,
                    entry=new_entry if new_entry is not None else entry,
                    platform=platform,
                )
                removable = plan_removal([tool], self._managed_bin_dir)
                if (
                    present
                    and ownership.owner == "installer"
                    and (receipt is None or broken)
                    and not removable.removable
                ):
                    # No receipt, adoption or layout proves it (review C2-M2).
                    receipt_notes += (UNPROVEN_NOTE,)
                facts = config.get(tool.id, _NO_FACTS)
                states[tool.id] = tool_state(
                    tool,
                    generation=started_epoch,
                    seq=seq,
                    platform=platform,
                    present=present,
                    ownership=ownership,
                    version=status,
                    removable=removable,
                    receipt=receipt,
                    broken=broken,
                    misconfigured=facts.misconfigured,
                    unconfigured=facts.steps,
                    notes=ownership_notes(tool, ownership, platform)
                    + version_notes(tool, status, ownership, present=present)
                    + receipt_notes
                    + (facts.unchecked if present else ()),
                )
            if would_fetch:
                fetches += 1
            if new_entry is not None:
                produced[tool.id] = new_entry
        scan = self._scan_packs([pack for pack, *_rest in packs])
        with self._lock:
            if self._epoch != started_epoch:
                # RACED: an invalidate landed while this pass was resolving,
                # so the WHOLE pass is discarded -- no state and no cache
                # write (D-02). Publishing any of it under the old tag would
                # overwrite or shadow the answer of a pass that started after
                # the mutation (Round-3 review HIGH #1); with this branch
                # silent, every published state names the pass that produced it.
                return
            for tool, ownership, status, removable in packs:
                states[tool.id] = self._skill_state(
                    tool,
                    generation=started_epoch,
                    seq=seq,
                    platform=platform,
                    ownership=ownership,
                    version=status,
                    removable=removable,
                    scan=scan,
                )
            # Newest pass wins per record (L-19-02): at one epoch a record
            # is replaced only by one from a pass with a higher sequence,
            # so a slower older pass can still fill tools a newer partial
            # pass did not cover, but never overwrites one it did.
            fresh = {
                tool_id: state
                for tool_id, state in states.items()
                if (current := self._states.get(tool_id)) is None or current.seq < seq
            }
            if not fresh:
                return
            # The ONE publication point, tagged with `started_epoch`, which
            # equals `self._epoch` here.
            self._states = {**self._states, **fresh}
            if any(tool.id in fresh for tool, *_rest in packs):
                self._pack_scan = (seq, scan)
            # Best effort, after the swap and still under the lock (it
            # serializes with `invalidate`'s save): a failed write leaves the
            # published states in place and surfaces as `warning`.
            managers: dict[str, object] | None = None
            if persist_snapshot:
                managers = encode_manager_snapshot(snapshot) if snapshot is not None else {}
            try:
                merged = load_version_cache(self._cache_path)
                merged.update({k: v for k, v in produced.items() if k in fresh})
                save_version_cache(self._cache_path, merged, managers=managers)
            except OSError as exc:
                self._warning = f"version cache not saved: {exc}"
            else:
                self._warning = None
