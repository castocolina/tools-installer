# Phase 20: Install plan with dispositions - Pattern Map

**Mapped:** 2026-10-17
**Files analyzed:** 22 (12 modified source, 2 deleted, 1 script, 7 test/doc files)
**Analogs found:** 21 / 22 (`tests/test_plan.py` is new; its analog is `tests/test_session.py` + `tests/state_doubles.py`)

Line numbers are from the tree at `0ddffed`. Every analog below is git-tracked source (none are mirrors).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/deps.py` (Resolution + closure/blocked/requested_by) | utility (pure core) | transform | itself, `deps.py:22-120` | exact (additive) |
| `installer/session.py` (Disposition, PlanRow, build_plan, RowOutcome, WORDS, execute_plan, exit_code, retained, ran_anything) | service (pure core) | transform + batch | `session.py` `Summary`/`run_installs`/`with_sensitive_confirm` (`:66-250`) | exact |
| `installer/update.py` (`update_refusal` extraction, PLAN-08 wording) | service | request-response | `update._perform` early returns (`:247-310`) | exact |
| `installer/render.py` (`render_plan`, `render_run_summary`; delete `render_audit`/`render_summary`/`render_dependency_notice`) | utility (render) | transform | `render.py:34-87` | exact |
| `installer/execute_screen.py` (plan-driven review/progress, `r`, wait worker, worker on `execute_plan`) | component (Textual ModalScreen) | event-driven | itself: `_execute_worker` `:617-740`, `_with_repair` `:240-277`, `_render_captured` `:1159-1166` | exact |
| `installer/wizard_app.py` (`_install_closed` retained selection, outcome fold, sync gate) | provider (app) | event-driven | itself `:2893-2930`, `on_tool_updated` `:3023-3050` | exact |
| `installer/app.py` (`run_wizard` on build_plan/execute_plan) | controller (headless) | request-response | itself `:130-197` | exact |
| `installer/catalog_tui.py` (PLAN-08 string at `:823`) | component | request-response | itself | exact |
| `installer/version_status.py` (`UNPROVEN_NOTE` reword, L-20-06) | config (copy const) | — | `version_status.py:606` | exact |
| `installer/engine.py` (delete `reapply_post_install` `:300-316`) | service | — | deletion | n/a |
| `installer/audit.py` (DELETE), `installer/selection.py` `tool_choices`, `installer/prompt.py` two-step | — | — | deletion (Pitfall 10) | n/a |
| `setup.py` (`_build_services`, `_session_exit_code` via `exit_code`, headless exit) | config (wiring) | request-response | `setup.py:764-1200` `_build_app`, `:1318-1327`, `:1550-1562` | exact |
| `scripts/container-e2e-verify.sh` (`SUMMARY_RE`) | config (script) | transform | itself `:242-255` | exact |
| `.claude/architecture.md` (Phase 20 section, rewrite Phase 3/13/14) | doc | — | Phase 19 section | exact |
| `tests/test_plan.py` (NEW: G cases A-I x tiers, health x owner, purity) | test | — | `tests/test_session.py` + `tests/state_doubles.py::pass_state` | role-match |
| `tests/state_doubles.py` (`plan_state`, `HeldRefreshService`, fake `UpdateService`) | test fixture | — | `FrozenStateService` `:137-157` | exact |
| `tests/test_session.py`, `tests/test_deps.py`, `tests/test_render.py` | test | — | themselves | exact |
| `tests/test_execute_screen.py`, `tests/test_wizard_app.py`, `tests/test_app.py`, `tests/test_setup.py` (ports) | test | — | themselves (`_inputs(...)` helper) | exact |
| `tests/test_docs.py` (`_PHASE_20_REQUIRED`) | test | — | `_PHASE_19_REQUIRED` `:188-221` | exact |
| `tests/test_update.py`/`test_catalog_tui.py` (grep test "moving it there", 78-col) | test | — | `test_catalog_tui.py:1741-1746` | exact |

## Pattern Assignments

### `installer/deps.py` (pure core, transform)

**Analog:** itself. Keep `order`/`dragged_in`/`warnings` byte-identical (23 tests in `tests/test_deps.py` pin them).

Current dataclass (`deps.py:22-29`) - add defaulted fields after these:
```python
@dataclass(frozen=True)
class Resolution:
    order: tuple[Tool, ...]
    dragged_in: tuple[str, ...]
    warnings: tuple[str, ...]
