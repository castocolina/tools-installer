from pathlib import Path

import pytest

from installer.enums import Audience, Priority, Tier
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
tier = "user"
requires = ["pnpm", "node"]
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"

[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    tools = {tool.id: tool for tool in load_tools(manifest)}
    assert tools["mmdc"].requires == ("pnpm", "node")
    assert tools["rg"].requires == ()
    assert all(isinstance(tool.requires, tuple) for tool in tools.values())


def test_tool_recommends_defaults_empty_and_parses(tmp_path: Path) -> None:
    """`recommends` is a soft-dependency seam: it defaults to an empty tuple
    and parses a declared list into a tuple of ids."""
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "claude"
category = "ai"
tier = "ai"
recommends = ["rg", "fd"]
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"

[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    tools = {tool.id: tool for tool in load_tools(manifest)}
    assert tools["claude"].recommends == ("rg", "fd")
    assert tools["rg"].recommends == ()
    assert all(isinstance(tool.recommends, tuple) for tool in tools.values())


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
tier = "user"
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
tier = "user"
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
tier = "user"
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
        'tier = "user"\n'
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
        'tier = "user"\n'
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
        'tier = "user"\n'
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
        'tier = "user"\n'
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
        'tier = "user"\n'
        'requires = "pnpm"\n'  # must be a list, not a string
        "[[tool.method]]\n"
        'kind = "script"\n'
        'url = "https://example.test/i.sh"\n'
    )
    with pytest.raises(ValueError, match="'requires' must be a list"):
        load_tools(manifest)


def test_load_tools_rejects_recommends_as_a_string(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "search"\n'
        'tier = "user"\n'
        'recommends = "rg"\n'  # must be a list, not a string
        "[[tool.method]]\n"
        'kind = "script"\n'
        'url = "https://example.test/i.sh"\n'
    )
    with pytest.raises(ValueError, match="'recommends' must be a list"):
        load_tools(manifest)


def test_load_tools_rejects_a_non_string_recommends_element(tmp_path: Path) -> None:
    """tomllib returns `Any`, so a list of non-ids would otherwise be stored
    behind the declared `tuple[str, ...]` and only fail later, as a TypeError
    inside the TUI's detail bar on cursor movement."""
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "search"\n'
        'tier = "user"\n'
        "recommends = [1, 2]\n"  # ids, not integers
        "[[tool.method]]\n"
        'kind = "script"\n'
        'url = "https://example.test/i.sh"\n'
    )
    with pytest.raises(ValueError, match="'recommends' must be a list of tool ids"):
        load_tools(manifest)


def test_load_tools_rejects_a_non_string_requires_element(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        "[[tool]]\n"
        'id = "demo"\n'
        'category = "search"\n'
        'tier = "user"\n'
        'requires = [["pnpm"]]\n'  # a nested list, not an id
        "[[tool.method]]\n"
        'kind = "script"\n'
        'url = "https://example.test/i.sh"\n'
    )
    with pytest.raises(ValueError, match="'requires' must be a list of tool ids"):
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
tier = "user"
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
tier = "user"
[[tool.method]]
kind = "brew"
formula = "demo"
""",
    )
    with pytest.raises(ValueError, match="unknown audience"):
        load_tools(manifest)


def test_load_tools_rejects_missing_tier(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
[[tool.method]]
kind = "brew"
formula = "demo"
""",
    )
    with pytest.raises(ValueError, match="tier"):
        load_tools(manifest)


def test_load_tools_rejects_unknown_tier(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "cloud"
[[tool.method]]
kind = "brew"
formula = "demo"
""",
    )
    with pytest.raises(ValueError, match="unknown tier"):
        load_tools(manifest)


def test_tier_parses_to_enum_member(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "uv"
category = "pkg-mgr"
tier = "system"
[[tool.method]]
kind = "brew"
formula = "uv"
""",
    )
    tool = load_tools(manifest)[0]
    assert tool.tier is Tier.SYSTEM
    assert tool.tier == "system"


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
tier = "user"
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
tier = "user"
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
tier = "user"
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
tier = "user"
[[tool.method]]
kind = "sdkman"
""",
    )
    with pytest.raises(ValueError, match="sdkman.*candidate"):
        load_tools(manifest)


def _node_registry(tmp_path: Path, method_extra: str, npm_pkg: str = "puppeteer") -> Path:
    return _write(
        tmp_path,
        f"""
