# macOS GUI App Install (Plan 6c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install macOS GUI apps (VS Code, Sublime Text) from vendor zips into `~/Applications` with their CLI symlinked into `~/.local/bin`, plus a `brew --cask` fallback — zero sudo, never `/Applications`.

**Architecture:** A new `app` method kind (focused module `installer/apps.py`: curl → `ditto -x -k` → `mv` in one `sh -c` pipeline, all argv through the injected Runner) and a one-line `cask` executor in `installer/executors.py` (`brew install --cask --appdir=~/Applications`). A new generic per-method `arch` filter (mirrors the existing `os` filter) drives VS Code's arch-split URLs. Detection (`installer/status.py`) gains a bundle-exists check; uninstall planning learns app bundles and CLI links.

**Tech Stack:** Python 3.11+ (uv-managed), pytest with 100% coverage gate, pyright strict, ruff. Spec: `docs/superpowers/specs/2026-06-11-macos-app-install-design.md` (user-approved; all URLs/zip members live-verified 2026-06-11).

**Per-commit gate (non-negotiable):** every commit in this plan must pass `make validate && make test` on the exact tree being committed. Never silence a check (`# noqa`, `# type: ignore`, `# pragma: no cover`, coverage lowering are all forbidden). NEVER run the real wizard or doctor against this machine's home.

**Conventions you must follow** (read these files before coding if anything is unclear):

- Executors build argv and hand it to a `Runner` (`installer/run.py`: `Runner = Callable[[list[str]], None]`); tests inject a recording runner and assert exact argv. No test performs network or filesystem side effects beyond `tmp_path`.
- `installer/executors.py` defines `ExecutorError` and `require_str(method, key)`.
- `installer/locations.py` has `bin_dir(declared)` (defaults `~/.local/bin`), `ensure_dir(path)`.
- `Platform.arch` is normalized to `"amd64"` / `"arm64"` (`installer/platform.py`).
- Tests fake `Path.home()` with `monkeypatch.setattr(Path, "home", lambda: tmp_path)`.
- Commit messages end with the trailer line `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: Generic per-method `arch` filter

**Files:**
- Modify: `installer/model.py` (Method dataclass + `load_tools` parse)
- Modify: `installer/resolve.py` (`_applies`)
- Test: `tests/test_model.py`, `tests/test_resolve.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_model.py`:

```python
def test_load_tools_reads_method_arch_targets(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "misc"\n'
        "[[tool.method]]\n"
        'kind = "script"\n'
        'os = ["macos"]\n'
        'arch = ["arm64"]\n'
        'url = "https://example.test/i.sh"\n'
    )
    method = load_tools(manifest)[0].methods[0]
    assert method.arch == ("arm64",)
    assert "arch" not in method.params
    assert method.params["url"] == "https://example.test/i.sh"


def test_load_tools_rejects_arch_as_a_string(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "misc"\n'
        "[[tool.method]]\n"
        'kind = "script"\n'
        'arch = "arm64"\n'  # must be a list, not a string
        'url = "https://example.test/i.sh"\n'
    )
    with pytest.raises(ValueError, match="'arch' must be a list"):
        load_tools(manifest)
```

Append to `tests/test_resolve.py`:

```python
def test_arch_filter_restricts_a_method_to_its_target_arch() -> None:
    arm = Method(kind="script", params={"url": "https://example.test/a"}, arch=("arm64",))
    intel = Method(kind="script", params={"url": "https://example.test/b"}, arch=("amd64",))
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(arm, intel))
    arm_mac = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    intel_mac = Platform(os="macos", arch="amd64", immutable=False, has_brew=False)
    assert resolve_methods(tool, arm_mac) == [arm]
    assert resolve_methods(tool, intel_mac) == [intel]


def test_method_without_arch_applies_on_every_arch() -> None:
    method = Method(kind="script", params={"url": "https://example.test/i.sh"})
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(method,))
    for arch in ("amd64", "arm64"):
        platform = Platform(os="debian", arch=arch, immutable=False, has_brew=False)
        assert resolve_methods(tool, platform) == [method]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_model.py tests/test_resolve.py -q --no-cov -k arch`
Expected: FAIL — `TypeError: Method.__init__() got an unexpected keyword argument 'arch'` (resolve tests) and `AssertionError`/`Failed: DID NOT RAISE` (model tests).

- [ ] **Step 3: Implement**

In `installer/model.py`, add the field to `Method` (after `os`):

```python
@dataclass(frozen=True)
class Method:
    kind: str
    params: dict[str, object] = field(default_factory=_empty_params)
    os: tuple[str, ...] = ()
    arch: tuple[str, ...] = ()
