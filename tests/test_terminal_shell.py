"""Safety-first terminal emulator shell synchronization tests."""

import contextlib
import os
import re
import shlex
import shutil
import subprocess
import threading
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import pytest

from installer import terminal_shell
from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.receipts import read_ledger
from installer.run import CommandError
from installer.terminal_shell import (
    TerminalShellError,
    sync_message,
    sync_terminal_shells,
    terminal_sync_warning,
)

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


class _SyncArgs(TypedDict):
    home: Path
    environ: dict[str, str]
    platform: Platform
    lookup: Callable[[str], str | None]


def _platform(os_name: str = "fedora") -> Platform:
    return Platform(os=os_name, arch="amd64", immutable=os_name == "fedora", has_brew=False)


def _lookup(**executables: str) -> Callable[[str], str | None]:
    return lambda name: executables.get(name)


def _kconfig_decode(value: str) -> str:
    """Undo KConfig's own value-decoding layer for the escapes this module
    writes, so a test can assert what Konsole would actually read back on
    disk -- not merely the bytes this module happened to write. Mirrors the
    same mapping as installer.terminal_shell._KCONFIG_ESCAPES, decoded."""
    decoded: list[str] = []
    mapping = {"\\": "\\", "n": "\n", "t": "\t", "r": "\r"}
    index = 0
    while index < len(value):
        character = value[index]
        if character == "\\" and index + 1 < len(value) and value[index + 1] in mapping:
            decoded.append(mapping[value[index + 1]])
            index += 2
        else:
            decoded.append(character)
            index += 1
    return "".join(decoded)


@pytest.mark.parametrize("os_name", ("fedora", "debian", "arch"))
def test_sync_writes_kitty_login_shell_for_each_supported_linux_distro(
    tmp_path: Path, os_name: str
) -> None:
    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(os_name),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty", wezterm="/usr/bin/wezterm"),
    )

    kitty_conf = tmp_path / ".config" / "kitty" / "kitty.conf"
    assert result.configured == ("zshenv", "kitty", "wezterm")
    assert "shell /usr/bin/zsh -l" in kitty_conf.read_text()


def test_sync_does_not_touch_macos_terminal_configuration(tmp_path: Path) -> None:
    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform("macos"),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    assert result.configured == ()
    assert not (tmp_path / ".config" / "kitty" / "kitty.conf").exists()


def test_sync_is_byte_stable_and_preserves_a_symlinked_kitty_configuration(tmp_path: Path) -> None:
    target = tmp_path / "dotfiles" / "kitty.conf"
    target.parent.mkdir()
    target.write_text("font_size 14\n")
    config = tmp_path / ".config" / "kitty" / "kitty.conf"
    config.parent.mkdir(parents=True)
    config.symlink_to(target)
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    }

    sync_terminal_shells(**args)
    first = target.read_bytes()
    sync_terminal_shells(**args)

    assert target.read_bytes() == first
    assert config.is_symlink()


@pytest.mark.parametrize(
    "original",
    (
        "# >>> tools-installer terminal-shell kitty >>>\nshell /bin/zsh -l\n",
        "# >>> tools-installer terminal-shell kitty >>>\n"
        "# >>> tools-installer terminal-shell kitty >>>\n"
        "# <<< tools-installer terminal-shell kitty <<<\n",
    ),
)
def test_malformed_kitty_ownership_regions_fail_without_changing_bytes(
    tmp_path: Path, original: str
) -> None:
    config = tmp_path / ".config" / "kitty" / "kitty.conf"
    config.parent.mkdir(parents=True)
    config.write_text(original)

    with pytest.raises(TerminalShellError, match="ownership"):
        sync_terminal_shells(
            home=tmp_path,
            environ={},
            platform=_platform(),
            lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
        )

    assert config.read_text() == original


def test_control_character_in_discovered_zsh_path_fails_before_kitty_changes(
    tmp_path: Path,
) -> None:
    config = tmp_path / ".config" / "kitty" / "kitty.conf"
    config.parent.mkdir(parents=True)
    original = "font_size 14\n"
    config.write_text(original)

    with pytest.raises(TerminalShellError, match="control"):
        sync_terminal_shells(
            home=tmp_path,
            environ={},
            platform=_platform(),
            lookup=_lookup(zsh="/usr/bin/zsh\nunsafe", kitty="/usr/bin/kitty"),
        )

    assert config.read_text() == original


def test_kitty_shell_uses_shlex_representation_for_special_but_safe_path(tmp_path: Path) -> None:
    zsh_path = '/opt/Zsh Tools/z"sh\\bin'
    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh=zsh_path, kitty="/usr/bin/kitty"),
    )

    content = (tmp_path / ".config" / "kitty" / "kitty.conf").read_text()
    assert "shell '/opt/Zsh Tools/z\"sh\\bin' -l" in content


def test_omz_repair_completes_before_kitty_region_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import terminal_shell

    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("source $ZSH/oh-my-zsh.sh\nplugins=(git)\n")
    (tmp_path / ".oh-my-zsh").mkdir()
    writes: list[Path] = []
    real_atomic_write = terminal_shell.atomic_write_text
    real_ensure_template = terminal_shell.ensure_zshrc_template

    def record_write(path: Path, text: str) -> None:
        writes.append(path)
        real_atomic_write(path, text)

    def record_template(path: Path, root: Path | None = None) -> bool:
        writes.append(path)
        return real_ensure_template(path, root)

    monkeypatch.setattr(terminal_shell, "atomic_write_text", record_write)
    monkeypatch.setattr(terminal_shell, "ensure_zshrc_template", record_template)

    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    kitty_conf = tmp_path / ".config" / "kitty" / "kitty.conf"
    assert zshrc.read_text().index("plugins=(git)") < zshrc.read_text().index("oh-my-zsh.sh")
    assert writes.index(zshrc) < writes.index(kitty_conf)


