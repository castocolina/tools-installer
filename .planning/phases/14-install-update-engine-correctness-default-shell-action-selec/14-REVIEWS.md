---
phase: 14
reviewers: [opencode-fallback]
reviewed_at: 2026-09-14T09:32:00Z
plans_reviewed:
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-01-PLAN.md
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-02-PLAN.md
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-03-PLAN.md
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-04-PLAN.md
  - .planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-05-PLAN.md
models:
  opencode-fallback: "router-env/my-coding (reasoning=medium)"
model_sources:
  opencode-fallback: "pinned"
failed_lanes:
  opencode-plan-review: "still failing this project (see Round 1 note below); not retried this cycle since review.default_reviewers now points at opencode-fallback."
  opencode-fallback-cycle2-attempts-1-4: "this cycle's opencode-fallback lane failed 4 times before succeeding on the 5th attempt — attempts 1-3 (at reasoning=high) were killed by the harness's tracked-background-task low-memory heuristic before opencode could finish (~25-40min runs are apparently vulnerable to this); attempt 4 (after lowering to reasoning=medium and detaching the process from harness background-task tracking via setsid/nohup/disown to escape the memory-kill heuristic) failed fast with the same #1936 'no final assistant text' defect seen in Phase 13. Attempt 5, an immediate identical retry of the detached/medium-effort invocation, succeeded end to end."
---

# Cross-AI Plan Review — Phase 14

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

**Round 1 (5e6e1ac) — none.** All thirteen findings (2 HIGH, 5 MEDIUM, 6 LOW) were checked against
`14-CONTEXT.md`'s seven locked decisions before revision. None of them asks for anything a locked
decision forbids: every HIGH and MEDIUM is a mechanical defect in a plan's own test spec, gate or
sequencing, and the LOWs are stale counts plus two confirmations that existing design choices are
correct. Nothing in the review proposes changing which mechanism is reused (D-01), where consent
comes from (D-02, D-05), what a refusal says (D-03), the immutable block (D-04), the dispatch site
(D-06) or the zsh-only scope (D-07). Every finding was either incorporated into a PLAN.md or
dispositioned in that plan's `## Review Dispositions Ledger`; none was deferred.

Two reviewer claims were partially corrected during verification against the live tree, and both
corrections are recorded in the relevant plan's ledger rather than here, because neither is a
conflict with a user decision:

- **14-04 HIGH, vulture.** The recommended fix (move the dead-code gate to Task 3) was taken, but the
  stated mechanism was wrong: this project pins `min_confidence = 80` (`pyproject.toml:60`) and
  vulture reports unused functions and classes at 60% confidence, so the Task 2 gate was passing
  vacuously rather than failing. Verified empirically in this checkout.
- **14-05 LOW, fake-install count.** "Eleven" was correct, not nine: `grep -c ') -> InstallOutcome:'
  tests/test_execute_screen.py` returns 11; only nine of the eleven are literally named `install`,
  which is exactly the trap. The plan now names the two odd ones and tells the executor to enumerate
  by return type.

**Round 2 (this review) — none.** Cycle 2 confirms cycle 1's two HIGH and five MEDIUM findings were
correctly incorporated (verified against the live tree, not taken on the plan's word). It raises 6
new findings (0 HIGH, 3 MEDIUM, 3 LOW), none of which touches a locked CONTEXT.md decision — all are
plan-internal test-spec/gate defects (a typing mismatch, a vacuous source-index gate reintroduced in
14-05 of the same shape 14-04 just fixed, a markup-handling contradiction between a task's action and
behavior text, one test-fixture split). No `## Plan-Revision Conflicts` entry required.

<!-- gsd:plan-revision-conflicts:end -->


> **Reviewer-availability note (cycle 2):** `opencode-plan-review` was not retried this cycle since
> `review.default_reviewers` now points at `opencode-fallback` (see Round 1). The `opencode-fallback`
> lane itself failed 4 times before succeeding — attempts 1-3 at `reasoning=high` were killed by the
> harness's tracked-background-task low-memory heuristic mid-run (~25-40min invocations appear
> vulnerable to this regardless of actual system memory availability, which stayed stable at ~13GiB
> free throughout); attempt 4 (after lowering to `reasoning=medium` and detaching the process from
> harness tracking via `setsid`/`nohup`/`disown` to escape the memory-kill heuristic) failed fast with
> the same `#1936` "no final assistant text" defect documented in Phase 13. Attempt 5, an immediate
> identical retry of the detached/medium-effort invocation, succeeded end to end and produced the full
> 5-plan review below.

