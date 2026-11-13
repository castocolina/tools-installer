import errno
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable
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
from installer.run import CommandError
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


def test_neovim_writes_the_editor_block_when_you_set_none() -> None:
    home = Path.home()
    lines = run_post_install(_shell_init_tool("neovim"), _mutable(), None).lines
    assert lines == ("Shell init on: open a new terminal to use it.",)
    text = (home / ".myshellrc").read_text()
    assert text.count("# >>> tools-installer tweak:neovim >>>") == 1
    assert "export EDITOR=nvim VISUAL=nvim" in text
    assert shell_init_record(home / ".myshellrc") == ("neovim",)


def test_neovim_keeps_your_editor() -> None:
    home = Path.home()
    (home / ".zshrc").write_text("export EDITOR=vim\n")
    lines = run_post_install(_shell_init_tool("neovim"), _mutable(), None).lines
    assert lines == ("Kept your EDITOR (~/.zshrc:1; the neovim shell init was not written).",)
    assert not (home / ".myshellrc").exists()
    assert shell_init_record(home / ".myshellrc") is None


def _neovim_lines() -> tuple[str, ...]:
    return run_post_install(_shell_init_tool("neovim"), _mutable(), None).lines


def _no_neovim_block() -> bool:
    rc = Path.home() / ".myshellrc"
    return (not rc.exists() or "tweak:neovim" not in rc.read_text()) and shell_init_record(
        rc
    ) is None


_KEPT = re.compile(r"Kept your EDITOR \(~/[^:]+:\d+; the neovim shell init was not written\)\.")


def _assert_kept_vim(lines: tuple[str, ...]) -> None:
    assert len(lines) == 1
    assert _KEPT.fullmatch(lines[0]), lines


def _zdotdir_in(monkeypatch: pytest.MonkeyPatch) -> Path:
    zdir = Path.home() / "zdot"
    zdir.mkdir()
    monkeypatch.setenv("ZDOTDIR", str(zdir))
    return zdir


@pytest.mark.parametrize(
    "where", ["bashrc.d", "zdot.zshrc", "zdot.zshenv", "home.zshenv", "profile", "shellrc"]
)
def test_user_export_reads_every_startup_file(where: str, monkeypatch: pytest.MonkeyPatch) -> None:
    home = Path.home()
    zdir = _zdotdir_in(monkeypatch)
    target = {
        "bashrc.d": home / ".bashrc.d" / "editor.sh",
        "zdot.zshrc": zdir / ".zshrc",
        "zdot.zshenv": zdir / ".zshenv",
        "home.zshenv": home / ".zshenv",
        "profile": home / ".profile",
        "shellrc": home / ".shellrc",
    }[where]
    target.parent.mkdir(exist_ok=True)
    target.write_text("export EDITOR=vim\n")
    _assert_kept_vim(_neovim_lines())
    assert _no_neovim_block()


def test_user_export_survives_non_utf8_bytes() -> None:
    (Path.home() / ".zshrc").write_bytes(b"# \xff\nexport EDITOR=vim\n")
    _assert_kept_vim(_neovim_lines())


def test_user_export_skips_missing_and_non_regular_files() -> None:
    home = Path.home()
    (home / ".zshrc").mkdir()
    os.mkfifo(home / ".bashrc")
    assert _neovim_lines() == ("Shell init on: open a new terminal to use it.",)
    assert "tweak:neovim" in (home / ".myshellrc").read_text()


def test_user_export_fails_closed_on_an_oversized_file() -> None:
    (Path.home() / ".zshrc").write_bytes(b"#" * ((1 << 20) + 1))
    assert _neovim_lines() == (
        "Could not read ~/.zshrc (larger than 1 MiB), so the neovim shell init was not written.",
    )
    assert _no_neovim_block()


