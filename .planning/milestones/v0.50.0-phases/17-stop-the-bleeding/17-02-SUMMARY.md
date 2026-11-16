---
phase: 17-stop-the-bleeding
plan: "02"
subsystem: installer
tags: [symlink-safety, atomic-writes, archive-install, executors, tdd]

requires:
  - phase: 12-update-action
    provides: atomic.replace_symlink sibling-temp symlink replacement
provides:
  - executors.link_executable — the one is_file()-checked, atomic link helper used by all three linking sites
  - tests/test_download.py::fixture_runner — public shared test runner that materializes the extracted member on disk
  - no install path shells chmod/ln for the tool link; directory members raise ExecutorError before any write
affects: [17-04-doctor-scan, 17-05-registry-fix, 18-digests]

actuals:
  tokens: 63000
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "link_executable(binary, link, member, *, chmod=True): one helper owning the is_file() check, os.chmod 0o755 and atomic.replace_symlink"
    - "fixture_runner(workdir, files, *, member=None): filesystem-assertion test runner shared by test_download/test_apps/test_engine"

key-files:
  created: []
  modified:
    - installer/executors.py
    - installer/download.py
    - installer/apps.py
    - tests/test_download.py
    - tests/test_apps.py
    - tests/test_engine.py

key-decisions:
  - "One helper (executors.link_executable) owns the is_file() check, the 0o755 chmod and atomic.replace_symlink for all three linking sites; the app site passes chmod=False because install_app never changed a mode inside a bundle"
  - "_relink_app_cli (update path) stays as-is: reusing link_executable there would be a no-op refactor; the plan's contract is the three install sites"
  - "Tests assert the link on disk (is_symlink, os.readlink, mode) through the shared fixture_runner instead of recording shelled ln/chmod argv"

patterns-established:
  - "link_executable: refuse-then-link — a non-regular-file member raises ExecutorError (message names the member) before any mode change or link write, so the engine ladder falls through"
  - "fixture_runner: one public runner materializing the extracted member as a file on tar/unzip/ditto extraction calls"

requirements-completed: [SAFE-01]

coverage:
  - id: D1
    description: "Unverified archive: directory member links nothing (ExecutorError naming the member); file member links atomically at mode 0o755 with no shelled ln/chmod"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_download.py#test_unverified_archive_with_a_directory_member_links_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_download.py#test_unverified_archive_links_the_member_file_atomically"
        status: pass
  - id: D2
    description: "Reinstall over an existing link-to-directory leaves the directory's files byte-identical and replaces only the link"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_download.py#test_reinstall_over_a_link_to_a_directory_leaves_its_files_byte_identical"
        status: pass
  - id: D3
    description: "Sublime-shaped case: bin_name 'subl' links to sublime_text/sublime_text inside the opt dir"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_download.py#test_tarball_bin_name_overrides_the_symlink_name"
        status: pass
  - id: D4
    description: "Verified archive path links through link_executable; directory member links nothing"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_download.py#test_verified_archive_with_a_directory_member_links_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_download.py#test_verified_archive_links_the_member_file_atomically"
        status: pass
  - id: D5
    description: "App bundle CLI links with chmod=False (bundle mode untouched); a directory CLI links nothing"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_apps.py#test_install_app_symlinks_declared_cli"
        status: pass
      - kind: unit
        ref: "tests/test_apps.py#test_install_app_cli_that_is_a_directory_links_nothing"
        status: pass
  - id: D6
    description: "engine.install_tool falls through the method ladder on the ExecutorError (outcome brew, no link, no engine change)"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_engine.py#test_github_release_directory_member_falls_through_the_ladder"
        status: pass

duration: 55min
completed: 2026-10-14
status: complete
---

# Plan 17-02 Summary

**All three install linking sites (unverified archive, verified archive, app bundle CLI) now link through one `executors.link_executable` that refuses non-file members and replaces links atomically — no install can create a link to a directory or write through one**

## Performance

