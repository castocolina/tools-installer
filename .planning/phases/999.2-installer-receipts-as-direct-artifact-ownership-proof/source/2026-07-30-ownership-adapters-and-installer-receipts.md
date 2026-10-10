# Ownership Adapters and Installer Receipts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace guessed package ownership with structured, platform-filtered manager evidence and atomic installer receipts while keeping update execution fail closed.

**Architecture:** Plan 1 owns status scheduling and supplies one refresh-scoped context to `inspect_status`; this plan makes ownership adapters consume that context so expensive inventories run once per refresh. `Ownership` records the resolved PATH entry, canonical target, artifact owner, installation origin, update authorization, and structured probe outcome independently. Direct installers issue digest-bearing receipts only after successful artifact creation, and receipt evidence enters status inspection through the same ownership path as package-manager evidence.

**Tech Stack:** Python 3.11+, frozen dataclasses, JSON, SHA-256, bounded `subprocess`, pytest, Ruff, Pyright.

## Global Constraints

- Implement this plan only after the responsive status plan has landed. Consume its existing `initial_statuses`, `inspect_status`, and refresh-context API exactly as declared in **Plan 1 Contract** below, then evolve the probe result types atomically in Task 1.
- `initial_statuses` remains local and non-blocking: it resolves PATH entries and app bundles only. It must not run health, ownership, update, package-manager, or receipt-digest probes.
- `inspect_status` remains the only complete-status inspection entry point. Do not add another refresh coordinator, worker pool, generation counter, status map, or UI-thread handoff.
- Preserve both the PATH entry returned by `shutil.which` and its strict canonical target. Neither value alone proves ownership.
- Exclude a command whose PATH entry or canonical target is inside the installer's active virtual environment before any manager or receipt probe runs.
- Probe only methods applicable to `Platform.os`, `Platform.arch`, `Platform.immutable`, method `os`, and method `arch`.
- A verified artifact owner does not authorize an update. `UpdateAuthorization` must be present and must match a reviewed adapter before update discovery or execution can run.
- Return structured outcomes for manager unavailable, platform skipped, package mismatch, receipt absent, malformed output, timeout, artifact mismatch, command missing, virtual-environment exclusion, and no adapter.
- Prefer the strongest relevant failure when no adapter verifies ownership; never collapse all failures to `owner unknown`.
- Every probe subprocess uses a fixed argv list, `check=False`, `stdin=subprocess.DEVNULL`, `capture_output=True`, `text=True`, and `timeout=5`. Never use `shell=True`.
- Homebrew formula ownership uses `brew --prefix --installed <formula>` and canonical containment. Casks remain separate and are not verified by formula-prefix evidence.
- pnpm ownership uses global direct-dependency JSON plus the installed package's `package.json`; it must verify the declared package's exported command and canonical target without assuming a store layout.
- Volta ownership uses `volta which <cmd>` plus package inventory. Volta evidence never creates pnpm update authorization.
- RPM ownership comes from the RPM file database. On immutable Fedora, rpm-ostree deployment JSON distinguishes base-image and layered origins; neither receives a per-package update command in this plan.
- apt and pacman use exact canonical-path ownership and run only on Debian and Arch respectively. A separately declared `ownership_package` may prove ownership but does not authorize updating a different install package.
- Existing artifacts without a valid receipt remain unknown. Never synthesize historical receipts.
- Receipts are atomically replaced JSON documents containing tool ID, method kind, source, resolved version, asset, expected checksum, installed paths, and final SHA-256 digests.
- All filesystem tests use `tmp_path`. All subprocess behavior is injected or monkeypatched. Tests never inspect or mutate the real home directory or run live package-manager mutations.
- Do not redesign the UI coordinator, registry recommendation/scope/dependency semantics, JVM or SDKMAN installation, Install dispositions, or selection lifecycle.
- This plan does not produce `VerifyMethodOwnership`, an SDKMAN adapter, or SDKMAN candidate verification. The later registry/SDKMAN plan must own that method-specific seam and consume this plan's `Ownership` values without assigning SDKMAN work back to this plan. Reserve `"SDKMAN"` and `"sdkman"` in the closed owner and update literals so that later plan can extend behavior without reopening the value model.
- Do not add compatibility properties for the old `Ownership.manager`, `confidence`, `method_kind`, `package`, or `executable` fields. Update all internal consumers in the same coherent task.
- Do not add `# noqa`, `# type: ignore`, `# pyright: ignore`, `# nosec`, skipped tests, lowered coverage, or quality-tool configuration changes.
- Before every commit step, `make validate && make test` must pass on that task's complete tree.

---

## Plan 1 Contract

This plan consumes the reconciled shared-refresh contract already supplied by `docs/superpowers/plans/2026-07-30-responsive-status-and-install-progress.md`. Plan 1 creates one fresh `RefreshContext` per generation and currently caches probe stdout strings. Task 1 evolves that existing probe seam and cache to structured `CommandResult` values in the same coherent change as structured ownership.

```python
# installer/ownership.py, supplied by Plan 1
from collections.abc import Callable

ProbeRunner = Callable[[list[str]], str]


# installer/status.py, supplied by Plan 1
from collections.abc import Sequence
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from installer.health import HealthRunner
from installer.model import Tool
from installer.ownership import ExecutableResolver, ProbeRunner, resolve_executable
from installer.platform import Platform
from installer.updates import UpdateRunner

@dataclass
class RefreshContext:
    platform: Platform
    probe: ProbeRunner
    health_runner: HealthRunner
    update_runner: UpdateRunner
    executable_resolver: ExecutableResolver
    app_roots: tuple[Path, ...] | None = None
    cache: dict[tuple[str, ...], Future[str]] = field(default_factory=dict)
    cache_lock: Lock = field(default_factory=Lock)

    def probe_once(self, argv: tuple[str, ...]) -> str:
        with self.cache_lock:
            future = self.cache.get(argv)
            owner = future is None
            if future is None:
                future = Future()
                self.cache[argv] = future
        if owner:
            try:
                future.set_result(self.probe(list(argv)))
            except Exception as error:
                future.set_exception(error)
        return future.result()


def initial_statuses(
    tools: Sequence[Tool],
    *,
    app_roots: tuple[Path, ...] | None = None,
    executable_resolver: ExecutableResolver = resolve_executable,
) -> dict[str, ToolStatus]:
    """Build the local presence-only snapshot used before Textual mounts."""


def inspect_status(tool: Tool, include_updates: bool, context: RefreshContext) -> ToolStatus:
    """Inspect one tool while sharing one context across the refresh generation."""
```

The responsive coordinator's callable contracts are:

```python
# installer/status_coordinator.py, supplied by Plan 1
StatusInspector = Callable[[Tool, bool, RefreshContext], ToolStatus]
RefreshContextFactory = Callable[[], RefreshContext]


class StatusCoordinator:
    def __init__(
        self,
        tools: list[Tool],
        inspect_status: StatusInspector,
        refresh_context: RefreshContextFactory,
        *,
        max_workers: int = 4,
    ) -> None: ...
```

`StatusCoordinator.refresh` calls `context = self._refresh_context()` exactly once, before submitting tool futures, then submits `self._inspect_status(tool, request.include_updates, context)` for every tool. Generation, progress, stale-result, failure-preservation, and Textual-thread behavior stay as Plan 1 declares them.

Task 1 replaces `ProbeRunner`'s `str` result, `RefreshContext.probe`, `RefreshContext.cache`'s `Future[str]`, and `RefreshContext.probe_once`'s `str` return with `CommandResult` together; it also replaces Plan 1's executable resolution types with `ResolvedExecutable`, `ExecutableResolver`, and `resolve_executable` from `installer.ownership`. Do not split this migration across tasks or leave an adapter consuming structured results through a stdout-only annotation. Tasks 2-8 consume the evolved Task 1 contract, and `RefreshContext.probe_once` remains the sole cache used by Tasks 2-4; do not add module-global caches.

Task 7 adds an optional `receipt_store` field to this existing context because receipt lookup is refresh input, not coordinator state:

```python
receipt_store: ReceiptStore | None = None
```

The coordinator creates a fresh `RefreshContext` for every startup, explicit, or post-install refresh. Therefore cached Homebrew, pnpm, Volta, and rpm-ostree results cannot leak between refresh generations.

## File Map

- `installer/ownership.py`: structured ownership values, executable resolution, platform applicability, bounded probes, adapter orchestration, and manager parsers.
- `installer/status.py`: Plan 1's presence/inspection composition; Task 1 atomically migrates its probe cache to `CommandResult`, then passes one `RefreshContext` to ownership and updates without adding scheduling behavior.
- `installer/updates.py`: update discovery and execution argv gated by `UpdateAuthorization`, not artifact ownership alone.
- `installer/catalog_tui.py`: minimal field-name adaptation for owner/origin/outcome rendering; no layout, coordinator, or navigation changes.
- `installer/wizard_app.py`: minimal verified-update predicate adaptation; no coordinator or lifecycle changes.
- `installer/receipts.py`: receipt schema, strict JSON parsing, deterministic path digests, atomic issue, and verification.
- `installer/download.py`: returns exact download source/version/checksum/path evidence after successful placement.
- `installer/apps.py`: returns exact app bundle and optional CLI-link evidence after successful placement.
- `installer/engine.py`: issues receipts for successful direct installs and never for manager installs, failures, or manual host-setup handoffs.
- `setup.py`: wiring only; constructs `ReceiptStore`, places it in refresh contexts, and injects it into `install_tool`.
- `tests/test_ownership.py`: structured model, resolution, exclusion, platform filtering, cache behavior, and all manager fixtures.
- `tests/test_status.py`: exact Plan 1 integration and one-context-per-refresh behavior.
- `tests/test_updates.py`: authorization independence plus reviewed discovery and mutation argv.
- `tests/test_receipts.py`: schema, digest, malformed, missing, mismatch, and atomic replacement behavior.
- `tests/test_download.py`: download evidence returned to receipt issuance.
- `tests/test_apps.py`: app evidence returned to receipt issuance.
- `tests/test_engine.py`: receipt issuance boundaries.
- `tests/test_setup.py`: production receipt-store and refresh-context wiring.

### Task 1: Introduce Structured Ownership, Structured Probe Caching, and Safe Executable Resolution

**Files:**
- Modify: `installer/ownership.py:1-210`
- Modify: `installer/status.py` at `RefreshContext`, the `ResolvedExecutable` imports, and the `inspect_status` ownership call
- Modify: `tests/test_ownership.py:1-275`
- Modify: `tests/test_status.py:1-238`

**Interfaces:**
- Consumes: Plan 1 `RefreshContext.platform: Platform`, stdout `ProbeRunner = Callable[[list[str]], str]`, `RefreshContext.probe: ProbeRunner`, `cache: dict[tuple[str, ...], Future[str]]`, and `probe_once(argv: tuple[str, ...]) -> str`.
- Changes atomically: `ProbeRunner = Callable[[list[str]], CommandResult]`, `RefreshContext.probe: ProbeRunner`, `cache: dict[tuple[str, ...], Future[CommandResult]]`, and `probe_once(argv: tuple[str, ...]) -> CommandResult`.
- Produces: structural `OwnershipRefresh` with `platform: Platform` and `probe_once(argv: tuple[str, ...]) -> CommandResult`; every later task consumes this evolved contract.
- Produces: `ResolvedExecutable(path_entry: Path, canonical_target: Path)`.
- Produces: `ArtifactOwner(manager: Manager, package: str, method_kind: str)`.
- Produces: `Manager = Literal["Homebrew", "pnpm", "Volta", "rpm", "apt", "pacman", "receipt", "SDKMAN"]`; `SDKMAN` is reserved for Plan 3 and has no adapter in this plan.
- Produces: `InstallationOrigin = Literal["unknown", "user", "system-package", "base-image", "layered-package", "formula", "sdkman-candidate", "direct-installer", "other-reviewed"]`.
- Produces: `UpdateAuthorization(mechanism: UpdateMechanism, package: str, method_kind: str)`.
- Produces: `UpdateMechanism = Literal["brew", "pnpm", "dnf", "apt", "pacman", "sdkman"]`; `sdkman` is reserved for Plan 3 and is never emitted here.
- Produces: `Ownership(outcome, path, artifact_owner, origin, update_authorization, detail)` with no legacy fields.
- Produces: `resolve_executable(cmd: str) -> ResolvedExecutable | None`.
- Produces: `detect_owner(tool: Tool, executable: ResolvedExecutable | None, context: OwnershipRefresh, *, venv_root: Path | None = active_venv_root()) -> Ownership`.

