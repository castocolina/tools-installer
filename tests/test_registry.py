from pathlib import Path

from installer.deps import requires_integrity_errors
from installer.model import Tool, load_categories, load_tools
from installer.platform import Platform
from installer.resolve import resolve_methods

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _tools_by_id() -> dict[str, Tool]:
    return {tool.id: tool for tool in load_tools(REGISTRY)}


def _ids_by_priority(priority: str) -> set[str]:
    return {tool.id for tool in load_tools(REGISTRY) if tool.priority == priority}


def test_registry_loads():
    tools = load_tools(REGISTRY)
    assert tools, "registry should declare at least one tool"


def test_registry_ids_unique():
    ids = [t.id for t in load_tools(REGISTRY)]
    assert len(ids) == len(set(ids))


def test_every_tool_has_at_least_one_method():
    assert all(t.methods for t in load_tools(REGISTRY))


def test_registry_includes_requested_installable_entries() -> None:
    ids = set(_tools_by_id())
    assert {
        "brew",
        "git",
        "codex",
        "claude",
        "opencode",
        "docker",
        "watch",
        "podman",
        "colima",
        "vscode",
        "jetbrains-toolbox",
        "sdkman",
        "java",
        "groovy",
        "springbootcli",
        "gradle",
        "maven",
    } <= ids


def test_human_agent_clis_are_p0_human_tools() -> None:
    tools = _tools_by_id()
    for tool_id in ("codex", "claude", "opencode"):
        tool = tools[tool_id]
        assert tool.priority == "P0"
        assert tool.audience == "human"
        assert tool.category == "ai"


def test_high_use_agent_utilities_are_p0() -> None:
    assert {
        "rg",
        "jq",
        "fd",
        "sd",
        "eza",
        "bat",
        "yq",
        "gh",
        "git",
    } <= _ids_by_priority("P0")


def test_priority_tool_descriptions_name_replacements_or_value() -> None:
    tools = _tools_by_id()
    expected_fragments = {
        "rg": ("grep", ".gitignore"),
        "fd": ("find", ".gitignore"),
        "sd": ("sed", "literal"),
        "eza": ("ls", "Git"),
        "bat": ("cat", "syntax"),
        "yq": ("YAML", "JSON"),
        "jq": ("JSON", "filters"),
        "git": ("version control", "agents"),
        "brew": ("Homebrew", "immutable Linux"),
    }
    for tool_id, fragments in expected_fragments.items():
        desc = tools[tool_id].desc
        for fragment in fragments:
            assert fragment in desc, f"{tool_id}: missing {fragment!r} in {desc!r}"
        assert len(desc) <= 150, f"{tool_id}: description is too long"


def test_java_tools_depend_on_sdkman() -> None:
    tools = _tools_by_id()
    for tool_id in ("java", "groovy", "springbootcli", "gradle", "maven"):
        assert "sdkman" in tools[tool_id].requires


def test_sdkman_uses_init_script_and_declares_bin_dir() -> None:
    sdkman = _tools_by_id()["sdkman"]
    assert sdkman.cmd == "sdkman-init.sh"
    assert "shell function" in sdkman.desc
    assert "sourcing" in sdkman.desc
    assert [m.kind for m in sdkman.methods] == ["script"]
    assert sdkman.methods[0].params["url"] == "https://get.sdkman.io?ci=true"
    assert sdkman.methods[0].params["bin_dir"] == "~/.sdkman/bin"


def test_agent_clis_use_supported_install_methods() -> None:
    tools = _tools_by_id()
    codex = tools["codex"]
    claude = tools["claude"]
    opencode = tools["opencode"]

    assert [m.kind for m in codex.methods] == ["script", "cask"]
    assert next(m for m in codex.methods if m.kind == "script").params["url"] == (
        "https://chatgpt.com/codex/install.sh"
    )
    assert next(m for m in codex.methods if m.kind == "cask").params["cask"] == "codex"

    assert [m.kind for m in claude.methods] == ["script", "cask"]
    assert next(m for m in claude.methods if m.kind == "script").params["url"] == (
        "https://claude.ai/install.sh"
    )
    assert next(m for m in claude.methods if m.kind == "cask").params["cask"] == "claude-code"

    assert [m.kind for m in opencode.methods] == ["script", "pacman", "brew"]
    assert next(m for m in opencode.methods if m.kind == "script").params["url"] == (
        "https://opencode.ai/install"
    )


