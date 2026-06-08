# tools-installer — Foundation & Declarative Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `tools-installer` Python project (uv + make + quality gates) and the tested, declarative core: platform detection, the Tool/Method model loaded from `registry.toml`, and the install **priority-ladder resolver**.

**Architecture:** A pure-logic core with no I/O side effects, so every piece is unit-tested. `registry.toml` is the single source of truth; `model.py` loads it into frozen `Tool`/`Method` dataclasses; `platform.py` detects OS/arch/immutability; `resolve.py` turns a tool + platform into an ordered list of applicable install methods (the ladder: official `.sh` → userspace tarball → native package manager → brew). Install execution, the TUI, the PATH doctor, and the `curl|bash` bootstrap are separate follow-up plans that build on this core.

**Tech Stack:** Python ≥3.11, [uv](https://docs.astral.sh/uv/) (env + deps), `make` (task interface), `ruff` (lint + format), `pyright` (strict types), `bandit` (security), `vulture` (dead code), `pytest` + coverage. Runtime deps `rich` + `questionary` arrive in later plans.

This plan follows the rules in [`CLAUDE.md`](../../../CLAUDE.md) and [`.claude/`](../../../.claude/): never bypass a gate, coherent commits, English only. Each task ends green on `make validate && make test`.

---

## File Structure

| File | Responsibility |
| ---- | -------------- |
| `pyproject.toml` | Project metadata, deps, and ALL tool config (`[tool.*]`) |
| `Makefile` | Task interface: install, build, run, uninstall, validate, test |
| `.pre-commit-config.yaml` | Local hooks mirroring `make validate` |
| `installer/__init__.py` | Package marker |
| `installer/platform.py` | OS / arch / immutability detection → `Platform` |
| `installer/model.py` | `Tool` / `Method` dataclasses + `load_tools()` (tomllib) |
| `installer/registry.toml` | The catalog — single source of truth (seeded) |
| `installer/resolve.py` | Priority-ladder: `resolve_methods(tool, platform)` |
| `tests/__init__.py` | Test package marker |
| `tests/test_platform.py` | Platform detection tests |
| `tests/test_model.py` | Model + loader tests |
| `tests/test_registry.py` | Integration: the real registry parses & is well-formed |
| `tests/test_resolve.py` | Priority-ladder resolution tests |

---

### Task 1: Project scaffolding (pyproject + package skeleton)

**Files:**
- Create: `pyproject.toml`
- Create: `installer/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "tools-installer"
version = "0.1.0"
description = "Cross-platform interactive installer for an AI dev environment"
requires-python = ">=3.11"
dependencies = [
    "rich>=13",
    "questionary>=2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["installer"]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "pyright>=1.1.380",
    "ruff>=0.6",
    "bandit>=1.7",
    "vulture>=2.11",
    "pre-commit>=3.8",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.pyright]
include = ["installer", "tests"]
typeCheckingMode = "strict"
pythonVersion = "3.11"

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]

[tool.coverage.run]
source = ["installer"]
branch = true

[tool.coverage.report]
show_missing = true
fail_under = 90

[tool.vulture]
paths = ["installer"]
min_confidence = 80
```

- [ ] **Step 2: Create package markers**

`installer/__init__.py`:

```python
"""tools-installer: cross-platform installer for an AI dev environment."""
```

`tests/__init__.py`:

```python
```

- [ ] **Step 3: Sync the environment**

Run: `uv sync`
Expected: creates `.venv`, installs runtime + dev deps, writes `uv.lock`. No errors.

- [ ] **Step 4: Verify the package imports**

Run: `uv run python -c "import installer; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock installer/__init__.py tests/__init__.py
git commit -m "$(printf 'chore: scaffold uv project and package skeleton\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Make + pre-commit task interface

**Files:**
- Create: `Makefile`
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Write `Makefile`**

> Tabs, not spaces, for recipe lines.

```makefile
.DEFAULT_GOAL := help
.PHONY: help install build run uninstall validate test

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

install:  ## Create .venv and install runtime + dev deps (uv)
	uv sync

build:  ## Build the wheel + sdist
	uv build

run:  ## Launch the wizard (available once setup.py ships)
	uv run setup.py

uninstall:  ## Remove installed artifacts (implemented in a later plan)
	@echo "uninstall: not yet implemented"

validate:  ## Lint, format-check, type-check, security, dead-code
	uv run ruff check installer tests
	uv run ruff format --check installer tests
	uv run pyright
	uv run bandit -q -r installer
	uv run vulture

test:  ## Run tests with coverage
	uv run pytest --cov
```

- [ ] **Step 2: Write `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check
        language: system
        types: [python]
      - id: ruff-format
        name: ruff format --check
        entry: uv run ruff format --check
        language: system
        types: [python]
      - id: pyright
        name: pyright
        entry: uv run pyright
        language: system
        types: [python]
        pass_filenames: false
      - id: bandit
        name: bandit
        entry: uv run bandit -q -r installer
        language: system
        pass_filenames: false
      - id: vulture
        name: vulture
        entry: uv run vulture
        language: system
        pass_filenames: false
```

- [ ] **Step 3: Verify validate runs clean on the skeleton**

Run: `make validate`
Expected: all five tools run and pass (nothing to lint yet beyond the package docstring). Exit 0.

- [ ] **Step 4: Commit**

```bash
git add Makefile .pre-commit-config.yaml
git commit -m "$(printf 'chore: add make + pre-commit task interface\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Platform detection

**Files:**
- Create: `installer/platform.py`
- Test: `tests/test_platform.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_platform.py`:

```python
from pathlib import Path

import pytest

from installer.platform import (
    Platform,
    detect,
    detect_immutable,
    detect_os,
    normalize_arch,
)


def test_normalize_arch_known():
    assert normalize_arch("x86_64") == "amd64"
    assert normalize_arch("aarch64") == "arm64"


def test_normalize_arch_passthrough():
    assert normalize_arch("riscv64") == "riscv64"


def test_detect_os_macos():
    assert detect_os("Darwin", lambda cmd: False) == "macos"


def test_detect_os_fedora_via_dnf():
    assert detect_os("Linux", lambda cmd: cmd == "dnf") == "fedora"


def test_detect_os_fedora_via_rpm_ostree():
    assert detect_os("Linux", lambda cmd: cmd == "rpm-ostree") == "fedora"


def test_detect_os_debian():
    assert detect_os("Linux", lambda cmd: cmd == "apt-get") == "debian"


def test_detect_os_arch():
    assert detect_os("Linux", lambda cmd: cmd == "pacman") == "arch"


def test_detect_os_unsupported_raises():
    with pytest.raises(RuntimeError):
        detect_os("Linux", lambda cmd: False)


def test_detect_immutable_true(tmp_path: Path):
    marker = tmp_path / "ostree-booted"
    marker.write_text("")
    assert detect_immutable(marker) is True


def test_detect_immutable_false(tmp_path: Path):
    assert detect_immutable(tmp_path / "ostree-booted") is False


def test_detect_uses_live_probes(monkeypatch):
    import installer.platform as plat

    monkeypatch.setattr(plat._stdlib_platform, "system", lambda: "Linux")
    monkeypatch.setattr(plat._stdlib_platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        plat.shutil, "which",
        lambda cmd: "/usr/bin/x" if cmd in ("dnf", "brew") else None,
    )
    monkeypatch.setattr(plat, "detect_immutable", lambda: False)

    result = detect()
    assert isinstance(result, Platform)
    assert result.os == "fedora"
    assert result.arch == "amd64"
    assert result.has_brew is True
    assert result.immutable is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_platform.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.platform'`.

- [ ] **Step 3: Implement `installer/platform.py`**

```python
"""OS, architecture, and immutability detection for install-strategy selection."""
import platform as _stdlib_platform
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_ARCH_MAP = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}

_OSTREE_MARKER = Path("/run/ostree-booted")


@dataclass(frozen=True)
class Platform:
    os: str          # "debian" | "arch" | "fedora" | "macos"
    arch: str        # "amd64" | "arm64" | raw machine string
    immutable: bool  # atomic/ostree filesystem (Bazzite, Silverblue)
    has_brew: bool


def normalize_arch(machine: str) -> str:
    return _ARCH_MAP.get(machine, machine)


def detect_os(system: str, available: Callable[[str], bool]) -> str:
    """Map (platform.system(), command-availability) to a supported OS key.

    Fedora is probed before debian/arch because immutable Fedora (Bazzite) may
    expose rpm-ostree rather than a usable dnf.
    """
    if system == "Darwin":
        return "macos"
    if available("dnf") or available("rpm-ostree"):
        return "fedora"
    if available("apt-get"):
        return "debian"
    if available("pacman"):
        return "arch"
    raise RuntimeError(
        "Unsupported OS: need macOS, or one of dnf/rpm-ostree, apt-get, pacman"
    )


def detect_immutable(marker: Path = _OSTREE_MARKER) -> bool:
    """True on ostree/atomic systems, detected via the booted marker file."""
    return marker.exists()


def detect() -> Platform:
    """Detect the real platform using live system probes."""

    def available(cmd: str) -> bool:
        return shutil.which(cmd) is not None

    return Platform(
        os=detect_os(_stdlib_platform.system(), available),
        arch=normalize_arch(_stdlib_platform.machine()),
        immutable=detect_immutable(),
        has_brew=available("brew"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_platform.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/platform.py tests/test_platform.py
git commit -m "$(printf 'feat: add OS/arch/immutability detection\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Tool / Method model and loader

**Files:**
- Create: `installer/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_model.py`:

```python
from pathlib import Path

import pytest

from installer.model import Method, Tool, load_tools


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "registry.toml"
    p.write_text(content)
    return p


def test_load_single_tool_with_methods(tmp_path: Path):
    manifest = _write(
        tmp_path,
        '''
[[tool]]
id = "uv"
name = "uv"
category = "pkg-mgr"
cmd = "uv"
priority = "P0"
desc = "Python package manager"
[[tool.method]]
kind = "script"
url = "https://astral.sh/uv/install.sh"
shell = "sh"
[[tool.method]]
kind = "brew"
formula = "uv"
''',
    )
    tools = load_tools(manifest)
    assert len(tools) == 1
    tool = tools[0]
    assert isinstance(tool, Tool)
    assert tool.id == "uv"
    assert tool.priority == "P0"
    assert [m.kind for m in tool.methods] == ["script", "brew"]
    assert isinstance(tool.methods[0], Method)
    assert tool.methods[0].params["url"] == "https://astral.sh/uv/install.sh"


def test_cmd_defaults_to_id(tmp_path: Path):
    manifest = _write(
        tmp_path,
        '''
[[tool]]
id = "jq"
name = "jq"
category = "data"
[[tool.method]]
kind = "brew"
formula = "jq"
''',
    )
    tool = load_tools(manifest)[0]
    assert tool.cmd == "jq"
    assert tool.priority == "P3"  # default
    assert tool.audience == "both"  # default


def test_tool_without_methods_raises(tmp_path: Path):
    manifest = _write(
        tmp_path,
        '''
[[tool]]
id = "broken"
name = "broken"
category = "x"
''',
    )
    with pytest.raises(ValueError, match="no install methods"):
        load_tools(manifest)


def test_unknown_method_kind_raises(tmp_path: Path):
    manifest = _write(
        tmp_path,
        '''
[[tool]]
id = "weird"
name = "weird"
category = "x"
[[tool.method]]
kind = "snap"
package = "weird"
''',
    )
    with pytest.raises(ValueError, match="unknown method kind"):
        load_tools(manifest)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.model'`.

- [ ] **Step 3: Implement `installer/model.py`**

```python
"""Declarative tool catalog: Tool/Method model and tomllib loader."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

METHOD_KINDS = (
    "script",
    "github_release",
    "tarball",
    "dnf",
    "apt",
    "pacman",
    "rpm_ostree",
    "brew",
)


@dataclass(frozen=True)
class Method:
    kind: str
    params: dict[str, object] = field(default_factory=dict)


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


def load_tools(manifest_path: str | Path) -> list[Tool]:
    """Parse the registry TOML into validated Tool objects."""
    with open(manifest_path, "rb") as fh:
        data = tomllib.load(fh)
    tools: list[Tool] = []
    for row in data.get("tool", []):
        raw_methods = row.get("method", [])
        if not raw_methods:
            raise ValueError(f"tool '{row['id']}' declares no install methods")
        methods: list[Method] = []
        for entry in raw_methods:
            kind = entry["kind"]
            if kind not in METHOD_KINDS:
                raise ValueError(f"tool '{row['id']}': unknown method kind '{kind}'")
            params = {k: v for k, v in entry.items() if k != "kind"}
            methods.append(Method(kind=kind, params=params))
        tools.append(
            Tool(
                id=row["id"],
                name=row.get("name", row["id"]),
                category=row["category"],
                cmd=row.get("cmd", row["id"]),
                methods=tuple(methods),
                priority=row.get("priority", "P3"),
                audience=row.get("audience", "both"),
                desc=row.get("desc", ""),
            )
        )
    return tools
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_model.py -v`
Expected: PASS.

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/model.py tests/test_model.py
git commit -m "$(printf 'feat: add Tool/Method model and registry loader\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Seed the registry and assert it is well-formed

**Files:**
- Create: `installer/registry.toml`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_registry.py`:

```python
from pathlib import Path

from installer.model import load_tools

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def test_registry_loads():
    tools = load_tools(REGISTRY)
    assert tools, "registry should declare at least one tool"


def test_registry_ids_unique():
    ids = [t.id for t in load_tools(REGISTRY)]
    assert len(ids) == len(set(ids))


def test_every_tool_has_at_least_one_method():
    assert all(t.methods for t in load_tools(REGISTRY))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL — `FileNotFoundError` (registry.toml does not exist yet).

- [ ] **Step 3: Create `installer/registry.toml`**

> Seed catalog covering every method kind exercised by the resolver tests:
> a script-first tool (`uv`), a userspace+native+brew tool (`rg`), and a
> native+brew-only tool (`jq`).

```toml
# tools-installer registry — single declarative source of truth.
# Each [[tool]] declares one or more [[tool.method]] entries. The resolver
# (installer/resolve.py) filters them to the platform and orders them by the
# priority ladder: script -> userspace download -> native pkg manager -> brew.

[[tool]]
id = "uv"
name = "uv"
category = "pkg-mgr"
cmd = "uv"
priority = "P0"
audience = "both"
desc = "Fast Python package and venv manager"
[[tool.method]]
kind = "script"
url = "https://astral.sh/uv/install.sh"
shell = "sh"
bin_dir = "~/.local/bin"
[[tool.method]]
kind = "brew"
formula = "uv"

[[tool]]
id = "rg"
name = "ripgrep"
category = "search"
cmd = "rg"
priority = "P0"
audience = "ai"
desc = "Fast recursive search; respects .gitignore"
[[tool.method]]
kind = "github_release"
repo = "BurntSushi/ripgrep"
asset = "ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "rg"
bin_dir = "~/.local/bin"
[[tool.method]]
kind = "dnf"
package = "ripgrep"
[[tool.method]]
kind = "apt"
package = "ripgrep"
[[tool.method]]
kind = "pacman"
package = "ripgrep"
[[tool.method]]
kind = "brew"
formula = "ripgrep"

[[tool]]
id = "jq"
name = "jq"
category = "data"
cmd = "jq"
priority = "P0"
audience = "ai"
desc = "Surgical queries and edits on JSON"
[[tool.method]]
kind = "dnf"
package = "jq"
[[tool.method]]
kind = "apt"
package = "jq"
[[tool.method]]
kind = "pacman"
package = "jq"
[[tool.method]]
kind = "brew"
formula = "jq"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Validate and commit**

```bash
make validate && make test
git add installer/registry.toml tests/test_registry.py
git commit -m "$(printf 'feat: seed registry with uv, ripgrep, jq\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: Priority-ladder resolver

**Files:**
- Create: `installer/resolve.py`
- Test: `tests/test_resolve.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_resolve.py`:

```python
from installer.model import Method, Tool
from installer.platform import Platform
from installer.resolve import resolve_methods


def _tool(*kinds: str) -> Tool:
    return Tool(
        id="t",
        name="t",
        category="c",
        cmd="t",
        methods=tuple(Method(kind=k) for k in kinds),
    )


def test_macos_prefers_script_then_brew():
    platform = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    tool = _tool("script", "brew", "apt")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["script", "brew"]


def test_userspace_before_native():
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    tool = _tool("dnf", "github_release")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["github_release", "dnf"]


def test_native_filtered_to_matching_os():
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    tool = _tool("dnf", "apt", "pacman")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["apt"]


def test_immutable_skips_native():
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    tool = _tool("github_release", "dnf")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["github_release"]


def test_rpm_ostree_skipped_by_default():
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    tool = _tool("github_release", "rpm_ostree")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["github_release"]


def test_brew_requires_brew_present():
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    tool = _tool("brew")
    assert resolve_methods(tool, platform) == []


def test_immutable_no_brew_native_only_returns_empty():
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    tool = _tool("dnf", "brew")
    assert resolve_methods(tool, platform) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resolve.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.resolve'`.

- [ ] **Step 3: Implement `installer/resolve.py`**

```python
"""Resolve which install methods apply to a platform, ordered by the priority ladder."""
from installer.model import Method, Tool
from installer.platform import Platform

# Lower rank is tried first. The default ladder:
#   1) official script  2) userspace download  3) native pkg manager  4) brew
_RANK = {
    "script": 10,
    "github_release": 20,
    "tarball": 20,
    "dnf": 30,
    "apt": 30,
    "pacman": 30,
    "rpm_ostree": 35,
    "brew": 40,
}

# Which OS each native package manager belongs to.
_NATIVE_OS = {
    "dnf": "fedora",
    "apt": "debian",
    "pacman": "arch",
}


def _applies(method: Method, platform: Platform) -> bool:
    kind = method.kind
    if kind in ("script", "github_release", "tarball"):
        return True
    if kind == "brew":
        return platform.has_brew
    if kind == "rpm_ostree":
        # Native installer for immutable Fedora, but skipped by default: it
        # requires a reboot and breaks atomicity. Userspace/brew are preferred.
        return False
    # Remaining kinds are native package managers (dnf/apt/pacman).
    if platform.immutable:
        return False  # skip the native step on immutable distros
    return _NATIVE_OS[kind] == platform.os


def resolve_methods(tool: Tool, platform: Platform) -> list[Method]:
    """Return the tool's platform-applicable methods, ordered by the priority ladder."""
    applicable = [m for m in tool.methods if _applies(m, platform)]
    return sorted(applicable, key=lambda m: _RANK[m.kind])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_resolve.py -v`
Expected: PASS.

- [ ] **Step 5: Full validate + coverage, then commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/resolve.py tests/test_resolve.py
git commit -m "$(printf 'feat: add priority-ladder install resolver\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Expected from `make test`: all tests pass and coverage ≥ 90% (the `fail_under` gate holds).

---

## Definition of Done (this plan)

- [ ] `make validate` passes (ruff, ruff format --check, pyright strict, bandit, vulture).
- [ ] `make test` passes with coverage ≥ 90%.
- [ ] `uv build` produces a wheel (`make build`).
- [ ] `installer/` exposes a tested core: `detect()`/`Platform`, `load_tools()`/`Tool`/`Method`, `resolve_methods()`.
- [ ] Six coherent commits, one per task (Task 1 may be one or two).

## Follow-up plans (not in scope here)

1. **Install strategies & execution engine** — one executor per method kind (`script`, `github_release`, native, `brew`), userspace location policy (`~/.local`, `~/Applications`), symlink-into-PATH, dependency ordering, idempotent re-runs, soft-fail-and-continue.
2. **Interactive TUI** — `questionary` category navigation + spacebar multi-select; pre-flight audit table (`rich`); `setup.py` entrypoint wiring `make run`.
3. **PATH doctor** — managed idempotent `~/.myshellrc`, `source` wiring into `.zshrc`/`.bashrc` without duplicates, audit of missing/broken/duplicate bin dirs.
4. **`curl|bash` bootstrap & packaging** — `install.sh` (detect OS/arch → ensure `uv` via Astral → fetch repo → run wizard); optional `brew-mac`/`brew-linux` registry entries; release/publish flow.
```
