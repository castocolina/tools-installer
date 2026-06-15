# Unified UI — Shared Pattern & Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all five views obey one wayfinding contract and share a single browsable-list component — fixing the navigation dead-end on Doctor/Fix and turning Uninstall into a catalog-parity view with removability annotations — while net-reducing UI code.

**Architecture:** Three independently-shippable phases. (1) Promote quit/back/nav to app-level bindings and give Doctor/Fix a Footer — stops the user-stranding bug with no refactor. (2) Introduce an `AppScreen` base scaffold (`WayfindingHeader` + body + `StatusLine` + `Footer`) that every screen yields, and extract the duplicated status/summary/mark/highlight helpers into one module — deleting `PlaceholderScreen` and the divergent copies. (3) Extract the catalog's browser into a reusable `ToolBrowser` widget, classify removability in the pure `uninstall` core, and rebuild Uninstall as full catalog parity (all tools, annotated removable-here vs managed-elsewhere vs not-installed) reusing that widget; migrate Policies onto the scaffold.

**Tech Stack:** Python (uv-managed), Textual 8.2.7, pytest + pytest-asyncio (`asyncio_mode=auto`), pyright strict (no suppressions), 100% coverage on `installer/`.

**Decisions baked in (from design + owner):** Uninstall = full catalog parity with disabled/hinted rows for not-installed/unavailable. Dependencies are OUT of scope — only a no-op `Tool.requires=()` seam + a detail-bar slot are added here; the real feature lives in `docs/prds/tool-dependencies-v1.0-prd.md`. Preserve: green/yellow/red severity vocabulary, `space`=select / `enter`=commit split, `●/○` policy glyph, the one-deep push/pop stack invariant, the `list[str] | None` run value, and live-apply via injected closures.

**Testing notes (learned in earlier phases):**
- Headless: `async with app.run_test(size=(120, 40)) as pilot: await pilot.press(...)`. Screens expose public seams (e.g. `status_text`, `active_state`) for assertions.
- Textual SVG screenshots NBSP-encode spaces (`&#160;`/`\xa0`); decode with `html.unescape(text).replace(chr(160), " ")` before substring checks.
- Query a parametrized table with `query_one(DataTable[Any])` (bare `DataTable` trips `reportUnknownVariableType`).
- IDE pyright diagnostics that say "import could not be resolved" are SPURIOUS (the IDE ignores the uv venv). The real gate is `uv run pyright` (and `make validate`). `setup.py` is pyright-excluded and untested by design.
- `q`/quit on a screen during `run_test` exits the app; assert via `app.return_value is None` and `not app.is_running`.

---

## File Structure

**Create:**
- `installer/ui_common.py` — shared UI primitives: `SEVERITY_STYLE` map, `severity_style(name)`, `mark(chosen)`, `multiline_summary(parts)`, `highlighted_key(table)`, `StatusLine` widget, `WayfindingHeader` widget, `AppScreen` base `Screen`.
- `installer/tool_browser.py` — `ToolBrowser` widget extracted from `CatalogScreen` (grouping `Tabs` + `DataTable` + detail bar + legend + marks + section rows + highlight→detail), parameterized by a row-adapter, accent, legend, and selectability.
- `tests/test_ui_common.py`, `tests/test_tool_browser.py`.

**Modify:**
- `installer/wizard_app.py` — app-level bindings (`q`, `esc`); migrate `DoctorScreen`/`FixScreen`/`UninstallScreen`/`PoliciesScreen` onto `AppScreen`; rebuild `UninstallScreen` on `ToolBrowser`; delete `PlaceholderScreen`.
- `installer/catalog_tui.py` — `CatalogScreen` mounts `ToolBrowser` + extends `AppScreen`; delete the now-extracted code.
- `installer/uninstall.py` — add removability classification over ALL tools.
- `installer/model.py` — add no-op `Tool.requires: tuple[str, ...] = ()` seam + parse in `load_tools`.
- `installer/render.py` — re-export severity styling from `ui_common` (single source).
- `setup.py` — build the full annotated tool list for Uninstall (reuse the `is_installed` map already computed for the catalog).
- `tests/test_wizard_app.py`, `tests/test_catalog_tui.py`, `tests/test_uninstall.py`, `tests/test_uninstall_e2e.py`, `tests/test_policies_e2e.py` — update for the new structure.

**Delete:**
- `PlaceholderScreen` class (`wizard_app.py:67-75`) + `test_placeholder_screen_renders_message` (`tests/test_wizard_app.py`).
- Duplicated helpers absorbed by `ui_common`: per-screen `_set_status`/`_clear_status`, `_mark`, `_applied_summary`/`_summary` join logic, `_highlighted_*`.

---

# PHASE 1 — Wayfinding emergency fix (Blocker, ships alone)

