---
phase: 21-one-screen-family
verified: 2026-11-03T20:00:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - ".claude/architecture.md"
  - ".planning/phases/21-one-screen-family/21-01-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-01-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-02-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-02-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-03-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-03-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-04-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-04-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-05-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-05-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-06-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-06-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-07-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-07-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-08-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-08-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-09-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-09-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-10-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-10-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-11-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-11-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-12-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-12-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-13-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-13-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-14-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-14-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-15-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-15-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-16-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-16-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-17-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-17-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-18-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-18-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-19-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-19-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-20-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-20-SUMMARY.md"
  - ".planning/phases/21-one-screen-family/21-21-PLAN.md"
  - ".planning/phases/21-one-screen-family/21-21-SUMMARY.md"
  - "installer/guidance.py"
  - "installer/uninstall.py"
  - "installer/wizard_app.py"
  - "tests/test_screen_family.py"
covered_digest: "v3:sha256:3321b902a798ac63f667e14c66557ef96a1e7d880b267766f6dca550277d4d1d"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "NO_COLOR tmux UAT at 80x20 in a disposable container (UI-SPEC's one human backstop): walk system/user/ai tiers, Uninstall, Policies and Doctor; trigger a held lock with the /tmp/uat-bin/systemctl shim and press a second mutating key"
    expected: "Every refusal and status string fits 80x20 and is readable without colour; the Doctor status sits on its own row; the five known pre-existing 80x20 layout items are the only deviations (todo 2026-11-03-fix-80x20-layout-gaps-found-by-the-phase-21-tui-check)"
    why_human: "Visual and layout judgment under NO_COLOR, and a real held-lock timing path; the tmux check recorded in the ledger is not a substitute for the user's own run"
  - test: "Real-host check of a removal (run only in a disposable container, never on the developer host): remove an installer-owned tool and a managed-elsewhere tool from the Uninstall screen, then quit with q and with a second ctrl+c during a slow remover"
    expected: "Removable tool moves to nothing to do, every tier shows the open circle, Policies shows a removed ban OFF; q waits, a second ctrl+c exits with 'Quit before the removal finished; some files may remain.'"
    why_human: "Real filesystem, real package managers and real signal handling cannot be exercised by fake-seam pilots"
---

# Phase 21: One screen family Verification Report

**Phase Goal:** Every screen shows the current truth after any mutation, and Uninstall, Policies and Doctor are projections of the shared state on one lifecycle.
**Verified:** 2026-11-03
**Status:** human_needed
**Re-verification:** No, initial verification

## Gates on HEAD (68d498d, clean tree)

| Gate | Result |
| ---- | ------ |
| `make validate` | exit 0 (ruff, pyright, bandit, vulture, shellcheck all ran) |
| `make test` | exit 0, 5233 passed, 4 skipped, 92.83 s, total coverage 96.22 % (floor 90 %) |
| `tests/test_screen_family.py` UI-01 matrix + fork guard (`-k "reaches_every_view or replaced_forks"`) | 68 cases (42 + 26) all pass |

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Matrix test: 7 mutation sources x 6 target views show new state on next entry, immediately when visible | VERIFIED | `tests/test_screen_family.py:3412` `MATRIX_SOURCES` (asserted len 7), `MATRIX_TARGETS` (len 6, equals `VIEW_NAMES`), `test_a_mutation_reaches_every_view` at :3467 parametrizes both = 42 cases; sources are driven through real key paths; held-navigation repaint case at :3487 passes |
| 2 | Every view keeps a status written during first entry and clears transient status on leave | VERIFIED | `test_entry_status_survives_first_entry_and_leave_clears_it` (:215), `test_uninstall_startup_read_error_stays_visible_on_first_entry` (:251), `test_flushed_warning_is_not_replaced_by_the_standing_status` (:268); C-06/RR-02 fixes keep the app state line from overwriting view status; suite green |
| 3 | Uninstall groups removable (with proof) / managed elsewhere (with owner hint) / nothing to do from shared state; unknown owner never names a manager; BROKEN row says reinstall from the catalog | VERIFIED | `installer/version_status.py:636` `BROKEN_REPAIR_NOTE = "reinstall it from the catalog to repair; nothing to remove here"`; unknown-owner case (`_rg_state` "unknown_owner", `tests/test_screen_family.py:1487`, `tests/test_plan.py:980`); C-23 fix makes removable rows read `installer` with the active copy in the detail |
| 4 | Removal runs on a worker with progress; afterwards tool is in nothing-to-do, selection pruned, tiers show open circle, Policies shows removed ban OFF | VERIFIED | `installer/wizard_app.py:1566` `@work(exclusive=True, group="uninstall-removal", exit_on_error=False)`; `test_a_held_removal_keeps_the_ui_responsive` (:782), `test_a_removed_tool_leaves_the_tier_selection` (:811), `test_publish_prunes_a_staged_tool_that_became_unavailable` (:598), `test_reload_prunes_*` in `tests/test_tool_browser.py:590,638`; matrix Uninstall-removal source crosses all six targets |
| 5 | Policies and Doctor read live state on entry: watch unblocks docker tweak, Doctor `a` inert, dangling pnpm shim shows broken | VERIFIED | `tests/test_policies_e2e.py:1138` `test_installing_watch_unblocks_the_docker_tweak`; `DoctorScreen.BINDINGS` (`installer/wizard_app.py:325-328`) holds only `enter` and `r`; `test_a_is_inert_on_doctor` (:2988); `test_dangling_pnpm_shim_reads_broken` (`tests/test_ownership.py:2461`) and `test_a_dangling_pnpm_shim_reads_broken_in_doctor_and_on_the_tier` (:2698) |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Amended decisions (verified in amended form)

