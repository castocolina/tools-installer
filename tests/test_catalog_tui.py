import pytest

from installer.catalog_tui import group_tools, sort_for_table
from installer.model import Method, Tool


def _tool(
    tool_id: str,
    *,
    category: str = "search",
    priority: str = "P1",
    audience: str = "both",
    desc: str = "",
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority=priority,
        audience=audience,
        desc=desc,
    )


_BLURBS = {"search": "Find files and code at speed"}


def _catalog() -> tuple[list[Tool], dict[str, bool]]:
    tools = [
        _tool("rg", priority="P0", audience="ai", desc="fast grep"),
        _tool("fd", priority="P1", audience="both", desc="file finder"),
        _tool("lazygit", category="git", priority="P2", audience="human"),
    ]
    installed = {"rg": True, "fd": False, "lazygit": False}
    return tools, installed


def test_group_by_priority_orders_tiers_and_drops_empty():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "priority", _BLURBS)
    assert [title for title, _ in groups] == [
        "P0 · essential",
        "P1 · recommended",
        "P2 · nice-to-have",
    ]  # no P3 tools -> tier dropped
    assert [t.id for _, members in groups for t in members] == ["rg", "fd", "lazygit"]


def test_group_by_audience_uses_labels():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "audience", _BLURBS)
    assert [title for title, _ in groups] == ["for AI", "for both", "for you"]
    assert [t.id for _, members in groups for t in members] == ["rg", "fd", "lazygit"]


def test_group_by_status_splits_missing_then_installed():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "status", _BLURBS)
    assert groups[0][0] == "missing"
    assert [t.id for t in groups[0][1]] == ["fd", "lazygit"]
    assert groups[1][0] == "installed"
    assert [t.id for t in groups[1][1]] == ["rg"]


def test_group_by_category_is_alphabetical_with_blurb_titles():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "category", _BLURBS)
    # "git" has no blurb -> plain title; "search" has one -> appended.
    assert [title for title, _ in groups] == [
        "git",
        "search — Find files and code at speed",
    ]
    # within a group: priority then id
    assert [t.id for t in groups[1][1]] == ["rg", "fd"]


def test_sort_for_table_by_each_key():
    tools, installed = _catalog()
    assert [t.id for t in sort_for_table(tools, installed, "id")] == ["fd", "lazygit", "rg"]
    assert [t.id for t in sort_for_table(tools, installed, "priority")] == [
        "rg",
        "fd",
        "lazygit",
    ]
    assert [t.id for t in sort_for_table(tools, installed, "category")] == [
        "lazygit",
        "rg",
        "fd",
    ]
    assert [t.id for t in sort_for_table(tools, installed, "audience")] == [
        "rg",
        "fd",
        "lazygit",
    ]  # ai < both < human alphabetically
    assert [t.id for t in sort_for_table(tools, installed, "installed")] == [
        "fd",
        "lazygit",
        "rg",
    ]  # missing first, then installed


def test_group_tools_rejects_unknown_view():
    tools, installed = _catalog()
    with pytest.raises(ValueError, match="unknown view"):
        group_tools(tools, installed, "table", _BLURBS)
