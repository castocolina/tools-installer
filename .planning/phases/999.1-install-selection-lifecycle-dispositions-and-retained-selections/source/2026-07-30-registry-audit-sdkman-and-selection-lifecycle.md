# Registry Audit, SDKMAN, and Selection Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the 69-tool, 198-method semantic audit; plan against method-specific prerequisites and the current Catalog snapshot; install JVM candidates only through SDKMAN; show every direct selection; and retain only selections that still need action.

**Architecture:** Extend each declarative method with its audited scope, manager, prerequisite, package, update, and uninstall semantics, then select a method before expanding its prerequisites. Represent the Install review as immutable entries with explicit dispositions while retaining one ordered executable subset. Consume Plan 1's current Catalog map, refresh context, and public refresh API plus Plan 2's structured ownership values; implement SDKMAN candidate ownership in this plan without redesigning either predecessor system.

**Tech Stack:** Python 3.11, TOML, Textual, Rich, pytest, Ruff, Pyright, uv.

## Global Constraints

- `contextual` is displayed as **ecosystem-specific**. It never means project-local installation and never creates a dependency.
- Recommendation and installation scope remain independent.
- Installation scope is exactly one of `user`, `system`, `manager`, or `project-wrapper`.
- Dependencies belong to the method that requires them unless every method shares the prerequisite.
- Select an applicable method before expanding prerequisites. Prune prerequisites when their selected parent is unavailable or blocked.
- SDKMAN is the exclusive catalog manager for Java, Gradle, Maven, Groovy, and Spring Boot CLI. Remove their native and Homebrew fallbacks.
- Project guidance recommends `./gradlew` and `./mvnw`; the Catalog still offers explicit ecosystem-specific global SDKMAN candidates.
- Every direct selection appears in Install as `will install`, `already installed`, `unavailable`, or `blocked`.
- Every dragged dependency names its dependent. No dependency row appears without a reason.
- Opening and cancelling an unapproved preview preserves the staged selection.
- Clear successful and already-satisfied direct selections. Retain failed, skipped, cancelled, unavailable, and blocked direct selections.
- Dragged dependencies never independently add or remove Catalog selection.
- Planning uses the current Catalog status snapshot. Delete the separate mutable `completed` snapshot.
- Normal install and reinstall use Plan 1's captured executable-entry statuses; the engine retains its per-executed-tool local presence guard and never deep-scans the complete catalog.
- All subprocess behavior is injected or monkeypatched. Tests never run live package-manager mutations.
- All filesystem state in tests uses `tmp_path`. Tests never inspect or mutate the real home directory.
- Manager output is escaped before Rich markup rendering.
- Keep `setup.py` wiring-only. Put decisions in `installer/`.
- Do not add `# noqa`, `# type: ignore`, `# pyright: ignore`, `# nosec`, skipped tests, lowered coverage, or quality-tool configuration changes.
- Use `uv`; never use `pip`, Poetry, Conda, or an ad hoc virtual environment.
- Every commit step is an execution-time instruction. Do not commit while authoring this plan.

## Declared Predecessor Contracts

Plan 1, `docs/superpowers/plans/2026-07-30-responsive-status-and-install-progress.md`, must land first and supplies these exact public contracts. This plan consumes them and must not reimplement status threading, generation handling, progress, failure preservation, bounded concurrency, preparation copy, or worker-exception handling.

```python
# installer/status_coordinator.py, supplied by Plan 1
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from installer.model import Tool
from installer.status import RefreshContext, ToolStatus

StatusKind = Literal["startup", "explicit", "post-install"]
StatusInspector = Callable[[Tool, bool, RefreshContext], ToolStatus]
RefreshContextFactory = Callable[[], RefreshContext]


@dataclass(frozen=True)
class StatusRequest:
    generation: int
    kind: StatusKind
    include_updates: bool


class StatusCoordinator:
    def __init__(
        self,
        tools: list[Tool],
        inspect_status: StatusInspector,
        refresh_context: RefreshContextFactory,
        *,
        max_workers: int = 4,
    ) -> None: ...

    def request(self, kind: StatusKind) -> StatusRequest: ...

    def is_current(self, generation: int) -> bool: ...
```

- `UnifiedApp` owns the coordinator and receives both `inspect_status: StatusInspector` and `refresh_context: RefreshContextFactory`; this plan does not inject or replace the coordinator.
- `StatusCoordinator.refresh` creates one context from the factory for each generation and passes that same context to every `inspect_status(tool, include_updates, context)` call in the generation.
- `UnifiedApp.request_status_refresh(kind: StatusKind) -> int` is Plan 1's only public refresh seam. This plan calls `request_status_refresh("post-install")` after selection cleanup.
- `CatalogScreen.status_for(tool_id: str) -> ToolStatus` exposes the complete map Plan 1 installed atomically. Task 7 adds only a read-only `status_snapshot() -> Mapping[str, ToolStatus]` projection so one generation drives the whole plan.
- Plan 1's `_open_install` already captures `operation_statuses` from Catalog for planned tools. Task 7 changes the builder signature so the same captured complete map drives method planning, then retains Plan 1's exact planned-tool capture.
- Plan 1 already emits `Preparing selected tools...` before invoking `StartInstall` and sends the captured planned-tool map directly to `run_plan`; this plan adds no preparation scan or coordinator API.

Plan 2, `docs/superpowers/plans/2026-07-30-ownership-adapters-and-installer-receipts.md`, must also land first and supplies these exact public values. It reserves the SDKMAN manager and update-mechanism literals but intentionally does not implement SDKMAN candidate ownership. This plan consumes the shared model and probe cache without duplicating Plan 2's existing manager adapters, receipt logic, origin inference, or update authorization rules.

```python
# installer/ownership.py, supplied by Plan 2
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from installer.health import CommandResult
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
```

- Plan 2 defines `ResolvedExecutable`, `ArtifactOwner`, `UpdateAuthorization`, `Ownership`, `OwnershipRefresh`, the reserved SDKMAN literals, and shared `probe_once` inventory caching.
- Task 5 in this plan produces `detect_sdkman_candidate_owner(candidate, executable, context) -> Ownership` and routes SDKMAN methods through it. The function uses `context.probe_once` for bounded SDKMAN candidate inventory and current-link queries. It never treats ordinary PATH presence as ownership.
- Successful evidence is exactly `Ownership("verified", executable, ArtifactOwner("SDKMAN", candidate, "sdkman"), "sdkman-candidate", UpdateAuthorization("sdkman", candidate, "sdkman"), detail)`.
- Unknown, malformed, unavailable, timeout, and package-mismatch outcomes retain Plan 2's structured `OwnershipOutcome` and return no update authorization.
- Task 6 defines `VerifyMethodOwnership = Callable[[Tool, Method], Ownership]` as an engine injection type. `setup.py` binds it to Task 5's `detect_sdkman_candidate_owner`, Plan 2's injected `ExecutableResolver`, and a fresh context from Plan 1's `RefreshContextFactory`.
- Task 1 mechanically changes Plan 2's package lookup from `method.params.get("ownership_package")` to `method.ownership_package`. This is required because this plan promotes package identity into typed method metadata; adapter behavior stays unchanged.
- Do not create a second ownership model, cache, or update authorization path. The SDKMAN adapter added here must use Plan 2's values and `OwnershipRefresh.probe_once`.

---

## File Map

- `installer/model.py`: owns recommendation rationale and closed method-semantic values parsed from TOML.
- `installer/registry.toml`: remains the single registry; carries every audited tool and method classification.
- `installer/resolve.py`: separates platform applicability from manager presence and selects one preferred method.
- `installer/deps.py`: expands only the selected method's prerequisites and returns complete review dispositions.
- `installer/install_plan.py`: owns `PlanEntry`, `PlanDisposition`, and immutable review/execution projections.
- `installer/app.py`: builds install/update/reinstall plans from a supplied current status map.
- `installer/executors.py`: builds the fixed non-interactive SDKMAN candidate invocation.
- `installer/ownership.py`: retains Plan 2's model and adapters, adds SDKMAN candidate inventory/current-link ownership, and uses the shared refresh cache.
- `installer/engine.py`: executes the planned method and requires verified SDKMAN candidate ownership.
- `installer/session.py`: seeds non-executable dispositions, executes only `will-install` entries, and returns every terminal outcome.
- `installer/catalog_tui.py`: explains ecosystem-specific recommendations and displays the preferred manager/scope.
- `installer/install_screen.py`: renders all direct selections plus reasoned dependencies and their dispositions.
- `installer/wizard_app.py`: captures Plan 1's current snapshot, preserves cancelled previews, clears resolved direct selections, and requests post-install refresh.
- `setup.py`: wires platform, coordinator, plan builder, SDKMAN verifier, and execution closure only.
- `README.md`: documents 69 tools, recommendation semantics, method-aware dependencies, SDKMAN, Install dispositions, and selection retention.
- `tests/test_model.py`, `tests/test_registry.py`: lock the semantic schema and complete audit.
- `tests/test_resolve.py`, `tests/test_deps.py`, `tests/test_install_plan.py`, `tests/test_app.py`: cover method selection, dependency pruning, dispositions, and snapshot-driven plans.
- `tests/test_executors.py`, `tests/test_ownership.py`, `tests/test_engine.py`, `tests/test_session.py`: cover the SDKMAN command, candidate ownership probes, post-install verification, selected-method execution, and summaries.
- `tests/test_catalog_tui.py`, `tests/test_install_screen.py`, `tests/test_wizard_app.py`, `tests/test_setup.py`: cover copy, preview completeness, selection lifecycle, and predecessor wiring.
- `tests/test_catalog_sdkman_e2e.py`: runs the final headless sandboxed journey.

## Audit Vocabulary

Every final `[[tool.method]]` declares these keys explicitly:

```toml
scope = "user"                 # user | system | manager | project-wrapper
manager = "tools-installer"   # non-empty reviewed manager/orchestrator id
requires = []                  # tool ids needed by this method only
install_package = "none"      # exact package/candidate id, or literal sentinel "none"
ownership_package = "none"    # exact evidence id, or literal sentinel "none"
update = "reinstall"          # manager | reinstall | unsupported
uninstall = "installer"       # installer | manager | manual | unsupported
```

The audit uses these complete profiles:

| Code | Kind | Scope | Manager | Method prerequisites | Install / ownership package | Update | Uninstall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `S` | `script` | `user` | `vendor-installer` | none | `none` / `none` | `reinstall` | `manual` |
| `R` | `github_release` | `user` | `tools-installer` | none | `none` / `none` | `reinstall` | `installer` |
| `A` | `app` | `user` | `tools-installer` | none | `none` / `none` | `reinstall` | `installer` |
| `D(p)` | `dnf` | `system` | `dnf` | none | `p` / `p` | `manager` | `manager` |
| `T(p)` | `apt` | `system` | `apt` | none | `p` / `p` | `manager` | `manager` |
| `P(p)` | `pacman` | `system` | `pacman` | none | `p` / `p` | `manager` | `manager` |
| `B(p)` | `brew` | `manager` | `Homebrew` | `brew` | `p` / `p` | `manager` | `manager` |
| `C(p)` | `cask` | `manager` | `Homebrew` | `brew` | `p` / `p` | `manager` | `manager` |
| `N(p)` | `node` | `manager` | `pnpm` | `pnpm` | `p` / `p` | `manager` | `manager` |
| `H(p)` | `host_setup` | `manager` | `pnpm` | `pnpm` | `p` / `p` | `manager` | `manager` |
| `K(p)` | `sdkman` | `manager` | `SDKMAN` | `sdkman` plus `java` for non-Java candidates | `p` / `p` | `manager` | `manager` |

`R-linux`, `R-macos`, and architecture suffixes below identify separate method records with the same `R` semantics. The same rule applies to `A-*` and `S-*` variants.

## Complete Registry Audit Matrix

This matrix accounts for all 69 current tools and all 198 current methods. Rows marked `replace` classify the current method before replacing it in Task 6. The final registry contains 186 methods: `198 - 17 replaced methods + 5 K methods`.

