import dataclasses
import functools
import hashlib
import json
import os
from pathlib import Path

import pytest

from installer import atomic, download
from installer.atomic import NEW_SUFFIX, OLD_SUFFIX, staged_sibling
from installer.checksums import ChecksumMismatch
from installer.download import (
    DOWNLOAD_KINDS,
    ExecContext,
    install_download,
    is_still_proven,
    update_download,
)
from installer.executors import ExecutorError
from installer.model import Method
from installer.platform import Platform
from installer.run import CommandError, Runner
from installer.versions import Release, ReleaseResolver, resolve_github_release


def _ctx(
    runner: Runner,
    tmp_version: str = "v14.1.0",
    *,
    resolve_release: ReleaseResolver | None = None,
) -> ExecContext:
    def default_release(_repo: str) -> Release:
        return Release(tmp_version, {})

    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    return ExecContext(
        runner=runner,
        platform=platform,
        resolve_release=resolve_release if resolve_release is not None else default_release,
    )


def _record() -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    return calls, runner


def test_download_kinds_constant():
    assert set(DOWNLOAD_KINDS) == {"github_release", "tarball"}


def test_exec_context_requires_a_release_resolver():
    fields = dataclasses.fields(ExecContext)
    assert {f.name for f in fields} == {"runner", "platform", "resolve_release"}
    for field in fields:
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING


def test_github_release_archive_extracts_to_opt_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    asset = "ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
    calls, runner = fixture_runner(workdir, {asset: b"archive"}, member=member)
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
    staged = staged_sibling(opt, NEW_SUFFIX)
    link = bin_dir / "rg"
    url = (
        "https://github.com/BurntSushi/ripgrep/releases/download/"
        "15.1.0/ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
    )
    assert calls == [
        ["curl", "-fsSL", "-o", str(workdir / asset), "--", url],
        ["tar", "-xzf", str(workdir / asset), "-C", str(staged), "--strip-components=1"],
    ]
    assert not any(cmd and cmd[0] == "sh" for cmd in calls)
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert opt.is_dir()
    assert not workdir.exists()


def test_archive_nested_member_uses_basename_for_link_and_opt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "gh" / "bin" / "gh"
    calls, runner = fixture_runner(None, {}, member=member)
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
    link = bin_dir / "gh"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert not any(cmd and cmd[0] in {"ln", "chmod"} for cmd in calls)


def test_tarball_uses_url_verbatim_and_strip_defaults_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "eza" / "eza"
    url = "https://x/eza.tar.gz"
    asset = "eza.tar.gz"
    calls, runner = fixture_runner(workdir, {asset: b"archive"}, member=member)
    method = Method(
        kind="tarball",
        params={"url": url, "member": "eza", "bin_dir": str(bin_dir)},
    )
    install_download(method, _ctx(runner))
    opt = tmp_path / ".local" / "opt" / "eza"
    staged = staged_sibling(opt, NEW_SUFFIX)
    link = bin_dir / "eza"
    assert calls == [
        ["curl", "-fsSL", "-o", str(workdir / asset), "--", url],
        ["tar", "-xzf", str(workdir / asset), "-C", str(staged), "--strip-components=0"],
    ]
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert not workdir.exists()


def test_tar_flag_covers_gzip_default_and_xz_for_all_three_extract_sites() -> None:
    """_tar_flag() backs install staging, _extract_into (update path), and
    _extract_into alike -- one unit test at this level covers the archive-format
    decision for all three."""
    gzip_default = Method(kind="tarball", params={"url": "https://x/y.tar.gz", "member": "y"})
    xz = Method(
        kind="tarball", params={"url": "https://x/y.tar.xz", "member": "y", "archive": "xz"}
    )
    assert download._tar_flag(gzip_default) == "z"  # pyright: ignore[reportPrivateUsage]
    assert download._tar_flag(xz) == "J"  # pyright: ignore[reportPrivateUsage]


def test_tarball_archive_xz_uses_tar_capital_j_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression: some vendors (e.g. Sublime Text's official Linux build)
    only ship `.tar.xz`, not `.tar.gz` -- `archive = "xz"` must extract with
    `tar -xJf`, not the gzip-only `-xzf` every other tarball entry uses."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "sublime_text" / "sublime_text"
    url = "https://x/sublime_text.tar.xz"
    asset = "sublime_text.tar.xz"
    calls, runner = fixture_runner(workdir, {asset: b"archive"}, member=member)
    method = Method(
        kind="tarball",
        params={
            "url": url,
            "member": "sublime_text",
            "archive": "xz",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner))
    opt = tmp_path / ".local" / "opt" / "sublime_text"
    link = bin_dir / "sublime_text"
    staged = staged_sibling(opt, NEW_SUFFIX)
    assert calls == [
        ["curl", "-fsSL", "-o", str(workdir / asset), "--", url],
        ["tar", "-xJf", str(workdir / asset), "-C", str(staged), "--strip-components=0"],
    ]
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert not workdir.exists()


def test_unverified_archive_with_a_directory_member_links_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory extracted as the member is not a binary: link nothing."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = tmp_path / ".local" / "opt" / "tool" / "tool"
    calls, runner = fixture_runner(None, {}, member=member)
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="tarball",
        params={"url": "https://x/tool.tar.gz", "member": "tool", "bin_dir": str(bin_dir)},
    )

    def plant_directory(cmd: list[str]) -> None:
        runner(cmd)
        if _is_extraction(cmd):
            dest = _extract_dest(cmd)
            live_opt = _live_opt_from_extract_dest(dest)
            staged = dest / member.relative_to(live_opt)
            staged.unlink()
            staged.mkdir()

    with pytest.raises(ExecutorError, match="tool"):
        install_download(method, _ctx(plant_directory))
    assert not member.exists()
    assert not (bin_dir / "tool").exists()
    assert not (bin_dir / "tool").is_symlink()
    assert not any(cmd and cmd[0] in {"ln", "chmod"} for cmd in calls)


def test_unverified_archive_links_the_member_file_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A regular-file member becomes one symlink, chmod'd in process, never via ln."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = tmp_path / ".local" / "opt" / "eza" / "eza"
    calls, runner = fixture_runner(None, {}, member=member)
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="tarball",
        params={"url": "https://x/eza.tar.gz", "member": "eza", "bin_dir": str(bin_dir)},
    )
    install_download(method, _ctx(runner))
    link = bin_dir / "eza"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert member.stat().st_mode & 0o777 == 0o755
    assert not any(cmd and cmd[0] in {"ln", "chmod"} for cmd in calls)