def test_omz_repair_uses_the_real_root_when_zsh_names_a_relocated_install(
    tmp_path: Path,
) -> None:
    """CR-01: `omz_present` treats a configured $ZSH as present too, so the
    repair must write that real root -- not assume the conventional
    ~/.oh-my-zsh -- or it overwrites a working $ZSH with a path that does not
    exist."""
    custom_root = tmp_path / "dotfiles" / "custom-omz"
    custom_root.mkdir(parents=True)

    sync_terminal_shells(
        home=tmp_path,
        environ={"ZSH": str(custom_root)},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    text = (tmp_path / ".zshrc").read_text()
    assert f"export ZSH={custom_root}" in text
    assert "$HOME/.oh-my-zsh" not in text


def test_omz_repair_falls_back_to_the_default_root_when_no_zsh_env_is_set(
    tmp_path: Path,
) -> None:
    """The conventional ~/.oh-my-zsh remains the default when omz_present is
    satisfied through that location rather than a configured $ZSH."""
    (tmp_path / ".oh-my-zsh").mkdir()

    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    text = (tmp_path / ".zshrc").read_text()
    assert 'export ZSH="$HOME/.oh-my-zsh"' in text


def test_omz_repair_targets_zdotdir_zshrc_when_zdotdir_is_set(tmp_path: Path) -> None:
    """G-01: the repair target must resolve through locations.zshrc_path --
    the same $ZDOTDIR-aware resolver the Policies route already uses
    (setup.py::_ZSHRC) -- rather than a hardcoded home / ".zshrc". Otherwise
    the D-04 repair silently no-ops on a ZDOTDIR host and creates a spurious
    $HOME/.zshrc that zsh never sources."""
    zdotdir = tmp_path / "zdotdir"
    zdotdir.mkdir()
    (tmp_path / ".oh-my-zsh").mkdir()

    sync_terminal_shells(
        home=tmp_path,
        environ={"ZDOTDIR": str(zdotdir)},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    assert not (tmp_path / ".zshrc").exists()
    text = (zdotdir / ".zshrc").read_text()
    # The real root (home / ".oh-my-zsh") differs from the .zshrc's own parent
    # dir (zdotdir), so ensure_zshrc_template quotes the real, resolved path
    # rather than the portable $HOME/.oh-my-zsh symbol -- proof the repair
    # actually reached and inspected the ZDOTDIR file, not a same-shaped stand-in.
    assert f"export ZSH={shlex.quote(str(tmp_path / '.oh-my-zsh'))}" in text
    assert "plugins=(git)" in text


def test_wezterm_generates_an_owned_login_program_before_return_config(tmp_path: Path) -> None:
    config_home = tmp_path / "xdg" / "config"
    result = sync_terminal_shells(
        home=tmp_path,
        environ={"XDG_CONFIG_HOME": str(config_home)},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty", wezterm="/usr/bin/wezterm"),
    )

    wezterm = config_home / "wezterm" / "wezterm.lua"
    content = wezterm.read_text()
    assert result.configured == ("zshenv", "kitty", "wezterm")
    assert 'config.default_prog = { "/usr/bin/zsh", "-l" }' in content
    assert content.index("tools-installer terminal-shell wezterm") < content.index("return config")


def test_wezterm_uses_the_existing_home_fallback_before_creating_a_new_file(tmp_path: Path) -> None:
    wezterm = tmp_path / ".wezterm.lua"
    wezterm.write_text('local wezterm = require "wezterm"\nlocal config = {}\nreturn config\n')

    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty", wezterm="/usr/bin/wezterm"),
    )

    assert 'config.default_prog = { "/usr/bin/zsh", "-l" }' in wezterm.read_text()
    assert not (tmp_path / ".config" / "wezterm" / "wezterm.lua").exists()


def test_wezterm_escapes_special_paths_and_leaves_unsupported_returns_unchanged(
    tmp_path: Path,
) -> None:
    wezterm = tmp_path / ".config" / "wezterm" / "wezterm.lua"
    wezterm.parent.mkdir(parents=True)
    original = "return { default_prog = {} }\n"
    wezterm.write_text(original)
    zsh_path = '/opt/Zsh Tools/z"sh\\bin'

    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh=zsh_path, kitty="/usr/bin/kitty", wezterm="/usr/bin/wezterm"),
    )

    assert wezterm.read_text() == original
    assert result.warnings == ("wezterm: unsupported return shape",)


def test_konsole_creates_an_owned_profile_and_records_the_prior_default(tmp_path: Path) -> None:
    data_home = tmp_path / "xdg" / "data"
    config_home = tmp_path / "xdg" / "config"
    konsolerc = config_home / "konsolerc"
    konsolerc.parent.mkdir(parents=True)
    konsolerc.write_text("[Desktop Entry]\nDefaultProfile=Old.profile\n")

    result = sync_terminal_shells(
        home=tmp_path,
        environ={"XDG_DATA_HOME": str(data_home), "XDG_CONFIG_HOME": str(config_home)},
        platform=_platform(),
        lookup=_lookup(
            zsh="/usr/bin/zsh",
            kitty="/usr/bin/kitty",
            konsole="/usr/bin/konsole",
            wezterm="/usr/bin/wezterm",
        ),
    )

    profile = data_home / "konsole" / "tools-installer-zsh.profile"
    state = data_home / "tools-installer" / "terminal-shell-konsole-default"
    assert result.configured == ("zshenv", "kitty", "wezterm", "konsole")
    profile_text = profile.read_text()
    assert "Command=/usr/bin/zsh -l" in profile_text
    # CR-05: every real Konsole profile carries a Name= (confirmed against
    # this host's own /usr/share/konsole/Vapor.profile); a profile missing
    # one is expected to be rejected outright by Konsole's profile manager.
    assert "Name=tools-installer zsh" in profile_text
    assert "Parent=FALLBACK/" in profile_text
    assert "DefaultProfile=tools-installer-zsh.profile" in konsolerc.read_text()
    assert state.read_text() == "Old.profile\n"


