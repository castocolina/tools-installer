# Phase 25: Lean - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-14
**Phase:** 25-lean
**Mode:** assumptions (`--analyze --all --batch`). This is a batch run under the user's /goal: jev ladder, best-over-easy, non-blocking questions deferred.
**Areas analyzed:** Reachability and deletion; Agent-policy fate; Composition; `wizard_app` split and log bound

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with jev-fast-decision injected. It made 71 tool calls, used codegraph caller graphs, and read Textual's `_rich_log.py` source.

| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Permanent AST import-graph test; vulture secondary | Likely → best | policy.py:192, 251 (lazy imports); pyproject.toml:60; Makefile:35-43 |
| Questionary chooser: re-trace control flow before deleting | Likely | setup.py:300-349, 1459-1487; app.py:101-124; G#9 |
| `audit.py` already gone in 20 | Confident | 20 D-12 |
| Agent-policy trio dead; 23 D-06 "audit role" contradiction | Likely | grep and codegraph: callers only in policy.py/agent_policy.py |
| Narrow compose move, names kept | Likely → best | setup.py:755-1211; tests/test_setup.py:658, 1325-1378 |
| Constants: single definition in compose | Likely → best | setup.py:99-110 |
| Strict pyright fixes small | Likely | no questionary in `_build_app` |
| 5-module split; no F14 merge | Confident / Likely | wizard_app.py class spans; audit :313 |
| Message classes decided at execution (AR-04 vs F15) | Unclear → best | TA :36; 21 D-05/D-06 |
| RichLog trims silently, so we need our own counter | Likely | textual `_rich_log.py:264-267` |

## jev screening (ladder)

| Item | Laya (prob / own confidence) | TypeSafe | Outcome |
|---|---|---|---|
| Reachability mechanism | permanent_ast_test 0.52 / 0.00 (needs fallback) | 1.00 | D-01 |
| Log notice placement | header_label 0.64 / 0.06 (needs fallback) | in_log_rewrite 0.61 (needs fallback) | **Full model (D-08):** label above the log |
| Compose scope | move_everything 0.62 / 0.04 (needs fallback) | narrow_move 0.99 | D-05 |

## Orchestrator findings
- **23 D-06 corrected:** "`apply_agent_permissions` keeps its read-only audit role" had no caller behind it. 23 now reuses `agent_env.AgentAdapter` for agent paths (one table, extended with cursor-agent and VS Code). The audit and guidance modules are left to 25's reachability check.
- **The analyzer misread the log notice as "notice last".** The SPEC says the *newest line* is last. That rules out keeping the notice inside the log without an O(n) rewrite.

## Deferred confirm (non-blocking)
- R4 "the log shows one line saying how many were dropped": built as a one-line label at the top of the log panel, not as a line inside the RichLog buffer.

## Corrections Made
None asked.
