---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 05
subsystem: ownership
tags: [homebrew, cellar, ownership, off-policy, update]

requires:
  - phase: 16-01
    provides: sdkman location proof from bin_dir, so a declared SDKMAN copy can win or lose against an undeclared brew copy
provides:
  - undeclared Homebrew ownership from a Cellar path plus the brew inventory
  - off_policy, also_installed_note, active_path_note, and declared_manager_label
  - off-policy update detail that names the declared manager and does not migrate
affects: [16-15]

actuals:
  tokens: 10357
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Undeclared brew evidence is a resolved Cellar path plus an inventory listing, never the tool id"
    - "A link-proven brew copy is withheld from the native/os-package gate so the active owner stays the winner"

key-files:
  created: []
  modified:
    - installer/ownership.py
    - installer/update.py
    - tests/test_ownership.py
    - tests/test_update.py

key-decisions:
  - "Link-proven brew (bin/ or opt/) is shadow evidence. It does not block _native_owner or _os_package_owner. A declared brew candidate still does."
  - "off_policy is true only when the winner is that undeclared brew copy and a declared policy exists to differ from."
  - "rpm_ostree is labeled even though resolve_methods never returns it, because resolve.py hard-skips that kind."

patterns-established:
  - "Row texts for off-policy, dual-owner, and unknown-path come from ownership.py helpers. catalog_tui.py is unchanged in this plan."

requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-06, D-08]

coverage:
  - id: D1
    description: "A SDKMAN-declared groovy whose live binary is a brew Cellar path resolves to brew, direct, off_policy, and u runs brew upgrade groovy."
    requirement: D-01
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_undeclared_brew_cellar_groovy"
        status: pass
    human_judgment: false
  - id: D2
    description: "java under Cellar/openjdk resolves to brew package openjdk. The formula name comes from the path, not the tool id."
    requirement: D-01
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_undeclared_brew_cellar_java_formula_not_tool_id"
        status: pass
    human_judgment: false
  - id: D3
    description: "An active SDKMAN, OS-package, or keg-only-shadowed copy keeps that owner and records the brew copy for the also-installed note."
    requirement: D-06
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_undeclared_brew_shadowed_by_sdkman"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_undeclared_brew_shadowed_by_os_package"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_also_installed_note_names_homebrew_for_keg_only_shadow"
        status: pass
    human_judgment: false
  - id: D4
    description: "off_policy is false when no declared policy applies. declared_manager_label names SDKMAN, GitHub release, dnf, and rpm-ostree without raising."
    requirement: D-02
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_off_policy_requires_a_declared_policy"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_declared_manager_label_native_kind"
        status: pass
    human_judgment: false
  - id: D5
    description: "u on an off-policy brew copy runs brew upgrade and says migration to the declared manager is not available yet. No uninstall or migrate path was added."
    requirement: D-05
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_off_policy_brew_update_names_the_declared_manager"
        status: pass
      - kind: other
        ref: "grep -c uninstall installer/update.py == 0 before and after"
        status: pass
    human_judgment: false
  - id: D6
    description: "UpdateService.run re-resolves before mutating, so a cached off-policy record cannot authorise an update."
    requirement: D-01
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_update_service_fresh_unknown_overrides_cached_off_policy_brew"
        status: pass
    human_judgment: false

duration: 32min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 05: Real-owner Homebrew attribution Summary

**An undeclared Homebrew copy resolves from its Cellar path, and `u` updates that copy through brew with a note that migration is not available yet.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-10-10T11:00:00Z
- **Completed:** 2026-10-10T11:32:01Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- `_brew_cellar_formula` plus an undeclared brew candidate attributes groovy/java to Homebrew when the live file resolves under `Cellar/<formula>/` and `brew list` names that formula. A bad segment, a dangling link, a left-behind directory, or an unreadable inventory produces no claim.
- The active owner still wins. A brew copy found only through `<prefix>/bin/<cmd>` or keg-only `<prefix>/opt/<formula>/bin/<cmd>` stays in `candidates` and does not block an OS-package or SDKMAN active copy. Off PATH, that link is enough for by-elimination.
- `declared_manager_label`, `also_installed_note`, and `active_path_note` are the row texts. `off_policy` is true only when the winner is that undeclared brew copy and a declared policy exists.
- `u` runs `brew upgrade <formula>` and says the catalog's declared manager is not a move path yet. Nothing uninstalls or migrates.

