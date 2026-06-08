from pathlib import Path

import pytest

from installer.model import Method, Tool, load_tools


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "registry.toml"
    p.write_text(content)
    return p


def test_load_single_tool_with_methods(tmp_path: Path):
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "uv"
name = "uv"
category = "pkg-mgr"
cmd = "uv"
priority = "P0"
desc = "Python package manager"
[[tool.method]]
kind = "script"
url = "https://astral.sh/uv/install.sh"
shell = "sh"
[[tool.method]]
kind = "brew"
formula = "uv"
""",
    )
    tools = load_tools(manifest)
    assert len(tools) == 1
    tool = tools[0]
    assert isinstance(tool, Tool)
    assert tool.id == "uv"
    assert tool.priority == "P0"
    assert [m.kind for m in tool.methods] == ["script", "brew"]
    assert isinstance(tool.methods[0], Method)
    assert tool.methods[0].params["url"] == "https://astral.sh/uv/install.sh"


def test_cmd_defaults_to_id(tmp_path: Path):
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "jq"
name = "jq"
category = "data"
[[tool.method]]
kind = "brew"
formula = "jq"
""",
    )
    tool = load_tools(manifest)[0]
    assert tool.cmd == "jq"
    assert tool.priority == "P3"  # default
    assert tool.audience == "both"  # default


def test_tool_without_methods_raises(tmp_path: Path):
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "broken"
name = "broken"
category = "x"
""",
    )
    with pytest.raises(ValueError, match="no install methods"):
        load_tools(manifest)


def test_unknown_method_kind_raises(tmp_path: Path):
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "weird"
name = "weird"
category = "x"
[[tool.method]]
kind = "snap"
package = "weird"
""",
    )
    with pytest.raises(ValueError, match="unknown method kind"):
        load_tools(manifest)
