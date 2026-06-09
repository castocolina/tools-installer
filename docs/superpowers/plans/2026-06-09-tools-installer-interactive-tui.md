# tools-installer — Interactive TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing install engine into an interactive wizard — pick categories, multi-select tools (missing ones pre-checked), see a pre-flight audit, confirm, install in priority order, and get a result summary — plus non-interactive flags (`--all`, `--categories`, `--yes`) for CI, all wired through `setup.py` so `make run` launches it.

**Architecture:** A pure, fully-testable core in `installer/` (selection/audit/session/cli/render/prompt/app), and one thin composition root `setup.py` that performs real terminal IO. Selection logic speaks in plain `Choice` dataclasses (never `questionary` objects); `rich` renders to an injected `Console` (tests point it at a `StringIO`, no TTY); the prompter is a `Protocol` driven by injected callbacks. `questionary` is imported **only** by `setup.py` — keeping the strict-typed, 100%-covered package free of untyped terminal IO.

**Tech Stack:** Python ≥3.11, stdlib `argparse`/`io`; `rich` (tables/summary, rendered to an injected Console); `questionary` (isolated in `setup.py`); existing `installer.model`, `installer.platform`, `installer.status`, `installer.run`, `installer.engine`, `installer.versions`.

This plan follows [`CLAUDE.md`](../../../CLAUDE.md) and [`.claude/`](../../../.claude/): never bypass a gate, coherent commits, English only. Each task ends green on `make validate && make test` (coverage ≥ 90%). Builds on the Foundation, Execution-Engine, and Download-Executors plans.

---

## Background the engineer needs

- **Existing surfaces this plan calls (do not change them):**
  - `installer/model.py`: `Tool(id, name, category, cmd, methods, priority="P3", audience="both", desc="")` frozen; `load_tools(manifest_path) -> list[Tool]`.
  - `installer/platform.py`: `Platform(os, arch, immutable, has_brew)` frozen; `detect() -> Platform`.
  - `installer/status.py`: `is_installed(tool: Tool) -> bool` (resolves `tool.cmd` on PATH).
  - `installer/run.py`: `Runner = Callable[[list[str]], None]`, `run_command`.
  - `installer/engine.py`: `install_tool(tool, platform, runner=run_command, resolve_version=resolve_github_version) -> InstallOutcome`; `InstallOutcome(tool_id, status, method_kind=None, errors=())` with `status` ∈ `{"already-installed","installed","no-method","failed"}`.
  - `installer/versions.py`: `VersionResolver = Callable[[str], str]`, `resolve_github_version`.
  - `installer/registry.toml`: the seeded catalog (uv, rg, jq) loaded via `load_tools`.
- **Strict-typing rules that have repeatedly bitten this repo** — follow them or `make validate` fails:
  - Do **NOT** add `from __future__ import annotations`.
  - Annotate every test fixture: `monkeypatch: pytest.MonkeyPatch`, `tmp_path: Path`, `capsys`, etc.
  - Prefer a typed `def` over a bare `lambda` in an `Any`/loosely-typed context. A `lambda` inside `sorted(list_of_known_type, key=...)` is fine (the element type is inferred) — `resolve.py` already does this.
  - `field(default_factory=dict/list)` can infer `Unknown`; use a typed factory function (`model.py._empty_params` is the pattern). For tuple fields, a literal default `()` is fine.
- **Coverage discipline:** `[tool.coverage.run] source = ["installer"]`, `branch = true`, `fail_under = 90`. Everything you put under `installer/` is measured. Keep all branchy logic there and test it. `setup.py` lives at the **repo root**, so it is *not* measured, *not* in the pyright `include`, and *not* in vulture `paths` — it is the deliberate, documented composition boundary where the untyped `questionary` IO lives. Do not move terminal IO into `installer/`.
- **`rich` is unit-testable without a TTY:** construct `Console(file=buf, width=100)` where `buf = io.StringIO()`, render into it, then assert on `buf.getvalue()`. Hold your own `StringIO` reference in the test; do not read it back off the `Console`.
- **`questionary` is NOT imported anywhere under `installer/`.** The prompter abstraction takes injected callbacks; only `setup.py` binds them to real `questionary` calls.

## File Structure

