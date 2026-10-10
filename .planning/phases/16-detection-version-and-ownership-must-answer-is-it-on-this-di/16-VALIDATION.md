---
phase: "16"
slug: "detection-version-and-ownership-must-answer-is-it-on-this-di"
status: backfilled
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-09"
backfilled: "2026-10-10"
audited: "2026-10-10"
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via `uv run pytest --cov`, confirmed in `Makefile:50-51` and `pyproject.toml`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_ownership.py tests/test_install_ownership.py tests/test_skill_lifecycle.py tests/test_rcclean.py -x` |
| **Full suite command** | `uv run pytest --cov` |
| **Estimated runtime** | ~300 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** the narrowest `-k`-filtered pytest invocation matching the touched module
- **After every plan wave:** `uv run pytest --cov` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green, plus the CONTEXT.md-mandated live proof against a real host reproducing each of the five original defects (see Manual-Only Verifications — this is not satisfied by unit tests alone)
- **Max feedback latency:** 300 seconds

---

## Per-Task Verification Map

*Backfilled 2026-10-10 from the executed plans. Each row's command was run in this plan; Status is that run.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 16-01 | 1 | D-01/D-05 | — | SDKMAN-owned tool resolves to `owner="sdkman"`, update dispatches through it | unit | `uv run pytest tests/test_ownership.py -k sdkman -x` | ✅ | ✅ green |
| 16-01-02 | 16-01 | 1 | D-01 (probe fix) | — | `_sdkman` probe matches `kind="sdkman"`/`candidate` param | unit | `uv run pytest tests/test_install_ownership.py -k sdkman -x` | ✅ | ✅ green |
| 16-15-01 | 16-15 | 6 | D-02 | — | Off-policy tool row carries "≠ policy" marker | unit | `uv run pytest tests/test_catalog_tui.py -k off_policy -x` | ✅ | ✅ green |
| 16-02-01 | 16-02 | 1 | D-09 | — | `supported_harnesses` validated against (widened) `SKILL_HARNESSES` | unit | `uv run pytest tests/test_model.py -k skill_harnesses -x` | ✅ | ✅ green |
| 16-12-01 | 16-12 | 4 | D-10/D-14 | — | skill_pack status cached with same staleness model as versions | unit | `uv run pytest tests/test_version_cache.py -x` | ✅ | ✅ green |
| 16-12-02 | 16-12 | 4 | D-13 | — | Multi-host Owner column truncation | unit | `uv run pytest tests/test_catalog_tui.py -k skill_owner_cell -x` | ✅ | ✅ green |
| 16-13-02 | 16-13 | 4 | D-17/D-20 | — | Explicit re-selection of already-installed tool updates/confirms and re-applies post-install only on this path | unit | `uv run pytest tests/test_engine.py tests/test_post_install.py -x` | ✅ | ✅ green |
| 16-09-01 | 16-09 | 3 | D-18 | — | Dangling pnpm shim reads as distinct "broken" state | unit | `uv run pytest tests/test_status.py tests/test_catalog_tui.py -k "broken or dangling" -x` | ✅ | ✅ green |
| 16-08-01 | 16-08 | 2 | D-21/D-23/D-24 | T-15.8 precedent (byte-exact refusal, case-guard emission reused) | Guard-in-place rewrite, backed up, per-file opt-in | unit | `uv run pytest tests/test_shellrc.py tests/test_rcclean.py -k "guard_in_place or path_writer_lines" -x` | ✅ | ✅ green |
| 16-08-02 | 16-08 | 2 | D-22 | — | Foreign marker block never touched | unit | `uv run pytest tests/test_rcclean.py -k marker_block -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Decision coverage audit (2026-10-10)

All 10 map commands above re-run green. Every decision is mapped to existing automated tests; no tests were added.

