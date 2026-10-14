# Phase 23: Configuration as a lifecycle step - Context

**Gathered:** 2026-10-14 (assumptions mode, `--analyze --all --batch`, jev ladder, best-over-easy)
**Status:** Ready for planning

<domain>
## Phase Boundary

Configuration is applied, checked and reversed together with its tool:
- reversible agent-host hooks that follow hosts in and out;
- shell init offered and removed with its tool;
- terminals on zsh with a correct `SHELL`;
- agent behaviour in each agent's own settings instead of aliases;
- every write touches only what the installer owns.

The WHAT is locked in `23-SPEC.md` (R1–R12). R8 was amended in this session: written keys go to a per-agent config-write ledger, not to install receipts. This file locks the HOW.

Out of scope:
- herdr/Alacritty onboarding (24).
- pi hook targets: unverified vendor support, see Deferred.
- The pi host repair todo.

**Prerequisites:**
- 17: D-05 atomic writes with restore, D-06 compare before commit, D-11 typed settings load.
- 19: D-05 receipts with `hooks`, D-16 the dry-run contract, D-20 `ConfigStep`.
- 20: D-06 RECONFIGURE, D-07 `execute_plan`, D-11 terminal-sync trigger, D-12 headless.
- 21: D-05 `request_refresh`.
- 22: D-03 `{omz_root}`, D-06/D-07 the removal order with the empty hook slot, D-01/D-11 `config_paths`.

None of these has landed as of 2026-10-14.
</domain>

<decisions>
## Implementation Decisions

**Decision rule:** best over easy. jev ladder: Laya is accepted only with high confidence of its own. Otherwise TypeSafe, and if that's unsure too, full-model reasoning.

### Hooks, hosts and re-sync (R1, R2, R3)
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

### Agent settings writer (R8, R9, R10, R12)
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

### Shell init, OMZ theme and `$ZSH` (R4, R7, R11)
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

### zsh everywhere (R5)
- **D-14:** This phase actually **adds** the `sync_terminal_shells(write=False)` parameter (`terminal_shell.py:383-456`). 19 D-16 assumed it, but the code has none.
  - In dry-run mode it returns the terminals that would change and writes nothing.
  - The kitty body gains `env SHELL=<zsh>` and the WezTerm body gains `config.set_environment_variables = { SHELL = "<zsh>" }`, inside the **same** owned region (`_replace_owned_region` :72-108). No second region is added.
- **D-15:** The `~/.zshenv` managed `export SHELL=<real zsh path>` uses the `shellrc.apply_block`/`strip_block` owned-block pattern, not `terminal_shell`'s region code.
- **D-16:** The `environment.d` `SHELL` question (asked, default off) generalizes `env_redirect.CacheRedirect`/`target_path` (`env_redirect.py:42-78, 122-134`) to accept an absolute resolved value. That keeps one `environment.d` writer, with the ownership sentinel and macOS/Linux branch.
  - The Bun redirect is regression-tested.
- **D-17:** The terminal sync is triggered by 20 D-11 (any row in {INSTALL, REPAIR, REINSTALL, UPDATE, RECONFIGURE} ran). This replaces `wizard_app.py:2960`.

### tealdeer (R6)
- **D-18:** `tealdeer-cache` is a non-sensitive `PostinstallHook` that runs `tldr --update` on install and update. Update re-dispatches through `update.py`'s `_run_postinstall` (`:200, 309, 343`).
  - A failure becomes a returned warning, following the `except CommandError` pattern (`postinstall.py:236-239`), not a row failure.
  - The cache dir goes in tealdeer's `config_paths` (22 D-01), not in the receipt artifacts.

### Claude's Discretion
- Plan and wave order. Suggested:
  1. One host list and the hook pairs, with `receipt.hooks`.
  2. `agent_settings` with the guarded splice and the ledger.
  3. The run-level questions and the alias migration.
  4. Shell init, OMZ root and theme.
  5. zsh everywhere.
  6. tealdeer.
- The ledger file schema details and the exact JSONC comment-stripper.

### Folded Todos
None.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/23-configuration-as-a-lifecycle-step/23-SPEC.md`: locked R1–R12 (R8 amended 2026-10-14)
- `.planning/research/2026-10-13-target-architecture.md`: §5 (receipt hooks), §6 (trigger model, keep/delete), §9.2 O4, O11
- `.planning/phases/18-registry-truth-and-drift-guard/18-CONTEXT.md`: D-09 (guarded splice precedent)
- `.planning/phases/19-one-tool-state-with-health-plus-receipts/19-CONTEXT.md`: D-05, D-16, D-20
- `.planning/phases/20-install-plan-with-dispositions/20-CONTEXT.md`: D-06, D-07, D-11, D-12
- `.planning/phases/22-method-lifecycle-contract/22-CONTEXT.md`: D-01, D-03, D-06, D-07, D-11
- `.planning/research/audit-2026-10-13/E-registry-user-part2.md:139` (cursor `cli-config.json`)
- `.planning/REQUIREMENTS.md`: CONF-01..12
- `.claude/architecture.md`, `AGENTS.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `skill_lifecycle.present_harnesses`/`HARNESS_PRESENCE` (includes pi)
- `post_install._set_login_shell` (a sensitive action with `confirm is None` → skip)
- `uninstall.active_policies`/`sweep_policies`; `shellrc.apply_block`/`strip_block`
- `omz.omz_root`, `_sourced_oh_my_zsh`, `ensure_zshrc_template(root=)`
- `env_redirect.CacheRedirect`/`render_conf`/`environment_d_dir`
- `atomic.atomic_write_text`; `tomllib`

### Established Patterns
- Guarded text splice plus a semantic re-parse (18 D-09) instead of format libraries.
- Inject environment facts once at the caller (`home`, `which`, hosts), not inside each callee.
- Asked actions default off; headless never opts in.

### Integration Points
- `execute_plan` → the re-sync sweep, the run-level answers, and the terminal sync
- `RemovalPlan.argv` hook slot ← `receipt.hooks`
- `agent_settings` ↔ the config ledger ↔ Policies agent rows ↔ tool removal
</code_context>

<specifics>
## Specific Ideas

- Host evidence (2026-10-13): every terminal runs zsh with `SHELL=/bin/bash`, and `ZSH_THEME` is unset. These are the acceptance anchors for D-14/D-15 and D-13.
</specifics>

<deferred>
## Deferred Ideas

- **pi hook targets** (codegraph/rtk/graphify for pi): unverified vendor support. A later phase adds them to the id maps once confirmed.
- **pi host repair** (`2026-10-13-repair-pi-install-and-sync-models`, 0.9 for 22 and 0.6 here): dangling Volta symlinks, the duplicate skill dir, `pi_sync.py`. This is host repair plus a reviewed handoff, not lifecycle config. It stays a pending todo (a quick task). Its "add pi to `_AGENT_HOST_IDS`" item is made moot by D-01/D-05.

### Reviewed Todos (not folded)
- GSD per-repo (0.6), Playwright Chrome (0.6), pnpm shims (0.2, Phase 21).
</deferred>