```

In `load_tools`, extend the per-entry parsing (replace the block from `raw_os = entry.get("os", [])` through the `methods.append(...)` call):

```python
            raw_os = entry.get("os", [])
            if isinstance(raw_os, str):
                # tuple("macos") would silently become ('m','a','c','o','s'); a list is required.
                raise ValueError(f"tool '{row['id']}': method 'os' must be a list of strings")
            os_targets = tuple(raw_os)
            raw_arch = entry.get("arch", [])
            if isinstance(raw_arch, str):
                raise ValueError(f"tool '{row['id']}': method 'arch' must be a list of strings")
            arch_targets = tuple(raw_arch)
            params = {k: v for k, v in entry.items() if k not in ("kind", "os", "arch")}
            methods.append(Method(kind=kind, params=params, os=os_targets, arch=arch_targets))
```

In `installer/resolve.py`, add the arch check in `_applies`, right after the existing os check:

```python
def _applies(method: Method, platform: Platform) -> bool:
    if method.os and platform.os not in method.os:
        return False
    if method.arch and platform.arch not in method.arch:
        return False
```

(The rest of `_applies` is unchanged.)

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all green, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add installer/model.py installer/resolve.py tests/test_model.py tests/test_resolve.py
git commit -m "feat: add per-method arch filter (amd64/arm64)

Mirrors the existing os filter: list-required parse validation in
load_tools, one check in resolve._applies against Platform.arch.
Needed for arch-split download URLs (VS Code); also reusable for
existing Intel-mac asset gaps.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `cask` method kind (brew cask into ~/Applications)

**Files:**
- Modify: `installer/model.py` (METHOD_KINDS)
- Modify: `installer/executors.py` (new `_cask` executor)
- Modify: `installer/resolve.py` (rank + applicability)
- Test: `tests/test_executors.py`, `tests/test_resolve.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_executors.py` (note the file already imports `pytest`, `EXECUTORS`, `ExecutorError`, `execute`, `Method`, `Runner`; add `from pathlib import Path` to its imports):

```python
def test_cask_executor_installs_into_user_applications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    execute(Method(kind="cask", params={"cask": "sublime-text"}), runner)
    assert calls == [
        ["brew", "install", "--cask", f"--appdir={tmp_path / 'Applications'}", "sublime-text"]
    ]


def test_cask_missing_param_raises():
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="cask"):
        execute(Method(kind="cask", params={}), runner)
    assert calls == []
```

In `tests/test_executors.py`, UPDATE the existing kind-inventory test:

```python
def test_every_command_kind_has_an_executor():
    assert set(EXECUTORS) == {"script", "dnf", "apt", "pacman", "brew", "cask"}
```

Append to `tests/test_resolve.py`:

```python
def test_cask_requires_macos_and_brew() -> None:
    cask = Method(kind="cask", params={"cask": "x"})
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(cask,))
    mac_brew = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    mac_no_brew = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    linux_brew = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    assert resolve_methods(tool, mac_brew) == [cask]
    assert resolve_methods(tool, mac_no_brew) == []
    assert resolve_methods(tool, linux_brew) == []
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_executors.py tests/test_resolve.py -q --no-cov -k cask`
Expected: FAIL — `ExecutorError: no executor for method kind 'cask'` and `KeyError: 'cask'` (resolve `_RANK`).

- [ ] **Step 3: Implement**

`installer/model.py` — add `"cask"` to `METHOD_KINDS` (after `"brew"`):

```python
METHOD_KINDS = (
    "script",
    "github_release",
    "tarball",
    "dnf",
    "apt",
    "pacman",
    "rpm_ostree",
    "brew",
    "cask",
)
```

`installer/executors.py` — add `from pathlib import Path` to the imports, then the executor (after `_brew`) and registry entry:

```python
def _cask(method: Method, runner: Runner) -> None:
    # --appdir keeps the bundle in userspace; brew's default appdir is /Applications,
    # which the PRD forbids (corporate machines without sudo).
    appdir = Path.home() / "Applications"
    runner(["brew", "install", "--cask", f"--appdir={appdir}", require_str(method, "cask")])


