---
phase: 20
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-17T22:25:00Z
cycle: 2
plans_reviewed: [20-01-PLAN.md, 20-02-PLAN.md, 20-03-PLAN.md, 20-04-PLAN.md, 20-05-PLAN.md, 20-06-PLAN.md, 20-07-PLAN.md, 20-08-PLAN.md, 20-09-PLAN.md, 20-10-PLAN.md, 20-11-PLAN.md, 20-12-PLAN.md, 20-13-PLAN.md, 20-14-PLAN.md, 20-15-PLAN.md, 20-16-PLAN.md, 20-17-PLAN.md, 20-18-PLAN.md, 20-19-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 20

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## Cycle 2 (current) — reviewed at HEAD 74a893b



**Method note.** HEAD is `74a893b` ("docs(20): incorporate cycle-1 cross-AI review"), which touched **only** `.planning/` files (11 plans + `20-UI-SPEC.md`, 2 lines) — verified via `git show --stat` and an empty `git diff --stat bb0b71f..HEAD` over `installer/ tests/ scripts/ .claude/`. Cycle-1's source verification at `bb0b71f` therefore still describes the tree, and I re-verified ~50 anchors directly this session (deps.py, session.py, render.py in full; update.py, catalog_tui.py, version_status.py, wizard_app.py, app.py, execute_screen.py, setup.py, pnpm_globals.py, engine.py, skill_lifecycle.py, model.py, ownership.py, receipts.py, prompt/selection/audit/status, the e2e script, state_doubles, conftest, the Textual 8.2.7 API surface, and every pinned test location). Every claim below is source-grounded; plan citations are `file:line` on disk.

**Reviewer note on method:** Every claim below was verified against the working tree at `HEAD` (`74a893b`). I read the cited files and traced the cited mechanisms; line references were re-checked rather than trusted. The research document's "State of the Art" table proved accurate — of ~60 line references checked, essentially all matched the tree (deviations are noted where found). No finding below relies on plan text alone.

---

### Cycle-1 Resolution Check

Judge: current plan text (not ledger claims), against the tree.

| Cycle-1 finding | Status | Evidence |
|---|---|---|
| 20-06/20-09 false-failing word-literal gates (MEDIUM) | **FULLY RESOLVED** | Both gates are now no-growth-against-`HEAD` (`20-06-PLAN.md:123`, `20-09-PLAN.md:133`) — satisfiable: today's inventory is exactly 2 review/done literals (`render.py:57`, `:78`) and 4 result literals (`:80-82`, `:95`), and the new renderers add none. File-wide zero gates moved to `20-14-PLAN.md:137`. (One residual defect in the *moved* gate: see 20-14 below.) |
| 20-03 second `node_install_policy` object (MEDIUM) | **FULLY RESOLVED** | `20-03-PLAN.md:22,56,84-85` — `_build_services` returns `(refresh, updates, policy)`; `node_install_policy(tools)` called exactly once (gate `:98`). The invariant at `setup.py:1060-1062` ("Preview and reinstall must receive the SAME policy object") is real and now holds by construction. `NodeInstallPolicy` exists (`pnpm_globals.py:113`). |
| 20-10 stale Task-1 acceptance bullet (MEDIUM) | **PARTIALLY RESOLVED** | The `make validate` half is fixed (`20-10-PLAN.md:112` "Tasks 1 and 2 land in ONE commit… runs once, on the combined tree"). But the revision *added* a new false claim at `:167` ("`uv run pytest tests/test_execute_screen.py … exit 0` after this task alone") — see new MEDIUM under 20-10. |
| Pending-row copy `… {id}` vs `…  {id}` (LOW-MEDIUM) | **FULLY RESOLVED** | `20-UI-SPEC.md:399` was actually edited in `74a893b` (`…  {id}` → `… {id}` — verified via `git show`). Anatomy (`:101-103`) is canonical; 20-10's must_haves/`test_checking_rows…` and `20-12-PLAN.md:100` expect `… rg  checking…`. Consistent everywhere now. |
| 20-18 `depends_on` missing 20-12/20-13 (MEDIUM metadata) | **FULLY RESOLVED** | `20-18-PLAN.md:6` `depends_on: ["20-10", "20-12", "20-13"]`, wave 9 (> 8, the highest dependency wave); ledger `:144`. |
| Fixture gaps (LOW): `VersionStatus.tool_id`, `plan_state` receipt/method, second fake prompter | **FULLY RESOLVED** | `20-04-PLAN.md:110` — `VersionStatus(tool_id=tool.id, …)`, `method: Method \| None = None` forwarded into `ManagerOwnership`, receipt kwarg dropped with rationale (verified `pass_state` at `tests/state_doubles.py:200-232` has no receipt kwarg). `20-05-PLAN.md:140` — `tool_id="jq"`, `method=tool.methods[0]`. `RecordingPrompter` named in `20-11-PLAN.md:119` and `20-15-PLAN.md` Task 2 (verified it exists at `tests/test_app.py:1306`). |
| 20-01 LOW: `def visit(` = 0 gate vs the nested-visit refactor | **UNRESOLVED** (still-open LOW) | `20-01-PLAN.md` Task 1 acceptance still requires `grep -c "def visit(" … is 0` while the context decision still says "the SAME nested `visit` function, refactored into a local `topo`" — the natural implementation keeps `def visit(` inside `topo` (`deps.py:121` today). |
| 20-01 LOW: `blocked_needs` "unsatisfiable" mapping implicit | **FULLY RESOLVED** | Task 2 action now states `blocked_needs[tool.id] = None if unsatisfiable else needs`; the behavior test pins `Blocked("z", needs=None, …)`. The two disjoint blocking causes at `deps.py:92-95,102-107` match. |
| 20-02 LOW: don't move `executors.execute(method, runner)` out of `_perform` | **FULLY RESOLVED** | Context: "_perform's pnpm branch keeps only `executors.execute(method, runner)`"; guard-removal comment planned; `pnpm_add_command` import at `update.py:86` stays. |
| 20-05 LOW: UNAVAILABLE race in the exhaustive `else` | **DEFERRED-WITH-RATIONALE** | `20-05-PLAN.md` ledger Deferred: the window (`version_status.py:1537` per-pass platform re-read vs older-published state) is closed by construction on the runnable paths (20-12 rebuilds from the latest publication before any run; 20-11 runs one synchronous pass then plans); worst case is a momentarily mislabeled SKIP row, never a mutation. Phase 21's owner removes the platform re-read. Rationale is sound for this phase. |
| 20-05 LOW: `catalog[r.tool_id]` on a `Sequence[Tool]` | **FULLY RESOLVED** | Task 1 action: `by_id = {t.id: t for t in catalog}` built once in `build_plan`. |
| 20-07 LOW: A7 (update failures don't propagate) | RESOLVED (no change needed) | Already pinned by Task 2's `test_update_failure_does_not_block_a_dependent`; consistent with D-03. |
| 20-07 LOW: `_with_force`/`_with_repair` coexistence | RESOLVED (accepted as designed) | Explicitly scheduled: 20-10 deletes the screen's copy. |
| 20-08 LOW: `perform_action`'s `ValueError` → row `crashed` | **UNRESOLVED** (still-open LOW, optional) | Verified `raise ValueError` at `skill_lifecycle.py:678`; the per-step catch list still `CommandError`/`OSError`. Fail-closed (exit 1), unreachable for `partial_steps` steps. |
| 20-10 LOW: review/headless must not share a cached `Text` | RESOLVED (no change needed) | Ledger documents it; the plan already keeps them separate (`_fold_width()` vs `render_plan`). |
| 20-11 LOW: refresh-failure branch ordering underspecified | **FULLY RESOLVED** | `20-11-PLAN.md:82` spells out pass → `build_plan` regardless → `State check failed: {detail}` → one `not_attempted` per row → `render_run_summary` → return. |
| 20-11 LOW: FakePrompter keeps `select_*` until 20-15 | RESOLVED (no change needed) | Coordinated same-commit trim with 20-15. |
| 20-11/20-19 same-wave coupling stated in 20-11 too | **FULLY RESOLVED** | `20-11-PLAN.md:91` ("in wave 7 beside 20-19… leaves `make e2e` parsing an `Installed: …` line that no longer prints"). Files disjoint (app/setup/test_app/test_setup vs the script). |
| 20-13 LOW: layout pilots may need iteration | RESOLVED (advisory only) | UI-SPEC measured baseline provides starting numbers; `Pilot.resize_terminal` verified at `.venv/.../textual/pilot.py:86`. |
| 20-16 LOW: Task-2 gate filters `deleted\|Phase 20` | **UNRESOLVED** (still-open LOW) | Gate unchanged; the rewrite instruction still doesn't mandate the word "deleted", so a transition sentence without it false-fails. |
| 20-19 LOW: `ACC_SKIPPED_FILE` vs counter `ACC_SKIPPED` overloading | **UNRESOLVED** (still-open LOW) | `scripts/container-e2e-verify.sh:382` still names the dependency-failed *lines* file `ACC_SKIPPED_FILE`; the plan renames `ACC_ALREADY` → counter `ACC_SKIPPED` without renaming the lines file. |
| 20-19 LOW: GNU sed `\b` | RESOLVED (accepted) | Linux-only by design (Fedora/Debian/Arch containers). |

**Revision-induced defects check:** wave topology re-verified from frontmatter — every `depends_on` edge points to a strictly earlier wave, same-wave plans are file-disjoint (W1: deps / update+catalog_tui / setup; W5: session / render / execute_screen+setup; W7: app+setup / execute_screen / script; W8: execute_screen+version_status / session+render+engine; W9: audit+selection+prompt / execute_screen; W10: docs). Cross-plan vocabulary stays coherent (`summary_counts` fixed order identical in 20-07, 20-09, and 20-19's parse categories; 20-03's 3-tuple ↔ 20-11's `refresh, updates, _` at `20-11-PLAN.md:85,226`). Three new defects found — all in gate/commit sequencing, none in design: see 20-10 and 20-14.

---

### 20-01

**Summary.** Adds defaulted `closure`/`blocked`/`requested_by` to `Resolution` while keeping `order`/`dragged_in`/`warnings` byte-identical — still the correct unblocking prerequisite for `build_plan`.

**Strengths.**
- The gap is real and verified: `deps.py:111-113` drops `satisfied_by_install` from `order`, so present tools have no position today; one shared `topo` avoids a second sort.
- `dragged_in` staying `()` for present deps holds by construction (`deps.py:137` derives it from `ordered`).
- Task 2's `blocked_needs` mapping is now explicit and pinned (`Blocked("z", needs=None, …)`; the two warning texts at `deps.py:105,107` are kept verbatim and become `Blocked.reason`).
- `Mapping` already imported (`deps.py:12`); `field` correctly flagged as missing (`deps.py:13` imports only `dataclass`).

**Concerns.**
- **LOW (still-open, cycle-1 carryover)** — the Task-1 acceptance gate `grep -c "def visit(" installer/deps.py` is 0 collides with the context's own wording ("the SAME nested `visit` function, refactored into a local `topo`"): the natural `topo` body keeps a nested `def visit(` (as `deps.py:121` does today). One head-scratch at gate time.

**Suggestions.** Rename the inner DFS (e.g. `_place`) in the same edit, or drop that grep clause.

**Risk Assessment.** LOW — additive change to a 184-line module, 23 pinned tests untouched (count verified: 23).

### 20-02

**Summary.** Extracts `_perform`'s pre-flight refusals into one `update_refusal` shared with `build_plan`, and removes the migration promise from the two strings.

**Strengths.**
- Gates are satisfiable against the tree exactly as claimed: `status="unknown-owner"` occurs 2× today (`update.py:251`, `:502`), `status="unsupported"` 5× (`:259`, `:280`, `:288`, `:330`, `:520`) — the move keeps both counts.
- Both reworded strings exist as described: the two-line f-string at `update.py:307-311` and the two-line status piece at `catalog_tui.py:821-825`; the replacements match the UI-SPEC Copywriting rows (`20-UI-SPEC.md:374-375`) verbatim.
- The existing pins port cleanly: `tests/test_update.py:1130-1137` asserts the exact old detail (checked); `tests/test_catalog_tui.py:2597-2604` and `:2693-2700` assert the old `u` line (checked).
- `_perform`'s pnpm branch keeping `executors.execute(method, runner)` is correct — with `update_refusal` returning first on `method is None`, the guard is genuinely impossible there.

**Concerns.** None new or still-open.

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-03

**Summary.** Extracts `_build_services(tools, platform)` for both routes; the cycle-1 policy split is fixed by returning the one policy object.

**Strengths.**
- The invariant comment is real and now honored by construction: `setup.py:1060-1062` ("Preview and reinstall must receive the SAME policy object…") verified on disk; the plan moves the construction (with the comment) into `_build_services` and returns it (`20-03-PLAN.md:84-85`), gate `node_install_policy(tools)` count = 1 (`:98`).
- `NodeInstallPolicy` is a public name (`pnpm_globals.py:113`), so the `isinstance` test and the return annotation compile.
- The extraction is clean: `VersionRefreshService(` at `setup.py:897` (hoisted above `uninstall_inputs`), `UpdateService(` at `:1121`, each constructed exactly once today; `_which_with_brew` is module-level (`:692`); `terminal_sync=_sync_omz_terminals` already appears 3× (`:983`, `:1009`, `:1195`), so 20-17's "at least 2" gate is safe.

**Concerns.** None new.

**Suggestions.** `test_build_services_binds_the_update_service_to_the_refresh_service` observes the epoch move via `refresh.state_of(any_id) is None` — that only distinguishes before/after if a state was published first; have the test publish one state (or call `refresh([])`) before `invalidate`.

**Risk Assessment.** LOW.

### 20-04

**Summary.** The plan model: `Disposition`, `PlanRow`, `WORDS`/`RESULT_WORDS`, pure `build_plan` for WAIT/MISSING/OK/reinstall/dragged/blocked rows.

**Strengths.**
- Fixture fixes land correctly: `VersionStatus(tool_id=tool.id, …)` (the first, non-defaulted field — verified), `method: Method | None` passthrough into `ManagerOwnership`, and the honest receipt story — `pass_state` (`tests/state_doubles.py:200-232`) has no receipt kwarg, so `receipt=None` always, which is exactly what L-20-06 needs.
- Purity is testable via the established `GuardedPopen` autouse (`tests/conftest.py:~108` patches `subprocess.Popen`).
- Reason texts match the UI-SPEC Disposition-copy rows verbatim; `select_tools(tools, ids)` exists (`installer/selection.py:82`).

**Concerns.** None new or still-open.

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-05

**Summary.** Completes the disposition table (BROKEN incl. drift, MISCONFIGURED, OUTDATED × owner), plan-time blocked-dependent post-pass, G cases A–I on three tiers.

**Strengths.**
- The post-pass is necessary and correctly scoped: `is_blocked` (`deps.py:81-100`) blocks only on unavailability, so a broken-but-available dnf-owned dependency does not resolver-block its dependent — the plan closes exactly that hole, with chain propagation in plan order.
- Zero-sudo grounding verified: `UNMANAGEABLE_OWNERS = frozenset({*NATIVE_OWNERS, OS_PACKAGE_OWNER})` (`ownership.py:119-125`); `CHANGED_SINCE_INSTALL` (`receipts.py:44`); `BROKEN_SHIM_REASON`'s first clause is `shim present, package missing` as the test expects (`version_status.py:596-598`).
- The pnpm leg is now buildable: `plan_state(method=tool.methods[0])` through 20-04's passthrough (`20-05-PLAN.md:140`).
- The one deferral (UNAVAILABLE-in-exhaustive-else race) is documented with a rationale that holds for this phase's runnable paths.

**Concerns.** None new (the deferred item is recorded above in the resolution table).

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-06

**Summary.** The one renderer (`render_plan`) with grouping, folding, sanitization, plus moving the glyph table to `HEALTH_MARKS`.

**Strengths.**
- The revised no-growth gate is now satisfiable by inventory: exactly 2 quoted review/done literals in `render.py` today (`:57`, `:78` — both inside functions 20-14 deletes), and the new renderers read `WORDS`/`HEALTH_MARKS` only.
- The glyph move is safe: `_HEALTH_CELL` has exactly seven entries at `catalog_tui.py:249-258`, `health_cell` (`:127-130`) is the only in-module consumer, and `render.py` imports nothing from `catalog_tui` today (verified).
- The anatomy and Words table match `20-UI-SPEC.md:101-120,143-152` exactly; width math checks (24-char id + 41-char longest phrase fits in 78).

**Concerns.** None new or still-open.

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-07

**Summary.** The one engine: `RowOutcome`, `RunContext`, `execute_plan`, and the four pure views.

**Strengths.**
- `UpdateService`'s public surface matches the `UpdateRunner` protocol exactly (`begin` at `update.py:485`, `run` at `:496`, `in_flight`/`end` as described).
- Exit-code parity is preserved by construction: today `Summary.has_failure` excludes `manual_required`/`no_method` (`session.py:119-134`); mapping them to `manual`/`blocked` (both outside `_FAILURE`) keeps every `--all --yes` exit unchanged.
- The crash policy is a strict improvement over `run_installs` (`session.py:212-213` drops rows after a cancel; `execute_plan` guarantees one outcome per row).

**Concerns.** None new or still-open (A7 and the two-wave `_with_repair` coexistence were advisory/accepted in cycle 1).

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-08

**Summary.** Executes the typed `ConfigStep`s: one dispatcher by kind, the portable cwd wrapper, pnpm group via the node executor, skill handoff → `manual`.

**Strengths.**
- `ConfigStepKind` is exactly the 8 members (`model.py:311-320`) and `ConfigStep` carries `text/kind/harness/argv/cwd` (`:322-332`); the `argv`-less kinds are all real producers (`partial_steps` at `skill_lifecycle.py:972`).
- `perform_action`'s statuses match the mapping; `LifecycleStatus` (`skill_lifecycle.py:27`) is exactly `completed | manual-required | present | absent | unknown`.
- Stop-at-first-failure preserves 19 D-18's enable-before-remove ordering.

**Concerns.**
- **LOW (carried)** — `perform_action` raises `ValueError` when a lifecycle has no executable operation (`skill_lifecycle.py:678` — verified); the per-step catch list is `CommandError`/`OSError`, so that path surfaces as row `crashed` (exit 1). Unreachable for `partial_steps`-produced steps; optional to name in the plan.

**Suggestions.** One line naming the `ValueError` → `crashed` (fail-closed) outcome would pin it.

**Risk Assessment.** LOW.

### 20-09

**Summary.** The finished-side renderer: `Summary — {counts}` head plus `outcome_row_text`/`running_row_text`.

**Strengths.**
- The revised no-growth gate is satisfiable: today's inventory is 4 quoted result literals (`render.py:80-82` in `render_summary`, plus `:95` in a kept docstring — counted, not grown by the new renderers).
- The Outcome-copy texts match `20-UI-SPEC.md:219-229` verbatim (checked row by row); `render_failure_details` and friends are kept per the UI-SPEC's explicit "only `render_summary` is replaced".

**Concerns.** None new (the residual belongs to 20-14's moved zero gate, raised there).

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-10

**Summary.** Moves the TUI review/worker/finished panel/retained selection/exit code onto the plan and deletes the screen's copies, porting the three largest test files.

**Strengths.**
- The one-commit design is now stated correctly for `make validate` (`20-10-PLAN.md:112`), and `InstallRunFinished`'s current shape (first field `summary: Summary`, plus `not_attempted`/`update_*` — `execute_screen.py:353-388`) matches the reshape description exactly.
- All mechanisms verified present: `replace_option_prompt` at `.venv/.../textual/widgets/_option_list.py:647`; `_staged` shared at `wizard_app.py:2517`/`:2578`; `_install_closed` clears unconditionally at `:2898-2899`; `on_tool_updated`/`_merge_summary` at `:3023`/`:3047` (latest-wins replaces them cleanly); the four other `_session_exit_code` callers at `setup.py:1339,1377,1403,1495`.
- Port scale is accurate: 114 tests/4705 lines, 97 `ExecuteScreen(`, 60 `installed=`, 3 `summarize` refs, 1 `#execute-progress` test ref (all counted this session).

**Concerns.**
- **MEDIUM (new)** — the revision's intermediate claim at `:167` ("`uv run pytest tests/test_execute_screen.py … exit 0` **after this task alone**") is false. The screen tests host on the real app: `_host(inputs) -> UnifiedApp` (`tests/test_execute_screen.py:259-261`). `InstallRunFinished` has no `message.stop()`/`no_bubble` anywhere in `execute_screen.py` (grep-verified), and `UnifiedApp.on_install_run_finished` (`wizard_app.py:2977`) reads `message.summary`, `message.not_attempted`, `message.update_outcomes`, `message.update_errors`, `message.error` — exactly the fields Task 1 removes, while `wizard_app.py` is Task 2's file. Every run-completing ported test (including Task 1's own `test_enter_runs_the_plan_and_finishes_with_the_summary_head`) crashes at the app handler mid-task. The executor will see reds that are not their port's fault.

**Suggestions.** Strike `tests/test_execute_screen.py` from the Task-1 intermediate gate (keep `tests/test_session.py tests/test_render.py`), or gate everything only at the combined commit, as the executor rules already mandate.

**Risk Assessment.** MEDIUM — highest blast radius of the phase; all mechanisms verified present, but the intermediate gate as written sends the executor chasing ghosts.

### 20-11

**Summary.** Headless on the same plan/engine; dead two-step path leaves `run_wizard`.

**Strengths.**
- Everything cited matches the tree: `run_wizard` at `app.py:130-197` with exactly the positional head + `installed`/`category_blurbs`/`select_catalog` the plan removes; the two-step branch at `app.py:122-127`; `category_blurbs=load_categories(_REGISTRY)` at `setup.py:1537` (and `load_categories` still used by `_build_app` at `:1170`, so the import stays — the plan says keep); `FakePrompter` at `tests/test_app.py:57-79` and `RecordingPrompter` at `:1306` (both verified); 20 `run_wizard(` sites (counted); `_ask_mismatch`/`_sync_terminals`/`_verify_and_clean`/`_sync_terminals_and_report` all exist (`setup.py:360,719,1449,750`).
- The failure-path ordering is now fully specified (`20-11-PLAN.md:82`), and the 3-tuple unpack matches revised 20-03 (`:85`, ledger `:226`).
- `reinstall=frozenset()` hard-coded makes the `--yes` prohibition structural.

**Concerns.**
- **LOW (new)** — the truth "no runnable rows → prints the plan and the summary **without asking**" is only pinned under `--yes` (`test_all_yes_on_an_all_current_host…`), where the confirm is never called anyway; no non-`--yes` all-current test asserts the no-ask behavior.

**Suggestions.** Add one non-`--yes` all-current case asserting `confirm` is not called (or drop the "without asking" clause from the truths).

**Risk Assessment.** LOW.

### 20-12

**Summary.** Wait-for-state: Enter joins the service's single flight via `_await_state`; token fails closed on `esc`.

**Strengths.**
- The core mechanism remains verified end-to-end: the single flight is keyed by `frozenset(tool.id for tool in tools)` (`version_status.py:1508`) and joins at the current epoch (`:1510-1521`, "never joins across an `invalidate`" — re-read this session); the screen refreshes the whole `ExecuteInputs.catalog`, matching the tier screens' key. `run_live` returns `(T | None, str | None)` (`ui_common.py:42`) — the `_result, error` unpack is right.
- `HeldRefreshService` fits `FrozenStateService`'s overridable surface (`publish`/`refresh`/`refresh_skills` at `tests/state_doubles.py:136-150`).
- The 20-10 `checking…` test port (frozen → held) is honest about the behavior change.

**Concerns.**
- **LOW (new)** — `service.calls == [frozenset({"rg"})]` after mount + first Enter (`20-12-PLAN.md:100`) cannot be delivered by the specified guards: `on_mount` joins the flight (`:74` — a first `refresh` call on the double) and the first Enter calls `_await_state()` again (the guard at `:72` is only on `_start_requested`, which is False after a mount-join). The double appends per call (no single-flight), so it records two calls; only the *real* service would join. The truth ("exactly one pass for the screen even with repeated Enter presses", `:27`-area truth + T-20-25 at `:186`) demands a pending-wait guard (e.g. `_waiting`, set when `_await_state` starts, cleared in `on_state_settled`) that the context block doesn't specify. TDD will surface it instantly; the fix direction is documented, so the risk is an executor weakening the double instead.

**Suggestions.** Specify the pending-wait guard in the context block (or make `HeldRefreshService.refresh` join like the real service).

**Risk Assessment.** LOW.

### 20-13

**Summary.** The `r` key, the reworded `UNPROVEN_NOTE`, and the 80×20 layout pins.

**Strengths.**
- All anchors re-verified: `UNPROVEN_NOTE = "not proven: reinstall with r to adopt"` at `version_status.py:606`; the pin at `tests/test_version_status.py:4212`; the catalog `r` binding at `catalog_tui.py:322`; `Pilot.resize_terminal` at `.venv/.../textual/pilot.py:86`.
- The worst-case-head math is right (13 finished categories ≈ 199 cells → 3 lines; `max-height: 3` covers both states; status/keys at rows 18/19 leaves exactly ≥15 plan rows + ≥6 log rows).

**Concerns.** None new or still-open.

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-14

**Summary.** Deletes the second copies (`Summary`/`fold_run`/`run_installs`/`summarize`, the three legacy renderers, `reapply_post_install`) with grep proof and a deleted-test ledger.

**Strengths.**
- The word-anchoring analysis still holds exactly: `tests/test_install_sh.py:211` (`test_run_installs_without_launching_when_no_run_set`) and `tests/test_agent_environment_e2e.py:62` (`ApplySummary(`) don't match the gate patterns — both re-verified on disk.
- `tests/test_versions.py:119-129` really carries `(session_module, "run_installs")` in `test_production_paths_select_the_real_release_resolver` — the plan's handling is right.
- `reapply_post_install` (`engine.py:300`) / `_dispatch_post_install` (`:287`) split is correct; the "single exception" paragraph exists at `post_install.py:23-27` as quoted.
- Deletion sequencing is right: `render_summary`'s last production caller (`app.py:187`) died in 20-11 (W7); this plan is W8.

**Concerns.**
- **MEDIUM (new)** — **Task 1's commit window is red.** `installer/render.py:29` does `from installer.session import Summary`, used only as `render_summary`'s annotation (`:66`). Task 1 deletes `Summary` from `session.py` while Task 2 (a separate commit, different files) deletes `render_summary` and its import. Between them, pyright (`make validate`, pre-commit — `--no-verify` forbidden) fails on the dangling import, contradicting Task 1's own acceptance ("`make validate && make test` exit 0"). The Task-1 git-grep gate misses it by design: `\bSummary\(` and `class Summary\b` don't match import/annotation references. `tests/test_render.py:32` imports it too (`:63,:73,:79,:96,:112,:386` construct it). Fix: land Tasks 1+2 as one commit (the 20-10/20-11 pattern), or reverse the order (the renderers have no production callers by W8).
- **MEDIUM (new)** — **the inherited result-word zero gate cannot pass.** `render.py:95`, inside the docstring of *kept* `render_failure_details` ("…so a bare \"failed\" is never the last word an operator sees"), is a quoted `"failed"` that survives Task 2's deletions. After `render_summary` (`:80-82`) dies, `grep -vE '^\s*#' installer/render.py | grep -cE '"(failed|checksum mismatch|…)"'` counts 1, not 0. (The review/done-words zero gate *is* satisfiable: its only literals are `:57` and `:78`, both deleted; `Installed: ` only at `:69`.) This is the same false-failing-gate class cycle-1 flagged twice — the gates were moved here without re-inventorizing the file.
- **LOW (new)** — Task 1's git-grep "must list only `installer/session.py` definitions, `tests/test_session.py` and `tests/test_versions.py`" omits `tests/test_render.py`, which still constructs `Summary` for the six `render_summary` tests until Task 2 deletes them — the gate fails on an expected same-plan caller. The context's "own tests" rule covers the intent.

**Suggestions.** One commit for Tasks 1+2 (or delete render.py's renderers first); reword `render.py:95` (backticks or unquoted) in the same Task-2 commit or scope the gate past docstrings; add `tests/test_render.py` to Task 1's allowed list.

**Risk Assessment.** MEDIUM — now the phase's riskiest plan, not for its deletions (all grep-proven) but for two gates/commit boundaries that cannot pass as written.

### 20-15

**Summary.** Finishes the audit.py deletion cascade down to a confirm-only prompter.

**Strengths.**
- Every symbol verified: `installer/audit.py` (36 lines, `ToolStatus` + `audit()`); `installer/selection.py:33,55,59` (`category_choices`, `_is_verified_download`, `tool_choices`); `installer/prompt.py:15-33` (three-method `Prompter`, `CallbackPrompter(ask_checkbox, ask_confirm)`); `setup.py:309` (`_ask_checkbox`) and `:1515` (`CallbackPrompter(ask_checkbox=…)`).
- `macos_stub_reason`'s keep decision is right: it has another production caller at `installer/status.py:144`.

**Concerns.**
- **LOW (new, wording)** — Task 1's grep says output "must list only the files above (and `tests/test_status.py` for `macos_stub_reason`)", but `installer/status.py:41/:144` also matches and is *not* in the allowed list. The read_first conditional ("keep if another caller exists") carries the right intent; the gate sentence contradicts it.

**Suggestions.** Add `installer/status.py` to the gate's expected matches.

**Risk Assessment.** LOW.

### 20-16

**Summary.** Records Phase 20 in the architecture doctrine; rewrites the pre-Phase-20 paragraphs that describe deleted machinery.

**Strengths.**
- All anchors verified: `render_dependency_notice` at `.claude/architecture.md:49` (Tier paragraph); Phase 3's `run_installs` at `:103-110`; Phase 13 at `:652-655`/`attributed_install` at `:672`; Phase 14 at `:701`/"call into `run_installs`" at `:745`; Phase 19 is the last section (`:1026`).
- Pin-file structure matches: `_TRUNCATION_BANNER_FRAGMENTS` (`tests/test_docs.py:6`), `_PHASE_13_REQUIRED` (`:51`), `_PHASE_14_REQUIRED` (`:85`), `_PHASE_19_REQUIRED` (`:188`) + its test (`:211`) — the Phase 20 section slots in cleanly.

**Concerns.**
- **LOW (carried)** — Task 2's verify filters gate-failing lines on `deleted|Phase 20`, but the action never instructs the rewriter to use the word "deleted" — a transition sentence phrased otherwise ("the old loop was folded into `execute_plan`") false-fails a doc that is actually fine.

**Suggestions.** Mandate "deleted" for removed machinery in the rewrite instruction, or drop the filter and assert plain absence.

**Risk Assessment.** LOW.

### 20-17

**Summary.** The mechanical `ExecuteInputs` contract change alone: `version_refresh` required, `installed` deleted, `terminal_sync` added and wired.

**Strengths.**
- Best-grounded plan in the batch: `ExecuteInputs` verified field-for-field (`execute_screen.py:400-417` — `installed: Callable[[Tool], bool] = is_installed` at `:411`, `version_refresh: VersionRefreshService | None = None` at `:415`); port inventory exact (97 `ExecuteScreen(`, 60 `installed=`, 22 `ExecuteInputs(` in test_wizard_app, 19 `installed=lambda`).
- `frozen_service(home)` and `pass_state` support the `_inputs` default exactly as specified (`tests/state_doubles.py:158,200-232`); scratch-HOME makes `Path.home()` safe.
- Wave 5 placement is right (file-disjoint from 20-08/20-09; before 20-10/20-12 need the default).

**Concerns.** None new or still-open.

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-18

**Summary.** Four end-to-end pins through the real `UnifiedApp` (`a` on all-current, order parity, mixed-run retention, D-05).

**Strengths.**
- The metadata fix landed (`20-18-PLAN.md:6` `depends_on: ["20-10", "20-12", "20-13"]`, wave 9) — the constraint now survives frontmatter-trusting tooling.
- D-05 correctly pinned, not reimplemented: `selectable=lambda tool: not self._is_unavailable(tool)` at `catalog_tui.py:375` (verified) shipped in Phase 19.

**Concerns.** None new or still-open.

**Suggestions.** None.

**Risk Assessment.** LOW.

### 20-19

**Summary.** Rewrites the container e2e parser for the `Summary — …` line and the outcome rows, same wave as 20-11.

**Strengths.**
- Necessity and scheduling verified: `SUMMARY_RE` at `scripts/container-e2e-verify.sh:242` parses the old `Installed: …` line that `render.py:69` prints today; `parse_summary_line` (`:245-258`) with its `[[ -n "$PARSE_INSTALLED" && -n "$PARSE_FAILED" ]]` success rule; `accumulate_summaries` (`:365-383`), `dependency_failures_explained` (`:390-403`), the four `render_summary` comments (`:244`, `:368`, `:496`, `:544`) all exist as described.
- `write_tester_path` (`:162`) untouched, as required by the two test files that extract it.
- The self-checks source the real functions and pin the old line's non-match.

**Concerns.**
- **LOW (carried)** — name overloading: `ACC_SKIPPED_FILE` (`:382`, the dependency-failed *lines* accumulator) survives while the plan renames counter `ACC_ALREADY` → `ACC_SKIPPED`. Two near-identical names for different things in a shell script CI depends on.

**Suggestions.** Rename the lines file (e.g. `ACC_DEP_LINES_FILE`) in the same commit (all sites: `:382`, `:391`, `:403`, `:419-420`, `:484`, `:490`, `:520-521`, `:524`, `:529`, `:559-560`, `:563`, `:567-568`).

**Risk Assessment.** LOW.

---

### Overall summary

**Verdict: the cycle-1 revisions did their job — every consensus item and nearly every per-plan LOW is genuinely resolved in the current text (verified against both the plan files on disk and the tree), and no revision broke the wave topology, the shared vocabulary, or a cross-plan contract. No HIGH concerns remain. Three MEDIUM defects survive or were introduced, all in commit-boundary/gate satisfiability, none in design.**

**Remaining HIGH:** none.

**Remaining actionable items (execute-phase fixes, all small):**

1. **MEDIUM — 20-14, Task 1 commit window**: `render.py:29` imports `Summary` (annotation-only at `:66`), invisible to the Task-1 git-grep gate; deleting `Summary` in session.py at Task 1 makes `make validate` (pyright, pre-commit; `--no-verify` forbidden) fail before Task 2 lands. Make Tasks 1+2 one commit or reverse their order.
2. **MEDIUM — 20-14, inherited result-word zero gate**: `render.py:95`'s quoted `"failed"` lives in kept `render_failure_details`' docstring, so the moved gate counts 1, not 0. Reword the docstring or scope the gate. (The sibling review/done-words zero gate is satisfiable: its only literals are `render.py:57,:78`.)
3. **MEDIUM — 20-10, false intermediate gate**: "tests/test_execute_screen.py … exit 0 after this task alone" (`20-10-PLAN.md:167`) cannot hold — `_host` runs the real `UnifiedApp` (`tests/test_execute_screen.py:259`), `InstallRunFinished` bubbles (no `stop()`), and `wizard_app.py:2977` reads the fields Task 1 removes. Drop the screen module from the intermediate gate.
4. **LOW — 20-12**: `service.calls == [frozenset({"rg"})]` needs a pending-wait guard the context doesn't specify (mount-join + first Enter = two calls on the non-joining double).
5. **LOW — 20-14**: Task 1's grep allowed-list omits `tests/test_render.py` (expected `Summary` constructions until Task 2).
6. **LOW — 20-01**: `def visit(` = 0 gate vs "the SAME nested `visit` function" wording (carried).
7. **LOW — 20-16**: Task 2's `deleted|Phase 20` gate filter can false-fail a transition sentence (carried).
8. **LOW — 20-19**: `ACC_SKIPPED_FILE` vs counter `ACC_SKIPPED` overloading (carried).
9. **LOW — 20-15**: Task 1's grep "must list only" omits `installer/status.py` (`macos_stub_reason`'s other production caller at `:144` — keep, as the read_first intends).
10. **LOW — 20-11**: the no-runnable "without asking" truth is only pinned under `--yes`.
11. **LOW — 20-08**: name `perform_action`'s `ValueError` → row `crashed` (fail-closed) — optional, carried.

**Risk by plan:** LOW — 20-01, 20-02, 20-03, 20-04, 20-05, 20-06, 20-07, 20-08, 20-09, 20-11, 20-12, 20-13, 20-15, 20-16, 20-17, 20-18, 20-19. MEDIUM — 20-10 (blast radius; intermediate gate), 20-14 (two unsatisfiable commit-boundary gates; deletions themselves are sound).

**What I did not check:** I ran no tests, no `make validate`, no pilots, and did not literally execute the no-growth gate scripts against hypothetical post-20-06/20-09 trees (I reasoned them from today's exact literal inventory: 2 review/done literals, 4 result literals in `render.py`). Textual's `exclusive=True` worker cancellation semantics (20-12's double-call reasoning) are from documented behavior, not execution. Per-test port inventories in the four large test files were count-verified, not read line by line. `20-SPEC.md`/`20-PATTERNS.md`/`20-RESEARCH.md` are unchanged since cycle 1 (only the 11 plans + UI-SPEC were revised in `74a893b`), so cycle-1's verification of them stands.

### Verification coverage (cycle 2)

Source-grounding pass (`plan_review.source_grounding`, effective authority `intel`):
- VERIFIED: every distinct repo path cited in the 19 plans exists (67 backtick-quoted file paths scanned). Bare module names used as prose shorthand (`audit.py`, `catalog_tui.py`, `engine.py`, `execute_screen.py`, `render.py`, `session.py`) resolve under `installer/`. `tests/test_plan.py` is a new artifact created by 20-04 (excluded). `20-NN-SUMMARY.md` paths are phase outputs (excluded).
- Reviewer re-verified ~50 symbol/line anchors against the tree; `git diff bb0b71f..HEAD` over `installer/ tests/ scripts/ .claude/` is empty, so cycle-1 source verification still holds.
- UNCHECKABLE: individual Python symbols and signatures — the `intel` adapter does not analyze Python and `grep` cannot assert signatures; coverage rests on the reviewer's manual reads.
- Not executed: `make validate`, `make test`, pilots, the no-growth gate scripts.

Cross-artifact fact-drift pass:
- Phase status (deterministic `drift-guard phase-status`): `lag` (STATE.md "Ready to execute" vs ROADMAP "Not started") — not a finding.
- Success criteria / requirement IDs (ROADMAP PLAN-01..PLAN-08 vs plan `requirements:`): no contradiction found.
- Glossary (CONTEXT.md vs plan usage): no contradiction; the cycle-1 pending-row copy discrepancy is resolved in 20-UI-SPEC.md.
- Advisory only; contributes to neither HIGH nor actionable counts.

---

## Cycle 1 (audit trail) — reviewed at HEAD bb0b71f


### OpenCode Review (opencode-plan-review)


**Reviewer note on method:** Every claim below was verified against the working tree at `HEAD` (`bb0b71f`). I read the cited files and traced the cited mechanisms; line references were re-checked rather than trusted. The research document's "State of the Art" table proved accurate — of ~60 line references checked, essentially all matched the tree (deviations are noted where found). No finding below relies on plan text alone.

**Verification highlights (evidence the plans rest on):** `installer/deps.py:27-29` (`Resolution` = order/dragged_in/warnings only), `deps.py:111-113` (present tools dropped from `order` — Pitfall 1 is real), `deps.py:93-95` (the `any(...)` to replace), `installer/session.py:106-165` (`Summary`/`fold_run`/`run_installs`/`order_for_install`), `session.py:29-37` (`_UNRESOLVED` includes `NO_METHOD`/`MANUAL_REQUIRED`), `setup.py:897-914/1121-1138/1160-1166/1247-1327/1521-1562` (service construction, `replace(execute, installed=version_refresh.is_present, ...)`, `_session_exit_code`, main's routing), `installer/version_status.py:1508-1521` (single-flight keyed by `frozenset(tool.id ...)`), `installer/wizard_app.py:2572-2577` (tier screens pass the **whole** catalog), `wizard_app.py:2896-2899` (`_install_closed` clears the shared `_staged`), `installer/catalog_tui.py:375` (unavailable rows already unselectable — D-05 done by 19), Textual 8.2.7's `OptionList.replace_option_prompt` (`.venv/.../textual/widgets/_option_list.py:647`) and `Pilot.resize_terminal` (`.venv/.../textual/pilot.py:86`) both exist. Test-count floors match reality: `tests/test_deps.py` = 23 tests, `tests/test_execute_screen.py` = 114 tests/4705 lines, `tests/test_wizard_app.py` = 301/8036, `tests/test_setup.py` = 126/3830, `tests/test_app.py` = 123/3776, `ExecuteInputs(` in test_wizard_app = 22, `install_summary` sites = 12/19, `Summary` in test_setup = 34, `_UNPROVEN` at `tests/test_version_status.py:4212`.

---

### 20-01

**Summary.** Adds three defaulted fields to `Resolution` — `closure` (deps-first order including present tools), `blocked` (typed blocked rows with the first blocking dependency), `requested_by` (dragged id → first selected requester) — while keeping `order`, `dragged_in`, `warnings` byte-identical. This is the correct unblocking prerequisite for `build_plan` (20-04): today the resolver throws away exactly what the plan needs.

**Strengths.**
- Solves the real gap the research identified: `installer/deps.py:111-113` computes `satisfied_by_install` and `runnable`, so present tools have no position in `order` — verified. `closure = topo([t for t in wanted if t.id not in blocked])` with one shared `topo` function is the minimal additive fix with no second sort.
- `dragged_in` staying `()` for present deps is correct by construction, not by assertion: `deps.py:137` derives `dragged_in` from `ordered` (runnable only), so the "unchanged" claim holds without touching that line.
- The blocked-order claim ("`c` precedes `z` in wanted order") is verifiable from `collect` at `deps.py:59-69` — the tool is appended (`:63`) before its deps are walked (`:64-69`).
- `Mapping` is indeed already imported (`deps.py:12`); the plan correctly flags that `field` must be added (`deps.py:13` imports only `dataclass`).
- Cycle detection carries over to the closure run (T-20-01): the same `visiting` guard and `DependencyCycleError` at `deps.py:121-125`.

**Concerns.**
- **LOW** — Task 1's acceptance gate `grep -c "def visit(" installer/deps.py` is 0 requires the nested DFS inside `topo` to be inlined or renamed; a natural refactor keeps a nested helper named `visit`, which would fail the gate on style, not substance. Harmless but will cause one head-scratch.
- **LOW** — Task 2's `blocked_needs[tool.id] = None if unsatisfiable else needs` relies on the executor correctly mapping "unsatisfiable" to the `not available(tool)` branch at `deps.py:92`. The mechanism is right (verified: `unsatisfiable` and `dep_blocked` are the two disjoint blocking causes at `deps.py:97`), but the plan's wording leaves the mapping implicit.

**Suggestions.** Rename the inner DFS helper deliberately (e.g. `_place`) in the same edit, or drop that grep clause. State explicitly that `needs=None` is recorded only on the `unsatisfiable` arm.

**Risk Assessment.** LOW — pure additive change to a 184-line module with 23 existing tests pinned byte-identical; the hardest part (order stability) is enforced by keeping `topo` the single sort.

---

### 20-02

**Summary.** Extracts `_perform`'s five pre-flight refusals into one `update_refusal(tool, ownership) -> UpdateOutcome | None` shared with `build_plan`, and removes the "moving it there" promise from the two strings, guarded by a grep test (PLAN-08).

**Strengths.**
- The no-`platform` parameter decision is **verified correct**: every refusal branch reads only `target.tool`/`ownership` — unknown/confidence at `update.py:248-254`, sdkman `:256-262`, `UNMANAGEABLE_OWNERS` `:263-283`, volta `:284-294`, pnpm host-setup `:312-333` (which reads `target.tool.methods` and `pnpm_add_command`, never `platform`).
- The status-count acceptance gates match today's tree exactly: `status="unknown-owner"` occurs 2× (`:251`, `:502`), `status="unsupported"` 5× (`:259`, `:280`, `:288`, `:330`, `:520`) — after the move the counts stay the same, so the gates are self-consistent, not aspirational.
- The two reworded strings exist exactly as described: `update.py:307-311` and `catalog_tui.py:821-825`, and the replacement texts match the UI-SPEC Copywriting Contract rows verbatim (`20-UI-SPEC.md:373-375`).
- Returning the full `UpdateOutcome` (not a bare string) preserves the `unknown-owner`/`unsupported` distinction the PATTERNS doc demanded (`20-PATTERNS.md:120`) — the plan satisfies that constraint while improving on the sketch.
- The parity test's "capture today's values as literals before refactoring" instruction is the right discipline for an extraction that must not drift.

**Concerns.**
- **LOW** — The pnpm branch's post-move claim "guard `method is None` is now impossible there" is sound only because `update_refusal` returns for `method is None` first; a one-line comment is planned. Fine, but the executor must not also move the `executors.execute(method, runner)` line (`update.py:334`) — the plan says keep it; worth being careful since `method` can still be `None` for other owners (brew/cask/uv never had the guard).

**Suggestions.** None beyond keeping the literal-capture step of the parity test.

**Risk Assessment.** LOW — small pure-core extraction with parity pinned both directions, plus two string edits with a grep guard.

---

### 20-03

**Summary.** Extracts the `VersionRefreshService` and `UpdateService` constructions from `_build_app` into `_build_services(tools, platform)` so the headless route (20-11) can reuse the same services — fixing the verified defect that headless `--all --yes` today can never update anything.

**Strengths.**
- The extraction is genuinely clean: verified `UpdateService`'s kwargs (`setup.py:1121-1138`: `platform`, `live_platform`, `runner`, `resolve_tag`, `tools`, `managed_packages`, `replay_globals`, `reresolve_ownership`, `invalidate`, `terminal_follow_up`) reference only `tools`, `platform`, `version_refresh`, `_reinstall_globals` and a terminal wrapper — none of the policy objects built between them in `_build_app`.
- The plan correctly anticipated the `policy` snag: `pnpm_globals.node_install_policy(tools)` at `setup.py:1063` is closed over by `_node_globals_report`/`_globals_preview` (`:1065-1073`) *and* `_reinstall_globals` (`:1075-1078`), and the plan pre-commits to keeping `policy` in `_build_app` and recomputing inside `_build_services`.
- Position claim verified: `VersionRefreshService` is hoisted above `uninstall_inputs` (`setup.py:892-897`), and `uninstall_inputs` closes over it (`:977`, `:982`) — the hoist point is right.
- `_which_with_brew` is module-level (`setup.py:692`), so the `terminal_drift` kwarg moves freely.

**Concerns.**
- **MEDIUM** — The second `node_install_policy(tools)` call breaks a documented invariant, not just a comment: `setup.py:1060-1062` says "Preview and reinstall must receive the **SAME policy object**: the module's preview-equals-effect guarantee rests on both paths reaching one argv builder with one set of inputs." After this plan, preview (`_globals_preview`, in `_build_app`) and replay (`_reinstall_globals`, in `_build_services`) hold two distinct policy objects. `node_install_policy(tools)` (`installer/pnpm_globals.py:229`) is deterministic over `tools` today, so behavior is identical — but the invariant comment is now false, and if the builder ever gains environment- or version-sensitivity, preview silently diverges from effect with no test to catch it.

**Suggestions.** Have `_build_services` return the policy too (e.g. return `(refresh, updates, policy)` and let `_build_app` reuse it), or thread `policy` in as an argument — one line either way keeps the existing comment true. If the two-object split is kept, rewrite the `setup.py:1060-1062` comment in the same commit to state the input-equality guarantee instead of object identity.

**Risk Assessment.** MEDIUM — the wiring itself is low-risk and well-tested, but the policy split violates a stated invariant with no automated guard; cheap to fix now, easy to forget.

---

### 20-04

**Summary.** Introduces the plan model: `Disposition`, `PlanRow`, `Result`, `WORDS`/`RESULT_WORDS`, `review_counts`, and a pure `build_plan` covering WAIT/MISSING/OK/reinstall/dragged/blocked rows, with the health matrix deliberately deferred to 20-05.

**Strengths.**
- Purity is testable exactly as planned: `GuardedPopen` is patched onto `subprocess.Popen` in `tests/conftest.py:108`, so replacing `Popen` with a raiser is an established mechanism, not a novel one.
- `pass_state` (`tests/state_doubles.py:200-232`) supports every input `plan_state` needs — verified: `present`, `ownership`, `version`, `broken`, `misconfigured`, `unconfigured` are all real kwargs, so the health→kwarg mapping in the plan compiles against the existing double.
- `ManagerOwnership`'s constructor list in the plan matches the dataclass field-for-field (`installer/ownership.py:304-318`, with `off_policy`/`broken` defaulted).
- Every reason text matches the UI-SPEC Disposition copy table verbatim (`20-UI-SPEC.md:187-208`): `not installed`, `needed by {requester}`, `already current`, `reinstall requested; r again to undo`, `managed by {label}`, `already present`, `needs {dependency}`, and the UNAVAILABLE fallback to the resolver warning. The `WORDS` table matches `20-UI-SPEC.md:143-152` including WAIT's `None` done word.
- The interim-fallthrough strategy (any other health → SKIP with `_first_clause`) is honest and explicitly replaced by 20-05 — no decision is silently reduced.
- `select_tools(tools, ids)` exists with exactly that signature (`installer/selection.py:82`).

**Concerns.**
- **LOW** — `plan_state(..., receipt=None)` can't do what it says: `pass_state` never forwards a receipt (`tests/state_doubles.py:200-232` has no receipt kwarg; `ToolState.receipt` exists at `version_status.py:709` but `tool_state`'s receipt kwarg is unreachable through `pass_state`). Tests needing a *present* receipt (e.g. a G case B variant) must call `tool_state` directly or extend `pass_state`. As written only `receipt=None` states are expressible.
- **LOW** — The test snippets construct `VersionStatus(installed="1.0", latest="2.0", outdated=True, stale=False, source="test")` — `tool_id` is the first, non-defaulted field (`installer/version_status.py:163-170`), so these snippets are a `TypeError` as written. Trivially fixed at execution, but the plan text should not teach a wrong constructor.

**Suggestions.** Add `receipt` passthrough to `pass_state` (or construct via `tool_state` in `plan_state`), and add `tool_id=` to the `VersionStatus` snippets here and in 20-05.

**Risk Assessment.** LOW — the model is pure, the vocabulary parity is pinned by iteration, and the drag/reinstall/wait semantics all match locked decisions (D-02, D-14, L-20-06).

---

### 20-05

**Summary.** Completes the disposition table: BROKEN (including receipt drift, L-20-01) crossed with `UNMANAGEABLE_OWNERS`, MISCONFIGURED with/without steps (L-20-04), OUTDATED via `update_refusal`, the plan-time blocked-dependent post-pass, and the G probe cases A–I as parametrized tests on all three tiers.

**Strengths.**
- The post-pass is genuinely necessary, not redundant with the resolver: `is_blocked` blocks only on unavailability (`deps.py:92-95`), so a *broken but available* dnf-owned dependency does **not** resolver-block its dependent — the plan's marquee case (mmdc/node) is exactly the hole the post-pass closes, and the chain-propagation in plan order is the right mechanism.
- Zero-sudo BLOCKED is grounded in the real constants: `UNMANAGEABLE_OWNERS = NATIVE_OWNERS + OS_PACKAGE_OWNER` (`installer/ownership.py:119-125`), `CHANGED_SINCE_INSTALL = "changed since install"` (`installer/receipts.py:44`).
- The G case mapping is faithful to the probe table (`.planning/research/audit-2026-10-13/G-ui-health-states-and-reuse.md:250-258`) — each of A–I maps to the new-world assertion, and the plan correctly *fixes* the probed bugs (A's "rg is not listed", D's silent refusal).
- The decision to make `_row` exhaustive (if/elif ending in the OK branch) removes the 20-04 fallthrough with pyright narrowing — good "best, not easiest" discipline.

**Concerns.**
- **LOW** — The exhaustive `else` = OK branch silently swallows an `UNAVAILABLE` `ToolState` that reaches `_row`. Today that path is closed by construction — `tool_health` makes UNAVAILABLE = absent + no applicable method (`version_status.py:212-214`), and such tools are resolver-blocked into `_blocked_row` — but it reopens in a narrow race: `refresh` re-reads brew per pass (`version_status.py:1537`) and replaces `self._platform`, so a state published before brew appeared can say UNAVAILABLE while `build_plan`'s platform sees a method (available → not resolver-blocked). Then an absent tool would render "already current / managed by …". A one-line `UNAVAILABLE → BLOCKED with _first_clause` guard in `_row` closes it for free.
- **LOW** — The parametrized "OUTDATED allowed" case includes "pnpm with a node method", but 20-04's `plan_state` hard-codes `ManagerOwnership(..., method=None, ...)`; with `method=None`, `update_refusal`'s pnpm branch (`update.py:312-333`) refuses as host-setup, so the pnpm leg of that test can't be built with the specified double. `plan_state` needs a `method=` passthrough.
- **LOW** — The post-pass snippet indexes `catalog[r.tool_id]` while `build_plan` receives `catalog: Sequence[Tool]`; the executor needs a `by_id` map (the resolver already builds one at `deps.py:49`). Mechanical, but worth saying.

**Suggestions.** Add the UNAVAILABLE guard in `_row` (belt-and-braces against the platform race), give `plan_state` a `method=` parameter, and add `tool_id` to the `VersionStatus` fixtures.

**Risk Assessment.** LOW — every pair is pinned, the drift-repair consent (L-20-01) shows the reason before Enter, and the sudo prohibition is grep-pinned.

---

### 20-06

**Summary.** The one renderer: `render_plan` with mark column, padded id, word from `WORDS`, grouped indented dragged rows, folding at the word column, `to configure:` step continuation, sanitization — plus moving the health glyph table out of `catalog_tui` into `version_status.HEALTH_MARKS`.

**Strengths.**
- The anatomy matches the UI-SPEC Row anatomy exactly (`20-UI-SPEC.md:99-119`), including the fold column at `2 + idw + 2` and the explicit-newlines-in-one-`Text` strategy that dodges the widget's own wrapping (the baseline measured that a `no_wrap` option *wraps* anyway — `20-UI-SPEC.md:67`).
- The `HEALTH_MARKS` move is verified safe: `_HEALTH_CELL` (`catalog_tui.py:249-258`) has exactly the seven entries claimed, only `catalog_tui` uses it (no other importer found), and the `_HEALTH_CELL = HEALTH_MARKS` alias keeps `health_cell` (`:127`) and the legend untouched.
- `render.py` imports nothing from `catalog_tui` today, so the `grep -c "from installer.catalog_tui" installer/render.py` = 0 gate is already true and stays true.
- Sanitization requirements mirror the existing ANSI-bomb test pattern (`tests/test_execute_screen.py:1405`) and `sanitize_log_line` (`installer/sanitize.py:13`).
- The width math is right: 24-char id + 2 indent + longest fixed phrase `skipped — already current (r: reinstall)` = 69 ≤ 78.

**Concerns.**
- **MEDIUM** — Task 1's acceptance gate — `grep -vE '^\s*#' installer/render.py | grep -cE '"(will install|…|installed|updated|repaired|reconfigured|reinstalled)"'` is 0 — **cannot pass at 20-06's commit time**. `render_audit` still contains `state = "installed"` (`render.py:57`) and `render_summary` still contains `("installed", summary.installed)` (`render.py:78`); both are deleted only in 20-14 (W8), three waves later. The same class of false-failure hits 20-09 (below). An executor honoring acceptance criteria literally either stalls or is tempted to delete those renderers early — which would break `app.run_wizard` (`app.py:166`, `:187`), still live until 20-11.
- **LOW** — The copy discrepancy: UI-SPEC itself renders the pending row two ways — `… {id}  checking…` (`20-UI-SPEC.md:271`) vs `…  {id}  checking…` (`:399`). The anatomy (`:102`) yields one space after the mark (`… rg  checking…`), which is what this plan implements — but 20-10/20-12 write their pilot expectations with two spaces (see those sections). One form must win before execution.

**Suggestions.** Scope both word-literal gates to the new functions (e.g. grep only `render_plan`/`plan_row_text`/`render_run_summary`/`outcome_row_text` bodies, or move the "no word literal" gate into 20-14 where the old renderers die), and pick the anatomy form (`… {id}`) as canonical, fixing the downstream test texts.

**Risk Assessment.** MEDIUM — the renderer logic itself is low-risk and well-specified; the risk is entirely the false-failing gate, which invites an out-of-sequence deletion.

---

### 20-07

**Summary.** The one engine: `RowOutcome`, `RunContext`, `execute_plan` (folding in `run_installs`' mismatch/propagation logic), `_with_force` (moved `_with_repair`), and the four pure views — `exit_code`, `retained`, `ran_anything`, `summary_counts`.

**Strengths.**
- The `UpdateRunner` protocol matches `UpdateService`'s real public surface exactly: `in_flight` property (`update.py:482`), `begin(tool_id) -> bool` (`:485`), `end()` (`:492`), `run(target)` (`:496`).
- The `_INSTALL_RESULT` mapping preserves today's exit-code parity by design: today `Summary.has_failure` explicitly excludes `manual_required`/`no_method` (`session.py:120-126`), and the plan maps them to `manual`/`blocked`, both outside `_FAILURE` — verified no exit-code drift for `--all --yes` runs.
- Dependency propagation semantics preserved: `_UNRESOLVED` already contains `NO_METHOD`/`MANUAL_REQUIRED` (`session.py:29-37`), so `dependency_failed` propagation is unchanged.
- The crash policy is a strict improvement with the right tests: `run_installs` *drops* rows after a `should_continue` stop (`session.py:212-213` breaks, "tools never reached are absent from that list"), while `execute_plan` guarantees one `RowOutcome` per row (`crashed` + `not_attempted`) — T-20-12 addresses exactly the repudiation the old code allowed.
- `on_row_started` inside the per-row `try` (a raising UI callback → `crashed`, not a dropped run) is a subtle, correct catch.

**Concerns.**
- **LOW** — A7 (update failures don't propagate to dependents) is an assumption, but it is pinned by a test and matches D-03's "only a direct selection updates" philosophy.
- **LOW** — `_with_force` and `execute_screen._with_repair` (`execute_screen.py:240-277`) coexist for two waves by design; the plan says so and 20-10 deletes the screen's copy. Acceptable debt, explicitly scheduled.

**Suggestions.** None material.

**Risk Assessment.** LOW — mostly relocation of already-tested logic (`run_installs`' body) into a row-addressable frame, with parity tests on both sides.

---

### 20-08

**Summary.** Executes the typed `ConfigStep`s: one dispatcher by `ConfigStepKind`, the portable `sh -c 'cd -- "$1" && shift && exec "$@"'` cwd wrapper with execution-time re-validation, pnpm group via the node executor, terminal sync, and the empty-argv skill handoff → `manual`.

**Strengths.**
- The dispatch table matches the real closed `ConfigStepKind` Literal member-for-member (`installer/model.py:311-320` — all 8 kinds quoted verbatim in the plan), and the empty-argv producers are real: `partial_steps` builds `ConfigStep(f"install {tool.id} for {label}", "skill_install", harness)` with no argv (`installer/skill_lifecycle.py:972-983`).
- The cwd wrapper is correct as specified: with `sh -c '<script>' sh <cwd> <argv…>`, `$1` is the cwd and, after `shift`, `"$@"` is exactly the argv — no shell reinterpretation, portable (no `env -C` on macOS, no process-global `chdir`), and pinned by an exact-argv test.
- `perform_action`'s real signature and statuses match the mapping (`installer/skill_lifecycle.py:656-677`, `LifecycleStatus` at `:27`): `manual-required` → `MANUAL_REQUIRED` with instructions feeding `render_handoff`, `completed`/`present` → success.
- Stop-at-first-failure preserves 19 D-18's enable-canonical-before-remove ordering — the DoS threat (T-20-15) is real and correctly mitigated.
- TOCTOU on `cwd` (T-20-14) is re-validated at execution time (absolute, `lstat`, not symlink) — the plan doesn't trust a minutes-old plan.

**Concerns.**
- **LOW** — `perform_action` raises `ValueError` when a lifecycle has no executable operation (`skill_lifecycle.py:677`); the per-step catch list is `CommandError`/`OSError`, so that path surfaces as a row `crashed` (exit 1) rather than `failed`. Unreachable for `partial_steps`-produced steps, but the plan could name it.

**Suggestions.** Optionally catch `ValueError` per step and map it to `failed` with the step text — or document the `crashed` outcome as intended.

**Risk Assessment.** LOW — all eight kinds get a representative test, including the three argv-less ones the research flagged (Pitfall 5).

---

### 20-09

**Summary.** The finished-side renderer: `Summary — {counts}` as the first line (the stable line the TUI log, headless output, and e2e parser all read), plus `outcome_row_text`/`running_row_text` reused by the screen's progress panel.

**Strengths.**
- The per-result row texts match the UI-SPEC Outcome copy table verbatim (`20-UI-SPEC.md:219-229`): `failed — no method succeeded`, `dependency failed — an earlier failure`, `manual — see the setup steps in the log`, `skipped — became present before it ran`, `blocked — no install method for this platform` — all cross-checked against the table.
- Reusing `fold_reason` from 20-06 for outcome rows keeps one folding routine; `display_order` reuse keeps one grouping rule.
- `Summary —` as the first line is the deliberate e2e contract (A11), and 20-19 lands the parser in the same wave.

**Concerns.**
- **MEDIUM** — Task 2's gate `grep -vE '^\s*#' installer/render.py | grep -cE '"(failed|checksum mismatch|dependency failed|not attempted|crashed|manual)"'` is 0 false-fails for the same reason as 20-06: `render_summary` still contains `("failed", summary.failed)` (`render.py:80`) until 20-14 (W8). Same fix: scope the gate to the new renderers or move it to 20-14.

**Suggestions.** See 20-06's suggestion — one fix covers both plans.

**Risk Assessment.** MEDIUM (gate only) — the renderer logic itself is LOW-risk and table-driven.

---

### 20-10

**Summary.** The big one: moves the TUI review, worker, finished panel, retained selection, sync gate, and exit code onto `build_plan`/`execute_plan`/`RowOutcome`, deletes the screen's classification/progress/update-loop copies, and ports the three largest test files.

**Strengths.**
- The sequencing problem is handled honestly and correctly: `InstallRunFinished` (`execute_screen.py:353-388`) changes shape, which breaks `wizard_app.on_install_run_finished` (`:2977`) until Task 2 — the plan explicitly lands Tasks 1+2 as **one commit** with the full gate only at that commit, honoring "never commit a red tree."
- The OptionList bet is verified safe: `replace_option_prompt` exists in installed textual 8.2.7 (`.venv/.../textual/widgets/_option_list.py:647`) along with `add_option`/`clear_options`/`get_option_index` — the in-place progress repaint mechanism is real.
- The retained-selection mechanics are exactly right for the shared set: `_staged` is one set shared with the tier browsers (`wizard_app.py:2517`, `:2578`), `_install_closed` today unconditionally clears (`:2898-2899`), and `intersection_update` in place is the only mutation that preserves sharing — plus L-20-07's never-add-dragged-ids falls out of intersection semantics for free.
- The outer-except completion (every unfinished row becomes `not_attempted` before `InstallRunFinished` posts) closes a real repudiation hole (T-20-32) the current worker has.
- The exit-code fold keeps every consumer working: `_session_exit_code` (`setup.py:1318-1327`) has four other callers (doctor `:1339`, fix, uninstall, guard `:1495`) that reach it with no plan run — the `outcomes is None → 0` rule preserves them.
- Test-port scale is realistic: 97 `ExecuteScreen(` constructions, 12 `install_summary` sites in test_wizard_app, 19 in test_setup — all counts verified exact — and the floors (≥295/≥120 against current 301/126) leave honest room for the deleted-by-decision pins.

**Concerns.**
- **MEDIUM** — Task 1's acceptance criteria still list "`make validate && make test` exit 0" while the plan's own action section says the tree is red between Tasks 1 and 2 and the full gate runs only at Task 2's combined commit. The bullet is stale as written; an executor or a later checker reading acceptance criteria in isolation will conclude Task 1 must end green, which contradicts the design. The bullet should read "at the combined Task 1+2 commit."
- **LOW** — The pilot expectation `…  rg` (option prompt with two spaces after the mark; also in 20-12) conflicts with the implemented anatomy `{mark}{sp}{indent}{id}` (`20-UI-SPEC.md:102`, `:271`), which renders `… rg` — the UI-SPEC's own `:399` line is the two-space outlier. Reconcile before writing the tests.
- **LOW** — `_fold_width()` reading the widget's size at layout time plus `plan_row_text(row, idw, width, hint=True)` means the review and the headless print must never share one cached `Text` — the plan keeps them separate (screen builds prompts directly, headless goes through `render_plan`), which is right, just worth guarding in review.

**Suggestions.** Fix the stale acceptance bullet; pick the one-space anatomy as canonical and align the `…  rg` expectations in this plan and 20-12.

**Risk Assessment.** MEDIUM — highest blast radius of the phase (6 files, ~100 test ports, a cross-module message reshape), but the risk is executional, not architectural: every mechanism it relies on (OptionList API, shared-set semantics, exit-code consumers, `run_live`, worker patterns) was verified present.

---

### 20-11

**Summary.** Rewrites headless `run_wizard` onto the shared plan and engine: one synchronous refresh pass, `build_plan`, printed plan, `Run this plan?`, `execute_plan`, `Summary —`, exit code from outcomes — and deletes the dead two-step prompter path.

**Strengths.**
- The dead-path claim is verified true in production: `main` routes every non-`--all`/`--categories` run to `_run_interactive_wizard` (`setup.py:1521-1529`) which never calls `run_wizard`, and the headless call (`:1530-1538`) passes flags that return before the two-step branch (`app.py:113-116`); `select_catalog` is never passed from setup.py. Deleting it (plus `tool_choices`/`category_choices` consumers in 20-15) is rule-5-correct.
- `reinstall=frozenset()` hard-coded in `run_wizard` makes the "--yes can never reinstall" prohibition structural (T-20-21) rather than behavioral.
- The state-check failure path fails closed exactly as the UI-SPEC requires (`20-UI-SPEC.md:304`: a surviving `checking…` row is "a failure to report, not a plan to run").
- The port inventory matches the tree: 20 `run_wizard(` sites in test_app (research said 30 in one spot — the plan's own list is what matters and it doesn't gate on 30), and the four named tests for deletion exist.

**Concerns.**
- **LOW** — The refresh-failure branch ("returns every row as `not_attempted`") is underspecified on ordering: rows must exist before outcomes can, so the implementation must build the plan (from a `state_of` that now yields nothing → WAIT rows) *after* the failed pass, then convert. The plan implies this but never says it; the executor will infer it, at the cost of one decision nobody pinned.
- **LOW** — `FakePrompter` keeps `select_categories`/`select_tools` until 20-15 (the protocol still declares them) — verified at `tests/test_app.py:57-79`; consistent.

**Suggestions.** Spell out the failure-path order (catch → build rows from ids/WAIT → emit `not_attempted` outcomes) so the "every row" wording has a concrete referent.

**Risk Assessment.** LOW — the rewrite is well-mapped onto the existing function (`app.py:130-197` read in full), and the acceptance cases (outdated brew updates / injected failure exits 1 / all-current runs nothing) are direct ports of SPEC R6.

---

### 20-12

**Summary.** Wait-for-state: Enter joins the service's single refresh flight via `_await_state`, repaints from the publication, starts only then; `esc` bumps a wait token that makes late publications inert; a failed refresh reports and retries.

**Strengths.**
- **The core mechanism is verified end-to-end, which is the highest-value check in this review.** The single flight is keyed by `frozenset(tool.id for tool in tools)` (`installer/version_status.py:1508`) and joins an in-flight pass at the current epoch (`:1510-1521`); the tier screens refresh `self._catalog`, which is the **whole catalog** — `CatalogScreen` is constructed with `catalog=list(tools)` per tier (`installer/wizard_app.py:2573-2577`) and the worker calls `service.refresh(self._catalog)` (`catalog_tui.py:423`). `ExecuteInputs.catalog` is likewise the full catalog (`_execute_inputs(tools, …)`). Same id-set key ⇒ the join works and no second pass starts. The design holds against the actual code, not just the research narrative.
- The worker shape mirrors an existing, working pattern: `_result, error = run_live(lambda: service.refresh(self._catalog))` at `catalog_tui.py:423` — `run_live`'s `(T | None, str | None)` return (`installer/ui_common.py:42`) matches the plan's `_result, error` unpacking.
- Token-guard-fails-closed matches the house epoch convention (`version_status.py:1499-1531` docstring: "never joins across an `invalidate`").
- `HeldRefreshService` fits the real double: `FrozenStateService` has `publish`/`refresh`/`refresh_skills` to override (`tests/state_doubles.py:137-150`).
- Unattended auto-start going through `action_start` (Pitfall 17) is the right single-entry fix, and the port of 20-10's frozen-service test to the held double is called out with its expected behavior change — honest test evolution.

**Concerns.**
- **LOW** — The `…  rg` two-space expectation inherits the UI-SPEC `:399` vs `:271` discrepancy (see 20-06/20-10).
- **LOW** — `exclusive=True, group="execute-wait"` allows a mount-time join and an Enter join to serialize but not overlap; the token is the real guard — the plan says this, correctly.

**Suggestions.** Align the pending-row copy with the anatomy form.

**Risk Assessment.** LOW — the one plan whose central claim (never a second pass) I could have imagined failing against the tree, and it doesn't.

---

### 20-13

**Summary.** The `r` key (the only path to a reinstall), the reworded `UNPROVEN_NOTE` pointing at it, and the 80×20 layout pins (status/keys on rows 18–19 at any plan size, 78-cell rows, Resize re-fold).

**Strengths.**
- All anchored facts verified: `UNPROVEN_NOTE = "not proven: reinstall with r to adopt"` at `installer/version_status.py:606`, the pin at `tests/test_version_status.py:4212`, the catalog `r` binding at `catalog_tui.py:322` (`accept_recommends`), and the new wording matches the UI-SPEC Copywriting row (`20-UI-SPEC.md:376`).
- `Pilot.resize_terminal` exists in installed textual 8.2.7 (`.venv/.../textual/pilot.py:86`) — the plan hedged on this; the hedge can be dropped.
- The eligibility rule (`can_reinstall` from the plan, one mutation site `self._reinstall ^= {tool_id}`) makes T-20-26 structural; the grep gate forbidding `.add/.discard/.update` on the set is a nice touch.
- The worst-case-head reasoning is correct: review-time has at most 7 disposition words; finished-time 13 outcome categories → `max-height: 3` covers both, per the UI-SPEC Layout contract (`20-UI-SPEC.md:82-97`).

**Concerns.**
- **LOW** — The layout pilots assert CSS-driven geometry (`get_widget_at(2, 18/19)`); these are the tests most likely to need a small iteration against real Textual rendering, but the UI-SPEC's measured baseline (`:57-70`) gives the executor accurate starting numbers, which lowers that risk substantially.

**Suggestions.** None material.

**Risk Assessment.** LOW — bounded screen work with pins for every behavior and a verified API surface.

---

### 20-14

**Summary.** Deletes the second copies now caller-less: `Summary`/`fold_run`/`run_installs`/`summarize`, `render_audit`/`render_summary`/`render_dependency_notice`, `reapply_post_install` — with grep gates proving nothing survives and a deleted-test → covering-test ledger.

**Strengths.**
- Deletion sequencing is correct against the tree: `render_dependency_notice`'s last production callers go in 20-10/20-11 (W6/W7); `render_summary`'s last production caller (`app.py:187`) goes in 20-11; this plan (W8) is safely after both.
- The word-anchoring analysis is **correct as stated**: `\brun_installs\b` does not match `test_run_installs_without_launching_when_no_run_set` (verified to exist at `tests/test_install_sh.py:211`; `_` is a word char, so no boundary before `run_installs`), and `\bSummary\(` does not match `ApplySummary(` (verified at `tests/test_agent_environment_e2e.py:62`). The gates do what the plan says they do.
- `tests/test_versions.py:129` does carry `(session_module, "run_installs")` inside `test_production_paths_select_the_real_release_resolver` (`:119`) — the plan's handling (drop the tuple, keep the pin meaningful for the remaining entries) is exactly right.
- `reapply_post_install` (`engine.py:300`) and `_dispatch_post_install` (`:287`) both exist; keeping the latter for `install_tool` is the correct split, and the `post_install.py:23-27` docstring paragraph exists verbatim as quoted.

**Concerns.**
- **LOW** — None of substance. The `install_summary`-era grep in Task 2's read-first list anticipates `installer/audit.py`/`selection.py` still referencing `ToolStatus` (they do — `selection.py:6`, `render.py:12`) and correctly defers their death to 20-15.

**Suggestions.** None.

**Risk Assessment.** LOW — deletion with grep proof and a per-test ledger; the phase's safest plan relative to its size.

---

### 20-15

**Summary.** Finishes the audit.py deletion cascade: `installer/audit.py`, `tool_choices`/`category_choices`, the `Prompter` checkbox methods, and `setup._ask_checkbox` — leaving headless with exactly one question.

**Strengths.**
- Every cited symbol verified: `audit.py` (36 lines, `ToolStatus` + `audit()`), `selection.py` `category_choices:33`/`_is_verified_download:55`/`tool_choices:59`, `prompt.py` (33 lines; `Prompter` with three methods; `CallbackPrompter(ask_checkbox, ask_confirm)`), `setup._ask_checkbox:309` and `CallbackPrompter(ask_checkbox=_ask_checkbox, ask_confirm=_ask_confirm):1515`.
- The production-unreachability of the two-step path is verified via `main`'s routing (see 20-11), so this is rule-5 deletion, not behavior change.
- `macos_stub_reason` (`installer/status.py:41`) has no production caller outside `audit.py` (grep-verified) — the plan's conditional deletion is correctly scoped.
- The FakePrompter trim is correctly coordinated with the protocol trim in the same commit so the tree is never red between them.

**Concerns.**
- **LOW** — `tests/test_app.py` contains a *second* class with `select_categories`/`select_tools` (`:1306`, `:1310`), not just `FakePrompter` at `:57`. The plan's verify gate (`! git grep -n -e "select_categories" …`) will catch it, but the action text only mentions `FakePrompter` — the executor should expect to trim both.

**Suggestions.** Mention the second fake explicitly so the trim isn't discovered only by the failing gate.

**Risk Assessment.** LOW.

---

### 20-16

**Summary.** Records Phase 20 in the architecture doctrine, rewrites the pre-Phase-20 paragraphs that describe deleted machinery, and pins both with `_PHASE_20_REQUIRED`.

**Strengths.**
- The doctrine's current state matches every claim: Phase 19 is the last section (`.claude/architecture.md:1026`), the Tier paragraph names `render_dependency_notice` at `:49`, Phase 3's `run_installs` sentences at `:103-110`, Phase 13's "`resolve_dependencies`, `audit`, `run_installs`" at `:655` and `attributed_install` at `:672`, Phase 14's "at the call into `run_installs`" at `:745`.
- The pin-file structure matches: `_PHASE_13_REQUIRED` (`tests/test_docs.py:51`), `_PHASE_14_REQUIRED` (`:85`), `_PHASE_19_REQUIRED` (`:188`), `_TRUNCATION_BANNER_FRAGMENTS` (`:6`) — the new section's test slots in cleanly.
- The chosen `_PHASE_20_REQUIRED` phrases include `(r: reinstall)` — which is correct as *doc* text even though 20-04 keeps it out of `session.py` (it's the renderer's hint), so the pin set is coherent.

**Concerns.**
- **LOW** — Task 2's gate greps pre-Phase-20 sections for deleted-machinery names and filters lines containing `deleted|Phase 20`. A rewritten sentence that describes the transition without using either filter word (e.g., "the old loop was folded into `execute_plan`") fails the gate even though the doc is fine. The executor must phrase rewrites with "deleted" (or the gate should drop the filter and assert absence outright).

**Suggestions.** Either instruct the rewrites to use the word "deleted" for removed machinery, or tighten the gate to plain absence and accept only the Phase 20 section's own deletion paragraph as the sanctioned mention.

**Risk Assessment.** LOW.

---

### 20-17

**Summary.** The mechanical `ExecuteInputs` contract change on its own, green alone: `version_refresh` required, `installed` deleted, `terminal_sync` added and wired; both screen-level test modules get input helpers with a published-state default.

**Strengths.**
- This is the best-grounded plan in the batch: `ExecuteInputs`' current fields verified exactly (`execute_screen.py:400-417`, `installed` at `:411`, `version_refresh | None` at `:415`), the four `self._inputs.installed(` sites verified at `:505/:544/:573/:583` and the four `self._inputs.version_refresh` reads at `:534/:538/:577/:757` — the plan's line claims are exact.
- `setup.py:1160-1166` really does wire `installed=version_refresh.is_present` today, so `_build_app` is already binding the very function the screen will read — the claim "behaviour is unchanged while the second source of truth is gone" is verified, not hoped.
- `VersionRefreshService.is_present` exists (`version_status.py:972`) with the CHECKING-aware semantics described.
- The port inventory is exact: `_inputs` at `tests/test_execute_screen.py:218` with an `installed=` parameter, 60 `installed=` sites, 22 `ExecuteInputs(` constructions in test_wizard_app (count verified = 22), 97 `ExecuteScreen(` constructions.
- Wave placement (W5) is right: it shares no file with 20-08/20-09 and lands before 20-10/20-12 need the default.

**Concerns.**
- **LOW** — None of substance. The `plan_state`/`receipt` gap noted under 20-04 slightly constrains this plan's `_inputs` default (which only needs OK/MISSING states — unaffected).

**Suggestions.** None.

**Risk Assessment.** LOW — exemplary decomposition: the contract change is isolated so the big screen rewrite (20-10) doesn't also carry a 60-site test port.

---

### 20-18

**Summary.** The four end-to-end acceptance pins through the real `UnifiedApp`: `a` on an all-current tier starts nothing, order parity with headless, the mixed-run retained selection, and D-05 (unavailable rows never selected).

**Strengths.**
- Correctly recognized that D-05 is already shipped by Phase 19 (`catalog_tui.py:375` `selectable=lambda tool: not self._is_unavailable(tool)`) and pins it against the plan rather than reimplementing — verified.
- The pins map directly to SPEC acceptance criteria 8/12 and edge ordering R9, and use the 20-17 helpers, so they're cheap to write once the screen is plan-driven.
- Wave-9 placement (after 20-12 W7 and 20-13 W8) is the right call given the shared files.

**Concerns.**
- **MEDIUM (metadata)** — The frontmatter says `depends_on: ["20-10"]` only, while the executor rules say "Runs after 20-10, 20-12 and 20-13 are committed" and the context block explains the wave-9 placement by file conflicts with 20-12 (`installer/execute_screen.py`, both test files) and 20-13 (same file + `version_status.py`). The wave assignment compensates today, but the dependency graph understates the real ordering constraint — any future re-waving or within-wave parallelization across waves would break the file isolation this plan silently relies on.

**Suggestions.** Add `20-12` and `20-13` to `depends_on` (or at least to a `conflicts_with` note) so the constraint survives tooling that trusts the frontmatter.

**Risk Assessment.** LOW — test-only plan (a screen fix only if a pin finds a gap), with the sequencing metadata caveat above.

---

### 20-19

**Summary.** Rewrites the container e2e parser for the `Summary — …` line and the outcome rows, in the same wave as the headless switch, with two sourced self-checks.

**Strengths.**
- The necessity is real and correctly scheduled: `SUMMARY_RE` at `scripts/container-e2e-verify.sh:242` parses the old `Installed: … Already: …` line that `render_summary` prints (`render.py:66-76`); once 20-11 (W7) switches headless to `render_run_summary`, the old regex matches nothing and `make e2e` would false-pass or misreport — both 20-11 and 20-19 are W7, no shared file, so the same-wave requirement is met structurally.
- The current cross-check internals are accurately described: blockers from `⚠ … skipped — dependency failed: …` lines (`:382`), manual names from the `  manual setup required: …` bucket line (`:383`, sourced from `render.py:84-87`), `dependency_failures_explained` at `:390-403`. The replacement sources (outcome rows rendered one per line under `COLUMNS=2000` at `:346`) are the right new provenance.
- The self-checks source the real functions rather than reimplementing them, and the old-line non-match assertion (`! parse_summary_line "Installed: 2  Already: 0"`) pins the retirement.
- The "do not rename `write_tester_path`" constraint is verified: `tests/test_shell_scripts_path.py:54-87` and `tests/test_container_e2e_receipts.py:265-284` extract that function by name; neither references `SUMMARY_RE`/`ACC_*`.

**Concerns.**
- **LOW** — Name overloading: the script already has `ACC_SKIPPED_FILE` (the dependency-failed lines accumulator, `:382`, `:419`); the plan adds a *counter* named `ACC_SKIPPED` and also keeps `ACC_MANUAL_NAMES_FILE`. Two near-identical names for different things invites a wrong-variable bug inside a shell script that CI depends on.
- **LOW** — The sed extraction uses GNU `\b` word boundaries; fine for the Linux containers (Fedora/Debian/Arch per ONB-04) and the Linux host, but worth knowing it's a GNU-ism if the script ever runs under BSD sed.

**Suggestions.** Rename the lines file (e.g. `ACC_DEP_LINES_FILE`) in the same commit so `ACC_SKIPPED` the counter is unambiguous.

**Risk Assessment.** LOW.

---

### Cross-plan comparison

**Wave and file topology (verified).** Waves are file-disjoint: W1 (20-01 deps, 20-02 update/catalog_tui, 20-03 setup) ∅; W3 (20-05 session, 20-06 render/version_status/catalog_tui) ∅; W5 (20-08 session/test_session, 20-09 render, 20-17 execute_screen/setup) ∅; W7 (20-11 app/setup/test_app/test_setup, 20-12 execute_screen/state_doubles, 20-19 the script) ∅; W8 (20-13 execute_screen/version_status, 20-14 session/render/engine/post_install) ∅; W9 (20-15 audit/selection/prompt/setup, 20-18 execute_screen/tests) ∅. Every `depends_on` edge points backwards across waves. The two metadata weak spots are 20-18 (missing 20-12/20-13) and 20-19 (same-wave coupling with 20-11 expressed only in prose — correctly, since there's no file dependency, but the co-wave requirement should be stated in 20-11 too).

**Shared vocabulary coherence (verified).** `WORDS`/`RESULT_WORDS` (20-04), the review words in `render_plan` (20-06), the outcome words in `render_run_summary` (20-09), the `Summary —` line the parser reads (20-19), and the `summary_counts` order (20-07) all match one another and the UI-SPEC Words/Summary-counts tables. `review_counts` (review words) and `summary_counts` (done/result words) are two views of one table — PLAN-04 holds by construction.

**Exit-code parity (verified).** Today `Summary.has_failure` excludes `manual_required`/`no_method` (`session.py:120-126`); 20-07's mapping (`MANUAL_REQUIRED → manual`, `NO_METHOD → blocked`, both outside `_FAILURE`) plus L-20-08's run-error OR preserves every existing exit behavior while unifying the rule. The four non-install `_session_exit_code` callers survive via the `outcomes is None → 0` rule (20-10).

**The one systemic defect: false-failing word-literal gates (20-06 Task 1, 20-09 Task 2).** Both gates assert zero legacy word literals in `installer/render.py` at a time when `render_audit`/`render_summary` — deleted only in 20-14 (W8) — still contain `"installed"` (`render.py:57`, `:78`) and `"failed"` (`:80`). The verify commands don't include these greps (they live in acceptance_criteria), but a plan-executor or checker honoring acceptance criteria will hit a gate that cannot pass, and the most tempting "fix" (deleting the old renderers early) would break live callers (`app.py:166/187` until 20-11, W7). Fix: scope both gates to the new renderer bodies, or move them into 20-14.

**The one copy inconsistency.** The pending-row rendering is written three ways across the contract documents: the anatomy (`… {id}`, `20-UI-SPEC.md:102` and `:271`), the UI-considerations row (`…  {id}`, `:399`), and the pilot expectations in 20-10/20-12 (`…  rg`). 20-06 implements the anatomy; the 20-10/20-12 tests expect the two-space form. Decide once (the anatomy is the defensible canonical form) and align the two plans' test expectations.

**Minor fixture gaps that will surface as immediate test failures (not design risks).** `VersionStatus(...)` snippets missing the required `tool_id` field (20-04, 20-05); `plan_state`'s `receipt` and `method` passthroughs unsupported by `pass_state` as specified (20-04/20-05).

---

### Overall summary

**Verdict: the plan set is execution-ready with small, targeted fixes.** This is an unusually well-grounded batch: I verified the resolver's actual behavior (`deps.py:111` dropping present tools), the single-flight join key and the whole-catalog refresh that makes 20-12's core mechanism real, `main`'s routing that makes 20-15's deletions dead code, the Textual API surface 20-10/20-13 bet on, the exact test counts the port floors assume, and ~60 line references — and the plans told the truth in essentially all of them. The wave topology is sound, the deletions are staged with grep proof and scheduled after their last callers die, and the phase goal (one plan, one engine, one vocabulary, one exit rule, retained selection, wait-for-state, zero sudo, no migration promise) is achieved by construction rather than by assertion.

**No HIGH concerns.** The six findings that need action before or during execution:

1. **20-06/20-09 — false-failing acceptance gates** (MEDIUM): scope the word-literal greps to the new renderers or move them to 20-14.
2. **20-03 — second `node_install_policy` object vs the same-object invariant comment at `setup.py:1060-1062`** (MEDIUM): return the policy from `_build_services` or reword the invariant.
3. **20-10 — stale Task-1 acceptance bullet (`make validate && make test` exit 0) contradicting the deliberate one-commit Tasks 1+2 design** (MEDIUM): reword to "at the combined commit".
4. **Pending-row copy (`… {id}` vs `…  {id}`) across UI-SPEC and plans 20-06/20-10/20-12** (LOW-MEDIUM): pick the anatomy form.
5. **20-18 — `depends_on` missing 20-12/20-13** (MEDIUM metadata / LOW risk): add them.
6. **Fixture gaps** (LOW): `VersionStatus` `tool_id`, `plan_state` `receipt`/`method` passthroughs, 20-15's second fake prompter at `tests/test_app.py:1306`.

**Risk by plan:** LOW — 20-01, 20-02, 20-04, 20-05, 20-07, 20-08, 20-11, 20-12, 20-13, 20-14, 20-15, 20-16, 20-17, 20-19. MEDIUM — 20-03 (invariant, cheap fix), 20-06 and 20-09 (gate-only), 20-10 (blast radius; mechanisms all verified present).

**What I did not check:** I did not run the test suite (`make validate && make test`) or any pilot — all findings are static verification against the tree; the layout pins in 20-13 and the `is_installed`-vs-`settled` interplay in `run_installs` porting were reviewed by reading, not execution. I did not verify `node_install_policy`'s internal purity beyond its signature (`installer/pnpm_globals.py:229`), which is the one assumption behind 20-03's risk rating, nor the exact current body of `execute_screen._with_repair` (`:240-277`) beyond its location, which 20-07 moves verbatim.

---

### Consensus Summary

Single reviewer (opencode-plan-review, source-grounded: cites file:line throughout), so no cross-reviewer consensus is possible. Reviewer verdict: plan set is execution-ready; no HIGH concerns.

### Agreed Strengths
- (single reviewer) Line references, test counts and API bets (Textual `replace_option_prompt`, `Pilot.resize_terminal`, single-flight join key at `installer/version_status.py:1508`) verified against the tree.

### Agreed Concerns
- n/a (one reviewer). Unresolved non-HIGH items, none yet reflected in the PLAN.md files: 20-06/20-09 acceptance gates that cannot pass before 20-14; 20-03 second `node_install_policy` object vs the same-object invariant at `setup.py:1060-1062`; 20-10 stale Task-1 `make validate && make test` bullet; pending-row copy (`… {id}` vs `…  {id}`) across 20-06/20-10/20-12; 20-18 `depends_on` missing 20-12/20-13; fixture gaps (`VersionStatus` missing `tool_id` in 20-04/20-05, `plan_state` receipt/method passthrough, second fake prompter at `tests/test_app.py:1306` for 20-15).

### Divergent Views
- None.

### Verification coverage

Source-grounding pass (`plan_review.source_grounding`, effective authority `intel`, via `drift-guard authority`):
- VERIFIED: all 25 distinct `installer/*.py` paths cited by the plans exist; all other cited repo paths (docs, scripts, `setup.py`, existing `tests/*`) exist.
- New artifact, not a reference: `tests/test_plan.py` (created by 20-04); excluded per the artifacts rule.
- Reviewer additionally verified ~60 line/symbol references against the tree (see body).
- UNCHECKABLE: individual Python symbols and signatures (functions, dataclass fields, methods) — the `intel` adapter does not analyze Python and `grep` cannot assert signatures; coverage for these rests on the reviewer's manual reads only, not an adapter verdict.
- Not executed: `make validate`, `make test`, pilots.

Cross-artifact fact-drift pass:
- Phase status (deterministic): verdict `lag` (STATE.md "Ready to execute" vs ROADMAP "Not started") — not a finding.
- Success criteria / requirement IDs: ROADMAP PLAN-01..PLAN-08; every `requirements:` entry in the 19 plans is within that set; no contradiction found.
- Glossary (CONTEXT.md decisions vs plan usage): no contradiction found beyond the reviewer's pending-row copy inconsistency, which is a UI-SPEC internal discrepancy, not a CONTEXT/PLAN contradiction.
- Advisory only; contributes to neither HIGH nor actionable counts.
