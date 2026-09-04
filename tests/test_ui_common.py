from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import DataTable

from installer.ui_common import (
    SEVERITY_STYLE,
    highlighted_key,
    mark,
    multiline_summary,
)


def test_severity_style_maps_each_level() -> None:
    assert SEVERITY_STYLE == {"ok": "green", "warn": "yellow", "error": "red"}


def test_mark_renders_checkbox_glyph_and_color() -> None:
    assert mark(True).plain == "[x]"
    assert mark(False).plain == "[ ]"
    assert "green" in str(mark(True).style)
    assert str(mark(False).style) in ("", "none")


def test_multiline_summary_joins_one_line_per_part() -> None:
    assert multiline_summary(["a", "b", "c"]) == "a\nb\nc"
    assert multiline_summary([]) == ""


def test_run_live_returns_result_or_oserror_message() -> None:
    from installer.ui_common import run_live

    assert run_live(lambda: 42) == (42, None)

    def boom() -> int:
        raise OSError("disk full")

    assert run_live(boom) == (None, "disk full")


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
    """The header numbers every view ([1]–[5]) and marks the active one accent-bold."""
    from installer.ui_common import WayfindingHeader

    class _Host(App[None]):
        def compose(self) -> ComposeResult:
            yield WayfindingHeader(active="doctor")

    app = _Host()
    async with app.run_test(size=(100, 5)):
        markup = app.query_one(WayfindingHeader).render_markup()
        assert "[bold $accent]\\[2] Doctor[/]" in markup
        assert "[bold $accent]\\[1] Catalog[/]" not in markup
        assert "[dim]\\[1] Catalog[/]" in markup


def test_wayfinding_header_numbers_each_view_in_order() -> None:
    from installer.ui_common import VIEWS, WayfindingHeader

    markup = WayfindingHeader(active="catalog").render_markup()
    for index, view in enumerate(VIEWS):
        # The bracket is escaped in the content markup so it renders literally.
        assert f"\\[{index + 1}] {view.label}" in markup


async def test_app_screen_yields_header_status_and_footer() -> None:
    """A subclass implements compose_body only; the scaffold guarantees header
    + Rule divider + status line + footer so chrome can never be omitted again."""
    from textual.widgets import Rule, Static

    from installer.ui_common import AppScreen, FooterBar, ModeBadge, StatusLine, WayfindingHeader

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
        assert len(screen.query(Rule)) == 1
        assert len(screen.query(ModeBadge)) == 1
        assert len(screen.query(StatusLine)) == 1
        assert len(screen.query(FooterBar)) == 1
        assert len(screen.query("#demo-body")) == 1


def test_view_registry_is_complete_and_consistent() -> None:
    """Every view row carries every chrome fact; VIEW_ORDER and the name lookup
    derive from the same table, so they can never drift apart."""
    from installer.ui_common import VIEW_BY_NAME, VIEW_ORDER, VIEWS

    assert VIEW_ORDER == ("catalog", "doctor", "fix", "uninstall", "policies")
    assert set(VIEW_BY_NAME) == set(VIEW_ORDER)
    for view in VIEWS:
        assert view.label and view.palette and view.mode and view.glyph and view.hint
        assert view.actions  # Doctor included: read-only is an explicit token


def test_footer_bar_shows_actions_then_global_nav() -> None:
    from installer.ui_common import FooterBar

    text = FooterBar("catalog").render_text().plain
    assert "space toggle" in text and "enter install" in text
    assert "│" in text  # zone separator
    assert "1–5 views" in text and "^p nav" in text and "q quit" in text
    # the action zone is left of the separator; global nav is right of it
    assert text.index("space toggle") < text.index("│") < text.index("1–5 views")


def test_footer_bar_doctor_reads_as_read_only() -> None:
    from installer.ui_common import FooterBar

    text = FooterBar("doctor").render_text().plain
    assert "(read-only)" in text
    assert text.index("(read-only)") < text.index("│")


def test_mode_badge_renders_label_glyph_and_hint() -> None:
    from installer.ui_common import VIEW_BY_NAME, ModeBadge

    badge = ModeBadge(VIEW_BY_NAME["policies"])
    text = badge.render_text()
    assert "◆" in text.plain
    assert "[LIVE]" in text.plain
    assert "space toggles a policy and applies it now" in text.plain


def test_mode_badge_staged_and_readonly_strings() -> None:
    from installer.ui_common import VIEW_BY_NAME, ModeBadge

    catalog_badge = ModeBadge(VIEW_BY_NAME["catalog"])
    assert "[STAGED]" in catalog_badge.render_text().plain
    assert "◇" in catalog_badge.render_text().plain
    uninstall = ModeBadge(VIEW_BY_NAME["uninstall"]).render_text().plain
    assert "[STAGED · DESTRUCTIVE]" in uninstall
    assert "◇" in uninstall  # staged stays hollow; danger is carried by the words + red
    assert "[READ-ONLY]" in ModeBadge(VIEW_BY_NAME["doctor"]).render_text().plain
