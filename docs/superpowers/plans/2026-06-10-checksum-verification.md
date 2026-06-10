# sha256 Checksum Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the sha256 digest of every `github_release` download that ships a published checksum, with ask-the-user handling on mismatch (hard-fail under `--yes`) and visible verified/unverified markers.

**Architecture:** A new pure module `installer/checksums.py` parses checksum files and hashes downloads. `download.py` gains a verified flow: the Runner curls the asset + checksum file into a Python-owned temp dir, Python compares digests, then extraction proceeds from the verified file. `engine.py` returns a distinct `checksum-mismatch` outcome (no fall-through by default; `checksum_policy="continue"` restores it). `session.run_installs` drives the retry/skip/fallback choice via an `on_mismatch` callback that `setup.py` backs with questionary. Spec: `docs/superpowers/specs/2026-06-10-checksum-verification-design.md`.

**Tech Stack:** Python ≥3.11 (`hashlib.file_digest`, `tempfile.mkdtemp`), uv, pytest (offline; mocked Runner that writes fixture files), TOML registry.

**Project rules that bind every task:**
- Validate with `make validate && make test` before every commit — the editor's `<new-diagnostics>` blocks are stale out-of-venv noise; ignore them.
- Never add `# noqa` / `# type: ignore` / `# nosec` / `# pragma: no cover` / coverage exclusions. 100% coverage on `installer/` via focused tests.
- A hook re-runs `ruff format` on `registry.toml`/test files after edits — re-read a file before further edits if it reports reformatting.
- Commit messages in English with trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

| File | Responsibility |
|---|---|
| `installer/checksums.py` (create) | Pure: parse checksum-file text, hash files, `ChecksumMismatch` |
| `installer/download.py` (modify) | `DownloadTarget` resolution (incl. `{asset}` token + checksum URL); verified install flow; returns `verified: bool` |
| `installer/engine.py` (modify) | `checksum-mismatch` status, `verified` on `InstallOutcome`, `checksum_policy` |
| `installer/session.py` (modify) | `Install` Protocol, `on_mismatch` retry/skip/fallback loop, `Summary.mismatched` |
| `installer/render.py` (modify) | `render_verification` lines, mismatch bucket in `render_summary` |
| `installer/app.py` (modify) | `run_wizard` threads `on_mismatch`, calls `render_verification` |
| `setup.py` (modify) | `_ask_mismatch` questionary select; exit code covers mismatches |
| `installer/registry.toml` (modify) | `checksum = "…"` on swept `github_release` methods |
| `tests/test_checksums.py` (create), `tests/test_download.py`, `tests/test_engine.py`, `tests/test_session.py`, `tests/test_render.py`, `tests/test_app.py`, `tests/test_registry.py` (modify) | TDD coverage |
| `README.md` (modify) | verified column in the tool catalog |

---

### Task 1: `installer/checksums.py` — pure parsing and hashing

**Files:**
- Create: `installer/checksums.py`
- Create: `tests/test_checksums.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_checksums.py`:

```python
import hashlib
from pathlib import Path

from installer.checksums import ChecksumMismatch, expected_sha256, sha256_file

RG = "ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
HASH_A = "a" * 64
HASH_B = "b" * 64


def test_multiline_checksums_file_finds_asset_hash():
    text = f"{HASH_A}  other.tar.gz\n{HASH_B}  {RG}\n"
    assert expected_sha256(text, RG) == HASH_B


def test_binary_marker_star_is_ignored():
    assert expected_sha256(f"{HASH_B} *{RG}\n", RG) == HASH_B


def test_sidecar_single_line_with_name_matches():
    assert expected_sha256(f"{HASH_B}  {RG}\n", RG) == HASH_B


def test_bare_hash_sidecar_matches_any_asset():
    assert expected_sha256(f"{HASH_B}\n", RG) == HASH_B


def test_path_prefixed_name_matches_by_basename():
    assert expected_sha256(f"{HASH_B}  ./dist/{RG}\n", RG) == HASH_B


def test_uppercase_hex_is_normalized_to_lower():
    assert expected_sha256(f"{'B' * 64}  {RG}\n", RG) == HASH_B


def test_crlf_lines_are_handled():
    text = f"{HASH_A}  other.tar.gz\r\n{HASH_B}  {RG}\r\n"
    assert expected_sha256(text, RG) == HASH_B


def test_asset_not_listed_returns_none():
    assert expected_sha256(f"{HASH_A}  other.tar.gz\n", RG) is None


def test_multiple_bare_hashes_are_not_a_sidecar():
    assert expected_sha256(f"{HASH_A}\n{HASH_B}\n", RG) is None


def test_non_hex_token_is_rejected():
    assert expected_sha256(f"{'z' * 64}  {RG}\n", RG) is None


def test_wrong_length_token_is_rejected():
    assert expected_sha256(f"{'a' * 63}  {RG}\n", RG) is None


def test_empty_text_returns_none():
    assert expected_sha256("", RG) is None


def test_sha256_file_hashes_bytes(tmp_path: Path):
    payload = b"tools-installer"
    target = tmp_path / "asset.tar.gz"
    target.write_bytes(payload)
    assert sha256_file(target) == hashlib.sha256(payload).hexdigest()


def test_checksum_mismatch_message_shows_asset_and_short_digests():
    exc = ChecksumMismatch("a.tar.gz", "12345678" + "a" * 56, "fedcba98" + "b" * 56)
    assert exc.asset == "a.tar.gz"
    assert "a.tar.gz" in str(exc)
    assert "12345678" in str(exc)
    assert "fedcba98" in str(exc)
    assert exc.expected.startswith("12345678")
    assert exc.actual.startswith("fedcba98")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_checksums.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.checksums'`

- [ ] **Step 3: Write the implementation**

Create `installer/checksums.py`:

```python
"""Parse published sha256 checksum files and hash downloaded assets."""

import hashlib
from pathlib import Path, PurePosixPath


class ChecksumMismatch(Exception):
    """A downloaded asset's sha256 digest differs from the published one.

    Deliberately NOT an ExecutorError subclass: the engine's generic
    fall-through except must not swallow the security signal.
    """

    def __init__(self, asset: str, expected: str, actual: str) -> None:
        self.asset = asset
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"checksum mismatch for {asset}: expected {expected[:8]}…, got {actual[:8]}…"
        )


def expected_sha256(text: str, asset: str) -> str | None:
    """Find the published sha256 for `asset` in a checksum file's content.

    Handles multi-line `<hash>  <name>` files (including the `*<name>` binary
    marker and path-prefixed names), single-line sidecars, and bare-hash
    sidecar files. Returns None when the asset has no entry.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and _names_match(parts[1], asset) and _is_sha256(parts[0]):
            return parts[0].lower()
    if len(lines) == 1 and len(lines[0].split()) == 1 and _is_sha256(lines[0]):
        return lines[0].lower()
    return None


def _names_match(listed: str, asset: str) -> bool:
    name = listed.lstrip("*")
    return name == asset or PurePosixPath(name).name == asset


def _is_sha256(token: str) -> bool:
    if len(token) != 64:
        return False
    try:
        int(token, 16)
    except ValueError:
        return False
    return True


def sha256_file(path: Path) -> str:
    """Streaming sha256 hex digest of a file."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_checksums.py -v`