- **Duration:** ~55 min across two runs (first run stopped by a provider quota after Task 1's commit)
- **Completed:** 2026-10-14
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- `installer/executors.py::link_executable(binary, link, member, *, chmod=True)` — raises `ExecutorError("archive member '<member>' is not a regular file: <path>")` when the member is not a regular file, then `chmod(0o755)` (unless `chmod=False`) and `atomic.replace_symlink`; any `OSError` becomes a chained `ExecutorError`
- `download._install_unverified` and `download._place_verified` replaced their shelled `chmod +x` / `ln -sf` with `link_executable`; `apps.install_app` replaced its `ln -sf` with `link_executable(..., chmod=False)`
- `tests/test_download.py::fixture_runner(workdir, files, *, member=None)` (public, replaces `_fixture_runner`) materializes the extracted member as a regular file on extraction calls; used by test_download, test_apps and test_engine
- Engine unchanged: the ExecutorError from the link helper falls through the method ladder like any executor error (proven by `test_github_release_directory_member_falls_through_the_ladder`: outcome `installed` via `brew`, no link)

## Task Commits

1. **Task 1: one archive path end to end — unverified tarball links only a regular file, atomically** - `5305479` (fix)
2. **Task 2: expand to the verified archive path and the app CLI link** - `91d3664` (feat)

## TDD RED evidence

Task 1 (from the first run, committed in `5305479`; failing tests against the pre-change tree included):
```
FAILED tests/test_download.py::test_unverified_archive_with_a_directory_member_links_nothing - Failed: DID NOT RAISE <class 'ExecutorError'>
FAILED tests/test_download.py::test_unverified_archive_links_the_member_file_atomically - AssertionError: assert not any(... cmd[0] in {'ln','chmod'} ...)
```

Task 2 (this run; new tests run with only the production diff of Task 2 reverted via `git stash push installer/apps.py installer/download.py`):
```
FAILED tests/test_apps.py::test_install_app_symlinks_declared_cli - AssertionError
FAILED tests/test_apps.py::test_install_app_cli_that_is_a_directory_links_nothing - Failed: DID NOT RAISE <class 'ExecutorError'>
FAILED tests/test_download.py::test_verified_archive_with_a_directory_member_links_nothing - Failed: DID NOT RAISE <class 'ExecutorError'>
FAILED tests/test_download.py::test_verified_archive_links_the_member_file_atomically - AssertionError: assert <...>.is_symlink
```

Note: `test_github_release_directory_member_falls_through_the_ladder` passes against the Task 1 tree alone because it exercises the unverified path, which Task 1 already fixed; it is the ladder-behavior proof required by Task 2's behavior list, and its RED is covered by Task 1's evidence.

## Verify-command results

- `uv run pytest tests/test_download.py -q --no-cov -k "directory_member or links_the_member_file or link_to_a_directory or bin_name_overrides"` — 6 passed (Task 1 verify; run after resume: 6 passed)
- `uv run pytest tests/test_download.py tests/test_engine.py -q --no-cov` — 77 passed
- `uv run pytest tests/test_download.py tests/test_apps.py tests/test_engine.py -q --no-cov` — 94 passed
- `uv run pytest tests/test_download.py tests/test_apps.py -q --no-cov -k "directory or links_the_member_file or symlinks_declared_cli"` — 7 passed
- `make validate` — all hooks pass
- `make test` — 3473 passed, 4 skipped, coverage 95.87% (floor 90%)
- Acceptance greps: `link_executable(` count download=2 apps=1; `chmod=False` apps=1 download=0; `"ln"` in `_install_unverified` body = 0; `"ln"`/`["chmod", "+x"` argv assertions in test_apps.py/test_engine.py = 0 (the negative `cmd[0] == "ln"` check at tests/test_apps.py:237 stays, as the plan allows); `def fixture_runner` = 1, `_fixture_runner` = 0

## Decisions Made
- Followed D-01 exactly: three sites, one helper, `os.chmod` + `replace_symlink`, no shelled `chmod`/`ln` for the link anywhere
- Kept the plan's scope boundary: the raw-asset branch of `_install_unverified` and the raw `cp`/`chmod` branch of `_place_verified` stay unchanged (not linking sites); the optional update-path guards RESEARCH listed as not required were not added

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- The run was interrupted by a provider quota after Task 1's commit, leaving the Task 2 edits uncommitted in the working tree. On resume, the edits were reviewed against the plan (they matched), RED evidence for Task 2 was regenerated by stashing the Task 2 production diff, and the work was committed as one coherent Task 2 commit.

## User Setup Required

None.

## Next Phase Readiness
- 17-04 (Doctor scan for dangling/link-to-directory findings) and 17-05 (Sublime registry `member` fix) can proceed against the fixed linking behavior; the already-damaged host link remains until the user follows Doctor's repair
- Real archive behavior is exercised end to end by `make e2e` in plan 17-13

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
