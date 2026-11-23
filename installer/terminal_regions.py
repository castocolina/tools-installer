"""Owned-region primitives shared by the terminal shell sync and the terminal keys mechanism
(28 D-05).
"""

from __future__ import annotations

import glob
import itertools
import os
import re
import tomllib
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, cast

from installer.agent_settings import missing_dirs, read_settings, write_if_unchanged
from installer.atomic import FileSnapshot, atomic_write_text, read_capped


class TerminalShellError(OSError):
    """Terminal configuration cannot be changed without risking user data."""


class Placement(Enum):
    END = "end"  # Append after the existing user content.
    TOP = "top"  # Place before every user line so later kitty mappings win.
    BEFORE_RETURN = "before_return"  # Place before WezTerm's single return config line.


WEZTERM = "wezterm"
WEZTERM_KEYS = "wezterm-keys"
WEZTERM_CREATED = "terminal-wezterm-created"
WEZTERM_SKELETON: Final = 'local wezterm = require "wezterm"\nlocal config = {}\nreturn config\n'
WEZTERM_UNVERIFIED: Final = "wezterm: could not verify the keys against wezterm show-keys"
_WEZTERM_KEYS_ASSIGNMENT = re.compile(
    r"^\s*config\.keys\s*=(?!=)(?!\s*config\.keys\s+or\b)(?!\s*config\.keys\s+or\s*\{)"
)
_WEZTERM_ENTRY_KEY = re.compile(r"""\bkey\s*=\s*(['"])([^'"]+)\1""")
_WEZTERM_ENTRY_MODS = re.compile(r"""\bmods\s*=\s*(['"])([^'"]*)\1""")
_WEZTERM_ENTRY = re.compile(
    r"^\s*\{\s*key\s*=\s*'([^']+)'\s*,\s*mods\s*=\s*'([^']*)'\s*,\s*action\s*=\s*(.*?)\s*\},?\s*$"
)


def wezterm_config_path(home: Path, environ: Mapping[str, str]) -> Path:
    config_home = xdg_config_home(home, environ)
    configured = config_home / "wezterm" / "wezterm.lua"
    fallback = home / ".wezterm.lua"
    return configured if configured.exists() or not fallback.exists() else fallback


def wezterm_keys_body(rows: Sequence[tuple[str, str, str]]) -> str:
    lines = (
        "do",
        '  local wezterm = require "wezterm"',
        "  local act = wezterm.action",
        '  local alias = { CMD = "SUPER", WIN = "SUPER", OPT = "ALT", '
        'META = "ALT", CONTROL = "CTRL" }',
        "  local function chord(key, mods)",
        "    local set = {}",
        '    for name in string.gmatch(string.upper(mods or ""), "[^|%s]+") do',
        "      local m = alias[name] or name",
        '      if m ~= "NONE" then set[m] = true end',
        "    end",
        '    local k = key or ""',
        '    if string.match(k, "^%u$") then set.SHIFT = true end',
        "    local names = {}",
        "    for m in pairs(set) do names[#names + 1] = m end",
        "    table.sort(names)",
        '    return string.lower(k) .. "/" .. table.concat(names, "|")',
        "  end",
        "  config.keys = config.keys or {}",
        "  local taken = {}",
        "  for _, entry in ipairs(config.keys) do taken[chord(entry.key, entry.mods)] = true end",
        "  for _, entry in ipairs({",
    )
    rendered = tuple(
        f'    {{ key = "{key}", mods = "{mods}", action = act.SendString "'
        + "".join(f"\\x{ord(char):02x}" if ord(char) < 32 else char for char in send)
        + '" },'
        for key, mods, send in rows
    )
    return "\n".join(
        (
            *lines,
            *rendered,
            "  }) do",
            "    if not taken[chord(entry.key, entry.mods)] then "
            "table.insert(config.keys, entry) end",
            "  end",
            "end",
        )
    )


