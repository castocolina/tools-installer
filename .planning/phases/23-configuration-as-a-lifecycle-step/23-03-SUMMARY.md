---
phase: 23-configuration-as-a-lifecycle-step
plan: "03"
subsystem: policies
tags: [oh-my-zsh, zshrc, theme, starship, ownership-record, tdd, atomic-write]

# Dependency graph
requires:
  - phase: 22-method-lifecycle-contract
    provides: the plugin ownership record helpers in installer/omz.py that this plan parameterizes
provides:
  - the Oh-My-Zsh plugins policy writes the real $ZSH root (omz_root) instead of the default
  - one theme writer (set_theme / apply_theme) that adds a default only where none exists
  - an installer-owned theme claim (THEME_BEGIN/THEME_END block in ~/.myshellrc) that starship can replace
  - default_theme() (empty once the starship block is present) and tweaks.bundle_marker_present()
affects: [23-09 (starship bundle id and install handoffs), 23-11 (Policies rows), 23-14 (alias strip and composition)]

# Actuals (#2632): chars/4 over the realized diff (git diff 97b9e0b..HEAD, 23282 chars)
actuals:
  tokens: 5820
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One closed-block record reader, parameterized by begin/end/prefix (plugin and theme records share it)"
    - "Claim order for file edits: reserve the record, write the file, roll the record back on OSError"

key-files:
  created: []
  modified:
    - installer/omz.py
    - installer/policy.py
    - installer/tweaks.py
    - tests/test_omz.py
    - tests/test_policy_omz.py
    - tests/test_tweaks.py

key-decisions:
  - "The plugins policy passes omz_root(Path.home(), os.environ) to write_plugins, so a custom $ZSH is written as the export (D-12)"
  - "The theme line is inserted before the source line only when no theme assignment exists (export, typeset and indented forms count); a commented line does not count (D-13, R1-17)"
  - "An existing theme value is rewritten only when it equals the installer's own recorded claim; a user theme is never touched (T-23-07)"
  - "The claim is reserved before the .zshrc write and rolled back on OSError, the write_plugins order (03-2, R1-02, T-23-51)"
  - "default_theme is empty once the starship block marker is present, so only one prompt is active (CONF-11)"
  - "write_plugins applies the default theme after its plugin edit; remove_plugins never touches the theme line or its claim"

patterns-established:
  - "Record helpers take begin/end (and the body prefix for readers); the plugin callers pass nothing and keep their bytes"

requirements-completed: [CONF-07]
# CONF-11 is partial: this plan delivers the writer half. The install-time handoff lines and the starship enable path land in 23-09.

# Metrics
duration: "approx. 11 min (prompt file mtime 01:05 to last commit 01:16, filesystem and git timestamps)"
completed: 2026-11-07
status: complete
---

# Phase 23 Plan 03: Oh-My-Zsh custom root and one theme writer Summary

**Oh-My-Zsh plugin writes honor a custom $ZSH, and one theme writer adds a default prompt only where none exists while starship can replace only the default the installer itself wrote**

## Performance

- **Duration:** approx. 11 min (timestamps from the prompt file and the two commits)
- **Started:** 2026-11-07T01:05 (approximate, prompt file mtime)
- **Completed:** 2026-11-07T01:15:49-03:00 (commit 97f142b)
- **Tasks:** 2 of 2
- **Files modified:** 6 (3 code, 3 tests)

## Accomplishments

- A `.zshrc` written for a custom `$ZSH` install (no `~/.oh-my-zsh`) now gets `export ZSH=<real root>`, never the conventional default (CONF-07, D-12, T-23-08).
- `omz.set_theme` is the pure theme writer. It inserts `ZSH_THEME="robbyrussell"` before the source line only when no theme assignment exists, keeps every existing theme line byte-identical, and never edits a file without its source line (D-13, CONF-11).
- `omz.apply_theme` reserves the installer's claim, writes `.zshrc`, and restores the previous claim when the write is refused, so a failed write cannot strand the claim (03-2, R1-02, T-23-51).
- The plugin and theme claims share one closed-block reader. `_record`, `_record_owned` and `_clear_owned` take begin/end (and the body prefix for the reader); the plugin record bytes are unchanged (03-1, R1-16).
- `write_plugins` writes the default theme after enabling its plugins. `default_theme` returns `""` once the starship block marker is present (CONF-11).
- `tweaks.bundle_marker_present` is the shared begin-marker reader; `tweak_present` delegates to it.

## Task Commits

