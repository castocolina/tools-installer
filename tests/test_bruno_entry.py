from dataclasses import replace
from pathlib import Path

from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.resolve import resolve_methods, unavailable_reason
from installer.verify_registry import CHECKABLE_KINDS

REGISTRY = Path("installer/registry.toml")


def bruno() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "bruno")


def test_bruno_pins_match_the_recorded_release_digests() -> None:
    amd, arm, cask = bruno().methods
    for method, arch, asset, digest in (
        (
            amd,
            "amd64",
            "x86_64",
            "3c386b1007f66d875c34a2a502063fbad65c66e37409a316ebe518788b1e80bb",
        ),
        (arm, "arm64", "arm64", "6048c3aeb76607c71df7558deea83cfef9d33cf24a63da9e7c5268ab19d13469"),
    ):
        assert method.kind == "tarball"
        assert method.os == ("debian", "fedora", "arch") and method.arch == (arch,)
        assert method.params == {
            "url": f"https://github.com/usebruno/bruno/releases/download/v{{ver}}/bruno_{{ver}}_{asset}_linux.AppImage",
            "version": "4.3.0",
            "sha256": digest,
            "member": "bruno",
            "raw": True,
        }
    assert cask.kind == "cask" and cask.os == ("macos",)
    assert cask.params == {"cask": "bruno", "app": "Bruno.app"}
    assert "tarball" in CHECKABLE_KINDS


def test_no_bruno_method_installs_the_bru_cli() -> None:
    for method in bruno().methods:
        assert "@usebruno/cli" not in str(method.params)
        assert method.params.get("bin_name") != "bru"
        assert method.kind not in ("node", "bun", "uv-tool")
        assert "desktop" not in method.params


def test_bruno_selection_is_by_os_and_arch() -> None:
    tool = bruno()
    amd, arm, cask = tool.methods
    hosts: tuple[tuple[Platform, list[Method]], ...] = (
        (Platform(os="fedora", arch="amd64", immutable=False, has_brew=True), [amd]),
        (Platform(os="fedora", arch="arm64", immutable=False, has_brew=True), [arm]),
        (Platform(os="macos", arch="arm64", immutable=False, has_brew=True), [cask]),
        (Platform(os="fedora", arch="riscv64", immutable=False, has_brew=True), []),
    )
    for host, expected in hosts:
        assert resolve_methods(tool, host) == expected
        assert (
            resolve_methods(replace(tool, methods=tuple(reversed(tool.methods))), host) == expected
        )
    assert unavailable_reason(tool, hosts[-1][0]) is not None
    assert amd.params["url"] != arm.params["url"]
    assert all("{ver}" in str(method.params["url"]) for method in (amd, arm))


def test_bruno_config_paths_keep_the_collections() -> None:
    paths = bruno().config_paths
    assert paths == ("~/.config/bruno", "~/Library/Application Support/bruno")
    assert all("Documents" not in path for path in paths)
