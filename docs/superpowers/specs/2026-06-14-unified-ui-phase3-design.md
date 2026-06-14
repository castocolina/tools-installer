# Unified UI Redesign — Phase 3: Uninstall View — Design

Date: 2026-06-14
Status: approved (design approved in terminal)
Source roadmap: `docs/prds/unified-ui-redesign-v1.0-prd.md` (Phase 3)
Builds on: `docs/superpowers/specs/2026-06-13-unified-ui-phase2-design.md`

## Goal

Move uninstall into the unified app. The `"uninstall"` placeholder becomes a real
Screen that lists tools with removable userspace artifacts as toggles, plus
explicit toggles for the pip/npm ban and the managed PATH block. On accept it
**applies the removal live, in place** (mirroring Phase 2's `FixScreen`), then
re-renders an applied state with what was removed and the reload guidance.
Execution composes the existing pure core removers — no new deletion logic.

## Decisions (user-approved)

1. **Live-apply in-view (like `FixScreen`).** On accept the screen calls an
   injected removal closure synchronously (cheap, destructive file IO — no Textual
   worker), then flips to an applied state. The app's run value stays the catalog
   selection (`list[str] | None`); uninstall mutates the filesystem directly and
   returns nothing through `run()`. This is the same narrow un-parking of the
   "operador en vivo" fork that Phase 2 used for fix.
2. **List only tools with removable artifacts.** A tool is listed iff
   `plan_uninstall([tool], bin_dir)` is non-empty (download/raw/app artifacts on
   disk). Cask/brew/native-managed tools are absent — no dead toggles that remove
   nothing.
3. **Explicit extra toggles for the ban and the PATH block.** Rather than the
   console path's all-or-nothing behavior, the user composes three independent
   levers: selected tools, the pip/npm ban, and the managed PATH wiring. Each maps
   onto an existing core remover.
4. **Reuse the granular core removers, not `run_uninstall` verbatim.**
   `run_uninstall` hard-codes "remove everything" (artifacts + block + ban). The
   view instead composes `remove_paths` / `remove_shims` / `remove_ban_aliases` /
   `remove_managed_block` per the decision, so a partial uninstall never silently
   tears out PATH wiring or the ban for tools the user kept.

### Why the return contract does NOT change

The removal runs live in the view and mutates the filesystem directly; the app
still returns only the catalog selection. No typed decision-set outcome is pulled
forward (consistent with the Phase 2 decision). `--uninstall` interactively opens
the app on this view, identical to how `--doctor`/`--fix` open theirs.

## Design

### 1. The three levers → existing core removers

The "explicit toggles" choice is cheap because the deletion seams already exist
(`installer/app.py:282-287` calls all four unconditionally):

| Lever | Core remover(s) | Gating condition |
|---|---|---|
| Selected tool rows | `remove_paths(paths_for_selected)` | rows whose `plan_uninstall([tool])` is non-empty |
| pip/npm ban toggle | `remove_shims(bin_dir)` + `remove_ban_aliases(myshellrc)` + `remove_ban_aliases(rc)` per rc | shown only when `guard_status(bin_dir)` has any active shim |
| PATH-wiring toggle | `remove_managed_block(myshellrc)` | shown only when a managed block is present |

The view lets the user *compose* these instead of firing all of them. No new
deletion logic; the removers are reused as-is.

### 2. Modules and responsibilities

- **`installer/uninstall.py`** *(edit, pure)*:
  - `removable_tools(tools: list[Tool], default_bin_dir: Path) -> list[tuple[Tool, list[Path]]]`
    — the listable rows: each tool paired with its existing artifact paths, in a
    stable order, dropping tools with an empty plan. Keeps the screen logic-light.
- **`installer/shellrc.py`** *(edit, pure)*:
  - `has_managed_block(path: Path) -> bool` — true when `path` contains the managed
    PATH block markers (`_PATH_BEGIN`/`_PATH_END`). Gates the PATH-wiring toggle.
    (No such predicate exists today; `strip_block` and the markers do.)
- **`installer/wizard_app.py`** *(edit)*:
  - `UninstallScreen(Screen[None])` replaces the `"uninstall"` `PlaceholderScreen`.
  - A small frozen dataclass (e.g. `UninstallInputs`) bundles the screen's inputs
    (the `removable_tools` result, the ban status names, the managed-block flag,
    and the `remove: Callable[[UninstallDecision], None]` closure), so
    `UnifiedApp.__init__` gains one parameter rather than five loose ones.
- **`setup.py`** *(IO boundary, coverage/pyright-excluded)*:
  - Builds the `UninstallInputs`: computes `removable_tools`, `guard_status`,
    `has_managed_block(_MYSHELLRC)`, and a `remove` closure binding the core
    removers to `_DEFAULT_BIN_DIR`, `_MYSHELLRC`, and `_RC_PATHS` (removal targets
    the standard rc set so it cleans wherever the ban was written, regardless of
    the original link mode).
  - `_run_uninstall` gains the interactive branch: TTY →
    `_build_app(..., initial_view="uninstall").run()`; non-TTY / `--yes` →
    unchanged console `run_uninstall`. Mirrors `_run_doctor`/`_run_fix`.

### 3. `UninstallScreen` — layout, bindings, flow

Mirrors `CatalogScreen`'s toggle muscle-memory and `FixScreen`'s
preview → apply → applied lifecycle:

- **Layout**: a single `DataTable` (Sel / Item / Removes) holding the removable
  tool rows, then the ban and PATH-wiring rows when applicable, then a status
  line for refusals/results.
  - **AS-BUILT deviation (intentional):** the original draft proposed a *separate
    framed section below the table* for the ban/PATH rows ("not fake tool rows").
    The implementation instead folds them into the **same** `DataTable` as rows
    keyed `#ban`/`#path-block`, made **visually distinct** by `bold yellow` styling
    plus a `shell config:` prefix in the Removes column (vs. plain `bold` package
    rows). Rationale: one uniform toggle surface (same `space`/`a`/`i`/`enter`
    muscle-memory across every removable thing) is simpler and avoids a
    second focusable widget with its own navigation. The `ui-ux-designer` review
    (Task 10) evaluated this exact layout and judged the package-vs-config
    distinction **resolved** (VERDICT: SHIP), so the "visually distinct" intent is
    met without a separate section. The `#`-prefixed keys cannot collide with real
    tool ids (mirrors `CatalogScreen`'s `#section` convention).
- **State (public test seams)**: `selected: set[str]`, `remove_ban: bool`,
  `remove_path_block: bool`, `applied: bool`, `error: str | None`,
  `status_text: str` — following the Phase 1/2 public-seam convention.
- **Bindings**: `space` toggle highlighted row · `a` select-all tools · `i` invert
  · `enter` **Remove selected** · navigation stays the unified scheme (number keys
  / `Ctrl+P`); no `q` (consistent with Doctor/Fix — `q` would be ambiguous
  back-vs-abort).
- **Flow**: the table *is* the confirmation surface — nothing deletes until
  `enter`. Empty selection (no tools, no ban, no block chosen) → status-line
  refusal ("Select at least one item to remove."), no mutation. On `enter`, call
  the injected `remove(decision)` closure synchronously, then flip to the applied
  state.
- **Error path**: wrap the closure in `try/except OSError` exactly like
  `FixScreen.action_apply` — set `error`, re-render "what failed / what to try",
  leave the screen retryable, never crash (PRD: a failed core action surfaces,
  never a silent failure).
- **Empty state**: no removable tools, ban inactive, no managed block → render
  "Nothing to uninstall." (parity with `render_uninstall`'s nothing-line); no
  Apply.

### 4. Reload-guidance wording (applied state)

Inlined in the applied state (like `FixScreen`), consistent with `guidance.py`'s
vocabulary — *not* a guidance-core expansion (that core maps doctor/guard
*findings*, not post-action results):

- tools removed → "Removed N tool(s)." (counts selected tools, not artifact
  paths — the ban and PATH wiring get their own lines below, so "tool(s)" is the
  accurate unit)
- ban removed → "pip/npm ban removed — open a new shell or run `hash -r` so cached
  command paths refresh."
- PATH block removed → "PATH wiring removed — restart your shell to drop the
  managed dirs."

### 5. Navigation & CLI flags

- `VIEW_ORDER` and the dual-route dispatch (`show_view`, palette + number keys)
  are unchanged from Phase 1; `"uninstall"` simply resolves to a real Screen now.
- `initial_view="uninstall"` lets `--uninstall` open the app on this view
  (interactive only). The `_navigable()` guard and the
  `[catalog]` / `[catalog, <one view>]` stack invariant are preserved.
- Non-interactive `--uninstall` / `--yes` / no-TTY → unchanged console
  `run_uninstall`; the app is never launched.

## Testing (headless, 100% core retained)

- **`removable_tools`**: pure, 100%, table-driven — download/raw/app tools with
  on-disk artifacts are listed with their paths; cask/brew and absent-artifact
  tools are dropped.
- **`has_managed_block`**: pure, 100% — true with the markers present, false on an
  empty/marker-less file.
- **`UninstallScreen`** via `app.run_test`: `space`/`a`/`i` mutate `selected`;
  ban/PATH-block toggles flip their flags; empty-Apply refuses with the status
  line and mutates nothing; `enter` calls the closure against **`tmp_path`** (never
  real home) and flips to applied; OSError → `error` state, no crash; empty state
  renders the nothing-line.
- **Navigation**: uninstall reachable via palette **and** number key resolve to
  the same screen; `initial_view="uninstall"` opens on it; `Ctrl+C` aborts (exit
  130 at the root).
- **`setup.py`** stays the coverage/pyright-excluded IO boundary.

## Out of scope (deferred / parked)

- Live in-UI execution of **installs** (the long-running "operador en vivo" fork)
  — still parked; only fix (Phase 2) and uninstall (here) run live, both cheap IO.
- Policies tab (Phase 4) and the policy model. Phase 3 introduces **no ban
  model** — only a removal toggle that calls the same `remove_shims` /
  `remove_ban_aliases` seam Phase 4 will reuse, so the two never diverge.
- Typed decision-set return outcome — not needed; removal runs live.
- Changing the console `run_uninstall` all-or-nothing contract (it stays the
  non-interactive path).

## Acceptance (Phase 3 subset of the PRD)

- [ ] An uninstall view lists tools with removable artifacts as toggles, plus
  explicit ban and PATH-wiring toggles, reusing `plan_uninstall` / `guard_status`
  for the preview (including ban artifacts).
- [ ] Accept removes exactly the chosen levers live, then shows a guidance/applied
  state (what was removed, any reload needed); a failed removal surfaces in place.
- [ ] Reachable via palette + number key and via `--uninstall` (interactive);
  non-interactive paths behave exactly as before; the app is not launched without
  a TTY.
- [ ] `make validate && make test` green on the exact committed tree; 100%
  coverage retained on the `installer/` core; English-only; coherent commits.
