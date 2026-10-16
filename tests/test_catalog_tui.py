import asyncio
import html
import inspect
import re
import threading
import typing
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from rich.cells import cell_len
from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DataTable, Static
from textual.widgets.data_table import ColumnKey

from installer.catalog_tui import (
    _COLUMNS,  # pyright: ignore[reportPrivateUsage]
    _LEGEND,  # pyright: ignore[reportPrivateUsage]
    AUDIENCE_LABEL,
    CatalogScreen,
    OwnershipRefreshed,
    SkillStatusRefreshed,
    ToolUpdated,
    VersionStatusRefreshed,
    group_tools,
    health_cell,
    sort_for_table,
)
from installer.deps import resolve_dependencies
from installer.doctor import DoctorReport
from installer.enums import Audience, Severity
from installer.manager_versions import ManagerVersion, OutdatedReport
from installer.model import (
    ConfigStep,
    Method,
    SkillLifecycle,
    SkillOperation,
    SkillStatusProbe,
    SkillTarget,
    Tool,
    load_categories,
    load_tools,
)
from installer.ownership import (
    ManagerInventory,
    ManagerOwnership,
    Owner,
    OwnershipCandidate,
    owner_detail,
    owner_label,
)
from installer.platform import Platform
from installer.resolve import UnavailableReason, platform_could_support, unavailable_reason
from installer.run import CommandError
from installer.selection import select_tools
from installer.tool_browser import ToolBrowser
from installer.ui_common import highlighted_key
from installer.uninstall import SweepResult
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_cache import VersionCacheEntry, save_version_cache
from installer.version_status import (
    Health,
    SkillHostStatus,
    ToolState,
    VersionRefreshService,
    VersionStatus,
)
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs
from tests.state_doubles import frozen_service, offline_service, pass_state, seeded_service
from tests.test_registry import REGISTRY

# The developer's home, read at import time before any test patches HOME.
_REAL_HOME = Path.home()
# Per-test scratch dir for the services the helpers below build on their own.
_SCRATCH: dict[str, Path] = {}


