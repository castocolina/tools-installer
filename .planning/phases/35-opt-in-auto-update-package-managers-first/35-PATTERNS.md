# Phase 35: Opt-in auto-update, package managers first - Pattern Map

**Mapped:** 2026-11-22
**Files analyzed:** 22 (new and modified)
**Analogs found:** 22 / 22 (all tracked in git; line numbers are from the working tree on 2026-11-22 and are shifted from CONTEXT's)

Binding inputs: 35-CONTEXT.md, 35-RESEARCH.md (Reconciliation), and the orchestrator decisions O1-O4 and items 5-10 (provisional, "needs confirmation"). Where CONTEXT and the code disagree, the code lines below win.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `installer/update_all.py` (new: planner, executor, store, summary line) | service (pure planner + store) | transform + file-I/O | `installer/update_check.py` | exact |
| `installer/schedules.py` (row, `JobKind.UPDATE_ALL`, `default_on`, `runner_argv`, `RUN_SCHEDULE_IDS`, store/log paths, `_state_artifacts`, `_row_action`) | model/config | CRUD | its own `CHECK_UPDATES` additions (`:41,97,105,155,873,1816-1830`) | exact |
| `installer/schedule_run.py` (dispatch, `_update_tool` refactor, `RunDeps` fields) | service | request-response | itself, `_check` / `_run_unlocked` / `run_schedule` (`:126-163`) | exact |
| `installer/helper_assets/schedule_runner.py` (job `update-all`, per-job timeout, `_WAIT_BOUND` comment) | utility (stdlib runner) | event-driven (timer) | itself, `check-updates` job (`:323-358, 476, 534`) | exact |
| `installer/cli.py` (`--plan`, validation) | config | request-response | itself, `--run-schedule` / `--parent-holds-run-lock` (`:55-72`) | exact |
| `installer/update.py` (only if a per-tool bound or an `UpdateService` seam is needed) | service | request-response | itself, `update_refusal` (`:283`), `run` (`:660`) | exact |
| `installer/compose.py` (scratch-cache service for plan mode, O2) | provider | request-response | `compose._build_services` (`:402-410`) | role-match |
| `setup.py` (`_schedule_run_deps`, `_run_schedule` forwards `plan`) | config (wiring only) | request-response | itself (`:535-575`) | exact |
| `installer/schedules_screen.py` (`what`, `_target`, detail/extra lines for the new row) | component | request-response | its `check-updates` branches (`_detail` `:475-498`, `_target` `:445-452`) | exact |
| `tests/test_update_all.py` (new: planner, executor, store, summary) | test | transform | `tests/test_update_check.py` + `tests/update_check_doubles.py` | exact |
| `tests/test_update_all_job.py` (new: through `schedule_runner.main`) | test | event-driven | `tests/test_update_check_job.py` | exact |
| `tests/test_update_all_contract.py` (new: sudo/pkexec/doas AST, choices, row truth table) | test | transform | `tests/test_update_check_contract.py` | exact |
| `tests/test_container_e2e_update_all.py` (new, static pin) | test | file-I/O | `tests/test_container_e2e_bun.py` | exact |
| `tests/e2e_update_all_driver.py` (new, container-only driver) | utility | batch | `tests/e2e_bun_driver.py` | exact |
| `scripts/container-e2e-verify.sh` (`cmd_update_all`, dispatch, usage) | script | batch | `cmd_bun_lifecycle` (`:3103`) | exact |
| `tests/test_shell_scripts_path.py` (renumber classified lines when usage grows) | test | file-I/O | itself | exact |
| Edited existing tests (exceptions): `tests/test_schedules.py:105-140`, `tests/test_schedules_view.py:240-248,679`, `tests/test_layout_80x20.py`, `tests/test_cli.py:114-125`, `tests/test_schedule_runner.py`, `tests/test_update_check_contract.py` (`:47-58` choices, `test_exactly_two_rows_are_daily`), runner_argv/unit-template tests | test | - | themselves | exact |
| Docs: `.claude/architecture.md` (phase 35 subsection), `35-SPEC.md` dated amendments (O2, O3, D-05, D-09) | docs | - | the phase 34 subsection of `.claude/architecture.md` | role-match |

## Pattern Assignments

### `installer/update_all.py` (service, pure planner + store + executor)

**Analog:** `installer/update_check.py` (module shape), `installer/notify.py` (injected seam).

**Module shape**: docstring that states limits; `from __future__ import annotations`; injected seams (`Refresher` Protocol `:41-54`, `Callable` clock `:264`); constants beside functions (`RESULT_LIMIT = 300`, `NOTIFIED_CAP = 64 * 1024`, `:58-59`); no subprocess.

**Imports** (`update_check.py:12-35`):
```python
from __future__ import annotations
import json
from collections.abc import Callable, Collection, Mapping, Sequence
from pathlib import Path
from installer import schedules
from installer.atomic import atomic_replace_entry, read_capped
from installer.locations import ensure_dir
from installer.model import TOOL_ID_RE, Tool
from installer.notify import Notifier, reason_line
from installer.version_status import FailureSink, Health, ToolState, outdated_ids
```
Add: `from installer.deps import resolve_dependencies` (keyword-only `available`, `is_installed`; pass `lambda _t: True` constants, see RESEARCH Pattern 2 rule 4), `from installer.update import update_refusal`, `from installer.ownership import ManagerOwnership`.

**Strict store reader** (copy `update_check.py:118-139`, change the keys). Decision 6: UTF-8, version 1, id shape, bounded `read_capped`, `RecursionError`/`OverflowError`, `follow_symlinks=False`; a directory at the path stays untouched (OSError -> `(empty, False)`). The `(value, healthy)` tuple lets the caller report damage:
```python
def read_notified(path: Path) -> tuple[frozenset[str], bool]:
    try:
        data = read_capped(path, NOTIFIED_CAP, follow_symlinks=False)
    except FileNotFoundError:
        return frozenset(), True
    except OSError:
        return frozenset(), False
    try:
        raw: object = json.loads(data.decode("utf-8")) if data is not None else None
    except (ValueError, RecursionError, OverflowError):
        return frozenset(), False
    ...
    if type(version) is not int or version != 1 or not isinstance(ids, list):
```
For `updated-today.json` the body is `{"version":1,"updated":{"<id>":{"date":"YYYY-MM-DD","by":"update-all"|"update-claude"}}}`: validate every key with `TOOL_ID_RE.fullmatch`, every `date` with `date.fromisoformat` (inside the same try), `by` against the two literals; any failure reads as empty and unhealthy.

**Writer** (copy `update_check.py:142-145`; never `atomic_write_text`, decision 6):
```python
def write_notified(path: Path, ids: Collection[str]) -> None:
    ensure_dir(path.parent)
    data = json.dumps({"version": 1, "notified": sorted(ids)}) + "\n"
    atomic_replace_entry(path, data.encode("utf-8"), mode=0o600)
```
Record per tool right after its outcome so a timeout kill keeps finished work (RESEARCH Pattern 5); `except OSError` -> a clause, never an exit-code change (compare `update_check.py:311-314`).

**Outdated input**: `outdated_ids(states)` (`version_status`; imported in `update_check.py:35`, used `:191`). Order refresh inputs with `oldest_checked_first` (`:243-254`) and window `CHECK_STALE_AFTER` (`:38`) (D-07). O1: expose `plan_managers(...)` and `plan_dependents(...)` as two pure functions that take the outdated set as an input; the executor calls `refresh` again between them (`UpdateService.run` already invalidates after outcomes, RESEARCH Pitfall 2).

**Summary line within 300 chars**: model on `update_check.result_line` (`:228-240`): fixed clauses first, free-text reasons share the remaining budget via `reason_line`:
```python
def result_line(count, clauses):
    prefix = f"ok: {count} updates available"
    reasons = [" ".join(reason_line(reason).split()) for _, reason in clauses]
    fixed = sum(len(label) + 2 + (2 if reason else 0) for (label, _), reason in zip(clauses, reasons, strict=True))
    share = max(0, (RESULT_LIMIT - len(prefix) - fixed) // reason_count) if reason_count else 0
```
New: `summary_line` with `ok: N updated, M skipped` / `failed: K failed (<first tool>), N updated, M skipped` (D-15), then `; notify skipped: <reason>` last (D-17). Define `RESULT_LIMIT = 300` locally (the "mirrors the runner" comment at `:57`) rather than importing the stdlib runner.

**Notification** (D-17, O3): call `notify(summary, body)` once only when `updated + failed > 0` after a real run; a returned string or an exception becomes a clause (compare `update_check.py:306-310`); counts and registry ids only (`notify.py:1-6` docstring forbids free text).

**Failure propagation** (RESEARCH Pattern 3): in-memory `blocked: dict[str, str]`, `transitive_requires` ten-line walk with a visited set.

**Per-tool execution**: call the refactored `schedule_run._update_tool(tool, deps)` (below); for `cursor-agent` call `_update_cursor_agent` with `schedules.schedule_by_id("update-cursor-agent")`.

---

### `installer/schedules.py` (model/config)

**Analog:** its own phase 34 additions.

**Kind and row** (`:41`, `:50`, `:97`):
```python
    CHECK_UPDATES = "check-updates"          # add: UPDATE_ALL = "update-all"
    daily: bool = False  # Cadence belongs to the row, not its kind.   # add: default_on: bool = True
    Schedule("check-updates", "update check", JobKind.CHECK_UPDATES, None, 24, "09:00", daily=True),
    # NEW: Schedule("update-all", "update all", JobKind.UPDATE_ALL, None, 24, "03:00", daily=True, default_on=False)
```
Add the comment pattern used at `:96` ("09:00 is off the update grid at ...") for 03:00 (before the 09:00 check).

**Closed id tuples** (`:99-106`): widen the second generator to `kind in (JobKind.CHECK_UPDATES, JobKind.UPDATE_ALL)`; `UPDATE_SCHEDULE_IDS` stays (it filters `JobKind.UPDATE`).

**`_row_action`** (`:1561-1575`; the one seeding line):
```python
    if record.decided is None:
        return "turn-on"          # -> "turn-on" if schedule.default_on else "none"
```
Truth table test: `tmp-cleanup` branch is unaffected (the `record.decided is None` inside it is the marker logic).

**`runner_argv`** (`:873`): mirror the CHECK branch:
```python
    elif schedule.kind is JobKind.CHECK_UPDATES:
        job = ["check-updates", "--installer", str(ctx.checkout), "--uv", str(uv)]
    # NEW: elif schedule.kind is JobKind.UPDATE_ALL: job = ["update-all", "--installer", ..., "--uv", ...]
```
Keep the six-element `uv run --no-cache --no-project --script <runner>` prefix (the contract test parses `argv[6:]`).

**State files** (`:155`, `:1816-1830`): add `UPDATED_TODAY_NAME = "updated-today.json"` beside `NOTIFIED_NAME`, `UPDATE_ALL_LOG_NAME = "update-all.log"`, accessors beside `notified_path`:
```python
def notified_path(ctx: ScheduleContext) -> Path:
    return ctx.state_path.with_name(NOTIFIED_NAME)
def _state_artifacts(ctx):
    return (ctx.state_path, damaged_path(ctx.state_path), notified_path(ctx), ctx.log_path, ...)
```
Log path is `ctx.log_path.with_name(...)` (D-12); both join `_state_artifacts` and are swept on uninstall. `_RECORD_KEYS` (`:269`) is unchanged.

**Guards to check** (gone-target drop only for `JobKind.UPDATE`, RESEARCH R2 / Pattern 1): `_require_available` (`:721-725`), `row_state` (`:1488-1510`), `_reconcile_pass` (`:1704-1725`). `update-all` has `target=None` and must stay out of the `UPDATE` branches.

---

### `installer/schedule_run.py` (service, request-response)

**Analog:** itself.

**Seam fields** (`RunDeps`, `:25-37`): add defaulted fields so existing constructors keep working (as phase 34 did for `notify`/`refresh`/`git`): `today: Callable[[], date]` (injected local date, never `date.today()` in logic), `plan: bool = False` is not needed here if plan mode is a separate function.

**Refactor** (RESEARCH Pattern 4): `_update(schedule, deps)` (`:50-68`) finds the tool by `schedule.target`, then runs the four-step body. Extract `_update_tool(tool, deps)` and keep `_update` as a two-line wrapper; keep the error mapping:
```python
    except (UpdateError, CommandError, OSError) as error:
        return f"failed: {_reason(error)}", 1
    line, code = schedules.update_result_line(outcome, before, after)
```
**Dispatch** (`:134-150`): add the `UPDATE_ALL` branch first in `_run_unlocked` and add the kind to the gate at `:149`:
```python
    if schedule.kind is schedules.JobKind.CHECK_UPDATES:
        return _check(deps)
    ...
    if schedule.kind not in (schedules.JobKind.UPDATE, schedules.JobKind.CHECK_UPDATES):
        return f"failed: {schedule_id} is not an update schedule", 2
```
**Lock** (`:153-163`) is the one lock rule; copy it for nothing new (`skipped: busy`, exit 0). Plan mode (D-18) bypasses `run_schedule`'s lock entirely: add a separate `plan_schedule(deps) -> list[str]` and have `setup.py` print it.

**Not-wired guard** (`_check`, `:126-131`): `return "failed: ... is not wired", 2` when a seam is `None`.

**Per-tool rows read the store** (D-14): a `UPDATE` row skips only when the entry has `by == "update-all"` and `date == today`; add that check in `_update_tool`'s caller path and record `by` = the row's id kind (`update-claude` literal per D-13) on `outcome.status == "updated"`.

---

### `installer/helper_assets/schedule_runner.py` (stdlib runner)

**Analog:** itself, the `check-updates` job.

**`_update` signature and child** (`:323-358`): add `timeout: int = _UPDATE_TIMEOUT`, pass `timeout=timeout` at `:344`; `update-all` passes `readonly=True` (it is what forwards `DBUS_SESSION_BUS_ADDRESS` per job through `extra_env`; do NOT add it to `_PASSED_ENV`, RESEARCH Pitfall 5, `tests/test_update_check_contract.py:77,97-104`):
```python
        timeout=_UPDATE_TIMEOUT,
        cwd=Path(installer),
        extra_env=({"PYTHONDONTWRITEBYTECODE": "1", **({"DBUS_SESSION_BUS_ADDRESS": os.environ[...]} if os.environ.get(...) else {})} if readonly else None),
```
**Job table** (`:476`, `:534`):
```python
        "check-updates": ("--installer", "--uv"),
        "check-updates": lambda: _update(run_id, options["--installer"], options["--uv"], what="update check", readonly=True),
# NEW: "update-all": ("--installer", "--uv") and
#      "update-all": lambda: _update(run_id, ..., what="update-all", readonly=True, timeout=_UPDATE_ALL_TIMEOUT),
```
**Constants** (`:52,71-74`): add `_UPDATE_ALL_TIMEOUT` (2 to 3 h); re-derive the `_WAIT_BOUND` comment (it says holders live at most `_UPDATE_TIMEOUT` plus kill grace); keep 7200 and say the 3 h holder makes a later per-tool row log `skipped: busy`, accepted. Update the module docstring job list (`:16-17`). Stdin: `_run_child` already has `stdin=subprocess.DEVNULL` (`:232`); D-16 only adds a pinning test (decision 5), `test_every_runner_child_gets_a_closed_stdin` already exists, do not duplicate.

---

### `installer/cli.py` (config)

**Analog:** itself (`:55-72`):
```python
    parser.add_argument(
        "--parent-holds-run-lock",
        action="store_true",
        help="internal: the schedule runner already holds the run lock",
    )
    ns = parser.parse_args(argv)
```
Add `--plan` the same way (`action="store_true"`), and after `parse_args` follow the existing `parser.error(...)` use in this file for the combination check (`--plan` valid only with `--run-schedule update-all`). `Options` (`:10-90`) gains `plan: bool = False`. `choices=list(schedules.RUN_SCHEDULE_IDS)` (`:57`) needs no edit once the tuple widens; update the help text ("an update row, the update check or update-all").

---

### `installer/compose.py` and `setup.py` (wiring only; architecture rule 4)

**Analog:** `setup.py:535-575` (`_schedule_run_deps`, `_run_schedule`):
```python
    return RunDeps(tools=tools, updates=updates, resolve_owner=version_refresh.resolve_owner,
        probe_version=lambda tool, own: probed_version(tool, own, probe_version_output),
        context=schedules.context_for(platform.os, checkout=Path(__file__).resolve().parent, read_models=cursor_shim.read_models),
        notify=notifier_for(platform.os), refresh=version_refresh, git=git_for_check)
    ...
    line, code = run_schedule(options.run_schedule or "", _schedule_run_deps(tools, platform), parent_holds_lock=options.parent_holds_run_lock)
    print(line)
    return code
```
Add the clock seam to `RunDeps(...)`; `_run_schedule` forwards `options.plan` and prints the plan lines (no logic in `setup.py`). O2 scratch route: `compose._build_services` (`:402-410`) takes an optional `cache_path`; setup builds the plan-mode service against a `tempfile.TemporaryDirectory` copy of `versions.json`, removed in `try/finally`. If impractical, reword the SPEC and say so in the SUMMARY (O2).

---

### `installer/schedules_screen.py` (component)

**Analog:** the check-updates branches: `_target` (`:445-452`), `_detail` `what` chain (`:475-498`), `_extra_lines` (`:532-564`). Add one branch each for `UPDATE_ALL` (CONTEXT D-04). `space` already calls `schedules.turn_on` (`_change_worker :646-655`). Keep the macOS permission sentence visible at 80x20 (decision 7); the table grows to 10 rows (`tests/test_layout_80x20.py`, `tests/test_schedules_view.py:679`).

---

### Tests

**`tests/test_update_all.py`** (analog `tests/test_update_check.py` and `tests/update_check_doubles.py`): fakes only: `tool_named` (`:26`), `pass_state` from `tests.state_doubles`, `typed_fake` notifier (`test_update_check_contract.py:27`), injected clock. Planner tests use `pass_state` fixtures (no PATH); executor tests inject `runner`, `resolve_owner`, `probe_version`, `notify`, clock (RESEARCH Pitfall 10). Add an `UpdateService` spy that records calls to prove "a failing manager skips dependents" and "nothing else spawns".

**`tests/test_update_all_job.py`** (analog `tests/test_update_check_job.py:138+` "hermetic job changes only the allowed files"): go through `schedule_runner.main([...])`, scratch `PATH`, `HOME`, clear `DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR`; assert the run log vs the shared log, the changed-files set, a second deterministic run.

**`tests/test_update_all_contract.py`** (analog `tests/test_update_check_contract.py:36-60,97,107`): per-row runner job (`test_every_schedule_row_has_a_runner_job_with_its_own_id` covers the new row automatically); AST/grep test for `sudo`/`pkexec`/`doas` in the new module (model `test_the_new_modules_hold_the_hard_rules`, `:107`); "no Policies row" asserts `tweaks.BUNDLES` rows, not ids starting with `schedule:`.

**Existing tests that must change (explicit exceptions, keep each assertion's meaning):**
- `tests/test_update_check_contract.py:47-58`: `test_run_schedule_choices_are_the_update_and_check_rows` expected set gains `UPDATE_ALL`; the `all(... for s in SCHEDULES if s.daily)` assertion holds (daily rows have interval 24).
- `test_exactly_two_rows_are_daily`: becomes three (name it for the real count).
- `tests/test_layout_80x20.py`, `tests/test_schedules_view.py:240-248,679`: row count 9 -> 10; `"never"` choice; detail panel loses a row at 80x20.
- `tests/test_schedules.py:105-140`, `tests/test_cli.py:114-125` (+ new `--plan` cases), `tests/test_schedule_runner.py` (jobs, per-job timeout, stdin), `runner_argv` and unit-template tests, `tests/test_shell_scripts_path.py` (classified PATH lines renumbered in the same commit when the usage text grows).
- Unchanged: `tests/test_schedules_lifecycle.py:107,152,256,441`, `tests/test_schedules_handover.py:493`, `tests/test_container_e2e_schedules.py:174`, `tests/e2e_schedules_driver.py:49,81`, `tests/test_schedule_update.py:180-187`.

---

### `scripts/container-e2e-verify.sh` and its driver (batch, container)

**Analog:** `cmd_bun_lifecycle` (`:3103-3135`) with `tests/e2e_bun_driver.py`; the landing target skeleton is shared with `cmd_herdr_keys` (`:3144`) and `cmd_ghostty`:
```bash
cmd_bun_lifecycle() {
  local failed=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --keep-image) LANDING_KEEP_IMAGE=1 ;;
      *) die "unknown bun-lifecycle option: $1" ;;
    esac
    shift
  done
  LANDING_CONTAINER_NAME="tools-installer-e2e-bun-$$"
  CONTAINER_NAME="$LANDING_CONTAINER_NAME"
  IMAGE="$LANDING_IMAGE"
  DISTRO=fedora
  LANDING_DRIVER_MODULE=tests.e2e_bun_driver
  PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-bun"
  LANDING_TRANSCRIPT="$PHASE_DIR/bun-transcript.log"
  trap landing_teardown EXIT
  ensure_phase_dir
  : >"$LANDING_TRANSCRIPT"
  landing_note_image
  landing_bootstrap
  landing_step install-mmdc install-mmdc || failed=1
  ...
  return "$failed"
}
```
Copy as `cmd_update_all` (container `tools-installer-e2e-update-all-$$`, driver `tests.e2e_update_all_driver`, `PHASE_DIR .../container-update-all`; steps such as `plan` and `real-run`, each collected into `failed`). Register in the dispatch (`bun-lifecycle) cmd_bun_lifecycle "$@" ;;` at `:3453`) and in `usage()` (`:54`). Items for the driver (decisions 8, 9): fake managers; the `plan` verdict must assert the uv line says `would update`, otherwise the verdict says so and fails (RESEARCH Pitfall 9: `bootstrap_uv` has no receipt); capture `uv --version` before and after, and whether rc files changed (Pitfall 8). Real run goes through `uv run --script runner.py update-all --installer ... --uv ...`. Orchestrator-run only, never executor-run.
No apostrophes or unbalanced quotes inside a heredoc inside `$(...)` (macOS bash 3.2); no `find -printf`.

**`tests/test_container_e2e_update_all.py`** (analog `tests/test_container_e2e_bun.py:1-40`): never starts a container; reads the committed script text, runs extracted bash functions with the `_CT_STUB` stubbed `ct` (`CALLS` file), imports the driver for pure verdict functions only; pins `_CONSTANTS`, the verdict markers, and the EXIT-trap teardown.

---

## Shared Patterns

### Link-safe state file I/O
**Source:** `installer/update_check.py:118-145` (`read_capped(..., follow_symlinks=False)` + `atomic_replace_entry`). **Apply to:** `updated-today.json` writer/reader; the `update-all.log` appender (never `open(..., "a")`, never `atomic_write_text`; RESEARCH Anti-Patterns).

### One result line, bounded
**Source:** `update_check.result_line` (`:228-240`), `RESULT_LIMIT = 300`, `notify.reason_line` (`notify.py:30-33`). **Apply to:** `update_all.summary_line` and every runner-facing line.

### One lock
**Source:** `schedule_run.run_schedule` (`:142-163`): `parent_holds_lock` or `runlock.try_acquire` -> `skipped: busy`. **Apply to:** the real update-all run; store writes happen only while held. Plan mode takes no lock.

### Refusals shared by plan and run
**Source:** `installer/update.py:283` `update_refusal` (zero subprocess) mapped through `schedules.update_result_line(outcome, None, None)` (`schedules.py:488`) so the plan and the run print the same text. **Apply to:** planner skip texts.

### Injected seams, no host effect
**Source:** `RunDeps` defaults (`schedule_run.py:34-37`: `notify = no_notifier`), `tests/update_check_doubles.py`. **Apply to:** clock, notifier, refresher, runner, `resolve_owner`, `probe_version`; tests never launch `git`/`gh`; no timing-sensitive assertions (poll with a cap); `os.killpg` may raise `PermissionError` on macOS; CI runs Python 3.15 vs local 3.12.

### Reachability guard
A module added in one plan must be imported by a production entry point in that plan or the next: `installer/update_all.py` is imported by `installer/schedule_run.py` in the plan that adds it (or the next).

### Provisional decisions to record in the implementing plan and its SUMMARY
O1 (second pass over dependents), O2 (scratch cache copy for `--plan`; dated SPEC amendment), O3 (notify only when `updated + failed > 0`; dated SPEC amendment), O4 (the eight script tools with no `update` argv, listed by name: `antigravity, codex, fnm, herdr-app, kitty, opencode, volta, xcode-clt`), D-05 (manager order amends AUTOUPD-02), uv rc-rewrite accepted limit (item 8).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| Manager-order depth walk over owner chain (inside `update_all.py`) | utility | transform | `resolve._RANK` ranks install-method kinds, not owner chains (CONTEXT D-05); use RESEARCH Pattern 2 rule 2 with a visited set. |
| Scratch-copy cache service for `--plan` (O2) | provider | file-I/O | No existing code builds a service against a temporary cache path; closest is `compose._build_services`. |
| Per-tool command bound inside the child | utility | request-response | `run_captured_in_group` passes `timeout=None` today (CONTEXT D-11); extend, no analog. |

## Metadata

**Analog search scope:** `installer/`, `installer/helper_assets/`, `tests/`, `scripts/container-e2e-verify.sh`, `setup.py`, phase 34 contract tests.
**Files read:** about 12 (partial reads of large files: `schedules.py`, `schedule_runner.py`, `container-e2e-verify.sh`, `setup.py`).
**Tracked-source gate:** analogs are under `installer/`, `tests/`, `scripts/`, `setup.py`; `git ls-files` confirmed `installer/update_check.py`, `installer/notify.py`, `tests/test_container_e2e_bun.py`, `tests/update_check_doubles.py`, `tests/e2e_bun_driver.py`, `tests/e2e_landing_driver.py`; no mirror paths are named.
**Pattern extraction date:** 2026-11-22
