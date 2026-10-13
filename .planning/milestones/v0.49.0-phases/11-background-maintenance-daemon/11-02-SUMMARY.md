---
phase: 11-background-maintenance-daemon
plan: 02
subsystem: infra
tags: [policy, launchd, textual, transactional-apply, hard-requires]

# Dependency graph
requires:
  - phase: 11-background-maintenance-daemon
    provides: "installer/daemon.py's mechanism layer (render_plist/write_plist/read_schedule/bootstrap/bootout/install_wrapper/remove_wrapper/ensure_log_path/decided/record_decided/DaemonScheduleError/_atomic_write), built by 11-01"
provides:
  - "installer/policy.py::Policy gains five additive fields: hard_requires (bool, default True), log_path, set_schedule, read_schedule, is_active — all inert (None/True) for ban/tweak:*/omz-plugins"
  - "installer/wizard_app.py::action_toggle_policy's enable gate now respects hard_requires, so a hard_requires=False policy toggles on even with missing_requires non-empty"
  - "installer/wizard_app.py::_requires_cell/_policy_detail render accurate 'recommended, not required' copy for a hard_requires=False policy, leaving the hard-block copy byte-for-byte unchanged"
  - "installer/policy.py::daemon_policy — the transactional apply/remove/set_schedule factory composing installer/daemon.py, parallel to omz_plugins_policy"
affects: [11-03-detail-panel-ui, 11-04-composition-and-on-by-default]

# Actuals (#2632)
actuals:
  tokens: 4573
  tasks: 3
  commits: 7

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Policy.hard_requires as an additive, default-preserving escape hatch from the existing hard-block missing_requires gate — only daemon_policy passes hard_requires=False"
    - "daemon_policy mirrors omz_plugins_policy's single-artifact + state_path ownership-record shape, extended with a validate-before-any-filesystem-side-effect helper and full apply/remove/set_schedule rollback-with-best-effort-re-bootstrap transactionality"
    - "A marker-write (record_decided) failure after an already-successful launchctl call degrades PolicyResult.warning instead of rolling back or propagating — the real registration and the plist already agree at that point"

key-files:
  created:
    - tests/test_policy_daemon.py
  modified:
    - installer/policy.py
    - installer/wizard_app.py
    - tests/test_wizard_app.py
    - tests/test_policies_e2e.py

key-decisions:
  - "daemon_policy's shared validation-plus-write helper calls daemon.render_plist purely as a validation gate BEFORE install_wrapper/ensure_log_path/write_plist ever run, so a DaemonScheduleError never leaves a partially-created wrapper or log file behind (11-REVIEWS.md cycle 2 finding #6)."
  - "apply()'s rollback on a bootstrap failure branches on whether a prior plist existed: a reapply restores the snapshot bytes via daemon._atomic_write and makes a best-effort re-bootstrap of the restored content (cycle 2 finding #5); a first-ever apply instead deletes the plist and rolls back only the wrapper/log THIS call newly created, never an artifact that legitimately predates it (cycle 3 finding #1)."
  - "Both apply()'s and remove()'s record_decided failures degrade to PolicyResult.warning rather than propagating or rolling back a now-correct launchctl registration (cycle 2 finding #7, cycle 3 finding #2) — action_toggle_policy only updates active_state when run_live's result is non-None, so a propagated OSError there would have misreported a genuinely-running daemon as off."
  - "remove()'s own plist unlink is guarded with a best-effort re-bootstrap of the still-on-disk (unlink-failed) content before the OSError re-raises (cycle 2 finding #8); remove_wrapper gains its first production caller inside remove() itself, with its own unlink failure also degrading to a warning rather than reporting a false removal failure (cycle 2 finding #9, cycle 3 finding #3)."
  - "set_schedule(hour, minute) rejects an inactive policy (no existing plist) via DaemonScheduleError before touching anything, as a core-layer guard independent of 11-03's own UI-layer gate (cycle 3 finding #5); every plist-bytes rollback (apply's reapply path, set_schedule's own rollback) writes through daemon._atomic_write, never a raw write_bytes call (cycle 3 finding #4)."
  - "Reworded a docstring's 'hard_requires=False' prose mention to 'hard_requires is False' after make test's own grep-based verification (11-02-PLAN.md <verification>) caught it as a second, accidental match against the exactly-1 call-site invariant."

