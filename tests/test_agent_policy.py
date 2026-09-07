import json
from pathlib import Path

import pytest

from installer.agent_env import AgentAdapter, adapters
from installer.agent_policy import apply_agent_policy, audit_agent_policy


def _adapter(agent_id: str, home: Path) -> AgentAdapter:
    return adapters(home)[agent_id]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_opencode_policy_allows_external_read_paths_and_denies_edits(
    tmp_path: Path,
) -> None:
    adapter = _adapter("opencode", tmp_path)

    apply_agent_policy(adapter, tmp_path)

    config = json.loads(adapter.config_path.read_text())
    external = config["permission"]["external_directory"]
    edits = config["permission"]["edit"]
    assert external["~/git/**"] == "allow"
    assert edits["~/git/**"] == "deny"
    assert external == {
        "~/.agents/**": "allow",
        "~/.claude/**": "allow",
        "~/.codex/**": "allow",
        "~/.config/opencode/**": "allow",
        "~/.gemini/antigravity-cli/**": "allow",
        "~/.pi/**": "allow",
        "~/git/**": "allow",
    }
    assert edits == {path: "deny" for path in external}


def test_pi_policy_requires_manual_setup(tmp_path: Path) -> None:
    result = apply_agent_policy(_adapter("pi", tmp_path), tmp_path)

    assert result.layers[0].detail == "manual setup required"


def test_managed_guidance_and_reference_are_idempotent_and_preserve_user_text(
    tmp_path: Path,
) -> None:
    adapter = _adapter("opencode", tmp_path)
    guidance = tmp_path / ".agents" / "AGENTS-TOOLING.md"
    guidance.parent.mkdir(parents=True)
    guidance.write_text("# Personal agent notes\n")
    assert adapter.instruction_path is not None
    adapter.instruction_path.parent.mkdir(parents=True)
    adapter.instruction_path.write_text("# OpenCode user instructions\n")

    apply_agent_policy(adapter, tmp_path)
    first_guidance = guidance.read_text()
    first_reference = adapter.instruction_path.read_text()
    apply_agent_policy(adapter, tmp_path)

    assert guidance.read_text() == first_guidance
    assert adapter.instruction_path.read_text() == first_reference
    assert first_guidance.count("<!-- >>> tools-installer shared agent tooling >>>") == 1
    assert first_guidance.count("<!-- <<< tools-installer shared agent tooling <<< -->") == 1
    assert first_guidance.count("rg instead of recursive grep") == 1
    assert "# Personal agent notes" in first_guidance
    assert first_reference.count("# >>> tools-installer agent tooling >>>") == 1
    assert "# OpenCode user instructions" in first_reference
    assert str(guidance) in first_reference


def test_opencode_json_merge_is_idempotent_and_preserves_user_keys(tmp_path: Path) -> None:
    adapter = _adapter("opencode", tmp_path)
    _write_json(
        adapter.config_path,
        {
            "$schema": "https://opencode.ai/config.json",
            "model": "user/model",
            "permission": {"webfetch": "ask"},
        },
    )

    apply_agent_policy(adapter, tmp_path)
    first = adapter.config_path.read_text()
    apply_agent_policy(adapter, tmp_path)
    config = json.loads(adapter.config_path.read_text())

    assert adapter.config_path.read_text() == first
    assert config["$schema"] == "https://opencode.ai/config.json"
    assert config["model"] == "user/model"
    assert config["permission"]["webfetch"] == "ask"
    assert "bash" not in config["permission"]
    assert set(config["permission"]) == {"webfetch", "external_directory", "edit"}


