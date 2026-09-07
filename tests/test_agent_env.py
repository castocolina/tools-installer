from pathlib import Path

from installer.agent_env import adapters


def test_adapters_define_supported_agents_with_injected_home_paths(tmp_path: Path) -> None:
    configured = adapters(tmp_path)

    assert set(configured) == {"claude", "codex", "opencode", "pi", "antigravity"}
    assert configured["claude"].config_path == tmp_path / ".claude" / "settings.json"
    assert configured["codex"].config_path == tmp_path / ".codex" / "config.toml"
    assert configured["opencode"].config_path == tmp_path / ".config" / "opencode" / "opencode.json"
    assert configured["pi"].config_path == tmp_path / ".pi"
    assert (
        configured["antigravity"].config_path
        == tmp_path / ".gemini" / "antigravity-cli" / "settings.json"
    )
    assert all(adapter.config_path.is_relative_to(tmp_path) for adapter in configured.values())


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
