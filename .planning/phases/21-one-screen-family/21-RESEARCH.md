# Phase 21: One screen family - Research

**Researched:** 2026-10-18
**Domain:** In-repo Python/Textual refactor. One screen lifecycle (`AppScreen` defaults + `UnifiedApp.show_view`), one app-level refresh owner, Uninstall/Policies/Doctor as projections of `ToolState`, removal on a worker with a mutation lock. No new packages, no external services.
**Confidence:** HIGH for the code map, the call sites and the hazards (every location below was read this session, line numbers are current `main` at `5f9a5d1`). MEDIUM for the design recommendations tagged `[ASSUMED]` (they need the planner or user to confirm).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Decision rule (user, 2026-10-13):** choose the best design, not the easiest. The analyzer's easy options were rejected wherever they kept a fork, a message bus that duplicates state, or a stale view.

#### Screen stack and lifecycle (R1, R3)
- **D-01:** Delete `UnifiedApp.get_default_screen` (`wizard_app.py:2670-2674`), so Textual's empty `_default` screen is the neutral root.
  - The three tiers join `self._views` (today they are excluded, `:2509-2511`), and all six views are `install_screen`'d once in `on_mount` (`:2589-2590`).
  - `on_mount` always calls `await self.show_view(BASE_VIEW)`.
  - `_navigable` is `self.screen in self._views.values()`.
- **D-02:** `show_view` (`:2676-2712`) does, in order: `leaving.clear_transient()` for any `AppScreen`; pop if a view is on top; `await push_screen(target)`; `target.enter_view()`.
  - The `BASE_VIEW` branch and the catalog-only `clear_transient` call go away.
  - Pressing the current view's key does nothing.
- **D-03:** `AppScreen` (`ui_common.py:321-355`) gets these defaults:
  - `enter_view()` -> `self.state_refreshed()`.
  - `state_refreshed()` does nothing.
  - `clear_transient()` -> `self.status.clear()`.
  - `CatalogScreen` keeps its own `clear_transient` override, which also clears the recommends line.
- **D-04 (best, not easy):** Views only build widgets in `on_mount`; content and status are rendered only in `enter_view`/`state_refreshed`.
  - Because `show_view` awaits the push before `enter_view`, the first entry renders after mount and nothing overwrites a status written during entry.
  - `_pending_status`/`_set_status` (`:943-952, 1165-1186`) are deleted, not moved into the base class. jev: TypeSafe 0.97.

#### Refresh owner (R2)
- **D-05:** One `UnifiedApp.request_refresh()` backed by one `@work(thread=True, exclusive=True, group="full-catalog-refresh")` worker over the full catalog (19 D-02).
  - A request that arrives during a pass sets `_refresh_pending`. The worker runs exactly one more pass after it commits, so requests coalesce and no second pass runs concurrently.
  - Every mutation calls `request_refresh()` after it completes, never before: install close, `u`, an Uninstall removal, a Policies toggle, Doctor `r`.
  - Entering a view never starts a pass (there is a spy test).
- **D-06:** On publish, the app calls `self.screen.state_refreshed()` directly when the top screen is an `AppScreen`. Hidden views render the published state on their next `enter_view`.
  - There is no message broadcast. `OwnershipRefreshed` (`catalog_tui.py:152`, handled at `wizard_app.py:2978-3000`) and the per-tier `_refresh_versions_worker`/`_refresh_skills_worker` (`catalog_tui.py:404-469`) are deleted.
  - 20 D-13's Enter waiter hooks into the same publication.

#### Uninstall and removal (R4, R5)
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

#### Policies and Doctor (R7, R8)
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

#### Pruning and deletions (R6, R9)
- **D-15:** `ToolBrowser.reload` (`tool_browser.py:204-220`) also drops selected ids whose item is still listed but no longer `selectable`. `selected_ids()` (`:325-331`) filters on `selectable`, so an unselectable id never reaches `Accepted`/execute.
- **D-16:** Each fork is deleted in the same wave as its replacement, not in a later cleanup wave (`.claude/architecture.md` rule 5): `OwnershipRefreshed`, `_pending_status`, `_resync` precedence, `classify_tools` and its closures, `_own_script_install`, and the per-tier and per-screen refresh workers (`uninstall-ownership-refresh` at `:1531`).
  - A grep test in `installer/` guards it.

### Claude's Discretion
- Plan and wave order. Suggested:
  1. Root, `show_view` and the `AppScreen` defaults.
  2. `request_refresh` and publish -> `state_refreshed`.
  3. The Uninstall projection, the removal worker and `mark_pending`.
  4. Policies and Doctor.
  5. Pruning and the grep test.
- The names of the evidence store and the `mark_pending` API.

### Deferred Ideas (OUT OF SCOPE)
- ~~Block navigation while a removal runs~~ was resolved 2026-10-14: the user chose "navigation yes, actions no" (D-08 mutation lock).
- Reviewed todos (not folded): GSD per-repo installs (0.6), Playwright Flatpak Chrome (0.6), pi repair/sync (0.6): outside this phase.
- Out of scope per the phase boundary: "Delete config too" (22); script/L1 removal recipes (22); hook reconfigure (23); replacing the three tier instances or the six number keys; a `RowsScreen` base class; cancelling a removal.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | After any mutation every view shows the new state on its next entry, and immediately if visible | One `request_refresh()` owner + publish -> `state_refreshed()` (Patterns 2, 3); matrix harness (Validation); pitfalls P3, P4, P5, P6, P12, P13 |
| UI-02 | Every view clears its transient status on leave and keeps a status written during entry | `AppScreen` defaults + `show_view` order (Pattern 1); D-04 is mechanically safe because `await push_screen` mounts the screen and its children first (verified by probe, see Pattern 1); pitfalls P8, P18 |
| UI-03 | Uninstall lists removable (with proof), managed elsewhere (with hint), nothing to do, from the shared state; unknown owner never attributed | Projection function over `ToolState` (Pattern 4); **prerequisite gap G1**: `RemovalPlan.level/hint` do not exist on `main` |
| UI-05 | Removal on a worker with visible progress | Removal worker + `mark_pending` + mutation lock + quit wait (Patterns 5, 6, 7); pitfalls P9, P10, P11, P14, P15 |
| UI-06 | Policies show live truth on entry (drift, live prerequisites) | Live `is_active`/`owned`/`missing_requires_now` (Pattern 8); pitfalls P16, P17 |
| UI-07 | Doctor follows the same lifecycle, hidden `a` removed, dangling pnpm shims appear as broken | Doctor lifecycle + evidence store (Pattern 9); gap G4; pitfalls P19, P20 |
| UI-08 | A selection no longer selectable is pruned on reload | `ToolBrowser.reload`/`selected_ids` (Pattern 10) |
</phase_requirements>

## Summary

The phase is a lifecycle unification, not a feature build. Every mechanism it needs already exists in smaller form: the `AppScreen.enter_view` hook, `CatalogScreen.clear_transient`, a worker-plus-`finally`-posted-message idiom (`_apply_daemon_default_worker`), `run_live`, `health_cell`, `WORDS`/`RowOutcome`/`summary_counts`/`retained`, `remove_proven`, `policy_owned`, `missing_requires_now`, `Worker.wait_for_complete`. The work is (1) moving the three tiers off the Textual default screen onto the same push path as the other three views, (2) replacing three divergent refresh paths with one app-owned coalescing worker, (3) rewriting Uninstall, Policies and Doctor to render from published state in `enter_view`/`state_refreshed`, and (4) deleting the forks.

Four things in CONTEXT.md are **not true of `main`** and the planner must absorb them before writing tasks (details in "Corrections to CONTEXT.md"): `RemovalPlan` has no `level`/`hint` (Phase 19 shipped the path split only); the line numbers in CONTEXT are stale by about +80 lines after Phase 20; `tweak_policy` and both daemon factories bake a construction-time `installed_tools` snapshot, so `missing_requires_now` is not bound to anything for them; and `perform_uninstall` returns no per-tool outcome (it discards the removed paths), so D-11's `removed`/`remove_failed` cannot be produced without changing its return. The Linux daemon's `is_active()` can spawn `systemctl`, so reading it from `PoliciesScreen.enter_view` on the event loop is a hazard that D-12 does not mention.

The blast radius on tests is large but contained by helpers: `UninstallInputs` is built 127 times in tests (84 inside `tests/test_wizard_app.py`, almost all through the one `_uninstall_inputs` helper at `tests/test_wizard_app.py:173`), `ToolRow`/`classify_tools` appear 71/52 times, `current_view` 52. Rewriting the helper first keeps the churn to one place. The five affected test files run in about 15 s under `-n auto`.

**Primary recommendation:** Land in six plans over five waves exactly along CONTEXT's order, add a Wave 0 for test doubles, and treat the four corrections below as explicit task content. Keep all refresh flags on the event loop (the worker runs one pass and posts one message; the handler decides whether to run another), keep the Uninstall group a pure function of `ToolState`, and make `perform_uninstall` return per-tool results.

