# Unified UI Redesign — Phase 2: Doctor/Fix Guidance + Views — Design

Date: 2026-06-13
Status: approved (design approved in terminal)
Source roadmap: `docs/prds/unified-ui-redesign-v1.0-prd.md` (Phase 2)
Builds on: `docs/superpowers/specs/2026-06-13-unified-ui-phase1-design.md`

## Goal

Turn doctor and fix from raw state reporters into **guides**, in the console
**and** inside the unified app. A pure guidance core maps every PATH/guard
finding type to a plain-language meaning plus an exact next step (including the
shell-reload scenarios). The two Phase 1 placeholders become real Screens: a
read-only Doctor view and a Fix view that applies the PATH fix live, in place.

## Decisions (user-approved)

1. **Doctor view is read-only.** It renders the live audit + guidance as
   color-coded blocks; navigation/quit only, no actions.
2. **Fix view applies the fix live, inside the view.** An Apply binding calls
   `configure_path` synchronously in the handler (fast rc-file IO — no Textual
   worker, no progress bar), then re-renders showing what was written + the
   reload guidance. This is a deliberate, *narrow* un-parking of the
   "operador en vivo" fork: it applies only to fix (cheap file IO), **not** to
   installs (the long-running case the PRD parked). Installs stay decisor-model.
3. **`--doctor` / `--fix` open the app on that view (interactively).** Both flags
   set the app's `initial_view`. Non-interactive paths (no TTY / `--yes`) are
   unchanged: they never launch the app and run the console core then exit.
4. **Guidance is a pure core (approach A).** `installer/guidance.py` returns
   structured `Guidance` items; both the console renderer and the Textual views
   consume the same list. No guidance logic lives in the UI or the audit module.

### Why the return contract does NOT change

Because the fix runs live in the Fix view, it mutates the filesystem directly;
the app still returns only the catalog selection (`list[str] | None`). No typed
decision-set outcome is pulled forward from Phase 3. The doctor audit is also
stable across a live fix: editing rc files does not change the *running*
process's PATH (that needs a shell reload), so a snapshot report stays truthful
for the whole session.

## Design

### 1. Modules and responsibilities

- **`installer/guidance.py`** *(new, pure — no IO, no rich/Textual imports)*:
  - `Severity = Literal["ok", "warn", "error"]`.
  - `@dataclass(frozen=True) class Guidance: title, meaning, next_step, severity`
    (`next_step` may be empty for the healthy/ok case).
  - `doctor_guidance(report: DoctorReport) -> list[Guidance]` — one item per
    finding (see content table); the healthy report yields a single `ok` item.
  - `guard_guidance(status: dict[str, bool], warning: str | None) -> list[Guidance]`
    — ban active/inactive + PATH-order warning. Silent (empty list) when the ban
    is inactive and there is no warning, matching today's `render_guard_status`.
- **`installer/render.py`** *(edit)*:
  - `render_doctor` consumes `doctor_guidance(report)` and prints, per item, the
    title, meaning, and next step (color by severity via rich styles). The
    `hint` parameter is **removed** — guidance replaces the single caller hint.
    Callers in `app.py`/`setup.py` updated.
  - `render_guard_status` consumes `guard_guidance(status, warning)`; unchanged
    silent behavior when nothing is active.
- **`installer/wizard_app.py`** *(edit)*:
  - `DoctorScreen(Screen[None])` and `FixScreen(Screen[None])` replace the
    doctor/fix entries in `_placeholders`; uninstall/policies stay placeholders.
  - New `initial_view: str = "catalog"`; on mount, if not `"catalog"`, push the
    target screen (stack becomes `[catalog, <view>]`, honoring the Phase 1
    invariant).
  - App receives `report: DoctorReport`, `guard_status: dict[str, bool]`,
    `guard_warning: str | None`, and `fix: Callable[[], None]` (a `configure_path`
    closure bound to the resolved paths + link_mode by the composition root).
- **`setup.py`** *(IO boundary, coverage/pyright-excluded)*:
  - Builds the `DoctorReport` (via the existing pure `audit_path`/`collect_bin_dirs`),
    the guard status/warning, and the `fix` closure; passes them to `UnifiedApp`.
  - Interactive `--doctor`/`--fix` set `initial_view`. The default interactive
    run still opens on the catalog. Non-interactive flags unchanged.

### 2. Guidance core content

