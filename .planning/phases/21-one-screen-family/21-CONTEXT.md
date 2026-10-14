# Phase 21: One screen family - Context

**Gathered:** 2026-10-14 (assumptions mode, `--analyze --all --batch`, jev screening, best-over-easy)
**Status:** Ready for planning

<domain>
## Phase Boundary

Every screen shows the current truth after any mutation. Uninstall, Policies and Doctor become projections of the shared `ToolState` and follow the same lifecycle as the catalog tiers: a neutral root, one `show_view` path, one app-level refresh owner, a status lifecycle, removal on a worker, pruned selections, live Policies, and Doctor on the same lifecycle. The forks are deleted.

The WHAT is locked in `21-SPEC.md` (R1–R9). This file locks the HOW.

Out of scope:
- "Delete config too" (22).
- Script/L1 removal recipes (22).
- Hook reconfigure (23).
- Replacing the three tier instances or the six number keys.
- A `RowsScreen` base class.
- Cancelling a removal.

**Prerequisites:**
- 17: D-07 worker except, D-09 `move_link_mode`, D-11 typed settings load, D-13 Doctor `bin_dir` scan.
- 19: D-02/D-03 one swap and `state_of`, D-04, D-10 `removal_plan`, D-15 `health_cell`, D-19.
- 20: D-05 `selectable`, D-08 `RowOutcome`/`WORDS`, D-13 Enter waiter.

None of these has landed as of 2026-10-14.
</domain>

<decisions>
## Implementation Decisions

**Decision rule (user, 2026-10-13):** choose the best design, not the easiest. The analyzer's easy options were rejected wherever they kept a fork, a message bus that duplicates state, or a stale view.

### Screen stack and lifecycle (R1, R3)
- **D-01:** Delete `UnifiedApp.get_default_screen` (`wizard_app.py:2670-2674`), so Textual's empty `_default` screen is the neutral root.
  - The three tiers join `self._views` (today they are excluded, `:2509-2511`), and all six views are `install_screen`'d once in `on_mount` (`:2589-2590`).
  - `on_mount` always calls `await self.show_view(BASE_VIEW)`.
  - `_navigable` is `self.screen in self._views.values()`.
- **D-02:** `show_view` (`:2676-2712`) does, in order: `leaving.clear_transient()` for any `AppScreen`; pop if a view is on top; `await push_screen(target)`; `target.enter_view()`.
  - The `BASE_VIEW` branch and the catalog-only `clear_transient` call go away.
  - Pressing the current view's key does nothing.
- **D-03:** `AppScreen` (`ui_common.py:321-355`) gets these defaults:
  - `enter_view()` → `self.state_refreshed()`.
  - `state_refreshed()` does nothing.
  - `clear_transient()` → `self.status.clear()`.
  - `CatalogScreen` keeps its own `clear_transient` override, which also clears the recommends line.
- **D-04 (best, not easy):** Views only build widgets in `on_mount`; content and status are rendered only in `enter_view`/`state_refreshed`.
  - Because `show_view` awaits the push before `enter_view`, the first entry renders after mount and nothing overwrites a status written during entry.
  - `_pending_status`/`_set_status` (`:943-952, 1165-1186`) are deleted, not moved into the base class. jev: TypeSafe 0.97.

### Refresh owner (R2)
- **D-05:** One `UnifiedApp.request_refresh()` backed by one `@work(thread=True, exclusive=True, group="full-catalog-refresh")` worker over the full catalog (19 D-02).
  - A request that arrives during a pass sets `_refresh_pending`. The worker runs exactly one more pass after it commits, so requests coalesce and no second pass runs concurrently.
  - Every mutation calls `request_refresh()` after it completes, never before: install close, `u`, an Uninstall removal, a Policies toggle, Doctor `r`.
  - Entering a view never starts a pass (there is a spy test).
- **D-06:** On publish, the app calls `self.screen.state_refreshed()` directly when the top screen is an `AppScreen`. Hidden views render the published state on their next `enter_view`.
  - There is no message broadcast. `OwnershipRefreshed` (`catalog_tui.py:152`, handled at `wizard_app.py:2978-3000`) and the per-tier `_refresh_versions_worker`/`_refresh_skills_worker` (`catalog_tui.py:404-469`) are deleted.
  - 20 D-13's Enter waiter hooks into the same publication.

