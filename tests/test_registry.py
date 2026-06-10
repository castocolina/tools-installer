from pathlib import Path

from installer.model import load_tools
from installer.platform import Platform
from installer.resolve import resolve_methods

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def test_registry_loads():
    tools = load_tools(REGISTRY)
    assert tools, "registry should declare at least one tool"


def test_registry_ids_unique():
    ids = [t.id for t in load_tools(REGISTRY)]
    assert len(ids) == len(set(ids))


def test_every_tool_has_at_least_one_method():
    assert all(t.methods for t in load_tools(REGISTRY))


def test_registry_includes_homebrew_with_os_targeted_install() -> None:
    brew = next(t for t in load_tools(REGISTRY) if t.id == "brew")
    assert {m.kind for m in brew.methods} == {"script"}
    # Look up by os membership so the test survives a reordering of the os lists.
    mac = next(m for m in brew.methods if "macos" in m.os)
    assert mac.params["bin_dir"] == "/opt/homebrew/bin"
    assert mac.params["env"] == {"NONINTERACTIVE": "1"}
    assert mac.params["shell"] == "bash"
    linux = next(m for m in brew.methods if "debian" in m.os)
    assert linux.params["bin_dir"] == "/home/linuxbrew/.linuxbrew/bin"
    assert linux.params["env"] == {"NONINTERACTIVE": "1"}
    assert linux.params["shell"] == "bash"


def test_homebrew_resolves_per_platform() -> None:
    brew = next(t for t in load_tools(REGISTRY) if t.id == "brew")
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    # immutable=True (Bazzite/Silverblue): brew is the recommended path there, and
    # script methods are not gated by immutability, so it must still resolve.
    fedora = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    assert [m.params["bin_dir"] for m in resolve_methods(brew, macos)] == ["/opt/homebrew/bin"]
    assert [m.params["bin_dir"] for m in resolve_methods(brew, fedora)] == [
        "/home/linuxbrew/.linuxbrew/bin"
    ]


def test_fd_resolves_per_platform() -> None:
    fd = next(t for t in load_tools(REGISTRY) if t.id == "fd")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    lin = resolve_methods(fd, linux)
    assert lin[0].kind == "github_release"
    assert lin[0].params["asset"] == "fd-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
    assert lin[0].params["strip"] == 1
    assert [m.kind for m in lin] == ["github_release", "brew"]
    mac = resolve_methods(fd, macos)
    assert [m.kind for m in mac] == ["github_release", "brew"]
    assert mac[0].params["asset"] == "fd-v{ver}-{arch.machine}-apple-darwin.tar.gz"


def test_delta_brew_formula_is_git_delta() -> None:
    delta = next(t for t in load_tools(REGISTRY) if t.id == "delta")
    brew = next(m for m in delta.methods if m.kind == "brew")
    assert brew.params["formula"] == "git-delta"


def test_ripgrep_github_release_is_os_split_and_strips() -> None:
    rg = next(t for t in load_tools(REGISTRY) if t.id == "rg")
    gh_methods = [m for m in rg.methods if m.kind == "github_release"]
    # Compare as frozensets so the assertion does not depend on os-list ordering.
    assert {frozenset(m.os) for m in gh_methods} == {
        frozenset({"debian", "arch", "fedora"}),
        frozenset({"macos"}),
    }
    assert all(m.params["strip"] == 1 and m.params["member"] == "rg" for m in gh_methods)


def test_eza_resolves_to_download_on_linux_and_brew_only_on_macos() -> None:
    eza = next(t for t in load_tools(REGISTRY) if t.id == "eza")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(eza, linux)] == ["github_release", "brew"]
    # eza ships no macOS asset, so only brew is left on a Mac.
    assert [m.kind for m in resolve_methods(eza, macos)] == ["brew"]


def test_gh_uses_nested_member_on_linux_and_brew_only_on_macos() -> None:
    gh = next(t for t in load_tools(REGISTRY) if t.id == "gh")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    method = resolve_methods(gh, linux)[0]
    assert method.kind == "github_release"
    assert method.params["member"] == "bin/gh"
    assert method.params["strip"] == 1
    # gh ships macOS only as zip/pkg, so only brew is left on a Mac.
    assert [m.kind for m in resolve_methods(gh, macos)] == ["brew"]


def test_yq_resolves_to_a_raw_download_on_every_os() -> None:
    yq = next(t for t in load_tools(REGISTRY) if t.id == "yq")
    for platform_os in ("debian", "macos"):
        platform = Platform(os=platform_os, arch="amd64", immutable=False, has_brew=False)
        top = resolve_methods(yq, platform)[0]
        assert top.kind == "github_release"
        assert top.params.get("raw") is True
        assert "strip" not in top.params  # raw downloads never unpack


def test_direnv_is_raw_per_os_download() -> None:
    direnv = next(t for t in load_tools(REGISTRY) if t.id == "direnv")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    lin = resolve_methods(direnv, linux)[0]
    mac = resolve_methods(direnv, macos)[0]
    assert lin.params == {
        "repo": "direnv/direnv",
        "asset": "direnv.linux-{arch.deb}",
        "member": "direnv",
        "raw": True,
    }
    assert mac.params["asset"] == "direnv.darwin-{arch.deb}"
    assert "strip" not in lin.params and "strip" not in mac.params


def test_hyperfine_linux_uses_gnu_and_strips() -> None:
    hf = next(t for t in load_tools(REGISTRY) if t.id == "hyperfine")
    linux = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    method = resolve_methods(hf, linux)[0]
    assert method.params["asset"] == "hyperfine-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
    assert method.params["strip"] == 1


def test_download_tools_resolve_github_release_then_brew_on_macos() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    for tool_id in ("starship", "just", "ruff", "dust"):
        kinds = [m.kind for m in resolve_methods(tools[tool_id], macos)]
        assert kinds == ["github_release", "brew"], tool_id


def test_every_tool_resolves_at_least_one_method_on_each_platform() -> None:
    # A tool that resolves to nothing on a supported platform is silently
    # uninstallable there; this guards against an os/method misconfiguration.
    tools = load_tools(REGISTRY)
    for platform_os in ("debian", "arch", "fedora", "macos"):
        platform = Platform(os=platform_os, arch="amd64", immutable=False, has_brew=True)
        stranded = [t.id for t in tools if not resolve_methods(t, platform)]
        assert not stranded, f"no install method on {platform_os}: {stranded}"
