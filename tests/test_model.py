from pathlib import Path

import pytest

from installer.enums import Audience, Priority
from installer.model import Method, Tool, load_categories, load_tools


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "registry.toml"
    p.write_text(content)
    return p


def test_tool_requires_defaults_empty_and_parses(tmp_path: Path) -> None:
    """`requires` is a no-op dependency seam for the deps PRD: it defaults to an
    empty tuple and parses a declared list into a tuple of ids."""
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "mmdc"
category = "diagram"
requires = ["pnpm", "node"]
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"

[[tool]]
id = "rg"
category = "search"
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    tools = {tool.id: tool for tool in load_tools(manifest)}
    assert tools["mmdc"].requires == ("pnpm", "node")
    assert tools["rg"].requires == ()
    assert all(isinstance(tool.requires, tuple) for tool in tools.values())


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
    assert tool.priority is Priority.P0
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
    assert tool.audience is Audience.BOTH


def test_tool_without_methods_raises(tmp_path: Path):
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "broken"
name = "broken"
category = "search"
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
category = "search"
[[tool.method]]
kind = "snap"
package = "weird"
""",
    )
    with pytest.raises(ValueError, match="unknown method kind"):
        load_tools(manifest)


def test_load_tools_reads_method_os_targets(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "search"\n'
        "[[tool.method]]\n"
        'kind = "script"\n'
        'os = ["macos"]\n'
        'url = "https://example.test/i.sh"\n'
    )
    method = load_tools(manifest)[0].methods[0]
    assert method.os == ("macos",)
    assert "os" not in method.params
    assert method.params["url"] == "https://example.test/i.sh"


def test_load_tools_rejects_os_as_a_string(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "search"\n'
        "[[tool.method]]\n"
        'kind = "script"\n'
        'os = "macos"\n'  # must be a list, not a string
        'url = "https://example.test/i.sh"\n'
    )
    with pytest.raises(ValueError, match="must be a list"):
        load_tools(manifest)


def test_load_tools_reads_method_arch_targets(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "search"\n'
        "[[tool.method]]\n"
        'kind = "script"\n'
        'os = ["macos"]\n'
        'arch = ["arm64"]\n'
        'url = "https://example.test/i.sh"\n'
    )
    method = load_tools(manifest)[0].methods[0]
    assert method.os == ("macos",)
    assert method.arch == ("arm64",)
    assert "arch" not in method.params
    assert method.params["url"] == "https://example.test/i.sh"


def test_load_tools_rejects_arch_as_a_string(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "search"\n'
        "[[tool.method]]\n"
        'kind = "script"\n'
        'arch = "arm64"\n'  # must be a list, not a string
        'url = "https://example.test/i.sh"\n'
    )
    with pytest.raises(ValueError, match="'arch' must be a list"):
        load_tools(manifest)


def test_load_tools_rejects_requires_as_a_string(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "search"\n'
        'requires = "pnpm"\n'  # must be a list, not a string
        "[[tool.method]]\n"
        'kind = "script"\n'
        'url = "https://example.test/i.sh"\n'
    )
    with pytest.raises(ValueError, match="'requires' must be a list"):
        load_tools(manifest)


def test_load_tools_rejects_unknown_category(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "misc"
[[tool.method]]
kind = "brew"
formula = "demo"
""",
    )
    with pytest.raises(ValueError, match="unknown category"):
        load_tools(manifest)


def test_load_tools_rejects_unknown_priority(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
priority = "P99"
[[tool.method]]
kind = "brew"
formula = "demo"
""",
    )
    with pytest.raises(ValueError, match="unknown priority"):
        load_tools(manifest)


def test_load_tools_rejects_unknown_audience(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
audience = "you"
[[tool.method]]
kind = "brew"
formula = "demo"
""",
    )
    with pytest.raises(ValueError, match="unknown audience"):
        load_tools(manifest)


def test_load_categories_reads_ordered_blurbs(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
id = "search"
desc = "Find files and code at speed"
[[category]]
id = "data"
desc = "Query and transform JSON, YAML and CSV"
[[tool]]
id = "rg"
category = "search"
[[tool.method]]
kind = "brew"
formula = "ripgrep"
""",
    )
    assert load_categories(manifest) == {
        "search": "Find files and code at speed",
        "data": "Query and transform JSON, YAML and CSV",
    }


def test_load_categories_empty_when_no_sections(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "rg"
category = "search"
[[tool.method]]
kind = "brew"
formula = "ripgrep"
""",
    )
    assert load_categories(manifest) == {}


def test_load_categories_rejects_duplicate_id(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
id = "search"
desc = "one"
[[category]]
id = "search"
desc = "two"
""",
    )
    with pytest.raises(ValueError, match="duplicate category id 'search'"):
        load_categories(manifest)


def test_load_categories_rejects_missing_id(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
desc = "no id here"
""",
    )
    with pytest.raises(ValueError, match="section #0 is missing a non-empty 'id'"):
        load_categories(manifest)


def test_load_categories_rejects_empty_id(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
id = ""
desc = "test"
""",
    )
    with pytest.raises(ValueError, match="section #0 is missing a non-empty 'id'"):
        load_categories(manifest)


def test_load_categories_rejects_empty_desc(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
id = "search"
desc = ""
""",
    )
    with pytest.raises(ValueError, match="category 'search' is missing a non-empty 'desc'"):
        load_categories(manifest)


def test_load_categories_rejects_unknown_category_id(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
id = "misc"
desc = "Miscellaneous tools"
""",
    )
    with pytest.raises(ValueError, match="unknown category id"):
        load_categories(manifest)


def test_node_kind_parses_with_npm_pkg(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "mmdc"
category = "diagram"
cmd = "mmdc"
requires = ["pnpm"]
[[tool.method]]
kind = "node"
npm_pkg = "@mermaid-js/mermaid-cli"
""",
    )
    tools = load_tools(manifest)
    method = tools[0].methods[0]
    assert method.kind == "node"
    assert method.params["npm_pkg"] == "@mermaid-js/mermaid-cli"


def test_node_method_without_npm_pkg_is_a_config_error(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "broken"
category = "diagram"
[[tool.method]]
kind = "node"
""",
    )
    with pytest.raises(ValueError, match="node.*npm_pkg"):
        load_tools(manifest)


def test_sdkman_kind_parses_with_candidate(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "java"
category = "runtime"
cmd = "java"
requires = ["sdkman"]
[[tool.method]]
kind = "sdkman"
candidate = "java"
bin_dir = "~/.sdkman/candidates/java/current/bin"
""",
    )
    tools = load_tools(manifest)
    method = tools[0].methods[0]
    assert method.kind == "sdkman"
    assert method.params["candidate"] == "java"


def test_sdkman_method_without_candidate_is_a_config_error(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "broken"
category = "runtime"
[[tool.method]]
kind = "sdkman"
""",
    )
    with pytest.raises(ValueError, match="sdkman.*candidate"):
        load_tools(manifest)
