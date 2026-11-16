---
phase: 23-configuration-as-a-lifecycle-step
verified: 2026-11-07T12:00:00Z
status: passed
score: 6/6 must-haves verified
covered_files: [".planning/phases/23-configuration-as-a-lifecycle-step/23-01-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-01-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-02-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-02-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-03-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-03-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-04-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-04-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-05-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-05-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-06-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-06-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-07-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-07-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-08-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-08-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-09-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-09-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-10-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-10-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-11-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-11-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-12-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-12-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-13-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-13-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-14-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-14-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-15-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-15-SUMMARY.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-16-PLAN.md",".planning/phases/23-configuration-as-a-lifecycle-step/23-16-SUMMARY.md","installer/agent_env.py","installer/agent_settings.py","installer/app.py","installer/atomic.py","installer/engine.py","installer/env_redirect.py","installer/execute_screen.py","installer/locations.py","installer/model.py","installer/omz.py","installer/policy.py","installer/post_install.py","installer/postinstall.py","installer/prompt.py","installer/receipts.py","installer/registry.toml","installer/render.py","installer/run.py","installer/session.py","installer/shellrc.py","installer/terminal_shell.py","installer/tweaks.py","installer/uninstall.py","installer/update.py","installer/version_status.py","installer/wizard_app.py","scripts/container-e2e-verify.sh","setup.py"]
covered_digest: "v4:sha256:dd29b879c937692aedf011045db2733693981200290e3ed7d6b8f49fa62cbeff"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "the installer does not install or register rtk (SC1 parenthetical)"
    reason: "The rtk hook is removed in Phase 23; the user's 2026-11-02 scope decision leaves removal of already-shipped catalog entries to a later phase the user creates (never removed on the agent's own initiative)"
    accepted_by: "user (scope decision 2026-11-02)"
    accepted_at: "2026-11-02T00:00:00Z"
deferred:
  - truth: "The herdr hook reads the one agent-host list for a real installed herdr (SC1 'codegraph, graphify and herdr hooks')"
    addressed_in: "Phase 24"
    evidence: "Phase 24 SC1: 'In a container, herdr installs, its integrations register for the present agent hosts, and uninstall leaves herdr integration status clean'. herdr has no registry entry yet; the `herdr-integration` HookPair exists and dispatches through run_postinstall over present_harnesses."
re_verification:
  date: 2026-11-15
  head: 024817d3
  previous_status: human_needed
  previous_score: 6/6
  method: "container UAT on Fedora 44 (ti-uat-23-fedora, removed), TUI driven through a herdr tab, 4352 phase tests green at HEAD"
  gaps_closed:
    - "H1 container run on a post-fix tree: TUI install/remove of zsh, starship, fzf, zoxide, codex, claude at HEAD (scratchpad/uat/23-reverify/02-17)"
    - "H4 settings revert with the real claude and codex CLIs: byte-identical (15-byte-compare.txt)"
    - "H5 layout of the Phase 23 surfaces: tests/test_layout_80x20.py green; the Phase 23 run options and shell-init modal were removed by 23.2 (TUNE-01/02)"
    - "H9 rtk parenthetical: registry.toml has no rtk entry since 23.1"
    - "herdr deferred item: registry entry herdr with postinstall = herdr-integration exists (Phase 24)"
  gaps_remaining: []
  regressions: []
  owner_confirmation_needed: [H2, H3, H6, H8]
  deferred_macos: [H7]
  refresh_2026_11_15:
    date: 2026-11-15
    head: c76a9e2b
    suite: "make validate && make test at HEAD c76a9e2b: 7676 passed, 6 skipped in 57.05s, coverage 96.07%"
    phase_tests: "own test files from this report's evidence run with uv run pytest -n 0 --no-cov: all passed"
    verified_commit: f2cdd0ec
    changed_files: "installer/app.py installer/shellrc.py installer/wizard_app.py"
    dropped_covered_files: "none"
    must_haves: "re-checked: unchanged. the strip_block blank-line fix (0e8cf604) and the uninstall PATH-entry fix (d113b87f) only change what is removed on uninstall; shellrc apply_block, the config lifecycle and its idempotence are unchanged (tests/test_shellrc.py and the 4 other files are green). the 80x20 layout fix (a8c37dc2) only reflowed widgets and added height guards."
  refresh_2026_11_15b:
    date: 2026-11-15
    head: 1cc6953e
    suite: "make validate && make test at HEAD 1cc6953e: 7679 passed, 6 skipped in 57.04s, coverage 96.09%"
    phase_tests: "own test files from this report's evidence run with uv run pytest -n 0 --no-cov: all passed"
    verified_commit: ed04c454
    changed_files: "installer/wizard_app.py"
    dropped_covered_files: "none"
    must_haves: "re-checked: unchanged. 7e9f2edb and 42ed8cd4 (merge 1cc6953e) only cap the status line at four rows, end the Policies Effect column and the Schedules detail in an ellipsis, and move cut_rows/Rows into ui_common (installer/ui_common.py, tool_browser.py, wizard_app.py, tests/test_layout_80x20.py, tests/test_schedules_view.py); layout and status-line code only, no behavior contract changed; this phase's test files are green."
  refresh_2026_11_16:
    date: 2026-11-16
    head: a2e68cf3
    suite: "make validate && make test at HEAD a2e68cf3: 7662 passed, 6 skipped in 60.05s, coverage 96.20%"
    phase_tests: "own test files from this report's evidence run with uv run pytest -n 0 --no-cov at HEAD: all passed; deleted test files dropped: none"
    verified_commit: b4d0cde9
    changed_files: "installer/agent_env.py installer/app.py installer/engine.py installer/execute_screen.py installer/locations.py installer/model.py installer/omz.py installer/post_install.py installer/receipts.py installer/run.py installer/session.py installer/shellrc.py installer/terminal_shell.py installer/update.py installer/version_status.py installer/wizard_app.py setup.py"
    dropped_covered_files: "none"
    must_haves: "re-checked: unchanged. Phase 25 (Lean) moved or deleted code (host_setup and sensitive-action retirements, compose.py, wizard_app.py split into ten modules); 25-VERIFICATION, 25-SECURITY and 25-UAT prove behaviour preserved (AST-identical moves, byte-identical 80x20 screens, real install and uninstall); this phase's surviving test files are green; the keyed sensitive prompts artifact in installer/post_install.py superseded by Phase 25 D-10/D-11 (SENSITIVE_PROMPTS and SENSITIVE_POST_INSTALL_ACTIONS were empty, retired)."
