# Unified UI Redesign - Product Requirements Document (PRD)

> **For the implementing session:** This PRD is the handoff artifact. It is
> self-contained: a fresh session can read it and start **Phase 1** without
> re-deriving context. Each phase is meant to go through its own
> `superpowers:brainstorming` design-spec → `superpowers:writing-plans` plan →
> implementation cycle. This document is the roadmap that spawns those per-phase
> specs; it is **not** itself an implementation plan.

---

## Requirements Description

### Background

- **Business Problem**: The installer's interactive flow is fragmented and, in
  places, confusing. Selection happens in a Textual catalog screen, but
  confirmation, doctor, fix, uninstall, and the pip/npm ban are separate
  questionary/console flows outside it. Concrete pain points the user hit:
  - Pressing `Ctrl+P` opens **Textual's default command palette**, whose options
    ("maximize", etc.) all dead-end by closing the screen — an unexpected exit.
  - The catalog cursor starts on a **section-header row**, so the first `space`
    is a silent no-op.
  - Selecting **nothing** still proceeds through the post-install flow and asks
    "Enable the pip/npm ban?" — a prompt with no preceding context.
  - The doctor and fix report state but give **no guidance**: a user seeing
    "missing" or "duplicated on PATH" is not told *what to do* (reopen the
    terminal, open a new tab, "duplicates are expected until you reload").
- **Target Users**: Developers running the installer on macOS/Linux — both
  first-time users bootstrapping an environment and returning users auditing or
  uninstalling. They live in a terminal and expect a coherent TUI, not a chain
  of disconnected prompts.
- **Value Proposition**: One Textual application where the work happens — catalog,
  doctor, fix, uninstall, and policies are all **views inside a single app**,
  reachable from a command palette and direct navigation — and where the system
  **guides** the user with clear instructions and visual help at every step,
  especially around the shell-reload friction that PATH/ban changes inherently
  create.

### Feature Overview

- **Core Features**:
  1. **Unified Textual app** *(foundation)* — one application that hosts every
     view; navigation via our **own** command palette **and** direct tab/key
     bindings, both routing to the same view; Textual's default palette
     **disabled**. Folds in the three known catalog fixes (cursor → first tool
     row, empty-selection guard, palette disable).
  2. **Doctor/fix guidance + views** — a pure guidance core (each finding → its
     meaning + exact next step) that enriches the **console** output (kept for
     headless/non-TTY use) *and* backs **doctor/fix views inside the app**,
     reachable from the palette. Covers the shell-reload scenarios explicitly.
  3. **Uninstall view** — toggle off what's installed from within the app.
  4. **Policies tab** — the pip/npm ban (and future env tweaks) as a first-class
     "Policies" tab, **distinct from the package catalog** (not a fake package).

- **Feature Boundaries** — *what is NOT included*:
  - **Live in-UI execution (operador-en-vivo).** Under the chosen model the views
    *collect decisions* and *render guidance*; installs/doctor/fix/uninstall
    execute through the existing core **outside** the UI. Running long work live
    inside the UI with progress bars is an explicitly **deferred fork** (see
    Design Decisions).
  - No new install methods, registry tools, or executor changes (backlog F2/F3
    and the deferred registry batches).
  - No change to the `install.sh` bootstrap or the publish/go-live step.
  - No push / remote creation (OWNER step, standing instruction).

- **User Scenarios**:
  - *Install*: app opens on the catalog view; the user selects tools, may visit
    other views, and on accept the app returns the decision set; installs run via
    the core; a guidance screen summarizes results and next steps.
  - *Audit*: the user opens the doctor view (palette or `--doctor`), sees
    color-coded findings, each with its meaning and exact remediation, including
    whether a shell reload is required.
  - *Fix*: after applying the fix, the app explains that PATH won't change until
    the shell restarts and that transient duplicates are expected.
  - *Uninstall*: the user opens the uninstall view, toggles tools off, sees a
    preview (including ban artifacts), confirms, and gets a guided result.
  - *Policies*: the user opens the Policies tab, toggles the pip/npm ban on/off,
    and is told to open a new shell (or run `hash -r`) so cached command paths
    refresh.

### Detailed Requirements

- **Input/Output**:
  - Input: keyboard navigation in the single Textual app (palette, tab/key view
    switch, toggle, accept, abort) plus the existing CLI flags (`--doctor`,
    `--fix`, `--uninstall`, `--guard`/`--unguard`, `--all`, `--categories`,
    `--yes`), which remain the headless/non-interactive contract and, when run
    interactively, open the app on the corresponding view.
  - Output: rendered TUI views, a final **guidance/summary screen**, and the
    existing console reports for the non-interactive paths.
