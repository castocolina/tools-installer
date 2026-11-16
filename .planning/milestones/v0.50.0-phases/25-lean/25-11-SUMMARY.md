---
phase: 25-lean
plan: "11"
subsystem: installer
tags: [lean, phase-gate, guards, vulture, suppressions, reachability, size-cap]

requires:
  - phase: 25-10
    provides: the final module split (installer/compose.py and the split screens) that the phase gates now measure
provides:
  - every phase guard run against the pre-phase SHA d0d88257 (D-12 assertions, suppression pairing, vulture-60 multiset, reachability, absence)
  - the measured net production change for installer/ and setup.py, with both SHAs
  - the kept-target table with callers, and the already-gone and deleted target evidence
affects: [phase-verification, ci-push-per-wave]

actuals:
  tokens: 128
  tasks: 2
  commits: 1
  measured: "git rev-list --count 3d61184f..HEAD at SUMMARY write (the SUMMARY commit itself is written after this measure)"

tech-stack:
  added: []
  patterns:
    - "suppression pairing: an added lint/type suppression must be paid for by a removed line with the same stripped text, one-for-one"
    - "vulture gate as a multiset of (kind, name) over the same production scope on both sides"

key-files:
  created: []
  modified:
    - tests/test_setup.py
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Removed the stale reportPrivateUsage suppression at tests/test_setup.py:693 (commit d19461c6): the rewrite to patch_composition reads no private attribute, so the ignore paid for nothing"
  - "The net count uses production paths only (installer, setup.py); tests are excluded per SPEC R5"
  - "The phase guard scripts stay in the session scratchpad with the p25-11- prefix and are not committed"

patterns-established:
  - "Phase gate: run every guard against the pre-phase SHA, paste each output into the SUMMARY"

requirements-completed: [LEAN-01, LEAN-02, LEAN-03, LEAN-04]

duration: not recorded
completed: 2026-11-15
status: complete

coverage:
  - id: D1
    description: "The final tree passes make validate and make test (7620 passed, 6 skipped, 96.15% coverage)"
    verification:
      - kind: integration
        ref: "command: make validate && make test"
        status: pass
    human_judgment: false
  - id: D2
    description: "No assertion, decorator or suppression was weakened across the phase (D-12, R1-32)"
    verification:
      - kind: other
        ref: "command: p25-d12-guard.py d0d88257 (checked 25 tests); p25-11-suppressions.py d0d88257 (4 added suppression lines, 0 unpaired)"
        status: pass
    human_judgment: false
  - id: D3
    description: "No new unused production symbol: vulture-60 (kind, name) multiset, 194 rows before and 177 after, no count rose"
    verification:
      - kind: other
        ref: "command: p25-11-vulture-diff.sh d0d88257"
        status: pass
    human_judgment: false
  - id: D4
    description: "The net production change and the kept-target table with callers"
    verification: []
    human_judgment: true
    rationale: "A report for the phase review: the numbers are measured below, and the reviewer confirms the kept-target judgments"
  - id: D5
    description: "CI green on ubuntu and macOS for the pushed phase head"
    verification: []
    human_judgment: true
    rationale: "Not established by this executor: the orchestrator pushes the phase head and records the CI run ids"
---

# Phase 25 Plan 11: Phase gate, net count, and kept-target report Summary

**Phase 25 gates pass on the final tree against d0d88257: 76 net production lines removed, one stale suppression fixed, no new unused symbol, and every kept target has a caller**

## Performance

- **Duration:** not recorded (the executor did not capture a start epoch)
- **Tasks:** 2
- **Files modified:** 2 (`tests/test_setup.py`, `.planning/REQUIREMENTS.md`)

## SHAs

- **before:** `d0d88257feec3895ee51d1b0050b47cabc3f9888` (the parent of `203d1584`, the first Phase 25 commit touching installer/, setup.py or tests/)
- **after:** `d19461c60c2722de6976f4628307420486ae2c94` (the last code commit; the phase report commit follows it)
- **plan_head_before:** `3d61184fdd78585aa7ca987bfd4258f8c1ca5a3d` (the worktree base for plan 25-11)
- **plan_head_after:** `d19461c60c2722de6976f4628307420486ae2c94`

