---
phase: 26
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-16T14:07:56Z
cycle: 1
plans_reviewed: [26-01-PLAN.md, 26-02-PLAN.md, 26-03-PLAN.md, 26-04-PLAN.md, 26-05-PLAN.md, 26-06-PLAN.md, 26-07-PLAN.md, 26-08-PLAN.md, 26-09-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "cli-flag"
---

# Cross-AI Plan Review — Phase 26

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## OpenCode Review (opencode-referee-one) — cycle 1

> Launched directly (`opencode run --model router-env/my-referee-one`, stdin closed, artifact paths only): GSD's runner rejects the instance (`review-lane plan --selected opencode-referee-one` → `malformed_lane: no such declared lane`). Raw log: `.planning/phases/26-commit-and-push-quality-hooks/.review-diagnostics/20261116T110200-c1-my-referee-one/review.log` (gitignored).

## 26-01

**Summary:** The plan gives each static check one command location and makes both hook stages use those targets. Its wiring guard does not fully enforce the promised two-way discovery of future gates.

**Strengths**
- The current Makefile contains the six commands directly (`Makefile:34-49`), and the plan moves them to individual targets while retaining one aggregate entry point (`26-01-PLAN.md:130-145`).
- The plan checks hook stage, execution on an empty file set, and push ordering (`26-01-PLAN.md:124-128`, `:174-180`).

**Concerns**
- **MEDIUM — A newly added gate can be invisible to the wiring test.** `GATES` is a fixed set of six names (`26-01-PLAN.md:126`, `:180`). Adding a new quality target to the Makefile without adding it to `GATES` or the hooks leaves the existing set comparison green, despite the stated requirement that a gate with no commit hook fail (`26-01-PLAN.md:33`; `26-SPEC.md:50-54`). Adding a properly wired gate also requires changing the test’s hard-coded set, contrary to the “one target plus one hook” description.

**Suggestions**
- Define an explicit, discoverable way to identify gate targets and test an extra unhooked target, or narrow the documented guarantee and require the registry to be updated when adding a gate.

**Risk Assessment:** MEDIUM — Existing gates are well covered, but the intended drift protection has a future-gate blind spot.

## 26-02

**Summary:** The rename covers the visible guidance, its assertions, and the affected documentation. It is coordinated with the Makefile change, although either independently completed plan briefly leaves commands and guidance out of sync.

**Strengths**
- The listed product strings and tests exist at the cited sites, including `installer/guidance.py:142`, `:224`, `:425` and `tests/test_guidance.py:216-226`.
- The zero-count check covers tracked hidden documentation as well as source (`26-02-PLAN.md:143-156`).

**Concerns**
- **LOW — Wave-one ordering permits a temporary broken user command.** Plan 01 removes `make setup` while explicitly leaving the messages for this parallel plan (`26-01-PLAN.md:228-234`); the current README and product guidance still tell users to run it (`README.md:98-111`, `installer/guidance.py:223-225`). Conversely, plan 02 may tell users to use `make run` before plan 01 changes its implementation, although the current alias makes that direction safe.

**Suggestions**
- Merge the rename and target removal together, or document that the intermediate commits are not release points.

**Risk Assessment:** LOW — The final combined tree is specified; the issue is the intermediate state.

## 26-03

**Summary:** The plan uses existing bounded pilot helpers and records honest before-and-after results. It does not establish that its proposed wait fixes the reported race.

**Strengths**
- It preserves assertions and bans fixed delays (`26-03-PLAN.md:62-65`, `:82-85`), consistent with `.claude/testing.md:24-33`.
- It requires recording a passing baseline rather than inventing a reproduction (`26-03-PLAN.md:79-80`).

**Concerns**
- **MEDIUM — Two equal pass counts do not prove the opening refresh has landed.** The proposed helper accepts two equal reads separated by `settle` (`26-03-PLAN.md:82-85`). `settle` waits for currently visible workers and pauses once (`tests/screen_family.py:22-26`); it does not prove a queued refresh has been published. The opening helper itself waits for the globals audit, not a particular refresh pass (`tests/test_screen_family.py:1912-1917`). A delayed message can therefore arrive after the two reads and still satisfy the later `before + 1` wait. Research explicitly says the suspected cause was not reproduced (`26-RESEARCH.md:503-508`), so 50 passes alone do not demonstrate that this interleaving is closed.

**Suggestions**
- Identify and wait for the opening publication or another explicit completion event before capturing the baseline. Add a controlled delayed-refresh test that fails with the old wait, and retain the measured repetition runs.

**Risk Assessment:** MEDIUM — The original flake can survive while the todo is marked resolved.

## 26-04

**Summary:** The gate has a clear ordered refusal contract and avoids shell interpolation. Its selected untracked-file rule does not establish the central claim that the tested tree equals the pushed commit.

**Strengths**
- The plan reads all ref updates, peels tags, and uses argument lists instead of shell command strings (`26-04-PLAN.md:78-100`, `:129-137`).
- It specifies signal forwarding and separate real-signal tests rather than assuming pre-commit restores edits on every signal (`26-04-PLAN.md:186-210`).

**Concerns**
- **HIGH — Untracked files outside three directories can change the checks.** The only untracked refusal is for `.py` files under `installer/`, `tests/`, and `devtools/` (`26-04-PLAN.md:94-100`, `:159-170`). For example, an untracked root `conftest.py` can be loaded by pytest and alter or skip test behavior, yet is not part of HEAD. The project’s test machinery uses pytest configuration and `tests/conftest.py` extensively (`pyproject.toml:47-52`, `tests/conftest.py:99-120`). Likewise, other untracked inputs can affect checks; research acknowledges this residual (`26-RESEARCH.md:321-322`). A green push therefore need not test the committed tree, contrary to `26-SPEC.md:71-83`.
- **MEDIUM — The signal tests miss the advertised spawn race.** The planned group-signal test waits for the child’s `started` marker before sending a signal (`26-04-PLAN.md:195-199`), so it cannot exercise the branch that records a signal before the child handle exists (`:206-208`).

**Suggestions**
- Resolve the mismatch with the locked refusal decision: amend it to reject all untracked, non-ignored inputs that can affect the gates, or execute the checks against an isolated committed tree. Add real-repository cases for a root `conftest.py` and other relevant non-Python inputs.
- Add a deterministic test that injects a signal during spawn and proves it is forwarded once after the handle becomes available.

**Risk Assessment:** HIGH — A push can pass checks against a tree different from the commit being pushed.

## 26-05

**Summary:** The bootstrap plan has useful preflight checks for a foreign hook and for `core.hooksPath`, and keeps the shared-hooks constraint explicit. The proposed file handling leaves a data-loss edge.

**Strengths**
- It checks for a foreign `pre-push` before invoking pre-commit or writing the shim (`26-05-PLAN.md:165-185`).
- It recognizes that the generated commit hook embeds a worktree’s interpreter and specifies a warning (`26-05-PLAN.md:98-107`, `:169-170`).

**Concerns**
- **HIGH — A marked symlink can cause a write outside the hooks directory.** The plan reads an existing `pre-push`, accepts it if it contains the marker, then uses `Path.write_text` when its bytes differ (`26-05-PLAN.md:134-136`, `:177-184`). If `pre-push` is a symlink to a user file containing that marker, `write_text` follows the link and overwrites the target. This contradicts the stated foreign-hook/data-loss boundary (`26-05-PLAN.md:33-35`, `:234-246`).
- **MEDIUM — A non-repository error is treated as a harmless skip.** Every nonzero common-directory query is classified as “not a git checkout” and returns success (`26-05-PLAN.md:177-180`). A permission or repository-corruption error can therefore leave a developer believing setup succeeded without hooks.

**Suggestions**
- Use `lstat` and refuse symlinks and other non-regular hook entries before writing; test that the symlink target remains unchanged.
- Skip only a verified “not a repository” case; surface other Git failures and their stderr.

**Risk Assessment:** HIGH — A hook installation can overwrite an unrelated file through a symlink.

## 26-06

**Summary:** The scratch-only real-Git harness is the right complement to the sandboxed unit tests, but several prescribed cases cannot prove what their names claim.

**Strengths**
- The environment allowlist addresses the real inherited-Git-variable hazard described in research (`26-06-PLAN.md:91-104`; `26-RESEARCH.md:303-306`).
- The harness exercises actual pre-commit configuration rather than a separate imitation (`26-06-PLAN.md:21-24`, `:94-102`).

**Concerns**
- **HIGH — Restore comparisons use the wrong expected bytes.** The plan saves `tests/test_a.py` *before* appending the unstaged `FAIL`, then expects the post-push file to equal that saved copy (`26-06-PLAN.md:163-168`). Correct restoration retains the appended edit, so this comparison fails when restoration works and would pass if the edit were lost. The interrupt cases repeat the same ordering (`:205-208`). This does not prove P2 (`26-SPEC.md:187`, `:250-253`).
- **HIGH — Existing-branch cases can push nothing and never run the hook.** Every new scratch repo initially pushes `main` before hooks are installed (`26-06-PLAN.md:94-102`). The existing-branch restore case then calls for a push without requiring a new local commit (`:166`); similarly, refusal cases do not consistently require an outstanding update (`:163-165`, `:172-173`). The gate is explicitly required to exit successfully without checks on empty input (`26-04-PLAN.md:21-22`). Such cases can therefore bypass the intended path or fail for the wrong reason.
- **MEDIUM — No specified failing-gate case compares a dirty edit after failure.** The red-push case uses a committed failing test and checks the remote SHA (`26-06-PLAN.md:127-130`); the byte-comparison cases cover success and signals, not a normal failed gate with an unstaged edit. P2 requires all three outcomes (`26-SPEC.md:187`).

**Suggestions**
- Save the expected file **after** adding the unstaged edit, and compare those exact bytes after each outcome.
- Create an unpushed committed change before every case intended to exercise the gate; assert the expected gate or refusal actually ran.
- Add a failed-gate case with a separate unstaged tracked edit and verify both the remote SHA and restored bytes.

**Risk Assessment:** HIGH — The phase’s main data-preservation proof is currently inverted and some cases may not invoke the gate.

## 26-07

**Summary:** The plan preserves the required job names and makes Git failures and empty diffs take the full path. Its docs-only rule has concrete false-fast-pass cases.

**Strengths**
- The current required-context job name and matrix are visible in `.github/workflows/ci.yml:13-21`; the plan explicitly keeps them unchanged (`26-07-PLAN.md:23-25`).
- NUL-separated paths and `--no-renames` address spaces, newlines, and rename classification (`26-07-PLAN.md:26-32`).

**Concerns**
- **HIGH — Code under `.planning/` gets a docs-only pass.** `is_docs_path` accepts every path under `.planning/`, subject only to the narrow test-read exclusions (`26-07-PLAN.md:83-85`, `:147-150`). The repository already tracks Python code there, including `.planning/research/2026-10-13-from-ai-kit/pi-sync/pi_sync.py` and its test. A change to one of those files is classified `full=false`, even though P4 says a change touching code must not skip the full jobs (`26-SPEC.md:250-255`). The held-out rename test only catches a move whose *old* path lies outside `.planning/` (`26-07-PLAN.md:178-180`); it does not cover a direct edit to code already inside it.
- **MEDIUM — The literal ledger misses dynamically resolved test-read Markdown.** The proposed detector only records string literals ending in `.md` or naming `.planning` (`26-07-PLAN.md:207-211`, `:227-228`). Existing tests resolve relative Markdown links from document text at runtime (`tests/test_docs.py:445-472`). A new README link to `notes/example.md`, followed by a change to that target alone, can make the link/heading test fail while the target remains eligible for the fast pass. The ledger sees no new literal in the test source.

**Suggestions**
- Reconcile D-16 with P4 and explicitly classify code and CI-related file types under `.planning/` as full-run changes; add a direct-edit test for the tracked Python example.
- Include dynamically resolved document targets in the test-read policy, or conservatively restrict the fast pass to a reviewed set of planning/document paths.

**Risk Assessment:** HIGH — Required checks can report success without running the full jobs for code or a file read by tests.

## 26-08

**Summary:** The documentation plan covers the requested gate tables, recovery instructions, and branch flow. Its escape procedure and timing fallback need stronger execution guidance.

**Strengths**
- The proposed table names the actual gate targets and stages from the earlier plans (`26-08-PLAN.md:83-86`, `:120-134`).
- The plan requires an off → push → on → read-back sequence and pins its order (`26-08-PLAN.md:151-177`).

**Concerns**
- **MEDIUM — The recovery command is not directly executable as written.** `git apply "$PRE_COMMIT_HOME"/patch<timestamp>-<pid>` uses angle-bracket placeholders that a shell interprets as redirections if copied literally (`26-08-PLAN.md:126-130`). It also does not provide a directly executable default when `PRE_COMMIT_HOME` is unset. The recovery is specifically for possible uncommitted-work loss (`26-RESEARCH.md:218-225`).
- **MEDIUM — The escape procedure depends on the operator continuing after a failed command.** The plan says “always” re-enable protection (`26-08-PLAN.md:172-177`), but its ordered prose and text-position test do not themselves ensure restoration if a shell exits on the failed push or the session is interrupted. P6 requires protection not to remain off (`26-SPEC.md:250-257`).
- **LOW — The fallback cannot supply both requested CI measurements.** If GitHub is unavailable, the plan asks for Ubuntu and macOS figures from the workflow comment (`26-08-PLAN.md:116-118`), but the current comment supplies only an approximate macOS duration (`.github/workflows/ci.yml:33-36`).

**Suggestions**
- Show how to locate the patch and apply a quoted, actual path, including the default cache directory and a warning to inspect before applying.
- Document a guarded cleanup sequence and explicit escalation if re-enabling or read-back fails; do not claim a prose-order pin alone enforces P6.
- Mark unavailable measurements as unavailable rather than deriving an Ubuntu time from a comment that has none.

**Risk Assessment:** MEDIUM — The docs are central to recovery and an administrator action; misleading commands or an incomplete recovery sequence matter.

## 26-09

**Summary:** The plan places protection changes and real hook installation after the implementation and requires read-back and a rejection probe. Two checkpoint instructions conflict with the repository’s agent-safety rules and with the evidence the selected GitHub command can return.

**Strengths**
- It requires the phase branch to be validated and CI-green before enabling strict checks and administrator enforcement (`26-09-PLAN.md:90-105`).
- It records the direct-push assumption as unproven and includes read-back after the fallback (`26-09-PLAN.md:167-180`; `26-RESEARCH.md:490-496`).

**Concerns**
- **HIGH — The orchestrator is instructed to run a command the planned agent rules prohibit.** Plan 08 adds “Agents never run `make dev-setup`” because it rewrites hooks shared by worktrees (`26-05-PLAN.md:203-215`), while plan 09 tells the orchestrator to run it twice in the real checkout (`26-09-PLAN.md:122-140`). The existing project rules also prohibit agents from mutating the developer’s host and agent settings (`AGENTS.md:31-39`). Labeling the step “ORCHESTRATOR” does not by itself make an agent a human or resolve that conflict.
- **MEDIUM — The requested API output does not prove `full=false`.** The command selects job and step names and conclusions only (`26-09-PLAN.md:169`); those fields do not include the classifier’s step-output value. Skipped steps can support the fast-pass conclusion, but the specified output cannot show `full=false` as claimed.
- **MEDIUM — The fallback treats a protection bypass as completion of the normal-flow proof.** If GitHub rejects the protected fast-forward, the plan disables enforcement, pushes, and re-enables it (`26-09-PLAN.md:175-183`), yet the verification and acceptance criteria allow that fallback as completion (`:183`, `:190-196`). That does not prove the locked requirement that the last change landed through the documented protected flow (`26-SPEC.md:119-125`, `:195-197`).

**Suggestions**
- Make the real hook installation a human-owner action with explicit consent and recorded evidence, or obtain an explicit higher-priority exception before an agent performs it.
- Retrieve the classifier’s logged decision or otherwise record verifiable evidence of its output.
- If the protected push fails, record the fallback and the requirement as unresolved; do not mark the protected-flow acceptance as passed.

**Risk Assessment:** HIGH — The checkpoint directs a prohibited real-checkout mutation and can declare the protected landing proven when it was bypassed.

## Overall

**Cross-plan risk: HIGH.** The plans are detailed and grounded in existing commands and tests, but the current design does not yet prove that the checked tree is the pushed tree, that interrupted edits are restored, or that every code change receives full CI. The real-hook checkpoint also needs a human-safe ownership boundary.

**HIGH concerns**
- **26-04:** Untracked files outside the three selected directories can affect the push checks, so a green gate need not test HEAD.
- **26-05:** A marked `pre-push` symlink can cause the installer to overwrite its target.
- **26-06:** Restore comparisons save the expected bytes before adding the edit, inverting the data-preservation proof.
- **26-06:** Cases without an outstanding ref update can exit through the empty-input path instead of testing the gate.
- **26-07:** Direct changes to Python code already under `.planning/` receive the docs-only fast pass.
- **26-09:** The orchestrator is told to run real hook installation despite the planned rule that agents never run it.

**Verdict: Fix the HIGH concerns before execution, then re-review the revised plans.**

**Not checked:** No tests, GitHub calls, installer commands, or mutating operations were run, as requested; GitHub protection behavior and the proposed signal behavior were assessed from the plans and recorded research, not independently reproduced.

---

## Orchestrator Verification (cycle 1)

Every HIGH was checked against the cited plan lines and the repository source before replanning
(owner rule: reviewers misread about one finding in five).

| # | Plan | Finding | Verdict | Evidence |
|---|------|---------|---------|----------|
| H1 | 26-04 | Untracked inputs outside `installer/`, `tests/`, `devtools/` can change the checks (root `conftest.py`) | **VERIFIED — HIGH** | `pyproject.toml:49` `testpaths = ["tests"]` with the rootdir at the repo root, so pytest loads a root `conftest.py`; an untracked root `pytest.ini`/`tox.ini`/`setup.cfg` would also override `[tool.pytest.ini_options]`. SPEC R3's target ("every push either tests a tree equal to HEAD or is refused") supports widening; SPEC's edge row "paths outside the two trees do not" needs a dated amendment. |
| H2 | 26-05 | A marked `pre-push` symlink makes `write_text` overwrite its target | **VERIFIED, downgraded to MEDIUM** | `26-05-PLAN.md:136,177-184` write with `Path.write_text` after a marker check. The target already holds our marker (a copy of our own shim), so the loss is bounded; refusing non-regular files (`lstat`) is still required. |
| H3 | 26-06 | Restore checks save the expected bytes before the unstaged edit | **VERIFIED — HIGH** | `26-06-PLAN.md:166` and `:206` save the copy, then append `FAIL`, then `cmp -s` with the pre-edit copy: a correct restore fails the check and a lost edit passes it. |
| H4 | 26-06 | Existing-branch restore and refusal cases may push nothing, so the gate takes its empty-input path | **VERIFIED — HIGH** | `26-06-PLAN.md:102` pushes `main` at repo creation; `:164`, `:166`, `:172-173` add no new commit before the push. With no ref update the gate exits 0 before any refusal or check (`26-04-PLAN.md` deletion/empty-input rule), so these cases can pass without exercising the gate. |
| H5 | 26-07 | Python code under `.planning/` gets the docs-only fast pass | **REFUTED** | SPEC R5 locks "every path it changes against `main` is under `.planning/`" as docs-only. No gate reads `.planning/*.py`: `Makefile:38-39` ruff runs on `installer tests setup.py`, `pyproject.toml:43` pyright `include = ["installer", "tests"]`, `pyproject.toml:49` `testpaths = ["tests"]`, bandit `-r installer` (`Makefile:43`). A fast pass there cannot hide a red check. Tracked `.planning/` non-Markdown: 16 json, 7 log, 4 yaml, 3 toml, 2 py (research scratch). |
| H6 | 26-09 | The orchestrator is told to run `make dev-setup` although the planned AGENTS.md rule says agents never run it | **NOT A HIGH — kept as MEDIUM** | The owner's run brief (2026-11-16) assigns "installing the hooks for real in this checkout" to the orchestrator as the final step. The real gap is wording: the new AGENTS.md sentence (`26-05-PLAN.md:203-215`) must name that owner-assigned exception so the two plans agree. |

MEDIUM and LOW findings (not separately verified, judged on the plan text):

| # | Plan | Finding | Disposition |
|---|------|---------|-------------|
| M1 | 26-01 | `GATES` is a hard-coded set, so an unhooked new gate target stays green | actionable: derive the gate set from the Makefile (a marker), test an extra unhooked target |
| M2 | 26-03 | Two equal pass counts after `settle` do not prove the opening refresh landed | actionable: wait on an explicit completion event; honest A1 wording |
| M3 | 26-04 | Signal tests never exercise a signal arriving before the child handle exists | actionable: deterministic spawn-window test |
| M4 | 26-05 | Every non-zero `git rev-parse` is treated as "not a git checkout" | actionable: skip only on the not-a-repository message, surface other failures |
| M5 | 26-05 | (H2 downgraded) symlink / non-regular `pre-push` | actionable: `lstat`, refuse non-regular, test the target is untouched |
| M6 | 26-06 | No failed-gate case checks a restored unstaged edit (P2 names pass, fail, interrupt) | actionable |
| M7 | 26-07 | The literal-scan ledger misses Markdown resolved at runtime from doc links (`tests/test_docs.py:445-472`) | actionable |
| M8 | 26-08 | Recovery command uses `<…>` placeholders and no default `PRE_COMMIT_HOME` | actionable |
| M9 | 26-08 | Escape hatch relies on the operator continuing after a failed push | actionable: guarded sequence, escalation if on/read-back fails |
| M10 | 26-09 | The chosen `gh api` fields cannot show the classifier's `full=false` | actionable |
| M11 | 26-09 | The A2 fallback is allowed to mark the protected-flow acceptance as passed | actionable: record it as unresolved if the fallback is used |
| M12 | 26-05/26-09 | (H6) AGENTS.md sentence vs the owner-assigned real install | actionable: name the exception |
| L1 | 26-02 | Wave-1 intermediate state between 26-01 and 26-02 | rejected: both land in one wave merge; each plan is green alone (26-01 keeps the pinned hint strings untouched) |
| L2 | 26-08 | Ubuntu timing cannot come from the ci.yml comment | actionable: mark unavailable figures as unavailable |

**Cycle 1 tally:** 6 HIGH raised → 3 verified HIGH (H1, H3, H4), 1 verified and downgraded (H2), 1 reclassified MEDIUM (H6), 1 refuted (H5). 11 MEDIUM + 2 LOW raised as review concerns plus 2 reclassified → 13 actionable, 1 rejected.

## Consensus Summary

One reviewer ran (opencode-referee-one), so there is no cross-reviewer consensus; the single-reviewer
consensus gate does not apply.

### Agreed Strengths
- Single reviewer: each gate command lives once in the Makefile; the push gate reads every ref and avoids shell strings; the e2e harness uses an `env -i` allowlist; the outward-facing steps sit in the final checkpoint.

### Agreed Concerns
- Single reviewer: see the verified HIGHs H1, H3, H4 above.

### Divergent Views
- None (one reviewer).

## Verification coverage

- Source-grounding (authority `intel`, via `drift-guard authority`): 63 repo paths cited across the 9 plans; 44 resolve to tracked files; 10 are new files listed under the plans' artifacts (`devtools/*`, the four new test files, `scripts/hooks-e2e.sh`). 9 are scratch-repo fixture names that exist only inside test or e2e repos (`tests/z.py`, `tests/data.json`, `installer/new.py`, `tests/test_x.py`, `tests/check.sh`, `tests/test_a.py`, `tests/test_b.py`, `docs/x.py`, `installer/a.py`): UNCHECKABLE by design, not repo references.
- Symbols (functions, classes) and signatures: UNCHECKABLE under the `intel` adapter for Python (the API surface lists 6 JS-derived symbols); the verify-command path probe resolved all 32 `<automated>` commands.
- Phase-status drift (`drift-guard phase-status --phase 26`): `uncheckable` (STATE `ready_to_plan`, ROADMAP "Not started" outside the shared vocabulary). Advisory only.
- Fact-drift pairs (ROADMAP success criteria ↔ plan truths, requirement IDs, CONTEXT terms): no contradiction found; the plans add truths beyond the roadmap criteria, which is sanctioned.