def test_reinstall_never_writes_through_a_link_to_a_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staged swap replaces links without writing through a foreign directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    outside = tmp_path / "outside-dir"
    outside.mkdir()
    marker = outside / "marker"
    marker.write_bytes(b"keep-outside")
    os.symlink(str(outside), bin_dir / "subl")

    member = tmp_path / ".local" / "opt" / "subl" / "sublime_text" / "sublime_text"
    _, runner = fixture_runner(None, {}, member=member)
    method = Method(
        kind="tarball",
        params={
            "url": "https://x/sublime_text.tar.xz",
            "member": "sublime_text/sublime_text",
            "bin_name": "subl",
            "archive": "xz",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner))
    assert marker.read_bytes() == b"keep-outside"
    link = bin_dir / "subl"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)

    opt = tmp_path / ".local" / "opt" / "subl2"
    legacy = opt / "legacy"
    inner = legacy / "inner"
    inner.parent.mkdir(parents=True)
    inner.write_bytes(b"keep-me")
    os.symlink(str(legacy), bin_dir / "subl2")
    member2 = opt / "sublime_text" / "sublime_text"
    method2 = Method(
        kind="tarball",
        params={
            "url": "https://x/sublime_text.tar.xz",
            "member": "sublime_text/sublime_text",
            "bin_name": "subl2",
            "archive": "xz",
            "bin_dir": str(bin_dir),
        },
    )
    calls2, runner2 = fixture_runner(None, {}, member=member2)
    with pytest.raises(ExecutorError):
        install_download(method2, _ctx(runner2))
    assert inner.read_bytes() == b"keep-me"
    link2 = bin_dir / "subl2"
    assert os.readlink(link2) == str(legacy)
    assert calls2 == []


def test_install_refuses_an_unproven_opt_tree_and_leaves_it_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Portable VS Code data under ~/.local/opt/code is not replaced without proof."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt = tmp_path / ".local" / "opt" / "code"
    settings = opt / "data" / "user-data" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_bytes(b"user-settings-bytes")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    member = opt / "bin" / "code"
    calls, runner = fixture_runner(None, {}, member=member)
    method = Method(
        kind="tarball",
        params={
            "url": "https://x/code.tar.gz",
            "member": "bin/code",
            "strip": 1,
            "bin_dir": str(bin_dir),
        },
    )
    with pytest.raises(ExecutorError, match="not proven"):
        install_download(method, _ctx(runner))
    assert settings.read_bytes() == b"user-settings-bytes"
    assert not staged_sibling(opt, NEW_SUFFIX).exists()
    assert not staged_sibling(opt, OLD_SUFFIX).exists()
    assert calls == []


def test_install_replaces_a_proven_opt_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt = tmp_path / ".local" / "opt" / "rg"
    binary = opt / "rg"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"old-rg")
    binary.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    os.symlink(str(binary), bin_dir / "rg")
    member = opt / "rg"
    calls, runner = fixture_runner(None, {}, member=member)
    method = Method(
        kind="tarball",
        params={"url": "https://x/rg.tar.gz", "member": "rg", "bin_dir": str(bin_dir)},
    )
    install_download(method, _ctx(runner))
    link = bin_dir / "rg"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert member.read_bytes() == _MEMBER_SCRIPT
    assert not staged_sibling(opt, OLD_SUFFIX).exists()
    assert calls  # curl + tar ran


def test_is_still_proven_accepts_an_explicit_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / "bundle"
    inside = root / "cli"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"x")
    inside.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    link = bin_dir / "tool"
    os.symlink(str(inside), link)
    assert is_still_proven(link, root) is True
    outside = tmp_path / "other" / "cli"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"y")
    os.symlink(str(outside), bin_dir / "foreign")
    assert is_still_proven(bin_dir / "foreign", root) is False
    dangling = bin_dir / "dangling"
    os.symlink(str(root / "missing"), dangling)
    assert is_still_proven(dangling, root) is False
    regular = bin_dir / "regular"
    regular.write_bytes(b"z")
    assert is_still_proven(regular, root) is False


def test_failed_raw_copy_leaves_no_staged_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno

    import installer.download as download_mod

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _calls, runner = fixture_runner(None, {"a": b"payload"}, member=None)
    method = Method(
        kind="tarball",
        params={"url": "https://x/a", "member": "tool", "raw": True, "bin_dir": str(bin_dir)},
    )

    def partial_copy2(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
        *,
        follow_symlinks: bool = True,
    ) -> None:
        Path(dst).write_bytes(b"partial")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(download_mod.shutil, "copy2", partial_copy2)
    with pytest.raises(OSError):
        install_download(method, _ctx(runner))
    assert not staged_sibling(bin_dir / "tool", NEW_SUFFIX).exists()


def test_rollback_failure_names_both_errors_and_the_old_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import installer.download as download_mod

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt = tmp_path / ".local" / "opt" / "rg"
    binary = opt / "rg"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"old")
    binary.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    os.symlink(str(binary), bin_dir / "rg")
    member = opt / "rg"
    _, runner = fixture_runner(None, {}, member=member)
    method = Method(
        kind="tarball",
        params={"url": "https://x/rg.tar.gz", "member": "rg", "bin_dir": str(bin_dir)},
    )
    old_path = staged_sibling(opt, OLD_SUFFIX)
    real_replace = os.replace

    def fail_swap(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        src_p = Path(src)
        dst_p = Path(dst)
        if dst_p == opt and NEW_SUFFIX in src_p.name:
            raise OSError("swap failed")
        if dst_p == opt and src_p == old_path:
            raise OSError("rollback failed")
        real_replace(src, dst)

    monkeypatch.setattr(download_mod.os, "replace", fail_swap)
    with pytest.raises(ExecutorError) as excinfo:
        install_download(method, _ctx(runner))
    msg = str(excinfo.value)
    assert "swap failed" in msg
    assert "rollback failed" in msg
    assert str(old_path) in msg


def test_undecodable_checksum_file_is_an_ordinary_method_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    _, runner = fixture_runner(workdir, {RG_ASSET: b"x", f"{RG_ASSET}.sha256": b"\xff\xfe\x00bad"})
    with pytest.raises(ExecutorError, match="no sha256 entry"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))


def test_tarball_bin_name_overrides_the_symlink_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression: Sublime Text's Linux tarball ships the executable nested as
    `sublime_text/sublime_text`, with no `subl` alongside it -- `bin_name` must
    expose that file on PATH as `tool.cmd` ("subl")."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = tmp_path / ".local" / "opt" / "subl" / "sublime_text" / "sublime_text"
    calls, runner = fixture_runner(None, {}, member=member)
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="tarball",
        params={
            "url": "https://download.sublimetext.com/sublime_text_build_4200_x64.tar.xz",
            "member": "sublime_text/sublime_text",
            "bin_name": "subl",
            "archive": "xz",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner))
    link = bin_dir / "subl"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert not any(cmd and cmd[0] in {"ln", "chmod"} for cmd in calls)


