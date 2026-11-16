---
phase: 22-method-lifecycle-contract
verified: 2026-11-15T00:00:00Z
status: passed
score: 5/5 must-haves verified (1 via override)
covered_files: [".planning/phases/22-method-lifecycle-contract/22-01-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-01-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-02-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-02-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-03-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-03-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-04-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-04-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-05-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-05-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-06-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-06-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-07-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-07-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-08-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-08-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-09-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-09-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-10-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-10-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-11-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-11-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-12-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-12-SUMMARY.md",".planning/phases/22-method-lifecycle-contract/22-13-PLAN.md",".planning/phases/22-method-lifecycle-contract/22-13-SUMMARY.md","installer/app.py","installer/apps.py","installer/atomic.py","installer/catalog_tui.py","installer/deps.py","installer/doctor.py","installer/download.py","installer/engine.py","installer/enums.py","installer/execute_screen.py","installer/executors.py","installer/guidance.py","installer/install_ownership.py","installer/locations.py","installer/manager_versions.py","installer/model.py","installer/ownership.py","installer/pnpm_globals.py","installer/policy.py","installer/post_install.py","installer/postinstall.py","installer/prompt.py","installer/receipts.py","installer/registry.toml","installer/render.py","installer/resolve.py","installer/run.py","installer/selection.py","installer/session.py","installer/settings.py","installer/status.py","installer/terminal_shell.py","installer/tool_browser.py","installer/tweaks.py","installer/ui_common.py","installer/uninstall.py","installer/update.py","installer/verify_registry.py","installer/version_cache.py","installer/version_status.py","installer/versions.py","installer/wizard_app.py","scripts/container-e2e-verify.sh","scripts/detect-container-runtime.sh","scripts/e2e-residue-allowlist.txt","scripts/lib/prune-tmp-common.sh","scripts/prune-tmp-linux.sh","setup.py"]
covered_digest: "v4:sha256:4a4841b476eee63a8909b242d77cdec02ecaf66f7dc8f8a75821c97d2912cd24"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "opencode removal runs `opencode uninstall --keep-config --keep-data` (fake runner)"
    reason: "Review R2-05: opencode v1.19.5 uninstall on a curl install rewrites the shell rc regardless of --keep-config, deletes unrecorded cache/state dirs and never deletes the binary. opencode declares no vendor `remove` and is removed by its receipt-proven binary alone. SPEC:37/:144, CONTEXT, UI-SPEC and LIFE-01 amended; the declared-`remove` mechanism itself stays and is tested with a fake runner."
    accepted_by: "orchestrator (RUN-LEDGER 2026-11-04, 22 replan cycle 3, R2-05 sign-off)"
    accepted_at: "2026-11-04T00:00:00Z"
