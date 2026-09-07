"""Resolve installed-vs-latest status for github_release tools.

Refresh is blocking and belongs on a Textual thread worker, never the event
loop. The merge guarantee is scoped to ONE process holding ONE
VersionRefreshService instance, which is the production topology (setup.py
builds one service, three CatalogScreens share it). A second concurrently
running copy of this app is not a supported topology; its worst case is one
entry lost to a last-writer-wins merge, self-healed on that entry's next
refresh. The unique sibling temp name in installer.atomic means even that
case cannot corrupt the file.

`invalidate` exists so Plan 12-03's update action can declare every in-flight
read of the machine obsolete. Nothing in this plan calls it.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from installer.model import Method, Tool
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.version_cache import (
    VersionCacheEntry,
    is_stale,
    load_version_cache,
    save_version_cache,
    should_fetch,
)
from installer.versions import (
    TagResolver,
    VersionError,
    extract_observed_version,
    is_outdated,
    probe_version_output,
    resolve_github_tag,
)


@dataclass(frozen=True)
class VersionStatus:
    tool_id: str
    installed: str | None
    latest: str | None
    outdated: bool | None
    stale: bool
    source: str


def github_repo(tool: Tool, platform: Platform) -> tuple[Method, str] | None:
    """The first applicable github_release method and its repo string.

    Used ONLY to find the latest-version SOURCE. This is not an ownership claim;
    ownership arrives in Plan 12-02.
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
) -> tuple[VersionStatus, VersionCacheEntry | None]:
    """Probe the installed tool, optionally fetch the latest tag, build status.

    `stale` is False only after a successful `resolve_tag` in THIS pass; every
    other path uses `is_stale(entry, now=now)` so a failed fetch that preserved
    an older `latest`, and a fetch skipped by backoff, both surface as stale.
    """
    output = probe_output([tool.cmd, "--version"])
    installed = extract_observed_version(output) if output else None
    now_iso = now.astimezone(UTC).isoformat()
    fetched = False
    latest: str | None
    new_entry: VersionCacheEntry | None
    if should_fetch(entry, now=now):
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


class VersionRefreshService:
    """Blocking refresh of github_release version status, shared by three screens."""

    def __init__(
        self,
        *,
        platform: Platform,
        cache_path: Path,
        resolve_tag: TagResolver = resolve_github_tag,
        probe_output: Callable[[list[str]], str | None] = probe_version_output,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._platform = platform
        self._cache_path = cache_path
        self._resolve_tag = resolve_tag
        self._probe_output = probe_output
        self._now = now if now is not None else (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._statuses: dict[str, VersionStatus] = {}
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

    def invalidate(self, *, reason: str) -> int:
        """Bump the epoch so in-flight refreshes that started earlier are dropped."""
        del reason
        with self._lock:
            self._epoch += 1
            return self._epoch

    def refresh(self, tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        """Load cache, resolve each tool, merge-save under the instance lock.

        BLOCKING — call only from a worker thread.
        """
        now = self._now()
        cache = load_version_cache(self._cache_path)
        produced: dict[str, VersionCacheEntry] = {}
        statuses: dict[str, VersionStatus] = {}
        for tool in tools:
            found = github_repo(tool, self._platform)
            if found is None:
                continue
            _method, repo = found
            status, entry = resolve_github_release_status(
                tool,
                repo=repo,
                entry=cache.get(tool.id),
                now=now,
                probe_output=self._probe_output,
                resolve_tag=self._resolve_tag,
            )
            statuses[tool.id] = status
            if entry is not None:
                produced[tool.id] = entry
        with self._lock:
            merged = load_version_cache(self._cache_path)
            merged.update(produced)
            save_version_cache(self._cache_path, merged)
            self._statuses.update(statuses)
        return dict(statuses)
