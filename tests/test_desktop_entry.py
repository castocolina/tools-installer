"""The pure desktop-entry renderer (24 D-06): upstream text in, absolute paths out."""

from pathlib import Path

import pytest

from installer.desktop_entry import DesktopEntryError, render

UPSTREAM = """[Desktop Entry]
Type=Application
TryExec=alacritty
Exec=alacritty
Icon=Alacritty
Terminal=false
Categories=System;TerminalEmulator;

Name=Alacritty
GenericName=Terminal
Comment=A fast, cross-platform, OpenGL terminal emulator
StartupNotify=true
StartupWMClass=Alacritty
Actions=New;

X-Desktop-File-Install-Version=0.26

[Desktop Action New]
Name=New Terminal
Exec=alacritty
"""
BINARY = Path("/home/u/.local/bin/alacritty")
ICON = Path("/home/u/.local/share/icons/hicolor/scalable/apps/Alacritty.svg")


def test_render_rewrites_exec_tryexec_and_icon() -> None:
    rendered = render(UPSTREAM, binary=BINARY, icon=ICON)
    lines = rendered.splitlines()
    assert lines.count(f"TryExec={BINARY}") == 1
    assert lines.count(f"Exec={BINARY}") == 2
    assert lines.count(f"Icon={ICON}") == 1
    untouched = [
        line
        for line in UPSTREAM.splitlines()
        if not line.startswith(("TryExec=", "Exec=", "Icon="))
    ]
    kept = [line for line in lines if not line.startswith(("TryExec=", "Exec=", "Icon="))]
    assert kept == untouched
    assert rendered.endswith("\n")


def test_render_keeps_exec_arguments_and_the_icon_when_none_is_given() -> None:
    source = "[Desktop Entry]\nExec=alacritty --class Foo %U\nIcon=Alacritty\n"
    rendered = render(source, binary=BINARY, icon=None)
    assert f"Exec={BINARY} --class Foo %U" in rendered.splitlines()
    assert "Icon=Alacritty" in rendered.splitlines()


def test_render_quotes_a_path_with_a_space() -> None:
    binary = Path("/home/my user/.local/bin/alacritty")
    rendered = render(UPSTREAM, binary=binary, icon=None)
    assert 'Exec="/home/my user/.local/bin/alacritty"' in rendered.splitlines()
    # TryExec and Icon are plain strings in the Desktop Entry spec: only Exec is quoted.
    assert "TryExec=/home/my user/.local/bin/alacritty" in rendered.splitlines()


def test_render_escapes_the_reserved_characters_in_a_quoted_path() -> None:
    binary = Path('/home/a"b$c`d\\e/bin/alacritty')
    rendered = render(UPSTREAM, binary=binary, icon=None)
    # The string rule runs before the quoting rule, so each escape is doubled in the file:
    # a quote, dollar or backtick takes two backslashes, a literal backslash takes four.
    two, four = "\\" * 2, "\\" * 4
    expected = f'Exec="/home/a{two}"b{two}$c{two}`d{four}e/bin/alacritty"'
    assert expected in rendered.splitlines()


def test_render_doubles_a_percent_sign_so_it_is_not_a_field_code() -> None:
    rendered = render(UPSTREAM, binary=Path("/home/u/100%/alacritty"), icon=None)
    assert "Exec=/home/u/100%%/alacritty" in rendered.splitlines()


@pytest.mark.parametrize(
    "binary",
    [Path("alacritty"), Path("bin/alacritty"), Path("/home/u/bin/a\x07b"), Path("/home/u/\x7f")],
)
def test_render_refuses_relative_or_control_character_paths(binary: Path) -> None:
    with pytest.raises(DesktopEntryError):
        render(UPSTREAM, binary=binary, icon=None)


def test_render_refuses_a_relative_icon() -> None:
    with pytest.raises(DesktopEntryError):
        render(UPSTREAM, binary=BINARY, icon=Path("Alacritty.svg"))
