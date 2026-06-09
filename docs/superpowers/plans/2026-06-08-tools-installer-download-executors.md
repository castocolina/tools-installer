# tools-installer — Download Executors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install tools that ship as release archives or raw binaries — `github_release` (version-resolved GitHub asset) and `tarball` (direct URL) — by downloading into a userspace bin dir, all driven through the existing injected `Runner` so it stays fully unit-testable.

**Architecture:** Three pure/injectable pieces — asset-name templating (`assets.py`), GitHub version resolution (`versions.py`, network injected), and the download executors (`download.py`) — plus a tiny `ExecContext` that carries `runner + platform + resolve_version`. The engine routes each resolved method to the command executors (Plan 2, unchanged) or the download executors by kind. Download/extract/chmod are modeled as `Runner` commands (`sh -c "curl … | tar …"`, `chmod +x …`), so tests assert the exact argv without touching the network or real binaries; only `ensure_dir` does real (harmless, tmp-scoped) filesystem work.

**Tech Stack:** Python ≥3.11, stdlib `urllib`/`json`/`shlex`; existing `installer.model`, `installer.platform`, `installer.resolve`, `installer.executors`, `installer.locations`, `installer.run`, `installer.engine`.

This plan follows [`CLAUDE.md`](../../../CLAUDE.md) and [`.claude/`](../../../.claude/): never bypass a gate, coherent commits, English only. Each task ends green on `make validate && make test` (coverage ≥ 90%). Builds on the Foundation and Execution-Engine plans.

---

## Background the engineer needs

- `Method.params` is `dict[str, object]` (loosely typed TOML). Always coerce: a shared `require_str(method, key) -> str` (Task 3 makes it public on `installer.executors`) raises `ExecutorError` for missing/empty/non-str values.
- The seeded `rg` tool already declares a `github_release` method: `repo="BurntSushi/ripgrep"`, `asset="ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz"`, `member="rg"`, `bin_dir="~/.local/bin"`.
- `Platform.arch` is the normalized `"amd64"`/`"arm64"`. Release assets need other spellings (`x86_64`, `aarch64`, …) — `assets.arch_tokens` maps normalized → an `ArchTokens` object whose attributes feed `{arch.machine}` etc. in templates.
- The only real subprocess call site remains `installer/run.py`. Download executors only BUILD argv and call `ctx.runner`. Do not import `subprocess` in the new modules.
- `make validate` runs bandit with `--skip B404,B603` (set in Plan 2). Task 2 adds `B310` (urllib audit) with rationale — a deliberate, documented config decision, never an inline `# nosec`.

## File Structure

| File | Responsibility |
| ---- | -------------- |
| `installer/assets.py` | `ArchTokens`, `arch_tokens(normalized)`, `render_asset(template, ver, arch)` — pure |
| `installer/versions.py` | `VersionResolver` type, `resolve_github_version(repo, fetch)` — network injected |
| `installer/executors.py` | (modified) rename `_require` → public `require_str` |
| `installer/download.py` | `ExecContext`, `DOWNLOAD_KINDS`, `install_download(method, ctx)` |
| `installer/engine.py` | (modified) route command vs download kinds; `install_tool` gains `resolve_version` |
| `tests/test_assets.py` | templating + arch token tests |
| `tests/test_versions.py` | version resolution tests (fake fetch + monkeypatched urlopen) |
| `tests/test_download.py` | download executor command-sequence tests |
| `tests/test_engine.py` | (modified) add download routing tests; replace the stale github_release case |

---

### Task 1: Asset templating + arch tokens

**Files:**
- Create: `installer/assets.py`
- Test: `tests/test_assets.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_assets.py`:

```python
import pytest

from installer.assets import ArchTokens, arch_tokens, render_asset


def test_arch_tokens_amd64():
    tokens = arch_tokens("amd64")
    assert isinstance(tokens, ArchTokens)
    assert tokens.machine == "x86_64"
    assert tokens.deb == "amd64"
    assert tokens.go == "amd64"


def test_arch_tokens_arm64():
    tokens = arch_tokens("arm64")
    assert tokens.machine == "aarch64"
    assert tokens.deb == "arm64"


def test_arch_tokens_unsupported_raises():
    with pytest.raises(ValueError, match="unsupported architecture"):
        arch_tokens("riscv64")


def test_render_asset_substitutes_ver_and_arch():
    out = render_asset("rg-{ver}-{arch.machine}-linux.tar.gz", "14.1.0", arch_tokens("amd64"))
    assert out == "rg-14.1.0-x86_64-linux.tar.gz"


def test_render_asset_supports_ver_only():
    assert render_asset("tool-{ver}.tgz", "1.2.3", arch_tokens("arm64")) == "tool-1.2.3.tgz"


def test_render_asset_bad_placeholder_raises():
    with pytest.raises(ValueError, match="bad asset template"):
        render_asset("rg-{nope}.tar.gz", "1.0", arch_tokens("amd64"))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_assets.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.assets'`.

