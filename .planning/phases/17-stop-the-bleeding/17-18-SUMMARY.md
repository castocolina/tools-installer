---
phase: 17-stop-the-bleeding
plan: "18"
subsystem: uninstall
tags: [symlink, removal-proof, download, raw-install, test-hygiene, race-test, doctor-guidance]

requires:
  - phase: 17-stop-the-bleeding
    provides: plan_removal strict removal proof, link_executable regular-file guard, race test harness in tests/test_version_status.py
provides:
  - loop-safe removal proof (plan_removal / is_still_proven / still_removable)
  - deletion-time re-proof on both uninstall apply paths (run_uninstall, perform_uninstall)
  - update paths require a regular executable live binary (download._replace_archive, apps._validate_app)
  - raw installs land via sibling temp + os.replace, never writing through an existing link
  - conditional doctor broken-link repair wording
  - suppression-free, split-literal-free tests; two-generation race test (two `type: ignore[arg-type]` added in ad63b1f were removed by 17-21, e63f983)
affects: [17-19, 17-20, phase-18-data-fixes, phase-22-uninstall-sweep]

actuals:
  tokens: 27700
  tasks: 4
  commits: 4

tech-stack:
  added: []
  patterns:
    - "deletion-time re-proof: a preview list is revalidated immediately before remove_paths, refusals reported one line each"

key-files:
  created: []
  modified:
    - installer/uninstall.py
    - installer/app.py
    - installer/download.py
    - installer/apps.py
    - installer/guidance.py
    - tests/test_uninstall.py
    - tests/test_app.py
    - tests/test_download.py
    - tests/test_apps.py
    - tests/test_guidance.py
    - tests/test_doctor.py
    - tests/test_engine.py
    - tests/test_catalog_tui.py
    - tests/test_version_status.py

key-decisions:
  - "IN-05 resolved via the docstring option (smaller and correct): link_name now states that install/update pass the rendered member while uninstall passes the raw registry template; no registry-validation change"
  - "TUI-side H1 reporting goes through the existing SweepResult.warnings channel, which UninstallScreen._applied_summary already renders — no new class or plumbing"
  - "Two existing download tests asserting the removed cp/chmod call sequences were updated to the new _replace_raw behavior (strengthened, not weakened)"

patterns-established:
  - "Per-link proof predicate: uninstall.is_still_proven(path) is the single strict (resolve strict=True, except OSError/RuntimeError) layout proof; plan_removal and both deletion paths share it"

requirements-completed: [SAFE-01, SAFE-03, CI-01]

coverage:
  - id: D1
    description: "A looping bin link or opt dir is unproven, never a crash: plan_removal, classify_tools and run_uninstall survive a self-loop at a catalog link name"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_plan_removal_survives_looping_link_and_opt_dir"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_run_uninstall_survives_a_looping_link"
        status: pass
    human_judgment: false
  - id: D2
    description: "A proven link replaced between preview and confirm is refused and reported, not deleted, on both the CLI and TUI apply paths"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_run_uninstall_refuses_paths_changed_since_the_preview"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_perform_uninstall_refuses_paths_changed_since_the_preview"
        status: pass
    human_judgment: false
  - id: D3
    description: "Update paths require a regular executable live binary; a directory member rolls back and reports failure (update_download and update_app)"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_download.py#test_update_download_directory_member_rolls_back"
        status: pass
      - kind: unit
        ref: "tests/test_apps.py#test_update_app_directory_cli_rolls_back"
        status: pass
    human_judgment: false
  - id: D4
    description: "Raw installs never write through an existing link: asset lands via sibling temp + os.replace on both verified and unverified branches; no shelled cp/chmod/curl -o <link>"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_download.py#test_raw_install_replaces_a_link_instead_of_writing_through_it"
        status: pass
      - kind: unit
        ref: "tests/test_download.py#test_verified_raw_install_replaces_a_link_instead_of_writing_through_it"
        status: pass
    human_judgment: false
  - id: D5
    description: "Doctor broken-link repair wording is conditional and never advises rm -rf on an unproven tree"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "tests/test_guidance.py#test_broken_link_guidance_names_the_opt_dir_repair"
        status: pass
      - kind: unit
        ref: "tests/test_doctor.py#test_run_doctor_reports_broken_links_and_changes_nothing"
        status: pass
    human_judgment: false
  - id: D6
    description: "Test hygiene: no pyright suppression for the worker wait, no split string literals, race test runs two writer generations (stress 20/20 at -n auto)"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py (worker wait via asyncio.gather, no ignore)"
        status: pass
      - kind: other
        ref: "uv run pytest tests/test_version_status.py -q --no-cov -n auto -p no:randomly (20/20 runs green)"
        status: pass
    human_judgment: false

