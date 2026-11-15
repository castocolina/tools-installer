---
phase: 25
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-15T21:59:44Z
review_cycle: 3
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


## Cycle 2 — reviewed at HEAD bfe38319

### Lane run facts

- opencode was launched directly, in the same way as cycle 1, across four lanes with the same plan split. The cycle-2 prompt added a note asking reviewers to rule on each R1 id and look for regressions.
- Lane A: exit 0, 21.5 KB. Lane B: exit 0, 21.5 KB. Lane C: exit 0, 14.8 KB. Lane D: exit 0, 25.5 KB. Every lane covered every plan id in its lane, and no failover was needed.
- Raw output: `.planning/phases/25-lean/.review-diagnostics/20261115T213302Z-cycle2/` (gitignored).
- After the lanes finished, `~/.claude/gsd-core` and `~/.claude/.gsd-source` were absent and no opencode run was left.
- A separate read-only verifier re-checked every HIGH, every MEDIUM and every "still open" claim against the source.

### Verified findings ledger (cycle 2)

Raw: 6 HIGH, 10 MEDIUM, plus 5 "still open" claims. After verification:
- 1 HIGH confirmed (R2-19).
- 2 MEDIUM (R2-03 and R2-05, both downgraded from HIGH).
- 12 LOW.
- 4 findings refuted, and 2 of the "still open" claims refuted (R1-10, R1-23).

R2-19 is trivial: a two-path command edit. R2-11 corrects the cycle-1 R1-23 ledger entry, which misread how Textual handles an empty write.

| ID | Plan | Raw | Verified | Finding (verified form) | Required property for the replan |
|----|------|-----|----------|-------------------------|-----------------------------------|
| R2-01 | 01 | MEDIUM | LOW | The relative-import guard (`25-01-PLAN.md:157`) raises only when the package has "fewer than `level - 1` components". `from .. import x` in `installer/a.py` passes that check and resolves to an empty base. R1-01 is still open for the same reason | A level>0 `ImportFrom` raises whenever the package has fewer than `level` components. A scratch-tree case covers `from .. import x` in `installer/a.py` (raises) and `installer/sub/y.py` `from .. import a` (resolves to `installer.a`) |
| R2-03 | 02 | HIGH | MEDIUM | `installer/version_cache.py` has no method fingerprint. `VersionCacheEntry` holds `latest_version`/`checked_at`/`failed_at`/`digests` (`:54-59`) keyed by tool id. The `{"kind","params"}` hash is `receipts.method_key` (`installer/receipts.py:111-116`). An old pi entry is a hit, not a miss. Task 2's test spec is wrong | The pin is `test_an_old_pi_version_cache_entry_loads_unchanged`: an old `tools.pi` entry loads unchanged and is looked up by tool id (no fingerprint, no miss) |
| R2-04 | 02 | MEDIUM | LOW | No ownership record is persisted. Ownership resolves live (`installer/version_status.py` `_resolve_owner_from` → `resolve_ownership`). The persisted inputs are the receipt and the `versions.json` `managers` snapshot, which holds no method kind | The plan and SUMMARY state that D-10's "ownership record" has no persisted format and is resolved live |
| R2-05 | 03 | HIGH | MEDIUM | `test_each_shell_init_prompt_shows_its_effect` (`tests/test_execute_screen.py:5621`), `test_the_login_shell_prompt_is_unchanged` (`:5642`) and `test_markup_in_review_values_renders_literally` (`:5682`) call `_sensitive_action_screen`/`_sensitive_labels` (`:1087,1104`). Those helpers sit in the block Task 1 deletes, and the plan names none of the three tests. Deleting them also orphans the `SHELL_INIT_TOOLS, shell_init_bundle` import (`:61`) and `_LOGIN_SHELL_TEXT` (`:5615`) | The two prompt-only tests (plus `_LOGIN_SHELL_TEXT` and the orphaned import) are DELETE. The markup test is STRIP: it loses only its modal lines and keeps the `assert any(prompt.startswith(f"○ {markup_id}") ...)` line (`:5702`) byte-identical |
| R2-06 | 03 | HIGH | REFUTED | Dropping the retired positional argument inside an assert is a deleted-target change (SPEC Constraints, `25-CONTEXT.md` D-11 "the `confirm` parameter ... and the test doubles"). The expected values are byte-identical. R1-10 is resolved | None |
| R2-08 | 03 | still open | LOW | STRIP names "the two `SENSITIVE_POST_INSTALL_ACTIONS == ()` lines" in `tests/test_model.py`. One of them (`:1969`) sits inside the DELETE-class `test_sensitive_tables_are_empty` | Each line is classified once. STRIP names only the line in `test_post_install_action_names_include_the_new_actions` |
| R2-09 | 05 | HIGH | REFUTED | At Task 1, setup's own code still reads every moved constant (`setup.py:344,496,497,582,1164,1179,1352`), so every binding stays. Task 2 retargets the patches in the same commit that drops reads (`25-05-PLAN.md:172,174`) | None |
| R2-10 | 05 | MEDIUM | REFUTED | All 29 `"--all"` uses in the frozen `tests/test_setup.py` are literal `setup.main([...])` calls inside 25 test functions. No helper hides one, and no test uses `--categories` | None |
| R2-11 | 06 | HIGH | REFUTED (corrects R1-23) | A `str` write always goes through Textual's trim. `Text("")` renders `Segment("")`+`Segment("\n")` (rich `text.py:731-734`), which is one line (`segment.py:259-269`). Only a renderable that yields no segments reaches the no-trim branch (`_rich_log.py:255-257`), and every writer passes `str`. The plan's "non-empty writes" caveat is wrong | The bound is stated for every `write_log` call, with no caveat. A test writes `""` at 5,000 lines and sees 5,000 lines with `dropped == 1` |
| R2-12 | 06 | MEDIUM | LOW | Textual's pre-size queue is unbounded, but in production it lasts only one layout pass (`installer/execute_screen.py:613,620`) | Optional note |
| R2-13 | 06 | MEDIUM | LOW | `textual>=8` has no upper bound, but `uv.lock` pins 8.2.7, and the boundary and replay tests fail loudly on a change | Optional note |
| R2-15 | 07 | MEDIUM | LOW | `p25-moved-same.py` selects only names removed from the source. A post-commit `--rev HEAD` run checks zero names and still exits 0. A copy left behind is not flagged | The checker flags a copy left behind (defined in the target and still in the source) and fails when it checked zero names. Verification runs before each commit, or against the task's parent commit |
| R2-16 | 08 | MEDIUM | LOW | The same checker gap as R2-15 | Covered by R2-15 |
| R2-17 | 09 | MEDIUM | LOW | The same checker gap: a retained `_DOCTOR_READ_ERROR` copy escapes the class/def grep | Covered by R2-15 |
| R2-18 | 10 | MEDIUM | LOW | `_config_lines` reads the disk (`installer/wizard_app.py:1863`). It still meets the plan's extraction criteria, but "pure" is loose | `config_lines` keeps its one call site and is never cached or hoisted |
| R2-19 | 11 | HIGH | **HIGH** | The vulture-60 multiset gate scans only `installer/` (`25-11-PLAN.md:25,98`). After 25-05, `_sync_terminals_and_report`, `_reconcile_headless`, `_build_app`, `_RC_PATHS` and `_WARN_CONSOLE` live in `installer/compose.py` while their only callers are in `setup.py`, so five new pairs appear and the gate fails the intended refactor. R1-33 stays open until this is fixed | Both vulture runs scan `installer` and `setup.py` at confidence 60, the same production scope on both sides |
| R2-20 | 11 | MEDIUM | LOW | Module-path normalization can pair only an identical line carrying the same suppression on the same private name. A wrong-module retarget fails pyright and the test | Optional |

CYCLE_SUMMARY: current_high=1 current_actionable=8

## OpenCode Review (opencode-referee-one) — cycle 2 raw lanes

### Lane A (`laneA-my-referee-one`)

#### 25-01

##### Summary

The plan adds a permanent AST import-reachability guard, with scratch-tree cases, dispatch-table inventory, and checks on the helper-assets exemption. It addresses the three cycle-1 findings in substance, but the revised relative-import algorithm still has a boundary error.

##### Strengths

- The orphan test requires the guard to identify a specific unreachable module rather than merely pass on the current tree (`.planning/phases/25-lean/25-01-PLAN.md:105-120`).
- The expanded dispatch inventory includes `_PATH_QUERIES`, whose tuple values contain the live ownership-query functions (`.planning/phases/25-lean/25-01-PLAN.md:80,150-155`; `installer/install_ownership.py:209-218`).
- The exemption check now looks for imports into the exempt package, not just the directory’s existence (`.planning/phases/25-lean/25-01-PLAN.md:152`).

##### Concerns

- **MEDIUM — Relative imports one level above the top-level package are not rejected.** The revised rule raises only when the package has *fewer than* `level - 1` components (`.planning/phases/25-lean/25-01-PLAN.md:157`). For `installer/a.py`, `from .. import x` has one package component and `level - 1 == 1`; the prescribed comparison permits removal of the only component and silently produces an empty base, although Python rejects the import as beyond the top-level package. The new negative case covers only a relative import in `setup.py`, whose package starts empty (`.planning/phases/25-lean/25-01-PLAN.md:149`). This leaves R1-01 **still open at the package boundary**.

##### Cycle-1 dispositions

- **R1-01: still open** — ordinary relative forms are specified, but the equal-depth escape above is not rejected.
- **R1-02: resolved** — `_PATH_QUERIES` is listed and the plan adds an inventory equality check (`.planning/phases/25-lean/25-01-PLAN.md:150-155`).
- **R1-03: resolved** — the exemption test checks reachable imports against the exempt modules (`.planning/phases/25-lean/25-01-PLAN.md:152`).

##### Suggestions

- Reject a relative import when removing `level - 1` components would leave no package, and add scratch cases for both `installer/a.py: from .. import x` and a valid nested-package parent import.
- Keep the runtime dispatch inventory and seeded orphan tests independent of the real-tree pass.

##### Risk Assessment