@pytest.fixture(autouse=True)
def scratch_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give `_screen`/`_unified_app` a scratch cache and home under `tmp_path`."""
    monkeypatch.setitem(_SCRATCH, "dir", tmp_path / "catalog-state")


def _seeded(tools: list[Tool], installed: Mapping[str, bool]) -> VersionRefreshService:
    """A service whose one completed pass reads `installed` as presence."""
    scratch = _SCRATCH["dir"]
    return seeded_service(
        tools,
        cache_path=scratch / "versions.json",
        home=scratch / "home",
        present={tool_id for tool_id, present in installed.items() if present},
    )


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
        blurbs,
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=list,
            ban_names=list,
            has_path_block=lambda: False,
            remove=lambda _decision: SweepResult(),
        ),
        policies=PolicyInputs(policies=[]),
        unavailable=unavailable,
        version_refresh=version_refresh or _seeded(tools, installed),
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
    method_os: tuple[str, ...] = (),
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}, os=method_os),),
        priority=priority,
        audience=audience,
        desc=desc,
        tier=tier,
        requires=requires,
        recommends=recommends,
    )


_BLURBS = {"search": "Find files and code at speed"}


def _health_from(installed: Mapping[str, bool]) -> Callable[[Tool], Health | None]:
    return lambda tool: Health.OK if installed[tool.id] else Health.MISSING


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
    groups = group_tools(tools, _health_from(installed), "priority", _BLURBS)
    assert [title for title, _, _ in groups] == ["P0", "P1", "P2"]  # no P3 tools -> dropped
    assert [detail for _, detail, _ in groups] == [
        "P0 · essential",
        "P1 · recommended",
        "P2 · nice-to-have",
    ]
    assert [t.id for _, _, members in groups for t in members] == ["rg", "fd", "lazygit"]


def test_group_by_audience_uses_labels():
    tools, installed = _catalog()
    groups = group_tools(tools, _health_from(installed), "audience", _BLURBS)
    assert [title for title, _, _ in groups] == ["for AI", "for both", "for human"]
    assert all(detail == title for title, detail, _ in groups)
    assert [t.id for _, _, members in groups for t in members] == ["rg", "fd", "lazygit"]


def test_audience_labels_keep_domain_names():
    assert AUDIENCE_LABEL[Audience.HUMAN] == "human"
    assert "you" not in AUDIENCE_LABEL.values()


def test_group_by_status_orders_health_groups_and_drops_empty():
    tools, installed = _catalog()
    groups = group_tools(tools, _health_from(installed), "status", _BLURBS)
    assert groups[0][:2] == ("✓ ok", "ok")
    assert [t.id for t in groups[0][2]] == ["rg"]
    assert groups[1][:2] == ("○ missing", "not installed")
    assert [t.id for t in groups[1][2]] == ["fd", "lazygit"]
    assert len(groups) == 2


def test_group_by_category_keeps_titles_short_and_blurbs_in_detail():
    tools, installed = _catalog()
    groups = group_tools(tools, _health_from(installed), "category", _BLURBS)
    # "git" has no blurb -> detail is the plain name; "search" has one -> appended.
    assert [(title, detail) for title, detail, _ in groups] == [
        ("git", "git"),
        ("search", "search — Find files and code at speed"),
    ]
    # within a group: priority then id
    assert [t.id for t in groups[1][2]] == ["rg", "fd"]


def test_sort_for_table_by_each_key():
    tools, installed = _catalog()
    assert [t.id for t in sort_for_table(tools, _health_from(installed), "id")] == [
        "fd",
        "lazygit",
        "rg",
    ]
    assert [t.id for t in sort_for_table(tools, _health_from(installed), "priority")] == [
        "rg",
        "fd",
        "lazygit",
    ]
    assert [t.id for t in sort_for_table(tools, _health_from(installed), "category")] == [
        "lazygit",
        "rg",
        "fd",
    ]
    assert [t.id for t in sort_for_table(tools, _health_from(installed), "audience")] == [
        "rg",
        "fd",
        "lazygit",
    ]  # ai < both < human alphabetically
    assert [t.id for t in sort_for_table(tools, _health_from(installed), "health")] == [
        "rg",
        "fd",
        "lazygit",
    ]  # Health precedence: ok before missing


def test_group_tools_rejects_unknown_view():
    tools, installed = _catalog()
    with pytest.raises(ValueError, match="unknown view"):
        group_tools(tools, _health_from(installed), "table", _BLURBS)


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
    # 15.4-01/D-01: widened from 120 -- the new Owner column (_COLUMNS) takes
    # real estate from the same row, which used to leave exactly zero margin
    # for the wide description at 120 columns.
    async with app.run_test(size=(130, 30)):
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


async def test_marking_claude_in_the_user_view_offers_its_recommends_and_r_stages_them() -> None:
    # claude is tier="user" (the human launches and drives it directly) but
    # recommends tier="ai" tooling (codegraph/graphify/rtk) -- proving a
    # cross-tier recommend still surfaces and stages correctly.
    tools = load_tools(REGISTRY)
    blurbs = load_categories(REGISTRY)
    installed = {tool.id: False for tool in tools}
    app = _unified_app(tools, installed, blurbs)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("2")
        await pilot.pause()
        screen = app.catalog_for("user")
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
    tools = [_tool("rg"), _tool("container", method_os=("linux",))]
    installed = {"rg": False, "container": False}
    app = _unified_app(tools, installed, _BLURBS, unavailable={"container": True})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        assert "container" not in app.catalog.selected
        assert app.catalog.selected == {"rg"}


def test_unavailable_reason_renders_in_row_and_detail() -> None:
    tool = next(item for item in load_tools(REGISTRY) if item.id == "alacritty")
    reason = unavailable_reason(
        tool, Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    )
    assert isinstance(reason, UnavailableReason)
    screen = CatalogScreen(
        [tool],
        _BLURBS,
        view="user",
        catalog=[tool],
        staged=set(),
        unavailable={tool.id: reason},
    )
    desc = screen._row_cells(tool)[8].plain  # pyright: ignore[reportPrivateUsage]
    assert "(not available: immutable host)" in desc
    assert reason.detail in screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert screen._adapter().selectable(tool) is False  # pyright: ignore[reportPrivateUsage]


def test_bare_true_unavailable_keeps_generic_copy() -> None:
    tool = _tool("x")
    screen = CatalogScreen(
        [tool],
        _BLURBS,
        view="system",
        catalog=[tool],
        staged=set(),
        unavailable={"x": True},
    )
    cells = screen._row_cells(tool)  # pyright: ignore[reportPrivateUsage]
    detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "(not available on this machine)" in cells[8].plain
    # The detail says it in the health block, as a reason (19-UI-SPEC).
    assert detail.endswith("checking… — not available on this machine")


async def test_unavailable_catalog_row_is_dimmed_with_blank_sel_cell() -> None:
    tools = [_tool("container", desc="Apple's native container runtime", method_os=("linux",))]
    app = _unified_app(tools, {"container": False}, _BLURBS, unavailable={"container": True})
    async with app.run_test(size=(100, 30)):
        table = app.catalog.query_one(DataTable[Any])
        sel = table.get_cell("container", "sel")
        desc = table.get_cell("container", "desc")
        assert sel.plain == ""
        assert "dim" in str(sel.style)
        assert "dim" in str(desc.style)
        assert "(not available on this machine)" in desc.plain
        assert "[dim]–[/] not available on this machine" in app.catalog.detail_text


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
        _tool("jq", category="data", priority="P1", method_os=("linux",)),
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
        _BLURBS,
        view="system",
        catalog=list(tools),
        staged=set(),
        version_refresh=version_refresh or _seeded(tools, installed),
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


def test_catalog_columns_include_ver_and_owner() -> None:
    assert len(_COLUMNS) == 9
    assert _COLUMNS[5] == ("Health", "health")
    assert _COLUMNS[6] == ("Ver", "ver")
    assert _COLUMNS[7] == ("Owner", "owner")
    assert _COLUMNS[8] == ("What it does", "desc")


def test_row_cells_both_branches_return_nine_cells() -> None:
    tool = _tool("rg")
    screen = _screen([tool], {"rg": True})
    assert len(screen._row_cells(tool)) == 9  # pyright: ignore[reportPrivateUsage]
    screen._unavailable["rg"] = True  # pyright: ignore[reportPrivateUsage]
    assert len(screen._row_cells(tool)) == 9  # pyright: ignore[reportPrivateUsage]


def test_zsh_is_audience_human_in_the_real_catalog() -> None:
    # Phase 15.3, D-01: zsh is the tracer subject for the registry-wide
    # audience re-tag. This asserts the full path -- registry value ->
    # group_tools placement -> the rendered `For` cell in both _row_cells
    # branches -> the detail bar -- not just the AUDIENCE_LABEL lookup those
    # functions share, which would stay true even if a renderer regressed.
    tools = load_tools(REGISTRY)
    installed = {tool.id: False for tool in tools}

    groups = group_tools(tools, _health_from(installed), "audience", _BLURBS)
    members_by_title = {title: {t.id for t in members} for title, _, members in groups}
    # group_tools drops empty groups before returning, so this title-list
    # equality IS the "all three groups are still populated" guard -- a group
    # that emptied would vanish from the list rather than arrive empty.
    assert [title for title, _, _ in groups] == ["for AI", "for both", "for human"]
    assert "zsh" in members_by_title["for human"]
    assert "zsh" not in members_by_title["for both"]
    # A D-02 keep, pinned on the other side of the split: the re-tag moved the
    # interactive rows without dragging the scriptable one-shots with them.
    assert "bat" in members_by_title["for both"]
    assert "bat" not in members_by_title["for human"]

    zsh = next(t for t in tools if t.id == "zsh")
    screen = _screen(tools, installed)
    assert _COLUMNS[4] == ("For", "for")
    assert screen._row_cells(zsh)[4].plain == "human"  # pyright: ignore[reportPrivateUsage]
    screen._unavailable["zsh"] = True  # pyright: ignore[reportPrivateUsage]
    assert screen._row_cells(zsh)[4].plain == "human"  # pyright: ignore[reportPrivateUsage]
    screen._unavailable["zsh"] = False  # pyright: ignore[reportPrivateUsage]
    assert "for human" in screen._detail_text(zsh)  # pyright: ignore[reportPrivateUsage]


def _ver_screen(
    tmp_path: Path, tool: Tool, version: VersionStatus | None, *, refreshing: bool = False
) -> CatalogScreen:
    """A screen over a frozen machine where `tool` is present at `version`
    (no state at all when `version` is None)."""
    service = frozen_service(tmp_path)
    if version is not None:
        service.publish([pass_state(tool, platform=service.platform, version=version)])
    screen = _screen([tool], {}, version_refresh=service)
    screen.version_refreshing = refreshing
    return screen


def test_stale_marker_is_visible_on_rendered_ver_cell(tmp_path: Path) -> None:
    tool = _tool("rg")
    fresh = _ver_screen(tmp_path, tool, _status(stale=False))._ver_cell(tool).plain  # pyright: ignore[reportPrivateUsage]
    stale = _ver_screen(tmp_path, tool, _status(stale=True))._ver_cell(tool).plain  # pyright: ignore[reportPrivateUsage]
    assert stale != fresh
    assert stale.endswith(" ~")
    assert not fresh.endswith(" ~")


def test_ver_cell_shows_a_probed_version_without_a_source_marker(tmp_path: Path) -> None:
    """A dnf/apt/pacman-owned tool has a real probed version but no 'latest'
    source: the cell keeps the version, and the missing comparison is a
    reason in the detail, never a marker in the cell (D-15)."""
    tool = _tool("rg")
    status = VersionStatus(
        tool_id="rg", installed="14.1.0", latest=None, outdated=None, stale=False, source="unknown"
    )
    screen = _ver_screen(tmp_path, tool, status)
    assert screen._ver_cell(tool).plain == "14.1.0"  # pyright: ignore[reportPrivateUsage]
    state = screen._state(tool)  # pyright: ignore[reportPrivateUsage]
    assert state is not None
    assert "no latest version to compare against" in state.reasons


def test_ver_cell_is_empty_when_no_version_was_read(tmp_path: Path) -> None:
    tool = _tool("rg")
    status = VersionStatus(
        tool_id="rg", installed=None, latest=None, outdated=None, stale=True, source="unknown"
    )
    screen = _ver_screen(tmp_path, tool, status)
    assert screen._ver_cell(tool).plain == ""  # pyright: ignore[reportPrivateUsage]
    state = screen._state(tool)  # pyright: ignore[reportPrivateUsage]
    assert state is not None
    assert "version unreadable" in state.reasons


def test_epoch_guard_drops_a_superseded_version_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _tool("rg")
    service = frozen_service(tmp_path)
    screen = _screen([tool], {}, version_refresh=service)
    screen._version_refresh_generation = 1  # pyright: ignore[reportPrivateUsage]
    service.invalidate(reason="test")
    reloads: list[object] = []
    monkeypatch.setattr(screen._browser, "reload", reloads.append)  # pyright: ignore[reportPrivateUsage]
    screen.on_version_status_refreshed(VersionStatusRefreshed(generation=1, epoch=0))
    assert reloads == []
    assert screen.version_refreshing is False


def _posted_messages(screen: CatalogScreen, monkeypatch: pytest.MonkeyPatch) -> list[Message]:
    """Capture every message a screen posts without needing a running app
    (`post_message` requires a live message pump, which a bare
    `CatalogScreen()` construction never has)."""
    posted: list[Message] = []

    def fake_post_message(message: Message) -> bool:
        posted.append(message)
        return True

    monkeypatch.setattr(screen, "post_message", fake_post_message)
    return posted


def test_ownership_refreshed_is_posted_on_the_commit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """15.4-04, Round-2 review HIGH: the commit path -- both the generation
    and the epoch gates already passed -- is the ONE point where the shared
    ownership map is known to hold a current pass, so it is the one point
    that posts the completion signal a mounted Uninstall screen listens
    for."""
    tool = _tool("rg")
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda repo: "v1.6.0",
        probe_output=lambda argv: "1.2.0",
    )
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    screen._version_refresh_generation = 1  # pyright: ignore[reportPrivateUsage]
    posted = _posted_messages(screen, monkeypatch)
    screen.on_version_status_refreshed(VersionStatusRefreshed(generation=1, epoch=service.epoch))
    assert any(isinstance(message, OwnershipRefreshed) for message in posted)


def test_ownership_refreshed_is_not_posted_on_a_superseded_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _tool("rg")
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda repo: "v1.6.0",
        probe_output=lambda argv: "1.2.0",
    )
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    screen._version_refresh_generation = 2  # pyright: ignore[reportPrivateUsage]
    posted = _posted_messages(screen, monkeypatch)
    screen.on_version_status_refreshed(VersionStatusRefreshed(generation=1, epoch=service.epoch))
    assert not any(isinstance(message, OwnershipRefreshed) for message in posted)


def test_ownership_refreshed_is_not_posted_on_a_raced_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _tool("rg")
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda repo: "v1.6.0",
        probe_output=lambda argv: "1.2.0",
    )
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    screen._version_refresh_generation = 1  # pyright: ignore[reportPrivateUsage]
    service.invalidate(reason="test")
    posted = _posted_messages(screen, monkeypatch)
    screen.on_version_status_refreshed(VersionStatusRefreshed(generation=1, epoch=0))
    assert not any(isinstance(message, OwnershipRefreshed) for message in posted)


# -- 15.4-01/D-01: tracer -- probe -> resolver -> label table -> rendered
# cell, end to end through a real VersionRefreshService.refresh pass. -------


def _git_shaped_tool() -> Tool:
    return Tool(
        id="git",
        name="Git",
        category="git",
        cmd="git",
        methods=(
            Method(kind="dnf", params={"package": "git"}),
            Method(kind="apt", params={"package": "git"}),
            Method(kind="pacman", params={"package": "git"}),
            Method(kind="brew", params={"formula": "git"}),
        ),
        owner_probes=("rpm-ostree", "dnf", "apt", "pacman"),
    )


def test_owner_column_and_detail_paint_the_os_package_case_end_to_end(tmp_path: Path) -> None:
    tool = _git_shaped_tool()

    def native_probe(command: list[str]) -> str:
        # The pass asks rpm once, batched: one "<path>\t<name>" line per path (D-11).
        if "[%{FILENAMES}\\t%{=NAME}\\n]" in command:
            return "".join(f"{path}\tgit-core\n" for path in command[4:])
        return "git-core\n"

    def which(cmd: str) -> str | None:
        return "/usr/bin/git" if cmd == "git" else None

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=lambda argv: None,
        platform=Platform(os="fedora", arch="amd64", immutable=True, has_brew=False),
        which=which,
        native_probe=native_probe,
        artifacts_for=lambda tool: [],
    )
    service.refresh([tool])
    state = service.state_of("git")
    assert state is not None
    assert state.ownership.owner == "os-package"

    screen = _screen([tool], {"git": True}, version_refresh=service)
    for unavailable in (False, True):
        screen._unavailable["git"] = unavailable  # pyright: ignore[reportPrivateUsage]
        cells = screen._row_cells(tool)  # pyright: ignore[reportPrivateUsage]
        assert cells[7].plain == "OS package"

    # The intermediate-state guard (Round-2 review MEDIUM): the detail bar
    # also names the new owner, so no surface is left blank before 15.4-03
    # lands. Asserted behaviourally so it survives that plan's refactor.
    screen._unavailable["git"] = False  # pyright: ignore[reportPrivateUsage]
    detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert detail
    assert "OS package" in detail


# -- 15.4-03/D-02: the Owner COLUMN renders every non-unknown owner value in
# BOTH `_row_cells` branches, and blank means exactly "genuinely don't know"
# -- never "didn't bother labeling this case". -------------------------------


@pytest.mark.parametrize("owner", [o for o in typing.get_args(Owner) if o != "unknown"])
def test_owner_column_renders_every_owner_value_in_both_branches(
    owner: Owner, tmp_path: Path
) -> None:
    # The second tool cannot install on this macOS host, so its absent state
    # is UNAVAILABLE and its row takes the dim branch.
    for tool, present in ((_tool("demo"), True), (_tool("demo", method_os=("linux",)), False)):
        ownership = _ownership(
            tool, owner=owner, package="demo-pkg" if owner == "os-package" else None
        )
        service = frozen_service(tmp_path)
        service.publish(
            [pass_state(tool, platform=service.platform, present=present, ownership=ownership)]
        )
        screen = _screen([tool], {}, version_refresh=service)
        expected = owner_label(ownership)
        assert expected
        cells = screen._row_cells(tool)  # pyright: ignore[reportPrivateUsage]
        assert cells[0].plain == ("[ ]" if present else "")
        assert cells[7].plain == expected


def test_owner_column_is_blank_for_an_unknown_record(tmp_path: Path) -> None:
    for tool, present in ((_tool("demo"), True), (_tool("demo", method_os=("linux",)), False)):
        ownership = _ownership(tool, owner="unknown", unknown_reason="no manager claimed the tool")
        service = frozen_service(tmp_path)
        service.publish(
            [pass_state(tool, platform=service.platform, present=present, ownership=ownership)]
        )
        screen = _screen([tool], {}, version_refresh=service)
        cells = screen._row_cells(tool)  # pyright: ignore[reportPrivateUsage]
        assert cells[0].plain == ("[ ]" if present else "")
        assert cells[7].plain == ""


def test_owner_column_is_blank_with_no_ownership_record_produced_yet(tmp_path: Path) -> None:
    """No pass has produced a state for this tool yet (e.g. the refresh
    worker has not landed) -- the SAME blank as an unknown record, because
    both genuinely mean "don't know"."""
    tool = _tool("demo")
    screen = _screen([tool], {}, version_refresh=frozen_service(tmp_path))
    for unavailable in (False, True):
        screen._unavailable["demo"] = unavailable  # pyright: ignore[reportPrivateUsage]
        assert screen._row_cells(tool)[7].plain == ""  # pyright: ignore[reportPrivateUsage]


def test_owner_column_is_blank_while_a_pass_is_in_flight(tmp_path: Path) -> None:
    """19-UI-SPEC A9: while no state exists the Health `…` is the one place
    that says "checking", so Owner stays blank instead of repeating it."""
    tool = _tool("demo")
    screen = _screen([tool], {}, version_refresh=frozen_service(tmp_path))
    screen.version_refreshing = True
    for unavailable in (False, True):
        screen._unavailable["demo"] = unavailable  # pyright: ignore[reportPrivateUsage]
        assert screen._row_cells(tool)[7].plain == ""  # pyright: ignore[reportPrivateUsage]


def test_owner_column_is_blank_with_no_version_refresh_service_wired() -> None:
    tool = _tool("demo")
    screen = _screen([tool], {"demo": True}, version_refresh=None)
    for unavailable in (False, True):
        screen._unavailable["demo"] = unavailable  # pyright: ignore[reportPrivateUsage]
        assert screen._row_cells(tool)[7].plain == ""  # pyright: ignore[reportPrivateUsage]


def test_owner_column_dims_in_the_unavailable_branch_like_every_other_cell(
    tmp_path: Path,
) -> None:
    tool = _tool("demo", method_os=("linux",))
    ownership = _ownership(tool, owner="brew")
    service = frozen_service(tmp_path)
    service.publish(
        [pass_state(tool, platform=service.platform, present=False, ownership=ownership)]
    )
    screen = _screen([tool], {}, version_refresh=service)
    cells = screen._row_cells(tool)  # pyright: ignore[reportPrivateUsage]
    assert cells[7].plain == "Homebrew"
    assert "dim" in str(cells[7].style)


def test_owner_column_does_not_gate_on_installed_state_unlike_ver_cell(
    tmp_path: Path,
) -> None:
    """The column does not suppress on presence (contrast with `_ver_cell`):
    ownership is resolved from the live binary path, and a tool the presence
    predicate happens to read as absent can still carry a real record."""
    tool = _tool("demo")
    ownership = _ownership(tool, owner="brew")
    service = frozen_service(tmp_path)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                present=False,
                ownership=ownership,
                version=_ver("1.0", "1.1", True),
            )
        ]
    )
    screen = _screen([tool], {}, version_refresh=service)
    cells = screen._row_cells(tool)  # pyright: ignore[reportPrivateUsage]
    assert cells[7].plain == owner_label(ownership)
    # The Ver cell, by contrast, DOES suppress for a not-installed tool.
    assert cells[6].plain == ""


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


async def test_ver_cell_is_empty_for_unparseable_probe_output(
    tmp_path: Path,
) -> None:
    tool = _gh_tool("dasel")
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda repo: "v2.8.0",
        probe_output=lambda argv: "Usage: dasel <command>",
    )
    app = _unified_app([tool], {"dasel": True}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _wait_until(pilot, lambda: not app.catalog.version_refreshing)
        await pilot.pause()
        state = service.state_of("dasel")
        assert state is not None
        assert "version unreadable" in state.reasons
        cell = app.catalog.query_one(DataTable[Any]).get_cell("dasel", "ver")
        assert cell.plain == ""


async def test_stale_and_fresh_rows_differ_only_by_trailing_marker(tmp_path: Path) -> None:
    def status(tool_id: str, installed: str | None, *, stale: bool) -> VersionStatus:
        return VersionStatus(
            tool_id=tool_id,
            installed=installed,
            latest=installed,
            outdated=False if installed else None,
            stale=stale,
            source="github",
        )

    rg, fd, dasel = _gh_tool("rg"), _gh_tool("fd"), _gh_tool("dasel")
    service = frozen_service(tmp_path)
    service.publish(
        [
            pass_state(rg, platform=service.platform, version=status("rg", "15.2.0", stale=True)),
            pass_state(fd, platform=service.platform, version=status("fd", "15.2.0", stale=False)),
            pass_state(dasel, platform=service.platform, version=status("dasel", None, stale=True)),
        ]
    )
    screen = _screen([rg, fd, dasel], {}, version_refresh=service)
    stale_cell = screen._ver_cell(rg).plain  # pyright: ignore[reportPrivateUsage]
    fresh_cell = screen._ver_cell(fd).plain  # pyright: ignore[reportPrivateUsage]
    unknown_cell = screen._ver_cell(dasel).plain  # pyright: ignore[reportPrivateUsage]
    assert stale_cell == fresh_cell + " ~"
    assert not fresh_cell.endswith(" ~")
    assert unknown_cell == ""


# -- D-02/Task 2: every dim Ver cell says which situation produced it --------


def test_ver_cell_github_source_without_latest_shows_the_bare_version(tmp_path: Path) -> None:
    """A github-sourced status whose latest fetch failed or was deferred keeps
    its installed version and gains no marker; the missing comparison is a
    reason in the detail bar (D-15)."""
    tool = _gh_tool("rg")
    status = VersionStatus(
        tool_id="rg", installed="14.1.0", latest=None, outdated=None, stale=False, source="github"
    )
    screen = _ver_screen(tmp_path, tool, status)
    assert screen._ver_cell(tool).plain == "14.1.0"  # pyright: ignore[reportPrivateUsage]


def test_ver_cell_unparseable_latest_shows_the_bare_version(tmp_path: Path) -> None:
    """The `outdated is None` branch with a latest present (both versions
    exist but one would not parse) keeps the installed version, unmarked."""
    tool = _tool("rg")
    status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="not-a-version",
        outdated=None,
        stale=False,
        source="github",
    )
    screen = _ver_screen(tmp_path, tool, status)
    assert screen._ver_cell(tool).plain == "14.1.0"  # pyright: ignore[reportPrivateUsage]


def test_ver_cell_is_empty_without_a_state_whether_or_not_refreshing(tmp_path: Path) -> None:
    tool = _tool("rg")
    for refreshing in (True, False):
        screen = _ver_screen(tmp_path, tool, None, refreshing=refreshing)
        assert screen._ver_cell(tool).plain == ""  # pyright: ignore[reportPrivateUsage]


def test_ver_cell_never_renders_a_dim_label(tmp_path: Path) -> None:
    """The six situations that used to produce four dim labels (D-02) now
    produce only two cells: empty when there is no version to show, the bare
    version otherwise. Their facts moved to the state's reasons (D-15)."""
    tool = _tool("rg")
    installed = "14.1.0"

    def cell_for(status: VersionStatus | None, *, refreshing: bool = False) -> Text:
        screen = _ver_screen(tmp_path, tool, status, refreshing=refreshing)
        return screen._ver_cell(tool)  # pyright: ignore[reportPrivateUsage]

    def status(version: str | None, latest: str | None, source: str) -> VersionStatus:
        return VersionStatus(
            tool_id="rg",
            installed=version,
            latest=latest,
            outdated=None,
            stale=False,
            source=source,
        )

    empty = [
        cell_for(None, refreshing=True),
        cell_for(None),
        cell_for(status(None, None, "unknown")),
    ]
    bare = [
        cell_for(status(installed, None, "unknown")),
        cell_for(status(installed, None, "github")),
        cell_for(status(installed, "not-a-version", "github")),
    ]
    assert [cell.plain for cell in empty] == ["", "", ""]
    assert [cell.plain for cell in bare] == [installed] * 3
    assert all(not cell.spans and str(cell.style) == "" for cell in empty + bare)


def test_ver_cell_stale_suffix_only_qualifies_a_comparison(tmp_path: Path) -> None:
    """D-04 as interpreted 2026-09-16 (15.1-CONTEXT.md), kept by 19-UI-SPEC
    A13: the stale suffix qualifies a claim about `latest`, so it is appended
    only to a cell that compared against one -- asserted over every situation
    at once, all built with stale=True, so a no-comparison branch falling
    through into the suffix assembly is caught."""
    tool = _tool("rg")
    installed = "14.1.0"

    def cell_for(status: VersionStatus | None, *, refreshing: bool = False) -> str:
        screen = _ver_screen(tmp_path, tool, status, refreshing=refreshing)
        return screen._ver_cell(tool).plain  # pyright: ignore[reportPrivateUsage]

    def status(
        version: str | None, latest: str | None, outdated: bool | None, source: str
    ) -> VersionStatus:
        return VersionStatus(
            tool_id="rg",
            installed=version,
            latest=latest,
            outdated=outdated,
            stale=True,
            source=source,
        )

    no_claim = [
        cell_for(None, refreshing=True),
        cell_for(None),
        cell_for(status(None, None, None, "unknown")),
        cell_for(status(installed, None, None, "unknown")),
        cell_for(status(installed, None, None, "github")),
        cell_for(status(installed, "not-a-version", None, "github")),
    ]
    compared = [
        cell_for(status(installed, "15.0.0", True, "github")),
        cell_for(status(installed, installed, False, "github")),
    ]
    for cell in no_claim:
        assert "~" not in cell, cell
    for cell in compared:
        assert cell.endswith(" ~"), cell


