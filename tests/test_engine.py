from pathlib import Path

import pytest

import installer.engine as engine
from installer.engine import install_tool
from installer.model import Method, Tool
from installer.platform import Platform
from installer.run import CommandError
from installer.versions import VersionError


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def _tool(*methods: Method) -> Tool:
    return Tool(id="rg", name="ripgrep", category="search", cmd="rg", methods=methods)


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