**MEDIUM.** The current tree has no relative imports according to the measured inventory, so the defect is not an immediate green-commit blocker; it weakens the permanent guard for a valid future source edit.

#### 25-02

##### Summary

The plan retires `host_setup` in a single production-and-test commit, preserves native manual handoffs and the pnpm refusal, then adds compatibility pins and updates documentation. The revised smoke-key and Pi ownership cases are well grounded. One compatibility test, however, is specified against a cache mechanism that does not exist.

##### Strengths

- The plan retains native handoffs rather than deleting the shared outcome field: `install_tool` independently returns a manual result for native methods (`installer/engine.py:267-277`; `.planning/phases/25-lean/25-02-PLAN.md:164-167`).
- The existing no-method pnpm refusal test remains unchanged, including its no-command assertion (`tests/test_update.py:1541-1551`; `.planning/phases/25-lean/25-02-PLAN.md:158-169`).
- The replacement smoke-key sample uses `rpm_ostree`, which excludes `smoke_argv`, unlike `dnf` (`installer/model.py:103-106`; `tests/test_model.py:761-784`).

##### Concerns

- **HIGH — Task 2 requires a version-cache miss based on a nonexistent method fingerprint.** The plan says `installer/version_cache.py` fingerprints `{"kind": method.kind, "params": ...}` and requires an old `host_setup` entry to miss for Pi’s current methods (`.planning/phases/25-lean/25-02-PLAN.md:197-203`). That fingerprint actually belongs to `receipts.method_key` (`installer/receipts.py:111-116`). A `VersionCacheEntry` contains version, timestamps, and digests—not a method kind or fingerprint (`installer/version_cache.py:54-59`); the refresh path looks entries up by `tool.id` (`installer/version_status.py:1827,1857-1867`). An executor cannot make the specified miss assertion pass while preserving current behavior. The plan also says these are pinning tests that “pass at once” (`.planning/phases/25-lean/25-02-PLAN.md:205`), making the contradiction an execution blocker.
- **MEDIUM — The compatibility task does not specify an old ownership-record check.** D-10 explicitly asks that an earlier Pi ownership record be read without crashing (`.planning/phases/25-lean/25-CONTEXT.md:144-146`). Task 2 names a receipt, a version-cache entry, and *newly resolved* pnpm ownership (`.planning/phases/25-lean/25-02-PLAN.md:201-208`). A fresh `_resolve` result is not by itself a test of reading an old persisted ownership record. The plan should first establish whether such a record exists and name the applicable reader or record that no such persisted format exists.

##### Cycle-1 dispositions

- **R1-04: resolved** — neither the Task 1 nor plan-level pytest command names the file created by parallel 25-01 (`.planning/phases/25-lean/25-02-PLAN.md:175-176,273-274`).
- **R1-05: resolved** — the plan specifies the `rpm_ostree` sample and preserves the existing error assertion (`.planning/phases/25-lean/25-02-PLAN.md:133,179-182`; `tests/test_model.py:761-784`).
- **R1-06: resolved** — Task 2 explicitly constructs the bun-plus-node Pi fixture with pnpm evidence and asserts pnpm ownership (`.planning/phases/25-lean/25-02-PLAN.md:201-208`; `tests/test_ownership.py:3297-3305`).

##### Suggestions

- Replace the nonexistent version-cache fingerprint/miss case with an executable compatibility pin based on the actual stored format and lookup behavior. If the intended fingerprint is the receipt method key, test that reader separately rather than attributing it to the version cache.
- Trace ownership persistence and document either the exact old-record fixture and reader or evidence that no such persisted record exists.

##### Risk Assessment

**HIGH.** Task 2’s required cache behavior contradicts the implementation, so the plan cannot be executed as written without either changing behavior or revising the acceptance.

#### 25-04

##### Summary

The plan triages vulture candidates, removes dead symbols in individually reversible commits, and moves the registry-integrity helper and its tests into the test suite. Its cycle-1 revisions supply the missing test helper and explain the release lookup removal. The main residual risk is the breadth and precision of the vulture classification rather than a demonstrated immediate blocker.

##### Strengths

- The per-symbol protocol requires production-caller checks before deletion (`.planning/phases/25-lean/25-04-PLAN.md:93-97`), which is important because vulture scans `installer/` while several candidates have callers in `setup.py` (`.planning/phases/25-lean/25-RESEARCH.md:219-238`).
- The registry-integrity relocation now includes `_tool`, which both moved tests need (`.planning/phases/25-lean/25-04-PLAN.md:143-148`; `tests/test_deps.py:15-27,153-163`).
- The `release_tag` revision accounts for both assignments and the release call: `resolve_target` makes the GitHub release lookup first, and the production resolver memoizes subsequent lookups (`installer/download.py:114-120`; `installer/verify_registry.py:372-390,628-650`).

##### Concerns

- **LOW — The framework-dispatched category is overly broad as a deletion rule.** The plan says Textual hooks “and similar” plus enum members in the vulture output are never deleted as one category (`.planning/phases/25-lean/25-04-PLAN.md:33-35,188-189`). That resolves the cycle-1 request for a category, but a name-shaped hook is not necessarily registered or invoked merely because it resembles `on_*`; the plan does not require checking its owning class or framework contract. The risk is retaining dead candidates while reporting every candidate triaged, rather than an identified live-code deletion.

##### Cycle-1 dispositions

- **R1-07: resolved** — the relocation includes a verbatim `_tool` copy in the same commit (`.planning/phases/25-lean/25-04-PLAN.md:147-148`).
- **R1-08: resolved** — the field, constructor keyword, and both assignments are removed together, with registry-verifier tests and ruff specified (`.planning/phases/25-lean/25-04-PLAN.md:115,123-125`).
- **R1-09: resolved** — the plan now has the requested framework-dispatched summary category (`.planning/phases/25-lean/25-04-PLAN.md:33-35,188-189`), subject to the precision concern above.

##### Suggestions

- For each grouped framework candidate, record enough evidence to distinguish a genuinely framework-invoked hook or enum value from an unused name; keep the summary compact, but do not classify solely by spelling.
- Preserve the existing registry assertions at `tests/test_registry.py:674,2052` when relocating the helper.

##### Risk Assessment

**LOW.** The identified cycle-1 execution blockers are addressed; the remaining concern is completeness of the dead-code report.

#### Cross-Plan Assessment

**Overall lane risk: HIGH**, driven by 25-02’s impossible version-cache acceptance. Correct that contract before execution; also close the relative-import boundary gap in 25-01.

- Wave ordering now places both 25-03 and 25-04 after 25-01 and 25-02 (`.planning/phases/25-lean/25-03-PLAN.md:3-6`; `.planning/phases/25-lean/25-04-PLAN.md:3-6`). Their declared modified-file lists do not overlap (`.planning/phases/25-lean/25-03-PLAN.md:7-24`; `.planning/phases/25-lean/25-04-PLAN.md:7-22`).
- The later Doctor split explicitly accounts for 25-04’s `_BodyStatic` replacement and preserves the generation-bearing message (`.planning/phases/25-lean/25-09-PLAN.md:98-100,113-135`).
- **Additional cross-plan requirement risk:** 25-06 expressly limits its bound to *non-empty* writes (`.planning/phases/25-lean/25-06-PLAN.md:21,28,107-111`), whereas the locked requirement says the log keeps **at most 5,000 lines** (`.planning/phases/25-lean/25-SPEC.md:64-69`). The completion handler writes a captured report without checking it for emptiness (`installer/execute_screen.py:938-941`). The plan acknowledges that an empty renderable can append beyond the limit (`.planning/phases/25-lean/25-06-PLAN.md:76`); this needs resolution in the owning lane without silently dropping visible blank output.

**Limits:** Read-only review; no implementation or test gates were run. The available codebase-memory project list did not include this repository, so source checks used direct reads and searches; plans outside this lane were checked only for the cited contracts.

### Lane B (`laneB-my-referee-one`)

#### 25-03

##### Summary

The plan retires the sensitive-action prompt and callback plumbing in three commits, while retaining checksum prompts, repair forwarding, and login-shell handoff behavior. It also explicitly rejects the retired registry field. The revised test classification improves the migration, but Task 1 misses later prompt tests and the proposed assertion exception conflicts with the locked review constraints.

##### Strengths

- The removal target is grounded in the implementation: `SENSITIVE_PROMPTS` is empty, and `sensitive_prompt` reads from that table (`installer/post_install.py:100-120`).
- The plan preserves the checksum prompt and its shared worker plumbing rather than deleting all modal infrastructure (`.planning/phases/25-lean/25-03-PLAN.md:101,133-137`; `installer/execute_screen.py:98-140,191-194`).
- Repair forwarding is explicitly retained: `_with_force` currently adds `repair=True` for selected rows (`installer/session.py:279-305`).

##### Concerns

- **HIGH — Task 1 leaves tests calling a deleted helper and screen.** The instructed deletion ends at the early prompt-test block (`.planning/phases/25-lean/25-03-PLAN.md:108,129,134-136`), but later tests still call `_sensitive_action_screen` and `_sensitive_labels` at `tests/test_execute_screen.py:5621-5657,5682-5707`. The helper itself is inside the deleted block (`tests/test_execute_screen.py:1087-1106`), so Task 1 cannot pass its specified suite. The final markup test also checks live review-row rendering at `tests/test_execute_screen.py:5695-5702`; deleting the entire test would lose that coverage.
- **HIGH — The R1-10 exception changes assertions despite the locked prohibition.** The plan permits removing the third argument inside existing assertions (`.planning/phases/25-lean/25-03-PLAN.md:110,118`), as needed for assertions such as `tests/test_post_install.py:686`. But the request permits only import-path or monkeypatch-target changes, or deletion of a deleted target’s tests, and the spec prohibits changing an assertion to make the refactor pass (`.planning/phases/25-lean/25-SPEC.md:103,143-146`). The plan cannot authorize that exception itself.

##### Cycle-1 dispositions

