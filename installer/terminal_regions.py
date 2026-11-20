"""Owned-region primitives shared by the terminal shell sync and the terminal keys mechanism
(28 D-05).
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, cast

from installer.agent_settings import missing_dirs, read_settings, write_if_unchanged
from installer.atomic import FileSnapshot, atomic_write_text


class TerminalShellError(OSError):
    """Terminal configuration cannot be changed without risking user data."""


class Placement(Enum):
    END = "end"  # Append after the existing user content.
    TOP = "top"  # Place before every user line so later kitty mappings win.
    BEFORE_RETURN = "before_return"  # Place before WezTerm's single return config line.


WEZTERM_SKELETON: Final = 'local wezterm = require "wezterm"\nlocal config = {}\nreturn config\n'


def marker(terminal: str, edge: str, *, comment: str = "#") -> str:
    return f"{comment} {edge} tools-installer terminal-shell {terminal} {edge}"


def replace_owned_region(
    content: str,
    terminal: str,
    body: str | None,
    *,
    comment: str = "#",
    placement: Placement = Placement.END,
) -> str:
    """Place new regions only when absent; row validation guards every written text."""
    begin = marker(terminal, ">>>", comment=comment)
    end = marker(terminal, "<<<", comment=comment)
    lines = content.splitlines(keepends=True)
    start: int | None = None
    complete: tuple[int, int] | None = None

    for index, line in enumerate(lines):
        text_line = line.rstrip("\r\n")
        if text_line == begin:
            if start is not None or complete is not None:
                raise TerminalShellError(f"malformed {terminal} ownership region")
            start = index
        elif text_line == end:
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
        if placement is Placement.TOP:
            return f"{region}{content}"
        if placement is Placement.BEFORE_RETURN:
            content = content or WEZTERM_SKELETON
            lines = content.splitlines(keepends=True)
            indices = [i for i, line in enumerate(lines) if line.strip() == "return config"]
            if len(indices) != 1:
                raise TerminalShellError("unsupported return shape")
            index = indices[0]
            return "".join((*lines[:index], region, *lines[index:]))
        prefix = content if not content or content.endswith(("\n", "\r")) else f"{content}\n"
        return f"{prefix}{region}"
    start_index, end_index = complete
    return "".join((*lines[:start_index], region, *lines[end_index + 1 :]))


def xdg_config_home(home: Path, environ: Mapping[str, str]) -> Path:
    configured = environ.get("XDG_CONFIG_HOME")
    return Path(configured) if configured else home / ".config"


def xdg_data_home(home: Path, environ: Mapping[str, str]) -> Path:
    configured = environ.get("XDG_DATA_HOME")
    return Path(configured) if configured else home / ".local" / "share"


ALACRITTY = "alacritty"
ALACRITTY_KEYS = "alacritty-keys"
ALACRITTY_CREATED = "terminal-alacritty-created"


def alacritty_config_path(home: Path, environ: Mapping[str, str]) -> Path:
    """The first existing of Alacritty's user config locations, in its own precedence order
    (alacritty(5): XDG alacritty/, XDG file, ~/.config/alacritty/, ~/.alacritty.toml), else the
    XDG one. The system-wide /etc/alacritty/alacritty.toml is never edited: it is not ours."""
    config_home = xdg_config_home(home, environ)
    candidates = (
        config_home / "alacritty" / "alacritty.toml",
        config_home / "alacritty.toml",
        home / ".config" / "alacritty" / "alacritty.toml",
        home / ".alacritty.toml",
    )
    return next((path for path in candidates if path.exists()), candidates[0])


def first_line(exc: BaseException) -> str:
    return (str(exc).splitlines() or [type(exc).__name__])[0]


def snapshot_text(snapshot: FileSnapshot | None) -> str:
    if snapshot is None:
        return ""
    try:
        return snapshot.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TerminalShellError("the file is not valid UTF-8; refusing to rewrite it") from exc


def user_document(text: str) -> tuple[dict[str, object], str]:
    """The parsed text outside both owned regions, and that text. Never raises a ValueError."""
    outside = replace_owned_region(
        replace_owned_region(text, ALACRITTY, None), ALACRITTY_KEYS, None
    )
    try:
        return tomllib.loads(outside), outside
    except tomllib.TOMLDecodeError as exc:
        raise TerminalShellError(f"the file does not parse ({exc}); left as it is") from exc


def toml_table(document: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = document.get(name)
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


IMPORTS = "you import other files (general.import); they are not followed"


def imports_files(document: Mapping[str, object]) -> bool:
    """`[general] import` (or the legacy top-level `import`) names files this module never reads,
    so a shell or binding the user keeps there cannot be checked for a conflict."""
    return "import" in toml_table(document, "general") or "import" in document


@dataclass(frozen=True)
class KeysPlan:
    body: str | None
    conflicts: tuple[str, ...] = ()
    refusal: str | None = None
    notes: tuple[str, ...] = ()


_KEY_BINDINGS = (
    ("Left", "Alt", 'chars = "\\u001bb"'),
    ("Right", "Alt", 'chars = "\\u001bf"'),
    ("K", "Control|Shift", 'chars = "\\u000c"'),
)
_KEYS_HEADER = re.compile(r"^\s*\[\[\s*keyboard\.bindings\s*\]\]", re.MULTILINE)


def _binding_id(key: object, mods: object) -> tuple[str, frozenset[str]]:
    """Alacritty reads key and modifier names case-insensitively, in any order."""
    names = str(mods or "").split("|")
    return str(key).lower(), frozenset(name.strip().lower() for name in names if name.strip())


def alacritty_keys_plan(document: Mapping[str, object], outside: str) -> KeysPlan:
    if imports_files(document):
        return KeysPlan(None, refusal=IMPORTS)
    bindings = toml_table(document, "keyboard").get("bindings")
    if bindings is not None and not _KEYS_HEADER.search(outside):
        return KeysPlan(None, refusal="you already define keyboard.bindings inline")
    entries = cast("list[object]", bindings) if isinstance(bindings, list) else []
    taken = {
        _binding_id(entry.get("key"), entry.get("mods"))
        for entry in (cast("Mapping[str, object]", e) for e in entries if isinstance(e, dict))
    }
    blocks: list[str] = []
    conflicts: list[str] = []
    for key, mods, action in _KEY_BINDINGS:
        if _binding_id(key, mods) in taken:
            conflicts.append(f"alacritty: partial: you already bind {mods.replace('|', '+')}+{key}")
        else:
            blocks.append(f'[[keyboard.bindings]]\nkey = "{key}"\nmods = "{mods}"\n{action}')
    return KeysPlan("\n\n".join(blocks) or None, tuple(conflicts))


def validate_toml(text: str) -> None:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise TerminalShellError(f"the edit would not re-parse ({exc}); nothing written") from exc


def created_path_record(created_marker: Path) -> Path:
    return created_marker.with_name(f"{created_marker.name}-path")


def commit_region(
    path: Path,
    before: FileSnapshot | None,
    text: str,
    updated: str,
    *,
    validate: Callable[[str], None],
    write: bool,
    created_marker: Path,
    home: Path,
    bind_path: bool = False,
) -> bool:
    """Report whether `updated` differs; write it only when `write`, and only after it re-parses
    and only if the file still is what was read (compare-before-commit)."""
    if updated == text:
        return False
    validate(updated)
    if write:
        created_dirs = missing_dirs(path, home) if before is None else ()
        write_if_unchanged(path, before, updated)
        if before is None:
            # The file is ours: strip may delete it once nothing else is in it, and the
            # directories this write created (listed after the first line) with it.
            created_marker.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(created_marker, "\n".join(("created", *created_dirs)) + "\n")
            if bind_path:
                atomic_write_text(created_path_record(created_marker), f"{path}\n")
    return True


def strip_region(path: Path, region: str, *, comment: str = "#") -> bool:
    before = read_settings(path)
    if before is None:
        return False
    text = snapshot_text(before)
    updated = replace_owned_region(text, region, None, comment=comment)
    if updated == text:
        return False
    write_if_unchanged(path, before, updated)
    return True
