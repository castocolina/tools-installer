---
phase: 22-method-lifecycle-contract
plan: "12"
subsystem: manager-versions
tags: [brew, cask, auto-updates, greedy, outdated, update, version-cache, LIFE-10]

requires:
  - phase: 22-05
    provides: pinned-method predicate and the OMZ root resolver used by the pass
  - phase: 22-06
    provides: method_package in installer/model.py (the one package reader)
  - phase: 22-10
    provides: wave 5 state the refresh pass runs on
provides:
  - parse_brew_cask_auto_updates, brew_cask_auto_updates, brew_greedy_outdated (installer/manager_versions.py)
  - OutdatedReport.greedy and read_outdated(casks=...) with the greedy merge
  - VersionRefreshService.greedy_casks() published under the epoch guard
  - manager snapshot cache encodes and decodes the greedy set
  - resolve_update_argv(target, greedy=...), perform_update(greedy_casks=...), UpdateService(greedy_casks=...)
  - setup.py binds UpdateService to VersionRefreshService.greedy_casks
affects: [phase 23 CONF-07 (OMZ root alignment), LIFE-10 closure]

tech-stack:
  added: []
  patterns:
    - "a failed greedy read is None (unknown), never an empty set; the previous published facts are kept"
    - "tracked cask tokens computed in the pass from the registry (method_package), asked of brew on macOS only"

key-files:
  created: []
  modified:
    - installer/manager_versions.py
    - installer/version_cache.py
    - installer/version_status.py
    - installer/update.py
    - setup.py
    - .planning/REQUIREMENTS.md
    - tests/test_manager_versions.py
    - tests/test_version_status.py
    - tests/test_version_cache.py
    - tests/test_update.py
    - tests/test_setup.py

key-decisions:
  - "Greedy facts are asked only when a tracked cask declares auto_updates: true; one batched brew info plus at most one batched greedy brew outdated per pass (D-16, ledger Q5)"
  - "u uses --greedy-auto-updates (narrower than --greedy) and only for a cask whose package is in the published greedy set"
  - "greedy_casks() is not cleared by invalidate: the set names casks that auto-update, which a mutation does not change; the epoch guard keeps a raced pass from writing it"
  - "A failed greedy read on an aged snapshot keeps the previous cask map and greedy set (reloaded from the cache); after a mutation the cask reads unknown, never current (review R2-08)"
  - "OutdatedReport.greedy defaults to frozenset() so existing constructors mean 'no auto-updating cask'; _EMPTY_OUTDATED passes None (unknown)"

patterns-established:
  - "read_outdated returns greedy=None and cask=None together when the cask side is incomplete (review R1-23)"

requirements-completed: [LIFE-10]

coverage:
  - id: D1
    description: "On macOS an auto-updating tracked cask that brew reports greedy-outdated reads OUTDATED (tier row `↑`)"
    requirement: "LIFE-10"
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_a_greedy_outdated_cask_is_outdated_on_its_tier"
        status: pass
      - kind: unit
        ref: "tests/test_manager_versions.py#test_an_auto_updating_cask_reads_greedy_outdated"
        status: pass
    human_judgment: false
  - id: D2
    description: "u on that cask runs brew upgrade --cask --greedy-auto-updates --appdir=<dir> <cask>; other casks and formulae never get the flag"
    requirement: "LIFE-10"
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_u_on_an_auto_updating_cask_runs_the_greedy_upgrade"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_a_non_auto_updating_cask_never_gets_the_greedy_flag"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_greedy_is_cask_only"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_the_composition_root_binds_greedy_casks"
        status: pass
    human_judgment: false
  - id: D3
    description: "Linux is unchanged: no brew info and no greedy argv off macOS"
    requirement: "LIFE-10"
    verification:
      - kind: unit
        ref: "tests/test_manager_versions.py#test_linux_makes_no_greedy_query"
        status: pass
    human_judgment: false
  - id: D4
    description: "A failed greedy read is unknown, not nothing outdated; an aged snapshot keeps its result and a post-mutation read is unknown, never current"
    requirement: "LIFE-10"
    verification:
      - kind: unit
        ref: "tests/test_manager_versions.py#test_a_failed_greedy_read_is_not_nothing_outdated"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_a_transient_greedy_failure_on_an_aged_snapshot_keeps_the_previous_result"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_a_greedy_failure_after_invalidate_reads_unknown_not_current"
        status: pass
    human_judgment: false
  - id: D5
    description: "The greedy set follows the published pass, survives the version cache, and a current greedy cask is SKIP and runs nothing"
    requirement: "LIFE-10"
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_greedy_casks_follows_the_published_pass"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_a_reloaded_snapshot_keeps_the_greedy_outdated_row"
        status: pass
      - kind: unit
        ref: "tests/test_version_cache.py#test_greedy_round_trips_through_the_cache"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_a_current_greedy_cask_is_skipped_and_runs_nothing"
        status: pass
    human_judgment: false

