---
phase: 20-install-plan-with-dispositions
plan: "14"
subsystem: installer
tags: [python, install-plan, rendering, session]

# Dependency graph
requires:
  - phase: 20-install-plan-with-dispositions
    provides: "Plans 20-10 and 20-11: the shared plan model, execution path, and render vocabulary"
provides:
  - "Removed legacy renderer functions and the duplicate install-session engine"
  - "Removed the standalone post-install reapply path"
affects: [phase-20, installer-session, installer-rendering, post-install]

# Actuals
actuals:
  tokens: 14185
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One execution engine: execute_plan owns plan-row install behavior."
    - "One result vocabulary: renderers consume plan outcomes instead of parallel summary models."

key-files:
  created:
    - .planning/phases/20-install-plan-with-dispositions/20-14-SUMMARY.md
  modified:
    - installer/render.py
    - installer/session.py
    - installer/engine.py
    - installer/post_install.py
    - tests/test_render.py
    - tests/test_audit.py
    - tests/test_session.py
    - tests/test_versions.py
    - tests/test_engine.py
    - tests/test_post_install.py

key-decisions:
  - "PLAN-04: retain one review/run vocabulary and remove legacy renderers and summary aggregation."
  - "D-08 and D-12: delete superseded install/render paths after their callers are removed."
  - "D-06: a post-install action runs only after a successful install; reinstall uses the normal install ladder."
  - "Keep _UNRESOLVED, _PRIORITY_RANK, and _dispatch_post_install because the remaining plan engine and install ladder use them."

patterns-established:
  - "Plan behavior tests target execute_plan and RunContext, not the retired run_installs API."

requirements-completed: [PLAN-04]

coverage:
  - id: D1
    description: "Legacy rendering and session paths are removed; plan outcomes and their shared vocabulary remain the only path."
    requirement: PLAN-04
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_session.py tests/test_plan.py tests/test_versions.py tests/test_render.py -n auto -q --no-cov"
        status: pass
      - kind: unit
        ref: "uv run pytest tests/test_engine.py tests/test_post_install.py tests/test_session.py -n auto -q --no-cov"
        status: pass
      - kind: other
        ref: "git grep checks for deleted renderer/session/reapply symbols; no matches after deletion"
        status: pass
    human_judgment: false

duration: 37min
completed: 2026-10-18
status: complete
---

# Phase 20 Plan 14 Summary

**The plan engine and its vocabulary are now the only install-session path; obsolete renderers and standalone post-install reapplication are gone.**

## Performance

- **Duration:** About 37 minutes, using the first task-brief timestamp; the exact start time was not recorded.
- **Started:** 2026-10-18T03:11:00-03:00 (approximate; task brief created at this time)
- **Completed:** 2026-10-18T03:47:23-03:00
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Removed `render_audit`, `render_summary`, and `render_dependency_notice`, along with their obsolete tests and references.
- Removed `Summary`, `fold_run`, `run_installs`, and `summarize`; retained `Install`, `SensitiveInstall`, `with_sensitive_confirm`, `order_for_install`, `_PRIORITY_RANK`, and `_UNRESOLVED` for the plan engine.
- Removed `reapply_post_install`; `_dispatch_post_install` remains on the successful install path, and the module docstring now documents SKIP/REINSTALL behavior under D-06.
- Migrated relevant tests to `execute_plan`, including context injection, mismatch handling, dependency propagation, cancellation, and sensitive confirmation.
- Preserved the pre-existing modified `.planning/config.json`; it was never staged or changed by this plan.

## Task Commits

Each task was committed separately:

1. **Task 1: delete legacy plan renderers** — `19f9737` (`refactor(20-14): delete legacy plan renderers`)
2. **Task 2: delete the legacy Summary vocabulary and `run_installs`** — `30dc20a` (`refactor(20-14): delete the legacy Summary vocabulary and run_installs`)
3. **Task 3: delete `reapply_post_install`** — `41248f0` (`refactor(20-14): delete reapply_post_install; reconfigure runs typed steps`)

