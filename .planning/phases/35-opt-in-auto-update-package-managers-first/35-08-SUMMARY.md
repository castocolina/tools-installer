# Phase 35 Plan 08 Summary

The plan ran as themed pi runs (one per task); the text below is the executors' own final notes.

## Task 1 (`87d62f9b`)

**Commit:** `87d62f9b` — describe the update-all preview, log and limits on the Schedules screen.

The update-all detail now includes the preview command, log and notification information, and update limits. Tests cover both platforms, rendered visibility at 80×20, an unavailable row, and clearing a four-row status.

## Test output

**RED:** The new detail test failed on Fedora and macOS because `last: never` appeared where the preview was expected.

```text
FAILED ...test_the_update_all_detail_names_the_preview_the_log_and_the_limits[fedora]
FAILED ...test_the_update_all_detail_names_the_preview_the_log_and_the_limits[macos]
```

**GREEN:** The task’s automated command passed; the additional affected-test run also passed.

```text
uv run pytest tests/test_schedules_view.py tests/test_layout_80x20.py tests/test_update_all_row.py -n auto -q --no-cov
........................................................................ [ 96%]
.....                                                                    [100%]
```

The commit hook passed all six static gates. An additional test run initially caught the 800-line module limit; after removing a blank line, the affected tests passed. All scratch run directories were removed by their traps; pytest used the default TMPDIR as instructed.

## Existing-test edits and deviations

- Adjusted the existing update-all detail test’s digit exclusion to permit the preview command’s `setup.py`; its other assertions remain intact.
- All named Task 1 scenarios have assertions. No requested test was omitted.
- Ran `ruff format` directly while preparing the change; this was unnecessary under the instruction not to run static gates by hand.
- The unrelated untracked goals file remains untouched.

## Decisions

- **35 D-04 (locked):** Changed only update-all row text, not the view mechanism.
- **35 D-05 and D-09 (own reasoning, needs confirmation):** The eight-tool breadth and dedicated mechanisms remain for the documentation task.
- **Orchestrator decisions 1, 2, 3, 4, 7, 8 and 9 (provisional, needs confirmation):** Dated amendments remain for Task 2; decision 9’s container target remains for plan 35-09.
- **Review H1 and H2 (round 2, provisional, needs confirmation):** Tested the complete rendered preview and record-health qualification; the shared document wording remains for Task 2.
- **Orchestrator decision 10:** Added no timing-sensitive assertions; the docs test remains for Task 2.
- **Review M8 and round 1 decisions of plans 35-02 to 35-07 (provisional, needs confirmation):** The preview is second and copyable; remaining documentation amendments are deferred to Task 2.

## Task 2 (`76639ac9`)

**Commit:** `76639ac9` — `docs(35-08): record Phase 35's mechanisms, limits and dated amendments`

Added the Phase 35 architecture subsection and its phrase-pinning test, and recorded dated amendments in the SPEC, ROADMAP, and REQUIREMENTS.

## Verification

- **RED:** `test_architecture_records_phase_35_mechanisms` failed as expected: `missing load-bearing phrase: ## Phase 35: opt-in auto-update`.
- **GREEN:** `uv run pytest tests/test_docs.py tests/test_docs_only.py tests/test_update_check_contract.py -n auto -q --no-cov` exited 0; output ended at `[100%]`.
- The commit hook passed all six static gates.
- No existing test assertions were edited. The task’s named test was written and run.
- Each run directory was removed by its exit trap.

## Decisions

- **35 D-04 — locked:** No new view mechanism; the text change is confined to the update-all row.
- **35 D-05 and D-09 — own reasoning, needs confirmation:** Recorded the eight-tool no-update-path breadth and the associated mechanisms.
- **Orchestrator decisions 1, 2, 3, 4, 7, 8 and 9 — provisional, need confirmation:** Recorded as dated amendments. The dedicated container target is orchestrator-run only and belongs to plan 35-09.
- **Review H1 and H2 — provisional, need confirmation:** The complete preview command is asserted on the rendered 80×20 widget; the limits qualify deduplication by record health; W1–W6 are the canonical wordings. Replay and parent-lock limits are recorded.
- **Orchestrator decision 10:** No timing assertion was added; the docs test reads the architecture rule file by path.
- **Review M8 and the round 1 decisions of plans 35-02 through 35-07 — provisional, need confirmation:** Recorded the missed-execution meaning of `skipped: busy`, the copyable second-line preview, cadence, degraded-record clauses, timer-only working-directory guarantee, and runner-site residuals.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: two themed pi runs, both first time; commits 87d62f9b (Task 1, Schedules screen detail text) and 76639ac9 (Task 2: `.claude/architecture.md` subsection, dated amendments of `35-SPEC.md`, `ROADMAP.md` and `REQUIREMENTS.md`, `tests/test_docs.py` pins); the commit hook ran the six static gates on both.
- Named tests: all 14 names in the tasks are defined.
- Plan verifies run by the orchestrator with an owned TMPDIR (removed afterwards): both <automated> pytest commands passed (all non-make verifies passed).
- Full `make test` run once by the orchestrator with the default TMPDIR: 9648 passed, 6 skipped, coverage 96.43%.
- Python 3.15 targeted run on tests/test_docs.py and tests/test_schedules_view.py: all passed.
- Provisional decisions (need owner confirmation): the dated amendments of SPEC, ROADMAP and REQUIREMENTS (operative lines rewritten in place, not only appended), wordings W1 to W6 (timer opt-in vs explicit manual run, notification as an attempt, cross-row deduplication and the six-hour cadence, process-group and replay limits), the 80x20 detail visibility rules.

orchestrator-verification: none required