[[tool]]
id = "demo"
category = "diagram"
cmd = "demo"
tier = "user"
[[tool.method]]
kind = "node"
npm_pkg = "{npm_pkg}"
{method_extra}
""",
    )


def test_node_method_parses_co_install(tmp_path: Path) -> None:
    tools = load_tools(_node_registry(tmp_path, 'co_install = ["puppeteer"]', npm_pkg="cli"))
    assert tools[0].methods[0].params["co_install"] == ["puppeteer"]


def test_node_method_parses_allow_build_in_group(tmp_path: Path) -> None:
    tools = load_tools(_node_registry(tmp_path, 'allow_build = ["puppeteer"]'))
    assert tools[0].methods[0].params["allow_build"] == ["puppeteer"]


def test_node_method_parses_versions_table(tmp_path: Path) -> None:
    tools = load_tools(_node_registry(tmp_path, 'versions = {puppeteer = "^25"}'))
    assert tools[0].methods[0].params["versions"] == {"puppeteer": "^25"}


def test_node_method_parses_min_node(tmp_path: Path) -> None:
    tools = load_tools(_node_registry(tmp_path, 'min_node = "22.12.0"'))
    assert tools[0].methods[0].params["min_node"] == "22.12.0"


def test_node_method_parses_smoke(tmp_path: Path) -> None:
    tools = load_tools(_node_registry(tmp_path, 'smoke = "puppeteer-browser"'))
    assert tools[0].methods[0].params["smoke"] == "puppeteer-browser"


def test_node_method_without_new_params_omits_them(tmp_path: Path) -> None:
    tools = load_tools(_node_registry(tmp_path, ""))
    params = tools[0].methods[0].params
    assert "co_install" not in params
    assert "allow_build" not in params
    assert "versions" not in params
    assert "min_node" not in params
    assert "smoke" not in params


def test_node_method_rejects_co_install_bare_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="co_install"):
        load_tools(_node_registry(tmp_path, 'co_install = "puppeteer"'))


def test_node_method_rejects_co_install_non_string_element(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="co_install"):
        load_tools(_node_registry(tmp_path, "co_install = [1]"))


def test_node_method_rejects_co_install_empty_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="co_install"):
        load_tools(_node_registry(tmp_path, 'co_install = [""]'))


def test_node_method_rejects_co_install_comma_in_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="co_install"):
        load_tools(_node_registry(tmp_path, 'co_install = ["a,b"]'))


def test_node_method_rejects_comma_in_npm_pkg(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="npm_pkg"):
        load_tools(_node_registry(tmp_path, "", npm_pkg="a,b"))


def test_node_method_rejects_allow_build_bare_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow_build"):
        load_tools(_node_registry(tmp_path, 'allow_build = "puppeteer"'))


def test_node_method_rejects_allow_build_non_string_element(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow_build"):
        load_tools(_node_registry(tmp_path, "allow_build = [1]"))


def test_node_method_rejects_allow_build_empty_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow_build"):
        load_tools(_node_registry(tmp_path, 'allow_build = [""]'))


def test_node_method_rejects_allow_build_comma_in_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow_build"):
        load_tools(_node_registry(tmp_path, 'allow_build = ["a,b"]'))


def test_node_method_rejects_allow_build_outside_install_group(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow_build.*sharp"):
        load_tools(_node_registry(tmp_path, 'allow_build = ["sharp"]'))


def test_node_method_rejects_versions_key_outside_install_group(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="versions.*sharp"):
        load_tools(_node_registry(tmp_path, 'versions = {sharp = "^1"}'))


def test_node_method_rejects_versions_bare_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="versions"):
        load_tools(_node_registry(tmp_path, 'versions = "puppeteer"'))


def test_node_method_rejects_versions_non_string_value(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="versions"):
        load_tools(_node_registry(tmp_path, "versions = {puppeteer = 25}"))


def test_node_method_rejects_versions_empty_value(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="versions"):
        load_tools(_node_registry(tmp_path, 'versions = {puppeteer = ""}'))


def test_node_method_rejects_versions_comma_in_value(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="versions"):
        load_tools(_node_registry(tmp_path, 'versions = {puppeteer = "1,2"}'))


def test_node_method_rejects_min_node_non_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="min_node"):
        load_tools(_node_registry(tmp_path, "min_node = 22"))


def test_node_method_rejects_min_node_empty_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="min_node"):
        load_tools(_node_registry(tmp_path, 'min_node = ""'))


def test_node_method_rejects_min_node_malformed_floor(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="min_node.*22.bad"):
        load_tools(_node_registry(tmp_path, 'min_node = "22.bad"'))


def test_node_method_rejects_min_node_range_and_latest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="min_node"):
        load_tools(_node_registry(tmp_path, 'min_node = "^25"'))
    with pytest.raises(ValueError, match="min_node"):
        load_tools(_node_registry(tmp_path, 'min_node = "latest"'))
    with pytest.raises(ValueError, match="min_node"):
        load_tools(_node_registry(tmp_path, 'min_node = "not.a.version"'))


def test_node_method_rejects_unknown_smoke(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="smoke.*not-a-check"):
        load_tools(_node_registry(tmp_path, 'smoke = "not-a-check"'))


def test_node_method_rejects_smoke_non_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="smoke"):
        load_tools(_node_registry(tmp_path, "smoke = 1"))


def test_node_method_rejects_smoke_empty_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="smoke"):
        load_tools(_node_registry(tmp_path, 'smoke = ""'))


def test_non_node_method_leaves_new_keys_untouched(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "ripgrep"
co_install = "not-validated"
allow_build = 1
versions = "nope"
min_node = 22
smoke = "not-a-check"
""",
    )
    tools = load_tools(manifest)
    params = tools[0].methods[0].params
    assert params["co_install"] == "not-validated"
    assert params["allow_build"] == 1
    assert params["versions"] == "nope"
    assert params["min_node"] == 22
    assert params["smoke"] == "not-a-check"
