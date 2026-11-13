import os
import re
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from installer import agent_settings, post_install
from installer.agent_settings import parse_settings
from installer.model import (
    POST_INSTALL_ACTIONS,
    POSTINSTALL_HOOK_NAMES,
    SENSITIVE_POST_INSTALL_ACTIONS,
    Method,
    Tool,
    load_tools,
)
from installer.platform import Platform
from installer.post_install import (
    POST_INSTALL_HOOKS,
    SENSITIVE_PROMPTS,
    ConfirmSensitiveAction,
    PostInstallOutput,
    apply_install_tuning,
    run_post_install,
    sensitive_prompt,
    use_shell_init_sourcing,
)
from installer.postinstall import POSTINSTALL_HOOKS
from installer.receipts import read_ledger
from installer.shellrc import write_myshellrc
from installer.tweaks import (
    SHELL_INIT_TOOLS,
    TweakBundle,
    record_shell_init,
    shell_init_bundle,
    shell_init_record,
    strip_tweak_block,
    write_tweak,
)

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _mutable() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def _immutable() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)


def _tool(
    *,
    post_install: tuple[str, ...] = (),
    default_enabled_sensitive_actions: tuple[str, ...] = (),
) -> Tool:
    return Tool(
        id="oh-my-zsh",
        name="Oh My Zsh",
        category="shell",
        cmd="omz",
        methods=(Method(kind="script", params={"url": "u"}),),
        post_install=post_install,
        default_enabled_sensitive_actions=default_enabled_sensitive_actions,
    )


def _login_shell_tool(
    *,
    default_enabled: bool = False,
) -> Tool:
    enabled = ("set_login_shell",) if default_enabled else ()
    return _tool(
        post_install=("set_login_shell",),
        default_enabled_sensitive_actions=enabled,
    )


def _stub_chsh(monkeypatch: pytest.MonkeyPatch, *, present: bool) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if present and cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)


def _record() -> tuple[list[tuple[str, str]], ConfirmSensitiveAction]:
    asked: list[tuple[str, str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    return asked, confirm


def test_real_oh_my_zsh_entry_declares_set_login_shell() -> None:
    tools = {tool.id: tool for tool in load_tools(REGISTRY)}
    assert "set_login_shell" in tools["oh-my-zsh"].post_install


def test_run_post_install_returns_chsh_instructions_without_asking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=True)
    asked, confirm = _record()
    lines = run_post_install(_tool(post_install=("set_login_shell",)), _mutable(), confirm).lines
    assert lines
    assert any("chsh -s" in line for line in lines)
    assert asked == []


def test_run_post_install_returns_a_post_install_output() -> None:
    output = run_post_install(_tool(post_install=("show_lean_tips",)), _mutable())
    assert isinstance(output, PostInstallOutput)
    assert output.lines and output.lines[0].startswith("Lean tip")
    assert output.settings == ()


def test_apply_agent_tuning_contributes_a_file_result_per_group_and_no_line() -> None:
    from installer.agent_settings import TUNING_GROUPS

    claude = replace(_tool(post_install=("apply_agent_tuning",)), id="claude")
    output = run_post_install(claude, _mutable())
    assert output.lines == ()
    assert [result.setting for result in output.settings] == list(TUNING_GROUPS["claude"])
    assert all(result.agent == "claude" for result in output.settings)


def test_copilot_tuning_follows_copilot_home_and_removal_reverts_that_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer import app as app_module

    ch = tmp_path / "ch"
    monkeypatch.setenv("COPILOT_HOME", str(ch))
    copilot = replace(_tool(post_install=("apply_agent_tuning",)), id="copilot")

    output = run_post_install(copilot, _mutable())

    assert [result.refused for result in output.settings] == [None, None]
    assert parse_settings((ch / "settings.json").read_text(encoding="utf-8"), "jsonc") == {
        "defaultPermissionMode": "allow-all",
        "includeCoAuthoredBy": False,
    }
    revert = app_module._revert_settings(  # pyright: ignore[reportPrivateUsage]
        ("copilot",), platform_os="linux"
    )
    assert revert == (("copilot",), (), ())
    assert not (ch / "settings.json").exists()


def test_run_post_install_skips_when_no_actions_declared() -> None:
    asked: list[tuple[str, str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    assert run_post_install(_tool(), _mutable(), confirm).lines == ()
    assert asked == []


def test_missing_chsh_explains_without_asking_or_offering_a_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=False)
    asked, confirm = _record()
    lines = run_post_install(_login_shell_tool(), _immutable(), confirm).lines
    assert lines
    assert not any("chsh -s" in line for line in lines)
    assert any("removed chsh" in line for line in lines)
    assert any("terminal emulator" in line for line in lines)
    assert asked == []


def test_missing_chsh_explains_on_mutable_hosts_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=False)
    asked, confirm = _record()
    lines = run_post_install(_login_shell_tool(), _mutable(), confirm).lines
    assert lines
    assert asked == []
    assert not any("chsh -s" in line for line in lines)


def test_missing_chsh_explains_without_a_confirm_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=False)
    lines = run_post_install(_login_shell_tool(), _immutable(), None).lines
    assert lines
    assert not any("chsh -s" in line for line in lines)


