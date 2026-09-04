"""Reusable browsable, selectable table widget extracted from the catalog.

`ToolBrowser` owns the grouping `Tabs`, the `DataTable`, the legend, the detail
bar, section rows, selection marks, cursor-on-first-selectable, view switching,
header-click sort, and the highlight->detail wiring. Everything data-specific is
supplied by a `BrowserAdapter`, so a future Uninstall view can reuse the widget
with its own columns, states, and grouping.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, TypeVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static, Tab, Tabs

from installer.ui_common import highlighted_key, mark

T = TypeVar("T")

# A grouped section: short title (cell-0 text), detail-bar line, members. An
# empty title means "no section row" (the flat table view emits a single such
# group). Members carry the items the adapter knows how to render.
Section = tuple[str, str, list[T]]


@dataclass(frozen=True)
class BrowserAdapter(Generic[T]):
    """The data-specific seam of a `ToolBrowser`.

    Parameterizes the catalog/uninstall differences: the columns, the optional
    legend, the items and their stable ids, how a row is rendered, what the
    detail bar says, the grouping per view, the navigable view names with their
    tab labels, and the column-header sort (a no-op tuple disables sorting).
    """

    items: list[T]
    columns: tuple[tuple[str, str], ...]
    item_id: Callable[[T], str]
    row_cells: Callable[[T], list[Text]]
    detail_text: Callable[[T], str]
    # (view name -> sections). The browser passes the active view; the adapter
    # returns the section list (short title, detail line, members).
    groups: Callable[[str], list[Section[T]]]
    # Navigable views as (name, tab label) in order. A single entry renders one
    # tab; the catalog uses five. Tab ids equal the view names.
    views: tuple[tuple[str, str], ...]
    legend: str | None = None
    section_detail_style: str = "bold"
    detail_is_markup: bool = True
    # column key -> a callback that re-groups; the browser calls it on a header
    # click and rebuilds. Absent keys (and non-table views) don't sort.
    on_sort: Callable[[str], None] | None = None
    sortable_in_views: frozenset[str] = field(default_factory=lambda: frozenset[str]())
    # Per-item selectability. The default is "everything selects" (the catalog);
    # the uninstall view marks managed/absent/unavailable rows non-selectable, so
    # space is inert on them and select-all/invert skip them. The browser also
    # leaves a non-selectable row's sel cell as the adapter rendered it.
    selectable: Callable[[T], bool] = field(default_factory=lambda: lambda _item: True)


class ToolBrowser(Widget, Generic[T]):
    """Grouped, selectable table. <-/-> (or the tabs) switch the grouping view;
    `space` toggles the highlighted item; `a`/`i` select-all/invert. Selection
    state, the current view, and the detail-bar text are public seams."""

    class Accepted(Message):
        """The user pressed enter: `ids` are the selected item ids in adapter
        order (possibly empty — the host decides what an empty accept means)."""

        def __init__(self, ids: list[str]) -> None:
            super().__init__()
            self.ids = ids

    class SelectionChanged(Message):
        """The selection set changed via toggle/select-all/invert. Hosts use it
        to clear a stale "select at least one" warning once the user acts."""

    DEFAULT_CSS = """
    ToolBrowser { layout: vertical; height: 1fr; }
    ToolBrowser Tabs { dock: top; }
    ToolBrowser #browser-detail { dock: bottom; height: 2; padding: 0 1; background: $surface; }
    ToolBrowser #browser-legend { dock: bottom; height: 1; padding: 0 1; }
    ToolBrowser DataTable { height: 1fr; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "prev_view", "prev view", priority=True),
        Binding("right", "next_view", "next view", priority=True),
        Binding("space", "toggle_selected", "toggle", priority=True),
        Binding("a", "select_all", "all"),
        Binding("i", "invert", "invert"),
        Binding("enter", "accept", "accept", priority=True),
    ]

    def __init__(self, adapter: BrowserAdapter[T]) -> None:
        super().__init__()
        self._adapter = adapter
        self._view_names = tuple(name for name, _ in adapter.views)
        self.view = self._view_names[0]
        self.selected: set[str] = set()
        self.detail_text = ""
        # str | None keys keep RowKey lookups branchless (RowKey.value is
        # str | None; our keys are always item ids or "#title").
        self._by_id: dict[str | None, T] = {adapter.item_id(item): item for item in adapter.items}
        self._view_for: dict[str | None, str] = {name: name for name in self._view_names}
        self._section_detail: dict[str | None, str] = {}

    def compose(self) -> ComposeResult:
        yield Tabs(*[Tab(label, id=name) for name, label in self._adapter.views])
        yield DataTable()
        if self._adapter.legend is not None:
            yield Static(Text.from_markup(self._adapter.legend), id="browser-legend")
        yield Static("", id="browser-detail")

    def on_mount(self) -> None:
        table = self.query_one(DataTable[Any])
        table.cursor_type = "row"
        table.focus()
        self._rebuild()

    # -- rows --------------------------------------------------------------
    def _rebuild(self) -> None:
        table = self.query_one(DataTable[Any])
        table.clear(columns=True)
        self._section_detail.clear()
        for label, key in self._adapter.columns:
            table.add_column(label, key=key)
        for title, detail, members in self._adapter.groups(self.view):
            if title:
                # The count guides the eye when narrow columns squeeze the rows.
                section = Text(f"── {title} ({len(members)}) ", style="bold")
                blanks = [""] * (len(self._adapter.columns) - 1)
                table.add_row(section, *blanks, key=f"#{title}")
                self._section_detail[f"#{title}"] = detail
            for item in members:
                table.add_row(*self._adapter.row_cells(item), key=self._adapter.item_id(item))
        first = self._first_selectable_row()
        if first is not None:
            table.move_cursor(row=first)
        # DataTable keeps serving render caches measured at the previous column
        # widths after clear(columns=True); a cell mutation arriving in a later
        # render cycle flushes them (textual 8.2.7), so re-mark every row once
        # the rebuilt table has painted.
        table.call_after_refresh(self._refresh_marks)

    # -- view switching ----------------------------------------------------
    def _switch_view(self, step: int) -> None:
        index = (self._view_names.index(self.view) + step) % len(self._view_names)
        self.query_one(Tabs).active = self._view_names[index]

    def action_prev_view(self) -> None:
        self._switch_view(-1)

    def action_next_view(self) -> None:
        self._switch_view(1)

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        self.view = self._view_for.get(event.tab.id, self.view)
        self._rebuild()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if self.view not in self._adapter.sortable_in_views:
            return
        on_sort = self._adapter.on_sort
        column_key = event.column_key.value
        if on_sort is None or column_key is None:
            return
        on_sort(column_key)
        self._rebuild()

    # -- selection ---------------------------------------------------------
    def _highlighted_item(self) -> T | None:
        # highlighted_key is None on an empty table; _by_id's str | None keys keep
        # the lookup branchless (section rows key on "#title", never on None).
        return self._by_id.get(highlighted_key(self.query_one(DataTable[Any])))

    def _first_selectable_row(self) -> int | None:
        table = self.query_one(DataTable[Any])
        for index, row_key in enumerate(table.rows):
            if row_key.value in self._by_id:  # item rows key on the id; sections on "#title"
                return index
        return None

    def _refresh_marks(self) -> None:
        # Scheduled via call_after_refresh, so by the time it fires under the real
        # driver the DataTable may be gone or cleared. Gone: rapid navigation can
        # pop this browser's screen (e.g. the Uninstall view) before the deferred
        # callback runs, removing the DataTable child while the browser still
        # reports is_mounted — query_one then raises NoMatches, which would wedge
        # the app's message loop. Cleared: a later _rebuild (single-tab activation,
        # resize) emptied it. Either way there is nothing to flush — the flush only
        # re-stamps the sel cell to bust the post-rebuild render cache — so no-op.
        try:
            table = self.query_one(DataTable[Any])
        except NoMatches:
            return
        if not table.columns:
            return
        for row_key in list(table.rows):
            item = self._by_id.get(row_key.value)
            if item is None or not self._adapter.selectable(item):
                continue  # section rows / non-selectable rows keep their rendered cell
            item_id = self._adapter.item_id(item)
            table.update_cell(item_id, "sel", mark(item_id in self.selected))

    def action_toggle_selected(self) -> None:
        item = self._highlighted_item()
        if item is None:  # empty table or a section row
            return
        if not self._adapter.selectable(item):  # a space on a non-selectable row is inert
            return
        item_id = self._adapter.item_id(item)
        self.selected.symmetric_difference_update({item_id})
        self.query_one(DataTable[Any]).update_cell(item_id, "sel", mark(item_id in self.selected))
        self.post_message(self.SelectionChanged())

    def action_select_all(self) -> None:
        self.selected = {
            self._adapter.item_id(item)
            for item in self._adapter.items
            if self._adapter.selectable(item)
        }
        self._refresh_marks()
        self.post_message(self.SelectionChanged())

    def action_invert(self) -> None:
        self.selected = {
            self._adapter.item_id(item)
            for item in self._adapter.items
            if self._adapter.selectable(item)
        } - self.selected
        self._refresh_marks()
        self.post_message(self.SelectionChanged())

    def selected_ids(self) -> list[str]:
        """The selected ids in adapter (item) order."""
        return [
            self._adapter.item_id(item)
            for item in self._adapter.items
            if self._adapter.item_id(item) in self.selected
        ]

    def action_accept(self) -> None:
        self.post_message(self.Accepted(self.selected_ids()))

    # -- detail bar --------------------------------------------------------
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        detail = self.query_one("#browser-detail", Static)
        item = self._by_id.get(event.row_key.value)
        if item is None:  # a section row: show the group's detail line
            self.detail_text = self._section_detail.get(event.row_key.value, "")
            detail.update(Text(self.detail_text, style=self._adapter.section_detail_style))
            return
        self.detail_text = self._adapter.detail_text(item)
        if self._adapter.detail_is_markup:
            detail.update(Text.from_markup(self.detail_text))
        else:
            detail.update(Text(self.detail_text))