human_verification:
  - test: "Run `make e2e` (Fedora podman, disposable container) on HEAD a30bb2f"
    expected: "Every TRACER_* line OK, including TRACER_HOOKS_RECORDED / TRACER_HOOKS_UNREGISTERED_OK and the TRACER_SETTINGS_* write/revert lines; the container is removed afterwards"
    why_human: "The only recorded container run (23-16-SUMMARY, b9121a8, 04:58) predates all 18 review-fix commits, including a19e9a4 which changed the hook probe itself. The verifier is not allowed to run e2e."
  - test: "On a real Linux desktop (Bazzite) after an install with zsh present, open a new kitty, WezTerm and Konsole window and run `echo $SHELL; ps -p $$ -o comm=`; then start herdr or tmux inside it"
    expected: "Each terminal runs zsh and `$SHELL` is the real zsh path from the managed `# >>> tools-installer shell >>>` block in ~/.zshenv (or $ZDOTDIR/.zshenv); child tools start zsh, not bash"
    why_human: "Tests prove the file contents in a scratch HOME; only a real terminal launch proves zsh reads the block and the emulators honour their owned regions"
  - test: "With VS Code installed and lean mode chosen, open the integrated terminal"
    expected: "It opens zsh (terminal.integrated.defaultProfile.linux = \"zsh\" resolves to a detected profile); user keys and comments in ~/.config/Code/User/settings.json are intact; VS Code itself still loads the file without a JSONC error"
    why_human: "Profile resolution and VS Code's own JSONC parser are runtime behaviour of the real app"
  - test: "Real-host settings revert: with a disposable copy of agent settings (never the developer's own), choose auto-approve + no-attribution, then turn them off in Policies, then uninstall claude/codex/cursor-agent/opencode"
    expected: "Only the documented keys appear and disappear; comments and unrelated keys survive byte-for-byte; a key the user changed in between is kept and reported"
    why_human: "Requested explicitly by the orchestrator; scratch-HOME tests pass but a real-host revert against live CLIs that rewrite their own settings files cannot be proven in pytest"
  - test: "Run the TUI under NO_COLOR=1 at 80x20: install review with run options, the keyed shell-init modal, Policies rows (auto-approve, attribution, VS Code, shell-init, desktop SHELL), ConfirmUninstall blocks, and the launch alias-removal notice"
    expected: "Every line fits the 78-cell budget, no truncated option notes, marks readable without colour; the alias-removal notice and the post-run `Shell:` notice line are legible"
    why_human: "Visual layout; tests/test_layout_80x20.py covers sizes but not human legibility under NO_COLOR"
  - test: "With colour on, trigger a post-run Shell write in the TUI (install zsh/kitty in a container) and look at the notice line"
    expected: "The `Shell: ... now exports SHELL=...` line appears in the warn colour on the interactive close notice (REVIEW-FIX deviation 5 chose the single notice channel)"
    why_human: "Colour and placement are visual"
  - test: "macOS (bash 3.2 as /bin/bash, zsh default login shell): turn on each of the six shell-init bundles, open a new zsh and a new bash"
    expected: "Each guarded block parses in bash 3.2 and zsh, no error at shell start; terminal sync and ~/.zshenv are skipped on macOS by design; VS Code lean writes update.mode=none and defaultProfile.osx"
    why_human: "No macOS host; tests pass platform_os=\"macos\" explicitly but never run the darwin detection or a real bash 3.2"
  - test: "Decide on CONF-08's pi clause: the requirement says pi's state 'notes when a permission extension is installed'; the code always shows the static note `pi: nothing written; its approvals come only from extensions` (installer/render.py:439) and never detects an extension"
    expected: "Either accept the static note (add an override) or schedule extension detection"
    why_human: "Signed off by the orchestrator only (RUN-LEDGER row 295 item 2), not by the user"
  - test: "Decide on SC1's rtk parenthetical: 'the installer does not install or register rtk', but the rtk catalog entry is still installable (installer/registry.toml:1827-1828)"
    expected: "Accept as out of scope (user scope change 2026-11-02 in 23-CONTEXT.md:6 says catalog removal is a later separate phase) via an override, or add the removal to a later phase"
    why_human: "The hook is gone (test_rtk_has_no_hook) but the literal SC wording is not true; no later roadmap phase names the rtk removal"
