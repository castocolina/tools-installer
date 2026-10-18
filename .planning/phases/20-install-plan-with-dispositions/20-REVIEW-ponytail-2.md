# Phase 20 — ponytail review, round 2

Scope: `git diff f9d98fe HEAD -- installer setup.py scripts tests` (33 files, +2267 / -644,
gap plans 20-20..20-29 closing J1..J12 of `20-REVIEW-CONSOLIDATED.md`).
Load assumed: one person running the TUI or one headless `--all`/`--categories` run on their own
machine, plus the disposable-container e2e gate (`scripts/container-e2e-verify.sh`). There is one
refresh service per process, a catalog of about 90 tools, and one worker thread per run.

**Severity counts:** High 0 · Medium 1 · Low 1

## What this change does

Headless `run_wizard` now settles skill packs (`refresh_skills`) and holds every refresh write
(cache saves, receipt retirement, receipt adoption) until the user consents (L-20-10). The TUI's
review wait joins both checks and always settles. `build_plan` waits on pending blocked
dependencies, does not block a dependent on a present dependency, and skips a dragged dependency
that only a blocked tool needs. Both routes share one bound install, one `RUNNABLE` set and one
`render_run_report`. Run-level PATH errors now fail headless, latest-wins covers run errors and `u`
retries, and a refused reinstall of oh-my-zsh shows the chsh handoff (L-20-11). The e2e gate now
counts not-attempted and crashed rows, checks the setup exit code, and reads folded rows with bash
only.

## Round-1 closure

| Id | Status | Where |
|----|--------|-------|
| P-01 headless `--all` never settles skill packs | closed | `installer/app.py:118-121`, `installer/execute_screen.py:543-557` |
| P-02 pending dependency with no method reads blocked | closed | `installer/session.py:710-711` |
| P-03 failed reconfigure / refused update loses its reason | closed | `installer/render.py:155-161` |
| P-04 headless second presence question | closed | `setup.py:779-788`, `setup.py:1513-1521` |
| P-05 successful `u` retry never clears a failed `u` | closed | `installer/wizard_app.py:3027-3029` |
| P-06 `Install` / `with_sensitive_confirm` leftovers | closed | `installer/session.py:267-293` |
| P-07 selection, style and `platform` leftovers | closed | `installer/selection.py`, `setup.py:146-152`, `installer/app.py:97-110` |
| P-08 `Resolution.order` / `dragged_in` / `warnings` | closed | `installer/deps.py:24-37`, `installer/deps.py:121-148` |
| P-09 runnable set and post-run report copied | closed | `installer/session.py:108-116`, `installer/render.py:280-289` |
| P-10 `_row` repeats itself | partial | `make` and `_off_policy_reason` landed (`installer/session.py:606-645`); the crash detail at `installer/session.py:562` still re-implements `_first_line` (`:330-334`). The `row.ownership is None` branch at `:531` stays as the type guard for `UpdateTarget`, which is acceptable |

## Must fix

1. **The e2e gate passes a run whose PATH wiring or PATH audit failed when any dependency failure
   is explained** — Medium (`scripts/container-e2e-verify.sh:426-434`, `setup.py:1540-1550`)
   - **What this is:** `install_step_ok` accepts setup exit 1 when `ACC_DEP_FAILED > 0` and every
     dependency failure is explained by a manual row. Plan 20-24 made headless return 1 for a PATH
     wiring or PATH audit error (`code = 1 if path_error or verify_error else …`).
   - **Problem:** Exit 1 now means two things, and the gate cannot tell them apart. A run with one
     explained dependency failure (the common case in the ledger: `dependency_failed=1` in 11 of 16
     recorded counts) that also prints `PATH wiring could not be completed: …` passes. I reproduced
     it with the test harness from `tests/test_container_e2e_receipts.py`: a transcript of
     `Summary — 5 installed, 1 manual, 1 dependency failed`, `✖ mmdc  dependency failed — pi`,
     `○ pi  manual — see the setup steps in the log` and
     `PATH wiring could not be completed: ~/.zshrc is not writable` gives
     `install_step_ok 1` → exit 0. A chunked `--categories` run hides it the same way: category A
     exits 1 for a PATH error, category B has an explained dependency failure, and the combined
     `setup_status=1` passes.
   - **Fix:** In `accumulate_summaries`, count lines that start with `PATH wiring could not be
     completed:` or `PATH audit could not be completed:` into an `ACC_RUN_ERRORS` counter (reset it
     next to the others in pass 1 and both pass-2 steps). In `install_step_ok`, return 1 when it is
     not 0. Add one parametrized case to `test_install_step_gate`: the explained dependency-failure
     transcript plus a PATH wiring line, exit 1, expected 1.
   - **If we skip it:** The gate that J2 hardened still lets a broken PATH setup through on the
     usual container run, and nobody sees it until a user's shell cannot find the tools.

