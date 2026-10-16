---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "04"
status: complete
subsystem: core
tags: [ownership, native-probe, batching, memoization, shims, tdd]

requires:
  - phase: 15.4
    provides: path_owner_package / package_owns_path per-path native queries this index answers
provides:
  - "NativeIndex: a ProbeRunner answering the per-path rpm/dpkg/pacman owner argvs by lookup and memoizing every other argv (text or exception) per index"
  - "native_index(os_family, paths, probe): one batched owner query per OS family per pass (rpm -qf --qf '[%{FILENAMES}\\t%{=NAME}\\n]', dpkg-query -S, env LC_ALL=C pacman -Qo); none on macOS or with no paths"
  - "guards.look_through_shim: the real binary behind this installer's own shim in the managed bin dir"
  - "guards.is_our_shim refuses files over 8 KiB before reading"
affects: [19-12 refresh pass wiring]

actuals:
  tokens: 5100
  tasks: 3
  commits: 3
plan_head_before: 4494bbe970a025afe84b7d6ebd3d37ea7df0a08d
plan_head_after: 69a4a7810c0b8d54c8216ec82a652b4d85d1f406

tech-stack:
  added: []
  patterns:
    - "batched native owner query parsed by path with a usrmerge-safe key (directory realpath, basename kept)"
    - "a ProbeRunner wrapper that answers known argv shapes by lookup and memoizes the rest per pass"

key-files:
  created: []
  modified:
    - installer/install_ownership.py
    - installer/guards.py
    - tests/test_install_ownership.py
    - tests/test_guards.py

key-decisions:
  - "Declared-package queries (rpm -q, dpkg-query -W, pacman -Qq) are NOT batched into one argv: each is one argv per distinct package, memoized per index, which meets STATE-04's 'memoized probe' with no new parser"
  - "NativeIndex answers the three per-path shapes regardless of family; an index built for another family (or macOS) holds no owners, so those answers fail closed"
  - "Only absolute paths are queried, so no queried path can be read as an option by rpm/dpkg-query/pacman"
  - "A reported path whose directory realpath raises (NUL from untrusted stdout -> ValueError) keeps its raw key and so matches nothing"

requirements-completed: [STATE-04]

duration: ~35 min
completed: 2026-10-16
---

# Phase 19 Plan 04: Batched native owner index and shim look-through Summary

One batched rpm/dpkg/pacman owner query per pass, parsed by path with a usrmerge-safe key and served to the unchanged per-path probes by lookup (with every other probe argv memoized), plus `look_through_shim` and an 8 KiB size guard on `is_our_shim`.

## What was built

| Task | Commit | What |
|------|--------|------|
| 1 (tracer) | db3a201 | `NativeIndex` + `native_index` for fedora: one `rpm -qf --qf '[%{FILENAMES}\t%{=NAME}\n]' P...`, `CalledProcessError.stdout` parsed, names filtered by `_PACKAGE_NAME_RE`, basename prefilter then memoized dir realpath; per-path rpm shape answered by lookup, uncollected path raises `CalledProcessError` (fail closed) |
| 2 | d254092 | `_BATCHES` table adds `dpkg-query -S` (multi-owner, `:arch` strip, `diversion by` skipped) and `env LC_ALL=C pacman -Qo` (regex `^(/\S.*) is owned by (\S+) \S+$`); `_PATH_ANSWERS` answers `dpkg-query -S P` and `pacman -Qoq P`; every delegated argv memoized (text or exception) |
| 3 | 69a4a78 | `guards.look_through_shim(found, name, *, shim_dir, path_value, lookup)` delegating to `real_binary`; `is_our_shim` returns False above `_SHIM_MAX_BYTES = 8192` before any read |

The existing per-path functions (`_rpm_owner`, `_rpm_owns_path`, `_dpkg_owner`, `_dpkg_owns_path`, `_pacman_owner`, `_pacman_owns_path`) are byte-identical; all pre-existing tests pass unchanged.

## TDD RED evidence

