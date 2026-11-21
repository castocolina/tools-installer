# Phase 32 Plan 10 Summary

- **Task 1 — `d52b4595`:** Added filtered ledger previews sharing the revert’s eligibility and grouped Codex decisions, plus unreadable-file and outside-home reporting. Task 1 RED and GREEN output was not available in this split run.
- **Task 2 — `17dd0f50`:** Added Playwright removal-preview lines and tests for exact keys, changed Codex fields, malformed and missing files, and external Copilot home.
- **Gate fix — `fb8827a3`:** Updated the existing uninstall UI test double to accept the new preview keywords after the full suite exposed its outdated signature.

## Verification

- Task 2 RED tail: the four new preview tests failed because the removal preview returned no lines.
- Task 2 GREEN tail: the targeted four-file pytest command reached `[100%]` with exit 0.
- `make validate` tail: lint, format-check, typecheck, security, dead-code and shellcheck **Passed**. This ran before the gate-fix commit; that commit’s hook passed the same six checks.
- Initial `make test`: **1 failed, 9043 passed, 6 skipped**; the failure was the outdated test double. Its targeted rerun passed.
- Final `make test` tail: **9044 passed, 6 skipped**; coverage **96.34%**, above the 90% requirement.
- Run directories created for targeted tests were removed by their exit traps. Tests used the default TMPDIR as directed by the orchestrator.

## Decisions

Each decision below is **provisional; needs owner confirmation**.

- Review M5: the sweep preview lists its exact files and keys, not unrelated agent settings.
- Review M3: the preview shares the revert’s grouped Codex decision and allowed file/key eligibility.
- Review M4: the preview explicitly names the outside-home limit without exposing the external path.
- Review M6/M7: the preview shares full revert eligibility and reports unreadable files as unchanged.
- Host settings OS is `macos` on Darwin and `linux` otherwise; public removal signatures remain unchanged.
- Orchestrator decision 9: guards and tests stay together; no module or usage-text PATH lines were added or changed. Python 3.12 was tested locally; Python 3.15 was not run.

## Pin edits

None.

## Deviations and remaining risk

- The full-suite failure required an additional coherent commit and a fifth changed file, `tests/test_wizard_app.py`, beyond the four planned files. No named Task 2 test was omitted.
- The initial commit hook identified long test literals and then a formatting issue; both were corrected and their failing gate targets rerun.
- No live tools, containers, GUI, or real agent configuration were exercised.

## Orchestrator verification

Verified by the orchestrator on 2026-11-21:

- Commits `d52b4595` (Task 1: ledger preview with a setting filter, the shared grouped-Codex decision and the (file, key path) eligibility, unreadable and outside-home reporting), `17dd0f50` (Task 2: the Playwright removal-preview lines) and `fb8827a3` (the existing uninstall-preview test double in `tests/test_wizard_app.py` takes the new `settings` and `environ` keywords: a signature update, no assertion weakened), each through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0; every `<behavior>` test exists.
- `make test` on the final tree, default TMPDIR: 9044 passed, 6 skipped, coverage 96.34%.
- Container checks: none required for this plan.

Provisional decisions carried to the verification report (needs owner confirmation): review M6/M7 and round 2 M3/M4 (the removal preview shares the revert's eligibility and grouped Codex decision; an unreadable file is reported instead of promised removal; an external `COPILOT_HOME` is named as reverted but not listed).

orchestrator-verification: none required

orchestrator-verification: none required
