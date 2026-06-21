"""Characterization tests for the reusable `ToolBrowser` widget in isolation.

The widget is mounted in a tiny host App with a hand-rolled adapter (no catalog
data model), so these tests pin the widget's own contract: groupings render,
marks toggle in place, the detail bar follows the highlight, enter returns ids
in order, and section rows are inert to selection. The catalog's concrete
behavior stays pinned by tests/test_catalog_tui.py.
"""

import html
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Static
from textual.widgets.data_table import ColumnKey

from installer.tool_browser import BrowserAdapter, Section, ToolBrowser


@dataclass(frozen=True)
class _Item:
    id: str
    group: str
    desc: str


_ITEMS = [
    _Item("alpha", "letters", "the first item"),
    _Item("beta", "letters", "the second item"),
    _Item("one", "numbers", "a numeric item"),
]

_COLUMNS = (("Sel", "sel"), ("Id", "id"), ("Desc", "desc"))


def _sections_by_group(items: list[_Item]) -> list[Section[_Item]]:
    groups = sorted({item.group for item in items})
    return [
        (group, f"group: {group}", [item for item in items if item.group == group])
        for group in groups
    ]


def _flat(items: list[_Item]) -> list[Section[_Item]]:
    return [("", "", list(items))]


class _Host(App[None]):
    def __init__(self, adapter: BrowserAdapter[_Item]) -> None:
        super().__init__()
        self._adapter = adapter
        self.accepted: list[str] | None = None

    def compose(self) -> ComposeResult:
        yield ToolBrowser(self._adapter)

    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        self.accepted = event.ids


def _adapter(
    *,
    items: list[_Item] | None = None,
    two_views: bool = False,
    sortable: bool = False,
    legend: str | None = None,
    selectable: "Callable[[_Item], bool] | None" = None,
) -> BrowserAdapter[_Item]:
    data = _ITEMS if items is None else items
    sort_state = {"last": ""}

    views: tuple[tuple[str, str], ...] = (("group", "By group"),)
    if two_views:
        views = (("group", "By group"), ("flat", "Flat"))

    def grouper(view: str) -> list[Section[_Item]]:
        if view == "flat":
            return _flat(data)
        return _sections_by_group(data)

    adapter = BrowserAdapter(
        items=data,
        columns=_COLUMNS,
        item_id=lambda item: item.id,
        row_cells=lambda item: [
            Text("[ ]"),
            Text(item.id, style="bold"),
            Text(item.desc, style="dim"),
        ],
        detail_text=lambda item: f"{item.id} — {item.desc}",
        groups=grouper,
        views=views,
        legend=legend,
        detail_is_markup=False,
        on_sort=lambda key: sort_state.__setitem__("last", key) if sortable else None,
        sortable_in_views=frozenset({"flat"}) if sortable else frozenset[str](),
    )
    if selectable is not None:
        object.__setattr__(adapter, "selectable", selectable)
    return adapter


def _screen_text(app: _Host) -> str:
    return html.unescape(app.export_screenshot()).replace("\xa0", " ")


async def test_renders_section_rows_and_items() -> None:
    app = _Host(_adapter())
    async with app.run_test(size=(80, 20)):
        table = app.query_one(DataTable[Any])
        # 2 sections (letters, numbers) + 3 item rows
        assert table.row_count == 5


async def test_cursor_starts_on_first_item_not_a_section() -> None:
    app = _Host(_adapter())
    async with app.run_test(size=(80, 20)) as pilot:
        # rows: [#letters, alpha, beta, #numbers, one]; first selectable is alpha
        await pilot.press("space")
        browser = app.query_one(ToolBrowser[_Item])
        assert browser.selected == {"alpha"}


async def test_space_toggles_mark_in_place() -> None:
    app = _Host(_adapter())
    async with app.run_test(size=(80, 20)) as pilot:
        browser = app.query_one(ToolBrowser[_Item])
        table = app.query_one(DataTable[Any])
        await pilot.press("space")
        assert table.get_cell("alpha", "sel").plain == "[x]"
        await pilot.press("space")
        assert browser.selected == set()
        assert table.get_cell("alpha", "sel").plain == "[ ]"


async def test_space_ignores_section_rows() -> None:
    app = _Host(_adapter())
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("up")  # from alpha onto the "letters" section row
        await pilot.press("space")
        browser = app.query_one(ToolBrowser[_Item])
        assert browser.selected == set()


