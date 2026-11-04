# Phase 23: Configuration as a lifecycle step - Research

**Researched:** 2026-11-04
**Domain:** Reversible host configuration (agent-host hooks, shell init, terminal `SHELL`, agent and editor settings) in a Python/uv installer
**Confidence:** MEDIUM-HIGH. The code reality is HIGH (read this session). The vendor keys are HIGH where official docs were fetched, and MEDIUM/LOW where they are marked `[ASSUMED]`.

<user_constraints>
## User Constraints (from CONTEXT.md)

> **Scope change (user, 2026-11-02):** rtk is out of scope. The installer does not install, register or unregister rtk, so CONF-01 covers only the codegraph, graphify and herdr hooks. This overrides every rtk mention below (`_RTK_HOST_ARGS`, `rtk init`, "register rtk for codex"). Removing an existing rtk catalog entry is a later, separate phase.

Binding scope rows (RUN-LEDGER 2026-11-02 and user memory): the installer does not install skill packs, rtk or open-gsd. rtk registration is dropped.

### Locked Decisions (verbatim from 23-CONTEXT.md `<decisions>`)

**Decision rule:** best over easy. jev ladder: Laya is accepted only with high confidence of its own. Otherwise TypeSafe, and if that's unsure too, full-model reasoning.

#### Hooks, hosts and re-sync (R1, R2, R3)
- **D-01 (best, not easy):** Delete `_AGENT_HOST_IDS`/`present_agent_hosts` (`postinstall.py:26-46`).
  - `skill_lifecycle.present_harnesses(home, which)` (`:234-242`) is computed **once per run** by the caller (`engine.install_tool`, `execute_plan`) and passed as a `frozenset[str]` into every hook.
  - `PostinstallHook` becomes `(register, unregister)` with the signature `(method, runner, hosts)`. The `tools` map parameter goes away.
  - Hosts = the passed set ∩ the hook's own id map (`_CODEGRAPH_TARGETS` :67, `_RTK_HOST_ARGS` :149, `_GRAPHIFY_HOST_SUBCOMMANDS` :250, plus herdr's).
  - jev: Laya hook_calls_itself 0.71, own confidence 0.13, so I pivoted; TypeSafe inject_hosts 0.96.
- **D-02:** `receipt.hooks[name]` holds a sorted tuple of the hosts that were registered.
  - `≈` shows when (present ∩ supported) − recorded is not empty, through a 19 D-20 `ConfigStep` ("register rtk for codex").
  - A crash after register but before the receipt write shows `≈` on the next pass, and RECONFIGURE registers again (registration is idempotent per host).
- **D-03:** New-host re-sync is **one sweep at the end of `execute_plan`**, when any INSTALL/REPAIR/REINSTALL row installed a harness.
  - For each hook tool whose receipt records hooks, register only for `present_harnesses − recorded`.
  - It never re-runs recorded hosts (SPEC AC 2: claude is not re-run).
- **D-04:** The removal unregister fills `RemovalPlan.argv`'s hook slot (22 D-06), **before** the remove argv.
  - It uses exactly `receipt.hooks[name]`, never the present hosts.
  - The commands are `codegraph uninstall --keep-cli`, `rtk init -g --uninstall`, `graphify <host> uninstall` and `herdr integration uninstall`, all to be verified by the researcher.
- **D-05:** pi becomes reachable as a host for free through `present_harnesses` (`HARNESS_PRESENCE["pi"]`, `skill_lifecycle.py:189`). It is **not** added to any hook id map, because no vendor support for a pi target is verified.

#### Agent settings writer (R8, R9, R10, R12)
- **D-06:** A new `installer/agent_settings.py` is the single writer for agent and editor settings.
  - Formats: JSON (Claude user `settings.json`, `opencode.json`, `~/.cursor/cli-config.json`), JSONC (VS Code `settings.json`) and TOML (`~/.codex/config.toml`).
  - It writes **only absent keys**.
  - A key with another value is left alone and reported as "set by you".
  - It refuses an invalid file: `≈` with the reason, and nothing is written.
  - `agent_policy._write_json` (`agent_policy.py:85-122`) is not reused. It re-serializes the whole file, isn't atomic and has no provenance. Agent config **paths** come from one table: `agent_env.AgentAdapter`/`adapters()` (`agent_env.py:21-63`) is reused and extended with cursor-agent and VS Code, not duplicated as new constants. Nothing in 23 wires `apply_agent_permissions`/`audit_agent_policy`/`agent_guidance`; Phase 25's reachability check decides their fate. (Corrected 2026-10-14: an earlier line claimed the audit "keeps its role", but no caller exists.)
- **D-07 (best, not easy):** Guarded splice for every format, the same pattern as 18 D-09.
  - Insert the key line at a computed position: top-level TOML keys go before the first table header; JSON/JSONC goes inside the root object, respecting commas.
  - Then re-parse (`tomllib`, or `json` after stripping comments and trailing commas) and assert that exactly the intended keys changed. Otherwise refuse.
  - Revert removes exactly the spliced lines when their values still match, so a file the user never touched comes back byte-identical.
  - There is no new dependency; tomlkit was rejected for consistency with 18 D-09 and because the guard is needed anyway.
  - Each write goes through `atomic_write_text` with the 17 D-06 compare-before-commit check (an mtime or byte check, which covers VS Code rewriting its file).
  - jev: Laya 0.43 (needs fallback); TypeSafe guarded_splice 1.00.
  - The researcher must confirm that Codex's `approval_policy`/`sandbox_mode` are top-level keys.
- **D-08 (best, not easy; SPEC R8 amended):** The written keys and values are recorded in a **per-agent config-write ledger**.
  - It lives at `~/.local/state/tools-installer/config/<agent>.json`, one file per agent, atomic, and is written by `receipts.py`.
  - It is not stored inside install receipts. Agents the user installed have no receipt, and creating one would wrongly make them removable (19 D-10).
  - Tool removal, opt-out and Policies revert all read the ledger.
  - jev: Laya config_ledger 0.58 (needs fallback); TypeSafe 0.95.
- **D-09 (best, not easy):** The questions are asked **at run level, in the review**.
  - When the plan contains at least one agent (claude, codex, opencode, cursor-agent), the review (20) shows "Auto-approve agents?" and "Turn off commit/PR attribution?", both default off.
  - The answers are inputs to `execute_plan` and apply to every agent row in the run.
  - Headless `--yes` leaves both off.
  - Policies keeps one row per agent for later changes.
  - The VS Code lean-mode questions (two of them) are asked the same way when VS Code is in the plan.
  - jev: Laya 0.55 (needs fallback); TypeSafe run_level_review 1.00.
- **D-10:** Alias migration (CONF-10).
  - `claude-skip` (`tweaks.py:181`), `codex-skip` (:188), `opencode-auto` (:201) and `cursor-agent-model` (:209, body :118-141) are deleted from `BUNDLES`, in the same change as the migration.
  - On the first run after the upgrade, an enabled alias block is stripped (by `shellrc.strip_block`) and its equivalent keys are written through D-06/D-08. For cursor-agent, the default model goes into `cli-config.json`.
  - The summary reports the migration.

