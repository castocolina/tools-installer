"""Safely synchronize the discovered zsh into Linux terminal configurations.

This module configures only marker-delimited regions in terminal-emulator files.
It never invokes a shell or changes an account login shell.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from installer.atomic import atomic_write_text
from installer.omz import ensure_zshrc_template, omz_present
from installer.platform import Platform

Lookup = Callable[[str], str | None]


class TerminalShellError(OSError):
    """Terminal configuration cannot be changed without risking user data."""


@dataclass(frozen=True)
class TerminalShellResult:
    """Terminal synchronization outcomes, split by the action taken."""

    configured: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    reverted: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _marker(terminal: str, edge: str, *, comment: str = "#") -> str:
    return f"{comment} {edge} tools-installer terminal-shell {terminal} {edge}"


def _replace_owned_region(
    content: str, terminal: str, body: str | None, *, comment: str = "#"
) -> str:
    """Replace exactly one complete owned region, rejecting malformed markers."""
    begin = _marker(terminal, ">>>", comment=comment)
    end = _marker(terminal, "<<<", comment=comment)
    lines = content.splitlines(keepends=True)
    start: int | None = None
    complete: tuple[int, int] | None = None

    for index, line in enumerate(lines):
        marker = line.rstrip("\r\n")
        if marker == begin:
            if start is not None or complete is not None:
                raise TerminalShellError(f"malformed {terminal} ownership region")
            start = index
        elif marker == end:
            if start is None:
                raise TerminalShellError(f"malformed {terminal} ownership region")
            complete = (start, index)
            start = None

    if start is not None:
        raise TerminalShellError(f"malformed {terminal} ownership region")

    if body is None:
        if complete is None:
            return content
        start_index, end_index = complete
        return "".join((*lines[:start_index], *lines[end_index + 1 :]))

    region = f"{begin}\n{body}\n{end}\n"
    if complete is None:
        prefix = content if not content or content.endswith(("\n", "\r")) else f"{content}\n"
        return f"{prefix}{region}"
    start_index, end_index = complete
    return "".join((*lines[:start_index], region, *lines[end_index + 1 :]))


def _safe_executable(path: str | None) -> str | None:
    if path is None:
        return None
    if not path or not Path(path).is_absolute():
        raise TerminalShellError("discovered executable path must be absolute")
    if any(ord(character) < 32 or ord(character) == 127 for character in path):
        raise TerminalShellError("discovered executable path contains a control character")
    return path


def _xdg_config_home(home: Path, environ: Mapping[str, str]) -> Path:
    configured = environ.get("XDG_CONFIG_HOME")
    return Path(configured) if configured else home / ".config"


def _kitty_config_path(home: Path, environ: Mapping[str, str]) -> Path:
    return _xdg_config_home(home, environ) / "kitty" / "kitty.conf"


def _xdg_data_home(home: Path, environ: Mapping[str, str]) -> Path:
    configured = environ.get("XDG_DATA_HOME")
    return Path(configured) if configured else home / ".local" / "share"


def _wezterm_config_path(home: Path, environ: Mapping[str, str]) -> Path:
    config_home = _xdg_config_home(home, environ)
    configured = config_home / "wezterm" / "wezterm.lua"
    fallback = home / ".wezterm.lua"
    if configured.exists() or not fallback.exists():
        return configured
    return fallback


def _lua_string(value: str) -> str:
    """Encode a validated string for the narrow Lua string shape we emit."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _wezterm_content(existing: str, zsh_path: str) -> str | None:
    """Add the owned Lua region before a recognised `return config` boundary."""
    body = f'config.default_prog = {{ {_lua_string(zsh_path)}, "-l" }}'
    updated = _replace_owned_region(existing, "wezterm", body, comment="--")
    if "tools-installer terminal-shell wezterm" in existing:
        return (
            updated
            if any(line.strip() == "return config" for line in existing.splitlines())
            else None
        )

    lines = existing.splitlines(keepends=True)
    return_indices = [index for index, line in enumerate(lines) if line.strip() == "return config"]
    if len(return_indices) != 1:
        return None
    region = (
        f"{_marker('wezterm', '>>>', comment='--')}\n{body}\n"
        f"{_marker('wezterm', '<<<', comment='--')}\n"
    )
    index = return_indices[0]
    return "".join((*lines[:index], region, *lines[index:]))


def _kconfig_command(zsh_path: str) -> str:
    """Render the two login-shell argv values for Konsole's command field."""
    return shlex.join((zsh_path, "-l"))


def _desktop_default(content: str) -> str | None:
    """Return the effective Desktop Entry default-profile value, if any."""
    in_desktop_entry = False
    found: str | None = None
    for line in content.splitlines():
        if line.startswith("[") and line.endswith("]"):
            in_desktop_entry = line == "[Desktop Entry]"
        elif in_desktop_entry and line.startswith("DefaultProfile="):
            found = line.removeprefix("DefaultProfile=")
    return found


def _remove_if_owned(path: Path, terminal: str, *, comment: str = "#") -> bool:
    if not path.exists():
        return False
    existing = _read_text(path)
    updated = _replace_owned_region(existing, terminal, None, comment=comment)
    if updated == existing:
        return False
    _write_if_changed(path, updated)
    return True


