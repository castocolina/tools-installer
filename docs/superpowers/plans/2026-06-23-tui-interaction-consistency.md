# TUI Interaction Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the wizard's staged-vs-live apply model legible and its keys consistent — aligned `space`/`enter`, a per-view mode badge, a curated two-zone footer, an uninstall confirmation, and a fix for the async navigation stack-invariant race.

**Architecture:** The five views already share one chrome via `AppScreen` (`installer/ui_common.py`): `WayfindingHeader → compose_body() → StatusLine → Footer`. We extend that chrome with a `ModeBadge` (looked up from a `VIEW_MODES` table keyed by the `view` the screen already passes) and replace the bare `Footer` with a curated `FooterBar`. We align the toggle/commit keys (`space` = toggle the highlighted thing, `enter` = proceed/commit) across views without flattening the genuinely different apply semantics, add a confirmation modal to the one destructive commit (uninstall), and serialize navigation with async `await` so rapid `1`–`5` presses cannot corrupt the screen stack.

**Tech Stack:** Python 3.12, Textual 8.x, Rich, pytest + pytest-asyncio, uv. All pure/IO-light UI logic lives in `installer/`; `setup.py` remains the untested composition root.

## Global Constraints

- **English only** in all code, comments, docstrings, log lines, and commit messages.
- **uv owns the environment.** Run everything via `uv run …` / `make …`. Never `pip`, `poetry`, `conda`, or a hand-rolled venv.
- **100% coverage on `installer/`.** `setup.py` is the only untested, pyright-excluded IO boundary; no new logic goes there.
- **pyright strict, no suppressions.** Fix root causes; never silence a check. `uv run pyright` (no args) is the authority — ignore stale editor diagnostics.
- **Never invoke bare `npm`/`pip`** anywhere.
- **`make validate && make test` must pass on the exact tree** before every commit.
- **Coherent commits.** Each task is one self-contained, valid change. Commit messages end with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **E2E never touches the real HOME.** Any test that exercises live apply/remove sandboxes `HOME` via `monkeypatch.setenv("HOME", tmp_path)`.

**Design of record:** `docs/superpowers/specs/2026-06-23-tui-interaction-consistency-design.md`

**Non-goal — `installer/tool_browser.py` is intentionally untouched.** The design's Components section listed "tool_browser.py — Footer hint description text and binding order" as a file to touch. That change is moot: Task 4 replaces Textual's `Footer` widget entirely with the hand-authored `FooterBar`, which reads from `FOOTER_ACTIONS` (not from `ToolBrowser.BINDINGS` description text). The `ToolBrowser` binding `description` fields (`"toggle"`, `"all"`, `"invert"`, `"accept"`) no longer drive any visible footer on any view, so there is nothing to update. A zero-context executor must not touch `installer/tool_browser.py`.

---

### Task 1: Rebind the Policies live toggle from `enter` to `space`

Policies stays live (each toggle applies immediately) but moves to `space`, so "act on the highlighted row" is the same key as in Catalog/Uninstall. `enter` becomes inert on Policies (there is no staged batch to commit).

**Files:**
- Modify: `installer/wizard_app.py:398-400` (PoliciesScreen `BINDINGS`) and the docstring at `:391-396`
- Test: `tests/test_wizard_app.py` (update the existing policy-toggle tests)

**Interfaces:**
- Consumes: nothing new.
- Produces: PoliciesScreen toggles its highlighted policy on `space`; `enter` does nothing on the Policies view.

- [ ] **Step 1: Update the existing policy-toggle tests to press `space`**

In `tests/test_wizard_app.py`, every policy test that drives the toggle currently presses `enter`. Change those presses to `space`. The affected tests (verify by reading each) are:
`test_policy_toggle_enables_inactive_policy`, `test_policy_state_cell_carries_glyph_for_on_and_off`, `test_policy_toggle_disables_active_policy`, `test_policy_toggle_error_surfaces_and_does_not_crash`, `test_policy_toggle_noop_on_empty_table`, `test_policy_summary_includes_warning_when_set`.

For each, replace `await pilot.press("enter")` with `await pilot.press("space")`. Example (`test_policy_toggle_enables_inactive_policy`):

```python
async def test_policy_toggle_enables_inactive_policy() -> None:
    app = _app(policies=_policy_inputs([_fake_policy(active=False)]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")
        assert screen.active_state["ban"] is True
```

Then add a new test asserting `enter` is now inert on Policies:

```python
async def test_policy_enter_does_not_toggle() -> None:
    """enter is inert on the live Policies view — there is no staged batch to
    commit, so only space (toggle-this-row) acts."""
    app = _app(policies=_policy_inputs([_fake_policy(active=False)]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("enter")
        assert screen.active_state["ban"] is False
```

- [ ] **Step 2: Run the tests to verify the new/updated expectations fail**

Run: `uv run pytest tests/test_wizard_app.py -k policy -v`
Expected: the `space` presses and `test_policy_enter_does_not_toggle` FAIL (today `enter` toggles, `space` does not).

- [ ] **Step 3: Rebind the key**

In `installer/wizard_app.py`, change the PoliciesScreen binding:

```python
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_policy", "toggle policy", show=True, priority=True),
    ]
```

Update the docstring to match the new model:

```python
class PoliciesScreen(AppScreen):
    """Toggle environment policies (the pip/npm ban) on/off, applied live.

    Each toggle is an immediate, idempotent, reversible mutation — there is no
    select-then-commit step. `space` toggles the highlighted policy (matching the
    "act on this row" meaning of `space` in the catalog/uninstall browsers);
    `enter` is inert here because there is no staged batch to commit.
    """
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -k policy -v`
Expected: PASS.

- [ ] **Step 5: Full gate and commit**

```bash
make validate && make test
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "feat: toggle policies with space, not enter

Aligns the live Policies toggle with the catalog/uninstall 'space acts on
the highlighted row' convention. enter is now inert on Policies (no staged
batch to commit). Policy toggles stay live and reversible.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Rebind the Fix apply key from `a` to `enter` (keep `a` as a hidden alias)

`enter` is the universal "proceed" key; `a` was an arbitrary mnemonic. Keep `a` working (hidden) for one release of muscle-memory continuity.

**Files:**
- Modify: `installer/wizard_app.py:101-103` (FixScreen `BINDINGS`) and `_refresh_body` copy at `:133-135` (the two "press 'a' to retry" / "Press 'a' to wire" lines)
- Test: `tests/test_wizard_app.py` (update the existing fix tests)

**Interfaces:**
- Consumes: nothing new.
- Produces: FixScreen applies on `enter` (shown) and on `a` (hidden alias); preview/error copy references `enter`.

- [ ] **Step 1: Update the existing fix tests to press `enter`; add an alias test**

In `tests/test_wizard_app.py`, the fix tests press `"a"`. Update them to press `"enter"`:
`test_fix_screen_previews_then_applies_live`, `test_fix_screen_apply_is_idempotent`, `test_fix_screen_surfaces_apply_failure_without_crashing`.

Example (`test_fix_screen_previews_then_applies_live`):

```python
async def test_fix_screen_previews_then_applies_live() -> None:
    calls: list[int] = []
    app = _app(fix=lambda: calls.append(1), initial_view="fix")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, FixScreen)
        await pilot.press("enter")  # Apply
        assert calls == [1]
        assert screen.applied is True
```

For `test_fix_screen_apply_is_idempotent`, both presses become `enter`. For the failure test, both the failing apply and the retry become `enter`.

Add a test that the legacy `a` alias still applies:

```python
async def test_fix_screen_apply_legacy_a_alias_still_works() -> None:
    """`a` remains a hidden alias for apply for one release of muscle memory."""
    calls: list[int] = []
    app = _app(fix=lambda: calls.append(1), initial_view="fix")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        assert calls == [1]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_wizard_app.py -k fix -v`
Expected: the `enter` presses FAIL (today only `a` applies).

- [ ] **Step 3: Rebind and update the copy**

In `installer/wizard_app.py`, change the FixScreen bindings:

```python
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "apply", "apply", show=True),
        Binding("a", "apply", "apply", show=False),  # legacy alias, kept one release
    ]
```

Update the two copy lines in `_refresh_body` that say `'a'`:

```python
            text.append("\n  → Check the target is writable, then press enter to retry.")
```

and

```python
            text.append("Press enter to wire the managed PATH into your shells.", style="yellow")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -k fix -v`
Expected: PASS.

- [ ] **Step 5: Full gate and commit**

```bash
make validate && make test
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "feat: apply the PATH fix with enter, not a

enter is the recognized 'proceed' key; a stays as a hidden alias for one
release. Preview and retry copy now reference enter.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Mode badge — name the apply semantics of every view

Add a `ViewMode` config and a `ModeBadge` widget to the shared chrome. Because every `AppScreen` already passes `view=`, the badge is looked up from a `VIEW_MODES` table — no subclass signature changes. The hints now match the keys finalized in Tasks 1–2.

**Design deviation — `AppScreen.__init__` is NOT changed.** The design's Components section says "AppScreen.__init__ takes a mode: ViewMode parameter". This plan intentionally supersedes that bullet: instead of threading a `ViewMode` instance through every `AppScreen` subclass constructor, `compose()` does a one-liner table lookup (`VIEW_MODES[self._view]`). This avoids adding a required constructor argument to all five screen subclasses and keeps the interface change confined to a single method in `ui_common.py`. The design's `__init__` bullet is obsoleted by this implementation choice.

**Files:**
- Modify: `installer/ui_common.py` (add `ViewMode`, `VIEW_MODES`, `ModeBadge`; wire into `AppScreen`)
- Test: `tests/test_ui_common.py` (badge rendering + chrome guarantee)

**Interfaces:**
- Consumes: the existing `AppScreen(view=...)` constructor.
- Produces:
  - `ViewMode` frozen dataclass: `label: str`, `glyph: str`, `style: str`, `hint: str`.
  - `VIEW_MODES: dict[str, ViewMode]` keyed by the five view names.
  - `ModeBadge(Static)` with `render_text() -> Text` (public seam) and an `on_mount` that paints it.
  - `AppScreen.compose()` yields `ModeBadge` immediately after `WayfindingHeader`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ui_common.py`:

```python
def test_view_modes_cover_every_view() -> None:
    from installer.ui_common import VIEW_LABELS, VIEW_MODES

    assert set(VIEW_MODES) == {key for key, _ in VIEW_LABELS}


def test_mode_badge_renders_label_glyph_and_hint() -> None:
    from installer.ui_common import VIEW_MODES, ModeBadge

    badge = ModeBadge(VIEW_MODES["policies"])
    text = badge.render_text()
    assert "◆" in text.plain
    assert "[LIVE]" in text.plain
    assert "space toggles a policy and applies it now" in text.plain


