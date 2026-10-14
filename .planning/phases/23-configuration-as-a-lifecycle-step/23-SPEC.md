# Phase 23: Configuration as a lifecycle step — Specification

**Created:** 2026-10-13
**Ambiguity score:** 0.16 (gate: ≤ 0.20)
**Requirements:** 12 locked

## Goal

Configuration is applied, checked and reversed together with its tool:
- agent-host hooks follow hosts in and out;
- shell init is offered and removed with its tool;
- terminals stay on zsh with a correct `SHELL`;
- agent behaviour lives in each agent's own settings instead of shell aliases;
- every write touches only what the installer owns.

## Background

Scouted 2026-10-13:
- **Two host lists.**
  - `postinstall.py:26` `_AGENT_HOST_IDS = ("claude", "codex", "opencode", "cursor-agent")` with `present_agent_hosts` (:29).
  - `skill_lifecycle.py:234` `present_harnesses` is the other list.
  - `POSTINSTALL_HOOKS` (:277) registers hooks but never unregisters them, and no host list is recorded (F X1).
- **Aliases instead of settings.** `tweaks.py` ships the alias bundles `claude-skip` (:181), `codex-skip` (:188), `opencode-auto`, and a cursor-agent `--model` wrapper (:136). `agent_policy.py` already writes JSON settings for opencode (`_apply_opencode` :113, `apply_agent_permissions` :231). That writer can be reused.
- **Shell evidence on the host (2026-10-13).** Every terminal runs zsh with `SHELL=/bin/bash` (999.4), and `ZSH_THEME` is unset (prompt `%m%# `).
- **Unused seams.**
  - `sync_terminal_shells` (`terminal_shell.py:383`) has no dry-run health signal.
  - tealdeer never fetches its cache (D).
  - The OMZ plugin writer ignores `$ZSH` (B 15.6 CR-01).
- **Ready from earlier phases.**
  - Phase 19: the `≈` signals for skill packs, terminals and pnpm groups.
  - Phase 20: RECONFIGURE.
  - Phase 22: `RemovalPlan.argv` (its hook slot) and `config_paths`.
  - Phase 17: an rc write that fails restores the original, and invalid JSON is never overwritten.

## Requirements

