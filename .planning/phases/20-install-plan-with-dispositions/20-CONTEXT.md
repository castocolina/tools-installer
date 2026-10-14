# Phase 20: Install plan with dispositions - Context

**Gathered:** 2026-10-14 (assumptions mode, `--analyze --all --batch`, jev screening, best-over-easy)
**Status:** Ready for planning

<domain>
## Phase Boundary

Before anything runs, the user sees what will happen to each selected and dragged tool. One `InstallPlan` has one disposition and one reason per row. The TUI and headless runs execute that same plan with one engine and report outcomes in the review's words.

The WHAT is locked in `20-SPEC.md` (R1–R9). R3 was clarified in this session: a dragged dependency that is outdated or misconfigured is "skipped — already present". This file locks the HOW.

Out of scope:
- `ToolState`, `Health` and receipts are built in 19 and consumed here.
- The Uninstall/Policies/Doctor screens (21), script recipes (22), hook re-registration (23), and actually migrating an off-policy tool (not planned).

**Prerequisites:** 17 (D-07 worker except, D-08 interim exit-code fields, D-12 `_build_app` builds `ExecuteInputs`) and 19 (`state_of`, `Health`, the single refresh owner, receipts, typed `ConfigStep`s from 19 D-20). As of 2026-10-14 neither has landed; today's code is from before 17.
</domain>

<decisions>
## Implementation Decisions

**Decision rule (user, 2026-10-13):** choose the best design, not the easiest. The analyzer's easy options were rejected wherever they left a second ordering, vocabulary, exit-code rule, engine or refresh path.

### Plan model (R1, R3, R9)
- **D-01:** `Disposition` (StrEnum), `PlanRow(tool_id, disposition, reason, requested_by)` and a pure `build_plan(selected, catalog, state_of, platform, *, reinstall: frozenset[str]) -> list[PlanRow]` live in `installer/session.py`, next to `order_for_install` (`:116`).
  - Order comes only from the unchanged `deps.resolve_dependencies`, with `is_installed = present and not BROKEN` built from `state_of`.
  - There is no second sort.
  - `build_plan` makes no network calls; it reads only published state.
- **D-02:** A dragged dependency gets exactly one row, with `requested_by` set to the first selected tool that pulled it in. That id is recorded when the existing `collect()` (`deps.py:59-72`) first reaches the dependency.
  - The row is rendered indented under that tool.
  - It is listed once even when several selected tools need it.
- **D-03 (user):** Dispositions follow target-architecture §3.1.
  - Dragged missing → "will install" (reason "needed by X").
  - Dragged broken → "will repair".
  - Dragged outdated or misconfigured → "skipped — already present", with the health reason visible.
  - Only a direct selection updates or reconfigures a tool. A run never mutates a tool the user didn't pick, unless the dependent can't work without it.
  - SPEC R3 wording was amended to match.
- **D-04:** Every id that `resolve_dependencies` reaches gets a row. The silent skip at `deps.py:111` becomes a BLOCKED row whose reason is the existing warning text, and the dependent shows "blocked — needs X".
  - A sudo-needing repair or update is BLOCKED with its reason, never escalated.
  - `render_dependency_notice` is no longer a separate print.
- **D-05 (user):** Unavailable (dim) rows are **not selectable**: the catalog adapter's `selectable` (today always `True`, `tool_browser.py:76`) returns false when health is UNAVAILABLE.
  - Space and `a` (`action_select_all`, `tool_browser.py:300-308`) both use that one predicate.
  - The focused-row detail explains why.
  - This also keeps a never-runnable row from staying in the retained selection forever.

### Execution and outcomes (R4, R5, R6)
- **D-06 (best, not easy):** RECONFIGURE runs the typed `ConfigStep`s from `ToolState.unconfigured` (19 D-20): skill install for a harness, terminal sync, or installing the missing pnpm group members.
  - The review lists the steps.
  - The generic `reapply_post_install` (`engine.py:200-216`) is not used for RECONFIGURE, because it re-runs registry actions and fixes none of 19's signals.
  - Hook re-registration stays in Phase 23. jev: TypeSafe 0.95.
- **D-07:** `execute_plan(rows, inputs) -> list[RowOutcome]` in `session.py` takes the body of `ExecuteScreen`'s worker (`execute_screen.py:573-671`), with 17 D-07's `except Exception`. The TUI worker and headless both call it.
  - INSTALL, REPAIR and REINSTALL go through `engine.install_tool(repair=True)`, using `_with_repair`'s set (`:239-276`) generalized to `force_ids`.
  - UPDATE goes through the unchanged `UpdateService.run`.
  - SKIP and BLOCKED rows never run.
- **D-08 (best, not easy):** `execute_plan` returns **one `RowOutcome` per plan row**, including skipped and blocked rows. `result` is one of `{done, failed, mismatch, dependency_failed, not_attempted, crashed, skipped, blocked}`.
  - The summary counts, the exit code and the retained selection are pure functions of that one list.
  - One `WORDS` table in `session.py` supplies every review, summary and headless word. The parity test iterates over it.
  - The legacy `Summary`/`summarize()` (`session.py:191-217`) and `render_summary`'s own words (`render.py:60-79`) are deleted. 17 D-08's interim tuples map onto `RowOutcome` and then go away. jev: TypeSafe 0.99 (Laya leaned toward extending `Summary` at 0.75, but that keeps two vocabularies).
- **D-09:** Exit code: 1 when any row's result is failed, mismatch, dependency_failed, not_attempted or crashed; otherwise 0. Skipped and blocked rows never change it.
  - This is the only exit-code rule; it replaces the `setup.py:1278,1509` checks.
