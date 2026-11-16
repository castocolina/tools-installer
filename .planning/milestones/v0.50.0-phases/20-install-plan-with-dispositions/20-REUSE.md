# Phase 20: Ponytail reuse pass (plans 20-04 .. 20-19)

Read-only audit, ultra level. Scope: every new function, module, class, dataclass, enum or helper in 20-04..20-19.
Locked decisions D-01..D-17 and L-20-01..09 were not re-argued: `Disposition`, `PlanRow`, `build_plan`, `RowOutcome`,
`WORDS`, `execute_plan`, `_await_state`, `ConfigStep` dispatch, `update_refusal` and the cwd shim are all taken as given.
Line numbers are from the tree at `9e35fb9`; 20-01..03 had not landed when this was written.

Each section below is an Orchestrator note: the executor applies it inside the named plan without replanning.

## 20-17 (also touches 20-11, 20-12, 20-18) -- three copies of "frozen service plus published presence"

### Finding 17-1 -- Important -- Task 1 and Task 2 -- new `_inputs(present=, states=)` body, `_execute_inputs(...)`, and 20-11's `_service(tools, present=, states=)`
- New symbols: the publish-presence block inside `tests/test_execute_screen.py::_inputs` (20-17 T1), `tests/test_wizard_app.py::_execute_inputs` (20-17 T2, "mirrors `_inputs`"), and `tests/test_app.py::_service` (20-11 T1).
- Existing helper: `tests/state_doubles.py:163` `frozen_service(home)` and `:137-144` `FrozenStateService.publish`, plus the new `plan_state` (20-04) next to `pass_state` (`state_doubles.py:200`).
- Instruction: all three helpers do the same thing: `frozen_service(Path.home() / "state")`, then `publish([plan_state(tool, health=OK if tool.id in present else MISSING) for tool in catalog] + list(states))`. Write that once as a public `presence_service(catalog, *, present=(), states=())` in `tests/state_doubles.py`, added in 20-17 Task 1 right after `plan_state` is available (20-04). Then `_inputs`, `_execute_inputs` and 20-11's `_service` each become a one-line call to it (20-11's `_service` can be dropped and call sites use `presence_service` directly). Keep `_inputs` and `_execute_inputs` as thin wrappers only for their ExecuteInputs defaults (`wire_path`, `verify`, `install`, `platform`); do not copy the publish logic into either. 20-12 and 20-18 already say they reuse `_inputs`/`_execute_inputs`, so they need no change.

## 20-07 -- `UpdateRunner` Protocol and a from-scratch `ScriptedUpdates`

### Finding 07-1 -- Important -- Task 1 (`UpdateRunner`, `ScriptedUpdates`)
- New symbols: `session.UpdateRunner` (Protocol with `in_flight`, `begin`, `end`, `run`) and `state_doubles.ScriptedUpdates` ("not a subclass").
- Existing helper: `tests/test_execute_screen.py:1502-1519` `_RecordingUpdateService(UpdateService)` (an inert-constructor subclass that overrides only `run`; 13 more subclasses build on it at `:2035`, `:2256`, `:2271`, `:2434`, `:3390`, `:4174` ...) and `tests/test_catalog_tui.py:3764` `_FailingUpdateService(UpdateService)`. `UpdateService.begin/end/in_flight` (`installer/update.py:476-492`) are already the real latch and are trivial.
- Instruction: do not add the Protocol. Type `RunContext.updates` as `UpdateService | None` (it is already the type `ExecuteInputs.updates` uses). Build `ScriptedUpdates` in `tests/state_doubles.py` as `class ScriptedUpdates(UpdateService)` whose `__init__` is the inert `super().__init__(platform=_MACOS, runner=lambda _c: None, resolve_tag=lambda _r: "v1", tools={}, managed_packages=lambda: (), replay_globals=lambda p: tuple(p), reresolve_ownership=unknown_ownership)` from `_RecordingUpdateService`, overriding only `run` (look up `outcomes[target.tool.id]`, raise if the value is an Exception, record the target). The latch tests (`test_update_latch_refusal_is_blocked`) then use the inherited `begin`/`in_flight` for real, which is a stronger test than a scripted `begin`; to force a refusal, call `updates.begin("rg")` on the double before `execute_plan`. This deletes one Protocol and one hand-written method set. Optionally promote `_RecordingUpdateService` itself into `state_doubles.py` for the 20-10 port, but that is not required.

