---
phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
plan: "05"
subsystem: catalog-ownership
tags: [ownership-detection, dnf, apt, pacman, rpm-ostree, update-refusal, pyright-strict, tdd]

# Dependency graph
requires:
  - phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
    provides: "15-04's rpm-ostree probe, OWNER_PROBES/_PROBES closed-set registration, and the ten native-manager registry rows declaring owner_probes"
provides:
  - "installer/ownership.py::resolve_ownership consults install_ownership.detect_owner through a new _native_owner adapter, placed before the active-path unknown branch (not at the function's end) so a real dnf/apt/pacman-installed tool with an unattributable live PATH actually resolves through it"
  - "Owner widened to include the four native manager names; NATIVE_OWNERS: tuple[Owner, ...] declared once in ownership.py and imported by installer/update.py's refusal branch, so the catalog's attribution set and the update path's refusal set cannot drift apart"
  - "installer/update.py::_perform refuses the four native owners cleanly (status=\"unsupported\", concrete manager named in UpdateOutcome.detail, zero subprocess) before the owner-dispatch ladder, never reaching the ladder's `unsupported owner` else-raise"
  - "VersionRefreshService accepts a native_probe seam (default None) threaded into resolve_ownership; setup.py wires install_ownership.run_probe at both the display-path service construction and the mutation-path _reresolve_ownership closure"
  - "CatalogScreen._version_detail labels all four native owners, naming the manager and stating this installer will not update it"
affects: []

# Actuals (#2632)
actuals:
  tokens: 8355
  tasks: 3
  commits: 7

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Adapter pattern for confidence-vocabulary translation: install_ownership.Ownership.confidence='verified' maps to ownership.py's ManagerOwnership.confidence='direct' through one private helper (_native_owner), never by re-implementing probe/parsing logic in the consuming module (.claude/architecture.md rule 5)"
    - "A single shared closed tuple (NATIVE_OWNERS) read by two modules (the attribution adapter and the update refusal) so membership cannot drift — a fifth name added later is refused automatically without a second edit"
    - "Composition-root (setup.py) wiring pinned by source-text inspection tests (occurrence counts of a keyword argument) because setup.py is deliberately excluded from pyright/coverage — the only place this repo can pin that wiring is a read of the committed file"

key-files:
  created: []
  modified:
    - installer/ownership.py
    - installer/update.py
    - installer/version_status.py
    - installer/catalog_tui.py
    - setup.py
    - tests/test_ownership.py
    - tests/test_update.py
    - tests/test_version_status.py
    - tests/test_catalog_tui.py
    - tests/test_setup.py

key-decisions:
  - "D-05: resolve_ownership's native adapter call site sits immediately after the active-candidate branch and immediately before the active-path unknown branch — not at the function's final _unknown(...) as 15-RESEARCH.md's Pattern 3 sketch suggested — because a real dnf-installed tool's live /usr/bin/<cmd> is unattributable and returns from the earlier branch on a real machine"
  - "The synthesized native candidate is threaded into its own candidates=(synthetic,) tuple with shadowed=False, mirroring the synthetic-script by-elimination precedent, so the record never claims an owner while its own candidate list says nobody claims the tool"
  - "A leftover installer artifact alongside a live native-manager install suppresses the native claim and the probe is never run — pinned by a dedicated test, not special-cased fixed, because resolving it properly would be a precedence change to the module's core evidence rule that this plan's boundary explicitly does not widen"
  - "installer/update.py's refusal branch reads the shared NATIVE_OWNERS tuple rather than restating the four names inline, and _NATIVE_OWNER_DETAIL interpolates the CONCRETE matched owner into UpdateOutcome.detail rather than a generic phrase"
  - "VersionRefreshService.native_probe defaults to None (not install_ownership.run_probe), deliberately breaking the surrounding query/which convention, so unit tests constructing the service never acquire a dnf/apt/pacman/rpm-ostree subprocess"
  - "install_ownership.run_probe (stdin=DEVNULL) is wired at both composition-root sites, never installer.run.run_query, because these probes run on a Textual worker thread while the main thread holds the terminal in raw/alt-screen mode"
  - "No second ownership gate was added to CatalogScreen.action_update_tool: the existing owner==\"unknown\" or confidence-not-in-MUTATION_GRADE gate is unchanged, a native owner deliberately passes it, and the refusal a user reads comes from UpdateService.run -> perform_update -> the update.py refusal branch, rendered by on_tool_updated's existing non-updated line"
  - "resolve_status's final branch (installed/latest=None/outdated=None/stale=True/source=\"unknown\") is deliberately untouched for these owners and is pinned by a direct field-by-field assertion, not an ownership-only proxy — there is genuinely no latest-version source for dnf/apt/pacman/rpm-ostree, and VersionStatus.source is not widened to carry the owner name"

requirements-completed: ["D-05", "D-06"]

