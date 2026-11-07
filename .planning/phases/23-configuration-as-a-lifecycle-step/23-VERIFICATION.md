---
phase: 23-configuration-as-a-lifecycle-step
verified: 2026-11-07T12:00:00Z
status: human_needed
score: 6/6 must-haves verified
covered_files: [".planning/phases/23-configuration-as-a-lifecycle-step/23-01-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-01-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-02-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-02-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-03-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-03-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-04-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-04-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-05-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-05-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-06-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-06-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-07-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-07-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-08-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-08-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-09-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-09-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-10-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-10-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-11-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-11-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-12-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-12-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-13-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-13-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-14-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-14-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-15-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-15-SUMMARY.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-16-PLAN.md", ".planning/phases/23-configuration-as-a-lifecycle-step/23-16-SUMMARY.md", "installer/agent_env.py", "installer/agent_settings.py", "installer/app.py", "installer/atomic.py", "installer/engine.py", "installer/env_redirect.py", "installer/execute_screen.py", "installer/locations.py", "installer/model.py", "installer/omz.py", "installer/policy.py", "installer/post_install.py", "installer/postinstall.py", "installer/prompt.py", "installer/receipts.py", "installer/registry.toml", "installer/render.py", "installer/run.py", "installer/session.py", "installer/shellrc.py", "installer/terminal_shell.py", "installer/tweaks.py", "installer/uninstall.py", "installer/update.py", "installer/version_status.py", "installer/wizard_app.py", "scripts/container-e2e-verify.sh", "setup.py", "tests/conftest.py", "tests/state_doubles.py", "tests/test_agent_env.py", "tests/test_agent_settings.py", "tests/test_app.py", "tests/test_atomic.py", "tests/test_catalog_tui.py", "tests/test_cli.py", "tests/test_container_e2e_receipts.py", "tests/test_engine.py", "tests/test_env_redirect.py", "tests/test_execute_screen.py", "tests/test_layout_80x20.py", "tests/test_locations.py", "tests/test_model.py", "tests/test_omz.py", "tests/test_ownership.py", "tests/test_policies_e2e.py", "tests/test_policy.py", "tests/test_policy_omz.py", "tests/test_policy_settings.py", "tests/test_policy_tweaks.py", "tests/test_post_install.py", "tests/test_postinstall.py", "tests/test_prompt.py", "tests/test_receipts.py", "tests/test_registry.py", "tests/test_render.py", "tests/test_run.py", "tests/test_sandbox.py", "tests/test_session.py", "tests/test_setup.py", "tests/test_shellrc.py", "tests/test_terminal_shell.py", "tests/test_tweaks.py", "tests/test_uninstall.py", "tests/test_uninstall_e2e.py", "tests/test_update.py", "tests/test_version_status.py", "tests/test_wizard_app.py"]
covered_digest: "v4:sha256:7a6d0e2cb4c1d014c17089ba8d21d8f68bad37cdb9b8301523927b878dda4d87"
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
**Status:** human_needed
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