def validate_wezterm(text: str) -> None:
    lines = text.splitlines()
    begin = marker(WEZTERM_KEYS, ">>>", comment="--")
    end = marker(WEZTERM_KEYS, "<<<", comment="--")
    if begin not in lines or end not in lines or lines.index(begin) >= lines.index(end):
        raise TerminalShellError(
            "the WezTerm keys region would not sit before return config; nothing written"
        )
    end_index = lines.index(end)
    returns = [
        index
        for index, line in enumerate(lines)
        if line.strip() == "return config" and index > end_index
    ]
    if not returns or any(line.strip() == "return config" for line in lines[: end_index + 1]):
        raise TerminalShellError(
            "the WezTerm keys region would not sit before return config; nothing written"
        )
    for line in lines[end_index + 1 : returns[0]]:
        if _WEZTERM_KEYS_ASSIGNMENT.match(line) and not re.match(
            r"^\s*config\.keys\s*=\s*config\.keys\s+or\b", line
        ):
            raise TerminalShellError(
                "your config.keys assignment after the WezTerm keys region would replace its "
                "keys; nothing written"
            )
    # shortcut: other edits are not detected; extend this guard if users report replacement.


def wezterm_chord(key: str, mods: str) -> str:
    aliases = {"CMD": "SUPER", "WIN": "SUPER", "OPT": "ALT", "META": "ALT", "CONTROL": "CTRL"}
    names = {
        aliases.get(name.upper(), name.upper())
        for name in re.split(r"[|\s]+", mods)
        if name and name.upper() != "NONE"
    }
    if re.fullmatch(r"[A-Z]", key):
        names.add("SHIFT")
    return f"{key.lower()}/{'|'.join(sorted(names))}"


def wezterm_display(key: str, mods: str) -> str:
    return f"{mods.replace('OPT', 'ALT').replace('|', '+')}+{key}"


def wezterm_disabled_chords(
    text: str, rows: Sequence[tuple[str, str, str]]
) -> tuple[tuple[str, str], ...]:
    """The installer chords the user's own config disables with DisableDefaultAssignment.

    Each item is (chord, report line). The scan reads one-line Lua key entries outside the
    installer's region; it is a line scan with linear patterns and never writes anything.
    """
    begin = marker(WEZTERM_KEYS, ">>>", comment="--")
    end = marker(WEZTERM_KEYS, "<<<", comment="--")
    ours = {wezterm_chord(key, mods): wezterm_display(key, mods) for key, mods, _ in rows}
    found: dict[str, str] = {}
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == begin:
            inside = True
        elif stripped == end:
            inside = False
        elif inside or stripped.startswith("--") or "DisableDefaultAssignment" not in line:
            continue
        else:
            key, mods = _WEZTERM_ENTRY_KEY.search(line), _WEZTERM_ENTRY_MODS.search(line)
            if key is None or mods is None:
                continue
            chord = wezterm_chord(key.group(2), mods.group(2))
            if chord in ours and chord not in found:
                found[chord] = (
                    f"wezterm: partial: your config disables {ours[chord]} "
                    "(DisableDefaultAssignment); kept yours"
                )
    return tuple(found.items())


def wezterm_readback(
    output: str, rows: Sequence[tuple[str, str, str]], reported: Collection[str] = ()
) -> tuple[str, ...]:
    """Lines for a chord wezterm show-keys lists with another action, disabled, or not at all.

    `reported` holds chords the static config scan already named. A failed command or output
    with no keys section cannot be judged and yields WEZTERM_UNVERIFIED.
    """
    actions: dict[str, str] = {}
    expected_chords = {wezterm_chord(key, mods.replace("OPT", "ALT")) for key, mods, _ in rows}
    in_keys = False
    listed = False
    for line in output.splitlines():
        if line.strip().startswith("key_tables"):
            break
        if line.strip().startswith("keys = {"):
            in_keys = listed = True
        elif in_keys:
            match = _WEZTERM_ENTRY.match(line)
            if match:
                key, mods, action = match.groups()
                chord = wezterm_chord(key, mods)
                if chord in expected_chords:
                    actions[chord] = action
    if not listed:
        return (WEZTERM_UNVERIFIED,)
    lines: list[str] = []
    for key, mods, send in rows:
        chord = wezterm_chord(key, mods)
        if chord in reported:
            continue
        display = wezterm_display(key, mods)
        expected = {
            "\x0c": "act.SendString '\\f'",
            "\x1bb": "act.SendString '\\u{1b}b'",
            "\x1bf": "act.SendString '\\u{1b}f'",
        }.get(send)
        action = actions.get(chord)
        if action is None:
            lines.append(
                f"wezterm: partial: wezterm show-keys does not list {display}; "
                "your config removes it"
            )
        elif "DisableDefaultAssignment" in action:
            lines.append(
                f"wezterm: partial: wezterm show-keys lists {display} as "
                "DisableDefaultAssignment; your config disables it; kept yours"
            )
        elif action != expected and expected is not None:
            lines.append(f"wezterm: partial: you already bind {display}; kept yours")
    return tuple(lines)


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


