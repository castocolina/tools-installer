---
phase: 14
reviewers: [opencode-fallback]
reviewed_at: 2026-09-14T10:07:00Z
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
  opencode-fallback-cycle3-attempt-1: "cycle 3's opencode-fallback lane (detached, reasoning=medium from the start, learning from cycle 2) succeeded on its first attempt in ~15 minutes."
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

**Round 3 (this revision) — none.** All six cycle-2 findings (0 HIGH, 3 MEDIUM, 3 LOW) were checked
against `14-CONTEXT.md`'s seven locked decisions before revising, rather than assuming the cycle-2
reviewer's own "none of which touches a locked CONTEXT.md decision" claim. The check holds: the two
14-01 findings are about how a test constructs its doubles and about documenting a call-site
difference, and neither changes which mechanism the batch path reuses (D-01) or where consent comes
from (D-02); the 14-02 finding splits one test fixture into three and does not touch D-03's reason
wording; the two 14-04 findings are a renderer's markup handling and a test helper's constructor,
neither of which touches D-05's confirmation requirement or D-06's dispatch site; and the 14-05
finding deletes a verify gate while strengthening the enforcement of D-05's unattended rule, moving
it from a source-order string comparison to a behavioural pilot test. Nothing was deferred and
nothing was rejected; every finding was incorporated and dispositioned in the relevant plan's
`## Review Dispositions Ledger` under `### Round 2 — e23d32a`.

Every cycle-2 claim was re-verified against the live tree before being acted on, as in Round 1. All
six were accurate this cycle; three were extended during verification, and those extensions are
recorded in the plans' ledgers rather than here, because none is a conflict with a user decision:

- **14-01 MEDIUM, typing.** Accurate, and the fix was widened to all three of the reviewer's options
  at once rather than one: concrete annotations kept (matching `installer/catalog_tui.py:219-220`),
  doubles respecified as subclasses of the real services, and `uv run pyright` added to Task 1's own
  verify. Confirmed `uv run pyright` currently exits `0 errors, 0 warnings` on the untouched tree, so
  the new wave-1 gate is not red by construction. The same fix also removed a latent second problem
  the reviewer did not name: the latch-refusal fixture told the executor to make the acquire method
  answer `False`, which a real-service subclass would have had to fake anyway — it now takes the real
  latch for another tool, which is both simpler and a stronger assertion.
- **14-04 LOW, `FakePrompter`.** Accurate, and it is against Task 3, not Task 1 as the review's
  heading implies — `FakePrompter` is extended in Task 3's action. Quantified while verifying:
  fifteen call sites, not "other wizard tests" in the abstract, and the plan now cites all fifteen
  line numbers and gates the count.
- **14-05 MEDIUM, vacuous gate.** Accurate. The reviewer's fallback suggestion (match the full unique
  expression instead of the bare word) was recorded but deliberately not adopted — it pins the
  implementation's line formatting and adds nothing over the behavioural pilot, which is what 14-04
  concluded for the same defect one cycle earlier.

<!-- gsd:plan-revision-conflicts:end -->



> **Reviewer-availability note (cycle 3, FINAL — max_cycles=3):** the `opencode-fallback` lane
> (detached from harness background-task tracking via `setsid`/`nohup`/`disown`, `reasoning=medium`)
> succeeded on its first attempt this cycle, in about 15 minutes. Learning from cycle 2's 4 failed
> attempts (3 killed by a harness low-memory heuristic at `reasoning=high`, 1 fast `#1936` failure),
> this cycle started directly at the detached/medium-effort configuration that worked.

## OpenCode Review (opencode-fallback)

I'll review the five Phase 14 plans against the live tree, starting with the review skill and the files cycle 2's findings actually touch.
Using the GSD plan-review skill. I'll ground cycle-2's six fixes against the live tree, then check whether any fix introduced a new problem.
Cycle 3 is a live-tree review, not another CLI dispatch. I'll ground cycle-2's six fixes against the code those plans actually name.
Cycle 2 named six live-tree defects. I'll read those exact call sites next, then check whether the plan fixes match the code.
The first cycle-2 sites check out. Next I'll read the remaining files those six findings actually named.
The cycle-2 sites match the live tree. Next I'll confirm the six claimed plan fixes are actually in the plan files, and look for anything those fixes introduced.
Cycle 2's six findings are recorded. I'll now check the plan text itself to confirm each fix actually landed, and look for anything those edits broke.
Cycle-2 fixes are in the plan text. I'll now check the remaining live seams those edits could have broken.
A few remaining seams could still hide a cycle-3 issue. Checking those now.
I'll verify the remaining live-tree claims that could still hide a cycle-3 defect: FakePrompter call sites, BIND-OK's install path, and whether `setup.py` already imports dataclasses.

Cycle 2's six fixes match the live tree. Checking one last host-dependent test seam, then writing the review.

Cycle 2's six findings are confirmed fixed against the live tree. No new HIGH/MEDIUM. Writing the cycle-3 review.

## 14-01

