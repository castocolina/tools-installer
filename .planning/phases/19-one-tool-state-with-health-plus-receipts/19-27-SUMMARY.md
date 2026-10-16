---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "27"
subsystem: state
tags: [skill-packs, health, terminal-shell, refresh, tool-state]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "19-22 settled the one-record refresh service this plan corrects"
provides:
  - "A probed skill pack stays CHECKING until the current probe answers; stale answers add only the seeded note"
  - "A finished probe is present when any host is present, else MISSING, with a not-checked note per unreadable present harness"
  - "refresh_skills rebuilds only pack states from the latest publishing pass, using that pass's scan"
  - "A dry-run terminal warning becomes a not-checked note on its mapped row, with no step"
  - "tool_health keeps other groups' facts by comparing Health values, not tuple identity"
affects: [19-one-tool-state-with-health-plus-receipts, catalog-health, skill-uninstall]

actuals:
  tokens: 6346
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Fresh skill answers are stored with stale=False; cache and invalidate write stale=True"
    - "The skill worker reuses the publishing pass's _pack_scan and never scans the home itself"
    - "tool_health selects the winning group by its Health value"

key-files:
  created: []
  modified:
    - installer/version_status.py
    - tests/test_version_status.py
    - tests/test_catalog_tui.py
    - tests/test_tool_health.py

key-decisions:
  - "A missing or stale skill-answer map is CHECKING; only a stale map adds the seeded note"
  - "After a fresh answer, presence is any present host; every other finished answer is MISSING"
  - "G17 stays a behavior-preserving refactor: the shared-tuple characterization passed before and after, so its RED is waived"

patterns-established:
  - "Pattern: stale skill answers never settle presence, facts, or steps"
  - "Pattern: refresh_skills publishes host answers against the scan of the pass that is current"

requirements-completed: [STATE-07, STATE-01, STATE-02, STATE-06]

coverage:
  - id: D1
    description: "A probed skill pack is CHECKING until the current probe answers; a cache-seeded present adds only the seeded note and never a check mark"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_stale_cached_present_is_checking_not_ok"
        status: pass
      - kind: automated_ui
        ref: "tests/test_catalog_tui.py#test_skill_health_cell_reads_a_persisted_answer_without_a_stale_variant"
        status: pass
    human_judgment: false
  - id: D2
    description: "A finished probe is present when any host is present, otherwise MISSING, with a not-checked note for each unreadable present harness"
    requirement: STATE-01
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_all_unknown_after_the_probe_is_missing_with_a_note"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_mixed_absent_and_unknown_hosts_never_settle_absent"
        status: pass
    human_judgment: false
  - id: D3
    description: "refresh_skills rebuilds pack states from the latest publishing pass's scan and never overwrites a newer pass's project facts"
    requirement: STATE-02
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_skill_rebuild_never_rereads_project_facts"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_skill_rebuild_after_a_newer_pass_keeps_its_facts"
        status: pass
    human_judgment: false
  - id: D4
    description: "A dry-run terminal warning becomes a not-checked note on the mapped row, including Konsole on zsh, with no configuration step"
    requirement: STATE-06
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_terminal_warning_is_a_not_checked_note"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_konsole_warning_lands_on_zsh"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_unknown_terminal_warning_lands_on_every_terminal_row"
        status: pass
    human_judgment: false
  - id: D5
    description: "tool_health keeps the other groups' facts by comparing Health values, so two groups holding one tuple cannot drop each other"
    requirement: STATE-06
    verification:
      - kind: unit
        ref: "tests/test_tool_health.py#test_reasons_follow_precedence_when_groups_share_a_tuple"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 27: Fresh Skill Answers, Publishing-Pass Scans, and Terminal Notes Summary

**Skill packs stay CHECKING until the current probe answers, the skill worker rebuilds with the publishing pass's scan, and terminal warnings become row notes**

## Performance

- **Duration:** 13 min
- **Started:** 2026-10-16T21:15:05Z
- **Completed:** 2026-10-16T21:28:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- A user-scope skill pack with probes is CHECKING while its answers are missing or stale. A cache-seeded `present` adds only `host status from the previous run, re-checking` and never settles presence, partial facts, steps, or a green check.
- Once the current probe answers, any `present` host makes the pack present. Every other finished answer is MISSING. Each harness on the machine that answered `unknown` adds `skill configuration not checked: no readable answer from {Harness}`.
- `refresh_skills` no longer scans the home. It rebuilds only pack states whose generation and sequence match the latest pass that published packs, using that pass's scan.
- A dry-run warning becomes `terminal shell not checked: {warning}` on the row named before its first colon. Konsole lands on `zsh`. An unknown prefix lands on every terminal row. A warning adds no step.
- `tool_health` appends the other groups' facts when their Health is not the winner's Health. The visible reason order is unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: a probed skill pack is CHECKING until the current probe answers** - `b48c176` (fix)
2. **Task 2: the skill worker rebuilds with the publishing pass's own scan** - `7d689d2` (fix)
3. **Task 3: terminal warnings reach their row, and tool_health picks precedence by Health** - `aa963f3` (fix)