```
`collect()` (`:59-72`) is where `requested_by` is recorded: thread the root from `for tool in selected: collect(tool)` into the recursion, set `requested_by.setdefault(dep.id, root.id)` only for ids not in `selected_ids`.
`is_blocked` (`:80-99`) is where `Blocked.needs` comes from (the `dep_blocked` branch); the warning texts at `:101-106` become `Blocked.reason` verbatim:
```python
            if not available(tool) and not is_installed(tool):
                warnings.append(f"{tool.id} is not available on this platform — skipped")
            else:
                warnings.append(f"{tool.id} skipped — a dependency is unavailable")
```
`closure` = run the existing step-3 `visit` topological sort over `[t for t in wanted if t.id not in blocked]` (do not write a second sort; reuse the same `visit` with a different id set).

---

### `installer/session.py` (pure core: plan + execution + vocabulary)

**Analog:** itself.

**Imports pattern** (`session.py:1-14`) - extend this block, keep module docstring style:
```python
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal, Protocol

from installer.engine import ChecksumPolicy, InstallOutcome, install_tool
from installer.enums import InstallStatus, Priority
from installer.model import Tool
...
from installer.update import UpdateOutcome
```
New imports needed: `enum.StrEnum`, `installer.deps.resolve_dependencies`, `installer.resolve.resolve_methods`, `installer.selection.select_tools`, `installer.version_status.ToolState, Health` (check for import cycles: `version_status` must not import `session`).

**Frozen dataclass + closed Literal style** (`:16-19`, `:106-134`) - model `Result` and `RowOutcome` on this; `has_failure`'s docstring explains why manual/no_method are not failures (carry that reasoning into `_FAILURE`):
```python
MismatchChoice = Literal["retry", "skip", "fallback"]
...
@dataclass(frozen=True)
class Summary:
    installed: tuple[str, ...]
    ...
    @property
    def has_failure(self) -> bool:
        """... manual_required and no_method do not count ..."""
```

**Forward-pass dependency propagation + mismatch retry** (`run_installs` `:168-235`) - fold this body into `execute_plan` verbatim for INSTALL/REPAIR/REINSTALL rows, then delete `run_installs`:
```python
    outcomes: list[InstallOutcome] = []
    unresolved: set[str] = set()
    for tool in tools:
        if should_continue is not None and not should_continue():
            break
        blocked = tuple(dep_id for dep_id in dict.fromkeys(tool.requires) if dep_id in unresolved)
        if blocked:
            outcome = InstallOutcome(tool.id, InstallStatus.DEPENDENCY_FAILED, blocked_by=blocked)
        else:
            outcome = install(tool, platform, runner, resolve_tag, tools=catalog)
            if outcome.status == InstallStatus.CHECKSUM_MISMATCH and on_mismatch is not None:
                choice = on_mismatch(tool.id)
                if choice == "retry": ...
                elif choice == "fallback": ... checksum_policy="continue" ...
        if outcome.status in _UNRESOLVED:
            unresolved.add(tool.id)
```
Differences: a `should_continue()` False marks remaining rows `not_attempted` (one outcome per row, D-08) instead of `break` leaving them absent; `_UNRESOLVED` (`:29-37`) stays the propagation set.

**Wrapper-not-widen pattern** (`with_sensitive_confirm` `:71-103`) - model the `force_ids` wrapper on this and on `execute_screen._with_repair` (below); move `_with_repair` into `session.py` as `_with_force(install, force_ids)` since `execute_plan` is its only caller.

**Delete in the same wave:** `Summary` (`:106-134`), `fold_run` (`:137-160`), `run_installs` (`:168`), `summarize` (`:238`).

---

### `installer/update.py` (`update_refusal`)

**Analog:** `_perform` early returns (`update.py:247-298`). Extract each return's `detail` into `update_refusal(tool, ownership, platform) -> str | None`; `_perform` calls it first and wraps in `UpdateOutcome(status=...)`. The status must stay distinguishable (`unknown-owner` for the first branch, `unsupported` otherwise) - return a `(status, detail)` pair or two predicates; do not lose that.
```python
    if ownership.owner == "unknown" or ownership.confidence not in MUTATION_GRADE:
        return UpdateOutcome(..., status="unknown-owner", detail=ownership.unknown_reason or _FALLBACK_UNKNOWN)
    if method is not None and method.kind == "sdkman": ... "unsupported", _SDKMAN_DETAIL
    if ownership.owner in UNMANAGEABLE_OWNERS:
        detail = _OS_PACKAGE_DETAIL... if OS_PACKAGE_OWNER else _NATIVE_OWNER_DETAIL...
    if ownership.owner == "volta": ...
    # plus the pnpm-with-no-node-method (host_setup) branch at ~:313
