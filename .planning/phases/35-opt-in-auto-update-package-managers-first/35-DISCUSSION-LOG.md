# Phase 35: Opt-in auto-update, package managers first - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 35-opt-in-auto-update-package-managers-first
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** the row and per-row default; the planner; the runner; notification and plan-only mode; tests and the container run

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 46 tool calls. It read the schedules, runner, update, resolve, deps, ownership, cli and setup code and the registry; no live or container runs. It did not read `e2e_landing_driver` internals or the bodies of `_parse` and `parse_log` past their signatures.

| Assumption | Confidence | Evidence |
|---|---|---|
| `default_on` field, one `_row_action` line | Confident | schedules.py:1548-1562; `_RECORD_KEYS` :258 |
| New `JobKind.UPDATE_ALL`, own `runner_argv` | Confident | schedules.py:710-714,1488-1492,1701-1704 |
| Daily at 03:00 | Likely | 34 D-06, D-07 |
| View needs no new mechanism | Confident | schedules.py:1493-1497; screens :629 |
| Managers from `Owner`, ordered by ownership edges | Likely | resolve.py:15-31; ownership.py:82-97 |
| Owner groups, closure filtered, transitive skip | Likely | deps.py:40-155 |
| Managers always, dependents when outdated | Unclear | download.py:437-465; update.py:503-505 |
| Pure planner with refusals | Likely | update.py:283 |
| Skip script tools with no declared update (Volta) | Unclear | registry.toml:2310-2320 |
| Runner job reusing `_update` | Confident | schedule_runner.py:320-358 |
| Longer per-job timeout, `_WAIT_BOUND` re-derived | Unclear | schedule_runner.py:51,62-69 |
| `update-all.log`, last run only | Likely | schedules.py:208-212,1803-1811 |
| `updated-today.json` under the run lock | Likely | runlock.py:59-73 |
| Per-tool rows skip only after `update-all` | Unclear | schedules.py:56-65 |
| `failed:` line on any failure | Likely | schedule_runner.py:509-527 |
| `stdin=DEVNULL` in the runner child | Likely | schedule_runner.py:226-233 |
| Notifier once per non-empty run | Confident | 34 D-16 |
| Lock-free `--plan`, manual run allowed | Likely | cli.py:10-90 |
| Dedicated container target | Likely | container-e2e-verify.sh:2627-2690 |

## jev screening

One jev request per item (Laya, then TypeSafe); `needs_fallback` items are decided by own reasoning. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| h1 start time | low 0.59; TypeSafe low 0.48 | **Own reasoning:** daily 03:00 (D-03, ledger) |
| h2 manager order | low 0.51 and 0.63 (install_preference_rank, rejected by the evidence) | **Own reasoning:** ownership edges (D-05, needs confirmation, ledger) |
| h3 failure skips | none_of_these 0.85 (contradicts evidence); second opinion owned_and_needing low 0.58 | **jev overridden / Own reasoning** (D-06, ledger) |
| h4 which tools | low 0.32; TypeSafe low 0.42 | **Own reasoning** (D-07, ledger) |
| h5 refusals in the planner | none_of_these 0.98 (contradicts evidence); second opinion only_while_running low 0.65 | **jev overridden / Own reasoning** (D-08, ledger) |
| h6 Volta | none_of_these 0.91 (contradicts evidence); second opinion skip_with_reason low 0.62 | **jev overridden / Own reasoning** (D-09, needs confirmation, ledger) |
| h7 time limit | low 0.62; TypeSafe low 0.38 | **Own reasoning** (D-11, ledger) |
| h8 detail log | low 0.63; TypeSafe low 0.73 | **Own reasoning:** last run only (D-12, ledger) |
| h9 store | low 0.69; TypeSafe choice dedicated_state_file 0.93 | D-13 |
| h10 per-tool rows | low 0.47; TypeSafe low 0.71 | **Own reasoning** (D-14, ledger) |
| h11 summary line | choice failure_line 0.78 | D-15 |
| h12 stdin | choice close_explicitly 0.87 | D-16 |
| h13 plan and manual run | low 0.54; TypeSafe choice lock_free_preview_manual_run_allowed 0.80 | D-18 |
| h14 e2e scope | none_of_these 0.91 (contradicts evidence); second opinion dedicated_run_real_installs 0.89 | **jev overridden** (D-20) |

## Live facts that changed the plan

- `_RANK` ranks install-method kinds, so it cannot order managers: ROADMAP criterion 2 and AUTOUPD-02 amended, flagged needs confirmation (D-05).
- Volta's only update path rewrites shell rc files: skipped with a reason; SPEC R2 amended, flagged needs confirmation (D-09).
- A global once-a-day rule would change the per-tool rows' 6 h cadence: SPEC R7 clarified (D-14).
- `update-all` must be its own job kind and the CLI `--run-schedule` choices come from `UPDATE_SCHEDULE_IDS`: 34-CONTEXT D-02 amended (D-02).
- The SPEC's "seven existing rows" is eight after phase 34; phase 35 depends on phase 34 being executed (D-21).

## Corrections Made

No corrections — unattended run; the owner reviews the ledger.

## Auto-Resolved

The Unclear items were decided by own reasoning above.

## External Research

Open items are in CONTEXT deferred: `uv self update` under `uv run`, non-interactivity of the manager self-updates, a Volta flag, brew's auto-update after `brew update`.