def test_konsole_serializer_kconfig_escapes_special_argv_and_rejects_unsafe_paths(
    tmp_path: Path,
) -> None:
    """WR-01: shlex's own shell-argv quoting is a separate escaping layer
    from KConfig's own value-decoding, applied when Konsole reads the file
    back. The shipped test this replaces asserted the raw, un-escaped
    shlex.join(...) bytes as correct -- certifying the bug rather than
    catching it. This decodes the written value through KConfig's own
    escaping rules and confirms it round-trips to the exact argv this
    module intended, for a path containing a space, a double quote, and a
    backslash."""
    data_home = tmp_path / "xdg" / "data"
    config_home = tmp_path / "xdg" / "config"
    zsh_path = '/opt/Zsh Tools/z"sh\\bin'
    sync_terminal_shells(
        home=tmp_path,
        environ={"XDG_DATA_HOME": str(data_home), "XDG_CONFIG_HOME": str(config_home)},
        platform=_platform(),
        lookup=_lookup(zsh=zsh_path, kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"),
    )
    profile = data_home / "konsole" / "tools-installer-zsh.profile"
    konsolerc = config_home / "konsolerc"
    original_profile = profile.read_bytes()
    original_konsolerc = konsolerc.read_bytes()

    command_line = next(
        line for line in profile.read_text().splitlines() if line.startswith("Command=")
    )
    written_value = command_line.removeprefix("Command=")
    assert _kconfig_decode(written_value) == shlex.join((zsh_path, "-l"))

    with pytest.raises(TerminalShellError, match="control"):
        sync_terminal_shells(
            home=tmp_path,
            environ={"XDG_DATA_HOME": str(data_home), "XDG_CONFIG_HOME": str(config_home)},
            platform=_platform(),
            lookup=_lookup(
                zsh="/usr/bin/zsh\x00unsafe", kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"
            ),
        )
    assert profile.read_bytes() == original_profile
    assert konsolerc.read_bytes() == original_konsolerc


def test_konsole_command_survives_a_backslash_t_sequence_without_becoming_a_tab(
    tmp_path: Path,
) -> None:
    """WR-01's own reproduction: shlex.quote('/opt/a\\test/zsh') writes the
    literal text '/opt/a\\test/zsh', and KConfig's decoder treats \\t as its
    own escape for a tab character on read -- so an un-escaped write
    silently corrupts the launch command into '/opt/a<TAB>est/zsh'."""
    data_home = tmp_path / "xdg" / "data"
    config_home = tmp_path / "xdg" / "config"
    zsh_path = "/opt/a\\test/zsh"

    sync_terminal_shells(
        home=tmp_path,
        environ={"XDG_DATA_HOME": str(data_home), "XDG_CONFIG_HOME": str(config_home)},
        platform=_platform(),
        lookup=_lookup(zsh=zsh_path, kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"),
    )

    profile = data_home / "konsole" / "tools-installer-zsh.profile"
    command_line = next(
        line for line in profile.read_text().splitlines() if line.startswith("Command=")
    )
    decoded = _kconfig_decode(command_line.removeprefix("Command="))
    assert decoded == shlex.join((zsh_path, "-l"))
    assert "\t" not in decoded


def test_zsh_removal_reverts_only_complete_owned_terminal_configuration(tmp_path: Path) -> None:
    data_home = tmp_path / "xdg" / "data"
    config_home = tmp_path / "xdg" / "config"
    konsolerc = config_home / "konsolerc"
    konsolerc.parent.mkdir(parents=True)
    original_konsolerc = "[Desktop Entry]\nDefaultProfile=Old.profile\n"
    konsolerc.write_text(original_konsolerc)
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {"XDG_DATA_HOME": str(data_home), "XDG_CONFIG_HOME": str(config_home)},
        "platform": _platform(),
        "lookup": _lookup(
            zsh="/usr/bin/zsh",
            kitty="/usr/bin/kitty",
            konsole="/usr/bin/konsole",
            wezterm="/usr/bin/wezterm",
        ),
    }
    sync_terminal_shells(**args)

    result = sync_terminal_shells(
        home=tmp_path,
        environ=args["environ"],
        platform=_platform(),
        lookup=_lookup(konsole="/usr/bin/konsole"),
    )

    assert result.reverted == ("zshenv", "kitty", "wezterm", "konsole")
    assert (
        "tools-installer terminal-shell kitty"
        not in (config_home / "kitty" / "kitty.conf").read_text()
    )
    assert (
        "tools-installer terminal-shell wezterm"
        not in (config_home / "wezterm" / "wezterm.lua").read_text()
    )
    assert not (data_home / "konsole" / "tools-installer-zsh.profile").exists()
    assert konsolerc.read_text() == original_konsolerc


def test_revert_restores_the_prior_konsole_default_after_a_real_konsole_rewrite(
    tmp_path: Path,
) -> None:
    """CR-06: konsolerc is a KConfig file Konsole itself rewrites on
    ordinary use, and KConfig's own backend does not preserve comment
    lines -- so the marker comments this module relies on elsewhere can
    silently vanish while DefaultProfile=tools-installer-zsh.profile
    survives as a plain, now-unmarked entry. This simulates exactly that:
    strip the marker lines from konsolerc the way a real Konsole rewrite
    would, leaving only the plain DefaultProfile= entry pointing at our
    profile, and confirm the prior default is restored rather than
    permanently lost."""
    data_home = tmp_path / "xdg" / "data"
    config_home = tmp_path / "xdg" / "config"
    konsolerc = config_home / "konsolerc"
    konsolerc.parent.mkdir(parents=True)
    konsolerc.write_text("[Desktop Entry]\nDefaultProfile=Old.profile\n")
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {"XDG_DATA_HOME": str(data_home), "XDG_CONFIG_HOME": str(config_home)},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"),
    }
    sync_terminal_shells(**args)

    # Simulate a real Konsole rewrite: the marker comments are gone, but the
    # value they wrapped is still there as a plain, unmarked entry.
    konsolerc.write_text("[Desktop Entry]\nDefaultProfile=tools-installer-zsh.profile\n")

    result = sync_terminal_shells(
        home=tmp_path,
        environ=args["environ"],
        platform=_platform(),
        lookup=_lookup(kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"),
    )

    assert "konsole" in result.reverted
    assert konsolerc.read_text() == "[Desktop Entry]\nDefaultProfile=Old.profile\n"
    assert not (data_home / "konsole" / "tools-installer-zsh.profile").exists()
    assert not (data_home / "tools-installer" / "terminal-shell-konsole-default").exists()


def test_revert_strips_a_stale_owned_konsolerc_region_even_when_no_longer_effective(
    tmp_path: Path,
) -> None:
    """WR-02: the profile file's own deletion and the konsolerc region-strip
    are both unconditionally ours whenever their own markers are present --
    never gated on whether our profile is still the *effective* default.
    Before this fix, the konsolerc cleanup was guarded by an effective-
    default check that could never become true again once a later
    [Desktop Entry] group (simulated here) took over, permanently stranding
    the installer-owned marker region."""
    data_home = tmp_path / "xdg" / "data"
    config_home = tmp_path / "xdg" / "config"
    konsolerc = config_home / "konsolerc"
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {"XDG_DATA_HOME": str(data_home), "XDG_CONFIG_HOME": str(config_home)},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"),
    }
    sync_terminal_shells(**args)

    # A later [Desktop Entry] group takes over as the effective default --
    # our owned region (still present, still marked) is no longer effective.
    konsolerc.write_text(
        konsolerc.read_text() + "[Desktop Entry]\nDefaultProfile=SomeoneElse.profile\n"
    )

    result = sync_terminal_shells(
        home=tmp_path,
        environ=args["environ"],
        platform=_platform(),
        lookup=_lookup(kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"),
    )

    assert "konsole" in result.reverted
    assert "tools-installer terminal-shell konsole" not in konsolerc.read_text()
    assert "DefaultProfile=SomeoneElse.profile" in konsolerc.read_text()
    assert not (data_home / "konsole" / "tools-installer-zsh.profile").exists()


def test_absent_konsole_does_not_create_profile_or_kconfig(tmp_path: Path) -> None:
    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    assert not (tmp_path / ".local" / "share" / "konsole" / "tools-installer-zsh.profile").exists()
    assert not (tmp_path / ".config" / "konsolerc").exists()


def test_absent_wezterm_does_not_create_a_config_file_or_its_parent_directory(
    tmp_path: Path,
) -> None:
    """CR-03: kitty and Konsole both gate on a live presence check; WezTerm had
    none at all, so a synchronizer run with no wezterm in the lookup table
    still created ~/.config/wezterm/wezterm.lua and its parent directory."""
    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    assert "wezterm" not in result.configured
    assert "wezterm unavailable" in result.skipped
    assert not (tmp_path / ".config" / "wezterm").exists()
    assert not (tmp_path / ".wezterm.lua").exists()


def test_non_utf8_kitty_config_is_refused_as_an_oserror_without_changing_bytes(
    tmp_path: Path,
) -> None:
    """CR-02: a Latin-1 byte must not escape as a bare UnicodeDecodeError.

    UnicodeDecodeError is a ValueError, so it would slip past every caller's
    `except OSError` -- including the six terminal-sync lifecycle call sites.
    """
    config = tmp_path / ".config" / "kitty" / "kitty.conf"
    config.parent.mkdir(parents=True)
    original = "# caf\xe9 comment\nfont_size 14\n".encode("latin-1")
    config.write_bytes(original)

    with pytest.raises(TerminalShellError, match="UTF-8") as caught:
        sync_terminal_shells(
            home=tmp_path,
            environ={},
            platform=_platform(),
            lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
        )

    assert isinstance(caught.value, OSError)
    assert config.read_bytes() == original


def test_dry_run_never_blocks_on_a_fifo_config(tmp_path: Path) -> None:
    """A FIFO at kitty.conf must not stall the refresh pass's dry run."""
    config = tmp_path / ".config" / "kitty" / "kitty.conf"
    config.parent.mkdir(parents=True)
    os.mkfifo(config)
    box: list[object] = []

    def run() -> None:
        try:
            box.append(
                sync_terminal_shells(
                    home=tmp_path,
                    environ={},
                    platform=_platform(),
                    lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
                    write=False,
                )
            )
        except Exception as exc:
            box.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert len(box) == 1
        assert isinstance(box[0], TerminalShellError)
        assert "is not a regular file of at most 1 MiB" in str(box[0])
        assert config.is_fifo()
    finally:
        with contextlib.suppress(OSError):
            os.close(os.open(config, os.O_WRONLY | os.O_NONBLOCK))
        thread.join(timeout=5)


def test_terminal_sync_warning_is_the_one_total_failure_contract() -> None:
    """WR-03/CR-02: one catch set and one message, and it never raises.

    A non-OSError -- CR-02's UnicodeDecodeError is a ValueError -- used to
    escape the narrow `except OSError` each of the five call sites wrote for
    itself, taking the already-completed primary operation down with it.
    """

    def raises_non_oserror() -> str | None:
        raise ValueError("kitty.conf is not valid UTF-8")

    def raises_oserror() -> str | None:
        raise OSError("permission denied")

    assert terminal_sync_warning(None) is None
    assert terminal_sync_warning(lambda: None) is None
    assert terminal_sync_warning(lambda: "wezterm: unsupported return shape") == (
        "wezterm: unsupported return shape"
    )
    assert terminal_sync_warning(raises_non_oserror) == (
        "Terminal shell synchronization failed: kitty.conf is not valid UTF-8"
    )
    assert terminal_sync_warning(raises_oserror) == (
        "Terminal shell synchronization failed: permission denied"
    )


# D-16 / L-19-05: the refresh pass asks whether a terminal would change
# without changing it, so a dry run must leave the whole HOME untouched.
_ALL_TERMINALS = {"zsh": "/usr/bin/zsh", "kitty": "/usr/bin/kitty", "wezterm": "/usr/bin/wezterm"}


def _fingerprint(home: Path) -> dict[str, tuple[bytes, int]]:
    """Every path under HOME with its bytes (files) and mtime, files and dirs alike."""
    return {
        str(path.relative_to(home)): (
            path.read_bytes() if path.is_file() else b"",
            path.stat().st_mtime_ns,
        )
        for path in home.rglob("*")
    }


def test_dry_run_reports_kitty_drift_without_writing(tmp_path: Path) -> None:
    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
        write=False,
    )

    assert result.drifted == ("zshenv", "kitty")
    assert not (tmp_path / ".config").exists()
    assert list(tmp_path.iterdir()) == []