1. **Task 1: a custom $ZSH reaches the .zshrc the plugins policy writes** - `54edfe6` (fix, RED then GREEN, tests and code in one commit)
2. **Task 2: one theme writer adds a default only where none exists and replaces only its own** - `97f142b` (feat, RED then GREEN, tests and code in one commit)

Per ledger row 31 and R1-01, each task is one green commit; the RED output is recorded here and was never committed alone.

## TDD Gate Compliance

- Each task began with its failing tests (RED, pasted below). The tests were committed only together with the implementation that turns them green.
- No separate `test(23-03)` commit exists by design (one commit per task). The advisory GSD TDD checkpoint lists this plan for that reason.
- One test that already passed was checked and kept as a regression guard, not as RED: `test_write_plugins_keeps_the_default_root_without_one` (the default `export ZSH="$HOME/.oh-my-zsh"` output is unchanged).

## Test Evidence

### Task 1 RED (before the change; `uv run pytest tests/test_omz.py tests/test_policy_omz.py -k "custom_zsh_root or passes_the_root_on_repair or keeps_the_default_root" -q --no-cov -n 0`)

```
F.F                                                                      [100%]
E       TypeError: write_plugins() got an unexpected keyword argument 'root'
E       assert 'export ZSH=/tmp/pytest-of-bazzite/.../custom/omz' in 'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git docker)\nsource $ZSH/oh-my-zsh.sh\n'
FAILED tests/test_omz.py::test_write_plugins_passes_the_root_on_repair - Type...
FAILED tests/test_policy_omz.py::test_a_custom_zsh_root_is_written_into_the_template
exit=1
```

### Task 1 GREEN

- Targeted filter: exit 0.
- `uv run pytest tests/test_omz.py tests/test_policy_omz.py -n auto -q --no-cov`: exit 0.
- `make validate`: exit 0 (after `ruff format` on `installer/policy.py`).
- `make test`: `5588 passed, 4 skipped in 90.03s`, coverage 96.30%, exit 0.

### Task 2 RED (before the change)

```
ImportError: cannot import name 'bundle_marker_present' from 'installer.tweaks'   (tests/test_tweaks.py, collection)
FAILED tests/test_omz.py::test_a_zshrc_without_a_theme_gets_robbyrussell_before_the_source_line
FAILED tests/test_omz.py::test_an_existing_theme_is_never_overwritten - AttributeError: module 'installer.omz' has no attribute 'set_theme'
FAILED tests/test_omz.py::test_no_source_line_writes_nothing - AttributeError: ... 'apply_theme'
FAILED tests/test_omz.py::test_starship_replaces_only_the_installer_default - AttributeError: ... 'apply_theme'
FAILED tests/test_omz.py::test_the_default_is_empty_when_the_starship_block_is_present - AttributeError: ... 'default_theme'
FAILED tests/test_omz.py::test_write_plugins_adds_the_default_theme - assert ...
FAILED tests/test_omz.py::test_an_exported_or_indented_theme_counts_as_a_theme - AttributeError: ... 'set_theme'
FAILED tests/test_omz.py::test_a_failed_zshrc_write_leaves_the_record_unchanged - AttributeError: ... 'apply_theme'
FAILED tests/test_omz.py::test_a_failed_zshrc_write_keeps_the_previous_theme_claim - AttributeError: ... 'apply_theme'
exit=1 (omz); exit=2 (collection error in test_tweaks.py)
```

### Task 2 GREEN

- Targeted filter (`-k "gets_robbyrussell or never_overwritten or no_source_line_writes_nothing or replaces_only_the_installer_default or starship_block_is_present or adds_the_default_theme or bundle_marker_present or exported_or_indented_theme or failed_zshrc_write"`): exit 0.
- Affected files after the one expectation change (see Deviations): `tests/test_omz.py tests/test_policy_omz.py tests/test_tweaks.py -n auto`: exit 0.
- `make validate`: exit 0 (pyright 0 errors; after `ruff format` on `tests/test_omz.py`).
- `make test`: `5598 passed, 4 skipped in 125.77s`, coverage 96.30%, exit 0.

## Test Counts (floors)

| Scope | Before | After Task 1 | After Task 2 |
|-------|--------|--------------|--------------|
| Full suite (collected) | 5589 | 5592 (+3) | 5602 (+10) |
| `tests/test_omz.py` | 55 | 57 | 66 |
| `tests/test_policy_omz.py` | 10 | 11 | 11 |
| `tests/test_tweaks.py` | 39 | 39 | 40 |

Full-suite totals match `passed + skipped` from `make test` (5588 + 4 = 5592; 5598 + 4 = 5602). The plan delta is met: +3 in Task 1 and +10 in Task 2.

## Changed or Deleted Existing Tests