**Outcome:** Every screen shows a Footer with nav, and `q` quits / `esc` returns to catalog from every view. No refactor. This phase alone resolves the reported "I get lost on Doctor, even `q` doesn't work."

### Task 1.1: Promote `q` (quit) and `esc` (back) to app-level bindings

**Files:**
- Modify: `installer/wizard_app.py` (`UnifiedApp.BINDINGS` ~:475-482; add `action_back`; `_navigable` ~:540-546; `action_abort` ~:565)
- Test: `tests/test_wizard_app.py`

- [ ] **Step 1: Write the failing tests**

```python
async def test_q_quits_from_every_pushed_view() -> None:
    """q must quit from any view, not just the catalog (regression: q was
    bound only on CatalogScreen, so non-catalog views had no working quit)."""
    for view in ("doctor", "fix", "uninstall", "policies"):
        app = _app(initial_view=view)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("q")
        assert not app.is_running
        assert app.return_value is None


async def test_esc_returns_to_catalog_from_a_pushed_view() -> None:
    """esc is the one-deep 'back': from any sub-view it pops to the catalog."""
    app = _app(initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.current_view == "doctor"
        await pilot.press("escape")
        assert app.current_view == "catalog"
        assert app.is_running  # esc goes back, does not quit


async def test_esc_on_catalog_is_inert() -> None:
    """On the base catalog there is nowhere to go back to; esc must not quit."""
    app = _app(initial_view="catalog")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("escape")
        assert app.current_view == "catalog"
        assert app.is_running
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_wizard_app.py -k "q_quits or esc_returns or esc_on_catalog" -q`
Expected: FAIL (`q`/`escape` not handled at app level; app stays running or wrong view).

- [ ] **Step 3: Add the bindings and `action_back`**

In `UnifiedApp.BINDINGS` (`wizard_app.py:475-482`), add two shown bindings alongside the existing `ctrl+c`/`ctrl+p`/number keys:

```python
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "abort", "quit", show=False, priority=True),
        Binding("q", "abort", "quit", show=True, priority=True),
        Binding("escape", "back", "back", show=True, priority=True),
        Binding("ctrl+p", "open_nav", "navigate", priority=True),
        *[
            Binding(str(i + 1), f"show('{name}')", name, priority=True)
            for i, name in enumerate(VIEW_ORDER)
        ],
    ]
```

Add the action method (near `action_show`):

```python
    def action_back(self) -> None:
        # One-deep stack: from a pushed view, go home to the catalog; on the
        # catalog itself there is nowhere further back, so esc is inert.
        if self._navigable() and self.current_view != "catalog":
            self.show_view("catalog")
```

- [ ] **Step 4: Guard against the NavScreen modal swallowing/duplicating keys**

`q`/`esc` are `priority=True` App bindings. `NavScreen` (the Ctrl+P palette) already binds `escape`→`cancel` (`wizard_app.py:451-452`). Confirm precedence: the modal's own `escape` closes the palette (its binding wins while it is focused), and `q` while the palette is open must NOT quit underneath it. Add a test:

```python
async def test_q_does_not_quit_while_nav_palette_open() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("q")  # must be inert under the modal
        assert app.is_running
        assert isinstance(app.screen, NavScreen)
```

If this fails (the priority App `q` fires under the modal), gate `action_abort` on `self._navigable()` so it no-ops while a modal is on top:

```python
    def action_abort(self) -> None:
        if not self._navigable():
            return
        self.exit(None)
```

