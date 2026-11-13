from dataclasses import replace
from pathlib import Path

import pytest

from installer.assets import arch_tokens, render_asset
from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.resolve import platform_could_support, resolve_methods, unavailable_reason
from installer.session import Disposition, build_plan
from installer.version_status import Health
from tests.state_doubles import pass_state, plan_state

_REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _tool(*kinds: str) -> Tool:
    return Tool(
        id="t",
        name="t",
        category="c",
        cmd="t",
        methods=tuple(Method(kind=k) for k in kinds),
    )


def test_macos_prefers_script_then_brew():
    platform = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    tool = _tool("script", "brew", "apt")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["script", "brew"]


def test_userspace_before_native():
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    tool = _tool("dnf", "github_release")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["github_release", "dnf"]


def test_native_filtered_to_matching_os():
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    tool = _tool("dnf", "apt", "pacman")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["apt"]


def test_immutable_skips_native():
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    tool = _tool("github_release", "dnf")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["github_release"]


def test_rpm_ostree_skipped_by_default():
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    tool = _tool("github_release", "rpm_ostree")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["github_release"]


def test_brew_requires_brew_present():
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    tool = _tool("brew")
    assert resolve_methods(tool, platform) == []


def test_immutable_no_brew_native_only_returns_empty():
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    tool = _tool("dnf", "brew")
    assert resolve_methods(tool, platform) == []


def test_os_filter_restricts_a_method_to_its_target_os() -> None:
    mac = Method(kind="script", params={"url": "https://example.test/i.sh"}, os=("macos",))
    linux = Method(
        kind="script", params={"url": "https://example.test/i.sh"}, os=("debian", "arch", "fedora")
    )
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(mac, linux))
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    debian = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    assert resolve_methods(tool, macos) == [mac]
    assert resolve_methods(tool, debian) == [linux]


def test_method_without_os_applies_on_every_platform() -> None:
    method = Method(kind="script", params={"url": "https://example.test/i.sh"})
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(method,))
    for os_name in ("macos", "debian", "arch", "fedora"):
        platform = Platform(os=os_name, arch="amd64", immutable=False, has_brew=False)
        assert resolve_methods(tool, platform) == [method]


def test_arch_filter_restricts_a_method_to_its_target_arch() -> None:
    arm = Method(kind="script", params={"url": "https://example.test/a"}, arch=("arm64",))
    intel = Method(kind="script", params={"url": "https://example.test/b"}, arch=("amd64",))
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(arm, intel))
    arm_mac = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    intel_mac = Platform(os="macos", arch="amd64", immutable=False, has_brew=False)
    assert resolve_methods(tool, arm_mac) == [arm]
    assert resolve_methods(tool, intel_mac) == [intel]


def test_method_without_arch_applies_on_every_arch() -> None:
    method = Method(kind="script", params={"url": "https://example.test/i.sh"})
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(method,))
    for arch in ("amd64", "arm64"):
        platform = Platform(os="debian", arch=arch, immutable=False, has_brew=False)
        assert resolve_methods(tool, platform) == [method]


def test_os_and_arch_filters_compose() -> None:
    method = Method(
        kind="script", params={"url": "https://example.test/i.sh"}, os=("macos",), arch=("arm64",)
    )
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(method,))
    arm_mac = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    arm_linux = Platform(os="debian", arch="arm64", immutable=False, has_brew=False)
    intel_mac = Platform(os="macos", arch="amd64", immutable=False, has_brew=False)
    assert resolve_methods(tool, arm_mac) == [method]
    assert resolve_methods(tool, arm_linux) == []
    assert resolve_methods(tool, intel_mac) == []


def test_cask_requires_macos_and_brew() -> None:
    cask = Method(kind="cask", params={"cask": "x"})
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(cask,))
    mac_brew = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    mac_no_brew = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    linux_brew = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    assert resolve_methods(tool, mac_brew) == [cask]
    assert resolve_methods(tool, mac_no_brew) == []
    assert resolve_methods(tool, linux_brew) == []


def test_app_ranks_with_userspace_downloads_before_cask() -> None:
    app = Method(kind="app", params={"url": "u", "app": "A.app"}, os=("macos",))
    cask = Method(kind="cask", params={"cask": "a"})
    tool = Tool(id="t", name="t", category="c", cmd="t", methods=(cask, app))
    mac = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(tool, mac)] == ["app", "cask"]