- **Changed:** `tests/test_omz.py::test_write_plugins_repairs_source_before_plugins_and_is_byte_stable`. Its expected bytes now include `ZSH_THEME="robbyrussell"` before the source line. This is required by CONF-11 (the plugins writer also writes the default theme). Only the expected literal changed; the byte-stability assertions after it are unchanged.
- **Deleted:** none.
- Every other existing omz, policy and tweaks test passes unchanged, including the plugin record tests.

## Deviations from Plan

### Plan-text adjustments (no scope change)

**1. `_record_owned` takes the block body, not the name list.**
- **Plan said:** `_record_owned` gets `begin`, `end` and body-prefix parameters.
- **Done:** `_record_owned(state_path, body, begin, end)` takes the body lines. The theme body (`# ZSH_THEME="<name>"`) is not a name list, and the prefix belongs to the body. `_owned_block` became `_owned_body`, which returns the four plugin body lines. The rendered plugin block is byte-identical to before.
- **Still per plan:** `_record` takes `begin`, `end` and `prefix`, and `_clear_owned` takes `begin` and `end`. There is one reader: `grep -c "^def _record(" installer/omz.py` is 1.

**2. One test added beyond the plan's list.**
- `test_a_failed_zshrc_write_keeps_the_previous_theme_claim` covers the rollback branch that restores a previous claim. The plan's failure test covers the branch that clears a claim.

**3. `ThemeResult.theme` is `None` for an unreadable existing value.**
- The plan documented `None` only for `no-source`. An existing theme line whose value cannot be read (an unclosed quote, a space inside the value) is reported as `yours` with `theme=None`, and it is never replaced.

**4. Existing test expectation changed** (see Changed or Deleted Existing Tests above).

## Acceptance Checks

- `sed -n "/^def write_plugins/,/^def /p" installer/omz.py | grep -c "ensure_zshrc_template(zshrc_path, root)"` = 2
- `grep -c "def set_theme(" installer/omz.py` = 1; `grep -c "def apply_theme(" installer/omz.py` = 1; `grep -c "^def _record(" installer/omz.py` = 1
- Suppression gate: `git grep -nE "type: ignore|pyright: ignore|noqa|nosec"` over `installer/*.py setup.py tests/*.py` counts 456 at the merge base (97b9e0b) and 456 at HEAD. No suppression was added.

## Issues Encountered

- **CodeGraph index was the main checkout's.** `codegraph explore` warned that its results came from another worktree. The worktree has no `.codegraph/`, and I did not run `codegraph init` there. I read the worktree files directly. The base SHA (97b9e0b) is the same as the main checkout's HEAD at dispatch, so the blast-radius data matches.
- **`ruff format` failed `make validate` twice.** It flagged `installer/policy.py` after Task 1 and `tests/test_omz.py` after Task 2. I applied `ruff format` to those files and re-ran the gate. No check was silenced.
- **Compound git command refused.** The harness rejected the combined worktree-branch-check command, so each check ran as a separate command. The checks themselves all passed.
- **Plan-head ledger written late.** Protocol 0c says to record the ledger before the first commit, and I did not. I wrote `$(git rev-parse --git-dir)/gsd-plan-head-before-23-03` after the Task 2 commit, with the base SHA `97b9e0b418d4947f60e375e5613978007dfcc10b` (the worktree HEAD at start, verified before the first commit). The commit count is measured from that base.
- **Host load.** The Task 2 `make test` ran slower than the first run, because other executors were running suites on the same host. It still completed with exit 0.
- **`make install`** created the worktree's `.venv` (gitignored). It is not committed.

## Decisions Made

- The theme is written only where none exists, and the claim is recorded only for the installer's own write; this follows D-13 and the cycle-1 resolutions R1-02, R1-16 and R1-17.
- `default_theme` reads the `starship` bundle's begin marker. The starship bundle itself lands in 23-09; until then the default is always `robbyrussell`.

## Threat Flags

None. The theme write stays inside the existing `.zshrc` trust boundary, and the threats in the plan's register (T-23-07, T-23-51, T-23-08) each have a test.

## Known Stubs

None.

## Next Phase Readiness

- 23-09 wires the starship bundle (id `starship`) and the install-time handoff lines. `default_theme` already reads that bundle's begin marker.
- 23-11 can read `owned_theme` to show the installer's claim in the Policies rows.

## Self-Check: PASSED

Verified after writing this file: all six modified source and test files and this SUMMARY exist, and both task commits (54edfe6, 97f142b) are ancestors of HEAD.

---
*Phase: 23-configuration-as-a-lifecycle-step*
*Completed: 2026-11-07*