patterns-established:
  - "A shared internal validate-then-write helper as the single choke point every filesystem side effect passes through, mirroring 11-01's own DaemonScheduleError single-choke-point pattern one layer up."
  - "Best-effort re-bootstrap-with-restored-content after every plist-bytes rollback, since daemon.bootstrap's own internal bootout-then-bootstrap pre-clear unconditionally tears the OLD registration out before every attempt — restoring only the file's bytes without re-registering them would make `active` a false positive."

requirements-completed: [REQ-launchd-prune-policy, REQ-daemon-dependency-gating]

coverage:
  - id: D1
    description: "Policy.hard_requires (+ log_path/set_schedule/read_schedule/is_active) is additive and default-preserving; action_toggle_policy's gate respects it; _requires_cell/_policy_detail render accurate 'recommended, not required' copy for a hard_requires=False policy, leaving the existing hard-block copy unchanged"
    requirement: "REQ-daemon-dependency-gating"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_policy_missing_required_tool_blocks_enable (unmodified, still passing)"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_policy_with_hard_requires_false_still_enables_when_requires_missing_with_recommended_copy"
        status: pass
    human_judgment: false
  - id: D2
    description: "daemon_policy factory (parallel to omz_plugins_policy) with fully transactional apply/remove/set_schedule: validate-before-any-side-effect, snapshot-and-roll-back-with-best-effort-re-bootstrap on a bootstrap/unlink failure, marker-write failures degrading to PolicyResult.warning, remove_wrapper's first production caller"
    requirement: "REQ-launchd-prune-policy"
    verification:
      - kind: unit
        ref: "tests/test_policy_daemon.py (19 tests: apply/remove round trip, schedule preservation, validation ordering, is_active/hard_requires shape, and the full failure-injection matrix)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A real daemon_policy with fd/rg both missing toggles ON via space in a headless PoliciesScreen pilot (writing a real plist file, the concrete proof apply() ran), rendering the new 'recommended'/'Recommended tool(s)... not required' copy — never the hard-block wording — at the real UI layer"
    requirement: "REQ-daemon-dependency-gating"
    verification:
      - kind: e2e
        ref: "tests/test_policies_e2e.py#test_daemon_policy_toggles_on_despite_missing_fd_and_rg_with_recommended_copy"
        status: pass
    human_judgment: false

# Metrics
duration: 23min
completed: 2026-09-07
status: complete
---

# Phase 11 Plan 02: Daemon Policy Factory Summary

**`Policy.hard_requires` gate fix (soft fd/rg dependency, accurate copy) plus `daemon_policy` — a fully transactional apply/remove/reschedule factory composing 11-01's LaunchAgent mechanism, with a complete failure-injection test matrix covering every rollback path.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-09-07T00:44:19-03:00
- **Completed:** 2026-09-07T01:06:56-03:00
- **Tasks:** 3
- **Files modified:** 5 (1 created test file, 4 modified)