def test_immutable_host_with_chsh_prints_the_command_without_asking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=True)
    asked, confirm = _record()
    lines = run_post_install(_login_shell_tool(), _immutable(), confirm).lines
    assert any("chsh -s" in line for line in lines)
    assert asked == []


def test_missing_chsh_cannot_be_silenced_via_default_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=False)
    asked, confirm = _record()
    lines = run_post_install(_login_shell_tool(default_enabled=True), _immutable(), confirm).lines
    assert lines
    assert asked == []


def test_set_login_shell_prints_the_handoff_without_asking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=True)
    with_chsh = run_post_install(_login_shell_tool(), _mutable(), None).lines
    assert with_chsh == (
        "After leaving the installer, run this command in your own terminal "
        "to set zsh as your login shell:",
        "chsh -s $(which zsh)",
        "Then log out and back in for the change to take effect.",
    )
    _stub_chsh(monkeypatch, present=False)
    without_chsh = run_post_install(_login_shell_tool(), _mutable(), None).lines
    assert any("removed chsh" in line for line in without_chsh)
    assert not any("chsh -s" in line for line in without_chsh)  # never both


def test_set_login_shell_ignores_a_refusing_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_chsh(monkeypatch, present=True)
    asked: list[tuple[str, str]] = []

    def refuse(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return False

    lines = run_post_install(_login_shell_tool(), _mutable(), refuse).lines
    assert any("chsh -s" in line for line in lines)
    assert asked == []


def test_sensitive_tables_are_empty() -> None:
    assert SENSITIVE_POST_INSTALL_ACTIONS == ()
    assert SENSITIVE_PROMPTS == {}
    for action in ("set_login_shell", "source_shell_init"):
        with pytest.raises(KeyError):
            sensitive_prompt("oh-my-zsh", action)


def test_unknown_post_install_action_name_is_inert() -> None:
    asked, confirm = _record()
    assert (
        run_post_install(_tool(post_install=("not-a-real-action",)), _mutable(), confirm).lines
        == ()
    )
    assert asked == []


def test_post_install_tables_are_disjoint_and_match_their_schema_sets() -> None:
    actions = set(POST_INSTALL_HOOKS)
    hooks = set(POSTINSTALL_HOOKS)
    hook_names = set(POSTINSTALL_HOOK_NAMES)
    action_names = set(POST_INSTALL_ACTIONS)
    sensitive = set(SENSITIVE_POST_INSTALL_ACTIONS)
    assert actions & hook_names == set(), sorted(actions & hook_names)
    assert hooks & action_names == set(), sorted(hooks & action_names)
    assert actions <= action_names, sorted(actions - action_names)
    assert hooks == hook_names, sorted(hooks.symmetric_difference(hook_names))
    assert sensitive <= actions, sorted(sensitive - actions)


def test_docstring_keeps_post_install_dispatch_on_the_install_ladder() -> None:
    import installer.post_install as module

    text = " ".join((module.__doc__ or "").split())
    assert "SKIP on the review" in text
    assert "REINSTALL" in text
    assert "successful reinstall dispatches actions once more" in text
    assert "No path re-applies post-install actions on their own (D-06)" in text


_OMZ_ZSHRC = 'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git)\nsource $ZSH/oh-my-zsh.sh\n'


def _shell_init_tool(tool_id: str) -> Tool:
    tools = {tool.id: tool for tool in load_tools(REGISTRY)}
    return replace(tools[tool_id], post_install=("source_shell_init",))


def _yes(_tool_id: str, _action: str) -> bool:
    return True


def test_starship_yes_turns_shell_init_on_and_empties_the_theme() -> None:
    home = Path.home()
    zshrc = home / ".zshrc"
    zshrc.write_text(_OMZ_ZSHRC)
    lines = run_post_install(
        _shell_init_tool("starship"),
        _mutable(),
        lambda tool_id, action: action == "source_shell_init",
    ).lines
    assert lines == ("Shell init on: open a new terminal to use it.",)
    assert "# >>> tools-installer tweak:starship >>>" in (home / ".myshellrc").read_text()
    assert "starship init zsh" in (home / ".myshellrc").read_text()
    rc_lines = zshrc.read_text().split("\n")
    theme = rc_lines.index('ZSH_THEME=""')
    assert rc_lines[theme + 1] == "source $ZSH/oh-my-zsh.sh"


def test_a_split_mode_yes_wires_the_rc_files_to_source_myshellrc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = Path.home()
    zshrc, bashrc, profile = home / ".zshrc", home / ".bashrc", home / ".profile"
    monkeypatch.setattr(post_install, "_shell_init_sourced_from", lambda: (zshrc, bashrc))
    run_post_install(_shell_init_tool("zoxide"), _mutable(), _yes)
    assert "# >>> tools-installer tweak:zoxide >>>" in (home / ".myshellrc").read_text()
    for rc in (zshrc, bashrc):
        assert "# >>> tools-installer source >>>" in rc.read_text()
        assert str(home / ".myshellrc") in rc.read_text()
    use_shell_init_sourcing(lambda: (profile,))
    run_post_install(_shell_init_tool("zoxide"), _mutable(), _yes)
    assert "# >>> tools-installer source >>>" in profile.read_text()


def test_the_default_reader_wires_no_rc_file() -> None:
    home = Path.home()
    run_post_install(_shell_init_tool("zoxide"), _mutable(), _yes)
    assert (home / ".myshellrc").exists()
    assert not (home / ".zshrc").exists()
    assert not (home / ".bashrc").exists()


def test_headless_zoxide_install_writes_its_shell_init_with_no_prompt() -> None:
    home = Path.home()
    lines = run_post_install(_shell_init_tool("zoxide"), _mutable(), None).lines
    assert lines == ("Shell init on: open a new terminal to use it.",)
    assert "# >>> tools-installer tweak:zoxide >>>" in (home / ".myshellrc").read_text()
    assert shell_init_record(home / ".myshellrc") == ("zoxide",)


def test_headless_starship_install_writes_its_block_and_the_empty_theme() -> None:
    home = Path.home()
    zshrc = home / ".zshrc"
    zshrc.write_text(_OMZ_ZSHRC)
    run_post_install(_shell_init_tool("starship"), _mutable(), None)
    assert "starship init zsh" in (home / ".myshellrc").read_text()
    assert 'ZSH_THEME=""' in zshrc.read_text()
    assert shell_init_record(home / ".myshellrc") == ("starship",)


def test_shell_init_reinstall_leaves_one_block() -> None:
    home = Path.home()
    for _ in range(2):
        run_post_install(_shell_init_tool("zoxide"), _mutable(), None)
    text = (home / ".myshellrc").read_text()
    assert text.count("# >>> tools-installer tweak:zoxide >>>") == 1
    assert shell_init_record(home / ".myshellrc") == ("zoxide",)


def test_shell_init_missing_myshellrc_is_created() -> None:
    rc = Path.home() / ".myshellrc"
    assert not rc.exists()
    run_post_install(_shell_init_tool("fzf"), _mutable(), None)
    assert "# >>> tools-installer tweak:fzf >>>" in rc.read_text()


def test_shell_init_bundle_absent_on_this_os_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = shell_init_bundle("zoxide")
    assert bundle is not None

    def macos_only(_tool_id: str) -> TweakBundle:
        return replace(bundle, platforms=("macos",))

    monkeypatch.setattr(post_install, "shell_init_bundle", macos_only)
    assert run_post_install(_shell_init_tool("zoxide"), _mutable(), None).lines == ()
    assert not (Path.home() / ".myshellrc").exists()


def test_shell_init_policies_era_block_is_the_same_block() -> None:
    home = Path.home()
    bundle = shell_init_bundle("zoxide")
    assert bundle is not None
    write_tweak(bundle, home / ".myshellrc")  # what the Policies row wrote before this phase
    before = (home / ".myshellrc").read_text()
    assert shell_init_record(home / ".myshellrc") is None
    run_post_install(_shell_init_tool("zoxide"), _mutable(), None)
    after = (home / ".myshellrc").read_text()
    assert after.count("# >>> tools-installer tweak:zoxide >>>") == 1
    assert after.startswith(before.rstrip("\n"))  # the block is untouched; the record is appended
    assert shell_init_record(home / ".myshellrc") == ("zoxide",)  # backfilled
    strip_tweak_block("zoxide", home / ".myshellrc")
    assert "tweak:zoxide" not in (home / ".myshellrc").read_text()


def test_shell_init_blocks_of_several_tools_keep_plan_order() -> None:
    home = Path.home()
    for tool in ("zoxide", "fzf", "direnv"):
        run_post_install(_shell_init_tool(tool), _mutable(), None)
    text = (home / ".myshellrc").read_text()
    order = [
        text.index(f"# >>> tools-installer tweak:{tool} >>>")
        for tool in ("zoxide", "fzf", "direnv")
    ]
    assert order == sorted(order)
    assert shell_init_record(home / ".myshellrc") == ("zoxide", "fzf", "direnv")
    strip_tweak_block("fzf", home / ".myshellrc")
    after = (home / ".myshellrc").read_text()
    assert "tweak:fzf" not in after
    assert "tweak:zoxide" in after
    assert "tweak:direnv" in after


def test_shell_init_two_blocks_never_interleave() -> None:
    home = Path.home()
    run_post_install(_shell_init_tool("zoxide"), _mutable(), None)
    run_post_install(_shell_init_tool("fnm"), _mutable(), None)
    lines = (home / ".myshellrc").read_text().split("\n")
    for tool in ("zoxide", "fnm"):
        begin = lines.index(f"# >>> tools-installer tweak:{tool} >>>")
        end = lines.index(f"# <<< tools-installer tweak:{tool} <<<")
        inner = lines[begin + 1 : end]
        assert not any("tools-installer" in line for line in inner)


@pytest.mark.parametrize("tool", SHELL_INIT_TOOLS)
def test_each_shell_init_tool_writes_one_block_and_asks_nothing(tool: str) -> None:
    home = Path.home()
    marker = f"# >>> tools-installer tweak:{tool} >>>"
    first = run_post_install(_shell_init_tool(tool), _mutable(), None).lines
    assert first == ("Shell init on: open a new terminal to use it.",)
    run_post_install(_shell_init_tool(tool), _mutable(), None)
    assert (home / ".myshellrc").read_text().count(marker) == 1
    assert shell_init_record(home / ".myshellrc") == (tool,)


def test_only_starship_touches_the_theme() -> None:
    zshrc = Path.home() / ".zshrc"
    zshrc.write_text(_OMZ_ZSHRC)
    before = zshrc.read_bytes()
    run_post_install(_shell_init_tool("zoxide"), _mutable(), _yes)
    assert zshrc.read_bytes() == before


def test_a_first_install_puts_the_path_block_above_shell_init() -> None:
    home = Path.home()
    run_post_install(_shell_init_tool("zoxide"), _mutable(), _yes)
    write_myshellrc([home / ".local" / "bin"], home / ".myshellrc")
    lines = (home / ".myshellrc").read_text().split("\n")
    assert lines.index("# >>> tools-installer path >>>") < lines.index(
        "# >>> tools-installer tweak:zoxide >>>"
    )


_OMZ_THEMELESS = 'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git)\nsource $ZSH/oh-my-zsh.sh\n'
_STARSHIP_BLOCK = (
    "# >>> tools-installer tweak:starship >>>\n"
    'eval "$(starship init zsh)"\n'
    "# <<< tools-installer tweak:starship <<<\n"
)
_OMZ_HANDOFF = (
    "Try a theme in this shell: omz theme use <name>",
    "Keep it: omz theme set <name>",
)


def _action_tool(tool_id: str, action: str) -> Tool:
    tools = {tool.id: tool for tool in load_tools(REGISTRY)}
    return replace(tools[tool_id], post_install=(action,))


def test_omz_install_adds_robbyrussell_and_names_the_theme_commands() -> None:
    home = Path.home()
    (home / ".oh-my-zsh").mkdir()
    zshrc = home / ".zshrc"
    zshrc.write_text(_OMZ_THEMELESS)
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None).lines
    assert lines == (
        "Theme: robbyrussell (added because ~/.zshrc had no ZSH_THEME).",
        *_OMZ_HANDOFF,
    )
    rc_lines = zshrc.read_text().split("\n")
    assert rc_lines[rc_lines.index('ZSH_THEME="robbyrussell"') + 1] == "source $ZSH/oh-my-zsh.sh"


