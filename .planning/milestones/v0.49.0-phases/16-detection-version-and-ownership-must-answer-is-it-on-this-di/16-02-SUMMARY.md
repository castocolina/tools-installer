---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 02
subsystem: skill-lifecycle
tags: [skill_pack, status_probes, harness-cli, skills-lock, install-state]

requires: []
provides:
  - Per-harness status_probes model over plugin-cli, skills-lock, and install-state
  - Closed HARNESS_CLI_STATUS table and batched inspect_skill_packs
  - Ponytail and superpowers registry rows migrated off command status ops
affects: [16-07, 16-12]

actuals:
  tokens: 9712
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Registry selects harness/via/match from closed code tables; argv and paths stay in code"
    - "One harness CLI argv per inspect_skill_packs call, host order follows SKILL_HARNESSES"

key-files:
  created: []
  modified:
    - installer/model.py
    - installer/skill_lifecycle.py
    - installer/registry.toml
    - tests/test_model.py
    - tests/test_skill_lifecycle.py

key-decisions:
  - "inspect_status resolves a missing home inside the function. Ruff B008 forbids Path.home() as a default."
  - "A pack with zero status_probes is manual-required, not vacuously absent."
  - "The skill lock is read only when a pack uses skills-lock, and at most once per call."

patterns-established:
  - "HARNESS_CLI_STATUS mirrors HOST_SETUPS: code-owned argv plus a matcher, looked up with .get"
  - "Disk fallbacks use closed home-relative dir tables. Skill names that fail ^[A-Za-z0-9._-]+$ or are . or .. are skipped before any path join."

requirements-completed: [D-09, D-10, D-11, D-14]

coverage:
  - id: D1
    description: "Ponytail and superpowers declare status_probes and report present from canned codex plugin list and pi list output."
    requirement: D-10
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_shipped_packs_report_per_host_status"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_shipped_status_probes_select_closed_sources"
        status: pass
    human_judgment: false
  - id: D2
    description: "Codex not-installed rows are absent, the Claude ❯ row is present, and a harness with no CLI row is unknown with zero probe calls."
    requirement: D-10
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_codex_not_installed_row_is_absent"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_claude_plugin_list_marker_row_is_present"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_plugin_cli_without_closed_row_is_unknown_and_unprobed"
        status: pass
    human_judgment: false
  - id: D3
    description: "skills-lock and install-state answer from a throwaway home. A ../evil skill name is ignored."
    requirement: D-11
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_skills_lock_present_when_source_and_skill_dir_exist"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_skills_lock_ignores_traversal_skill_names"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_install_state_file_is_present_and_missing_is_absent"
        status: pass
    human_judgment: false
  - id: D4
    description: "Three Claude packs cause one claude plugin list call. Host key order follows SKILL_HARNESSES."
    requirement: D-14
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_one_cli_call_per_harness_across_packs"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_host_order_follows_skill_harnesses_not_declaration_order"
        status: pass
    human_judgment: false
  - id: D5
    description: "SKILL_HARNESSES includes factory-droid and gemini-cli, in alphabetical order."
    requirement: D-09
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_skill_harnesses_include_factory_droid_and_gemini_cli"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 02: Per-harness skill status probes Summary

**Skill packs report present, absent, or unknown per harness from a closed CLI table, a skill lock, or gsd-install-state.json, with one list call per harness.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-10-10T09:36:00Z
- **Completed:** 2026-10-10T09:57:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Replaced the two command status operations with `status_probes` (`harness`, `via`, `match`). Ponytail and superpowers load through that shape.
- `inspect_skill_packs` batches `claude plugin list`, `codex plugin list`, and `pi list`, and matches line-anchored names. A missing CLI row or a probe exception is `unknown`, never `absent`.
- `skills-lock` and `install-state` read only closed home-relative dirs. The skills CLI is never run.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end superpowers/ponytail status_probes** - `089775d` (feat)
2. **Task 2: Disk-fallback sources skills-lock and install-state** - `97e07e8` (feat)
3. **Task 3: Batch-once guarantee and stable host order** - `e132f35` (test)

**Plan metadata:** this summary commit (`docs(16-02): summary for plan 16-02`)

TDD red was observed and not committed separately. A failing-test commit would be a knowingly broken tree.

## Files Created/Modified

- `installer/model.py` - `SkillStatusProbe`, `status_probes` parsing, widened `SKILL_HARNESSES`; removed the two status-arg types
- `installer/skill_lifecycle.py` - `HARNESS_CLI_STATUS`, disk dir tables, `inspect_skill_packs`
- `installer/registry.toml` - ponytail and superpowers `status_probes`; status ops are manual-required fallback text
- `tests/test_model.py` - harness widening pin
- `tests/test_skill_lifecycle.py` - migrated admission tests and probe pins

## Decisions Made

- `inspect_status(..., home=None)` calls `Path.home()` inside the body. Ruff B008 rejects a `Path.home()` default. Callers can still omit `home`.
- Empty `status_probes` returns manual-required before the all-absent check. `all([])` is true, so the other order would report absent.
- The lock file is parsed only when some pack uses `skills-lock`, so a plugin-cli pass does not read the real home.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Path.home() default failed ruff B008**
- **Found during:** Task 1 (CLI table)
- **Issue:** The plan's `home=Path.home()` signature is a function call in a default. Ruff B008 fails `make validate`.
- **Fix:** `home: Path | None = None`, then `Path.home()` when omitted.
- **Files modified:** installer/skill_lifecycle.py
- **Verification:** `make validate` passed
- **Committed in:** `089775d`

**2. [Rule 1 - Bug] Empty probe list must not be vacuously absent**
- **Found during:** Task 1 (inspect_status wrapper)
- **Issue:** The plan lists "all hosts absent" before "no probes". An empty host map makes `all(...)` true, so a manual pack would read absent.
- **Fix:** No probes returns `manual-required` with the status instructions, then all-absent, then unknown.
- **Files modified:** installer/skill_lifecycle.py
- **Verification:** `test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual` passed for the five manual packs
- **Committed in:** `089775d`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both keep the catalog loadable and the quality gate green. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-12 can call `inspect_skill_packs` and must supply the timed `run_query` probe. This plan maps probe exceptions to `unknown` but does not start a CLI itself.
- Plan 16-07 owns the full pack audit and the registry pin that every `install-state` match is the literal `gsd-core`. This plan does not enforce that match.
- `SKILL_LOCK_HARNESS_DIRS` has only `claude`. Other harness dirs stay out until that audit verifies them.
- A stale `installer/__pycache__/model.cpython-314.pyc` from 2026-09-22 still contained the removed status names. It was deleted locally and is not in git. A recursive grep of `installer/` and `tests/` now returns nothing.

## Self-Check: PASSED

- `grep -rn` of `codex_plugin_status|pi_package_status|CodexPluginStatusArgs|PiPackageStatusArgs` under `installer/` and `tests/` returned nothing after the stale 3.14 bytecode was removed.
- `grep -c 'HARNESS_CLI_STATUS\\[' installer/skill_lifecycle.py` printed 0.
- `grep -c 'Path.home()' tests/test_skill_lifecycle.py` printed 0.
- `uv run pytest tests/test_model.py tests/test_skill_lifecycle.py tests/test_registry.py tests/test_engine.py -q` exited 0.
- `uv run pytest -q` exited 0 (progress reached 100%; skips only, no FAILED).
- `make validate` exited 0 (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