re_verification:
  date: 2026-11-15
  head: d8c469f7
  previous_status: human_needed
  previous_score: 5/5
  reason: "agent-run re-verification at HEAD after phases 23 to 24.5; digest recomputed (installer/guards.py and installer/skill_lifecycle.py no longer exist and are dropped from covered_files)"
  gaps_closed: []
  gaps_remaining: []
  regressions: []
  human_item_verdicts:
    - item: 1
      verdict: resolved
      evidence: "container ti-uat-22-fedora (Fedora 44), tmux 80x20 NO_COLOR, captures scratchpad/uat/22-reverify/02..07: [c] marker + 'config +' prefix on gh, 'rg declares no config to delete.' on rg, detail sentence 'config deleted too: ~/.config/gh (c keeps it)', confirm modal (runs line, 'Config deleted too:') fits 80x20 unclipped. jev (typesafe) resolved 0.85. Observation, open-trivial: at 80 columns the 'What gets removed' header and cells are cut without an ellipsis; the detail bar carries the full text; fine at 140 columns."
    - item: 2
      verdict: owner-only
      evidence: "mouse selection and clipboard copy of the run-log command in a real terminal emulator; jev (typesafe) owner-only 0.83. The exact command text is proven by tests (test_plan manual command cases) and the container capture of the earlier UAT."
    - item: 3
      verdict: deferred (macOS, no CI path)
      evidence: "real Homebrew greedy casks and tap short names; fake-runner tests test_manager_versions greedy cases and test_update::test_u_on_an_auto_updating_cask_runs_the_greedy_upgrade pass at HEAD; jev (typesafe) owner-only 0.93"
    - item: 4
      verdict: deferred (macOS, no CI path)
      evidence: "bash 3.2 harness run; the guarded array-expansion form is grep-tested; docker.io/library/bash:3.2 image exists locally but the harness needs a macOS toolchain"
    - item: 5
      verdict: resolved (container)
      evidence: "removal of receipt-proven tools gh and mmdc through the Uninstall view in the container: receipts gone (09-disk-after.txt), gh config deleted only with c, glow config kept. A run on the owner's real host is forbidden for agents (owner-only for the host itself)."
    - item: 6
      verdict: resolved
      evidence: "at HEAD mmdc installs through its bun method first (registry.toml), so the pnpm group path is the second method. Real pnpm 12.21.0 in the container re-measured: a comma-joined group 'pnpm add --global is-odd,is-even' then 'pnpm remove --global is-odd' removes the whole group (11-real-pnpm-group.txt), so the group warning copy stays true. F-2/F-3 tests pass at HEAD (test_app group_member and unselected_members_receipt cases, test_pnpm_globals::test_a_member_known_gone_is_not_named, test_wizard_app group warning cases). Container bun removal of mmdc removed only mmdc, the puppeteer receipt and package stayed, consistent. jev (typesafe) open-real 0.85, overruled: the jev premise was that the pnpm path is unreachable, the pnpm semantics themselves were measured and the code paths are unit-tested."
  requirement_verdicts:
    LIFE-01: "SATISFIED (override on the opencode clause; tests pass at HEAD)"
    LIFE-02: "SATISFIED (test_plan manual handoff tests pass; jq/glab/alacritty planned manual with the exact command in the container install)"
    LIFE-03: "SATISFIED (container: receipt-proven removals only)"
    LIFE-04: "SATISFIED (test_model config_paths tests pass)"
    LIFE-05: "SATISFIED (F-1 test passes)"
    LIFE-06: "SATISFIED (test_update pass)"
    LIFE-07: "SATISFIED (test_plan, test_engine pass)"
    LIFE-08: "SATISFIED (real pnpm 12.21.0 group semantics re-measured; F-2/F-3 tests pass)"
    LIFE-09: "SATISFIED (e2e listing comparison script; test_container_e2e_receipts passes; no fresh make e2e run by this re-verification)"
    LIFE-10: "SATISFIED (code) / deferred (real macOS)"
    UI-04: "SATISFIED (container: c toggle, review modal, config deleted for gh and kept for glow)"
  tests: "uv run pytest app, pnpm_globals, version_status, wizard_app, uninstall, uninstall_e2e, update, container_e2e_receipts, manager_versions, registry, model, plan, executors, receipts: 2244 passed"
  refresh_2026_11_15:
    date: 2026-11-15
    head: c76a9e2b
    suite: "make validate && make test at HEAD c76a9e2b: 7676 passed, 6 skipped in 57.05s, coverage 96.07%"
    phase_tests: "own test files from this report's evidence run with uv run pytest -n 0 --no-cov: all passed"
    verified_commit: ee763b58
    changed_files: "installer/app.py installer/catalog_tui.py installer/tool_browser.py installer/ui_common.py installer/wizard_app.py"
    dropped_covered_files: "none"
    must_haves: "re-checked: unchanged. a8c37dc2 touches app/catalog_tui/tool_browser/ui_common/wizard_app UI only; the method lifecycle contract (resolve/executors/ownership) is untouched by it. The 4 test files are green."
  refresh_2026_11_15b:
    date: 2026-11-15
    head: 1cc6953e
    suite: "make validate && make test at HEAD 1cc6953e: 7679 passed, 6 skipped in 57.04s, coverage 96.09%"
    phase_tests: "own test files from this report's evidence run with uv run pytest -n 0 --no-cov: all passed"
    verified_commit: ed04c454
    changed_files: "installer/tool_browser.py installer/ui_common.py installer/wizard_app.py"
    dropped_covered_files: "none"
    must_haves: "re-checked: unchanged. 7e9f2edb and 42ed8cd4 (merge 1cc6953e) only cap the status line at four rows, end the Policies Effect column and the Schedules detail in an ellipsis, and move cut_rows/Rows into ui_common (installer/ui_common.py, tool_browser.py, wizard_app.py, tests/test_layout_80x20.py, tests/test_schedules_view.py); layout and status-line code only, no behavior contract changed; this phase's test files are green."
  refresh_2026_11_16:
    date: 2026-11-16
    head: a2e68cf3
    suite: "make validate && make test at HEAD a2e68cf3: 7662 passed, 6 skipped in 60.05s, coverage 96.20%"
    phase_tests: "own test files from this report's evidence run with uv run pytest -n 0 --no-cov at HEAD: all passed; deleted test files dropped: none"
    verified_commit: b4d0cde9
    changed_files: "installer/app.py installer/deps.py installer/engine.py installer/enums.py installer/execute_screen.py installer/executors.py installer/install_ownership.py installer/locations.py installer/model.py installer/ownership.py installer/post_install.py installer/receipts.py installer/resolve.py installer/run.py installer/session.py installer/settings.py installer/terminal_shell.py installer/ui_common.py installer/update.py installer/verify_registry.py installer/version_cache.py installer/version_status.py installer/wizard_app.py setup.py"
    dropped_covered_files: "installer/host_setup.py"
    must_haves: "re-checked: unchanged. Phase 25 (Lean) moved or deleted code (host_setup and sensitive-action retirements, compose.py, wizard_app.py split into ten modules); 25-VERIFICATION, 25-SECURITY and 25-UAT prove behaviour preserved (AST-identical moves, byte-identical 80x20 screens, real install and uninstall); this phase's surviving test files are green."
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
  - test: "In a disposable container with real pnpm, install mmdc (with its puppeteer co-install), remove only mmdc from the Uninstall view, then reopen Uninstall and run the review again"
    expected: "Status shows `puppeteer: removed with the mmdc group` after the counts, the puppeteer receipt is gone, and a later review names no absent group member"
    why_human: "The F-2/F-3 fixes landed after the last container UAT (83cb0dc) and the last make e2e (4727d2f); only fake-runner tests cover them, and real pnpm group semantics are a container-only check"