EXECUTORS: dict[str, Callable[[Method, Runner], None]] = {
    "script": _script,
    "dnf": _dnf,
    "apt": _apt,
    "pacman": _pacman,
    "brew": _brew,
    "cask": _cask,
}
```

Also update the module docstring's first lines to mention casks:

```python
"""Per-method-kind executors: build an argv and hand it to the injected runner.

Only command-based kinds live here (script, native package managers, brew, cask).
Download-based kinds (github_release, tarball) live in `installer.download`.
"""
```

`installer/resolve.py` — add the rank and applicability:

```python
_RANK = {
    "script": 10,
    "github_release": 20,
    "tarball": 20,
    "dnf": 30,
    "apt": 30,
    "pacman": 30,
    "rpm_ostree": 35,
    "brew": 40,
    "cask": 40,
}
```

In `_applies`, after the `if kind == "brew":` branch:

```python
    if kind == "cask":
        # Casks are a macOS-only brew concept; --appdir keeps them in ~/Applications.
        return platform.os == "macos" and platform.has_brew
```

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all green, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add installer/model.py installer/executors.py installer/resolve.py tests/test_executors.py tests/test_resolve.py
git commit -m "feat: cask method kind installs GUI apps via brew --appdir

brew install --cask --appdir=~/Applications keeps the PRD's
never-/Applications rule on the fallback rung. Applies only on
macOS with brew present; ranks with brew (40).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `app` method kind — installer/apps.py + engine routing

**Files:**
- Create: `installer/apps.py`
- Modify: `installer/model.py` (METHOD_KINDS), `installer/resolve.py` (rank + applies), `installer/engine.py` (`_perform` routing)
- Test: Create `tests/test_apps.py`; modify `tests/test_engine.py`, `tests/test_resolve.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_apps.py`:

```python
import shlex
from pathlib import Path

import pytest

import installer.apps as apps_mod
from installer.apps import APP_KINDS, install_app
from installer.executors import ExecutorError
from installer.model import Method
from installer.run import Runner


def _record() -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    return calls, runner


def _method(**extra: object) -> Method:
    params: dict[str, object] = {"url": "https://example.test/app.zip", "app": "Demo App.app"}
    params.update(extra)
    return Method(kind="app", params=params)


def test_app_kinds_inventory():
    assert APP_KINDS == ("app",)


def test_install_app_builds_curl_ditto_mv_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    install_app(_method(), runner)
    apps = tmp_path / "Applications"
    assert apps.is_dir()  # created before the pipeline runs
    expected = (
        "tmp=$(mktemp -d) && trap 'rm -rf \"$tmp\"' EXIT"
        ' && curl -fsSL -o "$tmp/app.zip" -- https://example.test/app.zip'
        ' && ditto -x -k "$tmp/app.zip" "$tmp/x"'
        f" && mv \"$tmp/x/\"'Demo App.app' {shlex.quote(str(apps))}/"
    )
    assert calls == [["sh", "-c", expected]]


def test_install_app_symlinks_declared_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    install_app(_method(cli="Contents/SharedSupport/bin/demo"), runner)
    assert len(calls) == 2
    bundle = tmp_path / "Applications" / "Demo App.app"
    assert calls[1] == [
        "ln",
        "-sf",
        str(bundle / "Contents/SharedSupport/bin/demo"),
        str(tmp_path / ".local" / "bin" / "demo"),
    ]
    assert (tmp_path / ".local" / "bin").is_dir()


def test_install_app_without_cli_runs_only_the_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    install_app(_method(), runner)
    assert len(calls) == 1


def test_install_app_requires_url_and_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="url"):
        install_app(Method(kind="app", params={"app": "Demo.app"}), runner)
    with pytest.raises(ExecutorError, match="app"):
        install_app(Method(kind="app", params={"url": "https://example.test/a.zip"}), runner)
    assert calls == []


def test_install_app_rejects_nested_or_traversal_bundle_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="invalid app bundle name"):
        install_app(_method(app="x/Demo.app"), runner)
    with pytest.raises(ExecutorError, match="invalid app bundle name"):
        install_app(_method(app=".."), runner)
    assert calls == []


def test_install_app_rejects_bad_cli_param(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="cli"):
        install_app(_method(cli=""), runner)
    with pytest.raises(ExecutorError, match="cli"):
        install_app(_method(cli=42), runner)
    with pytest.raises(ExecutorError, match="cannot derive a CLI name"):
        install_app(_method(cli="Contents/.."), runner)
    assert calls == []  # params are validated before any side effect


def test_install_app_wraps_applications_dir_oserror(monkeypatch: pytest.MonkeyPatch):
    def boom(directory: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(apps_mod, "ensure_dir", boom)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="Applications dir"):
        install_app(_method(), runner)
    assert calls == []


