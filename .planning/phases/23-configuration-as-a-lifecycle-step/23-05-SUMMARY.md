---
phase: 23-configuration-as-a-lifecycle-step
plan: "05"
subsystem: installer
tags: [postinstall, hooks, unregister, herdr, tealdeer, notingrunner, tdd]
status: complete

requires:
  - phase: 23-01
    provides: HookPair table, harness-keyed codegraph target map, _resolve_binary, register_hooks with receipt.hooks
provides:
  - unregister_argvs(name, binary, recorded): undo argvs built from recorded hosts only, filtered through the closed map
  - hook_method(tool, receipt): the one "which method was this receipt written for" rule (23-08 reuses it)
  - host_labels(hosts): catalog-id display labels, sorted
  - herdr-integration pair (per-host register and unregister), not wired to any registry tool until Phase 24
  - tealdeer-cache pair: tldr --update after install and after u, a failure is a warning
  - run.NotingRunner protocol and StreamingRunner.note (attributed log line)
  - tealdeer registry data: postinstall = "tealdeer-cache", config_paths for ~/.cache/tealdeer and ~/Library/Caches/tealdeer
affects: [23-07 (drift, re-sync, host labels), 23-08 (removal: unregister builders, hook_method), 24 (herdr wiring)]

actuals:
  tokens: 4553     # chars/4 over `git diff 703f5d6 HEAD` (18214 chars); realized diff, not a harness count
  tasks: 2
  commits: 2       # MEASURED: git rev-list --count 703f5d6..HEAD
plan_head_before: 703f5d6233ee735ef6cc0f3d4101ddefa87f3f94
plan_head_after: b1bde3bb5ee35f2bc6137916f2ab2c881e0aa615

tech-stack:
  added: []
  patterns:
    - "Undo argvs are pure builders over the recorded hosts; the recorded list is filtered through the code-owned map before any argv is built"
    - "A runner capability is a separate runtime_checkable Protocol (NotingRunner), so a fake without note still satisfies Runner"

key-files:
  created: []
  modified:
    - installer/postinstall.py
    - installer/run.py
    - installer/model.py
    - installer/registry.toml
    - tests/test_postinstall.py
    - tests/test_run.py
    - tests/test_update.py
    - tests/test_registry.py

key-decisions:
  - "unregister_argvs drops every id outside the target map (unknown ids, all, auto, paths, pi) before building an argv; no recorded host yields ()"
  - "hook_method keeps 23-01's behaviour: keyed match, else the only method of the receipt's kind, else None"
  - "herdr's per-host failures are joined as '{host}: {line}' with '; ' and the registered hosts are returned in map order"
  - "The tealdeer note is written only through a NotingRunner, so the headless runner prints nothing extra"
  - "The failure line is the first non-empty line of CommandError.detail, else of its message (the app.py:640 rule); see Deviations"

patterns-established:
  - "Test-first, one commit per task: RED pasted here, never committed alone; tests and code in one feat(23-05) commit"

requirements-completed: [CONF-01, CONF-06]

# Plan-level status against the requirements
# CONF-01: the unregister builders exist for codegraph and herdr. The removal call sites are 23-08.
# CONF-06: tealdeer fetches its cache after install and after u; the failure is a warning; the cache dirs are declared.
---

# Phase 23 Plan 05: Unregister builders, herdr pair, tealdeer cache fetch — Summary

**Hook undo commands come only from recorded hosts (`uninstall --target` / `integration uninstall`), hosts display by catalog id, herdr's pair exists unwired, and tealdeer fills its page cache after install and `u` with a warning-only failure.**

## Performance

- **Tasks:** 2 (both `tdd="true"`, one green commit each)
- **Commits:** 2 (`3f818f1`, `b1bde3b`), measured against base `703f5d6`
- **Test counts (collected, `--no-cov -n 0`):** 5621 at start → 5641 after Task 1 → 5648 after Task 2 (net +27).
  - Plan delta: 12 named tests. Task 1 adds 5 functions, one of them parametrized to 16 cases (`test_unregister_never_passes_all`), so +20. Task 2 adds 7.
  - `make test` after Task 1: 5637 passed, 4 skipped, coverage 96.31%. After Task 2: 5644 passed, 4 skipped, coverage 96.31%.
  - No existing test was deleted. One existing test was renamed and retargeted (see Test changes).

## Accomplishments