def test_dry_run_reports_no_drift_when_in_sync(tmp_path: Path) -> None:
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(**_ALL_TERMINALS),
    }
    sync_terminal_shells(**args, write=True)

    assert sync_terminal_shells(**args, write=False).drifted == ()


def test_dry_run_reports_wezterm_drift(tmp_path: Path) -> None:
    wezterm = tmp_path / ".config" / "wezterm" / "wezterm.lua"
    wezterm.parent.mkdir(parents=True)
    wezterm.write_text('local wezterm = require "wezterm"\nlocal config = {}\nreturn config\n')
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", wezterm="/usr/bin/wezterm"),
    }

    assert "wezterm" in sync_terminal_shells(**args, write=False).drifted

    wezterm.write_text("return { default_prog = {} }\n")
    unsupported = sync_terminal_shells(**args, write=False)
    assert "wezterm" not in unsupported.drifted
    assert unsupported.warnings == ("wezterm: unsupported return shape",)


def test_dry_run_leaves_home_byte_identical(tmp_path: Path) -> None:
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(**_ALL_TERMINALS, konsole="/usr/bin/konsole"),
    }
    sync_terminal_shells(**args, write=True)
    # kitty stays in sync; wezterm and konsolerc go stale; .zshrc needs the omz repair.
    wezterm = tmp_path / ".config" / "wezterm" / "wezterm.lua"
    wezterm.write_text('local wezterm = require "wezterm"\nlocal config = {}\nreturn config\n')
    (tmp_path / ".config" / "konsolerc").write_text("[Desktop Entry]\nDefaultProfile=Old.profile\n")
    (tmp_path / ".oh-my-zsh").mkdir()
    (tmp_path / ".zshrc").write_text("source $ZSH/oh-my-zsh.sh\nplugins=(git)\n")
    before = _fingerprint(tmp_path)

    result = sync_terminal_shells(**args, write=False)

    assert _fingerprint(tmp_path) == before
    assert result.drifted == ("wezterm", "konsole")


