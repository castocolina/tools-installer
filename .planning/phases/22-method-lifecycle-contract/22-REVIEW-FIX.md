---
phase: 22
fixed_at: 2026-11-04
review_path: .planning/phases/22-method-lifecycle-contract/22-REVIEW.md
iteration: 1
findings_in_scope: 23
fixed: 14
closed: 1
by_design: 3
residual: 5
status: all_fixed_or_decided
base: 67588cd
head_before_report: 05fdf0b
---

# Phase 22: Code Review Fix Report

Gates ran in the **main checkout** (no worktree). Every commit below passed `make validate`
(exit 0) and `make test` (exit 0) on the tree it was committed from. Final run:
**5577 passed, 4 skipped** (baseline at 67588cd: 5543 passed, 4 skipped). `make e2e` was
**not** re-run. C-02 changes how the pnpm group member is retired in the container (a fresh
`pnpm list -g` replaces the not-found string), so the next e2e run is the proof for that
path.

## Status table

| C-ID | Status | Commit | Test (RED → GREEN) |
|------|--------|--------|--------------------|
| C-01 | fixed | 3827623 | `test_engine::test_a_native_method_after_a_failed_method_fails_with_the_error_and_the_command`, `test_render::test_a_failed_row_with_a_native_handoff_shows_the_error_and_the_command` |
| C-02 | fixed (reinstall case residual) | 1be24cb | `test_app::test_a_manager_package_the_user_already_removed_runs_nothing_and_retires_the_receipt`, `…_still_listed_runs_its_uninstall`, `…_unreadable_listing_runs_the_uninstall_and_a_failure_keeps_the_receipt`, `…_group_member_pnpm_already_removed_is_removed` (rewritten), `test_ownership::test_manager_listing_asks_only_the_one_manager_a_kind_names` |
| C-03 | closed | 9cf3a69, 8417c5e | recorded `make e2e` exit 0 (22-13-SUMMARY D-2) |
| C-04 | fixed | 1be24cb | `test_app::test_a_pnpm_not_found_is_no_proof_without_a_readable_listing` |
| C-05 | by_design | — | ledger Q2 |
| C-06 | fixed | 17d2594 | `test_engine::test_a_tap_formula_brew_already_listed_writes_no_receipt`, `test_ownership::test_a_tap_formula_is_found_by_its_short_name_in_the_brew_listing` |
| C-07 | residual | 05fdf0b (shortcut comment) | — |
| C-08 | fixed | 1abe290 | `test_model::test_script_argv_refuses_an_elevation_command` (8 cases), `test_executors::test_no_registry_argv_starts_with_an_elevation_command` |
| C-09 | fixed | eef50dd | `test_model::test_config_paths_rejects_a_shared_well_known_dir` (10 cases), `…_keep_a_tool_dir_under_a_shared_root` |
| C-10 | fixed (partial; residual noted) | 804860d | `test_run::test_every_child_runs_without_askpass_brew_sudo_or_brew_autoremove`, `test_run::test_setup_applies_the_child_env_before_main_runs` |
| C-11 | fixed | 1d77027 | `test_update::test_a_declared_update_runs_the_declared_leaf_never_a_path_copy`, `…_whose_leaf_is_gone_runs_nothing` |
| C-12 | residual | — | — |
| C-13 | fixed | bd8e35c | `test_wizard_app::test_the_pnpm_group_warning_reads_the_frozen_decision` |
| C-14 | residual | — | — |
| C-15 | fixed | 6bf6e88 | `test_wizard_app::test_a_c_refusal_during_a_removal_shows_in_the_detail_bar` |
| C-16 | fixed | 4c073f1 | `test_version_cache::test_a_missing_cached_greedy_decodes_empty_and_a_malformed_one_unknown` |
| C-17 | fixed | d9683ad | `test_update::test_omz_update_runs_the_root_presence_reads_when_both_roots_exist`, `test_download::test_expand_script_token_resolves_zsh_when_the_default_dir_is_absent` (updated) |
| C-18 | fixed | 804860d | same two `test_run` tests as C-10 |
| C-19 | residual | — | — |
| C-20 | by_design | — | ledger "UI-SPEC open questions" + SPEC R6 shared-path edge |
| C-21 | by_design | 05fdf0b (shortcut comment) | — |
| C-22 | residual | — | — |
| C-23 | fixed | 6e5d3f9 | `test_container_e2e_receipts::test_every_array_expansion_survives_bash_3_2_under_set_u` |