### Uninstall and removal (R4, R5)
- **D-07:** Uninstall renders three groups from `state_of` and `ToolState.removable` (19 D-10):
  - **removable:** `level` set; shows the proof (receipt, adoption or layout) and the environment levers.
  - **managed elsewhere:** present with no proof; shows `removable.hint`. A BROKEN row says "reinstall it from the catalog to repair; nothing to remove here".
  - **nothing to do:** missing or unavailable.
  - There is a Health column via `health_cell`.
  - An unknown owner never shows a manager name or argv.
  - `classify_tools`/`ToolRow`/the owner hints (`uninstall.py:100-339`), the `setup.py:807-868` closures, `_resync` (`:1238-1352`) and `ownership._own_script_install` (`:1436-1444`, callers `:1465,1511`) are deleted.
- **D-08:** Removal runs on `@work(thread=True, exclusive=True, group="uninstall-removal", exit_on_error=False)` and shows "Removing…".
  - **One app-level mutation lock** (user, 2026-10-14). While a removal runs, the user can **only navigate**.
    - Every other mutation is refused with a status ("a removal is running"): a second removal, an install run (Enter/`a`), `u`, Doctor `r`/fix, and Policies toggles.
    - The lock lives on `UnifiedApp` (`mutation_in_flight`), not as per-screen flags, so no screen can forget to check it. The existing `toggle_in_flight`/`daemon_default_in_flight` guards fold into it.
  - The worker posts `RemovalFinished` in `finally:`. Its handler clears the guard, renders the summary and calls `request_refresh()`.
  - Navigation is allowed while it runs (SPEC R5). Actions are not (see the lock above).
- **D-09 (user):** Only the tools being removed show `…`. This is signalled without a second renderer input:
  - When removal starts, the refresh service gets `mark_pending(ids)`. That publishes a derived map with those ids dropped, in the same generation, so `state_of(id)` returns `None` for exactly those ids and every tier renders `…`. Other rows keep their state.
  - The full pass after `RemovalFinished` republishes everything.
  - A crashed worker still posts `RemovalFinished` from `finally:`, so the pass always follows and no id stays pending.
  - `health_cell` reads only `state_of`; there is no app-level in-flight set for renderers to consult.
  - jev: Laya and TypeSafe both leaned toward bumping the whole generation, with low confidence (0.65 and 0.56). The user chose per-tool precision.
- **D-10 (best, not easy):** Quitting during a removal waits for the worker.
  - `action_abort`/`action_hard_abort` (`:3002-3011`) become `async`. When the mutation lock is held by a removal, they show "waiting for removal to finish…" and `await self.workers.wait_for_complete([removal_worker])`, then exit.
  - Textual's `_shutdown` does not wait for thread workers (`textual/app.py:3737-3752`). Refusing the quit was rejected because the SPEC says "waits". jev: TypeSafe 0.99.
- **D-11:** Removal outcomes extend 20 D-08's `RowOutcome`/`WORDS` with `removed` and `remove_failed`, so there is one vocabulary and the parity test covers them.
  - The environment-lever text (`_applied_summary`, `:1552-1597`) stays as it is.
  - Rows that ended remove_failed stay selected, following the 20 D-10 rule.

### Policies and Doctor (R7, R8)
- **D-12:** `PoliciesScreen.enter_view` (new; the class has none, `:1600-1652`) rebuilds `active_state` from `policy.is_active()` instead of the snapshot taken at construction (`:1638-1640`).
  - Missing prerequisites come from `policy.missing_requirements()`, with `missing_requires_now` bound to `state_of`, so installing `watch` unblocks the docker tweak.
  - DRIFT is `policy.owned() and not policy.is_active()`, only for policies that declare `owned` (today `linux_daemon_policy`, `policy.py:1250`).
  - macOS prune truth follows from the same live `is_active` (`plist_path.exists()`).
- **D-13 (best, not easy):** pnpm findings have one output channel, `ToolState.reasons`.
  - Missing and incomplete global shims are computed in the refresh pass from the cached inventory (19 D-19), so a dangling shim is `!` on its tier.
  - The expensive browser smoke check stays a Doctor worker (`_audit_globals_worker`). Its result goes into a session **evidence store** keyed by tool id, and then it calls `request_refresh()`. The pass reads that store when it builds reasons.
  - Doctor renders those reasons, not its own `node_globals_guidance(self._globals_report)` (`:495-500`).
  - jev: TypeSafe 0.92; Laya leaned toward Doctor rendering its own text (0.58), which would keep two sources.
