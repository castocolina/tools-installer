"""Terminal keys mechanism tests: golden bytes first, then the table."""

import dataclasses
import json
import os
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

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
from installer.terminal_regions import KeysPlan, replace_owned_region, validate_toml
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


def _fixture_plan(platform_os: str, text: str) -> KeysPlan:
    del text
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


def test_alacritty_keeps_clear_history_until_phase_29() -> None:
    row = TERMINAL_KEYS["alacritty"]
    assert row.clear == "ClearHistory"
    assert clear_binding(row, "fedora") == ("ctrl+shift+k", "ClearHistory")
    assert 'action = "ClearHistory"' in _KEYS_REGION
