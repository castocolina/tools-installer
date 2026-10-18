---
phase: 20-install-plan-with-dispositions
plan: "15"
subsystem: headless-install
tags: [python, selection, prompts, deletion]
requires:
  - phase: 20-install-plan-with-dispositions (plan 20-11)
    provides: Shared headless install plan and engine
  - phase: 20-install-plan-with-dispositions (plan 20-14)
    provides: Removal of legacy plan renderers and run summary
provides:
  - Removed the unreachable pre-flight audit and two-step choice builders
  - Reduced the headless prompter to confirmation only
  - Preserved the TUI selection and recommendation APIs
affects: [headless-install, selection, prompting]
actuals:
  tokens: 4689
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns:
    - Remove dead helpers and their tests with their final callers.
    - Keep the headless Prompter contract limited to actions its live route uses.
key-files:
  created: []
  modified:
    - installer/selection.py
    - installer/prompt.py
    - setup.py
    - tests/test_selection.py
    - tests/test_prompt.py
    - tests/test_app.py
    - installer/audit.py (deleted)
    - tests/test_audit.py (deleted)
key-decisions:
  - Kept Choice, select_tools, unstaged_recommends, categories, and tools_in for the TUI path.
  - Removed setup checkbox-only formatting helpers with _ask_checkbox because they had no other callers.
  - Kept macos_stub_reason because installer/status.py::is_installed still calls it.
requirements-completed: [PLAN-06]
coverage:
  - id: D1
    description: Removed the audit module and unused category/tool choice builders with their tests.
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_selection.py tests/test_status.py tests/test_app.py -n auto -q --no-cov"
        status: pass
    human_judgment: false
  - id: D2
    description: Reduced Prompter and CallbackPrompter to confirmation and removed checkbox wiring.
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_prompt.py tests/test_setup.py tests/test_app.py -n auto -q --no-cov"
        status: pass
    human_judgment: false
duration: "24 min (approx.)"
completed: 2026-10-18
status: complete
---

# Phase 20 Plan 15 Summary

**Removed the unreachable pre-flight audit and checkbox-selection flow; the headless route now asks only for confirmation, while TUI selection helpers remain intact.**

## Performance

- **Duration:** About 24 minutes
- **Started:** 2026-10-18 (start time not recorded)
- **Completed:** 2026-10-18
- **Tasks:** 2
- **Files changed:** 8 (6 modified, 2 deleted)

## Accomplishments

- Deleted `installer/audit.py`, `tests/test_audit.py`, and the unused `tool_choices`, `category_choices`, and `_is_verified_download` helper with their tests.
- Reduced `Prompter` and `CallbackPrompter` to `confirm`; removed `_ask_checkbox` and its checkbox-only setup helpers; updated the headless constructor and `FakePrompter`.
- Kept `Choice`, `select_tools`, `unstaged_recommends`, `categories`, and `tools_in` for the catalog TUI.

## Task Commits

1. **Task 1: Delete the pre-flight audit and choice builders** — `dbd5b16` (`refactor(20-15): delete the pre-flight audit and choice builders`)
2. **Task 2: Keep the headless prompter confirmation-only** — `3a4c113` (`refactor(20-15): the headless prompter asks only for confirmation`)

## Deleted Tests

- `tests/test_audit.py`: `test_audit_marks_each_tool_installed_or_missing`, `test_audit_preserves_order_and_handles_empty`, `test_audit_returns_the_stub_reason`, `test_audit_asks_for_a_reason_only_for_missing_rows`, and `test_audit_without_stub_reason_has_plain_missing_status`.
- `tests/test_selection.py`: `test_category_choices_count_tools_and_start_unchecked`, `test_category_choices_without_blurbs_defaults_to_tool_list`, `test_tool_choices_precheck_missing_only`, and `test_tool_choices_flag_verified_downloads`.
- `tests/test_prompt.py`: `test_select_categories_forwards_choices_and_returns_ids` and `test_select_tools_forwards_choices`.
- No `_ask_checkbox` test existed in `tests/test_setup.py`; `RecordingPrompter` and its test were already removed by plan 20-11.

