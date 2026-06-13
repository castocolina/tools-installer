# Unified UI Phase 2 — Doctor/Fix Guidance + Views — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn doctor/fix from raw state reporters into guides — a pure guidance core feeds both the console renderer and two new in-app Screens (read-only Doctor, live-applying Fix).

**Architecture:** A new pure `installer/guidance.py` maps each PATH/guard finding type to a `Guidance(title, meaning, next_step, severity)`. `render.py` renders those to the console (color by severity); `wizard_app.py` renders them into a read-only `DoctorScreen` and a `FixScreen` whose Apply binding runs the injected `configure_path` closure live, in place. `setup.py` (the IO boundary) composes the report/guard data + fix closure and opens the app on the doctor/fix view for `--doctor`/`--fix`. The app's return contract stays `list[str] | None` — the fix mutates the filesystem directly, so no typed outcome is pulled forward.

**Tech Stack:** Python 3 (uv), Textual ≥8, rich, pytest + pytest-asyncio (asyncio_mode=auto), pyright strict.

**Spec:** `docs/superpowers/specs/2026-06-13-unified-ui-phase2-design.md`

---

## File Structure

- **Create** `installer/guidance.py` — pure finding→guidance mapping (no IO, no rich/Textual). One responsibility: the wording + severity for every finding type.
- **Create** `tests/test_guidance.py` — unit tests, one per finding type.
- **Modify** `installer/render.py` — `render_doctor` drops its `hint` param and renders `doctor_guidance`; `render_guard_status` renders `guard_guidance`; new shared `guidance_text(items) -> Text`.
- **Modify** `installer/app.py` — `run_doctor` drops its `hint` param.
- **Modify** `installer/wizard_app.py` — `DoctorScreen` + `FixScreen` replace the doctor/fix placeholders; `_placeholders` becomes `_views`; constructor gains report/guard/fix data + `initial_view`.
- **Modify** `setup.py` — compose the data + fix closure; open the app on doctor/fix for the flags (IO boundary, coverage/pyright-excluded).
- **Modify** `tests/test_render.py`, `tests/test_app.py`, `tests/test_wizard_app.py` — adjust to the new signatures + screens.

Conventions to follow (already in the codebase):
- Tests build a `Console(file=io.StringIO(), width=100, no_color=True)` (see `tests/test_render.py:30`) or `Console(record=True)`.
- Textual screen tests use `async ... app.run_test(size=(100, 30))` and assert on labels/structure (see `tests/test_wizard_app.py`).
- 100% coverage on `installer/`; `setup.py` is the excluded IO boundary.

---

## Task 1: Guidance core (`installer/guidance.py`)

