---
phase: 18-registry-truth-and-drift-guard
plan: "22"
subsystem: installer
tags: [registry, ownership-proof, install-ladder, OSError, apps, download]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: staged swap install paths (18-09 archives, 18-11 apps)
provides:
  - Shared `download.is_still_proven(path, root=None)` for install and uninstall
  - Archive and app install proof gates before download or staging
  - Unified app finalize (`.old` cleanup on install and update)
  - Per-method `OSError` capture in `install_tool`
affects: [phase-19-receipts, registry-truth]

actuals:
  tokens: 42000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Prove ownership via CLI symlink before mutating ~/.local/opt or ~/Applications"
    - "Filesystem errors stay on one method; rollback failures become ExecutorError with prior path"

key-files:
  created: []
  modified:
    - installer/download.py
    - installer/uninstall.py
    - installer/apps.py
    - installer/engine.py
    - tests/test_download.py
    - tests/test_apps.py
    - tests/test_engine.py
    - .claude/architecture.md

key-decisions:
  - "Moved `is_still_proven` into download.py with optional `root` for app bundles; uninstall imports it unchanged in behavior."
  - "App staging uses `tempfile.mkdtemp(..., dir=apps)` to avoid EXDEV on bundle move."
  - "Undecodable checksum files use UTF-8 replace so missing entries surface as ordinary ExecutorError."

patterns-established:
  - "Install and uninstall share one proof function; gates fail the method and leave foreign trees byte-identical."

requirements-completed: [REG-04, REG-05]

coverage:
  - id: D1
    description: Archive install refuses unproven ~/.local/opt trees; proven reinstall still works
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_download.py#test_install_refuses_an_unproven_opt_tree_and_leaves_it_byte_identical
        status: pass
      - kind: unit
        ref: tests/test_download.py#test_install_replaces_a_proven_opt_tree
        status: pass
    human_judgment: false
  - id: D2
    description: App install/update share finalize path, proof gate, Applications-filesystem staging
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_apps.py#test_install_over_a_proven_bundle_leaves_no_old_bundle
        status: pass
      - kind: unit
        ref: tests/test_apps.py#test_app_staging_stays_on_the_applications_filesystem
        status: pass
    human_judgment: false
  - id: D3
    description: OSError and rollback failures stay on one method; batch continues
    requirement: REG-05
    verification:
      - kind: unit
        ref: tests/test_engine.py#test_an_oserror_in_one_method_falls_through_to_the_next
        status: pass
      - kind: unit
        ref: tests/test_download.py#test_rollback_failure_names_both_errors_and_the_old_tree
        status: pass
    human_judgment: false

duration: 120min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 22 Summary

**Install and uninstall share one ownership proof; app and archive paths fail closed on unproven trees; disk errors stay on one method.**

## Performance

- **Duration:** ~120 min
- **Tasks:** 3 (+ summary commit)
- **Files modified:** 8

## Task Commits

1. **Task 1: archive opt proof gate (CR-02, IN-01)** — `b8eeae7`
2. **Task 2: app finalize, proof, EXDEV (WR-01, M3, opencode MEDIUM)** — `7e335d1`
3. **Task 3: OSError ladder, raw cleanup, checksum decode (WR-07, IN-07)** — `3be825c`

**Plan metadata:** (this commit) `docs(18-22): plan summary`

## Per-finding disposition

| ID | Source | Outcome | Commit | Test |
|----|--------|---------|--------|------|
| CR-02 | 18-REVIEW | fixed | b8eeae7 | `test_install_refuses_an_unproven_opt_tree_and_leaves_it_byte_identical`, restored `test_reinstall_never_writes_through_a_link_to_a_directory` |
| WR-01 | 18-REVIEW | fixed | 7e335d1 | `test_install_over_a_proven_bundle_leaves_no_old_bundle` |
| M3 | ponytail | fixed | 7e335d1 | same as WR-01 |
| opencode MEDIUM (.old) | 18-REVIEW-opencode | fixed | 7e335d1 | same as WR-01 |
| opencode MEDIUM (EXDEV) | 18-REVIEW-opencode | fixed | 7e335d1 | `test_app_staging_stays_on_the_applications_filesystem` |
| WR-07 | 18-REVIEW | fixed | 3be825c, 7e335d1 | `test_an_oserror_in_one_method_falls_through_to_the_next`, `test_app_rollback_failure_reports_both_errors_and_the_old_bundle`, rollback archive tests |
| UnicodeDecodeError checksum | planner | fixed | 3be825c | `test_undecodable_checksum_file_is_an_ordinary_method_failure` |
| IN-01 docstrings | 18-REVIEW | fixed | b8eeae7, 3be825c | `test_docs.py` (architecture); `resolve_target` / `_perform` docstrings |
| IN-07 smoke fall-through | 18-REVIEW | fixed | 3be825c | `test_smoke_failure_falls_through_to_the_next_method` + mutation RED |

## TDD RED evidence (trimmed)

**Task 1** (`uv run pytest tests/test_download.py -k "unproven or proven_opt or explicit_root or link_to_a_directory"`):

- `ImportError: cannot import name 'is_still_proven' from 'installer.download'`
- After partial gate: `test_install_refuses_an_unproven_opt_tree...` expected `not proven` (gate not yet matching message)

**Task 2** (`uv run pytest tests/test_apps.py -k "proven_bundle or unproven_bundle or applications_filesystem or rollback_failure"`):

- 5 failed: `.old` left behind, unproven installs succeeded, EXDEV, raw OSError on rollback

**Task 3** (`uv run pytest ... -k "oserror or staged_sibling or rollback_failure or undecodable or falls_through_to_the_next"`):

- 5 failed: `OSError` escaped `install_tool`, partial `.new` left, rollback/raw OSError, checksum read path

**IN-07 mutation** (temporary `smoke_argv=None` on install `_replace_archive`):

- `test_smoke_failure_falls_through_to_the_next_method` failed: `bin_dir / "rg2"` not a symlink (reverted before commit; `git diff installer/` empty)

## wc -l / diff-stat (pre-commit snapshots)

| Commit | Notable files | wc -l / stat |
|--------|---------------|--------------|
| b8eeae7 | test_download.py | 1958 lines; +106/-4 in test file |
| b8eeae7 | architecture.md | 1024 lines; +2/-1 |
| 7e335d1 | test_apps.py | ~849 lines total after; +170/-23 |
| 3be825c | test_engine.py | 1694 lines; test_download.py 2044 lines |

## Existing tests adjusted for proof gate

| Test | Intent |
|------|--------|
| `test_reinstall_never_writes_through_a_link_to_a_directory` (2nd half) | Unproven opt + link-to-directory must refuse install and keep bytes |
| `test_pinned_tarball_is_verified_against_its_sha256` (2nd half) | Checksum mismatch on reinstall: plant proving `bin2/rg` link so gate allows fetch |

## Verify commands

- Task 1: `uv run pytest tests/test_download.py tests/test_uninstall.py tests/test_app.py -q --no-cov` — pass
- Task 2: `uv run pytest tests/test_apps.py tests/test_engine.py tests/test_uninstall.py -q --no-cov` — pass
- Task 3: `make validate && make test` — pass (3883 passed, 4 skipped)

## Deviations from Plan

None — large test files edited via out-of-band Python scripts to avoid editor truncation; no plan file changes.

## Issues for orchestrator

None.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