duration: ~3h
completed: 2026-11-04
status: complete

actuals:
  tokens: 9340    # chars/4 over the realized plan diff (git diff c30c9de..HEAD = 37363 bytes)
  tasks: 3
  commits: 3      # MEASURED: git rev-list --count c30c9de..HEAD
plan_head_before: c30c9de257c602f2fe5ef055aa1b1ef6435849bd
plan_head_after: c05f538ad689ad45d494114901e144ad0ac1c7c5
---

# Phase 22 Plan 12: Greedy upgrade for auto-updating casks on macOS Summary

**One batched `brew info --cask` and, only when a tracked cask auto-updates, one greedy `brew outdated`: auto-updating casks read OUTDATED and `u` upgrades them with `--greedy-auto-updates`**

## Performance

- **Duration:** ~3h (includes the full-suite runs; three gates)
- **Tasks:** 3 of 3
- **Commits:** 3 (Task 1 feat, Task 2 feat, Task 3 test-only)
- **Files modified:** 11

## Accomplishments

- Refresh pass learns the auto-updating tracked casks from one batched `brew info --cask --installed --json=v2` and asks one greedy `brew outdated --cask --greedy-auto-updates --json=v2` only when a tracked cask auto-updates (macOS only).
- Greedy outdated rows are merged into the cask map only for tracked auto-updating tokens; the tier shows `↑` (SPEC R12 acceptance).
- `u` on an auto-updating cask runs `brew upgrade --cask --greedy-auto-updates --appdir=<dir> <cask>`; non-auto-updating casks and formulae keep their argv.
- A failed brew info or greedy read is `None` (unknown) for both `greedy` and `cask`; an aged snapshot keeps its previous facts, and a post-mutation read reads unknown, never current.
- `greedy_casks()` follows the last published pass; the set survives the version cache.
- LIFE-10 wording in `.planning/REQUIREMENTS.md` names the decided flags.

## Task Commits

1. **Task 1: one greedy brew query for auto-updating casks on macOS** - `1644744` (feat)
2. **Task 2: the greedy upgrade argv for auto-updating casks** - `2155089` (feat, includes the LIFE-10 wording fix)
3. **Task 3: pin the greedy cache shape and the current-cask skip** - `c05f538` (test-only)

## Files Created/Modified

- `installer/manager_versions.py` - `parse_brew_cask_auto_updates`, `brew_cask_auto_updates`, `brew_greedy_outdated`, `_greedy_cask_read`, `OutdatedReport.greedy`, `read_outdated(casks=...)`
- `installer/version_status.py` - `_tracked_casks`, `_merge_outdated` greedy, `_EMPTY_OUTDATED.greedy=None`, `_load_or_query_snapshot(casks=...)`, `_partial_manager_failure` greedy term, `_pass` publish block writes `_greedy` under the epoch guard, `greedy_casks()`
- `installer/version_cache.py` - encode `greedy` as a sorted list (null = unknown); decode missing as empty, malformed as empty
- `installer/update.py` - `resolve_update_argv(..., greedy=False)`, `perform_update(..., greedy_casks=...)`, `UpdateService(greedy_casks=...)`
- `setup.py` - `UpdateService(..., greedy_casks=version_refresh.greedy_casks)`
- `.planning/REQUIREMENTS.md` - LIFE-10 line names `--greedy-auto-updates`
- tests: `tests/test_manager_versions.py`, `tests/test_version_status.py`, `tests/test_version_cache.py`, `tests/test_update.py`, `tests/test_setup.py`

