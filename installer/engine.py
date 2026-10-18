"""Install a tool by walking its resolved priority ladder until one method works."""

import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from installer import apps, download, executors, receipts
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.enums import InstallStatus
from installer.locations import bin_dir, prepend_path
from installer.model import Method, Tool
from installer.ownership import method_package, method_removal_command
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction, run_post_install
from installer.postinstall import run_postinstall
from installer.resolve import resolve_methods
from installer.run import CommandError, MethodAwareRunner, Runner, run_command
from installer.skill_lifecycle import perform_action
from installer.status import is_installed
from installer.versions import TagResolver, VersionError, release_resolver, resolve_github_tag

Status = InstallStatus
ChecksumPolicy = Literal["fail", "continue"]
_HANDOFF_KINDS = frozenset({"host_setup", "skill_pack"})


def _manager_method(method: Method) -> bool:
    if method.kind in download.DOWNLOAD_KINDS or method.kind in apps.APP_KINDS:
        return False
    return method.kind not in _HANDOFF_KINDS


def _manager_smoke_target(method: Method, cmd: str) -> Path | None:
    raw_bin_dir = method.params.get("bin_dir")
    if isinstance(raw_bin_dir, str) and raw_bin_dir:
        declared = bin_dir(raw_bin_dir) / cmd
        if declared.is_file():
            if os.access(declared, os.X_OK):
                return declared
            return None
    resolved = shutil.which(cmd)
    if resolved is None:
        return None
    return Path(resolved)


def _run_manager_smoke(method: Method, tool: Tool) -> bool:
    """Smoke a manager install's binary; True only when a smoke actually ran."""
    if not _manager_method(method):
        return False
    target = _manager_smoke_target(method, tool.cmd)
    if target is None:
        return False
    executors.smoke_binary(target, executors.method_smoke_argv(method))
    return True


@dataclass(frozen=True, init=False)
class InstallOutcome:
    tool_id: str
    status: Status
    method_kind: str | None = None
    errors: tuple[Exception, ...] = ()
    verified: bool = False
    unverified_reason: str | None = None
    # Only on DEPENDENCY_FAILED: the dependency ids that did not resolve.
    # install_tool never sets it — the engine installs one tool, not a run.
    blocked_by: tuple[str, ...] = ()
    # Populated only when the tool declares a `postinstall` hook AND that
    # hook returned a non-None warning, or raised an exception that was
    # converted to a warning string, or when an earlier method's failed smoke
    # left a package installed (Ledger L-18-16). Never changes `status` away
    # from INSTALLED — the tool's own binary is on PATH and usable regardless.
    postinstall_warning: str | None = None
    # Only on MANUAL_REQUIRED (a host_setup or skill_pack method): reviewed
    # console instructions to run after the installer releases the terminal.
    handoff: tuple[str, ...] = ()
    # Reviewed instruction lines from plural post_install actions. Never
    # executed by the installer; the user runs them after leaving Textual.
    post_install_handoff: tuple[str, ...] = ()

    def __init__(
        self,
        tool_id: str,
        status: Status | str,
        method_kind: str | None = None,
        errors: tuple[Exception, ...] = (),
        verified: bool = False,
        unverified_reason: str | None = None,
        blocked_by: tuple[str, ...] = (),
        postinstall_warning: str | None = None,
        handoff: tuple[str, ...] = (),
        post_install_handoff: tuple[str, ...] = (),
    ) -> None:
        object.__setattr__(self, "tool_id", tool_id)
        object.__setattr__(self, "status", InstallStatus(status))
        object.__setattr__(self, "method_kind", method_kind)
        object.__setattr__(self, "errors", errors)
        object.__setattr__(self, "verified", verified)
        object.__setattr__(self, "unverified_reason", unverified_reason)
        object.__setattr__(self, "blocked_by", blocked_by)
        object.__setattr__(self, "postinstall_warning", postinstall_warning)
        object.__setattr__(self, "handoff", handoff)
        object.__setattr__(self, "post_install_handoff", post_install_handoff)