**Plan metadata:** This summary is the final documentation artifact. No orchestrator-owned planning metadata was changed.

## Files Created or Modified

- `installer/render.py` — removed the audit table, legacy summary, and dependency notice renderers; updated docs and imports.
- `installer/session.py` — removed the duplicate summary type, fold, installer loop, and bucketing function.
- `installer/engine.py` — removed the standalone post-install reapply function and its documentation reference.
- `installer/post_install.py` — documented that an already-present tool is skipped and `r` routes a reinstall through the install ladder.
- `tests/test_render.py`, `tests/test_audit.py` — deleted superseded output assertions while retaining audit-model coverage.
- `tests/test_session.py` — removed legacy API tests, migrated confirmation tests, and added `execute_plan` coverage where no equivalent existed.
- `tests/test_versions.py` — removed the resolver-default inspection of the deleted `run_installs` function.
- `tests/test_engine.py`, `tests/test_post_install.py` — removed reapply-specific tests and updated the D-06 docstring assertion.

## Verification Results

| Task | Targeted tests | `make validate` | Full suite | Additional gates |
|---|---|---|---|---|
| 1 | `uv run pytest tests/test_render.py -n auto -q --no-cov` passed. | Passed. | `make test` passed; the exact count was not retained in the task log. | Removed exactly nine legacy renderer tests from an 80-test-definition baseline; 71 definitions remained. The remaining quoted `failed`/`crashed` values are internal `RowOutcome.result` discriminators, not visible vocabulary. |
| 2 | `uv run pytest tests/test_session.py tests/test_plan.py tests/test_versions.py tests/test_render.py -n auto -q --no-cov` passed. | Passed. | 4,848 passed, 4 skipped; 96.02% coverage. | Both required symbol/type greps returned no matches; suppression count decreased from 484 to 483; `tests/test_session.py` retained 49 test definitions (gate: at least 40). |
| 3 | `uv run pytest tests/test_engine.py tests/test_post_install.py tests/test_session.py -n auto -q --no-cov` passed. | Passed. | 4,846 passed, 4 skipped; 96.02% coverage. | `reapply_post_install` grep returned no matches; definition count 0; `_dispatch_post_install` definition count 1. |

The final Task 3 tree passed `make validate && make test`. The checks ran on `main`; no branch switch, remote operation, privileged command, install, or user-configuration write occurred.

## Deleted Test Coverage Mapping

### Task 1: renderer tests

| Deleted test | Replacement or reason |
|---|---|
| `test_render_audit_lists_each_tool_and_its_state` | The report renderer was deleted; audit-model assertions remain in `tests/test_audit.py`. |
| `test_render_summary_reports_counts_and_ids`, `test_render_summary_handles_empty`, `test_render_summary_still_reports_zero_when_nothing_was_skipped` | `test_render_run_summary_mixed_run_counts_every_category`, `test_render_run_summary_first_line_is_the_summary_head`, and `test_summary_head_is_the_same_line_the_renderer_prints` cover the run-summary renderer. |
| `test_render_summary_counts_and_lists_dependency_failed`, `test_render_summary_counts_and_lists_manual_required`, `test_render_summary_includes_mismatch_bucket` | `test_outcome_row_text_per_result` and `test_render_run_summary_mixed_run_counts_every_category` cover plan-result presentation. |
| `test_render_dependency_notice_shows_dragged_in_and_warnings`, `test_render_dependency_notice_silent_when_nothing_to_say` | `test_render_plan_groups_dragged_rows_under_their_first_requester`, `test_render_plan_keeps_a_dragged_row_under_a_blocked_requester`, and `test_render_plan_lists_a_chain_once_at_one_indent_level` cover dependency visibility in the plan. |

### Task 2: `tests/test_session.py`

