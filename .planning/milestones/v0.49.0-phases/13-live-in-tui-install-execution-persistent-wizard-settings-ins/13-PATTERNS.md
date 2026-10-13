# Phase 13: Live in-TUI Install Execution & Persistent Wizard Settings - Pattern Map

**Mapped:** 2026-09-13
**Files analyzed:** 7 (new) + 3 (modified)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `installer/execute_screen.py` (new) | component (Textual `Screen`) | streaming + request-response | `installer/wizard_app.py::DoctorScreen` (lines 154-475) for the worker + `post_message` + `run_live` internals; `ConfirmUninstall`/`NavScreen`/`TimePickerScreen` for the base class | adapted — internals exact, base class deliberately different (see the note under "Pattern Assignments" below) |
| `installer/run.py::StreamingRunner` (new class, same file) | service (Runner implementation) | streaming | `installer/run.py::run_captured`/`run_output` (lines 42-97) | role-match (same `Runner` seam, new streaming behavior) |
| `installer/settings.py` (new) | model / persisted-state utility | CRUD (small JSON file) | `installer/version_cache.py` (full file, esp. lines 137-197) | exact (identical atomic-JSON envelope pattern) |
| `installer/wizard_app.py::UnifiedApp` handler for `CatalogScreen.Decided` (modified) | controller (message handler) | request-response | `installer/wizard_app.py` existing `on_globals_audited`/message handlers (lines ~476+) and `push_screen`/`pop_screen` at lines 810, 1620, 1627 | exact |
| `installer/catalog_tui.py::CatalogScreen.Decided` consumer wiring (modified, message shape unchanged) | controller | request-response | same file, `on_tool_browser_accepted` (lines 648-659) | exact (message already exists, only the receiver changes) |
| `tests/test_run.py` (extend) | test | unit | existing fakes in `tests/test_run.py` (check current fakes before adding) | role-match |
| `tests/test_settings.py` (new) | test | unit | `tests/test_version_cache.py` (full file, esp. lines 1-40) | exact |
| `tests/test_wizard_app.py` (extend) | test | integration (`Pilot`) | existing `_settle(app, pilot)` helper + DoctorScreen tests in same file | exact |
| `setup.py::main`/new interactive top-level function (modified) | config / composition-root wiring | request-response | `setup.py::_select_catalog`/`_build_app`/`main` (lines 596-786) | role-match — `setup.py` stays wiring-only per architecture rule 4 |

## Pattern Assignments

### `installer/execute_screen.py` (new screen, D-01/D-02/D-03)

**Analog:** `installer/wizard_app.py::DoctorScreen` (lines 154-475) for everything inside the
screen — the worker + `post_message` hand-off, the `run_live` apply, the redundantly-encoded status
rendering.

**One deliberate deviation from that analog, decided in plan 13-04 and recorded here so the two
artifacts agree:** `ExecuteScreen` subclasses `ModalScreen[None]` and defines `compose`, NOT
`AppScreen`/`compose_body`. `installer/ui_common.py::AppScreen.__init__` requires a `view` name
present in `VIEW_BY_NAME` (both `ModeBadge` and `WayfindingHeader` index it), so an `AppScreen`
subclass would force a seventh `installer/ui_common.py::VIEWS` row and hand the execution screen a
number key and a nav-palette entry — a destination the user could jump to mid-install, breaking the
`[catalog] / [catalog, <view>]` stack invariant `UnifiedApp._navigable` protects. `ModalScreen` is
this codebase's established shape for a pushed, non-navigable screen (`ConfirmUninstall`,
`NavScreen`, `TimePickerScreen`) and satisfies D-01's `push_screen`/`pop_screen` requirement.
Everywhere below that this section writes `compose_body`, read `compose`.

**Imports pattern** (mirror `wizard_app.py:15-52`):
```python
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Static

from installer.ui_common import run_live
```
(`ModalScreen` comes from `textual.screen`, not from `installer/ui_common.py` — only `AppScreen`
lives there, and per the deviation note above `ExecuteScreen` is not one.)