- `installer/postinstall.py`: `_codegraph_unregister` (one `uninstall --target <csv> --location global --yes --keep-cli` argv in map order), `unregister_argvs`, `hook_method`, `host_labels`, `_herdr_register` / `_herdr_unregister` / `_HERDR_TARGETS`, `_tealdeer_cache`, `_failure_line`, and the pairs `herdr-integration` and `tealdeer-cache` in `POSTINSTALL_HOOKS`.
- `installer/run.py`: `NotingRunner` (runtime_checkable: `__call__` and `note`), `StreamingRunner.note` emitting `(current tool, text)`.
- `installer/model.py`: `POSTINSTALL_HOOK_NAMES` gains `herdr-integration` and `tealdeer-cache`; the parity test with `POSTINSTALL_HOOKS` stays green.
- `installer/registry.toml`: tealdeer gets `postinstall = "tealdeer-cache"` and two `config_paths` entries, with a dated comment citing docs.tealdeer.org and noting the macOS path is assumed (research A6).

## Task Commits

1. **Task 1: build hook unregister commands from recorded hosts** - `3f818f1` (feat). Tests and code in one commit.
2. **Task 2: herdr hook pair and the tealdeer cache fetch** - `b1bde3b` (feat). Tests and code in one commit.

## Test-first evidence

### Task 1 RED

Command: `uv run pytest tests/test_postinstall.py -k "unregister_targets_only_recorded or tampered_ids or never_passes_all or hook_method_matches or host_labels_use_catalog_ids" -q --no-cov -n 0`
Log: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/red-23-05-task1.log`. Exit 1, 21 failed (every new case). Representative:

```
FAILED tests/test_postinstall.py::test_codegraph_unregister_targets_only_recorded_hosts
FAILED tests/test_postinstall.py::test_unregister_drops_unknown_and_tampered_ids
FAILED tests/test_postinstall.py::test_unregister_never_passes_all[none] ... [claude,codex,opencode,cursor]  (16 cases)
FAILED tests/test_postinstall.py::test_hook_method_matches_the_receipt_key
FAILED tests/test_postinstall.py::test_host_labels_use_catalog_ids - AttributeError: ... no attribute 'host_labels'
```

Task 1 GREEN: the same five functions, 20 cases: 20 passed (exit 0). `make validate` exit 0. `make test` exit 0: 5637 passed, 4 skipped.

### Task 2 RED

Command: `uv run pytest tests/test_postinstall.py tests/test_run.py tests/test_update.py tests/test_registry.py -k "herdr_registers or herdr_is_not_wired or tealdeer_fetches or failed_tldr_update or tldr_update_once or cache_in_config_paths or note_emits" -q --no-cov -n 0 --continue-on-collection-errors`
Log: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/red-23-05-task2.log`. Exit 1.

```
FAILED tests/test_postinstall.py::test_herdr_registers_and_unregisters_per_host
FAILED tests/test_postinstall.py::test_tealdeer_fetches_its_cache_after_install
FAILED tests/test_postinstall.py::test_a_failed_tldr_update_is_a_warning - At index 1 diff: None != 'tldr --update failed: boom; run it yourself later'
FAILED tests/test_update.py::test_tealdeer_update_runs_tldr_update_once
FAILED tests/test_registry.py::test_herdr_is_not_wired_in_the_registry
FAILED tests/test_registry.py::test_tealdeer_declares_its_cache_in_config_paths
ERROR tests/test_run.py  (collection: cannot import name 'NotingRunner' from 'installer.run')
```

Without `--continue-on-collection-errors` the same command stops at collection (`Interrupted: 1 error during collection`), which is also a missing-API RED.

Task 2 GREEN: the focused command above, 7 passed (exit 0). Plan verification set `tests/test_postinstall.py tests/test_run.py tests/test_update.py tests/test_registry.py tests/test_model.py -n auto` exit 0. `make validate` exit 0 (after one pyright fix in a test lambda, see Issues). `make test` exit 0: 5644 passed, 4 skipped.

No `# type: ignore`, `pyright: ignore`, `noqa` or `nosec` was added (checked against the diff: 0 added lines).

## Test changes (every change, with its reason)

- `tests/test_registry.py`: `test_only_codegraph_and_rtk_declare_a_postinstall_hook` renamed to `test_only_codegraph_and_tealdeer_declare_a_postinstall_hook`, and the exempt list is `("codegraph", "tealdeer")`. Reason: the plan requires `tealdeer` to declare `postinstall = "tealdeer-cache"`, and rtk's hook was already removed in 23-01. The assertion is otherwise unchanged.
- No other existing test was changed. New tests were appended, plus one import line each in `tests/test_run.py` (`NotingRunner`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, plan contract] The failure line comes from `exc.detail`, not `str(exc)`**
- **Found during:** Task 2, while writing the planned test "a CommandError whose text is `boom\nmore`".
- **Issue:** the plan says the first line is "the first non-empty line of `str(exc)`". Every real `CommandError` has a message that starts `command failed (N): <argv>`, so `str(exc)` can never produce the planned `boom` or `cursor: boom`. Real vendor output sits in `exc.detail` (StreamingRunner fills it), so a `str(exc)` rule would show the argv, not the cause.
- **Fix:** `_failure_line(exc)` returns the first non-empty line of `exc.detail`, falling back to the first line of `str(exc)`. This is the house rule at `installer/app.py:640`. The planned warning strings come out exactly as the plan writes them, and the tests build the error with `CommandError(cmd, 1, detail="boom\nmore")`.
- **Files modified:** `installer/postinstall.py` (`_failure_line`), `tests/test_postinstall.py`, `tests/test_update.py`.
- **Commit:** `b1bde3b`.