## Files Created/Modified

- `installer/version_status.py` - fresh-answer rule in `_skill_state`, `_pack_scan` published by `_pass` and read by `refresh_skills`, warning notes in `_terminal_facts`, Health comparison in `tool_health`
- `tests/test_version_status.py` - stale, unknown, mixed, rebuild, and terminal-warning tests, plus the planned updates of the old cached-OK assertions
- `tests/test_catalog_tui.py` - health-cell assertions updated from a seeded check mark and a stuck ellipsis to the finished answers
- `tests/test_tool_health.py` - shared-tuple characterization of precedence by Health

## Decisions Made

- None or stale skill answers both stay CHECKING. Only a stale map adds the seeded note, because a pack with no answer yet has nothing from a previous run to report.
- A finished probe with no `present` host is MISSING, including an all-unknown answer. The not-checked notes still name every unreadable harness that is on the machine, so the row is never a note-less MISSING for that input.
- `tool_health` compares Health values and then keeps `dict.fromkeys` deduplication. Two groups holding one tuple object therefore cannot drop each other, while duplicate sentences stay listed once.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The shared task-brief extractor cannot see this plan's tasks**
- **Found during:** Task 1 (fresh skill answers)
- **Issue:** `task-brief` matches markdown headings. This plan's tasks are XML `<task>` elements, so the extractor reported no task.
- **Fix:** Extracted each `<task>` element into the plan's SDD brief files. No source file changed.
- **Files modified:** none
- **Verification:** Each brief contained the task's behavior, action, and verify blocks before implementation.
- **Committed in:** none (workspace-only)

**2. [Rule 1 - Bug] One more catalog test pinned CHECKING after a finished failed probe**
- **Found during:** Task 1 (fresh skill answers)
- **Issue:** `test_skill_probe_failure_paints_unknown_and_keeps_the_app_running` expected `…` after the probe raised. Its service plants a `.claude` marker, so the harness is present and the finished answer is MISSING.
- **Fix:** Updated that assertion to `○`, named here as a planned update. No other assertion was weakened.
- **Files modified:** `tests/test_catalog_tui.py`
- **Verification:** The wider skill and pack selection passed, then `make test` passed.
- **Committed in:** `b48c176` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both stayed inside the plan's rule. No scope creep.

## TDD evidence

### Task 1 RED

`uv run pytest tests/test_version_status.py tests/test_catalog_tui.py -q --no-cov -k "stale_cached_present or all_unknown_after_the_probe or mixed_absent_and_unknown or seeded or inconclusive_claude or every_host_is_unknown or persisted_answer or empty_hosts"` failed 10 tests. Seeded `present` answers were OK, finished all-unknown probes stayed CHECKING, and the mixed stale cache settled MISSING.

### Task 2 RED

`uv run pytest tests/test_version_status.py -q --no-cov -k "skill_rebuild"` failed `test_skill_rebuild_never_rereads_project_facts`. After the home changed, `refresh_skills` replaced `installed in 1 repo` with the global-leftover and empty-install reasons from its own late scan.

### Task 3 RED

`uv run pytest tests/test_version_status.py tests/test_tool_health.py -q --no-cov -k "terminal_warning or konsole_warning or share_a_tuple"` failed the three G11 tests: the warning text was absent from every row. `test_reasons_follow_precedence_when_groups_share_a_tuple` passed before the change.

### G17 RED waiver

G17 is a behavior-preserving refactor. `dict.fromkeys` masks the tuple-identity skip for the shared object, so the characterization test passes before and after. Its RED is waived as the plan requires. The implementation now compares `state is not winner[0]`.

## Verification

- Task 1: `make validate` exit 0; `make test` 4539 passed, 4 skipped.
- Task 2: `make validate` exit 0; `make test` 4541 passed, 4 skipped.
- Task 3: `make validate` exit 0; `make test` 4545 passed, 4 skipped.
- Acceptance counts at task close: `self._pack_scan` 3, `self._scan_packs(` 1, `is not winner[0]` 1, `.warnings` 1.
- Final line counts: `installer/version_status.py` 1663, `tests/test_version_status.py` 5096, `tests/test_catalog_tui.py` 4771, `tests/test_tool_health.py` 177.

## Issues Encountered

- The first type narrowing used an assert. Bandit B101 rejected it, and the plan forbids a suppression, so the fresh branch assigns `answered = hosts` after the early return. Pyright narrows that local with no assert.
- `uv run pytest` on the skill selection also ran `test_skill_probe_failure_paints_unknown_and_keeps_the_app_running`, which the plan's named list did not include. It pinned the old stuck-CHECKING behavior and was updated as a planned update.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The four gap-closure truths are covered by passing tests. A finished skill probe no longer stays CHECKING, so `u` is not blocked by a probe that has already answered.
- No host mutation was run. No dependency file changed.

## Self-Check: PASSED

- FOUND: `.planning/phases/19-one-tool-state-with-health-plus-receipts/19-27-SUMMARY.md`
- FOUND: `b48c176`
- FOUND: `7d689d2`
- FOUND: `aa963f3`

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
