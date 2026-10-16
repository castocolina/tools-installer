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
from installer.model import Tool, load_categories, load_tools
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.ui_common import FooterBar, ModeBadge, WayfindingHeader
from installer.uninstall import SweepResult
from installer.version_status import VersionRefreshService, VersionStatus
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs
from tests.state_doubles import frozen_service, pass_state, seeded_service
from tests.test_registry import REGISTRY

_KEY = {"system": "1", "user": "2", "ai": "3", "doctor": "4", "uninstall": "5", "policies": "6"}
_TIERS = ["system", "user", "ai"]


def _app(tmp_path: Path, service: VersionRefreshService | None = None) -> UnifiedApp:
    tools = load_tools(REGISTRY)
    if service is None:
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


@pytest.mark.parametrize("tier", _TIERS)
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


def _column_spans(table: DataTable[Any]) -> dict[str, tuple[int, int]]:
    """Each column's [start, end) screen x, from the widths Textual lays the columns out with."""
    spans: dict[str, tuple[int, int]] = {}
    x = table.region.x
    for column in table.columns.values():
        width = column.get_render_width(table)
        spans[column.label.plain] = (x, x + width)
        x += width
    return spans


@pytest.mark.parametrize("tier", _TIERS)
async def test_health_column_inside_80_columns(tmp_path: Path, tier: str) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, tier)
        table = screen.query_one(DataTable[Any])
        start, end = _column_spans(table)["Health"]
        assert end - 1 < 80, (start, end)
        header_y = table.region.y
        for x in range(start, end):
            hit, _region = screen.get_widget_at(x, header_y)
            assert table in hit.ancestors_with_self, (x, hit)


async def test_catalog_at_120x30(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(120, 30)) as pilot:
        for tier in _TIERS:
            screen = await _open(app, pilot, tier)
            table = screen.query_one(DataTable[Any])
            assert len(rows_of(screen, table)) >= 16, tier
            spans = _column_spans(table)
            assert spans["Owner"][1] <= table.region.right, (tier, spans)


def _assert_chrome(screen: Screen[Any]) -> None:
    assert 0 in rows_of(screen, screen.query_one(WayfindingHeader))
    assert rows_of(screen, screen.query_one("AppScreen > Rule", Rule)) == {1}
    assert rows_of(screen, screen.query_one(ModeBadge)) == {2}
    assert rows_of(screen, screen.query_one(FooterBar)) == {19}


async def test_doctor_chrome_at_80x20(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "doctor")
        _assert_chrome(screen)
        body = screen.query_one("#doctor-body")
        # The Doctor card keeps its own `margin: 2 0`: its box starts right under the chrome.
        assert min(rows_of(screen, body)) == 3 + body.styles.margin.top
        assert screen.get_widget_at(0, 3)[0] is screen


async def test_uninstall_chrome_at_80x20(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "uninstall")
        _assert_chrome(screen)
        assert rows_of(screen, screen.query_one(DataTable[Any]))
        assert len(rows_of(screen, screen.query_one("#browser-detail"))) == 3


async def test_policies_chrome_at_80x20(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "policies")
        _assert_chrome(screen)
        for selector in ("#link-mode-line", "#policy-detail"):
            assert rows_of(screen, screen.query_one(selector)), selector
        assert rows_of(screen, screen.query_one(DataTable[Any]))


_MACOS = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
# A Mac before Homebrew: some tools of every tier have no method here.
_NO_BREW = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
# The Health glyph and the style each state renders with (19-UI-SPEC "Columns").
_MARKS = {
    "broken": ("!", "red"),
    "misconfigured": ("≈", "yellow"),
    "outdated": ("↑", "yellow"),
    "ok": ("✓", "green"),
    "missing": ("○", ""),
    "unavailable": ("–", "dim"),
    "checking": ("…", "dim"),
}


def _one_tool_per_health(tier: str) -> dict[str, Tool]:
    tools = [tool for tool in load_tools(REGISTRY) if tool.tier == tier]
    unavailable = [tool for tool in tools if not resolve_methods(tool, _NO_BREW)]
    assert unavailable, f"no {tier} tool lacks a method without Homebrew"
    rest = [tool for tool in tools if tool is not unavailable[0] and resolve_methods(tool, _MACOS)]
    picked = dict(zip(_MARKS, rest, strict=False))
    picked["unavailable"] = unavailable[0]
    return picked


@pytest.mark.parametrize("tier", _TIERS)
async def test_every_health_mark_renders_on_every_tier(tmp_path: Path, tier: str) -> None:
    picked = _one_tool_per_health(tier)
    service = frozen_service(tmp_path, platform=_MACOS)
    outdated = picked["outdated"]
    version = VersionStatus(
        tool_id=outdated.id,
        installed="1.0.0",
        latest="1.0.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    service.publish(
        [
            pass_state(picked["broken"], platform=_MACOS, broken=("a broken shim",)),
            pass_state(picked["misconfigured"], platform=_MACOS, misconfigured=("no hook",)),
            pass_state(outdated, platform=_MACOS, version=version),
            pass_state(picked["ok"], platform=_MACOS),
            pass_state(picked["missing"], platform=_MACOS, present=False),
            pass_state(picked["unavailable"], platform=_NO_BREW, present=False),
        ]
    )
    app = _app(tmp_path, service)
    async with app.run_test(size=(120, 30)) as pilot:
        screen = await _open(app, pilot, tier)
        table = screen.query_one(DataTable[Any])
        for health, (glyph, style) in _MARKS.items():
            cell = table.get_cell(picked[health].id, "health")
            assert cell.plain == glyph, health
            assert style in str(cell.style), (health, cell.style)
        for cell in table.get_row(picked["unavailable"].id):
            assert "dim" in str(cell.style), cell