def test_omz_install_keeps_a_user_theme() -> None:
    home = Path.home()
    (home / ".oh-my-zsh").mkdir()
    zshrc = home / ".zshrc"
    zshrc.write_text(_OMZ_THEMELESS.replace("plugins", 'ZSH_THEME="agnoster"\nplugins'))
    before = zshrc.read_bytes()
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None).lines
    assert lines[0] == "Theme: agnoster (yours; left as is)."
    assert zshrc.read_bytes() == before


def test_a_user_theme_name_is_sanitized_in_the_handoff() -> None:
    home = Path.home()
    (home / ".oh-my-zsh").mkdir()
    (home / ".zshrc").write_text(
        _OMZ_THEMELESS.replace("plugins", 'ZSH_THEME="ag\x1b[31mnoster"\nplugins')
    )
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None).lines
    assert "\x1b" not in lines[0]
    assert lines[0].startswith("Theme: ag")


def test_omz_install_with_starship_on_writes_an_empty_theme() -> None:
    home = Path.home()
    (home / ".oh-my-zsh").mkdir()
    (home / ".myshellrc").write_text(_STARSHIP_BLOCK)
    zshrc = home / ".zshrc"
    zshrc.write_text(_OMZ_THEMELESS)
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None).lines
    assert lines[0] == 'Theme: none (ZSH_THEME=""), so starship draws the prompt.'
    assert 'ZSH_THEME=""' in zshrc.read_text()


