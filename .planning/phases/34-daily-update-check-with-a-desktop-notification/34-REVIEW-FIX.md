# Phase 34 Review Fix

Two pi runs on router-env/my-coding (part A 03:43 to 04:00, part B 04:01 to 04:08), the reports below, then the orchestrator's verification (`make test` after the last commit: 9410 passed, 6 skipped, coverage 96.44%; the update-check, notify, cache, status, runner and container-schedule tests also pass on Python 3.15; the real `schedules` container check rerun on the final harness: PASS).

## Part A

| Item | Status | Commit | Note |
|---|---|---|---|
| Lane 2 | fixed | `d14560e1` | Confirmation uses the refresh pass's own states and stamps (no later disk read); a regression test writes a newer snapshot during the pass. |
| Lane 3 | fixed | `f0d78691`, `d14560e1` | Lookup failures report fixed categories, never raw exception text (a planted token in an exception does not reach the line). |
| Lane 4 | fixed | `f0d78691` | The check's git also disables configured cookies, saved cookies and extra HTTP headers. |
| Lane 5, IN-01 | fixed | `e72e808a` | A skipped self-check is unknown and keeps the prior membership; `samefile` for the root comparison. |
| WR-02 | fixed | `e72e808a` | The branch is compared as the full symbolic ref (a tag named `main` no longer hides the behind clause). |
| Lane 6, IN-03 | fixed | `b690daff` | `UNAVAILABLE` (absent, no applicable method) is confirmed absence like `MISSING`; the duplicate stale filtering is gone. |
| Lane 9, WR-01 | fixed | `e702b91f` | A failed cache save adds a clause, confirms nothing and does not store the set. |
| Lane 7 (notified file, order sort) | fixed | `f0d78691`, `a450570f` | `RecursionError` and `OverflowError` read as an empty or unusable value. |
| Lane 14 | fixed | `d63c99c5` | The derived D-Bus socket path is percent-encoded. |
| WR-04 | fixed | `a43b0db6` | Only the check child receives the session bus address. |
| IN-04, Lane 15, IN-05 | fixed | `b690daff`, `78828ffa`, `a507f408` | Alias and duplicate test removed; production uses the constants of `SKIP_REASONS`. |

## Part B

| Item | Status | Commit | Note |
|---|---|---|---|
| Lane 1 | fixed (real) | `2a2785cf` | Reproduced through the real service: one failing manager kept the shared stamp and hid another manager's result; the snapshot now carries a per-manager confirmation stamp (older snapshots still load). |
| Lane 7 (version cache) | fixed | `a02d5136` | Deeply nested JSON and an out-of-range timestamp read as an empty cache (Python 3.12 and 3.15). |
| Lane 8 | fixed | `cc274fbf` | An oversized write is refused, the last readable file is kept and a warning surfaces. |
| Lane 10, IN-06 | fixed | `74feb6b0` | The checkout probe compares regular-file paths and sizes outside `.git` and `.venv`; the verdict says what it proves and that the git self-check is not exercised in the workspace. |

## Edited existing assertions (record)

`tests/test_layout_80x20.py` changed one assertion from `size.width` to `outer_size.width` (plan 34-01, explained in its decision record); `tests/test_update_check_job.py` (plan 34-09's own test) was updated by the orchestrator to the four-query sequence when plan 34-10 added the worktree-root query.
