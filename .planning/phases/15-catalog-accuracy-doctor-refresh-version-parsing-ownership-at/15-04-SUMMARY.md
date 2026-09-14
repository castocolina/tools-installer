---
phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
plan: "04"
subsystem: catalog-ownership
tags: [rpm-ostree, ownership-detection, registry, pyright-strict, tdd]

# Dependency graph
requires:
  - phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
    provides: "15-03's tier fixes (D-07/D-08/D-09/D-10), the registry base this plan's ten rows edit"
provides:
  - "A new `_rpm_ostree` ownership probe in installer/install_ownership.py, registered in `_PROBES` and `installer/model.py`'s `OWNER_PROBES` closed set"
  - "Ten registry rows (rg, jq, git, zsh, watch, docker, podman, kitty, opencode, wezterm) declaring `owner_probes` so `detect_owner` can actually dispatch for them"
  - "A permanent closed-set-equality test between `OWNER_PROBES` and `_PROBES`, asserted in both directions"
affects: ["15-05"]

# Actuals (#2632)
actuals:
  tokens: 3509
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "New ownership probes mirror the existing `_apt`/`_dnf`/`_pacman` shape exactly: `_method_values` -> `_run` -> parse -> `Ownership(...)` or `None`, registered by name in `_PROBES`"
    - "A probe can read a registry field belonging to a DIFFERENT method kind than its own name (rpm-ostree reads the `dnf` method's `package`) when the two mechanisms share the same underlying package name and inventing a duplicate registry field would be an unrequested schema change"

key-files:
  created: []
  modified:
    - installer/install_ownership.py
    - installer/model.py
    - installer/registry.toml
    - tests/test_install_ownership.py
    - tests/test_registry.py

key-decisions:
  - "D-06: _rpm_ostree reads the tool's declared dnf package name (not a new registry field) and only consults the BOOTED deployment's requested-packages list"
  - "D-05: rpm-ostree is listed FIRST in owner_probes on every dnf/apt/pacman-capable row, so a layered package is attributed to the mechanism that layered it rather than falling through to the rpm database"
  - "Per-tool probe cost stays uncached, matching the three existing native probes' shape -- deliberately deferred, see 'Known follow-up' in the plan"

patterns-established:
  - "Closed-set schema additions (OWNER_PROBES <-> _PROBES) must be tested in BOTH subset directions, not just one -- the direction that bites in production is the one where a registry-declarable name has no dispatch implementation, raising KeyError at runtime instead of failing to load"

requirements-completed: ["D-06", "D-05"]

coverage:
  - id: D1
    description: "A new _rpm_ostree probe answers ownership for a dnf-declaring tool from the booted rpm-ostree deployment's explicitly layered packages, failing closed (None, never an exception) on every malformed/absent/non-booted input"
    requirement: "D-06"
    verification:
      - kind: unit
        ref: "tests/test_install_ownership.py -k rpm_ostree"
        status: pass
    human_judgment: false
  - id: D2
    description: "OWNER_PROBES and _PROBES are asserted equal in both directions by a permanent test, closing the runtime KeyError gap a one-way subset check would miss"
    verification:
      - kind: unit
        ref: "tests/test_install_ownership.py::test_owner_probes_closed_set_and_probe_registry_are_the_same_set"
        status: pass
    human_judgment: false
  - id: D3
    description: "The ten registry rows with a native dnf/apt/pacman method declare owner_probes (rpm-ostree first on the eight that can layer, pacman-only on opencode/wezterm), and the exact membership of that ten-row set is pinned"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_registry.py::test_native_package_manager_rows_declare_their_owner_probes"
        status: pass
    human_judgment: false

duration: 32min
completed: 2026-09-14
status: complete
---

# Phase 15 Plan 04: rpm-ostree Ownership Probe and Registry Opt-In Summary

