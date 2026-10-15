import re
from collections import Counter
from pathlib import Path
from typing import cast

import pytest

from installer.deps import requires_integrity_errors, resolve_dependencies
from installer.download import pinned_url
from installer.model import Method, Tool, load_categories, load_tools
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
        # The human launches and drives these directly -- tier="user" tracks
        # exactly that, independent of their "ai" category/audience.
        assert tool.tier == "user"


# Phase 15.3 (2026-09-16): these 16 rows were re-tagged from "both" to
# "human" under one rule. Each carried an explicit `audience = "both"` in
# installer/registry.toml -- one that happened to match the Tool dataclass
# default (installer/model.py:287) -- but had never been individually
# reviewed; the default only applies when the key is absent, and none of
# these 16 rows omitted it.
#
# The rule judges what a tool IS, not which flags it has: a tool is
# `human` when its default mode is an interactive session (a TUI, or shell
# UX a person types into) and a one-shot print is not what it is for; it
# stays `both` when invoking it non-interactively and reading what it
# printed IS the product -- the shape `df`, `ps`, `cat` and `ls` have. A
# batch, filter or CI flag bolted onto an interactive tool does not by
# itself make it `both` -- the question is whether an agent would reach
# for the tool on its own, and a flag's existence is not an answer to it.
#
# `fzf` and `dive` are judged against that rule rather than waved through
# by it: `fzf -f/--filter` prints matches for the initial query and exits,
# and `dive --ci` skips the interactive TUI and validates against CI
# rules. Both stay `human` anyway -- `fzf` is a picker a person drives, and
# an agent doing the same matching has `rg`/`grep`; `dive --ci` is a gate
# in a human's pipeline, and an agent inspecting an image reaches for
# `docker history` instead.
#
# `gum`, `gnu-bash` and `zsh` are judged the same way. `gum` bills itself
# as "a tool for glamorous shell scripts" and several subcommands (`style`,
# `format`, `log`) print and exit, but what the catalog installs is the
# interactive prompt toolkit a person's own scripts drive; an agent
# composing output has no use for styling it. `bash -c`/`zsh -c` are how
# agents run everything, but that runs on whatever shell the box already
# has -- these entries install the shell a person logs into, and no agent
# cares which one that is.
#
# This is the rule a NEW catalog entry should apply when choosing its
# `audience` value, not only a record of this one pass -- the dataclass
# default is silent, and the next entry will take it unless something
# tells its author otherwise.
_INTERACTIVE_ONLY_TOOLS = {
    # shell tools (D-01)
    "direnv",
    "gnu-bash",
    "gum",
    "oh-my-zsh",
    "starship",
    "watch",
    "zsh",
    # editors (D-01)
    "sublime",
    "vscode",
    # nav tools (D-01)
    "broot",
    "zoxide",
    # interactive TUIs (D-02)
    "gitui",
    "lazygit",
    "bottom",
    "dive",
    "fzf",
}


def test_interactive_only_tools_are_audience_human() -> None:
    tools = _tools_by_id()
    for tool_id in sorted(_INTERACTIVE_ONLY_TOOLS):
        assert tools[tool_id].audience == "human", tool_id


# D-02's other half: each of these prints and exits by default, so an agent
# can invoke it for a one-shot snapshot the same way it invokes df, du, ps,
# cat or ls -- which is why the Phase 15.3 re-tag pass deliberately stopped
# short of them.
_SCRIPTABLE_ONE_SHOT_TOOLS = ("duf", "dust", "procs", "bat", "eza", "glow", "hexyl")


def test_scriptable_one_shot_tools_stay_audience_both() -> None:
    tools = _tools_by_id()
    for tool_id in _SCRIPTABLE_ONE_SHOT_TOOLS:
        assert tools[tool_id].audience == "both", tool_id


# The 17 ids that already carried `audience = "human"` before Phase 15.3 --
# derived from the registry and reconciled against this list during
# planning, not transcribed by hand.
_PRE_15_3_HUMAN_TOOLS = {
    "antigravity",
    "claude",
    "codex",
    "cursor-agent",
    "jetbrains-toolbox",
    "kitty",
    "matt-pocock-skills",
    "opencode",
    "opengsd",
    "openspec",
    "pi",
    "ponytail",
    "softaworks-agent-toolkit",
    "spec-kit",
    "superpowers",
    "wezterm",
}


# Ids tagged `human` AFTER Phase 15.3. This is the open-ended set and the
# only one that may grow: the two above are frozen historical records of
# what Phase 15.3 found and what it changed, and adding a new id to either
# would make that set's own comment false.
_POST_15_3_HUMAN_TOOLS = {
    "alacritty",
}


def test_audience_human_set_is_exactly_the_reviewed_tools() -> None:
    # Set equality rather than a count: a count says "expected 33, got 34"
    # and a set difference says which row moved. A phase adding a
    # `human`-tagged catalog entry appends its id to _POST_15_3_HUMAN_TOOLS
    # in the same commit -- the same standing instruction
    # test_registry_tier_distribution_is_pinned already carries for `tier`.
    tools = _tools_by_id()
    human_ids = {tool_id for tool_id, tool in tools.items() if tool.audience == "human"}
    assert human_ids == (_PRE_15_3_HUMAN_TOOLS | _INTERACTIVE_ONLY_TOOLS | _POST_15_3_HUMAN_TOOLS)


def test_registry_audience_distribution_is_pinned() -> None:
    # Mirrors test_registry_tier_distribution_is_pinned. Catches a row
    # moving between `both` and `ai`, which the set equality above cannot
    # see -- neither set mentions `ai`.
    assert dict(Counter(t.audience for t in load_tools(REGISTRY))) == {
        "both": 47,
        "ai": 9,
        "human": 33,
    }


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
    assert sdkman.methods[0].params["version_file"] == "~/.sdkman/var/version"


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


def test_jetbrains_toolbox_installs_on_macos_and_linux() -> None:
    tools = _tools_by_id()
    toolbox = tools["jetbrains-toolbox"]
    assert toolbox.cmd == "jetbrains-toolbox"
    assert toolbox.category == "editor"
    assert {m.kind for m in toolbox.methods} == {"cask", "tarball"}
    cask = next(m for m in toolbox.methods if m.kind == "cask")
    assert cask.params["cask"] == "jetbrains-toolbox"
    assert cask.params["app"] == "JetBrains Toolbox.app"
    tarball = next(m for m in toolbox.methods if m.kind == "tarball")
    assert "debian" in tarball.os and "fedora" in tarball.os and "arch" in tarball.os
    linux_amd64 = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    assert [m.kind for m in resolve_methods(toolbox, linux_amd64)] == ["tarball"]