---

# Phase 23: Configuration as a lifecycle step Verification Report

**Phase Goal:** Configuration is applied, checked and reversed with its tool: agent-host hooks follow hosts in and out, shell init is offered and removed, and terminals stay on zsh.
**Verified:** 2026-11-07
**Status:** passed (re-verified 2026-11-15; owner-only items listed below)
**Re-verification:** No — initial verification (on main @ a30bb2f, after the code review fix loop)

## Gate runs (this verifier, this tree)

- `make validate`: exit 0 (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).
- `make test`: exit 0, 5819 passed, 4 skipped, coverage 96.20% (gate 90%).
- Targeted named run (`-n 0 --no-cov`, 23 SC-anchoring tests by name): 28 passed, 0 failed.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Installing codex with codegraph present registers codex once and records it in `receipt.hooks`; removing codegraph unregisters exactly the recorded hosts; hooks read one agent-host list | ✓ VERIFIED | `postinstall.register_hooks` (postinstall.py:269-301) registers `present - recorded` and records via `receipts.record_hooks`; `session._resync_hooks` (session.py:542-583) re-runs after a host row ends done; `uninstall._hook_undo` (uninstall.py:292-313) builds argvs from the receipt only, filtered through the code-owned target map. One list: `present_hosts()` -> `skill_lifecycle.present_harnesses`. Tests pass: `test_installing_codex_with_codegraph_registers_codex_once`, `test_installing_codex_resyncs_codegraph_for_codex_only`, `test_removing_codegraph_unregisters_exactly_the_recorded_hosts`, `test_one_host_list_has_no_second_host_table`, `test_rtk_has_no_hook`. rtk catalog entry still installable: see human decision item. herdr: deferred to Phase 24. graphify: no hook by ledger Q1 (project-scoped registration). |
| 2 | Managed `~/.zshenv` exports SHELL=real zsh; kitty/WezTerm/Konsole config without the owned region shows `≈`; RECONFIGURE writes it | ✓ VERIFIED | `terminal_shell.zshenv_block`/`_edit_zshenv` (terminal_shell.py:304-333), `sync_terminal_shells(write=False)` dry run feeds `version_status._terminal_facts` (version_status.py:1625-1646), RECONFIGURE runs the write path. Tests pass: `test_the_zshenv_dry_run_reports_drift_and_writes_nothing`, `test_a_zsh_reconfigure_reports_konsole_and_zshenv`, `test_konsole_drift_lands_on_zsh`, `test_strip_only_never_writes_while_zsh_is_present`. Linux only (macOS returns `skipped=("macos",)`, terminal_shell.py:489). Real terminal launch: human item. |
| 3 | starship "yes" turns its shell-init bundle on, declining leaves nothing, removal removes it (same for direnv, zoxide, fzf, fnm, volta) | ✓ VERIFIED | Six bundles in `tweaks.SHELL_INIT_TOOLS` (tweaks.py:87, 144-176); each registry entry declares `post_install = ["source_shell_init"]`; `_source_shell_init` (post_install.py:139-153) applies only on `confirm(...)` true; prompt default False (post_install.py:67-73); removal via `app._after_removal` (app.py:700-723). Headless default no / `--yes` asks nothing: `test_headless_option_questions_default_to_no`, `test_headless_yes_asks_nothing_and_says_so`. Tests pass: `test_each_shell_init_tool_follows_yes_and_no`, `test_shell_init_is_never_turned_on_without_a_yes`, `test_starship_yes_turns_shell_init_on_and_empties_the_theme`. |
| 4 | tealdeer fetches its cache after install and update; OMZ plugin writes honor `$ZSH`; selecting current zsh no longer promises a step that never runs | ✓ VERIFIED | `_tealdeer_cache` hook (postinstall.py:171-180), registry `postinstall = "tealdeer-cache"`, `test_tealdeer_fetches_its_cache_after_install`, `test_tealdeer_update_runs_tldr_update_once`; `omz_root` reads `$ZSH` (omz.py:659-676) and the template writes `export ZSH=<root>` (omz.py:444-449); `_CHSH_ABSENT_EXPLANATION` third line now names the sync that runs (post_install.py:107-113), `test_the_chsh_absent_text_names_the_sync_that_runs`. |
| 5 | Auto-approval and no-attribution write the documented keys into Claude, Codex, opencode, cursor-agent (comments/unrelated keys kept); off reverts exactly those keys; alias bundles gone from Policies with legacy blocks stripped + notice (CONF-10 amended); one prompt active | ✓ VERIFIED | Key table `agent_settings._KEYS` (agent_settings.py:519-542) matches CONF-08/09 (Claude attribution uses `""`, the vendor-documented form, ledger row 285); writes through `session._apply_run_options` and Policies `revert_setting` (policy.py:678); per-removal `_revert_settings` (app.py:670-697). `LEGACY_ALIAS_BUNDLES` not in `BUNDLES` (checked at runtime); `strip_legacy_aliases` (tweaks.py:335-360) called at launch (setup.py:930, 1336, 1464) and uninstall, writes nothing to agent files. Starship's yes sets `ZSH_THEME=""`; `test_starship_in_policies_sets_and_restores_the_theme_like_the_install_yes`. Tests pass: `test_claude_auto_approve_writes_records_and_reverts_byte_identical`, `test_codex_auto_approve_goes_to_the_top_level`, `test_cursor_attribution_replaces_cli_defaults_and_restores_them`. |
| 6 | VS Code lean writes only absent keys into a JSONC settings.json (comments and user keys intact), opt-out removes exactly those keys, integrated terminal opens zsh | ✓ VERIFIED | `_VSCODE_LEAN` + `_vscode_lean` (agent_settings.py:492-554) include every CONF-12 key plus `terminal.integrated.defaultProfile.<os>` = zsh; `chat.disableAIFeatures` and the two extension keys are separate settings. `update.mode` only on macOS (ledger Q7: VS Code on Linux is the installer's own tarball). Tests pass: `test_vscode_lean_adds_only_absent_keys_and_keeps_comments`, `test_vscode_lean_on_fedora_writes_the_linux_profile`. Real VS Code terminal: human item. |

**Score:** 6/6 truths verified (0 present, behavior-unverified)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | herdr hook on a real installed herdr | Phase 24 | SC1: "herdr installs, its integrations register for the present agent hosts" |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/postinstall.py` | HookPair table, one host list, register/unregister builders, tealdeer hook | ✓ VERIFIED | Wired from engine.py:24, update.py:102, session.py:45, uninstall.py:26 |
| `installer/agent_settings.py` | JSON/JSONC/TOML splice, ledger, documented keys | ✓ VERIFIED | Wired from app.py:16, policy.py, session.py |
| `installer/terminal_shell.py` | `.zshenv` block, kitty/WezTerm/Konsole regions, dry run | ✓ VERIFIED | Dry run feeds version_status; write path after runs |
| `installer/tweaks.py` | Six shell-init bundles, legacy alias strip | ✓ VERIFIED | setup.py launch + uninstall callers |
| `installer/omz.py` | `$ZSH`-aware root, single theme writer | ✓ VERIFIED | post_install `_set_omz_theme`, policy |
| `installer/post_install.py` | keyed sensitive prompts, shell-init/theme/lean-tip actions, chsh copy | ✓ VERIFIED | registry `post_install` lines for 8 tools |
| `installer/session.py` | run options, host re-sync, desktop SHELL | ✓ VERIFIED | execute_plan path |
| `installer/uninstall.py` / `installer/app.py` | unregister-first removal, settings/shell-init revert | ✓ VERIFIED | `_hook_undo`, `_after_removal`, `_revert_settings` |
| `scripts/container-e2e-verify.sh` | hook + settings probes around `--uninstall --yes` | ✓ VERIFIED (static) | Probes present and unit-tested (tests/test_container_e2e_receipts.py); container run on HEAD is a human item |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| engine.install_tool | postinstall.register_hooks | import + call after method install | WIRED |
| session.execute_plan | session._resync_hooks | host row INSTALL/REPAIR/REINSTALL ended done | WIRED |
| uninstall.removal_plan | postinstall.unregister_argvs | `_hook_undo` from receipt hooks only | WIRED |
| registry (6 tools) | post_install._source_shell_init | `post_install = ["source_shell_init"]` | WIRED |
| registry tealdeer | postinstall._tealdeer_cache | `postinstall = "tealdeer-cache"` (install and update) | WIRED |
| version_status._terminal_facts | terminal_shell.sync_terminal_shells(write=False) | one dry run per pass, drift -> MISCONFIGURED | WIRED |
| setup.py launch / uninstall | tweaks.strip_legacy_aliases | launch_lines -> StatusLine / console | WIRED |
| app removal routes | agent_settings.revert_agent | `_revert_settings` | WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full gates | `make validate`; `make test` | exit 0; 5819 passed, 4 skipped, 96.20% | ✓ PASS |
| SC-anchoring tests | `uv run pytest -n 0 --no-cov -k "<23 names>"` | 28 passed | ✓ PASS |
| Alias bundles gone, hook table, registry hook users | `uv run python -I -c ...` (scratch HOME) | legacy ∩ BUNDLES = {}; hooks = codegraph, herdr, tealdeer; postinstall users = codegraph, tealdeer | ✓ PASS |
| Container e2e on HEAD | `make e2e` | not run (forbidden for the verifier) | ? SKIP -> human |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists. The container e2e (`scripts/container-e2e-verify.sh`) is the phase's runnable check; it may not be run by the verifier, so it is a human item.

### Requirements Coverage

| Requirement | Description (short) | Status | Evidence |
|-------------|---------------------|--------|----------|
| CONF-01 | Hooks register per host, record, unregister | ✓ SATISFIED | SC1 (codegraph live; herdr shape, Phase 24 tool; graphify none by Q1) |
| CONF-02 | New agent host re-runs installed hook tools for that host only | ✓ SATISFIED | `_resync_hooks`, `test_installing_codex_resyncs_codegraph_for_codex_only` |
| CONF-03 | One agent-host list | ✓ SATISFIED | `present_harnesses` only; `test_one_host_list_has_no_second_host_table` |
| CONF-04 | Six shell inits offered (default off), removed with tool | ✓ SATISFIED | SC3 |
| CONF-05 | `.zshenv` SHELL, terminals on zsh, drift `≈`, environment.d asked | ✓ SATISFIED | SC2; `desktop-shell` run option + Policies row (session.py `_desktop_shell`) |
| CONF-06 | tealdeer cache after install/update | ✓ SATISFIED | SC4 |
| CONF-07 | OMZ writes honor `$ZSH` | ✓ SATISFIED | SC4 |
| CONF-08 | Auto-approval keys per agent, reverted on off/removal; pi nothing | ✓ SATISFIED (pi clause: human decision) | Keys exact; pi note is static, never detects an extension (render.py:439) |
| CONF-09 | Attribution off; Cursor caveat; no-key list | ✓ SATISFIED | Claude `""` (vendor form, ledger) instead of the REQUIREMENTS text `false`; cursor caveat and no-key note in run options/Policies |
| CONF-10 (amended) | Alias bundles leave Policies; blocks stripped with notice; no settings write | ✓ SATISFIED | `LEGACY_ALIAS_BUNDLES`, `strip_legacy_aliases`, launch notice |
| CONF-11 | Default robbyrussell only when absent; starship -> `ZSH_THEME=""`; omz theme handoff | ✓ SATISFIED | omz.set_theme/apply_theme, `_set_omz_theme` handoff lines |
| CONF-12 | VS Code lean, separate AI-off and ext-update questions, lean tips | ✓ SATISFIED | SC6; `show_lean_tips`; `update.mode` Linux deviation per ledger Q7 |

No orphaned requirements: all 12 CONF ids are claimed by at least one plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (30 phase-modified production files) | — | TBD/FIXME/XXX | none found | — |
| installer/uninstall.py | 304-308 | `shortcut:` no unregister when the executable is unproven (C-14 residual) | ℹ️ Info | Accepted in 23-REVIEW-FIX; vendor self-upgrade can leave hosts registered after removal, no handoff line |
| installer/omz.py / ~/.myshellrc | — | theme claim survives full uninstall (C-09 residual) | ℹ️ Info | Accepted; avoids the bare `%m%# ` prompt |
| installer/postinstall.py | 277-279 | `shortcut:` host removed by hand is re-registered while its marker dir remains | ℹ️ Info | Documented SPEC known limit |

### Documented deviations from REQUIREMENTS.md wording (all decided in RUN-LEDGER, none silent)

- CONF-09: Claude attribution keys are `""`, not `false` (ledger row 285; vendor-documented string form).
- CONF-12: `update.mode` is not written on Linux (ledger Q7: the installer, not a package manager, updates the Linux tarball); the Policies/run-option note says so.
- CONF-08: pi extension detection replaced by a static note (orchestrator sign-off only, row 295) — human decision item.
- SC1: rtk catalog entry kept (user scope change 2026-11-02, catalog removal "a later, separate phase") — human decision item; no later roadmap phase names it yet.

### Human Verification Required

1. **Container e2e on HEAD**: run `make e2e`. Expected: every TRACER line OK and the container removed. Why: the recorded run predates all 18 fix commits, including the hook probe change in a19e9a4.
2. **Real terminals use zsh**: on Bazzite, in new kitty/WezTerm/Konsole windows, check that `$SHELL` is the real zsh and that herdr/tmux start zsh.
3. **VS Code integrated terminal**: with lean mode on, the integrated terminal opens zsh and VS Code parses the edited JSONC.
4. **Real-host settings revert**: use a disposable copy of the agent settings. Turn the options on, then off in Policies, then uninstall. Expected: only the documented keys change and the rest survives byte for byte.
5. **NO_COLOR at 80x20**: check the TUI review options, the shell-init modal, the new Policies rows, the ConfirmUninstall blocks and the alias-removal notice for legibility.
6. **TUI Shell notice colour**: the post-run `Shell:` line appears in the warn colour.
7. **macOS bash 3.2 / zsh**: the six shell-init blocks parse at shell start. VS Code lean writes `update.mode` and `defaultProfile.osx` there.
8. **Decision on the CONF-08 pi clause**: accept the static note with an override, or schedule extension detection.
9. **Decision on the SC1 rtk parenthetical**: accept it with an override, or roadmap the removal of the rtk catalog entry.

Override template for items 8 and 9 if accepted:

```yaml
overrides:
  - must_have: "pi state notes when a permission extension is installed (CONF-08)"
    reason: "Static note covers it; pi stays out per D-05"
    accepted_by: "<user>"
    accepted_at: "<ISO timestamp>"
  - must_have: "the installer does not install or register rtk (SC1 parenthetical)"
    reason: "Hook removed in Phase 23; catalog entry removal is a later phase by user decision 2026-11-02"
    accepted_by: "<user>"
    accepted_at: "<ISO timestamp>"
```

### Gaps Summary

No blocking gaps. Every roadmap success criterion and every CONF requirement is implemented, wired and covered by passing behavioural tests on HEAD in a scratch HOME. `make validate` and `make test` are green. Two problems remain. First, the container e2e evidence predates the review-fix commits. Second, several outcomes can only be proven on a real TTY, terminal, VS Code or macOS host. Two wording deviations (the pi extension note and the rtk catalog entry) need a user decision because only the orchestrator signed them off.

---

_Verified: 2026-11-07_
_Verifier: Claude (gsd-verifier)_


## Re-verification 2026-11-15 (HEAD 024817d3)

Scope: code moved a lot since a30bb2f (23.1, 23.2, 24 to 24.5). Phase 23.2 (TUNE-01/02) replaced the Phase 23
run options, the shell-init question and the matching Policies rows with install-time tuning, so several
human items now apply to different screens. Evidence is a disposable Fedora 44 container
(`ti-uat-23-fedora`, repo copied from the tree, scratch HOME, Homebrew + uv), the TUI driven through a herdr
tab, captures in `scratchpad/uat/23-reverify/` (`01-first-screen.txt` .. `20-bash32.txt`).
`pytest` on the 37 phase test files: 4352 passed (`pytest-phase.txt`); the 10 core files alone: 766 passed.

| Item | Verdict | jev (advisory) | Evidence |
|------|---------|----------------|----------|
| H1 container e2e on HEAD | resolved | e2e: typesafe resolved 0.73 (fallback), laya open-real 0.30 (fallback); own reasoning decides | The TUI run at HEAD: zsh reconfigure + starship + fzf + zoxide + codex + claude installed, then removed through Uninstall (02, 03, 06-17). `~/.zshenv` got the managed block, `~/.myshellrc` got `tweak:` blocks with no question, removal removed them, `Shell init turned off for ...` shown. Also 23.2-VERIFICATION: `make e2e` run #9 on eb893c0, EXIT=0 with TRACER_HOOKS/SETTINGS. Caveat: the codegraph hook registration could not be re-run live because the unauthenticated GitHub API answered 403 rate limit (04, 11 show the failure; an environment limit, not a product defect). The register/unregister path is covered by `tests/test_postinstall.py` and `tests/test_container_e2e_receipts.py` (green). |
| H2 real kitty/WezTerm/Konsole windows run zsh | owner-only | typesafe owner-only 0.97 | Container proves the file side: `env -i SHELL=/bin/bash zsh -c 'echo $SHELL'` printed `/usr/bin/zsh` with the managed block (04-host-state.txt). Only a real desktop terminal launch proves the emulators honour their regions. |
| H3 VS Code integrated terminal opens zsh | owner-only | (not asked, same class as H2) | VS Code lean/AI-off/ext-update keys: `tests/test_agent_settings.py` (JSONC, comments kept, `defaultProfile.linux = "zsh"`). The real app's JSONC parser and profile resolution need the real app. |
| H4 settings revert against live CLIs | resolved | (covered by H1 class) | Real claude and codex CLIs in the container, seeded user settings: install wrote `permissions.defaultMode`, `skipDangerousModePermissionPrompt`, `attribution.pr/commit = ""` and codex `approval_policy`, `sandbox_mode` (12-settings-diff.txt, user keys intact, codex file still parses); the confirm listed exactly those keys (13); after Uninstall `cmp` reported CLAUDE_BYTE_IDENTICAL and CODEX_BYTE_IDENTICAL (15). |
| H5 NO_COLOR 80x20 legibility | resolved for Phase 23 surfaces | (class resolved) | The Phase 23 run options and the shell-init modal no longer exist (23.2). `tests/test_layout_80x20.py` green. The alias-removal notice reads `Removed the claude-skip alias; installing claude writes permissions.defaultMode in its settings instead.` and a second launch is silent (19-alias-strip.txt). The remaining 80x20 gaps (Policies shows one row, cut tab bar) are the already-tracked pre-existing todo `2026-11-03-fix-80x20-layout-gaps...` (T14), severity minor, not a Phase 23 regression (t80/02-policies.txt). |
| H6 Shell notice colour | owner-only | (colour judgement) | The line exists and is plain-text correct (`Shell: ~/.zshenv now exports SHELL=...`, 03-summary.txt shows the Shell section); the colour on the interactive notice is a visual call. |
| H7 macOS bash 3.2 / zsh | deferred (macOS, no CI path) | typesafe owner-only 0.79 | Parse part proven: the seven shell-init blocks generated by `tweaks.tweak_block` pass `bash -n` in `docker.io/library/bash:3.2` (3.2.57) and `zsh -n` (20-bash32.txt). Darwin detection, `update.mode=none` and `defaultProfile.osx` need a Mac. |
| H8 CONF-08 pi clause | owner-only | open-real 0.75 (fallback); not followed | `installer/render.py:357` prints the static `pi: nothing written; pi has no approval setting in its core`; no extension detection exists. Behaviour is not broken (pi writes nothing either way), so this is a requirement-wording decision for the owner: accept via override or schedule detection. |
| H9 SC1 rtk parenthetical | resolved | n/a | `rg 'id = "rtk"' installer/registry.toml` = 0 hits; 23.1 dropped the entry (ROADMAP 23.1 SC1). The existing override stays accurate history. |
| Deferred: herdr hook | resolved | n/a | `installer/registry.toml:3219` herdr with `postinstall = "herdr-integration"` (line 3229); Phase 24. |

### Requirements at HEAD

CONF-01 satisfied (codegraph-mcp-register, herdr-integration, tests); CONF-02 satisfied (test_session resync tests); CONF-03 satisfied (one host list, tests); CONF-04 satisfied as amended (blocks written at install and removed with the tool, container 03/06/17); CONF-05 satisfied (managed `~/.zshenv` block, container 04; desktop SHELL stays a Policies row, 05); CONF-06 satisfied (registry `postinstall = "tealdeer-cache"` + tests, not re-run live); CONF-07 satisfied (tests/test_omz.py); CONF-08 satisfied except the pi detection clause (owner, H8); CONF-09 satisfied (container: `attribution.* = ""`); CONF-10 satisfied (container 19); CONF-11 satisfied (23.2 UAT test 5, tests/test_omz.py); CONF-12 satisfied by tests (VS Code live install not re-run, H3).

### Needs owner confirmation

- H2: new kitty, WezTerm and Konsole windows on the real desktop start zsh (`echo $SHELL`).
- H3: VS Code's integrated terminal opens zsh and VS Code loads the edited settings.json.
- H6: the post-run `Shell:` notice colour on a real colour terminal.
- H8: accept the static pi note (CONF-08) or schedule extension detection.

### Deferred (macOS, no CI path)

- H7: darwin detection of the shell-init blocks, `update.mode = none`, `defaultProfile.osx`.

### Residual observations (not gaps)

- F-5 stays: removing the managed blocks leaves blank separator lines in `~/.myshellrc` (four blank lines after removing all blocks, 16-after-all-removed.txt); a byte-exact test pins the separator. Cosmetic, open-trivial.
- After removing codex, the PATH block in `~/.myshellrc` still listed codex's bin dirs until the PATH wiring row was removed (observation only; the next wiring pass rewrites it).


## Fresh re-verification with inline jev (2026-11-16)

HEAD 4c1d243e. Every finding was made as a fresh check at HEAD and classified by the jev ladder right after its group,
before the next group. Laya answers are all `fallback: true` (low confidence), so they never decided an item. Test runs:
`uv run pytest <files> -n 0 --no-cov -q` on test_postinstall, test_session (hook/resync/host/tealdeer selection),
test_terminal_shell, test_agent_settings, test_omz, test_tweaks, test_shellrc and test_layout_80x20: all passed.

| Item | Fresh evidence | Laya | TypeSafe | Verdict | Override reason |
|------|----------------|------|----------|---------|-----------------|
| CONF-01..03 | hook/resync/host/tealdeer tests pass; register_hooks, unregister_argvs, present_hosts in postinstall.py; codegraph and herdr postinstall users in registry | open-real 0.43 (fallback) | resolved 0.88 | resolved | |
| CONF-04..07 | seven phase test files pass; zshenv_block, sync_terminal_shells, omz_root, _tealdeer_cache present | open-real 0.58 (fallback) | resolved 0.98 | resolved | |
| CONF-08..12 | same files pass; strip_legacy_aliases present; REQUIREMENTS rows complete | open-real 0.51 (fallback) | resolved 0.72 (fallback) | resolved | no confident jev answer; own reasoning decides |
| H1 round trip at HEAD | container captures 02-17 present, tests green; no installer run now | open-real 0.46 (fallback) | resolved 0.73 (fallback) | resolved | own reasoning |
| H2 real terminals run zsh | capture 04: `env -i SHELL=/bin/bash zsh -c` prints /usr/bin/zsh | open-real 0.49 (fallback) | owner-only 0.94 | owner-only | |
| H3 VS Code terminal zsh | JSONC tests pass; real app not runnable here | open-real 0.40 (fallback) | owner-only 0.80 | owner-only | |
| H4 settings revert, live CLIs | capture 15: CLAUDE_BYTE_IDENTICAL, CODEX_BYTE_IDENTICAL | open-real 0.46 (fallback) | resolved 0.96 | resolved | |
| H5 80x20 legibility | test_layout_80x20 passes; alias notice in capture 19 | open-real 0.45 (fallback) | resolved 0.96 | resolved | |
| H6 Shell notice colour | line text in captures; colour is visual | open-real 0.54 (fallback) | owner-only 0.77 (fallback) | owner-only | own reasoning |
| H7 macOS bash 3.2 | capture 20: BASH32_N_OK (3.2.57); darwin detection needs a Mac | open-real 0.43 (fallback) | owner-only 0.90 | owner-only (deferred macOS) | |
| H8 CONF-08 pi clause | render.py:357 static note, no extension detection | open-real 0.52 (fallback) | resolved 0.50 (fallback) | owner-only | own reasoning: a requirement-wording decision, behaviour not broken |
| H9 rtk parenthetical | `rg 'id = "rtk"' installer/registry.toml` exit 1 (0 hits) | open-real 0.42 (fallback) | resolved 0.92 | resolved | |
| Deferred herdr hook | registry.toml:3219 herdr, postinstall herdr-integration | open-real 0.54 (fallback) | resolved 0.70 (fallback) | resolved | own reasoning |

Time order (UTC, 2026-11-16): group 1 (CONF) findings 02:44:02 to 02:44:29, jev call 02:44:40; group 2 (H1-H9, herdr)
findings 02:44:47, jev call 02:45:01. Inputs and outputs: scratchpad `fresh23-g1.json/.out`, `fresh23-g2.json/.out`.

Result: 8 resolved, 5 owner-only (H2, H3, H6, H7, H8), 0 open-trivial, 0 open-real. Status stays `passed`.
