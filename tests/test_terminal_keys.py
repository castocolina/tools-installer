"""Terminal keys mechanism tests: golden bytes first, then the table."""

import dataclasses
import json
import os
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

from installer import terminal_keys
from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.post_install import apply_install_tuning, run_post_install
from installer.run import CommandError
from installer.terminal_keys import (
    CTRL_L,
    KEYS_PENDING,
    TERMINAL_KEYS,
    KeysRow,
    NotApplicable,
    OwnedRegion,
    Vendor,
    Writes,
    apply_terminal_keys,
    clear_binding,
    strip_terminal_keys,
    terminal_keys_pending,
    wezterm_show_keys,
)
from installer.terminal_regions import (
    WEZTERM_CREATED,
    WEZTERM_KEYS,
    WEZTERM_SKELETON,
    WEZTERM_UNVERIFIED,
    KeysPlan,
    Placement,
    TerminalShellError,
    ghostty_chord,
    ghostty_config_path,
    ghostty_default_files,
    kitty_chord,
    kitty_config_path,
    replace_owned_region,
    scan_ghostty,
    scan_kitty,
    validate_ghostty,
    validate_kitty,
    validate_toml,
    validate_wezterm,
    wezterm_chord,
    wezterm_config_path,
    wezterm_keys_body,
)
from installer.terminal_shell import sync_terminal_shells

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
_LINUX = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
_SUMMARY = (
    "Alacritty keys: Alt+Left and Alt+Right move by word, "
    "Control+Shift+K clears the screen and scrollback."
)
_PHASE_28_KEYS_REGION = (
    "# >>> tools-installer terminal-shell alacritty-keys >>>\n"
    '[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "\\u001bb"\n\n'
    '[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "\\u001bf"\n\n'
    '[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\naction = "ClearHistory"\n'
    "# <<< tools-installer terminal-shell alacritty-keys <<<\n"
)
_KEYS_REGION = (
    "# >>> tools-installer terminal-shell alacritty-keys >>>\n"
    '[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "\\u001bb"\n\n'
    '[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "\\u001bf"\n\n'
    '[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\nchars = "\\u000c"\n'
    "# <<< tools-installer terminal-shell alacritty-keys <<<\n"
)
_KEYS_REGION_NO_LEFT = (
    "# >>> tools-installer terminal-shell alacritty-keys >>>\n"
    '[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "\\u001bf"\n\n'
    '[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\nchars = "\\u000c"\n'
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


def _kitty() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "kitty")


def _kitty_config() -> Path:
    return Path.home() / ".config" / "kitty" / "kitty.conf"


_KITTY_LINUX = (
    "# >>> tools-installer terminal-shell kitty-keys >>>\n"
    "map --allow-fallback=shifted,ascii ctrl+shift+k send_text all \\x0c\n\n"
    "map --allow-fallback=shifted,ascii kitty_mod+t new_tab_with_cwd\n"
    "map kitty_mod+enter new_window_with_cwd\n"
    "map --allow-fallback=shifted,ascii kitty_mod+n new_os_window_with_cwd\n"
    "# <<< tools-installer terminal-shell kitty-keys <<<\n"
)
_KITTY_MACOS = (
    "# >>> tools-installer terminal-shell kitty-keys >>>\n"
    "map opt+left send_text all \\x1bb\n"
    "map opt+right send_text all \\x1bf\n"
    "map cmd+k send_text all \\x0c\n\n"
    "map --allow-fallback=shifted,ascii cmd+t new_tab_with_cwd\n"
    "map cmd+enter new_window_with_cwd\n"
    "map --allow-fallback=shifted,ascii cmd+n new_os_window_with_cwd\n"
    "# <<< tools-installer terminal-shell kitty-keys <<<\n"
)
_KITTY_SUMMARY = (
    "kitty keys: the clear chord sends Ctrl+L (screen and scrollback), Option+Left and "
    "Option+Right move by word on macOS, and new tabs and windows open in the current directory."
)
_WEZTERM_SUMMARY = (
    "WezTerm keys: the clear chord sends Ctrl+L (screen and scrollback), and Option+Left "
    "and Option+Right move by word on macOS, unless your config.keys already binds them."
)
_WEZTERM_PREFIX = (
    'local wezterm = require "wezterm"\nlocal config = {}\n'
    "-- >>> tools-installer terminal-shell wezterm-keys >>>\n"
)
_WEZTERM_GUARD = (
    "do\n"
    '  local wezterm = require "wezterm"\n'
    "  local act = wezterm.action\n"
    '  local alias = { CMD = "SUPER", WIN = "SUPER", OPT = "ALT", '
    'META = "ALT", CONTROL = "CTRL" }\n'
    "  local function chord(key, mods)\n"
    "    local set = {}\n"
    '    for name in string.gmatch(string.upper(mods or ""), "[^|%s]+") do\n'
    "      local m = alias[name] or name\n"
    '      if m ~= "NONE" then set[m] = true end\n'
    "    end\n"
    '    local k = key or ""\n'
    '    if string.match(k, "^%u$") then set.SHIFT = true end\n'
    "    local names = {}\n"
    "    for m in pairs(set) do names[#names + 1] = m end\n"
    "    table.sort(names)\n"
    '    return string.lower(k) .. "/" .. table.concat(names, "|")\n'
    "  end\n"
    "  config.keys = config.keys or {}\n"
    "  local taken = {}\n"
    "  for _, entry in ipairs(config.keys) do taken[chord(entry.key, entry.mods)] = true end\n"
    "  for _, entry in ipairs({\n"
)
_WEZTERM_SUFFIX = (
    "  }) do\n"
    "    if not taken[chord(entry.key, entry.mods)] then table.insert(config.keys, entry) end\n"
    "  end\n"
    "end\n"
    "-- <<< tools-installer terminal-shell wezterm-keys <<<\n"
    "return config\n"
)
_WEZTERM_LINUX = (
    _WEZTERM_PREFIX
    + _WEZTERM_GUARD
    + '    { key = "k", mods = "CTRL|SHIFT", action = act.SendString "\\x0c" },\n'
    + _WEZTERM_SUFFIX
)
_WEZTERM_MACOS = (
    _WEZTERM_PREFIX
    + _WEZTERM_GUARD
    + '    { key = "LeftArrow", mods = "OPT", action = act.SendString "\\x1bb" },\n'
    + '    { key = "RightArrow", mods = "OPT", action = act.SendString "\\x1bf" },\n'
    + '    { key = "k", mods = "SUPER", action = act.SendString "\\x0c" },\n'
    + _WEZTERM_SUFFIX
)


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
    assert set(TERMINAL_KEYS) == {"alacritty", "kitty", "wezterm", "ghostty"}
    assert row.ownership == OwnedRegion("alacritty-keys")
    assert row.created_record == "terminal-alacritty-created"
    assert row.sibling_regions == ("alacritty",)
    assert row.summary == _SUMMARY
    assert row.config_path("fedora", Path.home(), {}) == (
        Path.home() / ".config" / "alacritty" / "alacritty.toml"
    )
    assert replace_owned_region("", "alacritty-keys", row.plan("fedora", "", _config()).body) == (
        _KEYS_REGION
    )


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
    assert missing_rows(load_tools(REGISTRY), {}) == {"alacritty", "kitty", "wezterm", "ghostty"}


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


# --- Ghostty (30): resolver, scan, validator ---


@pytest.mark.parametrize(
    ("legacy", "preferred", "expected"),
    [
        (None, None, "config.ghostty"),
        ("x", None, "config"),
        ("x", "x", "config.ghostty"),
        ("x", "", "config"),
        ("", "", "config.ghostty"),
        (None, "x", "config.ghostty"),
    ],
)
def test_ghostty_config_path_linux_cases(
    tmp_path: Path, legacy: str | None, preferred: str | None, expected: str
) -> None:
    root = tmp_path / ".config/ghostty"
    root.mkdir(parents=True)
    for name, value in (("config", legacy), ("config.ghostty", preferred)):
        if value is not None:
            (root / name).write_text(value)
    assert ghostty_config_path("fedora", tmp_path, {}) == root / expected
    assert (
        ghostty_config_path("fedora", tmp_path, {"XDG_CONFIG_HOME": str(tmp_path / "x")})
        == tmp_path / "x/ghostty/config.ghostty"
    )


@pytest.mark.parametrize(
    ("support", "xdg", "expected"),
    [
        ("config.ghostty", "config.ghostty", "support/config.ghostty"),
        ("config", None, "support/config"),
        (None, "config.ghostty", "xdg/config.ghostty"),
        (None, "config", "xdg/config"),
        (None, None, "support/config.ghostty"),
    ],
)
def test_ghostty_config_path_macos_cases(
    tmp_path: Path, support: str | None, xdg: str | None, expected: str
) -> None:
    roots = {
        "support": tmp_path / "Library/Application Support/com.mitchellh.ghostty",
        "xdg": tmp_path / ".config/ghostty",
    }
    for root, name in ((roots["support"], support), (roots["xdg"], xdg)):
        if name:
            root.mkdir(parents=True, exist_ok=True)
            (root / name).write_text("x")
    root_name, name = expected.split("/")
    assert ghostty_config_path("macos", tmp_path, {}) == roots[root_name] / name


def test_ghostty_default_files_follow_load_order(tmp_path: Path) -> None:
    x = tmp_path / "x/ghostty"
    s = tmp_path / "Library/Application Support/com.mitchellh.ghostty"
    env = {"XDG_CONFIG_HOME": str(tmp_path / "x")}
    assert ghostty_default_files("fedora", tmp_path, env) == (x / "config", x / "config.ghostty")
    assert ghostty_default_files("macos", tmp_path, env) == (
        x / "config",
        x / "config.ghostty",
        s / "config",
        s / "config.ghostty",
    )


@pytest.mark.parametrize(
    ("binding", "expected"),
    [
        ("ctrl+shift+k=reset", "ctrl+shift+k"),
        ("Shift+Control+K=reset", "ctrl+shift+k"),
        ("control+shift+key_k=text:x", "ctrl+shift+k"),
        ("ctrl+shift+physical:k=reset", "ctrl+shift+k"),
        ("shift+ctrl+unicode:k=reset", "ctrl+shift+k"),
        ("all:performable:ctrl+shift+k=reset", "ctrl+shift+k"),
        ("cmd+k=clear_screen", "super+k"),
        ("command+k=x", "super+k"),
        ("option+left=esc:b", "alt+left"),
        ("opt+left=x", "alt+left"),
        ("ctrl+a>k=x", None),
        ("mytable/ctrl+k=x", None),
        ("chain=ctrl+k", None),
        ("", None),
    ],
)
def test_ghostty_chord_normalizes(binding: str, expected: str | None) -> None:
    assert ghostty_chord(binding) == expected


