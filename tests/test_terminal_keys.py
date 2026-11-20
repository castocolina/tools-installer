"""Terminal keys mechanism tests: golden bytes first, then the table."""

import os
from pathlib import Path

from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.post_install import run_post_install
from installer.terminal_shell import sync_terminal_shells

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
_LINUX = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
_SUMMARY = "Alacritty keys: Alt+Left and Alt+Right move by word, Control+Shift+K clears history."
_KEYS_REGION = (
    "# >>> tools-installer terminal-shell alacritty-keys >>>\n"
    '[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "\\u001bb"\n\n'
    '[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "\\u001bf"\n\n'
    '[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\naction = "ClearHistory"\n'
    "# <<< tools-installer terminal-shell alacritty-keys <<<\n"
)
_KEYS_REGION_NO_LEFT = (
    "# >>> tools-installer terminal-shell alacritty-keys >>>\n"
    '[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "\\u001bf"\n\n'
    '[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\naction = "ClearHistory"\n'
    "# <<< tools-installer terminal-shell alacritty-keys <<<\n"
)
_SHELL_REGION = (
    "# >>> tools-installer terminal-shell alacritty >>>\n"
    '[terminal.shell]\nprogram = "/usr/bin/zsh"\nargs = ["-l"]\n\n'
    '[env]\nSHELL = "/usr/bin/zsh"\n'
    "# <<< tools-installer terminal-shell alacritty <<<\n"
)
_USER_FONT = "[font]\nsize = 12\n"
_USER_ALT_LEFT = '[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "x"\n'


def _alacritty() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "alacritty")


def _config() -> Path:
    return Path.home() / ".config" / "alacritty" / "alacritty.toml"


def _state_dir() -> Path:
    return Path.home() / ".local" / "share" / "tools-installer"


def _sync() -> None:
    sync_terminal_shells(
        home=Path.home(),
        environ=dict(os.environ),
        platform=_LINUX,
        lookup=lambda name: {
            "zsh": "/usr/bin/zsh",
            "alacritty": "/usr/bin/alacritty",
        }.get(name),
        write=True,
    )


def _remove(tmp_path: Path) -> None:
    from installer import app as app_module

    app_module._after_removal(  # pyright: ignore[reportPrivateUsage]
        _alacritty(),
        bundles=(),
        bin_dir=tmp_path / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        extra_policies=(),
        platform_os="fedora",
    )


def test_golden_created_file_holds_only_the_keys_region() -> None:
    result = run_post_install(_alacritty(), _LINUX)

    assert result.warning is None
    assert result.lines == (_SUMMARY,)
    assert _config().read_bytes() == _KEYS_REGION.encode()
    assert (_state_dir() / "terminal-tuning-alacritty").read_text() == "written\n"
    marker = (_state_dir() / "terminal-alacritty-created").read_text()
    assert marker.replace(str(Path.home()), "~") == "created\n~/.config\n~/.config/alacritty\n"
    assert {path.name for path in _state_dir().iterdir()} == {
        "terminal-alacritty-created",
        "terminal-tuning-alacritty",
    }


def test_golden_user_content_is_kept_above_the_region() -> None:
    config = _config()
    config.parent.mkdir(parents=True)
    config.write_text(_USER_FONT)

    run_post_install(_alacritty(), _LINUX)

    assert config.read_bytes() == (_USER_FONT + _KEYS_REGION).encode()
    assert {path.name for path in _state_dir().iterdir()} == {"terminal-tuning-alacritty"}


def test_golden_adjacent_user_binding_is_kept_and_reported() -> None:
    config = _config()
    config.parent.mkdir(parents=True)
    config.write_text(_USER_ALT_LEFT)

    result = run_post_install(_alacritty(), _LINUX)

    assert config.read_bytes() == (_USER_ALT_LEFT + _KEYS_REGION_NO_LEFT).encode()
    assert result.lines == (_SUMMARY, "alacritty: partial: you already bind Alt+Left")


def test_golden_install_twice_writes_the_same_bytes() -> None:
    run_post_install(_alacritty(), _LINUX)
    run_post_install(_alacritty(), _LINUX)

    assert _config().read_bytes() == _KEYS_REGION.encode()


def test_golden_shell_and_keys_regions_together_then_strip(tmp_path: Path) -> None:
    config = _config()
    config.parent.mkdir(parents=True)
    config.write_text(_USER_FONT)
    run_post_install(_alacritty(), _LINUX)

    _sync()
    settled = (_USER_FONT + _KEYS_REGION + _SHELL_REGION).encode()
    assert config.read_bytes() == settled
    _sync()
    assert config.read_bytes() == settled

    _remove(tmp_path)

    assert config.read_bytes() == _USER_FONT.encode()
    assert not (_state_dir() / "terminal-tuning-alacritty").exists()


def test_golden_created_file_goes_with_the_tool(tmp_path: Path) -> None:
    run_post_install(_alacritty(), _LINUX)
    _sync()

    _remove(tmp_path)

    assert not _config().exists()
    assert not _config().parent.exists()
    assert not (_state_dir() / "terminal-alacritty-created").exists()
