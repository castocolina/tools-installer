---
phase: 14
reviewers: [opencode-fallback]
reviewed_at: 2026-09-14T07:48:00Z
plans_reviewed:
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-01-PLAN.md
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-02-PLAN.md
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-03-PLAN.md
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-04-PLAN.md
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-05-PLAN.md
models:
  opencode-fallback: "router-env/my-coding (reasoning=high)"
model_sources:
  opencode-fallback: "pinned"
failed_lanes:
  opencode-plan-review: "configured default reviewer instance (opencode, model router-env/my-plan-review) failed twice this cycle — once via outer 1550s timeout (ETIMEDOUT), once via fast exit status 1 — both showing the agent loop ending its turn with no final assistant text (#1936). Config was changed to add a new instance opencode-fallback (opencode, model router-env/my-coding — the model proven reliable throughout Phase 13's review cycles) and default_reviewers was repointed at it; that lane succeeded on its first attempt this cycle."
---

# Cross-AI Plan Review — Phase 14

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

(none — no prior substantive REVIEWS.md existed for this phase; the immediately prior 14-REVIEWS.md was a total-failure stub with no conflict entries)
<!-- gsd:plan-revision-conflicts:end -->

> **Reviewer-availability note:** the project's configured default reviewer instance
> (`opencode-plan-review`, pinned to `router-env/my-plan-review`) failed twice this cycle with the
> same underlying defect (`#1936`: the opencode agent loop exits after tool calls with no final
> assistant message) — once via outer timeout, once via fast exit. `.planning/config.json` was
> updated to add `review.reviewer_instances.opencode-fallback` (opencode, model
> `router-env/my-coding`) and `review.default_reviewers` was repointed at it, matching the fallback
> that was reliable throughout Phase 13. That lane succeeded on its first attempt and produced a
> full 5-plan source-grounded review below.

## OpenCode Review (opencode-fallback)

I'll review the five Phase 14 plans against the live code, not the plan text alone. Loading the review skill and reading the files the plans claim to change.
The plans are inlined; I'll ground each claim against the live installer files they name.
This is a grounded plan review against the live tree, not an orchestrated re-review. Reading the files each plan cites.
I'll ground the plans against the live installer modules they name.
Continuing with execute-screen worker flow, composition root, and the post-install schema.
Checking composition root, version-status API, registry, tests, and a few plan-sensitive details.
Checking a few remaining integration points that could produce real findings.
Checking a few claim-vs-code mismatches that could be real findings.
Grounded against the live tree. Line numbers below are from this checkout.

## 14-01

**Summary.** The tracer targets the real bug path: `CatalogScreen.Decided` → `ExecuteScreen.on_mount` (`execute_screen.py:325-346`) → `resolve_dependencies` dropping installed tools (`deps.py:111-113`), not the stale `run_wizard` refs. Reusing `UpdateService.run` (`update.py:366-376`) and copying the `action_update_tool` predicate (`catalog_tui.py:568-570`) is the right split. One specified test cannot pass as written.

**Strengths**
- Split lives beside the resolver, not inside it — `deps.py:1-9` stays presence-only.
- Confirm gate is `action_start` (`execute_screen.py:348-356`), matching D-02 after Phase 13.
- `dataclasses.replace` in `_build_app` is the right composition-root shape: `_execute_inputs` (`setup.py:627-669`) runs before the services exist (`setup.py:572-624`).
- Structural gates (`MUTATION_GRADE` / `perform_update` absent from the screen; `satisfied_by_install` still in `deps.py`) match D-01.

**Concerns**
- **HIGH** — Task 1 behavior vs action disagree. Behavior says `setup._build_app([], platform)` yields `_execute is not None`. Action says replace only when `execute is not None`. Today `_build_app([], platform)` leaves execute `None` (`setup.py:382`); that is what `tests/test_setup.py:937` already calls. The identity assertion must pass `execute=_execute_inputs(...)` (as `_run_interactive_wizard` does at `setup.py:689-691`).
- **MEDIUM** — `_updates.begin` returning `False` is unspecified. Catalog treats that as a skip (`catalog_tui.py:578-581`). A sequential worker should too, not stall or raise.
- **LOW** — Documented preflight/progress gap is real (`execute_screen.py:336-342` still counts only `_ordered`) but 14-02 owns it.

**Suggestions**
- Rewrite the setup assertion to the wizard call shape, not the no-`execute` overload.
- If `begin(tool_id)` is `False`, skip that tool (or record a local refusal for 14-02); do not call `run`.

**Risk:** MEDIUM — design is sound; the setup test as specified is red by construction.

## 14-02

**Summary.** Closes the disclosure gap 14-01 documents: head and progress still iterate `_ordered` only (`execute_screen.py:342,539-547`). Reuses the same install/update split correctly.