## OpenCode Review (opencode-fallback)

I'll review the five Phase 14 plans against the live tree, starting with the review skill and the cycle-1 dispositions.
The plans are already in the prompt; I'll ground every claim against the live tree and the cycle-1 dispositions.
This is a cycle-2 plan review against the live tree, not an orchestrator run. I'll ground each plan's claims in the current code.
I'll ground each plan against the live files it cites, plus the cycle-1 review ledger.
Cycle-1 findings are recorded; I'll now check the remaining integration points those revisions could have broken.
Checking the remaining integration points that could hide new cycle-2 issues.
A few claim-vs-code spots still look load-bearing — I'll check those next, including the cycle-1 "vacuous gate" shape in 14-05.
The 14-04 BIND-OK snippet may actually invoke the real script executor — I need to confirm that before calling it a finding.
A few remaining seams look load-bearing: UnifiedApp's execute storage, the 14-04 BIND-OK snippet, and progress-id collisions.
Checking architecture rule 5 wording and a couple of remaining verify-gate traps.
Checking whether a few verify gates would already pass, and whether `setup.py` already imports `dataclasses`.
Checking one remaining vacuous-gate pattern and the 14-04 fake-install line numbers.
Checking how catalog tests fake the update service — that typing choice could make 14-01's ExecuteInputs annotations fail pyright.
The catalog's ownership-is-None skip may contradict the unknown-status path — checking that test now.
The 14-05 `WIRE-OK` unattended check looks like the same vacuous-gate pattern cycle 1 already caught in 14-04. Verifying that, and the signature assertion, against live code.
Cycle 1's HIGH/MEDIUM items are actually in the revised plans. Remaining issues are new or regressions of the same vacuous-gate shape.

## 14-01

**Summary.** The tracer still targets the real bug path: `CatalogScreen.Decided` → `ExecuteScreen.on_mount` (`execute_screen.py:325-346`) → `resolve_dependencies` dropping installed tools (`deps.py:111-113`). Cycle 1's HIGH (`_build_app([], platform)` vs `execute is None` at `setup.py:382`) and MEDIUM (`begin` False at `catalog_tui.py:578-581`) are specified correctly now. One typing mismatch will fail pyright in a later wave.

**Strengths**
- Split stays beside the resolver; `deps.py:1-9` remains presence-only.
- Confirm gate is still `action_start` (`execute_screen.py:348-356`).
- `dataclasses.replace` in `_build_app` is the right shape: `_execute_inputs` (`setup.py:627-669`) runs before the services exist (`setup.py:572-624`).
- Latch refusal is now a skip-and-record branch, and `end()` is forbidden on the refused path.

**Concerns**
- **MEDIUM** — Task 1 types `ExecuteInputs.updates` / `version_refresh` as the concrete classes (`catalog_tui.py:219-220` does the same) but tells the executor to write duck-typed fakes. `tests/test_catalog_tui.py:1358-1367` constructs a real `UpdateService` with fake collaborators; a Protocol-shaped fake will not satisfy those annotations. 14-01's verify runs ruff only, so pyright does not fire until 14-05 Task 1 / `make validate`.
- **LOW** — Catalog skips when `ownership_of` is `None` (`catalog_tui.py:571-573`); the batch path blocking-`refresh`es instead. That is necessary for the unknown-status case, but it is a real call-site difference from the `u` keybind. Say so in the SUMMARY so it is not "fixed" later.

