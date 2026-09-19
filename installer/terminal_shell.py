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


def _marker(terminal: str, edge: str) -> str:
    return f"# {edge} tools-installer terminal-shell {terminal} {edge}"


def _replace_owned_region(content: str, terminal: str, body: str) -> str:
    """Replace exactly one complete owned region, rejecting malformed markers."""
    begin = _marker(terminal, ">>>")
    end = _marker(terminal, "<<<")
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


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8") if path.exists() else ""


def _write_if_changed(path: Path, content: str) -> bool:
    existing = _read_text(path)
    if content == existing:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, content)
    return True


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
        return TerminalShellResult(skipped=("zsh unavailable",))

    if omz_present(home, environ):
        ensure_zshrc_template(home / ".zshrc")

    if _safe_executable(lookup("kitty")) is None:
        return TerminalShellResult(skipped=("kitty unavailable",))

    config_path = _kitty_config_path(home, environ)
    updated = _replace_owned_region(
        _read_text(config_path), "kitty", f"shell {shlex.join((zsh_path, '-l'))}"
    )
    _write_if_changed(config_path, updated)
    return TerminalShellResult(configured=("kitty",))
