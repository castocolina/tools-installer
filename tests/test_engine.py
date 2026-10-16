import hashlib
import json
import os
import urllib.request
from pathlib import Path

import pytest

import installer.engine as engine
from installer import executors, receipts
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.engine import install_tool
from installer.enums import InstallStatus
from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.run import CommandError
from installer.versions import Release, VersionError
from tests.test_apps import SHELLED_LINKERS
from tests.test_download import fixture_runner


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def _tool(
    *methods: Method,
    postinstall: str | None = None,
    post_install: tuple[str, ...] = (),
    tool_id: str = "rg",
) -> Tool:
    return Tool(
        id=tool_id,
        name="ripgrep",
        category="search",
        cmd="rg",
        methods=methods,
        postinstall=postinstall,
        post_install=post_install,
    )


@pytest.fixture(autouse=True)
def scratch_path_for_manager_smoke(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    sandbox = tmp_path / "path-sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("PATH", str(sandbox))
    return sandbox


def _macos_with_brew() -> Platform:
    return Platform(os="macos", arch="arm64", immutable=False, has_brew=True)


def _write_cmd(scratch: Path, name: str, exit_code: int) -> None:
    script = scratch / name
    script.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    script.chmod(0o755)


def _patch_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "is_installed", _always_not_installed)


def _always_not_installed(_tool: Tool) -> bool:
    return False


def test_already_installed_short_circuits(monkeypatch: pytest.MonkeyPatch):
    def fake_installed(tool: Tool) -> bool:
        return True

    monkeypatch.setattr(engine, "is_installed", fake_installed)
    calls: list[list[str]] = []
    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=lambda cmd: calls.append(cmd),
    )
    assert outcome.status == "already-installed"
    assert outcome.method_kind is None
    assert calls == []


def test_first_method_succeeds(monkeypatch: pytest.MonkeyPatch):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    calls: list[list[str]] = []
    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "ripgrep"}),
            Method(kind="brew", params={"formula": "ripgrep"}),
        ),
        _platform(),
        runner=lambda cmd: calls.append(cmd),
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "dnf"
    assert calls == [["sudo", "dnf", "install", "-y", "ripgrep"]]


