# Unified UI Phase 4 — Policies Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pip/npm ban a first-class, toggleable Policies tab inside the unified Textual app — backed by a generic `Policy` model — and retire the post-install "Enable the pip/npm ban?" prompt.

**Architecture:** A new pure `installer/policy.py` defines a generic `Policy` (id, label, description, snapshot `active`, `apply`/`remove` closures returning a per-layer `PolicyResult`) plus a `ban_policy(...)` factory composing the existing `installer/guards.py` shim/alias seams. A new `PoliciesScreen` in `installer/wizard_app.py` renders policies as live-toggle DataTable rows (mirroring `UninstallScreen`). `setup.py` (the coverage/pyright-excluded IO boundary) binds real paths, wires interactive `--guard`/`--unguard` to open the tab, and deletes the post-install prompt. Execution stays cheap, idempotent file IO applied live in-view (the same narrow un-parking Phases 2–3 used); the app's run value stays `list[str] | None`.

**Tech Stack:** Python 3.12, uv, Textual 8.2.7 (headless `app.run_test`), pytest + pytest-asyncio (asyncio_mode=auto), 100% coverage on `installer/`, pyright strict, ruff/bandit/vulture/shellcheck via `make validate`.

**Spec:** `docs/superpowers/specs/2026-06-15-unified-ui-phase4-design.md`

**Branch:** `feat/unified-ui-phase4` (already created; the design spec is committed there).

---

## Reference: existing seams this plan composes (read, do not modify)

`installer/guards.py` already provides everything the ban needs. Exact signatures:

```python
BANNED: dict[str, str]   # {"npm": "...", "pip": "...", "pip3": "..."}
def install_shims(shim_dir: Path) -> dict[str, str]   # {name: 'created'|'refreshed'|'skipped (real binary here)'}
def remove_shims(shim_dir: Path) -> dict[str, str]     # {name: 'removed'|'absent'}
def guard_status(shim_dir: Path) -> dict[str, bool]    # {name: our shim is installed}
def write_ban_aliases(rc_path: Path) -> None           # idempotent alias block
def remove_ban_aliases(rc_path: Path) -> None          # strip alias block (missing file/block = no-op)
def guard_path_warning(shim_dir: Path, path_value: str, which: Callable[[str], str | None]) -> str | None
```

These are pure (take a `shim_dir`/`rc_path`, no real-home assumption), so tests bind them to `tmp_path`.

---

## Task 1: Pure policy model — `installer/policy.py`

**Files:**
- Create: `installer/policy.py`
- Test: `tests/test_policy.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_policy.py`:

```python
from pathlib import Path

from installer.guards import guard_status, install_shims
from installer.policy import Policy, PolicyLayer, PolicyResult, ban_policy


def _ban(home: Path, *, apply_to: list[Path] | None = None, remove_from: list[Path] | None = None,
         path_value: str = "", which=lambda _name: None) -> Policy:
    shim_dir = home / ".local" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    rc = home / ".myshellrc"
    return ban_policy(
        shim_dir=shim_dir,
        apply_rc_paths=apply_to if apply_to is not None else [rc],
        remove_rc_paths=remove_from if remove_from is not None else [rc],
        path_value=path_value,
        which=which,
    )


def test_ban_policy_metadata(tmp_path: Path) -> None:
    policy = _ban(tmp_path)
    assert policy.id == "ban"
    assert policy.label == "pip/npm ban"
    assert "pip" in policy.description and "npm" in policy.description


def test_ban_policy_inactive_on_clean_dir(tmp_path: Path) -> None:
    assert _ban(tmp_path).active is False


def test_ban_policy_active_when_shims_present(tmp_path: Path) -> None:
    shim_dir = tmp_path / ".local" / "bin"
    shim_dir.mkdir(parents=True)
    install_shims(shim_dir)
    assert _ban(tmp_path).active is True


def test_apply_writes_both_layers_and_returns_result(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    result = _ban(tmp_path, apply_to=[rc]).apply()
    shim_dir = tmp_path / ".local" / "bin"
    # Both layers really happened on disk.
    assert all(active for active in guard_status(shim_dir).values())
    assert "alias" in rc.read_text()
    # Structured result: two named layers + a reload hint.
    names = [layer.name for layer in result.layers]
    assert names == ["Shims", "Aliases"]
    assert "3 active" in result.layers[0].detail
    assert str(rc) in result.layers[1].detail
    assert result.reload_hint is not None and "hash -r" in result.reload_hint


def test_apply_warns_when_shim_dir_absent_from_path(tmp_path: Path) -> None:
    result = _ban(tmp_path, path_value="/usr/bin").apply()
    assert result.warning is not None and "not on PATH" in result.warning


def test_apply_no_warning_when_shim_dir_on_path(tmp_path: Path) -> None:
    shim_dir = tmp_path / ".local" / "bin"
    result = _ban(tmp_path, path_value=str(shim_dir)).apply()
    assert result.warning is None


def test_apply_surfaces_skipped_real_binary(tmp_path: Path) -> None:
    shim_dir = tmp_path / ".local" / "bin"
    shim_dir.mkdir(parents=True)
    (shim_dir / "npm").write_text("#!/bin/sh\necho real\n")  # a real binary, not our shim
    result = _ban(tmp_path).apply()
    assert "skipped" in result.layers[0].detail


def test_remove_clears_both_layers(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = _ban(tmp_path, apply_to=[rc], remove_from=[rc])
    policy.apply()
    result = policy.remove()
    shim_dir = tmp_path / ".local" / "bin"
    assert all(active is False for active in guard_status(shim_dir).values())
    assert "alias" not in rc.read_text()
    assert [layer.name for layer in result.layers] == ["Shims", "Aliases"]
    assert "removed" in result.layers[0].detail
    assert result.warning is None


def test_remove_is_idempotent(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = _ban(tmp_path, remove_from=[rc])
    # Removing from a clean machine reports cleanly, never raises.
    result = policy.remove()
    assert isinstance(result, PolicyResult)
    assert result.reload_hint is not None


def test_policy_layer_is_frozen() -> None:
    layer = PolicyLayer(name="Shims", detail="x")
    try:
        layer.name = "y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("PolicyLayer must be frozen")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_policy.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.policy'`.

