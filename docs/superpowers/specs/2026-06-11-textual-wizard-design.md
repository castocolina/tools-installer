# Textual Catalog Wizard (uzkit-parity F1) — Design

Date: 2026-06-11
Status: draft — awaiting user review
Prototype: `.superpowers/prototypes/wizard_tui.py` (run:
`uv run --with textual python .superpowers/prototypes/wizard_tui.py`) —
user picked Option B (Textual) over a questionary emulation.

## Problem

The predecessor project (uzkit) organized its catalog by category, priority
(P0–P3) and audience (AI / you / both) with a sorted, sectioned table. Our
registry carries `priority` and `audience` on all 49 tools, but the wizard
ignores them: the questionary menus show only category → tools. questionary
cannot bind custom keys (established fact: it binds only
space/a/i/enter/arrows), so "switch the grouping with ←/→" is impossible there.

## Decision (user-approved direction)

Replace the wizard's interactive **selection step** with a Textual app — one
screen whose grouping is switchable live — while everything around it
(audit table, confirm, install engine, PATH wiring, doctor/fix) stays as is.

## UX contract (matches the validated prototype)

One screen: tab strip on top, tool table, legend line, detail bar, footer.

- **Views** (tabs): Category · Priority · Audience · Status · Table.
  ←/→ cycles (wrapping); clicking a tab jumps directly (Textual has terminal
  mouse support). Grouped views render non-selectable section rows
  (`── P0 · essential ──`); rows sort priority→id within sections.
- **Table view**: flat, all 49 tools; clicking a column header re-sorts by
  that column (Pri / Tool / Cat / For / Inst).
- **Columns**: `Sel · Pri · Tool · Cat · For · Inst · What it does`.
  Colors: P0 bold red, P1 bold yellow, P2 blue, P3 dim; AI cyan, you magenta;
  installed green check, missing yellow circle. Legend line pins these.
- **Keys**: space toggle, `a` all, `i` invert, enter accept selection,
  `q`/ctrl-c abort. Footer shows them (Textual renders it from bindings).
- **Detail bar**: highlighted tool's id, description, priority label,
  audience. (Dependencies and AI-rationale text land here in F3/F2 — the
  slot exists, the fields don't yet.)
- Enter returns the selected ids and the app exits; the existing flow
  continues unchanged (rich audit table → "Install the selected tools?"
  confirm → install → summary). `q`/ctrl-c at the selection screen aborts
  the wizard exactly like declining today (prints "Aborted.", exit 0).

## Architecture

New module `installer/catalog_tui.py` — typed, inside the coverage gate:

- `class CatalogApp(App[list[str] | None])`: constructed with
  `tools: list[Tool]`, `installed: dict[str, bool]`,
  `blurbs: dict[str, str]` (category blurbs feed the Category view's section
  titles). `run()` returns the selected ids, or None on abort.
- Pure helpers exposed for direct unit tests (no app needed):
  `group_tools(tools, view)` → `list[tuple[str, list[Tool]]]` and
  `sort_for_table(tools, key)`. The app is a thin shell over them.

Integration (`setup.py` + `installer/app.py`):

- `Prompter` keeps its protocol but the interactive selection path changes:
  `_choose_tools` gains a `select_catalog: Callable[..., list[str] | None]`
  seam that replaces the two-step `select_categories`/`select_tools` flow
  when provided; `setup.py` passes a closure that runs `CatalogApp`.
  Non-interactive paths (`--all`, `--categories`) are untouched, as are the
  questionary confirm / link-mode / mismatch prompts.
- The old `selection.category_choices`/`tool_choices` stay for now: they
  still serve the `Prompter`-based tests and any fallback; removing them is
  a follow-up once the Textual path is proven (no speculative deletion in
  this change).

Dependencies:

- `textual` becomes a **runtime** dependency (pyproject `[project]`
  dependencies; uv lock refresh). It is pure Python, ships `py.typed`
  (pyright-clean), and pulls only rich + platform glue — rich is already ours.
- `pytest-asyncio` becomes a **dev** dependency: Textual's headless `Pilot`
  tests are async (`async with app.run_test() as pilot: await pilot.press(...)`).

## Error handling

- Non-TTY: `main` already gates the interactive path behind `isatty`; Textual
  is never started without a TTY. `--all`/`--categories` bypass it entirely.
- Terminal resize/small terminals: Textual reflows natively; no minimum-size
  guard (prototype verified at 110×35 and Textual degrades gracefully).
- Ctrl-C inside the app: Textual converts it to an app exit; `run()` returns
  None and the wizard prints "Aborted." (no traceback, exit 0 — consistent
  with today's KeyboardInterrupt handling at prompts).

## Testing (100% gate)

- `tests/test_catalog_tui.py`:
  - Pure helpers: grouping per view (sections, ordering, audience labels,
    status split), table sorting per column key — plain unit tests.
  - App behavior via `Pilot` (async): initial focus on the table; ←/→ cycles
    views (wrap both ways); tab click switches view; space toggles only tool
    rows (section rows inert); `a`/`i`; header click re-sorts in Table view
    only; enter returns selected ids; `q` returns None.
- `tests/test_app.py`: `_choose_tools` uses the catalog seam when provided
  and falls back to the two-step prompter when not.
- `setup.py` remains the IO boundary: the closure wiring is smoke-tested via
  `--help` only. NEVER run the real wizard against the dev machine's home.

## Out of scope

- Install-progress/summary screens in Textual (selection only; rich output
  stays).
- `requires` dependency field + drag-in (F3) and AI-rationale registry field
  (F2) — the detail bar reserves their slot.
- Removing questionary: confirm, link-mode, mismatch prompts keep it.
- Linux/Windows terminal-emulator certification beyond what Textual supports.
