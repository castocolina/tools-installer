---
phase: 23
fixed_at: 2026-11-07
review_path: .planning/phases/23-configuration-as-a-lifecycle-step/23-REVIEW.md
iteration: 1
base: bb43f16
head: 8276273
findings_in_scope: 21
fixed: 20
by_design: 0
residual: 1
partial_residuals: 3
status: partial
verification: main checkout (workflow.use_worktrees not used; the orchestrator asked for the main checkout), scratch HOME only
final_make_test: "5819 passed, 4 skipped (coverage 96%+)"
---

# Phase 23: Code review fix report

The fixes follow the orchestrator decisions. Each fix was test-first: the new or changed
test ran RED before the code change, as recorded below. Each commit passed
`make validate && make test` (exit 0) on the exact tree it commits. No suppressions were
added, no `--no-verify` was used, and nothing ran against the real HOME. The user's real
`~/.myshellrc` and agent settings were not touched (mtimes predate this loop, and no
`~/.zshenv` was created). STATE.md, ROADMAP.md and RUN-LEDGER.md were not modified.

## Table

| C-ID | Status | Commit | Test (RED first) |
|------|--------|--------|------------------|
| C-01 | fixed | 4a918d6 | `test_vscode_lean_reverts_after_vscode_appends_a_user_key`, `test_opencode_and_a_created_claude_parent_revert_after_a_user_key_follows` (RED: "the edit broke the file") |
| C-02 | fixed | 150f5b9 | `test_revert_follows_the_recorded_file_not_the_one_resolved_now` (RED: "both … exist"), `test_a_recorded_file_that_is_gone_is_reported_and_no_other_file_is_touched` (RED: state `yours`) |
| C-03 | fixed | fe51919 | `test_a_post_run_sync_that_writes_reports_the_shell_lines`, `test_the_noninteractive_all_route_names_a_shell_write` (RED: no Shell line) |
| C-04 | fixed | 1f12f31 | `test_an_untrusted_ledger_is_kept_aside_and_blocks_every_write` (RED: apply succeeded over it), `test_an_untrusted_settings_ledger_reads_blocked` |
| C-05 | fixed | 067a485 | `test_an_unreadable_rc_is_reported_and_never_raises`, `test_every_route_survives_a_non_utf8_myshellrc`, `test_headless_launch_survives_a_non_utf8_myshellrc` (RED: UnicodeDecodeError) |
| C-06 | fixed | a928085 | `test_a_zshenv_step_whose_write_failed_fails_and_claims_nothing` (RED: row `done`), `test_a_zdotdir_zshenv_is_named_in_the_zsh_step` (RED: `~/.zshenv`) |
| C-07 | fixed | 6305779 | `test_a_hook_tool_that_recorded_no_host_is_registered_for_the_new_host` (RED: no register); `test_no_present_supported_host_runs_nothing` now pins the recorded empty list |
| C-08 | fixed | c843018 | `test_after_stop_no_hook_sweep_and_no_settings_write_run[2 shapes]` (RED: resynced) |
| C-09 | fixed (residual part) | 2371416 | `test_starship_in_policies_sets_and_restores_the_theme_like_the_install_yes` (RED: theme unchanged) |
| C-10 | fixed | fe51919 | `test_strip_only_never_writes_while_zsh_is_present`, `test_the_cli_uninstall_never_writes_a_shell_block_while_zsh_stays`, `test_build_app_wires_a_strip_only_terminal_closure_into_uninstall_inputs` (RED: ~/.zshenv created) |
| C-11 | fixed | fe51919 | `test_a_zsh_removal_stops_at_a_zshenv_warning` (RED: kitty stripped) |
| C-12 | fixed | 33ac074 | `test_jsonc_block_comments_never_reach_across_each_other` (RED: not valid JSONC) |
| C-13 | fixed | b4f0ab3 | `test_a_refusal_after_a_successful_unregister_forgets_the_hosts` (RED: hosts kept) |
| C-14 | residual | — | — |
| C-15 | fixed | f3225ee | `test_a_fifo_at_a_settings_path_is_refused_without_blocking` (RED: hung, killed by timeout) |
| C-16 | fixed | a19e9a4 | `test_hook_probe_before_requires_config_for_recorded_hosts`, `test_hook_probe_after_reports_a_file_still_naming_codegraph` (RED: SKIPPED, exit 0) |
| C-17 | fixed | e2e53ec | `test_the_desktop_shell_row_writes_environment_d` (second remove; RED by reading the code: the old `_remove` always reported "removed") |
| C-18 | fixed (residual part) | 0f13f63 | existing callers' tests (signature change: `ledger_summary`, `settings_change_lines`, `removal_change_lines`) |
| C-19 | fixed (by-design part) | 8276273 | `test_a_created_file_the_user_commented_is_kept_on_revert` (RED: file deleted) |
| C-20 | fixed | 6e1200a | `test_reapplying_the_installers_own_theme_is_not_reported_as_yours` (RED) |
| C-21 | fixed | 24e739a | `test_an_empty_file_a_bom_and_a_nested_toml_array_are_edited_not_refused` (RED: "empty file"); `test_a_toml_splice_never_lands_inside_an_array` replaces the old refusal pin |

