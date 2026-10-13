---
phase: 04-package-manager-redirect-policy
plan: 03
subsystem: guards
tags: [volta, npm-global, pnpm-wrapper, GLOBAL_REDIRECTED, real_pnpm, argv-conditional]

requires:
  - phase: 04-package-manager-redirect-policy
    provides: REDIRECTED exec-through + real_binary (04-01); volta catalog entry (04-02)
provides:
  - installer/guards.py GLOBAL_REDIRECTED / GlobalRedirect / GLOBAL_SUBCOMMANDS
  - argv-conditional npm/pnpm wrapper (volta install on global install/add/i)
  - real_pnpm + _node absolute-path invocation
  - volta-gated install_global_redirect_shims
affects:
  - 04-04 doctor UI copy (consumes guard_label and the volta tradeoff)
  - 04-05 pnpm-global reinstall (reuses real_pnpm)

actuals:
  tokens: 8500
  tasks: 4
  commits: 4

tech-stack:
  added: []
  patterns:
    - argv-conditional POSIX-sh wrapper parallel to REDIRECTED, never a widening of it
    - bake real_binary absolute path into pass-through; internal pnpm calls use the same resolver
    - three-writer apply order: hard block, unconditional redirect, argv-conditional redirect

key-files:
  created: []
  modified:
    - installer/guards.py
    - installer/executors.py
    - installer/policy.py
    - installer/app.py
    - tests/test_guards.py
    - tests/test_executors.py
    - tests/test_node_install_e2e.py
    - tests/test_policy.py
    - tests/test_policies_e2e.py
    - tests/test_app.py

key-decisions:
  - "D-06/R-01: npm/pnpm global install/add/i exec volta install <pkg>; other npm stays hard-blocked; other pnpm execs real pnpm unmodified"
  - "D-07: volta install still runs ungated npm postinstall scripts — shipped as the documented security-for-stability tradeoff, not a clean win"
  - "R-02: writer gates on volta resolving; missing volta leaves npm's hard block and does not shim pnpm"
  - "T-04-20: _node invokes real_pnpm() by absolute path and raises ExecutorError rather than falling back to a bare name"

patterns-established:
  - "GLOBAL_REDIRECTED sits parallel to REDIRECTED/BANNED; apply order is install_shims then install_redirect_shims then install_global_redirect_shims"
  - "real_pnpm is the single resolver both the shim writer and _node use"
  - "Names in GLOBAL_REDIRECTED skip ban_alias_block — the PATH shim is the only layer that can reproduce the argv branch"

requirements-completed:
  - REQ-npm-global-volta-redirect
  - REQ-npm-npx-redirect-policy

coverage:
  - id: D1
    description: "npm install -g / npm add -g / pnpm add -g exec volta install <pkg>, including packed short flags like -gD"
    requirement: REQ-npm-global-volta-redirect
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_npm_global_install_redirects_to_volta
        status: pass
      - kind: unit
        ref: tests/test_guards.py#test_pnpm_add_g_redirects_to_volta
        status: pass
      - kind: unit
        ref: tests/test_guards.py#test_pnpm_add_gd_redirects_to_volta
        status: pass
    human_judgment: false
  - id: D2
    description: "Non-global npm still prints the ban message and exits 127; pnpm non-global argv reaches real pnpm unmodified"
    requirement: REQ-npm-npx-redirect-policy
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_npm_install_without_global_is_banned
        status: pass
      - kind: unit
        ref: tests/test_guards.py#test_pnpm_add_without_global_passes_through_unmodified
        status: pass
      - kind: unit
        ref: tests/test_guards.py#test_pnpm_list_g_passes_through_unmodified
        status: pass
    human_judgment: false
  - id: D3
    description: "kind=node catalog installs invoke real pnpm by absolute path even when this installer's pnpm wrapper is first on PATH"
    requirement: REQ-npm-global-volta-redirect
    verification:
      - kind: unit
        ref: tests/test_executors.py#test_node_skips_wrapper_first_on_path
        status: pass
      - kind: unit
        ref: tests/test_executors.py#test_node_runs_pnpm_add_global_never_bare_npm
        status: pass
      - kind: e2e
        ref: tests/test_node_install_e2e.py#test_installing_mmdc_runs_pnpm_add_global_no_bare_npm
        status: pass
    human_judgment: false
  - id: D4
    description: "install_global_redirect_shims writes wrappers only when volta resolves; otherwise npm stays banned and pnpm is not shimmed"
    requirement: REQ-npm-global-volta-redirect
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_install_global_redirect_shims_volta_missing_leaves_ban
        status: pass
      - kind: unit
        ref: tests/test_policy.py#test_apply_writes_both_layers_and_returns_result
        status: pass
      - kind: unit
        ref: tests/test_policy.py#test_apply_with_volta_writes_five_shims
        status: pass
    human_judgment: false

