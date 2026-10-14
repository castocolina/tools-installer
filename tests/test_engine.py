import os
from pathlib import Path

import pytest

import installer.engine as engine
from installer import executors
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.engine import install_tool
from installer.enums import InstallStatus
from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.run import CommandError
from installer.versions import VersionError
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
    monkeypatch.setenv("PATH", "/usr/bin")
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
    bin_dir = tmp_path / "bin"
    member = tmp_path / ".local" / "opt" / "rg" / "rg"
    calls, runner = fixture_runner(None, {}, member=member)
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
    assert calls[0][0] == "sh" and "rg-14.1.0-x86_64.tar.gz" in calls[0][2]
    link = bin_dir / "rg"
    assert link.is_symlink()
    assert os.readlink(link) == str(member)
    shelled = {"l" + "n", "ch" + "mod"}
    assert not any(cmd and cmd[0] in shelled for cmd in calls)


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
        if cmd and cmd[0] == "sh" and " tar " in cmd[-1] and member.exists():
            member.unlink()
            member.mkdir()

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
    monkeypatch.setenv("PATH", "/usr/bin")
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
