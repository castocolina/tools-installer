from pathlib import Path

import pytest

from installer.model import (
    POST_INSTALL_ACTIONS,
    POSTINSTALL_HOOK_NAMES,
    SENSITIVE_POST_INSTALL_ACTIONS,
    Method,
    Tool,
    load_tools,
)
from installer.platform import Platform
from installer.post_install import POST_INSTALL_HOOKS, ConfirmSensitiveAction, run_post_install
from installer.postinstall import POSTINSTALL_HOOKS

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
    assert len(actions) == 1, sorted(actions)
    assert actions <= sensitive, sorted(actions - sensitive)


def test_docstring_keeps_post_install_dispatch_on_the_install_ladder() -> None:
    import installer.post_install as module

    text = " ".join((module.__doc__ or "").split())
    assert "SKIP on the review" in text
    assert "REINSTALL" in text
    assert "successful reinstall dispatches actions once more" in text
    assert "No path re-applies post-install actions on their own (D-06)" in text