**2. [Rule 3 - Blocking] Pyright strict on a test lambda**
- **Found during:** Task 2 `make validate`.
- **Issue:** `monkeypatch.setattr(update.download, "update_download", lambda _method, _ctx: ...)` gave reportUnknownLambdaType (3 errors).
- **Fix:** replaced it with a typed `def fake_update(_method: Method, _ctx: object) -> DownloadUpdateExecResult`, the form the existing tests use.
- **Commit:** `b1bde3b`.

### Judgement calls (not deviations from the plan's behaviour)

- `host_labels` uses `HOST_CATALOG_IDS.get(host, host)`. An id outside the map is shown as given, not a `KeyError`. A hand-edited receipt must not crash the display.
- The tealdeer update test (`test_tealdeer_update_runs_tldr_update_once`) fakes `update.download.update_download` instead of serving a release fixture over fake urlopen. The postinstall dispatch, not the download, is under test. The runner sees only the `tldr --update` argv, which is asserted exactly.

## Issues Encountered

- **Harness refusals:** the Bash harness refused compound commands that name git (for example `cd … && codegraph init … ; git …`, and `$(git merge-base …)` inside a command substitution). I split them into plain commands. Not a code problem.
- **Codegraph paths:** `codegraph explore` prints paths under the main checkout. I used it only to understand the code and read or edited files under the worktree root. I ran `codegraph init -i` in the worktree, which created `.codegraph/` there (git-ignored).
- **Protected-branch check:** the `gsd_run query git.base-branch --is-protected` call was not available in this shell, so the pre-commit HEAD guard used the five-name fallback (`main|master|develop|trunk|release/*`). The branch `worktree-agent-a6f0d889884e6fbff` is in the agent-* namespace, so the allow-list check passed.
- **Session guard:** `make test` ran twice without the test-session guard tripping, so no re-run was needed.
- **Ledger:** `gsd-spawn-toplevel` and `gsd-plan-head-before-23-05` were written with Bash `printf` and `git rev-parse` under the worktree's git directory, the same method as 23-04.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-23-01 is covered by `test_unregister_drops_unknown_and_tampered_ids` and `test_unregister_never_passes_all`. T-23-46 is covered by `test_a_failed_tldr_update_is_a_warning` and `test_tealdeer_update_runs_tldr_update_once`.

## Unverified and open items for the orchestrator

- **Orphan helpers (architecture rule 5):** `unregister_argvs`, `hook_method` and `host_labels` have no production caller in this plan. They are called from 23-07 (drift, host labels) and 23-08 (removal, unregister argvs, `hook_method`), as the plan sequences. `herdr-integration` is wired to no tool until Phase 24, by design (planner decision 6). `make validate` does not flag them: vulture runs at `min_confidence = 80`. Flagged here so the orchestrator can confirm the sequencing is intended.
- **Not run against a real host:** codegraph uninstall, herdr integration and `tldr --update` were exercised only through fake runners. Per the host rules, no real `codegraph`, `herdr` or `tldr` was invoked.
- **Pre-existing comment in `tests/test_setup.py`:** unchanged; not in this plan's scope.

## Self-Check

- [x] `installer/postinstall.py` has `def unregister_argvs(`, `def hook_method(`, `def host_labels(`; the `tealdeer-cache` and `herdr-integration` pairs are in `POSTINSTALL_HOOKS`.
- [x] `installer/run.py` has `class NotingRunner` and `StreamingRunner.note`.
- [x] `installer/registry.toml`: tealdeer has `postinstall = "tealdeer-cache"` and both `config_paths` entries.
- [x] Commits `3f818f1` and `b1bde3b` exist on `worktree-agent-a6f0d889884e6fbff` after base `703f5d6`.
- [x] `make validate` exit 0 and `make test` exit 0 on each commit's tree.
- [x] `STATE.md` and `ROADMAP.md` are not edited.

## Self-Check: PASSED
