"""Composited-screen layout checks at the 80x20 minimum (19-UI-SPEC "Layout contract").

Every visibility claim reads the compositor through `screen.get_widget_at`, so a
widget another one paints over does not count as shown.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from rich.cells import cell_len
from rich.console import Console
from rich.text import Text
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import DataTable, Rule

from installer.app import UninstallDecision
from installer.doctor import DoctorReport
from installer.enums import MutationHolder
from installer.model import Method, Tool, load_categories, load_tools
from installer.platform import Platform
from installer.policy import (
    Policy,
    PolicyResult,
    desktop_shell_policy,
)
from installer.resolve import resolve_methods
from installer.ui_common import FooterBar, ModeBadge, WayfindingHeader
from installer.uninstall import RemovalPlan, SweepResult
from installer.version_status import (
    LAYOUT_PROOF_NOTE,
    ToolState,
    VersionRefreshService,
    VersionStatus,
)
from installer.wizard_app import (
    ConfirmUninstall,
    PoliciesScreen,
    PolicyInputs,
    UnifiedApp,
    UninstallInputs,
    UninstallScreen,
)
from tests.screen_family import settle
from tests.state_doubles import (
    HeldRefreshService,
    absent_state,
    frozen_service,
    managed_state,
    pass_state,
    plan_state,
    removable_state,
    seeded_service,
)
from tests.test_registry import REGISTRY

_KEY = {
    "system": "1",
    "user": "2",
    "ai": "3",
    "doctor": "4",
    "uninstall": "5",
    "policies": "6",
    "schedules": "7",
}
_TIERS = ["system", "user", "ai"]


def _app(
    tmp_path: Path,
    service: VersionRefreshService | None = None,
    policies: list[Policy] | None = None,
    remove: Callable[[UninstallDecision], SweepResult] = lambda _decision: SweepResult(),
) -> UnifiedApp:
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
            ban_names=list,
            has_path_block=lambda: False,
            remove=remove,
        ),
        policies=PolicyInputs(policies=policies or [], link_mode=lambda: "symlink"),
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


async def test_doctor_status_line_stays_visible_at_80x20(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "doctor")
        app.begin_mutation(MutationHolder.GLOBALS_REINSTALL)
        await pilot.press("enter")
        await pilot.pause()
        status = app.view("doctor").status
        assert status.text.startswith("A pnpm reinstall is running")
        # The refusal is painted, on one row right above the footer, not under the card.
        assert rows_of(screen, status) == {18}
        assert rows_of(screen, screen.query_one(FooterBar)) == {19}


async def test_uninstall_chrome_at_80x20(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "uninstall")
        _assert_chrome(screen)
        assert rows_of(screen, screen.query_one(DataTable[Any]))
        assert len(rows_of(screen, screen.query_one("#browser-detail"))) == 3


async def test_uninstall_rows_fit_at_80x20_with_health(tmp_path: Path) -> None:
    tools = load_tools(REGISTRY)
    widest = max(tools, key=lambda tool: len(tool.id))
    long_paths = [Path(f"/home/someone/.local/share/a-long-directory-name/{n}/bin") for n in "abc"]
    service = frozen_service(tmp_path)
    service.publish([removable_state(widest, long_paths), managed_state(tools[0])])
    app = _app(tmp_path, service)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "uninstall")
        table = screen.query_one(DataTable[Any])
        spans = _column_spans(table)
        assert list(spans) == [
            "Sel",
            "Tool",
            "Health",
            "Cat",
            "Installed via",
            "What gets removed",
        ]
        # The widest catalog id and the owner label ("installer artifact" replaced
        # the old "userspace") leave the removes column few cells on an 80-column
        # screen, so "stays on screen" is its start plus a readable lead, and the
        # fixed cell budget (40 + 2 padding) bounds how far it can run on.
        start, end = spans["What gets removed"]
        assert start + 8 <= table.region.right, spans
        assert end - start <= 42, spans


async def test_uninstall_cursor_lands_on_the_removable_row_once_the_state_lands(
    tmp_path: Path,
) -> None:
    """Entered before the first pass publishes, Uninstall paints placeholder
    rows; once the state lands the cursor goes to the first removable row on
    top, not the placeholder row it sat on (tmux check, 2026-11-03)."""
    tools = load_tools(REGISTRY)
    removable = tools[5]
    service = HeldRefreshService(
        tmp_path,
        [
            managed_state(tools[0]),
            managed_state(tools[1]),
            removable_state(removable, [tmp_path / "bin" / removable.id]),
        ],
    )
    app = _app(tmp_path, service)
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            screen = await _open(app, pilot, "uninstall")
            service.release.set()
            await settle(app, pilot)
            table = screen.query_one(DataTable[Any])
            keys = [str(key.value) for key in table.rows]
            assert keys[:2] == ["#removable here", removable.id], keys[:4]
            assert keys[table.cursor_row] == removable.id
            assert table.region.y + 1 + table.cursor_row in rows_of(screen, table)
        finally:
            service.release.set()


async def test_a_one_tool_removal_summary_takes_one_status_row_at_80x20(
    tmp_path: Path,
) -> None:
    """With no lever chosen, `1 removed` is the whole summary: one status row,
    so the table keeps its rows (21-UAT test 1 (c))."""
    tool = load_tools(REGISTRY)[5]
    service = frozen_service(tmp_path)
    service.publish([removable_state(tool, [tmp_path / "bin" / tool.id])])
    app = _app(tmp_path, service, remove=lambda _decision: SweepResult(removed=(tool.id,)))
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "uninstall")
        await settle(app, pilot)
        service.queued = (absent_state(tool),)
        table = screen.query_one(DataTable[Any])
        table.move_cursor(row=table.get_row_index(tool.id))
        await pilot.press("space", "enter", "enter")
        await settle(app, pilot)
        status = app.view("uninstall").status
        assert status.text == "1 removed"
        assert rows_of(screen, status) == {18}


async def test_policies_chrome_at_80x20(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "policies")
        _assert_chrome(screen)
        for selector in ("#link-mode-line", "#policy-detail"):
            assert rows_of(screen, screen.query_one(selector)), selector
        assert rows_of(screen, screen.query_one(DataTable[Any]))


async def test_schedules_chrome_at_80x20(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "schedules")
        _assert_chrome(screen)
        # Note, the header row and seven schedule rows, then the detail panel down to the status.
        assert rows_of(screen, screen.query_one("#schedule-note")) == {3}
        assert rows_of(screen, screen.query_one(DataTable[Any])) == set(range(4, 12))
        assert rows_of(screen, screen.query_one("#schedule-detail")) == set(range(12, 18))
        assert rows_of(screen, app.view("schedules").status) == {18}


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


async def test_the_longest_refusal_fits_80_columns(tmp_path: Path) -> None:
    tool = load_tools(REGISTRY)[0]
    service = frozen_service(tmp_path)
    service.publish([removable_state(tool, [tmp_path / "bin"])])
    app = _app(tmp_path, service)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "uninstall")
        app.begin_mutation(MutationHolder.GLOBALS_REINSTALL)
        await pilot.press("space", "enter", "enter")
        await pilot.pause()
        status = app.view("uninstall").status
        assert status.text.startswith("A pnpm reinstall is running")
        assert cell_len(status.text) <= 78
        assert len(rows_of(screen, status)) == 1
        assert rows_of(screen, screen.query_one(FooterBar)) == {19}


async def test_a_drifted_policies_table_fits_80x20(tmp_path: Path) -> None:
    def result() -> PolicyResult:
        return PolicyResult(layers=(), reload_hint=None, warning=None)

    drifted = [
        Policy(
            id=f"drift{n}",
            label=f"a long policy label number {n}",
            description="a description long enough to need the Effect column budget",
            active=False,
            apply=result,
            remove=result,
            is_active=lambda: False,
            owned=lambda: True,
        )
        for n in range(3)
    ]
    app = _app(tmp_path, policies=drifted)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "policies")
        await pilot.pause()
        table = screen.query_one(DataTable[Any])
        assert {table.get_cell(p.id, "state").plain for p in drifted} == {"! [drift]"}
        spans = _column_spans(table)
        # The drift label is the widest State cell; State and Policy stay on screen.
        assert spans["State"][1] <= 78, spans
        assert spans["Policy"][1] <= 78, spans


async def test_the_toggle_fits_80x20(tmp_path: Path) -> None:
    """22-10: a flagged row keeps the chrome, its `[c]` and the config clause on screen."""
    gh = next(tool for tool in load_tools(REGISTRY) if tool.id == "gh")
    config = tuple(Path(entry).expanduser() for entry in gh.config_paths)
    service = frozen_service(tmp_path)
    service.publish([plan_state(gh, removable=RemovalPlan((tmp_path / "gh",), (), config=config))])
    app = _app(tmp_path, service)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "uninstall")
        await pilot.press("c")
        await pilot.pause()
        _assert_chrome(screen)
        table = screen.query_one(DataTable[Any])
        assert table.get_cell("gh", "sel").plain == "[c]"
        assert table.get_cell("gh", "removes").plain.startswith("config + ")
        uninstall = app.view("uninstall")
        assert isinstance(uninstall, UninstallScreen)
        assert len(rows_of(screen, screen.query_one("#browser-detail"))) == 3
        lines = list(Text(uninstall.detail_text).wrap(Console(width=78), 78))
        assert all(cell_len(line.plain) <= 78 for line in lines), lines
        # The proof sentence and the config clause land on the first two rows of the bar.
        head = " ".join(" ".join(line.plain.split()) for line in lines[:2])
        assert LAYOUT_PROOF_NOTE in head
        assert "config deleted too: ~/.config/gh (c keeps it)" in head


def _node_tool(tool_id: str, npm_pkg: str, *co_install: str) -> Tool:
    method = Method(kind="node", params={"npm_pkg": npm_pkg, "co_install": list(co_install)})
    return Tool(
        id=tool_id,
        name=tool_id,
        category="dev",
        cmd=tool_id,
        methods=(method,),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
    )


def _node_state(tool: Tool, npm_pkg: str) -> ToolState:
    argv = ("pnpm", "remove", "--global", npm_pkg)
    removable = RemovalPlan((Path(f"/opt/{tool.id}"),), (), level="manager", argv=argv)
    return plan_state(tool, removable=removable)


async def test_a_long_review_scrolls_and_keeps_its_keys_line(tmp_path: Path) -> None:
    """22-11 (UI-SPEC overflow backstop): 12 config paths and 2 pnpm warnings fit at 80x20."""
    paths = tuple(f"~/.config/review-{n:02d}" for n in range(12))
    gh = Tool(
        id="gh",
        name="gh",
        category="dev",
        cmd="gh",
        methods=(Method(kind="brew", params={"formula": "gh"}),),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
        config_paths=paths,
    )
    gh_removable = RemovalPlan(
        (tmp_path / "gh",),
        (),
        level="manager",
        argv=("brew", "uninstall", "gh"),
        config=tuple(Path(entry).expanduser() for entry in paths),
    )
    mmdc = _node_tool("mmdc", "@mermaid-js/mermaid-cli", "puppeteer")
    tsx = _node_tool("tsx", "tsx", "esbuild")
    service = frozen_service(tmp_path)
    service.publish(
        [
            plan_state(gh, removable=gh_removable),
            _node_state(mmdc, "@mermaid-js/mermaid-cli"),
            _node_state(tsx, "tsx"),
        ]
    )
    app = UnifiedApp(
        [gh, mmdc, tsx],
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            ban_names=list, has_path_block=lambda: False, remove=lambda _d: SweepResult()
        ),
        policies=PolicyInputs(policies=[], link_mode=lambda: "symlink"),
        version_refresh=service,
    )
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "uninstall")
        table = screen.query_one(DataTable[Any])
        for tool_id, key in (("gh", "c"), ("mmdc", "space"), ("tsx", "space")):
            table.move_cursor(row=table.get_row_index(tool_id))
            await pilot.pause()
            await pilot.press(key)
        await pilot.press("enter")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ConfirmUninstall)
        review = [line.plain for line in modal.review]
        for path in paths:  # every path appears whole in the body
            assert any(f"  {path} (gh)" in line for line in review), path
        assert sum(line.startswith("Warning:") for line in review) == 2
        mmdc_warning = next(line for line in review if line.startswith("Warning: pnpm group mmdc"))
        assert "\n  " in mmdc_warning  # folded with the 2-cell hanging indent, not cut
        box = modal.query_one("#confirm-box")
        assert box.region.width == 60
        assert box.region.height <= 18
        keys = modal.query_one("#confirm-keys")
        assert rows_of(modal, keys)
        assert max(rows_of(modal, keys)) < box.region.y + box.region.height - 1  # inside the border
        body = modal.query_one("#confirm-body", VerticalScroll)
        assert body.max_scroll_y > 0
        for _ in range(12):  # pgdn reaches the end of the body
            if body.scroll_y >= body.max_scroll_y:
                break
            await pilot.press("pagedown")
            await pilot.pause()
        assert body.scroll_y == body.max_scroll_y
        assert rows_of(modal, keys)  # the keys line stays on screen after scrolling
        await pilot.press("escape")
        await pilot.pause()


def _new_policy_rows(home: Path) -> list[Policy]:
    """The one Phase 23 row Policies still keeps (SPEC R7): the desktop SHELL row. The older rows
    (helper bundles, daemon, Bun redirect) have longer details that were never laid out here."""
    # Construction only reads the conf; nothing is written until a toggle.
    return [
        desktop_shell_policy(
            zsh_path="/home/linuxbrew/.linuxbrew/bin/zsh",
            conf_dir=home / ".config" / "environment.d",
            home=home,
        )
    ]


async def test_policies_fit_80x20_with_the_new_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("HOME", str(tmp_path))  # so display_path shows ~/… as on a real host
    rows = _new_policy_rows(tmp_path)
    app = _app(tmp_path, policies=rows)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "policies")
        assert isinstance(screen, PoliciesScreen)
        _assert_chrome(screen)
        table = screen.query_one(DataTable[Any])
        assert rows_of(screen, table)
        spans = _column_spans(table)
        assert spans["State"][1] - spans["State"][0] <= 9, spans
        assert spans["Policy"][1] <= 78, spans
        assert all(cell_len(row.label) <= 28 for row in rows), [row.label for row in rows]
        detail = screen.query_one("#policy-detail")
        assert detail.size.height == 11  # the panel height the Policies screen declares
        for index, row in enumerate(rows):
            if index:
                await pilot.press("down")
                await pilot.pause()
            lines = list(Text(screen.detail_text).wrap(Console(width=78), 78))
            assert len(lines) <= 9, (row.id, [line.plain for line in lines])
            assert all(cell_len(line.plain) <= 78 for line in lines), row.id
        _assert_chrome(screen)


async def test_uninstall_review_fits_80x20(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A21/A24/A25 backstop at 80x20 under NO_COLOR: the 92-cell undo line folds with the
    hanging indent and nothing is cut, block 3b fits the modal, and the removal status wraps."""
    from installer.agent_settings import apply_setting
    from installer.app import HOST_SETTINGS_OS

    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    apply_setting("claude", "auto-approve", home=tmp_path, platform_os=HOST_SETTINGS_OS)
    codegraph = Tool(
        id="codegraph",
        name="codegraph",
        category="dev",
        cmd="codegraph",
        methods=(Method(kind="brew", params={"formula": "codegraph"}),),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
    )
    undo = (
        str(tmp_path / ".local" / "bin" / "codegraph"),
        "uninstall",
        "--target",
        "claude,codex",
        "--location",
        "global",
        "--yes",
        "--keep-cli",
    )
    removable = RemovalPlan(
        (tmp_path / "opt" / "codegraph",), (), unregister=(undo,), hook_hosts=("claude", "codex")
    )
    service = frozen_service(tmp_path)
    service.publish([plan_state(codegraph, removable=removable)])
    result = SweepResult(removed=("codegraph",), settings_kept=("claude", "codex"))
    app = UnifiedApp(
        [codegraph],
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            ban_names=list, has_path_block=lambda: False, remove=lambda _decision: result
        ),
        policies=PolicyInputs(policies=[], link_mode=lambda: "symlink"),
        version_refresh=service,
    )
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await _open(app, pilot, "uninstall")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ConfirmUninstall)
        assert modal.review[0].plain.startswith("codegraph: runs codegraph uninstall")
        assert "\n  " in modal.review[0].plain  # folded with the 2-cell hanging indent
        assert " ".join(modal.review[0].plain.split()).endswith("--yes --keep-cli")
        assert modal.query_one("#confirm-box").region.width == 60
        await pilot.press("enter")  # confirm: the removal runs against the stub
        await settle(app, pilot)
        assert isinstance(screen, UninstallScreen)
        status = screen.status.text
        assert "Kept settings you changed since this installer wrote them: claude, codex." in status
        assert screen.query_one(DataTable[Any]).region.height > 0