Expected: all PASS

- [ ] **Step 5: Validate and commit**

Run: `make validate && make test`
Expected: 0 errors, 244+15 tests pass, 100% coverage

```bash
git add installer/checksums.py tests/test_checksums.py
git commit -m "feat: pure sha256 checksum parsing and hashing module

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `download.py` — `DownloadTarget` resolution with checksum URL

Pure refactor of `_resolve_target` into a dataclass + new checksum-name resolution (`{asset}` token, tarball rejection). The unverified install flow's argv stays **byte-identical** — existing tests must pass unchanged.

**Files:**
- Modify: `installer/download.py`
- Test: `tests/test_download.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_download.py`:

```python
def test_install_download_returns_false_when_unverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _, runner = _record()
    method = Method(
        kind="tarball",
        params={"url": "https://x/eza.tar.gz", "member": "eza", "bin_dir": str(tmp_path / "bin")},
    )
    assert install_download(method, _ctx(runner)) is False


def test_tarball_with_checksum_param_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _, runner = _record()
    method = Method(
        kind="tarball",
        params={"url": "https://x/eza.tar.gz", "member": "eza", "checksum": "SHA256SUMS"},
    )
    with pytest.raises(ExecutorError, match="only supported for github_release"):
        install_download(method, _ctx(runner))


def test_bad_checksum_template_raises_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _, runner = _record()
    method = Method(
        kind="github_release",
        params={
            "repo": "x/y",
            "asset": "tool-{ver}.tar.gz",
            "member": "tool",
            "checksum": "tool-{arch.nope}.sha256",
        },
    )
    with pytest.raises(ExecutorError, match="cannot build checksum name"):
        install_download(method, _ctx(runner, tmp_version="1.0.0"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_download.py -v`
Expected: the three new tests FAIL (`install_download` returns `None`, no checksum handling); all pre-existing tests PASS

- [ ] **Step 3: Refactor `_resolve_target` and split the install flow**

In `installer/download.py`, replace `_resolve_target` and `install_download` (keep `_opt_str` / `_opt_int` as-is). New imports at the top:

```python
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from installer.assets import arch_tokens, render_asset
from installer.checksums import ChecksumMismatch, expected_sha256, sha256_file
from installer.executors import ExecutorError, require_str
from installer.locations import bin_dir, ensure_dir, opt_dir
from installer.model import Method
from installer.platform import Platform
from installer.run import Runner
from installer.versions import TagResolver
```

(`shutil`, `tempfile`, `ChecksumMismatch`, `expected_sha256`, `sha256_file`, and `Path` are used by Task 3's verified flow; add them now so the imports are stable.)

```python
@dataclass(frozen=True)
class DownloadTarget:
    """A resolved download: where to fetch, what to extract, how to verify."""

    url: str
    member: str
    asset: str  # the download's filename; names the temp file in the verified flow
    checksum: tuple[str, str] | None = None  # (checksum url, checksum filename)


def _resolve_target(method: Method, ctx: ExecContext) -> DownloadTarget:
    """Resolve the download URL, member path, and optional checksum source.

    github_release templates asset/member/checksum with the resolved tag's
    bare version and the platform arch tokens; `{asset}` in the checksum
    template expands to the already-rendered asset name. tarball is verbatim
    and does not support checksums (no registry entry needs it).
    """
    try:
        tokens = arch_tokens(ctx.platform.arch)
    except ValueError as exc:
        raise ExecutorError(f"cannot build asset name: {exc}") from exc
    raw_member = require_str(method, "member")
    checksum_template = _opt_str(method, "checksum")
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
        base = f"https://github.com/{repo}/releases/download/{tag}"
        if checksum_template is None:
            return DownloadTarget(url=f"{base}/{asset}", member=member, asset=asset)
        try:
            checksum_name = render_asset(checksum_template.replace("{asset}", asset), ver, tokens)
        except ValueError as exc:
            raise ExecutorError(f"cannot build checksum name for '{repo}': {exc}") from exc
        return DownloadTarget(
            url=f"{base}/{asset}",
            member=member,
            asset=asset,
            checksum=(f"{base}/{checksum_name}", checksum_name),
        )
    if method.kind == "tarball":
        if checksum_template is not None:
            raise ExecutorError("checksum verification is only supported for github_release")
        url = require_str(method, "url")
        return DownloadTarget(url=url, member=raw_member, asset=PurePosixPath(url).name)
    raise ExecutorError(f"no download executor for kind '{method.kind}'")


def install_download(method: Method, ctx: ExecContext) -> bool:
    """Install a release binary into ~/.local/bin (userspace, no sudo).

    Returns True when the download was sha256-verified against a published
    checksum, False otherwise. Raw single-file assets go straight into the
    bin dir; archives unpack into ~/.local/opt/<binary>/ with the binary
    symlinked into the bin dir (the PRD's opt+symlink location policy).
    """
    target = _resolve_target(method, ctx)
    binname = PurePosixPath(target.member).name
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    link = dest / binname
    if target.checksum is None:
        _install_unverified(method, ctx, target, link)
        return False
    _install_verified(method, ctx, target, link, target.checksum)
    return True


def _install_unverified(
    method: Method, ctx: ExecContext, target: DownloadTarget, link: Path
) -> None:
    """The pre-checksum flow: curl|extract via a shell-side mktemp. Argv unchanged."""
    quoted_url = shlex.quote(target.url)
    if method.params.get("raw") is True:
        quoted_link = shlex.quote(str(link))
        ctx.runner(["sh", "-c", f"curl -fsSL -o {quoted_link} -- {quoted_url}"])
        ctx.runner(["chmod", "+x", str(link)])
        return
    strip = _opt_int(method, "strip", 0)
    try:
        opt = ensure_dir(opt_dir(link.name))
    except OSError as exc:
        raise ExecutorError(f"cannot create opt dir: {exc}") from exc
    binary = opt / target.member
    quoted_opt = shlex.quote(str(opt))
    quoted_member = shlex.quote(target.member)
    if _opt_str(method, "archive") == "zip":
        extract = (
            "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && unzip -q -o "$tmp" {quoted_member} -d {quoted_opt}'
        )
    else:
        extract = (
            "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && tar -xzf "$tmp" -C {quoted_opt} --strip-components={strip}'
        )
    ctx.runner(["sh", "-c", extract])
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])
```

For this task only, add a temporary stub so the module imports cleanly (Task 3 replaces it with the real flow — it raises, so coverage never reaches a placeholder branch; no registry entry declares `checksum` yet):

```python
def _install_verified(
    method: Method, ctx: ExecContext, target: DownloadTarget, link: Path, checksum: tuple[str, str]
) -> None:
    raise ExecutorError("checksum verification not yet wired")