(Keep `ctrl+c` working unconditionally as the hard abort — leave its existing handler path; only the new visible `q` routes through the guarded `action_abort`. If `ctrl+c` shares `action_abort`, verify a `ctrl+c`-aborts-from-palette test still passes; if not, give `ctrl+c` its own unguarded `action_hard_abort`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -k "q_quits or esc_returns or esc_on_catalog or q_does_not_quit or ctrl_c" -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "feat: app-level q/esc so quit and back work on every view

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 1.2: Add a Footer to Doctor and Fix

**Files:**
- Modify: `installer/wizard_app.py` (`DoctorScreen.compose` ~:97-98, `FixScreen.compose` ~:124-125)
- Test: `tests/test_wizard_app.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_doctor_and_fix_render_a_footer() -> None:
    """Pushed views hide the catalog's top Tabs strip, so each MUST yield a
    Footer or the app-level nav keys (1-5, ctrl+p, q, esc) are invisible and
    the user is stranded (regression: Doctor/Fix shipped without a Footer)."""
    from textual.widgets import Footer

    for view, screen_cls in (("doctor", DoctorScreen), ("fix", FixScreen)):
        app = _app(initial_view=view)
        async with app.run_test(size=(100, 30)):
            assert isinstance(app.screen, screen_cls)
            assert len(app.screen.query(Footer)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wizard_app.py::test_doctor_and_fix_render_a_footer -q`
Expected: FAIL (`len(... query(Footer)) == 0`).

- [ ] **Step 3: Add `yield Footer()` to both compose methods**

`DoctorScreen.compose` (`wizard_app.py:97-98`):

```python
    def compose(self) -> ComposeResult:
        yield Static(id="doctor-body")
        yield Footer()
```

`FixScreen.compose` (`wizard_app.py:124-125`):

```python
    def compose(self) -> ComposeResult:
        yield Static(id="fix-body")
        yield Footer()
```

(`Footer` is already imported in `wizard_app.py` — used by Uninstall/Policies.)

- [ ] **Step 4: Run the full wizard suite to verify pass + no regression**

Run: `uv run pytest tests/test_wizard_app.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "fix: render a Footer on Doctor and Fix so nav is visible

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 1.3: Validate Phase 1

- [ ] **Step 1:** Run `make validate && make test`. Expected: clean, 100% coverage, all green.
- [ ] **Step 2:** Regenerate the audit screenshots and confirm Doctor/Fix now show a footer row with `q quit  esc back  ^p navigate  1 catalog … 5 policies`.

Run: `uv run python .e2e-artifacts/_capture_audit.py && python3 -c "import html,re,pathlib; t=html.unescape(' '.join(re.findall(r'<text[^>]*>(.*?)</text>', pathlib.Path('.e2e-artifacts/audit/04-doctor.svg').read_text()))).replace(chr(160),' '); print('q quit' in t, 'esc back' in t, 'navigate' in t)"`
Expected: `True True True`.

---

# PHASE 2 — Shared scaffold + consolidation (net-negative code)

**Outcome:** One `AppScreen` base (header + body + status + footer) every screen obeys; a `WayfindingHeader` shows "you are here" on all five views; the duplicated status/mark/summary/highlight helpers collapse into `installer/ui_common.py`; `PlaceholderScreen` is deleted. The Phase-1 footer fix becomes structural (a screen can no longer omit chrome).

### Task 2.1: `installer/ui_common.py` — severity styling, mark, summary, highlight

**Files:**
- Create: `installer/ui_common.py`
- Modify: `installer/render.py` (re-export `SEVERITY_STYLE`)
- Test: `tests/test_ui_common.py`

- [ ] **Step 1: Write the failing tests**

```python
from textual.coordinate import Coordinate
from installer.ui_common import SEVERITY_STYLE, mark, multiline_summary, severity_style


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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ui_common.py -q`
Expected: FAIL (`No module named installer.ui_common`).

- [ ] **Step 3: Implement the pure helpers**

```python
"""Shared UI primitives reused across the wizard screens: a single severity
color map, the checkbox mark, the multi-line summary join, and the
highlighted-row lookup. Extracting these removes three+ near-identical copies
that drifted across catalog_tui.py and wizard_app.py."""

from typing import Any

from rich.text import Text
from textual.coordinate import Coordinate
from textual.widgets import DataTable

SEVERITY_STYLE: dict[str, str] = {"ok": "green", "warn": "yellow", "error": "red"}


def severity_style(level: str) -> str:
    return SEVERITY_STYLE[level]


def mark(chosen: bool) -> Text:
    """The [x]/[ ] selection cell shared by the catalog and uninstall tables."""
    return Text("[x]" if chosen else "[ ]", style="green" if chosen else "")


def multiline_summary(parts: list[str]) -> str:
    """One line per outcome. A single joined line overflows terminal width and
    truncates trailing reload guidance, so outcomes are newline-separated."""
    return "\n".join(parts)


def highlighted_key(table: DataTable[Any]) -> str | None:
    """The row-key value under the cursor, or None on an empty table."""
    if table.row_count == 0:
        return None
    cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
    return cell_key.row_key.value
```

- [ ] **Step 4: Re-export from `render.py` (single source of truth)**

In `installer/render.py`, replace the private `_SEVERITY_STYLE` (`:77`) with an import from `ui_common` so the colors live in exactly one place:

```python
from installer.ui_common import SEVERITY_STYLE
# ... use SEVERITY_STYLE where _SEVERITY_STYLE was used; delete the old literal.
```

- [ ] **Step 5: Run tests + the render suite**

Run: `uv run pytest tests/test_ui_common.py tests/test_render.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add installer/ui_common.py installer/render.py tests/test_ui_common.py
git commit -m "refactor: extract severity/mark/summary/highlight into ui_common

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2.2: `StatusLine` widget

**Files:**
- Modify: `installer/ui_common.py`
- Test: `tests/test_ui_common.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_status_line_set_and_clear() -> None:
    """StatusLine.set stores the text + severity style; clear empties it. The
    default color is neutral (NOT $warning) — every call passes an explicit
    severity, so a warning-yellow default would mislabel success/error."""
    from textual.app import App, ComposeResult
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ui_common.py::test_status_line_set_and_clear -q`
Expected: FAIL (`cannot import name 'StatusLine'`).

- [ ] **Step 3: Implement `StatusLine`** (append to `ui_common.py`)

```python
from textual.widgets import Static


class StatusLine(Static):
    """A docked status line. Neutral by default; each set() colors by severity.
    Replaces the three near-identical _set_status/_clear_status pairs (and the
    divergent `color: $warning` defaults) in catalog/uninstall/policies."""

    DEFAULT_CSS = "StatusLine { height: auto; padding: 0 1; }"

    def __init__(self) -> None:
        super().__init__("")
        self.text = ""  # public test seam

    def set(self, text: str, severity: str) -> None:
        self.text = text
        self.update(Text(text, style=severity_style(severity)))

    def clear(self) -> None:
        self.text = ""
        self.update("")
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ui_common.py::test_status_line_set_and_clear -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/ui_common.py tests/test_ui_common.py
git commit -m "feat: StatusLine widget (neutral default, severity-colored set)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2.3: `WayfindingHeader` widget

**Files:**
- Modify: `installer/ui_common.py`; `installer/wizard_app.py` (export `VIEW_ORDER` + a label map usable by the header)
- Test: `tests/test_ui_common.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_wayfinding_header_highlights_active_view() -> None:
    """The header lists every view and marks the active one so the user always
    knows where they are (Nielsen #1)."""
    from textual.app import App, ComposeResult
    from installer.ui_common import WayfindingHeader

    class _Host(App[None]):
        def compose(self) -> ComposeResult:
            yield WayfindingHeader(active="doctor")

    app = _Host()
    async with app.run_test(size=(100, 5)):
        header = app.query_one(WayfindingHeader)
        rendered = header.render_text()  # public seam returning the plain string
        assert "Catalog" in rendered and "Doctor" in rendered and "Policies" in rendered
        # active view is bracketed; others are not
        assert "[Doctor]" in rendered
        assert "[Catalog]" not in rendered
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ui_common.py::test_wayfinding_header_highlights_active_view -q`
Expected: FAIL.

- [ ] **Step 3: Implement `WayfindingHeader`** (append to `ui_common.py`)

Use the labels already defined for the palette. Define an ordered list of `(view_key, Label)` in `ui_common` so both the header and the palette share one source (import `VIEW_ORDER` + `_PALETTE_LABEL` from `wizard_app`, or move that map into `ui_common` and have `wizard_app` import it — prefer moving the label map into `ui_common` to avoid a circular import).

```python
VIEW_LABELS: tuple[tuple[str, str], ...] = (
    ("catalog", "Catalog"),
    ("doctor", "Doctor"),
    ("fix", "Fix"),
    ("uninstall", "Uninstall"),
    ("policies", "Policies"),
)


class WayfindingHeader(Static):
    """Docked-top breadcrumb of the five views, active one bracketed/inverse.
    Accent recolors per screen (e.g. destructive red on uninstall)."""

    DEFAULT_CSS = "WayfindingHeader { height: 1; padding: 0 1; }"

    def __init__(self, *, active: str, accent: str = "$accent") -> None:
        super().__init__()
        self._active = active
        self._accent = accent

    def render_text(self) -> str:  # public test seam
        parts = [f"[{label}]" if key == self._active else label for key, label in VIEW_LABELS]
        return "tools-installer · " + "  ".join(parts)

    def on_mount(self) -> None:
        text = Text("tools-installer · ", style="dim")
        for key, label in VIEW_LABELS:
            if key == self._active:
                text.append(f"[{label}]  ", style=f"bold {self._accent}")
            else:
                text.append(f"{label}  ", style="dim")
        self.update(text)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ui_common.py::test_wayfinding_header_highlights_active_view -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/ui_common.py installer/wizard_app.py tests/test_ui_common.py
git commit -m "feat: WayfindingHeader breadcrumb with active-view marker

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2.4: `AppScreen` base scaffold

**Files:**
- Modify: `installer/ui_common.py`
- Test: `tests/test_ui_common.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_app_screen_yields_header_status_and_footer() -> None:
    """A subclass implements compose_body only; the scaffold guarantees header
    + status line + footer so chrome can never be omitted again."""
    from textual.app import App, ComposeResult
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ui_common.py::test_app_screen_yields_header_status_and_footer -q`
Expected: FAIL.

- [ ] **Step 3: Implement `AppScreen`** (append to `ui_common.py`)

```python
from abc import abstractmethod
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer


class AppScreen(Screen[None]):
    """Base scaffold: WayfindingHeader + the subclass body + StatusLine + Footer.
    Subclasses implement compose_body(); the chrome is guaranteed."""

    def __init__(self, *, view: str, accent: str = "$accent") -> None:
        super().__init__()
        self._view = view
        self._accent = accent
        self.status = StatusLine()

    @abstractmethod
    def compose_body(self) -> ComposeResult: ...

    def compose(self) -> ComposeResult:
        yield WayfindingHeader(active=self._view, accent=self._accent)
        yield from self.compose_body()
        yield self.status
        yield Footer()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ui_common.py::test_app_screen_yields_header_status_and_footer -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/ui_common.py tests/test_ui_common.py
git commit -m "feat: AppScreen base scaffold (header + body + status + footer)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2.5: Migrate Doctor, Fix, Policies onto `AppScreen`; delete `PlaceholderScreen`

**Files:**
- Modify: `installer/wizard_app.py` (`DoctorScreen`, `FixScreen`, `PoliciesScreen`); delete `PlaceholderScreen` (:67-75)
- Test: `tests/test_wizard_app.py` (delete `test_placeholder_screen_renders_message`; existing doctor/fix/policies tests must still pass)

- [ ] **Step 1: Migrate each screen** — change the base class to `AppScreen`, move the body into `compose_body`, and route status through `self.status`:
  - `DoctorScreen(AppScreen)` — `__init__` calls `super().__init__(view="doctor")`; `compose_body` yields `Static(id="doctor-body")`; keep `on_mount` guidance rendering. Remove the standalone `compose`/`Footer` from Task 1.2 (now provided by the scaffold).
  - `FixScreen(AppScreen)` — `super().__init__(view="fix")`; `compose_body` yields `Static(id="fix-body")`; keep the apply/error logic; `_refresh_body` stays.
  - `PoliciesScreen(AppScreen)` — `super().__init__(view="policies")`; `compose_body` yields the `DataTable`; replace the `#policies-status` `Static` + `_set_status` with `self.status.set(text, severity)` and the `_summary` join with `multiline_summary(...)`; keep `action_toggle_policy`, `active_state`, `●/○` glyph.
- [ ] **Step 2: Delete `PlaceholderScreen`** (`wizard_app.py:67-75`) and its test (`test_placeholder_screen_renders_message`). Remove `PlaceholderScreen` from the `tests/test_wizard_app.py` import list. Confirm no remaining references: `grep -rn PlaceholderScreen installer tests` returns nothing.
- [ ] **Step 3: Update `_set_status` call sites** — Policies tests asserting `screen.status_text` should now assert `screen.status.text` (the `StatusLine` seam). Update those assertions.
- [ ] **Step 4: Run the wizard suite**

Run: `uv run pytest tests/test_wizard_app.py -q`
Expected: PASS (doctor/fix/policies behavior unchanged; placeholder test gone).

- [ ] **Step 5: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "refactor: Doctor/Fix/Policies on AppScreen; delete PlaceholderScreen

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2.6: Migrate Uninstall onto `AppScreen` (status/summary/mark/highlight via ui_common)

**Files:**
- Modify: `installer/wizard_app.py` (`UninstallScreen`)
- Test: `tests/test_wizard_app.py`, `tests/test_uninstall_e2e.py`

- [ ] **Step 1:** Change `UninstallScreen(AppScreen)`; `super().__init__(view="uninstall", accent="red")`; `compose_body` yields the `DataTable` (the table redesign comes in Phase 3 — here only the scaffold migration). Replace `_set_status`/`_clear_status` with `self.status.set/clear`; replace local `_mark` with `ui_common.mark`; replace `_highlighted_key` with `ui_common.highlighted_key(self.query_one(DataTable[Any]))`; replace `_applied_summary`'s `"\n".join` with `multiline_summary(parts)`. Keep `action_remove`/select/invert logic and the ban/PATH pseudo-rows for now.
- [ ] **Step 2:** Update `tests/test_wizard_app.py` uninstall assertions from `screen.status_text` → `screen.status.text`. Update `tests/test_uninstall_e2e.py` snapshot helper if it referenced removed ids.
- [ ] **Step 3: Run**

Run: `uv run pytest tests/test_wizard_app.py tests/test_uninstall_e2e.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py tests/test_uninstall_e2e.py
git commit -m "refactor: Uninstall on AppScreen via shared ui_common helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2.7: Validate Phase 2

- [ ] **Step 1:** `make validate && make test` — clean, 100% coverage, green.
- [ ] **Step 2:** Regenerate audit screenshots; confirm all five views now show the `WayfindingHeader` with the active view bracketed and a consistent status line + footer.
- [ ] **Step 3:** Confirm net code reduction: `git diff --stat <phase2-base>..HEAD` should show `installer/` lines removed (deleted duplicates + `PlaceholderScreen`) roughly offsetting the new `ui_common.py`. Record the delta in the commit body if negative.

---

# PHASE 3 — ToolBrowser extraction + Uninstall catalog-parity redesign

**Outcome:** The catalog's browser becomes a reusable `ToolBrowser`. Uninstall is rebuilt as full catalog parity: every tool shown, annotated removable-here (selectable) / managed-elsewhere (inert + command hint) / not-installed (dim) / unavailable (dim), in a destructive accent. Policies optionally adopts the shared chrome. A no-op `Tool.requires` seam is added for the deps PRD.

### Task 3.1: Removability classification in the pure core

**Files:**
- Modify: `installer/uninstall.py`
- Test: `tests/test_uninstall.py`

Define a pure classifier over ALL tools (not just removable ones), reusing `plan_uninstall`, the platform resolver, and the `installed` map. States: `removable` (has on-disk userspace artifacts → selectable, paths), `managed` (installed but no userspace artifacts → inert + a method-aware command hint), `absent` (resolvable on this platform but not installed → inert, "not installed"), `unavailable` (no method applies to this platform → inert, "not available on <os>").

- [ ] **Step 1: Write the failing tests**

```python
from installer.model import Method, Tool
from installer.platform import Platform
from installer.uninstall import classify_tools, ToolRow


def _dl(tool_id: str) -> Tool:
    return Tool(id=tool_id, name=tool_id, category="c", cmd=tool_id,
        methods=(Method(kind="github_release",
            params={"repo": "a/b", "asset": "x", "member": tool_id}),))


def _brew(tool_id: str) -> Tool:
    return Tool(id=tool_id, name=tool_id, category="c", cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),))


