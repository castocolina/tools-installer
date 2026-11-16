---
phase: 23-configuration-as-a-lifecycle-step
plan: "02"
subsystem: settings
tags: [settings-splice, json, jsonc, toml, compare-before-commit, atomic-write]

# Dependency graph
requires:
  - phase: 17-atomic-writes-and-compare-before-commit
    provides: atomic_write_text and the snapshot-based compare-before-commit rule (shellrc.py)
  - phase: 18-registry-truth-and-drift-guard
    provides: the guarded splice precedent (verify_registry.apply_registry_edits re-parse guard)
provides:
  - installer/agent_settings.py: guarded text splice for JSON, JSONC and TOML settings (insert one key, re-parse, write only if the result equals the old document plus that key; byte-identical revert)
  - installer/atomic.py: FileSnapshot, read_snapshot, snapshot_matches (the one compare-before-commit primitive, promoted from shellrc)
affects: [23-06 settings API and config-write ledger, 23-07, 23-11, 23-15]

# Actuals (#2632)
actuals:
  tokens: 9430   # chars/4 over the realized diff (git diff 97b9e0b HEAD = 37721 chars)
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One private _guarded(new_text, fmt, expected) re-parse guard, shared by insert, remove and replace"
    - "Scanner walks a cleaned text (JSONC comments and trailing commas blanked, same length); edits land on the original text"
    - "Type-strict same_value: 1 == True never matches"

key-files:
  created:
    - installer/agent_settings.py
    - tests/test_agent_settings.py
  modified:
    - installer/atomic.py
    - installer/shellrc.py
    - tests/test_atomic.py
    - tests/test_shellrc.py

key-decisions:
  - "Guarded splice for every format, no format library (D-07). json and tomllib parse; the splice and the guard are ours."
  - "Revert removes the recorded fragment when it occurs once and the located member is in it; otherwise the located member is cut with its comma (a vendor re-serialization still reverts)."
  - "A two-part key whose parent is absent creates the parent as one member; a one-line object takes the key on its `{` line; an empty object takes it on a new line indented from its parent."
  - "TOML: top-level bare keys with string or boolean values only, placed before the first table header or at the end; anything else is refused. A splice into an array fails the re-parse guard."
  - "Compare-before-commit: write_if_unchanged checks identity and bytes right before atomic_write_text and raises SettingsChanged; a symlinked settings file is edited through its target and the link is kept."

patterns-established:
  - "Edit-then-reparse: every write path parses its result and refuses unless it equals the expected document"

requirements-completed: [CONF-08, CONF-09, CONF-12]  # engine only: the user-facing behaviour of these requirements lands with 23-06's API

# Metrics
duration: approx. 3h 20m (plan start time not recorded; worktree checkout 01:05 UTC, finish 04:26 UTC)
completed: 2026-11-07
status: complete
---

# Phase 23 Plan 02: Settings splice engine Summary

**Guarded text splice for JSON, JSONC and TOML settings: one key goes in or comes out byte-identical, comments and unrelated keys survive, and nothing is written unless the re-parsed result equals the old document plus that key.**

## Performance

- **Duration:** approx. 3h 20m (start not recorded; see metrics)
- **Started:** not recorded (worktree checkout 2026-11-07T01:05Z)
- **Completed:** 2026-11-07T04:26Z (last commit e8f5dee)
- **Tasks:** 3 of 3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- `installer/agent_settings.py` (new): `insert_key`, `remove_key`, `replace_value`, `new_file_text`, `parse_settings`, `strip_jsonc`, `lookup`, `same_value`, `read_settings`, `write_if_unchanged`, `delete_if_unchanged`, the errors `SettingsParseError` / `SettingsEditRefused` / `SettingsChanged`, the `ABSENT` sentinel and `CHANGED_WHILE_WRITING`.
- A Claude-shaped `settings.json` gains two keys and gives them back byte-identical; a re-serialized file still loses only our member.
- A VS Code-shaped JSONC file keeps its header comment, block comment, trailing comma and user key through insert and revert.
- Codex TOML takes `approval_policy` and `sandbox_mode` before the first table, and gives them back byte-identical.
- An invalid file is refused with its format and position (`not valid JSON (line 1, column 9)`, `not valid TOML (line 1, column 5)`), and its bytes are never written.
- `installer/atomic.py` now owns `FileSnapshot`, `read_snapshot` and `snapshot_matches`; `installer/shellrc.py` imports them and its private copies are deleted (behaviour unchanged, its existing tests stay green).

