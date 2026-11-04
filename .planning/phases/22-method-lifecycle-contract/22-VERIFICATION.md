---
phase: 22-method-lifecycle-contract
verified: 2026-11-04T12:00:00Z
status: human_needed
score: 5/5 must-haves verified (1 via override)
covered_files:
  - ".planning/phases/22-method-lifecycle-contract/22-01-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-01-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-02-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-02-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-03-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-03-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-04-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-04-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-05-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-05-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-06-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-06-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-07-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-07-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-08-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-08-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-09-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-09-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-10-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-10-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-11-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-11-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-12-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-12-SUMMARY.md"
  - ".planning/phases/22-method-lifecycle-contract/22-13-PLAN.md"
  - ".planning/phases/22-method-lifecycle-contract/22-13-SUMMARY.md"
  - "installer/app.py"
  - "installer/apps.py"
  - "installer/atomic.py"
  - "installer/catalog_tui.py"
  - "installer/deps.py"
  - "installer/doctor.py"
  - "installer/download.py"
  - "installer/engine.py"
  - "installer/enums.py"
  - "installer/execute_screen.py"
  - "installer/executors.py"
  - "installer/guards.py"
  - "installer/guidance.py"
  - "installer/host_setup.py"
  - "installer/install_ownership.py"
  - "installer/locations.py"
  - "installer/manager_versions.py"
  - "installer/model.py"
  - "installer/ownership.py"
  - "installer/pnpm_globals.py"
  - "installer/policy.py"
  - "installer/post_install.py"
  - "installer/postinstall.py"
  - "installer/prompt.py"
  - "installer/receipts.py"
  - "installer/registry.toml"
  - "installer/render.py"
  - "installer/resolve.py"
  - "installer/run.py"
  - "installer/selection.py"
  - "installer/session.py"
  - "installer/settings.py"
  - "installer/skill_lifecycle.py"
  - "installer/status.py"
  - "installer/terminal_shell.py"
  - "installer/tool_browser.py"
  - "installer/tweaks.py"
  - "installer/ui_common.py"
  - "installer/uninstall.py"
  - "installer/update.py"
  - "installer/verify_registry.py"
  - "installer/version_cache.py"
  - "installer/version_status.py"
  - "installer/versions.py"
  - "installer/wizard_app.py"
  - "scripts/container-e2e-verify.sh"
  - "scripts/detect-container-runtime.sh"
  - "scripts/e2e-residue-allowlist.txt"
  - "scripts/lib/prune-tmp-common.sh"
  - "scripts/prune-tmp-linux.sh"
  - "setup.py"
covered_digest: "v3:sha256:8a75f53a3f2f50dcb2071fba1e8e0bf09f2b852b42ac8442e55c55516a686db4"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "opencode removal runs `opencode uninstall --keep-config --keep-data` (fake runner)"
    reason: "Review R2-05: opencode v1.19.5 uninstall on a curl install rewrites the shell rc regardless of --keep-config, deletes unrecorded cache/state dirs and never deletes the binary. opencode declares no vendor `remove` and is removed by its receipt-proven binary alone. SPEC:37/:144, CONTEXT, UI-SPEC and LIFE-01 amended; the declared-`remove` mechanism itself stays and is tested with a fake runner."
    accepted_by: "orchestrator (RUN-LEDGER 2026-11-04, 22 replan cycle 3, R2-05 sign-off)"
    accepted_at: "2026-11-04T00:00:00Z"
human_verification:
  - test: "Open Uninstall in a NO_COLOR 80x20 tmux pane, press `c` on a row with config_paths (gh, uv, kitty) and on one without (rg); then open the confirm review modal"
    expected: "Flagged row shows the `c` config prefix/suffix; rg shows 'rg declares no config to delete.' in the detail bar; the review modal lists removals, config to delete, config kept, and fits 80x20 without clipping"
    why_human: "Visual layout and readability under NO_COLOR at a small terminal size; tests assert text, not rendering"
  - test: "Trigger a native (dnf/apt/pacman) manual handoff, then select and copy the `you run:` command from the run log"
    expected: "The exact command copies cleanly as one line and runs as shown"
    why_human: "Terminal text selection and clipboard behaviour"
  - test: "On a real macOS host with VS Code installed as a cask, check the update view and press `u`"
    expected: "`brew outdated --cask --greedy-auto-updates` reports it when outdated; `u` runs `brew upgrade --cask --greedy-auto-updates visual-studio-code`; `brew list` tap formula short names (e.g. anomalyco/tap/opencode -> opencode) are matched"
    why_human: "Real Homebrew cask metadata and tap listing; only fakes run on Linux CI"
  - test: "Run the container e2e harness self-tests / array-expansion paths under macOS bash 3.2"
    expected: "No unbound-variable errors under set -u; same tracer lines"
    why_human: "Needs a macOS bash 3.2 interpreter; the test only greps for the guarded expansion form"
  - test: "On a real (non-container) host, uninstall one receipt-proven tool through the Uninstall view"
    expected: "Only the receipt's paths are removed, config kept unless `c` was pressed, receipt retired"
    why_human: "Project rule forbids mutating the developer host from an agent; container e2e covers Fedora only"