- [ ] **Step 3: Implement `installer/policy.py`**

```python
"""Generic environment-policy model, parallel to Tool.

A Policy bundles its identity (id/label/description), a snapshot of whether it is
currently active, and two idempotent closures — apply and remove — that each
return a structured per-layer PolicyResult. The pure layer owns the composition
of installer.guards; the IO boundary (setup.py) binds the real shim dir and rc
paths. The pip/npm ban is the first and only instance; future env tweaks slot in
with no screen changes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from installer.guards import (
    guard_path_warning,
    guard_status,
    install_shims,
    remove_ban_aliases,
    remove_shims,
    write_ban_aliases,
)

_RELOAD_HINT = "Open a new shell or run `hash -r` so cached command paths refresh."


@dataclass(frozen=True)
class PolicyLayer:
    """One independently-reported layer of a policy (e.g. shims vs aliases)."""

    name: str
    detail: str


@dataclass(frozen=True)
class PolicyResult:
    """The outcome of an apply/remove: per-layer details plus guidance."""

    layers: tuple[PolicyLayer, ...]
    reload_hint: str | None
    warning: str | None


@dataclass(frozen=True)
class Policy:
    """A toggleable environment policy with idempotent apply/remove closures."""

    id: str
    label: str
    description: str
    active: bool
    apply: Callable[[], PolicyResult]
    remove: Callable[[], PolicyResult]


def ban_policy(
    *,
    shim_dir: Path,
    apply_rc_paths: list[Path],
    remove_rc_paths: list[Path],
    path_value: str,
    which: Callable[[str], str | None],
) -> Policy:
    """The pip/npm ban as a Policy, composing installer.guards.

    apply writes shims into shim_dir and aliases into apply_rc_paths; remove
    clears shims and strips aliases from remove_rc_paths (the union of every
    location, so disabling leaves no stragglers regardless of link mode).
    """

    def _apply() -> PolicyResult:
        shim_results = install_shims(shim_dir)
        active = sum(1 for state in shim_results.values() if state in ("created", "refreshed"))
        skipped = sum(1 for state in shim_results.values() if state.startswith("skipped"))
        shim_detail = f"{active} active in {shim_dir}"
        if skipped:
            shim_detail += f" ({skipped} skipped — real binary present)"
        for rc_path in apply_rc_paths:
            write_ban_aliases(rc_path)
        alias_detail = "written to " + ", ".join(str(p) for p in apply_rc_paths)
        return PolicyResult(
            layers=(PolicyLayer("Shims", shim_detail), PolicyLayer("Aliases", alias_detail)),
            reload_hint=_RELOAD_HINT,
            warning=guard_path_warning(shim_dir, path_value, which),
        )

    def _remove() -> PolicyResult:
        shim_results = remove_shims(shim_dir)
        removed = sum(1 for state in shim_results.values() if state == "removed")
        shim_detail = f"{removed} removed from {shim_dir}"
        for rc_path in remove_rc_paths:
            remove_ban_aliases(rc_path)
        alias_detail = "cleared from " + ", ".join(str(p) for p in remove_rc_paths)
        return PolicyResult(
            layers=(PolicyLayer("Shims", shim_detail), PolicyLayer("Aliases", alias_detail)),
            reload_hint=_RELOAD_HINT,
            warning=None,
        )

    return Policy(
        id="ban",
        label="pip/npm ban",
        description="blocks bare pip/npm so installs go through uv/pnpm (shims + aliases)",
        active=any(guard_status(shim_dir).values()),
        apply=_apply,
        remove=_remove,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_policy.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Verify coverage and gates on the new module**

Run: `uv run pytest tests/test_policy.py --cov=installer.policy --cov-report=term-missing -q`
Expected: `installer/policy.py` 100% (no `Missing` lines).
Run: `uv run ruff check installer/policy.py tests/test_policy.py && uv run pyright installer/policy.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add installer/policy.py tests/test_policy.py
git commit -m "feat: generic Policy model with ban_policy factory

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `PoliciesScreen` + `PolicyInputs` in the unified app

