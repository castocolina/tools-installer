from collections import Counter
from pathlib import Path
from typing import cast

from installer.deps import requires_integrity_errors, resolve_dependencies
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
        "volta",
        "codegraph",
        "graphify",
        "rtk",
        "cursor-agent",
        "antigravity",
        "zsh",
        "oh-my-zsh",
    } <= ids


def test_human_agent_clis_are_p0_human_tools() -> None:
    tools = _tools_by_id()
    for tool_id in ("codex", "claude", "opencode", "cursor-agent"):
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
    # sdkman-init.sh is sourced, not executed — it never carries the execute
    # bit, so `which` can never find it; detect_path is the fallback marker.
    assert sdkman.methods[0].params["detect_path"] == "~/.sdkman/bin/sdkman-init.sh"


def test_java_tools_install_exclusively_through_sdkman() -> None:
    # brew is preferred generally, but Java-toolchain tools must go through
    # SDKMAN specifically, never a native/brew package — no fallback method.
    tools = _tools_by_id()
    expected_candidates = {
        "java": "java",
        "groovy": "groovy",
        "springbootcli": "springboot",
        "gradle": "gradle",
        "maven": "maven",
    }
    for tool_id, candidate in expected_candidates.items():
        tool = tools[tool_id]
        assert [m.kind for m in tool.methods] == ["sdkman"], (
            f"{tool_id}: must install exclusively through sdkman"
        )
        method = tool.methods[0]
        assert method.params["candidate"] == candidate
        assert method.params["bin_dir"] == f"~/.sdkman/candidates/{candidate}/current/bin"


def test_java_and_sdkman_entries_record_the_sc2_no_pin_verification() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "sdkman_auto_answer" in text
    assert "Tier-3 container" in text
    assert "$CURRENT" in text
    assert "no vendor prompt" in text
    assert "SC#2" in text

    lines = text.splitlines()
    sdkman_idx = next(i for i, line in enumerate(lines) if line == 'id = "sdkman"')
    java_idx = next(i for i, line in enumerate(lines) if line == 'id = "java"')
    window = 30
    sdkman_window = "\n".join(lines[max(0, sdkman_idx - window) : sdkman_idx])
    java_window = "\n".join(lines[max(0, java_idx - window) : java_idx])
    assert "sdkman_auto_answer" in sdkman_window
    assert "Tier-3 container" in sdkman_window
    assert "$CURRENT" in java_window
    assert "no vendor prompt" in java_window
    assert "SC#2" in java_window
    assert "Tier-3 container" in java_window


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

    cursor_agent = tools["cursor-agent"]
    assert [m.kind for m in cursor_agent.methods] == ["script"]
    assert next(m for m in cursor_agent.methods if m.kind == "script").params["url"] == (
        "https://cursor.com/install"
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


def test_volta_resolves_to_script_on_linux_and_brew_on_macos() -> None:
    volta = next(t for t in load_tools(REGISTRY) if t.id == "volta")
    assert volta.tier == "system"
    assert volta.category == "pkg-mgr"
    assert volta.cmd == "volta"
    assert volta.audience == "both"
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(volta, macos)][0] == "brew"
    for platform_os in ("debian", "arch", "fedora"):
        linux = Platform(os=platform_os, arch="amd64", immutable=False, has_brew=True)
        assert [m.kind for m in resolve_methods(volta, linux)][0] == "script"
    assert all(m.params.get("bin_dir") == "~/.volta/bin" for m in volta.methods)


def test_volta_entry_records_the_npm_postinstall_finding() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "run_global_install" in text


def test_mmdc_entry_records_the_brew_rejection_finding() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "1122" in text
    assert "peerDependency" in text


def test_puppeteer_entry_records_the_postinstall_and_arm64_caveats() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "install.mjs" in text
    assert "Linux arm64" in text
    assert "PUPPETEER_EXECUTABLE_PATH" in text


def test_mmdc_entry_records_the_brownfield_gap_and_group_coupling() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "Brownfield" in text
    assert "Doctor group detection:" in text
    assert "pnpm remove -g" in text
    # The comment must name BOTH brownfield shapes. Naming only the split one
    # told a future maintainer that `r` repairs a machine it left untouched —
    # the pre-phase-5 machine, which has no global puppeteer to put back.
    assert "SPLIT:" in text
    assert "INCOMPLETE:" in text


def test_puppeteer_entry_records_the_double_install_disposition() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "Installed twice" in text


def test_puppeteer_entry_states_the_persistent_grant_accurately() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "always be allowed to run its scripts" in text
    assert "bounds the pre-authorised" not in text
    assert "bounded only by the" not in text


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