```
**PLAN-08 edit** (`update.py:305-309`): drop only the clause, keep `declared`/`real`:
```python
f"{real} owns this copy; the catalog installs {target.tool.id} via "
f"{declared} — moving it there is not available yet, so it was "
f"updated through {real}"
```

---

### `installer/render.py` (`render_plan`, `render_run_summary`)

**Analog:** `render.py:34-87`. Keep the `(…, console: Console) -> None` signature shape and `sanitize_log_line` import (`:28`). Do NOT copy the `[cyan]…[/]` markup interpolation from `render_dependency_notice` (`:40-46`) - reasons are probe-derived; build `rich.text.Text` objects (`Text` is already imported, `:9`) and print with `markup=False`.

Shape to replace (the hard-coded words that move to `WORDS`, `:66-87`):
```python
def render_summary(summary: Summary, console: Console) -> None:
    console.print(
        f"Installed: {len(summary.installed)}  "
        f"Already: {len(summary.already)}  " ...
```
Delete `render_dependency_notice`, `render_audit`, `render_summary`, and the `installer.audit`/`installer.session.Summary` imports (`:12`, `:29`). Keep `render_failure_details`/`render_skipped`/`render_handoff`/`render_verification` (they take `list[InstallOutcome]`; feed them `[o.install for o in outcomes if o.install]`). Row anatomy, indent (2 cells after the mark), `idw` cap 26, folding with hanging indent: 20-UI-SPEC "Row anatomy" and "Words".

---

### `installer/execute_screen.py` (Textual ModalScreen, event-driven)

**Analog:** itself.

**Worker decorator** (`:617`) - reuse for the wait worker with `group="execute-wait"`:
```python
    @work(thread=True, exclusive=True, group="install-execute", exit_on_error=False)
    def _execute_worker(self) -> None:
```
**Worker body to collapse into one `execute_plan` call** (`:627-740`): keep the `emit`/`StreamingRunner(emit, unbuffer=True)`, `on_outcome` -> `InstallToolFinished`, `on_mismatch`/`on_confirm = None if self._inputs.unattended else ...`, `run_live(...)`, PATH wiring and verify through `run_live`, and the `try/except Exception/finally: self.post_message(InstallRunFinished(...))` skeleton. Replace the 12 parallel collections and `_run_updates`/`_reapply` loop with `outcomes: list[RowOutcome]` + one `run_error` (L-20-08). Gate `wire_path`/`verify` on `ran_anything(outcomes)`.
```python
            on_mismatch = None if self._inputs.unattended else self._ask_mismatch
            on_confirm = None if self._inputs.unattended else self._ask_sensitive_action
            result, message = run_live(lambda: run_installs(... _with_repair(self._inputs.install, self._repair_ids) ...))
            ...
                path_result, path_fail = run_live(self._inputs.wire_path)
        except Exception as exc:  # noqa: BLE001 -- the run must report, not die
            error = f"{error}; run stopped: {exc}" if error else f"run stopped: {exc}"
        finally:
            self.post_message(InstallRunFinished(...))
```
(The existing `# noqa: BLE001` is pre-existing; do not add new suppressions.)

**Capture at a width** (`:1159-1166`) - pass the widget width instead of 80 (Pitfall 13):
```python
    def _render_captured(self, render: Callable[[Console], None]) -> str:
        buffer = io.StringIO()
        render(Console(file=buffer, width=80, no_color=True))
        return sanitize_log_line(buffer.getvalue())
```
**Class signature to change:** `class ExecuteScreen(ModalScreen[None])` (`:420`) -> `ModalScreen[list[RowOutcome] | None]`; keep `ExecuteScreen(ids, inputs)` constructor. `ExecuteInputs` (`:401`) makes `version_refresh` required (L-20-09). `InstallRunFinished` (`:353`) shrinks to `(outcomes, run_error, path_text, verify_text)`.

**Imports to drop** (`:29-58`): `installer.audit.audit`, `reapply_post_install`, `render_audit`, `render_dependency_notice`, `render_summary`, `Summary`, `fold_run`, `run_installs`, `summarize`, `resolve_dependencies` (now inside `build_plan`). Update the module docstring (`:1-7`) which names `audit`, `run_installs`.

**Delete:** `_with_repair` (moves to session), `_classify_selection` (`:537-574`), `_update_targets` (`:576-589`), `_run_updates` (`:742-804`), `_preflight_prompt` (`:1110-1127`), `_refresh_progress` lists (`:1129-1157`).

**Stale-token fail-closed pattern** for the wait (`esc` bumps token): copy the epoch compare idea from `VersionRefreshService.refresh` (`version_status.py:1499-1531`) - capture the token when the worker starts, compare in the `StateSettled` handler, ignore when stale:
```python
        key = frozenset(tool.id for tool in tools)
        with self._lock:
            flight = self._inflight.get(key)
            joining = flight is not None and flight[0] == self._epoch
```
The wait must call `refresh(self._inputs.catalog)` with the WHOLE catalog so this key matches the catalog pass (L-20-03), inside one `_await_state` helper.

---

### `installer/wizard_app.py` (app, event-driven)

**Analog:** `_install_closed` (`wizard_app.py:2898-2925`):
```python
        self.push_screen(ExecuteScreen(message.result, self._execute), self._install_closed)

    def _install_closed(self, _result: None) -> None:
        self._staged.clear()
        ...
        if self._install_state_changed:
            self._install_state_changed = False
            sync_warning = terminal_sync_warning(self._terminal_sync)
```
Change to: `result: list[RowOutcome] | None`; `None` -> no change; else `self._staged.intersection_update(retained(result))` (in place: the set is shared with the tier browsers, Pitfall 8), and the sync gate becomes `ran_anything(result)`. Keep `terminal_sync_warning` (not `run_live`, WR-03 comment).
**Session fold:** `on_tool_updated` (`:3023-3045`) and `_merge_summary` (`:3047-3078`) become a `dict[str, RowOutcome]` keyed by tool id, latest wins (replicates cancel-then-retry), and a failed `u` stores `RowOutcome(UPDATE row, "failed")`. Delete `_install_state_changed` (`:2566`, `:2923`, `:3020`) and `install_summary`.

---

### `installer/app.py` (`run_wizard`, headless)

**Analog:** itself (`app.py:130-197`). Keep the signature style (injected `runner`, `resolve_tag`, `install`, `on_mismatch`) and the `confirm_sensitive` closure + `with_sensitive_confirm(None if options.yes else confirm_sensitive, install)`; keep the trailing `render_failure_details`/`render_skipped`/`render_handoff`/`render_post_install_handoff`/`render_postinstall_warnings`/`render_verification` calls.
Replace `resolve_dependencies` + `render_dependency_notice` + `audit` + `render_audit` + `run_installs` + `summarize` + `render_summary` with: `refresh.refresh(tools)` (sync) -> `build_plan(..., reinstall=frozenset())` -> `render_plan` -> `prompter.confirm` unless `options.yes` -> `execute_plan` -> `render_run_summary`. New params `refresh`, `updates` (remove `installed=` default `is_installed`). Return `list[RowOutcome] | None` (None = declined, as today). WAIT rows after the sync pass are a failure, never executed. `_choose_tools` (`:100-128`) keeps only `--all`/`--categories`.

---

### `setup.py` (wiring)

**Analogs:** `_build_app` (`:764`) service construction - `version_refresh = ...`, `updates = UpdateService(platform=..., live_platform=lambda: version_refresh.platform, runner=run_captured, ..., terminal_follow_up=_sync_omz_terminals)` (`:1121-1140`). Extract into `_build_services(tools, platform)` used by both `_build_app` and headless main.
Exit rule (`:1318-1327`) - keep the function, change what it reads:
```python
def _session_exit_code(app: UnifiedApp) -> int:
    if app.run_in_flight:
        return 1
    summary = app.install_summary
    if summary is not None and summary.has_failure:
        return 1
    return 0
```
-> `exit_code(app.outcomes) or bool(app.run_error)`. Headless (`:1559`) `if summary.has_failure:` -> same `exit_code(...)`; keep `render_troubleshooting(console)` before `return 1`. Four other routes call `_session_exit_code` (`:1339,1377,1403,1495`) - do not fork it.

---

### `installer/catalog_tui.py`, `installer/version_status.py` (copy edits)

`catalog_tui.py:819-823` - drop `", and moving it there is not available yet"`, keep `declared`/`real`:
```python
                    line += (
                        f" — {real} owns this copy; the catalog installs it via {declared}, "
                        "and moving it there is not available yet"
                    )
```
`version_status.py:605-606` - reword `UNPROVEN_NOTE` per L-20-06 and update its comment; pinned by `tests/test_version_status.py:4212` (`_UNPROVEN`). `selectable` (`catalog_tui.py:375`) is already done by Phase 19 - do not redo.

---

### `scripts/container-e2e-verify.sh`

**Analog:** itself `:242-255` - `SUMMARY_RE` + `parse_summary_line` sed extraction into `PARSE_*` globals. Rewrite both regex and sed lines for the new `N installed, N updated, ... N failed` words (from `WORDS`), same wave as `render_run_summary`. Check `tests/test_shell_scripts_path.py` / `tests/test_container_e2e_receipts.py` references.

---

### `tests/test_plan.py` (NEW) and `tests/state_doubles.py`

**Fixture analog:** `pass_state` (`state_doubles.py:200-232`) builds a `ToolState` the way the pass does (`present`, `ownership`, `broken`, `misconfigured`, `unconfigured`). Build `plan_state(...)` on top of it, not beside it. `FrozenStateService.publish` (`:141-144`) stamps generation at the current epoch - use it to feed `state_of`. `frozen_service(home)` (`:163`) is the default for `ExecuteInputs.version_refresh` in the `_inputs(...)` helper of `tests/test_execute_screen.py`.
```python
class FrozenStateService(VersionRefreshService):
    def publish(self, states: Iterable[ToolState]) -> None:
        with self._lock:
            stamped = {state.tool_id: replace(state, generation=self._epoch) for state in states}
            self._states = {**self._states, **stamped}

    def refresh(self, tools: Sequence[Tool]) -> None:
        del tools
        self.publish(list(self._states.values()))
```
`HeldRefreshService`: subclass `FrozenStateService`, `refresh` blocks on a `threading.Event` and counts calls (PLAN-07 asserts exactly one pass).
**Test-module analog:** `tests/test_session.py:1-40` - local `_tool(tool_id, priority, *, requires=())` builder, direct imports from `installer.session`. Purity: assert with conftest `GuardedPopen` that `build_plan` spawns nothing.

### `tests/test_docs.py`

Copy `_PHASE_19_REQUIRED` tuple + `test_architecture_records_phase_19_mechanisms` (`:188-221`) as `_PHASE_20_REQUIRED` (phrases such as `build_plan`, `execute_plan`, `RowOutcome`, `WORDS`, `retained`). Update `_PHASE_13_REQUIRED`/`_PHASE_14_REQUIRED` in the same commit as the doc rewrite (Pitfall 14).

## Shared Patterns

### Width budget (78 cells)
**Source:** `tests/test_catalog_tui.py:1741-1746`
**Apply to:** `render_plan`, `render_run_summary`, review head, pilot tests at `size=(80, 20)`
```python
    for line in lines:
        plain = re.sub(r"\[[^\]]*\]", "", line)
        assert len(plain) <= 78, (len(plain), plain)
```

### Untrusted text
**Source:** `execute_screen._render_captured` (`:1159-1166`) + `installer/sanitize.sanitize_log_line`
**Apply to:** every reason / `ConfigStep.text` / error in `render_plan` and the progress `OptionList`: `Text(...)`, never markup interpolation.

### Live calls from screens
**Source:** `ui_common.run_live` as used in `_execute_worker` (`result, message = run_live(...)`)
**Apply to:** PATH wiring, verify, and any screen-side core call (architecture rule 3).

### Wrap, don't widen protocols
**Source:** `session.with_sensitive_confirm` (`:71-103`), `execute_screen._with_repair` (`:240-277`)
**Apply to:** `force_ids` (REPAIR/REINSTALL), never add params to `Install` (29 fakes).

### Deps-first ordering only via resolver
**Source:** `deps.resolve_dependencies`; `run_installs` docstring "must not start sorting"
**Apply to:** `build_plan` and `execute_plan` - no second sort.

### Zero sudo
**Source:** `update._perform` `UNMANAGEABLE_OWNERS` branch (`:263-283`)
**Apply to:** BROKEN/OUTDATED rows owned by native/os-package -> BLOCKED in `build_plan` via `update_refusal`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| ConfigStep dispatch (`kind` -> executor, cwd wrapper `sh -c 'cd -- "$1" && shift && exec "$@"'`) inside `session.execute_plan` | service | batch | No existing code executes `ConfigStep`s (19 only builds them, `model.py:324-335`). Use RESEARCH Pattern 6 + "cwd wrapper"; `pnpm_group_install` -> `executors.execute(first node method)` (L-19-28); `terminal_sync` -> injected `_sync_omz_terminals` (`setup.py:942`). |

## Metadata

**Analog search scope:** `installer/` (session, deps, update, render, execute_screen, wizard_app, app, catalog_tui, version_status, model), `setup.py`, `scripts/container-e2e-verify.sh`, `tests/` (state_doubles, test_session, test_catalog_tui, test_docs)
**Files scanned:** 15
**Pattern extraction date:** 2026-10-17