## Verification Results

- Task 1 targeted tests: `uv run pytest tests/test_selection.py tests/test_status.py tests/test_app.py -n auto -q --no-cov` — passed.
- Task 1 full gate: `make validate && make test` — passed; 4,837 passed, 4 skipped, 96% coverage.
- Task 2 targeted tests: `uv run pytest tests/test_prompt.py tests/test_setup.py tests/test_app.py -n auto -q --no-cov` — passed after updating one remaining subclass call.
- Task 2 full gate: `make validate && make test` — passed; 4,835 passed, 4 skipped, 96% coverage. Ruff, format, pyright, bandit, vulture, and shellcheck hooks passed on commit.
- Acceptance gates passed: no `tool_choices`/`category_choices` definitions remain; `select_tools` remains; `Prompter` has two `confirm` definitions and no selection methods; setup constructs `CallbackPrompter(ask_confirm=_ask_confirm)` once; `tests/test_app.py` has no selection methods; no new suppressions were added.

## TDD RED Evidence

No TDD RED step was required: both plan tasks are deletion-only and the plan says not to add a RED step. The first Task 2 targeted run caught a stale `MustNotConfirm` constructor call after the prompt API changed. Updating it to use the confirmation-only constructor made the focused test and targeted suite pass.

## Required Grep Evidence

Task 1, before deletion (`git grep -n -e 'audit(' -e 'ToolStatus' -e 'tool_choices' -e 'category_choices' -e 'macos_stub_reason' -e 'from installer.audit' 6fdcdcd -- installer setup.py tests scripts`):