#### Shell init, OMZ theme and `$ZSH` (R4, R7, R11)
- **D-11:** One `TweakBundle` per shell-init tool (starship, direnv, zoxide, fzf, fnm, volta), with `requires=(cmd,)`, a body guarded by `command -v X >/dev/null &&`, and **a bundle id equal to the tool id**.
  - It is dispatched through a new `source_shell_init` entry in `POST_INSTALL_HOOKS` (`post_install.py:66-69`; the action is declared at `model.py:49` but never dispatched today).
  - `source_shell_init` is added to `SENSITIVE_POST_INSTALL_ACTIONS` (`model.py:55`), so it is asked through the existing confirm. `confirm is None` (headless) means it never runs (`post_install.py:62`).
  - `SensitiveActionScreen`'s prompt is hardcoded to the login-shell text (`execute_screen.py:161-165`), so it becomes keyed by action name. This was added 2026-10-14 by 24.1 D-06, because 24.1's EDITOR and kickstart questions need their own text.
  - Removing the tool disables **only that bundle**: `active_policies((bundle,), …)` + `sweep_policies` (`uninstall.py:401-446`). It never uses the whole-installer `sweep_tweaks`.
- **D-12:** CONF-07 fix: `write_plugins` (`omz.py:432`) calls `ensure_zshrc_template(zshrc_path)` **without** `root`, so it falls back to the default.
  - It must resolve `omz_root(home, environ)` and pass it through.
  - Any plugin directory writes use `{omz_root}/custom/plugins`, the same resolver as 22 D-03.
- **D-13:** One `set_theme(content, name)` in `omz.py` is the only theme writer.
  - It inserts `ZSH_THEME="robbyrussell"` before the source line found by `_sourced_oh_my_zsh` (`:147-153`), and only when no `ZSH_THEME=` line exists.
  - The starship bundle's enable path calls it with `""`.
  - It never overwrites an existing theme.
  - There is no shell `sed` in a bundle body.

#### zsh everywhere (R5)
- **D-14:** This phase actually **adds** the `sync_terminal_shells(write=False)` parameter (`terminal_shell.py:383-456`). 19 D-16 assumed it, but the code has none.
  - In dry-run mode it returns the terminals that would change and writes nothing.
  - The kitty body gains `env SHELL=<zsh>` and the WezTerm body gains `config.set_environment_variables = { SHELL = "<zsh>" }`, inside the **same** owned region (`_replace_owned_region` :72-108). No second region is added.
- **D-15:** The `~/.zshenv` managed `export SHELL=<real zsh path>` uses the `shellrc.apply_block`/`strip_block` owned-block pattern, not `terminal_shell`'s region code.
- **D-16:** The `environment.d` `SHELL` question (asked, default off) generalizes `env_redirect.CacheRedirect`/`target_path` (`env_redirect.py:42-78, 122-134`) to accept an absolute resolved value. That keeps one `environment.d` writer, with the ownership sentinel and macOS/Linux branch.
  - The Bun redirect is regression-tested.
- **D-17:** The terminal sync is triggered by 20 D-11 (any row in {INSTALL, REPAIR, REINSTALL, UPDATE, RECONFIGURE} ran). This replaces `wizard_app.py:2960`.

#### tealdeer (R6)
- **D-18:** `tealdeer-cache` is a non-sensitive `PostinstallHook` that runs `tldr --update` on install and update. Update re-dispatches through `update.py`'s `_run_postinstall` (`:200, 309, 343`).
  - A failure becomes a returned warning, following the `except CommandError` pattern (`postinstall.py:236-239`), not a row failure.
  - The cache dir goes in tealdeer's `config_paths` (22 D-01), not in the receipt artifacts.

### Claude's Discretion (verbatim)
- Plan and wave order. Suggested:
  1. One host list and the hook pairs, with `receipt.hooks`.
  2. `agent_settings` with the guarded splice and the ledger.
  3. The run-level questions and the alias migration.
  4. Shell init, OMZ root and theme.
  5. zsh everywhere.
  6. tealdeer.
- The ledger file schema details and the exact JSONC comment-stripper.

### Deferred Ideas (OUT OF SCOPE, verbatim)
- **pi hook targets** (codegraph/rtk/graphify for pi): unverified vendor support. A later phase adds them to the id maps once confirmed.
- **pi host repair** (`2026-10-13-repair-pi-install-and-sync-models`, 0.9 for 22 and 0.6 here): dangling Volta symlinks, the duplicate skill dir, `pi_sync.py`. This is host repair plus a reviewed handoff, not lifecycle config. It stays a pending todo (a quick task). Its "add pi to `_AGENT_HOST_IDS`" item is made moot by D-01/D-05.
- Reviewed Todos (not folded): GSD per-repo (0.6), Playwright Chrome (0.6), pnpm shims (0.2, Phase 21).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (REQUIREMENTS.md, abridged) | Research Support |
|----|-------------|------------------|
| CONF-01 | Agent-host hooks (codegraph, graphify, herdr; rtk dropped) register per host, record hosts in the receipt, unregister on removal | §Drift D1–D4; codegraph CLI verified (`uninstall --target --location --yes --keep-cli`); herdr `integration install/uninstall <TARGET>` verified; graphify conflicts with SAFE-02 and the skill-pack drop (Open Q1) |
| CONF-02 | Installing a new agent host re-runs installed hook tools for that host only | Pattern 2 (end-of-plan sweep in `execute_plan`); Pitfall 1 (`receipts.record` wipes `hooks`) |
| CONF-03 | One agent-host list everywhere | `present_harnesses` (`skill_lifecycle.py:633`); id-map re-key from catalog ids to harness ids (`cursor-agent` → `cursor`) |
| CONF-04 | Shell init for starship, direnv, zoxide, fzf, fnm, volta offered at install (default off), removed with the tool | Official init lines fetched; per-shell body pattern; volta has no init command (Open Q4); `source_shell_init` is not declared today (Drift D7) |
| CONF-05 | `SHELL` via managed `~/.zshenv`; kitty/WezTerm/Konsole point at zsh; drift `≈`; `environment.d` optional | `write=False`, the terminal `≈` and the ran-anything trigger **already landed** (Drift D5, D6); WezTerm table-clobber pitfall |
| CONF-06 | tealdeer fetches its cache after install and update | `tldr --update` [CITED docs.tealdeer.org]; cache `~/.cache/tealdeer` on Linux; update re-dispatch via `update._run_postinstall` |
| CONF-07 | OMZ plugin writes honor `$ZSH` | Bug confirmed at `omz.py:450,456`; the installer writes no plugin dirs (Drift D8) |
| CONF-08 | Auto-approval keys per agent (asked, default off), reverted on opt-out or removal | Claude/Codex/opencode/cursor keys verified in official docs; cursor self-repair pitfall (Open Q5); opencode file name (`.jsonc`) pitfall |
| CONF-09 | Attribution off for Claude and cursor-agent; Codex/opencode/pi "no documented key" | **Claude keys are strings, not booleans** (Drift D9); Codex has no attribution key [CITED]; cursor defaults `true` [CITED] |
| CONF-10 | Four alias bundles leave Policies; enabled alias migrated to config keys | Bundle ids/lines verified; cursor `model` is an object that the CLI owns (Open Q6); legacy strip for uninstall (Pitfall 7) |
| CONF-11 | Default `ZSH_THEME="robbyrussell"` only when absent; starship writes `ZSH_THEME=""` | `_sourced_oh_my_zsh` reuse; ordering of the myshellrc source line vs OMZ source (Pitfall 9) |
| CONF-12 | VS Code lean mode (JSONC, absent keys only, exact revert), two separate questions, terminal profile zsh | JSONC splice; VS Code on Linux is the installer's own tarball, not a package manager (Drift D10); LIFE-10 landed, so macOS `update.mode` is unblocked |
</phase_requirements>

## Summary

Phases 17–22 landed after CONTEXT was written ("None of these has landed as of 2026-10-14"). Several CONTEXT decisions now describe work that is already done or describe code shapes that do not exist. The biggest items: the `sync_terminal_shells(write=False)` dry run, the terminal `≈` (`ConfigStep` kind `terminal_sync`), RECONFIGURE, and the "a row ran" terminal-sync trigger are all in place (D-14 and D-17 are mostly done). There is no structural "hook slot" in `RemovalPlan.argv`: it is one `tuple[str, ...]`, so unregister needs its own field. `receipt.hooks` exists in the schema, but every write sets it to `{}`, including the update and repair re-records.