def test_codegraph_github_release_is_os_split_checksum_verified_and_nested() -> None:
    codegraph = next(t for t in load_tools(REGISTRY) if t.id == "codegraph")
    assert (
        codegraph.name,
        codegraph.category,
        codegraph.cmd,
        codegraph.priority,
        codegraph.audience,
        codegraph.tier,
    ) == ("CodeGraph", "dev", "codegraph", "P1", "ai", "ai")
    assert requires_integrity_errors(load_tools(REGISTRY)) == []
    assert all(
        m.params["repo"] == "colbymchenry/codegraph"
        and m.params["checksum"] == "SHA256SUMS"
        and m.params["member"] == "bin/codegraph"
        and m.params["strip"] == 1
        for m in codegraph.methods
    )
    for arch in ("amd64", "arm64"):
        macos = Platform(os="macos", arch=arch, immutable=False, has_brew=True)
        methods = resolve_methods(codegraph, macos)
        assert len(methods) == 1
        assert methods[0].params["asset"] == "codegraph-darwin-{arch.x64}.tar.gz"
        macos_no_brew = Platform(os="macos", arch=arch, immutable=False, has_brew=False)
        assert len(resolve_methods(codegraph, macos_no_brew)) == 1
    for platform_os in ("debian", "arch", "fedora"):
        for arch in ("amd64", "arm64"):
            linux = Platform(os=platform_os, arch=arch, immutable=False, has_brew=True)
            methods = resolve_methods(codegraph, linux)
            assert len(methods) == 1
            assert methods[0].params["asset"] == "codegraph-linux-{arch.x64}.tar.gz"
            immutable = Platform(os=platform_os, arch=arch, immutable=True, has_brew=False)
            assert len(resolve_methods(codegraph, immutable)) == 1


def test_codegraph_methods_are_github_release_only() -> None:
    codegraph = next(t for t in load_tools(REGISTRY) if t.id == "codegraph")
    assert {m.kind for m in codegraph.methods} == {"github_release"}


def test_codegraph_entry_records_the_no_brew_formula_finding() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "colbymchenry/codegraph" in text
    assert "v1.6.0" in text


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
MACOS_ONLY = {"vscode", "sublime", "jetbrains-toolbox", "gnu-bash"}
# Apple Containers: Homebrew itself requires macos>=26 and arch=arm64. Membership
# means the tool cannot work on that platform+arch, not that packaging is inconvenient.
MACOS_ARM64_ONLY = {"container"}
# Membership means the tool provably cannot work on that platform+arch, not
# that its packaging is inconvenient there.
NO_LINUX_ARM64 = {"puppeteer"}
# wezterm: Arch arm64 IS covered (its pacman method declares no arch list),
# but Debian/Fedora arm64 have no path — this session's live check of
# api.github.com/repos/wezterm/wezterm/releases/latest found only .deb arm64
# variants, no arm64 AppImage. A gap bounded by upstream asset availability,
# not a project scoping choice.
NO_DEBIAN_FEDORA_ARM64 = {"wezterm"}


def test_every_tool_resolves_at_least_one_method_on_each_platform() -> None:
    # A tool that resolves to nothing on a supported platform is silently
    # uninstallable there; this guards against an os/method misconfiguration.
    # macOS fixtures carry a current-enough os_version so a min_os_version gate
    # is evaluated on a capable Darwin, not fail-closed against os_version=None.
    tools = load_tools(REGISTRY)
    for platform_os in ("debian", "arch", "fedora", "macos"):
        for arch in ("amd64", "arm64"):
            platform = Platform(
                os=platform_os,
                arch=arch,
                immutable=False,
                has_brew=True,
                os_version="26.0" if platform_os == "macos" else None,
            )
            allowed: set[str] = set()
            if platform_os != "macos":
                allowed |= MACOS_ONLY
                allowed |= MACOS_ARM64_ONLY
            if platform_os == "macos" and arch != "arm64":
                allowed |= MACOS_ARM64_ONLY
            if platform_os != "macos" and arch == "arm64":
                allowed |= NO_LINUX_ARM64
            if platform_os in ("debian", "fedora") and arch == "arm64":
                allowed |= NO_DEBIAN_FEDORA_ARM64
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


def test_macos_arm64_only_allowlist_stays_honest() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    for tool_id in sorted(MACOS_ARM64_ONLY):
        assert tool_id in tools, f"MACOS_ARM64_ONLY entry '{tool_id}' is not in the registry"
        intel = Platform(
            os="macos", arch="amd64", immutable=False, has_brew=True, os_version="26.0"
        )
        assert resolve_methods(tools[tool_id], intel) == [], (
            f"'{tool_id}' unexpectedly resolves on macos/amd64"
        )
        arm = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")
        assert resolve_methods(tools[tool_id], arm), (
            f"'{tool_id}' must still resolve on macos/arm64"
        )