def test_omz_install_without_oh_my_zsh_hands_off_nothing() -> None:
    assert (
        run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None).lines == ()
    )


def test_vscode_install_returns_the_lean_tips() -> None:
    lines = run_post_install(_action_tool("vscode", "show_lean_tips"), _mutable(), None).lines
    assert lines == (
        "Lean tip: skip resident type-checkers (Pylance held 358 MB here).",
        "Run the project's pre-commit as an on-demand task, not on every save.",
    )
    assert all(len(line) <= 76 for line in lines)


def test_the_chsh_absent_text_names_the_sync_that_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_chsh(monkeypatch, present=False)
    lines = run_post_install(_login_shell_tool(), _immutable(), None).lines
    assert lines[2] == "This installer points Konsole, kitty and WezTerm at zsh when this run ends."
    stale = "A later installer step will apply that terminal-emulator configuration automatically."
    installer_dir = Path(__file__).resolve().parent.parent / "installer"
    assert not any(stale in path.read_text() for path in installer_dir.glob("*.py"))


def test_starship_in_policies_sets_and_restores_the_theme_like_the_install_yes() -> None:
    from installer.omz import owned_theme
    from installer.policy import tweak_policy

    home = Path.home()
    zshrc, myshellrc = home / ".zshrc", home / ".myshellrc"
    (home / ".oh-my-zsh").mkdir()
    zshrc.write_text(_OMZ_ZSHRC)
    run_post_install(
        _action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None
    )  # the installer's own robbyrussell
    bundle = shell_init_bundle("starship")
    assert bundle is not None
    policy = tweak_policy(bundle, rc_path=myshellrc)

    policy.apply()
    assert 'ZSH_THEME=""\nsource' in zshrc.read_text()

    policy.remove()  # the Policies off and the starship removal sweep share this closure
    assert 'ZSH_THEME="robbyrussell"\nsource' in zshrc.read_text()
    assert owned_theme(myshellrc) == "robbyrussell"


