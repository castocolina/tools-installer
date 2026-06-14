# Unified UI Phase 3 — Uninstall View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `"uninstall"` placeholder in the unified Textual app with a real view that lists tools with removable artifacts as toggles, adds explicit pip/npm-ban and PATH-wiring toggles, and live-applies the chosen removals in place.

**Architecture:** Three pure/IO core seams (`has_managed_block`, `removable_tools`, `perform_uninstall`) back a `UninstallScreen` that mirrors Phase 2's `FixScreen` live-apply lifecycle. The screen calls an injected `remove` closure synchronously, then flips to an applied state with reload guidance. The app's run value is unchanged (`list[str] | None`); removal mutates the filesystem directly. `setup.py` (the coverage-excluded IO boundary) builds the inputs and the closure, and opens the app on this view for interactive `--uninstall`.

**Tech Stack:** Python 3 (uv), Textual (headless `app.run_test`), pytest with 100% coverage on `installer/`, ruff/pyright-strict/bandit/vulture via `make validate`.

**Source spec:** `docs/superpowers/specs/2026-06-14-unified-ui-phase3-design.md`

---

## File Structure

- **`installer/shellrc.py`** *(modify)* — add pure `has_managed_block(path)`.
- **`installer/uninstall.py`** *(modify)* — add pure `removable_tools(tools, default_bin_dir)`.
- **`installer/app.py`** *(modify)* — add `UninstallDecision` dataclass + `perform_uninstall(...)` next to `run_uninstall` (reuses app.py's existing remover imports — no new import edges).
- **`installer/wizard_app.py`** *(modify)* — add `UninstallInputs` dataclass + `UninstallScreen`; replace the `"uninstall"` placeholder; thread `UninstallInputs` through `UnifiedApp.__init__`.
- **`setup.py`** *(modify, IO boundary)* — build `UninstallInputs` + `remove` closure in `_build_app`; add the interactive branch to `_run_uninstall`.
- **Tests:** `tests/test_shellrc.py`, `tests/test_uninstall.py`, `tests/test_app.py`, `tests/test_wizard_app.py`.
- **E2E (agent-driven):** `tests/test_uninstall_e2e.py` — (a) drives the *real* `UnifiedApp` through the *real* removal core against a sandboxed HOME and asserts real artifacts are gone; (b) captures a labeled **UX journey** of SVG screenshots (open → empty-refusal → selected → applied → error) into `.e2e-artifacts/ux/`. A safety subagent (Task 9) inspects the removal screenshot and proves real-home is untouched; a `ui-ux-designer` subagent (Task 10) role-plays the end user and critiques the journey. `.gitignore` ignores `.e2e-artifacts/`.
- **Docs:** `README.md`, `memory/roadmap-status.md`.

---

## Task 1: `has_managed_block` predicate (pure, shellrc)

**Files:**
- Modify: `installer/shellrc.py`
- Test: `tests/test_shellrc.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_shellrc.py` (import `has_managed_block` in the existing import line from `installer.shellrc`):

```python
def test_has_managed_block_true_when_markers_present(tmp_path: Path) -> None:
    from installer.shellrc import has_managed_block, write_myshellrc

    rc = tmp_path / ".myshellrc"
    write_myshellrc([tmp_path / "bin"], rc)
    assert has_managed_block(rc) is True


def test_has_managed_block_false_for_plain_or_missing_file(tmp_path: Path) -> None:
    from installer.shellrc import has_managed_block

    missing = tmp_path / "nope"
    assert has_managed_block(missing) is False
    plain = tmp_path / ".myshellrc"
    plain.write_text("export EDITOR=vim\n")
    assert has_managed_block(plain) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_shellrc.py -k has_managed_block -v`
Expected: FAIL with `ImportError: cannot import name 'has_managed_block'`.

- [ ] **Step 3: Implement the predicate**

In `installer/shellrc.py`, add directly after `remove_managed_block` (it reuses the same `_PATH_BEGIN` marker and line-based check as `strip_block`):

```python
def has_managed_block(path: Path) -> bool:
    """True when `path` exists and contains the managed PATH block markers."""
    if not path.exists():
        return False
    return _PATH_BEGIN in path.read_text().split("\n")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_shellrc.py -k has_managed_block -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add installer/shellrc.py tests/test_shellrc.py
git commit -m "feat: add has_managed_block predicate for PATH-wiring toggle"
```

---

## Task 2: `removable_tools` helper (pure, uninstall)

**Files:**
- Modify: `installer/uninstall.py`
- Test: `tests/test_uninstall.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_uninstall.py` (it already has `_tool`, `Method`, `Tool`, `tmp_path`, `monkeypatch` patterns):

```python
def test_removable_tools_lists_only_tools_with_existing_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from installer.uninstall import removable_tools

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("binary")
    dl_tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),
        tool_id="fd",
        cmd="fd",
    )
    brew_tool = _tool(Method(kind="brew", params={"formula": "x"}), tool_id="b", cmd="b")

    result = removable_tools([dl_tool, brew_tool], bin_dir)

    assert [tool.id for tool, _ in result] == ["fd"]  # brew tool dropped (no artifacts)
    assert result[0][1] == [opt]  # the existing artifact path


def test_removable_tools_empty_when_nothing_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from installer.uninstall import removable_tools

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    dl_tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"})
    )
    assert removable_tools([dl_tool], bin_dir) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_uninstall.py -k removable_tools -v`
Expected: FAIL with `ImportError: cannot import name 'removable_tools'`.

- [ ] **Step 3: Implement the helper**

In `installer/uninstall.py`, add after `plan_uninstall`:

```python
def removable_tools(tools: list[Tool], default_bin_dir: Path) -> list[tuple[Tool, list[Path]]]:
    """Tools that have userspace artifacts on disk, each paired with its paths.

    A tool is included only when `plan_uninstall([tool], default_bin_dir)` is
    non-empty, so cask/brew/native-managed tools (nothing to remove) are dropped.
    Order follows the input list.
    """
    result: list[tuple[Tool, list[Path]]] = []
    for tool in tools:
        paths = plan_uninstall([tool], default_bin_dir)
        if paths:
            result.append((tool, paths))
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_uninstall.py -k removable_tools -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add installer/uninstall.py tests/test_uninstall.py
git commit -m "feat: add removable_tools helper for the uninstall view"
```

---

## Task 3: `UninstallDecision` + `perform_uninstall` (app.py)

**Files:**
- Modify: `installer/app.py` (add next to `run_uninstall`, ~line 257; reuses existing imports of `remove_paths`, `remove_shims`, `remove_ban_aliases`, `remove_managed_block`)
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app.py` (uses `tmp_path`; build artifacts + ban + block, then assert selective removal):

```python
def test_perform_uninstall_removes_only_chosen_levers(tmp_path: Path) -> None:
    from installer.app import UninstallDecision, perform_uninstall
    from installer.shellrc import write_myshellrc

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    artifact = bin_dir / "fd"
    artifact.write_text("binary")
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)  # writes the managed PATH block

    # Only the artifact is selected; ban + path-block left intact.
    decision = UninstallDecision(paths=(artifact,), remove_ban=False, remove_path_block=False)
    perform_uninstall(decision, bin_dir=bin_dir, myshellrc_path=myshellrc, rc_paths=[])

    assert not artifact.exists()
    assert "tools-installer path" in myshellrc.read_text()  # block preserved


