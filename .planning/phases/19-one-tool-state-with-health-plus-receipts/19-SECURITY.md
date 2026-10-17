---
phase: "19"
slug: one-tool-state-with-health-plus-receipts
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_total: 139
threats_closed: 139
threats_open: 0
threats_open_nonblocking: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
audited_head: e7753f5
created: "2026-10-17"
---

# Phase 19 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

The register comes from the `<threat_model>` blocks of 19-01..19-46-PLAN.md: T-19-01..T-19-138 with no duplicate ids and no gaps, plus T-19-SC, which appears in every plan and is counted once (139 total; severity 1 critical, 22 high, 74 medium, 42 low; disposition 132 mitigate, 7 accept, 0 transfer). Later gap plans repeat earlier rows; the latest plan's disposition wins. Superseded mitigations: T-19-104 (`_safe_key` alone) is replaced by T-19-121 (`_key_file` containment); T-19-81 and the dir-identity part of T-19-91 (st_dev/st_ino) are replaced by the binding L-19-31 key-file proof (T-19-102/T-19-103). Each `mitigate` threat was checked in the code at the cited line and against a named test that exists. The 239 cited test names were run on this tree (`uv run --frozen pytest --no-cov -n 4 -k <names> tests/`): 391 passed, exit 0. The configured level is ASVS L1; the critical and high deletion and update paths were traced further. The audited tree is e7753f5, whose code equals d49e7b2 (`git diff d49e7b2 e7753f5 -- installer setup.py scripts tests` is empty).

---

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Receipt files → removal | `~/.local/state/tools-installer/receipts/<id>.json` is user-writable; a receipt is never trusted alone: removal intersects it with the registry's `artifact_paths` by (path, type) and re-proves every artifact at deletion time |
| Filesystem state → health/removal | installed files, dirs and links can change between preview and delete; files are re-hashed, dirs are proven by one contained key file and removed through a quarantine rename + re-verify |
| Host CLIs (rpm, brew, uv, pnpm, claude, volta) → state | output is parsed by path with closed name sets, bounded reads and fail-closed "not checked" notes; argv is always a tuple, never shell text |
| Config files (hooks, skill locks, terminal configs, installed_plugins) → state | read through the non-blocking capped reader; FIFO, oversize, deep nesting and non-object documents are "not checked" |
| Published state → TUI actions | one snapshot reader; actions re-resolve ownership and re-check receipts before any mutation |
| Test suite → developer host | scratch HOME per test, receipts/skill/bin sandboxes, PATH strip of host toolchain dirs, and a `GuardedPopen` tripwire for node-family binaries and brew |

---

## Threat Register

*Status: closed. Short paths: `rc` = `installer/receipts.py`, `un` = `installer/uninstall.py`, `vs` = `installer/version_status.py`, `up` = `installer/update.py`, `sl` = `installer/skill_lifecycle.py`, `ct` = `installer/catalog_tui.py`, `cf` = `tests/conftest.py`, `e2e` = `scripts/container-e2e-verify.sh`, `tr` = `tests/test_receipts.py`, `tu` = `tests/test_uninstall.py`, `tvs` = `tests/test_version_status.py`, `tsl` = `tests/test_skill_lifecycle.py`, `tce` = `tests/test_container_e2e_receipts.py`. Other modules are `installer/<file>`, other tests `tests/<file>`. Line numbers cite e7753f5.*