## Task Commits

Each task was committed atomically:

1. **Task 1: Cellar path to candidate to resolve to brew upgrade argv** - `3d99721` (feat)
2. **Task 2: declared_manager_label, also_installed_note, active_path_note** - `fea21ff` (feat)
3. **Task 3: Off-policy update note and fresh re-resolve pin** - `33b5ad1` (feat)

**Plan metadata:** this file (`docs(16-05): summary for plan 16-05`)

TDD red was observed (owner `unknown`, missing helpers, empty update detail) and not committed. A failing-test commit would be a knowingly broken tree.

## Files Created/Modified

- `installer/ownership.py` - `off_policy`, `_brew_cellar_formula`, undeclared brew candidate, shadow withholding, row helpers
- `installer/update.py` - off-policy detail sentence after a successful brew/cask/uv dispatch
- `tests/test_ownership.py` - cellar, shadow, keg-only, off-path, and helper tests
- `tests/test_update.py` - off-policy note, empty on-policy detail, cached-record refusal

## Decisions Made

- Option (b) from the checker: a link-proven brew copy is not the live binary, so it is removed from the `_native_owner` / `_os_package_owner` gate and appended afterwards. `unknown` would have contradicted D-06 and D-08.
- `off_policy` additionally requires `declared_manager_label(tool, platform) is not None`.
- No migration code. `grep -c uninstall installer/update.py` was 0 before Task 3 and 0 after.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `resolve_methods` never returns `rpm_ostree`**
- **Found during:** Task 2 (declared_manager_label)
- **Issue:** `resolve.py` hard-skips `rpm_ostree`. The plan's resolve_methods-only algorithm would return None, and `test_declared_manager_label_native_kind` requires `"rpm-ostree"`.
- **Fix:** When no method applies, a platform-targeting `rpm_ostree` method is still labeled. Other filtered-out methods stay None, so `off_policy` stays false with no declared policy.
- **Files modified:** installer/ownership.py
- **Verification:** `test_declared_manager_label_native_kind` and `test_off_policy_requires_a_declared_policy` passed
- **Committed in:** `fea21ff`

**2. [Rule 3 - Blocking] Shortcut comment exceeded the 100-character gate**
- **Found during:** Task 1
- **Issue:** The plan's one-line shortcut comment is longer than ruff E501 allows.
- **Fix:** Wrapped it onto two physical lines. Wording unchanged.
- **Files modified:** installer/ownership.py
- **Verification:** `make validate` passed
- **Committed in:** `3d99721`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both keep the required rpm-ostree label and the line-length gate. No scope creep. No migration code.

`grep -n 'off_policy: bool = False' installer/ownership.py` returns two lines (the dataclass field and `_owned`'s default). The plan's acceptance text said one line. Both are the defaults the action required. Behavior is unchanged.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-15 can render `off_policy`, `also_installed_note`, and `active_path_note`. This plan does not touch `catalog_tui.py`.
- `u` on an off-policy brew-owned tool updates through brew and names the declared manager. Moving the tool is still deferred (D-04).

## Self-Check: PASSED

- `grep -n 'def _brew_cellar_formula' installer/ownership.py` returned one line (496).
- `grep -n 'off_policy: bool = False' installer/ownership.py` returned two lines (311, 1014). See Deviations.
- `grep -n 'shadow_brew' installer/ownership.py` returned more than two lines.
- `grep -n 'def declared_manager_label\|def also_installed_note\|def active_path_note' installer/ownership.py` returned three lines.
- `grep -n 'moving it there is not available yet' installer/update.py` returned one line.
- `grep -c uninstall installer/update.py` was 0 before Task 3 and 0 after.
- `uv run pytest tests/test_ownership.py tests/test_update.py -q -k "cellar or off_policy or undeclared or groovy"` passed (Task 1 filter, re-run inside the later full files).
- `uv run pytest tests/test_ownership.py -q -k "declared_manager_label or also_installed or active_path_note"` passed (9 tests).
- `uv run pytest tests/test_update.py -q` passed.
- `uv run pytest tests/test_ownership.py tests/test_update.py tests/test_version_status.py tests/test_catalog_tui.py -q` passed (100%, no FAILED).
- `uv run pytest -q` reached 100% and exited 0. Progress showed skips only, no FAILED.
- `make validate` passed (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
