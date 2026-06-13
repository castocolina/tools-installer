# Unified UI — Phase 1: Unified Textual App + Navigation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single catalog app into a unified Textual *shell* that hosts every view (catalog + navigable placeholders), with dual-route navigation (our own Ctrl+P palette and direct number keys) through one dispatch, plus the three catalog quick-wins.

**Architecture:** A thin `UnifiedApp(App[list[str] | None])` owns navigation and the screen stack; the catalog UI becomes `CatalogScreen(Screen[...])`; doctor/fix/uninstall/policies are a shared `PlaceholderScreen`. Both navigation routes call one `show_view(name)` so they cannot drift. Execution stays behind the pure `installer/` core invoked from `setup.py`; the app only collects the catalog decision (`list[str] | None`).

**Tech Stack:** Python, uv, Textual (App/Screen/ModalScreen/ListView), Rich, pytest (`app.run_test`), ruff/pyright/bandit/vulture (`make validate`).

**Design spec:** `docs/superpowers/specs/2026-06-13-unified-ui-phase1-design.md`

---

## File Structure

- **`installer/catalog_tui.py`** *(modify)* — `CatalogApp` → `CatalogScreen(Screen[list[str] | None])`. Pure helpers (`group_tools`, `sort_for_table`) unchanged. Gains the cursor quick-win, the empty-selection guard, and a `#status` line.
- **`installer/wizard_app.py`** *(create)* — `UnifiedApp` shell, `PlaceholderScreen`, `NavScreen` (our palette), the `VIEW_ORDER` registry, and the single `show_view` dispatch.
- **`setup.py`** *(modify)* — `_select_catalog` launches `UnifiedApp` instead of `CatalogApp` (IO boundary; excluded from coverage/pyright).
- **`tests/test_catalog_tui.py`** *(modify)* — migrate the async catalog tests to drive `UnifiedApp` and read state via `app.catalog`; update the tests whose assumptions the quick-wins change.
- **`tests/test_wizard_app.py`** *(create)* — shell tests: dual-route navigation, placeholders, default-palette disabled, abort from any screen.
- **`README.md`** / **`Makefile`** *(modify, Task 6)* — reflect the single-app UI.
- **`/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md`** *(modify, Task 6)* — mark Phase 1 landed.

**Coverage note:** `installer/` keeps 100% coverage, so every line of `wizard_app.py` and the new `catalog_tui.py` paths must be exercised by tests. `setup.py` stays the coverage/pyright-excluded boundary.

**Test command reference:** single test `uv run pytest tests/test_x.py::test_name -v`; full gate `make validate && make test`.

---

## Task 1: Extract `CatalogScreen`; introduce `UnifiedApp` shell (no behavior change)

The existing async catalog tests are the regression spec for this refactor: after it, they pass unchanged in behavior, only re-pointed at the new entry points.

**Files:**
- Modify: `installer/catalog_tui.py`
- Create: `installer/wizard_app.py`
- Modify: `setup.py:25` (import) and `setup.py:141-143` (`_select_catalog`)
- Modify: `tests/test_catalog_tui.py`

- [ ] **Step 1: Convert `CatalogApp` into `CatalogScreen`**

In `installer/catalog_tui.py`, change the imports so the class is a Screen:

```python
from textual.app import ComposeResult
from textual.screen import Screen
```

(Remove `App` from the `from textual.app import ...` line — it is no longer used.)

Change the class declaration and docstring:

```python
class CatalogScreen(Screen[list[str] | None]):
    """Single-screen tool picker; ←/→ or clicking the tabs switches the grouping.

    Mounted inside the unified app. Accept exits the app with the selected ids in
    catalog order; abort exits with None. State the tests assert on (view,
    table_sort, selected, detail_text) is deliberately public.
    """
```

Rename the `CSS` class attribute to `DEFAULT_CSS` (Screens take `DEFAULT_CSS`):

```python
    DEFAULT_CSS = """
    Tabs { dock: top; }
    #detail { dock: bottom; height: 2; padding: 0 1; background: $surface; }
    #legend { dock: bottom; height: 1; padding: 0 1; }
    DataTable { height: 1fr; }
    """
```

Remove the `ctrl+c` binding from `BINDINGS` (it moves to the app). The list becomes:

```python
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "prev_view", "prev view", priority=True),
        Binding("right", "next_view", "next view", priority=True),
        Binding("space", "toggle_tool", "toggle", priority=True),
        Binding("a", "select_all", "all"),
        Binding("i", "invert", "invert"),
        Binding("enter", "accept", "install selected", priority=True),
        Binding("q", "abort", "quit"),
    ]
```

Change the two exit calls to go through the app:

```python
    def action_accept(self) -> None:
        self.app.exit([tool.id for tool in self.tools if tool.id in self.selected])

    def action_abort(self) -> None:
        self.app.exit(None)
```

Everything else in the file (helpers, `compose`, `on_mount`, `_rebuild`, selection, detail) stays byte-for-byte the same.

- [ ] **Step 2: Create the `UnifiedApp` shell**

> **As-built note:** the snippet below is the planned shape; under Textual 8.2.7 + strict pyright the final code (in `installer/wizard_app.py`, the source of truth) diverged: the catalog is the app's *base screen* via `get_default_screen()` (not `install_screen` + `push_screen`), and accept/abort are delivered through a typed `CatalogScreen.Decided` message that `on_catalog_screen_decided` forwards to `App.exit(...)` (reading `self.app.exit` directly leaks `Unknown` under strict pyright). See the spec's Status note and Task 2's as-built note.

Create `installer/wizard_app.py`:

```python
"""Unified Textual shell hosting the wizard views behind one app.

Phase 1 of the unified-UI redesign. The app owns navigation and the screen
stack; the catalog is the only functional view. Execution stays behind the pure
`installer/` core invoked from `setup.py`; the app only collects the catalog
decision (`list[str] | None`).
"""

from collections.abc import Mapping
from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

from installer.catalog_tui import CatalogScreen
from installer.model import Tool


class UnifiedApp(App[list[str] | None]):
    """One app hosting the wizard views. run() returns the catalog selection
    (ids in catalog order) on accept, or None when aborted. `current_view` and
    `catalog` are public for headless tests."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "abort", "quit", show=False, priority=True),
    ]

    def __init__(
        self,
        tools: list[Tool],
        installed: Mapping[str, bool],
        blurbs: Mapping[str, str],
    ) -> None:
        super().__init__()
        self._catalog = CatalogScreen(tools, installed, blurbs)
        self.current_view = "catalog"

    @property
    def catalog(self) -> CatalogScreen:
        return self._catalog

    def on_mount(self) -> None:
        self.install_screen(self._catalog, name="catalog")
        self.push_screen("catalog")

    def action_abort(self) -> None:
        self.exit(None)
```

- [ ] **Step 3: Point `setup.py` at the new app**

In `setup.py`, replace the catalog import:

```python
from installer.wizard_app import UnifiedApp
```

(remove the `from installer.catalog_tui import CatalogApp` line)

and update `_select_catalog`:

```python
def _select_catalog(tools: list[Tool]) -> list[str] | None:
    installed = {tool.id: is_installed(tool) for tool in tools}
    return UnifiedApp(tools, installed, load_categories(_REGISTRY)).run()
```

- [ ] **Step 4: Migrate the existing async catalog tests to the new entry points**

In `tests/test_catalog_tui.py`, add the import:

```python
from installer.wizard_app import UnifiedApp
```

and change the import line to keep only the pure helpers from the module:

```python
from installer.catalog_tui import group_tools, sort_for_table
```

Apply these exact substitutions across the whole file (they are mechanical — the behavior under test is unchanged):

- `CatalogApp(` → `UnifiedApp(`  (every construction: `_app()`, the two `_wide_catalog` tests, and `CatalogApp([], {}, {})`)
- `app: CatalogApp` → `app: UnifiedApp`  (the `_screen_text` and `_app` type hints)
- `app.view` → `app.catalog.view`
- `app.selected` → `app.catalog.selected`
- `app.detail_text` → `app.catalog.detail_text`
- `app.table_sort` → `app.catalog.table_sort`
- `app.on_data_table_header_selected(` → `app.catalog.on_data_table_header_selected(`

Leave unchanged: `app.return_value`, `app.is_running`, `app.query_one(DataTable[Any])`, `app.export_screenshot()`, and `pilot.*`.

