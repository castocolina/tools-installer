import shlex
from pathlib import Path

import pytest

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
        f"curl -fsSL -- {shlex.quote(url)}"
        f" | tar -xz -C {shlex.quote(str(opt))} --strip-components=1"
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
        f"curl -fsSL -- {shlex.quote('https://x/eza.tar.gz')}"
        f" | tar -xz -C {shlex.quote(str(opt))} --strip-components=0"
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
