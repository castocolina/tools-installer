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


def test_bottom_and_difftastic_cmd_differs_from_member_binary() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    bottom = tools["bottom"]
    difft = tools["difftastic"]
    assert bottom.cmd == "btm"
    assert difft.cmd == "difft"
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    assert resolve_methods(bottom, linux)[0].params["member"] == "btm"
    assert resolve_methods(difft, linux)[0].params["member"] == "difft"


def test_charm_tools_use_suffix_arch_token_and_strip() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    # arm64 is the harder arch (suffix=arm64, not aarch64); check both OS families
    # so the Linux_ and Darwin_ asset casing are both pinned.
    arch_linux = Platform(os="arch", arch="arm64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    for tool_id in ("gum", "glow"):
        for platform, os_word in ((arch_linux, "Linux"), (macos, "Darwin")):
            method = resolve_methods(tools[tool_id], platform)[0]
            assert method.params["asset"] == f"{tool_id}_{{ver}}_{os_word}_{{arch.suffix}}.tar.gz"
            assert method.params["strip"] == 1


def test_raw_tools_have_no_strip_and_resolve_per_os() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    expected_linux_asset = {
        "shfmt": "shfmt_v{ver}_linux_{arch.deb}",
        "tealdeer": "tealdeer-linux-{arch.machine}-musl",
        "fx": "fx_linux_{arch.deb}",
        "dasel": "dasel_linux_{arch.deb}",
    }
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    for tool_id, asset in expected_linux_asset.items():
        method = resolve_methods(tools[tool_id], linux)[0]
        assert method.params.get("raw") is True
        assert "strip" not in method.params
        assert method.params["asset"] == asset


def test_tealdeer_cmd_is_tldr_with_per_os_naming() -> None:
    tealdeer = next(t for t in load_tools(REGISTRY) if t.id == "tealdeer")
    assert tealdeer.cmd == "tldr"
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    assert resolve_methods(tealdeer, macos)[0].params["asset"] == "tealdeer-macos-{arch.machine}"


def test_gron_uses_tgz_with_trailing_version() -> None:
    gron = next(t for t in load_tools(REGISTRY) if t.id == "gron")
    linux = Platform(os="debian", arch="arm64", immutable=False, has_brew=True)
    method = resolve_methods(gron, linux)[0]
    assert method.params["asset"] == "gron-linux-{arch.deb}-{ver}.tgz"
    assert method.params["strip"] == 0


def test_registry_has_forty_seven_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    cmds = [t.cmd for t in tools]
    assert len(ids) == 47
    assert len(ids) == len(set(ids))
    assert len(cmds) == len(set(cmds))


def test_gitui_is_linux_download_and_brew_only_on_macos() -> None:
    gitui = next(t for t in load_tools(REGISTRY) if t.id == "gitui")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(gitui, linux)] == ["github_release", "brew"]
    assert [m.kind for m in resolve_methods(gitui, macos)] == ["brew"]


def test_miller_cmd_is_mlr_and_strips_nested_member() -> None:
    miller = next(t for t in load_tools(REGISTRY) if t.id == "miller")
    assert miller.cmd == "mlr"
    linux = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    method = resolve_methods(miller, linux)[0]
    assert method.params["member"] == "mlr"
    assert method.params["strip"] == 1


def test_hexyl_linux_uses_gnu_and_strips() -> None:
    hexyl = next(t for t in load_tools(REGISTRY) if t.id == "hexyl")
    linux = Platform(os="arch", arch="arm64", immutable=False, has_brew=True)
    method = resolve_methods(hexyl, linux)[0]
    assert method.params["asset"] == "hexyl-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
    assert method.params["strip"] == 1


def test_zip_runtime_and_tools_resolve_with_archive_zip() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    expected = {
        "deno": (
            "deno-{arch.machine}-unknown-linux-gnu.zip",
            "deno-{arch.machine}-apple-darwin.zip",
            "deno",
        ),
        "procs": (
            "procs-v{ver}-{arch.machine}-linux.zip",
            "procs-v{ver}-{arch.machine}-mac.zip",
            "procs",
        ),
        "ast-grep": (
            "app-{arch.machine}-unknown-linux-gnu.zip",
            "app-{arch.machine}-apple-darwin.zip",
            "ast-grep",
        ),
        "jless": (
            "jless-v{ver}-{arch.machine}-unknown-linux-gnu.zip",
            "jless-v{ver}-{arch.machine}-apple-darwin.zip",
            "jless",
        ),
    }
    for tool_id, (linux_asset, macos_asset, member) in expected.items():
        lin = resolve_methods(tools[tool_id], linux)
        mac = resolve_methods(tools[tool_id], macos)
        assert [m.kind for m in lin] == ["github_release", "brew"], tool_id
        assert [m.kind for m in mac] == ["github_release", "brew"], tool_id
        assert lin[0].params["archive"] == "zip", tool_id
        assert lin[0].params["asset"] == linux_asset, tool_id
        assert mac[0].params["asset"] == macos_asset, tool_id
        assert lin[0].params["member"] == member, tool_id
        assert "strip" not in lin[0].params, tool_id  # zip ignores strip


