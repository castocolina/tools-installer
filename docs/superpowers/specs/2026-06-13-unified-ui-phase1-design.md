# Unified UI Redesign — Phase 1: Unified Textual App + Navigation — Design

Date: 2026-06-13
Status: approved (design sections + CLI-flag recommendation approved in terminal)
Source roadmap: `docs/prds/unified-ui-redesign-v1.0-prd.md` (Phase 1)

## Goal

Establish the single-app **shell** the other phases mount into: one Textual app
hosting all views, dual-route navigation (our own palette + direct keybindings)
through a single dispatch, plus the three known catalog quick-wins. Doctor, fix,
uninstall, and policies views are **navigable placeholders** in this phase; their
real bodies land in Phases 2–4.

Execution stays behind the pure `installer/` seam invoked from `setup.py`. The UI
only collects decisions and renders navigation — no behavior change to the core.

## Decisions (user-approved)

1. **Shell pattern: Textual Screens.** Each view is an isolated `Screen`. The
   catalog UI becomes a `Screen`; a thin `UnifiedApp` owns the palette + key
   dispatch and switches screens. Idiomatic; each future phase adds/replaces one
   Screen, independently testable; no collision with the catalog's grouping
   `Tabs`.
2. **Future views are navigable placeholders.** The palette lists all five views;
   the four not-yet-built ones are a shared `PlaceholderScreen` ("… — coming in
   Phase N"). This exercises the real dual-route dispatch end-to-end now and lets
   Phases 2–4 only swap a Screen body.
3. **Return contract stays `list[str] | None`.** Placeholder screens produce no
   decisions, so in Phase 1 the app returns "install these ids" or `None`.
   `setup.py` is essentially unchanged. Generalize to a typed outcome in
   Phase 3/4 when uninstall/policies actually collect decisions (YAGNI).
4. **CLI flags keep current behavior in Phase 1.** `--doctor/--fix/--uninstall/
   --guard/--unguard` still run their console core and exit — opening the app on
   a dead placeholder would be a regression. Phase 1 builds the `show_view(name)`
   mechanism and wires only the **default interactive run → catalog view**. Each
   later phase re-wires its own flag to open-on-view once that view is real
   (Phase 2: doctor/fix; Phase 3: uninstall; Phase 4: policies).

## Design

### 1. Modules and responsibilities

- **`installer/wizard_app.py`** *(new)* — `UnifiedApp(App[list[str] | None])`, the
  shell:
  - `ENABLE_COMMAND_PALETTE = False` — disables Textual's default palette (whose
    "maximize"/etc. options dead-end by closing the screen).
  - A single dispatch entry point `show_view(name)` that switches to the named
    Screen. Both navigation routes call only this, so they cannot drift.
  - **Route A — our palette:** `Binding("ctrl+p", "open_nav")` pushes a modal
    `NavScreen` listing the five views (and any actions); selecting one calls
    `show_view`. This replaces the disabled default palette with one fully under
    our control and trivial to test headlessly.
  - **Route B — direct keybindings:** one named key per view, each calling
    `show_view`.
  - Result: the catalog Screen's accept/abort sets the app's return value
    (`list[str] | None`); abort/`Ctrl+C` from any screen returns `None`.
- **`installer/catalog_tui.py`** *(refactor)* — `CatalogApp(App[...])` becomes
  `CatalogScreen(Screen[list[str] | None])`. The pure helpers (`group_tools`,
  `sort_for_table`) and all selection/rebuild/detail logic move unchanged; only
  the base class and the app→screen lifecycle hooks change. `accept`/`abort` now
  set the parent app's result rather than `self.exit(...)`.
- **`PlaceholderScreen`** *(new, in `wizard_app.py`)* — a generic Screen
  rendering "<View> — coming in Phase N", reused for doctor/fix/uninstall/
  policies. Navigable, no logic.

### 2. The three quick-wins

- **Initial cursor on first selectable tool row.** In `CatalogScreen.on_mount`,
  after the first `_rebuild()`, move the DataTable cursor to the first **tool**
  row, skipping a leading section-header row (present in grouped views like
  "category"). Today nothing moves the cursor, so the first `space` on a header
  is a silent no-op.
- **Empty-selection guard.** `action_accept` with an empty `selected` does **not**
  exit: it shows an inline message ("Select at least one tool, or press q to
  quit") and stays on the view. The app therefore **never returns `[]`** — only a
  non-empty list (accept) or `None` (`q`/`Ctrl+C`). This removes at the source the
  "empty selection flows into the ban prompt" path; `setup.py`'s existing `None →
  "Aborted."` handling covers the quit case.
- **Custom palette.** Covered by §1: `ENABLE_COMMAND_PALETTE = False` plus
  `ctrl+p → NavScreen`.

### 3. CLI flags (Phase 1 scope)

`main()` in `setup.py` keeps its current flag branches (`--doctor` → `_run_doctor`,
etc., each running the console core and exiting). The only change: the default
interactive selection path launches `UnifiedApp` (catalog view active) instead of
`CatalogApp` directly. Non-interactive contracts (`--all`, `--categories`,
`--yes`, and every action flag) behave exactly as before; the app is never
launched without a TTY.

## Testing (headless, 100% core retained)

Following `tests/test_catalog_tui.py` patterns (`app.run_test(size=…)`; assert on
structure/labels, not NBSP):

- **Dual-route dispatch:** navigating to a view via `NavScreen` (palette) and via
  the direct keybinding both resolve to the same active Screen.
- **Initial cursor:** in a grouping that starts with a section header, the cursor
  rests on the first tool row, not the header.
- **Empty-selection guard:** `action_accept` with nothing selected does not exit
  and surfaces the message; with a selection it returns the ids in catalog order.
- **Abort:** `Ctrl+C` from the catalog and from a placeholder screen returns
  `None` (root maps to exit 130).
- **Placeholders:** each placeholder screen is reachable and renders its
  "coming in Phase N" message.

The pure `installer/` core is untouched, so its 100% coverage is unaffected;
`setup.py` remains the coverage/pyright-excluded IO boundary.

## Out of scope (deferred to later phases / parked)

- Real doctor/fix/uninstall/policies view bodies (Phases 2–4).
- Typed decision-set outcome (Phase 3/4).
- Re-wiring action flags to open-on-view (each in its own phase).
- Live in-UI execution / progress bars ("operador en vivo") — parked fork.

## Acceptance (Phase 1 subset of the PRD)

- [ ] One Textual app hosts the catalog view + navigable placeholders; `Ctrl+P`
  opens our palette (default disabled); palette command and keybinding for a view
  land on the same view.
- [ ] Cursor starts on the first selectable tool row; empty selection is a clear
  no-op that never proceeds to a policy prompt.
- [ ] Non-interactive paths behave exactly as before; app not launched without a
  TTY.
- [ ] `make validate && make test` green on the exact committed tree; English-only;
  coherent commits on `main`.
