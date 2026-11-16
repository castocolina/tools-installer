---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "10"
subsystem: uninstall
tags: [receipts, uninstall, removal-proof, tui, security]
status: complete
requires:
  - phase: 19-01
    provides: "receipts.read/receipt_path/matches/drifted/delete + conftest receipts sandbox"
  - phase: 19-02
    provides: "download.artifact_paths (path, kind) formula"
provides:
  - "receipt-aware plan_removal(tools, default_bin_dir, *, verify=False) with RemovalPlan.by_tool"
  - "remove_proven(tools, paths, bin_dir): the one remover for CLI and TUI, re-hash at deletion time, receipt retired after its paths"
  - "UninstallDecision.tools (required, first field); _UninstallEntry.tool"
affects: [19-14, phase-20 uninstall/reconfigure]
actuals:
  tokens: 10471
  tasks: 3
  commits: 3
plan_head_before: 22c5dcb00ea0a33f624b81a7f05b5c8bf3db70aa
plan_head_after: 53cdc0bcefac013df8c74c4a66892d6d327ec409
tech-stack:
  added: []
  patterns:
    - "Receipt proof = receipt artifacts whose (path, type) pair artifact_paths names for the tool's methods of the receipt's kind; whole-receipt drift checked first"
key-files:
  created: []
  modified:
    - installer/uninstall.py
    - installer/app.py
    - installer/wizard_app.py
    - tests/test_uninstall.py
    - tests/test_app.py
    - tests/test_setup.py
key-decisions:
  - "A receipt file that exists (or is a symlink) decides the tool alone: valid+undrifted -> receipt ∩ artifact_paths; corrupt or any drift -> nothing, no layout fallback (L-19-14); no receipt file -> today's archive-layout proof"
  - "remove_proven returns (removed, refusals); a receipt is deleted only when every by_tool path was kept and no longer exists; an OSError from remove_paths propagates before any receipt is touched"
  - "UninstallScreen builds tools from _UninstallEntry.tool, skipping env rows, de-duplicated by id in selection order"
requirements-completed: [STATE-03]
duration: ~45min
completed: 2026-10-16
---

# Phase 19 Plan 10: Receipt-proven removal through one remover Summary

`plan_removal` now proves a tool by receipt ∩ `artifact_paths` (pair-matched on path and type, whole-receipt drift first, corrupt receipt = unproven), and both the CLI `--yes` path and the TUI delete through one `remove_proven` that re-hashes at deletion time and retires the receipt once its paths are gone.

## Tasks

| Task | Commit | What |
|------|--------|------|
| 1 | 18fb2bd | `plan_removal(..., verify=False)` receipt-aware via `_receipt_proof`; `RemovalPlan.by_tool`; 11 new tests |
| 2 | 03fac47 | `remove_proven(tools, paths, bin_dir)`; `run_uninstall` deletes through it; 5 uninstall tests + `test_run_uninstall_uses_receipt_proof` |
| 3 | 53cdc0b | `UninstallDecision.tools`; `perform_uninstall` through `remove_proven`; `_UninstallEntry.tool` + `tool=row.tool`; `still_removable` deleted; 17 constructions converted; `test_perform_uninstall_reproves_per_tool`, `test_uninstall_screen_passes_the_selected_tools` x3 |

## TDD RED evidence

Task 1 (`-k "receipt or tampered or drifted or corrupt or layout_proof or another_kind or link_target"`): 11 failed, e.g.
```
E       AttributeError: 'RemovalPlan' object has no attribute 'by_tool'          (x5)
E       TypeError: plan_removal() got an unexpected keyword argument 'verify'     (x2)
E       AssertionError: assert () == (PosixPath('/...cal/bin/yq'),)
E       AssertionError: assert <UninstallSta...ED: 'managed'> == <UninstallSta...: 'removable'>
E         Left contains 2 more items, first extra item: PosixPath('.../test_corrupt_receipt_is_unprov0/.local/bin/rg')
```
Task 2 (`-k "remove_proven or receipt_proof"`): collection error for both files
```
E   ImportError: cannot import name 'remove_proven' from 'installer.uninstall'
```
Task 3 (`-k "reproves_per_tool or passes_the_selected_tools"`): 4 failed
```
E       AttributeError: 'UninstallDecision' object has no attribute 'tools'                 (x3, the screen tests)
E       TypeError: UninstallDecision.__init__() got an unexpected keyword argument 'tools'  (x1)
```

