"""Per-tool installed/missing status, computed from an injected check."""

from collections.abc import Callable
from dataclasses import dataclass

from installer.model import Tool
from installer.status import is_installed, macos_stub_reason


@dataclass(frozen=True)
class ToolStatus:
    tool: Tool
    installed: bool
    reason: str | None = None


def audit(
    tools: list[Tool],
    is_installed: Callable[[Tool], bool] = is_installed,
    stub_reason: Callable[[Tool], str | None] = macos_stub_reason,
) -> list[ToolStatus]:
    """Return each tool paired with whether it is already installed, in order.

    The injected ``is_installed`` alone decides installed vs missing (callers may
    fold in repair ids or other policy). ``stub_reason`` runs only for missing
    rows, so an installed tool is never probed twice. When the reason lookup's
    probe now passes, ``reason`` is None and the row reads plain ``missing``.
    On macOS at most one extra stub probe runs per missing stub-only tool;
    ``PROBE_VERSION_TIMEOUT`` bounds a hung probe.
    """
    statuses: list[ToolStatus] = []
    for tool in tools:
        installed = is_installed(tool)
        reason = None if installed else stub_reason(tool)
        statuses.append(ToolStatus(tool=tool, installed=installed, reason=reason))
    return statuses
