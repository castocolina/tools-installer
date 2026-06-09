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