## Task Commits

1. **Task 1: JSON splice with byte-identical revert** - `ab0aef8` (feat)
2. **Task 2: JSONC splice keeps comments and trailing commas** - `b4d8d8d` (feat)
3. **Task 3: TOML splice and compare-before-commit writes** - `e8f5dee` (feat)

Each task is one commit holding its tests and its code, made after RED and GREEN runs. `make validate` and `make test` exited 0 before each commit.

## Files Created/Modified

- `installer/agent_settings.py` (new) - the splice engine (JSON, JSONC, TOML), the guard, the CAS write helpers
- `tests/test_agent_settings.py` (new) - 20 tests
- `installer/atomic.py` - `FileSnapshot`, `read_snapshot`, `snapshot_matches` promoted from shellrc
- `installer/shellrc.py` - imports the promoted helpers; private `_Snapshot`, `_snapshot`, `_snapshot_matches` deleted
- `tests/test_atomic.py` - imports plus `test_snapshot_matches_refuses_a_swapped_file`
- `tests/test_shellrc.py` - two monkeypatch targets repointed (see Deviations)

## Decisions Made

- No format library, per D-07 and the 18 D-09 precedent. `json` and `tomllib` parse; the splice and the guard are ours. No new dependency.
- The scanner runs on a cleaned text where JSONC comments and trailing commas are blanked to spaces. Positions and newlines are unchanged, so error positions stay true and edits land on the original text.
- The re-parse guard is written once (`_guarded`) and is used by insert, remove and replace.
- Revert prefers the recorded fragment. The located member is only cut when the fragment is not unique or does not hold the member.
- TOML scope is deliberately narrow: top-level bare keys, string or boolean values. Other values are refused, not approximated.

## Deviations from Plan

### Process deviations (no code impact)

**1. [Process] Plan-start commit ledger not written before the first commit**
- **Found during:** Task 1 commit (protocol step 0c)
- **Issue:** `$(git rev-parse --git-dir)/gsd-plan-head-before-23-02` was not created before `ab0aef8`.
- **Fix:** `commits:` is measured explicitly against the plan base instead: `git rev-list --count 97b9e0b..HEAD` = 3. `plan_head_before` is the base `97b9e0b418d4947f60e375e5613978007dfcc10b`; `plan_head_after` is `e8f5deed26f84395c62ec134def2c83c87843c31`.
- **Committed in:** not applicable (SUMMARY only)

**2. [Process] Spawn-time worktree sentinel could not be written**
- **Found during:** pre-commit safety checks (protocol 0a)
- **Issue:** the harness refused a write of `gsd-spawn-toplevel` under the shared `.git` directory.
- **Fix:** the cwd-drift check was done as a direct comparison: before each of the three commits `git rev-parse --show-toplevel` equalled `/var/home/bazzite/git/personal/tools-installer/.claude/worktrees/agent-a32df92e2e7b1d01b`.
- **Committed in:** not applicable

**3. [Process] codegraph index belongs to the main checkout**
- **Found during:** Task 1 start (codegraph explore)
- **Issue:** the worktree has no `.codegraph/`; `codegraph explore` answered from the main checkout's index and warned about it.
- **Fix:** I read the worktree files directly for every edit. I did not run `codegraph init` in the worktree.

### Auto-fixed issues

