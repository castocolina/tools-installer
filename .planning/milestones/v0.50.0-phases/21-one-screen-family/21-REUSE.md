# Phase 21: Ponytail reuse pass (plans 21-01 .. 21-21)

Read-only audit, ultra level. Scope: every new function, module, class, dataclass, enum, Protocol, test helper or constant in 21-01..21-21.
Locked decisions were not re-argued: 21-CONTEXT D-01..D-16, 21-SPEC, the approved 21-UI-SPEC (the one refusal template, the `MutationHolder` noun table, and `MutationLock` as the one lock owner inherited by `UnifiedApp`, UI-SPEC line 132), and the D-07 adaptation (Uninstall groups derived from `ToolState` by one pure function).
Line numbers are from the tree at `c819e62`. None of the Phase 21 plans had landed when this was written.

Each section below is an Orchestrator note: the executor applies it inside the named plan without replanning.

## 21-04 -- a dead parameter widened instead of deleted

### Finding 04-1 -- Important -- Task 2 (`linux_daemon_policy` predicate, `test_linux_daemon_policy_accepts_a_predicate`)
- New symbols: the widened `installed_tools: Mapping[str, bool] | Callable[[str], bool] | None` on `linux_daemon_policy`, its normalisation, and the test `test_linux_daemon_policy_accepts_a_predicate`.
- Existing helper: `installer/policy.py:1043` declares `installed_tools`, and `:1095` does `del installed_tools`. The docstring at `:1089-1093` says the parameter exists only "for signature symmetry" because `requires` is empty on Linux. A live predicate on a parameter that is never read adds nothing.
- Instruction: delete the parameter from `linux_daemon_policy` and its docstring paragraph. Do not widen it. Widen only `tweak_policy` (`policy.py:507`) and `daemon_policy` (`:838`), which read it.
  - Drop `installed_tools=` from these callers: `setup.py:599-605` (the Linux branch of `_build_daemon_policy`), `tests/test_app.py:3170`, `:3239` and `:3305`, `tests/test_policies_e2e.py:584`, `tests/test_systemd_daemon.py:115`, and the kwargs builder in `tests/test_policy_linux_daemon.py:~127-148`.
  - Drop the new test.
- New acceptance:
  - `grep -c "Callable\[\[str\], bool\]" installer/policy.py` is at least 2.
  - The `tests/test_policy_linux_daemon.py` floor stays at 29.
  - `grep -c "installed_tools" <(awk '/^def linux_daemon_policy/,/^def [a-z_]+\(/' installer/policy.py)` prints 0.

## 21-05 -- a second copy of the "tracked pnpm global off PATH" rule

### Finding 05-1 -- Important -- Task 2 (`_pnpm_missing_facts`)
- New symbol: `version_status._pnpm_missing_facts(tools, packages, which)`. It loops over `node_globals(tools)`, keeps the entries whose `npm_pkg` is in `packages`, and keeps those whose `which(cmd)` is None.
- Existing helper: `installer/pnpm_globals.py:556-594` `audit_node_globals`. Both of its branches already compute exactly that set: `entries = ... if entry.npm_pkg in packages` and `missing = ... if which(entry.cmd) is None` (`:573-574`, `:587-588`). It also already treats an unknown package set (`None`) as "nothing known" (`:568-572`).
- Instruction: keep the function, but make its body one call to the existing rule.
  ```python
  if packages is None:
      return {}
  report = audit_node_globals(tools, which=which, managed=lambda: tuple(packages), smoke=lambda _cmd: None)
  return {tid: _ConfigFacts((PNPM_TRACKED_OFF_PATH.format(names=tid),)) for tid in report.missing}
  ```
  Notes on the call:
  - The default empty `policy` takes the `managed` branch.
  - `smoke=lambda _cmd: None` keeps the "no subprocess" guarantee.
  - `tuple(...)` adapts `inventory.pnpm_globals` (a `frozenset[str]`, `ownership.py:289`) to the `managed` signature.
  - `audit_node_globals` is already importable from the `installer.pnpm_globals` import block at `version_status.py:79`.
