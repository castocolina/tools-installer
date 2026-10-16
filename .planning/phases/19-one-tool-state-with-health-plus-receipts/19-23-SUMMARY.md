---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "23"
subsystem: skill-lifecycle
tags: [skill-packs, gsd, symlink, claude-plugin, gap-closure]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: project-pack repo walk, D-18 Claude reasons and the hosts projection (19-07, 19-21)
provides:
  - a repo walk that admits a directory only when `.planning` itself lstats as a real directory
  - inconclusive handling for an unlistable GSD install (not checked, no step)
  - duplicate reasons with no enable or install step for surplus canonical user installs
  - `inspect_status` reading `inspect_skill_reports` after the hosts projection was deleted
affects: [phase-20-reconfigure, skill-pack-status]

actuals:
  tokens: 5638
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "an unlistable content dir is inconclusive, reported through ProjectPackReport.unchecked"
    - "a step is built only when the command can name exactly what it acts on"

key-files:
  created: []
  modified:
    - installer/skill_lifecycle.py
    - tests/test_skill_lifecycle.py

key-decisions:
  - "`_unreadable_install_dirs` takes the caller's `_installed_runtimes` answer so the probe runs once"
  - "surplus canonical user entries are `duplicate:` reasons and suppress both the install and the enable step"

patterns-established:
  - "Pattern: a failed directory read never classifies an install as empty"
  - "Pattern: test host answers come from `inspect_skill_reports` through the `_hosts` helper"

requirements-completed: [STATE-07]

coverage:
  - id: D1
    description: "The repo walk admits a GSD repo only when `.planning` lstats as a real directory holding a regular config.json"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_repo_walk_rejects_a_symlinked_planning_dir"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unlistable skills or commands dir is reported as not checked and earns no empty reason and no reinstall step"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_unreadable_install_dirs_are_not_checked_not_empty"
        status: pass
    human_judgment: false
  - id: D3
    description: "A conclusively empty install keeps its reinstall step"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_conclusive_empty_install_keeps_its_reinstall_step"
        status: pass
    human_judgment: false
  - id: D4
    description: "Two or more canonical user-scope Claude entries are duplicate reasons with no enable or install step"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_two_disabled_canonical_user_entries_get_no_enable_step"
        status: pass
    human_judgment: false
  - id: D5
    description: "The hosts projection is gone and every caller reads inspect_skill_reports"
    requirement: STATE-07
    verification:
      - kind: other
        ref: "grep -rnE inspect_skill_packs installer setup.py tests -> 0; uv run vulture exit 0"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 23: Skill-pack probe gap closure Summary

**The repo walk rejects a symlinked `.planning`, an unreadable install is reported as not checked, duplicate canonical user installs are named, and the dead hosts projection is gone**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-16T20:26:32Z
- **Completed:** 2026-10-16T20:33:18Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- A directory is a GSD repo only when `.planning` itself lstats as a directory and its `config.json` lstats as a regular file, so a symlink into another project never becomes a Phase 20 `cwd`.
- A runtime whose `gsd-core/VERSION` is present but whose `skills` or `commands` dir cannot be listed is inconclusive: no `is empty` reason, no `not installed in {repo}` reason, no install step, and each dir is reported through the existing `cannot read ~/{path}` note.
- Two or more canonical user-scope Claude entries each produce `duplicate: {id} in user scope ({version})` and neither an enable nor an install step.
- `inspect_skill_packs` is deleted; `inspect_status` and every test read hosts through `inspect_skill_reports`.

## Task Commits

Each task was committed atomically (tests and code together; no red commit):

1. **Task 1: the repo walk requires a real `.planning` dir, and an unreadable install is inconclusive, not empty (G27, G26)** — `86635c9` (fix)
2. **Task 2: duplicate canonical user installs are reported, and the unused hosts projection is deleted (G25, G16)** — `496714f` (fix)

**Plan metadata:** this commit (docs)

## Files Created/Modified

- `installer/skill_lifecycle.py` — `.planning` dir check in `_find_project_repos`; new `_unreadable_install_dirs`; inconclusive runtimes in `inspect_project_pack`; surplus canonical user entries in `_claude_fixes`; `inspect_status` over `inspect_skill_reports`; hosts projection deleted
- `tests/test_skill_lifecycle.py` — the three G27/G26 tests, the extended two-entry test, the disabled-duplicates test, and the `_hosts` helper replacing every projection call

## Decisions Made

- `_unreadable_install_dirs(repo, installed)` takes the caller's `_installed_runtimes` answer instead of calling it again. The plan's no-argument form re-invoked the probe, and `test_install_step_cwd_is_validated` monkeypatches that probe to delete the repo, so the second call raised `FileNotFoundError`. `_installed_runtimes`'s signature is unchanged, which is what the 19-21 tests patch.
- When more than one canonical user entry exists, both the install step and the enable step are suppressed. `claude plugin` takes an id and a scope, not a version, so neither step could say which copy to keep.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The new helper must not probe a second time**

