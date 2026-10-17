# Phase 20: Install plan with dispositions - Research

**Researched:** 2026-10-17
**Domain:** In-repo Python/Textual refactor: one pure install plan (`build_plan`), one executor (`execute_plan`), one vocabulary (`WORDS`), consumed by the TUI review screen and the headless `--all`/`--categories` route. No new packages, no external services.
**Confidence:** HIGH for the code map and hazards (every location below was read this session); MEDIUM for the six design recommendations tagged `[ASSUMED]` (they need the planner or user to confirm).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Decision rule (user, 2026-10-13):** choose the best design, not the easiest. The analyzer's easy options were rejected wherever they left a second ordering, vocabulary, exit-code rule, engine or refresh path.

#### Plan model (R1, R3, R9)
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

#### Execution and outcomes (R4, R5, R6)
- **D-06 (best, not easy):** RECONFIGURE runs the typed `ConfigStep`s from `ToolState.unconfigured` (19 D-20): skill install for a harness, plugin dedupe/enable (19 D-18 fix step: enable canonical first, then remove copies), project-pack global uninstall (19 D-21), terminal sync, or installing the missing pnpm group members.
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

#### Headless (R6)
- **D-12:** `app.run_wizard` (`app.py:127-197`) runs one synchronous refresh pass, then `build_plan`, then `render_plan`, then confirms unless `--yes`, then `execute_plan`.
  - `render_plan` in `render.py` replaces `render_audit` (`:48-57`). `installer/audit.py` and the dead branch at `render.py:55` are deleted.
  - Headless never passes `reinstall`, so `--yes` can never turn a skipped row into a reinstall.

#### Waiting for state (R7)
- **D-13 (best, not easy):** Enter waits on the **single refresh owner** (19 D-02 / target-architecture §2) and never starts its own refresh.
  - When any planned row's `state_of` is `None`, Enter registers a waiter for the next publication, triggering the owner worker if the generation is stale and the worker is idle.
  - On publication, the plan is rebuilt from published state and then executed.
  - `esc` bumps a wait token. A publication whose captured token is out of date is ignored, so a late publication can never start a run.
  - There is no timeout.
  - A refresh started from the screen would run a second pass beside the owner. jev: TypeSafe 1.0.

#### `r`, wording, width (R2, R8)
- **D-14:** The review screen owns `reinstall: set[str]` and passes it into every `build_plan` call (after Enter, after a wait, after an `r` toggle).
  - `r` changes the set only on rows that show "(r: reinstall)", meaning installer-owned by receipt or adoption.
  - On any other row it does nothing and the reason stays.
  - `r` doesn't collide with the catalog's `accept_recommends` binding (`catalog_tui.py:317`), because only the top screen dispatches.
- **D-15:** Both "moving it there is not available yet" strings (`catalog_tui.py:923`, `update.py:296`) lose that clause in place and keep the `declared`/`real` labels already computed there.
  - A literal grep test guards it.
- **D-16:** `render_plan` puts dragged rows behind a short indent. The 78-column checks reuse the existing `Console(width=80)` capture (`execute_screen.py:1051-1057`) and the `len(plain) <= 78` assertion style.

#### Added by later phases
- **D-17 (from Phase 22 D-12, 2026-10-14):** `Disposition.MANUAL` ("you run: `<exact command>`") applies to a native dnf/apt/pacman install method, or a script method whose `writable_prefix` is not writable. It is decided by the shared `needs_manual` predicate. `RowOutcome` gains the result `manual`, which keeps the row selected and doesn't change the exit code. BLOCKED keeps the meaning "nothing the installer can do".

#### Ledger amendments (from Phase 19 planning, 2026-10-16; RUN-LEDGER)
- **Ledger L-19-28 (inbound):** Phase 19's `ConfigStep` kind `pnpm_group_install` carries an empty argv; Phase 20's plan/reconfigure execution must dispatch it to `executors.execute` on the declaring tool's first node method (the whole pinned group with `--allow-build`), like `terminal_sync` is dispatched by kind. Phase 20 also executes the per-repo skill install command Phase 19 builds (L-19-07).

### Claude's Discretion
- Plan and wave order. Suggested:
  1. `Disposition`/`PlanRow`/`build_plan` plus the G cases A–I.
  2. `RowOutcome`/`WORDS`/`execute_plan`.
  3. Moving the TUI review and worker onto them.
  4. Headless.
  5. Wait-for-state.
  6. `r`, `a`/selectable, wording and width.
- The exact `WORDS` keys and the indent marker.

### Deferred Ideas (OUT OF SCOPE)
- GSD per-repo installs (0.6) and the pi repair/sync (0.6): outside this phase.
- Dangling pnpm shims in Doctor (0.2): Phase 21.
- Playwright Flatpak Chrome (0.2): shell tweak, unrelated.
- Out of scope per CONTEXT boundary: `ToolState`/`Health`/receipts (built in 19, consumed here); Uninstall/Policies/Doctor screens (21); script recipes (22); hook re-registration (23); actually migrating an off-policy tool (not planned).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLAN-01 | The review lists every selected and dragged tool with its disposition and reason | `build_plan` over a `Resolution` that exposes the full closure (Pitfall 1), `render_plan` with dragged rows grouped under their requester, G cases A-I as parametrized tests on three tiers |
| PLAN-02 | A current installer-owned tool is skipped unless `r` is pressed, which shows "will be reinstalled" | `reinstall` set owned by `ExecuteScreen`; `PlanRow.can_reinstall`; eligibility rule and the G21 copy fix (Pitfall 9) |
| PLAN-03 | Broken tool → repair, misconfigured → reconfigure, including dragged dependencies | Disposition table (Standard Stack), `ConfigStep` executors (Pitfall 4, 5), BROKEN-by-drift decision (Open Question 2) |
| PLAN-04 | The summary counts outcomes with the same words as the review | `WORDS` + `summary_counts(outcomes)`; the e2e harness parses the old summary line (Pitfall 11) |
| PLAN-05 | Failed/blocked/not-attempted stay selected, done/skipped clear, `esc` before start keeps the selection | `retained(outcomes)` pure function; dismiss result carries outcomes; in-place `intersection_update` on the shared `_staged` set |
| PLAN-06 | Headless `--all`/`--categories` uses the same plan and engine; exit code from outcomes | `run_wizard` rewrite; headless has NO `VersionRefreshService`/`UpdateService` today (Pitfall 7); `exit_code(outcomes)` |
| PLAN-07 | Rows show "checking…" and Enter waits for the refresh | Wait worker on the service single-flight (Pitfall 6, Open Question 4) |
| PLAN-08 | No screen promises an off-policy migration | Two in-place string edits, a grep test over `installer/`, and three test files that pin the old text |
</phase_requirements>

## Summary

Phase 20 replaces three parallel decision paths with one. Today the TUI review classifies the selection ad hoc in `ExecuteScreen._classify_selection`/`_update_targets`/`_preflight_prompt`; the worker runs installs, then updates, then a generic `post_install` re-apply; the summary comes from `Summary`/`summarize`/`fold_run`; headless (`app.run_wizard`) has its own audit table and its own engine call and has no update capability at all. All of that collapses into `build_plan` (pure) -> `render_plan` -> `execute_plan` (returns one `RowOutcome` per row) with `WORDS`, `exit_code`, `retained` and `ran_anything` as pure functions of the outcome list.

Phase 19 has landed and the code differs from what CONTEXT cites. Line references in CONTEXT/SPEC are from before Phases 17 and 19 and are wrong now (table in State of the Art). More importantly, three assumptions in CONTEXT do not hold in today's tree: (1) there is no app-level "single refresh owner" yet (Phase 21 D-05 builds `UnifiedApp.request_refresh`; each `CatalogScreen` still runs its own refresh worker and the only single-flight is inside `VersionRefreshService.refresh`), so D-13 must be built on the service's single-flight; (2) `deps.resolve_dependencies` removes every present tool from `Resolution.order`, so D-01's "order comes only from the unchanged resolver" cannot place UPDATE/RECONFIGURE/REINSTALL/SKIP rows without an additive change to `Resolution`; (3) `Runner` has no `cwd`, but two `ConfigStep` kinds carry one. D-05 (unavailable rows not selectable) is already done by Phase 19.

The size is large and mostly deletion plus test porting: `Summary`, `summarize`, `fold_run`, `run_installs`, `audit.py`, `render_audit`, `render_summary`, `render_dependency_notice`, `reapply_post_install`, `_classify_selection`, `_update_targets`, `_preflight_prompt`, the three progress lists and `_install_state_changed` all go. About 100 tests in `tests/test_execute_screen.py` (114 tests, 97 `ExecuteScreen(` constructions), 22 `ExecuteInputs(` sites in `tests/test_wizard_app.py`, 30 `run_wizard` sites in `tests/test_app.py` and 34 `Summary` sites in `tests/test_setup.py` need porting.

