"""Update-check decisions over injected seams, without installing, updating, removing or pulling.

Git failures are reported as fixed categories only. The production runner disables hooks,
prompts, askpass and credential helpers, and lazy fetch (Git 2.44 or newer); older Git may
ignore the lazy-fetch setting. GIT_SSH_COMMAND outranks core.sshCommand. The user's and the
repository's other Git configuration remains in effect. A checkout that is not its own
worktree root is skipped to avoid querying a surrounding repository's origin. A partial clone
is skipped before object queries because older Git may ignore the lazy-fetch setting.
A persistent notified-set save failure can cause a notification on every run.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

from installer import schedules
from installer.atomic import atomic_replace_entry, read_capped
from installer.locations import ensure_dir
from installer.model import TOOL_ID_RE, Tool
from installer.notify import Notifier, reason_line
from installer.run import TIMEOUT_CODE, CommandError, run_git_isolated
from installer.version_cache import (
    ManagerSnapshot,
    VersionCacheEntry,
    attempted_at,
    load_manager_snapshot,
    load_version_cache,
    stamp_time,
)
from installer.version_status import FailureSink, Health, ToolState, outdated_ids

# Under 24 hours meets the schedule boundary without repeating a recent TUI fetch.
CHECK_STALE_AFTER = timedelta(hours=20)


class Refresher(Protocol):
    @property
    def cache_path(self) -> Path: ...

    @property
    def warning(self) -> str | None: ...

    def refresh(
        self, tools: Sequence[Tool], *, stale_after: timedelta, on_failure: FailureSink | None
    ) -> (
        tuple[dict[str, ToolState], dict[str, VersionCacheEntry], ManagerSnapshot | None] | None
    ): ...

    def state_of(self, tool_id: str) -> ToolState | None: ...


# Mirrors the schedule runner's _MAX_REASON; the runner cannot be imported here.
RESULT_LIMIT = 300
NOTIFIED_CAP = 64 * 1024
_BODY_IDS = 8
_MANAGER_SOURCES = frozenset({"brew", "cask", "pnpm", "uv"})

GitRunner = Callable[[list[str]], str]
GIT_TIMEOUT = 20
INSTALLER_ID = "tools-installer"
_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
NOT_CHECKOUT = "not a git checkout"
NOT_ROOT = "not the checkout root"
PARTIAL_CLONE = "partial clone"
GIT_NOT_FOUND = "git not found"
GIT_TIMEOUT_REASON = "git query timed out"
GIT_FAILED = "git query failed"
ORIGIN_FAILED = "origin query failed"
ORIGIN_NO_MAIN = "origin has no main branch"
ORIGIN_UNEXPECTED = "origin returned an unexpected answer"
SKIP_REASONS = frozenset(
    {
        NOT_CHECKOUT,
        NOT_ROOT,
        PARTIAL_CLONE,
        GIT_NOT_FOUND,
        GIT_TIMEOUT_REASON,
        GIT_FAILED,
        ORIGIN_FAILED,
        ORIGIN_NO_MAIN,
        ORIGIN_UNEXPECTED,
    }
)


def git_for_check(argv: list[str]) -> str:
    """Run a bounded, noninteractive Git query in the caller's process group."""
    return run_git_isolated(
        [
            argv[0],
            "-c",
            "credential.helper=",
            "-c",
            "core.askPass=",
            "-c",
            "http.cookieFile=",
            "-c",
            "http.saveCookies=false",
            "-c",
            "http.extraHeader=",
            *argv[1:],
        ],
        timeout=GIT_TIMEOUT,
        new_session=False,
        env_extra={
            "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",  # SSH cannot prompt.
            "GIT_NO_LAZY_FETCH": "1",  # Do not fetch missing objects.
            "GIT_ASKPASS": "",  # Override any configured askpass program.
        },
    )


def read_notified(path: Path) -> tuple[frozenset[str], bool]:
    try:
        data = read_capped(path, NOTIFIED_CAP, follow_symlinks=False)
    except FileNotFoundError:
        return frozenset(), True
    except OSError:
        return frozenset(), False
    try:
        raw: object = json.loads(data.decode("utf-8")) if data is not None else None
    except (ValueError, RecursionError, OverflowError):
        return frozenset(), False
    if not isinstance(raw, dict):
        return frozenset(), False
    mapping = cast(dict[str, object], raw)
    version = mapping.get("version")
    ids = mapping.get("notified")
    if type(version) is not int or version != 1 or not isinstance(ids, list):
        return frozenset(), False
    values = cast(list[object], ids)
    if not all(isinstance(item, str) and TOOL_ID_RE.fullmatch(item) for item in values):
        return frozenset(), False
    return frozenset(cast(list[str], values)), True


