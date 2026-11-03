"""Screen-family lifecycle pilots: launch, the one show_view order, status lifecycle."""

from collections.abc import Callable
from typing import Any

import pytest
from textual.widgets import DataTable

from installer.doctor import DoctorReport
from installer.model import Method, Tool
from installer.ui_common import AppScreen
from installer.uninstall import SweepResult, ToolRow
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs

VIEW_NAMES = ["system", "user", "ai", "doctor", "uninstall", "policies"]


def _tool(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
    )


def _family_app(
    *,
    rows: Callable[[], list[ToolRow]] = list,
    initial_view: str = "system",
    startup_warning: str | None = None,
) -> UnifiedApp:
    return UnifiedApp(
        [_tool("rg"), _tool("fd")],
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({"pip": False, "npm": False}, None),
        fix_preview="preview",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=rows,
            ban_names=lambda: [],
            has_path_block=lambda: False,
            remove=lambda _decision: SweepResult(),
            tweak_ids=lambda: (),
        ),
        policies=PolicyInputs(policies=[]),
        initial_view=initial_view,
        startup_warning=startup_warning,
    )


def _view(app: UnifiedApp, name: str) -> AppScreen:
    return app.view(name)


def _spy(app: UnifiedApp, leaving: AppScreen, target: AppScreen) -> list[str]:
    events: list[str] = []

    def sync(obj: object, attr: str, tag: str) -> None:
        original: Callable[..., Any] = getattr(obj, attr)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            events.append(tag)
            return original(*args, **kwargs)

        setattr(obj, attr, wrapper)

    def asynchronous(obj: object, attr: str, tag: str) -> None:
        original: Callable[..., Any] = getattr(obj, attr)

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            events.append(tag)
            return await original(*args, **kwargs)

        setattr(obj, attr, wrapper)

    sync(leaving, "clear_transient", "clear")
    asynchronous(app, "pop_screen", "pop")
    asynchronous(app, "push_screen", "push")
    sync(target, "enter_view", "enter")
    return events


async def test_launch_shows_the_system_tier_through_show_view():
    app = _family_app()
    async with app.run_test(size=(100, 30)):
        assert app.screen is app.catalog
        assert len(app.screen_stack) == 2
        assert not isinstance(app.screen_stack[0], AppScreen)
        assert app.current_view == "system"


@pytest.mark.parametrize("name", VIEW_NAMES)
async def test_show_view_call_order(name: str):
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        start = "user" if name == "system" else "system"
        await app.show_view(start)
        await pilot.pause()
        events = _spy(app, _view(app, start), _view(app, name))
        await app.show_view(name)
        assert events == ["clear", "pop", "push", "enter"]


async def test_current_view_key_is_a_no_op():
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("down", "space")
        app.catalog.status.set("kept", "ok")
        row = app.screen.query_one(DataTable[Any]).cursor_row
        selected = set(app.catalog.selected)
        events = _spy(app, app.catalog, app.catalog)
        await pilot.press("1")
        assert events == []
        assert app.screen.query_one(DataTable[Any]).cursor_row == row
        assert set(app.catalog.selected) == selected
        assert app.catalog.status.text == "kept"


async def test_nav_burst_with_escape_keeps_depth_two():
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4", "5", "escape", "6", "1", "escape")
        assert len(app.screen_stack) == 2
        assert app.current_view == "system"
        await pilot.press("5")
        assert app.current_view == "uninstall"
        assert len(app.screen_stack) == 2


@pytest.mark.parametrize("name", VIEW_NAMES)
async def test_entry_status_survives_first_entry_and_leave_clears_it(
    name: str, monkeypatch: pytest.MonkeyPatch
):
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        target = _view(app, name)
        if name == app.current_view:
            await app.show_view("doctor")
        original = target.enter_view

        def entering() -> None:
            original()
            target.status.set("entry", "warn")

        with monkeypatch.context() as patch:
            patch.setattr(target, "enter_view", entering)
            await app.show_view(name)
            await pilot.pause()
            assert target.status.text == "entry"
            await app.show_view("doctor" if name != "doctor" else "system")
            assert target.status.text == ""
        await app.show_view(name)
        await pilot.pause()
        assert target.status.text != "entry"


async def test_leaving_a_view_with_no_status_is_a_no_op():
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.catalog.status.text == ""
        await app.show_view("doctor")
        await pilot.pause()
        assert app.catalog.status.text == ""
        assert app.catalog.status.severity is None


async def test_uninstall_startup_read_error_stays_visible_on_first_entry():
    calls: list[int] = []

    def rows() -> list[ToolRow]:
        calls.append(1)
        if len(calls) == 1:
            raise OSError("boom")
        return []

    app = _family_app(rows=rows, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        status = _view(app, "uninstall").status
        assert status.text.startswith("Could not read the uninstall state at startup:")
        assert status.severity == "warn"


async def test_flushed_warning_is_not_replaced_by_the_standing_status():
    app = _family_app(initial_view="uninstall", startup_warning="w")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        status = _view(app, "uninstall").status
        assert status.text == "w"
        await app.show_view("system")
        await app.show_view("uninstall")
        await pilot.pause()
        assert status.text == "Nothing to uninstall."
