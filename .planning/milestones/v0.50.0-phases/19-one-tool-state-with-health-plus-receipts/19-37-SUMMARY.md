---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "37"
subsystem: version-status
tags: [skill-cache, pack-scans, claude, tui, state]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "UpdateService and receipt-backed tool state (19-32)"
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "Unified tool state and catalog health behavior (19-36)"
provides:
  - "Skill cache write failures settle fresh answers and surface a status-line warning"
  - "Skill invalidation marks in-memory answers stale before writing the cache"
  - "Each pack is rebuilt using the scan from the pass that published its state"
  - "Ambiguous Claude duplicates do not create partial install steps"
affects: [version-status, catalog-tui, skill-lifecycle, STATE-01, STATE-02, STATE-07]

actuals:
  tokens: 85000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Best-effort skill-cache persistence does not block publishing fresh skill answers"
    - "Each pack retains the sequence and scan from its publishing pass"
    - "D-18 Claude reasons prevent ambiguous listings from becoming partial install work"

key-files:
  created: []
  modified:
    - installer/version_status.py
    - installer/catalog_tui.py
    - tests/test_version_status.py
    - tests/test_catalog_tui.py

key-decisions:
  - "A failed skill-cache save becomes a service warning; fresh answers still publish and packs rebuild"
  - "Invalidation changes in-memory probe state before the cache write, while the write error still propagates"
  - "Pack scans are stored per pack so later partial passes do not strand earlier packs in CHECKING"
  - "Claude is excluded from partial targets whenever its D-18 listing reasons are non-empty"
  - "_skill_state deliberately differs from skill_lifecycle.inspect_status for fresh maps without a present answer (P19-07)"

patterns-established:
  - "A completed skill probe publishes fresh answers even when cache persistence fails"
  - "A skill-state rebuild uses the scan that published each pack's state"

requirements-completed: [STATE-07, STATE-01, STATE-02]

coverage:
  - id: D1
    description: "Skill-cache write failures still publish fresh answers, rebuild packs, and display a warning; failed invalidation writes still force a later probe"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_skill_cache_save_failure_still_settles_the_packs"
        status: pass
      - kind: automated_ui
        ref: "tests/test_catalog_tui.py#test_skill_cache_save_warning_reaches_the_status_line"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each pack is rebuilt with the scan from the pass that published its state"
    requirement: STATE-01
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_partial_pack_pass_keeps_every_packs_scan"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ambiguous Claude duplicates do not receive a partial reason or install step"
    requirement: STATE-02
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_ambiguous_claude_duplicates_never_get_a_partial_install_step"
        status: pass
    human_judgment: false

duration: unknown
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 37: Skill state and cache-failure gaps Summary

**Skill probes now settle pack state despite cache-write failures, retain each pack's publishing scan, and avoid turning ambiguous Claude duplicates into install steps.**

## Performance

- **Duration:** Not recorded
- **Tasks:** 3
- **Task commits:** 3
- **Files modified:** 4

## Accomplishments

- A failed skill-cache write no longer strands packs. `refresh_skills` treats the skill save as best effort, publishes fresh answers, marks the launch probed, rebuilds pack states, and records the failure as the service warning. `invalidate` clears the probed flag and marks held answers stale before writing the cache, so a failed write still forces the next skill probe; the write's `OSError` still propagates. The TUI carries the completed probe's warning through `SkillStatusRefreshed` and displays the existing status-line tail, `— marks are current; the next start checks again`, even though the earlier version pass already cleared its own warning.
- Each pack keeps the scan of the pass that published it. The service records the publishing pass's sequence and scan per pack, and `refresh_skills` rebuilds each pack with its own scan rather than a single global scan that a later partial pass could overwrite.
- Ambiguous Claude duplicates are not partial absences. `_user_pack_facts` previously treated an `absent` Claude answer as a missing harness when another harness had the pack, adding a `partial:` reason and `skill_install` step over D-18 duplicate fixes. Claude is now excluded from partial targets whenever D-18 reasons are non-empty. The redundant `answered` alias in `_skill_state` is gone, and its docstring records the deliberate difference from `skill_lifecycle.inspect_status` (P19-07).

## Task Commits

Each task was committed atomically:

1. **Task 1: Preserved skill answers when the cache write fails** — `92e9ac2` (fix)
2. **Task 2: Kept each published pack's own scan** — `ba1a2bf` (fix)
3. **Task 3: Stopped treating ambiguous Claude listings as absent** — `ecea8da` (fix)

**Plan summary:** `0463946` (`docs(19-37): plan summary`; this commit is being amended).

## Files Created/Modified

- `installer/version_status.py` — skill-cache failure handling, in-memory-first invalidation, per-pack scans, and Claude partial-target filtering.
- `installer/catalog_tui.py` — carries completed skill-probe warnings to the status line.
- `tests/test_version_status.py` — regression coverage for save failures, partial pack passes, and ambiguous Claude duplicates.
- `tests/test_catalog_tui.py` — regression coverage for skill-cache warning display.

## Decisions Made

- A failed skill-cache save does not prevent publishing fresh answers or rebuilding pack state; it becomes the service warning.
- Invalidation changes in-memory state before attempting persistence, but still propagates the cache write's `OSError`.
- Per-pack scan records ensure a later partial pass cannot strand a pack published by an earlier pass.
- D-18 Claude reasons mean a Claude listing is ambiguous or duplicated, not absent; Claude is therefore excluded from partial install targets.
- `_skill_state` intentionally returns MISSING with a not-checked note in the described fresh-map case, unlike `skill_lifecycle.inspect_status`, which returns unknown (P19-07).

## Deviations from Plan

- **Task 1:** `ruff format` reformatted the new try-block wrap in `installer/version_status.py`, and a 101-character assertion string in `tests/test_catalog_tui.py` was split across two literals. Mechanical only; no behavior change.
- **Task 2:** The 19-08 structural test `test_the_service_publishes_one_snapshot_of_tool_states` asserted the service held exactly one other tool-keyed dict besides the state snapshot. The plan's `_pack_scans` must-have adds a third store, so the test now expects two non-state dictionaries, matched by value shape (`SkillHostStatus` values versus `(int, scan)` entries) and still read through `vars()` with no private names. The 19-08 invariant of one published `ToolState` snapshot is unchanged.
- **Task 3:** None beyond the plan.

## Verification Results

- `make validate` — exit 0 (ruff check, ruff format --check, pyright, bandit, vulture, shellcheck).
- `make test` — 4612 passed, 4 skipped; coverage 95.97% (required 90.0%).
- Plan acceptance checks: `version cache not saved: {exc}` present (1); `marks are current; the next start checks again` present (1); `self._pack_scans` present, with no single `_pack_scan` field; `agreeing with` gone (0); `answered = hosts` gone (0); `skill_hosts=answered` gone (0); `P19-07` present (1); no new `type: ignore|pyright: ignore|noqa|nosec` suppressions.

## Known Limitations

- The three warnings this fixes were silent-shape issues (a probe ran but nothing published); no user-visible regression was reported in production, and the fixes only change behavior on the failing paths above.

## Issues Encountered

None beyond the plan deviations described above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The changes close the three Phase 19 review gaps described in the plan. No follow-ups are listed.

## Follow-ups

None.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