def test_jetbrains_toolbox_declares_two_distinct_linux_and_macos_cask_names() -> None:
    """D-01's second dated correction: a second, Linux-gated cask row names
    the cask Homebrew actually installs on Linux (jetbrains-toolbox-linux),
    distinct from the macOS cask token (jetbrains-toolbox). The row is
    ownership evidence only -- proven BEHAVIOURALLY here, not just by shape:
    resolve_methods on Linux still returns no cask method, and on macOS
    still returns exactly the one pre-existing cask method."""
    toolbox = _tools_by_id()["jetbrains-toolbox"]
    casks = [m for m in toolbox.methods if m.kind == "cask"]
    assert len(casks) == 2, [m.params for m in casks]
    names = {m.params.get("cask") for m in casks}
    assert names == {"jetbrains-toolbox", "jetbrains-toolbox-linux"}
    linux = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")
    assert [m for m in resolve_methods(toolbox, linux) if m.kind == "cask"] == []
    macos_casks = [m for m in resolve_methods(toolbox, macos) if m.kind == "cask"]
    assert len(macos_casks) == 1
    assert macos_casks[0].params["cask"] == "jetbrains-toolbox"


def test_jetbrains_toolbox_linux_cask_row_records_dated_verification() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    block = text.split('id = "jetbrains-toolbox"', 1)[1].split("[[tool]]", 1)[0]
    # Not a bare "26" -- every dated comment starts with "# Verified {date}:".
    verified = [
        line for line in block.splitlines() if line.lstrip().startswith("#") and "Verified" in line
    ]
    assert verified, block
    assert "jetbrains-toolbox-linux" in block
    assert "OWNERSHIP EVIDENCE ONLY" in block


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
    assert [m.kind for m in resolve_methods(volta, macos)][:2] == ["script", "brew"]
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
    assert [m.kind for m in resolve_methods(gh, macos)][:2] == ["github_release", "brew"]


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
    assert method.params["asset"] == "hyperfine-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
    assert method.params["strip"] == 1


def test_download_tools_resolve_github_release_then_brew_on_macos() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    for tool_id in ("starship", "just", "dust"):
        kinds = [m.kind for m in resolve_methods(tools[tool_id], macos)]
        assert kinds == ["github_release", "brew"], tool_id


# GUI apps with no Linux install method: gnu-bash exists specifically to
# patch macOS's ancient system bash, so it has nothing to install on Linux
# (already at a modern bash). vscode/sublime/jetbrains-toolbox all gained
# official Linux tarball methods -- see their registry entries.
MACOS_ONLY = {"gnu-bash"}
# Apple Containers: Homebrew itself requires macos>=26 and arch=arm64. Membership
# means the tool cannot work on that platform+arch, not that packaging is inconvenient.
MACOS_ARM64_ONLY = {"container", "podman"}
# Membership means the tool provably cannot work on that platform+arch, not
# that its packaging is inconvenient there.
NO_LINUX_ARM64 = {"puppeteer"}
# wezterm: Arch arm64 IS covered (its pacman method declares no arch list),
# but Debian/Fedora arm64 have no path — this session's live check of
# api.github.com/repos/wezterm/wezterm/releases/latest found only .deb arm64
# variants, no arm64 AppImage. A gap bounded by upstream asset availability,
# not a project scoping choice.
NO_DEBIAN_FEDORA_ARM64 = {"wezterm"}
# alacritty: the official Homebrew cask is macOS-only and has been disabled
# since 2026-09-01 (unsigned build fails Gatekeeper). No formula exists, and
# the GitHub release has no macOS asset this installer can place. Linux uses
# the distro package. Membership means no reviewed macOS method, not that
# Alacritty cannot run on macOS.
NO_MACOS = {"alacritty"}


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
            if platform_os == "macos":
                allowed |= NO_MACOS
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


def test_no_macos_allowlist_stays_honest() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    for tool_id in sorted(NO_MACOS):
        assert tool_id in tools, f"NO_MACOS entry '{tool_id}' is not in the registry"
        for arch in ("amd64", "arm64"):
            macos = Platform(
                os="macos", arch=arch, immutable=False, has_brew=True, os_version="26.0"
            )
            assert resolve_methods(tools[tool_id], macos) == [], (
                f"'{tool_id}' unexpectedly resolves on macos/{arch}"
            )
        debian = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
        assert resolve_methods(tools[tool_id], debian), (
            f"'{tool_id}' must still resolve on debian/amd64"
        )


def test_puppeteer_is_an_ai_tier_node_tool_requiring_pnpm() -> None:
    puppeteer = next(t for t in load_tools(REGISTRY) if t.id == "puppeteer")
    assert (
        puppeteer.name,
        puppeteer.category,
        puppeteer.cmd,
        puppeteer.priority,
        puppeteer.audience,
        puppeteer.tier,
    ) == ("Puppeteer", "dev", "puppeteer", "P3", "both", "ai")
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
    assert cursor_agent.tier == "user"
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
    assert antigravity.tier == "user"
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


def test_drawio_desktop_is_the_only_drawio_row() -> None:
    tools = _tools_by_id()
    assert "drawio-cli" not in tools
    assert tools["drawio-desktop"].audience == "both"
    assert len(tools) == 89


def test_removed_owner_probe_is_rejected_at_load(tmp_path: Path) -> None:
    manifest = tmp_path / "registry.toml"
    manifest.write_text(
        """
[[tool]]
id = "demo"
category = "dev"
tier = "user"
verified = 2026-10-13
owner_probes = ["managed-download"]
[[tool.method]]
kind = "brew"
formula = "demo"
"""
    )
    with pytest.raises(ValueError, match="unknown owner probe 'managed-download'"):
        load_tools(manifest)


def test_existing_drawio_install_shows_under_drawio_desktop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import installer.status as status

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    drawio = bin_dir / "drawio"
    drawio.write_bytes(b"")
    drawio.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    drawio_desktop = _tools_by_id()["drawio-desktop"]
    assert status.is_installed(drawio_desktop) is True