| Tool | Recommendation and exact rationale | Version check | Current 198-method disposition and final semantic profiles |
| --- | --- | --- | --- |
| `uv` | `core`: standard Python environment and package workflow | yes | `S`, `B(uv)` |
| `rg` | `core`: primary fast recursive code search | yes | `R-linux`, `R-macos`, `D(ripgrep)`, `T(ripgrep)`, `P(ripgrep)`, `B(ripgrep)` |
| `jq` | `core`: standard structured JSON query tool | yes | `D(jq)`, `T(jq)`, `P(jq)`, `B(jq)` |
| `brew` | `optional`: useful package source when native or user-space artifacts are unavailable | yes | `S-macos`, `S-linux` |
| `fd` | `core`: primary ergonomic file finder | yes | `R-linux`, `R-macos`, `B(fd)` |
| `bat` | `core`: primary syntax-aware file viewer | yes | `R-linux`, `R-macos`, `B(bat)` |
| `sd` | `optional`: ergonomic literal text replacement | yes | `R-linux`, `R-macos`, `B(sd)` |
| `git` | `core`: required version-control foundation | yes | `D(git)`, `T(git)`, `P(git)`, `B(git)` |
| `delta` | `core`: readable syntax-aware Git diffs | yes | `R-linux`, `R-macos`, `B(git-delta)` |
| `eza` | `core`: readable Git-aware directory listings | yes | `R-linux`, `B(eza)` |
| `zoxide` | `optional`: learned directory navigation | yes | `R-linux`, `R-macos`, `B(zoxide)` |
| `fzf` | `optional`: fuzzy selection for interactive shell workflows | yes | `R-linux`, `R-macos`, `B(fzf)` |
| `lazygit` | `optional`: full-screen Git workflow UI | yes | `R-linux`, `R-macos`, `B(lazygit)` |
| `gh` | `core`: standard GitHub command-line workflow | yes | `R-linux`, `B(gh)` |
| `glab` | `core`: standard GitLab command-line workflow for GitLab users | yes | `B(glab)` |
| `yq` | `core`: standard YAML query and transformation tool | yes | `R-linux`, `R-macos`, `B(yq)` |
| `zsh` | `optional`: alternative interactive shell | yes | `D(zsh)`, `T(zsh)`, `P(zsh)`, `B(zsh)` |
| `starship` | `optional`: cross-shell prompt customization | yes | `R-linux`, `R-macos`, `B(starship)` |
| `direnv` | `optional`: directory-scoped environment loading | yes | `R-linux`, `R-macos`, `B(direnv)` |
| `just` | `optional`: repository command recipes | yes | `R-linux`, `R-macos`, `B(just)` |
| `ruff` | `core`: standard fast Python lint and format workflow | yes | `R-linux`, `R-macos`, `B(ruff)`; remove false tool-level `uv` prerequisite |
| `dust` | `optional`: visual disk-usage inspection | yes | `R-linux`, `R-macos`, `B(dust)` |
| `hyperfine` | `optional`: repeatable command benchmarking | yes | `R-linux`, `R-macos`, `B(hyperfine)` |
| `bottom` | `optional`: interactive process and resource monitor | yes | `R-linux`, `R-macos`, `B(bottom)` |
| `gum` | `optional`: shell-script interaction widgets | yes | `R-linux`, `R-macos`, `B(gum)` |
| `glow` | `optional`: terminal Markdown rendering | yes | `R-linux`, `R-macos`, `B(glow)` |
| `xh` | `contextual`: HTTP work is ecosystem-specific | yes | `R-linux`, `R-macos`, `B(xh)` |
| `difftastic` | `core`: structural diffs improve code review | yes | `R-linux`, `R-macos`, `B(difftastic)` |
| `gitui` | `optional`: alternative full-screen Git UI | yes | `R-linux`, `B(gitui)` |
| `lazydocker` | `optional`: full-screen container workflow UI | yes | `R-linux`, `R-macos`, `B(lazydocker)` |
| `docker` | `contextual`: Docker development is ecosystem-specific | yes | change `D(docker)` to `D(moby-engine)`; keep `T(docker.io)`, `P(docker)`, `B(docker)` |
| `podman` | `contextual`: Podman development is ecosystem-specific | yes | `D(podman)`, `T(podman)`, `P(podman)`, `B(podman)` |
| `colima` | `contextual`: local container VM management is ecosystem-specific | yes | `B(colima)` |
| `dive` | `optional`: container image layer inspection | yes | `R-linux`, `R-macos`, `B(dive)` |
| `duf` | `optional`: readable filesystem-space summary | yes | `R-linux`, `R-macos`, `B(duf)` |
| `hexyl` | `optional`: hexadecimal terminal viewing | yes | `R-linux`, `R-macos`, `B(hexyl)` |
| `miller` | `optional`: tabular data transformation | yes | `R-linux`, `R-macos`, `B(miller)` |
| `shfmt` | `core`: standard shell formatting | yes | `R-linux`, `R-macos`, `B(shfmt)` |
| `tealdeer` | `optional`: concise command examples | yes | `R-linux`, `R-macos`, `B(tealdeer)` |
| `fx` | `optional`: interactive JSON exploration | yes | `R-linux`, `R-macos`, `B(fx)` |
| `dasel` | `optional`: multi-format data selection | yes | `R-linux`, `R-macos`, `B(dasel)` |
| `gron` | `optional`: flatten JSON for line-oriented inspection | yes | `R-linux`, `R-macos`, `B(gron)` |
| `aichat` | `optional`: additional terminal AI client | yes | `R-linux`, `R-macos`, `B(aichat)` |
| `codex` | `optional`: OpenAI coding workflow is provider-specific | yes | `S`, `C(codex)` |
| `claude` | `optional`: Anthropic coding workflow is provider-specific | yes | `S`, `C(claude-code)` |
| `opencode` | `optional`: OpenCode is an alternative coding-agent workflow | yes | `S`, `N(opencode-ai)`, `P(opencode)`, `B(anomalyco/tap/opencode)`; only `N` requires `pnpm` |
| `deno` | `contextual`: Deno projects form a distinct runtime ecosystem | yes | `R-linux`, `R-macos`, `B(deno)` |
| `sdkman` | `contextual`: SDKMAN is needed only for the JVM ecosystem | no | `S` |
| `java` | `contextual`: Java is the JVM ecosystem runtime | yes | replace `D(java-latest-openjdk)`, `T(default-jdk)`, `P(jdk-openjdk)`, `B(openjdk)` with `K(java)` requiring `sdkman` |
| `groovy` | `contextual`: Groovy is a JVM language and automation ecosystem | yes | replace `D(groovy)`, `T(groovy)`, `P(groovy)`, `B(groovy)` with `K(groovy)` requiring `sdkman`, `java` |
| `springbootcli` | change to `contextual`: Spring Boot CLI is specific to Spring projects | yes | replace `B(spring-boot)` with `K(springboot)` requiring `sdkman`, `java` |
| `gradle` | `contextual`: Gradle is specific to JVM and Android builds | yes | replace `D(gradle)`, `T(gradle)`, `P(gradle)`, `B(gradle)` with `K(gradle)` requiring `sdkman`, `java` |
| `maven` | `contextual`: Maven is specific to JVM builds | yes | replace `D(maven)`, `T(maven)`, `P(maven)`, `B(maven)` with `K(maven)` requiring `sdkman`, `java` |
| `procs` | `optional`: enhanced process listing | yes | `R-linux`, `R-macos`, `B(procs)` |
| `ast-grep` | `core`: structural code search and rewrite | yes | `R-linux`, `R-macos`, `B(ast-grep)` |
| `jless` | `optional`: interactive JSON viewing | yes | `R-linux`, `R-macos`, `B(jless)` |
| `bun` | `contextual`: Bun projects form a distinct runtime ecosystem | yes | `S`, `B(bun)` |
| `pnpm` | `core`: approved global JavaScript package manager | yes | `R-linux`, `R-macos-arm64`, `B(pnpm)` |
| `fnm` | `optional`: Node version switching is useful for multi-version work | yes | `S-linux`, `B(fnm)` |
| `gitleaks` | `core`: secret scanning belongs in the default development baseline | yes | `R-linux`, `R-macos`, `B(gitleaks)` |
| `vale` | `optional`: prose linting is useful for documentation-heavy work | yes | `R-linux`, `R-macos`, `B(vale)` |
| `broot` | `optional`: interactive filesystem navigation | yes | `R-linux`, `R-macos`, `B(broot)` |
| `vscode` | `optional`: GUI editor choice is personal | yes | `A-macos-arm64`, `A-macos-amd64`, `C(visual-studio-code)` |
| `jetbrains-toolbox` | `optional`: JetBrains IDE management is personal | yes | `C(jetbrains-toolbox)` |
| `sublime` | `optional`: GUI editor choice is personal | yes | `A-macos`, `C(sublime-text)` |
| `mmdc` | `contextual`: Mermaid rendering is specific to diagram workflows | yes | `N(@mermaid-js/mermaid-cli)` |
| `pi` | `optional`: Pi is an alternative coding-agent workflow | yes | `H(@earendil-works/pi-coding-agent)` |
| `drawio-desktop` | `optional`: draw.io desktop is specific to diagram workflows | yes | `R-linux-amd64`, `R-linux-arm64`, `A-macos-arm64`, `A-macos-amd64` |
| `drawio-cli` | `optional`: draw.io automation is specific to diagram workflows | yes | `R-linux-amd64`, `R-linux-arm64`, `A-macos-arm64`, `A-macos-amd64`; retain `drawio-desktop` only as a method prerequisite if the chosen method consumes its installed app, otherwise remove it |

The last row's current four methods install the same artifact directly, so none consumes a preinstalled `drawio-desktop`; remove the false tool-level prerequisite. The final four method records have empty `requires`.

### Task 1: Add the closed registry semantic model

**Files:**
- Modify: `installer/model.py:3-187`
- Modify: `installer/registry.toml:59-1821`
- Modify: `installer/ownership.py` at Plan 2's `_ownership_package`
- Modify: `installer/updates.py` at Plan 2's `_declares_authorization`
- Modify: `installer/deps.py`, `installer/catalog_tui.py`, and `installer/uninstall.py` for the mechanical method-field migration
- Modify: `tests/test_model.py`
- Modify: affected registry, ownership, updates, dependency, Catalog, and uninstall fixtures

**Interfaces:**
- Produces: `InstallationScope`, `UpdateStrategy`, and `UninstallStrategy` closed literals.
- Extends: `Method` with `scope`, `manager`, `requires`, `install_package`, `ownership_package`, `update`, and `uninstall`.
- Extends: `Tool` with `recommendation_reason: str`.
- Removes: `Tool.requires`, `Tool.owner`, and `Tool.uninstall`; method semantics become the only planning/ownership metadata.
- Parsing contract: shipped TOML must explicitly provide every semantic key. The sentinel string `none` becomes Python `None` only for package fields.

- [ ] **Step 1: Write failing parser and value tests**

```python
# tests/test_model.py
from pathlib import Path

import pytest

from installer.model import Method, load_tools


def _write_registry(tmp_path: Path, method_lines: str) -> Path:
    registry = tmp_path / "registry.toml"
    registry.write_text(
        """
[[tool]]
id = "demo"
category = "dev"
recommendation = "contextual"
recommendation_reason = "Demo belongs to one ecosystem"
[[tool.method]]
kind = "brew"
formula = "demo"
"""
        + method_lines
    )
    return registry


def test_method_semantics_are_parsed_without_leaking_into_executor_params(tmp_path: Path) -> None:
    method = load_tools(
        _write_registry(
            tmp_path,
            """
scope = "manager"
manager = "Homebrew"
requires = ["brew"]
install_package = "demo"
ownership_package = "demo-cli"
update = "manager"
uninstall = "manager"
""",
        )
    )[0].methods[0]

    assert method == Method(
        kind="brew",
        params={"formula": "demo"},
        scope="manager",
        manager="Homebrew",
        requires=("brew",),
        install_package="demo",
        ownership_package="demo-cli",
        update="manager",
        uninstall="manager",
    )


def test_none_package_sentinel_becomes_none(tmp_path: Path) -> None:
    method = load_tools(
        _write_registry(
            tmp_path,
            """
scope = "user"
manager = "tools-installer"
requires = []
install_package = "none"
ownership_package = "none"
update = "reinstall"
uninstall = "installer"
""",
        )
    )[0].methods[0]
    assert method.install_package is None
    assert method.ownership_package is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scope", '"global"'),
        ("manager", '""'),
        ("requires", '"brew"'),
        ("update", '"automatic"'),
        ("uninstall", '"delete files"'),
    ],
)
def test_invalid_method_semantics_fail_closed(
    tmp_path: Path, field: str, value: str
) -> None:
    lines = {
        "scope": 'scope = "manager"',
        "manager": 'manager = "Homebrew"',
        "requires": 'requires = ["brew"]',
        "install_package": 'install_package = "demo"',
        "ownership_package": 'ownership_package = "demo"',
        "update": 'update = "manager"',
        "uninstall": 'uninstall = "manager"',
    }
    lines[field] = f"{field} = {value}"
    with pytest.raises(ValueError, match=field):
        load_tools(_write_registry(tmp_path, "\n".join(lines.values())))


def test_recommendation_requires_a_visible_rationale(tmp_path: Path) -> None:
    registry = _write_registry(
        tmp_path,
        """
scope = "manager"
manager = "Homebrew"
requires = ["brew"]
install_package = "demo"
ownership_package = "demo"
update = "manager"
uninstall = "manager"
""",
    )
    registry.write_text(registry.read_text().replace(
        'recommendation_reason = "Demo belongs to one ecosystem"\n', ""
    ))
    with pytest.raises(ValueError, match="recommendation_reason"):
        load_tools(registry)
```

- [ ] **Step 2: Run the focused tests and verify red**

Run: `uv run pytest tests/test_model.py -k 'semantics or sentinel or rationale' -v`

Expected: FAIL because `Method` has no semantic fields and the loader accepts no recommendation rationale.

- [ ] **Step 3: Implement the closed types and parser**

```python
# installer/model.py
from typing import Literal, cast

InstallationScope = Literal["user", "system", "manager", "project-wrapper"]
UpdateStrategy = Literal["manager", "reinstall", "unsupported"]
UninstallStrategy = Literal["installer", "manager", "manual", "unsupported"]

INSTALLATION_SCOPES = ("user", "system", "manager", "project-wrapper")
UPDATE_STRATEGIES = ("manager", "reinstall", "unsupported")
UNINSTALL_STRATEGIES = ("installer", "manager", "manual", "unsupported")
_METHOD_SEMANTIC_FIELDS = {
    "scope",
    "manager",
    "requires",
    "install_package",
    "ownership_package",
    "update",
    "uninstall",
}


@dataclass(frozen=True)
class Method:
    kind: str
    params: dict[str, object] = field(default_factory=_empty_params)
    os: tuple[str, ...] = ()
    arch: tuple[str, ...] = ()
    scope: InstallationScope = "user"
    manager: str = "tools-installer"
    requires: tuple[str, ...] = ()
    install_package: str | None = None
    ownership_package: str | None = None
    update: UpdateStrategy = "unsupported"
    uninstall: UninstallStrategy = "unsupported"


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    category: str
    cmd: str
    methods: tuple[Method, ...]
    priority: str = "P3"
    audience: str = "both"
    desc: str = ""
    tier: Literal["basic", "user"] = "basic"
    recommendation: Literal["core", "contextual", "optional"] = "optional"
    recommendation_reason: str = "test fixture"
    post_install: tuple[str, ...] = ()
    default_enabled_sensitive_actions: tuple[str, ...] = ()
    source: str = ""
    version_args: tuple[str, ...] | None = ("--version",)


def _required_string(row: dict[str, object], field: str, tool_id: object) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"tool '{tool_id}': method '{field}' must be a non-empty string")
    return value


def _package_field(row: dict[str, object], field: str, tool_id: object) -> str | None:
    value = _required_string(row, field, tool_id)
    return None if value == "none" else value
```

Inside `load_tools`, cast each method table to `dict[str, object]`, require `scope`, `manager`, `requires`, `install_package`, `ownership_package`, `update`, and `uninstall`, and construct the semantic fields exactly as follows:

```python
scope = _required_string(entry, "scope", row["id"])
if scope not in INSTALLATION_SCOPES:
    raise ValueError(f"tool '{row['id']}': unknown method scope '{scope}'")
manager = _required_string(entry, "manager", row["id"])
method_requires = entry.get("requires")
if not isinstance(method_requires, list) or not all(
    isinstance(value, str) and value for value in cast(list[object], method_requires)
):
    raise ValueError(f"tool '{row['id']}': method 'requires' must be a list of tool ids")
update = _required_string(entry, "update", row["id"])
if update not in UPDATE_STRATEGIES:
    raise ValueError(f"tool '{row['id']}': unknown method update strategy '{update}'")
uninstall = _required_string(entry, "uninstall", row["id"])
if uninstall not in UNINSTALL_STRATEGIES:
    raise ValueError(f"tool '{row['id']}': unknown method uninstall strategy '{uninstall}'")
params = {
    key: value
    for key, value in entry.items()
    if key not in {"kind", "os", "arch", *_METHOD_SEMANTIC_FIELDS}
}
methods.append(
    Method(
        kind=kind,
        params=params,
        os=os_targets,
        arch=arch_targets,
        scope=cast(InstallationScope, scope),
        manager=manager,
        requires=tuple(cast(list[str], method_requires)),
        install_package=_package_field(entry, "install_package", row["id"]),
        ownership_package=_package_field(entry, "ownership_package", row["id"]),
        update=cast(UpdateStrategy, update),
        uninstall=cast(UninstallStrategy, uninstall),
    )
)
```