## Corrections to CONTEXT.md (read first)

| # | CONTEXT says | `main` actually has | Consequence for the plan |
|---|--------------|---------------------|--------------------------|
| G1 | D-07: groups come from `ToolState.removable` with `level` and `hint` (19 D-10 `removal_plan`) | `RemovalPlan` is the path split only: `[VERIFIED: installer/uninstall.py:75-80]` `removable: tuple[Path, ...]` / `yourself: tuple[Path, ...]` / `by_tool: Mapping[str, tuple[Path, ...]]` / `artifacts: Mapping[Path, receipts.ReceiptArtifact]`. No `level`, no `hint`, no `removal_plan` function anywhere in `installer/` `[VERIFIED: grep "removal_plan\|\.level\|\.hint" installer]` | Derive the group in a pure function from `ToolState.health`, `.removable.removable`, `.receipt`, `.ownership` (Pattern 4). Do **not** extend `RemovalPlan` unless a task needs it; Phase 22 owns the `level/argv` contract. |
| G2 | Line numbers (`wizard_app.py:2670`, `:1238`, ...) | Phase 20 grew the file. Current: `get_default_screen` `:2753`, `show_view` `:2759`, `_navigable` `:2798`, `_first_link_mode_picked` `:2837`, `_install_closed` `:2890`, `on_ownership_refreshed` `:3037`, `action_abort` `:3061`, `UninstallScreen` `:922`, `_resync` `:1252`, `_apply_removal` `:1456`, `PoliciesScreen` `:1619`, `DoctorScreen` `:292` `[VERIFIED: grep -n on installer/wizard_app.py]` | Use symbol names, not CONTEXT's numbers, in plan tasks. |
| G3 | D-12: `missing_requires_now` bound to `state_of` | Only `omz_plugins_policy` sets it `[VERIFIED: installer/policy.py:798-799]` `missing_requires=read_missing_requires(),` / `missing_requires_now=read_missing_requires,`. `tweak_policy` computes `missing_requires` once from the `installed_tools` mapping `[VERIFIED: installer/policy.py:586-588]` `installed_tools = installed_tools or {}`; `daemon_policy` the same at `:1004-1006`; `setup.py:819` builds `installed = {tool.id: is_installed(tool) for tool in tools}` once | Change the three factories to accept a live predicate and set `missing_requires_now` (Pattern 8). |
| G4 | D-13: Doctor's missing/incomplete pnpm findings come from the cached inventory in the pass | Incomplete groups: already in `ToolState` `[VERIFIED: installer/version_status.py:692]` `fact = _ConfigFacts((f"pnpm group incomplete: missing {names}",), steps)`. A dangling shim (shim present, package gone) is already BROKEN `[VERIFIED: installer/version_status.py:608-610]` `BROKEN_SHIM_REASON = (` `"shim present, package missing — select it and press enter to reinstall and repair"`. **Not** in `ToolState`: `NodeGlobalsReport.missing` (pnpm tracks it, command gone from PATH), `.unhealthy` (smoke failures) and `.split_groups` (needs group paths, which the cached `frozenset` of names does not carry) `[VERIFIED: installer/pnpm_globals.py NodeGlobalsReport fields]` | Phase 21 adds only: missing (pass, from cached inventory + `which`), unhealthy and split (evidence store). Success criterion 5's "dangling shim shows as broken" on the tier is **already true**; the new work is Doctor rendering the same reasons. |
| G5 | D-11: `removed`/`remove_failed` outcomes | `perform_uninstall` assigns `_removed, refused = remove_proven(...)` and returns `SweepResult(warnings=refused)` `[VERIFIED: installer/app.py:681,722]`; `remove_paths` raises on a failed delete and aborts the remaining tools; `_applied_summary` prints `swept.warnings` only inside the `remove_tweaks` branch `[VERIFIED: installer/wizard_app.py:1611]` `parts.extend(f"warning: {warning}." for warning in swept.warnings)` | Return per-tool results from the remover (Pattern 5). Today a refused path is silent unless the tweaks lever was also chosen. |
| G6 | D-10: "`action_abort`/`action_hard_abort` become async" | Both are sync `[VERIFIED: installer/wizard_app.py:3061,3068]`. `Worker.wait()` raises `WorkerFailed`/`WorkerCancelled` `[VERIFIED: textual/worker.py:450-454]`, and `wait_for_complete` only swallows `CancelledError` `[VERIFIED: textual/worker_manager.py:178-181]` | Wrap the wait in `contextlib.suppress(WorkerFailed, WorkerCancelled)` or a crashed removal makes the quit raise (Pattern 7). |

## Project Constraints (from CLAUDE.md / AGENTS.md)

`./CLAUDE.md` does not exist; `./AGENTS.md` and `.claude/*.md` apply with the same authority as locked decisions.

- **uv only.** Never `pip`/`poetry`/`conda`. `make test` = `uv run pytest -n auto --cov`; `make validate` = ruff check, ruff format --check, pyright (strict), bandit, vulture `[VERIFIED: Makefile:37-54]`. Coverage floor `fail_under = 90` `[VERIFIED: pyproject.toml:58]`.
- **Never bypass a gate.** No `# noqa`/`# type: ignore`/`# nosec`/vulture whitelist to go green; no `skip`/`xfail` to dodge a failure.
- **Never mutate the developer's host.** No `make setup/fix/uninstall`, no mutating `systemctl --user`, no real shell rc or agent settings. Tests use `tmp_path` HOME, fake removers and `FrozenStateService`-style doubles; real removals run only in disposable containers (`scripts/detect-container-runtime.sh`).
- **Zero sudo.** No `sudo`/`pkexec`/`doas`; native-owner removal is a hand-off of the exact command.
- **xdist-safe tests.** `tmp_path`, `monkeypatch`, no fixed ports/paths, no order dependence. `-n auto` is capped at ~40 % of threads by `tests/conftest.py`; never pass a fixed or higher `-n`.
- **English only; coherent commits** (amend/fixup, no "fix review" trail); `make validate && make test` on the exact tree committed.
- **Architecture rules 1-5** (`.claude/architecture.md`): one view registry (`VIEWS`), one navigation path (`show_view`; installed screens are destroyed on pop if not installed), one apply workflow (`ui_common.run_live`, no screen-local `try/except OSError`), `setup.py` is wiring only (decision functions belong in `installer/`), no orphan helpers (delete or adopt; delete a fork in the wave that replaces it).
- **Doctrine tests.** `tests/test_docs.py` pins phrases in `.claude/architecture.md` (`_PHASE_20_REQUIRED` includes `"_await_state"` and `"single flight"`) `[VERIFIED: tests/test_docs.py:187-203]`. Replacing `_await_state` or rewriting the doc section without updating the constant fails the suite.
- **Config:** `workflow.nyquist_validation: true`, `security_enforcement: true` (ASVS 1, block on high), `tdd_mode: true`, `use_worktrees: true` `[VERIFIED: .planning/config.json]`. Plans should be test-first and file-disjoint inside a wave.

## Architectural Responsibility Map

TUI-only project; tiers are the project's own layers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Navigation, stack, `show_view`, lifecycle order | App shell (`UnifiedApp`, `wizard_app.py`) | `ui_common.AppScreen` defaults | Architecture rule 2: one navigation path |
| Refresh coalescing, publish, mutation lock, quit wait | App shell (`UnifiedApp`) | `VersionRefreshService` (state, `mark_pending`, evidence) | One owner; screens only call `app.request_refresh()` / read the lock |
| State truth (`ToolState`, `state_of`, epoch/seq swap, evidence store) | Core (`installer/version_status.py`) | — | Rule 4: decisions live in `installer/` |
| Uninstall grouping, hints, proof label, per-tool removal results | Core (`installer/uninstall.py`, `installer/app.py::perform_uninstall`) | `session.py` vocabulary | Pure and testable under pyright/coverage |
| Removal vocabulary (`removed`, `remove failed`) | Core (`installer/session.py`: `WORDS`, `RESULT_WORDS`) | `render.py` | One vocabulary, parity test |
| Rendering of rows, cells, status | Screens (`wizard_app.py`, `catalog_tui.py`) | `tool_browser.py`, `health_cell` | Screens project state; they own no truth |
| Policy live truth (`is_active`, `owned`, `missing_requires_now`) | Core (`installer/policy.py`) | `setup.py` wiring | Closures bound in the composition root |
| pnpm findings as reasons | Core (`version_status._pass`, `pnpm_globals`) | Doctor worker (evidence) | Single output channel `ToolState.reasons` |
| Composition (closures, services) | `setup.py` | — | Wiring only |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| textual | 8.2.7 `[VERIFIED: uv run --no-sync python -c "import textual; print(textual.__version__)" -> 8.2.7; pyproject.toml:9 "textual>=8"]` | Screens, workers (`@work(thread=True)`), `App.workers.wait_for_complete`, `DataTable.update_cell(..., update_width=)` | Already the project's UI framework; no change |
| rich | `>=13` `[VERIFIED: pyproject.toml:7]` | `Text` for every dynamic cell (never markup) | Existing rule from Phases 19/20 |
| pytest + pytest-asyncio + pytest-xdist + pytest-cov | 9.0.3 / `>=1.4.0` / `>=3.8.0` / `>=5` `[VERIFIED: uv run pytest --version -> 9.0.3; pyproject.toml:22,31,32]` | `asyncio_mode = "auto"`, Textual `run_test()` pilots | Existing harness |

