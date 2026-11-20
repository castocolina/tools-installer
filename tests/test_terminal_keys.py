"""Terminal keys mechanism tests: golden bytes first, then the table."""

import dataclasses
import json
import os
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.post_install import apply_install_tuning, run_post_install
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
)
from installer.terminal_regions import (
    WEZTERM_SKELETON,
    KeysPlan,
    Placement,
    TerminalShellError,
    kitty_chord,
    kitty_config_path,
    replace_owned_region,
    scan_kitty,
    validate_kitty,
    validate_toml,
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
    assert set(TERMINAL_KEYS) == {"alacritty", "kitty"}
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
    assert missing_rows(load_tools(REGISTRY), {}) == {"alacritty", "kitty"}


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


def test_kitty_include_report_is_returned_by_install() -> None:
    config = _kitty_config()
    config.parent.mkdir(parents=True)
    config.write_text("geninclude generated.conf\\n")
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
    (tmp_path / "a.conf").write_text("include b.conf\n")
    (tmp_path / "b.conf").write_text("include a.conf\n")
    scan = scan_kitty("include a.conf\n", tmp_path / "kitty.conf")
    assert not scan.taken


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