Require a non-empty tool-level rationale and remove the old tool-level dependency and owner/uninstall parsing:

```python
recommendation_reason = row.get("recommendation_reason")
if not isinstance(recommendation_reason, str) or not recommendation_reason.strip():
    raise ValueError(f"tool '{row['id']}': missing non-empty 'recommendation_reason'")

# In Tool(...)
recommendation_reason=recommendation_reason,
```

Apply a behavior-preserving schema migration to all 198 current methods in the same task so the strict loader never lands against an unreadable shipped registry:

- Add the audit matrix's rationale to every tool.
- Add each method-kind profile's scope, manager, package, update, and uninstall fields.
- Copy each current tool-level prerequisite onto each of that tool's methods for this schema commit only. Task 2's failing semantic audit then removes prerequisites from methods that do not need them.
- Keep Docker's current `dnf` package as `docker` for this schema commit. Task 2's failing exception test changes it to `moby-engine`.
- Remove tool-level `requires`, `owner`, and `uninstall` after their values have moved to methods.

Mechanically adapt Plan 2's package and authorization readers without changing probe behavior:

```python
# installer/ownership.py
def _ownership_package(method: Method, _install_key: str) -> tuple[str, str] | None:
    install_package = method.install_package
    if install_package is None:
        return None
    return install_package, method.ownership_package or install_package


# installer/updates.py
def _declares_authorization(tool: Tool, authorization: UpdateAuthorization) -> bool:
    return any(
        method.kind == authorization.method_kind
        and method.install_package == authorization.package
        for method in tool.methods
    )
```

Change generic dependency integrity, Catalog detail, and uninstall reverse-edge readers from `tool.requires` to the stable union of `method.requires`. Task 2 replaces that mechanical union with the final audited values; Task 3 makes planning use only the selected method.

- [ ] **Step 4: Run model tests and verify green**

Run: `uv run pytest tests/test_model.py tests/test_registry.py tests/test_ownership.py tests/test_updates.py tests/test_deps.py tests/test_catalog_tui.py tests/test_uninstall.py -v`

Expected: PASS. Invalid semantic values fail closed, semantic keys stay out of executor params, `none` maps to `None`, and all 198 shipped methods load through the typed fields without changing pre-audit planning behavior.

- [ ] **Step 5: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS. The schema migration, Plan 2 field adaptation, and every existing caller are coherent before commit.

- [ ] **Step 6: Commit the semantic schema**

```bash
git add installer/model.py installer/registry.toml installer/ownership.py installer/updates.py installer/deps.py installer/catalog_tui.py installer/uninstall.py tests/test_model.py tests/test_registry.py tests/test_ownership.py tests/test_updates.py tests/test_deps.py tests/test_catalog_tui.py tests/test_uninstall.py
git commit -m "feat(registry): model method-level install semantics" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 2: Apply and lock the complete 69-tool, 198-method audit

**Files:**
- Modify: `installer/registry.toml:59-1821`
- Modify: `tests/test_registry.py`
- Modify: `tests/test_deps.py`
- Modify: `tests/test_catalog_tui.py`
- Modify: `tests/test_uninstall.py`

**Interfaces:**
- Consumes: Task 1's explicit method fields.
- Produces: 69 tools and the same 198 methods at this task boundary, classified by the audit matrix.
- Produces: method-only prerequisites: `brew` for every `brew`/`cask`, `pnpm` for `node` and Pi host setup, and the current SDKMAN/JVM prerequisites only on the current JVM methods until Task 6 replaces them.
- Behavior: Ruff and draw.io release methods have no false `uv` or `drawio-desktop` prerequisite. OpenCode's script, pacman, and brew methods have no `pnpm` prerequisite.

- [ ] **Step 1: Write the failing complete-contract tests**

```python
# tests/test_registry.py
import tomllib
from typing import cast


def test_registry_audit_covers_exactly_69_tools_and_198_methods() -> None:
    tools = load_tools(REGISTRY)
    assert len(tools) == 69
    assert sum(len(tool.methods) for tool in tools) == 198


def test_every_shipped_method_explicitly_declares_complete_semantics() -> None:
    with REGISTRY.open("rb") as stream:
        raw = tomllib.load(stream)
    required = {
        "scope",
        "manager",
        "requires",
        "install_package",
        "ownership_package",
        "update",
        "uninstall",
    }
    for tool_row in cast(list[dict[str, object]], raw["tool"]):
        for method in cast(list[dict[str, object]], tool_row["method"]):
            assert required <= method.keys(), (tool_row["id"], method["kind"])


def test_complete_recommendation_classification_is_stable() -> None:
    expected = {
        "core": {
            "uv", "rg", "jq", "fd", "bat", "git", "delta", "eza", "gh",
            "glab", "yq", "ruff", "difftastic", "shfmt", "ast-grep", "pnpm",
            "gitleaks",
        },
        "contextual": {
            "xh", "docker", "podman", "colima", "deno", "sdkman", "java",
            "groovy", "gradle", "maven", "bun", "mmdc",
        },
        "optional": {
            "brew", "sd", "zoxide", "fzf", "lazygit", "zsh", "starship",
            "direnv", "just", "dust", "hyperfine", "bottom", "gum", "glow",
            "gitui", "lazydocker", "dive", "duf", "hexyl", "miller", "tealdeer",
            "fx", "dasel", "gron", "aichat", "codex", "claude", "opencode",
            "springbootcli", "procs", "jless", "fnm", "vale", "broot", "vscode",
            "jetbrains-toolbox", "sublime", "pi", "drawio-desktop", "drawio-cli",
        },
    }
    actual = {
        recommendation: {
            tool.id for tool in load_tools(REGISTRY) if tool.recommendation == recommendation
        }
        for recommendation in expected
    }
    assert actual == expected
    assert all(tool.recommendation_reason for tool in load_tools(REGISTRY))


def test_semantic_profiles_match_every_method_kind() -> None:
    for tool in load_tools(REGISTRY):
        for method in tool.methods:
            if method.kind == "github_release":
                assert (method.scope, method.manager, method.requires) == (
                    "user", "tools-installer", ()
                )
                assert (method.update, method.uninstall) == ("reinstall", "installer")
            elif method.kind == "app":
                assert (method.scope, method.manager, method.requires) == (
                    "user", "tools-installer", ()
                )
                assert (method.update, method.uninstall) == ("reinstall", "installer")
            elif method.kind == "script":
                assert (method.scope, method.manager, method.requires) == (
                    "user", "vendor-installer", ()
                )
                assert (method.install_package, method.ownership_package) == (None, None)
                assert (method.update, method.uninstall) == ("reinstall", "manual")
            elif method.kind in {"dnf", "apt", "pacman"}:
                package = cast(str, method.params["package"])
                assert (method.install_package, method.ownership_package) == (package, package)
                assert (method.scope, method.manager) == ("system", method.kind)
            elif method.kind in {"brew", "cask"}:
                key = "formula" if method.kind == "brew" else "cask"
                assert method.requires == ("brew",)
                assert method.install_package == method.params[key]
                assert method.ownership_package == method.params[key]
                assert (method.scope, method.manager) == ("manager", "Homebrew")
            elif method.kind == "node":
                assert method.requires == ("pnpm",)
                assert method.install_package == method.params["npm_pkg"]
                assert (method.scope, method.manager) == ("manager", "pnpm")
            elif method.kind == "host_setup":
                assert tool.id == "pi"
                assert method.requires == ("pnpm",)
                assert (method.install_package, method.ownership_package) == (
                    "@earendil-works/pi-coding-agent",
                    "@earendil-works/pi-coding-agent",
                )
                assert (method.scope, method.manager) == ("manager", "pnpm")
            else:
                raise AssertionError((tool.id, method.kind))


def test_audited_method_specific_exceptions_are_exact() -> None:
    tools = _tools_by_id()
    assert tools["ruff"].methods[0].requires == ()
    assert [method.requires for method in tools["opencode"].methods] == [
        (), ("pnpm",), (), ("brew",)
    ]
    assert all(method.requires == () for method in tools["drawio-cli"].methods)
    docker_dnf = next(method for method in tools["docker"].methods if method.kind == "dnf")
    assert docker_dnf.params["package"] == "moby-engine"
    assert docker_dnf.ownership_package == "moby-engine"
```

Replace tool-level dependency assertions in `tests/test_deps.py`, `tests/test_catalog_tui.py`, and `tests/test_uninstall.py` with method-level assertions. Keep reverse-dependency behavior by deriving edges from every method's `requires` set.

- [ ] **Step 2: Run the audit tests and verify red**

Run: `uv run pytest tests/test_model.py tests/test_registry.py tests/test_deps.py tests/test_catalog_tui.py tests/test_uninstall.py -v`

Expected: FAIL because the registry lacks explicit semantics, Docker still names `docker`, and dependencies still live on `Tool`.

- [ ] **Step 3: Add all audited metadata and rationales**

For every method, copy the exact profile from the audit matrix. This is the literal TOML shape for each profile; substitute only the package token `p` and retain each method's existing executor parameters and OS/architecture filters:

```toml
# S
scope = "user"
manager = "vendor-installer"
requires = []
install_package = "none"
ownership_package = "none"
update = "reinstall"
uninstall = "manual"

# R or A
scope = "user"
manager = "tools-installer"
requires = []
install_package = "none"
ownership_package = "none"
update = "reinstall"
uninstall = "installer"

# D/T/P
scope = "system"
manager = "dnf" # apt or pacman on those records
requires = []
install_package = "p"
ownership_package = "p"
update = "manager"
uninstall = "manager"

# B/C
scope = "manager"
manager = "Homebrew"
requires = ["brew"]
install_package = "p"
ownership_package = "p"
update = "manager"
uninstall = "manager"

# N
scope = "manager"
manager = "pnpm"
requires = ["pnpm"]
install_package = "p"
ownership_package = "p"
update = "manager"
uninstall = "manager"

# H, used only by Pi
scope = "manager"
manager = "pnpm"
requires = ["pnpm"]
install_package = "@earendil-works/pi-coding-agent"
ownership_package = "@earendil-works/pi-coding-agent"
update = "manager"
uninstall = "manager"
```

Add each audit-matrix rationale as `recommendation_reason`. Change Docker's DNF `package` to `moby-engine`. Remove all tool-level `requires`, `owner`, and `uninstall` keys. Preserve `source` only where the UI still links to project documentation.

For the 17 JVM methods that Task 6 will replace, use their ordinary D/T/P/B profiles now. Do not attach SDKMAN requirements to native or Homebrew methods. This keeps the 198-method audit independently reviewable and proves method-specific dependency behavior before migration.

- [ ] **Step 4: Update dependency consumers to read method edges**

```python
# installer/deps.py
def declared_prerequisites(tool: Tool) -> tuple[str, ...]:
    """Return stable unique prerequisites across the tool's declared methods."""
    seen: set[str] = set()
    return tuple(
        prerequisite
        for method in tool.methods
        for prerequisite in method.requires
        if prerequisite not in seen and not seen.add(prerequisite)
    )


def requires_integrity_errors(catalog: list[Tool]) -> list[str]:
    ids = {tool.id for tool in catalog}
    return [
        f"tool '{tool.id}' method '{method.kind}' requires unknown tool '{required}'"
        for tool in catalog
        for method in tool.methods
        for required in method.requires
        if required not in ids
    ]
```

Use `declared_prerequisites` in reverse-dependency/uninstall guidance only. Planning must wait for Task 3 and use the selected method's `requires`, never this union.

- [ ] **Step 5: Run the full audit surface and verify green**

Run: `uv run pytest tests/test_model.py tests/test_registry.py tests/test_deps.py tests/test_catalog_tui.py tests/test_uninstall.py -v`

Expected: PASS with 69 tools, 198 methods, complete explicit metadata, no false Ruff/OpenCode/draw.io dependency, and method-derived uninstall guidance.

- [ ] **Step 6: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS on the exact audited 198-method tree.

- [ ] **Step 7: Commit the semantic audit**

```bash
git add installer/registry.toml installer/deps.py tests/test_registry.py tests/test_deps.py tests/test_catalog_tui.py tests/test_uninstall.py
git commit -m "feat(registry): audit all tool and method semantics" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 3: Build method-aware plans with complete dispositions

**Files:**
- Modify: `installer/resolve.py:1-64`
- Modify: `installer/deps.py:1-173`
- Modify: `installer/install_plan.py:1-85`
- Modify: `installer/app.py:71-107`
- Modify: `tests/test_resolve.py`
- Modify: `tests/test_deps.py`
- Modify: `tests/test_install_plan.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Produces: `PlanDisposition = Literal["will-install", "already-installed", "unavailable", "blocked"]`.
- Produces: `PlanEntry(tool: Tool, method: Method | None, disposition: PlanDisposition, direct: bool, required_by: str | None, detail: str)`.
- Replaces: `InstallPlan.ordered` storage with `entries`; retains read-only `ordered`, `dragged_in`, `warnings`, and `reasons` projections for console callers.
- Produces: `select_method(tool: Tool, platform: Platform) -> Method | None` using platform/architecture applicability but not current manager presence.
- Produces: `build_install_plan(selected_ids: Collection[str], catalog: Sequence[Tool], platform: Platform, statuses: Mapping[str, ToolStatus], *, execution_mode: ExecutionMode = "install") -> InstallPlan`.
- Behavior: a manager-scoped method is already satisfied only when Plan 2 ownership verifies that exact manager and package. User/system methods retain presence-based satisfaction.

- [ ] **Step 1: Write failing method-selection and disposition tests**

```python
# tests/test_deps.py
def test_selected_method_controls_prerequisites() -> None:
    pnpm = _semantic_tool("pnpm", _method("github_release"))
    demo = _semantic_tool(
        "demo",
        _method("script"),
        _method("node", requires=("pnpm",), manager="pnpm", scope="manager"),
    )
    plan = build_install_plan(
        ["demo"], [pnpm, demo], _platform(), _missing_statuses(pnpm, demo)
    )
    assert [(entry.tool.id, entry.method.kind) for entry in plan.entries] == [
        ("demo", "script")
    ]