def test_perform_uninstall_removes_path_block_when_chosen(tmp_path: Path) -> None:
    from installer.app import UninstallDecision, perform_uninstall
    from installer.shellrc import write_myshellrc

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)

    decision = UninstallDecision(paths=(), remove_ban=True, remove_path_block=True)
    perform_uninstall(decision, bin_dir=bin_dir, myshellrc_path=myshellrc, rc_paths=[myshellrc])

    assert "tools-installer path" not in myshellrc.read_text()  # block stripped
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_app.py -k perform_uninstall -v`
Expected: FAIL with `ImportError: cannot import name 'UninstallDecision'`.

- [ ] **Step 3: Implement the dataclass + function**

At the top of `installer/app.py`, add `from dataclasses import dataclass` to the imports. Then add directly after `run_uninstall` (the closing `return paths` near line 288):

```python
@dataclass(frozen=True)
class UninstallDecision:
    """The levers the in-app uninstall view collected: selected artifact paths,
    plus whether to also remove the pip/npm ban and the managed PATH block."""

    paths: tuple[Path, ...]
    remove_ban: bool
    remove_path_block: bool


def perform_uninstall(
    decision: UninstallDecision,
    *,
    bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
) -> None:
    """Apply exactly the levers the view chose, composing the existing core
    removers. Unlike `run_uninstall`, nothing is removed all-or-nothing: a
    partial selection leaves the ban and PATH wiring untouched."""
    remove_paths(list(decision.paths))
    if decision.remove_ban:
        remove_shims(bin_dir)
        remove_ban_aliases(myshellrc_path)
        for rc_path in rc_paths:
            remove_ban_aliases(rc_path)
    if decision.remove_path_block:
        remove_managed_block(myshellrc_path)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_app.py -k perform_uninstall -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add installer/app.py tests/test_app.py
git commit -m "feat: add UninstallDecision and perform_uninstall composer"
```

---

## Task 4: `UninstallScreen` + `UninstallInputs`, wired into the app

**Files:**
- Modify: `installer/wizard_app.py`
- Test: `tests/test_wizard_app.py`

This task adds the screen with navigation only (no toggling yet) so the app compiles and the `"uninstall"` placeholder is replaced. Toggling/apply come in Tasks 5–6.

- [ ] **Step 1: Update the test helper and write the failing navigation test**

In `tests/test_wizard_app.py`, extend the `_app` helper to provide uninstall inputs, and import the new symbols. Replace the import block and `_app` with:

```python
from installer.app import UninstallDecision
from installer.wizard_app import (
    VIEW_ORDER,
    DoctorScreen,
    FixScreen,
    NavScreen,
    PlaceholderScreen,
    UnifiedApp,
    UninstallInputs,
    UninstallScreen,
)


def _uninstall_inputs(
    *,
    removable: list[tuple[Tool, list[Path]]] | None = None,
    ban_names: list[str] | None = None,
    has_path_block: bool = False,
    remove: Callable[[UninstallDecision], None] = lambda _decision: None,
) -> UninstallInputs:
    return UninstallInputs(
        removable=removable if removable is not None else [],
        ban_names=ban_names if ban_names is not None else [],
        has_path_block=has_path_block,
        remove=remove,
    )