def test_no_linux_arm64_allowlist_stays_honest() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    for tool_id in sorted(NO_LINUX_ARM64):
        assert tool_id in tools, f"NO_LINUX_ARM64 entry '{tool_id}' is not in the registry"
        for platform_os in ("debian", "arch", "fedora"):
            platform = Platform(os=platform_os, arch="arm64", immutable=False, has_brew=True)
            assert resolve_methods(tools[tool_id], platform) == [], (
                f"'{tool_id}' unexpectedly resolves on {platform_os}/arm64"
            )
        debian_amd64 = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
        macos_arm64 = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
        assert resolve_methods(tools[tool_id], debian_amd64), (
            f"'{tool_id}' must still resolve on debian/amd64"
        )
        assert resolve_methods(tools[tool_id], macos_arm64), (
            f"'{tool_id}' must still resolve on macos/arm64"
        )


def test_no_debian_fedora_arm64_allowlist_stays_honest() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    for tool_id in sorted(NO_DEBIAN_FEDORA_ARM64):
        assert tool_id in tools, f"NO_DEBIAN_FEDORA_ARM64 entry '{tool_id}' is not in the registry"
        for platform_os in ("debian", "fedora"):
            platform = Platform(os=platform_os, arch="arm64", immutable=False, has_brew=True)
            assert resolve_methods(tools[tool_id], platform) == [], (
                f"'{tool_id}' unexpectedly resolves on {platform_os}/arm64"
            )
        arch_arm64 = Platform(os="arch", arch="arm64", immutable=False, has_brew=True)
        assert resolve_methods(tools[tool_id], arch_arm64), (
            f"'{tool_id}' must still resolve on arch/arm64"
        )


def test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm() -> None:
    puppeteer = next(t for t in load_tools(REGISTRY) if t.id == "puppeteer")
    assert (
        puppeteer.name,
        puppeteer.category,
        puppeteer.cmd,
        puppeteer.priority,
        puppeteer.audience,
        puppeteer.tier,
    ) == ("Puppeteer", "dev", "puppeteer", "P3", "both", "user")
    assert puppeteer.requires == ("pnpm",)
    assert puppeteer.recommends == ()
    assert len(puppeteer.methods) == 2
    assert {m.kind for m in puppeteer.methods} == {"node"}
    for method in puppeteer.methods:
        assert method.params["npm_pkg"] == "puppeteer"
        assert method.params["allow_build"] == ["puppeteer"]
        assert method.params["versions"] == {"puppeteer": "^25"}
        assert method.params["min_node"] == "22.12.0"
        assert method.params["smoke"] == "puppeteer-browser"
        assert "co_install" not in method.params
    macos = next(m for m in puppeteer.methods if m.os == ("macos",))
    assert macos.arch == ()
    linux = next(m for m in puppeteer.methods if m.os == ("debian", "arch", "fedora"))
    assert linux.arch == ("amd64",)
    for arch in ("amd64", "arm64"):
        macos_plat = Platform(os="macos", arch=arch, immutable=False, has_brew=True)
        assert len(resolve_methods(puppeteer, macos_plat)) == 1
    for platform_os in ("debian", "arch", "fedora"):
        linux_amd64 = Platform(os=platform_os, arch="amd64", immutable=False, has_brew=True)
        assert len(resolve_methods(puppeteer, linux_amd64)) == 1


def test_puppeteer_resolves_no_method_on_linux_arm64_because_chrome_has_no_binary() -> None:
    puppeteer = next(t for t in load_tools(REGISTRY) if t.id == "puppeteer")
    for platform_os in ("debian", "arch", "fedora"):
        platform = Platform(os=platform_os, arch="arm64", immutable=False, has_brew=False)
        assert resolve_methods(puppeteer, platform) == []


def test_mmdc_skips_on_linux_arm64_when_puppeteer_is_unavailable() -> None:
    catalog = load_tools(REGISTRY)
    by_id = {tool.id: tool for tool in catalog}
    platform = Platform(os="debian", arch="arm64", immutable=False, has_brew=False)
    result = resolve_dependencies(
        [by_id["mmdc"]],
        catalog,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=lambda _tool: False,
    )
    ids = [tool.id for tool in result.order]
    assert "mmdc" not in ids
    assert "puppeteer" not in ids
    assert result.warnings
    assert any("unavailable" in warning for warning in result.warnings)


def test_selecting_mmdc_drags_in_pnpm_and_puppeteer_on_linux_amd64() -> None:
    catalog = load_tools(REGISTRY)
    by_id = {tool.id: tool for tool in catalog}
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    result = resolve_dependencies(
        [by_id["mmdc"]],
        catalog,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=lambda _tool: False,
    )
    ids = [tool.id for tool in result.order]
    assert ids.index("pnpm") < ids.index("puppeteer") < ids.index("mmdc")
    assert "puppeteer" in result.dragged_in
    assert "pnpm" in result.dragged_in