| Threat ID | Category | Component | Severity | Disposition | Mitigation evidence (code; test) | Status |
|-----------|----------|-----------|----------|-------------|----------------------------------|--------|
| T-19-01 | DoS | `receipts.read` corrupt/huge/nested/grown file | medium | mitigate | rc:171 `read_capped(cap)` → atomic.py:118-147 reads cap+1 on the fd; rc:176 RecursionError caught; :182, :597-600 bool rejected; :603-655 per-type fields. tr::test_read_fails_closed[*], ::test_read_fails_closed_on_a_file_that_grew_after_the_size_check, ::test_read_fails_closed_on_recursion_error | closed |
| T-19-02 | Tampering | symlink at receipt path | low | mitigate | rc:117-121. tr::test_write_refuses_a_symlinked_receipt | closed |
| T-19-03 | Tampering | tool id as filename | low | mitigate | rc:100-104 TOOL_ID_RE fullmatch before any path. tr::test_read_rejects_an_unsafe_id, ::test_write_rejects_an_unsafe_id, ::test_receipt_ids_follow_the_registry_rule | closed |
| T-19-04 | Tampering | in-place rewrite keeps proof | medium | mitigate | rc:550-575 stat shortcut, re-hash on stat change, `rehash=True` bypass; un:97, :521. tr::test_matches_rejects_a_rewritten_file, ::test_rehash_true_always_hashes, ::test_matches_rehashes_a_touched_file_once | closed |
| T-19-05 | Tampering | tests writing real receipts dir | medium | mitigate | cf:232-244 sandbox; cf:139-146 session fingerprint of the real receipts dir. tr::test_suite_sandbox_redirects_receipts | closed |
| T-19-06 | Tampering | traversal name in artifact_paths / install / update | medium | mitigate | download.py:226-234 `_is_single_name`; :266-268; app guard :275-282; :328-330, :377-379 raise before any write. test_download.py::test_artifact_paths_rejects_bad_member_basenames, ::test_install_download_rejects_an_unsafe_bin_name, ::test_update_download_rejects_an_unsafe_bin_name | closed |
| T-19-07 | EoP | second path formula drifting | medium | mitigate | download.py:247-291 one formula, read by rc:271, un:53/:103/:124/:175, vs:1306. test_download.py::test_artifact_paths_matches_install_placement_for_every_registry_method | closed |
| T-19-08 | Spoofing | pending shown as ✓ | medium | mitigate | vs:171-183 declaration order is precedence, CHECKING first; vs:206-238. test_tool_health.py::test_tool_health_precedence_table, ::test_health_declaration_order_is_precedence | closed |
| T-19-09 | Spoofing | planted rpm owner lines | medium | mitigate | install_ownership.py:240-249 `_PACKAGE_NAME_RE`; :496 argv lists; :503-538 path-keyed. test_install_ownership.py::test_native_index_drops_invalid_package_names | closed |
| T-19-10 | DoS | is_our_shim reads 150 MB | low | mitigate | guards.py:276-299 8192-byte `read_capped`. test_guards.py::test_is_our_shim_never_reads_a_large_file | closed |
| T-19-11 | Tampering | positional owner parse | medium | mitigate | install_ownership.py:451-458, :523-536. ::test_native_index_parses_by_path_not_position, ::test_native_index_fails_closed_for_an_uncollected_path | closed |
| T-19-12 | Spoofing | Volta claim for non-shim | low | mitigate | ownership.py:802-830 needs `volta-shim`; up:284-293 refuses and only displays. test_ownership.py::test_volta_shim_resolves_to_volta, ::test_overlapping_volta_dir_without_a_shim_keeps_the_installer_owner | closed |
| T-19-13 | EoP | host-setup owner → mutating update | medium | mitigate | up:284-293, :310-329 unsupported before the runner; ownership.py:632, :937-975. test_update.py::test_update_refuses_volta_cleanly, ::test_update_refuses_host_setup_pnpm_cleanly | closed |
| T-19-14 | Spoofing | broad `uv tool dir` prefix | low | accept | AR-19-02 | closed |
| T-19-15 | Tampering | dry run rewrites terminal configs | high | mitigate | terminal_shell.py:279-288 `write=`; :334; :429-431; :435. test_terminal_shell.py::test_dry_run_leaves_home_byte_identical, ::test_dry_run_zsh_absent_reverts_nothing | closed |
| T-19-16 | ID | drift names config paths | low | accept | AR-19-03 | closed |
| T-19-17 | EoP | argv injection via plugin id/scope | high | mitigate | sl:33-34 regex + CLAUDE_SCOPES; sl:62-94; sl:897-925 tuple argv. tsl::test_hostile_ids_never_reach_argv, ::test_claude_scope_outside_the_closed_set_is_unknown | closed |
| T-19-18 | Tampering | arbitrary projectPath | medium | mitigate | sl:865-870 one absolute existing dir. tsl::test_project_copy_without_a_valid_project_path_has_no_step | closed |
| T-19-19 | DoS | huge/nested Claude JSON | low | mitigate | sl:35-36, :67 1 MiB cap, :72 RecursionError; sl:831-846 64 KiB + RecursionError. tsl::test_claude_unparseable_json_is_unknown[over-1-mib], ::test_unreadable_installed_plugins_keeps_the_reason_without_a_step[over-64-kib] (no deep-nesting fixture; see Residuals) | closed |
| T-19-20 | Spoofing | project/disabled copy reads installed | medium | mitigate | sl:97-102. tsl::test_claude_enabled_user_scope_canonical_is_present, ::test_claude_project_scope_only_is_absent, ::test_claude_two_enabled_user_entries_for_the_canonical_id_is_absent | closed |
| T-19-21 | Tampering | overtaken pass overwrites newer | high | mitigate | vs:1644-1652 epoch gate; vs:1668-1677 per-record `seq`. tvs::test_overtaken_pass_publishes_nothing, ::test_overtaken_by_invalidate_publishes_nothing, ::test_a_raced_refresh_publishes_no_state, ::test_partial_pass_merges_into_the_full_snapshot | closed |
| T-19-22 | ID | torn read of published map | medium | mitigate | vs:922-927, :1677 new dict per commit; vs:960-970 one reference read. tvs::test_the_service_publishes_one_snapshot_of_tool_states | closed |
| T-19-23 | Spoofing | planted brew on PATH | low | accept | AR-19-04 | closed |
| T-19-24 | DoS | cache write aborts pass | low | mitigate | vs:1677 swap first, vs:1695-1700 OSError → warning. tvs::test_cache_save_failure_keeps_states_and_sets_warning | closed |
| T-19-25 | Tampering | receipt records an uncreated path | high | mitigate | rc:268-287 only `artifact_paths`, missing dropped; download.py:291; un:99-105. tr::test_record_skips_missing_artifacts, ::test_record_writes_download_artifacts, test_engine.py::test_receipt_per_kind | closed |
| T-19-26 | Repudiation | silent or stale receipt after a failed write | low | mitigate | rc:288-300; engine.py:252-261; up:350-353. tr::test_record_failure_removes_the_previous_receipt, test_engine.py::test_receipt_write_failure_keeps_installed | closed |
| T-19-27 | EoP | manager update adopts foreign pkg | medium | mitigate | up:346-353. test_update.py::test_brew_update_rewrites_only_an_existing_receipt | closed |
| T-19-28 | Tampering/EoP | tampered receipt names ~/.ssh | critical | mitigate | un:83-105 receipt ∩ same-kind `artifact_paths` by (path, type); only deletion path un:504-557, called from app.py:618, :707. tu::test_tampered_receipt_path_is_never_removable, ::test_run_uninstall_uses_receipt_proof, ::test_perform_uninstall_reproves_per_tool | closed |
| T-19-29 | Tampering | swap between preview and delete | high | mitigate | un:546 `verify=True` → un:97 `drifted(rehash)`. tu::test_remove_proven_rehashes_before_deleting, ::test_drifted_receipt_artifact_outside_the_authorized_set_blocks_the_tool | closed |
| T-19-30 | Tampering | corrupt receipt → layout proof | medium | mitigate | un:96-98, :162-171 no fallback. tu::test_corrupt_receipt_is_unproven_without_layout_fallback | closed |
| T-19-31 | Repudiation | receipt deleted while its file exists | low | mitigate | un:554-556. tu::test_remove_proven_keeps_the_receipt_when_a_delete_fails, ::test_remove_proven_removes_and_deletes_the_receipt | closed |
| T-19-32 | DoS | unbounded/symlink repo walk | medium | mitigate | sl:325-329, :374-416. tsl::test_repo_walk_is_capped, ::test_repo_walk_bounds_queue_and_entries, ::test_repo_walk_rejects_a_symlinked_root, ::test_repo_walk_never_follows_symlinks | closed |
| T-19-33 | EoP | step argv from repo/JSON text | medium | mitigate | sl:499-520; model.py:180, :676-680 X.Y.Z pin. tsl::test_install_step_cwd_is_validated | closed |
| T-19-34 | Tampering | detection deletes global machinery | high | mitigate | sl:523-609 read-only; sl:499-504 builds, never runs, the uninstall step. tsl::test_global_leftover_detection_writes_nothing, ::test_hook_scan_writes_nothing | closed |
| T-19-35 | Spoofing | shim makes missing tool present | medium | mitigate | guards.py:338-356; status.py:74-76, :129-143. test_status.py::test_installer_shim_is_never_presence, tvs::test_pass_looks_through_the_redirect_shim | closed |
| T-19-36 | Spoofing | version probe runs volta-shim | low | mitigate | vs:338-348 and forwards. tvs::test_volta_tool_version_probes_the_unresolved_path, ::test_resolve_status_forwards_the_unresolved_path_for_volta_and_host_setup | closed |
| T-19-37 | DoS | N native queries per pass | medium | mitigate | install_ownership.py:421-475, :503-538; vs:1554-1565. tvs::test_pass_makes_one_rpm_path_query_for_many_native_tools, ::test_pass_reads_rpm_ostree_status_once | closed |
| T-19-38 | Spoofing | ✓ for pending/stale | medium | mitigate | ct:127-131; vs:960-970. test_catalog_tui.py::test_health_cell_is_checking_before_the_first_pass | closed |
| T-19-39 | Tampering | UNAVAILABLE row selectable | low | mitigate | ct:375, :501-509. ::test_unavailable_state_dims_and_blocks_selection | closed |
| T-19-40 | ID | refresh error as markup | low | mitigate | ct:479-482 → ui_common.py:82-85 plain `Text`. ::test_refresh_error_shows_the_retry_copy (no markup fixture; see Residuals) | closed |
| T-19-41 | Spoofing | foreign file adopted | high | mitigate | vs:1267-1269, :1282-1323 raw only, exact digest; rc:316-324. tvs::test_pass_adopts_a_raw_binary_by_cached_digest, ::test_archive_and_non_raw_methods_are_never_digest_adopted, ::test_adoption_makes_no_network_call | closed |
| T-19-42 | Tampering | adoption overwrites concurrent receipt | medium | mitigate | rc:316-324 re-check under `_WRITE_LOCK`. tr::test_adopt_refuses_when_a_receipt_appeared, ::test_adopt_refuses_when_the_file_changed | closed |
| T-19-43 | Tampering | edited cache digest | low | accept | AR-19-05 | closed |
| T-19-44 | DoS | AppImages hashed every pass | low | mitigate | vs:940-941, :1310-1320 memo. tvs::test_adoption_mismatch_is_hashed_once, ::test_adoption_memo_is_keyed_by_the_expected_digest | closed |
| T-19-45 | Tampering | Rich markup in reason/step | medium | mitigate | ct:656-661 `escape`. ::test_detail_escapes_reasons_and_steps | closed |
| T-19-46 | EoP | `u` on stale/pending ownership | medium | mitigate | ct:798-807; up:496-505. ::test_u_on_a_pending_row_says_checking, test_update.py::test_update_service_fresh_ownership_overrides_cached | closed |
| T-19-47 | Tampering | pass rewrites terminal configs | high | mitigate | setup.py:906-911 `write=False`. test_setup.py::test_terminal_drift_pass_writes_nothing | closed |
| T-19-48 | EoP | unsafe pnpm repair argv | medium | mitigate | vs:648, :651-682. tvs::test_incomplete_pnpm_group_is_misconfigured | closed |
| T-19-49 | DoS | harness CLIs probed inside pass | medium | mitigate | vs:1018 only; vs:1095 once per pass. test_catalog_tui.py::test_skill_probe_runs_once_across_three_catalog_entries, tvs::test_terminal_drift_seam_runs_once_per_pass | closed |
| T-19-50 | Repudiation | warning hidden or spilled | medium | mitigate | tool_browser.py:82-93, :376-394. test_layout_80x20.py::test_catalog_tiers_show_all_legend_and_detail_rows_at_80x20, test_tool_browser.py::test_detail_health_block_is_cut_at_two_rows | closed |
| T-19-51 | Tampering | markup breaks split / plain adapter parsed | low | mitigate | tool_browser.py:383-384. ::test_detail_of_a_plain_text_adapter_keeps_brackets_literal | closed |
| T-19-52 | Tampering | stale presence/ownership aims an action | high | mitigate | vs:960-970; setup.py:1132 → vs:1364-1405. test_update.py::test_update_service_fresh_ownership_overrides_cached, test_execute_screen.py::test_classify_reads_the_state | closed |
| T-19-53 | EoP | repair triggered by receipt drift | medium | mitigate | execute_screen.py:549-556. ::test_classify_reads_the_state | closed |
| T-19-54 | Spoofing | brew appears mid-session | low | accept | AR-19-06 | closed |
| T-19-55 | Tampering | e2e host test touches real HOME | medium | mitigate | tce:113-127, :130-145; cf:150-172. tce::test_assert_receipt_functions_in_bash, ::test_pre_uninstall_check_requires_binary_and_valid_receipt | closed |
| T-19-56 | EoP | shell injection via probe id | low | mitigate | e2e:20-21 constant; e2e:443 regex. tce::test_probe_tool_is_raw_download_first_on_fedora | closed |
| T-19-57 | Tampering | unsafe registry id | low | mitigate | model.py:187, :745; rc:102. test_model.py::test_load_tools_rejects_an_unsafe_tool_id, ::test_every_registry_tool_id_is_a_safe_filename | closed |
| T-19-58 | DoS | duplicate passes / joiner hang | medium | mitigate | vs:1508-1531. tvs::test_identical_passes_share_one_flight, ::test_join_never_crosses_an_invalidate, ::test_a_failed_shared_pass_raises_in_every_joiner | closed |
| T-19-59 | ID | test service reads real HOME | medium | mitigate | cf:271-290. tvs::test_suite_sandbox_redirects_skill_home | closed |
| T-19-60 | DoS | huge/nested/swapped hook config | medium | mitigate | sl:315-316, :452-469, :472-496. tsl::test_hook_config_fails_closed[*], ::test_hook_walk_bound_is_inconclusive, ::test_oversized_hook_config_is_never_read | closed |
| T-19-61 | Spoofing | usrmerge alias | medium | mitigate | install_ownership.py:440-448, :523-535. ::test_native_index_joins_usrmerge_aliases | closed |
| T-19-62 | Repudiation | unseen cache-save failure | low | mitigate | ct:425, :441, :453-454, :470-471, :484-485. ::test_cache_save_warning_reaches_the_status_line | closed |
| T-19-63 | Tampering | update uses launch-time platform | medium | mitigate | setup.py:1124; up:465-469, :546. test_update.py::test_update_service_reads_the_live_platform | closed |
| T-19-64 | Spoofing | leftover presence copy | medium | mitigate | no `set_installed`/`_BROKEN_MARK` in installer/. test_catalog_tui.py::test_catalog_screen_has_no_installed_parameter | closed |
| T-19-65 | Tampering | unpinned/global handoff text | medium | mitigate | registry.toml:3486, :3498; sl:518. test_registry.py::test_opengsd_handoff_text_matches_scope_and_pin, tsl::test_no_step_installs_globally | closed |
| T-19-66 | Repudiation | e2e skip / never-installed probe | low | mitigate | e2e:257-298, :304-332, :540-554. tce::test_receipt_check_is_skipped_for_other_categories, ::test_receipt_checks_are_wired_into_the_passes | closed |
| T-19-67 | ID | test reads real ~/.local/bin | medium | mitigate | cf:247-268. test_locations.py::test_suite_sandbox_redirects_the_default_bin_dir | closed |
| T-19-68 | ID | service presence via real bin | medium | mitigate | vs:893-895, :980. tvs::test_service_default_bin_dir_is_sandboxed | closed |
| T-19-69 | DoS | nested non-reentrant lock | high | mitigate | rc:52-59, :115-155, :316-324. tr::test_adopt_completes_without_deadlock | closed |
| T-19-70 | Tampering | overlapping Volta dir → installer owner | medium | mitigate | ownership.py:648-654. test_ownership.py::test_volta_shim_wins_over_an_overlapping_installer_candidate | closed |
| T-19-71 | Tampering | marketplace_remove orphans a copy | medium | mitigate | sl:917-925. tsl::test_marketplace_is_kept_when_a_copy_has_no_step, ::test_marketplace_is_kept_while_another_plugin_uses_it | closed |
| T-19-72 | Tampering | stale snapshot / mixed platform | medium | mitigate | vs:1537-1539, :1413-1424, :744. tvs::test_has_brew_is_reread_each_pass, ::test_a_pass_uses_one_platform_throughout | closed |
| T-19-73 | EoP | receipt type → rmtree | high | mitigate | un:99-105 (path, kind); un:504-529. tu::test_receipt_type_cannot_turn_a_file_path_into_a_directory, ::test_remove_proven_refuses_a_retyped_artifact | closed |
| T-19-74 | Spoofing | digest compared on other bytes | high | mitigate | vs:1313-1321; rc:316-324 one `fingerprint(rehash=True)`; rc:227-247. tvs::test_adoption_binds_the_digest_to_the_adopted_bytes, tr::test_adopt_records_the_verified_fingerprint_without_a_second_one | closed |
| T-19-75 | Repudiation | failed secondary probe erases a fact | medium | mitigate | vs:665-667, :1094-1107, :1132-1141, :1182, :1336-1356. tvs::test_terminal_drift_failure_is_a_not_checked_note, ::test_inconclusive_claude_listing_is_a_not_checked_note, ::test_unreadable_pnpm_inventory_is_a_not_checked_note | closed |
| T-19-76 | Spoofing | stale VERSION reads installed | medium | mitigate | sl:419-429. tsl::test_stale_version_beside_unrelated_skills_is_not_installed | closed |
| T-19-77 | Spoofing | unprobed pack shows ✓ | medium | mitigate | vs:731, :757-758, :1230. tvs::test_tool_state_forwards_checking_facts | closed |
| T-19-78 | Repudiation | failed listing read as absent | medium | mitigate | sl:784-791, :941-954. tsl::test_four_install_pack_with_an_unreadable_listing_is_an_unknown_host | closed |
| T-19-79 | Repudiation | unreadable config read as no leftover | medium | mitigate | sl:345-363, :472-496, :550; vs:1182. tsl::test_unlistable_machinery_dir_is_unchecked_not_a_leftover, ::test_unreadable_gsd_core_is_unchecked | closed |
| T-19-80 | Spoofing | non-object hook document | medium | mitigate | sl:493-494. tsl::test_hook_config_fails_closed[array_settings, array_hooks_json] | closed |
| T-19-81 | EoP | stale receipt proves a re-created dir | high | mitigate (superseded by L-19-31) | rc:471-489, :540-544; un:483-497 re-hash in quarantine. tr::test_dir_with_a_changed_or_missing_key_file_does_not_match, tu::test_replaced_dir_artifact_is_not_removable, ::test_remove_proven_refuses_a_dir_recreated_after_verification | closed |
| T-19-82 | DoS | NUL/unencodable path | medium | mitigate | rc:620-627, :362, :490, :546. tr::test_nul_artifact_path_is_unreadable, tvs::test_nul_receipt_path_never_aborts_refresh, tu::test_nul_receipt_path_never_aborts_plan_removal | closed |
| T-19-83 | Spoofing | memo reused against another digest | medium | mitigate | rc:54-59, :568-575. tr::test_rehash_memo_compares_each_receipts_digest | closed |
| T-19-84 | EoP | `.planning` symlink as cwd | medium | mitigate | sl:393-395. tsl::test_repo_walk_rejects_a_symlinked_planning_dir | closed |
| T-19-85 | Tampering | unreadable dir read as empty install | medium | mitigate | sl:432-449, :570-587. tsl::test_unreadable_install_dirs_are_not_checked_not_empty | closed |
| T-19-86 | Spoofing | duplicate canonical user installs | low | mitigate | sl:885-905. tsl::test_two_disabled_canonical_user_entries_get_no_enable_step, tvs::test_claude_duplicates_reach_the_state | closed |
| T-19-87 | Spoofing | shim read as installed pnpm | medium | mitigate | status.py:74-76, :139-143. test_status.py::test_installer_shim_on_path_is_never_presence | closed |
| T-19-88 | Repudiation | receipt claims a smoke that never ran | low | mitigate | engine.py:51-59, :246-258. test_engine.py::test_app_receipt_records_smoke_only_with_a_cli | closed |
| T-19-89 | ID | tests read real declared locations | medium | mitigate | cf:215-229. test_locations.py::test_registry_pass_reads_declared_locations_from_the_scratch_home, ::test_suite_home_is_a_per_test_scratch_dir | closed |
| T-19-90 | Tampering | unquoted path in generated shell | low | mitigate | tce:228-230, :298 `shlex.quote`. tce::test_uv_stub_survives_a_spaced_interpreter_path, ::test_assignment_survives_a_spaced_workspace | closed |
| T-19-91 | EoP | file/link replaced by a dir → rmtree | high | mitigate (dir-identity part superseded by L-19-31) | un:504-529 the authorized type picks the operation; rc:536-547. tu::test_remove_paths_unlinks_only_what_its_type_authorizes, ::test_remove_proven_refuses_a_file_replaced_by_a_dir_after_verification | closed |
| T-19-92 | Spoofing | cache-seeded present shown as ✓ | medium | mitigate | vs:1214-1232, :1134-1141. tvs::test_stale_cached_present_is_checking_not_ok, ::test_seeded_skill_hosts_are_a_note | closed |
| T-19-93 | Tampering | skill worker overwrites newer facts | medium | mitigate | vs:1047-1065. tvs::test_skill_rebuild_never_rereads_project_facts, ::test_skill_rebuild_after_a_newer_pass_keeps_its_facts | closed |
| T-19-94 | Spoofing | unassessed terminal reads OK | low | mitigate | vs:1351-1356. tvs::test_terminal_warning_is_a_not_checked_note | closed |
| T-19-95 | DoS | FIFO at plugins/hook/receipt file | medium | mitigate | atomic.py:118-147; sl:479, :833-837; rc:171. tsl::test_installed_plugins_fifo_never_blocks, ::test_hook_config_fifo_is_not_checked, tr::test_receipt_read_never_blocks_on_a_fifo | closed |
| T-19-96 | DoS | inaccessible receipts dir | medium | mitigate | rc:332-346; callers un:162, vs:1267. tr::test_receipt_exists_treats_an_unreadable_dir_as_present, tvs::test_inaccessible_receipts_dir_never_aborts_refresh, tu::test_inaccessible_receipts_dir_never_aborts_plan_removal | closed |
| T-19-97 | Tampering | pass retires a proving receipt / adopts | medium | mitigate | rc:317, :349-383. tr::test_all_gone_needs_every_artifact_gone, ::test_retire_refuses_a_replaced_receipt, tvs::test_artifactless_receipt_is_never_retired, ::test_partially_gone_receipt_is_unproven_not_broken | closed |
| T-19-98 | DoS | DuplicateKey during a rebuild | medium | mitigate | ct:106-114, :360-361, :489-492, :569. ::test_status_view_survives_a_publication_mid_rebuild | closed |
| T-19-99 | Tampering | update erases drift evidence | high | mitigate | up:505-520 in `run`; both routes call it (ct:854, execute_screen.py:790). test_update.py::test_update_service_refuses_a_drifted_receipt, test_execute_screen.py::test_drifted_receipt_update_is_refused_per_tool | closed |
| T-19-100 | Tampering | manager update rewrites installer receipt | medium | mitigate | up:346-349. test_update.py::test_manager_update_keeps_an_installer_receipt | closed |
| T-19-101 | EoP | pi hint without `--ignore-scripts` | medium | mitigate | up:310-329. test_update.py::test_host_setup_update_hint_is_the_reviewed_handoff | closed |
| T-19-102 | DoS | st_dev reassignment breaks receipts | high | mitigate | rc:1-16, :471-489 no dev/ino; rc:603-655 old shape unreadable. tr::test_dir_recreated_with_the_same_key_file_matches, ::test_old_shape_dir_artifact_is_unreadable | closed |
| T-19-103 | EoP | stale receipt proves a different dir | high | mitigate | rc:540-544, :555-557; un:484. tr::test_dir_with_a_changed_or_missing_key_file_does_not_match[rewritten, removed, symlinked], tu::test_replaced_dir_artifact_is_not_removable | closed |
| T-19-104 | Tampering | forged key hashes outside the dir | medium | mitigate (superseded by T-19-121) | rc:386-401, :472, :646; rc:421-433. tr::test_unsafe_dir_keys_never_fingerprint, ::test_link_key_is_the_member_inside_the_dir | closed |
| T-19-105 | Tampering | writing inside a .app bundle | medium | mitigate | rc:46-47, :436-442 read only. tr::test_record_keys_each_dir_by_its_key_file[app] | closed |
| T-19-106 | Tampering | update over a vendor-updated dir | low | accept | AR-19-07 | closed |
| T-19-107 | Tampering | dir swapped before rmtree | high | mitigate | un:457-501. tu::test_remove_paths_refuses_a_dir_replaced_after_its_final_check | closed |
| T-19-108 | Tampering | same-length bytes with restored mtime | high | mitigate | un:521; rc:564-565. tu::test_remove_proven_rehashes_a_file_swapped_after_verification | closed |
| T-19-109 | DoS | captured dir lost | medium | mitigate | un:446-454, :487-500. tu::test_remove_paths_keeps_a_captured_dir_it_cannot_put_back | closed |
| T-19-110 | Tampering | quarantine collides with `.old` | low | mitigate | un:108-111, :470-476. tu::test_dir_removal_leaves_no_quarantine_behind | closed |
| T-19-111 | Tampering | real pnpm read as absent | medium | mitigate | status.py:132-137. test_status.py::test_real_pnpm_behind_the_redirect_shim_is_presence | closed |
| T-19-112 | ID | inherited overrides reach real HOME | low | mitigate | cf:206-211. test_locations.py::test_inherited_location_overrides_are_cleared | closed |
| T-19-113 | DoS | FIFO at shim/terminal/skill lock | medium | mitigate | guards.py:286; terminal_shell.py:265; sl:718. test_guards.py::test_is_our_shim_never_blocks_on_a_fifo, test_terminal_shell.py::test_dry_run_never_blocks_on_a_fifo_config, tsl::test_skills_lock_fifo_never_blocks | closed |
| T-19-114 | Repudiation | one unlistable runtime hides another | low | mitigate | sl:571-587. tsl::test_unreadable_runtime_never_hides_another_runtimes_empty_install | closed |
| T-19-115 | Repudiation | preview promises a refused update | low | mitigate | execute_screen.py:552-556, :564. ::test_drifted_tool_is_refused_before_the_run_starts, ::test_broken_tool_with_no_reason_is_still_refused | closed |
| T-19-116 | Tampering | spaced workspace splits `cd` | low | mitigate | e2e:307-308, :323. tce::test_pre_uninstall_check_survives_a_spaced_workspace | closed |
| T-19-117 | DoS | full disk leaves packs CHECKING | medium | mitigate | vs:1032-1046. tvs::test_skill_cache_save_failure_still_settles_the_packs | closed |
| T-19-118 | Tampering | failed invalidate keeps stale flags | low | mitigate | vs:1075-1083. tvs::test_failed_invalidate_save_still_reprobes_the_skills | closed |
| T-19-119 | DoS | partial pass replaces pack scan | low | mitigate | vs:929-931, :1056-1062, :1678-1681. tvs::test_partial_pack_pass_keeps_every_packs_scan | closed |
| T-19-120 | Tampering | ambiguous Claude gets a third copy | medium | mitigate | vs:1121-1131. tvs::test_ambiguous_claude_duplicates_never_get_a_partial_install_step | closed |
| T-19-121 | EoP | key escapes the dir via an intermediate symlink | high | mitigate | rc:404-418, :476, :543; un:484 checks under the captured root. tr::test_key_through_an_escaping_symlink_is_no_proof[abs, rel], ::test_key_through_a_symlink_that_stays_inside_still_proves, tu::test_remove_paths_refuses_a_replacement_keyed_through_an_escaping_symlink, ::test_plan_removal_never_proves_a_dir_whose_key_escapes | closed |
| T-19-122 | DoS | loop or dangling key component raises | low | mitigate | rc:416-417. tr::test_key_through_a_symlink_loop_never_raises | closed |
| T-19-123 | DoS | tests reach host node/brew (fork bomb) | high | mitigate | cf:37-39, :49-108 GuardedPopen per test, :177-187, :212 PATH strip. test_sandbox.py::test_host_toolchain_dirs_are_off_path, ::test_a_node_family_binary_outside_tmp_is_never_run, ::test_assert_not_host_toolchain_only_guards_the_named_programs | closed |
| T-19-124 | DoS | script calls bare node / absolute brew | medium | mitigate | cf:177-212; e2e:25, :170, :321, :344 `BREW_BIN`; tce:256-262 stub. tce::test_extracted_functions_never_name_the_host_brew | closed |
| T-19-125 | Repudiation | later save clears the skill warning | low | mitigate | vs:933-934, :1038-1044, :1688-1703. tvs::test_a_version_pass_persists_unsaved_skill_answers_before_clearing_the_warning | closed |
| T-19-126 | Spoofing | shim under an alias spelling | low | mitigate | guards.py:325-331, :352-354. test_guards.py::test_look_through_shim_matches_the_shim_dir_by_resolved_path, ::test_real_binary_drops_every_spelling_of_the_managed_dir | closed |
| T-19-127 | DoS | malformed skill lock | medium | mitigate | sl:724-729. tsl::test_skills_lock_deep_nesting_or_bad_bytes_is_unknown | closed |
| T-19-128 | DoS | every layout member hashed each pass | medium | mitigate | rc:495-518. tr::test_fingerprint_hashes_an_unchanged_file_once_per_session, ::test_dir_key_file_is_hashed_once_per_session | closed |
| T-19-129 | Tampering | memo digest reaches a receipt | medium | mitigate | rc:282, :319 `rehash=True`. tr::test_record_and_adopt_never_trust_the_memo | closed |
| T-19-130 | Tampering | BROKEN rule drifts between callers | low | mitigate | rc:583-594; callers vs:1275, up:516. tr::test_broken_drift_skips_dirs_and_never_hashes_their_key_file | closed |
| T-19-131 | DoS | Ctrl+C strands an install | medium | mitigate | un:483-497. tu::test_remove_paths_puts_the_tree_back_when_interrupted[*], ::test_an_interrupted_removal_that_cannot_put_back_names_the_quarantine | closed |
| T-19-132 | ID | unlisted quarantine sibling | low | mitigate | un:114-133, :191-195, :404-408; app.py:585, :597. tu::test_a_leftover_quarantine_sibling_is_listed_to_remove_yourself | closed |
| T-19-133 | Tampering | auto-delete of an unverified leftover | medium | mitigate | listed only; un:546-549 deletes only `fresh.artifacts`. tu::test_a_leftover_quarantine_sibling_is_listed_to_remove_yourself | closed |
| T-19-134 | DoS | `reasons[0]` on a reason-less BROKEN state | low | mitigate | ct:808-812. test_catalog_tui.py::test_u_on_a_broken_row_without_a_reason_still_refuses | closed |
| T-19-135 | Tampering | file/dir digest parse diverges | low | mitigate | rc:636-642. tr::test_old_shape_dir_artifact_is_unreadable, ::test_reader_keeps_only_each_types_fields | closed |
| T-19-136 | DoS | rc gets `eval "$( shellenv)"` | medium | mitigate | e2e:169-186 host-expanded prefix. tce::test_write_tester_path_hands_the_selected_brew_to_the_tester_shell | closed |
| T-19-137 | DoS | `Path.resolve` loop raises RuntimeError | medium | mitigate | guards.py:326, :330, :352-353 `os.path.realpath`; cf:177-187. test_guards.py::test_real_binary_survives_a_looping_path_entry, test_sandbox.py::test_the_path_strip_survives_a_looping_entry | closed |
| T-19-138 | Tampering | memoized preview digest used as deletion proof | low | mitigate | un:181-183 `rehash=verify`. tu::test_remove_proven_rehashes_a_receiptless_dir_key_file_at_deletion_time, ::test_remove_proven_hashes_a_dir_key_file_twice_not_three_times | closed |
| T-19-SC | Tampering | npm/pip/cargo installs | high | accept | AR-19-01 | closed |

