"""Install a tool by walking its resolved priority ladder until one method works."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from installer import apps, download, executors
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.enums import InstallStatus
from installer.locations import bin_dir, prepend_path
from installer.model import Method, Tool
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
    # converted to a warning string. Never changes `status` away from
    # INSTALLED — the tool's own binary is on PATH and usable regardless.
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
    verified — their package managers do their own checks; app zips have no
    published checksums to verify). A non-empty `handoff` means the reviewed
    setup must run in a console after the installer releases the terminal (a
    host_setup or skill_pack method never performs its own install here).
    """
    if method.kind in download.DOWNLOAD_KINDS:
        reason = download.install_download(method, ctx)
        return reason is None, reason, ()
    if method.kind in apps.APP_KINDS:
        apps.install_app(method, ctx.runner)
        return False, None, ()
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
    dispatches postinstall or post_install at all. `reapply_post_install` is
    the separate, explicit-selection-only entry point (D-20).

    `repair` exists for D-18's broken state. It takes the identical ladder a
    fresh install takes, and is only ever set for a tool the user explicitly
    selected while it read broken.
    """
    if is_installed(tool) and not repair:
        return InstallOutcome(tool.id, InstallStatus.ALREADY_INSTALLED)

    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, InstallStatus.NO_METHOD)

    ctx = ExecContext(
        runner=runner,
        platform=platform,
        resolve_tag=resolve_tag,
        resolve_release=release_resolver(resolve_tag),
    )
    errors: list[Exception] = []
    for method in methods:
        if isinstance(runner, MethodAwareRunner):
            runner.method_started(method.kind)
        try:
            verified, unverified_reason, handoff = _perform(tool, method, ctx)
        except ChecksumMismatch as exc:
            if checksum_policy == "fail":
                return InstallOutcome(
                    tool.id, InstallStatus.CHECKSUM_MISMATCH, method_kind=method.kind, errors=(exc,)
                )
            errors.append(exc)
        except (CommandError, executors.ExecutorError, VersionError) as exc:
            errors.append(exc)
        else:
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


def reapply_post_install(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> InstallOutcome:
    """Dispatch post_install for one explicit re-selection. Not an install.

    install_tool still returns before this table on ALREADY_INSTALLED. Callers
    must pass only a tool the user selected while it was already installed.
    """
    handoff, warning = _dispatch_post_install(tool, platform, confirm)
    return InstallOutcome(
        tool.id,
        InstallStatus.ALREADY_INSTALLED,
        postinstall_warning=warning,
        post_install_handoff=handoff,
    )