def test_scan_ghostty_reads_user_lines_outside_the_regions(tmp_path: Path) -> None:
    path = tmp_path / ".config/ghostty/config.ghostty"
    path.parent.mkdir(parents=True)
    owned = replace_owned_region(
        replace_owned_region("", "ghostty", "command = /usr/bin/zsh -l"),
        "ghostty-keys",
        r"keybind = ctrl+shift+k=text:\x0c",
    )
    path.write_text(owned)
    scan = scan_ghostty("fedora", tmp_path, {})
    assert not scan.user_command and not scan.config_file and not scan.taken and not scan.clears
    path.write_text(
        owned + "command = /bin/bash\nkeybind = ctrl+shift+k=reset\nconfig-file = extra.conf\n"
    )
    scan = scan_ghostty("fedora", tmp_path, {})
    assert scan.user_command and scan.config_file and scan.taken == frozenset({"ctrl+shift+k"})


def test_scan_ghostty_covers_every_default_file(tmp_path: Path) -> None:
    files = ghostty_default_files("macos", tmp_path, {})
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
    files[0].write_text("command = /bin/sh\n")
    files[1].write_text("keybind = ctrl+shift+k=x\n")
    files[2].write_text("keybind = cmd+k=x\n")
    assert scan_ghostty("fedora", tmp_path, {}).user_command
    assert scan_ghostty("fedora", tmp_path, {}).taken == frozenset({"ctrl+shift+k"})
    assert scan_ghostty("macos", tmp_path, {}).taken == frozenset({"ctrl+shift+k", "super+k"})


def test_scan_ghostty_parsing_rules(tmp_path: Path) -> None:
    path = tmp_path / ".config/ghostty/config"
    path.parent.mkdir(parents=True)
    path.write_text(
        '# command = x\ninvalid\n command = "x"\n keybind = "ctrl+shift+k=reset"\nkeybind = clear\n'
    )
    scan = scan_ghostty("fedora", tmp_path, {})
    assert scan.user_command and scan.clears and scan.taken == frozenset({"ctrl+shift+k"})
    path.write_text("command =\nkeybind =\n")
    scan = scan_ghostty("fedora", tmp_path, {})
    assert scan.user_command and scan.clears


@pytest.mark.parametrize("platform", ["fedora", "macos"])
def test_scan_ghostty_blocks_on_an_unscannable_file_loaded_before_the_target(
    tmp_path: Path, platform: str
) -> None:
    files = ghostty_default_files(platform, tmp_path, {})
    files[0].parent.mkdir(parents=True)
    files[0].write_bytes(b"\xff\xfe\x00")
    files[-1].parent.mkdir(parents=True, exist_ok=True)
    files[-1].write_text("font-size = 12\n")
    scan = scan_ghostty(platform, tmp_path, {})
    assert scan.blocked == (
        "ghostty: partial: config could not be read and loads before config.ghostty; "
        "nothing written",
    )
    assert scan.reports == scan.blocked


def test_scan_ghostty_only_reports_an_unscannable_file_loaded_after_the_target(
    tmp_path: Path,
) -> None:
    files = ghostty_default_files("fedora", tmp_path, {})
    files[0].parent.mkdir(parents=True)
    files[0].write_text("command = /bin/bash\n")
    files[1].mkdir()
    scan = scan_ghostty("fedora", tmp_path, {})
    assert scan.blocked == () and scan.user_command
    assert scan.reports == (
        "ghostty: partial: config.ghostty could not be read; settings there are not checked",
    )


def test_validate_ghostty_accepts_both_regions_and_refuses_a_foreign_line() -> None:
    keys = replace_owned_region("", "ghostty-keys", "keybind = x=y")
    shell = replace_owned_region("", "ghostty", "command = /bin/sh")
    validate_ghostty(keys + shell)
    validate_ghostty("font-size = 1\n")
    with pytest.raises(
        TerminalShellError, match="ghostty-keys region would hold a line that is not a keybind"
    ):
        validate_ghostty(keys.replace("keybind = x=y", "font-size = 1"))
    with pytest.raises(
        TerminalShellError, match="ghostty region would hold a line that is not a command"
    ):
        validate_ghostty(shell.replace("command = /bin/sh", "font-size = 1"))


# --- Ghostty (30): row, goldens, conflicts ---
_GHOSTTY_SUMMARY = (
    "Ghostty keys: the clear chord sends Ctrl+L (screen and scrollback); "
    "new tabs, windows and splits already open in the current directory."
)
_GHOSTTY_LINUX = (
    "# >>> tools-installer terminal-shell ghostty-keys >>>\n"
    "keybind = ctrl+shift+k=text:\\x0c\n"
    "# <<< tools-installer terminal-shell ghostty-keys <<<\n"
)
_GHOSTTY_MACOS = _GHOSTTY_LINUX.replace("ctrl+shift+k", "super+k")
_MACOS = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0")


def _ghostty() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "ghostty")


def _ghostty_config(platform: str = "fedora") -> Path:
    return ghostty_config_path(platform, Path.home(), os.environ)


def test_ghostty_golden_linux_created_file() -> None:
    assert run_post_install(_ghostty(), _LINUX).lines == (_GHOSTTY_SUMMARY,)
    assert _ghostty_config().read_text() == _GHOSTTY_LINUX
    assert (_state_dir() / "terminal-ghostty-created-path").read_text() == f"{_ghostty_config()}\n"


def test_ghostty_golden_macos_created_file() -> None:
    assert run_post_install(_ghostty(), _MACOS).lines == (
        _GHOSTTY_SUMMARY,
        "ghostty: cmd+k now sends Ctrl+L; it was clear_screen.",
    )
    assert _ghostty_config("macos").read_text() == _GHOSTTY_MACOS


@pytest.mark.parametrize("platform", [_MACOS, _LINUX], ids=["macos", "linux"])
def test_ghostty_include_is_reported_only_by_macos_keys(platform: Platform) -> None:
    path = _ghostty_config(platform.os)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("config-file = extra.conf\n")
    result = run_post_install(_ghostty(), platform)
    warning = "ghostty: partial: you include other files (config-file); they are not followed"
    assert (warning in result.lines) == (platform.os == "macos")
    assert path.read_text() == (
        (_GHOSTTY_MACOS if platform.os == "macos" else _GHOSTTY_LINUX)
        + "config-file = extra.conf\n"
    )


def test_ghostty_never_writes_a_global_alt_switch() -> None:
    for platform in (_LINUX, _MACOS):
        run_post_install(_ghostty(), platform)
        text = _ghostty_config(platform.os).read_text() + _GHOSTTY_LINUX + _GHOSTTY_MACOS
        assert not any(
            s in text
            for s in (
                "macos-option-as-alt",
                "option-as-alt",
                "option_as_alt",
                "opt+",
                "alt+left",
                "alt+right",
            )
        )


def test_ghostty_region_goes_above_user_content() -> None:
    path = _ghostty_config()
    path.parent.mkdir(parents=True)
    path.write_text("font-size = 12\n")
    run_post_install(_ghostty(), _LINUX)
    assert path.read_text() == _GHOSTTY_LINUX + "font-size = 12\n"


@pytest.mark.parametrize(
    ("platform", "index"),
    [("fedora", 0), ("fedora", 1), ("macos", 0), ("macos", 1), ("macos", 2), ("macos", 3)],
)
def test_ghostty_user_chord_is_kept_and_reported(platform: str, index: int) -> None:
    files = ghostty_default_files(platform, Path.home(), os.environ)
    target = files[-1]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("font-size = 12\n")
    path = files[index]
    path.parent.mkdir(parents=True, exist_ok=True)
    chord = "cmd+k" if platform == "macos" else "ctrl+shift+k"
    content = f"keybind = {chord}=reset\n"
    path.write_text(content)
    result = run_post_install(_ghostty(), _MACOS if platform == "macos" else _LINUX)
    assert path.read_text() == content
    assert (
        f"ghostty: partial: you already bind {'super+k' if platform == 'macos' else chord}"
        in result.lines
    )
    assert (_state_dir() / "terminal-tuning-ghostty").exists()


def test_ghostty_legacy_physical_chord_is_kept_and_reported() -> None:
    legacy, target = ghostty_default_files("fedora", Path.home(), os.environ)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("keybind = ctrl+shift+physical:k=reset\n")
    target.write_text("font-size = 12\n")
    result = run_post_install(_ghostty(), _LINUX)
    assert "ghostty: partial: you already bind ctrl+shift+k" in result.lines
    assert target.read_text() == "font-size = 12\n"
    assert legacy.read_text() == "keybind = ctrl+shift+physical:k=reset\n"


@pytest.mark.parametrize("value", ["clear", ""])
def test_ghostty_keybind_clear_refuses(value: str) -> None:
    path = _ghostty_config()
    path.parent.mkdir(parents=True)
    text = f"keybind = {value}\n"
    path.write_text(text)
    reason = "you set keybind = clear, which would clear these keys"
    row = TERMINAL_KEYS["ghostty"]
    assert apply_terminal_keys(
        row, "ghostty", "fedora", Path.home(), os.environ, skip_recorded=False
    ) == ((), reason)
    assert terminal_keys_pending(row, "ghostty", "fedora", Path.home(), os.environ) == reason
    assert path.read_text() == text


@pytest.mark.parametrize("platform", ["fedora", "macos"])
def test_ghostty_unscannable_earlier_file_refuses_and_writes_nothing(platform: str) -> None:
    files = ghostty_default_files(platform, Path.home(), os.environ)
    files[0].parent.mkdir(parents=True, exist_ok=True)
    files[0].write_bytes(b"\xff\xfe\x00")
    files[-1].parent.mkdir(parents=True, exist_ok=True)
    files[-1].write_text("font-size = 12\n")
    row = TERMINAL_KEYS["ghostty"]
    reason = (
        "ghostty: partial: config could not be read and loads before config.ghostty; "
        "nothing written"
    )
    assert apply_terminal_keys(
        row, "ghostty", platform, Path.home(), os.environ, skip_recorded=False
    ) == ((), reason)
    assert terminal_keys_pending(row, "ghostty", platform, Path.home(), os.environ) == reason
    assert files[-1].read_text() == "font-size = 12\n" and files[0].read_bytes() == b"\xff\xfe\x00"
    assert not (_state_dir() / "terminal-tuning-ghostty").exists()
    assert run_post_install(_ghostty(), _MACOS if platform == "macos" else _LINUX).lines == (
        f"Ghostty keys not changed: {reason}",
    )
    files[0].write_text("font-size = 10\n")
    assert (
        apply_terminal_keys(row, "ghostty", platform, Path.home(), os.environ, skip_recorded=False)[
            1
        ]
        is None
    )
    assert "ghostty-keys >>>" in files[-1].read_text()