**Files:**
- Create: `installer/guidance.py`
- Test: `tests/test_guidance.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_guidance.py
from pathlib import Path

from installer.doctor import DoctorReport
from installer.guidance import Guidance, doctor_guidance, guard_guidance


def test_healthy_report_yields_a_single_ok_item() -> None:
    items = doctor_guidance(DoctorReport(missing=(), broken=(), duplicated=()))
    assert len(items) == 1
    assert items[0].severity == "ok"
    assert "healthy" in items[0].title.lower()
    assert items[0].next_step == ""  # nothing to do


def test_broken_dir_is_an_error_with_meaning_and_next_step() -> None:
    items = doctor_guidance(DoctorReport(missing=(), broken=(Path("/c/bin"),), duplicated=()))
    item = next(i for i in items if "/c/bin" in i.title)
    assert item.severity == "error"
    assert item.meaning and item.next_step
    assert "/c/bin" in item.meaning


def test_missing_dir_warns_and_points_at_make_fix() -> None:
    items = doctor_guidance(DoctorReport(missing=(Path("/a/bin"),), broken=(), duplicated=()))
    item = next(i for i in items if "/a/bin" in i.title)
    assert item.severity == "warn"
    assert "make fix" in item.next_step
    assert "new terminal" in item.next_step or "source" in item.next_step


def test_duplicated_dir_warns_and_says_duplicates_clear_on_reload() -> None:
    items = doctor_guidance(DoctorReport(missing=(), broken=(), duplicated=(Path("/b/bin"),)))
    item = next(i for i in items if "/b/bin" in i.title)
    assert item.severity == "warn"
    assert "new shell" in item.next_step.lower() or "reload" in item.next_step.lower()


def test_every_problem_finding_carries_meaning_and_next_step() -> None:
    report = DoctorReport(
        missing=(Path("/a/bin"),), broken=(Path("/c/bin"),), duplicated=(Path("/b/bin"),)
    )
    items = doctor_guidance(report)
    assert len(items) == 3  # no healthy item when there are problems
    assert all(i.meaning and i.next_step for i in items)


def test_guard_guidance_silent_when_inactive_and_no_warning() -> None:
    assert guard_guidance({"pip": False, "npm": False}, None) == []


def test_guard_guidance_reports_active_ban_with_reload_step() -> None:
    items = guard_guidance({"pip": True, "npm": False}, None)
    item = next(i for i in items if "ban active" in i.title)
    assert item.severity == "ok"
    assert "pip" in item.meaning
    assert "hash -r" in item.next_step or "new shell" in item.next_step


def test_guard_guidance_reports_path_order_warning() -> None:
    items = guard_guidance({"pip": False}, "shim dir is behind the real binary")
    item = next(i for i in items if "order" in i.title.lower())
    assert item.severity == "warn"
    assert "shim dir is behind the real binary" in item.meaning
    assert item.next_step


def test_guidance_is_frozen() -> None:
    g = Guidance(title="t", meaning="m", next_step="n", severity="ok")
    try:
        g.title = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Guidance should be frozen")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_guidance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'installer.guidance'`.

- [ ] **Step 3: Implement the guidance core**

```python
# installer/guidance.py
"""Pure guidance: map each PATH/guard finding type to a meaning + an exact next step.

No IO, no rich/Textual imports — both the console renderer and the Textual views
consume the same Guidance list, so each finding's wording lives in exactly one
place. `severity` drives color-coding downstream.
"""

from dataclasses import dataclass
from typing import Literal

from installer.doctor import DoctorReport, has_problems

Severity = Literal["ok", "warn", "error"]


@dataclass(frozen=True)
class Guidance:
    title: str
    meaning: str
    next_step: str  # empty only for the healthy/ok case
    severity: Severity


_HEALTHY = Guidance(
    title="PATH looks healthy",
    meaning="All bin dirs are present, on PATH, and unique.",
    next_step="",
    severity="ok",
)


def doctor_guidance(report: DoctorReport) -> list[Guidance]:
    """One Guidance per finding; a single healthy item when there are no problems."""
    if not has_problems(report):
        return [_HEALTHY]
    items: list[Guidance] = []
    for directory in report.broken:
        items.append(
            Guidance(
                title=f"{directory} does not exist",
                meaning=f"{directory} is declared but does not exist yet.",
                next_step="It is created when a tool installs there — nothing to do now.",
                severity="error",
            )
        )
    for directory in report.missing:
        items.append(
            Guidance(
                title=f"{directory} not on PATH",
                meaning=f"{directory} is not on your PATH.",
                next_step="Run `make fix`, then open a new terminal (or `source ~/.myshellrc`).",
                severity="warn",
            )
        )
    for directory in report.duplicated:
        items.append(
            Guidance(
                title=f"{directory} duplicated on PATH",
                meaning=f"{directory} appears more than once on PATH.",
                next_step="Harmless — transient duplicates clear when you open a new shell.",
                severity="warn",
            )
        )
    return items


def guard_guidance(status: dict[str, bool], warning: str | None) -> list[Guidance]:
    """pip/npm-ban + PATH-order guidance; empty when nothing is active and no warning."""
    items: list[Guidance] = []
    active = [name for name, installed in status.items() if installed]
    if active:
        items.append(
            Guidance(
                title="pip/npm ban active",
                meaning=f"{', '.join(active)} are shimmed to their replacements.",
                next_step="Open a new shell or run `hash -r` so cached command paths refresh.",
                severity="ok",
            )
        )
    if warning:
        items.append(
            Guidance(
                title="PATH order warning",
                meaning=warning,
                next_step="Put the shim dir ahead of the real binary on PATH, then reopen the shell.",
                severity="warn",
            )
        )
    return items
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_guidance.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add installer/guidance.py tests/test_guidance.py
git commit -m "feat: pure guidance core mapping findings to meaning + next step"
```