def test_github_release_bare_tag_no_v_in_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    calls, runner = fixture_runner(None, {}, member=member)
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
    assert any(url in cmd for cmd in calls if cmd and cmd[0] == "curl")


def test_github_release_raw_downloads_binary_directly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "yq_linux_amd64"
    payload = _MEMBER_SCRIPT
    calls, runner = fixture_runner(workdir, {asset: payload})
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
    assert calls == [["curl", "-fsSL", "-o", str(workdir / asset), "--", url]]
    assert not any(cmd and cmd[0] == "sh" for cmd in calls)
    assert not target.is_symlink()
    assert target.read_bytes() == payload
    assert target.stat().st_mode & 0o777 == 0o755
    assert not workdir.exists()


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

    ctx = ExecContext(
        runner=runner,
        platform=Platform(os="fedora", arch="riscv64", immutable=False, has_brew=False),
        resolve_release=lambda _repo: Release("1.0.0", {}),
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
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "bun" / "bun-linux-amd64" / "bun"
    calls, runner = fixture_runner(None, {}, member=member)
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
    link = bin_dir / "bun"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)  # {arch.deb} rendered
    assert not any(cmd and cmd[0] in {"ln", "chmod"} for cmd in calls)


def test_github_release_zip_uses_unzip_and_ignores_strip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "deno" / "deno"
    asset = "deno-x86_64-unknown-linux-gnu.zip"
    calls, runner = fixture_runner(workdir, {asset: b"zip"}, member=member)
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
    staged = staged_sibling(opt, NEW_SUFFIX)
    link = bin_dir / "deno"
    url = (
        "https://github.com/denoland/deno/releases/download/"
        "v2.1.4/deno-x86_64-unknown-linux-gnu.zip"
    )
    assert calls == [
        ["curl", "-fsSL", "-o", str(workdir / asset), "--", url],
        ["unzip", "-q", "-o", str(workdir / asset), "deno", "-d", str(staged)],
    ]
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert not workdir.exists()


def test_zip_extracts_only_the_nested_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    bin_dir = tmp_path / "bin"
    member_rel = "x86_64-unknown-linux-gnu/broot"  # {arch.machine} rendered for amd64
    binary = tmp_path / ".local" / "opt" / "broot" / member_rel
    asset = "broot_1.57.0.zip"
    calls, runner = fixture_runner(workdir, {asset: b"zip"}, member=binary)
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
    staged = staged_sibling(opt, NEW_SUFFIX)
    url = "https://github.com/Canop/broot/releases/download/v1.57.0/broot_1.57.0.zip"
    assert calls == [
        ["curl", "-fsSL", "-o", str(workdir / asset), "--", url],
        ["unzip", "-q", "-o", str(workdir / asset), member_rel, "-d", str(staged)],
    ]
    link = bin_dir / "broot"
    assert link.is_symlink()
    assert os.readlink(link) == str(binary)
    assert not workdir.exists()


def test_unhashed_tarball_install_is_unverified_with_a_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = tmp_path / ".local" / "opt" / "eza" / "eza"
    _, runner = fixture_runner(None, {}, member=member)
    method = Method(
        kind="tarball",
        params={"url": "https://x/eza.tar.gz", "member": "eza", "bin_dir": str(tmp_path / "bin")},
    )
    reason = install_download(method, _ctx(runner))
    assert reason == "unpinned url; no sha256 to verify against"
    assert (tmp_path / "bin" / "eza").is_symlink()


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


def _is_extraction(cmd: list[str]) -> bool:
    """True when this recorded call is the archive extraction step."""
    if not cmd:
        return False
    if cmd[0] in {"tar", "unzip", "ditto"}:
        return True
    if cmd[0] != "sh" or len(cmd) < 3:
        return False
    script = cmd[2]
    return " tar " in script or "unzip " in script or "ditto " in script


_MEMBER_SCRIPT = b"#!/bin/sh\nexit 0\n"


def _extract_dest(cmd: list[str]) -> Path:
    if cmd[0] == "tar":
        return Path(cmd[cmd.index("-C") + 1])
    if cmd[0] == "unzip":
        return Path(cmd[cmd.index("-d") + 1])
    if cmd[0] == "ditto":
        return Path(cmd[-1])
    raise AssertionError(f"not an extraction argv: {cmd}")


def _live_opt_from_extract_dest(dest: Path) -> Path:
    if dest.name.endswith(NEW_SUFFIX):
        return dest.parent / dest.name[: -len(NEW_SUFFIX)]
    return dest


def fixture_runner(
    workdir: Path | None, files: dict[str, bytes], *, member: Path | None = None
) -> tuple[list[list[str]], Runner]:
    """Record argv. A curl fetch drops `files` into `workdir`; an extraction
    materializes `member` as an executable script at the extraction dest."""
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            dest = Path(cmd[cmd.index("-o") + 1])
            if dest.name not in files:
                if files:
                    return
                payload = _MEMBER_SCRIPT
            else:
                payload = files[dest.name]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
        if workdir is not None and cmd[0] == "sh" and len(cmd) >= 3 and "curl" in cmd[2]:
            for name, content in files.items():
                (workdir / name).write_bytes(content)
        if member is not None and _is_extraction(cmd):
            if cmd[0] in {"tar", "unzip", "ditto"}:
                dest = _extract_dest(cmd)
                if cmd[0] == "ditto":
                    target = dest / member if not member.is_absolute() else member
                else:
                    live_opt = _live_opt_from_extract_dest(dest)
                    target = dest / member.relative_to(live_opt)
            else:
                target = member
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                return
            target.write_bytes(_MEMBER_SCRIPT)
            target.chmod(0o755)

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


def _rg_update_method(bin_dir_path: Path) -> Method:
    return Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz",
            "member": "rg",
            "strip": 1,
            "bin_dir": str(bin_dir_path),
        },
    )


RG_ASSET = "ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
RG_BASE = "https://github.com/BurntSushi/ripgrep/releases/download/15.1.0"


def test_release_digest_verifies_an_unchecksummed_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    payload = b"archive-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    asset = "tool-1.0.0-x86_64.tar.gz"

    def fetch(url: str) -> bytes:
        return json.dumps(
            {
                "tag_name": "v1.0.0",
                "assets": [{"name": asset, "digest": f"sha256:{digest}"}],
            }
        ).encode()

    member = tmp_path / ".local" / "opt" / "tool" / "tool"
    calls, runner = fixture_runner(workdir, {asset: payload}, member=member)
    bindir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "org/tool",
            "asset": "tool-{ver}-{arch.machine}.tar.gz",
            "member": "tool",
            "strip": 0,
            "bin_dir": str(bindir),
        },
    )
    ctx = _ctx(
        runner,
        tmp_version="unused",
        resolve_release=functools.partial(resolve_github_release, fetch=fetch),
    )
    assert install_download(method, ctx) is None
    url = f"https://github.com/org/tool/releases/download/v1.0.0/{asset}"
    assert calls[0] == ["curl", "-fsSL", "-o", str(workdir / asset), "--", url]
    assert (bindir / "tool").is_symlink()
    assert not workdir.exists()


