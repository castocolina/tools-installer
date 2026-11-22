---
phase: 35-opt-in-auto-update-package-managers-first
verified: 2026-11-22T20:00:00Z
status: human_needed
score: 5/5 roadmap criteria verified in code (8/8 requirements covered; AUTOUPD-08 real-run evidence on record, macOS and host runs pending)
covered_files:
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-01-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-02-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-03-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-04-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-05-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-06-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-07-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-07-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-08-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-09-SUMMARY.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md"
  - ".planning/phases/35-opt-in-auto-update-package-managers-first/35-10-SUMMARY.md"
  - "installer/schedule_run.py"
  - "installer/schedules.py"
  - "installer/update_all.py"
  - "installer/update_all_state.py"
covered_digest: "v4:sha256:6794a02db2824d573d8f106783a9c32930af426708c9ee59b2507e5510818928"
behavior_unverified: 0
gaps: []
human_verification:
  - test: "Real macOS run of the nightly update-all row"
    expected: "Row runs on macOS, casks left alone, managers then dependents updated, run log and summary line written"
    why_human: "Only Linux containers were exercised; no macOS host available to agents"
  - test: "Real Bazzite host first night: 03:00 timer firing under systemd and the real outdated set"
    expected: "Timer fires at 03:00, run completes, log lines match the real outdated tools, nothing run as root"
    why_human: "Timer firing and the real outdated set cannot be reproduced in a disposable container"
  - test: "Real desktop notification from the unit after a real run"
    expected: "A desktop notification appears listing updated/failed catalog ids"
    why_human: "The container run had no session bus (notify-send exited 1, expected); only the adapter is unit-tested"
  - test: "Effect of `uv self update` on the shell rc files of a real user"
    expected: "rc files unchanged (UV_NO_MODIFY_PATH=1 is set); vendor rc edits remain an accepted limit"
    why_human: "Container proved rc unchanged for a fresh user only (RC_FINDING changed=none)"
  - test: "Owner confirms every provisional decision in 35-10-SUMMARY.md 'Provisional decisions for the owner' (D-03, D-05..D-14, D-20, decisions 1-9, O7, rounds 1-3, and the dated SPEC/ROADMAP/REQUIREMENTS amendments)"
    expected: "Each decision confirmed or changed by the owner"
    why_human: "Decisions are marked provisional and needs-confirmation by design"
  - test: "Owner triage of deferred backlog 999.36 (review DEFER rows Lane 7, 11, 12, 14, LO-03, LO-04/05, LO-08) and ME-02 (limits/log lines only visible at 100x30, detail pane not focusable at 80x20)"
    expected: "Owner decides scrollable or focusable detail pane and accepts or schedules the other deferrals"
    why_human: "ME-02 is an owner UI decision; the rest are accepted-risk deferrals"
---

# Phase 35: Opt-in auto-update, package managers first - Verification Report

**Phase Goal:** A user who opts in gets their tools updated on a schedule in a safe order: managers first, then dependents, nothing updated twice, nothing run as root, nothing updated after its manager failed.
**Verified:** 2026-11-22
**Status:** human_needed
**Re-verification:** No, initial verification. Targeted reading only; no suite, container, updater, timer or notification was run.

## Observable Truths