```

Then add `uninstall: UninstallInputs | None = None` to `_app`'s keyword args and pass `uninstall=uninstall or _uninstall_inputs()` into `UnifiedApp(...)`. Add this test:

```python
async def test_uninstall_view_is_reachable() -> None:
    app = _app(uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert app.current_view == "uninstall"
        assert isinstance(app.screen, UninstallScreen)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_wizard_app.py -k uninstall_view_is_reachable -v`
Expected: FAIL with `ImportError: cannot import name 'UninstallInputs'`.

- [ ] **Step 3: Implement `UninstallInputs` + a minimal `UninstallScreen` and wire them in**

In `installer/wizard_app.py`:

Add imports near the top:

```python
from dataclasses import dataclass
from pathlib import Path

from installer.app import UninstallDecision
from installer.uninstall import removable_tools  # noqa: F401  (re-export convenience; remove if unused)
```

(If `removable_tools` is not referenced in `wizard_app.py`, omit that import — it is only used by `setup.py`.)

Add the inputs dataclass after the module constants:

```python
@dataclass(frozen=True)
class UninstallInputs:
    """Everything the UninstallScreen needs: the listable tools with their
    artifact paths, the active ban names, whether a managed PATH block exists,
    and the live removal closure bound by the composition root."""

    removable: list[tuple[Tool, list[Path]]]
    ban_names: list[str]
    has_path_block: bool
    remove: Callable[[UninstallDecision], None]
```

Add the screen (full implementation; Tasks 5–6 only add tests against it):

```python
class UninstallScreen(Screen[None]):
    """Toggle tools (and the ban / PATH wiring) to remove, then apply live."""

    _BAN_KEY = "#ban"
    _BLOCK_KEY = "#path-block"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle", "toggle", show=True),
        Binding("a", "select_all", "all"),
        Binding("i", "invert", "invert"),
        Binding("enter", "remove", "remove selected", show=True, priority=True),
    ]
    DEFAULT_CSS = """
    UninstallScreen #uninstall-status { dock: bottom; height: 1; padding: 0 1; color: $warning; }
    UninstallScreen DataTable { height: 1fr; }
    """

    def __init__(self, inputs: UninstallInputs) -> None:
        super().__init__()
        self._removable = inputs.removable
        self._paths_by_id: dict[str, list[Path]] = {t.id: paths for t, paths in inputs.removable}
        self._ban_names = inputs.ban_names
        self._has_path_block = inputs.has_path_block
        self._remove = inputs.remove
        # Public test seams (Phase 1/2 convention).
        self.selected: set[str] = set()
        self.remove_ban = False
        self.remove_path_block = False
        self.applied = False
        self.error: str | None = None
        self.status_text = ""

    def compose(self) -> ComposeResult:
        yield DataTable()
        yield Static("", id="uninstall-status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable[object])
        table.cursor_type = "row"
        table.add_column("Sel", key="sel")
        table.add_column("Item", key="item")
        table.add_column("Removes", key="removes")
        for tool, paths in self._removable:
            table.add_row(self._mark(False), Text(tool.id, style="bold"),
                          Text(f"{len(paths)} artifact(s)", style="dim"), key=tool.id)
        if self._ban_names:
            table.add_row(self._mark(False), Text("pip/npm ban", style="bold yellow"),
                          Text(f"shims + aliases ({', '.join(self._ban_names)})", style="dim"),
                          key=self._BAN_KEY)
        if self._has_path_block:
            table.add_row(self._mark(False), Text("PATH wiring", style="bold yellow"),
                          Text("managed block in ~/.myshellrc", style="dim"), key=self._BLOCK_KEY)
        if table.row_count == 0:
            self._set_status("Nothing to uninstall.", style="green")
        table.focus()

    # -- helpers --------------------------------------------------------------
    def _mark(self, chosen: bool) -> Text:
        return Text("[x]" if chosen else "[ ]", style="green" if chosen else "")

    def _toggleable_keys(self) -> list[str]:
        keys = [tool.id for tool, _ in self._removable]
        if self._ban_names:
            keys.append(self._BAN_KEY)
        if self._has_path_block:
            keys.append(self._BLOCK_KEY)
        return keys

    def _is_chosen(self, key: str) -> bool:
        if key == self._BAN_KEY:
            return self.remove_ban
        if key == self._BLOCK_KEY:
            return self.remove_path_block
        return key in self.selected

    def _set_chosen(self, key: str, chosen: bool) -> None:
        if key == self._BAN_KEY:
            self.remove_ban = chosen
        elif key == self._BLOCK_KEY:
            self.remove_path_block = chosen
        elif chosen:
            self.selected.add(key)
        else:
            self.selected.discard(key)
        self.query_one(DataTable[object]).update_cell(key, "sel", self._mark(chosen))

    def _highlighted_key(self) -> str | None:
        table = self.query_one(DataTable[object])
        if table.row_count == 0:
            return None
        cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        return cell_key.row_key.value

    def _set_status(self, text: str, *, style: str) -> None:
        self.status_text = text
        self.query_one("#uninstall-status", Static).update(Text(text, style=style))

    def _nothing_chosen(self) -> bool:
        return not self.selected and not self.remove_ban and not self.remove_path_block

    # -- actions --------------------------------------------------------------
    def action_toggle(self) -> None:
        if self.applied:
            return
        key = self._highlighted_key()
        if key is None:
            return
        self._set_chosen(key, not self._is_chosen(key))

    def action_select_all(self) -> None:
        if self.applied:
            return
        for key in self._toggleable_keys():
            self._set_chosen(key, True)

    def action_invert(self) -> None:
        if self.applied:
            return
        for key in self._toggleable_keys():
            self._set_chosen(key, not self._is_chosen(key))

    def action_remove(self) -> None:
        if self.applied or not self._toggleable_keys():
            return
        if self._nothing_chosen():
            self._set_status("Select at least one item to remove.", style="yellow")
            return
        paths: list[Path] = []
        for tool, tool_paths in self._removable:
            if tool.id in self.selected:
                paths.extend(tool_paths)
        decision = UninstallDecision(
            paths=tuple(paths), remove_ban=self.remove_ban, remove_path_block=self.remove_path_block
        )
        try:
            self._remove(decision)
        except OSError as exc:
            self.error = str(exc)
            self._set_status(f"Uninstall failed: {exc}. Check permissions, then press enter.",
                             style="red")
            return
        self.error = None
        self.applied = True
        self._set_status(self._applied_summary(len(paths)), style="green")

    def _applied_summary(self, removed: int) -> str:
        parts = [f"Removed {removed} item(s)."]
        if self.remove_ban:
            parts.append("pip/npm ban removed — open a new shell or run `hash -r`.")
        if self.remove_path_block:
            parts.append("PATH wiring removed — restart your shell to drop the managed dirs.")
        return "  ".join(parts)
```

Add the required Textual imports to the existing import lines: `Coordinate` from `textual.coordinate`, and ensure `DataTable` is imported from `textual.widgets` (add it to the existing `from textual.widgets import ...` line alongside `Label, ListItem, ListView, Static`).

Then in `UnifiedApp.__init__`, add a parameter `uninstall: UninstallInputs` (keyword-only, alongside the others) and replace the placeholder entry:

```python
            "uninstall": UninstallScreen(uninstall),
```

(removing the `PlaceholderScreen(_PLACEHOLDER_TEXT["uninstall"])` line and the now-unused `"uninstall"` key from `_PLACEHOLDER_TEXT`).

- [ ] **Step 4: Run the navigation test (and the full wizard suite) to verify**

Run: `uv run pytest tests/test_wizard_app.py -v`
Expected: PASS — `test_uninstall_view_is_reachable` passes; the existing `test_number_key_navigates_to_each_view` still passes (now landing on a real `UninstallScreen`).

- [ ] **Step 5: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "feat: add UninstallScreen and wire it into the unified app"
```

---

## Task 5: Toggling, select-all, invert

**Files:**
- Test: `tests/test_wizard_app.py`

The behavior is already implemented in Task 4; this task pins it with tests.

- [ ] **Step 1: Write the failing tests**

```python
async def test_uninstall_toggle_selects_highlighted_tool() -> None:
    app = _app(uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("space")
        assert app.screen.selected == {"rg"}
        await pilot.press("space")
        assert app.screen.selected == set()


async def test_uninstall_select_all_includes_ban_and_block() -> None:
    inputs = _uninstall_inputs(
        removable=[(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip", "npm"],
        has_path_block=True,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("a")
        assert app.screen.selected == {"rg"}
        assert app.screen.remove_ban is True
        assert app.screen.remove_path_block is True
        await pilot.press("i")  # invert clears everything
        assert app.screen.selected == set()
        assert app.screen.remove_ban is False
        assert app.screen.remove_path_block is False
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -k "uninstall_toggle or uninstall_select_all" -v`
Expected: PASS (2 passed). (Implementation already exists from Task 4.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_wizard_app.py
git commit -m "test: cover uninstall toggle, select-all, and invert"
```

---

## Task 6: Live apply, empty refusal, and error path

**Files:**
- Test: `tests/test_wizard_app.py`

- [ ] **Step 1: Write the failing tests**

```python
async def test_uninstall_apply_calls_remove_and_flips_applied() -> None:
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        removable=[(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        remove=captured.append,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("space")  # select rg
        await pilot.press("enter")
        assert app.screen.applied is True
        assert captured[0].paths == (Path("/opt/rg"),)
        assert captured[0].remove_ban is False


async def test_uninstall_empty_selection_refuses() -> None:
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        removable=[(_tool("rg"), [Path("/opt/rg")])], remove=captured.append
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("enter")  # nothing selected
        assert app.screen.applied is False
        assert captured == []  # closure never called
        assert "at least one" in app.screen.status_text


async def test_uninstall_apply_error_surfaces_and_does_not_crash() -> None:
    def boom(_decision: UninstallDecision) -> None:
        raise OSError("permission denied")

    inputs = _uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])], remove=boom)
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("space")
        await pilot.press("enter")
        assert app.screen.applied is False
        assert app.screen.error == "permission denied"
        assert "failed" in app.screen.status_text.lower()