- The existing acceptance (`def _pnpm_missing_facts` is 1) is unchanged. Add `grep -c "audit_node_globals(" installer/version_status.py` at least 1.

## 21-06 (also touches 21-15) -- `settle` re-writes the poll loop the suite already has

### Finding 06-1 -- Important -- Task 1 (`settle`, the version-flag waits)
- New symbol: `tests/screen_family.py::settle(app, pilot)`, which polls until no worker is pending or running, then pauses once.
- Existing helpers:
  - `tests/test_catalog_tui.py:2832-2837` `_wait_until(pilot, predicate, tries=400)` is the house poll loop, with 35 call sites.
  - `tests/test_wizard_app.py:1676` `_wait_for` (3 calls) is a byte-for-byte second copy of it.
  - The worker-wait idiom `asyncio.gather(*(worker.wait() for worker in app.workers))` is at `tests/test_catalog_tui.py:1854`. Its comment records why `wait_for_complete` is avoided under pyright strict.
- Instruction:
  1. Move `_wait_until` unchanged into `tests/screen_family.py` as the public `wait_until`. Write `settle` as `await wait_until(pilot, lambda: not any(w.state in (WorkerState.PENDING, WorkerState.RUNNING) for w in app.workers)); await pilot.pause()`.
  2. In `test_catalog_tui.py`, import `wait_until` and do not rewrite it there.
  3. Replace `test_wizard_app.py::_wait_for` with an import of `wait_until`. Its trailing extra pause is covered by the call sites' own `pilot.pause()`; keep one if a test needs it.
  4. `tests/test_wizard_app.py:5463` `_settle_versions` (70 calls) polls `version_refreshing`, which this plan deletes. Delete the helper and replace its calls with `await settle(app, pilot)` (the `screen=` argument goes away). Do not rewrite its body.
- New acceptance:
  - `grep -c "async def _wait_until\|async def _wait_for\|async def _settle_versions" tests/*.py` prints 0 for every file.
  - `grep -c "async def wait_until" tests/screen_family.py` is 1.

### Finding 15-1 -- Minor -- Task 2 of 21-15 (`_settle_daemon`, `_settle_toggle`, the `test_policies_e2e` wait loop)
- New symbols: the rewritten waits on `app.mutation_in_flight`. 21-15 line 174 says "the test_policies_e2e wait loop waits on the lock".
- Existing helpers: 21-06's `settle` and `wait_until` (06-1). The three loops are at `tests/test_wizard_app.py:4991` `_settle_daemon` (12 calls), `:5093` `_settle_toggle` (4 calls), and `tests/test_policies_e2e.py:45` (16 calls). Each polls a flag that 21-15 deletes.
- Instruction: delete the three helpers. Replace their calls with `await settle(app, pilot)`, because the holder's worker ending is what releases the lock. Where a test must observe the lock itself, use `await wait_until(pilot, lambda: not app.mutation_in_flight)`. Do not hand-write a fourth and fifth poll loop.

## 21-02 -- one `remove_failed` branch that the `failed` branch already is

### Finding 02-1 -- Minor -- Task 2 (`outcome_detail_text` branch for `remove_failed`)
- New symbol: a separate `remove_failed` branch in `installer/render.py::outcome_detail_text`.
- Existing helper: `render.py:150-161`, the `failed` branch. A removal outcome has `install is None` and `update is None`, so that branch already returns `sanitize_log_line(outcome.detail.splitlines()[0])`. That is the UI-SPEC "first line of the sanitized error".
- Instruction: change `if outcome.result == "failed":` to `if outcome.result in {"failed", "remove_failed"}:` and add no new branch. The `"no method succeeded"` fallback cannot be reached for a removal, because the removal worker always fills `detail` with `first_line(...)`. The truth test in the plan stays as written.

