import html
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from rich.text import Text
from textual.binding import Binding
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from installer.catalog_tui import (
    _COLUMNS,  # pyright: ignore[reportPrivateUsage]
    AUDIENCE_LABEL,
    CatalogScreen,
    VersionStatusRefreshed,
    group_tools,
    sort_for_table,
)
from installer.deps import resolve_dependencies
from installer.doctor import DoctorReport
from installer.enums import Audience
from installer.manager_versions import OutdatedReport
from installer.model import Method, Tool, load_categories, load_tools
from installer.ownership import ManagerInventory, ManagerOwnership, Owner, OwnershipCandidate
from installer.platform import Platform
from installer.resolve import platform_could_support
from installer.run import CommandError
from installer.selection import select_tools
from installer.uninstall import SweepResult
from installer.update import UpdateService
from installer.version_cache import VersionCacheEntry, save_version_cache
from installer.version_status import VersionRefreshService, VersionStatus
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs
from tests.test_registry import REGISTRY


def _unified_app(
    tools: list[Tool],
    installed: Mapping[str, bool],
    blurbs: Mapping[str, str],
    unavailable: Mapping[str, bool] | None = None,
    version_refresh: VersionRefreshService | None = None,
    updates: UpdateService | None = None,
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
        version_refresh=version_refresh,
        updates=updates,
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


def _screen(
    tools: list[Tool],
    installed: Mapping[str, bool],
    version_refresh: VersionRefreshService | None = None,
    updates: UpdateService | None = None,
) -> CatalogScreen:
    return CatalogScreen(
        tools,
        installed,
        _BLURBS,
        view="system",
        catalog=list(tools),
        staged=set(),
        version_refresh=version_refresh,
        updates=updates,
    )


def _status(*, stale: bool) -> VersionStatus:
    return VersionStatus(
        tool_id="rg",
        installed="1.2.0",
        latest="v1.6.0",
        outdated=True,
        stale=stale,
        source="github",
    )


def test_catalog_columns_include_ver() -> None:
    assert len(_COLUMNS) == 8
    assert _COLUMNS[5] == ("Inst", "inst")
    assert _COLUMNS[6] == ("Ver", "ver")
    assert _COLUMNS[7] == ("What it does", "desc")


def test_row_cells_both_branches_return_eight_cells() -> None:
    tool = _tool("rg")
    screen = _screen([tool], {"rg": True})
    assert len(screen._row_cells(tool)) == 8  # pyright: ignore[reportPrivateUsage]
    screen._unavailable["rg"] = True  # pyright: ignore[reportPrivateUsage]
    assert len(screen._row_cells(tool)) == 8  # pyright: ignore[reportPrivateUsage]


def test_stale_marker_is_visible_on_rendered_ver_cell() -> None:
    tool = _tool("rg")
    screen = _screen([tool], {"rg": True})
    screen._version_statuses = {"rg": _status(stale=False)}  # pyright: ignore[reportPrivateUsage]
    fresh = screen._ver_cell(tool).plain  # pyright: ignore[reportPrivateUsage]
    screen._version_statuses = {"rg": _status(stale=True)}  # pyright: ignore[reportPrivateUsage]
    stale = screen._ver_cell(tool).plain  # pyright: ignore[reportPrivateUsage]
    assert stale != fresh
    assert stale.endswith(" ~")
    assert not fresh.endswith(" ~")


def test_epoch_guard_drops_a_superseded_version_refresh(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1.6.0",
        probe_output=lambda argv: "1.2.0",
    )
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    screen._version_refresh_generation = 1  # pyright: ignore[reportPrivateUsage]
    service.invalidate(reason="test")
    screen.on_version_status_refreshed(
        VersionStatusRefreshed({"rg": _status(stale=False)}, generation=1, epoch=0)
    )
    assert screen._version_statuses == {}  # pyright: ignore[reportPrivateUsage]


_MANAGED = Path("/tmp/tools-installer-bin")


def _empty_inventory(**_kwargs: object) -> ManagerInventory:
    return ManagerInventory(
        brew_formulae={},
        brew_casks={},
        pnpm_globals=frozenset(),
        uv_tools={},
        brew_prefix=None,
    )


def _empty_outdated(**_kwargs: object) -> OutdatedReport:
    return OutdatedReport(brew={}, cask={}, pnpm={}, uv={})


def _offline_service(
    cache_path: Path,
    *,
    resolve_tag: Callable[[str], str],
    probe_output: Callable[[list[str]], str | None],
    now: Callable[[], datetime] | None = None,
) -> VersionRefreshService:
    return VersionRefreshService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        cache_path=cache_path,
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        now=now,
        managed_bin_dir=_MANAGED,
        which=lambda cmd: str(_MANAGED / cmd),
        artifacts_for=lambda tool: [_MANAGED / tool.cmd],
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        query=lambda *_a, **_k: "",
    )


