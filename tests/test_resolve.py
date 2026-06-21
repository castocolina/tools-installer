from installer.model import Method, Tool
from installer.platform import Platform
from installer.resolve import resolve_methods


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
