# Responsive Status and Install Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mount the Textual app from presence-only status, enrich status through one app-owned bounded background coordinator, and keep install preparation, completion refresh, and unexpected failures visible and responsive.

**Architecture:** `setup.py` constructs an immutable presence-only snapshot and directly injects the public `installer.status.inspect_status` function plus a factory for refresh-local dependency and probe-cache contexts. `UnifiedApp` owns a `StatusCoordinator` that creates exactly one context for each startup, explicit, or post-install generation, runs per-tool inspection through a bounded thread pool, reports progress on Textual's thread, and atomically applies only the newest complete map. Install execution uses its captured planned-tool statuses, announces preparation before its worker starts, finishes before scheduling refresh, and converts an unexpected worker exception into a terminal failed `Summary`.

**Tech Stack:** Python 3.11+, Textual 8+, standard-library `concurrent.futures`, dataclasses, immutable status snapshots and mappings, pytest 8+, pytest-asyncio, Ruff, Pyright strict mode, Bandit, and Vulture.

## Global Constraints

- `setup.py` builds an initial immutable status map using local presence checks only.
- Textual mounts immediately from this snapshot.
- `UnifiedApp` owns one background status coordinator. It serves startup enrichment, explicit Catalog refresh, and post-install refresh.
- The coordinator runs outside Textual's event loop.
- The coordinator uses bounded concurrency rather than one worker per tool.
- The coordinator reports completed and total tool counts.
- The coordinator assigns each request a generation ID.
- The coordinator creates exactly one refresh-local `RefreshContext` per generation before submitting per-tool futures; overlapping generations never share its probe cache.
- The coordinator discards stale results from superseded generations.
- The coordinator replaces the complete status map atomically on the Textual thread.
- Keys `1-4` remain responsive while this work runs.
- Startup enrichment and post-install refresh run presence, health, and ownership checks.
- Only explicit Catalog refresh runs update discovery.
- Failures preserve the prior complete map and display an error instead of replacing it with partial data.
- Normal install and reinstall do not scan the whole catalog. They use the operation's captured status map and recheck only planned tools where execution requires fresh evidence.
- Install displays `Preparing selected tools...` before preflight work. Once execution starts, existing per-tool method, output, fallback, and result events continue to update the screen.
- Post-install completion first marks Install finished and restores navigation. It then schedules a background Catalog refresh.
- Unexpected worker exceptions become a finished failure summary. No exception may leave Install permanently queued or navigation permanently disabled.
- Health, ownership, and update checks retain their bounded subprocess contracts.
- Manager output is escaped before Rich markup rendering.
- All filesystem state uses `tmp_path`. All subprocess behavior is injected or monkeypatched. Tests never inspect or mutate the real home directory.
- Do not add ownership adapter redesign, receipts, registry audit, SDKMAN, dispositions, or selection lifecycle changes in this plan.
- Do not add a dependency, alter `installer/registry.toml`, lower the 90% coverage floor, weaken strict Pyright, or add a quality-tool suppression.

---

## Baseline And File Map

Build against commit `62e42ef` (`docs(design): define responsive catalog architecture`) in `/var/home/bazzite/git/personal/tools-installer/.worktrees/catalog-reliability-scope-reduction`. Run every command from that worktree. The worktree is clean at planning time.

- `installer/status.py`: retains `ToolStatus` and deep `tool_status`; adds the presence-only constructor, explicit pending ownership value, the pre-structured-ownership `RefreshContext` with a refresh-local stdout-probe cache, and the public three-argument `inspect_status` coordinator adapter.
- `installer/status_coordinator.py`: new Textual-independent coordinator. It owns request generations, one bounded executor, complete immutable results, and count progress.
- `installer/wizard_app.py`: owns the coordinator, starts startup/explicit/post-install generations, moves progress and complete results onto Textual's thread, and preserves the old map on stale results or failures.
- `installer/catalog_tui.py`: retains complete-map validation and atomic replacement. No selection, disposition, registry, or ownership rendering redesign belongs here.
- `installer/install_screen.py`: displays preparation before its worker starts and converts an unexpected worker exception into terminal row states and a failed `Summary`.
- `setup.py`: remains wiring-only. It constructs the immutable presence snapshot, directly injects `installer.status.inspect_status` and `new_refresh_context`, passes captured planned-tool statuses to `run_plan`, and never runs a whole-catalog install preflight.
- `tests/test_status.py`: covers presence-only status without health, ownership, or update work and verifies the public inspector's context forwarding and explicit-only update replacement.
- `tests/test_status_coordinator.py`: new unit coverage for bounded concurrency, complete results, progress counts, and generations.
- `tests/test_setup.py`: proves app construction is presence-only, update inspection is explicit-only, and a single-tool install does not deep-scan the catalog.
- `tests/test_wizard_app.py`: proves immediate mount, responsive navigation, visible progress, stale-result rejection, failure preservation, and completion-before-refresh.
- `tests/test_install_screen.py`: proves preparation appears before blocked work and unexpected worker exceptions finish with a failed summary.
- `tests/test_catalog_tui.py`, `tests/test_uninstall_e2e.py`, and `tests/test_policies_e2e.py`: update `UnifiedApp` construction to the three-argument per-tool inspector and refresh-context factory interfaces without changing their behavior.

## Final Interfaces

```python
# installer/status.py
PENDING_OWNERSHIP: Ownership

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

    def probe_once(self, argv: tuple[str, ...]) -> str: ...

def presence_status(
    tool: Tool,
    app_roots: tuple[Path, ...] | None = None,
    executable_resolver: ExecutableResolver = resolve_executable,
) -> ToolStatus: ...

def inspect_status(
    tool: Tool,
    include_updates: bool,
    context: RefreshContext,
) -> ToolStatus: ...
```

```python
# installer/status_coordinator.py
StatusKind = Literal["startup", "explicit", "post-install"]
StatusInspector = Callable[[Tool, bool, RefreshContext], ToolStatus]
RefreshContextFactory = Callable[[], RefreshContext]

@dataclass(frozen=True)
class StatusRequest:
    generation: int
    kind: StatusKind
    include_updates: bool

@dataclass(frozen=True)
class StatusProgress:
    generation: int
    kind: StatusKind
    completed: int
    total: int

@dataclass(frozen=True)
class StatusResult:
    generation: int
    statuses: Mapping[str, ToolStatus]

class StatusCoordinator:
    def __init__(
        self,
        tools: list[Tool],
        inspect_status: StatusInspector,
        refresh_context: RefreshContextFactory,
        max_workers: int = 4,
    ) -> None: ...

    def request(self, kind: StatusKind) -> StatusRequest: ...
    def refresh(
        self,
        request: StatusRequest,
        progress: Callable[[StatusProgress], None],
    ) -> StatusResult: ...
    def is_current(self, generation: int) -> bool: ...
    def close(self) -> None: ...
```

```python
# installer/wizard_app.py
class UnifiedApp(App[list[str] | None]):
    def __init__(
        self,
        tools: list[Tool],
        statuses: Mapping[str, ToolStatus],
        blurbs: Mapping[str, str],
        *,
        report: DoctorReport,
        guard_status: dict[str, bool],
        guard_warning: str | None,
        fix_preview: str,
        fix: Callable[[], None],
        uninstall: UninstallInputs,
        policies: PolicyInputs,
        inspect_status: StatusInspector,
        refresh_context: RefreshContextFactory,
        status_workers: int = 4,
        initial_view: str = "catalog",
        initial_selected_ids: tuple[str, ...] = (),
        start_install: StartInstall | None = None,
        build_plan: BuildPlan | None = None,
    ) -> None: ...

    def request_status_refresh(self, kind: StatusKind) -> int: ...
```

Apart from the new public `installer.status.inspect_status` function, no other public interface changes. In particular, `StartInstall`, `BuildPlan`, `InstallPlan`, `ExecutionEvent`, `Summary`, `tool_status`, `run_plan`, ownership adapters, registry schema, and selection methods retain their current signatures.

### Task 1: Mount From An Immutable Presence-Only Snapshot

**Files:**
- Modify: `installer/status.py:1-71`
- Modify: `setup.py:10-18, 50-54, 144-180`
- Modify: `tests/test_status.py:1-67`
- Modify: `tests/test_setup.py:1-247, 838-1038`

**Interfaces:**
- Consumes: current `ProbeRunner = Callable[[list[str]], str]`, `HealthRunner`, `UpdateRunner`, `ExecutableResolver = Callable[[str], Path | None]`, `Platform`, `_app_bundle_installed`, `UNKNOWN_HEALTH`, and `UNKNOWN_UPDATE`.
- Produces: `PENDING_OWNERSHIP = Ownership(None, "unknown", "ownership pending")`.
- Produces: mutable per-generation `RefreshContext(platform, probe, health_runner, update_runner, executable_resolver, app_roots=None)` with `cache: dict[tuple[str, ...], Future[str]]`, `cache_lock`, and concurrent `probe_once(argv: tuple[str, ...]) -> str` de-duplication.
- Produces: `presence_status(tool, app_roots=None, executable_resolver=resolve_executable) -> ToolStatus`.
- Produces: public `inspect_status(tool, include_updates, context) -> ToolStatus`, which calls `tool_status` with `context.probe_once`, `context.health_runner`, `context.executable_resolver`, and `context.app_roots`, then replaces only `update` through `inspect_update` when `include_updates` is true.
- Preserves: `tool_status(...) -> ToolStatus` as the deep presence, health, and ownership inspector.
- Behavior: `_build_app` calls the executable resolver once per tool and performs no health, ownership, or update probe before returning `UnifiedApp`.

