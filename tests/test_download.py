import shlex
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
    cmd = (
        f"curl -fsSL -- {shlex.quote(url)}"
        f" | tar -xz -C {shlex.quote(str(bin_dir))}"
        f" -- {shlex.quote('rg')}"
    )
    assert calls == [
        ["sh", "-c", cmd],
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
        ["sh", "-c", f"curl -fsSL -o {shlex.quote(str(target))} -- {shlex.quote(url)}"],
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
    cmd = (
        f"curl -fsSL -- {shlex.quote('https://example.com/tool.tar.gz')}"
        f" | tar -xz -C {shlex.quote(str(bin_dir))}"
        f" -- {shlex.quote('tool')}"
    )
    assert calls == [
        ["sh", "-c", cmd],
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

    def resolve_version(repo: str) -> str:
        return "1.0.0"

    ctx = ExecContext(
        runner=runner,
        platform=Platform(os="fedora", arch="riscv64", immutable=False, has_brew=False),
        resolve_version=resolve_version,
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
