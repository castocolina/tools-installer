import html
from collections.abc import Mapping
from typing import Any

import pytest
from rich.text import Text
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from installer.catalog_tui import group_tools, sort_for_table
from installer.doctor import DoctorReport
from installer.model import Method, Tool
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs


def _unified_app(
    tools: list[Tool], installed: Mapping[str, bool], blurbs: Mapping[str, str]
) -> UnifiedApp:
    # The catalog tests exercise only the catalog view; the doctor/guard/fix
    # data is required by the constructor but irrelevant here, so pass neutral
    # defaults.
    return UnifiedApp(
        tools,
        installed,
        blurbs,
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status={},
        guard_warning=None,
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            removable=[], ban_names=[], has_path_block=False, remove=lambda _decision: None
        ),
        policies=PolicyInputs(policies=[]),
    )


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
    assert [title for title, _, _ in groups] == ["P0", "P1", "P2"]  # no P3 tools -> dropped
    assert [detail for _, detail, _ in groups] == [
        "P0 · essential",
        "P1 · recommended",
        "P2 · nice-to-have",
    ]
    assert [t.id for _, _, members in groups for t in members] == ["rg", "fd", "lazygit"]


def test_group_by_audience_uses_labels():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "audience", _BLURBS)
    assert [title for title, _, _ in groups] == ["for AI", "for both", "for you"]
    assert all(detail == title for title, detail, _ in groups)
    assert [t.id for _, _, members in groups for t in members] == ["rg", "fd", "lazygit"]


def test_group_by_status_splits_missing_then_installed():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "status", _BLURBS)
    assert groups[0][:2] == ("missing", "missing")
    assert [t.id for t in groups[0][2]] == ["fd", "lazygit"]
    assert groups[1][:2] == ("installed", "installed")
    assert [t.id for t in groups[1][2]] == ["rg"]


def test_group_by_category_keeps_titles_short_and_blurbs_in_detail():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "category", _BLURBS)
    # "git" has no blurb -> detail is the plain name; "search" has one -> appended.
    assert [(title, detail) for title, detail, _ in groups] == [
        ("git", "git"),
        ("search", "search — Find files and code at speed"),
    ]
    # within a group: priority then id
    assert [t.id for t in groups[1][2]] == ["rg", "fd"]


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


def _app() -> UnifiedApp:
    tools, installed = _catalog()
    return _unified_app(tools, installed, _BLURBS)


async def test_starts_in_category_view_with_section_rows():
    app = _app()
    async with app.run_test(size=(100, 30)):
        assert app.catalog.view == "category"
        table = app.query_one(DataTable[Any])
        assert table.row_count == 5  # 2 section rows + 3 tool rows


async def test_arrow_keys_cycle_views_and_wrap():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("right")
        assert app.catalog.view == "priority"
        await pilot.press("left", "left")
        assert app.catalog.view == "table"  # wrapped backwards past category


async def test_clicking_a_tab_switches_view():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#status")
        assert app.catalog.view == "status"


async def test_cursor_starts_on_first_tool_row_not_a_section_header():
    app = _app()  # category view: rows are [#git, lazygit, #search, rg, fd]
    async with app.run_test(size=(100, 30)) as pilot:
        # The first selectable row (lazygit) is highlighted, so the first
        # `space` toggles a tool instead of being a silent no-op on a header.
        await pilot.press("space")
        assert app.catalog.selected == {"lazygit"}


async def test_space_ignores_section_rows():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("up")  # from lazygit onto the "git" section row
        await pilot.press("space")  # section row -> no-op
        assert app.catalog.selected == set()
        await pilot.press("down", "space")  # back to lazygit
        assert app.catalog.selected == {"lazygit"}
        await pilot.press("space")  # toggle off again
        assert app.catalog.selected == set()