- [ ] **Step 1: Write the failing presence, refresh-context, and public-inspector unit tests**

Update the imports as shown and add these tests to `tests/test_status.py`:

```python
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from installer.health import UNKNOWN_HEALTH, CommandResult, HealthRunner
from installer.ownership import (
    ExecutableResolution,
    ExecutableResolver,
    Ownership,
    ProbeRunner,
)
from installer.platform import Platform
from installer.status import (
    PENDING_OWNERSHIP,
    RefreshContext,
    ToolStatus,
    inspect_status,
    is_installed,
    presence_status,
    tool_status,
)
from installer.updates import UNKNOWN_UPDATE, UpdateRunner, UpdateStatus


def test_presence_status_resolves_only_presence_and_marks_deep_checks_pending() -> None:
    tool = _tool("demo")
    resolved: list[str] = []

    status = presence_status(
        tool,
        executable_resolver=lambda cmd: resolved.append(cmd) or Path("/fixture/bin/demo"),
    )

    assert resolved == ["demo"]
    assert status == ToolStatus(
        tool=tool,
        installed=True,
        ownership=PENDING_OWNERSHIP,
        health=UNKNOWN_HEALTH,
        update=UNKNOWN_UPDATE,
    )


def test_presence_status_counts_an_app_bundle_without_running_a_command(tmp_path: Path) -> None:
    (tmp_path / "Demo.app").mkdir()
    resolved: list[str] = []

    status = presence_status(
        _app_tool(),
        app_roots=(tmp_path,),
        executable_resolver=lambda cmd: resolved.append(cmd) or None,
    )

    assert resolved == ["demo"]
    assert status.installed is True
    assert status.ownership == PENDING_OWNERSHIP
    assert status.health == UNKNOWN_HEALTH


def test_refresh_context_probes_each_argv_once_across_concurrent_inspectors() -> None:
    started = Event()
    release = Event()
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        started.set()
        assert release.wait(timeout=5), "test did not release probe"
        return "fixture stdout"

    context = RefreshContext(
        platform=Platform("macos", "arm64", False, True),
        probe=probe,
        health_runner=lambda _argv: CommandResult(0, "", ""),
        update_runner=lambda _argv: CommandResult(0, "", ""),
        executable_resolver=lambda _cmd: None,
        app_roots=(),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(context.probe_once, ("brew", "list"))
        assert started.wait(timeout=5)
        second = executor.submit(context.probe_once, ("brew", "list"))
        release.set()

    assert first.result() == "fixture stdout"
    assert second.result() == "fixture stdout"
    assert calls == [["brew", "list"]]
    assert tuple(context.cache) == (("brew", "list"),)


def test_inspect_status_uses_context_and_only_discovers_requested_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import installer.status as status_module

    tool = _tool("demo")
    deep_status = ToolStatus(
        tool,
        True,
        Ownership("Homebrew", "verified", "fixture", "brew", "demo"),
    )
    available = UpdateStatus("available", "1.1", "fixture")
    app_roots = (Path("/fixture/Applications"),)
    health_runner: HealthRunner = lambda _argv: CommandResult(0, "", "")
    update_runner: UpdateRunner = lambda _argv: CommandResult(0, "", "")
    executable_resolver: ExecutableResolver = lambda _cmd: Path("/fixture/bin/demo")
    deep_calls: list[str] = []
    update_calls: list[str] = []

    def fake_tool_status(
        value: Tool,
        probe: ProbeRunner,
        app_roots: tuple[Path, ...] | None,
        health_runner: HealthRunner,
        executable_resolver: ExecutableResolver,
    ) -> ToolStatus:
        assert value is tool
        assert probe == context.probe_once
        assert app_roots == context.app_roots
        assert health_runner is context.health_runner
        assert executable_resolver is context.executable_resolver
        deep_calls.append(value.id)
        return deep_status

    def fake_inspect_update(
        value: Tool,
        owner: Ownership,
        runner: UpdateRunner,
    ) -> UpdateStatus:
        assert value is tool
        assert owner is deep_status.ownership
        assert runner is context.update_runner
        update_calls.append(value.id)
        return available

    monkeypatch.setattr(status_module, "tool_status", fake_tool_status)
    monkeypatch.setattr(status_module, "inspect_update", fake_inspect_update)
    context = RefreshContext(
        platform=Platform("macos", "arm64", False, True),
        probe=lambda _argv: "fixture stdout",
        health_runner=health_runner,
        update_runner=update_runner,
        executable_resolver=executable_resolver,
        app_roots=app_roots,
    )

    without_updates = inspect_status(tool, False, context)
    with_updates = inspect_status(tool, True, context)

    assert without_updates is deep_status
    assert with_updates == ToolStatus(
        tool,
        True,
        deep_status.ownership,
        deep_status.health,
        available,
    )
    assert deep_calls == ["demo", "demo"]
    assert update_calls == ["demo"]
```

- [ ] **Step 2: Run the focused status tests and verify the red state**

Run: `uv run pytest tests/test_status.py -k 'presence_status or refresh_context or inspect_status' -v`

Expected: FAIL during collection with `ImportError` for `PENDING_OWNERSHIP`, `RefreshContext`, `presence_status`, or `inspect_status` from `installer.status`.

- [ ] **Step 3: Implement the minimal context, presence constructor, and public inspector**

In `installer/status.py`, replace `from dataclasses import dataclass` with the `dataclasses` import below, add the other new imports, place the constant and context after `ToolStatus`, place `presence_status` before `tool_status`, and place public `inspect_status` after `tool_status`:

```python
from concurrent.futures import Future
from dataclasses import dataclass, field, replace
from threading import Lock

from installer.platform import Platform
from installer.updates import UNKNOWN_UPDATE, UpdateRunner, UpdateStatus, inspect_update


PENDING_OWNERSHIP = Ownership(None, "unknown", "ownership pending")


@dataclass
class RefreshContext:
    """Dependencies and stdout probes shared by one refresh generation."""

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
            except Exception as exc:
                future.set_exception(exc)
        return future.result()


def presence_status(
    tool: Tool,
    app_roots: tuple[Path, ...] | None = None,
    executable_resolver: ExecutableResolver = resolve_executable,
) -> ToolStatus:
    """Inspect local presence without running health, ownership, or update probes."""
    executable = executable_resolver(tool.cmd)
    installed = executable is not None or _app_bundle_installed(tool, app_roots)
    return ToolStatus(
        tool=tool,
        installed=installed,
        ownership=PENDING_OWNERSHIP,
        health=UNKNOWN_HEALTH,
        update=UNKNOWN_UPDATE,
    )
```

Keep the existing `tool_status` implementation and add this public adapter immediately after it:

```python
def inspect_status(
    tool: Tool,
    include_updates: bool,
    context: RefreshContext,
) -> ToolStatus:
    """Inspect one tool with dependencies owned by one refresh generation."""
    status = tool_status(
        tool,
        lambda argv: context.probe_once(tuple(argv)),
        app_roots=context.app_roots,
        health_runner=context.health_runner,
        executable_resolver=context.executable_resolver,
    )
    if not include_updates:
        return status
    return replace(
        status,
        update=inspect_update(
            status.tool,
            status.ownership,
            context.update_runner,
        ),
    )
```

Do not implement this in terms of `is_installed`: `presence_status` must use the injected resolver exactly once, and `is_installed` uses the real resolver.

- [ ] **Step 4: Run the focused status tests and verify the green state**

Run: `uv run pytest tests/test_status.py -k 'presence_status or refresh_context or inspect_status or resolves_the_executable_once' -v`

Expected: PASS. The presence tests call only the injected resolver, one context coalesces concurrent identical stdout probes into one underlying call, the public inspector forwards the context's probe, health runner, resolver, and app roots into `tool_status`, update replacement occurs only when requested, and the existing deep-status test still resolves once for presence, health, and ownership.

- [ ] **Step 5: Write the failing composition test for immediate construction**

In `tests/test_setup.py`, replace the existing `IsolatedBuildApp` protocol with this final declaration:

```python
class IsolatedBuildApp(Protocol):
    resolver_calls: list[str]
    deep_inspections: list[str]

    def __call__(
        self,
        tools: list[Tool],
        platform: Platform,
        *,
        enable_install: bool = True,
        probe: ProbeRunner | None = None,
        update_runner: UpdateRunner | None = None,
        executable_resolver: ExecutableResolver | None = None,
    ) -> UnifiedApp: ...
```

Add `UNKNOWN_HEALTH` to the existing import from `installer.health` before adding the composition assertion below.

Inside `isolated_build_app`, replace the resolver that always fails, record deep inspections in `fake_tool_status`, replace the final `build` closure with a typed callable object, and return that object:

```python
    resolver_calls: list[str] = []
    deep_inspections: list[str] = []

    def presence_resolver(cmd: str) -> Path | None:
        resolver_calls.append(cmd)
        return None

    def fake_tool_status(
        tool: Tool,
        probe: ProbeRunner,
        *,
        app_roots: tuple[Path, ...] | None = None,
        health_runner: HealthRunner,
        executable_resolver: ExecutableResolver,
    ) -> ToolStatus:
        assert callable(probe)
        assert app_roots is None
        assert health_runner is fail_health
        assert callable(executable_resolver)
        deep_inspections.append(tool.id)
        return ToolStatus(
            tool,
            False,
            Ownership(None, "unknown", "not installed", None, None, None),
            Health("missing", None, "command not found on PATH"),
            UNKNOWN_UPDATE,
        )

    class _IsolatedBuildApp:
        def __init__(self) -> None:
            self.resolver_calls = resolver_calls
            self.deep_inspections = deep_inspections

        def __call__(
            self,
            tools: list[Tool],
            platform: Platform,
            *,
            enable_install: bool = True,
            probe: ProbeRunner | None = None,
            update_runner: UpdateRunner | None = None,
            executable_resolver: ExecutableResolver | None = None,
        ) -> UnifiedApp:
            build_app = cast(Callable[..., UnifiedApp], vars(setup)["_build_app"])
            return build_app(
                tools,
                platform,
                enable_install=enable_install,
                probe=fail_probe if probe is None else probe,
                health_runner=fail_health,
                executable_resolver=presence_resolver
                if executable_resolver is None
                else executable_resolver,
                update_runner=fail_update if update_runner is None else update_runner,
            )

    monkeypatch.setattr(setup, "tool_status", fake_tool_status)
    return _IsolatedBuildApp()
```

Remove the fixture's old `monkeypatch.setattr(setup, "tool_status", fake_tool_status)` and `return build` lines because the complete replacement above owns both operations. Then add this test:

```python
def test_build_app_constructs_from_presence_without_deep_status_work(
    isolated_build_app: IsolatedBuildApp,
) -> None:
    tool = _tool("fd")

    app = isolated_build_app([tool], _platform(), enable_install=False)

    assert isolated_build_app.resolver_calls == ["fd"]
    assert isolated_build_app.deep_inspections == []
    assert app.catalog.status_for("fd") == ToolStatus(
        tool,
        False,
        Ownership(None, "unknown", "ownership pending"),
        UNKNOWN_HEALTH,
        UNKNOWN_UPDATE,
    )
```

- [ ] **Step 6: Run the composition test and verify the red state**

Run: `uv run pytest tests/test_setup.py::test_build_app_constructs_from_presence_without_deep_status_work -v`

Expected: FAIL because `_build_app` still invokes `tool_status` for every tool before constructing `UnifiedApp`; `deep_inspections` is `['fd']`.

- [ ] **Step 7: Wire the immutable initial map in `setup.py`**

Add the imports:

```python
from types import MappingProxyType

from installer.status import ToolStatus, presence_status, tool_status
```

Keep the existing deep `status_factory` unchanged for this task. Replace only its eager invocation at the start of `_build_app`:

```python
    statuses: Mapping[str, ToolStatus] = MappingProxyType(
        {
            tool.id: presence_status(tool, executable_resolver=executable_resolver)
            for tool in tools
        }
    )
    installed = {tool_id: status.installed for tool_id, status in statuses.items()}
```

Pass this `statuses` mapping to `classify_tools` and `UnifiedApp` exactly as before. `CatalogScreen` copies it into its private dictionary, so later atomic complete-map replacement remains possible. Do not move decision logic into `setup.py`; the only new decision is the tested `presence_status` function in `installer/status.py`.

- [ ] **Step 8: Run Task 1's focused tests**

Before running the tests, update the two existing setup composition expectations that intentionally depended on eager deep inspection:

```python
# test_reinstall_plan_includes_selected_present_broken_tools_in_dependency_order
app = isolated_build_app(
    [dependent, dependency],
    _platform(),
    executable_resolver=lambda cmd: Path(f"/fixture/bin/{cmd}"),
)
```

The injected resolver makes both tools present in the initial snapshot; the test's `present_broken` deep inspector remains available to startup enrichment, but plan construction no longer calls it eagerly.

At the end of `test_build_app_composes_expanded_plan_and_injected_executor`, replace the eager-ownership assertions with the new boundary assertions:

```python
    assert app_statuses is not None
    assert app_statuses["rg"].ownership.detail == "ownership pending"
    assert classified_statuses is app_statuses
    assert status_probes == [fake_probe, fake_probe]
```

The two `status_probes` calls come from the still-existing whole-catalog execution preflight in this intermediate task. Task 3 removes those final calls. Do not preserve the old expectation that initial construction provides verified ownership.

Run: `uv run pytest tests/test_status.py tests/test_setup.py -k 'presence or inspect_status or build_app_constructs' -v`

Expected: PASS. `_build_app` resolves local presence once per tool, returns without health or ownership inspection, the Catalog starts with pending deep status, and the public inspector retains context-bound deep and optional-update behavior.

- [ ] **Step 9: Run the full quality gate**

Run: `make validate && make test`

Expected: PASS. Ruff formatting and lint, Pyright strict mode, Bandit, Vulture, ShellCheck, all tests, and coverage at or above 90% succeed.

- [ ] **Step 10: Commit the presence-only snapshot**

```bash
git add installer/status.py setup.py tests/test_status.py tests/test_setup.py
git commit -m "feat(status): mount from a presence-only snapshot" \
  -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 2: Own Bounded Status Generations In `UnifiedApp`

**Files:**
- Create: `installer/status_coordinator.py`
- Create: `tests/test_status_coordinator.py`
- Modify: `installer/wizard_app.py:15-56, 623-705, 756-807`
- Modify: `setup.py:10-18, 144-180, 266-319`
- Modify: `tests/test_wizard_app.py:1-165, 346-370, 619-652, 687-699`
- Modify: `tests/test_setup.py:666-723, 838-1038`
- Modify: `tests/test_catalog_tui.py:19-44`
- Modify: `tests/test_uninstall_e2e.py:50-120`
- Modify: `tests/test_policies_e2e.py:37-128`

**Interfaces:**
- Consumes: Task 1's complete initial `Mapping[str, ToolStatus]` and public `installer.status.inspect_status(tool, include_updates, context) -> ToolStatus`.
- Consumes: Task 1's `RefreshContext` with the current stdout-only `ProbeRunner` and refresh-local `Future[str]` cache.
- Produces: the `StatusKind`, `StatusInspector = Callable[[Tool, bool, RefreshContext], ToolStatus]`, `RefreshContextFactory`, `StatusRequest`, `StatusProgress`, `StatusResult`, and `StatusCoordinator` signatures in Final Interfaces.
- Replaces: `UnifiedApp.refresh_statuses: Callable[[bool], Mapping[str, ToolStatus]]` and synchronous `refresh_catalog(...)` with `inspect_status: StatusInspector`, `refresh_context: RefreshContextFactory`, and `request_status_refresh(kind) -> int`.
- Behavior: `StatusCoordinator.refresh` calls its context factory exactly once before submitting any per-tool future, then passes that same context to every inspector in the generation.
- Behavior: startup and post-install requests pass `include_updates=False`; explicit requests pass `include_updates=True`.
- Behavior: a refresh failure or stale generation never calls `CatalogScreen.refresh_statuses`.
- Behavior: successful replacement occurs once, after every tool returns, on Textual's thread.
- Behavior: post-install refresh starts only after `InstallScreen._finish` has set `finished=True` and restored completion actions.

- [ ] **Step 1: Write the failing coordinator unit tests**

Create `tests/test_status_coordinator.py`:

```python
from threading import Event, Lock

from installer.health import CommandResult
from installer.model import Method, Tool
from installer.ownership import Ownership
from installer.platform import Platform
from installer.status import RefreshContext, ToolStatus
from installer.status_coordinator import StatusCoordinator, StatusResult


def _tool(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="fixture",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
    )


def _status(tool: Tool) -> ToolStatus:
    return ToolStatus(tool, True, Ownership(None, "unknown", "fixture"))


def _context() -> RefreshContext:
    return RefreshContext(
        platform=Platform("macos", "arm64", False, True),
        probe=lambda _argv: "",
        health_runner=lambda _argv: CommandResult(0, "", ""),
        update_runner=lambda _argv: CommandResult(0, "", ""),
        executable_resolver=lambda _cmd: None,
        app_roots=(),
    )