| # | Truth (ROADMAP SC as amended) | Status | Evidence |
|---|---|---|---|
| 1 | Fresh install seeds `update-all` off, no Policies row, never turned on/off by the installer once decided | VERIFIED | `installer/schedules.py:54` (`default_on: bool = True` field), `:97-110` (update-all row `default_on=False`, daily 03:00), `:1594` (`_row_action`: undecided row returns `"none"` unless `default_on`), `:1595-1596` (decided False returns `none`). No Policies row found for it. |
| 2 | Order: managers (ownership edges), then dependents grouped by owner / `resolve_dependencies`; failed manager gives a skip line per dependent and no update call | VERIFIED | `installer/update_all.py:122` `_manager_order`, `:228` `plan_managers`, `:267` `plan_dependents`, `:178` `blocking_manager`, `:204` `_decide`; runner `schedule_run.py:531-` refreshes and re-plans dependents after managers (`failed_managers`, `completed` sets). Container run2 order=brew,bun,sdkman,uv,ruff (transcript line 2028). |
| 3 | Refused tools skipped with reason; held lock refuses; no sudo; casks left alone; Volta and seven others `no unattended update path` | VERIFIED | `update_all.py:159` shared `exclusion` predicate (cask, no-update-argv at `:167-178`); `schedule_run.py:239` `_BatchGuard` re-applies exclusion on fresh ownership; `:429` `_confirmed` (windows, evidence); root refusal `:709-710` (`euid()==0`) before lock; parent-handoff `:781-784` requires `runlock.held_by` (holder line plus kernel lock) else `refuses an unverified parent run lock`; busy lock `:722-723` `skipped: busy`; `try_acquire` non-blocking. 35-SECURITY.md T-35-03 greps found no sudo/pkexec/doas call path. |
| 4 | Run leaves one line per tool in run log and one summary line in the shared log; per-tool row tools updated once per day | VERIFIED | `update_all_state.py:78` `record_updated`, `:74` `updated_on`; `schedule_run.py:631` records mutations, `:732-735` per-tool row returns `skipped: updated today`; `update_all.py:57` `summary_line`. Container run2: `UPDATE_ALL_LOG ... uv skipped: updated today`, `UPDATE_ALL_SHARED_LOG ... update-all ok: 0 updated, 4 skipped`. |
| 5 | e2e runs update-all in a disposable container, never on host, and records the `uv self update` result | VERIFIED (code) / real run on record | `scripts/container-e2e-verify.sh:193,3460,3518` (`update-all` verb, PID-named container, orchestrator-only). Transcript run2: `UV_SELF_UPDATE_OK before=0.11.0 after=0.13.9`, `DEPENDENT_OK ruff 0.1.0->0.17.6`, `RC_FINDING changed=none`, `AGAIN_CURRENT ruff already current`, `TEARDOWN_OK`. |
| 6 | Plan mode writes no installer state | VERIFIED | `cli.py:75-87` `--plan` only with `update-all`, not with `--parent-holds-run-lock`; `setup.py:543-567` `hold_writes` then `plan_update_all`; `_plan_schedule` returns before `run_schedule` (`setup.py:564-581`); `version_status.py:1328` `hold_writes`. |
| 7 | Notification after a real run only when updated+failed > 0, attempt not guarantee | VERIFIED | `schedule_run.py:708-714`: notify only `if updated_ids or failed`; failure becomes clause `notify skipped: ...`. Real desktop notification is human-only (container: notify-send exit 1, expected). |

**Score:** 7/7 code-level truths verified; real macOS/host/desktop evidence is human-only.

## Key Link Verification

| From | To | Status | Details |
|---|---|---|---|
| `schedules.SCHEDULES` update-all row | `_row_action` / `ensure_schedule_defaults` | WIRED | `schedules.py:109`, `:1594` |
| `schedule_run.run_schedule` | `_update_all` / `_run_unlocked` | WIRED | `schedule_run.py:709-727`, `:781-791` |
| `_update_all` | `update_all.plan_*`, `update_all_state`, notifier | WIRED | `schedule_run.py:531-725` |
| `setup.py --plan` | `plan_update_all` with `hold_writes` | WIRED | `setup.py:564-581` |
| per-tool update rows | updated-today record | WIRED | `schedule_run.py:732-744` |
| uninstall sweep | record and log files | WIRED | `schedules.py:1850-1859` (per 35-SECURITY.md T-35-01) |
| container verb | real `uv run` chain | WIRED | `container-e2e-verify.sh:3456-3518` and transcripts |

## Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| AUTOUPD-01 | SATISFIED | Truth 1 |
| AUTOUPD-02 | SATISFIED (amended: ownership edges) | Truth 2 |
| AUTOUPD-03 | SATISFIED | Truth 2 (`blocking_manager`) |
| AUTOUPD-04 | SATISFIED | Truth 3 (guard, root refusal, lock, DEVNULL per 35-SECURITY.md) |
| AUTOUPD-05 | SATISFIED | `update_all.py:167-168` cask exclusion |
| AUTOUPD-06 | SATISFIED | Truth 4, 7 |
| AUTOUPD-07 | SATISFIED | Truth 4 |
| AUTOUPD-08 | SATISFIED for the container, partial by design | Real container run twice PASS; macOS/host remain human items |

No orphaned requirements. REQUIREMENTS.md still shows these as Pending (checkbox state is the orchestrator's to update).

## Gaps

None blocking. Deferred backlog 999.36 (review DEFER rows, ME-02) is accepted-risk and listed under human verification.

## Anti-Patterns

No unreferenced TBD/FIXME/XXX found in the phase's four implementation files by the reading performed; I did not run a full marker grep over every touched file. `_update_all` is about 160 lines with nonlocal closures (review LO-08, deferred refactor, not a defect). Summaries disclose two incomplete test assertions in 35-10 (closed-list screen coverage only for two rows; notification reason trimming not proved at every budget); both are minor.

## Human Verification Required

See the `human_verification` frontmatter list: macOS nightly row, Bazzite first night with timer, real desktop notification, `uv self update` rc effect on a real user, owner confirmation of all provisional decisions, and the 999.36 deferrals including ME-02.

---

_Verified: 2026-11-22_
_Verifier: Claude (gsd-verifier)_