## Net production change (D-09, SPEC R5)

Measured with `git diff --shortstat d0d88257 HEAD -- installer setup.py`:

    41 files changed, 5091 insertions(+), 5167 deletions(-)

**net production lines removed: 76** (5167 deletions minus 5091 insertions). Tests are excluded by the path filter. Zero or negative would be a valid report; the value is what was measured.

Per-file numstat (`git diff --numstat d0d88257 HEAD -- installer setup.py`), insertions then deletions:

| File | + | - |
| --- | ---: | ---: |
| installer/agent_env.py | 1 | 24 |
| installer/app_messages.py | 38 | 0 |
| installer/app.py | 0 | 6 |
| installer/catalog_audit.py | 1 | 1 |
| installer/compose.py | 937 | 0 |
| installer/deps.py | 0 | 13 |
| installer/diskusage.py | 9 | 0 |
| installer/doctor_messages.py | 55 | 0 |
| installer/doctor_screen.py | 782 | 0 |
| installer/engine.py | 18 | 42 |
| installer/enums.py | 1 | 1 |
| installer/execute_screen.py | 93 | 84 |
| installer/executors.py | 0 | 19 |
| installer/host_setup.py | 0 | 56 |
| installer/install_ownership.py | 2 | 26 |
| installer/locations.py | 1 | 1 |
| installer/modals.py | 389 | 0 |
| installer/model.py | 5 | 29 |
| installer/mutation_lock.py | 89 | 0 |
| installer/omz.py | 10 | 28 |
| installer/ownership.py | 3 | 52 |
| installer/policies_screen.py | 526 | 0 |
| installer/post_install.py | 22 | 91 |
| installer/receipts.py | 1 | 1 |
| installer/resolve.py | 0 | 2 |
| installer/run.py | 0 | 11 |
| installer/schedules_screen.py | 749 | 0 |
| installer/session.py | 6 | 14 |
| installer/settings.py | 1 | 1 |
| installer/shellrc.py | 0 | 5 |
| installer/systemd_daemon.py | 8 | 1 |
| installer/terminal_shell.py | 3 | 4 |
| installer/ui_common.py | 20 | 0 |
| installer/uninstall_review.py | 417 | 0 |
| installer/uninstall_screen.py | 762 | 0 |
| installer/update.py | 7 | 32 |
| installer/verify_registry.py | 0 | 4 |
| installer/version_cache.py | 0 | 11 |
| installer/version_status.py | 4 | 6 |
| installer/wizard_app.py | 95 | 3740 |
| setup.py | 36 | 862 |

Final sizes (`wc -l`) of the split modules and of the composition root:

| Module | Lines | Notes |
| --- | ---: | --- |
| installer/app_messages.py | 38 | split message classes |
| installer/doctor_messages.py | 55 | split message classes |
| installer/mutation_lock.py | 89 | split |
| installer/modals.py | 389 | split |
| installer/uninstall_review.py | 417 | split |
| installer/policies_screen.py | 526 | split |
| installer/schedules_screen.py | 749 | split |
| installer/uninstall_screen.py | 762 | split |
| installer/doctor_screen.py | 782 | split |
| installer/wizard_app.py | 793 | split; the largest of the ten under the 800 cap |
| installer/compose.py | 937 | the composition root; outside `_SPLIT_MODULES` (the 800-line cap in tests/test_reachability.py covers the ten split modules only) |
| setup.py | 663 | wiring only |

## Phase guards, run against d0d88257

**D-12 assertion and decorator guard (`p25-d12-guard.py d0d88257…`)**

    checked 25 tests against d0d88257feec3895ee51d1b0050b47cabc3f9888
    exit=0

