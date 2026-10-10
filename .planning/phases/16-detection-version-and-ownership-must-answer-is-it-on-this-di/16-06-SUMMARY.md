---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 06
subsystem: version
tags: [sdkman, version, version_file, active_path]

requires:
  - phase: 16-01
    provides: sdkman ownership from the method's bin_dir, with method pinned on the location candidate
provides:
  - SDKMAN installed version from the current symlink target name
  - one _version_argv helper for every version probe
  - version_file reader for a declared first-line version
affects: [16-10]

actuals:
  tokens: 4329
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Version argv comes from _version_argv only: active_path, then declared bin_dir/cmd, then bare cmd"
    - "A declared version_file is the answer, including when the file has no version token"

key-files:
  created: []
  modified:
    - installer/version_status.py
    - tests/test_version_status.py
    - tests/test_wizard_app.py

key-decisions:
  - "SDKMAN source is sdkman with latest and outdated left None. No comparison is claimed."
  - "version_file is read only inside _probed_version. The github-release path still probes, always through _version_argv."
  - "_sdkman_current_version returns None when method is missing, so a method=None record cannot crash."

patterns-established:
  - "Pattern: on-disk version answers share _version_argv. No second [tool.cmd, --version] literal."

requirements-completed: [D-01, D-19]

coverage:
  - id: D1
    description: "An SDKMAN candidate's installed version is the name of the directory its current symlink points at, including through the real resolve_ownership record."
    requirement: D-01
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_sdkman_current_symlink_is_the_installed_version_without_a_probe"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_sdkman_version_through_real_resolve_ownership"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every version probe runs at active_path, else the declared bin_dir command file, else the bare command."
    requirement: D-19
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_probe_uses_resolved_active_path"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_github_release_probes_at_the_active_path"
        status: pass
    human_judgment: false
  - id: D3
    description: "A declared version_file supplies the installed version, and an unreadable or non-version file yields None without a subprocess probe."
    requirement: D-01
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_version_file_is_read_without_a_subprocess_probe"
        status: pass
    human_judgment: false

duration: 50min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 06: On-disk version answers Summary

**SDKMAN candidates report the version directory behind `current`, and every other probe runs at the resolved binary or a declared `version_file`.**

## Performance

- **Duration:** 50 min
- **Started:** 2026-10-10T11:21:00Z
- **Completed:** 2026-10-10T12:11:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `resolve_status` reads an SDKMAN candidate's version from `os.readlink` of the `current` directory named by `method.params["bin_dir"]`, with `source="sdkman"` and no probe.
- `_version_argv` is the only probe argv. `active_path` wins, then `ownership.method`'s `bin_dir/<cmd>` if that file exists, then any method `bin_dir`, then the bare command.
- A declared `version_file` is read as the first line and passed through `extract_observed_version`. Missing, undecodable, empty, or non-version content is `installed=None` and does not fall back to a subprocess.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end springbootcli shows 4.1.0** - `1a84e05` (feat)
2. **Task 2: Probe at the resolved absolute path, and version_file support** - `1c1f7ca` (feat)
3. **Follow-up: install-closed stub matches the resolved probe path** - `4fed51c` (fix)

**Plan metadata:** this summary commit (`docs(16-06): summary for plan 16-06`)

## Files Created/Modified

- `installer/version_status.py` - `_sdkman_current_version`, `_version_argv`, `_version_file`; sdkman branch; ownership kwarg on the github path
- `tests/test_version_status.py` - symlink, dangling, unparseable, real `resolve_ownership`, argv order, and version_file cases
- `tests/test_wizard_app.py` - install-closed probe stub keys off the command name

## Decisions Made

- SDKMAN reports `latest=None`, `outdated=None`, `stale=False`, `source="sdkman"`. The symlink is read on this pass, and no latest comparison is claimed.
- `version_file` short-circuits only `_probed_version`. `resolve_github_release_status` always calls `_version_argv`, including when ownership is omitted.
- `_sdkman_current_version` tests `Path(bin_dir).is_dir()` directly. The parent is used only for `readlink`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Install-closed version stub still matched the bare command**
- **Found during:** Task 2 verification (`uv run pytest -q`)
- **Issue:** `test_install_closed_marks_a_freshly_installed_row_and_keeps_an_unreadable_one` returned a version only when `argv[0]` was the bare cmd. The service's `which` sets `active_path` to `managed/cmd`, so the probe now runs there and the stub returned None ("no version").
- **Fix:** Compare `Path(argv[0]).name` so the presence contract still sees the probe answer at the resolved path.
- **Files modified:** tests/test_wizard_app.py
- **Verification:** that test passed, then `make test` (3273 passed, 5 skipped).
- **Committed in:** `4fed51c`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The production change is the plan. The test stub had encoded the old bare-cmd argv. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-10 can declare `version_file = "~/.sdkman/var/version"` on the sdkman script method. This plan already reads it.
- A tool owned by `installer` that also has a `github_release` method still probes; `version_file` is not consulted on that path. The sdkman tool has no github method, so its file reader is the installer fallthrough.

## Self-Check

- `grep -n 'def _sdkman_current_version' installer/version_status.py` — one line (266).
- `grep -n 'source="sdkman"' installer/version_status.py` — one line (395).
- `grep -c 'tool.cmd, "--version"' installer/version_status.py` — 1.
- `grep -n 'def _version_argv\|def _version_file' installer/version_status.py` — lines 223 and 240.
- SDKMAN tests, including `test_sdkman_version_through_real_resolve_ownership`, passed with zero probe calls on the happy path.
- `make validate` passed after the last code change (ruff, format, pyright, bandit, vulture, shellcheck).
- `uv run pytest tests/test_version_status.py tests/test_catalog_tui.py tests/test_ownership.py -q` exited 0 with no FAILED.
- `uv run pytest -q` exited 0 with no FAILED.
- `make test`: 3273 passed, 5 skipped, coverage 95.96% (floor 90%).

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