def test_user_export_sanitizes_an_unreadable_file_name() -> None:
    snippets = Path.home() / ".bashrc.d"
    snippets.mkdir()
    (snippets / "ed\x1bitor.sh").write_bytes(b"#" * ((1 << 20) + 1))
    lines = _neovim_lines()
    assert lines == (
        "Could not read ~/.bashrc.d/editor.sh (larger than 1 MiB), "
        "so the neovim shell init was not written.",
    )
    assert "\x1b" not in lines[0]
    assert _no_neovim_block()


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file")
def test_user_export_fails_closed_on_an_unreadable_file() -> None:
    bashrc = Path.home() / ".bashrc"
    bashrc.write_text("export EDITOR=vim\n")
    bashrc.chmod(0)
    try:
        assert _neovim_lines() == (
            "Could not read ~/.bashrc (Permission denied), "
            "so the neovim shell init was not written.",
        )
    finally:
        bashrc.chmod(0o600)
    assert _no_neovim_block()


def test_neovim_keeps_an_editor_set_in_a_multi_assignment_export() -> None:
    (Path.home() / ".bashrc").write_text("export LANG=C.UTF-8 EDITOR=vim\n")
    _assert_kept_vim(_neovim_lines())
    assert _no_neovim_block()


def test_neovim_keeps_your_visual() -> None:
    (Path.home() / ".zshrc").write_text("export VISUAL=code\n")
    assert _neovim_lines() == (
        "Kept your VISUAL (~/.zshrc:1; the neovim shell init was not written).",
    )
    assert _no_neovim_block()


def test_neovim_kept_line_names_the_file_not_the_value() -> None:
    (Path.home() / ".zshrc").write_text("export EDITOR=$(command -v v\x1bim)\n")
    lines = _neovim_lines()
    assert lines == ("Kept your EDITOR (~/.zshrc:1; the neovim shell init was not written).",)
    assert "\x1b" not in lines[0]


@pytest.mark.parametrize(
    "text",
    [
        "case $TERM in\n  xterm)\n    export EDITOR=vim\n    ;;\nesac\n",
        "case $TERM in xterm) EDITOR=vim;; esac\n",
        "time export EDITOR=vim\n",
        "true && export EDITOR=vim\n",
        "export EDITOR=vim\nexport EDITOR=\n",
    ],
)
def test_neovim_keeps_an_editor_set_anywhere_in_a_statement(text: str) -> None:
    (Path.home() / ".zshrc").write_text(text)
    lines = _neovim_lines()
    assert len(lines) == 1
    assert lines[0].startswith("Kept your EDITOR (~/.zshrc:")
    assert _no_neovim_block()


def test_neovim_ignores_an_environment_editor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDITOR", "vim")
    assert _neovim_lines() == ("Shell init on: open a new terminal to use it.",)
    assert "tweak:neovim" in (Path.home() / ".myshellrc").read_text()