def test_unavailable_parent_does_not_leave_orphan_prerequisites() -> None:
    manager = _semantic_tool("manager", _method("script"))
    unavailable = _semantic_tool(
        "unavailable",
        _method("brew", os=("macos",), requires=("manager",), scope="manager"),
    )
    plan = build_install_plan(
        ["unavailable"], [manager, unavailable], _linux(), _missing_statuses(manager, unavailable)
    )
    assert [(entry.tool.id, entry.disposition) for entry in plan.entries] == [
        ("unavailable", "unavailable")
    ]


def test_blocked_direct_selection_and_failing_dependency_are_both_visible() -> None:
    manager = _semantic_tool("manager", _method("brew", os=("macos",)))
    selected = _semantic_tool(
        "selected", _method("node", requires=("manager",), scope="manager", manager="pnpm")
    )
    plan = build_install_plan(
        ["selected"], [manager, selected], _linux(), _missing_statuses(manager, selected)
    )
    assert [(entry.tool.id, entry.disposition, entry.required_by) for entry in plan.entries] == [
        ("manager", "unavailable", "selected"),
        ("selected", "blocked", None),
    ]


def test_every_direct_selection_has_one_review_entry() -> None:
    installed = _semantic_tool("installed", _method("script"))
    missing = _semantic_tool("missing", _method("script"))
    unavailable = _semantic_tool("unavailable", _method("app", os=("macos",)))
    statuses = _statuses(installed=True, missing=False, unavailable=False)
    plan = build_install_plan(
        ["installed", "missing", "unavailable"],
        [installed, missing, unavailable],
        _linux(),
        statuses,
    )
    direct = [entry for entry in plan.entries if entry.direct]
    assert [(entry.tool.id, entry.disposition) for entry in direct] == [
        ("installed", "already-installed"),
        ("missing", "will-install"),
        ("unavailable", "unavailable"),
    ]


def test_manager_scoped_install_is_satisfied_only_by_the_selected_manager() -> None:
    demo = _semantic_tool(
        "demo",
        _method(
            "sdkman",
            scope="manager",
            manager="SDKMAN",
            ownership_package="demo",
        ),
    )
    foreign = _status(demo, installed=True, owner=_verified_owner("apt", "demo"))
    matching = _status(demo, installed=True, owner=_verified_owner("SDKMAN", "demo"))
    assert build_install_plan(["demo"], [demo], _linux(), {"demo": foreign}).ordered == (demo,)
    assert build_install_plan(["demo"], [demo], _linux(), {"demo": matching}).ordered == ()


def _verified_owner(manager: Manager, package: str) -> Ownership:
    return Ownership(
        "verified",
        None,
        ArtifactOwner(manager, package, "fixture"),
        "other-reviewed",
        None,
        "fixture ownership",
    )
```

```python
# tests/test_install_plan.py
def test_plan_projects_only_will_install_entries_for_execution() -> None:
    plan = InstallPlan(
        selected_ids=("present", "missing"),
        entries=(
            PlanEntry(_tool("present"), _method("script"), "already-installed", True, None, "present"),
            PlanEntry(_tool("manager"), _method("script"), "will-install", False, "missing", "required"),
            PlanEntry(_tool("missing"), _method("script"), "will-install", True, None, "missing"),
        ),
    )
    assert [tool.id for tool in plan.ordered] == ["manager", "missing"]
    assert plan.dragged_in == ("manager",)
    assert plan.method_for("missing").kind == "script"
```

- [ ] **Step 2: Run focused planning tests and verify red**

Run: `uv run pytest tests/test_resolve.py tests/test_deps.py tests/test_install_plan.py tests/test_app.py -v`

Expected: FAIL because resolution traverses `Tool.requires`, filters Homebrew by current presence, and omits satisfied/blocked direct selections.

- [ ] **Step 3: Separate platform applicability from manager presence**

```python
# installer/resolve.py
def method_applies(method: Method, platform: Platform) -> bool:
    if method.os and platform.os not in method.os:
        return False
    if method.arch and platform.arch not in method.arch:
        return False
    if method.kind == "cask":
        return platform.os == "macos"
    if method.kind == "rpm_ostree":
        return False
    if method.kind in _NATIVE_OS:
        return not platform.immutable and _NATIVE_OS[method.kind] == platform.os
    return True


def resolve_methods(tool: Tool, platform: Platform) -> list[Method]:
    return sorted(
        (method for method in tool.methods if method_applies(method, platform)),
        key=lambda method: _RANK[method.kind],
    )


def select_method(tool: Tool, platform: Platform) -> Method | None:
    return next(iter(resolve_methods(tool, platform)), None)
```

Do not check `platform.has_brew` in `method_applies`. A selected brew/cask method carries `requires = ["brew"]`; planning installs or satisfies that manager relationship before execution.

- [ ] **Step 4: Add immutable plan entries and projections**

```python
# installer/install_plan.py
PlanDisposition = Literal["will-install", "already-installed", "unavailable", "blocked"]


@dataclass(frozen=True)
class PlanEntry:
    tool: Tool
    method: Method | None
    disposition: PlanDisposition
    direct: bool
    required_by: str | None
    detail: str


@dataclass(frozen=True)
class InstallPlan:
    selected_ids: tuple[str, ...]
    entries: tuple[PlanEntry, ...]
    execution_mode: ExecutionMode = "install"

    @property
    def ordered(self) -> tuple[Tool, ...]:
        return tuple(
            entry.tool for entry in self.entries if entry.disposition == "will-install"
        )

    @property
    def dragged_in(self) -> tuple[str, ...]:
        return tuple(
            entry.tool.id
            for entry in self.entries
            if not entry.direct and entry.disposition == "will-install"
        )

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(
            entry.detail
            for entry in self.entries
            if entry.disposition in {"unavailable", "blocked"}
        )

    @property
    def reasons(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (entry.tool.id, entry.required_by)
            for entry in self.entries
            if entry.required_by is not None
        )

    def reason_for(self, tool_id: str) -> str | None:
        return next(
            (entry.required_by for entry in self.entries if entry.tool.id == tool_id),
            None,
        )

    def method_for(self, tool_id: str) -> Method:
        method = next(
            (entry.method for entry in self.entries if entry.tool.id == tool_id),
            None,
        )
        if method is None:
            raise KeyError(f"no selected method for '{tool_id}'")
        return method
```

Update `action_keys()` and approval methods to iterate `ordered` exactly as before.

- [ ] **Step 5: Implement method-first dependency expansion**

```python
# installer/deps.py
def _method_satisfied(status: ToolStatus, method: Method) -> bool:
    if not status.installed:
        return False
    if method.scope != "manager":
        return True
    owner = status.ownership.artifact_owner
    return (
        status.ownership.outcome == "verified"
        and owner is not None
        and owner.manager == method.manager
        and owner.package == method.ownership_package
    )


def _update_entries(
    selected_ids: Collection[str],
    by_id: Mapping[str, Tool],
    platform: Platform,
    statuses: Mapping[str, ToolStatus],
) -> tuple[PlanEntry, ...]:
    entries: list[PlanEntry] = []
    for tool_id in selected_ids:
        tool = by_id[tool_id]
        status = statuses[tool_id]
        owner = status.ownership.artifact_owner
        method = next(
            (
                candidate
                for candidate in resolve_methods(tool, platform)
                if owner is not None
                and candidate.manager == owner.manager
                and candidate.ownership_package == owner.package
            ),
            None,
        )
        if status.update.state == "current":
            disposition: PlanDisposition = "already-installed"
            detail = f"{tool.id} is already current"
        elif (
            status.update.state == "available"
            and status.ownership.update_authorization is not None
            and method is not None
        ):
            disposition = "will-install"
            detail = f"{tool.id} will update through {method.manager}"
        else:
            disposition = "unavailable"
            detail = f"{tool.id} has no verified authorized update"
        entries.append(PlanEntry(tool, method, disposition, True, None, detail))
    return tuple(entries)


def resolve_dependencies(
    selected_ids: Collection[str],
    catalog: Sequence[Tool],
    *,
    platform: Platform,
    statuses: Mapping[str, ToolStatus],
    execution_mode: ExecutionMode = "install",
) -> tuple[PlanEntry, ...]:
    by_id = {tool.id: tool for tool in catalog}
    if execution_mode == "update":
        return _update_entries(selected_ids, by_id, platform, statuses)
    direct_ids = frozenset(selected_ids)
    entries: dict[str, PlanEntry] = {}
    order: list[str] = []
    visiting: set[str] = set()

    def put(entry: PlanEntry) -> None:
        if entry.tool.id not in entries:
            order.append(entry.tool.id)
        entries[entry.tool.id] = entry

    def visit(tool: Tool, required_by: str | None) -> bool:
        existing = entries.get(tool.id)
        if existing is not None:
            return existing.disposition in {"will-install", "already-installed"}
        if tool.id in visiting:
            raise DependencyCycleError(f"dependency cycle involving '{tool.id}'")
        direct = tool.id in direct_ids
        method = select_method(tool, platform)
        if method is None:
            put(PlanEntry(tool, None, "unavailable", direct, required_by,
                          f"{tool.id} is unavailable on this platform"))
            return False
        status = statuses[tool.id]
        force = execution_mode == "reinstall" and direct
        if not force and _method_satisfied(status, method):
            put(PlanEntry(tool, method, "already-installed", direct, required_by,
                          f"{tool.id} is already installed through {method.manager}"))
            return True
        visiting.add(tool.id)
        prerequisites_ok = True
        for prerequisite_id in method.requires:
            prerequisite = by_id.get(prerequisite_id)
            if prerequisite is None:
                raise ValueError(
                    f"tool '{tool.id}' method '{method.kind}' requires unknown tool "
                    f"'{prerequisite_id}'"
                )
            if not visit(prerequisite, tool.id):
                prerequisites_ok = False
        visiting.remove(tool.id)
        if not prerequisites_ok:
            put(PlanEntry(tool, method, "blocked", direct, required_by,
                          f"{tool.id} is blocked by an unavailable prerequisite"))
            return False
        put(PlanEntry(tool, method, "will-install", direct, required_by,
                      f"{tool.id} will install through {method.manager}"))
        return True

    for tool in order_for_install([by_id[tool_id] for tool_id in selected_ids]):
        visit(tool, None)
    return tuple(entries[tool_id] for tool_id in order)
```

The `_update_entries` branch builds direct entries only: an available, authorized update is `will-install`; current becomes `already-installed`; unknown/unsupported becomes `unavailable`. It never expands method prerequisites for update.

- [ ] **Step 6: Replace plan builders with the current-status signature**

```python
# installer/app.py
def build_install_plan(
    selected_ids: Collection[str],
    catalog: Sequence[Tool],
    platform: Platform,
    statuses: Mapping[str, ToolStatus],
    *,
    execution_mode: ExecutionMode = "install",
) -> InstallPlan:
    entries = resolve_dependencies(
        selected_ids,
        catalog,
        platform=platform,
        statuses=statuses,
        execution_mode=execution_mode,
    )
    return InstallPlan(tuple(selected_ids), entries, execution_mode)
```

Delete `build_update_plan`; the unified builder handles all modes from one supplied snapshot. Update console callers to construct a status map once and pass it in.

- [ ] **Step 7: Run planning tests and verify green**

Run: `uv run pytest tests/test_resolve.py tests/test_deps.py tests/test_install_plan.py tests/test_app.py -v`

Expected: PASS. Methods are selected before prerequisite traversal; every direct selection has one disposition; manager ownership controls satisfaction; unavailable parents leave no orphan prerequisite.

- [ ] **Step 8: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS with console and Textual callers migrated to immutable plan entries.

- [ ] **Step 9: Commit method-aware planning**

```bash
git add installer/resolve.py installer/deps.py installer/install_plan.py installer/app.py tests/test_resolve.py tests/test_deps.py tests/test_install_plan.py tests/test_app.py
git commit -m "feat(planning): resolve method-specific prerequisites" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 4: Render complete Install review and Catalog semantics

**Files:**
- Modify: `installer/catalog_tui.py:26-278`
- Modify: `installer/install_screen.py:119-284`
- Modify: `installer/session.py:96-311`
- Modify: `tests/test_catalog_tui.py`
- Modify: `tests/test_install_screen.py`
- Modify: `tests/test_session.py`

**Interfaces:**
- Consumes: Task 3's `PlanEntry` and `PlanDisposition`.
- Extends: `Summary` with `unavailable: tuple[str, ...] = ()` and `blocked: tuple[str, ...] = ()`.
- Behavior: `run_plan` seeds summary outcomes for direct non-executable entries and executes only `will-install` entries.
- Behavior: Catalog details show recommendation/rationale and the preferred method's manager/scope; Install shows source, manager/scope, method, and disposition for every entry.

- [ ] **Step 1: Write failing rendering and summary tests**

```python
# tests/test_catalog_tui.py
def test_contextual_is_explained_as_ecosystem_specific() -> None:
    tool = replace(
        _tool("java"),
        recommendation="contextual",
        recommendation_reason="Java is the JVM ecosystem runtime",
    )
    screen = CatalogScreen([tool], _statuses([tool]), {}, _linux())
    assert "ecosystem-specific" in screen._row_cells(tool)[2].plain
    assert "Java is the JVM ecosystem runtime" in screen._detail_text(tool)


def test_catalog_detail_shows_preferred_manager_and_scope() -> None:
    tool = _tool_with_method(
        "demo", _method("node", manager="pnpm", scope="manager", requires=("pnpm",))
    )
    screen = CatalogScreen([tool], _statuses([tool]), {}, _linux())
    assert "manager: pnpm" in screen._detail_text(tool)
    assert "scope: manager" in screen._detail_text(tool)
```

```python
# tests/test_install_screen.py
def test_preview_shows_every_direct_disposition_and_reasoned_dependency() -> None:
    plan = _plan(
        PlanEntry(_tool("sdkman"), _method("script"), "will-install", False, "java", "required"),
        PlanEntry(_tool("java"), _method("sdkman"), "will-install", True, None, "selected"),
        PlanEntry(_tool("present"), _method("script"), "already-installed", True, None, "present"),
        PlanEntry(_tool("missing-macos"), None, "unavailable", True, None, "unavailable"),
        PlanEntry(_tool("blocked"), _method("node"), "blocked", True, None, "blocked"),
    )
    screen = InstallScreen(plan, lambda _choices, _emit: Summary((), (), (), ()))
    assert "sdkman — dependency required by java — vendor-installer/user — will install" in screen.plan_text
    assert "java — direct selection — SDKMAN/manager — will install" in screen.plan_text
    assert "present — direct selection — vendor-installer/user — already installed" in screen.plan_text
    assert "missing-macos — direct selection — unavailable" in screen.plan_text
    assert "blocked — direct selection — pnpm/manager — blocked" in screen.plan_text
```