def test_node_is_userspace_ranked_before_brew():
    platform = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    tool = _tool("brew", "node")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["node", "brew"]


def test_node_applies_on_every_platform():
    for os_name in ("debian", "arch", "fedora", "macos"):
        platform = Platform(os=os_name, arch="amd64", immutable=False, has_brew=False)
        assert [m.kind for m in resolve_methods(_tool("node"), platform)] == ["node"]


def test_uv_tool_is_userspace_ranked_before_brew():
    platform = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    tool = _tool("brew", "uv-tool")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["uv-tool", "brew"]


def test_uv_tool_applies_on_every_platform_including_immutable():
    for os_name in ("debian", "arch", "fedora", "macos"):
        for immutable in (False, True):
            platform = Platform(os=os_name, arch="amd64", immutable=immutable, has_brew=False)
            assert [m.kind for m in resolve_methods(_tool("uv-tool"), platform)] == ["uv-tool"]


def test_sdkman_is_userspace_ranked_before_brew():
    platform = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    tool = _tool("brew", "sdkman")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["sdkman", "brew"]


def test_sdkman_applies_on_every_platform_including_immutable():
    for os_name in ("debian", "arch", "fedora", "macos"):
        for immutable in (False, True):
            platform = Platform(os=os_name, arch="amd64", immutable=immutable, has_brew=False)
            assert [m.kind for m in resolve_methods(_tool("sdkman"), platform)] == ["sdkman"]


def _macos_arm64_min_26_tool() -> Tool:
    return Tool(
        id="t",
        name="t",
        category="c",
        cmd="t",
        methods=(
            Method(
                kind="brew",
                params={"formula": "x", "min_os_version": "26"},
                os=("macos",),
                arch=("arm64",),
            ),
        ),
    )


def test_min_os_version_gate_blocks_a_too_old_macos() -> None:
    tool = _macos_arm64_min_26_tool()
    method = tool.methods[0]
    assert resolve_methods(
        tool, Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")
    ) == [method]
    assert resolve_methods(
        tool, Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="27.1")
    ) == [method]
    assert (
        resolve_methods(
            tool,
            Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="15.0"),
        )
        == []
    )
    assert (
        resolve_methods(
            tool,
            Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version=None),
        )
        == []
    )


def _registry_tool(tool_id: str) -> Tool:
    return next(tool for tool in load_tools(_REGISTRY) if tool.id == tool_id)


def test_unavailable_reason_alacritty_names_distrobox_and_podman() -> None:
    reason = unavailable_reason(
        _registry_tool("alacritty"),
        Platform(os="fedora", arch="amd64", immutable=True, has_brew=True),
    )
    assert reason is not None
    assert reason.short == "needs distrobox and podman"
    assert "distrobox" in reason.detail
    assert "podman" in reason.detail


def test_unavailable_reason_gnu_bash_names_unsupported_os() -> None:
    reason = unavailable_reason(
        _registry_tool("gnu-bash"),
        Platform(os="fedora", arch="amd64", immutable=True, has_brew=True),
    )
    assert reason is not None
    assert reason.short == "fedora not supported"
    assert "macos" in reason.detail


def test_unavailable_reason_rg_on_immutable_fedora_is_available() -> None:
    assert (
        unavailable_reason(
            _registry_tool("rg"),
            Platform(os="fedora", arch="amd64", immutable=True, has_brew=True),
        )
        is None
    )


def test_unavailable_reason_container_names_its_macos_floor() -> None:
    reason = unavailable_reason(
        _registry_tool("container"),
        Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0"),
    )
    assert reason is not None
    assert reason.short == "needs macOS 26+"


def test_unavailable_reason_mixed_lists_shorts_in_declaration_order() -> None:
    tool = Tool(
        id="split",
        name="split",
        category="c",
        cmd="split",
        methods=(
            Method(
                kind="script",
                params={"url": "https://example.test/l"},
                os=("fedora",),
                arch=("arm64",),
            ),
            Method(kind="dnf", params={"package": "split"}),
        ),
    )
    reason = unavailable_reason(
        tool, Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    )
    assert reason is not None
    assert reason.detail == "no method applies here: not built for amd64; immutable host"