def _fake_nvim_dir(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    nvim = bin_dir / "nvim"
    nvim.write_text("#!/bin/sh\n")
    nvim.chmod(0o755)
    return bin_dir


def _probe_output(shell: list[str], tmp_path: Path, script: str, path_dirs: str) -> str:
    """Run `script` as a file (the 23.1 sandbox cannot resolve `$HOME` in a word sourced through
    `-c`) in a fresh shell holding only HOME and PATH, and return what it printed."""
    probe = tmp_path / "probe.sh"
    probe.write_text(script)
    done = subprocess.run(
        [*shell, str(probe)],
        env={"HOME": str(Path.home()), "PATH": path_dirs},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


def _sourcing_probe(*files: Path) -> str:
    return "".join(f'. "{file}"\n' for file in files) + 'printf "%s" "$EDITOR $VISUAL"\n'


def _shells() -> list[object]:
    bash, zsh = shutil.which("bash"), shutil.which("zsh")
    return [
        pytest.param([bash, "--noprofile", "--norc"], id="bash"),
        pytest.param(
            [zsh, "-f"],
            id="zsh",
            marks=pytest.mark.skipif(zsh is None, reason="zsh is not on PATH; zsh run skipped"),
        ),
    ]


@pytest.mark.parametrize("shell", _shells())
def test_a_new_shell_prints_nvim(shell: list[str], tmp_path: Path) -> None:
    run_post_install(_shell_init_tool("neovim"), _mutable(), None)
    probe = _sourcing_probe(Path.home() / ".myshellrc")
    with_nvim = f"{_fake_nvim_dir(tmp_path)}:/usr/bin:/bin"
    assert _probe_output(shell, tmp_path, probe, with_nvim) == "nvim nvim"
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _probe_output(shell, tmp_path, probe, str(empty)) == " "  # the guard holds


@pytest.mark.parametrize("shell", _shells())
def test_an_os_default_editor_is_overridden(shell: list[str], tmp_path: Path) -> None:
    run_post_install(_shell_init_tool("neovim"), _mutable(), None)
    script = "export EDITOR=/usr/bin/nano\n" + _sourcing_probe(Path.home() / ".myshellrc")
    path_dirs = f"{_fake_nvim_dir(tmp_path)}:/usr/bin:/bin"
    assert _probe_output(shell, tmp_path, script, path_dirs).startswith("nvim")


def test_your_editor_wins_in_a_new_shell(tmp_path: Path) -> None:
    home = Path.home()
    (home / ".bashrc").write_text("export EDITOR=vim\n")
    run_post_install(_shell_init_tool("neovim"), _mutable(), None)
    assert not (home / ".myshellrc").exists()
    shell = [shutil.which("bash") or "bash", "--noprofile", "--norc"]
    out = _probe_output(shell, tmp_path, _sourcing_probe(home / ".bashrc"), "/usr/bin:/bin")
    assert out == "vim "


def test_neovim_reinstall_rewrites_the_block_in_place() -> None:
    home = Path.home()
    for _ in range(2):
        assert _neovim_lines() == ("Shell init on: open a new terminal to use it.",)
    text = (home / ".myshellrc").read_text()
    assert text.count("# >>> tools-installer tweak:neovim >>>") == 1
    assert shell_init_record(home / ".myshellrc") == ("neovim",)


def test_interrupted_editor_block_write_keeps_the_old_rc(monkeypatch: pytest.MonkeyPatch) -> None:
    rc = Path.home() / ".myshellrc"
    rc.write_text("export KEEP=1\n")
    before = rc.read_bytes()

    def interrupted(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("installer.tweaks.atomic_write_text", interrupted)
    output = run_post_install(_shell_init_tool("neovim"), _mutable(), None)
    assert output.warning == "source_shell_init crashed: disk full"
    assert rc.read_bytes() == before
    assert shell_init_record(rc) is None


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


_PATCHED_LINE = (
    "  servers = {} -- tools-installer: no language servers; enable one with :lsp enable <name>"
)
_STARTER_URL = "https://github.com/nvim-lua/kickstart.nvim.git"
_STARTER_LINES = (
    "Starter: kickstart.nvim 8e35dbe (no language servers) is in ~/.config/nvim.",
    "Open nvim once so the starter downloads its plugins (it asks Proceed? once).",
)
_HINT_LINES = (
    "Neovim runs no language server: check the open file with :!pre-commit run --files %",
    "For one session with a server, run :lsp enable <name> inside nvim.",
)
_SHELL_INIT_LINE = "Shell init on: open a new terminal to use it."


def _kickstart_pin() -> str:
    return str(vars(post_install)["_KICKSTART_PIN"])


def _kickstart_patch() -> Path:
    return Path(str(vars(post_install)["_KICKSTART_PATCH"]))


def _shipped_neovim() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "neovim")


class FakeGit:
    """The injected git runner: records argv, simulates each step on disk, fails or hooks a step."""

    def __init__(
        self,
        *,
        fail_at: str | None = None,
        head: str | None = None,
        hooks: dict[str, Callable[[], None]] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._fail_at = fail_at
        self._head = head
        self._hooks = hooks or {}
        self._error = error

    @staticmethod
    def step(argv: list[str]) -> str:
        if argv[1] == "clone":
            return "clone"
        verb = argv[3]
        return "apply-check" if verb == "apply" and "--check" in argv else verb

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(list(argv))
        step = self.step(argv)
        tmp = Path(argv[-1] if step == "clone" else argv[2])
        if step in self._hooks:
            self._hooks[step]()
        if step == self._fail_at:
            raise self._error or CommandError(argv, 128, detail="fatal: boom")
        if step == "clone":
            (tmp / ".git").mkdir()
        elif step == "checkout":
            (tmp / "init.lua").write_text("-- kickstart\n", encoding="utf-8")
        elif step == "rev-parse":
            return f"{self._head or _kickstart_pin()}\n"
        elif step == "apply":
            with (tmp / "init.lua").open("a", encoding="utf-8") as handle:
                handle.write(_PATCHED_LINE + "\n")
        return ""


def use_fake_git(
    monkeypatch: pytest.MonkeyPatch, *, present: bool = True, **kwargs: Any
) -> FakeGit:
    """Install a fake git runner for this test (restored after it) and answer `which git`."""
    fake = FakeGit(**kwargs)
    monkeypatch.setattr(post_install, "_git", fake)
    real_which = shutil.which

    def which(cmd: str) -> str | None:
        if cmd == "git":
            return "/usr/bin/git" if present else None
        return real_which(cmd)

    monkeypatch.setattr(shutil, "which", which)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return fake


def test_starter_clones_the_pin_patches_and_moves_into_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = use_fake_git(monkeypatch)
    config = Path.home() / ".config"

    output = run_post_install(_shipped_neovim(), _mutable())

    assert output.warning is None
    assert output.lines == (_SHELL_INIT_LINE, *_STARTER_LINES, *_HINT_LINES)
    tmp = fake.calls[0][-1]
    assert Path(tmp).parent == config
    patch = str(_kickstart_patch())
    assert fake.calls == [
        ["git", "clone", "--quiet", "--no-checkout", "--", _STARTER_URL, tmp],
        ["git", "-C", tmp, "checkout", "--quiet", "-B", "master", _kickstart_pin()],
        ["git", "-C", tmp, "rev-parse", "HEAD"],
        ["git", "-C", tmp, "apply", "--check", patch],
        ["git", "-C", tmp, "apply", patch],
    ]
    assert (config / "nvim" / "init.lua").read_text().splitlines()[-1] == _PATCHED_LINE
    assert not list(config.glob(".nvim-starter.*"))


def test_neovim_hints_name_pre_commit_and_lsp_enable() -> None:
    lines = run_post_install(_tool(post_install=("show_nvim_hints",)), _mutable()).lines
    text = "\n".join(lines)
    assert ":!pre-commit run --files %" in text
    assert ":lsp enable <name>" in text


def test_the_default_git_runner_refuses() -> None:
    default = vars(post_install)["_git"]
    with pytest.raises(CommandError) as raised:
        default(["git", "clone", "x"])
    assert raised.value.returncode == 127

    def fake(argv: list[str]) -> str:
        return ""

    post_install.use_git_runner(fake)
    assert vars(post_install)["_git"] is fake  # the autouse no_git_runner fixture resets it


_BY_HAND_HEAD = "To add it by hand:"
_CHANGED_LINE = (
    "Starter not added: ~/.config/nvim changed while the starter was prepared (left as is)."
)
_YOURS_LINE = "Starter not added: ~/.config/nvim is yours (left as is)."


def _by_hand_lines() -> tuple[str, ...]:
    return (
        _BY_HAND_HEAD,
        f"git clone {_STARTER_URL} ~/.config/nvim",
        f"git -C ~/.config/nvim checkout -B master {_kickstart_pin()}",
        f"git -C ~/.config/nvim apply {_kickstart_patch()}",
    )


def _starter() -> tuple[str, ...]:
    """Only the starter action's lines, through the dispatcher (never `_clone_nvim_starter`)."""
    return run_post_install(_tool(post_install=("clone_nvim_starter",)), _mutable()).lines


def _no_temp_dir() -> bool:
    return not list((Path.home() / ".config").glob(".nvim-starter.*"))


def _snapshot(path: Path) -> object:
    """Everything the user could notice about `path`: bytes, entry names and a link's target."""
    raw = os.fsencode(path)
    if path.is_symlink():
        return ("link", os.readlink(raw))
    if path.is_dir():
        return ("dir", {name: _snapshot(path / os.fsdecode(name)) for name in os.listdir(raw)})
    return ("file", path.read_bytes())


def _dotfile_only(target: Path) -> None:
    target.mkdir(parents=True)
    (target / ".keep").write_bytes(b"")


def _non_utf8_entry(target: Path) -> None:
    target.mkdir(parents=True)
    with open(os.path.join(os.fsencode(target), b"\xff"), "wb") as handle:
        handle.write(b"mine")


def _regular_file(target: Path) -> None:
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not a dir")


def _link_to_empty_dir(target: Path) -> None:
    target.parent.mkdir(parents=True)
    elsewhere = target.parent / "elsewhere"
    elsewhere.mkdir()
    target.symlink_to(elsewhere)


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(_dotfile_only, id="dotfile"),
        pytest.param(
            _non_utf8_entry,
            id="non-utf8-name",
            marks=pytest.mark.skipif(
                sys.platform == "darwin", reason="APFS rejects a file name that is not UTF-8"
            ),
        ),
        pytest.param(_regular_file, id="regular-file"),
        pytest.param(_link_to_empty_dir, id="symlink"),
    ],
)
def test_starter_leaves_a_non_empty_config_byte_identical(
    build: Callable[[Path], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = use_fake_git(monkeypatch)
    target = Path.home() / ".config" / "nvim"
    build(target)
    before = _snapshot(target)

    assert _starter() == (_YOURS_LINE,)

    assert fake.calls == []
    assert _snapshot(target) == before
    assert _no_temp_dir()


def test_starter_skips_when_xdg_config_home_points_elsewhere(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = use_fake_git(monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    lines = _starter()

    assert lines == (
        "Starter not added: XDG_CONFIG_HOME points elsewhere than ~/.config (left as is).",
    )
    assert fake.calls == []

    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/config")  # ignored: not absolute
    assert _starter()[0].startswith("Starter: kickstart.nvim")
    assert len(fake.calls) == 5


def test_starter_without_git_says_how(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_git(monkeypatch, present=False)

    assert _starter() == ("Starter not added: git is not installed.", *_by_hand_lines())

    assert fake.calls == []
    assert not (Path.home() / ".config" / "nvim").exists()


@pytest.mark.parametrize("step", ["clone", "checkout", "rev-parse", "apply-check", "apply"])
def test_a_failing_git_step_leaves_nothing(step: str, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_git(monkeypatch, fail_at=step)

    lines = _starter()

    assert lines == ("Starter not added: fatal: boom.", *_by_hand_lines())
    assert [FakeGit.step(argv) for argv in fake.calls][-1] == step
    assert not (Path.home() / ".config" / "nvim").exists()
    assert _no_temp_dir()


def test_a_moved_branch_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_git(monkeypatch, head="0" * 40)

    lines = _starter()

    pinned = _kickstart_pin()[:12]
    assert lines == (
        f"Starter not added: the checkout is at {'0' * 12}, not the pinned {pinned}.",
        *_by_hand_lines(),
    )
    assert [FakeGit.step(argv) for argv in fake.calls] == ["clone", "checkout", "rev-parse"]
    assert not (Path.home() / ".config" / "nvim").exists()
    assert _no_temp_dir()


def test_starter_refuses_a_config_created_while_it_prepared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = Path.home() / ".config" / "nvim"

    def user_creates_a_config() -> None:
        target.mkdir()
        (target / "mine.lua").write_bytes(b"mine")

    use_fake_git(monkeypatch, hooks={"apply": user_creates_a_config})

    assert _starter() == (_CHANGED_LINE,)

    assert [entry.name for entry in target.iterdir()] == ["mine.lua"]
    assert (target / "mine.lua").read_bytes() == b"mine"
    assert _no_temp_dir()


def test_a_refused_rename_leaves_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_git(monkeypatch)

    def refuse(src: object, dst: object) -> None:
        raise OSError(errno.ENOTEMPTY, "Directory not empty")

    monkeypatch.setattr(os, "rename", refuse)

    assert _starter() == (_CHANGED_LINE,)

    assert not (Path.home() / ".config" / "nvim").exists()
    assert _no_temp_dir()


def test_an_interrupted_starter_removes_its_temp_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_git(monkeypatch, fail_at="checkout", error=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        _starter()

    assert not (Path.home() / ".config" / "nvim").exists()
    assert _no_temp_dir()


def test_starter_replaces_an_empty_config_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_git(monkeypatch)
    target = Path.home() / ".config" / "nvim"
    target.mkdir(parents=True)

    assert _starter() == _STARTER_LINES

    assert (target / "init.lua").read_text().splitlines()[-1] == _PATCHED_LINE
    assert _no_temp_dir()


def test_reconfigure_never_runs_the_starter(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_git(monkeypatch)

    apply_install_tuning(_shipped_neovim(), _mutable(), skip_recorded=True)

    assert fake.calls == []
    assert not (Path.home() / ".config" / "nvim").exists()


def test_kickstart_patch_is_one_reviewed_hunk() -> None:
    patch = _kickstart_patch()
    assert patch.is_relative_to(Path(post_install.__file__).parent)
    raw = patch.read_bytes()
    assert raw.endswith(b"\n")
    lines = raw.decode("utf-8").splitlines()
    assert lines[0] == "diff --git a/init.lua b/init.lua"
    headers = [line for line in lines if line.startswith("@@")]
    assert headers == ["@@ -778,6 +778,7 @@ do"]
    body = lines[lines.index(headers[0]) + 1 :]
    added = [line for line in body if line.startswith("+")]
    assert added == ["+" + _PATCHED_LINE]
    assert [line for line in body if line.startswith("-")] == []
    assert len(body) - len(added) == 6  # old side: the context lines
    assert len(body) == 7  # new side
    assert " " in body and body.count(" ") == 1  # the one-space context line


def test_e2e_script_names_the_same_pin_and_patch() -> None:
    script = (REGISTRY.parent.parent / "scripts" / "container-e2e-verify.sh").read_text()
    match = re.search(r"^NVIM_STARTER_PIN=(\S+)$", script, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == _kickstart_pin()
    relative = _kickstart_patch().relative_to(REGISTRY.parent.parent).as_posix()
    assert relative == "installer/patches/kickstart-no-lsp.patch"
    assert f"NVIM_STARTER_PATCH={relative}" in script


def test_neovim_hints_survive_a_crashed_starter(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object) -> tuple[str, ...]:
        raise RuntimeError("boom")

    monkeypatch.setitem(POST_INSTALL_HOOKS, "clone_nvim_starter", boom)

    output = run_post_install(_shipped_neovim(), _mutable())

    assert output.warning == "clone_nvim_starter crashed: boom"
    assert output.lines == (_SHELL_INIT_LINE, *_HINT_LINES)


def test_neovim_hints_print_with_your_own_config(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_git(monkeypatch)
    mine = Path.home() / ".config" / "nvim"
    mine.mkdir(parents=True)
    (mine / "init.lua").write_bytes(b"mine")

    output = run_post_install(_shipped_neovim(), _mutable())

    assert output.lines == (_SHELL_INIT_LINE, _YOURS_LINE, *_HINT_LINES)
    assert fake.calls == []
