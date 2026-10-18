import typing
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from installer.enums import Audience, Priority, Tier
from installer.model import (
    METHOD_KINDS,
    METHOD_PARAMS,
    POSTINSTALL_HOOK_NAMES,
    SKILL_HARNESSES,
    SMOKE_CHECK_NAMES,
    TOOL_ID_RE,
    ConfigStep,
    ConfigStepKind,
    Method,
    Tool,
    load_categories,
    load_tools,
)
from tests.test_registry import REGISTRY


def _seed_verified_in_content(content: str) -> str:
    lines = content.splitlines(keepends=True)
    result: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].rstrip("\n") != "[[tool]]":
            result.append(lines[i])
            i += 1
            continue
        result.append(lines[i])
        i += 1
        tool_lines: list[str] = []
        while i < n and not lines[i].startswith("["):
            tool_lines.append(lines[i])
            i += 1
        has_verified = any(tl.lstrip().startswith("verified") for tl in tool_lines)
        if has_verified:
            result.extend(tool_lines)
            continue
        inserted = False
        for tl in tool_lines:
            result.append(tl)
            if not inserted and tl.startswith("tier = "):
                result.append("verified = 2026-10-13\n")
                inserted = True
    return "".join(result)


def _write(tmp_path: Path, content: str, *, seed_verified: bool = True) -> Path:
    p = tmp_path / "registry.toml"
    text = _seed_verified_in_content(content) if seed_verified else content
    p.write_text(text)
    return p


def test_skill_harnesses_include_factory_droid_and_gemini_cli() -> None:
    assert "factory-droid" in SKILL_HARNESSES
    assert "gemini-cli" in SKILL_HARNESSES
    assert list(SKILL_HARNESSES) == sorted(SKILL_HARNESSES)


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
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "script"
os = ["macos"]
url = "https://example.test/i.sh"
shell = "sh"
""",
    )
    method = load_tools(manifest)[0].methods[0]
    assert method.os == ("macos",)
    assert "os" not in method.params
    assert method.params["url"] == "https://example.test/i.sh"


def test_load_tools_rejects_os_as_a_string(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "script"
os = "macos"
url = "https://example.test/i.sh"
shell = "sh"
""",
    )
    with pytest.raises(ValueError, match="must be a list"):
        load_tools(manifest)


def test_load_tools_reads_method_arch_targets(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "script"
os = ["macos"]
arch = ["arm64"]
url = "https://example.test/i.sh"
shell = "sh"
""",
    )
    method = load_tools(manifest)[0].methods[0]
    assert method.os == ("macos",)
    assert method.arch == ("arm64",)
    assert "arch" not in method.params
    assert method.params["url"] == "https://example.test/i.sh"


def test_load_tools_rejects_arch_as_a_string(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "script"
arch = "arm64"
url = "https://example.test/i.sh"
shell = "sh"
""",
    )
    with pytest.raises(ValueError, match="'arch' must be a list"):
        load_tools(manifest)


def test_load_tools_rejects_requires_as_a_string(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
requires = "pnpm"
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"
""",
    )
    with pytest.raises(ValueError, match="'requires' must be a list"):
        load_tools(manifest)


def test_load_tools_rejects_recommends_as_a_string(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
recommends = "rg"
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"
""",
    )
    with pytest.raises(ValueError, match="'recommends' must be a list"):
        load_tools(manifest)


def test_load_tools_rejects_a_non_string_recommends_element(tmp_path: Path) -> None:
    """tomllib returns `Any`, so a list of non-ids would otherwise be stored
    behind the declared `tuple[str, ...]` and only fail later, as a TypeError
    inside the TUI's detail bar on cursor movement."""
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
recommends = [1, 2]
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"
""",
    )
    with pytest.raises(ValueError, match="'recommends' must be a list of tool ids"):
        load_tools(manifest)


def test_load_tools_rejects_a_non_string_requires_element(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
requires = [["pnpm"]]
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"
""",
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
tier = "user"
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
tier = "user"
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
tier = "user"
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