---

# Phase 22: Method lifecycle contract Verification Report

**Phase Goal:** Update and removal follow one per-method contract: nothing is removed without proof, no executor runs sudo, and config stays unless the user asks.
**Verified:** 2026-11-04
**Status:** human_needed
**Re-verification:** No (initial verification)

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every kind, both directions (scratch HOME): install writes a receipt, Uninstall shows removable, removal leaves none of the receipt's paths; a foreign file at a declared script path is never deleted | VERIFIED | `tests/test_uninstall_e2e.py::test_every_receipt_kind_installs_and_removes_in_both_directions` parametrized over github_release, tarball, app, script, brew, cask, uv-tool, node, two rounds each, asserts receipt, `plan.level != "none"`, removed, receipt gone, no proven path left. Foreign file: `test_a_declared_path_present_before_the_install_is_never_adopted`, `tests/test_uninstall.py::test_a_foreign_file_at_a_declared_path_survives`, `tests/test_app.py::test_a_foreign_file_at_a_declared_path_survives_the_cli_removal`, `tests/test_receipts.py` replaced/retargeted cases. All pass. |
| 2 | opencode removal (override); brew/uv/pnpm uninstall only on receipt proof, otherwise a hint; pnpm co-install member warns about its group | PASSED (override) + VERIFIED | opencode: registry stanza declares `paths = ["~/.opencode/bin/opencode"]`, no `remove` (R2-05 override). Receipt gate: `test_app.py::test_a_brew_package_without_a_receipt_runs_nothing`, manager_listing C-02/C-04 tests; `remove_tool` shared by CLI and TUI. Group warning: `pnpm_globals.py:308` "removes the whole group, X included", `test_app.py::test_the_cli_prints_the_group_warning_before_the_confirm`, `test_wizard_app.py::test_the_pnpm_group_warning_reads_the_frozen_decision`. Real-pnpm group semantics measured in a container (22-13 D-1). |
| 3 | `u` on OMZ runs `upgrade.sh`, on SDKMAN `sdk selfupdate`; `u` on a pinned app without version source refused with reason | VERIFIED | `registry.toml:618` `update = ["{omz_root}/tools/upgrade.sh"]` (resolver per C-17, SPEC R8 amended), `:1957` `update = ["sdk", "selfupdate"]`; `update.py:270` pinned refusal with `PINNED_DETAIL`. Tests `test_update.py::test_omz_update_*` (4), `test_sdkman_bootstrap_update_runs_selfupdate_sourced`, `test_a_pinned_app_is_refused_by_update_refusal`, `test_perform_update_on_a_pinned_app_runs_nothing`, `test_catalog_tui.py::test_u_on_a_pinned_app_is_refused_before_the_lock`. |
| 4 | Unwritable brew prefix becomes a manual handoff; native dnf/apt/pacman handed off as the exact command; grep test finds zero sudo argv | VERIFIED | `executors.needs_manual` (`executors.py:644`) with native command table (`:613-615`, strings only, never run); `engine.py:250` returns MANUAL_REQUIRED (FAILED when earlier errors, C-01) with `manual_command`. `writable_prefix` declared for the three brew bootstraps (`registry.toml:184/194/204`). Tests: `test_plan.py::test_an_unwritable_prefix_is_planned_manual_and_nothing_runs`, `test_engine.py::test_the_engine_re_checks_a_prefix_that_became_unwritable`, `test_plan.py::test_a_native_only_tool_is_planned_manual_with_its_exact_command`, AST tests `test_executors.py::test_no_argv_literal_starts_with_an_elevation_command`, `test_no_registry_argv_starts_with_an_elevation_command`, `test_plan.py::test_no_sudo_argv_on_the_plan_path`, load-time `ELEVATION_COMMANDS` refusal (`model.py:599`). |
| 5 | "delete config too" only for tools with config_paths (default keep; CLI `--yes` never deletes config); harness dir in config_paths rejected at load; container e2e compares listings before/after uninstall | VERIFIED | `wizard_app.py:1619-1633` refuses `c` without config_paths; tests `test_c_turns_the_flag_on_and_the_removal_deletes_the_config`, `test_an_unflagged_row_sends_no_config`, `test_unflagged_config_is_reviewed_as_kept`, refusal text asserted at `test_wizard_app.py:8300/8427`; `test_app.py::test_the_cli_never_deletes_config`. Load-time denylist: `model._parse_config_paths` over `HARNESS_MARKER_DIRS`, tests `test_config_paths_rejects_a_harness_dir`, `..._shared_well_known_dir`. E2E: `container-e2e-verify.sh` `home_listing` baseline (line 232) and `assert_no_leftovers`/`new_leftovers` (613-672) wired into pass 2 (781); recorded run (22-13 D-2 closure) `TRACER_RECEIPTS_GONE_OK count=61`, `TRACER_LEFTOVER_OK`, `make e2e exit=0`. |

