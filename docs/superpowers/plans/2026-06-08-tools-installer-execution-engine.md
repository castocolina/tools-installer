# tools-installer — Install Execution Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the resolved priority-ladder into real installs: a status check, a userspace location policy, command-based executors (script / dnf / apt / pacman / brew), and an engine that walks the ladder until one method succeeds (soft-failing per tool).

**Architecture:** Executors are pure command *builders* that delegate side effects to an injected `Runner` (`Callable[[list[str]], None]` that raises on non-zero exit). This keeps every executor unit-testable by asserting the exact argv it produces — no subprocess, no sudo, no network. The engine resolves a tool's methods (Plan 1's `resolve_methods`), then tries each method's executor in order, stopping at the first that doesn't raise; if all fail it returns the collected errors instead of throwing. Download-based executors (`github_release`, `tarball`) are deliberately out of scope and land in Plan 3.

**Tech Stack:** Python ≥3.11, stdlib `subprocess`/`shutil`/`pathlib`; existing `installer.model`, `installer.platform`, `installer.resolve`; pytest with an injected fake runner.

This plan follows [`CLAUDE.md`](../../../CLAUDE.md) and [`.claude/`](../../../.claude/): never bypass a gate, coherent commits, English only. Each task ends green on `make validate && make test` (coverage ≥ 90%).

Builds on the Foundation plan (`2026-06-08-tools-installer-foundation.md`), which provides `Tool`, `Method`, `Platform`, and `resolve_methods`.

---

## Background the engineer needs

- A `Method` (from `installer/model.py`) has `.kind: str` and `.params: dict[str, object]`. Method params seen in this plan:
  - `script`: `url` (str), `shell` (str, e.g. `"sh"`/`"bash"`), optional `bin_dir` (str).
  - `dnf` / `apt` / `pacman`: `package` (str).
  - `brew`: `formula` (str).
- `resolve_methods(tool, platform) -> list[Method]` (from `installer/resolve.py`) already returns only platform-applicable methods in ladder order. The engine does NOT re-filter; it just executes in the given order.
- Param values are typed `object` (TOML is loosely typed). Executors must coerce to `str` explicitly and reject missing/empty values with a clear error — never pass `object` into a command list.

## File Structure

| File | Responsibility |
| ---- | -------------- |
| `installer/locations.py` | Userspace path policy: where binaries go, ensure-dir, PATH-prepend (process env) |
| `installer/run.py` | `Runner` type + the real subprocess runner; `CommandError` |
| `installer/executors.py` | One command-building executor per method kind, dispatched by kind |
| `installer/status.py` | `is_installed(tool)` — is the tool's `cmd` resolvable on PATH |
| `installer/engine.py` | `install_tool()` (walk ladder) and `InstallOutcome` result type |
| `tests/test_locations.py` | Location policy tests |
| `tests/test_run.py` | Runner + CommandError tests |
| `tests/test_executors.py` | Executor argv tests (injected fake runner) |
| `tests/test_status.py` | Status check tests |
| `tests/test_engine.py` | Engine orchestration tests (fake runner, simulated failures) |

---

### Task 1: Command runner abstraction

**Files:**
- Create: `installer/run.py`
- Test: `tests/test_run.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_run.py`:

```python
import subprocess

import pytest

from installer.run import CommandError, run_command


def test_run_command_success(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], check: bool):
        seen["cmd"] = cmd
        seen["check"] = check

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_command(["echo", "hi"])
    assert seen["cmd"] == ["echo", "hi"]
    assert seen["check"] is True


def test_run_command_raises_on_nonzero(monkeypatch: pytest.MonkeyPatch):
    def fake_run(cmd: list[str], check: bool):
        raise subprocess.CalledProcessError(returncode=2, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(CommandError) as exc:
        run_command(["false"])
    assert "false" in str(exc.value)
    assert exc.value.returncode == 2


def test_run_command_raises_when_binary_missing(monkeypatch: pytest.MonkeyPatch):
    def fake_run(cmd: list[str], check: bool):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(CommandError) as exc:
        run_command(["nope"])
    assert exc.value.returncode == 127
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_run.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.run'`.