def test_ast_grep_cmd_is_ast_grep_not_sg() -> None:
    ast = next(t for t in load_tools(REGISTRY) if t.id == "ast-grep")
    assert ast.cmd == "ast-grep"  # the bundled `sg` alias collides with the system tool


def test_runtime_category_members() -> None:
    runtimes = sorted(t.id for t in load_tools(REGISTRY) if t.category == "runtime")
    assert runtimes == ["bun", "deno", "fnm"]


def test_script_installer_tier_resolves_script_then_brew() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)

    # bun: one script method (no os filter) applies on both platforms, then brew.
    for platform in (linux, macos):
        bun = resolve_methods(tools["bun"], platform)
        assert [m.kind for m in bun] == ["script", "brew"]
        assert bun[0].params["url"] == "https://bun.sh/install"
        assert bun[0].params["shell"] == "bash"
        assert bun[0].params["bin_dir"] == "~/.bun/bin"

    # pnpm: per-OS bin_dir (PNPM_HOME differs by platform), then brew.
    pnpm_linux = resolve_methods(tools["pnpm"], linux)
    pnpm_macos = resolve_methods(tools["pnpm"], macos)
    assert [m.kind for m in pnpm_linux] == ["script", "brew"]
    assert [m.kind for m in pnpm_macos] == ["script", "brew"]
    assert pnpm_linux[0].params["url"] == "https://get.pnpm.io/install.sh"
    assert pnpm_linux[0].params["shell"] == "sh"
    assert pnpm_linux[0].params["bin_dir"] == "~/.local/share/pnpm"
    assert pnpm_macos[0].params["bin_dir"] == "~/Library/pnpm"

    # fnm: script on Linux, brew-only on macOS (its installer brew-delegates there).
    fnm_linux = resolve_methods(tools["fnm"], linux)
    assert [m.kind for m in fnm_linux] == ["script", "brew"]
    assert fnm_linux[0].params["url"] == "https://fnm.vercel.app/install"
    assert fnm_linux[0].params["shell"] == "bash"
    assert fnm_linux[0].params["bin_dir"] == "~/.local/share/fnm"
    assert [m.kind for m in resolve_methods(tools["fnm"], macos)] == ["brew"]


def test_broot_is_selective_zip_with_nested_member() -> None:
    broot = next(t for t in load_tools(REGISTRY) if t.id == "broot")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    lin = resolve_methods(broot, linux)
    assert [m.kind for m in lin] == ["github_release", "brew"]
    assert lin[0].params["asset"] == "broot_{ver}.zip"
    assert lin[0].params["archive"] == "zip"
    assert lin[0].params["member"] == "{arch.machine}-unknown-linux-gnu/broot"
    mac = resolve_methods(broot, macos)
    assert mac[0].params["member"] == "{arch.machine}-apple-darwin/broot"


def test_gitleaks_and_vale_use_new_arch_tokens() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)

    gl_linux = resolve_methods(tools["gitleaks"], linux)
    assert [m.kind for m in gl_linux] == ["github_release", "brew"]
    assert gl_linux[0].params["asset"] == "gitleaks_{ver}_linux_{arch.x64}.tar.gz"
    assert gl_linux[0].params["member"] == "gitleaks"
    assert resolve_methods(tools["gitleaks"], macos)[0].params["asset"] == (
        "gitleaks_{ver}_darwin_{arch.x64}.tar.gz"
    )

    vale_linux = resolve_methods(tools["vale"], linux)
    assert [m.kind for m in vale_linux] == ["github_release", "brew"]
    assert vale_linux[0].params["asset"] == "vale_{ver}_Linux_{arch.bits}.tar.gz"
    assert resolve_methods(tools["vale"], macos)[0].params["asset"] == (
        "vale_{ver}_macOS_{arch.bits}.tar.gz"
    )