def test_mode_badge_staged_and_readonly_strings() -> None:
    from installer.ui_common import VIEW_MODES, ModeBadge

    assert "[STAGED]" in ModeBadge(VIEW_MODES["catalog"]).render_text().plain
    assert "◇" in ModeBadge(VIEW_MODES["catalog"]).render_text().plain
    uninstall = ModeBadge(VIEW_MODES["uninstall"]).render_text().plain
    assert "[STAGED · DESTRUCTIVE]" in uninstall
    assert "◇" in uninstall  # staged stays hollow; danger is carried by the words + red
    assert "[READ-ONLY]" in ModeBadge(VIEW_MODES["doctor"]).render_text().plain
```

Extend the chrome guarantee test `test_app_screen_yields_header_status_and_footer` to assert exactly one `ModeBadge`:

```python
    async with app.run_test(size=(100, 20)):
        screen = app.screen
        assert len(screen.query(WayfindingHeader)) == 1
        assert len(screen.query(ModeBadge)) == 1
        assert len(screen.query(StatusLine)) == 1
        assert len(screen.query(Footer)) == 1
        assert len(screen.query("#demo-body")) == 1
```

Add `ModeBadge` to that test's imports: `from installer.ui_common import AppScreen, ModeBadge, StatusLine, WayfindingHeader`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_common.py -k "mode_badge or view_modes or yields_header" -v`
Expected: FAIL with `ImportError` / `AttributeError` for `ModeBadge` / `VIEW_MODES`.

- [ ] **Step 3: Implement `ViewMode`, `VIEW_MODES`, `ModeBadge`, and wire the chrome**

In `installer/ui_common.py`, add the imports `from dataclasses import dataclass` (top) and define, near `VIEW_LABELS`:

```python
@dataclass(frozen=True)
class ViewMode:
    """The apply-semantics badge for a view: a bracketed label (the load-bearing
    signal), a glyph whose fill is the colorblind-safe cue (hollow ◇ = staged,
    filled ◆ = live), a concrete color, and a plain-language controls hint."""

    label: str
    glyph: str
    style: str
    hint: str


# One mode per view. Hollow ◇ = staged (nothing changes until you commit);
# filled ◆ = live (each action applies immediately). Fix is a single-action
# apply (▸); Doctor is read-only (‹). Hints name the keys finalized for each view.
VIEW_MODES: dict[str, ViewMode] = {
    "catalog": ViewMode(
        "STAGED", "◇", "cyan", "space marks a tool · enter installs your selection"
    ),
    "doctor": ViewMode(
        "READ-ONLY", "‹", "dim", "audit report · nothing here changes your system"
    ),
    "fix": ViewMode("APPLY", "▸", "yellow", "enter wires the managed PATH into your shells"),
    "uninstall": ViewMode(
        "STAGED · DESTRUCTIVE",
        "◇",
        "red",
        "space marks · enter removes marked items (you'll confirm)",
    ),
    "policies": ViewMode(
        "LIVE", "◆", "yellow", "space toggles a policy and applies it now · reversible"
    ),
}


class ModeBadge(Static):
    """Docked under the breadcrumb: names the view's apply semantics, redundantly
    encoded (bracketed label + glyph + color) so the cue survives a colorblind
    reader and a flattened selection highlight."""

    DEFAULT_CSS = "ModeBadge { height: 1; padding: 0 1; }"

    def __init__(self, mode: ViewMode) -> None:
        super().__init__()
        self._mode = mode

    def render_text(self) -> Text:
        # Rich Text (not markup): the [LABEL] brackets are literal, and the colors
        # are concrete, so no content-markup escaping or theme-var resolution is
        # needed. Public seam: tests assert on exactly what on_mount paints.
        text = Text()
        text.append(f"{self._mode.glyph} [{self._mode.label}]", style=self._mode.style)
        text.append(f"   {self._mode.hint}", style="dim")
        return text

    def on_mount(self) -> None:
        self.update(self.render_text())
```

Update `AppScreen.compose` to yield the badge after the header:

```python
    def compose(self) -> ComposeResult:
        yield WayfindingHeader(active=self._view, accent=self._accent)
        yield ModeBadge(VIEW_MODES[self._view])
        yield from self.compose_body()
        yield self.status
        yield Footer()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_common.py -v`
Expected: PASS.

- [ ] **Step 5: Full gate and commit**

The full suite drives all five screens; confirm the new chrome row does not break any layout-sensitive assertions.

```bash
make validate && make test
git add installer/ui_common.py tests/test_ui_common.py
git commit -m "feat: add a per-view mode badge naming apply semantics

ViewMode + VIEW_MODES + ModeBadge, wired into the AppScreen chrome so no
screen can ship without one. Hollow/filled glyph + bracketed label + color
redundantly signal staged vs live vs apply vs read-only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Two-zone footer — view actions left, dim global nav right

Replace the bare Textual `Footer` (which renders an undifferentiated union of bindings) with a curated `FooterBar`: this screen's actions first, a `│` separator, then the always-present global nav, dimmed. Doctor leads with `(read-only)` so its empty action zone reads as intentional.

**Files:**
- Modify: `installer/ui_common.py` (add `FOOTER_ACTIONS`, `GLOBAL_NAV`, `FooterBar`; swap `Footer` → `FooterBar` in `AppScreen.compose`)
- Test: `tests/test_ui_common.py`, and update the two existing tests that assert a `Footer` is present

**Interfaces:**
- Consumes: `AppScreen(view=...)`.
- Produces:
  - `FOOTER_ACTIONS: dict[str, str]` — the left-zone action hint per view.
  - `GLOBAL_NAV: str` — the constant dim nav suffix.
  - `FooterBar(Static)` with `render_text() -> Text` (public seam).
  - `AppScreen.compose()` yields `FooterBar(self._view)` instead of `Footer()`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ui_common.py`:

```python
def test_footer_actions_cover_every_view() -> None:
    from installer.ui_common import FOOTER_ACTIONS, VIEW_LABELS

    assert set(FOOTER_ACTIONS) == {key for key, _ in VIEW_LABELS}


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
```

Update the chrome guarantee test (Task 3 left it asserting `Footer`): replace the `Footer` import and assertion with `FooterBar`:

```python
    from installer.ui_common import AppScreen, FooterBar, ModeBadge, StatusLine, WayfindingHeader
    ...
        assert len(screen.query(FooterBar)) == 1
```

Find the other test asserting a footer — `test_doctor_and_fix_render_a_footer` in `tests/test_wizard_app.py` — and update it to query `FooterBar`:

```python
async def test_doctor_and_fix_render_a_footer() -> None:
    from installer.ui_common import FooterBar

    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert len(app.screen.query(FooterBar)) == 1
        await pilot.press("3")
        assert len(app.screen.query(FooterBar)) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_common.py -k footer -v && uv run pytest tests/test_wizard_app.py -k footer -v`
Expected: FAIL with `ImportError` for `FooterBar` / `FOOTER_ACTIONS`.

- [ ] **Step 3: Implement `FooterBar` and swap the chrome**

In `installer/ui_common.py`, add near `VIEW_MODES`:

```python
# The always-available navigation, shown dim on every view so the user learns one
# rule: the dim cluster right of the separator is global nav; everything left is
# what this screen does.
GLOBAL_NAV = "1–5 views · ^p nav · esc back · q quit"

# The action-zone hint per view (left of the separator). Doctor is read-only, so
# its action zone is an explicit token, not an empty gap.
FOOTER_ACTIONS: dict[str, str] = {
    "catalog": "space toggle · enter install · a all · i invert",
    "doctor": "(read-only)",
    "fix": "enter apply",
    "uninstall": "space mark · enter remove · a all · i invert",
    "policies": "space toggle",
}


class FooterBar(Static):
    """Two-zone key hints: this view's actions, a separator, then dim global nav.
    Replaces Textual's Footer, whose undifferentiated binding union read the same
    on every view (including read-only Doctor)."""

    DEFAULT_CSS = "FooterBar { dock: bottom; height: 1; padding: 0 1; background: $surface; }"

    def __init__(self, view: str) -> None:
        super().__init__()
        self._view = view

    def render_text(self) -> Text:
        text = Text()
        text.append(FOOTER_ACTIONS[self._view])
        text.append("   │   ", style="dim")
        text.append(GLOBAL_NAV, style="dim")
        return text

    def on_mount(self) -> None:
        self.update(self.render_text())
```

Update the `Footer` import line at the top of `ui_common.py` — remove `Footer` if now unused:

```python
from textual.widgets import DataTable, Static
```

Swap the chrome:

```python
    def compose(self) -> ComposeResult:
        yield WayfindingHeader(active=self._view, accent=self._accent)
        yield ModeBadge(VIEW_MODES[self._view])
        yield from self.compose_body()
        yield self.status
        yield FooterBar(self._view)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_common.py -k footer -v && uv run pytest tests/test_wizard_app.py -k footer -v`
Expected: PASS.

- [ ] **Step 5: Full gate and commit**

```bash
make validate && make test
git add installer/ui_common.py tests/test_ui_common.py tests/test_wizard_app.py
git commit -m "feat: curate the footer into a view-actions + global-nav two-zone bar

Replace the undifferentiated Textual Footer with FooterBar: this view's
actions left, a separator, then dim always-available nav. Doctor leads with
(read-only) so its empty action zone reads as intentional.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Confirmation modal on the destructive uninstall commit

Uninstall's `enter` deletes installed artifacts — destructive and not one-keystroke-reversible. It alone gets a confirm step. Policies (idempotent, reversible) deliberately does not.

**Files:**
- Modify: `installer/wizard_app.py` (add `ConfirmUninstall(ModalScreen[bool])`; route `on_tool_browser_accepted` through it)
- Test: `tests/test_wizard_app.py` (update existing uninstall-apply tests to confirm; add cancel + modal tests)

**Interfaces:**
- Consumes: the existing `UninstallScreen.on_tool_browser_accepted` flow and `self._remove(decision)`.
- Produces:
  - `ConfirmUninstall(ModalScreen[bool])` rendering an artifact-count summary; `enter`/`y` dismiss `True`, `escape`/`n` dismiss `False`.
  - On accept with a non-empty selection, `UninstallScreen` pushes the modal; removal runs only on a `True` result.

- [ ] **Step 1: Write/adjust the failing tests**

The destructive removal now takes two keystrokes: `enter` (accept → opens modal), then `enter` (confirm). Update the live-removal uninstall tests to confirm. Affected:
`test_uninstall_apply_calls_remove_and_flips_applied`, `test_uninstall_apply_error_surfaces_and_does_not_crash`, `test_uninstall_partial_selection_apply`, `test_uninstall_applied_summary_ban_and_path`, `test_uninstall_applied_summary_omits_tool_line_when_no_tool`.

Pattern — after the committing `enter`, await the modal and press `enter` again. Example (`test_uninstall_apply_calls_remove_and_flips_applied`):

```python
async def test_uninstall_apply_calls_remove_and_flips_applied() -> None:
    captured: list[UninstallDecision] = []
    rows = [_removable_row(_tool("rg"), [Path("/opt/rg")])]
    app = _app(uninstall=_uninstall_inputs(rows=rows, remove=captured.append))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")  # select rg
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm
        await pilot.pause()
        assert len(captured) == 1
        assert screen.applied is True