**Files:**
- Modify: `installer/wizard_app.py` (add `PolicyInputs`, `PoliciesScreen`; thread `policies` through `UnifiedApp`; drop the policies placeholder)
- Modify: `tests/test_wizard_app.py` (extend `_app` helper; add screen + nav tests)
- Modify: `tests/test_catalog_tui.py:22`, `tests/test_uninstall_e2e.py:56`, `tests/test_uninstall_e2e.py:90` (every `UnifiedApp(...)` call site gains the required `policies=` kw-arg)

- [ ] **Step 1: Write the failing tests**

In `tests/test_wizard_app.py`, extend the imports and the `_app` helper, and add a policy-inputs helper + tests. First, update the import block (top of file) to add the new names:

```python
from installer.policy import Policy, PolicyLayer, PolicyResult, ban_policy
from installer.wizard_app import (
    VIEW_ORDER,
    DoctorScreen,
    FixScreen,
    NavScreen,
    PlaceholderScreen,
    PoliciesScreen,
    PolicyInputs,
    UnifiedApp,
    UninstallInputs,
    UninstallScreen,
)
```

Add a helper just after `_uninstall_inputs`:

```python
def _ok_result() -> PolicyResult:
    return PolicyResult(
        layers=(PolicyLayer("Shims", "3 active in /bin"), PolicyLayer("Aliases", "written to /rc")),
        reload_hint="Open a new shell or run `hash -r` so cached command paths refresh.",
        warning=None,
    )


def _fake_policy(
    *,
    active: bool = False,
    apply: Callable[[], PolicyResult] = _ok_result,
    remove: Callable[[], PolicyResult] = _ok_result,
) -> Policy:
    return Policy(
        id="ban",
        label="pip/npm ban",
        description="blocks bare pip/npm",
        active=active,
        apply=apply,
        remove=remove,
    )


def _policy_inputs(policies: list[Policy] | None = None) -> PolicyInputs:
    return PolicyInputs(policies=policies if policies is not None else [_fake_policy()])
```

Update the `_app` helper signature and body to take and pass `policies`:

```python
def _app(
    *,
    report: DoctorReport | None = None,
    guard_status: dict[str, bool] | None = None,
    guard_warning: str | None = None,
    fix_preview: str = "Will wire ~/.local/bin into ~/.zshrc",
    fix: Callable[[], None] = lambda: None,
    uninstall: UninstallInputs | None = None,
    policies: PolicyInputs | None = None,
    initial_view: str = "catalog",
) -> UnifiedApp:
    tools = [_tool("rg"), _tool("fd")]
    installed: Mapping[str, bool] = {"rg": True, "fd": False}
    return UnifiedApp(
        tools,
        installed,
        {"search": "find things"},
        report=report or DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status or {"pip": False, "npm": False},
        guard_warning=guard_warning,
        fix_preview=fix_preview,
        fix=fix,
        uninstall=uninstall or _uninstall_inputs(),
        policies=policies or _policy_inputs(),
        initial_view=initial_view,
    )
```

Add these tests at the end of the file:

```python
async def test_policies_view_is_reachable() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert app.current_view == "policies"
        assert isinstance(app.screen, PoliciesScreen)


async def test_policies_reachable_via_palette() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("down", "down", "down", "down", "enter")  # 5th item: policies
        assert app.current_view == "policies"
        assert isinstance(app.screen, PoliciesScreen)


async def test_policies_initial_view_opens_on_policies() -> None:
    app = _app(initial_view="policies")
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, PoliciesScreen)


async def test_policy_toggle_enables_inactive_policy() -> None:
    calls: list[str] = []
    policy = _fake_policy(active=False, apply=lambda: (calls.append("apply"), _ok_result())[1])
    app = _app(policies=_policy_inputs([policy]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == ["apply"]
        assert app.screen.active_state["ban"] is True
        assert "enabled" in app.screen.status_text
        assert "Shims:" in app.screen.status_text


async def test_policy_toggle_disables_active_policy() -> None:
    calls: list[str] = []
    policy = _fake_policy(active=True, remove=lambda: (calls.append("remove"), _ok_result())[1])
    app = _app(policies=_policy_inputs([policy]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == ["remove"]
        assert app.screen.active_state["ban"] is False
        assert "disabled" in app.screen.status_text


async def test_policy_toggle_error_surfaces_and_does_not_crash() -> None:
    def boom() -> PolicyResult:
        raise OSError("permission denied")

    app = _app(policies=_policy_inputs([_fake_policy(active=False, apply=boom)]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is False  # unchanged on failure
        assert app.screen.error == "permission denied"
        assert "failed" in app.screen.status_text.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_wizard_app.py -q`
Expected: FAIL — `ImportError: cannot import name 'PoliciesScreen'` (and `PolicyInputs`).

- [ ] **Step 3: Implement `PolicyInputs` and `PoliciesScreen` in `installer/wizard_app.py`**

Add `from installer.policy import Policy, PolicyResult` to the imports (after the `from installer.model import Tool` line).

Add `PolicyInputs` right after the `UninstallInputs` dataclass (around line 59):

```python
@dataclass(frozen=True)
class PolicyInputs:
    """The policies the PoliciesScreen renders, each carrying its own bound
    apply/remove closures. The composition root builds these from the pure core."""

    policies: list[Policy]
```

Add `PoliciesScreen` right after the `UninstallScreen` class (after line 338, before `NavScreen`):

```python
class PoliciesScreen(Screen[None]):
    """Toggle environment policies (the pip/npm ban) on/off, applied live.

    Unlike the catalog/uninstall views there is no select-then-apply step: each
    toggle is an immediate, idempotent mutation, so only `enter` is bound (not
    `space`, whose 'harmless select' meaning elsewhere would be a footgun here).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "toggle", "toggle policy", show=True, priority=True),
    ]
    DEFAULT_CSS = """
    PoliciesScreen #policies-status { height: auto; padding: 0 1; color: $warning; }
    PoliciesScreen DataTable { height: 1fr; }
    """

    def __init__(self, inputs: PolicyInputs) -> None:
        super().__init__()
        self._policies = inputs.policies
        self.active_state: dict[str, bool] = {policy.id: policy.active for policy in inputs.policies}
        self.status_text = ""
        self.error: str | None = None

    def compose(self) -> ComposeResult:
        yield DataTable()
        yield Static("", id="policies-status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable[Any])
        table.cursor_type = "row"
        table.add_column("State", key="state")
        table.add_column("Policy", key="policy")
        table.add_column("Effect", key="effect")
        for policy in self._policies:
            table.add_row(
                self._state_cell(self.active_state[policy.id]),
                Text(policy.label, style="bold yellow"),
                Text(f"shell config: {policy.description}", style="dim"),
                key=policy.id,
            )
        table.focus()

    def _state_cell(self, active: bool) -> Text:
        return Text("[on]" if active else "[off]", style="green" if active else "dim")

    def _highlighted_policy(self) -> Policy | None:
        table = self.query_one(DataTable[Any])
        if table.row_count == 0:
            return None
        cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        policy_id = cell_key.row_key.value
        return next((policy for policy in self._policies if policy.id == policy_id), None)

    def _set_status(self, text: str, *, style: str) -> None:
        self.status_text = text
        self.query_one("#policies-status", Static).update(Text(text, style=style))

    def action_toggle(self) -> None:
        policy = self._highlighted_policy()
        if policy is None:
            return
        active = self.active_state[policy.id]
        try:
            result = policy.remove() if active else policy.apply()
        except OSError as exc:
            self.error = str(exc)
            self._set_status(
                f"Policy change failed: {exc}. Check permissions, then press enter.",
                style="red",
            )
            return
        self.error = None
        new_active = not active
        self.active_state[policy.id] = new_active
        self.query_one(DataTable[Any]).update_cell(policy.id, "state", self._state_cell(new_active))
        verb = "enabled" if new_active else "disabled"
        self._set_status(self._summary(policy, verb, result), style="green")

    def _summary(self, policy: Policy, verb: str, result: PolicyResult) -> str:
        # One line per outcome: a single joined line overflows the terminal width
        # and truncates the reload guidance (the Phase 3 fix).
        parts = [f"{policy.label} {verb}."]
        parts.extend(f"{layer.name}: {layer.detail}" for layer in result.layers)
        if result.reload_hint:
            parts.append(result.reload_hint)
        if result.warning:
            parts.append(result.warning)
        return "\n".join(parts)
```