def test_uv_tool_kind_parses_with_pypi_pkg(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "graphify"
category = "dev"
cmd = "graphify"
tier = "ai"
requires = ["uv"]
[[tool.method]]
kind = "uv-tool"
pypi_pkg = "graphifyy"
""",
    )
    tools = load_tools(manifest)
    method = tools[0].methods[0]
    assert method.kind == "uv-tool"
    assert method.params["pypi_pkg"] == "graphifyy"


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


def test_script_args_reject_shell_metacharacters(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "kitty"
category = "terminal"
cmd = "kitty"
tier = "user"
[[tool.method]]
kind = "script"
url = "https://sw.kovidgoyal.net/kitty/installer.sh"
args = ["launch=n; rm -rf ~"]
""",
    )
    with pytest.raises(ValueError, match="tool 'kitty': script 'args'"):
        load_tools(manifest)


@pytest.mark.parametrize(
    ("kind", "method_body"),
    [
        ("github_release", 'repo = "o/r"\nasset = "a.zip"\nmember = "bin/demo"'),
        ("tarball", 'url = "https://x/y.tar.xz"\nmember = "bin/demo"'),
        ("app", 'url = "https://x/y.zip"\napp = "Demo.app"'),
        ("brew", 'formula = "rg"'),
        ("script", 'url = "https://example.test/i.sh"\nshell = "sh"'),
    ],
)
def test_smoke_argv_is_accepted_on_binary_installing_kinds(
    tmp_path: Path, kind: str, method_body: str
) -> None:
    manifest = _write(
        tmp_path,
        f"""
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "{kind}"
{method_body}
smoke_argv = ["--appimage-version"]
""",
    )
    tools = load_tools(manifest)
    assert tools[0].methods[0].params["smoke_argv"] == ["--appimage-version"]


def test_refuses_existing_must_be_a_bool(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"
refuses_existing = "yes"
""",
    )
    with pytest.raises(ValueError, match=r"tool 'demo'.*refuses_existing.*true or false"):
        load_tools(manifest)


@pytest.mark.parametrize(
    "smoke_argv_toml",
    [
        '"--version"',
        "[]",
        "[1]",
        '["a b"]',
        '["a;b"]',
    ],
)
def test_smoke_argv_shape_is_validated(tmp_path: Path, smoke_argv_toml: str) -> None:
    manifest = _write(
        tmp_path,
        f"""
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "script"
url = "https://example.test/i.sh"
shell = "sh"
smoke_argv = {smoke_argv_toml}
""",
    )
    with pytest.raises(ValueError, match=r"tool 'demo'.*smoke_argv"):
        load_tools(manifest)


@pytest.mark.parametrize(
    ("kind", "method_body"),
    [
        ("host_setup", 'setup_id = "pi"'),
        ("skill_pack", ""),
    ],
)
def test_smoke_argv_is_rejected_where_nothing_is_installed(
    tmp_path: Path, kind: str, method_body: str
) -> None:
    manifest = _write(
        tmp_path,
        f"""
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "{kind}"
{method_body}
smoke_argv = ["--version"]
""",
    )
    with pytest.raises(ValueError, match=r"unknown key 'smoke_argv'"):
        load_tools(manifest)


def test_node_smoke_name_is_unchanged_by_smoke_argv(tmp_path: Path) -> None:
    known = next(iter(SMOKE_CHECK_NAMES))
    tools = load_tools(_node_registry(tmp_path, f'smoke = "{known}"'))
    assert tools[0].methods[0].params["smoke"] == known
    with pytest.raises(ValueError, match="smoke.*not-a-check"):
        load_tools(_node_registry(tmp_path, 'smoke = "not-a-check"'))


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


_VALID_SHA256 = "a" * 64


def test_pinned_url_requires_version_and_sha256(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://x/y_{ver}.tar.xz"
member = "bin/demo"
""",
    )
    with pytest.raises(ValueError, match=r"tool 'demo'.*'version'"):
        load_tools(manifest)
    manifest2 = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://x/y_{ver}.tar.xz"