- **User Interaction** (decisor model): each view **collects decisions** (what to
  install, what to uninstall, which policies to toggle). On accept, the app
  returns the full decision set; execution and verification run through the
  existing pure core invoked from the `setup.py` composition root; the app then
  **shows a guidance screen**.
- **Data Requirements**: introduce a notion of **policy items** parallel to
  `Tool` (id, label, description, on/off state, idempotent apply/remove actions
  with an independently queryable status). The ban is the first policy, backed by
  the existing `installer/guards.py`. No registry schema change to `Tool`.
- **Edge Cases**:
  - Empty selection → a no-op with a clear message; it must **not** flow into a
    ban/policy prompt.
  - Non-TTY / `--yes` → unchanged headless behavior; the app is never launched;
    policies stay opt-in and are never silently enabled.
  - Cursor must never rest on a non-selectable section header at start.
  - `Ctrl+P` must open *our* palette, never an exit-on-select trap.
  - Palette command and key-binding for the same view must always land on the
    same view (single dispatch).
  - Guidance must distinguish "needs a new shell" from "fixed now".

## Design Decisions

### Technical Approach

- **Architecture Choice — decisor + guía (RECOMMENDED, adopted for this PRD).**
  The app is a **decisor + guide**: it gathers decisions and renders guidance,
  but installs/doctor/fix/uninstall continue to run through the **pure,
  fully-tested `installer/` core** invoked from the `setup.py` composition root.
  This preserves the project's central architectural seam — strict-typed,
  100%-covered pure logic vs. the untyped IO boundary — and avoids pulling
  long-running work and Textual workers into the UI. "Everything happens in one
  UI" is satisfied because every *decision* and all *guidance* live there; the
  *execution* stays behind the tested seam.

- **Single-app / dual-route navigation.** One Textual app hosts all views.
  Navigation has two routes that share one dispatch: our **own command palette**
  (a nav hub exposing a command per view and per action) and **direct tab/key
  bindings**. Both call a single "show view X" entry point, so the two routes can
  never drift. Textual's default palette is disabled (`ENABLE_COMMAND_PALETTE =
  False`). CLI flags still drive headless behavior and, interactively, open the
  app on the corresponding view.

- **Deferred fork — operador en vivo.** Running installs/doctor/fix live inside
  the UI with real-time progress is a richer UX but requires Textual workers,
  moving execution across the IO boundary, and rethinking how the 100%-covered
  core is exercised. It is **documented and parked**, not chosen. The single-app
  shell built here does not preclude it; a future session may revisit it.

- **Key Components** (existing files the phases touch):
  - `installer/catalog_tui.py` — the `CatalogApp` (`App[list[str] | None]`).
    Phase 1 evolves it into / mounts it under the unified app; sets
    `ENABLE_COMMAND_PALETTE = False`; fixes the initial cursor; adds the
    empty-selection guard; establishes the view-container + dispatch pattern.
  - `installer/doctor.py` + `installer/render.py` (`render_doctor`,
    `render_guard_status`) — Phase 2 adds the guidance core and the doctor/fix
    view rendering.
  - `installer/app.py` — `run_doctor`, `configure_path`, `run_uninstall`,
    `run_guard`; the orchestration the views call into (unchanged contracts).
  - `installer/guards.py` — the ban logic backing the first Policy item
    (unchanged; surfaced through the Policies tab; already returns per-name
    status used for partial-apply reporting).
  - `setup.py` — composition root; wires views to the core; remains the untested
    IO boundary (excluded from coverage/pyright by design).
  - A new **policy model** (parallel to `Tool`) for the Policies tab.

- **Interface Design**: views communicate with the core through the existing
  function seams in `installer/app.py`, which already take injected `console`,
  `confirm`, `which`, and path arguments — ideal for headless testing. Guidance
  is data the core returns or the render layer composes, not logic embedded in
  the UI.

### Constraints

- **Performance**: the app stays responsive; under the decisor model no
  long-running work blocks the UI thread (work runs after the app returns
  decisions). Headless test runs (`app.run_test`) must remain fast.
- **Compatibility**: macOS + Linux; zsh + bash. CLI flag contracts for
  non-interactive use are preserved exactly. `install.sh` bootstrap unaffected.
- **Security / Safety**: NEVER run a real `--doctor`/wizard/`--guard`/uninstall
  against the dev machine's home — split mode and shims rewrite real
  `~/.zshrc`/`~/.bashrc`/`~/.myshellrc` and write real shims into `~/.local/bin`.
  All UI work is tested **headlessly** (`app.run_test(size=…)` +
  `export_screenshot`) or via `--help`; policies remain **opt-in** and never
  silently enabled under `--yes`.
- **Scalability**: the policy model must accommodate future env tweaks beyond the
  ban (the backlog's "env policy / setup tweaks") without polluting the package
  catalog.

### Risk Assessment

- **Technical Risks**:
  - *Textual screenshot/NBSP brittleness* in headless assertions (spaces encode
    as `&#160;`/`\xa0`). Mitigation: assert on structure/labels, follow the
    existing catalog test patterns.
  - *Scope creep toward operador-en-vivo.* Mitigation: this PRD fixes the decisor
    model; any live-execution work is a separate future PRD.
  - *Shell-reload semantics are inherently confusing.* Mitigation: that is
    exactly what the doctor/fix guidance addresses; treat the wording as a
    first-class deliverable, not a footnote.