Now wire it into `UnifiedApp`. Add the `policies: PolicyInputs` parameter (keyword-only, required) to `UnifiedApp.__init__` — insert it right after the `uninstall: UninstallInputs,` line in the signature:

```python
        uninstall: UninstallInputs,
        policies: PolicyInputs,
        initial_view: str = "catalog",
```

Replace the placeholder entry in `self._views` (the `"policies": PlaceholderScreen(...)` line) with:

```python
            "policies": PoliciesScreen(policies),
```

Delete the now-unused `_PLACEHOLDER_TEXT` dict (lines 37-39) — `policies` was its only key, so it becomes dead (vulture will flag it). Also remove `_PLACEHOLDER_TEXT` from `PlaceholderScreen` usages if any remain. Note: `PlaceholderScreen` itself is still imported by tests and may still be referenced; keep the class but drop the dict. Verify with grep in Step 4.

- [ ] **Step 4: Update the other `UnifiedApp(...)` call sites**

Each construction site must pass the new required `policies=` kw-arg. Use an empty policy list where policies are irrelevant to the test.

In `tests/test_catalog_tui.py`, add to its imports and the `UnifiedApp(...)` at line 22:

```python
from installer.wizard_app import PolicyInputs  # add to existing wizard_app import
# ... inside the UnifiedApp(...) call, alongside uninstall=...:
        policies=PolicyInputs(policies=[]),
```

In `tests/test_uninstall_e2e.py`, add the import and pass an empty `PolicyInputs` at both call sites (lines 56 and 90):

```python
from installer.wizard_app import PolicyInputs  # add to existing wizard_app import line
# ... in both UnifiedApp(...) calls, alongside uninstall=...:
        policies=PolicyInputs(policies=[]),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_wizard_app.py tests/test_catalog_tui.py tests/test_uninstall_e2e.py -q`
Expected: PASS (all green, including the 7 new policy tests).

- [ ] **Step 6: Verify gates**

Run: `uv run ruff check installer/wizard_app.py tests/ && uv run pyright installer/wizard_app.py && uv run vulture installer/wizard_app.py`
Expected: clean (no dead `_PLACEHOLDER_TEXT`). If vulture flags `PlaceholderScreen` as unused, confirm it is still imported/used by tests — if genuinely unused, leave it (tests import it); vulture is configured to scan `installer/`, so an unused-but-imported class will not flag. If it does flag, that means tests stopped using it — in that case keep the dict removal but do NOT delete the class without checking grep.

- [ ] **Step 7: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py tests/test_catalog_tui.py tests/test_uninstall_e2e.py
git commit -m "feat: live-toggle Policies tab in the unified app

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `setup.py` wiring — build the ban policy, open the tab, drop the prompt

**Files:**
- Modify: `setup.py` (`_build_app`, `main`/`_run_guard`, remove post-install prompt + dead `_ask_optin`)

> `setup.py` is the coverage/pyright-excluded IO boundary — it has no unit tests. Verify via `make validate` (ruff/vulture see it) and a sandboxed manual smoke that never mutates the real home.

- [ ] **Step 1: Import the policy factory and inputs**

Add to the `from installer.wizard_app import (...)` block: `PolicyInputs`. Add a new import line: `from installer.policy import ban_policy`.

- [ ] **Step 2: Build the ban policy in `_build_app`**

In `_build_app` (after the `uninstall_inputs = UninstallInputs(...)` block, before `_apply_fix`), add:

```python
    policy_inputs = PolicyInputs(
        policies=[
            ban_policy(
                shim_dir=_DEFAULT_BIN_DIR,
                apply_rc_paths=_ban_rc_paths(link_mode),
                remove_rc_paths=_all_ban_rc_paths(),
                path_value=os.environ.get("PATH", ""),
                which=shutil.which,
            )
        ]
    )
```