1. **Reversible host hooks (CONF-01)**: The codegraph, rtk, graphify and herdr hooks each become a `(register, unregister)` pair.
   - Current: Register only.
   - Target:
     - Register runs for (present hosts ∩ the hook's supported hosts) and records the hosts in `receipt.hooks[name]`.
     - On removal, unregister runs first for the recorded hosts only: `codegraph uninstall --keep-cli`, `rtk init -g --uninstall`, `graphify <host> uninstall`, `herdr integration uninstall`.
     - A supported, present host that is missing from `receipt.hooks` shows `≈`.
   - Acceptance:
     - Installing codex with rtk present runs `rtk init` for codex once, and the receipt gains codex (fake runner).
     - Removing rtk runs the uninstall for exactly the recorded hosts.

2. **New host re-sync (CONF-02)**: At the end of any plan run that installed an agent host, the hooks of the already-installed hook tools run for the new host only.
   - Current: Nothing.
   - Acceptance: With codegraph installed for claude, installing codex runs codegraph's register for codex only, and claude is not re-run.

3. **One host list (CONF-03)**: `_AGENT_HOST_IDS` and `present_agent_hosts` are deleted. `present_harnesses` is the only host list.
   - Acceptance: A grep test finds no `_AGENT_HOST_IDS` in `installer/`. Every hook gets its hosts from `present_harnesses`.

4. **Shell init offered (CONF-04, O11)**: starship, direnv, zoxide, fzf, fnm and volta each get one `TweakBundle`, with `requires=(cmd,)` and a body guarded by `command -v X >/dev/null &&`.
   - Current: Accepted but never run (C G6).
   - Target:
     - The bundle is offered at install through the existing sensitive-action confirm, default off.
     - Declining sets no health state.
     - Removing the tool disables its bundle.
   - Acceptance:
     - Installing starship with "yes" turns its bundle ON. Declining leaves it OFF and the row `✓`.
     - Removing starship disables the bundle.
     - The same holds for each of the six tools.

5. **zsh everywhere (CONF-05, O4)**: A managed line in `~/.zshenv` exports `SHELL` as the real zsh path. kitty (`env SHELL=`), WezTerm (`set_environment_variables`) and Konsole keep pointing at zsh inside their owned regions.
   - Current: `SHELL=/bin/bash` inside zsh.
   - Target:
     - The `sync_terminal_shells` dry run (`write=False`) yields `≈` on drift, and RECONFIGURE writes the region.
     - Exporting `SHELL` through `environment.d` (for apps started from the desktop menu) is a separate asked question, default off.
     - The terminal sync is triggered by any plan row in {INSTALL, REPAIR, REINSTALL, UPDATE, RECONFIGURE}. This replaces `wizard_app.py:2960`.
   - Acceptance:
     - In a scratch HOME, `zsh -c 'echo $SHELL'` prints the zsh path.
     - A kitty config without the region shows `≈`, and RECONFIGURE writes it.
     - An uninstalled terminal gives no `≈`.

6. **tealdeer cache (CONF-06)**: A `tealdeer-cache` hook runs `tldr --update` after install and update. The cache dir is in `config_paths`.
   - Acceptance: With a fake runner, install and `u` each run `tldr --update` once. A failure ends the row with a warning, not a failure.

7. **OMZ honors `$ZSH` (CONF-07)**: The plugin writer resolves the OMZ dir from `$ZSH` when it is set, and otherwise uses the default.
   - Acceptance: With `ZSH=/custom/omz` in a scratch HOME, plugins land under `/custom/omz/custom/plugins`.

8. **Auto-approval in settings (CONF-08)**: One install-time question (default off) covers every agent in the run. Policies keeps one row per agent for later changes.
   - Current: Alias bundles.
   - Target: When the user opts in, the keys below are written, and only when the key is absent.
     - **Claude:** user scope `permissions.defaultMode: "bypassPermissions"` and `skipDangerousModePermissionPrompt: true`.
     - **Codex:** `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`.
     - **opencode:** `"permission": "allow"`.
     - **cursor-agent:** `approvalMode: "unrestricted"`.
     - **pi:** nothing is written. Its state notes when a permission extension is installed.
   - Conflicts and reverts:
     - A key the user already set to another value is left untouched and reported as "set by you".
     - Opting out, or removing the tool, removes only the keys the installer wrote that still hold its value.
     - The keys written are recorded in the installer's per-agent config-write ledger (written by `receipts.py`, separate from install receipts so an agent the installer did not install never gains a removal-proof receipt; amended 2026-10-14).
   - Acceptance (scratch HOME):
     - Opting in writes the keys, and comments and unrelated keys are preserved.
     - A pre-existing `defaultMode: "acceptEdits"` stays and shows "set by you".
     - Opting out restores byte-identical files for keys the user never had.
     - Invalid JSON or TOML is not written, and the row shows `≈` with the reason.

9. **Attribution off (CONF-09)**: The same single question format (asked, default off) controls commit and PR attribution.
   - Target:
     - **Claude:** `attribution.commit = false` and `attribution.pr = false`.
     - **cursor-agent:** `attribution.attributeCommitsToAgent = false` and `attributePRsToAgent = false`. The UI states that the Cursor CLI ignores the commit opt-out as of 2026-10-04.
     - **Codex, opencode and pi:** listed as having no documented key, and nothing is written for them.
     - The same conflict and revert rules as requirement 8 apply.
   - Acceptance: The keys are written and reverted as in requirement 8. The three agents without a key show the "no documented key" note.

10. **Aliases leave Policies (CONF-10)**: `claude-skip`, `codex-skip`, `opencode-auto` and the cursor-agent model wrapper are removed from `tweaks.BUNDLES`.
    - Current: Four alias bundles.
    - Target:
      - On the first run after upgrade, a host that had one enabled gets the alias removed from the rc. It also gets the equivalent config key applied (for cursor-agent, the default model goes into `cli-config.json`) under the rules of requirement 8.
      - The migration is reported in the summary.
    - Acceptance:
      - A scratch rc with `claude-skip` enabled ends with no alias and with the Claude keys written.
      - Policies lists none of the four bundles.

11. **Default OMZ theme (CONF-11)**: The OMZ writer adds `ZSH_THEME="robbyrussell"` before `source $ZSH/oh-my-zsh.sh` only when the file has no `ZSH_THEME` line.
    - Target:
      - Choosing starship (requirement 4) writes `ZSH_THEME=""`, so only one prompt is active.
      - The install summary names `omz theme use <name>` (try it) and `omz theme set <name>` (keep it).
    - Acceptance:
      - A zshrc without `ZSH_THEME` gains `robbyrussell`, placed before the source line.
      - A zshrc with `ZSH_THEME="agnoster"` is unchanged.
      - Starship writes an empty theme.

12. **VS Code lean mode (CONF-12)**: Installing VS Code asks about lean mode. Built-in AI off (`chat.disableAIFeatures`) and extension auto-update off are two separate questions.
    - Target:
      - Lean mode writes only keys absent from `~/.config/Code/User/settings.json`. The file is JSONC, and its comments are preserved.
      - The written keys are recorded, and opt-out or removal reverts exactly those keys.
      - The keys are the CONF-12 list. `update.mode: "none"` is written on macOS only together with LIFE-10.
      - The summary recommends no resident type-checker extension, and running pre-commit on demand.
    - Acceptance (scratch HOME):
      - A JSONC file with comments and one user key: lean mode adds only the absent keys, and both the comments and the user key survive.
      - Opt-out returns the file byte-identical.
      - The integrated terminal default profile is zsh.

## Boundaries

**In scope:**
- `(register, unregister)` hook pairs, `receipt.hooks`, re-sync for new hosts, one host list
- Six shell-init bundles; the `SHELL` zshenv line; the terminal dry run as `≈`; the optional `environment.d` question
- `tealdeer-cache`, OMZ `$ZSH`, the default theme, single-prompt with starship
- Auto-approval and attribution keys for Claude, Codex, opencode and cursor-agent; pi noted only; the alias migration
- VS Code lean mode and its two separate questions

**Out of scope:**
- Login-shell change (`chsh`) — unchanged, note only
- git config for delta/difftastic, completions, desktop entries, services — handoff lines only (TA §6)
- herdr and Alacritty onboarding themselves — Phase 24; only herdr's hook pair shape is defined here
- Re-registering a host the user removed by hand is not prevented — known limit, with a `shortcut:` comment at the hook dispatch (TA §6)
- VS Code extensions management and LSP on demand — not planned

## Constraints

- Writers preserve comments and unrelated keys in JSON, JSONC and TOML. A file that fails to parse is never written (Phase 17 rule).
- Every write is atomic, and a failed write leaves the original (Phase 17).
- Only installer-written keys are reverted, and only while they still hold the installer's value.
- Zero sudo. Tests use a scratch HOME and fake runners, and never touch the real rc or agent settings.
- `environment.d` writes go only to the user dir and only when asked.

## Acceptance Criteria

- [ ] Installing codex with rtk present runs `rtk init` for codex once and records it; removing rtk unregisters exactly the recorded hosts
- [ ] Installing a new host re-runs installed hook tools for that host only
- [ ] No `_AGENT_HOST_IDS` in `installer/`; every hook reads `present_harnesses`
- [ ] Each of the six shell-init tools: "yes" → bundle ON; "no" → OFF and no health state; removal disables the bundle
- [ ] In a scratch HOME, zsh prints the zsh path for `$SHELL`; a kitty config without the region shows `≈` and RECONFIGURE writes it; no `≈` for absent terminals
- [ ] `tldr --update` runs once after install and once after `u`; its failure ends the row with a warning
- [ ] With `ZSH=/custom/omz`, plugins land under `/custom/omz/custom/plugins`
- [ ] Auto-approval: keys written only when absent, comments and unrelated keys kept; a user-set value stays and shows "set by you"; opt-out restores the file byte-identical; invalid JSON/TOML is not written and shows `≈`
- [ ] Attribution: Claude and cursor-agent keys written and reverted; Codex, opencode and pi show "no documented key"; the Cursor commit caveat is shown
- [ ] An enabled `claude-skip` alias migrates to the Claude keys and leaves no alias; Policies lists none of the four bundles
- [ ] A zshrc without `ZSH_THEME` gets `robbyrussell` before the source line; an existing theme is unchanged; starship writes `ZSH_THEME=""`
- [ ] VS Code lean mode adds only absent keys to a commented JSONC file; opt-out returns it byte-identical; the terminal profile is zsh; AI-off and auto-update-off are separate questions

## Edge Coverage

**Coverage:** 20/20 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| idempotency | R1 | ✅ covered | A second register for a recorded host is skipped (AC 1) |
| concurrency | R1 | 🧪 backstop | A crash after register and before the receipt write: the next pass shows `≈`, and RECONFIGURE registers again (held-out test) |
| unclassified | R2 | ✅ covered | Only the new host is run (AC 2) |
| adjacency | R3 | ✅ covered | A host supported by the hook but absent is never registered (AC 1, AC 3) |
| empty | R3 | ✅ covered | No present hosts → hooks run nothing and record nothing (AC 3) |
| ordering | R3 | ✅ covered | Hosts are iterated in `present_harnesses` order; receipts store a sorted list (AC 3) |
| unclassified | R4 | ✅ covered | Six tools, yes/no/removal (AC 4) |
| adjacency | R5 | ✅ covered | A user's own `SHELL=` line elsewhere in `.zshenv` is left; the managed line comes after it (AC 5) |
| empty | R5 | ✅ covered | No terminals installed → no `≈`, no writes (AC 5) |
| ordering | R5 | ✅ covered | The terminal sync runs after the plan rows finish (AC 5) |
| idempotency | R6 | ✅ covered | One `tldr --update` per install or update; reruns are harmless (AC 6) |
| concurrency | R6 | ✅ covered | It runs inside the plan's sequential engine; no parallel update (AC 6) |
| unclassified | R7 | ✅ covered | The custom `$ZSH` fixture (AC 7) |
| adjacency | R8 | ✅ covered | A key already equal to the installer's value is recorded as not written by us, so opt-out keeps it (AC 8) |
| empty | R8 | ✅ covered | A missing settings file is created with only our keys and deleted on opt-out if it is then empty (AC 8) |
| ordering | R8 | ✅ covered | Keys are inserted without reordering existing keys (AC 8) |
| unclassified | R9 | ✅ covered | Two agents with keys, three without (AC 9) |
| unclassified | R10 | ✅ covered | Migration of an enabled alias (AC 10) |
| unclassified | R11 | ✅ covered | Absent, present and starship cases (AC 11) |
| concurrency | R12 | 🧪 backstop | VS Code rewriting `settings.json` between our read and write: compare and swap on the mtime; on a mismatch, re-read and retry once, then report `≈` (held-out test) |

## Prohibitions (must-NOT)

**Coverage:** 5/5 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT overwrite a settings key the user set to another value | R8, R9, R12 | resolved | test: the pre-set `acceptEdits` and the user VS Code key survive |
| MUST NOT write a settings file that fails to parse | R8, R12 | resolved | test: invalid JSON/TOML is byte-identical after the run |
| MUST NOT overwrite an existing `ZSH_THEME` | R11 | resolved | test: the `agnoster` fixture is unchanged |
| MUST NOT unregister a host that the receipt does not record | R1 | resolved | test: the fake runner sees only recorded hosts |
| MUST NOT enable auto-approval, attribution-off or shell init without an explicit "yes" | R4, R8, R9 | resolved | test: a default run writes none of them |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.88  | 0.75 | ✓      | Configuration lives and dies with its tool |
| Boundary Clarity   | 0.82  | 0.70 | ✓      | herdr onboarding in 24; handoff-only items listed |
| Constraint Clarity | 0.80  | 0.65 | ✓      | Preserve, parse-or-refuse, revert only our keys |
| Acceptance Criteria| 0.84  | 0.70 | ✓      | 12 pass/fail criteria in a scratch HOME |
| **Ambiguity**      | 0.16  | ≤0.20| ✓      | |

## Interview Log

`--auto`: the initial ambiguity of 0.16 was under the gate, because CONF-01..12 already name the keys and behaviours, so the interview was skipped. The two open decisions went to jev-fast-decision. Local Laya answered first, one call per question, and then TypeSafe direct (`jev-latest` → `jev-1.13.0`) answered both in one batch. Every answer is advisory, and the final decision is recorded below.

| Round | Perspective     | Question summary | Laya (advisory) | TypeSafe (advisory) | Decision locked |
|-------|-----------------|------------------|-----------------|---------------------|-----------------|
| auto | Failure Analyst | An agent settings key the user already set differently | ask_each p=0.86 | leave_and_report p=0.53 (needs fallback) | **Leave it and report "set by you".** This matches CONF-11 (never overwrite a theme) and CONF-12 (absent keys only), and adds no install prompts |
| auto | Simplifier      | Ask about auto-approval and attribution per agent or once? | one_for_all p=0.64 (needs fallback) | one_for_all p=0.82 | One question per setting for the run; per-agent rows in Policies |
| auto | Failure Analyst | Edge table and prohibitions | – | – | All resolved as covered or backstop; none dismissed |

---

*Phase: 23-configuration-as-a-lifecycle-step*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 23 — implementation decisions (how to build what's specified above)*