def test_container_tools_resolve_on_immutable_linux_without_native_writes() -> None:
    tools = _tools_by_id()
    immutable_fedora = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)

    assert [m.kind for m in resolve_methods(tools["docker"], immutable_fedora)] == ["brew"]
    assert [m.kind for m in resolve_methods(tools["podman"], immutable_fedora)] == ["brew"]
    assert [m.kind for m in resolve_methods(tools["colima"], immutable_fedora)] == ["brew"]


def test_watch_is_generic_shell_tool_required_by_docker_aliases() -> None:
    watch = _tools_by_id()["watch"]
    assert watch.category == "shell"
    assert watch.cmd == "watch"
    assert watch.priority == "P1"
    assert "Docker shortcuts policy" in watch.desc
    methods = {method.kind: method.params for method in watch.methods}
    assert methods["dnf"]["package"] == "procps-ng"
    assert methods["apt"]["package"] == "procps"
    assert methods["pacman"]["package"] == "procps-ng"
    assert methods["brew"]["formula"] == "watch"


def test_watch_resolves_on_immutable_linux_through_brew() -> None:
    watch = _tools_by_id()["watch"]
    immutable_fedora = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    assert [m.kind for m in resolve_methods(watch, immutable_fedora)] == ["brew"]


def test_jetbrains_toolbox_is_macos_cask_only() -> None:
    tools = _tools_by_id()
    toolbox = tools["jetbrains-toolbox"]
    assert toolbox.cmd == "jetbrains-toolbox"
    assert toolbox.category == "editor"
    assert [m.kind for m in toolbox.methods] == ["cask"]
    assert toolbox.methods[0].params["cask"] == "jetbrains-toolbox"
    assert toolbox.methods[0].params["app"] == "JetBrains Toolbox.app"


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


# GUI apps with no Linux install method yet (VS Code tar.gz / Sublime tarball
# are a future batch). Every other tool must resolve on every platform.
MACOS_ONLY = {"vscode", "sublime", "jetbrains-toolbox"}


def test_every_tool_resolves_at_least_one_method_on_each_platform() -> None:
    # A tool that resolves to nothing on a supported platform is silently
    # uninstallable there; this guards against an os/method misconfiguration.
    tools = load_tools(REGISTRY)
    for platform_os in ("debian", "arch", "fedora", "macos"):
        for arch in ("amd64", "arm64"):
            platform = Platform(os=platform_os, arch=arch, immutable=False, has_brew=True)
            allowed: set[str] = MACOS_ONLY if platform_os != "macos" else set()
            stranded = [
                t.id for t in tools if not resolve_methods(t, platform) and t.id not in allowed
            ]
            assert not stranded, f"no install method on {platform_os}/{arch}: {stranded}"


def test_macos_only_allowlist_stays_honest() -> None:
    # If a Linux method is ever added to one of these, it must leave the allowlist.
    tools = {t.id: t for t in load_tools(REGISTRY)}
    for tool_id in sorted(MACOS_ONLY):
        assert tool_id in tools, f"MACOS_ONLY entry '{tool_id}' is not in the registry"
        for platform_os in ("debian", "arch", "fedora"):
            platform = Platform(os=platform_os, arch="amd64", immutable=False, has_brew=True)
            assert resolve_methods(tools[tool_id], platform) == [], (
                f"'{tool_id}' unexpectedly resolves on {platform_os}"
            )


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


def test_registry_has_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    cmds = [t.cmd for t in tools]
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
    assert runtimes == [
        "bun",
        "deno",
        "fnm",
        "gradle",
        "groovy",
        "java",
        "maven",
        "sdkman",
        "springbootcli",
    ]


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


def test_checksum_param_only_on_github_release_methods() -> None:
    for tool in load_tools(REGISTRY):
        for method in tool.methods:
            if "checksum" in method.params:
                assert method.kind == "github_release", tool.id