**Screen scaffold / push convention** (`installer/wizard_app.py:154-175`, `239-263`):
```python
class DoctorScreen(AppScreen):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "apply", "apply", show=True),
        ...
    ]

    def compose_body(self) -> ComposeResult:
        yield _BodyStatic(id="doctor-body")

    def on_mount(self) -> None:
        self._refresh_guidance()
        self._refresh_body()
        self._start_globals_audit()

    def enter_view(self) -> None:
        """Re-derive anything this view must not read from a stale snapshot."""
        self._refresh_guidance()
        if self.is_mounted:
            self._refresh_body()
            self._start_globals_audit()
```
`ExecuteScreen` follows this shape with the base-class substitution noted above — its `compose` (the `ModalScreen` equivalent of `compose_body`) renders the dependency notice + pre-flight audit text IMMEDIATELY (D-05.1 — no blocking modal before visible start), and `on_mount` does no subprocess work itself (the confirm keypress starts the worker, per D-01's "visible, non-modal confirm"). There is no `enter_view`: that hook belongs to `AppScreen`'s navigation lifecycle, and a pushed modal is entered exactly once.

**Worker + `post_message` hand-off pattern** (`installer/wizard_app.py:434-443`, verbatim):
```python
# Distinct groups: `exclusive` cancels within a group, so leaving both
# workers in the default one would let a reinstall cancel an in-flight
# audit and vice versa.
@work(thread=True, exclusive=True, group="globals-reinstall")
def _reinstall_globals_worker(self, packages: tuple[str, ...]) -> None:
    """Run the reinstall off the event loop, then hand the outcome back to it.

    A synchronous subprocess here would freeze every frame for the length of
    a `pnpm add -g`. Widgets may only be touched from the app's own thread,
    hence a posted message rather than a direct refresh.
    """
    _, error = run_live(lambda: self._reinstall_globals(packages))
    self.post_message(GlobalsReinstalled(error))
```
The new install-execution worker copies this shape exactly: `@work(thread=True, exclusive=True, group="install-execute")`, its own dedicated `group=` (per RESEARCH.md's explicit call-out — no group-collision with `globals-reinstall`/`version-refresh`/`tool-update`/`globals-audit`), and a `Message` subclass per event (one for each streamed output line/batch — `InstallLogLine(tool_id, line)` — and one terminal `InstallRunFinished(summary, captured_text)`), matching `GlobalsReinstalled`/`GlobalsAudited`'s own `Message` shape (`installer/wizard_app.py:108-143`).

**Message class pattern** (`installer/wizard_app.py:108-127`, verbatim to mirror):
```python
class GlobalsReinstalled(Message):
    """The threaded pnpm-globals reinstall finished; `error` is None on success.

    post_message is Textual's thread-safe hand-off back to the event loop, so
    the worker never touches a widget from its own thread.
    """

    def __init__(self, error: str | None) -> None:
        self.error = error
        super().__init__()
```

**Push-screen convention** (verified call sites `installer/wizard_app.py:810`, `1627`):
```python
self.app.push_screen(TimePickerScreen(), self._time_picked(policy, policy.set_schedule))
...
await self.push_screen(entering)
```
D-01 requires `push_screen`/eventual `pop_screen` (`await self.pop_screen()` at `installer/wizard_app.py:1620`) rather than `self.exit(...)` for the interactive path — `UnifiedApp`'s new `on_catalog_screen_decided` handler pushes `ExecuteScreen` instead of calling `self.exit(message.result)`.

**Console-redirect pattern for reused pure-core functions** (`setup.py:473-486`, verbatim):
```python
def _apply_fix() -> None:
    # Runs live inside the DoctorScreen. A quiet console keeps configure_path's
    # own prints from corrupting the running TUI; the screen renders its own
    # result. Link mode is resolved before the app opens (never prompted while
    # the TUI is live).
    configure_path(
        tools,
        Console(file=io.StringIO()),
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=rc_paths,
        link_mode=link_mode,
    )
```
The worker's post-install step calls `configure_path` this exact way (`Console(file=io.StringIO())`), inside the SAME worker that just ran `run_installs` — never a second worker.

**Confirm-modal pattern (only if execute screen needs an explicit "Are you sure" for a NEW destructive action)** — `installer/wizard_app.py:1291-1324`, verbatim:
```python
class ConfirmUninstall(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "confirm", "remove", show=True, priority=True),
        Binding("y", "confirm", "remove", show=False),
        Binding("escape", "cancel", "cancel", show=True),
        Binding("n", "cancel", "cancel", show=False),
    ]

    def __init__(self, summary: str) -> None:
        super().__init__()
        self.summary = summary  # public test seam

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
```
Mirror this shape for the checksum-mismatch modal (D-05's Pattern 3 in RESEARCH.md), and ensure any dismiss/cancel path renders an explicit status line (D-05.3 — never a silent no-op), matching `StatusLine.set(...)` usage already established in `installer/ui_common.py:61-78`.

---

### `installer/run.py::StreamingRunner` (new)

**Analog:** existing `Runner` implementations in the SAME file (`installer/run.py:42-97`, verbatim above in Imports section — `run_command`, `run_captured`, `run_output`), plus the `MethodAwareRunner` protocol it must implement:

**Protocol to implement** (`installer/run.py:15-21`, verbatim):
```python
@runtime_checkable
class MethodAwareRunner(Protocol):
    """Optional runner capability used to attribute method-ladder transitions."""

    def __call__(self, cmd: list[str]) -> None: ...

    def method_started(self, method: str) -> None: ...
```

**Error handling pattern to match** (`installer/run.py:42-49`, `90-97`):
```python
def run_command(cmd: list[str]) -> None:
    """Real Runner: run argv, raise CommandError on non-zero exit."""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise CommandError(cmd, exc.returncode) from exc
    except OSError as exc:
        raise CommandError(cmd, 127) from exc
```
`StreamingRunner.__call__` must raise the same `CommandError(cmd, returncode, detail=...)` shape on non-zero exit (so `run_live`'s existing `except (OSError, CommandError)` catch in `installer/ui_common.py:41-50` keeps working unmodified) but build it via `subprocess.Popen` reading `stdout` line-by-line (D-05.2: attribution is UNCONDITIONAL — `method_started(method)` implements the `MethodAwareRunner` protocol so `install_tool` (`installer/engine.py:124-127`) already calls it with no engine changes needed):
```python
# Source: installer/engine.py:124-127 (read this session, verbatim) —
# the zero-change integration point StreamingRunner.method_started plugs into
for method in methods:
    if isinstance(runner, MethodAwareRunner):
        runner.method_started(method.kind)
```
Per Pitfall 3 in RESEARCH.md: use `stdin=subprocess.DEVNULL`, `stderr=subprocess.STDOUT`, and read in the same thread that owns the `Popen` object (the worker thread), never hand `Popen` across threads.

---

### `installer/settings.py` (new — `link_mode` persistence)

**Analog:** `installer/version_cache.py` (full file; the load/save/default-path trio is the exact shape to mirror)

**Imports pattern** (`installer/version_cache.py:25-37`):
```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from installer.atomic import atomic_write_text
from installer.locations import ensure_dir
```

**Save pattern** (`installer/version_cache.py:154-176`, verbatim):
```python
def save_version_cache(
    path: Path,
    cache: Mapping[str, VersionCacheEntry],
    *,
    managers: Mapping[str, object] | None = None,
) -> None:
    """Write the versioned envelope. managers=None preserves the existing key."""
    managers_out = dict(managers) if managers is not None else _existing_managers(path)
    payload = {
        "version": 1,
        "tools": {
            tool_id: {
                "latest_version": entry.latest_version,
                "checked_at": entry.checked_at,
                "failed_at": entry.failed_at,
            }
            for tool_id, entry in cache.items()
        },
        "managers": managers_out,
    }
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")
```

**Load pattern (defensive-degrade)** (`installer/version_cache.py:137-151`, verbatim):
```python
def load_version_cache(path: Path) -> dict[str, VersionCacheEntry]:
    """Read the cache. Missing, unreadable, or malformed input yields {} / skips."""
    try:
        raw: object = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    ...
```

**Default path pattern** (`installer/version_cache.py:196-197`, verbatim):
```python
def default_cache_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "versions.json"
```
`installer/settings.py` mirrors this exactly: `{"version": 1, "link_mode": "centralized"}`, `default_settings_path() -> Path.home() / ".local" / "state" / "tools-installer" / "settings.json"`, `load_settings(path) -> Settings` degrading to a default `Settings()` on any `OSError`/`json.JSONDecodeError`/malformed content (V5 Input Validation from RESEARCH.md's Security Domain — a tampered `link_mode` string MUST be validated against the closed `{"centralized", "single", "split"}` literal set on load and fall back to the safe default before ever reaching `rc_paths_for_mode`/`ban_rc_paths`), `save_settings(path, settings)` via `ensure_dir` + `atomic_write_text`.

---

### `installer/wizard_app.py::UnifiedApp` — new `CatalogScreen.Decided` handler (modified)

**Analog:** existing message handlers in the same class, e.g. `on_globals_audited` pattern (generation-guarded dispatch) and the existing `push_screen`/`await self.pop_screen()` calls at `installer/wizard_app.py:810`, `1620`, `1627`.

**Core pattern to replace**: today `CatalogScreen.Decided` ultimately reaches `self.exit(message.result)` (per RESEARCH.md's architecture diagram). The interactive path changes this ONE call site to `self.push_screen(ExecuteScreen(...))`, leaving the headless path (`options.all`/`options.categories`) — which never touches `UnifiedApp`/`CatalogScreen` at all — untouched (Pitfall 2 in RESEARCH.md; recommended option (b): a NEW, parallel interactive top-level function that never calls `run_wizard`).

---

### `tests/test_settings.py` (new)

**Analog:** `tests/test_version_cache.py` (full file; excerpt lines 1-40 above)

**Core round-trip test pattern to mirror** (`tests/test_version_cache.py:25-39`, verbatim):
```python
def test_round_trip_through_the_versioned_envelope(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    entry = VersionCacheEntry(
        latest_version="v1.6.0",
        checked_at="2026-09-01T00:00:00+00:00",
        failed_at=None,
    )
    save_version_cache(path, {"codegraph": entry})
    raw = json.loads(path.read_text())
    assert raw["version"] == 1
    ...
    loaded = load_version_cache(path)
    assert loaded["codegraph"] == entry
```
`tests/test_settings.py` mirrors this: round-trip save/load, a malformed-`link_mode`-string-degrades-to-default case (closed literal set), and a missing-file-degrades-to-default case (both already precedented by `load_version_cache`'s `except (OSError, json.JSONDecodeError): return {}` branch).

---

### `tests/test_wizard_app.py` (extend, integration/`Pilot`)

**Analog:** existing `Pilot`-driven `DoctorScreen`/`ConfirmUninstall` tests already in this 3787-line file — reuse the file's own `_settle(app, pilot)` helper (grep the file at plan time for its exact signature and the nearest `push_screen`-driven test to copy structurally). D-01/D-02/D-05.3 all need `Pilot`-driven assertions (screen pushed not exited; screen stays visible after terminal message until a keypress; a cancelled modal shows an explicit status line).

---

### `tests/test_run.py` (extend, unit)

**Analog:** this file's own existing `Runner`-fake conventions — check the current fakes before adding a new one (RESEARCH.md's Wave-0 gap note: "matching this project's existing convention of injecting fakes rather than mocking `subprocess` directly").

---

### `setup.py` (modified — composition root wiring only)

**Analog:** `setup.py:596-786` (`_select_catalog`, `_resolve_link_mode`, `main`) — architecture rule 4 requires `setup.py` stay wiring-only; the new interactive top-level function (Pitfall 2's recommended option (b)) lives in `installer/app.py` or a new module, never as decision logic inside `setup.py` itself. `setup.py::main` only gains a new call-site wire-up, mirroring the existing `_select_catalog`/`_build_app` composition shape at lines 763-786.

## Shared Patterns

### Worker-thread + post_message (applies to `execute_screen.py`)
**Source:** `installer/wizard_app.py:434-443` (`_reinstall_globals_worker`), `installer/wizard_app.py:445-470` (`_audit_globals_worker`), `installer/catalog_tui.py:273-295` (`_refresh_versions_worker`)
**Apply to:** the new install-execution worker and the checksum-mismatch modal's blocking-thread interaction (Pattern 3 in RESEARCH.md — unverified combination, needs the 20-line spike RESEARCH.md's Pitfall 1 describes before committing the real plan to it).

### Live-apply / error surfacing
**Source:** `installer/ui_common.py:41-50` (`run_live`)
```python
def run_live(action: Callable[[], T]) -> tuple[T | None, str | None]:
    """Run a live core mutation from a screen: (result, None) on success,
    (None, message) on OSError or a failed command. The single apply workflow
    shared by the fix, uninstall, policies, and pnpm-globals screens..."""
    try:
        return action(), None
    except (OSError, CommandError) as exc:
        return None, str(exc)
```
**Apply to:** every worker-side call into a pure-core function from `execute_screen.py` — never a screen's own `try/except OSError` (architecture rule 3, "one apply workflow").

### Atomic JSON state persistence
**Source:** `installer/version_cache.py` (full file), `installer/atomic.py::atomic_write_text`
**Apply to:** `installer/settings.py`'s `link_mode` persistence — identical envelope shape (`{"version": 1, ...}`), same `ensure_dir` + `atomic_write_text` write path.

### Console-redirect for reused pure-core rendering functions
**Source:** `setup.py:473-486` (`_apply_fix`)
**Apply to:** `execute_screen.py`'s post-install `configure_path` call and the read-only doctor audit call — `Console(file=io.StringIO())`, never a bespoke print-interceptor.

### One view registry / one navigation path
**Source:** `installer/ui_common.py:81-179` (`View` dataclass, `VIEWS` tuple)
**Apply to:** ANY new Settings-adjustment UI this phase adds (Open Question #3) — if it becomes a new view, it is a one-row `VIEWS` addition, never a second navigation mechanism; if folded into `PoliciesScreen` instead, no `VIEWS` change is needed at all. This call must be made explicitly at plan time (CONTEXT.md flags this open).

## No Analog Found

None — every classified file has a strong (exact or role-match) analog in the existing codebase; this phase is explicitly framed in RESEARCH.md as "an IO-adapter problem," not new decision logic, so no file lacks a precedent to copy from.

## Metadata

**Analog search scope:** `installer/wizard_app.py`, `installer/catalog_tui.py`, `installer/ui_common.py`, `installer/run.py`, `installer/session.py`, `installer/engine.py`, `installer/app.py`, `installer/version_cache.py`, `installer/atomic.py`, `setup.py`, `tests/test_version_cache.py`, `tests/test_run.py`
**Files scanned:** 12 read in full or targeted section; no `.codegraph/` index present in this repo (confirmed absent), so Grep/Read were used directly per the fallback instruction.
**Pattern extraction date:** 2026-09-13
**Tracked-source gate:** all analog paths above are ordinary tracked files under `installer/`, `tests/`, and `setup.py` in this single-repo project (no submodules, no `.gsd/capabilities/` mirrors involved) — verified via direct `Read`/`Bash grep` against the working tree; no `git ls-files` gate issue applies here.
