---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 12
subsystem: catalog-ui
tags: [skill_pack, version-cache, catalog-tui, stale-marker]

requires:
  - phase: 16-02
    provides: inspect_skill_packs per-host present/absent/unknown
  - phase: 16-06
    provides: version-cache envelope and VersionRefreshService epoch gate
  - phase: 16-07
    provides: SKILL_HARNESS_LABELS
provides:
  - skills key on the existing version-cache envelope
  - once-per-launch background skill probe with epoch discard and a pass lock
  - stale-then-fresh Inst cell, truncated Owner hosts, and detail-pane host list
affects: [16-15]

actuals:
  tokens: 14329
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Skill answers share the version-cache envelope; skills=None preserves the key the way managers=None does"
    - "The skill worker probes self._catalog, never the tier slice, and a second caller waits on _skills_pass_lock"

key-files:
  created: []
  modified:
    - installer/version_cache.py
    - installer/version_status.py
    - installer/catalog_tui.py
    - setup.py
    - tests/test_version_cache.py
    - tests/test_version_status.py
    - tests/test_catalog_tui.py

key-decisions:
  - "No Inst legend entry for ?. Lines measure 58/76/77. Line 1 has 20 free columns and plan 16-15 needs 11 left for its broken marker. Detail pane not probed: covers unknown hosts."
  - "SkillStatusRefreshed discards a mismatched generation before clearing skill_refreshing, matching VersionStatusRefreshed."

patterns-established:
  - "Writers replace self._skills with a new dict under self._lock. skill_status_of is an unlocked single-dict read and does no IO."
  - "refresh_skills returns the held map without probing, persisting, or setting _skills_probed when the input holds no skill pack."

requirements-completed: [D-10, D-12, D-13, D-14]

coverage:
  - id: D1
    description: "Skill-pack host answers persist under the existing version-cache skills key and survive a later save that omits skills. Malformed entries decode to {} for that tool."
    requirement: D-10
    verification:
      - kind: unit
        ref: "tests/test_version_cache.py#test_skill_statuses_round_trip_preserve_and_drop_malformed"
        status: pass
    human_judgment: false
  - id: D2
    description: "A catalog launch probes skill packs once, from the full catalog even when System mounts first, and a second in-flight caller waits for the landed map."
    requirement: D-14
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_probe_runs_once_across_three_catalog_entries"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_probe_covers_packs_when_system_view_mounts_first"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_second_skill_caller_waits_for_in_flight_pass"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_skill_pass_superseded_by_invalidate_stores_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "Before the probe lands, a pack Inst cell shows the persisted or filesystem answer plus a dim ~. After it lands, the mark is plain. All-unknown is a dim ?."
    requirement: D-12
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_inst_cell_shows_persisted_answer_with_stale_mark"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_inst_cell_uses_filesystem_answer_while_refreshing"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_inst_cell_is_dim_question_when_every_host_is_unknown"
        status: pass
    human_judgment: false
  - id: D4
    description: "Owner lists present hosts and truncates to first +N only when the joined text is wider than the column already is. Detail lists every present host and unknown hosts."
    requirement: D-13
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_owner_cell_lists_hosts_and_truncates_when_wider_than_the_column"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_detail_lists_every_present_host_and_unprobed_hosts"
        status: pass
    human_judgment: false

duration: 50min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 12: Skill-pack catalog truth Summary

**Skill packs show a cached per-host Inst and Owner answer, probed once per launch in the background and marked stale until that probe lands.**

## Performance

- **Duration:** 50 min
- **Started:** 2026-10-10T14:35:00Z
- **Completed:** 2026-10-10T15:23:01Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `skills` lives on the existing version-cache envelope. A save that omits it keeps the key. Bad entries decode to `{}` for that tool.
- `refresh_skills` runs `inspect_skill_packs` once per launch, on the screen's full catalog, in its own worker. A second caller waits for the in-flight pass. An invalidate mid-pass stores nothing.
- Inst shows the last answer plus dim `~` until the probe lands, then the fresh mark. Owner lists hosts (`Claude Code, Pi`, or `Claude Code +2` when wider than the column). Detail lists every present host and `not probed:` for unknown ones.

## Task Commits

Each task was committed atomically:

1. **Task 1: probe, cache envelope, worker, tracer cells** - `bc7d96e` (feat)
2. **Task 2: stale Inst cell, Owner truncation, detail list** - `9c6d339` (feat)
3. **Task 3: once-per-launch, invalidate, pass lock** - `a701d1f` (test)

**Plan metadata:** this summary commit (`docs(16-12): summary for plan 16-12`)

## Files Created/Modified

- `installer/version_cache.py` - `skills` envelope encode/decode
- `installer/version_status.py` - `SkillHostStatus`, `refresh_skills`, `seed_skills_from_cache`, pass lock
- `installer/catalog_tui.py` - skill worker, Inst/Owner/detail rendering
- `setup.py` - `skill_probe=lambda argv: run_query(argv)` and composition-time seed
- `tests/test_version_cache.py` - envelope round-trip and malformed decode
- `tests/test_version_status.py` - once-per-launch, epoch discard, in-flight join
- `tests/test_catalog_tui.py` - tracer, D-12/D-13 cells, System-view-first launch path

## Decisions Made

- No `?` legend entry. Plain-text legend lines are 58/76/77. Line 1 must keep 11 free columns for plan 16-15's ` · ! broken`. ` · ? unknown` is 12 characters and would leave 8. Lines 2 and 3 have 2 and 1 free. Unknown hosts are explained by the detail pane's `not probed:`.
- `SkillStatusRefreshed` checks `generation` before clearing `skill_refreshing`, the same order as `on_version_status_refreshed`. A superseded worker must not clear the flag of the pass still in flight.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - correctness] Generation gate on the skill-refresh handler**

- **Found during:** Task 1 (worker message)
- **Issue:** The plan said the handler clears `skill_refreshing` and discards on epoch mismatch. The message also carries `generation`. Ignoring it would let a superseded worker clear the flag, and an unread field is dead code.
- **Fix:** Discard a mismatched generation before clearing the flag, matching `on_version_status_refreshed`.
- **Files modified:** `installer/catalog_tui.py`
- **Verification:** `test_skill_status_refreshed_discards_a_superseded_epoch` passes; epoch mismatch still skips the reload.
- **Committed in:** `bc7d96e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 correctness)
**Impact on plan:** The generation check is the version-refresh pattern the plan already cited. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Skill-pack rows answer "installed in which hosts" from a background probe. Plan 16-15 can add its broken-state legend entry on line 1; 11 columns remain free.
- Confirmed the System-view launch guard: temporarily calling `refresh_skills(self.tools)` failed `test_skill_probe_covers_packs_when_system_view_mounts_first` (`assert ['claude', 'plugin', 'list'] in []`). Restored `self._catalog` before commit.

## Verification

- `make validate` passed (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).
- `uv run pytest tests/test_version_cache.py tests/test_version_status.py tests/test_catalog_tui.py tests/test_setup.py -q` passed.
- `uv run pytest -q` passed (100%, skips only).

## Self-Check: PASSED

- `skills` envelope key, `refresh_skills` / `skill_status_of`, `group="skill-refresh"`, `refresh_skills(self._catalog)`, `skill_probe=` and `seed_skills_from_cache()` in setup.py are present.
- `skill_status_of` does no `load_` and takes no `self._lock`.
- `_skills_pass_lock` is created in `__init__` and used in `refresh_skills`, not in `invalidate` or `skill_status_of`.

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
