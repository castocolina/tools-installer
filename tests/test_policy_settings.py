"""Settings rows in Policies: each agent_settings outcome maps to the UI-SPEC result."""

import json
from pathlib import Path

import pytest

from installer import agent_settings
from installer.agent_settings import CHANGED_WHILE_WRITING, FileResult
from installer.locations import display_path
from installer.policy import Policy, settings_policy


def _claude_row(home: Path, *, claude_installed: bool = True) -> Policy:
    return settings_policy(
        "claude",
        "auto-approve",
        policy_id="agent:claude:auto-approve",
        label="claude auto-approve",
        description="bypassPermissions in ~/.claude/settings.json",
        effect_kind="agent settings",
        fixed=(),
        home=home,
        platform_os="fedora",
        installed_tools={"claude": claude_installed},
    )


def _settings(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def test_settings_policy_results_map_every_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = _settings(tmp_path)
    row = _claude_row(tmp_path)

    wrote = row.apply()
    assert wrote.changed is True
    assert wrote.warning is None
    assert wrote.layers[0].name == display_path(path)
    assert (
        wrote.layers[0].detail == "wrote permissions.defaultMode, skipDangerousModePermissionPrompt"
    )

    removed = row.remove()
    assert removed.changed is True
    assert removed.layers[0].detail == (
        "removed skipDangerousModePermissionPrompt, permissions.defaultMode"
    )
    assert not path.exists()  # the installer created the file, so it goes with the keys

    path.parent.mkdir(exist_ok=True)  # the directory stays after its installer-made file goes
    path.write_text(json.dumps({"permissions": {"defaultMode": "acceptEdits"}}))
    set_by_you = row.apply()
    assert set_by_you.changed is True
    assert set_by_you.layers[0].detail == "wrote skipDangerousModePermissionPrompt"
    assert (
        set_by_you.warning == 'permissions.defaultMode is set by you ("acceptEdits"); left as is.'
    )
    row.remove()

    path.write_text(
        json.dumps(
            {
                "permissions": {"defaultMode": "bypassPermissions"},
                "skipDangerousModePermissionPrompt": True,
            }
        )
    )
    nothing = row.apply()
    assert nothing.changed is False
    assert nothing.warning == (
        "claude auto-approve: nothing to write; "
        "permissions.defaultMode, skipDangerousModePermissionPrompt already hold these values."
    )

    path.unlink()
    row.apply()  # records both keys on a fresh file
    path.write_text(
        json.dumps(
            {"permissions": {"defaultMode": "plan"}, "skipDangerousModePermissionPrompt": True}
        )
    )
    kept = row.remove()
    assert kept.warning == "kept permissions.defaultMode: it changed since this installer wrote it."
    path.unlink()

    path.write_text("{ not json")
    refused = row.apply()
    assert refused.changed is False
    assert refused.warning is not None
    assert refused.warning.startswith("claude auto-approve not changed: ")
    assert "not valid JSON" in refused.warning
    assert refused.warning.endswith("fix it, then press space.")
    assert path.read_text() == "{ not json"


def test_a_changed_while_writing_refusal_leaves_the_row_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    def changed(agent: str, setting: str, *, home: Path, platform_os: str) -> FileResult:
        return FileResult(agent, setting, _settings(home), "json", refused=CHANGED_WHILE_WRITING)

    monkeypatch.setattr(agent_settings, "apply_setting", changed)
    result = _claude_row(tmp_path).apply()
    assert result.changed is False
    assert result.warning == (
        f"claude auto-approve not changed: {display_path(_settings(tmp_path))} "
        "changed while it was being written; press space to retry."
    )


def test_a_settings_row_requires_its_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    absent = _claude_row(tmp_path, claude_installed=False)
    assert absent.requires == ("claude",)
    assert absent.missing_requirements() == ("claude",)
    assert _claude_row(tmp_path).missing_requirements() == ()