def test_dry_run_zsh_absent_reverts_nothing(tmp_path: Path) -> None:
    sync_terminal_shells(
        home=tmp_path, environ={}, platform=_platform(), lookup=_lookup(**_ALL_TERMINALS)
    )
    before = _fingerprint(tmp_path)

    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(kitty="/usr/bin/kitty", wezterm="/usr/bin/wezterm"),
        write=False,
    )

    assert _fingerprint(tmp_path) == before
    assert result.drifted == ()
    assert result.reverted == ()


def test_write_true_default_unchanged(tmp_path: Path) -> None:
    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    assert result.configured == ("zshenv", "kitty")
    assert "shell /usr/bin/zsh -l" in (tmp_path / ".config" / "kitty" / "kitty.conf").read_text()


def test_dry_run_reports_konsole_drift(tmp_path: Path) -> None:
    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", konsole="/usr/bin/konsole"),
        write=False,
    )

    data_home = tmp_path / ".local" / "share"
    assert "konsole" in result.drifted
    assert not (data_home / "konsole" / "tools-installer-zsh.profile").exists()
    assert not (tmp_path / ".config" / "konsolerc").exists()
    assert not (data_home / "tools-installer" / "terminal-shell-konsole-default").exists()
    assert list(tmp_path.iterdir()) == []


def test_dry_run_konsole_in_sync_is_quiet(tmp_path: Path) -> None:
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", konsole="/usr/bin/konsole"),
    }
    sync_terminal_shells(**args, write=True)
    before = _fingerprint(tmp_path)

    result = sync_terminal_shells(**args, write=False)

    assert "konsole" not in result.drifted
    assert _fingerprint(tmp_path) == before


def test_dry_run_konsole_user_owned_profile_warns(tmp_path: Path) -> None:
    profile = tmp_path / ".local" / "share" / "konsole" / "tools-installer-zsh.profile"
    profile.parent.mkdir(parents=True)
    profile.write_text("[General]\nName=mine\n")
    before = _fingerprint(tmp_path)

    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", konsole="/usr/bin/konsole"),
        write=False,
    )

    assert result.warnings == ("konsole: installer profile path is already user-owned",)
    assert "konsole" not in result.drifted
    assert _fingerprint(tmp_path) == before


# Phase 23 / CONF-05: every zsh exports SHELL as the real zsh through a managed ~/.zshenv block.
_ZSHENV_BEGIN = "# >>> tools-installer shell >>>"
_ZSHENV_END = "# <<< tools-installer shell <<<"


def test_zsh_in_a_scratch_home_prints_the_zsh_path(tmp_path: Path) -> None:
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh is not on PATH; the real-shell probe needs it")

    result = sync_terminal_shells(
        home=tmp_path, environ={}, platform=_platform(), lookup=_lookup(zsh=zsh)
    )
    probe = subprocess.run(
        [zsh, "-c", "echo $SHELL"],
        env={"HOME": str(tmp_path), "SHELL": "/bin/bash", "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=True,
    )

    assert probe.stdout.strip() == zsh
    assert result.zsh == zsh
    assert ("zshenv", tmp_path / ".zshenv") in result.paths


def test_a_user_shell_line_stays_and_the_block_comes_after(tmp_path: Path) -> None:
    zshenv = tmp_path / ".zshenv"
    zshenv.write_text("export SHELL=/bin/sh\nexport EDITOR=vim\n")

    sync_terminal_shells(
        home=tmp_path, environ={}, platform=_platform(), lookup=_lookup(zsh="/usr/bin/zsh")
    )

    text = zshenv.read_text()
    assert text.startswith("export SHELL=/bin/sh\nexport EDITOR=vim\n")
    assert text.index(_ZSHENV_BEGIN) > text.index("export EDITOR=vim")
    assert "export SHELL=/usr/bin/zsh" in text


def test_the_zshenv_dry_run_reports_drift_and_writes_nothing(tmp_path: Path) -> None:
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh"),
    }

    assert "zshenv" in sync_terminal_shells(**args, write=False).drifted
    assert not (tmp_path / ".zshenv").exists()

    sync_terminal_shells(**args, write=True)
    assert "zshenv" not in sync_terminal_shells(**args, write=False).drifted

    other_zsh = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/local/bin/zsh"),
        write=False,
    )
    assert "zshenv" in other_zsh.drifted


def test_no_zsh_strips_the_zshenv_block(tmp_path: Path) -> None:
    zshenv = tmp_path / ".zshenv"
    zshenv.write_text(
        f"export EDITOR=vim\n\n{_ZSHENV_BEGIN}\nexport SHELL=/usr/bin/zsh\n{_ZSHENV_END}\n"
    )
    before = zshenv.read_bytes()
    gone: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(),
    }

    dry = sync_terminal_shells(**gone, write=False)
    assert "zshenv" not in dry.drifted
    assert zshenv.read_bytes() == before

    sync_terminal_shells(**gone, write=True)
    text = zshenv.read_text()
    assert _ZSHENV_BEGIN not in text
    assert "export EDITOR=vim" in text


def test_macos_writes_no_zshenv(tmp_path: Path) -> None:
    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform("macos"),
        lookup=_lookup(zsh="/usr/bin/zsh"),
    )

    assert not (tmp_path / ".zshenv").exists()


def test_an_unreadable_zshenv_is_a_warning_and_terminals_still_sync(tmp_path: Path) -> None:
    zshenv = tmp_path / ".zshenv"
    zshenv.write_bytes(b"export X=\xff\n")
    kitty = tmp_path / ".config" / "kitty" / "kitty.conf"
    kitty.parent.mkdir(parents=True)
    kitty.write_text("font_size 14\n")
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    }

    dry = sync_terminal_shells(**args, write=False)
    assert any(warning.startswith("zshenv: ") for warning in dry.warnings)
    assert "kitty" in dry.drifted

    result = sync_terminal_shells(**args, write=True)
    assert any(warning.startswith("zshenv: ") for warning in result.warnings)
    assert zshenv.read_bytes() == b"export X=\xff\n"
    assert "shell /usr/bin/zsh -l" in kitty.read_text()


# Phase 23 / CONF-05, Task 2: kitty and WezTerm regions also carry SHELL.


def test_a_kitty_config_without_the_shell_line_drifts_and_is_fixed(tmp_path: Path) -> None:
    kitty = tmp_path / ".config" / "kitty" / "kitty.conf"
    kitty.parent.mkdir(parents=True)
    kitty.write_text(
        "# >>> tools-installer terminal-shell kitty >>>\n"
        "shell /usr/bin/zsh -l\n"
        "# <<< tools-installer terminal-shell kitty <<<\n"
    )
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    }

    assert "kitty" in sync_terminal_shells(**args, write=False).drifted

    result = sync_terminal_shells(**args, write=True)
    text = kitty.read_text()
    assert "shell /usr/bin/zsh -l" in text
    assert "env SHELL=/usr/bin/zsh" in text
    assert "kitty" not in sync_terminal_shells(**args, write=False).drifted
    assert ("kitty", kitty) in result.paths