- [ ] **Step 1: Write failing model, probe-cache, PATH-preservation, and virtual-environment tests**

```python
# tests/test_ownership.py
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from installer.health import CommandResult
from installer.model import Method, Tool
from installer.ownership import (
    ArtifactOwner,
    Ownership,
    ResolvedExecutable,
    UpdateAuthorization,
    detect_owner,
    resolve_executable,
    run_probe,
)
from installer.platform import Platform


@dataclass
class StubRefresh:
    platform: Platform
    responses: dict[tuple[str, ...], CommandResult] = field(default_factory=dict)
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def probe_once(self, argv: tuple[str, ...]) -> CommandResult:
        self.calls.append(argv)
        return self.responses.get(argv, CommandResult(127, "", "", "manager unavailable"))


def _platform(os_name: str = "fedora", *, immutable: bool = False, brew: bool = False) -> Platform:
    return Platform(os=os_name, arch="amd64", immutable=immutable, has_brew=brew)


def _tool(*methods: Method) -> Tool:
    return Tool("demo", "Demo", "dev", "demo", methods)


def _resolved_file(path: Path) -> ResolvedExecutable:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")
    return ResolvedExecutable(path.absolute(), path.resolve(strict=True))


def test_resolve_executable_preserves_path_entry_and_canonical_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "store" / "demo"
    target.parent.mkdir()
    target.write_bytes(b"demo")
    entry = tmp_path / "bin" / "demo"
    entry.parent.mkdir()
    entry.symlink_to(target)
    monkeypatch.setattr(ownership.shutil, "which", lambda _cmd: str(entry))

    assert resolve_executable("demo") == ResolvedExecutable(
        entry.absolute(), target.resolve(strict=True)
    )


def test_installer_venv_command_is_excluded_before_manager_probes(tmp_path: Path) -> None:
    target = tmp_path / ".venv" / "bin" / "demo"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"demo")
    resolved = ResolvedExecutable(target, target.resolve(strict=True))
    context = StubRefresh(_platform(brew=True))

    result = detect_owner(
        _tool(Method("brew", {"formula": "demo"})),
        resolved,
        context,
        venv_root=tmp_path / ".venv",
    )

    assert result == Ownership(
        outcome="venv-excluded",
        path=resolved,
        artifact_owner=None,
        origin="unknown",
        update_authorization=None,
        detail="command resolves inside the installer virtual environment",
    )
    assert context.calls == []


def test_ownership_values_keep_owner_origin_and_authorization_independent() -> None:
    path = ResolvedExecutable(Path("/usr/bin/demo"), Path("/usr/bin/demo"))
    value = Ownership(
        "verified",
        path,
        ArtifactOwner("rpm", "demo", "dnf"),
        "base-image",
        None,
        "RPM owns demo; rpm-ostree supplies it in the base image",
    )
    assert value.artifact_owner == ArtifactOwner("rpm", "demo", "dnf")
    assert value.origin == "base-image"
    assert value.update_authorization is None
    assert UpdateAuthorization("dnf", "demo", "dnf") != value.update_authorization


def test_run_probe_uses_bounded_noninteractive_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "demo\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert run_probe(["rpm", "-q", "demo"]) == CommandResult(0, "demo\n", "")
    assert calls == [
        (
            ["rpm", "-q", "demo"],
            {
                "check": False,
                "stdin": subprocess.DEVNULL,
                "capture_output": True,
                "text": True,
                "timeout": 5,
            },
        )
    ]
```

```python
# tests/test_status.py
from installer.health import CommandResult


def test_refresh_context_caches_complete_command_result() -> None:
    calls: list[list[str]] = []
    expected = CommandResult(9, "partial stdout", "manager stderr", "probe failed")
    context = _refresh_context(
        probe=lambda argv: calls.append(argv) or expected,
    )

    argv = ("manager", "inventory")
    assert context.probe_once(argv) is expected
    assert context.probe_once(argv) is expected
    assert calls == [["manager", "inventory"]]
```

- [ ] **Step 2: Run the focused tests and verify the red state**

Run: `uv run pytest tests/test_ownership.py tests/test_status.py -k 'preserves_path_entry or venv_command or keep_owner_origin or caches_complete_command_result' -v`

Expected: FAIL because `ResolvedExecutable`, `ArtifactOwner`, `UpdateAuthorization`, structured outcomes, venv exclusion, and the structured probe/cache contract do not exist together yet.

- [ ] **Step 3: Replace the ownership value model and executable resolver, and migrate the probe cache**

```python
# installer/ownership.py
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from installer.health import CommandResult
from installer.model import Method, Tool
from installer.platform import Platform

Manager = Literal["Homebrew", "pnpm", "Volta", "rpm", "apt", "pacman", "receipt", "SDKMAN"]
UpdateMechanism = Literal["brew", "pnpm", "dnf", "apt", "pacman", "sdkman"]
InstallationOrigin = Literal[
    "unknown",
    "user",
    "system-package",
    "base-image",
    "layered-package",
    "formula",
    "sdkman-candidate",
    "direct-installer",
    "other-reviewed",
]
OwnershipOutcome = Literal[
    "pending",
    "verified",
    "command-missing",
    "manager-unavailable",
    "platform-skipped",
    "package-mismatch",
    "receipt-absent",
    "malformed-output",
    "timeout",
    "artifact-mismatch",
    "venv-excluded",
    "no-adapter",
]

ProbeRunner = Callable[[list[str]], CommandResult]


@dataclass(frozen=True)
class ResolvedExecutable:
    path_entry: Path
    canonical_target: Path


@dataclass(frozen=True)
class ArtifactOwner:
    manager: Manager
    package: str
    method_kind: str


@dataclass(frozen=True)
class UpdateAuthorization:
    mechanism: UpdateMechanism
    package: str
    method_kind: str


@dataclass(frozen=True)
class Ownership:
    outcome: OwnershipOutcome
    path: ResolvedExecutable | None
    artifact_owner: ArtifactOwner | None
    origin: InstallationOrigin
    update_authorization: UpdateAuthorization | None
    detail: str


class OwnershipRefresh(Protocol):
    platform: Platform

    def probe_once(self, argv: tuple[str, ...]) -> CommandResult: ...


ExecutableResolution = ResolvedExecutable | None
ExecutableResolver = Callable[[str], ExecutableResolution]


def active_venv_root() -> Path | None:
    if sys.prefix == sys.base_prefix:
        return None
    try:
        return Path(sys.prefix).resolve(strict=True)
    except OSError:
        return None


def _under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def resolve_executable(cmd: str) -> ResolvedExecutable | None:
    found = shutil.which(cmd)
    if found is None:
        return None
    entry = Path(found).absolute()
    try:
        target = entry.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return ResolvedExecutable(entry, target)


def run_probe(argv: list[str]) -> CommandResult:
    try:
        completed = subprocess.run(
            argv,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", "", "ownership probe timed out after 5 seconds")
    except OSError as error:
        return CommandResult(127, "", "", f"manager unavailable: {error}")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _unknown(
    outcome: OwnershipOutcome,
    executable: ResolvedExecutable | None,
    detail: str,
) -> Ownership:
    return Ownership(outcome, executable, None, "unknown", None, detail)
```

Migrate the existing refresh context in this same step; do not retain a stdout compatibility path or a second cache:

```python
# installer/status.py
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from installer.health import CommandResult, HealthRunner
from installer.ownership import ExecutableResolver, ProbeRunner
from installer.platform import Platform
from installer.updates import UpdateRunner


@dataclass
class RefreshContext:
    platform: Platform
    probe: ProbeRunner
    health_runner: HealthRunner
    update_runner: UpdateRunner
    executable_resolver: ExecutableResolver
    app_roots: tuple[Path, ...] | None = None
    cache: dict[tuple[str, ...], Future[CommandResult]] = field(default_factory=dict)
    cache_lock: Lock = field(default_factory=Lock)

    def probe_once(self, argv: tuple[str, ...]) -> CommandResult:
        with self.cache_lock:
            future = self.cache.get(argv)
            owner = future is None
            if future is None:
                future = Future()
                self.cache[argv] = future
        if owner:
            try:
                future.set_result(self.probe(list(argv)))
            except Exception as error:
                future.set_exception(error)
        return future.result()
```

Keep `resolve_executable` responsible only for preserving resolution. In `detect_owner`, perform the explicit `venv_root` containment rejection shown by the test before adapter selection; this preserves the path in the structured diagnostic while ensuring no ownership probe runs. Change Plan 1's health call to pass `resolved.canonical_target` and its presence check to use `resolved is not None`. Change `is_installed` in `installer/status.py` to use the same `ResolvedExecutable | None` contract.

Replace Plan 1's pending value with the new constructor while retaining its presence-only semantics:

```python
# installer/status.py
PENDING_OWNERSHIP = Ownership(
    "pending", None, None, "unknown", None, "ownership pending"
)
```

- [ ] **Step 4: Add platform applicability and strongest-outcome selection**

```python
# installer/ownership.py
_NATIVE_OS = {"dnf": "fedora", "rpm_ostree": "fedora", "apt": "debian", "pacman": "arch"}
_OUTCOME_RANK: dict[OwnershipOutcome, int] = {
    "pending": -1,
    "verified": 100,
    "venv-excluded": 95,
    "artifact-mismatch": 90,
    "package-mismatch": 80,
    "malformed-output": 70,
    "timeout": 60,
    "receipt-absent": 50,
    "manager-unavailable": 40,
    "command-missing": 30,
    "platform-skipped": 10,
    "no-adapter": 0,
}


def _method_applies(method: Method, platform: Platform) -> bool:
    if method.os and platform.os not in method.os:
        return False
    if method.arch and platform.arch not in method.arch:
        return False
    native_os = _NATIVE_OS.get(method.kind)
    if native_os is not None:
        return platform.os == native_os
    if method.kind == "cask":
        return platform.os == "macos" and platform.has_brew
    return True


def _strongest(results: list[Ownership], executable: ResolvedExecutable) -> Ownership:
    if not results:
        return _unknown("no-adapter", executable, "no reviewed ownership adapter applies")
    return max(results, key=lambda result: _OUTCOME_RANK[result.outcome])


def _venv_exclusion(
    executable: ResolvedExecutable, venv_root: Path | None
) -> Ownership | None:
    if venv_root is None:
        return None
    if not (
        _under(executable.path_entry, venv_root)
        or _under(executable.canonical_target, venv_root)
    ):
        return None
    return Ownership(
        "venv-excluded",
        executable,
        None,
        "unknown",
        None,
        "command resolves inside the installer virtual environment",
    )
```

At the start of `detect_owner`, return `command-missing` when `executable is None`, then return `_venv_exclusion(executable, venv_root)` when non-`None`. Convert the existing brew/node/apt/dnf/pacman return constructors to the new field order without changing their evidence in this foundation task; Tasks 2-4 replace each parser and argv under focused red-green tests. For an inapplicable declared method, append `Ownership("platform-skipped", executable, None, "unknown", None, f"{method.kind} is not applicable on {context.platform.os}")`; do not invoke it. Finish with `_strongest(results, executable)`.

- [ ] **Step 5: Run ownership and status tests**

Run: `uv run pytest tests/test_ownership.py tests/test_status.py -v`

Expected: PASS. PATH entry and target survive resolution, venv commands trigger no probes, status uses the canonical target for health, and inapplicable methods return `platform-skipped`.

- [ ] **Step 6: Run all quality gates**

Run: `make validate && make test`

Expected: both commands exit 0; coverage remains at or above the configured floor.

- [ ] **Step 7: Commit the structured ownership foundation**