Then pass it into the `UnifiedApp(...)` return — add `policies=policy_inputs,` right after the `uninstall=uninstall_inputs,` line.

- [ ] **Step 3: Open the tab from interactive `--guard` / `--unguard`**

Replace the `if options.guard:` and `if options.unguard:` branches in `main` (currently calling `_run_guard` directly) with an interactive-first branch that mirrors `_run_uninstall`. Replace lines `if options.guard: ... ` through the end of the `if options.unguard:` block with:

```python
    if options.guard or options.unguard:
        if sys.stdin.isatty() and not options.yes:
            _build_app(load_tools(_REGISTRY), detect(), initial_view="policies").run()
            return 0
        if options.guard:
            return _run_guard(
                console,
                remove=False,
                rc_paths=_ban_rc_paths(_resolve_link_mode(options.link_mode)),
                assume_yes=options.yes,
            )
        return _run_guard(
            console, remove=True, rc_paths=_all_ban_rc_paths(), assume_yes=options.yes
        )
```

- [ ] **Step 4: Remove the post-install ban prompt and the dead helper**

Delete the post-install prompt block in the install flow (the `if sys.stdin.isatty() and not options.yes and _ask_optin("Enable the pip/npm ban? ...")` block that calls `_run_guard`). The surrounding flow becomes:

```python
    _verify_and_clean(console, tools, platform, assume_yes=options.yes)
    if summary.failed or summary.mismatched:
        render_troubleshooting(console)
        return 1
    return 0
```

Then delete the now-unused `_ask_optin` helper function (it has no other caller; vulture will flag it otherwise).

- [ ] **Step 5: Verify gates on the boundary**

Run: `uv run ruff check setup.py && uv run vulture setup.py`
Expected: clean — no dead `_ask_optin`, no unused imports.

- [ ] **Step 6: Sandboxed smoke — interactive guard opens the tab (no real-home mutation)**

This proves the wiring without touching the real home. It pipes empty stdin (non-TTY) so it takes the console path against a throwaway HOME, then exits.

Run: `HOME="$(mktemp -d)" uv run setup.py --unguard --yes < /dev/null`
Expected: exits 0, prints nothing destructive (removal against an empty sandbox home is a clean no-op). It must NOT prompt and must NOT touch your real `~`.

- [ ] **Step 7: Commit**

```bash
git add setup.py
git commit -m "feat: wire Policies tab into setup.py; retire post-install ban prompt

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Agent-driven E2E — sandboxed toggle round-trip + UX journey screenshots

**Files:**
- Create: `tests/test_policies_e2e.py`

- [ ] **Step 1: Write the E2E test**

Create `tests/test_policies_e2e.py`. It drives the real `PoliciesScreen` through the real `ban_policy` closures against a sandboxed HOME, asserts shims/aliases appear then vanish, and saves journey screenshots for the UX agent.

```python
"""End-to-end policies toggle: drive the real PoliciesScreen through the real
ban_policy closures against a sandboxed HOME, asserting shims + aliases appear on
enable and vanish on disable while the real $HOME is never touched. Saves SVG
screenshots for agent inspection."""

from pathlib import Path

import pytest

from installer.doctor import DoctorReport
from installer.guards import guard_status
from installer.model import Method, Tool
from installer.policy import ban_policy
from installer.wizard_app import (
    PoliciesScreen,
    PolicyInputs,
    UnifiedApp,
    UninstallInputs,
)

_ARTIFACTS = Path(__file__).resolve().parent.parent / ".e2e-artifacts"
_UX = _ARTIFACTS / "policies"


def _tool() -> Tool:
    return Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(Method(kind="brew", params={"formula": "rg"}),),
    )


def _build_real_app(home: Path) -> tuple[UnifiedApp, Path, Path]:
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rc = home / ".myshellrc"
    policy = ban_policy(
        shim_dir=bin_dir,
        apply_rc_paths=[rc],
        remove_rc_paths=[rc],
        path_value=str(bin_dir),  # shim dir on PATH -> no spurious warning
        which=lambda _name: None,
    )
    app = UnifiedApp(
        [_tool()],
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status(bin_dir),
        guard_warning=None,
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(removable=[], ban_names=[], has_path_block=False, remove=lambda _d: None),
        policies=PolicyInputs(policies=[policy]),
        initial_view="policies",
    )
    return app, bin_dir, rc


def _snapshot(app: UnifiedApp, name: str) -> None:
    _UX.mkdir(parents=True, exist_ok=True)
    (_UX / name).write_text(app.export_screenshot())