def test_ghostty_row_declaration() -> None:
    row = TERMINAL_KEYS["ghostty"]
    assert row.ownership == OwnedRegion("ghostty-keys", "#", Placement.TOP)
    assert row.sibling_regions == ("ghostty",) and row.created_record == "terminal-ghostty-created"
    assert row.bind_created_path and row.strip_files is ghostty_default_files
    assert not row.validate_on_status and row.readback is None and row.clear == CTRL_L
    assert row.config_path is ghostty_config_path and isinstance(row.same_directory, Vendor)
    assert "2026-11-20" in row.same_directory.note and row.same_directory.note.endswith(
        "The installer writes nothing."
    )
    assert _ghostty().post_install == ("apply_terminal_tuning",)


def test_ghostty_status_and_apply_agree_on_a_refused_plan() -> None:
    row = TERMINAL_KEYS["ghostty"]
    run_post_install(_ghostty(), _LINUX)
    path = _ghostty_config()
    path.write_text(path.read_text() + "keybind = clear\n")
    assert terminal_keys_pending(row, "ghostty", "fedora", Path.home(), os.environ) is None
    assert apply_terminal_keys(
        row, "ghostty", "fedora", Path.home(), os.environ, skip_recorded=True
    ) == ((), None)


def test_ghostty_strip_leaves_a_file_it_did_not_create_when_the_resolver_moved() -> None:
    run_post_install(_ghostty(), _LINUX)
    _ghostty_config().unlink()
    legacy = Path.home() / ".config/ghostty/config"
    legacy.write_text("font-size = 12\n")
    result = strip_terminal_keys(
        TERMINAL_KEYS["ghostty"], "ghostty", "fedora", Path.home(), os.environ
    )
    assert (
        "created config at" in result[0] and "is not the file now resolved; left alone" in result[0]
    )
    assert legacy.read_text() == "font-size = 12\n"


def test_ghostty_drift_is_pending_only_without_a_record() -> None:
    row = TERMINAL_KEYS["ghostty"]
    args = (row, "ghostty", "fedora", Path.home(), os.environ)
    assert terminal_keys_pending(*args) == KEYS_PENDING
    assert apply_terminal_keys(*args, skip_recorded=False)[1] is None
    assert terminal_keys_pending(*args) is None
    path = _ghostty_config()
    path.write_text(path.read_text().replace("text:\\x0c", "text:old"))
    assert terminal_keys_pending(*args) == KEYS_PENDING
    path.write_text("")
    assert terminal_keys_pending(*args) is None


def test_ghostty_reconfigure_restores_the_region_and_a_second_one_changes_nothing() -> None:
    row = TERMINAL_KEYS["ghostty"]
    args = (row, "ghostty", "fedora", Path.home(), os.environ)
    apply_terminal_keys(*args, skip_recorded=False)
    path = _ghostty_config()
    path.write_text(path.read_text().replace("text:\\x0c", "text:old"))
    assert apply_terminal_keys(*args, skip_recorded=True) == ((_GHOSTTY_SUMMARY,), None)
    assert path.read_text() == _GHOSTTY_LINUX
    assert apply_terminal_keys(*args, skip_recorded=True) == ((), None)
    assert apply_terminal_keys(*args, skip_recorded=False)[1] is None
    assert path.read_text() == _GHOSTTY_LINUX


@pytest.mark.parametrize("platform", ["fedora", "macos"])
def test_ghostty_reconfigure_does_not_restore_a_deleted_recorded_region(platform: str) -> None:
    args = (TERMINAL_KEYS["ghostty"], "ghostty", platform, Path.home(), os.environ)
    apply_terminal_keys(*args, skip_recorded=False)
    path = _ghostty_config(platform)
    path.write_text("user = kept\n")
    assert terminal_keys_pending(*args) is None
    assert apply_terminal_keys(*args, skip_recorded=True) == ((), None)
    assert path.read_text() == "user = kept\n"
    assert (_state_dir() / "terminal-tuning-ghostty").exists()


@pytest.mark.parametrize("platform", ["fedora", "macos"])
def test_ghostty_strip_drops_the_regions_the_record_and_a_created_file(platform: str) -> None:
    args = (TERMINAL_KEYS["ghostty"], "ghostty", platform, Path.home(), os.environ)
    apply_terminal_keys(*args, skip_recorded=False)
    path = _ghostty_config(platform)
    assert strip_terminal_keys(*args) == ()
    assert not path.exists() and not path.parent.exists()
    assert not (_state_dir() / "terminal-tuning-ghostty").exists()


@pytest.mark.parametrize("platform", ["fedora", "macos"])
def test_ghostty_strip_keeps_every_user_byte(platform: str) -> None:
    path = _ghostty_config(platform)
    path.parent.mkdir(parents=True)
    path.write_text("font-size = 12\n")
    args = (TERMINAL_KEYS["ghostty"], "ghostty", platform, Path.home(), os.environ)
    apply_terminal_keys(*args, skip_recorded=False)
    path.write_text(replace_owned_region(path.read_text(), "ghostty", "command = /usr/bin/zsh -l"))
    assert strip_terminal_keys(*args) == ()
    assert path.read_text() == "font-size = 12\n"


def test_ghostty_strip_with_no_config_file_is_quiet() -> None:
    assert (
        strip_terminal_keys(TERMINAL_KEYS["ghostty"], "ghostty", "fedora", Path.home(), os.environ)
        == ()
    )


@pytest.mark.parametrize("platform", ["fedora", "macos"])
def test_ghostty_strip_removes_regions_left_in_every_default_file(platform: str) -> None:
    files = ghostty_default_files(platform, Path.home(), os.environ)
    legacy = files[0]
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("font-size = 12\n")
    args = (TERMINAL_KEYS["ghostty"], "ghostty", platform, Path.home(), os.environ)
    apply_terminal_keys(*args, skip_recorded=False)
    legacy.write_text(
        replace_owned_region(legacy.read_text(), "ghostty", "command = /usr/bin/zsh -l")
    )
    target = files[-1]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("theme = x\n")
    assert strip_terminal_keys(*args) == ()
    assert legacy.read_text() == "font-size = 12\n"
    assert target.read_text() == "theme = x\n"
    assert not (_state_dir() / "terminal-tuning-ghostty").exists()


def test_cross_row_tests_visit_ghostty() -> None:
    assert "ghostty" in TERMINAL_KEYS


def test_kitty_golden_linux_created_file() -> None:
    result = run_post_install(_kitty(), _LINUX)
    assert result.lines == (
        _KITTY_SUMMARY,
        "kitty: ctrl+shift+k now clears the screen and scrollback; it was scroll_line_up, "
        "and ctrl+shift+up still scrolls.",
        "kitty: restart kitty or press ctrl+shift+f5 if it was running before kitty.conf existed.",
        "kitty: new_tab_with_cwd, new_window_with_cwd and new_os_window_with_cwd "
        "replace new_tab, new_window and new_os_window on those chords.",
    )
    assert _kitty_config().read_bytes() == _KITTY_LINUX.encode()
    marker = _state_dir() / "terminal-kitty-created-path"
    assert marker.read_text() == f"{_kitty_config()}\n"


def test_kitty_golden_macos_created_file() -> None:
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0")
    result = run_post_install(_kitty(), macos)
    assert result.lines == (
        _KITTY_SUMMARY,
        "kitty: cmd+k now clears the screen and scrollback; it was clear_terminal to_cursor.",
        "kitty: restart kitty or press ctrl+cmd+, if it was running before kitty.conf existed.",
        "kitty: new_tab_with_cwd, new_window_with_cwd and new_os_window_with_cwd "
        "replace new_tab, new_window and new_os_window on those chords.",
    )
    assert _kitty_config().read_bytes() == _KITTY_MACOS.encode()
    assert "macos_option_as_alt" not in _KITTY_MACOS


def test_kitty_never_writes_option_as_alt() -> None:
    assert "macos_option_as_alt" not in _KITTY_LINUX + _KITTY_MACOS
    assert "option_as_alt" not in _KITTY_LINUX + _KITTY_MACOS


def test_kitty_user_map_is_kept_and_reported() -> None:
    config = _kitty_config()
    config.parent.mkdir(parents=True)
    config.write_text("map ctrl+shift+k scroll_line_up\n")
    result = run_post_install(_kitty(), _LINUX)
    assert "ctrl+shift+k send_text" not in config.read_text()
    assert config.read_text().endswith("map ctrl+shift+k scroll_line_up\n")
    assert "kitty: partial: you already map ctrl+shift+k" in result.lines


def test_kitty_config_path_follows_kittys_order(tmp_path: Path) -> None:
    xdg = tmp_path / "xdg"
    fallback = tmp_path / ".config"
    (fallback / "kitty").mkdir(parents=True)
    (fallback / "kitty" / "kitty.conf").touch()
    assert kitty_config_path("fedora", tmp_path, {"XDG_CONFIG_HOME": str(xdg)}) == (
        fallback / "kitty" / "kitty.conf"
    )
    direct = tmp_path / "direct"
    assert kitty_config_path("fedora", tmp_path, {"KITTY_CONFIG_DIRECTORY": str(direct)}) == (
        direct / "kitty.conf"
    )


def test_kitty_chord_normalizes_aliases_kitty_mod_and_order() -> None:
    assert kitty_chord("shift+control+K", "ctrl+shift") == "ctrl+shift+k"
    assert kitty_chord("kitty_mod+t", "alt+ctrl") == "alt+ctrl+t"
    assert kitty_chord("opt+left", "ctrl+shift") == "alt+left"
    assert kitty_chord("cmd+k", "ctrl+shift") == "super+k"
    assert kitty_chord("command+option+x", "ctrl+shift") == "alt+super+x"


def test_kitty_region_goes_above_user_content() -> None:
    config = _kitty_config()
    config.parent.mkdir(parents=True)
    config.write_text("font_size 12\n")
    run_post_install(_kitty(), _LINUX)
    assert config.read_bytes() == (_KITTY_LINUX + "font_size 12\n").encode()


def test_validate_kitty_refuses_a_non_map_line() -> None:
    with pytest.raises(TerminalShellError):
        validate_kitty(
            "# >>> tools-installer terminal-shell kitty-keys >>>\n"
            "shell /bin/sh\n"
            "# <<< tools-installer terminal-shell kitty-keys <<<\n"
        )


def test_kitty_include_relative_to_the_config_is_scanned(tmp_path: Path) -> None:
    path = tmp_path / "kitty.conf"
    (tmp_path / "theme.conf").write_text("map ctrl+shift+k x\n")
    scan = scan_kitty("include theme.conf\n", path)
    assert "ctrl+shift+k" in scan.taken


def test_kitty_indented_include_is_scanned(tmp_path: Path) -> None:
    path = tmp_path / "kitty.conf"
    (tmp_path / "theme.conf").write_text("map ctrl+shift+k x\n")
    scan = scan_kitty("  \tinclude theme.conf\n", path)
    assert "ctrl+shift+k" in scan.taken