---

## Accepted Risks Log

| Risk ID | Threat | Rationale | Plan |
|---------|--------|-----------|------|
| AR-19-01 | T-19-SC | No package installs: `git diff --stat 5e4bfa7..HEAD -- pyproject.toml uv.lock` is empty (5e4bfa7 is the parent of the first 19-01 commit). | every plan |
| AR-19-02 | T-19-14 | A uv-owned update still needs the uv inventory to list the package, and the `uv tool upgrade` argv names only that package. | 19-05 |
| AR-19-03 | T-19-16 | `drifted` holds terminal names only (terminal_shell.py:458, :479, :488). | 19-06 |
| AR-19-04 | T-19-23 | Same trust as the launch-time `which("brew")`; brew methods run only after the user selects and confirms. | 19-08 |
| AR-19-05 | T-19-43 | The cache is user-owned like the files it describes; adoption only makes a user-deletable file removable, and removal still intersects `artifact_paths` (un:99-105). | 19-14 |
| AR-19-06 | T-19-54 | Same as AR-19-04, for brew appearing mid-session. | 19-18 |
| AR-19-07 | T-19-106 | Binding L-19-31: dir drift is not update-refused; the row says `not proven` (vs:1277-1279); file and link drift stay refused (rc:583-594, up:509-516). test_update.py::test_dir_drift_does_not_block_an_update, tvs::test_dir_drift_is_unproven_not_broken. | 19-32 |