def test_classify_removable_when_artifacts_on_disk(tmp_path) -> None:
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    (bin_dir / "fd").write_text("x")
    rows = classify_tools([_dl("fd")], bin_dir, installed={"fd": True}, platform=_LINUX)
    row = rows[0]
    assert row.state == "removable"
    assert row.paths  # non-empty, real artifacts
    assert row.selectable is True


def test_classify_managed_when_installed_without_artifacts(tmp_path) -> None:
    rows = classify_tools([_brew("jq")], tmp_path / "bin", installed={"jq": True}, platform=_MAC)
    row = rows[0]
    assert row.state == "managed"
    assert row.selectable is False
    assert "brew uninstall jq" in row.hint


def test_classify_absent_when_not_installed(tmp_path) -> None:
    rows = classify_tools([_dl("fd")], tmp_path / "bin", installed={"fd": False}, platform=_LINUX)
    assert rows[0].state == "absent"
    assert rows[0].selectable is False
    assert "not installed" in rows[0].hint
```

(Define `_LINUX`/`_MAC` `Platform` fixtures matching existing test helpers in `tests/test_uninstall.py`.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_uninstall.py -k classify -q`
Expected: FAIL (`cannot import name 'classify_tools'`).

- [ ] **Step 3: Implement `ToolRow` + `classify_tools`** in `installer/uninstall.py`

