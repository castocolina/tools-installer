---
phase: 21-one-screen-family
verified: 2026-11-03T21:30:00Z
status: passed
score: 5/5 must-haves verified
covered_files: [".claude/architecture.md", ".planning/phases/21-one-screen-family/21-01-PLAN.md", ".planning/phases/21-one-screen-family/21-01-SUMMARY.md", ".planning/phases/21-one-screen-family/21-02-PLAN.md", ".planning/phases/21-one-screen-family/21-02-SUMMARY.md", ".planning/phases/21-one-screen-family/21-03-PLAN.md", ".planning/phases/21-one-screen-family/21-03-SUMMARY.md", ".planning/phases/21-one-screen-family/21-04-PLAN.md", ".planning/phases/21-one-screen-family/21-04-SUMMARY.md", ".planning/phases/21-one-screen-family/21-05-PLAN.md", ".planning/phases/21-one-screen-family/21-05-SUMMARY.md", ".planning/phases/21-one-screen-family/21-06-PLAN.md", ".planning/phases/21-one-screen-family/21-06-SUMMARY.md", ".planning/phases/21-one-screen-family/21-07-PLAN.md", ".planning/phases/21-one-screen-family/21-07-SUMMARY.md", ".planning/phases/21-one-screen-family/21-08-PLAN.md", ".planning/phases/21-one-screen-family/21-08-SUMMARY.md", ".planning/phases/21-one-screen-family/21-09-PLAN.md", ".planning/phases/21-one-screen-family/21-09-SUMMARY.md", ".planning/phases/21-one-screen-family/21-10-PLAN.md", ".planning/phases/21-one-screen-family/21-10-SUMMARY.md", ".planning/phases/21-one-screen-family/21-11-PLAN.md", ".planning/phases/21-one-screen-family/21-11-SUMMARY.md", ".planning/phases/21-one-screen-family/21-12-PLAN.md", ".planning/phases/21-one-screen-family/21-12-SUMMARY.md", ".planning/phases/21-one-screen-family/21-13-PLAN.md", ".planning/phases/21-one-screen-family/21-13-SUMMARY.md", ".planning/phases/21-one-screen-family/21-14-PLAN.md", ".planning/phases/21-one-screen-family/21-14-SUMMARY.md", ".planning/phases/21-one-screen-family/21-15-PLAN.md", ".planning/phases/21-one-screen-family/21-15-SUMMARY.md", ".planning/phases/21-one-screen-family/21-16-PLAN.md", ".planning/phases/21-one-screen-family/21-16-SUMMARY.md", ".planning/phases/21-one-screen-family/21-17-PLAN.md", ".planning/phases/21-one-screen-family/21-17-SUMMARY.md", ".planning/phases/21-one-screen-family/21-18-PLAN.md", ".planning/phases/21-one-screen-family/21-18-SUMMARY.md", ".planning/phases/21-one-screen-family/21-19-PLAN.md", ".planning/phases/21-one-screen-family/21-19-SUMMARY.md", ".planning/phases/21-one-screen-family/21-20-PLAN.md", ".planning/phases/21-one-screen-family/21-20-SUMMARY.md", ".planning/phases/21-one-screen-family/21-21-PLAN.md", ".planning/phases/21-one-screen-family/21-21-SUMMARY.md", "installer/guidance.py", "installer/uninstall.py", "installer/wizard_app.py", "tests/test_layout_80x20.py", "tests/test_screen_family.py"]
covered_digest: "v4:sha256:3febd8bd34c9659b0c8f530314d3e61b9679913a0605143bb470e8fa12b5d454"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  date: 2026-11-15
  head: a1877a23
  previous_status: human_needed
  previous_score: 5/5
  method: "container UAT on Fedora 44 (ti-uat-21-fedora, removed), TUI driven through a herdr tab (full width) and tmux 80x20 NO_COLOR inside the container; phase tests green at HEAD"
  gaps_closed:
    - "Real-host check: every screen shows current truth after mutations is proven in a container at HEAD (matrix tests plus UAT 2/3); only the owner's own-machine confirmation remains, listed below"
  gaps_remaining: []
  regressions: []
  owner_confirmation_needed: [real-host check]

---

# Phase 21: One screen family Verification Report