---

# Phase 22: Method lifecycle contract Verification Report

**Phase Goal:** Update and removal follow one per-method contract: nothing is removed without proof, no executor runs sudo, and config stays unless the user asks.
**Verified:** 2026-11-04
**Status:** human_needed
**Re-verification:** Yes. Incremental, after the stale digest (allowlist 4727d2f, UAT fixes eb14872, dd73476, cae8aa5) at HEAD 6164583. Unchanged evidence is carried forward from the initial report (970f830).

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every kind, both directions (scratch HOME): install writes a receipt, Uninstall shows removable, removal leaves none of the receipt's paths; a foreign file at a declared script path is never deleted | VERIFIED | `tests/test_uninstall_e2e.py::test_every_receipt_kind_installs_and_removes_in_both_directions` parametrized over github_release, tarball, app, script, brew, cask, uv-tool, node, two rounds each, asserts receipt, `plan.level != "none"`, removed, receipt gone, no proven path left. Foreign file: `test_a_declared_path_present_before_the_install_is_never_adopted`, `tests/test_uninstall.py::test_a_foreign_file_at_a_declared_path_survives`, `tests/test_app.py::test_a_foreign_file_at_a_declared_path_survives_the_cli_removal`, `tests/test_receipts.py` replaced/retargeted cases. All pass. |
| 2 | opencode removal (override); brew/uv/pnpm uninstall only on receipt proof, otherwise a hint; pnpm co-install member warns about its group | PASSED (override) + VERIFIED | opencode: registry stanza declares `paths = ["~/.opencode/bin/opencode"]`, no `remove` (R2-05 override). Receipt gate: `test_app.py::test_a_brew_package_without_a_receipt_runs_nothing`, manager_listing C-02/C-04 tests; `remove_tool` shared by CLI and TUI. Group warning: `pnpm_globals.py:308` "removes the whole group, X included", `test_app.py::test_the_cli_prints_the_group_warning_before_the_confirm`, `test_wizard_app.py::test_the_pnpm_group_warning_reads_the_frozen_decision`. Real-pnpm group semantics measured in a container (22-13 D-1). Re-checked after the UAT fixes. F-2: `app.retire_group_members` (`app.py:538`) runs only after a node `MANAGER_UNINSTALL_ARGV` removal and retires a member receipt only when a readable fresh `manager_listing("node")` lacks it (unreadable listing or failed delete retires nothing). Wired into CLI `run_uninstall` (`app.py:813`) and TUI `perform_uninstall` (`app.py:980`), surfaced through `SweepResult.with_group` in `wizard_app.py:1851`. F-3: `co_install_warnings(..., present=...)` is keyword-only and both callers pass it (`app.py:753`, `wizard_app.py:1606`, codegraph + grep). Tests pass: `test_app::test_a_group_member_pnpm_already_removed_is_removed`, `..._tui_group_removal_retires_the_unselected_members_receipt`, `..._group_member_pnpm_still_lists_keeps_its_receipt`, `..._unreadable_listing_keeps_the_group_members_receipt`, `..._cli_group_warning_skips_a_member_already_gone`, `test_pnpm_globals::test_a_member_known_gone_is_not_named`, `test_wizard_app::test_the_group_warning_skips_a_member_shown_absent`, `..._a_member_removed_with_its_group_is_reported_after_the_counts`. |
| 3 | `u` on OMZ runs `upgrade.sh`, on SDKMAN `sdk selfupdate`; `u` on a pinned app without version source refused with reason | VERIFIED | `registry.toml:618` `update = ["{omz_root}/tools/upgrade.sh"]` (resolver per C-17, SPEC R8 amended), `:1957` `update = ["sdk", "selfupdate"]`; `update.py:270` pinned refusal with `PINNED_DETAIL`. Tests `test_update.py::test_omz_update_*` (4), `test_sdkman_bootstrap_update_runs_selfupdate_sourced`, `test_a_pinned_app_is_refused_by_update_refusal`, `test_perform_update_on_a_pinned_app_runs_nothing`, `test_catalog_tui.py::test_u_on_a_pinned_app_is_refused_before_the_lock`. Re-checked after F-1 (cae8aa5): `version_status.version_notes` (`version_status.py:937`) now calls the same `update.update_refusal` predicate `u` uses, so a pinned tool's note reads `u does not update it: pinned; ...` instead of promising the install path; `test_version_status::test_a_pinned_install_note_matches_the_u_refusal` passes. No import cycle (`update.py` does not import `version_status`). Container UAT test 6 (`u` on pinned sublime) PASS. |
| 4 | Unwritable brew prefix becomes a manual handoff; native dnf/apt/pacman handed off as the exact command; grep test finds zero sudo argv | VERIFIED | `executors.needs_manual` (`executors.py:644`) with native command table (`:613-615`, strings only, never run); `engine.py:250` returns MANUAL_REQUIRED (FAILED when earlier errors, C-01) with `manual_command`. `writable_prefix` declared for the three brew bootstraps (`registry.toml:184/194/204`). Tests: `test_plan.py::test_an_unwritable_prefix_is_planned_manual_and_nothing_runs`, `test_engine.py::test_the_engine_re_checks_a_prefix_that_became_unwritable`, `test_plan.py::test_a_native_only_tool_is_planned_manual_with_its_exact_command`, AST tests `test_executors.py::test_no_argv_literal_starts_with_an_elevation_command`, `test_no_registry_argv_starts_with_an_elevation_command`, `test_plan.py::test_no_sudo_argv_on_the_plan_path`, load-time `ELEVATION_COMMANDS` refusal (`model.py:599`). |
| 5 | "delete config too" only for tools with config_paths (default keep; CLI `--yes` never deletes config); harness dir in config_paths rejected at load; container e2e compares listings before/after uninstall | VERIFIED | `wizard_app.py:1619-1633` refuses `c` without config_paths; tests `test_c_turns_the_flag_on_and_the_removal_deletes_the_config`, `test_an_unflagged_row_sends_no_config`, `test_unflagged_config_is_reviewed_as_kept`, refusal text asserted at `test_wizard_app.py:8300/8427`; `test_app.py::test_the_cli_never_deletes_config`. Load-time denylist: `model._parse_config_paths` over `HARNESS_MARKER_DIRS`, tests `test_config_paths_rejects_a_harness_dir`, `..._shared_well_known_dir`. E2E: `container-e2e-verify.sh` `home_listing` baseline (line 232) and `assert_no_leftovers`/`new_leftovers` (613-672) wired into pass 2 (781); recorded run (22-13 D-2 closure) `TRACER_RECEIPTS_GONE_OK count=61`, `TRACER_LEFTOVER_OK`, `make e2e exit=0`. New: 4727d2f adds `.local/share/pki` (the Chromium NSS db, browser runtime state) to `e2e-residue-allowlist.txt`, a narrow single-dir entry with its reason. The final orchestrator `make e2e` on 4727d2f exited 0 with TRACER_CLEAN_INSTALL_OK, TRACER_RERUN_OK, TRACER_UNINSTALL_OK, TRACER_RECEIPTS_GONE_OK, TRACER_LEFTOVER_OK, TRACER_REINSTALL_OK, TRACER_CONTAINER_TEARDOWN_OK, and the container was removed. Container UAT (22-UAT.md) tests 2-4 (`c` toggle, review modal, CLI `--yes` keeps config) PASS. |

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
| Re-verification: changed-file tests (app, pnpm_globals, version_status, wizard_app, uninstall, uninstall_e2e, update, container_e2e_receipts) at 6164583 | `uv run pytest <files> --no-cov -n auto` | 1176 passed, exit 0 | PASS |
| Re-verification: UAT-fix named tests (F-1..F-3, 11 tests) | `uv run pytest <4 files> -k "group_member or ... or pinned_install_note" -v` | 11 passed | PASS |
| Re-verification: regression (catalog_tui, engine, executors, model, plan, receipts, registry, manager_versions, ownership) | `uv run pytest <files> --no-cov -n auto` | 1240 passed | PASS |
| Container e2e | final orchestrator `make e2e` on 4727d2f (not run by the verifier) | exit 0; all seven TRACER_*_OK lines incl. TRACER_LEFTOVER_OK and TRACER_CONTAINER_TEARDOWN_OK; container removed | PASS (recorded) |
| Container UAT | 22-UAT.md, run at 83cb0dc | 6/6 PASS; findings F-1..F-3 fixed afterwards (see its "UAT fixes" section) | PASS (recorded) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` declared for this phase. Not applicable.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| LIFE-01 | Script paths, update, optional remove from proven exe; opencode no remove; delete only declared existing paths | SATISFIED | SC1, SC2 (override); `test_a_recipe_tool_is_removed_by_its_vendor_command_first`, `test_script_lifecycle_data` |
| LIFE-02 | Native installs handed off as exact command; no sudo | SATISFIED | SC4 |
| LIFE-03 | brew/uv/pnpm uninstall only on receipt proof, else hint | SATISFIED | SC2; manager receipt only when package absent pre-install (R3-02); F-2 retirement deletes only receipts (no extra pnpm argv) and only on a readable listing proving the member gone |
| LIFE-04 | config_paths; harness dirs never listed | SATISFIED | SC5; one `HARNESS_MARKER_DIRS` source shared with skill_lifecycle |
| LIFE-05 | `u` refused for pinned app with reason | SATISFIED | SC3; the version note now agrees with the refusal (F-1) |
| LIFE-06 | Vendor updates use vendor command | SATISFIED | SC3 |
| LIFE-07 | Unwritable prefix becomes handoff after preflight | SATISFIED | SC4 |
| LIFE-08 | pnpm co-install group warning | SATISFIED | SC2; copy amended to measured semantics (UI-SPEC D-1); re-verified: warning names only present members (F-3), members pnpm took along have their receipts retired (F-2) |
| LIFE-09 | Container e2e compares file listings | SATISFIED | SC5; final `make e2e` on 4727d2f exit 0, TRACER_LEFTOVER_OK |
| LIFE-10 | macOS greedy auto-updating casks | SATISFIED (code) / human on real macOS | `test_manager_versions.py` greedy tests, `test_update.py::test_u_on_an_auto_updating_cask_runs_the_greedy_upgrade` |
| UI-04 | Uninstall "delete config too"; default keep; CLI never deletes | SATISFIED | SC5; container UAT tests 2-4 PASS |

No orphaned requirements: every ID mapped to Phase 22 in REQUIREMENTS.md is claimed by a plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| phase-changed installer/, scripts/, setup.py | - | TBD/FIXME/XXX/TODO/HACK added in phase diff (re-scanned over 970f830..HEAD) | none found | - |
| `receipts._leaf_matches`, `uninstall._recipe_argv`, `container-e2e-verify.sh home_listing` | - | `shortcut:` comments (C-07, C-21, D-2 empty-dir skip) | Info | documented limits, accepted in 22-REVIEW-FIX |

### Accepted Residuals and Deviations (not gaps)

- C-05 by design (ledger Q2: handoff ends the ladder, no silent brew switch).
- C-11 accepted: update binds the declared existing leaf, not a receipt-proven one.
- C-17 accepted: one `omz_root` resolver; SPEC R8 amended (d4bcfd8).
- R1-11, R1-14, R1-22 signed off (ledger).
- C-12 residual (Info): the e2e does not assert absence for level-`none` receipts (oh-my-zsh, sdkman, brew bootstrap survive by design) and the empty-dir skip can hide an empty must-clear dir. LIFE-09's listing comparison itself is delivered.
- Bookkeeping (Info): ROADMAP now shows 22-13 checked (6164583). REQUIREMENTS.md rows for LIFE-01..10 and UI-04 still read Pending; the orchestrator updates these at phase close. 22-UAT.md frontmatter still reads `status: issues_found` although its "UAT fixes" section records F-1..F-3 fixed.
- Evidence ordering (Info): the final `make e2e` (4727d2f) and the container UAT (83cb0dc) both predate the F-1..F-3 code (eb14872, dd73476, cae8aa5). The fixes are proven by fake-runner unit tests only; a real-pnpm container re-check is listed as human item 6. F-2 only deletes receipts and runs no extra command, so it cannot add filesystem residue to the e2e.

### Human Verification Required

1. **NO_COLOR 80x20 Uninstall `c` toggle and review modal** — press `c` on gh/uv/kitty and on rg; open the confirm review. Expected: readable prefixes/suffixes, refusal in the detail bar, modal fits. Why human: visual.
2. **Copy the manual handoff command from the run log** — expected one clean copyable line. Why human: terminal selection.
3. **Real macOS greedy casks and `brew list` tap short names** — expected greedy outdated/upgrade argv and short-name matching. Why human: real Homebrew.
4. **macOS bash 3.2 harness run** — expected no `set -u` unbound errors. Why human: needs bash 3.2.
5. **Real-host removal of a receipt-proven tool** — expected only receipt paths removed, config kept by default. Why human: agents never mutate the host.
6. **Real-pnpm group removal after the UAT fixes** — in a disposable container remove only mmdc from the Uninstall view. Expected: `puppeteer: removed with the mmdc group`, puppeteer receipt gone, a later review names no absent member. Why human: the F-2/F-3 fixes postdate the last container runs.

### Re-verification 2026-11-15 (agent-run at d8c469f7)

Human items 1, 5 and 6 are resolved with container captures (scratchpad/uat/22-reverify/) and tests. Items 3 and 4 are deferred (macOS, no CI path).

**Needs owner confirmation:**

- Item 2: copy of the manual-handoff command line by mouse selection in a real terminal emulator.
- Item 5, host part: a removal of a receipt-proven tool on the owner's real host (agents never mutate it).
- Taste call: the Uninstall table cuts its last column at 80 columns without an ellipsis (open-trivial).

### Gaps Summary

No blocking gaps. All five roadmap success criteria and all eleven requirements have code, wiring and passing tests; the opencode clause of SC2 is satisfied through the recorded R2-05 override. The re-verification found no regression from the allowlist entry or the F-1..F-3 fixes: the new code is wired at every caller and its tests pass. Status is human_needed only for the six human-only checks above.

---

_Verified: 2026-11-04 (re-verified at 6164583)_
_Verifier: Claude (gsd-verifier)_

## Fresh re-verification with inline jev (2026-11-16)

Fresh checks at HEAD 4c1d243e. Each group was classified by the jev ladder (Laya first, TypeSafe jev-1.14.0 under the 2026-10-14 consent) right after its findings, before the next group. `fb` = the column returned `fallback: true` and did not decide.

| Item | Fresh evidence | Laya | TypeSafe | Verdict | Override reason |
|------|----------------|------|----------|---------|-----------------|
| SC1, LIFE-09 (both-direction receipts, listing compare) | `uv run pytest` test_uninstall_e2e, test_uninstall, test_receipts, test_container_e2e_receipts, test_ownership: all pass | open-real 0.46 (fb) | resolved 0.89 | resolved | none |
| SC2, LIFE-01/03/08 (receipt gate, group warning, opencode override) | test_app, test_pnpm_globals pass; opencode stanza declares `remove = ["opencode2","service","stop"]` (a service stop, not `opencode uninstall`), so the accepted override still holds | open-real 0.53 (fb) | open-real 0.81 | resolved | Overrode a confident TypeSafe open-real: every named test passes and the override's subject (vendor `opencode uninstall`) is still not run. Info: the override's reason text says opencode declares no `remove`; that is now stale (a service-stop remove exists). Documentation drift only, open-trivial |
| LIFE-02 (no sudo argv) | `sudo` in executors.py only in a comment and the manual-handoff display strings (lines 701-720); model.py `ELEVATION_COMMANDS`; no other argv with sudo | open-trivial 0.34 (fb) | resolved 0.87 | resolved | none |
| SC3, LIFE-05/06 (OMZ upgrade.sh, sdk selfupdate, pinned refusal) | test_update, test_version_status, test_version_cache pass; registry.toml:624 and :2004 | open-real 0.47 (fb) | resolved 0.51 (fb) | resolved | needs_fallback: decided by me on the passing tests and the registry lines |
| SC4, LIFE-02/07 (prefix handoff) | test_plan, test_engine, test_executors, test_run pass; `writable_prefix` at registry.toml:184/194/204 | open-real 0.45 (fb) | resolved 0.51 (fb) | resolved | needs_fallback: decided by me |
| LIFE-10 (greedy casks) | test_manager_versions passes; `brew_greedy_outdated` uses `--greedy-auto-updates`; no macOS host | open-real 0.48 (fb) | owner-only 0.83 | owner-only (deferred, macOS, no CI) | none |
| SC5, LIFE-04, UI-04 (config_paths, c toggle, CLI never deletes) | test_model, test_registry, test_wizard_app, test_catalog_tui, test_cli pass; `HARNESS_MARKER_DIRS` at model.py:153 | open-real 0.44 (fb) | resolved 0.65 (fb) | resolved | needs_fallback: decided by me |
| Human 1 (80x20 `c` toggle and modal) | captures uat/22-reverify/03,05,07,08: `[c]` + 'config +', 'rg declares no config to delete.', modal with the runs line and 'Config deleted too: ~/.config/gh (gh)' unclipped, '2 removed / Config deleted for gh.'; last table column cut without an ellipsis at 80 columns | open-real 0.43 (fb) | open-trivial 0.71 (fb) | resolved, with open-trivial cosmetic (column cut) | needs_fallback: decided by me |
| Human 2 (copy run-log command by mouse) | no real terminal emulator for agents; command text covered by tests | open-real 0.45 (fb) | owner-only 0.69 (fb) | owner-only | needs_fallback: decided by me |
| Human 3/4 (macOS casks and bash 3.2) | no macOS host or bash 3.2 here; fake-runner and grep tests pass | open-real 0.40 (fb) | open-real 0.54 (fb) | owner-only (deferred, macOS, no CI) | needs_fallback: decided by me. Not open-real: a missing host is not a defect and no code evidence is against it |
| Human 5 (real-host removal) | container capture 08/09 shows receipts gone; the real host is off limits to agents | open-real 0.57 (fb) | owner-only 0.73 (fb) | owner-only (container part resolved) | needs_fallback: decided by me |
| Human 6 (real pnpm group removal) | uat/22-reverify/11-real-pnpm-group.txt: pnpm 12.21.0 comma-joined group removed whole; group-warning tests pass | open-real 0.51 (fb) | resolved 0.98 | resolved | none |

Counts: 12 rows: resolved 8 (plus 1 cosmetic open-trivial note under Human 1 and 1 doc-drift note under SC2), owner-only 4 (LIFE-10, Human 2, Human 3/4, Human 5), open-real 0. jev agreement: of 5 confident (non-fallback) TypeSafe answers, 4 agreed with the verdict (SC1, LIFE-02, LIFE-10, Human 6) and 1 was overridden (SC2); 7 rows had only needs_fallback answers and were decided by me (SC3, SC4, SC5, Human 1, 2, 3/4, 5), where TypeSafe's fallback guess matched my verdict on 5.

Time order (UTC, 2026-11-16; finding made, then jev call; the finding window includes the pytest runs):
- Group 1 (SC1, SC2, LIFE-02): findings 02:44:07 to 02:44:34; jev call 02:44:48 to 02:44:49 (first call 02:44:34 was rejected for empty context, re-sent with context).
- Group 2 (SC3, SC4, LIFE-10): findings 02:44:55 to 02:45:11; jev call 02:45:11.
- Group 3 (SC5, Human 1, 2, 3/4, 5, 6): findings 02:45:16 to 02:47:44; jev call 02:47:44 to 02:47:45.

Status stays `passed`; no open-real finding. Covered files unchanged, so the digest is untouched.

**Orchestrator note (2026-11-16):** two lines in the fresh section rest on old evidence. First, the Uninstall
80-column ellipsis is already fixed: commit 81ef77e4 makes the header and cut cells end in `…`, and the 80x20
captures in `uat/80x20-after2/` and `uat/25/` show `What gets …`. Second, the opencode override reason text is
outdated: opencode now removes through `remove = ["opencode2","service","stop"]`, a service stop. The override's
substance, that `opencode uninstall` is never run, still holds.


## Re-verification 2026-11-16 (after Phase 26)

Changed covered files since the last verifier head (d8c469f7): `installer/guidance.py`, `setup.py`.

- `installer/guidance.py`: Phase 26 commits 457d728f and d444804b replaced `make setup` with `make run` in four
  strings and one comment (reinstall hint, pnpm-globals hint, tmp-cleanup hint). No route or logic change.
  Re-checked: `uv run pytest tests -n 0 --no-cov -q -k "guidance or applies_the_child_env or pnpm_globals"` passes.
- `setup.py`: the docstring now says `make run`; the composition code moved to `installer/compose.py` in Phase 25
  (behavior preserved per 25-VERIFICATION). The cited wiring still holds: `apply_child_env(os.environ)` is called at
  `setup.py:656` and imported at `setup.py:75`; `uv run pytest tests/test_run.py -n 0 --no-cov -q` passes (includes
  `test_setup_applies_the_child_env_before_main_runs`).
- No test, doc or Makefile citation in this VERIFICATION named `make setup` or `make install`; no stale citation to fix.

Verdict: all 5 must-haves (1 via override) still hold; status stays `passed`.
