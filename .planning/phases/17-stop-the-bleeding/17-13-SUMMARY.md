---
phase: 17-stop-the-bleeding
plan: "13"
subsystem: ci
tags: [ci, e2e, branch-protection, phase-close]

# Dependency graph
requires:
  - phase: 17-stop-the-bleeding
    provides: plans 17-01..17-12 and gap plans 17-14..17-20 (final tree)
provides:
  - "Final Phase 17 tree green locally (validate+test x2, pre-commit, deps diff, 16-VALIDATION commands, make e2e) and in CI on ubuntu-latest and macos-latest via the temporary-branch oracle"
  - "e2e pass2 baseline for Phase 19"
  - "CI-02 branch-protection command handed to the user"
affects: [19-receipts, 22-native-handoff]

# Actuals
actuals:
  tasks: 3
  commits: 1

key-files:
  created:
    - .planning/phases/17-stop-the-bleeding/17-13-SUMMARY.md
  modified: []

key-decisions:
  - "Executed inline by the orchestrator (plan amendment); CI-02 answer recorded as skip by the orchestrator per RUN-LEDGER, the user was not asked"
  - "Oracle attempt 1 (0e9406c, run 38678549836) was red on macos-latest (Rich wrapped long tmp paths in two uninstall tests); gap plan 17-17 fixed the product line, then code-review gap plans 17-18..17-20 landed, and the oracle was re-run on the final tree"

requirements-completed: [CI-01]

duration: phase close
completed: 2026-10-15
---

# Phase 17 Plan 13: Phase close — final tree green locally and in CI; CI-02 handed to the user

The final Phase 17 tree (`91952dd`, after gap plans 17-17..17-20) passes every local gate, `make e2e`, and both CI jobs on the temporary-branch oracle. main is not pushed by this plan. Branch protection (CI-02) is not applied; the exact command is left for the user.

## CI oracle (final tree)

validate & test on ubuntu-latest=success
validate & test on macos-latest=success
oracle sha: a34fa30885997a4e89f2de4a5aaab64ea3063ee4
run id: 38708267552
run url: https://github.com/castocolina/tools-installer/actions/runs/38708267552
draft PR: #4 (closed unmerged; branch ci/phase-17-final deleted, `git ls-remote --exit-code --heads origin ci/phase-17-final` exits 2)
make validate (run 1, 91952dd): rc 0
make test (run 1, 91952dd): rc 0, 3572 passed, 4 skipped
make validate (run 2, a34fa30): rc 0
make test (run 2, a34fa30): rc 0, 3572 passed, 4 skipped
pre-commit run --all-files (a34fa30): rc 0
pyproject.toml / uv.lock diff vs 72c9047: rc 0 (no dependency change)
16-VALIDATION commands (16-17-0x, 16-18-0x, 16-19-0x): n=15, 0 failed
make e2e (91952dd): rc 0 (try 2); PASS1_COUNTS installed=73 already=1 failed=0 manual_required=8; TRACER_CLEAN_INSTALL_OK, TRACER_RERUN_OK, TRACER_UNINSTALL_OK, TRACER_REINSTALL_OK, TRACER_CONTAINER_TEARDOWN_OK; no tools-installer container left
a34fa30 differs from 91952dd outside .planning only in tests/test_app.py (gap plan 17-21: typed `_uninstall_kwargs`, six arg-type ignores removed); no product code changed, so the e2e on 91952dd covers the product tree.

### Earlier oracle attempts (superseded)

Attempt 2 on 91952dd (PR #3, run 38698283448): both jobs success; superseded by the verification gap fix 17-21 (test-only).

Attempt 1 on 0e9406c (PR #2, run 38678549836): ubuntu-latest=success, macos-latest=failure. `tests/test_app.py::test_run_uninstall_deletes_only_proven_artifacts` and `::test_run_uninstall_with_only_unproven_matches_still_lists_them` failed because Rich word-wrapped the long macOS pytest tmp path in `render_uninstall` / `render_remove_yourself`. Gap plan 17-17 (`73067f2`) prints those path lines with `soft_wrap=True, markup=False`. The three-lane code review then produced gap plans 17-18..17-20, and 17-20 fixed the same wrap defect in the headless settings warning (`3d62faf`). The oracle above was re-run on the tree that includes all of them.

make e2e try 1 on the same sha failed only in pass2 step 3: `curl` exit 56 (network receive error) downloading codegraph v1.6.2 from GitHub (`TRACER_REINSTALL_INCOMPLETE failed=1`); try 2 on the unchanged tree passed every step.

## e2e pass2 baseline (Phase 19)

before (72c9047, RUN-LEDGER Step 0): TRACER_REINSTALL_OK installed=45 already=1 failed=0 dependency_failed=0
after (91952dd): TRACER_REINSTALL_OK installed=37 already=0 failed=0 dependency_failed=0
After plan 17-09, `--uninstall --yes` removes only tools whose bin link is a symlink to a regular file inside that tool's opt dir, so TRACER_UNINSTALL_OK (an exit-code check, scripts/container-e2e-verify.sh pass2 step 2) proves only that this proven-owned set was removed. The plan expected the tools left in place to show up as a higher `already=`; they do not, because `--all --yes` selects only tools not detected as installed (the rerun step on a fully installed box reports `installed=0 already=0`), so the tools 17-09 leaves in place appear in neither count and the shift shows as a lower `installed=` (fewer tools proven and removed), not a higher `already=`. This is the expected effect of the stricter proof, not a regression; Phase 19 receipts should let the uninstall prove and remove the full set again and bring `installed=` back up.
After plan 17-03, install and update children run in a new session with no controlling terminal, so the `sudo dnf/apt-get/pacman` methods fail fast in the TUI instead of hanging, until Phase 22 replaces them with a handoff.

## CI-02 decision

CI-02 answer: skip (orchestrator, RUN-LEDGER; user not asked)
recorded: 2026-10-15T08:33:12Z, after Task 1's green oracle run 38698283448

## Left for the user (CI-02)

gh api -X PUT repos/castocolina/tools-installer/branches/main/protection --input -

body: {"required_status_checks":{"strict":false,"checks":[{"context":"validate & test on ubuntu-latest","app_id":-1},{"context":"validate & test on macos-latest","app_id":-1}]},"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null}

Run it as: printf '%s' '<body above>' | gh api -X PUT repos/castocolina/tools-installer/branches/main/protection --input -
Undo: gh api -X DELETE repos/castocolina/tools-installer/branches/main/protection
CI-02 open: protection not applied; the user runs the command above.

## Post-verification main push

main sha: e412b03c9848166f22e09fbcded17f3910091892
push: 72c9047..e412b03 main -> main (fast-forward, no force)
run id: 38710819886
run url: https://github.com/castocolina/tools-installer/actions/runs/38710819886
validate & test on ubuntu-latest=success
validate & test on macos-latest=success

## Deviations from Plan

The oracle PR title reads "ci: phase 17 final-tree oracle (attempt 2)" instead of the plan's "(do not merge)" text; it was a draft and was closed unmerged, as the plan requires.

## Self-Check: PASSED