def test_registry_has_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    assert len(ids) == len(set(ids))
    by_cmd: dict[str, set[str]] = {}
    for tool in tools:
        by_cmd.setdefault(tool.cmd, set()).add(tool.id)
    duplicates = {cmd: tool_ids for cmd, tool_ids in by_cmd.items() if len(tool_ids) > 1}
    assert duplicates == {}


def test_registry_tier_distribution_is_pinned() -> None:
    # Deliberate tripwire: any phase that adds or removes a registry entry
    # (ROADMAP Phases 7 and 8 both will) must update these counts in the same
    # commit that changes the catalog.
    assert dict(Counter(t.tier for t in load_tools(REGISTRY))) == {
        "system": 26,
        "ai": 17,
        "user": 46,
    }


def test_d09_borderline_tools_stay_user_tier() -> None:
    # D-09: mmdc, gitleaks and vale were reviewed against .claude/architecture.md's
    # tier criterion and confirmed correct as user-tier -- each is invoked by the
    # human on the human's own artifact (a diagram, a repo scan, prose), not
    # infrastructure an agent consumes underneath.
    tools = _tools_by_id()
    for tool_id in ("mmdc", "gitleaks", "vale"):
        assert tools[tool_id].tier == "user", tool_id


def test_bootstrap_package_managers_are_system_tier() -> None:
    tools = _tools_by_id()
    for tool_id in ("uv", "pnpm", "brew", "sdkman"):
        assert tools[tool_id].tier == "system"


def test_reconciliation_tier_audit_confirms_all_11_re_added_rows() -> None:
    # Individual audit (D-02) of the 11 rows commit 9f6274b re-added, checked
    # against origin's real tier semantics (system = machine prerequisite,
    # user = a tool the human runs and drives directly -- including an AI
    # agent harness/CLI -- ai = tooling that operates underneath or is
    # consumed BY an agent session, never launched directly by the human as
    # their own interface) and this registry's own established precedents --
    # not the porting agent's skill-pack/agent->ai, everything-else->user
    # heuristic.
    tools = _tools_by_id()

    # glab (git CLI, audience=both, priority=P0) matches the existing gh
    # (GitHub CLI) precedent exactly: same category, same audience, same
    # priority. gh is already tier="user" despite agents using it too.
    assert tools["glab"].tier == "user"

    # drawio-desktop (diagram render tool, audience=both) matches the existing
    # mmdc precedent (diagram-category, tier="user", audience="both").
    assert tools["drawio-desktop"].tier == "user"
    assert tools["drawio-desktop"].audience == "both"

    # pi (own coding-agent harness, kind="host_setup") is a standalone,
    # human-driven agent CLI -- the same shape as claude/codex/opencode/
    # cursor-agent/antigravity/aichat, all tier="user": the human launches
    # and drives it directly, which is what tier="user" now tracks.
    assert tools["pi"].tier == "user"

    # ponytail/openspec/superpowers/softaworks-agent-toolkit/
    # matt-pocock-skills/opengsd/spec-kit (all kind="skill_pack", each
    # installing a plugin/workflow into an agent harness's own skill
    # directory) match the existing codegraph/graphify/rtk precedent:
    # ai-tier tools that exist specifically to serve agent hosts.
    for tool_id in (
        "ponytail",
        "openspec",
        "superpowers",
        "softaworks-agent-toolkit",
        "matt-pocock-skills",
        "opengsd",
        "spec-kit",
    ):
        assert tools[tool_id].tier == "ai"


def test_gitui_is_linux_download_and_brew_only_on_macos() -> None:
    gitui = next(t for t in load_tools(REGISTRY) if t.id == "gitui")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(gitui, linux)] == ["github_release", "brew"]
    assert [m.kind for m in resolve_methods(gitui, macos)][:2] == ["github_release", "brew"]


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


def test_only_oh_my_zsh_declares_a_post_install_action() -> None:
    """D-07: a second declarer arriving unreviewed is how a guarded,
    single-purpose action quietly becomes a general mechanism. This test is
    the only automated thing standing between those two states.
    """
    declarers = [tool.id for tool in load_tools(REGISTRY) if tool.post_install]
    assert declarers == ["oh-my-zsh"]
    oh_my_zsh = _tools_by_id()["oh-my-zsh"]
    assert oh_my_zsh.post_install == ("set_login_shell",)
    assert oh_my_zsh.requires == ("zsh", "git")
    method = oh_my_zsh.methods[0]
    assert method.kind == "script"
    assert method.params["env"] == {"RUNZSH": "no", "CHSH": "no", "KEEP_ZSHRC": "yes"}


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
    assert [m.kind for m in resolve_methods(kitty, fedora)] == ["script", "dnf"]
    assert [m.kind for m in resolve_methods(kitty, bazzite)] == ["script"]
    assert [m.kind for m in resolve_methods(kitty, macos)] == ["script", "cask"]
    assert all(method.kind != "github_release" for method in kitty.methods)


def test_kitty_linux_script_declares_vendor_bin_dir() -> None:
    kitty = _tools_by_id()["kitty"]
    script = next(
        method
        for method in kitty.methods
        if method.kind == "script" and method.os == ("debian", "arch", "fedora")
    )
    assert script.os == ("debian", "arch", "fedora")
    assert script.params["url"] == "https://sw.kovidgoyal.net/kitty/installer.sh"
    assert script.params["args"] == ["launch=n"]
    assert script.params["bin_dir"] == "~/.local/kitty.app/bin"
    assert script.params["shell"] == "sh"


def test_every_script_method_declares_a_location_or_explains_no_bin_dir() -> None:
    """Load-bearing contract: the literal phrase `no bin_dir` inside a
    `# Verified` comment is what this scan accepts in place of `bin_dir` or
    `detect_path`. Do not reword that phrase.
    """
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    tool_at = [index for index, line in enumerate(lines) if line.strip() == "[[tool]]"]
    missing: list[int] = []
    for index, line in enumerate(lines):
        if line.strip() != 'kind = "script"':
            continue
        method_end = index + 1
        while method_end < len(lines) and not lines[method_end].startswith("[["):
            method_end += 1
        body = "\n".join(lines[index:method_end])
        if "bin_dir" in body or "detect_path" in body:
            continue
        tool_start = max(start for start in tool_at if start < index)
        comment_start = tool_start
        while comment_start > 0 and (
            lines[comment_start - 1].startswith("#") or not lines[comment_start - 1].strip()
        ):
            comment_start -= 1
        window = "\n".join(lines[comment_start:method_end])
        if any(item.startswith("# Verified") for item in lines[comment_start:tool_start]) and (
            "no bin_dir" in window
        ):
            continue
        missing.append(index + 1)
    assert missing == []


