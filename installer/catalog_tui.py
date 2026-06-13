"""Textual catalog selection screen: one screen, switchable grouping views.

The wizard's interactive selection step (uzkit-parity F1): tools grouped by
category, priority, audience, install status, or shown as a flat sortable
table. Pure grouping/sorting helpers live alongside the app so they can be
unit-tested without a terminal.
"""

from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.coordinate import Coordinate
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, Tab, Tabs

from installer.model import Tool

TableSortKey = Literal["id", "category", "priority", "audience", "installed"]

PRIORITY_LABEL = {"P0": "essential", "P1": "recommended", "P2": "nice-to-have", "P3": "niche"}
AUDIENCE_LABEL = {"ai": "AI", "human": "you", "both": "both"}


def sort_for_table(
    tools: list[Tool], installed: Mapping[str, bool], key: TableSortKey
) -> list[Tool]:
    """Flat-table order: by `key`, then priority, then id (deterministic)."""
    if key == "installed":
        return sorted(tools, key=lambda t: (installed[t.id], t.priority, t.id))
    return sorted(tools, key=lambda t: (getattr(t, key), t.priority, t.id))


def _category_title(category: str, blurbs: Mapping[str, str]) -> str:
    blurb = blurbs.get(category, "")
    return f"{category} — {blurb}" if blurb else category


def group_tools(
    tools: list[Tool],
    installed: Mapping[str, bool],
    view: str,
    blurbs: Mapping[str, str],
) -> list[tuple[str, str, list[Tool]]]:
    """(short title, detail line, members) per grouped view; empty groups dropped.

    The short title is what the section row shows in the table — it must stay
    narrow because it lives in the first column and auto-width would otherwise
    inflate it. The detail line (e.g. the category blurb) goes to the detail
    bar when the section row is highlighted. Members are priority-then-id.
    """
    ordered = sorted(tools, key=lambda t: (t.priority, t.id))
    if view == "priority":
        groups = [
            (p, f"{p} · {PRIORITY_LABEL[p]}", [t for t in ordered if t.priority == p])
            for p in ("P0", "P1", "P2", "P3")
        ]
    elif view == "audience":
        titles = {a: f"for {AUDIENCE_LABEL[a]}" for a in ("ai", "both", "human")}
        groups = [
            (title, title, [t for t in ordered if t.audience == a]) for a, title in titles.items()
        ]
    elif view == "status":
        groups = [
            ("missing", "missing", [t for t in ordered if not installed[t.id]]),
            ("installed", "installed", [t for t in ordered if installed[t.id]]),
        ]
    elif view == "category":
        categories = sorted({t.category for t in ordered})
        groups = [
            (c, _category_title(c, blurbs), [t for t in ordered if t.category == c])
            for c in categories
        ]
    else:  # "table" is routed by the app before grouping; anything else is a bug
        raise ValueError(f"unknown view: {view!r}")
    return [(title, detail, members) for title, detail, members in groups if members]


VIEWS: tuple[str, ...] = ("category", "priority", "audience", "status", "table")
_TAB_LABELS = {
    "category": "Category",
    "priority": "Priority",
    "audience": "Audience",
    "status": "Status",
    "table": "Table",
}
_PRIORITY_STYLE = {"P0": "bold red", "P1": "bold yellow", "P2": "blue", "P3": "dim"}
_AUDIENCE_STYLE = {"ai": "bold cyan", "human": "magenta", "both": ""}

# Sortable Table-view columns by column key; absent keys (sel/desc) don't sort.
_SORT_BY_COLUMN: dict[str | None, TableSortKey] = {
    "pri": "priority",
    "tool": "id",
    "cat": "category",
    "for": "audience",
    "inst": "installed",
}

_COLUMNS = (
    ("Sel", "sel"),
    ("Pri", "pri"),
    ("Tool", "tool"),
    ("Cat", "cat"),
    ("For", "for"),
    ("Inst", "inst"),
    ("What it does", "desc"),
)