---

## Task 2: Console renderer consumes guidance (`render_doctor`, `guidance_text`)

`render_doctor` drops its `hint` param (guidance now carries the next step) and renders each finding's guidance. A shared `guidance_text` builds the colored `Text` reused later by the screens.

**Files:**
- Modify: `installer/render.py` (the `render_doctor` function at `installer/render.py:75-87`; add `guidance_text`)
- Modify: `tests/test_render.py` (the two `render_doctor` tests at `:63` and `:81`)

- [ ] **Step 1: Update the failing tests first**

Replace `tests/test_render.py:63-89` (the two `render_doctor` tests) with:

```python
def test_render_doctor_prints_findings_with_meaning_and_next_step() -> None:
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    report = DoctorReport(
        missing=(Path("/a/bin"),),
        broken=(Path("/c/bin"),),
        duplicated=(Path("/b/bin"),),
    )
    console, buf = _console()
    render_doctor(report, console)
    out = buf.getvalue()
    assert "/a/bin" in out and "/c/bin" in out and "/b/bin" in out
    assert "not on PATH" in out  # the missing-dir guidance title
    assert "make fix" in out  # the missing-dir next step
    assert "github.com" not in out  # troubleshooting URL never printed here


def test_render_doctor_healthy_says_healthy() -> None:
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    console, buf = _console()
    render_doctor(DoctorReport(missing=(), broken=(), duplicated=()), console)
    out = buf.getvalue()
    assert "healthy" in out.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_render.py -k render_doctor -v`
Expected: FAIL — `render_doctor()` still requires the removed `hint` argument (TypeError) or asserts mismatch.

- [ ] **Step 3: Implement `guidance_text` and rewrite `render_doctor`**

In `installer/render.py`, add the import near the top (after the existing imports):

```python
from rich.text import Text

from installer.guidance import Guidance, doctor_guidance, guard_guidance
```

Add the shared helper (place it above `render_doctor`):

```python
_SEVERITY_STYLE: dict[str, str] = {"ok": "green", "warn": "yellow", "error": "red"}


def guidance_text(items: list[Guidance]) -> Text:
    """Render guidance items as one colored block: title (by severity), meaning, next step."""
    text = Text()
    for index, item in enumerate(items):
        if index:
            text.append("\n")
        text.append(item.title, style=_SEVERITY_STYLE[item.severity])
        text.append(f"\n  {item.meaning}")
        if item.next_step:
            text.append(f"\n  → {item.next_step}")
    return text
```

Replace the existing `render_doctor` (`installer/render.py:75-87`) with:

```python
def render_doctor(report: DoctorReport, console: Console) -> None:
    """Print each PATH finding with its meaning and exact next step (color by severity)."""
    console.print(guidance_text(doctor_guidance(report)))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_render.py -k render_doctor -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add installer/render.py tests/test_render.py
git commit -m "refactor: render_doctor renders guidance, drops the single hint param"
```

---

## Task 3: `render_guard_status` consumes guidance

Keep the silent-when-inactive contract; route the active/warning output through `guard_guidance` + `guidance_text` so the in-app and console wording match.

**Files:**
- Modify: `installer/render.py` (the `render_guard_status` function at `installer/render.py:102-110`)
- Modify: `tests/test_render.py` (the four `render_guard_status` tests at `:201-233` keep passing; add one for the next-step line)

- [ ] **Step 1: Add a failing test for the next-step line**

Append to `tests/test_render.py`:

```python
def test_render_guard_status_includes_reload_next_step():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": True, "npm": False}, None, console)
    out = buf.getvalue()
    assert "pip/npm ban active" in out
    assert "hash -r" in out  # the reload next step from guard_guidance
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_render.py -k guard_status_includes_reload -v`
Expected: FAIL — current `render_guard_status` prints no `hash -r` next step.

- [ ] **Step 3: Rewrite `render_guard_status`**

Replace `installer/render.py:102-110` with:

```python
def render_guard_status(status: dict[str, bool], warning: str | None, console: Console) -> None:
    """Read-only doctor lines: silent unless the ban is active or PATH order is off."""
    items = guard_guidance(status, warning)
    if items:
        console.print(guidance_text(items))
```

- [ ] **Step 4: Run the full render suite**

Run: `uv run pytest tests/test_render.py -v`
Expected: PASS — the silent-when-inactive test (`:201`) still passes (no items → nothing printed → empty buffer); the active/warning tests still find their substrings in the meaning/title.

- [ ] **Step 5: Commit**

```bash
git add installer/render.py tests/test_render.py
git commit -m "refactor: render_guard_status renders guard guidance"
```

---

## Task 4: Drop `hint` from `run_doctor` and fix its callers

`render_doctor` no longer takes `hint`, so `run_doctor` drops it too.

**Files:**
- Modify: `installer/app.py` (`run_doctor` at `installer/app.py:165-190`)
- Modify: `tests/test_app.py` (the two `run_doctor` tests at `:223`/`:246`, and the guard test call at `:798`)
- Modify: `setup.py` (the two `run_doctor` calls at `:180` and `:242`) — IO boundary

- [ ] **Step 1: Update the failing tests first**

In `tests/test_app.py`, edit `test_run_doctor_reports_problems_with_hint_and_never_writes` (`:223`): rename to `test_run_doctor_reports_problems_and_never_writes`, delete the `hint=...` line (`:236`), and keep the assertions (`make fix` still appears via the missing-dir guidance):

```python
def test_run_doctor_reports_problems_and_never_writes(tmp_path: Path):
    from installer.app import run_doctor

    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()

    report = run_doctor(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value="/usr/bin",
        exists=lambda _p: False,  # default dir absent -> missing + broken
    )

    assert bin_dir in report.missing
    assert bin_dir in report.broken
    assert "make fix" in buf.getvalue()
    assert "github.com" not in buf.getvalue()
    assert list(tmp_path.iterdir()) == []  # diagnosis only: nothing written
```

Edit `test_run_doctor_healthy_reports_no_hint` (`:246`): rename to `test_run_doctor_healthy_says_healthy`, delete the `hint="HINT"` line and the `"HINT" not in` assertion:

```python
def test_run_doctor_healthy_says_healthy(tmp_path: Path):
    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    console, buf = _console()

    report = run_doctor(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value=str(bin_dir),
        exists=lambda _p: True,
    )

    assert report.missing == () and report.broken == () and report.duplicated == ()
    assert "healthy" in buf.getvalue().lower()
```

