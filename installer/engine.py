"""Install a tool by walking its resolved priority ladder until one method works."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from installer import apps, download, executors
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.enums import InstallStatus
from installer.model import Method, Tool
from installer.platform import Platform
from installer.postinstall import run_postinstall
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner, run_command
from installer.status import is_installed
from installer.versions import TagResolver, VersionError, resolve_github_tag

Status = InstallStatus
ChecksumPolicy = Literal["fail", "continue"]


@dataclass(frozen=True, init=False)
class InstallOutcome:
    tool_id: str
    status: Status
    method_kind: str | None = None
    errors: tuple[Exception, ...] = ()
    verified: bool = False
    # Only on DEPENDENCY_FAILED: the dependency ids that did not resolve.
    # install_tool never sets it — the engine installs one tool, not a run.
    blocked_by: tuple[str, ...] = ()
    # Populated only when the tool declares a `postinstall` hook AND that
    # hook returned a non-None warning, or raised an exception that was
    # converted to a warning string. Never changes `status` away from
    # INSTALLED — the tool's own binary is on PATH and usable regardless.
    postinstall_warning: str | None = None

    def __init__(
        self,
        tool_id: str,
        status: Status | str,
        method_kind: str | None = None,
        errors: tuple[Exception, ...] = (),
        verified: bool = False,
        blocked_by: tuple[str, ...] = (),
        postinstall_warning: str | None = None,
    ) -> None:
        object.__setattr__(self, "tool_id", tool_id)
        object.__setattr__(self, "status", InstallStatus(status))
        object.__setattr__(self, "method_kind", method_kind)
        object.__setattr__(self, "errors", errors)
        object.__setattr__(self, "verified", verified)
        object.__setattr__(self, "blocked_by", blocked_by)
        object.__setattr__(self, "postinstall_warning", postinstall_warning)


def _perform(method: Method, ctx: ExecContext) -> bool:
    """Route download kinds to the download executor; everything else to a command executor.

    Returns True when the download was sha256-verified (non-download methods
    are never marked verified — their package managers do their own checks;
    app zips have no published checksums to verify).
    """
    if method.kind in download.DOWNLOAD_KINDS:
        return download.install_download(method, ctx)
    if method.kind in apps.APP_KINDS:
        apps.install_app(method, ctx.runner)
        return False
    executors.execute(method, ctx.runner)
    return False


def install_tool(
    tool: Tool,
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    *,
    checksum_policy: ChecksumPolicy = "fail",
    tools: Mapping[str, Tool] | None = None,
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
    The ALREADY_INSTALLED short-circuit never dispatches postinstall at all
    (D-01's single-direction trigger).
    """
    if is_installed(tool):
        return InstallOutcome(tool.id, InstallStatus.ALREADY_INSTALLED)

    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, InstallStatus.NO_METHOD)

    ctx = ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)
    errors: list[Exception] = []
    for method in methods:
        try:
            verified = _perform(method, ctx)
        except ChecksumMismatch as exc:
            if checksum_policy == "fail":
                return InstallOutcome(
                    tool.id, InstallStatus.CHECKSUM_MISMATCH, method_kind=method.kind, errors=(exc,)
                )
            errors.append(exc)
        except (CommandError, executors.ExecutorError, VersionError) as exc:
            errors.append(exc)
        else:
            warning = None
            if tool.postinstall:
                try:
                    warning = run_postinstall(tool.postinstall, method, runner, tools or {})
                except Exception as exc:  # noqa: BLE001 -- isolation boundary, see design_decisions
                    warning = f"postinstall hook {tool.postinstall!r} crashed: {exc}"
            return InstallOutcome(
                tool.id,
                InstallStatus.INSTALLED,
                method_kind=method.kind,
                verified=verified,
                postinstall_warning=warning,
            )
    return InstallOutcome(tool.id, InstallStatus.FAILED, errors=tuple(errors))
