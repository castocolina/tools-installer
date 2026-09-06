import html
from collections.abc import Mapping
from typing import Any

import pytest
from rich.text import Text
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from installer.catalog_tui import AUDIENCE_LABEL, group_tools, sort_for_table
from installer.deps import resolve_dependencies
from installer.doctor import DoctorReport
from installer.enums import Audience
from installer.model import Method, Tool, load_categories, load_tools
from installer.platform import Platform
from installer.resolve import platform_could_support
from installer.selection import select_tools
from installer.uninstall import SweepResult
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs
from tests.test_registry import REGISTRY


def _unified_app(
    tools: list[Tool],
    installed: Mapping[str, bool],
    blurbs: Mapping[str, str],
    unavailable: Mapping[str, bool] | None = None,
) -> UnifiedApp:
    # The catalog tests exercise only the catalog view; the doctor/guard/fix
    # data is required by the constructor but irrelevant here, so pass neutral
    # defaults.
    return UnifiedApp(
        tools,
        installed,
        blurbs,
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[],
            ban_names=list,
            has_path_block=lambda: False,
            remove=lambda _decision: SweepResult(),
        ),
        policies=PolicyInputs(policies=[]),
        unavailable=unavailable,
    )


def _tool(
    tool_id: str,
    *,
    category: str = "search",
    priority: str = "P1",
    audience: str = "both",
    desc: str = "",
    tier: str = "system",
    requires: tuple[str, ...] = (),
    recommends: tuple[str, ...] = (),
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
        tier=tier,
        requires=requires,
        recommends=recommends,
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
    assert [title for title, _, _ in groups] == ["for AI", "for both", "for human"]
    assert all(detail == title for title, detail, _ in groups)
    assert [t.id for _, _, members in groups for t in members] == ["rg", "fd", "lazygit"]


def test_audience_labels_keep_domain_names():
    assert AUDIENCE_LABEL[Audience.HUMAN] == "human"
    assert "you" not in AUDIENCE_LABEL.values()


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
        assert "for human" in app.catalog.detail_text
        await pilot.press("up")  # onto the "git" section row
        assert app.catalog.detail_text == "git"


async def test_detail_bar_shows_requires_when_declared():
    """A tool with declared dependencies shows a `requires …` slot in the detail
    bar (the no-op seam for the deps PRD); tools without it are unchanged."""
    tools = [_tool("mmdc", desc="mermaid cli")]
    tools[0] = Tool(
        id="mmdc",
        name="mmdc",
        category="search",
        cmd="mmdc",
        methods=(Method(kind="brew", params={"formula": "mmdc"}),),
        tier="system",
        requires=("pnpm", "node"),
    )
    app = _unified_app(tools, {"mmdc": False}, _BLURBS)
    async with app.run_test(size=(100, 30)):
        assert "requires pnpm, node" in app.catalog.detail_text


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


def _tiered_catalog() -> tuple[list[Tool], dict[str, bool]]:
    tools = [
        _tool("pnpm", category="pkg-mgr", priority="P0", tier="system"),
        _tool("jq", category="data", priority="P1", tier="user"),
        _tool("claude", category="ai", priority="P0", tier="ai"),
    ]
    return tools, {tool.id: False for tool in tools}


def test_each_tier_view_lists_only_its_own_tier() -> None:
    tools, installed = _tiered_catalog()
    app = _unified_app(tools, installed, {})
    assert [t.id for t in app.catalog_for("system").tools] == ["pnpm"]
    assert [t.id for t in app.catalog_for("user").tools] == ["jq"]
    assert [t.id for t in app.catalog_for("ai").tools] == ["claude"]
    listed = [t.id for name in ("system", "user", "ai") for t in app.catalog_for(name).tools]
    assert listed == [t.id for t in tools]
    assert len(listed) == len(set(listed))


async def test_staging_spans_tier_views_and_commits_from_any_of_them() -> None:
    tools, installed = _tiered_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")  # System view: marks pnpm
        await pilot.press("3")  # AI view
        await pilot.press("space")  # marks claude
        await pilot.press("enter")
    assert app.return_value == ["pnpm", "claude"]


async def test_select_all_is_scoped_to_the_active_tier_view() -> None:
    tools, installed = _tiered_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")  # System: mark pnpm
        await pilot.press("2")  # User view
        await pilot.press("a")
        assert app.catalog.selected == {"pnpm", "jq"}
        await pilot.press("i")
        assert app.catalog.selected == {"pnpm"}


async def test_tier_view_keeps_the_five_grouping_tabs() -> None:
    tools, installed = _tiered_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")  # User view
        screen = app.catalog_for("user")
        assert screen.view == "category"
        await pilot.press("right")
        assert screen.view == "priority"
        await pilot.press("right")
        assert screen.view == "audience"
        await pilot.press("right")
        assert screen.view == "status"
        await pilot.press("right")
        assert screen.view == "table"
        await pilot.press("right")
        assert screen.view == "category"


def _cross_tier_catalog() -> tuple[list[Tool], dict[str, bool]]:
    tools = [
        _tool("pnpm", category="pkg-mgr", priority="P0", tier="system"),
        _tool("agent", category="ai", priority="P0", tier="ai", requires=("pnpm",)),
    ]
    return tools, {tool.id: False for tool in tools}


async def test_system_tier_dependency_is_announced_from_the_ai_view() -> None:
    tools, installed = _cross_tier_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")  # AI view, never visit System
        await pilot.press("space")
        assert "pnpm" in app.catalog_for("ai").status_text


async def test_unmarking_a_tool_clears_the_dependency_notice() -> None:
    tools, installed = _cross_tier_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.press("space")
        await pilot.press("space")
        assert app.catalog_for("ai").status_text == ""


async def test_already_staged_dependency_is_not_re_announced() -> None:
    tools, installed = _cross_tier_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")  # System: mark pnpm
        await pilot.press("3")  # AI view
        await pilot.press("space")  # mark agent
        assert app.catalog_for("ai").status_text == ""


async def test_dependency_notice_does_not_promise_availability() -> None:
    tools, installed = _cross_tier_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.press("space")
        notice = app.catalog_for("ai").status_text
        assert "agent also needs pnpm" in notice
        assert "added automatically at install time" in notice
        assert "reported when the installer runs" in notice


async def test_selection_made_in_one_tier_view_resolves_against_the_whole_catalog() -> None:
    tools, installed = _cross_tier_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.press("space")
        await pilot.press("enter")
    ids = app.return_value
    assert ids is not None
    assert ids == ["agent"]
    selected = select_tools(tools, ids)
    result = resolve_dependencies(
        selected,
        tools,
        available=lambda _tool: True,
        is_installed=lambda _tool: False,
    )
    assert result.dragged_in == ("pnpm",)
    assert [tool.id for tool in result.order] == ["pnpm", "agent"]


async def test_marking_claude_in_the_ai_view_offers_its_recommends_and_r_stages_them() -> None:
    tools = load_tools(REGISTRY)
    blurbs = load_categories(REGISTRY)
    installed = {tool.id: False for tool in tools}
    app = _unified_app(tools, installed, blurbs)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        screen = app.catalog_for("ai")
        table = screen.query_one(DataTable[Any])
        table.move_cursor(row=table.get_row_index("claude"))
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert "claude pairs well with codegraph, graphify, rtk - press r" in screen.recommends_text
        assert screen.selected == {"claude"}
        await pilot.press("r")
        await pilot.pause()
        assert screen.selected == {"claude", "codegraph", "graphify", "rtk"}
        assert screen.recommends_text == ""


def _recommends_catalog() -> tuple[list[Tool], dict[str, bool]]:
    tools = [
        _tool("pnpm", category="pkg-mgr", priority="P0", tier="system"),
        _tool("jq", category="data", priority="P1", tier="user"),
        _tool("agent", category="ai", priority="P0", tier="ai", recommends=("jq",)),
    ]
    return tools, {tool.id: False for tool in tools}


def _both_lines_catalog() -> tuple[list[Tool], dict[str, bool]]:
    """One mark on `agent` raises both transient lines: a requires notice for
    `pnpm` and a recommends prompt for `jq`."""
    tools = [
        _tool("pnpm", category="pkg-mgr", priority="P0", tier="system"),
        _tool("jq", category="data", priority="P1", tier="user"),
        _tool(
            "agent",
            category="ai",
            priority="P0",
            tier="ai",
            requires=("pnpm",),
            recommends=("jq",),
        ),
    ]
    return tools, {tool.id: False for tool in tools}


async def test_dismissing_the_prompt_leaves_the_selection_untouched() -> None:
    tools, installed = _recommends_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        screen = app.catalog_for("ai")
        assert screen.recommends_text == ""
        assert screen.selected == {"agent"}


async def test_unmarking_the_tool_clears_the_recommends_prompt() -> None:
    tools, installed = _recommends_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        screen = app.catalog_for("ai")
        assert screen.recommends_text == ""
        assert screen.selected == set()


async def test_bulk_select_all_opens_no_recommends_prompt() -> None:
    tools, installed = _recommends_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert "agent" in app.catalog.selected
        assert app.catalog_for("ai").recommends_text == ""


async def test_prompt_is_suppressed_when_every_recommendation_is_already_staged() -> None:
    tools, installed = _recommends_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert app.catalog_for("ai").recommends_text == ""


async def test_pressing_r_with_no_pending_prompt_changes_nothing() -> None:
    tools, installed = _recommends_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("r")
        await pilot.pause()
        assert app.catalog.selected == set()
        assert app.catalog.recommends_text == ""
        assert app.catalog.status_text == ""


async def test_leaving_the_view_clears_the_prompt_and_the_requires_notice() -> None:
    """Both lines describe one selection moment, and navigating away ends it
    (.claude/architecture.md: the prompt "is transient and keeps no per-session
    state"). Regression: they used to survive every view switch, leaving `r`
    armed for a row the cursor and the detail bar no longer described."""
    tools, installed = _both_lines_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        screen = app.catalog_for("ai")
        assert "agent also needs pnpm" in screen.status_text
        assert "agent pairs well with jq" in screen.recommends_text
        await pilot.press("2")  # away to the User view
        await pilot.pause()
        await pilot.press("3")  # and back
        await pilot.pause()
        assert screen.status_text == ""
        assert screen.recommends_text == ""
        # Disarmed, not merely blanked: a stray r must not stage anything.
        await pilot.press("r")
        await pilot.pause()
        assert screen.selected == {"agent"}


async def test_cancelling_the_nav_palette_keeps_the_prompt_and_the_requires_notice() -> None:
    """Opening the palette and escaping out of it is not leaving the view: the
    user ends up on the same view over the same row, so the selection moment
    those two lines describe has not ended. Regression: the clear used to hang
    off `ScreenSuspend`, which fires for a palette push too, so a cancelled
    palette silently blanked both lines and disarmed `r`."""
    tools, installed = _both_lines_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        screen = app.catalog_for("ai")
        await pilot.press("ctrl+p")  # open the nav palette over the AI view
        await pilot.pause()
        await pilot.press("escape")  # and cancel it without navigating
        await pilot.pause()
        assert app.current_view == "ai"
        assert "agent also needs pnpm" in screen.status_text
        assert "agent pairs well with jq" in screen.recommends_text
        # Still armed, not merely still rendered: r must stage the offer.
        await pilot.press("r")
        await pilot.pause()
        assert screen.selected == {"agent", "jq"}


async def test_cancelling_the_nav_palette_keeps_the_empty_selection_warning() -> None:
    """The accept guard's message tells a user who pressed enter with an empty
    batch what to do next; an unrelated palette open/cancel must not wipe it."""
    tools, installed = _recommends_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")  # empty batch -> the guard warns
        await pilot.pause()
        assert "Select at least one tool" in app.catalog.status_text
        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert "Select at least one tool" in app.catalog.status_text


async def test_accept_names_only_the_ids_it_actually_added() -> None:
    """The pending ids are captured when the prompt is raised; the shared staged
    set can move before the accept, so the confirmation must report the delta."""
    tools = [
        _tool("pnpm", category="pkg-mgr", priority="P0", tier="system"),
        _tool("jq", category="data", priority="P1", tier="user"),
        _tool("agent", category="ai", priority="P0", tier="ai", recommends=("jq", "pnpm")),
    ]
    installed = {tool.id: False for tool in tools}
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")  # mark agent: the prompt offers jq and pnpm
        await pilot.pause()
        screen = app.catalog_for("ai")
        assert "pairs well with jq, pnpm" in screen.recommends_text
        screen.selected.add("jq")  # staged another way while the prompt is armed
        await pilot.press("r")
        await pilot.pause()
        assert screen.selected == {"agent", "jq", "pnpm"}
        assert screen.status_text == "added pnpm to your selection."


async def test_accept_claims_nothing_when_the_recommendation_is_already_staged() -> None:
    tools, installed = _recommends_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        screen = app.catalog_for("ai")
        assert "pairs well with jq" in screen.recommends_text
        screen.selected.add("jq")
        await pilot.press("r")
        await pilot.pause()
        assert screen.selected == {"agent", "jq"}
        assert screen.recommends_text == ""
        assert screen.status_text == ""


async def test_accepted_cross_tier_recommendation_shows_marked_on_returning_to_its_tier_view() -> (
    None
):
    # The opening `2` is load-bearing: it forces the User screen to be built
    # and stamped while jq is NOT staged. Without it the User screen's FIRST
    # mount happens after the accept and _row_cells paints [x] from the
    # already-populated shared set, so the test would pass with
    # on_screen_resume deleted.
    tools, installed = _recommends_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        assert "jq" in app.catalog.selected
        user_table = app.catalog_for("user").query_one(DataTable[Any])
        assert user_table.get_cell("jq", "sel").plain == "[x]"


async def test_detail_bar_shows_recommends_when_declared() -> None:
    tools = [
        _tool("claude", recommends=("rg", "fd"), desc="agent"),
        _tool("rg", desc="fast grep"),
    ]
    app = _unified_app(tools, {"claude": False, "rg": False}, _BLURBS)
    async with app.run_test(size=(100, 30)) as pilot:
        assert "pairs well with rg, fd" in app.catalog.detail_text
        await pilot.press("down")
        assert "pairs well with" not in app.catalog.detail_text


async def test_unavailable_catalog_rows_are_inert_under_select_all() -> None:
    tools = [_tool("rg"), _tool("container")]
    installed = {"rg": False, "container": False}
    app = _unified_app(tools, installed, _BLURBS, unavailable={"container": True})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        assert "container" not in app.catalog.selected
        assert app.catalog.selected == {"rg"}


async def test_unavailable_catalog_row_is_dimmed_with_blank_sel_cell() -> None:
    tools = [_tool("container", desc="Apple's native container runtime")]
    app = _unified_app(tools, {"container": False}, _BLURBS, unavailable={"container": True})
    async with app.run_test(size=(100, 30)):
        table = app.catalog.query_one(DataTable[Any])
        sel = table.get_cell("container", "sel")
        desc = table.get_cell("container", "desc")
        assert sel.plain == ""
        assert "dim" in str(sel.style)
        assert "dim" in str(desc.style)
        assert "(not available on this machine)" in desc.plain
        assert "(not available on this machine)" in app.catalog.detail_text


def test_real_apple_containers_unavailable_only_for_genuine_incompatibility() -> None:
    tools = load_tools(REGISTRY)
    intel = Platform(os="macos", arch="amd64", immutable=False, has_brew=True, os_version="26.0")
    fresh = Platform(os="macos", arch="arm64", immutable=False, has_brew=False, os_version="26.0")
    intel_map = {tool.id: not platform_could_support(tool, intel) for tool in tools}
    fresh_map = {tool.id: not platform_could_support(tool, fresh) for tool in tools}
    assert intel_map["container"] is True
    assert fresh_map["container"] is False
    assert fresh_map["gnu-bash"] is False


async def test_unavailable_recommendation_is_not_staged_or_emitted() -> None:
    tools = [
        _tool("agent", category="ai", priority="P0", recommends=("jq",)),
        _tool("jq", category="data", priority="P1"),
    ]
    installed = {tool.id: False for tool in tools}
    app = _unified_app(tools, installed, _BLURBS, unavailable={"jq": True})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert "jq" not in app.catalog.selected

    seeded = _unified_app(tools, installed, _BLURBS, unavailable={"jq": True})
    seeded.catalog.selected.update({"agent", "jq"})
    async with seeded.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")
    assert seeded.return_value == ["agent"]