| File | Responsibility |
| ---- | -------------- |
| `installer/audit.py` | `ToolStatus` + `audit(tools, is_installed)` — per-tool installed/missing (pure, injected check) |
| `installer/selection.py` | `Choice`; `categories`/`tools_in`; `category_choices`/`tool_choices`; `select_tools` — catalog → choices → tools (pure) |
| `installer/session.py` | `Summary`; `order_for_install`; `run_installs`; `summarize` — orchestrate installs + bucket outcomes (pure, injected install) |
| `installer/cli.py` | `Options`; `parse_args(argv)` — non-interactive flags (pure) |
| `installer/render.py` | `render_audit`/`render_summary` — `rich` rendering into an injected `Console` |
| `installer/prompt.py` | `Prompter` Protocol; `CallbackPrompter` — questionary-agnostic prompting via injected callbacks |
| `installer/app.py` | `run_wizard(...)` — the wizard flow tying selection→audit→confirm→install→summary together (pure, everything injected) |
| `setup.py` | Composition root: real `detect()`, real `Console`, questionary-backed prompter, registry load, arg parse, exit code. Wires `make run`. |
| `tests/test_audit.py`, `tests/test_selection.py`, `tests/test_session.py`, `tests/test_cli.py`, `tests/test_render.py`, `tests/test_prompt.py`, `tests/test_app.py` | unit tests per module |

The dependency direction is one-way: `app` → {`selection`, `audit`, `session`, `render`, `prompt`, `cli`} → {existing engine/model/...}. No module under `installer/` imports `questionary`.

---

### Task 1: Per-tool audit (installed / missing)

**Files:**
- Create: `installer/audit.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_audit.py`:

```python
from installer.audit import ToolStatus, audit
from installer.model import Method, Tool


def _tool(tool_id: str, cmd: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=cmd,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
    )


def test_audit_marks_each_tool_installed_or_missing():
    tools = [_tool("rg", "rg"), _tool("jq", "jq")]
    present = {"rg"}

    def installed(tool: Tool) -> bool:
        return tool.cmd in present

    result = audit(tools, installed)
    assert result == [
        ToolStatus(tool=tools[0], installed=True),
        ToolStatus(tool=tools[1], installed=False),
    ]


def test_audit_preserves_order_and_handles_empty():
    assert audit([], lambda tool: True) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_audit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.audit'`.

- [ ] **Step 3: Implement `installer/audit.py`**

```python
"""Per-tool installed/missing status, computed from an injected check."""
from collections.abc import Callable
from dataclasses import dataclass

from installer.model import Tool
from installer.status import is_installed


@dataclass(frozen=True)
class ToolStatus:
    tool: Tool
    installed: bool


def audit(tools: list[Tool], is_installed: Callable[[Tool], bool] = is_installed) -> list[ToolStatus]:
    """Return each tool paired with whether it is already installed, in order."""
    return [ToolStatus(tool=tool, installed=is_installed(tool)) for tool in tools]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_audit.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/audit.py tests/test_audit.py
git commit -m "$(printf 'feat: add per-tool installed/missing audit\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

> Note: the second test passes a bare `lambda tool: True` as the injected check. That is acceptable here because `audit`'s parameter is typed `Callable[[Tool], bool]`, so pyright infers the lambda's parameter type from the call site — no `Any` context. If pyright still complains, replace it with a local `def always(tool: Tool) -> bool: return True`.

---

### Task 2: Catalog → selectable choices

**Files:**
- Create: `installer/selection.py`
- Test: `tests/test_selection.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_selection.py`:

```python
from installer.audit import ToolStatus
from installer.model import Method, Tool
from installer.selection import (
    Choice,
    categories,
    category_choices,
    select_tools,
    tool_choices,
    tools_in,
)


def _tool(tool_id: str, category: str, desc: str = "") -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        desc=desc,
    )


def test_categories_are_unique_in_first_seen_order():
    tools = [_tool("rg", "search"), _tool("jq", "data"), _tool("fd", "search")]
    assert categories(tools) == ["search", "data"]


def test_tools_in_filters_by_category():
    tools = [_tool("rg", "search"), _tool("jq", "data"), _tool("fd", "search")]
    assert [t.id for t in tools_in(tools, "search")] == ["rg", "fd"]


def test_category_choices_count_tools_and_start_unchecked():
    tools = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    assert category_choices(tools) == [
        Choice(id="search", label="search (2 tools)", checked=False),
        Choice(id="data", label="data (1 tool)", checked=False),
    ]