coverage:
  - id: D1
    description: "A tool the OS package manager actually owns (dnf/apt/pacman/rpm-ostree) resolves to that manager instead of unknown, including on the real-machine case where the live binary is unattributable to any tracked owner"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_ownership.py -k native"
        status: pass
    human_judgment: false
  - id: D2
    description: "The evidence rule is preserved: the native claim requires complete negative evidence (no tracked candidate, no unreadable inventory), a leftover installer artifact suppresses it, and a tracked manager's own claim always wins first"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_ownership.py -k native"
        status: pass
    human_judgment: false
  - id: D3
    description: "Owner is widened with the four native names declared once as NATIVE_OWNERS, consumed by both the adapter's translation table and update.py's refusal condition, with no cast/# type: ignore"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_ownership.py::test_native_owners_tuple_is_the_four_widened_values"
        status: pass
    human_judgment: false
  - id: D4
    description: "installer/update.py::_perform refuses all four native owners cleanly (status=unsupported, concrete manager named in detail, zero subprocess) before the owner-dispatch ladder, never raising UpdateError(\"unsupported owner ...\")"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_update.py -k native"
        status: pass
    human_judgment: false
  - id: D5
    description: "The running application actually asks: VersionRefreshService and setup.py's _reresolve_ownership both pass install_ownership.run_probe, so the display and mutation paths resolve a native owner the same way"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_version_status.py -k native"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py::test_native_probe_is_wired_at_both_the_display_and_mutation_sites"
        status: pass
    human_judgment: false
  - id: D6
    description: "resolve_status's final branch is untouched for a native owner, pinned field by field (latest is None, outdated is None, stale is True, source == \"unknown\")"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_version_status.py::test_native_probe_service_resolves_owner_and_status_stays_on_final_branch"
        status: pass
    human_judgment: false
  - id: D7
    description: "The catalog detail line names the owning OS manager for all four native owners and states this installer will not update it; the update key still routes through UpdateService with no second screen-local gate"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py -k native"
        status: pass
    human_judgment: false

duration: 29min
completed: 2026-09-14
status: complete
---

# Phase 15 Plan 05: Native-Manager Ownership Attribution and Update Refusal Summary

**A dnf/apt/pacman/rpm-ostree-installed tool now resolves to its real owner in the live catalog instead of `unknown`, on both the browsing and update-attempt paths, and pressing `u` on it produces a clean refusal naming the manager instead of a raised "unsupported owner" error.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-09-14T23:18:00Z (approx.)
- **Completed:** 2026-09-14T23:47:17Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- `installer/ownership.py::resolve_ownership` gains a `native_probe` seam and a `_native_owner` adapter that calls `install_ownership.detect_owner` (never re-implementing a probe) and adapts its `"verified"` confidence to this module's `"direct"` — placed at the ONE call site that covers both unknown branches, both by-elimination branches, and the real-machine unattributable-live-path case
- `Owner` widened to include `"dnf"`, `"apt"`, `"pacman"`, `"rpm-ostree"`; the four names live in exactly one place — `ownership.py`'s new public `NATIVE_OWNERS` tuple — consumed by the adapter's translation table AND `installer/update.py`'s refusal condition
- `installer/update.py::_perform` gains an explicit refusal branch for `NATIVE_OWNERS`, placed before the SDKMAN branch's sibling position and before the owner-dispatch ladder: `status="unsupported"`, the concrete manager interpolated into `UpdateOutcome.detail` via `_NATIVE_OWNER_DETAIL`, zero subprocess, zero filesystem write
- `VersionRefreshService` threads a `native_probe: ProbeRunner | None = None` parameter into its `resolve_ownership` call; `setup.py` wires `install_ownership.run_probe` at both the display-path service construction and the mutation-path `_reresolve_ownership` closure
- `CatalogScreen._version_detail`'s label map gains an entry for each of the four native owners, naming the manager and stating the no-update fact — no second ownership gate was added to `action_update_tool`

## Task Commits

Each task followed the RED -> GREEN cycle (`tdd="true"`), plus one style-only follow-up:

1. **Task 1: a native-manager-owned tool resolves to its real owner and is refused cleanly by the update path (D-05)**
   - `6090492` - `test(15-05): add failing tests for native-manager ownership adapter (D-05)` (RED)
   - `d9cc74d` - `feat(15-05): wire install_ownership.detect_owner into resolve_ownership and refuse native updates (D-05)` (GREEN)
2. **Task 2: the running application passes a real probe on both the display and the mutation path**
   - `63937e4` - `test(15-05): add failing tests for the native-probe service seam and composition-root wiring (D-05)` (RED)
   - `9ff1d8c` - `feat(15-05): thread a real native probe through both the display and mutation ownership paths (D-05)` (GREEN)
3. **Task 3: the catalog detail line names the OS manager that owns the row**
   - `48329c9` - `test(15-05): add failing tests for native-owner catalog detail labels (D-05)` (RED)
   - `c93c4c7` - `feat(15-05): label the four native owners in the catalog detail line (D-05)` (GREEN)
