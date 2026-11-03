---
phase: 21-one-screen-family
plan: "19"
subsystem: doctor-screen
tags: [textual, doctor, pnpm, session-evidence, screen-family]
requires: [21-05, 21-18]
provides: [DoctorScreen state_refreshed, node-tool reason lines, pnpm evidence recording, guarded Doctor reads]
affects: [installer/wizard_app.py, installer/pnpm_globals.py, installer/guidance.py]
key-files:
  modified:
    - installer/wizard_app.py
    - installer/pnpm_globals.py
    - installer/guidance.py
    - tests/test_screen_family.py
    - tests/test_wizard_app.py
decisions:
  - "Doctor's pnpm findings are the published ToolState reasons; node_globals_guidance stays console-only"
  - "The audit records evidence for every node tool and requests a pass only when stored evidence changed"
requirements: [UI-07]
status: complete
actuals:
  tokens: 21000
  tasks: 2
  commits: 4
plan_head_before: 503a6887c5be8adc229c092e1b95e7393fb4c7fd
plan_head_after: b398a32
---

# Phase 21 Plan 19: Doctor joins the screen family Summary

Doctor renders pnpm findings from the same `ToolState.reasons` the tiers show, records its own audit as session evidence (one pass only on change), and reports a failed live read as an error instead of an old frame.

## Commits

- d353421 test(21-19): doctor shows pnpm findings from the shared state (RED)
- 140cff1 feat(21-19): doctor shows pnpm findings from the shared state
- bf364e1 test(21-19): a failed doctor read shows its error instead of an old frame (RED)
- b398a32 feat(21-19): a failed doctor read shows its error instead of an old frame

## RED output

Task 1 (`-k "smoke_failure or unchanged_audit or dangling_pnpm or doctor_rerenders or unreadable_audit or hostile_pnpm_reason or disk_item_sits"`): 6 failed.
- smoke_failure: `AssertionError: condition never became true within the polling budget` (no second pass)
- unchanged_audit: `assert 1 == 2` (passes)
- dangling_pnpm / doctor_rerenders: `'mmdc: ...' in 'PATH Doctor\nAudit...'` false
- hostile_pnpm_reason: `'\x1b' is contained here: ...[31mboom` (the old guidance path let the escape byte through)
- disk_item_sits: `Left contains one more item: Guidance(title='pnpm-managed global set is incomplete'...)`
- `test_an_unreadable_audit_records_no_evidence` passed in RED: it is a regression guard (nothing was recorded before either).

Task 2 (`-k "failed_doctor_read or no_findings_draws"`): both `test_a_failed_doctor_read_shows_the_error[...]` cases failed with the uncaught `OSError: rc file locked`. `test_doctor_with_no_findings_draws_its_empty_copy` passed in RED (Doctor already rebuilds its frame each entry); it stays as the backstop.

## GREEN output

`make validate` exit 0; `make test` exit 0, `5102 passed, 4 skipped`, coverage 96.16%. Before this plan the base tree measured 5099 passed after Task 1.

## Collected counts (start -> end)

- tests/test_screen_family.py: 104 -> 113 (+9: 6 Task 1, 2 failed-read cases, 1 empty backstop; plan floor 103+9=112 measured as 104+9)
- tests/test_wizard_app.py: 319 -> 319
- tests/test_guidance.py: 60 -> 60 (console tests unchanged, output byte-identical)

## Empty-body text pinned

The backstop compares a Doctor re-entered with every seam answering nothing against a freshly built Doctor with the same seams: byte-equal body, containing no guard warning, disk item or stale node-tool reason. The tail of that body is `0 package(s)`-free: with the default report it ends `... catalog tool(s).\nnothing pnpm-managed to reinstall\nPress r to reinstall the pnpm-managed global set.`

## Existing tests changed (with reasons)

All because Doctor's guidance no longer carries `node_globals_guidance` (plan decision; the finding now arrives as state reasons):
- `test_doctor_disk_item_sits_after_guard_and_before_pnpm_globals` renamed `test_doctor_disk_item_sits_after_guard_and_before_pnpm_reasons`: asserts `guidance == _HEALTHY_DOCTOR + guard_items + disk_pressure_guidance(_AT_RISK)` and that the first `mmdc: ` body line sits after the disk item title (frozen service wired).
- `test_doctor_screen_shows_missing_pnpm_globals_and_preview`: dropped the guidance-meaning and body `mmdc` assertions; preview and heading assertions stay.
- `test_doctor_reinstall_refuses_a_stale_report_while_reauditing`: the body no longer names `mmdc` from the audit; asserts the count line before and `globals_auditing`/`globals_note` cleared after.
- `test_doctor_r_clears_the_stale_missing_globals_warning`: dropped the two guidance-title assertions; body assertions stay.
- `test_doctor_rereads_node_globals_on_enter_view`: now counts audit reads (1, then 2 on re-entry) instead of reading guidance items.
- `test_doctor_tui_guidance_rewrites_make_setup_prefix`: now asserts no guidance item carries the console `Run \`make setup\`` step and the body shows `Press r`, never the console wording.
- The `node_globals_guidance` import in `tests/test_wizard_app.py` was removed (unused).

## Deviations from Plan

**1. [Rule 1 - Bug in own test] tier repaint** - the tracer test asserted the tier mark while Doctor was on top; D-06 repaints only the visible view, so the test re-enters the tier first. Commit 140cff1.

Otherwise the plan ran as written. `_tui_guidance`'s `Run \`make setup\`` rewrite branch is now unreachable from production items (kept as planned: "rewrites stay as they are").

## Issues

- Known Doctor UI gap (21-16): at 80x20 the Doctor card covers the status row, so the new `Could not read the doctor state: ...` error is not visible at that size. Not fixed here (the card layout is outside this plan's tests); the error is visible at larger sizes and is covered at 120x30. Needs a layout follow-up.
- The incomplete-group and plain "missing" findings no longer render in the TUI from the Doctor audit; they come from the pass reasons (`PNPM_TRACKED_OFF_PATH`, group facts), as the plan's review disposition states.

## Known Stubs

None.

## Self-Check: PASSED