```

Complete replacement for `test_uninstall_apply_error_surfaces_and_does_not_crash` — press `space`, `enter` (accept → modal opens), `enter` (confirm → `_apply_removal` raises), `await pilot.pause()`, then assert error surfaced and `applied` is False. Preserve the exact `boom` closure and assertions from the current test (lines 417-430):

```python
async def test_uninstall_apply_error_surfaces_and_does_not_crash() -> None:
    def boom(_decision: UninstallDecision) -> None:
        raise OSError("permission denied")

    inputs = _uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])], remove=boom)
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("space")          # select rg
        await pilot.press("enter")          # accept → confirmation modal
        await pilot.press("enter")          # confirm → _apply_removal raises OSError
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert app.screen.error == "permission denied"
        assert "failed" in app.screen.status.text.lower()
```

Complete replacement for `test_uninstall_partial_selection_apply` — preserve its existing cursor/selection presses (`space` on row 0 only), add the confirm `enter` and `await pilot.pause()` INSIDE the `async with` block before the context exits (assertions on `captured[0]` happen after exit, so removal must finish first). Based on current test at lines 484-504:

```python
async def test_uninstall_partial_selection_apply() -> None:
    """Only selected tools appear in the UninstallDecision paths."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        rows=[
            _removable_row(_tool("rg"), [Path("/opt/rg")]),
            _removable_row(_tool("fd"), [Path("/opt/fd")]),
        ],
        remove=captured.append,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, UninstallScreen)
        # Cursor starts on row 0 (rg); space selects only that one.
        await pilot.press("space")
        assert len(app.screen.selected) == 1
        await pilot.press("enter")          # accept → confirmation modal
        await pilot.press("enter")          # confirm
        await pilot.pause()                 # wait for _apply_removal to complete
    assert len(captured) == 1
    assert len(captured[0].paths) == 1
    assert Path("/opt/rg") in captured[0].paths
    assert Path("/opt/fd") not in captured[0].paths
```

Complete replacement for `test_uninstall_applied_summary_ban_and_path` — preserves `a` (select-all), adds confirmation `enter` and post-modal read of `remove_ban`/`remove_path_block` (100% coverage of the post-modal property read path):

```python
async def test_uninstall_applied_summary_ban_and_path() -> None:
    """Status text mentions ban and PATH lines when both are selected.
    Also verifies that remove_ban/remove_path_block read the browser's live
    selection correctly after the modal is dismissed (the post-modal read path)."""
    inputs = _uninstall_inputs(
        rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        has_path_block=True,
        remove=lambda _d: None,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")          # select all: tool + ban + path block
        assert screen.remove_ban is True
        assert screen.remove_path_block is True
        await pilot.press("enter")      # accept → confirmation modal
        await pilot.press("enter")      # confirm
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert screen.applied is True
        assert "ban removed" in screen.status.text
        assert "PATH wiring removed" in screen.status.text
```

Complete replacement for `test_uninstall_applied_summary_omits_tool_line_when_no_tool` — preserves the existing cursor-navigation (`down down space`) to reach the ban row, adds confirmation `enter` and `await pilot.pause()`:

```python
async def test_uninstall_applied_summary_omits_tool_line_when_no_tool() -> None:
    """Selecting only the ban (no tool) yields no 'Removed N tool(s).' line."""
    inputs = _uninstall_inputs(
        rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        remove=lambda _d: None,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        # rows: [#removable, rg, #environment, #ban] — step past the section header.
        await pilot.press("down", "down")  # onto the ban row
        await pilot.press("space")         # select only the ban
        assert screen.selected == set()    # no tool ids selected
        assert screen.remove_ban is True
        await pilot.press("enter")         # accept → confirmation modal
        await pilot.press("enter")         # confirm
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert screen.applied is True
        assert "tool(s)" not in screen.status.text
        assert "ban removed" in screen.status.text
```

Add two new tests:

```python
async def test_uninstall_cancel_modal_removes_nothing() -> None:
    captured: list[UninstallDecision] = []
    rows = [_removable_row(_tool("rg"), [Path("/opt/rg")])]
    app = _app(uninstall=_uninstall_inputs(rows=rows, remove=captured.append))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")
        await pilot.press("enter")  # accept → modal
        await pilot.press("escape")  # cancel
        await pilot.pause()
        assert captured == []
        assert screen.applied is False


async def test_uninstall_confirm_modal_shows_artifact_count() -> None:
    from installer.wizard_app import ConfirmUninstall

    rows = [_removable_row(_tool("rg"), [Path("/opt/rg")])]
    app = _app(uninstall=_uninstall_inputs(rows=rows))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("space")
        await pilot.press("enter")  # accept → modal
        await pilot.pause()
        assert isinstance(app.screen, ConfirmUninstall)
        assert "1" in app.screen.summary  # one item to remove
```

The empty-selection refusal (`test_uninstall_empty_selection_refuses`) keeps its single `enter` — an empty accept must NOT open the modal (it shows the "select at least one" toast as before). Leave that test unchanged; it already asserts no removal.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_wizard_app.py -k uninstall -v`
Expected: the updated/added tests FAIL (today removal happens on the first `enter`; `ConfirmUninstall` does not exist).

- [ ] **Step 3: Implement the modal and route accept through it**

In `installer/wizard_app.py`, add a `ConfirmUninstall` modal (near `NavScreen`):

```python
class ConfirmUninstall(ModalScreen[bool]):
    """Confirm the one destructive, hard-to-reverse commit: deleting installed
    artifacts. enter/y confirm; escape/n cancel. Reversible actions (policies)
    deliberately get no modal — over-confirming trains click-through."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "confirm", "remove", show=True, priority=True),
        Binding("y", "confirm", "remove", show=False),
        Binding("escape", "cancel", "cancel", show=True),
        Binding("n", "cancel", "cancel", show=False),
    ]
    DEFAULT_CSS = """
    ConfirmUninstall { align: center middle; }
    ConfirmUninstall > Static { width: 60; border: round red; padding: 1 2; }
    """

    def __init__(self, summary: str) -> None:
        super().__init__()
        self.summary = summary  # public test seam

    def compose(self) -> ComposeResult:
        yield Static(
            Text.from_markup(
                f"[bold red]Remove {self.summary}?[/]\n\n"
                "This deletes installed artifacts and is not undoable.\n"
                "[dim]enter remove · esc cancel[/]"
            )
        )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