async def test_checking_mark_reaches_the_rendered_table_while_a_pass_is_blocked(
    tmp_path: Path,
) -> None:
    """The checking mark must be observed in a PAINTED `DataTable` cell
    while a refresh worker is provably blocked, after a first pass that
    crashed and published nothing."""
    tool = _gh_tool("dasel")
    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def resolve_tag(repo: str) -> str:
        del repo
        calls["n"] += 1
        if calls["n"] == 1:
            # First pass crashes: nothing is published, so the row stays `…`.
            raise RuntimeError("simulated domain failure")
        started.set()
        assert release.wait(timeout=5)
        return "v2.8.0"

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=resolve_tag,
        probe_output=lambda argv: "1.0.0",
    )
    app = _unified_app([tool], {"dasel": True}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        for _ in range(400):
            if not app.catalog.version_refreshing:
                break
            await pilot.pause()
        await pilot.pause()
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("dasel", "health").plain == "…"
        assert table.get_cell("dasel", "ver").plain == ""
        app.catalog.enter_view()
        # A blocking Event.wait() here would starve the asyncio loop of the
        # tick it needs to actually dispatch the thread-worker submission --
        # pilot.pause() yields control instead, so the background thread gets
        # scheduled and can reach started.set().
        for _ in range(500):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        assert table.get_cell("dasel", "health").plain == "…"
        release.set()
        for _ in range(400):
            if not app.catalog.version_refreshing:
                break
            await pilot.pause()
        await pilot.pause()
        assert table.get_cell("dasel", "health").plain != "…"
        assert "v2.8.0" in table.get_cell("dasel", "ver").plain


async def test_refresh_cursor_survives_both_repaints_of_one_cycle(tmp_path: Path) -> None:
    """Both repaints a refresh cycle now performs -- the start-of-refresh
    reload and the completion reload -- must leave the user's cursor where
    they left it, read back at both points (not only at the end, which
    cannot tell a fix that survives only the completion rebuild apart from
    one that also survives the start-of-refresh rebuild)."""
    tools = [_gh_tool("alpha"), _gh_tool("beta")]
    started = threading.Event()
    release = threading.Event()
    blocking = {"on": False}

    def probe_output(argv: list[str]) -> str | None:
        # probe_output runs unconditionally every pass, unlike resolve_tag
        # (gated by the per-tool GitHub cache's own freshness window) -- the
        # second enter_view() below would otherwise never call resolve_tag at
        # all once the first pass has already cached a fresh entry.
        del argv
        if blocking["on"]:
            started.set()
            assert release.wait(timeout=5)
        return "1.0.0"

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=probe_output,
    )
    app = _unified_app(tools, {"alpha": True, "beta": True}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        for _ in range(400):
            if not app.catalog.version_refreshing:
                break
            await pilot.pause()
        await pilot.pause()
        table = app.catalog.query_one(DataTable[Any])
        table.move_cursor(row=table.get_row_index("beta"))
        await pilot.pause()
        started_row = table.cursor_row
        blocking["on"] = True
        app.catalog.enter_view()
        # See the sibling checking-marker test above: pilot.pause() (not a
        # blocking Event.wait()) is what lets the thread-worker submission
        # actually happen while we poll.
        for _ in range(500):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        assert table.cursor_row == started_row
        release.set()
        for _ in range(400):
            if not app.catalog.version_refreshing:
                break
            await pilot.pause()
        await pilot.pause()
        assert table.cursor_row == started_row


# -- D-03/D-04/Task 3: an always-on legend names every version state --------


_BROKEN_HINT = "shim present, package missing — select it and press enter to reinstall and repair"


def test_broken_row_marks_health_red_and_explains_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm_home = tmp_path / "pnpm"
    monkeypatch.setenv("PNPM_HOME", str(pnpm_home))
    tool = Tool(
        id="mmdc",
        name="mmdc",
        category="docs",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
    )
    service = seeded_service(
        [tool],
        cache_path=tmp_path / "versions.json",
        home=tmp_path / "home",
        present={"mmdc"},
        which=lambda cmd: str(pnpm_home / cmd),
    )
    screen = _screen([tool], {"mmdc": True}, version_refresh=service)
    cell = screen._row_cells(tool)[5]  # pyright: ignore[reportPrivateUsage]
    assert cell.plain == "!"
    assert "red" in str(cell.style)
    detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert _BROKEN_HINT in detail


def test_update_on_broken_row_hints_repair_without_updating(tmp_path: Path) -> None:
    tool = _tool("mmdc")
    ownership = _ownership(tool, owner="pnpm", broken=True)
    service = frozen_service(tmp_path)
    updates = _update_service(lambda _tool: ownership)
    begins = _counting_begin(updates)
    screen = _screen([tool], {"mmdc": True}, version_refresh=service, updates=updates)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=ownership,
                version=_outdated_status("mmdc"),
            )
        ]
    )
    screen._browser.highlighted_id = lambda: "mmdc"  # type: ignore[method-assign]
    started: list[str] = []
    screen._update_tool_worker = lambda target: started.append(target.tool.id)  # type: ignore[method-assign]
    messages: list[str] = []
    screen.status.set = lambda text, severity: messages.append(text)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert begins == []
    assert started == []
    assert messages == [f"mmdc is broken: {_BROKEN_HINT}"]


def test_legend_names_the_broken_mark() -> None:
    lines = _LEGEND.split("\n")
    assert "! broken" in lines[0]
    for line in lines:
        plain = re.sub(r"\[[^\]]*\]", "", line)
        assert len(plain) <= 78, (len(plain), plain)


def test_installed_row_without_broken_still_shows_green_check(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = seeded_service(
        [tool], cache_path=tmp_path / "versions.json", home=tmp_path / "home", present={"rg"}
    )
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    cell = screen._row_cells(tool)[5]  # pyright: ignore[reportPrivateUsage]
    assert cell.plain == "✓"
    assert "green" in str(cell.style)


def _painted_legend(legend: Static) -> str:
    """Everything the legend widget actually paints, as one line.

    Iterates the widget's own rendered height rather than assuming one line --
    that is the whole point of the content-sized CSS; a clipped legend fails
    these assertions even though every entry is present in the constant.

    The wrapped lines are joined with a space and re-split, never edge to
    edge: Rich breaks at spaces, so a two-word marker split across a wrap
    boundary is still painted in full and must not be reported as missing.
    """
    lines = " ".join(
        "".join(segment.text for segment in legend.render_line(i))
        for i in range(legend.size.height)
    )
    return " ".join(lines.split())


def _dim_legend_text(legend: Static) -> str:
    """Only the parts of the legend actually painted with the `dim` style."""
    dim = " ".join(
        segment.text
        for i in range(legend.size.height)
        for segment in legend.render_line(i)
        if segment.style is not None and segment.style.dim
    )
    return " ".join(dim.split())


async def test_legend_widget_paints_every_marker_at_full_width() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)):
        legend = app.query_one("#browser-legend", Static)
        painted = _painted_legend(legend)
        markers = (
            "✓ ok",
            "↑ update",
            "≈ config",
            "! broken",
            "○ missing",
            "… checking",
            "– unavailable",
            "essential",
            "cached latest",
            "≠ policy",
        )
        for marker in markers:
            assert marker in painted, marker
        # The line-3 tail, which clipped in the 2026-09-16 regression.
        assert "other manager owns it" in painted
        # Each entry is painted in the style of the cell it decodes: the
        # checking and unavailable marks, the stale `~` and `≠ policy` are dim.
        dim = _dim_legend_text(legend)
        for entry in ("… checking", "– unavailable", "~", "≠ policy"):
            assert entry in dim, entry


async def test_legend_keeps_the_catalog_table_usable_at_the_minimum_size() -> None:
    """The legend is readable AND the table is usable at 80x20 -- this
    project's own tested minimum terminal size.

    Both halves are asserted together on purpose, because either one alone is
    trivially satisfiable in a way that breaks the other: capping the height
    clips markers off the bottom, and shortening the text leaves the next
    edit free to collapse the table again.
    """
    app = _app()
    async with app.run_test(size=(80, 20)):
        legend = app.query_one("#browser-legend", Static)
        table = app.query_one(DataTable[Any])
        painted = _painted_legend(legend)
        markers = (
            "✓ ok",
            "↑ update",
            "≈ config",
            "! broken",
            "○ missing",
            "… checking",
            "– unavailable",
            "essential",
            "cached latest",
            "≠ policy",
        )
        for marker in markers:
            assert marker in painted, marker
        # The line-3 tail, which clipped in the 2026-09-16 regression.
        assert "other manager owns it" in painted
        # The harm first, then the cause: the table has to stay usable, and
        # the legend's own budget is what keeps it that way.
        assert table.size.height >= 6, table.size.height
        assert legend.size.height <= 3, legend.size.height


# -- 15.4-03/Task 3: Owner-cell coverage split in two, on purpose (Round-2
# review LOW). A single "the Owner value is visually reachable at 80x20"
# assertion would depend on Textual's runtime column auto-sizing and
# horizontal-scroll position -- not this project's behaviour to pin. -------


async def test_owner_cell_semantic_value_reaches_the_mounted_table(tmp_path: Path) -> None:
    """SEMANTIC, deterministic: the Owner value through the table's own cell
    data -- the adapter's `row_cells` output at index 7, AND the mounted
    table's stored cell for that row/column -- with no size harness involved
    at all. Answers "did this screen tell the table the owner" and nothing
    else."""
    tool = _tool("rg")

    def brew_owns_rg(**_kwargs: object) -> ManagerInventory:
        return ManagerInventory(
            brew_formulae={"rg": "1.0"},
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=tmp_path / "brew",
        )

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
        artifacts_for=lambda _t: [],
        read_inventory_fn=brew_owns_rg,
        which=lambda cmd: str(tmp_path / "brew" / "bin" / cmd),
    )
    app = _unified_app([tool], {"rg": True}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(100, 30)) as pilot:
        # WR-07: suppression-free wait -- WorkerManager.__iter__ returns
        # Iterator[Worker[Any]], so gather type-checks clean under strict
        # pyright where wait_for_complete's bare-generic signature does not.
        await asyncio.gather(*(worker.wait() for worker in app.workers))
        await pilot.pause()
        resolved = service.state_of("rg")
        assert resolved is not None
        assert resolved.ownership.owner == "brew"
        row_cells = app.catalog._row_cells(tool)  # pyright: ignore[reportPrivateUsage]
        assert row_cells[7].plain == "Homebrew"
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("rg", "owner").plain == "Homebrew"


async def test_nine_column_table_mounts_and_renders_at_the_minimum_size() -> None:
    """LAYOUT, deterministic: only what's guaranteed at 80x20 -- the screen
    mounts and renders nine columns without error, and the table region
    still has room for at least one data row below the docked legend.

    Deliberately NOT asserted here: which characters of which column land on
    screen. Textual decides column auto-sizing and horizontal-scroll
    position at runtime, so a "the Owner text is visible" assertion would pin
    this suite to Textual's layout algorithm rather than to this project's
    own behaviour (Round-2 review LOW). Do not "strengthen" this into a
    rendered-text match -- see `test_owner_cell_semantic_value_reaches_the_
    mounted_table` above for the deterministic semantic coverage instead.
    """
    app = _app()
    async with app.run_test(size=(80, 20)):
        table = app.catalog.query_one(DataTable[Any])
        assert len(table.columns) == 9
        assert table.size.height >= 6, table.size.height


async def test_owner_column_starts_inside_the_viewport_at_the_minimum_size() -> None:
    """WR-03 (15.4-REVIEW.md). A DETERMINISTIC GEOMETRY assertion, which is
    a different thing from the rendered-text assertion
    `test_nine_column_table_mounts_and_renders_at_the_minimum_size` above
    deliberately refuses: `get_render_width` is the number Textual lays the
    columns out WITH, so this pins this project's own column budget rather
    than Textual's layout algorithm.

    Measured over the REAL registry at 80x20 with realistic content in the
    two columns that sit before Owner -- a `1.22.3 -> 1.22.44 ~` Ver cell and
    the widest Owner label -- the phase's headline column used to start at
    x=80 in an 80-wide viewport, i.e. entirely off screen, with no horizontal
    scroll to reach it (`left`/`right` are `priority=True` view-switch
    bindings on `ToolBrowser`). Moving section titles out of the
    selection-mark column (`BrowserAdapter.section_column`) bought the 10
    columns that put it back on screen.
    """
    tools = load_tools(REGISTRY)
    installed = {tool.id: True for tool in tools}
    app = _unified_app(tools, installed, {tool.category: "" for tool in tools})
    async with app.run_test(size=(80, 20)) as pilot:
        catalog = app.catalog
        # The widest Ver cell this phase renders (19-UI-SPEC "Columns").
        catalog._ver_cell = lambda _tool: Text("1.22.3 -> 1.22.44 ~")  # type: ignore[method-assign]
        # The widest label `OWNER_LABELS` can produce, so the assertion is
        # made against the worst case rather than an empty column.
        catalog._owner_cell = lambda _tool: Text("Homebrew cask")  # type: ignore[method-assign]
        catalog._browser.reload(catalog._adapter())  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        table = app.query_one(DataTable[Any])
        offsets: dict[str, int] = {}
        total = 0
        for column in table.columns.values():
            offsets[column.label.plain] = total
            total += column.get_render_width(table)
        assert offsets["Owner"] < table.size.width, offsets


def test_legend_is_identical_across_all_three_tier_views() -> None:
    tools, _ = _catalog()
    screens = [
        CatalogScreen(tools, _BLURBS, view=tier, catalog=list(tools), staged=set())
        for tier in ("system", "user", "ai")
    ]
    legends = {screen._adapter().legend for screen in screens}  # pyright: ignore[reportPrivateUsage]
    assert legends == {_LEGEND}


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
    service = offline_service(
        path,
        skill_home=tmp_path,
        resolve_tag=lambda repo: "1.0.0",
        probe_output=lambda argv: "1.0.0",
        now=lambda: now,
    )
    tools = [_gh_tool("fresh"), _gh_tool("stale")]
    app = _unified_app(tools, {"fresh": True, "stale": True}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _wait_until(pilot, lambda: not app.catalog.version_refreshing)
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
    off_policy: bool = False,
    broken: bool = False,
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
        off_policy=off_policy,
        broken=broken,
    )


# -- 15.4-03/D-02/D-02a: _version_detail hand-writes no owner prose of its
# own -- it must read ownership.owner_detail and agree with it byte-for-byte,
# for every Owner value, not just a representative one (Round-1 review
# HIGH/MEDIUM). ---------------------------------------------------------------


@pytest.mark.parametrize(
    "owner",
    [o for o in typing.get_args(Owner) if o not in ("unknown", "installer", "os-package")],
)
def test_version_detail_reads_the_prose_register_for_every_simple_owner_value(
    owner: Owner, tmp_path: Path
) -> None:
    tool = _tool("demo")
    ownership = _ownership(tool, owner=owner)
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    screen = _screen([tool], {"demo": True}, version_refresh=service)
    detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    expected = owner_detail(ownership)
    assert expected is not None
    assert expected in detail


