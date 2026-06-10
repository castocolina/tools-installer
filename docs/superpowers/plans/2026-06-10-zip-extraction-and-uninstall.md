# Tempfile Extraction, `.zip` Support & `make uninstall` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the download executor extract archives from a temp file (fixing the `curl | tar` pipefail-masking bug), add `.zip` support, and implement a userspace `make uninstall`.

**Architecture:** The archive path stops streaming `curl | tar` and instead `curl`s to a `mktemp` file, then extracts (`tar -xzf` or `unzip`). This single change closes the pipefail hole *and* gives `unzip` the seekable file it requires. A new optional `archive = "zip"` method param selects `unzip`; `member` is rendered through the existing `{ver}`/`{arch.*}` templating so nested zip layouts are addressable. `make uninstall` is the registry-driven symmetric inverse of `install_download`: for each download/raw method, remove `~/.local/opt/<binname>` and `~/.local/bin/<binname>` if present, with a dry-run preview and confirm.

**Tech Stack:** Python 3 (managed by uv), POSIX `sh` via the injected `Runner` seam, `tomllib`, `rich`, `questionary` (composition root only), `pytest` + coverage. Strict gates: ruff, pyright (strict), bandit, vulture, shellcheck. 100% coverage on `installer/`.

**Non-negotiables:** English only. Never bypass a gate (`# noqa` / `# type: ignore` / `# nosec` / `# pragma: no cover` / skips / coverage lowering). Each task ends with `make validate && make test` green and one coherent commit. `setup.py` is the composition root — excluded from pyright/coverage by design (see `Makefile` comment), so wiring there carries no unit test.

---

## Background the implementer needs

