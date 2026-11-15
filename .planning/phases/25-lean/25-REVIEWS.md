---
phase: 25
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-15T20:48:00Z
review_cycle: 1
plans_reviewed: [25-01-PLAN.md, 25-02-PLAN.md, 25-03-PLAN.md, 25-04-PLAN.md, 25-05-PLAN.md, 25-06-PLAN.md, 25-07-PLAN.md, 25-08-PLAN.md, 25-09-PLAN.md, 25-10-PLAN.md, 25-11-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "reviewer-instance"
---

# Cross-AI Plan Review — Phase 25

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## Cycle 1 — reviewed at HEAD 3ae04e61

### Lane run facts

- GSD's review runner was not used; opencode was launched directly (`timeout 3600 opencode run --model router-env/my-referee-one`, stdin `/dev/null`, paths-only prompts) in four parallel lanes: A (25-01, 02, 04), B (03, 05, 06), C (07, 08, 09), D (10, 11). The probe answered `OK` first.
- Lane A: exit 0, 17.7 KB. Lane B: exit 0, 23.9 KB. Lane C: exit 0, 17.5 KB. Lane D: exit 0, 34.9 KB. Every lane streamed tool calls within the first minute and covered every plan id in its lane. No failover was needed.
- Raw output: `.planning/phases/25-lean/.review-diagnostics/20261115T204800Z-cycle1/` (gitignored).
- After the lanes finished, `~/.claude/gsd-core` and `~/.claude/.gsd-source` were absent and no opencode run was left.
- One reviewer model ran, so the consensus gate is skipped. A separate read-only verifier re-checked every HIGH and MEDIUM against the source. The orchestrator spot-checked the three confirmed HIGHs (`setup.py:703`, `tests/test_versions.py:150-159`, `25-02-PLAN.md:173,268`).

### Verified findings ledger (cycle 1)

Raw: 20 HIGH, 15 MEDIUM. After verification: **3 HIGH confirmed**, 10 MEDIUM (8 downgraded from HIGH, 2 confirmed), 17 LOW (downgraded), 5 refuted. The verifier judged every remaining fix to be plan wording, ordering or command text.

| ID | Plan | Raw | Verified | Finding (verified form) | Required property for the replan |
|----|------|-----|----------|-------------------------|-----------------------------------|
| R1-01 | 01 | HIGH | LOW | The visitor takes only level-0 `ImportFrom` (`25-01-PLAN.md:117`). `installer/` has no relative import today. A missed edge can only fail loudly | A level>0 `ImportFrom` is resolved against its package or fails the test as unsupported, never silently dropped |
| R1-02 | 01 | MEDIUM | LOW | `install_ownership._PATH_QUERIES` (`installer/install_ownership.py:213-218`) is a callable table missing from `_DISPATCH_TABLES` (`25-01-PLAN.md:151`) | `_DISPATCH_TABLES` lists every string-keyed callable table, `_PATH_QUERIES` included |
| R1-03 | 01 | MEDIUM | LOW | The exemption test checks only that the exempt dirs exist (`25-01-PLAN.md:148`) | Nothing reachable imports a module under an exempt dir, so a live package cannot hide behind an exemption |
| R1-04 | 02 | HIGH | **HIGH** | 25-02 (wave 1, `depends_on: []`) names `tests/test_reachability.py` in Task 1's verify and its plan verification (`25-02-PLAN.md:173,268`). 25-01 creates that file in the same wave | No 25-02 command names a file only 25-01 creates (drop it there, or order 25-02 after 25-01) |
| R1-05 | 02 | MEDIUM | MEDIUM | The test checks `smoke_argv` (`tests/test_model.py:761-784`). `dnf` allows it (`installer/model.py:103`), `rpm_ostree` does not (`:106`). The plan's `dnf` example and its "delete if none" fallback are wrong | The host_setup case becomes `("rpm_ostree", 'package = "demo"')`, and the `unknown key 'smoke_argv'` assertion is unchanged |
| R1-06 | 02 | MEDIUM | LOW | Deleting the host_setup pi tests (`tests/test_ownership.py:3010-3083`) leaves no pi-specific pnpm-owner test | Task 2 adds a pi test built on `_bun_pi()` plus pnpm globals evidence that asserts owner `pnpm`. The mmdc test does not count |
| R1-07 | 04 | HIGH | MEDIUM | The moved tests call `_tool`, defined only in `tests/test_deps.py:15-27`. "Unchanged except imports" (`25-04-PLAN.md:146`) gives a NameError | The relocation commit copies a `_tool` helper into `tests/test_registry.py`. The moved assert lines are unchanged |
| R1-08 | 04 | HIGH | LOW | Deleting only `release_tag` leaves `tag` unused (`installer/verify_registry.py:376,389`), so ruff F841 fails. `resolve_target` already does the release lookup (`installer/download.py:119`) | The commit also deletes both `tag =` assignments, and states why VersionError handling is unchanged |
| R1-09 | 04 | MEDIUM | LOW | The truth "each vulture-60 candidate" is wider than the tasks | The SUMMARY lists Textual hooks and enum members as one framework-dispatched category, never deleted |
| R1-10 | 03 | HIGH | MEDIUM | Assert lines pass the retired third argument (`tests/test_post_install.py:170,267-268,686,1132,1134,1139`). The byte-identical rule (`25-03-PLAN.md:115`) forbids removing it | Removing the retired argument from a call inside an assert is allowed when the expected values stay byte-identical. The SUMMARY lists each such line |
| R1-11 | 03 | HIGH | MEDIUM | `25-03-PLAN.md:107` lists `test_execute_plan_prints_the_login_shell_handoff_whatever_the_confirmation_says` both for deletion and for strip-only. The asked-based post_install tests (`tests/test_post_install.py:112-120,163-171,174-184,207-214,265-271`) also assert live chsh, emulator, unknown-action and empty-output behaviour | Each test is classified once. The post_install asked-based tests keep every live assert and lose only the `_record`/`asked`/confirm lines. The session `run(confirm)` test is deleted because `tests/test_session.py:1296-1323` covers it |
| R1-12 | 03 | HIGH | LOW | The `boom(_tool, _platform, _confirm)` doubles (`tests/test_engine.py:1174,1297`) would raise TypeError with two arguments | Task 2 also drops the third parameter from the action-table doubles |
| R1-13 | 03 | HIGH | MEDIUM | (a) Deleting the fixture leaves `SENSITIVE_PROMPTS`/`SensitivePrompt` unused (`tests/test_execute_screen.py:49`), so ruff F401 fails Task 1. (b) The "prints 6" criterion (`25-03-PLAN.md:142`) cannot hold, because `installer/execute_screen.py:148` sits inside the deleted docstring | Task 1 removes the imports it orphans, and its criterion expects 5 lines or checks the class and its call site |
| R1-14 | 03 | MEDIUM | REFUTED | `25-03-PLAN.md:41` promises that no pin of retired text remains, not a negative pin | None |
| R1-15 | 05 | HIGH | **HIGH** | `_schedule_context` computes `checkout=Path(__file__).resolve().parent` (`setup.py:703`). After the verbatim move into `installer/compose.py` that points at `installer/`, which breaks `schedules.py:734,859` and `tests/test_setup.py:981` | In compose, `checkout` is `Path(__file__).resolve().parent.parent` (repo root), named as an allowed edit beside `_REGISTRY`. `tests/test_setup.py:981` is unchanged |
| R1-16 | 05 | HIGH | **HIGH** | Both `resolve_tag=` keywords sit in `_build_services` (`setup.py:592,627`), which moves in Task 2. The `tests/test_versions.py:150-159` retarget is deferred to Task 3. `tests/test_setup.py:3540-3545` also reads only `setup.py` for `native_probe=`/`reresolve_ownership=`/`install_ownership import run_probe` | The Task 2 commit carries both source-scan retargets (`tests/test_versions.py` reads setup.py plus compose.py; `tests/test_setup.py:3541` reads compose). Only paths change |
| R1-17 | 05 | HIGH | LOW | Direct reads of `setup._execute_inputs` (`tests/test_setup.py:661,2503,2537,3589`) break once the import-back is dropped. The patch audit scans only `setattr` and misses `setattr(setup, <variable>, ...)` (`:1614`) | Every test read or patch of a moved name targets the module whose globals the code reads. The audit flags non-constant setattr names |
| R1-18 | 05 | HIGH | REFUTED | `tests/test_setup.py:1368-1374` already runs undo then reload. The autouse sandbox (`tests/conftest.py:301-323`) re-roots the next test | None (keep the order: compose then setup, after undo) |
| R1-19 | 05 | HIGH | MEDIUM | The prescribed docstring names questionary, while the Task 3 grep requires zero matches (`25-05-PLAN.md:134,209`) | The forbidden-import check is structural (AST imports only); prose may name questionary |
| R1-20 | 05 | MEDIUM | LOW | `git diff --quiet <BEFORE> HEAD -- ...` (`25-05-PLAN.md:195`) ignores the working tree | Use `git diff --quiet <BEFORE> -- ...` |
| R1-21 | 06 | HIGH | LOW | Writes made before the first sized resize replay via `self.write` (`_rich_log.py:132-139,205-213`), outside `write_log`. `dropped` is cumulative, so the next write corrects it | The notice reflects `_start_line` after any trimming, replay included (override `write` in `RunLog`, or guarantee a refreshing run-end write) |
| R1-22 | 06 | HIGH | LOW | The Task 1 commit enables trimming while `on_install_run_finished` still writes directly (`installer/execute_screen.py:938-953`) | The commit that enables `max_lines` routes all ten writes through `write_log` |
| R1-23 | 06 | MEDIUM | LOW | An empty write appends a blank strip outside the trim (`_rich_log.py:255-257`) | `write_log` skips empty strings, or the bound is stated per non-empty write |
| R1-24 | 06 | MEDIUM | LOW | The multi-line test calls the helper directly, and the 80x20 test runs before any drop | Add a near-full `InstallRunFinished` test and an 80x20 check with the label shown |
| R1-25 | 07 | MEDIUM | LOW | The checker compares only moved nodes. Leftover references are caught by ruff F821 and pyright strict | Remaining references are proven by F821/pyright, or the checker fails when an old name remains |
| R1-26 | 08 | MEDIUM | LOW | `_fit` leaves `wizard_app`. `SchedulesScreen`'s calls (`installer/wizard_app.py:2850-2856`) are not named | 25-08 Task 1 states that `SchedulesScreen`'s `_fit` calls become `fit` imported from `ui_common` |
| R1-27 | 09 | MEDIUM | REFUTED | `UninstallScreen` moves in the same task as the renames, and the checker applies the rename map | None |
| R1-28 | 10 | HIGH | LOW | `CompetingProbe`'s comment carries WR-10 (`installer/wizard_app.py:178`). It moves into `systemd_daemon.py`, which 25-10 does not scan | The id-free rule covers comments moved into pre-existing modules, for the moved lines only |
| R1-29 | 10 | HIGH | MEDIUM | `_tool_entry` writes `self._painted` (`installer/wizard_app.py:1304`) and `_with_failure` deletes from `self._failed_lines` (`:1337`), yet both are fallback "pure helper" candidates (`25-10-PLAN.md:82,131`) | Only side-effect-free helpers are extracted. Any state write stays in the class method |
| R1-30 | 10 | MEDIUM | LOW | The `app_messages.py` fallback does not say that `wizard_app` imports the moved classes | The fallback states that `wizard_app` imports `ScheduleDefaultsApplied`, `RefreshPublished` and `RefreshFinished` |
| R1-31 | 11 | HIGH | REFUTED | `ci.yml:3-6` runs on push to `main` and on PRs. The project commits on main and the orchestrator pushes main per wave | None (optionally record the run id for the final head SHA) |
| R1-32 | 11 | HIGH | MEDIUM | Aggregate suppression counts (`25-11-PLAN.md:97`) let a deleted suppression mask an added one | The gate fails on any `+` line in `git diff -U0 <BEFORE> HEAD -- installer tests setup.py` carrying a suppression token unless the same stripped text is a `-` line |
| R1-33 | 11 | HIGH | MEDIUM | A vulture name-set difference hides a new unused symbol whose name is already in the baseline | Compare multiset counts of (kind, name). Any increase must be an exempt hook on a class this phase created |
| R1-34 | 11 | MEDIUM | MEDIUM | The D-12 guard compares only `assert` segments (`25-05-PLAN.md:195`), so `@pytest.mark.parametrize` expected values (`tests/test_setup.py:1597-1603`) go unguarded | The guard also compares each checked test's decorator source |
| R1-35 | 11 | MEDIUM | REFUTED | An empty `installer/` diff cannot happen with a correct baseline, because 25-02 deletes `installer/host_setup.py` | None |

CYCLE_SUMMARY: current_high=3 current_actionable=27

## OpenCode Review (opencode-referee-one) — cycle 1 raw lanes

### Lane A (`laneA-my-referee-one`)

#### 25-01

##### Summary

The plan adds a permanent AST-based module-reachability test, scratch-tree cases for orphaned and typing-only modules, and checks for callable targets in selected dispatch tables. Its separation of module reachability from vulture’s symbol-level scan is appropriate, but the specified walker and dispatch checks leave gaps in the permanent guard.

##### Strengths

- **The seeded-orphan case makes the main check non-vacuous.** The plan requires a scratch module named in the failure result rather than merely asserting that the current checkout passes (`.planning/phases/25-lean/25-01-PLAN.md:103-105`).
- **The plan distinguishes runtime and typing-only imports.** It requires lazy function imports to count while excluding `TYPE_CHECKING` bodies (`.planning/phases/25-lean/25-01-PLAN.md:115-118,144-146`).
- **Entry-point checks are grounded in actual launch routes.** The Makefile runs both registry modules with `python -m` (`Makefile:28-32`), and `install.sh` launches `setup.py` (`install.sh:88`).

##### Concerns

- **HIGH — Relative imports are omitted from the permanent graph.** The prescribed visitor collects only level-0 `ImportFrom` nodes (`.planning/phases/25-lean/25-01-PLAN.md:117`). A reachable module using `from . import sibling` or `from .sibling import value` would therefore not produce the required edge. That can falsely report a live module as orphaned and undermines D-01’s requirement to build the import graph (`.planning/phases/25-lean/25-CONTEXT.md:30-35`). The scratch cases exercise only absolute imports.
- **MEDIUM — The dispatch-table test can pass while omitting live table targets.** The plan checks the listed seven tables and requires at least one recognized installer callable per table (`.planning/phases/25-lean/25-01-PLAN.md:147-151`), but the live ownership code also dispatches through `_PATH_QUERIES`, whose values contain callables (`installer/install_ownership.py:209-218,236-240`). Further, silently skipping unrecognized values does not prove that *every* target was examined. This weakens the stated string-dispatch coverage rather than proving it.
- **MEDIUM — The exemption check does not constrain exemption growth.** It only requires each exempt directory to exist and contain a Python file (`.planning/phases/25-lean/25-01-PLAN.md:113,148`). Adding an otherwise live installer directory to `_EXEMPT_DIRS` would still satisfy that test, despite the threat model describing it as protection against a widened exemption (`.planning/phases/25-lean/25-01-PLAN.md:179-180`).

##### Suggestions

- Resolve relative imports against the importing file’s package and add scratch tests for both relative-import forms.
- Inventory the live callable dispatch tables, include `_PATH_QUERIES`, and fail explicitly on an unsupported value shape instead of silently skipping a potential target.
- Pin the permitted exemption set, or otherwise verify its exact intended contents.

##### Risk Assessment

**HIGH.** The real-tree test may pass initially, but an incomplete import graph leaves the phase’s permanent deletion guard unreliable for valid Python imports.

#### 25-02

##### Summary

The plan removes the retired `host_setup` kind and its supporting branches in one coherent production commit, then adds compatibility pins and cleans up documentation. The removal inventory is substantial and the update refusal is handled conservatively, but the first task has a wave-order dependency on a file that its metadata does not declare.

##### Strengths

- **The update path preserves the existing refusal instead of executing a guessed command.** The current branch has a special reviewed-command path (`installer/update.py:391-400,441-451`); the plan replaces it with refusal for a pnpm owner without a method and retains the existing refusal test (`.planning/phases/25-lean/25-02-PLAN.md:155-158,164-166`; `tests/test_update.py:1541-1551`).
- **The plan preserves live native handoffs.** `install_tool` independently returns manual outcomes for native methods (`installer/engine.py:267-277`), and the plan explicitly keeps the outcome field and status while removing the obsolete `_perform` handoff slot (`.planning/phases/25-lean/25-02-PLAN.md:164`).
- **Old stored data receives explicit compatibility tests** rather than assuming removal of a registry kind implies an on-disk migration (`.planning/phases/25-lean/25-02-PLAN.md:187-202`).

##### Concerns

- **HIGH — The first task verifies against a file produced by a parallel plan.** `25-02` is wave 1 with `depends_on: []` (`.planning/phases/25-lean/25-02-PLAN.md:3-6`), but its Task 1 pytest command includes `tests/test_reachability.py` (`.planning/phases/25-lean/25-02-PLAN.md:172-174`), which `25-01` creates in the same wave (`.planning/phases/25-lean/25-01-PLAN.md:5-8,93-95`). If `25-02` runs first or in an isolated parallel worktree, pytest fails because the file is absent.
- **MEDIUM — The specified replacement for the smoke-key test is wrong and risks discarding a viable guard.** The plan suggests `dnf` as a kind rejecting the tested key and allows deleting the test if no live kind qualifies (`.planning/phases/25-lean/25-02-PLAN.md:130`). The actual assertion concerns `smoke_argv`, not `smoke` (`tests/test_model.py:761-784`), and `dnf` allows `smoke_argv`; `rpm_ostree` does not (`installer/model.py:103-106`). Following the example makes the test fail, while the fallback could delete it unnecessarily.
- **MEDIUM — The ownership-compatibility task does not explicitly test the current Pi registry row.** The plan requires confirming or adding a pnpm-owned Pi test (`.planning/phases/25-lean/25-02-PLAN.md:196-202`), but the existing Pi-specific pnpm cases found in `tests/test_ownership.py:3010-3080` are the host-setup cases slated for deletion (`.planning/phases/25-lean/25-02-PLAN.md:130`). The replacement needs to exercise the current bun-plus-node Pi shape, not merely a generic pnpm tool.

##### Suggestions

- Make `25-02` depend on completion of `25-01`, or remove the new test from the first task’s command and run it at the wave integration gate.
- Specify `rpm_ostree` with a valid package as the `smoke_argv` negative-case replacement; preserve the existing assertion.
- Require a Pi-specific ownership test using the current registry methods and pnpm global evidence.

##### Risk Assessment

**HIGH.** The undeclared same-wave test dependency can fail the first task even when its implementation is correct.

#### 25-04

##### Summary

The plan triages vulture candidates, removes dead code in individually reversible commits, and relocates the registry-integrity helper to tests. It correctly cautions that vulture output is not proof of deadness, but the prescribed relocation omits a test helper dependency, and the `release_tag` edit leaves a potentially significant call behind without instructions for its now-unused result.

##### Strengths

- **The plan checks production callers before deletion.** In particular, `encode_manager_snapshot` must remain: `installer/version_status.py:123,1999` uses it, as anticipated by the plan’s conditional cascade (`.planning/phases/25-lean/25-04-PLAN.md:94,113`).
- **The registry-integrity assertion is retained.** `tests/test_registry.py:674,2052` currently calls the helper; relocating it rather than deleting those assertions preserves the shipped-registry check (`.planning/phases/25-lean/25-04-PLAN.md:37,145-146`).
- **The candidate list distinguishes test-only fields from the live adapter module.** `AgentAdapter` still carries the configuration path used by production, alongside the two proposed fields (`installer/agent_env.py:11-24`), so the plan removes fields rather than the whole module.

##### Concerns

- **HIGH — The moved unit tests lose their `_tool` helper.** Task 2 says to move the two tests unchanged except for imports (`.planning/phases/25-lean/25-04-PLAN.md:145-146`). Both call `_tool` (`tests/test_deps.py:153-163`), defined locally in `tests/test_deps.py:15-27`; `tests/test_registry.py` has `_tools_by_id`, not that `_tool` helper (`tests/test_registry.py:29-33`). The moved tests therefore fail with an unresolved name unless the dependency is moved, imported, or replaced in the same commit.
- **HIGH — The `release_tag` deletion leaves an unused local and an unspecified side-effect decision.** The plan directs deletion of the field and constructor keyword only (`.planning/phases/25-lean/25-04-PLAN.md:110-115`). The value comes from `tag = release(repo).tag if repo else None` (`installer/verify_registry.py:373-389`) and is passed at construction (`installer/verify_registry.py:435-448`). Removing only the keyword leaves `tag` assigned but unread, conflicting with the required ruff gate (`Makefile:34-38`). Blindly deleting the assignment also removes a release-resolver call inside the existing `VersionError` handling, so the plan needs an explicit behavior-preserving treatment and a test.
- **MEDIUM — The “each vulture candidate” criterion lacks a workable classification for framework hooks.** The plan requires each candidate to be deleted when it has no production caller or listed with its caller (`.planning/phases/25-lean/25-04-PLAN.md:33-38,92-96`), while the research identifies about 200 framework hooks and enum members reported by vulture (`.planning/phases/25-lean/25-RESEARCH.md:217-219`). Framework-dispatched methods need evidence of the framework contract, not necessarily a repository caller; otherwise the per-symbol rule can misclassify them or leave the stated completion criterion unresolved.

##### Suggestions

- Include `_tool`’s test-side dependency explicitly in the relocation commit, while keeping the moved assertions unchanged.
- Specify how the release lookup and its error behavior are preserved or proven redundant, and verify ruff plus the registry-verification tests on that commit.
- Add a triage category for framework-dispatched hooks with the framework entry-point evidence recorded in the summary.

##### Risk Assessment

**HIGH.** The prescribed helper relocation cannot pass as written, and the field deletion needs a defined treatment of the resolver call before it can satisfy the green-commit rule.

#### Cross-Plan Assessment

**Overall lane risk: HIGH.** The immediate execution blockers are the undeclared `25-01` → `25-02` test dependency and the missing `_tool` dependency in `25-04`. The reachability visitor also needs relative-import support before it can serve as the durable guard required by D-01.

The reviewed wave-2 plans declare separate modified files: `25-03` changes the sensitive-action paths (`.planning/phases/25-lean/25-03-PLAN.md:7-24`), while `25-04` lists the vulture targets (`.planning/phases/25-lean/25-04-PLAN.md:7-22`). The later composition plan explicitly moves the home-derived constants and sandbox updates together (`.planning/phases/25-lean/25-05-PLAN.md:33-40,75-76`); that is the right contract to preserve. The research also identifies the generation-bearing messages as keepers (`.planning/phases/25-lean/25-RESEARCH.md:200-215`).

**Limits:** This was a read-only review; I did not run the implementation or its test suite, and did not exhaustively audit the plans outside this lane. The project had no matching codebase-memory index, so findings are grounded in source reads and text searches rather than graph results.

### Lane B (`laneB-my-referee-one`)

#### 25-03

##### Summary

Retire the unused sensitive-action prompt and callback plumbing in three commits while preserving checksum prompts, repair forwarding, login-shell handoff behavior, and explicit rejection of the retired registry field.

##### Strengths

- The plan correctly identifies the empty prompt table and asks for an explicit retired-key check rather than assuming unknown tool keys are rejected (`installer/post_install.py:100–120`; `.planning/phases/25-lean/25-03-PLAN.md:159–167`).
- It explicitly preserves the checksum prompt and its shared worker-to-modal plumbing (`installer/execute_screen.py:837–847`; `.planning/phases/25-lean/25-03-PLAN.md:130–134`).
- It identifies repair forwarding as live behavior: `_with_force` conditionally adds `repair=True` (`installer/session.py:279–305`).

##### Concerns

- **HIGH — The assertion rule makes the two-argument migration impossible without clarification.** The plan requires `run_post_install(tool, platform)` and forbids changing other assert lines (`.planning/phases/25-lean/25-03-PLAN.md:114–115, 163–168`). Existing live assertions pass a third argument inside the assertion itself, including the shell-init and OMZ plugin checks (`tests/test_post_install.py:686, 1129–1139`). Keeping those lines makes the new API fail; deleting the tests loses live behavior coverage.
- **HIGH — The deletion instructions can remove live handoff coverage and contradict one another.** The plan says to delete the “asked”-based tests and the `run(confirm)` test, but also says to strip only confirmation lines from mixed tests (`.planning/phases/25-lean/25-03-PLAN.md:107, 115, 168`). The affected post-install tests assert actual `chsh` handoff or refusal text (`tests/test_post_install.py:112–120, 174–184`); the `run(confirm)` test also asserts handoff outcomes (`tests/test_session.py:1228–1262`).
- **HIGH — Registered action doubles retain the old arity.** Task 2 specifies mechanical changes to install doubles but not action-table doubles (`.planning/phases/25-lean/25-03-PLAN.md:164–168`). The three-argument `boom` functions in `tests/test_engine.py:1174–1190, 1297–1309` will raise `TypeError` when called with two arguments, so the assertions for the intended exception messages fail.
- **HIGH — Task 1 cannot pass its prescribed gate as written.** Deleting the sensitive fixture leaves `SENSITIVE_PROMPTS` and `SensitivePrompt` unused in the import at `tests/test_execute_screen.py:49`; the plan defers the mechanical import cleanup to Task 2 (`.planning/phases/25-lean/25-03-PLAN.md:129–143, 163–168`). Also, the required count of six `ChecksumMismatchScreen` occurrences includes a reference in the sensitive class being deleted (`installer/execute_screen.py:143–148`); deleting that class leaves five, even though the checksum implementation is intact.
- **MEDIUM — The claimed negative documentation pin is not specified.** The plan says `tests/test_docs.py` pins the retired phrase’s absence, but Task 3 only deletes its positive pin (`.planning/phases/25-lean/25-03-PLAN.md:41, 192–202`; `tests/test_docs.py:91–120`). The one-time grep does not guard against reintroduction.

##### Suggestions

- Obtain an explicit decision permitting **only mechanical removal of the retired argument inside affected assertions**, with expected values unchanged. Enumerate those assertions and retain tests of live behavior.
- Inventory action-table doubles as well as install doubles; update their signatures in Task 2.
- Move the now-unused imports into Task 1’s cleanup, and replace the brittle checksum occurrence count with tests or checks of the actual checksum path.
- Distinguish confirmation-only assertions from handoff assertions, and add the promised negative documentation test if that guarantee is wanted.

##### Risk Assessment

**HIGH.** The specified migration conflicts with the assertion-preservation rule and otherwise leaves both intermediate validation and live action-failure tests broken.

#### 25-05

##### Summary

Move composition and environment constants from `setup.py` into a strict-typed, coverage-gated `installer/compose.py`, with test patch retargeting, a generalized home sandbox, and structural and CLI-assertion guards.

##### Strengths

- The plan identifies the two consequential hazards: import-time home paths and monkeypatches targeting the module that no longer owns a lookup (`.planning/phases/25-lean/25-05-PLAN.md:101–104, 221–232`; `tests/conftest.py:301–323`).
- Moving constants and extending the sandbox in the same commit is the right safety boundary (`.planning/phases/25-lean/25-05-PLAN.md:114, 120–148`).
- `installer/` is in both pyright strict and coverage scope, so the intended new location is under the stated gates (`pyproject.toml:42–45, 54–60`).

##### Concerns

- **HIGH — The verbatim move changes the schedule checkout directory.** `_schedule_context` currently computes `checkout=Path(__file__).resolve().parent` in `setup.py` (`setup.py:697–707`). After the prescribed verbatim move it resolves to `installer/`, not the repository root, while the plan allows only typing fixes and the `_REGISTRY` path adjustment (`.planning/phases/25-lean/25-05-PLAN.md:113, 161`). Schedule asset copying then looks for `installer/scripts/...` (`installer/schedules.py:732–740, 758–761`), and scheduled update arguments also receive the wrong checkout (`installer/schedules.py:853–859`). The existing root assertion would fail (`tests/test_setup.py:972–982`).
- **HIGH — Task 2 moves source-inspected code before updating its tests.** `_build_services` contains both `resolve_tag=` uses and the native-probe/ownership wiring (`setup.py:580–628`). Task 2 moves it but defers the `tests/test_versions.py` source-scan change to Task 3 (`.planning/phases/25-lean/25-05-PLAN.md:151–174, 179–189`); `tests/test_versions.py:150–160` will then find no keywords. A separate test also reads only `setup.py` and asserts that the moved wiring is present (`tests/test_setup.py:3540–3545`). Consequently Task 2 cannot meet its full-suite green-commit requirement as specified.
- **HIGH — Import-back and patch auditing omit reads of moved names.** The plan imports back only names still used by setup and audits `setattr` targets (`.planning/phases/25-lean/25-05-PLAN.md:99, 161–163, 189`). Once `_build_app` moves, setup no longer needs `_execute_inputs`, but tests still read `setup._execute_inputs` (`tests/test_setup.py:661, 2489–2504, 2525–2537`). Those reads are not caught by the patch audit and will fail if the unused import is removed.
- **HIGH — The reload instructions can restore real-home constants during a test.** The plan says to reload compose before setup and restore in the same order (`.planning/phases/25-lean/25-05-PLAN.md:103, 130–134`). The existing cleanup calls `monkeypatch.undo()` before reloading (`tests/test_setup.py:1368–1374`), which also undoes the shared fixture’s scratch `HOME` and path patches (`tests/conftest.py:261–275, 301–323`). A compose reload at that point can rebuild constants against the real home, outside the already-run sandbox fixture.
- **HIGH — The compose import acceptance check contradicts the required docstring.** Task 1 asks for a module docstring naming the “questionary/tty plumbing,” while Task 3 requires `grep -c "questionary\|prompt_toolkit" installer/compose.py` to print zero (`.planning/phases/25-lean/25-05-PLAN.md:134, 209`). The prescribed docstring alone violates that check even if there are no forbidden imports.
- **MEDIUM — The D-12 byte-identity check ignores uncommitted changes.** The proposed `git diff --quiet <BEFORE> HEAD` checks two commits, not the index and working tree being validated before the Task 3 commit (`.planning/phases/25-lean/25-05-PLAN.md:195–200`). It can report success while either protected file has staged or unstaged edits.

##### Suggestions

- Explicitly preserve the checkout root when moving `_schedule_context`, and retain the existing root assertion plus an asset-path regression test.
- Move **both** affected source-inspection test updates into Task 2; preserve their assertions while changing the inspected source path or sources.
- Audit direct reads, `vars(setup)` lookups, string targets, and patches separately. Retarget each according to the module whose globals the exercised code reads.
- Use scoped monkeypatching for reload tests and verify both modules’ constants after cleanup while `HOME` remains scratch.
- Check forbidden **imports** structurally rather than grepping all prose; compare protected files against the actual index and working tree.

##### Risk Assessment

**HIGH.** As specified, the move changes production schedule paths, breaks the required intermediate commit, and leaves a real-home sandbox escape during reload cleanup.

#### 25-06

##### Summary

Bound the Execute log with a `RichLog` subclass, expose Textual’s trimmed-line count, and show a dropped-lines label above the log, migrating streaming and completion writes in two commits.

##### Strengths

- Counting rendered strips rather than write calls handles multiline reports correctly: the installed Textual implementation increments `_start_line` by the number of trimmed strips (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:259–267`).
- The planned 5,000/5,001/6,000 tests and singular/plural wording directly cover the principal acceptance boundaries (`.planning/phases/25-lean/25-06-PLAN.md:94–100`).
- The existing handlers and their write ordering are identified explicitly (`installer/execute_screen.py:862–874, 904–953`).

##### Concerns

- **HIGH — Deferred replay can drop lines without updating the notice.** The planned helper reads `log.dropped` immediately after writing (`.planning/phases/25-lean/25-06-PLAN.md:73, 96–100`). Before a nonzero resize, Textual queues writes and later replays them through `RichLog.write`, outside that helper (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:132–139, 205–213`). A sufficiently fast burst can therefore trigger trimming during replay after the helper last checked the counter, leaving the label absent or stale. The proposed tests deliberately wait until the log has a size, so they miss this path.
- **HIGH — The first commit enables trimming without updating the label for all writers.** Task 1 migrates streaming writes only; Task 2 later migrates completion-report and PATH writes (`.planning/phases/25-lean/25-06-PLAN.md:99–112, 123–139`). In the intermediate commit, those existing direct writes (`installer/execute_screen.py:938–953`) can cause or increase trimming without updating the notice, violating the requirement for coherent intermediate commits.
- **MEDIUM — Empty writes can exceed the unconditional bound.** The plan exposes `write_log(*lines: str)` and claims at most 5,000 stored lines (`.planning/phases/25-lean/25-06-PLAN.md:21, 100`). In the installed Textual version, an empty renderable appends a blank strip outside the trimming branch (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:251–267`). Existing production writers appear to supply nonempty strings, but the helper’s stated contract does not enforce that assumption.
- **MEDIUM — Completion eviction and post-drop layout are not exercised end to end.** The multiline test calls the helper directly rather than driving `InstallRunFinished` across the boundary (`.planning/phases/25-lean/25-06-PLAN.md:122–127`); existing PATH assertions check content, not eviction (`tests/test_execute_screen.py:1416–1417`). The existing 80×20 Execute layout test checks the log before a drop (`tests/test_execute_screen.py:4157–4197`), not after the new label consumes a row.

##### Suggestions

- Refresh the notice when deferred writes are actually rendered, and add a pre-resize burst test that includes a run finishing before replay.
- Route **all** existing writes through the notice-updating path in the same commit that enables trimming.
- Define and test empty-string handling; add a near-full `InstallRunFinished` test and a post-drop 80×20 visibility/layout test.
- Add a long-line test for the promised wrap-off precision, and account for the fact that `textual>=8` permits versions beyond the locally inspected implementation (`pyproject.toml:6–10`).

##### Risk Assessment

**HIGH.** The normal bounded-log path is well targeted, but deferred replay and the first intermediate commit can silently discard output without the required notice.

#### Cross-Plan Assessment

**Overall lane risk: HIGH.** Plans 25-03 and 25-05 have concrete green-commit blockers; 25-05 also risks changing schedule behavior and test isolation. Plan 25-06 needs its notification mechanism to cover deferred rendering and every writer from the first bounded commit.

Wave order correctly places 25-03 before both 25-05 and 25-06 (`.planning/ROADMAP.md:737–743`). The declared file sets for 25-05 and 25-06 are disjoint (`.planning/phases/25-lean/25-05-PLAN.md:7–21`; `.planning/phases/25-lean/25-06-PLAN.md:7–9`), as are the declared production edits of 25-03 and 25-04. Concurrent execution still needs isolated working trees or serialization: each plan requires full-tree validation and commits while the other may have partial edits.

**Review status: Issues found — revise and re-review.** No tests were run and no files were changed. The project’s codebase-memory index was unavailable, so evidence is from direct source inspection; the Textual behavior was checked against the installed version only.

### Lane C (`laneC-my-referee-one`)

#### 25-07

##### Summary

Plan 25-07 starts the split by moving the mutation lock and modal classes, placing two shared schedule helpers in `ui_common.py`, and introducing an AST-based checker for the subsequent moves. The dependency order is sensible, but the checker as specified does not fully prove the safety property the plans rely on.

##### Strengths

- The modal dependencies identified by the plan match the source: `ScheduleTimeScreen` uses `_TIMES_LISTED`, and `CursorModelScreen` uses `_sentence` (`installer/wizard_app.py:3416`, `installer/wizard_app.py:3514`). Giving each a shared home avoids importing the app module from the modals.
- The mutation-lock move preserves the cross-process refusal path and the shared base used by `UnifiedApp` and tests (`installer/wizard_app.py:3605-3674`, `tests/test_mutation_runlock.py:90-120`).
- The plan requires the pilot tests and full gates on both intermediate commits (`.planning/phases/25-lean/25-07-PLAN.md:92-93`, `.planning/phases/25-lean/25-07-PLAN.md:112-120`).

##### Concerns

- **MEDIUM — The verbatim checker cannot establish that callers left behind were retargeted correctly.** The checker compares *removed definitions* with destination definitions (`.planning/phases/25-lean/25-07-PLAN.md:107`). For example, `_TIMES_LISTED` and `_sentence` are also referenced by the `SchedulesScreen` class that remains in `wizard_app.py` during this task (`installer/wizard_app.py:2953`, `installer/wizard_app.py:3139`). A missed rename or changed reference in that remaining class is outside the described comparison. The same limitation matters more as later plans move policy and uninstall symbols.
- **LOW — Checker semantics for top-level assignments are underspecified.** Several required moved names are assignments or annotated assignments, not functions or classes: `MUTATION_REFUSAL`, `SCHEDULED_RUN_REFUSAL`, and `_TIMES_LISTED` (`installer/wizard_app.py:3566-3569`, `installer/wizard_app.py:2642`). The checker description says “top-level names” but does not define how to extract names and compare `Assign` and `AnnAssign` nodes (`.planning/phases/25-lean/25-07-PLAN.md:107`). An implementation that inventories only `FunctionDef` and `ClassDef` can pass while omitting those constants.

##### Suggestions

- Specify assignment and annotated-assignment handling and add a small self-check containing a moved constant, a renamed constant, a deliberately lost name, and a changed body.
- Compare or explicitly inspect the remaining source’s references to moved names as well as the moved definitions; retain the pilot and full-suite checks as independent runtime evidence.

##### Risk Assessment

**MEDIUM.** The decomposition and named importers are well grounded, but the proposed mechanical proof is weaker than the plan’s claim that no moved name is lost or behavior changed.

#### 25-08

##### Summary

Plan 25-08 moves the Policies and Schedules screens after the modal split, relocates shared helpers and probe aliases, and explicitly retargets the schedule tests’ module-global access. Its most important test hazard is correctly identified, but its validation language overstates what the move checker proves.

##### Strengths

- The `vars(wizard_app)` hazard is real: the refresh test sets `_REFRESH_SECONDS` at `tests/test_schedules_view.py:596`, while the screen reads that global to create its interval at `installer/wizard_app.py:2725`. Retargeting the patch to the new module in the same commit is necessary.
- The separate lookup of `_SCHEDULE_COLUMNS` is also accounted for (`tests/test_schedules_view.py:673`; `.planning/phases/25-lean/25-08-PLAN.md:142`).
- The existing `move_link_mode` string patch is correctly distinguished from the Policies-screen call: the test drives the first-run app path (`tests/test_screen_family.py:2951-2957`), while the two production calls are separate (`installer/wizard_app.py:2551`, `installer/wizard_app.py:4209`).

##### Concerns

- **MEDIUM — The AST checker will not verify changes made inside the screen that remains behind during Task 1.** Task 1 renames `_fit` to `fit` while `SchedulesScreen` still lives in `wizard_app.py` (`.planning/phases/25-lean/25-08-PLAN.md:117`). Its existing `_fit` calls are at `installer/wizard_app.py:2850-2856`; they are not removed top-level nodes, so the checker described at `.planning/phases/25-lean/25-07-PLAN.md:107` does not compare them. A missed call can survive until that screen renders, despite a successful checker result.
- **LOW — The documented test-retarget instruction relies on a private test access mechanism without stating its typing constraint.** The plan correctly uses `vars(schedules_screen)` for `_SCHEDULE_COLUMNS` (`.planning/phases/25-lean/25-08-PLAN.md:142`), while pyright runs in strict mode over tests (`pyproject.toml:42-45`). The plan should preserve that distinction rather than permit a direct private import or attribute access, given its no-new-suppression rule.

##### Suggestions

- In Task 1, explicitly check all remaining `_fit` references in `wizard_app.py` after the move and include a render path for both Policies and Schedules in verification.
- Keep the `_REFRESH_SECONDS` patch loud and the `_SCHEDULE_COLUMNS` access via `vars`, as specified; document that the existing app-level `move_link_mode` patch must remain on `wizard_app`.

##### Risk Assessment

**MEDIUM.** The silent monkeypatch failure is handled well, and the wave order avoids an obvious cycle. The residual risk is an unverified reference in the still-unmoved screen, not the planned destination itself.

#### 25-09

##### Summary

Plan 25-09 moves Doctor and Uninstall last, splitting each into a screen and sibling module. It preserves the Doctor message classes and schedules the destructive Uninstall move with its importers and end-to-end tests. The same checker limitation applies, and the locked ordering and line-cap outcome depend on the next plan.

##### Strengths

- The plan preserves `GlobalsAudited` and its `generation` field (`.planning/phases/25-lean/25-09-PLAN.md:34-35`). That field is necessary: the handler rejects a result whose generation is no longer current before applying its report (`installer/wizard_app.py:950-964`).
- The Uninstall split keeps the review helpers and the destructive screen in the same task and runs the uninstall end-to-end suite (`.planning/phases/25-lean/25-09-PLAN.md:140-152`). The review information is meaningful to the deletion decision, not merely presentation (`installer/wizard_app.py:1032-1062`, `installer/wizard_app.py:1135-1159`).
- Keeping the two removal-quit strings in the app module matches their stated ownership and avoids an unnecessary cross-module move (`.planning/phases/25-lean/25-09-PLAN.md:37`; `installer/wizard_app.py:1090-1091`).

##### Concerns

- **MEDIUM — The move proof does not cover changed references outside the moved nodes.** Task 2 renames twelve uninstall globals and updates their uses (`.planning/phases/25-lean/25-09-PLAN.md:147-150`). The checker compares removed nodes after applying a rename map, but does not compare the rest of the source or independently validate imports and bindings (`.planning/phases/25-lean/25-07-PLAN.md:107`). The risk is material here because `UninstallScreen` uses these names in row selection and confirmation construction, including `_ENV_KEYS` and the three pseudo-row keys (`installer/wizard_app.py:1651-1663`, `installer/wizard_app.py:1792-1800`).
- **LOW — The cap is not established by this plan alone.** It explicitly permits over-800-line modules until plan 25-10 (`.planning/phases/25-lean/25-09-PLAN.md:81-84`). That is compatible with the planned wave order, but completion of 25-09 must not be reported as satisfying LEAN-03’s size acceptance; the measured uninstall screen class alone is 868 lines before imports (`.planning/phases/25-lean/25-RESEARCH.md:315-316`).

##### Suggestions

- Add a binding/reference check for every renamed Uninstall global, including references inside destination helpers and the moved screen, and run the existing unchanged confirmation and removal tests.
- Record actual post-move line counts in the 25-09 summary and hand every over-cap file explicitly to 25-10; retain the generation/supersede test selection.

##### Risk Assessment

**MEDIUM.** The plan preserves the documented race mechanism and includes the right destructive-path tests, but correctness still depends on thorough import and reference verification during a large rename.

#### Cross-Plan Assessment

**Overall lane risk: MEDIUM.** The three plans are sequential rather than parallel (`.planning/ROADMAP.md:745-755`), and their contracts place shared dependencies before consumers. The most significant shared weakness is the **AST checker’s limited scope**: it can compare moved definitions but, as specified, does not prove that remaining callers and module bindings were updated. Strengthening that check would improve all three plans without changing the intended refactor.

The review was grounded in the cited source and plan sections; the project was not present in the available codebase-memory index, so structural checks used source reads and searches instead. **Not checked:** a full execution of the planned refactor or its test gates; no files or host state were changed.

### Lane D (`laneD-my-referee-one`)

#### 25-10

##### Summary

Plan 25-10 finishes the screen split by cleaning review-history prose, extracting helpers from oversized modules, and adding permanent size, review-ID and import-cycle guards. It correctly schedules cleanup after the verbatim moves, but its cleanup scope misses code moved into existing modules, and some proposed extraction candidates are not pure.

##### Strengths

- The separate cleanup commit and AST comparison make it easier to distinguish a move from a later comment or docstring edit (`.planning/phases/25-lean/25-10-PLAN.md:98-119`). That supports the ordering requirement in `.planning/phases/25-lean/25-SPEC.md:129-131`.
- The plan keeps the size guard until after the split and cleanup, allowing the intermediate over-cap modules explicitly anticipated by `.planning/phases/25-lean/25-09-PLAN.md:80-83`.
- The proposed seeded review-ID test checks that the scanner can find both a comment and a docstring ID (`.planning/phases/25-lean/25-10-PLAN.md:148-161`).

##### Concerns

- **HIGH — Cleanup omits review-history text moved into existing modules.** Plan 25-08 moves `CompetingProbe` *with its comment* into `installer/systemd_daemon.py` (`.planning/phases/25-lean/25-08-PLAN.md:114-117`). That comment currently contains `WR-10` (`installer/wizard_app.py:178-182`). Plan 25-10 neither cleans that destination nor includes it in its permanent scan (`.planning/phases/25-lean/25-10-PLAN.md:98-107,148-161`). Consequently, review history from the split survives while the plan reports cleanup complete. The same scope question applies to other shared destinations of moved code.

- **HIGH — The fallback extraction list includes stateful methods, not just pure helpers.** Task 2 permits `_tool_entry` and `_with_failure` to move as explicit-argument functions, saying values read from `self` should be passed explicitly (`.planning/phases/25-lean/25-10-PLAN.md:80-82,129-133`). But `_tool_entry` calls other instance methods and writes `self._painted` (`installer/wizard_app.py:1267-1272,1303-1305`); `_with_failure` calls `_state_of` and deletes from `self._failed_lines` (`installer/wizard_app.py:1323-1337`). Passing only values read from `self` does not specify how those side effects and call relationships remain intact. This matters because the projected initial excess is approximately 164 lines, while the five preferred candidates save approximately 72 before cleanup (`.planning/phases/25-lean/25-RESEARCH.md:339-346`), so the fallback may be needed.

- **MEDIUM — The fallback message move does not explicitly update production references.** If `app_messages.py` is created, Task 2 calls out test importers but does not explicitly require `wizard_app.py` to import all three moved classes (`.planning/phases/25-lean/25-10-PLAN.md:124,129-134`). `UnifiedApp` constructs `RefreshPublished`, `RefreshFinished`, and `ScheduleDefaultsApplied` and uses them in handler annotations (`installer/wizard_app.py:3926-3945,4042-4044`). The executor can infer the imports, but the plan should name this production dependency rather than relying on a later failure.

##### Suggestions

- Include every destination that received code or attached comments from `wizard_app.py` in the one-time cleanup and review-ID verification, including `installer/systemd_daemon.py`; distinguish those destinations from files subject to the 800-line split cap if necessary.
- Choose genuinely pure extraction candidates first. For any stateful extraction, specify the exact mutable objects, callbacks, call sites and preserved side effects, and verify the destructive-review behavior with unchanged tests.
- Explicitly require `wizard_app.py` to import the three message classes when the optional message module is created.

##### Risk Assessment

**HIGH.** The planned cleanup can report success while leaving a known review ID behind, and the size fallback can require a behavior-sensitive extraction whose contract is not specified.

#### 25-11

##### Summary

Plan 25-11 is the phase gate: it compares the result with the pre-phase tree, runs the full local gates, reports the production-line delta, and records retained targets and CI results. Its reporting goals align with the locked requirements, but several proposed checks do not establish the guarantees attributed to them, and the CI handoff is incomplete for the repository’s workflow triggers.

##### Strengths

- The net-line report uses production paths only and defines net as deletions minus insertions, with both revisions recorded (`.planning/phases/25-lean/25-11-PLAN.md:18-20,119-131`), matching `.planning/phases/25-lean/25-SPEC.md:133-135`.
- The report explicitly inventories retained message classes and their post sites and handlers (`.planning/phases/25-lean/25-11-PLAN.md:74-78,125-131`), consistent with the keep-if-live rule and race-epoch protection in `.planning/phases/25-lean/25-CONTEXT.md:102-104`.
- Local verification includes strict checking and coverage of composition, plus the full project gates (`.planning/phases/25-lean/25-11-PLAN.md:99-113`); the applicable configuration is `pyproject.toml:42-45,54-60`.

##### Concerns

- **HIGH — A push alone does not establish the required CI result.** The plan relies on an orchestrator “push-per-wave” run and forbids the executor to push (`.planning/phases/25-lean/25-11-PLAN.md:27-30,81-85,129-131`). But `.github/workflows/ci.yml:3-6` triggers on pushes to `main` and on pull requests—not on arbitrary phase-branch pushes. The plan does not require an open PR, identify a run for the exact final head, or provide a blocking handoff if no run exists. It can therefore finish with a placeholder rather than the Ubuntu and macOS CI evidence required by `.planning/phases/25-lean/25-SPEC.md:71-74`.

- **HIGH — The suppression check can accept a newly added prohibition.** The proposed script compares only aggregate token counts before and after (`.planning/phases/25-lean/25-11-PLAN.md:97-103`). Removing one existing suppression and adding a different one elsewhere leaves the count unchanged, even though `.planning/phases/25-lean/25-SPEC.md:141-146` prohibits adding suppressions. Existing suppressions do occur in the test tree—for example, `tests/test_setup.py:2451`—so this is not an impossible input shape. The check cannot support the plan’s claim that it detects additions.

- **HIGH — The vulture comparison loses symbol identity and can miss new unused code.** Task 1 compares only quoted identifiers, not their defining locations or kinds (`.planning/phases/25-lean/25-11-PLAN.md:25,97`). A newly unused symbol with a name already reported anywhere in the baseline disappears from the set difference. This is material in this repository: the baseline already reports repeated names such as `BINDINGS`, `DEFAULT_CSS`, `compose`, and `on_mount` across several classes, including the screens being split (`installer/wizard_app.py:365,369,1185,2173,2177`). Name-only comparison therefore cannot establish the stated “no new unused code” gate.

- **MEDIUM — The D-12 guard does not protect all expected values it claims to protect.** Plan 25-11 inherits the guard defined in `.planning/phases/25-lean/25-05-PLAN.md:193-195`: it compares the source text of `assert` nodes in selected test functions. It does not compare parametrization data or other values outside those assertions. For example, `tests/test_setup.py:1597-1616` supplies the `expected` values in the decorator and asserts against the variable. Those values could change without changing any assert text, contrary to D-12’s requirement that expected values remain byte-identical (`.planning/phases/25-lean/25-CONTEXT.md:159-162`).

- **MEDIUM — The reporting command rejects one valid zero-change boundary.** The plan says zero net production lines is valid (`.planning/phases/25-lean/25-11-PLAN.md:27`), but treats empty `git diff --shortstat` output as a failure (`.planning/phases/25-lean/25-11-PLAN.md:133-135`). A net-zero diff with insertions and deletions produces output, but an identical production tree produces none; it should still be reported as zero rather than assumed to prove the wrong baseline.

##### Suggestions

- Make CI completion an explicit blocking handoff: require a PR-triggered or otherwise valid run for the recorded final head SHA, with both matrix jobs green; record the run URL or ID.
- Check added suppression occurrences in the phase diff, accounting for moved existing occurrences without allowing an addition to be canceled merely by a deletion elsewhere.
- Compare vulture findings using enough identity to distinguish separate definitions, with an explicit move mapping or reviewed exceptions for moved framework hooks.
- Extend D-12 verification to the relevant parametrization and expected-value sources, not only `assert` AST nodes.
- Treat an empty production diff as a measured zero after independently validating the baseline SHA.

##### Risk Assessment

**HIGH.** The final gate can miss violations of locked requirements, and its CI instructions do not guarantee that the required platform runs exist for the final phase head.

#### Cross-Plan Assessment

**Overall lane risk: HIGH.** The sequencing from 25-09 through 25-10 and 25-11 is explicit and avoids same-wave file overlap. However, 25-10’s cleanup scope leaves a known moved review ID outside its guard, while 25-11’s final checks can report compliance without proving the no-new-suppressions, no-new-unused-code, or final-head CI requirements.

**Limits:** This was a read-only review; later-wave modules and scratch guards do not yet exist at HEAD, so their eventual implementations could not be inspected. The full test suite and CI were not run.