Three locked items conflict with verified facts and need a user decision before planning (Open Questions 1, 5 and 6). (1) graphify has no hook today: Phase 17 SAFE-02 removed it because every graphify form writes into the CWD. graphify 0.9.54's "global" form is a skill-file copy into the host's skills dir, which is skill-pack scope (dropped 2026-11-02). Its uninstall forms also edit `./CLAUDE.md`/`./AGENTS.md` in the CWD and ignore `--platform`. (2) Claude Code's `attribution.commit`/`attribution.pr` are **strings**: `""` hides them, and `false` is not a documented value for the sub-keys. CONF-09's `= false` would be wrong. (3) cursor-agent's `cli-config.json` is CLI-managed: the CLI "self-repairs missing fields", so `approvalMode`, `attribution.*` and `model` are normally present already. On this host they hold `allowlist`, `true`/`true` and a model object. Under "absent keys only", the cursor opt-in and the cursor model migration are no-ops on any machine where the CLI has run.

**Primary recommendation:** Build one `installer/agent_settings.py` guarded-splice writer plus a per-agent ledger, reusing the `verify_registry.apply_registry_edits` re-parse-and-compare pattern and `shellrc._snapshot`/`_snapshot_matches` for compare-before-commit. Add `RemovalPlan.unregister: tuple[tuple[str, ...], ...]` run before `argv`. Make `receipts.record` carry `previous.hooks` forward. Drop D-14/D-17 to "extend the existing region bodies". Resolve Open Q1/Q5/Q6 with the user first.

## Current State vs SPEC/CONTEXT (Drift)

| # | CONTEXT/SPEC says | Code reality (read 2026-11-04) | Impact on the plan |
|---|---|---|---|
| D1 | D-01: id maps `_RTK_HOST_ARGS` :149, `_GRAPHIFY_HOST_SUBCOMMANDS` :250 | `POSTINSTALL_HOOKS` holds only `"codegraph-mcp-register"` and `"rtk-register"` [VERIFIED: installer/postinstall.py:243-246]. No graphify hook exists. registry.toml:1780 says "postinstall removed (Phase 17, SAFE-02)" | graphify needs a new decision (Open Q1). rtk's hook still calls `present_agent_hosts` and must be touched by CONF-03 (Open Q2) |
| D2 | D-04: "fills `RemovalPlan.argv`'s hook slot" | `argv: tuple[str, ...] = ()` and `level: RemovalLevel = "none"` with `RemovalLevel = Literal["manager", "artifacts", "recipe", "none"]` [VERIFIED: installer/uninstall.py:61,93-95]. codegraph is `github_release`, so its level is `artifacts` and its argv is `()` | Add a separate field (e.g. `unregister`), and add it to `remove_tool`'s preview-equals-fresh check (`argv != fresh.argv`, app.py:593ff) |
| D3 | D-02: `receipt.hooks[name]` sorted host tuple | Schema exists: `hooks: Mapping[str, tuple[str, ...]]` [VERIFIED: installer/receipts.py:87]. The only constructor writes `hooks={},` [VERIFIED: installer/receipts.py:246]. `record()` is called from engine.py:321 and update.py:391 | Every install/update/repair re-record wipes the hosts. `record` must merge `previous.hooks` (Pitfall 1) |
| D4 | herdr hook pair | herdr is **not in the registry** (Phase 24 onboards it). Verified on host: `herdr integration install <TARGET>`, `herdr integration uninstall <TARGET>`, `herdr integration status`. Targets include `pi, claude, codex, opencode, cursor, copilot, devin, droid, kimi, kilo, hermes, qwen, grok, antigravity-cli` [VERIFIED: herdr 0.9.3 `--help`] | Define the pair and its id map only; no registry wiring until 24. herdr **does** list `pi`, which weakens D-05's reason for pi. Keep pi out per D-05 (deferred), but note it |
| D5 | D-14: "This phase actually adds `write=False`" | Already present: `write: bool = True` and the docstring "`write=False` is a dry run (D-16, L-19-05)" [VERIFIED: installer/terminal_shell.py:410-422]. Production wires it in `setup.py:727` (`terminal_drift=... write=False`). The pass turns drift into `ConfigStep(f"point {label} at zsh", "terminal_sync")` [VERIFIED: installer/version_status.py:1589] | D-14 shrinks to: extend the kitty/WezTerm region bodies with the SHELL lines. The SPEC acceptance "kitty without the region shows `≈`, RECONFIGURE writes it" likely already passes and needs only a regression test |
| D6 | D-17: replace `wizard_app.py:2960` with the 20 D-11 trigger | Already done: `if result is not None and ran_anything(result): sync_warning = terminal_sync_warning(self._terminal_sync)` [VERIFIED: installer/wizard_app.py:3578-3579] | D-17 is complete. Only the `.zshenv` line and `environment.d` remain for CONF-05 |
| D7 | D-11: `source_shell_init` "declared at `model.py:49` but never dispatched" | Not declared at all: `POST_INSTALL_ACTIONS = ("configure_path", "set_login_shell",)` and `SENSITIVE_POST_INSTALL_ACTIONS = ("set_login_shell",)` [VERIFIED: installer/model.py:125-129] | Add the name to both tuples. The post_install module doctrine "never spawns a child process ... returns reviewed instruction lines" (post_install.py:13-16) must be amended, because enabling a bundle writes `~/.myshellrc` |
| D8 | CONF-07 AC: "plugins land under `/custom/omz/custom/plugins`" | The installer writes no plugin directories: `MANAGED_PLUGINS: tuple[str, ...] = ("git", "docker")` are bundled with OMZ (omz.py:63ff). The real bug: `write_plugins` calls `ensure_zshrc_template(zshrc_path)` with no `root` [VERIFIED: installer/omz.py:450,456], so the template writes `export ZSH="$HOME/.oh-my-zsh"` for a custom `$ZSH`. Also `omz_root` prefers `~/.oh-my-zsh` over `$ZSH` when both exist [VERIFIED: installer/omz.py:530-543] | The test should assert the written `export ZSH=` line (and that no dir is created under the default). Keep `omz_root`'s order (22 C-17 locked one resolver); record the both-exist case as a known limit |
| D9 | CONF-09/SPEC R9: Claude `attribution.commit = false`, `attribution.pr = false` | Claude docs: `attribution.commit` and `attribution.pr` are **strings**, "Set it to an empty string to hide". Whole `attribution: false` needs v2.1.281+, and "earlier versions reject it and skip the whole ... settings file" [CITED: code.claude.com/docs/en/settings-reference] | Write `"commit": ""` and `"pr": ""` (works on every version). Amend SPEC R9/CONF-09 text |
| D10 | CONF-12: `update.mode: "none"` on Linux because "the package manager updates it" | VS Code on Linux is the installer's own `tarball` from the unpinned `.../latest/linux-x64/stable` URL into `~/.local/opt` (registry.toml vscode entry), not a package manager. On this host it is linuxbrew (`/home/linuxbrew/.linuxbrew/bin/code`). LIFE-10 is complete (22-12-SUMMARY `requirements-completed: [LIFE-10]`) | macOS is unblocked. For Linux, confirm the installer's `u` reports a newer VS Code tarball before muting VS Code's own update notice (Open Q7) |
| D11 | D-06: opencode file `opencode.json` | `config_path=home / ".config" / "opencode" / "opencode.json"` [VERIFIED: installer/agent_env.py:45]. This host has only `~/.config/opencode/opencode.jsonc` | The writer must pick the existing file (`.jsonc` first) and treat both as JSONC (Pitfall 5) |
| D12 | ROADMAP SC4 "selecting a current zsh no longer promises a step that never runs" | Not in SPEC/CONTEXT. The promise text survives: `"A later installer step will apply that terminal-emulator configuration automatically."` [VERIFIED: installer/post_install.py:46]. Phase 20 made a current zsh a SKIP (20-05 case G), and a REINSTALL now triggers the sync via `ran_anything` | Add one plan task: a test that a zsh reinstall with no `chsh` ends with the terminal sync called, and reword the line to name the sync that now runs |
| D13 | D-11: SensitiveActionScreen keyed by action name "added by 24.1 D-06" | 24.1 has not landed. The prompt text is still hardcoded to the login-shell sentence (execute_screen.py:160-163), and `_ask_sensitive_action(self, tool_id, _action)` ignores the action [VERIFIED: installer/execute_screen.py:784-787] | Phase 23 owns the keyed-prompt change |
| D14 | D-01: hooks take hosts "computed once per run" | `present_harnesses` reads PATH plus marker dirs [VERIFIED: installer/skill_lifecycle.py:633-641]. A host installed earlier in the same run is on PATH only after `prepend_path` (engine.py:284-286) | Compute at each dispatch (cheap) or rely on the D-03 end sweep. Either is fine, but the end sweep must recompute, never reuse the start-of-run set |