def test_refresh_bounds_concurrency_and_reports_completed_counts() -> None:
    tools = [_tool(str(index)) for index in range(5)]
    release = Event()
    saturated = Event()
    lock = Lock()
    active = 0
    maximum_active = 0
    created_contexts: list[RefreshContext] = []
    observed_contexts: list[RefreshContext] = []

    def new_context() -> RefreshContext:
        context = _context()
        created_contexts.append(context)
        return context

    def inspect(
        tool: Tool,
        include_updates: bool,
        context: RefreshContext,
    ) -> ToolStatus:
        nonlocal active, maximum_active
        assert include_updates is False
        with lock:
            observed_contexts.append(context)
            active += 1
            maximum_active = max(maximum_active, active)
            if active == 2:
                saturated.set()
        assert release.wait(timeout=5), "test did not release status inspection"
        with lock:
            active -= 1
        return _status(tool)

    coordinator = StatusCoordinator(tools, inspect, new_context, max_workers=2)
    request = coordinator.request("startup")
    progress: list[tuple[int, int]] = []
    finished = Event()
    results: list[StatusResult] = []

    from threading import Thread

    def run_refresh() -> None:
        results.append(
            coordinator.refresh(
                request,
                lambda value: progress.append((value.completed, value.total)),
            )
        )
        finished.set()

    thread = Thread(target=run_refresh)
    try:
        thread.start()
        assert saturated.wait(timeout=5)
        assert maximum_active == 2
        release.set()
        assert finished.wait(timeout=5)
        result = results[0]
        assert result.generation == request.generation
        assert set(result.statuses) == {tool.id for tool in tools}
        assert progress == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
        assert len(created_contexts) == 1
        assert all(context is created_contexts[0] for context in observed_contexts)
    finally:
        release.set()
        thread.join(timeout=5)
        coordinator.close()


def test_new_request_advances_the_current_generation_and_sets_update_policy() -> None:
    tool = _tool("fd")
    coordinator = StatusCoordinator(
        [tool],
        lambda value, _updates, _context: _status(value),
        _context,
    )
    try:
        startup = coordinator.request("startup")
        explicit = coordinator.request("explicit")

        assert startup.include_updates is False
        assert explicit.include_updates is True
        assert explicit.generation == startup.generation + 1
        assert coordinator.is_current(startup.generation) is False
        assert coordinator.is_current(explicit.generation) is True
    finally:
        coordinator.close()
```

- [ ] **Step 2: Run the coordinator tests and verify the red state**

Run: `uv run pytest tests/test_status_coordinator.py -v`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'installer.status_coordinator'`.

- [ ] **Step 3: Implement the Textual-independent coordinator**

Create `installer/status_coordinator.py`:

```python
"""Bounded, generation-aware background construction of complete status maps."""

from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from typing import Literal, TypeAlias

from installer.model import Tool
from installer.status import RefreshContext, ToolStatus

StatusKind = Literal["startup", "explicit", "post-install"]
StatusInspector: TypeAlias = Callable[[Tool, bool, RefreshContext], ToolStatus]
RefreshContextFactory: TypeAlias = Callable[[], RefreshContext]


@dataclass(frozen=True)
class StatusRequest:
    generation: int
    kind: StatusKind
    include_updates: bool


@dataclass(frozen=True)
class StatusProgress:
    generation: int
    kind: StatusKind
    completed: int
    total: int


@dataclass(frozen=True)
class StatusResult:
    generation: int
    statuses: Mapping[str, ToolStatus]


class StatusCoordinator:
    """Own one bounded executor and issue monotonically increasing refreshes."""

    def __init__(
        self,
        tools: list[Tool],
        inspect_status: StatusInspector,
        refresh_context: RefreshContextFactory,
        max_workers: int = 4,
    ) -> None:
        if max_workers < 1:
            raise ValueError("status max_workers must be at least one")
        self._tools = tuple(tools)
        self._inspect_status = inspect_status
        self._refresh_context = refresh_context
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="catalog-status",
        )
        self._lock = Lock()
        self._generation = 0

    def request(self, kind: StatusKind) -> StatusRequest:
        with self._lock:
            self._generation += 1
            generation = self._generation
        return StatusRequest(generation, kind, kind == "explicit")

    def refresh(
        self,
        request: StatusRequest,
        progress: Callable[[StatusProgress], None],
    ) -> StatusResult:
        context = self._refresh_context()
        futures: dict[Future[ToolStatus], Tool] = {
            self._executor.submit(
                self._inspect_status,
                tool,
                request.include_updates,
                context,
            ): tool
            for tool in self._tools
        }
        statuses: dict[str, ToolStatus] = {}
        total = len(futures)
        try:
            for completed, future in enumerate(as_completed(futures), start=1):
                tool = futures[future]
                statuses[tool.id] = future.result()
                progress(
                    StatusProgress(
                        request.generation,
                        request.kind,
                        completed,
                        total,
                    )
                )
        except Exception:
            for future in futures:
                future.cancel()
            raise
        return StatusResult(request.generation, MappingProxyType(statuses))

    def is_current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
```

The shared executor bounds aggregate concurrency across overlapping generations. Do not create an executor per refresh and do not submit work through Textual's event-loop worker. Each call to `refresh` creates exactly one context before its comprehension submits futures; all tools in that generation share it, while overlapping generations receive distinct contexts and caches. A superseded generation may finish already-running calls, but its progress and result will be discarded by `UnifiedApp`.

- [ ] **Step 4: Run the coordinator tests and verify the green state**

Run: `uv run pytest tests/test_status_coordinator.py -v`

Expected: PASS. At most two inspectors run at once, progress reaches `5/5`, one context is created before submission and shared by all five inspectors, explicit requests alone include updates, and generation IDs increase.

- [ ] **Step 5: Write failing app tests for mount, navigation, progress, stale results, failure preservation, and post-install completion**

Update the `_app` helper in `tests/test_wizard_app.py` to accept the new inspector and refresh-context seams:

```python
from installer.health import CommandResult, Health
from installer.platform import Platform
from installer.status import RefreshContext, ToolStatus
from installer.status_coordinator import RefreshContextFactory, StatusInspector


def _refresh_context() -> RefreshContext:
    return RefreshContext(
        platform=Platform("macos", "arm64", False, True),
        probe=lambda _argv: "",
        health_runner=lambda _argv: CommandResult(0, "", ""),
        update_runner=lambda _argv: CommandResult(0, "", ""),
        executable_resolver=lambda _cmd: None,
        app_roots=(),
    )


def _app(
    *,
    tools: list[Tool] | None = None,
    statuses: Mapping[str, ToolStatus] | None = None,
    inspect_status: StatusInspector | None = None,
    refresh_context: RefreshContextFactory = _refresh_context,
    status_workers: int = 4,
    report: DoctorReport | None = None,
    guard_status: dict[str, bool] | None = None,
    guard_warning: str | None = None,
    fix_preview: str = "Will wire ~/.local/bin into ~/.zshrc",
    fix: Callable[[], None] = lambda: None,
    uninstall: UninstallInputs | None = None,
    policies: PolicyInputs | None = None,
    initial_view: str = "catalog",
    start_install: StartInstall | None = None,
    build_plan: BuildPlan | None = None,
) -> UnifiedApp:
    tools = [_tool("rg"), _tool("fd")] if tools is None else tools
    catalog_statuses = _statuses_for(tools) if statuses is None else statuses
    if start_install is not None and build_plan is None:
        def build_selected_plan(ids: list[str], mode: ExecutionMode = "install") -> InstallPlan:
            return replace(_plan_for(tools, ids), execution_mode=mode)

        build_plan = build_selected_plan
    inspector = inspect_status or (
        lambda tool, _include_updates, _context: catalog_statuses[tool.id]
    )
    return UnifiedApp(
        tools,
        catalog_statuses,
        {"search": "find things"},
        report=report or DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status or {"pip": False, "npm": False},
        guard_warning=guard_warning,
        fix_preview=fix_preview,
        fix=fix,
        uninstall=uninstall or _uninstall_inputs(),
        policies=policies or _policy_inputs(),
        inspect_status=inspector,
        refresh_context=refresh_context,
        status_workers=status_workers,
        initial_view=initial_view,
        start_install=start_install,
        build_plan=build_plan,
    )
```

Add `StartInstall` and `BuildPlan` to the existing imports from `installer.wizard_app`. Then add:

```python
async def test_startup_status_work_mounts_first_and_keeps_number_keys_responsive() -> None:
    started = Event()
    release = Event()

    def inspect(
        tool: Tool,
        include_updates: bool,
        _context: RefreshContext,
    ) -> ToolStatus:
        assert include_updates is False
        started.set()
        assert release.wait(timeout=5), "test did not release startup inspection"
        return ToolStatus(tool, True, Ownership(None, "unknown", "enriched"))

    app = _app(inspect_status=inspect, status_workers=1)
    try:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert started.is_set()
            assert app.current_view == "catalog"
            assert "Checking tool status 0/2..." in app.catalog.status_text
            await pilot.press("2", "3", "4", "1")
            assert app.current_view == "catalog"
            release.set()
            await pilot.pause()
    finally:
        release.set()


async def test_new_explicit_generation_prevents_stale_startup_overwrite() -> None:
    startup_started = Event()
    explicit_started = Event()
    release_startup = Event()
    release_explicit = Event()
    tool = _tool("fd")
    initial = ToolStatus(tool, False, Ownership(None, "unknown", "pending"))
    created_contexts: list[RefreshContext] = []

    def new_context() -> RefreshContext:
        context = _refresh_context()
        created_contexts.append(context)
        return context

    def inspect(
        value: Tool,
        include_updates: bool,
        _context: RefreshContext,
    ) -> ToolStatus:
        if include_updates:
            explicit_started.set()
            assert release_explicit.wait(timeout=5), "test did not release explicit refresh"
            return replace(initial, installed=True)
        startup_started.set()
        assert release_startup.wait(timeout=5), "test did not release startup refresh"
        return initial

    app = _app(
        tools=[tool],
        statuses={"fd": initial},
        inspect_status=inspect,
        refresh_context=new_context,
        status_workers=2,
    )
    try:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert startup_started.is_set()
            await pilot.press("ctrl+f")
            await pilot.pause()
            assert explicit_started.is_set()
            assert len(created_contexts) == 2
            assert created_contexts[0] is not created_contexts[1]
            assert "Refreshing ownership and updates 0/1..." in app.catalog.status_text
            release_explicit.set()
            await pilot.pause()
            assert app.catalog.status_for("fd").installed is True
            release_startup.set()
            await pilot.pause()
            assert app.catalog.status_for("fd").installed is True
    finally:
        release_explicit.set()
        release_startup.set()


async def test_refresh_failure_keeps_the_previous_complete_map() -> None:
    tool = _tool("fd")
    previous = ToolStatus(tool, True, Ownership(None, "unknown", "previous"))

    def inspect(
        value: Tool,
        include_updates: bool,
        _context: RefreshContext,
    ) -> ToolStatus:
        if include_updates:
            raise RuntimeError("fixture probe failed")
        return previous

    app = _app(tools=[tool], statuses={"fd": previous}, inspect_status=inspect)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+f")
        await pilot.pause()
        assert app.catalog.status_for("fd") is previous
        assert app.catalog.status_text == "Status refresh failed: fixture probe failed"


async def test_install_finishes_and_navigation_restores_before_post_refresh() -> None:
    post_started = Event()
    release_post = Event()
    inspections = 0

    def inspect(
        tool: Tool,
        include_updates: bool,
        _context: RefreshContext,
    ) -> ToolStatus:
        nonlocal inspections
        assert include_updates is False
        inspections += 1
        if inspections > 2:
            post_started.set()
            assert release_post.wait(timeout=5), "test did not release post-install refresh"
        return ToolStatus(tool, True, Ownership(None, "unknown", "refreshed"))

    def start_install(
        plan: InstallPlan,
        _statuses: Mapping[str, ToolStatus],
        _choices: ExecutionChoices,
        emit: Callable[[ExecutionEvent], None],
    ) -> Summary:
        for tool in plan.ordered:
            emit(ExecutionEvent(tool.id, "installed", f"{tool.id}: installed"))
        return _summary(*plan.selected_ids)

    app = _app(inspect_status=inspect, start_install=start_install)
    try:
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("space", "enter", "enter")
            await pilot.pause()
            assert isinstance(app.screen, InstallScreen)
            assert app.screen.finished is True
            assert post_started.is_set()
            assert "Install complete; refreshing catalog..." in app.screen.status.text
            await pilot.press("2")
            assert app.current_view == "doctor"
            release_post.set()
            await pilot.pause()
    finally:
        release_post.set()
```

The post-refresh test has two catalog tools, so startup consumes two inspector calls and the first post-install call sets `post_started`. If task execution changes the fixture catalog size, replace the numeric condition with a locked refresh-round counter; do not use sleeps.

- [ ] **Step 6: Run the app tests and verify the red state**

Run: `uv run pytest tests/test_wizard_app.py -k 'startup_status_work or stale_startup or refresh_failure_keeps or finishes_and_navigation' -v`

Expected: FAIL because the baseline `UnifiedApp` constructor rejects the new inspector, context-factory, and worker-limit keywords; startup does not schedule background work, explicit refresh blocks synchronously, and post-install completion calls the synchronous refresh before input resumes.

- [ ] **Step 7: Integrate the coordinator into `UnifiedApp`**

Add these imports to `installer/wizard_app.py`:

```python
from installer.status_coordinator import (
    RefreshContextFactory,
    StatusCoordinator,
    StatusInspector,
    StatusKind,
    StatusProgress,
    StatusRequest,
    StatusResult,
)
```

Replace the `refresh_statuses` constructor parameter and field with:

```python
        inspect_status: StatusInspector,
        refresh_context: RefreshContextFactory,
        status_workers: int = 4,
```

```python
        self._status_coordinator = StatusCoordinator(
            tools,
            inspect_status,
            refresh_context,
            max_workers=status_workers,
        )
```

At the end of `on_mount`, after the initial view or initial Install preview has mounted, schedule startup enrichment:

```python
        self.request_status_refresh("startup")

    def on_unmount(self) -> None:
        self._status_coordinator.close()
```

Delete the synchronous `refresh_catalog`. Add these complete methods in its place:

```python
    def request_status_refresh(self, kind: StatusKind) -> int:
        request = self._status_coordinator.request(kind)
        self._show_status_progress(
            StatusProgress(request.generation, request.kind, 0, len(self._catalog.tools))
        )
        self.run_worker(
            lambda: self._run_status_refresh(request),
            thread=True,
            exclusive=False,
        )
        return request.generation

    def _run_status_refresh(self, request: StatusRequest) -> None:
        try:
            result = self._status_coordinator.refresh(
                request,
                lambda value: self.call_from_thread(self._show_status_progress, value),
            )
        except Exception as exc:
            detail = str(exc) or type(exc).__name__
            self.call_from_thread(self._status_refresh_failed, request, detail)
            return
        self.call_from_thread(self._apply_status_result, request, result)

    @staticmethod
    def _status_progress_text(progress: StatusProgress) -> str:
        if progress.kind == "startup":
            return f"Checking tool status {progress.completed}/{progress.total}..."
        if progress.kind == "explicit":
            return (
                "Refreshing ownership and updates "
                f"{progress.completed}/{progress.total}..."
            )
        return (
            "Install complete; refreshing catalog... "
            f"({progress.completed}/{progress.total})"
        )

    def _show_status_progress(self, progress: StatusProgress) -> None:
        if not self._status_coordinator.is_current(progress.generation):
            return
        text = self._status_progress_text(progress)
        self._catalog.status.set(text, "warn")
        if progress.kind == "post-install":
            install = self._views["install"]
            if isinstance(install, InstallScreen):
                install.status.set(text, "warn")

    def _apply_status_result(
        self,
        request: StatusRequest,
        result: StatusResult,
    ) -> None:
        if (
            result.generation != request.generation
            or not self._status_coordinator.is_current(request.generation)
        ):
            return
        self._catalog.refresh_statuses(result.statuses)
        self._catalog.status.clear()
        if request.kind == "post-install":
            install = self._views["install"]
            if isinstance(install, InstallScreen):
                install.status.set("Install complete; catalog refreshed.", "ok")

    def _status_refresh_failed(self, request: StatusRequest, detail: str) -> None:
        if not self._status_coordinator.is_current(request.generation):
            return
        text = f"Status refresh failed: {detail}"
        self._catalog.status.set(text, "error")
        if request.kind == "post-install":
            install = self._views["install"]
            if isinstance(install, InstallScreen):
                install.status.set(text, "error")
```

Replace the explicit handler body:

```python
    async def on_catalog_screen_refresh_requested(
        self, message: CatalogScreen.RefreshRequested
    ) -> None:
        message.stop()
        self.request_status_refresh("explicit")
```

Replace `_finish_catalog_operation` so completion state and existing selection cleanup happen before refresh scheduling:

```python
    def _finish_catalog_operation(self, summary: Summary) -> None:
        self._catalog.discard_selected(set(summary.installed) | set(summary.already))
        self.request_status_refresh("post-install")
```

`InstallScreen._finish` already sets `summary`, `finished=True`, and completion footer actions before invoking `_on_complete`; preserve that ordering. Do not change selection rules in this plan.

- [ ] **Step 8: Inject the public inspector and bind the refresh-context factory in `setup.py`**

Use these final production imports, removing `tool_status` and `inspect_update` from `setup.py`:

```python
from installer.status import RefreshContext, ToolStatus, inspect_status, presence_status
from installer.updates import UpdateRunner, run_update_check
```

Replace `status_factory(include_updates)` with only the refresh-context factory. Do not define a local `inspect_status`; `setup.py` must inject the imported public function directly:

```python
    def new_refresh_context() -> RefreshContext:
        return RefreshContext(
            platform=platform,
            probe=probe,
            health_runner=health_runner,
            update_runner=update_runner,
            executable_resolver=executable_resolver,
        )
```

The public `installer.status.inspect_status` function owns the adapter behavior: `context.probe_once` deliberately has the current `ProbeRunner = Callable[[list[str]], str]` signature and is passed directly to `tool_status` with the context's health runner, executable resolver, and app roots. The context cache stores `Future[str]` by `tuple(argv)` only for this generation. The function replaces `ToolStatus.update` only when `include_updates` is true. Do not introduce structured command results, ownership refresh protocols, receipts, or manager-specific inventory types here.

In `tests/test_setup.py`, add these imports:

```python
import installer.status as status_module
from installer.status_coordinator import StatusInspector
```