def _perform(
    tool: Tool, method: Method, ctx: ExecContext
) -> tuple[bool, str | None, tuple[str, ...]]:
    """Route download kinds to the download executor; everything else to a command executor.

    Returns ``(verified, unverified_reason, handoff)``. `verified` is True when
    the download was sha256-verified (non-download methods are never marked
    verified — their package managers do their own checks; pinned or declared
    app zips are sha256-verified). A non-empty `handoff` means the reviewed
    setup must run in a console after the installer releases the terminal (a
    host_setup or skill_pack method never performs its own install here).
    """
    if method.kind in download.DOWNLOAD_KINDS:
        reason = download.install_download(method, ctx)
        return reason is None, reason, ()
    if method.kind in apps.APP_KINDS:
        reason = apps.install_app(method, ctx.runner)
        return reason is None, reason, ()
    if method.kind == "skill_pack":
        outcome = perform_action(tool, "install", ctx.runner)
        return False, None, outcome.instructions
    if method.kind == "host_setup":
        return False, None, executors.host_setup_handoff(method)
    executors.execute(method, ctx.runner)
    return False, None, ()


def install_tool(
    tool: Tool,
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    *,
    checksum_policy: ChecksumPolicy = "fail",
    tools: Mapping[str, Tool] | None = None,
    confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    repair: bool = False,
    present: Callable[[Tool], bool] | None = None,
) -> InstallOutcome:
    """Try each applicable method in ladder order; stop at the first success.

    A checksum mismatch halts the ladder by default (the security signal must
    not silently degrade to another channel); checksum_policy="continue"
    restores ordinary fall-through and is only ever set by an explicit user
    choice.

    `tools` is the full loaded catalog, keyed by id — required only when
    `tool.postinstall` names a hook that needs to check another host's
    presence; `None` is safe for any `Tool` with `postinstall=None`,
    including every existing call site and test predating this phase.

    After a method succeeds, a tool declaring `postinstall` is dispatched
    immediately, before this function returns; a postinstall problem is
    carried on `postinstall_warning` and it never turns this INSTALLED outcome into a failure.
    Declared `post_install` actions are dispatched next, producing reviewed
    instruction lines on `post_install_handoff`. `confirm_sensitive_action` is
    the optional confirmation callback those actions consult; `None` is the
    unattended case and skips them. The ALREADY_INSTALLED short-circuit never
    dispatches postinstall or post_install at all.

    `repair` exists for D-18's broken state. It takes the identical ladder a
    fresh install takes, and is only ever set for a tool the user explicitly
    selected while it read broken. A present tool whose method declares
    `refuses_existing` instead skips that method and dispatches its reviewed
    post-install actions without writing a receipt.

    Manager kinds are smoke-run once after a successful install when a runnable
    target exists: an executable ``<bin_dir>/<cmd>`` names the method's own
    binary; a present but non-executable file there means nothing to smoke; a
    missing one falls back to ``shutil.which(tool.cmd)`` (in a repair run,
    possibly an older copy on PATH). A failed smoke falls through; the package
    stays installed and is reported with its removal command, never removed
    (SPEC REG-05 covers installer-created links only; Ledger L-18-16).

    A success writes the tool's receipt (`receipts.record`) before any hook
    runs; a failed write is a warning on `postinstall_warning`, never FAILED.

    `present` decides the ALREADY_INSTALLED short-circuit: the composition
    root passes the refresh service's presence (D-04, wired in plan 19-18);
    `None` keeps `is_installed`, looked up at call time.
    """
    installed = present(tool) if present is not None else is_installed(tool)
    if installed and not repair:
        return InstallOutcome(tool.id, InstallStatus.ALREADY_INSTALLED)

    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, InstallStatus.NO_METHOD)

    ctx = ExecContext(
        runner=runner,
        platform=platform,
        resolve_release=release_resolver(resolve_tag),
    )
    errors: list[Exception] = []
    leftovers: list[str] = []
    for method in methods:
        if installed and repair and method.params.get("refuses_existing") is True:
            post_install_handoff, warning = _dispatch_post_install(
                tool, platform, confirm_sensitive_action
            )
            return InstallOutcome(
                tool.id,
                InstallStatus.MANUAL_REQUIRED,
                method_kind=method.kind,
                handoff=(
                    f"{tool.id}: its installer refuses to run over an existing install, "
                    "so it was not re-run.",
                ),
                postinstall_warning=warning,
                post_install_handoff=post_install_handoff,
            )
        if isinstance(runner, MethodAwareRunner):
            runner.method_started(method.kind)
        path_before = os.environ.get("PATH", "")
        try:
            verified, unverified_reason, handoff = _perform(tool, method, ctx)
            if handoff:
                return InstallOutcome(
                    tool.id,
                    InstallStatus.MANUAL_REQUIRED,
                    method_kind=method.kind,
                    handoff=handoff,
                )
            raw_bin_dir = method.params.get("bin_dir")
            if isinstance(raw_bin_dir, str) and raw_bin_dir:
                prepend_path(bin_dir(raw_bin_dir))
            try:
                smoked = _run_manager_smoke(method, tool)
            except executors.ExecutorError as exc:
                os.environ["PATH"] = path_before
                removal = method_removal_command(method, tool.cmd)
                tail = (
                    "remove it with that installer's own uninstaller"
                    if removal is None
                    else f"remove it with `{removal}`"
                )
                leftover = (
                    f"{method.kind} left {tool.cmd} installed after its smoke run failed; {tail}"
                )
                leftovers.append(leftover)
                raise executors.ExecutorError(f"{exc}; {leftover}") from exc
        except ChecksumMismatch as exc:
            if checksum_policy == "fail":
                return InstallOutcome(
                    tool.id, InstallStatus.CHECKSUM_MISMATCH, method_kind=method.kind, errors=(exc,)
                )
            errors.append(exc)
        except (CommandError, executors.ExecutorError, VersionError, OSError) as exc:
            errors.append(exc)
        else:
            # An app is smoked only when it declares a cli (_stage_and_swap_app);
            # a receipt must not claim a check that never ran (IN-04). Download
            # kinds always smoke before their link swap.
            smoked_artifact = method.kind in download.DOWNLOAD_KINDS or (
                method.kind in apps.APP_KINDS and method.params.get("cli") is not None
            )
            try:
                receipts.record(
                    tool,
                    method,
                    package=method_package(method),
                    smoke="ok" if smoked_artifact or smoked else None,
                )
            except OSError as exc:
                leftovers.append(f"install receipt not written: {exc}")
            warning = None
            if tool.postinstall:
                try:
                    warning = run_postinstall(tool.postinstall, method, runner, tools or {})
                except Exception as exc:  # noqa: BLE001 -- isolation boundary, see design_decisions
                    warning = f"postinstall hook {tool.postinstall!r} crashed: {exc}"
            post_install_handoff, crash = _dispatch_post_install(
                tool, platform, confirm_sensitive_action
            )
            if crash:
                warning = f"{warning}; {crash}" if warning else crash
            if leftovers:
                joined = "; ".join(leftovers)
                warning = f"{warning}; {joined}" if warning else joined
            return InstallOutcome(
                tool.id,
                InstallStatus.INSTALLED,
                method_kind=method.kind,
                verified=verified,
                unverified_reason=unverified_reason,
                postinstall_warning=warning,
                post_install_handoff=post_install_handoff,
            )
    return InstallOutcome(tool.id, InstallStatus.FAILED, errors=tuple(errors))


def _dispatch_post_install(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[tuple[str, ...], str | None]:
    if not tool.post_install:
        return (), None
    try:
        return run_post_install(tool, platform, confirm), None
    except Exception as exc:  # noqa: BLE001 -- isolation boundary, see design_decisions
        return (), f"post-install actions crashed: {exc}"