def test_graphify_uses_the_uv_tool_executor_and_requires_uv() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    graphify = tools["graphify"]
    assert graphify.name == "Graphify"
    assert graphify.category == "dev"
    assert graphify.cmd == "graphify"
    assert graphify.priority == "P1"
    assert graphify.audience == "ai"
    assert graphify.tier == "ai"
    assert graphify.requires == ("uv",)
    assert graphify.recommends == ()
    assert len(graphify.methods) == 1
    assert graphify.methods[0].kind == "uv-tool"
    assert graphify.methods[0].params["pypi_pkg"] == "graphifyy"


def test_selecting_graphify_drags_in_uv() -> None:
    catalog = load_tools(REGISTRY)
    by_id = {tool.id: tool for tool in catalog}
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    result = resolve_dependencies(
        [by_id["graphify"]],
        catalog,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=lambda _tool: False,
    )
    ids = [tool.id for tool in result.order]
    assert ids.index("uv") < ids.index("graphify")
    assert "uv" in result.dragged_in


def test_graphify_entry_records_the_legitimacy_gate_evidence() -> None:
    text = REGISTRY.read_text()
    idx = text.index('id = "graphify"')
    window = text[max(0, idx - 1500) : idx]
    for needle in ("graphifyy", "uv tool install", "too-new", "Graphify-Labs/graphify"):
        assert needle in window, f"missing {needle!r} in graphify's comment"


def test_cursor_agent_uses_the_legacy_collision_safe_cmd_name() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    cursor_agent = tools["cursor-agent"]
    assert cursor_agent.name == "Cursor Agent CLI"
    assert cursor_agent.category == "ai"
    assert cursor_agent.cmd == "cursor-agent"
    assert cursor_agent.cmd != "agent"
    assert cursor_agent.priority == "P0"
    assert cursor_agent.audience == "human"
    assert cursor_agent.tier == "ai"
    assert cursor_agent.recommends == ("codegraph", "graphify", "rtk")
    assert len(cursor_agent.methods) == 1
    assert cursor_agent.methods[0].kind == "script"
    assert cursor_agent.methods[0].params["url"] == "https://cursor.com/install"
    assert cursor_agent.methods[0].params["shell"] == "bash"


def test_antigravity_installs_via_official_script_with_no_recommends() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    antigravity = tools["antigravity"]
    assert antigravity.name == "Antigravity CLI"
    assert antigravity.category == "ai"
    assert antigravity.cmd == "agy"
    assert antigravity.priority == "P1"
    assert antigravity.audience == "human"
    assert antigravity.tier == "ai"
    assert antigravity.recommends == ()
    assert len(antigravity.methods) == 1
    assert antigravity.methods[0].kind == "script"
    assert antigravity.methods[0].params["url"] == "https://antigravity.google/cli/install.sh"
    assert antigravity.methods[0].params["shell"] == "bash"


def test_cursor_agent_and_antigravity_scripts_resolve_on_every_platform() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    for tool_id in ("cursor-agent", "antigravity"):
        tool = tools[tool_id]
        for os_name in ("macos", "debian", "arch", "fedora"):
            for arch in ("amd64", "arm64"):
                platform = Platform(os=os_name, arch=arch, immutable=False, has_brew=False)
                assert [m.kind for m in resolve_methods(tool, platform)] == ["script"]


def test_cursor_agent_and_antigravity_entries_record_the_verification_findings() -> None:
    text = REGISTRY.read_text()
    idx_ca = text.index('id = "cursor-agent"')
    window_ca = text[max(0, idx_ca - 1500) : idx_ca]
    for needle in ("cursor.com/install", "agent", "legacy", "cask"):
        assert needle in window_ca, f"missing {needle!r} in cursor-agent's comment"

    idx_ag = text.index('id = "antigravity"')
    window_ag = text[max(0, idx_ag - 1500) : idx_ag]
    for needle in ("agy", "SHA-512", "cask", "D-01"):
        assert needle in window_ag, f"missing {needle!r} in antigravity's comment"


def test_rtk_installs_via_checksum_verified_github_release_with_brew_fallback() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    rtk = tools["rtk"]
    assert rtk.name == "RTK (Rust Token Killer)"
    assert rtk.category == "dev"
    assert rtk.cmd == "rtk"
    assert rtk.priority == "P1"
    assert rtk.audience == "ai"
    assert rtk.tier == "ai"
    assert rtk.recommends == ()
    kinds = [m.kind for m in rtk.methods]
    assert kinds == ["github_release", "github_release", "github_release", "brew"]
    for method in rtk.methods:
        if method.kind == "github_release":
            assert method.params["repo"] == "rtk-ai/rtk"
            assert method.params["checksum"] == "checksums.txt"
            assert method.params["member"] == "rtk"
            assert method.params["strip"] == 0
    brew_method = next(m for m in rtk.methods if m.kind == "brew")
    assert brew_method.params["formula"] == "rtk"
    assert brew_method.os == ()