def test_kitty_cleanup_after_a_resolver_change_leaves_the_other_file_alone(tmp_path: Path) -> None:
    home = tmp_path / "home"
    original_dir = home / ".config" / "kitty"
    original_env = {
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
    }
    row = TERMINAL_KEYS["kitty"]
    assert (
        apply_terminal_keys(row, "kitty", "fedora", home, original_env, skip_recorded=False)[1]
        is None
    )
    original = original_dir / "kitty.conf"
    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir()
    fallback = fallback_dir / "kitty.conf"
    fallback.touch()
    changed_env = {**original_env, "KITTY_CONFIG_DIRECTORY": str(fallback_dir)}
    warnings = strip_terminal_keys(row, "kitty", "fedora", home, changed_env)
    assert fallback.exists() and fallback.read_text() == ""
    assert original.exists()
    assert (home / ".local/share/tools-installer/terminal-tuning-kitty").exists()
    assert (home / ".local/share/tools-installer/terminal-kitty-created").exists()
    assert len(warnings) == 1


def test_kitty_include_report_is_returned_by_install() -> None:
    config = _kitty_config()
    config.parent.mkdir(parents=True)
    config.write_text("geninclude generated.conf\n")
    result = run_post_install(_kitty(), _LINUX)
    assert "kitty: partial: geninclude is not followed; maps there are not checked" in result.lines


def test_kitty_globinclude_is_scanned(tmp_path: Path) -> None:
    (tmp_path / "themes").mkdir()
    (tmp_path / "themes" / "a.conf").write_text("map kitty_mod+t new_tab\n")
    scan = scan_kitty("globinclude themes/*.conf\n", tmp_path / "kitty.conf")
    assert "ctrl+shift+t" in scan.taken


def test_kitty_nested_include_is_relative_to_its_own_file(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "one.conf").write_text("include two.conf\n")
    (tmp_path / "sub" / "two.conf").write_text("map kitty_mod+n x\n")
    scan = scan_kitty("include sub/one.conf\n", tmp_path / "kitty.conf")
    assert "ctrl+shift+n" in scan.taken


def test_kitty_include_expands_environment_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KITTY_EXTRA", str(tmp_path / "extra.conf"))
    (tmp_path / "extra.conf").write_text("map ctrl+shift+k x\n")
    scan = scan_kitty("include $KITTY_EXTRA\n", tmp_path / "kitty.conf")
    assert "ctrl+shift+k" in scan.taken


def test_kitty_unreadable_include_is_reported(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.conf"
    invalid.write_bytes(b"\xff\n")
    fifo = tmp_path / "fifo.conf"
    os.mkfifo(fifo)
    scan = scan_kitty(
        "include invalid.conf\ninclude fifo.conf\ninclude missing.conf\n", tmp_path / "kitty.conf"
    )
    assert (
        f"kitty: partial: {invalid.name} could not be read; maps there are not checked"
        in scan.reports
    )
    assert (
        f"kitty: partial: {fifo.name} could not be read; maps there are not checked" in scan.reports
    )
    assert not any("missing.conf" in report for report in scan.reports)


def test_kitty_include_cycle_terminates(tmp_path: Path) -> None:
    (tmp_path / "a.conf").write_text("map ctrl+shift+a x\ninclude b.conf\n")
    (tmp_path / "b.conf").write_text("map ctrl+shift+b x\ninclude a.conf\n")
    scan = scan_kitty("include a.conf\n", tmp_path / "kitty.conf")
    assert scan.taken == frozenset({"ctrl+shift+a", "ctrl+shift+b"})
    assert "depth 8" not in " ".join(scan.reports)


def test_kitty_symlink_loop_on_the_config_keeps_its_own_maps(tmp_path: Path) -> None:
    config = tmp_path / "kitty.conf"
    os.symlink(config, config)
    scan = scan_kitty("map ctrl+shift+k x\n", config)
    assert "ctrl+shift+k" in scan.taken
    # Python before 3.13 raises RuntimeError from resolve() on a loop and the scan reports it;
    # later versions resolve it without an error, so both outcomes keep the maps.
    assert scan.reports in (
        (),
        ("kitty: partial: kitty.conf could not be read; maps there are not checked",),
    )


def test_kitty_symlink_loop_is_reported_and_apply_continues(tmp_path: Path) -> None:
    loop = tmp_path / "loop.conf"
    os.symlink(loop, loop)
    config = tmp_path / "kitty.conf"
    config.write_text("include loop.conf\n")
    scan = scan_kitty(config.read_text(), config)
    assert scan.reports == (
        f"kitty: partial: {loop.name} could not be read; maps there are not checked",
    )
    result = apply_terminal_keys(
        TERMINAL_KEYS["kitty"],
        "kitty",
        "fedora",
        tmp_path,
        {"KITTY_CONFIG_DIRECTORY": str(tmp_path)},
        skip_recorded=False,
    )
    assert result[1] is None
    assert "kitty-keys >>>" in config.read_text()


def test_kitty_kitty_mod_in_an_include_is_followed(tmp_path: Path) -> None:
    (tmp_path / "theme.conf").write_text("kitty_mod ctrl+alt\nmap ctrl+alt+enter x\n")
    scan = scan_kitty("include theme.conf\n", tmp_path / "kitty.conf")
    assert "alt+ctrl+enter" in scan.taken


def test_kitty_geninclude_and_envinclude_are_reported_not_followed(tmp_path: Path) -> None:
    scan = scan_kitty("geninclude foo\nenvinclude BAR\n", tmp_path / "kitty.conf")
    assert "kitty: partial: geninclude is not followed; maps there are not checked" in scan.reports
    assert "kitty: partial: envinclude is not followed; maps there are not checked" in scan.reports


def test_kitty_options_and_sequences_take_the_chord(tmp_path: Path) -> None:
    scan = scan_kitty("map --when-focus-on var:x ctrl+shift+k y\n", tmp_path / "kitty.conf")
    assert "ctrl+shift+k" in scan.taken
    sequenced = scan_kitty("map ctrl+shift+k>x y\n", tmp_path / "kitty.conf")
    assert "ctrl+shift+k" in sequenced.taken


def test_kitty_clear_all_shortcuts_yes_refuses() -> None:
    config = _kitty_config()
    config.parent.mkdir(parents=True)
    config.write_text("clear_all_shortcuts yes\n")
    before = config.read_bytes()
    result = run_post_install(_kitty(), _LINUX)
    reason = "you set clear_all_shortcuts yes, which would clear these keys"
    assert result.lines == (f"kitty keys not changed: {reason}",)
    assert config.read_bytes() == before
    assert (
        terminal_keys_pending(TERMINAL_KEYS["kitty"], "kitty", "fedora", Path.home(), os.environ)
        == reason
    )


def test_kitty_clear_all_shortcuts_no_allows_tuning() -> None:
    scan = scan_kitty("clear_all_shortcuts no\n", _kitty_config())
    assert not scan.clears_all


def test_kitty_clear_all_shortcuts_yes_in_an_include_refuses(tmp_path: Path) -> None:
    (tmp_path / "clear.conf").write_text("clear_all_shortcuts yes\n")
    scan = scan_kitty("include clear.conf\n", tmp_path / "kitty.conf")
    assert scan.clears_all


def test_kitty_clear_all_shortcuts_yes_is_sticky() -> None:
    scan = scan_kitty("clear_all_shortcuts yes\nclear_all_shortcuts no\n", _kitty_config())
    assert scan.clears_all


def test_kitty_include_with_spaces_is_scanned(tmp_path: Path) -> None:
    (tmp_path / "themes").mkdir()
    (tmp_path / "themes" / "my keys.conf").write_text("map ctrl+shift+k x\n")
    scan = scan_kitty("include themes/my keys.conf\n", tmp_path / "kitty.conf")
    assert "ctrl+shift+k" in scan.taken


@pytest.mark.parametrize(("platform", "name"), [("fedora", "linux.conf"), ("macos", "macos.conf")])
def test_kitty_include_expands_platform(tmp_path: Path, platform: str, name: str) -> None:
    (tmp_path / name).write_text("map ctrl+shift+k x\n")
    scan = scan_kitty("include ${KITTY_OS}.conf\n", tmp_path / "kitty.conf", platform)
    assert "ctrl+shift+k" in scan.taken


def test_kitty_map_skips_option_values_and_return_alias(tmp_path: Path) -> None:
    source = "map --allow-fallback shifted,ascii ctrl+shift+k something\nmap ctrl+return x\n"
    scan = scan_kitty(source, tmp_path / "kitty.conf")
    assert {"ctrl+shift+k", "ctrl+enter"} <= scan.taken


def test_kitty_include_expands_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    extra = Path.home() / "extra.conf"
    extra.write_text("map ctrl+shift+k x\n")
    scan = scan_kitty("include ~/extra.conf\n", tmp_path / "kitty.conf")
    assert "ctrl+shift+k" in scan.taken


def test_kitty_deep_include_chain_stops_at_the_cap(tmp_path: Path) -> None:
    for index in range(12):
        following = f"include {index + 1}.conf\n" if index < 11 else "map ctrl+shift+k x\n"
        (tmp_path / f"{index}.conf").write_text(following)
    scan = scan_kitty("include 0.conf\n", tmp_path / "kitty.conf")
    assert (
        "kitty: partial: include scan stopped at depth 8; maps beyond it are not checked"
        in scan.reports
    )


def test_kitty_include_file_cap_is_reported(tmp_path: Path) -> None:
    many = tmp_path / "many"
    many.mkdir()
    for index in range(70):
        (many / f"f{index:02}.conf").write_text("# empty\n")
    scan = scan_kitty("globinclude many/*.conf\n", tmp_path / "kitty.conf")
    assert (
        scan.reports.count(
            "kitty: partial: include scan stopped at 64 files; maps beyond it are not checked"
        )
        == 1
    )


def test_kitty_clear_all_shortcuts_added_after_a_recorded_install_stays_quiet() -> None:
    run_post_install(_kitty(), _LINUX)
    config = _kitty_config()
    config.write_text(config.read_text() + "clear_all_shortcuts yes\n")
    before = config.read_bytes()
    assert apply_terminal_keys(
        TERMINAL_KEYS["kitty"], "kitty", "fedora", Path.home(), os.environ, skip_recorded=True
    ) == ((), None)
    assert config.read_bytes() == before
    assert (
        terminal_keys_pending(TERMINAL_KEYS["kitty"], "kitty", "fedora", Path.home(), os.environ)
        is None
    )


def _pending() -> str | None:
    return terminal_keys_pending(
        TERMINAL_KEYS["alacritty"], "alacritty", "fedora", Path.home(), os.environ
    )


def _reapply() -> tuple[tuple[str, ...], str | None]:
    return apply_terminal_keys(
        TERMINAL_KEYS["alacritty"],
        "alacritty",
        "fedora",
        Path.home(),
        os.environ,
        skip_recorded=True,
    )


def _edit_keys_region(text: str) -> str:
    return text.replace('chars = "\\u001bf"', 'chars = "x"')


def test_drift_never_applied_reads_pending() -> None:
    assert _pending() == KEYS_PENDING
    _config().parent.mkdir(parents=True)
    _config().write_text(_USER_FONT)
    assert _pending() == KEYS_PENDING


def test_drift_recorded_and_deleted_region_is_the_users() -> None:
    config = _config()
    config.parent.mkdir(parents=True)
    config.write_text(_USER_FONT)
    run_post_install(_alacritty(), _LINUX)
    config.write_text(replace_owned_region(config.read_text(), "alacritty-keys", None))

    assert _pending() is None
    assert _reapply() == ((), None)
    assert config.read_bytes() == _USER_FONT.encode()


def test_drift_recorded_current_region_is_quiet() -> None:
    run_post_install(_alacritty(), _LINUX)
    before = _config().read_bytes()

    assert _pending() is None
    assert _reapply() == ((), None)
    assert _config().read_bytes() == before


def _wezterm() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "wezterm")


