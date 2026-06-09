# tools-installer Homebrew Tool (Phase 6b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Homebrew an opt-in tool the wizard can install (`brew-mac` / `brew-linux`), so brew-only tools have a path to being installed — without making brew a prerequisite.

**Architecture:** Three small composable seams. (1) The existing `script` executor gains an optional `env` param (so the Homebrew installer runs with `NONINTERACTIVE=1`) — inlined into the `sh -c` string, no `Runner` change. (2) `Method` gains a general `os` tuple that `resolve._applies` honors for any kind, so one `script` method targets macOS and another targets Linux. (3) `collect_bin_dirs` becomes platform-aware (it wires only the bin dir of the *applicable* method), so a mac never exports the Linux brew path. Then a single `brew` registry tool ties them together.

**Tech Stack:** Python, uv, pytest. No new dependencies.

---

## Scope

In scope: env support on `script`; a per-method `os` filter; platform-aware PATH wiring; the Homebrew registry entry; tests for each.

**Out of scope / deferred:** Intel-mac brew prefix (`/usr/local/bin`) — this plan assumes Apple Silicon (`/opt/homebrew/bin`); arch-level gating is a future refinement (note it, don't build it). Re-detecting `has_brew` mid-run so a brew-only tool installed *after* brew in the same session resolves — platform is detected once at startup (documented limitation, unchanged by this plan).

## Background facts (already true in the codebase)

- `installer/executors.py` `_script` builds `["sh", "-c", f"curl -fsSL -- {url} | {shell}"]` with an optional `shell` param (default `sh`). The brew *formula* kind (`_brew` → `brew install <formula>`) and `has_brew` gating already work.
- `installer/model.py` `Method(kind, params)` is a frozen dataclass; `load_tools` puts every TOML key except `kind` into `params`.
- `installer/resolve.py` `_applies(method, platform)` returns True for `script`/`github_release`/`tarball` unconditionally; native pkg managers gate on `platform.os` / `immutable`; `brew` gates on `has_brew`.
- `installer/platform.py` `Platform.os` is one of `"macos" | "debian" | "arch" | "fedora"`.
- `installer/shellrc.py` `collect_bin_dirs(tools, default)` iterates **every** method's `bin_dir` (no platform awareness — the gap this plan fixes).
- `installer/app.py` `configure_path(...)` and `run_doctor(...)` call `collect_bin_dirs`; both are invoked from `setup.py` where the detected `Platform` is in scope.

---

## Task 1: `env` support in the `script` executor

**Files:**
- Modify: `installer/executors.py`
- Test: `tests/test_executors.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_executors.py` (these use a list-recording runner; if the file already defines an equivalent recorder, reuse it instead of redefining):

```python
def test_script_passes_env_assignments_before_the_pipeline() -> None:
    calls: list[list[str]] = []
    method = Method(
        kind="script",
        params={
            "url": "https://example.test/install.sh",
            "shell": "bash",
            "env": {"NONINTERACTIVE": "1"},
        },
    )
    execute(method, calls.append)
    assert calls == [
        ["sh", "-c", "NONINTERACTIVE=1 curl -fsSL -- https://example.test/install.sh | bash"]
    ]


def test_script_without_env_is_unchanged() -> None:
    calls: list[list[str]] = []
    method = Method(kind="script", params={"url": "https://example.test/i.sh"})
    execute(method, calls.append)
    assert calls == [["sh", "-c", "curl -fsSL -- https://example.test/i.sh | sh"]]
```

(`Method` and `execute` are already imported in `tests/test_executors.py`; if not, add `from installer.model import Method` and `from installer.executors import execute`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_executors.py -k script -v`
Expected: `test_script_passes_env_assignments_before_the_pipeline` FAILS (no env prefix yet); the unchanged test passes.

- [ ] **Step 3: Implement env support**

In `installer/executors.py`, add `from typing import cast` to the imports, then add this helper above `_script` and replace `_script`:

```python
def _env_prefix(method: Method) -> str:
    """Shell-quoted `KEY=value` assignments to prepend to a script pipeline, sorted by key."""
    raw = method.params.get("env")
    if not isinstance(raw, dict):
        return ""
    env = cast(dict[str, object], raw)
    parts = [
        f"{key}={shlex.quote(str(value))}"
        for key, value in sorted(env.items(), key=lambda item: item[0])
    ]
    return " ".join(parts)


def _script(method: Method, runner: Runner) -> None:
    url = require_str(method, "url")
    shell = method.params.get("shell")
    shell = shell if isinstance(shell, str) and shell else "sh"
    pipeline = f"curl -fsSL -- {shlex.quote(url)} | {shlex.quote(shell)}"
    prefix = _env_prefix(method)
    if prefix:
        pipeline = f"{prefix} {pipeline}"
    runner(["sh", "-c", pipeline])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_executors.py -k script -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify the gate**

Run: `make validate && make test`
Expected: all green; 100% coverage. (`cast` is required for pyright-strict cleanliness against the `object`-typed param — it is not a gate bypass.)

- [ ] **Step 6: Commit**

```bash
git add installer/executors.py tests/test_executors.py
git commit -m "feat: let the script executor pass environment assignments

Prepend shell-quoted KEY=value pairs (e.g. NONINTERACTIVE=1) to the curl|sh
pipeline so unattended installers like Homebrew can run non-interactively.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: A general `os` filter on methods

**Files:**
- Modify: `installer/model.py`
- Modify: `installer/resolve.py`
- Test: `tests/test_model.py`, `tests/test_resolve.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_model.py` (add `from pathlib import Path` and ensure `from installer.model import load_tools` are imported):

```python
def test_load_tools_reads_method_os_targets(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "misc"\n'
        "[[tool.method]]\n"
        'kind = "script"\n'
        'os = ["macos"]\n'
        'url = "https://example.test/i.sh"\n'
    )
    method = load_tools(manifest)[0].methods[0]
    assert method.os == ("macos",)
    assert "os" not in method.params
    assert method.params["url"] == "https://example.test/i.sh"
```

Append to `tests/test_resolve.py` (ensure `Method`, `Tool`, `Platform`, `resolve_methods` are imported):

```python
def test_os_filter_restricts_a_method_to_its_target_os() -> None:
    mac = Method(kind="script", params={"url": "https://example.test/i.sh"}, os=("macos",))
    linux = Method(
        kind="script", params={"url": "https://example.test/i.sh"}, os=("debian", "arch", "fedora")
    )
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(mac, linux))
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    debian = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    assert resolve_methods(tool, macos) == [mac]
    assert resolve_methods(tool, debian) == [linux]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_model.py::test_load_tools_reads_method_os_targets tests/test_resolve.py::test_os_filter_restricts_a_method_to_its_target_os -v`
Expected: FAIL — `Method` has no `os` attribute / the loader does not populate it.

- [ ] **Step 3: Add the `os` field to `Method` and populate it in the loader**

In `installer/model.py`, change the `Method` dataclass to:

```python
@dataclass(frozen=True)
class Method:
    kind: str
    params: dict[str, object] = field(default_factory=_empty_params)
    os: tuple[str, ...] = ()
```

In `load_tools`, replace the method-building lines:

```python
            params = {k: v for k, v in entry.items() if k != "kind"}
            methods.append(Method(kind=kind, params=params))
```

with:

```python
            os_targets = tuple(entry.get("os", []))
            params = {k: v for k, v in entry.items() if k not in ("kind", "os")}
            methods.append(Method(kind=kind, params=params, os=os_targets))
```

- [ ] **Step 4: Honor the filter in the resolver**

In `installer/resolve.py`, add the OS check as the first lines of `_applies`:

```python
def _applies(method: Method, platform: Platform) -> bool:
    if method.os and platform.os not in method.os:
        return False
    kind = method.kind
    if kind in ("script", "github_release", "tarball"):
        return True
```

(Leave the rest of `_applies` unchanged.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_model.py tests/test_resolve.py -v`
Expected: PASS (existing tests still pass; the two new ones pass).

- [ ] **Step 6: Verify the gate**

Run: `make validate && make test`
Expected: all green; 100% coverage.

- [ ] **Step 7: Commit**

```bash
git add installer/model.py installer/resolve.py tests/test_model.py tests/test_resolve.py
git commit -m "feat: add a per-method os filter to the resolver

A method may declare os = [...] in the registry; the resolver skips it unless
the platform's os is listed. Empty (the default) means it applies everywhere,
so existing methods are unaffected.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Platform-aware `collect_bin_dirs`

**Files:**
- Modify: `installer/shellrc.py`
- Modify: `installer/app.py`
- Modify: `setup.py`
- Test: `tests/test_shellrc.py`, `tests/test_app.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_shellrc.py` (ensure `Method`, `Tool`, `Platform`, `Path`, and `collect_bin_dirs` are imported):

```python
def test_collect_bin_dirs_only_includes_platform_applicable_methods() -> None:
    mac = Method(
        kind="script",
        params={"url": "u", "bin_dir": "/opt/homebrew/bin"},
        os=("macos",),
    )
    linux = Method(
        kind="script",
        params={"url": "u", "bin_dir": "/home/linuxbrew/.linuxbrew/bin"},
        os=("debian", "arch", "fedora"),
    )
    tool = Tool(id="brew", name="Homebrew", category="pkg-mgr", cmd="brew", methods=(mac, linux))
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    dirs = collect_bin_dirs([tool], macos, Path("~/.local/bin"))
    assert Path("/opt/homebrew/bin") in dirs
    assert Path("/home/linuxbrew/.linuxbrew/bin") not in dirs
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_shellrc.py::test_collect_bin_dirs_only_includes_platform_applicable_methods -v`
Expected: FAIL — `collect_bin_dirs` currently takes `(tools, default)`, so passing a 3rd positional argument is a TypeError.

- [ ] **Step 3: Make `collect_bin_dirs` platform-aware**

In `installer/shellrc.py`, add these imports near the top (alongside `from installer.model import Tool`):

```python
from installer.platform import Platform
from installer.resolve import resolve_methods
```

Replace the `collect_bin_dirs` function with:

```python
def collect_bin_dirs(tools: list[Tool], platform: Platform, default: Path) -> list[Path]:
    """The default bin dir plus the bin_dir of every platform-applicable method, deduped in order."""
    dirs: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            dirs.append(resolved)

    add(default)
    for tool in tools:
        for method in resolve_methods(tool, platform):
            raw = method.params.get("bin_dir")
            if isinstance(raw, str) and raw:
                add(Path(raw))
    return dirs
```

- [ ] **Step 4: Thread `platform` through `app.py`**

In `installer/app.py`, update `configure_path` to take a keyword-only `platform` and pass it down:

```python
def configure_path(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
) -> None:
    """Write the managed PATH block and wire `source` into every rc path.

    Each rc file is wired idempotently; an absent rc file is created so the PATH
    block is sourced even on a fresh machine with no shell rc yet.
    """
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir)
    write_myshellrc(bin_dirs, myshellrc_path)
    for rc_path in rc_paths:
        ensure_source(rc_path, myshellrc_path)
    console.print(f"PATH configured in {myshellrc_path} (restart your shell or source it).")