```bash
git add installer/ownership.py installer/status.py tests/test_ownership.py tests/test_status.py
git commit -m "refactor(status): separate ownership evidence and authorization" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 2: Add Cached Homebrew Formula Ownership

**Files:**
- Modify: `installer/ownership.py` Homebrew adapter and adapter registry
- Modify: `tests/test_ownership.py`

**Interfaces:**
- Consumes: Task 1's `OwnershipRefresh.probe_once(argv) -> CommandResult`; one context means one inventory query per refresh.
- Produces: `_brew_owner(method: Method, executable: ResolvedExecutable, context: OwnershipRefresh) -> Ownership`.
- Produces: `ArtifactOwner("Homebrew", formula, "brew")`, origin `formula`, and `UpdateAuthorization("brew", formula, "brew")` only after installed-inventory membership and canonical-prefix containment both pass.

- [ ] **Step 1: Write failing Homebrew argv, cache, mismatch, malformed, unavailable, and timeout tests**

```python
# tests/test_ownership.py
@pytest.mark.parametrize(
    ("result", "outcome"),
    [
        (CommandResult(127, "", "", "manager unavailable: brew"), "manager-unavailable"),
        (CommandResult(124, "", "", "ownership probe timed out after 5 seconds"), "timeout"),
        (CommandResult(0, "demo\nother extra\n", ""), "malformed-output"),
    ],
)
def test_brew_inventory_failures_are_structured(
    tmp_path: Path, result: CommandResult, outcome: str
) -> None:
    executable = _resolved_file(tmp_path / "Cellar" / "demo" / "1.0" / "bin" / "demo")
    context = StubRefresh(
        _platform("macos", brew=True),
        {("brew", "list", "--formula", "--full-name"): result},
    )
    owner = detect_owner(_tool(Method("brew", {"formula": "demo"})), executable, context)
    assert owner.outcome == outcome


def test_brew_inventory_is_cached_and_prefix_uses_reviewed_argv(tmp_path: Path) -> None:
    root = tmp_path / "Cellar" / "demo" / "1.0"
    first = _resolved_file(root / "bin" / "demo")
    second = _resolved_file(root / "libexec" / "demo-helper")
    responses = {
        ("brew", "list", "--formula", "--full-name"): CommandResult(0, "demo\n", ""),
        ("brew", "--prefix", "--installed", "demo"): CommandResult(0, f"{root}\n", ""),
    }
    context = StubRefresh(_platform("macos", brew=True), responses)
    tool = _tool(Method("brew", {"formula": "demo"}))

    assert detect_owner(tool, first, context).artifact_owner == ArtifactOwner(
        "Homebrew", "demo", "brew"
    )
    assert detect_owner(tool, second, context).update_authorization == UpdateAuthorization(
        "brew", "demo", "brew"
    )
    assert context.calls.count(("brew", "list", "--formula", "--full-name")) == 1
    assert len(context.responses) == 2


def test_brew_rejects_executable_outside_declared_formula_prefix(tmp_path: Path) -> None:
    formula_root = tmp_path / "Cellar" / "demo" / "1.0"
    formula_root.mkdir(parents=True)
    executable = _resolved_file(tmp_path / "foreign" / "demo")
    context = StubRefresh(
        _platform("macos", brew=True),
        {
            ("brew", "list", "--formula", "--full-name"): CommandResult(0, "demo\n", ""),
            ("brew", "--prefix", "--installed", "demo"): CommandResult(
                0, f"{formula_root}\n", ""
            ),
        },
    )
    assert detect_owner(
        _tool(Method("brew", {"formula": "demo"})), executable, context
    ).outcome == "package-mismatch"
```

`StubRefresh.calls` records every request, while its evolved Task 1 behavior must cache structured responses. Implement its method for this task as:

```python
def probe_once(self, argv: tuple[str, ...]) -> CommandResult:
    if argv not in self.calls:
        self.calls.append(argv)
    return self.responses.get(argv, CommandResult(127, "", "", "manager unavailable"))
```

- [ ] **Step 2: Run the focused tests and verify the red state**

Run: `uv run pytest tests/test_ownership.py -k brew -v`

Expected: FAIL because the current command is `brew --prefix --formula`, there is no refresh-scoped inventory, and errors collapse to unknown.

- [ ] **Step 3: Implement the strict cached formula adapter**

```python
# installer/ownership.py
def _failure(result: CommandResult) -> OwnershipOutcome | None:
    if result.failure is None:
        return None
    if "timed out" in result.failure:
        return "timeout"
    return "manager-unavailable"


def _single_path(result: CommandResult) -> Path | None:
    records = [line for line in result.stdout.splitlines() if line]
    if result.returncode != 0 or len(records) != 1:
        return None
    try:
        return Path(records[0]).resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def _brew_owner(
    method: Method, executable: ResolvedExecutable, context: OwnershipRefresh
) -> Ownership:
    formula = _package(method, "formula")
    if formula is None:
        return _unknown("malformed-output", executable, "brew method has no formula")
    inventory = context.probe_once(("brew", "list", "--formula", "--full-name"))
    if (outcome := _failure(inventory)) is not None:
        return _unknown(outcome, executable, inventory.failure or "Homebrew inventory failed")
    formulae = inventory.stdout.splitlines()
    if inventory.returncode != 0:
        return _unknown("manager-unavailable", executable, "Homebrew inventory failed")
    if any(not name or name != name.strip() or len(name.split()) != 1 for name in formulae):
        return _unknown("malformed-output", executable, "Homebrew returned malformed inventory")
    if formula not in formulae:
        return _unknown("package-mismatch", executable, f"Homebrew does not list {formula}")
    prefix_result = context.probe_once(("brew", "--prefix", "--installed", formula))
    if (outcome := _failure(prefix_result)) is not None:
        return _unknown(outcome, executable, prefix_result.failure or "Homebrew prefix failed")
    prefix = _single_path(prefix_result)
    if prefix is None:
        return _unknown("malformed-output", executable, "Homebrew returned no canonical prefix")
    if not _under(executable.canonical_target, prefix):
        return _unknown(
            "package-mismatch",
            executable,
            f"{executable.canonical_target} is outside Homebrew formula {formula}",
        )
    return Ownership(
        "verified",
        executable,
        ArtifactOwner("Homebrew", formula, "brew"),
        "formula",
        UpdateAuthorization("brew", formula, "brew"),
        f"Homebrew formula {formula} contains the canonical executable",
    )
```

Do not route `cask` methods to `_brew_owner`. A cask without a receipt remains a structured `receipt-absent` result in Task 7.

- [ ] **Step 4: Run tests and all quality gates**

Run: `uv run pytest tests/test_ownership.py -k brew -v && make validate && make test`

Expected: all commands exit 0. The inventory argv appears once in the underlying injected probe per refresh even when more than one tool uses Homebrew.

- [ ] **Step 5: Commit the Homebrew adapter**

```bash
git add installer/ownership.py tests/test_ownership.py
git commit -m "fix(status): verify Homebrew formula ownership" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 3: Add pnpm and Volta Ownership Without Layout Assumptions

**Files:**
- Modify: `installer/ownership.py` node adapters and adapter orchestration
- Modify: `tests/test_ownership.py`

**Interfaces:**
- Consumes: one cached `pnpm list --global --depth 0 --json` result per refresh.
- Produces: pnpm owner/origin/update authorization only when inventory package path, package metadata `bin`, command name, and canonical target all agree.
- Produces: Volta owner/origin with no update authorization only when `volta which` and exact package inventory agree.

- [ ] **Step 1: Write failing pnpm and Volta fixture tests**

```python
# tests/test_ownership.py
def test_pnpm_verifies_exported_command_at_inventory_reported_package_path(tmp_path: Path) -> None:
    package = tmp_path / "pnpm-store" / "opencode-ai@1.2.3"
    target = package / "dist" / "opencode"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"cli")
    (package / "package.json").write_text(
        json.dumps({"name": "opencode-ai", "bin": {"opencode": "dist/opencode"}})
    )
    entry = tmp_path / "bin" / "opencode"
    entry.parent.mkdir()
    entry.symlink_to(target)
    executable = ResolvedExecutable(entry, target.resolve(strict=True))
    inventory = json.dumps(
        [{"dependencies": {"opencode-ai": {"version": "1.2.3", "path": str(package)}}}]
    )
    context = StubRefresh(
        _platform(),
        {("pnpm", "list", "--global", "--depth", "0", "--json"): CommandResult(0, inventory, "")},
    )

    owner = detect_owner(
        _tool(Method("node", {"npm_pkg": "opencode-ai"})), executable, context
    )

    assert owner.artifact_owner == ArtifactOwner("pnpm", "opencode-ai", "node")
    assert owner.origin == "user"
    assert owner.update_authorization == UpdateAuthorization("pnpm", "opencode-ai", "node")


@pytest.mark.parametrize(
    "package_json",
    [
        {"name": "other", "bin": {"demo": "bin/demo"}},
        {"name": "demo", "bin": {"other": "bin/demo"}},
        {"name": "demo", "bin": "bin/demo"},
        {"name": "demo", "bin": {"demo": "../foreign"}},
    ],
)
def test_pnpm_rejects_foreign_or_malformed_package_metadata(
    tmp_path: Path, package_json: dict[str, object]
) -> None:
    owner = _pnpm_fixture_owner(tmp_path, package_json)
    assert owner.outcome in {"package-mismatch", "malformed-output"}
    assert owner.update_authorization is None


def test_volta_verifies_which_and_inventory_but_never_authorizes_pnpm(tmp_path: Path) -> None:
    executable = _resolved_file(tmp_path / ".volta" / "tools" / "image" / "packages" / "demo" / "bin" / "demo")
    context = StubRefresh(
        _platform(),
        {
            ("volta", "which", "demo"): CommandResult(
                0, f"{executable.canonical_target}\n", ""
            ),
            ("volta", "list", "--format", "plain", "demo-package"): CommandResult(
                0, "demo-package@2.0.0 (default)\n", ""
            ),
        },
    )

    owner = detect_owner(
        _tool(Method("node", {"npm_pkg": "demo-package"})), executable, context
    )

    assert owner.artifact_owner == ArtifactOwner("Volta", "demo-package", "node")
    assert owner.origin == "user"
    assert owner.update_authorization is None
```

- [ ] **Step 2: Run the focused tests and verify the red state**

Run: `uv run pytest tests/test_ownership.py -k 'pnpm or volta' -v`

Expected: FAIL because the current pnpm adapter assumes `pnpm root --global`, does not parse package exports, and has no Volta adapter.

- [ ] **Step 3: Implement strict pnpm parsing and canonical export checks**

```python
# installer/ownership.py
def _json_object(text: str) -> object | None:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _pnpm_owner(
    tool: Tool,
    method: Method,
    executable: ResolvedExecutable,
    context: OwnershipRefresh,
) -> Ownership:
    package_name = _package(method, "npm_pkg")
    if package_name is None:
        return _unknown("malformed-output", executable, "node method has no npm_pkg")
    argv = ("pnpm", "list", "--global", "--depth", "0", "--json")
    result = context.probe_once(argv)
    if (outcome := _failure(result)) is not None:
        return _unknown(outcome, executable, result.failure or "pnpm inventory failed")
    parsed = _json_object(result.stdout)
    if result.returncode != 0 or not isinstance(parsed, list) or len(parsed) != 1:
        return _unknown("malformed-output", executable, "pnpm returned malformed inventory")
    root = parsed[0]
    if not isinstance(root, dict) or not isinstance(root.get("dependencies"), dict):
        return _unknown("malformed-output", executable, "pnpm inventory has no dependencies")
    dependency = root["dependencies"].get(package_name)
    if not isinstance(dependency, dict):
        return _unknown("package-mismatch", executable, f"pnpm does not list {package_name}")
    package_path_value = dependency.get("path")
    if not isinstance(package_path_value, str) or not package_path_value:
        return _unknown("malformed-output", executable, "pnpm package has no installed path")
    try:
        package_path = Path(package_path_value).resolve(strict=True)
        metadata = json.loads((package_path / "package.json").read_text())
    except (OSError, RuntimeError, ValueError):
        return _unknown("malformed-output", executable, "pnpm package metadata is unreadable")
    if not isinstance(metadata, dict) or metadata.get("name") != package_name:
        return _unknown("package-mismatch", executable, "pnpm metadata names another package")
    exported = metadata.get("bin")
    if not isinstance(exported, dict):
        return _unknown("malformed-output", executable, "pnpm package bin metadata is not a map")
    tool_command = tool.cmd
    relative = exported.get(tool_command)
    if not isinstance(relative, str) or not relative:
        return _unknown("package-mismatch", executable, f"pnpm package does not export {tool_command}")
    try:
        expected = (package_path / relative).resolve(strict=True)
    except (OSError, RuntimeError):
        return _unknown("artifact-mismatch", executable, "pnpm exported command is missing")
    if not _under(expected, package_path) or expected != executable.canonical_target:
        return _unknown("artifact-mismatch", executable, "pnpm shim targets another artifact")
    return Ownership(
        "verified",
        executable,
        ArtifactOwner("pnpm", package_name, "node"),
        "user",
        UpdateAuthorization("pnpm", package_name, "node"),
        f"pnpm package {package_name} exports {tool_command}",
    )
```