def _gh_tool(tool_id: str, *, desc: str = "") -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="github_release", params={"repo": f"owner/{tool_id}"}),),
        priority="P1",
        audience="both",
        desc=desc,
        tier="system",
    )


async def test_unparseable_probe_output_renders_unknown(tmp_path: Path) -> None:
    tool = _gh_tool("dasel")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v2.8.0",
        probe_output=lambda argv: "Usage: dasel <command>",
    )
    app = _unified_app([tool], {"dasel": True}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        for _ in range(400):
            if "dasel" in app.catalog._version_statuses:  # pyright: ignore[reportPrivateUsage]
                break
            await pilot.pause()
        cell = app.catalog.query_one(DataTable[Any]).get_cell("dasel", "ver")
        assert cell.plain == "unknown"


async def test_stale_and_fresh_rows_differ_only_by_trailing_marker() -> None:
    stale_status = VersionStatus(
        tool_id="rg",
        installed="15.2.0",
        latest="15.2.0",
        outdated=False,
        stale=True,
        source="github",
    )
    fresh_status = VersionStatus(
        tool_id="fd",
        installed="15.2.0",
        latest="15.2.0",
        outdated=False,
        stale=False,
        source="github",
    )
    unknown_status = VersionStatus(
        tool_id="dasel",
        installed=None,
        latest=None,
        outdated=None,
        stale=True,
        source="github",
    )
    rg = _gh_tool("rg")
    fd = _gh_tool("fd")
    dasel = _gh_tool("dasel")
    screen = _screen([rg, fd, dasel], {"rg": True, "fd": True, "dasel": True})
    screen._version_statuses = {  # pyright: ignore[reportPrivateUsage]
        "rg": stale_status,
        "fd": fresh_status,
        "dasel": unknown_status,
    }
    stale_cell = screen._ver_cell(rg).plain  # pyright: ignore[reportPrivateUsage]
    fresh_cell = screen._ver_cell(fd).plain  # pyright: ignore[reportPrivateUsage]
    unknown_cell = screen._ver_cell(dasel).plain  # pyright: ignore[reportPrivateUsage]
    assert stale_cell == fresh_cell + " ~"
    assert not fresh_cell.endswith(" ~")
    assert unknown_cell == "unknown"
    assert " ~" not in unknown_cell


async def test_budget_deferred_row_renders_stale_marker(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    save_version_cache(
        path,
        {
            "fresh": VersionCacheEntry(
                latest_version="1.0.0",
                checked_at=now.isoformat(),
                failed_at=None,
            ),
            "stale": VersionCacheEntry(
                latest_version="1.0.0",
                checked_at=(now - timedelta(days=8)).isoformat(),
                failed_at=(now - timedelta(hours=1)).isoformat(),
            ),
        },
    )
    service = _offline_service(
        path,
        resolve_tag=lambda repo: "1.0.0",
        probe_output=lambda argv: "1.0.0",
        now=lambda: now,
    )
    tools = [_gh_tool("fresh"), _gh_tool("stale")]
    app = _unified_app(tools, {"fresh": True, "stale": True}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        for _ in range(400):
            statuses = app.catalog._version_statuses  # pyright: ignore[reportPrivateUsage]
            if "fresh" in statuses and "stale" in statuses:
                break
            await pilot.pause()
        table = app.catalog.query_one(DataTable[Any])
        fresh = table.get_cell("fresh", "ver").plain
        stale = table.get_cell("stale", "ver").plain
        assert stale.endswith(" ~")
        assert not fresh.endswith(" ~")


def _ownership(
    tool: Tool,
    *,
    owner: Owner,
    shadowed: bool = False,
    unknown_reason: str | None = None,
    active_path: Path | None = None,
    candidates: tuple[OwnershipCandidate, ...] = (),
    package: str | None = None,
) -> ManagerOwnership:
    if not candidates:
        candidates = (
            OwnershipCandidate(
                owner=owner,
                method=tool.methods[0] if tool.methods else None,
                package=package,
                current_version=None,
                evidence="test",
            ),
        )
    return ManagerOwnership(
        tool_id=tool.id,
        owner=owner,
        method=tool.methods[0] if tool.methods else None,
        package=package,
        current_version=None,
        confidence="none" if owner == "unknown" else "direct",
        shadowed=shadowed,
        candidates=candidates,
        active_candidate=None if owner == "unknown" else owner,
        active_path=active_path,
        unknown_reason=unknown_reason,
    )


def test_detail_line_names_homebrew_for_brew_owned_row(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {"rg": _ownership(tool, owner="brew")}  # pyright: ignore[reportPrivateUsage]
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    screen._version_statuses = {  # pyright: ignore[reportPrivateUsage]
        "rg": VersionStatus(
            tool_id="rg",
            installed="14.1.0",
            latest="14.1.1",
            outdated=True,
            stale=False,
            source="brew",
        )
    }
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "Homebrew" in text


def test_detail_line_names_competing_manager_and_active_path(tmp_path: Path) -> None:
    tool = _tool("rg")
    path = Path("/opt/homebrew/bin/rg")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {  # pyright: ignore[reportPrivateUsage]
        "rg": _ownership(
            tool,
            owner="brew",
            shadowed=True,
            active_path=path,
            candidates=(
                OwnershipCandidate(
                    owner="installer",
                    method=None,
                    package=None,
                    current_version=None,
                    evidence="artifact",
                ),
                OwnershipCandidate(
                    owner="brew",
                    method=tool.methods[0],
                    package="ripgrep",
                    current_version="14.1.0",
                    evidence="inventory",
                ),
            ),
        )
    }
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "installer" in text
    assert str(path) in text


def test_unknown_owner_detail_contains_unknown_reason(tmp_path: Path) -> None:
    tool = _tool("rg")
    reason = "the brew inventory could not be read"
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {  # pyright: ignore[reportPrivateUsage]
        "rg": _ownership(tool, owner="unknown", unknown_reason=reason)
    }
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    screen._version_statuses = {  # pyright: ignore[reportPrivateUsage]
        "rg": VersionStatus(
            tool_id="rg",
            installed="14.1.0",
            latest=None,
            outdated=None,
            stale=True,
            source="unknown",
        )
    }
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert reason in text
    cell = screen._ver_cell(tool)  # pyright: ignore[reportPrivateUsage]
    assert cell.plain == "unknown"
    assert " ~" not in cell.plain
    assert "re-check is pending" not in text


def test_pinned_spec_appears_in_detail_line(tmp_path: Path) -> None:
    tool = _tool("mmdc")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {"mmdc": _ownership(tool, owner="pnpm")}  # pyright: ignore[reportPrivateUsage]
    screen = _screen([tool], {"mmdc": True}, version_refresh=service)
    screen._version_statuses = {  # pyright: ignore[reportPrivateUsage]
        "mmdc": VersionStatus(
            tool_id="mmdc",
            installed="11.0.0",
            latest="11.1.0",
            outdated=True,
            stale=False,
            source="pnpm",
            pinned_spec="puppeteer ^25",
        )
    }
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "puppeteer ^25" in text


def test_stale_latest_has_marker_and_detail_explanation(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {"rg": _ownership(tool, owner="brew")}  # pyright: ignore[reportPrivateUsage]
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=True,
        source="brew",
    )
    fresh_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    screen._version_statuses = {"rg": stale_status}  # pyright: ignore[reportPrivateUsage]
    stale_cell = screen._ver_cell(tool).plain  # pyright: ignore[reportPrivateUsage]
    stale_detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert stale_cell.endswith(" ~")
    assert "re-check is pending" in stale_detail
    screen._version_statuses = {"rg": fresh_status}  # pyright: ignore[reportPrivateUsage]
    fresh_cell = screen._ver_cell(tool).plain  # pyright: ignore[reportPrivateUsage]
    fresh_detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert not fresh_cell.endswith(" ~")
    assert "re-check is pending" not in fresh_detail


def test_installer_no_repo_detail_explains_undetermined_latest(tmp_path: Path) -> None:
    tool = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(Method(kind="script", params={"url": "https://get.pnpm.io/install.sh"}),),
    )
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {  # pyright: ignore[reportPrivateUsage]
        "pnpm": _ownership(tool, owner="installer")
    }
    screen = _screen([tool], {"pnpm": True}, version_refresh=service)
    screen._version_statuses = {  # pyright: ignore[reportPrivateUsage]
        "pnpm": VersionStatus(
            tool_id="pnpm",
            installed="11.9.0",
            latest=None,
            outdated=None,
            stale=True,
            source="installer",
        )
    }
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "cannot be determined" in text
    assert "up to date" not in text.lower()


def _update_service(reresolve: Callable[[Tool], ManagerOwnership]) -> UpdateService:
    return UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=lambda _cmd: None,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=reresolve,
    )


def test_update_binding_exists_and_is_shown() -> None:
    keys = {
        binding.key: binding for binding in CatalogScreen.BINDINGS if isinstance(binding, Binding)
    }
    assert "u" in keys
    assert keys["u"].show is True
    assert keys["u"].action == "update_tool"


def test_action_update_tool_skips_confirmed_current(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {"rg": ownership}  # pyright: ignore[reportPrivateUsage]
    started: list[str] = []
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"rg": True}, version_refresh=service, updates=updates)
    screen._version_statuses = {  # pyright: ignore[reportPrivateUsage]
        "rg": VersionStatus(
            tool_id="rg",
            installed="14.1.1",
            latest="14.1.1",
            outdated=False,
            stale=False,
            source="brew",
        )
    }
    screen._browser.highlighted_id = lambda: "rg"  # type: ignore[method-assign]
    screen._update_tool_worker = lambda tool_id: started.append(tool_id)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert started == []


def test_action_update_tool_refuses_non_mutation_grade(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(
        tool, owner="unknown", unknown_reason="the brew inventory could not be read"
    )
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {"rg": ownership}  # pyright: ignore[reportPrivateUsage]
    started: list[str] = []
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"rg": True}, version_refresh=service, updates=updates)
    screen._version_statuses = {  # pyright: ignore[reportPrivateUsage]
        "rg": VersionStatus(
            tool_id="rg",
            installed="14.1.0",
            latest="14.1.1",
            outdated=True,
            stale=False,
            source="unknown",
        )
    }
    screen._browser.highlighted_id = lambda: "rg"  # type: ignore[method-assign]
    screen._update_tool_worker = lambda tool_id: started.append(tool_id)  # type: ignore[method-assign]
    messages: list[str] = []
    screen.status.set = lambda text, severity: messages.append(text)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert started == []
    assert any("brew inventory" in message for message in messages)