KITTY = "kitty"
KITTY_KEYS = "kitty-keys"
KITTY_CREATED = "terminal-kitty-created"


def kitty_config_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    """Resolve kitty v0.49.2 tools/utils/paths.go ConfigDirForName order."""
    direct = environ.get("KITTY_CONFIG_DIRECTORY")
    if direct:
        return Path(direct).expanduser() / "kitty.conf"
    roots = (
        [Path(value).expanduser() for value in (environ.get("XDG_CONFIG_HOME", ""),)]
        if environ.get("XDG_CONFIG_HOME")
        else []
    )
    roots.extend(
        Path(value).expanduser() for value in environ.get("XDG_CONFIG_DIRS", "").split(":") if value
    )
    roots.extend((home / ".config",))
    if platform_os == "macos":
        roots.append(home / "Library" / "Preferences")
    unique = dict.fromkeys(roots)
    for root in unique:
        config = root / "kitty" / "kitty.conf"
        if config.exists() and os.access(config.parent, os.W_OK):
            return config
    return xdg_config_home(home, environ) / "kitty" / "kitty.conf"


@dataclass(frozen=True)
class KittyScan:
    taken: frozenset[str]
    kitty_mod: str
    reports: tuple[str, ...] = ()
    clears_all: bool = False


def kitty_chord(chord: str, kitty_mod: str) -> str:
    """Normalize kitty modifier aliases and expand kitty_mod."""
    aliases = {
        "control": "ctrl",
        "ctrl": "ctrl",
        "opt": "alt",
        "option": "alt",
        "alt": "alt",
        "cmd": "super",
        "command": "super",
        "super": "super",
        "shift": "shift",
    }
    parts = chord.lower().split("+")
    key = {"return": "enter"}.get(parts[-1], parts[-1])
    modifiers: set[str] = set()
    for part in parts[:-1]:
        values = kitty_mod.lower().split("+") if part == "kitty_mod" else [part]
        modifiers.update(aliases.get(value, value) for value in values)
    return "+".join((*sorted(modifiers), key))


