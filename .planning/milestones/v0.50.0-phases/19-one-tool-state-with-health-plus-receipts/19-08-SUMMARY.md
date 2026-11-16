---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "08"
status: complete
subsystem: core
tags: [tool-state, health, refresh, concurrency, single-flight, brew, skill-packs, tdd]

requires:
  - phase: 19-01
    provides: autouse sandboxed_bin_dir (locations.bin_dir), receipts.Receipt
  - phase: 19-02
    provides: status.is_installed(..., default_bin_dir=)
  - phase: 19-03
    provides: Health, Evidence, tool_health
  - phase: 19-07
    provides: model.ConfigStep
provides:
  - "ToolState (tool_id, generation, seq, health, reasons, ownership, version, skill_hosts, receipt, removable, unconfigured; `present` property)"
  - "tool_state(...) pure builder: availability from resolve_methods with the pass platform, NEEDS_BREW_REASON when unavailable_reason has no answer, keyword-only `checking` forwarded to Evidence, absent tools keep misconfigured facts as the first notes"
  - "BROKEN_SHIM_REASON, NEEDS_BREW_REASON, SKILL_CHECKING_REASON, SKILL_SEEDED_NOTE"
  - "VersionRefreshService.state_of / is_present / warning, present= constructor kwarg, managed_bin_dir default via installer.locations.bin_dir(None)"
  - "seq-gated one-swap publication, single-flight join keyed by tool-id set + epoch, overtaken passes publish nothing, cache saved after the swap for published records only"
  - "has_brew re-read per pass into one pass-local platform; fresh manager snapshot reused only when its brew evidence agrees"
  - "skill-pack states CHECKING until probed, rebuilt by refresh_skills in the same generation"
  - "default_skill_home() + autouse conftest sandboxed_skill_home"
affects: [19-09, 19-10, 19-11, 19-12, 19-13, 19-15, 19-18]

actuals:
  tokens: 15600
  tasks: 3
  commits: 3
plan_head_before: 22c5dcb00ea0a33f624b81a7f05b5c8bf3db70aa
plan_head_after: 2e703f19ae10fdd0d7b1067483d7d9dcd61eafa2

tech-stack:
  added: []
  patterns:
    - "publish-by-assignment snapshot dict (never mutated) read without a lock, record first then epoch"
    - "single flight: (epoch, seq, Event, outcome) per in-flight tool-id set; outcome set before the Event in a finally"
    - "one pass-local Platform handed to every helper of the pass"
    - "concurrency tests hold a pass on an Event inside an injected resolve_tag; threads run through concurrent.futures so no broad except is needed"

key-files:
  created:
    - .planning/phases/19-one-tool-state-with-health-plus-receipts/19-08-SUMMARY.md
  modified:
    - installer/version_status.py
    - tests/test_version_status.py
    - tests/conftest.py
    - tests/test_wizard_app.py

key-decisions:
  - "A record is replaced only when the current one is missing or has a lower seq; seq is global and taken with the epoch under one lock, so an older generation's record always has a lower seq than any current-epoch pass"
  - "A pass whose fresh set is empty (fully overtaken) assigns nothing and writes no cache at all, manager snapshot included"
  - "Skill-pack states are built inside the commit critical section from self._skills, so the host answers and the publication come from one moment"
  - "sandboxed_skill_home mirrors sandboxed_bin_dir: it redirects only while HOME is the real home, so tests that set HOME keep reading that scratch HOME"
  - "The default presence helper is named _default_present (not _installed) because a test_execute_screen subclass already defines _installed"

requirements-completed: [STATE-01, STATE-05]

duration: ~75min
completed: 2026-10-16
---

# Phase 19 Plan 08: One ToolState per tool with seq-gated one-swap publication Summary

`VersionRefreshService` now builds one `ToolState` per tool per pass through the pure `tool_state` builder (which delegates the decision to `tool_health`), publishes the whole pass with one dict assignment, and serves it through `state_of`. The publication is ordered by a monotonic pass sequence. Identical concurrent passes share one flight. Brew is re-read on every pass. Skill packs stay CHECKING until they are probed.

## Tasks

