---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 18
subsystem: detection
tags: [catalog-tui, skill-lifecycle, ownership, doctor, registry]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: catalog presence, skill-pack handoff, ownership resolution, and Doctor guidance from plans 16-01..16-17
provides:
  - probe-less skill packs take presence from the PATH answer
  - by_harness install handoff is framed and labeled per host
  - install-state probes honor match; a repeated probe harness fails at load
  - a non-active location copy shadows instead of blocking OS-package ownership
  - Doctor drops the inert enter hint after apply
  - a stale current row says current as of the last check
affects: [catalog, skill-pack-handoff, ownership, doctor]

actuals:
  tokens: 8051
  tasks: 8
  commits: 9

tech-stack:
  added: []
  patterns:
    - "probe-less skill packs reuse _installed; probe-backed packs stay unknown until hosts land"
    - "D-06 shadows is one tuple: link-proven brew plus non-active location-proof candidates"

key-files:
  created: []
  modified:
    - installer/catalog_tui.py
    - installer/skill_lifecycle.py
    - installer/model.py
    - installer/ownership.py
    - installer/wizard_app.py
    - installer/registry.toml

key-decisions:
  - "WR-04 header is the constant 'Run each block inside the named host.'"
  - "The Claude alternative marker is the action's exact 'or, instead, from the obra marketplace:' line."
  - "IN-10 location shadows match the location-proof evidence string, so an artifact-backed installer candidate still blocks."

patterns-established:
  - "INSTALL_STATE_FILES is a closed match-to-filename table; an unknown match is unknown"
  - "Post-apply Doctor rewrites inert enter sentences by containment, not startswith"

requirements-completed: [D-02, D-05, D-06, D-14, D-15, D-16, D-17, D-19]

coverage:
  - id: D1
    description: "A skill pack with no status_probes takes presence from the PATH answer, including the Ver cell and installed group."
    requirement: D-02
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_pack_with_no_status_probes_uses_path_presence"
        status: pass
    human_judgment: false
  - id: D2
    description: "by_harness install handoff is framed, host-labeled, and marks the Claude marketplace pair as an alternative."
    requirement: D-14
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_superpowers_install_on_claude_only_host_is_framed_and_labeled"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_superpowers_by_harness_marks_claude_alternative_and_explains_codex"
        status: pass
    human_judgment: false
  - id: D3
    description: "An unknown install-state match is unknown; a duplicated status_probes harness fails at load."
    requirement: D-15
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_install_state_probe_honors_match"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_duplicate_status_probe_harness_fails_at_load"
        status: pass
    human_judgment: false
  - id: D4
    description: "A non-active script or sdkman location copy is a shadow, so the OS-package owner still resolves."
    requirement: D-06
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_non_active_script_location_shadows_instead_of_blocking_os_package"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_non_active_sdkman_location_shadows_instead_of_blocking_os_package"
        status: pass
    human_judgment: false
  - id: D5
    description: "After apply, Doctor no longer tells the user to press enter, including a mid-string block-owner record."
    requirement: D-16
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_doctor_drops_inert_enter_hint_after_apply"
        status: pass
    human_judgment: false
  - id: D6
    description: "u on a stale current row says current as of the last check; a fresh current row is unchanged."
    requirement: D-17
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_update_on_stale_current_qualifies_the_last_check"
        status: pass
    human_judgment: false
  - id: D7
    description: "The alacritty registry comment no longer claims kitty has no method on immutable Fedora."
    requirement: D-19
    verification:
      - kind: other
        ref: "git diff 71dd4ae^..71dd4ae -- installer/registry.toml"
        status: pass
    human_judgment: false

duration: 17min
completed: 2026-10-10
status: complete
---

# Phase 16: Catalog truth Summary

**Probe-less skill packs, host-labeled install handoff, location shadows, and Doctor wording now agree with the live answer**

## Performance

- **Duration:** 17 min
- **Started:** 2026-10-10T19:26:32Z
- **Completed:** 2026-10-10T19:43:11Z
- **Tasks:** 8
- **Files modified:** 12

## Accomplishments

- A skill pack with no `status_probes` (openspec, spec-kit) takes Inst, group, and Ver from the PATH answer. Probe-backed packs still stay unknown until hosts land.
- Superpowers install handoff names each host, frames the blocks, marks the obra marketplace pair as an alternative, and replaces the bare Codex `/plugins` + `superpowers` pair with one self-explanatory line.
- An unknown install-state `match` is `unknown`. A repeated `status_probes` harness fails at load.
- A non-active script or sdkman location copy is a shadow, so kitty and java with a live `/usr/bin` copy resolve to the OS-package owner.
- After apply, Doctor no longer says press enter, including when that sentence sits after a block-owner fragment.
- `u` on a stale current row says current as of the last check. The alacritty comment no longer misstates kitty.

## Task Commits

Each task was committed atomically:

1. **Task 1: WR-03 probe-less presence** - `e2d5dbc` (fix)
2. **Task 2: WR-04 host-labeled handoff** - `6ae95a3` (fix)
3. **Task 3: IN-17 + IN-18 match and duplicate harness** - `8bb1f9d` (fix)
4. **Task 4: IN-10 location shadows** - `0cc67cc` (fix)
5. **Task 5: IN-12 inert enter hint** - `41f99a8` (fix)
6. **Task 6: IN-15 stale current wording** - `ed990dd` (fix)
7. **Task 7: IN-16 alacritty comment** - `71dd4ae` (docs)
8. **Task 8: format gate fix** - `772f85f` (style)

