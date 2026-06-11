"""Turn the tool catalog and audit into selectable choices, and back to tools."""

from dataclasses import dataclass, field

from installer.audit import ToolStatus
from installer.model import Tool


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    checked: bool
    tag: str = field(default="")  # short status suffix (state/count), colored at the IO boundary
    description: str = field(default="")  # hover text for the highlighted row


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


def category_choices(tools: list[Tool], blurbs: dict[str, str] | None = None) -> list[Choice]:
    """One unchecked choice per category: count as tag, blurb + tool ids on hover."""
    blurbs = blurbs or {}
    choices: list[Choice] = []
    for category in categories(tools):
        members = tools_in(tools, category)
        unit = "tool" if len(members) == 1 else "tools"
        ids = ", ".join(tool.id for tool in members)
        blurb = blurbs.get(category, "")
        description = f"{blurb} — {ids}" if blurb else ids
        choices.append(
            Choice(
                id=category,
                label=category,
                checked=False,
                tag=f"{len(members)} {unit}",
                description=description,
            )
        )
    return choices


def _is_verified_download(tool: Tool) -> bool:
    return any("checksum" in method.params for method in tool.methods)


def tool_choices(statuses: list[ToolStatus]) -> list[Choice]:
    """One choice per tool; missing tools are pre-checked, installed ones are not."""
    choices: list[Choice] = []
    for status in statuses:
        tool = status.tool
        head = f"{tool.id} — {tool.desc}" if tool.desc else tool.id
        state = "installed" if status.installed else "missing"
        parts = [tool.desc] if tool.desc else []
        if _is_verified_download(tool):
            parts.append("sha256-verified download")
        # Pre-check the tools the user still needs (missing), not the ones present.
        choices.append(
            Choice(
                id=tool.id,
                label=head,
                checked=not status.installed,
                tag=state,
                description=" · ".join(parts),
            )
        )
    return choices


def select_tools(tools: list[Tool], ids: list[str]) -> list[Tool]:
    """Tools whose id was selected, in catalog order; unknown ids are ignored."""
    wanted = set(ids)
    return [tool for tool in tools if tool.id in wanted]