### Finding 07-2 -- Minor -- Task 1 (`summary_counts`) with 20-04 `review_counts`
- New symbols: `session.summary_counts` (20-07) next to `session.review_counts` (20-04).
- Existing helper: `review_counts` itself (20-04 T1), which already does "non-zero counts by word, in table order, comma-joined, `nothing selected` when empty".
- Instruction: in 20-04 write one private `_count_line(words: Iterable[str], order: Sequence[str]) -> str` (a `Counter(words)` filtered by `order`, joined with `, `, empty -> `nothing selected`). `review_counts(rows)` calls it with the review words, `summary_counts(outcomes)` (20-07) calls it with the done/result words. Do not write the join and the empty-string rule twice.

## 20-06 -- renderer folding and glyph alias

### Finding 06-1 -- Important -- Task 1/2 (`fold_reason`)
- New symbol: `render.fold_reason(prefix, body, column, width)`: hand-written space-splitting, hanging indent and "clamp a long word by slicing at `width - column` cells".
- Existing helper: stdlib `textwrap.wrap(body, width - column, break_long_words=True)` (does exactly the break-at-spaces plus clamp-long-word rule), or Rich's `Text.wrap(console, width)` already used for the same job at `installer/tool_browser.py:82-92` (`_cut_rows`: `list(text.wrap(console, width))`, then `.truncate(width, overflow="ellipsis")`).
- Instruction: implement `fold_reason` as the loop over `textwrap.wrap(...)` chunks (first chunk appended to `prefix`, the rest as `"\n" + " " * column + chunk`); the "clamp" paragraph and the custom splitter disappear. Keep the public name and signature because 20-09 and 20-10 call it. Keep every test in 20-06 T2 (they pin behaviour, not the splitter). If `cell_len` accuracy for wide glyphs matters, use `Text(body).wrap(Console(width=width - column), width - column)`; either beats a new splitter.

### Finding 06-2 -- Minor -- Task 1 (`_HEALTH_CELL = HEALTH_MARKS` alias)
- New symbol: the alias line in `installer/catalog_tui.py`.
- Existing: `catalog_tui.py:249` (the table), used at `:110`, `:130`, `:639`; no test references `_HEALTH_CELL` (checked `tests/`).
- Instruction: move the table to `version_status.HEALTH_MARKS` as planned, then rename the three uses in `catalog_tui.py` to `HEALTH_MARKS` instead of keeping an alias. Same diff size, one less name. The 20-06 acceptance line `grep -c "^_HEALTH_CELL = HEALTH_MARKS"` becomes `grep -c "_HEALTH_CELL" installer/catalog_tui.py` is 0.

## 20-18 -- test nobody needs

### Finding 18-1 -- Important -- Task 1 (`test_a_never_selects_an_unavailable_row`)
- New symbol: that test (D-05 pin through the app).
- Existing: `tests/test_catalog_tui.py:904` `test_unavailable_catalog_rows_are_inert_under_select_all` (press `a`, unavailable row not in `selected`) and `:4109` `test_unavailable_state_dims_and_blocks_selection` (space and `a` on an UNAVAILABLE state row). The plan itself says D-05 "needs no code: Phase 19 already made it so".
- Instruction: drop this test and its acceptance grep from 20-18. D-05 is already pinned twice. If the orchestrator wants a plan-side pin, add one assertion to `test_a_and_enter_use_the_same_plan_order_as_the_headless_route` that no row in the review has `Health.UNAVAILABLE` when the tier contains an unavailable tool, rather than a fourth test.

## 20-10 -- fields no task reads

### Finding 10-1 -- Minor -- Task 1 (screen state)
- New symbols: `self._outcomes: dict[str, RowOutcome]` and `self._wait_token: int` in `ExecuteScreen.__init__`.
- Existing: the screen already holds the final list in `self.outcomes` and a local `collected` in the worker; no 20-10 step reads `_outcomes`. `_wait_token` is first read in 20-12.
- Instruction: do not add `_outcomes` at all, and add `_wait_token` in 20-12 Task 1 together with `_waiting` (its first reader). Keep `_start_requested` and `_reinstall` in 20-10 because `action_start` and `_replan` use them there.

