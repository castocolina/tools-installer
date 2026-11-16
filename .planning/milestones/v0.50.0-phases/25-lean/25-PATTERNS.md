# Phase 25: Lean - Pattern Map

**Mapped:** 2026-11-15 (HEAD 86bb48d0)
**Files analyzed:** 9 new module groups + 2 deletion groups
**Analogs found:** 9 / 10 (no analog for the import-graph walker itself)
**Tracked-source gate:** every analog below was confirmed `git ls-files` tracked. No mirror paths.
Line numbers are from HEAD and are starting points; plans re-check them.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `installer/compose.py` | service/composition | request-response | `setup.py` `_build_app`/`_execute_inputs` (:743, :1062) + constants (:112-136) | exact (it is a move) |
| `tests/test_reachability.py` | test (guard) | transform (AST) | `tests/test_executors.py:165-173`, `tests/test_locations.py:468-495`, `tests/test_run.py:819-825` | role-match |
| `installer/doctor_screen.py` | component | event-driven | `installer/execute_screen.py` header + `installer/catalog_tui.py` | role-match |
| `installer/uninstall_screen.py` (+ `uninstall_review.py`) | component | event-driven | same | role-match |
| `installer/policies_screen.py`, `schedules_screen.py` | component | event-driven | same | role-match |
| `installer/modals.py` | component | event-driven | `ModalScreen` classes at `wizard_app.py:3202-3565` (verbatim move) | exact |
| `installer/mutation_lock.py` | utility | state | `wizard_app.py:3566-3676` (`MutationLock`) | exact (move) |
| `RunLog(RichLog)` + dropped label in `installer/execute_screen.py` | component | streaming | `_BodyStatic(Static)` `wizard_app.py:333-338`; `RichLog` at `execute_screen.py:431` | role-match |
| composition monkeypatch helper (tests) | test util | n/a | `tests/test_setup.py::_sandbox` (:566-591), `tests/conftest.py` autouse fixtures (:99-120) | exact |
| `host_setup` + sensitive-action deletion | deletion | n/a | 24.4 guards retirement commits | exact |

## Pattern Assignments

### `installer/compose.py` (composition, request-response)

**Analog:** `setup.py`. Constants block, `setup.py:112-136`, to move and define once:
```python
_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"   # NOTE: Path(__file__).parent must become parents[1]/.. in compose.py
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
_SHELLRC = Path.home() / ".shellrc"
_ZSHRC = zshrc_path(Path.home(), os.environ)
_RC_PATHS = [_ZSHRC, Path.home() / ".bashrc"]
_SHELL = os.environ.get("SHELL", "")
_WARN_CONSOLE = Console(stderr=True)
_DAEMON_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{daemon.LABEL}.plist"
_LINUX_DAEMON_UNIT_DIR = systemd_daemon.user_unit_dir(Path.home(), os.environ)
_ENVIRONMENT_D_DIR = env_redirect.environment_d_dir(Path.home(), os.environ)
```
Gotcha: `_REGISTRY` is `__file__`-relative; in `installer/compose.py` it must resolve to `Path(__file__).parent / "registry.toml"`. `_STYLE` (questionary) stays in `setup.py`. Import header of `setup.py` ends at :97 with `from installer.wizard_app import PolicyInputs, ScheduleInputs, UnifiedApp, UninstallInputs`; that line becomes imports from the split modules. Every home constant is import-time, so all tests patch the module that owns them (see `_sandbox` below), which is why constants must have exactly one home.

Questionary callbacks (`ask_confirm`, `_ask_mismatch`) enter compose only as injected parameters.

### `tests/test_reachability.py` (guard test, AST)

**Analog A, scan of all of `installer/` plus `setup.py`** (`tests/test_executors.py:165-173`):
```python
root = Path(__file__).resolve().parents[1]
offenders: list[str] = []
for path in [*sorted((root / "installer").rglob("*.py")), root / "setup.py"]:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        ...
            offenders.append(f"{path.relative_to(root)}:{node.lineno}")
assert offenders == []
```
**Analog B, locating `setup.py` entry (`main`, `__main__` block)** `tests/test_locations.py:468-495` and `tests/test_run.py:819-825`: `ast.parse(SETUP_PY.read_text())`, iterate `tree.body` for `ast.If` on `__name__`, `ast.walk` into `FunctionDef` bodies.
Needed on top (no analog): walk `ast.walk` (not `tree.body`) so function-level `Import`/`ImportFrom` count (`policy.py` lazy imports); resolve `from installer import x` to `installer/x.py`; follow string-keyed dispatch tables by reading dict-literal string keys. Probe table is `installer/install_ownership.py` (`"host-setup": _host_setup` at :378, goes away with D-10). Convention from `.claude/architecture.md:915-935`: an exemption list must be asserted live (matches a real hit), so a stale allowlist entry fails.

### Split screen modules (`doctor_screen.py`, `uninstall_screen.py`, `policies_screen.py`, `schedules_screen.py`, `modals.py`)