- **D-14:** Doctor renders from `enter_view`/`state_refreshed`. The hidden `a` binding (`:292`) is deleted.
  - The first-run link pick's success branch (`_first_link_mode_picked`, `:2759-2788`) calls `target.enter_view()` when the target is Doctor, reusing Doctor's own re-render path. There is no second bespoke call.

### Pruning and deletions (R6, R9)
- **D-15:** `ToolBrowser.reload` (`tool_browser.py:204-220`) also drops selected ids whose item is still listed but no longer `selectable`. `selected_ids()` (`:325-331`) filters on `selectable`, so an unselectable id never reaches `Accepted`/execute.
- **D-16:** Each fork is deleted in the same wave as its replacement, not in a later cleanup wave (`.claude/architecture.md` rule 5): `OwnershipRefreshed`, `_pending_status`, `_resync` precedence, `classify_tools` and its closures, `_own_script_install`, and the per-tier and per-screen refresh workers (`uninstall-ownership-refresh` at `:1531`).
  - A grep test in `installer/` guards it.

### Claude's Discretion
- Plan and wave order. Suggested:
  1. Root, `show_view` and the `AppScreen` defaults.
  2. `request_refresh` and publish → `state_refreshed`.
  3. The Uninstall projection, the removal worker and `mark_pending`.
  4. Policies and Doctor.
  5. Pruning and the grep test.
- The names of the evidence store and the `mark_pending` API.

### Folded Todos
- `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor` (score 0.9) is covered by D-13 and SPEC R8.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/21-one-screen-family/21-SPEC.md`: locked R1–R9
- `.planning/research/2026-10-13-target-architecture.md`: §2 (single owner, publication), §4.3 (RemovalPlan), §7 (screen lifecycle table)
- `.planning/phases/19-one-tool-state-with-health-plus-receipts/19-CONTEXT.md`: D-02/D-03, D-04, D-10, D-15, D-19
- `.planning/phases/20-install-plan-with-dispositions/20-CONTEXT.md`: D-05, D-08, D-10, D-13
- `.planning/phases/17-stop-the-bleeding/17-CONTEXT.md`: D-07, D-09, D-11, D-13
- `.planning/todos/pending/2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md`
- `.planning/REQUIREMENTS.md`: UI-01..08
- `.claude/architecture.md`, `AGENTS.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ui_common.AppScreen` (`:321-355`), `CatalogScreen.clear_transient` (`catalog_tui.py:825-837`)
- The worker plus in-flight-guard plus `finally`-posted message idiom (`wizard_app.py:2062-2071, 2613-2650`)
- `policy.Policy.is_active`/`owned`/`missing_requirements` (`policy.py:132-164`)
- `DoctorScreen.enter_view` (`:417-433`); `pnpm_globals.py:172-178`
- `tool_browser.ToolBrowser.reload`/`selected_ids`/`action_select_all`

### Established Patterns
- A Textual screen only dispatches bindings when it is on top. An installed screen is composed, but its `on_mount` fires on the first push.
- The epoch/generation fail-closed read (19).
- Textual does not wait for thread workers at shutdown, so an explicit await is required.

### Integration Points
- `request_refresh()` ← every mutation site; the publish → `self.screen.state_refreshed()`; the 20 D-13 waiter
- `mark_pending(ids)` ← the removal worker's start
- The evidence store ← Doctor's smoke worker → the refresh pass → `reasons`
</code_context>

<specifics>
## Specific Ideas

- The user's expectation for removal (not a requirement now): during a removal the screen would stay put and not allow going to other views. See Deferred.
</specifics>

<deferred>
## Deferred Ideas

- ~~Block navigation while a removal runs~~ was resolved 2026-10-14: the user chose "navigation yes, actions no" (D-08 mutation lock).

### Reviewed Todos (not folded)
- GSD per-repo installs (0.6), Playwright Flatpak Chrome (0.6), pi repair/sync (0.6): outside this phase.
</deferred>