def test_an_uninstalled_terminal_gives_no_drift(tmp_path: Path) -> None:
    lookup = _lookup(zsh="/usr/bin/zsh")

    dry = sync_terminal_shells(
        home=tmp_path, environ={}, platform=_platform(), lookup=lookup, write=False
    )
    assert set(dry.drifted) <= {"zshenv"}
    assert not (tmp_path / ".config").exists()

    sync_terminal_shells(home=tmp_path, environ={}, platform=_platform(), lookup=lookup)
    assert not (tmp_path / ".config").exists()


def test_wezterm_keeps_a_user_environment_table(tmp_path: Path) -> None:
    wezterm = tmp_path / ".config" / "wezterm" / "wezterm.lua"
    wezterm.parent.mkdir(parents=True)
    user_line = 'config.set_environment_variables = { FOO = "1" }'
    wezterm.write_text(
        f'local wezterm = require "wezterm"\nlocal config = {{}}\n{user_line}\nreturn config\n'
    )

    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", wezterm="/usr/bin/wezterm"),
    )

    lines = wezterm.read_text().splitlines()
    start = lines.index("-- >>> tools-installer terminal-shell wezterm >>>")
    end = lines.index("-- <<< tools-installer terminal-shell wezterm <<<")
    assert lines.index(user_line) < start < lines.index("return config")
    assert lines[start + 1 : end] == [
        'config.default_prog = { "/usr/bin/zsh", "-l" }',
        "config.set_environment_variables = config.set_environment_variables or {}",
        'config.set_environment_variables.SHELL = "/usr/bin/zsh"',
    ]


def test_the_region_bodies_quote_an_unusual_zsh_path(tmp_path: Path) -> None:
    zsh = "/opt/my shells/zsh"

    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh=zsh, kitty="/usr/bin/kitty", wezterm="/usr/bin/wezterm"),
    )

    kitty_text = (tmp_path / ".config" / "kitty" / "kitty.conf").read_text()
    assert "shell '/opt/my shells/zsh' -l" in kitty_text
    assert "env SHELL=/opt/my shells/zsh" in kitty_text
    wezterm_text = (tmp_path / ".config" / "wezterm" / "wezterm.lua").read_text()
    assert 'config.default_prog = { "/opt/my shells/zsh", "-l" }' in wezterm_text
    assert 'config.set_environment_variables.SHELL = "/opt/my shells/zsh"' in wezterm_text


def test_a_zsh_removal_stops_at_a_zshenv_warning(tmp_path: Path) -> None:
    kitty = tmp_path / ".config" / "kitty" / "kitty.conf"
    present: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    }
    sync_terminal_shells(**present)
    owned_kitty = kitty.read_bytes()
    zshenv = tmp_path / ".zshenv"
    zshenv.write_bytes(zshenv.read_bytes() + b"# \xff\n")

    result = sync_terminal_shells(
        home=tmp_path, environ={}, platform=_platform(), lookup=_lookup(kitty="/usr/bin/kitty")
    )

    assert result.reverted == ()
    assert [warning.split(":")[0] for warning in result.warnings] == ["zshenv"]
    assert "left as they are" in result.warnings[0]
    assert kitty.read_bytes() == owned_kitty


def test_strip_only_never_writes_while_zsh_is_present(tmp_path: Path) -> None:
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    }
    before = _fingerprint(tmp_path)

    result = sync_terminal_shells(**args, strip_only=True)

    assert _fingerprint(tmp_path) == before
    assert not (tmp_path / ".zshenv").exists()
    assert sync_message(result, report_changes=True) is None
    sync_terminal_shells(**args)
    gone = sync_terminal_shells(
        home=tmp_path, environ={}, platform=_platform(), lookup=_lookup(), strip_only=True
    )
    assert set(gone.reverted) == {"zshenv", "kitty"}


def test_a_post_run_sync_that_writes_reports_the_shell_lines(tmp_path: Path) -> None:
    zdotdir = tmp_path / "zdot"
    zdotdir.mkdir()
    args: _SyncArgs = {
        "home": tmp_path,
        "environ": {"ZDOTDIR": str(zdotdir)},
        "platform": _platform(),
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    }

    first = sync_terminal_shells(**args)
    again = sync_terminal_shells(**args)

    message = sync_message(first, report_changes=True)
    assert message is not None
    assert message.startswith(f"Shell: {zdotdir / '.zshenv'} now exports SHELL=/usr/bin/zsh")
    assert "Shell: kitty now starts zsh" in message
    assert sync_message(first) is None
    assert sync_message(again, report_changes=True) is None


# ---------------------------------------------------------------------------
# Alacritty (24 D-08, D-23): the `alacritty` shell region and the `alacritty-keys` region.
# ---------------------------------------------------------------------------

_ZSH = "/usr/bin/zsh"
_ALACRITTY_LOOKUP = _lookup(zsh=_ZSH, alacritty="/usr/bin/alacritty")


def _alacritty_tool() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "alacritty")


def _alacritty_toml() -> Path:
    return Path.home() / ".config" / "alacritty" / "alacritty.toml"


def _alacritty_record() -> Path:
    return Path.home() / ".local" / "share" / "tools-installer" / "terminal-tuning-alacritty"


def _sync_alacritty(*, write: bool = True, lookup: Callable[[str], str | None] | None = None):
    return sync_terminal_shells(
        home=Path.home(),
        environ=dict(os.environ),
        platform=_platform(),
        lookup=lookup or _ALACRITTY_LOOKUP,
        write=write,
    )


def _remove_alacritty(tmp_path: Path) -> None:
    from installer import app as app_module

    app_module._after_removal(  # pyright: ignore[reportPrivateUsage]
        _alacritty_tool(),
        bundles=(),
        bin_dir=tmp_path / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        extra_policies=(),
        platform_os="fedora",
    )