def test_install_without_checksum_or_digest_is_unverified_with_a_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    asset = "tool-1.0.0-x86_64.tar.gz"
    member = tmp_path / ".local" / "opt" / "tool" / "tool"
    _, runner = fixture_runner(None, {}, member=member)
    bindir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "org/tool",
            "asset": "tool-{ver}-{arch.machine}.tar.gz",
            "member": "tool",
            "bin_dir": str(bindir),
        },
    )

    def empty_release(_repo: str) -> Release:
        return Release("v1.0.0", {})

    reason = install_download(method, _ctx(runner, resolve_release=empty_release))
    assert reason is not None
    assert asset in reason
    assert (bindir / "tool").is_symlink()


def test_unverified_install_fetches_into_staging_with_a_plain_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "tool-1.0.0-x86_64.tar.gz"
    payload = b"archive-bytes"
    member = tmp_path / ".local" / "opt" / "tool" / "tool"
    calls, runner = fixture_runner(workdir, {asset: payload}, member=member)
    bindir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "org/tool",
            "asset": "tool-{ver}-{arch.machine}.tar.gz",
            "member": "tool",
            "strip": 0,
            "bin_dir": str(bindir),
        },
    )

    def empty_release(_repo: str) -> Release:
        return Release("v1.0.0", {})

    reason = install_download(method, _ctx(runner, resolve_release=empty_release))
    url = f"https://github.com/org/tool/releases/download/v1.0.0/{asset}"
    assert reason is not None
    assert calls[0] == ["curl", "-fsSL", "-o", str(workdir / asset), "--", url]
    assert calls[1][0] == "tar"
    assert not any(cmd and cmd[0] == "sh" for cmd in calls)
    assert (bindir / "tool").is_symlink()
    assert not workdir.exists()


def test_update_verifies_the_release_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = tmp_path / "update-staging"
    workdir.mkdir()

    def fake_mkdtemp(prefix: str) -> str:
        return str(workdir)

    monkeypatch.setattr(download.tempfile, "mkdtemp", fake_mkdtemp)
    asset = "tool-1.0.0-x86_64.tar.gz"
    payload = b"new-archive"
    digest = hashlib.sha256(payload).hexdigest()
    wrong_digest = "0" * 64
    member = "tool"
    opt, _binary, link = _plant_archive_install(tmp_path, name="tool", member=member)

    def release_for(_repo: str) -> Release:
        return Release("v1.0.0", {asset: digest})

    def wrong_release(_repo: str) -> Release:
        return Release("v1.0.0", {asset: wrong_digest})

    method = Method(
        kind="github_release",
        params={
            "repo": "org/tool",
            "asset": "tool-{ver}-{arch.machine}.tar.gz",
            "member": member,
            "strip": 0,
            "bin_dir": str(tmp_path / "bin"),
        },
    )
    _, runner_mismatch = _curl_and_extract_runner(
        {asset: payload}, member=member, extracted=payload
    )
    with pytest.raises(ChecksumMismatch):
        update_download(method, _ctx(runner_mismatch, resolve_release=wrong_release))
    assert (opt / "marker").read_text() == "original"
    assert (opt / member).read_bytes() == b"old-binary"
    assert os.readlink(link) == str(opt / member)

    calls, runner = _curl_and_extract_runner({asset: payload}, member=member, extracted=payload)
    result = update_download(method, _ctx(runner, resolve_release=release_for))
    assert result.verified is True
    assert (opt / member).read_bytes() == payload
    assert calls[0][0] == "curl"


def test_verified_archive_fetches_verifies_and_extracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    payload = b"archive-bytes"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {RG_ASSET}\n".encode()
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    calls, runner = fixture_runner(
        workdir, {RG_ASSET: payload, f"{RG_ASSET}.sha256": sums}, member=member
    )
    bindir = tmp_path / "bin"
    assert install_download(_rg_method(bindir), _ctx(runner, tmp_version="15.1.0")) is None
    opt = tmp_path / ".local" / "opt" / "rg"
    assert calls == [
        ["curl", "-fsSL", "-o", str(workdir / RG_ASSET), "--", f"{RG_BASE}/{RG_ASSET}"],
        [
            "curl",
            "-fsSL",
            "-o",
            str(workdir / f"{RG_ASSET}.sha256"),
            "--",
            f"{RG_BASE}/{RG_ASSET}.sha256",
        ],
        [
            "tar",
            "-xzf",
            str(workdir / RG_ASSET),
            "-C",
            str(staged_sibling(opt, NEW_SUFFIX)),
            "--strip-components=1",
        ],
    ]
    assert (bindir / "rg").is_symlink()
    assert os.readlink(bindir / "rg") == str(member)
    assert not workdir.exists()  # temp dir removed after success


def test_verified_archive_with_a_directory_member_links_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A verified archive whose member extracts as a directory links nothing."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    payload = b"archive-bytes"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {RG_ASSET}\n".encode()
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    _, runner = fixture_runner(
        workdir, {RG_ASSET: payload, f"{RG_ASSET}.sha256": sums}, member=member
    )
    bindir = tmp_path / "bin"

    def plant_directory(cmd: list[str]) -> None:
        runner(cmd)
        if _is_extraction(cmd):
            dest = _extract_dest(cmd)
            live_opt = _live_opt_from_extract_dest(dest)
            staged = dest / member.relative_to(live_opt)
            staged.unlink()
            staged.mkdir()

    with pytest.raises(ExecutorError, match="rg"):
        install_download(_rg_method(bindir), _ctx(plant_directory, tmp_version="15.1.0"))
    assert not member.exists()
    assert not (bindir / "rg").exists()
    assert not (bindir / "rg").is_symlink()


def test_verified_archive_links_the_member_file_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The verified path links the member file without shelling chmod or ln."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    payload = b"archive-bytes"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {RG_ASSET}\n".encode()
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    calls, runner = fixture_runner(
        workdir, {RG_ASSET: payload, f"{RG_ASSET}.sha256": sums}, member=member
    )
    bindir = tmp_path / "bin"
    install_download(_rg_method(bindir), _ctx(runner, tmp_version="15.1.0"))
    link = bindir / "rg"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert member.stat().st_mode & 0o777 == 0o755
    assert not any(cmd and cmd[0] in {"ln", "chmod"} for cmd in calls)