async def test_detail_bar_follows_highlight_and_section_rows() -> None:
    app = _Host(_adapter())
    async with app.run_test(size=(80, 20)) as pilot:
        browser = app.query_one(ToolBrowser[_Item])
        assert browser.detail_text == "alpha — the first item"
        await pilot.press("up")  # onto the "letters" section row
        assert browser.detail_text == "group: letters"


async def test_select_all_and_invert_preserve_cursor() -> None:
    app = _Host(_adapter())
    async with app.run_test(size=(80, 20)) as pilot:
        browser = app.query_one(ToolBrowser[_Item])
        await pilot.press("a")
        assert browser.selected == {"alpha", "beta", "one"}
        assert app.query_one(DataTable[Any]).cursor_row == 1  # still on alpha
        await pilot.press("i")
        assert browser.selected == set()


async def test_enter_posts_accepted_with_ids_in_item_order() -> None:
    app = _Host(_adapter())
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("a", "enter")
        await pilot.pause()
        assert app.accepted == ["alpha", "beta", "one"]


async def test_enter_with_empty_selection_posts_empty_ids() -> None:
    app = _Host(_adapter())
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert app.accepted == []


async def test_arrow_keys_cycle_views_and_wrap() -> None:
    app = _Host(_adapter(two_views=True))
    async with app.run_test(size=(80, 20)) as pilot:
        browser = app.query_one(ToolBrowser[_Item])
        assert browser.view == "group"
        await pilot.press("right")
        assert browser.view == "flat"
        await pilot.press("right")  # wraps back to the first view
        assert browser.view == "group"


async def test_flat_view_has_no_section_rows() -> None:
    app = _Host(_adapter(two_views=True))
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("right")  # -> flat view
        table = app.query_one(DataTable[Any])
        assert table.row_count == 3  # just the items, no section headers


async def test_header_click_sorts_only_in_sortable_views() -> None:
    sort_log: list[str] = []
    adapter = _adapter(two_views=True, sortable=True)
    # observe the sort callback fired only inside the sortable view
    object.__setattr__(adapter, "on_sort", sort_log.append)
    app = _Host(adapter)
    async with app.run_test(size=(80, 20)) as pilot:
        browser = app.query_one(ToolBrowser[_Item])
        table = app.query_one(DataTable[Any])
        # grouped (non-sortable) view: header click is ignored.
        browser.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("id"), 1, Text("Id"))
        )
        assert sort_log == []
        await pilot.press("right")  # -> flat (sortable) view
        browser.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("id"), 1, Text("Id"))
        )
        assert sort_log == ["id"]


async def test_header_click_ignored_when_no_sort_callback() -> None:
    # A view may be marked sortable while the adapter supplies no on_sort
    # callback: the header click must be a safe no-op, not a crash.
    adapter = _adapter(two_views=True, sortable=True)
    object.__setattr__(adapter, "on_sort", None)
    app = _Host(adapter)
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("right")  # -> flat (sortable) view
        browser = app.query_one(ToolBrowser[_Item])
        table = app.query_one(DataTable[Any])
        browser.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("id"), 1, Text("Id"))
        )
        assert browser.view == "flat"  # no crash, no rebuild side effect


async def test_legend_renders_when_supplied() -> None:
    app = _Host(_adapter(legend="[bold]LEGEND-MARKER[/]"))
    async with app.run_test(size=(80, 20)):
        legend = app.query_one("#browser-legend", Static)
        painted = "".join(segment.text for segment in legend.render_line(0))
        assert "LEGEND-MARKER" in painted


async def test_no_legend_widget_when_absent() -> None:
    app = _Host(_adapter(legend=None))
    async with app.run_test(size=(80, 20)):
        assert len(app.query("#browser-legend")) == 0


async def test_empty_items_no_crash_on_toggle_and_accept() -> None:
    app = _Host(_adapter(items=[]))
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("space")  # nothing highlighted -> no-op
        await pilot.press("enter")
        await pilot.pause()
        assert app.accepted == []
        browser = app.query_one(ToolBrowser[_Item])
        assert browser.selected == set()


async def test_space_is_inert_on_non_selectable_row() -> None:
    # alpha is non-selectable: a space on it must not enter the selection.
    app = _Host(_adapter(selectable=lambda item: item.id != "alpha"))
    async with app.run_test(size=(80, 20)) as pilot:
        browser = app.query_one(ToolBrowser[_Item])
        await pilot.press("space")  # cursor on alpha (non-selectable)
        assert browser.selected == set()
        await pilot.press("down")  # onto beta (selectable)
        await pilot.press("space")
        assert browser.selected == {"beta"}


