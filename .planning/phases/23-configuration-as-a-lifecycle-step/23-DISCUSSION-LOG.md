# Phase 23: Configuration as a lifecycle step - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-14
**Phase:** 23-configuration-as-a-lifecycle-step
**Mode:** assumptions (`--analyze --all --batch`). This is a batch run under the user's /goal: jev ladder, best-over-easy, non-blocking questions deferred.
**Areas analyzed:** Hooks and hosts; Agent settings writer; Shell init, OMZ theme and `$ZSH`; zsh everywhere; tealdeer and install-time questions

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with jev-fast-decision injected. It made 55 tool calls and no network calls. Its output tripped the harness's "settings-json" instruction-pattern filter. That was only because it quotes the agent settings keys from the SPEC; there was no injected instruction.

| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Delete `_AGENT_HOST_IDS`; hooks take the `present_harnesses` set | Likely → best | postinstall.py:26-46, 67, 149, 250, 277-301; skill_lifecycle.py:174-192, 234-242; engine.py:168 |
| `receipt.hooks` sorted host tuple; `≈` = present ∩ supported − recorded | Confident | 19 D-05; TA §1, §5 |
| Re-sync: one sweep at the end of `execute_plan` | Likely → best | 20 D-07/D-11 |
| Unregister from the receipt hosts, before the remove argv | Confident | SPEC prohibitions; 22 D-06 |
| pi not added to hook id maps | Likely → best | id maps list 4 hosts only |
| New `agent_settings` writer, not `agent_policy._write_json` | Confident | agent_policy.py:85-122, 231-252; agent_env.py:21-63 |
| Provenance in the receipt vs a separate ledger | Likely | TA §5 |
| JSONC/TOML: tomlkit vs hand-rolled | Unclear | pyproject (3 deps); model.py tomllib only |
| CAS for VS Code rewrites follows 17 D-06 | Confident | atomic.py:34-130 |
| Alias bundles deleted with the migration | Confident | tweaks.py:118-141, 155-217 |
| Shell-init via the `source_shell_init` sensitive action | Confident | model.py:49, 55; post_install.py:57-69 (no dispatch today) |
| Bundle disabled per tool (scoped sweep) | Likely → best | uninstall.py:401-446, 533-558 |
| OMZ `$ZSH` already correct? | Unclear → **verified bug** | omz.py:432-454: `write_plugins` calls `ensure_zshrc_template` without `root` |
| One `set_theme` writer | Likely → best | omz.py:147-153, 185-227 |
| `write=False` must be added | Confident | terminal_shell.py:383-388 (no parameter) |
| SHELL lines inside the existing owned regions | Likely → best | terminal_shell.py:72-108, 150-170, 420-422 |
| `.zshenv` via shellrc blocks | Likely | shellrc.py |
| `environment.d` SHELL via a generalized CacheRedirect | Unclear → best | env_redirect.py:42-78, 122-134 |
| tealdeer non-sensitive hook; cache in `config_paths` | Likely | postinstall.py:236-239; update.py:200, 309, 343 |
| Run-level questions vs memoized per-row confirm | Unclear | post_install.py:35; execute_screen.py:828-838 |
| Headless never opts in | Confident | execute_screen.py:604; post_install.py:62 |

## jev screening (ladder)

| Item | Laya (prob / own confidence) | TypeSafe | Outcome |
|---|---|---|---|
| Settings provenance | config_ledger 0.58 / 0.02 (needs fallback) | config_ledger 0.95 | D-08; SPEC R8 amended |
| Format writer | guarded_splice 0.43 / 0.04 (needs fallback) | guarded_splice 1.00 | D-07 |
| Run-level questions | run_level_review 0.55 / 0.01 (needs fallback) | run_level_review 1.00 | D-09 |
| Hook hosts | hook_calls_itself 0.71 / **0.13** | inject_hosts 0.96 | D-01; Laya's own confidence was too low to accept |

## Orchestrator findings
- **Ledger, not receipt.** SPEC R8 said keys are recorded "in the receipt". But agents installed by the user have no install receipt, and creating one would make them removable (19 D-10). So the keys go to a per-agent config-write ledger. SPEC amended.
- **CONF-07 is a real bug:** `write_plugins` → `ensure_zshrc_template(zshrc_path)` without `root`.
- **19 D-16** assumed `write=False` already existed. It doesn't; 23 D-14 adds it.

## Corrections Made
None asked. Nothing blocked a later phase.

## External research flagged
- Codex `config.toml` placement of `approval_policy`/`sandbox_mode` (top level?).
- Vendor unregister commands: `codegraph uninstall --keep-cli`, `rtk init -g --uninstall`, `graphify <host> uninstall`, `herdr integration uninstall`.
- VS Code JSONC tolerance (trailing commas, both comment styles).
- Whether the cursor-agent attribution opt-out is still ignored (stated as of 2026-10-04).
- pi target support in codegraph/rtk/graphify (deferred).