- [ ] **Step 3: Implement `installer/assets.py`**

```python
"""GitHub-release asset-name templating and architecture token mapping."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ArchTokens:
    machine: str  # x86_64 | aarch64
    deb: str      # amd64 | arm64
    go: str       # amd64 | arm64
    suffix: str   # x86_64 | arm64


_TOKENS = {
    "amd64": ArchTokens(machine="x86_64", deb="amd64", go="amd64", suffix="x86_64"),
    "arm64": ArchTokens(machine="aarch64", deb="arm64", go="arm64", suffix="arm64"),
}


def arch_tokens(normalized: str) -> ArchTokens:
    """Map a normalized arch (amd64/arm64) to release-asset token variants."""
    tokens = _TOKENS.get(normalized)
    if tokens is None:
        raise ValueError(f"unsupported architecture for downloads: {normalized}")
    return tokens


def render_asset(template: str, ver: str, arch: ArchTokens) -> str:
    """Render an asset filename: supports {ver} and {arch.machine|deb|go|suffix}."""
    try:
        return template.format(ver=ver, arch=arch)
    except (KeyError, IndexError, AttributeError) as exc:
        raise ValueError(f"bad asset template '{template}': {exc}") from exc
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_assets.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/assets.py tests/test_assets.py
git commit -m "$(printf 'feat: add release-asset templating and arch tokens\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: GitHub version resolution

**Files:**
- Create: `installer/versions.py`
- Modify: `Makefile` (bandit skip), `.pre-commit-config.yaml` (bandit hook)
- Test: `tests/test_versions.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_versions.py`:

```python
import pytest

from installer.versions import resolve_github_version


def test_resolve_strips_leading_v():
    def fetch(url: str) -> bytes:
        assert url == "https://api.github.com/repos/BurntSushi/ripgrep/releases/latest"
        return b'{"tag_name": "v14.1.0"}'

    assert resolve_github_version("BurntSushi/ripgrep", fetch) == "14.1.0"


def test_resolve_without_v_prefix():
    def fetch(url: str) -> bytes:
        return b'{"tag_name": "1.2.3"}'

    assert resolve_github_version("a/b", fetch) == "1.2.3"


def test_resolve_missing_tag_raises():
    def fetch(url: str) -> bytes:
        return b"{}"

    with pytest.raises(ValueError, match="no release tag"):
        resolve_github_version("a/b", fetch)


def test_urlopen_fetch_reads_body(monkeypatch: pytest.MonkeyPatch):
    import installer.versions as versions

    class FakeResp:
        def __enter__(self) -> "FakeResp":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b'{"tag_name": "v9.9.9"}'

    def fake_urlopen(url: str, timeout: int) -> FakeResp:
        return FakeResp()

    monkeypatch.setattr(versions.urllib.request, "urlopen", fake_urlopen)
    assert versions._urlopen_fetch("https://example.com") == b'{"tag_name": "v9.9.9"}'
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_versions.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.versions'`.

- [ ] **Step 3: Implement `installer/versions.py`**

```python
"""Resolve the latest release version of a GitHub repository."""
import json
import urllib.request
from collections.abc import Callable

# Resolve a repo ("owner/name") to its latest version string (no leading 'v').
VersionResolver = Callable[[str], str]

# Fetch raw bytes at a URL. Injected in tests; defaults to urllib.
Fetch = Callable[[str], bytes]


def _urlopen_fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read()


def resolve_github_version(repo: str, fetch: Fetch = _urlopen_fetch) -> str:
    """Return the latest release tag for owner/repo, without a leading 'v'."""
    raw = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
    data = json.loads(raw)
    tag = str(data.get("tag_name", ""))
    if not tag:
        raise ValueError(f"no release tag for {repo}")
    return tag.lstrip("v")
```

- [ ] **Step 4: Add bandit B310 skip (deliberate, documented)**

`_urlopen_fetch` calls `urllib.request.urlopen` with a constructed (non-literal) URL, which bandit flags as `B310` (audit url open for permitted schemes). The URL is always an `https://api.github.com/...` string built from a registry-controlled repo name — not user input. Skip `B310` as a reviewed config decision (never inline `# nosec`).