def test_kitty_declared_location_counts_as_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import installer.status as status

    def _which_none(_cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", _which_none)
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "kitty.app" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "kitty").touch()
    assert status.is_installed(_tools_by_id()["kitty"]) is True


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
    assert [m.kind for m in resolve_methods(kitty, too_old)] == ["script"]
    assert [m.kind for m in resolve_methods(kitty, new_enough)] == ["script", "cask"]


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


def test_kitty_entry_records_why_it_uses_the_vendor_script() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, line in enumerate(lines) if line == 'id = "kitty"')
    window = "\n".join(lines[max(0, idx - 40) : idx])
    for fragment in (
        ".txz",
        "download.py",
        'archive = "xz"',
        "x86_64_linux",
        'platform.os == "macos"',
    ):
        assert fragment in window, f'missing {fragment!r} above id = "kitty"'
    for forbidden in ("_install_unverified", "_place_verified"):
        assert forbidden not in window, f'stale download reference {forbidden!r} above id = "kitty"'


def test_no_registry_comment_names_a_deleted_download_function() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert "_install_unverified" not in text
    assert "_place_verified" not in text


def test_alacritty_uses_distro_packages_only() -> None:
    alacritty = _tools_by_id()["alacritty"]
    fedora = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    debian = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    arch = Platform(os="arch", arch="arm64", immutable=False, has_brew=True)
    bazzite = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")
    assert [m.kind for m in resolve_methods(alacritty, fedora)] == ["dnf"]
    assert [m.kind for m in resolve_methods(alacritty, debian)] == ["apt"]
    assert [m.kind for m in resolve_methods(alacritty, arch)] == ["pacman"]
    assert resolve_methods(alacritty, bazzite) == []
    assert resolve_methods(alacritty, macos) == []
    assert {m.kind for m in alacritty.methods} == {"dnf", "apt", "pacman"}


def test_alacritty_entry_records_the_missing_linux_release_and_disabled_cask() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, line in enumerate(lines) if line == 'id = "alacritty"')
    window = "\n".join(lines[max(0, idx - 20) : idx])
    for fragment in (
        "v0.17.0",
        "no Linux binary",
        "disabled 2026-09-01",
        "immutable Fedora",
    ):
        assert fragment in window, f'missing {fragment!r} above id = "alacritty"'


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


def test_ast_grep_tier_is_ai() -> None:
    # D-07: same category = "search" family as rg/fd, both already tier =
    # "ai" -- a structural-search tool an agent invokes, not one the human
    # types.
    ast = next(t for t in load_tools(REGISTRY) if t.id == "ast-grep")
    assert ast.tier == "ai"


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
    assert pnpm_linux[0].params["bin_dir"] == "~/.local/share/pnpm/bin"
    assert pnpm_macos[0].params["bin_dir"] == "~/Library/pnpm/bin"

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


def test_vscode_declares_two_distinct_linux_and_macos_cask_names() -> None:
    """15.4-VERIFICATION.md gap closure: the exact second instance of D-01's
    dated correction, mirroring jetbrains-toolbox's fix. A second, Linux-gated
    cask row names the cask Homebrew actually installs on Linux
    (visual-studio-code-linux), distinct from the macOS cask token
    (visual-studio-code). The row is ownership evidence only -- proven
    BEHAVIOURALLY here, not just by shape: resolve_methods on Linux still
    returns no cask method, and on macOS still returns exactly the one
    pre-existing cask method."""
    vscode = _tools_by_id()["vscode"]
    casks = [m for m in vscode.methods if m.kind == "cask"]
    assert len(casks) == 2, [m.params for m in casks]
    names = {m.params.get("cask") for m in casks}
    assert names == {"visual-studio-code", "visual-studio-code-linux"}
    linux = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")
    assert [m for m in resolve_methods(vscode, linux) if m.kind == "cask"] == []
    macos_casks = [m for m in resolve_methods(vscode, macos) if m.kind == "cask"]
    assert len(macos_casks) == 1
    assert macos_casks[0].params["cask"] == "visual-studio-code"


def test_vscode_linux_cask_row_records_dated_verification() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    block = text.split('id = "vscode"', 1)[1].split("[[tool]]", 1)[0]
    # Not a bare "26" -- every dated comment starts with "# Verified {date}:".
    verified = [
        line for line in block.splitlines() if line.lstrip().startswith("#") and "Verified" in line
    ]
    assert verified, block
    assert "visual-studio-code-linux" in block
    assert "OWNERSHIP EVIDENCE ONLY" in block


_PINNED_LITERAL_DOT = re.compile(r"\d+\.\d+")
_PINNED_LITERAL_BUILD = re.compile(r"\d{3,}")
_ARCH_TOKENS_IN_URL = ("x86_64", "arm64", "amd64", "x64")


def _scrub_arch_tokens_from_url(url: str) -> str:
    scrubbed = url
    for token in _ARCH_TOKENS_IN_URL:
        scrubbed = scrubbed.replace(token, "")
    return scrubbed


def _app_tarball_methods() -> list[tuple[Tool, Method]]:
    return [
        (tool, method)
        for tool in load_tools(REGISTRY)
        for method in tool.methods
        if method.kind in ("app", "tarball")
    ]


def test_no_pinned_url_carries_a_literal_version() -> None:
    violations: list[str] = []
    for tool, method in _app_tarball_methods():
        url = str(method.params["url"])
        if "{ver}" in url:
            version = method.params.get("version")
            sha256 = method.params.get("sha256")
            if not isinstance(version, str) or not version:
                violations.append(f"{tool.id}: pinned url missing version")
            if not isinstance(sha256, str) or len(sha256) != 64:
                violations.append(f"{tool.id}: pinned url missing sha256")
            continue
        scrubbed = _scrub_arch_tokens_from_url(url)
        if _PINNED_LITERAL_DOT.search(scrubbed) or _PINNED_LITERAL_BUILD.search(scrubbed):
            violations.append(f"{tool.id}: unpinned url carries a literal version: {url}")
    assert violations == []