```text
6fdcdcd:installer/audit.py:7:from installer.status import is_installed, macos_stub_reason
6fdcdcd:installer/audit.py:11:class ToolStatus:
6fdcdcd:installer/audit.py:17:def audit(
6fdcdcd:installer/audit.py:20:    stub_reason: Callable[[Tool], str | None] = macos_stub_reason,
6fdcdcd:installer/audit.py:21:) -> list[ToolStatus]:
6fdcdcd:installer/audit.py:31:    statuses: list[ToolStatus] = []
6fdcdcd:installer/audit.py:35:        statuses.append(ToolStatus(tool=tool, installed=installed, reason=reason))
6fdcdcd:installer/selection.py:6:from installer.audit import ToolStatus
6fdcdcd:installer/selection.py:33:def category_choices(tools: list[Tool], blurbs: dict[str, str] | None = None) -> list[Choice]:
6fdcdcd:installer/selection.py:59:def tool_choices(statuses: list[ToolStatus]) -> list[Choice]:
6fdcdcd:installer/status.py:41:def macos_stub_reason(
6fdcdcd:installer/status.py:144:        and macos_stub_reason(tool, darwin=darwin, probe=probe, which=which) is None
6fdcdcd:installer/wizard_app.py:425:        self._start_globals_audit()
6fdcdcd:installer/wizard_app.py:443:            self._start_globals_audit()
6fdcdcd:installer/wizard_app.py:481:    def _start_globals_audit(self) -> None:
6fdcdcd:installer/wizard_app.py:769:            self._start_globals_audit()
6fdcdcd:installer/wizard_app.py:860:        self._start_globals_audit()
6fdcdcd:tests/test_audit.py:1:from installer.audit import ToolStatus, audit
6fdcdcd:tests/test_audit.py:22:    result = audit(tools, installed)
6fdcdcd:tests/test_audit.py:24:        ToolStatus(tool=tools[0], installed=True),
6fdcdcd:tests/test_audit.py:25:        ToolStatus(tool=tools[1], installed=False),
6fdcdcd:tests/test_audit.py:30:    assert audit([], lambda tool: True) == []
6fdcdcd:tests/test_audit.py:35:    result = audit([tool], lambda t: False, stub_reason=lambda t: "reason text")
6fdcdcd:tests/test_audit.py:36:    assert result == [ToolStatus(tool=tool, installed=False, reason="reason text")]
6fdcdcd:tests/test_audit.py:50:    audit(tools, installed, stub_reason=stub_reason)
6fdcdcd:tests/test_audit.py:56:    result = audit([tool], lambda t: False, stub_reason=lambda t: None)
6fdcdcd:tests/test_audit.py:57:    assert result == [ToolStatus(tool=tool, installed=False, reason=None)]
6fdcdcd:tests/test_selection.py:1:from installer.audit import ToolStatus
6fdcdcd:tests/test_selection.py:6:    category_choices,
6fdcdcd:tests/test_selection.py:8:    tool_choices,
6fdcdcd:tests/test_selection.py:40:def test_category_choices_count_tools_and_start_unchecked() -> None:
6fdcdcd:tests/test_selection.py:43:    assert category_choices(tools, blurbs) == [
6fdcdcd:tests/test_selection.py:55:def test_category_choices_without_blurbs_defaults_to_tool_list() -> None:
6fdcdcd:tests/test_selection.py:57:    assert category_choices(tools) == [
6fdcdcd:tests/test_selection.py:62:def test_tool_choices_precheck_missing_only() -> None:
6fdcdcd:tests/test_selection.py:65:        ToolStatus(tool=tools[0], installed=True),
6fdcdcd:tests/test_selection.py:66:        ToolStatus(tool=tools[1], installed=False),
6fdcdcd:tests/test_selection.py:68:    assert tool_choices(statuses) == [
6fdcdcd:tests/test_selection.py:76:def test_tool_choices_flag_verified_downloads() -> None:
6fdcdcd:tests/test_selection.py:90:    statuses = [ToolStatus(tool=verified, installed=False)]
6fdcdcd:tests/test_selection.py:91:    assert tool_choices(statuses)[0].description == "fast grep · sha256-verified download"
6fdcdcd:tests/test_status.py:15:    macos_stub_reason,
6fdcdcd:tests/test_status.py:487:    reason = macos_stub_reason(tool, darwin=True, probe=probe_fail)
6fdcdcd:tests/test_status.py:506:    assert macos_stub_reason(tool, darwin=True, probe=probe_ok) is None
6fdcdcd:tests/test_status.py:555:    reason = macos_stub_reason(tool, darwin=True, probe=probe_fail)
6fdcdcd:tests/test_status.py:705:    and macos_stub_reason reads the same lookup."""
6fdcdcd:tests/test_status.py:708:    reason = macos_stub_reason(
6fdcdcd:tests/test_status.py:732:    assert macos_stub_reason(_tool("jq"), darwin=True, probe=lambda _argv: True) is None
```

Task 2, before deleting the two-step prompter (`git grep -n -e "select_categories" -e "select_tools(" -e "_ask_checkbox" -e "ask_checkbox" -e "from installer.selection import Choice" dbd5b16 -- installer setup.py tests scripts`):