Edit the bandit line in the `Makefile` `validate` target so the skip list and comment read:

```makefile
	# B404/B603 (subprocess) and B310 (urlopen) are inherent to this installer; all
	# args/URLs come from the trusted registry, never external input. Skipped deliberately.
	uv run bandit -q -r installer --skip B404,B603,B310
```

And update the bandit hook `entry` in `.pre-commit-config.yaml` to:
`entry: uv run bandit -q -r installer --skip B404,B603,B310`

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_versions.py -q`
Expected: PASS (4 tests).

- [ ] **Step 6: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/versions.py tests/test_versions.py Makefile .pre-commit-config.yaml
git commit -m "$(printf 'feat: add GitHub release version resolution\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Make the param-coercion helper public (refactor)

**Files:**
- Modify: `installer/executors.py`

This is a small refactor so `download.py` can reuse the param coercion without importing a private name. The existing `tests/test_executors.py` is the regression guard — no new test.

- [ ] **Step 1: Confirm current tests pass (baseline)**

Run: `uv run pytest tests/test_executors.py -q`
Expected: PASS (current count).

- [ ] **Step 2: Rename `_require` → `require_str` in `installer/executors.py`**

Change the helper definition and ALL five call sites. The function becomes:

```python
def require_str(method: Method, key: str) -> str:
    value = method.params.get(key)
    if not isinstance(value, str) or not value:
        raise ExecutorError(f"method '{method.kind}' is missing or empty required param '{key}'")
    return value
```

Update the five executors to call `require_str(...)` instead of `_require(...)`:
- `_script`: `url = require_str(method, "url")`
- `_dnf`: `runner(["sudo", "dnf", "install", "-y", require_str(method, "package")])`
- `_apt`: `runner(["sudo", "apt-get", "install", "-y", require_str(method, "package")])`
- `_pacman`: `runner(["sudo", "pacman", "-S", "--noconfirm", "--needed", require_str(method, "package")])`
- `_brew`: `runner(["brew", "install", require_str(method, "formula")])`

(No other changes. The error message text is unchanged, so `test_missing_required_param_raises` still matches.)

- [ ] **Step 3: Verify tests still pass**

Run: `uv run pytest tests/test_executors.py -q`
Expected: PASS (same count as Step 1).

- [ ] **Step 4: Validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/executors.py
git commit -m "$(printf 'refactor: expose require_str for reuse by download executors\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Download executors (github_release + tarball)

**Files:**
- Create: `installer/download.py`
- Test: `tests/test_download.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_download.py`:

```python
from pathlib import Path

import pytest

from installer.download import DOWNLOAD_KINDS, ExecContext, install_download
from installer.executors import ExecutorError
from installer.model import Method
from installer.platform import Platform
from installer.run import Runner


def _ctx(runner: Runner, tmp_version: str = "14.1.0") -> ExecContext:
    def resolve_version(repo: str) -> str:
        return tmp_version

    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    return ExecContext(runner=runner, platform=platform, resolve_version=resolve_version)


def _record() -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    return calls, runner


def test_download_kinds_constant():
    assert set(DOWNLOAD_KINDS) == {"github_release", "tarball"}


def test_github_release_archive_downloads_and_chmods(tmp_path: Path):
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz",
            "member": "rg",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner))
    url = (
        "https://github.com/BurntSushi/ripgrep/releases/download/"
        "v14.1.0/ripgrep-14.1.0-x86_64-unknown-linux-musl.tar.gz"
    )
    target = bin_dir / "rg"
    assert calls == [
        ["sh", "-c", f"curl -fsSL -- {url} | tar -xz -C {bin_dir} -- rg"],
        ["chmod", "+x", str(target)],
    ]
    assert bin_dir.is_dir()  # ensure_dir ran


def test_github_release_raw_downloads_binary_directly(tmp_path: Path):
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "mikefarah/yq",
            "asset": "yq_linux_{arch.deb}",
            "member": "yq",
            "raw": True,
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner))
    target = bin_dir / "yq"
    url = "https://github.com/mikefarah/yq/releases/download/v14.1.0/yq_linux_amd64"
    assert calls == [
        ["sh", "-c", f"curl -fsSL -o {target} -- {url}"],
        ["chmod", "+x", str(target)],
    ]


def test_tarball_uses_direct_url(tmp_path: Path):
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="tarball",
        params={
            "url": "https://example.com/tool.tar.gz",
            "member": "tool",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner))
    target = bin_dir / "tool"
    assert calls == [
        ["sh", "-c", f"curl -fsSL -- https://example.com/tool.tar.gz | tar -xz -C {bin_dir} -- tool"],
        ["chmod", "+x", str(target)],
    ]