def test_tool_choices_precheck_missing_only():
    tools = [_tool("rg", "search", desc="fast grep"), _tool("fd", "search")]
    statuses = [
        ToolStatus(tool=tools[0], installed=True),
        ToolStatus(tool=tools[1], installed=False),
    ]
    assert tool_choices(statuses) == [
        Choice(id="rg", label="rg — fast grep (installed)", checked=False),
        Choice(id="fd", label="fd (missing)", checked=True),
    ]


def test_select_tools_keeps_catalog_order_and_ignores_unknown_ids():
    tools = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    assert [t.id for t in select_tools(tools, ["jq", "rg", "ghost"])] == ["rg", "jq"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_selection.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.selection'`.

- [ ] **Step 3: Implement `installer/selection.py`**

```python
"""Turn the tool catalog and audit into selectable choices, and back to tools."""
from dataclasses import dataclass

from installer.audit import ToolStatus
from installer.model import Tool


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    checked: bool


def categories(tools: list[Tool]) -> list[str]:
    """Distinct categories in first-seen order."""
    seen: list[str] = []
    for tool in tools:
        if tool.category not in seen:
            seen.append(tool.category)
    return seen


def tools_in(tools: list[Tool], category: str) -> list[Tool]:
    """Tools belonging to one category, in catalog order."""
    return [tool for tool in tools if tool.category == category]


def category_choices(tools: list[Tool]) -> list[Choice]:
    """One unchecked choice per category, labelled with its tool count."""
    choices: list[Choice] = []
    for category in categories(tools):
        count = len(tools_in(tools, category))
        unit = "tool" if count == 1 else "tools"
        choices.append(Choice(id=category, label=f"{category} ({count} {unit})", checked=False))
    return choices


def tool_choices(statuses: list[ToolStatus]) -> list[Choice]:
    """One choice per tool; missing tools are pre-checked, installed ones are not."""
    choices: list[Choice] = []
    for status in statuses:
        tool = status.tool
        head = f"{tool.id} — {tool.desc}" if tool.desc else tool.id
        state = "installed" if status.installed else "missing"
        choices.append(Choice(id=tool.id, label=f"{head} ({state})", checked=not status.installed))
    return choices


def select_tools(tools: list[Tool], ids: list[str]) -> list[Tool]:
    """Tools whose id was selected, in catalog order; unknown ids are ignored."""
    wanted = set(ids)
    return [tool for tool in tools if tool.id in wanted]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_selection.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/selection.py tests/test_selection.py
git commit -m "$(printf 'feat: build selectable choices from the tool catalog\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Install session — order, run, summarize

**Files:**
- Create: `installer/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_session.py`:

```python
from installer.engine import InstallOutcome
from installer.model import Method, Tool
from installer.platform import Platform
from installer.session import Summary, order_for_install, run_installs, summarize


def _tool(tool_id: str, priority: str = "P3") -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority=priority,
    )


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)


def test_order_for_install_sorts_by_priority_then_keeps_catalog_order():
    tools = [_tool("a", "P3"), _tool("b", "P0"), _tool("c", "P3"), _tool("d", "P1")]
    assert [t.id for t in order_for_install(tools)] == ["b", "d", "a", "c"]


def test_run_installs_calls_install_per_tool_with_injected_deps():
    tools = [_tool("rg"), _tool("jq")]
    platform = _platform()
    seen: list[tuple[str, str]] = []

    def fake_install(tool: Tool, plat: Platform, runner: object, resolve_version: object) -> InstallOutcome:
        seen.append((tool.id, plat.os))
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    def runner(cmd: list[str]) -> None:
        return None

    def resolve_version(repo: str) -> str:
        return "1.0.0"

    outcomes = run_installs(tools, platform, runner, resolve_version, fake_install)
    assert seen == [("rg", "fedora"), ("jq", "fedora")]
    assert [o.tool_id for o in outcomes] == ["rg", "jq"]


def test_summarize_buckets_by_status():
    outcomes = [
        InstallOutcome("rg", "installed"),
        InstallOutcome("jq", "already-installed"),
        InstallOutcome("fd", "failed"),
        InstallOutcome("bat", "no-method"),
        InstallOutcome("uv", "installed"),
    ]
    assert summarize(outcomes) == Summary(
        installed=("rg", "uv"),
        already=("jq",),
        failed=("fd",),
        no_method=("bat",),
    )


def test_summarize_empty_is_all_empty():
    assert summarize([]) == Summary(installed=(), already=(), failed=(), no_method=())
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_session.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.session'`.

- [ ] **Step 3: Implement `installer/session.py`**