def test_rtk_linux_methods_are_arch_gated_by_the_real_musl_gnu_asset_split() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    rtk = tools["rtk"]
    for os_name in ("debian", "arch", "fedora"):
        amd64 = Platform(os=os_name, arch="amd64", immutable=False, has_brew=True)
        amd64_resolved = resolve_methods(rtk, amd64)
        assert [m.kind for m in amd64_resolved] == ["github_release", "brew"]
        assert amd64_resolved[0].params["asset"] == "rtk-{arch.machine}-unknown-linux-musl.tar.gz"

        arm64 = Platform(os=os_name, arch="arm64", immutable=False, has_brew=True)
        arm64_resolved = resolve_methods(rtk, arm64)
        assert [m.kind for m in arm64_resolved] == ["github_release", "brew"]
        assert arm64_resolved[0].params["asset"] == "rtk-{arch.machine}-unknown-linux-gnu.tar.gz"


def test_rtk_macos_method_is_arch_unrestricted() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    rtk = tools["rtk"]
    for arch in ("amd64", "arm64"):
        platform = Platform(os="macos", arch=arch, immutable=False, has_brew=True)
        assert [m.kind for m in resolve_methods(rtk, platform)] == ["github_release", "brew"]


def test_rtk_resolves_via_download_and_brew_even_on_immutable_linux() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    rtk = tools["rtk"]
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    assert [m.kind for m in resolve_methods(rtk, platform)] == ["github_release", "brew"]


def test_rtk_entry_records_the_musl_gnu_split_and_brew_confirmation() -> None:
    text = REGISTRY.read_text()
    idx = text.index('id = "rtk"')
    window = text[max(0, idx - 2000) : idx]
    for needle in ("checksums.txt", "musl", "gnu", "develop", "formulae.brew.sh", "0.48.0"):
        assert needle in window, f"missing {needle!r} in rtk's comment"


def test_no_chrome_headless_shell_catalog_entry() -> None:
    ids = {tool.id for tool in load_tools(REGISTRY)}
    assert "chrome-headless-shell" not in ids


def test_mmdc_requires_puppeteer_and_groups_the_node_install() -> None:
    mmdc = next(t for t in load_tools(REGISTRY) if t.id == "mmdc")
    assert mmdc.requires == ("pnpm", "puppeteer")
    node = next(method for method in mmdc.methods if method.kind == "node")
    assert node.params["npm_pkg"] == "@mermaid-js/mermaid-cli"
    assert node.params["co_install"] == ["puppeteer"]
    assert node.params["allow_build"] == ["puppeteer"]
    assert node.params["min_node"] == "22.12.0"
    assert node.params["smoke"] == "puppeteer-browser"
    assert node.params["versions"] == {"puppeteer": "^25"}
    assert node.os == ()
    assert node.arch == ()


def test_co_install_names_resolve_to_required_catalog_tools() -> None:
    tools = load_tools(REGISTRY)
    npm_pkg_owners: dict[str, list[str]] = {}
    for tool in tools:
        for method in tool.methods:
            if method.kind != "node":
                continue
            pkg = method.params.get("npm_pkg")
            if isinstance(pkg, str):
                npm_pkg_owners.setdefault(pkg, []).append(tool.id)
    for tool in tools:
        for method in tool.methods:
            if method.kind != "node" or "co_install" not in method.params:
                continue
            raw = method.params["co_install"]
            assert isinstance(raw, list)
            names: list[str] = []
            for item in cast(list[object], raw):
                assert isinstance(item, str)
                names.append(item)
            for name in names:
                owners = npm_pkg_owners.get(name, [])
                assert owners, f"{tool.id} co_install '{name}' is not any catalog tool's npm_pkg"
                assert any(owner_id in tool.requires for owner_id in owners), (
                    f"{tool.id} co_install '{name}' has no matching requires edge"
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
    assert len(ids) == len(set(ids))
    by_cmd: dict[str, set[str]] = {}
    for tool in tools:
        by_cmd.setdefault(tool.cmd, set()).add(tool.id)
    duplicates = {cmd: tool_ids for cmd, tool_ids in by_cmd.items() if len(tool_ids) > 1}
    # drawio-cli ships inside drawio-desktop's own release and is never
    # independently invocable, so both reviewed entries share the `drawio` cmd.
    assert duplicates == {"drawio": {"drawio-desktop", "drawio-cli"}}


def test_registry_tier_distribution_is_pinned() -> None:
    # Deliberate tripwire: any phase that adds or removes a registry entry
    # (ROADMAP Phases 7 and 8 both will) must update these counts in the same
    # commit that changes the catalog.
    assert dict(Counter(t.tier for t in load_tools(REGISTRY))) == {
        "system": 26,
        "ai": 22,
        "user": 41,
    }


def test_bootstrap_package_managers_are_system_tier() -> None:
    tools = _tools_by_id()
    for tool_id in ("uv", "pnpm", "brew", "sdkman"):
        assert tools[tool_id].tier == "system"


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


def test_zsh_resolves_across_platforms_with_immutable_brew_fallback() -> None:
    zsh = _tools_by_id()["zsh"]
    fedora = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    bazzite = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(zsh, fedora)] == ["dnf", "brew"]
    assert [m.kind for m in resolve_methods(zsh, bazzite)] == ["brew"]
    assert [m.kind for m in resolve_methods(zsh, macos)] == ["brew"]