def test_pinned_methods_render_their_upstream_asset_names() -> None:
    tools = _tools_by_id()
    drawio = tools["drawio-desktop"]
    for method in drawio.methods:
        if method.kind != "app" or method.os != ("macos",):
            continue
        ver = str(method.params["version"])
        rendered = pinned_url(method)
        if method.arch == ("arm64",):
            assert rendered == (
                f"https://github.com/jgraph/drawio-desktop/releases/download/v{ver}/"
                f"draw.io-arm64-{ver}.zip"
            )
        else:
            assert rendered == (
                f"https://github.com/jgraph/drawio-desktop/releases/download/v{ver}/"
                f"draw.io-x64-{ver}.zip"
            )

    sublime = tools["sublime"]
    for method in sublime.methods:
        if method.kind not in ("app", "tarball"):
            continue
        ver = str(method.params["version"])
        rendered = pinned_url(method)
        if method.kind == "app":
            assert rendered == f"https://download.sublimetext.com/sublime_text_build_{ver}_mac.zip"
        elif method.arch == ("amd64",):
            assert rendered == (
                f"https://download.sublimetext.com/sublime_text_build_{ver}_x64.tar.xz"
            )
        else:
            assert rendered == (
                f"https://download.sublimetext.com/sublime_text_build_{ver}_arm64.tar.xz"
            )


def test_a_tools_pinned_methods_share_one_version() -> None:
    by_tool: dict[str, set[str]] = {}
    for tool, method in _app_tarball_methods():
        url = str(method.params["url"])
        if "{ver}" not in url:
            continue
        version = method.params.get("version")
        assert isinstance(version, str) and version
        by_tool.setdefault(tool.id, set()).add(version)
    multi = {tid: versions for tid, versions in by_tool.items() if len(versions) > 1}
    assert multi == {}