```python
# tests/test_session.py
def test_run_plan_returns_non_executable_direct_dispositions_without_running_them() -> None:
    calls: list[str] = []
    plan = _plan_with_dispositions(
        ("present", "already-installed"),
        ("missing-macos", "unavailable"),
        ("blocked", "blocked"),
    )
    summary = run_plan(
        plan,
        _platform(),
        lambda _event: None,
        statuses=_statuses_for_plan(plan),
        install=lambda tool, *_args, **_kwargs: calls.append(tool.id) or _installed(tool.id),
    )
    assert calls == []
    assert summary.already == ("present",)
    assert summary.unavailable == ("missing-macos",)
    assert summary.blocked == ("blocked",)
```

- [ ] **Step 2: Run focused UI/session tests and verify red**

Run: `uv run pytest tests/test_catalog_tui.py tests/test_install_screen.py tests/test_session.py -k 'ecosystem_specific or preferred_manager or disposition or non_executable' -v`

Expected: FAIL because the UI says `contextual`, Install iterates only `ordered`, and `Summary` has no unavailable/blocked buckets.

- [ ] **Step 3: Render recommendation, rationale, manager, and scope**

```python
# installer/catalog_tui.py
_RECOMMENDATION_LABEL = {
    "core": "core",
    "contextual": "ecosystem-specific",
    "optional": "optional",
}

# Add `platform: Platform` to CatalogScreen.__init__ and save it as self._platform.
# In _row_cells:
tool_name.append(
    f" · {_RECOMMENDATION_LABEL[tool.recommendation]}",
    style="yellow" if tool.recommendation == "contextual" else "dim",
)

# In _detail_text:
method = select_method(tool, self._platform)
detail += (
    f"  |  recommendation: {escape(_RECOMMENDATION_LABEL[tool.recommendation])}"
    f" ({escape(tool.recommendation_reason)})"
)
if method is not None:
    detail += f"  |  manager: {escape(method.manager)}  |  scope: {method.scope}"
```

Append `core = broadly recommended`, `ecosystem-specific = recommended for that ecosystem`, and `optional = useful but not broadly recommended` to `_LEGEND`.

- [ ] **Step 4: Render every plan entry**

```python
# installer/install_screen.py
_DISPOSITION_TEXT = {
    "will-install": "will install",
    "already-installed": "already installed",
    "unavailable": "unavailable",
    "blocked": "blocked",
}


@staticmethod
def _format_plan(
    plan: InstallPlan,
    routine_approval: bool,
    login_shell_approved: bool,
) -> str:
    lines = ["Expanded installation plan"]
    for entry in plan.entries:
        source = (
            "direct selection"
            if entry.direct
            else f"dependency required by {entry.required_by}"
        )
        method = (
            f"{entry.method.manager}/{entry.method.scope}"
            if entry.method is not None
            else "unavailable"
        )
        disposition = _DISPOSITION_TEXT[entry.disposition]
        lines.append(f"{entry.tool.id} — {source} — {method} — {disposition}")
```

Replace only the existing `dragged_in`/`for tool in plan.ordered` review loop with this block; leave the approval block beginning at `if plan.warnings`, sensitive-event disclosures, handoffs, post-install actions, final approval prompt, and existing `return "\n".join(lines)` byte-for-byte unchanged. Initialize table rows from `plan.entries`. Use `queued` only for `will-install`; map the other dispositions to existing terminal states `already-installed` and `no-method` for the row state while the separate disposition text remains visible in the plan summary. Add `Manager/scope` between `Why` and `Method`.

- [ ] **Step 5: Seed summary with direct non-executable dispositions**

```python
# installer/session.py
@dataclass(frozen=True)
class Summary:
    installed: tuple[str, ...]
    already: tuple[str, ...]
    failed: tuple[str, ...]
    no_method: tuple[str, ...]
    mismatched: tuple[str, ...] = ()
    manual_required: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    cancelled: tuple[str, ...] = ()
    unavailable: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()


def _planned_dispositions(plan: InstallPlan) -> tuple[list[str], list[str], list[str]]:
    already = [
        entry.tool.id
        for entry in plan.entries
        if entry.direct and entry.disposition == "already-installed"
    ]
    unavailable = [
        entry.tool.id
        for entry in plan.entries
        if entry.direct and entry.disposition == "unavailable"
    ]
    blocked = [
        entry.tool.id
        for entry in plan.entries
        if entry.direct and entry.disposition == "blocked"
    ]
    return already, unavailable, blocked
```

In `run_plan`, execute only `plan.ordered`, summarize execution outcomes, then `replace` the summary with the three direct disposition tuples. Emit no execution event for unavailable/blocked entries; the preview already carries their final state.

- [ ] **Step 6: Run the complete affected test files**

Run: `uv run pytest tests/test_catalog_tui.py tests/test_install_screen.py tests/test_session.py -v`

Expected: PASS. Catalog defines ecosystem-specific, every direct selection and dependency appears, and only `will-install` entries execute.

- [ ] **Step 7: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS with every existing install mode and screen test using complete review entries.

- [ ] **Step 8: Commit complete review rendering**

```bash
git add installer/catalog_tui.py installer/install_screen.py installer/session.py tests/test_catalog_tui.py tests/test_install_screen.py tests/test_session.py
git commit -m "feat(install): show every selected tool disposition" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 5: Add the fixed SDKMAN candidate executor and ownership adapter

**Files:**
- Modify: `installer/model.py:10-23,107-136`
- Modify: `installer/resolve.py:6-21`
- Modify: `installer/executors.py:1-140`
- Modify: `installer/ownership.py` at Plan 2's adapter implementations and dispatch
- Modify: `tests/test_model.py`
- Modify: `tests/test_resolve.py`
- Modify: `tests/test_executors.py`
- Modify: `tests/test_ownership.py`

**Interfaces:**
- Adds: method kind `sdkman` with required non-empty `candidate` parameter.
- Adds: SDKMAN rank `20`, after SDKMAN's own script prerequisite and alongside other user/manager artifacts.
- Produces: `sdkman_candidate_command(candidate: str) -> list[str]`.
- Consumes: Plan 2's `Ownership`, `ArtifactOwner`, `UpdateAuthorization`, `ResolvedExecutable`, `OwnershipRefresh`, `_failure`, `_single_path`, `_under`, and `_unknown` unchanged.
- Produces: `detect_sdkman_candidate_owner(candidate: str, executable: ResolvedExecutable | None, context: OwnershipRefresh) -> Ownership` and routes applicable `sdkman` methods through it.
- Ownership evidence: one refresh-cached candidate inventory query plus one refresh-cached canonical `current` link query must agree with the resolved executable before authorization is returned.
- Security: candidate is passed as positional parameter `$1`, never interpolated into shell source.

- [ ] **Step 1: Write failing command, validation, and ownership tests**

```python
# tests/test_executors.py
def test_sdkman_candidate_uses_a_fresh_noninteractive_manager_environment() -> None:
    calls: list[list[str]] = []
    execute(
        Method(kind="sdkman", params={"candidate": "gradle"}),
        calls.append,
    )
    assert calls == [[
        "env",
        "CI=true",
        "SDKMAN_NON_INTERACTIVE=true",
        "bash",
        "-c",
        'set -eu; SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"; '
        '. "$SDKMAN_DIR/bin/sdkman-init.sh"; sdk install "$1" </dev/null',
        "sdkman-candidate",
        "gradle",
    ]]


def test_sdkman_candidate_is_positional_not_shell_interpolated() -> None:
    command = sdkman_candidate_command("candidate; touch /tmp/not-run")
    assert command[-1] == "candidate; touch /tmp/not-run"
    assert "candidate; touch" not in command[5]
```

Add `detect_sdkman_candidate_owner` to the existing multiline `installer.ownership` import in `tests/test_ownership.py`, then add these exact fixtures and tests:

```python
# tests/test_ownership.py
_SDKMAN_LIST_GRADLE = (
    "env",
    "CI=true",
    "SDKMAN_NON_INTERACTIVE=true",
    "bash",
    "-c",
    'set -eu; SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"; '
    '. "$SDKMAN_DIR/bin/sdkman-init.sh"; sdk list "$1" </dev/null',
    "sdkman-owner",
    "gradle",
)
_SDKMAN_CURRENT_GRADLE = (
    "env",
    "CI=true",
    "SDKMAN_NON_INTERACTIVE=true",
    "bash",
    "-c",
    'set -eu; SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"; '
    'current="$SDKMAN_DIR/candidates/$1/current"; cd -P -- "$current"; pwd -P',
    "sdkman-owner",
    "gradle",
)


def test_sdkman_candidate_owner_uses_cached_inventory_and_current_link(
    tmp_path: Path,
) -> None:
    version = tmp_path / ".sdkman" / "candidates" / "gradle" / "8.14"
    executable = _resolved_file(version / "bin" / "gradle")
    current = version.parent / "current"
    current.symlink_to(version, target_is_directory=True)
    context = StubRefresh(
        _platform(),
        {
            _SDKMAN_LIST_GRADLE: CommandResult(
                0,
                "Available Gradle Versions\n8.14 installed\n",
                "",
            ),
            _SDKMAN_CURRENT_GRADLE: CommandResult(0, f"{current}\n", ""),
        },
    )
    tool = _tool(Method("sdkman", {"candidate": "gradle"}))

    first = detect_owner(tool, executable, context)
    second = detect_sdkman_candidate_owner("gradle", executable, context)

    assert first == second == Ownership(
        "verified",
        executable,
        ArtifactOwner("SDKMAN", "gradle", "sdkman"),
        "sdkman-candidate",
        UpdateAuthorization("sdkman", "gradle", "sdkman"),
        "SDKMAN candidate gradle owns the canonical executable through its current link",
    )
    assert context.calls == [_SDKMAN_LIST_GRADLE, _SDKMAN_CURRENT_GRADLE]


@pytest.mark.parametrize(
    ("inventory", "outcome"),
    [
        (
            CommandResult(127, "", "", "manager unavailable: sdkman"),
            "manager-unavailable",
        ),
        (
            CommandResult(124, "", "", "ownership probe timed out after 5 seconds"),
            "timeout",
        ),
        (CommandResult(0, "", ""), "malformed-output"),
        (CommandResult(1, "", "candidate not found"), "package-mismatch"),
    ],
)
def test_sdkman_candidate_inventory_failures_are_structured(
    tmp_path: Path,
    inventory: CommandResult,
    outcome: str,
) -> None:
    executable = _resolved_file(tmp_path / "gradle")
    owner = detect_sdkman_candidate_owner(
        "gradle",
        executable,
        StubRefresh(_platform(), {_SDKMAN_LIST_GRADLE: inventory}),
    )
    assert owner.outcome == outcome
    assert owner.artifact_owner is None
    assert owner.update_authorization is None


def test_sdkman_candidate_rejects_missing_or_foreign_current_link(
    tmp_path: Path,
) -> None:
    executable = _resolved_file(tmp_path / "foreign" / "gradle")
    listed = CommandResult(0, "Available Gradle Versions\n8.14 installed\n", "")
    missing = StubRefresh(
        _platform(),
        {
            _SDKMAN_LIST_GRADLE: listed,
            _SDKMAN_CURRENT_GRADLE: CommandResult(1, "", "not installed"),
        },
    )
    assert detect_sdkman_candidate_owner(
        "gradle", executable, missing
    ).outcome == "package-mismatch"

    current = tmp_path / ".sdkman" / "candidates" / "gradle" / "current"
    current.mkdir(parents=True)
    foreign = StubRefresh(
        _platform(),
        {
            _SDKMAN_LIST_GRADLE: listed,
            _SDKMAN_CURRENT_GRADLE: CommandResult(0, f"{current}\n", ""),
        },
    )
    assert detect_sdkman_candidate_owner(
        "gradle", executable, foreign
    ).outcome == "artifact-mismatch"
```

```python
# tests/test_model.py
def test_sdkman_method_requires_candidate(tmp_path: Path) -> None:
    registry = _semantic_registry(tmp_path, kind="sdkman", extra="")
    with pytest.raises(ValueError, match="candidate"):
        load_tools(registry)
```

- [ ] **Step 2: Run focused SDKMAN tests and verify red**

Run: `uv run pytest tests/test_model.py tests/test_resolve.py tests/test_executors.py tests/test_ownership.py -k sdkman -v`

Expected: FAIL because `sdkman` is not a method kind, rank, executor, or ownership adapter.

- [ ] **Step 3: Implement the candidate command and ownership route**

```python
# installer/executors.py
_SDKMAN_INSTALL = (
    'set -eu; SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"; '
    '. "$SDKMAN_DIR/bin/sdkman-init.sh"; sdk install "$1" </dev/null'
)


def sdkman_candidate_command(candidate: str) -> list[str]:
    return [
        "env",
        "CI=true",
        "SDKMAN_NON_INTERACTIVE=true",
        "bash",
        "-c",
        _SDKMAN_INSTALL,
        "sdkman-candidate",
        candidate,
    ]


def _sdkman(method: Method, runner: Runner) -> ExecutionStatus:
    runner(sdkman_candidate_command(require_str(method, "candidate")))
    return "completed"


EXECUTORS = {
    "script": _script,
    "node": _node,
    "host_setup": _host_setup,
    "dnf": _dnf,
    "apt": _apt,
    "pacman": _pacman,
    "brew": _brew,
    "cask": _cask,
    "sdkman": _sdkman,
}
```

Add `sdkman` to `METHOD_KINDS` and `_RANK`. In `load_tools`, validate `candidate` using the same non-empty string rule as `node.npm_pkg`. Add the SDKMAN ownership implementation to Plan 2's existing ownership module:

```python
# installer/ownership.py
_SDKMAN_LIST = (
    'set -eu; SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"; '
    '. "$SDKMAN_DIR/bin/sdkman-init.sh"; sdk list "$1" </dev/null'
)
_SDKMAN_CURRENT = (
    'set -eu; SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"; '
    'current="$SDKMAN_DIR/candidates/$1/current"; cd -P -- "$current"; pwd -P'
)


def _sdkman_probe(script: str, candidate: str) -> tuple[str, ...]:
    return (
        "env",
        "CI=true",
        "SDKMAN_NON_INTERACTIVE=true",
        "bash",
        "-c",
        script,
        "sdkman-owner",
        candidate,
    )