**Analog:** `installer/execute_screen.py:1-30, 66-71`: module docstring, `from __future__ import annotations`, stdlib, then third-party, then `installer.*` absolute imports, then:
```python
if TYPE_CHECKING:
    from installer.wizard_app import UnifiedApp
```
`installer/catalog_tui.py:45-46` does the same. Narrow `self.app` inside each screen class exactly as `DoctorScreen` does today (`wizard_app.py:358-363`):
```python
class DoctorScreen(AppScreen):
    if TYPE_CHECKING:
        @property
        def app(self) -> "UnifiedApp": ...
```
Rules: screens import `wizard_app` only under `TYPE_CHECKING` (no cycle); `from installer.ui_common import AppScreen, ...` is the base import. Shared inputs/messages go where two or more modules use them; `_BodyStatic` (`:333`) moves with `DoctorScreen` unless Policies/Uninstall also use it (grep first). Block ranges: Doctor :333-1031, uninstall :1032-2157 (`UninstallScreen` :1180, then `PoliciesScreen` :2158 per `grep ^class`; context says :2050, plans re-measure), Schedules :2669, modals :3202-3565, MutationLock :3605, UnifiedApp :3677. `modals.py` gets `ConfirmGuardFile`..`CursorModelScreen`; `from textual.screen import ModalScreen`. Update importers in the same commit: `setup.py:97`, `catalog_tui.py`, `execute_screen.py`, `terminal_shell.py`, `ui_common.py`, tests.

### `installer/mutation_lock.py`

Move `wizard_app.py:3566-3676` verbatim: `MUTATION_REFUSAL`, `SCHEDULED_RUN_REFUSAL`, `class MutationLock:` (plain base, `_mutation_holder`, `_run_lock: runlock.RunLock | None`, `_CROSS_PROCESS`). `UnifiedApp(MutationLock, App[...])` imports it back. Tests: `tests/test_mutation_runlock.py` changes only import path.

### `RunLog(RichLog)` and dropped label (`execute_screen.py`)

**Small-subclass analog** (`wizard_app.py:333-338`):
```python
class _BodyStatic(Static):
    """Static with a small public render seam for headless tests."""
    @property
    def renderable(self) -> Any:
        return self.render()
```
**Current construct to replace** (`execute_screen.py:431-436`):
```python
yield RichLog(id="execute-log", markup=False, highlight=False, auto_scroll=True)
yield Static(id="execute-silence")
```
Add `max_lines=5000`, the label `Static` immediately above it (hidden until first drop, CSS near `:385-398`, which already toggles `#execute-log` with `-running`/`-finished`). Writes to centralize: `self.query_one("#execute-log", RichLog)` at :869 and :938 plus the `log.write(...)` calls through ~:953 (grep `execute-log` and `log.write`). The counter lives in the subclass `write` override; text "1 earlier line dropped" / "N earlier lines dropped". `RichLog` is already imported (:30). Tests querying `#execute-log` as `RichLog` still pass (subclass).

### Composition monkeypatch helper (tests)

**Analog:** `tests/test_setup.py::_sandbox` (:566-591): `monkeypatch.setattr(setup, "_DEFAULT_BIN_DIR", ...)` for each home constant, `_LINUX_DAEMON_UNIT_DIR`, `load_tools`, `detect`, `setup.sys.stdin`, plus `monkeypatch.setattr("installer.settings.default_settings_path", ...)`. After the move, the setattr targets become `compose` (D-12: only module-object references and monkeypatch targets may change; keep every `assert` byte-identical). Put one shared helper in `tests/` next to `tests/sandbox.py` / `state_doubles.py` (non-`test_` helper modules), taking the module object, so tests do not repeat a 25-line block. Session-wide autouse patterns to mirror: `tests/conftest.py:99-120`.

## Deletion Patterns (precedents)

- **Retire a module with its tests and flags** — 24.4:
  - `8b727786 refactor(24.4-06): delete the retired guard module`: deletes `installer/guards.py` (655) and `tests/test_guards.py` (1085) in one commit, with small edits in `locations.py`/`settings.py`/`test_locations.py`, and compensating tests added to `tests/test_setup.py`.
  - `14bf6d86 feat(24.4-06): drop the --guard/--unguard flags and the make guard targets`: touches `setup.py`, `render.py`, `tests/test_cli.py`, `test_makefile.py`, `test_app.py` in one change.
  - `5635baab` / `f0d18d4c` (screen-level removal from Uninstall/Policies), then docs commits `4c7f6425`, `4d81f169` (architecture.md follow-up). Order: callers first, module and tests last, docs after.
- **Apply to D-10:** `installer/host_setup.py` and `tests/test_host_setup.py` are both tracked at HEAD. Delete them in one commit with their branches; swap sample-kind tests to a live kind without weakening assertions.
- **Apply to D-11:** same shape; update `.claude/architecture.md:779` in the same plan.
- 18's managed-download probe removal: no commit found by subject search (`git log --oneline | grep -i managed.download` returned nothing relevant); do not cite one. 24.4 is the precedent to use.

## Shared Patterns

- Absolute `installer.*` imports; `from __future__ import annotations` in screen modules; `TYPE_CHECKING` only for `wizard_app`.
- Moves keep names so tests change only import paths (`# pyright: ignore[reportPrivateUsage]` stays).
- Guard tests scan `[*sorted((root/"installer").rglob("*.py")), root/"setup.py"]` and assert `offenders == []`.
- Every intermediate commit keeps `tests/test_layout_80x20.py`, `tests/test_screen_family.py`, `tests/test_wizard_app.py` green.

## No Analog Found

| File | Reason |
|---|---|
| import-graph resolver in `tests/test_reachability.py` | No existing test builds a module graph; only per-node scans exist. Use RESEARCH.md. |

## Metadata

**Search scope:** `setup.py`, `installer/`, `tests/`, `.claude/architecture.md`, git log.
**Not verified:** exact post-move line counts; whether `_BodyStatic` has users outside Doctor.