**Summary.** Tracer still hits the real bug path: `CatalogScreen.Decided` → `ExecuteScreen.on_mount` (`installer/execute_screen.py:325-346`) → `resolve_dependencies` dropping installed tools (`installer/deps.py:111-113`). Cycle 2's MEDIUM (concrete-class fields vs duck-typed fakes) and LOW (ownership-is-None divergence) are specified correctly now: doubles are subclasses of the real services, `uv run pyright` runs in Task 1, and the blocking-refresh vs `catalog_tui.py:571-573` early-return is a recorded decision with a test.

**Strengths**
- Split stays beside the resolver; `installer/deps.py:1-9` remains presence-only.
- Confirm gate is still `action_start` (`installer/execute_screen.py:348-356`).
- `dataclasses.replace` in `_build_app` is the right shape: `_execute_inputs` (`setup.py:627-669`) runs before the services exist (`setup.py:572-624`); `execute` defaults to `None` (`setup.py:382`).
- Latch refusal is a skip-and-record branch driven through the real `begin()` lock (`installer/update.py:355-364`), and `end()` is forbidden on the refused path.
- `pyproject.toml:42-45` is strict over `tests/`; `_offline_service` (`tests/test_catalog_tui.py:983-1003`) and `_update_service` (`tests/test_catalog_tui.py:1358-1367`) are the right construction pattern.

**Concerns**
- None new. Cycle 2 MEDIUM/LOW are actually in the plan (subclass + pyright in Task 1 verify; `DELIBERATE DIVERGENCE` must_have + behavior bullet that the single-tool `refresh` is called).

**Suggestions**
- None required before execute.

**Risk:** LOW — design matches the live tree; the typing miss can no longer slip to wave 3.

## 14-02

**Summary.** Closes the disclosure gap 14-01 documents (`installer/execute_screen.py:342,539-547` still iterate `_ordered` only). Cycle 2's LOW (set-equality and latch-refusal cannot share a fixture) is split into named fixtures A/B/C. Cycle 1's cancel-tail hole and the whole-file `except` gate stay fixed.

**Strengths**
- Head, progress, and dispatch all read the one `_to_update` list — no second eligibility computation.
- Finish-handler sweep covers cancel, latch refusal, and a dead worker without a second worker-side list; install-side `not_attempted` (`installer/execute_screen.py:382,416-417,495-496`) structurally cannot cover update rows.
- LIVE-APPLY-OK is scoped to `_run_updates` and asserts `run_live(` positively. A `try/finally` latch (14-01) does not trip `except`.
- Existing progress tests stay green: `_inputs()` defaults `installed` to False (`tests/test_execute_screen.py:199`), so `_to_update` is empty for them.
- `read_first` now reuses 14-01's real-service subclasses rather than inventing a second pair.

**Concerns**
- None new.

**Suggestions**
- None required before execute.

**Risk:** LOW — remaining work is rendering, not a missing capability.

## 14-03

**Summary.** Still the strongest plan. Cycle 1's already-installed consequence is a stated decision plus a docstring requirement; D-04's one-way checkpoint is recorded. No cycle-2 finding landed here, and nothing new against the live tree.

**Strengths**
- Closed table in a new module; `POSTINSTALL_HOOKS` stays disjoint from `POST_INSTALL_ACTIONS` (`installer/model.py:46-54`).
- Dispatch sits after the singular hook (`installer/engine.py:149-154`) and cannot be reached from `ALREADY_INSTALLED` (`installer/engine.py:116-117`) or `MANUAL_REQUIRED` (`installer/engine.py:139-145`).
- `CHSH=no` stays on the script (`installer/registry.toml:541`); `detect_path` at `:542` is the short-circuit.
- `Install` protocol is unchanged (`installer/session.py:38-50`); `confirm_sensitive_action` is keyword-only with a default.
- Module has no execution seam; GATES-OK constructs `Platform(immutable=True)` the way `tests/test_engine.py:18-19` already does.
- `is_installed` monkeypatch convention is in `read_first` (`tests/test_engine.py:37`), so the real-registry e2e is host-independent if followed.

**Concerns**
- **LOW** — Task 1's behavior bullets say "`install_tool` on that real tool" without saying to monkeypatch `engine.is_installed`. `oh-my-zsh`'s `detect_path` (`installer/registry.toml:542`) makes `is_installed` (`installer/status.py:29-31`) host-dependent. `read_first` already cites the monkeypatch convention, and a miss fails closed (`()` handoff). Do not drop the patch.

**Suggestions**
- Executor: copy `tests/test_engine.py:37` on the real-registry case. Not a plan rewrite.

**Risk:** LOW

## 14-04

**Summary.** Cycle 2's MEDIUM (copy `render_handoff`'s markup-on print) and LOW (`FakePrompter` constructor) are actually gone: instruction lines use `markup=False`, and `FakePrompter` is extended additively with a `>= 15` call-site gate. Cycle 1's HIGH (vulture before the caller) and MEDIUM (vacuous `options.yes` index) stay gone.

