---
phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer
plan: 04
subsystem: doctor
tags: [pnpm, globals, co_install, puppeteer, mmdc, doctor, brownfield]

requires:
  - phase: 05-01
    provides: probe_version, PNPM_CO_INSTALL_MIN, PNPM_ALLOW_BUILD_MIN, SPLIT/GROUPED JSON
  - phase: 05-03
    provides: mmdc+puppeteer co_install group, allow_build, versions pin, pending detection line
provides:
  - registry-derived NodeInstallPolicy
  - group-aware pin-aware allow-build-aware pnpm-globals replay
  - TUI Doctor split-group detection via path-hash membership
affects:
  - Phase 5 verification (REQ-puppeteer-catalog-entries now complete)
  - brownfield users opening the TUI Doctor

actuals:
  tokens: 18000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - NodeInstallPolicy is a frozen declaration intersected with pnpm's live set
    - preview and reinstall share one policy object and one argv builder
    - split-group membership is the per-package path hash, not multiple project objects

key-files:
  created: []
  modified:
    - installer/pnpm_globals.py
    - installer/guidance.py
    - installer/registry.toml
    - setup.py
    - tests/test_pnpm_globals.py
    - tests/test_guidance.py
    - tests/test_setup.py

key-decisions:
  - "Branch A: pnpm list -g --json emits ONE project object; group membership is the path hash"
  - "Console make doctor is deliberately unwired; only the TUI passes the policy"
  - "reinstall_node_globals returns specs, never --allow-build flags"

patterns-established:
  - "Comma versus space in pnpm add -g is isolation, not formatting"
  - "Doctor split detection reuses audit_node_globals plus node_globals_guidance"

requirements-completed:
  - REQ-puppeteer-catalog-entries

coverage:
  - id: D1
    description: "Registry-derived NodeInstallPolicy and group/pin/allowance-aware reinstall_argv"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_pnpm_globals.py#test_reinstall_argv_groups_pins_and_allows_the_declared_pair
        status: pass
      - kind: unit
        ref: tests/test_pnpm_globals.py#test_reinstall_node_globals_returns_specs_never_flags
        status: pass
    human_judgment: false
  - id: D2
    description: "Doctor preview and reinstall share one policy; brownfield replay regroups mmdc+puppeteer"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_setup.py#test_doctor_preview_carries_the_grouped_pinned_allowed_replay
        status: pass
      - kind: unit
        ref: tests/test_pnpm_globals.py#test_replay_regroups_a_brownfield_split_mmdc_and_puppeteer
        status: pass
    human_judgment: false
  - id: D3
    description: "TUI Doctor detects a split install group from real SPLIT/GROUPED JSON and names both packages"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_pnpm_globals.py#test_parse_global_groups_split_state_holds_mmdc_and_puppeteer_apart
        status: pass
      - kind: unit
        ref: tests/test_guidance.py#test_node_globals_guidance_warns_on_a_split_install_group
        status: pass
    human_judgment: false

duration: 31 min
completed: 2026-09-06
status: complete
---

PLAN_BASE
364acb51930548ae5e89a9f82fbdc7a213282a3f

# Phase 05 Plan 04: Group-aware pnpm-globals replay and split-group Doctor Summary

**The Doctor's pnpm-globals reinstall now replays `@mermaid-js/mermaid-cli,puppeteer@^25` with `--allow-build=puppeteer`, and the TUI Doctor names a brownfield split and points at `r`.**

## Performance

- **Duration:** 31 min
- **Started:** 2026-09-05T23:52:58Z
- **Completed:** 2026-09-06T00:23:30Z
- **Tasks:** 3
- **Files modified:** 7

## PLAN_BASE

364acb51930548ae5e89a9f82fbdc7a213282a3f

## Accomplishments