## Accomplishments
- `installer/policy.py::Policy` gains five new, additive, default-preserving fields (`hard_requires: bool = True`, `log_path`, `set_schedule`, `read_schedule`, `is_active`) — every existing `Policy(...)` construction site (`ban_policy`, `tweak_policy`, `omz_plugins_policy`) is byte-for-byte unaffected.
- `installer/wizard_app.py::action_toggle_policy`'s enable-time gate is now `if not active and policy.missing_requires and policy.hard_requires:` — the single line that resolves 11-RESEARCH.md's Common Pitfall 1 (the docker/`watch` hard-block pattern REQ-daemon-dependency-gating names as its template contradicted that same requirement's "apply never refuses to run" text).
- `_requires_cell`/`_policy_detail` gained a new, additive branch: a `hard_requires=False` policy with missing requirements now renders "recommended: fd, rg" / "Recommended tool(s): fd, rg. Not required — apply still runs and falls back automatically." — never the hard-block "missing:"/"Missing required tool(s)... before enabling" wording, which was literally false for a policy whose apply never refuses to run.
- `installer/policy.py::daemon_policy` is a new factory, parallel to `omz_plugins_policy`, composing every function `installer/daemon.py` (11-01) exposes — `render_plist`/`write_plist`/`read_schedule`/`bootstrap`/`bootout`/`ensure_log_path`/`install_wrapper`/`remove_wrapper`/`record_decided`/`_atomic_write` — into three fully transactional closures: `apply()`, `remove()`, and `set_schedule(hour, minute)`.
- A shared internal validation-plus-write helper calls `daemon.render_plist` purely as a validation gate before `install_wrapper`/`ensure_log_path`/`write_plist` ever run, so an invalid `tmpdir_value`/`home_value` leaves zero filesystem side effects — not merely zero side effects from `write_plist` alone.
- `apply()`'s rollback on a `bootstrap` failure distinguishes a first-ever apply (rolls back the plist plus any wrapper/log THIS call newly created, preserving anything that legitimately predates it) from a reapply (restores the snapshot bytes via `daemon._atomic_write` and makes a best-effort re-`bootstrap` of the restored content, since `bootstrap`'s own internal pre-clear always tears the old registration out first).
- `remove()` calls `bootout` first (a real failure propagates before the plist is ever touched), guards its own plist unlink with a best-effort re-`bootstrap` of the still-on-disk content on failure, and calls `remove_wrapper` — its first production caller in the whole codebase — before `record_decided`.
- Marker-write (`record_decided`) failures after an already-successful `bootstrap`/`bootout`/unlink degrade both `apply()`'s and `remove()`'s result to `PolicyResult.warning` rather than rolling back a now-correct registration or propagating a misleading `OSError` — `action_toggle_policy` only updates `active_state` when `run_live`'s result is non-`None`, so a propagated exception there would have reported a genuinely-running (or genuinely-removed) daemon as failed.
- `set_schedule(hour, minute)` rejects an inactive policy (no existing plist) via `DaemonScheduleError` before touching anything, as a core-layer guard independent of 11-03's own UI-layer gate.
- A real, headless `PoliciesScreen` pilot test (`tests/test_policies_e2e.py`) proves the whole chain end to end: a real `daemon_policy` with `fd`/`rg` both missing toggles ON via `space` (writing a real plist file — the concrete proof `apply()` ran, not merely the absence of an exception), rendering the new "recommended, not required" copy, never the hard-block wording.

## Task Commits

Each task was committed via a RED/GREEN TDD pair (per `tdd="true"`):

1. **Task 1: `Policy.hard_requires`/`read_schedule` fields, gate fix, accurate soft-dependency copy**
   - `2bd3093` test(11-02): add failing test for hard_requires=False soft-dependency gate (RED)
   - `acd96de` feat(11-02): add Policy.hard_requires gate fix and accurate soft-dependency copy (GREEN)
2. **Task 2: `daemon_policy` factory with transactional apply/remove/reschedule**
   - `9e8b813` test(11-02): add failing tests for daemon_policy transactional apply/remove/reschedule (RED)
   - `83379e3` feat(11-02): implement daemon_policy with transactional apply/remove/reschedule (GREEN)
3. **Task 3: End-to-end proof — soft dependency gating and accurate copy at the UI layer**
   - `4456e9f` test(11-02): prove soft dependency gating and accurate copy at the UI layer

_Note: Task 3's single commit passed on the first run with zero production changes — Tasks 1 and 2 already implemented everything it exercises, so this task is a pure integration proof, not a new-feature RED/GREEN pair. See "TDD Gate Compliance" below._

4. **Post-execution fixes** (not plan tasks; closes gaps found during final gate verification):
   - `432e05b` fix(11-02): reword daemon_policy docstring so hard_requires=False is unique
   - `8d69b93` test(11-02): close a coverage gap for the first-ever-apply log rollback branch