async def test_policies_e2e_toggle_round_trip_against_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    app, bin_dir, rc = _build_real_app(Path.home())
    async with app.run_test(size=(100, 30)) as pilot:
        _snapshot(app, "01-open.svg")
        await pilot.press("enter")  # enable: writes shims + aliases live
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is True
        assert all(guard_status(bin_dir).values())
        assert "alias" in rc.read_text()
        _snapshot(app, "02-enabled.svg")
        await pilot.press("enter")  # disable: clears both layers
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is False
        _snapshot(app, "03-disabled.svg")

    assert all(active is False for active in guard_status(bin_dir).values())
    assert "alias" not in rc.read_text()


def test_real_home_rc_files_are_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Belt-and-suspenders: even constructing the sandbox app must never read or
    # write the real home. We assert the test's own HOME is the sandbox.
    monkeypatch.setenv("HOME", str(tmp_path))
    assert Path.home() == tmp_path
    _build_real_app(Path.home())
    assert not (Path("/") / "should-never-exist").exists()
```

- [ ] **Step 2: Run the E2E to verify it passes**

Run: `uv run pytest tests/test_policies_e2e.py -q`
Expected: PASS (2 passed). Confirms shims+aliases land then clear in the sandbox.

- [ ] **Step 3: Confirm screenshots were captured**

Run: `ls .e2e-artifacts/policies/`
Expected: `01-open.svg  02-enabled.svg  03-disabled.svg`.

NBSP note: Textual SVG encodes spaces as `&#160;`. To grep applied-state text, decode first:

Run: `uv run python -c "import re,html; t=re.sub(r'<[^>]+>','',html.unescape(open('.e2e-artifacts/policies/02-enabled.svg').read()).replace(chr(160),' ')); print('enabled' in t and 'Shims' in t)"`
Expected: `True`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_policies_e2e.py
git commit -m "test: agent-driven E2E for the Policies toggle against a sandbox HOME

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Agent-driven E2E safety verification (real home byte-identical)

**Files:** none (verification gate dispatched to a subagent)

- [ ] **Step 1: Capture pre-run hashes of the real home artifacts**

Dispatch a `general-purpose` subagent with these exact instructions (it must NOT mutate anything):

> Run, in order, and report the output verbatim. Do not modify any file.
> 1. `for f in ~/.zshrc ~/.bashrc ~/.myshellrc; do [ -f "$f" ] && shasum "$f" || echo "absent $f"; done`
> 2. `ls -la ~/.local/bin/npm ~/.local/bin/pip ~/.local/bin/pip3 2>&1 || true`
> 3. `uv run pytest -q` (the full suite — every UI/E2E test sandboxes HOME, so this must not touch the real home)
> 4. Repeat command 1 and command 2 exactly.
> Report: the full suite result line, and whether the command-1 and command-2 outputs are byte-identical between the before and after captures. State PASS only if (a) the suite is green and (b) both before/after captures match exactly.

- [ ] **Step 2: Evaluate the agent's verdict**

Expected: PASS — full suite green at 100% coverage, and the real `~/.zshrc`/`~/.bashrc`/`~/.myshellrc` + `~/.local/bin/{npm,pip,pip3}` are byte-identical before and after. If the agent reports any drift, STOP: a test is mutating the real home — find and fix the unsandboxed test before proceeding.

---

## Task 6: Agent-driven end-user UX evaluation of the Policies tab

**Files:** possible follow-up edits to `installer/wizard_app.py` (only if the UX agent finds blocking issues)

- [ ] **Step 1: Dispatch the `ui-ux-designer` agent**

Dispatch the `agent-ui-ux-designer:ui-ux-designer` agent with these instructions:

> You are evaluating a terminal UI as a real end user. The artifacts are SVG screenshots of a Textual "Policies" tab in a CLI installer at `.e2e-artifacts/policies/` (`01-open.svg`, `02-enabled.svg`, `03-disabled.svg`). The tab lists the "pip/npm ban" policy as an on/off row in a table; pressing `enter` on the highlighted row toggles it and renders a multi-line status summary (per-layer Shims/Aliases detail + a shell-reload hint). Evaluate as the final user would: Is the on/off state obvious at a glance? Are the available keys discoverable (is there a footer/hint)? After toggling, is it clear what changed and what the user must do next (shell reload)? Is the package-vs-policy distinction clear? Note any truncation/overflow at 100 columns. Return a verdict of SHIP or FIX-FIRST with a prioritized list (CRITICAL / HIGH / MINOR) and concrete, specific fixes.

