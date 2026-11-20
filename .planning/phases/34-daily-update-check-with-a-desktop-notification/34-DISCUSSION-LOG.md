# Phase 34: Daily update check with a desktop notification - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 34-daily-update-check-with-a-desktop-notification
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** the new row; the forced refresh and outdated set; the changed-set rule; notifiers; the self-check; tests

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 47 tool calls. It read the schedules, runner, version-cache and unit code, ran `notify-send --help` and `systemctl --user show-environment` read-only, and made no network or host-mutating calls and sent no notification. It did not read the template bodies beyond the render functions, `test_version_status` internals, the macOS plist session-type key, or whether the repo is public.

| Assumption | Confidence | Evidence |
|---|---|---|
| `JobKind.CHECK_UPDATES`, row appended last | Confident | schedules.py:37-41,71-93 |
| Unit and plist generic; new `runner_argv` branch and runner job | Confident | schedules.py:853-888; schedule_runner.py:454-515 |
| `run_schedule` dispatches by kind | Confident | schedule_run.py:127-148 |
| Row on by default | Likely | schedules.py:1548-1562; 24.2 D-09 |
| `daily` field on Schedule | Likely | schedules.py:847-850,1412-1415 |
| Default start 09:00 | Likely | research :58 |
| Row detail names the permission | Confident | schedules_screen.py:458-482 |
| `stale_after` keyword, about 20 h | Likely | version_cache.py:70-92,216-231 |
| Tools sorted oldest first | Likely | version_status.py:1855-1866 |
| Anonymous by construction | Confident | versions.py:358-373; daemon.py:34-47 |
| Error sink for the first reason | Likely | versions.py:396-409 |
| `outdated_ids` pure function | Confident | version_status.py:271-304,1019-1043 |
| Own state file `update-check.json` | Likely | schedules.py:254-260,1510-1512,1692-1706 (verified) |
| Store set only after a successful send | Likely | SPEC R3 |
| `installer/notify.py` seam | Likely | schedule_runner.py:26-29 |
| Linux argv; bus forwarded then derived | Likely | live systemctl show-environment |
| macOS argv with `on run argv` | Likely | research :49-52 |
| Self-check git commands and skip clause | Likely | setup.py:539-543; run.py:157-171 |
| "Behind" = differs and not a known ancestor | Unclear | SPEC R6 forbids fetch |

## jev screening

One jev request per item (Laya, then TypeSafe); `needs_fallback` items are decided by own reasoning. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| e1 default on/off | none_of_these 0.86 (contradicts evidence); second opinion off_by_default low 0.51 | **jev overridden / Own reasoning:** on (D-05, ledger) |
| e2 daily-only | low 0.61; TypeSafe choice fixed_daily 0.99 | D-06 |
| e3 start time | low 0.67 (midnight); TypeSafe low | **Own reasoning:** 09:00 (D-07, ledger) |
| e4 refresh window | low 0.46; TypeSafe 0.94 `keep the 7-day window` (contradicts SPEC R2) | **jev overridden** by the SPEC (D-09) |
| e5 order | low 0.56; TypeSafe low 0.65 | **Own reasoning:** oldest first (D-10, ledger) |
| e6 failure reason | low 0.68; TypeSafe low 0.58 | **Own reasoning:** first reason plus count (D-12, ledger) |
| e7 state location | low 0.60; TypeSafe key_in_schedules_file 0.83 and again 0.82 as second opinion (contradict the code) | **jev overridden** (D-14) |
| e8 store after failed send | none_of_these 0.80 (contradicts evidence); second opinion store_only_after_success low 0.61 | **jev overridden / Own reasoning** (D-15, ledger) |
| e9 notifier location | low 0.42; TypeSafe choice main_package_module 0.82 | D-16 |
| e10 bus address | none_of_these 0.91 (contradicts evidence); second opinion derive_only low 0.77 | **jev overridden / Own reasoning** (D-17, ledger) |
| e11 macOS argument passing | none_of_these 0.73 (contradicts evidence); second opinion separate_arguments low 0.52 | **jev overridden / Own reasoning** (D-18, ledger) |
| e12 SSH remote | none_of_these 0.97 (contradicts evidence); second opinion public_https_address low 0.51 | **jev overridden / Own reasoning** (D-19, ledger) |
| e13 behind semantics | low 0.48; TypeSafe low 0.67 | **Own reasoning** (D-20, ledger) |

## Live facts that changed the plan

- C1: the runner writes `start` plus the child's last `ok:`/`skipped:`/`failed:` line, so extra log lines would be discarded: clauses fold into the one result line; SPEC R1, R4-R6 amended (D-21). Verified at `schedule_runner.py:345-358`.
- C2: adding a row changes the tests that list every row: SPEC in-scope amended (D-22).
- C3: the R2 backstop "the run lock serializes the refresh with the TUI's" is false; restated (D-24).
- The 24.2 amendment text was already in both files from phase 34's SPEC commit.

## Corrections Made

No corrections — unattended run; the owner reviews the ledger.

## Auto-Resolved

The Unclear item (behind semantics) was decided by own reasoning above.

## External Research

Open items are in CONTEXT deferred: osascript argument passing, `brew outdated` without `brew update`, repo visibility, notify-send's own bus fallback.