def test_oh_my_zsh_requires_zsh_and_sets_safe_env() -> None:
    oh_my_zsh = _tools_by_id()["oh-my-zsh"]
    assert oh_my_zsh.requires == ("zsh", "git")
    assert oh_my_zsh.cmd == "omz"
    method = oh_my_zsh.methods[0]
    assert method.params["env"] == {"RUNZSH": "no", "CHSH": "no", "KEEP_ZSHRC": "yes"}
    assert method.params["detect_path"] == "~/.oh-my-zsh/oh-my-zsh.sh"


def test_selecting_oh_my_zsh_drags_in_zsh_and_git_in_deps_first_order() -> None:
    catalog = load_tools(REGISTRY)
    by_id = {tool.id: tool for tool in catalog}
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    result = resolve_dependencies(
        [by_id["oh-my-zsh"]],
        catalog,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=lambda _tool: False,
    )
    ids = [tool.id for tool in result.order]
    assert ids.index("zsh") < ids.index("oh-my-zsh")
    assert ids.index("git") < ids.index("oh-my-zsh")
    assert "zsh" in result.dragged_in
    assert "git" in result.dragged_in


def test_bazzite_zsh_and_podman_both_resolve_brew_only_no_new_entry() -> None:
    tools = _tools_by_id()
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    assert [m.kind for m in resolve_methods(tools["zsh"], platform)] == ["brew"]
    assert [m.kind for m in resolve_methods(tools["podman"], platform)] == ["brew"]
    assert sum(1 for tool_id in {t.id for t in load_tools(REGISTRY)} if tool_id == "podman") == 1


def test_oh_my_zsh_entry_records_the_keep_zshrc_finding() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, line in enumerate(lines) if line == 'id = "oh-my-zsh"')
    window = "\n".join(lines[max(0, idx - 50) : idx])
    for needle in (
        "KEEP_ZSHRC",
        "RUNZSH",
        "CHSH",
        "OVERWRITE_CONFIRMATION",
        "Tier-3 container",
        "Bazzite",
        "command_exists git",
        "HEAD",
    ):
        assert needle in window, f'missing {needle!r} above id = "oh-my-zsh"'


def test_zsh_entry_records_the_podman_pattern_reuse() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, line in enumerate(lines) if line == 'id = "zsh"')
    window = "\n".join(lines[max(0, idx - 15) : idx])
    assert "podman" in window
    assert "5.9.2" in window


def test_gnu_bash_avoids_system_bash_false_positive_via_detect_path() -> None:
    gnu_bash = _tools_by_id()["gnu-bash"]
    assert gnu_bash.cmd != "bash"
    assert all(
        method.kind == "brew" and method.params["formula"] == "bash" for method in gnu_bash.methods
    )
    by_arch = {method.arch: method for method in gnu_bash.methods}
    assert by_arch[("arm64",)].params["detect_path"] == "/opt/homebrew/bin/bash"
    assert by_arch[("amd64",)].params["detect_path"] == "/usr/local/bin/bash"


def test_gnu_bash_only_resolves_on_macos() -> None:
    gnu_bash = _tools_by_id()["gnu-bash"]
    debian = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert resolve_methods(gnu_bash, debian) == []
    methods = resolve_methods(gnu_bash, macos)
    assert len(methods) == 1
    assert methods[0].kind == "brew"


def test_apple_containers_resolves_only_on_macos_arm64_with_a_new_enough_version() -> None:
    container = _tools_by_id()["container"]
    arm = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")
    intel = Platform(os="macos", arch="amd64", immutable=False, has_brew=True, os_version="26.0")
    fedora = Platform(os="fedora", arch="arm64", immutable=False, has_brew=True, os_version=None)
    assert [m.kind for m in resolve_methods(container, arm)] == ["brew"]
    assert resolve_methods(container, intel) == []
    assert resolve_methods(container, fedora) == []


def test_apple_containers_blocks_a_too_old_macos_version() -> None:
    container = _tools_by_id()["container"]
    too_old = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="15.0")
    unknown = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version=None)
    assert resolve_methods(container, too_old) == []
    assert resolve_methods(container, unknown) == []


def test_apple_containers_always_appears_in_the_registry_regardless_of_platform() -> None:
    assert "container" in {t.id for t in load_tools(REGISTRY)}