Task 1 (`-k native_index`, before implementation):
```
E       AttributeError: module 'installer.install_ownership' has no attribute 'native_index'
FAILED tests/test_install_ownership.py::test_native_index_makes_one_rpm_query_for_many_paths
FAILED tests/test_install_ownership.py::test_native_index_answers_the_existing_per_path_queries
FAILED tests/test_install_ownership.py::test_native_index_parses_by_path_not_position
FAILED tests/test_install_ownership.py::test_native_index_fails_closed_for_an_uncollected_path
FAILED tests/test_install_ownership.py::test_native_index_drops_invalid_package_names
FAILED tests/test_install_ownership.py::test_native_index_survives_a_probe_os_error
FAILED tests/test_install_ownership.py::test_native_index_joins_usrmerge_aliases
```

Task 2 (against the Task 1 code):
```
E       AssertionError: assert [] == [['dpkg-query...'/usr/bin/z']]
E           AssertionError: unexpected second query: ['dpkg-query', '-S', '/p']
E       AssertionError: assert [] == [['env', 'LC_...in/ls', '/x']]
E       AssertionError: assert 2 == 1   (rpm-ostree status called twice)
E         Left contains 3 more items, first extra item: ['rpm', '-q', '--qf', '%{NAME}\\n', 'git']
FAILED tests/test_install_ownership.py::test_native_index_debian_one_query
FAILED tests/test_install_ownership.py::test_native_index_debian_multi_owner_is_ambiguous
FAILED tests/test_install_ownership.py::test_native_index_arch_one_query_under_c_locale
FAILED tests/test_install_ownership.py::test_native_index_reads_rpm_ostree_status_once
FAILED tests/test_install_ownership.py::test_native_index_memoizes_every_delegated_argv
```
(`passes_other_argv_through` and `macos_makes_no_query` already held under Task 1 code; they stay as regression guards.)

Task 3:
```
E   ImportError: cannot import name 'look_through_shim' from 'installer.guards'
```

## Verify results

- Task 1: `pytest tests/test_install_ownership.py -k native_index` 7 passed; `grep -c "def native_index"` = 1; `%{=NAME}` present.
- Task 2: `pytest tests/test_install_ownership.py` all passed; `-k native_index` = 15 passed (14 planned + 1 added); `grep -c '"LC_ALL=C"'` = 1.
- Task 3: `-k "look_through or large_file or size_cap or is_our_shim or real_binary"` = 15 passed; `grep -c "def look_through_shim"` = 1.
- Truncation guard, tests/test_guards.py: HEAD 1080 lines -> 1143 (`wc -l`), test functions 90 -> 96, ends with newline. `git diff --stat` before the Task 3 commit: `installer/guards.py | 23 +++, tests/test_guards.py | 63 +++, 2 files changed, 86 insertions(+)`.
- Suppression guard: 598 -> 598 (no new `type: ignore`/`pyright: ignore`/`noqa`/`nosec`).
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock`: unchanged.
- Plan verification: `pytest tests/test_install_ownership.py tests/test_guards.py -n auto --no-cov` 189 passed, 0 failed.
- `make validate` green and `make test` green before each commit; final: 4088 passed, 4 skipped, coverage 95.5%.

## Deviations from Plan

1. **[Rule 2 - Missing critical] Added `test_native_index_survives_an_unresolvable_output_path`** (Task 2, d254092). Untrusted stdout with a NUL in a reported directory makes `os.path.realpath` raise `ValueError` (not `OSError`), so the key helper catches both and keeps the raw path. The test covers that branch.
2. **Shape of `NativeIndex`**: holds the wrapped probe, the owners dict, a dir-realpath memo and the argv memo; no separate `family` or queried-set field. Neither changes behavior: an uncollected path is simply absent from the owners dict and fails closed.
3. **Guard scripts run in plain form**: the worktree sandbox refused `bash -c '... git show ...'`, so the shrink and suppression guards were run as their individual commands (same checks, results above).

## Issues for the orchestrator

- The `4 skipped` in `make test` are macOS-only host tests (`tests/test_daemon.py:288` launchctl, three `tests/test_prune_user_tmpdir_sh.py:218` macOS system paths); none are in this plan's files.
- Nothing in production calls `native_index` or `look_through_shim` yet; plan 19-12 wires them into the refresh pass. Vulture passes as is.

## Self-Check: PASSED

- FOUND: installer/install_ownership.py (`def native_index`, `class NativeIndex`)
- FOUND: installer/guards.py (`def look_through_shim`)
- FOUND commits: db3a201, d254092, 69a4a78 (ancestors of HEAD)