| Task | Commit | What |
|------|--------|------|
| 1 (tracer) | 52df37f | `ToolState`, `tool_state`, `BROKEN_SHIM_REASON`, `NEEDS_BREW_REASON`, `state_of` (record first, epoch second), `is_present`, `present=` kwarg whose default is `is_installed(tool, which=self._which, default_bin_dir=self._managed_bin_dir)`, `managed_bin_dir` default through `installer.locations.bin_dir(None)`, one-swap publication in `refresh` |
| 2 | e2a4dbf | `self._seq` taken with `started_epoch` in one critical section; single flight in `_inflight` keyed by `frozenset` of ids (a joiner waits and returns, or re-raises, the shared outcome); `refresh` split into admission + `_pass`; raced pass publishes nothing (the raced `_statuses.update(statuses)` is deleted); per-record newest-wins `fresh` merge; best-effort cache save after the swap for `fresh` records only, `OSError` -> `warning` |
| 3 | 2e703f1 | Pass-local `platform = replace(self._platform, has_brew=self._which("brew") is not None)`, published as `service.platform` and passed to `_load_or_query_snapshot`, `_partial_manager_failure`, `resolve_ownership`, `github_repo`, `resolve_status`, `tool_state`; snapshot reuse requires agreeing brew evidence or `failed_at`; `_skill_state` (CHECKING via `checking=`, stale-host note) built at commit and rebuilt by `refresh_skills`; absent tools keep configuration facts as the first notes; `default_skill_home()` + conftest `sandboxed_skill_home` |

The tracer gate passed: Task 1's `<verify>` was rerun end-to-end (13 targeted tests, the signature check, and the full suite) before Task 2 started.

## TDD RED evidence

Task 1 (tests appended first, run before any source change):
```
E   ImportError: cannot import name 'BROKEN_SHIM_REASON' from 'installer.version_status'
```

Task 2 (9 of the 10 new tests failed against the Task 1 code; `test_join_never_crosses_an_invalidate` already held there):
```
FAILED test_overtaken_pass_publishes_nothing         (state_of('a') is not the captured object: A's late merge replaced B's record)
FAILED test_overtaken_by_invalidate_publishes_nothing (assert {'a': VersionStatus(...), ...} == {}: the raced status merge)
FAILED test_partial_pass_merges_into_the_full_snapshot (assert 0 > 0: no seq yet)
FAILED test_older_full_pass_fills_tools_a_newer_partial_pass_did_not_cover
FAILED test_pass_sequence_is_monotonic_across_threads  (assert 1 == 10: len({0}))
FAILED test_identical_passes_share_one_flight          (assert False = is_alive(): no join)
FAILED test_a_failed_shared_pass_raises_in_every_joiner
FAILED test_cache_save_failure_keeps_states_and_sets_warning (OSError: disk full escaped)
FAILED test_only_published_records_are_cached       ({'a': '9.9.9', ...} != {'a': '2.0.0', ...})
```

Task 3 (first an `ImportError` for `default_skill_home`; with only that function added, 10 tests failed):
```
FAILED test_has_brew_is_reread_each_pass[no-snapshot]
FAILED test_has_brew_is_reread_each_pass[fresh-snapshot-without-brew]
FAILED test_manager_snapshot_query_uses_the_live_has_brew
FAILED test_a_pass_uses_one_platform_throughout
FAILED test_skill_pack_without_data_is_checking
FAILED test_skill_pack_states_follow_refresh_skills
FAILED test_refresh_skills_superseded_rebuilds_nothing
FAILED test_seeded_skill_hosts_are_a_note
FAILED test_absent_pack_keeps_configuration_facts_as_reasons
FAILED test_suite_sandbox_redirects_skill_home
```

## Verify results

- Task 1: `uv run pytest tests/test_version_status.py -q --no-cov` green (60). `-k "tool_state or state_of or ..."` 13 passed (needs 12 or more). `inspect.signature` check for `checking`: ok.
- Task 2: full file green (70). `-k "overtaken or ... or shared_pass"` 14 passed (needs 12 or more). The concurrency subset passed 10 of 10 repetitions; this was rerun on the amended Task 2 tree (see Deviations).
- Task 3: full file green (80). `-k "has_brew or ... or redirects_skill_home"` 10 passed (needs 10 or more). Suppression count across `installer/*.py setup.py tests/*.py`: 598 at base, 598 now.
- Plan-level checks: `uv run pytest tests/test_version_status.py -n auto -q --no-cov` is green. `make validate` passes and `make test` gives 4202 passed, 4 skipped, coverage 95.75%. `git diff fde3e68 -- pyproject.toml uv.lock` is empty.
- Acceptance greps:
  - `def state_of` 1, `class ToolState` 1, `self._states = ` 2 (3 at most allowed).
  - `default_bin_dir=self._managed_bin_dir` 1. `Path.home() / ".local" / "bin"` 0 outside comments.
  - `self._statuses.update(statuses)` 0, `def warning` 1, `_inflight` 5.
  - `has_brew=self._which("brew") is not None` 1, `def default_skill_home` 1, `sandboxed_skill_home` in conftest 1, `self._platform.has_brew` 0.