def test_unavailable_reason_drops_an_os_only_rejection_beside_an_arch_one() -> None:
    """The old fixture (a macOS-only method plus a fedora/arm64 one) now reads one category."""
    tool = Tool(
        id="split",
        name="split",
        category="c",
        cmd="split",
        methods=(
            Method(kind="script", params={"url": "https://example.test/m"}, os=("macos",)),
            Method(
                kind="script",
                params={"url": "https://example.test/l"},
                os=("fedora",),
                arch=("arm64",),
            ),
        ),
    )
    reason = unavailable_reason(
        tool, Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    )
    assert reason is not None
    assert reason.short == "not built for amd64"


def test_unavailable_reason_empty_methods() -> None:
    tool = Tool(id="empty", name="empty", category="c", cmd="empty", methods=())
    reason = unavailable_reason(
        tool, Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    )
    assert reason is not None
    assert reason.short == "no install method"


def test_unavailable_reason_matches_platform_could_support_for_every_tool() -> None:
    platforms = (
        Platform(os="fedora", arch="amd64", immutable=True, has_brew=True),
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
        Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="15.0"),
    )
    for tool in load_tools(_REGISTRY):
        for platform in platforms:
            assert (unavailable_reason(tool, platform) is None) == platform_could_support(
                tool, platform
            ), tool.id


def test_platform_could_support_ignores_missing_brew_but_not_wrong_platform() -> None:
    tool = _macos_arm64_min_26_tool()
    assert (
        platform_could_support(
            tool,
            Platform(os="macos", arch="arm64", immutable=False, has_brew=False, os_version="26.0"),
        )
        is True
    )
    assert (
        platform_could_support(
            tool,
            Platform(os="debian", arch="amd64", immutable=False, has_brew=True, os_version=None),
        )
        is False
    )
    assert (
        platform_could_support(
            tool,
            Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="15.0"),
        )
        is False
    )


def test_copilot_resolves_per_platform() -> None:
    copilot = next(t for t in load_tools(_REGISTRY) if t.id == "copilot")
    for arch in ("arm64", "amd64"):
        mac = Platform(os="macos", arch=arch, immutable=False, has_brew=True)
        assert [(m.kind, m.params["cask"]) for m in resolve_methods(copilot, mac)] == [
            ("cask", "copilot-cli")
        ]
    for os_name, arch, asset in (
        ("fedora", "amd64", "copilot-linux-x64.tar.gz"),
        ("debian", "amd64", "copilot-linux-x64.tar.gz"),
        ("arch", "amd64", "copilot-linux-x64.tar.gz"),
        ("fedora", "arm64", "copilot-linux-arm64.tar.gz"),
    ):
        linux = Platform(os=os_name, arch=arch, immutable=False, has_brew=False)
        methods = resolve_methods(copilot, linux)
        assert [m.kind for m in methods] == ["github_release"]
        assert render_asset(str(methods[0].params["asset"]), "1.0.107", arch_tokens(arch)) == asset
        with_brew = Platform(os=os_name, arch=arch, immutable=False, has_brew=True)
        assert "cask" not in [m.kind for m in resolve_methods(copilot, with_brew)]


def _host(
    os_name: str = "fedora",
    *,
    arch: str = "amd64",
    immutable: bool = False,
    tools: bool = False,
    node: str | None = None,
) -> Platform:
    return Platform(
        os=os_name,
        arch=arch,
        immutable=immutable,
        has_brew=False,
        has_distrobox=tools,
        has_podman=tools,
        node_version=node,
    )


@pytest.mark.parametrize(
    ("platform", "first", "short"),
    [
        (_host(immutable=True, tools=True), "cargo_distrobox", None),
        (_host(immutable=True), None, "needs distrobox and podman"),
        (_host(), "dnf", None),
        (_host(tools=True), "cargo_distrobox", None),
        (_host("macos", arch="arm64"), None, "macos not supported"),
    ],
)
def test_precedence_fixtures(platform: Platform, first: str | None, short: str | None) -> None:
    alacritty = _registry_tool("alacritty")
    methods = resolve_methods(alacritty, platform)
    assert (methods[0].kind if methods else None) == first
    reason = unavailable_reason(alacritty, platform)
    assert (reason.short if reason else None) == short


