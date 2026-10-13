---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 14
subsystem: ui
tags: [catalog, resolve, unavailable-reason]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: platform_could_support and the catalog unavailable map from earlier plans
provides:
  - UnavailableReason and unavailable_reason, tied to platform_could_support
  - Catalog rows and detail panes that name why a tool cannot be selected
affects: [16-16]

actuals:
  tokens: 4133
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - Reason text is classified from _applies' clause order, not from catalog-unsupported-tools.md prose

key-files:
  created: []
  modified:
    - installer/resolve.py
    - installer/catalog_tui.py
    - installer/wizard_app.py
    - installer/selection.py
    - setup.py
    - tests/test_resolve.py
    - tests/test_catalog_tui.py
    - tests/test_setup.py

key-decisions:
  - "A mixed rejection uses the sentence `no method applies here: <shorts>` as both short and detail, in method declaration order. The word mixed is the category, not the row text."
  - "A cask that fails the kind clause is classified as os, so the detail can name macos."

patterns-established:
  - "unavailable_reason returns None exactly when platform_could_support is True. The parity test pins that for every registry tool on four platforms."
  - "A bare True in the unavailable map still renders the old generic copy. A reason object renders short in the row and detail in the pane."

requirements-completed: [D-16]

coverage:
  - id: D1
    description: "A tool with no method on this platform is dimmed and unselectable, with a short reason in the row and a full sentence in the detail pane."
    requirement: D-16
    verification:
      - kind: unit
        ref: "tests/test_resolve.py#test_unavailable_reason_alacritty_names_immutable_host"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_unavailable_reason_renders_in_row_and_detail"
        status: pass
      - kind: unit
        ref: "tests/test_resolve.py#test_unavailable_reason_matches_platform_could_support_for_every_tool"
        status: pass
    human_judgment: false
  - id: D2
    description: "Shared, mixed, min-version, and empty-method rejections each produce a deterministic reason. A bare True keeps the old generic copy."
    requirement: D-16
    verification:
      - kind: unit
        ref: "tests/test_resolve.py#test_unavailable_reason_mixed_lists_shorts_in_declaration_order"
        status: pass
      - kind: unit
        ref: "tests/test_resolve.py#test_unavailable_reason_container_names_its_macos_floor"
        status: pass
      - kind: unit
        ref: "tests/test_resolve.py#test_unavailable_reason_empty_methods"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_bare_true_unavailable_keeps_generic_copy"
        status: pass
    human_judgment: false

duration: 30min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 14: Unavailable-reason Summary

**A catalog row with no install method on this platform names the mechanical reason instead of a generic dim.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-10-10T16:12:25Z
- **Completed:** 2026-10-10T16:42:13Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- `unavailable_reason` returns None exactly when `platform_could_support` is True, and otherwise a short plus a detail sentence.
- setup.py hands that reason to the catalog. The row shows `(not available: <short>)` and the detail pane shows the sentence. A bare True still uses the old generic copy.
- alacritty on immutable Fedora reads `immutable host`. gnu-bash and container on Fedora read `fedora not supported`. container on macOS 14 reads `needs macOS 26+`.

## Task Commits

Each task was committed atomically:

1. **Task 1: unavailable_reason, setup map, catalog row and detail** - `81e6d8f` (feat)
2. **Task 2: mixed, min-version, and empty-method edges** - `5b14904` (test)

## Files Created/Modified

- `installer/resolve.py` - `UnavailableReason`, `unavailable_reason`, `_rejection`
- `setup.py` - unavailable map values are a reason or False
- `installer/catalog_tui.py` - reason rendering; annotation widened
- `installer/wizard_app.py` - annotation widened
- `installer/selection.py` - `unstaged_recommends` unavailable annotation widened to `Mapping[str, object]`
- `tests/test_resolve.py` - registry, parity, and edge tests
- `tests/test_catalog_tui.py` - row, detail, and bare-True rendering
- `tests/test_setup.py` - apt-upgrade assertion now checks the reason's short

## Decisions Made

- Mixed reasons put `no method applies here: <shorts joined by '; '>` in both fields, in declaration order. `.short` is not the word `mixed`.
- A cask rejected by the kind clause counts as `os`, matching a native manager of another OS.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cast the untyped setup map value before narrowing**

- **Found during:** Task 1 (`make validate` / pyright)
- **Issue:** `seen[0]["unavailable"]` is unknown because setup.py is outside pyright. Assigning the apt-upgrade entry and reading `.short` was `reportUnknownVariableType`.
- **Fix:** `cast(object, unavailable["apt-upgrade"])` before `isinstance`.
- **Files modified:** `tests/test_setup.py`
- **Verification:** `uv run pyright` reported 0 errors.
- **Committed in:** `81e6d8f` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The assertion is the one the plan required. The cast only satisfies strict pyright. No scope creep.

## Issues Encountered

Task 2's three tests passed on the first run. Task 1's action already required the mixed, min-version, and empty-method shapes, so Task 2 only pinned them. No production change.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-16 can call `unavailable_reason` the same way setup.py does. A dimmed alacritty row already carries `(not available: immutable host)` and the ostree sentence.
- An `rpm_ostree`-only tool still gets short `immutable host` on a mutable host, as the plan specified. The registry has no such method.

## Self-Check: PASSED

- `grep -n 'def unavailable_reason\|class UnavailableReason' installer/resolve.py` returned lines 87 and 131.
- `grep -n 'unavailable_reason(tool, platform)' setup.py` returned line 784.
- `grep -n 'unavailable: Mapping\[str, object\] | None' installer/selection.py` returned line 94.
- `grep -n 'unavailable\["apt-upgrade"\] is True' tests/test_setup.py` returned nothing.
- `make validate` passed (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).
- `uv run pytest tests/test_resolve.py tests/test_catalog_tui.py tests/test_setup.py tests/test_wizard_app.py -q` exited 0.
- `uv run pytest -q` exited 0. No FAILED.

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