@pytest.mark.parametrize(
    ("kind", "mechanism"),
    [
        ("github_release", "GitHub release"),
        ("tarball", "tarball download"),
        ("app", "downloaded app"),
        ("script", "own installer"),
    ],
)
def test_version_detail_names_every_installer_placement_mechanism(
    kind: str, mechanism: str, tmp_path: Path
) -> None:
    tool = _tool("demo")
    method = Method(kind=kind, params={})
    ownership = ManagerOwnership(
        tool_id="demo",
        owner="installer",
        method=method,
        package=None,
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate="installer",
        active_path=None,
        unknown_reason=None,
    )
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    screen = _screen([tool], {"demo": True}, version_refresh=service)
    detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert mechanism in detail
    # D-02a: never the bare catch-all word that implies a package manager
    # exists behind it.
    assert "installed by this installer" not in detail


def test_version_detail_os_package_names_the_actual_package(tmp_path: Path) -> None:
    tool = _tool("demo")
    ownership = _ownership(tool, owner="os-package", package="git-core")
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    screen = _screen([tool], {"demo": True}, version_refresh=service)
    detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "git-core" in detail
    assert "will not update it" in detail


def test_detail_hand_writes_no_owner_vocabulary_of_its_own() -> None:
    """NO-LOCAL-DICT gate (source inspection): the detail builders contain no
    owner-keyed prose of their own -- the owner sentences arrive as state
    reasons, built by `ownership_notes` from `owner_detail`."""
    import installer.catalog_tui as catalog_tui_module

    screen = catalog_tui_module.CatalogScreen
    body = "\n".join(
        line
        for target in (screen._detail_text, screen._health_block)  # pyright: ignore[reportPrivateUsage]
        for line in inspect.getsource(target).splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "state.reasons" in body
    stray = [owner for owner in typing.get_args(Owner) if f'"{owner}"' in body]
    assert not stray, stray


def test_detail_line_names_homebrew_for_brew_owned_row(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = frozen_service(tmp_path)
    screen = _screen([tool], {"rg": True}, version_refresh=service)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=_ownership(tool, owner="brew"),
                version=VersionStatus(
                    tool_id="rg",
                    installed="14.1.0",
                    latest="14.1.1",
                    outdated=True,
                    stale=False,
                    source="brew",
                ),
            )
        ]
    )
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "Homebrew" in text


def test_detail_line_names_competing_manager_and_active_path(tmp_path: Path) -> None:
    tool = _tool("rg")
    path = Path("/opt/homebrew/bin/rg")
    ownership = _ownership(
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
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    screen = _screen([tool], {}, version_refresh=service)
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert f"also installed via installer artifact — live copy at {path}" in text


def test_detail_names_also_installed_via_the_shadowed_manager(tmp_path: Path) -> None:
    tool = _sdkman_tool("java")
    path = Path("/home/user/.sdkman/candidates/java/current/bin/java")
    ownership = _ownership(
        tool,
        owner="brew",
        shadowed=True,
        active_path=path,
        candidates=(
            OwnershipCandidate(
                owner="brew",
                method=None,
                package="openjdk",
                current_version=None,
                evidence="cellar",
            ),
            OwnershipCandidate(
                owner="sdkman",
                method=tool.methods[0],
                package="java",
                current_version=None,
                evidence="candidate",
            ),
        ),
    )
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    screen = _screen([tool], {}, version_refresh=service)
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert f"also installed via SDKMAN — live copy at {path}" in text


def test_unknown_detail_names_the_active_binary(tmp_path: Path) -> None:
    tool = _tool("foo")
    path = Path("/opt/x/bin/foo")
    ownership = _ownership(
        tool, owner="unknown", unknown_reason="no manager claimed this tool", active_path=path
    )
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    screen = _screen([tool], {}, version_refresh=service)
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "active binary resolves to /opt/x/bin/foo" in text


def test_update_unknown_appends_the_active_path(tmp_path: Path) -> None:
    tool = _tool("foo")
    path = Path("/opt/x/bin/foo")
    ownership = _ownership(
        tool,
        owner="unknown",
        unknown_reason="no manager claimed this tool",
        active_path=path,
    )
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"foo": True}, version_refresh=service, updates=updates)
    screen._browser.highlighted_id = lambda: "foo"  # type: ignore[method-assign]
    messages: list[str] = []
    screen.status.set = lambda text, severity: messages.append(text)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert messages
    assert messages[-1].endswith("— active binary resolves to /opt/x/bin/foo")


def test_detail_escapes_path_with_bracket(tmp_path: Path) -> None:
    path = Path("/opt/a[red]b/bin/foo")
    unknown = _tool("foo")
    shadowed = _tool("bar")
    records = (
        (
            unknown,
            _ownership(
                unknown,
                owner="unknown",
                unknown_reason="no manager claimed this tool",
                active_path=path,
            ),
        ),
        (
            shadowed,
            _ownership(
                shadowed,
                owner="brew",
                shadowed=True,
                active_path=path,
                candidates=(
                    OwnershipCandidate(
                        owner="sdkman",
                        method=None,
                        package=None,
                        current_version=None,
                        evidence="candidate",
                    ),
                    OwnershipCandidate(
                        owner="brew",
                        method=shadowed.methods[0],
                        package="bar",
                        current_version=None,
                        evidence="inventory",
                    ),
                ),
            ),
        ),
    )
    needle = "/opt/a[red]b/bin/foo"
    for tool, ownership in records:
        service = frozen_service(tmp_path)
        service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
        screen = _screen([tool], {}, version_refresh=service)
        screen._browser.detail_text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
        rendered = Text.from_markup(screen.detail_text)
        assert needle in rendered.plain
        start = rendered.plain.find("[red]")
        assert not any(
            span.start <= start < span.end and "red" in str(span.style) for span in rendered.spans
        )


def test_detail_text_flags_installed_shell_as_default_or_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zsh = _tool("zsh", category="shell")
    screen = _screen([zsh], {"zsh": True})
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")
    assert "this is your default shell" in screen._detail_text(zsh)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setenv("SHELL", "/bin/bash")
    assert "installed, but not your default shell" in screen._detail_text(zsh)  # pyright: ignore[reportPrivateUsage]


def test_detail_text_omits_default_shell_note_for_non_shell_tools() -> None:
    rg = _tool("rg", category="search")
    screen = _screen([rg], {"rg": True})
    assert "default shell" not in screen._detail_text(rg)  # pyright: ignore[reportPrivateUsage]


def test_unknown_owner_detail_contains_unknown_reason(tmp_path: Path) -> None:
    tool = _tool("rg")
    reason = "the brew inventory could not be read"
    ownership = _ownership(tool, owner="unknown", unknown_reason=reason)
    status = VersionStatus(
        tool_id="rg", installed="14.1.0", latest=None, outdated=None, stale=True, source="unknown"
    )
    service = frozen_service(tmp_path)
    service.publish(
        [pass_state(tool, platform=service.platform, ownership=ownership, version=status)]
    )
    screen = _screen([tool], {}, version_refresh=service)
    service.publish(
        [pass_state(tool, platform=service.platform, ownership=ownership, version=status)]
    )
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert reason in text
    cell = screen._ver_cell(tool)  # pyright: ignore[reportPrivateUsage]
    # A probed version is real information even with no "latest" to diff
    # against (e.g. a dnf/apt/pacman package -- ownership.py deliberately
    # doesn't track those managers), so the cell keeps it, unmarked.
    assert cell.plain == "14.1.0"
    assert "re-check is pending" not in text


# -- D-05/Task 3: the catalog detail line names the OS manager that owns
# the row, and the update key still routes through the update service, not
# a second screen-local gate. -----------------------------------------------


def test_native_owner_detail_names_manager_and_no_update_fact(tmp_path: Path) -> None:
    tool = _tool("jq")
    service = frozen_service(tmp_path)
    service.publish(
        [pass_state(tool, platform=service.platform, ownership=_ownership(tool, owner="dnf"))]
    )
    screen = _screen([tool], {"jq": True}, version_refresh=service)
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "dnf" in text
    assert "not update" in text.lower()


async def test_native_owner_update_key_reaches_the_service_and_renders_its_refusal(
    tmp_path: Path,
) -> None:
    """Proves no second gate was added: a screen-local short-circuit would
    show a message without the service ever being asked."""
    tool = _tool("jq")
    ownership = _ownership(tool, owner="dnf")
    service = frozen_service(tmp_path)
    reresolve_calls: list[str] = []

    def reresolve(target: Tool) -> ManagerOwnership:
        reresolve_calls.append(target.id)
        return ownership

    runner_calls: list[list[str]] = []

    def recording_runner(argv: list[str]) -> None:
        runner_calls.append(argv)

    updates = UpdateService(
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=recording_runner,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=reresolve,
    )
    app = _unified_app([tool], {"jq": True}, _BLURBS, version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=ownership,
                    version=VersionStatus(
                        tool_id="jq",
                        installed="1.7",
                        latest=None,
                        outdated=None,
                        stale=True,
                        source="unknown",
                    ),
                )
            ]
        )
        app.catalog._browser.highlighted_id = lambda: "jq"  # type: ignore[method-assign]
        await pilot.press("u")
        await _wait_until(pilot, lambda: reresolve_calls == ["jq"])
        await _wait_until(pilot, lambda: "dnf" in app.catalog.status_text)
    assert "dnf" in app.catalog.status_text
    assert runner_calls == []


def test_pinned_spec_appears_in_detail_line(tmp_path: Path) -> None:
    tool = _tool("mmdc")
    service = frozen_service(tmp_path)
    screen = _screen([tool], {"mmdc": True}, version_refresh=service)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=_ownership(tool, owner="pnpm"),
                version=VersionStatus(
                    tool_id="mmdc",
                    installed="11.0.0",
                    latest="11.1.0",
                    outdated=True,
                    stale=False,
                    source="pnpm",
                    pinned_spec="puppeteer ^25",
                ),
            )
        ]
    )
    text = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "puppeteer ^25" in text


def test_stale_latest_has_marker_and_detail_explanation(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew")
    service = frozen_service(tmp_path)
    screen = _screen([tool], {}, version_refresh=service)

    def cell_and_detail(*, stale: bool) -> tuple[str, str]:
        version = VersionStatus(
            tool_id="rg",
            installed="14.1.0",
            latest="14.1.1",
            outdated=True,
            stale=stale,
            source="brew",
        )
        service.publish(
            [pass_state(tool, platform=service.platform, ownership=ownership, version=version)]
        )
        cell = screen._ver_cell(tool).plain  # pyright: ignore[reportPrivateUsage]
        return cell, screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]

    stale_cell, stale_detail = cell_and_detail(stale=True)
    assert stale_cell.endswith(" ~")
    assert "re-check is pending" in stale_detail
    fresh_cell, fresh_detail = cell_and_detail(stale=False)
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
    service = frozen_service(tmp_path)
    screen = _screen([tool], {"pnpm": True}, version_refresh=service)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=_ownership(tool, owner="installer"),
                version=VersionStatus(
                    tool_id="pnpm",
                    installed="11.9.0",
                    latest=None,
                    outdated=None,
                    stale=True,
                    source="installer",
                ),
            )
        ]
    )
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
    service = frozen_service(tmp_path)
    started: list[str] = []
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"rg": True}, version_refresh=service, updates=updates)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=ownership,
                version=VersionStatus(
                    tool_id="rg",
                    installed="14.1.1",
                    latest="14.1.1",
                    outdated=False,
                    stale=False,
                    source="brew",
                ),
            )
        ]
    )
    screen._browser.highlighted_id = lambda: "rg"  # type: ignore[method-assign]
    screen._update_tool_worker = lambda target: started.append(target.tool.id)  # type: ignore[method-assign]
    messages: list[str] = []
    screen.status.set = lambda text, severity: messages.append(text)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert started == []
    assert messages == ["rg is already current"]


def _sdkman_tool(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="lang",
        cmd=tool_id,
        methods=(Method(kind="sdkman", params={"candidate": tool_id}),),
    )


def _counting_begin(updates: UpdateService) -> list[str]:
    begins: list[str] = []
    original = updates.begin

    def begin(tool_id: str) -> bool:
        begins.append(tool_id)
        return original(tool_id)

    updates.begin = begin  # type: ignore[method-assign]
    return begins


def test_off_policy_owner_cell_and_detail_name_the_declared_manager(tmp_path: Path) -> None:
    tool = _sdkman_tool("groovy")
    ownership = _ownership(tool, owner="brew", off_policy=True)
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    service.publish([pass_state(tool, platform=service.platform, ownership=ownership)])
    screen = _screen([tool], {}, version_refresh=service)
    cell = screen._owner_cell(tool)  # pyright: ignore[reportPrivateUsage]
    assert cell.plain == "Homebrew ≠ policy"
    tag = " ≠ policy"
    start = cell.plain.find(tag)
    assert any(span.start <= start < span.end and "dim" in str(span.style) for span in cell.spans)
    detail = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "the catalog's policy installs groovy via SDKMAN" in detail


def test_update_on_current_off_policy_tool_explains_and_does_not_begin(tmp_path: Path) -> None:
    tool = _sdkman_tool("groovy")
    ownership = _ownership(tool, owner="brew", off_policy=True)
    service = frozen_service(tmp_path)
    updates = _update_service(lambda _tool: ownership)
    begins = _counting_begin(updates)
    screen = _screen([tool], {"groovy": True}, version_refresh=service, updates=updates)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=ownership,
                version=VersionStatus(
                    tool_id="groovy",
                    installed="4.0.0",
                    latest="4.0.0",
                    outdated=False,
                    stale=False,
                    source="brew",
                ),
            )
        ]
    )
    screen._browser.highlighted_id = lambda: "groovy"  # type: ignore[method-assign]
    messages: list[str] = []
    screen.status.set = lambda text, severity: messages.append(text)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert begins == []
    assert messages == [
        "groovy is already current — Homebrew owns this copy; the catalog installs it via "
        "SDKMAN, and moving it there is not available yet"
    ]


def test_update_on_current_tool_says_already_current(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew")
    service = frozen_service(tmp_path)
    updates = _update_service(lambda _tool: ownership)
    begins = _counting_begin(updates)
    screen = _screen([tool], {"rg": True}, version_refresh=service, updates=updates)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=ownership,
                version=VersionStatus(
                    tool_id="rg",
                    installed="14.1.1",
                    latest="14.1.1",
                    outdated=False,
                    stale=False,
                    source="brew",
                ),
            )
        ]
    )
    screen._browser.highlighted_id = lambda: "rg"  # type: ignore[method-assign]
    messages: list[str] = []
    screen.status.set = lambda text, severity: messages.append(text)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert begins == []
    assert messages == ["rg is already current"]