| Deleted or renamed legacy test | `execute_plan` coverage |
|---|---|
| `test_run_installs_calls_install_per_tool_with_injected_deps` | `test_execute_plan_passes_run_context_dependencies_to_install` |
| `test_summarize_buckets_by_status`, `test_summarize_buckets_manual_required`, `test_summarize_buckets_checksum_mismatch`, `test_summarize_buckets_dependency_failed` | `test_every_install_status_maps_to_one_result` and `test_summary_counts_fixed_order_and_nothing_selected` |
| `test_summarize_empty_is_all_empty`, `test_summarize_over_truncated_outcomes_still_buckets` | `test_summary_counts_fixed_order_and_nothing_selected` and `test_execute_plan_returns_one_outcome_per_row_in_plan_order` |
| `test_on_mismatch_retry_reinstalls_with_default_policy`, `test_on_mismatch_fallback_reinstalls_with_continue_policy`, `test_on_mismatch_skip_keeps_the_mismatch_outcome` | Renamed and expanded as `test_execute_plan_mismatch_retry_skip_and_fallback`. |
| `test_without_on_mismatch_the_outcome_stands` | `test_every_install_status_maps_to_one_result` exercises checksum-mismatch without a callback. |
| `test_on_mismatch_is_not_consulted_for_clean_installs` | `test_execute_plan_does_not_prompt_for_a_clean_install` |
| `test_dependent_is_skipped_when_its_dependency_failed`, `test_dependency_failure_propagates_down_a_chain`, `test_install_failure_blocks_dependents_down_a_chain` | Expanded as `test_install_failure_blocks_dependents_but_not_unrelated_rows`. |
| `test_every_unresolved_status_blocks_a_dependent`, `test_manual_and_no_method_statuses_still_block_dependents` | Parameterized as `test_every_unresolved_install_status_blocks_dependents`. |
| `test_successful_statuses_never_block_a_dependent` | `test_successful_install_statuses_do_not_block_dependents` |
| `test_an_unrelated_tool_still_installs_after_a_failure` | Covered by the expanded `test_install_failure_blocks_dependents_but_not_unrelated_rows`. |
| `test_only_the_matching_requires_ids_are_reported_as_blockers` | `test_execute_plan_reports_only_failed_unique_dependencies` |
| `test_a_retried_mismatch_does_not_block_its_dependents`, `test_mismatch_retry_skip_and_fallback_match_run_installs` | Renamed and expanded as `test_execute_plan_mismatch_retry_skip_and_fallback`; it checks the dependent row and catalog identity across retries/fallback. |
| `test_a_dependent_listed_before_its_dependency_is_still_attempted` | `test_execute_plan_does_not_reorder_rows_to_satisfy_dependencies` |
| `test_run_installs_threads_catalog_into_every_install_call`, `test_run_installs_catalog_defaults_to_none_for_untouched_callers` | `test_execute_plan_passes_run_context_dependencies_to_install`; the mismatch test checks catalog identity at retry/fallback call sites. A nullable catalog default no longer applies because `RunContext` owns the catalog. |
| `test_run_installs_preexisting_parameters_stay_positional` | Ported as `test_execute_plan_rows_and_context_remain_positional`. |
| `test_run_installs_should_continue_stops_between_tools` | `test_should_continue_false_marks_the_rest_not_attempted` |
| `test_run_installs_should_continue_is_checked_before_dependency_blocked` | Ported as `test_should_continue_is_checked_before_dependency_blocking`. |
| `test_summary_has_failure` | `test_exit_code_retained_and_ran_anything_are_pure_views_of_the_list` and `test_blocked_plus_done_exits_zero_and_failed_exits_one` |
| `test_fold_run_records_not_attempted_update_failures_and_crash` | `test_a_crashing_row_is_crashed_and_the_rest_not_attempted`, `test_should_continue_false_marks_the_rest_not_attempted`, and `test_update_failure_does_not_block_a_dependent` cover row-level outcomes. |
| `test_fold_run_drops_duplicate_update_failure_ids` | No direct `execute_plan` analogue: the removed aggregate fold no longer combines update-error lists into a `Summary`; update outcomes remain per row and exit status is tested through `exit_code`. |

