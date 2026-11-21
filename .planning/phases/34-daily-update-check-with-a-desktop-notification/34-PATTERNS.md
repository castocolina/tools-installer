# Phase 34: Daily update check with a desktop notification - Pattern Map

**Mapped:** 2026-11-21
**Files analyzed:** 21 (9 new or new-in-part, 12 modified)
**Analogs found:** 21 / 21 (notify.py and update_check.py are role-matches, see notes)

All analog paths are git-tracked source (`installer/`, `tests/`, `scripts/`); no gitignored mirror is named. Line numbers are as read on 2026-11-21 on branch `gsd/phase-27-...`. The orchestrator decisions in `note-decisions.txt` (numbered N1-N12 below) bind; CONTEXT D-xx are locked.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `installer/schedules.py` (JobKind, `Schedule.daily`, row, `runner_argv`, `_state_artifacts`) | config/model | request-response | itself: `JobKind`/`_update()`/`runner_argv` branches | exact |
| `installer/schedule_run.py` (dispatch by kind, defaulted `RunDeps` fields) | service | request-response | itself: `run_schedule`/`_run_unlocked` | exact |
| `installer/update_check.py` (new, recommended by research) | service | batch + file-I/O | `installer/schedule_run.py` (`_update`, `_first_line`, `_reason`) | role-match |
| `installer/notify.py` (new) | utility | request-response (subprocess seam) | `installer/run.py` `run_output_with_stderr` + `systemd_daemon.systemd_available(which=)` | role-match |
| `installer/helper_assets/schedule_runner.py` (job table, `_PASSED_ENV`, timeout text) | service (stdlib-only) | batch | itself: `_update`, `_parse`, `_locked_run` | exact |
| `installer/schedules_screen.py` (daily, what/_target, CSS height) | component | event-driven | itself: `_target`/`_detail` kind branches | exact |
| `installer/daemon.py` | config | n/a | no change needed (see Shared Pattern: bus variable) | n/a |
| `installer/versions.py` | utility | request-response | n/a: no edit (D-11 verified only); see N8 | n/a |
| `installer/version_cache.py` (`stale_after` kwarg) | utility | transform | itself: `is_stale`/`should_fetch` | exact |
| `installer/version_status.py` (`outdated_ids`, `stale_after`, failure sink) | service | transform | itself: `_latest_status`, `refresh`/`_pass` | exact |
| `installer/run.py` (`run_git_isolated` keywords) | utility | request-response | itself: `run_git_isolated` | exact |
| `installer/cli.py` (widen `--run-schedule` choices) | config | request-response | itself, lines 56-62 | exact |
| `setup.py` (`_schedule_run_deps`) | wiring | request-response | itself, lines 529-544 | exact |
| notified-set file `update-check.json` | store | file-I/O | `installer/version_cache.py` save (ensure_dir + atomic_write_text) | exact |
| `tests/test_schedules.py` (closed table) | test | n/a | itself, lines 105-142 | exact |
| `tests/test_schedules_view.py`, `_lifecycle.py`, `_handover.py` | test | n/a | themselves (listed exceptions, N1) | exact |
| `tests/test_schedule_update.py` (+ check-updates dispatch tests) | test | request-response | itself: `_claude`, `test_a_non_update_schedule_is_refused` | exact |
| `tests/test_schedule_runner.py` (+ check-updates job, env pass) | test | batch | itself: `_update`, `test_update_runs_the_installer_child`, env test | exact |
| `tests/test_notify.py`, `tests/test_update_check.py` (new) | test | n/a | `tests/test_schedule_update.py` (fakes) + `tests/test_daemon.py` env style | role-match |
| `tests/e2e_schedules_driver.py`, `scripts/container-e2e-verify.sh` (`check-updates` pair) | test/script | request-response | the existing `schedules` target pair | exact |
| docs (`.claude/architecture.md` Phase 34 subsection, ROADMAP note) | docs | n/a | per-phase subsections of `.claude/architecture.md` | role-match |

## Pattern Assignments

### `installer/schedules.py` (config/model, request-response)

**Analog:** itself.