def test_update_on_stale_current_qualifies_the_last_check(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew")
    service = frozen_service(tmp_path)
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"rg": True}, version_refresh=service, updates=updates)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=ownership,
                version=VersionStatus(
                    tool_id="rg",
                    installed="14.1.1",
                    latest="14.1.1",
                    outdated=False,
                    stale=True,
                    source="brew",
                ),
            )
        ]
    )
    screen._browser.highlighted_id = lambda: "rg"  # type: ignore[method-assign]
    messages: list[tuple[str, str]] = []
    screen.status.set = lambda text, severity: messages.append((text, severity))  # type: ignore[method-assign]
    screen.action_update_tool()
    assert messages == [("rg is current as of the last check", "ok")]


def test_update_on_stale_current_off_policy_keeps_the_tail(tmp_path: Path) -> None:
    tool = _sdkman_tool("groovy")
    ownership = _ownership(tool, owner="brew", off_policy=True)
    service = frozen_service(tmp_path)
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"groovy": True}, version_refresh=service, updates=updates)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=ownership,
                version=VersionStatus(
                    tool_id="groovy",
                    installed="4.0.0",
                    latest="4.0.0",
                    outdated=False,
                    stale=True,
                    source="brew",
                ),
            )
        ]
    )
    screen._browser.highlighted_id = lambda: "groovy"  # type: ignore[method-assign]
    messages: list[tuple[str, str]] = []
    screen.status.set = lambda text, severity: messages.append((text, severity))  # type: ignore[method-assign]
    screen.action_update_tool()
    assert messages == [
        (
            "groovy is current as of the last check — Homebrew owns this copy; the catalog "
            "installs it via SDKMAN, and moving it there is not available yet",
            "ok",
        )
    ]


def test_action_update_tool_refuses_non_mutation_grade(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(
        tool, owner="unknown", unknown_reason="the brew inventory could not be read"
    )
    service = frozen_service(tmp_path)
    started: list[str] = []
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"rg": True}, version_refresh=service, updates=updates)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=ownership,
                version=VersionStatus(
                    tool_id="rg",
                    installed="14.1.0",
                    latest="14.1.1",
                    outdated=True,
                    stale=False,
                    source="unknown",
                ),
            )
        ]
    )
    screen._browser.highlighted_id = lambda: "rg"  # type: ignore[method-assign]
    screen._update_tool_worker = lambda target: started.append(target.tool.id)  # type: ignore[method-assign]
    messages: list[str] = []
    screen.status.set = lambda text, severity: messages.append(text)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert started == []
    assert any("brew inventory" in message for message in messages)


def test_action_update_tool_reports_an_in_flight_refresh_instead_of_a_silent_noop(
    tmp_path: Path,
) -> None:
    """CR-02 (15.4-REVIEW.md): no current state used to be a
    bare `return` -- no status line, no message. After one in-catalog update
    that is the answer for every OTHER tool in the catalog, so pressing `u`
    on any of them was a silent no-op the user had no way to interpret."""
    tool = _tool("rg")
    service = frozen_service(tmp_path)
    ownership = _ownership(tool, owner="brew")
    service.publish(
        [
            pass_state(
                tool, platform=service.platform, ownership=ownership, version=_outdated_status("rg")
            )
        ]
    )
    # The exact shape an epoch bump leaves behind: a state is present, but
    # from a superseded epoch, so `state_of` answers `None`.
    service.invalidate(reason="updated some other tool")
    assert service.state_of("rg") is None
    started: list[str] = []
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"rg": True}, version_refresh=service, updates=updates)
    screen._browser.highlighted_id = lambda: "rg"  # type: ignore[method-assign]
    screen._update_tool_worker = lambda target: started.append(target.tool.id)  # type: ignore[method-assign]
    messages: list[str] = []
    screen.status.set = lambda text, severity: messages.append(text)  # type: ignore[method-assign]
    screen.action_update_tool()
    assert started == []
    assert any("cannot update rg" in message for message in messages)
    assert any("its state is still being checked" in message for message in messages)


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
    service = frozen_service(tmp_path)
    started: list[str] = []
    updates = _update_service(lambda _tool: ownership)
    screen = _screen([tool], {"pnpm": True}, version_refresh=service, updates=updates)
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                ownership=ownership,
                version=VersionStatus(
                    tool_id="pnpm",
                    installed="11.9.0",
                    latest=None,
                    outdated=None,
                    stale=True,
                    source="installer",
                ),
            )
        ]
    )
    screen._browser.highlighted_id = lambda: "pnpm"  # type: ignore[method-assign]

    def fake_worker(target: UpdateTarget) -> None:
        started.append(target.tool.id)

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
    """Let the on_mount version-refresh worker finish before a test publishes
    its own states, so the mount-time pass cannot land after them."""
    await _wait_until(pilot, lambda: not app.catalog.version_refreshing)


async def test_update_success_renders_new_version_on_status_line(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = frozen_service(tmp_path)
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
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=ownership,
                    version=_outdated_status("rg"),
                )
            ]
        )
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating rg" not in app.catalog.status_text)
        assert "updated rg" in app.catalog.status_text
        assert "update failed" not in app.catalog.status_text


def test_a_single_tool_refresh_after_invalidate_strands_every_other_record(
    tmp_path: Path,
) -> None:
    """CR-02 (15.4-REVIEW.md), the service-level half: this pins the map
    state `UpdateService.run` + `_update_tool_worker` actually produce, so the
    screen-level recovery test below is provably exercising a real condition
    and not a hypothetical one. Exactly one tool carries the current epoch;
    every other tool's state is stranded under the previous one and
    `state_of` answers `None` for it."""
    alpha, beta = _tool("alpha"), _tool("beta")
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: "1.0",
    )
    service.refresh([alpha, beta])
    assert service.state_of("alpha") is not None
    assert service.state_of("beta") is not None
    service.invalidate(reason="updated alpha")  # what UpdateService.run does
    service.refresh([alpha])  # a single-tool pass after the invalidate
    assert service.state_of("alpha") is not None
    assert service.state_of("beta") is None


async def test_an_in_catalog_update_restores_the_whole_owner_column(tmp_path: Path) -> None:
    """CR-02 (15.4-REVIEW.md): one `u` press on ONE tool blanked the Owner
    column for the ENTIRE catalog and made `u` a silent no-op on every other
    row until the user navigated away and back. `on_tool_updated` now kicks
    the full pass that replaces the invalidate the update performed, so the
    untouched tool's state is current again once it lands."""
    rg, fd = _tool("rg"), _tool("fd")
    ownership_rg = _ownership(rg, owner="brew", package="rg")
    ownership_fd = _ownership(fd, owner="brew", package="fd")
    service = frozen_service(tmp_path)
    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=lambda _argv: None,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership_rg,
        # Wired exactly as setup.py wires it: the invalidate is what bumps the
        # shared epoch and strands every untouched tool's state.
        invalidate=service.invalidate,
    )
    app = _unified_app(
        [rg, fd], {"rg": True, "fd": True}, _BLURBS, version_refresh=service, updates=updates
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service.publish(
            [
                pass_state(
                    rg,
                    platform=service.platform,
                    ownership=ownership_rg,
                    version=_outdated_status("rg"),
                ),
                pass_state(fd, platform=service.platform, ownership=ownership_fd),
            ]
        )
        # Pin which row `u` acts on; the rest of the pipeline (worker,
        # UpdateService.run, the ToolUpdated message loop) stays real.
        app.catalog._browser.highlighted_id = lambda: "rg"  # type: ignore[method-assign]
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating rg" not in app.catalog.status_text)
        assert "updated rg" in app.catalog.status_text
        await _wait_until(pilot, lambda: not app.catalog.version_refreshing)
        # The untouched tool answers again -- without the follow-on pass it
        # stays `None` (and its Owner cell stays blank) for the rest of the
        # session, or until the user navigates away and back.
        assert service.state_of("fd") is not None
        assert app.catalog._row_cells(fd)[7].plain != ""  # pyright: ignore[reportPrivateUsage]


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
    service = frozen_service(tmp_path)
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
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=ownership,
                    version=_outdated_status("pnpm", source="installer"),
                )
            ]
        )
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating pnpm" not in app.catalog.status_text)
        status = app.catalog.status_text
        assert "updated pnpm" in status
        assert "replayed typescript, eslint" in status
        assert "removed a stale cache entry" in status
        assert "postinstall shim needs manual review" in status


# -- 15.6-05/D-01: the direct `u` route covers the same terminal synchronizer
# Plan 04 wired for Policies -- a successful update, then a nonfatal terminal
# follow-up warning rendered beside it without downgrading the status. -------


async def test_update_success_reports_terminal_follow_up_warning_without_downgrading(
    tmp_path: Path,
) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = frozen_service(tmp_path)

    def failing_terminal_follow_up() -> str | None:
        raise OSError("konsole profile is not writable")

    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=lambda _argv: None,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        terminal_follow_up=failing_terminal_follow_up,
    )
    app = _unified_app([tool], {"rg": True}, _BLURBS, version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=ownership,
                    version=_outdated_status("rg"),
                )
            ]
        )
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating rg" not in app.catalog.status_text)
        status = app.catalog.status_text
        assert "updated rg" in status
        assert "konsole profile is not writable" in status
        assert "update failed" not in status


async def test_update_via_u_calls_the_injected_terminal_follow_up_exactly_once(
    tmp_path: Path,
) -> None:
    """D-01: the direct `u` route must reach `UpdateService`'s callback
    through `action_update_tool`'s existing `UpdateService.run` call -- not a
    second, `CatalogScreen`-owned mutation path that duplicates the sync."""
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = frozen_service(tmp_path)
    calls: list[int] = []

    def terminal_follow_up() -> str | None:
        calls.append(1)
        return None

    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=lambda _argv: None,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        terminal_follow_up=terminal_follow_up,
    )
    app = _unified_app([tool], {"rg": True}, _BLURBS, version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=ownership,
                    version=_outdated_status("rg"),
                )
            ]
        )
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating rg" not in app.catalog.status_text)
        assert "updated rg" in app.catalog.status_text
        assert calls == [1]


async def test_update_failure_renders_status_line(tmp_path: Path) -> None:
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = frozen_service(tmp_path)

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
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=ownership,
                    version=_outdated_status("rg"),
                )
            ]
        )
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
    service = frozen_service(tmp_path)
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
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=cached_ownership,
                    version=_outdated_status("rg"),
                )
            ]
        )
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updating rg" not in app.catalog.status_text)
        status = app.catalog.status_text
        assert "updated rg" not in status
        assert "brew inventory changed mid-flight" in status


async def test_second_update_press_shows_already_in_flight(tmp_path: Path) -> None:
    import threading

    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = frozen_service(tmp_path)
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
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=ownership,
                    version=_outdated_status("rg"),
                )
            ]
        )
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


def _skill_pack(
    tool_id: str, probes: tuple[SkillStatusProbe, ...], *, tier: str = "system"
) -> Tool:
    manual = SkillOperation(
        mode="manual-required", instructions=("Review and run the official flow.",)
    )
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="skill_pack"),),
        tier=tier,
        skill_lifecycle=SkillLifecycle(
            source="https://github.com/example/skills",
            owner="example",
            supported_harnesses=tuple(dict.fromkeys(probe.harness for probe in probes)),
            revision_policy="upstream-latest",
            targets=(SkillTarget("harness", "<codex-plugin-dir>/demo"),),
            install=manual,
            status=manual,
            update=manual,
            removal=manual,
            status_probes=probes,
        ),
    )


_CLAUDE_SUPERPOWERS_JSON = (
    '[{"id": "superpowers@claude-plugins-official", "scope": "user", '
    '"enabled": true, "version": "6.4.1"}]'
)


async def test_skill_worker_paints_superpowers_installed_with_claude_code_owner(
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def skill_probe(argv: list[str]) -> str:
        calls.append(list(argv))
        if argv == ["claude", "plugin", "list", "--json"]:
            return _CLAUDE_SUPERPOWERS_JSON
        return ""

    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: None,
        skill_probe=skill_probe,
        skill_home=tmp_path,
    )
    app = _unified_app([pack], {"superpowers": False}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(140, 30)) as pilot:
        await _wait_until(pilot, lambda: not app.catalog.skill_refreshing)
        await pilot.pause()
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("superpowers", "health").plain == "✓"
        assert table.get_cell("superpowers", "owner").plain == "Claude Code"
    assert calls


def _skill_hosts(service: VersionRefreshService, tool_id: str) -> SkillHostStatus | None:
    """The host answers the tool's published state carries."""
    state = service.state_of(tool_id)
    return state.skill_hosts if state is not None else None


def _claude_has_superpowers(argv: list[str]) -> str:
    return _CLAUDE_SUPERPOWERS_JSON if argv == ["claude", "plugin", "list", "--json"] else ""


def _skill_screen(
    tmp_path: Path,
    hosts: dict[str, str] | None,
    *,
    stale: bool = False,
    refreshing: bool = False,
) -> tuple[CatalogScreen, Tool]:
    """A screen over a frozen pack state with these host answers (no state at
    all when `hosts` is None)."""
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = frozen_service(tmp_path)
    if hosts is not None:
        service.publish(
            [
                pass_state(
                    pack,
                    platform=service.platform,
                    present="present" in hosts.values(),
                    skill_hosts=SkillHostStatus(hosts=dict(hosts), stale=stale),
                )
            ]
        )
    screen = _screen([pack], {}, version_refresh=service)
    screen.skill_refreshing = refreshing
    return screen, pack


def test_skill_health_cell_reads_a_persisted_answer_without_a_stale_variant(
    tmp_path: Path,
) -> None:
    from installer.version_status import SKILL_SEEDED_NOTE

    path = tmp_path / "versions.json"
    save_version_cache(path, {}, skills={"superpowers": {"claude": "present"}})
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = offline_service(
        path,
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: None,
        skill_home=tmp_path,
    )
    service.seed_skills_from_cache()
    service.refresh([pack])
    state = service.state_of(pack.id)
    assert state is not None
    assert SKILL_SEEDED_NOTE in state.reasons
    screen = _screen([pack], {pack.id: False}, version_refresh=service)
    cell = screen._row_cells(pack)[5]  # pyright: ignore[reportPrivateUsage]
    assert (cell.plain, str(cell.style)) == ("✓", "green")


def test_skill_health_cell_is_ok_after_the_probe_lands(tmp_path: Path) -> None:
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = seeded_service(
        [pack],
        cache_path=tmp_path / "versions.json",
        home=tmp_path,
        skill_probe=_claude_has_superpowers,
    )
    screen = _screen([pack], {pack.id: False}, version_refresh=service)
    cell = screen._row_cells(pack)[5]  # pyright: ignore[reportPrivateUsage]
    assert cell.plain == "✓"


def test_skill_health_cell_is_checking_until_a_host_answers(tmp_path: Path) -> None:
    screen, pack = _skill_screen(tmp_path, None, refreshing=True)
    cell = screen._row_cells(pack)[5]  # pyright: ignore[reportPrivateUsage]
    assert (cell.plain, str(cell.style)) == ("…", "dim")


def test_skill_health_cell_is_checking_when_every_host_is_unknown(tmp_path: Path) -> None:
    def skill_probe(_argv: list[str]) -> str:
        raise OSError("harness down")

    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = seeded_service(
        [pack], cache_path=tmp_path / "versions.json", home=tmp_path, skill_probe=skill_probe
    )
    status = _skill_hosts(service, pack.id)
    assert status is not None
    assert set(status.hosts.values()) == {"unknown"}
    screen = _screen([pack], {pack.id: True}, version_refresh=service)
    cell = screen._row_cells(pack)[5]  # pyright: ignore[reportPrivateUsage]
    assert (cell.plain, str(cell.style)) == ("…", "dim")


