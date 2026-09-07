"""Ownership-first update dispatch.

This module never indexes `resolve_methods(tool, platform)[0]` for provenance.
`resolve_methods` ordering is install preference, not which manager actually
placed the tool — `rg` declares `github_release` (rank 20) ahead of `brew`
(rank 40), so a brew-installed copy would otherwise be re-downloaded into
`~/.local/bin`. Callers construct an `UpdateTarget` from a resolved
`ManagerOwnership`; `perform_update` only acts on that evidence.

It also never imports `installer.engine`. `install_tool` short-circuits on
`is_installed` with `ALREADY_INSTALLED` and would perform no action for a
tool that is already present — exactly the case an update exists to handle.

pnpm-owned tools do not get a `pnpm update -g` argv, and they do not get
`pnpm update -g --latest` either:

1. Ordinary `pnpm update -g <pkg>` respects the package's declared semver
   range rather than moving to latest. 12-RESEARCH.md:221's live report shows
   `current == wanted == 11.9.0` while `latest == 12.3.4`, so a plain update
   would report success and change nothing while the Ver cell still said
   outdated.
2. `--latest` would ignore that range, but it would also ignore THIS
   project's own registry pins (`mmdc`'s `versions = { puppeteer = "^25" }`),
   which exist to keep a peer-dependency pair inside a working range.
3. Either way a bare pnpm argv bypasses everything
   `installer/executors.py::_node` does around the install: the comma-joined
   co-install GROUP that keeps `mmdc` and `puppeteer` in one shared install
   group, the `--allow-build` allowances without which puppeteer's browser
   download is silently skipped, the minimum-pnpm floor for grouping and
   allow-build, the minimum-Node floor, and the smoke check. The registry's
   only `node`-kind tools are exactly `mmdc` and `puppeteer`, and both
   declare all of those fields.

A pnpm-owned update therefore dispatches `executors.execute` with the owning
`node` method — the same entry point an install takes — so those invariants
cannot drift apart.

An installer-owned `script` method is also the vendor's own documented update
path, and it is the only update mechanism such a tool has, so it reuses
`executors.execute` rather than inventing a second script runner.

`should_replay_node_globals` is true only when `tool.id == "pnpm"`, whatever
that tool's owner turns out to be. REQUIREMENTS.md's
REQ-pnpm-global-reinstall-mitigation says "reinstall it together in one
invocation after `pnpm` itself updates". 12-REVIEWS.md:137 flagged replaying
after every node-package update as a significant unrequested secondary
mutation, since `reinstall_node_globals` deliberately includes globals
unknown to this registry. pnpm itself installs through a vendor `script` or
through `brew` and has no `node` method, so the trigger keys on the TOOL,
not on the manager performing the update.

Ordering contract: when `should_replay_node_globals` returns True, the
caller (`UpdateService.run`, Plan 12-03 Task 3) captures the pnpm-managed
package set BEFORE running the update, because the update is the very event
that can lose it. A post-update snapshot of a wiped global set would make
`reinstall_node_globals` a silent no-op.

Every subprocess argv is a Python list handed to `runner`. Formula, cask,
npm, and pypi identifiers come only from `ownership.package` (trusted
registry data) — never from a cached version string, a manager's reported
"latest", or a GitHub tag.

`UpdateService` is the TUI-facing coordinator. Display can be cheap and
cached (Plan 12-02's manager snapshot, up to MANAGER_STALE_AFTER old);
mutation cannot. `run` therefore re-resolves ownership for the one tool
being updated via the injected `reresolve_ownership` seam BEFORE any
capture or mutation, and uses that fresh result — never the caller-supplied
cached `target.ownership` — to authorise the update. The production
implementation in `setup.py` pays one real, timeout-bounded manager
subprocess round-trip at mutation time, the same cost an install already
pays per tool.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal, Protocol

from installer import apps, download, executors
from installer import ownership as ownership_mod
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.executors import ExecutorError
from installer.locations import applications_dir
from installer.model import Method, Tool
from installer.ownership import MUTATION_GRADE, ManagerOwnership
from installer.platform import Platform
from installer.pnpm_globals import PnpmUnavailable
from installer.postinstall import run_postinstall
from installer.run import CommandError, Runner, run_captured
from installer.versions import TagResolver, VersionError, resolve_github_tag

PostinstallFn = Callable[[str, Method, Runner, Mapping[str, Tool]], str | None]

_FALLBACK_UNKNOWN = "no manager claimed this tool"
_SDKMAN_DETAIL = "SDKMAN updates use `sdk upgrade <candidate>`, which this phase does not implement"


class UpdateError(RuntimeError):
    """The update path could not be constructed or was called incorrectly."""


@dataclass(frozen=True)
class UpdateTarget:
    """A tool plus the ownership evidence that authorises mutating it.

    Construction is the caller's job; `perform_update` never resolves
    ownership itself, so the mutating path can only act on evidence that was
    already gathered from artifacts, inventories, and live PATH attribution.
    """

    tool: Tool
    ownership: ManagerOwnership


@dataclass(frozen=True)
class UpdateOutcome:
    tool_id: str
    status: Literal["updated", "failed", "unknown-owner", "unsupported"]
    owner: str
    detail: str = ""
    errors: tuple[Exception, ...] = ()
    postinstall_warning: str | None = None
    replayed_globals: tuple[str, ...] = ()
    cleanup_warnings: tuple[str, ...] = ()


def resolve_update_argv(target: UpdateTarget) -> list[str] | None:
    """Manager argv for brew/cask/uv; None for pnpm and installer (sentinels).

    `"unknown"` is never a valid call: `perform_update` short-circuits first.
    """
    owner = target.ownership.owner
    if owner == "unknown":
        raise UpdateError("resolve_update_argv must not be called with owner='unknown'")
    if owner in ("pnpm", "installer"):
        return None
    package = target.ownership.package
    if not isinstance(package, str) or not package:
        raise UpdateError(f"ownership.package is required for a {owner} update")
    if owner == "brew":
        return ["brew", "upgrade", package]
    if owner == "cask":
        return ["brew", "upgrade", "--cask", f"--appdir={applications_dir()}", package]
    if owner == "uv":
        return ["uv", "tool", "upgrade", package]
    raise UpdateError(f"no update argv for owner {owner!r}")


def should_replay_node_globals(target: UpdateTarget) -> bool:
    """True only when the tool being updated is pnpm itself.

    See the module docstring for REQUIREMENTS.md wording and the
    capture-before-update ordering contract this predicate implies.
    """
    return target.tool.id == "pnpm"


def perform_update(
    target: UpdateTarget,
    *,
    platform: Platform,
    runner: Runner,
    resolve_tag: TagResolver,
    tools: Mapping[str, Tool],
    postinstall: PostinstallFn = run_postinstall,
) -> UpdateOutcome:
    """Dispatch an update on resolved ownership. Never raises.

    Refuses anything whose `owner` is `unknown` or whose `confidence` is not
    in the imported `MUTATION_GRADE` frozenset, with zero subprocess and zero
    filesystem write. The refusal detail is `ownership.unknown_reason`.
    """
    ownership = target.ownership
    try:
        return _perform(
            target,
            platform=platform,
            runner=runner,
            resolve_tag=resolve_tag,
            tools=tools,
            postinstall=postinstall,
        )
    except (
        CommandError,
        ExecutorError,
        VersionError,
        ChecksumMismatch,
        UpdateError,
        PnpmUnavailable,
        OSError,
    ) as exc:
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="failed",
            owner=ownership.owner,
            detail=str(exc),
            errors=(exc,),
        )


def _perform(
    target: UpdateTarget,
    *,
    platform: Platform,
    runner: Runner,
    resolve_tag: TagResolver,
    tools: Mapping[str, Tool],
    postinstall: PostinstallFn,
) -> UpdateOutcome:
    ownership = target.ownership
    if ownership.owner == "unknown" or ownership.confidence not in MUTATION_GRADE:
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="unknown-owner",
            owner=ownership.owner,
            detail=ownership.unknown_reason or _FALLBACK_UNKNOWN,
        )
    method = ownership.method
    if method is not None and method.kind == "sdkman":
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="unsupported",
            owner=ownership.owner,
            detail=_SDKMAN_DETAIL,
        )
    owner = ownership.owner
    cleanup_warnings: tuple[str, ...] = ()
    if owner in ("brew", "cask", "uv"):
        argv = resolve_update_argv(target)
        if argv is None:
            raise UpdateError(f"missing argv for {owner} update")
        runner(argv)
    elif owner == "pnpm":
        if method is None:
            raise UpdateError("pnpm-owned update requires a resolved node method")
        executors.execute(method, runner)
    elif owner == "installer":
        cleanup_warnings = _update_installer_owned(
            method, platform=platform, runner=runner, resolve_tag=resolve_tag
        )
    else:
        raise UpdateError(f"unsupported owner {owner!r}")
    warning = _run_postinstall(target, method, runner, tools, postinstall)
    return UpdateOutcome(
        tool_id=target.tool.id,
        status="updated",
        owner=owner,
        postinstall_warning=warning,
        cleanup_warnings=cleanup_warnings,
    )


def _update_installer_owned(
    method: Method | None,
    *,
    platform: Platform,
    runner: Runner,
    resolve_tag: TagResolver,
) -> tuple[str, ...]:
    if method is None:
        raise UpdateError("installer-owned update requires a resolved method")
    if method.kind in download.DOWNLOAD_KINDS:
        result = download.update_download(
            method, ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)
        )
        return result.warnings
    if method.kind in apps.APP_KINDS:
        result = apps.update_app(method, runner)
        return result.warnings
    if method.kind == "script":
        executors.execute(method, runner)
        return ()
    raise UpdateError(f"no installer-owned update path for method kind '{method.kind}'")


def _run_postinstall(
    target: UpdateTarget,
    method: Method | None,
    runner: Runner,
    tools: Mapping[str, Tool],
    postinstall: PostinstallFn,
) -> str | None:
    hook = target.tool.postinstall
    if not hook:
        return None
    if method is None:
        return f"postinstall hook {hook!r} skipped: no owning method"
    try:
        return postinstall(hook, method, runner, tools)
    except Exception as extra:  # noqa: BLE001 -- isolation boundary, mirrors engine.py
        return f"postinstall hook {hook!r} crashed: {extra}"


class InvalidateFn(Protocol):
    def __call__(self, *, reason: str) -> int: ...


ManagedPackagesFn = Callable[[], tuple[str, ...] | None]
ReplayGlobalsFn = Callable[[Sequence[str]], tuple[str, ...]]
ReresolveFn = Callable[[Tool], ManagerOwnership]


class UpdateService:
    """In-flight-guarded update coordinator shared by all three catalog screens.

    `begin`/`end` are the explicit concurrency guard: `exclusive=True` on a
    Textual Worker cancels the Worker but cannot stop a thread already inside
    `subprocess.run`. A second `u` press while the first update holds the
    latch is a no-op that names the in-flight tool.

    `run` order is load-bearing, not an implementation detail:
    0. Fresh ownership re-resolution (never the 6-hour cached snapshot).
    1. Pre-capture the pnpm-managed package set when the tool is pnpm itself.
    2. Mutate via `perform_update`.
    3. Replay the captured snapshot only after `updated`.
    4. Invalidate the version-refresh epoch and manager snapshot.

    The capture cannot follow the update: if the pnpm self-update is the
    event that loses the globals, a post-update `managed_packages()` returns
    an empty or shortened list, and `reinstall_node_globals` returns `()`
    immediately for an empty list — so the recovery would report success
    while restoring nothing.
    """

    def __init__(
        self,
        *,
        platform: Platform,
        runner: Runner = run_captured,
        resolve_tag: TagResolver = resolve_github_tag,
        tools: Mapping[str, Tool],
        managed_packages: ManagedPackagesFn,
        replay_globals: ReplayGlobalsFn,
        reresolve_ownership: ReresolveFn,
        invalidate: InvalidateFn | None = None,
    ) -> None:
        self.platform = platform
        self._runner = runner
        self._resolve_tag = resolve_tag
        self._tools = tools
        self._managed_packages = managed_packages
        self._replay_globals = replay_globals
        self._reresolve_ownership = reresolve_ownership
        self._invalidate = invalidate
        self._lock = threading.Lock()
        self._in_flight: str | None = None

    @property
    def in_flight(self) -> str | None:
        return self._in_flight

    def begin(self, tool_id: str) -> bool:
        with self._lock:
            if self._in_flight is not None:
                return False
            self._in_flight = tool_id
            return True

    def end(self) -> None:
        with self._lock:
            self._in_flight = None

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        """Re-resolve, pre-capture, mutate, replay, invalidate — in that order."""
        fresh = self._reresolve_ownership(target.tool)
        if fresh.owner == "unknown" or fresh.confidence not in ownership_mod.MUTATION_GRADE:
            return UpdateOutcome(
                tool_id=target.tool.id,
                status="unknown-owner",
                owner=fresh.owner,
                detail=fresh.unknown_reason or _FALLBACK_UNKNOWN,
            )
        fresh_target = UpdateTarget(tool=target.tool, ownership=fresh)
        snapshot: tuple[str, ...] | None = None
        snapshot_unknown = False
        if should_replay_node_globals(fresh_target):
            captured = self._managed_packages()
            if captured is None:
                snapshot_unknown = True
            else:
                snapshot = tuple(captured)
        outcome = perform_update(
            fresh_target,
            platform=self.platform,
            runner=self._runner,
            resolve_tag=self._resolve_tag,
            tools=self._tools,
        )
        detail = outcome.detail
        replayed: tuple[str, ...] = ()
        if snapshot_unknown:
            warning = (
                "pnpm's global set could not be listed before the update; nothing was replayed"
            )
            detail = f"{detail}; {warning}" if detail else warning
        if outcome.status == "updated" and snapshot:
            try:
                replayed = tuple(self._replay_globals(snapshot))
            except Exception as extra:  # noqa: BLE001 -- secondary mutation, never downgrades updated
                warning = f"pnpm globals replay failed: {extra}"
                detail = f"{detail}; {warning}" if detail else warning
        if outcome.status == "updated" and self._invalidate is not None:
            self._invalidate(reason=f"updated {target.tool.id}")
        if detail == outcome.detail and replayed == outcome.replayed_globals:
            return outcome
        return replace(outcome, detail=detail, replayed_globals=replayed)