```python
"""Orchestrate installs for a selection of tools and bucket the outcomes."""
from collections.abc import Callable
from dataclasses import dataclass

from installer.engine import InstallOutcome, install_tool
from installer.model import Tool
from installer.platform import Platform
from installer.run import Runner, run_command
from installer.versions import VersionResolver, resolve_github_version

# (tool, platform, runner, resolve_version) -> outcome. Matches engine.install_tool.
Install = Callable[[Tool, Platform, Runner, VersionResolver], InstallOutcome]

_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass(frozen=True)
class Summary:
    installed: tuple[str, ...]
    already: tuple[str, ...]
    failed: tuple[str, ...]
    no_method: tuple[str, ...]


def order_for_install(tools: list[Tool]) -> list[Tool]:
    """Stable sort by priority (P0 first); ties keep catalog order."""
    return sorted(tools, key=lambda tool: _PRIORITY_RANK.get(tool.priority, 99))


def run_installs(
    tools: list[Tool],
    platform: Platform,
    runner: Runner = run_command,
    resolve_version: VersionResolver = resolve_github_version,
    install: Install = install_tool,
) -> list[InstallOutcome]:
    """Install each tool in turn, collecting one outcome per tool."""
    return [install(tool, platform, runner, resolve_version) for tool in tools]


def summarize(outcomes: list[InstallOutcome]) -> Summary:
    """Bucket outcome tool ids by status."""
    buckets: dict[str, list[str]] = {
        "installed": [],
        "already-installed": [],
        "failed": [],
        "no-method": [],
    }
    for outcome in outcomes:
        buckets[outcome.status].append(outcome.tool_id)
    return Summary(
        installed=tuple(buckets["installed"]),
        already=tuple(buckets["already-installed"]),
        failed=tuple(buckets["failed"]),
        no_method=tuple(buckets["no-method"]),
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_session.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/session.py tests/test_session.py
git commit -m "$(printf 'feat: add install session ordering, run, and summary\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

> Note on the `Install` type and the default `install_tool`: `install_tool` has `runner`/`resolve_version` as keyword params with defaults, which is assignable to `Callable[[Tool, Platform, Runner, VersionResolver], InstallOutcome]` (extra defaults are allowed when fewer/positional args are supplied). `run_installs` calls `install(tool, platform, runner, resolve_version)` positionally, which matches both the real engine and the test fake.

---

### Task 4: Non-interactive CLI flags

**Files:**
- Create: `installer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_cli.py`:

```python
import pytest

from installer.cli import Options, parse_args


def test_defaults_are_interactive():
    assert parse_args([]) == Options(all=False, categories=(), yes=False)


def test_all_flag():
    assert parse_args(["--all"]) == Options(all=True, categories=(), yes=False)


def test_categories_split_and_trimmed():
    opts = parse_args(["--categories", "search, data , git"])
    assert opts.categories == ("search", "data", "git")


def test_categories_repeatable():
    opts = parse_args(["--categories", "search", "--categories", "data"])
    assert opts.categories == ("search", "data")


def test_yes_flag():
    assert parse_args(["--yes"]).yes is True


def test_unknown_flag_exits():
    with pytest.raises(SystemExit):
        parse_args(["--nope"])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.cli'`.

- [ ] **Step 3: Implement `installer/cli.py`**

```python
"""Parse non-interactive CLI flags into an Options value."""
import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Options:
    all: bool
    categories: tuple[str, ...]
    yes: bool


def parse_args(argv: list[str]) -> Options:
    """Parse argv (excluding program name) into Options; exits on bad input."""
    parser = argparse.ArgumentParser(
        prog="tools-installer",
        description="Interactively install an AI dev environment.",
    )
    parser.add_argument("--all", action="store_true", help="select every tool, no prompts")
    parser.add_argument(
        "--categories",
        action="append",
        default=[],
        metavar="A,B",
        help="install only these categories (comma-separated; repeatable)",
    )
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ns = parser.parse_args(argv)

    categories: list[str] = []
    raw_groups: list[str] = ns.categories
    for group in raw_groups:
        for name in group.split(","):
            trimmed = name.strip()
            if trimmed:
                categories.append(trimmed)
    return Options(all=ns.all, categories=tuple(categories), yes=ns.yes)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/cli.py tests/test_cli.py
git commit -m "$(printf 'feat: parse non-interactive CLI flags\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

> Note: `argparse` namespace attributes are dynamically typed. Annotating `raw_groups: list[str] = ns.categories` before iterating gives pyright a concrete type and keeps strict mode happy without a cast. Do the same (`ns.all`, `ns.yes` are `bool` from `store_true`) only if pyright complains.

---

### Task 5: Rich rendering of audit and summary

**Files:**
- Create: `installer/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_render.py`:

```python
import io