```python
from dataclasses import dataclass
from installer.model import Method, Tool
from installer.platform import Platform
from installer.resolver import resolve  # whichever picks applicable methods per platform


@dataclass(frozen=True)
class ToolRow:
    tool: Tool
    state: str            # "removable" | "managed" | "absent" | "unavailable"
    paths: list[Path]     # non-empty only when state == "removable"
    hint: str
    selectable: bool


def _manager_hint(tool: Tool) -> str:
    for method in tool.methods:
        if method.kind == "cask":
            return f"managed by Homebrew — `brew uninstall --cask {tool.cmd}`"
        if method.kind == "brew":
            return f"managed by Homebrew — `brew uninstall {tool.cmd}`"
    return "managed outside this installer — remove with your package manager"


def classify_tools(
    tools: list[Tool], default_bin_dir: Path, *, installed: dict[str, bool], platform: Platform
) -> list[ToolRow]:
    rows: list[ToolRow] = []
    for tool in tools:
        paths = plan_uninstall([tool], default_bin_dir)
        if paths:
            rows.append(ToolRow(tool, "removable", paths,
                "installed in userspace — removable here", True))
        elif installed.get(tool.id, False):
            rows.append(ToolRow(tool, "managed", [], _manager_hint(tool), False))
        elif _has_applicable_method(tool, platform):
            rows.append(ToolRow(tool, "absent", [], "not installed", False))
        else:
            rows.append(ToolRow(tool, "unavailable", [],
                f"not available on {platform.os}", False))
    return rows
```