- **R1-10: still open.** The plan now explains the mechanical edit and retains expected values, but it does not resolve the conflict with the locked assertion rule.
- **R1-11: still open.** Mixed post-install and session coverage is better classified (`.planning/phases/25-lean/25-03-PLAN.md:108-110`; `tests/test_post_install.py:112-120,174-184`; `tests/test_session.py:1296-1323`), but the later Execute prompt tests were missed. Also, `test_sensitive_tables_are_empty` in `tests/test_model.py:1968-1979` is listed for deletion and its assertion is also included in the strip list.
- **R1-12: resolved.** Both action-table doubles are expressly migrated to two parameters in the same task (`.planning/phases/25-lean/25-03-PLAN.md:110,173`).
- **R1-13: resolved for the reported import and count issues.** Task 1 removes the orphaned imports and expects five checksum-screen occurrences (`.planning/phases/25-lean/25-03-PLAN.md:136,145-147`). The separate missed tests above remain a blocker.

##### Suggestions

- Classify the later prompt-only tests for deletion and strip only the deleted-modal portion of `test_markup_in_review_values_renders_literally`, preserving its review-row assertion.
- Obtain an explicit owner amendment for the narrowly mechanical assertion edits, or provide an implementation that meets the existing prohibition without weakening live tests.
- Remove the duplicate classification of the model test.

##### Risk Assessment

**HIGH.** Task 1 leaves the suite broken, and the assertion migration requires a decision outside the plan’s authority.

#### 25-05

##### Summary

The plan moves composition and environment constants into `installer/compose.py`, extends the home sandbox, retargets monkeypatches, and adds structural and CLI-preservation guards. The schedule-path and source-scan revisions address concrete cycle-1 failures. The remaining blocker is that test patch retargeting is scheduled one commit after constants cease to be `setup.py` globals.

##### Strengths

- The corrected schedule checkout preserves the current repository-root behavior (`setup.py:697-707`; `.planning/phases/25-lean/25-05-PLAN.md:106,166-168`).
- Both source-inspection tests move with `_build_services`, preserving their assertions (`setup.py:589-595,622-632`; `tests/test_versions.py:150-160`; `tests/test_setup.py:3540-3545`; `.planning/phases/25-lean/25-05-PLAN.md:170`).
- The sandbox extension correctly recognizes that `HOME` alone cannot redirect import-time constants (`setup.py:112-136`; `tests/conftest.py:261-275,301-323`).

##### Concerns

- **HIGH — Task 1 can remove setup bindings that existing tests still monkeypatch, before Task 2 retargets them.** Task 1 says setup imports back constants **its code still reads** (`.planning/phases/25-lean/25-05-PLAN.md:138`), while `patch_composition` and patch-site migration are deferred to Task 2 (`.planning/phases/25-lean/25-05-PLAN.md:155-174`). In particular, Task 1 still has the helper bodies in `setup.py`, so its exact intermediate imports must cover their globals **and** the test-only bindings. After Task 2 moves those bodies, `_DAEMON_PLIST_PATH` and `_LINUX_DAEMON_UNIT_DIR` have no remaining setup-side reads (`setup.py:132-136,320-345,472-497`), yet tests patch `setup` directly (`tests/test_setup.py:575-584,3064,3524`). The plan should explicitly ensure that each task’s import cleanup and patch retargeting occur together; otherwise `monkeypatch.setattr` raises or a patch misses the owning module. Task 2 does prescribe retargeting, but Task 1’s “every constant its code still reads” rule leaves no explicit allowance for bindings required only by tests or by the next task’s intermediate state.
- **MEDIUM — The D-12 guard identifies protected tests by source spelling, not by exercised route.** It selects functions whose own source contains `"--all"` or `"--categories"` (`.planning/phases/25-lean/25-05-PLAN.md:208`). The locked decision covers every test that *exercises* those flags (`.planning/phases/25-lean/25-CONTEXT.md:159-162`). A test driving the route through a helper rather than containing the literal would be omitted. The decorator comparison fixes the reported parametrization gap for selected tests, but does not establish complete selection.

##### Cycle-1 dispositions

- **R1-15: resolved.** The moved checkout uses the parent of `installer/` and the existing root assertion remains (`.planning/phases/25-lean/25-05-PLAN.md:168,184-185`; `setup.py:697-707`).
- **R1-16: resolved.** Both source scans are retargeted in Task 2, alongside the move (`.planning/phases/25-lean/25-05-PLAN.md:170`).
- **R1-17: resolved for the reported cases.** Direct reads and non-constant patch names are included in the audit and retargeting instructions (`.planning/phases/25-lean/25-05-PLAN.md:108,172-174,202`).
- **R1-19: resolved.** The forbidden-import check now examines AST imports, not prose (`.planning/phases/25-lean/25-05-PLAN.md:204`).
- **R1-20: resolved.** The protected-file diff compares the baseline with the working tree (`.planning/phases/25-lean/25-05-PLAN.md:208`).
- **R1-34: resolved for parametrized values.** The guard compares decorator source segments as well as assertions (`.planning/phases/25-lean/25-05-PLAN.md:208`; `tests/test_setup.py:1597-1617`). The selection limitation above is separate.

##### Suggestions

- Give Task 1 an explicit intermediate binding inventory and move any required test retargets into the same commit that removes a binding. Run the listed setup and sandbox tests before committing.
- Inventory flag-route tests through their helpers as well as literal occurrences, and pin that inventory or add a seeded indirect-route guard case.

##### Risk Assessment

**HIGH.** The move affects both test isolation and module-global lookup. Its intermediate binding contract needs to be explicit enough to guarantee a green, sandboxed commit.

#### 25-06

##### Summary

The plan subclasses `RichLog`, routes all Execute log writes through one helper, and updates a separate dropped-lines label from Textual’s trim counter. Its revised callback covers deferred replay and completion writes, but its empty-write qualification does not satisfy the locked unconditional bound.

##### Strengths

- Textual increments `_start_line` by the number of stored strips trimmed, which is appropriate for multiline writes (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:251-267`).
- The callback is placed in the override that Textual calls during deferred replay (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:132-139`; `.planning/phases/25-lean/25-06-PLAN.md:106-111`).
- All existing streaming and completion writers are migrated in the commit that enables trimming (`installer/execute_screen.py:862-874,904-953`; `.planning/phases/25-lean/25-06-PLAN.md:111`).

##### Concerns

- **HIGH — The plan knowingly permits more than 5,000 stored lines.** The locked requirement is “at most 5,000 lines” (`.planning/phases/25-lean/25-SPEC.md:64-69`). Textual appends an empty renderable without entering its trim branch (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:251-267`). The plan instead narrows the promise to *after non-empty writes* and forbids skipping empty writes (`.planning/phases/25-lean/25-06-PLAN.md:28,76,109-111`). Consecutive empty writes can therefore exceed the cap and produce no dropped-lines notice. This is a contract failure even if the typical completion report is nonempty.
- **MEDIUM — The deferred queue itself is not bounded before the first resize.** Textual queues every pre-size write without applying `max_lines` (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:124-139,205-213`), and the plan explicitly tests a 5,001-write queued burst (`.planning/phases/25-lean/25-06-PLAN.md:102`). The callback fixes the eventual notice, but not memory growth while rendering remains deferred. This weakens the stated protection against unbounded output (`.planning/phases/25-lean/25-06-PLAN.md:164-173`).
- **MEDIUM — The implementation relies on Textual internals without a supported-version contract.** `textual>=8` has no upper bound (`pyproject.toml:6-10`), while the design copies the installed `write` signature and relies on `_start_line` and replay internals (`.planning/phases/25-lean/25-06-PLAN.md:76,106-109`). The planned tests establish behavior for the installed version, not necessarily future allowed versions.

##### Cycle-1 dispositions