## 20-12 -- truncation helper

### Finding 12-1 -- Minor -- Task 2 (`_fit`)
- New symbol: `_fit(text, budget)`: cell-width truncation with `...`.
- Existing: Rich `Text.truncate(width, overflow="ellipsis")`, used exactly this way at `installer/tool_browser.py:89-90`.
- Instruction: build the error as `err = Text(error); err.truncate(budget, overflow="ellipsis")` and `str(err)` (or append it) into the status; drop `_fit`. Keep the budget arithmetic and the 78-cell test.

## 20-08 -- cwd validation

### Finding 08-1 -- Minor -- Task 1 (`_valid_cwd`)
- New symbol: `_valid_cwd` (absolute, `lstat` is a directory, not a symlink).
- Existing: `installer/skill_lifecycle.py:365-371` `_lstat_mode` and the `stat.S_ISDIR(_lstat_mode(...))` admission rule at `:386-388` that produced the repo path in the first place.
- Instruction: write it as two checks, `path.is_absolute()` and `stat.S_ISDIR(path.lstat().st_mode)` inside `try/except OSError`. The separate `S_ISLNK` test is redundant: `lstat` on a symlink reports `S_ISLNK`, so `S_ISDIR` is already false. Keep the three parametrized refusal tests. (Do not import the private `_lstat_mode` across modules.)

## 20-05 -- duplicate no-sudo pin

### Finding 05-1 -- Minor -- Task 1 (`test_no_sudo_argv_on_the_plan_path`)
- New symbol: a pytest that reads `installer/session.py` and `installer/deps.py` for `sudo|pkexec|doas` literals.
- Existing: the same check is already the plan's own `<automated>` `bash -c '! grep -nE "\"(sudo|pkexec|doas)\"" installer/session.py installer/deps.py'` gate in the same task, and the pytest-style banned-word check pattern lives at `tests/test_render.py:737` (output based).
- Instruction: keep the shell gate (it runs on every verify) and drop the pytest, or keep the pytest and drop the shell gate. One of them. The behavioural pin that matters is the parametrized `test_broken_tool_owned_by_a_native_manager_is_blocked_never_repaired`, which stays.

## 20-13 -- redundant budget test

### Finding 13-1 -- Minor -- Task 2 (`test_unproven_note_fits_the_detail_budget`)
- New symbol: the `len(UNPROVEN_NOTE) <= 156` test.
- Existing: `_UNPROVEN` in `tests/test_version_status.py` (~line 4212) already pins the exact string; the new string is 69 characters, so the length bound can never fail without the equality pin failing first.
- Instruction: drop the budget test; the exact-string pin is the budget guard.

## No findings

- 20-04: the types, `WORDS`/`RESULT_WORDS`, `plan_state` over `pass_state` (`state_doubles.py:200`), `_first_clause`, reuse of `resolve_dependencies`, `select_tools`, `resolve_methods`, `owner_label`, `declared_manager_label` are all justified (only the shared count line in 07-2 applies).
- 20-09: `summary_head`, `outcome_row_text`, `running_row_text` reuse `fold_reason`, `WORDS`, `RESULT_WORDS`, `HEALTH_MARKS`, `sanitize_log_line`; nothing duplicated.
- 20-11: `run_wizard` rewrite reuses `build_plan`, `execute_plan`, the existing `confirm_sensitive` closure and the render helpers; only the test-helper duplication in 17-1 applies.
- 20-14, 20-15: pure deletions with grep gates; no new symbols.
- 20-16: docs pin follows `_PHASE_19_REQUIRED` exactly.
- 20-19: edits the existing `SUMMARY_RE`/`parse_summary_line` in place; the self-checks are sourced from the script itself.

Not checked: 20-01..03 (out of scope), runtime behaviour, and whether the Rich `Text.wrap` / `textwrap` suggestion in 06-1 keeps the exact UI-SPEC folding at wide glyphs (the 20-06 tests will say).
