# Phase 35 Plan 10 Summary

The plan ran as two themed pi runs; the text below is the executors' own final notes. Task 2 made no commit (it names none unless a repair is needed).

## Task 1 (`a476f032`)

**Commit:** `a476f032faa561963ff87cf817af82c5f5c508b2` — `test(35-10): prove the update-all plan, run and closed lists agree`

Added dispatch-parity, closed-list, composition-and-lock, module-import, summary-budget, and long-ID manual-versus-timer tests. No production files or existing test assertions were changed.

## Test output

**Initial runs:** The first dispatch and import tests passed immediately; there was no product RED. Subsequent test-harness failures exposed incorrect screen-method access and an in-process child patch leaking into other tests. Both were corrected.

The first full targeted run ended with four failures caused by that leaked patch. After isolation, the required targeted command exited 0:

```text
........................................................................ [ 29%]
........................................................................ [ 59%]
........................................................................ [ 89%]
..........................                                               [100%]
```

The commit hook passed all six static gates. Its earlier lint, typecheck, and format failures were corrected and their respective targets rerun successfully.

## Deviations and remaining coverage

All five named tests were added, but two requested assertions remain incomplete:

- The closed-list test checks runner parsing for every row, but checks screen target and detail text only for update-all and cache-cleanup, not every row.
- The multiword summary test varies padding but does not establish that the notification reason is trimmed at every budget from 270 through 300.

The required final `make validate` and `make test` were not run, as directed for this themed run. Each owned scratch run directory was removed by its exit trap; pytest used the default temporary directory as directed.

## Decisions

- Orchestrator decision 10 — host seams are faked and the strict reachability guard is included in targeted verification: **provisional; needs confirmation**.
- All phase provisional decisions remain provisional and **need confirmation**; this task changes none.

## Task 2

## Task and verification

- **Commit:** None. Task 2 specifies no new test and no commit unless a repair is needed. The tree had no Task 2 changes; HEAD remained `a476f032`.
- **RED:** Not applicable; Task 2 names no new test.
- **GREEN:** `uv run pytest tests/test_reachability.py tests/test_docs.py -n auto -q --no-cov` exited 0, ending at `[100%]`.
- **Earlier summaries:** `35-01-SUMMARY.md` through `35-09-SUMMARY.md` each exist and have a `## Decisions` section.
- **Existing-test edits:** None. **Named Task 2 tests omitted:** None.
- The targeted run used the default `TMPDIR`; its separately created scratch directory was removed by its exit trap.
- **Deviation:** The themed-run instruction expressly deferred `make validate` and `make test`; they were not run. Consequently, no final-tree gate pass is claimed.

## Decisions

- **Orchestrator decision 10 — provisional, needs confirmation:** Inject external-tool and clock fakes, avoid timing-sensitive assertions, assert the complete 300-character result-line budget, and retain the strict reachability guard.
- All phase provisional decisions remain provisional and need owner confirmation; this task changes none.

## Provisional decisions for the owner

Each item below is **provisional and needs confirmation**.

