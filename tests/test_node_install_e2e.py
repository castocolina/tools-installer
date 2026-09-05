from pathlib import Path

import pytest

import installer.engine as engine
import installer.executors as executors
from installer.engine import install_tool
from installer.model import Tool, load_tools
from installer.platform import Platform

_REGISTRY = "installer/registry.toml"


def _platform() -> Platform:
    return Platform(os="debian", arch="amd64", immutable=False, has_brew=False)


def _by_id(tool_id: str) -> Tool:
    return next(t for t in load_tools(_REGISTRY) if t.id == tool_id)


def test_mmdc_is_a_node_tool_requiring_pnpm() -> None:
    mmdc = _by_id("mmdc")
    assert mmdc.requires == ("pnpm", "puppeteer")
    node_methods = [m for m in mmdc.methods if m.kind == "node"]
    assert node_methods and node_methods[0].params["npm_pkg"] == "@mermaid-js/mermaid-cli"


def _stub_version_probe_and_browser_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = tmp_path / "puppeteer-cache"
    browser = (
        cache
        / "chrome-headless-shell"
        / "linux-152.0.7977.75"
        / "chrome-headless-shell-linux64"
        / "chrome-headless-shell"
    )
    browser.parent.mkdir(parents=True)
    browser.write_text("x")
    browser.chmod(0o755)
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(cache))

    def fake_probe(argv: list[str]) -> str:
        program = argv[0]
        if program.endswith("pnpm"):
            return "12.3.4"
        if program == "node" or program.endswith("/node"):
            return "v24.20.0"
        return "152.0.7977.75"

    monkeypatch.setattr(executors, "probe_version", fake_probe)


def test_installing_mmdc_runs_pnpm_add_global_no_bare_npm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _stub_version_probe_and_browser_cache(monkeypatch, tmp_path)
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    pnpm = real_dir / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)
    monkeypatch.setenv("PATH", str(real_dir))
    calls: list[list[str]] = []

    def not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", not_installed)
    outcome = install_tool(_by_id("mmdc"), _platform(), runner=calls.append)
    assert outcome.status == "installed"
    grouped = "@mermaid-js/mermaid-cli,puppeteer@^25"
    matching = [
        call for call in calls if call[-4:] == ["add", "-g", "--allow-build=puppeteer", grouped]
    ]
    assert matching
    assert len(calls) == 1
    argv0 = matching[0][0]
    assert argv0 == str(pnpm)
    assert Path(argv0).is_absolute()
    assert argv0.endswith("pnpm")
    assert not any(call[:1] == ["npm"] for call in calls)
    assert not any(call[:1] == ["pnpm"] for call in calls)