Reject an absolute `bin` value or a resolved path outside `package_path` before comparing targets.

- [ ] **Step 4: Implement Volta as a separate node evidence path**

```python
# installer/ownership.py
_VOLTA_RECORD = re.compile(r"^(?P<package>[^@\s]+)@(?P<version>\S+) \(default\)$")


def _volta_owner(
    tool: Tool, method: Method, executable: ResolvedExecutable, context: OwnershipRefresh
) -> Ownership:
    package_name = _package(method, "npm_pkg")
    if package_name is None:
        return _unknown("malformed-output", executable, "node method has no npm_pkg")
    which = context.probe_once(("volta", "which", tool.cmd))
    if (outcome := _failure(which)) is not None:
        return _unknown(outcome, executable, which.failure or "Volta is unavailable")
    target = _single_path(which)
    if target is None:
        return _unknown("malformed-output", executable, "Volta returned no canonical command")
    if target != executable.canonical_target:
        return _unknown("artifact-mismatch", executable, "Volta resolves another executable")
    inventory = context.probe_once(("volta", "list", "--format", "plain", package_name))
    if (outcome := _failure(inventory)) is not None:
        return _unknown(outcome, executable, inventory.failure or "Volta inventory failed")
    lines = inventory.stdout.splitlines()
    record = _VOLTA_RECORD.fullmatch(lines[0]) if len(lines) == 1 else None
    if inventory.returncode != 0 or record is None:
        return _unknown("malformed-output", executable, "Volta returned malformed inventory")
    if record["package"] != package_name:
        return _unknown("package-mismatch", executable, "Volta inventory names another package")
    return Ownership(
        "verified",
        executable,
        ArtifactOwner("Volta", package_name, "node"),
        "user",
        None,
        f"Volta package {package_name} supplies {tool.cmd}",
    )
```

For a `node` method, evaluate pnpm and Volta independently and return a verified result first; otherwise feed both results to `_strongest`. Do not infer Volta from a `.volta` path without both commands succeeding.

- [ ] **Step 5: Run tests and all quality gates**

Run: `uv run pytest tests/test_ownership.py -k 'pnpm or volta' -v && make validate && make test`

Expected: all commands exit 0; pnpm inventory is cached within a refresh, no filesystem layout is constructed, and Volta has no update authorization.

- [ ] **Step 6: Commit node-manager ownership**

```bash
git add installer/ownership.py tests/test_ownership.py
git commit -m "feat(status): verify pnpm and Volta ownership" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 4: Add Native Package and rpm-ostree Origin Adapters

**Files:**
- Modify: `installer/ownership.py` apt, RPM/rpm-ostree, and pacman adapters
- Modify: `tests/test_ownership.py`

**Interfaces:**
- Produces: exact ownership-package evidence using optional method param `ownership_package`, falling back to the install package only when the values are identical.
- Produces: apt and pacman `system-package` origins and authorization only when ownership package equals install package.
- Produces: RPM `system-package`, `base-image`, or `layered-package` origin; immutable origins have no per-package update authorization.
- Consumes: one cached `rpm-ostree status --json` result per refresh.

- [ ] **Step 1: Write failing platform, ownership-package, and deployment fixture tests**

```python
# tests/test_ownership.py
@pytest.mark.parametrize(
    ("os_name", "method", "expected_argv", "stdout", "manager"),
    [
        (
            "debian",
            Method("apt", {"package": "demo"}),
            ("dpkg-query", "-S", "/usr/bin/demo"),
            "demo: /usr/bin/demo\n",
            "apt",
        ),
        (
            "arch",
            Method("pacman", {"package": "demo"}),
            ("pacman", "-Qqo", "/usr/bin/demo"),
            "demo\n",
            "pacman",
        ),
        (
            "fedora",
            Method("dnf", {"package": "demo"}),
            ("rpm", "-q", "--qf", "%{NAME}\\n", "-f", "/usr/bin/demo"),
            "demo\n",
            "rpm",
        ),
    ],
)
def test_native_adapters_use_exact_path_queries(
    os_name: str,
    method: Method,
    expected_argv: tuple[str, ...],
    stdout: str,
    manager: str,
) -> None:
    executable = ResolvedExecutable(Path("/usr/bin/demo"), Path("/usr/bin/demo"))
    context = StubRefresh(_platform(os_name), {expected_argv: CommandResult(0, stdout, "")})
    owner = detect_owner(_tool(method), executable, context)
    assert owner.artifact_owner is not None
    assert owner.artifact_owner.manager == manager
    assert expected_argv in context.calls


def test_native_adapter_is_platform_skipped_without_running_foreign_manager() -> None:
    executable = ResolvedExecutable(Path("/usr/bin/demo"), Path("/usr/bin/demo"))
    context = StubRefresh(_platform("arch"))
    owner = detect_owner(_tool(Method("apt", {"package": "demo"})), executable, context)
    assert owner.outcome == "platform-skipped"
    assert context.calls == []


def test_distinct_apt_ownership_package_proves_owner_but_not_update_authorization() -> None:
    executable = ResolvedExecutable(Path("/usr/bin/demo"), Path("/usr/bin/demo"))
    argv = ("dpkg-query", "-S", "/usr/bin/demo")
    method = Method("apt", {"package": "demo-meta", "ownership_package": "demo-bin"})
    owner = detect_owner(
        _tool(method),
        executable,
        StubRefresh(_platform("debian"), {argv: CommandResult(0, "demo-bin: /usr/bin/demo\n", "")}),
    )
    assert owner.artifact_owner == ArtifactOwner("apt", "demo-bin", "apt")
    assert owner.update_authorization is None


@pytest.mark.parametrize(
    ("requested", "origin"),
    [(["demo"], "layered-package"), ([], "base-image")],
)
def test_rpm_ostree_distinguishes_layered_and_base_image(
    requested: list[str], origin: str
) -> None:
    executable = ResolvedExecutable(Path("/usr/bin/demo"), Path("/usr/bin/demo"))
    rpm = ("rpm", "-q", "--qf", "%{NAME}\\n", "-f", "/usr/bin/demo")
    ostree = ("rpm-ostree", "status", "--json")
    deployment = json.dumps(
        {"deployments": [{"booted": True, "requested-packages": requested}]}
    )
    context = StubRefresh(
        _platform("fedora", immutable=True),
        {rpm: CommandResult(0, "demo\n", ""), ostree: CommandResult(0, deployment, "")},
    )
    owner = detect_owner(_tool(Method("dnf", {"package": "demo"})), executable, context)
    assert owner.origin == origin
    assert owner.update_authorization is None
```

- [ ] **Step 2: Run the focused tests and verify the red state**

Run: `uv run pytest tests/test_ownership.py -k 'native or platform_skipped or ownership_package or rpm_ostree' -v`

Expected: FAIL because adapters are not fully platform-filtered, `ownership_package` is ignored, and rpm-ostree origin is absent.

- [ ] **Step 3: Implement strict apt and pacman adapters**

```python
# installer/ownership.py
def _ownership_package(method: Method, install_key: str) -> tuple[str, str] | None:
    install = _package(method, install_key)
    raw_owner = method.params.get("ownership_package")
    owner = raw_owner if isinstance(raw_owner, str) and raw_owner else install
    if install is None or owner is None:
        return None
    return install, owner


def _apt_owner(
    method: Method, executable: ResolvedExecutable, context: OwnershipRefresh
) -> Ownership:
    packages = _ownership_package(method, "package")
    if packages is None:
        return _unknown("malformed-output", executable, "apt method has no package")
    install_package, owner_package = packages
    argv = ("dpkg-query", "-S", str(executable.canonical_target))
    result = context.probe_once(argv)
    if (outcome := _failure(result)) is not None:
        return _unknown(outcome, executable, result.failure or "dpkg-query failed")
    records = result.stdout.splitlines()
    if result.returncode != 0 or len(records) != 1:
        return _unknown("malformed-output", executable, "dpkg-query returned malformed ownership")
    owner, separator, path = records[0].partition(": ")
    owner = owner.split(":", maxsplit=1)[0]
    if separator != ": " or owner != owner_package or path != str(executable.canonical_target):
        return _unknown("package-mismatch", executable, "dpkg-query names another package or path")
    authorization = (
        UpdateAuthorization("apt", owner_package, "apt")
        if owner_package == install_package
        else None
    )
    return Ownership(
        "verified",
        executable,
        ArtifactOwner("apt", owner_package, "apt"),
        "system-package",
        authorization,
        f"dpkg owns {executable.canonical_target} as {owner_package}",
    )


def _pacman_owner(
    method: Method, executable: ResolvedExecutable, context: OwnershipRefresh
) -> Ownership:
    packages = _ownership_package(method, "package")
    if packages is None:
        return _unknown("malformed-output", executable, "pacman method has no package")
    install_package, owner_package = packages
    result = context.probe_once(("pacman", "-Qqo", str(executable.canonical_target)))
    if (outcome := _failure(result)) is not None:
        return _unknown(outcome, executable, result.failure or "pacman failed")
    records = result.stdout.splitlines()
    if result.returncode != 0 or records != [owner_package]:
        return _unknown("package-mismatch", executable, "pacman names another package")
    authorization = (
        UpdateAuthorization("pacman", owner_package, "pacman")
        if owner_package == install_package
        else None
    )
    return Ownership(
        "verified",
        executable,
        ArtifactOwner("pacman", owner_package, "pacman"),
        "system-package",
        authorization,
        f"pacman owns {executable.canonical_target} as {owner_package}",
    )
```

- [ ] **Step 4: Implement RPM and rpm-ostree origin parsing**

```python
# installer/ownership.py
def _rpm_ostree_origin(package: str, context: OwnershipRefresh) -> tuple[InstallationOrigin, str]:
    result = context.probe_once(("rpm-ostree", "status", "--json"))
    if result.failure is not None or result.returncode != 0:
        return "unknown", result.failure or "rpm-ostree status failed"
    parsed = _json_object(result.stdout)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("deployments"), list):
        return "unknown", "rpm-ostree returned malformed deployment data"
    deployments = parsed["deployments"]
    booted = [item for item in deployments if isinstance(item, dict) and item.get("booted") is True]
    if len(booted) != 1 or not isinstance(booted[0].get("requested-packages"), list):
        return "unknown", "rpm-ostree returned malformed booted deployment data"
    requested = booted[0]["requested-packages"]
    if not all(isinstance(item, str) for item in requested):
        return "unknown", "rpm-ostree requested packages are malformed"
    if package in requested:
        return "layered-package", f"rpm-ostree layers {package}"
    return "base-image", f"rpm-ostree base image supplies {package}"


def _rpm_owner(
    method: Method, executable: ResolvedExecutable, context: OwnershipRefresh
) -> Ownership:
    packages = _ownership_package(method, "package")
    if packages is None:
        return _unknown("malformed-output", executable, "RPM method has no package")
    install_package, owner_package = packages
    argv = ("rpm", "-q", "--qf", "%{NAME}\\n", "-f", str(executable.canonical_target))
    result = context.probe_once(argv)
    if (outcome := _failure(result)) is not None:
        return _unknown(outcome, executable, result.failure or "RPM query failed")
    if result.returncode != 0 or result.stdout.splitlines() != [owner_package]:
        return _unknown("package-mismatch", executable, "RPM names another package")
    if context.platform.immutable:
        origin, detail = _rpm_ostree_origin(owner_package, context)
        return Ownership(
            "verified" if origin != "unknown" else "malformed-output",
            executable,
            ArtifactOwner("rpm", owner_package, method.kind),
            origin,
            None,
            detail,
        )
    authorization = (
        UpdateAuthorization("dnf", owner_package, "dnf")
        if method.kind == "dnf" and owner_package == install_package
        else None
    )
    return Ownership(
        "verified",
        executable,
        ArtifactOwner("rpm", owner_package, method.kind),
        "system-package",
        authorization,
        f"RPM owns {executable.canonical_target} as {owner_package}",
    )
