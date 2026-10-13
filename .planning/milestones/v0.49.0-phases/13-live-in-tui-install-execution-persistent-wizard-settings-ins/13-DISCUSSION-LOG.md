# Phase 13: Live in-TUI Install Execution & Persistent Wizard Settings - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-13
**Phase:** 13-live-in-tui-install-execution-persistent-wizard-settings-ins
**Areas discussed:** Live-execution screen behavior (fully); Failure handling,
Settings wizard scope/location, CLI flag precedence (selected, not yet
covered — superseded by the `feat/install-experience` investigation)

---

## Live-execution screen behavior

**Q1: Does the live execution replace the catalog screen (push) or overlay it (modal)?**

| Option | Description | Selected |
|--------|-------------|----------|
| Push nueva pantalla | Same `push_screen`/`pop_screen` pattern as `DoctorScreen` (`wizard_app.py:154`) | ✓ |
| Overlay/modal sobre el catálogo | Catalog stays visible behind it; no precedent in the codebase | |

**User's choice:** Push nueva pantalla (Recomendado)
**Notes:** No follow-up — user accepted the recommendation directly.

**Q2: What happens when installation finishes (success or not)?**

| Option | Description | Selected |
|--------|-------------|----------|
| Se queda mostrando el log hasta tecla | User reads the full result (failures, manual handoffs, warnings) before returning | ✓ |
| Vuelve sola al catálogo tras unos segundos | Less friction on the happy path, but risks the user missing failures/warnings | |

**User's choice:** Se queda mostrando el log hasta tecla (Recomendado)
**Notes:** No follow-up — user accepted the recommendation directly.

**Continue-or-next check:** User chose "Next area," but flagged a concern
before moving on: this area "parece regresión" — the user recalled
implementing in-TUI install execution on an old branch before, with output
that used to show on the CLI (brew/pnpm), then got moved into a TUI
text-area, with feedback given about it at the time.

---

## Investigation: `feat/install-experience` (triggered mid-discussion)

The user's regression concern led to a live investigation rather than
continuing the planned area-by-area discussion:

1. Searched git history/branches for prior work — found branch
   `feat/install-experience` (diverged July 2026, still present as worktree
   `.worktrees/install-experience`), containing a near-complete prior
   implementation: `installer/install_screen.py`, `installer/install_plan.py`,
   wired into `wizard_app.py`.
2. Searched planning docs for recorded feedback on that implementation — none
   found (only an unrelated mention of the worktree's existence in
   `12.2-REVIEWS.md`, about a different module's deletion-safety check).
3. Asked the user how to proceed given this finding. **User's choice:**
   "Replantear como fase de PORT/reconciliación" (option 1) — but with an
   explicit follow-up request: verify whether the old implementation's
   feedback was ever recorded anywhere, and delegate a real code audit
   (not guesswork) to assess correctness, checking specifically for issues
   the user remembered: something unexpectedly "esperaba input," output not
   clearly attributed per package, and unclear boundaries between components.
4. First delegation attempt: `opencode` CLI with model `xai/grok-4.6`,
   given a worktree audit task. Killed once by a system OOM signal on the
   first attempt (memory pressure turned out to be a momentary spike, not
   a real constraint — confirmed via `free -h`'s `available` column on a
   later recheck). A second attempt got stuck: the model tried to read
   outside its own worktree (`../main`, `../.worktrees/*`) to diff against
   `main`, which the permission layer auto-rejected, and the run stalled.
5. **User's follow-up instruction:** if delegating a direct audit, use a
   Haiku-model subagent equipped with modern CLI tools (`rg`/`bat`/`fd`/`sd`)
   instead of continuing to fight the `opencode` session.
6. Stopped the stuck `opencode` background task; dispatched a Haiku
   subagent instead, scoped to the same audit task but instructed to use
   `git diff`/`git show main:<path>` from inside its own worktree (avoiding
   the external-directory permission trip entirely) to assess port risk.
7. **Audit result** (full report: `13-AUDIT-install-experience.md`):
   confirmed all three of the user's remembered concerns with file:line
   evidence (input-blocking modal loop before the `starting` state is ever
   emitted; output attribution that silently disappears when a parameter
   is omitted, with no per-tool visual separation even when present;
   responsibility for the same decision split across three modules), plus
   a fourth defect (a settings-prompt cancellation that silently returns
   the user to the catalog with no explanation). Port-risk verdict: HIGH —
   10 concrete type/signature collisions against how far `main` has evolved
   since the branch split, estimated at 15-23 hours to reconcile, comparable
   to a clean rebuild.
8. **User's final instruction for this discussion:** "Update it" — write
   the audit's findings into `13-CONTEXT.md` as locked decisions (treat the
   branch as a design reference and a named anti-pattern list, never a
   literal port target) and stop the discussion here rather than continuing
   through the three originally-selected-but-not-yet-discussed areas.

---

## Claude's Discretion

- Exact Textual widget for the streaming log (`RichLog` vs a plain
  `TextArea`) — implementation detail, constrained by the locked decisions
  (D-01/D-02/D-05.2 in CONTEXT.md).
- Whether the worker-execution model borrows naming/structure inspiration
  from the old branch's `ExecutionEvent`/`ExecutionState` shape — allowed as
  inspiration only, never as copied code (per the audit's collision list).

## Deferred Ideas

None deferred to another phase. Three areas selected for discussion
(Failure handling mid-run, Settings wizard scope/location, CLI flag vs.
persisted-setting precedence) were never reached before the conversation
pivoted to the `feat/install-experience` investigation — these remain
**open, unresolved questions within this phase's own scope**, recorded as
such in `13-CONTEXT.md`'s "Open Design Questions" subsection, not deferred
elsewhere.