- `NodeInstallPolicy` derived from the catalog carries the one mmdc+puppeteer group, a de-duplicated `puppeteer` allowance, and the `^25` pin.
- `reinstall_argv` with that policy emits `['/x/pnpm', 'add', '-g', '--allow-build=puppeteer', '@mermaid-js/mermaid-cli,puppeteer@^25']`; without a policy the argv is byte-identical to today.
- A partial group (only `puppeteer` present) replays only what pnpm already manages, still pinned, and never adds `@mermaid-js/mermaid-cli`.
- `reinstall_node_globals` returns the specs it invoked, never `--allow-build=` flags; an empty policy probes nothing; a contributing policy refuses pnpm below the applicable floor.
- `setup.py::_build_app` constructs one policy and passes it to preview, reinstall, and (Task 3) the TUI audit.
- The TUI Doctor detects a split install group from live path-hash membership and reports it as WARN with `Run \`make setup\`` so `_tui_guidance` rewrites it to `Press r to reinstall the pnpm-managed global set`.

## Task Commits

1. **Task 1: A registry-derived install policy and a group-aware, pin-aware `reinstall_argv`** - `4cb5578` (feat)
2. **Task 2: Wire the registry policy into the Doctor's preview and reinstall, and pin the brownfield remedy** - `ec73a84` (feat)
3. **Task 3: Detect a split install group in the Doctor audit and tell the user about it** - `4a09900` (feat)

## Exact replay argv (shipped registry policy)

```
['/x/pnpm', 'add', '-g', '--allow-build=puppeteer', '@mermaid-js/mermaid-cli,puppeteer@^25']
```

Partial-group behaviour: members not in the live `packages` list are never added, so the replay cannot install a tool the user never chose (T-05-15).

Return contract: `reinstall_node_globals` returns `tuple(specs)` from `_reinstall_parts`. The old `tuple(argv[3:])` slice became wrong the moment `--allow-build=` flags were prepended.

Pnpm floor: probed only when this package set produced a comma-joined group or at least one flag. Grouped form requires `PNPM_CO_INSTALL_MIN` (11.0.0); allow-build-only requires `PNPM_ALLOW_BUILD_MIN` (10.4.0). The preview never probes — the floor is a precondition of running, not a different command.

## Corrected docstring (verbatim LIMITATIONS)

```
LIMITATIONS of a name-only snapshot:

- `parse_global_packages` flattens pnpm's JSON to bare package NAMES, so the
  replay knows neither the version a package was at nor which live group it
  belonged to. A package the registry does not know is therefore reinstalled
  at whatever the registry's dist-tag resolves to now, ungrouped — its
  previous version and any hand-created group are not reconstructible from
  the snapshot.
- Consequently a hand-made group of packages this catalog does not declare is
  replayed as separate isolated installs, which can break a peer relationship
  the user set up themselves. This is a known limitation of replaying a
  name-only snapshot, not an oversight; reconstructing it would require
  reading pnpm's per-group project structure, which is out of this phase's
  scope.
- pnpm removes a whole comma group when either member is removed with
  `pnpm remove -g`, so a group this replay creates is also a coupling the
  user inherits.
```

The preceding paragraph restates that under pnpm v11 each package or comma-joined group is its own hash-keyed install and supersedes nothing else.

## PnpmUnavailable on the Doctor path

`PnpmUnavailable` subclasses `OSError`. `installer/wizard_app.py` `DoctorScreen._reinstall_globals_worker` calls `ui_common.run_live`, which surfaces OSError under architecture rule 3 with no screen-level `except`. The unmet pnpm floor uses the same path as a missing pnpm. `installer/wizard_app.py` was not edited.

## Task 2 wiring seam

`tests/test_setup.py` replaces `UnifiedApp` and calls the captured `globals_preview` closure with a `NodeGlobalsReport` whose `managed` set is the brownfield pair. That is the closest seam `_build_app` exposes without launching Textual. The resolver is stubbed to `/x/pnpm` so no real pnpm runs.

Brownfield regression: `test_replay_regroups_a_brownfield_split_mmdc_and_puppeteer`. Plan 05-01 Container C measured the split (hashes `14f2-...` vs `151d-...`) and the grouped remedy (shared `15c0-...`, `TRACER_BROWNFIELD_OK`).

## Task 3 branch