In the guard test (`tests/test_app.py:791-800`), delete the `hint="hint",` line (`:798`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_app.py -k run_doctor -v`
Expected: FAIL — `run_doctor()` still declares a required `hint` parameter (TypeError on the calls that now omit it) until Step 3.

- [ ] **Step 3: Drop `hint` from `run_doctor`**

In `installer/app.py`, edit `run_doctor` (`:165-190`): remove the `hint: str,` parameter line (`:173`), remove the `hint` sentence from the docstring, and change the render call (`:184`) from `render_doctor(report, console, hint)` to:

```python
    render_doctor(report, console)
```

- [ ] **Step 4: Fix the `setup.py` callers (IO boundary)**

In `setup.py`, delete the `hint=...` keyword from both `run_doctor` calls: `_run_doctor` (`:180`) and `_verify_and_clean` (`:242`).

- [ ] **Step 5: Run the affected suites**

Run: `uv run pytest tests/test_app.py tests/test_render.py -v`
Expected: PASS. Then `uv run python setup.py --help` (or `make setup ARGS="--help"`) runs without a TypeError.

- [ ] **Step 6: Commit**

```bash
git add installer/app.py setup.py tests/test_app.py
git commit -m "refactor: run_doctor drops hint param now that guidance carries next steps"
```

---

## Task 5: Read-only `DoctorScreen` in the app

Replace the doctor placeholder with a real Screen rendering the guidance. Refactor `_placeholders` → `_views` and extend the constructor with the doctor/guard data.

**Files:**
- Modify: `installer/wizard_app.py`
- Modify: `tests/test_wizard_app.py` (the `_app()` helper at `:22`, and the doctor-placeholder assertion at `:47`)

- [ ] **Step 1: Write the failing test**

In `tests/test_wizard_app.py`, replace the imports/helper to construct the new data, and add a DoctorScreen test. First update the import line (`:6`) and `_app` (`:22-25`):

```python
from pathlib import Path

from installer.doctor import DoctorReport
from installer.wizard_app import (
    VIEW_ORDER,
    DoctorScreen,
    NavScreen,
    PlaceholderScreen,
    UnifiedApp,
)


def _app(
    *,
    report: DoctorReport | None = None,
    guard_status: dict[str, bool] | None = None,
    guard_warning: str | None = None,
    fix_preview: str = "Will wire ~/.local/bin into ~/.zshrc",
    fix=lambda: None,
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
```

Update `test_number_key_navigates_to_each_view` — the doctor view is now a real screen, so replace the doctor placeholder assertion (`:47`) with a screen-type check:

```python
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
```

Add a DoctorScreen content test:

```python
async def test_doctor_screen_renders_guidance() -> None:
    app = _app(report=DoctorReport(missing=(Path("/a/bin"),), broken=(), duplicated=()))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert isinstance(app.screen, DoctorScreen)
        text = "".join(g.title + g.meaning + g.next_step for g in app.screen.guidance)
        assert "/a/bin" in text
        assert "make fix" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_wizard_app.py -k "doctor_screen or number_key" -v`
Expected: FAIL — `UnifiedApp.__init__` does not accept `report=`/`fix=` yet; `DoctorScreen` is not importable.

- [ ] **Step 3: Implement `DoctorScreen` and the constructor refactor**

In `installer/wizard_app.py`, extend the imports:

```python
from collections.abc import Callable, Mapping
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Middle
from textual.screen import ModalScreen, Screen
from textual.widgets import Label, ListItem, ListView, Static

from installer.catalog_tui import CatalogScreen
from installer.doctor import DoctorReport
from installer.guidance import Guidance, doctor_guidance, guard_guidance
from installer.model import Tool
from installer.render import guidance_text
```

Add `DoctorScreen` (after `PlaceholderScreen`):

```python
class DoctorScreen(Screen[None]):
    """Read-only PATH audit + guidance, color-coded by severity."""

    DEFAULT_CSS = """
    DoctorScreen #doctor-body { padding: 1 2; }
    """

    def __init__(
        self,
        report: DoctorReport,
        guard_status: dict[str, bool],
        guard_warning: str | None,
    ) -> None:
        super().__init__()
        self._report = report
        self._guard_status = guard_status
        self._guard_warning = guard_warning
        self.guidance: list[Guidance] = []  # public test seam

    def compose(self) -> ComposeResult:
        yield Static(id="doctor-body")

    def on_mount(self) -> None:
        self.guidance = doctor_guidance(self._report) + guard_guidance(
            self._guard_status, self._guard_warning
        )
        self.query_one("#doctor-body", Static).update(guidance_text(self.guidance))
```

Rewrite `UnifiedApp.__init__` and the `_placeholders` → `_views` rename. Replace the constructor (`installer/wizard_app.py:96-111`) with:

```python
    def __init__(
        self,
        tools: list[Tool],
        installed: Mapping[str, bool],
        blurbs: Mapping[str, str],
        *,
        report: DoctorReport,
        guard_status: dict[str, bool],
        guard_warning: str | None,
        fix_preview: str,
        fix: Callable[[], None],
        initial_view: str = "catalog",
    ) -> None:
        super().__init__()
        self._catalog = CatalogScreen(tools, installed, blurbs)
        # Non-catalog views, pushed by value. Doctor is real; the rest are
        # placeholders until their phases. push_screen/pop_screen stay fully
        # typed under pyright strict (unlike install_screen/switch_screen).
        self._views: dict[str, Screen[None]] = {
            "doctor": DoctorScreen(report, guard_status, guard_warning),
            "fix": PlaceholderScreen(_PLACEHOLDER_TEXT["fix"]),
            "uninstall": PlaceholderScreen(_PLACEHOLDER_TEXT["uninstall"]),
            "policies": PlaceholderScreen(_PLACEHOLDER_TEXT["policies"]),
        }
        self._fix_preview = fix_preview  # used by FixScreen in Task 6
        self._fix = fix
        self._initial_view = initial_view
        self.current_view = "catalog"
```

Update `show_view` (`:123-134`): change `self._placeholders[name]` to `self._views[name]`.

Update `_navigable` (`:136-142`): change `self.screen in self._placeholders.values()` to `self.screen in self._views.values()`.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_wizard_app.py -v`
Expected: PASS. (The existing `test_palette_from_placeholder_navigates_without_desync` still passes: it navigates to doctor then on to the uninstall placeholder.)

- [ ] **Step 5: Update `setup.py` `_select_catalog` (IO boundary)**

`UnifiedApp` now needs the doctor/guard data + a fix closure. Replace `_select_catalog` (`setup.py:141-143`) with:

```python
def _doctor_data(tools: list[Tool], platform: Platform) -> tuple[DoctorReport, dict[str, bool], str | None]:
    path_value = os.environ.get("PATH", "")
    bin_dirs = collect_bin_dirs(tools, platform, _DEFAULT_BIN_DIR)
    report = audit_path(bin_dirs, path_value, Path.is_dir)
    status = guard_status(_DEFAULT_BIN_DIR)
    warning = (
        guard_path_warning(_DEFAULT_BIN_DIR, path_value, shutil.which)
        if any(status.values())
        else None
    )
    return report, status, warning


def _build_app(tools: list[Tool], platform: Platform, *, initial_view: str = "catalog") -> UnifiedApp:
    installed = {tool.id: is_installed(tool) for tool in tools}
    report, status, warning = _doctor_data(tools, platform)
    link_mode = _resolve_link_mode(None)
    rc_paths = _rc_paths_for_mode(link_mode)

    def _apply_fix() -> None:
        # Runs live inside the FixScreen. Use a quiet console so configure_path's
        # own prints never corrupt the running TUI; the screen shows its own result.
        configure_path(
            tools,
            Console(file=io.StringIO()),
            platform=platform,
            default_bin_dir=_DEFAULT_BIN_DIR,
            myshellrc_path=_MYSHELLRC,
            rc_paths=rc_paths,
            link_mode=link_mode,
        )

    preview = f"Will wire the managed bin dirs into {', '.join(str(p) for p in rc_paths)} (mode: {link_mode})."
    return UnifiedApp(
        tools,
        installed,
        load_categories(_REGISTRY),
        report=report,
        guard_status=status,
        guard_warning=warning,
        fix_preview=preview,
        fix=_apply_fix,
        initial_view=initial_view,
    )


def _select_catalog(tools: list[Tool]) -> list[str] | None:
    return _build_app(tools, detect()).run()
```

Add the needed imports to `setup.py` if missing: `io`, `shutil`, and from `installer.app` / modules: `audit_path` (from `installer.doctor`), `collect_bin_dirs` (already imported), `guard_status`, `guard_path_warning` (from `installer.guards`), `DoctorReport` (from `installer.doctor`). Verify with `uv run python setup.py --help`.

- [ ] **Step 6: Run validate + the app/setup smoke**

Run: `uv run pytest tests/test_wizard_app.py tests/test_app.py -v && uv run python setup.py --help`
Expected: PASS; `--help` prints usage with no import/type error.

- [ ] **Step 7: Commit**

```bash
git add installer/wizard_app.py setup.py tests/test_wizard_app.py
git commit -m "feat: in-app read-only DoctorScreen rendering PATH guidance"
```

---

## Task 6: `FixScreen` (applies live) + `--doctor`/`--fix` open-on-view

Replace the fix placeholder with a Screen that previews the wiring and applies it live via the injected closure; add `initial_view` mounting; re-wire the flags.

**Files:**
- Modify: `installer/wizard_app.py` (add `FixScreen`; swap the fix placeholder; add `on_mount`)
- Modify: `tests/test_wizard_app.py` (FixScreen + initial_view tests)
- Modify: `setup.py` (`_run_doctor`/`_run_fix` open the app when interactive) — IO boundary

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_wizard_app.py` (and add `FixScreen` to the `wizard_app` import):

```python
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
```

Also update the `wizard_app` import block in the test to include `FixScreen`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_wizard_app.py -k "fix_screen or initial_view" -v`
Expected: FAIL — `FixScreen` not importable; `initial_view` not honored on mount.

- [ ] **Step 3: Implement `FixScreen`, swap the placeholder, add `on_mount`**

In `installer/wizard_app.py`, add `FixScreen` (after `DoctorScreen`):

```python
class FixScreen(Screen[None]):
    """Preview the PATH wiring + reload guidance; Apply runs it live, in place."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "apply", "apply", show=True),
    ]
    DEFAULT_CSS = """
    FixScreen #fix-body { padding: 1 2; }
    """

    def __init__(self, preview: str, fix: Callable[[], None]) -> None:
        super().__init__()
        self._preview = preview
        self._fix = fix
        self.applied = False  # public test seam

    def compose(self) -> ComposeResult:
        yield Static(id="fix-body")

    def on_mount(self) -> None:
        self._render()

    def _render(self) -> None:
        body = self.query_one("#fix-body", Static)
        text = Text()
        if self.applied:
            text.append("PATH wired.", style="green")
            text.append("\n  → Restart your shell or run `source ~/.myshellrc` to apply.")
        else:
            text.append("Press 'a' to wire the managed PATH into your shells.", style="yellow")
            text.append(f"\n\n{self._preview}")
            text.append("\n\nAfter applying, restart your shell or `source ~/.myshellrc`.")
        body.update(text)

    def action_apply(self) -> None:
        if self.applied:
            return
        self._fix()
        self.applied = True
        self._render()
```

In `UnifiedApp.__init__`, change the `"fix"` entry of `self._views` from the placeholder to:

```python
            "fix": FixScreen(fix_preview, fix),
```

(The `self._fix_preview`/`self._fix` attributes set in Task 5 are now consumed here; you may drop them if unused — keep the constructor params.)

Add `on_mount` to `UnifiedApp` (after `__init__`/`catalog` property, before `get_default_screen`):

```python
    def on_mount(self) -> None:
        if self._initial_view != "catalog":
            self.show_view(self._initial_view)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_wizard_app.py -v`
Expected: PASS (all wizard tests, including the new fix + initial_view ones).

- [ ] **Step 5: Re-wire `--doctor`/`--fix` in `setup.py` (IO boundary)**

Make the flags open the app on the corresponding view when interactive; keep the console core for non-interactive. Replace `_run_doctor` (`setup.py:172-182`) and `_run_fix` (`:185-199`) with:

```python
def _run_doctor(console: Console) -> int:
    tools = load_tools(_REGISTRY)
    platform = detect()
    if sys.stdin.isatty():
        _build_app(tools, platform, initial_view="doctor").run()
        return 0
    run_doctor(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
    )
    return 0


def _run_fix(console: Console, *, link_mode_option: str | None) -> int:
    tools = load_tools(_REGISTRY)
    platform = detect()
    if sys.stdin.isatty() and link_mode_option is None:
        # Interactive: the FixScreen previews and applies live (its closure resolves
        # the link mode the same way). An explicit --link-mode keeps the headless path.
        _build_app(tools, platform, initial_view="fix").run()
        return 0
    link_mode = _resolve_link_mode(link_mode_option)
    configure_path(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_rc_paths_for_mode(link_mode),
        link_mode=link_mode,
    )
    return 0
```

(Non-interactive `--doctor`/`--fix` and `--fix --link-mode=...` keep the exact previous console behavior; the app is never launched without a TTY.)

- [ ] **Step 6: Smoke + full validate**

Run: `uv run python setup.py --help` then `make validate && make test`
Expected: `--help` clean; `make validate` green (ruff, ruff format, pyright strict, bandit, vulture, shellcheck); `make test` green at 100% coverage on `installer/`.

- [ ] **Step 7: Commit**

```bash
git add installer/wizard_app.py setup.py tests/test_wizard_app.py
git commit -m "feat: live-applying FixScreen + open the app on doctor/fix views"
```

---

## Task 7: Docs + memory

**Files:**
- Modify: `README.md` (doctor/fix section — mention the in-app guided views)
- Modify: `/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md` (mark Phase 2 done)

- [ ] **Step 1: Update README**

Find the doctor/fix section in `README.md` and add a sentence: interactive `make doctor`/`make fix` now open the unified app on a guided Doctor view (read-only audit + per-finding guidance) / Fix view (preview, then apply with `a`); non-interactive use and `--link-mode` keep the console behavior. Verify the wording matches the as-built keys (`a` to apply; `Ctrl+P`/number keys to navigate).

- [ ] **Step 2: Update roadmap memory**

In `roadmap-status.md`, update the Phase-1 entry's trailing "Phases 2–4 PENDING" note: mark **Phase 2 DONE** with the spec/plan paths, the guidance-core + DoctorScreen/FixScreen summary, the "fix runs live in-view, return contract unchanged" decision, and that it is NOT pushed (owner step). Leave Phases 3–4 pending.

- [ ] **Step 3: Final validate on the exact tree**

Run: `make validate && make test`
Expected: green; 100% coverage retained.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: describe the in-app guided doctor/fix views (Phase 2)"
```

(The memory file lives outside the repo; it is updated, not committed.)

---

## Self-Review

**Spec coverage:**
- Guidance core (pure, all finding types) → Task 1. ✓
- Console `render_doctor`/`render_guard_status` enriched → Tasks 2–3. ✓
- In-app Doctor (read-only) + Fix (applies live) views, reachable via palette + key → Tasks 5–6. ✓
- `--doctor`/`--fix` open-on-view interactively; non-interactive unchanged → Task 6. ✓
- Return contract stays `list[str] | None` (fix mutates FS directly) → no contract task needed; verified by unchanged `CatalogScreen.Decided` flow. ✓
- 100% coverage retained; `setup.py` excluded → Tasks 5–7 smoke + `make test`. ✓
- Docs + memory → Task 7. ✓

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to" — every code step shows the code. Task 7 README step describes content rather than a code block because it is prose docs (acceptable; the substance is specified).

**Type consistency:**
- `Guidance(title, meaning, next_step, severity)` — defined Task 1, used identically in Tasks 2/3/5.
- `guidance_text(items: list[Guidance]) -> Text` — defined Task 2, imported in Task 5.
- `doctor_guidance(report)` / `guard_guidance(status, warning)` — consistent across Tasks 1/2/3/5.
- `DoctorScreen(report, guard_status, guard_warning)` / `FixScreen(preview, fix)` — constructor args match the `UnifiedApp._views` build sites in Tasks 5/6.
- `UnifiedApp(..., *, report, guard_status, guard_warning, fix_preview, fix, initial_view)` — same keyword set in the `_app()` test helper (Task 5) and `_build_app` (Tasks 5/6).
- `.applied` / `.guidance` public seams — set in screens, asserted in tests, names match.