**Concerns**
- **MEDIUM** — Cancel mid-update-tail. Install leftovers become `skipped` via `not_attempted` (`execute_screen.py:495-496`). That list is install-order only (`execute_screen.py:382,416-417`). Cancelled update rows would stay `pending` under a "Done." line unless 14-02 also marks untouched `_to_update` ids skipped.
- **LOW** — `except `-count gate is valid today (no `except ` in this file) and stays valid through 14-05's planned `try/finally`, but it will break if anyone adds a real `except` for a legitimate reason. Prefer asserting `run_live` wraps the re-probe.

**Risk:** LOW — small cancel/progress hole, not a design miss.

## 14-03

**Concerns**
- **LOW** — Already-installed `oh-my-zsh` (`detect_path` → `ALREADY_INSTALLED` at `engine.py:116-117`) never offers the action. Correct per single-direction trigger; worth one SUMMARY sentence so it is not "fixed" later.
- **LOW** — D-04 one-way reversibility is already locked; the planned SUMMARY checkpoint is enough.

**Risk:** LOW — this is the strongest of the five plans.

## 14-04

**Concerns**
- **HIGH** — Task 2 verify runs `uv run vulture` before Task 3 adds the production caller. Vulture only scans `installer/` (`pyproject.toml:59-61`); Task 2 tests do not count. Per-task commit will fail Task 2 (architecture rule 5 / the verify's own `fails_when`). Move vulture to Task 3, or land binding + `app.py` caller in one commit.
- **MEDIUM** — `ORDER-OK` uses `s.index('options.yes')`, which already hits the batch confirm at `app.py:148`, so it passes even if the sensitive closure never consults `options.yes`. Rely on the unattended pytest, or search a more specific snippet (`None if options.yes`).
- **LOW** — "Six fakes at 73, 121, 153, 587, 1269, 1917" drifted: `def install(` is at 67, 115, 147, 581, 1911 plus `record_install` at 1263. Also widen `_recording_install` (used at 675). Pyright will catch a miss.

**Risk:** MEDIUM — sequencing of the vulture gate can stall Wave 2.

## 14-05

**Concerns**
- **MEDIUM** — `ask_from_worker` is `ModalScreen[str | None] -> str | None` (`execute_screen.py:124-137`). A `ModalScreen[bool | None]` will not typecheck. Return `"yes"`/`"no"` (mismatch style) and map to `bool` in `_ask_sensitive_action`. Do not generalize the helper for one prompt unless you also re-type the mismatch path.
- **MEDIUM** — `architecture.md:337-341` still says `Tool.post_install` has "zero production callers as of Phase 12.4". A new Phase 14 section that leaves that sentence in place is a lying canonical doc. Edit that paragraph in Task 3.
- **LOW** — "Eleven fake installs" in `tests/test_execute_screen.py` is actually nine `def install(` (167, 417, 456, 670, 711, 792, 895, 969, 1050). Two in `test_wizard_app.py` (`_ok_install` at 4081, `sequenced` at 4149) is right. Also widen `_inputs(..., install: Install | None)` (`test_execute_screen.py:187`) or pyright will reject passing them into `ExecuteInputs.install: SensitiveInstall`.

**Risk:** LOW — typing and the stale architecture sentence are the only real traps.

## Cross-plan

**Overall risk: MEDIUM** — not because the design is wrong (it is the research recommendation, grounded in this tree), but because two verify blocks are red against the code they claim to lock (14-01 `_build_app([], platform)` vs `execute is None`; 14-04 vulture before `app.py` caller). Those are planner-fixable before execute; they should not wait for an executor to discover them.

---

## Consensus Summary

Single reviewer (`opencode-fallback`) this cycle — no cross-reviewer consensus to compute. Its verdict is grounded (every finding cites `path:line` against the live tree) and is treated at full weight per the workflow's single-reviewer contract. Two HIGH findings, both mechanical rather than design-level: a self-contradicting test spec in 14-01 (behavior text vs action text disagree on when `execute` gets set, and the action's own version is red against the live `_build_app([], platform)` return value), and a verify-ordering defect in 14-04 (the vulture gate runs a task before the production caller it needs to exist lands, in Task 3). Five MEDIUM and six LOW findings are refinements to already-sound designs, not structural objections — most name a specific brittle assertion (an `s.index()` substring match that would pass even if the real wiring were missing, a stale line-number count, a stale architecture.md sentence) rather than a missing capability.

### Agreed Strengths
N/A — single reviewer this cycle.

### Agreed Concerns
N/A — single reviewer this cycle; see per-plan Concerns above.

### Divergent Views
N/A — single reviewer this cycle.