Add `_has_applicable_method(tool, platform)` using the existing platform-resolution logic (mirror how the catalog/`resolve` decides a method applies — check `Method.os`/`arch` filters). Keep `removable_tools` as-is (Phase 2 callers still use it) or refactor callers to `classify_tools` + filter `state == "removable"` and delete `removable_tools` (prefer deletion if no other caller remains — confirm with `grep -rn removable_tools`).

- [ ] **Step 4: Run to verify pass + full uninstall suite**

Run: `uv run pytest tests/test_uninstall.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/uninstall.py tests/test_uninstall.py
git commit -m "feat: classify_tools — removable/managed/absent/unavailable rows

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3.2: Extract `ToolBrowser` widget from `CatalogScreen`

**Files:**
- Create: `installer/tool_browser.py`
- Modify: `installer/catalog_tui.py`
- Test: `tests/test_tool_browser.py`, `tests/test_catalog_tui.py`

This is a behavior-preserving extraction guarded by the existing catalog tests. Move the grouping `Tabs`, the `DataTable`, the detail bar, the legend, marks, section/group rows, the `_SORT_BY_COLUMN` table-sort, and the `RowHighlighted`→detail wiring (`catalog_tui.py:136-333`) into a `ToolBrowser(Widget)` parameterized by:
- `rows`: the data to render (a list of row models with id, columns, detail text, selectable, accent-state);
- `groupings`: which grouping tabs to show;
- `legend`: the legend markup;
- `selectable`: predicate per row (catalog: all P-rows; uninstall: only `state == "removable"`).

- [ ] **Step 1: Write a characterization test for the catalog through `ToolBrowser`** asserting the catalog still renders all groupings, marks toggle in place, the detail bar updates on highlight, and `enter` returns ids in catalog order. (Port the strongest existing assertions from `tests/test_catalog_tui.py`.)
- [ ] **Step 2: Run** — FAIL (`installer.tool_browser` missing).
- [ ] **Step 3: Move the code** from `catalog_tui.py:136-333` into `tool_browser.py` as `ToolBrowser`; have `CatalogScreen.compose_body` mount a `ToolBrowser` configured with the catalog's groupings/legend/adapter. Keep the row-adapter generic so uninstall can supply its own columns. Preserve the as-built gotchas: focus the `DataTable` on mount; `table.call_after_refresh(self._refresh_marks)` after `_rebuild` (stale render caches); short section keys in cell 0 with the blurb in the detail bar.
- [ ] **Step 4: Run the catalog suite** — `uv run pytest tests/test_catalog_tui.py tests/test_tool_browser.py -q` — PASS (behavior preserved).
- [ ] **Step 5: Commit**

```bash
git add installer/tool_browser.py installer/catalog_tui.py tests/test_tool_browser.py tests/test_catalog_tui.py
git commit -m "refactor: extract ToolBrowser widget from CatalogScreen

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3.3: Rebuild Uninstall as catalog-parity on `ToolBrowser`

