# Install Execution Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Catalog-to-Install flow visibly start, stream attributed output, apply the existing shell-layout workflow, and return a refreshed Catalog.

**Architecture:** Keep `session.run_plan` as the execution core. Extend its event stream and runners; make `InstallScreen` render explicit sections and failure states. Compose the existing `configure_path` closure into `UnifiedApp` rather than creating shellrc logic in the screen.

**Tech Stack:** Python 3.12, Textual, Rich, pytest.

## Global Constraints

- Use temporary homes and injected/stubbed runners in every E2E test.
- Never hand Textual's TTY to a package manager or change a real shell rc file in tests.
- Preserve manual handoffs for commands requiring a controlling terminal.

---

### Task 1: Model execution start and unexpected worker failure

**Files:**
- Modify: `installer/install_plan.py`, `installer/install_screen.py`
- Test: `tests/test_install_screen.py`

**Interfaces:**
- Produces `ExecutionEvent(tool_id, state, text, method=None)` states including `starting` and `failed`.
- Produces `InstallScreen.error: str | None` and `InstallScreen.started: bool`.

- [ ] **Step 1: Write the failing test**

```python
async def test_enter_marks_execution_starting_before_worker_output() -> None:
    app, install = _app_with_blocked_start()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        assert install.started is True
        assert "Installation starting" in install.output_text

async def test_unexpected_worker_error_is_rendered() -> None:
    app, install = _app_with_start_raising(RuntimeError("resolver offline"))
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert install.finished is True
        assert install.error == "resolver offline"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_install_screen.py -k 'starting or unexpected_worker_error' -v`

Expected: FAIL because the screen has no immediate event or worker error boundary.

- [ ] **Step 3: Write minimal implementation**

```python
def _execute(self) -> None:
    try:
        summary = self._start(choices, self._emit_from_worker)
    except Exception as exc:
        self.app.call_from_thread(self._fail, str(exc))
        return
    self.app.call_from_thread(self._finish, summary)
```

Set `started = True` and render a plan-level `Installation starting` state before calling `run_worker`. Do not add a fake tool row.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_install_screen.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/install_plan.py installer/install_screen.py tests/test_install_screen.py
git commit -m "fix(ui): surface install start and worker failures"
```

### Task 2: Build separated Install sections and readable live output

**Files:**
- Modify: `installer/install_screen.py`, `installer/run.py`, `installer/ui_common.py`
- Test: `tests/test_install_screen.py`, `tests/test_run.py`

**Interfaces:**
- Produces widgets `#install-review`, `#install-warnings`, `#install-approvals`, `#install-rows`, and `#install-output`.
- Produces normalized output events from `run_captured_command(cmd, sink)`.

- [ ] **Step 1: Write the failing test**

```python
async def test_install_screen_has_distinct_regions() -> None:
    app, _ = _app_with_install_screen([])
    async with app.run_test():
        assert app.query_one("#install-review")
        assert app.query_one("#install-warnings")
        assert app.query_one("#install-output")

def test_captured_runner_normalizes_carriage_return_progress() -> None:
    assert _normalized_chunks("a\rprogress\n") == ["progress"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_install_screen.py tests/test_run.py -k 'region or carriage_return' -v`

Expected: FAIL because plan content is one static widget and output is line-only.

- [ ] **Step 3: Write minimal implementation**

Render review, warnings, and approvals with separate widgets. Give warnings an explicit orange style. Extract a pure `normalize_output_chunks(text: str) -> list[str]` used by the captured runner; it must replace a carriage-return progress line without losing the final newline line. Keep commands that need a TTY as manual handoffs.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_install_screen.py tests/test_run.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/install_screen.py installer/run.py installer/ui_common.py tests/test_install_screen.py tests/test_run.py
git commit -m "feat(ui): separate install review from live output"
```

### Task 3: Reuse shell-layout selection and configure PATH after install

**Files:**
- Modify: `setup.py`, `installer/wizard_app.py`, `installer/install_screen.py`
- Test: `tests/test_setup.py`, `tests/test_wizard_app.py`, `tests/test_installer_workflow_e2e.py`

**Interfaces:**
- Produces `path_setup: Callable[[InstallPlan, Summary], PolicyResult | None]` injected into `UnifiedApp`.
- Consumes existing `_resolve_link_mode`, `rc_paths_for_mode`, and `configure_path`.

- [ ] **Step 1: Write the failing test**

```python
async def test_completed_path_managed_plan_runs_injected_path_setup() -> None:
    calls: list[tuple[str, ...]] = []
    app = _app(start_install=_install_fd,
               path_setup=lambda plan, summary: calls.append(plan.selected_ids))
    async with app.run_test() as pilot:
        await pilot.press("space", "enter", "enter")
        await pilot.pause()
    assert calls == [("fd",)]
```

Add a setup composition test proving normal interactive setup calls `_resolve_link_mode(None)` only after a selected plan contains a managed bin directory.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_setup.py tests/test_wizard_app.py -k 'path_setup or link_mode' -v`

Expected: FAIL because normal interactive setup never invokes the chooser or `configure_path` after execution.

- [ ] **Step 3: Write minimal implementation**

Use the existing `_resolve_link_mode` after plan construction and before approval only when `collect_bin_dirs(plan.ordered, ...)` is nonempty. Bind a closure that calls existing `configure_path`; invoke it only after successful/already-installed PATH-managed tools. Do not create another shellrc writer.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_setup.py tests/test_wizard_app.py tests/test_installer_workflow_e2e.py -v`

Expected: PASS using `tmp_path` and stubbed runners.

- [ ] **Step 5: Commit**

```bash
git add setup.py installer/wizard_app.py installer/install_screen.py tests/test_setup.py tests/test_wizard_app.py tests/test_installer_workflow_e2e.py
git commit -m "fix(setup): reuse shell layout workflow after installs"
```

