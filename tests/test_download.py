import hashlib
import shlex
from pathlib import Path

import pytest

from installer import download
from installer.checksums import ChecksumMismatch
from installer.download import DOWNLOAD_KINDS, ExecContext, install_download
from installer.executors import ExecutorError
from installer.model import Method
from installer.platform import Platform
from installer.run import Runner


def _ctx(runner: Runner, tmp_version: str = "v14.1.0") -> ExecContext:
    def resolve_tag(repo: str) -> str:
        return tmp_version

    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    return ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)


def _record() -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    return calls, runner


def test_download_kinds_constant():
    assert set(DOWNLOAD_KINDS) == {"github_release", "tarball"}


def test_github_release_archive_extracts_to_opt_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
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
        "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
        f' && curl -fsSL -o "$tmp" -- {shlex.quote(url)}'
        f' && tar -xzf "$tmp" -C {shlex.quote(str(opt))} --strip-components=1'
    )
    assert calls == [
        ["sh", "-c", extract],
        ["chmod", "+x", str(binary)],
        ["ln", "-sf", str(binary), str(link)],
    ]
    assert opt.is_dir()


def test_archive_nested_member_uses_basename_for_link_and_opt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
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


def test_tarball_uses_url_verbatim_and_strip_defaults_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="tarball",
        params={"url": "https://x/eza.tar.gz", "member": "eza", "bin_dir": str(bin_dir)},
    )
    install_download(method, _ctx(runner))
    opt = tmp_path / ".local" / "opt" / "eza"
    binary = opt / "eza"
    link = bin_dir / "eza"
    # The tarball URL is used verbatim (no resolution), and strip defaults to 0.
    extract = (
        "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
        f' && curl -fsSL -o "$tmp" -- {shlex.quote("https://x/eza.tar.gz")}'
        f' && tar -xzf "$tmp" -C {shlex.quote(str(opt))} --strip-components=0'
    )
    assert calls == [
        ["sh", "-c", extract],
        ["chmod", "+x", str(binary)],
        ["ln", "-sf", str(binary), str(link)],
    ]


def test_github_release_bare_tag_no_v_in_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
    url = (
        "https://github.com/BurntSushi/ripgrep/releases/download/"
        "15.1.0/ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
    )
    # URL must use the bare tag (no leading v in path or asset)
    assert any(shlex.quote(url) in c[-1] for c in calls if c[0] == "sh")


def test_github_release_raw_downloads_binary_directly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
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
        ["sh", "-c", f"curl -fsSL -o {shlex.quote(str(target))} -- {shlex.quote(url)}"],
        ["chmod", "+x", str(target)],
    ]


def test_unsupported_kind_raises(tmp_path: Path):
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="brew"):
        install_download(Method(kind="brew", params={"formula": "x", "member": "x"}), _ctx(runner))
    assert calls == []


def test_missing_required_param_raises(tmp_path: Path):
    calls, runner = _record()
    method = Method(kind="tarball", params={"url": "https://x/y.tgz"})  # no member
    with pytest.raises(ExecutorError, match="member"):
        install_download(method, _ctx(runner))
    assert calls == []


def test_github_release_bad_asset_template_raises_executor_error(tmp_path: Path):
    calls, runner = _record()
    method = Method(
        kind="github_release",
        params={
            "repo": "a/b",
            "asset": "tool-{nope}.tar.gz",
            "member": "tool",
            "bin_dir": str(tmp_path / "bin"),
        },
    )
    with pytest.raises(ExecutorError, match="asset"):
        install_download(method, _ctx(runner))
    assert calls == []


def test_github_release_unsupported_arch_raises_executor_error(tmp_path: Path):
    calls, runner = _record()

    def resolve_tag(repo: str) -> str:
        return "1.0.0"

    ctx = ExecContext(
        runner=runner,
        platform=Platform(os="fedora", arch="riscv64", immutable=False, has_brew=False),
        resolve_tag=resolve_tag,
    )
    method = Method(
        kind="github_release",
        params={
            "repo": "a/b",
            "asset": "tool-{arch.machine}.tar.gz",
            "member": "tool",
            "bin_dir": str(tmp_path / "bin"),
        },
    )
    with pytest.raises(ExecutorError, match="asset"):
        install_download(method, ctx)
    assert calls == []