- [ ] **Step 3: Implement `installer/run.py`**

```python
"""The command runner seam: executors build argv, the runner performs the side effect."""
import subprocess
from collections.abc import Callable

# An executor calls a Runner with an argv list. The runner raises CommandError on failure.
Runner = Callable[[list[str]], None]


class CommandError(RuntimeError):
    """A command exited non-zero (or could not be launched)."""

    def __init__(self, cmd: list[str], returncode: int) -> None:
        self.cmd = cmd
        self.returncode = returncode
        super().__init__(f"command failed ({returncode}): {' '.join(cmd)}")


def run_command(cmd: list[str]) -> None:
    """Real Runner: run argv, raise CommandError on non-zero exit."""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise CommandError(cmd, exc.returncode) from exc
    except OSError as exc:
        raise CommandError(cmd, 127) from exc
```

- [ ] **Step 4: Allow the subprocess seam in bandit (deliberate, documented)**

This is the first `subprocess` call in the codebase. bandit raises `B603`
(subprocess use) on it — `LOW` severity but enough to fail `make validate`. This is
an installer: shelling out to package managers is its purpose, and argv is built from
the trusted `registry.toml`, never from external input. Skip `B603` *as a reviewed
config decision* (never an inline `# nosec`).

Modify the `validate` target's bandit line in `Makefile`:

```makefile
validate:  ## Lint, format-check, type-check, security, dead-code
	uv run ruff check installer tests
	uv run ruff format --check installer tests
	uv run pyright
	# B603 (subprocess use) is inherent to this installer; argv comes from the
	# trusted registry, never external input. Reviewed and skipped deliberately.
	uv run bandit -q -r installer --skip B603
	uv run vulture
```

Update the matching hook in `.pre-commit-config.yaml`:

```yaml
      - id: bandit
        name: bandit
        entry: uv run bandit -q -r installer --skip B603
        language: system
        pass_filenames: false
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_run.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/run.py tests/test_run.py Makefile .pre-commit-config.yaml
git commit -m "$(printf 'feat: add command runner seam with CommandError\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Userspace location policy

**Files:**
- Create: `installer/locations.py`
- Test: `tests/test_locations.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_locations.py`:

```python
import os
from pathlib import Path

import pytest

from installer.locations import bin_dir, ensure_dir, prepend_path


def test_bin_dir_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert bin_dir(None) == tmp_path / ".local" / "bin"


def test_bin_dir_expands_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert bin_dir("~/.local/bin") == tmp_path / ".local" / "bin"


def test_ensure_dir_creates(tmp_path: Path):
    target = tmp_path / "a" / "b"
    result = ensure_dir(target)
    assert result == target
    assert target.is_dir()


def test_prepend_path_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PATH", "/usr/bin")
    prepend_path(tmp_path)
    prepend_path(tmp_path)  # second call must not duplicate
    parts = os.environ["PATH"].split(os.pathsep)
    assert parts[0] == str(tmp_path)
    assert parts.count(str(tmp_path)) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_locations.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.locations'`.

- [ ] **Step 3: Implement `installer/locations.py`**

```python
"""Userspace install-location policy: binaries land under ~/.local/bin, no sudo."""
import os
from pathlib import Path


def bin_dir(declared: str | None) -> Path:
    """Resolve a method's bin dir. Defaults to ~/.local/bin; expands a leading ~."""
    if declared:
        return Path(declared).expanduser()
    return Path.home() / ".local" / "bin"


def ensure_dir(directory: Path) -> Path:
    """Create the directory (and parents) if missing. Returns it."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def prepend_path(directory: Path) -> None:
    """Put `directory` first on the process PATH, without duplicating it."""
    entry = str(directory)
    parts = os.environ.get("PATH", "").split(os.pathsep)
    parts = [p for p in parts if p != entry]
    os.environ["PATH"] = os.pathsep.join([entry, *parts])
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_locations.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/locations.py tests/test_locations.py
git commit -m "$(printf 'feat: add userspace location policy\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Method executors (command builders)

**Files:**
- Create: `installer/executors.py`
- Test: `tests/test_executors.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_executors.py`:

```python
import pytest