def _read_text(path: Path) -> str:
    """Read a terminal configuration file, refusing one this module cannot decode.

    A non-UTF-8 byte is reported as TerminalShellError -- an OSError subclass,
    like every other refusal here -- rather than the bare UnicodeDecodeError
    `bytes.decode` raises. UnicodeDecodeError is a ValueError, not an OSError,
    so it would escape the OSError handler each lifecycle call site wraps the
    synchronizer in. Refusing also leaves the file byte-identical rather than
    rewriting content this module could not read.
    """
    if not path.exists():
        return ""
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TerminalShellError(f"{path} is not valid UTF-8; refusing to rewrite it") from exc


def _write_if_changed(path: Path, content: str) -> bool:
    existing = _read_text(path)
    if content == existing:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, content)
    return True


def _sync_konsole(
    *, home: Path, environ: Mapping[str, str], zsh_path: str, lookup: Lookup
) -> tuple[bool, str | None]:
    """Create the dedicated Konsole profile and select it without touching user profiles."""
    if _safe_executable(lookup("konsole")) is None:
        return False, None

    data_home = _xdg_data_home(home, environ)
    profile = data_home / "konsole" / "tools-installer-zsh.profile"
    state = data_home / "tools-installer" / "terminal-shell-konsole-default"
    konsolerc = _xdg_config_home(home, environ) / "konsolerc"
    profile_content = _read_text(profile)
    if profile_content and "tools-installer terminal-shell konsole-profile" not in profile_content:
        return False, "konsole: installer profile path is already user-owned"

    original_konsolerc = _read_text(konsolerc)
    updated_profile = _replace_owned_region(
        profile_content,
        "konsole-profile",
        f"[General]\nCommand={_kconfig_command(zsh_path)}",
    )
    updated_konsolerc = _replace_owned_region(
        original_konsolerc,
        "konsole",
        "[Desktop Entry]\nDefaultProfile=tools-installer-zsh.profile",
    )
    if not state.exists():
        state.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(state, f"{_desktop_default(original_konsolerc) or ''}\n")
    _write_if_changed(profile, updated_profile)
    _write_if_changed(konsolerc, updated_konsolerc)
    return True, None


def _revert_konsole(*, home: Path, environ: Mapping[str, str]) -> bool:
    """Undo only the profile and selection whose ownership this module can prove."""
    data_home = _xdg_data_home(home, environ)
    profile = data_home / "konsole" / "tools-installer-zsh.profile"
    state = data_home / "tools-installer" / "terminal-shell-konsole-default"
    konsolerc = _xdg_config_home(home, environ) / "konsolerc"
    reverted = False
    current_konsolerc = _read_text(konsolerc)
    if _desktop_default(current_konsolerc) == "tools-installer-zsh.profile":
        reverted = _remove_if_owned(konsolerc, "konsole") or reverted
    if profile.exists() and "tools-installer terminal-shell konsole-profile" in _read_text(profile):
        profile.unlink()
        reverted = True
    if state.exists():
        state.unlink()
    return reverted


def _revert_terminal_shells(*, home: Path, environ: Mapping[str, str]) -> TerminalShellResult:
    """Remove only complete terminal regions created by this synchronizer."""
    reverted: list[str] = []
    kitty = _kitty_config_path(home, environ)
    if _remove_if_owned(kitty, "kitty"):
        reverted.append("kitty")
    wezterm = _wezterm_config_path(home, environ)
    if _remove_if_owned(wezterm, "wezterm", comment="--"):
        reverted.append("wezterm")
    if _revert_konsole(home=home, environ=environ):
        reverted.append("konsole")
    return TerminalShellResult(reverted=tuple(reverted), skipped=("zsh unavailable",))


def sync_terminal_shells(
    *,
    home: Path,
    environ: Mapping[str, str],
    platform: Platform,
    lookup: Lookup,
) -> TerminalShellResult:
    """Synchronize zsh into detected Linux terminal emulators.

    The caller injects every environment-dependent value so tests never consult or
    mutate the developer's actual home directory.
    """
    if platform.os == "macos":
        return TerminalShellResult(skipped=("macos",))

    zsh_path = _safe_executable(lookup("zsh"))
    if zsh_path is None:
        return _revert_terminal_shells(home=home, environ=environ)

    if omz_present(home, environ):
        ensure_zshrc_template(home / ".zshrc")

    configured: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    if _safe_executable(lookup("kitty")) is None:
        skipped.append("kitty unavailable")
    else:
        config_path = _kitty_config_path(home, environ)
        updated = _replace_owned_region(
            _read_text(config_path), "kitty", f"shell {shlex.join((zsh_path, '-l'))}"
        )
        _write_if_changed(config_path, updated)
        configured.append("kitty")

    wezterm_path = _wezterm_config_path(home, environ)
    wezterm_existing = _read_text(wezterm_path)
    if not wezterm_existing:
        wezterm_existing = 'local wezterm = require "wezterm"\nlocal config = {}\nreturn config\n'
    wezterm_content = _wezterm_content(wezterm_existing, zsh_path)
    if wezterm_content is None:
        warnings.append("wezterm: unsupported return shape")
    else:
        _write_if_changed(wezterm_path, wezterm_content)
        configured.append("wezterm")

    konsole_configured, konsole_warning = _sync_konsole(
        home=home, environ=environ, zsh_path=zsh_path, lookup=lookup
    )
    if konsole_configured:
        configured.append("konsole")
    if konsole_warning is not None:
        warnings.append(konsole_warning)
    return TerminalShellResult(
        configured=tuple(configured), skipped=tuple(skipped), warnings=tuple(warnings)
    )
