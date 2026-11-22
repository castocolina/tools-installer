---
phase: 34-daily-update-check-with-a-desktop-notification
reviewed: 2026-11-22T00:00:00Z
depth: deep
files_reviewed: 36
files_reviewed_list:
  - .claude/architecture.md
  - installer/cli.py
  - installer/helper_assets/schedule_runner.py
  - installer/notify.py
  - installer/run.py
  - installer/schedule_run.py
  - installer/schedules.py
  - installer/schedules_screen.py
  - installer/update_check.py
  - installer/version_cache.py
  - installer/version_status.py
  - scripts/container-e2e-verify.sh
  - setup.py
  - tests/state_doubles.py
  - tests/test_app.py
  - tests/test_cli.py
  - tests/test_container_e2e_schedules.py
  - tests/test_docs.py
  - tests/test_execute_screen.py
  - tests/test_layout_80x20.py
  - tests/test_notify.py
  - tests/test_run.py
  - tests/test_schedule_runner.py
  - tests/test_schedules_engine.py
  - tests/test_schedules_handover.py
  - tests/test_schedules_lifecycle.py
  - tests/test_schedules.py
  - tests/test_schedules_view.py
  - tests/test_schedule_update.py
  - tests/test_update_check_contract.py
  - tests/test_update_check_job.py
  - tests/test_update_check.py
  - tests/test_version_cache.py
  - tests/test_version_status.py
  - tests/update_check_child.py
  - tests/update_check_doubles.py
findings:
  critical: 0
  warning: 4
  info: 7
  total: 11
  necessity: 1
status: issues_found
---

# Phase 34: Code Review Report

**Reviewed:** 2026-11-22
**Depth:** deep
**Files Reviewed:** 36
**Status:** issues_found

## Summary

Scope: `74f66900..HEAD` in the 36 files above, plus the called code I had to read to trace the check end to end (`installer/atomic.py`, `installer/compose.py` `_build_services`, `installer/run.py` `run_query`, `installer/versions.py`, `installer/sanitize.py`, `installer/systemd_daemon.py` `render_exec_service`). `necessity-review.md` was read; one necessity finding is recorded (IN-03).

The core design holds up under attack. I traced the confirmed-only membership rule, the strict reader, the notifier, the self-check and the container verdict, and found no data-loss or security defect and no blocker. What I verified, with evidence:

- **Notified set.** `next_set` (`installer/update_check.py:146-185`) cannot add an id from stale or failed evidence: `fresh_ids` (`:132-142`) requires `state.version.stale` false and a stamp `>= started` read from the file after the pass. The manager snapshot keeps its old `checked_at` on a failed or partial pass (`installer/version_status.py:1768-1798`), so a failed manager query never reads as fresh. A failed notification does not store the set (`update_check.py:271-274`). A directory or symlink at the path reads as unhealthy through `read_capped` (`installer/atomic.py:186-215`: a directory returns `None`, `O_NOFOLLOW` on a symlink raises). `atomic_replace_entry` replaces a link and fails on a directory (reproduced in the tests and by me).
- **Result line.** `result_line` (`update_check.py:206-218`) bounds the total at 300, equals the runner's `_MAX_REASON` (`schedule_runner.py:105`, pinned by a test) and keeps every label, because the label width is subtracted before the reason share is computed. `reason_line` (`notify.py:29-32`) and the runner's `_CONTROLS` (`schedule_runner.py:104`) agree on `0x7f-0x9f`.
- **Notifier.** No shell, fixed failure categories (`notify.py:70-75`), argv and body never echoed (`test_failures_map_to_fixed_reasons`). The bus probe catches a raising `is_socket` (`:60-66`), derives only from an existing socket and never sets an empty value.
- **Self-check.** I ran the real `git_for_check` against scratch repos with a scratch `HOME` and `GIT_CONFIG_*=/dev/null`, all removed afterwards. Behind returns `(True, None)`. Fetched-but-unmerged returns `(True, None)`. Up to date and ahead of origin return `(False, None)`. A subdirectory returns `not the checkout root`. A hash of every file in the clone, `.git` included, plus its mtimes, was identical before and after. `cat-file -e` of an absent 40-hex id exits 1 silently, and the partial-clone regexp matches `remote.origin.promisor` (case-insensitively) and exits 1 when absent.
- **Refresh budget.** `stale_after` reaches the budget check (`version_status.py:1951`), `resolve_status` (`:1965`) and the fetch gate (`:400`, `:429`, `:432`). `on_failure` sits in `_latest_status`'s except branch (`:411-413`) and `resolve_tag` is not wrapped. `test_the_cap_holds_at_twenty_and_twenty_one_eligible_tools` seeds entries aged 1 day, between 20 h and 7 d, so dropping `stale_after` at the budget site would make it fail (21 calls, not 20).
- **Schedules.** `Schedule.daily` replaces every hard-coded daily site. I grepped `== 24` and `JobKind.TMP_CLEANUP`, and each remaining use is a real tmp-only branch (`_grid` Linux fixed cadence, `_is_linux_tmp`, legacy wrapper). `_cleanup_if_last` keeps a directory and deletes the rest (`schedules.py:1856-1878`).
- **Container harness.** The new awk rejects `start,ok,ok`, `start,skipped,start` and a second pair; I ran the awk under gawk. `[[ =~ $pattern ]]` with the pattern in a variable and the `$'..'` strings are bash 3.2 safe. `shellcheck -s bash -S style scripts/container-e2e-verify.sh` is clean.
- **Tests run.** `test_update_check.py`, `test_notify.py`, `test_update_check_job.py`, `test_update_check_contract.py`, `test_shell_scripts_path.py` and `test_container_e2e_schedules.py` pass on Python 3.12. `test_update_check.py`, `test_notify.py` and `test_update_check_job.py` also pass on Python 3.15.2 through `uv run --isolated --frozen --python 3.15`, so `.venv` was not touched. The tests inject `which`, `run`, `environ`, `uid` and `is_socket`; the one that reaches a real `notify-send` (`test_update_check_job.py`) runs it under a scratch `PATH` and a planted bus variable.

Four defects survive. WR-01 is a silent no-op when the cache cannot be saved. WR-02 is a silently vanishing self-update clause. WR-03 is a permanent crash on a deeply nested state file (Python 3.12). WR-04 is scoping: the session bus address now reaches every runner child, including vendor update scripts. I reproduced WR-01 to WR-03 with read-only experiments. Nothing here reopens the provisional decisions listed in the request.

Not exercised: macOS delivery, a real timer or unit, the container run (`scripts/container-e2e-verify.sh schedules`, orchestrator-owned), a real notification, `uv run --frozen --isolated` against a real checkout, and the other test files under Python 3.15.

## Warnings

### WR-01: A failed `versions.json` save is swallowed, so the check silently reports `ok: N updates available` with no evidence

**File:** `installer/update_check.py:249-261` (cause: `installer/version_status.py:2075-2089`, `:1379-1381`)
**Issue:** `VersionRefreshService._pass` writes the pass through `save_pass`, which catches `OSError` and only sets `self._warning` (`version_status.py:2080-2081`). `refresh()` then returns normally. `run_check` never reads `refresh.warning` and the `Refresher` protocol (`update_check.py:39-47`) does not even declare it. `fresh_ids` re-reads the file (`:127`), finds no stamp written by this run and confirms nothing. The result is a daily `ok:` line carrying no clause, with exit 0, while every outdated tool stays unreported.