`_mismatch_then_install` and `_failing_install` were obsolete test helpers and were removed. `test_install_protocol_parameters_are_unchanged`, `test_order_for_install_sorts_by_priority_then_keeps_catalog_order`, and `test_tool_rejects_unknown_priority` remain.

### Task 3: standalone post-install reapply tests

| Deleted test | Replacement or reason |
|---|---|
| `test_reapply_post_install_returns_handoff_without_installing` | No standalone reapply path remains by D-06. Normal install dispatch and confirmation stay covered by `test_repair_dispatches_post_install_like_a_fresh_install` and the `execute_plan` sensitive-confirmation tests. |
| `test_reapply_post_install_isolates_a_raising_action` | `test_raising_confirm_degrades_to_named_warning_not_a_crash` covers isolation on the surviving install path. Typed reconfiguration remains covered by the 20-08 `execute_plan` tests. |

## Pre-Deletion Symbol Checks

Task 1, at base `007db0c` (the grep showed only the listed renderer, model, selection, and test files):

```text
007db0c:installer/audit.py:11:class ToolStatus:
007db0c:installer/audit.py:21:) -> list[ToolStatus]:
007db0c:installer/audit.py:31:    statuses: list[ToolStatus] = []
007db0c:installer/audit.py:35:        statuses.append(ToolStatus(tool=tool, installed=installed, reason=reason))
007db0c:installer/render.py:13:from installer.audit import ToolStatus
007db0c:installer/render.py:45:def render_dependency_notice(
007db0c:installer/render.py:60:def render_audit(statuses: list[ToolStatus], console: Console) -> None:
007db0c:installer/render.py:77:def render_summary(summary: Summary, console: Console) -> None:
007db0c:installer/render.py:312:    render_summary only counts and names failed tools; this is where the
007db0c:installer/render.py:333:    matching render_dependency_notice). Counts live in render_summary;
007db0c:installer/render.py:361:    render_summary only counts and names these tools ("Manual setup
007db0c:installer/selection.py:6:from installer.audit import ToolStatus
007db0c:installer/selection.py:59:def tool_choices(statuses: list[ToolStatus]) -> list[Choice]:
007db0c:tests/test_audit.py:5:from installer.audit import ToolStatus, audit
007db0c:tests/test_audit.py:7:from installer.render import render_audit
007db0c:tests/test_audit.py:29:        ToolStatus(tool=tools[0], installed=True),
007db0c:tests/test_audit.py:30:        ToolStatus(tool=tools[1], installed=False),
007db0c:tests/test_audit.py:41:    assert result == [ToolStatus(tool=tool, installed=False, reason="reason text")]
007db0c:tests/test_audit.py:44:    render_audit(result, console)
007db0c:tests/test_audit.py:66:    assert result == [ToolStatus(tool=tool, installed=False, reason=None)]
007db0c:tests/test_audit.py:69:    render_audit(result, console)
007db0c:tests/test_render.py:10:from installer.audit import ToolStatus
007db0c:tests/test_render.py:18:    render_audit,
007db0c:tests/test_render.py:19:    render_dependency_notice,
007db0c:tests/test_render.py:30:    render_summary,
007db0c:tests/test_render.py:56:def test_render_audit_lists_each_tool_and_its_state() -> None:
007db0c:tests/test_render.py:58:        ToolStatus(tool=_tool("rg"), installed=True),
007db0c:tests/test_render.py:59:        ToolStatus(tool=_tool("fd"), installed=False),
007db0c:tests/test_render.py:62:    render_audit(statuses, console)
007db0c:tests/test_render.py:68:def test_render_summary_reports_counts_and_ids() -> None:
007db0c:tests/test_render.py:71:    render_summary(summary, console)
007db0c:tests/test_render.py:77:def test_render_summary_handles_empty() -> None:
007db0c:tests/test_render.py:79:    render_summary(Summary(installed=(), already=(), failed=(), no_method=()), console)
007db0c:tests/test_render.py:84:def test_render_summary_counts_and_lists_dependency_failed() -> None:
007db0c:tests/test_render.py:93:    render_summary(summary, console)
007db0c:tests/test_render.py:101:def test_render_summary_counts_and_lists_manual_required() -> None:
007db0c:tests/test_render.py:110:    render_summary(summary, console)
007db0c:tests/test_render.py:116:def test_render_summary_still_reports_zero_when_nothing_was_skipped() -> None:
007db0c:tests/test_render.py:118:    render_summary(Summary(installed=(), already=(), failed=(), no_method=()), console)
007db0c:tests/test_render.py:390:def test_render_summary_includes_mismatch_bucket():
007db0c:tests/test_render.py:393:    render_summary(summary, console)
007db0c:tests/test_render.py:514:def test_render_dependency_notice_shows_dragged_in_and_warnings() -> None:
007db0c:tests/test_render.py:516:    render_dependency_notice(
007db0c:tests/test_render.py:524:def test_render_dependency_notice_silent_when_nothing_to_say() -> None:
007db0c:tests/test_render.py:526:    render_dependency_notice((), (), console)
007db0c:tests/test_selection.py:1:from installer.audit import ToolStatus
007db0c:tests/test_selection.py:65:        ToolStatus(tool=tools[0], installed=True),
007db0c:tests/test_selection.py:66:        ToolStatus(tool=tools[1], installed=False),
007db0c:tests/test_selection.py:90:    statuses = [ToolStatus(tool=verified, installed=False)]
```

