from pathlib import Path

from installer.agent_env import adapters


def test_adapters_define_supported_agents_with_injected_home_paths(tmp_path: Path) -> None:
    configured = adapters(tmp_path)

    assert set(configured) == {
        "claude",
        "codex",
        "opencode",
        "pi",
        "antigravity",
        "cursor-agent",
        "vscode",
        "copilot",
        "herdr",
    }
    assert configured["herdr"].config_path == tmp_path / ".config" / "herdr" / "config.toml"
    assert configured["claude"].config_path == tmp_path / ".claude" / "settings.json"
    assert configured["codex"].config_path == tmp_path / ".codex" / "config.toml"
    assert configured["opencode"].config_path == tmp_path / ".config" / "opencode" / "opencode.json"
    assert configured["pi"].config_path == tmp_path / ".pi"
    assert (
        configured["antigravity"].config_path
        == tmp_path / ".gemini" / "antigravity-cli" / "settings.json"
    )
    assert all(adapter.config_path.is_relative_to(tmp_path) for adapter in configured.values())


def test_adapters_add_cursor_agent_and_vscode(tmp_path: Path) -> None:
    linux = adapters(tmp_path)

    assert linux["cursor-agent"].config_path == tmp_path / ".cursor" / "cli-config.json"
    assert linux["vscode"].config_path == tmp_path / ".config" / "Code" / "User" / "settings.json"
    assert (
        adapters(tmp_path, platform_os="fedora")["vscode"].config_path
        == linux["vscode"].config_path
    )
    assert adapters(tmp_path, platform_os="macos")["vscode"].config_path == (
        tmp_path / "Library" / "Application Support" / "Code" / "User" / "settings.json"
    )
    assert linux["claude"].config_path == tmp_path / ".claude" / "settings.json"


def test_pi_is_an_audit_only_adapter(tmp_path: Path) -> None:
    adapter = adapters(tmp_path)["pi"]

    assert adapter.permission_mode == "audit-only"


def test_adapters_define_native_instruction_paths_when_supported(tmp_path: Path) -> None:
    configured = adapters(tmp_path)

    assert configured["claude"].instruction_path == tmp_path / ".claude" / "CLAUDE.md"
    assert configured["codex"].instruction_path == tmp_path / ".codex" / "AGENTS.md"
    assert configured["opencode"].instruction_path == (
        tmp_path / ".config" / "opencode" / "AGENTS.md"
    )
    assert configured["pi"].instruction_path == tmp_path / ".pi" / "AGENTS.md"
    assert configured["antigravity"].instruction_path == tmp_path / ".gemini" / "GEMINI.md"


def test_copilot_adapter_honours_an_absolute_copilot_home(tmp_path: Path) -> None:
    ch = tmp_path / "ch"
    copilot = adapters(tmp_path / "home", "linux", environ={"COPILOT_HOME": str(ch)})["copilot"]

    assert copilot.config_path == ch / "settings.json"
    assert copilot.label == "GitHub Copilot CLI"
    assert copilot.instruction_path is None
    assert copilot.permission_mode == "configurable"


def test_copilot_adapter_ignores_an_empty_or_relative_copilot_home(tmp_path: Path) -> None:
    # A relative value resolves against copilot's own working directory, unknowable here.
    default = tmp_path / ".copilot" / "settings.json"

    assert adapters(tmp_path)["copilot"].config_path == default
    assert adapters(tmp_path, environ={})["copilot"].config_path == default
    assert adapters(tmp_path, environ={"COPILOT_HOME": ""})["copilot"].config_path == default
    assert adapters(tmp_path, environ={"COPILOT_HOME": "rel/ch"})["copilot"].config_path == default


def test_herdr_adapter_path(tmp_path: Path) -> None:
    # herdr's own config_path() order: HERDR_CONFIG_PATH, then XDG_CONFIG_HOME, then ~/.config.
    default = tmp_path / ".config" / "herdr" / "config.toml"

    def herdr_path(environ: dict[str, str] | None) -> Path:
        return adapters(tmp_path, environ=environ)["herdr"].config_path

    assert herdr_path({"HERDR_CONFIG_PATH": "/abs/h.toml"}) == Path("/abs/h.toml")
    assert herdr_path({"XDG_CONFIG_HOME": "/x"}) == Path("/x/herdr/config.toml")
    both = {"HERDR_CONFIG_PATH": "/abs/h.toml", "XDG_CONFIG_HOME": "/x"}
    assert herdr_path(both) == Path("/abs/h.toml")
    relative = {"HERDR_CONFIG_PATH": "rel.toml", "XDG_CONFIG_HOME": "/x"}
    assert herdr_path(relative) == Path("/x/herdr/config.toml")
    assert herdr_path({"HERDR_CONFIG_PATH": "", "XDG_CONFIG_HOME": "rel"}) == default
    assert herdr_path({}) == default
    assert herdr_path(None) == default
    herdr = adapters(tmp_path)["herdr"]
    assert herdr.label == "herdr"
    assert herdr.instruction_path is None
    assert herdr.permission_mode == "unknown"


def test_herdr_home_changes_no_other_adapter(tmp_path: Path) -> None:
    plain = adapters(tmp_path)
    tweaked = adapters(tmp_path, environ={"HERDR_CONFIG_PATH": str(tmp_path / "h.toml")})

    assert {k: v for k, v in tweaked.items() if k != "herdr"} == {
        k: v for k, v in plain.items() if k != "herdr"
    }


def test_copilot_home_changes_no_other_adapter(tmp_path: Path) -> None:
    plain = adapters(tmp_path)
    tweaked = adapters(tmp_path, environ={"COPILOT_HOME": str(tmp_path / "ch")})

    assert {k: v for k, v in tweaked.items() if k != "copilot"} == {
        k: v for k, v in plain.items() if k != "copilot"
    }
