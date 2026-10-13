---
phase: 04-package-manager-redirect-policy
plan: 01
subsystem: guards
tags: [npx, pnpm-dlx, REDIRECTED, PATH-shims, aliases]

requires:
  - phase: 03-install-uninstall-tweak-lifecycle-hardening
    provides: ban_policy apply/remove, run_guard, guard_status dict[str, bool]
provides:
  - installer/guards.py REDIRECTED parallel to BANNED
  - npx exec-through shim to pnpm dlx with real exit code
  - guarded_names / guard_label / guard_redirect_warning
  - two-step install_shims then install_redirect_shims at both apply sites
affects:
  - 04-03 argv-conditional npm/pnpm wrappers (reuses REDIRECTED + real_binary)
  - 04-04 doctor UI label text (consumes guard_label)

actuals:
  tokens: 7200
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - parallel REDIRECTED dict beside BANNED, never a generalized ban
    - bake real_binary absolute path into exec-through shim at write time
    - hard-block first, redirect second so overlap names supersede safely

key-files:
  created: []
  modified:
    - installer/guards.py
    - installer/policy.py
    - installer/app.py
    - tests/test_guards.py
    - tests/test_policy.py
    - tests/test_app.py
    - tests/test_policies_e2e.py

key-decisions:
  - "D-01: REDIRECTED sits parallel to BANNED; shim_script/EXIT_CODE/SHIM_SENTINEL untouched"
  - "D-02: guard_status stays dict[str, bool]; redirect vs block lives in guard_label"
  - "D-03: npx execs pnpm dlx \"$@\", not pnpx"
  - "D-04: pip/pip3 stay hard-blocked; uv-pip uninstall/compile gap recorded in the module docstring"

patterns-established:
  - "REDIRECTED + Redirect(target, args, label) for unconditional exec-through shims"
  - "guarded_names() is the one ownership set for remove/status/path-warning"
  - "install_shims then install_redirect_shims; unresolvable target keeps the hard block"

requirements-completed:
  - REQ-npx-ban
  - REQ-npm-npx-redirect-policy

coverage:
  - id: D1
    description: "Running npx through the managed shim dir execs pnpm dlx and the caller sees pnpm's real exit code, stdout and stderr"
    requirement: REQ-npx-ban
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_npx_redirect_shim_execs_into_pnpm_dlx_with_real_exit_code
        status: pass
    human_judgment: false
  - id: D2
    description: "No resolvable pnpm yields an npx hard-block (message + exit 127) instead of exec into a missing command"
    requirement: REQ-npx-ban
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_install_redirect_shims_falls_back_to_hard_block_when_pnpm_missing
        status: pass
      - kind: unit
        ref: tests/test_policy.py#test_apply_writes_npx_hard_block_when_pnpm_missing
        status: pass
    human_judgment: false
  - id: D3
    description: "guard_status returns dict[str, bool] covering npx alongside npm/pip/pip3"
    requirement: REQ-npm-npx-redirect-policy
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_guarded_names_is_stable_and_deduplicated
        status: pass
      - kind: unit
        ref: tests/test_guards.py#test_guard_status_reports_installed_ours
        status: pass
    human_judgment: false
  - id: D4
    description: "Removing the policy removes the npx redirect shim exactly like a ban shim"
    requirement: REQ-npx-ban
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_remove_shims_removes_npx_after_ban_and_redirect_install
        status: pass
      - kind: unit
        ref: tests/test_policy.py#test_remove_clears_both_layers
        status: pass
      - kind: e2e
        ref: tests/test_policies_e2e.py#test_policies_e2e_toggle_round_trip_against_sandbox
        status: pass
    human_judgment: false
  - id: D5
    description: "pip and pip3 remain hard-blocked, with the uv-pip gap recorded in the module docstring"
    requirement: REQ-npm-npx-redirect-policy
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_guard_label_distinguishes_redirect_from_block
        status: pass
      - kind: other
        ref: "grep -c uninstall installer/guards.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "ban_policy.apply and run_guard produce the same shim dir; npx is redirect when pnpm resolves"
    requirement: REQ-npm-npx-redirect-policy
    verification:
      - kind: unit
        ref: tests/test_app.py#test_run_guard_shim_dir_matches_ban_policy_apply
        status: pass
      - kind: unit
        ref: tests/test_policy.py#test_apply_writes_npx_redirect_when_pnpm_resolves
        status: pass
    human_judgment: false