duration: 31min
completed: 2026-09-05
status: complete
---

# Phase 4 Plan 03: argv-conditional global redirect Summary

**`npm install -g` / `pnpm add -g` exec `volta install <pkg>` via an argv-conditional PATH shim; the installer's own `kind="node"` call reaches real pnpm by absolute path so the wrapper cannot intercept it.**

## Performance

- **Duration:** 31 min
- **Started:** 2026-09-05T13:57:03Z
- **Completed:** 2026-09-05T14:27:35Z
- **Tasks:** 4
- **Files modified:** 10

## Accomplishments

- `real_pnpm` wraps `real_binary("pnpm", ...)` with defaults from `bin_dir(None)` and live `PATH`. `_node` passes that absolute path as argv[0] and raises `ExecutorError` when it is None.
- `GLOBAL_REDIRECTED` / `GlobalRedirect` / `GLOBAL_SUBCOMMANDS` sit parallel to `REDIRECTED`. Combined short flags (`-gD`) count as global; `--filter=-g` does not.
- `install_global_redirect_shims` gates on volta. Both `ban_policy._apply` and `app.run_guard` call it third. `guarded_names()` is `npm, pip, pip3, npx, pnpm`.
- `BANNED["npm"]` hint is now `pnpm (local) or volta install <pkg> (global)`. npm/pnpm have no interactive alias.

## Exact shim body committed

```
#!/bin/sh
# tools-installer-redirect-shim
subcmd=''
is_global=0
for arg in "$@"; do
  case "$arg" in
    -g|--global) is_global=1 ;;
    -[!-]*) case "$arg" in *g*) is_global=1 ;; esac ;;
    -*) ;;
    *) if [ -z "$subcmd" ]; then subcmd="$arg"; fi ;;
  esac
done
if [ "$is_global" -eq 1 ]; then
  case "$subcmd" in
    install|add|i)
      argc=$#
      seen=0
      while [ "$argc" -gt 0 ]; do
        arg="$1"
        shift
        argc=$((argc - 1))
        case "$arg" in
          -*) ;;
          *) if [ "$seen" -eq 0 ]; then seen=1; else set -- "$@" "$arg"; fi ;;
        esac
      done
      if [ "$#" -gt 0 ]; then
        exec {quoted volta} install "$@"
      fi
      echo "tools-installer: a global install needs a package name." >&2
      exit 127
      ;;
  esac
fi
{fallback}
```