| Decision | Amended text | Status |
| -------- | ------------ | ------ |
| D-06 | A view under a modal re-renders when it closes (`AppScreen.on_screen_resume`); a left view renders on next `enter_view` (CONTEXT:56) | VERIFIED, test coverage for C-08 in suite |
| D-10 | First `q`/`ctrl+c` waits; a second `ctrl+c` exits at once printing `_REMOVAL_QUIT_CUT` (`installer/wizard_app.py:1025`), asserted at `tests/test_screen_family.py:1398`; RR-01 routes `ctrl+q` to the soft quit | VERIFIED |

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
| ----------- | ------------ | ------ | -------- |
| UI-01 | 21-01, 06, 07, 10, 15, 17, 18, 20, 21 | SATISFIED | 42-case matrix + repaint cases pass |
| UI-02 | 21-01, 21-21 | SATISFIED | status lifecycle tests (:215-:268) |
| UI-03 | 21-08, 11, 12, 21 | SATISFIED | projection tests, `BROKEN_REPAIR_NOTE`, unknown owner |
| UI-05 | 21-02, 05, 09, 13, 15, 16, 21 | SATISFIED | exclusive removal worker, `removed`/`remove failed` outcome vocabulary |
| UI-06 | 21-04, 17, 18, 21 | SATISFIED | live Policies; watch/docker e2e |
| UI-07 | 21-05, 19, 20, 21 | SATISFIED | Doctor `a` removed, pnpm shim broken |
| UI-08 | 21-03, 06, 21 | SATISFIED | prune-on-reload tests |

All seven IDs in the ROADMAP are claimed by at least one PLAN. UI-04 maps to Phase 22 in REQUIREMENTS.md (traceability row 188) and is correctly not claimed here. No orphaned requirements. Note: REQUIREMENTS.md checkboxes and traceability rows still read `Pending` for UI-01..UI-08, and the ROADMAP phase 21 checkbox is unticked; both are bookkeeping for the orchestrator's phase-complete step, not code gaps.

### Key Link / Guard Verification

| Check | Status | Details |
| ----- | ------ | ------- |
| Fork guard (26 deleted names) over `git ls-files installer` + untracked + `setup.py` | VERIFIED | `test_the_replaced_forks_are_gone` 26 cases pass; independent grep of 22 of the names over tracked installer files and `setup.py` returned zero hits |
| `.claude/architecture.md` has `## Phase 21: one screen family` | VERIFIED | line 1159; pinned by `tests/test_docs.py::_PHASE_21_REQUIRED` |

### Anti-Patterns Found

None blocking. No unreferenced TBD/FIXME/XXX in installer or setup.py files touched since 390f464.

### Review Findings

REVIEW-FIX reports 30 fixed, 1 by design (C-29), 3 backlog (C-22, C-25, C-27), 6 re-review items (RR-01..06) fixed, each with a RED test commit first. Backlog items are pre-existing and user-accepted, not gaps. The 5 pre-existing 80x20 layout items are tracked in a todo.

### Human Verification Required

1. **NO_COLOR 80x20 tmux UAT** (disposable container). Expected: all strings fit and read without colour; only the five known layout items deviate. Why human: visual judgment and real held-lock timing.
2. **Real-host removal check** (disposable container only). Expected: tool moves to nothing to do, tiers show the open circle, Policies shows a removed ban OFF, `q` waits and a second `ctrl+c` exits with the partial-removal warning. Why human: real filesystem, package managers and signals.

### Gaps Summary

No gaps. All five roadmap success criteria and all seven requirement IDs are backed by code and by passing tests on HEAD. Status is `human_needed` solely because the phase's declared human backstops (NO_COLOR 80x20 UAT, real-host checks) are not automatable.

---

_Verified: 2026-11-03_
_Verifier: Claude (gsd-verifier)_
