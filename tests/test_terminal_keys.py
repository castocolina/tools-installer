"""Terminal keys mechanism tests: golden bytes first, then the table."""

import dataclasses
import os
from collections.abc import Iterable, Mapping
from pathlib import Path

from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.post_install import apply_install_tuning, run_post_install
from installer.terminal_keys import TERMINAL_KEYS, OwnedRegion, apply_terminal_keys
from installer.terminal_regions import replace_owned_region
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
_FIXTURE_REGISTRY = """[[tool]]
id = "alacritty"
category = "terminal"
tier = "user"
verified = 2026-11-20
post_install = ["apply_terminal_tuning"]
[[tool.method]]
kind = "brew"
formula = "alacritty"

[[tool]]
id = "fixture-term"
category = "terminal"
tier = "user"
verified = 2026-11-20
post_install = ["apply_terminal_tuning"]
[[tool.method]]
kind = "brew"
formula = "fixture-term"
"""


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


def apply_alacritty_keys(
    home: Path, environ: Mapping[str, str], *, skip_recorded: bool
) -> tuple[tuple[str, ...], str | None]:
    """Bind the Alacritty row for tests/test_terminal_shell.py (28 D-12)."""
    return apply_terminal_keys(
        TERMINAL_KEYS["alacritty"],
        "alacritty",
        "fedora",
        home,
        environ,
        skip_recorded=skip_recorded,
    )


def test_alacritty_row_is_keyed_by_its_registry_id() -> None:
    row = TERMINAL_KEYS["alacritty"]
    assert set(TERMINAL_KEYS) == {"alacritty"}
    assert row.ownership == OwnedRegion("alacritty-keys")
    assert row.created_record == "terminal-alacritty-created"
    assert row.sibling_regions == ("alacritty",)
    assert row.summary == _SUMMARY
    assert row.config_path("fedora", Path.home(), {}) == (
        Path.home() / ".config" / "alacritty" / "alacritty.toml"
    )
    assert replace_owned_region("", "alacritty-keys", row.plan("fedora", "").body) == (_KEYS_REGION)


def missing_rows(tools: Iterable[Tool], table: Mapping[str, object]) -> set[str]:
    """Ids declaring terminal tuning but absent from the keys table."""
    return {tool.id for tool in tools if "apply_terminal_tuning" in tool.post_install} - set(table)


def extra_rows(tools: Iterable[Tool], table: Mapping[str, object]) -> set[str]:
    """Keys table ids with no registry terminal-tuning declaration."""
    return set(table) - {tool.id for tool in tools if "apply_terminal_tuning" in tool.post_install}


def test_completeness_every_declarer_has_a_row_and_every_row_a_declarer() -> None:
    tools = load_tools(REGISTRY)
    assert missing_rows(tools, TERMINAL_KEYS) == set()
    assert extra_rows(tools, TERMINAL_KEYS) == set()
    assert "konsole" not in TERMINAL_KEYS


def test_completeness_fails_for_a_declarer_without_a_row(tmp_path: Path) -> None:
    path = tmp_path / "registry.toml"
    path.write_text(_FIXTURE_REGISTRY)
    assert missing_rows(load_tools(path), TERMINAL_KEYS) == {"fixture-term"}


def test_completeness_fails_on_an_empty_table() -> None:
    assert missing_rows(load_tools(REGISTRY), {}) == {"alacritty"}


def test_completeness_ignores_table_order(tmp_path: Path) -> None:
    path = tmp_path / "registry.toml"
    path.write_text(_FIXTURE_REGISTRY)
    tools = load_tools(path)
    forward = {
        "alacritty": TERMINAL_KEYS["alacritty"],
        "fixture-term": TERMINAL_KEYS["alacritty"],
    }
    reverse = {
        "fixture-term": TERMINAL_KEYS["alacritty"],
        "alacritty": TERMINAL_KEYS["alacritty"],
    }
    for table in (forward, reverse):
        assert missing_rows(tools, table) == set()
        assert extra_rows(tools, table) == set()


def test_completeness_fails_for_a_row_without_a_declarer() -> None:
    table = {**TERMINAL_KEYS, "ghost": TERMINAL_KEYS["alacritty"]}
    tools = load_tools(REGISTRY)
    assert extra_rows(tools, table) == {"ghost"}
    assert missing_rows(tools, table) == set()


def test_a_declarer_without_a_row_is_refused_not_crashed() -> None:
    tool = dataclasses.replace(_alacritty(), id="fixture-term", name="Fixture")
    output = apply_install_tuning(tool, _LINUX, skip_recorded=True)
    assert output.refused == "no keys row for fixture-term"
    assert output.lines == ("Fixture keys not changed: no keys row for fixture-term",)
    post_install = run_post_install(tool, _LINUX)
    assert post_install.lines == output.lines
    assert post_install.warning is None
    assert not (Path.home() / ".config").exists()


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