### Supporting
None to add. Reuse map is in "Reuse Map" below.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Handler-side restart for the coalesced second pass (recommended) | A `while` loop inside the thread worker reading `_refresh_pending` | Loop-in-worker needs a lock around the flag check; flags touched only on the event loop need none. Same observable behaviour. |
| `Disposition.REMOVE` + result `"remove_failed"` in the existing tables | A separate removal outcome type | A second type recreates the two-vocabulary problem D-11 forbids. |
| One `UnifiedApp.mutation_in_flight` with a reason key | Per-screen booleans | CONTEXT D-08 already rejected per-screen flags. |

**Installation:** none. No package is added or upgraded.

## Package Legitimacy Audit

No external package is installed or changed by this phase. `gsd-tools query package-legitimacy check` was not run because there is nothing to check.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                    keys 1-6 / ctrl+p / esc / header click
                                  |
                                  v
                       UnifiedApp.show_view(name)
        (no-op if name == current_view; root is empty + non-navigable)
                                  |
      leaving.clear_transient() -> pop_screen() -> await push_screen(target) -> target.enter_view()
                                  |                                                  |
                                  |                                       AppScreen.enter_view() = state_refreshed()
                                  |                                       (renders from state_of / live reads; NEVER starts a pass)
                                  v
   ┌──────────────────────── mutation sources ────────────────────────┐
   │ install close (_install_closed)   `u` (on_tool_updated)           │
   │ removal (RemovalFinished)         Policies toggle (_finish_toggle)│
   │ Doctor r (GlobalsReinstalled)     Doctor evidence changed         │
   └─────────────────────────────────┬─────────────────────────────────┘
        each: invalidate() first when tool facts changed, THEN
                                     v
                         UnifiedApp.request_refresh()          (event loop)
                  running? -> set _refresh_pending, return
                  else    -> _refresh_running = True; start worker
                                     v
        @work(thread=True, exclusive=True, group="full-catalog-refresh", exit_on_error=False)
           service.refresh(catalog)  -> post RefreshPublished(final=False)
           service.refresh_skills(catalog) -> post RefreshPublished(final=True)
           finally: post RefreshFinished(error)
                                     v
   app handler (event loop): topmost AppScreen in screen_stack .state_refreshed()
                 then if _refresh_pending: clear it, start ONE more pass; else _refresh_running = False
                                     v
         hidden views: nothing now; they call state_of again in their next enter_view

   Removal:  Accepted -> lock check -> ConfirmUninstall -> lock check again -> begin_mutation("removal")
             -> service.mark_pending(ids) -> publish (rows show …) -> status "Removing…"
             -> @work(thread=True, group="uninstall-removal") per-tool remove_proven
             -> finally post RemovalFinished -> handler: end_mutation, invalidate, summary, request_refresh
```

### Recommended Project Structure
```
installer/
├── ui_common.py        # AppScreen defaults (enter_view/state_refreshed/clear_transient); owner Protocol if used
├── wizard_app.py       # UnifiedApp: root, show_view, request_refresh, publish, lock, removal worker, quit wait; screens rewritten
├── catalog_tui.py      # CatalogScreen.state_refreshed; per-tier workers + OwnershipRefreshed deleted
├── tool_browser.py     # reload prunes unselectable; selected_ids filters on selectable
├── uninstall.py        # uninstall_group / managed_hint (pure); per-tool removal result; classify_tools/ToolRow deleted
├── app.py              # perform_uninstall returns per-tool results
├── session.py          # Disposition.REMOVE, Result "remove_failed", WORDS/RESULT_WORDS/_FAILURE/_KEEP
├── version_status.py   # mark_pending, evidence store, missing-shim fact in _pass
├── policy.py           # live installed predicate in tweak/daemon factories; omz is_active
├── execute_screen.py   # _wait_worker body -> app publication waiter
setup.py                # wiring only: drop rows/owner closures; bind live predicates
tests/
├── screen_family.py    # NEW doubles: held remover, pass-counting service, matrix harness (Wave 0)
├── test_screen_family.py   # NEW: call order, matrix, status lifecycle, lock, quit wait, grep guard
```

### Pattern 1: One lifecycle (R1, R3; D-01..D-04)

**What:** `AppScreen` owns the default lifecycle; `UnifiedApp.show_view` is the only caller.
**Verified shape of today's code:** `AppScreen.enter_view` already exists as a no-op hook `[VERIFIED: installer/ui_common.py:338-348]`; `CatalogScreen.clear_transient` already clears recommends and status `[VERIFIED: installer/catalog_tui.py:702-714]` `self._pending_recommends = ()` / `self.recommends_line.clear()` / `self.status.clear()`.
**Example:**
```python
# ui_common.AppScreen  [ASSUMED shape; names from D-03]
def enter_view(self) -> None:
    self.state_refreshed()

def state_refreshed(self) -> None:
    """Re-render from published state. Default: nothing."""

def clear_transient(self) -> None:
    self.status.clear()

# UnifiedApp
async def show_view(self, name: str) -> None:
    if name == self.current_view:
        return
    leaving = self._views.get(self.current_view)   # None while the root is the top screen
    if leaving is not None:
        leaving.clear_transient()
        await self.pop_screen()
    target = self._views[name]
    await self.push_screen(target)
    self.current_view = name
    target.enter_view()
    self._flush_pending_warnings(target)
```
**Facts the plan relies on:**
- `await push_screen(screen)` returns only after the screen **and its nested children** have mounted and run `on_mount`; the stack is `['Screen', 'V']` `[VERIFIED: probe in scratchpad: "after await push (True, True, True, 1) screen is v True", "stack ['Screen', 'V']"]`. This is what makes D-04 safe: `enter_view` after the awaited push always runs on a mounted tree.
- An installed screen survives `pop_screen` and re-push (`mounted True`) `[VERIFIED: same probe, "repush mounted True"]`.
- `current_view` is initialised to `BASE_VIEW` `[VERIFIED: installer/wizard_app.py:2630]` `self.current_view = BASE_VIEW`, so `show_view(BASE_VIEW)` in `on_mount` would hit the `name == self.current_view` early return. Initialise it to a root sentinel (`""`) or the first call is a no-op (pitfall P1).
- `UnifiedApp.catalog` and `catalog_for` stay; `_catalogs` is still the tier dict, `_views` gains the three tiers.

### Pattern 2: One refresh owner (R2; D-05)

**What:** `request_refresh()` is the only entry; flags live on the event loop.
**Reuse:** the worker-plus-`finally`-post idiom `[VERIFIED: installer/wizard_app.py:2696-2733]` (`@work(thread=True, exclusive=True, group="daemon-default", exit_on_error=False)` and `finally: ... self.post_message(DaemonDefaultApplied(...))`).
**Example:**
```python
def request_refresh(self) -> None:
    if self._version_refresh is None or self._quitting:
        return
    if self._refresh_running:
        self._refresh_pending = True        # coalesce; no second concurrent pass
        return
    self._refresh_running = True
    self._refresh_worker()

@work(thread=True, exclusive=True, group="full-catalog-refresh", exit_on_error=False)
def _refresh_worker(self) -> None:
    service, error = self._version_refresh, None
    try:
        _r, error = run_live(lambda: service.refresh(self._tools))
        self.post_message(RefreshPublished(error=error, warning=service.warning))
        if error is None:
            run_live(lambda: service.refresh_skills(self._tools))
            self.post_message(RefreshPublished(error=None, warning=service.warning))
    finally:
        self.post_message(RefreshFinished())

def on_refresh_published(self, message: RefreshPublished) -> None:   # event loop
    screen = self._topmost_app_screen()
    if screen is not None:
        screen.state_refreshed()
    ...status for error / cache warning...

def on_refresh_finished(self, _m: RefreshFinished) -> None:
    self._refresh_running = False
    if self._refresh_pending:
        self._refresh_pending = False
        self.request_refresh()