## Verify results

- Task 1: `pytest tests/test_uninstall.py` green; gate `-k ...` 11 passed (>= 11). Greps: `receipts.read(` 1, `receipts.drifted(` 1, version_status import 0.
- Task 2: `-k "remove_proven or run_uninstall or uninstall"` green; gate `-k "remove_proven or receipt_proof"` 7 passed (>= 6). `def remove_proven` 1, `remove_proven(` in app.py 1.
- Task 3: `pytest tests/test_app.py tests/test_setup.py tests/test_wizard_app.py -k "uninstall or Uninstall"` green; gate `-k "reproves_per_tool or passes_the_selected_tools"` 4 passed (>= 4). `still_removable` total 0; `tools=` in wizard_app.py 0 -> 1; `tool: Tool | None = None` 1; `tool=row.tool` 1. Suppression count 598 -> 598.
- Plan verification: `make validate` green and `make test` 4190 passed, 4 skipped, coverage 95.72% on the final tree; `pytest tests/test_uninstall.py tests/test_app.py tests/test_setup.py tests/test_uninstall_e2e.py -n auto` 360 passed. `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` clean.

### Large-file evidence (wc -l HEAD -> new, test functions)

- Task 1: tests/test_uninstall.py 1635 -> 1865, tests 78 -> 89
- Task 2: tests/test_uninstall.py 1865 -> 1947 (89 -> 94); tests/test_app.py 3704 -> 3725 (121 -> 122)
- Task 3: installer/wizard_app.py 3166 -> 3174; tests/test_app.py 3725 -> 3776 (122 -> 123); tests/test_setup.py 3460 -> 3557 (119 -> 120)
- `git diff --stat 22c5dcb..HEAD`: app.py 41, uninstall.py 110, wizard_app.py 12, test_app.py 102, test_setup.py 103, test_uninstall.py 312 (608 insertions, 72 deletions)

### Scripted conversion counts (Task 3)

tests/test_app.py: 14 constructions, 3 with real tools (`loop_tool("fd")` in `test_perform_uninstall_removes_only_chosen_levers`; the planted `fd` twice in `test_perform_uninstall_refuses_paths_changed_since_the_preview`) and 11 lever-only with `tools=()`. tests/test_setup.py: 3, all `tools=()`. installer/wizard_app.py: 1 (`tools=tuple(tools.values())`). All assertions unchanged.

## Deviations from Plan

1. [Rule 3 - Blocking] `test_uninstall_screen_passes_the_selected_tools` drives the real composition root (`setup.main(["--uninstall"])` with `_hermetic_route`). Its tool rows trigger the post-removal ownership refresh and terminal sync, so the test stubs `setup.resolve_github_tag` (raises OSError) and `setup._sync_terminals` (returns None). That keeps it offline and off the scratch HOME's terminal configs. It is test-only and inside tests/test_setup.py.
2. The worktree sandbox refused `bash -c '…git…'`, so I ran the plan's truncation-guard and suppression-guard one-liners as plain commands plus a scratch script, with the same checks. The scratch script has been deleted.
3. Once, during a check rerun, I invoked pytest with a fixed `-n 4`. That was a read-only rerun and changed nothing. The recorded runs used `-n auto` / `make test`.

Otherwise the plan executed as written.

## Notes for the orchestrator

- No file outside this plan's files_modified was touched. `perform_uninstall` now needs `decision.tools`. Any other plan in this wave that builds `UninstallDecision(` (none found at 22c5dcb outside these files) must pass `tools=`.
- An app-kind tool with a valid receipt now becomes removable through its bundle dir and cli link, because `artifact_paths` names both. A receipt-less app bundle stays remove-it-yourself as before.

## Self-Check: PASSED

- Files exist: installer/uninstall.py, installer/app.py, installer/wizard_app.py, tests/test_uninstall.py, tests/test_app.py, tests/test_setup.py
- Commits reachable from HEAD: 18fb2bd, 03fac47, 53cdc0b