def test_install_tool_prepends_declared_bin_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A later tool in the same process must see a just-installed bin dir.

    pnpm's script method lands the `pnpm` binary in a declared bin_dir that is
    not on the installer process PATH until we prepend it. Without this, a
    subsequent node tool (puppeteer) reports 'pnpm not found' after pnpm just
    installed successfully in the same --all run.
    """

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    scratch = tmp_path / "path-minimal"
    scratch.mkdir()
    monkeypatch.setenv("PATH", str(scratch))
    dest = tmp_path / "pnpm-bin"
    dest.mkdir()
    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep", "bin_dir": str(dest)})),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert os.environ["PATH"].split(os.pathsep)[0] == str(dest)


def test_falls_through_to_next_method_on_failure(monkeypatch: pytest.MonkeyPatch):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    attempted: list[str] = []

    def runner(cmd: list[str]) -> None:
        attempted.append(cmd[0])
        if cmd[0] == "sudo":
            raise CommandError(cmd, 1)
        # brew succeeds

    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "ripgrep"}),
            Method(kind="brew", params={"formula": "ripgrep"}),
        ),
        platform,
        runner=runner,
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "brew"
    assert attempted == ["sudo", "brew"]


def test_no_applicable_methods(monkeypatch: pytest.MonkeyPatch):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    outcome = install_tool(
        _tool(Method(kind="brew", params={"formula": "ripgrep"})),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "no-method"
    assert outcome.method_kind is None


def test_all_methods_fail_returns_failed(monkeypatch: pytest.MonkeyPatch):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=runner,
    )
    assert outcome.status == "failed"
    assert outcome.method_kind is None
    assert len(outcome.errors) == 1


def test_github_release_routes_to_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    import installer.download as download_mod

    workdir = tmp_path / "dl"
    workdir.mkdir()

    def fake_mkdtemp(prefix: str) -> str:
        return str(workdir)

    monkeypatch.setattr(download_mod.tempfile, "mkdtemp", fake_mkdtemp)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    asset = "rg-14.1.0-x86_64.tar.gz"
    calls, runner = fixture_runner(workdir, {asset: b"archive"}, member=member)
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "rg-{ver}-{arch.machine}.tar.gz",
            "member": "rg",
            "bin_dir": str(bin_dir),
        },
    )

    def resolve_tag(repo: str) -> str:
        return "14.1.0"

    outcome = install_tool(
        _tool(method),
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=runner,
        resolve_tag=resolve_tag,
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "github_release"
    assert calls[0][0] == "curl" and asset in calls[0][3]
    link = bin_dir / "rg"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    assert not any(cmd and cmd[0] in SHELLED_LINKERS for cmd in calls)


def test_smoke_failure_falls_through_to_the_next_method(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    bin_dir = tmp_path / "bin"
    fail_body = b"#!/bin/sh\nexit 127\n"
    ok_body = b"#!/bin/sh\nexit 0\n"

    first = Method(
        kind="github_release",
        params={
            "repo": "x/y",
            "asset": "rg-{ver}.tar.gz",
            "member": "rg",
            "bin_dir": str(bin_dir),
        },
    )
    second = Method(
        kind="github_release",
        params={
            "repo": "x/y2",
            "asset": "rg-{ver}.tar.gz",
            "member": "rg",
            "bin_dir": str(bin_dir),
            "bin_name": "rg2",
        },
    )
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            dest = Path(cmd[cmd.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"archive")
        if cmd and cmd[0] == "tar":
            dest = Path(cmd[cmd.index("-C") + 1])
            from installer.atomic import NEW_SUFFIX

            if dest.name.endswith(NEW_SUFFIX):
                live = dest.parent / dest.name[: -len(NEW_SUFFIX)]
            else:
                live = dest
            if live.name == "rg":
                target = dest / "rg"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(fail_body)
                target.chmod(0o755)
            elif live.name == "rg2":
                target = dest / "rg"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(ok_body)
                target.chmod(0o755)

    outcome = install_tool(
        _tool(first, second, tool_id="rg"),
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=runner,
        resolve_tag=lambda _repo: "1.0.0",
    )
    assert outcome.status == "installed"
    link = bin_dir / "rg2"
    assert link.is_symlink()
    assert "rg2" in os.readlink(link)
    assert calls

    rg_link = bin_dir / "rg"
    assert not rg_link.exists() and not rg_link.is_symlink()
    assert not (tmp_path / ".local" / "opt" / "rg").exists()


def test_an_oserror_in_one_method_falls_through_to_the_next(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import errno

    import installer.download as download_mod

    _patch_not_installed(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    first = Method(
        kind="tarball",
        params={"url": "https://x/a", "member": "rg", "raw": True, "bin_dir": str(bin_dir)},
    )
    second = Method(
        kind="tarball",
        params={"url": "https://x/b", "member": "rg", "bin_dir": str(bin_dir)},
    )
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    _calls, inner = fixture_runner(None, {"a": b"raw-bytes", "b": b"archive"}, member=member)
    real_copy2 = download_mod.shutil.copy2

    def boom_copy2(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
        *,
        follow_symlinks: bool = True,
    ) -> None:
        if str(dst).endswith(".tools-installer.new"):
            raise OSError(errno.ENOSPC, "No space left on device")
        real_copy2(src, dst, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(download_mod.shutil, "copy2", boom_copy2)

    def runner(cmd: list[str]) -> None:
        inner(cmd)

    outcome = install_tool(_tool(first, second), _platform(), runner=runner)
    assert outcome.status == InstallStatus.INSTALLED
    assert (bin_dir / "rg").is_symlink()


def test_an_oserror_in_the_only_method_is_a_failed_outcome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import errno

    import installer.download as download_mod

    _patch_not_installed(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    first = Method(
        kind="tarball",
        params={"url": "https://x/a", "member": "rg", "raw": True, "bin_dir": str(bin_dir)},
    )
    _calls, inner = fixture_runner(None, {"a": b"raw-bytes"}, member=None)

    def boom_copy2(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
        *,
        follow_symlinks: bool = True,
    ) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(download_mod.shutil, "copy2", boom_copy2)

    def runner(cmd: list[str]) -> None:
        inner(cmd)

    outcome = install_tool(_tool(first), _platform(), runner=runner)
    assert outcome.status == InstallStatus.FAILED
    assert isinstance(outcome.errors[-1], OSError)


def test_single_failing_method_leaves_no_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    _calls, base = fixture_runner(None, {"rg-1.0.0.tar.gz": b"archive"}, member=member)

    def runner(cmd: list[str]) -> None:
        base(cmd)
        if cmd and cmd[0] == "tar":
            dest = Path(cmd[cmd.index("-C") + 1])
            target = dest / "rg"
            target.write_bytes(b"#!/bin/sh\nexit 127\n")
            target.chmod(0o755)

    method = Method(
        kind="github_release",
        params={
            "repo": "x/y",
            "asset": "rg-{ver}.tar.gz",
            "member": "rg",
            "bin_dir": str(bin_dir),
        },
    )
    outcome = install_tool(
        _tool(method),
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=runner,
        resolve_tag=lambda _repo: "1.0.0",
    )
    assert outcome.status == "failed"
    assert not (bin_dir / "rg").exists()
    assert not (tmp_path / ".local" / "opt" / "rg").exists()


def test_github_release_directory_member_falls_through_the_ladder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A directory member is an executor error, so the ladder tries the next method."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    calls, runner = fixture_runner(None, {}, member=member)
    download = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "rg-{ver}-{arch.machine}.tar.gz",
            "member": "rg",
            "bin_dir": str(bin_dir),
        },
    )
    brew = Method(kind="brew", params={"formula": "ripgrep"})

    def resolve_tag(repo: str) -> str:
        return "14.1.0"

    def plant_directory(cmd: list[str]) -> None:
        runner(cmd)
        if cmd and cmd[0] == "tar":
            dest = Path(cmd[cmd.index("-C") + 1])
            from installer.atomic import NEW_SUFFIX

            live_opt = (
                dest.parent / dest.name[: -len(NEW_SUFFIX)]
                if dest.name.endswith(NEW_SUFFIX)
                else dest
            )
            staged = dest / member.relative_to(live_opt)
            if staged.exists():
                staged.unlink()
                staged.mkdir()

    outcome = install_tool(
        _tool(download, brew),
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
        runner=plant_directory,
        resolve_tag=resolve_tag,
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "brew"
    link = bin_dir / "rg"
    assert not link.exists()
    assert not link.is_symlink()
    assert any(cmd and cmd[0] == "brew" for cmd in calls)


def test_download_failure_is_caught_as_failed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    def resolve_tag(repo: str) -> str:
        return "14.1.0"

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
        resolve_tag=resolve_tag,
    )
    assert outcome.status == "failed"
    assert len(outcome.errors) == 1


def test_version_resolution_failure_is_caught_as_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    def resolve_tag(repo: str) -> str:
        raise VersionError("network down")

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
        resolve_tag=resolve_tag,
    )
    assert outcome.status == "failed"
    assert len(outcome.errors) == 1
    assert isinstance(outcome.errors[0], VersionError)
    assert calls == []  # resolution fails before any command runs


def _mismatching_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_install_download(method: Method, ctx: ExecContext) -> str | None:
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


def test_checksum_mismatch_halts_the_ladder_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _not_installed(monkeypatch)
    _mismatching_download(monkeypatch)
    calls: list[list[str]] = []
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    outcome = install_tool(_gh_then_brew(), platform, runner=lambda cmd: calls.append(cmd))
    assert outcome.status == "checksum-mismatch"
    assert outcome.method_kind == "github_release"
    assert isinstance(outcome.errors[0], ChecksumMismatch)
    assert calls == []  # brew was never attempted


def test_checksum_policy_continue_falls_through_to_brew(monkeypatch: pytest.MonkeyPatch) -> None:
    _not_installed(monkeypatch)
    _mismatching_download(monkeypatch)
    calls: list[list[str]] = []
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    outcome = install_tool(
        _gh_then_brew(),
        platform,
        runner=lambda cmd: calls.append(cmd),
        checksum_policy="continue",
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "brew"
    assert calls == [["brew", "install", "ripgrep"]]


def test_installed_outcome_carries_verified_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _not_installed(monkeypatch)

    def fake_install_download(method: Method, ctx: ExecContext) -> str | None:
        return None

    monkeypatch.setattr(engine.download, "install_download", fake_install_download)
    outcome = install_tool(
        _tool(Method(kind="github_release", params={"repo": "x/y", "asset": "a", "member": "rg"})),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert outcome.verified is True


def test_non_download_install_is_not_marked_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    _not_installed(monkeypatch)
    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert outcome.verified is False


def test_app_kind_routes_to_app_executor(monkeypatch: pytest.MonkeyPatch):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    seen: list[str] = []

    def fake_install_app(method: Method, runner: object) -> str | None:
        seen.append(method.kind)
        return "unpinned url; no sha256 to verify against"

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


def test_host_setup_kind_routes_to_host_setup_handoff(monkeypatch: pytest.MonkeyPatch):
    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    method = Method(kind="host_setup", params={"setup_id": "pi"})
    outcome = install_tool(
        _tool(method),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == InstallStatus.MANUAL_REQUIRED
    assert outcome.method_kind == "host_setup"
    assert outcome.handoff == executors.host_setup_handoff(method)


def test_postinstall_hook_dispatches_after_a_successful_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _not_installed(monkeypatch)
    seen: list[tuple[object, object, object, object]] = []

    def fake_run_postinstall(name: str, method: Method, runner: object, tools: object) -> None:
        seen.append((name, method, runner, tools))
        return None

    monkeypatch.setattr(engine, "run_postinstall", fake_run_postinstall)
    method = Method(kind="dnf", params={"package": "codegraph"})
    tools = {"claude": _tool()}

    def runner(cmd: list[str]) -> None:
        return None

    outcome = install_tool(
        _tool(method, postinstall="codegraph-mcp-register"),
        _platform(),
        runner=runner,
        tools=tools,
    )
    assert outcome.status == "installed"
    assert outcome.postinstall_warning is None
    assert len(seen) == 1
    name, called_method, called_runner, called_tools = seen[0]
    assert name == "codegraph-mcp-register"
    assert called_method is method
    assert called_runner is runner
    assert called_tools is tools


def test_postinstall_hook_sees_the_same_tools_freshly_prepended_bin_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bin_dir must be on PATH before the tool's own postinstall hook runs.

    A hook that resolves its own just-installed binary via PATH (rather than
    an explicit bin_dir path) must see it — prepend_path has to run before
    postinstall dispatch, not after.
    """
    _not_installed(monkeypatch)
    scratch = tmp_path / "path-minimal"
    scratch.mkdir()
    monkeypatch.setenv("PATH", str(scratch))
    dest = tmp_path / "tool-bin"
    dest.mkdir()
    seen_path: list[str] = []

    def fake_run_postinstall(name: str, method: Method, runner: object, tools: object) -> None:
        seen_path.append(os.environ["PATH"])
        return None

    monkeypatch.setattr(engine, "run_postinstall", fake_run_postinstall)
    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "ripgrep", "bin_dir": str(dest)}),
            postinstall="codegraph-mcp-register",
        ),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert seen_path == [os.environ["PATH"]]
    assert seen_path[0].split(os.pathsep)[0] == str(dest)