def test_alacritty_install_writes_both_regions_and_removal_strips_them(tmp_path: Path) -> None:
    from installer.post_install import run_post_install

    config = _alacritty_toml()
    config.parent.mkdir(parents=True)
    config.write_text("[font]\nsize = 12\n")

    run_post_install(_alacritty_tool(), _platform())
    keys_only = tomllib.loads(config.read_text())
    assert [(b["key"], b["mods"]) for b in keys_only["keyboard"]["bindings"]] == [
        ("Left", "Alt"),
        ("Right", "Alt"),
        ("K", "Control|Shift"),
    ]
    assert keys_only["keyboard"]["bindings"][0]["chars"] == "\x1bb"
    assert keys_only["keyboard"]["bindings"][1]["chars"] == "\x1bf"
    assert keys_only["keyboard"]["bindings"][2]["action"] == "ClearHistory"
    assert _alacritty_record().is_file()

    result = _sync_alacritty()
    document = tomllib.loads(config.read_text())
    assert document["terminal"]["shell"] == {"program": _ZSH, "args": ["-l"]}
    assert document["env"] == {"SHELL": _ZSH}
    assert document["font"] == {"size": 12}
    assert "alacritty" in result.configured
    assert ("alacritty", config) in result.paths

    settled = config.read_bytes()
    _sync_alacritty()
    assert config.read_bytes() == settled

    _remove_alacritty(tmp_path)
    assert config.read_text() == "[font]\nsize = 12\n"
    assert not _alacritty_record().exists()


_REGION = re.compile(
    r"# >>> tools-installer terminal-shell alacritty(-keys)? >>>\n.*?"
    r"# <<< tools-installer terminal-shell alacritty(-keys)? <<<\n",
    re.DOTALL,
)


def _outside_regions(text: str) -> str:
    return _REGION.sub("", text)


_USER_SHELL = '[terminal.shell]\nprogram = "/bin/fish"\n'
_USER_ENV = '[env]\nTERM = "xterm"\n'
_USER_ALT_LEFT = '[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "x"\n'


@pytest.mark.parametrize(
    ("user_text", "warning", "refusal"),
    [
        (_USER_SHELL, "alacritty: partial: you already define terminal.shell", None),
        (_USER_ENV, "alacritty: partial: you already define env", None),
        (_USER_ALT_LEFT, "alacritty: partial: you already bind Alt+Left", None),
        (
            "keyboard.bindings = []\n",
            None,
            "you already define keyboard.bindings inline",
        ),
    ],
    ids=["terminal-shell", "env", "binding", "inline-bindings"],
)
def test_alacritty_partial_conflicts(user_text: str, warning: str | None, refusal: str | None):
    from installer.terminal_shell import apply_alacritty_keys

    config = _alacritty_toml()
    config.parent.mkdir(parents=True)
    config.write_text(user_text)
    environ = dict(os.environ)

    lines, refused = apply_alacritty_keys(Path.home(), environ, skip_recorded=False)
    result = _sync_alacritty()

    assert refused == refusal
    if refusal is None:
        assert warning in result.warnings
        if "you already bind" in warning:  # the install action names it too
            assert warning in lines
    else:
        assert not _alacritty_record().exists()
        assert warning is None and result.warnings == ()
    final = config.read_text()
    assert _outside_regions(final) == user_text  # the user's bytes survive untouched
    document = tomllib.loads(final)
    program = document["terminal"]["shell"]["program"] if "terminal" in document else None
    assert program == ("/bin/fish" if user_text == _USER_SHELL else _ZSH)
    assert ("SHELL" in document.get("env", {})) == (user_text != _USER_ENV)
    if user_text == _USER_ENV:
        assert document["env"] == {"TERM": "xterm"}
    if user_text == _USER_ALT_LEFT:
        pairs = [(b["key"], b["mods"]) for b in document["keyboard"]["bindings"]]
        assert pairs.count(("Left", "Alt")) == 1 and ("Right", "Alt") in pairs
    if refusal is not None:
        assert "keyboard" in document and "[[keyboard.bindings]]" not in final


def test_alacritty_invalid_toml_writes_nothing() -> None:
    from installer.terminal_shell import apply_alacritty_keys

    config = _alacritty_toml()
    config.parent.mkdir(parents=True)
    config.write_text("[font\nsize = 12\n")
    before = config.read_bytes()

    result = _sync_alacritty()
    _lines, refused = apply_alacritty_keys(Path.home(), dict(os.environ), skip_recorded=False)

    assert config.read_bytes() == before
    assert result.warnings[0].startswith("alacritty: the file does not parse")
    assert "alacritty" not in result.configured
    assert refused is not None and refused.startswith("the file does not parse")
    assert not _alacritty_record().exists()