def write_notified(path: Path, ids: Collection[str]) -> None:
    ensure_dir(path.parent)
    data = json.dumps({"version": 1, "notified": sorted(ids)}) + "\n"
    atomic_replace_entry(path, data.encode("utf-8"), mode=0o600)


def fresh_ids(
    tools: Sequence[Tool],
    state_of: Callable[[str], ToolState | None],
    cache_path: Path,
    *,
    started: datetime,
    now: datetime,
    pass_cache: Mapping[str, VersionCacheEntry] | None = None,
    pass_snapshot: ManagerSnapshot | None = None,
) -> frozenset[str]:
    cache = load_version_cache(cache_path) if pass_cache is None else pass_cache
    snapshot = load_manager_snapshot(cache_path) if pass_cache is None else pass_snapshot
    fresh: set[str] = set()
    for tool in tools:
        state = state_of(tool.id)
        if state is None or state.version is None or state.version.stale:
            continue
        entry = cache.get(tool.id)
        value = (
            (
                snapshot.manager_checked_at.get(state.version.source)
                if snapshot is not None
                else None
            )
            if (state.version.source in _MANAGER_SOURCES)
            else (entry.checked_at if entry is not None else None)
        )
        stamp = stamp_time(value, now=now)
        if stamp is not None and stamp >= started:
            fresh.add(tool.id)
    return frozenset(fresh)


def next_set(
    tools: Sequence[Tool],
    state_of: Callable[[str], ToolState | None],
    installer: tuple[bool | None, str | None],
    prior: frozenset[str],
    fresh: frozenset[str],
) -> frozenset[str]:
    """Keep unknowns to avoid re-notifications and stale additions; drop out-of-scope ids."""
    states = [state_of(tool.id) for tool in tools]
    scope = {tool.id for tool in tools} | {INSTALLER_ID}
    confirmed_in = set(outdated_ids(states) & fresh)
    confirmed_out = {
        state.tool_id
        for state in states
        if state is not None
        and (
            state.health in (Health.MISSING, Health.UNAVAILABLE)
            or (
                state.present
                and state.tool_id in fresh
                and state.version is not None
                and state.version.outdated is False
            )
        )
    }
    if installer[0]:
        confirmed_in.add(INSTALLER_ID)
    elif installer[0] is False and installer[1] is None:
        confirmed_out.add(INSTALLER_ID)
    return frozenset(confirmed_in | (prior & (scope - confirmed_in - confirmed_out)))


def message(ids: Collection[str]) -> tuple[str, str]:
    names = sorted(ids)
    count = len(names)
    summary = f"{count} tool update{'' if count == 1 else 's'} available"
    body = ", ".join(names[:_BODY_IDS])
    if count > _BODY_IDS:
        body += f", and {count - _BODY_IDS} more"
    return summary, body


def failed_reason(exc: Exception) -> str:
    del exc
    return "refresh failed"