**Primary recommendation:** Build bottom-up in the CONTEXT order, but make the first wave also change `Resolution` (additive `closure`, `blocked`, `requested_by`) and add the `update_refusal` predicate, because every later wave depends on them. Keep `ExecuteScreen(ids, inputs)` constructor-stable to limit test churn, make the plan the single source for both the review and the progress panel, and delete each superseded path in the same wave that replaces it (`.claude/architecture.md` rule 5).

## Project Constraints (from CLAUDE.md / AGENTS.md)

`./CLAUDE.md` does not exist; `./AGENTS.md` and its linked `.claude/*.md` rules apply with the authority of locked decisions. [VERIFIED: AGENTS.md read this session]

- **uv owns the environment.** Never `pip`, `poetry`, `conda`, hand-rolled venv. Targeted tests: `uv run pytest <file> -q --no-cov -n 0`.
- **English only** for identifiers, comments, docstrings, log lines, commit messages.
- **Never bypass a quality gate**: no `# noqa`, `# type: ignore`, `# nosec`, vulture whitelist, `skip`/`xfail`, lowered coverage floor (`fail_under = 90`). pyright is strict; vulture runs on `installer/` at `min_confidence = 80`.
- **`make validate && make test` must pass on the exact tree you commit.** Commits are coherent: no trail of "fix review" commits.
- **Never mutate the developer's host**: no `make setup/fix/uninstall`, no `systemctl --user` mutation, no edits to the real rc or agent settings. Tests use a scratch HOME (autouse in `tests/conftest.py`); real installs run only in disposable containers.
- **Zero sudo**: no code path runs `sudo`/`pkexec`/`doas`; root work is handed off as the exact command.
- **Architecture rules** (`.claude/architecture.md`): (1) one view registry (`VIEWS`), (2) one navigation path (`UnifiedApp.show_view`), (3) one apply workflow (`ui_common.run_live` for live core mutations from screens), (4) `setup.py` is wiring only (decision functions live in `installer/`), (5) no orphan helpers: a shared helper with zero production callers is deleted or adopted. Rule 5 is why deletions must ride with their replacements.
- **Tests**: parallel by default (`pytest -n auto`, capped near 40% of threads), xdist-safe (no fixed paths/ports, `monkeypatch` for env/cwd/HOME), deterministic and offline, no skip/xfail without a `reason=`. Coverage must not drop.
- **Docs are tested**: `tests/test_docs.py` pins load-bearing phrases in `.claude/architecture.md`; a Phase 20 section needs a matching `_PHASE_20_REQUIRED` test, and the Phase 3/13/14 paragraphs that describe deleted machinery must be edited (Pitfall 14).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Disposition decision (`build_plan`) | Pure core (`installer/session.py`) | — | Pure function of published state; no IO, no network (SPEC constraint) |
| Dependency closure, ordering, blocked reasons, `requested_by` | Pure core (`installer/deps.py`) | — | `requires` + `resolve_dependencies` stays the only ordering mechanism (architecture.md "Tier is a browsing label") |
| Update-refusal predicate | Pure core (`installer/update.py`) | `build_plan` | One predicate shared by `_perform` and the plan so the review cannot promise an update the engine refuses |
| Plan execution (`execute_plan`, `RowOutcome`, `WORDS`, `exit_code`, `retained`) | Pure-ish core (`installer/session.py`) | TUI worker, headless | One engine for both routes; only callbacks differ (streaming, prompts) |
| Review / progress / summary text | Render (`installer/render.py` `render_plan`, `render_run_summary`) | — | Words come from `WORDS`; width rules live here |
| Review screen, `r` toggle, wait token, retained selection | TUI (`installer/execute_screen.py`, `installer/wizard_app.py`) | — | IO adapter only (architecture.md Phase 13: "an IO adapter, not a second decision layer") |
| State publication and single-flight | `VersionRefreshService` (`installer/version_status.py`) | — | Already owns epoch, seq, `state_of`; the waiter joins it |
| Service construction for headless | `setup.py` (wiring) | — | Rule 4: construct only; extract a builder shared with `_build_app` |
| Exit code | `installer/session.py` `exit_code` | `setup.py` | `setup.py` only passes the list through (rule 4) |
| Terminal-sync trigger | `installer/session.py` `ran_anything` | `UnifiedApp._install_closed`, `setup.main` | Computed from outcomes (D-11) |

## Standard Stack

### Core

No new dependencies. Everything is existing in-repo code. [VERIFIED: pyproject.toml read; `uv run python` printed `3.12.12 8.2.7` for Python and Textual]

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.12 installed (`requires-python = ">=3.11"`) | StrEnum, frozen dataclasses | Project baseline |
| textual | 8.2.7 installed (`textual>=8`) | `ModalScreen`, `@work(thread=True)`, `post_message` | Already used for the execute screen and every worker |
| rich | `rich>=13` | `Console(width=…)` capture, `Text` | Already the render layer (`render.py`) |
| pytest + pytest-asyncio (`asyncio_mode = "auto"`) + xdist | existing | Tests | `.claude/testing.md` |

### Supporting (existing seams to reuse, not rebuild)