```

Treat both `dnf` and `rpm_ostree` methods as RPM evidence on Fedora. Do not run `dnf repoquery`, `rpm-ostree install`, or `rpm-ostree upgrade` during inspection.

- [ ] **Step 5: Run tests and all quality gates**

Run: `uv run pytest tests/test_ownership.py -k 'native or platform_skipped or ownership_package or rpm_ostree' -v && make validate && make test`

Expected: all commands exit 0; foreign-platform adapters run zero probes, rpm-ostree status is cached per refresh, and immutable origins have no update authorization.

- [ ] **Step 6: Commit native ownership adapters**

```bash
git add installer/ownership.py tests/test_ownership.py
git commit -m "feat(status): classify native package origins" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 5: Gate Update Discovery and Execution on Explicit Authorization

**Files:**
- Modify: `installer/updates.py:1-298`
- Modify: `installer/engine.py:10-15,106-122`
- Modify: `installer/catalog_tui.py:220-282`
- Modify: `installer/wizard_app.py` verified-update predicate only
- Modify: `tests/test_updates.py:1-466`
- Modify: `tests/test_engine.py` update tests
- Modify: `tests/test_catalog_tui.py` owner rendering fixtures
- Modify: `tests/test_wizard_app.py` update-selection fixtures

**Interfaces:**
- Consumes: `Ownership.update_authorization: UpdateAuthorization | None`.
- Produces: `inspect_update(tool: Tool, ownership: Ownership, update_runner: UpdateRunner) -> UpdateStatus` with no query when authorization is absent.
- Produces: `update_argv(tool: Tool, authorization: UpdateAuthorization | None) -> list[str] | None`.
- Retains: existing reviewed argv for brew, pnpm, apt, dnf, and pacman; no rpm-ostree per-package mutation is added.

- [ ] **Step 1: Write failing authorization-independence tests**

```python
# tests/test_updates.py
def _ownership(
    owner: ArtifactOwner,
    authorization: UpdateAuthorization | None,
) -> Ownership:
    path = ResolvedExecutable(Path("/fixture/bin/demo"), Path("/fixture/bin/demo"))
    return Ownership("verified", path, owner, "user", authorization, "fixture")


def test_verified_owner_without_authorization_runs_no_update_query() -> None:
    commands: list[list[str]] = []
    ownership = _ownership(ArtifactOwner("Volta", "demo", "node"), None)
    status = inspect_update(_tool("demo", "node"), ownership, commands.append)
    assert status == UpdateStatus("unsupported", None, "verified owner has no reviewed update authorization")
    assert commands == []


def test_artifact_owner_does_not_override_distinct_authorization() -> None:
    commands: list[list[str]] = []
    ownership = _ownership(
        ArtifactOwner("pnpm", "demo", "node"),
        UpdateAuthorization("brew", "demo", "brew"),
    )
    assert inspect_update(_tool("demo", "node"), ownership, commands.append).state == "unknown"
    assert update_argv(_tool("demo", "node"), ownership.update_authorization) is None
    assert commands == []


@pytest.mark.parametrize(
    ("authorization", "expected"),
    [
        (UpdateAuthorization("pnpm", "demo", "node"), ["pnpm", "add", "-g", "demo"]),
        (UpdateAuthorization("brew", "demo", "brew"), ["brew", "upgrade", "demo"]),
        (
            UpdateAuthorization("apt", "demo", "apt"),
            ["sudo", "apt-get", "install", "--only-upgrade", "-y", "demo"],
        ),
        (UpdateAuthorization("dnf", "demo", "dnf"), ["sudo", "dnf", "upgrade", "-y", "demo"]),
        (
            UpdateAuthorization("pacman", "demo", "pacman"),
            ["sudo", "pacman", "-S", "--noconfirm", "demo"],
        ),
    ],
)
def test_authorized_update_argv_is_fixed(
    authorization: UpdateAuthorization, expected: list[str]
) -> None:
    assert update_argv(_tool("demo", authorization.method_kind), authorization) == expected
```

- [ ] **Step 2: Run update and engine tests and verify the red state**

Run: `uv run pytest tests/test_updates.py tests/test_engine.py -k 'authorization or update' -v`

Expected: FAIL because update code still derives authority from legacy ownership fields.

- [ ] **Step 3: Replace owner-derived update routing with authorization routing**

```python
# installer/updates.py
_OUTDATED_COMMANDS: dict[UpdateMechanism, Callable[[str], list[str]]] = {
    "pnpm": lambda package: ["pnpm", "outdated", "--global", "--format", "json", package],
    "brew": lambda package: ["brew", "outdated", "--json=v2", "--formula", package],
    "apt": lambda package: ["apt-get", "--simulate", "--only-upgrade", "install", package],
    "dnf": lambda package: ["dnf", "check-update", package],
    "pacman": lambda package: ["pacman", "-Qu", package],
}
_UPDATE_COMMANDS: dict[UpdateMechanism, Callable[[str], list[str]]] = {
    "pnpm": lambda package: ["pnpm", "add", "-g", package],
    "brew": lambda package: ["brew", "upgrade", package],
    "apt": lambda package: ["sudo", "apt-get", "install", "--only-upgrade", "-y", package],
    "dnf": lambda package: ["sudo", "dnf", "upgrade", "-y", package],
    "pacman": lambda package: ["sudo", "pacman", "-S", "--noconfirm", package],
}


def _declares_authorization(tool: Tool, authorization: UpdateAuthorization) -> bool:
    package_key = "npm_pkg" if authorization.method_kind == "node" else (
        "formula" if authorization.method_kind == "brew" else "package"
    )
    return any(
        method.kind == authorization.method_kind
        and method.params.get(package_key) == authorization.package
        for method in tool.methods
    )


def inspect_update(
    tool: Tool, ownership: Ownership, update_runner: UpdateRunner
) -> UpdateStatus:
    authorization = ownership.update_authorization
    if ownership.artifact_owner is None:
        return UpdateStatus("unknown", None, ownership.detail)
    if authorization is None:
        return UpdateStatus(
            "unsupported", None, "verified owner has no reviewed update authorization"
        )
    if not _declares_authorization(tool, authorization):
        return UpdateStatus("unknown", None, "update authorization does not match the registry")
    factory = _OUTDATED_COMMANDS.get(authorization.mechanism)
    if factory is None:
        return UpdateStatus("unsupported", None, "no reviewed update adapter matches authorization")
    return _parse_outdated(authorization, update_runner(factory(authorization.package)))


def update_argv(
    tool: Tool, authorization: UpdateAuthorization | None
) -> list[str] | None:
    if authorization is None or not _declares_authorization(tool, authorization):
        return None
    factory = _UPDATE_COMMANDS.get(authorization.mechanism)
    return factory(authorization.package) if factory is not None else None
```

Change `_parse_outdated` to branch on `authorization.mechanism`. Keep every existing parser's strict output validation unchanged.

- [ ] **Step 4: Adapt engine and UI consumers without redesigning behavior**

```python
# installer/engine.py, update_tool body
if ownership.artifact_owner is None or update.state != "available":
    return InstallOutcome(tool.id, "no-method")
authorization = ownership.update_authorization
command = update_argv(tool, authorization)
if command is None:
    return InstallOutcome(tool.id, "no-method")
try:
    runner(command)
except CommandError as error:
    method = authorization.method_kind if authorization is not None else None
    return InstallOutcome(tool.id, "failed", method, (error,))
method = authorization.method_kind if authorization is not None else None
return InstallOutcome(tool.id, "installed", method)
```

In `installer/catalog_tui.py`, render `ownership.artifact_owner.manager` when the owner is present, append `ownership.origin` when it is not `unknown`, and render `ownership.detail` otherwise. In `installer/wizard_app.py`, replace the old `confidence == "verified"` update predicate with `ownership.update_authorization is not None and update.state == "available"`. Do not change messages, keys, layout, generation handling, or selection mutation.

- [ ] **Step 5: Run affected tests and all quality gates**

Run: `uv run pytest tests/test_updates.py tests/test_engine.py tests/test_catalog_tui.py tests/test_wizard_app.py -v && make validate && make test`

Expected: all commands exit 0; Volta and immutable RPM ownership run no update query or mutation, while reviewed authorized managers retain their exact argv.

- [ ] **Step 6: Commit the authorization boundary**

```bash
git add installer/updates.py installer/engine.py installer/catalog_tui.py installer/wizard_app.py tests/test_updates.py tests/test_engine.py tests/test_catalog_tui.py tests/test_wizard_app.py
git commit -m "fix(updates): require explicit update authorization" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 6: Add Atomic Digest-Bearing Installer Receipts

**Files:**
- Create: `installer/receipts.py`
- Create: `tests/test_receipts.py`

**Interfaces:**
- Produces: `InstallEvidence(source, resolved_version, asset, expected_checksum, installed_paths)`.
- Produces: `ReceiptArtifact(path: Path, sha256: str)` and `Receipt(schema_version, tool_id, method_kind, source, resolved_version, asset, expected_checksum, artifacts)`.
- Produces: `ReceiptStore(root: Path)`, `ReceiptStore.issue(tool_id, method_kind, evidence) -> Receipt`, and `ReceiptStore.verify(tool_id, executable) -> ReceiptVerification`.
- Produces: deterministic SHA-256 for files, symlink targets, and directory trees.

- [ ] **Step 1: Write failing issue, verify, malformed, mismatch, and atomicity tests**

```python
# tests/test_receipts.py
import json
import os
from pathlib import Path

import pytest

from installer.ownership import ResolvedExecutable
from installer.receipts import InstallEvidence, ReceiptStore


def _evidence(path: Path, *, version: str = "1.0.0") -> InstallEvidence:
    return InstallEvidence(
        source="https://example.test/demo-1.0.0.tar.gz",
        resolved_version=version,
        asset="demo-1.0.0.tar.gz",
        expected_checksum="a" * 64,
        installed_paths=(path,),
    )


def test_issue_writes_complete_json_and_verify_checks_final_digest(tmp_path: Path) -> None:
    artifact = tmp_path / "bin" / "demo"
    artifact.parent.mkdir()
    artifact.write_bytes(b"version one")
    store = ReceiptStore(tmp_path / "receipts")
    receipt = store.issue("demo", "github_release", _evidence(artifact))
    payload = json.loads((tmp_path / "receipts" / "demo.json").read_text())
    assert payload == {
        "schema_version": 1,
        "tool_id": "demo",
        "method_kind": "github_release",
        "source": "https://example.test/demo-1.0.0.tar.gz",
        "resolved_version": "1.0.0",
        "asset": "demo-1.0.0.tar.gz",
        "expected_checksum": "a" * 64,
        "artifacts": [{"path": str(artifact.absolute()), "sha256": receipt.artifacts[0].sha256}],
    }
    executable = ResolvedExecutable(artifact, artifact.resolve(strict=True))
    assert store.verify("demo", executable).outcome == "verified"
    artifact.write_bytes(b"tampered")
    assert store.verify("demo", executable).outcome == "artifact-mismatch"


def test_missing_receipt_and_malformed_receipt_are_distinct(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path / "receipts")
    assert store.verify("demo", None).outcome == "receipt-absent"
    store.root.mkdir(parents=True)
    (store.root / "demo.json").write_text('{"schema_version": 1}')
    assert store.verify("demo", None).outcome == "malformed-output"