**Plan metadata:** this commit (docs: summary for plan 16-18)

## Finding ledger

| Finding | Commit | Result |
|---------|--------|--------|
| WR-03 | `e2d5dbc` | fixed |
| WR-04 | `6ae95a3` | fixed |
| IN-10 | `0cc67cc` | fixed |
| IN-12 | `41f99a8` | fixed |
| IN-15 | `ed990dd` | fixed |
| IN-16 | `71dd4ae` | fixed |
| IN-17 | `8bb1f9d` | fixed |
| IN-18 | `8bb1f9d` | fixed |
| IN-03 | — | accepted: two legitimate marketplaces; one probe per harness cannot name both |
| IN-04 | — | accepted: fails closed when two managers claim a directory; harm is a label |
| IN-05 | — | accepted: documented `shortcut:` in a background refresh |
| IN-07 | — | accepted: rare; repair reinstalls the declared package and is non-destructive |
| IN-08 | — | accepted: remaining `--version` run is bounded by `run_query`'s timeout |
| IN-09 | — | accepted: private-name suppressions are scoped and pass the gates |
| puppeteer `!` / `no version` | — | accepted: this host's pnpm globals hold only `@opengsd/gsd-browser`; `~/.local/share/pnpm/bin/puppeteer` is a leftover shim, so `dangling_shim` is true |

## Files Created/Modified

- `installer/catalog_tui.py` - probe-less `_present` fallback; stale-aware current wording
- `installer/skill_lifecycle.py` - `_HOST_HEADER`, labeled install lines, `INSTALL_STATE_FILES`
- `installer/model.py` - duplicate-harness check in `_parse_status_probes`
- `installer/ownership.py` - `shadows` tuple generalizing the D-06 brew shadow
- `installer/wizard_app.py` - post-apply containment rewrite in `_tui_guidance`
- `installer/registry.toml` - superpowers claude/codex handoff lines; alacritty comment

## Decisions Made

- Host frame text is `Run each block inside the named host.`
- Claude alternative marker is the plan action's exact prose line, not a rewritten command.
- Location shadows are identified by the location-proof evidence string so an artifact-backed installer candidate still blocks native attribution.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Format gate on three test files**
- **Found during:** Task 8 (gate run)
- **Issue:** `ruff format --check` would reformat `tests/test_model.py`, `tests/test_ownership.py`, and `tests/test_wizard_app.py` (extra EOF blank lines and one join wrap).
- **Fix:** `ruff format` on those three files only.
- **Files modified:** tests/test_model.py, tests/test_ownership.py, tests/test_wizard_app.py
- **Verification:** `make validate && make test` exit 0 after the style commit.
- **Committed in:** `772f85f`

**2. [smallest deviation] WR-04 marker does not start with `or `**
- **Found during:** Task 2
- **Issue:** The behavior bullet asked for a prose line starting with `or `; the action specified the exact string `or, instead, from the obra marketplace:`, which starts with `or,`.
- **Fix:** Shipped the action's exact string. The registry test asserts that line, not `startswith("or ")`.
- **Files modified:** installer/registry.toml, tests/test_registry.py
- **Verification:** `tests/test_registry.py` and `tests/test_skill_lifecycle.py` pass.
- **Committed in:** `6ae95a3`

**3. [smallest deviation] IN-10 fixtures stay under tmp_path and use a split package name**
- **Found during:** Task 4
- **Issue:** A literal `~/.local` or `~/.sdkman` bin_dir would expand into the real home. A probe answer equal to the declared package name makes `_native_owner` win, not os-package.
- **Fix:** bin dirs are absolute paths under `tmp_path`. Probe answers are `kitty-terminfo` and `java-21-openjdk-headless`, the same split-package shape as `_os_package_probe` in the git fixture, so the owner is os-package.
- **Files modified:** tests/test_ownership.py
- **Verification:** both RED fixtures fail with `unknown` before the fix and pass after it; inventory-backed brew/pnpm/uv still block.
- **Committed in:** `0cc67cc`

---

**Total deviations:** 3 auto-fixed (1 gate, 2 smallest-plan-vs-action)
**Impact on plan:** No scope creep. The shipped behavior matches the action steps.

## Issues Encountered

- This repo has no `.codegraph/` index, so symbol location used Read and Grep after one `codegraph_explore` call reported the index missing.
- First `make validate` failed on ruff format. Fixed in `772f85f` and rerun.

## User Setup Required

None - no external service configuration required.

## Verification

- `make validate` exit 0 on the rerun: ruff check passed, ruff format reported 141 files already formatted, pyright 0 errors, bandit quiet, vulture quiet, shellcheck quiet.
- `make test` exit 0: `3453 passed, 5 skipped in 329.17s (0:05:29)`. Coverage 95.87% (required 90%).

## Next Phase Readiness

- Review findings WR-03, WR-04, IN-10, IN-12, IN-15, IN-16, IN-17, and IN-18 are closed on this branch.
- Accepted items IN-03, IN-04, IN-05, IN-07, IN-08, IN-09, and the puppeteer observation are recorded above and were not coded.
- STATE.md and ROADMAP.md were left untouched, per the executor brief.

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
