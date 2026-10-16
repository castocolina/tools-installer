"""Composited-screen layout checks at the 80x20 minimum (19-UI-SPEC "Layout contract").

Every visibility claim reads the compositor through `screen.get_widget_at`, so a
widget another one paints over does not count as shown.
"""

from pathlib import Path
from typing import Any

import pytest
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import DataTable, Rule

from installer.doctor import DoctorReport
from installer.model import load_categories, load_tools
from installer.ui_common import FooterBar, ModeBadge, WayfindingHeader
from installer.uninstall import SweepResult
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs
from tests.state_doubles import seeded_service
from tests.test_registry import REGISTRY

_KEY = {"system": "1", "user": "2", "ai": "3", "doctor": "4", "uninstall": "5", "policies": "6"}


def _app(tmp_path: Path) -> UnifiedApp:
    tools = load_tools(REGISTRY)
    service = seeded_service(
        tools,
        cache_path=tmp_path / "versions.json",
        home=tmp_path / "home",
        present={tool.id for tool in tools[::2]},
    )
    return UnifiedApp(
        tools,
        load_categories(REGISTRY),
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
        policies=PolicyInputs(policies=[], link_mode=lambda: "symlink"),
        version_refresh=service,
    )


def rows_of(screen: Screen[Any], widget: Widget) -> set[int]:
    """The screen rows where `widget` (or one of its descendants) is topmost at some x."""
    width, height = screen.size
    rows: set[int] = set()
    for y in range(height):
        for x in range(width):
            hit, _region = screen.get_widget_at(x, y)
            if widget in hit.ancestors_with_self:
                rows.add(y)
                break
    return rows


async def _open(app: UnifiedApp, pilot: Any, view: str) -> Screen[Any]:
    await pilot.press(_KEY[view])
    await pilot.pause()
    await pilot.pause()
    return app.screen


@pytest.mark.parametrize("tier", ["system"])
async def test_catalog_tiers_show_all_legend_and_detail_rows_at_80x20(
    tmp_path: Path, tier: str
) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, tier)
        table = rows_of(screen, screen.query_one(DataTable[Any]))
        legend = rows_of(screen, screen.query_one("#browser-legend"))
        detail = rows_of(screen, screen.query_one("#browser-detail"))
        assert len(table) >= 6, table
        assert len(legend) == 3, legend
        assert len(detail) == 3, detail
        assert max(table) < min(legend) and max(legend) < min(detail), (table, legend, detail)


async def test_rule_has_no_margin(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "system")
        assert 0 in rows_of(screen, screen.query_one(WayfindingHeader))
        assert rows_of(screen, screen.query_one(Rule)) == {1}
        assert rows_of(screen, screen.query_one(ModeBadge)) == {2}
        assert rows_of(screen, screen.query_one(FooterBar)) == {19}