- **Found during:** Task 1 (unreadable install)
- **Issue:** The plan specified `_unreadable_install_dirs(repo)` calling `_installed_runtimes` itself. `test_install_step_cwd_is_validated` replaces that function with one that deletes the repo, so the second call raised `FileNotFoundError` inside `shutil.rmtree`.
- **Fix:** The helper takes the caller's already-computed installed tuple and probes nothing itself.
- **Files modified:** `installer/skill_lifecycle.py`
- **Verification:** `uv run pytest tests/test_skill_lifecycle.py -q --no-cov` — 193 passed
- **Committed in:** `86635c9` (Task 1)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The helper's contract is unchanged for every caller; only the double probe went away. No scope creep.

## TDD RED evidence

Task 1, `uv run pytest tests/test_skill_lifecycle.py -q --no-cov -k "symlinked_planning or unreadable_install_dirs or conclusive_empty"` (2 failed, 1 passed):

```
test_repo_walk_rejects_a_symlinked_planning_dir
E  AssertionError: assert {.../home/git/a: (), .../home/git/b: ()} == {.../home/git/b: ()}
E  Left contains 1 more item: .../home/git/a

test_unreadable_install_dirs_are_not_checked_not_empty
E  assert not any("is empty" in reason for reason in report.reasons)
E  assert not True
```

`test_conclusive_empty_install_keeps_its_reinstall_step` passed before the change: a readable empty install already earned its reinstall step.

Task 2, `uv run pytest tests/test_skill_lifecycle.py -q --no-cov -k "two_enabled_user_entries or two_disabled_canonical"` (2 failed):

```
test_claude_two_enabled_user_entries_for_the_canonical_id_is_absent
E  AssertionError: assert () == ('duplicate: ... (6.4.1)', 'duplicate: ... (6.2.0)')

test_two_disabled_canonical_user_entries_get_no_enable_step
E  AssertionError: assert ('disabled: ... (6.4.1)', 'disabled: ... (6.2.0)') == ('duplicate: ...', 'duplicate: ...')
E  At index 0 diff: 'disabled: ...' != 'duplicate: ...'
```

G16 has no RED: it deletes `inspect_skill_packs` with unchanged behavior, proved by the green suite and the acceptance grep.

## Verify-command results

- Task 1 targeted pytest (`repo_walk`, `empty_install`, `install_steps`, `reinstall`, `one_real_runtime` plus the three new tests): 14 passed.
- Task 1 shrink guard: `tests/test_skill_lifecycle.py` 2181 → 2242 lines, tests 108 → 111; suppression comments 487 → 487.
- Task 1 `make validate` exit 0; `make test` exit 0 — 4522 passed, 4 skipped, 95.97%.
- Task 2 full file: 193 passed. Shrink guard: 2242 → 2244 lines (floor 2212), tests 111 → 111 (one deleted, one added). Suppressions 487 → 487.
- `grep -rnE "inspect_skill_packs" installer setup.py tests` (comments excluded): 0. `grep -c "inspect_skill_reports((tool,)" installer/skill_lifecycle.py`: 1. `uv run vulture` exit 0.
- Task 2 `make validate` exit 0; `make test` exit 0 — 4522 passed, 4 skipped, 95.97%.
- Plan verification `uv run pytest tests/test_skill_lifecycle.py tests/test_version_status.py -n auto -q --no-cov`: 356 passed.
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock`: no change.

## Size evidence

| File | HEAD before Task 1 | after Task 1 | final | diff vs plan base |
| --- | --- | --- | --- | --- |
| `installer/skill_lifecycle.py` | 959 | 993 | 991 | +32 |
| `tests/test_skill_lifecycle.py` | 2181 | 2242 | 2244 | +63 |

`git diff --stat 86635c9^..HEAD`: 2 files changed, 174 insertions, 79 deletions. Both files end in a newline. The diffs contain only the intended hunks.

## Planned updates

- Added: `test_repo_walk_rejects_a_symlinked_planning_dir`, `test_unreadable_install_dirs_are_not_checked_not_empty`, `test_conclusive_empty_install_keeps_its_reinstall_step`, `test_two_disabled_canonical_user_entries_get_no_enable_step`
- Extended: `test_claude_two_enabled_user_entries_for_the_canonical_id_is_absent` (reasons and empty steps)
- Renamed: `test_inspect_skill_packs_is_idempotent` → `test_skill_hosts_are_idempotent`
- Deleted: `test_inspect_skill_packs_is_the_hosts_projection`
- Rewritten through `_hosts`: `_claude_status` and every former projection call site (26)

## Issues Encountered

None beyond the double-probe deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 20 can trust a detected repo's `.planning` to be a real directory under HOME, and it will never be handed a reinstall step for an install whose content dirs could not be read.
- Duplicate canonical user installs stay reasons only; no step claims to choose the version to keep.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
