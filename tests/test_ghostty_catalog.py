"""Consistency guards for the Ghostty catalog entry."""

import re
from pathlib import Path

from installer.download import artifact_paths, pinned_method
from installer.model import Tool, load_tools
from installer.terminal_regions import ghostty_default_files

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _note_methods(tools: list[Tool]) -> set[tuple[str, str]]:
    return {
        (tool.id, method.kind)
        for tool in tools
        for method in tool.methods
        if "note" in method.params
    }


def test_ghostty_config_paths_cover_every_resolver_directory(tmp_path: Path) -> None:
    ghostty = next(tool for tool in load_tools(REGISTRY) if tool.id == "ghostty")
    paths = {tmp_path / path.removeprefix("~/") for path in ghostty.config_paths}
    for os_name in ("fedora", "macos"):
        assert {path.parent for path in ghostty_default_files(os_name, tmp_path, {})} <= paths


def test_both_ghostty_appimage_tarball_methods_are_pinned_github_releases() -> None:
    ghostty = next(tool for tool in load_tools(REGISTRY) if tool.id == "ghostty")
    methods = [method for method in ghostty.methods if method.kind == "tarball"]
    assert len(methods) == 2
    pattern = (
        r"https://github\.com/pkgforge-dev/ghostty-appimage/releases/download/"
        r"v\{ver\}/Ghostty-\{ver\}-(x86_64|aarch64)\.AppImage"
    )
    architectures: set[str] = set()
    for method in methods:
        assert pinned_method(method)
        url = method.params["url"]
        assert isinstance(url, str)
        match = re.fullmatch(pattern, url)
        assert match
        architectures.add(match.group(1))
    assert architectures == {"x86_64", "aarch64"}
    assert methods[0].params["version"] == methods[1].params["version"]
    assert methods[0].params["sha256"] != methods[1].params["sha256"]


def test_the_community_build_note_is_only_on_the_ghostty_appimage_methods() -> None:
    tools = load_tools(REGISTRY)
    assert _note_methods(tools) == {("ghostty", "tarball")}
    assert sum("note" in method.params for tool in tools for method in tool.methods) == 2


def test_every_desktop_method_is_a_raw_tarball_with_two_leaves() -> None:
    for tool in load_tools(REGISTRY):
        for method in tool.methods:
            if "desktop" not in method.params:
                continue
            assert method.kind == "tarball"
            assert method.params["raw"] is True
            artifacts = artifact_paths(method, Path("/h/.local/bin"))
            assert [artifact.kind for artifact in artifacts] == ["file", "leaf", "leaf"]
            desktop = method.params["desktop"]
            assert [artifact.path.name for artifact in artifacts[1:]] == [
                f"{desktop}.desktop",
                f"{desktop}.png",
            ]