`installer/download.py` today (the code you're changing):

```python
def install_download(method: Method, ctx: ExecContext) -> None:
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

`render_asset(template, ver, arch)` (in `installer/assets.py`) substitutes `{ver}` and `{arch.machine|deb|go|suffix}`, raising `ValueError` on a bad template. `arch_tokens(normalized)` maps `amd64`/`arm64` to an `ArchTokens`.

Test helpers in `tests/test_download.py`: `_ctx(runner, tmp_version="v14.1.0")` builds an `ExecContext` on a fedora/amd64 platform whose `resolve_tag` returns `tmp_version`; `_record()` returns `(calls, runner)` capturing every argv.

---

## Task 1: Extract from a temp file (fix the `curl | tar` pipefail bug)

Replace the streaming pipe with a download-to-`mktemp` then `tar -xzf`. No pipe means `curl`'s failure breaks the `&&` chain instead of being masked by `tar`. Behavior is otherwise identical (`tar.gz`, default path). The `raw` path is untouched.

**Files:**
- Modify: `installer/download.py:81-96` (the archive branch)
- Test: `tests/test_download.py` (update two existing tests)

- [ ] **Step 1: Update the two existing archive tests to expect the tempfile command**

In `tests/test_download.py`, replace the `extract = (...)` expression in `test_github_release_archive_extracts_to_opt_and_symlinks` (lines 58-61) with:

```python
    extract = (
        'tmp=$(mktemp) && trap \'rm -f "$tmp"\' EXIT'
        f' && curl -fsSL -o "$tmp" -- {shlex.quote(url)}'
        f' && tar -xzf "$tmp" -C {shlex.quote(str(opt))} --strip-components=1'
    )
```

And in `test_tarball_uses_url_verbatim_and_strip_defaults_to_zero` replace the `extract = (...)` expression (lines 109-112) with:

```python
    extract = (
        'tmp=$(mktemp) && trap \'rm -f "$tmp"\' EXIT'
        f' && curl -fsSL -o "$tmp" -- {shlex.quote("https://x/eza.tar.gz")}'
        f' && tar -xzf "$tmp" -C {shlex.quote(str(opt))} --strip-components=0'
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_download.py -q`
Expected: FAIL — the two updated tests fail because `install_download` still emits the `curl ... | tar -xz` pipe.

- [ ] **Step 3: Implement the tempfile extraction**

In `installer/download.py`, replace the `ctx.runner([...])` block that currently builds the `curl ... | tar -xz` command (lines 88-94) with:

```python
    extract = (
        'tmp=$(mktemp) && trap \'rm -f "$tmp"\' EXIT'
        f' && curl -fsSL -o "$tmp" -- {quoted_url}'
        f' && tar -xzf "$tmp" -C {quoted_opt} --strip-components={strip}'
    )
    ctx.runner(["sh", "-c", extract])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_download.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates pass; coverage 100%.

```bash
git add installer/download.py tests/test_download.py
git commit -m "fix: extract archives from a temp file, closing the curl|tar pipefail hole"
```

---

## Task 2: Add `.zip` support via an `archive` method param

A new optional param `archive` selects the extractor: absent or `"tar.gz"` → `tar -xzf` (Task 1's command); `"zip"` → `unzip -q -o`. `unzip` has no `--strip-components`, so for zip the archive extracts whole and `strip` is ignored.

**Files:**
- Modify: `installer/download.py` (the archive branch from Task 1)
- Test: `tests/test_download.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_download.py`:

```python
def test_github_release_zip_uses_unzip_and_ignores_strip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "denoland/deno",
            "asset": "deno-{arch.machine}-unknown-linux-gnu.zip",
            "member": "deno",
            "archive": "zip",
            "strip": 3,  # must be ignored for zip
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner, tmp_version="v2.1.4"))
    opt = tmp_path / ".local" / "opt" / "deno"
    binary = opt / "deno"
    link = bin_dir / "deno"
    url = (
        "https://github.com/denoland/deno/releases/download/"
        "v2.1.4/deno-x86_64-unknown-linux-gnu.zip"
    )
    extract = (
        'tmp=$(mktemp) && trap \'rm -f "$tmp"\' EXIT'
        f' && curl -fsSL -o "$tmp" -- {shlex.quote(url)}'
        f' && unzip -q -o "$tmp" -d {shlex.quote(str(opt))}'
    )
    assert calls == [
        ["sh", "-c", extract],
        ["chmod", "+x", str(binary)],
        ["ln", "-sf", str(binary), str(link)],
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_download.py::test_github_release_zip_uses_unzip_and_ignores_strip -v`
Expected: FAIL — `install_download` always emits the `tar -xzf` command regardless of `archive`.

- [ ] **Step 3: Implement the `archive` branch**

In `installer/download.py`, replace the single `extract = (...)` assignment from Task 1 with a per-archive selection:

```python
    if _opt_str(method, "archive") == "zip":
        extract = (
            'tmp=$(mktemp) && trap \'rm -f "$tmp"\' EXIT'
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && unzip -q -o "$tmp" -d {quoted_opt}'
        )
    else:
        extract = (
            'tmp=$(mktemp) && trap \'rm -f "$tmp"\' EXIT'
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && tar -xzf "$tmp" -C {quoted_opt} --strip-components={strip}'
        )
    ctx.runner(["sh", "-c", extract])
```

Note: `_opt_str` already returns `None` for a missing/empty/non-string param, so `archive` absent → the `else` (tar) branch. `strip` is computed above the branch as today and simply unused on the zip side.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_download.py -q`
Expected: PASS (all tests, including the tar.gz tests from Task 1).

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates pass; coverage 100%.

```bash
git add installer/download.py tests/test_download.py
git commit -m "feat: add .zip archive support to the download executor"
```

---

## Task 3: Render `member` through `{ver}`/`{arch.*}` templating

So nested zip layouts (e.g. `bun-<arch>/bun`) are addressable, `member` is rendered with the same tokens as `asset`. This consolidates URL+member resolution into one helper. For `tarball` (no version) `member` is used verbatim.

**Files:**
- Modify: `installer/download.py` (replace `_github_release_url`; adjust `install_download`)
- Test: `tests/test_download.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_download.py`:

```python
def test_member_is_rendered_with_ver_and_arch_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "oven-sh/bun",
            "asset": "bun-linux-{arch.deb}.zip",
            "member": "bun-linux-{arch.deb}/bun",  # nested under a templated dir
            "archive": "zip",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner, tmp_version="bun-v1.1.38"))
    opt = tmp_path / ".local" / "opt" / "bun"  # link/opt key is the basename
    binary = opt / "bun-linux-amd64" / "bun"  # {arch.deb} rendered
    link = bin_dir / "bun"
    assert ["chmod", "+x", str(binary)] in calls
    assert ["ln", "-sf", str(binary), str(link)] in calls
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_download.py::test_member_is_rendered_with_ver_and_arch_tokens -v`
Expected: FAIL — `member` is used verbatim, so `binary`/`link` paths still contain the literal `{arch.deb}`.

- [ ] **Step 3: Replace `_github_release_url` with a combined resolver**

In `installer/download.py`, delete `_github_release_url` (lines 38-47) and add:

```python
def _resolve_target(method: Method, ctx: ExecContext) -> tuple[str, str]:
    """Return (download url, member path), rendering {ver}/{arch.*} where a version is known.

    github_release templates both the asset and the member with the resolved
    tag's bare version and the platform arch tokens. tarball has no version, so
    its url and member are used verbatim.
    """
    try:
        tokens = arch_tokens(ctx.platform.arch)
    except ValueError as exc:
        raise ExecutorError(f"cannot build asset name: {exc}") from exc
    raw_member = require_str(method, "member")
    if method.kind == "github_release":
        repo = require_str(method, "repo")
        template = require_str(method, "asset")
        tag = ctx.resolve_tag(repo)
        ver = tag.removeprefix("v")  # asset/member use the bare number; the path uses the tag
        try:
            asset = render_asset(template, ver, tokens)
            member = render_asset(raw_member, ver, tokens)
        except ValueError as exc:
            raise ExecutorError(f"cannot build asset name for '{repo}': {exc}") from exc
        return f"https://github.com/{repo}/releases/download/{tag}/{asset}", member
    if method.kind == "tarball":
        return require_str(method, "url"), raw_member
    raise ExecutorError(f"no download executor for kind '{method.kind}'")
```

Then in `install_download`, replace the opening kind-dispatch and the `member = require_str(...)` line:

```python
    url, member = _resolve_target(method, ctx)
    binname = PurePosixPath(member).name
```

(Delete the old `if method.kind == "github_release": ... else: raise ExecutorError(...)` block and the standalone `member = require_str(method, "member")` line — `_resolve_target` now handles both, including the unsupported-kind error.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_download.py -q`
Expected: PASS (all). The existing error-path tests still hold: `test_unsupported_kind_raises` (`ExecutorError` matching `"brew"`), `test_missing_required_param_raises` (`"member"`), `test_github_release_bad_asset_template_raises_executor_error` (`"asset"`), and `test_github_release_unsupported_arch_raises_executor_error` (`"asset"`). The last one passes because `_resolve_target` wraps `arch_tokens` in a `try` that re-raises `riscv64`'s `ValueError` as an `ExecutorError` whose message contains `"asset name"` — before any runner call, so `calls == []` remains true.

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates pass; coverage 100%.

```bash
git add installer/download.py tests/test_download.py
git commit -m "feat: render download member through {ver}/{arch.*} templating"
```

---

## Task 4: `shellrc.remove_managed_block`

Add the inverse of `apply_block`: strip the marked PATH block from a file (idempotent; missing file or missing block → no change).

**Files:**
- Modify: `installer/shellrc.py`
- Test: `tests/test_shellrc.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_shellrc.py` (imports at top of that file already cover `shellrc`; add what's missing):

```python
def test_remove_managed_block_strips_only_the_block(tmp_path):
    from installer.shellrc import remove_managed_block, write_myshellrc

    path = tmp_path / ".myshellrc"
    path.write_text("# user line\n")
    write_myshellrc([tmp_path / "bin"], path)
    assert "tools-installer path" in path.read_text()
    remove_managed_block(path)
    text = path.read_text()
    assert "tools-installer path" not in text
    assert "# user line" in text  # user content preserved


def test_remove_managed_block_is_idempotent_and_tolerates_absence(tmp_path):
    from installer.shellrc import remove_managed_block

    path = tmp_path / ".myshellrc"
    remove_managed_block(path)  # missing file -> no error, no file created
    assert not path.exists()
    path.write_text("# only user content\n")
    remove_managed_block(path)  # no block present -> unchanged
    assert path.read_text() == "# only user content\n"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_shellrc.py -q`
Expected: FAIL — `ImportError: cannot import name 'remove_managed_block'`.

- [ ] **Step 3: Implement `remove_managed_block`**

Add to `installer/shellrc.py`:

```python
def remove_managed_block(path: Path) -> None:
    """Strip the managed PATH block from `path`, preserving the rest. Idempotent.

    Pairs the LAST begin marker with the following end marker (mirroring
    apply_block). A missing file or a file without the block is left untouched.
    """
    if not path.exists():
        return
    lines = path.read_text().split("\n")
    if _PATH_BEGIN not in lines:
        return
    start = max(index for index, line in enumerate(lines) if line == _PATH_BEGIN)
    for stop in range(start, len(lines)):
        if lines[stop] == _PATH_END:
            kept = lines[:start] + lines[stop + 1 :]
            path.write_text("\n".join(kept))
            return
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_shellrc.py -q`
Expected: PASS.

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates pass; coverage 100%.

```bash
git add installer/shellrc.py tests/test_shellrc.py
git commit -m "feat: add shellrc.remove_managed_block for uninstall"
```

---

## Task 5: `installer/uninstall.py` — registry-driven removal

Compute the userspace artifacts the download/raw executors create, then remove the ones that exist.

**Files:**
- Create: `installer/uninstall.py`
- Test: `tests/test_uninstall.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_uninstall.py`:

```python
from pathlib import Path

import pytest

from installer.model import Method, Tool
from installer.uninstall import plan_uninstall, remove_paths


def _tool(method: Method, *, tool_id: str = "t", cmd: str = "t") -> Tool:
    # methods is tuple[Method, ...]; priority/audience/desc use their defaults.
    return Tool(id=tool_id, name=tool_id, category="dev", cmd=cmd, methods=(method,))


def test_plan_collects_existing_opt_and_bin_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("binary")
    (bin_dir / "fd").symlink_to(opt / "fd")
    tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"})
    )
    paths = plan_uninstall([tool], bin_dir)
    assert set(paths) == {opt, bin_dir / "fd"}


def test_plan_skips_absent_paths_and_nondownload_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    # brew method contributes nothing; download method's paths don't exist yet.
    brew_tool = _tool(Method(kind="brew", params={"formula": "x"}), tool_id="b", cmd="b")
    dl_tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"})
    )
    assert plan_uninstall([brew_tool, dl_tool], bin_dir) == []


def test_plan_uses_basename_of_nested_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "gh"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    tool = _tool(
        Method(kind="github_release", params={"repo": "cli/cli", "asset": "x", "member": "bin/gh"})
    )
    assert set(plan_uninstall([tool], bin_dir)) == {opt}  # opt exists, bin/gh symlink does not


def test_plan_includes_dangling_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "fd").symlink_to(tmp_path / "gone")  # target missing -> dangling
    tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"})
    )
    assert plan_uninstall([tool], bin_dir) == [bin_dir / "fd"]


def test_remove_paths_deletes_dirs_files_and_symlinks(tmp_path: Path):
    opt = tmp_path / "opt" / "fd"
    opt.mkdir(parents=True)
    (opt / "fd").write_text("bin")
    real = tmp_path / "real"
    real.write_text("x")
    link = tmp_path / "link"
    link.symlink_to(real)
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "missing")
    remove_paths([opt, link, dangling])
    assert not opt.exists()
    assert not link.is_symlink()
    assert not dangling.is_symlink()
    assert real.exists()  # the symlink target itself is preserved
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_uninstall.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.uninstall'`.

- [ ] **Step 3: Implement `installer/uninstall.py`**

```python
"""Registry-driven uninstall: remove the userspace artifacts install_download creates."""

import shutil
from pathlib import Path, PurePosixPath

from installer.download import DOWNLOAD_KINDS
from installer.locations import opt_dir
from installer.model import Tool


def _exists(path: Path) -> bool:
    # is_symlink catches dangling links (exists() is False when the target is gone).
    return path.exists() or path.is_symlink()


def plan_uninstall(tools: list[Tool], default_bin_dir: Path) -> list[Path]:
    """Existing opt dirs and bin entries the download/raw executors would have created.

    The registry is the manifest: every download/raw method maps to opt_dir(binname)
    and <bin_dir>/binname, where binname is the basename of the method's member.
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
            if method.kind not in DOWNLOAD_KINDS:
                continue
            member = method.params.get("member")
            if not isinstance(member, str) or not member:
                continue
            binname = PurePosixPath(member).name
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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_uninstall.py -q`
Expected: PASS.

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates pass (vulture sees both functions used by tests); coverage 100%.

```bash
git add installer/uninstall.py tests/test_uninstall.py
git commit -m "feat: add registry-driven uninstall path planner and remover"
```

---

## Task 6: `render_uninstall` + `app.run_uninstall` orchestrator

A dry-run preview renderer and the orchestration: plan → preview → confirm → remove → strip the managed block.

**Files:**
- Modify: `installer/render.py`
- Modify: `installer/app.py`
- Test: `tests/test_render.py`, `tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render.py`:

```python
def test_render_uninstall_lists_paths():
    from rich.console import Console

    from installer.render import render_uninstall

    console = Console(record=True, width=80)
    render_uninstall([Path("/x/opt/fd"), Path("/x/bin/fd")], console)
    text = console.export_text()
    assert "/x/opt/fd" in text
    assert "/x/bin/fd" in text


def test_render_uninstall_reports_nothing_to_do():
    from rich.console import Console

    from installer.render import render_uninstall

    console = Console(record=True, width=80)
    render_uninstall([], console)
    assert "Nothing to uninstall" in console.export_text()
```

(`from pathlib import Path` is already imported at the top of `tests/test_render.py`; add it if not.)

Add to `tests/test_app.py`:

```python
def test_run_uninstall_removes_when_confirmed(tmp_path, monkeypatch):
    import pytest

    from installer.app import run_uninstall
    from installer.model import Method, Tool
    from installer.shellrc import write_myshellrc

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("bin")
    (bin_dir / "fd").symlink_to(opt / "fd")
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)
    tool = Tool(
        id="fd", name="fd", category="search", cmd="fd",
        methods=(Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),),
    )
    removed = run_uninstall(
        [tool], Console(record=True),
        default_bin_dir=bin_dir, myshellrc_path=myshellrc, confirm=lambda _m: True,
    )
    assert set(removed) == {opt, bin_dir / "fd"}
    assert not opt.exists()
    assert "tools-installer path" not in myshellrc.read_text()


def test_run_uninstall_aborts_when_declined(tmp_path, monkeypatch):
    from installer.app import run_uninstall
    from installer.model import Method, Tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (bin_dir / "fd").symlink_to(opt)
    tool = Tool(
        id="fd", name="fd", category="search", cmd="fd",
        methods=(Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),),
    )
    removed = run_uninstall(
        [tool], Console(record=True),
        default_bin_dir=bin_dir, myshellrc_path=tmp_path / ".myshellrc", confirm=lambda _m: False,
    )
    assert removed == []
    assert opt.exists()  # nothing removed


def test_run_uninstall_nothing_to_remove_skips_confirm(tmp_path, monkeypatch):
    from installer.app import run_uninstall
    from installer.model import Method, Tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = Tool(
        id="fd", name="fd", category="search", cmd="fd",
        methods=(Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),),
    )

    def fail_confirm(_message: str) -> bool:
        raise AssertionError("confirm must not be called when there is nothing to remove")

    removed = run_uninstall(
        [tool], Console(record=True),
        default_bin_dir=bin_dir, myshellrc_path=tmp_path / ".myshellrc", confirm=fail_confirm,
    )
    assert removed == []
```

(Ensure `tests/test_app.py` imports `from pathlib import Path` and `from rich.console import Console` at the top — add any that are missing.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_render.py tests/test_app.py -q`
Expected: FAIL — `render_uninstall` and `run_uninstall` do not exist.

- [ ] **Step 3: Implement `render_uninstall`**

Add to `installer/render.py`:

```python
def render_uninstall(paths: list[Path], console: Console) -> None:
    """Preview the artifacts that will be removed (dry run)."""
    if not paths:
        console.print("Nothing to uninstall: no tools-installer artifacts found.")
        return
    console.print("The following will be removed:")
    for path in paths:
        console.print(f"  {path}")
```

Add the import at the top of `installer/render.py`:

```python
from pathlib import Path
```

- [ ] **Step 4: Implement `run_uninstall`**

Add to `installer/app.py`. Extend the existing imports:

```python
from installer.render import render_audit, render_doctor, render_summary, render_uninstall
from installer.shellrc import collect_bin_dirs, ensure_source, remove_managed_block, write_myshellrc
from installer.uninstall import plan_uninstall, remove_paths
```

Then add the function:

```python
def run_uninstall(
    tools: list[Tool],
    console: Console,
    *,
    default_bin_dir: Path,
    myshellrc_path: Path,
    confirm: Callable[[str], bool],
) -> list[Path]:
    """Preview userspace artifacts, confirm, then remove them and strip the PATH block.

    Returns the removed paths ([] if there was nothing to remove or the user declined).
    """
    paths = plan_uninstall(tools, default_bin_dir)
    render_uninstall(paths, console)
    if not paths:
        return []
    if not confirm("Remove these artifacts?"):
        return []
    remove_paths(paths)
    remove_managed_block(myshellrc_path)
    return paths
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_render.py tests/test_app.py -q`
Expected: PASS.

- [ ] **Step 6: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates pass; coverage 100%.

```bash
git add installer/render.py installer/app.py tests/test_render.py tests/test_app.py
git commit -m "feat: add uninstall preview renderer and run_uninstall orchestrator"
```

---

## Task 7: `--uninstall` CLI flag

**Files:**
- Modify: `installer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
def test_uninstall_flag_defaults_false():
    assert parse_args([]).uninstall is False


def test_uninstall_flag_parses():
    assert parse_args(["--uninstall"]).uninstall is True
```

(`parse_args` is already imported in `tests/test_cli.py`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL — `Options` has no `uninstall` attribute / unknown `--uninstall`.

- [ ] **Step 3: Implement the flag**

In `installer/cli.py`, add the field to `Options` (after `doctor`):

```python
    doctor: bool = False
    uninstall: bool = False
```

Register the argument (after the `--doctor` line):

```python
    parser.add_argument(
        "--uninstall", action="store_true", help="remove installed userspace artifacts, then exit"
    )
```

And thread it into the returned `Options`:

```python
    return Options(
        all=ns.all,
        categories=tuple(categories),
        yes=ns.yes,
        doctor=ns.doctor,
        uninstall=ns.uninstall,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates pass; coverage 100%.

```bash
git add installer/cli.py tests/test_cli.py
git commit -m "feat: add --uninstall CLI flag"
```

---

## Task 8: Wire `--uninstall` into `setup.py` and `make uninstall`

Composition-root wiring (no unit tests — `setup.py` is excluded from pyright/coverage by design) plus the README docs.

**Files:**
- Modify: `setup.py`
- Modify: `Makefile:22-23`
- Modify: `README.md` (the `make uninstall` row + a short note)

- [ ] **Step 1: Add the `_run_uninstall` helper and route it in `setup.py`**

In `setup.py`, extend the import:

```python
from installer.app import configure_path, run_doctor, run_uninstall, run_wizard
```

Add the helper (after `_run_doctor`):

```python
def _run_uninstall(console: Console, *, assume_yes: bool) -> int:
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    run_uninstall(
        load_tools(_REGISTRY),
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        confirm=confirm,
    )
    return 0
```

Route it in `main`, right after the `options.doctor` check:

```python
    if options.uninstall:
        return _run_uninstall(console, assume_yes=options.yes)
```

- [ ] **Step 2: Point the Makefile target at the wizard**

In `Makefile`, replace the `uninstall` recipe (lines 22-23):

```makefile
uninstall:  ## Remove installed userspace artifacts (opt dirs, bin symlinks, PATH block)
	uv run setup.py --uninstall
```

- [ ] **Step 3: Update the README**

In `README.md`, change the `make uninstall` table row (line 163) to:

```
| `make uninstall` | remove userspace artifacts: `~/.local/opt/*`, `~/.local/bin` symlinks, the `~/.myshellrc` PATH block (interactive; add `ARGS` is not needed — it confirms first) |
```

And in the "Available tools" / ladder area (after the opt+symlink paragraph at lines 57-59), add a sentence:

```
Archives may be `.tar.gz` or `.zip` (set `archive = "zip"` on the method); both are
downloaded to a temp file and extracted into `~/.local/opt/<tool>/`. `make uninstall`
reverses this — it removes those opt dirs, the matching `~/.local/bin` symlinks, and
the managed `~/.myshellrc` block, leaving Homebrew/native/uv installs untouched.
```

- [ ] **Step 4: Validate, test, and smoke-check the flag**

Run: `make validate && make test`
Expected: all gates pass; coverage 100% (no new `installer/` lines went uncovered — the only additions here are in `setup.py`, which is out of coverage).

Smoke check (no artifacts present → "nothing to uninstall", exits 0):

Run: `printf 'n\n' | uv run setup.py --uninstall`
Expected: prints `Nothing to uninstall: no tools-installer artifacts found.` (or a preview + a declined prompt if you happen to have artifacts), exits 0.

- [ ] **Step 5: Commit**

```bash
git add setup.py Makefile README.md
git commit -m "feat: wire --uninstall into setup.py and make uninstall"
```

---

## Final review

After all tasks: dispatch a holistic code reviewer over the whole diff (`git diff main...HEAD` if on a branch, else the range of commits from this plan), then run `make validate && make test` once more on the final tree. Confirm:

- The `curl | tar` pipe is gone from `download.py` (grep for `| tar` returns nothing).
- `.zip` and `.tar.gz` both extract from a temp file with a cleanup `trap`.
- `make uninstall` removes only userspace artifacts and is existence-gated.
- 100% coverage on `installer/`; all gates green.

Then update `roadmap-status.md` memory: the `.zip` extractor and `make uninstall` deferred items are now **done**; note that Batch 4 (JS-runtime tier on the proven `.zip` path) is the natural next step.
```
