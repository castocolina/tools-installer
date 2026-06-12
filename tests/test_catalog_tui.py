from typing import Any

import pytest
from rich.text import Text
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from installer.catalog_tui import CatalogApp, group_tools, sort_for_table
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


def _app() -> CatalogApp:
    tools, installed = _catalog()
    return CatalogApp(tools, installed, _BLURBS)


async def test_starts_in_category_view_with_section_rows():
    app = _app()
    async with app.run_test(size=(100, 30)):
        assert app.view == "category"
        table = app.query_one(DataTable[Any])
        assert table.row_count == 5  # 2 section rows + 3 tool rows


async def test_arrow_keys_cycle_views_and_wrap():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("right")
        assert app.view == "priority"
        await pilot.press("left", "left")
        assert app.view == "table"  # wrapped backwards past category


async def test_clicking_a_tab_switches_view():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#status")
        assert app.view == "status"


async def test_space_toggles_tool_rows_and_ignores_section_rows():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")  # cursor starts on the "git" section row -> no-op
        assert app.selected == set()
        await pilot.press("down", "space")  # first tool row: lazygit
        assert app.selected == {"lazygit"}
        await pilot.press("space")  # toggle off again
        assert app.selected == set()


async def test_select_all_and_invert():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("down")  # move to lazygit so cursor/detail survival is meaningful
        await pilot.press("a")
        assert app.selected == {"rg", "fd", "lazygit"}
        # select-all must not reset the cursor or blank the detail bar
        assert "lazygit" in app.detail_text
        assert app.query_one(DataTable[Any]).cursor_row == 1
        await pilot.press("i")
        assert app.selected == set()
        await pilot.press("space", "i")  # space toggles lazygit ON; invert gives {rg, fd}
        assert app.selected == {"rg", "fd"}


async def test_enter_returns_selection_in_catalog_order():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a", "enter")
    assert app.return_value == ["rg", "fd", "lazygit"]


async def test_q_aborts_with_none():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("down", "space", "q")
    assert app.return_value is None


async def test_detail_bar_follows_the_highlighted_row():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.detail_text == ""  # section row highlighted on start
        await pilot.press("down")  # lazygit: empty desc -> falls back to name
        assert "lazygit" in app.detail_text
        assert "P2" in app.detail_text
        assert "for you" in app.detail_text


async def test_header_click_sorts_only_in_table_view():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("left")  # wrap straight to the table view
        assert app.view == "table"
        table = app.query_one(DataTable[Any])
        app.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("tool"), 2, Text("Tool"))
        )
        assert app.table_sort == "id"
        # non-sortable column -> ignored
        app.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("sel"), 0, Text("Sel"))
        )
        assert app.table_sort == "id"
        await pilot.press("right")  # back to category view
        app.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("pri"), 1, Text("Pri"))
        )
        assert app.table_sort == "id"  # ignored outside the table view


async def test_empty_catalog_is_safe():
    app = CatalogApp([], {}, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space", "enter")  # toggle on empty table must not crash
    assert app.return_value == []
