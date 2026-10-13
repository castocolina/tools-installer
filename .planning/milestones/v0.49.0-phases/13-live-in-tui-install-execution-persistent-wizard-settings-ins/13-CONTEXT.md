# Phase 13: Live in-TUI Install Execution & Persistent Wizard Settings - Context

**Gathered:** 2026-09-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Move install execution — confirm, run commands, wire PATH, verify — to run
INSIDE the Textual app instead of dropping to plain-console `rich`/
`questionary` output the moment the catalog screen's `App.run()` returns
(confirmed today: `setup.py:596-598`'s `_select_catalog` is the only Textual
involvement in the whole flow; everything after in
`installer/app.py::run_wizard` lines 111-170 is plain console). Implement it
as a worker-thread-driven screen with a streaming log widget, headless-
capable via the existing `--all`/`--categories`/`--yes`/`--link-mode` CLI
flags. Separately, persist the `link_mode` choice (centralized/single/split)
instead of `_resolve_link_mode` (`setup.py:601-613`) prompting on every run
with no stored preference, and expose it as an adjustable setting inside the
TUI rather than a pre-TUI CLI/questionary prompt.

Surfaced by real-machine use of the shipped v0.49.0 installer (F1+F2 from
that session's audit): the in-TUI live-execution design was explicitly
deferred in `unified-ui-redesign-v1.0-prd.md:134-138` ("a future session may
revisit it") — this is that session.

</domain>

<decisions>
## Implementation Decisions

### Live-execution screen behavior
- **D-01:** Confirming install PUSHES a new Textual screen (same
  `push_screen`/`pop_screen` pattern `DoctorScreen` already uses,
  `installer/wizard_app.py:154`) rather than an overlay/modal over the
  catalog — no overlay pattern exists in the codebase today; reusing the
  existing push/pop convention is zero new mechanism. — **Reversibility:**
  reversible.
- **D-02:** On completion (success, failure, or partial), the screen STAYS
  showing the full log until the user presses a key — it does not
  auto-return to the catalog after a timer. `render_failure_details`/
  `render_handoff`/`render_postinstall_warnings` (`installer/app.py:163-168`)
  already assume the user reads this output attentively; auto-closing
  risks losing exactly that information. — **Reversibility:** reversible.
- **D-03 (locked earlier in this conversation, restated for downstream
  agents):** Execution runs live inside a log/text-area widget in the TUI
  (not summarized after the fact) — this was the user's original,
  standing request from a prior session, restated when this phase was
  scoped. — **Reversibility:** reversible.

### `feat/install-experience` — reference only, not a port target
- **D-04:** A prior, never-merged branch (`feat/install-experience`,
  diverged from `main` July 2026, still present as a worktree at
  `.worktrees/install-experience`) already implements almost this exact
  feature (`installer/install_screen.py`, `installer/install_plan.py`,
  wired into `wizard_app.py`). A read-only audit (see
  `13-AUDIT-install-experience.md`) found real UX/architecture problems in
  it AND a high (15-23h) cost to reconcile its 10 concrete type/signature
  collisions with how far `main` has since evolved (`Tool` fields now
  `Enum`-validated, `ExecutionEvent`/`ActionKey`/`ExecutionChoices` don't
  exist on `main`, `Method.kind` gained new variants, etc.).
  **Decision: research and planning must treat this branch as a design
  reference and a named anti-pattern list — never cherry-pick or port its
  code directly.** — **Reversibility:** one-way — treating it as portable
  and starting a port, then discovering the audit's collision list mid-way,
  would waste the 15-23h estimate on a rebuild that still inherits bugs A-C
  below; deciding now to rebuild clean avoids that sunk cost.
- **D-05:** The new implementation MUST avoid the three confirmed defects
  the audit found in the old branch, as hard constraints on the design (not
  suggestions):
  1. **No blocking modal loop before execution visibly starts.** The old
     branch set `started = True` before showing approval modals, then
     queued modal-after-modal with no visible sign that installation was
     "waiting" (`install_screen.py:378-397` in the old branch). Whatever
     approval/confirmation step this phase needs must show the user
     execution is queued/pending, not silently gate behind a modal stack.
  2. **Output must be attributed per tool, unconditionally** — never
     dependent on an optional injected parameter (the old branch's
     attribution vanished entirely when `captured_runner=None`,
     `session.py:182` in the old branch). Every line of streamed output
     must show which tool it came from.
  3. **No silently-swallowed prompt cancellation.** If a setting prompt
     (e.g. first-run link-mode choice) is dismissed/cancelled, the user
     must see why nothing happened next, not silently land back at the
     catalog (`wizard_app.py:946-968` in the old branch was the case that
     went silent).
  — **Reversibility:** reversible — these are design constraints on new
  code, not a claim about legacy code being kept.

### Claude's Discretion
- Exact Textual widget choice for the streaming log (`RichLog` vs a plain
  `TextArea` writable buffer) — implementation detail, as long as D-01/D-02/
  D-05.2 hold.
- Whether the worker-thread execution model is built from scratch or
  informed by (never copy-pasted from) `installer/install_plan.py`'s
  `ExecutionEvent`/`ExecutionState` shape as naming/structure inspiration
  only — the audit's collision list applies to REUSING the code, not to
  learning from its shape.

### Open Design Questions — NOT YET DECIDED

These three gray areas were selected for discussion but the conversation
pivoted to the `feat/install-experience` investigation (D-04/D-05) before
they were covered. They are real, unresolved decisions — research/planning
must either surface them again to the user or make an explicit,
recorded judgment call, not silently default:

- **Failure handling mid-run:** does a single tool's failure stop the whole
  batch (fail-fast), or does the batch continue with a running per-tool
  status list (✓/✗/pending), and can the user cancel mid-run? The existing
  `Summary`/`render_summary`/`render_skipped` machinery
  (`installer/app.py:160-169`) already tracks partial outcomes across a
  batch — whatever this phase decides should reuse that shape, not
  reinvent it.
- **Settings wizard scope and location:** does the "first-run wizard"
  cover ONLY `link_mode`, or does it also fold in other one-time
  preferences raised in the same real-machine audit (default-shell
  preference, headless-flag defaults)? And once set, where does the user
  adjust it afterward — a new dedicated Settings view (a fourth-ish nav
  entry, which needs explicit justification against
  `.claude/architecture.md`'s "one view registry" constraint), or folded
  into the existing `PoliciesScreen` (`wizard_app.py`), which is today's
  closest precedent for "a screen where installer-level settings are
  toggled"?
- **CLI flag vs. persisted setting precedence:** once a `link_mode` is
  persisted, does an explicit `--link-mode` flag on a later run override it
  for that run only, or does passing the flag also update the persisted
  value going forward?

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### This phase's own audit (mandatory first read)
- `.planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-AUDIT-install-experience.md`
  — the full read-only audit of `feat/install-experience`; D-04/D-05 above
  summarize it, but the file has the file:line evidence research/planning
  will need to avoid repeating each defect.

### The abandoned branch itself (reference only — do not import from it)
- `.worktrees/install-experience` (branch `feat/install-experience`) —
  `installer/install_screen.py`, `installer/install_plan.py`,
  `docs/superpowers/plans/2026-07-26-install-execution-experience.md`,
  `docs/superpowers/specs/2026-07-26-install-experience-and-agent-toolkit-design.md`,
  `docs/superpowers/checkpoints/plan-1-execution-ui.md` — read for design
  intent and to see the collisions D-04 names, never as a code source to
  copy from directly.

### Where this gap was originally scoped
- `docs/prds/unified-ui-redesign-v1.0-prd.md:134-138` — the original
  "deferred fork" note that parked in-TUI live execution as future work.
- `docs/superpowers/plans/2026-06-12-textual-catalog-wizard.md:7` — records
  that the original wizard design left "audit table, confirm, install, PATH
  wiring" untouched by the Textual migration — the root of today's gap.

### Existing patterns this phase must reuse, not reinvent
- `installer/wizard_app.py:154` (`DoctorScreen`) — the push/pop screen
  pattern D-01 reuses.
- `REQ-background-version-refresh-worker` (`.planning/REQUIREMENTS.md:86`)
  — the existing Textual `Worker`-based background-task convention,
  already proven in this codebase, that a new install-execution worker
  should follow.
- `installer/locations.py:45-65` (`rc_paths_for_mode`) and
  `installer/app.py:173-201` (`configure_path`) — the real PATH-wiring
  logic the in-TUI execution screen must call into, unchanged.
- `installer/cli.py:20-79` — the existing headless flags
  (`--all`/`--categories`/`--yes`/`--link-mode`) this phase's
  "headless-capable" requirement builds on, not replaces.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `installer/app.py::run_wizard` (lines 111-170) — today's confirm → resolve
  dependencies → audit → confirm → `run_installs` → render-summary sequence;
  this is the exact sequence that needs to move inside the TUI, so its
  ordering and the existing `render_*` helper functions
  (`render_dependency_notice`, `render_audit`, `render_summary`,
  `render_failure_details`, `render_skipped`, `render_handoff`,
  `render_postinstall_warnings`, `render_verification`) are the reference
  point for what the new screen's log must show — likely adapted from
  Rich-console output to log-widget lines, not redesigned from zero.
- `installer/run.py::run_command` — today's synchronous, non-capturing
  shell-out; whatever this phase's worker uses to actually execute install
  commands must capture stdout/stderr for streaming instead.

### Established Patterns
- One view registry / one navigation path / one apply workflow
  (`installer/ui_common.py` `VIEWS`, `.claude/architecture.md`) — any new
  screen or settings surface this phase adds must fit this existing
  constraint, not add a second navigation mechanism.

### Integration Points
- `setup.py:721` (`main`) and `installer/app.py::run_wizard` — the call
  site where console-based confirm/install/configure_path currently lives
  and where the new in-TUI flow replaces it.

</code_context>

<specifics>
## Specific Ideas

- The user's original standing request (from a prior session, restated when
  this phase was scoped) was specifically for a "text-area/log widget"
  inside the TUI — see D-03.
- The user directly commissioned the `feat/install-experience` audit rather
  than accepting a fresh design without checking prior work first — this
  reflects a general preference (not phase-specific, but relevant here) to
  check for prior/abandoned implementations before designing something that
  might already half-exist.

</specifics>

<deferred>
## Deferred Ideas

None — the discussion stayed within this phase's scope; the "Open Design
Questions" above are unresolved parts of THIS phase's domain, not deferred
to another phase.

### Reviewed Todos (not folded)
None — no matching todos found for this phase.

</deferred>

---

*Phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins*
*Context gathered: 2026-09-13*