SIDECAR_VERIFIED = {"rg", "starship", "ruff", "deno", "tealdeer"}


def test_sidecar_verified_tools_declare_checksums() -> None:
    for tool in load_tools(REGISTRY):
        if tool.id not in SIDECAR_VERIFIED:
            continue
        gh_methods = [m for m in tool.methods if m.kind == "github_release"]
        assert gh_methods, tool.id
        for method in gh_methods:
            assert "checksum" in method.params, f"{tool.id}: missing checksum param"
            assert "{asset}" in str(method.params["checksum"]), tool.id


CHECKSUM_FILE_VERIFIED = {
    "fzf",
    "lazygit",
    "gh",
    "just",
    "gum",
    "glow",
    "lazydocker",
    "dive",
    "miller",
    "gitleaks",
    "vale",
    "duf",
}


def test_checksum_file_verified_tools_declare_checksums() -> None:
    for tool in load_tools(REGISTRY):
        if tool.id not in CHECKSUM_FILE_VERIFIED:
            continue
        gh_methods = [m for m in tool.methods if m.kind == "github_release"]
        assert gh_methods, tool.id
        for method in gh_methods:
            assert "checksum" in method.params, f"{tool.id}: missing checksum param"


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


def test_vscode_is_arch_split_app_with_cask_fallback() -> None:
    vscode = next(t for t in load_tools(REGISTRY) if t.id == "vscode")
    assert vscode.cmd == "code"
    assert vscode.category == "editor"
    arm = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    intel = Platform(os="macos", arch="amd64", immutable=False, has_brew=True)
    arm_methods = resolve_methods(vscode, arm)
    assert [m.kind for m in arm_methods] == ["app", "cask"]
    assert (
        arm_methods[0].params["url"]
        == "https://update.code.visualstudio.com/latest/darwin-arm64/stable"
    )
    assert arm_methods[0].params["app"] == "Visual Studio Code.app"
    assert arm_methods[0].params["cli"] == "Contents/Resources/app/bin/code"
    assert arm_methods[1].params["cask"] == "visual-studio-code"
    intel_methods = resolve_methods(vscode, intel)
    assert [m.kind for m in intel_methods] == ["app", "cask"]
    assert (
        intel_methods[0].params["url"]
        == "https://update.code.visualstudio.com/latest/darwin/stable"
    )


def test_sublime_is_single_universal_app_with_cask_fallback() -> None:
    sublime = next(t for t in load_tools(REGISTRY) if t.id == "sublime")
    assert sublime.cmd == "subl"
    assert sublime.category == "editor"
    for arch in ("arm64", "amd64"):  # one universal zip serves both
        mac = Platform(os="macos", arch=arch, immutable=False, has_brew=True)
        methods = resolve_methods(sublime, mac)
        assert [m.kind for m in methods] == ["app", "cask"]
        assert (
            methods[0].params["url"]
            == "https://download.sublimetext.com/sublime_text_build_4200_mac.zip"
        )
        assert methods[0].params["app"] == "Sublime Text.app"
        assert methods[0].params["cli"] == "Contents/SharedSupport/bin/subl"
        assert methods[1].params["cask"] == "sublime-text"


def test_every_used_category_has_a_blurb() -> None:
    blurbs = load_categories(REGISTRY)
    used = {t.category for t in load_tools(REGISTRY)}
    missing = sorted(used - set(blurbs))
    assert not missing, f"categories without a [[category]] blurb: {missing}"


def test_every_category_blurb_is_used_by_a_tool() -> None:
    blurbs = load_categories(REGISTRY)
    used = {t.category for t in load_tools(REGISTRY)}
    orphans = sorted(set(blurbs) - used)
    assert not orphans, f"[[category]] blurbs with no tools: {orphans}"


def test_shipped_registry_requires_all_resolve() -> None:
    tools = load_tools(REGISTRY)
    assert requires_integrity_errors(tools) == []


def test_shipped_node_tools_require_pnpm() -> None:
    tools = load_tools(REGISTRY)
    for tool in tools:
        if any(m.kind == "node" for m in tool.methods):
            assert "pnpm" in tool.requires, f"{tool.id}: node tool must require pnpm"
