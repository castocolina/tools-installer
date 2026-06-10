# Registry Expansion — Batch 1 (Verified CLI Tools) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the tool registry from 4 to 15 entries by adding 11 verified AI-dev CLIs (fd, bat, sd, delta, eza, zoxide, fzf, lazygit, gh, yq + a fixed ripgrep), and make the `github_release`/`tarball` download path actually work against real release archives.

**Architecture:** Two correctness fixes land first as prerequisites, then the tool data:
1. **Version→tag contract.** The release resolver returns the *raw* tag (`v10.4.2` **or** bare `15.1.0`); the download URL uses that tag for its path and a `v`-stripped `{ver}` for the asset filename. This fixes a latent 404 bug for projects whose tags have no leading `v` (ripgrep, delta).
2. **opt+symlink extraction.** Archives unpack into `~/.local/opt/<binary>/` (stripping leading path components) and the binary is symlinked into `~/.local/bin`, matching the PRD's userspace location policy. This fixes a latent bug where the binary, nested under a versioned directory inside the archive, was never extractable.

Then the registry gains the 11 tools, each as `github_release` (userspace, no sudo) + `brew` methods, OS-split where asset naming differs by platform. Native package managers are intentionally deferred (per-distro package/binary-name mismatches need separate verification).

**Tech Stack:** Python 3.11+, uv, tomllib, pytest (100% coverage gate), ruff/pyright-strict/bandit/vulture. POSIX `sh` for executor command strings.

---

## Verified Release Facts (ground truth — captured from live GitHub releases on 2026-06-09)

Every value below was confirmed against the actual latest release and, for archives, by listing real archive members. Do not change these from memory.