def test_failed_atomic_replace_preserves_previous_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo"
    artifact.write_bytes(b"one")
    store = ReceiptStore(tmp_path / "receipts")
    store.issue("demo", "script", _evidence(artifact, version="1"))
    original = (store.root / "demo.json").read_bytes()
    artifact.write_bytes(b"two")
    monkeypatch.setattr(os, "replace", lambda _source, _target: (_ for _ in ()).throw(OSError("full")))
    with pytest.raises(OSError, match="full"):
        store.issue("demo", "script", _evidence(artifact, version="2"))
    assert (store.root / "demo.json").read_bytes() == original


def test_directory_digest_changes_when_nested_app_file_changes(tmp_path: Path) -> None:
    bundle = tmp_path / "Demo.app"
    binary = bundle / "Contents" / "MacOS" / "demo"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"one")
    store = ReceiptStore(tmp_path / "receipts")
    store.issue("demo", "app", _evidence(bundle))
    binary.write_bytes(b"two")
    assert store.verify("demo", None).outcome == "artifact-mismatch"
```

- [ ] **Step 2: Run receipt tests and verify the red state**

Run: `uv run pytest tests/test_receipts.py -v`

Expected: FAIL because `installer.receipts` does not exist.

- [ ] **Step 3: Implement the strict schema and deterministic digest**

```python
# installer/receipts.py
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from installer.ownership import OwnershipOutcome, ResolvedExecutable


@dataclass(frozen=True)
class InstallEvidence:
    source: str
    resolved_version: str | None
    asset: str | None
    expected_checksum: str | None
    installed_paths: tuple[Path, ...]


@dataclass(frozen=True)
class ReceiptArtifact:
    path: Path
    sha256: str


@dataclass(frozen=True)
class Receipt:
    schema_version: Literal[1]
    tool_id: str
    method_kind: str
    source: str
    resolved_version: str | None
    asset: str | None
    expected_checksum: str | None
    artifacts: tuple[ReceiptArtifact, ...]


@dataclass(frozen=True)
class ReceiptVerification:
    outcome: OwnershipOutcome
    receipt: Receipt | None
    detail: str


def _path_digest(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    if path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
        for item in files:
            relative = item.relative_to(path).as_posix().encode()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(bytes.fromhex(_path_digest(item)))
        return digest.hexdigest()
    raise OSError(f"installed path is not a file or directory: {path}")


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _parse_receipt(raw: object, expected_tool_id: str) -> Receipt | None:
    if not isinstance(raw, dict):
        return None
    value = cast(dict[str, object], raw)
    required = {
        "schema_version",
        "tool_id",
        "method_kind",
        "source",
        "resolved_version",
        "asset",
        "expected_checksum",
        "artifacts",
    }
    if (
        set(value) != required
        or not isinstance(value["schema_version"], int)
        or isinstance(value["schema_version"], bool)
        or value["schema_version"] != 1
    ):
        return None
    tool_id = value["tool_id"]
    method_kind = value["method_kind"]
    source = value["source"]
    if (
        not isinstance(tool_id, str)
        or tool_id != expected_tool_id
        or not isinstance(method_kind, str)
        or not method_kind
        or not isinstance(source, str)
        or not source
    ):
        return None
    resolved_version = value["resolved_version"]
    asset = value["asset"]
    checksum = value["expected_checksum"]
    if resolved_version is not None and _optional_string(resolved_version) is None:
        return None
    if asset is not None and _optional_string(asset) is None:
        return None
    if checksum is not None and (
        not isinstance(checksum, str)
        or len(checksum) != 64
        or any(character not in "0123456789abcdef" for character in checksum)
    ):
        return None
    raw_artifacts = value["artifacts"]
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        return None
    artifacts: list[ReceiptArtifact] = []
    for raw_artifact in cast(list[object], raw_artifacts):
        if not isinstance(raw_artifact, dict):
            return None
        artifact = cast(dict[str, object], raw_artifact)
        if set(artifact) != {"path", "sha256"}:
            return None
        raw_path = artifact["path"]
        digest = artifact["sha256"]
        if (
            not isinstance(raw_path, str)
            or not Path(raw_path).is_absolute()
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            return None
        artifacts.append(ReceiptArtifact(Path(raw_path), digest))
    if len({artifact.path for artifact in artifacts}) != len(artifacts):
        return None
    return Receipt(
        1,
        tool_id,
        method_kind,
        source,
        _optional_string(resolved_version),
        _optional_string(asset),
        _optional_string(checksum),
        tuple(artifacts),
    )
```

Strictly reject relative artifact paths, duplicate paths, unknown or missing JSON keys, non-hex or non-64-character digests, a schema version other than `1`, and empty `tool_id`, `method_kind`, or `source`. `expected_checksum` may be `None`; when present it must be 64 lowercase hex characters.

- [ ] **Step 4: Implement atomic issue and verification**

```python
# installer/receipts.py
class ReceiptStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, tool_id: str) -> Path:
        if not tool_id or Path(tool_id).name != tool_id:
            raise ValueError("tool_id must be one path-safe name")
        return self.root / f"{tool_id}.json"

    def issue(self, tool_id: str, method_kind: str, evidence: InstallEvidence) -> Receipt:
        if not method_kind or not evidence.source or not evidence.installed_paths:
            raise ValueError("receipt requires method, source, and installed paths")
        artifacts = tuple(
            ReceiptArtifact(path.absolute(), _path_digest(path.absolute()))
            for path in evidence.installed_paths
        )
        if len({artifact.path for artifact in artifacts}) != len(artifacts):
            raise ValueError("receipt contains duplicate installed paths")
        receipt = Receipt(
            1,
            tool_id,
            method_kind,
            evidence.source,
            evidence.resolved_version,
            evidence.asset,
            evidence.expected_checksum,
            artifacts,
        )
        payload = {
            "schema_version": receipt.schema_version,
            "tool_id": receipt.tool_id,
            "method_kind": receipt.method_kind,
            "source": receipt.source,
            "resolved_version": receipt.resolved_version,
            "asset": receipt.asset,
            "expected_checksum": receipt.expected_checksum,
            "artifacts": [
                {"path": str(artifact.path), "sha256": artifact.sha256}
                for artifact in receipt.artifacts
            ],
        }
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{tool_id}.", suffix=".tmp", dir=self.root)
        temporary_path = Path(temporary)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self._path(tool_id))
        finally:
            temporary_path.unlink(missing_ok=True)
        return receipt

    def _load(self, tool_id: str) -> ReceiptVerification:
        path = self._path(tool_id)
        try:
            raw = json.loads(path.read_text())
        except FileNotFoundError:
            return ReceiptVerification("receipt-absent", None, "installer receipt is absent")
        except (OSError, ValueError):
            return ReceiptVerification("malformed-output", None, "installer receipt is unreadable")
        receipt = _parse_receipt(raw, tool_id)
        if receipt is None:
            return ReceiptVerification("malformed-output", None, "installer receipt is malformed")
        return ReceiptVerification("verified", receipt, "installer receipt is well formed")

    def verify(
        self, tool_id: str, executable: ResolvedExecutable | None
    ) -> ReceiptVerification:
        loaded = self._load(tool_id)
        if loaded.receipt is None:
            return loaded
        receipt = loaded.receipt
        if executable is not None:
            targets = {
                artifact.path.resolve(strict=True)
                for artifact in receipt.artifacts
                if artifact.path.exists()
            }
            if executable.canonical_target not in targets and executable.path_entry not in {
                artifact.path for artifact in receipt.artifacts
            }:
                return ReceiptVerification(
                    "artifact-mismatch", receipt, "PATH executable is not recorded by the receipt"
                )
        try:
            matches = all(
                _path_digest(artifact.path) == artifact.sha256 for artifact in receipt.artifacts
            )
        except OSError:
            matches = False
        if not matches:
            return ReceiptVerification(
                "artifact-mismatch", receipt, "installed path digest does not match the receipt"
            )
        return ReceiptVerification("verified", receipt, "receipt digests match installed paths")
```

- [ ] **Step 5: Run receipt tests and all quality gates**

Run: `uv run pytest tests/test_receipts.py -v && make validate && make test`

Expected: all commands exit 0; a failed replace leaves the old receipt byte-for-byte intact, and changed or missing artifacts fail verification.

- [ ] **Step 6: Commit the receipt store**

```bash
git add installer/receipts.py tests/test_receipts.py
git commit -m "feat(receipts): record atomic artifact evidence" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 7: Integrate Receipt Ownership Into Plan 1 Status Inspection

**Files:**
- Modify: `installer/ownership.py` receipt adapter and direct-method orchestration
- Modify: `installer/status.py` Plan 1 `RefreshContext` and `inspect_status`
- Modify: `tests/test_ownership.py`
- Modify: `tests/test_status.py`

**Interfaces:**
- Consumes: `ReceiptStore.verify(tool_id, executable) -> ReceiptVerification`.
- Extends: Task 1's structured-result `RefreshContext` with `receipt_store: ReceiptStore | None = None`.
- Extends: `detect_owner(tool, executable, context, receipt_store=None, *, venv_root=active_venv_root()) -> Ownership`.
- Produces: receipt owner `ArtifactOwner("receipt", tool.id, receipt.method_kind)`, origin `direct-installer`, and no update authorization.
- Retains: `initial_statuses` as presence-only and receipt-free.

- [ ] **Step 1: Write failing receipt-owner and status-boundary tests**

```python
# tests/test_ownership.py
def test_valid_receipt_verifies_direct_installer_without_authorizing_update(tmp_path: Path) -> None:
    artifact = tmp_path / "bin" / "demo"
    artifact.parent.mkdir()
    artifact.write_bytes(b"demo")
    store = ReceiptStore(tmp_path / "receipts")
    store.issue(
        "demo",
        "github_release",
        InstallEvidence("https://example.test/demo", "1.0", "demo", None, (artifact,)),
    )
    executable = ResolvedExecutable(artifact, artifact.resolve(strict=True))
    owner = detect_owner(
        _tool(Method("github_release", {"repo": "x/demo", "asset": "demo", "member": "demo"})),
        executable,
        StubRefresh(_platform()),
        receipt_store=store,
    )
    assert owner.artifact_owner == ArtifactOwner("receipt", "demo", "github_release")
    assert owner.origin == "direct-installer"
    assert owner.update_authorization is None


def test_unreceipted_direct_artifact_remains_unknown(tmp_path: Path) -> None:
    executable = _resolved_file(tmp_path / "bin" / "demo")
    owner = detect_owner(
        _tool(Method("script", {"url": "https://example.test/install.sh"})),
        executable,
        StubRefresh(_platform()),
        receipt_store=ReceiptStore(tmp_path / "receipts"),
    )
    assert owner.outcome == "receipt-absent"
    assert owner.artifact_owner is None
```

```python
# tests/test_status.py
def test_initial_statuses_never_read_receipts(tmp_path: Path) -> None:
    statuses = initial_statuses(
        [_tool("demo")],
        executable_resolver=lambda _cmd: None,
    )
    assert statuses["t"].ownership == Ownership(
        "pending", None, None, "unknown", None, "ownership pending"
    )


def test_inspect_status_passes_one_receipt_store_through_refresh_context(tmp_path: Path) -> None:
    artifact = tmp_path / "demo"
    artifact.write_bytes(b"demo")
    store = ReceiptStore(tmp_path / "receipts")
    store.issue(
        "t", "script", InstallEvidence("https://example.test/install", None, None, None, (artifact,))
    )
    context = _refresh_context(
        executable_resolver=lambda _cmd: ResolvedExecutable(artifact, artifact.resolve(strict=True)),
        receipt_store=store,
    )
    status = inspect_status(_script_tool(), include_updates=False, context=context)
    assert status.ownership.artifact_owner == ArtifactOwner("receipt", "t", "script")
```

- [ ] **Step 2: Run focused tests and verify the red state**

Run: `uv run pytest tests/test_ownership.py tests/test_status.py -k receipt -v`

Expected: FAIL because receipt verification and `receipt_store` are not part of ownership or the evolved refresh context.

- [ ] **Step 3: Add the direct-method receipt adapter**

