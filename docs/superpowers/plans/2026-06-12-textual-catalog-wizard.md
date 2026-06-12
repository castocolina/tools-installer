# Textual Catalog Wizard (uzkit-parity F1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the wizard's interactive selection step with a single Textual screen whose grouping (Category / Priority / Audience / Status / Table) switches live via ←/→ or mouse-clickable tabs, with clickable column-header sorting in the Table view.

**Architecture:** New `installer/catalog_tui.py` (pure grouping/sorting helpers + a `CatalogApp(App[list[str] | None])` shell over them), inside the 100% coverage gate via Textual's headless `Pilot`. `run_wizard` gains an optional `select_catalog` seam that replaces the two-step questionary flow when provided; `setup.py` wires a closure that runs the app. Everything downstream (audit table, confirm, install, PATH wiring) is untouched.

**Tech Stack:** textual >= 8 (runtime dep, verified 8.2.7), pytest-asyncio (dev dep, `asyncio_mode = "auto"`), existing uv/pytest/pyright-strict/ruff gates.

**Spec:** `docs/superpowers/specs/2026-06-11-textual-wizard-design.md` (approved).
**Validated prototype:** `.superpowers/prototypes/wizard_tui.py` (gitignored; reference only — production code below is the typed, coverage-clean rewrite).

**Verified API facts (textual 8.2.7):** `DataTable.HeaderSelected(data_table, column_key, column_index, label)`; `DataTable.RowHighlighted(data_table, cursor_row, row_key)`; `add_column(label, *, key=...)`; `ColumnKey`/`RowKey` import from `textual.widgets.data_table`; `Static` content cannot be inspected outside a live app — tests assert on a public `detail_text` attribute instead.

**Repo conventions:** work on `main` (no remote); `make validate && make test` green on every commit; vulture runs at `min_confidence = 80`, so Textual's dynamically-dispatched `on_*`/`action_*` methods (60-confidence findings) do NOT trip the gate — no whitelist needed.

---

## File map

| File | Change |
| --- | --- |
| `pyproject.toml` | `textual>=8` in `[project].dependencies`; `pytest-asyncio` in dev group; `asyncio_mode = "auto"` |
| `installer/catalog_tui.py` | NEW — helpers (Task 2) + `CatalogApp` (Task 3) |
| `tests/test_catalog_tui.py` | NEW — helper unit tests (Task 2) + Pilot tests (Task 3) |
| `installer/app.py` | `_choose_tools`/`run_wizard` gain `select_catalog` seam; abort returns None (Task 4) |
| `tests/test_app.py` | seam tests (Task 4) |
| `setup.py` | `_select_catalog` closure wired into `run_wizard` (Task 5) |
| `README.md` | selection-screen docs (Task 5) |

---

### Task 1: Dependencies via pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the runtime and dev dependencies (uv edits pyproject.toml — never install ad hoc)**

```bash
uv add "textual>=8"
uv add --dev pytest-asyncio
```

Expected result in `pyproject.toml`: `[project].dependencies` now contains `"textual>=8"`; the `dev` dependency group contains a `pytest-asyncio` entry. `uv.lock` updated.

- [ ] **Step 2: Enable auto asyncio mode for Pilot tests**

In `pyproject.toml`, extend `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: Verify**

Run: `uv run python -c "import textual; print(textual.__version__)"`
Expected: prints `8.x`.

Run: `make validate && make test`
Expected: all pass, 340 tests, coverage 100% (no code change yet).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add textual (runtime) and pytest-asyncio (dev)"
```

---

### Task 2: Pure grouping and sorting helpers

**Files:**
- Create: `installer/catalog_tui.py`
- Create: `tests/test_catalog_tui.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_catalog_tui.py`:

```python
from installer.catalog_tui import group_tools, sort_for_table
from installer.model import Method, Tool


def _tool(
    tool_id: str,
    *,
    category: str = "search",
    priority: str = "P1",
    audience: str = "both",
    desc: str = "",
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority=priority,
        audience=audience,
        desc=desc,
    )


_BLURBS = {"search": "Find files and code at speed"}


def _catalog() -> tuple[list[Tool], dict[str, bool]]:
    tools = [
        _tool("rg", priority="P0", audience="ai", desc="fast grep"),
        _tool("fd", priority="P1", audience="both", desc="file finder"),
        _tool("lazygit", category="git", priority="P2", audience="human"),
    ]
    installed = {"rg": True, "fd": False, "lazygit": False}
    return tools, installed


def test_group_by_priority_orders_tiers_and_drops_empty():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "priority", _BLURBS)
    assert [title for title, _ in groups] == [
        "P0 · essential",
        "P1 · recommended",
        "P2 · nice-to-have",
    ]  # no P3 tools -> tier dropped
    assert [t.id for _, members in groups for t in members] == ["rg", "fd", "lazygit"]


def test_group_by_audience_uses_labels():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "audience", _BLURBS)
    assert [title for title, _ in groups] == ["for AI", "for both", "for you"]


def test_group_by_status_splits_missing_then_installed():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "status", _BLURBS)
    assert groups[0][0] == "missing"
    assert [t.id for t in groups[0][1]] == ["fd", "lazygit"]
    assert groups[1][0] == "installed"
    assert [t.id for t in groups[1][1]] == ["rg"]


def test_group_by_category_is_alphabetical_with_blurb_titles():
    tools, installed = _catalog()
    groups = group_tools(tools, installed, "category", _BLURBS)
    # "git" has no blurb -> plain title; "search" has one -> appended.
    assert [title for title, _ in groups] == [
        "git",
        "search — Find files and code at speed",
    ]
    # within a group: priority then id
    assert [t.id for t in groups[1][1]] == ["rg", "fd"]


def test_sort_for_table_by_each_key():
    tools, installed = _catalog()
    assert [t.id for t in sort_for_table(tools, installed, "id")] == ["fd", "lazygit", "rg"]
    assert [t.id for t in sort_for_table(tools, installed, "priority")] == [
        "rg",
        "fd",
        "lazygit",
    ]
    assert [t.id for t in sort_for_table(tools, installed, "category")] == [
        "lazygit",
        "rg",
        "fd",
    ]
    assert [t.id for t in sort_for_table(tools, installed, "audience")] == [
        "rg",
        "fd",
        "lazygit",
    ]  # ai < both < human alphabetically
    assert [t.id for t in sort_for_table(tools, installed, "installed")] == [
        "fd",
        "lazygit",
        "rg",
    ]  # missing first, then installed
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_catalog_tui.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'installer.catalog_tui'`.

- [ ] **Step 3: Implement the helpers**

Create `installer/catalog_tui.py`:

```python
"""Textual catalog selection screen: one screen, switchable grouping views.

The wizard's interactive selection step (uzkit-parity F1): tools grouped by
category, priority, audience, install status, or shown as a flat sortable
table. Pure grouping/sorting helpers live alongside the app so they can be
unit-tested without a terminal.
"""

from collections.abc import Mapping

from installer.model import Tool

PRIORITY_LABEL = {"P0": "essential", "P1": "recommended", "P2": "nice-to-have", "P3": "niche"}
AUDIENCE_LABEL = {"ai": "AI", "human": "you", "both": "both"}


def sort_for_table(tools: list[Tool], installed: Mapping[str, bool], key: str) -> list[Tool]:
    """Flat-table order: by `key`, then priority, then id (deterministic)."""
    if key == "installed":
        return sorted(tools, key=lambda t: (not installed[t.id], t.priority, t.id))
    return sorted(tools, key=lambda t: (getattr(t, key), t.priority, t.id))


def _category_title(category: str, blurbs: Mapping[str, str]) -> str:
    blurb = blurbs.get(category, "")
    return f"{category} — {blurb}" if blurb else category


def group_tools(
    tools: list[Tool],
    installed: Mapping[str, bool],
    view: str,
    blurbs: Mapping[str, str],
) -> list[tuple[str, list[Tool]]]:
    """(section title, members) per grouped view; members priority-then-id; empty groups dropped."""
    ordered = sorted(tools, key=lambda t: (t.priority, t.id))
    if view == "priority":
        groups = [
            (f"{p} · {PRIORITY_LABEL[p]}", [t for t in ordered if t.priority == p])
            for p in ("P0", "P1", "P2", "P3")
        ]
    elif view == "audience":
        groups = [
            (f"for {AUDIENCE_LABEL[a]}", [t for t in ordered if t.audience == a])
            for a in ("ai", "both", "human")
        ]
    elif view == "status":
        groups = [
            ("missing", [t for t in ordered if not installed[t.id]]),
            ("installed", [t for t in ordered if installed[t.id]]),
        ]
    else:  # category (the app never routes "table" here)
        categories = sorted({t.category for t in ordered})
        groups = [
            (_category_title(c, blurbs), [t for t in ordered if t.category == c])
            for c in categories
        ]
    return [(title, members) for title, members in groups if members]
```

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all pass, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add installer/catalog_tui.py tests/test_catalog_tui.py
git commit -m "feat: catalog grouping and table-sort helpers"
```

---

### Task 3: The CatalogApp screen (Pilot-tested)

**Files:**
- Modify: `installer/catalog_tui.py` (append the app)
- Modify: `tests/test_catalog_tui.py` (append Pilot tests)

- [ ] **Step 1: Write the failing Pilot tests**

Append to `tests/test_catalog_tui.py` (update the top import line to also pull in the app pieces):

```python
from rich.text import Text
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from installer.catalog_tui import CatalogApp, group_tools, sort_for_table
```

(then delete the now-duplicated original `from installer.catalog_tui import group_tools, sort_for_table` line)

```python
def _app() -> CatalogApp:
    tools, installed = _catalog()
    return CatalogApp(tools, installed, _BLURBS)


async def test_starts_in_category_view_with_section_rows():
    app = _app()
    async with app.run_test(size=(100, 30)):
        assert app.view == "category"
        table = app.query_one(DataTable)
        assert table.row_count == 5  # 2 section rows + 3 tool rows


async def test_arrow_keys_cycle_views_and_wrap():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("right")
        assert app.view == "priority"
        await pilot.press("left", "left")
        assert app.view == "table"  # wrapped backwards past category


async def test_clicking_a_tab_switches_view():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#status")
        assert app.view == "status"


async def test_space_toggles_tool_rows_and_ignores_section_rows():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")  # cursor starts on the "git" section row -> no-op
        assert app.selected == set()
        await pilot.press("down", "space")  # first tool row: lazygit
        assert app.selected == {"lazygit"}
        await pilot.press("space")  # toggle off again
        assert app.selected == set()


async def test_select_all_and_invert():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        assert app.selected == {"rg", "fd", "lazygit"}
        await pilot.press("i")
        assert app.selected == set()
        await pilot.press("down", "space", "i")
        assert app.selected == {"rg", "fd"}


async def test_enter_returns_selection_in_catalog_order():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a", "enter")
    assert app.return_value == ["rg", "fd", "lazygit"]


async def test_q_aborts_with_none():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("down", "space", "q")
    assert app.return_value is None


async def test_detail_bar_follows_the_highlighted_row():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.detail_text == ""  # section row highlighted on start
        await pilot.press("down")  # lazygit: empty desc -> falls back to name
        assert "lazygit" in app.detail_text
        assert "P2" in app.detail_text
        assert "for you" in app.detail_text


async def test_header_click_sorts_only_in_table_view():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("left")  # wrap straight to the table view
        assert app.view == "table"
        table = app.query_one(DataTable)
        app.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("tool"), 2, Text("Tool"))
        )
        assert app.table_sort == "id"
        # non-sortable column -> ignored
        app.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("sel"), 0, Text("Sel"))
        )
        assert app.table_sort == "id"
        await pilot.press("right")  # back to category view
        app.on_data_table_header_selected(
            DataTable.HeaderSelected(table, ColumnKey("pri"), 1, Text("Pri"))
        )
        assert app.table_sort == "id"  # ignored outside the table view