def detect_sdkman_candidate_owner(
    candidate: str,
    executable: ResolvedExecutable | None,
    context: OwnershipRefresh,
) -> Ownership:
    if executable is None:
        return _unknown(
            "command-missing",
            None,
            f"SDKMAN candidate {candidate} has no resolved executable",
        )
    if not candidate or candidate != candidate.strip() or any(
        character.isspace() for character in candidate
    ):
        return _unknown(
            "malformed-output",
            executable,
            "SDKMAN candidate must be one non-empty token",
        )
    inventory = context.probe_once(_sdkman_probe(_SDKMAN_LIST, candidate))
    if (outcome := _failure(inventory)) is not None:
        return _unknown(
            outcome,
            executable,
            inventory.failure or "SDKMAN candidate inventory failed",
        )
    if inventory.returncode != 0:
        return _unknown(
            "package-mismatch",
            executable,
            f"SDKMAN does not list candidate {candidate}",
        )
    if not inventory.stdout.strip():
        return _unknown(
            "malformed-output",
            executable,
            "SDKMAN returned an empty candidate inventory",
        )
    current_result = context.probe_once(_sdkman_probe(_SDKMAN_CURRENT, candidate))
    if (outcome := _failure(current_result)) is not None:
        return _unknown(
            outcome,
            executable,
            current_result.failure or "SDKMAN current-link query failed",
        )
    if current_result.returncode != 0:
        return _unknown(
            "package-mismatch",
            executable,
            f"SDKMAN candidate {candidate} has no current installation",
        )
    current = _single_path(current_result)
    if current is None:
        return _unknown(
            "malformed-output",
            executable,
            f"SDKMAN candidate {candidate} returned no canonical current link",
        )
    if not _under(executable.canonical_target, current):
        return _unknown(
            "artifact-mismatch",
            executable,
            f"{executable.canonical_target} is outside SDKMAN candidate {candidate}",
        )
    return Ownership(
        "verified",
        executable,
        ArtifactOwner("SDKMAN", candidate, "sdkman"),
        "sdkman-candidate",
        UpdateAuthorization("sdkman", candidate, "sdkman"),
        f"SDKMAN candidate {candidate} owns the canonical executable through its current link",
    )
```

Add this exact branch to Plan 2's existing applicable-method adapter dispatch. Keep all existing branches and strongest-outcome selection unchanged:

```python
elif method.kind == "sdkman":
    candidate = method.params.get("candidate")
    if not isinstance(candidate, str):
        results.append(
            _unknown(
                "malformed-output",
                executable,
                "sdkman method has no candidate",
            )
        )
    else:
        results.append(
            detect_sdkman_candidate_owner(candidate, executable, context)
        )
```

- [ ] **Step 4: Run executor, resolver, model, and ownership tests**

Run: `uv run pytest tests/test_model.py tests/test_resolve.py tests/test_executors.py tests/test_ownership.py -v`

Expected: PASS. The install and inventory commands source SDKMAN from `$SDKMAN_DIR` in the same process invocation, are non-interactive, close stdin where SDKMAN may prompt, keep candidate data out of shell source, cache both ownership probes per refresh, and authorize only a canonical executable below the candidate's current link.

- [ ] **Step 5: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS before any shipped tool references the new method kind.

- [ ] **Step 6: Commit SDKMAN candidate execution and ownership**

```bash
git add installer/model.py installer/resolve.py installer/executors.py installer/ownership.py tests/test_model.py tests/test_resolve.py tests/test_executors.py tests/test_ownership.py
git commit -m "feat(installs): add SDKMAN candidate execution and ownership" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 6: Migrate JVM tools and verify SDKMAN ownership

**Files:**
- Modify: `installer/registry.toml`
- Modify: `installer/engine.py:31-103`
- Modify: `installer/session.py:39-280`
- Modify: `installer/install_screen.py:230-249`
- Modify: `setup.py` at Plan 2's `new_refresh_context` and `_start_install`
- Modify: `tests/test_registry.py`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_session.py`
- Modify: `tests/test_install_screen.py`
- Modify: `tests/test_setup.py`

**Interfaces:**
- Consumes: Plan 2's `Ownership`, `ArtifactOwner`, `OwnershipRefresh`, and injected `ExecutableResolver` plus Task 5's `detect_sdkman_candidate_owner` unchanged.
- Produces: `VerifyMethodOwnership = Callable[[Tool, Method], Ownership]` as the engine injection type; setup satisfies it with a closure that creates one fresh refresh context per post-install verification.
- Extends: `install_tool(..., *, method: Method | None = None, fallback_methods: tuple[Method, ...] = (), verify_ownership: VerifyMethodOwnership | None = None, ...) -> InstallOutcome`.
- Extends: `Install` protocol and `run_plan` to pass `plan.method_for(tool.id)`.
- Behavior: a planned method is attempted first. Fallback methods are allowed only when all their method prerequisites are already satisfied in the supplied status map.
- Behavior: SDKMAN execution is successful only when Task 5's adapter verifies the candidate owner immediately afterward.
- Registry result: 69 tools, 186 methods, and exactly five `sdkman` candidate records.

- [ ] **Step 1: Write failing JVM migration and ownership tests**

```python
# tests/test_registry.py
def test_jvm_candidates_are_sdkman_exclusive() -> None:
    tools = _tools_by_id()
    expected = {
        "java": ("java", ("sdkman",)),
        "gradle": ("gradle", ("sdkman", "java")),
        "maven": ("maven", ("sdkman", "java")),
        "groovy": ("groovy", ("sdkman", "java")),
        "springbootcli": ("springboot", ("sdkman", "java")),
    }
    for tool_id, (candidate, requires) in expected.items():
        tool = tools[tool_id]
        assert [method.kind for method in tool.methods] == ["sdkman"]
        assert tool.methods[0].params == {"candidate": candidate}
        assert tool.methods[0].requires == requires
        assert tool.methods[0].manager == "SDKMAN"
        assert tool.methods[0].ownership_package == candidate
        assert tool.recommendation == "contextual"
    assert len(tools) == 69
    assert sum(len(tool.methods) for tool in tools.values()) == 186
```

```python
# tests/test_engine.py
def test_sdkman_candidate_requires_verified_sdkman_ownership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("installer.engine.is_installed", lambda _tool: False)
    tool = _sdkman_tool("gradle")
    method = tool.methods[0]
    calls: list[list[str]] = []
    verified = Ownership(
        "verified",
        None,
        ArtifactOwner("SDKMAN", "gradle", "sdkman"),
        "sdkman-candidate",
        UpdateAuthorization("sdkman", "gradle", "sdkman"),
        "fixture inventory and current link",
    )
    outcome = install_tool(
        tool,
        _platform(),
        calls.append,
        method=method,
        verify_ownership=lambda actual_tool, actual_method: (
            verified
            if (actual_tool, actual_method) == (tool, method)
            else pytest.fail("wrong ownership input")
        ),
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "sdkman"
    assert calls[0][-1] == "gradle"


def test_unverified_sdkman_candidate_fails_closed_after_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("installer.engine.is_installed", lambda _tool: False)
    tool = _sdkman_tool("gradle")
    outcome = install_tool(
        tool,
        _platform(),
        lambda _command: None,
        method=tool.methods[0],
        verify_ownership=lambda _tool, _method: Ownership(
            "manager-unavailable",
            None,
            None,
            "unknown",
            None,
            "SDKMAN is unavailable",
        ),
    )
    assert outcome.status == "failed"
    assert "SDKMAN ownership verification failed" in str(outcome.errors[0])
```

```python
# tests/test_session.py
def test_java_and_gradle_plan_executes_sdkman_then_both_candidates() -> None:
    tools = _jvm_tools()
    statuses = _missing_statuses(*tools)
    plan = build_install_plan(
        ["java", "gradle"], tools, _platform(), statuses
    )
    candidates: list[str] = []
    summary = run_plan(
        plan,
        _platform(),
        lambda _event: None,
        statuses=statuses,
        install=lambda tool, _platform, _runner, _resolve_tag, *, method, **_kwargs: (
            candidates.append(str(method.params.get("candidate", tool.id)))
            or InstallOutcome(tool.id, "installed", method.kind)
        ),
    )
    assert [entry.tool.id for entry in plan.entries] == ["sdkman", "java", "gradle"]
    assert plan.entries[0].required_by == "java"
    assert candidates == ["sdkman", "java", "gradle"]
    assert summary.installed == ("sdkman", "java", "gradle")
```

- [ ] **Step 2: Run focused JVM tests and verify red**

Run: `uv run pytest tests/test_registry.py tests/test_engine.py tests/test_session.py tests/test_install_screen.py -k 'jvm or sdkman or java_and_gradle' -v`

Expected: FAIL because JVM tools still have native/Homebrew methods, engine re-resolves methods, and no post-execution ownership verification occurs.

- [ ] **Step 3: Replace the 17 JVM methods with five candidate records**

Use this exact record shape, changing the candidate and prerequisites according to the matrix:

```toml
[[tool.method]]
kind = "sdkman"
candidate = "gradle"
scope = "manager"
manager = "SDKMAN"
requires = ["sdkman", "java"]
install_package = "gradle"
ownership_package = "gradle"
update = "manager"
uninstall = "manager"
```

Java uses `requires = ["sdkman"]`. Gradle, Maven, Groovy, and Spring Boot CLI use `requires = ["sdkman", "java"]`. Spring Boot CLI uses candidate/package `springboot` and recommendation `contextual`. Delete every native and Homebrew JVM method. Do not add project-wrapper methods.

Update Task 2's complete registry contract at the same migration boundary:

```python
def test_registry_contains_69_tools_and_186_post_migration_methods() -> None:
    tools = load_tools(REGISTRY)
    assert len(tools) == 69
    assert sum(len(tool.methods) for tool in tools) == 186


# In test_complete_recommendation_classification_is_stable:
# move "springbootcli" from the optional set to the contextual set.

# Add this branch before the semantic-profile test's final AssertionError:
elif method.kind == "sdkman":
    candidate = cast(str, method.params["candidate"])
    assert (method.scope, method.manager) == ("manager", "SDKMAN")
    assert (method.install_package, method.ownership_package) == (
        candidate,
        candidate,
    )
    assert (method.update, method.uninstall) == ("manager", "manager")
```

Rename the old `198` runtime-count test rather than keeping contradictory final counts. The complete audit matrix in this plan remains the review record for all 198 input methods and their 17 replacement dispositions.

In Install guidance, append these reviewed notes when the plan contains Gradle or Maven:

```python
if any(entry.tool.id == "gradle" for entry in plan.entries):
    lines.append("Project guidance: prefer ./gradlew when the repository provides it.")
if any(entry.tool.id == "maven" for entry in plan.entries):
    lines.append("Project guidance: prefer ./mvnw when the repository provides it.")
```

- [ ] **Step 4: Execute the planned method and verify SDKMAN ownership**

```python
# installer/engine.py
from collections.abc import Callable
from typing import TypeAlias


VerifyMethodOwnership: TypeAlias = Callable[[Tool, Method], Ownership]


class OwnershipVerificationError(RuntimeError):
    pass


def _verified_sdkman_candidate(
    tool: Tool,
    method: Method,
    verify_ownership: VerifyMethodOwnership | None,
) -> None:
    if verify_ownership is None:
        raise OwnershipVerificationError(
            f"{tool.id}: SDKMAN ownership verifier was not configured"
        )
    ownership = verify_ownership(tool, method)
    artifact = ownership.artifact_owner
    if not (
        ownership.outcome == "verified"
        and artifact is not None
        and artifact.manager == "SDKMAN"
        and artifact.package == method.ownership_package
    ):
        raise OwnershipVerificationError(
            f"{tool.id}: SDKMAN ownership verification failed: {ownership.detail}"
        )


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
    method: Method | None = None,
    fallback_methods: tuple[Method, ...] = (),
    verify_ownership: VerifyMethodOwnership | None = None,
) -> InstallOutcome:
    if not force and is_installed(tool):
        return InstallOutcome(tool.id, "already-installed")
    methods = [method, *fallback_methods] if method is not None else resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, "no-method")
    ctx = ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)
    errors: list[Exception] = []
    for candidate in methods:
        if isinstance(ctx.runner, MethodAwareRunner):
            ctx.runner.method_started(candidate.kind)
        try:
            verified, handoff, evidence = _perform(
                tool, candidate, ctx, artifact_resolver
            )
            if candidate.kind == "sdkman":
                _verified_sdkman_candidate(tool, candidate, verify_ownership)
            if handoff:
                return InstallOutcome(tool.id, "manual-required", candidate.kind, handoff=handoff)
            if (
                receipt_store is not None
                and candidate.kind in _RECEIPT_KINDS
                and evidence is not None
            ):
                receipt_store.issue(tool.id, candidate.kind, evidence)
            return InstallOutcome(tool.id, "installed", candidate.kind, verified=verified)
        except OwnershipVerificationError as error:
            return InstallOutcome(tool.id, "failed", candidate.kind, (error,))
        except ChecksumMismatch as error:
            if checksum_policy == "fail":
                return InstallOutcome(tool.id, "checksum-mismatch", candidate.kind, (error,))
            errors.append(error)
        except (
            CommandError,
            executors.ExecutorError,
            VersionError,
            OSError,
            ValueError,
        ) as error:
            errors.append(error)
    return InstallOutcome(tool.id, "failed", errors=tuple(errors))
```

Add the exact protocol and session forwarding below. The manager mismatch expression bypasses only the engine's presence guard; checksum, approval, method order, and ownership verification remain active.

```python
# installer/session.py
class Install(Protocol):
    def __call__(
        self,
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = ...,
        force: bool = ...,
        method: Method | None = ...,
        fallback_methods: tuple[Method, ...] = ...,
        verify_ownership: VerifyMethodOwnership | None = ...,
    ) -> InstallOutcome: ...


def _eligible_fallbacks(
    tool: Tool,
    planned: Method,
    platform: Platform,
    statuses: Mapping[str, ToolStatus],
) -> tuple[Method, ...]:
    return tuple(
        candidate
        for candidate in resolve_methods(tool, platform)
        if candidate != planned
        and all(statuses[required].installed for required in candidate.requires)
    )