- **D-03:** Daily at 03:00.
- **D-05:** Order managers by ownership edges; amend ROADMAP criterion 2 and AUTOUPD-02.
- **D-06:** Group dependents by owner and skip those blocked by failed managers.
- **D-07:** Plan managers regardless of outdated status; dependents require outdated, confirmed evidence within the applicable refresh windows.
- **D-08:** Use a pure planner and one status pass per stage, with caller-supplied refusal evidence.
- **D-09 / decision 4:** Use the generic no-unattended-update-path rule for antigravity, codex, fnm, herdr-app, kitty, opencode, volta and xcode-clt; xcode-clt retains its earlier hand-off refusal text.
- **D-11:** Three-hour job bound and 1200-second per-command bound.
- **D-12:** Keep a last-run, per-tool update-all log.
- **D-13:** The `by` value accepts update schedule IDs; write with `atomic_replace_entry` and read strictly.
- **D-14:** Per-tool rows skip only tools updated by update-all that day.
- **D-20 / decision 9:** Use a dedicated orchestrator-run container target; its narrowed fixtures use real managers rather than the originally proposed fake managers.
- **Decision 1:** Refresh and re-plan dependents after managers finish.
- **Decision 2:** Interpret plan-mode “writes nothing” as no installer-state writes; use `hold_writes()` rather than a scratch cache because receipt writes must also be held.
- **Decision 3:** Notify only when updated plus failed is greater than zero.
- **Decision 7:** Add the ninth schedule row, increase table height to ten, adjust layout pins and reflow the check detail.
- **Decision 8:** Set `UV_NO_MODIFY_PATH`; rename-based self-replacement is expected but unproven here, and vendor shell-rc modification remains an accepted limit.
- **O7:** Count unchanged outcomes separately; a successful update with an unreadable version counts as updated.
- **Round 1:** Caller-supplied refusal evidence keeps the planner pure; guard fresh ownership with the shared exclusion predicate; require confirmed evidence; skip cycles; deduplicate from structured mutation evidence and report degraded records; type-check the reader and append logs non-blockingly.
- **Round 1:** Refuse root; inject the runner at replay and terminal follow-up sites, accepting the separately bounded runner-site residual; always print the plan note; preview cached evidence; use `plain_line` as the normalizer and test the real notification adapter.
- **Round 1:** Show the preview and documented limits; seed older uv and upgradeable Ruff, with gated container steps.
- **Round 2:** Verify the parent flag using the runner PID and live holder line; give each command its own process group, forward job-level termination, and end and await the group.
- **Round 2:** Apply the backfilled-report rule, “did not run first” guard and guarded Cursor skip; retain pnpm replay and count planned updates only.
- **Round 2:** Record `UpdateOutcome.mutated`: a post-mutation smoke failure counts, but a failed mutating command does not; sample the record day at mutation. This deviates from “record conservatively.”
- **Round 2:** Block cycle-dependent managers; share confirmation logic with preview; describe notification as an attempt; retain canonical wordings W1–W6; cap `first_failed` at 40 characters; use a portable fail-closed disk check and persist container evidence.
- **Round 3:** Prove the parent holder with the kernel lock as well as its line; bind evidence to its producing owner; pass failure and cycle blocks through skipped managers; judge the day at each decision.
- **Round 3:** Cap cleanup within the runner stop budget; refuse root in the stdlib runner; close query stdin; cap record writes.
- **Round 3:** Include drift evidence and the extended note in preview; require the installer’s own evidence for an omitted dependent on container rerun; measure the unresolved uv leaf; emit skipped-step markers from the EXIT trap.
- **Documentation amendments:** The dated SPEC, ROADMAP and REQUIREMENTS amendments remain subject to confirmation.

## Deferred verification

- **AUTOUPD-08: instrumented (35-09), real container run: not run.** The verifier must retain real replacement of the running uv as a human item.
- The orchestrator should record, beside any container transcript, `git rev-parse HEAD` and a digest of `git status --porcelain=v1 --untracked-files=all` immediately before the run. A later repair to an exercised path invalidates that observation and requires a rerun.
- Deferred owner checks: real Bazzite and macOS runs, real notification, the 03:00 timer on both OSes, and the first night’s outdated set.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: two themed pi runs; commit a476f032 (Task 1, the consistency tests); Task 2 (phase-close gates and the owner's list) needed no repair commit.
- Named tests: all 18 names in the tasks are defined.
- Plan verifies run by the orchestrator with an owned TMPDIR (removed afterwards): all non-make verifies passed (including the nine-summary enumeration).
- Final gates run once by the orchestrator at HEAD a476f032 with the default TMPDIR: `make validate` all six gates Passed; `make test` 9690 passed, 6 skipped, coverage 96.44%. Python 3.15 targeted run on tests/test_update_all_contract.py, test_reachability.py, test_docs.py: all passed.
- AUTOUPD-08, REAL container run PERFORMED by the orchestrator (the executor's "not run" above predates it): `scripts/container-e2e-verify.sh update-all` on the tree at 1d88f6e7 (only tests/test_update_all_contract.py and tests/update_all_child.py changed afterwards, no exercised production path): uv 0.11.0 replaced itself with 0.13.9 at /home/tester/.local/bin/uv through the real `uv run` chain (TRACER_UPDATE_ALL_UV_SELF_UPDATE_OK), ruff 0.1.0 updated to 0.17.6 (DEPENDENT_OK), shell rc files unchanged (RC_FINDING changed=none), bun and sdkman up to date, the same-day rerun skipped all four recorded tools (AGAIN_OK), the notification skipped (`notify-send exited 1`: no session bus in the box, expected), teardown OK, the PID-named container and image removed. Evidence is labelled installer-outcome (not vendor stdout). Not covered: macOS, Bazzite host, a real desktop notification, the 03:00 timer firing.
- All provisional decisions listed in the Task 2 section above remain provisional and need owner confirmation.

orchestrator-verification: none required