duration: remainder-of-plan
completed: 2026-09-05
status: complete
---

# Phase 4 Plan 01: npx exec-through redirect

**REDIRECTED shims sit beside BANNED; `npx` execs `pnpm dlx "$@"` with the real exit code, and pip/pip3 stay hard-blocked.**

## Accomplishments

- Parallel `REDIRECTED` mechanism (`Redirect`, `REDIRECT_SENTINEL`, `redirect_shim_script`, `real_binary`, `install_redirect_shims`) without generalizing `BANNED`.
- `npx` fail-safe entry in `BANNED` (`"pnpm (pnpm dlx <pkg>)"`); one `guarded_names()` set drives remove/status/path-warning.
- Both apply entry points (`ban_policy._apply`, `app.run_guard`) write hard-block bodies first, then redirect bodies.

## Final REDIRECTED entry

```python
REDIRECTED = {
    "npx": Redirect(target="pnpm", args=("dlx",), label="redirected to pnpm dlx"),
}
```

## Fallback when pnpm is absent

`install_redirect_shims` resolves the target with `real_binary`. If that returns None, it writes `shim_script("npx")` (hard-block, exit 127, `SHIM_SENTINEL` only) and reports `"blocked (pnpm not found)"`. It never emits an exec-through body that would call a missing command. `guard_redirect_warning` names `npx` and `pnpm` and tells the user to install the target and re-apply.

## uv-pip gap wording (D-04)

Recorded in `installer/guards.py`'s module docstring:

> pip and pip3 stay hard-blocked because `uv pip` is not an argv-compatible drop-in for two of the six subcommands this shim would intercept — `uninstall` cascades to transitive dependencies pip leaves in place, and `compile` requires an explicit output file and applies a different extras-stripping default — so a blanket redirect would change behaviour silently. See https://docs.astral.sh/uv/pip/compatibility/ and `.planning/phases/04-package-manager-redirect-policy/04-RESEARCH.md` Pitfall 1.

## Task Commits

1. **Task 1: End-to-end npx execs into pnpm dlx** - `10387225501431f080b52eb0f30834781abae965` (feat)
2. **Task 2 RED: pin guarded_names/guard_label/redirect-alias contract** - `275b32878ba06b53f46ff29647ae37bd18f8f7ba` (test)
3. **Task 2 GREEN: implement guarded_names/guard_label/redirect alias** - `b99843c638a46e0e579482201ae588b34f07b953` (feat)
4. **Task 3: wire redirect into ban_policy and run_guard** - `f9a39f809ba5d5d2934b7376ce424580dc07d174` (feat)

## Files Created/Modified

- `installer/guards.py` — REDIRECTED mechanism, guarded_names, labels, warnings, D-04 docstring
- `installer/policy.py` — two-step apply, 4-active detail, description
- `installer/app.py` — two-step `run_guard`, composed `guard_state` warning
- `tests/test_guards.py` — mechanism and ownership tests
- `tests/test_policy.py` / `tests/test_app.py` / `tests/test_policies_e2e.py` — both apply paths

## Decisions Made

Followed the plan: D-01 through D-04. `BANNED["npm"]` hint left unchanged (owned by 04-03). Interactive alias names the target by PATH name; the shim bakes `real_binary`'s absolute path.

## Deviations from Plan

None — plan executed as written. Task 1 and the Task 2 RED test commit were already on the branch; this run implemented Task 2 GREEN and Task 3 only.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 04-03 can add argv-conditional npm/pnpm wrappers on a proven exec-through + `real_binary` seam.
- 04-04 can consume `guard_label` / `guard_redirect_warning` for doctor copy.
- `REQ-npm-npx-redirect-policy` pip/pip3 half is closed as hard-block (research gap), not as a redirect.

## Self-Check: PASSED

`make validate` — ruff, ruff format, pyright 0 errors 0 warnings, bandit, vulture, shellcheck. `make test` — full suite green, coverage floor 90% held (`installer/app.py` and `installer/policy.py` at 100%).

---
*Phase: 04-package-manager-redirect-policy*
*Completed: 2026-09-05*
