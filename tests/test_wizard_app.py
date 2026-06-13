from collections.abc import Callable, Mapping
from pathlib import Path

from textual.widgets import Label

from installer.doctor import DoctorReport
from installer.model import Method, Tool
from installer.wizard_app import (
    VIEW_ORDER,
    DoctorScreen,
    FixScreen,
    NavScreen,
    PlaceholderScreen,
    UnifiedApp,
)


def _tool(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority="P1",
        audience="both",
        desc="",
    )


def _app(
    *,
    report: DoctorReport | None = None,
    guard_status: dict[str, bool] | None = None,
    guard_warning: str | None = None,
    fix_preview: str = "Will wire ~/.local/bin into ~/.zshrc",
    fix: Callable[[], None] = lambda: None,
    initial_view: str = "catalog",
) -> UnifiedApp:
    tools = [_tool("rg"), _tool("fd")]
    installed: Mapping[str, bool] = {"rg": True, "fd": False}
    return UnifiedApp(
        tools,
        installed,
        {"search": "find things"},
        report=report or DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status or {"pip": False, "npm": False},
        guard_warning=guard_warning,
        fix_preview=fix_preview,
        fix=fix,
        initial_view=initial_view,
    )


def test_default_palette_is_disabled() -> None:
    assert UnifiedApp.ENABLE_COMMAND_PALETTE is False


def test_view_order_lists_every_view() -> None:
    assert VIEW_ORDER == ("catalog", "doctor", "fix", "uninstall", "policies")


async def test_starts_on_the_catalog_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "catalog"


async def test_number_key_navigates_to_each_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert app.current_view == "doctor"
        assert isinstance(app.screen, DoctorScreen)
        await pilot.press("3")
        assert app.current_view == "fix"
        await pilot.press("4")
        assert app.current_view == "uninstall"
        await pilot.press("5")
        assert app.current_view == "policies"
        await pilot.press("1")
        assert app.current_view == "catalog"


async def test_doctor_screen_renders_guidance() -> None:
    app = _app(report=DoctorReport(missing=(Path("/a/bin"),), broken=(), duplicated=()))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert isinstance(app.screen, DoctorScreen)
        text = "".join(g.title + g.meaning + g.next_step for g in app.screen.guidance)
        assert "/a/bin" in text
        assert "make fix" in text


async def test_fix_screen_previews_then_applies_live() -> None:
    applied: list[str] = []
    app = _app(fix_preview="Will wire ~/.local/bin", fix=lambda: applied.append("ran"))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")  # fix view
        assert isinstance(app.screen, FixScreen)
        assert app.screen.applied is False
        assert applied == []  # nothing applied just by viewing
        await pilot.press("a")  # Apply
        assert applied == ["ran"]
        assert app.screen.applied is True


async def test_fix_screen_apply_is_idempotent() -> None:
    applied: list[str] = []
    app = _app(fix=lambda: applied.append("ran"))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.press("a")
        await pilot.press("a")  # second press is inert once applied
        assert applied == ["ran"]


async def test_initial_view_opens_on_that_view() -> None:
    app = _app(initial_view="doctor")
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "doctor"
        assert isinstance(app.screen, DoctorScreen)


async def test_initial_view_fix_opens_on_fix() -> None:
    app = _app(initial_view="fix")
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "fix"
        assert isinstance(app.screen, FixScreen)


async def test_navigating_to_the_current_view_is_a_no_op() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("1")  # already on catalog
        assert app.current_view == "catalog"
        assert app.is_running


async def test_palette_and_key_resolve_to_the_same_view() -> None:
    # Direct key route.
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert app.current_view == "doctor"
    by_key = app.current_view
    # Palette route: open Ctrl+P, pick the "doctor" item.
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("down", "enter")  # first item is catalog; second is doctor
        assert app.current_view == "doctor"
    assert app.current_view == by_key


async def test_palette_escape_does_not_navigate() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("escape")
        assert app.current_view == "catalog"
        assert not isinstance(app.screen, NavScreen)


async def test_ctrl_c_aborts_from_a_placeholder_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")  # navigate onto the doctor placeholder
        assert app.current_view == "doctor"
        await pilot.press("ctrl+c")  # abort must work from any view
        assert not app.is_running
    assert app.return_value is None


async def test_number_keys_are_inert_while_the_palette_is_open() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        depth = len(app.screen_stack)
        await pilot.press("2")  # must NOT navigate underneath the modal
        assert isinstance(app.screen, NavScreen)
        assert app.current_view == "catalog"
        assert len(app.screen_stack) == depth  # no extra push


async def test_ctrl_p_does_not_stack_a_second_palette() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        depth = len(app.screen_stack)
        await pilot.press("ctrl+p")  # second press is inert
        assert isinstance(app.screen, NavScreen)
        assert len(app.screen_stack) == depth
        await pilot.press("escape")
        assert not isinstance(app.screen, NavScreen)


async def test_palette_from_placeholder_navigates_without_desync() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")  # -> doctor placeholder
        assert app.current_view == "doctor"
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        # ListView starts on catalog(0); step to uninstall(3): catalog,doctor,fix,uninstall
        await pilot.press("down", "down", "down", "enter")
        assert app.current_view == "uninstall"
        assert not isinstance(app.screen, NavScreen)
        assert isinstance(app.screen, PlaceholderScreen)
        # the SCREEN shown matches current_view (no desync)
        assert "Uninstall" in str(app.screen.query_one("#placeholder", Label).content)