**Phase Goal:** Every screen shows the current truth after any mutation, and Uninstall, Policies and Doctor are projections of the shared state on one lifecycle.
**Verified:** 2026-11-03
**Status:** passed (re-verified 2026-11-15; owner-only item listed below)
**Re-verification:** Yes, after review-fix round 3 (68d498d..1d07f04) changed covered files

## Gates on HEAD (1d07f04; only .planning/RUN-LEDGER.md modified)

| Gate | Result |
| ---- | ------ |
| `make validate` | exit 0 (re-run by the verifier on 1d07f04) |
| `make test` | exit 0, 5237 passed, 4 skipped, 93.06 s, total coverage 96.22 % (floor 90 %); was 5233 at 68d498d, +4 round-3 RED-then-GREEN cases |
| Round 3 targeted cases (`-k "supersedes or hostile or one_tool or Removing"`) | all pass |
| CI / `make e2e` | per RUN-LEDGER 2026-11-03: e2e rc 0 at ~68d498d, CI green on 1d07f04 (not re-run here) |
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

### Round 3 re-check (68d498d..HEAD, touched wizard_app.py and two test files)

| Change | Evidence in code at HEAD | Status |
| ------ | ------------------------ | ------ |
| T-21-52: every daemon-apply completion supersedes an in-flight job read | `PoliciesScreen.refresh_daemon_state` (`installer/wizard_app.py` ~2250-2272): resolved value only when present, then `_start_job_state_read()` on every mounted completion, `_job_state_generation += 1` when unmounted; `resolved = applied if policy.is_active is None else live` is behavior-equivalent to the old branches except the old early return | VERIFIED (RED test 59b2b15, fix 351becd, suite green); closes SECURITY T-21-52 |
| pnpm smoke reason sanitized where recorded | `DoctorScreen` wraps `PNPM_SMOKE_FAILED.format(...)` in `sanitize_log_line` (:950); hostile-reason test passes | VERIFIED |
| Uninstall one-tool summary takes one status row | blank `_applied_summary` no longer appended (:1646); layout test in `tests/test_layout_80x20.py` passes | VERIFIED; resolves UAT 1(c) |
| `Removing...` kept when a row is marked during a removal | `UninstallScreen.on_tool_browser_selection_changed` skips `status.clear()` when `app.mutation_holder is MutationHolder.REMOVAL` (:1452); `MutationLock.mutation_holder` property added (:2741); resolves UAT 3 gap | VERIFIED |

No regression found in truths 1-5: the full suite including the 42-case matrix and the 26-case fork guard is green on HEAD.

### Human Verification Executed (21-UAT.md, container, orchestrator-run at 68d498d)

| Item | Result |
| ---- | ------ |
| NO_COLOR 80x20 walk of all six views plus palette, refusals on row 19 / footer row 20 | Executed, issue (minor): the five known layout items reproduced; three more were seen: (a) Policies shows one table row, (b) a three-line toggle status scrolls the Policies table off screen, (c) Uninstall summary used two rows. (c) fixed in round 3 (5ced876). (a) and (b) are item 6 of the existing 80x20 layout todo (6 items, pre-existing), a backlog item, not a phase gap |
| Real removal of an installer-owned tool | Executed, pass: tool moved to nothing to do, tier row showed the open circle, receipt and files gone |
| Quit during removal (q, second ctrl+c, ctrl+q) | Executed, pass; the Removing-status loss on space was found here and fixed in round 3 (25f26bf) |
| Not covered by UAT | 75-cell pnpm refusal (pnpm absent) and "Policies shows a removed ban OFF" (covered by automated matrix and `tests/test_policies_e2e.py`, not walked by hand) |

### Human Verification Required

1. **Real-host check on the developer's own machine** (the only remaining item). Expected: every screen shows current truth after each mutation; removed tool moves to nothing to do and its tier row shows the open circle. Why human: real package managers, shell rc and systemd user session; a container cannot stand in for the host, and the project forbids agents running setup there.

### Gaps Summary

No gaps. All five roadmap success criteria and all seven requirement IDs are backed by code and by passing tests on HEAD (`make validate` 0, `make test` 5237 passed). Round 3 fixes are present and tested. Known backlog (not gaps): C-22, C-25, C-27, the 80x20 layout todo (6 items), C-29 by design. Status is `human_needed` solely because the real-host check on the user's own machine cannot be automated.