def _wezterm_config() -> Path:
    return Path.home() / ".config" / "wezterm" / "wezterm.lua"


def test_wezterm_helpers_generate_regions_and_resolve_paths(tmp_path: Path) -> None:
    assert wezterm_config_path(tmp_path, {}) == tmp_path / ".config" / "wezterm" / "wezterm.lua"
    assert wezterm_keys_body((("k", "CTRL|SHIFT", "\x0c"),)).startswith("do\n")
    assert WEZTERM_KEYS == "wezterm-keys"


def test_no_test_runs_wezterm_even_when_it_is_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "bin" / "wezterm"
    binary.parent.mkdir()
    marker = tmp_path / "ran"
    binary.write_text(f"#!/bin/sh\ntouch {marker}\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ['PATH']}")
    result = run_post_install(_wezterm(), _LINUX)
    assert result.lines == (_WEZTERM_SUMMARY,)
    assert not marker.exists()
    assert terminal_keys.wezterm_show_keys is not wezterm_show_keys


def test_wezterm_show_keys_runs_the_exact_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "wezterm.lua"
    calls: list[tuple[list[str], float | None]] = []

    def found(name: str) -> str:
        del name
        return "/usr/bin/wezterm"

    def capture(argv: list[str], *, timeout: float | None = None) -> str:
        calls.append((argv, timeout))
        return "OUT"

    def missing(name: str) -> None:
        del name

    monkeypatch.setattr(terminal_keys, "which", found)
    monkeypatch.setattr(terminal_keys, "run_output", capture)
    assert wezterm_show_keys(path) == "OUT"
    assert calls == [(["/usr/bin/wezterm", "--config-file", str(path), "show-keys", "--lua"], 20)]
    calls.clear()
    monkeypatch.setattr(terminal_keys, "which", missing)
    assert wezterm_show_keys(path) is None
    assert calls == []


def test_wezterm_chord_mirrors_the_lua_guard() -> None:
    assert wezterm_chord("K", "CTRL") == wezterm_chord("k", "CTRL|SHIFT")
    assert wezterm_chord("k", "CTRL|SHIFT") == wezterm_chord("k", "SHIFT|CTRL")
    assert wezterm_chord("K", "CTRL") == wezterm_chord("K", "CTRL|SHIFT")
    assert wezterm_chord("k", "CMD") == wezterm_chord("k", "SUPER")
    assert wezterm_chord("LeftArrow", "OPT") == wezterm_chord("LeftArrow", "ALT")
    assert wezterm_chord("k", "NONE") == "k/"


def _show_keys(keys: str) -> str:
    return f"  keys = {{\n{keys}  }}\n  key_tables = {{\n"


def _patch_show_keys(monkeypatch: pytest.MonkeyPatch, output: str) -> None:
    def show_keys(path: Path) -> str:
        del path
        return output

    monkeypatch.setattr(terminal_keys, "wezterm_show_keys", show_keys)


