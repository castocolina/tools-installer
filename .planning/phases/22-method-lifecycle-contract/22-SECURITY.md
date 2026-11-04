---
phase: "22"
slug: method-lifecycle-contract
status: verified
verdict: SECURED
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_total: 51
mitigated: 50
accepted: 1
open: 0
threats_open: 0
threats_open_nonblocking: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
audited_head: d4bcfd8
created: "2026-11-04"
---

# Phase 22 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Where the register comes from:** the `<threat_model>` blocks of 22-01..22-13-PLAN.md. They hold
T-22-01..T-22-50 with no gaps. T-22-45 appears in 22-03 and 22-05 and counts once. T-22-SC
appears in every plan and counts once. That is 51 threats.

- Severity: 1 critical, 28 high, 16 medium, 6 low.
- Disposition: 50 mitigate, 1 accept, 0 transfer.

**Method:** ASVS L1 (the mitigation is in the cited code) plus a passing test for each one.
Every test the register names was located and run read-only at `d4bcfd8`:
`uv run pytest <76 node ids> -q --no-cov -n 0` gave 118 passed (with parametrized cases) and 0 failed.
A second run of the review-fix tests the residuals depend on gave 25 passed (C-02, C-04, C-08,
C-09, C-10/C-18, C-11). No install, removal, `make setup`/`fix`/`uninstall` or `make e2e` was run.

**Test-name drift (not gaps):**
- T-22-06 names `test_tree_and_leaf_artifacts_with_extra_fields_are_rejected`, but no test has
  that name. The covering test is `test_tree_and_leaf_artifacts_with_a_hash_or_key_are_rejected`
  (22-03-SUMMARY deviation 3). The register says `_read_artifact` "rejects extra fields", which
  is inaccurate: the reader ignores unknown keys. A tree or leaf with a hash or key is rejected.
  The threat (a receipt retyping a leaf into a recursive delete) is closed by the (path, type)
  pair intersection, not by the reader.
- T-22-37 names `test_a_failed_cli_removal_is_reported_and_exits_non_zero`. That test was split
  into `test_a_failed_cli_removal_is_reported_and_keeps_its_receipt` and
  `test_a_failed_cli_removal_exits_non_zero`.

## Threat Verification