```python
# installer/ownership.py
_RECEIPT_METHODS = frozenset({"script", "github_release", "tarball", "app", "host_setup", "cask"})


def _receipt_owner(
    tool: Tool,
    executable: ResolvedExecutable | None,
    receipt_store: ReceiptStore | None,
) -> Ownership | None:
    if not any(method.kind in _RECEIPT_METHODS for method in tool.methods):
        return None
    if receipt_store is None:
        return _unknown("receipt-absent", executable, "receipt store is unavailable")
    verification = receipt_store.verify(tool.id, executable)
    receipt = verification.receipt
    if verification.outcome != "verified" or receipt is None:
        return _unknown(verification.outcome, executable, verification.detail)
    declared = any(method.kind == receipt.method_kind for method in tool.methods)
    if not declared:
        return _unknown("package-mismatch", executable, "receipt method is not declared by the tool")
    return Ownership(
        "verified",
        executable,
        ArtifactOwner("receipt", tool.id, receipt.method_kind),
        "direct-installer",
        None,
        verification.detail,
    )
```

Evaluate manager adapters first because exact package-manager file databases are stronger than a direct receipt for a command now replaced by a manager. Evaluate `_receipt_owner` after applicable manager adapters and before `_strongest`. A receipt can verify an app bundle when `executable is None` only if Plan 1 already marked the app bundle present; do not make receipts a second presence system.

- [ ] **Step 4: Thread the store through Plan 1's existing inspection only**

```python
# installer/status.py
from installer.receipts import ReceiptStore


@dataclass
class RefreshContext:
    platform: Platform
    probe: ProbeRunner
    health_runner: HealthRunner
    update_runner: UpdateRunner
    executable_resolver: ExecutableResolver
    app_roots: tuple[Path, ...] | None = None
    cache: dict[tuple[str, ...], Future[CommandResult]] = field(default_factory=dict)
    cache_lock: Lock = field(default_factory=Lock)
    receipt_store: ReceiptStore | None = None


# Inside inspect_status's per-tool inspection, after presence and health:
ownership = detect_owner(
    tool,
    executable,
    context,
    receipt_store=context.receipt_store,
)
```

Do not add `receipt_store` to `initial_statuses`; its signature and local-only behavior stay unchanged.

- [ ] **Step 5: Run tests and all quality gates**

Run: `uv run pytest tests/test_ownership.py tests/test_status.py tests/test_receipts.py -v && make validate && make test`

Expected: all commands exit 0; unreceipted direct artifacts remain `receipt-absent`, receipt digests are checked only during deep inspection, and no receipt grants updates.

- [ ] **Step 6: Commit receipt-backed ownership**

```bash
git add installer/ownership.py installer/status.py tests/test_ownership.py tests/test_status.py
git commit -m "feat(status): verify installer receipt ownership" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 8: Issue Receipts From Successful Direct Installers and Wire Production State

**Files:**
- Modify: `installer/download.py:41-209`
- Modify: `installer/apps.py:23-84`
- Modify: `installer/engine.py:31-103`
- Modify: `setup.py:36-57,144-177,266-291`
- Modify: `tests/test_download.py`
- Modify: `tests/test_apps.py`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_setup.py`

**Interfaces:**
- Changes: `install_download(method: Method, ctx: ExecContext) -> tuple[bool, InstallEvidence]`.
- Changes: `install_app(method: Method, runner: Runner) -> InstallEvidence`.
- Extends: `install_tool(..., receipt_store: ReceiptStore | None = None, artifact_resolver: ExecutableResolver = resolve_executable) -> InstallOutcome`.
- Produces: receipts after successful `script`, `github_release`, `tarball`, and `app` installs when concrete artifacts exist.
- Excludes: `node`, brew/cask package-manager installs, apt/dnf/pacman/rpm-ostree installs, failed methods, checksum mismatches, and `host_setup` manual handoffs.

- [ ] **Step 1: Write failing download and app evidence tests**

```python
# tests/test_download.py
def test_verified_download_returns_receipt_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    payload = b"archive"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {RG_ASSET}\n".encode()
    _, runner = _fixture_runner(workdir, {RG_ASSET: payload, f"{RG_ASSET}.sha256": sums})
    verified, evidence = install_download(
        _rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0")
    )
    assert verified is True
    assert evidence.source == f"{RG_BASE}/{RG_ASSET}"
    assert evidence.resolved_version == "15.1.0"
    assert evidence.asset == RG_ASSET
    assert evidence.expected_checksum == hashlib.sha256(payload).hexdigest()
    assert evidence.installed_paths == (
        tmp_path / ".local" / "opt" / "rg" / "rg",
        tmp_path / "bin" / "rg",
    )
```

```python
# tests/test_apps.py
def test_app_returns_bundle_and_cli_receipt_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    evidence = install_app(
        _method(cli="Contents/SharedSupport/bin/demo"), runner
    )
    bundle = tmp_path / "Applications" / "Demo App.app"
    assert evidence == InstallEvidence(
        source="https://example.test/app.zip",
        resolved_version=None,
        asset="app.zip",
        expected_checksum=None,
        installed_paths=(bundle, tmp_path / ".local" / "bin" / "demo"),
    )
    assert len(calls) == 2
```

- [ ] **Step 2: Run evidence tests and verify the red state**

Run: `uv run pytest tests/test_download.py tests/test_apps.py -k receipt_evidence -v`

Expected: FAIL because download returns only `bool` and app returns `None`.

- [ ] **Step 3: Return exact evidence from download and app executors**

```python
# installer/download.py
@dataclass(frozen=True)
class DownloadTarget:
    url: str
    member: str
    asset: str
    resolved_version: str | None
    checksum: tuple[str, str] | None = None


def install_download(method: Method, ctx: ExecContext) -> tuple[bool, InstallEvidence]:
    target = _resolve_target(method, ctx)
    binname = PurePosixPath(target.member).name
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as error:
        raise ExecutorError(f"cannot create bin dir: {error}") from error
    link = dest / binname
    if target.checksum is None:
        installed = _install_unverified(method, ctx, target, link)
        return False, InstallEvidence(
            target.url, target.resolved_version, target.asset, None, installed
        )
    installed, expected = _install_verified(method, ctx, target, link, target.checksum)
    return True, InstallEvidence(
        target.url, target.resolved_version, target.asset, expected, installed
    )
```

Replace the return points in `_resolve_target` with these exact constructors; all URL, member, asset, and checksum rendering around them remains unchanged:

```python
# installer/download.py, _resolve_target
if checksum_template is None:
    return DownloadTarget(
        url=f"{base}/{asset}",
        member=member,
        asset=asset,
        resolved_version=tag,
    )
return DownloadTarget(
    url=f"{base}/{asset}",
    member=member,
    asset=asset,
    resolved_version=tag,
    checksum=(f"{base}/{checksum_name}", checksum_name),
)

# tarball branch
return DownloadTarget(
    url=url,
    member=raw_member,
    asset=PurePosixPath(url).name,
    resolved_version=None,
)
```

Replace the three placement functions with these complete versions:

```python
# installer/download.py
def _install_unverified(
    method: Method, ctx: ExecContext, target: DownloadTarget, link: Path
) -> tuple[Path, ...]:
    quoted_url = shlex.quote(target.url)
    if method.params.get("raw") is True:
        quoted_link = shlex.quote(str(link))
        ctx.runner(["sh", "-c", f"curl -fsSL -o {quoted_link} -- {quoted_url}"])
        ctx.runner(["chmod", "+x", str(link)])
        return (link,)
    strip = _opt_int(method, "strip", 0)
    try:
        opt = ensure_dir(opt_dir(link.name))
    except OSError as error:
        raise ExecutorError(f"cannot create opt dir: {error}") from error
    binary = opt / target.member
    quoted_opt = shlex.quote(str(opt))
    quoted_member = shlex.quote(target.member)
    if _opt_str(method, "archive") == "zip":
        extract = (
            "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && unzip -q -o "$tmp" {quoted_member} -d {quoted_opt}'
        )
    else:
        extract = (
            "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && tar -xzf "$tmp" -C {quoted_opt} --strip-components={strip}'
        )
    ctx.runner(["sh", "-c", extract])
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])
    return binary, link


def _install_verified(
    method: Method,
    ctx: ExecContext,
    target: DownloadTarget,
    link: Path,
    checksum: tuple[str, str],
) -> tuple[tuple[Path, ...], str]:
    checksum_url, checksum_name = checksum
    workdir = Path(tempfile.mkdtemp(prefix="tools-installer-"))
    try:
        asset_path = workdir / target.asset
        sum_path = workdir / checksum_name
        fetch = (
            f"curl -fsSL -o {shlex.quote(str(asset_path))} -- {shlex.quote(target.url)}"
            f" && curl -fsSL -o {shlex.quote(str(sum_path))} -- {shlex.quote(checksum_url)}"
        )
        ctx.runner(["sh", "-c", fetch])
        try:
            text = sum_path.read_text()
        except OSError as error:
            raise ExecutorError(f"cannot read checksum file '{checksum_name}': {error}") from error
        expected = expected_sha256(text, target.asset)
        if expected is None:
            raise ExecutorError(f"no sha256 entry for '{target.asset}' in '{checksum_name}'")
        try:
            actual = sha256_file(asset_path)
        except OSError as error:
            raise ExecutorError(f"cannot hash downloaded asset '{target.asset}': {error}") from error
        if actual != expected:
            raise ChecksumMismatch(target.asset, expected, actual)
        return _place_verified(method, ctx, target, link, asset_path), expected
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _place_verified(
    method: Method,
    ctx: ExecContext,
    target: DownloadTarget,
    link: Path,
    asset_path: Path,
) -> tuple[Path, ...]:
    if method.params.get("raw") is True:
        ctx.runner(["cp", str(asset_path), str(link)])
        ctx.runner(["chmod", "+x", str(link)])
        return (link,)
    try:
        opt = ensure_dir(opt_dir(link.name))
    except OSError as error:
        raise ExecutorError(f"cannot create opt dir: {error}") from error
    binary = opt / target.member
    if _opt_str(method, "archive") == "zip":
        ctx.runner(["unzip", "-q", "-o", str(asset_path), target.member, "-d", str(opt)])
    else:
        strip = _opt_int(method, "strip", 0)
        ctx.runner(
            ["tar", "-xzf", str(asset_path), "-C", str(opt), f"--strip-components={strip}"]
        )
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])
    return binary, link
```

```python
# installer/apps.py
def install_app(method: Method, runner: Runner) -> InstallEvidence:
    url = require_str(method, "url")
    app = require_str(method, "app")
    if PurePosixPath(app).name != app or app in (".", ".."):
        raise ExecutorError(f"invalid app bundle name '{app}'")
    spec = cli_spec(method)
    try:
        apps = ensure_dir(applications_dir())
    except OSError as error:
        raise ExecutorError(f"cannot create Applications dir: {error}") from error
    pipeline = (
        "tmp=$(mktemp -d) && trap 'rm -rf \"$tmp\"' EXIT"
        f' && curl -fsSL -o "$tmp/app.zip" -- {shlex.quote(url)}'
        ' && ditto -x -k "$tmp/app.zip" "$tmp/x"'
        f' && mv "$tmp/x/"{shlex.quote(app)} {shlex.quote(str(apps))}/'
    )
    runner(["sh", "-c", pipeline])
    bundle = apps / app
    installed: tuple[Path, ...] = (bundle,)
    if spec is not None:
        cli, name = spec
        try:
            dest = ensure_dir(bin_dir(None))
        except OSError as error:
            raise ExecutorError(f"cannot create bin dir: {error}") from error
        link = dest / name
        runner(["ln", "-sf", str(bundle / cli), str(link)])
        installed = (bundle, link)
    return InstallEvidence(
        source=url,
        resolved_version=None,
        asset=PurePosixPath(url).name or None,
        expected_checksum=None,
        installed_paths=installed,
)
```

- [ ] **Step 4: Write failing engine issuance-boundary tests**

