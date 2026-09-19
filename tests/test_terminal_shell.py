"""Safety-first terminal emulator shell synchronization tests."""

from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import pytest

from installer.platform import Platform
from installer.terminal_shell import TerminalShellError, sync_terminal_shells


class _SyncArgs(TypedDict):
    home: Path
    environ: dict[str, str]
    platform: Platform
    lookup: Callable[[str], str | None]


def _platform(os_name: str = "fedora") -> Platform:
    return Platform(os=os_name, arch="amd64", immutable=os_name == "fedora", has_brew=False)


def _lookup(**executables: str) -> Callable[[str], str | None]:
    return lambda name: executables.get(name)


@pytest.mark.parametrize("os_name", ("fedora", "debian", "arch"))
def test_sync_writes_kitty_login_shell_for_each_supported_linux_distro(
    tmp_path: Path, os_name: str
) -> None:
    result = sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(os_name),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
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

    def record_template(path: Path) -> bool:
        writes.append(path)
        return real_ensure_template(path)

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


def test_wezterm_generates_an_owned_login_program_before_return_config(tmp_path: Path) -> None:
    config_home = tmp_path / "xdg" / "config"
    result = sync_terminal_shells(
        home=tmp_path,
        environ={"XDG_CONFIG_HOME": str(config_home)},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
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
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
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
        lookup=_lookup(zsh=zsh_path, kitty="/usr/bin/kitty"),
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
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"),
    )

    profile = data_home / "konsole" / "tools-installer-zsh.profile"
    state = data_home / "tools-installer" / "terminal-shell-konsole-default"
    assert result.configured == ("kitty", "wezterm", "konsole")
    assert "Command=/usr/bin/zsh -l" in profile.read_text()
    assert "DefaultProfile=tools-installer-zsh.profile" in konsolerc.read_text()
    assert state.read_text() == "Old.profile\n"


def test_konsole_serializer_preserves_special_login_argv_and_rejects_unsafe_paths(
    tmp_path: Path,
) -> None:
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

    assert "Command='/opt/Zsh Tools/z\"sh\\bin' -l" in profile.read_text()
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
        "lookup": _lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty", konsole="/usr/bin/konsole"),
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


def test_absent_konsole_does_not_create_profile_or_kconfig(tmp_path: Path) -> None:
    sync_terminal_shells(
        home=tmp_path,
        environ={},
        platform=_platform(),
        lookup=_lookup(zsh="/usr/bin/zsh", kitty="/usr/bin/kitty"),
    )

    assert not (tmp_path / ".local" / "share" / "konsole" / "tools-installer-zsh.profile").exists()
    assert not (tmp_path / ".config" / "konsolerc").exists()
