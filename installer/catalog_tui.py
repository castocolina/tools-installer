"""Textual catalog selection screen: one screen, switchable grouping views.

The wizard's interactive selection step (uzkit-parity F1): tools grouped by
category, priority, audience, install status, or shown as a flat sortable
table. Pure grouping/sorting helpers live alongside the app so they can be
unit-tested without a terminal. The browsable-list mechanics live in the
reusable `ToolBrowser` widget; this screen wires the catalog's data into it.
"""

from collections.abc import Mapping
from typing import Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import DataTable

from installer.model import Tool
from installer.tool_browser import BrowserAdapter, Section, ToolBrowser
from installer.ui_common import AppScreen, mark

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
_SORT_BY_COLUMN: dict[str, TableSortKey] = {
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


class CatalogScreen(AppScreen):
    """Single-screen tool picker; ←/→ or clicking the tabs switches the grouping.

    Mounted as the unified app's base screen. Accept/abort post a `Decided`
    message carrying the selected ids in catalog order (or None on abort); the
    host app turns that into its run() result. State the tests assert on (view,
    table_sort, selected, detail_text, status_text) is delegated to the embedded
    `ToolBrowser` (or the screen's StatusLine) and exposed as public properties.
    """

    class Decided(Message):
        """The user resolved the catalog: `result` is the selected ids in catalog
        order, or None when aborted. The host app forwards it to App.exit."""

        def __init__(self, result: list[str] | None) -> None:
            super().__init__()
            self.result = result

    def __init__(
        self,
        tools: list[Tool],
        installed: Mapping[str, bool],
        blurbs: Mapping[str, str],
    ) -> None:
        super().__init__(view="catalog")
        self.tools = list(tools)
        self.table_sort: TableSortKey = "priority"
        self._installed = dict(installed)
        self._blurbs = dict(blurbs)
        self._browser: ToolBrowser[Tool] = ToolBrowser(self._adapter())

    def _adapter(self) -> BrowserAdapter[Tool]:
        return BrowserAdapter(
            items=self.tools,
            columns=_COLUMNS,
            item_id=lambda tool: tool.id,
            row_cells=self._row_cells,
            detail_text=self._detail_text,
            groups=self._groups,
            views=tuple((view, _TAB_LABELS[view]) for view in VIEWS),
            legend=_LEGEND,
            on_sort=self._sort,
            sortable_in_views=frozenset({"table"}),
        )

    def compose_body(self) -> ComposeResult:
        yield self._browser

    # -- catalog data wiring for the browser adapter -----------------------
    def _row_cells(self, tool: Tool) -> list[Text]:
        installed = self._installed[tool.id]
        return [
            mark(tool.id in self._browser.selected),
            Text(tool.priority, style=_PRIORITY_STYLE[tool.priority]),
            Text(tool.id, style="bold"),
            Text(tool.category),
            Text(AUDIENCE_LABEL[tool.audience], style=_AUDIENCE_STYLE[tool.audience]),
            Text("✓", style="green") if installed else Text("○", style="yellow"),
            Text(tool.desc or tool.name, style="dim"),
        ]

    def _groups(self, view: str) -> list[Section[Tool]]:
        if view == "table":
            return [("", "", sort_for_table(self.tools, self._installed, self.table_sort))]
        return group_tools(self.tools, self._installed, view, self._blurbs)

    def _detail_text(self, tool: Tool) -> str:
        detail = (
            f"[bold]{tool.id}[/] — {tool.desc or tool.name}  |  "
            f"[{_PRIORITY_STYLE[tool.priority]}]{tool.priority}"
            f" {PRIORITY_LABEL[tool.priority]}[/]  |  "
            f"for {AUDIENCE_LABEL[tool.audience]}"
        )
        # Dependency slot for the deps PRD: shown only when declared, so the
        # layout is unchanged for the common no-requires case.
        if tool.requires:
            detail += f"  |  requires {', '.join(tool.requires)}"
        return detail

    def _sort(self, column_key: str) -> None:
        key = _SORT_BY_COLUMN.get(column_key)
        if key is None:
            return
        self.table_sort = key

    # -- public seams (delegated to the browser / status line) -------------
    @property
    def view(self) -> str:
        return self._browser.view

    @property
    def selected(self) -> set[str]:
        return self._browser.selected

    @property
    def detail_text(self) -> str:
        return self._browser.detail_text

    @property
    def status_text(self) -> str:
        return self.status.text

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        # The catalog test drives header sort directly on the screen. Forward it
        # to the browser, which owns the table and the view-gated sort handling.
        self._browser.on_data_table_header_selected(event)

    # -- accept ------------------------------------------------------------
    def on_tool_browser_selection_changed(self, event: ToolBrowser.SelectionChanged) -> None:
        # Clear the "select at least one" warning the moment the user selects.
        event.stop()
        self.status.clear()

    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        event.stop()
        if not event.ids:
            self.status.set("Select at least one tool, or press q to quit.", "warn")
            return
        self.status.clear()
        self.post_message(self.Decided(event.ids))
