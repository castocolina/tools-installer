"""Settings rows in Policies: each agent_settings outcome maps to the UI-SPEC result."""

import json
from pathlib import Path

import pytest

from installer import agent_settings
from installer.agent_settings import CHANGED_WHILE_WRITING, FileResult
from installer.env_redirect import DESKTOP_SHELL_CONF
from installer.locations import display_path
from installer.policy import (
    Policy,
    PolicyLayer,
    desktop_shell_policy,
    settings_policies,
    settings_policy,
    tweak_policy,
)
from installer.tweaks import shell_init_bundle
from installer.uninstall import active_policies, sweep_policies


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

    # Both keys recorded; the user then sets the skip key to false. Nothing is absent, and the
    # state is on, so this is not the yours refusal: apply reports nothing to write.
    path.unlink()
    row.apply()
    path.write_text(
        json.dumps(
            {
                "permissions": {"defaultMode": "bypassPermissions"},
                "skipDangerousModePermissionPrompt": False,
            }
        )
    )
    nothing = row.apply()
    assert nothing.changed is False
    assert nothing.warning == (
        "claude auto-approve: nothing to write; permissions.defaultMode already hold these values. "
        "skipDangerousModePermissionPrompt is set by you (false); left as is."
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


SHELL_INIT_IDS = ("starship", "direnv", "zoxide", "fzf", "fnm", "volta")


def _shell_init_row(home: Path, tool: str) -> Policy:
    bundle = shell_init_bundle(tool)
    assert bundle is not None
    return tweak_policy(
        bundle,
        rc_path=home / ".myshellrc",
        bin_dir=home / ".local" / "bin",
        installed_tools={tool: True},
    )


def test_policies_list_the_new_rows_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    shell = tuple(_shell_init_row(tmp_path, tool) for tool in SHELL_INIT_IDS)
    settings = settings_policies(home=tmp_path, platform_os="fedora", installed_tools={})
    desktop = desktop_shell_policy(
        zsh_path=None, conf_dir=tmp_path / "environment.d", home=tmp_path
    )
    rows = (*shell, *settings, desktop)
    assert [row.id for row in shell] == [f"tweak:{tool}" for tool in SHELL_INIT_IDS]
    assert [row.id for row in settings] == [
        "agent:claude:auto-approve",
        "agent:claude:no-attribution",
        "agent:codex:auto-approve",
        "agent:opencode:auto-approve",
        "agent:cursor-agent:auto-approve",
        "agent:cursor-agent:no-attribution",
        "vscode:lean",
        "vscode:ai-off",
        "vscode:ext-updates-off",
    ]
    assert desktop.label == "SHELL for desktop apps"
    assert all(len(row.label) <= 28 for row in rows)


def test_shell_init_rows_show_their_detail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zoxide = _shell_init_row(tmp_path, "zoxide")
    assert zoxide.detail_lines is not None
    assert zoxide.detail_lines() == (
        "Adds zoxide's shell init to ~/.myshellrc, guarded by command -v zoxide.",
        "Adds z, a cd that learns the directories you use.",
        "Turned off automatically when zoxide is removed.",
    )
    assert zoxide.effect_kind is None  # the Effect cell prefix is the row's own description
    assert zoxide.description == "adds z, a cd that learns the directories you use"
    starship = _shell_init_row(tmp_path, "starship")
    assert starship.detail_lines is not None
    lines = starship.detail_lines()
    assert len(lines) == 4
    assert lines[-1] == (
        'Sets ZSH_THEME="" in ~/.zshrc so Oh-My-Zsh draws no prompt; turning it off leaves '
        "the theme line as it is."
    )


def test_the_desktop_shell_row_writes_environment_d(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zsh = tmp_path / "bin" / "zsh"
    zsh.parent.mkdir()
    zsh.write_text("")
    conf = tmp_path / ".config" / "environment.d" / DESKTOP_SHELL_CONF
    row = desktop_shell_policy(zsh_path=str(zsh), conf_dir=conf.parent, home=tmp_path)
    assert row.is_active is not None and row.is_active() is False
    result = row.apply()
    assert f"SHELL={zsh}" in conf.read_text()
    assert result.layers == (PolicyLayer("environment.d", f"wrote {DESKTOP_SHELL_CONF}"),)
    assert result.reload_hint == "Log out and back in for desktop apps to see it."
    assert row.is_active is not None and row.is_active() is True
    row.remove()
    assert not conf.exists()


def test_a_desktop_shell_file_outlives_zsh_and_is_still_swept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zsh = tmp_path / "bin" / "zsh"
    zsh.parent.mkdir()
    zsh.write_text("")
    conf = tmp_path / ".config" / "environment.d" / DESKTOP_SHELL_CONF
    desktop_shell_policy(zsh_path=str(zsh), conf_dir=conf.parent, home=tmp_path).apply()
    gone = desktop_shell_policy(zsh_path=None, conf_dir=conf.parent, home=tmp_path)
    assert gone.description == "SHELL=zsh in ~/.config/environment.d"
    assert gone.active is False
    assert gone.owned is not None and gone.owned() is True
    moved = desktop_shell_policy(
        zsh_path=str(tmp_path / "other" / "zsh"), conf_dir=conf.parent, home=tmp_path
    )
    assert moved.owned is not None and moved.owned() is True
    gone.remove()
    assert not conf.exists()


def test_vscode_and_cursor_details_follow_the_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    def rows(platform_os: str) -> dict[str, Policy]:
        found = settings_policies(home=tmp_path, platform_os=platform_os, installed_tools={})
        return {row.id: row for row in found}

    def details(platform_os: str, policy_id: str) -> tuple[str, ...]:
        detail = rows(platform_os)[policy_id].detail_lines
        assert detail is not None
        return detail()

    assert "update.mode is not written on Linux: this installer updates VS Code." in details(
        "fedora", "vscode:lean"
    )
    assert "update.mode is set to none: this installer updates VS Code." in details(
        "macos", "vscode:lean"
    )
    assert (
        "The Cursor CLI ignores the commit opt-out as of 2026-10-04; the PR opt-out works."
        in details("fedora", "agent:cursor-agent:no-attribution")
    )
    assert (
        "codex, opencode and pi have no documented attribution key; nothing is written for them."
        in details("fedora", "agent:claude:no-attribution")
    )


def test_the_desktop_shell_row_is_swept_by_its_sentinel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard (written after the implementation): uninstall's sweep path finds the
    conf by its sentinel, even after zsh has gone, and never touches a foreign file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    zsh = tmp_path / "bin" / "zsh"
    zsh.parent.mkdir()
    zsh.write_text("")
    conf = tmp_path / ".config" / "environment.d" / DESKTOP_SHELL_CONF
    desktop_shell_policy(zsh_path=str(zsh), conf_dir=conf.parent, home=tmp_path).apply()
    moved = desktop_shell_policy(zsh_path=None, conf_dir=conf.parent, home=tmp_path)
    listed = active_policies(
        (),
        rc_path=tmp_path / ".myshellrc",
        bin_dir=tmp_path / ".local" / "bin",
        extra_policies=(moved,),
    )
    assert [policy.id for policy in listed] == ["desktop-shell"]
    sweep_policies(listed)
    assert not conf.exists()

    conf.write_text("SHELL=/bin/bash\n", encoding="utf-8")  # no sentinel: not ours
    foreign = active_policies(
        (),
        rc_path=tmp_path / ".myshellrc",
        bin_dir=tmp_path / ".local" / "bin",
        extra_policies=(moved,),
    )
    assert foreign == []
    sweep_policies(foreign)
    assert conf.read_text(encoding="utf-8") == "SHELL=/bin/bash\n"