from installer.executors import EXECUTORS, ExecutorError, execute
from installer.model import Method


def _record() -> tuple[list[list[str]], object]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    return calls, runner


def test_dnf_executor_builds_sudo_install():
    calls, runner = _record()
    execute(Method(kind="dnf", params={"package": "jq"}), runner)
    assert calls == [["sudo", "dnf", "install", "-y", "jq"]]


def test_apt_executor_builds_sudo_install():
    calls, runner = _record()
    execute(Method(kind="apt", params={"package": "jq"}), runner)
    assert calls == [["sudo", "apt-get", "install", "-y", "jq"]]


def test_pacman_executor_builds_sudo_install():
    calls, runner = _record()
    execute(Method(kind="pacman", params={"package": "jq"}), runner)
    assert calls == [["sudo", "pacman", "-S", "--noconfirm", "--needed", "jq"]]


def test_brew_executor_builds_install():
    calls, runner = _record()
    execute(Method(kind="brew", params={"formula": "jq"}), runner)
    assert calls == [["brew", "install", "jq"]]


def test_script_executor_pipes_curl_into_shell():
    calls, runner = _record()
    execute(
        Method(kind="script", params={"url": "https://astral.sh/uv/install.sh", "shell": "sh"}),
        runner,
    )
    assert calls == [["sh", "-c", "curl -fsSL https://astral.sh/uv/install.sh | sh"]]


def test_script_executor_defaults_shell_to_sh():
    calls, runner = _record()
    execute(Method(kind="script", params={"url": "https://example.com/i.sh"}), runner)
    assert calls == [["sh", "-c", "curl -fsSL https://example.com/i.sh | sh"]]


def test_missing_required_param_raises():
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="package"):
        execute(Method(kind="dnf", params={}), runner)
    assert calls == []


def test_unsupported_kind_raises():
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="github_release"):
        execute(Method(kind="github_release", params={"repo": "x/y"}), runner)


def test_every_command_kind_has_an_executor():
    for kind in ("script", "dnf", "apt", "pacman", "brew"):
        assert kind in EXECUTORS
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_executors.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.executors'`.

- [ ] **Step 3: Implement `installer/executors.py`**

```python
"""Per-method-kind executors: build an argv and hand it to the injected runner.

Only command-based kinds live here (script, native package managers, brew).
Download-based kinds (github_release, tarball) are implemented in a later plan.
"""
from collections.abc import Callable

from installer.model import Method
from installer.run import Runner


class ExecutorError(RuntimeError):
    """A method could not be turned into a runnable command."""


def _require(method: Method, key: str) -> str:
    value = method.params.get(key)
    if not isinstance(value, str) or not value:
        raise ExecutorError(f"method '{method.kind}' is missing required param '{key}'")
    return value


def _script(method: Method, runner: Runner) -> None:
    url = _require(method, "url")
    shell = method.params.get("shell")
    shell = shell if isinstance(shell, str) and shell else "sh"
    runner(["sh", "-c", f"curl -fsSL {url} | {shell}"])


def _dnf(method: Method, runner: Runner) -> None:
    runner(["sudo", "dnf", "install", "-y", _require(method, "package")])


def _apt(method: Method, runner: Runner) -> None:
    runner(["sudo", "apt-get", "install", "-y", _require(method, "package")])


def _pacman(method: Method, runner: Runner) -> None:
    runner(["sudo", "pacman", "-S", "--noconfirm", "--needed", _require(method, "package")])


def _brew(method: Method, runner: Runner) -> None:
    runner(["brew", "install", _require(method, "formula")])


EXECUTORS: dict[str, Callable[[Method, Runner], None]] = {
    "script": _script,
    "dnf": _dnf,
    "apt": _apt,
    "pacman": _pacman,
    "brew": _brew,
}


def execute(method: Method, runner: Runner) -> None:
    """Run the executor for `method.kind`, or raise ExecutorError if unsupported."""
    executor = EXECUTORS.get(method.kind)
    if executor is None:
        raise ExecutorError(f"no executor for method kind '{method.kind}'")
    executor(method, runner)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_executors.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/executors.py tests/test_executors.py
git commit -m "$(printf 'feat: add command-based method executors\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Status check

**Files:**
- Create: `installer/status.py`
- Test: `tests/test_status.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_status.py`:

```python
import pytest

