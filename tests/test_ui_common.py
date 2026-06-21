from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import DataTable

from installer.ui_common import (
    SEVERITY_STYLE,
    highlighted_key,
    mark,
    multiline_summary,
    severity_style,
)


def test_severity_style_maps_each_level() -> None:
    assert severity_style("ok") == "green"
    assert severity_style("warn") == "yellow"
    assert severity_style("error") == "red"
    assert set(SEVERITY_STYLE) == {"ok", "warn", "error"}


def test_mark_renders_checkbox_glyph_and_color() -> None:
    assert mark(True).plain == "[x]"
    assert mark(False).plain == "[ ]"
    assert "green" in str(mark(True).style)
    assert str(mark(False).style) in ("", "none")


def test_multiline_summary_joins_one_line_per_part() -> None:
    assert multiline_summary(["a", "b", "c"]) == "a\nb\nc"
    assert multiline_summary([]) == ""


class _TableHost(App[None]):
    def compose(self) -> ComposeResult:
        yield DataTable[Any]()


async def test_highlighted_key_returns_row_under_cursor() -> None:
    app = _TableHost()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable[Any])
        table.add_column("c", key="c")
        table.add_row("one", key="row-a")
        table.add_row("two", key="row-b")
        table.move_cursor(row=1)
        await pilot.pause()
        assert highlighted_key(table) == "row-b"


async def test_highlighted_key_is_none_on_empty_table() -> None:
    app = _TableHost()
    async with app.run_test():
        table = app.query_one(DataTable[Any])
        table.add_column("c", key="c")
        assert highlighted_key(table) is None


async def test_status_line_set_and_clear() -> None:
    """StatusLine.set stores the text + severity style; clear empties it. The
    default color is neutral (NOT $warning) — every call passes an explicit
    severity, so a warning-yellow default would mislabel success/error."""
    from installer.ui_common import StatusLine

    class _Host(App[None]):
        def compose(self) -> ComposeResult:
            yield StatusLine()

    app = _Host()
    async with app.run_test():
        line = app.query_one(StatusLine)
        line.set("Removed 2 tools.", "ok")
        assert line.text == "Removed 2 tools."
        line.clear()
        assert line.text == ""


async def test_wayfinding_header_highlights_active_view() -> None:
    """The header lists every view and marks the active one so the user always
    knows where they are (Nielsen #1)."""
    from installer.ui_common import WayfindingHeader

    class _Host(App[None]):
        def compose(self) -> ComposeResult:
            yield WayfindingHeader(active="doctor")

    app = _Host()
    async with app.run_test(size=(100, 5)):
        header = app.query_one(WayfindingHeader)
        markup = header.render_markup()  # exactly what on_mount renders
        # every view is listed
        assert "Catalog" in markup and "Doctor" in markup and "Policies" in markup
        # the active view is accent-bold; the others are dim (the real marker)
        assert "[bold $accent]Doctor[/]" in markup
        assert "[bold $accent]Catalog[/]" not in markup
        assert "[dim]Catalog[/]" in markup


async def test_app_screen_yields_header_status_and_footer() -> None:
    """A subclass implements compose_body only; the scaffold guarantees header
    + status line + footer so chrome can never be omitted again."""
    from textual.widgets import Footer, Static

    from installer.ui_common import AppScreen, StatusLine, WayfindingHeader

    class _Demo(AppScreen):
        def __init__(self) -> None:
            super().__init__(view="doctor")

        def compose_body(self) -> ComposeResult:
            yield Static("body", id="demo-body")

    class _Host(App[None]):
        def on_mount(self) -> None:
            self.push_screen(_Demo())

    app = _Host()
    async with app.run_test(size=(100, 20)):
        screen = app.screen
        assert len(screen.query(WayfindingHeader)) == 1
        assert len(screen.query(StatusLine)) == 1
        assert len(screen.query(Footer)) == 1
        assert len(screen.query("#demo-body")) == 1