```
**Why two publications:** today the tier rows paint after `refresh` and the slow skill probe lands separately (`_refresh_versions_worker` then `_refresh_skills_worker`, `catalog_tui.py:402-433`). One worker must keep both points or first paint waits on the skill probe `[VERIFIED: installer/catalog_tui.py:402-433]`.
**`exclusive=True` caveat:** Textual cancels the earlier worker of the same group when a new one starts; a thread already running keeps running. Never call `_refresh_worker()` while one is running; the `_refresh_running` guard is what enforces D-05's "no second concurrent pass" (pitfall P2).

### Pattern 3: Publish target and status (R2, R3)

Use the topmost `AppScreen` in `screen_stack`, not `self.screen`. `self.screen` is the modal while `ConfirmUninstall`/`ExecuteScreen` is open, so D-06's literal wording skips the update and the covered view stays stale after the modal closes (pitfall P6). `_visible_app_screen` `[VERIFIED: installer/wizard_app.py:2965-2967]` (`screen = self.screen` / `return screen if isinstance(screen, AppScreen) else None`) is the helper to generalise. Re-render never calls `.focus()` (`ToolBrowser.on_mount` is the only place that does `[VERIFIED: installer/tool_browser.py:171-175]`), so it cannot steal focus from the modal.

### Pattern 4: Uninstall is a pure projection (R4; D-07)

New pure function in `installer/uninstall.py` (rule 4), replacing `classify_tools` `[VERIFIED: installer/uninstall.py:359-369]` (`def classify_tools(` with `installed: dict[str, bool]`, `owner_hint`, `owner_label_hint`). Reuse `UninstallState` as the group key `[VERIFIED: installer/enums.py:71-77]` `REMOVABLE = "removable"` / `MANAGED = "managed"` / `ABSENT = "absent"` / `UNAVAILABLE = "unavailable"`; the screen merges `ABSENT` and `UNAVAILABLE` under the title `nothing to do` (UI-SPEC A1).

```python
def uninstall_group(state: ToolState | None) -> UninstallState:   # [ASSUMED rule order]
    if state is None or state.health in (Health.MISSING, Health.UNAVAILABLE):
        return UninstallState.ABSENT if ... else UninstallState.UNAVAILABLE   # None -> ABSENT with "…"
    if state.health is Health.BROKEN:
        return UninstallState.MANAGED          # repair sentence, never selectable
    return UninstallState.REMOVABLE if state.removable.removable else UninstallState.MANAGED
```
Detail text per UI-SPEC table:
- Removable: proof sentence from `state.receipt` (receipt) or `ADOPTED_NOTE` (adopted) or layout; `paths = state.removable.removable` (these become `UninstallDecision.paths`).
- Managed, known owner: `removal_hint(state.ownership, tool.cmd)` `[VERIFIED: installer/ownership.py:1602-1622]` returns the manager sentence, `None` for `unknown` and `installer` (`_NO_REMOVAL_HINT`). Cell label: `removal_label(state.ownership)` `[VERIFIED: installer/ownership.py:1644-1668]`.
- Managed, owner `unknown`: fixed `owner unknown; nothing here can remove it safely`; cell `unknown`; no manager name, no argv (prohibition).
- Managed, BROKEN: fixed `reinstall it from the catalog to repair; nothing to remove here`.
- Managed, `installer`-owned but unproven: `UNPROVEN_NOTE` is already in `state.reasons` `[VERIFIED: installer/version_status.py:618]` (`# Phase 20 binds r on the review screen`) `UNPROVEN_NOTE = "not proven: select it, then press r on the review to reinstall and adopt"`; reuse it (see O1/A3).
- **Keep the SAFE-03 suffix.** `classify_tools` appends `remove it yourself: <paths>` from `plan.yourself`; with `ToolState.removable.yourself` available the projection must keep it or it regresses Phase 17 (`classify_tools` body, `uninstall.py:407-413`). Keep the `required by` suffix from `reverse_dependencies` `[VERIFIED: installer/uninstall.py:347]` (`def reverse_dependencies(tools: list[Tool]) -> dict[str, list[str]]:`).
- Nothing-to-do text: `_HEALTH_DETAIL[Health.MISSING]` is `"not installed"` and unavailable reasons are already `state.reasons[0]` (`tool_state` puts `absent_reason` first) `[VERIFIED: installer/version_status.py:218-250 tool_health, installer/catalog_tui.py:258-266]`.
- Standing status `Nothing to uninstall.` must require **all states known** and none present and no environment rows; otherwise it would claim emptiness before the first pass (every state is `None` then). See P7.

### Pattern 5: Removal outcomes (R5; D-08, D-11)

Vocabulary, reusing the Phase 20 tables `[VERIFIED: installer/session.py:87-98, 134-143, 216-217]`:
- `Disposition` members `WAIT, INSTALL, UPDATE, REPAIR, RECONFIGURE, REINSTALL, SKIP, BLOCKED`; `_FAILURE = frozenset({"failed", "mismatch", "dependency_failed", "not_attempted", "crashed"})`; `_KEEP = _FAILURE | {"blocked", "manual"}`.
- Add `Disposition.REMOVE = Words("will remove", "removed", "red", done_style="green")`, `Result` member `"remove_failed"` with `RESULT_WORDS["remove_failed"] = ("remove failed", "red")`, add it to `_FAILURE` (so `retained()` keeps the row selected and the arithmetic of `summary_counts` includes it) and to `summary_counts`' explicit result tuple and `render._FAILURE_RESULTS`. **Do not add REMOVE to `RUNNABLE`** `[VERIFIED: installer/session.py:113-121]`; `execute_plan` would try to install it (P11).
- `list(Disposition)` is iterated by `_REVIEW_ORDER` and by parametrised tests `[VERIFIED: tests/test_render.py:671, tests/test_plan.py:558-568]`; add REMOVE fixtures there or those tests fail.
- Do not push removal outcomes into `UnifiedApp.outcomes` (that dict feeds the session exit code, `_record`); a failed interactive removal must not turn `make setup` into exit 1 `[ASSUMED]`.

Per-tool remover (core, not screen): change `perform_uninstall` `[VERIFIED: installer/app.py:650-722]` to loop tools, call `remove_proven([tool], tool_paths, bin_dir)` inside `try/except OSError`, and return per-tool `removed`/`failed` (+ first error line via `session._first_line`, `session.py:336`, made public) alongside the existing `SweepResult` fields. `remove_proven` already re-proves with `verify=True` at deletion time and retires a receipt only when every proven path is gone `[VERIFIED: installer/uninstall.py:532-557]`; do not add any new deletion code.

### Pattern 6: `mark_pending` (D-09)

Service-side, under `self._lock`, same file as the single publication point `[VERIFIED: installer/version_status.py:1760]` `self._states = {**self._states, **fresh}`:
```python
def mark_pending(self, tool_ids: Collection[str]) -> None:      # [ASSUMED name/shape]
    with self._lock:
        self._pending |= set(tool_ids)
        self._states = {k: v for k, v in self._states.items() if k not in self._pending}
```
- `state_of` already answers `None` for an absent key `[VERIFIED: installer/version_status.py:1015-1018]` `state = self._states.get(tool_id)` / `if state is None or state.generation != self._epoch:` / `return None`.
- The commit filter must skip pending ids, otherwise a pass that started **before** `mark_pending` and commits after it republishes the pre-removal state for those ids (`fresh` is filtered only by `current.seq < seq`, `version_status.py:1751-1755`). `invalidate()` clears `_pending` (its epoch bump already hides every state) (P9).
- After `mark_pending`, call the same publish path as a pass so visible tiers repaint `…` immediately.

### Pattern 7: Mutation lock and quit wait (R5; D-08, D-10)

```python
# UnifiedApp  [ASSUMED shape]
@property
def mutation_in_flight(self) -> bool: ...
def begin_mutation(self, kind: str) -> bool: ...     # False + nothing started when held
def end_mutation(self, kind: str) -> None: ...
def refuse_if_mutating(self, screen: AppScreen) -> bool:   # sets warn status, returns True when refused
    ...

async def action_abort(self) -> None:
    if not self._navigable():
        return
    await self._exit_after_removal()

async def _exit_after_removal(self) -> None:
    worker = self._removal_worker
    self._quitting = True                       # suppress the post-removal request_refresh
    if worker is not None and worker.is_running:
        screen = self._topmost_app_screen()
        if screen is not None:
            screen.status.set("Waiting for the removal to finish…", "warn")
        with contextlib.suppress(WorkerFailed, WorkerCancelled):
            await self.workers.wait_for_complete([worker])
    self.exit(None)
```
- `Worker.is_running` exists `[VERIFIED: textual/worker.py:219]`; `WorkerFailed`/`WorkerCancelled` at `:49,:61`. Textual itself calls `self.workers.cancel_all()` on exit and does not join thread workers `[VERIFIED: textual/app.py:3465]`, so the explicit await is required.
- Check the lock at **both** the open and the mutation point: `ConfirmUninstall` can stay open while the on-by-default daemon worker starts (`_apply_removal` already re-checks `daemon_default_in_flight` for this exact reason, `wizard_app.py:1469`).
- Mutation sites that must call the lock (each currently has its own guard or none): `CatalogScreen.action_update_tool` (`catalog_tui.py:777`), `UnifiedApp.on_catalog_screen_decided` (install `Decided`, `wizard_app.py:2884`), `DoctorScreen.action_apply`/`action_reinstall_globals`, `PoliciesScreen.action_toggle_policy`/`_time_picked`/`_link_mode_picked`, `UnifiedApp._first_link_mode_picked`, `UninstallScreen._apply_removal`. The folded flags are `toggle_in_flight` (8 refs incl. `tests/test_policies_e2e.py`) and `daemon_default_in_flight` (18 refs) `[VERIFIED: grep -rc]`.

### Pattern 8: Policies live truth (R7; D-12)

- Rows are built once; `enter_view`/`state_refreshed` call `update_cell(..., update_width=True)` per policy. `update_width` defaults to `False` `[VERIFIED: textual/widgets/_data_table.py:871-878]` and the DRIFT cell `! [drift]` is wider than `○ [off]`, so omit it and the cell clips (P17).
- Live reads: `policy.is_active()` when present else `policy.active`. **Six** factories build a `Policy` `[VERIFIED: grep "Policy(" installer/policy.py -> :478 ban, :590 tweak, :720 cache_redirect, :790 omz, :1007 macOS daemon, :1386 linux daemon]`; only `omz_plugins_policy` has no `is_active` (it passes `active=plugins_owned(state_path)` only) so it needs `is_active=lambda: plugins_owned(state_path)` or it stays stale.
- DRIFT: `policy.owned is not None and policy.owned() and not active`. Reuse `uninstall.policy_owned` `[VERIFIED: installer/uninstall.py:593]` only for the predicate fallback chain, but DRIFT must require the field itself (`owned` is declared only by `linux_daemon_policy`, `policy.py:1401` `owned=_owned,`).
- **Event-loop hazard (P16):** the Linux daemon's `is_active` is `cache.read() is DaemonState.ACTIVE` `[VERIFIED: installer/policy.py:1375-1377]`, and `TimerStateCache.read()` "MAY block for up to the probe's own timeout" `[VERIFIED: installer/systemd_daemon.py:501-503]`. `peek()` "NEVER probes" `:522-523`. Recommended: read every policy synchronously except those with `state_cache is not None`; for those use `state_cache.peek()` on the loop and a thread worker (the `_probe_competing_worker` shape, `wizard_app.py:1701-1711`) that calls `live_state(policy_id)` and then updates the row (as `refresh_daemon_state` does).
- Live requires: give `tweak_policy` (`:502`), `daemon_policy` (`:831`) an `installed_tools: Mapping[str, bool] | Callable[[str], bool]` and set `missing_requires_now` from it, mirroring `omz_plugins_policy`'s `present: bool | Callable[[], bool]` + `missing_requires_now=read_missing_requires` (`policy.py:734-799`). `setup.py` passes `lambda tool_id: (s := version_refresh.state_of(tool_id)) is not None and s.present`. `linux_daemon_policy` accepts `installed_tools` but does `del installed_tools` `[VERIFIED: installer/policy.py:1095]`; leave it. Tests that pass a plain dict (28 refs) keep working because the parameter is a union.
- Link-mode line is re-read in the same pass (`_refresh_link_mode_line`, `wizard_app.py:1718-1723`).

### Pattern 9: Doctor on the lifecycle (R8; D-13, D-14)

- Delete `Binding("a", "apply", "apply", show=False),` `[VERIFIED: installer/wizard_app.py:303]`; flip `tests/test_wizard_app.py::test_doctor_hidden_a_alias_applies_fix` (`:895`) to assert inertness.
- Move `_refresh_guidance`/`_refresh_body` and the two worker starts from `on_mount` to `enter_view`; implement `state_refreshed` as the re-render. Today `on_mount` renders and `enter_view` guards on `is_mounted` `[VERIFIED: installer/wizard_app.py:422-444]`.
- Evidence store (session, on `VersionRefreshService`): `record_evidence(tool_id, broken=(...), notes=(...))` under `_lock`, read by `_pass` when it builds `Evidence` for a tool (`facts = config.get(tool.id, _NO_FACTS)` site, `version_status.py:1703-1721`). Smoke failures -> `broken` (the tool "is installed but does not work", `guidance.py:344-356`), split groups -> `notes` on the declaring tool. Store only failures so a healthy machine records nothing.
- Missing shim fact: in `_pnpm_group_facts` neighbourhood, for each tool with a `node` method whose `npm_pkg` is in `inventory.pnpm_globals` and whose command does not resolve, add a note (health stays MISSING; `tool_health` drops present-only facts for an absent tool, `version_status.py:218-236`, and `tool_state` moves misconfigured to notes at `:766`). Reuse the sentence from `node_globals_guidance` `[VERIFIED: installer/guidance.py:307-330]` ("pnpm still tracks {names} globally, but the command no longer resolves on PATH.").
- Doctor renders `state_of(tool_id).reasons` for tools with a `node` method (use `pnpm_globals.node_globals(tools)`, `pnpm_globals.py:181`) instead of `node_globals_guidance(report)`. It **keeps** `NodeGlobalsReport.managed` for the reinstall preview and `r` (`wizard_app.py:781`).
- **Audit-loop hazard (P19):** `_start_globals_audit` runs on every entry (`wizard_app.py:443`). If every audit end calls `request_refresh()`, every Doctor entry costs a full pass and violates the "entering starts no pass" spirit. Call `request_refresh()` only when the evidence set **changed**.
- First-run link pick: in the success branch of `_first_link_mode_picked` (`wizard_app.py:2881-2882`) call `target.enter_view()` when `target` is the Doctor (D-14). Doctor shows the mode through `preview()` which reads `_current_link_mode()` live (`setup.py:1056-1063`).

### Pattern 10: Prune (R6; D-15)

`ToolBrowser.reload` today drops only ids whose item disappeared `[VERIFIED: installer/tool_browser.py:246-249]` `stale = {key for key in self._by_id if key is not None}` ... `self.selected -= stale - {key for key in self._by_id if key is not None}`. Add: for ids of the new adapter's items with `not selectable(item)`, also subtract them. Keep the in-place `-=` (the three tier browsers share one set). `selected_ids()` (`:356-362`) adds `and selectable(item)`; `action_accept` posts that list (`:364-365`). Safe for the catalog: its `selectable` is `not self._is_unavailable(tool)` (`catalog_tui.py:365`) and `_is_unavailable` falls back to the launch-time map while state is `None`, so a `…` row (pending removal) is not pruned from the shared staged set.

### Anti-Patterns to Avoid
- **A second render input for "pending".** D-09 says `health_cell` reads only `state_of`; do not add an app-level in-flight set for renderers.
- **Starting a pass from an entry, an audit end with unchanged evidence, or a refused mutation's early return.** The spy test counts them.
- **`self.screen` as the publish target.** Use the topmost `AppScreen`.
- **Markup for dynamic text.** Tool ids, paths, errors and reasons go through `Text` and `sanitize_log_line`, never `Text.from_markup`; `BrowserAdapter.detail_is_markup=False` for Uninstall is already set `[VERIFIED: installer/wizard_app.py:1155]`.
- **New deletion code.** Removal stays `remove_proven`.

## Reuse Map (ponytail reuse pass)

| New thing the plan needs | Reuse (codegraph/grep evidence) | Why nothing new |
|--------------------------|----------------------------------|-----------------|
| `AppScreen.state_refreshed`/default `clear_transient` | `AppScreen.enter_view` hook `ui_common.py:338`; `CatalogScreen.clear_transient` `catalog_tui.py:702` | Extend; the catalog override stays |
| `request_refresh` worker | `_apply_daemon_default_worker` idiom `wizard_app.py:2696`; `run_live` `ui_common.py:42`; `VersionRefreshService.refresh`/`refresh_skills` (`version_status.py:1582`, `:1046`) | One new method; no new abstraction |
| Publish target | `_visible_app_screen` `wizard_app.py:2965` (generalise) | codegraph: only 1 helper of this shape |
| `mark_pending`, evidence store | `invalidate` `version_status.py:1121`, `_lock`/`_states` swap `:1760`, `_ConfigFacts.plus` `:629-645`, `Evidence.broken/notes` `:201-215` | Same lock, same swap, same fact vocabulary |
| Uninstall group/hints | `UninstallState` `enums.py:71`, `removal_hint`/`removal_label` `ownership.py:1602,1644`, `reverse_dependencies` `uninstall.py:341`, `health_cell` `catalog_tui.py:128`, `_HEALTH_DETAIL` `catalog_tui.py:258`, `ToolBrowser` sections, `_UninstallEntry` `wizard_app.py:864` | `classify_tools` takes an `installed` map and two closures; none works from `ToolState` (signature `uninstall.py:359-369`), so one small pure function is new |
| Removal vocabulary | `WORDS`, `RESULT_WORDS`, `summary_counts`, `retained`, `_count_line` (`session.py:134,146,247,227,203`), `render.outcome_word` | Add one disposition + one result |
| First error line | `session._first_line` `session.py:336` (2 callers; codegraph) | Make public and reuse; do not re-derive |
| Sanitising | `sanitize_log_line` `sanitize.py:13` (13 callers) | |
| Per-tool deletion | `remove_proven` `uninstall.py:532`, `remove_paths` `:508` | Called per tool in a loop |
| Mutation lock | `daemon_default_in_flight`/`toggle_in_flight` + the check-at-mutation-point pattern `wizard_app.py:1469, 2046-2053, 2167-2174`; `run_in_flight` `:2534` | Fold into one owner; same messages |
| Quit wait | `App.workers.wait_for_complete` (`worker_manager.py:172`) | |
| Policy live reads | `Policy.is_active/owned/missing_requires_now`, `policy_owned` (`uninstall.py:593`), `omz_plugins_policy` pattern (`policy.py:734`), `refresh_daemon_state` worker shape (`wizard_app.py:2008`) | |
| pnpm reasons | `_pnpm_group_facts` (`version_status.py:663`), `audit_node_globals`, `node_globals_guidance` sentences (`guidance.py:307`) | Reuse the sentences, drop the second renderer |
| Cursor/selection preservation | `ToolBrowser._rebuild` restores the cursor by row key (`tool_browser.py:193-221`) | Uninstall and tiers get it free via `reload`; Policies uses `update_cell` |
| Enter waiter (20 D-13) | `_await_state`/`_wait_worker`/`StateSettled` `execute_screen.py:534-575` | Replace the worker body with "register for next final publication"; keep the token contract and `StateSettled` |
| Test doubles | `tests/state_doubles.py`: `FrozenStateService.publish`, `seeded_service`, `pass_state`, `ScriptedUpdates`, `RunRecorder`; `tests/test_wizard_app.py::_app`/`_uninstall_inputs`/`_settle`; `tests/test_layout_80x20.py::_app`/`rows_of` | New: a held remover, a pass-counting service, the matrix harness |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Waiting for a thread worker at quit | A polling loop / `threading.Event` | `await self.workers.wait_for_complete([worker])` wrapped in `suppress(WorkerFailed, WorkerCancelled)` | Textual already tracks worker state; the suppress is the only missing piece |
| Coalescing refresh requests | A debounce timer | Two booleans on the event loop + handler restart | No timers, no locks |
| Per-tool pending signal | A parallel "in flight" set read by renderers | `mark_pending` dropping ids from the one published map | `health_cell(None)` is already `…` |
| Removal outcome words | A removal-only summary formatter | `WORDS`/`RESULT_WORDS`/`summary_counts` | Parity test covers one vocabulary |
| Row cursor / scroll preservation | Saving and restoring offsets | `ToolBrowser.reload` (key-based cursor restore) and `DataTable.update_cell` | Already keyed by row id |
| Path deletion / TOCTOU safety | New unlink logic | `remove_proven` (re-proof, quarantine rename, receipt retirement) | Phase 19 security work |
| Group classification from the registry | A second owner-hint table | `removal_hint`/`removal_label` + `ToolState.reasons` | Single owner vocabulary (`OWNER_LABELS`) |
| Markup escaping | `escape()` on every dynamic string | `Text` objects | Existing rule; a `[` in a path never restyles |

**Key insight:** every duplicated path in this phase exists because a screen kept a private copy of something `ToolState` or `AppScreen` could own. The plan's job is to delete the copies in the same wave that makes the owner real.

## Runtime State Inventory

The phase deletes parallel code paths; it renames no persisted string. Answered explicitly per category:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Version cache JSON (`default_cache_path()`), receipts under `~/.local/state/tools-installer/receipts/`: formats unchanged. The evidence store and `_pending` are in-memory only (session). | None. No migration. |
| Live service config | None. No external service holds the removed names (`OwnershipRefreshed`, `uninstall-ownership-refresh` are in-process message/worker names). | None |
| OS-registered state | None. Worker group names are Textual-internal. | None |
| Secrets/env vars | None. | None |
| Build artifacts | None. No package rename. `.claude/architecture.md` prose and `tests/test_docs.py` constants are the only "stale names" risk. | Update both in the same wave (P21) |

## Common Pitfalls

### P1: `show_view(BASE_VIEW)` in `on_mount` is a no-op
**What goes wrong:** the app launches with an empty root. **Why:** `current_view` starts as `BASE_VIEW` (`wizard_app.py:2630`) and `show_view` returns early on equality. **Avoid:** initialise `current_view` to a root sentinel; assert `app.screen is app.catalog` after `on_mount`. Tests read `current_view` 52 times; the post-mount value is unchanged. **Warning sign:** `len(app.screen_stack) == 1` after launch.

### P2: `exclusive=True` plus coalescing starts a second concurrent pass
Calling the `@work` method while one is running cancels the old worker's task but the thread keeps running, so two passes overlap. Guard with `_refresh_running`; restart only from the finish handler.

### P3: A mutation that does not `invalidate` re-reads the cached manager snapshot
`refresh()` reuses the manager snapshot for up to `MANAGER_STALE_AFTER` unless `invalidate()` cleared it (`version_status.py:1121-1141`). Install finish (`on_install_run_finished`) and `UpdateService.run` already invalidate; **Doctor `r` (pnpm global replay) and the removal handler do not** — add `invalidate(reason=...)` before `request_refresh()` there, or the pnpm inventory stays stale. A Policies toggle changes no tool fact and must **not** invalidate (that would blank every row to `…` for a policy flip).

### P4: `request_refresh` before the mutation completes
Order is mutation -> (invalidate) -> `request_refresh`. A removal handler must run it from `RemovalFinished`, not at worker start. A refused mutation (lock held, validation failure) starts no pass.

### P5: Failure leaves rows at `…` with no retry
Today a failed pass writes "tool state check failed: … leave and re-enter this view to retry" (`catalog_tui.py:456-458`), and re-entry started the pass. With D-05 entry never starts one, so that text becomes false and rows stay `…` until some mutation. Decide the retry affordance (O2) and update `test_refresh_error_shows_the_retry_copy` (`tests/test_catalog_tui.py:4207`).

### P6: Publish while a modal is on top
`self.screen` is the modal; D-06's literal rule skips the update. Use the topmost `AppScreen`. Test: open `ConfirmUninstall`, publish, dismiss, assert Uninstall already shows the new rows.

### P7: Pre-pass "Nothing to uninstall."
Before the first pass every `state_of` is `None`; `not self._entries`-style emptiness would announce an empty machine. Require all states known (or a published epoch) before writing the standing status.

### P8: `_flush_pending_warnings` overwrites an entry-written status
`show_view` calls it after `enter_view` and does `screen.status.set(" · ".join(pending), "warn")` (`wizard_app.py:2792-2796`), replacing any status `enter_view` wrote (e.g. Uninstall's startup read error). Merge instead of replace, or flush before `enter_view`.

### P9: `mark_pending` vs an in-flight pass
See Pattern 6. Add a test: start a pass, `mark_pending({"rg"})`, let the pass commit, assert `state_of("rg") is None`.

### P10: Lock released late or never
`RemovalFinished` must be posted in `finally:` and its handler must clear the lock first (the `on_daemon_default_applied` comment at `wizard_app.py:2736-2739` is the precedent). A crashed worker still releases it. Test with a remover that raises.

### P11: `Disposition.REMOVE` leaking into the install engine
`RUNNABLE`, `build_plan` and `execute_plan` iterate dispositions; REMOVE belongs to no plan. Keep it out of `RUNNABLE` and out of `_REVIEW_ORDER` consumers that assume plan rows, or document why it is harmless. `tests/test_render.py:671` and `tests/test_plan.py:558` parametrise over `Disposition`.

### P12: `app.query_one` only resolves against the default screen
Once the tiers are pushed, `app.query*` finds nothing `[VERIFIED: probe: "default-screen app.query: 1", "pushed-screen app.query: 0 | app.screen.query: 1"]`. `tests/test_wizard_app.py` already uses `app.screen.query_one`; `tests/test_catalog_tui.py` (5 sites: `:294,:343,:459,:1793,:1915`), `tests/test_ui_common.py` (4) and `tests/test_policies_e2e.py` (1) use `app.query_one` and need checking if their `app` is a `UnifiedApp`. The stack-depth assertion at `tests/test_wizard_app.py:3286-3290` (`len(app.screen_stack) == 1`) becomes 2 and must be rewritten.

### P13: Test doubles built without a service
`UnifiedApp(version_refresh=None)` is common in tests (`_app`, `test_layout_80x20`). `request_refresh()` must be a no-op then, and Uninstall must render something sensible with `state_of` always `None`. Give Uninstall a `state_of` provider that is `None`-safe and let the helper default to a `FrozenStateService`.

### P14: Quit during removal triggers a post-removal pass
The `RemovalFinished` handler runs while `_exit_after_removal` awaits; its `request_refresh()` would start a 4-6 s thread that delays process exit. Set `_quitting` before waiting and make `request_refresh` return when it is set.

### P15: `wait_for_complete` raises on a failed worker
See G6. Without `suppress(WorkerFailed, WorkerCancelled)` a crashed removal makes `q` raise instead of exiting.

### P16: Reading the Linux daemon's `is_active()` on the event loop
See Pattern 8. `PoliciesScreen.enter_view` must not call a blocking probe synchronously.

### P17: `DataTable.update_cell` without `update_width=True`
The DRIFT cell is 9 cells (`!`, space, `[drift]`); an old 7-cell column clips it. Re-check the 78-cell tests (`tests/test_layout_80x20.py`).

### P18: `DoctorScreen`/`PoliciesScreen` tests that rely on `on_mount` rendering
31 refs to `_DoctorHost`/`_ready_doctor` in `tests/test_wizard_app.py` mount a screen directly with no `show_view`. After D-04 they must call `screen.enter_view()` (or go through `UnifiedApp`). Rewrite the helper once.

### P19: Doctor audit end requesting a pass on every entry
See Pattern 9. Request only when the evidence set differs from the stored one.

### P20: `split_groups` has no home in `ToolState`
D-13 says one channel, but split detection needs group paths the cached `frozenset[str]` lacks (`pnpm_global_groups`, `pnpm_globals.py`). Either store it as evidence (recommended, O3) or Doctor loses a finding it has today.

### P21: Doctrine and grep tests
Update `.claude/architecture.md` (rule 2 prose naming `enter_view`/`show_view`, the Phase 20 `_await_state` paragraph "Phase 21's refresh owner replaces this helper's body") and `tests/test_docs.py` in the same wave. The R9 grep guard must also match **comments and docstrings**: `OwnershipRefreshed` appears in prose in `installer/uninstall.py`, `installer/wizard_app.py`, `installer/catalog_tui.py`, `installer/ownership.py`; scrub them.

### P22: The nav burst
Removing the catalog as the permanent bottom means a transient root between `pop` and `push`. Number keys are priority App bindings gated by `_navigable()`. The existing burst test (`tests/test_wizard_app.py:3278-3292`, `pilot.press("4","5","6","1")`) is the guard; keep it green and add a burst including `esc`. The app message loop awaits each handler, so the root is not observable by the next key `[ASSUMED]`.

## Code Examples

### Group + row text (illustrative; names are `[ASSUMED]`)
```python
# installer/uninstall.py
_BROKEN_TEXT = "reinstall it from the catalog to repair; nothing to remove here"
_UNKNOWN_TEXT = "owner unknown; nothing here can remove it safely"

def managed_hint(tool: Tool, state: ToolState) -> str:
    if state.health is Health.BROKEN:
        return _BROKEN_TEXT
    hint = removal_hint(state.ownership, tool.cmd)
    if hint is not None:
        return hint
    if state.ownership.owner == "unknown":
        return _UNKNOWN_TEXT
    return " · ".join(state.reasons)          # installer-owned, unproven: UNPROVEN_NOTE is first
```

### Held remover for the responsiveness test
```python
class HeldRemover:                                # tests/screen_family.py  [ASSUMED]
    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = threading.Event()
        self.calls: list[UninstallDecision] = []
    def __call__(self, decision: UninstallDecision) -> UninstallResult:
        self.calls.append(decision)
        self.started.set()
        assert self.release.wait(timeout=10)       # bounded: never hang the suite
        return UninstallResult(...)
```
Drive it with `pilot.press`, `await pilot.pause()`, assert navigation works and a second `enter` is refused, `release.set()`, then wait on `app.workers.wait_for_complete()`.

### Pass-counting spy (R2, "entering starts no pass")
Wrap `service.refresh` in a counting subclass of the existing `FrozenStateService` (`tests/state_doubles.py:~230`); assert the count is unchanged across `show_view` to each of the six views, and exactly +1 after each mutation source.

### Call-order test (R1)
Spy `leaving.clear_transient`, `UnifiedApp.pop_screen`/`push_screen` and `target.enter_view` into one list; assert `["clear", "pop", "push", "enter"]` for each of the six views and an empty list when pressing the current view's key.

## State of the Art

| Old approach | Current approach | When | Impact |
|--------------|------------------|------|--------|
| Tier is the Textual default screen, never pushed | Root is empty, every view pushed | this phase | `app.query*` no longer reaches the tier |
| Per-tier refresh workers + `OwnershipRefreshed` fan-out | One app worker + direct `state_refreshed()` | this phase | Deletes 3 workers, 2 messages, ~49 test refs to rewrite |
| `classify_tools` + `UninstallInputs.rows` | `ToolState` projection | this phase | `UninstallInputs` shrinks to env predicates + remover + terminal sync |

**Deprecated/outdated after this phase:** `UninstallInputs.rows/invalidate/refresh`, `ToolRow`, `OwnerHint`/`OwnerLabelHint`, `setup.py:843-902` closures, `UninstallScreen._resync/_set_status/applied` gating, `CatalogScreen.version_refreshing/skill_refreshing/_state_line`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Uninstall group can be derived from `health`/`removable.removable`/`receipt`/`ownership` without adding `level`/`hint` to `RemovalPlan` | Patterns 4, G1 | If the user expects the Phase 22 contract early, a later rewrite; low |
| A2 | Handler-side restart (flags on the loop) satisfies D-05's "worker runs exactly one more pass" | Pattern 2 | Wording drift only; behaviour identical |
| A3 | Installer-owned but unproven (script installs, `_own_script_install`'s case) gets `UNPROVEN_NOTE`/`state.reasons` as hint after the helper is deleted | Pattern 4, O1 | The old sentence "installed by its own installer — remove it with that installer's own uninstaller" disappears; copy needs user sign-off |
| A4 | A pnpm-tracked package whose command is gone is a MISSING row with a note, not BROKEN | Pattern 9 | SPEC R8 wording ("shows `!`") could be read as requiring BROKEN for this case |
| A5 | Smoke-check failures become `broken` facts (tier `!`, update refused) | Pattern 9 | Changes health for tools that previously only warned in Doctor |
| A6 | `split_groups` is carried as an evidence note on the declaring tool | P20, O3 | Doctor loses the finding if rejected |
| A7 | Policies reads cheap `is_active` synchronously and the cache-backed daemon through a worker | Pattern 8 | A purely synchronous read could freeze the UI up to the probe timeout |
| A8 | The mutation lock also covers `u` (update in flight) so a removal cannot start during an update | Pattern 7, O4 | SPEC lists only the reverse direction; an update and a removal could race on one tool |
| A9 | `current_view` root sentinel is `""` | P1 | Tests asserting the pre-mount value |
| A10 | Failed interactive removals do not feed `UnifiedApp.outcomes`/the exit code | Pattern 5 | Exit code semantics differ from the user's expectation |
| A11 | `request_refresh` after an install close only when a run happened (`result is not None`) | Pattern 2 sources | An extra or a missed pass on cancel |
| A12 | Rapid nav burst is safe with a transient root | P22 | Dropped keys in fast sequences |
| A13 | `Disposition.REMOVE` is not a plan row and stays out of `RUNNABLE` | Pattern 5 | Install engine mis-dispatch |

## Open Questions

1. **Hint for installer-owned, unproven tools after `_own_script_install` goes (O1)**
   - Known: `removal_hint` returns `None` for `installer` except script installs, which `_own_script_install` special-cases (`ownership.py:1591-1599`, used at `:1620,:1666`).
   - Unclear: the user-facing sentence for a script install until Phase 22 ships `remove` recipes.
   - Recommendation: render `state.reasons` joined (carries `UNPROVEN_NOTE`) plus the `remove it yourself: <paths>` suffix; do not name a manager. Ask the user only if they want the old sentence kept.
2. **Retry after a failed pass (O2)**
   - Known: entry must start no pass (SPEC prohibition + spy test).
   - Unclear: what the status line says and what retries.
   - Recommendation: `tool state check failed: {error} — the next change retries it`, and let the next `request_refresh()` (any mutation) retry. No new key.
3. **Where `split_groups` lives (O3)** — see P20; recommend evidence store.
4. **Does the lock cover `u`? (O4)** — see A8; recommend yes (begin in `action_update_tool`, end in `on_tool_updated`, reuse the existing `update already in flight` copy).
5. **Pre-existing guards' copy** — `_DAEMON_DEFAULT_IN_FLIGHT_MESSAGE` and `_TOGGLE_IN_FLIGHT_MESSAGE` (`wizard_app.py:2444-2447`) stay for their own cases (UI-SPEC); the lock owns one removal string only.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all commands | ✓ | 0.11.28 `[VERIFIED: uv --version]` | — |
| Python | runtime/tests | ✓ | 3.12.12 `[VERIFIED: uv run --no-sync python --version]` | — |
| textual / rich / pytest stack | tests, screens | ✓ | 8.2.7 / pytest 9.0.3 `[VERIFIED]` | — |
| CodeGraph | research only | ✓ | `codegraph sync` ran clean | grep |
| Container runtime (real removal e2e) | `scripts/container-e2e-verify.sh` | not probed | — | UAT only; not needed for unit/pilot tests. Never run on the host. |

No missing dependency blocks planning. `make setup/fix/uninstall` must not be run (AGENTS.md).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3, `asyncio_mode = "auto"`, pytest-xdist, pytest-cov `fail_under = 90` `[VERIFIED: pyproject.toml:47-58]` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) |
| Quick run command | `uv run pytest -n auto tests/test_screen_family.py tests/test_tool_browser.py tests/test_uninstall.py tests/test_session.py tests/test_plan.py -q --no-cov` |
| Screen run command | `uv run pytest -n auto tests/test_wizard_app.py tests/test_catalog_tui.py tests/test_policies_e2e.py tests/test_layout_80x20.py tests/test_execute_screen.py -q --no-cov` (the first four ran in ~15 s with `-n auto` this session) |
| Full suite command | `make validate && make test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| UI-01 | clear -> pop -> push -> enter per view; current-key no-op | pilot | `uv run pytest -n auto tests/test_screen_family.py -k "call_order or current_view" -q --no-cov` | ❌ Wave 0 |
| UI-01 | matrix: {install close, `u` x3 tiers, removal, Policies toggle, Doctor `r`} x {system,user,ai,Uninstall,Policies,Doctor}, next entry and visible | pilot (parametrised) | `... -k matrix` | ❌ Wave 0 |
| UI-01 | entering a view starts zero passes; mutation ends with exactly one; coalescing; superseded pass discarded | unit+pilot | `... -k "no_pass_on_entry or coalesce"` | ❌ Wave 0 |
| UI-02 | first-entry status kept; leave clears; re-entry shows none; publish never clears | pilot | `... -k status_lifecycle` | ❌ Wave 0 |
| UI-03 | fixtures per group; unknown owner shows no manager/argv; BROKEN repair text; empty machine shows only `nothing to do`; `yourself` suffix kept; Health column | unit (`uninstall_group`) + pilot | `uv run pytest -n auto tests/test_uninstall.py tests/test_wizard_app.py -k "uninstall" -q --no-cov` | ✅ extend (rewrite `_uninstall_inputs`) |
| UI-05 | held remover: UI responsive, navigation works, second removal and every mutation refused, rows `…` only for removed ids, afterwards `nothing to do`, `○` on tiers, ban OFF in Policies | pilot | `uv run pytest -n auto tests/test_screen_family.py -k removal -q --no-cov` | ❌ Wave 0 |
| UI-05 | quit during removal waits; crashed remover still exits and releases the lock | pilot | `... -k "quit or crashed"` | ❌ Wave 0 |
| UI-05 | `mark_pending` vs in-flight pass | unit | `uv run pytest tests/test_version_status.py tests/test_tool_health.py -k pending -q --no-cov` | ✅ extend |
| UI-05 | `removed`/`remove failed` in `WORDS` parity; `retained` keeps failed | unit | `uv run pytest tests/test_plan.py tests/test_session.py tests/test_render.py -q --no-cov` | ✅ extend |
| UI-06 | `watch` install unblocks docker tweak; owned+inactive shows DRIFT; macOS no plist reads OFF; no blocking probe on the loop | unit+pilot | `uv run pytest -n auto tests/test_policy_tweaks.py tests/test_policy_linux_daemon.py tests/test_policy_daemon.py tests/test_wizard_app.py tests/test_policies_e2e.py -k "policy or policies" -q --no-cov` | ✅ extend |
| UI-07 | `a` inert; dangling pnpm shim shows `!`+reason on tier and in Doctor; link pick re-renders Doctor; evidence change requests one pass, unchanged requests none | pilot | `uv run pytest -n auto tests/test_wizard_app.py tests/test_pnpm_globals.py tests/test_tool_health.py -k "doctor or pnpm or shim" -q --no-cov` | ✅ extend |
| UI-08 | selected -> unselectable pruned on reload; `selected_ids`/`Accepted` filter | unit+pilot | `uv run pytest -n auto tests/test_tool_browser.py tests/test_catalog_tui.py -k "prune or selectable" -q --no-cov` | ✅ extend |
| R9 | grep guard: none of `OwnershipRefreshed`, `_pending_status`, `_own_script_install` (and the other deleted names) in `installer/`, comments included | unit | `uv run pytest tests/test_screen_family.py -k forks -q --no-cov` | ❌ Wave 0 |
| Layout | Uninstall/Policies/status lines <= 78 cells at 80x20; status stays on its row | pilot | `uv run pytest tests/test_layout_80x20.py -q --no-cov` | ✅ extend |
| Docs | architecture.md records Phase 21 mechanisms | unit | `uv run pytest tests/test_docs.py -q --no-cov` | ✅ extend (`_PHASE_21_REQUIRED`) |

### Sampling Rate
- **Per task commit:** the Quick command (no or few Textual pilots) for the touched module, `--no-cov`.
- **Per wave merge:** Quick + Screen commands, then `make validate && make test`.
- **Phase gate:** `make validate && make test` green on the exact tree; coverage not below the floor.

### Wave 0 Gaps
- [ ] `tests/screen_family.py` — held remover, pass-counting `FrozenStateService`, matrix observables per target view, call-order recorder (covers UI-01, UI-02, UI-05)
- [ ] `tests/test_screen_family.py` — call order, matrix, status lifecycle, lock, quit, forks grep (covers UI-01, UI-02, UI-05, R9)
- [ ] Rewrite `_uninstall_inputs`/`_app`/`_DoctorHost` helpers in `tests/test_wizard_app.py` once (covers the 84 + 31 call sites)
- [ ] `FrozenStateService`: support `mark_pending` and evidence in the double (`tests/state_doubles.py`)
- [ ] `_PHASE_21_REQUIRED` in `tests/test_docs.py` (written with the architecture.md change)

### Matrix design note
Per-target observables: tiers/Uninstall/Doctor read `state_of` (Health cell, group, reasons); Policies reads `active_state`, the Requires cell, DRIFT; Uninstall also reads environment predicates (`ban_names`, `has_path_block`, `tweak_ids`) which a Policies toggle changes. Use `FrozenStateService.publish` between steps; assert "next entry" by `show_view` and "immediately" by publishing while the target is on top.

## Security Domain

### Applicable ASVS Categories (level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no (single local user) | Zero sudo is structural (AGENTS.md) |
| V5 Input Validation | yes | `Text` (never markup) + `sanitize_log_line` for tool ids, paths, reasons, errors; fixed strings for unknown-owner and BROKEN copy |
| V6 Cryptography | no new use | Receipt re-hash stays in `receipts`/`remove_proven` |
| V12 Files/Resources | yes | Deletions only through `remove_proven` (re-proof with `verify=True`, quarantine rename, receipt retired only when all proven paths are gone) |
| V13 API/Concurrency (race conditions) | yes | One mutation lock; `mark_pending` filtered at commit; flags on the event loop |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Markup/ANSI injection through a path, id or error line (`[red]x[/]`, `\x1b[31m`) | Tampering | `Text` + `sanitize_log_line`; held-out test per UI-SPEC |
| Removal of an unproven artifact (preview is not a permission slip) | Tampering | `remove_proven` re-proves at delete time; unknown owner never offered, never given an argv |
| Naming a manager/command for an unknown owner | Information integrity | Fixed sentence; prohibition test |
| Concurrent mutation (removal vs install/update/toggle) corrupting one tool | Tampering / DoS | Single `mutation_in_flight`; check at open and at the mutation point |
| Quit during removal leaving a `.tools-installer.rm` quarantine sibling | Tampering | Quit waits (D-10); `plan_removal` already lists leftovers (`_quarantined`) |
| Stale publish re-showing a removed tool as present | Integrity | `mark_pending` commit filter + epoch fail-closed `state_of` |
| Refresh flood (toggle spam) | DoS | Coalescing: at most one pass running, one queued |
| Evidence store poisoning | Tampering | In-process only; written from the Doctor worker; smoke argv comes from the registry, not user input (unchanged) |

## Sources

### Primary (HIGH confidence)
- In-repo code read this session: `installer/wizard_app.py`, `ui_common.py`, `catalog_tui.py`, `tool_browser.py`, `uninstall.py`, `app.py`, `policy.py`, `session.py`, `version_status.py`, `pnpm_globals.py`, `guidance.py`, `ownership.py`, `execute_screen.py`, `setup.py`; `tests/state_doubles.py`, `tests/test_wizard_app.py` helpers, `tests/test_docs.py`, `tests/test_layout_80x20.py`.
- Planning artifacts: `21-CONTEXT.md`, `21-SPEC.md`, `21-UI-SPEC.md`, `20-RESEARCH.md` (format), `19-CONTEXT.md` D-10, `.planning/research/2026-10-13-target-architecture.md` §2/§4.3/§7.
- Textual 8.2.7 source in `.venv`: `worker.py:219,423-455`, `worker_manager.py:172-181`, `app.py:3465,3737`, `widgets/_data_table.py:871-878`.
- Probes run in the scratchpad (stack/mount behaviour, `app.query` scope).

### Secondary / Tertiary
- None. No web search was needed; no external API is involved. jev-fast-decision was not used (advisory, disabled by default, and every question here was answerable from code).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency.
- Architecture: HIGH for the mechanisms (all reuse sites read); MEDIUM for the thirteen assumptions above.
- Pitfalls: HIGH — each tied to a read line or a probe.

**Research date:** 2026-10-18
**Valid until:** 2026-11-17 (stable; revalidate line numbers after any merge touching `wizard_app.py`)
</content>