## Files Created/Modified
- `installer/policy.py` - `Policy`'s five new fields; `daemon_policy` factory with transactional `apply`/`remove`/`set_schedule`
- `installer/wizard_app.py` - `action_toggle_policy`'s gate fix; `_requires_cell`/`_policy_detail`'s new soft-dependency copy branch
- `tests/test_policy_daemon.py` - 19 tests: full apply/remove round trip, schedule preservation, validation-before-side-effects, `set_schedule`-on-inactive rejection, and the complete failure-injection matrix
- `tests/test_wizard_app.py` - the new inverse test proving a `hard_requires=False` policy enables despite missing requirements, with accurate copy
- `tests/test_policies_e2e.py` - the real, headless `PoliciesScreen` pilot proof of the whole chain end to end

## Decisions Made
- Placed `daemon_policy` immediately after `omz_plugins_policy` (its structural template) rather than after `omz_removal_detail`, per the plan's own "immediately after `omz_plugins_policy`" instruction.
- Used a private, locally-duplicated `_DAEMON_WRAPPER_COMMAND` string constant (mirroring `installer.daemon._WRAPPER_COMMAND`'s value) for the validation-only `render_plist` call's "would-be" wrapper path, rather than importing the private constant across modules — the validation call only checks `is_absolute()`, so the literal value only needs to match the shape, not be import-shared. `daemon._atomic_write` itself, by contrast, is called directly across modules (with a narrow `# pyright: ignore[reportPrivateUsage]` per call site) because it is the actual crash-safety algorithm being reused, not a value being shaped — duplicating that logic would be a real DRY violation, unlike a filename string.
- Added `test_apply_bootstrap_failure_on_first_ever_apply_preserves_a_pre_existing_log` (a sibling to the plan's own pre-existing-wrapper test) after `make test`'s coverage report flagged `installer/policy.py:430->432` as the one untested branch (the `log_existed_before=True` path of the first-ever-apply rollback). `installer/policy.py` now has 100% line/branch coverage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reworded a docstring to satisfy the plan's own `hard_requires=False` uniqueness invariant**
- **Found during:** Final `<verification>` pass (all `grep`-based checks from 11-02-PLAN.md's `<verification>` block)
- **Issue:** `daemon_policy`'s docstring mentioned the literal string `hard_requires=False` in prose, making `grep -n "hard_requires=False" installer/policy.py | wc -l` report `2` instead of the plan-mandated exactly `1`.
- **Fix:** Reworded the docstring to "`hard_requires` is False" — same meaning, no second literal match.
- **Files modified:** `installer/policy.py`
- **Verification:** `grep -n "hard_requires=False" installer/policy.py | wc -l` now reports `1`.
- **Committed in:** `432e05b`

**2. [Rule 2 - Missing Critical] Closed a coverage gap in `apply()`'s first-ever-apply rollback**
- **Found during:** Final `make test` coverage report, after all three tasks' own tests passed
- **Issue:** The `log_existed_before=True` branch of `apply()`'s first-ever-apply rollback (a pre-existing log surviving the rollback, symmetric to the plan's own pre-existing-wrapper test) had no test, leaving one uncovered branch (`installer/policy.py:430->432`).
- **Fix:** Added `test_apply_bootstrap_failure_on_first_ever_apply_preserves_a_pre_existing_log`, mirroring the plan's own pre-existing-wrapper test shape.
- **Files modified:** `tests/test_policy_daemon.py`
- **Verification:** `installer/policy.py` now shows 100% line/branch coverage in `make test`'s report.
- **Committed in:** `8d69b93`

---

**Total deviations:** 2 auto-fixed (1 verification-compliance wording fix, 1 test-coverage gap closed)
**Impact on plan:** No scope creep and no change to designed behavior — both were surfaced by running the plan's own gates (`<verification>` block, `make test`'s coverage report), not architectural changes.

## Issues Encountered
- Task 3's test passed immediately on its first run with zero production code changes, since Tasks 1 and 2 already fully implemented everything it exercises. Per the task's own description ("Task 3 proves the two compose correctly together, end to end, at the UI layer"), this is the expected, correct outcome for a pure integration-proof task, not a RED-phase failure to investigate — see "TDD Gate Compliance" below.
- `rtk` (the project's token-optimized CLI proxy) intercepted and summarized some `uv run pytest`/`make test`/`make validate` invocations misleadingly during this session, consistent with the note already on file from 11-01's own SUMMARY. Worked around identically: every verification command in this plan was run via `rtk proxy <cmd>`, which reproduced full, unfiltered output. Environment-tooling quirk, not a project or plan issue.

## TDD Gate Compliance

Tasks 1 and 2 (both `tdd="true"`) each show a `test(...)` commit (RED) immediately followed by a `feat(...)` commit (GREEN), confirmed failing/passing respectively before being committed. Task 3 (`tdd="true"`) is a pure end-to-end integration proof of behavior Tasks 1+2 already built — it produced one `test(...)` commit that passed on its first run, with no corresponding `feat(...)` commit, because no production code needed to change. This is consistent with the plan's own framing of Task 3 as verifying composition, not adding new behavior.

## User Setup Required

None - no external service configuration required. Every test in this plan uses an injected fake `run`; no real `launchctl` is ever invoked.

## Next Phase Readiness
- `installer/policy.py::daemon_policy` is ready for 11-03's detail-panel UI (the time-of-day picker calling `policy.set_schedule`, the persistent schedule display calling `policy.read_schedule()`) and 11-04's composition root (wiring `daemon_policy(...)` into `setup.py`'s macOS-only policy list, plus the on-by-default bootstrap using `daemon.decided`/`record_decided`).
- `Policy.is_active` (a live re-check closure, distinct from the frozen `active` snapshot) is ready for 11-04's full-uninstall wiring, per 11-REVIEWS.md cycle 2 finding #13.
- `daemon_policy.remove()`'s new `remove_wrapper` call means 11-04's full-uninstall teardown (which reuses this same `.remove()` closure per this codebase's "toggle off == full uninstall" invariant) removes the wrapper too, with no separate 11-04-side change required (11-REVIEWS.md cycle 2 finding #16, resolved here).
- No blockers identified. `setup.py` remains untouched by this plan, exactly as scoped.

## Self-Check: PASSED

- FOUND: `installer/policy.py`
- FOUND: `installer/wizard_app.py`
- FOUND: `tests/test_policy_daemon.py`
- FOUND: `tests/test_wizard_app.py`
- FOUND: `tests/test_policies_e2e.py`
- FOUND: `.planning/phases/11-background-maintenance-daemon/11-02-SUMMARY.md`
- FOUND commit `2bd3093` (test(11-02): add failing test for hard_requires=False soft-dependency gate)
- FOUND commit `acd96de` (feat(11-02): add Policy.hard_requires gate fix and accurate soft-dependency copy)
- FOUND commit `9e8b813` (test(11-02): add failing tests for daemon_policy transactional apply/remove/reschedule)
- FOUND commit `83379e3` (feat(11-02): implement daemon_policy with transactional apply/remove/reschedule)
- FOUND commit `4456e9f` (test(11-02): prove soft dependency gating and accurate copy at the UI layer)
- FOUND commit `432e05b` (fix(11-02): reword daemon_policy docstring so hard_requires=False is unique)
- FOUND commit `8d69b93` (test(11-02): close a coverage gap for the first-ever-apply log rollback branch)
- VERIFIED: `uv run pytest tests/test_policy_daemon.py tests/test_wizard_app.py tests/test_policies_e2e.py -q` passes in full
- VERIFIED: `uv run pytest -q` (full suite) exits 0 with zero regression to `ban_policy`/`tweak_policy`/`omz_plugins_policy` behavior
- VERIFIED: `make validate && make test` passes on the committed tree (1427 passed, 1 skipped, 99.42% coverage)
- VERIFIED: every `<verification>` grep/python3 check from 11-02-PLAN.md passes exactly as specified

---
*Phase: 11-background-maintenance-daemon*
*Completed: 2026-09-07*