def test_wezterm_readback_reports_a_kept_user_chord_on_linux(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_show_keys(
        monkeypatch,
        _show_keys("    { key = 'K', mods = 'CTRL', action = act.SendString 'USER' },\n"),
    )
    assert run_post_install(_wezterm(), _LINUX).lines == (
        _WEZTERM_SUMMARY,
        "wezterm: partial: you already bind CTRL+SHIFT+k; kept yours",
    )


def test_wezterm_readback_is_quiet_when_the_installer_rows_are_effective(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_show_keys(
        monkeypatch,
        _show_keys(
            "    { key = 'k', mods = 'SUPER', action = act.SendString '\\f' },\n"
            "    { key = 'LeftArrow', mods = 'ALT', action = act.SendString '\\u{1b}b' },\n"
            "    { key = 'RightArrow', mods = 'ALT', action = act.SendString '\\u{1b}f' },\n"
        ),
    )
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0")
    assert run_post_install(_wezterm(), macos).lines == (_WEZTERM_SUMMARY,)


def test_wezterm_readback_reports_a_kept_cmd_k_on_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_show_keys(
        monkeypatch,
        _show_keys(
            "    { key = 'k', mods = 'SUPER', action = act.ActivateTabRelative(1) },\n"
            "    { key = 'LeftArrow', mods = 'ALT', action = act.SendString '\\u{1b}b' },\n"
            "    { key = 'RightArrow', mods = 'ALT', action = act.SendString '\\u{1b}f' },\n"
        ),
    )
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0")
    assert (
        run_post_install(_wezterm(), macos).lines[-1]
        == "wezterm: partial: you already bind SUPER+k; kept yours"
    )


def test_wezterm_readback_ignores_key_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_show_keys(
        monkeypatch,
        "  keys = {\n    { key = 'k', mods = 'CTRL|SHIFT', action = act.SendString '\\f' },\n"
        "  }\n  key_tables = {\n    { key = 'K', mods = 'CTRL', action = act.CopyMode 'MoveUp' },\n"
        "  }\n",
    )
    assert run_post_install(_wezterm(), _LINUX).lines == (_WEZTERM_SUMMARY,)


def test_wezterm_readback_notes_a_failed_command(monkeypatch: pytest.MonkeyPatch) -> None:
    def failed(path: Path) -> str:
        del path
        raise CommandError(["wezterm"], 1, detail="config error")

    monkeypatch.setattr(terminal_keys, "wezterm_show_keys", failed)
    result = run_post_install(_wezterm(), _LINUX)
    assert result.lines == (_WEZTERM_SUMMARY, WEZTERM_UNVERIFIED)
    assert result.refused is None
    assert _wezterm_config().read_text() == _WEZTERM_LINUX
    assert (_state_dir() / "terminal-tuning-wezterm").exists()


def test_wezterm_readback_notes_unparseable_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_show_keys(monkeypatch, "wezterm 20240203\nno key table here\n")
    assert run_post_install(_wezterm(), _LINUX).lines == (_WEZTERM_SUMMARY, WEZTERM_UNVERIFIED)


def test_wezterm_readback_notes_a_missing_chord(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_show_keys(
        monkeypatch,
        _show_keys("    { key = 'k', mods = 'SUPER', action = act.SendString '\\f' },\n"),
    )
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0")
    assert run_post_install(_wezterm(), macos).lines == (_WEZTERM_SUMMARY, WEZTERM_UNVERIFIED)


def test_wezterm_readback_runs_nothing_without_wezterm() -> None:
    assert run_post_install(_wezterm(), _LINUX).lines == (_WEZTERM_SUMMARY,)


def test_wezterm_readback_skipped_on_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(path: Path) -> str:
        del path
        pytest.fail("readback ran on refusal")

    monkeypatch.setattr(terminal_keys, "wezterm_show_keys", unexpected)
    config = _wezterm_config()
    config.parent.mkdir(parents=True)
    config.write_text("return {}\n")
    assert run_post_install(_wezterm(), _LINUX).lines == (
        "WezTerm keys not changed: unsupported return shape",
    )


def test_wezterm_strip_deletes_created_seed_file_and_directories(tmp_path: Path) -> None:
    home = tmp_path / "home"
    environ = {
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
    }
    row = TERMINAL_KEYS["wezterm"]
    assert (
        apply_terminal_keys(row, "wezterm", "fedora", home, environ, skip_recorded=False)[1] is None
    )
    config = row.config_path("fedora", home, environ)
    assert config.read_text().startswith(WEZTERM_SKELETON.split("return config")[0])
    assert strip_terminal_keys(row, "wezterm", "fedora", home, environ) == ()
    assert not config.exists()
    assert not config.parent.exists()


def test_wezterm_strip_keeps_user_edited_created_file(tmp_path: Path) -> None:
    home = tmp_path / "home"
    environ = {
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
    }
    row = TERMINAL_KEYS["wezterm"]
    apply_terminal_keys(row, "wezterm", "fedora", home, environ, skip_recorded=False)
    config = row.config_path("fedora", home, environ)
    config.write_text(config.read_text() + "-- user edit\n")
    assert strip_terminal_keys(row, "wezterm", "fedora", home, environ) == ()
    assert config.read_text() == WEZTERM_SKELETON + "-- user edit\n"


def test_wezterm_golden_linux_created_file() -> None:
    result = run_post_install(_wezterm(), _LINUX)
    assert result.lines == (_WEZTERM_SUMMARY,)
    assert _wezterm_config().read_text() == _WEZTERM_LINUX
    marker = _state_dir() / WEZTERM_CREATED
    assert marker.exists()
    assert marker.with_name(f"{marker.name}-path").read_text() == f"{_wezterm_config()}\n"
    assert (_state_dir() / "terminal-tuning-wezterm").exists()
    body = _wezterm_config().read_text()
    assert "config.keys = config.keys or {}" in body
    assert "table.insert(config.keys, entry)" in body
    assert "config.keys = {" not in body


def test_wezterm_golden_macos_created_file() -> None:
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0")
    assert run_post_install(_wezterm(), macos).lines == (_WEZTERM_SUMMARY,)
    assert _wezterm_config().read_text() == _WEZTERM_MACOS


def test_no_row_writes_a_global_option_as_alt_switch(tmp_path: Path) -> None:
    forbidden = ("option_as_alt", "send_composed_key_when")
    for tool_id, row in TERMINAL_KEYS.items():
        for platform_os in ("macos", "fedora"):
            home = tmp_path / f"{tool_id}-{platform_os}"
            environ = {"HOME": str(home)}
            assert (
                apply_terminal_keys(row, tool_id, platform_os, home, environ, skip_recorded=False)[
                    1
                ]
                is None
            )
            text = row.config_path(platform_os, home, environ).read_text().lower()
            assert not any(switch in text for switch in forbidden), (tool_id, platform_os, text)


def test_only_alacritty_writes_linux_alt_rows(tmp_path: Path) -> None:
    forbidden = ("opt+left", "alt+left", "opt+right", "alt+right", "leftarrow", "rightarrow")
    for tool_id, row in TERMINAL_KEYS.items():
        home = tmp_path / f"{tool_id}-fedora"
        environ = {"HOME": str(home)}
        assert (
            apply_terminal_keys(row, tool_id, "fedora", home, environ, skip_recorded=False)[1]
            is None
        )
        text = row.config_path("fedora", home, environ).read_text().lower()
        if tool_id == "alacritty":
            assert 'key = "left"' in text
            assert 'mods = "alt"' in text
        else:
            assert not any(binding in text for binding in forbidden), (tool_id, text)


def test_wezterm_never_writes_a_global_alt_switch() -> None:
    assert "send_composed_key_when" not in _WEZTERM_LINUX + _WEZTERM_MACOS
    assert "option_as_alt" not in _WEZTERM_LINUX + _WEZTERM_MACOS


def test_wezterm_user_keys_are_kept_in_order() -> None:
    config = _wezterm_config()
    config.parent.mkdir(parents=True)
    user = (
        'local wezterm = require "wezterm"\nlocal config = wezterm.config_builder()\n'
        "config.keys = {\n"
        '  { key = "K", mods = "CTRL", action = wezterm.action.SendString "USER" },\n'
        "}\nreturn config\n"
    )
    config.write_text(user)
    assert run_post_install(_wezterm(), _LINUX).refused is None
    result = config.read_text()
    assert result.startswith(user.removesuffix("return config\n"))
    assert result.endswith("return config\n")
    assert result.index("config.keys = {") < result.index("wezterm-keys >>>")
    assert result.index("wezterm-keys <<<") < result.index("return config")


def test_wezterm_keys_marker_lookalike_comment_is_not_owned() -> None:
    config = _wezterm_config()
    config.parent.mkdir(parents=True)
    config.write_text("-- tools-installer terminal-shell wezterm-keys notes\n" + WEZTERM_SKELETON)
    assert run_post_install(_wezterm(), _LINUX).refused is None
    assert config.read_text().startswith("-- tools-installer terminal-shell wezterm-keys notes\n")
    assert config.read_text().count("wezterm-keys notes") == 1


def test_two_wezterm_applies_in_a_row_leave_one_region() -> None:
    """Sequential proxy of the SPEC R2 concurrency backstop; this is not a race test."""
    run_post_install(_wezterm(), _LINUX)
    run_post_install(_wezterm(), _LINUX)
    assert _wezterm_config().read_text().count("wezterm-keys >>>") == 1


def test_wezterm_unsupported_return_shape_refuses() -> None:
    config = _wezterm_config()
    config.parent.mkdir(parents=True)
    for invalid in ("return {}\n", "return config\nreturn config\n"):
        config.write_text(invalid)
        assert apply_terminal_keys(
            TERMINAL_KEYS["wezterm"],
            "wezterm",
            "fedora",
            Path.home(),
            os.environ,
            skip_recorded=False,
        ) == ((), "unsupported return shape")
        assert config.read_text() == invalid
        assert not (_state_dir() / "terminal-tuning-wezterm").exists()
        assert (
            terminal_keys_pending(
                TERMINAL_KEYS["wezterm"], "wezterm", "fedora", Path.home(), os.environ
            )
            == "unsupported return shape"
        )


def test_validate_wezterm_requires_the_region_before_return_config() -> None:
    validate_wezterm(_WEZTERM_LINUX)
    validate_wezterm(_WEZTERM_MACOS)
    with pytest.raises(TerminalShellError):
        validate_wezterm(
            _WEZTERM_LINUX.replace(
                "-- <<< tools-installer terminal-shell wezterm-keys <<<\nreturn config\n",
                "return config\n-- <<< tools-installer terminal-shell wezterm-keys <<<\n",
            )
        )
    with pytest.raises(TerminalShellError):
        validate_wezterm("return config\n")


def test_validate_wezterm_refuses_a_config_keys_assignment_after_the_region() -> None:
    for assignment in (
        "config.keys = {}",
        '  config.keys={ { key = "x", mods = "CTRL", action = wezterm.action.Nop } }',
    ):
        with pytest.raises(
            TerminalShellError, match="config.keys assignment after the WezTerm keys region"
        ):
            validate_wezterm(
                _WEZTERM_LINUX.replace("return config\n", assignment + "\nreturn config\n")
            )
    for allowed in (
        "config.keys[1] = nil",
        'table.insert(config.keys, { key = "x" })',
        "config.keys = config.keys or {}",
        "-- config.keys = {}",
        "if config.keys == nil then end",
    ):
        validate_wezterm(_WEZTERM_LINUX.replace("return config\n", allowed + "\nreturn config\n"))


def test_wezterm_fresh_install_after_a_user_config_keys_assignment_is_written() -> None:
    config = _wezterm_config()
    config.parent.mkdir(parents=True)
    user = (
        'local wezterm = require "wezterm"\nlocal config = wezterm.config_builder()\n'
        "config.keys = {}\nreturn config\n"
    )
    config.write_text(user)
    result = run_post_install(_wezterm(), _LINUX)
    assert result.refused is None
    assert config.read_text().startswith(user.removesuffix("return config\n"))
    assert config.read_text().endswith("return config\n")
    assert config.read_text().index("config.keys = {}") < config.read_text().index(
        "wezterm-keys >>>"
    )


def test_wezterm_in_place_rewrite_refuses_a_later_config_keys_assignment() -> None:
    config = _wezterm_config()
    config.parent.mkdir(parents=True)
    stale = _WEZTERM_LINUX.replace(
        'action = act.SendString "\\x0c"', 'action = act.SendString "old"'
    )
    stale = stale.replace("return config\n", "config.keys = {}\nreturn config\n")
    config.write_text(stale)
    assert apply_terminal_keys(
        TERMINAL_KEYS["wezterm"], "wezterm", "fedora", Path.home(), os.environ, skip_recorded=False
    ) == (
        (),
        "your config.keys assignment after the WezTerm keys region would replace its "
        "keys; nothing written",
    )
    assert config.read_text() == stale
    assert not (_state_dir() / "terminal-tuning-wezterm").exists()


def test_wezterm_moved_region_above_a_config_keys_assignment_refuses() -> None:
    config = _wezterm_config()
    config.parent.mkdir(parents=True)
    moved = (
        _WEZTERM_LINUX.replace(
            'action = act.SendString "\\x0c"', 'action = act.SendString "old"'
        ).replace("return config\n", "")
        + 'local wezterm = require "wezterm"\nlocal config = wezterm.config_builder()\n'
        "config.keys = {}\nreturn config\n"
    )
    config.write_text(moved)
    assert apply_terminal_keys(
        TERMINAL_KEYS["wezterm"], "wezterm", "fedora", Path.home(), os.environ, skip_recorded=False
    ) == (
        (),
        "your config.keys assignment after the WezTerm keys region would replace its "
        "keys; nothing written",
    )
    assert config.read_text() == moved


def test_wezterm_drift_never_applied_reads_pending() -> None:
    assert (
        terminal_keys_pending(
            TERMINAL_KEYS["wezterm"], "wezterm", "fedora", Path.home(), os.environ
        )
        == KEYS_PENDING
    )
    run_post_install(_wezterm(), _LINUX)
    assert (
        terminal_keys_pending(
            TERMINAL_KEYS["wezterm"], "wezterm", "fedora", Path.home(), os.environ
        )
        is None
    )


def test_wezterm_status_reports_a_config_keys_assignment_added_after_install() -> None:
    config = _wezterm_config()
    config.parent.mkdir(parents=True)
    config.write_text(
        'local wezterm = require "wezterm"\nlocal config = wezterm.config_builder()\n'
        "config.keys = {}\nreturn config\n"
    )
    run_post_install(_wezterm(), _LINUX)
    before = config.read_text()
    assert (
        terminal_keys_pending(
            TERMINAL_KEYS["wezterm"], "wezterm", "fedora", Path.home(), os.environ
        )
        is None
    )
    changed = before.replace("return config\n", "config.keys = {}\nreturn config\n")
    config.write_text(changed)
    assert terminal_keys_pending(
        TERMINAL_KEYS["wezterm"], "wezterm", "fedora", Path.home(), os.environ
    ) == (
        "your config.keys assignment after the WezTerm keys region would replace its "
        "keys; nothing written"
    )
    assert config.read_text() == changed
    config.write_text(before)
    assert (
        terminal_keys_pending(
            TERMINAL_KEYS["wezterm"], "wezterm", "fedora", Path.home(), os.environ
        )
        is None
    )


def test_only_wezterm_validates_on_status() -> None:
    assert [tool_id for tool_id, row in TERMINAL_KEYS.items() if row.validate_on_status] == [
        "wezterm"
    ]


def test_only_kitty_wezterm_and_ghostty_bind_the_created_path() -> None:
    assert {tool_id for tool_id, row in TERMINAL_KEYS.items() if row.bind_created_path} == {
        "kitty",
        "wezterm",
        "ghostty",
    }


def test_drift_edited_region_reads_pending_and_reconfigure_restores() -> None:
    config = _config()
    config.parent.mkdir(parents=True)
    config.write_text(_USER_FONT)
    run_post_install(_alacritty(), _LINUX)
    before = config.read_text()
    config.write_text(_edit_keys_region(before))

    assert _pending() == KEYS_PENDING
    assert _reapply() == ((_SUMMARY,), None)
    assert config.read_bytes() == before.encode()
    assert _reapply() == ((), None)
    assert config.read_bytes() == before.encode()
    assert _pending() is None


def test_drift_without_a_record_a_stale_region_reads_pending() -> None:
    _config().parent.mkdir(parents=True)
    _config().write_text(
        replace_owned_region(
            _USER_FONT,
            "alacritty-keys",
            _KEYS_REGION.split("\n", 2)[1].rsplit("\n# <<<", 1)[0],
        )
    )

    assert _pending() == KEYS_PENDING
    assert _reapply()[1] is None
    assert _config().read_text() == _USER_FONT + _KEYS_REGION


def test_all_conflicts_keep_empty_region_and_restore_freed_chord() -> None:
    run_post_install(_alacritty(), _LINUX)
    config = _config()
    user_bindings = (
        '[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "x"\n'
        '[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "y"\n'
        '[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\naction = "Quit"\n'
    )
    config.write_text(_KEYS_REGION + user_bindings)

    assert _pending() == KEYS_PENDING
    assert _reapply()[1] is None
    empty_region = (
        "# >>> tools-installer terminal-shell alacritty-keys >>>\n\n"
        "# <<< tools-installer terminal-shell alacritty-keys <<<\n"
    )
    assert config.read_text() == empty_region + user_bindings
    assert _pending() is None
    before = config.read_bytes()
    assert _reapply() == ((), None)
    assert config.read_bytes() == before

    config.write_text(
        config.read_text().replace('key = "Left"\nmods = "Alt"\nchars = "x"\n', "", 1)
    )
    assert _pending() == KEYS_PENDING
    assert _reapply()[1] is None
    assert 'key = "Left"\nmods = "Alt"\nchars = "\\u001bb"' in config.read_text()
    assert 'key = "Right"\nmods = "Alt"\nchars = "y"' in config.read_text()
    assert 'action = "Quit"' in config.read_text()


def test_all_conflicts_empty_region_uninstalls_without_touching_user_bindings() -> None:
    run_post_install(_alacritty(), _LINUX)
    config = _config()
    user_bindings = (
        '[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "x"\n'
        '[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "y"\n'
        '[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\naction = "Quit"\n'
    )
    config.write_text(_KEYS_REGION + user_bindings)
    assert _reapply()[1] is None

    assert (
        strip_terminal_keys(
            TERMINAL_KEYS["alacritty"], "alacritty", "fedora", Path.home(), os.environ
        )
        == ()
    )
    assert config.read_text() == user_bindings


def test_drift_user_binding_added_after_install_wins_on_reconfigure() -> None:
    run_post_install(_alacritty(), _LINUX)
    _config().write_text(_config().read_text() + _USER_ALT_LEFT)

    assert _pending() == KEYS_PENDING
    lines, refused = _reapply()
    assert refused is None
    assert "alacritty: partial: you already bind Alt+Left" in lines
    assert _config().read_text() == _KEYS_REGION_NO_LEFT + _USER_ALT_LEFT


def test_drift_recorded_file_that_now_refuses_stays_quiet() -> None:
    run_post_install(_alacritty(), _LINUX)
    config = _config()
    before = config.read_bytes()
    config.write_text('[general]\nimport = ["/x/theme.toml"]\n' + before.decode())
    before = config.read_bytes()

    assert _pending() is None
    assert _reapply() == ((), None)
    assert config.read_bytes() == before


def test_drift_recorded_unreadable_file_stays_quiet() -> None:
    run_post_install(_alacritty(), _LINUX)
    config = _config()
    config.write_bytes(config.read_bytes() + b"\xff\n")
    before = config.read_bytes()

    assert _pending() is None
    assert _reapply() == ((), None)
    assert config.read_bytes() == before


def test_drift_unrecorded_unreadable_file_names_the_reason() -> None:
    _config().parent.mkdir(parents=True)
    _config().write_bytes(b"\xff\n")

    assert _pending() == "the file is not valid UTF-8; refusing to rewrite it"


def test_two_applies_in_a_row_leave_one_region() -> None:
    """Sequential proxy for the held-out R1 concurrency backstop; this is not a race test."""
    for _ in range(2):
        apply_terminal_keys(
            TERMINAL_KEYS["alacritty"],
            "alacritty",
            "fedora",
            Path.home(),
            os.environ,
            skip_recorded=False,
        )
    assert _config().read_bytes() == _KEYS_REGION.encode()


def test_reconfigure_then_uninstall_in_sequence_leaves_no_region() -> None:
    """Sequential proxy for the held-out R2 concurrency backstop; this is not a race test."""
    config = _config()
    config.parent.mkdir(parents=True)
    config.write_text(_USER_FONT)
    run_post_install(_alacritty(), _LINUX)
    config.write_text(_edit_keys_region(config.read_text()))

    assert _reapply()[1] is None
    assert (
        strip_terminal_keys(
            TERMINAL_KEYS["alacritty"], "alacritty", "fedora", Path.home(), os.environ
        )
        == ()
    )
    assert config.read_text() == _USER_FONT


def _fixture_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    del platform_os, environ
    return home / "fixture" / "keys.toml"


def _fixture_plan(platform_os: str, text: str, path: Path) -> KeysPlan:
    del text, path
    chord, send = clear_binding(_FIXTURE_ROW, platform_os)
    return KeysPlan(f'[[keys]]\nchord = "{chord}"\nsend = {json.dumps(send)}')


_FIXTURE_ROW = KeysRow(
    ownership=OwnedRegion("fixture-keys"),
    config_path=_fixture_path,
    plan=_fixture_plan,
    validate=validate_toml,
    summary="Fixture keys.",
    created_record="terminal-fixture-created",
    same_directory=Vendor("fixture: the vendor opens the current directory"),
)


def test_placement_top_puts_a_new_region_before_every_user_line() -> None:
    region = replace_owned_region("a = 1\nb = 2\n", "fixture-keys", "x", placement=Placement.TOP)
    assert region == (
        "# >>> tools-installer terminal-shell fixture-keys >>>\nx\n"
        "# <<< tools-installer terminal-shell fixture-keys <<<\na = 1\nb = 2\n"
    )
    assert replace_owned_region("", "fixture-keys", "x", placement=Placement.TOP) == (
        "# >>> tools-installer terminal-shell fixture-keys >>>\nx\n"
        "# <<< tools-installer terminal-shell fixture-keys <<<\n"
    )
    existing = replace_owned_region("a = 1\n", "fixture-keys", "old")
    assert replace_owned_region(existing, "fixture-keys", "new", placement=Placement.TOP).endswith(
        "# >>> tools-installer terminal-shell fixture-keys >>>\nnew\n"
        "# <<< tools-installer terminal-shell fixture-keys <<<\n"
    )


def test_placement_before_return_inserts_above_the_single_return_config() -> None:
    comment = "--"
    expected = (
        "local config = {}\n-- >>> tools-installer terminal-shell fixture-keys >>>\nx\n"
        "-- <<< tools-installer terminal-shell fixture-keys <<<\nreturn config\n"
    )
    assert (
        replace_owned_region(
            "local config = {}\nreturn config\n",
            "fixture-keys",
            "x",
            comment=comment,
            placement=Placement.BEFORE_RETURN,
        )
        == expected
    )
    assert replace_owned_region(
        "", "fixture-keys", "x", comment=comment, placement=Placement.BEFORE_RETURN
    ) == WEZTERM_SKELETON.replace(
        "return config\n",
        "-- >>> tools-installer terminal-shell fixture-keys >>>\nx\n"
        "-- <<< tools-installer terminal-shell fixture-keys <<<\nreturn config\n",
    )
    for invalid in ("return {}\n", "return config\nreturn config\n"):
        try:
            replace_owned_region(
                invalid, "fixture-keys", "x", comment=comment, placement=Placement.BEFORE_RETURN
            )
        except TerminalShellError as exc:
            assert str(exc) == "unsupported return shape"
        else:
            raise AssertionError("unsupported return shape was accepted")
    duplicate = (
        replace_owned_region("return config\n", "fixture-keys", "old", comment=comment)
        + "return config\n"
    )
    assert "new" in replace_owned_region(
        duplicate,
        "fixture-keys",
        "new",
        comment=comment,
        placement=Placement.BEFORE_RETURN,
    )


def test_placement_end_is_phase_28s_append() -> None:
    for content in ("a = 1", "a = 1\n"):
        expected = "a = 1\n# >>> tools-installer terminal-shell fixture-keys >>>\nx\n"
        expected += "# <<< tools-installer terminal-shell fixture-keys <<<\n"
        assert replace_owned_region(content, "fixture-keys", "x") == expected
        assert replace_owned_region(content, "fixture-keys", "x") == replace_owned_region(
            content, "fixture-keys", "x", placement=Placement.END
        )


def test_writes_callable_varies_per_os_and_merges_notes_and_conflicts() -> None:
    def plan(platform_os: str, text: str, path: Path) -> KeysPlan:
        del platform_os, text, path
        return KeysPlan('[[keys]]\nchord = "x"', notes=("plan note",))

    def snippet(platform_os: str, text: str, path: Path) -> KeysPlan:
        del text, path
        return KeysPlan(
            f'[cwd]\nos = "{platform_os}"',
            ("fixture: partial: you already map y",),
            notes=("cwd note",),
        )

    row = dataclasses.replace(_FIXTURE_ROW, plan=plan, same_directory=Writes(snippet))
    lines, refusal = apply_terminal_keys(
        row, "fixture-callable", "macos", Path.home(), os.environ, skip_recorded=False
    )
    assert refusal is None
    assert lines == (
        "Fixture keys.",
        "plan note",
        "cwd note",
        "fixture: partial: you already map y",
    )
    text = _fixture_path("macos", Path.home(), os.environ).read_text()
    assert 'os = "macos"' in text
    assert text.index('chord = "x"') < text.index("[cwd]")
    tomllib.loads(text)

    def fedora_path(os_name: str, home: Path, env: Mapping[str, str]) -> Path:
        del os_name, env
        return home / "fixture" / "fedora.toml"

    row = dataclasses.replace(row, config_path=fedora_path)
    assert (
        apply_terminal_keys(row, "fixture-fedora", "fedora", Path.home(), {}, skip_recorded=False)[
            1
        ]
        is None
    )
    tomllib.loads((Path.home() / "fixture" / "fedora.toml").read_text())
    assert 'os = "fedora"' in (Path.home() / "fixture" / "fedora.toml").read_text()


def test_plan_receives_the_resolved_config_path() -> None:
    received: list[Path] = []

    def plan(platform_os: str, text: str, path: Path) -> KeysPlan:
        del platform_os, text
        received.append(path)
        return KeysPlan(None)

    row = dataclasses.replace(_FIXTURE_ROW, plan=plan)
    apply_terminal_keys(row, "fixture-path", "fedora", Path.home(), os.environ, skip_recorded=False)
    assert received == [row.config_path("fedora", Path.home(), os.environ)]


def test_readback_lines_follow_a_write_and_are_skipped_on_refusal() -> None:
    called: list[bool] = []

    def readback(platform_os: str, path: Path) -> tuple[str, ...]:
        return (f"readback {platform_os} {path.name}",)

    row = dataclasses.replace(_FIXTURE_ROW, readback=readback)
    assert apply_terminal_keys(
        row, "fixture-readback", "fedora", Path.home(), {}, skip_recorded=False
    ) == (("Fixture keys.", "readback fedora keys.toml"), None)

    def refusal_plan(platform_os: str, text: str, path: Path) -> KeysPlan:
        del platform_os, text, path
        return KeysPlan(None, refusal="nope")

    def unexpected_readback(platform_os: str, path: Path) -> tuple[str, ...]:
        del platform_os, path
        called.append(True)
        return ("unexpected",)

    refusing = dataclasses.replace(row, plan=refusal_plan, readback=unexpected_readback)
    assert apply_terminal_keys(
        refusing, "fixture-refusal", "fedora", Path.home(), {}, skip_recorded=False
    ) == ((), "nope")
    assert called == []


def test_row_validate_refuses_an_in_place_rewrite_of_a_moved_region() -> None:
    def validate(text: str) -> None:
        marker_line = "-- <<< tools-installer terminal-shell fixture-keys <<<"
        lines = text.splitlines()
        if not any(
            line.strip() == "return config" for line in lines[lines.index(marker_line) + 1 :]
        ):
            raise TerminalShellError("fixture region is not before return config")

    row = dataclasses.replace(
        _FIXTURE_ROW,
        ownership=OwnedRegion("fixture-keys", "--", Placement.BEFORE_RETURN),
        validate=validate,
    )
    path = _fixture_path("fedora", Path.home(), os.environ)
    path.parent.mkdir(parents=True, exist_ok=True)
    moved = (
        "local config = {}\nreturn config\n"
        "-- >>> tools-installer terminal-shell fixture-keys >>>\nold\n"
        "-- <<< tools-installer terminal-shell fixture-keys <<<\n"
    )
    path.write_text(moved)
    assert apply_terminal_keys(
        row, "fixture", "fedora", Path.home(), os.environ, skip_recorded=False
    ) == ((), "fixture region is not before return config")
    assert path.read_text() == moved
    assert not (_state_dir() / "terminal-tuning-fixture").exists()
    valid = moved.replace("return config\n-- >>>", "-- >>>").replace(
        "-- <<< tools-installer terminal-shell fixture-keys <<<\n",
        "-- <<< tools-installer terminal-shell fixture-keys <<<\nreturn config\n",
    )
    path.write_text(valid)
    assert (
        apply_terminal_keys(
            row, "fixture-control", "fedora", Path.home(), os.environ, skip_recorded=False
        )[1]
        is None
    )
    assert path.read_text().index("fixture-keys >>>") < path.read_text().index("return config")


def test_validate_on_status_reports_an_unchanged_region_the_validator_refuses() -> None:
    def validate(text: str) -> None:
        if any(line.strip() == "shadow" for line in text.splitlines()):
            raise TerminalShellError("fixture keys are shadowed")

    row = dataclasses.replace(_FIXTURE_ROW, validate=validate, validate_on_status=True)
    assert (
        apply_terminal_keys(row, "fixture", "fedora", Path.home(), os.environ, skip_recorded=False)[
            1
        ]
        is None
    )
    assert terminal_keys_pending(row, "fixture", "fedora", Path.home(), os.environ) is None
    path = _fixture_path("fedora", Path.home(), os.environ)
    path.write_text(path.read_text() + "shadow\n")
    assert terminal_keys_pending(row, "fixture", "fedora", Path.home(), os.environ) == (
        "fixture keys are shadowed"
    )
    assert (
        terminal_keys_pending(
            dataclasses.replace(row, validate_on_status=False),
            "fixture",
            "fedora",
            Path.home(),
            os.environ,
        )
        is None
    )
    text = path.read_text().replace("shadow\n", "")
    start = text.index("# >>> tools-installer terminal-shell fixture-keys >>>\n")
    end = text.index("# <<< tools-installer terminal-shell fixture-keys <<<\n")
    changed_region = text[start:end].replace('send = "', 'send = "stale', 1)
    path.write_text(text[:start] + changed_region + text[end:])
    assert terminal_keys_pending(row, "fixture", "fedora", Path.home(), os.environ) == KEYS_PENDING


def test_bound_created_file_is_deleted_only_at_its_recorded_path() -> None:
    def config_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
        del platform_os
        return Path(environ.get("FIXTURE_DIR", str(home / "fixture"))) / "keys.toml"

    row = dataclasses.replace(_FIXTURE_ROW, config_path=config_path, bind_created_path=True)
    created = Path.home() / "fixture" / "keys.toml"
    assert (
        apply_terminal_keys(row, "fixture", "fedora", Path.home(), {}, skip_recorded=False)[1]
        is None
    )
    marker = _state_dir() / "terminal-fixture-created"
    sidecar = _state_dir() / "terminal-fixture-created-path"
    assert marker.exists() and sidecar.read_text() == f"{created}\n"
    other = Path.home() / "other" / "keys.toml"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b"")
    assert strip_terminal_keys(
        row, "fixture", "fedora", Path.home(), {"FIXTURE_DIR": str(other.parent)}
    ) == (f"fixture: created config at {created} is not the file now resolved; left alone",)
    assert other.exists() and other.read_bytes() == b"" and created.exists()
    assert marker.exists() and sidecar.exists()
    sidecar.unlink()
    assert strip_terminal_keys(row, "fixture", "fedora", Path.home(), {}) == (
        "fixture: created config at an unrecorded path is not the file now resolved; left alone",
    )
    assert created.exists()
    sidecar.write_text(f"{created}\n")
    assert strip_terminal_keys(row, "fixture", "fedora", Path.home(), {}) == ()
    assert not created.exists() and not created.parent.exists()
    assert not marker.exists() and not sidecar.exists()


def test_row_fields_are_exactly_the_declared_set() -> None:
    assert [field.name for field in dataclasses.fields(KeysRow)] == [
        "ownership",
        "config_path",
        "plan",
        "validate",
        "summary",
        "created_record",
        "same_directory",
        "sibling_regions",
        "clear",
        "readback",
        "validate_on_status",
        "bind_created_path",
        "strip_files",
    ]
    assert all("option" not in field.name.lower() for field in dataclasses.fields(KeysRow))
    assert "option_as_alt" not in _KEYS_REGION


def test_same_directory_has_no_default() -> None:
    field = next(field for field in dataclasses.fields(KeysRow) if field.name == "same_directory")
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING


def test_a_row_without_same_directory_is_a_type_error() -> None:
    kwargs: dict[str, Any] = {
        field.name: getattr(_FIXTURE_ROW, field.name)
        for field in dataclasses.fields(KeysRow)
        if field.name != "same_directory"
    }
    try:
        KeysRow(**kwargs)
    except TypeError:
        return
    raise AssertionError("same_directory must be required")


def test_every_row_declares_same_directory() -> None:
    assert all(
        isinstance(row.same_directory, (Vendor, Writes, NotApplicable))
        for row in TERMINAL_KEYS.values()
    )
    alacritty = TERMINAL_KEYS["alacritty"].same_directory
    assert isinstance(alacritty, Vendor)
    assert "2026-11-19" in alacritty.note and "unverified" in alacritty.note


def test_same_directory_vendor_writes_nothing_and_writes_writes_it_once() -> None:
    snippet = '[window]\nworking_directory = "inherit"'
    fixture = _FIXTURE_ROW
    vendor_path = fixture.config_path("fedora", Path.home(), os.environ)
    lines, refused = apply_terminal_keys(
        fixture, "fixture-vendor", "fedora", Path.home(), os.environ, skip_recorded=False
    )
    assert refused is None and lines == (fixture.summary,)
    assert "working_directory" not in vendor_path.read_text()

    vendor_path.unlink()
    writer = dataclasses.replace(fixture, same_directory=Writes(snippet))
    _, refused = apply_terminal_keys(
        writer, "fixture-writes", "fedora", Path.home(), os.environ, skip_recorded=False
    )
    written = vendor_path.read_text()
    assert refused is None
    assert written.count(snippet) == 1
    assert written.index("# >>> tools-installer terminal-shell fixture-keys >>>") < written.index(
        snippet
    )
    assert written.index(snippet) < written.index(
        "# <<< tools-installer terminal-shell fixture-keys <<<"
    )
    tomllib.loads(written)

    vendor_path.unlink()
    no_tabs = dataclasses.replace(fixture, same_directory=NotApplicable("fixture: no tabs"))
    apply_terminal_keys(
        no_tabs, "fixture-none", "fedora", Path.home(), os.environ, skip_recorded=False
    )
    assert "working_directory" not in vendor_path.read_text()


def test_clear_chord_sends_ctrl_l_on_every_os_for_a_default_row() -> None:
    assert _FIXTURE_ROW.clear == CTRL_L == "\x0c"
    assert clear_binding(_FIXTURE_ROW, "macos") == ("cmd+k", "\x0c")
    for platform_os in ("fedora", "debian", "arch"):
        assert clear_binding(_FIXTURE_ROW, platform_os) == ("ctrl+shift+k", "\x0c")
    apply_terminal_keys(
        _FIXTURE_ROW, "fixture-clear", "macos", Path.home(), os.environ, skip_recorded=False
    )
    path = _fixture_path("macos", Path.home(), os.environ)
    assert tomllib.loads(path.read_text())["keys"] == [{"chord": "cmd+k", "send": "\x0c"}]
    apply_terminal_keys(
        _FIXTURE_ROW, "fixture-clear", "fedora", Path.home(), os.environ, skip_recorded=False
    )
    assert tomllib.loads(path.read_text())["keys"] == [{"chord": "ctrl+shift+k", "send": "\x0c"}]


def test_alacritty_region_differs_from_phase_28_only_in_the_clear_row() -> None:
    old_lines = _PHASE_28_KEYS_REGION.splitlines()
    new_lines = _KEYS_REGION.splitlines()
    differences = [(old, new) for old, new in zip(old_lines, new_lines, strict=True) if old != new]

    assert len(old_lines) == len(new_lines)
    assert differences == [('action = "ClearHistory"', 'chars = "\\u000c"')]
    assert old_lines[:8] == new_lines[:8]


def test_alacritty_clear_sends_ctrl_l() -> None:
    row = TERMINAL_KEYS["alacritty"]
    assert row.clear == CTRL_L
    assert clear_binding(row, "fedora") == ("ctrl+shift+k", "\x0c")
    assert 'chars = "\\u000c"' in _KEYS_REGION
    assert "ClearHistory" not in _KEYS_REGION
    assert tomllib.loads(_KEYS_REGION)["keyboard"]["bindings"][2] == {
        "key": "K",
        "mods": "Control|Shift",
        "chars": "\x0c",
    }


def test_recorded_phase_28_install_reconfigure_flips_clear_row() -> None:
    config = _config()
    config.parent.mkdir(parents=True)
    config.write_text(_USER_FONT + _PHASE_28_KEYS_REGION)
    (_state_dir() / "terminal-tuning-alacritty").parent.mkdir(parents=True, exist_ok=True)
    (_state_dir() / "terminal-tuning-alacritty").write_text("written\n")

    assert _pending() == KEYS_PENDING
    lines, refusal = _reapply()
    assert refusal is None
    assert _SUMMARY in lines
    assert config.read_bytes() == (_USER_FONT + _KEYS_REGION).encode()
    assert _reapply() == ((), None)
    assert _pending() is None