## RED evidence (each test failed before its fix)

- C-01: the engine returned `MANUAL_REQUIRED`, not `FAILED`; the row detail was `download failed` with no command.
- C-02 / C-04: `AttributeError: installer.app has no attribute 'manager_listing'` in every new test (the import failed).
- C-06: a receipt was written for `anomalyco/tap/opencode`; ownership was `'unknown'`, not `'brew'`.
- C-08: all 8 `sudo`/`pkexec`/`doas`/`/usr/bin/sudo` cases DID NOT RAISE. The registry scan is a new guard and passes on today's registry.
- C-09: 9 of 10 entries DID NOT RAISE (`~/.local/share` was already refused as a harness-marker parent).
- C-10 / C-18: `ImportError: apply_child_env`; the `setup.py` `__main__` block lacked the call.
- C-11: ran bare `['t', 'upgrade']`; with the leaf gone the status was `updated`, not `failed`.
- C-13: the warning line was missing once the live state changed before the review.
- C-15: the detail bar kept the row text and the refusal was dropped.
- C-16: a malformed value decoded as `frozenset()`, not `None`.
- C-17: ran `$ZSH/tools/upgrade.sh`, not `~/.oh-my-zsh/tools/upgrade.sh`.
- C-23 (PT-07): 7 bare `"${arr[@]}"` expansions.

## Applied fixes

- **C-01**: at a native step after earlier failures, the ladder returns `FAILED` with those
  errors and keeps `handoff`/`manual_command`. The failed row reads `<error>; you run:
  \`<cmd>\``, `render_handoff` prints any outcome that carries a handoff, and the exit code
  is 1. Nothing runs sudo.
- **C-02 / C-04**: `ownership.manager_listing(kind)` queries one manager.
  `app.remove_tool`, shared by the CLI and the TUI, checks it before a manager uninstall. A
  readable listing without the package means no command runs, the receipt is deleted, and
  `already removed` is reported (the CLI prints `<id>: already removed`). An unreadable
  listing runs the previewed command, and a failure keeps the receipt (fail closed). The
  pnpm-only `ERR_PNPM_GLOBAL_PKG_NOT_FOUND` tolerance and its constant are deleted, and no
  manager error-string table was added. A conftest autouse fixture makes the listing
  unknown, so no test queries the host's brew, uv or pnpm.
- **C-06**: `ownership.listed_name(kind, package)` gives the last path segment for
  brew/cask. Both the engine's pre-install check and ownership's brew/cask candidates use it.
- **C-08**: `load_tools` refuses a script `remove`/`update` whose first word, or its
  basename, is sudo/pkexec/doas.
- **C-09**: refuses `~/.local/{bin,share,state}`, `~/.config/{systemd,autostart}` and any
  `~/Library/<dir>`, plus anything under `~/.local/bin`, `~/.ssh` or `~/.gnupg`. Entries at
  depth 1, such as `~/.config` and `~/.cache`, were already refused. All declared entries
  still load.
- **C-10 / C-18**: `run.apply_child_env(os.environ)` runs in `setup.py`'s `__main__`, next to
  `drop_project_venv_from_path`. It pops `SUDO_ASKPASS` and sets `HOMEBREW_NO_SUDO=1` and
  `HOMEBREW_NO_AUTOREMOVE=1`. Every CLI and TUI runner inherits the process environment, so
  brew and cask removals (and installer-run brew installs/cleanups) are covered without an
  `env` argv prefix. The previewed argv stays `brew uninstall <pkg>`.
  `HOMEBREW_NO_AUTO_UPDATE` was not added: `uninstall` is not an auto-update command
  (Homebrew `utils/auto-update.sh:144-150`), and setting it process-wide would change
  install freshness.