def test_reapplying_the_installers_own_theme_is_not_reported_as_yours() -> None:
    zshrc = Path.home() / ".zshrc"
    (Path.home() / ".oh-my-zsh").mkdir()
    zshrc.write_text(_OMZ_ZSHRC)
    run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None)
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None).lines
    assert "yours" not in lines[0]


# ---------------------------------------------------------------------------
# 23.2-01 Task 3: the tuning action, per agent and for VS Code.
# ---------------------------------------------------------------------------

_TUNED_AGENTS = ("claude", "codex", "opencode", "cursor-agent", "copilot", "vscode")
_TUNED_PLATFORMS = [(agent, "fedora") for agent in _TUNED_AGENTS] + [("vscode", "macos")]


def _on(platform_os: str) -> Platform:
    return Platform(os=platform_os, arch="arm64", immutable=False, has_brew=platform_os == "macos")


def _tuned(tool_id: str) -> Tool:
    return replace(_tool(post_install=("apply_agent_tuning",)), id=tool_id)


def _settings_path(tool_id: str, platform_os: str = "fedora") -> Path:
    return agent_settings.settings_file(
        tool_id, home=Path.home(), platform_os=platform_os, environ=os.environ
    )


def _tuning_keys(tool_id: str, platform_os: str) -> list[agent_settings.SettingKey]:
    return [
        key
        for group in agent_settings.TUNING_GROUPS[tool_id]
        for key in agent_settings.setting_keys(tool_id, group, platform_os)
    ]


def _document(tool_id: str, platform_os: str = "fedora") -> dict[str, object]:
    path = _settings_path(tool_id, platform_os)
    return parse_settings(path.read_text(encoding="utf-8"), agent_settings.AGENT_FORMATS[tool_id])