member = "bin/demo"
version = "4215"
""",
    )
    with pytest.raises(ValueError, match=r"tool 'demo'.*sha256"):
        load_tools(manifest2)


def test_pinned_sha256_must_be_64_lowercase_hex(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://x/y_{ver}.tar.xz"
member = "bin/demo"
version = "1"
sha256 = "ABC"
""",
    )
    with pytest.raises(ValueError, match=r"64 lowercase hex"):
        load_tools(manifest)


def test_pinned_app_method_loads(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        f"""
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "app"
url = "https://github.com/o/r/releases/download/v{{ver}}/a-{{ver}}.zip"
app = "Demo.app"
version = "32.4.1"
sha256 = "{_VALID_SHA256}"
""",
    )
    tools = load_tools(manifest)
    params = tools[0].methods[0].params
    assert params["version"] == "32.4.1"
    assert params["sha256"] == _VALID_SHA256


def test_version_without_a_templated_url_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://x/y.tar.xz"
member = "bin/demo"
version = "1"
""",
    )
    with pytest.raises(ValueError, match=r"'version' needs a url templated"):
        load_tools(manifest)
    manifest2 = _write(
        tmp_path,
        f"""
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://x/y.tar.xz"
member = "bin/demo"
sha256 = "{_VALID_SHA256}"
""",
    )
    with pytest.raises(ValueError, match=r"'sha256' needs a url templated"):
        load_tools(manifest2)


def test_github_release_is_never_pinned(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a.zip"
member = "bin/demo"
version = "1.0"
""",
    )
    with pytest.raises(ValueError, match=r"has unknown key 'version'"):
        load_tools(manifest)


def test_missing_verified_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "x"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "rg"
""",
        seed_verified=False,
    )
    with pytest.raises(ValueError, match=r"tool 'x': missing required 'verified'"):
        load_tools(manifest)


def test_string_verified_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "x"
category = "search"
tier = "user"
verified = "2026-10-13"
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    with pytest.raises(ValueError, match=r"tool 'x'.*TOML date"):
        load_tools(manifest)


def test_integer_verified_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "x"
category = "search"
tier = "user"
verified = 20261013
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    with pytest.raises(ValueError, match=r"tool 'x'.*TOML date"):
        load_tools(manifest)


def test_datetime_verified_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "x"
category = "search"
tier = "user"
verified = 2026-10-13T00:00:00Z
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    with pytest.raises(ValueError, match=r"tool 'x'.*TOML date"):
        load_tools(manifest)


def test_future_verified_is_rejected(tmp_path: Path) -> None:
    today = date(2026, 10, 15)
    manifest_far = _write(
        tmp_path,
        """
[[tool]]
id = "x"
category = "search"
tier = "user"
verified = 2026-10-17
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    with pytest.raises(ValueError, match=r"tool 'x'.*in the future"):
        load_tools(manifest_far, today=today)
    manifest_tol = _write(
        tmp_path,
        """
[[tool]]
id = "x"
category = "search"
tier = "user"
verified = 2026-10-16
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    load_tools(manifest_tol, today=today)


def test_verified_on_a_method_table_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "x"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "rg"
verified = 2026-10-13
""",
    )
    with pytest.raises(ValueError, match=r"has unknown key 'verified'"):
        load_tools(manifest)


def test_unknown_method_key_names_the_tool_and_key(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "x/y"
asset = "a"
member = "rg"
formula = "x"
""",
    )
    with pytest.raises(
        ValueError,
        match=r"tool 'rg': method 'github_release' has unknown key 'formula'",
    ):
        load_tools(manifest)


def test_key_valid_for_another_kind_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "rg"
npm_pkg = "x"
""",
    )
    with pytest.raises(ValueError, match=r"has unknown key 'npm_pkg'"):
        load_tools(manifest)