---

_Verified: 2026-11-03_
_Verifier: Claude (gsd-verifier)_


## Re-verification 2026-11-15 (HEAD a1877a23)

Evidence: `uv run pytest tests/test_screen_family.py tests/test_layout_80x20.py tests/test_policies_e2e.py
tests/test_ownership.py tests/test_tool_browser.py -n 4 --no-cov -q` exits 0 at HEAD (the 42-case matrix and the
26-case fork guard pass). A fresh Fedora 44 container (`ti-uat-21-fedora`, repo copied from the tree, uv, scratch
HOME, no Homebrew) ran the wizard through a herdr tab at full width and through tmux at 80x20 with NO_COLOR;
captures are in `scratchpad/uat/21-reverify/` (`01-system.txt`, `03-view-*.txt`, `t80/00..08`). The container and tab
were removed afterwards.

| Item | Verdict | jev (advisory) | Evidence |
|------|---------|----------------|----------|
| Real-host check on the developer's own machine | owner-only | typesafe owner-only 0.95; laya resolved 0.29 (fallback); own reasoning follows typesafe | The container shows Uninstall grouping (managed elsewhere 6 / nothing to do 80), Policies live state, Doctor audit, tier health after mutation at HEAD; the owner's real package managers, shell rc and systemd user session are the part automation cannot show |
| UAT 1 (80x20 deviations) | open-trivial, tracked in todo | typesafe open-trivial 0.62/0.66; laya open-real 0.45/0.42 (fallback); own reasoning: minor and pre-existing, not a Phase 21 requirement | see "80x20 todo status" below |
| UAT 2, 3 | pass (unchanged) | n/a | recorded at 68d498d; the 1-tool summary and `Removing...` fixes are pinned by tests that pass at HEAD |

### Requirements at HEAD

UI-01 satisfied (matrix tests pass); UI-02 satisfied (status lifecycle tests); UI-03 satisfied (projection tests,
Uninstall groups seen in the container capture `t80/02-uninstall.txt`); UI-05 satisfied (removal worker tests);
UI-06 satisfied (`tests/test_policies_e2e.py` green, live Policies capture `03-view-6.txt`); UI-07 satisfied (Doctor
bindings only `enter` and `r`, footer in `t80/03-doctor.txt` shows `enter apply | r reinstall pnpm globals`);
UI-08 satisfied (prune tests in `tests/test_tool_browser.py` pass).

### 80x20 todo status (`2026-11-03-fix-80x20-layout-gaps-found-by-the-phase-21-tui-check`, not edited)

Captured at HEAD in tmux 80x20 NO_COLOR (`scratchpad/uat/21-reverify/t80/`):

1. Tab bar clipped: partly present. With the seventh tab the bar fits exactly on System/Uninstall/Policies, but on Doctor
   it still reads `[7] Schedul` (`03-doctor.txt`).
2. Doctor scrolls as one card: still present (bordered card with a scrollbar inside, `03-doctor.txt`); the tab bar and badge stay put.
3. Uninstall badge cut: present (`enter removes marked items (you'll`, `02-uninstall.txt`).
4. System tier columns cut: changed. `Owner` now shows in full but `What it does` is dropped at 80 columns (`01-system.txt`).
5. Doctor pnpm hint beside an unreadable set: not reproduced here (pnpm absent; the footer offers `r reinstall pnpm globals` while pnpm is missing, which still reads as the contradiction). Not confirmed.
6. Policies one row at a time, and a three-line status hides the table: present (`04-policies.txt` one row; `05-policies-after-toggle.txt`
   shows no table and no `[on]` row until re-entering, `06-policies-reenter.txt`).
7. Key-hint footer cut at 80 columns (`q quit`/`esc back` missing on System, Uninstall, Doctor): present. The confirm box scroll was not re-captured (nothing removable in the container).

All are minor layout items, pre-existing before Phase 21 and tracked in the todo; none is a requirement of this phase.

### Needs owner confirmation

- Run the wizard on the real machine: remove an installer-owned and a managed-elsewhere tool from Uninstall, toggle a Policies row, open Doctor, quit with `q`; every screen shows the current truth.