def _plant(tool_id: str, text: str, platform_os: str = "fedora") -> Path:
    path = _settings_path(tool_id, platform_os)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _kinds(output: PostInstallOutput) -> dict[str, str]:
    return {key.key: key.kind for result in output.settings for key in result.keys}


@pytest.mark.parametrize(("tool_id", "platform_os"), _TUNED_PLATFORMS)
def test_install_tuning_writes_exactly_each_agents_keys(tool_id: str, platform_os: str) -> None:
    output = run_post_install(_tuned(tool_id), _on(platform_os))

    keys = _tuning_keys(tool_id, platform_os)
    assert [result.refused for result in output.settings] == [None] * len(
        agent_settings.TUNING_GROUPS[tool_id]
    )
    doc = _document(tool_id, platform_os)
    assert set(doc) == {key.path[0] for key in keys}
    for key in keys:
        assert agent_settings.same_value(agent_settings.lookup(doc, key.path), key.value)
    ledger = read_ledger(tool_id)
    assert ledger is not None
    assert [entry.key_path for entry in ledger.entries] == [key.path for key in keys]
    assert (("update.mode",) in [key.path for key in keys]) is (platform_os == "macos")


def test_install_tuning_keeps_a_user_value_as_set_by_you() -> None:
    claude = _plant(
        "claude",
        '{\n  "model": "opus",\n  "permissions": {\n    "defaultMode": "acceptEdits"\n  }\n}\n',
    )
    vscode = _plant(
        "vscode",
        '// VS Code user settings\n{\n  "editor.fontSize": 14, // size\n'
        '  "editor.minimap.enabled": true,\n}\n',
    )

    claude_output = run_post_install(_tuned("claude"), _mutable())
    vscode_output = run_post_install(_tuned("vscode"), _mutable())

    assert _kinds(claude_output)["permissions.defaultMode"] == "set_by_you"
    assert _kinds(claude_output)["skipDangerousModePermissionPrompt"] == "wrote"
    text = claude.read_text(encoding="utf-8")
    assert '"model": "opus"' in text and '"defaultMode": "acceptEdits"' in text
    assert _document("claude")["permissions"] == {"defaultMode": "acceptEdits"}
    assert _kinds(vscode_output)["editor.minimap.enabled"] == "set_by_you"
    vscode_text = vscode.read_text(encoding="utf-8")
    assert vscode_text.startswith("// VS Code user settings\n{")
    assert '"editor.fontSize": 14, // size' in vscode_text
    assert _document("vscode")["editor.minimap.enabled"] is True
    ledger = read_ledger("vscode")
    assert ledger is not None
    assert ("editor.minimap.enabled",) not in [entry.key_path for entry in ledger.entries]


def test_install_tuning_reports_already_for_our_value() -> None:
    _plant("claude", '{"skipDangerousModePermissionPrompt": true}\n')

    output = run_post_install(_tuned("claude"), _mutable())

    assert _kinds(output)["skipDangerousModePermissionPrompt"] == "already"
    ledger = read_ledger("claude")
    assert ledger is not None
    assert ("skipDangerousModePermissionPrompt",) not in [e.key_path for e in ledger.entries]
    assert _document("claude")["skipDangerousModePermissionPrompt"] is True


@pytest.mark.parametrize("before", [None, "", "  \n", "{}"])
def test_install_tuning_on_missing_empty_and_bare_files(before: str | None) -> None:
    if before is not None:
        _plant("claude", before)

    output = run_post_install(_tuned("claude"), _mutable())

    assert [result.refused for result in output.settings] == [None, None]
    assert _document("claude") == {
        "permissions": {"defaultMode": "bypassPermissions"},
        "skipDangerousModePermissionPrompt": True,
        "attribution": {"commit": "", "pr": ""},
    }


def test_install_tuning_refuses_an_unparsable_file_and_writes_nothing() -> None:
    path = _plant("claude", "{not json\n")

    output = run_post_install(_tuned("claude"), _mutable())

    assert [(result.keys, bool(result.refused)) for result in output.settings] == [
        ((), True),
        ((), True),
    ]
    assert all((result.refused or "").startswith("not valid JSON") for result in output.settings)
    assert path.read_text(encoding="utf-8") == "{not json\n"
    assert read_ledger("claude") is None


def test_install_tuning_second_install_writes_nothing() -> None:
    run_post_install(_tuned("claude"), _mutable())
    path = _settings_path("claude")
    bytes_before = path.read_bytes()
    ledger_before = read_ledger("claude")

    again = run_post_install(_tuned("claude"), _mutable())

    assert path.read_bytes() == bytes_before
    assert read_ledger("claude") == ledger_before
    assert set(_kinds(again).values()) == {"already"}


