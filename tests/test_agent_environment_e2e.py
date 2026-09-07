import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from installer.agent_env import adapters
from installer.agent_policy import (
    apply_agent_guidance,
    apply_agent_permissions,
    audit_agent_policy,
)
from installer.policy import compose_agent_environment_policy

Runner = Callable[[list[str]], None]


@dataclass(frozen=True)
class ApplySummary:
    fixed: tuple[str, ...]
    healthy: tuple[str, ...]
    manual_required: tuple[str, ...]


def apply_all_detected_agents(home: Path, *, runner: Runner) -> ApplySummary:
    """Exercise the same audit/apply boundary as the UI without host commands."""
    del runner
    fixed: list[str] = []
    healthy: list[str] = []
    manual_required: list[str] = []

    for adapter in adapters(home).values():
        audit = audit_agent_policy(adapter, home)
        if audit.state == "not-detected":
            continue
        policy = compose_agent_environment_policy(
            adapter,
            home=home,
            audit_agent=audit_agent_policy,
            apply_agent=apply_agent_permissions,
            apply_guidance=apply_agent_guidance,
        )
        if audit.state == "healthy":
            healthy.append(adapter.id)
        elif audit.state == "fixable":
            assert policy.apply is not None
            policy.apply()
            refreshed = audit_agent_policy(adapter, home)
            if refreshed.state != "healthy":
                raise AssertionError(f"{adapter.id} did not converge: {refreshed.state}")
            fixed.append(adapter.id)
        else:
            if policy.apply is not None:
                policy.apply()
                refreshed = audit_agent_policy(adapter, home)
                if refreshed.guidance_pending:
                    raise AssertionError(f"{adapter.id} guidance did not converge")
            manual_required.append(adapter.id)

    return ApplySummary(tuple(fixed), tuple(healthy), tuple(manual_required))


def _copy_fixture_home(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixture"
    files = {
        ".claude/settings.json": '{"model": "user-claude-model"}\n',
        ".claude/CLAUDE.md": "# Existing Claude instructions\n",
        ".codex/config.toml": 'model = "user-codex-model"\n',
        ".codex/AGENTS.md": "# Existing Codex instructions\n",
        ".config/opencode/opencode.json": json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "model": "user/opencode-model",
                "permission": {"webfetch": "ask"},
            }
        ),
        ".config/opencode/AGENTS.md": "# Existing OpenCode instructions\n",
        ".pi/AGENTS.md": "# Existing Pi instructions\n",
        ".gemini/GEMINI.md": "# Existing Antigravity instructions\n",
        ".gemini/antigravity-cli/settings.json": json.dumps(
            {
                "theme": "user-theme",
                "permissions": {
                    "allow": ["read_file(/user/managed)"],
                    "deny": ["command(rm -rf)"],
                },
            }
        ),
    }
    for relative, content in files.items():
        path = fixture / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    home = tmp_path / "home"
    shutil.copytree(fixture, home)
    return home


def test_agent_policy_is_idempotent_in_a_temporary_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _copy_fixture_home(tmp_path)
    ambient_home = tmp_path / "ambient-home-must-remain-absent"
    monkeypatch.setenv("HOME", str(ambient_home))
    commands: list[list[str]] = []

    first = apply_all_detected_agents(home, runner=commands.append)
    second = apply_all_detected_agents(home, runner=commands.append)

    assert first.fixed == ("opencode", "antigravity")
    assert first.fixed == second.healthy
    assert first.manual_required == ("claude", "codex", "pi")
    assert second.manual_required == first.manual_required
    assert (home / ".agents" / "AGENTS-TOOLING.md").read_text().count("rg instead") == 1
    reference_paths = (
        home / ".claude/CLAUDE.md",
        home / ".codex/AGENTS.md",
        home / ".config/opencode/AGENTS.md",
        home / ".pi/AGENTS.md",
        home / ".gemini/GEMINI.md",
    )
    for reference_path in reference_paths:
        content = reference_path.read_text()
        assert content.count("# >>> tools-installer agent tooling >>>") == 1
        assert str(home / ".agents/AGENTS-TOOLING.md") in content
        assert "Existing" in content
    assert commands == []
    assert not ambient_home.exists()

    opencode = json.loads((home / ".config/opencode/opencode.json").read_text())
    assert set(opencode["permission"]) == {"webfetch", "external_directory", "edit"}
    assert set(opencode["permission"]["external_directory"].values()) == {"allow"}
    assert set(opencode["permission"]["edit"].values()) == {"deny"}

    antigravity = json.loads((home / ".gemini/antigravity-cli/settings.json").read_text())
    managed_rules = [
        rule for rule in antigravity["permissions"]["allow"] if rule != "read_file(/user/managed)"
    ]
    assert managed_rules
    assert all(rule.startswith("read_file(") for rule in managed_rules)
    assert not any(rule.startswith(("write_file(", "command(")) for rule in managed_rules)


def test_gemini_instruction_only_does_not_detect_or_configure_antigravity(
    tmp_path: Path,
) -> None:
    """A shared Gemini instruction file is not Antigravity installation evidence."""
    home = tmp_path / "home"
    gemini_instruction = home / ".gemini" / "GEMINI.md"
    gemini_instruction.parent.mkdir(parents=True)
    gemini_instruction.write_text("# Gemini user instructions\n")
    adapter = adapters(home)["antigravity"]

    audit = audit_agent_policy(adapter, home)
    policy = compose_agent_environment_policy(
        adapter,
        home=home,
        audit_agent=audit_agent_policy,
        apply_agent=apply_agent_permissions,
        apply_guidance=apply_agent_guidance,
    )
    summary = apply_all_detected_agents(home, runner=lambda _command: None)

    assert audit.state == "not-detected"
    assert policy.apply is None
    assert policy.action_detail is None
    assert summary == ApplySummary((), (), ())
    assert gemini_instruction.read_text() == "# Gemini user instructions\n"
    assert not (home / ".gemini" / "antigravity-cli" / "settings.json").exists()
    assert not (home / ".agents" / "AGENTS-TOOLING.md").exists()