from installer.model import Method, Tool
from installer.status import is_installed


def _tool(cmd: str) -> Tool:
    return Tool(
        id="t", name="t", category="c", cmd=cmd,
        methods=(Method(kind="brew", params={"formula": "t"}),),
    )


def test_is_installed_true_when_cmd_on_path(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", lambda cmd: "/usr/bin/jq" if cmd == "jq" else None)
    assert is_installed(_tool("jq")) is True


def test_is_installed_false_when_cmd_absent(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", lambda cmd: None)
    assert is_installed(_tool("jq")) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_status.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.status'`.

- [ ] **Step 3: Implement `installer/status.py`**

```python
"""Whether a tool is already installed, by resolving its command on PATH."""
import shutil

from installer.model import Tool


def is_installed(tool: Tool) -> bool:
    """True if the tool's command resolves on the current PATH."""
    return shutil.which(tool.cmd) is not None
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_status.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/status.py tests/test_status.py
git commit -m "$(printf 'feat: add tool status check\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Engine — walk the ladder

**Files:**
- Create: `installer/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_engine.py`:

```python
import pytest

from installer.engine import InstallOutcome, install_tool
from installer.executors import ExecutorError
from installer.model import Method, Tool
from installer.platform import Platform
from installer.run import CommandError


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def _tool(*methods: Method) -> Tool:
    return Tool(id="rg", name="ripgrep", category="search", cmd="rg", methods=methods)


def test_already_installed_short_circuits(monkeypatch: pytest.MonkeyPatch):
    import installer.engine as engine

    monkeypatch.setattr(engine, "is_installed", lambda tool: True)
    calls: list[list[str]] = []
    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=lambda cmd: calls.append(cmd),
    )
    assert outcome.status == "already-installed"
    assert outcome.method_kind is None
    assert calls == []


def test_first_method_succeeds(monkeypatch: pytest.MonkeyPatch):
    import installer.engine as engine

    monkeypatch.setattr(engine, "is_installed", lambda tool: False)
    calls: list[list[str]] = []
    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "ripgrep"}),
            Method(kind="brew", params={"formula": "ripgrep"}),
        ),
        _platform(),
        runner=lambda cmd: calls.append(cmd),
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "dnf"
    assert calls == [["sudo", "dnf", "install", "-y", "ripgrep"]]


def test_falls_through_to_next_method_on_failure(monkeypatch: pytest.MonkeyPatch):
    import installer.engine as engine

    monkeypatch.setattr(engine, "is_installed", lambda tool: False)
    attempted: list[str] = []

    def runner(cmd: list[str]) -> None:
        attempted.append(cmd[0])
        if cmd[0] == "sudo":
            raise CommandError(cmd, 1)
        # brew succeeds

    # Force both dnf and brew to be applicable on this platform.
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "ripgrep"}),
            Method(kind="brew", params={"formula": "ripgrep"}),
        ),
        platform,
        runner=runner,
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "brew"
    assert attempted == ["sudo", "brew"]


