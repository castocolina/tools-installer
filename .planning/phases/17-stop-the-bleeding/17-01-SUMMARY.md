---
phase: 17-stop-the-bleeding
plan: "01"
subsystem: testing
tags: [ci, bash-3.2, pyright, textual, pytest]

requires:
  - phase: 16-detection-version-and-ownership
    provides: ownership resolution and the version refresh the owner-cell test exercises
provides:
  - bash 3.2 portable linux tmp prune (while-read, grep -E, set -u safe arrays)
  - Darwin-clean pyright for the xdist worker cap
  - deterministic owner-cell, console-width and systemd-gate tests
affects: [17-02, 17-03, 17-04, 17-05, 17-12, ci-wave-1]

actuals:
  tokens: 600
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "sys.platform narrows the Linux-only os.sched_getaffinity call for pyright"
    - "a test pins the owner label the refresh resolves, never a seeded private record"

key-files:
  created: []
  modified:
    - scripts/prune-tmp-linux.sh
    - scripts/lib/prune-tmp-common.sh
    - tests/conftest.py
    - tests/test_shellrc.py
    - tests/test_catalog_tui.py
    - tests/test_app.py
    - tests/test_setup.py

key-decisions:
  - "version_status join checks stay: 10/10 stress runs passed and CI history does not fail them"
  - "the owner-cell wait uses a scoped pyright ignore because textual's Worker is generic and unparameterized"

patterns-established:
  - "Pattern: per-shell source expectation derived from Path(shell).resolve().name == dash"
  - "Pattern: systemd_available supplied by the test, so a macOS host still builds the daemon policy"

requirements-completed: [CI-01]

coverage:
  - id: D1
    description: "prune-tmp-linux.sh deletes exactly the two old Bun cache files under bash 3.2 with busybox find, and an empty tmpdir exits 0"
    requirement: CI-01
    verification:
      - kind: e2e
        ref: "podman run docker.io/library/bash:3.2 scripts/prune-tmp-linux.sh --apply"
        status: pass
      - kind: unit
        ref: "tests/test_prune_tmp_linux_sh.py + tests/test_prune_user_tmpdir_sh.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "pyright reports 0 errors on Darwin and Linux, and the time-source test states dash does not source while bash, zsh and other sh do"
    requirement: CI-01
    verification:
      - kind: other
        ref: "uv run pyright --pythonplatform Darwin"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py::test_reserved_word_prefixed_source_forms_execute_and_are_refused"
        status: pass
    human_judgment: false
  - id: D3
    description: "owner cell, the two wide-console consolidation tests and the shared daemon cache test pass regardless of worker timing, path length or systemctl presence"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py::test_owner_cell_semantic_value_reaches_the_mounted_table"
        status: pass
      - kind: unit
        ref: "tests/test_app.py::test_an_rc_with_an_unresolvable_source_command_still_gets_our_block_and_a_diagnostic"
        status: pass
      - kind: unit
        ref: "tests/test_app.py::test_configure_path_reports_a_consolidation_refusal"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py::test_interactive_wizard_shares_one_cache_with_the_daemon_policy"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both CI jobs green on the wave-1 tree (ubuntu-latest and macos-latest)"
    requirement: CI-01
    verification: []
    human_judgment: true
    rationale: "ci.yml triggers only on push to main or pull_request, and the executor must not push or open a PR. The orchestrator records both job conclusions."

duration: 140min
completed: 2026-10-14
status: complete
---

# Phase 17: Stop the bleeding Summary

**The linux tmp prune runs under bash 3.2, Darwin pyright is clean, and the three host-dependent tests assert a result that no longer depends on timing, path length or systemctl.**

## Performance

- **Duration:** 140 min
- **Started:** 2026-10-14T18:37:00Z
- **Completed:** 2026-10-14T20:55:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `scripts/prune-tmp-linux.sh` fills its match list with `while IFS= read -r` and `scripts/lib/prune-tmp-common.sh` filters the regex with `grep -E`, so bash 3.2 and busybox find prune the same two files GNU find did.
- `pytest_xdist_auto_num_workers` narrows `os.sched_getaffinity` on `sys.platform == "linux"`, and the time-source test keeps `sh` while expecting dash not to source.
- The owner cell, the two consolidation tests and the shared-cache test no longer depend on worker timing, console width or a host `systemctl`.

## Task Commits

Each task was committed atomically:

1. **Task 1: bash 3.2 prune** - `a51e07e` (fix)
2. **Task 2: Darwin pyright and dash time** - `a26b9e3` (fix)
3. **Task 3: deterministic UI and setup tests** - `6eeabba` (fix)

## Files Created/Modified

- `scripts/prune-tmp-linux.sh` - while-read array fill; empty-safe `"${files[@]}"` loops
- `scripts/lib/prune-tmp-common.sh` - `find | grep -E` regex filter; `${arr[@]+"${arr[@]}"}` expansions; `_prune_common_find_matches0` matches with `-name` only
- `tests/conftest.py` - `sys.platform`-narrowed CPU count
- `tests/test_shellrc.py` - dash does not source `time . file`; every other shell must
- `tests/test_catalog_tui.py` - owner cell pinned to `Homebrew` from a brew-owning refresh; `_offline_service` gains optional `read_inventory_fn`
- `tests/test_app.py` - the two consolidation tests use `Console(width=1000)`
- `tests/test_setup.py` - the shared-cache test supplies `systemd_available`

## Decisions Made

- `tests/test_version_status.py` was not edited. Its stress loop passed 10/10, so the `second.join(timeout=0.2)` checks stay (RUN-LEDGER Q3: fix only if reproduced).
- The owner-cell `await app.workers.wait_for_complete()` carries `# pyright: ignore[reportUnknownMemberType]`. textual types `Worker` without a type parameter, so the method's type is partially unknown under strict pyright; the call itself is the real wait. A `cast` cannot cover the attribute access, and `getattr` trips ruff B009.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale `regextype` comment kept the acceptance grep red**
- **Found during:** Task 1
- **Issue:** `_prune_common_escape_dots`'s header still named `find -regextype posix-extended` after the predicate was removed, so `! grep -q regextype` failed.
- **Fix:** The comment now names the regex filter of `_prune_common_find_matches`.
- **Files modified:** `scripts/lib/prune-tmp-common.sh`
- **Verification:** `grep -c regextype` is 0; shellcheck clean
- **Committed in:** `a51e07e`

**2. [Rule 1 - Bug] The plan's lambdas fail strict pyright**
- **Found during:** Task 3
- **Issue:** `lambda **_kwargs: True` and `lambda **_kwargs: ManagerInventory(...)` are partially unknown (`reportUnknownLambdaType`), and `app.workers.wait_for_complete` is `reportUnknownMemberType` because textual's `Worker` is generic and unparameterized.
- **Fix:** Named, fully typed callables for the systemd gate and the inventory reader. The worker wait keeps a scoped pyright ignore with a one-line reason, matching `tests/test_execute_screen.py:2740`.
- **Files modified:** `tests/test_setup.py`, `tests/test_catalog_tui.py`
- **Verification:** `make validate` exits 0; the four named tests pass
- **Committed in:** `6eeabba`

---

**Total deviations:** 2 auto-fixed (2 correctness)
**Impact on plan:** Both keep the planned behavior and the acceptance greps. No scope creep.

## TDD RED evidence

Task 1, `docker.io/library/bash:3.2` before the fix (exit 127):

```
/s/lib/prune-tmp-common.sh: line 208: find_type[@]: unbound variable
/s/prune-tmp-linux.sh: line 101: mapfile: command not found
exit=127
empty-exit=127
```

GREEN after the fix: `deleted: 2`, `exit=0`, listing exactly `.0123456789abcdef-1234567.so` and `.fedcba9876543210-87654321.so`, `deleted: 0`, `empty-exit=0`. `uv run pytest tests/test_prune_tmp_linux_sh.py tests/test_prune_user_tmpdir_sh.py` → 59 passed, 3 skipped. shellcheck clean.

Task 2, `uv run pyright --pythonplatform Darwin` before the fix (3 errors, all at `tests/conftest.py:27`):

```
error: Type of "sched_getaffinity" is unknown (reportUnknownMemberType)
error: Argument type is unknown (reportUnknownArgumentType)
error: "sched_getaffinity" is not a known attribute of module "os" (reportAttributeAccessIssue)
3 errors, 0 warnings, 0 informations
```

GREEN: `uv run pyright --pythonplatform Darwin` and `uv run pyright` both report `0 errors`. `uv run pytest tests/test_shellrc.py -k reserved_word` → 4 passed, 221 deselected (host `sh` is bash).