- [ ] **Step 2: Act on the verdict (FIX-FIRST loop)**

If SHIP: proceed to Task 7. If FIX-FIRST: apply the CRITICAL and HIGH fixes to `PoliciesScreen` (e.g. footer/key hints, wording, multi-line summary already present), keeping every change covered by a test in `tests/test_wizard_app.py` (add/extend tests so coverage stays 100%). Re-run `uv run pytest tests/test_wizard_app.py tests/test_policies_e2e.py -q`, regenerate the screenshots, and re-dispatch the agent. Repeat until SHIP. Note MINOR items in the commit message but do not block on them.

- [ ] **Step 3: Commit any UX fixes**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "fix: Policies tab UX per end-user evaluation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(Skip this commit if the agent returned SHIP with no changes.)

---

## Task 7: Docs, full validation, and final review

**Files:**
- Modify: `README.md` (describe the Policies tab; note `make guard`/`make unguard` open it interactively)
- Modify: `installer/wizard_app.py:1-12` (module docstring — policies is no longer a placeholder)

- [ ] **Step 1: Update the `wizard_app.py` module docstring**

Change the docstring line that says "uninstall and policies remain placeholders until later phases" to reflect that catalog, doctor, fix, uninstall, and policies are all functional views now (only the live-apply exception note stays).

- [ ] **Step 2: Update `README.md`**

Find the section describing the in-app views (catalog/doctor/fix/uninstall) and add the Policies tab: a first-class on/off toggle for the pip/npm ban (shims + aliases), reachable via the palette, number key, or interactive `make guard`/`make unguard`; the post-install ban prompt is gone. Update the `make` target table if it describes `make guard`/`make unguard` as imperative-only (they now open the tab interactively; `--yes`/non-TTY stays imperative).

- [ ] **Step 3: Run the full gate on the exact tree**

Run: `make validate && make test`
Expected: all green — ruff, ruff format, pyright strict, bandit, vulture, shellcheck; full pytest with **100% coverage** on `installer/`.

- [ ] **Step 4: Commit docs**

```bash
git add README.md installer/wizard_app.py
git commit -m "docs: describe the Policies tab; mark policies view as shipped

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: Final whole-branch code review**

Dispatch a final code reviewer (per `superpowers:requesting-code-review`) over the full branch range (`main..feat/unified-ui-phase4`): verify the generic `Policy` model is clean, `run_guard`'s non-interactive contract is unchanged, the post-install prompt is gone with no dead code, the real home is never at risk, and the new tab follows the Phase 3 patterns. Address Critical/Important findings before finishing.

- [ ] **Step 6: Finish the branch**

Use `superpowers:finishing-a-development-branch` to present merge options. Update `memory/roadmap-status.md` with a Phase 4 DONE entry capturing the as-built model and any gotchas.

---

## Self-Review (plan vs. spec)

**Spec coverage:**
- Generic policy model (id/label/description/active/apply/remove + queryable status) → Task 1. ✓
- Ban seeded from `guards.py`, per-layer result, reload hint, PATH warning → Task 1. ✓
- Policies tab visually distinct, live toggle, per-layer status, error path, never empty → Task 2. ✓
- Reachable via palette + number key + `initial_view` → Task 2. ✓
- Interactive `--guard`/`--unguard` open the tab; non-TTY/`--yes` unchanged console path → Task 3. ✓
- Post-install prompt + dead `_ask_optin` removed → Task 3. ✓
- Headless tests for tab/toggle/per-layer/guidance/nav → Tasks 2, 4. ✓
- Agent-driven E2E (sandbox, real-home byte-identical) + agent UX eval → Tasks 4, 5, 6. ✓
- 100% coverage, English-only, coherent commits, `make validate && make test` → every task + Task 7. ✓

**Type consistency:** `Policy`, `PolicyLayer`, `PolicyResult`, `ban_policy`, `PolicyInputs`, `PoliciesScreen`, `active_state`, `status_text`, `error`, `action_toggle` are used identically across Tasks 1–7. `ban_policy` signature (`shim_dir`, `apply_rc_paths`, `remove_rc_paths`, `path_value`, `which`) matches between Task 1 (def), Task 3 (call), and Task 4 (call). `UnifiedApp` gains exactly one required kw-arg `policies: PolicyInputs`, updated at all five construction sites (setup.py + four test files).

**Placeholder scan:** No TBD/TODO; every code step has complete code; commands have expected output.