def test_install_app_wraps_bin_dir_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    real = apps_mod.ensure_dir

    def flaky(directory: Path) -> Path:
        if directory.name == "bin":
            raise OSError("denied")
        return real(directory)

    monkeypatch.setattr(apps_mod, "ensure_dir", flaky)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="bin dir"):
        install_app(_method(cli="Contents/bin/demo"), runner)
    assert len(calls) == 1  # the pipeline ran; only the symlink step failed
```

Append to `tests/test_engine.py` (the file already imports `engine`, `install_tool`, `Method`, `Tool`, `Platform`, `pytest`):

```python
def test_app_kind_routes_to_app_executor(monkeypatch: pytest.MonkeyPatch):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    seen: list[str] = []

    def fake_install_app(method: Method, runner: object) -> None:
        seen.append(method.kind)

    monkeypatch.setattr(engine.apps, "install_app", fake_install_app)
    outcome = install_tool(
        _tool(Method(kind="app", params={"url": "u", "app": "A.app"})),
        Platform(os="macos", arch="arm64", immutable=False, has_brew=False),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "app"
    assert outcome.verified is False
    assert seen == ["app"]
```

Append to `tests/test_resolve.py`:

```python
def test_app_ranks_with_userspace_downloads_before_cask() -> None:
    app = Method(kind="app", params={"url": "u", "app": "A.app"}, os=("macos",))
    cask = Method(kind="cask", params={"cask": "a"})
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(cask, app))
    mac = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(tool, mac)] == ["app", "cask"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_apps.py tests/test_engine.py::test_app_kind_routes_to_app_executor tests/test_resolve.py::test_app_ranks_with_userspace_downloads_before_cask -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.apps'`.

- [ ] **Step 3: Implement**

Create `installer/apps.py`:

```python
"""Executor for macOS GUI apps shipped as a zip containing a .app bundle.

The bundle lands in ~/Applications (never /Applications, zero sudo) and the
optional in-bundle CLI is symlinked into ~/.local/bin, per the PRD's location
policy. Extraction uses `ditto -x -k`, the canonical macOS extractor for .app
zips: it preserves the extended attributes and framework symlinks that
Info-ZIP `unzip` can mangle in Electron-style bundles. curl never sets
com.apple.quarantine, so installed apps launch without the Gatekeeper
"downloaded from the internet" dialog — identical to `brew install --cask`.
"""

import shlex
from pathlib import Path, PurePosixPath

from installer.executors import ExecutorError, require_str
from installer.locations import bin_dir, ensure_dir
from installer.model import Method
from installer.run import Runner

APP_KINDS = ("app",)


def applications_dir() -> Path:
    """The userspace Applications dir: ~/Applications."""
    return Path.home() / "Applications"


def _cli_spec(method: Method) -> tuple[str, str] | None:
    """(bundle-relative CLI path, symlink name) for the optional `cli` param."""
    cli = method.params.get("cli")
    if cli is None:
        return None
    if not isinstance(cli, str) or not cli:
        raise ExecutorError("method 'app' param 'cli' must be a non-empty string")
    name = PurePosixPath(cli).name
    if name in ("", ".", ".."):
        raise ExecutorError(f"cannot derive a CLI name from '{cli}'")
    return cli, name


def install_app(method: Method, runner: Runner) -> None:
    """Download the app zip, extract in a temp dir, move the .app into place.

    Extract-then-move keeps ~/Applications free of partial bundles on any
    failure; a non-zero exit anywhere breaks the && chain (CommandError),
    which falls through to the next ladder method (the cask rung).
    """
    url = require_str(method, "url")
    app = require_str(method, "app")
    if PurePosixPath(app).name != app or app in (".", ".."):
        # A nested or traversal bundle name would move/symlink outside ~/Applications.
        raise ExecutorError(f"invalid app bundle name '{app}'")
    spec = _cli_spec(method)  # validate every param before any side effect
    try:
        apps = ensure_dir(applications_dir())
    except OSError as exc:
        raise ExecutorError(f"cannot create Applications dir: {exc}") from exc
    pipeline = (
        "tmp=$(mktemp -d) && trap 'rm -rf \"$tmp\"' EXIT"
        f' && curl -fsSL -o "$tmp/app.zip" -- {shlex.quote(url)}'
        ' && ditto -x -k "$tmp/app.zip" "$tmp/x"'
        # Adjacent quoting: "$tmp/x/" expands in the shell, the bundle name stays literal.
        f' && mv "$tmp/x/"{shlex.quote(app)} {shlex.quote(str(apps))}/'
    )
    runner(["sh", "-c", pipeline])
    if spec is None:
        return
    cli, name = spec
    try:
        dest = ensure_dir(bin_dir(None))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    runner(["ln", "-sf", str(apps / app / cli), str(dest / name)])
```

`installer/model.py` — add `"app"` to `METHOD_KINDS` (after `"tarball"`):

```python
METHOD_KINDS = (
    "script",
    "github_release",
    "tarball",
    "app",
    "dnf",
    "apt",
    "pacman",
    "rpm_ostree",
    "brew",
    "cask",
)
```

`installer/resolve.py` — rank `"app": 20` (insert after `"tarball": 20`) and include `"app"` in the unconditional kinds inside `_applies`:

```python
_RANK = {
    "script": 10,
    "github_release": 20,
    "tarball": 20,
    "app": 20,
    "dnf": 30,
    "apt": 30,
    "pacman": 30,
    "rpm_ostree": 35,
    "brew": 40,
    "cask": 40,
}
```

```python
    if kind in ("script", "github_release", "tarball", "app"):
        return True
```

`installer/engine.py` — import and route. Change the import line and `_perform`:

```python
from installer import apps, download, executors
```

```python
def _perform(method: Method, ctx: ExecContext) -> bool:
    """Route download kinds to the download executor; everything else to a command executor.

    Returns True when the download was sha256-verified (non-download methods
    are never marked verified — their package managers do their own checks;
    app zips have no published checksums to verify).
    """
    if method.kind in download.DOWNLOAD_KINDS:
        return download.install_download(method, ctx)
    if method.kind in apps.APP_KINDS:
        apps.install_app(method, ctx.runner)
        return False
    executors.execute(method, ctx.runner)
    return False
```

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all green, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add installer/apps.py installer/model.py installer/resolve.py installer/engine.py tests/test_apps.py tests/test_engine.py tests/test_resolve.py
git commit -m "feat: app method kind installs .app bundles into ~/Applications

New installer/apps.py: one sh -c pipeline (mktemp -d, curl, ditto -x -k,
mv) plus an optional in-bundle CLI symlink into ~/.local/bin. ditto
preserves the xattrs and framework symlinks unzip can mangle in
Electron-style bundles; extract-then-move keeps ~/Applications free of
partial bundles. Ranks with userspace downloads (20).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Bundle-aware installed detection

**Files:**
- Modify: `installer/status.py`
- Test: `tests/test_status.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_status.py`. Add `from pathlib import Path` to the file's imports; keep the file's existing convention of importing `installer.status as status` inside each test that monkeypatches `status.shutil`:

```python
def _app_tool(app: str = "Demo.app") -> Tool:
    return Tool(
        id="d",
        name="d",
        category="editor",
        cmd="demo",
        methods=(Method(kind="app", params={"url": "https://example.test/a.zip", "app": app}),),
    )


def test_app_bundle_present_counts_as_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", lambda cmd: None)
    (tmp_path / "Demo.app").mkdir()
    assert is_installed(_app_tool(), app_roots=(tmp_path,)) is True


def test_app_tool_without_bundle_or_cmd_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", lambda cmd: None)
    assert is_installed(_app_tool(), app_roots=(tmp_path,)) is False


def test_app_method_without_app_param_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", lambda cmd: None)
    tool = Tool(
        id="d",
        name="d",
        category="editor",
        cmd="demo",
        methods=(Method(kind="app", params={"url": "https://example.test/a.zip"}),),
    )
    assert is_installed(tool, app_roots=(tmp_path,)) is False


def test_default_app_roots_include_user_applications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "Applications" / "Demo.app").mkdir(parents=True)
    assert is_installed(_app_tool()) is True


def test_cmd_on_path_still_wins_for_app_tools(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", lambda cmd: "/usr/local/bin/demo")
    assert is_installed(_app_tool()) is True
```

Add `from pathlib import Path` to the top of `tests/test_status.py`.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_status.py -q --no-cov`
Expected: FAIL — `TypeError: is_installed() got an unexpected keyword argument 'app_roots'` (and the default-roots test fails because bundles are not checked).

- [ ] **Step 3: Implement**

Replace `installer/status.py` with:

```python
"""Whether a tool is already installed: command on PATH, or its .app bundle present."""

import shutil
from pathlib import Path

from installer.model import Tool


def _default_app_roots() -> tuple[Path, ...]:
    # A drag-installed copy in /Applications counts as installed too — we must
    # never install a userspace duplicate of a system-wide app.
    return (Path.home() / "Applications", Path("/Applications"))


def is_installed(tool: Tool, app_roots: tuple[Path, ...] | None = None) -> bool:
    """True if the tool's command resolves on PATH, or any app-method bundle exists."""
    if shutil.which(tool.cmd) is not None:
        return True
    roots = _default_app_roots() if app_roots is None else app_roots
    for method in tool.methods:
        if method.kind != "app":
            continue
        app = method.params.get("app")
        if not isinstance(app, str) or not app:
            continue
        if any((root / app).exists() for root in roots):
            return True
    return False
```

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all green, coverage 100%. (Existing callers — `engine.install_tool`, `audit.audit`, `app.run_wizard` — pass `tool` only; the new keyword defaults preserve their behavior. For non-app tools the method loop finds no `app` kinds and returns False exactly as before.)

- [ ] **Step 5: Commit**

```bash
git add installer/status.py tests/test_status.py
git commit -m "feat: bundle-aware installed detection for GUI apps

A tool is installed when its command resolves on PATH or when any
app-method bundle exists in ~/Applications or /Applications — a
drag-installed system copy is respected, never duplicated.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Uninstall planning for app bundles and CLI links

**Files:**
- Modify: `installer/uninstall.py`
- Test: `tests/test_uninstall.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_uninstall.py`:

```python
def test_plan_collects_app_bundle_and_cli_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bundle = tmp_path / "Applications" / "Demo App.app"
    bundle.mkdir(parents=True)
    (bin_dir / "demo").symlink_to(bundle / "Contents/bin/demo")  # dangling is fine
    tool = _tool(
        Method(
            kind="app",
            params={
                "url": "https://example.test/a.zip",
                "app": "Demo App.app",
                "cli": "Contents/bin/demo",
            },
        )
    )
    assert set(plan_uninstall([tool], bin_dir)) == {bundle, bin_dir / "demo"}


def test_plan_app_without_cli_plans_bundle_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bundle = tmp_path / "Applications" / "Demo.app"
    bundle.mkdir(parents=True)
    tool = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip", "app": "Demo.app"})
    )
    assert plan_uninstall([tool], bin_dir) == [bundle]


def test_plan_app_skips_absent_bundle_and_guards_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    absent = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip", "app": "Gone.app"})
    )
    traversal = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip", "app": ".."}),
        tool_id="t2",
        cmd="t2",
    )
    nested = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip", "app": "x/Demo.app"}),
        tool_id="t3",
        cmd="t3",
    )
    no_app = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip"}),
        tool_id="t4",
        cmd="t4",
    )
    assert plan_uninstall([absent, traversal, nested, no_app], bin_dir) == []


def test_plan_app_guards_cli_traversal_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bundle = tmp_path / "Applications" / "Demo.app"
    bundle.mkdir(parents=True)
    tool = _tool(
        Method(
            kind="app",
            params={"url": "https://example.test/a.zip", "app": "Demo.app", "cli": "Contents/.."},
        )
    )
    # the bundle is planned; the traversal cli name is not
    assert plan_uninstall([tool], bin_dir) == [bundle]


def test_plan_skips_cask_methods(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = _tool(Method(kind="cask", params={"cask": "sublime-text"}))
    assert plan_uninstall([tool], bin_dir) == []
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_uninstall.py -q --no-cov`
Expected: the new app tests FAIL (`plan_uninstall` returns `[]` — app kinds are currently skipped); `test_plan_skips_cask_methods` may already pass (cask is not a download kind), that is fine.

- [ ] **Step 3: Implement**

In `installer/uninstall.py`: extend the module docstring's scope line, import the app helpers, and plan app methods. Full updated file:

```python
"""Registry-driven uninstall: remove the userspace artifacts install_download
and install_app create. Cask/brew/native-managed artifacts are left alone."""

import shutil
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from installer.apps import APP_KINDS, applications_dir
from installer.download import DOWNLOAD_KINDS
from installer.locations import opt_dir
from installer.model import Tool


def _exists(path: Path) -> bool:
    # is_symlink catches dangling links (exists() is False when the target is gone).
    return path.exists() or path.is_symlink()


def _plan_app(
    params: dict[str, object], default_bin_dir: Path, add: Callable[[Path], None]
) -> None:
    """Plan the ~/Applications bundle and the cli symlink an app method created.

    Only the userspace bundle is planned — a copy in /Applications was never
    ours to manage. The same traversal guard as download binnames applies: a
    nested or dot name would resolve outside ~/Applications or ~/.local/bin.
    """
    app = params.get("app")
    if not isinstance(app, str) or not app:
        return
    if PurePosixPath(app).name != app or app in (".", ".."):
        return
    add(applications_dir() / app)
    cli = params.get("cli")
    if not isinstance(cli, str) or not cli:
        return
    name = PurePosixPath(cli).name
    if name in ("", ".", ".."):
        return
    add(default_bin_dir / name)


def plan_uninstall(tools: list[Tool], default_bin_dir: Path) -> list[Path]:
    """Existing artifacts the download/raw/app executors would have created.

    The registry is the manifest: every download/raw method maps to opt_dir(binname)
    and <bin_dir>/binname, where binname is the basename of the method's member;
    every app method maps to ~/Applications/<app> and <bin_dir>/<cli basename>.
    Only paths that currently exist (including dangling symlinks) are returned, in a
    stable de-duplicated order.
    """
    found: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path not in seen and _exists(path):
            seen.add(path)
            found.append(path)

    for tool in tools:
        for method in tool.methods:
            if method.kind in APP_KINDS:
                _plan_app(method.params, default_bin_dir, add)
                continue
            if method.kind not in DOWNLOAD_KINDS:
                continue
            member = method.params.get("member")
            if not isinstance(member, str) or not member:
                continue
            binname = PurePosixPath(member).name
            if binname in ("", ".", ".."):
                # Defensive: a traversal/empty basename would resolve opt_dir/bin
                # paths up to ~/.local and risk deleting far more than one tool.
                # Members come from the trusted registry, but this code deletes files.
                continue
            declared = method.params.get("bin_dir")
            base = (
                Path(declared).expanduser()
                if isinstance(declared, str) and declared
                else default_bin_dir
            )
            add(opt_dir(binname))
            add(base / binname)
    return found


def remove_paths(paths: list[Path]) -> None:
    """Delete each path: a symlink is unlinked (target preserved), a dir is removed
    recursively, a file is unlinked."""
    for path in paths:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
```

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all green, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add installer/uninstall.py tests/test_uninstall.py
git commit -m "feat: uninstall plans app bundles and their cli symlinks

App methods map to ~/Applications/<app> plus <bin_dir>/<cli basename>,
with the same traversal guards as download binnames. /Applications is
never planned; cask-installed apps are left alone like brew CLIs.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Registry entries — vscode + sublime (47 → 49)

**Files:**
- Modify: `installer/registry.toml` (append two tools at the end)
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_registry.py`, UPDATE the count test (rename it too):

```python
def test_registry_has_forty_nine_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    cmds = [t.cmd for t in tools]
    assert len(ids) == 49
    assert len(ids) == len(set(ids))
    assert len(cmds) == len(set(cmds))
```

UPDATE the all-platform guard to carry an explicit macOS-only allowlist:

```python
# GUI apps with no Linux install method yet (VS Code tar.gz / Sublime tarball
# are a future batch). Every other tool must resolve on every platform.
MACOS_ONLY = {"vscode", "sublime"}


def test_every_tool_resolves_at_least_one_method_on_each_platform() -> None:
    # A tool that resolves to nothing on a supported platform is silently
    # uninstallable there; this guards against an os/method misconfiguration.
    tools = load_tools(REGISTRY)
    for platform_os in ("debian", "arch", "fedora", "macos"):
        platform = Platform(os=platform_os, arch="amd64", immutable=False, has_brew=True)
        allowed = MACOS_ONLY if platform_os != "macos" else set()
        stranded = [
            t.id for t in tools if not resolve_methods(t, platform) and t.id not in allowed
        ]
        assert not stranded, f"no install method on {platform_os}: {stranded}"


def test_macos_only_allowlist_stays_honest() -> None:
    # If a Linux method is ever added to one of these, it must leave the allowlist.
    tools = {t.id: t for t in load_tools(REGISTRY)}
    debian = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    for tool_id in sorted(MACOS_ONLY):
        assert resolve_methods(tools[tool_id], debian) == []
```

Append the two structural tests:

```python
def test_vscode_is_arch_split_app_with_cask_fallback() -> None:
    vscode = next(t for t in load_tools(REGISTRY) if t.id == "vscode")
    assert vscode.cmd == "code"
    assert vscode.category == "editor"
    arm = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    intel = Platform(os="macos", arch="amd64", immutable=False, has_brew=True)
    arm_methods = resolve_methods(vscode, arm)
    assert [m.kind for m in arm_methods] == ["app", "cask"]
    assert (
        arm_methods[0].params["url"]
        == "https://update.code.visualstudio.com/latest/darwin-arm64/stable"
    )
    assert arm_methods[0].params["app"] == "Visual Studio Code.app"
    assert arm_methods[0].params["cli"] == "Contents/Resources/app/bin/code"
    assert arm_methods[1].params["cask"] == "visual-studio-code"
    intel_methods = resolve_methods(vscode, intel)
    assert [m.kind for m in intel_methods] == ["app", "cask"]
    assert (
        intel_methods[0].params["url"]
        == "https://update.code.visualstudio.com/latest/darwin/stable"
    )


def test_sublime_is_single_universal_app_with_cask_fallback() -> None:
    sublime = next(t for t in load_tools(REGISTRY) if t.id == "sublime")
    assert sublime.cmd == "subl"
    assert sublime.category == "editor"
    for arch in ("arm64", "amd64"):  # one universal zip serves both
        mac = Platform(os="macos", arch=arch, immutable=False, has_brew=True)
        methods = resolve_methods(sublime, mac)
        assert [m.kind for m in methods] == ["app", "cask"]
        assert (
            methods[0].params["url"]
            == "https://download.sublimetext.com/sublime_text_build_4200_mac.zip"
        )
        assert methods[0].params["app"] == "Sublime Text.app"
        assert methods[0].params["cli"] == "Contents/SharedSupport/bin/subl"
        assert methods[1].params["cask"] == "sublime-text"
```

- [ ] **Step 2: Run the registry tests to verify they fail**

Run: `uv run pytest tests/test_registry.py -q --no-cov`
Expected: FAIL — count is 47, `StopIteration` on the vscode/sublime lookups.

- [ ] **Step 3: Append the registry entries**

Append to the end of `installer/registry.toml`:

```toml
[[tool]]
id = "vscode"
name = "Visual Studio Code"
category = "editor"
cmd = "code"
priority = "P3"
audience = "both"
desc = "Microsoft's extensible code editor"
# Arch-split `latest` aliases (each 302s to the current build's CDN zip); the
# universal zip is ~120 MB larger per download and ~2x on disk -> not used.
[[tool.method]]
kind = "app"
os = ["macos"]
arch = ["arm64"]
url = "https://update.code.visualstudio.com/latest/darwin-arm64/stable"
app = "Visual Studio Code.app"
cli = "Contents/Resources/app/bin/code"
[[tool.method]]
kind = "app"
os = ["macos"]
arch = ["amd64"]
url = "https://update.code.visualstudio.com/latest/darwin/stable"
app = "Visual Studio Code.app"
cli = "Contents/Resources/app/bin/code"
[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "visual-studio-code"

[[tool]]
id = "sublime"
name = "Sublime Text"
category = "editor"
cmd = "subl"
priority = "P3"
audience = "both"
desc = "Fast proprietary text editor"
# One universal mac zip. The build number is pinned (no `latest` URL exists);
# the app self-updates after first launch, so the pin only affects first install.
[[tool.method]]
kind = "app"
os = ["macos"]
url = "https://download.sublimetext.com/sublime_text_build_4200_mac.zip"
app = "Sublime Text.app"
cli = "Contents/SharedSupport/bin/subl"
[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "sublime-text"
```

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all green, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add vscode and sublime as macOS app installs (registry 47->49)

VS Code uses arch-split latest aliases (universal zip is ~120 MB
larger); Sublime ships one universal zip with the build pinned (it
self-updates after first launch). Both fall back to their brew cask.
New category: editor. Both URLs and bundle/cli paths live-verified
2026-06-11.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: README catalog + ladder docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the editor category row**

In the catalog table (after the `| ai | ...` row, keeping the table's column alignment style), add:

```markdown
| editor      | `vscode` (code), `sublime` (subl)                                             |
```

- [ ] **Step 2: Document the app location policy in the ladder section**

In "How installs are decided", ladder item 2 currently ends with "…under `--yes` it hard-fails)." Append a new sentence to item 2 (same indentation, still inside item 2):

```markdown
   macOS GUI apps (`.app` from a vendor zip) land in `~/Applications` — never
   `/Applications`, zero sudo — with their CLI symlinked into `~/.local/bin`;
   their Homebrew-cask fallback also targets `~/Applications` via `--appdir`.
```

- [ ] **Step 3: Run the full gate**

Run: `make validate && make test`
Expected: all green (README is lint-checked by pre-commit hooks if configured; no test asserts README content for these tools).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: list vscode and sublime; document ~/Applications policy

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (controller)

- `git log --oneline` shows 7 coherent commits for this feature.
- `make validate && make test` green on the final tree, coverage 100%.
- `git status --short` clean.
- Dispatch the final whole-feature code review per superpowers:subagent-driven-development.
- Do NOT push or create a remote (standing instruction; publish is owner-only).