def test_sublime_is_single_universal_app_with_cask_fallback() -> None:
    sublime = next(t for t in load_tools(REGISTRY) if t.id == "sublime")
    assert sublime.cmd == "subl"
    assert sublime.category == "editor"
    for arch in ("arm64", "amd64"):  # one universal zip serves both
        mac = Platform(os="macos", arch=arch, immutable=False, has_brew=True)
        methods = resolve_methods(sublime, mac)
        assert [m.kind for m in methods] == ["app", "cask"]
        assert "{ver}" in str(methods[0].params["url"])
        assert pinned_url(methods[0]) == (
            f"https://download.sublimetext.com/sublime_text_build_"
            f"{methods[0].params['version']}_mac.zip"
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


def test_only_codegraph_and_rtk_declare_a_postinstall_hook() -> None:
    # graphify's host-registration hook was removed in Phase 17 (SAFE-02):
    # every graphify host-registration form writes into the working directory,
    # so the installer runs none of them.
    tools = load_tools(REGISTRY)
    for tool in tools:
        if tool.id in ("codegraph", "rtk"):
            continue
        assert tool.postinstall is None, f"{tool.id}: unexpected postinstall hook declared"


def test_native_package_manager_rows_declare_their_owner_probes() -> None:
    # D-05: exactly the eleven rows that can be installed through a native
    # OS package manager (or, for opencode/wezterm, pacman alone) declare
    # owner_probes so detect_owner can actually answer for them.
    # rpm-ostree is listed FIRST on the nine dnf/apt/pacman-capable rows: on
    # an ostree host the rpm database still answers `rpm -q`, so probing dnf
    # first would attribute a package the user explicitly layered to the
    # wrong mechanism -- see install_ownership.py's _rpm_ostree docstring.
    tools = _tools_by_id()
    full = ("rpm-ostree", "dnf", "apt", "pacman")
    expected = {
        "rg": full,
        "jq": full,
        "git": full,
        "zsh": full,
        "watch": full,
        "docker": full,
        "podman": full,
        "kitty": full,
        "alacritty": full,
        "opencode": ("pacman",),
        "wezterm": ("pacman",),
    }
    for tool_id, owner_probes in expected.items():
        assert tools[tool_id].owner_probes == owner_probes, tool_id

    # The pre-existing host-setup owner_probes row keeps its value.
    assert tools["pi"].owner_probes == ("host-setup",)
    assert tools["drawio-desktop"].owner_probes == ()

    # The second assertion is the one that matters over time: it turns
    # "someone added a dnf-installable tool and forgot to opt it in" from a
    # silent gap into a red test.
    native_probe_names = {"rpm-ostree", "dnf", "apt", "pacman"}
    native = {
        tool.id for tool in load_tools(REGISTRY) if set(tool.owner_probes) & native_probe_names
    }
    assert native == set(expected)


def test_every_skill_pack_records_a_verified_comment() -> None:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    headers = [
        index for index, line in enumerate(lines) if line.strip() == "[tool.skill_lifecycle]"
    ]

    assert len(headers) == 7
    for index in headers:
        window = lines[max(0, index - 15) : index]
        assert any(line.startswith("# Verified ") for line in window), window


def test_superpowers_by_harness_marks_claude_alternative_and_explains_codex() -> None:
    lifecycle = _tools_by_id()["superpowers"].skill_lifecycle
    assert lifecycle is not None
    pairs = dict(lifecycle.install.by_harness)
    claude = pairs["claude"]
    assert claude == ("/plugin install superpowers@claude-plugins-official",)
    codex = pairs["codex"]
    assert len(codex) == 1
    assert "/plugins" in codex[0]
    assert "superpowers" in codex[0]


def test_install_state_probes_match_gsd_core() -> None:
    for tool in load_tools(REGISTRY):
        lifecycle = tool.skill_lifecycle
        if lifecycle is None:
            continue
        for probe in lifecycle.status_probes:
            if probe.via == "install-state":
                assert probe.match == "gsd-core", tool.id


def test_sublime_linux_tarballs_link_the_binary_inside_the_archive_dir() -> None:
    """Phase 17 SAFE-01/D-02: both Linux tarball archives unpack to a single
    top-level sublime_text/ directory holding the executable at
    sublime_text/sublime_text -- member must name that file, not the
    directory (a directory member made the symlink point at a directory)."""
    sublime = next(t for t in load_tools(REGISTRY) if t.id == "sublime")
    tarballs = [m for m in sublime.methods if m.kind == "tarball"]
    assert len(tarballs) == 2
    for method in tarballs:
        assert method.params["member"] == "sublime_text/sublime_text"
        assert method.params["bin_name"] == "subl"
        assert method.params["archive"] == "xz"
        assert "strip" not in method.params  # default 0
    text = REGISTRY.read_text()
    block = text[text.index('id = "sublime"') :]
    assert "Verified 2026-10-14" in block


def test_codex_script_runs_non_interactive() -> None:
    """Phase 17 SAFE-07/D-10: codex's install.sh prompts on /dev/tty unless
    CODEX_NON_INTERACTIVE is set (install.sh line 6 reads it, line 100
    documents it) -- the script method declares it through the env table, and
    _env_prefix turns it into a shell prefix on the recorded command."""
    import installer.executors as executors

    codex = next(t for t in load_tools(REGISTRY) if t.id == "codex")
    script = next(m for m in codex.methods if m.kind == "script")
    assert script.params["env"] == {"CODEX_NON_INTERACTIVE": "1"}
    calls: list[list[str]] = []
    executors.execute(script, calls.append)
    assert len(calls) == 1
    assert "CODEX_NON_INTERACTIVE=1" in calls[0][-1]


def test_every_shipped_tool_declares_a_verified_date() -> None:
    import re

    text = REGISTRY.read_text()
    tool_headers = len(re.findall(r"^\[\[tool\]\]$", text, re.MULTILINE))
    verified_lines = len(re.findall(r"^verified = \d{4}-\d{2}-\d{2}$", text, re.MULTILINE))
    load_tools(REGISTRY)
    assert verified_lines == tool_headers


def test_audit_fix_c1_volta_script_covers_macos() -> None:
    volta = next(t for t in load_tools(REGISTRY) if t.id == "volta")
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    kinds = [m.kind for m in resolve_methods(volta, macos)]
    assert "script" in kinds
    block = REGISTRY.read_text(encoding="utf-8")
    start = block.index('id = "volta"')
    end = block.index('id = "fnm"', start)
    volta_block = block[start:end]
    assert "macOS" in volta_block or "macos" in volta_block.lower()
    assert "mise" in volta_block
    assert "No macOS script fallback" not in volta_block


def test_audit_fix_c2_podman_brew_is_split() -> None:
    podman = next(t for t in load_tools(REGISTRY) if t.id == "podman")
    mac_arm = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    mac_amd = Platform(os="macos", arch="amd64", immutable=False, has_brew=True)
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    assert any(m.kind == "brew" for m in resolve_methods(podman, mac_arm))
    assert not any(m.kind == "brew" for m in resolve_methods(podman, mac_amd))
    assert any(m.kind == "brew" for m in resolve_methods(podman, linux))


def test_audit_fix_c3_docker_dnf_installs_the_cli() -> None:
    docker = next(t for t in load_tools(REGISTRY) if t.id == "docker")
    dnf = next(m for m in docker.methods if m.kind == "dnf")
    apt = next(m for m in docker.methods if m.kind == "apt")
    pacman = next(m for m in docker.methods if m.kind == "pacman")
    assert dnf.params["package"] == "docker-cli"
    assert apt.params["package"] == "docker.io"
    assert pacman.params["package"] == "docker"
    block = REGISTRY.read_text(encoding="utf-8")
    start = block.index('id = "docker"\nname = "Docker CLI"')
    end = block.index('id = "podman"', start)
    assert "engine" in block[start:end].lower()


def test_audit_fix_c4_uv_does_not_modify_path() -> None:
    uv = next(t for t in load_tools(REGISTRY) if t.id == "uv")
    script = next(m for m in uv.methods if m.kind == "script")
    assert script.params["env"] == {"UV_NO_MODIFY_PATH": "1"}


def test_audit_fix_c5_sdkman_comment_records_5_23_2() -> None:
    block = REGISTRY.read_text(encoding="utf-8")
    start = block.index('id = "sdkman"')
    end = block.index('id = "java"', start)
    sdkman_block = block[start:end]
    assert "5.23.2" in sdkman_block
    assert "unzip" in sdkman_block


def test_audit_fix_c6_colima_recommends_docker() -> None:
    colima = next(t for t in load_tools(REGISTRY) if t.id == "colima")
    assert colima.recommends == ("docker",)


def test_audit_fix_c8_brew_script_is_split_by_arch() -> None:
    brew = next(t for t in load_tools(REGISTRY) if t.id == "brew")
    mac_arm = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    mac_amd = Platform(os="macos", arch="amd64", immutable=False, has_brew=False)
    arm_script = next(m for m in resolve_methods(brew, mac_arm) if m.kind == "script")
    amd_script = next(m for m in resolve_methods(brew, mac_amd) if m.kind == "script")
    assert arm_script.params["bin_dir"] == "/opt/homebrew/bin"
    assert amd_script.params["bin_dir"] == "/usr/local/bin"


def test_audit_fix_d1_difftastic_asset_carries_the_version() -> None:
    from installer.assets import arch_tokens, render_asset

    difftastic = next(t for t in load_tools(REGISTRY) if t.id == "difftastic")
    linux = next(
        m
        for m in difftastic.methods
        if m.kind == "github_release" and m.os == ("debian", "arch", "fedora")
    )
    macos = next(m for m in difftastic.methods if m.kind == "github_release" and m.os == ("macos",))
    amd64 = arch_tokens("amd64")
    ver = "0.71.0"
    assert render_asset(str(linux.params["asset"]), ver, amd64) == (
        "difft-0.71.0-x86_64-unknown-linux-gnu.tar.gz"
    )
    assert render_asset(str(macos.params["asset"]), ver, amd64) == (
        "difft-0.71.0-x86_64-apple-darwin.tar.gz"
    )


def test_audit_fix_d2_delta_macos_release_is_arm64_only() -> None:
    delta = next(t for t in load_tools(REGISTRY) if t.id == "delta")
    macos_method = next(
        m for m in delta.methods if m.kind == "github_release" and m.os == ("macos",)
    )
    assert macos_method.arch == ("arm64",)
    mac_intel = Platform(os="macos", arch="amd64", immutable=False, has_brew=True)
    assert resolve_methods(delta, mac_intel)[0].kind == "brew"


def test_audit_fix_d3_gh_has_a_macos_release() -> None:
    gh = next(t for t in load_tools(REGISTRY) if t.id == "gh")
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    methods = resolve_methods(gh, macos)
    release = next(m for m in methods if m.kind == "github_release")
    assert release.params["asset"] == "gh_{ver}_macOS_{arch.deb}.zip"
    assert release.params["archive"] == "zip"
    assert release.params["member"] == "gh_{ver}_macOS_{arch.deb}/bin/gh"
    assert release.params["checksum"] == "gh_{ver}_checksums.txt"
    assert release.params["strip"] == 0
    assert methods.index(release) < next(i for i, m in enumerate(methods) if m.kind == "brew")


def test_audit_fix_d4_gitui_uses_the_org_repo_and_ships_macos() -> None:
    gitui = next(t for t in load_tools(REGISTRY) if t.id == "gitui")
    releases = [m for m in gitui.methods if m.kind == "github_release"]
    assert all(m.params["repo"] == "gitui-org/gitui" for m in releases)
    mac_arm = next(m for m in releases if m.os == ("macos",) and m.arch == ("arm64",))
    mac_amd = next(m for m in releases if m.os == ("macos",) and m.arch == ("amd64",))
    assert mac_arm.params["asset"] == "gitui-mac.tar.gz"
    assert mac_amd.params["asset"] == "gitui-mac-x86.tar.gz"
    assert mac_arm.params["member"] == "gitui"
    assert mac_arm.params["strip"] == 0


def test_audit_fix_d5_tealdeer_uses_the_org_repo() -> None:
    tealdeer = next(t for t in load_tools(REGISTRY) if t.id == "tealdeer")
    releases = [m for m in tealdeer.methods if m.kind == "github_release"]
    assert len(releases) == 2
    assert all(m.params["repo"] == "tealdeer-rs/tealdeer" for m in releases)


def test_audit_fix_d6_ruff_has_a_uv_tool_method_after_its_releases() -> None:
    ruff = next(t for t in load_tools(REGISTRY) if t.id == "ruff")
    kinds = [m.kind for m in ruff.methods]
    release_indices = [i for i, k in enumerate(kinds) if k == "github_release"]
    uv_index = kinds.index("uv-tool")
    assert uv_index > max(release_indices)
    assert ruff.methods[uv_index].params["pypi_pkg"] == "ruff"
    ladder = resolve_methods(ruff, Platform("fedora", "amd64", False, True))
    assert [m.kind for m in ladder] == ["github_release", "uv-tool", "brew"]


def test_audit_fix_d7_hyperfine_uses_the_musl_assets() -> None:
    from installer.assets import arch_tokens, render_asset

    hyperfine = next(t for t in load_tools(REGISTRY) if t.id == "hyperfine")
    linux = next(
        m
        for m in hyperfine.methods
        if m.kind == "github_release" and m.os == ("debian", "arch", "fedora")
    )
    assert linux.params["member"] == "hyperfine"
    assert linux.params["strip"] == 1
    ver = "1.19.0"
    assert render_asset(str(linux.params["asset"]), ver, arch_tokens("amd64")) == (
        "hyperfine-v1.19.0-x86_64-unknown-linux-musl.tar.gz"
    )
    assert render_asset(str(linux.params["asset"]), ver, arch_tokens("arm64")) == (
        "hyperfine-v1.19.0-aarch64-unknown-linux-musl.tar.gz"
    )


def test_audit_fix_e2_jetbrains_toolbox_ships_linux_arm64() -> None:
    toolbox = _tools_by_id()["jetbrains-toolbox"]
    linux_arm64 = Platform(os="fedora", arch="arm64", immutable=False, has_brew=False)
    methods = resolve_methods(toolbox, linux_arm64)
    assert len(methods) == 1
    arm64 = methods[0]
    assert arm64.kind == "tarball"
    assert arm64.params["url"] == (
        "https://data.services.jetbrains.com/products/download?platform=linuxARM64&code=TBA"
    )
    assert arm64.params["member"] == "bin/jetbrains-toolbox"
    assert arm64.params["strip"] == 1
    linux_amd64 = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    amd64 = resolve_methods(toolbox, linux_amd64)[0]
    assert amd64.params["url"] == (
        "https://data.services.jetbrains.com/products/download?platform=linux&code=TBA"
    )
    block = (
        REGISTRY.read_text(encoding="utf-8")
        .split('id = "jetbrains-toolbox"', 1)[1]
        .split("[[tool]]", 1)[0]
    )
    assert "no arm64 URL" not in block


def test_audit_fix_e4_opencode_script_skips_path_edits() -> None:
    opencode = _tools_by_id()["opencode"]
    script = next(m for m in opencode.methods if m.kind == "script")
    assert script.params.get("args") == ["--no-modify-path"]


def test_audit_fix_e5_jless_linux_release_is_amd64_only() -> None:
    jless = _tools_by_id()["jless"]
    linux = next(
        m
        for m in jless.methods
        if m.kind == "github_release" and m.os == ("debian", "arch", "fedora")
    )
    assert linux.arch == ("amd64",)


def test_audit_fix_e6_broot_macos_release_is_arm64_only() -> None:
    broot = _tools_by_id()["broot"]
    macos = next(m for m in broot.methods if m.kind == "github_release" and m.os == ("macos",))
    assert macos.arch == ("arm64",)


def test_audit_fix_e7_drawio_linux_release_is_checksummed() -> None:
    drawio = _tools_by_id()["drawio-desktop"]
    linux = [
        m
        for m in drawio.methods
        if m.kind == "github_release" and m.os == ("debian", "arch", "fedora")
    ]
    assert len(linux) == 2
    assert all(m.params.get("checksum") == "Files-SHA256-Hashes.txt" for m in linux)


def test_drawio_desktop_declares_its_smoke_argv() -> None:
    drawio = _tools_by_id()["drawio-desktop"]
    linux = [
        m
        for m in drawio.methods
        if m.kind == "github_release" and m.os == ("debian", "arch", "fedora")
    ]
    expected = ["--ozone-platform=headless", "--version"]
    assert all(m.params.get("smoke_argv") == expected for m in linux)


def test_audit_fix_e10_glab_has_native_fallbacks() -> None:
    glab = _tools_by_id()["glab"]
    native = {m.kind: m for m in glab.methods if m.kind in ("dnf", "pacman", "apt")}
    assert set(native) == {"dnf", "pacman", "apt"}
    for method in native.values():
        assert method.params["package"] == "glab"
    assert [m.kind for m in resolve_methods(glab, Platform("fedora", "amd64", False, True))] == [
        "dnf",
        "brew",
    ]
    assert [m.kind for m in resolve_methods(glab, Platform("fedora", "amd64", True, True))] == [
        "brew"
    ]
    assert [m.kind for m in resolve_methods(glab, Platform("debian", "amd64", False, False))] == [
        "apt"
    ]


def test_audit_fix_e11_pi_uninstall_text_does_not_assume_pnpm() -> None:
    pi = _tools_by_id()["pi"]
    text = pi.uninstall.lower()
    assert "pnpm" in text
    assert "volta" in text
    assert "manager that installed" in text


def test_audit_fix_e8_kitty_script_covers_macos() -> None:
    kitty = _tools_by_id()["kitty"]
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    methods = resolve_methods(kitty, macos)
    assert methods[0].kind == "script"
    assert methods[0].params["url"] == "https://sw.kovidgoyal.net/kitty/installer.sh"
    assert methods[0].params.get("args") == ["launch=n"]
    assert methods[0].params["bin_dir"] == "/Applications/kitty.app/Contents/MacOS"
    macos_brew = Platform(
        os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0"
    )
    kinds = [m.kind for m in resolve_methods(kitty, macos_brew)]
    assert kinds[0] == "script"
    assert "cask" in kinds
    linux = next(
        m for m in kitty.methods if m.kind == "script" and m.os == ("debian", "arch", "fedora")
    )
    assert linux.params["bin_dir"] == "~/.local/kitty.app/bin"
    assert linux.os == ("debian", "arch", "fedora")


def test_audit_fix_f1_graphify_records_the_cwd_scope_and_uninstall() -> None:
    graphify = _tools_by_id()["graphify"]
    block = (
        REGISTRY.read_text(encoding="utf-8").split('id = "graphify"', 1)[1].split("[[tool]]", 1)[0]
    )
    assert "project/CWD-scoped" in block or "CWD-scoped" in block
    assert graphify.uninstall == "graphify uninstall; uv tool uninstall graphifyy"


def test_audit_fix_f2_codegraph_comment_records_1_6_2() -> None:
    block = (
        REGISTRY.read_text(encoding="utf-8").split('id = "codegraph"', 1)[1].split("[[tool]]", 1)[0]
    )
    assert "v1.6.2" in block
    assert "UserPromptSubmit" in block or "prompt-hook" in block
    assert "CLAUDE.md" in block
    assert "~/.codegraph/versions" in block
    assert "codegraph upgrade" in block


def test_audit_fix_f3_rtk_comment_records_0_52_0() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    block = (
        text.split('[[tool]]\nid = "rtk"', 1)[0][-2500:]
        + text.split('[[tool]]\nid = "rtk"', 1)[1].split("\n[[tool]]", 1)[0]
    )
    assert "0.52.0" in block
    assert "--opencode" in block
    assert "#2097" in block or "2097" in block


def test_audit_fix_f4_ponytail_probes_pi_and_documents_claude_removal() -> None:
    ponytail = _tools_by_id()["ponytail"]
    assert ponytail.skill_lifecycle is not None
    removal = "\n".join(ponytail.skill_lifecycle.removal.instructions)
    assert "/plugin uninstall ponytail@ponytail" in removal
    probes = ponytail.skill_lifecycle.status_probes
    pi_probe = next((p for p in probes if p.harness == "pi"), None)
    if pi_probe is not None:
        assert pi_probe.via == "plugin-cli"
        assert pi_probe.match == "DietrichGebert/ponytail"
        return
    snippet = (
        REGISTRY.read_text(encoding="utf-8").split('id = "ponytail"', 1)[1].split("[[tool]]", 1)[0]
    )
    assert "/plugin uninstall ponytail@ponytail" in snippet
    tmp_registry = REGISTRY.read_text(encoding="utf-8")
    if (
        '{ harness = "pi", via = "plugin-cli", match = "DietrichGebert/ponytail" }'
        not in tmp_registry
    ):
        pi_probe_row = '{ harness = "pi", via = "plugin-cli", match = "DietrichGebert/ponytail" }'
        codex_probe = '{ harness = "codex", via = "plugin-cli", match = "ponytail" }'
        tmp_registry = tmp_registry.replace(
            codex_probe,
            f"{codex_probe}\n  {pi_probe_row}",
            1,
        )
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as handle:
        handle.write(tmp_registry)
        tmp_path = Path(handle.name)
    try:
        with pytest.raises(ValueError, match="status_probes") as exc:
            load_tools(tmp_path)
        assert "pi" in str(exc.value)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_audit_fix_f5_superpowers_has_one_claude_route() -> None:
    superpowers = _tools_by_id()["superpowers"]
    assert superpowers.skill_lifecycle is not None
    claude = dict(superpowers.skill_lifecycle.install.by_harness)["claude"]
    joined = "\n".join(claude)
    assert "or, instead" not in joined.lower()
    assert "obra/superpowers-marketplace" not in joined
    text = REGISTRY.read_text(encoding="utf-8")
    assert "or, instead, from the obra marketplace" not in text


def test_audit_fix_f6_matt_pocock_default_is_the_plugin_route() -> None:
    matt = _tools_by_id()["matt-pocock-skills"]
    assert matt.skill_lifecycle is not None
    default = "\n".join(matt.skill_lifecycle.install.instructions)
    assert "claude plugin install mattpocock-skills@claude-plugins-official" in default
    assert "codex plugin" in default
    probes = matt.skill_lifecycle.status_probes
    assert any(p.harness == "claude" and p.via == "plugin-cli" for p in probes)


def test_audit_fix_f7_opengsd_notes_node_24() -> None:
    opengsd = _tools_by_id()["opengsd"]
    assert opengsd.skill_lifecycle is not None
    joined = "\n".join(opengsd.skill_lifecycle.install.instructions)
    assert "Node" in joined and "24" in joined


def test_audit_fix_f8_puppeteer_records_cft_linux_arm64() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    anchor = text.index('[[tool]]\nid = "puppeteer"')
    block = text[text.rfind("# Linux arm64: puppeteer", 0, anchor) : anchor]
    assert "linux-arm64" in block
    assert "@puppeteer/browsers" in block
    assert "linux64" in block