## Architectural Responsibility Map

The tiers here are installer layers, not web tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Host presence (one list) | `skill_lifecycle.present_harnesses` | composition root injects `home`/`which` | CONF-03; already the presence source for skill packs |
| Hook register/unregister argv | `postinstall.py` closed table | `engine.install_tool`, `session.execute_plan` (end sweep), `update._run_postinstall` | The registry names a hook; code owns the argv (architecture "Phase 9") |
| Hook host record | `receipts.py` (`hooks` field) | `uninstall.removal_plan` reads it | The receipt already has the field; removal proof stays receipt-based |
| Hook drift `≈` | `version_status` pass → `ConfigStep` | `session._run_step` (RECONFIGURE) | Same path as `terminal_sync` and `pnpm_group_install` |
| Agent/editor settings splice | new `agent_settings.py` | `agent_env.adapters()` for paths | One writer (D-06) |
| Config-write ledger | `receipts.py` (separate dir) | `agent_settings`, Policies, removal | D-08 |
| Run-level questions | `ExecuteScreen` review | `RunContext` field → `execute_plan` | D-09; headless leaves them off |
| Shell-init bundles | `tweaks.BUNDLES` + `post_install` action | `uninstall.active_policies/sweep_policies` | Existing tweak lifecycle |
| `.zshenv` `SHELL` line | `shellrc.apply_block/strip_block` | `terminal_shell` (zsh path lookup) | D-15 (architecture.md ownership rule must be amended, Pitfall 10) |
| `environment.d` `SHELL` | `env_redirect` (generalized) | Policies row | D-16 |
| OMZ theme | `omz.set_theme` | starship bundle enable | D-13 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `json` (stdlib) | Python 3.x (uv-managed) | Re-parse JSON/JSONC after the splice | No new dependency (D-07) |
| `tomllib` (stdlib) | Python ≥3.11 | Re-parse the Codex TOML after the splice | Already used by `model.py`, `verify_registry.py` |
| `installer.atomic.atomic_write_text` | in-repo | Sibling temp plus `os.replace`, resolves symlinks | Phase 17 rule |
| `installer.shellrc._snapshot/_snapshot_matches` | in-repo (shellrc.py:905-933) | Compare-before-commit (device, inode, bytes) | The 17 D-06 CAS that already exists. Promote it to a public helper instead of a third copy |
| `installer.verify_registry.apply_registry_edits` | in-repo (verify_registry.py:1040-1058) | The splice → re-parse → compare-to-expected pattern | 18 D-09 precedent; copy the shape, not the code |

### Supporting
| Component | Purpose | When to Use |
|---------|---------|-------------|
| `session.in_directory(cwd, argv)` (session.py:322) | Run a child in a given cwd without `os.chdir` | Only if graphify stays in scope (Open Q1: run it in an empty scratch cwd) |
| `uninstall.active_policies` + `sweep_policies` | Scoped bundle removal | CONF-04 per-tool removal |
| `env_redirect.render_conf/environment_d_dir` | `environment.d` writer with an ownership sentinel | CONF-05 optional question |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-written guarded splice | tomlkit / json5 | Rejected by D-07 (locked). The guard is needed anyway |

**Installation:** none. No new packages.

## Package Legitimacy Audit

No external packages are added in this phase. Every capability uses the stdlib or in-repo modules.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
 install row (INSTALL/REPAIR/REINSTALL)            update row (u)
        │                                                  │
        ▼                                                  ▼
 engine.install_tool ── method ok ─► receipts.record ─► hook.register(method, runner, hosts)
        │                     (keeps previous.hooks)       │   hosts = present_harnesses ∩ hook.targets
        │                                                  ▼
        │                                     receipts.record_hooks(tool, name, ∪ registered)
        ▼
 post_install actions ── source_shell_init? ─► SensitiveActionScreen(action) ─yes─► write_tweak(bundle)
        │                                                                          (starship → set_theme "")
        ▼
 execute_plan loop ends ─► END SWEEP: for each hook tool with a receipt:
        │                      new = (present_harnesses ∩ targets) − receipt.hooks[name]
        │                      register(new) → record_hooks
        │              ─► run-level answers (auto-approve / attribution / lean mode)
        │                      agent_settings.apply(agent, keys) ─► ledger/<agent>.json
        ▼
 ran_anything ─► terminal_sync (existing) + .zshenv SHELL block

 refresh pass (read-only) ─► (present ∩ targets) − recorded ≠ ∅ → ConfigStep("hook_register") → ≈
                         ─► terminal dry run (existing) → ConfigStep("terminal_sync") → ≈
                         ─► agent file unparsable → note/≈ with reason

 removal (CLI + TUI, remove_tool) ─► removal_plan: unregister argvs from receipt.hooks (recorded only)
        ─► preview == fresh check ─► run unregister ─► argv / proven paths ─► receipt retired
        ─► agent_settings.revert(agent) from ledger ─► scoped sweep of the tool's own bundle
```

### Recommended Project Structure
```
installer/
├── postinstall.py      # HookPair table: register/unregister/targets; tealdeer-cache; no _AGENT_HOST_IDS
├── agent_settings.py   # NEW: splice/revert for JSON, JSONC, TOML; parse-or-refuse; CAS
├── receipts.py         # + record keeps hooks; record_hooks(); config ledger read/write
├── uninstall.py        # RemovalPlan.unregister; removal_plan fills it from receipt.hooks
├── session.py          # RunContext answers; end-of-plan hook sweep; "hook_register" step kind
├── post_install.py     # source_shell_init action
├── tweaks.py           # 6 shell-init bundles; 4 alias bundles deleted; LEGACY_ALIAS ids for strip
├── omz.py              # write_plugins passes omz_root; set_theme()
├── terminal_shell.py   # kitty `env SHELL=`, WezTerm merge-safe env line; zshenv block helper
└── env_redirect.py     # generalized for an absolute value (SHELL)
```

### Pattern 1: Hook pair with a closed target map
**What:** Each hook is code-owned data (register argv builder, unregister argv builder, harness-id → vendor-target map). Hosts are injected. The receipt records what was registered.
**Example (shape only; names are suggestions):**
```python
# Values below are quoted from: postinstall.py:67-72 (codegraph targets keyed by catalog id today),
# skill_lifecycle.py:241 ("cursor": ("cursor-agent", "cursor")), codegraph 1.6.2 --help.
_CODEGRAPH_TARGETS: dict[str, str] = {   # re-keyed by HARNESS id, not catalog id
    "claude": "claude", "codex": "codex", "opencode": "opencode", "cursor": "cursor",
}