_LEGEND = (
    "[bold red]P0[/] essential · [bold yellow]P1[/] recommended · [blue]P2[/] nice-to-have"
    " · [dim]P3[/] niche  |  for [bold cyan]AI[/] / [magenta]you[/] / both"
    "  |  [green]✓ installed[/] · [yellow]○ missing[/]"
)


class CatalogScreen(Screen[list[str] | None]):
    """Single-screen tool picker; ←/→ or clicking the tabs switches the grouping.

    Mounted as the unified app's base screen. Accept/abort post a `Decided`
    message carrying the selected ids in catalog order (or None on abort); the
    host app turns that into its run() result. State the tests assert on (view,
    table_sort, selected, detail_text) is deliberately public.
    """

    class Decided(Message):
        """The user resolved the catalog: `result` is the selected ids in catalog
        order, or None when aborted. The host app forwards it to App.exit."""

        def __init__(self, result: list[str] | None) -> None:
            super().__init__()
            self.result = result

    DEFAULT_CSS = """
    Tabs { dock: top; }
    #detail { dock: bottom; height: 2; padding: 0 1; background: $surface; }
    #legend { dock: bottom; height: 1; padding: 0 1; }
    DataTable { height: 1fr; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "prev_view", "prev view", priority=True),
        Binding("right", "next_view", "next view", priority=True),
        Binding("space", "toggle_tool", "toggle", priority=True),
        Binding("a", "select_all", "all"),
        Binding("i", "invert", "invert"),
        Binding("enter", "accept", "install selected", priority=True),
        Binding("q", "abort", "quit"),
    ]

    def __init__(
        self,
        tools: list[Tool],
        installed: Mapping[str, bool],
        blurbs: Mapping[str, str],
    ) -> None:
        super().__init__()
        self.tools = list(tools)
        self.view = VIEWS[0]
        self.table_sort: TableSortKey = "priority"
        self.selected: set[str] = set()
        self.detail_text = ""
        self._installed = dict(installed)
        self._blurbs = dict(blurbs)
        # str | None keys let row-key lookups stay branchless under strict typing
        # (RowKey.value is str | None; ours are always tool ids).
        self._by_id: dict[str | None, Tool] = {tool.id: tool for tool in self.tools}
        # Tab ids are exactly the view names. A dict (str | None keys) instead of
        # `id if id in VIEWS else ...` keeps the handler branchless: pyright can't
        # narrow `str | None` through an `in` check, and a branch would be
        # uncoverable (tabs are built from VIEWS, so misses can't happen).
        self._view_for: dict[str | None, str] = {view: view for view in VIEWS}
        # Section-row key -> detail-bar line, rebuilt with the table (str | None
        # keys for the same branchless RowKey lookups as _by_id).
        self._section_detail: dict[str | None, str] = {}

    def compose(self) -> ComposeResult:
        yield Tabs(*[Tab(_TAB_LABELS[view], id=view) for view in VIEWS])
        yield DataTable()
        yield Static(Text.from_markup(_LEGEND), id="legend")
        yield Static("", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable[Any])
        table.cursor_type = "row"
        table.focus()
        self._rebuild()

    # -- rows -----------------------------------------------------------
    def _row_cells(self, tool: Tool) -> list[Text]:
        chosen = tool.id in self.selected
        installed = self._installed[tool.id]
        return [
            Text("[x]" if chosen else "[ ]", style="green" if chosen else ""),
            Text(tool.priority, style=_PRIORITY_STYLE[tool.priority]),
            Text(tool.id, style="bold"),
            Text(tool.category),
            Text(AUDIENCE_LABEL[tool.audience], style=_AUDIENCE_STYLE[tool.audience]),
            Text("✓", style="green") if installed else Text("○", style="yellow"),
            Text(tool.desc or tool.name, style="dim"),
        ]

    def _groups(self) -> list[tuple[str, str, list[Tool]]]:
        if self.view == "table":
            return [("", "", sort_for_table(self.tools, self._installed, self.table_sort))]
        return group_tools(self.tools, self._installed, self.view, self._blurbs)

    def _rebuild(self) -> None:
        table = self.query_one(DataTable[Any])
        table.clear(columns=True)
        self._section_detail.clear()
        for label, key in _COLUMNS:
            table.add_column(label, key=key)
        for title, detail, members in self._groups():
            if title:
                section = Text(f"── {title} ", style="bold")
                table.add_row(section, "", "", "", "", "", "", key=f"#{title}")
                self._section_detail[f"#{title}"] = detail
            for tool in members:
                table.add_row(*self._row_cells(tool), key=tool.id)
        # DataTable keeps serving render caches measured at the previous column
        # widths after clear(columns=True); a cell mutation arriving in a later
        # render cycle flushes them (textual 8.2.7), so re-mark every row once
        # the rebuilt table has painted.
        table.call_after_refresh(self._refresh_marks)

    # -- view switching ---------------------------------------------------
    def _switch_view(self, step: int) -> None:
        index = (VIEWS.index(self.view) + step) % len(VIEWS)
        self.query_one(Tabs).active = VIEWS[index]

    def action_prev_view(self) -> None:
        self._switch_view(-1)

    def action_next_view(self) -> None:
        self._switch_view(1)

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        self.view = self._view_for.get(event.tab.id, self.view)
        self._rebuild()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if self.view != "table":
            return
        key = _SORT_BY_COLUMN.get(event.column_key.value)
        if key is None:
            return
        self.table_sort = key
        self._rebuild()

    # -- selection ----------------------------------------------------------
    def _highlighted_tool(self) -> Tool | None:
        table = self.query_one(DataTable[Any])
        if table.row_count == 0:
            return None
        cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        return self._by_id.get(cell_key.row_key.value)

    def _mark(self, chosen: bool) -> Text:
        return Text("[x]" if chosen else "[ ]", style="green" if chosen else "")

    def _refresh_marks(self) -> None:
        table = self.query_one(DataTable[Any])
        for tool in self.tools:
            chosen = tool.id in self.selected
            table.update_cell(tool.id, "sel", self._mark(chosen))

    def action_toggle_tool(self) -> None:
        tool = self._highlighted_tool()
        if tool is None:  # empty catalog or a section row
            return
        self.selected.symmetric_difference_update({tool.id})
        chosen = tool.id in self.selected
        self.query_one(DataTable[Any]).update_cell(tool.id, "sel", self._mark(chosen))

    def action_select_all(self) -> None:
        self.selected = {tool.id for tool in self.tools}
        self._refresh_marks()

    def action_invert(self) -> None:
        self.selected = {tool.id for tool in self.tools} - self.selected
        self._refresh_marks()

    def action_accept(self) -> None:
        self.post_message(
            self.Decided([tool.id for tool in self.tools if tool.id in self.selected])
        )

    def action_abort(self) -> None:
        self.post_message(self.Decided(None))

    # -- detail bar ----------------------------------------------------------
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        tool = self._by_id.get(event.row_key.value)
        detail = self.query_one("#detail", Static)
        if tool is None:  # a section row: show the group's detail line
            self.detail_text = self._section_detail.get(event.row_key.value, "")
            detail.update(Text(self.detail_text, style="bold"))
            return
        self.detail_text = (
            f"[bold]{tool.id}[/] — {tool.desc or tool.name}  |  "
            f"[{_PRIORITY_STYLE[tool.priority]}]{tool.priority}"
            f" {PRIORITY_LABEL[tool.priority]}[/]  |  "
            f"for {AUDIENCE_LABEL[tool.audience]}"
        )
        detail.update(Text.from_markup(self.detail_text))