def test_install_tuning_refusal_of_one_group_keeps_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_apply = post_install.apply_setting

    def failing_first(agent: str, setting: str, **kwargs: Any) -> agent_settings.FileResult:
        if setting == "auto-approve":
            raise OSError("disk exploded\nsecond line")
        return real_apply(agent, setting, **kwargs)

    monkeypatch.setattr(post_install, "apply_setting", failing_first)

    output = run_post_install(_tuned("claude"), _mutable())

    first, second = output.settings
    assert (first.setting, first.refused) == ("auto-approve", "disk exploded")
    assert first.path == _settings_path("claude")
    assert (second.setting, second.refused) == ("no-attribution", None)
    assert _document("claude") == {"attribution": {"commit": "", "pr": ""}}


def test_install_tuning_keeps_utf8_comments_byte_for_byte() -> None:
    head = "// ñandú — 日本語 ✓\n{\n"
    tail = '  "editor.fontFamily": "Fíra Código",\n  // «comentario»\n  "editor.rulers": [80]\n}\n'
    path = _plant("vscode", head + tail)

    run_post_install(_tuned("vscode"), _mutable())

    # New keys are spliced in after the opening brace; every byte around them is untouched.
    text = path.read_text(encoding="utf-8")
    assert text.startswith(head) and text.endswith(tail)
    assert _document("vscode")["editor.fontFamily"] == "Fíra Código"


