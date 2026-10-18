# Phase 21: One screen family - Pattern Map

**Mapped:** 2026-10-18
**Files analyzed:** 17 (modified) + 2 (new tests)
**Analogs found:** 19 / 19 (all in-file or same-repo; this is a refactor, so most analogs are the code being replaced or its smaller sibling)

Line numbers are current `main` (post Phase 20). Use symbol names in plans; lines drift. All analog paths below were checked as git-tracked (`installer/`, `tests/`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/ui_common.py` (`AppScreen` defaults) | component base | event-driven | `AppScreen.enter_view` hook (`ui_common.py:338`) + `CatalogScreen.clear_transient` (`catalog_tui.py:702`) | exact |
| `installer/wizard_app.py` `UnifiedApp.show_view` / root / `_navigable` | controller (nav) | request-response | current `show_view` (`:2759`) | exact (rewrite) |
| `installer/wizard_app.py` `request_refresh` + `_refresh_worker` + publish handlers | service (worker owner) | event-driven / batch | `_apply_daemon_default_worker` + `on_daemon_default_applied` (`:2696-2740`) | exact |
| `installer/wizard_app.py` mutation lock (`mutation_in_flight`) | utility/guard | request-response | `daemon_default_in_flight` / `toggle_in_flight` checks (`:1469, 2046-2053, 2167-2174`) | exact |
| `installer/wizard_app.py` removal worker + `RemovalFinished` | service (worker) | event-driven | `_apply_daemon_default_worker` / `DaemonDefaultApplied` (`:2450`, `:2696`) | exact |
| `installer/wizard_app.py` `action_abort` / `action_hard_abort` | controller | request-response | current sync versions (`:3061, 3068`) | role-match |
| `installer/wizard_app.py` `UninstallScreen` projection | component | CRUD (read projection) | `CatalogScreen` tier rows + `health_cell` (`catalog_tui.py:128, 258`) | role-match |
| `installer/wizard_app.py` `PoliciesScreen.enter_view` / live cells | component | request-response | `omz_plugins_policy` live reads (`policy.py:734-799`), `refresh_daemon_state` (`wizard_app.py:2008`) | role-match |
| `installer/wizard_app.py` `DoctorScreen` lifecycle | component | event-driven | `DoctorScreen.enter_view` (`:422-444`) | exact (rewrite) |
| `installer/catalog_tui.py` (`state_refreshed`, delete workers/`OwnershipRefreshed`) | component | event-driven | own `_refresh_versions_worker` (`:402-433`) being replaced | exact |
| `installer/tool_browser.py` (`reload`, `selected_ids`) | component | transform | own `reload` (`:236-250`) | exact |
| `installer/uninstall.py` (`uninstall_group`, `managed_hint`; delete `classify_tools`/`ToolRow`) | utility (pure) | transform | `classify_tools` (`:359`), `reverse_dependencies` (`:341`) | role-match |
| `installer/app.py::perform_uninstall` (per-tool results) | service | CRUD / batch | itself (`:650-722`) + `remove_proven` loop | exact |
| `installer/session.py` (`Disposition.REMOVE`, `"remove_failed"`, WORDS/RESULT_WORDS) | model | transform | Phase 20 `WORDS` rows (`:134-143`) | exact |
| `installer/version_status.py` (`mark_pending`, evidence store, shim fact) | service | event-driven | `invalidate` (`:1121`) + single publication swap (`:1760`) | exact |
| `installer/policy.py` (live installed predicate in tweak/daemon factories) | factory | request-response | `omz_plugins_policy` (`:734-799`) | exact |
| `installer/execute_screen.py` (`_wait_worker` body to publication waiter) | component | event-driven | own `_await_state`/`_wait_worker` (`:534-575`) | exact |
| `setup.py` (drop row/owner closures, bind live predicates) | config (wiring) | n/a | existing closures being deleted (`:807-868`) | exact |
| `tests/screen_family.py` (NEW doubles) + `tests/test_screen_family.py` (NEW) | test | event-driven | `tests/state_doubles.py` `FrozenStateService`/`HeldRefreshService` (`:244-290`) | role-match |

## Pattern Assignments

### `installer/ui_common.py` - `AppScreen` defaults (component base, event-driven)

**Analog:** `AppScreen.enter_view` (`ui_common.py:338-348`) and `CatalogScreen.clear_transient` (`catalog_tui.py:702-714`).

Current hook to replace (docstring-only no-op):
```python
def enter_view(self) -> None:
    """Re-derive anything this view must not read from a stale snapshot.
    Called by UnifiedApp.show_view ... Default: nothing to refresh."""
```
Target shape (D-03):
```python
def enter_view(self) -> None:
    self.state_refreshed()
def state_refreshed(self) -> None:
    """Re-render from published state. Default: nothing."""
def clear_transient(self) -> None:
    self.status.clear()
```
`CatalogScreen.clear_transient` stays as the override (clears `_pending_recommends`, `recommends_line`, then `status`). Keep the rationale docstring (why `show_view` and not `ScreenSuspend`).

### `installer/wizard_app.py` - `show_view` and root (controller, request-response)

**Analog:** current `show_view` (`:2759-2790`) and `_navigable` (`:2798`).

Structure to keep: early return on `name == self.current_view`, await each stack mutation, flush warnings last. Reorder to clear -> pop -> `await push_screen` -> `enter_view` (research Pattern 1):
```python
if name == self.current_view:
    return
leaving = self._views.get(self.current_view)   # None while the root is on top
if leaving is not None:
    leaving.clear_transient()
    await self.pop_screen()
target = self._views[name]
await self.push_screen(target)
self.current_view = name
target.enter_view()
self._flush_pending_warnings(target)
```
Delete: `get_default_screen` (`:2753`), the `BASE_VIEW` branch, `self._catalogs.get(...)` leaving lookup. `_navigable` becomes `self.screen in self._views.values()`. Pitfalls: P1 (init `current_view` to `""`, it is `BASE_VIEW` at `:2630`), P8 (`_flush_pending_warnings` at `:2792` does `status.set(" · ".join(pending), "warn")` and overwrites an entry-written status; merge or flush before `enter_view`), P22 (burst test `tests/test_wizard_app.py:3278-3292`).

### `installer/wizard_app.py` - `request_refresh` + one worker (service, event-driven)

**Analog:** `_apply_daemon_default_worker` (`:2696-2733`) and `on_daemon_default_applied` (`:2736`).

Worker idiom to copy exactly (thread worker, `exit_on_error=False`, `finally`-posted message so the in-flight flag can never stick):
```python
@work(thread=True, exclusive=True, group="daemon-default", exit_on_error=False)
def _apply_daemon_default_worker(self) -> None:
    applied = False
    live: bool | None = None
    try:
        ...
    finally:
        if self._daemon_default_policy_id is not None:
            self.post_message(DaemonDefaultApplied(self._daemon_default_policy_id, applied, live))

def on_daemon_default_applied(self, message: DaemonDefaultApplied) -> None:
    # Cleared FIRST, unconditionally ...
    self.daemon_default_in_flight = False
```
Apply as: `_refresh_worker` (`group="full-catalog-refresh"`) runs `run_live(lambda: service.refresh(...))` then `service.refresh_skills(...)`, posting `RefreshPublished` after each (keeps two paint points, see `catalog_tui.py:402-433`) and `RefreshFinished` in `finally`. Flags `_refresh_running` / `_refresh_pending` are touched only on the event loop; the `RefreshFinished` handler restarts exactly one more pass (research Pattern 2). Publish target: generalise `_visible_app_screen` (`:2965-2967`):
```python
def _visible_app_screen(self) -> AppScreen | None:
    screen = self.screen
    return screen if isinstance(screen, AppScreen) else None
```
to the topmost `AppScreen` in `screen_stack` (P6: `self.screen` is a modal while `ConfirmUninstall` is open). `request_refresh` must no-op when `_version_refresh is None` (P13) or `_quitting` (P14).

### `installer/wizard_app.py` - mutation lock (guard, request-response)

**Analog:** check-at-open-and-at-mutation-point sites: `UninstallScreen._apply_removal` (`:1469`, `getattr(self.app, "daemon_default_in_flight", False)`), `PoliciesScreen` toggle (`:2046-2053`, `:2167-2174`, `toggle_in_flight`), `run_in_flight` (`:2534`). Fold into `UnifiedApp.begin_mutation(kind) -> bool` / `end_mutation` / `refuse_if_mutating(screen)`; keep the `_TOGGLE_IN_FLIGHT_MESSAGE` / `_DAEMON_DEFAULT_IN_FLIGHT_MESSAGE` constants (`:2444-2447`) for their own cases. Sites to wire (research Pattern 7): `CatalogScreen.action_update_tool` (`catalog_tui.py:777`), `on_catalog_screen_decided` (`:2884`), Doctor `action_apply`/`action_reinstall_globals`, Policies `action_toggle_policy`/`_time_picked`/`_link_mode_picked`, `_first_link_mode_picked`, `_apply_removal`. Single refusal string: `A removal is running; wait for it to finish. Navigation still works.` Existing tests touching the old flags: `toggle_in_flight` (8 refs, `tests/test_policies_e2e.py`), `daemon_default_in_flight` (18 refs).

### `installer/wizard_app.py` - removal worker (service, event-driven)

**Analog:** same daemon worker + message idiom (above). `@work(thread=True, exclusive=True, group="uninstall-removal", exit_on_error=False)`; `finally:` posts `RemovalFinished`; the handler clears the lock FIRST, calls `service.invalidate(reason=...)` (P3: removal does not invalidate today), renders the summary, then `request_refresh()` (P4: after, never before). Before starting: `service.mark_pending(ids)` and publish so visible rows show `…`.

`RemovalFinished` message class: copy `DaemonDefaultApplied` (`:2450-2465`) docstring shape (posted unconditionally from the worker, widgets touched only on the app thread).

### `installer/wizard_app.py` - quit wait (controller, request-response)

**Analog:** `action_abort` / `action_hard_abort` (`:3061-3071`, sync today):
```python
def action_abort(self) -> None:
    if not self._navigable():
        return
    self.exit(None)
def action_hard_abort(self) -> None:
    self.exit(None)
```
Make both `async` and route through `_exit_after_removal` (research Pattern 7): set `_quitting = True`, status `Waiting for the removal to finish…`, `with contextlib.suppress(WorkerFailed, WorkerCancelled): await self.workers.wait_for_complete([worker])`, then `self.exit(None)`. Keep the `_navigable()` guard on soft quit only.

### `installer/wizard_app.py` - delete `on_ownership_refreshed` (`:3037-3059`)

Replaced by direct `screen.state_refreshed()` on publish. Delete in the same wave as `OwnershipRefreshed` (`catalog_tui.py:152`) and the per-tier workers (D-16).

### `installer/wizard_app.py` - `UninstallScreen` (component, read projection)

**Analog:** the tier row rendering: `health_cell` (`catalog_tui.py:128`) and `_HEALTH_DETAIL` (`catalog_tui.py:258-266`). Existing pieces to keep: `BrowserAdapter.detail_is_markup=False` (`:1155`), `_UninstallEntry` (`:864`), `ConfirmUninstall`, `_applied_summary` (`:1552-1597`). Delete `_resync` (`:1252`), `_pending_status`/`_set_status` (`:943-952, 1165-1186`), `ownership_refreshed`, `uninstall-ownership-refresh` worker (`:1531`). Build rows in `state_refreshed` from `uninstall_group(state_of(id))`; call `ToolBrowser.reload` so cursor is restored by row key (`tool_browser.py:193-221`). Standing status `Nothing to uninstall.` only when all states are known (P7). Titles: `removable here`, `managed elsewhere`, `nothing to do` (UI-SPEC A1).

### `installer/wizard_app.py` - `PoliciesScreen` (component)

**Analog:** `omz_plugins_policy` live-read shape and `refresh_daemon_state` worker (`:2008`; `_probe_competing_worker` shape at `:1701-1711`).

Add `enter_view`/`state_refreshed`: per policy `update_cell(..., update_width=True)` (P17; default is `False` and `! [drift]` is wider). Live read `policy.is_active()` if present else `policy.active`. DRIFT: `policy.owned is not None and policy.owned() and not active`. For policies with `state_cache`, use `peek()` on the loop and a thread worker for `live_state` (P16: `TimerStateCache.read()` can block). `_refresh_link_mode_line` (`:1718-1723`) re-read in the same pass. Reuse `uninstall.policy_owned` (`:593`) only as a fallback predicate chain.

### `installer/wizard_app.py` - `DoctorScreen` (component)

**Analog:** its own `enter_view` (`:422-444`, guarded by `is_mounted`) and the two workers `_audit_globals_worker` / `_reinstall_globals_worker`. Move body render and worker starts from `on_mount` to `enter_view`; `state_refreshed` re-renders; delete `Binding("a", "apply", "apply", show=False)` (`:303`); flip `test_doctor_hidden_a_alias_applies_fix` (`tests/test_wizard_app.py:895`). Render pnpm findings from `state_of(tool.id).reasons` (tools via `pnpm_globals.node_globals(tools)`, `pnpm_globals.py:181`), not `node_globals_guidance(self._globals_report)` (sentences live at `guidance.py:307-330`; keep `NodeGlobalsReport.managed` for the reinstall preview). Audit end calls `request_refresh()` only if evidence changed (P19). `_first_link_mode_picked` success branch (`:2837`) calls `target.enter_view()` when target is Doctor.

### `installer/tool_browser.py` - `reload` and `selected_ids` (component, transform)

**Analog (itself):**
```python
stale = {key for key in self._by_id if key is not None}
self._adapter = adapter
self._by_id = {adapter.item_id(item): item for item in adapter.items}
self.selected -= stale - {key for key in self._by_id if key is not None}
```
and
```python
def selected_ids(self) -> list[str]:
    return [self._adapter.item_id(item) for item in self._adapter.items
            if self._adapter.item_id(item) in self.selected]
```
Add: subtract ids of items with `not selectable(item)` from `self.selected` (keep the in-place `-=`: the three tier browsers share one set), and add `and selectable(item)` to `selected_ids`. Catalog `selectable` is `not self._is_unavailable(tool)` (`catalog_tui.py:365`), safe for `…` rows.

### `installer/session.py` - removal vocabulary (model, transform)

**Analog:** Phase 20 tables:
```python
Disposition.INSTALL: Words("will install", "installed", "green"),
Disposition.BLOCKED: Words("blocked", "blocked", "red", done_style="red"),
RESULT_WORDS: dict[Result, tuple[str, str]] = { "failed": ("failed", "red"), ... }
```
Add `Disposition.REMOVE = "remove"` with `Words("will remove", "removed", "red", done_style="green")`, result `"remove_failed"` -> `("remove failed", "red")`, add to `_FAILURE`, `summary_counts` result tuple and `render._FAILURE_RESULTS`. Keep REMOVE out of `RUNNABLE` (`session.py:113-121`, P11). Parametrised tests over `list(Disposition)` need REMOVE fixtures: `tests/test_render.py:671`, `tests/test_plan.py:558-568`. Make `_first_line` (`session.py:336`) public for the error line.

### `installer/app.py::perform_uninstall` (service, batch)

**Analog (itself, `:681`):** `_removed, refused = remove_proven(list(decision.tools), list(decision.paths), bin_dir)`. Change to a per-tool loop: `remove_proven([tool], tool_paths, bin_dir)` inside `try/except OSError`, returning per-tool removed/failed with first error line, alongside the existing `SweepResult` (it currently returns `dataclasses.replace(swept, warnings=swept.warnings + refused)` or `SweepResult(warnings=refused)`). No new deletion code.

### `installer/version_status.py` - `mark_pending`, evidence store (service)

**Analog:** `invalidate` (`:1121`) for lock + epoch idiom, and the single publication point:
```python
fresh = {tool_id: state for tool_id, state in states.items()
         if (current := self._states.get(tool_id)) is None or current.seq < seq}
...
self._states = {**self._states, **fresh}
```
`mark_pending`: under `self._lock`, add to `_pending` and drop ids from `_states`; the commit filter must skip pending ids (P9); `invalidate()` clears `_pending`. `state_of` (`:1010-1018`) already returns `None` for an absent key. Evidence: `record_evidence(tool_id, broken=..., notes=...)` under `_lock`, read where `_pass` builds `Evidence` (`facts = config.get(tool.id, _NO_FACTS)`, `:1703-1721`); reuse `_ConfigFacts.plus` (`:629-645`), `BROKEN_SHIM_REASON` (`:608`). Missing-shim note near `_pnpm_group_facts` (`:663`). Test double: `tests/state_doubles.py::FrozenStateService` needs `mark_pending`/evidence support (it overrides `refresh` to re-publish).

### `installer/policy.py` - live installed predicate (factory)

**Analog:** `omz_plugins_policy` (`:734-799`): `present: bool | Callable[[], bool]` and
```python
missing_requires=read_missing_requires,
missing_requires_now=read_missing_requires,
```
Apply to `tweak_policy` (`:502`, snapshot at `:586-588`) and `daemon_policy` (`:831`, snapshot at `:1004-1006`): accept `Mapping[str, bool] | Callable[[str], bool]`, set `missing_requires_now`. `linux_daemon_policy` does `del installed_tools` (`:1095`); leave. `omz_plugins_policy` needs `is_active=lambda: plugins_owned(state_path)` or it stays stale. 28 test refs pass a plain dict; the union keeps them working.

### `installer/execute_screen.py` (component, event-driven)

**Analog:** its own `_await_state` / `_wait_worker` / `StateSettled` (`:534-575`). Replace only the worker body with "register for the next final publication"; keep the token contract and `StateSettled`. `tests/test_docs.py::_PHASE_20_REQUIRED` pins `"_await_state"` and `"single flight"`: update with `.claude/architecture.md`.

### `installer/uninstall.py` (utility, transform)

**Analog:** `classify_tools` (`:359`), `reverse_dependencies` (`:341`), `UninstallState` (`enums.py:71-77`), `removal_hint`/`removal_label` (`ownership.py:1602, 1644`). New pure `uninstall_group(state)` plus `managed_hint(tool, state)` (research Pattern 4 and Code Examples). Keep SAFE-03 `remove it yourself: <paths>` suffix (from `state.removable.yourself`) and the `required by` suffix. Delete `classify_tools`, `ToolRow`, `OwnerHint`/`OwnerLabelHint`, `ownership._own_script_install` (callers `ownership.py:1620, 1666`).

### `setup.py` (wiring)

Delete the row/owner closures (`setup.py:807-868`); bind live predicates: `lambda tool_id: (s := version_refresh.state_of(tool_id)) is not None and s.present`. Decision logic stays in `installer/`.

### Tests (NEW) `tests/screen_family.py`, `tests/test_screen_family.py`

**Analog:** `tests/state_doubles.py` (`FrozenStateService.publish`, `HeldRefreshService`, `seeded_service`) and `tests/test_wizard_app.py::_uninstall_inputs` (`:173`), `_app`, `_settle`. Add: `HeldRemover` (threading.Event with bounded `wait(timeout=10)`), a pass-counting `FrozenStateService` subclass wrapping `refresh`, call-order recorder (`["clear","pop","push","enter"]`), matrix harness, grep guard test over `installer/` for `OwnershipRefreshed`, `_pending_status`, `_own_script_install`, `classify_tools`, `uninstall-ownership-refresh` including comments and docstrings (P21). Rewrite `_uninstall_inputs` first (127 `UninstallInputs` constructions, 84 in `test_wizard_app.py`). `app.query_one` no longer reaches pushed tiers (P12): check `tests/test_catalog_tui.py` (`:294,:343,:459,:1793,:1915`), `tests/test_ui_common.py`, `tests/test_policies_e2e.py`; stack-depth assertion at `tests/test_wizard_app.py:3286-3290` becomes 2. Doctor tests mounting directly (`_DoctorHost`/`_ready_doctor`, 31 refs) must call `enter_view()` (P18).

## Shared Patterns

### Worker + `finally`-posted message (flags can never stick)
**Source:** `installer/wizard_app.py` `_apply_daemon_default_worker` / `DaemonDefaultApplied` / `on_daemon_default_applied` (`:2450-2740`)
**Apply to:** `_refresh_worker`, removal worker.

### Text, not markup, for dynamic strings
**Source:** `sanitize_log_line` (`installer/sanitize.py:13`), `Text` objects, `detail_is_markup=False` (`wizard_app.py:1155`)
**Apply to:** Uninstall detail/removes cells, Doctor reasons, removal error lines.

### Single apply workflow
**Source:** `ui_common.run_live` (`ui_common.py:42`); `.claude/architecture.md` rule 3 (no screen-local `try/except OSError`).

### One health writer
**Source:** `health_cell` (`catalog_tui.py:128`); `state_of` returning `None` renders `…`. No second in-flight input (D-09).

### Docs doctrine
**Source:** `.claude/architecture.md` + `tests/test_docs.py` `_PHASE_20_REQUIRED` (`:187-203`). Add `_PHASE_21_REQUIRED` in the same wave as the prose change (P21).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| Quit-wait on a thread worker | controller | request-response | No existing async quit path; use Textual `workers.wait_for_complete` (`textual/worker_manager.py:172`) wrapped in `suppress(WorkerFailed, WorkerCancelled)` per RESEARCH G6 |
| Policies cache-backed live read | component | request-response | Nearest is `_probe_competing_worker` (`wizard_app.py:1701`); `state_cache.peek()` + worker is new |
| Evidence store | service | event-driven | No session evidence exists; build from `Evidence.broken/notes` and `_ConfigFacts.plus` |

## Corrections to carry into plans (from RESEARCH)

- `RemovalPlan` has no `level`/`hint` (G1): derive the group from `ToolState.health`, `.removable.removable`, `.receipt`, `.ownership`.
- `tweak_policy`/`daemon_policy` bake a snapshot (G3); `perform_uninstall` returns no per-tool outcome (G5); `Worker.wait()` raises on failure (G6).

## Metadata

**Analog search scope:** `installer/`, `tests/`, `setup.py`, `.claude/architecture.md` (via RESEARCH reads plus targeted sed of `ui_common.py`, `wizard_app.py`, `tool_browser.py`, `version_status.py`, `session.py`, `app.py`, `catalog_tui.py`, `tests/state_doubles.py`, `tests/test_wizard_app.py`)
**Files scanned:** ~12 read in part; analog claims for `policy.py`, `uninstall.py`, `execute_screen.py`, `ownership.py`, `setup.py` come from RESEARCH.md `[VERIFIED]` lines and were not re-read here
**Pattern extraction date:** 2026-10-18