def test_unsupported_kind_raises(tmp_path: Path):
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="brew"):
        install_download(Method(kind="brew", params={"formula": "x"}), _ctx(runner))
    assert calls == []


def test_missing_required_param_raises(tmp_path: Path):
    calls, runner = _record()
    method = Method(kind="tarball", params={"url": "https://x/y.tgz"})  # no member
    with pytest.raises(ExecutorError, match="member"):
        install_download(method, _ctx(runner))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_download.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.download'`.

- [ ] **Step 3: Implement `installer/download.py`**

```python
"""Download-based executors: github_release and tarball binaries into a bin dir."""
import shlex
from dataclasses import dataclass

from installer.assets import arch_tokens, render_asset
from installer.executors import ExecutorError, require_str
from installer.locations import bin_dir, ensure_dir
from installer.model import Method
from installer.platform import Platform
from installer.run import Runner
from installer.versions import VersionResolver

DOWNLOAD_KINDS = ("github_release", "tarball")


@dataclass(frozen=True)
class ExecContext:
    runner: Runner
    platform: Platform
    resolve_version: VersionResolver


def _opt_str(method: Method, key: str) -> str | None:
    value = method.params.get(key)
    return value if isinstance(value, str) and value else None


def _github_release_url(method: Method, ctx: ExecContext) -> str:
    repo = require_str(method, "repo")
    template = require_str(method, "asset")
    ver = ctx.resolve_version(repo)
    asset = render_asset(template, ver, arch_tokens(ctx.platform.arch))
    return f"https://github.com/{repo}/releases/download/v{ver}/{asset}"


def install_download(method: Method, ctx: ExecContext) -> None:
    """Download a release archive/binary into the bin dir and make it executable."""
    if method.kind == "github_release":
        url = _github_release_url(method, ctx)
    elif method.kind == "tarball":
        url = require_str(method, "url")
    else:
        raise ExecutorError(f"no download executor for kind '{method.kind}'")

    member = require_str(method, "member")
    dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    target = dest / member
    quoted_url = shlex.quote(url)
    if method.params.get("raw") is True:
        ctx.runner(["sh", "-c", f"curl -fsSL -o {shlex.quote(str(target))} -- {quoted_url}"])
    else:
        ctx.runner(
            ["sh", "-c", f"curl -fsSL -- {quoted_url} | tar -xz -C {shlex.quote(str(dest))} -- {shlex.quote(member)}"]
        )
    ctx.runner(["chmod", "+x", str(target)])
```

> Note: the test argvs above contain no shell-special characters, so `shlex.quote` leaves the URLs/paths unquoted (only the `--` separators appear). The quoting still protects against accidental metacharacters in registry values.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_download.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/download.py tests/test_download.py
git commit -m "$(printf 'feat: add github_release and tarball download executors\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Route download kinds in the engine

**Files:**
- Modify: `installer/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Update the failing tests first**

In `tests/test_engine.py`, change the imports at the top to add `Path`, the download `ExecContext` is NOT needed, but you need a fake resolver and tmp paths. Replace the existing `test_executor_error_is_caught_as_failure` test with the two tests below, and add the needed imports.

Add to the imports block at the top of `tests/test_engine.py`:

```python
from pathlib import Path
```

DELETE this existing test entirely:

```python
def test_executor_error_is_caught_as_failure(monkeypatch: pytest.MonkeyPatch):
    import installer.engine as engine

    monkeypatch.setattr(engine, "is_installed", lambda tool: False)
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    outcome = install_tool(
        _tool(Method(kind="github_release", params={"repo": "BurntSushi/ripgrep"})),
        platform,
        runner=lambda cmd: None,
    )
    assert outcome.status == "failed"
    assert isinstance(outcome.errors[0], ExecutorError)