**Strengths**
- Adapter keeps `Install` byte-identical (`installer/session.py:38-50`); 6 / 11 / 9 / 2 fakes across `test_app.py` / `test_execute_screen.py` / `test_session.py` / `test_wizard_app.py` still match.
- `--yes` → `None` callback mirrors `installer/app.py:157`.
- New renderer, not a widened `render_handoff` (`installer/render.py:118-132` is `MANUAL_REQUIRED`-only, markup enabled at `:131-132` — the one line not to copy).
- Fifteen `FakePrompter(categories=` sites confirmed at `tests/test_app.py:96,126,165,181,199,220,610,637,684,705,729,751,1279,1931,1971`.
- Unattended is `-k sensitive_unattended`, not a source-order string comparison.

**Concerns**
- None new. Cycle 2 MEDIUM/LOW are in the action, the Design decisions bullet, and the verify.

**Suggestions**
- None required before execute.

**Risk:** LOW — markup will fail closed at Task 1 verify if the sibling is copied anyway.

## 14-05

**Summary.** Cycle 2's MEDIUM (vacuous `WIRE-OK` `s.index('unattended')`) is deleted; the real gate is `-k sensitive_unattended`, matching 14-04's console path. Cycle 1's modal-typing and stale-`architecture.md` findings stay fixed (`HELPER-UNCHANGED` matches `installer/execute_screen.py:124`; the Phase 12.4 clause is at `.claude/architecture.md:340`).

**Strengths**
- One worker-to-modal helper; new screen returns `str | None` like `ChecksumMismatchScreen` (`installer/execute_screen.py:79,124-137`).
- `MismatchPromptOpen` has no test references (only `installer/execute_screen.py:201,450,454,475`).
- 14-01's name-free modal count stays 1; this plan correctly forbids editing it.
- Attribution stays outermost: `attributed_install` (`installer/execute_screen.py:154-174`) does not forward `confirm_sensitive_action`, so binding must wrap the inner install.
- Stale "zero production callers as of Phase 12.4" gate cannot collide with rule 5 (`.claude/architecture.md:23-25`).
- `WIRE-OK` is now membership-only (`with_sensitive_confirm` / `attributed_install` / `ask_from_worker`); the standing note against restoring the index comparison is load-bearing.

**Concerns**
- None new.

**Suggestions**
- None required before execute.

**Risk:** LOW — D-05 is enforced by the pilot, not by a cargo-culted source-order gate.

## Cross-plan

Cycle 2's six findings (0 HIGH, 3 MEDIUM, 3 LOW) are incorporated as claimed, re-verified against the live tree this cycle:

| Finding | Where | Live-tree check | Disposition |
|---|---|---|---|
| Concrete annotations vs duck-typed fakes | 14-01 MEDIUM | `pyproject.toml:42-45`; helpers at `tests/test_catalog_tui.py:983-1003,1358-1367` | subclasses + `uv run pyright` in Task 1 |
| `ownership_of is None` skip vs blocking refresh | 14-01 LOW | `installer/catalog_tui.py:571-573,597-599` | recorded divergence + test |
| Set-equality vs latch-refusal on one fixture | 14-02 LOW | n/a (test-spec) | fixtures A / B / C |
| `render_handoff` markup-on vs `[this]` must survive | 14-04 MEDIUM | `installer/render.py:131-132` | `markup=False` on instruction lines only |
| `FakePrompter` constructor | 14-04 LOW | 15 sites, signature `(categories, tools, confirm)` at `tests/test_app.py:46-61` | additive + `>= 15` gate; finding was Task 3, not Task 1 |
| Vacuous `WIRE-OK` `index('unattended')` | 14-05 MEDIUM | `installer/execute_screen.py:398` already contains the word | deleted; `-k sensitive_unattended` is the gate |

No revision reintroduced a locked-decision conflict. Wave order (01∥03 → 02∥04 → 05) still matches the code dependencies: 14-01/14-03 share no files; 14-02/14-04 share no files; 14-05 needs 14-02's execute-screen surface and 14-04's adapter.

The one LOW left (14-03 real-registry e2e should monkeypatch `is_installed`) is fail-closed and already implied by `read_first`. It is not a reason to rewrite.

**Overall risk: LOW** — cycle 2's remaining misses are gone, and nothing new is red-by-construction against the live tree the way cycle 1's two HIGHs were. Execute.

---

## Consensus Summary

Single reviewer (`opencode-fallback`) this FINAL cycle (3/3, max_cycles reached) — no cross-reviewer consensus to compute. Zero HIGH and zero MEDIUM findings this cycle; both cycle 1's and cycle 2's fixes were independently re-verified against the live tree, not taken on trust. One residual LOW remains against 14-03: its Task 1 behavior text should explicitly instruct monkeypatching `engine.is_installed` for the real-registry end-to-end test (the convention is already cited in `read_first`, and a miss fails closed rather than silently passing, so this is not blocking). Per the plan-review-convergence loop's max_cycles=3 escalation rule, the loop ends here regardless of outcome — this single LOW is carried forward as a known, non-blocking residual issue rather than triggering a fourth revision cycle.

### Agreed Strengths
N/A — single reviewer this cycle.

### Agreed Concerns
N/A — single reviewer this cycle; see per-plan Concerns above.

### Divergent Views
N/A — single reviewer this cycle.