def test_verified_mismatch_raises_and_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    sums = f"{'0' * 64}  {RG_ASSET}\n".encode()  # wrong digest
    files = {RG_ASSET: b"archive-bytes", f"{RG_ASSET}.sha256": sums}
    calls, runner = fixture_runner(workdir, files)
    with pytest.raises(ChecksumMismatch) as excinfo:
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert excinfo.value.asset == RG_ASSET
    assert excinfo.value.expected == "0" * 64
    assert len(calls) == 2  # asset + checksum fetch; no extraction after the mismatch
    assert not workdir.exists()  # temp dir removed on the failure path too


def test_verified_missing_entry_is_ordinary_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    sums = f"{'0' * 64}  some-other-asset.tar.gz\n".encode()
    _, runner = fixture_runner(workdir, {RG_ASSET: b"x", f"{RG_ASSET}.sha256": sums})
    with pytest.raises(ExecutorError, match="no sha256 entry"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert not workdir.exists()


def test_verified_unreadable_checksum_file_is_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    _, runner = fixture_runner(workdir, {RG_ASSET: b"x"})  # checksum file never written
    with pytest.raises(ExecutorError, match="cannot read checksum file"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))


def test_verified_missing_asset_file_is_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    sums = f"{'0' * 64}  {RG_ASSET}\n".encode()
    _, runner = fixture_runner(workdir, {f"{RG_ASSET}.sha256": sums})  # asset never written
    with pytest.raises(ExecutorError, match="cannot hash downloaded asset"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))


def test_verified_raw_copies_from_temp_into_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "yq_linux_amd64"
    payload = _MEMBER_SCRIPT
    sums = f"{hashlib.sha256(payload).hexdigest()}  {asset}\n".encode()
    calls, runner = fixture_runner(workdir, {asset: payload, "checksums.txt": sums})
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
    assert install_download(method, _ctx(runner, tmp_version="v4.44.0")) is None
    # WR-04: placed via _replace_raw (sibling temp + os.replace), never a
    # shelled cp/chmod through the live path.
    assert not any(cmd and cmd[0] in {"cp", "chmod"} for cmd in calls)
    placed = bindir / "yq"
    assert not placed.is_symlink()
    assert placed.read_bytes() == payload
    assert placed.stat().st_mode & 0o777 == 0o755
    assert not Path(str(placed) + ".tools-installer.new").exists()


def test_verified_zip_extracts_member_from_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "deno-x86_64-unknown-linux-gnu.zip"
    payload = b"zip-bytes"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {asset}\n".encode()
    member = tmp_path / ".local" / "opt" / "deno" / "deno"
    calls, runner = fixture_runner(
        workdir, {asset: payload, f"{asset}.sha256sum": sums}, member=member
    )
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
    assert install_download(method, _ctx(runner, tmp_version="v2.0.0")) is None
    opt = tmp_path / ".local" / "opt" / "deno"
    staged = staged_sibling(opt, NEW_SUFFIX)
    assert calls[2:] == [
        ["unzip", "-q", "-o", str(workdir / asset), "deno", "-d", str(staged)],
    ]
    assert (bindir / "deno").is_symlink()
    assert os.readlink(bindir / "deno") == str(member)


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
    _, runner = fixture_runner(workdir, {RG_ASSET: payload, f"{RG_ASSET}.sha256": sums})
    with pytest.raises(ExecutorError, match="opt dir"):
        install_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))


def _raw_method(bin_dir_path: Path) -> Method:
    return Method(
        kind="github_release",
        params={
            "repo": "mikefarah/yq",
            "asset": "yq_linux_{arch.deb}",
            "member": "yq",
            "raw": True,
            "bin_dir": str(bin_dir_path),
        },
    )


def _plant_executable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(0o755)


def _plant_archive_install(
    tmp_path: Path, *, name: str = "rg", member: str = "rg"
) -> tuple[Path, Path, Path]:
    opt = tmp_path / ".local" / "opt" / name
    opt.mkdir(parents=True)
    binary = opt / member
    _plant_executable(binary, b"old-binary")
    (opt / "marker").write_text("original")
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    link = bindir / name
    os.symlink(str(binary), link)
    return opt, binary, link