def test_gnu_bash_entry_records_the_detection_fix() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, line in enumerate(lines) if line == 'id = "gnu-bash"')
    window = "\n".join(lines[max(0, idx - 50) : idx])
    for needle in ("5.3.15", "DEFAULT_LOADABLE_BUILTINS_PATH", "sdkman"):
        assert needle in window, f'missing {needle!r} above id = "gnu-bash"'


def test_apple_containers_entry_records_the_disabled_state_resolution() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, line in enumerate(lines) if line == 'id = "container"')
    window = "\n".join(lines[max(0, idx - 50) : idx])
    for needle in (
        "NO_METHOD",
        "macos",
        "version",
        # Not a bare "26" — every dated comment starts with "# Verified
        # 2026-09-06: ...", so a bare "26" is trivially satisfied by "2026"
        # regardless of whether the actual version-floor fact survives a
        # future edit (dual-lane review, WR-01).
        'min_os_version = "26"',
        "arm64",
        "brew install container",
    ):
        assert needle in window, f'missing {needle!r} above id = "container"'


def test_fresh_bazzite_without_brew_has_no_method_for_zsh_or_podman_yet() -> None:
    """zsh/oh-my-zsh have no method on a brew-less immutable Fedora because Homebrew
    is not yet installed, not because Bazzite is unsupported. The fix is running
    this installer once with only the registry's existing, unconditional brew
    kind="script" Linux method selected (it applies regardless of has_brew), then
    re-running the installer in a fresh process, which re-probes has_brew=True
    and unblocks zsh/oh-my-zsh. This is how every brew-only Linux entry already
    requires two runs on a truly bare machine — a pre-existing property of the
    static per-run Platform snapshot, not something these two entries change.
    """
    catalog = load_tools(REGISTRY)
    by_id = {tool.id: tool for tool in catalog}
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    assert resolve_methods(by_id["zsh"], platform) == []
    assert resolve_methods(by_id["podman"], platform) == []
    result = resolve_dependencies(
        [by_id["oh-my-zsh"]],
        catalog,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=lambda _tool: False,
    )
    assert result.order == ()
    assert any("zsh" in warning and "not available" in warning for warning in result.warnings)


def test_hexyl_linux_uses_gnu_and_strips() -> None:
    hexyl = next(t for t in load_tools(REGISTRY) if t.id == "hexyl")
    linux = Platform(os="arch", arch="arm64", immutable=False, has_brew=True)
    method = resolve_methods(hexyl, linux)[0]
    assert method.params["asset"] == "hexyl-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
    assert method.params["strip"] == 1


def test_kitty_has_no_linux_download_fallback() -> None:
    kitty = _tools_by_id()["kitty"]
    fedora = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    bazzite = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")
    assert [m.kind for m in resolve_methods(kitty, fedora)] == ["dnf"]
    assert resolve_methods(kitty, bazzite) == []
    assert [m.kind for m in resolve_methods(kitty, macos)] == ["cask"]


def test_kitty_cask_blocks_a_too_old_macos_version() -> None:
    # Dual-lane review (codex-sol-high) found the cask's macOS >= 12 floor
    # (formulae.brew.sh/api/cask/kitty.json depends_on.macos) was missing
    # from the catalog, so platform_could_support wrongly left kitty
    # enabled on an unsupported old macOS.
    kitty = _tools_by_id()["kitty"]
    too_old = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="11.0")
    new_enough = Platform(
        os="macos", arch="arm64", immutable=False, has_brew=True, os_version="12.0"
    )
    assert resolve_methods(kitty, too_old) == []
    assert [m.kind for m in resolve_methods(kitty, new_enough)] == ["cask"]


def test_wezterm_appimage_covers_bazzite_where_kitty_cannot() -> None:
    wezterm = _tools_by_id()["wezterm"]
    arch_amd64 = Platform(os="arch", arch="amd64", immutable=False, has_brew=True)
    arch_arm64 = Platform(os="arch", arch="arm64", immutable=False, has_brew=True)
    debian = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    bazzite = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    fedora_arm64 = Platform(os="fedora", arch="arm64", immutable=False, has_brew=True)

    assert [m.kind for m in resolve_methods(wezterm, arch_amd64)] == ["pacman"]
    assert [m.kind for m in resolve_methods(wezterm, arch_arm64)] == ["pacman"]
    assert [m.kind for m in resolve_methods(wezterm, debian)] == ["github_release"]
    assert [m.kind for m in resolve_methods(wezterm, bazzite)] == ["github_release"]
    assert [m.kind for m in resolve_methods(wezterm, macos)] == ["cask"]

    # Debian/Fedora arm64 has no path: this session's live check of
    # api.github.com/repos/wezterm/wezterm/releases/latest found only .deb
    # arm64 variants, no arm64 AppImage.
    assert resolve_methods(wezterm, fedora_arm64) == []

    method = resolve_methods(wezterm, debian)[0]
    assert method.params["asset"] == "WezTerm-{ver}-Ubuntu20.04.AppImage"
    assert method.params["checksum"] == "{asset}.sha256"
    assert method.params["raw"] is True
    assert method.params["member"] == "wezterm"
    assert method.arch == ("amd64",)