After Task 2 removes `setup.py`'s `tool_status` import, change every setup composition monkeypatch from `monkeypatch.setattr(setup, "tool_status", fake_tool_status)` to `monkeypatch.setattr(status_module, "tool_status", fake_tool_status)`. This keeps each test's deep-status seam below the public inspector while allowing `setup.py` to inject the real `inspect_status` function object. Update every such `fake_tool_status` or equivalent test double to accept `app_roots: tuple[Path, ...] | None = None` in addition to `health_runner` and `executable_resolver`, because the public adapter forwards all three context fields. Likewise, patch update discovery with `monkeypatch.setattr(status_module, "inspect_update", fake_inspect_update)` because `inspect_update` is no longer imported by `setup.py`.

In `test_build_app_composes_expanded_plan_and_injected_executor`, capture the injected inspector in `fake_unified_app` and assert direct injection:

```python
    inspect_status_seen: StatusInspector | None = None

    def fake_unified_app(
        *args: object,
        inspect_status: StatusInspector,
        start_install: StartInstall | None = None,
        build_plan: BuildPlan | None = None,
        **_kwargs: object,
    ) -> _DummyApp:
        nonlocal app_statuses, build_plan_callback, inspect_status_seen
        nonlocal start_install_callback
        app_statuses = cast(dict[str, ToolStatus], args[1])
        inspect_status_seen = inspect_status
        build_plan_callback = build_plan
        start_install_callback = start_install
        return app
```

Add `StartInstall` and `BuildPlan` to the existing `installer.wizard_app` import in this test module. Immediately after the existing `isolated_build_app(tools, _platform(), probe=fake_probe)` call, add `assert inspect_status_seen is setup.inspect_status`. The identity assertion prevents a nested wrapper or duplicate inspector from returning to `setup.py`.

In `test_build_app_composes_expanded_plan_and_injected_executor`, replace Task 1's intermediate raw-probe assertion with the context-bound assertion that is correct for this task:

```python
    assert len(status_probes) == 2
    first_context = cast(RefreshContext, getattr(status_probes[0], "__self__"))
    second_context = cast(RefreshContext, getattr(status_probes[1], "__self__"))
    assert first_context is second_context
    assert first_context.probe is fake_probe
```

The two preflight inspections share one `RefreshContext`, and their current stdout probe delegates to the injected `fake_probe`. Task 3 removes both inspections and changes this assertion to `status_probes == []`.

For this task only, preserve the current whole-catalog execution preflight by rewriting its old `status_factory(False)` call as a comprehension. Task 3 removes it under a dedicated failing test:

```python
        if plan.execution_mode == "update":
            execution_statuses = operation_statuses
        else:
            execution_context = new_refresh_context()
            execution_statuses = {
                tool.id: inspect_status(tool, False, execution_context)
                for tool in tools
            }
```

This intermediate execution preflight shares one context, but it is not a coordinator refresh generation and must not be retained. Task 3 deletes the whole branch. In the existing `UnifiedApp` call, replace `refresh_statuses=status_factory` with these exact arguments:

```python
        inspect_status=inspect_status,
        refresh_context=new_refresh_context,
```

The first argument is the imported `installer.status.inspect_status` object, not a nested function.

- [ ] **Step 9: Update every direct `UnifiedApp` test constructor**

Reuse Step 5's `_refresh_context` in `tests/test_wizard_app.py`. Add `CommandResult`, `Platform`, and `RefreshContext` imports where absent, then add this complete inert factory to each of `tests/test_catalog_tui.py`, `tests/test_uninstall_e2e.py`, and `tests/test_policies_e2e.py` (if a file already defines `_LINUX`, use `platform=_LINUX` instead of constructing the shown platform):

```python
def _refresh_context() -> RefreshContext:
    return RefreshContext(
        platform=Platform("macos", "arm64", False, True),
        probe=lambda _argv: "",
        health_runner=lambda _argv: CommandResult(0, "", ""),
        update_runner=lambda _argv: CommandResult(0, "", ""),
        executable_resolver=lambda _cmd: None,
        app_roots=(),
    )
```

Use these final adapters at all seven direct test construction sites (Step 8 covers the eighth `UnifiedApp` construction in production `setup.py`):

```python
        inspect_status=lambda tool, _include_updates, _context: catalog_statuses[tool.id],
        refresh_context=_refresh_context,
```

Where the local mapping is named `statuses`, use `statuses[tool.id]`. Delete every `refresh_statuses=` argument. In existing refresh assertions, accept the third `context: RefreshContext` argument, record `(tool.id, include_updates)`, and call `ctrl+f` through the pilot; do not call a synchronous app refresh method because it no longer exists.

Delete `test_refresh_request_and_completion_use_the_public_refresh_seam`; the new explicit-generation and post-install-blocking tests replace its removed synchronous seam with stronger behavior assertions.

In `test_completed_install_refreshes_catalog_and_discards_completed_selection`, replace the old map factory with this per-tool inspector and clear startup observations before starting the operation:

```python
    refreshes: list[tuple[str, bool]] = []

    def inspect(
        tool: Tool,
        include_updates: bool,
        _context: RefreshContext,
    ) -> ToolStatus:
        refreshes.append((tool.id, include_updates))
        return refreshed[tool.id]

    app = _app(
        statuses=statuses,
        inspect_status=inspect,
        start_install=start_install,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        refreshes.clear()
        await pilot.press("space", "enter")
        install = app.screen
        assert isinstance(install, InstallScreen)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("fd", "inst").plain == "✓ owner unknown"
        assert app.catalog.selected == set()
        assert set(refreshes) == {("rg", False), ("fd", False)}
        assert [plan.selected_ids for plan in calls] == [("fd",)]
```

This is an observation-only adaptation of the existing selection assertion; do not change which selections are discarded.

In `tests/test_setup.py`, rewrite `test_public_catalog_refresh_skips_update_queries_until_requested` as:

```python
async def test_background_status_skips_update_queries_until_explicit_refresh(
    monkeypatch: pytest.MonkeyPatch,
    isolated_build_app: IsolatedBuildApp,
) -> None:
    update_calls: list[str] = []

    def injected_update_runner(_argv: list[str]) -> CommandResult:
        pytest.fail("update runner must not execute during startup enrichment")

    def fake_inspect_update(
        tool: Tool,
        _owner: Ownership,
        runner: UpdateRunner,
    ) -> UpdateStatus:
        assert runner is injected_update_runner
        update_calls.append(tool.id)
        return UNKNOWN_UPDATE

    monkeypatch.setattr(status_module, "inspect_update", fake_inspect_update)
    app = isolated_build_app(
        [_tool("fd")],
        _platform(),
        enable_install=False,
        update_runner=injected_update_runner,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        assert update_calls == []
        await pilot.press("ctrl+f")
        await pilot.pause()
    assert update_calls == ["fd"]
```

- [ ] **Step 10: Run Task 2's focused tests**

Run: `uv run pytest tests/test_status_coordinator.py tests/test_wizard_app.py tests/test_setup.py tests/test_catalog_tui.py tests/test_uninstall_e2e.py tests/test_policies_e2e.py -k 'status or refresh or navigation or catalog' -v`

Expected: PASS. Textual mounts before blocked startup inspection, `1-4` navigation works during the block, count progress is visible, explicit generations include updates, stale startup results do not overwrite explicit results, failures retain the prior map, and successful Install completion restores navigation before post-refresh returns.

- [ ] **Step 11: Run the full quality gate**

Run: `make validate && make test`

Expected: PASS. Pyright accepts public `installer.status.inspect_status` as `StatusInspector = Callable[[Tool, bool, RefreshContext], ToolStatus]`, `RefreshContext.probe_once` as the current stdout `ProbeRunner`, every factory as `Callable[[], RefreshContext]`, and all thread-boundary types; `setup.py` injects that public function directly, no executor or helper is dead code, all tests pass, and coverage remains at least 90%.

- [ ] **Step 12: Commit the background coordinator**