def test_alacritty_changed_before_commit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backstop: a file edited between the read and the write is not overwritten."""
    config = _alacritty_toml()
    config.parent.mkdir(parents=True)
    config.write_text("[font]\nsize = 12\n")
    real_read = terminal_shell.read_settings

    def racing_read(path: Path):
        snapshot = real_read(path)
        path.write_text(path.read_text() + "# edited meanwhile\n")
        return snapshot

    monkeypatch.setattr(terminal_shell, "read_settings", racing_read)

    result = _sync_alacritty()

    assert config.read_text() == "[font]\nsize = 12\n# edited meanwhile\n"
    assert "alacritty" not in result.configured + result.drifted
    assert result.warnings == ("alacritty: changed while being written",)


def test_alacritty_region_that_would_not_reparse_is_refused() -> None:
    """Backstop: an edit whose whole document fails `tomllib` writes nothing."""
    config = _alacritty_toml()
    config.parent.mkdir(parents=True)
    config.write_text('terminal = { osc52 = "Disabled" }\n')
    before = config.read_bytes()

    result = _sync_alacritty()

    assert config.read_bytes() == before
    assert result.warnings[0].startswith("alacritty: the edit would not re-parse")


def test_alacritty_keys_without_zsh() -> None:
    from installer.post_install import run_post_install

    config = _alacritty_toml()
    run_post_install(_alacritty_tool(), _platform())  # needs no zsh
    assert "keyboard" in tomllib.loads(config.read_text())

    _sync_alacritty()
    assert "shell" in tomllib.loads(config.read_text())["terminal"]
    result = _sync_alacritty(lookup=_lookup(alacritty="/usr/bin/alacritty"))

    document = tomllib.loads(config.read_text())
    assert "terminal" not in document and "env" not in document
    assert len(document["keyboard"]["bindings"]) == 3
    assert "alacritty" in result.reverted


def test_alacritty_regions_are_replaced_in_place_and_stay_apart() -> None:
    from installer.terminal_shell import apply_alacritty_keys

    config = _alacritty_toml()
    config.parent.mkdir(parents=True)
    config.write_text("[font]\nsize = 12\n")
    _sync_alacritty()
    apply_alacritty_keys(Path.home(), dict(os.environ), skip_recorded=False)
    text = config.read_text()
    assert text.index("terminal-shell alacritty >>>") < text.index(
        "terminal-shell alacritty-keys >>>"
    )

    _sync_alacritty(lookup=_lookup(zsh="/opt/zsh", alacritty="/usr/bin/alacritty"))
    after = config.read_text()
    assert '"/opt/zsh"' in after and _ZSH not in after
    assert after.index("terminal-shell alacritty >>>") < after.index(
        "terminal-shell alacritty-keys >>>"
    )
    # the keys region is the exact bytes it was before the shell region changed
    keys = re.search(r"# >>> [^\n]*alacritty-keys >>>.*?<<<\n", text, re.DOTALL)
    assert keys is not None and keys.group(0) in after


def test_alacritty_is_created_in_the_first_existing_location_or_the_xdg_one() -> None:
    from installer.terminal_shell import alacritty_config_path

    home = Path.home()
    environ = {"XDG_CONFIG_HOME": str(home / "xdg")}
    assert alacritty_config_path(home, environ) == home / "xdg" / "alacritty" / "alacritty.toml"
    (home / "xdg").mkdir()
    flat = home / "xdg" / "alacritty.toml"
    flat.write_text("")
    assert alacritty_config_path(home, environ) == flat

    result = sync_terminal_shells(
        home=home, environ=environ, platform=_platform(), lookup=_ALACRITTY_LOOKUP
    )
    assert "alacritty" in result.configured
    text = flat.read_text()
    assert text.startswith("# >>> tools-installer terminal-shell alacritty >>>")
    assert _outside_regions(text) == ""


# ---------------------------------------------------------------------------
# herdr (24 D-08b, D-22): terminal.default_shell follows zsh, then the server reloads.
# ---------------------------------------------------------------------------

_HERDR = "/usr/bin/herdr"
_HERDR_LOOKUP = _lookup(zsh=_ZSH, herdr=_HERDR)


def _herdr_toml() -> Path:
    return Path.home() / ".config" / "herdr" / "config.toml"


def _sync_herdr(
    *,
    lookup: Callable[[str], str | None] = _HERDR_LOOKUP,
    write: bool = True,
    runner: Callable[[list[str]], None] | None = None,
):
    return sync_terminal_shells(
        home=Path.home(),
        environ=dict(os.environ),
        platform=_platform(),
        lookup=lookup,
        write=write,
        runner=runner,
    )


def _ledgered_settings() -> list[str]:
    ledger = read_ledger("herdr")
    return [entry.setting for entry in ledger.entries] if ledger else []


def test_herdr_default_shell_written_and_reloaded() -> None:
    config = _herdr_toml()
    config.parent.mkdir(parents=True)
    config.write_text('[terminal]\nshell_mode = "auto"\n')
    calls: list[list[str]] = []

    result = _sync_herdr(runner=calls.append)

    assert tomllib.loads(config.read_text())["terminal"] == {
        "shell_mode": "auto",
        "default_shell": _ZSH,
    }
    assert _ledgered_settings() == ["default-shell"]
    assert calls == [[_HERDR, "server", "reload-config"]]
    assert "herdr" in result.configured and "herdr" in result.drifted
    assert ("herdr", config) in result.paths

    settled = config.read_bytes()
    _sync_herdr(runner=calls.append)
    assert config.read_bytes() == settled
    assert len(calls) == 1


def test_herdr_reload_failure_is_a_note() -> None:
    config = _herdr_toml()

    def failing(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    result = _sync_herdr(runner=failing)

    assert tomllib.loads(config.read_text())["terminal"]["default_shell"] == _ZSH
    assert any(w.startswith("herdr: reload-config failed") for w in result.warnings)
    assert "herdr" in result.configured


def test_herdr_user_default_shell_is_kept() -> None:
    config = _herdr_toml()
    config.parent.mkdir(parents=True)
    calls: list[list[str]] = []

    same = f'[terminal]\ndefault_shell = "{_ZSH}"\n'
    config.write_text(same)
    result = _sync_herdr(runner=calls.append)
    assert config.read_text() == same
    assert _ledgered_settings() == []
    assert result.warnings == () and "herdr" in result.configured
    assert "herdr" not in result.drifted

    other = '[terminal]\ndefault_shell = "/bin/fish"\n'
    config.write_text(other)
    result = _sync_herdr(runner=calls.append)
    assert config.read_text() == other
    assert result.warnings == ("herdr: partial: you already set terminal.default_shell",)
    assert "herdr" not in result.configured
    assert calls == []


@pytest.mark.parametrize(
    "lookup",
    [_lookup(zsh=_ZSH), _lookup(herdr=_HERDR)],
    ids=["no-herdr", "no-zsh"],
)
def test_herdr_nothing_without_zsh_or_herdr(lookup: Callable[[str], str | None]) -> None:
    calls: list[list[str]] = []

    result = _sync_herdr(lookup=lookup, runner=calls.append)

    assert not _herdr_toml().exists()
    assert calls == []
    assert "herdr" not in result.configured


def test_herdr_dry_run_reports_drift_without_reloading() -> None:
    config = _herdr_toml()
    config.parent.mkdir(parents=True)
    config.write_text('[terminal]\nshell_mode = "auto"\n')
    before = config.read_bytes()
    calls: list[list[str]] = []

    result = _sync_herdr(write=False, runner=calls.append)

    assert "herdr" in result.drifted
    assert config.read_bytes() == before
    assert calls == []
    assert _ledgered_settings() == []

    config.write_text('[terminal]\ndefault_shell = "/bin/fish"\n')
    kept = _sync_herdr(write=False)
    assert "herdr" not in kept.drifted
    assert kept.warnings == ("herdr: partial: you already set terminal.default_shell",)

    config.write_text("[terminal\n")
    broken = _sync_herdr(write=False)
    assert broken.warnings and broken.warnings[0].startswith("herdr: ")
    assert "herdr" not in broken.drifted


def test_zsh_gone_reverts_only_the_ledgered_default_shell() -> None:
    from installer.agent_settings import apply_setting

    config = _herdr_toml()
    apply_setting("herdr", "sidebar", home=Path.home(), platform_os="fedora", environ=os.environ)
    _sync_herdr()
    assert set(_ledgered_settings()) == {"default-shell", "sidebar"}  # sidebar: one per key

    result = _sync_herdr(lookup=_lookup(herdr=_HERDR))

    assert "herdr" in result.reverted
    assert "default_shell" not in tomllib.loads(config.read_text()).get("terminal", {})
    assert "ui" in tomllib.loads(config.read_text())  # the sidebar keys stay
    assert set(_ledgered_settings()) == {"sidebar"}

    _sync_herdr()
    config.write_text(config.read_text().replace(_ZSH, "/bin/fish"))
    kept = _sync_herdr(lookup=_lookup(herdr=_HERDR))
    assert "herdr" not in kept.reverted
    assert tomllib.loads(config.read_text())["terminal"]["default_shell"] == "/bin/fish"