def test_kitty_entry_records_the_txz_extraction_gap() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, line in enumerate(lines) if line == 'id = "kitty"')
    window = "\n".join(lines[max(0, idx - 40) : idx])
    for fragment in (
        ".txz",
        "tar -xzf",
        "download.py",
        "x86_64_linux",
        'platform.os == "macos"',
    ):
        assert fragment in window, f'missing {fragment!r} above id = "kitty"'


def test_wezterm_entry_records_the_checksum_sidecar_verification() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, line in enumerate(lines) if line == 'id = "wezterm"')
    window = "\n".join(lines[max(0, idx - 40) : idx])
    for fragment in (".sha256", "arm64", "Bazzite"):
        assert fragment in window, f'missing {fragment!r} above id = "wezterm"'


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


SIDECAR_VERIFIED = {"rg", "starship", "ruff", "deno", "tealdeer", "wezterm"}


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
    "rtk",
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


def test_shipped_registry_recommends_all_resolve() -> None:
    tools = load_tools(REGISTRY)
    known = {tool.id for tool in tools}
    errors = [
        f"{tool.id} recommends unknown id '{rec_id}'"
        for tool in tools
        for rec_id in tool.recommends
        if rec_id not in known
    ]
    assert errors == []


def test_agent_hosts_recommend_existing_catalog_tools() -> None:
    # Do not assert the two lists are equal: Phase 8 D-01 specifies per-host
    # membership, so an equality check would be mandatory churn when the real
    # companion data lands.
    tools = _tools_by_id()
    ids = set(tools)
    for host_id in ("claude", "opencode", "codex", "cursor-agent"):
        recommends = tools[host_id].recommends
        assert recommends, f"{host_id} must declare a non-empty recommends list"
        assert set(recommends) <= ids, f"{host_id} recommends unknown ids"


def test_agent_host_recommends_match_the_researched_per_host_set() -> None:
    tools = _tools_by_id()
    want = ("codegraph", "graphify", "rtk")
    assert tools["claude"].recommends == want
    assert tools["opencode"].recommends == want
    assert tools["codex"].recommends == want
    assert tools["cursor-agent"].recommends == want
    assert tools["antigravity"].recommends == ()


def test_agent_host_recommends_entries_record_the_rtk_codex_caveat() -> None:
    text = REGISTRY.read_text()
    for host_id in ("claude", "opencode", "codex", "cursor-agent"):
        idx = text.index(f'id = "{host_id}"')
        next_method = text.index("[[tool.method]]", idx)
        window = text[idx:next_method]
        for needle in ("codegraph", "graphify", "rtk"):
            assert needle in window, f"missing {needle!r} in {host_id}'s recommends window"
        if host_id == "codex":
            assert "instructions-based rather than a runtime hook" in window


def test_shipped_node_tools_require_pnpm() -> None:
    tools = load_tools(REGISTRY)
    for tool in tools:
        if any(m.kind == "node" for m in tool.methods):
            assert "pnpm" in tool.requires, f"{tool.id}: node tool must require pnpm"


def test_shipped_uv_tool_tools_require_uv() -> None:
    tools = load_tools(REGISTRY)
    for tool in tools:
        if any(m.kind == "uv-tool" for m in tool.methods):
            assert "uv" in tool.requires, f"{tool.id}: uv-tool tool must require uv"


def test_puppeteer_entry_records_when_the_smoke_check_does_not_re_run() -> None:
    """CR-02: install-time success was implicitly treated as ongoing correctness.

    The entry must say where the re-check lives and what the remaining gap is,
    so a future maintainer does not read a passing install as a standing
    guarantee.
    """
    text = REGISTRY.read_text(encoding="utf-8")
    assert "ALREADY_INSTALLED" in text
    assert "audit_node_globals" in text


def test_codegraph_declares_the_mcp_postinstall_hook() -> None:
    tools = _tools_by_id()
    assert tools["codegraph"].postinstall == "codegraph-mcp-register"


def test_codegraph_entry_records_the_postinstall_research_findings() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    idx = text.index('id = "codegraph"')
    next_method = text.index("[[tool.method]]", idx)
    window = text[idx:next_method]
    for needle in (
        "codegraph-mcp-register",
        "--target auto",
        "cursor-agent",
        "is_installed",
        "D-01",
    ):
        assert needle in window, f"missing {needle!r} in codegraph's postinstall window"


def test_only_codegraph_declares_a_postinstall_hook() -> None:
    tools = load_tools(REGISTRY)
    for tool in tools:
        if tool.id == "codegraph":
            continue
        assert tool.postinstall is None, f"{tool.id}: unexpected postinstall hook declared"