| Decision | Status | Representative automated tests |
|----------|--------|-------------------------------|
| D-01 | COVERED | `test_ownership.py::test_undeclared_brew_cellar_groovy`, `::test_sdkman_location_proof_resolves_direct_when_which_matches`, `test_version_status.py::test_sdkman_version_through_real_resolve_ownership` |
| D-02 | COVERED | `test_catalog_tui.py::test_off_policy_owner_cell_and_detail_name_the_declared_manager` |
| D-03 | PARTIAL (by design) | The "offer" is text only: `test_update.py::test_off_policy_brew_update_names_the_declared_manager` ("moving it there is not available yet"). No migrate action exists, per D-04. |
| D-04 | DEFERRED | Migration flow is out of Phase 16 scope; nothing to test. |
| D-05 | COVERED | `test_update.py::test_sdkman_owned_update_refuses_with_real_command`, `::test_off_policy_brew_update_names_the_declared_manager` |
| D-06 | COVERED | `test_ownership.py::test_also_installed_note_*`, `test_catalog_tui.py::test_detail_names_also_installed_via_the_shadowed_manager` |
| D-07 | COVERED | `test_ownership.py::test_own_installer_location_proof_resolves_bun_when_brew_does_not_list_it`, `test_registry.py::test_kitty_linux_script_declares_vendor_bin_dir` |
| D-08 | COVERED | `test_catalog_tui.py::test_unknown_detail_names_the_active_binary`, `test_ownership.py::test_active_path_note_*` |
| D-09 | COVERED | `test_model.py::test_skill_harnesses_include_factory_droid_and_gemini_cli`, `test_skill_lifecycle.py::test_superpowers_catalog_is_multi_host_without_a_forced_pi_dependency` |
| D-10 | COVERED | `test_skill_lifecycle.py::test_shipped_packs_report_per_host_status`, `::test_one_cli_call_per_harness_across_packs` |
| D-11 | COVERED | `test_skill_lifecycle.py::test_cursor_is_present_from_disk_when_path_misses`, `::test_skills_lock_*`, `::test_install_state_file_*` |
| D-12 | COVERED | `test_catalog_tui.py::test_skill_inst_cell_shows_persisted_answer_with_stale_mark`, `::test_skill_inst_cell_drops_stale_mark_after_the_probe_lands` |
| D-13 | COVERED | `test_catalog_tui.py::test_skill_owner_cell_lists_hosts_and_truncates_when_wider_than_the_column` |
| D-14 | COVERED | `test_catalog_tui.py::test_skill_probe_covers_packs_when_system_view_mounts_first`, `test_version_status.py::test_refresh_skills_persists_once_and_skips_the_second_call` |
| D-15 | COVERED | `test_skill_lifecycle.py::test_superpowers_install_on_a_claude_only_host_omits_pi`, `::test_cursor_is_present_from_disk_when_path_misses` |
| D-16 | COVERED | `test_resolve.py::test_unavailable_reason_alacritty_names_immutable_host`, `test_catalog_tui.py::test_unavailable_reason_renders_in_row_and_detail` |
| D-17 | COVERED | `test_execute_screen.py::test_current_only_selection_says_already_current_not_install_zero`, `::test_outdated_selected_tool_stays_an_update_target` |
| D-18 | COVERED | `test_ownership.py::test_dangling_pnpm_shim_reads_broken`, `test_catalog_tui.py::test_broken_row_marks_inst_red_and_explains_repair`, `test_execute_screen.py::test_broken_selection_is_installed_with_repair` |
| D-19 | COVERED | `test_registry.py::test_every_script_method_declares_a_location_or_explains_no_bin_dir`, `::test_kitty_declared_location_counts_as_installed` |
| D-20 | COVERED | `test_execute_screen.py::test_explicit_current_selection_reapplies_post_install_once`, `::test_installed_drag_in_is_not_reapplied`, `test_engine.py::test_reapply_post_install_*` |
| D-21 | COVERED | `test_shellrc.py::test_guard_in_place_rewrites_one_foreign_bashrc_line`, `test_rcclean.py::test_path_writer_lines_prepend_is_guardable` |
| D-22 | COVERED | `test_rcclean.py::test_marker_block_kitty_names_the_owner`, `test_guidance.py::test_foreign_block_writer_is_named_and_not_offered` |
| D-23 | COVERED | `test_shellrc.py::test_guard_refuses_a_preexisting_backup_with_different_bytes`, `::test_guard_preserves_mode_0600_on_the_file_and_the_backup`, `test_wizard_app.py` (`.bashrc.tools-installer.old`) |
| D-24 | COVERED | `test_wizard_app.py::test_doctor_guard_chain_confirms_files_in_record_order`, `::test_doctor_guard_no_skips_without_calling_guard_file` |