async def test_empty_catalog_is_safe():
    app = CatalogApp([], {}, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space", "enter")  # toggle on empty table must not crash
    assert app.return_value == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_catalog_tui.py -v`
Expected: FAIL with `ImportError: cannot import name 'CatalogApp'`.

- [ ] **Step 3: Implement the app**

Append to `installer/catalog_tui.py` (and extend the imports at the top):

```python
from collections.abc import Mapping
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Static, Tab, Tabs

from installer.model import Tool
```

```python
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

# Column index -> sort key for the Table view's clickable headers.
TABLE_SORT_KEYS: tuple[str | None, ...] = (
    None,  # Sel
    "priority",  # Pri
    "id",  # Tool
    "category",  # Cat
    "audience",  # For
    "installed",  # Inst
    None,  # What it does
)

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


class CatalogApp(App[list[str] | None]):
    """Single-screen tool picker; ←/→ or clicking the tabs switches the grouping.

    run() returns the selected ids in catalog order, or None when aborted (q).
    State the tests assert on (view, table_sort, selected, detail_text) is
    deliberately public.
    """

    CSS = """
    Tabs { dock: top; }
    #detail { dock: bottom; height: 2; padding: 0 1; background: $surface; }
    #legend { dock: bottom; height: 1; padding: 0 1; }
    DataTable { height: 1fr; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "prev_view", "prev view", priority=True),
        Binding("right", "next_view", "next view", priority=True),
        Binding("space", "toggle", "toggle", priority=True),
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
        self.table_sort = "priority"
        self.selected: set[str] = set()
        self.detail_text = ""
        self._installed = dict(installed)
        self._blurbs = dict(blurbs)
        # str | None keys let row-key lookups stay branchless under strict typing
        # (RowKey.value is str | None; ours are always tool ids).
        self._by_id: dict[str | None, Tool] = {tool.id: tool for tool in self.tools}
        self._view_for: dict[str | None, str] = {view: view for view in VIEWS}

    def compose(self) -> ComposeResult:
        yield Tabs(*[Tab(_TAB_LABELS[view], id=view) for view in VIEWS])
        yield DataTable()
        yield Static(Text.from_markup(_LEGEND), id="legend")
        yield Static("", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
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

    def _groups(self) -> list[tuple[str, list[Tool]]]:
        if self.view == "table":
            return [("", sort_for_table(self.tools, self._installed, self.table_sort))]
        return group_tools(self.tools, self._installed, self.view, self._blurbs)

    def _rebuild(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        for label, key in _COLUMNS:
            table.add_column(label, key=key)
        for title, members in self._groups():
            if title:
                section = Text(f"── {title} ", style="bold")
                table.add_row(section, "", "", "", "", "", "", key=f"#{title}")
            for tool in members:
                table.add_row(*self._row_cells(tool), key=tool.id)

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
        key = TABLE_SORT_KEYS[event.column_index]
        if key is None:
            return
        self.table_sort = key
        self._rebuild()

    # -- selection ----------------------------------------------------------
    def _highlighted_tool(self) -> Tool | None:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        return self._by_id.get(cell_key.row_key.value)

    def action_toggle(self) -> None:
        tool = self._highlighted_tool()
        if tool is None:  # empty catalog or a section row
            return
        self.selected.symmetric_difference_update({tool.id})
        chosen = tool.id in self.selected
        mark = Text("[x]" if chosen else "[ ]", style="green" if chosen else "")
        self.query_one(DataTable).update_cell(tool.id, "sel", mark)

    def action_select_all(self) -> None:
        self.selected = {tool.id for tool in self.tools}
        self._rebuild()

    def action_invert(self) -> None:
        self.selected = {tool.id for tool in self.tools} - self.selected
        self._rebuild()

    def action_accept(self) -> None:
        self.exit([tool.id for tool in self.tools if tool.id in self.selected])

    def action_abort(self) -> None:
        self.exit(None)

    # -- detail bar ----------------------------------------------------------
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        tool = self._by_id.get(event.row_key.value)
        detail = self.query_one("#detail", Static)
        if tool is None:  # a section row
            self.detail_text = ""
            detail.update("")
            return
        self.detail_text = (
            f"[bold]{tool.id}[/] — {tool.desc or tool.name}  |  "
            f"[{_PRIORITY_STYLE[tool.priority]}]{tool.priority}"
            f" {PRIORITY_LABEL[tool.priority]}[/]  |  "
            f"for {AUDIENCE_LABEL[tool.audience]}"
        )
        detail.update(Text.from_markup(self.detail_text))
```

- [ ] **Step 4: Run the Pilot tests**

Run: `uv run pytest tests/test_catalog_tui.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full gate**

Run: `make validate && make test`
Expected: all pass, coverage 100% (every branch above is exercised: section-row toggle guard via `test_space_toggles…`, empty-table guard via `test_empty_catalog…`, all three header-click branches via `test_header_click…`, desc-fallback via lazygit's empty desc, table-vs-grouped `_groups` branches via the table-view tests).

- [ ] **Step 6: Commit**

```bash
git add installer/catalog_tui.py tests/test_catalog_tui.py
git commit -m "feat: Textual catalog selection screen with switchable views"
```

---

### Task 4: The `select_catalog` seam in the wizard

**Files:**
- Modify: `installer/app.py:46-102` (`_choose_tools`, `run_wizard`)
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app.py`:

```python
def test_catalog_seam_replaces_two_step_selection():
    installed_ids, install = _recording_install()
    prompter = FakePrompter(categories=["IGNORED"], tools=["IGNORED"], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        select_catalog=lambda tools: ["jq"],
    )
    assert installed_ids == ["jq"]
    assert summary is not None
    assert prompter.confirmed == 1  # the confirm step still runs


def test_catalog_seam_abort_returns_none_without_confirm():
    installed_ids, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        select_catalog=lambda tools: None,
    )
    assert summary is None
    assert installed_ids == []
    assert prompter.confirmed == 0


def test_all_flag_bypasses_catalog_seam():
    def boom(tools: list[Tool]) -> list[str] | None:
        raise AssertionError("select_catalog must not be called under --all")

    installed_ids, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        select_catalog=boom,
    )
    assert installed_ids == ["rg", "fd", "jq"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_app.py -v`
Expected: the three new tests FAIL with `TypeError: run_wizard() got an unexpected keyword argument 'select_catalog'`.

- [ ] **Step 3: Implement the seam**

In `installer/app.py`, add the alias near the top (after the imports):

```python
# Catalog selection seam: given the platform-filtered tools, return the chosen
# ids (the Textual screen in production), or None when the user aborted.
SelectCatalog = Callable[[list[Tool]], list[str] | None]
```

Replace `_choose_tools` with:

```python
def _choose_tools(
    tools: list[Tool],
    prompter: Prompter,
    options: Options,
    installed: Callable[[Tool], bool],
    category_blurbs: dict[str, str] | None = None,
    select_catalog: SelectCatalog | None = None,
) -> list[Tool] | None:
    """The tools to install, or None when the user aborted the selection screen."""
    if options.all:
        return tools
    if options.categories:
        return [tool for tool in tools if tool.category in options.categories]
    if select_catalog is not None:
        chosen_ids = select_catalog(tools)
        if chosen_ids is None:
            return None
        return select_tools(tools, chosen_ids)
    chosen_categories = prompter.select_categories(category_choices(tools, category_blurbs))
    wanted = set(chosen_categories)
    in_categories = [tool for tool in tools if tool.category in wanted]
    statuses = audit(in_categories, installed)
    chosen_ids = prompter.select_tools(tool_choices(statuses))
    return select_tools(in_categories, chosen_ids)
```

In `run_wizard`, add the parameter and the abort check (docstring gains one line):

```python
def run_wizard(
    tools: list[Tool],
    platform: Platform,
    prompter: Prompter,
    console: Console,
    options: Options,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: Install = install_tool,
    installed: Callable[[Tool], bool] = is_installed,
    on_mismatch: OnMismatch | None = None,
    category_blurbs: dict[str, str] | None = None,
    select_catalog: SelectCatalog | None = None,
) -> Summary | None:
```

```python
    select_catalog, when given, replaces the category->tools prompts with the
    single catalog screen; its None return (user aborted) aborts the wizard.
    """
    selected = _choose_tools(tools, prompter, options, installed, category_blurbs, select_catalog)
    if selected is None:
        return None
```

(The rest of `run_wizard` is unchanged.)

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all pass, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add installer/app.py tests/test_app.py
git commit -m "feat: wizard accepts a catalog selection seam (None = abort)"
```

---

### Task 5: Wire setup.py and document

**Files:**
- Modify: `setup.py`
- Modify: `README.md`

- [ ] **Step 1: Wire the closure in setup.py**

Add the imports (with the existing `installer.` imports):

```python
from installer.catalog_tui import CatalogApp
from installer.status import is_installed
```

Add the closure (after `_ask_mismatch`):

```python
def _select_catalog(tools: list[Tool]) -> list[str] | None:
    installed = {tool.id: is_installed(tool) for tool in tools}
    return CatalogApp(tools, installed, load_categories(_REGISTRY)).run()
```

In `main`, thread it into the wizard call:

```python
    summary = run_wizard(
        tools,
        platform,
        prompter,
        console,
        options,
        on_mismatch=_ask_mismatch,
        category_blurbs=load_categories(_REGISTRY),
        select_catalog=_select_catalog,
    )
```

Update the module docstring's first paragraph mention of questionary to:

```python
"""Entry point for the tools-installer wizard. Run via `make setup` (uv run setup.py).

This is the composition root: it performs the real terminal IO (the Textual
catalog screen for selection; questionary for confirms and choices) and the
real home-path wiring, and composes the pure, fully-tested installer package.
It deliberately lives outside the `installer/` package so the untyped
questionary boundary is isolated from the strict-typed, fully-covered core.
"""
```

- [ ] **Step 2: Document the screen in README.md**

Insert this section immediately before `## Supported platforms`:

```markdown
## Selecting tools

The wizard opens a single catalog screen (keyboard and mouse):

| Key / action | Effect |
| --- | --- |
| ←/→ or click a tab | switch grouping: Category · Priority · Audience · Status · Table |
| click a column header (Table view) | re-sort by that column |
| ↑/↓ | move; the bottom bar shows the highlighted tool's details |
| space / a / i | toggle · select all · invert |
| enter | install the selection (audit + confirm follow) |
| q | abort |

Priorities are color-coded (P0 essential → P3 niche) and every tool shows who
it serves (AI · you · both) plus its install state, with a legend pinned at
the bottom. `--all` and `--categories A,B` skip the screen entirely.
```

- [ ] **Step 3: Run the full gate + smoke**

Run: `make validate && make test`
Expected: all pass, coverage 100%.

Run: `uv run setup.py --help`
Expected: exits 0. Do NOT run the real wizard against the dev machine's home —
the USER tries `make setup` themselves (q aborts without installing anything).

- [ ] **Step 4: Commit**

```bash
git add setup.py README.md
git commit -m "feat: wizard selection runs in the Textual catalog screen"
```

---

## Out of scope (per spec)

- Install-progress/summary screens in Textual; removing questionary's confirm /
  link-mode / mismatch prompts; the old two-step prompter path (kept as
  fallback + test seam).
- `requires` dependencies (F3) and AI-rationale field (F2) — the detail bar is
  their future slot.

## Acceptance

`make setup` on a TTY opens the catalog screen; ←/→ and tab clicks switch the
five views; the Table view re-sorts on header clicks; enter hands the selection
to the unchanged audit → confirm → install flow; q prints "Aborted." and exits 0.
