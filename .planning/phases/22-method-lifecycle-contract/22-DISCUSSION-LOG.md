# Phase 22: Method lifecycle contract - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-14
**Phase:** 22-method-lifecycle-contract
**Mode:** assumptions (`--analyze --all --batch`). This is a batch run under the user's /goal: jev ladder (Laya high confidence → TypeSafe → full model), best-over-easy, non-blocking questions deferred to the end.
**Areas analyzed:** Schema and registry data; Removal contract; Zero sudo and writable prefix; Update contract; E2E leftover check

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with jev-fast-decision injected. It made 53 tool calls (codegraph plus reads) and no network calls.

| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| `config_paths` tool-level; script keys method-level | Confident | model.py:324-370, 668; TA §4.2 |
| Denylist from `HARNESS_PRESENCE` dirs relocated to model.py | Likely | skill_lifecycle.py:12, 174 (import cycle) |
| `$ZSH` handling: `~` path vs `sh -c` | Unclear | assets.py:33; executors.py:335-351 |
| 16 stanzas / 14 ids; pi is `host_setup` | Confident | registry.toml (16 `kind = "script"`), :2691-2706 |
| `writable_prefix` = brew only; pure stat | Confident | registry.toml:162-174 |
| `removal_plan` extended with L1 argv and L3 | Confident | TA §4.3 |
| Receipt deleted before config | Unclear | TA §5; 19 D-08 |
| Native `_REMOVAL_COMMANDS` deleted | Confident | ownership.py:1378-1381, 1398-1401, 1447-1475 |
| SDKMAN hint reuses the version probe | Confident | registry.toml:1787-1789 |
| pnpm group warning reuses pnpm_globals | Confident | pnpm_globals.py:438-486 |
| MANUAL via the `_perform` handoff ladder | Confident | engine.py:71-85; executors.py:370-379 |
| `writable_prefix` checked at execute time | Confident (per TA) | TA §4.2 |
| MANUAL as a new outcome word vs BLOCKED | Likely | 20 D-04/D-08 |
| Pinned-app refusal in `update._perform` | Likely → best | update.py:236-317, 253-260 |
| SDKMAN self-update vs candidate refusal kept separate | Confident | update.py:253-260, 337-339 |
| Greedy: registry `auto_updates` flag | Likely | manager_versions.py:52, 158-165 |
| E2E: extend `cmd_pass2` | Likely → best | container-e2e-verify.sh:399-458 |

## jev screening (ladder)

| Item | Laya (prob / own confidence) | TypeSafe | Outcome |
|---|---|---|---|
| Denylist source | literal_denylist 0.61 / 0.03 (needs fallback) | relocate_dirs 0.87 | D-02 relocate |
| Receipt vs config order | receipt_before_config 0.66 / 0.07 (needs fallback) | receipt_before_config 0.98 | D-07 |
| MANUAL decided when | execute_time_only 0.59 / 0.02 (needs fallback) | plan_time_manual 1.00 | D-12 plan-time plus executor re-check |
| Greedy source | per_cask_info 0.39 / 0.02 (needs fallback) | batched_live_info 0.94 | D-16 |
| OMZ `$ZSH` | shell_var 0.85 / **own confidence 0.39** | tilde_path 0.96 | **Full model (D-03):** a closed `{omz_root}` placeholder resolved by `omz.omz_root`. It keeps `$ZSH` truth (CONF-07, omz.py:396-423) without a shell |

Laya's winning probability cleared 0.7 only on `$ZSH`, but its own calibration was 0.39, so I treated it as low confidence and pivoted.

## Orchestrator findings
- MANUAL is decided at plan time, against the analyzer's execute-time pick, because the review promises "what will happen before anything runs". The executor re-checks with the same predicate.
- Greedy: one batched `brew info --cask --installed --json=v2` gives live `auto_updates` without hand-kept data.
- SPEC R8's acceptance was clarified: `<omz root>/tools/upgrade.sh`, resolved in Python.

## Corrections Made
No user corrections. The user's /goal said to defer non-blocking questions, and nothing here blocks a later phase.

## External research flagged (for plan-phase research)
- Vendor uninstall/update commands for the 14 script tools, including confirming `opencode uninstall --keep-config --keep-data`.
- Homebrew `--greedy` with `--json=v2` output shape, and `brew info --cask --installed --json=v2` `auto_updates`.

## Reviewed Todos
- pi repair/sync (0.9) → Phase 23. pnpm shims → 21. GSD per-repo and Playwright Chrome: outside the milestone.