## Should fix

2. **`receipts.commit_adoption` is a second copy of `receipts.adopt`** — Low
   (`installer/receipts.py:304-348`, `installer/version_status.py:1381-1394`)
   - **What this is:** For a held run, `_adopt` calls `receipts.adopt(..., write=False)` to get a
     candidate receipt, then queues `commit_adoption(candidate)`. That function takes the same lock,
     repeats the same `receipt_exists` check, the same `fingerprint(..., rehash=True)` and the same
     comparison, and then writes.
   - **Problem:** The two checks must change together. A future fix to the adoption guard (for
     example a new artifact type check) in `adopt` would not reach the held path, and headless
     would adopt a file the TUI refuses. `commit_adoption` also adds its own `len(artifacts) != 1`
     rule that `adopt` does not state.
   - **Fix:** Queue the real thing:
     `self._pending_writes.append(lambda: receipts.adopt(tool, method, artifact, package=None))`
     (it already returns None instead of writing when a receipt exists or the bytes changed, and
     `_write_unlocked`'s `OSError` is caught by `commit_writes`). Delete `commit_adoption` and the
     closure around it. Keep `adopt(write=False)` for the in-memory candidate. Point
     `test_held_adoption_write_failure_does_not_abort_commit` at `receipts._write_unlocked`.
   - **If we skip it:** About 20 lines of duplicated trust-boundary logic on the receipt path.

## Checked and fine

- Consent gating (L-20-10): every pre-consent write in `VersionRefreshService` goes through
  `_write_or_queue` or the two held branches (retire, adopt). A decline, a failed state check and a
  current-only plan without `--yes` commit nothing. `--yes` and a confirmed plan commit once, before
  the first engine call. `retire` re-reads under the lock at commit time, so a receipt written in
  between is kept.
- The review wait: a non-`OSError` failure still posts `StateSettled`; a late settle after start or
  finish is ignored; a multi-line error shows its first line. Highlight restore now lives in
  `_paint_review`, so `r`, a replan and a settle all keep the cursor on its tool.
- `build_plan`: the new reverse pass runs dependents before dependencies (closure order reversed),
  so a chain C → B → A under a blocked A skips both B and C. A WAIT dependent keeps its dependency
  runnable, which is right because WAIT already stops Enter.
- `ran_anything`: a `manual` RECONFIGURE row counts only when a step with a command ran. That is
  exact today, because the only handoff step (`skill_install` with no argv) runs no command and any
  failed step ends the row as `failed`.
- `refuses_existing` fires only for `installed and repair`. oh-my-zsh cannot read BROKEN through a
  receipt (script installs record no artifacts), so in practice it is reached through `r` only. No
  catalog tool requires oh-my-zsh, so the `MANUAL_REQUIRED` result being in `_UNRESOLVED` does not
  block a dependent today.
- A RECONFIGURE row's terminal-sync warning is kept in `RowOutcome.detail` and no report prints it.
  It is not lost, because both routes run the synchronizer again after any run that ran something
  (`setup.py` `_sync_terminals_and_report`, `wizard_app` close callback) and report that warning.
- Run errors follow latest-wins: they are replaced only by a run that ran something or crashed. A
  successful `u` now makes `app.outcomes` non-empty. That is consistent with a failed `u`, which
  already did.

Verdict: fix 1 first.
Lean: about -20 lines possible (2).
Not checked: I did not run the container e2e or a real headless install. Finding 1 was reproduced
with the repo's own bash harness for the gate functions. I read the test changes only where a
finding or a closure needed them.