| ID | Sev | Disposition | Evidence (code) | Test |
|----|-----|-------------|-----------------|------|
| T-22-01 | high | mitigate | `installer/model.py:526` `_config_path_flaw` (harness markers from `HARNESS_MARKER_DIRS` :200, outside `~/`, depth < 2, shared well-known dirs per C-09) | `tests/test_model.py:1785` test_config_paths_rejects_a_harness_dir, `:1826` …outside_two_levels_of_home, test_config_paths_rejects_a_shared_well_known_dir (10 cases) |
| T-22-02 | high | mitigate | `installer/model.py:232` `_SCRIPT_ARG_RE`, `:583` refuses unknown `{root}` (only `SCRIPT_ROOTS` :118), `:599-618` refuses sudo/pkexec/doas heads (C-08); no `sh -c` in the script update path (`installer/update.py:436-451`) | `tests/test_model.py:1915` test_script_tokens_reject_an_unknown_placeholder, test_script_argv_refuses_an_elevation_command (8 cases) |
| T-22-03 | high | mitigate | `installer/model.py:507` refuses `""`/`.`/`..`/NUL parts; `:621` `_script_paths_refusal` keeps `paths` under HOME or a root | `tests/test_model.py:1934` test_script_paths_stay_under_home, `:1959` test_writable_prefix_is_an_absolute_path |
| T-22-32 | high | mitigate | `installer/model.py:564` `_refuse_config_overlap` | `tests/test_model.py:1848` test_config_paths_refuse_an_overlap_across_tools |
| T-22-04 | critical | mitigate | native executors gone; `installer/executors.py:613-615` keeps only display strings; `needs_manual` (`executors.py`) returns a `ManualHandoff`; engine returns before any runner call (`installer/engine.py:250-261`) | `tests/test_executors.py:163` test_no_argv_literal_starts_with_an_elevation_command (AST, installer/ + setup.py), test_no_registry_argv_starts_with_an_elevation_command, `tests/test_engine.py:163` test_a_native_method_is_handed_off_with_zero_runner_calls |
| T-22-05 | low | mitigate | `installer/render.py:340-354` `render_handoff`: `sanitize_log_line` + `markup=False, soft_wrap=True` | `tests/test_render.py:1297`, `:1313` |
| T-22-06 | high | mitigate | `installer/uninstall.py:112-134` `_receipt_proof` keeps the (path, type) pair the registry names; `installer/download.py:339` types `tree` only for an entry ending in `/` | `tests/test_receipts.py:1483` test_tree_and_leaf_artifacts_with_a_hash_or_key_are_rejected (see drift note) |
| T-22-07 | medium | mitigate | `installer/receipts.py:638-656` `_leaf_matches` lexical containment in the receipt's trees | `tests/test_receipts.py:1415` test_a_retargeted_link_outside_the_tree_is_not_removable |
| T-22-33 | high | mitigate | `installer/receipts.py:257-279` `record(preexisting=)`, None fails closed; snapshot taken before the method (`installer/engine.py:264-270`) | `tests/test_receipts.py:1506`, `:1550` |
| T-22-45 | medium | mitigate | `installer/ownership.py:156` `_INSTALLER_KINDS` includes `script`; `:1091` picks the artifact candidate's method | `tests/test_ownership.py:397` test_a_script_tools_declared_path_keeps_its_script_method, `tests/test_update.py:1952` (refresh → resolve_owner → run) |
| T-22-08 | high | mitigate | `installer/uninstall.py:334-378` `_remove_dir`: exclusive quarantine rename, re-verify inside it, put back on mismatch or `BaseException` | `tests/test_uninstall.py:2253`, `:2271` |
| T-22-09 | high | mitigate | `installer/executors.py` `needs_manual` → MANUAL for an unwritable `writable_prefix`; plan time through `installer/session.py:690` | `tests/test_plan.py:1141` test_an_unwritable_prefix_is_planned_manual_and_nothing_runs |
| T-22-10 | medium | mitigate | `installer/engine.py:250` re-checks with the live `executors.prefix_writable` right before the method | `tests/test_engine.py:210` |
| T-22-34 | medium | mitigate | `installer/executors.py:623-641` owner comparison on the nearest parent; any `OSError` → False | `tests/test_executors.py:83` |
| T-22-11 | high | mitigate | `installer/update.py:436-451` literal argv through `expand_script_token`; unresolved token raises before running; `sdk` via `executors.sdk_pipeline` with `shlex.join` (`installer/executors.py:546-553`); bare first word bound to the declared leaf (`update.py:457-470`, C-11) | `tests/test_update.py:1928`, `:1816`, test_a_declared_update_runs_the_declared_leaf_never_a_path_copy, test_a_declared_update_whose_leaf_is_gone_runs_nothing |
| T-22-12 | medium | mitigate | `installer/update.py:270` `pinned_method` in `update_refusal`; `installer/catalog_tui.py:677` before the lock | `tests/test_update.py:2036`, `tests/test_catalog_tui.py:2289` |
| T-22-13 | high | mitigate | `installer/uninstall.py:228-238` `_manager_argv`: receipt kind + package must equal a declared method's package | `tests/test_app.py:4681`, `:4695` |
| T-22-14 | high | mitigate | `installer/app.py:591-595` a `CommandError` returns before any delete; receipt kept | `tests/test_app.py:4535` test_a_failing_remove_deletes_nothing |
| T-22-15 | medium | mitigate | `installer/app.py:563-572` `remove_tool` re-plans with `verify=True` and refuses a changed path or argv; shared by CLI (`:744`) and TUI (`:903`) | `tests/test_app.py:4570`, `:5010` |
| T-22-35 | high | mitigate | `installer/uninstall.py:254` `_recipe_argv` needs `plan.by_tool[tool.id]` non-empty | `tests/test_app.py:4841` |
| T-22-36 | medium | mitigate | `installer/app.py:532-544` `removal_order`, used at `:657` and `:902` | `tests/test_app.py:4875`, `:5038` |
| T-22-37 | medium | mitigate | `installer/app.py:757-759,798` returns failed ids; `setup.py:1343` `return 1 if failed else 0` | `tests/test_app.py:5070`, `tests/test_setup.py:1370` |
| T-22-16 | medium | mitigate | `setup.py:756,868,1325` `runner=run_captured` (stdin `/dev/null`, new session, stderr in `detail`) | `tests/test_run.py:183`, `tests/test_setup.py:1350` test_both_removers_bind_run_captured |
| T-22-46 | high | mitigate | `installer/app.py:568` with an argv every previewed path must still be removable; `:606-607` any refusal fails the tool before `receipts.delete` | `tests/test_app.py:4617`, `:4100`, `:5210` test_a_refused_removal_keeps_the_config |
| T-22-47 | high | mitigate | `installer/uninstall.py:268-276` first word bound to exactly one receipt-proven leaf's absolute path, else `()` | `tests/test_app.py:4495`, `:4589` |
| T-22-49 | medium | mitigate | `installer/engine.py:356-369` `_package_already_there` (no reader or unreadable → already there), `:319` writes no receipt unless the previous one proved it; `setup.py:783` binds `read_inventory_fn=read_inventory` | `tests/test_uninstall_e2e.py:379`, `:423`; plus C-06 tap-name tests |
| T-22-17 | medium | mitigate | `installer/ownership.py:1523-1525` native removal commands are None | `tests/test_ownership.py:1921`, `:1931` |
| T-22-18 | low | mitigate | house path: `sanitize_log_line` (`installer/wizard_app.py:647,958,1216`), cells as `Text`, `detail_is_markup=False` | covered by `tests/test_wizard_app.py:8567`, `:8894` |
| T-22-38 | high | mitigate | `installer/version_status.py:1473-1490` broken receipt stays BROKEN, all-gone receipt retired; level `none`, no argv | `tests/test_version_status.py:6509` |
| T-22-19 | high | mitigate | `paths` are evidence only: deletion needs a receipt record (`installer/receipts.py:257-279`) and a pair match (`installer/uninstall.py:128-134`); citations in `installer/registry.toml` comments | `tests/test_receipts.py:1506`; container check in 22-13 |
| T-22-48 | high | mitigate | no registry method declares `remove` (`grep -nE '^\s*remove\s*=' installer/registry.toml` = 0); opencode has `paths` + `update` only (`registry.toml:1570-1571`); SPEC R1 amended (22-SPEC.md:37,144) | registry tests in `tests/test_registry.py` (whole file passes) |
| T-22-39 | high | mitigate | pnpm/bun/Volta/fnm stanzas declare executables as leaves only | `tests/test_registry.py:2802`, `:2832` |
| T-22-50 | medium | mitigate | narrowest vendor trees (cursor-agent `versions/`, codex `releases/`, claude whole dir by its documented uninstall) | `tests/test_registry.py:2777` test_no_declared_path_is_or_contains_a_harness_marker |
| T-22-20 | medium | mitigate | process control: vendor scripts downloaded to fresh `mktemp -d`, read with grep/sed only (22-08-SUMMARY:270; 22-REVIEWS cycle 3 note) | n/a (process; no code path fetches vendor scripts for reading) |
| T-22-21 | high | mitigate | `installer/app.py:831-840` `_config_step` deletes only a path equal to a catalog tool's expanded `config_paths`; `installer/uninstall.py:467-469` symlink unlinked | `tests/test_app.py:5325`, `tests/test_uninstall.py:2401` |
| T-22-22 | high | mitigate | `installer/app.py:841-844` every catalog owner removed and listing it; `perform_uninstall(catalog=)` is required (`:865`) | `tests/test_app.py:5238`, `:5280` |
| T-22-40 | high | mitigate | `installer/uninstall.py:452-472` resolved parent inside real HOME and outside every resolved marker; resolved target refused when a marker is it or under it | `tests/test_uninstall.py:2331`, `:2363` |
| T-22-23 | high | mitigate | `delete_config_path` has one caller, `installer/app.py:846` (`_config_step`, reached only from `perform_uninstall`); `run_uninstall` (`:614-798`) never calls it | `tests/test_app.py:5392` test_the_cli_never_deletes_config |
| T-22-24 | high | mitigate | flags intersected with marks on repaint; `installer/wizard_app.py:1050` `config_split` keeps a path an unflagged declarer needs | `tests/test_wizard_app.py:8331`, `:8195` |
| T-22-41 | high | mitigate | `installer/wizard_app.py:1559` decision built before the modal; `:1679-1685` the callback hands that object to `_apply_removal`, which never rebuilds it (`:1689`) | `tests/test_wizard_app.py:8212` |
| T-22-42 | medium | mitigate | `installer/wizard_app.py:1490-1493` `clear_transient` clears `_config_on` | `tests/test_wizard_app.py:8466` |
| T-22-25 | low | mitigate | same house path as T-22-18 | `tests/test_wizard_app.py:8567` |
| T-22-26 | high | mitigate | review and decision from the one `_decision` call (`installer/wizard_app.py:1654-1677`); scroll body | `tests/test_wizard_app.py:8504`, `tests/test_layout_80x20.py:457`, `tests/test_wizard_app.py:8212` |
| T-22-27 | medium | mitigate | `Text` pieces + `sanitize_log_line` on every data piece (`installer/wizard_app.py:647,958,1216`) | `tests/test_wizard_app.py:8567`, `:8894` |
| T-22-28 | low | mitigate | `installer/update.py:187` flag on cask argv only; `:354` package from registry ownership tested against the tracked greedy set | `tests/test_update.py:469` |
| T-22-29 | low | mitigate | brew JSON parsers fail closed to None | `tests/test_manager_versions.py:324` |
| T-22-43 | low | mitigate | `installer/version_status.py:141` `_EMPTY_OUTDATED.greedy=None`; `:1903-1905` publishes only a non-None greedy; `:1715` `_partial_manager_failure` | `tests/test_version_status.py:6648`, `:6667` |
| T-22-30 | high | mitigate | `scripts/container-e2e-verify.sh:71` sources the detector, `:813` `trap 'ct rm -f …' EXIT`, `:84` `exec_tester`; `make e2e` was not run by this audit | harness self-tests in `tests/test_container_e2e_receipts.py` |
| T-22-44 | high | mitigate | `setup.py:1343` exit 1; `scripts/container-e2e-verify.sh:687` `assert_removed_receipts_gone`; recorded paths checked whatever the baseline holds (`:614-618`) | `tests/test_container_e2e_receipts.py:831`, `:816` |
| T-22-31 | medium | mitigate | `scripts/container-e2e-verify.sh:604` `must_clear_paths`; must-clear wins over allowed prefixes | `tests/test_container_e2e_receipts.py:760`, `:798`, `:853`, `:810` |
| T-22-SC | high | accept | no plan adds a package (see Accepted Risks AR-22-01) | `git diff 8fc4ab5^ HEAD -- pyproject.toml uv.lock`: only `pytest-xdist`/`execnet` (dev), from commit 51b0d29, outside every phase-22 plan |