**Score:** 5/5 truths verified (1 part via override, 0 present-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/model.py` | config_paths, script paths/remove/update/writable_prefix validation | VERIFIED | `_parse_config_paths`, `HARNESS_MARKER_DIRS`, `ELEVATION_COMMANDS`, `SCRIPT_ROOTS` |
| `installer/executors.py` | native handoff, no sudo executors | VERIFIED | `needs_manual`, `prefix_writable`; native table holds display strings only |
| `installer/receipts.py` | type-only tree/leaf proof, preexisting paths | VERIFIED | used by engine and uninstall; shortcut C-07 documented |
| `installer/uninstall.py` / `installer/app.py` | removal_plan levels, one remover for CLI and TUI, config step 4 | VERIFIED | `removal_plan`, `remove_tool`, `pnpm_removal_packages`, `delete_config_path` |
| `installer/update.py` | vendor update argv, pinned refusal, greedy cask upgrade | VERIFIED | lines 110-112, 173-187, 270 |
| `installer/manager_versions.py` | `--greedy-auto-updates` read | VERIFIED | `brew_greedy_outdated`, `_greedy_cask_read` |
| `installer/wizard_app.py` | `c` toggle, full review modal, config result lines | VERIFIED | tests in `test_wizard_app.py` 8154-8861 |
| `installer/registry.toml` | 18 script stanzas with lifecycle data, config_paths | VERIFIED | config_paths on uv, gh, glow, pnpm, kitty; `test_script_lifecycle_data` |
| `scripts/container-e2e-verify.sh`, `scripts/e2e-residue-allowlist.txt` | HOME listing diff, receipt-gone check | VERIFIED | wired into pass 2; self-tests in `test_container_e2e_receipts.py` |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| engine.install_tool | executors.needs_manual | plan-time and run-time re-check | WIRED |
| CLI run_uninstall / TUI removal | app.remove_tool | shared remover, re-prove after confirm | WIRED |
| app.remove_tool | ownership.manager_listing | readable listing gate before manager uninstall | WIRED |
| download script tokens / update | omz.omz_root | single resolver (C-17) | WIRED |
| setup.py `__main__` | run.apply_child_env | HOMEBREW_NO_SUDO / NO_AUTOREMOVE, drop SUDO_ASKPASS | WIRED (`test_setup_applies_the_child_env_before_main_runs`) |
| container-e2e pass2 | assert_no_leftovers | `home-before.txt` vs `home-after.txt` | WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase test files (app, cli, container_e2e_receipts, engine, executors, model, ownership, plan, receipts, registry, uninstall, uninstall_e2e, update, version_cache, version_status, manager_versions, run, wizard_app) | `uv run pytest <files> --no-cov -n auto` | 2203 passed, exit 0 | PASS |
| catalog_tui, pnpm_globals, render, guidance, download, omz | `uv run pytest <files> --no-cov -n auto` | 656 passed | PASS |
| Container e2e | not run by the verifier (orchestrator re-run in progress) | recorded in 22-13-SUMMARY D-2 closure: `make e2e exit=0`, `TRACER_LEFTOVER_OK` | PASS (recorded) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` declared for this phase. Not applicable.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| LIFE-01 | Script paths, update, optional remove from proven exe; opencode no remove; delete only declared existing paths | SATISFIED | SC1, SC2 (override); `test_a_recipe_tool_is_removed_by_its_vendor_command_first`, `test_script_lifecycle_data` |
| LIFE-02 | Native installs handed off as exact command; no sudo | SATISFIED | SC4 |
| LIFE-03 | brew/uv/pnpm uninstall only on receipt proof, else hint | SATISFIED | SC2; manager receipt only when package absent pre-install (R3-02) |
| LIFE-04 | config_paths; harness dirs never listed | SATISFIED | SC5; one `HARNESS_MARKER_DIRS` source shared with skill_lifecycle |
| LIFE-05 | `u` refused for pinned app with reason | SATISFIED | SC3 |
| LIFE-06 | Vendor updates use vendor command | SATISFIED | SC3 |
| LIFE-07 | Unwritable prefix becomes handoff after preflight | SATISFIED | SC4 |
| LIFE-08 | pnpm co-install group warning | SATISFIED | SC2; copy amended to measured semantics (UI-SPEC D-1) |
| LIFE-09 | Container e2e compares file listings | SATISFIED | SC5; recorded run exit 0 |
| LIFE-10 | macOS greedy auto-updating casks | SATISFIED (code) / human on real macOS | `test_manager_versions.py` greedy tests, `test_update.py::test_u_on_an_auto_updating_cask_runs_the_greedy_upgrade` |
| UI-04 | Uninstall "delete config too"; default keep; CLI never deletes | SATISFIED | SC5 |

No orphaned requirements: every ID mapped to Phase 22 in REQUIREMENTS.md is claimed by a plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| phase-changed installer/, scripts/, setup.py | - | TBD/FIXME/XXX/TODO/HACK added in phase diff | none found | - |
| `receipts._leaf_matches`, `uninstall._recipe_argv`, `container-e2e-verify.sh home_listing` | - | `shortcut:` comments (C-07, C-21, D-2 empty-dir skip) | Info | documented limits, accepted in 22-REVIEW-FIX |

### Accepted Residuals and Deviations (not gaps)

- C-05 by design (ledger Q2: handoff ends the ladder, no silent brew switch).
- C-11 accepted: update binds the declared existing leaf, not a receipt-proven one.
- C-17 accepted: one `omz_root` resolver; SPEC R8 amended (d4bcfd8).
- R1-11, R1-14, R1-22 signed off (ledger).
- C-12 residual (Info): the e2e does not assert absence for level-`none` receipts (oh-my-zsh, sdkman, brew bootstrap survive by design) and the empty-dir skip can hide an empty must-clear dir. LIFE-09's listing comparison itself is delivered.
- Bookkeeping (Info): ROADMAP still shows 22-13 unchecked (12/13) and REQUIREMENTS.md rows read Pending; the orchestrator updates these at phase close. 22-13-SUMMARY frontmatter `status: halted` predates its appended D-2 closure section.

### Human Verification Required

1. **NO_COLOR 80x20 Uninstall `c` toggle and review modal** — press `c` on gh/uv/kitty and on rg; open the confirm review. Expected: readable prefixes/suffixes, refusal in the detail bar, modal fits. Why human: visual.
2. **Copy the manual handoff command from the run log** — expected one clean copyable line. Why human: terminal selection.
3. **Real macOS greedy casks and `brew list` tap short names** — expected greedy outdated/upgrade argv and short-name matching. Why human: real Homebrew.
4. **macOS bash 3.2 harness run** — expected no `set -u` unbound errors. Why human: needs bash 3.2.
5. **Real-host removal of a receipt-proven tool** — expected only receipt paths removed, config kept by default. Why human: agents never mutate the host.

### Gaps Summary

No blocking gaps. All five roadmap success criteria and all eleven requirements have code, wiring and passing tests; the opencode clause of SC2 is satisfied through the recorded R2-05 override. Status is human_needed only for the five human-only checks above.

---

_Verified: 2026-11-04_
_Verifier: Claude (gsd-verifier)_