```

And update `run_doctor` to take `platform` and pass it to both `collect_bin_dirs` and `configure_path`:

```python
def run_doctor(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    path_value: str,
    exists: Callable[[Path], bool],
    myshellrc_path: Path,
    rc_paths: list[Path],
    fix: bool,
) -> DoctorReport:
    """Audit the PATH, render the report, and (if fix) write the managed config."""
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir)
    report = audit_path(bin_dirs, path_value, exists)
    render_doctor(report, console)
    if fix:
        configure_path(
            tools,
            console,
            platform=platform,
            default_bin_dir=default_bin_dir,
            myshellrc_path=myshellrc_path,
            rc_paths=rc_paths,
        )
    return report
```

(`Platform` is already imported in `installer/app.py`.)

- [ ] **Step 5: Update the call sites in `setup.py`**

In `setup.py`, find the `configure_path(...)` and `run_doctor(...)` calls and add `platform=<the detected Platform>` as a keyword argument, using the `Platform` value already detected in `setup.py` (the same one passed to `run_wizard` / used for the doctor). Do not change anything else.

- [ ] **Step 6: Fix the existing tests that call the changed signatures**

In `tests/test_app.py` and `tests/test_shellrc.py`, the existing calls to `collect_bin_dirs(tools, default)`, `configure_path(...)`, and `run_doctor(...)` must pass a `platform`. Add a helper Platform where needed, e.g.:

```python
_PLATFORM = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
```

- `collect_bin_dirs(tools, default)` → `collect_bin_dirs(tools, _PLATFORM, default)`
- `configure_path(tools, console, default_bin_dir=..., ...)` → add `platform=_PLATFORM`
- `run_doctor(tools, console, default_bin_dir=..., ...)` → add `platform=_PLATFORM`

Ensure `Platform` is imported in both test files. Note: the existing `test_app.py` tools use a `brew` formula method with no `os`, and `_PLATFORM` has `has_brew=True`, so those methods still resolve and their (absent) bin dirs behave exactly as before — the existing assertions stay valid.

- [ ] **Step 7: Run the full suite**

Run: `make validate && make test`
Expected: all green; 100% coverage. If any pre-existing `test_app.py`/`test_shellrc.py` assertion changed meaning, fix the test call (not the production code) to pass the platform.

- [ ] **Step 8: Commit**

```bash
git add installer/shellrc.py installer/app.py setup.py tests/test_shellrc.py tests/test_app.py
git commit -m "feat: wire only the platform-applicable bin dirs onto PATH