def scan_kitty(text: str, path: Path, platform_os: str = "linux") -> KittyScan:
    default = "ctrl+shift"
    raw: list[str] = []
    reports: list[str] = []
    try:
        visited = {path.resolve()}
    except (OSError, RuntimeError):
        visited: set[Path] = set()
        reports.append(f"kitty: partial: {path.name} could not be read; maps there are not checked")
    read_files = 1
    stopped: set[str] = set()
    clears_all = False
    value_options = {
        "--when-focus-on",
        "--mode",
        "--new-mode",
        "--on-unknown",
        "--on-action",
        "--allow-fallback",
        "--timeout",
    }

    def walk(source: str, base: Path, depth: int) -> None:
        nonlocal default, read_files, clears_all
        outside = replace_owned_region(replace_owned_region(source, KITTY, None), KITTY_KEYS, None)
        for line in outside.splitlines():
            tokens = line.split()
            if not tokens or tokens[0].startswith("#"):
                continue
            directive = tokens[0]
            if directive == "kitty_mod" and len(tokens) > 1:
                default = tokens[1]
            elif directive == "clear_all_shortcuts" and len(tokens) > 1:
                clears_all |= tokens[1].lower() in {"yes", "y", "true"}
            elif directive in {"geninclude", "envinclude"}:
                reports.append(
                    f"kitty: partial: {directive} is not followed; maps there are not checked"
                )
                # shortcut: the kitty region position after a user edit is not checked; moved below
                # a map the scan cannot read (geninclude, envinclude), the installer's map wins by
                # last-wins, as with phase 28's Alacritty region; upgrade in validate_kitty if a
                # user hits it.
            elif directive in {"include", "globinclude"} and len(tokens) > 1:
                if depth >= 8:
                    stopped.add("depth 8")
                    continue
                include = line.strip()[len(directive) :].strip()
                kitty_os = "macos" if platform_os == "macos" else "linux"
                include = include.replace("${KITTY_OS}", kitty_os).replace("$KITTY_OS", kitty_os)
                pattern = Path(os.path.expandvars(include)).expanduser()
                if not pattern.is_absolute():
                    pattern = base / pattern
                if directive == "globinclude":
                    remaining = max(0, 64 - read_files)
                    # shortcut: glob lists each matched directory once in full before islice caps
                    # it; kitty globs are small, upgrade to an os.scandir walk if a real config
                    # needs it.
                    matches = list(itertools.islice(glob.iglob(str(pattern)), remaining + 1))
                    if len(matches) > remaining:
                        stopped.add("64 files")
                    targets = sorted(matches)[:remaining]
                else:
                    targets = [str(pattern)]
                for target_name in targets:
                    try:
                        target = Path(target_name).resolve()
                    except (OSError, RuntimeError):
                        reports.append(
                            f"kitty: partial: {Path(target_name).name} could not be read; maps "
                            "there are not checked"
                        )
                        continue
                    if target in visited:
                        continue
                    if read_files >= 64:
                        stopped.add("64 files")
                        break
                    visited.add(target)
                    try:
                        data = read_capped(target, 1 << 20, follow_symlinks=True)
                        if data is None:
                            raise OSError("not readable")
                        included = data.decode("utf-8")
                    except (FileNotFoundError, NotADirectoryError):
                        continue
                    except (OSError, RuntimeError, UnicodeDecodeError):
                        reports.append(
                            f"kitty: partial: {target.name} could not be read; maps there are "
                            "not checked"
                        )
                        continue
                    read_files += 1
                    walk(included, target.parent, depth + 1)
            elif directive == "map":
                index = 1
                while index < len(tokens):
                    token = tokens[index]
                    if token.startswith("--"):
                        index += 2 if token in value_options else 1
                        continue
                    raw.append(token.split(">", 1)[0])
                    break

    walk(text, path.parent, 0)
    normalized_mod = kitty_chord(default, "ctrl+shift")
    for cap in sorted(stopped):
        reports.append(
            f"kitty: partial: include scan stopped at {cap}; maps beyond it are not checked"
        )
    return KittyScan(
        frozenset(kitty_chord(chord, normalized_mod) for chord in raw),
        normalized_mod,
        tuple(dict.fromkeys(reports)),
        clears_all,
    )