def test_postinstall_failure_does_not_fail_the_install(monkeypatch: pytest.MonkeyPatch) -> None:
    _not_installed(monkeypatch)

    def fake_run_postinstall(name: str, method: Method, runner: object, tools: object) -> str:
        return "codegraph MCP registration failed: exit 1"

    monkeypatch.setattr(engine, "run_postinstall", fake_run_postinstall)
    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "codegraph"}),
            postinstall="codegraph-mcp-register",
        ),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert outcome.postinstall_warning == "codegraph MCP registration failed: exit 1"


def test_postinstall_hook_exception_does_not_fail_the_install_or_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _not_installed(monkeypatch)

    def fake_run_postinstall(
        name: str, method: Method, runner: object, tools: object
    ) -> str | None:
        raise RuntimeError("hook bug")

    monkeypatch.setattr(engine, "run_postinstall", fake_run_postinstall)
    attempted: list[str] = []

    def runner(cmd: list[str]) -> None:
        attempted.append(cmd[0])

    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "codegraph"}),
            Method(kind="brew", params={"formula": "codegraph"}),
            postinstall="codegraph-mcp-register",
        ),
        _platform(),
        runner=runner,
    )
    assert outcome.status == "installed"
    assert outcome.postinstall_warning is not None
    assert "crashed" in outcome.postinstall_warning
    assert "hook bug" in outcome.postinstall_warning
    # Only the first (successful) method's own command ran; the fallback
    # brew method was never attempted once the first method succeeded.
    assert attempted == ["sudo"]