async def test_uninstall_initial_view_opens_on_uninstall() -> None:
    app = _app(
        uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, UninstallScreen)


async def test_uninstall_empty_state_shows_nothing_line() -> None:
    app = _app(uninstall=_uninstall_inputs())  # no removable, no ban, no block
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("enter")  # no-op
        assert app.screen.applied is False
        assert "Nothing to uninstall" in app.screen.status_text
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py -k uninstall -v`
Expected: PASS (all uninstall tests green; behavior implemented in Task 4).

- [ ] **Step 3: Verify the abort contract still holds from the new view**

Add:

```python
async def test_ctrl_c_aborts_from_uninstall_view() -> None:
    app = _app(uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("ctrl+c")
    assert app.return_value is None
```

Run: `uv run pytest tests/test_wizard_app.py -k "ctrl_c_aborts_from_uninstall" -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_wizard_app.py
git commit -m "test: cover uninstall apply, refusal, error, initial-view, and abort"
```

---

## Task 7: Composition root — build inputs + open on view for `--uninstall`

**Files:**
- Modify: `setup.py` (coverage/pyright-excluded IO boundary — no unit tests; verified via `make validate` and the `--help`/non-interactive paths)

- [ ] **Step 1: Build `UninstallInputs` in `_build_app`**

In `setup.py`, import the new symbols:

```python
from installer.app import (
    ...,
    UninstallDecision,
    perform_uninstall,
    ...,
)
from installer.guards import guard_path_warning, guard_status
from installer.shellrc import has_managed_block
from installer.uninstall import removable_tools
from installer.wizard_app import UninstallInputs, UnifiedApp
```

Inside `_build_app`, after the existing `rc_paths = _rc_paths_for_mode(link_mode)` line, add:

```python
    removable = removable_tools(tools, _DEFAULT_BIN_DIR)
    ban_names = [name for name, active in status.items() if active]

    def _do_uninstall(decision: UninstallDecision) -> None:
        # Runs live inside the UninstallScreen. rc_paths is the standard set so the
        # ban aliases are cleaned wherever they were written, regardless of mode.
        perform_uninstall(
            decision,
            bin_dir=_DEFAULT_BIN_DIR,
            myshellrc_path=_MYSHELLRC,
            rc_paths=_RC_PATHS,
        )

    uninstall_inputs = UninstallInputs(
        removable=removable,
        ban_names=ban_names,
        has_path_block=has_managed_block(_MYSHELLRC),
        remove=_do_uninstall,
    )
```

Then pass `uninstall=uninstall_inputs` into the `UnifiedApp(...)` call.

- [ ] **Step 2: Add the interactive branch to `_run_uninstall`**

Replace the body of `_run_uninstall` so a TTY opens the app on the uninstall view, mirroring `_run_doctor`:

The current body is:

```python
def _run_uninstall(console: Console, *, assume_yes: bool) -> int:
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    run_uninstall(
        load_tools(_REGISTRY),
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
        confirm=confirm,
    )
    return 0
```

Add only the interactive branch at the top (everything else unchanged):

```python
def _run_uninstall(console: Console, *, assume_yes: bool) -> int:
    if sys.stdin.isatty() and not assume_yes:
        _build_app(load_tools(_REGISTRY), detect(), initial_view="uninstall").run()
        return 0
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    run_uninstall(
        load_tools(_REGISTRY),
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
        confirm=confirm,
    )
    return 0
```

- [ ] **Step 3: Verify non-interactive behavior and validation**

Run:
```bash
uv run setup.py --uninstall --yes < /dev/null   # non-TTY path: console run_uninstall, app NOT launched
make validate
```
Expected: the `--yes` path prints the console uninstall flow (or the nothing-line) and does **not** launch the TUI; `make validate` is green (ruff, ruff format, pyright strict, bandit, vulture, shellcheck).

- [ ] **Step 4: Commit**

```bash
git add setup.py
git commit -m "feat: open the app on the uninstall view for interactive --uninstall"
```

---

## Task 8: End-to-end uninstall through the real core (sandboxed)

This is a **true E2E**: it builds real artifacts + a real ban + a real managed PATH block on disk under a sandbox HOME, drives the *actual* `UnifiedApp` keystroke-by-keystroke, lets it call the *real* `perform_uninstall` (not a fake), and asserts the real files are gone. It also saves an SVG screenshot of the applied state to `.e2e-artifacts/uninstall.svg` so the Task 9 verification subagent can confirm the UI rendered the guidance. The sandbox is `tmp_path`; the real `$HOME` is never referenced.

**Files:**
- Create: `tests/test_uninstall_e2e.py`
- Modify: `.gitignore`

- [ ] **Step 1: Ignore the artifacts directory**

Append to `.gitignore`:

```gitignore
# Agent-driven E2E screenshots (Phase 3 uninstall verification)
.e2e-artifacts/
```

- [ ] **Step 2: Write the E2E test**

Create `tests/test_uninstall_e2e.py`:

```python
"""End-to-end uninstall: drive the real UnifiedApp through the real removal
core against a sandboxed HOME, asserting real artifacts are deleted while the
real $HOME is never touched. Saves an SVG screenshot for agent inspection."""

from pathlib import Path

from installer.app import UninstallDecision, perform_uninstall
from installer.doctor import DoctorReport
from installer.guards import guard_status, install_shims, write_ban_aliases
from installer.model import Method, Tool
from installer.shellrc import has_managed_block, write_myshellrc
from installer.uninstall import removable_tools
from installer.wizard_app import UnifiedApp, UninstallInputs

_ARTIFACTS = Path(__file__).resolve().parent.parent / ".e2e-artifacts"


def _dl_tool() -> Tool:
    return Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(
            Method(
                kind="github_release",
                params={"repo": "a/fd", "asset": "x", "member": "fd"},
            ),
        ),
    )