def test_skill_owner_cell_lists_hosts_and_truncates_when_wider_than_the_column(
    tmp_path: Path,
) -> None:
    from installer.catalog_tui import _OWNER_CELL_MAX  # pyright: ignore[reportPrivateUsage]
    from installer.ownership import OWNER_LABELS

    assert max(len(label) for label in OWNER_LABELS.values()) == _OWNER_CELL_MAX

    claude_pi, pack = _skill_screen(tmp_path, {"claude": "present", "pi": "present"})
    assert claude_pi._owner_cell(pack).plain == "Claude Code, Pi"  # pyright: ignore[reportPrivateUsage]

    three, pack = _skill_screen(
        tmp_path, {"claude": "present", "codex": "present", "pi": "present"}
    )
    assert three._owner_cell(pack).plain == "Claude Code +2"  # pyright: ignore[reportPrivateUsage]

    codex_pi, pack = _skill_screen(tmp_path, {"codex": "present", "pi": "present"})
    assert codex_pi._owner_cell(pack).plain == "Codex, Pi"  # pyright: ignore[reportPrivateUsage]

    none, pack = _skill_screen(tmp_path, {"claude": "absent", "pi": "unknown"})
    assert none._owner_cell(pack).plain == ""  # pyright: ignore[reportPrivateUsage]


def test_skill_detail_reads_the_pack_state_reasons_and_steps(tmp_path: Path) -> None:
    """The hosts a pack is installed in are the Owner cell's job; the detail
    explains the mark with the state's reasons and configuration steps."""
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = frozen_service(tmp_path)
    hosts = SkillHostStatus(hosts={"claude": "present", "codex": "absent"}, stale=False)
    step = ConfigStep("install superpowers for Codex", "skill_install", harness="codex")
    service.publish(
        [
            pass_state(
                pack,
                platform=service.platform,
                skill_hosts=hosts,
                misconfigured=("partial: missing on Codex",),
                unconfigured=(step,),
            )
        ]
    )
    screen = _screen([pack], {}, version_refresh=service)
    _identity, health = _detail_lines(screen, pack)
    assert health == (
        "≈ needs configuration — partial: missing on Codex"
        " — to configure: install superpowers for Codex"
    )
    assert "installed in:" not in screen._detail_text(pack)  # pyright: ignore[reportPrivateUsage]


def test_skill_rendering_leaves_a_non_pack_row_unchanged(tmp_path: Path) -> None:
    tool = _tool("rg")
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    plain = _screen([tool], {"rg": True})
    service = seeded_service(
        [tool, pack],
        cache_path=tmp_path / "versions.json",
        home=tmp_path,
        present={"rg"},
        skill_probe=_claude_has_superpowers,
    )
    wired = _screen([tool], {"rg": True}, version_refresh=service)
    wired.skill_refreshing = True

    def signature(screen: CatalogScreen) -> list[tuple[str, str]]:
        return [
            (cell.plain, str(cell.style))
            for cell in screen._row_cells(tool)  # pyright: ignore[reportPrivateUsage]
        ]

    assert signature(plain) == signature(wired)
    assert "installed in:" not in plain._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    assert "installed in:" not in wired._detail_text(tool)  # pyright: ignore[reportPrivateUsage]


def _counting_skill_probe(calls: list[list[str]]) -> Callable[[list[str]], str]:
    def skill_probe(argv: list[str]) -> str:
        calls.append(list(argv))
        if argv == ["claude", "plugin", "list", "--json"]:
            return _CLAUDE_SUPERPOWERS_JSON
        return ""

    return skill_probe


async def test_skill_probe_runs_once_across_three_catalog_entries(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: None,
        skill_probe=_counting_skill_probe(calls),
        skill_home=tmp_path,
    )
    app = _unified_app([pack], {"superpowers": False}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(140, 30)) as pilot:
        await _wait_until(pilot, lambda: not app.catalog.skill_refreshing)
        await pilot.pause()
        app.catalog.enter_view()
        await _wait_until(pilot, lambda: not app.catalog.skill_refreshing)
        await pilot.pause()
        app.catalog.enter_view()
        await _wait_until(pilot, lambda: not app.catalog.skill_refreshing)
        await pilot.pause()
    assert calls.count(["claude", "plugin", "list", "--json"]) == 1


async def test_skill_probe_runs_again_after_invalidate(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: None,
        skill_probe=_counting_skill_probe(calls),
        skill_home=tmp_path,
    )
    app = _unified_app([pack], {"superpowers": False}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(140, 30)) as pilot:
        await _wait_until(pilot, lambda: not app.catalog.skill_refreshing)
        await pilot.pause()
        assert calls.count(["claude", "plugin", "list", "--json"]) == 1
        service.invalidate(reason="x")
        app.catalog.enter_view()
        await _wait_until(pilot, lambda: not app.catalog.skill_refreshing)
        await pilot.pause()
    assert calls.count(["claude", "plugin", "list", "--json"]) == 2


async def test_skill_probe_failure_paints_unknown_and_keeps_the_app_running(tmp_path: Path) -> None:
    def skill_probe(_argv: list[str]) -> str:
        raise RuntimeError("harness down")

    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = offline_service(
        tmp_path / "versions.json",
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: None,
        skill_probe=skill_probe,
        skill_home=tmp_path,
    )
    app = _unified_app([pack], {"superpowers": False}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(140, 30)) as pilot:
        await _wait_until(pilot, lambda: not app.catalog.skill_refreshing)
        await pilot.pause()
        cell = app.catalog.query_one(DataTable[Any]).get_cell("superpowers", "health")
        assert cell.plain == "…"
        assert "dim" in str(cell.style)
    status = _skill_hosts(service, "superpowers")
    assert status is not None
    assert status.hosts == {"claude": "unknown"}


def test_skill_status_refreshed_discards_a_superseded_epoch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: None,
    )
    screen = _screen([pack], {"superpowers": False}, version_refresh=service)
    screen._version_refresh_generation = 1  # pyright: ignore[reportPrivateUsage]
    service.invalidate(reason="x")
    reloads = {"n": 0}

    def counting(_adapter: object) -> None:
        reloads["n"] += 1

    monkeypatch.setattr(screen._browser, "reload", counting)  # pyright: ignore[reportPrivateUsage]
    screen.on_skill_status_refreshed(SkillStatusRefreshed(generation=1, epoch=0))
    assert reloads["n"] == 0


async def test_skill_probe_covers_packs_when_system_view_mounts_first(tmp_path: Path) -> None:
    import json

    from installer.version_cache import save_version_cache

    calls: list[list[str]] = []
    system = _tool("rg", tier="system")
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
        tier="ai",
    )
    path = tmp_path / "versions.json"
    save_version_cache(path, {}, skills={"superpowers": {"claude": "present"}})
    service = offline_service(
        path,
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: None,
        skill_probe=_counting_skill_probe(calls),
        skill_home=tmp_path,
    )
    service.seed_skills_from_cache()
    app = _unified_app(
        [system, pack],
        {"rg": False, "superpowers": False},
        _BLURBS,
        version_refresh=service,
    )
    async with app.run_test(size=(140, 30)) as pilot:
        assert app.current_view == "system"
        await _wait_until(pilot, lambda: not app.catalog.skill_refreshing)
        await pilot.pause()
        assert ["claude", "plugin", "list", "--json"] in calls
        status = _skill_hosts(service, "superpowers")
        assert status is not None
        assert status.stale is False
        raw = json.loads(path.read_text())
        assert raw["skills"]["superpowers"]
        before = len(calls)
        await pilot.press("3")
        await _wait_until(pilot, lambda: not app.catalog_for("ai").skill_refreshing)
        await pilot.pause()
        cell = app.catalog_for("ai").query_one(DataTable[Any]).get_cell("superpowers", "health")
        assert cell.plain == "✓"
        assert "~" not in cell.plain
        assert len(calls) == before


def _probe_less_pack_screen(tmp_path: Path, *, installed: bool) -> tuple[CatalogScreen, Tool]:
    pack = _skill_pack("openspec", ())
    assert pack.skill_lifecycle is not None
    assert pack.skill_lifecycle.status_probes == ()
    service = seeded_service(
        [pack],
        cache_path=tmp_path / "versions.json",
        home=tmp_path,
        present={pack.id} if installed else set[str](),
        which=lambda cmd: str(tmp_path / "bin" / cmd),
        probe_output=lambda _argv: "1.2.3",
    )
    screen = _screen([pack], {pack.id: installed}, version_refresh=service)
    return screen, pack


def test_skill_pack_with_no_status_probes_uses_path_presence(tmp_path: Path) -> None:
    screen, pack = _probe_less_pack_screen(tmp_path, installed=True)
    assert screen._ver_cell(pack).plain == "1.2.3"  # pyright: ignore[reportPrivateUsage]
    assert screen._row_cells(pack)[5].plain == "✓"  # pyright: ignore[reportPrivateUsage]
    groups = group_tools([pack], screen._health_of, "status", _BLURBS)  # pyright: ignore[reportPrivateUsage]
    assert [(title, [t.id for t in members]) for title, _detail, members in groups] == [
        ("✓ ok", ["openspec"])
    ]


def test_skill_pack_with_no_status_probes_is_absent_when_not_on_path(tmp_path: Path) -> None:
    screen, pack = _probe_less_pack_screen(tmp_path, installed=False)
    assert screen._row_cells(pack)[5].plain == "○"  # pyright: ignore[reportPrivateUsage]
    assert screen._ver_cell(pack).plain == ""  # pyright: ignore[reportPrivateUsage]


def test_skill_pack_with_probes_and_empty_hosts_stays_unknown(tmp_path: Path) -> None:
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = seeded_service(
        [pack], cache_path=tmp_path / "versions.json", home=tmp_path, skill_probe=lambda _a: ""
    )
    state = service.state_of(pack.id)
    assert state is not None
    assert state.health is Health.CHECKING
    assert state.present is False


def test_skill_pack_with_probes_present_host_stays_present(tmp_path: Path) -> None:
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = seeded_service(
        [pack],
        cache_path=tmp_path / "versions.json",
        home=tmp_path,
        skill_probe=_claude_has_superpowers,
    )
    state = service.state_of(pack.id)
    assert state is not None
    assert state.present is True


def test_a_failed_direct_update_renders_as_an_error_not_a_warning() -> None:
    """opencode H3 (screen half): a `u` update whose outcome is `failed` is an
    error, on the same severity as a raised worker error -- never a yellow
    warning for something that must turn the session exit code red."""
    screen = _screen([_tool("rg")], {"rg": True})
    messages: list[tuple[str, str]] = []
    screen.status.set = lambda text, severity: messages.append((text, severity))  # type: ignore[method-assign]
    outcome = UpdateOutcome(tool_id="rg", status="failed", owner="brew", detail="brew exploded")
    screen.on_tool_updated(ToolUpdated("rg", outcome, None, 0))
    assert messages == [("brew exploded", "error")]


class _FailingUpdateService(UpdateService):
    """An UpdateService whose run reports a failed outcome, never raises."""

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="failed",
            owner=target.ownership.owner,
            detail="brew exploded",
        )