collect_bin_dirs now resolves each tool's methods for the platform and collects
only their bin dirs, so a mac never exports a Linux brew path (and the doctor
never reports it as broken). configure_path/run_doctor take the platform.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: The Homebrew registry entry

**Files:**
- Modify: `installer/registry.toml`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registry.py` (reuse the module's existing registry-path constant and imports; ensure `Platform` and `resolve_methods` are imported):

```python
def test_registry_includes_homebrew_with_os_targeted_install() -> None:
    brew = next(t for t in load_tools(REGISTRY) if t.id == "brew")
    assert {m.kind for m in brew.methods} == {"script"}
    by_os = {m.os: m for m in brew.methods}
    mac = by_os[("macos",)]
    assert mac.params["bin_dir"] == "/opt/homebrew/bin"
    assert mac.params["env"] == {"NONINTERACTIVE": "1"}
    assert mac.params["shell"] == "bash"
    linux = by_os[("debian", "arch", "fedora")]
    assert linux.params["bin_dir"] == "/home/linuxbrew/.linuxbrew/bin"


def test_homebrew_resolves_per_platform() -> None:
    brew = next(t for t in load_tools(REGISTRY) if t.id == "brew")
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    fedora = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    assert [m.params["bin_dir"] for m in resolve_methods(brew, macos)] == ["/opt/homebrew/bin"]
    assert [m.params["bin_dir"] for m in resolve_methods(brew, fedora)] == [
        "/home/linuxbrew/.linuxbrew/bin"
    ]