**Files:**
- Modify: `installer/wizard_app.py` (`UninstallScreen`, `UninstallInputs`), `setup.py`
- Test: `tests/test_wizard_app.py`, `tests/test_uninstall_e2e.py`

- [ ] **Step 1: Write the failing tests** asserting:
  - the uninstall table lists ALL classified tools (removable + managed + absent), not only removable ones;
  - `managed`/`absent`/`unavailable` rows render dimmed, are NOT selectable (pressing `space` on them is inert), and show their hint in the detail bar;
  - `removable` rows toggle and `enter` removes only the selected removable artifacts (+ ban/PATH env rows);
  - the destructive accent is present (header `accent="red"`).

```python
async def test_uninstall_lists_all_tools_with_states() -> None:
    rows = [
        ToolRow(_tool("fd"), "removable", [Path("/x/fd")], "removable here", True),
        ToolRow(_tool("jq"), "managed", [], "managed by Homebrew — `brew uninstall jq`", False),
        ToolRow(_tool("rg"), "absent", [], "not installed", False),
    ]
    app = _app(uninstall=_uninstall_inputs(rows=rows), initial_view="uninstall")
    async with app.run_test(size=(120, 40)) as pilot:
        table = app.screen.query_one(DataTable[Any])
        assert table.row_count >= 3  # all states shown
        # selecting a managed row is inert
        await pilot.press("space")  # cursor starts on a selectable row; move to jq first in real test
        # ... assert jq not in selected
```

- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3:** Change `UninstallInputs` to carry `rows: list[ToolRow]` (+ the ban/PATH env inputs + the `remove` closure). `UninstallScreen` mounts a `ToolBrowser` with an uninstall adapter (columns: `Sel · Tool · Cat · Installed via · What gets removed`), `accent="red"`, `selectable=lambda row: row.state == "removable"`. Non-selectable rows render dimmed with the hint; the detail bar shows the per-row hint. Keep the `environment` group (ban + PATH) as a section. `action_remove` collects paths from selected `removable` rows + env toggles, unchanged otherwise.
- [ ] **Step 4:** In `setup.py`, build `rows = classify_tools(load_tools(_REGISTRY), _DEFAULT_BIN_DIR, installed=<reuse catalog map>, platform=detect())` and pass into `UninstallInputs`. Reuse the `installed` map already computed for the catalog (avoid a second `is_installed` sweep).
- [ ] **Step 5: Run** — `uv run pytest tests/test_wizard_app.py tests/test_uninstall_e2e.py -q` — PASS.
- [ ] **Step 6: Commit**