Reproduction (the real `VersionRefreshService` from `tests/update_check_doubles.py::real_service`, a scratch `HOME`, an outdated receipted `yq`, `versions.json` replaced by a directory, run twice):
```
('ok: 0 updates available', 0) | warning: version cache not saved: [Errno 21] Is a directory: '.../versions.json.<pid>.<uuid>.tools-installer.tmp' -> '.../versions.json'
('ok: 0 updates available', 0) | warning: version cache not saved: [Errno 21] ...
notifier calls: []
```
A directory at the path is contrived. The same silent path is taken for any persistent `OSError` from the save (read-only filesystem, quota, a permission problem on the state directory) whenever the notified set is unchanged. In that case `write_notified` is never attempted, so no `notified set not saved` clause appears either. SPEC R2 asks that a failed lookup "logs a reason"; a failed evidence write needs the same.
**Fix:** declare `warning` on `Refresher` and surface it after the pass:
```python
class Refresher(Protocol):
    @property
    def warning(self) -> str | None: ...
...
    if refresh.warning is not None:
        clauses.append(("version cache not saved", refresh.warning))
```
Build `clauses` before the `failures` clause so the order stays stable, and add `warning` to `FakeRefresher`. Add a test with a directory at `versions.json` through the real service (the reproduction above).

### WR-02: `git rev-parse --abbrev-ref HEAD` returns `heads/main` when a tag `main` exists, so the behind clause silently disappears

**File:** `installer/update_check.py:294-298`
**Issue:** With an ambiguous short name git prints `heads/main`, and `if branch != "main": return False, None` (the silent skip meant for a detached HEAD or another branch) swallows it. I reproduced it with the real `git_for_check` against a scratch clone that is one commit behind its origin and carries a tag `main`: `installer_behind` returned `(False, None)`, where the same clone without the tag returns `(True, None)`. `git rev-parse --abbrev-ref HEAD` printed `heads/main` in a separate experiment. The user then never learns the installer is behind, and `confirmed_out` also drops `tools-installer` from the stored set (`:183-184`). A tag named `main` is unusual but not impossible in a fork or a mirror.
**Fix:** compare the full ref instead of the abbreviated name:
```python
try:
    ref = git([*base, "symbolic-ref", "-q", "HEAD"]).strip()
except CommandError as exc:
    if exc.returncode == 1:  # detached HEAD
        return False, None
    return False, _failure_category(exc, "not a git checkout")
if ref != "refs/heads/main":
    return False, None
```
`symbolic-ref -q` exits 1 on a detached HEAD, so the `FakeGit` table and the `BRANCH` constant in `tests/test_update_check.py:267` change with it. `--short` would repeat the ambiguity, so do not use it.

### WR-03: Deeply nested JSON crashes both strict readers with `RecursionError` on Python 3.12, and nothing rewrites the file

**File:** `installer/update_check.py:96-99` (called from `:259`), `installer/version_cache.py:171-177` (called from `update_check.py:243`)
**Issue:** `read_notified` catches `(ValueError, UnicodeDecodeError)` and `_read_json` catches `(OSError, ValueError)`. `json.loads` of `"[" * 30000 + "]" * 30000` (60 KB, inside both caps: 64 KiB for the notified file, 4 MiB for the cache) raises `RecursionError` on Python 3.12.12. It does not on 3.15.2, which returns `(frozenset(), False)` and `{}`. `requires-python` is `>=3.11` and the venv and push gate run 3.12, so a host that resolves to 3.11 to 3.14 is affected. In `run_check` neither call sits inside the `try`, so the process dies with a traceback (reproduced: `run_check raised RecursionError`). The runner logs `failed: installer exited 1: RecursionError...` every day, because the file is never rewritten. This violates SPEC R3 ("a corrupt state file is treated as empty and rewritten") and the strict-reader contract in `.claude/architecture.md`. The precondition is same-user corruption or deliberate planting, which is why this is a Warning and not a Critical.
**Fix:** catch it at the two decode sites:
```python
except (ValueError, RecursionError):
```
(`UnicodeDecodeError` is a `ValueError`). Add a parametrized case `b"[" * 30000 + b"]" * 30000` to `test_read_notified_is_strict` and to the cache tests.

### WR-04: The session bus address now reaches every runner child, including vendor update scripts, not only the check's notifier