```

(If `tests/test_registry.py` names its path constant differently than `REGISTRY`, use that name. `load_tools` should already be imported there.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_registry.py -k homebrew -v`
Expected: FAIL — there is no `brew` tool in the registry yet (`StopIteration` from `next(...)`).

- [ ] **Step 3: Add the Homebrew tool to the registry**

Append to `installer/registry.toml`:

```toml

[[tool]]
id = "brew"
name = "Homebrew"
category = "pkg-mgr"
cmd = "brew"
priority = "P1"
audience = "both"
desc = "The missing package manager (optional; some tools only live here)"
[[tool.method]]
kind = "script"
os = ["macos"]
url = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
shell = "bash"
env = { NONINTERACTIVE = "1" }
bin_dir = "/opt/homebrew/bin"
[[tool.method]]
kind = "script"
os = ["debian", "arch", "fedora"]
url = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
shell = "bash"
env = { NONINTERACTIVE = "1" }
bin_dir = "/home/linuxbrew/.linuxbrew/bin"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_registry.py -k homebrew -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify the full gate**

Run: `make validate && make test`
Expected: all green; 100% coverage. If `tests/test_registry.py` has an invariant test over every tool (e.g. "every tool has a non-empty category / valid priority"), confirm the brew entry satisfies it.

- [ ] **Step 6: Commit**

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add Homebrew as an opt-in installable tool

A single brew tool with two os-targeted script methods runs the official
Homebrew installer non-interactively, declaring the macOS (/opt/homebrew/bin)
and Linuxbrew (/home/linuxbrew/.linuxbrew/bin) prefixes so PATH is wired.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:** The two confirmed decisions are implemented — env-via-`script` (Task 1) and a general per-method `os` filter (Task 2). Task 3 fixes the PATH-wiring consequence of OS-targeting (correctness, not polish). Task 4 ships the actual `brew-mac`/`brew-linux` capability as one os-targeted tool. Deferred items (Intel-mac prefix, mid-run brew re-detection) are called out under Scope and intentionally excluded.

**2. Placeholder scan:** No `TBD`/"handle edge cases". Every code step shows complete functions or exact before/after text. The only loosely-specified spots are "reuse the existing recorder / path constant / Platform import in the test file," which are concrete reconciliation instructions, not placeholders — the full test bodies are provided.

**3. Type/name consistency:** `Method.os` is a `tuple[str, ...]` everywhere (model field, loader, resolve check, tests). `collect_bin_dirs(tools, platform, default)` has the same signature in shellrc, both app callers, and every test. `platform.os` values (`macos`/`debian`/`arch`/`fedora`) match the registry `os` lists and the `Platform` constructions in tests. The brew bin dirs are byte-identical across the registry and the tests.

**Coverage note:** Every new branch is exercised — `_env_prefix` (env present/absent), the `os` filter (match/no-match), platform-aware collection (applicable/not), and per-platform resolution of the brew tool. No `installer` line is added without a covering test, so the 100% floor holds.