def test_bin_dir_creation_failure_raises_executor_error(tmp_path: Path):
    calls, runner = _record()
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    method = Method(
        kind="tarball",
        params={
            "url": "https://example.com/tool.tar.gz",
            "member": "tool",
            "bin_dir": str(blocker / "bin"),  # parent is a file -> mkdir fails
        },
    )
    with pytest.raises(ExecutorError, match="bin dir"):
        install_download(method, _ctx(runner))
    assert calls == []


def test_opt_dir_creation_failure_raises_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _, runner = _record()
    # Make ~/.local/opt/<bin> un-creatable: place a FILE where the opt dir must go.
    blocker = tmp_path / ".local" / "opt"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a directory")  # opt is a file -> mkdir of opt/<bin> fails
    method = Method(
        kind="tarball",
        params={"url": "https://x/y.tgz", "member": "tool", "bin_dir": str(tmp_path / "bin")},
    )
    with pytest.raises(ExecutorError, match="opt dir"):
        install_download(method, _ctx(runner))


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
        "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
        f' && curl -fsSL -o "$tmp" -- {shlex.quote(url)}'
        f' && unzip -q -o "$tmp" {shlex.quote("deno")} -d {shlex.quote(str(opt))}'
    )
    assert calls == [
        ["sh", "-c", extract],
        ["chmod", "+x", str(binary)],
        ["ln", "-sf", str(binary), str(link)],
    ]


def test_zip_extracts_only_the_nested_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "Canop/broot",
            "asset": "broot_{ver}.zip",
            "member": "{arch.machine}-unknown-linux-gnu/broot",
            "archive": "zip",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner, tmp_version="v1.57.0"))
    opt = tmp_path / ".local" / "opt" / "broot"
    member = "x86_64-unknown-linux-gnu/broot"  # {arch.machine} rendered for amd64
    binary = opt / member
    url = "https://github.com/Canop/broot/releases/download/v1.57.0/broot_1.57.0.zip"
    extract = (
        "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
        f' && curl -fsSL -o "$tmp" -- {shlex.quote(url)}'
        f' && unzip -q -o "$tmp" {shlex.quote(member)} -d {shlex.quote(str(opt))}'
    )
    assert calls[0] == ["sh", "-c", extract]
    assert ["chmod", "+x", str(binary)] in calls
    assert ["ln", "-sf", str(binary), str(bin_dir / "broot")] in calls


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


def test_tarball_with_checksum_param_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
    rg_url = shlex.quote(f"{RG_BASE}/{RG_ASSET}")
    rg_path = shlex.quote(str(workdir / RG_ASSET))
    rg_sum_path = shlex.quote(str(workdir / RG_ASSET) + ".sha256")
    rg_sum_url = shlex.quote(f"{RG_BASE}/{RG_ASSET}.sha256")
    fetch = f"curl -fsSL -o {rg_path} -- {rg_url} && curl -fsSL -o {rg_sum_path} -- {rg_sum_url}"
    assert calls == [
        ["sh", "-c", fetch],
        ["tar", "-xzf", str(workdir / RG_ASSET), "-C", str(opt), "--strip-components=1"],
        ["chmod", "+x", str(opt / "rg")],
        ["ln", "-sf", str(opt / "rg"), str(bindir / "rg")],
    ]
    assert not workdir.exists()  # temp dir removed after success


def test_verified_mismatch_raises_and_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    sums = f"{'0' * 64}  {RG_ASSET}\n".encode()  # wrong digest
    files = {RG_ASSET: b"archive-bytes", f"{RG_ASSET}.sha256": sums}
    calls, runner = _fixture_runner(workdir, files)
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


def test_verified_raw_copies_from_temp_into_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


def test_verified_zip_extracts_member_from_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


def test_verified_opt_dir_creation_failure_raises_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    # Place a FILE where ~/.local/opt must be, so mkdir of opt/<bin> fails.
    blocker = tmp_path / ".local" / "opt"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a directory")
    payload = b"archive-bytes"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {RG_ASSET}\n".encode()
    _, runner = _fixture_runner(workdir, {RG_ASSET: payload, f"{RG_ASSET}.sha256": sums})
    with pytest.raises(ExecutorError, match="opt dir"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