4. **Style follow-up:** `5272491` - `style(15-05): apply ruff format to test_ownership.py's D-05 test helper` (no behavior change; `ruff format` collapsed a two-line signature)

No REFACTOR commit was needed for any task — each GREEN implementation passed `pyright --strict`, `ruff check`, and `ruff format --check` on the first pass.

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `installer/ownership.py` - Widened `Owner`, `NATIVE_OWNERS` tuple, `_native_owner` adapter, `native_probe` parameter on `resolve_ownership`
- `installer/update.py` - `_NATIVE_OWNER_DETAIL` constant, refusal branch in `_perform` reading `NATIVE_OWNERS`
- `installer/version_status.py` - `native_probe` keyword on `VersionRefreshService`, threaded into `refresh`'s `resolve_ownership` call
- `installer/catalog_tui.py` - Four new entries in `_version_detail`'s `labels` dict
- `setup.py` - `install_ownership.run_probe` imported and wired at both composition-root ownership-resolution sites
- `tests/test_ownership.py` - 8 new `native`-named tests plus a `native_probe` kwarg on the `_resolve` helper
- `tests/test_update.py` - Parameterized `native`-named refusal test over all four owners, plus a `NATIVE_OWNERS` pin test
- `tests/test_version_status.py` - 2 new `native`-named tests plus a `_native_owned_service`/`_jq_tool` fixture pair
- `tests/test_catalog_tui.py` - 2 new `native`-named tests (detail-line label, end-to-end `u`-press through the real `UpdateService`)
- `tests/test_setup.py` - 1 new source-inspection test pinning both `native_probe=` wiring sites

## Decisions Made

Followed the plan's D-05 decisions exactly as specified in CONTEXT.md and the plan's cycle-2 review dispositions (shared `NATIVE_OWNERS` tuple, concrete-owner-name requirement in `UpdateOutcome.detail`, direct `resolve_status` final-branch field assertion) — no deviation from the locked design. See `key-decisions` above for the specific implementation choices within that design (adapter call-site placement, candidates/shadowed self-consistency, leftover-artifact suppression, `native_probe` default).

## Deviations from Plan

None — plan executed exactly as written. The only unplanned addition was a `ruff format` auto-reformat of a two-line function signature in `tests/test_ownership.py` (collapsed onto one line), caught by `make validate` and committed as a separate style-only commit (`5272491`) rather than folded into a feature commit.

## Known Follow-ups, Deliberately Out of This Plan

(Restated from the plan, confirmed still true after implementation.)

- **`version_status.resolve_status` has no branch for the four native owners.** A native-owned tool falls to the module's final branch (`installed=probed, latest=None, outdated=None, stale=True, source="unknown"`), which is correct — this installer genuinely has no source for a dnf/apt/pacman/rpm-ostree "latest" report. `VersionStatus.source` is deliberately NOT widened to carry the owner name. Pinned directly by `tests/test_version_status.py::test_native_probe_service_resolves_owner_and_status_stays_on_final_branch`.
- **A machine holding both a stale installer artifact and a live native-manager install resolves to `unknown`, on purpose,** with the native probe never run. This is the candidate guard failing closed (the evidence rule this module already follows for every other source of positive evidence), pinned by `tests/test_ownership.py::test_native_owner_suppressed_by_leftover_installer_artifact`. Resolving it properly (preferring a live executable over a stale artifact) would be a precedence change to the module's core evidence rule — out of this plan's stated boundary (attribution correctness, not evidence-rule redesign).
- **Really updating a dnf/apt/pacman/rpm-ostree package needs privilege escalation this installer has never required.** Every other owner (brew, cask, pnpm, uv, installer) is user-space; the refusal branch added here is what keeps the newly-correct attribution from silently becoming an incorrect mutation capability. That capability is a different phase's scope.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `install_ownership.detect_owner` is no longer an orphan helper — this plan closes the `.claude/architecture.md` rule 5 violation 15-04's SUMMARY flagged as knowingly deferred.
- Phase 15's four bugs (Doctor stale guidance, version-parsing false-negative, ownership disconnection, tier misclassification) are all now addressed across plans 15-01 through 15-05.
- `installer/version_status.py::resolve_status` remains a documented, tested gap for a future phase that would want to surface a "latest" comparison for native-manager-owned tools (e.g. reading `dnf check-update` output) — not started here, and the module docstring/this SUMMARY record why.

## Self-Check: PASSED

- FOUND: `.planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-05-SUMMARY.md`
- FOUND: `installer/ownership.py`, `installer/update.py`, `installer/version_status.py`, `installer/catalog_tui.py`, `setup.py`
- FOUND commits: `6090492`, `d9cc74d`, `63937e4`, `9ff1d8c`, `48329c9`, `c93c4c7`, `5272491`

---
*Phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at*
*Completed: 2026-09-14*