## Decisions Made

- Greedy facts are asked only when a tracked cask declares `auto_updates: true` (D-16, ledger Q5).
- `--greedy-auto-updates` is used, not `--greedy`, so `version :latest` casks keep the plain path.
- `invalidate` does not clear `greedy_casks()` (R1-22 sign-off): the set names auto-updating casks, which a mutation does not change.
- A failed greedy read on an aged snapshot keeps the previous result; after a mutation it reads unknown (R2-08).

## Test Evidence

### RED (Task 1, before implementation)

`uv run pytest tests/test_manager_versions.py tests/test_version_status.py -k "greedy or auto_updating" -q --no-cov -n 0` -> 12 failed (the new items: 7 in test_manager_versions including 4 parametrized cases, 5 in test_version_status), for example:

```
FAILED tests/test_manager_versions.py::test_an_auto_updating_cask_reads_greedy_outdated
FAILED tests/test_manager_versions.py::test_no_auto_updating_tracked_cask_means_no_greedy_query
FAILED tests/test_manager_versions.py::test_linux_makes_no_greedy_query - AttributeError
FAILED tests/test_manager_versions.py::test_a_failed_greedy_read_is_not_nothing_outdated[info-not-json]
FAILED tests/test_manager_versions.py::test_a_failed_greedy_read_is_not_nothing_outdated[entry-without-token]
FAILED tests/test_manager_versions.py::test_a_failed_greedy_read_is_not_nothing_outdated[greedy-raises]
FAILED tests/test_manager_versions.py::test_a_failed_greedy_read_is_not_nothing_outdated[greedy-not-json]
FAILED tests/test_version_status.py::test_a_greedy_outdated_cask_is_outdated_on_its_tier
FAILED tests/test_version_status.py::test_greedy_casks_follows_the_published_pass
FAILED tests/test_version_status.py::test_a_transient_greedy_failure_on_an_aged_snapshot_keeps_the_previous_result
FAILED tests/test_version_status.py::test_a_greedy_failure_after_invalidate_reads_unknown_not_current
FAILED tests/test_version_status.py::test_a_reloaded_snapshot_keeps_the_greedy_outdated_row
```

### RED (Task 2, before implementation)

`uv run pytest tests/test_update.py tests/test_setup.py -k "greedy" -q --no-cov -n 0` -> 4 failed, each on the missing keyword (`UpdateService.__init__() got an unexpected keyword argument 'greedy_casks'`, or `record() missing 1 required keyword-only argument: 'greedy_casks'`):

```
FAILED tests/test_update.py::test_u_on_an_auto_updating_cask_runs_the_greedy_upgrade
FAILED tests/test_update.py::test_a_non_auto_updating_cask_never_gets_the_greedy_flag
FAILED tests/test_update.py::test_greedy_is_cask_only - TypeError: UpdateServ...
FAILED tests/test_setup.py::test_the_composition_root_binds_greedy_casks - TypeError ...
```

### RED (Task 3)

Not a RED run. All three Task 3 tests passed on the first run against the Task 1 tree: `test_greedy_round_trips_through_the_cache`, `test_a_missing_or_malformed_cached_greedy_decodes_empty` (added), and `test_a_current_greedy_cask_is_skipped_and_runs_nothing`. They are regression guards, as the plan allows. No installer change was needed, so Task 3 is test-only.

### GREEN

- Task 1 targeted: `-k "greedy or auto_updating"` -> 12 passed, exit 0.
- Task 1 full gate: `make test` -> 5504 passed, 4 skipped, coverage 96.28%, exit 0. `make validate` exit 0 on the tree before commit.
- Task 2 targeted: `-k greedy` on test_update and test_setup -> 4 passed, exit 0.
- Task 2 full gate: `make test` -> 5508 passed, 4 skipped, coverage 96.29%, exit 0. `make validate` exit 0.
- Task 3 targeted: 3 passed, exit 0. Full gate: `make test` -> 5511 passed, 4 skipped, coverage 96.29%, exit 0. `make validate` exit 0.

### Test counts (floors)

- Start (measured with `pytest --co`): 5496 collected (ledger: 5492 passed + 4 skipped).
- End: 5515 collected (5511 passed + 4 skipped). Delta +19 = 12 (Task 1) + 4 (Task 2) + 3 (Task 3).