# Inside run_plan's `for tool in plan.ordered` loop:
method = plan.method_for(tool.id)
status = statuses[tool.id]
force = plan.execution_mode == "reinstall" or (
    status.installed and method.scope == "manager"
)
outcome = run_installs(
    [tool],
    platform,
    tool_runner,
    resolve_tag,
    install,
    on_mismatch=on_mismatch,
    force=force,
    method=method,
    fallback_methods=_eligible_fallbacks(tool, method, platform, statuses),
    verify_ownership=verify_ownership,
)[0]
```

Extend `run_installs` with the same three keyword-only parameters and forward them in its initial, retry, and checksum-fallback calls. `update` mode retains its existing `update_tool` branch and does not call `run_installs`.

Add `verify_ownership: VerifyMethodOwnership | None = None` to `run_plan`. The planned method always remains eligible because its dependencies occur earlier in the plan; fallback methods are eligible only when their method prerequisites are present in the supplied operation snapshot.

Bind the injected callable in `setup.py` to Task 5's SDKMAN adapter and the existing Plan 1 context factory wired by Plan 2:

```python
# setup.py, inside _build_app after new_refresh_context
def verify_method_ownership(tool: Tool, method: Method) -> Ownership:
    candidate = method.params.get("candidate")
    if method.kind != "sdkman" or not isinstance(candidate, str) or not candidate:
        raise ValueError(f"{tool.id}: method does not declare an SDKMAN candidate")
    return detect_sdkman_candidate_owner(
        candidate,
        executable_resolver(tool.cmd),
        new_refresh_context(),
    )
```

Extend Plan 2's receipt-bound install closure so the new planning arguments reach `install_tool` without losing receipt issuance:

```python
def install_with_receipts(
    tool: Tool,
    current_platform: Platform,
    runner: Runner,
    resolve_tag: TagResolver,
    *,
    checksum_policy: ChecksumPolicy = "fail",
    force: bool = False,
    method: Method | None = None,
    fallback_methods: tuple[Method, ...] = (),
    verify_ownership: VerifyMethodOwnership | None = None,
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
        method=method,
        fallback_methods=fallback_methods,
        verify_ownership=verify_ownership,
    )
```

Pass `verify_ownership=verify_method_ownership` and `install=install_with_receipts` from `_start_install` to `run_plan`. The fresh Plan 1 `RefreshContext` gives immediate verification bounded probes through Plan 2's `OwnershipRefresh.probe_once` contract and a private cache without sharing state across coordinator generations.

- [ ] **Step 5: Run JVM registry, engine, session, and preview tests**

Run: `uv run pytest tests/test_registry.py tests/test_engine.py tests/test_session.py tests/test_install_screen.py tests/test_setup.py -v`

Expected: PASS with 69 tools/186 methods, visible `SDKMAN -> Java -> Gradle`, both candidate commands routed through SDKMAN, wrapper guidance, and fail-closed ownership verification.

- [ ] **Step 6: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS with this plan's SDKMAN verifier wired through setup and no native/Homebrew JVM route.

- [ ] **Step 7: Commit the JVM migration**

```bash
git add installer/registry.toml installer/engine.py installer/session.py installer/install_screen.py setup.py tests/test_registry.py tests/test_engine.py tests/test_session.py tests/test_install_screen.py tests/test_setup.py
git commit -m "feat(jvm): install global candidates exclusively with SDKMAN" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 7: Use the current coordinator snapshot and enforce selection lifecycle

**Files:**
- Modify: `installer/catalog_tui.py:303-310`
- Modify: `installer/wizard_app.py:51-55,623-807`
- Modify: `installer/install_screen.py:169-197,411-429`
- Modify: `setup.py:144-320`
- Modify: `tests/test_wizard_app.py`
- Modify: `tests/test_install_screen.py`
- Modify: `tests/test_setup.py`

**Interfaces:**
- Consumes unchanged: Plan 1's `StatusInspector = Callable[[Tool, bool, RefreshContext], ToolStatus]`, `RefreshContextFactory = Callable[[], RefreshContext]`, `CatalogScreen.status_for`, captured `operation_statuses`, and `UnifiedApp.request_status_refresh(kind) -> int`.
- Changes: `BuildPlan = Callable[[list[str], ExecutionMode, Mapping[str, ToolStatus]], InstallPlan]`.
- Produces: `CatalogScreen.status_snapshot() -> Mapping[str, ToolStatus]`, an immutable copy of Plan 1's current atomically installed map.
- Produces: `resolved_direct_ids(plan: InstallPlan, summary: Summary) -> frozenset[str]`.
- Behavior: `_open_install` captures one current complete snapshot and uses it for both planning and operation evidence.
- Behavior: operation evidence contains exactly the `will-install` entries in `plan.ordered`; Plan 1's Install screen displays preparation before calling `StartInstall`.
- Behavior: unapproved preview cancellation returns to Catalog without invoking completion or refresh.
- Behavior: completion marks Install finished first, clears only resolved direct selections, then calls `request_status_refresh("post-install")`.

- [ ] **Step 1: Write failing snapshot and lifecycle tests**

```python
# tests/test_wizard_app.py
async def test_planning_uses_the_latest_catalog_snapshot() -> None:
    tool = _tool("java")
    old = {"java": _status(tool, installed=False)}
    current = {"java": _status(tool, installed=True, owner=_sdkman_owner("java"))}
    seen: list[Mapping[str, ToolStatus]] = []
    app = _app(
        tools=[tool],
        statuses=old,
        inspect_status=lambda actual, _updates, _context: current[actual.id],
        build_plan=lambda ids, mode, statuses: (
            seen.append(statuses) or build_install_plan(ids, [tool], _platform(), statuses)
        ),
        start_install=_no_op_start,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space", "enter")
    assert seen == [current]
    install = app.screen
    assert isinstance(install, InstallScreen)
    assert install.plan is not None
    assert install.plan.entries[0].disposition == "already-installed"


async def test_operation_capture_contains_only_will_install_entries() -> None:
    captured: list[set[str]] = []
    app = _app(
        start_install=lambda _plan, statuses, _choices, _emit: (
            captured.append(set(statuses)) or Summary(("fd",), (), (), ())
        )
    )
    async with app.run_test() as pilot:
        await pilot.press("space", "enter", "enter")
        await pilot.pause()
    assert captured == [{"fd"}]


async def test_cancelled_unapproved_preview_preserves_selection_and_skips_post_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(start_install=_successful_start)
    async with app.run_test() as pilot:
        await pilot.pause()
        requests: list[StatusKind] = []
        monkeypatch.setattr(
            app,
            "request_status_refresh",
            lambda kind: requests.append(kind) or 99,
        )
        await pilot.press("space", "enter", "escape")
        await pilot.pause()
    assert app.catalog.selected == {"fd"}
    assert requests == []


@pytest.mark.parametrize(
    ("summary", "cleared", "retained"),
    [
        (Summary(("ok",), ("present",), (), ()), {"ok", "present"}, set()),
        (Summary((), (), ("failed",), ()), set(), {"failed"}),
        (Summary((), (), (), (), skipped=("skipped",)), set(), {"skipped"}),
        (Summary((), (), (), (), cancelled=("cancelled",)), set(), {"cancelled"}),
        (Summary((), (), (), (), unavailable=("unavailable",)), set(), {"unavailable"}),
        (Summary((), (), (), (), blocked=("blocked",)), set(), {"blocked"}),
    ],
)
def test_resolved_direct_ids_cover_every_terminal_disposition(
    summary: Summary, cleared: set[str], retained: set[str]
) -> None:
    plan = _direct_plan(*(cleared | retained))
    assert resolved_direct_ids(plan, summary) == frozenset(cleared)


async def test_dependency_success_never_clears_catalog_selection() -> None:
    plan = _sdkman_java_gradle_plan()
    app = _app_with_plan(plan, Summary(("sdkman", "java", "gradle"), (), (), ()))
    app.catalog._browser.selected.update({"java", "gradle"})
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
    assert app.catalog.selected == set()
    assert "sdkman" not in app.catalog.selected
```

- [ ] **Step 2: Run focused lifecycle tests and verify red**

Run: `uv run pytest tests/test_wizard_app.py tests/test_install_screen.py tests/test_setup.py -k 'snapshot or operation_capture or unapproved or resolved_direct or dependency_success' -v`

Expected: FAIL because planning closes over `completed`, cancellation calls completion, and `BuildPlan` does not receive the current complete Catalog map.

- [ ] **Step 3: Make preview cancellation distinct from completion**

```python
# installer/install_screen.py
def cancel_pending(self) -> None:
    """Abandon an unapproved preview without producing operation outcomes."""
    if self.started or self.finished:
        return
    self._plan = None
    self._start = None
    self.rows = {}
    self.plan_text = ""
    self.output_text = ""
    if self.is_mounted:
        self._render_plan()
```

Do not call `_finish`, `on_complete`, or emit cancelled execution events. Once approval starts execution, cancellation remains an execution outcome and is retained.

- [ ] **Step 4: Plan and prepare from Plan 1's current snapshot**

```python
# installer/wizard_app.py
from types import MappingProxyType

BuildPlan: TypeAlias = Callable[
    [list[str], ExecutionMode, Mapping[str, ToolStatus]],
    InstallPlan,
]


# installer/catalog_tui.py
def status_snapshot(self) -> Mapping[str, ToolStatus]:
    return MappingProxyType(dict(self._statuses))


# installer/wizard_app.py
async def _open_install(
    self,
    selected_ids: list[str],
    mode: ExecutionMode = "install",
) -> None:
    build_plan = self._build_plan
    start_install = self._start_install
    if build_plan is None or start_install is None:
        return
    snapshot = self._catalog.status_snapshot()
    plan = build_plan(selected_ids, mode, snapshot)
    operation_statuses = {tool.id: snapshot[tool.id] for tool in plan.ordered}
    screen = self._install_screen()
    if self.current_view == "install":
        await self.show_view("catalog")
    screen.prepare(
        plan,
        lambda choices, emit: start_install(
            plan,
            operation_statuses,
            choices,
            emit,
        ),
    )
    await self.show_view("install")
```

Implement `_install_screen()` as this checked access to the installed screen, then use `show_view` for every transition:

```python
def _install_screen(self) -> InstallScreen:
    screen = self._views["install"]
    if not isinstance(screen, InstallScreen):
        raise RuntimeError("installed install view has the wrong screen type")
    return screen
```

Expose the reviewed plan without reaching into `_plan`:

```python
# installer/install_screen.py
@property
def plan(self) -> InstallPlan | None:
    return self._plan
```

- [ ] **Step 5: Clear only resolved direct selections and schedule refresh last**

```python
# installer/wizard_app.py
def resolved_direct_ids(plan: InstallPlan, summary: Summary) -> frozenset[str]:
    direct = {entry.tool.id for entry in plan.entries if entry.direct}
    return frozenset((set(summary.installed) | set(summary.already)) & direct)


def _finish_catalog_operation(self, summary: Summary) -> None:
    screen = self._install_screen()
    plan = screen.plan
    if plan is None:
        return
    self._catalog.discard_selected(resolved_direct_ids(plan, summary))
    self.request_status_refresh("post-install")
```

`InstallScreen._finish` must set `summary`, `finished`, and the navigable footer before invoking `_on_complete`. Plan 1 owns the asynchronous request, so this callback never blocks navigation.

- [ ] **Step 6: Replace setup's stale completed set with pure wiring**

```python
# setup.py inside _build_app
def build_plan(
    selected_ids: list[str],
    mode: ExecutionMode,
    statuses: Mapping[str, ToolStatus],
) -> InstallPlan:
    return build_install_plan(
        selected_ids,
        tools,
        platform,
        statuses,
        execution_mode=mode,
    )
```

Delete `completed`, `_track`, and every closure that mutates them. Keep Plan 1's `inspect_status=inspect_statuses` and `refresh_context=new_refresh_context` constructor wiring unchanged. Keep Task 6's `verify_method_ownership` closure bound into execution. Keep doctor and uninstall initial inputs derived from Plan 1's initial local snapshot.

- [ ] **Step 7: Run all app, screen, and composition tests**

Run: `uv run pytest tests/test_wizard_app.py tests/test_install_screen.py tests/test_setup.py -v`

Expected: PASS. Planning sees the latest complete Catalog generation, operation capture covers only executable entries, preview cancellation preserves selection, completion clears only successful/already direct selections, and Plan 1 schedules post-install refresh after Install finishes.

- [ ] **Step 8: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS with Plan 1 responsiveness and Plan 2 ownership tests unchanged.

- [ ] **Step 9: Commit snapshot planning and lifecycle**

```bash
git add installer/wizard_app.py installer/install_screen.py setup.py tests/test_wizard_app.py tests/test_install_screen.py tests/test_setup.py
git commit -m "feat(catalog): preserve actionable selections across installs" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 8: Update README semantics and current catalog inventory

**Files:**
- Modify: `README.md:22-205`
- Modify: `tests/test_registry.py`

**Interfaces:**
- Documents: 69 tools, recommendation labels, installation scope, method-specific prerequisites, complete Install dispositions, selection lifecycle, SDKMAN-exclusive JVM candidates, and project-wrapper guidance.
- Removes: stale 49-tool count, stale runtime list, and generic tool-level `requires` explanation.

- [ ] **Step 1: Write a failing documentation contract test**

```python
# tests/test_registry.py
def test_readme_documents_current_catalog_and_jvm_flow() -> None:
    readme = (REGISTRY.parent.parent / "README.md").read_text()
    for text in (
        "69 tools",
        "ecosystem-specific",
        "Installation scope",
        "method-specific prerequisites",
        "SDKMAN -> Java -> Gradle",
        "already installed",
        "unavailable",
        "blocked",
        "Failed, skipped, cancelled, unavailable, and blocked selections remain staged",
        "./gradlew",
        "./mvnw",
    ):
        assert text in readme
    assert "all 49 tools" not in readme
```

- [ ] **Step 2: Run the documentation contract and verify red**

Run: `uv run pytest tests/test_registry.py::test_readme_documents_current_catalog_and_jvm_flow -v`

Expected: FAIL because README still advertises 49 tools and tool-level `requires`.

- [ ] **Step 3: Replace the stale sections with exact user-facing copy**

Use these paragraphs verbatim under `What it does`, `Available tools`, `Catalog recovery controls`, and `How installs are decided`:

```markdown
The Catalog contains 69 tools. Recommendation and installation scope answer
different questions:

- **core**: broadly recommended for the supported development environment.
- **ecosystem-specific**: recommended when you work in that ecosystem. The
  registry stores this value as `contextual`; it does not mean project-local and
  does not add a dependency.
- **optional**: useful, but not broadly recommended.

### Installation scope

Each selected method shows one scope: **user** for home-directory installs,
**system** for the operating-system package layer, **manager** for tools owned by
Homebrew, pnpm, or SDKMAN, and **project-wrapper** for repository-provided
guidance. The Install review shows the selected manager and scope.

### Method-specific prerequisites

The installer chooses an applicable method before expanding prerequisites. A
pnpm method can require pnpm without making a script method require pnpm; a
Homebrew method can require Homebrew without affecting a release download. The
review lists each added dependency beside the selected tool that needs it.