**4. [Rule 2 - Missing critical test] Extra JSONC cut test**
- **Found during:** Task 2 (manual check of the cut path)
- **Issue:** the cut path for a last member with a trailing comma and comments had no test; the plan's Task 2 list only exercises the fragment path.
- **Fix:** added `test_a_member_cut_without_its_fragment_takes_its_comma_and_keeps_comments`.
- **Files modified:** `tests/test_agent_settings.py`
- **Committed in:** `b4d8d8d`

**5. [Rule 2 - Missing critical test] Refusal branches for TOML scope**
- **Found during:** Task 3
- **Issue:** the TOML refusals (nested key, non-bare key, integer value, in-place replace) are branches I added and had no test.
- **Fix:** asserted inside `test_codex_toml_round_trip_inserts_before_the_first_table`.
- **Committed in:** `e8f5dee`

### Existing tests changed (listed per the executor rules)

- `tests/test_shellrc.py::test_refuses_when_the_snapshot_cannot_be_read` - monkeypatch target `installer.shellrc._snapshot` changed to `installer.shellrc.read_snapshot`. **Reason:** the helper moved to `installer/atomic.py` (plan Task 1, review R1-12).
- `tests/test_shellrc.py::test_guard_refuses_when_the_file_changes_while_it_is_being_guarded` - monkeypatch target `installer.shellrc._snapshot_matches` changed to `installer.shellrc.snapshot_matches`. **Reason:** same promotion (R1-12).
- No test was deleted.

**Total deviations:** 5 (3 process, 2 Rule 2 test additions). **Impact on plan:** none to the delivered behaviour; the two extra tests cover branches the plan's own list did not reach.

## Issues Encountered

- **Intermediate states (not released, each commit green):** Task 1 refused an empty object and a whitespace-only file as "not supported yet"; Task 2 lifted the empty-object restriction; TOML raised `NotImplementedError` until Task 3. All three are gone at HEAD.
- **Lint and typing:** `ruff` and `pyright` strict needed three rewrites in `lookup`, `_edited` and `parse_settings` (narrowing of `object` to a dict). The final form passes pyright with zero errors and adds no suppression. A grep of the diff since `97b9e0b` finds 0 new `noqa`, `type: ignore`, `nosec` or `pyright: ignore`.
- **Host load:** four executors ran tests in parallel on this host. The full suite took 88 to 117 s per run. The session guard that watches the real dotfiles never tripped.

## RED / GREEN evidence

**Task 1 RED** (`-k` filter over the three files):
```
ERROR tests/test_agent_settings.py
E   ModuleNotFoundError: No module named 'installer.agent_settings'
ERROR tests/test_atomic.py
E   ImportError: cannot import name 'read_snapshot' from 'installer.atomic'
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
```
Also, with the repointed shellrc patches and no shellrc change yet:
```
E   AttributeError: module 'installer.shellrc' has no attribute 'read_snapshot'. Did you mean: '_snapshot'?
E   AttributeError: module 'installer.shellrc' has no attribute 'snapshot_matches'. Did you mean: '_snapshot_matches'?
FAILED tests/test_shellrc.py::test_refuses_when_the_snapshot_cannot_be_read
FAILED tests/test_shellrc.py::test_guard_refuses_when_the_file_changes_while_it_is_being_guarded
```

**Task 1 GREEN:**
```
collected 22 items / 15 deselected / 7 selected
tests/test_agent_settings.py ......
tests/test_atomic.py .
======================= 7 passed, 15 deselected in 0.04s =======================
```

**Task 2 RED:**
```
E   ImportError: cannot import name 'new_file_text' from 'installer.agent_settings'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```
**Task 2 GREEN:** the file runs 14 of 14 passing (the seven Task 2 tests plus the extra cut test and the Task 1 set); the `-k` selection of the seven Task 2 tests passes (seven dots, no failure).