- **D-10:** After a run, rows that ended failed, mismatch, dependency_failed, not_attempted, crashed or blocked stay selected, and done and skipped rows are cleared. This replaces the unconditional `self._staged.clear()` at `wizard_app.py:2797`.
  - `esc` before the run posts no decision, so the whole selection is kept.
  - A worker crash marks every unfinished row crashed or not_attempted, and those stay selected.
- **D-11:** The terminal-sync trigger is "any row other than SKIP or BLOCKED ran", computed from the outcomes. This replaces `_install_state_changed` (`wizard_app.py:2487,2857,2960`), which missed update, repair and reconfigure runs.

### Headless (R6)
- **D-12:** `app.run_wizard` (`app.py:127-197`) runs one synchronous refresh pass, then `build_plan`, then `render_plan`, then confirms unless `--yes`, then `execute_plan`.
  - `render_plan` in `render.py` replaces `render_audit` (`:48-57`). `installer/audit.py` and the dead branch at `render.py:55` are deleted.
  - Headless never passes `reinstall`, so `--yes` can never turn a skipped row into a reinstall.

### Waiting for state (R7)
- **D-13 (best, not easy):** Enter waits on the **single refresh owner** (19 D-02 / target-architecture §2) and never starts its own refresh.
  - When any planned row's `state_of` is `None`, Enter registers a waiter for the next publication, triggering the owner worker if the generation is stale and the worker is idle.
  - On publication, the plan is rebuilt from published state and then executed.
  - `esc` bumps a wait token. A publication whose captured token is out of date is ignored, so a late publication can never start a run.
  - There is no timeout.
  - A refresh started from the screen would run a second pass beside the owner. jev: TypeSafe 1.0.

### `r`, wording, width (R2, R8)
- **D-14:** The review screen owns `reinstall: set[str]` and passes it into every `build_plan` call (after Enter, after a wait, after an `r` toggle).
  - `r` changes the set only on rows that show "(r: reinstall)", meaning installer-owned by receipt or adoption.
  - On any other row it does nothing and the reason stays.
  - `r` doesn't collide with the catalog's `accept_recommends` binding (`catalog_tui.py:317`), because only the top screen dispatches.
- **D-15:** Both "moving it there is not available yet" strings (`catalog_tui.py:923`, `update.py:296`) lose that clause in place and keep the `declared`/`real` labels already computed there.
  - A literal grep test guards it.
- **D-16:** `render_plan` puts dragged rows behind a short indent. The 78-column checks reuse the existing `Console(width=80)` capture (`execute_screen.py:1051-1057`) and the `len(plain) <= 78` assertion style.

### Added by later phases
- **D-17 (from Phase 22 D-12, 2026-10-14):** `Disposition.MANUAL` ("you run: `<exact command>`") applies to a native dnf/apt/pacman install method, or a script method whose `writable_prefix` is not writable. It is decided by the shared `needs_manual` predicate. `RowOutcome` gains the result `manual`, which keeps the row selected and doesn't change the exit code. BLOCKED keeps the meaning "nothing the installer can do".

### Claude's Discretion
- Plan and wave order. Suggested:
  1. `Disposition`/`PlanRow`/`build_plan` plus the G cases A–I.
  2. `RowOutcome`/`WORDS`/`execute_plan`.
  3. Moving the TUI review and worker onto them.
  4. Headless.
  5. Wait-for-state.
  6. `r`, `a`/selectable, wording and width.
- The exact `WORDS` keys and the indent marker.

### Folded Todos
None.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/20-install-plan-with-dispositions/20-SPEC.md`: locked R1–R9 (R3 amended 2026-10-14)
- `.planning/research/2026-10-13-target-architecture.md`: §3 (Disposition, PlanRow, plan), §3.1 (disposition table), §3.2 (execution, outcomes, exit code, retained selection, deletes), §9.2 (O7, O8, O9)
- `.planning/phases/17-stop-the-bleeding/17-CONTEXT.md`: D-07, D-08, D-12
- `.planning/phases/19-one-tool-state-with-health-plus-receipts/19-CONTEXT.md`: D-02/D-03 single owner and `state_of`, D-04, D-20 typed `ConfigStep`s
- `.planning/REQUIREMENTS.md`: PLAN-01..08
- `.claude/architecture.md`, `AGENTS.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `session.order_for_install` (`:116`), `run_installs`; `deps.resolve_dependencies`/`collect` (`deps.py:59-72`)
- `execute_screen._with_repair` (`:239-276`), worker body (`:573-671`), `_render_captured` (`:1051-1057`)
- `engine.install_tool(repair=)`; `update.UpdateService.run` (`:442-507`)
- `tool_browser.BrowserAdapter.selectable` (`:76`), `action_select_all` (`:300-308`)

### Established Patterns
- `setup.py` is wiring only; decisions live in `installer/` (`.claude/architecture.md:20`).
- Epoch/token compare and fail closed, as in `version_status.py:510-529`.
- 78-column budget assertions in `tests/test_catalog_tui.py`.

### Integration Points
- `build_plan` ← the review screen, headless `run_wizard`, and `a`/Enter
- `execute_plan` → `install_tool`, `UpdateService`, the `ConfigStep` executors
- `RowOutcome` list → summary, exit code (`setup.py`), retained selection (`wizard_app.py:2797`), terminal-sync trigger
- The refresh owner's publication → the Enter waiter
</code_context>

<specifics>
## Specific Ideas

- The acceptance anchors are the G probe cases A–I (SPEC R1) as parametrized `build_plan` tests on all three tiers.
</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- GSD per-repo installs (0.6) and the pi repair/sync (0.6): outside this phase.
- Dangling pnpm shims in Doctor (0.2): Phase 21.
- Playwright Flatpak Chrome (0.2): shell tweak, unrelated.
</deferred>
