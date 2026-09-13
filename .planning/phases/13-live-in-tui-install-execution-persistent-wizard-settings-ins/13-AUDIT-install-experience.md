# Phase 13: Audit of `feat/install-experience` (never-merged branch)

**Gathered:** 2026-09-13
**Purpose:** Before designing Phase 13's in-TUI live install execution from
scratch, a prior, never-merged branch (`feat/install-experience`, diverged
from `main` in July 2026: 89 commits ahead / 375 behind) was found to
already implement almost exactly this feature — `installer/install_screen.py`
(`InstallScreen`, `RoutineActionPrompt`, `ChecksumMismatchPrompt`) and
`installer/install_plan.py` (`InstallPlan`, `ExecutionEvent`,
`ExecutionState`), wired into `installer/wizard_app.py`. A worktree exists
at `.worktrees/install-experience`. This audit (a read-only agent
investigation) answers whether that work should be ported onto `main` or
treated only as a design reference.

## A. Input Blocking — Severity: HIGH

When `routine_approval` is toggled OFF (via the 'a' key), pressing enter to
"install" traps the user in a sequential modal loop instead of starting
execution:

- `installer/install_screen.py:378-387` — sets `self.started = True`
  *before* showing the first `RoutineActionPrompt` modal, then calls
  `_prompt_next_routine_action()`.
- `installer/install_screen.py:391-399` — each modal is pushed sequentially;
  the callback `_routine_action_decided` pops the next action and pushes
  another modal.
- **Design mismatch:** the branch's own design doc
  (`docs/superpowers/specs/2026-07-26-install-experience-and-agent-toolkit-design.md:11`)
  says "The screen updates to `starting` before it starts its worker," but
  `starting` is never emitted until *after* all routine actions are
  approved/skipped. The user has zero visibility that installation is
  queued behind a stack of modals.

## B. Live Output Attribution — Severity: HIGH

- `installer/session.py:83-91` (`_CapturedToolRunner._emit_line`) prefixes
  output as `{tool_id} [{method}]: {line}` **only if** `captured_runner` is
  injected.
- `installer/session.py:182` — if `captured_runner=None`, the plain
  `runner` is used with **no attribution at all**.
- `installer/install_screen.py:463-478` — even when attribution exists,
  every tool's output lands in one shared `RichLog` with no visual section
  break per tool; output from tool A and tool B runs together
  indistinguishably.
- **Design mismatch:** the same design doc (line 13) describes "a per-tool
  live-output pane" — the implementation uses one shared log, not per-tool
  panes.

## C. Component Boundaries — Severity: MEDIUM

Three modules share execution responsibility with no clean separation:

- **`installer/install_screen.py`** (~516 lines) mixes modal-screen
  definitions, plan-text formatting, approval-toggle logic, **control-flow
  branching** (decides whether to enter the routine-action loop,
  lines 371-389), **worker-thread orchestration**, and event-sink logic —
  all in one class.
- **`installer/session.py::run_plan`** (lines 143-261) independently decides
  *what* `ExecutionEvent`s to emit (lines 173-180, 206-213, 252-257) — the
  screen doesn't own event semantics, session.py does.
- **`installer/install_plan.py`** defines `routine_action_approvals()`
  (lines 50-56) and dependency-reason tracking (58-72), but the actual
  *flow decision* ("show modals or not") lives in `install_screen.py:378`,
  not here.
- Net effect: testing "user unchecks routine approval, presses enter"
  requires mocking across all three modules — no single seam owns that
  decision.

## D. Other Rough Edges

1. **Dense, jargon-heavy approval copy** — `install_screen.py:274-302`
   explains "routine approval," "sensitive events," and "post-install
   actions" in one dense block with no guided distinction.
2. **Unexplained `skipped` vs `cancelled` outcomes** —
   `install_plan.py:18-20` (`ExecutionState` literal) has both, but neither
   the approval UI nor any user-facing copy explains the difference.
3. **Silent modal-cancel** — `installer/wizard_app.py:946-952` pushes
   `PathLinkModePrompt` *before* `_prepare_install()` pushes `InstallScreen`.
   If the user dismisses that modal (`None`), `wizard_app.py:968`'s
   `if link_mode is not None:` guard means nothing else happens — the user
   is silently returned to the catalog with no explanation.

## E. Port Risk — Verdict: HIGH

10 concrete collision points, found via `git diff feat/install-experience...main`
against the modules this code touches:

1. `Tool` fields (`priority`/`audience`) are plain strings on the branch;
   `main` validates them as `Enum` types (`installer/model.py`).
2. `ExecutionEvent` doesn't exist on `main` at all — `install_screen.py` and
   `session.py` both depend on it throughout.
3. `session.run_plan`'s signature is far larger on the branch (`on_mismatch`,
   `outcomes`, `action_context`, `approved_actions`, `skipped_actions`,
   `deferred_actions`, `captured_runner`, `interactive_runner`) than
   `main`'s current, simpler signature.
4. `ActionKey`, `ExecutionChoices`, `ExecutionState`, `MismatchChoice` are
   branch-only types with no `main` equivalent.
5. `_CapturedToolRunner` (session.py:52-91) has no counterpart on `main`.
6. `ActionContext`/`apply_actions` evolved differently on `main` — the
   branch's version has fields (`approved_actions`, `skipped_actions`) main's
   doesn't, and `apply_actions`'s return shape differs.
7. `Method.kind`'s closed set expanded on `main` since the branch split
   (`uv-tool`, `sdkman`, `host_setup`, `skill_pack` — none exist on the
   branch's `model.py`).
8. `SkillLifecycle` / `Tool.skill_lifecycle` are `main`-only additions the
   branch's `install_screen.py` never accounts for.
9. `Tool.post_install`, `owner_probes`, `uninstall` fields were added on
   `main` after the branch split; `install_screen.py`/`session.py` reference
   an older shape.
10. `Summary` gained fields on the branch (`cancelled`, `manual_required`)
    that don't exist on `main`'s current `Summary` dataclass.

**Effort estimate:** 3-5h low-level collision fixes (type/signature
reconciliation) + 8-12h architectural fixes (unblock the modal loop, add
real per-tool output attribution, disentangle the three-module control flow,
fix the silent `PathLinkModePrompt` cancel) + 4-6h testing/verification —
**15-23 hours total**, and that is before any of Phase 13's own new
requirements (headless-capable worker execution, persisted link-mode
setting) are added on top.

## Conclusion

The branch is evidence of **intent and precedent** (worker-thread execution,
push-screen pattern, modal-based sensitive-action approval, choosing
link-mode inside the wizard) — not a portable implementation. The port cost
(15-23h) is comparable to a clean rebuild, and a clean rebuild additionally
fixes the three confirmed UX/architecture problems (A, B, C above) rather
than inheriting them. **Decision: treat as a design reference and a
named list of anti-patterns to avoid, not a literal port target.**

---
*Produced by: a Haiku-model read-only subagent audit, 2026-09-13, following
a prior aborted attempt via `opencode`/`xai/grok-4.6` (killed once by a
system OOM signal, then stuck on out-of-worktree permission denials when
comparing against `main` from inside `.worktrees/install-experience`).*