def result_line(count: int, clauses: Sequence[tuple[str, str]]) -> str:
    prefix = f"ok: {count} updates available"
    reasons = [" ".join(reason_line(reason).split()) for _, reason in clauses]
    fixed = sum(
        len(label) + 2 + (2 if reason else 0)
        for (label, _), reason in zip(clauses, reasons, strict=True)
    )
    reason_count = sum(bool(reason) for reason in reasons)
    share = max(0, (RESULT_LIMIT - len(prefix) - fixed) // reason_count) if reason_count else 0
    return prefix + "".join(
        f"; {label}" + (f": {reason[:share].rstrip()}" if reason and share else "")
        for (label, _), reason in zip(clauses, reasons, strict=True)
    )


def oldest_checked_first(
    tools: Sequence[Tool], cache: Mapping[str, VersionCacheEntry], *, now: datetime
) -> list[Tool]:
    """Put oldest attempts first so recently failed tools rotate to the back."""

    def attempt(tool: Tool) -> datetime:
        try:
            return attempted_at(cache.get(tool.id), now=now) or datetime.min.replace(tzinfo=UTC)
        except (OverflowError, RecursionError):
            return datetime.min.replace(tzinfo=UTC)

    return sorted(tools, key=attempt)


def run_check(
    tools: Sequence[Tool],
    *,
    refresh: Refresher,
    notify: Notifier,
    context: schedules.ScheduleContext,
    git: GitRunner,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> tuple[str, int]:
    started = clock()
    cache = load_version_cache(refresh.cache_path)
    failures: list[str] = []

    def on_failure(tool_id: str, reason: str) -> None:
        del reason
        failures.append(f"lookup failed for {tool_id}")

    try:
        result = refresh.refresh(
            oldest_checked_first(tools, cache, now=started),
            stale_after=CHECK_STALE_AFTER,
            on_failure=on_failure,
        )
    except (CommandError, OSError) as exc:
        return f"failed: {failed_reason(exc)}", 1

    path = schedules.notified_path(context)
    prior, healthy = read_notified(path)
    installer = installer_behind(context.checkout, git)
    states, pass_cache, snapshot = result if result is not None else ({}, {}, None)
    fresh = fresh_ids(
        tools,
        states.get,
        refresh.cache_path,
        started=started,
        now=clock(),
        pass_cache=pass_cache,
        pass_snapshot=snapshot,
    )
    ids = next_set(tools, states.get, installer, prior, fresh)
    clauses: list[tuple[str, str]] = []
    if refresh.warning is not None:
        return result_line(len(prior), [("cache not saved", "")]), 0
    if failures:
        clauses.append((f"{len(failures)} lookups failed", failures[0]))
    if installer[0]:
        clauses.append(("installer behind origin/main", ""))
    elif installer[1] is not None:
        clauses.append(("installer check skipped", installer[1]))
    if not healthy or ids != prior:
        reason = notify(*message(ids)) if ids else None
        if reason is not None:
            clauses.append(("notify skipped", reason))
        else:
            try:
                write_notified(path, ids)
            except OSError:
                clauses.append(("notified set not saved", ""))
    return result_line(len(ids), clauses), 0


def _failure_category(exc: CommandError, default: str) -> str:
    if exc.returncode == 127:
        return GIT_NOT_FOUND
    if exc.returncode == TIMEOUT_CODE:
        return GIT_TIMEOUT_REASON
    return default


def installer_behind(checkout: Path, git: GitRunner) -> tuple[bool | None, str | None]:
    """Compare main with origin using only read-only queries and fixed error categories."""
    base = ["git", "-C", str(checkout)]
    try:
        branch = git([*base, "symbolic-ref", "-q", "HEAD"]).strip()
    except CommandError as exc:
        if exc.returncode == 1:
            return None, None
        return False, _failure_category(exc, NOT_CHECKOUT)
    if branch != "refs/heads/main":
        return None, None
    try:
        toplevel = git([*base, "rev-parse", "--show-toplevel"]).strip()
    except CommandError as exc:
        return False, _failure_category(exc, NOT_CHECKOUT)
    try:
        same_root = Path(toplevel).samefile(checkout)
    except OSError:
        same_root = False
    if not same_root:
        return False, NOT_ROOT
    try:
        head = git([*base, "rev-parse", "HEAD"]).strip()
    except CommandError as exc:
        return False, _failure_category(exc, GIT_FAILED)
    try:
        remote = git([*base, "ls-remote", "origin", "refs/heads/main"])
    except CommandError as exc:
        return False, _failure_category(exc, ORIGIN_FAILED)
    sha = next(
        (
            fields[0]
            for line in remote.splitlines()
            if len(fields := line.split("\t")) == 2 and fields[1] == "refs/heads/main"
        ),
        None,
    )
    if sha is None:
        return False, ORIGIN_NO_MAIN
    if not _SHA.fullmatch(sha):
        return False, ORIGIN_UNEXPECTED
    if sha == head:
        return False, None
    try:
        partial = git(
            [*base, "config", "--get-regexp", r"^(extensions\.partialclone|remote\..*\.promisor)$"]
        )
    except CommandError as exc:
        if exc.returncode != 1:
            return False, _failure_category(exc, GIT_FAILED)
    else:
        if partial:
            return False, PARTIAL_CLONE
    try:
        git([*base, "cat-file", "-e", sha])
    except CommandError as exc:
        if exc.returncode == 1:
            return True, None
        return False, _failure_category(exc, GIT_FAILED)
    try:
        git([*base, "merge-base", "--is-ancestor", sha, "HEAD"])
    except CommandError as exc:
        if exc.returncode == 1:
            return True, None
        return False, _failure_category(exc, GIT_FAILED)
    return False, None
