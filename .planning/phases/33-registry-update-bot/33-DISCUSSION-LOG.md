# Phase 33: Registry update bot - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 33-registry-update-bot
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** workflow design; CI dispatch and the proof; the date-only flag; workflow tests and linting; dependabot

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 19 tool calls. It read branch protection and workflow permissions through `gh api` GET calls, ran `--help` and two existing unit tests, and made no remote writes. It did not run the real verify-registry, actionlint, or read `_finalize_report_after_bumps`.

| Assumption | Confidence | Evidence |
|---|---|---|
| `registry-bot.yml`, weekly Monday after the drift run | Likely | verify-registry.yml cron 05:17; test_verify_registry_workflow.py:31-33 |
| Direct `uv run ... --write`, not `make`; exits 0/1/2 continue | Confident | Makefile:27-28; test_write_dates_only_passing_tools |
| Guard step, `if:` on publishing steps | Confident | SPEC R1 |
| Dated branch, fetch plus force-with-lease, env-only branch name | Likely | test_ci_workflow.py:84-86 |
| Older bot branches | Unclear | SPEC silent |
| Concurrency group without cancel | Likely | SPEC R1 |
| Permissions contents/actions/issues write | Confident | repo default read |
| New `registry-bot` label, inline upsert | Likely | upsert_drift_issue overwrites its body |
| Issue close path | Unclear | SPEC R1 no-change rule |
| Share the drift state cache | Likely | verify-registry.yml cache steps |
| Bare `workflow_dispatch` on ci.yml; names unchanged | Confident | tests/test_ci_workflow.py:45-48 |
| Dispatch with `gh workflow run ci.yml --ref` | Confident | research doc :141 |
| Dispatched checks satisfy protection | Likely | `app_id: null` on both contexts |
| Proof design (real bot on a throwaway ref) | Likely | only the bot's token proves the exemption |
| Rollout sequencing | Unclear | default-branch requirement unverified |
| Filter in `_registry_edits_for_write`; flag `--bumps-only` | Confident / Likely | verify_registry.py:1330-1339, :1581 |
| Test layout and lint | Likely | one test file per workflow; no workflow linter |
| dependabot.yml one weekly group | Likely | four action families |

## jev screening

One jev request per item (Laya, then TypeSafe); `needs_fallback` items are decided by own reasoning. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| c1 schedule | low 0.32; TypeSafe choice monday_after_check 0.84 | D-01 |
| c2 overwrite | low 0.57; TypeSafe choice fetch_then_lease 0.97 | D-04 |
| c3 older branches | low 0.36; TypeSafe low 0.54 (leave_for_owner) | **Own reasoning:** bot deletes older (D-05, ledger) |
| c4 concurrency | cancel 0.98 (contradicts evidence); second opinion queue low 0.53 | **jev overridden / Own reasoning** (D-06, ledger) |
| c5 issue label | low 0.56; TypeSafe choice new_label_inline 0.87 | D-08 |
| c6 issue close | low 0.38; TypeSafe low 0.52 (owner_closes) | **Own reasoning:** closing keyword (D-08, ledger) |
| c7 cache | no_cache 0.81 (contradicts evidence); second opinion share_cache 0.94 | **jev overridden** (D-09) |
| c8 proof | none_of_these 0.91 (contradicts evidence); second opinion real_bot_on_throwaway low 0.50 | **jev overridden / Own reasoning** (D-11, ledger) |
| c9 rollout | low 0.50; TypeSafe low 0.60 (all_at_once) | **Own reasoning:** manual first (D-12, ledger) |
| c10 flag name | low 0.43; TypeSafe low 0.66 (bumps_only) | **Own reasoning** (D-13, ledger) |
| c11 test file | none_of_these 0.71 (contradicts evidence); second opinion new_file 0.83 | **jev overridden** (D-15) |
| c12 lint | none_of_these 0.93 (contradicts evidence); second opinion new_gate low 0.68 | **jev overridden / Own reasoning** (D-16, ledger) |
| c13 dependabot grouping | low 0.35; TypeSafe low 0.75 (separate_weekly) | **Own reasoning:** one weekly group (D-17, ledger) |

## Live facts that changed the plan

- Branch protection has no push restrictions and no required reviews (read live): the R3 edge row's "protection is the guard" was wrong and is corrected; the workflow content and its test are the guard (D-07).
- `tests/test_ci_workflow.py:41` and `:52` conflict with the dispatch trigger and the first Dependabot checkout bump: added to the SPEC's in-scope list (D-10). Verified by reading both lines.
- SPEC R1's "no step runs" is read as "no publishing step" (D-03).
- The analyzer called the SPEC's argparse citation (`:1551-1565`) stale; checked: it is correct and the analyzer's range was wrong. The `requires --write` check is at `:1581`.
- Only drawio-desktop is auto-bumpable (2 of 5 pinned methods); Sublime is bumped by hand.

## Corrections Made

No corrections — unattended run; the owner reviews the ledger.

## Auto-Resolved

The three Unclear items (older branches, issue close, rollout) were decided by own reasoning above.

## External Research

Open items in CONTEXT deferred: default-branch requirement for dispatch, closing keyword on a fast-forward push, Dependabot grouping.