Every direct selection remains visible in Install as **will install**, **already
installed**, **unavailable**, or **blocked**. Cancelling an unapproved preview
keeps the selection. Successful and already-installed selections clear after
completion. Failed, skipped, cancelled, unavailable, and blocked selections
remain staged for correction or retry.

### JVM tools

SDKMAN exclusively manages the Catalog's global Java, Gradle, Maven, Groovy, and
Spring Boot CLI candidates. Selecting Java and Gradle produces the visible order
`SDKMAN -> Java -> Gradle`; both candidates execute through the same freshly
sourced non-interactive SDKMAN environment. In a repository, prefer `./gradlew`
and `./mvnw` when those wrappers are present.
```

Replace the available-tools table with this exact 69-tool inventory:

```markdown
| Category | Tools |
| --- | --- |
| pkg-mgr | `uv`, `brew`, `pnpm` |
| search | `rg`, `fd`, `fzf`, `ast-grep` |
| data | `jq`, `yq`, `miller`, `fx`, `dasel`, `gron`, `jless` |
| view | `bat`, `eza`, `glow`, `hexyl` |
| text | `sd` |
| git | `git`, `delta`, `lazygit`, `gh`, `glab`, `difftastic`, `gitui` |
| nav | `zoxide`, `broot` |
| shell | `zsh`, `starship`, `direnv`, `gum` |
| dev | `just`, `ruff`, `hyperfine`, `shfmt`, `tealdeer`, `vale` |
| sysinfo | `dust`, `bottom`, `duf`, `procs` |
| net | `xh` |
| docker | `lazydocker`, `docker`, `podman`, `colima`, `dive` |
| ai | `aichat`, `codex`, `claude`, `opencode`, `pi` |
| runtime | `deno`, `sdkman`, `java`, `groovy`, `springbootcli`, `gradle`, `maven`, `bun`, `fnm` |
| security | `gitleaks` |
| editor | `vscode`, `jetbrains-toolbox`, `sublime` |
| diagram | `mmdc`, `drawio-desktop`, `drawio-cli` |
```

Keep the checksum legend tied to method metadata; remove stale checkmarks from the old table because the replacement table carries no per-tool checksum mark.

- [ ] **Step 4: Run the README contract and Markdown-adjacent tests**

Run: `uv run pytest tests/test_registry.py tests/test_ci_workflow.py -v`

Expected: PASS. README says 69 tools, defines ecosystem-specific and scope, documents all dispositions/lifecycle, and names SDKMAN plus wrapper guidance.

- [ ] **Step 5: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS; documentation checks and all code gates remain green.

- [ ] **Step 6: Commit the documentation**

```bash
git add README.md tests/test_registry.py
git commit -m "docs: explain registry semantics and SDKMAN planning" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 9: Add the sandboxed headless Catalog-to-SDKMAN journey

**Files:**
- Create: `tests/test_catalog_sdkman_e2e.py`

**Interfaces:**
- Consumes: Plan 1's coordinator/context-factory API, Plan 2's ownership values, Task 5's SDKMAN verifier, and Tasks 1-8 unchanged.
- Covers: immediate pending snapshot, responsive navigation during blocked enrichment, current snapshot planning, Java/Gradle selection, SDKMAN dependency order, fake candidate execution, finished Install before refresh release, resolved selection clearing, and no real home/subprocess access.

- [ ] **Step 1: Write the complete failing E2E test**

```python
# tests/test_catalog_sdkman_e2e.py
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from threading import Event

import pytest

from installer.app import build_install_plan
from installer.doctor import DoctorReport
from installer.health import UNKNOWN_HEALTH
from installer.install_plan import ExecutionEvent, ExecutionMode, InstallPlan
from installer.install_screen import InstallScreen
from installer.model import Tool, load_tools
from installer.ownership import ArtifactOwner, Ownership, UpdateAuthorization
from installer.platform import Platform
from installer.session import ExecutionChoices, Summary, run_plan
from installer.status import RefreshContext, ToolStatus
from installer.status_coordinator import RefreshContextFactory, StatusInspector
from installer.updates import UNKNOWN_UPDATE
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs

REGISTRY = Path(__file__).parents[1] / "installer" / "registry.toml"


def _unknown(tool: Tool) -> ToolStatus:
    return ToolStatus(
        tool,
        False,
        Ownership(
            "command-missing",
            None,
            None,
            "unknown",
            None,
            "pending",
        ),
        UNKNOWN_HEALTH,
        UNKNOWN_UPDATE,
    )


def _sdkman_owner(candidate: str) -> Ownership:
    return Ownership(
        "verified",
        None,
        ArtifactOwner("SDKMAN", candidate, "sdkman"),
        "sdkman-candidate",
        UpdateAuthorization("sdkman", candidate, "sdkman"),
        "fixture inventory and current link",
    )


def _app(
    tools: list[Tool],
    statuses: Mapping[str, ToolStatus],
    inspect_status: StatusInspector,
    refresh_context: RefreshContextFactory,
    build_plan: Callable[
        [list[str], ExecutionMode, Mapping[str, ToolStatus]], InstallPlan
    ],
    start_install: Callable[
        [
            InstallPlan,
            Mapping[str, ToolStatus],
            ExecutionChoices,
            Callable[[ExecutionEvent], None],
        ],
        Summary,
    ],
) -> UnifiedApp:
    return UnifiedApp(
        tools,
        statuses,
        {"pkg-mgr": "Package managers", "runtime": "Runtime managers and candidates"},
        report=DoctorReport((), (), ()),
        guard_status={"pip": False, "npm": False},
        guard_warning=None,
        fix_preview="No fixture PATH changes",
        fix=lambda: None,
        uninstall=UninstallInputs([], [], False, lambda _decision: None),
        policies=PolicyInputs([]),
        inspect_status=inspect_status,
        refresh_context=refresh_context,
        status_workers=1,
        start_install=start_install,
        build_plan=build_plan,
    )


async def test_catalog_sdkman_selection_lifecycle_is_responsive_and_sandboxed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr("installer.engine.is_installed", lambda _tool: False)

    all_tools = load_tools(REGISTRY)
    wanted = {"sdkman", "java", "gradle"}
    tools = [tool for tool in all_tools if tool.id in wanted]
    pending = {tool.id: _unknown(tool) for tool in tools}
    platform = Platform("fedora", "amd64", True, False)
    commands: list[list[str]] = []
    operation_status_ids: list[tuple[str, ...]] = []
    inspect_calls: list[tuple[str, bool]] = []
    startup_started = Event()
    release_startup = Event()
    post_started = Event()
    release_post = Event()

    def new_refresh_context() -> RefreshContext:
        return RefreshContext(
            platform=platform,
            probe=lambda _argv: pytest.fail("E2E status inspector must not probe"),
            health_runner=lambda _argv: pytest.fail(
                "E2E status inspector must not inspect health"
            ),
            update_runner=lambda _argv: pytest.fail(
                "E2E status inspector must not inspect updates"
            ),
            executable_resolver=lambda _command: None,
        )

    def inspect_status(
        tool: Tool,
        include_updates: bool,
        _context: RefreshContext,
    ) -> ToolStatus:
        inspect_calls.append((tool.id, include_updates))
        if len(inspect_calls) <= len(tools):
            startup_started.set()
            assert release_startup.wait(timeout=5), "test did not release startup enrichment"
        else:
            post_started.set()
            assert release_post.wait(timeout=5), "test did not release post-install refresh"
        return pending[tool.id]

    def build(
        selected_ids: list[str],
        mode: ExecutionMode,
        statuses: Mapping[str, ToolStatus],
    ) -> InstallPlan:
        return build_install_plan(
            selected_ids,
            tools,
            platform,
            statuses,
            execution_mode=mode,
        )

    def start(
        plan: InstallPlan,
        statuses: Mapping[str, ToolStatus],
        choices: ExecutionChoices,
        emit: Callable[[ExecutionEvent], None],
    ) -> Summary:
        operation_status_ids.append(tuple(statuses))
        return run_plan(
            plan,
            platform,
            emit,
            statuses,
            runner=commands.append,
            approved_actions=choices.approved_actions,
            verify_ownership=lambda tool, method: _sdkman_owner(
                str(method.params.get("candidate", tool.id))
            ),
        )

    app = _app(
        tools,
        pending,
        inspect_status,
        new_refresh_context,
        build,
        start,
    )
    try:
        async with app.run_test(size=(110, 34)) as pilot:
            assert app.current_view == "catalog"
            assert all(status.health == UNKNOWN_HEALTH for status in pending.values())
            assert startup_started.wait(timeout=5)

            await pilot.press("2", "1")
            assert app.current_view == "catalog"
            release_startup.set()
            await pilot.pause()

            app.catalog._browser.selected.update({"java", "gradle"})
            app.catalog._browser.refresh_items()
            app.catalog.post_message(app.catalog.Decided(["java", "gradle"]))
            await pilot.pause()
            install = app.screen
            assert isinstance(install, InstallScreen)
            assert install.plan is not None
            assert [entry.tool.id for entry in install.plan.entries] == [
                "sdkman", "java", "gradle"
            ]
            assert "dependency required by java" in install.plan_text

            await pilot.press("enter")
            await pilot.pause()
            assert install.finished is True
            assert post_started.is_set()
            assert operation_status_ids == [("sdkman", "java", "gradle")]
            candidate_commands = [command for command in commands if command[:1] == ["env"]]
            assert [command[-1] for command in candidate_commands] == ["java", "gradle"]
            assert app.catalog.selected == set()

            await pilot.press("2", "1")
            assert app.current_view == "catalog"
    finally:
        release_startup.set()
        release_post.set()
    assert list(home.iterdir()) == []
```

- [ ] **Step 2: Run the E2E test**

Run: `uv run pytest tests/test_catalog_sdkman_e2e.py -v`

Expected: PASS without invoking a real subprocess or touching the ambient home. The test fails if Tasks 1-8 leave an integration contract incomplete; fix the owning task rather than changing this test.

- [ ] **Step 3: Run the E2E and complete focused regression set**

Run: `uv run pytest tests/test_catalog_sdkman_e2e.py tests/test_registry.py tests/test_deps.py tests/test_ownership.py tests/test_engine.py tests/test_session.py tests/test_install_screen.py tests/test_wizard_app.py tests/test_setup.py -v`

Expected: PASS. The journey mounts with pending status, switches views during status work, reviews SDKMAN/Java/Gradle, executes two fake candidates, finishes before post-install refresh completes, clears Java/Gradle only, and leaves the temporary home empty.

- [ ] **Step 4: Run the full repository gates**

Run: `make validate && make test`

Expected: PASS with the new E2E included in coverage and no live host access.

- [ ] **Step 5: Commit the sandboxed journey**

```bash
git add tests/test_catalog_sdkman_e2e.py
git commit -m "test(e2e): cover SDKMAN catalog selection lifecycle" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 10: Run final registry, quality, and sandbox gates

**Files:**
- Verify only; no planned source changes.

**Interfaces:**
- Verifies: Plan 1 coordinator integration, Plan 2 ownership integration, all 69 tools, final 186 methods with the documented 198-method migration audit, SDKMAN candidate flow, complete review dispositions, selection lifecycle, README, and sandbox isolation.

- [ ] **Step 1: Scan the final registry counts and JVM exclusivity**

Run:

```bash
uv run python -c "from pathlib import Path; from installer.model import load_tools; tools=load_tools(Path('installer/registry.toml')); assert len(tools)==69; assert sum(len(t.methods) for t in tools)==186; assert all([m.kind for m in next(t for t in tools if t.id==i).methods]==['sdkman'] for i in ('java','gradle','maven','groovy','springbootcli')); print('69 tools, 186 final methods, five SDKMAN-exclusive JVM entries')"
```

Expected: prints `69 tools, 186 final methods, five SDKMAN-exclusive JVM entries` and exits 0.

- [ ] **Step 2: Run the complete focused feature suite**

Run: `uv run pytest tests/test_model.py tests/test_registry.py tests/test_resolve.py tests/test_deps.py tests/test_install_plan.py tests/test_app.py tests/test_catalog_tui.py tests/test_executors.py tests/test_ownership.py tests/test_engine.py tests/test_session.py tests/test_install_screen.py tests/test_wizard_app.py tests/test_setup.py tests/test_catalog_sdkman_e2e.py -v`

Expected: PASS with no skipped or xfailed tests.

- [ ] **Step 3: Run repository validation**

Run: `make validate`

Expected: PASS for Ruff check, Ruff format check, strict Pyright, Bandit, Vulture, ShellCheck, and every configured pre-commit hook.

- [ ] **Step 4: Run the complete test and coverage gate**

Run: `make test`

Expected: PASS for the complete pytest suite with coverage at or above the configured floor, no skipped tests introduced by this plan, and no access to the real home or live package managers.

- [ ] **Step 5: Inspect the implementation diff without committing**

Run: `git status --short && git diff --check`

Expected: only intended implementation, test, registry, README, and plan files are listed; `git diff --check` prints nothing. Do not create an additional gate-only commit.

## Self-Review Record

- Spec coverage: Tasks 1-2 cover contextual copy and the complete registry audit; Tasks 3-4 cover method-aware planning, current dispositions, manager/scope display, and direct-selection completeness; Tasks 5-6 cover SDKMAN execution, exclusive JVM migration, ownership verification, ordered Java/Gradle execution, and wrapper guidance; Task 7 covers current coordinator snapshots and every selection outcome; Task 8 covers README; Task 9 covers the sandboxed responsive E2E; Task 10 runs all gates.
- Predecessor boundary: the plan leaves Plan 1's coordinator implementation untouched and passes its final three-argument inspector plus context factory everywhere. It consumes Plan 2's reserved SDKMAN literals and structured ownership contracts, changes Plan 2's method package-field access where Task 1 promotes that metadata into `Method`, and owns all concrete SDKMAN candidate probing in Task 5.
- Audit arithmetic: the matrix covers the current 198 records; Task 6 removes 17 JVM native/Homebrew records and adds five candidate records, yielding 186.
- Placeholder scan: every code-changing task contains concrete tests, implementation blocks, commands, expected results, and a commit command. No implementation step delegates an unspecified behavior.
- Type consistency: `PlanDisposition`, `PlanEntry`, `InstallPlan.entries`, `method_for`, `BuildPlan`, `Summary.unavailable`, `Summary.blocked`, `VerifyMethodOwnership`, `StatusInspector`, `RefreshContextFactory`, `StatusKind`, `CatalogScreen.status_snapshot`, and `UnifiedApp.request_status_refresh` retain one spelling and signature throughout.