async def test_select_all_and_invert():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        # cursor already starts on lazygit (the first tool row)
        await pilot.press("a")
        assert app.catalog.selected == {"rg", "fd", "lazygit"}
        # select-all must not reset the cursor or blank the detail bar
        assert "lazygit" in app.catalog.detail_text
        assert app.query_one(DataTable[Any]).cursor_row == 1
        await pilot.press("i")
        assert app.catalog.selected == set()
        await pilot.press("space", "i")  # space toggles lazygit ON; invert gives {rg, fd}
        assert app.catalog.selected == {"rg", "fd"}


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


async def test_ctrl_c_aborts_with_none():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+c")
        # The binding must have triggered exit() — app must no longer be running
        # before the context manager closes it.  Without the priority binding,
        # ctrl+c fires the system help_quit action (shows a hint, does NOT exit)
        # and is_running stays True here.
        assert not app.is_running
    assert app.return_value is None


async def test_detail_bar_follows_the_highlighted_row():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        # lazygit is highlighted on start: empty desc -> falls back to name
        assert "lazygit" in app.catalog.detail_text
        assert "P2" in app.catalog.detail_text
        assert "for you" in app.catalog.detail_text
        await pilot.press("up")  # onto the "git" section row
        assert app.catalog.detail_text == "git"


async def test_section_row_detail_shows_the_group_blurb():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("down")  # from lazygit onto the "search" section row
        assert app.catalog.detail_text == "search — Find files and code at speed"


_WIDE_DESC = "finds files fast while respecting your gitignore rules"


def _screen_text(app: UnifiedApp) -> str:
    """The painted screen as plain text (the SVG export NBSP-encodes spaces)."""
    return html.unescape(app.export_screenshot()).replace("\xa0", " ")


def _wide_catalog() -> tuple[list[Tool], dict[str, bool]]:
    tools = [
        _tool("rg", priority="P0", audience="ai", desc="recursive grep, fast"),
        _tool("fd", priority="P1", desc=_WIDE_DESC),
    ]
    return tools, {"rg": True, "fd": False}


async def test_view_switch_repaints_cells_at_full_width():
    # Regression: after clear(columns=True) + re-add, DataTable kept serving
    # render caches measured at the old column widths, truncating every cell
    # to its header width until some cell mutation flushed them.
    tools, installed = _wide_catalog()
    app = _unified_app(tools, installed, _BLURBS)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("right")  # category -> priority rebuilds the table
        assert _WIDE_DESC in _screen_text(app)


async def test_section_titles_do_not_inflate_the_sel_column():
    # Regression: the full "category — blurb" title used to live in the section
    # row's first cell, widening Sel to the title length and squeezing the
    # description column off the screen.
    tools, installed = _wide_catalog()
    blurbs = {"search": "Find files and code at speed across very large source trees"}
    app = _unified_app(tools, installed, blurbs)
    async with app.run_test(size=(120, 30)):
        assert _WIDE_DESC in _screen_text(app)


async def test_header_click_sorts_only_in_table_view():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("left")  # wrap straight to the table view
        assert app.catalog.view == "table"
        table = app.query_one(DataTable[Any])
        app.catalog.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("tool"), 2, Text("Tool"))
        )
        assert app.catalog.table_sort == "id"
        # non-sortable column -> ignored
        app.catalog.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("sel"), 0, Text("Sel"))
        )
        assert app.catalog.table_sort == "id"
        await pilot.press("right")  # back to category view
        app.catalog.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("pri"), 1, Text("Pri"))
        )
        assert app.catalog.table_sort == "id"  # ignored outside the table view


async def test_enter_with_empty_selection_is_a_no_op():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")  # nothing selected
        assert app.is_running  # did not exit / return a selection
        assert "Select at least one tool" in app.catalog.status_text


async def test_status_message_clears_once_a_tool_is_selected():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")  # empty -> warning shown
        assert "Select at least one tool" in app.catalog.status_text
        await pilot.press("space")  # select the highlighted tool
        assert app.catalog.status_text == ""


async def test_empty_catalog_enter_is_blocked_then_aborts():
    app = _unified_app([], {}, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")  # toggle on empty table must not crash
        await pilot.press("enter")  # no tools -> blocked, must not crash
        assert app.is_running
        await pilot.press("q")
    assert app.return_value is None