**Branch A.** `SPLIT_STATE_JSON` (Container C, before remedy) reports **one** project object whose `dependencies` hold `@mermaid-js/mermaid-cli` (path hash `14f2-18d28dc072dbf202-0`), `@pnpm/exe` (`14d6-...`), and `puppeteer` (`151d-18d28dce58a8e9af-0`). `GROUPED_STATE_JSON` (after remedy) is also **one** project object; mermaid-cli and puppeteer share hash `15c0-18d28df958d4debd-0`. Membership is therefore observable via the per-package `path` hash, not via multiple project objects. `parse_global_groups` groups by the directory above `node_modules`.

## Split-group guidance

Title: `pnpm install group is split`

Meaning: `pnpm is holding @mermaid-js/mermaid-cli and puppeteer in separate global installs, so the dependent cannot load its peer at runtime — the tool fails when it is run rather than when it is installed.`

Next step: `Run \`make setup\` and open the Doctor view to reinstall the globals pnpm still tracks.`

Surfaces: TUI Doctor (wired: `setup.py` passes `policy=` into `audit_node_globals`). Console `make doctor` is deliberately unwired — `installer/app.py::run_doctor` still calls `audit_node_globals` without a policy. `installer/render.py` would print the item if it ever arrived, but this plan never emits it on that path. `installer/wizard_app.py` and `installer/render.py` were not modified; `_tui_guidance` already rewrites the prefix.

## Registry hand-off

Replaced `pending plan 05-04` with:

`the TUI Doctor reports a split as a warning naming both packages and pointing at the \`r\` reinstall action.`

## Untouched by this plan's commits

`git diff --name-only 364acb51930548ae5e89a9f82fbdc7a213282a3f..HEAD -- installer/wizard_app.py installer/render.py installer/app.py` is empty.

## Files Created/Modified

- `installer/pnpm_globals.py` - NodeInstallPolicy, grouped replay, path-hash groups, split detection
- `installer/guidance.py` - split-group WARN item
- `installer/registry.toml` - resolved Doctor split-group detection line
- `setup.py` - one policy object to preview, reinstall, and TUI audit
- `tests/test_pnpm_globals.py` - policy, argv, floor, brownfield, SPLIT/GROUPED fixtures
- `tests/test_guidance.py` - split-group guidance cases
- `tests/test_setup.py` - Doctor preview wiring seam

## Decisions Made

- Branch A with path-hash grouping, as 05-01 measured and instructed.
- Console Doctor left unwired, matching the plan's acceptance criterion on `run_doctor` source.
- `_EMPTY_POLICY` module singleton to satisfy ruff B008 on frozen-dataclass defaults.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ruff B008 on `NodeInstallPolicy()` defaults**
- **Found during:** Task 1 (`make validate`)
- **Issue:** Function-call defaults are forbidden; a frozen empty policy is a singleton.
- **Fix:** Module-level `_EMPTY_POLICY = NodeInstallPolicy()`.
- **Files modified:** `installer/pnpm_globals.py`
- **Verification:** `make validate` passed
- **Committed in:** `4cb5578` (Task 1)

**2. [Rule 3 - Blocking] E501 on verbatim Container C paths**
- **Found during:** Task 3 (`make validate`)
- **Issue:** Full `/root/.local/share/pnpm/global/v11/...mermaid-cli` lines exceeded 100 characters.
- **Fix:** Trimmed the host prefix to `/g/v11/...`; hash directories remain verbatim from Container C.
- **Files modified:** `tests/test_pnpm_globals.py`
- **Verification:** parse tests still distinguish SPLIT vs GROUPED
- **Committed in:** `4a09900` (Task 3)

---

**Total deviations:** 2 auto-fixed (2 blocking quality-gate).
**Impact on plan:** None. Behaviour matches the plan; fixtures keep the membership hashes.

## Issues Encountered

None that blocked production tasks.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase complete, ready for next step. `REQ-puppeteer-catalog-entries` is complete. `installer/wizard_app.py`, `installer/render.py`, `installer/app.py` and `installer/deps.py` were not modified.

## Self-Check: PASSED

- Key files exist on disk
- `git log --oneline --all --grep="05-04"` returns the three feat commits
- All task `<acceptance_criteria>` passed, including python one-liners, greps, `PLAN_BASE` guard, and `make validate` / `make test`
- No real package install or shell-config edit was performed against this machine

---
*Phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer*
*Completed: 2026-09-06*