from rich.console import Console

from installer.audit import ToolStatus
from installer.model import Method, Tool
from installer.render import render_audit, render_summary
from installer.session import Summary


def _tool(tool_id: str, category: str = "search") -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
    )


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=100, no_color=True), buf


def test_render_audit_lists_each_tool_and_its_state():
    statuses = [
        ToolStatus(tool=_tool("rg"), installed=True),
        ToolStatus(tool=_tool("fd"), installed=False),
    ]
    console, buf = _console()
    render_audit(statuses, console)
    out = buf.getvalue()
    assert "rg" in out and "fd" in out
    assert "installed" in out and "missing" in out


def test_render_summary_reports_counts_and_ids():
    summary = Summary(installed=("rg",), already=("jq",), failed=("fd",), no_method=())
    console, buf = _console()
    render_summary(summary, console)
    out = buf.getvalue()
    assert "Installed: 1" in out
    assert "rg" in out and "jq" in out and "fd" in out


def test_render_summary_handles_empty():
    console, buf = _console()
    render_summary(Summary(installed=(), already=(), failed=(), no_method=()), console)
    out = buf.getvalue()
    assert "Installed: 0" in out
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_render.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.render'`.

- [ ] **Step 3: Implement `installer/render.py`**

```python
"""Render the pre-flight audit and the post-install summary to a Console."""
from rich.console import Console
from rich.table import Table

from installer.audit import ToolStatus
from installer.session import Summary


def render_audit(statuses: list[ToolStatus], console: Console) -> None:
    """Print a table of each selected tool, its category, and installed/missing."""
    table = Table(title="Pre-flight audit")
    table.add_column("Tool")
    table.add_column("Category")
    table.add_column("State")
    for status in statuses:
        state = "installed" if status.installed else "missing"
        table.add_row(status.tool.id, status.tool.category, state)
    console.print(table)


def render_summary(summary: Summary, console: Console) -> None:
    """Print install counts and the tool ids in each bucket."""
    console.print(
        f"Installed: {len(summary.installed)}  "
        f"Already: {len(summary.already)}  "
        f"Failed: {len(summary.failed)}  "
        f"No method: {len(summary.no_method)}"
    )
    for label, ids in (
        ("installed", summary.installed),
        ("already installed", summary.already),
        ("failed", summary.failed),
        ("no method", summary.no_method),
    ):
        if ids:
            console.print(f"  {label}: {', '.join(ids)}")
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_render.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/render.py tests/test_render.py
git commit -m "$(printf 'feat: render audit table and install summary with rich\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

> Note: `Console(file=buf, width=100, no_color=True)` makes rendering deterministic and strips ANSI codes so substring assertions are stable. A wide table can wrap/truncate long cells — keep assertions to short tokens (`"rg"`, `"missing"`), not full lines.

---

### Task 6: Prompter abstraction (questionary-agnostic)

**Files:**
- Create: `installer/prompt.py`
- Test: `tests/test_prompt.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_prompt.py`:

```python
from installer.prompt import CallbackPrompter, Prompter
from installer.selection import Choice


def test_callback_prompter_is_a_prompter():
    prompter: Prompter = CallbackPrompter(
        ask_checkbox=lambda message, choices: [],
        ask_confirm=lambda message: True,
    )
    assert isinstance(prompter, CallbackPrompter)


def test_select_categories_forwards_choices_and_returns_ids():
    seen: list[tuple[str, list[Choice]]] = []

    def ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
        seen.append((message, choices))
        return ["search"]

    def ask_confirm(message: str) -> bool:
        return True

    prompter = CallbackPrompter(ask_checkbox=ask_checkbox, ask_confirm=ask_confirm)
    choices = [Choice(id="search", label="search (2 tools)", checked=False)]
    assert prompter.select_categories(choices) == ["search"]
    assert seen[0][1] == choices


def test_select_tools_forwards_choices():
    captured: list[list[Choice]] = []

    def ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
        captured.append(choices)
        return ["rg"]

    prompter = CallbackPrompter(ask_checkbox=ask_checkbox, ask_confirm=lambda message: False)
    choices = [Choice(id="rg", label="rg (missing)", checked=True)]
    assert prompter.select_tools(choices) == ["rg"]
    assert captured[0] == choices