def test_antigravity_adds_only_exact_absolute_read_file_allows(
    tmp_path: Path,
) -> None:
    adapter = _adapter("antigravity", tmp_path)
    existing_rule = "read_file(/user/managed)"
    _write_json(
        adapter.config_path,
        {
            "theme": "user-theme",
            "permissions": {
                "allow": [existing_rule],
                "deny": ["command(rm -rf)"],
            },
        },
    )

    apply_agent_policy(adapter, tmp_path)
    first = adapter.config_path.read_text()
    apply_agent_policy(adapter, tmp_path)
    config = json.loads(adapter.config_path.read_text())

    expected_managed = {
        f"read_file({tmp_path / '.agents'})",
        f"read_file({tmp_path / '.claude'})",
        f"read_file({tmp_path / '.codex'})",
        f"read_file({tmp_path / '.config/opencode'})",
        f"read_file({tmp_path / '.gemini/antigravity-cli'})",
        f"read_file({tmp_path / '.pi'})",
        f"read_file({tmp_path / 'git'})",
    }
    assert adapter.config_path.read_text() == first
    assert config["theme"] == "user-theme"
    assert config["permissions"]["deny"] == ["command(rm -rf)"]
    assert set(config["permissions"]["allow"]) == {existing_rule, *expected_managed}
    assert all(
        rule.startswith("read_file(")
        for rule in config["permissions"]["allow"]
        if rule != existing_rule
    )
    assert not any(
        rule.startswith(("write_file(", "command(", "read_url(", "execute_url("))
        for rule in config["permissions"]["allow"]
        if rule != existing_rule
    )


@pytest.mark.parametrize("agent_id", ["claude", "codex"])
def test_unknown_persistent_formats_are_audit_only(
    agent_id: str,
    tmp_path: Path,
) -> None:
    adapter = _adapter(agent_id, tmp_path)
    adapter.config_path.parent.mkdir(parents=True)
    original = "user configuration\n"
    adapter.config_path.write_text(original)

    result = apply_agent_policy(adapter, tmp_path)

    assert result.layers[0].detail == "audit only; persistent permission format unknown"
    assert adapter.config_path.read_text() == original


def test_audit_reports_not_detected_fixable_manual_and_healthy_states(
    tmp_path: Path,
) -> None:
    opencode = _adapter("opencode", tmp_path)
    pi = _adapter("pi", tmp_path)
    claude = _adapter("claude", tmp_path)

    assert audit_agent_policy(opencode, tmp_path).state == "not-detected"
    _write_json(opencode.config_path, {"model": "user/model"})
    assert audit_agent_policy(opencode, tmp_path).state == "fixable"
    apply_agent_policy(opencode, tmp_path)
    assert audit_agent_policy(opencode, tmp_path).state == "healthy"

    pi.config_path.mkdir(parents=True)
    assert audit_agent_policy(pi, tmp_path).state == "manual-required"
    claude.config_path.parent.mkdir(parents=True)
    claude.config_path.write_text("user config\n")
    claude_audit = audit_agent_policy(claude, tmp_path)
    assert claude_audit.state == "manual-required"
    assert claude_audit.detail == "audit only; persistent permission format unknown"


@pytest.mark.parametrize(
    ("agent_id", "config"),
    [
        ("opencode", "{"),
        ("opencode", "[]"),
        ("opencode", '{"permission": []}'),
        ("opencode", '{"permission": {"external_directory": []}}'),
        ("antigravity", '{"permissions": []}'),
        ("antigravity", '{"permissions": {"allow": {}}}'),
    ],
)
def test_unusable_config_audit_matches_apply_manual_requirement(
    agent_id: str,
    config: str,
    tmp_path: Path,
) -> None:
    adapter = _adapter(agent_id, tmp_path)
    adapter.config_path.parent.mkdir(parents=True)
    adapter.config_path.write_text(config)

    audit = audit_agent_policy(adapter, tmp_path)
    result = apply_agent_policy(adapter, tmp_path)

    assert audit.state == "manual-required"
    assert audit.detail.startswith("manual setup required: ")
    assert audit.detail == result.layers[0].detail
    assert adapter.config_path.read_text() == config