async def test_a_failed_direct_update_folds_into_the_session_summary(
    tmp_path: Path,
) -> None:
    """opencode H3 (app half): a failed direct `u` update never reaches an
    ExecuteScreen summary, so the app itself must fold it into
    install_summary -- the session then has_failure, and the process exits 1
    even when the user quits without ever running an install."""
    tool = _tool("rg")
    ownership = _ownership(tool, owner="brew", package="rg")
    service = frozen_service(tmp_path)
    app = _unified_app(
        [tool],
        {"rg": True},
        _BLURBS,
        version_refresh=service,
        updates=_FailingUpdateService(
            platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
            runner=lambda _cmd: None,
            resolve_tag=lambda _repo: "v1",
            tools={},
            managed_packages=lambda: (),
            replay_globals=lambda packages: tuple(packages),
            reresolve_ownership=lambda _tool: ownership,
        ),
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        service.publish(
            [
                pass_state(
                    tool,
                    platform=service.platform,
                    ownership=ownership,
                    version=_outdated_status("rg"),
                )
            ]
        )
        await pilot.press("u")
        await _wait_until(pilot, lambda: "brew exploded" in app.catalog.status_text)
        summary = app.install_summary
        assert summary is not None
        assert "rg" in summary.update_failed
        assert summary.has_failure is True


# -- 19-13 Task 1: one Health cell per row from the published tool state (D-15)


_HEALTH_GLYPHS = {
    Health.CHECKING: ("…", "dim"),
    Health.BROKEN: ("!", "red"),
    Health.MISCONFIGURED: ("≈", "yellow"),
    Health.OUTDATED: ("↑", "yellow"),
    Health.OK: ("✓", "green"),
    Health.MISSING: ("○", ""),
    Health.UNAVAILABLE: ("–", "dim"),
}


def _health_cells(app: UnifiedApp, ids: list[str]) -> dict[str, str]:
    table = app.catalog.query_one(DataTable[Any])
    return {tool_id: table.get_cell(tool_id, "health").plain for tool_id in ids}


def test_health_cell_glyph_table(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = seeded_service(
        [tool], cache_path=tmp_path / "versions.json", home=tmp_path / "home", present={"rg"}
    )
    state = service.state_of("rg")
    assert state is not None
    for health, (glyph, style) in _HEALTH_GLYPHS.items():
        cell = health_cell(replace(state, health=health))
        assert (cell.plain, str(cell.style)) == (glyph, style), health
    checking = health_cell(None)
    assert (checking.plain, str(checking.style)) == ("…", "dim")


async def test_health_cell_is_checking_before_the_first_pass(tmp_path: Path) -> None:
    tools, installed = _catalog()
    ids = [tool.id for tool in tools]
    home = tmp_path / "home"
    started = threading.Event()
    release = threading.Event()

    def which(cmd: str) -> str | None:
        if cmd == "brew":
            started.set()
            assert release.wait(timeout=5)
        return str(home / ".local" / "bin" / cmd)

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=home,
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: None,
        which=which,
        present=lambda tool: tool.id == "rg",
    )
    app = _unified_app(tools, installed, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _wait_until(pilot, started.is_set)
        cells = _health_cells(app, ids)
        assert cells == dict.fromkeys(ids, "…")
        release.set()
        await _wait_until(pilot, lambda: _health_cells(app, ids)["rg"] == "✓")
        assert _health_cells(app, ids) == {"rg": "✓", "fd": "○", "lazygit": "○"}


def test_health_column_header() -> None:
    from installer.catalog_tui import _SORT_BY_COLUMN  # pyright: ignore[reportPrivateUsage]

    assert ("Health", "health") in _COLUMNS
    assert ("Inst", "inst") not in _COLUMNS
    assert _COLUMNS.index(("Health", "health")) == 5
    assert _SORT_BY_COLUMN["health"] == "health"


def test_broken_shim_row_shows_bang(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm_home = tmp_path / "pnpm"
    monkeypatch.setenv("PNPM_HOME", str(pnpm_home))
    tool = Tool(
        id="mmdc",
        name="mmdc",
        category="docs",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
    )
    service = seeded_service(
        [tool],
        cache_path=tmp_path / "versions.json",
        home=tmp_path / "home",
        present={"mmdc"},
        which=lambda cmd: str(pnpm_home / cmd),
    )
    state = service.state_of("mmdc")
    assert state is not None
    assert state.health is Health.BROKEN
    screen = _screen([tool], {"mmdc": True}, version_refresh=service)
    cell = screen._row_cells(tool)[5]  # pyright: ignore[reportPrivateUsage]
    assert cell.plain == "!"
    assert str(cell.style) == "red"


def test_skill_pack_rows_use_the_same_cell(tmp_path: Path) -> None:
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    unprobed = seeded_service(
        [pack], cache_path=tmp_path / "a" / "versions.json", home=tmp_path / "a"
    )
    screen = _screen([pack], {"superpowers": True}, version_refresh=unprobed)
    assert screen._row_cells(pack)[5].plain == "…"  # pyright: ignore[reportPrivateUsage]

    def skill_probe(argv: list[str]) -> str:
        return _CLAUDE_SUPERPOWERS_JSON if argv == ["claude", "plugin", "list", "--json"] else ""

    probed = seeded_service(
        [pack],
        cache_path=tmp_path / "b" / "versions.json",
        home=tmp_path / "b",
        skill_probe=skill_probe,
    )
    screen = _screen([pack], {"superpowers": False}, version_refresh=probed)
    cell = screen._row_cells(pack)[5]  # pyright: ignore[reportPrivateUsage]
    assert (cell.plain, str(cell.style)) == ("✓", "green")


def test_state_doubles_never_use_the_real_home(tmp_path: Path) -> None:
    from installer import version_status

    tool = _tool("rg")
    seeded_home = tmp_path / "seeded-home"
    offline_home = tmp_path / "offline-home"
    seeded = seeded_service(
        [tool], cache_path=tmp_path / "seeded.json", home=seeded_home, present={"rg"}
    )
    offline = offline_service(
        tmp_path / "offline.json",
        skill_home=offline_home,
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: None,
    )
    for service, home in ((seeded, seeded_home), (offline, offline_home)):
        assert service.managed_bin_dir.is_relative_to(home)
        assert not home.is_relative_to(_REAL_HOME)
        assert not service.managed_bin_dir.is_relative_to(_REAL_HOME)
    assert not version_status.default_skill_home().is_relative_to(_REAL_HOME)

    # No helper can default to Path.home(): the scratch home is a required keyword.
    def no_version(argv: list[str]) -> str | None:
        del argv
        return None

    without_home: dict[str, Any] = {"resolve_tag": str, "probe_output": no_version}
    with pytest.raises(TypeError, match="skill_home"):
        offline_service(tmp_path / "missing.json", **without_home)


# -- 19-13 Task 2: grouping, sort, selection and presence read the tool state


def _tier_gh_tool(tool_id: str, tier: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="github_release", params={"repo": f"owner/{tool_id}"}),),
        tier=tier,
    )


def _brew_on_path(home: Path) -> Callable[[str], str | None]:
    """`which` that finds only brew itself, so brew-method tools can install."""
    return lambda cmd: str(home / "homebrew" / "bin" / "brew") if cmd == "brew" else None


def _shim_tool() -> Tool:
    return Tool(
        id="mmdc",
        name="mmdc",
        category="docs",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
        tier="system",
    )


def _row_keys(table: DataTable[Any]) -> list[str]:
    return [str(row.key.value) for row in table.ordered_rows]


async def test_status_view_groups_by_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm_home = tmp_path / "pnpm"
    monkeypatch.setenv("PNPM_HOME", str(pnpm_home))
    home = tmp_path / "home"
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    tools = [
        _shim_tool(),
        _tool("rg", priority="P0"),
        _tool("fd"),
        _tool("container", method_os=("linux",)),
        pack,
    ]
    ids = [tool.id for tool in tools]

    def which(cmd: str) -> str | None:
        if cmd == "mmdc":
            return str(pnpm_home / cmd)
        return _brew_on_path(home)(cmd)

    service = seeded_service(
        tools,
        cache_path=tmp_path / "versions.json",
        home=home,
        present={"mmdc", "rg"},
        which=which,
    )
    health = {tool_id: state.health for tool_id in ids if (state := service.state_of(tool_id))}
    assert health == {
        "mmdc": Health.BROKEN,
        "rg": Health.OK,
        "fd": Health.MISSING,
        "container": Health.UNAVAILABLE,
        "superpowers": Health.CHECKING,
    }
    groups = group_tools(tools, lambda tool: health[tool.id], "status", _BLURBS)
    assert [(title, detail, [t.id for t in members]) for title, detail, members in groups] == [
        ("… checking", "checking…", ["superpowers"]),
        ("! broken", "broken", ["mmdc"]),
        ("✓ ok", "ok", ["rg"]),
        ("○ missing", "not installed", ["fd"]),
        ("– unavailable", "not available on this machine", ["container"]),
    ]
    app = _unified_app(tools, dict.fromkeys(ids, False), _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        while app.catalog.view != "status":
            await pilot.press("right")
        table = app.catalog.query_one(DataTable[Any])
        titles = [
            table.get_cell(key, "tool").plain.strip() for key in _row_keys(table) if key not in ids
        ]
        assert titles == [
            "── … checking (1)",
            "── ! broken (1)",
            "── ✓ ok (1)",
            "── ○ missing (1)",
            "── – unavailable (1)",
        ]
        table.move_cursor(row=table.get_row_index("fd"))
        await pilot.pause()
        app.catalog.enter_view()
        await _mount_and_settle(app, pilot)
        await pilot.pause()
        assert highlighted_key(table) == "fd"


def test_table_sorts_by_health_then_priority_then_id() -> None:
    tools = [
        _tool("b-ok", priority="P1"),
        _tool("a-ok", priority="P1"),
        _tool("z-ok", priority="P0"),
        _tool("broken", priority="P3"),
        _tool("missing", priority="P0"),
        _tool("pending", priority="P2"),
    ]
    health: dict[str, Health | None] = {
        "b-ok": Health.OK,
        "a-ok": Health.OK,
        "z-ok": Health.OK,
        "broken": Health.BROKEN,
        "missing": Health.MISSING,
        "pending": None,
    }
    ordered = sort_for_table(tools, lambda tool: health[tool.id], "health")
    assert [tool.id for tool in ordered] == [
        "pending",
        "broken",
        "z-ok",
        "a-ok",
        "b-ok",
        "missing",
    ]


async def test_unavailable_state_dims_and_blocks_selection(tmp_path: Path) -> None:
    tool = _tool("x")
    service = seeded_service(
        [tool],
        cache_path=tmp_path / "versions.json",
        home=tmp_path / "home",
        which=lambda _cmd: None,
    )
    state = service.state_of("x")
    assert state is not None
    assert state.health is Health.UNAVAILABLE
    app = _unified_app([tool], {"x": False}, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("x", "health").plain == "–"
        assert table.get_cell("x", "sel").plain == ""
        assert "dim" in str(table.get_cell("x", "pri").style)
        table.move_cursor(row=table.get_row_index("x"))
        await pilot.press("space")
        await pilot.press("a")
        assert "x" not in app.catalog.selected


async def test_brew_appearing_makes_the_row_selectable(tmp_path: Path) -> None:
    tool = _tool("x")
    home = tmp_path / "home"
    service = seeded_service(
        [tool],
        cache_path=tmp_path / "versions.json",
        home=home,
        which=_brew_on_path(home),
    )
    state = service.state_of("x")
    assert state is not None
    assert state.health is Health.MISSING
    # The launch-time map was computed before brew appeared.
    app = _unified_app([tool], {"x": False}, _BLURBS, {"x": True}, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("x", "sel").plain == "[ ]"
        assert "dim" not in str(table.get_cell("x", "pri").style)
        table.move_cursor(row=table.get_row_index("x"))
        await pilot.press("space")
        assert "x" in app.catalog.selected
        await pilot.press("enter")
    assert app.return_value == ["x"]


async def test_requires_presence_comes_from_state(tmp_path: Path) -> None:
    home = tmp_path / "home"
    pnpm = _tool("pnpm", tier="system")
    mmdc = _tool("mmdc", tier="ai", requires=("pnpm",))
    service = seeded_service(
        [pnpm, mmdc],
        cache_path=tmp_path / "versions.json",
        home=home,
        present={"pnpm"},
        which=_brew_on_path(home),
    )
    # The helper's presence seed says absent on purpose: the passed state must win.
    app = _unified_app(
        [pnpm, mmdc], {"pnpm": False, "mmdc": False}, _BLURBS, version_refresh=service
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("3")
        ai = app.catalog_for("ai")
        await _wait_until(pilot, lambda: not ai.version_refreshing)
        await pilot.press("space")
        await pilot.pause()
        assert "mmdc" in ai.selected
        assert "also needs" not in ai.status_text


async def test_refresh_worker_covers_the_full_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = [_tool("rg", tier="system"), _tool("mmdc", tier="ai"), _tool("jq", tier="user")]
    service = _seeded(tools, dict.fromkeys((tool.id for tool in tools), True))
    calls: list[set[str]] = []
    refresh = service.refresh

    def recording(batch: typing.Sequence[Tool]) -> dict[str, VersionStatus]:
        calls.append({tool.id for tool in batch})
        return refresh(batch)

    monkeypatch.setattr(service, "refresh", recording)
    app = _unified_app(
        tools, dict.fromkeys(("rg", "mmdc", "jq"), True), _BLURBS, version_refresh=service
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("3")
        ai = app.catalog_for("ai")
        await _wait_until(pilot, lambda: not ai.version_refreshing and len(calls) >= 2)
    assert calls
    assert all(batch == {"rg", "mmdc", "jq"} for batch in calls)


async def test_refresh_error_shows_the_retry_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools, installed = _catalog()
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path / "home",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: None,
    )

    def failing(batch: typing.Sequence[Tool]) -> dict[str, VersionStatus]:
        del batch
        raise OSError("boom")

    monkeypatch.setattr(service, "refresh", failing)
    app = _unified_app(tools, installed, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        await pilot.pause()
        assert app.catalog.status_text == (
            "tool state check failed: boom — leave and re-enter this view to retry"
        )
        assert app.catalog.status.severity is Severity.WARN
        assert set(_health_cells(app, [tool.id for tool in tools]).values()) == {"…"}


def _brew_owned_service(
    tmp_path: Path, tools: list[Tool], hold: dict[str, threading.Event | None]
) -> VersionRefreshService:
    brew = tmp_path / "brew"

    def probe_output(argv: list[str]) -> str | None:
        # Only a full pass probes fd: holding here holds the follow-up pass
        # and never a single-tool pass over the updated rg.
        gate = hold.get("gate")
        if gate is not None and Path(argv[0]).name == "fd":
            hold["started"] = gate
            assert gate.wait(timeout=5)
        return "1.0"

    def inventory(**_kwargs: object) -> ManagerInventory:
        return ManagerInventory(
            brew_formulae={tool.id: "1.0" for tool in tools},
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=brew,
        )

    def outdated(**_kwargs: object) -> OutdatedReport:
        return OutdatedReport(
            brew={"rg": ManagerVersion(current="1.0", latest="1.1")}, cask={}, pnpm={}, uv={}
        )

    return seeded_service(
        tools,
        cache_path=tmp_path / "versions.json",
        home=tmp_path / "home",
        present={tool.id for tool in tools},
        which=lambda cmd: str(brew / "bin" / cmd),
        probe_output=probe_output,
        read_inventory_fn=inventory,
        read_outdated_fn=outdated,
    )


async def test_update_shows_checking_on_every_row_until_the_full_pass(tmp_path: Path) -> None:
    tools, _installed = _catalog()
    ids = [tool.id for tool in tools]
    hold: dict[str, threading.Event | None] = {"gate": None}
    service = _brew_owned_service(tmp_path, tools, hold)
    updates = UpdateService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        runner=lambda _argv: None,
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda tool: _ownership(tool, owner="brew", package=tool.id),
        invalidate=service.invalidate,
    )
    app = _unified_app(
        tools, dict.fromkeys(ids, True), _BLURBS, version_refresh=service, updates=updates
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        assert _health_cells(app, ids) == {"rg": "↑", "fd": "✓", "lazygit": "✓"}
        table = app.catalog.query_one(DataTable[Any])
        table.move_cursor(row=table.get_row_index("rg"))
        await pilot.pause()
        gate = threading.Event()
        hold["gate"] = gate
        await pilot.press("u")
        await _wait_until(pilot, lambda: "updated rg" in app.catalog.status_text)
        await _wait_until(pilot, lambda: hold.get("started") is not None)
        assert _health_cells(app, ids) == dict.fromkeys(ids, "…")
        hold["gate"] = None
        gate.set()
        await _wait_until(pilot, lambda: _health_cells(app, ids)["rg"] != "…")
        assert _health_cells(app, ids) == {"rg": "↑", "fd": "✓", "lazygit": "✓"}


async def test_cache_save_warning_reaches_the_status_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import version_status

    tools, installed = _catalog()
    ids = [tool.id for tool in tools]
    fail = {"on": True}
    original = version_status.save_version_cache

    def save(path: Path, *args: Any, **kwargs: Any) -> None:
        if fail["on"]:
            raise OSError("disk full")
        original(path, *args, **kwargs)

    monkeypatch.setattr(version_status, "save_version_cache", save)
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path / "home",
        resolve_tag=lambda repo: "v1",
        probe_output=lambda argv: None,
        present=lambda tool: installed[tool.id],
    )
    app = _unified_app(tools, installed, _BLURBS, version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _mount_and_settle(app, pilot)
        await pilot.pause()
        assert app.catalog.status_text == (
            "version cache not saved: disk full — marks are current; the next start checks again"
        )
        assert app.catalog.status.severity is Severity.WARN
        assert _health_cells(app, ids) == {"rg": "✓", "fd": "○", "lazygit": "○"}
        fail["on"] = False
        app.catalog.enter_view()
        await _mount_and_settle(app, pilot)
        await pilot.pause()
        assert service.warning is None
        assert app.catalog.status_text == ""


async def test_quick_tier_switching_runs_one_full_pass(tmp_path: Path) -> None:
    tools = [
        _tier_gh_tool("sys-tool", "system"),
        _tier_gh_tool("usr-tool", "user"),
        _tier_gh_tool("ai-tool", "ai"),
    ]
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def resolve_tag(repo: str) -> str:
        calls.append(repo)
        if len(calls) == 1:
            started.set()
            assert release.wait(timeout=5)
        return "v1.0.0"

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path / "home",
        resolve_tag=resolve_tag,
        probe_output=lambda argv: "1.0.0",
    )
    app = _unified_app(
        tools, dict.fromkeys((tool.id for tool in tools), True), _BLURBS, version_refresh=service
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await _wait_until(pilot, started.is_set)
        await pilot.press("2")
        await pilot.press("3")
        await pilot.pause()
        release.set()
        screens = [app.catalog_for(tier) for tier in ("system", "user", "ai")]
        await _wait_until(pilot, lambda: not any(s.version_refreshing for s in screens))
        await pilot.pause()
        for screen, tool in zip(screens, tools, strict=True):
            cell = screen.query_one(DataTable[Any]).get_cell(tool.id, "health")
            assert cell.plain != "…", tool.id
    assert sorted(calls) == sorted(f"owner/{tool.id}" for tool in tools)


def test_catalog_screen_has_no_installed_parameter() -> None:
    """D-04: the catalog keeps no presence copy of its own; every mark reads the tool state."""
    assert "installed" not in inspect.signature(CatalogScreen).parameters
    assert "installed" not in inspect.signature(UnifiedApp).parameters
    assert not hasattr(CatalogScreen, "set_installed")
    assert not hasattr(UnifiedApp, "_rederive_installed")


# -- 19-15 Task 1: the Ver and Owner cells read the one tool state (19-UI-SPEC)


def _ver(
    installed: str | None, latest: str | None, outdated: bool | None, *, stale: bool = False
) -> VersionStatus:
    return VersionStatus(
        tool_id="rg",
        installed=installed,
        latest=latest,
        outdated=outdated,
        stale=stale,
        source="github",
    )


@pytest.mark.parametrize(
    ("case", "version", "expected"),
    [
        ("checking", None, ""),
        ("missing", _ver("1.2.3", "1.3.0", True), ""),
        ("unavailable", _ver("1.2.3", "1.3.0", True), ""),
        ("unreadable", _ver(None, None, None), ""),
        ("no latest", _ver("1.2.3", None, None), "1.2.3"),
        ("current", _ver("1.2.3", "1.2.3", False), "1.2.3"),
        ("outdated", _ver("1.2.3", "1.3.0", True), "1.2.3 -> 1.3.0"),
        ("stale current", _ver("1.2.3", "1.2.3", False, stale=True), "1.2.3 ~"),
        ("stale outdated", _ver("1.2.3", "1.3.0", True, stale=True), "1.2.3 -> 1.3.0 ~"),
    ],
)
def test_ver_cell_follows_the_state(
    case: str, version: VersionStatus | None, expected: str, tmp_path: Path
) -> None:
    tool = _tool("rg", method_os=("linux",)) if case == "unavailable" else _tool("rg")
    service = frozen_service(tmp_path)
    if version is not None:
        present = case not in ("missing", "unavailable")
        service.publish(
            [pass_state(tool, platform=service.platform, present=present, version=version)]
        )
    screen = _screen([tool], {}, version_refresh=service)
    cell = screen._ver_cell(tool)  # pyright: ignore[reportPrivateUsage]
    assert cell.plain == expected
    # The Health mark is the row's only color: the version text has no style,
    # and only the stale suffix is dim.
    assert str(cell.style) == ""
    assert [(cell.plain[s.start : s.end], str(s.style)) for s in cell.spans] == (
        [(" ~", "dim")] if expected.endswith(" ~") else []
    )


def test_owner_cell_follows_the_state(tmp_path: Path) -> None:
    rg = _tool("rg")
    groovy = _sdkman_tool("groovy")
    pending = _tool("fd")
    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    service = frozen_service(tmp_path)
    hosts = SkillHostStatus(hosts={"claude": "present", "pi": "present"}, stale=False)
    service.publish(
        [
            pass_state(rg, platform=service.platform, ownership=_ownership(rg, owner="brew")),
            pass_state(
                groovy,
                platform=service.platform,
                ownership=_ownership(groovy, owner="brew", off_policy=True),
            ),
            pass_state(pack, platform=service.platform, skill_hosts=hosts),
        ]
    )
    screen = _screen([rg, groovy, pending, pack], {}, version_refresh=service)
    screen.version_refreshing = True
    owner = screen._owner_cell  # pyright: ignore[reportPrivateUsage]
    assert owner(rg).plain == "Homebrew"
    off_policy = owner(groovy)
    assert off_policy.plain == "Homebrew ≠ policy"
    assert [(off_policy.plain[s.start : s.end], str(s.style)) for s in off_policy.spans] == [
        (" ≠ policy", "dim")
    ]
    # No state yet: the Health `…` already says checking, so Owner is blank.
    assert owner(pending).plain == ""
    assert owner(pack).plain == "Claude Code, Pi"


def test_frozen_state_service_publishes_without_probing(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = frozen_service(tmp_path)
    service.invalidate(reason="test")
    version = _ver("1.2.3", "1.3.0", True)
    service.publish([pass_state(tool, platform=service.platform, version=version)])
    state = service.state_of("rg")
    assert state is not None
    assert state.generation == service.epoch
    assert state.health is Health.OUTDATED
    # frozen_service's probes all raise, so a refresh that probed would fail.
    assert service.refresh([tool]) == {"rg": version}
    assert service.refresh_skills([tool]) == {}
    assert service.state_of("rg") == state
    service.invalidate(reason="a mutation")
    assert service.state_of("rg") is None
    service.refresh([tool])
    refreshed = service.state_of("rg")
    assert refreshed is not None
    assert refreshed.generation == service.epoch


# -- 19-15 Task 2: the focused-row detail is identity + health block (STATE-06)


def _detail_lines(screen: CatalogScreen, tool: Tool) -> list[str]:
    """The detail's plain text, one entry per line (identity, then health)."""
    markup = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    return Text.from_markup(markup).plain.split("\n")


def test_detail_health_block(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = frozen_service(tmp_path)
    steps = (ConfigStep("s1", "terminal_sync"), ConfigStep("s2", "terminal_sync"))
    service.publish(
        [pass_state(tool, platform=service.platform, misconfigured=("a", "b"), unconfigured=steps)]
    )
    screen = _screen([tool], {}, version_refresh=service)
    assert _detail_lines(screen, tool)[1] == "≈ needs configuration — a · b — to configure: s1; s2"
    # The glyph keeps the Health cell's style.
    assert "[yellow]≈[/]" in screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]

    service.publish([pass_state(tool, platform=service.platform)])
    assert _detail_lines(screen, tool)[1] == "✓ ok"

    pending = _tool("fd")
    no_state = _screen([pending], {}, version_refresh=frozen_service(tmp_path / "other"))
    assert _detail_lines(no_state, pending)[1] == "… checking…"
    no_state._unavailable["fd"] = True  # pyright: ignore[reportPrivateUsage]
    assert _detail_lines(no_state, pending)[1] == "… checking… — not available on this machine"


def test_detail_labels_per_health(tmp_path: Path) -> None:
    labels = {
        Health.CHECKING: "checking…",
        Health.BROKEN: "broken",
        Health.MISCONFIGURED: "needs configuration",
        Health.OUTDATED: "update available",
        Health.OK: "ok",
        Health.MISSING: "not installed",
        Health.UNAVAILABLE: "not available on this machine",
    }
    assert set(labels) == set(Health)
    tool = _tool("rg")
    service = frozen_service(tmp_path)
    screen = _screen([tool], {}, version_refresh=service)
    for health, label in labels.items():
        state = replace(pass_state(tool, platform=service.platform), health=health, reasons=())
        service.publish([state])
        glyph = health_cell(state).plain
        assert _detail_lines(screen, tool)[1] == f"{glyph} {label}", health


def test_detail_escapes_reasons_and_steps(tmp_path: Path) -> None:
    tool = _tool("rg")
    service = frozen_service(tmp_path)
    step = ConfigStep("point [bold]Konsole[/] at /opt/a[b/zsh", "terminal_sync")
    service.publish(
        [
            pass_state(
                tool,
                platform=service.platform,
                misconfigured=("reason [red]x[/]",),
                unconfigured=(step,),
            )
        ]
    )
    screen = _screen([tool], {}, version_refresh=service)
    markup = screen._detail_text(tool)  # pyright: ignore[reportPrivateUsage]
    rendered = Text.from_markup(markup)
    assert "reason [red]x[/]" in rendered.plain
    assert "to configure: point [bold]Konsole[/] at /opt/a[b/zsh" in rendered.plain
    # Only the glyph and the id carry a style; nothing the machine said does.
    styled = {rendered.plain[span.start : span.end] for span in rendered.spans}
    assert styled <= {"rg", "≈", "P1 recommended"}, styled


def test_detail_identity_line_is_unchanged(tmp_path: Path) -> None:
    tool = _tool(
        "zsh",
        category="shell",
        desc="the Z shell",
        requires=("brew",),
        recommends=("rg",),
        method_os=("linux",),
    )
    reason = UnavailableReason(short="linux only", detail="needs Linux; this is macOS")
    screen = CatalogScreen(
        [tool],
        _BLURBS,
        view="system",
        catalog=[tool],
        staged=set(),
        unavailable={"zsh": reason},
        version_refresh=frozen_service(tmp_path),
    )
    identity, health = _detail_lines(screen, tool)
    assert identity == (
        "zsh — the Z shell  |  P1 recommended  |  for both  |  requires brew  |  pairs well with rg"
    )
    assert reason.detail in health
    assert "default shell" not in identity


def test_default_shell_note_in_the_health_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zsh = _tool("zsh", category="shell")
    service = frozen_service(tmp_path)
    service.publish(
        [pass_state(zsh, platform=service.platform, ownership=_ownership(zsh, owner="brew"))]
    )
    screen = _screen([zsh], {}, version_refresh=service)
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")
    identity, health = _detail_lines(screen, zsh)
    assert health.startswith("✓ ok — managed by Homebrew")
    assert health.endswith(" · this is your default shell")
    assert "default shell" not in identity


_UI_SPEC_LEGEND = (
    "[green]✓ ok[/] · [yellow]↑ update[/] · [yellow]≈ config[/] · [red]! broken[/]"
    " · ○ missing · [dim]… checking[/] · [dim]– unavailable[/]\n"
    "[bold red]P0[/] essential · [bold yellow]P1[/] recommended · [blue]P2[/] nice-to-have"
    " · [dim]P3[/] niche · [bold cyan]AI[/] / [magenta]human[/] / both\n"
    "Ver a -> b: newer release · [dim]~[/] cached latest · [dim]≠ policy[/]: other manager owns it"
)


def test_legend_is_the_ui_spec_string() -> None:
    assert _LEGEND == _UI_SPEC_LEGEND
    lines = _LEGEND.split("\n")
    assert len(lines) == 3
    assert "✓ ok · ↑ update · ≈ config · ! broken · ○ missing" in Text.from_markup(lines[0]).plain


def test_legend_lines_fit_78_cells() -> None:
    widths = [cell_len(Text.from_markup(line).plain) for line in _LEGEND.split("\n")]
    assert widths == [78, 78, 77]


# -- 19-15 Task 3: `u` reads the tool state (19-UI-SPEC "Copywriting")


def _u_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: Tool, state: ToolState | None
) -> tuple[CatalogScreen, list[UpdateTarget], list[tuple[str, str]], list[str]]:
    """A screen with `tool` highlighted over a frozen machine holding `state`
    (none when None); returns the screen, the worker's targets, the status
    lines and the ids `begin` was asked about."""
    service = frozen_service(tmp_path)
    if state is not None:
        service.publish([state])
    updates = _update_service(lambda _tool: _ownership(tool, owner="brew"))
    begins = _counting_begin(updates)
    screen = _screen([tool], {}, version_refresh=service, updates=updates)
    targets: list[UpdateTarget] = []
    lines: list[tuple[str, str]] = []

    def highlighted(_browser: ToolBrowser[Tool]) -> str:
        return tool.id

    def show(text: str, severity: str) -> None:
        lines.append((text, severity))

    monkeypatch.setattr(ToolBrowser, "highlighted_id", highlighted)
    monkeypatch.setattr(screen, "_update_tool_worker", targets.append)
    monkeypatch.setattr(screen.status, "set", show)
    return screen, targets, lines, begins


def test_u_on_a_pending_row_says_checking(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool("rg")
    screen, targets, lines, begins = _u_screen(tmp_path, monkeypatch, tool, None)
    screen.action_update_tool()
    assert lines == [
        ("cannot update rg: its state is still being checked — try again in a moment", "warn")
    ]
    assert targets == []
    assert begins == []
    # A state that is itself CHECKING (a pack waiting on its hosts) is pending too.
    checking = replace(
        pass_state(
            tool, platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
        ),
        health=Health.CHECKING,
    )
    screen, targets, lines, _begins = _u_screen(tmp_path / "checking", monkeypatch, tool, checking)
    screen.action_update_tool()
    assert lines[-1][0].endswith("its state is still being checked — try again in a moment")
    assert targets == []


def test_u_on_a_broken_row_names_the_first_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _tool("rg")
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    state = pass_state(
        tool,
        platform=macos,
        ownership=_ownership(tool, owner="brew"),
        version=_outdated_status("rg"),
        broken=("changed since install", "another fact"),
    )
    assert state.health is Health.BROKEN
    screen, targets, lines, begins = _u_screen(tmp_path, monkeypatch, tool, state)
    screen.action_update_tool()
    assert lines == [("rg is broken: changed since install", "warn")]
    assert targets == []
    assert begins == []


def test_u_uses_the_state_ownership(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool("rg")
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    ownership = _ownership(tool, owner="brew", package="ripgrep")
    state = pass_state(tool, platform=macos, ownership=ownership, version=_outdated_status("rg"))
    assert state.health is Health.OUTDATED
    screen, targets, lines, begins = _u_screen(tmp_path, monkeypatch, tool, state)
    screen.action_update_tool()
    assert targets == [UpdateTarget(tool=tool, ownership=ownership)]
    assert begins == ["rg"]
    assert lines == [("updating rg…", "ok")]


def test_u_current_and_unknown_owner_copies_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _tool("rg")
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    current = VersionStatus(
        tool_id="rg",
        installed="14.1.1",
        latest="14.1.1",
        outdated=False,
        stale=False,
        source="brew",
    )
    state = pass_state(
        tool, platform=macos, ownership=_ownership(tool, owner="brew"), version=current
    )
    screen, targets, lines, _begins = _u_screen(tmp_path, monkeypatch, tool, state)
    screen.action_update_tool()
    assert lines == [("rg is already current", "ok")]
    assert targets == []

    unknown = _ownership(
        tool,
        owner="unknown",
        unknown_reason="the brew inventory could not be read",
        active_path=Path("/opt/x/bin/rg"),
    )
    state = pass_state(tool, platform=macos, ownership=unknown, version=_outdated_status("rg"))
    screen, targets, lines, _begins = _u_screen(tmp_path / "unknown", monkeypatch, tool, state)
    screen.action_update_tool()
    assert lines == [
        (
            "cannot update rg: the brew inventory could not be read"
            " — active binary resolves to /opt/x/bin/rg",
            "warn",
        )
    ]
    assert targets == []


def test_no_test_pokes_private_service_stores() -> None:
    """Tests seed state through the public doubles (tests/state_doubles.py),
    never by assigning a service's private ownership, status, skill or state
    store. Plan 19-18 widens this scan to every test file."""
    stores = "|".join(("_own" + "ership", "_stat" + "uses", "_sta" + "tes", "_sk" + "ills"))
    poke = re.compile(r"\.(?:" + stores + r")\b(?:\[[^\]]*\])?\s*=(?!=)")
    here = Path(__file__).parent
    hits = [
        f"{name}:{number}: {line.strip()}"
        for name in ("test_catalog_tui.py", "test_wizard_app.py")
        for number, line in enumerate((here / name).read_text().splitlines(), 1)
        if poke.search(line)
    ]
    assert hits == []