def _codegraph_register(method, runner, hosts: frozenset[str]) -> tuple[tuple[str, ...], str | None]:
    targets = [t for h, t in _CODEGRAPH_TARGETS.items() if h in hosts]
    if not targets:
        return (), None
    argv = [codegraph_bin, "install", "--target", ",".join(targets),
            "--location", "global", "--yes", "--no-permissions"]
    ...  # on CommandError: return (), warning
    return tuple(sorted(h for h in _CODEGRAPH_TARGETS if h in hosts)), None

def codegraph_unregister_argv(binary: str, recorded: tuple[str, ...]) -> tuple[str, ...]:
    # --target is REQUIRED: the default is "all", and --yes alone means --target=all.
    targets = [_CODEGRAPH_TARGETS[h] for h in recorded if h in _CODEGRAPH_TARGETS]
    return (binary, "uninstall", "--target", ",".join(targets),
            "--location", "global", "--yes", "--keep-cli")
```
The codegraph flags were checked against `codegraph uninstall --help` (v1.6.2): `-t, --target <ids> ... Default: all`, `-l, --location <where> ... Default: prompt`, `-y, --yes  Non-interactive: defaults to --location=global --target=all`, `--keep-cli  Remove agent configs only — leave the codegraph CLI installed` [VERIFIED: codegraph 1.6.2 CLI help, this session].

### Pattern 2: End-of-plan re-sync sweep (CONF-02)
After the `execute_plan` loop, if any INSTALL/REPAIR/REINSTALL row whose tool id is an agent host finished `done`: recompute `present_harnesses`. Then, for every catalog tool that has a hook and a readable receipt, register only `(present ∩ targets) − receipt.hooks[name]` and append those hosts. Return a warning on the host row's outcome, or a separate summary line; never fail a row.

### Pattern 3: Guarded splice plus ledger (CONF-08/09/10/12)
1. Read bytes through `_snapshot` (O_NOFOLLOW, device, inode). A missing file means "create".
2. Parse: `json.loads` (Claude, cursor: strict JSON), the JSONC stripper then `json.loads` (VS Code, opencode), or `tomllib.loads` (Codex). Failure → refuse with a reason, write nothing, show `≈`.
3. For each wanted `(key_path, value)`: absent → plan an insert. Equal → "already set" (the ledger records nothing, so opt-out keeps it). Different → "set by you".
4. Splice. JSON: insert `"k": v` right after the target object's `{`, adding a comma only when the object is non-empty. A missing parent object is created as one member. TOML: insert top-level `k = v` lines before the first `[table]` header.
5. Re-parse and assert `new_doc == expected_doc`. Otherwise refuse (the `apply_registry_edits` shape).
6. `_snapshot_matches` right before `atomic_write_text`. On a mismatch, re-read and retry once, then `≈` (SPEC R12 backstop).
7. Ledger `config/<agent>.json`: `{path, created_file, entries: [{key_path, value, inserted_text}]}`.
8. Revert: for each entry whose current value still equals `value`, remove the member (prefer the exact `inserted_text` span; fall back to locating the member when the vendor re-serialized the file). Delete a file we created when it then equals what we created. Re-parse to guard.

### Pattern 4: Cross-shell init bundle body (CONF-04)
`~/.myshellrc` is sourced by bash and zsh, so each body branches on the running shell. The init lines below come from each vendor's docs (fetched this session):
```sh
# starship: eval "$(starship init zsh)" / eval "$(starship init bash)"   [CITED: starship.rs/guide]
if command -v starship >/dev/null; then
  if [ -n "$ZSH_VERSION" ]; then eval "$(starship init zsh)"
  elif [ -n "$BASH_VERSION" ]; then eval "$(starship init bash)"; fi
fi
# direnv: eval "$(direnv hook zsh|bash)"                                [CITED: direnv.net/docs/hook.html]
# zoxide: eval "$(zoxide init zsh|bash)"  (zsh: after compinit)         [CITED: zoxide README]
# fzf:    source <(fzf --zsh) / eval "$(fzf --bash)"  ("recent versions") [CITED: fzf README]
# fnm:    eval "$(fnm env --use-on-cd --shell zsh|bash)"                [CITED: fnm README]
# volta:  no init command; needs $VOLTA_HOME/bin on PATH (already the managed PATH block) [CITED: docs.volta.sh]
```
The SPEC's single `command -v X >/dev/null && ...` line cannot pick the shell, so use the `if` form. Host fzf is `0.74.5 (Fedora)`, which has `--zsh`.

### Anti-Patterns to Avoid
- **Re-serializing a user's settings file** (`agent_policy._write_json`): loses comments and key order, and it is not atomic.
- **`--target auto`/`all` or omitted `--target`** on codegraph: the default is "all", which unregisters hosts the receipt never recorded.
- **Running any graphify install/uninstall in the installer's CWD**: SAFE-02 hazard (Open Q1).
- **`config.set_environment_variables = { SHELL = ... }` in WezTerm**: our region sits just before `return config` (terminal_shell.py:167-176), so the assignment replaces any user table set above it. Use `config.set_environment_variables = config.set_environment_variables or {}` then `config.set_environment_variables.SHELL = "<zsh>"`.
- **Using `sweep_tweaks` on a tool removal**: it disables every bundle (D-11 forbids).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Compare-before-commit | a new mtime check | `shellrc._snapshot/_snapshot_matches` (promote to `atomic.py`) | Already binds bytes to device and inode, and fails closed on error |
| Atomic write through a symlink | `path.write_text` | `atomic.atomic_write_text` | It resolves a dotfile symlink and keeps the mode |
| Owned rc block | a regex edit of `.zshenv` | `shellrc.apply_block/strip_block` | Idempotent, with last-begin pairing |
| OMZ source-line detection | a new regex | `omz._sourced_oh_my_zsh` (omz.py:147) | It already handles `.`/`source`/`;` forms |
| environment.d file | a new writer | `env_redirect` (generalized) | Sentinel ownership, lexical ordering, the macOS branch |
| Re-parse guard | ad-hoc diffing | the `apply_registry_edits` "expected doc == new doc" pattern | Proven in 18 D-09 |
| Running a step in a cwd | `os.chdir` | `session.in_directory` | Thread-safe, already reviewed |

**Key insight:** every format edit in this repo is a text splice plus a semantic re-parse. Format libraries would still need the guard, and they rewrite more bytes than the splice does.

## Common Pitfalls

### Pitfall 1: Receipt re-records wipe `hooks`
**What goes wrong:** After `u` on codegraph, or a repair, `receipt.hooks` becomes `{}`. The next pass shows `≈` for every host, and removal unregisters nothing.
**Why:** `_build_receipt(...)` always passes `hooks={}` (receipts.py:246). `record()` reads `previous` but carries only proofs forward.
**How to avoid:** `record` merges `previous.hooks` when the method kind is unchanged. Add a test for an update re-record.

### Pitfall 2: Unregister without a recorded host list, or with a tampered one
The receipt is user-writable JSON. Filter the recorded hosts through the code-owned target map (closed set) before building the argv. An unknown id is dropped, never passed through.

### Pitfall 3: Cursor CLI owns its file
Docs: "Some fields are CLI-managed and may be overwritten" and the CLI "performs self-repair for missing fields" [CITED: cursor.com/docs/cli/reference/configuration]. On this host `approvalMode` is `allowlist`, `attribution` is `{'attributeCommitsToAgent': True, 'attributePRsToAgent': True}`, and `model` is an object (`modelId`, `displayModelId`, ...). Absent-only writes are therefore no-ops, and a cursor-agent running at the same time can overwrite a splice. See Open Q5/Q6.

### Pitfall 4: Claude re-serializes `settings.json`
Claude Code writes the user settings file itself (`/config`, accepting the bypass dialog writes `skipDangerousModePermissionPrompt: true` [CITED: settings-reference]). After that, our exact `inserted_text` is gone, so revert needs the member-locate fallback. Byte-identical revert is guaranteed only when nobody else wrote the file. Claude settings are strict JSON ("a `//` comment or a trailing comma is a syntax error" [CITED: code.claude.com/docs/en/settings]), so the splice must never leave a trailing comma.

### Pitfall 5: opencode file name
Docs name `~/.config/opencode/opencode.json` and say JSON and JSONC are both supported [CITED: opencode.ai/docs/config]. This host has only `opencode.jsonc`. Rule: write the one that exists (`.jsonc` first). When both exist, refuse with a `≈` reason. When neither exists, create `opencode.json`. Treat both as JSONC.

### Pitfall 6: Marker-dir presence registers hosts the user never installed
`present_harnesses` counts a host as present when only its home dir exists (e.g. `~/.cursor` from the Cursor IDE, `~/.claude` created by another tool) [VERIFIED: skill_lifecycle.py:633-641, model.py:200-218]. This is a behaviour change from `is_installed` (PATH only). It is acceptable under CONF-03, but it must be stated in the hook comment. SPEC already accepts "re-registering a host the user removed by hand" as a `shortcut:` limit.

### Pitfall 7: Deleted alias bundles strand old rc blocks
Once `claude-skip` etc. leave `BUNDLES`, `sweep_policies`/`active_policies` no longer see their marker blocks, so `make uninstall` would leave `# >>> tools-installer tweak:claude-skip >>>` forever. Keep a `LEGACY_ALIAS_BUNDLE_IDS` tuple used only by the migration and the full-uninstall strip. The real host has `claude-skip` enabled today (`alias claude='claude --dangerously-skip-permissions'` was observed in this shell).

### Pitfall 8: Same-run host detection lag
A host installed earlier in the run is visible only after `prepend_path`. The end sweep must recompute presence after the loop.

### Pitfall 9: Prompt and completion ordering
The myshellrc source block is appended to `.zshrc`, and `ensure_zshrc_template` appends `source $ZSH/oh-my-zsh.sh` after existing content. So starship/zoxide init can run before OMZ. Then OMZ's theme overwrites starship's prompt (hence `ZSH_THEME=""`, CONF-11), and zoxide completions miss `compinit` (zoxide README: "must be added _after_ `compinit`"). Test the source-line order in a fresh scratch `.zshrc`. Prefer placing the zoxide/starship bodies so they run after OMZ (e.g. when OMZ is present, `ensure_source` keeps the myshellrc source line after the OMZ source line).

### Pitfall 10: `.zshenv` is not an installer-owned file today
architecture.md: "`apply_block`/`strip_block` applies only to files this installer owns — `~/.myshellrc`, and the rc files it wires a `source` line into". D-15 adds `$ZDOTDIR/.zshenv`, so amend architecture.md in the same change. Resolve the path through the existing `$ZDOTDIR`-aware resolver (the one `zshrc_path(home, environ)` uses).

### Pitfall 11: Every existing kitty/WezTerm user turns `≈` after upgrade
Changing the region body makes `_write_if_changed(write=False)` report drift for every configured terminal. This is intended (SC2), but the UAT should expect it.

### Pitfall 12: Test isolation does not cover the new files
`_GUARDED_DOTFILES = (".myshellrc", ".shellrc", ".bashrc", ".zshrc", ".profile")` [VERIFIED: tests/conftest.py:34]. `.zshenv`, the agent settings files, VS Code `settings.json`, `environment.d/` and the new ledger dir are not fingerprinted. Add `.zshenv`, `.config/environment.d` (dir listing) and `.local/state/tools-installer/config` (dir listing). Do **not** mtime-fingerprint `~/.cursor/cli-config.json` or `~/.claude/settings.json`: the live CLIs rewrite them during a test run (flaky). Assert instead that the ledger dir is absent or unchanged in the real HOME.

## Code Examples

### JSON insert inside a named object (sketch)
```python
# Pattern from verify_registry.apply_registry_edits (verify_registry.py:1040-1058): splice, re-parse, compare.
def _insert_member(text: str, obj_span: tuple[int, int], key: str, value: object) -> str:
    open_brace, close_brace = obj_span           # from a string/comment-aware scanner
    inner = text[open_brace + 1 : close_brace]
    member = f"{json.dumps(key)}: {json.dumps(value)}"
    sep = "," if _strip_jsonc(inner).strip() else ""
    return f"{text[: open_brace + 1]}\n  {member}{sep}{text[open_brace + 1 :]}"
```
The scanner must skip `"..."` strings with escapes, `//` and `/* */` comments (JSONC only), so that a `//` inside a URL string is not taken as a comment.

### TOML top-level insert (Codex)
```python
# approval_policy: "on-request | never | { granular = ... }"; sandbox_mode: "read-only | workspace-write |
# danger-full-access"; both are bare top-level names [CITED: learn.chatgpt.com/docs/config-file/config-reference]
lines = text.splitlines(keepends=True)
first_table = next((i for i, l in enumerate(lines) if l.lstrip().startswith("[")), len(lines))
new = lines[:first_table] + ['approval_policy = "never"\n', 'sandbox_mode = "danger-full-access"\n'] + lines[first_table:]
assert tomllib.loads("".join(new)) == {**tomllib.loads(text), "approval_policy": "never", "sandbox_mode": "danger-full-access"}
```
The host config.toml has top-level `model` and `model_reasoning_effort`, then `[features]` and `[projects."..."]` tables (written by Codex itself).

## Verified Vendor Keys

| Agent / file | Setting | Key and value | Source |
|---|---|---|---|
| Claude `~/.claude/settings.json` (user scope) | auto-approve | `permissions.defaultMode: "bypassPermissions"`; "`auto` and `bypassPermissions` don't take effect from project or local settings ... Before v2.1.257, `bypassPermissions` took effect from any file" | [CITED: code.claude.com/docs/en/settings-reference] |
| Claude | skip dialog | `skipDangerousModePermissionPrompt: true`, scope "User, local, or managed" | [CITED: same] |
| Claude | attribution off | `attribution.commit: ""`, `attribution.pr: ""` (strings; `attribution: false` needs v2.1.281+) | [CITED: same] (drift D9) |
| Codex `~/.codex/config.toml` | auto-approve | top-level `approval_policy = "never"`, `sandbox_mode = "danger-full-access"` | [CITED: learn.chatgpt.com config reference] |
| Codex | attribution | no documented key ("None" found in the full reference) | [CITED: same] |
| opencode | auto-approve | `"permission": "allow"` ("You can also set all permissions at once") | [CITED: opencode.ai/docs/permissions] |
| opencode | attribution | no documented key | [ASSUMED] (not searched in depth) |
| cursor-agent `~/.cursor/cli-config.json` | auto-approve | `approvalMode`: "`allowlist`, `auto-review`, or `unrestricted`" (no default documented) | [CITED: cursor.com/docs/cli/reference/configuration] |
| cursor-agent | attribution | `attribution.attributeCommitsToAgent` / `attributePRsToAgent` booleans, "default: `true`" | [CITED: same] |
| cursor-agent | "CLI ignores the commit opt-out as of 2026-10-04" | not stated in the docs page | [ASSUMED] (keep the UI caveat; re-verify live in a container) |
| pi | approvals | none in core; only via extensions | [ASSUMED] (from CONF-08 text) |
| VS Code `~/.config/Code/User/settings.json` | lean keys | CONF-12 list ("verified in VS Code 1.138"); `chat.disableAIFeatures` listed in the official AI settings reference | [CITED: REQUIREMENTS CONF-12; code.visualstudio.com/docs/agents/reference/ai-settings] |
| VS Code | terminal | `terminal.integrated.defaultProfile.linux` "should be set to the name of an existing profile"; without it "defaults to `$SHELL` on Linux and macOS" | [CITED: code.visualstudio.com/docs/terminal/profiles] |
| tealdeer | cache | `tldr --update` "Update the local cache"; Linux default `~/.cache/tealdeer/` | [CITED: docs.tealdeer.org/stable/print.html] |
| herdr | integrations | `herdr integration install <TARGET>` / `herdr integration uninstall <TARGET>`, `status` lists the path per target | [VERIFIED: herdr 0.9.3 CLI on host] |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Claude `includeCoAuthoredBy: false` | `attribution.commit/pr` strings | Claude Code v2.0.62 | Write `attribution`; `includeCoAuthoredBy` is ignored once attribution is set |
| Claude `bypassPermissions` from any file | user/managed scope only | v2.1.257 | Write only the user file (already the plan) |
| Codex `approval_policy = "on-failure"` | `on-request`/`never`; `on-failure` deprecated, `untrusted` unsupported | current reference | Use `never` |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `codegraph uninstall` also removes the `~/.claude/CLAUDE.md` block and the prompt hook that `install --yes` wrote (audit F2) | Pattern 1 | Leftover codegraph config after removal; verify in a container e2e |
| A2 | opencode reads `opencode.jsonc` from `~/.config/opencode` | Pitfall 5 | Keys written to a file opencode ignores (host evidence: only `.jsonc` exists and opencode works) |
| A3 | The Cursor CLI still ignores the commit attribution opt-out | Vendor keys | Wrong UI caveat |
| A4 | Codex rewrites `config.toml` with format preservation (its own `[projects]` writes) | Pitfall/revert | Byte-identical revert fails after Codex writes; the member-locate fallback covers it |
| A5 | VS Code merges a user `terminal.integrated.profiles.linux` with the defaults, and the built-in `zsh` profile resolves `zsh` via PATH | CONF-12 | A desktop-launched VS Code without brew on PATH may not find a brew zsh; consider an absolute-path profile (Open Q8) |
| A6 | The tealdeer macOS cache is `~/Library/Caches/tealdeer` | CONF-06 | Wrong `config_paths` entry on macOS (harmless: a missing path is skipped) |
| A7 | pi permission extensions are detectable from `~/.pi/agent` (extensions dir or settings packages) | CONF-08 pi note | The note may be missing or wrong |
| A8 | opencode has no attribution key | CONF-09 | Missed setting |

## Open Questions (each with a recommended answer)

1. **graphify hook pair (CONF-01).** Facts: there is no graphify hook today (SAFE-02). graphify 0.9.54's global `install --platform <p>` copies a skill into `~/.<host>/skills/graphify/` and appends to `~/.claude/CLAUDE.md` (claude), and for `cursor`/`opencode` it writes into `Path(".")`. `graphify uninstall` ignores `--platform` and strips the CWD's CLAUDE.md/AGENTS.md. `graphify claude uninstall` removes the user skill **and** strips `./CLAUDE.md`. **Recommend:** keep graphify out of the hook table in Phase 23 (it is skill-pack content, which is out of scope since 2026-11-02, and SAFE-02 is locked). Amend CONF-01/SC1 to "codegraph and herdr". If the user wants it anyway: claude/codex only, register/unregister run via `in_directory(<empty scratch dir>)`, plus a container probe.
2. **rtk under CONF-03.** `_rtk_register` calls `present_agent_hosts`, which CONF-03 deletes. **Recommend:** delete the `rtk-register` hook and `postinstall = "rtk-register"` now, since the user said the installer does not register rtk. Leave the rtk catalog entry for the later removal phase. Alternative: a mechanical signature port, with a `shortcut:` comment.
3. **Policies rows.** "One row per agent" for two settings. **Recommend:** one Policy row per (agent, setting) that has a documented key: Claude ×2, Codex ×1, opencode ×1, cursor ×2. VS Code gets 3 rows (lean, AI off, auto-update off). Run `/gsd-ui-phase 23` for the review questions, the keyed sensitive prompt and these rows (`workflow.ui_phase: true`).
4. **volta shell init.** Volta has no init command, and its PATH is already managed. **Recommend:** a volta bundle exporting only `VOLTA_HOME="${VOLTA_HOME:-$HOME/.volta}"`, or drop volta from CONF-04 with a note. Ask the user. Default to keeping the minimal export so that "six tools" holds.
5. **cursor-agent absent-only rule.** The CLI fills in defaults. **Recommend:** for cursor only, treat a key whose value equals the documented default (`attribution.* = true`) as replaceable. Record the prior value in the ledger and restore it exactly on revert. `approvalMode` has no documented default, so it stays "set by you" unless absent. This needs a user decision, because it relaxes the SPEC prohibition.
6. **cursor-agent model migration (CONF-10).** `model` is a CLI-managed object, always present. **Recommend:** strip the alias and report "set the default model with `/model` in cursor-agent (was gpt-5.6-sol-high)". Write nothing, since an object write would be "set by you" anyway and fragile.
7. **VS Code `update.mode` on Linux.** **Recommend:** write it on macOS (LIFE-10 landed). On Linux, write it only if the refresh pass reports a newer VS Code tarball (check `version_status` for vscode in the planner's first task). Otherwise skip it on Linux with a note.
8. **VS Code terminal profile.** **Recommend:** `terminal.integrated.defaultProfile.linux: "zsh"` only (absent-only), plus the CONF-05 `environment.d` option for desktop launches. No custom profile object.
9. **Where the alias migration runs.** **Recommend:** a pure `installer/` function called once from the composition root at launch (TUI and headless) and from `make uninstall`. It is idempotent: no legacy block means no action. The user's earlier opt-in through the alias is the consent. Report the migration in the run summary.

## Environment Availability

| Dependency | Required By | Available (host, read-only probe) | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv / Python | everything | ✓ | project venv | — |
| codegraph | CLI-flag verification | ✓ | 1.6.2 | tests use a fake runner |
| herdr | CLI-flag verification | ✓ | 0.9.3 | fake runner |
| graphify | source reading | ✓ | 0.9.54 | — |
| zsh | CONF-05 tests | ✓ | linuxbrew zsh | tests inject `lookup` |
| tldr (tealdeer) | CONF-06 | ✗ on host | — | fake runner (no real run needed) |
| podman/docker | container probes (A1, A3) | via `scripts/detect-container-runtime.sh` | — | mark as human/UAT |

The real host is never mutated: no `make setup/fix/uninstall`, and no write to real rc or agent settings. Every new test runs under the autouse `sandboxed_home` scratch HOME.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-xdist + coverage (`fail_under = 90`, pyproject.toml:60) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`; `tests/conftest.py` (sandboxed HOME, receipts, bin dir) |
| Quick run command | `uv run pytest tests/test_postinstall.py tests/test_agent_settings.py -x -q` |
| Full suite command | `make validate && make test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | Install codex with codegraph present → register for codex once, receipt gains `codex`; remove codegraph → `uninstall --target <recorded> ... --keep-cli` before paths | unit (fake runner) | `uv run pytest tests/test_postinstall.py tests/test_uninstall.py -k hook -x` | ✅ files, ❌ tests |
| CONF-01 | Update/repair re-record keeps `hooks` | unit | `uv run pytest tests/test_receipts.py -k hooks -x` | ✅ / ❌ |
| CONF-01 | `≈` when present∩supported−recorded ≠ ∅; RECONFIGURE registers | unit | `uv run pytest tests/test_version_status.py tests/test_session.py -k hook_register -x` | ✅ / ❌ |
| CONF-02 | Installing codex re-runs codegraph for codex only, never claude | unit | `uv run pytest tests/test_session.py -k resync -x` | ✅ / ❌ |
| CONF-03 | No `_AGENT_HOST_IDS`/`present_agent_hosts` in `installer/` | grep test | `uv run pytest tests/test_postinstall.py -k one_host_list -x` | ✅ / ❌ |
| CONF-04 | ×6 tools: yes → bundle ON; no → OFF, no health state; removal disables only that bundle; headless never | unit, parametrized | `uv run pytest tests/test_post_install.py tests/test_tweaks.py -k shell_init -x` | ✅ / ❌ |
| CONF-05 | `zsh -c 'echo $SHELL'` in a scratch HOME with `.zshenv` prints the zsh path; kitty/WezTerm region carries SHELL; absent terminal no `≈`; WezTerm keeps a user env table | unit (+ one real-zsh subprocess with HOME=tmp) | `uv run pytest tests/test_terminal_shell.py tests/test_shellrc.py -k shell_env -x` | ✅ / ❌ |
| CONF-05 | `environment.d` SHELL opt-in writes/removes the owned conf; Bun redirect unchanged | unit | `uv run pytest tests/test_env_redirect.py -x` | ✅ / ❌ |
| CONF-06 | `tldr --update` once on install and once on `u`; failure → warning | unit | `uv run pytest tests/test_postinstall.py tests/test_update.py -k tealdeer -x` | ✅ / ❌ |
| CONF-07 | `ZSH=/custom/omz` → the template exports `/custom/omz`; nothing under `~/.oh-my-zsh` | unit | `uv run pytest tests/test_omz.py -k custom_zsh -x` | ✅ / ❌ |
| CONF-08 | Keys written only when absent; comments/unrelated keys kept; `acceptEdits` stays "set by you"; opt-out byte-identical; invalid JSON/TOML untouched + `≈`; CAS retry once | unit, fixtures per format | `uv run pytest tests/test_agent_settings.py -x` | ❌ Wave 0 |
| CONF-09 | Claude `""` strings and cursor booleans written and reverted; Codex/opencode/pi "no documented key"; cursor caveat shown | unit | `uv run pytest tests/test_agent_settings.py -k attribution -x` | ❌ Wave 0 |
| CONF-10 | An enabled `claude-skip` rc → no alias + Claude keys; Policies lists none of the four; uninstall strips a legacy block | unit | `uv run pytest tests/test_tweaks.py tests/test_policy_tweaks.py -k legacy_alias -x` | ✅ / ❌ |
| CONF-11 | No `ZSH_THEME` → `robbyrussell` before the source line; `agnoster` unchanged; starship → `""` | unit | `uv run pytest tests/test_omz.py -k theme -x` | ✅ / ❌ |
| CONF-12 | JSONC with comments plus one user key: only absent keys added, opt-out byte-identical, defaultProfile zsh, two separate questions | unit | `uv run pytest tests/test_agent_settings.py -k vscode -x` | ❌ Wave 0 |
| SC4 | zsh reinstall with no `chsh` → terminal sync called; promise text matches | unit | `uv run pytest tests/test_execute_screen.py -k chsh -x` | ✅ / ❌ |

### Sampling Rate
- **Per task commit:** the quick command for the touched files.
- **Per wave merge:** `make validate && make test`.
- **Phase gate:** full suite green, plus `make e2e` (container) for the codegraph unregister and the leftover check, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_agent_settings.py`: fixtures for Claude (strict JSON), cursor (strict JSON with CLI defaults), opencode `.jsonc` and `.json`, VS Code JSONC (both comment styles, trailing commas, `//` inside a URL string), Codex TOML with `[features]`/`[projects."..."]` tables, invalid file per format, missing file.
- [ ] `tests/conftest.py`: extend the real-home guard (`.zshenv`, `.config/environment.d`, `.local/state/tools-installer/config`) without fingerprinting live CLI files (Pitfall 12).
- [ ] A fake runner fixture that records argv per hook (exists in `test_postinstall.py`; reuse it).

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes (local) | Writes only under the user's HOME; zero sudo; `environment.d` user dir only |
| V5 Input Validation | yes | Parse-or-refuse for every settings file; closed hook/target maps; receipt/ledger values filtered through code-owned allowlists |
| V6 Cryptography | no | — |
| V12 Files | yes | `O_NOFOLLOW` snapshot, atomic replace, symlink resolution, compare-before-commit |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hand-edited `receipt.hooks` widens unregister to unrelated hosts | Tampering | Intersect with the code-owned target map; never `--target all` |
| Hand-edited ledger makes revert delete user keys | Tampering | Revert only key paths from the code-owned key table, only when the current value equals the ledger value |
| Settings file swapped between read and write | Tampering (TOCTOU) | `_snapshot_matches` before replace; retry once then `≈` |
| Auto-approval enabled silently | Elevation | Default off; headless never; explicit "yes" only; prohibition test |
| graphify writes into the CWD | Tampering | Not run (Open Q1) or run only in an empty scratch cwd |
| Shell-init body injection | Tampering | Bodies are code constants; no registry or user string reaches them |

## Sources

### Primary (HIGH confidence)
- In-repo files read this session: `installer/postinstall.py`, `receipts.py`, `uninstall.py`, `app.py` (remove_tool), `session.py`, `engine.py`, `update.py`, `terminal_shell.py`, `omz.py`, `tweaks.py`, `post_install.py`, `model.py`, `skill_lifecycle.py`, `version_status.py`, `env_redirect.py`, `agent_env.py`, `agent_policy.py`, `shellrc.py`, `atomic.py`, `execute_screen.py`, `wizard_app.py`, `verify_registry.py`, `registry.toml`, `tests/conftest.py`
- CLI help on host: codegraph 1.6.2 (`install`, `uninstall`), herdr 0.9.3 (`integration`), graphify 0.9.54 (`--help` + `install.py` source)
- https://code.claude.com/docs/en/settings and /settings-reference: defaultMode scope, skip dialog, attribution strings

### Secondary (MEDIUM confidence)
- https://learn.chatgpt.com/docs/config-file/config-reference: Codex `approval_policy`, `sandbox_mode`
- https://opencode.ai/docs/permissions/ and /docs/config/: `"permission": "allow"`, JSONC support
- https://cursor.com/docs/cli/reference/configuration: `approvalMode`, `attribution`, self-repair
- https://code.visualstudio.com/docs/terminal/profiles; https://code.visualstudio.com/docs/agents/reference/ai-settings.md
- https://docs.tealdeer.org/stable/print.html; starship.rs/guide; direnv.net/docs/hook.html; zoxide, fzf and fnm READMEs; docs.volta.sh/advanced/installers

### Tertiary (LOW confidence)
- The Cursor commit-attribution caveat date (from CONF-09 text only)

## Metadata

**Confidence breakdown:**
- Code reality/drift: HIGH. Every drift row was read from the source this session.
- Vendor keys: HIGH for Claude, Codex, opencode and cursor (official docs). MEDIUM for VS Code profiles. LOW for the pi/cursor caveats.
- Architecture: MEDIUM-HIGH. It reuses the existing patterns; graphify and the cursor rules depend on user decisions.
- Pitfalls: HIGH. Most are visible in the code or on the host.

**Research date:** 2026-11-04
**Valid until:** 2026-11-18 (vendor CLIs move fast; re-check codegraph/herdr flags at execution)