```bash
git add installer/wizard_app.py setup.py tests/test_wizard_app.py tests/test_uninstall_e2e.py
git commit -m "feat: Uninstall as catalog-parity view with removability states

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3.4: `Tool.requires` no-op seam + detail-bar slot

**Files:**
- Modify: `installer/model.py` (`Tool` + `load_tools`), `installer/tool_browser.py` (detail-bar slot)
- Test: `tests/test_model.py`, `tests/test_tool_browser.py`

- [ ] **Step 1: Write the failing test**

```python
def test_tool_requires_defaults_empty_and_parses(tmp_path) -> None:
    from installer.model import load_tools
    # a registry row with `requires = ["volta"]` parses into the tuple;
    # a row without it defaults to ().
    tools = load_tools(_REGISTRY)
    assert all(isinstance(t.requires, tuple) for t in tools)
```

- [ ] **Step 2: Run** — FAIL (`Tool` has no `requires`).
- [ ] **Step 3:** Add `requires: tuple[str, ...] = ()` to the `Tool` dataclass and parse `tuple(row.get("requires", []))` in `load_tools`. No resolution logic. In `ToolBrowser`'s detail bar, render a `requires: X, Y` line only when `tool.requires` is non-empty (so the slot exists for the deps PRD without changing layout when empty).
- [ ] **Step 4: Run** — `uv run pytest tests/test_model.py tests/test_tool_browser.py -q` — PASS.
- [ ] **Step 5: Commit**

```bash
git add installer/model.py installer/tool_browser.py tests/test_model.py tests/test_tool_browser.py
git commit -m "feat: Tool.requires no-op seam + detail-bar slot for deps PRD

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3.5: (Optional) Migrate Policies fully onto `ToolBrowser`

Only if it reduces code without fighting the framework. Policies is a 1-row table; if the `ToolBrowser` adapter doesn't fit its `enter`-only immediate-toggle model cleanly, leave Policies on `AppScreen` + a plain `DataTable` (already consistent after Phase 2). Decide during implementation; do NOT force it. If skipped, note why in the commit/PR.

### Task 3.6: Validate Phase 3 + whole-feature review

- [ ] **Step 1:** `make validate && make test` — clean, 100% coverage, green.
- [ ] **Step 2:** Regenerate audit screenshots; confirm Uninstall shows all tools with states/hints, destructive accent, detail bar, and the wayfinding header — visually a catalog sibling.
- [ ] **Step 3:** Run the agent-driven E2E safety gate (real `~/.zshrc`/`~/.bashrc`/`~/.myshellrc` + `~/.local/bin` byte-identical before/after the full suite) and a `ui-ux-designer` end-user pass on the new Uninstall.
- [ ] **Step 4:** Whole-branch code review (`requesting-code-review`) before finishing the branch.

---

## Self-Review (completed during authoring)

**Spec coverage:** Wayfinding dead-end → Phase 1 (1.1, 1.2). "You are here" → 2.3. Quit/back model → 1.1. Status/mark/summary/highlight duplication → 2.1, 2.2, 2.6. `PlaceholderScreen` deletion → 2.5. ToolBrowser reuse (catalog↔uninstall) → 3.2, 3.3. Uninstall full-parity + removability hints → 3.1, 3.3. Dependencies deferred + seam → 3.4 (feature itself in `docs/prds/tool-dependencies-v1.0-prd.md`). Severity-color single source → 2.1. Net-negative code → 2.7 measured.

**Placeholder scan:** Task 3.2 (ToolBrowser extraction) and 3.3 (uninstall adapter) cite exact source ranges to relocate rather than re-pasting hundreds of lines — these are relocations of known, test-guarded code, not TODOs. Every NEW unit (helpers, `StatusLine`, `WayfindingHeader`, `AppScreen`, `classify_tools`, `ToolRow`) has complete code. The catalog characterization test in 3.2 must port concrete assertions from the existing `tests/test_catalog_tui.py` (named there).

**Type consistency:** `StatusLine.set(text, severity)`, `.clear()`, `.text`; `AppScreen.__init__(*, view, accent)`, `compose_body()`; `WayfindingHeader(active=, accent=)`, `.render_text()`; `classify_tools(tools, default_bin_dir, *, installed, platform) -> list[ToolRow]`; `ToolRow(tool, state, paths, hint, selectable)`; `mark(chosen)`, `multiline_summary(parts)`, `highlighted_key(table)`, `severity_style(level)`. Used consistently across tasks.

**Open implementation choices flagged for the implementer:** (a) whether `ctrl+c` shares `action_abort` or needs an unguarded `action_hard_abort` (1.1 step 4); (b) whether `removable_tools` is deleted or kept after `classify_tools` lands (3.1 step 3); (c) whether Policies adopts `ToolBrowser` (3.5). Each has a decision rule in-task.