`doctor_guidance` / `guard_guidance` map each finding type to meaning + next
step. Wording is a first-class deliverable (PRD success metric: 100% of finding
types render both a meaning and a concrete next step).

| Finding | Severity | Meaning | Next step |
|---|---|---|---|
| `broken` (declared, not on disk) | error | "`<dir>` is declared but does not exist yet." | "It is created when a tool installs there — nothing to do now." |
| `missing` (not on PATH) | warn | "`<dir>` is not on your PATH." | "Run `make fix`, then open a new terminal (or `source ~/.myshellrc`)." |
| `duplicated` (more than once on PATH) | warn | "`<dir>` appears more than once on PATH." | "Harmless — transient duplicates clear when you open a new shell." |
| healthy (no problems) | ok | "PATH looks healthy: all bin dirs present, on PATH, and unique." | (empty) |
| ban active | ok | "pip/npm ban active (`<names>` shimmed)." | "Open a new shell or run `hash -r` so cached command paths refresh." |
| PATH-order warning | warn | the existing `guard_path_warning` text | "Put the shim dir ahead of the real binary on PATH, then reopen the shell." |

### 3. The two Screens + the live-fix flow

- **`DoctorScreen`** — read-only. Builds the guidance list from the injected
  report + guard status/warning and renders each `Guidance` as a color-coded
  block (green/yellow/red by severity). Public test seam (e.g. `guidance` or the
  rendered text) following the Phase 1 `status_text` pattern.
- **`FixScreen`** — renders a **preview** (the rc files and bin dirs that will be
  wired) plus the reload guidance, with an Apply binding (e.g. `a`). Apply calls
  the injected `fix()` closure synchronously, then flips the screen to an
  **applied** state showing what was written + "restart your shell or
  `source ~/.myshellrc`". A public flag (e.g. `applied`) is the test seam. Quit
  without Apply writes nothing.

### 4. Navigation & CLI flags

- `VIEW_ORDER` and the dual-route dispatch (`show_view`, palette + number keys)
  are unchanged from Phase 1; doctor/fix simply resolve to real Screens now.
- `initial_view` lets `--doctor`/`--fix` open the app on the corresponding view.
- The `_navigable()` guard and the `[catalog]` / `[catalog, <one view>]` stack
  invariant are preserved.

## Testing (headless, 100% core retained)

- **`guidance.py`**: each finding type → asserts a non-empty meaning and (except
  the ok/healthy case) a non-empty next step, plus the expected severity. Covers
  the PRD success metric directly. Pure, 100%.
- **`render.py`**: `render_doctor`/`render_guard_status` console output carries
  the guidance for each finding type; healthy and inactive-ban cases unchanged.
- **`DoctorScreen`**: renders a block per severity; assert on labels/structure
  via the existing `_screen_text` NBSP-safe helper.
- **`FixScreen`**: Apply calls the injected `configure_path` against `tmp_path`
  (rc files written, view shows applied state); quit-without-Apply writes nothing
  — no real-home mutation.
- **Navigation**: doctor/fix reachable via palette **and** number key resolve to
  the same screen; `initial_view="doctor"/"fix"` opens on the right view;
  `Ctrl+C` aborts from both screens (exit 130 at the root).
- **`setup.py`** stays the coverage/pyright-excluded IO boundary.

## Out of scope (deferred / parked)

- Live in-UI execution of **installs** (the long-running "operador en vivo"
  fork) — still parked; only fix runs live here.
- Uninstall view (Phase 3) and Policies tab (Phase 4).
- Typed decision-set return outcome (Phase 3/4) — not needed here.
- Re-wiring `--uninstall`/`--guard` to open-on-view (their phases).

## Acceptance (Phase 2 subset of the PRD)

- [ ] A pure guidance core maps every finding type (missing dir, not-on-PATH,
  duplicated-on-PATH, ban active/inactive, PATH-order warning) to a meaning + an
  exact next step, including the shell-reload scenarios.
- [ ] `render_doctor`/`render_guard_status` console output renders the guidance.
- [ ] In-app Doctor view (read-only) and Fix view (applies live) are reachable
  via palette + number key and via `--doctor`/`--fix`; both render the guidance.
- [ ] Non-interactive paths behave exactly as before; the app is not launched
  without a TTY.
- [ ] `make validate && make test` green on the exact committed tree; 100%
  coverage retained on the `installer/` core; English-only; coherent commits.