## Deviations from the orchestrator decisions

1. **C-01: the `stranded` case is deleted, but one general check replaces it.**
   - JSONC accepts a trailing comma, so the re-parse fallback alone accepts a fragment cut
     that leaves `false,}`. The existing VS Code ai-off test goes RED on this.
   - The fast path is now taken only when the cut adds no blanked trailing comma
     (`_trailing_commas`). Otherwise the located member cut runs.
2. **C-02: a recorded path is followed only if the agent's settings can live there.**
   - The allowed paths are the adapter path, plus `opencode.jsonc` for opencode.
   - This keeps `test_a_tampered_ledger_never_removes_a_user_key` true. A forged ledger
     entry naming another file is refused and never reverted.
   - When the recorded file is gone, the revert returns `RECORDED_FILE_GONE`, keeps the
     entries, and touches nothing else. The preview names the missing file the same way.
3. **C-04: the TUI catalog row also shows the untrusted-ledger reason.**
   - The row shows it the way O7 does.
   - `ledger_summary` (the preview) still reads an untrusted ledger as "no entries". The
     revert reports the block.
4. **C-05: two more launch reads were made non-raising.**
   - The two read-only launch probes of the same file, `bundle_marker_present` and
     `omz._record`, no longer raise. Without that, the TUI still crashed after the strip
     was fixed.
5. **C-03: the Shell lines arrive as one line, not as a separate Shell section.**
   - The lines come from `terminal_shell.sync_message(report_changes=True)`:
     `Shell: <.zshenv> now exports SHELL=<zsh>; new terminals start with it` and
     `Shell: kitty now starts zsh`.
   - The CLI prints them after the run report. The update route adds them to its detail.
     The interactive close adds them to its notice line, in the warn colour, because that
     seam has a single notice channel.
6. **C-11: the stop is reported as a warning, not as an error or exit 1.**
   - The line is `zshenv: <reason>; kitty, WezTerm and Konsole left as they are`.
   - `terminal_sync_warning` never flips the primary operation. The zsh removal itself
     already succeeded when the sync runs.
7. **C-18 uses a `refactor(23):` prefix.** It removes dead code and changes no behaviour.

## Residuals (with reasons)

- **C-14 (CR-11): no handoff line when a hook tool's executable is unproven.**
  - This is the accepted shortcut from planner sign-off 7 (R1-40).
  - The removal still succeeds and the receipt goes. A handoff line naming
    `codegraph uninstall --target … --keep-cli` is left for when the receipt learns the
    moved binary path.
- **C-09 (CR-08), residual part: the installer theme claim survives a full uninstall.**
  - The `omz-theme` claim block in `~/.myshellrc` and the installer-written `ZSH_THEME`
    line stay after a full uninstall or after Oh-My-Zsh plugins are turned off.
  - Removing the inserted line would bring back the bare `%m%# ` prompt this phase set
    out to fix. Starship's own on, off and removal are symmetric now.
- **C-18 (CR-15/PT-09), residual and by-design parts:**
  - `_first_line_of` takes text, `first_line` takes an exception: not duplicates.
  - `_HERDR_TARGETS` is herdr's own vendor contract and stays separate from codegraph's.
  - The `herdr-integration` hook has no registry tool yet (the Phase 24 shape). Its
    per-host retry is untestable until a tool uses it.
- **C-19 (PT-05), by-design part: a comment on the installer's own member line goes with
  that member.**
  - `test_a_member_cut_without_its_fragment_takes_its_comma_and_keeps_comments` pins this.
  - That comment describes our key. The created-file deletion that lost user comments is
    fixed.

## Commits

4a918d6, 33ac074, 150f5b9, 1f12f31, 067a485, fe51919, a928085, 6305779, c843018,
2371416, 6e1200a, a19e9a4, b4f0ab3, e2e53ec, 0f13f63, 24e739a, f3225ee, 8276273.

_Fixed: 2026-11-07_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