Large-file evidence (base 22c5dcb -> HEAD):
```
installer/version_status.py   852 -> 1127 lines
tests/test_version_status.py 2041 -> 2969 lines, test functions 47 -> 79
git diff --stat 22c5dcb HEAD:
 installer/version_status.py  | 395 +++++++++++++++---
 tests/conftest.py            |  24 +-
 tests/test_version_status.py | 930 ++++++++++++++++++++++++++++++++++++++++++-
 tests/test_wizard_app.py     |   3 +
 4 files changed, 1290 insertions(+), 62 deletions(-)
```
Before each commit, the test file's diff was only additions plus import-line changes. Both files end in a newline.

## Deviations from Plan

1. **[Rule 3 - Blocking] tests/test_wizard_app.py (outside files_modified).** `test_version_navigation_discards_a_superseded_generation` waited for a second pass over the same `[user-tool]` set at the same epoch. With single flight that second pass joins the first one, so the test hung on `second_started`. The plan says to convert such tests. The catalog always refreshes a tier's full tool set, so the test cannot use distinct sets. Instead it calls `service.invalidate(reason="test")` between the two user-tier entries, which gives the second entry its own pass. The UI-generation discard it checks is unchanged. This is a 3-line change in commit e2a4dbf. **The orchestrator should watch this file for rebase conflicts.**
2. **[Rule 1] Default presence helper renamed to `_default_present`.** The plan has no name for it. `_installed` collided with an attribute that a `test_execute_screen.py` subclass assigns, which pyright rejected.
3. **[CLAUDE.md coherent commits] Task 2 commit amended once.** The first Task 2 test helper caught `BaseException` with a `# noqa: BLE001`, which goes against the plan's no-new-suppression rule. I amended the Task 2 commit so the helper uses `concurrent.futures`, with no broad except and no noqa. To do that I set the Task 3 working files aside as scratch copies, checked out the Task 2 versions of the three files, and reran `make validate`, `make test` and the 10-repetition guard on the exact amended tree. Then I restored the Task 3 files. No `git stash` was used.
4. **`sandboxed_skill_home` redirects only while HOME is the real home.** This mirrors `sandboxed_bin_dir`. The plan said to patch unconditionally. A test that redirects HOME already reads scratch, and keeping that HOME stops tests that plant skill evidence under a fake HOME from breaking. The plan's test, which sets no monkeypatch, still gets the per-test scratch dir.
5. **`test_suite_sandbox_redirects_skill_home` calls `version_status.default_skill_home()` through the module.** A name imported at test-module import time would bypass the fixture's patch.
6. **The truncation guard was run as plain commands.** The sandbox refused the plan's `bash -c` guard because its scratch path contains "git". The same checks ran as separate commands against saved HEAD copies: `wc -l`, `grep -c "^def test_"`, a trailing-newline check, and `git diff --stat`.
7. **CodeGraph was not used.** The worktree has no index. Code was read directly.

## Issues for the orchestrator

- Plans that add skill facts later (misconfigured, unconfigured, broken from 19-11/19-12) must also feed `_skill_state`. `refresh_skills` rebuilds pack records from ownership, version and removable only, so any extra facts a pass attached to a pack would be dropped on rebuild until those plans route them through `_skill_state`.
- `ToolState.receipt` is always `None` for now: no pass supplies receipts yet (19-09/19-10).
- The transitional readers (`statuses`, `ownership_of`, `skill_status_of`) are still in place and answer from the same commit.

## Self-Check: PASSED

- installer/version_status.py, tests/conftest.py, tests/test_version_status.py, tests/test_wizard_app.py exist and are committed.
- Commits 52df37f, e2a4dbf, 2e703f1 are ancestors of HEAD (`git rev-list --count 22c5dcb..HEAD` = 3 before this summary commit).