| Seam | Location | Use in this phase |
|------|----------|-------------------|
| `state_of`, `ToolState`, `Health`, `VersionRefreshService.refresh` | `installer/version_status.py:960`, `:693`, `:173`, `:1499` | Plan input; the wait joins `refresh(catalog)` |
| `resolve_dependencies` | `installer/deps.py:32` | Only ordering mechanism; extended additively |
| `install_tool(repair=…, present=…)` | `installer/engine.py:138` | INSTALL/REPAIR/REINSTALL |
| `UpdateService.run` | `installer/update.py:496` | UPDATE rows; unchanged |
| `ConfigStep` (+ `ConfigStepKind`) | `installer/model.py:311-333` | RECONFIGURE steps |
| `executors.execute`, `terminal_sync` closures | `installer/executors.py`, `setup.py:942` | `pnpm_group_install`, `terminal_sync` |
| `FrozenStateService`, `pass_state`, `frozen_service` | `tests/state_doubles.py` | Fixture states for `build_plan` and screen tests |
| `ownership.MUTATION_GRADE`, `UNMANAGEABLE_OWNERS`, `OS_PACKAGE_OWNER`, `owner_label`, `declared_manager_label` | `installer/ownership.py` | Update/skip decisions and off-policy reasons |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extend `Summary` (Laya's lean) | `RowOutcome` list | Rejected by locked D-08: two vocabularies |
| New `request_refresh` owner now | Join the service single-flight | The owner is Phase 21 scope; building it here duplicates 21 D-05. Recommended: join `service.refresh(catalog)` (Open Question 4) |
| `os.chdir` / `env -C` for `ConfigStep.cwd` | `sh -c 'cd -- "$1" && shift && exec "$@"'` argv wrapper | `chdir` is process-global (thread-unsafe); `env -C` is absent on macOS. The wrapper is portable and leaves `Runner` unchanged |

**Installation:** none. **Version verification:** not applicable (no packages added).

## Package Legitimacy Audit

No external packages are installed or added by this phase.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
 selection ids (Decided.result, or --all / --categories)
        |
        v
 +-----------------------+   state_of(id) -> ToolState | None      +--------------------------+
 | build_plan (pure)     |<----------------------------------------| VersionRefreshService    |
 |  order_for_install    |   platform (live: service.platform)     |  _states, epoch, seq     |
 |  resolve_dependencies |                                         |  refresh(catalog) single |
 |   -> closure, blocked,|                                         |  flight (join by id-set) |
 |      requested_by     |                                         +------------^-------------+
 |  per-tool disposition |                                                      |
 +-----------+-----------+                                                      | join / run ONE pass
             | list[PlanRow]  (any WAIT row?)                                   |
             |                         yes                                      |
             +--------------------------------> wait worker (token) ------------+
             | no                                  |  settled -> rebuild plan (same reinstall set)
             v                                     v
   render_plan(rows)  ---- review (TUI Static, or headless Console) ----> user: r toggles reinstall,
             |                                                            esc keeps selection, Enter starts
             v
 +------------------------------------------------------------------------------------------+
 | execute_plan(rows, RunContext) -> list[RowOutcome]   (one per row, plan order)           |
 |  SKIP/BLOCKED -> emit skipped/blocked (never run)                                        |
 |  INSTALL/REPAIR/REINSTALL -> install(force=repair ids) ; dependency_failed propagation   |
 |  UPDATE -> UpdateService.run (re-resolves ownership, invalidates epoch)                  |
 |  RECONFIGURE -> ConfigStep executors by kind, stop at first failure                      |
 |  except Exception -> row crashed, rest not_attempted ; should_continue() -> not_attempted|
 +----------------------------------+-------------------------------------------------------+
                                    | list[RowOutcome]
        +---------------------------+------------------------------+----------------------+
        v                           v                              v                      v
 summary_counts / WORDS     exit_code (1 iff failed|mismatch|     retained(...) ->        ran_anything ->
 (review words == summary    dependency_failed|not_attempted|     UnifiedApp._staged       terminal sync +
  words)                     crashed)                             .intersection_update    PATH wiring gate
```

### Recommended Project Structure

```
installer/
├── deps.py            # Resolution gains closure / blocked / requested_by (additive)
├── session.py         # Disposition, PlanRow, RowOutcome, WORDS, build_plan, execute_plan,
│                      #   summary_counts, exit_code, retained, ran_anything, RunContext
├── update.py          # update_refusal(...) extracted from _perform; wording fix (PLAN-08)
├── render.py          # render_plan, render_run_summary; render_audit/render_summary/
│                      #   render_dependency_notice DELETED
├── execute_screen.py  # plan-driven review + progress, r key, wait worker; _classify_selection,
│                      #   _update_targets, _preflight_prompt, 3 progress lists DELETED
├── wizard_app.py      # UnifiedApp: outcomes fold, retained selection, sync gate
├── app.py             # run_wizard on build_plan/execute_plan; _choose_tools shrinks
├── audit.py           # DELETED (forces selection.tool_choices / Prompter two-step path out, Pitfall 10)
└── engine.py          # reapply_post_install DELETED (no caller after D-06)
setup.py               # extract _build_services(); _session_exit_code -> exit_code(outcomes)
scripts/container-e2e-verify.sh  # SUMMARY_RE parser updated (Pitfall 11)
```

### Pattern 1: `Resolution` additive fields (needed by D-01, D-02, D-04)

**What:** Keep `order`, `dragged_in`, `warnings` byte-identical (existing `tests/test_deps.py` pins them) and add what the plan needs: the deps-first closure including present tools, the blocked set with culprit, and `requested_by`.

**Why it is needed:** `resolve_dependencies` drops every present tool from `order` (`satisfied_by_install`), so a directly selected present tool (UPDATE, RECONFIGURE, REINSTALL, SKIP) has no position in `order`; and the resolver currently returns blocked tools only as warning *text*.

**Verbatim facts (read this session):**
`installer/deps.py:27-29`:
```
    order: tuple[Tool, ...]
    dragged_in: tuple[str, ...]
    warnings: tuple[str, ...]
```
`installer/deps.py:109-113`:
```
    # Tools that need no installation action: already installed AND not blocked.
    # These satisfy dependency edges but are excluded from the output order.
    satisfied_by_install = {t.id for t in wanted if is_installed(t) and t.id not in blocked}

    runnable = [t for t in wanted if t.id not in blocked and t.id not in satisfied_by_install]
```

**Proposed shape** (new code, not a verified in-repo value):
```python
@dataclass(frozen=True)
class Blocked:
    tool_id: str
    needs: str | None   # None = unavailable itself; else the first blocking dependency id
    reason: str         # the existing warning text

@dataclass(frozen=True)
class Resolution:
    order: tuple[Tool, ...]
    dragged_in: tuple[str, ...]
    warnings: tuple[str, ...]
    closure: tuple[Tool, ...] = ()               # deps-first, non-blocked, present tools included
    blocked: tuple[Blocked, ...] = ()
    requested_by: Mapping[str, str] = field(default_factory=dict)  # dragged id -> first selected tool
```
`requested_by` is recorded in `collect()` by threading the selected root through the recursion (the root is the `for tool in selected` loop variable). `closure` is the same `visit` topological sort run over all non-blocked `wanted` tools; `order` is computed exactly as today so existing tests stay green. `blocked.needs` is set inside `is_blocked` where `dep_blocked` is evaluated.

### Pattern 2: Disposition table (direct vs dragged) [CITED: target-architecture §3.1; SPEC R2/R3; CONTEXT D-03/D-04]

| `state_of` / health | Owner / proof | Direct selection | Dragged dependency |
|---|---|---|---|
| `None` or `CHECKING` | — | WAIT "checking…" | WAIT |
| `MISSING` | — | INSTALL | INSTALL, reason "needed by X" |
| `UNAVAILABLE` | — | BLOCKED (`state.reasons[0]`, else the resolver warning) | BLOCKED; dependent BLOCKED "blocked — needs X" |
| `BROKEN` | owner not in `UNMANAGEABLE_OWNERS` | REPAIR (Open Question 2 for receipt drift) | REPAIR |
| `BROKEN` | owner in `UNMANAGEABLE_OWNERS` (sudo) | BLOCKED, reason names the owner | BLOCKED |
| `MISCONFIGURED` | `state.unconfigured` has executable steps | RECONFIGURE (steps listed) | SKIP "already present", health reason shown |
| `MISCONFIGURED` | no steps | BLOCKED, health reason (Open Question 7) | SKIP "already present" |
| `OUTDATED` | `update_refusal(...)` is None | UPDATE | SKIP "already present", health reason shown |
| `OUTDATED` | refused (native, os-package, volta, sdkman, unknown, pnpm host-setup) | SKIP "managed by {owner}" / refusal text | SKIP "already present" |
| `OK` | `ownership.owner == "installer"` | SKIP "already current (r: reinstall)", `can_reinstall=True`; REINSTALL when id in `reinstall` | SKIP "already present" |
| `OK` | another manager / unknown | SKIP "managed by {owner}" (`r` inert) | SKIP "already present" |

Rendered text is `f"{WORDS review word} — {reason}"`, e.g. `skipped — already current (r: reinstall)`, `skipped — managed by dnf`, `skipped — already present`, `will install — needed by mmdc`, `blocked — needs docker`. The ROADMAP/SPEC/CONTEXT all say "will repair"; target-architecture §7 says "will repair (reinstall)". Use "will repair" (a test asserting `"will repair" in text` passes either way) [ASSUMED: A12].

`is_installed` for the resolver, per D-01: `present and health is not BROKEN`, where `present` is `state is not None and state.present` (`ToolState.present` is false for `CHECKING`/`MISSING`/`UNAVAILABLE`). A `None` state counts as not installed, which is safe because it becomes a WAIT row and blocks the run.

### Pattern 3: One outcome list, pure derived views [ASSUMED design, matches locked D-08..D-11]

```python
Result = Literal["done", "failed", "mismatch", "dependency_failed", "not_attempted",
                 "crashed", "skipped", "blocked", "manual"]

@dataclass(frozen=True)
class RowOutcome:
    row: PlanRow
    result: Result
    install: InstallOutcome | None = None   # keeps render_failure_details/handoff/verification working
    update: UpdateOutcome | None = None
    detail: str = ""

_FAILURE = frozenset({"failed", "mismatch", "dependency_failed", "not_attempted", "crashed"})
_KEEP = _FAILURE | {"blocked", "manual"}          # stay selected
_RAN = frozenset({"done", "failed", "mismatch", "crashed"})  # state may have changed

def exit_code(outcomes) -> int:   return int(any(o.result in _FAILURE for o in outcomes))
def retained(outcomes) -> frozenset[str]: return frozenset(o.row.tool_id for o in outcomes if o.result in _KEEP)
def ran_anything(outcomes) -> bool: return any(o.result in _RAN for o in outcomes)
```
`manual` is in `_KEEP` and not in `_FAILURE` (D-17). `_RAN` excludes `manual`, `skipped`, `blocked`, `not_attempted`, `dependency_failed` because nothing was mutated.

Engine/update results map to `Result` as follows [ASSUMED mapping; the D-08 result set has no slot for three engine statuses, Open Question 3]:

| Source | Result |
|---|---|
| `InstallStatus.INSTALLED` | done |
| `InstallStatus.ALREADY_INSTALLED` (race: tool became present) | skipped |
| `InstallStatus.FAILED` | failed |
| `InstallStatus.CHECKSUM_MISMATCH` | mismatch |
| `InstallStatus.DEPENDENCY_FAILED` | dependency_failed |
| `InstallStatus.MANUAL_REQUIRED` (host_setup/skill_pack handoff) | manual |
| `InstallStatus.NO_METHOD` | blocked |
| `UpdateOutcome.status == "updated"` | done |
| `"failed"` | failed |
| `"unknown-owner"`, `"unsupported"` (race, or an un-predicted refusal) | blocked, `detail` = the outcome detail |
| update latch refused (`updates.begin` False) | blocked, `detail` "update already in flight for X" |
| any `Exception` in a row | crashed (rest not_attempted) |
| `should_continue()` false before a runnable row | not_attempted |

### Pattern 4: One `WORDS` table, parity by construction

CONTEXT leaves the exact keys to discretion. Recommended: a single module-level table with, per `Disposition`, the review word and the done-summary word, plus one word per non-done `Result`. `summary_counts(outcomes)` groups by `(disposition, result)`: `done` -> the disposition's done word ("installed", "updated", "repaired", "reconfigured", "reinstalled"), `skipped` -> "skipped", `blocked` -> "blocked", other results -> their own word ("failed", "checksum mismatch", "dependency failed", "not attempted", "crashed", "manual"). Output order is the table order, e.g. `2 installed, 1 updated, 3 skipped, 1 failed`. The parity test iterates the table and asserts that every `Disposition` has both words and that `render_plan` and `summary_counts` only ever read the table (no literals in `render.py`).

### Pattern 5: Wait for state on the service single-flight [ASSUMED, Open Question 4]

`ExecuteScreen` gets a `_wait_token: int`, a `_start_requested: bool` and one `@work(thread=True, exclusive=True, group="execute-wait", exit_on_error=False)` worker. The worker calls `refresh.refresh(self._inputs.catalog)` with the **whole catalog**. That is the same id-set key the catalog tiers use (`frozenset(tool.id for tool in tools)`), so `VersionRefreshService.refresh` joins an in-flight pass at the current epoch instead of starting a second one, and starts the one pass only when none is running. The worker posts `StateSettled(token, error)`. The handler ignores a message whose token is stale (esc bumped it), otherwise rebuilds the plan from `state_of` with the current `reinstall` set and, if `_start_requested` and no WAIT rows remain, starts the run. No timeout. A raised error is shown and Enter retries. The worker also runs at mount when the first plan has WAIT rows, so "checking…" rows repaint on their own.

Verified behavior it relies on (`installer/version_status.py:1499-1531`, read this session): a call over the same tool-id set as an in-flight pass at the current epoch "joins that pass (or raises its error): no second fetch, probe or publication. It never joins across an `invalidate`."

### Pattern 6: `ConfigStep` dispatch by kind (RECONFIGURE)

Steps run in order and stop at the first failure (19 D-18 requires enable-canonical before removing copies; continuing after a failed enable would remove the only working copy).

| `kind` | Executor | Notes |
|---|---|---|
| `plugin_enable`, `plugin_uninstall`, `marketplace_remove`, `project_pack_global_uninstall`, `project_pack_install`, `skill_install` with argv | `runner(step.argv)` (wrapped in the cwd shim when `step.cwd` is set) | argv comes only from constants and registry pins (builders validate) |
| `skill_install` with **empty** argv (`partial_steps`) | Reviewed handoff, not an execution: produce the per-harness instruction lines via `skill_lifecycle.perform_action(tool, "install", runner)` and return result `manual` | `partial_steps` builds `ConfigStep(f"install {tool.id} for {label}", "skill_install", harness)` with no argv |
| `pnpm_group_install` | `executors.execute(first node method of the declaring tool, runner)` | L-19-28; the whole pinned group, `--allow-build`, smoke check |
| `terminal_sync` | injected `terminal_sync` closure (the one `setup.py::_sync_omz_terminals` already provides) | same synchronizer as Policies/`u` |

### Anti-Patterns to Avoid

- **A second sort in `build_plan`.** Use `Resolution.closure`; do not re-implement topology.
- **Re-reading `state_of` inside `execute_plan`.** `UpdateService.run` calls `invalidate`, which bumps the epoch, so `state_of` returns `None` for every tool after the first update. Capture what execution needs on the `PlanRow` at plan time (ownership, steps).
- **Matching `"(r: reinstall)"` in the reason string** to decide `r` eligibility. Use a boolean `PlanRow.can_reinstall`.
- **Letting `ExecuteScreen` call `refresh` with a partial id set** (a different single-flight key means a second concurrent pass, which D-13 forbids).
- **Acting on a row whose disposition is WAIT.** `execute_plan` must refuse a plan containing WAIT (raise `ValueError`), and headless must treat WAIT-after-sync-pass as a failure, not run it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency order and transitive drag-in | A topological sort in `build_plan` | `resolve_dependencies` + additive `closure` | `requires` is the only ordering mechanism (architecture.md) |
| Update vs refuse decision | A parallel ownership ladder in `build_plan` | One `update_refusal(target.tool, ownership, platform)` extracted from `update._perform`, used by both | Otherwise the review promises "will update" and the engine answers "unsupported" (G case D) |
| Checksum-mismatch retry/fallback | New retry code | The body of `run_installs` (fold it into `execute_plan`) | Existing, tested behavior |
| Repair/force flag plumbing | Widening the `Install` protocol (29 fakes) | `_with_repair` generalized to `force_ids` (a wrapper) | architecture.md Phase 14: `with_sensitive_confirm` precedent |
| Update ownership at run time | Trusting the plan's ownership | `UpdateService.run` already re-resolves (`reresolve_ownership`) | Display can be cached; mutation cannot (architecture.md Phase 12) |
| Terminal sync | A new synchronizer | The existing `_sync_omz_terminals` closure | One synchronizer for all routes |
| Wrapped-line handling at 78 columns | Manual wrapping | Rich `Console(width=…)` capture + `Text(overflow="fold")` | Existing test style |
| Per-process `cwd` for a child | `os.chdir` | argv wrapper `sh -c 'cd -- "$1" && shift && exec "$@"' sh <cwd> <argv…>` | Thread-safe and portable; `Runner` stays `Callable[[list[str]], None]` |

**Key insight:** every decision this phase "adds" already exists in some screen's private code; the work is moving each decision to exactly one pure function and deleting the copies. The risk is not logic, it is leaving a second copy alive.

## Common Pitfalls

### Pitfall 1: The resolver hides present tools
**What goes wrong:** D-01 says order comes only from the unchanged resolver. But `Resolution.order` excludes every installed, non-blocked tool, so direct UPDATE/RECONFIGURE/REINSTALL/SKIP rows have no position, and "A dragged present dependency -> already present under its dependent" cannot be produced.
**Why:** `deps.py:109-113` (quoted above) removes `satisfied_by_install` from the order.
**How to avoid:** the additive `closure`/`blocked`/`requested_by` fields (Pattern 1). Keep `order` byte-identical so `tests/test_deps.py` (23 tests) stays valid.
**Warning signs:** a test selecting a current tool gets zero rows; a dragged present dep is missing.

### Pitfall 2: `UpdateService.run` invalidates the epoch mid-run
**What goes wrong:** after the first successful update `state_of` returns `None` for the whole catalog. Code that reads `state_of` or `refresh.state_of(...).ownership` for later rows (as `_run_updates` does today, with a `refresh.refresh([tool])` fallback) will see `None`.
**Why:** `update.py:568-570`: `if outcome.status == "updated" and self._invalidate is not None: ... self._invalidate(reason=...)`.
**How to avoid:** `PlanRow` carries `ownership` (for `UpdateTarget`) and `steps`; `execute_plan` never reads published state. The reported "now X.Y.Z" version after an update (current `versions[tool.id]` from a single-tool refresh) needs a deliberate decision: either drop it or read it from `UpdateOutcome`; do not call `refresh([tool])` inside `execute_plan` (it would publish a one-tool pass).

### Pitfall 3: Engine statuses with no slot in the locked result set
**What goes wrong:** D-08's results are `{done, failed, mismatch, dependency_failed, not_attempted, crashed, skipped, blocked}`. `InstallStatus.MANUAL_REQUIRED` (every skill pack and `host_setup` tool such as pi, ponytail) and `NO_METHOD` have no slot. Today `Summary.has_failure` explicitly excludes both (`manual_required`, `no_method`), so mapping them to a failure result would change the exit code of every `--all --yes` run.
**How to avoid:** adopt `manual` now (D-17 already defines it with the right semantics: stays selected, exit code unchanged) and map `NO_METHOD` -> `blocked` (Pattern 3 table). Keep `_UNRESOLVED` semantics for dependency propagation. Open Question 3.

### Pitfall 4: `Runner` has no `cwd`
**What goes wrong:** `ConfigStep.cwd` is set for project-scope `plugin_uninstall` and for `project_pack_install` (the per-repo install, L-19-07). `Runner = Callable[[list[str]], None]` (`installer/run.py:18`) cannot carry it; `StreamingRunner`, `run_captured` and every test fake share that signature.
**How to avoid:** the argv wrapper (Don't Hand-Roll). Re-validate the directory at execution time (absolute, `lstat` says directory, not a symlink), because the plan may be minutes old and `skill_lifecycle.py:378` documents that "a repo becomes the `cwd` of a Phase 20 command".

### Pitfall 5: Empty-argv steps are handoffs or kind-dispatched
**What goes wrong:** running `runner(step.argv)` with `()` raises or no-ops. Three kinds legitimately have no argv: `terminal_sync`, `pnpm_group_install` (dispatched by kind, L-19-28) and `skill_install` from `partial_steps` (a reviewed handoff). A `MISCONFIGURED` row whose only steps are handoffs is **manual**, not done.
**How to avoid:** Pattern 6. Test one fixture per `ConfigStepKind` (the Literal has 8 members, quoted below).

### Pitfall 6: There is no app-level refresh owner yet
**What goes wrong:** CONTEXT D-13 ("Enter waits on the single refresh owner... registers a waiter for the next publication, triggering the owner worker") assumes `UnifiedApp.request_refresh`. That is **Phase 21 D-05**, and 21-CONTEXT lists "the 20 D-13 waiter" as one of its integration points. In the current tree each `CatalogScreen` runs its own `_refresh_versions_worker`; the only de-duplication is `VersionRefreshService.refresh`'s single flight, keyed by the tool-id set.
**How to avoid:** Pattern 5 (join via `refresh(whole catalog)`). Write the waiter behind one small method (`_await_state`) so Phase 21 swaps its body for `request_refresh()` + a publication callback without touching callers. Open Question 4.
**Warning signs:** a test counting `refresh` calls sees two concurrent passes; the wait uses `refresh(planned_tools)`.

### Pitfall 7: Headless has no state service and no update capability
**What goes wrong:** `run_wizard` is called from `setup.main` with no `VersionRefreshService` and no `UpdateService`; both are constructed inside `_build_app` (`setup.py:897`, `:1121`). Today `--all --yes` can never update anything. PLAN-06 requires "on a host with an outdated tool it updates it and exits 0".
**How to avoid:** extract the service construction from `_build_app` into one `_build_services(tools, platform)` in `setup.py` returning `(version_refresh, updates, install)`. The extraction is clean: `UpdateService`'s dependencies (`_reinstall_globals`, `_sync_omz_terminals`, `pnpm_globals`) do not depend on policy objects. Then `run_wizard` takes `refresh` and `updates` as parameters. Headless runs `refresh.refresh(tools)` synchronously (a 4.5-5.7 s pass per SPEC R7).
**Warning signs:** a headless test passes only with a hand-injected `installed=` predicate.

### Pitfall 8: Retained selection must mutate the shared set in place
**What goes wrong:** `UnifiedApp._staged` is one `set` shared by the three tier screens and their `ToolBrowser`s (`wizard_app.py:2517`, `:2578`; `ToolBrowser` comment: "Several browsers may share one set, so the two bulk actions must never rebind it"). Assigning a new set breaks the sharing.
**How to avoid:** `self._staged.intersection_update(retained_ids)` on a run result, and no change on `None` (esc before start). Intersecting also drops dragged-in ids that were never selected (Open Question 6).
**Verbatim current code (`wizard_app.py:2898-2899`):**
```
    def _install_closed(self, _result: None) -> None:
        self._staged.clear()
```
`ExecuteScreen` is `ModalScreen[None]` and `push_screen(ExecuteScreen(...), self._install_closed)` ignores the result; the dismiss value must become `list[RowOutcome] | None`.

### Pitfall 9: The `r` copy and eligibility (G21 / WR-03 deferred here)
**What goes wrong:** Phase 19 emits `UNPROVEN_NOTE = "not proven: reinstall with r to adopt"` (`version_status.py:606`, comment: "SPEC-locked text; this phase adds no `r` binding (Phase 20 does)") on installer-owned tools with no receipt. In the catalog `r` is `accept_recommends`. D-14 says `r` acts only on rows "installer-owned by receipt or adoption", but an unproven installer-owned tool has neither, and that is exactly the row whose note says to press `r`.
**How to avoid:** make eligibility `Health.OK and ownership.owner == "installer"` (receipt optional), so the note becomes true on the review screen; and reword the note so it does not point at the catalog's `r` (for example "not proven: select it, then press r on the review to reinstall and adopt"). The note is pinned by `tests/test_version_status.py:4212` (`_UNPROVEN`) and possibly by catalog detail tests; update them. Open Question 5. [ASSUMED: A5]

### Pitfall 10: Deleting `audit.py` cascades
**What goes wrong:** D-12 deletes `installer/audit.py`. `ToolStatus` is also imported by `installer/selection.py:6` (`tool_choices`) and `installer/render.py:12`; `app._choose_tools` uses `audit(...)` + `tool_choices(statuses)` in its prompter two-step branch. In production that branch is unreachable: `main()` routes every non-`--all`/`--categories` run to `_run_interactive_wizard`, and `setup.py` never passes `select_catalog`.
**How to avoid:** delete the dead two-step branch (`_choose_tools` keeps only `--all`/`--categories`), `tool_choices`, `Prompter.select_categories`/`select_tools` and `category_choices` if nothing else reads them (rule 5), and port `tests/test_audit.py` (72 lines), `tests/test_selection.py` (9 refs), `tests/test_prompt.py` (2), `tests/test_app.py` (9 refs). Verify with `grep` before deleting each helper; keep `Choice`/`select_tools` (used by the TUI path).

### Pitfall 11: A hidden consumer parses the old summary line
**What goes wrong:** `scripts/container-e2e-verify.sh:242` defines
```
SUMMARY_RE='Installed: [0-9]+[[:space:]]+Already: [0-9]+[[:space:]]+Failed: [0-9]+[[:space:]]+Dependency failed: [0-9]+[[:space:]]+Checksum mismatch: [0-9]+[[:space:]]+No method: [0-9]+[[:space:]]+Manual setup required: [0-9]+'
```
and `parse_summary_line` extracts each counter; pass1/pass2 gate on `failed == 0`, `mismatched == 0` and cross-check `dependency_failed` against `manual_required`. Replacing `render_summary` with `2 installed, 1 updated, ...` silently breaks `make e2e` (the parse returns empty and the harness reports incomplete).
**How to avoid:** change the harness in the same wave as the summary (parse the new words, or emit a stable machine line next to the human line), and update the 7 references in `tests/test_shell_scripts_path.py` / `tests/test_container_e2e_receipts.py` if they assert the format. `make e2e` runs in a disposable container and is the human-verification backstop; do not run it from research.

### Pitfall 12: PATH-wiring and verify errors currently fail the exit code
**What goes wrong:** the worker sets `error = path_fail`/`verify_fail`, `fold_run(... error=message.error)` stores it as `crash_error`, and `Summary.has_failure` returns true for it, so `_session_exit_code` returns 1 and the screen says "Failed.". D-09 defines the exit code over rows only; a naive port loses this. `test_wire_path_oserror_names_the_section_and_still_finishes` pins the behavior.
**How to avoid:** carry a run-level `error` next to the outcome list (the `InstallRunFinished` message already carries `error`/`path_error`/`verify_error`) and have the app-level exit rule be `exit_code(outcomes) or bool(run_error)`; or model a failed wiring as a `crashed` pseudo-row. Open Question 8. Also gate PATH wiring/verify on `ran_anything` (Open Question 8) so "starts nothing" is true for an all-skipped run.

### Pitfall 13: 76 columns, not 78, inside the head widget; and an unscrollable head
**What goes wrong:** D-16 reuses `Console(width=80)` (`execute_screen.py:1161`: `render(Console(file=buffer, width=80, no_color=True))`). But `#execute-head` is `height: auto; padding: 1 2;` (`execute_screen.py:454`), so on an 80-column terminal the inner width is 76 and Textual re-wraps what Rich laid out at 80. Also `height: auto` with a long plan (an `--all` style selection can exceed 20 rows) pushes `#execute-log` (`1fr`) to zero height at 80x20.
**How to avoid:** render the plan at the widget's real width (pass `width` into `render_plan`), cap the plan region with `max-height` and scrolling, and assert in a pilot test at `size=(80, 20)` with 25 rows. The longest registry id is 24 characters (checked with `tomllib`); the longest fixed phrase `skipped — already current (r: reinstall)` is 41, so a 2-space indent leaves room (2+24+2+41 = 69), but `ConfigStep.text` and probe-derived reasons are unbounded: fold them onto continuation lines.
**Also:** reasons and step text come from probe output (plugin ids, repo names). Render with `Text`/`markup=False` and pass through `sanitize_log_line`; `ExecuteScreen._render_captured` already sanitizes the whole capture, `render_plan` must not use markup interpolation.

### Pitfall 14: Docs are test-pinned and describe deleted machinery
**What goes wrong:** `.claude/architecture.md` Phase 3 ("`run_installs`... `dependency-failed`"), Phase 13 (`resolve_dependencies, audit, run_installs...` "sole owners"), Phase 14 ("The split is made beside the `resolve_dependencies` call in `ExecuteScreen.on_mount`") describe the code this phase deletes. `tests/test_docs.py` pins phrases from those sections (`_PHASE_13_REQUIRED`, `_PHASE_14_REQUIRED`, ...).
**How to avoid:** rewrite those paragraphs to describe `build_plan`/`execute_plan`, update the pinned tuples in the same commit, add a Phase 20 section plus `_PHASE_20_REQUIRED`. Do not delete a pinned phrase without updating the test for the right reason.

### Pitfall 15: Dragged display order versus execution order
**What goes wrong:** execution is deps-first (dependency before dependent), but SPEC/D-02 say the dragged row is rendered "indented under" its first dependent. A naive in-order render puts the dependency above the dependent.
**How to avoid:** keep `PlanRow` order = execution order and group only at render time: each direct row, then its dragged children (those whose `requested_by` equals it) indented. State this in the review header ("order of execution is top to bottom except indented rows, which run first") or accept it silently; either way the test asserts "after the requester, indented". [ASSUMED: A11]

### Pitfall 16: REPAIR and REINSTALL follow the method ladder, not the owner's method
**What goes wrong:** `install_tool(repair=True)` walks `resolve_methods(tool, platform)` in rank order, which is install preference, never provenance (architecture.md Phase 12). Reinstalling an installer-owned binary after Homebrew appeared can pick brew first and create a shadow.
**How to avoid:** out of scope to fix here; record a `shortcut:` comment at the REINSTALL dispatch and a test that pins the current behavior on a tool whose first method equals its owner.

### Pitfall 17: Unattended auto-start races the wait
**What goes wrong:** `ExecuteScreen.on_mount` calls `self.action_start()` when `inputs.unattended`. With WAIT rows that must set `_start_requested` and wait, not start.
**How to avoid:** `action_start` is the single entry; it builds the plan, and if any row is WAIT it records the request and returns.

### Pitfall 18: Test blast radius is the dominant cost
`tests/test_execute_screen.py` (4705 lines, 114 tests; 30 hits on `_to_update/_reapply/_classify_selection/_refused/_current/_repair_ids/_preflight_prompt/_progress`), `tests/test_wizard_app.py` (22 `ExecuteInputs(`, `install_summary` tests such as `test_two_runs_accumulate_failures_into_install_summary`), `tests/test_app.py` (30 `run_wizard`), `tests/test_setup.py` (34 `Summary`), `tests/test_session.py` (22), `tests/test_render.py` (22), `tests/test_post_install.py`/`tests/test_engine.py` (`reapply_post_install`). Budget explicit port tasks; do not leave them to "fix at the end". Keep `ExecuteScreen(ids, inputs)` and the test helper `_inputs(...)` signatures stable.

## Code Examples

Everything below is a **proposal** to be adapted, not copy-ready verified code.

### `build_plan` skeleton
```python
# Source: this research; contracts from CONTEXT D-01..D-04, target-architecture §3.1
def build_plan(selected, catalog, state_of, platform, *, reinstall):
    chosen = select_tools(list(catalog), list(selected))
    def settled(tool):                                   # D-01: present and not BROKEN
        s = state_of(tool.id)
        return s is not None and s.present and s.health is not Health.BROKEN
    res = resolve_dependencies(
        order_for_install(chosen), list(catalog),
        available=lambda t: bool(resolve_methods(t, platform)),
        is_installed=settled,
    )
    direct = {t.id for t in chosen}
    rows = [_blocked_row(b, res) for b in res.blocked]           # D-04
    for tool in res.closure:
        rows.append(_row(tool, state_of(tool.id),
                         requested_by=res.requested_by.get(tool.id),
                         dragged=tool.id not in direct, reinstall=reinstall))
    return sorted_by_closure_position(rows)        # blocked rows slot in at their closure position
```

### Shared update gate (extract from `update._perform`, parallel to Phase 22 D-14)
```python
# Source: installer/update.py:248-294 (early returns), this research
def update_refusal(tool, ownership, platform) -> str | None:
    """The sentence _perform would answer; None when an update can run."""
    # unknown owner / confidence not in MUTATION_GRADE / sdkman / UNMANAGEABLE_OWNERS /
    # volta / pnpm owner with no node method -> the same detail strings _perform returns today
```
`_perform` calls it first and wraps the string in `UpdateOutcome(status="unsupported"|"unknown-owner")`, so there is one source for both.

### Verified: current native sudo argv (why plan-time BLOCKED matters until Phase 22)
`installer/executors.py:448-457` (read this session):
```
def _dnf(method: Method, runner: Runner) -> None:
    runner(["sudo", "dnf", "install", "-y", require_str(method, "package")])
...
    runner(["sudo", "apt-get", "install", "-y", require_str(method, "package")])
...
    runner(["sudo", "pacman", "-S", "--noconfirm", "--needed", require_str(method, "package")])
```
Phase 22 D-12 deletes these and adds plan-time MANUAL. Until then an INSTALL row whose ladder ends in a native method still escalates; Phase 20's guarantee is narrower: a **repair or update** of a tool owned by a native/os-package manager is BLOCKED and `build_plan` itself never runs a command (assert with the conftest `GuardedPopen`).

### `ConfigStepKind` (verbatim, `installer/model.py:311-320`)
```
ConfigStepKind = Literal[
    "skill_install",
    "plugin_enable",
    "plugin_uninstall",
    "marketplace_remove",
    "terminal_sync",
    "pnpm_group_install",
    "project_pack_global_uninstall",
    "project_pack_install",
]
```

### cwd wrapper
```python
# Source: this research [ASSUMED: A3]
def in_directory(cwd: Path, argv: Sequence[str]) -> list[str]:
    # argv stays separate arguments, so nothing is interpreted by the shell
    return ["sh", "-c", 'cd -- "$1" && shift && exec "$@"', "sh", str(cwd), *argv]
```

## State of the Art

### Where CONTEXT's references point today

CONTEXT/SPEC cite the pre-17/19 tree. Use these current locations (all read this session):

| CONTEXT/SPEC reference | Now |
|---|---|
| `session.order_for_install` `:116` | `installer/session.py:163`; `Summary` `:106-134`, `fold_run` `:137`, `run_installs` `:168`, `summarize` `:238` |
| `deps.py:59-72` `collect()` | same (`installer/deps.py:59-72`); blocked warnings `:102-107`; `satisfied_by_install` `:111` |
| `execute_screen` worker `:573-671` | `_execute_worker` `installer/execute_screen.py:617-740`; `_run_updates` `:742-804`; `_with_repair` `:240-277`; `_classify_selection` `:537-574`; `_update_targets` `:576-589`; `_preflight_prompt` `:1110-1127`; `_refresh_progress` `:1129-1157`; `_render_captured` `:1159-1166` |
| `render_audit` `render.py:48-57`, `render_summary` `:60-79` | `render_audit` `:49-63`, `render_summary` `:66-87` |
| `app.run_wizard` `app.py:127-197` | `installer/app.py:130-197` |
| `wizard_app.py:2797` `_staged.clear()` | `installer/wizard_app.py:2899` (`_install_closed`) |
| `_install_state_changed` `:2487,2857,2960` | `:2566` (init), `:2923` (consumed), `:3020` (set) |
| `tool_browser.py:76` selectable default, `:300-308` | default still `:77`; `action_select_all` `:331-342`; **catalog already overrides**: `catalog_tui.py:375` `selectable=lambda tool: not self._is_unavailable(tool),` (D-05 core is done by Phase 19) |
| `catalog_tui.py:317` accept_recommends binding | `:322` `Binding("r", "accept_recommends", "add recommended", show=False),` |
| `catalog_tui.py:923` "moving it there" | `installer/catalog_tui.py:823` (inside `action_update_tool`) |
| `update.py:296` "moving it there" | `installer/update.py:309` (inside `_perform`) |
| `setup.py:1278,1509` exit checks | `_session_exit_code` `setup.py:1318-1327`; headless `if summary.has_failure:` `setup.py:1559` |
| `engine.reapply_post_install` `:200-216` | `installer/engine.py:300-316` |
| `ExecuteInputs` `_build_app` D-12 | `setup.py:1144` `execute = _execute_inputs(...)` then `replace(execute, installed=..., install=_install, version_refresh=..., updates=updates)` `:1160-1166` |

**Already done by earlier phases (do not redo):** D-05 selectable core (19); 17 D-07 `except Exception` in the worker (`execute_screen.py:710`); 17 D-12 `_build_app` builds `ExecuteInputs`; `state_of`, `Health`, `ToolState.unconfigured`, typed `ConfigStep`s (19).

**Deprecated/outdated by this phase:** `Summary`/`summarize`/`fold_run`, `run_installs`, `audit.py`, `render_audit`, `render_summary`, `render_dependency_notice`, `reapply_post_install`, `ExecuteScreen._classify_selection/_update_targets/_preflight_prompt`, the `_to_update/_current/_refused/_repair/_reapply` lists, `_install_state_changed`, `UnifiedApp.install_summary`/`_merge_summary`, `ToolStatus`.

## Runtime State Inventory

Not a rename/migration phase in the data sense. Explicit answers for the string removals:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None. Version cache, receipts and settings are unchanged; `Summary` is in-memory only | none |
| Live service config | None | none |
| OS-registered state | None | none |
| Secrets/env vars | None | none |
| Build artifacts | `scripts/container-e2e-verify.sh` `SUMMARY_RE`/`parse_summary_line` parse the old summary text (Pitfall 11) | code edit, same wave as the summary change |

## Don't-Break List (consumers of what is removed)

- `tests/test_docs.py` phrase tuples (Pitfall 14).
- `scripts/container-e2e-verify.sh` (Pitfall 11) and `tests/test_shell_scripts_path.py` / `tests/test_container_e2e_receipts.py` that reference it.
- Four other routes call `_session_exit_code(app)`: doctor, fix, uninstall, guard (`setup.py:1339,1377,1403,1495`). They all read `app.install_summary`/`run_in_flight`; keep one `_session_exit_code`, change what it reads.
- `UnifiedApp.on_tool_updated` folds a failed direct `u` into the session summary (`wizard_app.py:3023-3045`); it must fold a `RowOutcome(UPDATE, failed)` into the same outcome map so the exit code keeps failing after a failed `u`.
- `_merge_summary` "cancel-then-retry does not leak a stale failure" (`wizard_app.py:3047-3078`): replicate by keeping the **latest outcome per tool id** (a later `done` replaces an earlier `not_attempted`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all test commands | yes | 0.11.28 | — |
| Python | runtime | yes | 3.12.12 | — |
| textual | pilot tests | yes | 8.2.7 | — |
| `uv run pytest tests/test_session.py tests/test_deps.py -q --no-cov -n 0` | baseline | yes, passes | — | — |
| Container runtime (`scripts/detect-container-runtime.sh`) | `make e2e` (human verification only) | not probed; not needed for planning | — | e2e stays a human/CI backstop |

**Missing dependencies with no fallback:** none. **Missing with fallback:** container e2e is out of the automated loop by design.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode = "auto", pytest-xdist, coverage `fail_under = 90`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) |
| Quick run command | `uv run pytest tests/test_plan.py tests/test_session.py tests/test_deps.py tests/test_render.py -q --no-cov -n 0` |
| Screen run command | `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py -q --no-cov -n 0` (slow; run per wave, not per task) |
| Full suite command | `make validate && make test` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAN-01 | G cases A-I as parametrized `build_plan` tests on system, user, ai tiers (A listed not omitted; B current skip; C mixed install+skip; D dnf-owned skip; E broken -> repair; F off-policy skip naming both owners; G current zsh skip, `r` -> reinstall, sync runs; H current rtk skip (hooks are Phase 23); I no state -> WAIT) | unit | `uv run pytest tests/test_plan.py -q --no-cov -n 0` | no, Wave 0 |
| PLAN-01 | closure/blocked/requested_by; `order` unchanged | unit | `uv run pytest tests/test_deps.py -q --no-cov -n 0` | yes (extend) |
| PLAN-01 | dragged present dep indented after requester, listed once; 78-col budget with 24-char ids | unit/pilot | `uv run pytest tests/test_render.py tests/test_execute_screen.py -k plan -q --no-cov -n 0` | partial |
| PLAN-02 | `r` toggles both ways on installer-owned; inert on dnf-owned; `a`/`--yes` never reinstall | pilot + unit | `uv run pytest tests/test_execute_screen.py -k reinstall -q --no-cov -n 0` | no, Wave 0 |
| PLAN-03 | one test per (health x owner x direct/dragged) pair; sudo-needing repair BLOCKED; no `sudo`/`pkexec`/`doas` as `argv[0]`; `build_plan` makes no subprocess | unit | `uv run pytest tests/test_plan.py -k "health or sudo or pure" -q --no-cov -n 0` | no, Wave 0 |
| PLAN-03 | each `ConfigStepKind` executes (cwd wrapper, handoff -> manual, pnpm group via `executors.execute`, stop at first failure) | unit | `uv run pytest tests/test_session.py -k config_step -q --no-cov -n 0` | no, Wave 0 |
| PLAN-04 | `WORDS` parity: every `Disposition` has a review and a done word; summary and review read only the table; "2 installed, 1 updated, 3 skipped, 1 failed" | unit | `uv run pytest tests/test_session.py -k words -q --no-cov -n 0` | no, Wave 0 |
| PLAN-05 | mixed run keeps exactly failed/mismatch/dependency_failed/not_attempted/crashed/blocked/manual; `esc` before start leaves `_staged` unchanged; crash marks unfinished rows | pilot | `uv run pytest tests/test_wizard_app.py tests/test_execute_screen.py -k "retained or esc" -q --no-cov -n 0` | partial |
| PLAN-06 | `--all --yes` with one outdated brew tool updates it and exits 0; injected failure exits 1; all-current host runs nothing and exits 0; headless order == TUI order | integration | `uv run pytest tests/test_app.py tests/test_setup.py -k "wizard or headless" -q --no-cov -n 0` | partial |
| PLAN-07 | held refresh: rows "checking…", Enter starts nothing (engine and update service never called), release -> plan rebuilt -> run starts, `esc` during wait keeps selection, late publication ignored | pilot | `uv run pytest tests/test_execute_screen.py -k wait -q --no-cov -n 0` | no, Wave 0 |
| PLAN-08 | no `moving it there` anywhere under `installer/` (literal ASCII grep over the tree); off-policy reason still names both owners; unknown declared manager shows only the real owner | unit | `uv run pytest tests/test_update.py tests/test_catalog_tui.py -k off_policy -q --no-cov -n 0` plus the new grep test | partial |
| Prohib. | no reinstall unless `r` (`a`, `--yes`); engine never called on older-generation state; no sudo in the plan path | unit | covered by the rows above | — |
| Docs | Phase 20 section pinned | unit | `uv run pytest tests/test_docs.py -q --no-cov -n 0` | yes (extend) |

### Sampling Rate
- **Per task commit:** the quick run command (under 30 s, no Textual pilots).
- **Per wave merge:** quick command plus the screen run command for the touched screen files.
- **Phase gate:** `make validate && make test` green on the committed tree, then `/gsd-verify-work`. Human checks: `make e2e` in a container (summary parser), 80x20 review with 25 rows on a real terminal, `NO_COLOR=1`.

### Wave 0 Gaps
- [ ] `tests/test_plan.py` - G cases A-I x 3 tiers, health x owner matrix, dragged rows, purity (GuardedPopen).
- [ ] `tests/state_doubles.py` - a `plan_state(...)` builder over `pass_state` for every health/owner/step combination; a `HeldRefreshService` (a `FrozenStateService` whose `refresh` blocks on a `threading.Event` and counts calls); a fake `UpdateService` returning scripted `UpdateOutcome`s.
- [ ] A `RunContext` fake (install, runner, updates, terminal_sync recorders) shared by `tests/test_session.py` and the screen tests.
- [ ] `ExecuteInputs.version_refresh` becomes required (or a documented test default): decide before porting the 97 `ExecuteScreen(` tests; the `_inputs(...)` helper in `tests/test_execute_screen.py` is the single place to default it (Open Question 9).
- [ ] No new framework install needed.

## Security Domain

`security_enforcement` is enabled (absent = enabled; `security_asvs_level: 1`, `security_block_on: high` in `.planning/config.json`). [VERIFIED: config.json read]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes (privilege) | Zero-sudo invariant: REPAIR/UPDATE of a native/os-package-owned tool is BLOCKED, never escalated; no `sudo`/`pkexec`/`doas` argv built in the plan path |
| V5 Input Validation | yes | `ConfigStep.argv` only from constants + registry pins (builders validate; `_NPM_NAME_RE` gates pnpm names); re-validate `ConfigStep.cwd` at execution time; render reasons/step text as plain `Text`, sanitized (`sanitize_log_line`), never as Rich markup |
| V6 Cryptography | no | — |
| V12 Files | yes | `cwd` must be an absolute real directory (not a symlink) when the command runs, not only when the plan was built |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| TOCTOU between plan and run (state changes after Enter) | Tampering | Engine re-checks (`install_tool(present=…)`, `UpdateService.run` re-resolves ownership and re-checks the receipt drift gate); map a raced `ALREADY_INSTALLED`/`unsupported` to `skipped`/`blocked`, never to `done` |
| Markup/ANSI injection through probe-derived reasons | Tampering / Spoofing | `Text` objects, `markup=False`, `sanitize_log_line` (existing ANSI-bomb test pattern: `test_failed_install_report_never_carries_raw_escape_sequences`) |
| Acting on stale state | Tampering | WAIT rows block execution; epoch/token compare fails closed (`version_status.py` convention); late publication ignored after `esc` |
| Silent overwrite of a user-modified artifact via REPAIR | Tampering | Review shows "will repair" with the drift reason before Enter (Open Question 2) |
| Over-broad reconfigure (removing the only working plugin copy) | Denial of service | Steps run in order and stop at the first failure |

## Open Questions

1. **Group dragged rows under the requester, or keep execution order?** (Pitfall 15)
   - Known: SPEC/D-02 say "indented under its first dependent"; execution is deps-first.
   - Unclear: whether the user expects the review order to equal execution order.
   - Recommendation: keep `PlanRow` order = execution order; `render_plan` groups dragged rows under their requester (literal SPEC reading). Confirm.

2. **BROKEN caused by receipt drift ("changed since install"): REPAIR or refuse?**
   - Known: 19-RESEARCH Pitfall 10 said "Dispositions are Phase 20" and warns that repair "makes a 'changed since install' raw file get overwritten on select"; the current screen refuses it (`execute_screen.py:549-556`), and SPEC R3/TA §3.1 say BROKEN -> REPAIR for any owner.
   - Recommendation: REPAIR for both BROKEN sources with the drift reason visible in the review (informed consent at Enter), and pin it with a test. The alternative (BLOCKED, stays selected forever) is a dead end. Needs user confirmation [ASSUMED: A2].

3. **Result slots for `MANUAL_REQUIRED`, `NO_METHOD`, `ALREADY_INSTALLED`.** (Pitfall 3)
   - Recommendation: ship result `manual` in Phase 20 (kept selected, exit unchanged), map `NO_METHOD` -> `blocked`, `ALREADY_INSTALLED` -> `skipped`. Leave `Disposition.MANUAL` and `needs_manual` to Phase 22 (its D-12 owns the producer); structure `WORDS` so adding a `Disposition` member without a word fails the parity test. Confirm D-17 scope [ASSUMED: A1].

4. **Wait mechanism without Phase 21's owner.** (Pitfall 6)
   - Recommendation: Pattern 5 (join the service single-flight with `refresh(whole catalog)`), isolated in `_await_state` for Phase 21 to swap. Confirm this satisfies D-13's intent ("never a second pass") given the owner does not exist yet [ASSUMED: A4].

5. **Reword `UNPROVEN_NOTE` and widen `r` eligibility to unproven installer-owned tools.** (Pitfall 9)
   - Recommendation: yes to both; update the pinned tests.

6. **Which ids stay selected: all failed rows, or only the user's selection?**
   - Recommendation: `_staged.intersection_update(retained)`, so a failed dragged-in dependency is not added to the selection (its dependent stays selected and re-drags it).

7. **MISCONFIGURED with no executable step** (ambiguous Claude plugin duplicates, project pack with no detected repo, rejected pnpm names).
   - Recommendation: BLOCKED with the health reason, never "will reconfigure" with nothing to run. Confirm [ASSUMED: A9].

8. **PATH wiring / verify errors and the all-skipped run.** (Pitfall 12)
   - Recommendation: keep a run-level error beside the outcomes so a wiring failure still exits 1 and shows "Failed."; skip wiring/verify and terminal sync when `ran_anything` is false so "starts nothing" is literally true.

9. **Make `ExecuteInputs.version_refresh` required?**
   - Recommendation: yes in the type; give tests a default via `frozen_service`. The alternative (synthesizing a presence-only state from `installed`) keeps a second source of truth alive.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `manual` result ships now; `Disposition.MANUAL` + `needs_manual` are Phase 22's | Pattern 3, OQ3 | If Phase 20 must also produce plan-time MANUAL, a predicate and prefix-writability evidence are missing from this tree |
| A2 | BROKEN-by-drift -> REPAIR with the reason shown | Pattern 2, OQ2 | Silently overwrites a user-modified installer-owned binary after Enter |
| A3 | cwd via `sh -c 'cd -- "$1" && shift && exec "$@"'` | Pattern 6, Pitfall 4 | A wrapped argv breaks `StreamingRunner.unbuffered_argv`/stdbuf detection or a test fake that inspects `argv[0]` |
| A4 | Wait joins `service.refresh(whole catalog)` | Pattern 5, OQ4 | If the id sets differ (catalog list vs. `ExecuteInputs.catalog`) a second concurrent pass starts |
| A5 | `r` eligible when `owner == "installer"` and `OK`, receipt optional | Pitfall 9 | D-14's "by receipt or adoption" read strictly leaves the "reinstall with r to adopt" note false |
| A6 | `PlanRow` gains `can_reinstall`, `steps`, `ownership` (D-01 lists four fields) | Pattern 3 | Extra fields change D-01's literal signature; execution needs them or must re-read state (Pitfall 2) |
| A7 | Install-class failures (INSTALL/REPAIR/REINSTALL) propagate `dependency_failed`; UPDATE/RECONFIGURE failures do not | Pattern 3 | A failed update of a present dependency would wrongly block dependents |
| A8 | `ALREADY_INSTALLED` -> `skipped`; `NO_METHOD` -> `blocked` | Pattern 3 | Exit-code or retained-selection differences vs. today |
| A9 | MISCONFIGURED with no steps -> BLOCKED | OQ7 | Row stays selected forever |
| A10 | Extract `update_refusal` from `_perform` for plan use | Don't Hand-Roll | Review and engine drift apart (G case D) |
| A11 | Dragged rows grouped under requester at render time | Pitfall 15 | Reviewer reads wrong execution order |
| A12 | "will repair" (not "will repair (reinstall)") | Pattern 2 | A test pinned to the TA wording fails |
| A13 | `execute_plan` absorbs and deletes `run_installs`; widget plan region needs `max-height` + scroll | Structure, Pitfall 13 | Dead helper kept, or a long plan collapses the log |

## Sources

### Primary (HIGH confidence, read in this session)
- `20-CONTEXT.md`, `20-SPEC.md`, `20-DISCUSSION-LOG.md`; `19-CONTEXT.md` (D-02..D-09), `19-VERIFICATION.md`, `19-RESEARCH.md` (Pitfall 10), `19-REVIEW-2.md` (G21/WR-03); `21-CONTEXT.md` (D-05, integration points); `22-CONTEXT.md` (D-12..D-14)
- `.planning/research/2026-10-13-target-architecture.md` §2, §3, §3.1, §3.2, §6, §7, §9.2; `.planning/research/audit-2026-10-13/G-ui-health-states-and-reuse.md` (probe cases A-I, lines 246-258, 273-327)
- `AGENTS.md`, `.claude/architecture.md`, `.claude/testing.md`, `.claude/python-tooling.md`
- Code: `installer/session.py`, `deps.py`, `engine.py`, `execute_screen.py`, `wizard_app.py` (2480-2600, 2760-3114), `app.py`, `render.py`, `audit.py`, `update.py`, `version_status.py` (155-250, 600-780, 855-1090, 1495-1705), `catalog_tui.py` (286-530, 690-920), `tool_browser.py`, `ownership.py` (76-135, 300-320, 1310-1440), `model.py` (295-335), `skill_lifecycle.py` (490-525, 870-985), `enums.py`, `run.py`, `ui_common.py`, `cli.py`, `executors.py` (440-460), `selection.py`, `prompt.py`, `setup.py` (764-1330, 1472-1573)
- Tests/tooling: `tests/state_doubles.py`, `tests/test_execute_screen.py` (index, 160-300, 1479-1565, 4425-4520), `tests/test_docs.py`, `tests/conftest.py` head, `scripts/container-e2e-verify.sh` (236-255); `uv run pytest tests/test_session.py tests/test_deps.py` (passes)

### Secondary / Tertiary
- None. No external documentation was needed; the phase is internal. Textual primitives used (`@work(thread=True, exclusive=True, group=…)`, `ModalScreen.dismiss(result)`, `post_message`) are already exercised in `installer/execute_screen.py` and `installer/catalog_tui.py`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies; all seams read.
- Architecture: HIGH for the data flow and deletions; MEDIUM for the wait mechanism and the engine-result mapping (assumptions A1-A9).
- Pitfalls: HIGH - each is grounded in a line read this session.

**Research date:** 2026-10-17
**Valid until:** 2026-10-24 for line numbers (the tree is moving: Phases 21-23 touch the same files); the design findings hold until Phase 21 lands.