def kitty_maps(
    rows: Sequence[tuple[str, str]], scan: KittyScan
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    added: list[str] = []
    conflicts: list[str] = []
    for chord, line in rows:
        if kitty_chord(chord, scan.kitty_mod) in scan.taken:
            conflicts.append(f"kitty: partial: you already map {chord}")
        else:
            added.append(line)
    return tuple(added), tuple(conflicts)


def validate_kitty(text: str) -> None:
    lines = text.splitlines()
    begin = marker(KITTY_KEYS, ">>>")
    end = marker(KITTY_KEYS, "<<<")
    if begin not in lines or end not in lines:
        return
    for line in lines[lines.index(begin) + 1 : lines.index(end)]:
        if line.strip() and not line.strip().startswith("map "):
            raise TerminalShellError(
                "the kitty keys region would hold a line that is not a map; nothing written"
            )


GHOSTTY = "ghostty"
GHOSTTY_KEYS = "ghostty-keys"
GHOSTTY_CREATED = "terminal-ghostty-created"
GHOSTTY_INCLUDE_REPORT = (
    "ghostty: partial: you include other files (config-file); they are not followed"
)


def _nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def ghostty_config_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    """Mirror Ghostty v1.4.0 file_load.zig preferredDefaultFilePath."""
    xdg = xdg_config_home(home, environ) / "ghostty"
    preferred = next(
        (p for p in (xdg / "config.ghostty", xdg / "config") if _nonempty_file(p)),
        xdg / "config.ghostty",
    )
    if platform_os != "macos":
        return preferred
    support = home / "Library" / "Application Support" / "com.mitchellh.ghostty"
    return next(
        (
            p
            for p in (support / "config.ghostty", support / "config", preferred)
            if _nonempty_file(p)
        ),
        support / "config.ghostty",
    )


def ghostty_default_files(
    platform_os: str, home: Path, environ: Mapping[str, str]
) -> tuple[Path, ...]:
    xdg = xdg_config_home(home, environ) / "ghostty"
    files = (xdg / "config", xdg / "config.ghostty")
    if platform_os == "macos":
        support = home / "Library" / "Application Support" / "com.mitchellh.ghostty"
        files += (support / "config", support / "config.ghostty")
    return files


def ghostty_chord(binding: str) -> str | None:
    binding = binding.strip().lower()
    while any(
        binding.startswith(prefix) for prefix in ("all:", "global:", "unconsumed:", "performable:")
    ):
        binding = binding.split(":", 1)[1]
    trigger = binding.split("=", 1)[0].strip()
    if not trigger or ">" in trigger or "/" in trigger or trigger == "chain":
        return None
    parts = trigger.split("+")
    aliases = {"cmd": "super", "command": "super", "opt": "alt", "option": "alt", "control": "ctrl"}
    key = parts[-1].removeprefix("physical:").removeprefix("unicode:").removeprefix("key_")
    return "+".join((*sorted(aliases.get(part, part) for part in parts[:-1]), key))


@dataclass(frozen=True)
class GhosttyScan:
    user_command: bool
    config_file: bool
    taken: frozenset[str]
    clears: bool
    reports: tuple[str, ...]
    blocked: tuple[str, ...]


def scan_ghostty(platform_os: str, home: Path, environ: Mapping[str, str]) -> GhosttyScan:
    files = ghostty_default_files(platform_os, home, environ)
    target = ghostty_config_path(platform_os, home, environ)
    user_command = config_file = clears = False
    taken: set[str] = set()
    reports: list[str] = []
    blocked: list[str] = []
    for index, path in enumerate(files):
        try:
            data = read_capped(path, 1 << 20, follow_symlinks=True)
            if data is None:
                raise OSError("not a readable regular file")
            text = replace_owned_region(
                replace_owned_region(data.decode("utf-8"), GHOSTTY, None), GHOSTTY_KEYS, None
            )
        except (FileNotFoundError, NotADirectoryError):
            continue
        except (OSError, UnicodeDecodeError):
            if index < files.index(target):
                report = (
                    f"ghostty: partial: {path.name} could not be read and loads before "
                    f"{target.name}; nothing written"
                )
                blocked.append(report)
            else:
                report = (
                    f"ghostty: partial: {path.name} could not be read; "
                    "settings there are not checked"
                )
            reports.append(report)
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            if key == "command":
                user_command = True
            elif key == "config-file":
                config_file = True
            elif key == "keybind":
                # shortcut: clear before the target is refused too; narrow the scan if users hit it.
                if value in ("", "clear"):
                    clears = True
                elif (chord := ghostty_chord(value)) is not None:
                    taken.add(chord)
    return GhosttyScan(
        user_command,
        config_file,
        frozenset(taken),
        clears,
        tuple(dict.fromkeys(reports)),
        tuple(dict.fromkeys(blocked)),
    )


def validate_ghostty(text: str) -> None:
    lines = text.splitlines()
    for region, prefix, kind in (
        (GHOSTTY_KEYS, "keybind =", "keybind"),
        (GHOSTTY, "command =", "command"),
    ):
        begin, end = marker(region, ">>>"), marker(region, "<<<")
        if begin in lines and end in lines:
            for line in lines[lines.index(begin) + 1 : lines.index(end)]:
                if line.strip() and not line.strip().startswith(prefix):
                    raise TerminalShellError(
                        f"the Ghostty {region} region would hold a line that is not a {kind}; "
                        "nothing written"
                    )


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


@dataclass(frozen=True)
class Restored:
    lines: tuple[str, ...]
    confirmed: bool


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