def _build_real_app(home: Path) -> tuple[UnifiedApp, Path, Path, Path]:
    bin_dir = home / ".local" / "bin"
    opt = home / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("binary")
    (bin_dir / "fd").symlink_to(opt / "fd")
    myshellrc = home / ".myshellrc"
    install_shims(bin_dir)  # real ban shims
    write_ban_aliases(myshellrc)  # real alias block
    write_myshellrc([bin_dir], myshellrc)  # real managed PATH block

    removable = removable_tools([_dl_tool()], bin_dir)

    def _remove(decision: UninstallDecision) -> None:
        perform_uninstall(
            decision, bin_dir=bin_dir, myshellrc_path=myshellrc, rc_paths=[myshellrc]
        )

    inputs = UninstallInputs(
        removable=removable,
        ban_names=[name for name, active in guard_status(bin_dir).items() if active],
        has_path_block=has_managed_block(myshellrc),
        remove=_remove,
    )
    app = UnifiedApp(
        [_dl_tool()],
        {"fd": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status(bin_dir),
        guard_warning=None,
        fix_preview="",
        fix=lambda: None,
        uninstall=inputs,
        initial_view="uninstall",
    )
    return app, opt, bin_dir, myshellrc


async def test_uninstall_e2e_removes_everything_against_sandbox(tmp_path: Path) -> None:
    app, opt, bin_dir, myshellrc = _build_real_app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")  # select tools + ban + PATH wiring
        await pilot.press("enter")  # apply live through the real core
        assert app.screen.applied is True
        _ARTIFACTS.mkdir(exist_ok=True)
        (_ARTIFACTS / "uninstall.svg").write_text(pilot.app.export_screenshot())

    # Real artifacts removed:
    assert not opt.exists()
    assert not (bin_dir / "fd").exists()
    # Ban shims + managed PATH block + alias block all removed:
    assert all(active is False for active in guard_status(bin_dir).values())
    assert has_managed_block(myshellrc) is False
    assert "alias" not in myshellrc.read_text()
```

- [ ] **Step 3: Run the E2E test**

Run: `uv run pytest tests/test_uninstall_e2e.py -v`
Expected: PASS (1 passed); `.e2e-artifacts/uninstall.svg` is created.

- [ ] **Step 4: Sanity-check the screenshot artifact carries the guidance**

Run: `grep -o "Removed\|ban removed\|PATH wiring removed" .e2e-artifacts/uninstall.svg | sort -u`
Expected: all three strings appear (the applied state rendered them — Textual embeds row text in the SVG).

- [ ] **Step 5: Capture the UX journey screenshots**

Append to `tests/test_uninstall_e2e.py` (a capture-and-assert test: it both writes the frames the Task 10 evaluator reads and pins that each state renders its key text). `_dl_tool`, `_build_real_app`, `_ARTIFACTS`, and the imports are already defined above:

```python
_UX = _ARTIFACTS / "ux"


def _snapshot(app: UnifiedApp, name: str) -> None:
    _UX.mkdir(parents=True, exist_ok=True)
    (_UX / name).write_text(app.export_screenshot())


def _error_app(home: Path) -> UnifiedApp:
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "fd").write_text("x")

    def _boom(_decision: UninstallDecision) -> None:
        raise OSError("permission denied")

    inputs = UninstallInputs(
        removable=[(_dl_tool(), [bin_dir / "fd"])],
        ban_names=[],
        has_path_block=False,
        remove=_boom,
    )
    return UnifiedApp(
        [_dl_tool()],
        {"fd": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status={},
        guard_warning=None,
        fix_preview="",
        fix=lambda: None,
        uninstall=inputs,
        initial_view="uninstall",
    )


async def test_uninstall_ux_journey_captures_each_state(tmp_path: Path) -> None:
    app, _opt, _bin_dir, _myshellrc = _build_real_app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        _snapshot(app, "01-open.svg")  # first sight of the view
        await pilot.press("enter")  # nothing selected -> refusal, not a dead-end
        assert "at least one" in app.screen.status_text
        _snapshot(app, "02-empty-refusal.svg")
        await pilot.press("a")  # select tools + ban + PATH wiring
        _snapshot(app, "03-selected.svg")
        await pilot.press("enter")  # apply live
        assert app.screen.applied is True
        _snapshot(app, "04-applied.svg")

    err = _error_app(tmp_path / "home2")
    async with err.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")  # removal raises -> error must render, not crash
        assert err.screen.error is not None
        _snapshot(err, "05-error.svg")
```

- [ ] **Step 6: Run the E2E + journey tests**

Run: `uv run pytest tests/test_uninstall_e2e.py -v`
Expected: PASS (2 passed); `.e2e-artifacts/ux/01-open.svg` … `05-error.svg` plus `.e2e-artifacts/uninstall.svg` exist.

- [ ] **Step 7: Commit**

```bash
git add tests/test_uninstall_e2e.py .gitignore
git commit -m "test: end-to-end uninstall + UX journey screenshots, sandboxed"
```

---

## Task 9: Agent-driven E2E safety verification gate

A fresh **verification subagent** independently confirms the feature end-to-end and — critically — proves the real `$HOME` was never mutated (the PRD's hard safety rule). This is a review gate, not new code: dispatch the subagent, read its verdict, and only proceed if it returns PASS.

**Files:** none (verification only).

- [ ] **Step 1: Dispatch the verification subagent**

Dispatch a fresh `general-purpose` subagent (via the Agent tool) with exactly this prompt:

> You are verifying the Phase 3 uninstall view end-to-end. Work from the repo root `/Users/ramon/git/personal/tools-installer`. Do NOT modify any source or test files. Perform these steps and report a verdict:
>
> 1. **Capture real-home baseline.** Run: `shasum -a 256 ~/.zshrc ~/.bashrc ~/.myshellrc 2>/dev/null > /tmp/home-before.txt; cat /tmp/home-before.txt`. (Missing files simply won't appear — that's fine.)
> 2. **Run the E2E test.** Run: `uv run pytest tests/test_uninstall_e2e.py -v`. Confirm it passes.
> 3. **Inspect the rendered UI.** Run: `grep -o "Removed\|ban removed\|PATH wiring removed" .e2e-artifacts/uninstall.svg | sort -u`. Confirm all three guidance strings are present — this proves the applied state actually rendered, not just a state flag.
> 4. **Run the full suite + gate.** Run: `make validate && make test`. Confirm green and that coverage on `installer/` is 100%.
> 5. **Prove real-home safety.** Run: `shasum -a 256 ~/.zshrc ~/.bashrc ~/.myshellrc 2>/dev/null > /tmp/home-after.txt; diff /tmp/home-before.txt /tmp/home-after.txt && echo IDENTICAL`. Confirm `IDENTICAL` (no real rc file changed during any test run).
>
> Return a verdict block: `VERDICT: PASS` or `VERDICT: FAIL`, followed by the exact command output for any step that did not meet its expectation. If FAIL, name the failing step and the discrepancy.

- [ ] **Step 2: Act on the verdict**

If the subagent returns `VERDICT: FAIL`, stop and fix the root cause (re-run the relevant earlier task), then re-dispatch. Only proceed to Task 10 on `VERDICT: PASS`.

- [ ] **Step 3: Record the verification**

No commit (verification produces no tracked files). Note in the eventual PR/branch summary that the agent-driven E2E gate passed, including the real-home `IDENTICAL` check.

---

## Task 10: Agent-driven UX evaluation (end-user critique)

A fresh **`ui-ux-designer` subagent role-plays the end user** and judges the uninstall experience from the journey screenshots Task 8 captured — not "do the files get deleted" (Task 9 covers that) but "is this flow understandable, trustworthy, and free of dead-ends for a real person." This is a quality gate: high-severity UX findings are fixed before the feature is considered done.

**Files:** none directly (findings may loop back to Tasks 4/6 for screen/wording changes).

- [ ] **Step 1: Dispatch the UX-evaluator subagent**

Dispatch a subagent with `subagent_type: "agent-ui-ux-designer:ui-ux-designer"` and this prompt:

> You are evaluating the UX of a new terminal (Textual TUI) "Uninstall" view as if you were the end user — both a first-time user removing a tool and a returning user cleaning up. Work from repo root `/Users/ramon/git/personal/tools-installer`.
>
> The journey screenshots are SVG files in `.e2e-artifacts/ux/` (Textual embeds all visible text and colors as `<text>`/`fill` attributes, so read them with the Read tool or `cat`; if you want a rendered raster, try `uv run python -c "import cairosvg, sys; cairosvg.svg2png(url=sys.argv[1], write_to=sys.argv[2])" <in.svg> <out.png>` and Read the PNG — skip if cairosvg is absent). The frames, in order:
> - `01-open.svg` — the view as first seen (tool rows, plus a pip/npm-ban row and a PATH-wiring row).
> - `02-empty-refusal.svg` — the user pressed "remove" with nothing selected.
> - `03-selected.svg` — everything toggled on.
> - `04-applied.svg` — after applying the removal.
> - `05-error.svg` — a removal that failed (e.g. permission denied).
>
> Walk the journey in order and narrate the end-user experience. Evaluate specifically against these product criteria (from the PRD):
> 1. **No dead-end flows** — every state is either an action with a preview/confirm or a guidance screen with a clear next step. Empty selection must be a clear no-op, never an unexplained exit.
> 2. **Trustworthy destruction** — before anything is deleted, can the user tell exactly what will be removed? Are the tool rows visually distinct from the ban / PATH-wiring rows (they are NOT packages)?
> 3. **Clear outcome + reload guidance** — does the applied state say what was removed AND that a shell reload is needed where relevant (open a new shell / `hash -r` for the ban; restart shell for PATH wiring)? Does it distinguish "done now" from "needs a new shell"?
> 4. **Discoverability** — from `01-open`, can a first-time user tell how to select, how to remove, and how to leave without removing?
> 5. **Failure clarity** — does `05-error` explain what failed and what to try, without a traceback?
>
> Return: a short end-user walkthrough, then a findings table with columns `Severity (CRITICAL/HIGH/MEDIUM/LOW) | Frame | Issue | Suggested fix`, then `VERDICT: SHIP` or `VERDICT: FIX-FIRST`. Cite the specific frame and on-screen wording for each finding. Be honest and opinionated; do not invent praise.

- [ ] **Step 2: Triage and fix high-severity findings**

For every CRITICAL or HIGH finding, fix the root cause — usually wording or layout in `UninstallScreen` (Task 4) or `_applied_summary` (Task 4), or the refusal/error text (Task 6). Re-run Task 8 to regenerate the screenshots (`uv run pytest tests/test_uninstall_e2e.py -v`), then re-dispatch the evaluator. Repeat until no CRITICAL/HIGH findings remain. MEDIUM/LOW findings are recorded for follow-up but do not block.

- [ ] **Step 3: Commit any UX fixes**

If Step 2 changed code, commit it (tests already cover the seams; update any assertion whose wording you changed):

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "fix: address end-user UX findings on the uninstall view"
```

If no code changed (VERDICT: SHIP on the first pass), record that the UX gate passed in the eventual PR/branch summary; no commit.

---

## Task 11: Full validation, docs, and roadmap status

**Files:**
- Modify: `README.md`, `memory/roadmap-status.md`

- [ ] **Step 1: Run the full gate on the committed tree**

Run: `make validate && make test`
Expected: all green; **100% coverage on `installer/`** (the new `has_managed_block`, `removable_tools`, `UninstallDecision`, `perform_uninstall`, and every `UninstallScreen` branch are covered by Tasks 1–6). If coverage flags an uncovered branch, add a focused test for it before proceeding — never lower the gate.

- [ ] **Step 2: Update the README**

In `README.md`, update the unified-UI / uninstall description to state that uninstall is now an in-app view (reachable via the palette, the `4` key, and interactive `--uninstall`) with toggles for tools, the pip/npm ban, and the managed PATH wiring, applied live with reload guidance. Keep the non-interactive `--uninstall --yes` contract description unchanged.

- [ ] **Step 3: Update the roadmap status memory**

In `memory/roadmap-status.md`, mark Phase 3 (Uninstall View) of the unified-UI redesign as done, noting Phase 4 (Policies tab) remains.

- [ ] **Step 4: Commit**

```bash
git add README.md memory/roadmap-status.md
git commit -m "docs: describe the in-app uninstall view (Phase 3)"
```

- [ ] **Step 5: Final verification**

Run: `make validate && make test`
Expected: green on the exact tree of the final commit. Phase 3 complete.

---

## Self-Review Notes

- **Spec coverage:** list = removable-artifact tools (Task 2); live-apply like FixScreen (Tasks 4/6); explicit ban + PATH toggles (Task 4 rows, Task 3 composer); preview-as-confirmation + empty refusal + error path + nothing-line (Task 6); `--uninstall` opens on view, non-interactive unchanged (Task 7); reload guidance wording (Task 4 `_applied_summary`); navigation parity + abort (Tasks 4/6); real-core E2E + journey capture (Task 8); agent-driven safety verification incl. real-home proof (Task 9); agent-driven end-user UX critique against the PRD UX criteria (Task 10); 100% coverage + validate + docs (Task 11). Phase 4 boundary respected — no ban *model* introduced; ban removal reuses `remove_shims`/`remove_ban_aliases`.
- **E2E vs unit:** Tasks 4–6 inject a fake `remove` closure to isolate the screen; Task 8 wires the *real* `perform_uninstall` against a sandbox HOME for a true round-trip (real shims/aliases/PATH block created, then removed). Task 9's subagent additionally hashes the real `~/.zshrc`/`~/.bashrc`/`~/.myshellrc` before and after the whole suite and asserts `IDENTICAL`, enforcing the PRD's "never mutate real home" rule.
- **Two distinct agent gates:** Task 9 is a *correctness/safety* PASS/FAIL gate (files removed, real home untouched). Task 10 is a *UX-quality* gate — a `ui-ux-designer` agent role-plays the end user over the journey screenshots and returns severity-ranked findings + SHIP/FIX-FIRST; CRITICAL/HIGH findings loop back to Task 4/6 before the feature is done. They answer different questions: "does it work safely?" vs "is it good to use?"
- **Type consistency:** `UninstallDecision(paths: tuple[Path, ...], remove_ban: bool, remove_path_block: bool)`, `perform_uninstall(decision, *, bin_dir, myshellrc_path, rc_paths)`, `removable_tools(...) -> list[tuple[Tool, list[Path]]]`, `has_managed_block(path) -> bool`, `UninstallInputs(removable, ban_names, has_path_block, remove)` are used identically across tasks and tests.
- **Adjust-on-contact:** Task 7's `_run_uninstall` rewrite must preserve the current call's exact `confirm`/path argument expressions; only the `isatty` branch is new. If the existing `_run_uninstall` already differs (e.g., a `_confirm` name), match what is there.