**Suggestions**
- Reuse `_update_service()`'s pattern (real `UpdateService`, fake `reresolve`/`runner`), or type the fields as a Protocol. Do not wait for wave 3 pyright.
- Add `uv run pyright` to Task 1's verify, or land the fakes as real service instances.

**Risk:** LOW — design is sound; the typing miss is planner-fixable and would not ship a wrong runtime path.

## 14-02

**Summary.** Closes the disclosure gap 14-01 documents (`execute_screen.py:342,539-547` still iterate `_ordered` only). Cycle 1's cancel-tail hole and the whole-file `except` gate are fixed correctly. One behavior bullet over-claims set equality.

**Strengths**
- Head, progress, and dispatch all read the one `_to_update` list — no second eligibility computation.
- Finish-handler sweep covers cancel, latch refusal, and a dead worker without a second worker-side list.
- LIVE-APPLY-OK is now scoped to `_run_updates` and asserts `run_live(` positively. A `try/finally` latch (14-01) does not trip `except`.
- Existing progress tests stay green: `_inputs()` defaults `installed` to False (`test_execute_screen.py:199`), so `_to_update` is empty for them.

**Concerns**
- **LOW** — Task 1 requires both "ids named before enter == ids the fake service receives" and "latch refusal means `run` is never called." Those cannot hold on the same fixture. Split them: set-equality is the happy path; latch/cancel assert skip + `not_attempted`.

**Suggestions**
- Two tests, two fixtures. Do not let the latch case weaken the disclosure assertion.

**Risk:** LOW — remaining nit is test-spec wording, not a missing capability.

## 14-03

**Summary.** Still the strongest plan. Cycle 1's already-installed consequence is now a stated decision plus a docstring requirement; D-04's one-way checkpoint is recorded. No new issue against the live tree.

**Strengths**
- Closed table in a new module; `POSTINSTALL_HOOKS` (`postinstall.py:272-276`) stays disjoint from `POST_INSTALL_ACTIONS` (`model.py:46-54`).
- Dispatch sits after the singular hook (`engine.py:149-154`) and cannot be reached from `ALREADY_INSTALLED` (`engine.py:116-117`) or `MANUAL_REQUIRED` (`engine.py:139-145`).
- `CHSH=no` stays on the script (`registry.toml:541`); `detect_path` at `:542` is the short-circuit.
- `Install` protocol is unchanged; `confirm_sensitive_action` is keyword-only with a default.
- Module has no execution seam; GATES-OK constructs `Platform(immutable=True)` the way `test_engine.py:18-19` already does.

**Concerns**
- None new.

**Risk:** LOW

## 14-04

**Summary.** Cycle 1's HIGH (vulture before the caller) and MEDIUM (vacuous `options.yes` index) are actually gone: vulture is Task 3, unattended is `-k sensitive_unattended`. One action/behavior contradiction remains on markup.

**Strengths**
- Adapter keeps `Install` byte-identical (`session.py:38-50`); I counted 6 / 11 / 10 / 2 fakes across the four test files, matching the ledger.
- `--yes` → `None` callback mirrors `app.py:157`.
- New renderer, not a widened `render_handoff` (`render.py:118-132` is MANUAL_REQUIRED-only).
- Fake-install list is now by return type; `grep` hits `test_app.py` at 75, 123, 155, 589, 1271, 1919.

**Concerns**
- **MEDIUM** — Task 1 action says model the new renderer on `render_handoff`, which is `console.print(f"  {line}")` with markup on (`render.py:131-132`). Behavior and RENDER-OK require `[this]` to survive. Those two instructions contradict. Copying the sibling will fail the gate.
- **LOW** — Extending `FakePrompter` (`test_app.py:46-61`) without keeping `confirm=` and `confirmed` valid will red the existing wizard tests. Default the new answer; do not replace the constructor.