Task 2, at base `19f9737`. The first grep showed only `installer/session.py`, `tests/test_session.py`, and `tests/test_versions.py`; the second showed no annotation outside `installer/session.py`:

```text
installer/session.py:128:class Summary:
installer/session.py:158:def fold_run(
installer/session.py:189:def run_installs(
installer/session.py:211:    dependency is always visited before anything requiring it. run_installs
installer/session.py:220:    reaches the full loaded catalog without run_installs needing to know
installer/session.py:259:def summarize(outcomes: list[InstallOutcome]) -> Summary:
installer/session.py:277:    return Summary(
tests/test_session.py:39:    fold_run,
tests/test_session.py:43:    run_installs,
tests/test_session.py:684:    outcomes = run_installs(tools, platform, runner, resolve_tag, fake_install)
tests/test_session.py:697:    assert summarize(outcomes) == Summary(
tests/test_session.py:706:    assert summarize([]) == Summary(installed=(), already=(), failed=(), no_method=())
tests/test_session.py:719:    summary = summarize(outcomes)
tests/test_session.py:751:    outcomes = run_installs(
tests/test_session.py:764:    outcomes = run_installs(
tests/test_session.py:777:    outcomes = run_installs(
tests/test_session.py:786:    outcomes = run_installs(
tests/test_session.py:811:    run_installs(
tests/test_session.py:822:    summary = summarize(outcomes)
tests/test_session.py:842:    outcomes = run_installs(
tests/test_session.py:862:    summary = summarize(outcomes)
tests/test_session.py:889:    outcomes = run_installs(
tests/test_session.py:908:    outcomes = run_installs(
tests/test_session.py:936:    outcomes = run_installs(
tests/test_session.py:951:    outcomes = run_installs(
tests/test_session.py:965:    outcomes = run_installs(
tests/test_session.py:976:    outcomes_dup = run_installs(
tests/test_session.py:993:    outcomes = run_installs(
tests/test_session.py:1009:    outcomes = run_installs(
tests/test_session.py:1049:    outcomes = run_installs(
tests/test_session.py:1079:    run_installs([_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install)
tests/test_session.py:1084:    params = inspect.signature(run_installs).parameters
tests/test_session.py:1123:    outcomes = run_installs(
tests/test_session.py:1157:    outcomes = run_installs(
tests/test_session.py:1172:    summary = summarize(
tests/test_session.py:1222:    yes_outcomes = run_installs([tool], platform, lambda cmd: None, lambda repo: "1.0.0", yes)
tests/test_session.py:1223:    no_outcomes = run_installs([tool], platform, lambda cmd: None, lambda repo: "1.0.0", no)
tests/test_session.py:1249:    run_installs(
tests/test_session.py:1277:    outcomes = run_installs(
tests/test_session.py:1315:    summary = replace(Summary(installed=(), already=(), failed=(), no_method=()), **kwargs)  # pyright: ignore[reportArgumentType]
tests/test_session.py:1321:    summary = Summary(installed=("a",), already=(), failed=(), no_method=())
tests/test_session.py:1322:    folded = fold_run(
tests/test_session.py:1343:    summary = Summary(installed=(), already=(), failed=(), no_method=())
tests/test_session.py:1344:    folded = fold_run(
tests/test_versions.py:129:        (session_module, "run_installs"),
```