```text
dbd5b16:installer/catalog_tui.py:900:            for tool in select_tools(self._catalog, list(self._staged))
dbd5b16:installer/prompt.py:7:from installer.selection import Choice
dbd5b16:installer/prompt.py:16:    def select_categories(self, choices: list[Choice]) -> list[str]: ...
dbd5b16:installer/prompt.py:17:    def select_tools(self, choices: list[Choice]) -> list[str]: ...
dbd5b16:installer/prompt.py:23:    ask_checkbox: AskCheckbox
dbd5b16:installer/prompt.py:26:    def select_categories(self, choices: list[Choice]) -> list[str]:
dbd5b16:installer/prompt.py:27:        return self.ask_checkbox("Select categories", choices)
dbd5b16:installer/prompt.py:29:    def select_tools(self, choices: list[Choice]) -> list[str]:
dbd5b16:installer/prompt.py:30:        return self.ask_checkbox("Select tools", choices)
dbd5b16:installer/selection.py:32:def select_tools(tools: list[Tool], ids: list[str]) -> list[Tool]:
dbd5b16:installer/session.py:826:    chosen = select_tools(list(catalog), list(selected))
dbd5b16:setup.py:78:from installer.selection import Choice
dbd5b16:setup.py:310:def _ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
dbd5b16:setup.py:1543:    prompter = CallbackPrompter(ask_checkbox=_ask_checkbox, ask_confirm=_ask_confirm)
dbd5b16:tests/test_app.py:24:from installer.selection import Choice
dbd5b16:tests/test_app.py:82:    def select_categories(self, choices: list[Choice]) -> list[str]:
dbd5b16:tests/test_app.py:85:    def select_tools(self, choices: list[Choice]) -> list[str]:
dbd5b16:tests/test_catalog_tui.py:623:    selected = select_tools(tools, ids)
dbd5b16:tests/test_prompt.py:2:from installer.selection import Choice
dbd5b16:tests/test_prompt.py:7:        ask_checkbox=lambda message, choices: [],
dbd5b16:tests/test_prompt.py:13:def test_select_categories_forwards_choices_and_returns_ids():
dbd5b16:tests/test_prompt.py:16:    def ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
dbd5b16:tests/test_prompt.py:23:    prompter = CallbackPrompter(ask_checkbox=ask_checkbox, ask_confirm=ask_confirm)
dbd5b16:tests/test_prompt.py:25:    assert prompter.select_categories(choices) == ["search"]
dbd5b16:tests/test_prompt.py:32:    def ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
dbd5b16:tests/test_prompt.py:36:    prompter = CallbackPrompter(ask_checkbox=ask_checkbox, ask_confirm=lambda message: False)
dbd5b16:tests/test_prompt.py:38:    assert prompter.select_tools(choices) == ["rg"]
dbd5b16:tests/test_prompt.py:49:    prompter = CallbackPrompter(ask_checkbox=lambda message, choices: [], ask_confirm=ask_confirm)
dbd5b16:tests/test_selection.py:45:    assert [t.id for t in select_tools(tools, ["jq", "rg", "ghost"])] == ["rg", "jq"]
```

## Decisions and Rulings

- **Ruling:** The Task 1 grep also matched `installer/wizard_app.py`'s `_start_globals_audit` and calls. They audit pnpm-global inventory and do not call the deleted `installer.audit.audit`; kept them. Cost if wrong: a production caller of the deleted API could remain. The exact `installer.audit` references were checked separately.
- Kept `macos_stub_reason`; `installer/status.py::is_installed` still calls it.
- No plan deviations. Removed `_tag_class`, `_title`, and `_CHECKBOX_KEYS` as checkbox-only helpers made orphaned by deleting `_ask_checkbox`.

## Issues Encountered

- The first Task 2 targeted run exposed a stale `MustNotConfirm` constructor call after the prompt API changed. Updated it to use the confirmation-only constructor, then reran the focused test and targeted suite successfully.
- The first Task 2 `make validate` stopped at Ruff formatting because deleting `_CHECKBOX_KEYS` left too few blank lines. Ran Ruff's formatter and reran `make validate && make test` successfully.
- Three reviewer-subagent dispatch attempts returned HTTP 500. A separate self-review of the full diff found no Critical, Important, or Minor findings. A self-review is weaker than a fresh review; the orchestrator should decide whether it is sufficient.
- The plan helper `task-start` did not recognize the XML task format, so task progress was recorded manually. `tests/test_setup.py` required no change because it contained no `_ask_checkbox` test.
- `.planning/config.json` remains intentionally modified by the orchestrator and was not staged, reverted, or edited.

## Next Phase Readiness

Plan 20-15 is complete. The headless confirmation interface no longer exposes unused checkbox operations, and the TUI continues using the retained selection helpers. Only the orchestrator-owned `.planning/config.json` change remains outside the plan commits.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
