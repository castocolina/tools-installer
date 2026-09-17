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
evidence the update just invalidated. Ownership is the second thing this
epoch gates (15.4-04): a raced pass publishes no ownership record at all,
and `ownership_of` answers `None` for any record whose own tag is not the
CURRENT epoch, so a mutation this app performed makes every existing
ownership record report as unavailable until a fresh pass commits one.
"""

from __future__ import annotations

import shutil
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from installer.guards import real_pnpm
from installer.install_ownership import ProbeRunner
from installer.manager_versions import OutdatedReport, read_outdated
from installer.model import Method, Tool
from installer.ownership import (
    ManagerInventory,
    ManagerOwnership,
    read_inventory,
    resolve_ownership,
)
from installer.platform import Platform
from installer.pnpm_globals import pnpm_global_packages
from installer.resolve import resolve_methods
from installer.run import CommandError, run_query
from installer.uninstall import plan_uninstall
from installer.version_cache import (
    ManagerSnapshot,
    VersionCacheEntry,
    encode_manager_snapshot,
    is_stale,
    load_manager_snapshot,
    load_version_cache,
    save_version_cache,
    should_fetch,
    should_fetch_managers,
)
from installer.versions import (
    TagResolver,
    VersionError,
    extract_observed_version,
    is_outdated,
    probe_version_output,
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
) -> tuple[VersionStatus, VersionCacheEntry | None]:
    """Probe the installed tool, optionally fetch the latest tag, build status.

    `stale` is False only after a successful `resolve_tag` in THIS pass; every
    other path uses `is_stale(entry, now=now)` so a failed fetch that preserved
    an older `latest`, and a fetch skipped by backoff, both surface as stale.
    `allow_fetch=False` skips the network even when `should_fetch` is True
    (the per-pass GitHub budget) and forces stale=True.
    """
    output = probe_output([tool.cmd, "--version"])
    installed = extract_observed_version(output) if output else None
    now_iso = now.astimezone(UTC).isoformat()
    fetched = False
    latest: str | None
    new_entry: VersionCacheEntry | None
    if allow_fetch and should_fetch(entry, now=now):
        try:
            latest = resolve_tag(repo)
            new_entry = VersionCacheEntry(latest_version=latest, checked_at=now_iso, failed_at=None)
            fetched = True
        except (VersionError, OSError):
            latest = entry.latest_version if entry is not None else None
            new_entry = VersionCacheEntry(
                latest_version=entry.latest_version if entry is not None else None,
                checked_at=entry.checked_at if entry is not None else None,
                failed_at=now_iso,
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


def _probed_version(tool: Tool, probe_output: Callable[[list[str]], str | None]) -> str | None:
    output = probe_output([tool.cmd, "--version"])
    return extract_observed_version(output) if output else None


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
) -> tuple[VersionStatus, VersionCacheEntry | None]:
    """Pick the latest-version source from ownership.owner, never from rank."""
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
        probed = _probed_version(tool, probe_output)
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
        probed = _probed_version(tool, probe_output)
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
    probed = _probed_version(tool, probe_output)
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
    ) -> None:
        self._platform = platform
        self._cache_path = cache_path
        self._resolve_tag = resolve_tag
        self._probe_output = probe_output
        self._now = now if now is not None else (lambda: datetime.now(UTC))
        self._managed_bin_dir = (
            managed_bin_dir if managed_bin_dir is not None else Path.home() / ".local" / "bin"
        )
        self._which = which
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
        self._lock = threading.Lock()
        self._statuses: dict[str, VersionStatus] = {}
        # ONE map of epoch-tagged records, deliberately never a second
        # parallel `dict[str, int]` epoch map beside a plain ownership map
        # (Round-3 review HIGH #2): `ownership_of` below is a single
        # unlocked `dict.get()` called once per rendered row per repaint
        # from the UI thread, while every WRITER here takes `_lock`
        # (`refresh`, below). Two parallel maps would let that unlocked
        # reader observe one map updated and the other not yet -- a torn
        # read. A single key lookup against one map returns both halves of
        # the pair or neither, which is inherently atomic and costs no
        # reader lock. Taking `_lock` in the reader was rejected: the
        # worker holds it across a cache load, a merge and a
        # `save_version_cache` write, and `ownership_of` must never block
        # the UI thread on that.
        self._ownership: dict[str, tuple[int, ManagerOwnership]] = {}
        self._epoch = 0

    @property
    def platform(self) -> Platform:
        return self._platform

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def statuses(self) -> dict[str, VersionStatus]:
        return dict(self._statuses)

    @property
    def managed_bin_dir(self) -> Path:
        return self._managed_bin_dir

    def ownership_of(self, tool_id: str) -> ManagerOwnership | None:
        """A record, or `None` -- meaning either "no pass has ever covered
        this tool" or "a mutation has happened since this record was
        produced". Both `None` cases mean the same thing to a caller (do
        not know), which is why they are one return value and not two.

        Reads the RECORD first (the single dict lookup, returning both
        halves of the epoch-tagged pair atomically or neither) and the
        current epoch SECOND. An `invalidate` landing between the two reads
        then makes the comparison fail and the call answer `None` -- the
        fail-closed direction. Reading the epoch first would risk the
        opposite: accepting a record the service had just superseded.
        """
        pair = self._ownership.get(tool_id)
        if pair is None:
            return None
        epoch, ownership = pair
        if epoch != self._epoch:
            return None
        return ownership

    def invalidate(self, *, reason: str) -> int:
        """Bump the epoch and drop the manager snapshot under the merge lock."""
        del reason
        with self._lock:
            self._epoch += 1
            tools = load_version_cache(self._cache_path)
            save_version_cache(self._cache_path, tools, managers={})
            return self._epoch

    def _artifacts(self, tool: Tool) -> Sequence[Path]:
        if self._artifacts_for is not None:
            return self._artifacts_for(tool)
        return plan_uninstall([tool], self._managed_bin_dir)

    def _load_or_query_snapshot(
        self, *, now: datetime
    ) -> tuple[ManagerSnapshot | None, bool, bool]:
        """Return (snapshot, persist, failed). persist means this pass queried."""
        snapshot = load_manager_snapshot(self._cache_path)
        if not should_fetch_managers(snapshot, now=now):
            return snapshot, False, False
        now_iso = now.astimezone(UTC).isoformat()
        try:
            inventory = self._read_inventory(
                has_brew=self._platform.has_brew,
                query=self._query,
                pnpm_packages=self._pnpm_packages,
            )
            outdated = self._read_outdated(
                has_brew=self._platform.has_brew,
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
        if self._partial_manager_failure(inventory, outdated):
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
        self, inventory: ManagerInventory, outdated: OutdatedReport
    ) -> bool:
        """True when a manager CONFIRMED present on this machine came back
        `None` on at least one of its fields — a swallowed transient query
        failure, never "this manager just isn't installed"."""
        if self._platform.has_brew and (
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

    def refresh(self, tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        """Load cache, resolve each tool, merge-save under the instance lock.

        BLOCKING — call only from a worker thread.
        """
        started_epoch = self.epoch
        now = self._now()
        cache = load_version_cache(self._cache_path)
        snapshot, persist_snapshot, _failed = self._load_or_query_snapshot(now=now)
        inventory = snapshot.inventory if snapshot is not None else _EMPTY_INVENTORY
        outdated = snapshot.outdated if snapshot is not None else _EMPTY_OUTDATED
        produced: dict[str, VersionCacheEntry] = {}
        statuses: dict[str, VersionStatus] = {}
        ownerships: dict[str, ManagerOwnership] = {}
        fetches = 0
        for tool in tools:
            ownership = resolve_ownership(
                tool,
                platform=self._platform,
                inventory=inventory,
                artifacts=self._artifacts(tool),
                which=self._which,
                managed_bin_dir=self._managed_bin_dir,
                native_probe=self._native_probe,
            )
            ownerships[tool.id] = ownership
            entry = cache.get(tool.id)
            allow_fetch = fetches < MAX_FETCHES_PER_REFRESH
            would_fetch = (
                allow_fetch
                and ownership.owner == "installer"
                and github_repo(tool, self._platform) is not None
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
                platform=self._platform,
                allow_fetch=allow_fetch,
            )
            statuses[tool.id] = status
            if would_fetch:
                fetches += 1
            if new_entry is not None:
                produced[tool.id] = new_entry
        with self._lock:
            if self._epoch != started_epoch:
                # RACED: an invalidate landed while this pass was resolving.
                # Publish NO ownership at all for this pass -- neither a
                # record nor an epoch for any tool in it (Round-3 review
                # HIGH #1). This deleted line used to call
                # `self._ownership.update(ownerships)`, which looks like a
                # harmless partial save but is not: a pass that started at
                # epoch 0 and finishes after a newer pass already committed
                # at epoch 1 would overwrite that newer pass's records with
                # its own obsolete ones, and -- because the tag travels
                # with the record -- every affected tool's `ownership_of`
                # would then flip from a correct current answer back to
                # `None` until yet another refresh landed. A superseded
                # pass's ownership answers are discarded entirely;
                # publishing them under an old tag is not a weaker form of
                # correct, it is the bug. This is ALSO what makes the epoch
                # gate meaningful rather than merely defensive: with this
                # branch silent, a tagged record can only ever have come
                # from the accepted commit path below, so the tag names the
                # pass that actually produced the answer the map holds.
                # Statuses are unaffected -- they are not the subject of
                # this fix, and this pass's statuses still merge exactly as
                # today.
                self._statuses.update(statuses)
                return dict(statuses)
            merged = load_version_cache(self._cache_path)
            merged.update(produced)
            managers: dict[str, object] | None
            if persist_snapshot:
                managers = encode_manager_snapshot(snapshot) if snapshot is not None else {}
            else:
                managers = None
            save_version_cache(self._cache_path, merged, managers=managers)
            self._statuses.update(statuses)
            # The ONE ownership publication point (Round-3 review HIGH #1's
            # `EPOCH-GATED` gate counts this): tagged with `started_epoch`,
            # which equals `self._epoch` here since the raced branch above
            # already returned otherwise. Every record in `self._ownership`
            # therefore carries the epoch of the pass that actually
            # produced it -- never the raced branch's obsolete one.
            self._ownership.update(
                {tool_id: (started_epoch, ownership) for tool_id, ownership in ownerships.items()}
            )
        return dict(statuses)