async def test_select_all_skips_non_selectable_rows() -> None:
    app = _Host(_adapter(selectable=lambda item: item.id != "alpha"))
    async with app.run_test(size=(80, 20)) as pilot:
        browser = app.query_one(ToolBrowser[_Item])
        await pilot.press("a")
        assert browser.selected == {"beta", "one"}  # alpha never enters


async def test_invert_skips_non_selectable_rows() -> None:
    app = _Host(_adapter(selectable=lambda item: item.id != "alpha"))
    async with app.run_test(size=(80, 20)) as pilot:
        browser = app.query_one(ToolBrowser[_Item])
        await pilot.press("down")  # onto beta
        await pilot.press("space")  # select beta
        assert browser.selected == {"beta"}
        await pilot.press("i")  # invert over selectable only: beta drops, one enters
        assert browser.selected == {"one"}


async def test_refresh_marks_leaves_non_selectable_cell_untouched() -> None:
    # alpha's row_cells render a distinctive sel cell; _refresh_marks (run on
    # select-all) must not overwrite it, since alpha is non-selectable.
    def cells(item: _Item) -> list[Text]:
        sel = Text("---") if item.id == "alpha" else Text("[ ]")
        return [sel, Text(item.id, style="bold"), Text(item.desc, style="dim")]

    adapter = _adapter(selectable=lambda item: item.id != "alpha")
    object.__setattr__(adapter, "row_cells", cells)
    app = _Host(adapter)
    async with app.run_test(size=(80, 20)) as pilot:
        table = app.query_one(DataTable[Any])
        await pilot.press("a")  # select-all triggers _refresh_marks
        assert table.get_cell("alpha", "sel").plain == "---"  # untouched
        assert table.get_cell("beta", "sel").plain == "[x]"  # marked


async def test_view_switch_repaints_cells_at_full_width() -> None:
    # Regression analog: after clear(columns=True) + re-add, the rebuilt table
    # must paint full-width cells (the long desc must be visible), not stale
    # header-width caches.
    wide = [_Item("alpha", "letters", "a very long description that needs full column width here")]
    app = _Host(_adapter(items=wide, two_views=True))
    async with app.run_test(size=(120, 20)) as pilot:
        await pilot.press("right")  # group -> flat rebuilds the table
        assert "a very long description that needs full column width here" in _screen_text(app)


async def test_refresh_marks_tolerates_a_cleared_table() -> None:
    """Regression: _refresh_marks is scheduled via call_after_refresh; under the
    real Textual driver a second _rebuild (the single-tab activation / a resize)
    clears the table before the pending callback fires. It must not raise
    CellDoesNotExist — this crashed the real Uninstall view on `make setup`."""
    app = _Host(_adapter())
    async with app.run_test():
        browser = app.query_one(ToolBrowser[_Item])
        table = browser.query_one(DataTable[Any])
        table.clear(columns=True)  # the transient state between a rebuild's clear and re-add
        # getattr: invoke the internal flush dynamically (the production trigger is
        # an internal call_after_refresh; this pins the same callback's robustness).
        refresh_marks: object = getattr(browser, "_refresh_marks")  # noqa: B009
        assert callable(refresh_marks)
        refresh_marks()  # must not raise CellDoesNotExist


async def test_select_all_marks_all_rows_via_flush() -> None:
    """select-all routes through the same mark flush; every present row is stamped
    [x] (exercises the flush's normal path: it re-stamps the rows that exist)."""
    app = _Host(_adapter())
    async with app.run_test() as pilot:
        await pilot.press("a")  # select all -> _refresh_marks over the live rows
        table = app.query_one(ToolBrowser[_Item]).query_one(DataTable[Any])
        assert table.get_cell("alpha", "sel").plain == "[x]"
        assert table.get_cell("one", "sel").plain == "[x]"


async def test_section_header_shows_member_count() -> None:
    """Section rows carry their member count, a guide when narrow columns squeeze
    the rows (e.g. `── letters (2) `)."""
    app = _Host(_adapter())
    async with app.run_test():
        table = app.query_one(ToolBrowser[_Item]).query_one(DataTable[Any])
        section = table.get_cell("#letters", "sel").plain
        assert "letters" in section and "(2)" in section