```

NOTE: if `make test` flags the stub's line as uncovered, fold Task 3 into this commit instead of suppressing anything — never add a pragma. (Task 3's tests cover it immediately either way; squash the two tasks into one commit if needed.)

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest tests/test_download.py -v && make test`
Expected: all download tests PASS including the three new ones. If the `_install_verified` stub line shows as uncovered in `make test`, proceed directly to Task 3 and commit both tasks together.

- [ ] **Step 5: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add installer/download.py tests/test_download.py
git commit -m "refactor: resolve downloads into DownloadTarget with checksum source

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `download.py` — the verified install flow

**Files:**
- Modify: `installer/download.py` (replace the `_install_verified` stub)
- Test: `tests/test_download.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_download.py`. Also add to the file's imports:

```python
import hashlib

from installer import download
from installer.checksums import ChecksumMismatch
```

```python
def _workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pin the verified flow's temp dir to a known path."""
    workdir = tmp_path / "dl"
    workdir.mkdir()

    def fake_mkdtemp(prefix: str) -> str:
        return str(workdir)

    monkeypatch.setattr(download.tempfile, "mkdtemp", fake_mkdtemp)
    return workdir


def _fixture_runner(workdir: Path, files: dict[str, bytes]) -> tuple[list[list[str]], Runner]:
    """Record argv; when the fetch command runs, drop the given files into workdir."""
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd[0] == "sh" and "curl" in cmd[2]:
            for name, content in files.items():
                (workdir / name).write_bytes(content)

    return calls, runner


def _rg_method(bin_dir_path: Path) -> Method:
    return Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz",
            "member": "rg",
            "strip": 1,
            "checksum": "{asset}.sha256",
            "bin_dir": str(bin_dir_path),
        },
    )


RG_ASSET = "ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
RG_BASE = "https://github.com/BurntSushi/ripgrep/releases/download/15.1.0"


def test_verified_archive_fetches_verifies_and_extracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    payload = b"archive-bytes"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {RG_ASSET}\n".encode()
    calls, runner = _fixture_runner(workdir, {RG_ASSET: payload, f"{RG_ASSET}.sha256": sums})
    bindir = tmp_path / "bin"
    assert install_download(_rg_method(bindir), _ctx(runner, tmp_version="15.1.0")) is True
    opt = tmp_path / ".local" / "opt" / "rg"
    fetch = (
        f"curl -fsSL -o {shlex.quote(str(workdir / RG_ASSET))} -- {shlex.quote(f'{RG_BASE}/{RG_ASSET}')}"
        f" && curl -fsSL -o {shlex.quote(str(workdir / RG_ASSET) + '.sha256')}"
        f" -- {shlex.quote(f'{RG_BASE}/{RG_ASSET}.sha256')}"
    )
    assert calls == [
        ["sh", "-c", fetch],
        ["tar", "-xzf", str(workdir / RG_ASSET), "-C", str(opt), "--strip-components=1"],
        ["chmod", "+x", str(opt / "rg")],
        ["ln", "-sf", str(opt / "rg"), str(bindir / "rg")],
    ]
    assert not workdir.exists()  # temp dir removed after success


def test_verified_mismatch_raises_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    sums = f"{'0' * 64}  {RG_ASSET}\n".encode()  # wrong digest
    calls, runner = _fixture_runner(workdir, {RG_ASSET: b"archive-bytes", f"{RG_ASSET}.sha256": sums})
    with pytest.raises(ChecksumMismatch) as excinfo:
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert excinfo.value.asset == RG_ASSET
    assert excinfo.value.expected == "0" * 64
    assert len(calls) == 1  # fetch only; no extraction commands after the mismatch
    assert not workdir.exists()  # temp dir removed on the failure path too


def test_verified_missing_entry_is_ordinary_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    sums = f"{'0' * 64}  some-other-asset.tar.gz\n".encode()
    _, runner = _fixture_runner(workdir, {RG_ASSET: b"x", f"{RG_ASSET}.sha256": sums})
    with pytest.raises(ExecutorError, match="no sha256 entry"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert not workdir.exists()


def test_verified_unreadable_checksum_file_is_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    _, runner = _fixture_runner(workdir, {RG_ASSET: b"x"})  # checksum file never written
    with pytest.raises(ExecutorError, match="cannot read checksum file"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))


def test_verified_missing_asset_file_is_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    sums = f"{'0' * 64}  {RG_ASSET}\n".encode()
    _, runner = _fixture_runner(workdir, {f"{RG_ASSET}.sha256": sums})  # asset never written
    with pytest.raises(ExecutorError, match="cannot hash downloaded asset"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))


def test_verified_raw_copies_from_temp_into_bin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "yq_linux_amd64"
    payload = b"raw-binary"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {asset}\n".encode()
    calls, runner = _fixture_runner(workdir, {asset: payload, "checksums.txt": sums})
    bindir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "mikefarah/yq",
            "asset": "yq_linux_{arch.deb}",
            "member": "yq",
            "raw": True,
            "checksum": "checksums.txt",
            "bin_dir": str(bindir),
        },
    )
    assert install_download(method, _ctx(runner, tmp_version="v4.44.0")) is True
    assert calls[1:] == [
        ["cp", str(workdir / asset), str(bindir / "yq")],
        ["chmod", "+x", str(bindir / "yq")],
    ]


def test_verified_zip_extracts_member_from_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "deno-x86_64-unknown-linux-gnu.zip"
    payload = b"zip-bytes"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {asset}\n".encode()
    calls, runner = _fixture_runner(workdir, {asset: payload, f"{asset}.sha256sum": sums})
    bindir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "denoland/deno",
            "asset": "deno-{arch.machine}-unknown-linux-gnu.zip",
            "member": "deno",
            "archive": "zip",
            "checksum": "{asset}.sha256sum",
            "bin_dir": str(bindir),
        },
    )
    assert install_download(method, _ctx(runner, tmp_version="v2.0.0")) is True
    opt = tmp_path / ".local" / "opt" / "deno"
    assert calls[1:] == [
        ["unzip", "-q", "-o", str(workdir / asset), "deno", "-d", str(opt)],
        ["chmod", "+x", str(opt / "deno")],
        ["ln", "-sf", str(opt / "deno"), str(bindir / "deno")],
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_download.py -v`
Expected: new tests FAIL with `ExecutorError: checksum verification not yet wired`; old tests PASS