## Deviations from Plan

### Changed existing tests (required by the plan's new macOS read)

1. **`tests/test_version_status.py::_counting_query`** - added an answer for `brew info --cask` (an empty casks payload). Reason: the pass now issues `brew info --cask --installed` on macOS whenever a cask tool is tracked. The old fixture answered `{}`, which would fail the cask read.
2. **`tests/test_version_status.py::test_stale_manager_snapshot_requeries_seven_plus_one`** - query count 7 -> 8. Reason: the one extra batched `brew info --cask` read from item 1 (the pass includes a cask tool).
3. **`tests/test_version_status.py::test_group_check_makes_no_extra_query`** - query count 7 -> 8. Same reason.

The two other `== 7` count tests use a brew-only tool list, so no cask is tracked and they are unchanged.

### Auto-fixed issues

**1. [Rule 2 - Clarity] `_partial_manager_failure` greedy term is redundant**
- **Found during:** Task 1
- **Issue:** `read_outdated` sets `cask=None` whenever it sets `greedy=None`, so the existing `outdated.cask is None` term already trips the partial-failure check.
- **Fix:** Added `or outdated.greedy is None` anyway, to state the R1-23 intent in the check itself.
- **Committed in:** `1644744`

**2. [Rule 3 - Blocking] Pyright and formatter fixes in new test and source code**
- Untyped `frozenset()` fallback in `_pass` -> `frozenset[str]()`.
- Untyped `**_kwargs` lambda for `read_inventory_fn` -> a typed `_vscode_inventory` function.
- `on_info` lambda returned `int` (from `invalidate`) -> a `race()` function returning `None`.
- Tuple of greedy values in the cache test annotated; `which` lambda in the setup test replaced by a typed `no_which`.
- Formatter reflowed new lines.
- **Committed in:** `1644744`, `2155089`, `c05f538`

**3. [Added test] `test_a_missing_or_malformed_cached_greedy_decodes_empty`** - not in the plan's behavior list; the plan's Task 3 item says the cache edge cases are pinned, so it covers the "missing or malformed decodes empty" clause explicitly. Passes on first run. Committed in `c05f538`.

**4. [Test shape] `test_the_composition_root_binds_greedy_casks` checks the `greedy_casks` kwarg reaching `perform_update`**, not the argv. The argv itself is pinned in `test_update.py` (`test_u_on_an_auto_updating_cask_runs_the_greedy_upgrade`). This keeps the setup test off the real runner.

**Total deviations:** 4 (1 clarity check, 1 pyright/format cleanup, 1 added test, 1 test shape) plus the 3 changed count assertions, all listed above. **Impact on plan:** none to scope; no new dependency, no new module.

## Issues Encountered

- A compound `git` command (`git rev-parse ... && git log ...`) and a `(...)` subshell were refused by the worktree guard; re-ran them as separate plain commands from the worktree root. No effect on the commits.
- `codegraph explore` served the main checkout (a different worktree), so all reads and edits went through the worktree files directly.

## Not verified / residuals

- Real brew was never run (fixtures only, per the project rules). The `auto_updates` boolean contract and the flag spellings come from the plan's research and ledger Q5, not from a live `brew` call on macOS.
- `greedy_casks()` is empty from process start until the first published pass; the cache carries the set across restarts.
- A cache written before this change has no `greedy` key and decodes as an empty set, so an auto-updating cask reads current until the next 6-hour query. A plain upgrade of an existing install therefore shows the greedy row up to 6 hours late.
- The tracked casks are computed from the `tools` passed to `refresh`. Both call sites (`app.py:129`, `wizard_app.py:3126`) pass the full catalog; a future partial refresh would narrow the greedy set (not enforced).
- No STATE.md or ROADMAP.md changes (orchestrator owns them).

## Next Phase Readiness

- LIFE-10 code path complete for macOS. A live check on a Mac with VS Code installed (`brew info --cask --installed --json=v2`, `brew outdated --cask --greedy-auto-updates --json=v2`) is still worth a manual run before closing the requirement in the UAT pass.

---
*Phase: 22-method-lifecycle-contract*
*Completed: 2026-11-04*

## Self-Check: PASSED