## Accepted Risks

| ID | Source | Sev | Risk | Why accepted | Upgrade path |
|----|--------|-----|------|--------------|--------------|
| AR-22-01 | T-22-SC | high | supply chain of npm/pip/cargo installs | No phase-22 plan installs or adds a package. The only lockfile change in the window is the dev-only `pytest-xdist` 3.8.0 + `execnet` 2.1.2 from PyPI (51b0d29, a test-infra commit outside the plans). It is not a runtime path. | Register a T-xx-SC entry in the phase that owns 51b0d29 if one is audited |
| AR-22-02 | REVIEW-FIX C-02 (reinstall case) | low | The user removes a manager package and then reinstalls it themselves, with no removal in between. The receipt still proves it, so L1 `brew/uv/pnpm uninstall` runs on the user's copy. | The command is shown in the review before the confirm. The package is one the registry declares. `ManagerInventory` has no version or keg time to tell the two cases apart. The receipt is retired as soon as any removal sees the package missing. | Record the keg install time/version in manager receipts and require a match before L1 |
| AR-22-03 | REVIEW-FIX C-07 | low | A regular-file leaf is proven by type alone, so another installer's file at a declared leaf path (shared bin dir such as `~/.local/bin`) is unlinked | It is a declared path that this installer's receipt recorded, and the worst case is an executable the other installer can restore. Vendor self-updates rewrite leaves (ledger Q3). `shortcut:` comment at `installer/receipts.py:645-648`. | Record size/hash for leaves that every installer-run update re-takes |
| AR-22-04 | REVIEW-FIX C-10 (part); 22-REVIEWS cycle 3 residual 1 | medium | A manager's or vendor script's own `sudo` (for example a cask `uninstall` stanza) runs if the user has NOPASSWD sudo | No installer argv starts with sudo/pkexec/doas (AST test, registry load refusal C-08). `apply_child_env` (`installer/run.py:32-43`, `setup.py:1489`) sets `HOMEBREW_NO_SUDO=1`, `HOMEBREW_NO_AUTOREMOVE=1` and drops `SUDO_ASKPASS`. `run_captured` gives stdin `/dev/null` and no tty, so a password prompt fails closed. Only NOPASSWD defeats this, and that is elevation inside the manager, which the installer cannot see. **Needs explicit user sign-off against the zero-sudo rule.** | If a root-free cask removal must be guaranteed, pre-scan the cask's `uninstall` stanza (`brew info --json=v2 --cask`) for sudo-requiring keys and hand those off as MANUAL |
| AR-22-05 | REVIEW-FIX C-12 | low | e2e harness false-pass gaps: whole harness-marker dirs allowed, level-`none` receipts not asserted absent, the empty-dir skip hides an empty must-clear dir | It is a verification-harness weakness, not a product path. Non-empty must-clear paths still win over every allowlist entry (T-22-31 tests). | Emit surviving receipts as a `TRACER_` line and fail on any not in a hint-only set |
| AR-22-06 | REVIEW-FIX C-14 | low | the "Config kept" stat runs on the UI thread and can hang on a stalled network HOME | Availability only, a recorded 22-11 deviation | Move the stat into the refresh worker |
| AR-22-07 | REVIEW-FIX C-19 | low | A hand-edited receipt adding `/` as a tree widens `_leaf_matches`' retarget rule (`receipts.drifted` uses the receipt's own trees, `installer/receipts.py:661`), so a retargeted proven leaf link is still unlinked | Needs write access to the user's own receipts dir. The deleted object is still a registry-declared leaf, and only a symlink is unlinked, never followed. | Intersect the receipt's trees with the registry's `artifact_paths` before `_leaf_matches` |
| AR-22-08 | REVIEW-FIX C-22 | low | whole-inventory read per manager-method install (1-3 s) | Performance, not correctness | Switch the engine seam to `manager_listing(kind)` |
| AR-22-09 | 22-REVIEWS cycle 3 residual 2 | low | A declared `update` whose first word names no declared leaf (`brew update`) runs from PATH | C-11 binds every bare word that names a declared leaf (`installer/update.py:457-470`). Removal is not affected, and ownership gates `u`. | Bind manager update heads to the proven manager executable |
| AR-22-10 | 22-REVIEWS R1-11 (open item) | low | An all-gone receipt reads MISSING, not BROKEN | Signed off in ledger row 256. The tool is not removable and nothing re-runs in either reading. | none |

Recorded by design in 22-REVIEW-FIX, not risks: C-05 (handoff ends the ladder), C-20 (equal shared config entries, SPEC R6), C-21 (vendor `remove` mechanism kept, `shortcut:` at `installer/uninstall.py:246-248`).

## Unregistered Flags

None blocking. The SUMMARY `## Threat Flags` sections that exist (22-01, -03, -04, -05, -07, -08) map to registered IDs or say "none". Review-fix surface checked here:
- C-02 `manager_listing` retires a receipt only on a readable listing that lacks the package. An unreadable listing runs the previewed command and keeps the receipt on failure (`installer/app.py:576-582`). This is fail-closed and needs no new ID.
- C-08 and C-10 add mitigations, not surface.
- Informational: `pytest-xdist` dev dependency (see AR-22-01).

## Audit Trail

| Date | Auditor | Head | Result |
|------|---------|------|--------|
| 2026-11-04 | gsd-security-auditor (Claude) | d4bcfd8 | SECURED: 50 mitigated, 1 accepted, 0 open; 10 accepted residuals; 118 + 25 targeted tests passed |