**File:** `installer/helper_assets/schedule_runner.py:84-99` (list), `:194-198` (`_child_env`), `:237` (every `_run_child`)
**Issue:** The owner decision on the mechanism (the runner's environment only, nothing in the unit) is respected and not reopened here. This is about its scope. `_PASSED_ENV` feeds `_child_env`, which every `_run_child` call uses: the tmp-cleanup script (`:316`), each cache prune (`:414`), and `uv run setup.py --run-schedule update-<tool>` (`:334`), whose descendants are vendor installers, `npm`/`pnpm` lifecycle scripts and `curl | sh` update paths. Before this phase those children could not reach the user's session bus (`notify-send` fails with `Cannot autolaunch D-Bus without X11 $DISPLAY`, per decision 3). Now a postinstall script can call the Secret Service (an unlocked keyring), `org.freedesktop.Notifications`, or the user's `systemd --user` manager. Only the check job needs the address. `tests/test_schedule_runner.py::test_child_env_passes_the_session_bus_address` and `test_the_runner_environment_equals_the_unit_keys_plus_the_two_runner_only_keys` pin the global behavior.
**Fix:** drop `DBUS_SESSION_BUS_ADDRESS` from `_PASSED_ENV` and pass it only to the check child:
```python
def _bus_env() -> dict[str, str]:
    bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    return {"DBUS_SESSION_BUS_ADDRESS": bus} if bus else {}

extra_env={"PYTHONDONTWRITEBYTECODE": "1", **_bus_env()} if readonly else None,
```
Update the two tests to assert the address reaches the `check-updates` child and not a `cache-cleanup` or `update` child.

## Info

### IN-01: Worktree-root comparison may skip a checkout on a case-insensitive macOS volume

**File:** `installer/update_check.py:303`
**Issue:** `Path(toplevel).resolve() != checkout.resolve()` compares strings. `checkout` is `Path(__file__).resolve().parent` (`setup.py:543`), which keeps the case the user typed, while git prints the case of `getcwd()`. On a case-insensitive APFS volume a checkout reached as `~/git/Tools-Installer` can differ from the canonical case, yielding the permanent `installer check skipped: not the checkout root`. This is unverified: I could not run it on macOS, and Linux has no case folding. The skip is visible, not silent.
**Fix:** `if not Path(toplevel).samefile(checkout):`. It also covers bind mounts and symlinks. Keep `resolve()` out of the comparison. `test_a_checkout_that_is_not_its_own_worktree_root_is_skipped` already uses a symlink and a different directory, so it still holds.

### IN-02: A save failure that persists (a directory or an unwritable state path) re-notifies on every run

**File:** `installer/update_check.py:270-278`, pinned by `tests/test_update_check.py:688-693`
**Issue:** When `write_notified` fails, the set is not stored, `prior` stays empty, and the next run (any manual or catch-up run too, not only the daily one) notifies the same set again. The line carries `notified set not saved: <errno text>`, so the failure is visible, but the user gets one desktop notification per run for as long as the path stays broken. The test records this as intended. This is not on the accepted list (the daily limit is the timer cadence; a persistent save failure is a different case). The errno text also carries the absolute state path into the shared log (the whole path, through `str(exc)` at `:278`).
**Fix:** decide it explicitly. Either accept it and state it in `.claude/architecture.md`, or keep a per-process marker. A cheap bound: when the save fails, do not notify on a later run whose `ids` equal the ids that failed to save, by writing nothing and logging the clause only. At minimum, name this in the architecture note next to "A changed non-empty set triggers a notification attempt on any run".

### IN-03: Defensive stale re-filtering in `next_set` duplicates `fresh_ids`

**File:** `installer/update_check.py:172-180` (and the stale re-check inside `confirmed_out`, `:166-168`)
**Category:** necessity
**Issue:** Impossible-state guard. The guarded state (a stale id inside `fresh`) cannot occur in production: `fresh_ids` is the only producer (`:261`) and it already skips `state.version.stale` (`:132`), and `next_set` has one caller (`run_check:262`, found with `rg "next_set" installer`). The second filter and the `not state.version.stale` terms exist so a direct test call with a hand-built `fresh` (`tests/test_update_check.py:207-233`, ids `d` and `e`) still behaves. This rests on judgment, not proof, because it is a deliberate second layer on a public function, so it is Info.
**Fix:** keep it if the contract "a supplied fresh set is trusted for staleness only through this function" is wanted, and say so in the docstring. Otherwise delete `:172-180` and the `stale` terms, and move the stale-id cases of the test to `fresh_ids`.

### IN-04: `_message = message` alias exists only for a test lookup

**File:** `installer/update_check.py:198` (used at `:271`), `tests/test_update_check.py:237`
**Issue:** `message` is public and never called by production code; `run_check` calls the private alias, and the test reaches it with `vars(update_check)["_message"]`. Two names for one function, with the public one dead in production.
**Fix:** delete the alias, call `message(ids)` in `run_check`, and import it normally in the test.

### IN-05: `SKIP_REASONS` is a production constant read only by tests

**File:** `installer/update_check.py:60-72`
**Issue:** Nothing in `installer/` reads `SKIP_REASONS` (`rg SKIP_REASONS installer setup.py` finds the definition only); `tests/test_update_check.py:322-333` and the category tests use it as an oracle. Production strings are written as literals in `installer_behind`, so the set and the code can drift: adding a literal does not fail the test unless the author remembers the set.
**Fix:** use the constants in `installer_behind` (for example `NOT_A_CHECKOUT = "not a git checkout"`) and build the set from them, or move the set into the test.

### IN-06: The container verdict never exercises the self-check, and its checkout probe excludes `.git`

**File:** `scripts/container-e2e-verify.sh:2528-2541` (probe), `:327-334` (`stream_worktree`), `tests/test_docs.py:243-285`
**Issue:** `stream_worktree` copies `git ls-files` content only, so the container workspace has no `.git`. The recorded real run says it: `installer check skipped: not a git checkout` (`34-07-SUMMARY.md`). `TRACER_SCHEDULE_CHECKOUT_UNCHANGED` therefore says nothing about the git queries, and the probe also excludes `*/.git/*`, the one place a stray fetch would write. The real-git path is covered only by `FakeGit` in the unit tests (accepted) and by my own scratch run (byte and mtime identical, including `.git`). `.claude/architecture.md` ("nothing is written into the checkout") and the phrase-presence test in `tests/test_docs.py` record the claim, while the test evidence for it is the env-var check `bytecode == "1"` plus the harness probe above.
**Fix:** state in the container verdict output (or the SUMMARY) that the git path is unexercised there. If wanted later, `git init` plus a commit in the workspace copy and drop the `.git` exclusion for the check row.

### IN-07: The 80x20 ellipsis assertion changed from `size.width` to `outer_size.width`

**File:** `tests/test_layout_80x20.py:870`
**Issue:** The edit to an existing assertion is explained in `34-01-PLAN.md:144` (the `…` lands in the padding column with the taller table), and the `endswith("…")` check is unchanged, so the test still asserts what it claims. It is listed here because it is a silent change to a pre-existing test that the SPEC wording ("assertions about the other rows stay") does not name; record it in the SUMMARY's list of edited assertions if it is not already there.
**Fix:** none in code; add the line to the edited-assertions list.

---

_Reviewed: 2026-11-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

---

## Orchestrator triage (2026-11-22)

Sources: this report (gsd-code-reviewer, deep: 0 critical, 4 warnings, 7 info), the external lane `opencode-referee-one` (15 findings, one pass, 03:19 to 03:37), the security audit (`34-SECURITY.md`: SECURED 23/23, 0 open) and the orchestrator's real `schedules` container check (PASS, see `34-07-SUMMARY.md`). Claims that rest on code or Git behavior are for the fixing executor to verify first and fix or reject with a stated reason. Decisions are provisional.

| Item | Source | Decision |
|---|---|---|
| Lane 1 | lane | VERIFY, then FIX if real: a persistently failing manager query (for example `pnpm outdated`) keeps the old SHARED `checked_at`, so the daily check rejects every manager result without a fresh stamp and a uv update stays hidden; record the confirmation stamp PER MANAGER (an additive field of the manager snapshot) and have the confirmed-membership rule read it per manager; test a mixed success/failure pass through the real service. |
| Lane 2 | lane | FIX: `run_check` must not reconstruct confirmation from a later disk read (a TUI refresh can write a newer snapshot during the Git check): return the confirmed ids with the pass result from the refresh service's own states and stamps. |
| Lane 3 | lane | FIX: the failure sink and the result line report a fixed category (and at most the tool id), never the raw exception text (a manual run's token with an invalid header character appears in the HTTP error); test with a planted token in the exception. |
| Lane 4 | lane | FIX: the check's git also passes `-c http.cookieFile=`, `-c http.saveCookies=false` and `-c http.extraHeader=` (an empty value resets the list), keeping the stated remaining limit (other git configuration stays in effect); argv test. |
| Lane 5 | lane | FIX: a skipped self-check (detached HEAD, non-main branch, non-root checkout, partial clone) is UNKNOWN, not a confirmed negative: `tools-installer` keeps its prior membership; test a notified installer followed by a branch switch. |
| Lane 6 | lane | VERIFY, then FIX: `Health.UNAVAILABLE` (the tool is absent and no install method applies) is confirmed absence like `MISSING`; `CHECKING` and a missing state stay unknown. |
| Lane 7 + WR-03 | lane, reviewer | FIX: catch `RecursionError` (Python 3.12) and `OverflowError` (a timestamp at the edge of the year range) at every decoding boundary of the notified-set reader, the version-cache reader and the attempt-order sort; a corrupt file reads as empty; tests under 3.12 and 3.15. |
| Lane 8 | lane | FIX: the version-cache writer refuses to replace the file with content over the reader's cap, keeps the last readable file and surfaces a warning. |
| Lane 9 + WR-01 + IN-02 | lane, reviewer | FIX: a failed cache save (`service.warning`) is propagated into the result line as a clause (`cache not saved`) and confirms nothing; a persistent save failure re-notifying each run is stated, not hidden. |
| WR-02 | reviewer | FIX (reproduced): `git rev-parse --abbrev-ref HEAD` prints `heads/main` when a tag `main` exists and the behind clause vanishes; read the branch with `git symbolic-ref --short -q HEAD` or compare `refs/heads/main` exactly; test with a tag named `main`. |
| WR-04 | reviewer | FIX (scope only): `DBUS_SESSION_BUS_ADDRESS` is given to the check job's child only (the runner's `extra_env`), not to every runner child; it stays out of the unit environment. |
| Lane 10 + IN-06 | lane, reviewer | FIX (narrow): the container checkout probe compares a before/after manifest of the regular files (path and size) under the workspace, so a deletion is caught, and its wording says what it proves (no new, removed or modified regular file outside `.git` and `.venv`); the workspace has no `.git`, so the self-check path is not exercised there (stated). |
| Lane 11 | lane | DEFER: the Last-cell check can disagree across midnight (two clock reads); orchestrator-run only, a failure not a false pass; backlog 999.34. |
| Lane 12 | lane | DEFER: in-flight refreshes are keyed by tool ids only, so a joined refresh ignores a different freshness window or callback (the scheduled process builds its own service); backlog 999.34. |
| Lane 13 | lane | DEFER: the manual check route inherits stdin for manager queries and reads `settings.json` before taking the lock (a FIFO there can block); backlog 999.34. |
| Lane 14 | lane | FIX: percent-encode the socket path component of the derived D-Bus address; an explicitly supplied address is left alone. |
| Lane 15, IN-04 | lane, reviewer | FIX: drop the duplicate setup wiring test and the `_message` alias; test the public function. |
| IN-01 | reviewer | FIX: compare the worktree root with `samefile`, not path strings (case-insensitive macOS volumes). |
| IN-03 | reviewer | FIX: `next_set` stops repeating the stale filtering `fresh_ids` already does. |
| IN-05 | reviewer | FIX: production code uses the `SKIP_REASONS` constants, so the literals cannot drift. |
| IN-07 | reviewer | RECORD: the existing assertion in `tests/test_layout_80x20.py` that changed from `size.width` to `outer_size.width` is listed in the review-fix record (the plan explained it). |