def test_incomplete_guidance_is_fixable_and_apply_converges(
    tmp_path: Path,
) -> None:
    adapter = _adapter("opencode", tmp_path)
    apply_agent_policy(adapter, tmp_path)
    guidance = tmp_path / ".agents" / "AGENTS-TOOLING.md"
    guidance.write_text(
        "# User before\n"
        "<!-- >>> tools-installer shared agent tooling >>>\n"
        "stale managed content\n"
        "# User after\n"
    )

    assert audit_agent_policy(adapter, tmp_path).state == "fixable"

    apply_agent_policy(adapter, tmp_path)
    first = guidance.read_text()
    apply_agent_policy(adapter, tmp_path)

    assert audit_agent_policy(adapter, tmp_path).state == "healthy"
    assert guidance.read_text() == first
    assert first.count("<!-- >>> tools-installer shared agent tooling >>>") == 1
    assert first.count("<!-- <<< tools-installer shared agent tooling <<< -->") == 1
    assert first.count("rg instead of recursive grep") == 1
    assert "stale managed content" in first
    assert "# User before" in first
    assert "# User after" in first


def test_orphan_before_complete_block_preserves_intervening_user_text(
    tmp_path: Path,
) -> None:
    adapter = _adapter("opencode", tmp_path)
    apply_agent_policy(adapter, tmp_path)
    guidance = tmp_path / ".agents" / "AGENTS-TOOLING.md"
    guidance.write_text(
        "# User before\n"
        "<!-- >>> tools-installer shared agent tooling >>>\n"
        "# User between\n"
        "<!-- >>> tools-installer shared agent tooling >>>\n"
        "stale managed content\n"
        "<!-- <<< tools-installer shared agent tooling <<< -->\n"
        "# User after\n"
    )

    apply_agent_policy(adapter, tmp_path)
    updated = guidance.read_text()

    assert audit_agent_policy(adapter, tmp_path).state == "healthy"
    assert "# User before" in updated
    assert "# User between" in updated
    assert "# User after" in updated
    assert "stale managed content" not in updated
    assert updated.count("<!-- >>> tools-installer shared agent tooling >>>") == 1
    assert updated.count("<!-- <<< tools-installer shared agent tooling <<< -->") == 1


def test_stale_reference_is_fixable_and_apply_converges(
    tmp_path: Path,
) -> None:
    adapter = _adapter("opencode", tmp_path)
    apply_agent_policy(adapter, tmp_path)
    assert adapter.instruction_path is not None
    adapter.instruction_path.write_text(
        "# User before\n"
        "# >>> tools-installer agent tooling >>>\n"
        "Read /stale/guidance.md for shared tool guidance.\n"
        "# <<< tools-installer agent tooling <<<\n"
        "# User after\n"
    )

    assert audit_agent_policy(adapter, tmp_path).state == "fixable"

    apply_agent_policy(adapter, tmp_path)
    first = adapter.instruction_path.read_text()
    apply_agent_policy(adapter, tmp_path)

    assert audit_agent_policy(adapter, tmp_path).state == "healthy"
    assert adapter.instruction_path.read_text() == first
    assert first.count("# >>> tools-installer agent tooling >>>") == 1
    assert first.count("# <<< tools-installer agent tooling <<<") == 1
    assert f"Read {tmp_path / '.agents/AGENTS-TOOLING.md'} for shared tool guidance." in first
    assert "Read /stale/guidance.md" not in first
    assert "# User before" in first
    assert "# User after" in first


def test_policy_rejects_adapter_paths_outside_injected_home(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-opencode.json"
    adapter = AgentAdapter(
        id="opencode",
        label="OpenCode",
        config_path=outside,
        instruction_path=None,
        permission_mode="configurable",
    )

    with pytest.raises(ValueError, match="outside injected home"):
        apply_agent_policy(adapter, tmp_path)

    assert not outside.exists()


def test_policy_rejects_guidance_symlink_outside_injected_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    home.mkdir()
    outside.mkdir()
    (home / ".agents").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="outside injected home"):
        apply_agent_policy(_adapter("pi", home), home)

    assert list(outside.iterdir()) == []


def test_antigravity_rules_are_absolute_when_injected_home_is_relative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    relative_home = Path("fixture-home")
    adapter = _adapter("antigravity", relative_home)

    apply_agent_policy(adapter, relative_home)

    config = json.loads(adapter.config_path.read_text())
    expected_root = (tmp_path / relative_home).resolve()
    assert f"read_file({expected_root / 'git'})" in config["permissions"]["allow"]
    assert all(rule.startswith("read_file(/") for rule in config["permissions"]["allow"])