def test_mutable_without_tools_plans_the_dnf_handoff() -> None:
    alacritty = _registry_tool("alacritty")
    platform = _host()
    state = plan_state(alacritty, platform=platform, health=Health.MISSING, present=False)
    rows = build_plan(
        ["alacritty"], [alacritty], {"alacritty": state}.get, platform, reinstall=frozenset()
    )
    assert [row.disposition for row in rows] == [Disposition.MANUAL]
    assert rows[0].manual_command is not None
    assert "dnf" in rows[0].manual_command


@pytest.mark.parametrize("which", ["distrobox", "podman"])
def test_only_distrobox_or_only_podman_is_not_enough(which: str) -> None:
    alacritty = _registry_tool("alacritty")
    platform = replace(
        _host(immutable=True), has_distrobox=which == "distrobox", has_podman=which == "podman"
    )
    assert resolve_methods(alacritty, platform) == []
    reason = unavailable_reason(alacritty, platform)
    assert reason is not None
    assert reason.short == "needs distrobox and podman"


def test_unavailable_reason_deduplicates_shorts() -> None:
    tool = Tool(
        id="split",
        name="split",
        category="c",
        cmd="split",
        methods=(
            Method(kind="dnf", params={"package": "x"}),
            Method(kind="apt", params={"package": "x"}),
            Method(kind="pacman", params={"package": "x"}),
            Method(kind="script", params={"url": "https://example.test/l"}, arch=("arm64",)),
        ),
    )
    reason = unavailable_reason(tool, _host(immutable=True))
    assert reason is not None
    assert reason.detail == "no method applies here: immutable host; not built for amd64"


def test_os_only_rejections_drop_when_another_method_passes_the_os_gate() -> None:
    puppeteer = _registry_tool("puppeteer")
    floor = unavailable_reason(puppeteer, _host("debian", node="20.19.2"))
    assert floor is not None
    assert floor.short == "needs Node >= 22.12.0; this system has 20.19.2"
    arm = unavailable_reason(puppeteer, _host("debian", arch="arm64"))
    assert arm is not None
    assert arm.short == "not built for arm64"
    assert "debian not supported" not in arm.detail


def test_node_floor_rejects_with_the_reason() -> None:
    mmdc = _registry_tool("mmdc")
    reason = unavailable_reason(mmdc, _host("debian", node="20.19.2"))
    assert reason is not None
    assert reason.short == "needs Node >= 22.12.0; this system has 20.19.2"
    assert "mmdc needs Node 22.12.0 or newer" in reason.detail
    assert resolve_methods(mmdc, _host("debian", node="20.19.2")) == []
    assert [m.kind for m in resolve_methods(mmdc, _host("debian", node="26.13.0"))] == ["node"]
    assert [m.kind for m in resolve_methods(mmdc, _host("debian", node="22.12.0"))] == ["node"]
    assert [m.kind for m in resolve_methods(mmdc, _host("debian", node=None))] == ["node"]


def test_node_floor_rejects_a_prerelease_at_the_floor() -> None:
    mmdc = _registry_tool("mmdc")
    reason = unavailable_reason(mmdc, _host("debian", node="22.12.0-rc.1"))
    assert reason is not None
    assert reason.short == "needs Node >= 22.12.0; this system has 22.12.0-rc.1"


def test_node_floor_plans_blocked_not_failed() -> None:
    catalog = [_registry_tool(tool_id) for tool_id in ("pnpm", "puppeteer", "mmdc")]
    platform = _host("debian", node="20.19.2")
    states = {tool.id: pass_state(tool, platform=platform, present=False) for tool in catalog}
    rows = {
        row.tool_id: row
        for row in build_plan(["mmdc"], catalog, states.get, platform, reinstall=frozenset())
    }
    assert rows["mmdc"].disposition is Disposition.BLOCKED
    assert "needs Node 22.12.0 or newer" in rows["mmdc"].reason
    assert "20.19.2" in rows["mmdc"].reason
    assert rows["puppeteer"].disposition is Disposition.BLOCKED