**A new `_rpm_ostree` probe answers "does the OS own this tool?" on Bazzite/Silverblue from the booted deployment's explicitly-layered packages, and the ten dnf/apt/pacman-capable registry rows now declare which probes to ask.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-09-14T22:45:00Z (approx.)
- **Completed:** 2026-09-14T23:17:25Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `installer/install_ownership.py::_rpm_ostree` -- reads the tool's declared `dnf` package name, runs `rpm-ostree status --json` through the existing `_run` swallow, narrows the parsed JSON with `isinstance` checks, and matches against only the `booted: true` deployment's `requested-packages` list
- `"rpm-ostree"` registered in the existing `_PROBES` dict AND added to `installer/model.py`'s `OWNER_PROBES` closed tuple -- both required, since `detect_owner` indexes `_PROBES` directly with no `.get`/default
- A permanent test (`-k owner_probes` in `tests/test_install_ownership.py`) asserts `OWNER_PROBES` and `_PROBES` are equal in BOTH directions, closing the cycle-2 review finding that a one-way subset check misses the direction that actually raises `KeyError` at runtime
- Ten registry rows (`rg`, `jq`, `git`, `zsh`, `watch`, `docker`, `podman`, `kitty`, `opencode`, `wezterm`) now declare `owner_probes`, with `rpm-ostree` listed first on the eight that can layer via dnf/apt/pacman
- A pinning test (`-k owner_probes` in `tests/test_registry.py`) asserts both the exact per-id values and that the SET of ids declaring any native probe is exactly those ten

## Task Commits

Each task followed the RED -> GREEN cycle (`tdd="true"`):

1. **Task 1: an rpm-ostree ownership probe, registered and schema-legal (D-06)**
   - `1c801d0` - `test(15-04): add failing tests for rpm-ostree ownership probe (D-06)` (RED)
   - `5d86076` - `feat(15-04): add rpm-ostree ownership probe, close the schema (D-06)` (GREEN)
2. **Task 2: the ten native-package-manager rows declare the probes that can answer for them (D-05)**
   - `672838e` - `test(15-04): add failing pin for native-manager owner_probes rows (D-05)` (RED)
   - `b58d859` - `feat(15-04): wire owner_probes on the ten native-manager registry rows (D-05)` (GREEN)

No REFACTOR commit was needed for either task -- both GREEN implementations landed clean on the first pass, with no obvious cleanup remaining.

**Plan metadata:** (see final commit below)

## Files Created/Modified
- `installer/install_ownership.py` - New `_rpm_ostree` probe, registered in `_PROBES`
- `installer/model.py` - `"rpm-ostree"` added to `OWNER_PROBES`
- `installer/registry.toml` - Ten `[[tool]]` rows gain `owner_probes`
- `tests/test_install_ownership.py` - 9 new `rpm_ostree`-named tests, 1 permanent closed-set-equality test, `_manager_for` extended for the new command
- `tests/test_registry.py` - 1 new pinning test for the ten native-manager rows

## Decisions Made
- Followed the plan's D-05/D-06 decisions exactly as specified in CONTEXT.md -- no deviation from the locked design.
- Test structure: dedicated `rpm_ostree`-named test functions (not folded into the existing `test_owner_verifies_each_manager_from_its_own_output` parametrize table), because `-k rpm_ostree` selection requires the substring in the test's own name/id, and a parametrize id of `rpm-ostree` (hyphen) would not match a `-k rpm_ostree` (underscore) filter.

## Deviations from Plan

None - plan executed exactly as written. The only unplanned addition was a scoped `# pyright: ignore[reportPrivateUsage]` on the new closed-set-equality test's `ownership._PROBES` access, needed because pyright strict flags private-member access across module boundaries; this follows the project's own existing suppression convention (narrowest scope, one-line comment, matches `tests/test_daemon.py`/`tests/test_setup.py`/`tests/test_catalog_tui.py` precedent) rather than a new pattern.

## Known follow-up, deliberately out of this plan

`detect_owner` still has no production caller after this plan lands -- it is reachable only from `tests/test_install_ownership.py`, exactly as before. This is a knowing, one-plan-long violation of `.claude/architecture.md` rule 5 ("no orphan helpers"), closed by plan 15-05 in the next wave, which calls it from `installer/ownership.py::resolve_ownership`. Neither plan reaches a released build on its own: they are the same phase, and the phase is not verifiable until both have landed. **15-05 remains mandatory before phase-level verification.**

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The probe and the closed-set schema are fully tested and ready for 15-05 to wire into `installer/ownership.py`'s live resolution path.
- 15-05 still needs to: widen the `Literal` type used by the strict type checker for the adapted `"direct"` confidence value, and add the refusal branch to `update.py::_perform`'s owner-dispatch `if/elif/else` (currently has no branch for the new native-manager owner names).
- This plan alone does NOT change any resolution result for any tool in the catalog -- `owner="unknown"` behavior is unchanged until 15-05 lands.

## Self-Check: PASSED

- FOUND: `.planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-04-SUMMARY.md`
- FOUND: `installer/install_ownership.py`, `installer/model.py`, `installer/registry.toml`
- FOUND commits: `1c801d0`, `5d86076`, `672838e`, `b58d859`

---
*Phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at*
*Completed: 2026-09-14*