## 21-08 -- the nothing-to-do detail words are already a table

### Finding 08-1 -- Minor -- Task 1 (`uninstall_detail`, nothing-to-do branch)
- New symbols: the literals `"not installed"` (MISSING) and `"checking…"` (None) inside `version_status.uninstall_detail`.
- Existing helper: `installer/catalog_tui.py:258-266` `_HEALTH_DETAIL` already maps `Health.MISSING -> "not installed"` and `Health.CHECKING -> "checking…"`. It is the tiers' detail word, and UI-SPEC line 179 says "No new copy". `version_status` cannot import from `catalog_tui`, because `catalog_tui.py:38` imports `version_status`.
- Instruction: move the dict unchanged to `installer/version_status.py` as `HEALTH_DETAIL`, beside `HEALTH_MARKS` (`:189`). `catalog_tui` imports it (its two readers are `:112` and `:631`), and `uninstall_detail` reads `HEALTH_DETAIL[Health.MISSING]` and `HEALTH_DETAIL[Health.CHECKING]`. The UNAVAILABLE branch keeps `state.reasons[0]` as planned.
- New acceptance: `grep -c "^HEALTH_DETAIL" installer/version_status.py` is 1, and `grep -c "_HEALTH_DETAIL = " installer/catalog_tui.py` is 0.

## 21-11 -- leftovers of the row-based cell builder

### Finding 11-1 -- Minor -- Task 1 (`_VIA_*` constants)
- New/kept symbols: `installer/wizard_app.py:906-908`, which are `_VIA_USERSPACE`, `_VIA_UNATTRIBUTED` and `_VIA_NONE`, together with their CR-03 comment block (`:900-905`, `:1013-1031`).
- Existing helper: `uninstall_label` (21-08) is now the only writer of the `Installed via` cell (21-11 truth line 31). Nothing reads the three constants after `_tool_entry(tool)` replaces the row builder.
- Instruction: delete the three constants and the `installed_via` dict in the same task. Keep the CR-03 rationale as one comment line on `_REMOVES_CELL_MAX`.
- New acceptance: `grep -c "_VIA_" installer/wizard_app.py` prints 0.

### Finding 11-2 -- Minor -- Task 1 (`_REMOVES_CELL_MAX` truncation)
- New symbol: the comma-joined path cell truncated "with an ellipsis" to `_REMOVES_CELL_MAX`.
- Existing helper: Rich `Text.truncate(width, overflow="ellipsis")`. It is already the house form at `installer/tool_browser.py:90` and `installer/execute_screen.py:568` and `:582`.
- Instruction: build the cell as `Text(", ".join(paths), style=style)` and then call `.truncate(_REMOVES_CELL_MAX, overflow="ellipsis")`. Do not slice the string by hand or append `…` by hand.

## 21-21 -- two app builders with a conditional merge

### Finding 21-1 -- Minor -- Task 1 (`matrix_app`, "`_family_app` delegates to `matrix_app` when the shapes match")
- New symbols: `tests/screen_family.py::matrix_app`, `MATRIX_SOURCES` and `MATRIX_TARGETS`, plus the conditional rewrite of `_family_app`.
- Existing helper: `tests/test_screen_family.py::_family_app(**overrides)` (21-01). It already builds a `UnifiedApp` and takes `version_refresh=` (21-06 line 134). 21-01 line 82 keeps it module-local because only that file needs it. The matrix has the same single consumer: both of its tests live in `tests/test_screen_family.py`.
- Instruction:
  1. Put `MATRIX_SOURCES`, `MATRIX_TARGETS` and `matrix_app` in `tests/test_screen_family.py`.
  2. Write `matrix_app(tmp_path)` as `_family_app(version_refresh=service, uninstall=..., policies=...)` plus the seams it returns. `_family_app` stays unchanged.
  3. Delete the "delegates when the shapes match" step. The SUMMARY then reports only which helper each source reuses.