duration: ~22min
completed: 2026-10-14
status: complete
---

# Phase 17 Plan 18 Summary

**Review-finding closure in the uninstall/download area: the removal proof is loop-safe and re-checked at deletion time, update and raw-install paths never link or write through a non-regular file, doctor repair wording is conditional, and the test-hygiene debts (suppression, split literals, one-generation race test) are paid.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-10-15T01:15Z (approx., first test edit)
- **Completed:** 2026-10-15T01:36Z (last task commit)
- **Tasks:** 4
- **Files modified:** 14

## Per-finding outcomes

| ID | Source lane | Outcome | Commit | Test |
|----|-------------|---------|--------|------|
| CR-01 | gsd-code-reviewer | fixed | ad63b1f | `tests/test_uninstall.py#test_plan_removal_survives_looping_link_and_opt_dir`, `tests/test_app.py#test_run_uninstall_survives_a_looping_link` |
| H1 | opencode | fixed | ad63b1f | `tests/test_app.py#test_run_uninstall_refuses_paths_changed_since_the_preview`, `tests/test_app.py#test_perform_uninstall_refuses_paths_changed_since_the_preview` |
| IN-03 | gsd-code-reviewer | fixed | ad63b1f | rename verified by `grep -rn youself` (0 hits) + full suite |
| IN-05 | gsd-code-reviewer | fixed (docstring option) | ad63b1f | docstring; behavior unchanged by design |
| WR-03 | gsd-code-reviewer / ponytail #2 | fixed | 9038f17 | `tests/test_download.py#test_update_download_directory_member_rolls_back`, `tests/test_apps.py#test_update_app_directory_cli_rolls_back` |
| WR-04 | gsd-code-reviewer | fixed | 9038f17 | `tests/test_download.py#test_raw_install_replaces_a_link_instead_of_writing_through_it`, `tests/test_download.py#test_verified_raw_install_replaces_a_link_instead_of_writing_through_it` |
| IN-02 | gsd-code-reviewer | fixed | adf5389 | `tests/test_guidance.py#test_broken_link_guidance_names_the_opt_dir_repair`, `tests/test_doctor.py#test_run_doctor_reports_broken_links_and_changes_nothing` |
| WR-07 | gsd-code-reviewer | fixed | f6cd226 | `tests/test_catalog_tui.py` worker wait via `asyncio.gather`, zero ignores (grep-verified) |
| IN-04 | gsd-code-reviewer | fixed | f6cd226 | `SHELLED_LINKERS` in `tests/test_apps.py`, imported by `tests/test_engine.py` |
| M4 | opencode | fixed | f6cd226 | two-generation writer loop; stress 20/20 green |

## TDD RED evidence

Task 1 (CR-01 + H1), tests written first against the unfixed tree:

```
E       RuntimeError: Symlink loop from '/tmp/.../test_plan_removal_survives_loo0/.local/bin/foo'
E       OSError: [Errno 40] Too many levels of symbolic links: ... bin/foo
FAILED tests/test_uninstall.py::test_plan_removal_survives_looping_link_and_opt_dir
FAILED tests/test_app.py::test_run_uninstall_survives_a_looping_link (RuntimeError)
>       assert removed == []
E       AssertionError: assert [PosixPath('.../opt/fd')] == []   (foreign replacement file deleted through the stale preview)
FAILED tests/test_app.py::test_run_uninstall_refuses_paths_changed_since_the_preview
FAILED tests/test_app.py::test_perform_uninstall_refuses_paths_changed_since_the_preview
```

Task 2 (WR-03 + WR-04), tests written first:

```
E   Failed: DID NOT RAISE <class 'installer.executors.ExecutorError'>      (directory-member update reported success)
E   IsADirectoryError: ... bin/yq                                          (curl wrote through the link into the foreign dir)
E   AssertionError: assert not link.is_symlink()                           (verified raw cp'd through the link; link intact)
FAILED ... 4 tests
```

Task 3 and Task 4 are not `tdd="true"`; test expectations were updated with the fix in the same commit.

## Verify-command results

- `uv run pytest tests/test_uninstall.py tests/test_app.py -q --no-cov` — 130 passed
- `uv run pytest tests/test_download.py tests/test_apps.py -q --no-cov` — 135 passed
- `uv run pytest tests/test_guidance.py tests/test_doctor.py -q --no-cov` — 67 passed
- `uv run pytest tests/test_catalog_tui.py tests/test_apps.py tests/test_engine.py tests/test_version_status.py -q --no-cov` — 126 passed
- M4 stress: `uv run pytest tests/test_version_status.py -q --no-cov -n auto -p no:randomly` — **20/20 runs green**
- `make validate` — exit 0 (ruff check/format, pyright strict, bandit, vulture, shellcheck)
- `make test` — **3551 passed, 4 skipped, coverage 95.95%** (gate 90%)

## Deviations from Plan

Two small auto-fixed items, both inside the plan's intent:

1. **`tests/test_doctor.py` expectation updated** (found during Task 3 verify): `test_run_doctor_reports_broken_links_and_changes_nothing` also asserted the old `"reinstall subl"` wording. Updated to assert the new conditional wording (`"If tools-installer installed it"` + `"reinstall the tool from the catalog"`, and `"reinstall subl" not in out`). Strengthened, not weakened. Caught because the verify command was run before committing; the Task 3 commit was amended to stay coherent.
2. **Two download tests asserting the removed call sequences updated** (Task 2): `test_github_release_raw_downloads_binary_directly` and `test_verified_raw_copies_from_temp_into_bin` asserted the exact `chmod +x <link>` / `cp <asset> <link>` calls WR-04 removes. They now assert the `_replace_raw` behavior (sibling temp + `os.replace`, mode 0o755, no cp/chmod). Also, `test_perform_uninstall_removes_only_chosen_levers` planted a plain file where production only ever passes a proven link+opt-dir pair; its fixture was upgraded to a real proven pair and its `bin_dir` made HOME-sandboxed.

**Total deviations:** 3 test-fixture/expectation updates, all forced by the planned behavior changes. No scope creep.

## Issues Encountered

- `plan_removal`'s resolve raises either `OSError` (ELOOP surfaced as "Too many levels of symbolic links") or `RuntimeError` depending on the loop's entry point; the catch is `except (OSError, RuntimeError)` as the plan specified, and both variants are exercised by the RED run.
- `perform_uninstall`'s proof needs no tool list: the per-path form (`is_still_proven` plus the opt-dir half, `still_removable`) is exactly `plan_removal`'s predicate because `_download_link` always maps the opt dir from the link name alone, independent of a declared `bin_dir`.

## Next Phase Readiness

- SAFE-01's "never write through or link a non-regular file" invariant now holds on install, update, raw, and app paths; 17-19/17-20 can build on `is_still_proven`/`still_removable` for any further removal hardening.
- The registry's directory-member data defects (e.g. Sublime) remain deferred to Phase 18 data fixes as planned; the code now rolls such updates back instead of relinking a directory.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
