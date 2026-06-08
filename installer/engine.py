"""Install a tool by walking its resolved priority ladder until one method works."""

from dataclasses import dataclass
from typing import Literal

from installer.executors import ExecutorError, execute
from installer.model import Tool
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner, run_command
from installer.status import is_installed

Status = Literal["already-installed", "installed", "no-method", "failed"]


@dataclass(frozen=True)
class InstallOutcome:
    tool_id: str
    status: Status
    method_kind: str | None = None
    errors: tuple[Exception, ...] = ()


def install_tool(tool: Tool, platform: Platform, runner: Runner = run_command) -> InstallOutcome:
    """Try each applicable method in ladder order; stop at the first success."""
    if is_installed(tool):
        return InstallOutcome(tool.id, "already-installed")

    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, "no-method")

    errors: list[Exception] = []
    for method in methods:
        try:
            execute(method, runner)
            return InstallOutcome(tool.id, "installed", method_kind=method.kind)
        except (CommandError, ExecutorError) as exc:
            errors.append(exc)
    return InstallOutcome(tool.id, "failed", errors=tuple(errors))
