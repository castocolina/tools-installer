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
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from installer import apps, download, executors
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.executors import ExecutorError
from installer.locations import applications_dir
from installer.model import Method, Tool
from installer.ownership import MUTATION_GRADE, ManagerOwnership
from installer.platform import Platform
from installer.pnpm_globals import PnpmUnavailable
from installer.postinstall import run_postinstall
from installer.run import CommandError, Runner
from installer.versions import TagResolver, VersionError

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
    except Exception as exc:  # noqa: BLE001 -- isolation boundary, mirrors engine.py
        return f"postinstall hook {hook!r} crashed: {exc}"
