"""The shipped npm-package CLIs install through bun first, with pnpm as the fallback.

Every test loads the real `installer/registry.toml` entries and drives `install_tool` with a
recording runner, fake `bun`/`pnpm` on a scratch PATH and a stubbed browser launch: nothing
starts a package manager, node or a browser.
"""

import json
from pathlib import Path

import pytest

import installer.executors as executors
from installer.engine import install_tool
from installer.model import Tool, load_tools
from installer.ownership import read_inventory, resolve_ownership
from installer.platform import Platform
from installer.run import CommandError
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
