import os
from pathlib import Path

import pytest

import installer.engine as engine
from installer import executors
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.engine import install_tool
from installer.enums import InstallStatus
from installer.model import Method, Tool
from installer.platform import Platform
from installer.run import CommandError
from installer.versions import VersionError


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def _tool(*methods: Method, postinstall: str | None = None) -> Tool:
    return Tool(
        id="rg",
        name="ripgrep",
        category="search",
        cmd="rg",
        methods=methods,
        postinstall=postinstall,
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
    calls: list[list[str]] = []
    bin_dir = tmp_path / "bin"
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

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    outcome = install_tool(
        _tool(method),
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=runner,
        resolve_tag=resolve_tag,
    )
    opt = tmp_path / ".local" / "opt" / "rg"
    assert outcome.status == "installed"
    assert outcome.method_kind == "github_release"
    assert calls[0][0] == "sh" and "rg-14.1.0-x86_64.tar.gz" in calls[0][2]
    assert calls[1] == ["chmod", "+x", str(opt / "rg")]
    assert calls[2] == ["ln", "-sf", str(opt / "rg"), str(bin_dir / "rg")]


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
