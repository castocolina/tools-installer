from installer.audit import ToolStatus
from installer.model import Method, Tool
from installer.selection import (
    Choice,
    categories,
    category_choices,
    select_tools,
    tool_choices,
    tools_in,
)


def _tool(tool_id: str, category: str, desc: str = "") -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        desc=desc,
    )


def test_categories_are_unique_in_first_seen_order() -> None:
    tools = [_tool("rg", "search"), _tool("jq", "data"), _tool("fd", "search")]
    assert categories(tools) == ["search", "data"]


def test_tools_in_filters_by_category() -> None:
    tools = [_tool("rg", "search"), _tool("jq", "data"), _tool("fd", "search")]
    assert [t.id for t in tools_in(tools, "search")] == ["rg", "fd"]


def test_tools_in_unknown_category_is_empty() -> None:
    assert tools_in([_tool("rg", "search")], "ghost") == []


def test_category_choices_count_tools_and_start_unchecked() -> None:
    tools = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    assert category_choices(tools) == [
        Choice(id="search", label="search (2 tools)", checked=False),
        Choice(id="data", label="data (1 tool)", checked=False),
    ]


def test_tool_choices_precheck_missing_only() -> None:
    tools = [_tool("rg", "search", desc="fast grep"), _tool("fd", "search")]
    statuses = [
        ToolStatus(tool=tools[0], installed=True),
        ToolStatus(tool=tools[1], installed=False),
    ]
    assert tool_choices(statuses) == [
        Choice(id="rg", label="rg — fast grep (installed)", checked=False),
        Choice(id="fd", label="fd (missing)", checked=True),
    ]


def test_select_tools_keeps_catalog_order_and_ignores_unknown_ids() -> None:
    tools = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    assert [t.id for t in select_tools(tools, ["jq", "rg", "ghost"])] == ["rg", "jq"]