- [ ] **Step 5: Run the full suite to verify the refactor is behavior-preserving**

Run: `make validate && make test`
Expected: all green, 100% coverage retained. (`make validate` also confirms `App` is no longer an unused import in `catalog_tui.py`.)

- [ ] **Step 6: Commit**

```bash
git add installer/catalog_tui.py installer/wizard_app.py setup.py tests/test_catalog_tui.py
git commit -m "refactor: host the catalog in a UnifiedApp shell screen

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Placeholder views + `show_view` dispatch + direct key bindings + disable default palette

**Files:**
- Modify: `installer/wizard_app.py`
- Create: `tests/test_wizard_app.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_wizard_app.py`:

```python
from collections.abc import Mapping

from installer.model import Method, Tool
from installer.wizard_app import VIEW_ORDER, UnifiedApp


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


def _app() -> UnifiedApp:
    tools = [_tool("rg"), _tool("fd")]
    installed: Mapping[str, bool] = {"rg": True, "fd": False}
    return UnifiedApp(tools, installed, {"search": "find things"})


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
        assert "coming in Phase 2" in str(app.screen.query_one("#placeholder", Label).content)
        await pilot.press("3")
        assert app.current_view == "fix"
        await pilot.press("4")
        assert app.current_view == "uninstall"
        await pilot.press("5")
        assert app.current_view == "policies"
        await pilot.press("1")
        assert app.current_view == "catalog"


async def test_navigating_to_the_current_view_is_a_no_op() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("1")  # already on catalog
        assert app.current_view == "catalog"
        assert app.is_running
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_wizard_app.py -v`
Expected: FAIL (`ImportError: cannot import name 'VIEW_ORDER'`, and `ENABLE_COMMAND_PALETTE` is the Textual default `True`).

- [ ] **Step 3: Add placeholders, the registry, dispatch, and key bindings**

Edit `installer/wizard_app.py`. Extend the imports:

```python
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Label
```

Add the view registry and placeholder text above the classes:

```python
# Navigation order shared by every route, so the palette and the direct 1..N key
# bindings expose exactly the same views in the same order.
VIEW_ORDER: tuple[str, ...] = ("catalog", "doctor", "fix", "uninstall", "policies")
_PLACEHOLDER_TEXT = {
    "doctor": "Doctor — coming in Phase 2",
    "fix": "Fix — coming in Phase 2",
    "uninstall": "Uninstall — coming in Phase 3",
    "policies": "Policies — coming in Phase 4",
}