def test_no_applicable_methods(monkeypatch: pytest.MonkeyPatch):
    import installer.engine as engine

    monkeypatch.setattr(engine, "is_installed", lambda tool: False)
    # brew-only tool on a platform without brew -> resolver yields nothing.
    outcome = install_tool(
        _tool(Method(kind="brew", params={"formula": "ripgrep"})),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "no-method"
    assert outcome.method_kind is None


def test_all_methods_fail_returns_failed(monkeypatch: pytest.MonkeyPatch):
    import installer.engine as engine

    monkeypatch.setattr(engine, "is_installed", lambda tool: False)

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=runner,
    )
    assert outcome.status == "failed"
    assert outcome.method_kind is None
    assert len(outcome.errors) == 1


def test_executor_error_is_caught_as_failure(monkeypatch: pytest.MonkeyPatch):
    import installer.engine as engine

    monkeypatch.setattr(engine, "is_installed", lambda tool: False)
    # A resolved-but-unsupported kind (github_release) must be caught, not crash.
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    outcome = install_tool(
        _tool(Method(kind="github_release", params={"repo": "BurntSushi/ripgrep"})),
        platform,
        runner=lambda cmd: None,
    )
    assert outcome.status == "failed"
    assert isinstance(outcome.errors[0], ExecutorError)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_engine.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.engine'`.

- [ ] **Step 3: Implement `installer/engine.py`**

```python
"""Install a tool by walking its resolved priority ladder until one method works."""
from dataclasses import dataclass, field

from installer.executors import ExecutorError, execute
from installer.model import Tool
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner, run_command
from installer.status import is_installed


@dataclass(frozen=True)
class InstallOutcome:
    tool_id: str
    status: str                      # "already-installed" | "installed" | "no-method" | "failed"
    method_kind: str | None = None   # which method succeeded (if any)
    errors: list[Exception] = field(default_factory=list)


def install_tool(tool: Tool, platform: Platform, runner: Runner = run_command) -> InstallOutcome:
    """Try each applicable method in ladder order; stop at the first success."""
    if is_installed(tool):
        return InstallOutcome(tool.id, "already-installed")

    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, "no-method")

    errors: list[Exception] = []
    for method in methods:
        try:
            execute(method, runner)
            return InstallOutcome(tool.id, "installed", method_kind=method.kind)
        except (CommandError, ExecutorError) as exc:
            errors.append(exc)
    return InstallOutcome(tool.id, "failed", errors=errors)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_engine.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Full validate + coverage, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/engine.py tests/test_engine.py
git commit -m "$(printf 'feat: add install engine that walks the priority ladder\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Expected from `make test`: all tests pass, coverage ≥ 90%.

---

## Definition of Done (this plan)

- [ ] `make validate` passes (ruff, ruff format --check, pyright strict, bandit, vulture).
- [ ] `make test` passes with coverage ≥ 90%.
- [ ] `installer/` gains: `run_command`/`Runner`/`CommandError`, location policy, `execute`/`EXECUTORS`, `is_installed`, `install_tool`/`InstallOutcome`.
- [ ] An applicable command-based method installs; failures fall through to the next method; all-fail and no-method are reported, not raised.
- [ ] Five coherent commits, one per task.

## Known limitation (called out, not silently dropped)

`github_release` and `tarball` methods have NO executor yet — a tool whose only *resolved* method is download-based returns `status="failed"` with an `ExecutorError`. In the seeded registry, `uv` (script→brew) and `jq` (native→brew) install fully; `rg` installs via its native/brew fallbacks on every supported platform, and only its userspace-download path is deferred. The download executors are Plan 3.

## Follow-up plans (unchanged from Foundation plan)

3. **Download executors** — `github_release`/`tarball`: version resolution, asset templating, download + extract + chmod + symlink into `~/.local/bin`; macOS `~/Applications` for GUI apps.
4. **Interactive TUI** — `questionary` category navigation + spacebar multi-select; pre-flight audit; `setup.py` entrypoint.
5. **PATH doctor** — managed idempotent `~/.myshellrc`, `source` wiring, audit of missing/broken/duplicate bin dirs.
6. **`curl|bash` bootstrap & packaging** — `install.sh`; optional `brew-mac`/`brew-linux`; release/publish flow.
```