```

ADD these two tests in its place:

```python
def test_github_release_routes_to_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    calls: list[list[str]] = []
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "rg-{ver}-{arch.machine}.tar.gz",
            "member": "rg",
            "bin_dir": str(bin_dir),
        },
    )

    def resolve_version(repo: str) -> str:
        return "1.2.3"

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    outcome = install_tool(
        _tool(method),
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=runner,
        resolve_version=resolve_version,
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "github_release"
    assert calls[0][0] == "sh" and "rg-1.2.3-x86_64.tar.gz" in calls[0][2]
    assert calls[1] == ["chmod", "+x", str(bin_dir / "rg")]


def test_download_failure_is_caught_as_failed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    def resolve_version(repo: str) -> str:
        return "1.2.3"

    method = Method(
        kind="github_release",
        params={
            "repo": "x/y",
            "asset": "x-{ver}.tar.gz",
            "member": "x",
            "bin_dir": str(tmp_path / "bin"),
        },
    )
    outcome = install_tool(
        _tool(method),
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=runner,
        resolve_version=resolve_version,
    )
    assert outcome.status == "failed"
    assert len(outcome.errors) == 1
```

> Note: `engine` is already imported at module level (`import installer.engine as engine`) and `_tool`, `CommandError`, `Method`, `Platform`, `install_tool` are already imported from the Plan 2 test file. After deleting the old test, `ExecutorError` may become an unused import — if so, remove it from the imports to satisfy ruff/pyright.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_engine.py -q`
Expected: FAIL — `install_tool()` got an unexpected keyword argument `resolve_version` (and the github_release routing assertions fail).

- [ ] **Step 3: Update `installer/engine.py`**

Replace the entire file with:

```python
"""Install a tool by walking its resolved priority ladder until one method works."""
from dataclasses import dataclass
from typing import Literal

from installer import download, executors
from installer.download import ExecContext
from installer.model import Method, Tool
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner, run_command
from installer.status import is_installed
from installer.versions import VersionResolver, resolve_github_version

Status = Literal["already-installed", "installed", "no-method", "failed"]


@dataclass(frozen=True)
class InstallOutcome:
    tool_id: str
    status: Status
    method_kind: str | None = None
    errors: tuple[Exception, ...] = ()


def _perform(method: Method, ctx: ExecContext) -> None:
    """Route a method to its command executor or its download executor."""
    if method.kind in executors.EXECUTORS:
        executors.execute(method, ctx.runner)
    else:
        download.install_download(method, ctx)


def install_tool(
    tool: Tool,
    platform: Platform,
    runner: Runner = run_command,
    resolve_version: VersionResolver = resolve_github_version,
) -> InstallOutcome:
    """Try each applicable method in ladder order; stop at the first success."""
    if is_installed(tool):
        return InstallOutcome(tool.id, "already-installed")

    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, "no-method")

    ctx = ExecContext(runner=runner, platform=platform, resolve_version=resolve_version)
    errors: list[Exception] = []
    for method in methods:
        try:
            _perform(method, ctx)
            return InstallOutcome(tool.id, "installed", method_kind=method.kind)
        except (CommandError, executors.ExecutorError) as exc:
            errors.append(exc)
    return InstallOutcome(tool.id, "failed", errors=tuple(errors))
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_engine.py -q`
Expected: PASS (7 tests: 5 original kept + 2 new).

- [ ] **Step 5: Full validate + coverage, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/engine.py tests/test_engine.py
git commit -m "$(printf 'feat: route download method kinds through the install engine\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Expected from `make test`: all tests pass, coverage ≥ 90%.

---

## Definition of Done (this plan)

- [ ] `make validate` passes (ruff, ruff format --check, pyright strict, bandit, vulture).
- [ ] `make test` passes with coverage ≥ 90%.
- [ ] A `github_release` tool installs end-to-end through fakes (version resolved → asset templated → curl|tar → chmod), and `tarball` installs from a direct URL.
- [ ] Download failures and unsupported kinds are caught by the engine as `failed`, never raised.
- [ ] Command-based installs (Plan 2) are unaffected — their tests pass unchanged.
- [ ] Five coherent commits (Task 3 is a small refactor commit).

## Known limitation (called out, not silently dropped)

- macOS GUI apps (`.dmg` mount → copy `.app` into `~/Applications` → symlink CLI into `~/.local/bin`) are NOT handled here. No seeded tool needs it yet; it is deferred to a later plan. Download executors here target CLI binaries into a bin dir.
- `tarball`/`github_release` extract a single `member` into the bin dir (flat binaries). Multi-file app layouts (extract to `~/.local/opt` + symlink) are out of scope for this plan.

## Follow-up plans (remaining roadmap)

4. **Interactive TUI** — `questionary` category navigation + spacebar multi-select; pre-flight audit (`rich`); `setup.py` entrypoint wiring `make run`.
5. **PATH doctor** — managed idempotent `~/.myshellrc`, `source` wiring into `.zshrc`/`.bashrc` without duplicates, audit of missing/broken/duplicate bin dirs.
6. **`curl|bash` bootstrap & packaging** — `install.sh` (detect OS/arch → ensure uv → fetch repo → run wizard); optional `brew-mac`/`brew-linux` registry entries; macOS GUI/`.app` install; release/publish flow.
```
