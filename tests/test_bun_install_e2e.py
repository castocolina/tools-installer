"""The shipped npm-package CLIs install through bun first, with pnpm as the fallback.

Every test loads the real `installer/registry.toml` entries and drives `install_tool` with a
recording runner, fake `bun`/`pnpm` on a scratch PATH and a stubbed browser launch: nothing
starts a package manager, node or a browser.
"""

import json
import os
from pathlib import Path

import pytest

import installer.engine as engine
import installer.executors as executors
from installer.engine import install_tool
from installer.enums import InstallStatus
from installer.model import Method, Tool, load_tools
from installer.ownership import (
    ManagerInventory,
    ManagerOwnership,
    read_inventory,
    resolve_ownership,
)
from installer.platform import Platform
from installer.run import CommandError
from installer.update import UpdateTarget, perform_update
from tests.launch_doubles import stub_launch

_REGISTRY = "installer/registry.toml"
_PI = "@earendil-works/pi-coding-agent"


def _platform() -> Platform:
    return Platform(os="debian", arch="amd64", immutable=False, has_brew=False)


def _by_id(tool_id: str) -> Tool:
    return next(t for t in load_tools(_REGISTRY) if t.id == tool_id)


def _fake(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _scratch_host(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    managers: tuple[str, ...],
    node: str = "v22.23.1",
) -> dict[str, Path]:
    """A scratch HOME and a PATH holding only the named fake managers; `node` is what it probes."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in ("BUN_INSTALL", "BUN_INSTALL_BIN", "BUN_INSTALL_GLOBAL_DIR"):
        monkeypatch.delenv(name, raising=False)
    real = tmp_path / "real"
    real.mkdir()
    fakes = {name: _fake(real, name) for name in managers}
    monkeypatch.setenv("PATH", str(real))

    def probe(argv: list[str]) -> str:
        return "12.3.4" if argv[0].endswith("pnpm") else node

    monkeypatch.setattr(executors, "probe_version", probe)
    monkeypatch.setattr(executors, "launch_puppeteer", stub_launch(None))
    return fakes


def test_catalog_install_of_mmdc_runs_bun_add_with_the_pinned_peer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fakes = _scratch_host(monkeypatch, tmp_path, managers=("bun",))
    calls: list[list[str]] = []
    outcome = install_tool(
        _by_id("mmdc"), _platform(), runner=calls.append, present=lambda _tool: False
    )
    assert outcome.status == "installed"
    assert outcome.method_kind == "bun"
    assert calls == [[str(fakes["bun"]), "add", "-g", "@mermaid-js/mermaid-cli", "puppeteer@^25"]]


def test_shipped_puppeteer_and_pi_install_through_bun(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fakes = _scratch_host(monkeypatch, tmp_path, managers=("bun",), node="v22.19.0")
    for tool_id, spec in (("puppeteer", "puppeteer@^25"), ("pi", _PI)):
        calls: list[list[str]] = []
        outcome = install_tool(
            _by_id(tool_id), _platform(), runner=calls.append, present=lambda _tool: False
        )
        assert (outcome.status, outcome.method_kind) == ("installed", "bun"), tool_id
        assert calls == [[str(fakes["bun"]), "add", "-g", spec]], tool_id


def test_shipped_mmdc_falls_back_to_pnpm_without_bun(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-10: bun resolves first and the node method stays reachable when bun is absent.

    `test_installing_mmdc_runs_pnpm_add_global_no_bare_npm` keeps passing for the same reason.
    """
    fakes = _scratch_host(monkeypatch, tmp_path, managers=("pnpm",))
    calls: list[list[str]] = []
    outcome = install_tool(
        _by_id("mmdc"), _platform(), runner=calls.append, present=lambda _tool: False
    )
    assert (outcome.status, outcome.method_kind) == ("installed", "node")
    grouped = "@mermaid-js/mermaid-cli,puppeteer@^25"
    assert calls == [[str(fakes["pnpm"]), "add", "-g", "--allow-build=puppeteer", grouped]]


def _query_fails(argv: list[str], **_kwargs: object) -> str:
    raise CommandError(argv, 1, detail="not installed")


def test_shipped_bun_owned_pi_reads_owner_and_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _scratch_host(monkeypatch, tmp_path, managers=())
    home = tmp_path / "home"
    global_dir = home / ".bun" / "install" / "global"
    package = global_dir / "node_modules" / _PI
    (package / "dist").mkdir(parents=True)
    (global_dir / "package.json").write_text(
        json.dumps({"dependencies": {_PI: "1.5.2"}}), encoding="utf-8"
    )
    (package / "package.json").write_text(json.dumps({"version": "1.5.2"}), encoding="utf-8")
    cli = package / "dist" / "cli.js"
    cli.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    cli.chmod(0o755)
    link = home / ".bun" / "bin" / "pi"
    link.parent.mkdir(parents=True)
    link.symlink_to(cli)

    inventory = read_inventory(has_brew=False, query=_query_fails, pnpm_packages=lambda: ())
    result = resolve_ownership(
        _by_id("pi"),
        platform=_platform(),
        inventory=inventory,
        artifacts=(),
        which=lambda _cmd: str(link),
        managed_bin_dir=home / ".local" / "bin",
    )
    assert (result.owner, result.current_version, result.package) == ("bun", "1.5.2", _PI)


# --- PRIO-05: a copy another manager already installed stays with that manager ---------------

_MMDC = "@mermaid-js/mermaid-cli"
_OWNERS = ("pnpm", "volta", "brew")


def _executable(path: Path, text: str = "#!/bin/sh\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _brew_copy(prefix: Path) -> Path:
    """`<prefix>/bin/mmdc` linked into `<prefix>/Cellar/mermaid-cli/12.2.0/bin`."""
    binary = _executable(prefix / "Cellar" / "mermaid-cli" / "12.2.0" / "bin" / "mmdc")
    link = prefix / "bin" / "mmdc"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(binary)
    return link


class _OwnedMmdc:
    """A scratch machine holding the shipped mmdc as `owner`'s copy, with a fake bun on PATH."""

    def __init__(
        self, owner: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, bun_globals: bool
    ) -> None:
        self.tmp_path = tmp_path
        self.tool = _by_id("mmdc")
        self.platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
        self.bun = _scratch_host(monkeypatch, tmp_path, managers=("bun",))["bun"]
        self.brew_prefix = tmp_path / "brew"
        self.pnpm: Path | None = None
        self.pnpm_globals: frozenset[str] = frozenset()
        self.brew_formulae: dict[str, str] = {}
        path_dirs = [str(self.bun.parent)]
        if owner == "pnpm":
            pnpm_home = tmp_path / "pnpm"
            monkeypatch.setenv("PNPM_HOME", str(pnpm_home))
            self.pnpm = _executable(pnpm_home / "bin" / "pnpm")
            self.command = _executable(pnpm_home / "bin" / "mmdc")
            self.pnpm_globals = frozenset({_MMDC})
            path_dirs.insert(0, str(pnpm_home / "bin"))
        elif owner == "volta":
            volta_bin = tmp_path / "volta" / "bin"
            monkeypatch.setenv("VOLTA_HOME", str(tmp_path / "volta"))
            shim = _executable(volta_bin / "volta-shim")
            self.command = volta_bin / "mmdc"
            self.command.symlink_to(shim)
            path_dirs.insert(0, str(volta_bin))
        else:
            self.command = _brew_copy(self.brew_prefix)
            self.brew_formulae = {"mermaid-cli": "12.2.0"}
            path_dirs.insert(0, str(self.command.parent))
        monkeypatch.setenv("PATH", os.pathsep.join(path_dirs))
        # `{}` is a readable, empty bun tree; None is a tree that could not be read.
        self.bun_globals: dict[str, str | None] | None = {} if bun_globals else None

    def ownership(self) -> ManagerOwnership:
        inventory = ManagerInventory(
            brew_formulae=self.brew_formulae,
            brew_casks={},
            pnpm_globals=self.pnpm_globals,
            uv_tools={},
            brew_prefix=self.brew_prefix,
            bun_globals=self.bun_globals,
        )
        return resolve_ownership(
            self.tool,
            platform=self.platform,
            inventory=inventory,
            artifacts=(),
            which=lambda _cmd: str(self.command),
            managed_bin_dir=self.tmp_path / "home" / ".local" / "bin",
        )


def _ran_bun(calls: list[list[str]]) -> bool:
    return any(Path(argv[0]).name == "bun" for argv in calls)


@pytest.mark.parametrize("owner", _OWNERS)
def test_owned_mmdc_is_already_installed_without_a_bun_call(
    owner: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    machine = _OwnedMmdc(owner, tmp_path, monkeypatch, bun_globals=True)
    calls: list[list[str]] = []
    outcome = install_tool(machine.tool, machine.platform, runner=calls.append)
    assert outcome.status == InstallStatus.ALREADY_INSTALLED
    assert calls == []
    assert machine.ownership().owner == owner


@pytest.mark.parametrize("owner", _OWNERS)
def test_owned_mmdc_updates_through_its_own_manager(
    owner: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    machine = _OwnedMmdc(owner, tmp_path, monkeypatch, bun_globals=True)
    calls: list[list[str]] = []
    outcome = perform_update(
        UpdateTarget(machine.tool, machine.ownership()),
        platform=machine.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1.0.0",
    )
    assert not _ran_bun(calls)
    assert ["add", "-g", _MMDC, "puppeteer@^25"] not in [argv[1:] for argv in calls]
    if owner == "pnpm":
        grouped = f"{_MMDC},puppeteer@^25"
        assert outcome.status == "updated"
        assert calls == [[str(machine.pnpm), "add", "-g", "--allow-build=puppeteer", grouped]]
    elif owner == "volta":
        assert outcome.status == "unsupported"
        assert outcome.detail == f"managed by Volta — update it with `volta install {_MMDC}`"
        assert calls == []
    else:
        assert outcome.status == "updated"
        assert calls == [["brew", "upgrade", "mermaid-cli"]]


def test_already_installed_short_circuits_before_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    machine = _OwnedMmdc("pnpm", tmp_path, monkeypatch, bun_globals=True)

    def refuse(_tool: Tool, _platform: Platform) -> list[Method]:
        raise AssertionError("method resolution ran for a tool that is already present")

    monkeypatch.setattr(engine, "resolve_methods", refuse)
    calls: list[list[str]] = []
    statuses = [
        install_tool(machine.tool, machine.platform, runner=calls.append).status for _ in range(3)
    ]
    assert statuses == [InstallStatus.ALREADY_INSTALLED] * 3
    assert calls == []


@pytest.mark.parametrize("bun_globals", [True, False])
def test_volta_shim_with_brew_copy_keeps_active_and_shadowed_reporting(
    bun_globals: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    machine = _OwnedMmdc("volta", tmp_path, monkeypatch, bun_globals=bun_globals)
    _brew_copy(machine.brew_prefix)
    machine.brew_formulae = {"mermaid-cli": "12.2.0"}
    result = machine.ownership()
    assert result.owner == "volta"
    assert result.shadowed is True
    assert result.active_path is not None and result.active_path.name == "volta-shim"
    assert any(candidate.owner == "brew" for candidate in result.candidates)
    calls: list[list[str]] = []
    outcome = install_tool(machine.tool, machine.platform, runner=calls.append)
    assert (outcome.status, calls) == (InstallStatus.ALREADY_INSTALLED, [])


def test_shipped_mmdc_names_a_pnpm_owned_puppeteer_peer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-20: a puppeteer another manager owns is left alone; bun installs its own and says so."""
    bun = _scratch_host(monkeypatch, tmp_path, managers=("bun",))["bun"]
    pnpm_bin = tmp_path / "pnpm" / "bin"
    peer = _executable(pnpm_bin / "puppeteer")
    monkeypatch.setenv("PATH", os.pathsep.join([str(bun.parent), str(pnpm_bin)]))
    calls: list[list[str]] = []
    outcome = install_tool(
        _by_id("mmdc"), _platform(), runner=calls.append, present=lambda _tool: False
    )
    assert outcome.status == "installed"
    assert calls == [[str(bun), "add", "-g", _MMDC, "puppeteer@^25"]]
    warning = outcome.postinstall_warning or ""
    assert "puppeteer" in warning
    assert str(peer) in warning