```bash
git add installer/status_coordinator.py installer/wizard_app.py setup.py \
  tests/test_status_coordinator.py tests/test_wizard_app.py tests/test_setup.py \
  tests/test_catalog_tui.py tests/test_uninstall_e2e.py tests/test_policies_e2e.py
git commit -m "feat(status): coordinate background catalog refreshes" \
  -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 3: Prepare Only The Captured Install Plan

**Files:**
- Modify: `setup.py:266-291`
- Modify: `installer/install_screen.py:169-198, 355-376, 397-420`
- Modify: `tests/test_setup.py:694-723, 838-1038`
- Modify: `tests/test_install_screen.py:29-105`

**Interfaces:**
- Consumes: existing `StartInstall(plan, operation_statuses, choices, emit) -> Summary` and `run_plan(..., statuses=...)` contracts.
- Produces: no new public Python type.
- Behavior: `_start_install` passes `operation_statuses` to `run_plan` for install, reinstall, and update.
- Behavior: the operation map contains exactly `plan.ordered` because `_open_install` captures it from the current Catalog map.
- Behavior: `engine.install_tool` retains its existing per-planned-tool `is_installed(tool)` recheck; this task does not remove that fresh execution guard.
- Behavior: `InstallScreen.status.text` is `Preparing selected tools...` before the execution closure runs and changes to `Installing selected tools...` on the first `installing` event.

- [ ] **Step 1: Write the failing single-tool preflight composition test**

Replace `test_start_install_passes_the_prepared_mode_and_fresh_statuses` in `tests/test_setup.py` with:

```python
async def test_single_tool_install_uses_captured_status_without_catalog_preflight(
    monkeypatch: pytest.MonkeyPatch,
    isolated_build_app: IsolatedBuildApp,
) -> None:
    received: dict[str, object] = {}
    inspected: list[str] = []
    inspected_at_execution: tuple[str, ...] | None = None
    tools = [_tool("fd"), _tool("rg")]

    def fake_tool_status(
        tool: Tool,
        _probe: ProbeRunner,
        *,
        app_roots: tuple[Path, ...] | None = None,
        health_runner: HealthRunner,
        executable_resolver: ExecutableResolver,
    ) -> ToolStatus:
        assert app_roots is None
        assert callable(health_runner)
        assert callable(executable_resolver)
        inspected.append(tool.id)
        return _status_for(tool.id)

    def fake_run_plan(
        plan: InstallPlan,
        _platform: Platform,
        _emit: Callable[[ExecutionEvent], None],
        **kwargs: object,
    ) -> Summary:
        nonlocal inspected_at_execution
        inspected_at_execution = tuple(inspected)
        received.update(plan=plan, **kwargs)
        return Summary(("fd",), (), (), ())

    monkeypatch.setattr(status_module, "tool_status", fake_tool_status)
    monkeypatch.setattr(setup, "run_plan", fake_run_plan)
    app = isolated_build_app(tools, _platform())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert set(inspected) == {"fd", "rg"}
        inspected.clear()
        await pilot.press("space", "enter", "enter")
        await pilot.pause()

    plan = cast(InstallPlan, received["plan"])
    statuses = cast(Mapping[str, ToolStatus], received["statuses"])
    assert plan.selected_ids == ("fd",)
    assert set(statuses) == {"fd"}
    assert inspected_at_execution == ()
```

Startup enrichment may complete in either tool order, so assert the set before clearing it. `inspected_at_execution == ()` is the regression assertion: approving one tool must reach `run_plan` without calling the public `inspect_status` path, and therefore without calling its internal `tool_status`, for either the selected tool or the rest of the catalog. The expected asynchronous post-install refresh may inspect the catalog after `run_plan` returns. `engine.install_tool` performs the selected tool's local presence recheck when the real `run_plan` is used.

- [ ] **Step 2: Run the composition test and verify the red state**

Run: `uv run pytest tests/test_setup.py::test_single_tool_install_uses_captured_status_without_catalog_preflight -v`

Expected: FAIL at `assert inspected_at_execution == ()`; `_start_install` calls the Task 2 comprehension for both `fd` and `rg` before `run_plan`, so the captured value is `('fd', 'rg')` in catalog order.

- [ ] **Step 3: Delete the whole-catalog execution preflight**

Replace `_start_install` in `setup.py` with this complete body:

```python
    def _start_install(
        plan: InstallPlan,
        operation_statuses: Mapping[str, ToolStatus],
        choices: ExecutionChoices,
        emit: Callable[[ExecutionEvent], None],
    ) -> Summary:
        def _track(event: ExecutionEvent) -> None:
            if event.state in {"installed", "already-installed"}:
                completed.add(event.tool_id)
            emit(event)

        return run_plan(
            plan,
            platform,
            _track,
            statuses=operation_statuses,
            on_mismatch=choices.on_mismatch,
            approved_actions=choices.approved_actions,
            skipped_actions=choices.skipped_actions,
            captured_runner=run_captured_command,
            interactive_runner=_run_interactive_action,
        )
```

Do not add a selected-tool `tool_status` loop here. `operation_statuses` is the operation snapshot captured in `UnifiedApp._open_install`; `run_plan` already requires that it cover every planned tool, and the real install engine rechecks local presence only for each tool it executes.

In `test_build_app_composes_expanded_plan_and_injected_executor`, change the final status-probe assertion from Task 1's intermediate two calls to the final expectation:

```python
    assert status_probes == []
```

The composition root now injects public `installer.status.inspect_status` directly; that function is the only route from app-owned background inspection to `tool_status`. This test replaces `UnifiedApp` with a dummy, so no background generation starts and no deep status probe is expected.

- [ ] **Step 4: Run the composition test and verify the green state**

Run: `uv run pytest tests/test_setup.py::test_single_tool_install_uses_captured_status_without_catalog_preflight tests/test_setup.py::test_update_uses_the_available_status_captured_from_the_catalog -v`

Expected: PASS. Normal install and update both receive exactly the planned tools' captured statuses, and approval does not invoke deep status inspection.

- [ ] **Step 5: Write the failing visible-preparation test**

Add `Event` to `tests/test_install_screen.py` imports and add:

```python
async def test_screen_shows_preparation_before_blocked_execution() -> None:
    from installer.install_screen import InstallScreen

    started = Event()
    release = Event()
    plan = InstallPlan(("uv",), (_tool("uv"),), (), ())

    class _BlockedApp(App[None]):
        def __init__(self) -> None:
            super().__init__()
            self.install = InstallScreen(plan, self._start)

        def _start(
            self,
            _choices: ExecutionChoices,
            emit: Callable[[ExecutionEvent], None],
        ) -> Summary:
            started.set()
            assert release.wait(timeout=5), "test did not release install execution"
            emit(ExecutionEvent("uv", "installed", "uv: installed"))
            return Summary(("uv",), (), (), ())

        def on_mount(self) -> None:
            self.push_screen(self.install)

    app = _BlockedApp()
    try:
        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.pause()
            assert started.is_set()
            assert app.install.started is True
            assert app.install.finished is False
            assert app.install.status.text == "Preparing selected tools..."
            release.set()
            await pilot.pause()
    finally:
        release.set()
```

- [ ] **Step 6: Run the preparation test and verify the red state**

Run: `uv run pytest tests/test_install_screen.py::test_screen_shows_preparation_before_blocked_execution -v`

Expected: FAIL because `_begin_execution` starts the worker without writing a preparation message; `InstallScreen.status.text` is empty.

- [ ] **Step 7: Render preparation before starting the worker**

In `InstallScreen.prepare`, clear a previous operation's status after resetting state:

```python
        if self.is_mounted:
            self.status.clear()
            self._render_plan()
```

Replace `_begin_execution` with:

```python
    def _begin_execution(
        self,
        approved: set[ActionKey],
        skipped: set[ActionKey],
    ) -> None:
        self.approved_actions = frozenset(approved)
        self.skipped_actions = frozenset(skipped)
        self.started = True
        self.status.set("Preparing selected tools...", "warn")
        self.query_one(FooterBar).set_actions("install in progress")
        self.run_worker(self._execute, thread=True, exclusive=True)
```

At the start of `_apply_event`, update the phase before changing the row:

```python
    def _apply_event(self, event: ExecutionEvent) -> None:
        if event.tool_id not in self.rows:
            return
        if event.state == "installing":
            self.status.set("Installing selected tools...", "warn")
        self.rows[event.tool_id] = event.state
        table = cast(DataTable[Any], self.query_one("#install-rows", DataTable))
        if event.method is not None:
            table.update_cell(event.tool_id, "method", event.method)
        table.update_cell(event.tool_id, "state", event.state)
        self.output_text += f"{event.text}\n"
        self.query_one("#install-output", RichLog).write(event.text)
```

Keep the current event stream and table rendering. Do not add a fake preparation row or a new execution state.

- [ ] **Step 8: Run Task 3's focused tests**

Run: `uv run pytest tests/test_setup.py tests/test_install_screen.py tests/test_wizard_app.py -k 'single_tool_install or captured_status or preparation or execution' -v`

Expected: PASS. A blocked worker leaves visible preparation text, existing per-tool events still render, and a one-tool operation triggers no catalog-wide deep inspection.

- [ ] **Step 9: Run the full quality gate**

Run: `make validate && make test`

Expected: PASS. Every existing install, reinstall, update, retry, checksum, and post-install action test remains green, with coverage at or above 90%.

- [ ] **Step 10: Commit focused install preparation**

```bash
git add setup.py installer/install_screen.py tests/test_setup.py tests/test_install_screen.py
git commit -m "fix(install): prepare only captured plan statuses" \
  -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 4: Finish Unexpected Install Worker Exceptions

**Files:**
- Modify: `installer/install_screen.py:119-150, 169-198, 366-420`
- Modify: `installer/wizard_app.py` in `_show_status_progress`, `_apply_status_result`, and `_status_refresh_failed`
- Modify: `tests/test_install_screen.py:29-117`
- Modify: `tests/test_wizard_app.py` near install completion tests

**Interfaces:**
- Consumes: existing `Summary` buckets and `ExecutionState` values.
- Produces: `InstallScreen.error: str | None`, initialized and reset to `None` by `__init__` and `prepare`.
- Behavior: `_execute` catches `Exception`, not `BaseException`, and schedules failure handling on Textual's thread.
- Behavior: rows still in `queued` or `installing` become `failed`; existing terminal rows retain their states and matching summary buckets.
- Behavior: `_finish` receives the synthesized `Summary`, sets `finished=True`, restores completion navigation, and invokes completion once.
- Behavior: post-install catalog refresh may run after an unexpected install failure, but its progress or result must not overwrite the visible installation error on `InstallScreen.status`.