- New acceptance: the `MATRIX_SOURCES` greps (frontmatter `contains`/`pattern`, line 126) target `tests/test_screen_family.py` instead of `tests/screen_family.py`.

## No-finding plans

- 21-01: `AppScreen.enter_view`, `state_refreshed` and `clear_transient`, `show_view` as the one nav path, and the module-local `_family_app` (see 21-1 for its later reuse).
- 21-03: the reload prune and the `selectable` filter edit `ToolBrowser` in place; no new helper.
- 21-05 (outside 05-1):
  - `mark_pending`, `_pending_ids`, `record_evidence` and `_evidence` are new state that the D-03/D-13 design requires.
  - Computing `which = self._looked_through` before `config` only moves the existing line at `version_status.py:1635`.
- 21-07: `RefreshRequested` is justified by bare-screen tests that have no `UnifiedApp`; the plan keeps one handler.
- 21-08 (outside 08-1):
  - `uninstall_group`, `uninstall_label` and `uninstall_detail` reuse `removal_label`, `owner_label` and `removal_hint`.
  - `LAYOUT_PROOF_NOTE` moves the literal from `uninstall.py:403` rather than copying it.
  - The other three notes sit beside `UNPROVEN_NOTE` (`:618`).
- 21-09: `SweepResult.removed`/`remove_failed` and the per-tool loop extend `perform_uninstall` in place.
- 21-10: `await_publication` replaces the Phase 20 wait worker; `_await_state` is kept and re-pointed, not copied.
- 21-12: deletions only (`classify_tools`, `ToolRow` and the owner hints, with their tests); `reverse_dependencies` and `manager_name` are kept.
- 21-11 (outside 11-1/11-2):
  - Extending `pass_state` (`tests/state_doubles.py:367`) with `removable=` and `receipt=` is the right reuse.
  - `_removable_state`, `_managed_state`, `_absent_state` and `_unavailable_state` replace the row helpers (`test_wizard_app.py:121`, `:1083-1091`) one for one.
- 21-13:
  - The removal worker follows D-08.
  - `HeldRemover` has no existing analogue; it mirrors `HeldRefreshService` (`state_doubles.py:274`).
  - `MUTATION_REFUSAL` and `MutationHolder` are locked.
- 21-14: `_exit_after_removal` uses `Worker.wait` with a suppress, which matches the pyright-strict idiom at `test_catalog_tui.py:1854` (not `wait_for_complete`).
- 21-16: `MutationLock`, inherited by `UnifiedApp` and `_DoctorHost`, is locked by UI-SPEC line 132. The two new holders are table rows.
- 21-17: `installed_or` is justified, because `is_present` (`version_status.py:1020`) probes and the Policies view must not.
- 21-18: `JobStatesRead` and its worker follow the existing `_probe_competing_worker` shape; this plan adds no second loader.
- 21-19: the `PNPM_SMOKE_FAILED` and `PNPM_SPLIT_GROUP` constants are new copy, and they sit beside `PNPM_TRACKED_OFF_PATH`.
- 21-20: `r` reuses the 21-13 lock API and `request_refresh`.
- 21-21 guard and docs: the guard follows the `_PHASE_19_REQUIRED`/`_PHASE_20_REQUIRED` docs-pin pattern. `tests/test_guards.py` tests the ban shims, not source absence, so no existing scan helper fits.

## Counts

important=4 minor=6

Not checked: runtime behaviour. Also not checked:
- Whether `settle` (06-1, 15-1) also waits out the daemon-default worker that starts before `run_test`. 21-15's `test_the_daemon_default_holds_the_lock_from_construction` will show this; fall back to `wait_until(..., not app.mutation_in_flight)` there.
- Whether every `_settle_versions(..., screen=...)` call site has its target screen on top.
