from pathlib import Path

from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.post_install import run_post_install

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _mutable() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def _tool(*, post_install: tuple[str, ...] = ()) -> Tool:
    return Tool(
        id="oh-my-zsh",
        name="Oh My Zsh",
        category="shell",
        cmd="omz",
        methods=(Method(kind="script", params={"url": "u"}),),
        post_install=post_install,
    )


def test_real_oh_my_zsh_entry_declares_set_login_shell() -> None:
    tools = {tool.id: tool for tool in load_tools(REGISTRY)}
    assert "set_login_shell" in tools["oh-my-zsh"].post_install


def test_run_post_install_returns_chsh_instructions_when_confirmed() -> None:
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