- [ ] **Step 1: Write the failing worker-exception test**

Add this test to `tests/test_install_screen.py`:

```python
async def test_unexpected_worker_exception_finishes_with_failed_summary() -> None:
    from installer.install_screen import InstallScreen

    completed: list[Summary] = []
    plan = InstallPlan(("uv",), (_tool("uv"),), (), ())

    def fail(
        _choices: ExecutionChoices,
        emit: Callable[[ExecutionEvent], None],
    ) -> Summary:
        emit(ExecutionEvent("uv", "installing", "uv: started", method="script"))
        raise RuntimeError("fixture executor crashed")

    class _FailureApp(App[None]):
        def __init__(self) -> None:
            super().__init__()
            self.install = InstallScreen(plan, fail, on_complete=completed.append)

        def on_mount(self) -> None:
            self.push_screen(self.install)

    app = _FailureApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert app.install.started is True
        assert app.install.finished is True
        assert app.install.error == "fixture executor crashed"
        assert app.install.rows == {"uv": "failed"}
        assert app.install.summary == Summary((), (), ("uv",), ())
        assert app.install.status.text == "Installation failed: fixture executor crashed"
        assert completed == [Summary((), (), ("uv",), ())]
```

Add this app-level regression test to `tests/test_wizard_app.py`:

```python
async def test_worker_exception_restores_app_navigation_and_keeps_error_visible() -> None:
    def fail_install(
        _plan: InstallPlan,
        _statuses: Mapping[str, ToolStatus],
        _choices: ExecutionChoices,
        _emit: Callable[[ExecutionEvent], None],
    ) -> Summary:
        raise RuntimeError("fixture executor crashed")

    app = _app(start_install=fail_install)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space", "enter", "enter")
        await pilot.pause()
        assert isinstance(app.screen, InstallScreen)
        assert app.screen.finished is True
        assert app.screen.status.text == "Installation failed: fixture executor crashed"
        await pilot.press("2")
        assert app.current_view == "doctor"
```

- [ ] **Step 2: Run the exception tests and verify the red state**

Run: `uv run pytest tests/test_install_screen.py::test_unexpected_worker_exception_finishes_with_failed_summary tests/test_wizard_app.py::test_worker_exception_restores_app_navigation_and_keeps_error_visible -v`

Expected: FAIL. The background worker raises through Textual, `finished` remains false, the row remains `installing` or `queued`, no summary reaches completion, and navigation remains disabled.

- [ ] **Step 3: Add one terminal exception boundary in `InstallScreen`**

In `InstallScreen.__init__`, initialize:

```python
        self.error: str | None = None
```

In `prepare`, reset it with the other operation state:

```python
        self.error = None
```

Replace `_execute` and add `_finish_worker_failure` immediately after it:

```python
    def _execute(self) -> None:
        start = self._start
        if start is None:
            return
        choices = ExecutionChoices(
            approved_actions=self.approved_actions,
            skipped_actions=self.skipped_actions,
            on_mismatch=self._ask_mismatch_from_worker,
        )
        try:
            summary = start(choices, self._emit_from_worker)
        except Exception as exc:
            detail = str(exc) or type(exc).__name__
            self.app.call_from_thread(self._finish_worker_failure, detail)
            return
        self.app.call_from_thread(self._finish, summary)

    def _finish_worker_failure(self, detail: str) -> None:
        for tool_id, state in tuple(self.rows.items()):
            if state in {"queued", "installing"}:
                self._apply_event(
                    ExecutionEvent(
                        tool_id,
                        "failed",
                        f"{tool_id}: failed - {detail}",
                    )
                )
        self.error = detail
        self.status.set(f"Installation failed: {detail}", "error")
        summary = Summary(
            installed=tuple(
                tool_id for tool_id, state in self.rows.items() if state == "installed"
            ),
            already=tuple(
                tool_id
                for tool_id, state in self.rows.items()
                if state == "already-installed"
            ),
            failed=tuple(
                tool_id for tool_id, state in self.rows.items() if state == "failed"
            ),
            no_method=tuple(
                tool_id for tool_id, state in self.rows.items() if state == "no-method"
            ),
            mismatched=tuple(
                tool_id
                for tool_id, state in self.rows.items()
                if state == "checksum-mismatch"
            ),
            manual_required=tuple(
                tool_id
                for tool_id, state in self.rows.items()
                if state == "manual-required"
            ),
            skipped=tuple(
                tool_id for tool_id, state in self.rows.items() if state == "skipped"
            ),
            cancelled=tuple(
                tool_id for tool_id, state in self.rows.items() if state == "cancelled"
            ),
        )
        self._finish(summary)
```

Use ASCII `-` in the emitted worker-failure line, as shown. Existing source strings contain Unicode punctuation, but new code defaults to ASCII. Keep `_finish`'s current idempotence guard and ordering.

- [ ] **Step 4: Keep post-refresh status from hiding an install error**

In each of `UnifiedApp._show_status_progress`, `_apply_status_result`, and `_status_refresh_failed`, change the post-install `InstallScreen` write guard to the same condition:

```python
            if isinstance(install, InstallScreen) and install.error is None:
                install.status.set(text, "warn")
```

Use the method's existing text and severity for each site: `warn` for progress, `ok` with `"Install complete; catalog refreshed."` for success, and `error` for refresh failure. The full success branch is:

```python
        if request.kind == "post-install":
            install = self._views["install"]
            if isinstance(install, InstallScreen) and install.error is None:
                install.status.set("Install complete; catalog refreshed.", "ok")
```

This guard preserves `Installation failed: <detail>` while the Catalog still receives its asynchronous refresh and any refresh diagnostic.

- [ ] **Step 5: Run the focused exception and completion tests**

Run: `uv run pytest tests/test_install_screen.py tests/test_wizard_app.py -k 'worker_exception or unexpected_worker or completion or post_refresh' -v`

Expected: PASS. Unexpected exceptions finish once, all nonterminal rows become failed, `Summary.failed` is populated, navigation works, and background refresh cannot replace the visible install error.

- [ ] **Step 6: Run the complete scoped regression set**

Run: `uv run pytest tests/test_status.py tests/test_status_coordinator.py tests/test_catalog_tui.py tests/test_install_screen.py tests/test_wizard_app.py tests/test_setup.py tests/test_uninstall_e2e.py tests/test_policies_e2e.py -v`

Expected: PASS. This covers presence-only startup, all status generations, Catalog rendering, install preparation and completion, exception handling, and unaffected neighboring views.

- [ ] **Step 7: Run the full quality gate**

Run: `make validate && make test`

Expected: PASS. Every validation hook and test succeeds on the exact tree to be committed, and coverage remains at least 90%.

- [ ] **Step 8: Commit install worker hardening**

```bash
git add installer/install_screen.py installer/wizard_app.py \
  tests/test_install_screen.py tests/test_wizard_app.py
git commit -m "fix(install): finish unexpected worker failures" \
  -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Completion Checklist

- [ ] Confirm `git diff --check` exits 0 with no whitespace errors.
- [ ] Confirm `git status --short` lists only the files named in this plan plus this plan file.
- [ ] Confirm `make validate && make test` passes after the final implementation commit.
- [ ] Confirm no code or test mentions receipts, SDKMAN, registry classification, install dispositions, ownership adapter redesign, or new selection lifecycle behavior.
- [ ] Confirm `installer/status.py` retains the pre-Plan-2 `ProbeRunner = Callable[[list[str]], str]` contract, `RefreshContext.cache` stores `Future[str]`, and no structured ownership refresh/result types appear.
- [ ] Confirm public `installer.status.inspect_status(tool, include_updates, context) -> ToolStatus` passes `context.probe_once`, `context.health_runner`, `context.executable_resolver`, and `context.app_roots` to `tool_status`, and replaces only `update` when `include_updates` is true.
- [ ] Confirm `rg 'Callable\[\[Tool, bool\], ToolStatus\]|inspect_status=lambda [^,]+, [^,]+:' installer tests setup.py` returns no matches; every status inspector accepts `(tool, include_updates, context)`.
- [ ] Confirm `setup.py` imports `installer.status.inspect_status`, passes it directly as `inspect_status=inspect_status`, and contains no nested `def inspect_status`.
- [ ] Confirm every production and test `UnifiedApp(...)` construction supplies both `inspect_status=` and `refresh_context=`.
- [ ] Confirm `StatusCoordinator.refresh` calls `_refresh_context()` once before its first `submit` and passes that one object to every per-tool future in the generation.
- [ ] Confirm no `tool_status` whole-catalog comprehension remains in `_start_install`.
- [ ] Confirm only explicit refresh passes `include_updates=True`.
- [ ] Confirm every complete status-map replacement remains inside `UnifiedApp._apply_status_result` on Textual's thread.
- [ ] Confirm the plan file itself remains uncommitted unless the implementing user explicitly requests a documentation commit.