tests/test_cli.py and tests/test_install_sh.py are byte-identical to the before tree (the guard's `git diff --quiet` passed). Every `--all`/`--categories` test in tests/test_setup.py keeps its assert and decorator segments.

**Suppression pairing guard (`p25-11-suppressions.py`)**

Self-check (all cases must give their stated verdict):

    self-check PASS: deleted suppression in one file, a different one added in another -> must fail (unpaired=1)
    self-check PASS: moved line with the same suppression -> must pass (unpaired=0)
    self-check PASS: setup. to compose. retarget with the same ignore -> must pass (unpaired=0)
    self-check PASS: from-import retarget from installer.setup to installer.compose -> must pass (unpaired=0)
    self-check PASS: one removed line pays for only one of two identical additions -> must fail (unpaired=1)
    self-check PASS: a module outside the normalization set is not rewritten -> must fail (unpaired=1)
    self-check PASS: diff header parsing

Real run against d0d88257 on the committed HEAD:

    added suppression lines checked: 4; unpaired: 0
    exit=0

The first real run found one unpaired added suppression (see Deviations). The fix is committed, and the gate was re-run on the committed tree. No whitelist file was added and pyproject.toml is unchanged.

**Vulture-60 (kind, name) multiset gate (`p25-11-vulture-diff.sh d0d88257…`)**

Both sides scan the same production scope (`installer`, `setup.py`, `--min-confidence 60`); the before side is `git archive d0d88257 installer setup.py` extracted to a scratch directory.

    before rows: 194; after rows: 177
    vulture-60 (kind, name) gate: PASS
    exit=0

No (kind, name) count rose, so no new unused symbol was added and no Textual hook exception was needed.

**Reachability and size tests (`tests/test_reachability.py`)**

`test_every_installer_module_is_reachable_from_an_entry_point`, `test_dispatch_table_targets_live_in_reachable_modules` and `test_split_modules_stay_under_800_lines` pass (targeted run exit 0; also inside the full suite).

**Race-epoch selection**

    uv run pytest tests/test_wizard_app.py tests/test_screen_family.py -k "generation or supersede or epoch or refresh" -n auto -q --no-cov
    30 passed, exit=0

**Absence checks on installer/ and setup.py**

- `rg -nw` over the retired identifiers (host_setup, host_setup_handoff, pnpm_add_command, ConfirmSensitiveAction, SensitivePrompt, SENSITIVE_POST_INSTALL_ACTIONS, confirm_sensitive_action, SensitiveActionScreen, run_interactive_command, save_manager_snapshot, classify_source_line, disable_plugins, PermissionMode, requires_integrity_errors and the rest of the list): no match, exit 1.
- `grep -c "^def _build_app(" setup.py`: `0`.
- `test -e installer/compose.py`: present.

**Full gates**

    make validate: exit 0 (ruff, format, pyright 0 errors, bandit, vulture, shellcheck)
    make test: exit 0; 7620 passed, 6 skipped; coverage 96.15% (required 90.0%);
               installer/compose.py listed in the coverage table at 98%

`git status --short -- installer setup.py tests` prints nothing after the fix commit, so no stray edits remain.

## Kept targets and their callers

| Target | Where it is defined | Caller(s) |
| --- | --- | --- |
| `installer/agent_env.py` (package `adapters`) | installer/agent_env.py | `installer/agent_settings.py:22` (`from installer.agent_env import adapters`); `tests/test_agent_env.py:3`. The test that asserts it has exactly this importer (tests/test_agent_settings.py) passes. |
| `app._choose_tools` | installer/app.py:110 | called in `run_wizard` (installer/app.py:117, call at line 136), the `--all`/`--categories` filter |
| `selection.select_tools` (a live id-to-tool helper, not the questionary chooser) | installer/selection.py:8 | `installer/catalog_tui.py:743`, `installer/session.py:856` |
| `diskusage.probe_disk_pressure` (triage keep) | installer/diskusage.py:105 | `installer/compose.py:281` |
| `receipts.scan_retired` (triage keep) | installer/receipts.py:654 | `setup.py:476`; `installer/compose.py:697`, `:704` |
| `render.render_troubleshooting` (triage keep) | installer/render.py:535 | `setup.py:341`, `setup.py:650` |
| `schedules.sweep_adapters` (triage keep) | installer/schedules.py:1929 | `setup.py:493`; `installer/compose.py:632` |
| test seam `CatalogScreen.status_text` | installer/catalog_tui.py:503 (class at :223) | the catalog tests (tests/test_catalog_tui.py and others) |
| test seam `CatalogScreen.recommends_text` | installer/catalog_tui.py:507 (class at :223) | the catalog tests (tests/test_catalog_tui.py and others) |
| test seam `UnifiedApp.catalog_for` | installer/wizard_app.py:466 (class at :81) | tests/test_wizard_app.py, tests/test_catalog_tui.py, tests/test_setup.py |

The ten remaining Message classes, each with its post site and handler (none deleted):

| Message | Defined | Post site | Handler |
| --- | --- | --- | --- |
| GlobalsReinstalled | installer/doctor_messages.py:10 | installer/doctor_screen.py:673 | `on_globals_reinstalled`, doctor_screen.py:768 |
| GlobalsAudited (carries `generation`, the AR-04 race epoch) | installer/doctor_messages.py:23 | installer/doctor_screen.py:704 | `on_globals_audited`, doctor_screen.py:710 |
| DiskPressureProbed | installer/doctor_messages.py:49 | installer/doctor_screen.py:304 | `on_disk_pressure_probed`, doctor_screen.py:306 |
| ScheduleChanged | installer/schedules_screen.py:63 | installer/schedules_screen.py:639 | `on_schedule_changed`, schedules_screen.py:641 |
| ScheduleManagerProbed | installer/schedules_screen.py:76 | installer/schedules_screen.py:302 | `on_schedule_manager_probed`, schedules_screen.py:304 |
| RemovalFinished | installer/uninstall_screen.py:99 | installer/uninstall_screen.py:670 | `on_removal_finished`, uninstall_screen.py:672 |
| CursorModelsRead | installer/modals.py:272 | installer/modals.py:333 | `on_cursor_models_read`, modals.py:335 |
| ScheduleDefaultsApplied | installer/app_messages.py:8 | installer/wizard_app.py:431 | `on_schedule_defaults_applied`, wizard_app.py:433 |
| RefreshPublished | installer/app_messages.py:23 | installer/wizard_app.py:332 | `on_refresh_published`, wizard_app.py:336 |
| RefreshFinished | installer/app_messages.py:33 | installer/wizard_app.py:334 | `on_refresh_finished`, wizard_app.py:345 |

## Already gone before this phase (absence checks)

| Target | Check and result |
| --- | --- |
| installer/audit.py | `test -e`: absent |
| installer/agent_policy.py | `test -e`: absent |
| installer/agent_guidance.py | `test -e`: absent |
| installer/guards.py | `test -e`: absent |
| `agent_environment_policy`, `compose_agent_environment_policy` | `rg -nw` finds no `def` or `class` in installer/; the only hits are the absence assertions in tests/test_agent_settings.py:1143-1144 against installer/policy.py, which pass |
| `Tool.source`, `Tool.owner`, `Tool.uninstall` | The `Tool` dataclass (installer/model.py:326) declares id, name, category, cmd, methods, priority, audience, tier, desc, requires, recommends, postinstall, post_install, owner_probes, config_paths, retired; none of the three names is a field (`owner_probes` is a different field) |
| `setup._ask_checkbox` | `rg -nw`: no match in installer/, setup.py or tests/ |
| `prompt.select_categories`, `prompt.select_tools` | `rg -nw select_categories`: no match; `prompt.select_tools` is not present |

## Deleted by this phase

- **host_setup kind (plan 25-02):** `installer/host_setup.py` is deleted (`--diff-filter=D` lists it; 56 deletions). The retired-identifier grep returns zero matches in installer/ and setup.py.
- **sensitive-action machinery (plan 25-03):** the confirmation types, the prompt, and the threading are gone; the grep for ConfirmSensitiveAction, SensitivePrompt, SENSITIVE_POST_INSTALL_ACTIONS, confirm_sensitive_action and SensitiveActionScreen returns zero matches.
- **triaged symbols (plan 25-04):** run_interactive_command, save_manager_snapshot, classify_source_line, disable_plugins, PermissionMode and requires_integrity_errors are absent from installer/ and setup.py (the grep returns zero matches; `"defaultPermissionMode"` and the live `_classify_source_lines` are not matched by `rg -w`).

## Task Commits

1. **Task 1: every phase guard passes against the pre-phase SHA, and the full gates are green** - `d19461c6` (`fix(25-11)`: drop the stale pyright suppression the suppression guard flagged). The gate commit is the only code change in this plan.
2. **Task 2: the SUMMARY reports the net production lines with both SHAs and lists every kept target with its caller** - this phase-report commit (`docs(25-11)`), which adds this file and the LEAN requirement marks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale pyright suppression removed in tests/test_setup.py**
- **Found during:** Task 1 (the suppression pairing guard, `p25-11-suppressions.py d0d88257`)
- **Issue:** `monkeypatch.setattr(setup, "_execute_inputs", recording_inputs)  # pyright: ignore[reportPrivateUsage]` was rewritten to `patch_composition(monkeypatch, "_execute_inputs", recording_inputs)  # pyright: ignore[reportPrivateUsage]` in the phase. The new line reads no private attribute, so the ignore paid for nothing and the gate found it as an added suppression with no removed line of the same text. Sibling calls such as `patch_composition(monkeypatch, "_build_app", ...)` carry no ignore.
- **Fix:** removed the trailing `# pyright: ignore[reportPrivateUsage]` comment on that line. No assertion, decorator or test expectation changed.
- **Files modified:** tests/test_setup.py
- **Verification:** the suppression gate re-run on the committed tree reports 4 added suppression lines, 0 unpaired; the D-12 guard still passes (checked 25 tests); `make validate` and `make test` pass.
- **Committed in:** d19461c6

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** the fix is one line, removes a suppression the phase added without a reason, and changes no assertion. Nothing else in the phase needed a change.

## Decisions Made

- The phase guard scripts were written as `p25-11-*` in the session scratchpad (`p25-11-suppressions.py`, `p25-11-vulture-diff.sh`, `p25-11-vulture-compare.py`) to follow the plan-id prefix rule. They are not committed. The before tree was extracted to a scratch directory and removed after the run.
- `p25-d12-guard.py` and `p25-before-sha.sh` were run as written by plan 25-05. Both were read before running and are read-only.

## Issues Encountered

- `make test` reports 6 skipped tests. This plan did not examine them; they did not fail the gate.
- The CI result for ubuntu and macOS is not in this report. The orchestrator pushes the phase head and records the run ids (see below).
- The shell is zsh, so `PIPESTATUS` did not carry the exit status through a pipe. The exit codes in this report come from runs whose output went to a file.

## CI (D-09)

Pending the orchestrator's push of the phase head. The run ids for ubuntu and macOS are to be recorded here or in the phase VERIFICATION by the orchestrator. This executor did not push.

## Known Stubs

None.

## Threat Flags

None.

## Next Phase Readiness

- Plan 25-11 is the last plan of Phase 25. Its gates pass on the final tree against d0d88257, and the report carries the measured net count, both SHAs, and the kept-target table with callers.
- Open for the orchestrator: push the phase head, watch CI on ubuntu and macOS, and record the run ids.

## Self-Check: PASSED

- `.planning/phases/25-lean/25-11-SUMMARY.md`: found
- commit `d19461c6` (the gate fix): found in HEAD history
- tree after the docs commit: clean for installer/, setup.py and tests/

---
*Phase: 25-lean*
*Completed: 2026-11-15*