- **Dependency Risks**: Textual API for disabling the default palette / building
  a custom one. Mitigation: pin behavior with headless tests;
  `ENABLE_COMMAND_PALETTE` is a documented class attribute.
- **Schedule Risks**: four phases. The shell (Phase 1) is the foundation the rest
  mount into, so it must land first; thereafter Phases 2–4 are independent of one
  another and can be reordered or parallelized across sessions.

## Acceptance Criteria

### Functional Acceptance
- [ ] **Unified app**: one Textual app hosts catalog, doctor, fix, uninstall, and
  policies views; `Ctrl+P` opens our palette (Textual's default disabled); the
  palette command and the key-binding for a given view land on the same view.
- [ ] **Catalog fixes**: the cursor starts on the first **selectable tool row**;
  an empty selection is a clear no-op and never proceeds to a policy prompt.
- [ ] **Doctor/fix guidance**: every doctor finding renders a plain-language
  meaning **and** an exact next step; PATH-change findings state that a shell
  reload is required and that transient duplicates are expected until reload —
  in both the console output and the in-app doctor/fix views.
- [ ] **Uninstall view**: the user can toggle installed tools off inside the app,
  see a preview (including ban artifacts when present), confirm, and remove them.
- [ ] **Policies tab**: a first-class "Policies" tab lists the pip/npm ban as a
  toggle, separate from package rows; toggling it applies/removes both layers
  (shims + aliases) via `installer/guards.py`, reports per-layer status, and
  shows the reload guidance.
- [ ] Non-interactive paths (`--all`, `--categories`, `--yes`, `--doctor`,
  `--guard`, etc.) behave exactly as before; the app is not launched without a
  TTY.

### Quality Standards
- [ ] **Code Quality**: `make validate` green (ruff, ruff format, pyright strict,
  bandit, vulture, shellcheck). English-only. Coherent commits on `main`.
- [ ] **Test Coverage**: `make test` green; **100% coverage maintained** on the
  pure `installer/` core. UI tested headlessly; `setup.py` stays the
  coverage/pyright-excluded IO boundary.
- [ ] **Safety**: no test or smoke run mutates the real home directory.
- [ ] `make validate && make test` pass on the exact tree of each commit.

### User Acceptance
- [ ] **User Experience**: no dead-end flows; every state transition is either an
  action with a preview/confirm or a guidance screen with next steps.
- [ ] **Documentation**: README + `make` target help reflect the single-app UI
  and the Policies tab. `memory/roadmap-status.md` updated as phases land.

## Success Metrics

Measurable signals that the redesign achieved its intent:

- **100%** of doctor/guard finding types render both a meaning and a concrete
  next step (asserted per finding type in tests).
- **Zero** interactive flows terminate without either an action or a guidance
  screen — specifically, empty selection and palette interactions never dead-end
  in an unexplained exit.
- **One** entry point: every view is reachable from inside the single app via
  both palette and key-binding, verified to resolve to the same view.
- **No regression** in the non-interactive CLI contract (flag behaviors covered
  by existing tests stay green).
- **100%** coverage retained on the `installer/` core across all four phases.

## Error & Interrupt Handling

The cross-cutting policy (per-view detail belongs in each phase's spec):

- **`Ctrl+C` anywhere** aborts cleanly with the existing contract — print
  "Aborted.", exit `130` (128 + SIGINT), no traceback. The app must honor this
  from any view.
- **A failed core action** (e.g., a shim that cannot be written, a permission
  error, an rc file that cannot be updated) surfaces on the guidance screen with
  what failed and what to try — never a silent failure.
- **Partial policy apply** reports per-layer state (shims vs. aliases)
  independently, leaning on the per-name status `installer/guards.py` already
  returns, so the user sees exactly what took effect.
- **Aborting a view** (without accepting) discards that view's pending decisions
  and returns to navigation; nothing is executed until the user accepts.

## Execution Phases

> Each phase is a roadmap entry. The implementing session should take the phase,
> run it through `superpowers:brainstorming` to produce a dated design spec in
> `docs/superpowers/specs/`, then `superpowers:writing-plans`, then implement.
> **Phase 1 (the shell) is the foundation the other views mount into and must
> land first.** Phases 2–4 are independent of one another thereafter.

### Phase 1: Unified Textual App + Navigation  *(START HERE — foundation)*
**Goal**: One app hosting all views, with dual-route navigation and the known
catalog fixes.
- [ ] Establish the single-app shell and the view-container pattern that Phases
  2–4 mount into.
- [ ] Set `ENABLE_COMMAND_PALETTE = False`; build our own palette (nav hub:
  a command per view/action) and direct tab/key bindings, both calling one
  "show view X" dispatch so they cannot drift.
- [ ] Fix the initial cursor to land on the first selectable **tool** row.
- [ ] Add the empty-selection guard: selecting nothing is a clear no-op that does
  not proceed to any policy prompt.
- [ ] Wire CLI flags to open the app on the corresponding view interactively
  while preserving headless behavior.
- [ ] Headless tests: palette ↔ key-binding resolve to the same view, initial
  cursor, empty-selection, `Ctrl+C` abort.
- **Deliverables**: the single-app shell + dual-route navigation + the three
  quick wins, tested.

### Phase 2: Doctor/Fix Guidance + Views
**Goal**: Turn doctor/fix from state reporters into guides, in console **and** in
the app.
- [ ] Build the pure **guidance core** first (independent, console-safe): each
  finding type (missing dir, not-on-PATH, duplicated-on-PATH, ban
  active/inactive, PATH-order warning) → its meaning + exact next step, including
  the shell-reload scenarios (reopen terminal, open a new tab,
  `source ~/.myshellrc`, `hash -r`, "duplicates are expected until reload").
- [ ] Enrich `render_doctor` / `render_guard_status` console output with the
  guidance (kept for headless/non-TTY).
- [ ] Add **doctor and fix views** inside the app (mounted in the Phase 1 shell,
  reachable via palette + key), rendering the guidance with visual help (panels,
  color-coded severity).
- [ ] Headless tests: each finding type yields its guidance (pure core); the
  views render the guidance.
- **Deliverables**: guided doctor/fix in both console and app, fully tested.

### Phase 3: Uninstall View
**Goal**: Move uninstall into the app under the decisor model.
- [ ] An uninstall view listing installed tools as toggles, reusing
  `plan_uninstall` / `guard_status` for the preview (including ban artifacts).
- [ ] Accept → call existing `run_uninstall` core (unchanged contract);
  guidance screen on completion (what was removed, any reload needed).
- [ ] Headless tests for the view + preview + confirm path.
- **Deliverables**: uninstall reachable and tested inside the app.

### Phase 4: Policies Tab
**Goal**: The ban (and future env tweaks) as a first-class, non-package tab.
- [ ] A policy model parallel to `Tool` (id, label, description, state, idempotent
  apply/remove with queryable status); seed it with the pip/npm ban backed by
  `installer/guards.py`.
- [ ] A "Policies" tab/view, visually distinct from package rows, with on/off
  toggles, per-layer status, and the reload guidance from Phase 2.
- [ ] Remove the post-install "Enable the pip/npm ban?" questionary prompt from
  `setup.py` once the tab owns this (the empty-selection confusion disappears).
- [ ] Headless tests for the tab, toggle apply/remove, per-layer reporting, and
  guidance.
- **Deliverables**: discoverable, separated policy management; ban no longer a
  stray post-install prompt.

---

**Document Version**: 1.0
**Created**: 2026-06-13
**Clarification Rounds**: 2
**Quality Score**: 98/100
**Status**: ✅ **Implemented (Phases 1–4 on `main`)**, plus a follow-on "shared
pattern" consolidation (AppScreen/WayfindingHeader/ToolBrowser/catalog-parity
uninstall) on branch `feat/unified-ui-shared-pattern`. Phase 4's anticipated
"future env tweaks" are now scoped in
`docs/prds/dependencies-and-shell-tweaks-v1.0-prd.md` (Workstream B).
*(Original handoff status: "Roadmap for handoff. No code this session. Implementing
session starts at Phase 1.")*
