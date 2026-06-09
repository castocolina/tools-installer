"""Turn the tool catalog and audit into selectable choices, and back to tools."""

from dataclasses import dataclass

from installer.audit import ToolStatus
from installer.model import Tool


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    checked: bool


def categories(tools: list[Tool]) -> list[str]:
    """Distinct categories in first-seen order."""
    seen: list[str] = []
    for tool in tools:
        if tool.category not in seen:
            seen.append(tool.category)
    return seen


def tools_in(tools: list[Tool], category: str) -> list[Tool]:
    """Tools belonging to one category, in catalog order."""
    return [tool for tool in tools if tool.category == category]


def category_choices(tools: list[Tool]) -> list[Choice]:
    """One unchecked choice per category, labelled with its tool count."""
    choices: list[Choice] = []
    for category in categories(tools):
        count = len(tools_in(tools, category))
        unit = "tool" if count == 1 else "tools"
        choices.append(Choice(id=category, label=f"{category} ({count} {unit})", checked=False))
    return choices


def tool_choices(statuses: list[ToolStatus]) -> list[Choice]:
    """One choice per tool; missing tools are pre-checked, installed ones are not."""
    choices: list[Choice] = []
    for status in statuses:
        tool = status.tool
        head = f"{tool.id} — {tool.desc}" if tool.desc else tool.id
        state = "installed" if status.installed else "missing"
        # Pre-check the tools the user still needs (missing), not the ones present.
        choices.append(Choice(id=tool.id, label=f"{head} ({state})", checked=not status.installed))
    return choices


def select_tools(tools: list[Tool], ids: list[str]) -> list[Tool]:
    """Tools whose id was selected, in catalog order; unknown ids are ignored."""
    wanted = set(ids)
    return [tool for tool in tools if tool.id in wanted]