def test_action_update_tool_starts_worker_when_outdated_is_none(tmp_path: Path) -> None:
    tool = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(Method(kind="script", params={"url": "https://get.pnpm.io/install.sh"}),),
    )
    ownership = ManagerOwnership(
        tool_id="pnpm",
        owner="installer",
        method=tool.methods[0],
        package=None,
        current_version=None,
        confidence="by-elimination",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service._ownership = {"pnpm": ownership}  # pyright: ignore[reportPrivateUsage]
    started: list[str] = []
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"pnpm": True}, version_refresh=service, updates=updates)
    screen._version_statuses = {  # pyright: ignore[reportPrivateUsage]
        "pnpm": VersionStatus(
            tool_id="pnpm",
            installed="11.9.0",
            latest=None,
            outdated=None,
            stale=True,
            source="installer",
        )
    }
    screen._browser.highlighted_id = lambda: "pnpm"  # type: ignore[method-assign]

    def fake_worker(tool_id: str) -> None:
        started.append(tool_id)

    screen._update_tool_worker = fake_worker  # type: ignore[method-assign]
    screen.status.set = lambda text, severity: None  # type: ignore[method-assign]
    screen.action_update_tool()
    assert started == ["pnpm"]


# -- end-to-end `u`-press pipeline: keypress -> UpdateService.run() -> status
# line, driven through a real Pilot with the worker's own message loop, so
# `_update_tool_worker`/`on_tool_updated` run for real rather than being
# stubbed out. Only the runner/manager-query seams are fake; nothing here
# spawns a real subprocess. -----------------------------------------------