Task 2 annotation grep:

```text
installer/session.py:159:    summary: Summary,
installer/session.py:165:) -> Summary:
installer/session.py:259:def summarize(outcomes: list[InstallOutcome]) -> Summary:
```

Task 3, at base `30dc20a`:

```text
installer/engine.py:169:    dispatches postinstall or post_install at all. `reapply_post_install` is
installer/engine.py:300:def reapply_post_install(
installer/post_install.py:25:`engine.reapply_post_install`; drag-ins and plain re-runs still never reach
tests/test_engine.py:1071:def test_reapply_post_install_returns_handoff_without_installing(
tests/test_engine.py:1075:    outcome = engine.reapply_post_install(_shelltool(), _platform(), confirm=_confirm(True))
tests/test_engine.py:1079:    declined = engine.reapply_post_install(_shelltool(), _platform(), confirm=_confirm(False))
tests/test_engine.py:1083:def test_reapply_post_install_isolates_a_raising_action(
tests/test_engine.py:1090:    outcome = engine.reapply_post_install(_shelltool(), _platform(), confirm=_confirm(True))
tests/test_post_install.py:203:    assert "reapply_post_install" in text
```

All three tasks passed their post-deletion symbol checks. In particular, Task 2's legacy-symbol and deleted-`Summary` greps, and Task 3's `reapply_post_install` grep, returned no matches.

## Deviations from Plan

1. **Adjusted Task 1's test-count gate.** The plan required at least 95 test definitions in `tests/test_render.py`, but the pre-task tree had 80. The task removed its nine obsolete renderer tests, leaving 71. Verification used the baseline-minus-nine count and reviewed the exact deleted names rather than adding unrelated tests.
2. **Updated `tests/test_audit.py` beyond Task 1's file list.** It imported and asserted the deleted `render_audit`; those assertions were removed while the audit model checks remained. This prevented a stale import and preserved the report's model coverage.
3. **Used the embedded task briefs manually.** The task-start helper only recognizes Markdown `## Task N` headings and could not parse this plan's XML `<task><name>Task N</name>` structure. The exact briefs were followed, and `task-done` recorded all three passing task gates.

The Task 2 test port also added `execute_plan` coverage where the old suite had no equivalent: positional parameters, RunContext dependency/catalog injection, unique dependency blockers, row order, clean-install mismatch prompting, and cancellation before dependency blocking. No implementation behavior changed.

## Issues Encountered

- The expanded mismatch test added a dependent row, so successful retry/fallback correctly produced one additional install call. The fixture expectations were updated; all cases passed.
- Ruff and Pyright flagged style and protocol-parameter issues in the new test. Named functions and the `SensitiveInstall` parameter names fixed them without suppressions.
- Task 3's docstring assertion initially crossed a source line break. Normalizing whitespace fixed the assertion; an unused test import and a trailing EOF blank line were also removed.

The commit hook temporarily stashed and restored the unrelated `.planning/config.json` diff under `$HOME/.cache/pre-commit`. The config diff remains unchanged and unstaged; no user configuration or installation artifacts were written to the real home.

All issues were resolved before the task commits. The final quality gate passed on the Task 3 tree.

## User Setup Required

None.

## Outstanding Issues and Next Phase Readiness

None. The Phase 20 shared plan engine, vocabulary, renderer, and post-install dispatch path remain the supported implementation. `.planning/config.json` remains in its pre-existing modified state and was not staged.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