```

Refactor `UninstallScreen.on_tool_browser_accepted` to push the modal, and move the live removal into a callback. Replace the method body from the `decision = …` line onward:

```python
    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        event.stop()
        if self.applied or not self._entries:  # nothing to uninstall: keep the standing message
            return
        if not event.ids:
            self.status.set("Select at least one item to remove.", "warn")
            return
        self.app.push_screen(ConfirmUninstall(self._accept_summary(event.ids)), self._on_confirm(event.ids))

    def _accept_summary(self, ids: list[str]) -> str:
        tool_count = sum(1 for key in ids if key not in (_BAN_KEY, _BLOCK_KEY))
        parts: list[str] = []
        if tool_count:
            parts.append(f"{tool_count} tool(s)")
        if _BAN_KEY in ids:
            parts.append("the pip/npm ban")
        if _BLOCK_KEY in ids:
            parts.append("the PATH wiring")
        return ", ".join(parts)

    def _on_confirm(self, ids: list[str]) -> Callable[[bool | None], None]:
        # Callable[[bool | None], None] is the correct pyright-strict type:
        # ScreenResultCallbackType (textual/screen.py:83) passes Optional[ScreenResultType]
        # to the callback, i.e. bool | None for ModalScreen[bool].
        def run(confirmed: bool | None) -> None:
            if confirmed:
                self._apply_removal(ids)
        return run

    def _apply_removal(self, ids: list[str]) -> None:
        paths: list[Path] = []
        for key in ids:
            paths.extend(self._by_key[key].paths)
        decision = UninstallDecision(
            paths=tuple(paths),
            remove_ban=self.remove_ban,
            remove_path_block=self.remove_path_block,
        )
        try:
            self._remove(decision)
        except OSError as exc:
            self.error = str(exc)
            self.status.set(
                f"Uninstall failed: {exc}. Check permissions, then press enter.",
                "error",
            )
            return
        self.error = None
        self.applied = True
        tool_count = sum(1 for key in ids if key not in (_BAN_KEY, _BLOCK_KEY))
        self.status.set(self._applied_summary(tool_count), "ok")
```

Note: `remove_ban`/`remove_path_block` read the browser's live selection, which is unchanged while the modal is open, so they stay correct in `_apply_removal`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -k uninstall -v`
Expected: PASS.

- [ ] **Step 5: Full gate and commit**

```bash
make validate && make test
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "feat: confirm the destructive uninstall commit

enter now opens a ConfirmUninstall modal summarizing the artifact count;
removal runs only on confirm. Reversible actions (policies) keep no modal.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Fix the async navigation stack-invariant race

`show_view()` updates `current_view` synchronously while `pop_screen()`/`push_screen()` apply asynchronously. Rapid `1`–`5` presses can interleave with an in-flight transition, break the `[catalog]` / `[catalog, <view>]` invariant, and wedge navigation (the "1–5 stop responding" symptom). Serialize transitions with `await` so each completes before the next runs.

**Files:**
- Modify: `installer/wizard_app.py` (`show_view`, `action_show`, `action_back`, `on_mount`, `_navigate`)
- Test: `tests/test_wizard_app.py`

**Interfaces:**
- Consumes: Textual's awaitable `App.push_screen` / `App.pop_screen`.
- Produces: `show_view`/`action_show`/`action_back`/`on_mount`/`_navigate` all become `async` coroutines; each stack mutation is awaited so the one-deep invariant holds under rapid navigation. `_navigate` is passed as an async callback to `push_screen`; Textual awaits it via `call_next`.

- [ ] **Step 1: Write the invariant regression test**

Add to `tests/test_wizard_app.py` (import `CatalogScreen` from `installer.catalog_tui`):

```python
async def test_rapid_view_switching_keeps_stack_one_deep() -> None:
    """Rapid 1–5 presses must not corrupt the [catalog] / [catalog, <view>]
    stack invariant or wedge navigation (the 'keys stop responding' bug)."""
    from installer.catalog_tui import CatalogScreen

    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2", "3", "4", "5", "1")
        assert app.current_view == "catalog"
        assert isinstance(app.screen, CatalogScreen)
        # The catalog is the app's base screen (get_default_screen), so it is
        # never pushed or popped — it is always the permanent bottom of the stack.
        # After navigating back to "catalog", the stack is [catalog] (depth 1).
        assert len(app.screen_stack) == 1  # back to just the catalog base
        # not wedged: a subsequent press still navigates
        await pilot.press("3")
        assert app.current_view == "fix"
        assert len(app.screen_stack) == 2