- [ ] **Step 3: Replace the `_install_verified` stub with the real flow**

```python
def _install_verified(
    method: Method, ctx: ExecContext, target: DownloadTarget, link: Path, checksum: tuple[str, str]
) -> None:
    """Fetch asset + checksum file into a temp dir, verify the digest, then install.

    A missing entry for the asset is registry/upstream drift — an ordinary
    ExecutorError that falls through to the next method. A present-but-wrong
    digest is the security signal — ChecksumMismatch, which stops the ladder.
    """
    checksum_url, checksum_name = checksum
    workdir = Path(tempfile.mkdtemp(prefix="tools-installer-"))
    try:
        asset_path = workdir / target.asset
        sum_path = workdir / checksum_name
        fetch = (
            f"curl -fsSL -o {shlex.quote(str(asset_path))} -- {shlex.quote(target.url)}"
            f" && curl -fsSL -o {shlex.quote(str(sum_path))} -- {shlex.quote(checksum_url)}"
        )
        ctx.runner(["sh", "-c", fetch])
        try:
            text = sum_path.read_text()
        except OSError as exc:
            raise ExecutorError(f"cannot read checksum file '{checksum_name}': {exc}") from exc
        expected = expected_sha256(text, target.asset)
        if expected is None:
            raise ExecutorError(f"no sha256 entry for '{target.asset}' in '{checksum_name}'")
        try:
            actual = sha256_file(asset_path)
        except OSError as exc:
            raise ExecutorError(f"cannot hash downloaded asset '{target.asset}': {exc}") from exc
        if actual != expected:
            raise ChecksumMismatch(target.asset, expected, actual)
        _place_verified(method, ctx, target, link, asset_path)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _place_verified(
    method: Method, ctx: ExecContext, target: DownloadTarget, link: Path, asset_path: Path
) -> None:
    """Install a verified download from its temp path (plain argv, no shell)."""
    if method.params.get("raw") is True:
        ctx.runner(["cp", str(asset_path), str(link)])
        ctx.runner(["chmod", "+x", str(link)])
        return
    try:
        opt = ensure_dir(opt_dir(link.name))
    except OSError as exc:
        raise ExecutorError(f"cannot create opt dir: {exc}") from exc
    binary = opt / target.member
    if _opt_str(method, "archive") == "zip":
        ctx.runner(["unzip", "-q", "-o", str(asset_path), target.member, "-d", str(opt)])
    else:
        strip = _opt_int(method, "strip", 0)
        ctx.runner(["tar", "-xzf", str(asset_path), "-C", str(opt), f"--strip-components={strip}"])
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_download.py -v && make test`
Expected: all PASS, 100% coverage (the mismatch/missing/unreadable branches are each exercised)

- [ ] **Step 5: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add installer/download.py tests/test_download.py
git commit -m "feat: sha256-verify github_release downloads before extraction

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `engine.py` — `checksum-mismatch` outcome, `verified`, `checksum_policy`

**Files:**
- Modify: `installer/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_engine.py`. Add imports:

```python
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
```

```python
def _mismatching_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_install_download(method: Method, ctx: ExecContext) -> bool:
        raise ChecksumMismatch("a.tar.gz", "0" * 64, "f" * 64)

    monkeypatch.setattr(engine.download, "install_download", fake_install_download)


def _not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)


def _gh_then_brew() -> Tool:
    return _tool(
        Method(kind="github_release", params={"repo": "x/y", "asset": "a", "member": "rg"}),
        Method(kind="brew", params={"formula": "ripgrep"}),
    )


def test_checksum_mismatch_halts_the_ladder_by_default(monkeypatch: pytest.MonkeyPatch):
    _not_installed(monkeypatch)
    _mismatching_download(monkeypatch)
    calls: list[list[str]] = []
    outcome = install_tool(_gh_then_brew(), _platform(), runner=lambda cmd: calls.append(cmd))
    assert outcome.status == "checksum-mismatch"
    assert outcome.method_kind == "github_release"
    assert isinstance(outcome.errors[0], ChecksumMismatch)
    assert calls == []  # brew was never attempted


def test_checksum_policy_continue_falls_through_to_brew(monkeypatch: pytest.MonkeyPatch):
    _not_installed(monkeypatch)
    _mismatching_download(monkeypatch)
    calls: list[list[str]] = []
    outcome = install_tool(
        _gh_then_brew(),
        _platform(),
        runner=lambda cmd: calls.append(cmd),
        checksum_policy="continue",
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "brew"
    assert calls == [["brew", "install", "ripgrep"]]


def test_installed_outcome_carries_verified_flag(monkeypatch: pytest.MonkeyPatch):
    _not_installed(monkeypatch)

    def fake_install_download(method: Method, ctx: ExecContext) -> bool:
        return True

    monkeypatch.setattr(engine.download, "install_download", fake_install_download)
    outcome = install_tool(
        _tool(Method(kind="github_release", params={"repo": "x/y", "asset": "a", "member": "rg"})),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert outcome.verified is True


def test_non_download_install_is_not_marked_verified(monkeypatch: pytest.MonkeyPatch):
    _not_installed(monkeypatch)
    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert outcome.verified is False
```

NOTE: if the brew executor's argv in `test_checksum_policy_continue_falls_through_to_brew` differs (check an existing brew test in this file for the exact command), copy the exact argv from that existing test. The platform may also need `has_brew=True` — mirror how `test_falls_through_to_next_method_on_failure` builds it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine.py -v`
Expected: new tests FAIL (`install_tool` has no `checksum_policy`, `InstallOutcome` has no `verified`, status literal lacks `checksum-mismatch`)

- [ ] **Step 3: Implement**

In `installer/engine.py`:

```python
"""Install a tool by walking its resolved priority ladder until one method works."""

from dataclasses import dataclass
from typing import Literal

from installer import download, executors
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.model import Method, Tool
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner, run_command
from installer.status import is_installed
from installer.versions import TagResolver, VersionError, resolve_github_tag

Status = Literal["already-installed", "installed", "no-method", "failed", "checksum-mismatch"]
ChecksumPolicy = Literal["fail", "continue"]


@dataclass(frozen=True)
class InstallOutcome:
    tool_id: str
    status: Status
    method_kind: str | None = None
    errors: tuple[Exception, ...] = ()
    verified: bool = False


def _perform(method: Method, ctx: ExecContext) -> bool:
    """Route download kinds to the download executor; everything else to a command executor.

    Returns True when the download was sha256-verified (non-download methods
    are never marked verified — their package managers do their own checks).
    """
    if method.kind in download.DOWNLOAD_KINDS:
        return download.install_download(method, ctx)
    executors.execute(method, ctx.runner)
    return False


def install_tool(
    tool: Tool,
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    *,
    checksum_policy: ChecksumPolicy = "fail",
) -> InstallOutcome:
    """Try each applicable method in ladder order; stop at the first success.

    A checksum mismatch halts the ladder by default (the security signal must
    not silently degrade to another channel); checksum_policy="continue"
    restores ordinary fall-through and is only ever set by an explicit user
    choice.
    """
    if is_installed(tool):
        return InstallOutcome(tool.id, "already-installed")

    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, "no-method")

    ctx = ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)
    errors: list[Exception] = []
    for method in methods:
        try:
            verified = _perform(method, ctx)
            return InstallOutcome(tool.id, "installed", method_kind=method.kind, verified=verified)
        except ChecksumMismatch as exc:
            if checksum_policy == "fail":
                return InstallOutcome(
                    tool.id, "checksum-mismatch", method_kind=method.kind, errors=(exc,)
                )
            errors.append(exc)
        except (CommandError, executors.ExecutorError, VersionError) as exc:
            errors.append(exc)
    return InstallOutcome(tool.id, "failed", errors=tuple(errors))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine.py -v && make test`
Expected: PASS. `summarize` in `session.py` will KeyError on a `"checksum-mismatch"` outcome — that bucket is added in Task 5; no existing test produces that status through `summarize`, so the suite stays green.

- [ ] **Step 5: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add installer/engine.py tests/test_engine.py
git commit -m "feat: checksum-mismatch outcome halts the install ladder by default

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `session.py` — `Install` Protocol, `on_mismatch` loop, `Summary.mismatched`

**Files:**
- Modify: `installer/session.py`
- Test: `tests/test_session.py` (and the two `Install` fakes: `tests/test_session.py`, `tests/test_app.py`)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_session.py`. Add imports:

```python
from installer.engine import ChecksumPolicy
from installer.session import MismatchChoice
```

```python
def _mismatch_then_install() -> tuple[list[tuple[str, str]], object]:
    """An Install fake that mismatches on the first call per tool, then installs."""
    seen: list[tuple[str, str]] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: object,
        resolve_tag: object,
        *,
        checksum_policy: ChecksumPolicy = "fail",
    ) -> InstallOutcome:
        seen.append((tool.id, checksum_policy))
        if len([s for s in seen if s[0] == tool.id]) == 1 and checksum_policy == "fail":
            return InstallOutcome(tool.id, "checksum-mismatch", method_kind="github_release")
        return InstallOutcome(tool.id, "installed", method_kind="github_release")

    return seen, install


def test_on_mismatch_retry_reinstalls_with_default_policy():
    seen, install = _mismatch_then_install()

    def on_mismatch(tool_id: str) -> MismatchChoice:
        return "retry"

    outcomes = run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install, on_mismatch
    )
    assert seen == [("rg", "fail"), ("rg", "fail")]
    assert outcomes[0].status == "installed"


def test_on_mismatch_fallback_reinstalls_with_continue_policy():
    seen, install = _mismatch_then_install()

    def on_mismatch(tool_id: str) -> MismatchChoice:
        return "fallback"

    outcomes = run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install, on_mismatch
    )
    assert seen == [("rg", "fail"), ("rg", "continue")]
    assert outcomes[0].status == "installed"


def test_on_mismatch_skip_keeps_the_mismatch_outcome():
    seen, install = _mismatch_then_install()

    def on_mismatch(tool_id: str) -> MismatchChoice:
        return "skip"

    outcomes = run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install, on_mismatch
    )
    assert seen == [("rg", "fail")]
    assert outcomes[0].status == "checksum-mismatch"


def test_without_on_mismatch_the_outcome_stands():
    seen, install = _mismatch_then_install()
    outcomes = run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install
    )
    assert seen == [("rg", "fail")]
    assert outcomes[0].status == "checksum-mismatch"