async def _wait_until(pilot: Any, predicate: Callable[[], bool], tries: int = 400) -> None:
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause()
    raise AssertionError("condition never became true within the polling budget")


def _outdated_status(tool_id: str, *, source: str = "brew") -> VersionStatus:
    return VersionStatus(
        tool_id=tool_id,
        installed="1.0.0",
        latest="1.0.1",
        outdated=True,
        stale=False,
        source=source,
    )


async def _mount_and_settle(app: UnifiedApp, pilot: Any) -> None:
    """Let the on_mount version-refresh worker finish before a test overrides
    `_version_statuses`/`service._ownership` directly -- otherwise the real
    refresh (which runs concurrently on mount) can clobber the test's fixture
    state with its own resolution of a fake, unrecognised inventory."""
    await _wait_until(pilot, lambda: not app.catalog.version_refreshing)


async def test_update_success_renders_new_version_on_status_line(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=lambda _argv: None,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _unified_app([tool], {"rg": True}, _BLURBS, version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service._ownership = {"rg": ownership}  # pyright: ignore[reportPrivateUsage]
        app.catalog._version_statuses = {  # pyright: ignore[reportPrivateUsage]
            "rg": _outdated_status("rg")
        }
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating rg" not in app.catalog.status_text)
        assert "updated rg" in app.catalog.status_text
        assert "update failed" not in app.catalog.status_text


async def test_update_success_reports_replay_cleanup_and_postinstall_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import installer.update as update_module
    from installer.download import ExecContext, UpdateExecResult
    from installer.postinstall import POSTINSTALL_HOOKS

    monkeypatch.setitem(
        POSTINSTALL_HOOKS,
        "fake-warn-hook",
        lambda method, runner, tools: "postinstall shim needs manual review",
    )

    def fake_update_download(_method: Method, _ctx: ExecContext) -> UpdateExecResult:
        return UpdateExecResult(verified=True, warnings=("removed a stale cache entry",))

    monkeypatch.setattr(
        update_module.download,
        "update_download",
        fake_update_download,
    )

    tool = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(Method(kind="github_release", params={"repo": "pnpm/pnpm"}),),
        tier="system",
        postinstall="fake-warn-hook",
    )
    ownership = ManagerOwnership(
        tool_id="pnpm",
        owner="installer",
        method=tool.methods[0],
        package=None,
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate="installer",
        active_path=None,
        unknown_reason=None,
    )
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v2",
        probe_output=lambda argv: "2.0",
    )
    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=lambda _argv: None,
        resolve_tag=lambda _repo: "v2",
        tools={"pnpm": tool},
        managed_packages=lambda: ("typescript", "eslint"),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _unified_app([tool], {"pnpm": True}, _BLURBS, version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service._ownership = {"pnpm": ownership}  # pyright: ignore[reportPrivateUsage]
        app.catalog._version_statuses = {  # pyright: ignore[reportPrivateUsage]
            "pnpm": _outdated_status("pnpm", source="installer")
        }
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating pnpm" not in app.catalog.status_text)
        status = app.catalog.status_text
        assert "updated pnpm" in status
        assert "replayed typescript, eslint" in status
        assert "removed a stale cache entry" in status
        assert "postinstall shim needs manual review" in status


async def test_update_failure_renders_status_line(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )

    def failing_runner(argv: list[str]) -> None:
        raise CommandError(argv, 1, detail="permission denied")

    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=failing_runner,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _unified_app([tool], {"rg": True}, _BLURBS, version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service._ownership = {"rg": ownership}  # pyright: ignore[reportPrivateUsage]
        app.catalog._version_statuses = {  # pyright: ignore[reportPrivateUsage]
            "rg": _outdated_status("rg")
        }
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating rg" not in app.catalog.status_text)
        status = app.catalog.status_text
        assert "updated rg" not in status
        assert "permission denied" in status


async def test_update_unknown_owner_refusal_from_fresh_reresolution(tmp_path: Path) -> None:
    """The gate in `action_update_tool` reads the CACHED ownership (mutation
    grade at highlight time); `UpdateService.run` always re-resolves fresh
    ownership before mutating. A tool whose cached ownership was mutation
    grade but whose fresh re-resolution comes back unknown (e.g. the manager
    inventory changed between the two reads) must still be refused -- by
    `on_tool_updated`'s outcome-formatting path, not the pre-flight gate."""
    tool = _tool("rg")
    cached_ownership = _ownership(tool, owner="brew")
    fresh_unknown = _ownership(
        tool, owner="unknown", unknown_reason="brew inventory changed mid-flight"
    )
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=lambda _argv: None,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: fresh_unknown,
    )
    app = _unified_app([tool], {"rg": True}, _BLURBS, version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service._ownership = {"rg": cached_ownership}  # pyright: ignore[reportPrivateUsage]
        app.catalog._version_statuses = {  # pyright: ignore[reportPrivateUsage]
            "rg": _outdated_status("rg")
        }
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating rg" not in app.catalog.status_text)
        status = app.catalog.status_text
        assert "updated rg" not in status
        assert "brew inventory changed mid-flight" in status


async def test_second_update_press_shows_already_in_flight(tmp_path: Path) -> None:
    import threading

    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = _offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    # A real mutation has non-zero duration; a no-op runner can let the whole
    # update finish before the second key press is even dispatched, which
    # would make the in-flight window flaky rather than exercised. Blocking
    # the first update's runner on an Event -- released only after the second
    # press has been observed -- makes the guard's window deterministic
    # without a real subprocess or a sleep-based race.
    release = threading.Event()

    def blocking_runner(_argv: list[str]) -> None:
        release.wait(timeout=5)

    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=blocking_runner,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _unified_app([tool], {"rg": True}, _BLURBS, version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service._ownership = {"rg": ownership}  # pyright: ignore[reportPrivateUsage]
        app.catalog._version_statuses = {  # pyright: ignore[reportPrivateUsage]
            "rg": _outdated_status("rg")
        }
        # `begin()` latches synchronously inside action_update_tool, before the
        # worker thread is even spawned, so the second press deterministically
        # observes the in-flight guard regardless of the first update's timing.
        await pilot.press("u")
        assert "updating rg" in app.catalog.status_text
        await pilot.press("u")
        assert "already in flight for rg" in app.catalog.status_text
        # Let the blocked update finish so the worker's own thread and
        # post_message do not leak past the end of the test.
        release.set()
        await _wait_until(pilot, lambda: "updated rg" in app.catalog.status_text)