- **C-11**: a bare first word that names one of the method's declared leaves runs that
  leaf's absolute path. A declared leaf that is gone raises `UpdateError`, so nothing runs.
  `sdk`, `{omz_root}` and words that name no declared leaf (`brew update`) are unchanged.
  Deviation: the binding uses the **declared** leaf (re-checked as present), not a
  receipt-proven one. Ownership already proved this copy, and R2-01 (an installer copy
  found by its declared paths, with no receipt) would otherwise lose `u`. This closes the
  PATH-shadowing failure CR-11 describes.
- **C-13**: `pnpm_removal_packages` takes argvs. The TUI review passes
  `decision.argv.values()`, and the CLI passes the plan argvs.
- **C-15**: `_config_refused` shows the text in the detail bar during a removal
  (`ToolBrowser.show_detail`, renamed from `_show_detail`). `Removing…` keeps the status
  line.
- **C-16**: `greedy=_str_set(raw)`: a missing key reads as empty, and null or a malformed
  value reads as unknown, which forces a re-read.
- **C-17**: `_zsh_first_omz_root` is deleted, and `{omz_root}` resolves through
  `omz.omz_root`, the resolver presence and ownership already use. With only `$ZSH` present,
  `u` still runs `$ZSH/tools/upgrade.sh`. With both present, it upgrades `~/.oh-my-zsh` (the
  copy the row and receipt describe). **The SPEC R8 wording ("`$ZSH` when set") needs an
  amendment for the both-present case.** That is for the orchestrator; this run left SPEC
  unchanged.
- **C-23**: every array expansion in `container-e2e-verify.sh` uses
  `${arr[@]+"${arr[@]}"}`, and a test keeps new ones guarded. Shellcheck findings are
  unchanged: the same 3 pre-existing SC2016 infos.

## Residuals (with reasons)

- **C-02, reinstall case**: if the user removes the package and reinstalls it themselves,
  and no uninstall ran in between, the receipt still proves it and L1 still runs.
  `ManagerInventory` carries name→version only, and the receipt records no version or keg
  install time, so the inventory cannot tell the two cases apart. The option chosen keeps
  the receipt and retires it the moment any removal sees the package missing. It never
  retires a receipt without a readable listing. Upgrade path: record the keg's install
  time/version in a manager receipt and require a match before L1.
- **C-07**: the receipt records no size/hash for leaves, and the 22-03 type-only rule
  (ledger Q3) is kept for vendor-updated binaries. A `shortcut:` comment in
  `receipts._leaf_matches` names the limit.
- **C-10 (part)**: a vendor script that calls NOPASSWD `sudo` directly, outside Homebrew,
  is not stopped by an environment variable. It is only visible in the vendor script.
- **C-12**: the e2e harness still allows whole harness-marker dirs, and it does not assert
  absence for level-`none` receipts (oh-my-zsh, sdkman and the brew bootstrap survive by
  design). The D-2 empty-dir skip also hides an empty must-clear dir. Not changed, because a
  harness assertion cannot be verified without a container run, and an unverified one would
  risk the phase gate. The upgrade path: list the surviving receipts as a `TRACER_` line,
  then fail on any not in a hint-only set.
- **C-14**: the "Config kept" stat runs on the UI thread. This is an acknowledged 22-11
  deviation, LOW, and only matters for a HOME on a stalled network mount.
- **C-19**: a hand-edited receipt can add `/` as a tree, which widens `_leaf_matches`'
  lexical retarget rule. Exploiting it needs write access to the user's own receipts dir,
  and the worst case is unlinking a symlink.
- **C-22**: the per-install whole-inventory read costs about 1-3 s per manager-method tool.
  This is a performance issue, not a correctness one. `manager_listing(kind)` now exists as
  the narrower reader. Switching the engine to it changes the `read_inventory_fn` seam used
  by about 50 test sites.

## By design

- **C-05**: ledger Q2, "handoff ends the ladder; no silent switch to Homebrew".
- **C-20**: equal shared config entries are a recorded UI-SPEC/SPEC R6 case ("kept, also
  used by"). Refusing them at load would contradict that decision.
- **C-21**: UI-SPEC amendment 2026-11-04 keeps the vendor `remove` mechanism. A `shortcut:`
  comment in `uninstall._recipe_argv` names the decision.

---

_Fixed: 2026-11-04_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