class PlaceholderScreen(Screen[None]):
    """A navigable stand-in for a view whose body lands in a later phase."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        yield Middle(Center(Label(self._message, id="placeholder")))
```

On `UnifiedApp`, disable the default palette and add the direct key bindings:

```python
    ENABLE_COMMAND_PALETTE = False  # replace Textual's dead-ending default palette
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "abort", "quit", show=False, priority=True),
        *[
            Binding(str(i + 1), f"show('{name}')", name, priority=True)
            for i, name in enumerate(VIEW_ORDER)
        ],
    ]
```

Build the placeholders as instances and add the dispatch. **Note (foundation from Task 1):** the catalog is the app's *base screen* via `get_default_screen()` — it **cannot** be `switch_screen`-ed out. Navigation is a stack with the catalog at the bottom: always `[catalog]` or `[catalog, <one other view>]`. **As-built (Textual 8.2.7 + strict pyright):** `install_screen`/`switch_screen` are avoided entirely — their bare-`Screen` stubs leak `Unknown` under strict pyright (no suppressions allowed) — so placeholders are held as instances in `self._placeholders` (built in `__init__`) and navigated with `push_screen(instance)` / `pop_screen` only. There is no `on_mount`. The single source of truth is `installer/wizard_app.py`.

In `__init__`, build the placeholder instances:

```python
        self._placeholders: dict[str, Screen[None]] = {
            name: PlaceholderScreen(message) for name, message in _PLACEHOLDER_TEXT.items()
        }
```

Add the dispatch (push/pop instances; pop any overlay, then push the target unless it is the base catalog):

```python
    def show_view(self, name: str) -> None:
        if name == self.current_view:
            return
        if self.current_view != "catalog":
            self.pop_screen()
        if name != "catalog":
            self.push_screen(self._placeholders[name])
        self.current_view = name

    def action_show(self, name: str) -> None:
        self.show_view(name)
```

`current_view` tracks the **active screen/view** (distinct from `CatalogScreen.view`, which is the catalog's grouping). Task 1 left it set-but-unread; this task is its first reader.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "feat: placeholder views + direct-key navigation; disable default palette

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Our own command palette (`NavScreen`) on Ctrl+P — dual-route parity

**Files:**
- Modify: `installer/wizard_app.py`
- Modify: `tests/test_wizard_app.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_wizard_app.py`:

```python
from installer.wizard_app import NavScreen


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_wizard_app.py -v`
Expected: FAIL (`ImportError: cannot import name 'NavScreen'`).

- [ ] **Step 3: Add `NavScreen` and the Ctrl+P route**

Edit `installer/wizard_app.py`. Extend the widget imports:

```python
from textual.screen import ModalScreen, Screen
from textual.widgets import Label, ListItem, ListView
```

Add the palette labels next to `_PLACEHOLDER_TEXT`:

```python
_PALETTE_LABEL = {
    "catalog": "Catalog — pick tools to install",
    "doctor": "Doctor — audit your PATH",
    "fix": "Fix — wire PATH into your shells",
    "uninstall": "Uninstall — remove installed tools",
    "policies": "Policies — pip/npm ban and env tweaks",
}
```

Add the `NavScreen` class (after `PlaceholderScreen`):

```python
class NavScreen(ModalScreen[str | None]):
    """Our command palette: a modal list of views, dismissing the chosen one.

    Replaces Textual's default palette (disabled on the app), whose options
    dead-end by closing the screen. Selecting an item dismisses with the view
    name; Escape dismisses with None (no navigation).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    NavScreen { align: center middle; }
    NavScreen > ListView { width: 60; height: auto; border: round $accent; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(
            *[ListItem(Label(_PALETTE_LABEL[name]), id=name) for name in VIEW_ORDER]
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

Add the Ctrl+P binding to `UnifiedApp.BINDINGS` (insert after the `ctrl+c` line):

```python
        Binding("ctrl+p", "open_nav", "navigate", priority=True),
```

and add the open/callback handlers to `UnifiedApp`:

```python
    def action_open_nav(self) -> None:
        self.push_screen(NavScreen(), self._navigate)

    def _navigate(self, name: str | None) -> None:
        if name is not None:
            self.show_view(name)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "feat: Ctrl+P command palette routed through the same show_view dispatch

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Quick-win — initial cursor on the first selectable tool row

**Files:**
- Modify: `installer/catalog_tui.py`
- Modify: `tests/test_catalog_tui.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_catalog_tui.py`:

```python
async def test_cursor_starts_on_first_tool_row_not_a_section_header():
    app = _app()  # category view: rows are [#git, lazygit, #search, rg, fd]
    async with app.run_test(size=(100, 30)) as pilot:
        # The first selectable row (lazygit) is highlighted, so the first
        # `space` toggles a tool instead of being a silent no-op on a header.
        await pilot.press("space")
        assert app.catalog.selected == {"lazygit"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_catalog_tui.py::test_cursor_starts_on_first_tool_row_not_a_section_header -v`
Expected: FAIL — cursor starts on the `#git` section row, so `space` is a no-op and `selected` stays empty.

- [ ] **Step 3: Move the cursor to the first tool row on every rebuild**

In `installer/catalog_tui.py`, add a helper and call it at the end of `_rebuild`. Add the method (next to `_highlighted_tool`):

```python
    def _first_tool_row(self) -> int | None:
        table = self.query_one(DataTable[Any])
        for index, row_key in enumerate(table.rows):
            if row_key.value in self._by_id:  # tool rows key on the id; sections on "#title"
                return index
        return None
```

At the end of `_rebuild`, after the build loop and before `table.call_after_refresh(self._refresh_marks)`, add:

```python
        first_tool = self._first_tool_row()
        if first_tool is not None:
            table.move_cursor(row=first_tool)
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `uv run pytest tests/test_catalog_tui.py::test_cursor_starts_on_first_tool_row_not_a_section_header -v`
Expected: PASS.

- [ ] **Step 5: Update the existing tests whose start-cursor assumptions changed**

The cursor now starts on `lazygit` (row 1) instead of the `#git` header (row 0). Replace these four tests in `tests/test_catalog_tui.py`:

```python
async def test_space_ignores_section_rows():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("up")  # from lazygit onto the "git" section row
        await pilot.press("space")  # section row -> no-op
        assert app.catalog.selected == set()
        await pilot.press("down", "space")  # back to lazygit
        assert app.catalog.selected == {"lazygit"}
        await pilot.press("space")  # toggle off again
        assert app.catalog.selected == set()


async def test_select_all_and_invert():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        # cursor already starts on lazygit (the first tool row)
        await pilot.press("a")
        assert app.catalog.selected == {"rg", "fd", "lazygit"}
        # select-all must not reset the cursor or blank the detail bar
        assert "lazygit" in app.catalog.detail_text
        assert app.query_one(DataTable[Any]).cursor_row == 1
        await pilot.press("i")
        assert app.catalog.selected == set()
        await pilot.press("space", "i")  # space toggles lazygit ON; invert gives {rg, fd}
        assert app.catalog.selected == {"rg", "fd"}


async def test_detail_bar_follows_the_highlighted_row():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        # lazygit is highlighted on start: empty desc -> falls back to name
        assert "lazygit" in app.catalog.detail_text
        assert "P2" in app.catalog.detail_text
        assert "for you" in app.catalog.detail_text
        await pilot.press("up")  # onto the "git" section row
        assert app.catalog.detail_text == "git"


async def test_section_row_detail_shows_the_group_blurb():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("down")  # from lazygit onto the "search" section row
        assert app.catalog.detail_text == "search — Find files and code at speed"
```

(Delete the old `test_space_toggles_tool_rows_and_ignores_section_rows`; the new `test_space_ignores_section_rows` replaces it.)

- [ ] **Step 6: Run the full catalog suite**

Run: `uv run pytest tests/test_catalog_tui.py -v`
Expected: PASS (all, including the four updated tests).

- [ ] **Step 7: Commit**

```bash
git add installer/catalog_tui.py tests/test_catalog_tui.py
git commit -m "fix: start the catalog cursor on the first selectable tool row

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Quick-win — empty-selection guard

**Files:**
- Modify: `installer/catalog_tui.py`
- Modify: `tests/test_catalog_tui.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_catalog_tui.py`:

```python
async def test_enter_with_empty_selection_is_a_no_op():
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")  # nothing selected
        assert app.is_running  # did not exit / return a selection
        assert "Select at least one tool" in app.catalog.status_text


async def test_empty_catalog_enter_is_blocked_then_aborts():
    app = UnifiedApp([], {}, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")  # no tools -> blocked, must not crash
        assert app.is_running
        await pilot.press("q")
    assert app.return_value is None
```

Also delete the obsolete `test_empty_catalog_is_safe` (it asserted `return_value == []`, which the guard now forbids — the new `test_empty_catalog_enter_is_blocked_then_aborts` replaces it).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_catalog_tui.py::test_enter_with_empty_selection_is_a_no_op -v`
Expected: FAIL (`AttributeError: ... has no attribute 'status_text'`, and Enter currently exits with `[]`).

- [ ] **Step 3: Add the `#status` line and guard `action_accept`**

In `installer/catalog_tui.py`:

Add a `status_text` field in `__init__` (next to `self.detail_text = ""`):

```python
        self.status_text = ""
```

Add a status line to `DEFAULT_CSS` (inside the existing block). **Use the id `status-line`, NOT `status`** — `status` is already the id of the Status grouping Tab (tab ids are the `VIEWS` names), so reusing it makes `query_one("#status")` ambiguous and breaks `test_clicking_a_tab_switches_view`:

```python
    #status-line { dock: bottom; height: 1; padding: 0 1; color: $warning; }
```

Yield it in `compose`, right after the `#legend` Static:

```python
        yield Static("", id="status-line")
```

Replace `action_accept`:

```python
    def action_accept(self) -> None:
        chosen = [tool.id for tool in self.tools if tool.id in self.selected]
        if not chosen:
            self.status_text = "Select at least one tool, or press q to quit."
            self.query_one("#status-line", Static).update(Text(self.status_text, style="yellow"))
            return
        self.app.exit(chosen)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_catalog_tui.py -v`
Expected: PASS (including `test_enter_returns_selection_in_catalog_order`, which selects `a` first so `chosen` is non-empty).

- [ ] **Step 5: Commit**

```bash
git add installer/catalog_tui.py tests/test_catalog_tui.py
git commit -m "fix: empty catalog selection is a guided no-op, never an exit

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Docs, memory, and the full gate

**Files:**
- Modify: `README.md`
- Modify: `Makefile` (only if a target's help text names the catalog screen)
- Modify: `/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md`

- [ ] **Step 1: Update the README**

Read `README.md` and find where the interactive selection / catalog is described. Update that prose to describe the single Textual app: one app hosting the catalog plus navigable doctor/fix/uninstall/policies placeholders, with Ctrl+P opening our command palette and number keys `1`–`5` switching views. Do not document the deferred views as functional — they are placeholders in this phase.

- [ ] **Step 2: Update the Makefile help text if needed**

Run: `grep -n "catalog\|wizard\|CatalogApp" Makefile`
If any target's help text refers to the old catalog screen by name, update the wording to "the unified wizard app". If there are no such references, make no change.

- [ ] **Step 3: Update the roadmap memory**

Read `/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md` and mark unified-UI Phase 1 (shell + dual-route navigation + the three quick-wins) as landed, leaving Phases 2–4 as pending. Keep it to one or two lines, consistent with the file's existing style.

- [ ] **Step 4: Run the full gate on the final tree**

Run: `make validate && make test`
Expected: all green; 100% coverage on `installer/` (verify `installer/wizard_app.py` reports 100%).

- [ ] **Step 5: Commit**

```bash
git add README.md Makefile
git commit -m "docs: describe the unified wizard app and Ctrl+P navigation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(Adjust the staged paths to exactly what changed; the memory file lives outside the repo and is not committed.)

---

## Self-Review

**Spec coverage:**
- "Shell pattern: Textual Screens" → Task 1 (`CatalogScreen` + `UnifiedApp`).
- "Future views are navigable placeholders" → Task 2 (`PlaceholderScreen`, installed for all four).
- "Return contract stays `list[str] | None`" → Task 1 (`UnifiedApp(App[list[str] | None])`; accept/abort via `self.app.exit`).
- "CLI flags keep current behavior" → Task 1 only changes `_select_catalog`; the `--doctor/--fix/...` branches in `setup.py:main` are untouched.
- "Disable Textual's default palette" → Task 2 (`ENABLE_COMMAND_PALETTE = False`, asserted).
- "Our palette + direct keys through one dispatch" → Tasks 2–3 (`show_view` is the only mutator; `action_show` and `_navigate` both call it; parity asserted in `test_palette_and_key_resolve_to_the_same_view`).
- "Initial cursor on first selectable tool row" → Task 4.
- "Empty-selection guard, never proceeds to a policy prompt" → Task 5 (Enter never returns `[]`; the only empty exit is `None` via `q`/Ctrl+C, which `setup.py` already maps to "Aborted." before any ban prompt).
- "Ctrl+C aborts from any screen" → Task 1 (app-level priority binding), exercised by the migrated `test_ctrl_c_aborts_with_none` and reachable from placeholders (app binding).
- "Headless tests; 100% core retained" → every task ends on `make test`; coverage note calls out `wizard_app.py`.

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output.

**Type consistency:** `show_view(name: str)`, `action_show(name: str)`, `_navigate(name: str | None)`, `catalog -> CatalogScreen`, `current_view: str`, `status_text: str`, `_first_tool_row() -> int | None` are used consistently across tasks and tests. `UnifiedApp(App[list[str] | None])` matches `CatalogScreen(Screen[list[str] | None])` and `setup.py`'s `list[str] | None` return. `VIEW_ORDER`, `_PLACEHOLDER_TEXT`, `_PALETTE_LABEL` share the same five view names.

**Risk to watch during execution:** the four `tests/test_catalog_tui.py` tests updated in Task 4 depend on the exact category-view row order (`#git, lazygit, #search, rg, fd`) from the `_catalog()` fixture — if a step is implemented out of order, re-confirm that fixture before adjusting cursor assertions.
