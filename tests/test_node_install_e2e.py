from pathlib import Path

import pytest

import installer.engine as engine
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
    assert mmdc.requires == ("pnpm",)
    node_methods = [m for m in mmdc.methods if m.kind == "node"]
    assert node_methods and node_methods[0].params["npm_pkg"] == "@mermaid-js/mermaid-cli"


def test_installing_mmdc_runs_pnpm_add_global_no_bare_npm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    calls: list[list[str]] = []

    def not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", not_installed)
    outcome = install_tool(_by_id("mmdc"), _platform(), runner=calls.append)
    assert outcome.status == "installed"
    assert ["pnpm", "add", "-g", "@mermaid-js/mermaid-cli"] in calls
    assert not any(call[:1] == ["npm"] for call in calls)