Dash oracle: the same test inside `docker.io/library/ubuntu:24.04`, where `readlink -f $(command -v sh)` is `/usr/bin/dash`, using the host's uv cpython mounted read-only and the project venv on `PYTHONPATH`:

```
/usr/bin/dash
4 passed, 221 deselected in 0.04s
```

Task 3, scratch copy (deleted, never committed) with `await app.workers.wait_for_complete()` added before the asserts:

```
E   AssertionError: assert 'installer artifact' == 'Homebrew'
E   - Homebrew
E   + installer artifact
1 failed in 0.30s
```

GREEN: the four named tests pass (`4 passed in 5.46s`).

## Verify results

- Task 1 container, prune pytest and shellcheck: pass (see RED evidence).
- Task 2 Darwin pyright, Linux pyright, reserved-word pytest: pass.
- Task 3 named pytest: 4 passed. `tests/test_version_status.py -n auto`: pass on the single run and on every stress run.
- `make validate && make test` on each task's tree: validate exit 0; `3466 passed, 4 skipped`, coverage 95.88% (floor 90%).
- No `pytest.mark.skip`, `xfail` or `pytest.skip(` added (`git diff 6eeabba^..6eeabba -- tests`).
- `grep -c 'width=1000' tests/test_app.py` is 5, up 2 from 3 at `a26b9e3`.

## Stress and CI history (version_status)

- `test_owner_cell_semantic_value_reaches_the_mounted_table`: 10/10.
- `tests/test_version_status.py -n auto`: 10/10. No edit.
- `gh run list --workflow CI --limit 30`: 21 failed runs. `gh run view <id> --log-failed | grep test_version_status` found the file in exactly two, both `validate & test on macos-latest`:
  - run 38556835234 (2026-10-14T11:28Z) and run 38505722588 (2026-10-14T03:20Z)
  - both fail `test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record` at `tests/test_version_status.py:1300` with `the unsynchronized reader never overlapped a committed pass`
- Neither failure is the `second.join(timeout=0.2)` pair at lines 1790 and 1874, which is the only edit Q3 authorizes. Those two lines were not touched. The overlapping-reader failure is recorded here for the orchestrator; it is outside this plan's files and action.

## Issues Encountered

- The plan's Task 3 lambdas do not type-check under strict pyright. Resolved with named functions and one scoped ignore (see Deviations).
- The ubuntu dash oracle needed the host uv Python and the project venv mounted read-only: the local `ubuntu:24.04` image has dash but no Python or pytest. The container only read the tree.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 1 can be judged once the orchestrator records both CI jobs below. The local suite is green on this tree.
- The macOS proof of BSD `find -mmin/-mindepth/-maxdepth` is still the macos-latest job; only busybox find was proven locally.
- The unsynchronized-reader failure above is a separate flake from the one this plan fixed.

## CI oracle (wave 1)

Attempt 1 (red, routed to gap plan 17-14):
run 38653233506 https://github.com/castocolina/tools-installer/actions/runs/38653233506
oracle sha: 2378dd9a2125c91054d9b139c16285b5b839a1c6
validate & test on ubuntu-latest: success
validate & test on macos-latest: failure (make validate green; 2 test failures: test_refuses_a_dotdot_spelling_of_the_root_directory, test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record)

Attempt 2 (after 17-14; red, routed to gap plan 17-15):
run 38654588972 https://github.com/castocolina/tools-installer/actions/runs/38654588972
oracle sha: 460da3998fe36bd5a7ad153fad8a04f3c934ad09
validate & test on ubuntu-latest: success
validate & test on macos-latest: failure (dot-dot test fixed; the unsynchronized-reader race test still never observes a committed record)

Attempt 3 (after 17-15; red, routed to gap plan 17-16):
run 38656028040 https://github.com/castocolina/tools-installer/actions/runs/38656028040
oracle sha: 1bdc07f94f8a5089eacaf6095caed1c845082daa
validate & test on ubuntu-latest: success
validate & test on macos-latest: failure (race test fixed; new timing failure: test_manual_toggle_of_the_daemon_is_refused_while_the_worker_is_in_flight)

Attempt 4 (after 17-16; green, wave 2 unblocked):
run 38657359355 https://github.com/castocolina/tools-installer/actions/runs/38657359355
oracle sha: 2617d97d3e3283c89351d1e49ace02b5280c15f6
validate & test on ubuntu-latest=success
validate & test on macos-latest=success

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
