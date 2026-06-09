"""Per-tool installed/missing status, computed from an injected check."""

from collections.abc import Callable
from dataclasses import dataclass

from installer.model import Tool
from installer.status import is_installed


@dataclass(frozen=True)
class ToolStatus:
    tool: Tool
    installed: bool


def audit(
    tools: list[Tool],
    is_installed: Callable[[Tool], bool] = is_installed,
) -> list[ToolStatus]:
    """Return each tool paired with whether it is already installed, in order."""
    return [ToolStatus(tool=tool, installed=is_installed(tool)) for tool in tools]