```

Attempt to reproduce the raw race first (best effort): drive the keys without intermediate awaits via `app.post_message`/queued `pilot.press` and confirm the invariant breaks pre-fix. If a deterministic red is impractical under the pilot (which awaits between presses), proceed — the fix is correctness-by-construction and this test is the standing guard.

- [ ] **Step 2: Run the test (record current behavior)**

Run: `uv run pytest tests/test_wizard_app.py -k rapid_view_switching -v`
Expected: document whether it reproduces the wedge (FAIL) or passes under the pilot. Either way it becomes the regression guard.

- [ ] **Step 3: Serialize the transitions**

In `installer/wizard_app.py`, make the navigation path async and await each mutation:

```python
    async def on_mount(self) -> None:
        if self._initial_view != "catalog":
            await self.show_view(self._initial_view)

    async def show_view(self, name: str) -> None:
        # Await each stack mutation so a transition fully settles before the next
        # runs: this prevents a queued second nav from popping/pushing onto an
        # in-flight stack and breaking the [catalog] / [catalog, <view>] invariant.
        if name == self.current_view:
            return
        if self.current_view != "catalog":
            await self.pop_screen()
        if name != "catalog":
            await self.push_screen(self._views[name])
        self.current_view = name

    async def action_show(self, name: str) -> None:
        if not self._navigable():
            return
        await self.show_view(name)
```

Update `action_back` to await, and make `_navigate` an async callback (Textual 8.x's `push_screen` callback dispatch via `call_next` supports both sync and async callables — `ScreenResultCallbackType` is a union of both). Using `async def` here means the pilot awaits the callback before returning, so no palette tests need `pilot.pause()` edits:

```python
    async def action_back(self) -> None:
        if self._navigable() and self.current_view != "catalog":
            await self.show_view("catalog")

    async def _navigate(self, name: str | None) -> None:
        # Textual awaits async screen-result callbacks: textual/screen.py:83 defines
        # ScreenResultCallbackType as a Union including Callable[[Optional[T]], Awaitable[None]],
        # and textual/_callback.py's invoke does `if isawaitable(result): result = await result`.
        # Using async here means the pilot awaits this callback fully before resuming, so
        # palette tests asserting current_view immediately after enter do not need pilot.pause() edits.
        if name is not None:
            await self.show_view(name)
```

- [ ] **Step 4: Run the navigation tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -k "view or nav or rapid or initial or palette" -v`
Expected: PASS — including `test_number_key_navigates_to_each_view`, `test_policies_reachable_via_palette`, and the new invariant test.

- [ ] **Step 5: Full gate and commit**

```bash
make validate && make test
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "fix: serialize view navigation so rapid 1-5 cannot wedge the stack

show_view now awaits each pop/push so a queued navigation never mutates an
in-flight screen stack, preserving the one-deep invariant and keeping the
number keys responsive.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Numbered nav bar — circled keys + divider rule

Make the `1`–`5` mapping visible and give the top strip a real nav-bar feel: prefix each view in
the `WayfindingHeader` with its circled key glyph (❶–❺), widen the spacing, keep the active view
accent-bold, and add a horizontal `Rule` divider between the header and the mode badge so the nav
is clearly separated from the view content. (User-approved layout, 2026-06-26.)

**Files:**
- Modify: `installer/ui_common.py` (`WayfindingHeader.render_markup`; add `_view_key_glyph`; insert
  a `Rule` in `AppScreen.compose`; add `AppScreen.DEFAULT_CSS` to tighten the rule)
- Test: `tests/test_ui_common.py` (header numbering + chrome guarantee includes the `Rule`)

**Interfaces:**
- Consumes: `VIEW_LABELS`, `VIEW_MODES`, `ModeBadge`, `FooterBar` (existing chrome).
- Produces: `WayfindingHeader.render_markup` returns each view as `<circled-key> <label>`, the active
  one accent-bold; `AppScreen.compose` yields `WayfindingHeader → Rule → ModeBadge → body → status →
  FooterBar`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_ui_common.py`, update `test_wayfinding_header_highlights_active_view` (active is
`doctor`, the 2nd view → ❷) and add a numbering test:

```python
async def test_wayfinding_header_highlights_active_view() -> None:
    """The header numbers every view (❶–❺) and marks the active one accent-bold."""
    from installer.ui_common import WayfindingHeader

    class _Host(App[None]):
        def compose(self) -> ComposeResult:
            yield WayfindingHeader(active="doctor")

    app = _Host()
    async with app.run_test(size=(100, 5)):
        markup = app.query_one(WayfindingHeader).render_markup()
        assert "[bold $accent]❷ Doctor[/]" in markup
        assert "[bold $accent]❶ Catalog[/]" not in markup
        assert "[dim]❶ Catalog[/]" in markup


def test_wayfinding_header_numbers_each_view_in_order() -> None:
    from installer.ui_common import VIEW_LABELS, WayfindingHeader

    markup = WayfindingHeader(active="catalog").render_markup()
    for glyph, (_key, label) in zip("❶❷❸❹❺", VIEW_LABELS, strict=True):
        assert f"{glyph} {label}" in markup
```