---

## Residuals and Deferred Items (no register change)

- Test gaps, verified by reading the code: T-19-19 has no deep-nesting fixture for the Claude listing (sl:72) and installed_plugins (sl:844) RecursionError catches; T-19-40 has no refresh-error fixture containing markup.
- T-19-124: the GuardedPopen limit (no inspection of shell scripts or `shell=True`) is documented in the cf:56-61 docstring without the literal `shortcut:` tag.
- L-19-31 residual: a dir re-created with a byte-identical key file counts as the same software; a vendor-updated `.app` stays not removable until reinstall.
- T-19-129: the pass's layout proof and `_adopt`'s pre-check use the memo; the under-lock re-fingerprint catches a swap. T-19-131: SIGKILL or power loss leaves the quarantine sibling, which is listed for the user.
- Accepted / deferred review items (not register threats): G15, G21/WR-03 (Phase 20 D-14), IN-02/03/06 (Phase 25), P19-07 residual, IN3-04 (cosmetic).

---

## Unregistered Flags

None. Only 19-12-SUMMARY.md has a `## Threat Flags` section; it says "None" and maps to T-19-35, T-19-36 and T-19-37.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-17 | 139 | 139 | 0 | gsd-security-auditor (Claude Opus 5.5), ASVS L1, block_on high, HEAD e7753f5 (code = d49e7b2); 391 cited test items passed |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-17