`{fallback}` is `exec {quoted real pnpm} "$@"` for pnpm, or the two hard-block lines from `BANNED["npm"]` / `EXIT_CODE` for npm (byte-identical to `shim_script("npm")`'s last two lines).

Accepted parse gap (T-04-22): a value-taking option before the subcommand mis-reads it. npm fails to the hard block; pnpm fails to an un-redirected pass-through.

## `install_global_redirect_shims` result-string vocabulary

| Result | Meaning |
|--------|---------|
| `created` / `refreshed` | wrote the argv-conditional body, mode 0o755, `REDIRECT_SENTINEL` |
| `skipped (real binary here)` | foreign file at that name, left untouched |
| `blocked (volta not found)` | npm; volta missing; existing hard block left in place |
| `absent (volta not found)` | pnpm; volta missing; no our shim was there |
| `removed (volta not found)` | pnpm; volta gone; our previous wrapper deleted |
| `skipped (real pnpm not found)` | volta resolved, no real pnpm outside shim_dir; nothing written |
| `removed (real pnpm not found)` | same, but our previous wrapper was deleted |

## D-07 shipped position

Volta install still runs `npm install --global` with install scripts ungated (recorded on the 04-02 catalog entry). This plan ships the redirect as that documented security-for-stability tradeoff, not as an assumed-safe win. The wrapper intercepts only what a user types; `_node` still reaches real pnpm, so pnpm's gated postinstall remains for `kind="node"` catalog installs (`mmdc`).

## How `_node` resolves pnpm

`installer/executors.py::_node` calls `real_pnpm()` with no overrides. That excludes `installer.locations.bin_dir(None)` (`~/.local/bin`) from PATH and refuses sentinel-carrying results. argv[0] is the absolute path. None raises `ExecutorError` naming pnpm and the managed shim dir — never a bare-name fallback that would re-enter the wrapper.

## Task Commits

1. **Task 1: The installer's own pnpm calls resolve the real binary first** - `562c282` (feat)
2. **Task 2: The argv-conditional shim body** - `9c5b625` (feat)
3. **Task 3: Volta-gated writer, and pnpm joins the guarded name set** - `5ca8985` (feat)
4. **Task 4: Three writers, one apply order, both entry points** - `e51e8db` (feat)

## Files Created/Modified

- `installer/guards.py` - `real_pnpm`, `GLOBAL_REDIRECTED`, shim generator, volta-gated writer, guarded name/label/alias/warning updates
- `installer/executors.py` - `_node` uses `real_pnpm()` absolute path
- `installer/policy.py` - third writer in `ban_policy._apply`; degraded outcomes named in Shims detail
- `installer/app.py` - same third writer in `run_guard`
- `tests/test_guards.py` - real-`sh` matrix, writer/status/label/alias tests
- `tests/test_executors.py` / `tests/test_node_install_e2e.py` - absolute-path `_node` + wrapper-first regression
- `tests/test_policy.py` / `tests/test_policies_e2e.py` / `tests/test_app.py` - two-sandbox apply (volta present / absent)

## Decisions Made

Followed the plan: D-05, D-06, D-07, D-01, R-01, R-02. Combined short-flag arm shipped. Leading value-taking-option gap accepted and pinned per binary.

## Deviations from Plan

**1. [Rule 2 - Missing Critical] Volta-absent test assertions moved into Task 3**
- **Found during:** Task 3 (`guarded_names()` gained `pnpm`)
- **Issue:** `make test` failed on `assert all(guard_status(...).values())` in a volta-less sandbox — the quality gate forbids committing that tree
- **Fix:** Task 3 replaced those two blanket assertions with the volta-absent per-name shape (4 True, pnpm False). Task 4 then installed the specified two-sandbox replacement
- **Files modified:** `tests/test_policy.py`, `tests/test_policies_e2e.py`
- **Verification:** `make validate && make test` passed on the Task 3 commit and again on Task 4
- **Committed in:** `5ca8985` (Task 3) and `e51e8db` (Task 4)

---

**Total deviations:** 1 auto-fixed (quality-gate ordering). **Impact:** none on shipped behaviour; Task 4 still owns the two-sandbox contract.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-04: doctor label text distinguishing redirected vs blocked, plus the volta tradeoff in UI copy. `guard_label("npm")` / `guard_label("pnpm")` already return the GLOBAL_REDIRECTED labels.

## Self-Check: PASSED

---
*Phase: 04-package-manager-redirect-policy*
*Completed: 2026-09-05*