Extend the chrome guarantee test to assert exactly one `Rule` (keep the existing ModeBadge /
FooterBar / StatusLine assertions); add `Rule` to its imports:

```python
    from textual.widgets import Rule, Static
    from installer.ui_common import AppScreen, FooterBar, ModeBadge, StatusLine, WayfindingHeader
    ...
        assert len(screen.query(WayfindingHeader)) == 1
        assert len(screen.query(Rule)) == 1
        assert len(screen.query(ModeBadge)) == 1
        assert len(screen.query(StatusLine)) == 1
        assert len(screen.query(FooterBar)) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_common.py -k "wayfinding or yields_header" -v`
Expected: FAIL — current `render_markup` has no glyphs; compose has no `Rule`.

- [ ] **Step 3: Implement**

In `installer/ui_common.py`, add the glyph helper near `VIEW_LABELS`:

```python
def _view_key_glyph(index: int) -> str:
    """The circled-digit nav key for the view at `index` (❶=0 … ❿=9), matching the
    1-based number key that navigates to it."""
    return chr(0x2776 + index)
```

Rewrite `WayfindingHeader.render_markup` to number each view and widen the gap:

```python
    def render_markup(self) -> str:
        # Each view shows its circled key so the 1–5 mapping is always on screen
        # (recognition over recall). The active view is accent-bold; the rest dim.
        parts = [
            f"[bold {self._accent}]{_view_key_glyph(index)} {label}[/]"
            if key == self._active
            else f"[dim]{_view_key_glyph(index)} {label}[/]"
            for index, (key, label) in enumerate(VIEW_LABELS)
        ]
        return "    ".join(parts)
```

Add `Rule` to the `textual.widgets` import in `ui_common.py`, give `AppScreen` a `DEFAULT_CSS` that
pins the rule tight, and insert the `Rule` in `compose`:

```python
from textual.widgets import DataTable, Rule, Static
```

```python
class AppScreen(Screen[None]):
    """Base scaffold: WayfindingHeader + a divider Rule + ModeBadge + the subclass
    body + StatusLine + FooterBar. The chrome is guaranteed so a screen can never
    ship without nav."""

    DEFAULT_CSS = "AppScreen > Rule { margin: 0; color: $accent; }"

    ...

    def compose(self) -> ComposeResult:
        yield WayfindingHeader(active=self._view, accent=self._accent)
        yield Rule()
        yield ModeBadge(VIEW_MODES[self._view])
        yield from self.compose_body()
        yield self.status
        yield FooterBar(self._view)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_common.py -v`
Expected: PASS. Also search for and update any other test asserting the old header text
(`uv run pytest tests/ -k header -v`); the uninstall red-accent test still passes because the active
entry remains `[bold red]…`.

- [ ] **Step 5: Full gate and commit**

```bash
make validate && make test
git add installer/ui_common.py tests/test_ui_common.py
git commit -m "feat: number the nav bar with circled keys and a divider rule

Each view shows its 1-5 key (❶–❺) so the mapping is always on screen; a Rule
separates the nav from the view content. Active view stays accent-bold.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

> **Visual confirmation required:** because the rule color/margin and inter-view spacing cannot be
> judged from headless tests, after this task render a real screenshot (Textual `save_screenshot`)
> of one screen and confirm the look before considering it done; tune the `Rule` color and the join
> spacing if needed.

---

## Self-Review

**Spec coverage:**
- D1 keys (space=toggle, enter=proceed): Policies → Task 1; Fix → Task 2; Catalog/Uninstall already `space`/`enter` (unchanged, covered by footer hints in Task 4). ✔
- D2 mode badge: Task 3 (ViewMode/VIEW_MODES/ModeBadge, all five views, hollow/filled glyph rule, kept row indicators). ✔
- D3 two-zone footer + Doctor `(read-only)`: Task 4. ✔
- D4 uninstall confirmation (reserved for the destructive commit; Policies excluded): Task 5. ✔
- D5 navigation race fix: Task 6. ✔
- Non-goals (no deferred-commit Policies; no merged `[x]`/`●` glyphs; keyboard-only; no new views): respected — Policies stays live (Task 1), row indicators untouched (Task 3 keeps `mark`/`_state_cell`). ✔

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code; every test step shows the assertion. ✔

**Type consistency:** `ViewMode(label, glyph, style, hint)` defined in Task 3 and used by `ModeBadge`; `VIEW_MODES`/`FOOTER_ACTIONS` keyed by the same five view names as `VIEW_LABELS` (asserted by `test_view_modes_cover_every_view`/`test_footer_actions_cover_every_view`). `ConfirmUninstall(summary: str)` with `.summary` seam matches the Task 5 test. `show_view`/`action_show`/`action_back`/`on_mount`/`_navigate` are all consistently `async` in Task 6; `_navigate` is an async callback that Textual awaits directly (no `call_later` needed). ✔

**Coverage note:** Every new branch has a test — badge per-mode strings, footer zone ordering + Doctor token, policy `enter`-inert, fix `a`-alias, uninstall confirm + cancel + summary, nav invariant. Keep `installer/` at 100%; if `make test` reports an uncovered line, add the missing case before committing that task.