def test_on_mismatch_is_not_consulted_for_clean_installs():
    asked: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: object,
        resolve_tag: object,
        *,
        checksum_policy: ChecksumPolicy = "fail",
    ) -> InstallOutcome:
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    def on_mismatch(tool_id: str) -> MismatchChoice:
        asked.append(tool_id)
        return "skip"

    run_installs([_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install, on_mismatch)
    assert asked == []


def test_summarize_buckets_checksum_mismatch():
    outcomes = [
        InstallOutcome("rg", "installed"),
        InstallOutcome("fd", "checksum-mismatch"),
    ]
    summary = summarize(outcomes)
    assert summary.installed == ("rg",)
    assert summary.mismatched == ("fd",)
```

Adapt the calls above to this file's existing local helpers (`_tool`, `_platform`); if the existing `fake_install` signatures use `plat`, rename that parameter to `platform` and add the keyword-only `checksum_policy: ChecksumPolicy = "fail"` so they satisfy the new Protocol. Apply the same signature update to `_recording_install` in `tests/test_app.py`. If existing tests construct `Summary(...)` directly, add `mismatched=()`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_session.py -v`
Expected: new tests FAIL (no `MismatchChoice`, `run_installs` takes no 6th argument, `Summary` has no `mismatched`)

- [ ] **Step 3: Implement**

In `installer/session.py`:

```python
"""Orchestrate installs for a selection of tools and bucket the outcomes."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from installer.engine import ChecksumPolicy, InstallOutcome, install_tool
from installer.model import Tool
from installer.platform import Platform
from installer.run import Runner, run_command
from installer.versions import TagResolver, resolve_github_tag

# The user's answer to a checksum mismatch: retry the download, skip the
# tool, or fall back to the remaining methods (brew/native).
MismatchChoice = Literal["retry", "skip", "fallback"]
OnMismatch = Callable[[str], MismatchChoice]

_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


class Install(Protocol):
    """Matches engine.install_tool, including the keyword-only checksum policy."""

    def __call__(
        self,
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = ...,
    ) -> InstallOutcome: ...


@dataclass(frozen=True)
class Summary:
    installed: tuple[str, ...]
    already: tuple[str, ...]
    failed: tuple[str, ...]
    no_method: tuple[str, ...]
    mismatched: tuple[str, ...] = ()


def order_for_install(tools: list[Tool]) -> list[Tool]:
    """Stable sort by priority (P0 first); ties keep catalog order."""
    return sorted(tools, key=lambda tool: _PRIORITY_RANK.get(tool.priority, 99))


def run_installs(
    tools: list[Tool],
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: Install = install_tool,
    on_mismatch: OnMismatch | None = None,
) -> list[InstallOutcome]:
    """Install each tool in turn, collecting one outcome per tool.

    On a checksum mismatch, consult on_mismatch (when given): retry re-runs
    the install once, fallback re-runs it letting the ladder continue past
    the mismatch, skip keeps the mismatch outcome. No callback = unattended
    mode: the hard-fail outcome stands.
    """
    outcomes: list[InstallOutcome] = []
    for tool in tools:
        outcome = install(tool, platform, runner, resolve_tag)
        if outcome.status == "checksum-mismatch" and on_mismatch is not None:
            choice = on_mismatch(tool.id)
            if choice == "retry":
                outcome = install(tool, platform, runner, resolve_tag)
            elif choice == "fallback":
                outcome = install(tool, platform, runner, resolve_tag, checksum_policy="continue")
        outcomes.append(outcome)
    return outcomes


def summarize(outcomes: list[InstallOutcome]) -> Summary:
    """Bucket outcome tool ids by status.

    The keys mirror engine.Status (a closed Literal); an out-of-range status
    is impossible under pyright and would surface as a KeyError if one ever
    slipped through, rather than being silently dropped.
    """
    buckets: dict[str, list[str]] = {
        "installed": [],
        "already-installed": [],
        "failed": [],
        "no-method": [],
        "checksum-mismatch": [],
    }
    for outcome in outcomes:
        buckets[outcome.status].append(outcome.tool_id)
    return Summary(
        installed=tuple(buckets["installed"]),
        already=tuple(buckets["already-installed"]),
        failed=tuple(buckets["failed"]),
        no_method=tuple(buckets["no-method"]),
        mismatched=tuple(buckets["checksum-mismatch"]),
    )
```

- [ ] **Step 4: Run the full suite; fix the two fakes**

Run: `uv run pytest -x -q`
Expected: PASS after updating the `Install` fakes in `tests/test_session.py` and `tests/test_app.py` to the Protocol signature (parameter names `tool, platform, runner, resolve_tag` plus keyword-only `checksum_policy: ChecksumPolicy = "fail"`).

- [ ] **Step 5: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add installer/session.py tests/test_session.py tests/test_app.py
git commit -m "feat: mismatch retry/skip/fallback loop and mismatch summary bucket

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `render.py` — verification lines and the mismatch bucket

**Files:**
- Modify: `installer/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`, following the file's existing Console capture pattern (`Console(record=True)` + `export_text()`, or whatever the file already uses — mirror it exactly). Add imports:

```python
from installer.engine import InstallOutcome
from installer.render import render_verification
```

```python
def test_render_verification_marks_download_outcomes():
    console = Console(record=True)
    outcomes = [
        InstallOutcome("rg", "installed", method_kind="github_release", verified=True),
        InstallOutcome("fd", "installed", method_kind="github_release", verified=False),
        InstallOutcome("jq", "installed", method_kind="brew"),
    ]
    render_verification(outcomes, console)
    text = console.export_text()
    assert "rg: sha256 ✓" in text
    assert "fd: unverified" in text
    assert "jq" not in text  # brew does its own integrity checks


def test_render_verification_prints_mismatch_error():
    console = Console(record=True)
    exc = ChecksumMismatch("a.tar.gz", "12345678" + "a" * 56, "fedcba98" + "b" * 56)
    outcomes = [
        InstallOutcome("rg", "checksum-mismatch", method_kind="github_release", errors=(exc,))
    ]
    render_verification(outcomes, console)
    text = console.export_text()
    assert "rg" in text
    assert "12345678" in text
    assert "fedcba98" in text


def test_render_summary_includes_mismatch_bucket():
    console = Console(record=True)
    summary = Summary(
        installed=("rg",), already=(), failed=(), no_method=(), mismatched=("fd",)
    )
    render_summary(summary, console)
    text = console.export_text()
    assert "Checksum mismatch: 1" in text
    assert "checksum mismatch: fd" in text
```

(Import `ChecksumMismatch` from `installer.checksums` and `Summary` from `installer.session` if not already imported in this file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL — `render_verification` does not exist; summary line lacks the mismatch bucket

- [ ] **Step 3: Implement**

In `installer/render.py`, add imports:

```python
from installer.download import DOWNLOAD_KINDS
from installer.engine import InstallOutcome
```

Update `render_summary` (counts line + buckets loop):

```python
def render_summary(summary: Summary, console: Console) -> None:
    """Print install counts and the tool ids in each bucket."""
    console.print(
        f"Installed: {len(summary.installed)}  "
        f"Already: {len(summary.already)}  "
        f"Failed: {len(summary.failed)}  "
        f"Checksum mismatch: {len(summary.mismatched)}  "
        f"No method: {len(summary.no_method)}"
    )
    for label, ids in (
        ("installed", summary.installed),
        ("already installed", summary.already),
        ("failed", summary.failed),
        ("checksum mismatch", summary.mismatched),
        ("no method", summary.no_method),
    ):
        if ids:
            console.print(f"  {label}: {', '.join(ids)}")
```

Add `render_verification`:

```python
def render_verification(outcomes: list[InstallOutcome], console: Console) -> None:
    """One line per download-based install: sha256-verified, unverified, or mismatched.

    brew/native/script installs are omitted — those channels run their own
    integrity checks, so an 'unverified' label there would mislead.
    """
    for outcome in outcomes:
        if outcome.method_kind not in DOWNLOAD_KINDS:
            continue
        if outcome.status == "installed":
            marker = "sha256 ✓" if outcome.verified else "unverified"
            console.print(f"  {outcome.tool_id}: {marker}")
        elif outcome.status == "checksum-mismatch":
            console.print(f"  {outcome.tool_id}: {outcome.errors[0]}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render.py -v && make test`
Expected: PASS

- [ ] **Step 5: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add installer/render.py tests/test_render.py
git commit -m "feat: render sha256 verification markers and mismatch bucket

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: `app.run_wizard` — thread `on_mismatch`, render verification

**Files:**
- Modify: `installer/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app.py`, reusing this file's existing fixtures (`FakePrompter`-style prompter, `parse_args`, `_never_installed`). Add imports:

```python
from installer.engine import ChecksumPolicy
from installer.session import MismatchChoice
```

```python
def _mismatching_install() -> tuple[list[str], Install]:
    attempts: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: object,
        resolve_tag: object,
        *,
        checksum_policy: ChecksumPolicy = "fail",
    ) -> InstallOutcome:
        attempts.append(checksum_policy)
        return InstallOutcome(tool.id, "checksum-mismatch", method_kind="github_release")

    return attempts, install


def test_wizard_consults_on_mismatch_when_interactive(tmp_path: Path):
    attempts, install = _mismatching_install()
    asked: list[str] = []

    def on_mismatch(tool_id: str) -> MismatchChoice:
        asked.append(tool_id)
        return "skip"

    summary = run_wizard(
        [_tool("rg")],
        _platform(),
        _prompter(confirm=True),
        Console(record=True),
        parse_args(["--all"]),
        runner=lambda cmd: None,
        resolve_tag=lambda repo: "1.0.0",
        install=install,
        installed=_never_installed,
        on_mismatch=on_mismatch,
    )
    assert asked == ["rg"]
    assert summary is not None
    assert summary.mismatched == ("rg",)


def test_wizard_suppresses_on_mismatch_under_yes(tmp_path: Path):
    attempts, install = _mismatching_install()
    asked: list[str] = []

    def on_mismatch(tool_id: str) -> MismatchChoice:
        asked.append(tool_id)
        return "retry"

    summary = run_wizard(
        [_tool("rg")],
        _platform(),
        _prompter(confirm=True),
        Console(record=True),
        parse_args(["--all", "--yes"]),
        runner=lambda cmd: None,
        resolve_tag=lambda repo: "1.0.0",
        install=install,
        installed=_never_installed,
        on_mismatch=on_mismatch,
    )
    assert asked == []  # unattended: never prompt, hard-fail stands
    assert summary is not None
    assert summary.mismatched == ("rg",)
    assert attempts == ["fail"]
```

Mirror this file's existing helper names exactly (`_tool`, `_platform`, prompter construction) — if a helper has a different name or signature, adapt the new tests to it, not the other way around.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_app.py -v`
Expected: new tests FAIL (`run_wizard` has no `on_mismatch` parameter)

- [ ] **Step 3: Implement**

In `installer/app.py`: add `OnMismatch` and `render_verification` to the imports:

```python
from installer.render import (
    render_audit,
    render_doctor,
    render_rc_duplicates,
    render_summary,
    render_uninstall,
    render_verification,
)
from installer.session import (
    Install,
    OnMismatch,
    Summary,
    order_for_install,
    run_installs,
    summarize,
)
```

Update `run_wizard`:

```python
def run_wizard(
    tools: list[Tool],
    platform: Platform,
    prompter: Prompter,
    console: Console,
    options: Options,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: Install = install_tool,
    installed: Callable[[Tool], bool] = is_installed,
    on_mismatch: OnMismatch | None = None,
) -> Summary | None:
    """Drive the full wizard. Returns the install summary, or None if the user declined.

    None (aborted) is distinct from an empty Summary (ran, but nothing to install).
    --yes implies unattended: the mismatch prompt is suppressed and a checksum
    mismatch hard-fails that tool.
    """
    selected = _choose_tools(tools, prompter, options, installed)
    statuses = audit(selected, installed)
    render_audit(statuses, console)
    if not options.yes and not prompter.confirm("Install the selected tools?"):
        return None
    ordered = order_for_install(selected)
    outcomes = run_installs(
        ordered,
        platform,
        runner,
        resolve_tag,
        install,
        on_mismatch=None if options.yes else on_mismatch,
    )
    summary = summarize(outcomes)
    render_summary(summary, console)
    render_verification(outcomes, console)
    return summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_app.py -v && make test`
Expected: PASS

- [ ] **Step 5: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add installer/app.py tests/test_app.py
git commit -m "feat: wizard threads the mismatch prompt and prints verification lines

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: `setup.py` wiring + registry structural test

**Files:**
- Modify: `setup.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Add the structural registry test**

Append to `tests/test_registry.py`:

```python
def test_checksum_param_only_on_github_release_methods() -> None:
    for tool in load_tools(REGISTRY):
        for method in tool.methods:
            if "checksum" in method.params:
                assert method.kind == "github_release", tool.id
```

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS (vacuously — no checksum params exist yet; it guards the sweep tasks)

- [ ] **Step 2: Wire setup.py**

In `setup.py`, add after `_ask_select`:

```python
def _ask_mismatch(tool_id: str) -> str:
    return _ask_select(
        f"Checksum mismatch for {tool_id} — the download may be corrupted or tampered with.",
        [
            ("Retry the download", "retry"),
            ("Skip this tool", "skip"),
            ("Fall back to another install method (brew/native)", "fallback"),
        ],
    )
```

In `main()`, pass it to the wizard (run_wizard suppresses it under `--yes`):

```python
    summary = run_wizard(tools, platform, prompter, console, options, on_mismatch=_ask_mismatch)
```

And make a mismatch surface in the exit code:

```python
    if summary.failed or summary.mismatched:
        render_troubleshooting(console)
        return 1
```

- [ ] **Step 3: Smoke-test the composition root**

Run: `uv run setup.py --help`
Expected: usage text, exit 0. NEVER run a real wizard/`--doctor` against this dev machine's home.

- [ ] **Step 4: Validate and commit**

Run: `make validate && make test`
Expected: green (setup.py is ruff-gated only; pyright/coverage exclude it by design)

```bash
git add setup.py tests/test_registry.py
git commit -m "feat: interactive checksum-mismatch prompt and mismatch exit code

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Survey — which registry tools ship checksums (no commit)

**Files:** none modified. Produces the verified-tool table consumed by Tasks 10–11.

- [ ] **Step 1: Enumerate checksum assets across every registry repo**

```bash
for r in $(grep 'repo = ' installer/registry.toml | sed 's/.*"\(.*\)"/\1/' | sort -u); do
  echo "== $r"
  gh api "repos/$r/releases/latest" --jq '.assets[].name' 2>/dev/null | grep -iE '\.sha|sums|checksum' | head -6
done
```

- [ ] **Step 2: Record the table**

For each repo note: (a) no checksum asset → tool stays unverified; (b) per-asset sidecar (suffix `.sha256` / `.sha256sum`) → `checksum = "{asset}.sha256"` form; (c) single multi-line file → `checksum = "<name>"` form (template `{ver}` if the name embeds the version). Already confirmed by sampling on 2026-06-10: ripgrep/starship/ruff → `{asset}.sha256`; deno → `{asset}.sha256sum`; fzf → `fzf_{ver}_checksums.txt`; gh → `gh_{ver}_checksums.txt`; lazygit/gum → `checksums.txt`; just → `SHA256SUMS`; gitleaks → `gitleaks_{ver}_checksums.txt`; fd/delta/xh → none. yq's `checksums` file is multi-algorithm — see step 3.

- [ ] **Step 3: Parse-verify each candidate's checksum file format**

For every tool that has a checksum asset, confirm our parser finds the entry (substitute the real tag/file/asset):

```bash
curl -fsSL "https://github.com/OWNER/REPO/releases/download/TAG/CHECKSUM_FILE" -o /tmp/sums
uv run python -c "
from pathlib import Path
from installer.checksums import expected_sha256
print(expected_sha256(Path('/tmp/sums').read_text(), 'ASSET_NAME'))
"
```

Expected: a 64-hex digest. `None` → that tool's format is incompatible (e.g. yq's multi-algorithm `checksums`) → it stays unverified, recorded in the Task 12 docs. Do NOT extend the parser for one oddball without prior agreement.

- [ ] **Step 4: One full end-to-end spot check per format family**

For one sidecar tool (ripgrep) and one multi-line tool (gitleaks), also download the actual asset and confirm the digest matches:

```bash
curl -fsSL -o /tmp/asset "https://github.com/OWNER/REPO/releases/download/TAG/ASSET_NAME"
uv run python -c "
from pathlib import Path
from installer.checksums import expected_sha256, sha256_file
text = Path('/tmp/sums').read_text()
assert expected_sha256(text, 'ASSET_NAME') == sha256_file(Path('/tmp/asset')), 'MISMATCH'
print('verified ok')
"
```

Expected: `verified ok` for both.

---

### Task 10: Registry sweep A — sidecar-style tools

**Files:**
- Modify: `installer/registry.toml`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing registry test**

Append to `tests/test_registry.py`. Seed `SIDECAR_VERIFIED` with the sampling-confirmed ids and **extend it with every sidecar-style tool the Task 9 survey confirmed**:

```python
SIDECAR_VERIFIED = {"ripgrep", "starship", "ruff", "deno"}  # extend per Task 9 survey


def test_sidecar_verified_tools_declare_checksums() -> None:
    for tool in load_tools(REGISTRY):
        if tool.id not in SIDECAR_VERIFIED:
            continue
        gh_methods = [m for m in tool.methods if m.kind == "github_release"]
        assert gh_methods, tool.id
        for method in gh_methods:
            assert "checksum" in method.params, f"{tool.id}: missing checksum param"
            assert "{asset}" in str(method.params["checksum"]), tool.id
```

Run: `uv run pytest tests/test_registry.py -v` — Expected: FAIL (no checksum params yet)

- [ ] **Step 2: Add `checksum` to every github_release method of each confirmed sidecar tool**

In `installer/registry.toml`, add one line per `[[tool.method]]` of kind `github_release` (every os-split method of the tool gets it). Confirmed forms:

```toml
# ripgrep, starship, ruff — every github_release method:
checksum = "{asset}.sha256"
# deno — every github_release method:
checksum = "{asset}.sha256sum"
```

Plus the same line for each additional sidecar tool the survey confirmed (using its exact suffix). Every added line must have passed the Task 9 step-3 parse check against the live release — never add one from memory.

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/test_registry.py -v && make test`
Expected: PASS (including `test_checksum_param_only_on_github_release_methods`)

- [ ] **Step 4: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: declare sidecar sha256 checksums for verified release tools

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Registry sweep B — multi-line checksum-file tools

**Files:**
- Modify: `installer/registry.toml`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing registry test**

Append to `tests/test_registry.py`. Seed with the sampling-confirmed ids and **extend with every multi-line-style tool the Task 9 survey confirmed**:

```python
CHECKSUM_FILE_VERIFIED = {"fzf", "gh", "lazygit", "just", "gum", "gitleaks"}  # extend per survey


def test_checksum_file_verified_tools_declare_checksums() -> None:
    for tool in load_tools(REGISTRY):
        if tool.id not in CHECKSUM_FILE_VERIFIED:
            continue
        gh_methods = [m for m in tool.methods if m.kind == "github_release"]
        assert gh_methods, tool.id
        for method in gh_methods:
            assert "checksum" in method.params, f"{tool.id}: missing checksum param"
```

Run: `uv run pytest tests/test_registry.py -v` — Expected: FAIL

- [ ] **Step 2: Add `checksum` lines**

Confirmed forms (one line per github_release method of the tool):

```toml
# fzf:
checksum = "fzf_{ver}_checksums.txt"
# gh:
checksum = "gh_{ver}_checksums.txt"
# lazygit, gum:
checksum = "checksums.txt"
# just:
checksum = "SHA256SUMS"
# gitleaks:
checksum = "gitleaks_{ver}_checksums.txt"
```

Plus each additional survey-confirmed tool with its exact file name. Every line must have passed the Task 9 step-3 parse check live. Tools whose format failed to parse (e.g. yq) get NO checksum line — they stay honestly unverified.

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/test_registry.py -v && make test`
Expected: PASS

- [ ] **Step 4: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: declare checksums-file sha256 sources for verified release tools

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 12: Docs + memory

**Files:**
- Modify: `README.md`
- Modify: `/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md` (not committed — outside the repo)

- [ ] **Step 1: Catalog verified column**

In `README.md` "Available tools", mark each tool whose downloads are now sha256-verified (the union of the two sweep sets) — follow the table/list format already there; a trailing `✓ sha256` marker or column. Add one sentence to "How installs are decided": downloads are sha256-verified against the release's published checksums when the upstream ships them; a mismatch stops that tool's install (interactively you may retry, skip, or fall back).

- [ ] **Step 2: Validate and commit**

Run: `make validate && make test`
Expected: green

```bash
git add README.md
git commit -m "docs: mark sha256-verified tools in the catalog

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: Update the roadmap memory**

In `roadmap-status.md`, mark the "Download checksum/sha256 verification" pending item DONE with: date, commit range, the verified-tool list, the unverified holdouts (and why — no upstream checksums vs unparseable format), and the policy summary (interactive ask / `--yes` hard-fail / opt-in + visible marker).

---

## Self-Review (completed)

- **Spec coverage:** checksums module (T1), `{asset}` token + tarball rejection (T2), verified flow + severity split + temp-dir hygiene (T3), engine policy + verified flag (T4), retry/skip/fallback + `--yes` suppression + mismatch bucket (T5, T7), UI markers + mismatch line (T6), questionary prompt + exit code (T8), structural test (T8), live-verified sweep with honest gaps (T9–T11), catalog column (T12). All spec sections mapped.
- **Type consistency:** `ChecksumPolicy` defined in `engine.py`, imported by `session.py`/tests; `MismatchChoice`/`OnMismatch` defined in `session.py`, imported by `app.py`/tests; `DownloadTarget.checksum: tuple[str, str] | None` narrows both URL and name in one check; `install_download -> bool` consumed by `_perform -> bool`.
- **Known adaptation points (not placeholders):** exact brew argv in T4's fallback test and the local helper names in T5/T7 must mirror what already exists in those test files; the sweep sets in T10/T11 are seeded with live-confirmed ids and extended only by the T9 survey's live checks.
