"""Install a tool by walking its resolved priority ladder until one method works."""

from dataclasses import dataclass
from typing import Literal

from installer import apps, download, executors
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.enums import InstallStatus
from installer.model import Method, Tool
from installer.platform import Platform
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

    def __init__(
        self,
        tool_id: str,
        status: Status | str,
        method_kind: str | None = None,
        errors: tuple[Exception, ...] = (),
        verified: bool = False,
    ) -> None:
        object.__setattr__(self, "tool_id", tool_id)
        object.__setattr__(self, "status", InstallStatus(status))
        object.__setattr__(self, "method_kind", method_kind)
        object.__setattr__(self, "errors", errors)
        object.__setattr__(self, "verified", verified)


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
) -> InstallOutcome:
    """Try each applicable method in ladder order; stop at the first success.

    A checksum mismatch halts the ladder by default (the security signal must
    not silently degrade to another channel); checksum_policy="continue"
    restores ordinary fall-through and is only ever set by an explicit user
    choice.
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
            return InstallOutcome(
                tool.id, InstallStatus.INSTALLED, method_kind=method.kind, verified=verified
            )
        except ChecksumMismatch as exc:
            if checksum_policy == "fail":
                return InstallOutcome(
                    tool.id, InstallStatus.CHECKSUM_MISMATCH, method_kind=method.kind, errors=(exc,)
                )
            errors.append(exc)
        except (CommandError, executors.ExecutorError, VersionError) as exc:
            errors.append(exc)
    return InstallOutcome(tool.id, InstallStatus.FAILED, errors=tuple(errors))