Open (not Phase 16 test gaps): code-review WR-01 (`installer/shellrc.py:1184`) and IN-01 (`installer/rcclean.py:283`) have no regression tests yet; they are unfixed findings.

---

## Wave 0 Requirements

- [x] Confirm existence and exact names of `tests/test_catalog_tui.py`, `tests/test_model.py`, `tests/test_engine.py`, `tests/test_post_install.py`, `tests/test_status.py`, `tests/test_version_cache.py`, `tests/test_deps.py`
- [x] A fixture/helper for constructing a `Tool` with a `kind="sdkman"` method plus a competing `kind="brew"` method (the groovy off-policy shape) — add if `test_ownership.py` lacks one for this dual-owner shape
- [x] A fixture reproducing the dangling-pnpm-shim shape (shim file present, `pnpm list --global` output not listing the package) for D-18 — new, mirroring the pending todo's live repro

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| Live proof against the real defects this phase fixes (skill_pack detection, sdkman version/ownership, kitty's silent no-method row, outdated-tool re-select no-op) | Phase goal ("Proven against the real defects below on a host that reproduces each one") | Unit tests prove the mechanism; the phase goal demands proof against a host that actually reproduces each original live defect — not satisfiable by mocked unit tests alone | Read-only production composition recorded in 16-16-SUMMARY.md. TUI states are the Phase 16 walkthrough rows below. | recorded |
| Phase 16 walkthrough (1): Owner reads `Homebrew ≠ policy` for groovy, gradle, maven, and java. `u` is pressed only on a current row. | D-02 | Rendered Owner cell, detail, and status line | `uv run python setup.py` (no flags). Find groovy/gradle/maven/java. Press `u` only on a row whose Ver cell shows it is current. Do not press `u` on an outdated row. | pending |
| Phase 16 walkthrough (2): springbootcli and sdkman show versions, never `no version`. | D-01 | Rendered Ver cell | Find springbootcli and sdkman. Read the versions. No install or update key. | pending |
| Phase 16 walkthrough (3): after a System-view wait, the AI view shows skill packs present, with hosts in Owner. | D-10 | Rendered Inst and Owner after the launch probe | The app opens on the System view. Wait a few seconds, then switch to the AI view (view navigation only). Find superpowers, ponytail, softaworks-agent-toolkit, and opengsd. | pending |
| Phase 16 walkthrough (4): kitty is selectable with Owner `own installer`; alacritty is dim with the immutable-host reason. | D-07, D-16 | Dim styling and detail sentence | Find kitty and alacritty. Browse only. | pending |
| Phase 16 walkthrough (5): execute preflight says already current. Exit key is esc. Enter is not pressed on the execute screen. | D-17 | On-mount preflight text | Select wezterm (or any current tool) and open the execute screen, read the preflight shown on mount, then leave with esc. Enter is not pressed on the execute screen. | pending |
| Phase 16 walkthrough (6): mmdc Inst is a red `!` only if the shim is still dangling. Browse only, no keypress. | D-18 | Rendered Inst mark | Find mmdc if its shim is still dangling. Host proof on 2026-10-10 read `broken=False` and `owner='brew'`, so the row may be absent. Browse only, no keypress. | pending |
| Phase 16 walkthrough (7): Doctor guidance names the kitty block and the guard offer. Exit key is esc. Enter is not pressed. | D-22 | Rendered guidance text | Open Doctor and read its guidance. Enter is not pressed (enter is Doctor's apply). Leave with esc. | pending |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [ ] Feedback latency < 300s — full suite observed `3395 passed, 5 skipped in 320.66s` on 2026-10-10 (over the 300s cap)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** map backfilled by plan 16-16 on 2026-10-10. Human walkthrough rows stay pending until end-of-phase review.
