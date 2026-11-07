from dataclasses import replace
from pathlib import Path

import pytest

from installer import post_install
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
    SensitivePrompt,
    run_post_install,
    sensitive_prompt,
    use_shell_init_sourcing,
)
from installer.postinstall import POSTINSTALL_HOOKS
from installer.shellrc import write_myshellrc
from installer.tweaks import SHELL_INIT_TOOLS, shell_init_bundle

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


def test_run_post_install_returns_chsh_instructions_when_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=True)
    asked: list[tuple[str, str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    lines = run_post_install(_tool(post_install=("set_login_shell",)), _mutable(), confirm)
    assert lines
    assert any("chsh -s" in line for line in lines)
    assert asked == [("oh-my-zsh", "set_login_shell")]


def test_run_post_install_skips_when_no_actions_declared() -> None:
    asked: list[tuple[str, str]] = []

    def confirm(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return True

    assert run_post_install(_tool(), _mutable(), confirm) == ()
    assert asked == []


def test_missing_chsh_explains_without_asking_or_offering_a_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=False)
    asked, confirm = _record()
    lines = run_post_install(_login_shell_tool(), _immutable(), confirm)
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
    lines = run_post_install(_login_shell_tool(), _mutable(), confirm)
    assert lines
    assert asked == []
    assert not any("chsh -s" in line for line in lines)


def test_missing_chsh_explains_without_a_confirm_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=False)
    lines = run_post_install(_login_shell_tool(), _immutable(), None)
    assert lines
    assert not any("chsh -s" in line for line in lines)


def test_immutable_host_with_chsh_still_uses_the_confirm_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=True)
    asked, confirm = _record()
    lines = run_post_install(_login_shell_tool(), _immutable(), confirm)
    assert any("chsh -s" in line for line in lines)
    assert asked == [("oh-my-zsh", "set_login_shell")]


def test_missing_chsh_cannot_be_silenced_via_default_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=False)
    asked, confirm = _record()
    lines = run_post_install(_login_shell_tool(default_enabled=True), _immutable(), confirm)
    assert lines
    assert asked == []


def test_login_shell_skips_when_confirm_callback_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=True)
    assert run_post_install(_login_shell_tool(), _mutable(), None) == ()


def test_login_shell_skips_when_confirm_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_chsh(monkeypatch, present=True)
    asked: list[tuple[str, str]] = []

    def refuse(tool_id: str, action: str) -> bool:
        asked.append((tool_id, action))
        return False

    assert run_post_install(_login_shell_tool(), _mutable(), refuse) == ()
    assert asked == [("oh-my-zsh", "set_login_shell")]


def test_unknown_post_install_action_name_is_inert() -> None:
    asked, confirm = _record()
    assert run_post_install(_tool(post_install=("not-a-real-action",)), _mutable(), confirm) == ()
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
    )
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


def test_shell_init_is_never_turned_on_without_a_yes() -> None:
    home = Path.home()
    zshrc = home / ".zshrc"
    zshrc.write_text(_OMZ_ZSHRC)
    before = zshrc.read_bytes()
    assert run_post_install(_shell_init_tool("starship"), _mutable(), None) == ()
    assert run_post_install(_shell_init_tool("starship"), _mutable(), lambda _t, _a: False) == ()
    assert not (home / ".myshellrc").exists()
    assert zshrc.read_bytes() == before


def test_the_shell_init_prompt_is_keyed_by_action() -> None:
    bundle = shell_init_bundle("zoxide")
    assert bundle is not None
    assert bundle.description == "adds z, a cd that learns the directories you use"
    assert sensitive_prompt("zoxide", "source_shell_init") == SensitivePrompt(
        "Turn on zoxide shell init? It adds one guarded block to ~/.myshellrc that adds z, "
        "a cd that learns the directories you use. It stays off unless you choose yes; "
        "Policies can change it later.",
        "Yes, turn it on",
        "No, leave it off",
        False,
    )
    assert sensitive_prompt("oh-my-zsh", "set_login_shell") == SensitivePrompt(
        "Show a reviewed command to change the login shell to zsh for oh-my-zsh, which you "
        "run in your own terminal after the installer exits?",
        "Yes, show the reviewed command",
        "No, skip this",
        True,
    )


def test_every_sensitive_action_has_a_prompt() -> None:
    for action in SENSITIVE_POST_INSTALL_ACTIONS:
        assert action in SENSITIVE_PROMPTS
    with pytest.raises(KeyError):
        sensitive_prompt("zoxide", "no_such_action")
    assert not hasattr(post_install, "SHELL_INIT_EFFECTS")


@pytest.mark.parametrize("tool", SHELL_INIT_TOOLS)
def test_each_shell_init_tool_follows_yes_and_no(tool: str) -> None:
    home = Path.home()
    marker = f"# >>> tools-installer tweak:{tool} >>>"
    no = run_post_install(_shell_init_tool(tool), _mutable(), lambda _t, _a: False)
    assert no == ()
    assert not (home / ".myshellrc").exists()
    yes = run_post_install(_shell_init_tool(tool), _mutable(), _yes)
    assert yes == ("Shell init on: open a new terminal to use it.",)
    run_post_install(_shell_init_tool(tool), _mutable(), _yes)
    assert (home / ".myshellrc").read_text().count(marker) == 1


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
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None)
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
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None)
    assert lines[0] == "Theme: agnoster (yours; left as is)."
    assert zshrc.read_bytes() == before


def test_a_user_theme_name_is_sanitized_in_the_handoff() -> None:
    home = Path.home()
    (home / ".oh-my-zsh").mkdir()
    (home / ".zshrc").write_text(
        _OMZ_THEMELESS.replace("plugins", 'ZSH_THEME="ag\x1b[31mnoster"\nplugins')
    )
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None)
    assert "\x1b" not in lines[0]
    assert lines[0].startswith("Theme: ag")


def test_omz_install_with_starship_on_writes_an_empty_theme() -> None:
    home = Path.home()
    (home / ".oh-my-zsh").mkdir()
    (home / ".myshellrc").write_text(_STARSHIP_BLOCK)
    zshrc = home / ".zshrc"
    zshrc.write_text(_OMZ_THEMELESS)
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None)
    assert lines[0] == 'Theme: none (ZSH_THEME=""), so starship draws the prompt.'
    assert 'ZSH_THEME=""' in zshrc.read_text()


def test_omz_install_without_oh_my_zsh_hands_off_nothing() -> None:
    assert run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None) == ()


def test_vscode_install_returns_the_lean_tips() -> None:
    lines = run_post_install(_action_tool("vscode", "show_lean_tips"), _mutable(), None)
    assert lines == (
        "Lean tip: skip resident type-checkers (Pylance held 358 MB here).",
        "Run the project's pre-commit as an on-demand task, not on every save.",
    )
    assert all(len(line) <= 76 for line in lines)


def test_the_chsh_absent_text_names_the_sync_that_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_chsh(monkeypatch, present=False)
    lines = run_post_install(_login_shell_tool(), _immutable(), None)
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
    lines = run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None)
    assert "yours" not in lines[0]
