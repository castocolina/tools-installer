# Phase 20: Install plan with dispositions - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-14
**Phase:** 20-install-plan-with-dispositions
**Mode:** assumptions (`--analyze --all --batch`), jev screening, best-over-easy
**Areas analyzed:** Plan model; Execution and outcomes; Headless; Waiting for state; `r`, `a`, selection, wording

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with jev-fast-decision injected and best-over-easy in its brief. It made 44 tool calls and no network calls.

| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Plan types and `build_plan` in session.py; one ordering via `resolve_dependencies` | Confident | session.py:116; TA §3 |
| One `RowOutcome` per row, including skip/blocked (best) vs extend `Summary` (easy) | Likely → best | session.py:191-217; render.py:60-79; update.py:151-159 (three vocabularies today) |
| Dragged dep listed once under its first dependent | Confident | deps.py:59-72 |
| Dragged misconfigured/outdated → skip (TA) vs mirror the direct mapping | Likely | TA §3.1; SPEC R3 |
| One `execute_plan` in session.py | Confident | execute_screen.py:573-671 |
| RECONFIGURE = `reapply_post_install` + terminal sync | Likely | engine.py:200-216 |
| Terminal sync on any non-skip/blocked row | Confident | wizard_app.py:2960-2966 |
| Headless on `build_plan`/`execute_plan`; delete audit.py | Confident | app.py:127-197; TA §3.2 |
| `deps.py:111` silent skip → BLOCKED row | Likely → best | deps.py:111; render.py:33-45 |
| Wait: the screen runs its own targeted refresh, cancelled by a token | Likely | execute_screen.py `_run_updates` |
| `r` set owned by the screen and passed in | Confident | TA §3 signature |
| `a` needs no change (`selectable` assumed to exclude unavailable) | Likely | tool_browser.py:300-308 |
| Retained selection from outcomes; `esc` keeps everything | Confident | wizard_app.py:2797 |
| Wording fixed in place | Confident | catalog_tui.py:917-924; update.py:289-296 |

## Orchestrator findings (beyond the analyzer)
- `reapply_post_install` re-runs the registry's generic `post_install` actions. It fixes none of 19's misconfiguration signals (skill on a harness, terminal shell, pnpm group), so "will reconfigure" would have been a false promise. Each signal needs a typed fix step.
- A screen-run targeted refresh would be a second refresh path beside 19's single owner worker.
- The catalog adapter's `selectable` is the default `lambda _: True` (`tool_browser.py:76`; catalog_tui sets no override), so `a` selects unavailable rows today.

## jev screening

One Laya call per item, then TypeSafe direct (`jev-latest` → `jev-1.13.0`). Summaries only.

| Item | Laya | TypeSafe | Outcome |
|---|---|---|---|
| Dragged outdated/misconfigured | mirror_direct p=0.50 (needs fallback) | skip_already_present p=0.60 (needs fallback) | Asked the user: skip (D-03) |
| Wait mechanism | await_single_owner p=0.58 (needs fallback) | await_single_owner p=1.00 | D-13 |
| Reconfigure | generic_reapply p=0.67 (needs fallback) | typed_fix_steps p=0.95 | D-06; 19 D-20 added |
| Outcome model | extend_summary p=0.75 | row_outcome_list p=0.99 | D-08; Laya overruled on the single-source rule |

## Corrections Made

### Dragged dependencies
- **Question:** a present but outdated or misconfigured dragged dependency: skip it, or treat it like a direct selection?
- **User choice:** skip and show its health (recommended). SPEC R3 was amended.

### Unavailable rows
- **Original assumption:** `a` already skips them.
- **Finding:** `selectable` is always true.
- **User choice:** not selectable by space or `a` (recommended) (D-05).

## Reviewed Todos
- GSD per-repo (0.6), pi repair (0.6), pnpm shims (0.2) and Playwright Chrome (0.2): not folded.