```python
# tests/test_engine.py
def test_successful_script_install_issues_receipt_for_resolved_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _not_installed(monkeypatch)
    artifact = tmp_path / "bin" / "demo"
    artifact.parent.mkdir()
    store = ReceiptStore(tmp_path / "receipts")

    def runner(_argv: list[str]) -> None:
        artifact.write_bytes(b"installed")

    outcome = install_tool(
        _tool(Method("script", {"url": "https://example.test/install.sh"})),
        _platform(),
        runner=runner,
        receipt_store=store,
        artifact_resolver=lambda _cmd: ResolvedExecutable(artifact, artifact.resolve(strict=True)),
    )
    assert outcome.status == "installed"
    assert store.verify("rg", ResolvedExecutable(artifact, artifact.resolve(strict=True))).outcome == "verified"


@pytest.mark.parametrize(
    "method",
    [
        Method("node", {"npm_pkg": "demo"}),
        Method("brew", {"formula": "demo"}),
        Method("dnf", {"package": "demo"}),
    ],
)
def test_manager_installs_never_issue_direct_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: Method
) -> None:
    _not_installed(monkeypatch)
    store = ReceiptStore(tmp_path / "receipts")
    platform = Platform("fedora", "amd64", False, method.kind == "brew")
    assert install_tool(_tool(method), platform, runner=lambda _argv: None, receipt_store=store).status == "installed"
    assert store.verify("rg", None).outcome == "receipt-absent"


def test_manual_host_setup_never_issues_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _not_installed(monkeypatch)
    store = ReceiptStore(tmp_path / "receipts")
    outcome = install_tool(
        _tool(Method("host_setup", {"setup_id": "pi"})),
        _platform(),
        receipt_store=store,
    )
    assert outcome.status == "manual-required"
    assert store.verify("rg", None).outcome == "receipt-absent"


def test_receipt_failure_does_not_fall_through_after_direct_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _not_installed(monkeypatch)
    artifact = tmp_path / "demo"
    calls: list[list[str]] = []

    class FailingStore(ReceiptStore):
        def issue(
            self, tool_id: str, method_kind: str, evidence: InstallEvidence
        ) -> Receipt:
            raise OSError("state directory is full")

    def runner(argv: list[str]) -> None:
        calls.append(argv)
        artifact.write_bytes(b"installed")

    outcome = install_tool(
        _tool(
            Method("script", {"url": "https://example.test/install.sh"}),
            Method("brew", {"formula": "demo"}),
        ),
        Platform("fedora", "amd64", False, True),
        runner=runner,
        receipt_store=FailingStore(tmp_path / "receipts"),
        artifact_resolver=lambda _cmd: ResolvedExecutable(
            artifact, artifact.resolve(strict=True)
        ),
    )
    assert outcome.status == "failed"
    assert outcome.method_kind == "script"
    assert len(calls) == 1
    assert calls[0][0:2] == ["sh", "-c"]
```

- [ ] **Step 5: Run engine receipt tests and verify the red state**

Run: `uv run pytest tests/test_engine.py -k receipt -v`

Expected: FAIL because `install_tool` does not accept a receipt store or artifact resolver and `_perform` discards install evidence.

- [ ] **Step 6: Issue receipts only after successful concrete direct installs**

```python
# installer/engine.py
_RECEIPT_KINDS = frozenset({"script", "github_release", "tarball", "app"})


def _perform(
    tool: Tool,
    method: Method,
    ctx: ExecContext,
    artifact_resolver: ExecutableResolver,
) -> tuple[bool, tuple[str, ...], InstallEvidence | None]:
    if method.kind in download.DOWNLOAD_KINDS:
        verified, evidence = download.install_download(method, ctx)
        return verified, (), evidence
    if method.kind in apps.APP_KINDS:
        return False, (), apps.install_app(method, ctx.runner)
    status = executors.execute(method, ctx.runner)
    handoff = executors.host_setup_handoff(method) if status == "manual-required" else ()
    if handoff or method.kind != "script":
        return False, handoff, None
    resolved = artifact_resolver(tool.cmd)
    if resolved is None:
        return False, (), None
    url = method.params.get("url")
    if not isinstance(url, str) or not url:
        return False, (), None
    evidence = InstallEvidence(url, None, PurePosixPath(url).name or None, None, (resolved.path_entry,))
    return False, (), evidence


def install_tool(
    tool: Tool,
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    *,
    checksum_policy: ChecksumPolicy = "fail",
    force: bool = False,
    receipt_store: ReceiptStore | None = None,
    artifact_resolver: ExecutableResolver = resolve_executable,
) -> InstallOutcome:
    if not force and is_installed(tool):
        return InstallOutcome(tool.id, "already-installed")
    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, "no-method")
    ctx = ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)
    errors: list[Exception] = []
    for method in methods:
        if isinstance(ctx.runner, MethodAwareRunner):
            ctx.runner.method_started(method.kind)
        try:
            verified, handoff, evidence = _perform(tool, method, ctx, artifact_resolver)
            if handoff:
                return InstallOutcome(tool.id, "manual-required", method.kind, handoff=handoff)
            if receipt_store is not None and method.kind in _RECEIPT_KINDS and evidence is not None:
                try:
                    receipt_store.issue(tool.id, method.kind, evidence)
                except (OSError, ValueError) as error:
                    return InstallOutcome(tool.id, "failed", method.kind, (error,))
            return InstallOutcome(tool.id, "installed", method.kind, verified=verified)
        except ChecksumMismatch as error:
            if checksum_policy == "fail":
                return InstallOutcome(
                    tool.id, "checksum-mismatch", method.kind, (error,)
                )
            errors.append(error)
        except (CommandError, executors.ExecutorError, VersionError) as error:
            errors.append(error)
    return InstallOutcome(tool.id, "failed", errors=tuple(errors))
```

Receipt issuance failure returns a failed outcome for the method that already mutated the filesystem; it must not continue to another install method and create a duplicate installation. Do not delete an older valid receipt until the new receipt's atomic replace succeeds.

- [ ] **Step 7: Wire one production store into inspection and execution**

```python
# setup.py, inside _build_app
receipt_store = ReceiptStore(Path.home() / ".local" / "state" / "tools-installer" / "receipts")


def new_refresh_context() -> RefreshContext:
    return RefreshContext(
        platform=platform,
        probe=probe,
        health_runner=health_runner,
        update_runner=update_runner,
        executable_resolver=executable_resolver,
        receipt_store=receipt_store,
    )
```

Replace the old startup `status_factory(False)` with `initial_statuses(tools, executable_resolver=executable_resolver)`. Pass both Plan 1 callables to `UnifiedApp` in their existing slots:

```python
# setup.py, UnifiedApp construction keyword arguments
inspect_status=inspect_status,
refresh_context=new_refresh_context,
```

In `_start_install`, inject this closure into `run_plan`:

```python
def install_with_receipts(
    tool: Tool,
    current_platform: Platform,
    runner: Runner,
    resolve_tag: TagResolver,
    *,
    checksum_policy: ChecksumPolicy = "fail",
    force: bool = False,
) -> InstallOutcome:
    return install_tool(
        tool,
        current_platform,
        runner,
        resolve_tag,
        checksum_policy=checksum_policy,
        force=force,
        receipt_store=receipt_store,
        artifact_resolver=executable_resolver,
    )
```

Pass `install=install_with_receipts` to `run_plan`. Do not invoke `inspect_status` from `_start_install`; Plan 1's captured operation statuses and post-install coordinator request remain unchanged.

- [ ] **Step 8: Add setup wiring assertions**

```python
# tests/test_setup.py
def test_build_app_shares_receipt_store_between_refresh_and_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    captured: dict[str, object] = {}
    installed_with: list[ReceiptStore | None] = []

    def fake_app(*_args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    def fake_install_tool(
        tool: Tool,
        _platform: Platform,
        _runner: Runner,
        _resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        force: bool = False,
        receipt_store: ReceiptStore | None = None,
        artifact_resolver: ExecutableResolver = resolve_executable,
    ) -> InstallOutcome:
        assert checksum_policy == "fail"
        assert force is False
        assert callable(artifact_resolver)
        installed_with.append(receipt_store)
        return InstallOutcome(tool.id, "installed", "script")

    def fake_run_plan(
        plan: InstallPlan,
        platform: Platform,
        _emit: Callable[[ExecutionEvent], None],
        statuses: Mapping[str, ToolStatus],
        *,
        install: Install,
        **_kwargs: object,
    ) -> Summary:
        tool = plan.ordered[0]
        assert tool.id in statuses
        install(tool, platform, lambda _argv: None, lambda _repo: "1.0")
        return Summary((tool.id,), (), (), ())

    monkeypatch.setattr(setup, "UnifiedApp", fake_app)
    monkeypatch.setattr(setup, "install_tool", fake_install_tool)
    monkeypatch.setattr(setup, "run_plan", fake_run_plan)
    tool = Tool(
        "demo",
        "Demo",
        "fixture",
        "demo",
        (Method("script", {"url": "https://example.test/install.sh"}),),
    )
    setup._build_app([tool], _platform(), enable_install=True)
    context_factory = cast(RefreshContextFactory, captured["refresh_context"])
    start_install = cast(StartInstall, captured["start_install"])
    refresh_context = context_factory()
    plan = InstallPlan((tool.id,), (tool,), (), ())
    status = ToolStatus(
        tool,
        False,
        Ownership("command-missing", None, None, "unknown", None, "fixture"),
    )
    choices = ExecutionChoices(frozenset(), frozenset(), lambda _tool_id: "skip")
    start_install(plan, {tool.id: status}, choices, lambda _event: None)
    assert refresh_context.receipt_store is not None
    assert installed_with == [refresh_context.receipt_store]
    assert refresh_context.receipt_store.root == (
        tmp_path / ".local" / "state" / "tools-installer" / "receipts"
    )
```

- [ ] **Step 9: Run focused integration tests**

Run: `uv run pytest tests/test_download.py tests/test_apps.py tests/test_engine.py tests/test_setup.py tests/test_status.py tests/test_receipts.py -v`

Expected: PASS. Successful direct installs issue complete receipts, manager/manual/failure paths do not, and the next coordinator refresh verifies the same store.

- [ ] **Step 10: Run final quality gates**

Run: `make validate && make test`

Expected: both commands exit 0 with no skips, no warnings introduced by this change, and coverage at or above the configured floor.

- [ ] **Step 11: Inspect the final scope boundary**

Run: `git diff --stat 62e42ef -- installer/ownership.py installer/status.py installer/updates.py installer/catalog_tui.py installer/wizard_app.py installer/receipts.py installer/download.py installer/apps.py installer/engine.py setup.py tests`

Expected: changes are limited to ownership, status integration, update authorization, receipt issuance, setup wiring, and their tests. There are no changes to resolver dependency semantics, SDKMAN/JVM execution, Install dispositions, selection lifecycle, or coordinator generation logic.

- [ ] **Step 12: Commit receipt issuance and integration**

```bash
git add installer/download.py installer/apps.py installer/engine.py setup.py tests/test_download.py tests/test_apps.py tests/test_engine.py tests/test_setup.py
git commit -m "feat(installs): issue receipts for direct artifacts" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Self-Review Results

- **Spec coverage:** Tasks 1 and 5 separate artifact owner, origin, and update authorization; Task 1 atomically migrates `ProbeRunner`, `RefreshContext.probe`, its cached `Future`, and `probe_once` from stdout strings to `CommandResult`, preserves PATH entry/canonical target, filters platforms, excludes the installer venv, and ranks structured outcomes. Tasks 2-4 implement Homebrew, pnpm, Volta, RPM/rpm-ostree, apt, and pacman with fixed argv and refresh-scoped probes. Tasks 6-8 create, verify, issue, and integrate atomic receipts without fabricating history.
- **Scope boundary:** The plan consumes Plan 1's `initial_statuses`, `inspect_status`, and one-context-per-generation coordinator contract. Task 1 evolves only the existing probe/result cache and ownership values; Task 7 adds only receipt input to that context. SDKMAN owner/update values are reserved, but its adapter and candidate verification remain entirely in Plan 3. This plan does not alter coordinator generations, Textual scheduling, registry recommendation/scope/dependencies, JVM installation, dispositions, or selection lifecycle.
- **Placeholder scan:** The plan contains no deferred implementation markers. Every code-changing task supplies concrete tests, interfaces, implementation code, commands, expected results, validation, and a coherent commit.
- **Type consistency:** `ProbeRunner`, `RefreshContext`, `ResolvedExecutable`, `ArtifactOwner`, `UpdateAuthorization`, `Ownership`, `OwnershipRefresh`, `InstallEvidence`, `Receipt`, `ReceiptVerification`, and `ReceiptStore` use the same field names and signatures in all producing and consuming tasks.
