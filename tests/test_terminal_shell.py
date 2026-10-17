"""Safety-first terminal emulator shell synchronization tests."""

import contextlib
import os
import shlex
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import pytest

from installer.platform import Platform
from installer.terminal_shell import (
    TerminalShellError,
    sync_terminal_shells,
    terminal_sync_warning,
)


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
    assert result.configured == ("kitty", "wezterm")
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
    assert result.configured == ("kitty", "wezterm")
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
    assert result.configured == ("kitty", "wezterm", "konsole")
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

    assert result.reverted == ("kitty", "wezterm", "konsole")
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

    assert result.drifted == ("kitty",)
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

    assert result.configured == ("kitty",)
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