| tool | repo | linux asset (`{ver}` = tag w/o `v`) | macOS asset | `strip` | `member` | `raw` | brew formula |
|---|---|---|---|---|---|---|---|
| fd | sharkdp/fd | `fd-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `fd-v{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | `fd` | no | `fd` |
| bat | sharkdp/bat | `bat-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `bat-v{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | `bat` | no | `bat` |
| sd | chmln/sd | `sd-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `sd-v{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | `sd` | no | `sd` |
| rg | BurntSushi/ripgrep | `ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `ripgrep-{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | `rg` | no | `ripgrep` |
| delta | dandavison/delta | `delta-{ver}-{arch.machine}-unknown-linux-gnu.tar.gz` | `delta-{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | `delta` | no | `git-delta` |
| eza | eza-community/eza | `eza_{arch.machine}-unknown-linux-gnu.tar.gz` | *(none — brew only)* | 0 | `eza` | no | `eza` |
| zoxide | ajeetdsouza/zoxide | `zoxide-{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `zoxide-{ver}-{arch.machine}-apple-darwin.tar.gz` | 0 | `zoxide` | no | `zoxide` |
| fzf | junegunn/fzf | `fzf-{ver}-linux_{arch.go}.tar.gz` | `fzf-{ver}-darwin_{arch.go}.tar.gz` | 0 | `fzf` | no | `fzf` |
| lazygit | jesseduffield/lazygit | `lazygit_{ver}_linux_{arch.suffix}.tar.gz` | `lazygit_{ver}_darwin_{arch.suffix}.tar.gz` | 0 | `lazygit` | no | `lazygit` |
| gh | cli/cli | `gh_{ver}_linux_{arch.deb}.tar.gz` | *(none — zip only — brew)* | 1 | `bin/gh` | no | `gh` |
| yq | mikefarah/yq | `yq_linux_{arch.deb}` | `yq_darwin_{arch.deb}` | — | `yq` | **yes** | `yq` |

**`ArchTokens` reference** (`installer/assets.py`): for `amd64` → `machine=x86_64, deb=amd64, go=amd64, suffix=x86_64`; for `arm64` → `machine=aarch64, deb=arm64, go=arm64, suffix=arm64`.

**Known ragged-arch gaps (acceptable — engine falls through to `brew`):** delta/fd have no x86_64 (Intel) mac asset; ripgrep has no aarch64-linux musl asset; eza/gh have no usable macOS tarball. In every case the missing asset 404s → `CommandError` → engine tries the next ladder method (`brew`). This is by design (`engine.install_tool` already falls through on `CommandError`/`ExecutorError`/`VersionError`).

---

## File Structure

- `installer/versions.py` — **modify**: resolver returns the raw tag (rename `resolve_github_version`→`resolve_github_tag`, `VersionResolver`→`TagResolver`).
- `installer/download.py` — **modify**: URL uses raw tag + `v`-stripped `{ver}`; extraction unpacks to `~/.local/opt/<bin>/` + symlinks; rename the threaded `resolve_version`→`resolve_tag`.
- `installer/locations.py` — **modify**: add `opt_dir(name)`.
- `installer/engine.py`, `installer/session.py`, `installer/app.py` — **modify**: propagate the `TagResolver`/`resolve_tag` rename through the seam.
- `installer/registry.toml` — **modify**: add 11 tools; replace the existing `rg` `github_release` method with the OS-split, strip-aware form.
- `tests/test_versions.py`, `tests/test_download.py`, `tests/test_engine.py`, `tests/test_session.py`, `tests/test_app.py` — **modify**: follow the rename + new extraction behavior.
- `tests/test_registry.py` — **modify**: add per-platform resolution tests for the new tools.
- `tests/test_locations.py` — **modify/create**: cover `opt_dir`.
- `README.md`, memory `roadmap-status.md` — **modify**: document the catalog + location policy.

---

## Task 1: Version→tag contract (raw tag, honest rename)

**Files:**
- Modify: `installer/versions.py`
- Modify: `installer/download.py` (`_github_release_url`, `ExecContext`, import)
- Modify: `installer/engine.py`, `installer/session.py`, `installer/app.py` (rename propagation)
- Test: `tests/test_versions.py`, `tests/test_download.py`, `tests/test_engine.py`, `tests/test_session.py`, `tests/test_app.py`

**Why:** `download.py` hardcodes `releases/download/v{ver}/`, but the resolver strips the leading `v` and the builder re-adds it. For projects whose tag is a bare number (ripgrep `15.1.0`, delta `0.19.2`) the result is `/download/v15.1.0/` → **404**. The fix is to keep the raw tag for the path and derive a `v`-stripped `{ver}` only for the asset filename. The function literally named `resolve_*version*` would then return `"v10.4.2"`, so rename it for honesty.

- [ ] **Step 1: Rewrite the failing test for the resolver returning the raw tag**

Replace the version-extraction tests in `tests/test_versions.py`. The resolver must now return the tag **verbatim**:

```python
import json

import pytest

from installer.versions import VersionError, resolve_github_tag


def _fetch(tag: str):
    def fetch(url: str) -> bytes:
        return json.dumps({"tag_name": tag}).encode()

    return fetch


def test_resolve_returns_tag_verbatim_with_leading_v():
    assert resolve_github_tag("sharkdp/fd", _fetch("v10.4.2")) == "v10.4.2"


def test_resolve_returns_bare_tag_verbatim():
    # ripgrep / delta ship tags with no leading 'v'; it must be preserved.
    assert resolve_github_tag("BurntSushi/ripgrep", _fetch("15.1.0")) == "15.1.0"


def test_resolve_raises_when_tag_missing():
    with pytest.raises(VersionError, match="no release tag"):
        resolve_github_tag("a/b", _fetch(""))


def test_resolve_raises_on_bad_json():
    def fetch(url: str) -> bytes:
        return b"not json"

    with pytest.raises(VersionError, match="failed to resolve tag"):
        resolve_github_tag("a/b", fetch)


def test_resolve_raises_on_network_error():
    def fetch(url: str) -> bytes:
        raise OSError("network down")

    with pytest.raises(VersionError, match="failed to resolve tag"):
        resolve_github_tag("a/b", fetch)
```

- [ ] **Step 2: Run it to confirm failure**

Run: `uv run pytest tests/test_versions.py -q`
Expected: FAIL (`resolve_github_tag` undefined / old name still strips `v`).

- [ ] **Step 3: Update `installer/versions.py`**

```python
"""Resolve the latest release tag of a GitHub repository."""

import json
import urllib.request
from collections.abc import Callable

# Resolve a repo ("owner/name") to its latest release tag, verbatim. The leading-'v'
# convention varies per project (fd: "v10.4.2"; ripgrep: "15.1.0"), and the raw tag is
# exactly what the release *download path* uses, so it must NOT be stripped here.
TagResolver = Callable[[str], str]

# Fetch raw bytes at a URL. Injected in tests; defaults to urllib.
Fetch = Callable[[str], bytes]


class VersionError(RuntimeError):
    """Raised when a GitHub release tag cannot be resolved."""


def urlopen_fetch(url: str) -> bytes:
    """Fetch raw bytes from a URL using urllib. Default Fetch implementation."""
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read()


def resolve_github_tag(repo: str, fetch: Fetch = urlopen_fetch) -> str:
    """Return the latest release tag for owner/repo, verbatim (leading 'v' preserved)."""
    try:
        raw = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionError(f"failed to resolve tag for {repo}: {exc}") from exc
    tag = str(data.get("tag_name", ""))
    if not tag:
        raise VersionError(f"no release tag for {repo}")
    return tag
```

- [ ] **Step 4: Propagate the rename through the seam**

In `installer/download.py`:
- Import: `from installer.versions import TagResolver` (drop `VersionResolver`).
- `ExecContext.resolve_version: VersionResolver` → `resolve_tag: TagResolver`.
- Rewrite `_github_release_url`:

```python
def _github_release_url(method: Method, ctx: ExecContext) -> str:
    repo = require_str(method, "repo")
    template = require_str(method, "asset")
    tag = ctx.resolve_tag(repo)
    ver = tag.removeprefix("v")  # asset filenames use the bare number; the path uses the tag
    try:
        asset = render_asset(template, ver, arch_tokens(ctx.platform.arch))
    except ValueError as exc:
        raise ExecutorError(f"cannot build asset name for '{repo}': {exc}") from exc
    return f"https://github.com/{repo}/releases/download/{tag}/{asset}"
```

In `installer/engine.py`:
- Import: `from installer.versions import TagResolver, VersionError, resolve_github_tag`.
- `install_tool(..., resolve_version: VersionResolver = resolve_github_version)` → `resolve_tag: TagResolver = resolve_github_tag`.
- `ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)`.

In `installer/session.py`:
- Import: `from installer.versions import TagResolver, resolve_github_tag`.
- `Install = Callable[[Tool, Platform, Runner, TagResolver], InstallOutcome]` (update the comment too).
- `run_installs(..., resolve_tag: TagResolver = resolve_github_tag, ...)` and pass `resolve_tag` to `install(...)`.

In `installer/app.py`:
- Import: `from installer.versions import TagResolver, resolve_github_tag`.
- `run_wizard(..., resolve_tag: TagResolver = resolve_github_tag, ...)` and pass `resolve_tag` to `run_installs(...)`.

- [ ] **Step 5: Update the affected tests for the rename**

- `tests/test_download.py`: the helper `_ctx` builds `ExecContext(..., resolve_tag=resolve_tag)`; its inner function returns a tag (use `"v14.1.0"`). Update the URL-shape assertions to expect `/download/v14.1.0/` and add one bare-tag case (a method whose resolver returns `"15.1.0"` must produce `/download/15.1.0/`). (The extraction-call assertions are rewritten in Task 2 — keep them compiling for now or mark Task 2 to fix; do not leave the file failing for unrelated reasons.)
- `tests/test_engine.py`: rename the three inner `resolve_version` functions and the `resolve_tag=` kwarg.
- `tests/test_session.py` / `tests/test_app.py`: rename the `resolve_version` parameter in the fake-install signatures and the `resolve_tag=`/positional call sites.

- [ ] **Step 6: Run the full gate**

Run: `make validate && make test`
Expected: PASS, 100% coverage. (If Task 2's extraction assertions in `test_download.py` block this, implement Task 2 before declaring Task 1 done — they share the file.)

- [ ] **Step 7: Commit**

```bash
git add installer/versions.py installer/download.py installer/engine.py installer/session.py installer/app.py tests/
git commit -m "fix: resolve and use the raw release tag for download URLs"
```

---

## Task 2: opt+symlink extraction with strip-components

**Files:**
- Modify: `installer/locations.py` (add `opt_dir`)
- Modify: `installer/download.py` (`install_download`)
- Test: `tests/test_locations.py`, `tests/test_download.py`

**Why:** Real release archives nest the binary under a versioned directory (`fd-v10.4.2-…/fd`) or under `bin/` (`gh_…/bin/gh`). The current code runs `tar -xz -C <bindir> -- <member>` and chmods `<bindir>/<member>`, which only works for a binary at the archive root. Unpack into `~/.local/opt/<bin>/` (stripping `strip` leading components) and symlink the binary into `~/.local/bin`, per the PRD location policy.

- [ ] **Step 1: Write the failing test for `opt_dir`**

Add to `tests/test_locations.py`:

```python
from pathlib import Path

from installer.locations import opt_dir


def test_opt_dir_is_under_local_opt():
    assert opt_dir("fd") == Path.home() / ".local" / "opt" / "fd"
```

- [ ] **Step 2: Run it to confirm failure**

Run: `uv run pytest tests/test_locations.py -q`
Expected: FAIL (`opt_dir` undefined).

- [ ] **Step 3: Add `opt_dir` to `installer/locations.py`**

```python
def opt_dir(name: str) -> Path:
    """Resolve the userspace opt dir for an unpacked app: ~/.local/opt/<name>."""
    return Path.home() / ".local" / "opt" / name
```

- [ ] **Step 4: Rewrite the download tests for opt+symlink**

Replace the archive-extraction assertions in `tests/test_download.py`. An archive method must: ensure the bin dir, ensure `~/.local/opt/<bin>/`, `curl | tar -xz -C <opt> --strip-components=<strip>`, `chmod +x <opt>/<member>`, then `ln -sf <opt>/<member> <bindir>/<bin>`. Raw assets still go straight to the bin dir. Drive `opt_dir` to a temp location by monkeypatching `Path.home` (the existing tests already use `tmp_path` for `bin_dir`; add a `monkeypatch.setattr(Path, "home", lambda: tmp_path)` so the opt dir is sandboxed).

```python
def test_github_release_archive_extracts_to_opt_and_symlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz",
            "member": "rg",
            "strip": 1,
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner, tmp_version="15.1.0"))
    opt = tmp_path / ".local" / "opt" / "rg"
    binary = opt / "rg"
    link = bin_dir / "rg"
    url = (
        "https://github.com/BurntSushi/ripgrep/releases/download/"
        "15.1.0/ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
    )
    extract = (
        f"curl -fsSL -- {shlex.quote(url)}"
        f" | tar -xz -C {shlex.quote(str(opt))} --strip-components=1"
    )
    assert calls == [
        ["sh", "-c", extract],
        ["chmod", "+x", str(binary)],
        ["ln", "-sf", str(binary), str(link)],
    ]
    assert opt.is_dir()


def test_archive_nested_member_uses_basename_for_link_and_opt(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "cli/cli",
            "asset": "gh_{ver}_linux_{arch.deb}.tar.gz",
            "member": "bin/gh",
            "strip": 1,
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner, tmp_version="v2.93.0"))
    opt = tmp_path / ".local" / "opt" / "gh"
    binary = opt / "bin" / "gh"
    link = bin_dir / "gh"
    assert ["chmod", "+x", str(binary)] in calls
    assert ["ln", "-sf", str(binary), str(link)] in calls


def test_strip_defaults_to_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    method = Method(
        kind="tarball",
        params={"url": "https://x/eza.tar.gz", "member": "eza", "bin_dir": str(tmp_path / "bin")},
    )
    install_download(method, _ctx(runner))
    assert any("--strip-components=0" in c[-1] for c in calls if c[0] == "sh")
```

Keep the existing `raw` test (`test_github_release_raw_downloads_binary_directly`) — raw behavior is unchanged except the link/target name derives from `basename(member)`. Keep the error-path tests (`unsupported_kind`, `missing member`, `bad asset`, `unsupported arch`, `bin dir creation failure`). Add an opt-dir creation-failure test mirroring the bin-dir one.

- [ ] **Step 5: Run to confirm failure**

Run: `uv run pytest tests/test_download.py -q`
Expected: FAIL (old extraction shape).

- [ ] **Step 6: Rewrite `install_download` in `installer/download.py`**

Add imports: `from pathlib import PurePosixPath` and `from installer.locations import bin_dir, ensure_dir, opt_dir`. Add an int param helper and rewrite the installer:

```python
def _opt_int(method: Method, key: str, default: int) -> int:
    value = method.params.get(key)
    # bool is an int subclass; reject it so `strip = true` can't mean strip=1.
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def install_download(method: Method, ctx: ExecContext) -> None:
    """Install a release binary into ~/.local/bin (userspace, no sudo).

    Raw single-file assets are written straight into the bin dir. Archives are
    unpacked into ~/.local/opt/<binary>/ (stripping `strip` leading path
    components) and the binary is symlinked into the bin dir — the PRD's
    opt+symlink location policy, which also handles binaries nested under a
    versioned directory inside the archive.
    """
    if method.kind == "github_release":
        url = _github_release_url(method, ctx)
    elif method.kind == "tarball":
        url = require_str(method, "url")
    else:
        raise ExecutorError(f"no download executor for kind '{method.kind}'")

    member = require_str(method, "member")
    binname = PurePosixPath(member).name
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    link = dest / binname
    quoted_url = shlex.quote(url)

    if method.params.get("raw") is True:
        quoted_link = shlex.quote(str(link))
        ctx.runner(["sh", "-c", f"curl -fsSL -o {quoted_link} -- {quoted_url}"])
        ctx.runner(["chmod", "+x", str(link)])
        return

    strip = _opt_int(method, "strip", 0)
    try:
        opt = ensure_dir(opt_dir(binname))
    except OSError as exc:
        raise ExecutorError(f"cannot create opt dir: {exc}") from exc
    binary = opt / member
    quoted_opt = shlex.quote(str(opt))
    ctx.runner(
        [
            "sh",
            "-c",
            f"curl -fsSL -- {quoted_url} | tar -xz -C {quoted_opt} --strip-components={strip}",
        ]
    )
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])
```

- [ ] **Step 7: Run the full gate**

Run: `make validate && make test`
Expected: PASS, 100% coverage.

- [ ] **Step 8: Commit**

```bash
git add installer/download.py installer/locations.py tests/test_download.py tests/test_locations.py
git commit -m "feat: unpack release archives to ~/.local/opt and symlink into bin"
```

---

## Task 3: Registry — rust/musl tools (fd, bat, sd, delta) + fix ripgrep

**Files:**
- Modify: `installer/registry.toml`
- Test: `tests/test_registry.py`

**Why:** These five share the rust target-triple naming with `{arch.machine}` and `strip = 1`. ripgrep's existing `github_release` method is wrong (no `strip`, no OS split, bare-tag path now needed) and is replaced here.

- [ ] **Step 1: Replace `rg`'s `github_release` method and add fd/bat/sd/delta**

In `installer/registry.toml`, replace the existing `rg` `github_release` block (keep `rg`'s `dnf`/`apt`/`pacman`/`brew` methods) with the OS-split form, and append the four new tools. Each new tool gets a linux `github_release` (`os=["debian","arch","fedora"]`), a macOS `github_release` (`os=["macos"]`, omitted for none here), and a `brew` method. Use `member`, `strip`, and `asset` exactly from the Verified Release Facts table.

```toml
# --- ripgrep github_release (replaces the old strip-less, OS-agnostic method) ---
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "BurntSushi/ripgrep"
asset = "ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "rg"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "BurntSushi/ripgrep"
asset = "ripgrep-{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "rg"
strip = 1
# (keep rg's existing dnf/apt/pacman/brew methods below)

[[tool]]
id = "fd"
name = "fd"
category = "search"
cmd = "fd"
priority = "P1"
audience = "both"
desc = "Fast, user-friendly alternative to find"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "sharkdp/fd"
asset = "fd-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "fd"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "sharkdp/fd"
asset = "fd-v{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "fd"
strip = 1
[[tool.method]]
kind = "brew"
formula = "fd"

[[tool]]
id = "bat"
name = "bat"
category = "view"
cmd = "bat"
priority = "P1"
audience = "both"
desc = "A cat clone with syntax highlighting and git integration"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "sharkdp/bat"
asset = "bat-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "bat"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "sharkdp/bat"
asset = "bat-v{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "bat"
strip = 1
[[tool.method]]
kind = "brew"
formula = "bat"

[[tool]]
id = "sd"
name = "sd"
category = "text"
cmd = "sd"
priority = "P2"
audience = "both"
desc = "Intuitive find-and-replace (sed alternative)"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "chmln/sd"
asset = "sd-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "sd"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "chmln/sd"
asset = "sd-v{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "sd"
strip = 1
[[tool.method]]
kind = "brew"
formula = "sd"

[[tool]]
id = "delta"
name = "delta"
category = "git"
cmd = "delta"
priority = "P2"
audience = "both"
desc = "A syntax-highlighting pager for git, diff, and grep output"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "dandavison/delta"
asset = "delta-{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
member = "delta"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "dandavison/delta"
asset = "delta-{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "delta"
strip = 1
[[tool.method]]
kind = "brew"
formula = "git-delta"
```

- [ ] **Step 2: Add resolution tests**

Append to `tests/test_registry.py`:

```python
def test_fd_resolves_per_platform() -> None:
    fd = next(t for t in load_tools(REGISTRY) if t.id == "fd")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    lin = resolve_methods(fd, linux)
    assert lin[0].kind == "github_release"
    assert lin[0].params["asset"] == "fd-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
    assert lin[0].params["strip"] == 1
    assert [m.kind for m in lin] == ["github_release", "brew"]
    mac = resolve_methods(fd, macos)
    assert mac[0].params["asset"] == "fd-v{ver}-{arch.machine}-apple-darwin.tar.gz"


def test_delta_brew_formula_is_git_delta() -> None:
    delta = next(t for t in load_tools(REGISTRY) if t.id == "delta")
    brew = next(m for m in delta.methods if m.kind == "brew")
    assert brew.params["formula"] == "git-delta"


def test_ripgrep_github_release_is_os_split_and_strips() -> None:
    rg = next(t for t in load_tools(REGISTRY) if t.id == "rg")
    gh_methods = [m for m in rg.methods if m.kind == "github_release"]
    assert {tuple(m.os) for m in gh_methods} == {
        ("debian", "arch", "fedora"),
        ("macos",),
    }
    assert all(m.params["strip"] == 1 and m.params["member"] == "rg" for m in gh_methods)
```

- [ ] **Step 3: Run the gate**

Run: `make validate && make test`
Expected: PASS, 100% coverage.

- [ ] **Step 4: Commit**

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add fd, bat, sd, delta and fix ripgrep download method"
```

---

## Task 4: Registry — flat/go tools (eza, zoxide, fzf, lazygit, gh) + yq (raw)

**Files:**
- Modify: `installer/registry.toml`
- Test: `tests/test_registry.py`

**Why:** These use varied arch tokens (`{arch.go}`, `{arch.suffix}`, `{arch.deb}`), `strip = 0` (flat) except gh (`strip = 1`, `member = "bin/gh"`), and two have no macOS tarball (eza, gh → brew only). yq is a single raw binary (`raw = true`).

- [ ] **Step 1: Append the six tools to `installer/registry.toml`**

```toml
[[tool]]
id = "eza"
name = "eza"
category = "view"
cmd = "eza"
priority = "P2"
audience = "both"
desc = "A modern replacement for ls"
# eza publishes no macOS asset; mac installs via brew.
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "eza-community/eza"
asset = "eza_{arch.machine}-unknown-linux-gnu.tar.gz"
member = "eza"
strip = 0
[[tool.method]]
kind = "brew"
formula = "eza"

[[tool]]
id = "zoxide"
name = "zoxide"
category = "nav"
cmd = "zoxide"
priority = "P2"
audience = "both"
desc = "A smarter cd command with frecency-based jumping"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "ajeetdsouza/zoxide"
asset = "zoxide-{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "zoxide"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "ajeetdsouza/zoxide"
asset = "zoxide-{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "zoxide"
strip = 0
[[tool.method]]
kind = "brew"
formula = "zoxide"

[[tool]]
id = "fzf"
name = "fzf"
category = "search"
cmd = "fzf"
priority = "P1"
audience = "both"
desc = "A general-purpose command-line fuzzy finder"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "junegunn/fzf"
asset = "fzf-{ver}-linux_{arch.go}.tar.gz"
member = "fzf"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "junegunn/fzf"
asset = "fzf-{ver}-darwin_{arch.go}.tar.gz"
member = "fzf"
strip = 0
[[tool.method]]
kind = "brew"
formula = "fzf"

[[tool]]
id = "lazygit"
name = "lazygit"
category = "git"
cmd = "lazygit"
priority = "P2"
audience = "both"
desc = "A simple terminal UI for git commands"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "jesseduffield/lazygit"
asset = "lazygit_{ver}_linux_{arch.suffix}.tar.gz"
member = "lazygit"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "jesseduffield/lazygit"
asset = "lazygit_{ver}_darwin_{arch.suffix}.tar.gz"
member = "lazygit"
strip = 0
[[tool.method]]
kind = "brew"
formula = "lazygit"

[[tool]]
id = "gh"
name = "GitHub CLI"
category = "git"
cmd = "gh"
priority = "P1"
audience = "both"
desc = "GitHub on the command line"
# gh ships macOS only as .zip/.pkg; mac installs via brew.
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "cli/cli"
asset = "gh_{ver}_linux_{arch.deb}.tar.gz"
member = "bin/gh"
strip = 1
[[tool.method]]
kind = "brew"
formula = "gh"

[[tool]]
id = "yq"
name = "yq"
category = "data"
cmd = "yq"
priority = "P2"
audience = "ai"
desc = "Portable command-line YAML/JSON processor"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "mikefarah/yq"
asset = "yq_linux_{arch.deb}"
member = "yq"
raw = true
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "mikefarah/yq"
asset = "yq_darwin_{arch.deb}"
member = "yq"
raw = true
[[tool.method]]
kind = "brew"
formula = "yq"
```

- [ ] **Step 2: Add resolution tests**

Append to `tests/test_registry.py`:

```python
def test_eza_has_no_macos_download_only_brew() -> None:
    eza = next(t for t in load_tools(REGISTRY) if t.id == "eza")
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(eza, macos)] == ["brew"]


def test_gh_linux_uses_nested_member_and_strip() -> None:
    gh = next(t for t in load_tools(REGISTRY) if t.id == "gh")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    method = resolve_methods(gh, linux)[0]
    assert method.params["member"] == "bin/gh"
    assert method.params["strip"] == 1


def test_yq_is_raw_download() -> None:
    yq = next(t for t in load_tools(REGISTRY) if t.id == "yq")
    raw_methods = [m for m in yq.methods if m.params.get("raw") is True]
    assert len(raw_methods) == 2
    assert all("tar" not in str(m.params.get("asset", "")) for m in raw_methods)


def test_all_registry_ids_unique_after_expansion() -> None:
    ids = [t.id for t in load_tools(REGISTRY)]
    assert len(ids) == len(set(ids))
    assert {"fd", "bat", "sd", "delta", "eza", "zoxide", "fzf", "lazygit", "gh", "yq"} <= set(ids)
```

- [ ] **Step 3: Run the gate**

Run: `make validate && make test`
Expected: PASS, 100% coverage.

- [ ] **Step 4: Commit**

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add eza, zoxide, fzf, lazygit, gh and yq to the registry"
```

---

## Task 5: Document the catalog and location policy

**Files:**
- Modify: `README.md`
- Modify: `/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md`

**Why:** The README should reflect that the registry now installs a real toolset and explain the opt+symlink policy; the roadmap memory should record Batch 1 as done and list the deferred follow-ups.

- [ ] **Step 1: Update `README.md`**

In the project description / "What it does" area, add a short "Available tools" list grouped by category (search: rg, fd, fzf · view: bat, eza · git: delta, lazygit, gh · data: jq, yq · text: sd · nav: zoxide · pkg-mgr: uv, brew) and a one-paragraph note: download-based tools install without sudo into `~/.local/opt/<tool>/` with a symlink in `~/.local/bin`; macOS-only or Intel-mac gaps fall through to Homebrew. Do not invent flags or behavior — describe only what exists.

- [ ] **Step 2: Update the roadmap memory**

Add a "Batch 1 registry expansion (done)" line listing the 11 tools and the two correctness fixes (raw-tag URL, opt+symlink extraction). Under deferred, record: native package-manager methods for the new tools (per-distro package/binary-name verification needed — e.g. Debian `fd-find`→`fdfind`, `bat`→`batcat`); aarch64-linux ripgrep (no musl asset); checksum/sha256 verification of downloads; the remaining ~25 tools toward the ~40 target.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document the expanded tool catalog and opt+symlink policy"
```

(The memory file lives outside the repo; update it but do not `git add` it.)

---

## Self-Review (completed by plan author)

- **Spec coverage:** "Verified first batch (~8–12)" → 11 tools (Tasks 3–4), each method grounded in live release data. "Fix executor: opt + symlink" → Task 2. Prerequisite tag bug → Task 1. Docs → Task 5. ✓
- **Placeholder scan:** Every code step shows complete code; every asset template/`strip`/`member` is a verified literal. ✓
- **Type consistency:** The rename is applied uniformly — `TagResolver` / `resolve_tag` / `resolve_github_tag` everywhere the old `VersionResolver` / `resolve_version` / `resolve_github_version` appeared (enumerated in Task 1, Step 4). `ExecContext` field is `resolve_tag`. `opt_dir`/`bin_dir`/`ensure_dir` signatures match `installer/locations.py`. ✓
- **Gate discipline:** Every task ends on `make validate && make test` green at 100% coverage; no gate is bypassed. ✓