**Task 3 RED** (`-k` filter, six tests): four FAILED on the placeholder:
```
FAILED tests/test_agent_settings.py::test_codex_toml_round_trip_inserts_before_the_first_table
FAILED tests/test_agent_settings.py::test_a_toml_file_without_a_final_newline_round_trips
FAILED tests/test_agent_settings.py::test_a_toml_splice_into_an_array_is_refused
FAILED tests/test_agent_settings.py::test_an_invalid_toml_file_names_the_line
E   NotImplementedError: toml
```
The other two selected tests did not fail: `test_a_file_changed_between_read_and_write_is_not_written` and `test_a_symlinked_settings_file_is_edited_through_its_target` use the Task 1 compare-before-commit helpers and JSON, so they are **regression guards, not RED**.

**Task 3 GREEN:**
```
collected 36 items / 30 deselected / 6 selected
tests/test_agent_settings.py tests/test_atomic.py ......
======================= 6 passed, 30 deselected in 0.04s =======================
```

## Test counts

- Baseline at `97b9e0b`: 5589 collected (5585 passed, 4 skipped), `make test` exit 0.
- After Task 1: 5596 collected (5592 passed, 4 skipped), exit 0. `make validate` exit 0.
- After Task 2: 5604 collected (5600 passed, 4 skipped), exit 0. `make validate` exit 0.
- After Task 3 (final): 5610 collected (5606 passed, 4 skipped), exit 0. Coverage 96.24%, floor 90%.
- `tests/test_atomic.py`: 15 to 16. `tests/test_shellrc.py`: 225 to 225. `tests/test_agent_settings.py`: new, 20.

## Verification (acceptance greps)

- `def _snapshot_matches` in `installer/shellrc.py`: 0. `def snapshot_matches(` in `installer/atomic.py`: 1.
- `def _guarded(` in `installer/agent_settings.py`: 1.
- `installer.shellrc._snapshot` in `tests/test_shellrc.py`: 0 (baseline 2).
- `def strip_jsonc(` and `def replace_value(`: 1 each.
- tomlkit / json5 / commentjson imports: 0.

## Threat model coverage

- T-23-04 (splice corrupts or drops keys): `test_the_guard_refuses_an_unintended_edit` and `test_a_toml_splice_into_an_array_is_refused`.
- T-23-05 (file swapped between read and write): `test_snapshot_matches_refuses_a_swapped_file` and `test_a_file_changed_between_read_and_write_is_not_written`.
- T-23-06 (writing a file that does not parse): `test_an_invalid_json_file_is_refused_and_untouched`, `test_an_invalid_jsonc_file_names_line_and_column`, `test_an_invalid_toml_file_names_the_line`.

## Known Stubs

None.

## Handed to later plans

- **23-06 must map non-UTF-8 bytes itself.** This engine takes `str`. The decision "non-UTF-8 bytes are line 1, no column" is not implemented here, because no bytes entry point exists; 23-06's read path decodes and must raise `SettingsParseError(fmt, 1, None)` on failure.
- **Ownership and the already-equal check.** `insert_key` refuses a key that is already set, so 23-06 checks absence first and uses `same_value` for "already set" and "still ours".
- **`delete_if_unchanged` deletes the link target**, not the link, because the compare is on the real file. Ledger deletes only ever target files the installer created.

## Next Phase Readiness

The splice engine and the compare-before-commit primitive are in place for 23-06 (settings API and ledger). `requirements-completed` lists CONF-08, CONF-09 and CONF-12 because the plan frontmatter does; the engine is the writer core behind them, and their user-facing behaviour lands with 23-06.

## Self-Check: PASSED

- `installer/agent_settings.py`, `tests/test_agent_settings.py`, `installer/atomic.py`, `installer/shellrc.py`, `tests/test_atomic.py`, `tests/test_shellrc.py` exist on the worktree branch.
- Commits present on `worktree-agent-a32df92e2e7b1d01b`: `ab0aef8`, `b4d8d8d`, `e8f5dee` (each an ancestor of HEAD; `git rev-list --count 97b9e0b..HEAD` = 3).