**Suggestions**
- Print instruction lines with `markup=False` (or equivalent escape). Do not say "the way surrounding renderers print untrusted text" — they don't, and the verify forbids it.
- Keep `FakePrompter(confirm=True)` working.

**Risk:** LOW — markup will fail closed at Task 1 verify; it is a plan contradiction, not a missing gate.

## 14-05

**Summary.** Cycle 1's modal-typing and stale-`architecture.md` findings are fixed (`HELPER-UNCHANGED` matches the live signature exactly; the Phase 12.4 clause is at `architecture.md:340`). The unattended source-order gate is the same vacuous pattern 14-04 just deleted.

**Strengths**
- One worker-to-modal helper; new screen returns `str | None` like `ChecksumMismatchScreen` (`execute_screen.py:79,124-137`).
- `MismatchPromptOpen` has no test references (only `execute_screen.py:201,450,454,475`).
- 14-01's name-free modal count stays 1; this plan correctly forbids editing it.
- Attribution stays outermost: `attributed_install` (`execute_screen.py:154-174`) does not forward `confirm_sensitive_action`, so binding must wrap the inner install.
- Stale "zero production callers as of Phase 12.4" gate cannot collide with rule 5 (`architecture.md:23-25`).

**Concerns**
- **MEDIUM** — WIRE-OK does `s.index('unattended') < s.index('with_sensitive_confirm')` on `_execute_worker`. That file already contains `on_mismatch = None if self._inputs.unattended else self._ask_mismatch` (`execute_screen.py:398`). `s.index('unattended')` hits that line today, so the assertion passes even if the sensitive closure never reads the flag. Same defect as 14-04's deleted ORDER-OK (cycle 1 MEDIUM). The behavioral "modal never opens when unattended" case in `fails_when` is the real gate.

**Suggestions**
- Delete the source-index comparison. Keep HELPER-UNCHANGED, the `ask_from_worker` membership check, and the unattended pilot assertion.
- If a source check is wanted, match a unique snippet (`None if self._inputs.unattended else self._ask_sensitive_action`), not the bare word `unattended`.

**Risk:** LOW — D-05 is still enforced by the pilot; only the extra gate is cargo-culted.

## Cross-plan

Cycle 1's two HIGHs and five MEDIUMs are incorporated as claimed. The 14-04 vulture mechanism correction (vacuous at `min_confidence = 80`, `pyproject.toml:60`) is accurate. No revision reintroduced a locked-decision conflict.

New issues are all MEDIUM or lower: one transplanted vacuous gate (14-05), one typing/fake mismatch that pyright will catch a wave late (14-01), one renderer markup contradiction that fails closed (14-04). Wave order (01∥03 → 02∥04 → 05) still matches the code dependencies.

**Overall risk: LOW** — not because nothing is left, but because nothing left is red-by-construction against the live tree the way cycle 1's two HIGHs were. The remaining misses are the same class 14-04 already learned to replace with a behavioral test.

---

## Consensus Summary

Single reviewer (`opencode-fallback`) this cycle — no cross-reviewer consensus to compute. Its verdict is grounded (every finding cites `path:line` against the live tree, and it explicitly re-verified that cycle 1's fixes actually landed rather than trusting the plan text) and is treated at full weight. Zero HIGH findings this cycle: cycle 1's two HIGHs are confirmed fixed. Three MEDIUM findings — a typing mismatch (14-01's fakes won't satisfy `UpdateService`'s concrete-class annotations until pyright runs in a later wave), a reintroduced vacuous source-index gate in 14-05 (the same class of defect 14-04 was just fixed to avoid), and an action/behavior contradiction on markup handling in 14-04's new renderer. Three LOW findings are narrower test-spec/documentation nits.

### Agreed Strengths
N/A — single reviewer this cycle.

### Agreed Concerns
N/A — single reviewer this cycle; see per-plan Concerns above.

### Divergent Views
N/A — single reviewer this cycle.