def test_confirm_forwards_message():
    seen: list[str] = []

    def ask_confirm(message: str) -> bool:
        seen.append(message)
        return True

    prompter = CallbackPrompter(ask_checkbox=lambda message, choices: [], ask_confirm=ask_confirm)
    assert prompter.confirm("Proceed?") is True
    assert seen == ["Proceed?"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_prompt.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.prompt'`.

- [ ] **Step 3: Implement `installer/prompt.py`**

```python
"""Prompting abstraction. Pure: real terminal IO is injected as callbacks."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from installer.selection import Choice

# Show a multi-select of `choices` under `message`; return the chosen ids.
AskCheckbox = Callable[[str, list[Choice]], list[str]]
# Ask a yes/no question; return the answer.
AskConfirm = Callable[[str], bool]


class Prompter(Protocol):
    def select_categories(self, choices: list[Choice]) -> list[str]: ...
    def select_tools(self, choices: list[Choice]) -> list[str]: ...
    def confirm(self, message: str) -> bool: ...


@dataclass(frozen=True)
class CallbackPrompter:
    ask_checkbox: AskCheckbox
    ask_confirm: AskConfirm

    def select_categories(self, choices: list[Choice]) -> list[str]:
        return self.ask_checkbox("Select categories", choices)

    def select_tools(self, choices: list[Choice]) -> list[str]:
        return self.ask_checkbox("Select tools", choices)

    def confirm(self, message: str) -> bool:
        return self.ask_confirm(message)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_prompt.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/prompt.py tests/test_prompt.py
git commit -m "$(printf 'feat: add questionary-agnostic prompter abstraction\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

> Note: the bare lambdas in the tests sit in parameters typed `AskCheckbox`/`AskConfirm`, so pyright infers their signatures — acceptable. The `Prompter` Protocol's methods are *used* (called in `app.py`, Task 7, and exercised through `CallbackPrompter` here), so vulture will not flag them. Do not add `# type: ignore`/vulture ignores.

---

### Task 7: The wizard flow

**Files:**
- Create: `installer/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_app.py`:

```python
import io

from rich.console import Console

from installer.app import run_wizard
from installer.cli import Options
from installer.engine import InstallOutcome
from installer.model import Method, Tool
from installer.platform import Platform
from installer.selection import Choice
from installer.session import Install, Summary


def _tool(tool_id: str, category: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
    )


def _catalog() -> list[Tool]:
    return [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=100, no_color=True), buf


class FakePrompter:
    def __init__(self, categories: list[str], tools: list[str], confirm: bool) -> None:
        self._categories = categories
        self._tools = tools
        self._confirm = confirm
        self.confirmed = 0

    def select_categories(self, choices: list[Choice]) -> list[str]:
        return self._categories

    def select_tools(self, choices: list[Choice]) -> list[str]:
        return self._tools

    def confirm(self, message: str) -> bool:
        self.confirmed += 1
        return self._confirm


def _recording_install() -> tuple[list[str], Install]:
    installed: list[str] = []

    def install(tool: Tool, platform: Platform, runner: object, resolve_version: object) -> InstallOutcome:
        installed.append(tool.id)
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    return installed, install


def _never_installed(tool: Tool) -> bool:
    return False


def _runner(cmd: list[str]) -> None:
    return None


def _resolve(repo: str) -> str:
    return "1.0.0"


def test_all_flag_installs_every_tool_without_prompting():
    installed, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_version=_resolve,
        install=install,
        installed=_never_installed,
    )
    assert installed == ["rg", "fd", "jq"]
    assert summary == Summary(installed=("rg", "fd", "jq"), already=(), failed=(), no_method=())
    assert prompter.confirmed == 0


def test_categories_flag_filters_tools():
    installed, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=("data",), yes=True),
        runner=_runner,
        resolve_version=_resolve,
        install=install,
        installed=_never_installed,
    )
    assert installed == ["jq"]


def test_interactive_path_selects_then_installs():
    installed, install = _recording_install()
    prompter = FakePrompter(categories=["search"], tools=["fd"], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=(), yes=False),
        runner=_runner,
        resolve_version=_resolve,
        install=install,
        installed=_never_installed,
    )
    assert installed == ["fd"]
    assert summary.installed == ("fd",)
    assert prompter.confirmed == 1


def test_declining_confirmation_installs_nothing():
    installed, install = _recording_install()
    prompter = FakePrompter(categories=["search"], tools=["fd"], confirm=False)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=(), yes=False),
        runner=_runner,
        resolve_version=_resolve,
        install=install,
        installed=_never_installed,
    )
    assert installed == []
    assert summary == Summary(installed=(), already=(), failed=(), no_method=())
    assert prompter.confirmed == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_app.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.app'`.

- [ ] **Step 3: Implement `installer/app.py`**

```python
"""The interactive wizard flow: select -> audit -> confirm -> install -> summarize."""
from collections.abc import Callable

from rich.console import Console

from installer.audit import audit
from installer.cli import Options
from installer.engine import install_tool
from installer.model import Tool
from installer.platform import Platform
from installer.prompt import Prompter
from installer.render import render_audit, render_summary
from installer.run import Runner, run_command
from installer.selection import category_choices, select_tools, tool_choices
from installer.session import Install, Summary, order_for_install, run_installs, summarize
from installer.status import is_installed
from installer.versions import VersionResolver, resolve_github_version


def _choose_tools(
    tools: list[Tool],
    prompter: Prompter,
    options: Options,
    installed: Callable[[Tool], bool],
) -> list[Tool]:
    if options.all:
        return tools
    if options.categories:
        return [tool for tool in tools if tool.category in options.categories]
    chosen_categories = prompter.select_categories(category_choices(tools))
    wanted = set(chosen_categories)
    in_categories = [tool for tool in tools if tool.category in wanted]
    statuses = audit(in_categories, installed)
    chosen_ids = prompter.select_tools(tool_choices(statuses))
    return select_tools(in_categories, chosen_ids)


def run_wizard(
    tools: list[Tool],
    platform: Platform,
    prompter: Prompter,
    console: Console,
    options: Options,
    runner: Runner = run_command,
    resolve_version: VersionResolver = resolve_github_version,
    install: Install = install_tool,
    installed: Callable[[Tool], bool] = is_installed,
) -> Summary:
    """Drive the full wizard and return the install summary (empty if declined)."""
    selected = _choose_tools(tools, prompter, options, installed)
    statuses = audit(selected, installed)
    render_audit(statuses, console)
    if not options.yes and not prompter.confirm("Install the selected tools?"):
        return summarize([])
    ordered = order_for_install(selected)
    outcomes = run_installs(ordered, platform, runner, resolve_version, install)
    summary = summarize(outcomes)
    render_summary(summary, console)
    return summary
```

The `tools_in` helper is intentionally *not* imported — `_choose_tools` filters inline by category membership, so importing `tools_in` would be unused (vulture would flag it). Only import what you use.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_app.py -q`
Expected: PASS (4 tests). Note `FakePrompter` structurally satisfies the `Prompter` Protocol, so passing it is type-correct.

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/app.py tests/test_app.py
git commit -m "$(printf 'feat: add the interactive wizard flow\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

> Note: every parameter of `run_wizard` has a real default except the injected data, so `setup.py` (Task 8) can call `run_wizard(tools, platform, prompter, console, options)` and let the engine defaults apply in production, while tests override `runner`/`resolve_version`/`install`/`installed` with fakes. This is the same injection seam used throughout the codebase.

---

### Task 8: Composition root — `setup.py`

**Files:**
- Create: `setup.py` (repo root)
- (No new test file — `setup.py` is the composition boundary: outside `installer/`, so outside coverage source, the pyright `include`, and vulture `paths`. It contains only wiring and the one untyped `questionary` boundary. It is validated manually via `make run`.)

- [ ] **Step 1: Implement `setup.py`**

```python
"""Entry point for the tools-installer wizard. Run via `make run` (uv run setup.py).

This is the composition root: it performs the real terminal IO (questionary)
and wires the pure, fully-tested installer package together. It deliberately
lives outside the `installer/` package so the untyped questionary boundary is
isolated from the strict-typed, fully-covered core.
"""
import sys
from pathlib import Path

import questionary
from rich.console import Console

from installer.app import run_wizard
from installer.cli import parse_args
from installer.model import load_tools
from installer.platform import detect
from installer.prompt import CallbackPrompter
from installer.selection import Choice

_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"


def _ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
    answer = questionary.checkbox(
        message,
        choices=[questionary.Choice(title=c.label, value=c.id, checked=c.checked) for c in choices],
    ).ask()
    return list(answer) if answer else []


def _ask_confirm(message: str) -> bool:
    return bool(questionary.confirm(message, default=True).ask())


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    console = Console()
    interactive = options.all or bool(options.categories) or sys.stdin.isatty()
    if not interactive:
        console.print(
            "No TTY detected. Re-run with --all or --categories A,B (and --yes) for "
            "non-interactive use."
        )
        return 2
    tools = load_tools(_REGISTRY)
    prompter = CallbackPrompter(ask_checkbox=_ask_checkbox, ask_confirm=_ask_confirm)
    summary = run_wizard(tools, detect(), prompter, console, options)
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 2: Verify `make run` launches and exits cleanly in non-interactive mode**

Run: `printf '' | uv run setup.py`
Expected: prints the "No TTY detected" guidance and exits with code 2 (stdin is not a TTY when piped, and no flags were given). Verify the exit code:

```bash
printf '' | uv run setup.py; echo "exit=$?"
```
Expected: `exit=2`.

- [ ] **Step 3: Verify `--all` runs end-to-end against the seeded registry (real installs)**

This actually installs the seeded tools via the real engine, so run it only where that is acceptable (or skip on CI). It exercises the full wiring:

Run: `uv run setup.py --all --yes`
Expected: prints the pre-flight audit table and an install summary; exit code 0 unless a tool failed. (On a machine that already has `uv`/`rg`/`jq`, the summary shows them under "already installed".)

- [ ] **Step 4: Confirm gates are unaffected**

`setup.py` is outside `installer/`, so it does not change coverage, pyright `include`, or vulture `paths`. Confirm the suite is still green:

Run: `make validate && make test`
Expected: all pass, coverage ≥ 90% (unchanged by `setup.py`).

- [ ] **Step 5: Commit**

```bash
uv run ruff format installer tests setup.py
git add setup.py
git commit -m "$(printf 'feat: wire the wizard entry point for make run\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

> Note: `ruff` still formats/lints `setup.py` (it is passed explicitly and is not excluded from ruff), so keep it clean. `questionary` has no type stubs, which is exactly why it is confined to `setup.py` (outside the pyright `include`); never import it under `installer/`. If you later want `setup.py` type-checked, add stubs or a typed wrapper — do not weaken the strict config.

---

## Definition of Done (this plan)

- [ ] `make validate` passes (ruff, ruff format --check, pyright strict, bandit, vulture).
- [ ] `make test` passes with coverage ≥ 90% (the `installer/` additions should keep it at 100%).
- [ ] `make run` (`uv run setup.py`) launches the wizard; piping empty stdin with no flags prints guidance and exits 2.
- [ ] Interactive flow: select categories → select tools (missing pre-checked) → pre-flight audit table → confirm → ordered install → summary.
- [ ] Non-interactive flags work: `--all` installs everything with no prompts; `--categories search,data` filters; `--yes` skips confirmation.
- [ ] Installs run in priority order (P0 first), reusing `engine.install_tool` unchanged.
- [ ] No module under `installer/` imports `questionary`; `rich` output is rendered through an injected `Console`.
- [ ] Eight coherent commits (one per task).

## Known limitations (called out, not silently dropped)

- **PATH doctor / `~/.myshellrc` is NOT in this plan.** After installing, tools land in their `bin_dir` (e.g. `~/.local/bin`) but the wizard does not yet ensure that dir is on PATH or wire `source ~/.myshellrc`. That is **Plan 5**. Until then the summary may list a tool as "installed" that is not yet on `PATH` in a fresh shell — acceptable for this slice.
- **`curl | bash` bootstrap is NOT in this plan** (it is **Plan 6**). This plan assumes the repo is already cloned and `uv` is present (`make run`).
- **Root menu modes** beyond install (PATH doctor / Shell guards / Version sync / AI plugins) and **audience filtering** are out of scope; the MVP is the category→tool install flow plus flags.
- **Network degradation UX** (GitHub rate-limit warnings) is handled at the engine level (a failed version lookup is recorded as `failed` in the summary, never crashes) — no extra UI for it here.

## Follow-up plans (remaining roadmap)

5. **PATH doctor** — managed idempotent `~/.myshellrc`, `source` wiring into `.zshrc`/`.bashrc` without duplicates, audit of missing/broken/duplicate bin dirs; a `--doctor` flag and standalone subcommand.
6. **`curl|bash` bootstrap & packaging** — `install.sh` (detect OS/arch → ensure uv → fetch repo → run wizard); optional `brew-mac`/`brew-linux` registry entries; macOS GUI/`.app` install; release/publish flow.