def _curl_and_extract_runner(
    files: dict[str, bytes],
    *,
    member: str = "rg",
    extracted: bytes = b"new-binary",
    fail_fetch: bool = False,
) -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd[0] == "curl":
            if fail_fetch:
                raise CommandError(cmd, 1, detail="fetch failed")
            dest = Path(cmd[cmd.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            name = dest.name
            dest.write_bytes(files.get(name, b"payload"))
            return
        if cmd[0] == "tar":
            dest = Path(cmd[cmd.index("-C") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            binary = dest / member
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(extracted)
            binary.chmod(0o755)
            return
        if cmd[0] == "unzip":
            dest = Path(cmd[cmd.index("-d") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            listed = cmd[-3]
            binary = dest / listed
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(extracted)
            binary.chmod(0o755)

    return calls, runner


def _fetch_output_path(calls: list[list[str]]) -> Path:
    for cmd in calls:
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            return Path(cmd[cmd.index("-o") + 1])
    raise AssertionError(f"no curl -o in {calls}")


def test_raw_update_replaces_via_staging_not_live_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bindir = tmp_path / "bin"
    link = bindir / "yq"
    _plant_executable(link, b"old-yq")
    calls, runner = _curl_and_extract_runner({"yq_linux_amd64": _MEMBER_SCRIPT})
    result = update_download(_raw_method(bindir), _ctx(runner))
    assert result.verified is False
    assert link.read_bytes() == _MEMBER_SCRIPT
    fetch_to = _fetch_output_path(calls)
    assert fetch_to != link
    assert str(link) not in str(fetch_to)
    assert "tools-installer-update-" in str(fetch_to) or fetch_to.parent != bindir


def test_raw_update_fetch_failure_leaves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bindir = tmp_path / "bin"
    link = bindir / "yq"
    _plant_executable(link, b"old-yq")
    _, runner = _curl_and_extract_runner({}, fail_fetch=True)
    with pytest.raises(CommandError):
        update_download(_raw_method(bindir), _ctx(runner))
    assert link.read_bytes() == b"old-yq"


def test_archive_update_replaces_tree_and_cleans_remnants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _binary, link = _plant_archive_install(tmp_path)
    calls, runner = _curl_and_extract_runner({}, extracted=b"new-rg")
    result = update_download(
        _rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0")
    )
    assert result.verified is False
    assert (opt / "rg").read_bytes() == b"new-rg"
    assert not (opt / "marker").exists()
    assert link.exists()
    assert Path(os.readlink(link)).exists()
    assert not Path(str(opt) + ".tools-installer.old").exists()
    assert not Path(str(opt) + ".tools-installer.new").exists()
    assert not any(cmd and cmd[0] == "ln" for cmd in calls)


def test_archive_update_swap_failure_restores_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _binary, link = _plant_archive_install(tmp_path)
    _, runner = _curl_and_extract_runner({}, extracted=b"new-rg")
    real_replace = os.replace

    def fail_swap(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if Path(dst) == opt and str(src).endswith(".tools-installer.new"):
            raise OSError("swap failed")
        real_replace(src, dst)

    monkeypatch.setattr(download.os, "replace", fail_swap)
    with pytest.raises(ExecutorError, match="restored"):
        update_download(_rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert (opt / "marker").read_text() == "original"
    assert (opt / "rg").read_bytes() == b"old-binary"
    assert Path(os.readlink(link)).exists()


def test_archive_update_symlink_failure_restores_tree_and_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, binary, link = _plant_archive_install(tmp_path)
    original_target = os.readlink(link)
    _, runner = _curl_and_extract_runner({}, extracted=b"new-rg")
    real_symlink = os.symlink
    seen: list[str] = []

    def fail_first(target: str, path: str) -> None:
        seen.append(target)
        if len(seen) == 1:
            raise OSError("symlink failed")
        real_symlink(target, path)

    monkeypatch.setattr(atomic.os, "symlink", fail_first)
    with pytest.raises(ExecutorError, match="restored"):
        update_download(_rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert (opt / "marker").read_text() == "original"
    assert os.readlink(link) == original_target
    assert Path(os.readlink(link)).resolve() == binary.resolve()
    assert not Path(str(opt) + ".tools-installer.old").exists()
    assert not Path(str(opt) + ".tools-installer.new").exists()
    # The live symlink path is stable across an update (it always points at
    # opt/<member>), so seen[0] is textually equal to original_target too —
    # that equality proves nothing about restore behavior. What matters is
    # that exactly two symlink attempts happened (the failing one, then the
    # restore) and the second one is the captured pre-update target.
    assert len(seen) == 2
    assert seen[1] == original_target


def test_archive_update_symlink_restore_uses_captured_step_minus_one_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _opt, _binary, link = _plant_archive_install(tmp_path)
    captured = os.readlink(link)
    _, runner = _curl_and_extract_runner({}, extracted=b"new-rg")
    real_symlink = os.symlink
    seen: list[str] = []

    def fail_first(target: str, path: str) -> None:
        seen.append(target)
        if len(seen) == 1:
            raise OSError("symlink failed")
        real_symlink(target, path)

    monkeypatch.setattr(atomic.os, "symlink", fail_first)
    with pytest.raises(ExecutorError):
        update_download(_rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert seen[1] == captured


def test_archive_update_no_shelled_ln(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _plant_archive_install(tmp_path)
    calls, runner = _curl_and_extract_runner({}, extracted=b"new-rg")
    update_download(_rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert not any(cmd and cmd[0] == "ln" for cmd in calls)


def test_interrupted_run_restores_old_then_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _binary, link = _plant_archive_install(tmp_path)
    old = Path(str(opt) + ".tools-installer.old")
    os.replace(opt, old)
    assert not opt.exists()
    _, runner = _curl_and_extract_runner({}, extracted=b"new-rg")
    result = update_download(
        _rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0")
    )
    assert result.verified is False
    assert (opt / "rg").read_bytes() == b"new-rg"
    assert link.exists()
    assert not old.exists()


def test_interrupted_run_discards_stale_new(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _binary, _link = _plant_archive_install(tmp_path)
    stale = Path(str(opt) + ".tools-installer.new")
    stale.mkdir()
    (stale / "stale-marker").write_text("stale")
    _, runner = _curl_and_extract_runner({}, extracted=b"new-rg")
    update_download(_rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert (opt / "rg").read_bytes() == b"new-rg"
    assert not stale.exists()
    assert not (opt / "stale-marker").exists()


def test_cleanup_failure_is_warning_not_update_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _binary, link = _plant_archive_install(tmp_path)
    _, runner = _curl_and_extract_runner({}, extracted=b"new-rg")
    real_rmtree = download.shutil.rmtree

    def fail_old(path: str | os.PathLike[str], ignore_errors: bool = False) -> None:
        if str(path).endswith(".tools-installer.old"):
            raise OSError("cleanup failed")
        real_rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(download.shutil, "rmtree", fail_old)
    result = update_download(
        _rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0")
    )
    assert result.verified is False
    assert any("cleanup failed" in warning for warning in result.warnings)
    assert (opt / "rg").read_bytes() == b"new-rg"
    assert Path(os.readlink(link)).exists()


def test_checksum_mismatch_during_update_leaves_live_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _binary, _link = _plant_archive_install(tmp_path)
    sums = f"{'0' * 64}  {RG_ASSET}\n".encode()
    files = {RG_ASSET: b"archive-bytes", f"{RG_ASSET}.sha256": sums}
    _, runner = _curl_and_extract_runner(files)
    with pytest.raises(ChecksumMismatch):
        update_download(_rg_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0"))
    assert (opt / "marker").read_text() == "original"
    assert (opt / "rg").read_bytes() == b"old-binary"


def test_update_download_directory_member_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-03: the live-binary check on update is the same predicate install
    uses -- a directory member is a failure, and the swap rolls back."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _binary, link = _plant_archive_install(tmp_path)
    original = os.readlink(link)
    _, plain_runner = _curl_and_extract_runner({}, extracted=b"new-rg")

    def dir_member_runner(cmd: list[str]) -> None:
        if cmd[0] == "tar":
            dest = Path(cmd[cmd.index("-C") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "rg").mkdir()  # the archive member is a directory
        else:
            plain_runner(cmd)

    with pytest.raises(ExecutorError, match="regular file"):
        update_download(_rg_update_method(tmp_path / "bin"), _ctx(dir_member_runner))
    assert (opt / "marker").read_text() == "original"
    assert (opt / "rg").read_bytes() == b"old-binary"
    assert os.readlink(link) == original
    assert not Path(str(opt) + ".tools-installer.old").exists()


def test_raw_install_replaces_a_link_instead_of_writing_through_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-04: a raw install with ~/.local/bin/<name> a symlink to a foreign
    directory replaces the link itself; the target is untouched and no
    shelled chmod/cp targets the link."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep").write_text("important")
    link = bindir / "yq"
    os.symlink(str(foreign), link)
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "yq_linux_amd64"
    calls, runner = fixture_runner(workdir, {asset: _MEMBER_SCRIPT})
    install_download(_raw_method(bindir), _ctx(runner, tmp_version="v14.1.0"))
    assert not link.is_symlink()
    assert link.read_bytes() == _MEMBER_SCRIPT
    assert (foreign / "keep").read_text() == "important"
    assert not any(cmd and cmd[0] in {"chmod", "cp"} for cmd in calls)
    fetch_to = Path(calls[0][calls[0].index("-o") + 1])
    assert fetch_to != link  # curl never targets the live link
    assert not workdir.exists()


def test_verified_raw_install_replaces_a_link_instead_of_writing_through_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-04, verified raw branch: the asset lands via sibling temp +
    os.replace, so a link to a foreign directory is replaced, never written
    through."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "yq_linux_amd64"
    payload = _MEMBER_SCRIPT
    sums = f"{hashlib.sha256(payload).hexdigest()}  {asset}\n".encode()
    calls, runner = fixture_runner(workdir, {asset: payload, "checksums.txt": sums})
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep").write_text("important")
    link = bindir / "yq"
    os.symlink(str(foreign), link)
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
    assert install_download(method, _ctx(runner, tmp_version="v4.44.0")) is None
    assert not link.is_symlink()
    assert link.read_bytes() == payload
    assert (foreign / "keep").read_text() == "important"
    assert not any(cmd and cmd[0] in {"chmod", "cp"} for cmd in calls)


def test_pinned_url_renders_the_version() -> None:
    digest = "a" * 64
    method = Method(
        kind="tarball",
        params={
            "url": "https://x/build_{ver}_x64.tar.xz",
            "version": "4215",
            "sha256": digest,
            "member": "x",
        },
    )
    assert download.pinned_url(method) == "https://x/build_4215_x64.tar.xz"
    verbatim = Method(
        kind="tarball",
        params={"url": "https://x/latest.tar.xz", "member": "x"},
    )
    assert download.pinned_url(verbatim) == "https://x/latest.tar.xz"
    missing = Method(
        kind="tarball",
        params={"url": "https://x/build_{ver}_x64.tar.xz", "member": "x"},
    )
    with pytest.raises(ExecutorError):
        download.pinned_url(missing)


def test_pinned_tarball_is_verified_against_its_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    payload = b"pinned-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    url = "https://x/build_4215_x64.tar.xz"
    asset = "build_4215_x64.tar.xz"
    member = tmp_path / ".local" / "opt" / "x" / "x"
    calls, runner = fixture_runner(workdir, {asset: payload}, member=member)
    bindir = tmp_path / "bin"
    method = Method(
        kind="tarball",
        params={
            "url": "https://x/build_{ver}_x64.tar.xz",
            "version": "4215",
            "sha256": digest,
            "member": "x",
            "bin_dir": str(bindir),
        },
    )
    assert install_download(method, _ctx(runner)) is None
    assert calls[0] == ["curl", "-fsSL", "-o", str(workdir / asset), "--", url]
    assert (bindir / "x").is_symlink()
    assert not workdir.exists()

    bindir2 = tmp_path / "bin2"
    bindir2.mkdir()
    os.symlink(str(member), bindir2 / "x")
    bad = Method(
        kind="tarball",
        params={
            "url": "https://x/build_{ver}_x64.tar.xz",
            "version": "4215",
            "sha256": "b" * 64,
            "member": "x",
            "bin_dir": str(bindir2),
        },
    )
    _, runner2 = fixture_runner(workdir, {asset: payload}, member=member)
    with pytest.raises(ChecksumMismatch):
        install_download(bad, _ctx(runner2))
    assert os.readlink(bindir2 / "x") == str(member)


def test_supplied_sha256_is_never_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    payload = b" tarball-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    asset = "latest.tar.xz"
    url = "https://x/latest.tar.xz"
    member = tmp_path / ".local" / "opt" / "x" / "x"
    bindir = tmp_path / "bin"
    bad = Method(
        kind="tarball",
        params={
            "url": url,
            "member": "x",
            "sha256": "c" * 64,
            "bin_dir": str(bindir),
        },
    )
    _, runner = fixture_runner(workdir, {asset: payload}, member=member)
    with pytest.raises(ChecksumMismatch):
        install_download(bad, _ctx(runner))
    assert not (bindir / "x").exists()

    good = Method(
        kind="tarball",
        params={"url": url, "member": "x", "sha256": digest, "bin_dir": str(bindir)},
    )
    _, runner2 = fixture_runner(workdir, {asset: payload}, member=member)
    assert install_download(good, _ctx(runner2)) is None
    assert (bindir / "x").is_symlink()


def _member_script(exit_code: int = 0, *, extra: str = "") -> bytes:
    return f"#!/bin/sh\n{extra}exit {exit_code}\n".encode()


def _script_member_runner(
    member: Path, body: bytes, *, workdir: Path | None = None, files: dict[str, bytes] | None = None
) -> tuple[list[list[str]], Runner]:
    file_map = dict(files or {})
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            dest = Path(cmd[cmd.index("-o") + 1])
            if dest.name not in file_map:
                return
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(file_map[dest.name])
        if workdir is not None and cmd[0] == "sh" and len(cmd) >= 3 and "curl" in cmd[2]:
            for name, content in file_map.items():
                (workdir / name).write_bytes(content)
        if _is_extraction(cmd):
            if cmd[0] in {"tar", "unzip"}:
                dest = _extract_dest(cmd)
                live_opt = _live_opt_from_extract_dest(dest)
                target = dest / member.relative_to(live_opt)
            else:
                target = member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            target.chmod(0o755)

    return calls, runner


def test_smoke_failure_keeps_an_existing_good_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt = tmp_path / ".local" / "opt" / "rg"
    binary = opt / "rg"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"good-binary")
    planted = opt / "planted"
    planted.write_bytes(b"planted-bytes")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    os.symlink(str(binary), bin_dir / "rg")
    member = binary
    asset = "rg-1.0.0.tar.gz"
    calls, runner = _script_member_runner(member, _member_script(127), files={asset: b"archive"})
    method = Method(
        kind="github_release",
        params={
            "repo": "x/y",
            "asset": "rg-{ver}.tar.gz",
            "member": "rg",
            "bin_dir": str(bin_dir),
        },
    )
    with pytest.raises(ExecutorError):
        install_download(method, _ctx(runner, tmp_version="1.0.0"))
    assert binary.read_bytes() == b"good-binary"
    assert planted.read_bytes() == b"planted-bytes"
    assert os.readlink(bin_dir / "rg") == str(binary)
    assert not any(cmd and cmd[0] in {"ln", "chmod"} for cmd in calls)


def test_mismatch_never_runs_the_staged_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _workdir(tmp_path, monkeypatch)
    marker = tmp_path / "smoke-ran"
    body = _member_script(0, extra=f"touch {marker}\n")
    member = tmp_path / ".local" / "opt" / "tool" / "tool"
    asset = "tool-1.0.0.tar.gz"
    payload = b"archive"
    _, runner = _script_member_runner(member, body, workdir=workdir, files={asset: payload})
    method = Method(
        kind="tarball",
        params={
            "url": "https://x/tool-1.0.0.tar.gz",
            "member": "tool",
            "sha256": "0" * 64,
            "bin_dir": str(tmp_path / "bin"),
        },
    )
    with pytest.raises(ChecksumMismatch):
        install_download(method, _ctx(runner))
    assert not marker.exists()


def test_declared_smoke_argv_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = tmp_path / ".local" / "opt" / "tool" / "tool"
    body = _member_script(
        127,
        extra='if [ "$1" = "--custom" ]; then exit 0; fi\n',
    )
    _, runner = _script_member_runner(member, body)
    bin_dir = tmp_path / "bin"
    params: dict[str, object] = {
        "repo": "x/y",
        "asset": "tool-{ver}.tar.gz",
        "member": "tool",
        "bin_dir": str(bin_dir),
    }
    with pytest.raises(ExecutorError):
        install_download(Method("github_release", params), _ctx(runner, tmp_version="1.0.0"))
    custom = Method(
        kind="github_release",
        params={**params, "smoke_argv": ["--custom"]},
    )
    install_download(custom, _ctx(runner, tmp_version="1.0.0"))
    assert (bin_dir / "tool").is_symlink()


def test_update_download_does_not_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _binary, link = _plant_archive_install(tmp_path)
    body = _member_script(127)
    _calls, runner = _curl_and_extract_runner({}, extracted=body)
    result = update_download(
        _rg_update_method(tmp_path / "bin"), _ctx(runner, tmp_version="15.1.0")
    )
    assert result.verified is False
    assert (opt / "rg").read_bytes() == body
    assert link.exists()


def test_failed_extraction_leaves_no_staged_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt = tmp_path / ".local" / "opt" / "rg"
    binary = opt / "rg"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"good")
    planted = opt / "planted"
    planted.write_bytes(b"planted")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    os.symlink(str(binary), bin_dir / "rg")
    member = binary
    workdir = _workdir(tmp_path, monkeypatch)
    checksum_name = f"{RG_ASSET}.sha256"
    digest_line = (
        f"0eb3e36bfb24dcd9bb1d1bece1531216b59539a8fde17ee80224af0653c92aa3  {RG_ASSET}\n"
    ).encode()
    _calls, base_runner = fixture_runner(
        workdir,
        {RG_ASSET: b"archive", checksum_name: digest_line},
        member=member,
    )

    def failing_runner(cmd: list[str]) -> None:
        base_runner(cmd)
        if cmd and cmd[0] == "tar":
            raise CommandError(cmd, 1, detail="extract failed")

    with pytest.raises(CommandError):
        install_download(_rg_method(bin_dir), _ctx(failing_runner, tmp_version="15.1.0"))
    assert not staged_sibling(opt, NEW_SUFFIX).exists()
    assert binary.read_bytes() == b"good"
    assert planted.read_bytes() == b"planted"
    assert os.readlink(bin_dir / "rg") == str(binary)


def test_member_symlink_outside_staging_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    opt = tmp_path / ".local" / "opt" / "tool"
    member_name = "tool"
    outside = tmp_path / "outside.sh"
    outside.write_text("#!/bin/sh\n: > marker\n", encoding="utf-8")
    outside.chmod(0o644)
    marker = tmp_path / "marker"
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            dest = Path(cmd[cmd.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"archive")
        if _is_extraction(cmd):
            dest = _extract_dest(cmd)
            (dest / member_name).symlink_to(outside)

    method = Method(
        kind="github_release",
        params={
            "repo": "x/y",
            "asset": "tool-{ver}.tar.gz",
            "member": member_name,
            "bin_dir": str(bin_dir),
        },
    )
    with pytest.raises(ExecutorError, match=member_name):
        install_download(method, _ctx(runner, tmp_version="1.0.0"))
    assert outside.stat().st_mode & 0o777 == 0o644
    assert not marker.exists()
    assert not staged_sibling(opt, NEW_SUFFIX).exists()
    assert not (bin_dir / member_name).exists()


def test_member_symlink_inside_staging_installs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            dest = Path(cmd[cmd.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"archive")
        if _is_extraction(cmd):
            dest = _extract_dest(cmd)
            real_path = dest / "real"
            real_path.parent.mkdir(parents=True, exist_ok=True)
            real_path.write_bytes(_MEMBER_SCRIPT)
            real_path.chmod(0o755)
            (dest / "tool").symlink_to("real")

    method = Method(
        kind="github_release",
        params={
            "repo": "x/y",
            "asset": "tool-{ver}.tar.gz",
            "member": "tool",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner, tmp_version="1.0.0"))
    link = bin_dir / "tool"
    assert link.is_symlink()
    resolved = Path(os.readlink(link)).resolve()
    assert str(resolved).startswith(str((tmp_path / ".local" / "opt" / "tool").resolve()))


def test_fresh_install_failure_after_relink_leaves_no_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    _, runner = fixture_runner(None, {RG_ASSET: b"archive"}, member=member)
    real_replace_symlink = download.replace_symlink

    def boom_after_relink(link: Path, target: str) -> None:
        real_replace_symlink(link, target)
        raise OSError("post-swap validation failed")

    monkeypatch.setattr(download, "replace_symlink", boom_after_relink)
    with pytest.raises(ExecutorError):
        install_download(_rg_method(bin_dir), _ctx(runner, tmp_version="15.1.0"))
    link = bin_dir / "rg"
    assert not link.exists()
    assert not link.is_symlink()
    opt = tmp_path / ".local" / "opt" / "rg"
    assert not opt.exists()
    assert not staged_sibling(opt, NEW_SUFFIX).exists()
    assert not staged_sibling(opt, atomic.OLD_SUFFIX).exists()


def test_raw_asset_is_smoked_before_it_replaces_the_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bindir = tmp_path / "bin"
    workdir = _workdir(tmp_path, monkeypatch)
    asset = "yq_linux_amd64"
    bad = _member_script(127)
    _, runner = _script_member_runner(
        tmp_path / ".local" / "bin" / "yq", bad, workdir=workdir, files={asset: bad}
    )
    with pytest.raises(ExecutorError):
        install_download(_raw_method(bindir), _ctx(runner, tmp_version="v14.1.0"))
    link = bindir / "yq"
    assert not link.exists()
    assert not staged_sibling(link, NEW_SUFFIX).exists()

    good = _MEMBER_SCRIPT
    _, runner2 = _script_member_runner(
        tmp_path / ".local" / "bin" / "yq", good, workdir=workdir, files={asset: good}
    )
    install_download(_raw_method(bindir), _ctx(runner2, tmp_version="v14.1.0"))
    assert (bindir / "yq").read_bytes() == good


def test_raw_update_does_not_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bindir = tmp_path / "bin"
    link = bindir / "yq"
    _plant_executable(link, _MEMBER_SCRIPT)
    bad = _member_script(127)
    _, runner = _curl_and_extract_runner({"yq_linux_amd64": bad})
    result = update_download(_raw_method(bindir), _ctx(runner))
    assert result.verified is False
    assert link.read_bytes() == bad
