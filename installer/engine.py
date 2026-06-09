"""Install a tool by walking its resolved priority ladder until one method works."""

from dataclasses import dataclass
from typing import Literal

from installer import download, executors
from installer.download import ExecContext
from installer.model import Method, Tool
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner, run_command
from installer.status import is_installed
from installer.versions import VersionError, VersionResolver, resolve_github_version

Status = Literal["already-installed", "installed", "no-method", "failed"]


@dataclass(frozen=True)
class InstallOutcome:
    tool_id: str
    status: Status
    method_kind: str | None = None
    errors: tuple[Exception, ...] = ()


def _perform(method: Method, ctx: ExecContext) -> None:
    """Route download kinds to the download executor; everything else to a command executor."""
    if method.kind in download.DOWNLOAD_KINDS:
        download.install_download(method, ctx)
    else:
        executors.execute(method, ctx.runner)


def install_tool(
    tool: Tool,
    platform: Platform,
    runner: Runner = run_command,
    resolve_version: VersionResolver = resolve_github_version,
) -> InstallOutcome:
    """Try each applicable method in ladder order; stop at the first success."""
    if is_installed(tool):
        return InstallOutcome(tool.id, "already-installed")

    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, "no-method")

    ctx = ExecContext(runner=runner, platform=platform, resolve_version=resolve_version)
    errors: list[Exception] = []
    for method in methods:
        try:
            _perform(method, ctx)
            return InstallOutcome(tool.id, "installed", method_kind=method.kind)
        except (CommandError, executors.ExecutorError, VersionError) as exc:
            errors.append(exc)
    return InstallOutcome(tool.id, "failed", errors=tuple(errors))