**Kind enum and row** (`schedules.py:37-50, 71-93`): append a member and a `daily: bool = False` field (last, defaulted so no positional change); `tmp-cleanup` gets `daily=True`, append the new row last.
```python
class JobKind(StrEnum):
    TMP_CLEANUP = "tmp-cleanup"
    CACHE_CLEANUP = "cache-cleanup"
    UPDATE = "update"
@dataclass(frozen=True)
class Schedule:
    id: str; label: str; kind: JobKind; target: str | None
    default_interval: int; default_start: str
# SCHEDULES ... ends with  _update("copilot"),  (line 92)
```
New row text (D-02): `Schedule("check-updates", "update check", JobKind.CHECK_UPDATES, None, 24, "09:00", daily=True)`. `UPDATE_SCHEDULE_IDS` (line 94) filters by kind: unchanged.

**The seven hard-coded "tmp cleanup is daily" sites** (D-06) to convert to `schedule.daily`: `schedules.py:847-850` (`interval = 24 if schedule.kind is JobKind.TMP_CLEANUP else record.interval`), `:1412-1415`; `schedules_screen.py:384,395-396,501-502,577,717`. Read each in the plan task before editing.

**runner_argv branch** (`schedules.py:858-870`): add a branch before the `else` (the unknown-kind fallthrough is tmp-cleanup's argv):
```python
if schedule.kind is JobKind.UPDATE:
    job = ["update", schedule.target or "", "--installer", str(ctx.checkout), "--uv", str(uv)]
elif schedule.kind is JobKind.CACHE_CLEANUP:
    job = ["cache-cleanup"]
elif schedule.kind is JobKind.CHECK_UPDATES:   # NEW
    job = ["check-updates", "--installer", str(ctx.checkout), "--uv", str(uv)]
else: ...
```

**State artifacts** (`schedules.py:1803-1811`): add `ctx.state_path.with_name("update-check.json")` to the tuple so last-off cleanup and the uninstall sweep delete it (D-14).

**Environment rule (N3):** the `/run/user/*` ban is enforced at `schedules.py:442-446` (docstring of the PATH builder) and `daemon.check_environment` (`daemon.py:55-59`, rejects keys outside `ENVIRONMENT_KEYS`, `daemon.py:47`), not at `systemd_daemon.py:207-211`. Do NOT add `DBUS_SESSION_BUS_ADDRESS` to `ENVIRONMENT_KEYS` or any unit.

**Row default-on / state gating:** `row_state` gates on presence only for `JobKind.UPDATE` (`schedules.py:1488-1492`); a CHECK_UPDATES row falls through to the generic path with no edit. Reconcile `_row_action` needs no change (D-05).

---

### `installer/schedule_run.py` (service, request-response)

**Analog:** itself, `run_schedule` and `_run_unlocked` (lines 121-148).

**RunDeps** (`:24-32`): new fields get defaults placed AFTER `context` (N2; the positional build at `tests/test_schedule_update.py:193` must not change):
```python
@dataclass(frozen=True)
class RunDeps:
    tools: Sequence[Tool]
    updates: UpdateService
    resolve_owner: Callable[[Tool], ManagerOwnership]
    probe_version: Callable[[Tool, ManagerOwnership], str | None]
    context: schedules.ScheduleContext | None
    # NEW, all defaulted: refresh handle, notifier, git runner/clock seams
```

**Dispatch** (replace `:133-135`, keep the lock branch `:136-148` shared):
```python
schedule = schedules.schedule_by_id(schedule_id)
if schedule.kind is not schedules.JobKind.UPDATE:
    return f"failed: {schedule_id} is not an update schedule", 2
```
becomes a branch: UPDATE -> existing `_run_unlocked`; CHECK_UPDATES -> the check function; TMP/CACHE keep the exact refusal `failed: tmp-cleanup is not an update schedule` (`tests/test_schedule_update.py:180-187`). Put the choice inside `_run_unlocked` (or a small table) so both lock paths (`parent_holds_lock` and `try_acquire` giving `skipped: busy`, `:138-148`) are shared.

**Error and result-line style** to copy into the check (`schedule_run.py:35-42, 58-63`):
```python
def _first_line(text): ... [:_REASON_LIMIT]          # sanitize_log_line first
except (UpdateError, CommandError, OSError) as error:
    return f"failed: {_reason(error)}", 1
if outcome.receipt_warning:
    line += f"; warning: {_first_line(outcome.receipt_warning)}"   # extras are "; " clauses
```
The check emits ONE line: `ok: N updates available` (literal, no pluralising) plus `; N lookups failed: <first reason>`, `; notify skipped: <reason>`, `; installer check skipped: <reason>` (D-12, D-16, D-19, D-21).

---

### `installer/update_check.py` (new; service, batch + file-I/O)

**Analog:** `installer/schedule_run.py` for structure (pure decisions, seams injected via `RunDeps`, `_first_line`/`_reason`), `installer/version_cache.py:212-213` for the write.

**Notified-set read/write** (research Pattern 3; sources `installer/atomic.py` `read_capped`/`atomic_write_text`, `version_cache.py:38-39,212-213`):
```python
path = ctx.state_path.with_name("update-check.json")          # scratch HOME works
try:
    raw = read_capped(path, 64 * 1024, follow_symlinks=False)
    data = json.loads(raw) if raw is not None else None
except (OSError, ValueError):
    data = None
notified = frozenset(i for i in data.get("notified", []) if isinstance(i, str)) \
    if isinstance(data, dict) and data.get("version") == 1 else frozenset()
ensure_dir(path.parent)                                       # version_cache.py:212
atomic_write_text(path, json.dumps({"version": 1, "notified": sorted(ids)}) + "\n")
```
Rules (D-15): notify first, store only when the notifier returned None; unchanged does nothing; empty stores empty, never notifies; shrinking non-empty set notifies again (N6: state in docs or row detail).

**Self-check** (D-19/D-20): `git -C <checkout> rev-parse HEAD`, `ls-remote origin refs/heads/main`, then `cat-file -e` and `merge-base --is-ancestor`; N5: skip silently on detached HEAD or branch not `main`. Use the extended `run_git_isolated` (below) with `GIT_SSH_COMMAND="ssh -o BatchMode=yes"`, timeout 20, `new_session=False`.

**Refresh order** (D-10): sort tools oldest `checked_at` first (missing first) before `refresh(tools, stale_after=timedelta(hours=20))`.

---

### `installer/notify.py` (new; utility, request-response subprocess seam)

**Analogs:** `installer/run.py:115-151` (`run_output_with_stderr`: stdin DEVNULL, timeout, `CommandError` 124 on timeout and 127 on OSError), `command_error_line` (`run.py:75`), and the injected-which style `systemd_daemon.py:146` (`def systemd_available(*, which: Callable[[str], str | None] = shutil.which)`), `installer/run.py:325`.

**Seam shape to copy:**
```python
Notifier = Callable[[str, str], str | None]   # summary, body -> None on success or a skip reason
def notifier_for(platform_os: str, which=shutil.which, run=run_output_with_stderr) -> Notifier: ...
```
Children: `run(argv, timeout=10, env=..., new_session=False)` so the runner's group kill reaches them (D-16). Reason text: `command_error_line(exc)` then `sanitize_log_line`, bounded to 300 chars like `schedule_run._first_line`.

**Argv (golden, tested on both OSes):**
- Linux (D-17, N3): `[notify-send, "--app-name=tools-installer", "--urgency=normal", "--", summary, body]`; env gets `DBUS_SESSION_BUS_ADDRESS` from the process env if present, else `unix:path=$XDG_RUNTIME_DIR/bus` or `/run/user/<uid>/bus` only when that socket exists, else unset, never empty.
- macOS (D-18, N4): `["osascript", "-e", "on run argv", "-e", "display notification (item 2 of argv) with title (item 1 of argv)", "-e", "end run", title, body]` (NO `--`; N4). Non-zero exit/timeout/missing binary -> `notify skipped`.

**Reachability:** `tests/test_reachability.py` requires a module to be imported by a production entry point in the same plan or the next; `setup.py` (`_schedule_run_deps`) must import `notify` (and `update_check`) in the plan that adds them or the immediately following plan.

---

### `installer/helper_assets/schedule_runner.py` (stdlib-only service, batch)

**Analog:** itself. It cannot import `installer` (`schedule_runner.py:26-29`; test `tests/test_schedule_runner.py:205`).

**_PASSED_ENV** (`:82-97`): append `"DBUS_SESSION_BUS_ADDRESS"` and (so GLib can fall back, per N3) `"XDG_RUNTIME_DIR"`; the list only grows, existing env test (`test_schedule_runner.py:448-473`) stays valid.

**Job table** (`:454-458` required options, `:466-474` positional arity, `:511-515` runners): add
```python
"check-updates": ("--installer", "--uv"),       # required
wanted = 2 if job == "update" else 1             # unchanged: check-updates takes 0 positionals
run_id = job                                      # "check-updates"
"check-updates": lambda: _update(run_id, options["--installer"], options["--uv"]),
```
`_update` (`:320-358`) is reused whole: it passes `run_id` to `--run-schedule`, keeps the last `ok:/skipped:/failed:` line. Timeout wording at `:341-342` (`"failed: the update timed out"`) must become kind-aware (D-03), e.g. `"failed: the update check timed out"` when `run_id == "check-updates"`. Update the usage docstring (lines 15-19).

---

### `installer/version_cache.py` and `installer/version_status.py` (transform)

**Analog:** themselves.

**version_cache** (`:216-231`): add `stale_after: timedelta = STALE_AFTER` keyword to `is_stale` and `should_fetch`, replace `STALE_AFTER` use at `:222`; `should_fetch` forwards it. Never shift `now` (`_parse_iso` rejects stamps over `FUTURE_SKEW`, `:43`).
```python
def is_stale(entry, *, now): ... return now - checked_at >= STALE_AFTER      # :222
def should_fetch(entry, *, now): if not is_stale(entry, now=now): ...      # :225-231
```

**version_status thread path** (research Pattern 2): `refresh` (`:1791`) -> `_pass` (`:1825`) -> `should_fetch` gate (`:1891`) and `resolve_status` (`:542`, `:1893`) -> `resolve_github_release_status` (`:334`) / `_latest_status` (`:360`, gates at `:390,417,420`). Every keyword defaults, so other callers and tests are unchanged.

**Failure sink (D-12, N8):** goes in the existing except branch only (`version_status.py:401-413`); do NOT wrap `resolve_tag`:
```python
except (VersionError, OSError):          # :401  <- add: sink(tool.id, exc) when a sink is given
    latest = entry.latest_version if entry is not None else None
    ...
    failed_at=now_iso,
```

**`outdated_ids`** (D-13, contract for phase 35): pure function beside `ToolState` (`version_status.py:1032-1045`; `_PRESENT_HEALTH` at `:1029`):
```python
def outdated_ids(states: Iterable[ToolState]) -> frozenset[str]:
    # present tools whose state.version.outdated is True; never read Health.OUTDATED; None never counts
```
Confirm `ToolState.version` field name at `:1046+` when writing the plan task (not read in this pass).

**Seams for tests:** `VersionRefreshService(resolve_tag=..., now=...)` (`version_status.py:1204-1225`).

---

### `installer/run.py` (utility)

**Analog:** itself, `run_git_isolated` (`:181-195`):
```python
_GIT_INHERITED = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_ASKPASS", "SSH_ASKPASS")
_GIT_ISOLATION = ["-c", "core.hooksPath=/dev/null", "-c", "core.autocrlf=false"]
def run_git_isolated(argv: list[str]) -> str:
    env = {k: v for k, v in os.environ.items() if k not in _GIT_INHERITED}
    env.update(GIT_TERMINAL_PROMPT="0", SSH_ASKPASS_REQUIRE="never")
    return run_output([argv[0], *_GIT_ISOLATION, *argv[1:]], timeout=600, env=env)
```
Add keyword-only `timeout: float = 600`, `new_session: bool = True`, `env_extra: Mapping[str, str] | None = None`; default call stays byte-identical (guards: `tests/test_run.py:992`, `tests/test_setup.py:4859,4867`).

---

### `installer/cli.py`, `setup.py` (wiring)

**cli.py** (`:56-62`): `choices=list(schedules.UPDATE_SCHEDULE_IDS)` -> `[*UPDATE_SCHEDULE_IDS, "check-updates"]` (tmp-cleanup stays rejected; `tests/test_cli.py:109-123`).

**setup.py** (`:529-544`) `_schedule_run_deps` builds `RunDeps(...)` by keyword; add the refresh service handle (`version_refresh` is already in scope from `_build_services`, `:531`), notifier (`notify.notifier_for(platform.os, ...)`) and checkout (`context.checkout` already `Path(__file__).resolve().parent`, `:541`). `_run_schedule` (`:547-561`) stays unchanged: it prints the single line.

---

### `installer/schedules_screen.py` (component, event-driven)

**Analog:** itself, kind branches.

**CSS** (`:240`, N1): `SchedulesScreen DataTable { height: auto; max-height: 8; }` -> `max-height: 9` (header + 8 rows).

**_target** (`:430-435`): add before the final return `if schedule.kind is schedules.JobKind.CHECK_UPDATES: return "installed"`.

**_detail what** (`:461-466`): add an `elif schedule.kind is JobKind.CHECK_UPDATES:` text naming notify-send / osascript and, on macOS, "notifications come from Script Editor: allow them once in System Settings > Notifications"; state the changed-set rule and N7/N11 limits where space allows. Line `:480` (`job = ... else schedule.kind.value`) already prints `check-updates`. Replace TMP-specific daily checks with `schedule.daily` (D-06). Details clipped via `Rows(...)`, so keep lines short.

---

### Tests (modified, listed exceptions per N1 and D-22)

Edits are additions of one entry only; every other assertion keeps its meaning.
- `tests/test_schedules.py:105-140`: append `"check-updates"` to the ids tuple (`:106-114`), `"update check"` to labels (`:115-123`), `None` to the targets list (`:131-139`); `UPDATE_SCHEDULE_IDS` assertion (`:124-130`) unchanged.
- `tests/test_schedules_view.py:240-248` (last-cells list), layout assertions `:673-679` (table height 9; confirm with the pilot test first); `IDS` derived from `SCHEDULES` at `:40` self-adapts.
- `tests/test_schedules_lifecycle.py:104,107,110,152,548,600,654`, `tests/test_schedules_handover.py:62,493,494`: `turned_on` tuples and the `reconcile_lines` text that becomes `..., claude update, update check.` Each edit needs an exact reason in the plan SUMMARY.
- Unchanged: `tests/test_schedule_update.py:180-187`, `tests/test_container_e2e_schedules.py:174` (derived from `SCHEDULES`), `tests/test_cli.py:109-123`.

### New tests (scratch HOME, fakes only; N12)

**Analog for dispatch/check tests:** `tests/test_schedule_update.py` (`_tool`, `_claude(tmp_path, monkeypatch, ...)` helper returning `deps, recorder, leaf`, fake `Platform` `_FEDORA` at `:34`, direct `RunDeps(...)`, `run_schedule(id, deps, parent_holds_lock=True)`; spy `UpdateService` with zero calls). Test shape:
```python
def test_a_non_update_schedule_is_refused(tmp_path, monkeypatch) -> None:
    deps, recorder, _leaf = _claude(tmp_path, monkeypatch)
    assert run_schedule("tmp-cleanup", deps, parent_holds_lock=True) == ("failed: tmp-cleanup is not an update schedule", 2)
    assert recorder.calls == []
```
**Analog for runner log test** (R1 via `schedule_runner.main`): `tests/test_schedule_runner.py:576-589` (`_update(tmp_path, uv, checkout)` helper, `_script(bin_dir, "uv", 'echo "ok: ..."')` fake uv, `_texts(lines, run_id) == ["start", "ok: ..."]`); for `_PASSED_ENV` growth copy the env test at `:448-473` (`monkeypatch.setenv`, `/usr/bin/env > seen`, key-by-key compare, assert unlisted key absent).
**Analog for environment isolation:** `tests/test_daemon.py:50` (`_AGENT_ENV` dict style) and the rule N12: inject `which` and `run` into every notifier test; `monkeypatch.setenv("PATH", <tmp>)` and delenv `DBUS_SESSION_BUS_ADDRESS`/`XDG_RUNTIME_DIR` in any test that could reach a real binary; never call default `notifier_for(...)`.
**Fixture bare repo / git:** the sandbox forbids launching `git` and `gh` from unit tests (N12): drive `run_git_isolated`'s replacement through an injected fake runner returning canned outputs; the byte-compare of the checkout is an orchestrator-level container check.
**Python versions:** assertions must hold on 3.12 and 3.15; no timing assertions.

### Container check (test/script, request-response)

**Analog:** the existing `schedules` target: `scripts/container-e2e-verify.sh` (usage line `:97`, `SCHEDULES_*` vars `:2365-2374`, log helpers `:2489-2494`, `schedules_tester` call `:2739`) and `tests/e2e_schedules_driver.py` (verbs `_ARITY = {"on": 1, "off": 1, "retime": 3, "cells": 0, "argv": 1}` at `:29`, `_context()` `:32`, `_run()` `:46`). Add a `check-updates` verb/pair; orchestrator-run only, cannot prove the bus variable reaches `notify-send` (N9); never installs on the real host. Any usage-text change shifts classified PATH lines in `tests/test_shell_scripts_path.py`: move them in the same commit. macOS bash 3.2: no apostrophes or unbalanced quotes in a heredoc inside `$(...)`. Minimum fallback: a host test with a stubbed runtime.

## Shared Patterns

### One result line, "; " clauses
**Source:** `installer/schedule_run.py:58-63`, `installer/helper_assets/schedule_runner.py:345-358, 522-523`. **Apply to:** `update_check.py`, runner timeout wording. The runner logs only `start` plus the child's last `ok:/skipped:/failed:` line (D-21); nothing else survives.

### Sanitized, bounded reasons
**Source:** `schedule_run.py:21, 35-42` (`_REASON_LIMIT = 300`, `sanitize_log_line`). **Apply to:** notify skip reasons, lookup failure reason, installer-check skip reason.

### Atomic state writes under a scratch-HOME-safe path
**Source:** `version_cache.py:38-39, 212-213` (`ensure_dir`, `atomic_write_text`), `ctx.state_path.with_name(...)`. **Apply to:** `update-check.json`; also add to `_state_artifacts` (`schedules.py:1803-1811`).

### House child policy
**Source:** `run.py:115-151, 154-178` (stdin DEVNULL, optional timeout, `new_session`). **Apply to:** `notify.py`, git self-check. Use `new_session=False` so the runner group kill reaches them.

### Environment closure (no token, no unit bus address)
**Source:** `daemon.py:34-47` (`PASSTHROUGH_KEYS`, `ENVIRONMENT_KEYS`), `daemon.py:55-59` (`check_environment`), runner `_PASSED_ENV` `schedule_runner.py:82-97`. **Apply to:** D-11 (no `GITHUB_TOKEN`/`GH_TOKEN`), D-17 (bus variable added to the runner only). Add a token grep test over unit, state file and log.

### Provisional-decision recording
**Apply to:** every plan implementing N1-N11: record the decision in the plan and repeat "needs confirmation" in that plan's SUMMARY.

### Test-suite guards to respect
`tests/test_reachability.py` (new module imported by an entry point within the plan or next); `tests/test_docs_only.py` LEDGER (avoid new `.md` or `.planning` string literals in tests, or add LEDGER entries); `tests/test_docs.py` banned fragments (`[Showing lines`, `Use offset=`); `tests/test_shell_scripts_path.py` line numbers.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| desktop notification send (`notify.py` body) | utility | request-response | No existing notifier; use `run.py` runner + the argv in CONTEXT D-17/D-18 and research "Code Examples" |
| git ls-remote self-check | service | request-response | Only `run_git_isolated` exists (600 s, new session); extended per above |
| `.claude/architecture.md` schedules section | docs | n/a | None exists (N10); add a short Phase 34 subsection following the per-phase pattern |

## Metadata

**Analog search scope:** `installer/`, `installer/helper_assets/`, `tests/`, `scripts/`, `setup.py`.
**Files read:** about 14 source and test files (targeted ranges); `ToolState.version` field name and `git ls-files` for each analog not individually re-verified (all under tracked `installer/`, `tests/`, `scripts/`).
**Pattern extraction date:** 2026-11-21