def test_no_postinstall_field_means_no_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    _not_installed(monkeypatch)
    calls: list[object] = []

    def spy_run_postinstall(name: str, method: Method, runner: object, tools: object) -> None:
        calls.append(name)
        return None

    monkeypatch.setattr(engine, "run_postinstall", spy_run_postinstall)
    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "installed"
    assert outcome.postinstall_warning is None
    assert calls == []


def test_already_installed_never_dispatches_postinstall(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_installed(tool: Tool) -> bool:
        return True

    monkeypatch.setattr(engine, "is_installed", fake_installed)
    calls: list[object] = []

    def spy_run_postinstall(name: str, method: Method, runner: object, tools: object) -> None:
        calls.append(name)
        return None

    monkeypatch.setattr(engine, "run_postinstall", spy_run_postinstall)
    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "codegraph"}),
            postinstall="codegraph-mcp-register",
        ),
        _platform(),
        runner=lambda cmd: None,
    )
    assert outcome.status == "already-installed"
    assert calls == []


def test_failed_install_never_dispatches_postinstall(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool with no successful method has nothing to dispatch after."""
    _not_installed(monkeypatch)
    calls: list[object] = []

    def spy_run_postinstall(name: str, method: Method, runner: object, tools: object) -> None:
        calls.append(name)
        return None

    monkeypatch.setattr(engine, "run_postinstall", spy_run_postinstall)

    def failing_runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "codegraph"}),
            postinstall="codegraph-mcp-register",
        ),
        _platform(),
        runner=failing_runner,
    )
    assert outcome.status == "failed"
    assert outcome.postinstall_warning is None
    assert calls == []


def test_login_shell_action_dispatches_reviewed_instructions_after_oh_my_zsh_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    _not_installed(monkeypatch)
    omz = next(t for t in load_tools(Path("installer/registry.toml")) if t.id == "oh-my-zsh")
    asked: list[tuple[str, str]] = []
    calls: list[list[str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    outcome = install_tool(
        omz,
        _platform(),
        runner=lambda cmd: calls.append(cmd),
        confirm_sensitive_action=confirm,
    )
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.post_install_handoff
    assert any("chsh -s" in line for line in outcome.post_install_handoff)
    assert asked == [("oh-my-zsh", "set_login_shell")]
    assert len(calls) == 1


def test_login_shell_action_is_not_offered_when_tool_declares_no_post_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _not_installed(monkeypatch)
    asked: list[tuple[str, str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=lambda cmd: None,
        confirm_sensitive_action=confirm,
    )
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.post_install_handoff == ()
    assert asked == []


def test_already_installed_login_shell_never_invokes_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_installed(tool: Tool) -> bool:
        return True

    monkeypatch.setattr(engine, "is_installed", fake_installed)
    asked: list[tuple[str, str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    outcome = install_tool(
        _tool(
            Method(kind="script", params={"url": "u"}),
            post_install=("set_login_shell",),
            tool_id="oh-my-zsh",
        ),
        _platform(),
        runner=lambda cmd: None,
        confirm_sensitive_action=confirm,
    )
    assert outcome.status == InstallStatus.ALREADY_INSTALLED
    assert outcome.post_install_handoff == ()
    assert asked == []


def test_manual_required_login_shell_never_invokes_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _not_installed(monkeypatch)
    asked: list[tuple[str, str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    outcome = install_tool(
        _tool(
            Method(kind="host_setup", params={"setup_id": "pi"}),
            post_install=("set_login_shell",),
            tool_id="oh-my-zsh",
        ),
        _platform(),
        runner=lambda cmd: None,
        confirm_sensitive_action=confirm,
    )
    assert outcome.status == InstallStatus.MANUAL_REQUIRED
    assert outcome.post_install_handoff == ()
    assert asked == []


def test_raising_confirm_degrades_to_named_warning_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    _not_installed(monkeypatch)

    def boom(tool_id: str, action: str) -> bool:
        raise RuntimeError("confirm exploded")

    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "ripgrep"}),
            post_install=("set_login_shell",),
            tool_id="oh-my-zsh",
        ),
        _platform(),
        runner=lambda cmd: None,
        confirm_sensitive_action=boom,
    )
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.post_install_handoff == ()
    assert outcome.postinstall_warning is not None
    assert "confirm exploded" in outcome.postinstall_warning


def test_repair_walks_the_ladder_past_already_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_installed(tool: Tool) -> bool:
        return True

    monkeypatch.setattr(engine, "is_installed", fake_installed)
    calls: list[list[str]] = []
    outcome = install_tool(
        _tool(Method(kind="dnf", params={"package": "ripgrep"})),
        _platform(),
        runner=lambda cmd: calls.append(cmd),
        repair=True,
    )
    assert outcome.status == InstallStatus.INSTALLED
    assert calls == [["sudo", "dnf", "install", "-y", "ripgrep"]]


def test_repair_dispatches_post_install_like_a_fresh_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)

    def fake_installed(tool: Tool) -> bool:
        return True

    monkeypatch.setattr(engine, "is_installed", fake_installed)
    asked: list[tuple[str, str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    outcome = install_tool(
        _tool(
            Method(kind="dnf", params={"package": "ripgrep"}),
            post_install=("set_login_shell",),
            tool_id="oh-my-zsh",
        ),
        _platform(),
        runner=lambda cmd: None,
        confirm_sensitive_action=confirm,
        repair=True,
    )
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.post_install_handoff
    assert any("chsh -s" in line for line in outcome.post_install_handoff)
    assert asked == [("oh-my-zsh", "set_login_shell")]


def _shelltool() -> Tool:
    return _tool(
        Method(kind="script", params={"url": "u"}),
        post_install=("set_login_shell",),
        tool_id="shelltool",
    )


def _stub_chsh(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)


def _confirm(answer: bool) -> ConfirmSensitiveAction:
    def confirm(_tool_id: str, _action: str) -> bool:
        return answer

    return confirm


def test_reapply_post_install_returns_handoff_without_installing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch)
    outcome = engine.reapply_post_install(_shelltool(), _platform(), confirm=_confirm(True))
    assert outcome.tool_id == "shelltool"
    assert outcome.status == InstallStatus.ALREADY_INSTALLED
    assert any("chsh -s" in line for line in outcome.post_install_handoff)
    declined = engine.reapply_post_install(_shelltool(), _platform(), confirm=_confirm(False))
    assert declined.post_install_handoff == ()


def test_reapply_post_install_isolates_a_raising_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> tuple[str, ...]:
        raise RuntimeError("action exploded")

    monkeypatch.setattr(engine, "run_post_install", boom)
    outcome = engine.reapply_post_install(_shelltool(), _platform(), confirm=_confirm(True))
    assert outcome.status == InstallStatus.ALREADY_INSTALLED
    assert outcome.postinstall_warning is not None
    assert "action exploded" in outcome.postinstall_warning


def test_digest_mismatch_fails_with_nothing_linked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    asset = "rg-14.1.0-x86_64.tar.gz"
    payload = b"archive-bytes"

    def fake_release_resolver(_resolve_tag: object):
        def resolve(_repo: str) -> Release:
            return Release("14.1.0", {asset: "f" * 64})

        return resolve

    monkeypatch.setattr(engine, "release_resolver", fake_release_resolver)

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    workdir = tmp_path / "dl"
    workdir.mkdir()

    def pin_workdir(prefix: str) -> str:
        return str(workdir)

    monkeypatch.setattr(engine.download.tempfile, "mkdtemp", pin_workdir)
    rg_member = tmp_path / ".local" / "opt" / "rg" / "rg"
    calls, runner = fixture_runner(workdir, {asset: payload}, member=rg_member)
    bindir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "rg-{ver}-{arch.machine}.tar.gz",
            "member": "rg",
            "bin_dir": str(bindir),
        },
    )
    outcome = install_tool(
        _tool(method),
        _platform(),
        runner=runner,
    )
    assert outcome.status == InstallStatus.CHECKSUM_MISMATCH
    assert not (bindir / "rg").exists()
    assert not (tmp_path / ".local" / "opt" / "rg").exists()
    assert len(calls) >= 1


def test_pinned_app_mismatch_moves_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _patch_not_installed(monkeypatch)
    payload = b"drawio-zip"
    marker = tmp_path / "cli-ran.marker"
    cli_script = f'#!/bin/sh\n: > {marker}\nif [ "$1" = "--version" ]; then exit 0; fi\nexit 0\n'
    member = Path("draw.io.app/Contents/MacOS/draw.io")

    def app_runner(cmd: list[str]) -> None:
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            dest = Path(cmd[cmd.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
        elif cmd and cmd[0] == "ditto":
            dest = Path(cmd[-1])
            target = dest / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(cli_script, encoding="utf-8")
            target.chmod(0o755)

    method = Method(
        kind="app",
        params={
            "url": (
                "https://github.com/jgraph/drawio-desktop/releases/download/v{ver}/"
                "draw.io-arm64-{ver}.zip"
            ),
            "version": "32.4.1",
            "app": "draw.io.app",
            "cli": "Contents/MacOS/draw.io",
            "cli_name": "drawio",
            "sha256": "0" * 64,
        },
    )
    outcome = install_tool(
        _tool(method, tool_id="drawio-desktop"),
        Platform(os="macos", arch="arm64", immutable=False, has_brew=False),
        runner=app_runner,
    )
    assert outcome.status == InstallStatus.CHECKSUM_MISMATCH
    assert not (tmp_path / "Applications" / "draw.io.app").exists()
    assert not (tmp_path / ".local" / "bin" / "drawio").exists()
    assert not marker.exists()


@pytest.mark.parametrize(
    ("verified", "unverified_reason"),
    [
        (False, "no checksum file and no GitHub sha256 digest for rg-14.1.0-x86_64.tar.gz"),
        (False, "unpinned url; no sha256 to verify against"),
        (True, None),
    ],
    ids=("no-digest-github", "tarball", "digest-verified"),
)
def test_engine_outcome_carries_the_unverified_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    verified: bool,
    unverified_reason: str | None,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    bindir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "rg" / "rg"

    if verified:
        asset = "rg-14.1.0-x86_64.tar.gz"
        payload = b"archive-bytes"
        digest = hashlib.sha256(payload).hexdigest()

        def fake_release_resolver(_resolve_tag: object):
            def resolve(_repo: str) -> Release:
                return Release("14.1.0", {asset: digest})

            return resolve

        monkeypatch.setattr(engine, "release_resolver", fake_release_resolver)
        workdir = tmp_path / "dl"
        workdir.mkdir()

        def pin_workdir(prefix: str) -> str:
            return str(workdir)

        monkeypatch.setattr(engine.download.tempfile, "mkdtemp", pin_workdir)
        _, runner = fixture_runner(workdir, {asset: payload}, member=member)
        method = Method(
            kind="github_release",
            params={
                "repo": "BurntSushi/ripgrep",
                "asset": "rg-{ver}-{arch.machine}.tar.gz",
                "member": "rg",
                "bin_dir": str(bindir),
            },
        )
    elif unverified_reason is not None and unverified_reason.startswith("unpinned"):
        _, runner = fixture_runner(None, {}, member=member)
        method = Method(
            kind="tarball",
            params={"url": "https://x/eza.tar.gz", "member": "rg", "bin_dir": str(bindir)},
        )
    else:

        def empty_release(_resolve_tag: object):
            def resolve(_repo: str) -> Release:
                return Release("14.1.0", {})

            return resolve

        monkeypatch.setattr(engine, "release_resolver", empty_release)
        _, runner = fixture_runner(None, {}, member=member)
        method = Method(
            kind="github_release",
            params={
                "repo": "BurntSushi/ripgrep",
                "asset": "rg-{ver}-{arch.machine}.tar.gz",
                "member": "rg",
                "bin_dir": str(bindir),
            },
        )

    outcome = install_tool(_tool(method), _platform(), runner=runner)
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.verified is verified
    assert outcome.unverified_reason == unverified_reason


@pytest.mark.parametrize("wrong_digest", [False, True], ids=("matching", "wrong"))
def test_default_resolver_verifies_against_the_api_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    wrong_digest: bool,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    repo = "BurntSushi/ripgrep"
    asset = "rg-14.1.0-x86_64.tar.gz"
    payload = b"archive-bytes"
    good_digest = hashlib.sha256(payload).hexdigest()
    api_digest = ("f" * 64) if wrong_digest else good_digest
    requested: list[str] = []

    class FakeResp:
        def __enter__(self) -> "FakeResp":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "tag_name": "14.1.0",
                    "assets": [{"name": asset, "digest": f"sha256:{api_digest}"}],
                }
            ).encode()

    def fake_urlopen(req: urllib.request.Request, timeout: int) -> FakeResp:
        requested.append(req.full_url)
        return FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    workdir = tmp_path / "dl"
    workdir.mkdir()

    def pin_workdir(prefix: str) -> str:
        return str(workdir)

    monkeypatch.setattr(engine.download.tempfile, "mkdtemp", pin_workdir)
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    _, runner = fixture_runner(workdir, {asset: payload}, member=member)
    bindir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": repo,
            "asset": "rg-{ver}-{arch.machine}.tar.gz",
            "member": "rg",
            "bin_dir": str(bindir),
        },
    )
    outcome = install_tool(_tool(method), _platform(), runner=runner)
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    assert requested == [api_url]
    if wrong_digest:
        assert outcome.status == InstallStatus.CHECKSUM_MISMATCH
        assert not (bindir / "rg").exists()
        assert not (tmp_path / ".local" / "opt" / "rg").exists()
    else:
        assert outcome.status == InstallStatus.INSTALLED
        assert outcome.verified is True
        assert outcome.unverified_reason is None


def test_manager_install_with_a_broken_binary_falls_through(
    monkeypatch: pytest.MonkeyPatch, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)
    scratch = scratch_path_for_manager_smoke
    stages: list[str] = []

    def runner(cmd: list[str]) -> None:
        if cmd[:2] == ["brew", "install"] and "--cask" not in cmd:
            _write_cmd(scratch, "rg", 127)
            stages.append("brew")
        elif cmd[:2] == ["brew", "install"] and "--cask" in cmd:
            _write_cmd(scratch, "rg", 0)
            stages.append("cask")

    tool = _tool(
        Method(kind="brew", params={"formula": "ripgrep"}),
        Method(kind="cask", params={"cask": "ripgrep"}),
    )
    outcome = install_tool(tool, _macos_with_brew(), runner=runner)
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.method_kind == "cask"
    assert stages == ["brew", "cask"]

    stages.clear()

    def broken_runner(cmd: list[str]) -> None:
        _write_cmd(scratch, "rg", 127)
        stages.append(cmd[0])

    outcome = install_tool(
        _tool(Method(kind="brew", params={"formula": "ripgrep"})),
        _macos_with_brew(),
        runner=broken_runner,
    )
    assert outcome.status == InstallStatus.FAILED
    assert stages == ["brew"]
    assert outcome.errors


def test_manager_install_with_a_working_binary_is_installed(
    monkeypatch: pytest.MonkeyPatch, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)
    scratch = scratch_path_for_manager_smoke

    def runner(_cmd: list[str]) -> None:
        _write_cmd(scratch, "rg", 0)

    outcome = install_tool(
        _tool(Method(kind="brew", params={"formula": "ripgrep"})),
        _macos_with_brew(),
        runner=runner,
    )
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.method_kind == "brew"


def test_manager_install_without_a_resolvable_cmd_skips_smoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_not_installed(monkeypatch)
    calls: list[Path] = []

    def recording_smoke(
        path: Path,
        argv: tuple[str, ...] = ("--version",),
        **_ignored: object,
    ) -> None:
        calls.append(path)

    monkeypatch.setattr(executors, "smoke_binary", recording_smoke)
    outcome = install_tool(
        _tool(Method(kind="brew", params={"formula": "ripgrep"})),
        _macos_with_brew(),
        runner=lambda _cmd: None,
    )
    assert outcome.status == InstallStatus.INSTALLED
    assert calls == []


def test_handoff_kinds_are_never_smoked(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_not_installed(monkeypatch)
    calls: list[Path] = []

    def fail_if_smoked(
        path: Path,
        argv: tuple[str, ...] = ("--version",),
        **_ignored: object,
    ) -> None:
        calls.append(path)
        raise AssertionError("handoff methods must not be smoked")

    monkeypatch.setattr(executors, "smoke_binary", fail_if_smoked)
    method = Method(kind="host_setup", params={"setup_id": "pi"})
    outcome = install_tool(_tool(method), _platform(), runner=lambda _cmd: None)
    assert outcome.status == InstallStatus.MANUAL_REQUIRED
    assert calls == []


def test_declared_bin_dir_is_searchable_before_the_smoke(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_not_installed(monkeypatch)
    dest = tmp_path / "vendor-bin"
    dest.mkdir()

    def runner(_cmd: list[str]) -> None:
        script = dest / "rg"
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        script.chmod(0o755)

    tool = _tool(Method(kind="script", params={"url": "u", "shell": "sh", "bin_dir": str(dest)}))
    outcome = install_tool(tool, _platform(), runner=runner)
    assert outcome.status == InstallStatus.INSTALLED

    def runner_broken(_cmd: list[str]) -> None:
        script = dest / "rg"
        script.write_text("#!/bin/sh\nexit 127\n", encoding="utf-8")
        script.chmod(0o755)

    outcome = install_tool(tool, _platform(), runner=runner_broken)
    assert outcome.status == InstallStatus.FAILED


def test_failed_smoke_restores_path_before_the_next_method(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_not_installed(monkeypatch)
    dir_a = tmp_path / "bin-a"
    dir_b = tmp_path / "bin-b"
    dir_a.mkdir()
    dir_b.mkdir()
    calls = 0

    def runner(_cmd: list[str]) -> None:
        nonlocal calls
        calls += 1
        target = dir_a if calls == 1 else dir_b
        script = target / "rg"
        code = 127 if calls == 1 else 0
        script.write_text(f"#!/bin/sh\nexit {code}\n", encoding="utf-8")
        script.chmod(0o755)

    tool = _tool(
        Method(kind="script", params={"url": "u1", "shell": "sh", "bin_dir": str(dir_a)}),
        Method(kind="script", params={"url": "u2", "shell": "sh", "bin_dir": str(dir_b)}),
    )
    outcome = install_tool(tool, _platform(), runner=runner)
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.method_kind == "script"
    path_entries = os.environ["PATH"].split(os.pathsep)
    assert str(dir_a) not in path_entries
    assert path_entries[0] == str(dir_b)


def test_declared_bin_dir_binary_is_smoked_not_an_earlier_path_hit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)
    _write_cmd(scratch_path_for_manager_smoke, "rg", 0)
    dest = tmp_path / "declared"
    dest.mkdir()

    def runner(_cmd: list[str]) -> None:
        script = dest / "rg"
        script.write_text("#!/bin/sh\nexit 127\n", encoding="utf-8")
        script.chmod(0o755)

    tool = _tool(Method(kind="script", params={"url": "u", "shell": "sh", "bin_dir": str(dest)}))
    outcome = install_tool(tool, _platform(), runner=runner, repair=True)
    assert outcome.status == InstallStatus.FAILED


def test_without_a_bin_dir_the_path_hit_is_smoked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_not_installed(monkeypatch)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _write_cmd(first, "rg", 0)
    _write_cmd(second, "rg", 127)
    monkeypatch.setenv("PATH", f"{first}{os.pathsep}{second}")
    outcome = install_tool(
        _tool(Method(kind="brew", params={"formula": "ripgrep"})),
        _macos_with_brew(),
        runner=lambda _cmd: None,
        repair=True,
    )
    assert outcome.status == InstallStatus.INSTALLED


def test_manager_smoke_uses_the_declared_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        """
[[tool]]
id = "demo"
name = "Demo"
category = "search"
cmd = "demo"
tier = "user"
verified = 2026-10-13
[[tool.method]]
kind = "brew"
formula = "demo"
os = ["macos"]
smoke_argv = ["--custom"]
""",
        encoding="utf-8",
    )
    tool = load_tools(manifest)[0]
    scratch = scratch_path_for_manager_smoke

    def runner(_cmd: list[str]) -> None:
        script = scratch / "demo"
        script.write_text(
            '#!/bin/sh\nif [ "$1" = "--custom" ]; then exit 0; fi\nexit 127\n',
            encoding="utf-8",
        )
        script.chmod(0o755)

    outcome = install_tool(tool, _macos_with_brew(), runner=runner)
    assert outcome.status == InstallStatus.INSTALLED


def test_non_executable_declared_bin_dir_file_is_not_smoked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)
    declared = tmp_path / ".sdkman" / "bin"
    declared.mkdir(parents=True)
    init_script = declared / "sdkman-init.sh"
    init_script.write_text("# sourced\n", encoding="utf-8")
    init_script.chmod(0o644)
    marker = tmp_path / "marker"
    trap = scratch_path_for_manager_smoke / "sdkman-init.sh"
    trap.write_text(f'#!/bin/sh\n: > "{marker}"\nexit 127\n', encoding="utf-8")
    trap.chmod(0o755)

    def runner(_cmd: list[str]) -> None:
        return None

    tool = Tool(
        id="sdkman-init",
        name="SDKMAN init",
        category="shell",
        cmd="sdkman-init.sh",
        methods=(
            Method(
                kind="script",
                params={"url": "u", "shell": "sh", "bin_dir": str(declared)},
            ),
        ),
    )
    outcome = install_tool(tool, _platform(), runner=runner)
    assert outcome.status == InstallStatus.INSTALLED
    assert not marker.exists()


def test_missing_declared_bin_dir_file_falls_back_to_which(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)
    dest = tmp_path / "empty-bin"
    dest.mkdir()
    scratch = scratch_path_for_manager_smoke
    tool = _tool(Method(kind="script", params={"url": "u", "shell": "sh", "bin_dir": str(dest)}))

    def runner_ok(_cmd: list[str]) -> None:
        _write_cmd(scratch, "rg", 0)

    assert install_tool(tool, _platform(), runner=runner_ok).status == InstallStatus.INSTALLED

    def runner_broken(_cmd: list[str]) -> None:
        _write_cmd(scratch, "rg", 127)

    outcome = install_tool(tool, _platform(), runner=runner_broken)
    assert outcome.status == InstallStatus.FAILED


def test_failed_manager_smoke_reports_the_removal_command_and_never_uninstalls(
    monkeypatch: pytest.MonkeyPatch, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)
    recorded: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        recorded.append(cmd)
        _write_cmd(scratch_path_for_manager_smoke, "rg", 127)

    outcome = install_tool(
        _tool(Method(kind="brew", params={"formula": "ripgrep"})),
        _macos_with_brew(),
        runner=runner,
    )
    assert outcome.status == InstallStatus.FAILED
    last = str(outcome.errors[-1])
    assert "brew uninstall ripgrep" in last
    assert not any("uninstall" in arg or "remove" in arg for cmd in recorded for arg in cmd)


def test_leftover_package_is_reported_on_a_later_install(
    monkeypatch: pytest.MonkeyPatch, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)
    scratch = scratch_path_for_manager_smoke
    stage = 0

    def runner(cmd: list[str]) -> None:
        nonlocal stage
        stage += 1
        if stage == 1:
            _write_cmd(scratch, "rg", 127)
        else:
            _write_cmd(scratch, "rg", 0)

    tool = _tool(
        Method(kind="brew", params={"formula": "ripgrep"}),
        Method(kind="cask", params={"cask": "ripgrep"}),
    )
    outcome = install_tool(tool, _macos_with_brew(), runner=runner)
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.postinstall_warning is not None
    assert "brew uninstall ripgrep" in outcome.postinstall_warning


def test_failed_vendor_script_smoke_names_its_own_uninstaller(
    monkeypatch: pytest.MonkeyPatch, scratch_path_for_manager_smoke: Path
) -> None:
    _patch_not_installed(monkeypatch)

    def runner(_cmd: list[str]) -> None:
        _write_cmd(scratch_path_for_manager_smoke, "rg", 127)

    outcome = install_tool(
        _tool(Method(kind="script", params={"url": "u", "shell": "sh"})),
        _platform(),
        runner=runner,
    )
    assert outcome.status == InstallStatus.FAILED
    last = str(outcome.errors[-1])
    assert "that installer's own uninstaller" in last


# --- Plan 19-09: install receipts ----------------------------------------------

_RECEIPT_MEMBER_SCRIPT = b"#!/bin/sh\nexit 0\n"


def _pin_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import installer.download as download_mod

    workdir = tmp_path / "dl"
    workdir.mkdir(exist_ok=True)

    def fake_mkdtemp(prefix: str) -> str:
        workdir.mkdir(exist_ok=True)
        return str(workdir)

    monkeypatch.setattr(download_mod.tempfile, "mkdtemp", fake_mkdtemp)
    return workdir


def _raw_yq_method(bin_dir: Path) -> Method:
    return Method(
        kind="github_release",
        params={
            "repo": "mikefarah/yq",
            "asset": "yq_linux_{arch.deb}",
            "member": "yq_linux_amd64",
            "bin_name": "yq",
            "raw": True,
            "bin_dir": str(bin_dir),
        },
    )


def _install_raw_yq(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes = _RECEIPT_MEMBER_SCRIPT,
    *,
    postinstall: str | None = None,
    repair: bool = False,
) -> tuple[engine.InstallOutcome, Path]:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _pin_workdir(tmp_path, monkeypatch)
    _calls, runner = fixture_runner(workdir, {"yq_linux_amd64": payload})
    bin_dir = tmp_path / "bin"
    tool = _tool(_raw_yq_method(bin_dir), postinstall=postinstall, tool_id="yq")
    outcome = install_tool(
        tool, _platform(), runner=runner, resolve_tag=lambda _repo: "4.44.1", repair=repair
    )
    return outcome, bin_dir / "yq"


def test_install_writes_one_receipt_before_postinstall(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_not_installed(monkeypatch)
    seen: list[receipts.Receipt | None] = []

    def observing_postinstall(_name: str, _method: Method, _runner: object, _tools: object) -> None:
        seen.append(receipts.read("yq"))

    monkeypatch.setattr(engine, "run_postinstall", observing_postinstall)
    outcome, placed = _install_raw_yq(tmp_path, monkeypatch, postinstall="codegraph-mcp-register")
    assert outcome.status == InstallStatus.INSTALLED
    written = receipts.read("yq")
    assert written is not None
    assert written.artifacts == (receipts.fingerprint(placed, "file"),)
    assert written.smoke == "ok"
    assert seen == [written]
    assert [p.name for p in receipts.receipts_dir().iterdir()] == ["yq.json"]


def test_failed_install_writes_no_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_not_installed(monkeypatch)

    def failing(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    outcome = install_tool(
        _tool(Method(kind="brew", params={"formula": "ripgrep"})),
        _macos_with_brew(),
        runner=failing,
    )
    assert outcome.status == InstallStatus.FAILED
    assert receipts.read("rg") is None


def test_archive_install_writes_a_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_not_installed(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = _pin_workdir(tmp_path, monkeypatch)
    opt = tmp_path / ".local" / "opt" / "rg"
    asset = "rg-14.1.0-x86_64.tar.gz"
    _calls, runner = fixture_runner(workdir, {asset: b"archive"}, member=opt / "rg-x" / "rg")
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "rg-{ver}-{arch.machine}.tar.gz",
            "member": "rg-x/rg",
        },
    )
    outcome = install_tool(
        _tool(method), _platform(), runner=runner, resolve_tag=lambda _repo: "14.1.0"
    )
    assert outcome.status == InstallStatus.INSTALLED
    link = tmp_path / ".local" / "bin" / "rg"
    written = receipts.read("rg")
    assert written is not None
    assert written.artifacts == (
        receipts.fingerprint(opt, "dir"),
        receipts.fingerprint(link, "link"),
    )
    assert written.artifacts[1].target == os.readlink(link)