def test_kind_only_method_loads(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
""",
    )
    tools = load_tools(manifest)
    assert tools[0].methods[0].params == {}


def test_method_params_covers_every_kind() -> None:
    assert set(METHOD_PARAMS) == set(METHOD_KINDS)
    assert METHOD_PARAMS["skill_pack"] == frozenset()
    for allowed in METHOD_PARAMS.values():
        assert "kind" not in allowed
        assert "os" not in allowed
        assert "arch" not in allowed


def test_shipped_registry_uses_only_allowed_method_keys() -> None:
    registry = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
    tools = load_tools(registry)
    for tool in tools:
        for method in tool.methods:
            allowed = METHOD_PARAMS[method.kind]
            assert set(method.params) <= allowed, (tool.id, method.kind, method.params)


def test_method_with_a_key_outside_its_kind_is_rejected(tmp_path: Path) -> None:
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
    with pytest.raises(ValueError, match=r"has unknown key 'allow_build'"):
        load_tools(manifest)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("os", "macos", "method 'os' must be a list of strings"),
        ("arch", "arm64", "method 'arch' must be a list of strings"),
    ],
)
def test_string_os_and_arch_still_fail_after_the_closed_key_check(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    manifest = _write(
        tmp_path,
        f"""
[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "x"
{field} = "{value}"
""",
    )
    with pytest.raises(ValueError, match=message):
        load_tools(manifest)

    manifest_ok = _write(
        tmp_path,
        """
[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "x"
os = ["macos"]
arch = ["arm64"]
""",
    )
    tools = load_tools(manifest_ok)
    assert tools[0].methods[0].params == {"formula": "x"}


def test_postinstall_field_parses_with_a_known_hook_name(tmp_path: Path) -> None:
    """`postinstall` names a hook from the closed dispatch table in
    `installer/postinstall.py`, mirroring `smoke`'s closed-set-by-name shape
    one level up: on `Tool` itself, not on a single `Method`."""
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "codegraph"
category = "dev"
tier = "ai"
postinstall = "codegraph-mcp-register"
[[tool.method]]
kind = "github_release"
repo = "x/y"
asset = "a"
member = "codegraph"
""",
    )
    tools = load_tools(manifest)
    assert tools[0].postinstall == "codegraph-mcp-register"


def test_postinstall_defaults_to_none(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "rg"
category = "search"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "rg"
""",
    )
    tools = load_tools(manifest)
    assert tools[0].postinstall is None


def test_unknown_postinstall_name_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "codegraph"
category = "dev"
tier = "ai"
postinstall = "not-a-real-hook"
[[tool.method]]
kind = "github_release"
repo = "x/y"
asset = "a"
member = "codegraph"
""",
    )
    with pytest.raises(ValueError, match="codegraph") as exc_info:
        load_tools(manifest)
    assert "not-a-real-hook" in str(exc_info.value)


def test_empty_string_postinstall_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "codegraph"
category = "dev"
tier = "ai"
postinstall = ""
[[tool.method]]
kind = "github_release"
repo = "x/y"
asset = "a"
member = "codegraph"
""",
    )
    with pytest.raises(ValueError, match="non-empty string"):
        load_tools(manifest)


def test_non_string_postinstall_is_rejected(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "codegraph"
category = "dev"
tier = "ai"
postinstall = 1
[[tool.method]]
kind = "github_release"
repo = "x/y"
asset = "a"
member = "codegraph"
""",
    )
    with pytest.raises(ValueError, match="non-empty string"):
        load_tools(manifest)


def test_postinstall_hook_names_matches_the_real_dispatch_table() -> None:
    """WR-02 (internal dual-lane review): model.py's own comment claims
    POSTINSTALL_HOOK_NAMES is "duplicated (not imported)" from
    installer.postinstall.POSTINSTALL_HOOKS's keys -- unlike SMOKE_CHECK_NAMES/
    SMOKE_CHECKS, which has exactly this drift guard (tests/test_executors.py),
    nothing previously pinned the two postinstall sets to actually agree.
    """
    from installer.postinstall import POSTINSTALL_HOOKS

    assert frozenset(POSTINSTALL_HOOKS) == POSTINSTALL_HOOK_NAMES


def test_duplicate_status_probe_harness_fails_at_load(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo-skills"
category = "ai"
tier = "user"
[[tool.method]]
kind = "skill_pack"

[tool.skill_lifecycle]
source = "https://github.com/example/skills"
owner = "example"
supported_harnesses = ["claude"]
revision_policy = "upstream-latest"
targets = [{ scope = "harness", path = "<codex-plugin-dir>/demo" }]
status_probes = [
  { harness = "claude", via = "plugin-cli", match = "demo" },
  { harness = "claude", via = "plugin-cli", match = "other" },
]

[tool.skill_lifecycle.install]
mode = "manual-required"
instructions = ["Review and run the official install flow."]

[tool.skill_lifecycle.status]
mode = "manual-required"
instructions = ["Review and run the official status flow."]

[tool.skill_lifecycle.update]
mode = "manual-required"
instructions = ["Review and run the official update flow."]

[tool.skill_lifecycle.removal]
mode = "manual-required"
instructions = ["Review and run the official removal flow."]
""",
    )

    with pytest.raises(ValueError, match="demo-skills") as exc:
        load_tools(manifest)
    message = str(exc.value)
    assert "claude" in message
    assert "duplicate" in message


def test_shipped_status_probes_do_not_repeat_a_harness() -> None:
    registry = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
    tools = load_tools(registry)
    assert tools
    for tool in tools:
        lifecycle = tool.skill_lifecycle
        if lifecycle is None:
            continue
        harnesses = [probe.harness for probe in lifecycle.status_probes]
        assert len(harnesses) == len(set(harnesses)), tool.id


@pytest.mark.parametrize(
    "strip_line",
    [
        "strip = true",
        "strip = -1",
        'strip = "1"',
    ],
)
def test_strip_must_be_a_non_negative_integer(tmp_path: Path, strip_line: str) -> None:
    manifest = _write(
        tmp_path,
        f"""
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a.tar.gz"
member = "bin/demo"
{strip_line}
""",
    )
    with pytest.raises(ValueError, match="demo") as exc_info:
        load_tools(manifest)
    assert "strip" in str(exc_info.value)


def test_strip_positive_integer_on_tarball_loads(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://example.test/y.tar.gz"
member = "bin/demo"
strip = 2
""",
    )
    tools = load_tools(manifest)
    assert tools[0].methods[0].params["strip"] == 2


@pytest.mark.parametrize(
    ("extra",),
    [
        ('archive = "zip"\nstrip = 0',),
        ("raw = true\nstrip = 1",),
    ],
)
def test_strip_is_rejected_where_install_ignores_it(tmp_path: Path, extra: str) -> None:
    manifest = _write(
        tmp_path,
        f"""
[[tool]]
id = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a.zip"
member = "bin/demo"
{extra}
""",
    )
    with pytest.raises(ValueError, match="demo") as exc_info:
        load_tools(manifest)
    assert "strip" in str(exc_info.value)


def test_config_step_is_frozen_with_closed_kinds() -> None:
    step = ConfigStep(text="t", kind="plugin_enable")
    assert (step.harness, step.argv, step.cwd) == (None, (), None)
    field_name = "text"
    with pytest.raises(FrozenInstanceError):
        setattr(step, field_name, "u")
    assert typing.get_args(ConfigStepKind) == (
        "skill_install",
        "plugin_enable",
        "plugin_uninstall",
        "marketplace_remove",
        "terminal_sync",
        "pnpm_group_install",
        "project_pack_global_uninstall",
        "project_pack_install",
    )


@pytest.mark.parametrize("tool_id", ["../x", "Yq", "a/b", "-x"])
def test_load_tools_rejects_an_unsafe_tool_id(tmp_path: Path, tool_id: str) -> None:
    manifest = _write(
        tmp_path,
        f"""
[[tool]]
id = "{tool_id}"
name = "demo"
category = "search"
tier = "user"
[[tool.method]]
kind = "uv-tool"
package = "demo"
""",
    )
    with pytest.raises(ValueError, match="id must match") as exc_info:
        load_tools(manifest)
    assert tool_id in str(exc_info.value)
    assert "[a-z0-9][a-z0-9._-]*" in str(exc_info.value)


def test_every_registry_tool_id_is_a_safe_filename() -> None:
    tools = load_tools(REGISTRY)
    assert tools
    assert all(TOOL_ID_RE.fullmatch(tool.id) for tool in tools)


def _lifecycle_manifest(
    lifecycle_keys: str = "",
    targets: str = '[{ scope = "project", path = "<project>/<selected-runtime-dir>" }]',
) -> str:
    operations = "\n".join(
        f'[tool.skill_lifecycle.{operation}]\nmode = "manual-required"\n'
        f'instructions = ["Review and run the official {operation} flow."]\n'
        for operation in ("install", "status", "update", "removal")
    )
    return f"""
[[tool]]
id = "demo-pack"
category = "ai"
tier = "user"
[[tool.method]]
kind = "skill_pack"

[tool.skill_lifecycle]
source = "https://github.com/example/skills"
owner = "example"
supported_harnesses = ["claude"]
revision_policy = "upstream-latest"
targets = {targets}
{lifecycle_keys}

{operations}
"""


def test_skill_lifecycle_scope_defaults_to_user(tmp_path: Path) -> None:
    (tool,) = load_tools(_write(tmp_path, _lifecycle_manifest()))

    assert tool.skill_lifecycle is not None
    assert tool.skill_lifecycle.scope == "user"
    assert tool.skill_lifecycle.version is None


def test_skill_lifecycle_rejects_an_unknown_scope(tmp_path: Path) -> None:
    manifest = _write(tmp_path, _lifecycle_manifest('scope = "global"'))

    with pytest.raises(ValueError, match="demo-pack") as exc_info:
        load_tools(manifest)
    assert "scope 'global'" in str(exc_info.value)


@pytest.mark.parametrize("pin", ["", 'version = "latest"', 'version = "1.16"', "version = 1"])
def test_project_pack_requires_a_semver_pin(tmp_path: Path, pin: str) -> None:
    manifest = _write(tmp_path, _lifecycle_manifest(f'scope = "project"\n{pin}'))

    with pytest.raises(ValueError, match="demo-pack") as exc_info:
        load_tools(manifest)
    assert "version" in str(exc_info.value)


def test_project_pack_accepts_a_semver_pin(tmp_path: Path) -> None:
    manifest = _write(tmp_path, _lifecycle_manifest('scope = "project"\nversion = "1.16.0"'))

    (tool,) = load_tools(manifest)

    assert tool.skill_lifecycle is not None
    assert (tool.skill_lifecycle.scope, tool.skill_lifecycle.version) == ("project", "1.16.0")


def test_project_pack_rejects_a_global_target(tmp_path: Path) -> None:
    targets = (
        '[{ scope = "global", path = "<selected-runtime-global-dir>" },'
        ' { scope = "project", path = "<project>/<selected-runtime-dir>" }]'
    )
    manifest = _write(
        tmp_path, _lifecycle_manifest('scope = "project"\nversion = "1.16.0"', targets)
    )

    with pytest.raises(ValueError, match="demo-pack") as exc_info:
        load_tools(manifest)
    assert "global" in str(exc_info.value)