- **R1-21: resolved for notice refresh.** Replay invokes the overridden `write`, which calls the label callback when trimming changes the count (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:132-139`; `.planning/phases/25-lean/25-06-PLAN.md:102,109`).
- **R1-22: resolved.** Both handlers are migrated in Task 1 (`.planning/phases/25-lean/25-06-PLAN.md:111`).
- **R1-23: still open.** The plan documents the exception instead of maintaining the spec’s unconditional 5,000-line cap.
- **R1-24: resolved for the requested coverage.** Task 2 specifies both a near-full completion report and a post-drop 80×20 layout test (`.planning/phases/25-lean/25-06-PLAN.md:138-145`).

##### Suggestions

- Preserve blank-line rendering while enforcing the cap and updating the dropped count after empty writes; add a test with repeated empty writes at the boundary.
- Decide how pre-resize buffering is bounded, then test a burst substantially larger than the cap before resize.
- Document and test the supported Textual version range or use an integration contract that does not silently depend on a changing private counter.

##### Risk Assessment

**HIGH.** The stated implementation can violate the phase’s principal bounded-log requirement.

#### Cross-Plan Assessment

**Overall lane risk: HIGH.** The wave order places sensitive-action retirement before both dependent plans, and the declared wave-3 file sets are disjoint (`.planning/ROADMAP.md:737-743`; `.planning/phases/25-lean/25-05-PLAN.md:7-21`; `.planning/phases/25-lean/25-06-PLAN.md:7-9`). The decisive blockers are the missed 25-03 tests, the unresolved assertion-rule conflict, and 25-06’s unconditional-cap violation. The composition move also needs a precise per-commit binding and patch inventory before parallel execution.

The review was read-only. I did not execute the plans or their gates, and I could not verify every cited source and test file exhaustively; the project had no matching codebase-memory index, so the findings above use direct source evidence.

### Lane C (`laneC-my-referee-one`)

#### 25-07

##### Summary

Plan 25-07 moves the mutation lock and modal screens first, gives the shared sentence and schedule-count helpers public homes, and introduces the AST checker reused by the next two plans. The dependency order is sensible. The checker improves on the cycle-1 version, but its success does not by itself prove that every intended definition moved or that its new global bindings are equivalent.

##### Strengths

- Moving the shared helpers before their consumers addresses real cross-references: both `SchedulesScreen` and the modal screens use `_sentence` and `_TIMES_LISTED` (`installer/wizard_app.py:2642,2656-2659,2953,3139,3416,3514`).
- **R1-25 — resolved as specified in the verified ledger.** The revised checker includes assignment and annotated-assignment bindings, checks for old renamed references in both source and targets, and retains ruff and pyright as checks for undefined names (`.planning/phases/25-lean/25-07-PLAN.md:107`). This addresses the verified property recorded at `.planning/phases/25-lean/25-REVIEWS.md:59`.
- The mutation-lock tests exercise the actual cross-process refusal and lock-release paths, not only imports (`tests/test_mutation_runlock.py:49-70,90-114`).

##### Concerns

- **MEDIUM — The checker can pass without checking an intended move.** It selects names defined at `HEAD` but absent from the working-tree source (`.planning/phases/25-lean/25-07-PLAN.md:107`). If an executor accidentally leaves a definition in `wizard_app.py` while also defining it in the destination, that name is not compared. In addition, rerunning the stated verification after committing against `--rev HEAD` compares the committed tree with itself and can check zero names (`.planning/phases/25-lean/25-07-PLAN.md:112,137,169-170`). The named class and constant greps catch some, but not all, omissions in later plans.
- **LOW — AST equality does not establish equivalent imported bindings.** For example, `_sentence` calls `sanitize_log_line` (`installer/wizard_app.py:2656-2659`), whose implementation removes terminal control characters (`installer/sanitize.py:13-22`). The moved function can have an identical AST while resolving that name to a different callable. The plan requires imports “they need” and runs tests, but its claim that the checker proves a verbatim move is broader than the mechanism (`.planning/phases/25-lean/25-07-PLAN.md:33,107,134`).

##### Suggestions

- Give the checker an explicit expected move manifest per task; require every expected name to disappear from the source, appear exactly once in the intended destination, and contribute to a nonzero checked count. Record the pre-task revision for any post-commit rerun.
- Describe the AST comparison as a body-preservation check, with import/binding review and existing behavior tests as separate evidence.

##### Risk Assessment

**MEDIUM.** The intended decomposition is supported by source and tests, but the shared proof mechanism can pass vacuously or miss an omitted move.

#### 25-08

##### Summary

Plan 25-08 moves Policies and Schedules sequentially, placing shared formatting and probe types in common homes. It identifies the important test hazard where a dictionary-based monkeypatch can silently affect the old module instead of the new screen.

##### Strengths

- **R1-26 — resolved.** Task 1 explicitly changes the `SchedulesScreen` calls to `fit` in the same commit as the helper move (`.planning/phases/25-lean/25-08-PLAN.md:117`); the calls exist at `installer/wizard_app.py:2850-2856`.
- The plan retargets both module-global schedule-test accesses: the refresh interval patch and the columns lookup (`tests/test_schedules_view.py:593-596,673`; `.planning/phases/25-lean/25-08-PLAN.md:142`). Making the patch use `setattr` makes a missing target fail loudly.
- Keeping the existing `move_link_mode` patch on `wizard_app` for the app path is appropriate: the cited test drives the deferred first-run flow (`tests/test_screen_family.py:2943-2977`).

##### Concerns

- **MEDIUM — The shared checker can miss an omitted policy or schedule definition.** Task 1 lists helpers and constants beyond those covered by its three-name acceptance grep (`.planning/phases/25-lean/25-08-PLAN.md:117,125-128`); Task 2 likewise moves a larger set than its four-class grep checks (`.planning/phases/25-lean/25-08-PLAN.md:142,150-153`). Because the checker selects only definitions removed from the source, an accidentally retained definition is not checked (`.planning/phases/25-lean/25-07-PLAN.md:107`). The full gates are valuable but do not themselves prove the no-leftover-definition contract.

##### Suggestions

- Supply explicit expected-name manifests for both tasks and check the source and designated destination for every listed helper and constant, alongside the existing behavior tests.

##### Risk Assessment

**MEDIUM.** The important patch retargets and sequencing are well specified; the remaining concern is completeness of the mechanical move proof.

#### 25-09

##### Summary

Plan 25-09 moves Doctor and Uninstall last, with sibling modules for messages and review helpers. It keeps the destructive Uninstall path and its tests together, and explicitly preserves Doctor’s generation-bearing message and handlers. The 800-line cap is intentionally deferred to plan 25-10.

##### Strengths

- The generation check is live behavior: `GlobalsAudited` carries the generation and `DoctorScreen` rejects stale results (`installer/wizard_app.py:274-287,950-957`). The plan moves the message and screen together and runs the relevant pilot tests (`.planning/phases/25-lean/25-09-PLAN.md:114-126`).
- The Uninstall screen and its review helpers move in the same task, with the uninstall end-to-end tests included (`.planning/phases/25-lean/25-09-PLAN.md:138-153`).
- The two quit strings are correctly left with `UnifiedApp`, rather than being moved with the adjacent review constants (`installer/wizard_app.py:1090-1091`; `.planning/phases/25-lean/25-09-PLAN.md:147`).

##### Concerns

- **MEDIUM — The “only the app remains” criterion is not fully checked.** The plan requires Doctor’s constants and helper to move (`.planning/phases/25-lean/25-09-PLAN.md:121`) and says the final source contains only the app, its messages, and two strings (`.planning/phases/25-lean/25-09-PLAN.md:40`). However, the final acceptance grep counts only top-level classes and functions (`.planning/phases/25-lean/25-09-PLAN.md:157`), while the reused checker examines only names removed from the source (`.planning/phases/25-lean/25-07-PLAN.md:107`). A retained duplicate constant such as `_DOCTOR_READ_ERROR` or `_GLOBALS_UNKNOWN` would therefore evade both checks (`installer/wizard_app.py:220-226,341`).
- **LOW — Size acceptance remains dependent on the next wave.** This plan appropriately acknowledges that its moved files may still exceed 800 lines (`.planning/phases/25-lean/25-09-PLAN.md:80-84`); the research projects the Uninstall module at roughly 964 lines before cleanup and extraction (`.planning/phases/25-lean/25-RESEARCH.md:329-346`). Completion of this plan alone should not be reported as satisfying LEAN-03.

##### Suggestions

- Check an explicit final top-level definition and assignment inventory for `wizard_app.py`, in addition to the per-task expected move manifests.
- Record actual post-move line counts in the handoff to 25-10 and verify its final cap guard after extraction.

##### Risk Assessment

**MEDIUM.** Race protection and destructive-path tests are retained, but the promised final ownership boundary is not completely enforced by the stated checks.

#### Cross-Plan Assessment

**Overall lane risk: MEDIUM.** The plans are sequential—07, then 08, then 09—so their shared-file edits are not scheduled in the same wave (`.planning/ROADMAP.md:745-752`). The main shared issue is that the AST checker proves equality only for definitions it detects as removed; it needs an expected move set and a stable baseline to prove completeness.

**Review status: Issues found — revise and re-review.** This was a read-only review. The project was not present in the available codebase-memory index, so findings use source and plan inspection; the refactor and its test gates were not executed. The future split files cannot yet be inspected at HEAD.

### Lane D (`laneD-my-referee-one`)

#### 25-10

##### Summary

Plan 25-10 completes the screen split in three ordered commits: remove review-history prose without changing executable ASTs, extract helpers from oversized modules, and add permanent size, review-ID and runtime-import guards. Its contracts address the three cycle-1 findings, although the size-reduction instructions still describe one filesystem-reading helper as pure.

##### Strengths

- The cleanup follows the verbatim split and is checked separately with an AST comparison that ignores docstrings (`.planning/phases/25-lean/25-10-PLAN.md:103-118`). That supports the ordering requirement in `.planning/phases/25-lean/25-SPEC.md:129-131`.
- The plan now explicitly keeps the stateful `_tool_entry` and `_with_failure` methods on the class (`.planning/phases/25-lean/25-10-PLAN.md:86,143`). Those methods respectively update `_painted` and delete from `_failed_lines` in the current source (`installer/wizard_app.py:1303-1305,1323-1337`).
- The permanent review-ID scanner has seeded comment and docstring cases, and its shared-module checks fail on missing named nodes (`.planning/phases/25-lean/25-10-PLAN.md:167-174`).

##### Concerns

- **MEDIUM — A prescribed “pure” extraction reads the filesystem.** Task 2 includes `_config_lines` among the first five side-effect-free helpers to move (`.planning/phases/25-lean/25-10-PLAN.md:40,86,142-143`). Its body calls `path.is_symlink()` and `path.exists()` (`installer/wizard_app.py:1853-1864`), so its result depends on live filesystem state. Moving it can preserve behavior, but describing it as pure obscures that its reads must remain at the same point in the removal flow; the locked decision permits pure helpers in the sibling (`.planning/phases/25-lean/25-CONTEXT.md:128`). Clarify the contract before an executor treats purity as permission to cache or precompute the result.

##### Cycle-1 dispositions

- **R1-28 — resolved.** The plan now cleans and guards `CompetingProbe` and the other named nodes moved into existing modules (`.planning/phases/25-lean/25-10-PLAN.md:108-115,170-174`). The original moved comment contains `WR-10` (`installer/wizard_app.py:178-182`).
- **R1-29 — resolved.** The two state-writing methods are explicitly excluded from extraction (`.planning/phases/25-lean/25-10-PLAN.md:86,143`).
- **R1-30 — resolved.** The optional message extraction now requires `wizard_app.py` to import all three moved classes and retargets their test importers (`.planning/phases/25-lean/25-10-PLAN.md:87,145`).

##### Suggestions

- Describe `_config_lines` as a filesystem-reading helper rather than a pure function, and require its calls and evaluation timing to remain unchanged. Alternatively, use genuinely pure candidates to meet the cap.
- Record actual post-cleanup and post-extraction line counts rather than relying on the projected savings (`.planning/phases/25-lean/25-RESEARCH.md:329-348`).

##### Risk Assessment

**MEDIUM.** The destructive-path tests and stateful-method exclusions reduce risk, but the extraction classification needs clarification for a helper that inspects live config paths.

#### 25-11

##### Summary

Plan 25-11 is the final phase gate: it compares the finished tree with the pre-phase revision, runs the local quality gates and race tests, and reports the production-line delta and retained targets. The revised multiset comparison fixes the original name-set masking problem, but its treatment of functions moved from `setup.py` makes the prescribed final gate reject a correct execution.

##### Strengths

- The report measures production paths only and defines net removed lines as deletions minus insertions, matching the locked precision requirement (`.planning/phases/25-lean/25-11-PLAN.md:19-20,127-128`; `.planning/phases/25-lean/25-SPEC.md:133-135`).
- The D-12 guard now compares decorator source as well as assertion source (`.planning/phases/25-lean/25-05-PLAN.md:204-208`; `.planning/phases/25-lean/25-11-PLAN.md:23,74-75`). This covers the expected values in the existing parametrization at `tests/test_setup.py:1597-1603`.
- The retained-target inventory correctly identifies the live adapter import and CLI filter (`installer/agent_settings.py:22`; `installer/app.py:111-115,137`).

##### Concerns

- **HIGH — The vulture comparison rejects live helpers moved into its scan scope.** The gate scans only `installer/` in both revisions and rejects any increased `(kind, name)` count except hooks on newly created classes (`.planning/phases/25-lean/25-11-PLAN.md:25,98`). Plan 25-05 moves `_sync_terminals_and_report` and `_reconcile_headless` into `installer/compose.py`, while their production callers remain in `setup.py` (`.planning/phases/25-lean/25-05-PLAN.md:100-101,166`; `setup.py:1327,1448,1473`). Before the move, their definitions are outside the vulture scan; afterward, their definitions are inside it but their callers are still outside. Vulture therefore can report them as newly unused even though they are live, and neither is an allowed Textual hook. The required gate would fail on the intended refactor. Compare equivalent production scopes—including `setup.py`—or explicitly prove and allow these external callers without permitting genuinely unused additions.

- **MEDIUM — Suppression-line normalization can pair a retarget that is not behavior-preserving.** The checker replaces *any* listed module prefix with the same placeholder before matching across files (`.planning/phases/25-lean/25-11-PLAN.md:76,98`). The current test suite has private-usage suppressions on `setup._timer_state_cache` (`tests/test_systemd_daemon.py:296-308`), and moving that function to `compose` is legitimate (`.planning/phases/25-lean/25-05-PLAN.md:100`). But the specified normalization also treats an unrelated listed destination, such as `wizard_app._timer_state_cache`, as equivalent. The stated self-check covers a valid `setup`→`compose` retarget, not an invalid cross-module pairing (`.planning/phases/25-lean/25-11-PLAN.md:98`). Restrict normalization to verified symbol-specific moves and test an invalid retarget.

##### Cycle-1 dispositions

- **R1-32 — resolved for the original aggregate-count defect.** One-for-one multiset pairing prevents a different deleted suppression line from paying for an added line (`.planning/phases/25-lean/25-11-PLAN.md:49,98`). The broader module-normalization risk above is new to the revision.
- **R1-33 — still open as an executable gate.** Multiset counts address the original duplicate-name masking issue, but the scan-scope mismatch above makes the revised gate fail for live moved helpers (`.planning/phases/25-lean/25-11-PLAN.md:98`; `setup.py:1327,1448,1473`).
- **R1-34 — resolved.** The guard compares each selected test’s ordered decorator source as well as its assertions (`.planning/phases/25-lean/25-05-PLAN.md:208`), and plan 25-11 runs it (`.planning/phases/25-lean/25-11-PLAN.md:101-102`).

##### Suggestions

- Run the vulture comparison over the same complete production call scope on both sides, with a self-check for a live helper moved from `setup.py` and a separate newly unused helper.
- Pair suppression-bearing lines using an explicit symbol-to-destination move map, and add a negative self-check for an incorrect listed module.

##### Risk Assessment

**HIGH.** The final gate can fail on the implementation the preceding plan requires, preventing phase completion without changing or weakening the check.

#### Cross-Plan Assessment

**Overall lane risk: HIGH.** The sequence correctly places comment cleanup and cap enforcement after the screen moves and before the phase gate (`.planning/ROADMAP.md:745-758`). The principal blocker is the final vulture comparison’s mismatch with the composition-move contract; resolving it requires coordinating plans 25-05 and 25-11, not changing the intended production behavior.

**Not checked:** I did not execute the plans, full test suite, or CI. The split destination files do not yet exist at HEAD, so their final imports, sizes, and generated guards could only be assessed against the plans and current source.


## Cycle 3 — reviewed at HEAD 67187186 (final cycle)

### Lane run facts

- opencode was launched directly, as in cycles 1-2, over four lanes with the same plan split. The cycle-3 prompt asked reviewers to rule on every R1/R2 id and to report only real blockers.
- Lane A: exit 0, 16.4 KB. Lane B: exit 0, 22.6 KB. Lane C: exit 0, 14.0 KB. Lane D: exit 0, 33.7 KB. Every lane covered every plan id in its lane, and no failover was needed.
- Raw output: `.planning/phases/25-lean/.review-diagnostics/20261115T215944Z-cycle3/` (gitignored).
- After the lanes finished, `~/.claude/gsd-core` and `~/.claude/.gsd-source` were absent and no opencode run was left.
- The orchestrator verified all four HIGHs directly against the source. Every lane rated its remaining items LOW: the R2-12 and R2-13 notes were already accepted, and the rest were execution-time verification notes. No MEDIUM was raised.

### Verified findings ledger (cycle 3)

| ID | Plan | Raw | Verified | Finding (verified form) | Fix applied by hand (trivial) |
|----|------|-----|----------|-------------------------|-------------------------------|
| R3-01 | 04 | HIGH | **HIGH**, trivial | `tests/test_deps.py:5-11` imports `requires_integrity_errors` from `installer.deps`. Task 2 moves the function out of `installer/deps.py` and moves its two tests, but never drops that import, so collection fails with ImportError | Task 2 drops `requires_integrity_errors` from that import list in the same commit, and an acceptance grep proves it is gone |
| R3-02 | 05 | HIGH | **HIGH**, trivial | `test_the_environment_d_dir_honours_xdg_config_home` runs `import setup; print(setup._ENVIRONMENT_D_DIR)` in a fresh interpreter (`tests/test_setup.py:1221-1222`). Its last production readers (`_cache_redirect_policies`, `_desktop_shell_policies`) move in Task 2, so ruff drops the import-back and the subprocess raises AttributeError. The AST patch audit does not read `-c` strings. This also keeps R1-17 open | Task 2 retargets that string to `import installer.compose as compose; print(compose._ENVIRONMENT_D_DIR)` in the same commit. The assert is unchanged, and the audit also scans string literals for `setup.<name>` of compose-only names |
| R3-03 | 05 | HIGH | **HIGH**, trivial | Replacing `_build_services._install`'s `**options` with explicit keyword defaults forwards `repair=False` on every row. `session._with_force` deliberately omits `repair` on ordinary rows (`installer/session.py:279-305`), and `_recording_install` (`tests/test_setup.py:602-621`) has no `repair` parameter, so this raises TypeError and breaks the omission contract | Type `**options` as `Unpack[_InstallOptions]`, a `TypedDict(total=False)` in compose with `checksum_policy: ChecksumPolicy` and `repair: bool`, and forward `**options` unchanged, so an omitted key stays omitted. pyright strict accepts this without a suppression |
| R3-04 | 11 | HIGH | **HIGH**, trivial | The final absence `rg` (`25-11-PLAN.md:112`) matches substrings. The live `_classify_source_lines` (`installer/shellrc.py:708,797,843,894`) and `"defaultPermissionMode"` (`installer/agent_settings.py:692`) would make a correct tree fail | The command uses `rg -nw` (whole words) with explicit names (`HOST_SETUPS`, `HOST_SETUP_IDS`, `_HOST_SETUP_OWNERS`, `_host_setup`, `_host_setup_owner`, `host_setup_handoff`, `host_setup_approval_disclosures`, `host_setup_update_argv`, `confirm_sensitive_action`, ...), so live identifiers that merely contain a retired name no longer match |

CYCLE_SUMMARY: current_high=4 current_actionable=0

**Cap rule (cycle 3 of 3).** All four HIGHs are verified and trivial, meaning each is a plan-text edit with no design question. Under the owner's 2026-11-15 amendment ("when the remaining HIGHs are trivial, fix them by hand and continue the GSD flow at any count"), the orchestrator fixed all four by hand in plans 25-04, 25-05 and 25-11 and recorded them under `### Round 3` in each plan's ledger. After those fixes, unresolved: 0 HIGH and 0 actionable MEDIUM. The accepted LOWs are R2-12 and R2-13.

## OpenCode Review (opencode-referee-one) — cycle 3 raw lanes

### Lane A (`laneA-my-referee-one`)

#### 25-01

##### Summary

The plan adds a permanent AST-based module-reachability guard, including scratch-tree tests for orphaned modules, lazy imports, typing-only imports and relative imports. It also inventories callable dispatch tables and checks the `helper_assets` exemption.

##### Strengths

- The seeded-orphan case makes the guard non-vacuous, while the entry-point check covers the two actual `python -m` launches in `Makefile:28–32` (`.planning/phases/25-lean/25-01-PLAN.md:105–121`).
- The dispatch inventory now includes `_PATH_QUERIES`, which is both defined and consulted by the ownership probe (`installer/install_ownership.py:213–218,236–240`; `.planning/phases/25-lean/25-01-PLAN.md:147–155`).

##### Concerns

- No new execution-blocking concern was established in the source checked.

##### Prior-review dispositions

- **R1-01 — resolved:** relative imports are resolved, and above-package imports fail by name (`.planning/phases/25-lean/25-01-PLAN.md:149,157`).
- **R1-02 — resolved:** `_PATH_QUERIES` is listed and the inventory test checks for omitted tables (`.planning/phases/25-lean/25-01-PLAN.md:80,150–155`).
- **R1-03 — resolved:** the exemption test checks both that the directory is live and that reachable modules do not import it (`.planning/phases/25-lean/25-01-PLAN.md:152`).
- **R2-01 — resolved:** the revised boundary is fewer than `level` package components, with both invalid and valid two-level examples (`.planning/phases/25-lean/25-01-PLAN.md:149,157`).

##### Suggestions

Keep the scratch cases and table-inventory test in the same commit as the visitor changes, as specified.

##### Risk Assessment

**LOW** for the reviewed contracts. The guard is new code, so its implementation and real-tree behavior still require execution-time verification.

#### 25-02

##### Summary

The plan retires the unused `host_setup` kind in one production commit, preserves native-package handoffs and the pnpm refusal, then adds compatibility pins and removes stale documentation.

##### Strengths

- It preserves the independent native-package handoff: `install_tool` returns `MANUAL_REQUIRED` from `needs_manual` before `_perform` (`installer/engine.py:267–278`; `.planning/phases/25-lean/25-02-PLAN.md:163–170`).
- The replacement smoke-key case is grounded in the loader’s closed parameters: `rpm_ostree` permits `package` but not `smoke_argv` (`installer/model.py:103–106`), while the existing assertion checks that exact unknown key (`tests/test_model.py:761–784`).
- The compatibility pin now reflects the actual cache representation: `VersionCacheEntry` has the four stated fields and no method fingerprint (`installer/version_cache.py:54–59`; `.planning/phases/25-lean/25-02-PLAN.md:202–209`).

##### Concerns

- No new execution-blocking concern was established in the source checked.

##### Prior-review dispositions

- **R1-04 — resolved:** the plan’s focused pytest commands no longer name the file created by parallel plan 25-01 (`.planning/phases/25-lean/25-02-PLAN.md:175–177,274–276`).
- **R1-05 — resolved:** the plan specifies the `rpm_ostree` replacement and preserves the existing assertion (`.planning/phases/25-lean/25-02-PLAN.md:133,179–182`; `installer/model.py:103–106`).
- **R1-06 — resolved:** the plan keeps `_PI_PACKAGE` and requires a pi-specific pnpm ownership pin (`.planning/phases/25-lean/25-02-PLAN.md:133,202–205`).
- **R2-03 — resolved:** the old pi cache entry is specified as loading unchanged, rather than as a fingerprint miss (`.planning/phases/25-lean/25-02-PLAN.md:203–204`; `installer/version_cache.py:54–59`).
- **R2-04 — resolved:** the plan records live ownership resolution and the absence of a persisted ownership-record format (`.planning/phases/25-lean/25-02-PLAN.md:208–209`; `installer/version_status.py:1664–1675`).

##### Suggestions

During execution, retain the full-suite check after the retirement commit: the sample `host_setup` method in `tests/test_engine.py:1144–1166` exercises a live manual-handoff assertion and must be switched in that same commit.

##### Risk Assessment

**MEDIUM.** The documented migration is broad, but the checked handoff and compatibility contracts are explicit. Correctness still depends on completing the test and caller inventory in the retirement commit.

#### 25-04

##### Summary

The plan triages the vulture-60 inventory, removes dead or test-only symbols in individually reversible commits, and moves the registry-integrity helper and its tests out of production.

##### Strengths

- The conditional cascade correctly protects `encode_manager_snapshot`: production still imports and calls it in `installer/version_status.py:123,1997–1999` (`.planning/phases/25-lean/25-04-PLAN.md:111–115`).
- The `release_tag` plan now accounts for both assignments. The first release lookup occurs in `resolve_target` (`installer/download.py:116–120`), and the second uses the memoized resolver (`installer/verify_registry.py:628–650`).
- The registry helper’s `_tool` dependency is explicitly included in the relocation commit (`tests/test_deps.py:15–27,153–163`; `.planning/phases/25-lean/25-04-PLAN.md:148`).

##### Concerns

- **HIGH — The helper-relocation instructions leave an import of the deleted production symbol.** Task 2 says to move `requires_integrity_errors` from `installer/deps.py` and change the import in `tests/test_registry.py` (`.planning/phases/25-lean/25-04-PLAN.md:148`), but `tests/test_deps.py` also imports it at lines 5–10. Moving its two callers at `tests/test_deps.py:153–163` does not remove that import. Following the enumerated edits leaves test collection failing with `ImportError` in the required same-commit gate.

##### Prior-review dispositions

- **R1-07 — resolved:** the plan copies `_tool` with the moved tests (`.planning/phases/25-lean/25-04-PLAN.md:148`; `tests/test_deps.py:15–27`).
- **R1-08 — resolved:** it removes both now-unused `tag` assignments and verifies the registry tests and ruff (`.planning/phases/25-lean/25-04-PLAN.md:115,123–125`; `installer/verify_registry.py:373–389`).
- **R1-09 — resolved:** framework-dispatched hooks and enum members have an explicit retained category (`.planning/phases/25-lean/25-04-PLAN.md:34–35,188–189`).
- The verified cycle-2 ledger records no additional finding for 25-04 (`.planning/phases/25-lean/25-REVIEWS.md:454–471`).

##### Suggestions

In Task 2 item 4, explicitly remove `requires_integrity_errors` from **both** `tests/test_deps.py` and `tests/test_registry.py` imports in the relocation commit. Keep the moved tests and assertions unchanged.

##### Risk Assessment

**HIGH.** The prescribed relocation is incomplete and can break collection before its required green commit.

#### Cross-Plan Assessment

**Overall lane risk: HIGH**, driven by the 25-04 relocation import. The declared wave-1 files for 25-01 and 25-02 are disjoint; the declared wave-2 files for 25-03 and 25-04 are also disjoint (`.planning/phases/25-lean/25-01-PLAN.md:5–8`, `.planning/phases/25-lean/25-02-PLAN.md:5–39`, `.planning/phases/25-lean/25-03-PLAN.md:5–24`, `.planning/phases/25-lean/25-04-PLAN.md:5–22`). The downstream composition plan places the home-constant move and sandbox generalization in the same commit (`.planning/phases/25-lean/25-05-PLAN.md:118,123–138`), and the Doctor move explicitly retains the generation-bearing message (`.planning/phases/25-lean/25-09-PLAN.md:98–100,114–131`).

**Review limit:** This was read-only; I did not execute the plans or test gates, and I did not exhaustively read every cited source and test file. The 25-04 import finding is grounded in the current source, not an execution result.

##### Status: Issues Found — fix and re-invoke

### Lane B (`laneB-my-referee-one`)

#### 25-03

##### Summary

The plan retires the sensitive-action prompts first, then removes callback threading, action parameters, and the registry field, followed by a documentation update. It preserves the checksum-mismatch prompt and the repair path.

##### Strengths

- The deletion is grounded in the empty prompt table: `SENSITIVE_PROMPTS` is `{}` in `installer/post_install.py:110-120`. The plan also explicitly rejects the retired registry key rather than relying on unknown-key handling (`.planning/phases/25-lean/25-03-PLAN.md:176-181`).
- The checksum prompt has independent worker-to-modal plumbing (`installer/execute_screen.py:837-847`), and Task 1 expressly retains it (`.planning/phases/25-lean/25-03-PLAN.md:139-143`).
- The plan preserves the live `repair=True` forwarding in `_with_force` (`installer/session.py:279-305`; `.planning/phases/25-lean/25-03-PLAN.md:178-181`).

##### Concerns

- No new execution-blocking concern found.

##### Prior-review dispositions

- **R1-10 — resolved.** The plan permits removal of the retired argument inside an assertion while preserving its expected value (`.planning/phases/25-lean/25-03-PLAN.md:116,124`).
- **R1-11 — resolved.** Mixed post-install tests are classified as STRIP, preserving live handoff assertions such as those in `tests/test_post_install.py:112-120,174-184`; the plan distinguishes them from confirmation-only tests (`.planning/phases/25-lean/25-03-PLAN.md:113-115`).
- **R1-12 — resolved.** Both action-table doubles are explicitly included in the arity migration (`.planning/phases/25-lean/25-03-PLAN.md:116,181`).
- **R1-13 — resolved.** Task 1 removes the orphaned prompt imports and corrects the checksum occurrence check (`.planning/phases/25-lean/25-03-PLAN.md:142,151`).
- **R1-14 — resolved/refuted.** The verified ledger found no requirement for a new negative documentation pin (`.planning/phases/25-lean/25-REVIEWS.md:48`).
- **R2-05 — resolved.** Task 1 now covers the later modal-helper users in `tests/test_execute_screen.py:5621-5657,5682-5707` (`.planning/phases/25-lean/25-03-PLAN.md:142-154`).
- **R2-06 — resolved/refuted.** The verified ledger treats removal of the retired argument as a deleted-target change (`.planning/phases/25-lean/25-REVIEWS.md:460`).
- **R2-08 — resolved.** The two model-test occurrences are assigned to separate classifications (`.planning/phases/25-lean/25-03-PLAN.md:115`).

##### Suggestions

- During execution, retain the plan’s per-test classification and before/after record for assertions containing the retired argument.

##### Risk Assessment

**LOW.** The migration has broad test fan-out, but the identified prompt, dispatch, repair, and documentation dependencies are assigned to the appropriate commits.

#### 25-05

##### Summary

The plan moves composition and import-time constants into `installer/compose.py`, extends the test sandbox, retargets patches and source scans, and adds structural and CLI-assertion guards. Two concrete dependencies remain unresolved in the intermediate helper-move commit.

##### Strengths

- The constant move and sandbox extension are required in the same commit (`.planning/phases/25-lean/25-05-PLAN.md:133-150`), addressing the import-time paths documented in `tests/conftest.py:261-283,301-323`.
- The schedule checkout correction preserves the existing repository-root calculation (`setup.py:697-707`; `.planning/phases/25-lean/25-05-PLAN.md:166-170`).
- The two source-inspection tests move with `_build_services`: `tests/test_versions.py:150-160` and `tests/test_setup.py:3540-3545` currently inspect `setup.py`; Task 2 retargets both (`.planning/phases/25-lean/25-05-PLAN.md:170`).

##### Concerns

- **HIGH — The fresh-process `_ENVIRONMENT_D_DIR` lookup loses its binding in Task 2.** The plan imports back only constants still read by setup’s production code and audits Python attribute reads and string-form *patch targets* (`.planning/phases/25-lean/25-05-PLAN.md:101,172-174`). At HEAD, the production reads of `_ENVIRONMENT_D_DIR` are in `_cache_redirect_policies` and `_desktop_shell_policies`, both moved in Task 2 (`setup.py:502-527,666-674`). But `tests/test_setup.py:1212-1230` launches a fresh interpreter with the string `import setup; print(setup._ENVIRONMENT_D_DIR)`. Once ruff removes the now-unused setup import-back, that subprocess raises `AttributeError`; the described AST audit does not inspect Python embedded in `-c` strings. Task 2 therefore cannot satisfy its full-suite green-commit gate as specified.

- **HIGH — Explicitly forwarding `repair=False` breaks an existing install double.** Task 2 replaces `_build_services._install`’s `**options` with explicit keyword parameters and forwards them by name (`.planning/phases/25-lean/25-05-PLAN.md:102,166`). Today `_with_force` deliberately omits `repair` for ordinary rows (`installer/session.py:279-305`), and `_build_services._install` forwards only the supplied options (`setup.py:641-654`). The existing `_recording_install` double has no `repair` parameter (`tests/test_setup.py:602-621`) and is used by the TUI route pilot (`tests/test_setup.py:624-660,2242-2261`). Unconditionally forwarding the default passes `repair=False` to that double, raising `TypeError` on ordinary installs. It also changes the existing omission contract for install seams.

##### Prior-review dispositions

- **R1-15 — resolved.** The moved schedule context is explicitly adjusted to the repository root (`.planning/phases/25-lean/25-05-PLAN.md:168`).
- **R1-16 — resolved.** Both source-scan changes land in Task 2 with the moved implementation (`.planning/phases/25-lean/25-05-PLAN.md:170`).
- **R1-17 — still open.** The revised audit covers ordinary module reads, but not the fresh-process string lookup described above: `tests/test_setup.py:1220-1230` reads a binding whose last production users move in Task 2 (`setup.py:502-527,666-674`).
- **R1-18 — resolved/refuted.** The verified ledger accepts the existing undo-then-reload sequence and the next-test sandbox (`.planning/phases/25-lean/25-REVIEWS.md:52`).
- **R1-19 — resolved.** The forbidden-import check is now AST-based rather than a prose grep (`.planning/phases/25-lean/25-05-PLAN.md:204`).
- **R1-20 — resolved.** The specified diff compares the baseline with the working tree (`.planning/phases/25-lean/25-05-PLAN.md:208`).
- **R1-34 — resolved.** The D-12 guard compares decorators as well as assertion segments (`.planning/phases/25-lean/25-05-PLAN.md:208`).
- **R2-09 — resolved/refuted.** The verified finding concerned Task 1’s bindings (`.planning/phases/25-lean/25-REVIEWS.md:462`); the new subprocess issue above occurs after Task 2 moves the remaining production readers.
- **R2-10 — resolved/refuted.** The verified ledger found the flag uses directly in the guarded test functions (`.planning/phases/25-lean/25-REVIEWS.md:463`).

##### Suggestions

1. In Task 2, retarget the fresh-process lookup to `installer.compose`, preserving the existing output assertion, and include embedded subprocess code in the patch/read audit.
2. Specify an `_install` implementation that preserves omission of `repair` when it was not supplied, while retaining strict typing and `repair=True` for forced rows. Run the existing TUI route pilot and the install-binding tests in that same commit.

##### Risk Assessment

**HIGH.** Both issues affect the required green intermediate commit; the install-wrapper change also alters a documented call contract.

#### 25-06

##### Summary

The plan introduces a bounded `RichLog` subclass, routes streaming and completion writes through one helper in the first commit, and displays Textual’s cumulative trimmed-line count above the log. A second commit adds multiline, empty-write, completion, and layout pins.

##### Strengths

- The callback runs from the `write` override, matching Textual’s deferred replay through `self.write` (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:132-139,205-213`; `.planning/phases/25-lean/25-06-PLAN.md:106-111`).
- Both streaming and completion writes are migrated in the commit enabling trimming (`installer/execute_screen.py:862-874,904-953`; `.planning/phases/25-lean/25-06-PLAN.md:111`).
- The plan tests rendered multiline eviction and the visible 80×20 layout, not just a count of write calls (`.planning/phases/25-lean/25-06-PLAN.md:138-146`).

##### Concerns

- **LOW — Deferred writes remain temporarily unbounded.** Before its first known size, Textual queues writes without applying `max_lines` (`.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py:205-213`). The plan acknowledges this and tests replay (`.planning/phases/25-lean/25-06-PLAN.md:102,219`). This is the previously accepted low-risk limitation, not a new blocker.
- **LOW — The implementation relies on Textual internals across dependency upgrades.** The project declares `textual>=8` without an upper bound (`pyproject.toml:6-10`), while the plan reads `_start_line` and relies on replay behavior (`.planning/phases/25-lean/25-06-PLAN.md:76,106-109`). The boundary and replay tests mitigate drift.

##### Prior-review dispositions

- **R1-21 — resolved.** The override observes replayed writes (`.planning/phases/25-lean/25-06-PLAN.md:102,109`).
- **R1-22 — resolved.** All current writers move with the bound (`.planning/phases/25-lean/25-06-PLAN.md:111`).
- **R1-23 — resolved, corrected by R2-11.** The plan now states and tests the bound for empty string writes too (`.planning/phases/25-lean/25-06-PLAN.md:28,140`).
- **R1-24 — resolved.** The completion and post-drop layout paths have explicit tests (`.planning/phases/25-lean/25-06-PLAN.md:141-142`).
- **R2-11 — resolved/refuted as a blocker.** The corrected empty-string behavior and regression test are specified (`.planning/phases/25-lean/25-06-PLAN.md:140,146`).
- **R2-12 — still open, accepted LOW.** The pre-size queue remains unbounded as described above.
- **R2-13 — still open, accepted LOW.** The dependency range remains open-ended as described above.

##### Suggestions

- Keep the replay and empty-string tests in the permanent suite so a Textual upgrade exposes a changed internal contract.

##### Risk Assessment

**LOW.** The planned mechanism addresses the prior notice and ordering failures; remaining risks are the documented transient queue and dependency-internal coupling.

#### Cross-Plan Assessment

**Overall lane risk: HIGH.** Plan 25-05 has two Task 2 green-commit blockers. Plans 25-05 and 25-06 declare disjoint modified files (`.planning/phases/25-lean/25-05-PLAN.md:7-21`; `.planning/phases/25-lean/25-06-PLAN.md:7-9`), and both follow 25-03 in the wave order (`.planning/ROADMAP.md:737-743`). The size-cap work remains assigned to the later split plans, whose projections identify the oversized modules (`.planning/phases/25-lean/25-RESEARCH.md:329-348`). The existing silence-generation check remains outside these lane changes (`installer/execute_screen.py:743-757`).

**Review status: Issues found — revise 25-05.**

**Not checked:** I did not execute the planned refactor or its test gates; the new modules and scratch guards do not yet exist. No matching codebase-memory index was available, so findings rely on source inspection and text searches.

### Lane C (`laneC-my-referee-one`)

#### 25-07

##### Summary

The plan moves the mutation lock and modal screens first, places the two shared schedule names in `ui_common.py`, and introduces the AST move checker reused by the next two plans. The ordering gives later screens stable dependencies without a runtime import back into `wizard_app.py`.

##### Strengths

- The shared-name move addresses real dependencies: `SchedulesScreen` and the modal screens both use `_TIMES_LISTED` and `_sentence` (`installer/wizard_app.py:2642,2656,2953,3139,3416,3514`; `.planning/phases/25-lean/25-07-PLAN.md:133-139`).
- The mutation-lock move retains the cross-process refusal and release logic (`installer/wizard_app.py:3632-3668`; `.planning/phases/25-lean/25-07-PLAN.md:98-120`).
- Both tasks require the pilot tests and full gates before their respective commits (`.planning/phases/25-lean/25-07-PLAN.md:111-120,136-146`).

##### Concerns

- No execution-blocking concern confirmed.

##### Prior-review dispositions

- **R1-25: resolved.** The checker specification includes assignment bindings and detects old renamed references in source and targets; the plan also requires lint and strict typing checks (`.planning/phases/25-lean/25-07-PLAN.md:107`).
- **R2-15: resolved for the verified finding.** The checker must detect a copy newly defined in a target while retained in the source, fail on zero checked names, and run against the pre-commit revision (`.planning/phases/25-lean/25-07-PLAN.md:107,111-113`).

##### Suggestions

- In the task summaries, record the checker’s nonzero comparison count and the revision used, alongside the pilot and full-gate results.

##### Risk Assessment

**LOW.** The named dependencies and intermediate gates are consistent with the current source. The checker is a planned tool, however, so its implementation and self-check remain to be verified during execution.

#### 25-08

##### Summary

The plan moves Policies and Schedules in sequence, first relocating their shared formatting helper and probe aliases, then moving Schedules and retargeting its module-global test accesses.

##### Strengths

- The plan explicitly updates the Schedules calls to `_fit` in the same commit that moves the helper (`installer/wizard_app.py:2850-2856`; `.planning/phases/25-lean/25-08-PLAN.md:116-120`).
- It addresses both schedule-test global accesses: the silent dictionary-based refresh patch and the columns lookup (`tests/test_schedules_view.py:593-596,673`; `.planning/phases/25-lean/25-08-PLAN.md:141-147`).
- It distinguishes the app-level `move_link_mode` patch from the moved Policies call, avoiding an indiscriminate retarget (`tests/test_screen_family.py:2951`; `installer/wizard_app.py:2551,4216`; `.planning/phases/25-lean/25-08-PLAN.md:94`).

##### Concerns

- No execution-blocking concern confirmed.

##### Prior-review dispositions

- **R1-26: resolved.** Task 1 explicitly replaces the remaining Schedules `_fit` calls with `fit` in the same commit (`.planning/phases/25-lean/25-08-PLAN.md:117`).
- **R2-16: resolved for the verified finding.** Both tasks use the revised checker and specify the nonzero-count, retained-copy and revision-timing failure conditions (`.planning/phases/25-lean/25-08-PLAN.md:119-121,144-146`; `.planning/phases/25-lean/25-07-PLAN.md:107`).

##### Suggestions

- Preserve the distinction between the loud `_REFRESH_SECONDS` patch and the existing `vars(...)` lookup for `_SCHEDULE_COLUMNS`, as specified, and verify both in the same commit as the screen move.

##### Risk Assessment

**LOW.** The identified test-patching hazards have explicit same-commit fixes, and the plan follows the prerequisite modal move. Actual new-module bindings still require execution-time validation.

#### 25-09

##### Summary

The plan moves Doctor and Uninstall last, each with a sibling module. It moves Doctor’s worker messages together with their screen, and moves the destructive Uninstall screen together with its review helpers and importers. The final size cap is deliberately delegated to plan 25-10.

##### Strengths

- The generation-bearing message and its handler move together. The current handler rejects stale audit results before applying them (`installer/wizard_app.py:274-287,947-964`; `.planning/phases/25-lean/25-09-PLAN.md:113-126`).
- The Uninstall screen, review helpers and relevant end-to-end tests are included in one task (`.planning/phases/25-lean/25-09-PLAN.md:138-153`).
- The removal-quit strings correctly remain with the app rather than moving with the adjacent review constants (`installer/wizard_app.py:1090-1091`; `.planning/phases/25-lean/25-09-PLAN.md:146-147`).

##### Concerns

- No execution-blocking concern confirmed.

##### Prior-review dispositions

- **R1-27: resolved by the recorded refutation.** The screen and renamed review globals move in the same task, with the rename map applied to the moved nodes (`.planning/phases/25-lean/25-09-PLAN.md:146-150`; `.planning/phases/25-lean/25-REVIEWS.md:59-61`).
- **R2-17: resolved for the verified finding.** The shared checker’s retained-copy rule includes assignment bindings, so the specified retained `_DOCTOR_READ_ERROR` copy is covered (`installer/wizard_app.py:341`; `.planning/phases/25-lean/25-07-PLAN.md:107`; `.planning/phases/25-lean/25-09-PLAN.md:120-125`).

##### Suggestions

- Record the actual post-move module sizes for plan 25-10; do not report the 800-line acceptance as complete at the end of this plan (`.planning/phases/25-lean/25-09-PLAN.md:80-83`; `.planning/phases/25-lean/25-10-PLAN.md:134-155`).

##### Risk Assessment

**LOW for the specified move; phase completion remains dependent on plan 25-10.** The race check and destructive-path coverage are explicitly retained, while the size guard lands in the following wave.

#### Cross-Plan Assessment

**Overall lane risk: LOW**, with no confirmed execution blocker in these three plans. Their shared-file edits are sequential rather than parallel: 25-07, 25-08 and 25-09 occupy waves 4, 5 and 6 respectively (`.planning/ROADMAP.md:745-752`). Plan 25-10 owns the subsequent cleanup, extraction and permanent size guard (`.planning/ROADMAP.md:754-755`).

This was a read-only review: the refactor, checker and test gates were not executed. The future split modules do not yet exist at HEAD, and the source/test review was targeted rather than exhaustive; no matching codebase-memory index was available.

### Lane D (`laneD-my-referee-one`)

#### 25-10

##### Summary

Plan 25-10 finishes the screen split in three commits: it removes review-history prose without changing code, extracts eligible Uninstall helpers until the split modules meet the 800-line cap, and adds permanent size, review-ID and runtime-import guards.

##### Strengths

- The cleanup follows the verbatim moves and uses an AST comparison before its commit, matching the ordering requirement (`.planning/phases/25-lean/25-10-PLAN.md:103-131`; `.planning/phases/25-lean/25-SPEC.md:129-131`).
- The extraction contract excludes the two known stateful candidates: `_tool_entry` writes `_painted`, and `_with_failure` deletes an entry from `_failed_lines` (`.planning/phases/25-lean/25-10-PLAN.md:141-145`; `installer/wizard_app.py:1303-1305,1323-1337`).
- The revised plan preserves `_config_lines` at its existing post-removal call site; it currently checks the filesystem when the result is rendered (`.planning/phases/25-lean/25-10-PLAN.md:143`; `installer/wizard_app.py:1853-1863,2005`).

##### Concerns

- No new execution-blocking concern was established from the plan and the current source. Final sizes remain projections until the preceding moves and cleanup are performed (`.planning/phases/25-lean/25-10-PLAN.md:84-86`; `.planning/phases/25-lean/25-RESEARCH.md:329-348`).

##### Prior finding dispositions

- **R1-28 — resolved.** Cleanup and a permanent guard now cover the moved nodes and their attached comments in shared modules (`.planning/phases/25-lean/25-10-PLAN.md:103-120,171-174`; original `WR-10` comment at `installer/wizard_app.py:178-182`).
- **R1-29 — resolved.** Stateful methods stay on the class and only the specified eligible helpers can move (`.planning/phases/25-lean/25-10-PLAN.md:85-86,141-143`).
- **R1-30 — resolved.** The fallback explicitly imports all three messages into `wizard_app.py`, where their constructors and handler annotations are used (`.planning/phases/25-lean/25-10-PLAN.md:87,145`; `installer/wizard_app.py:3925-3945,4042-4044`).
- **R2-18 — resolved.** The disk-reading helper remains at its current call site and cannot be cached or hoisted (`.planning/phases/25-lean/25-10-PLAN.md:143`; `installer/wizard_app.py:1853-1863,2005`).

##### Suggestions

- Record actual post-cleanup and post-extraction line counts in the summary, as the plan requires, rather than relying on the projections (`.planning/phases/25-lean/25-10-PLAN.md:146`).

##### Risk Assessment

**LOW.** The identified stateful-extraction and moved-comment issues are addressed. The remaining uncertainty is the unexecuted split and its measured final sizes.

#### 25-11

##### Summary

Plan 25-11 runs the phase-wide guards and local gates, compares production lines with the pre-phase commit, and reports kept and deleted targets. Its production-scope vulture comparison fixes the cycle-2 scope error, but the final deleted-target grep has two concrete false positives that prevent its stated acceptance criterion from passing.

##### Strengths

- The line-count report uses `installer/` and `setup.py`, excludes tests, and records both revisions (`.planning/phases/25-lean/25-11-PLAN.md:19-20,126-128`; `.planning/phases/25-lean/25-SPEC.md:133-135`).
- The race check is retained explicitly; the current Doctor handler rejects a stale generation before applying its report (`.planning/phases/25-lean/25-11-PLAN.md:41-43,105-106`; `installer/wizard_app.py:950-964`).
- Both vulture scans now include `setup.py` and `installer/`, so the comparison includes setup-side callers on both sides (`.planning/phases/25-lean/25-11-PLAN.md:25,98`; `pyproject.toml:62-64`).

##### Concerns

- **HIGH — The final absence grep matches live, unrelated identifiers.** The required command treats each alternative as an arbitrary substring and must print zero (`.planning/phases/25-lean/25-11-PLAN.md:112`). Deleting `shellrc.classify_source_line` still leaves the live `_classify_source_lines` function and its callers (`installer/shellrc.py:703-708,793-797`), which contain `classify_source_line` as a substring. Likewise, deleting the `PermissionMode` alias leaves the real Copilot configuration key `"defaultPermissionMode"` (`installer/agent_settings.py:692`). The earlier triage correctly calls for retaining `_SourceInspection` and the live inspector (`.planning/phases/25-lean/25-04-PLAN.md:137-147`). Consequently, a correct implementation cannot meet this final zero-match criterion without incorrectly changing live code or weakening the stated check.

##### Prior finding dispositions

- **R1-31 — resolved/refuted in the verified ledger.** The plan retains the requirement to record CI results for the pushed phase head; the workflow has Ubuntu and macOS jobs (`.planning/phases/25-lean/25-11-PLAN.md:19,29`; `.github/workflows/ci.yml:3-6,13-21`).
- **R1-32 — resolved as specified.** The revised guard pairs suppression-bearing lines one-for-one rather than comparing aggregate totals, with the stated retarget normalization (`.planning/phases/25-lean/25-11-PLAN.md:49,98`).
- **R1-33 — resolved for the recorded finding.** The vulture comparison uses multiset counts of `(kind, name)`, so an additional occurrence of an existing name increases the count (`.planning/phases/25-lean/25-11-PLAN.md:25,98`).
- **R1-34 — resolved.** The D-12 guard also compares decorator source, covering the parameterized expected values at `tests/test_setup.py:1597-1603` (`.planning/phases/25-lean/25-05-PLAN.md:208`; `.planning/phases/25-lean/25-11-PLAN.md:75,101-102`).
- **R1-35 — resolved/refuted in the verified ledger.** The phase deletes `installer/host_setup.py`, so an empty production diff would indicate a wrong baseline for this planned phase (`.planning/phases/25-lean/25-11-PLAN.md:190-192`; `.planning/phases/25-lean/25-CONTEXT.md:134-135`).
- **R2-19 — resolved.** Both baseline and final vulture commands scan the same production scope, including `setup.py` (`.planning/phases/25-lean/25-11-PLAN.md:25,98`).
- **R2-20 — resolved under the verified ledger’s accepted disposition.** The plan retains the explicitly documented normalization without further change (`.planning/phases/25-lean/25-11-PLAN.md:76,203-204`; `.planning/phases/25-lean/25-REVIEWS.md:470-472`).

##### Suggestions

- Replace the substring-only absence check with identifier-aware checks: for example, use word boundaries for symbol names and separate exact checks for the retired hyphenated kind. Preserve checks for the actual deleted definitions, imports and dispatch keys while allowing `_classify_source_lines` and `"defaultPermissionMode"`.

##### Risk Assessment

**HIGH.** The final phase gate cannot satisfy its prescribed zero-match acceptance on the intended behavior-preserving tree.

#### Cross-Plan Assessment

**Overall lane risk: HIGH**, driven by 25-11’s false-positive final gate. Plans 25-10 and 25-11 are sequential, following the split in 25-09, so their shared files do not create a same-wave conflict (`.planning/ROADMAP.md:751-758`).

The review was read-only. A baseline vulture scan was run; the phase implementation, full test suite and CI were not run. The later-wave split modules and scratch guards do not yet exist at HEAD, so their eventual implementations and final sizes could not be verified.