@pytest.mark.parametrize("agent", ["claude", "vscode"])
def test_install_tuning_refuses_a_file_changed_before_commit(
    agent: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    other_writer = '{"model": "sonnet"}\n'
    path = _plant(agent, other_writer)

    def always_changed(_path: Path, _before: object, _text: str) -> None:
        raise agent_settings.SettingsChanged()

    monkeypatch.setattr(agent_settings, "write_if_unchanged", always_changed)

    output = run_post_install(_tuned(agent), _mutable())

    assert {result.refused for result in output.settings} == {agent_settings.CHANGED_WHILE_WRITING}
    assert path.read_text(encoding="utf-8") == other_writer
    assert read_ledger(agent) is None


def test_tuning_targets_only_user_scope_files() -> None:
    home = Path.home()
    user_dirs = (".claude", ".codex", ".config", ".cursor", ".copilot", "Library")
    for agent in _TUNED_AGENTS:
        for platform_os in ("fedora", "macos"):
            path = _settings_path(agent, platform_os)
            relative = path.relative_to(home)
            assert relative.parts[0] in user_dirs
            assert path.name not in {"settings.local.json", "copilot.json"}
            assert ".github" not in relative.parts
            assert Path.cwd() not in path.parents


def test_reinstall_rewrites_a_deleted_recorded_key() -> None:
    """The install-time action rewrites what RECONFIGURE leaves alone (SPEC R2)."""
    claude = _tuned("claude")
    run_post_install(claude, _mutable())
    path = _settings_path("claude")
    path.write_text("{}\n", encoding="utf-8")  # the user deleted every recorded key

    left_alone = apply_install_tuning(claude, _mutable(), skip_recorded=True)
    assert _kinds(left_alone) == {}
    assert path.read_text(encoding="utf-8") == "{}\n"

    reinstalled = run_post_install(claude, _mutable())

    assert set(_kinds(reinstalled).values()) == {"wrote"}
    assert len(_kinds(reinstalled)) == 4
    assert _document("claude")["skipDangerousModePermissionPrompt"] is True
    ledger = read_ledger("claude")
    assert ledger is not None and len(ledger.entries) == 4


_OMZ_USER_ZSHRC = 'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git z)\nsource $ZSH/oh-my-zsh.sh\n'


def _omz_home(zshrc_text: str | None) -> Path:
    home = Path.home()
    (home / ".oh-my-zsh").mkdir()
    if zshrc_text is not None:
        (home / ".zshrc").write_text(zshrc_text)
    return home


def test_set_omz_plugins_reports_what_it_added_and_what_was_already_on() -> None:
    home = _omz_home(_OMZ_USER_ZSHRC)
    tool = _action_tool("oh-my-zsh", "set_omz_plugins")
    assert run_post_install(tool, _mutable(), None).lines == ("Plugins: added docker to ~/.zshrc.",)
    assert "plugins=(git z docker)" in (home / ".zshrc").read_text()
    assert run_post_install(tool, _mutable(), None).lines == ("Plugins: git and docker are on.",)


def test_set_omz_plugins_without_an_oh_my_zsh_root_does_nothing() -> None:
    tool = _action_tool("oh-my-zsh", "set_omz_plugins")
    assert run_post_install(tool, _mutable(), None).lines == ()
    assert not (Path.home() / ".zshrc").exists()


def test_set_omz_plugins_honours_zsh_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "relocated-omz"
    root.mkdir()
    monkeypatch.setenv("ZSH", str(root))
    tool = _action_tool("oh-my-zsh", "set_omz_plugins")
    run_post_install(tool, _mutable(), None)
    zshrc = (Path.home() / ".zshrc").read_text()
    assert f"export ZSH={root}" in zshrc
    assert "plugins=(git docker)" in zshrc


def test_set_omz_plugins_refusal_is_a_line_not_an_exception() -> None:
    home = _omz_home("plugins=(\n  git\n)\nsource $ZSH/oh-my-zsh.sh\n")
    tool = _action_tool("oh-my-zsh", "set_omz_plugins")
    lines = run_post_install(tool, _mutable(), None).lines
    assert len(lines) == 1
    assert lines[0].startswith("Plugins not changed: ")
    assert (home / ".zshrc").read_text() == "plugins=(\n  git\n)\nsource $ZSH/oh-my-zsh.sh\n"


def test_one_crashing_action_keeps_the_chsh_handoff_and_the_other_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-04: a non-UTF-8 .zshrc breaks the theme action; the chsh lines (SPEC R8) and the
    plugins action's line still come out, and the crash is the warning."""
    _stub_chsh(monkeypatch, present=True)
    home = _omz_home(None)
    (home / ".zshrc").write_bytes(b"plugins=(git)\n# caf\xe9\nsource $ZSH/oh-my-zsh.sh\n")
    tool = replace(
        _action_tool("oh-my-zsh", "set_login_shell"),
        post_install=("set_login_shell", "set_omz_theme", "set_omz_plugins"),
    )

    output = run_post_install(tool, _mutable(), None)

    assert any("chsh -s" in line for line in output.lines)
    assert output.warning is not None and "set_omz_theme crashed: " in output.warning
    assert any(line.startswith("Plugins") for line in output.lines)


def test_shell_init_record_on_a_non_utf8_rc_is_a_refusal_not_a_decode_crash() -> None:
    rc_path = Path.home() / ".myshellrc"
    rc_path.write_bytes(b"# caf\xe9\n")

    with pytest.raises(OSError, match="not valid UTF-8"):
        record_shell_init(rc_path, "starship")
    assert rc_path.read_bytes() == b"# caf\xe9\n"


def test_omz_install_tuning_on_reconfigure_skips_a_recorded_record() -> None:
    _omz_home(_OMZ_USER_ZSHRC)
    tool = _action_tool("oh-my-zsh", "set_omz_plugins")
    assert apply_install_tuning(tool, _mutable(), skip_recorded=True).lines != ()
    zshrc = Path.home() / ".zshrc"
    zshrc.write_text(_OMZ_USER_ZSHRC)  # the user cut docker again after the record was written
    assert apply_install_tuning(tool, _mutable(), skip_recorded=True).lines == ()
    assert zshrc.read_text() == _OMZ_USER_ZSHRC
    assert apply_install_tuning(tool, _mutable(), skip_recorded=False).lines != ()
    assert "docker" in zshrc.read_text()


def test_apply_terminal_tuning_writes_the_keys_once_and_reconfigure_respects_a_deletion() -> None:
    tool = next(t for t in load_tools(REGISTRY) if t.id == "alacritty")
    config = Path.home() / ".config" / "alacritty" / "alacritty.toml"

    assert run_post_install(tool, _mutable()).warning is None
    assert len(tomllib.loads(config.read_text())["keyboard"]["bindings"]) == 3

    config.write_text(re.sub(r"# >>>.*?<<<[^\n]*\n", "", config.read_text(), flags=re.DOTALL))
    assert apply_install_tuning(tool, _mutable(), skip_recorded=True).lines == ()
    assert "keyboard" not in tomllib.loads(config.read_text())  # recorded, so the user's choice

    apply_install_tuning(tool, _mutable(), skip_recorded=False)  # a reinstall writes it again
    assert "keyboard" in tomllib.loads(config.read_text())


def test_apply_terminal_tuning_names_the_refusal(tmp_path: Path) -> None:
    config = Path.home() / ".config" / "alacritty" / "alacritty.toml"
    config.parent.mkdir(parents=True)
    config.write_text("keyboard.bindings = []\n")
    tool = next(t for t in load_tools(REGISTRY) if t.id == "alacritty")

    output = run_post_install(tool, _mutable())

    assert output.lines == (
        "Alacritty keys not changed: you already define keyboard.bindings inline",
    )
    assert config.read_text() == "keyboard.bindings = []\n"
