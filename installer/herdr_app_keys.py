"""The herdr desktop app's keys data and pure logic."""

import json
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Final, cast

from installer.agent_settings import same_value
from installer.run import CommandError, run_output
from installer.terminal_regions import TerminalShellError, first_line, xdg_config_home

HERDR_APP_DEFAULTS_VERSION: Final = "0.1.16"
HERDR_APP_DEFAULTS_SHA256: Final[dict[str, str]] = {
    "keys.json": "d1831fe2e9a685abf5fd95c156f4425fcbc17f81919163955a3688a166ea269f",
    "keys.macos.json": "8728a5190aa2ef1609c08c0cb49cf31dd74ab7018944b6453d9f371570d023c0",
}
HERDR_APP_CREATED: Final = "terminal-herdr-app-created"
HERDR_APP_CLEAR: Final = "send:" + chr(12)  # The clear chord sends Ctrl+L (KEYS-03).
HERDR_APP_BIN_DIR: Final = "~/.local/bin"  # The script method's declared bin_dir.


def vendor_default(platform_os: str) -> str:
    name = "keys.macos.json" if platform_os == "macos" else "keys.json"
    folder = Path(__file__).parent / "vendor_defaults" / f"herdr-app-{HERDR_APP_DEFAULTS_VERSION}"
    return (folder / name).read_text(encoding="utf-8")


def herdr_app_keys_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    del platform_os
    direct = environ.get("HERDR_APP_HOME")
    folder = Path(direct) if direct else xdg_config_home(home, environ) / "herdr-app"
    return folder / "keys.json"


def clear_chord(platform_os: str) -> str:
    return "cmd-k" if platform_os == "macos" else "ctrl-shift-k"


def herdr_app_owned_keys(platform_os: str) -> tuple[tuple[tuple[str, str], str], ...]:
    return ((("terminal", clear_chord(platform_os)), HERDR_APP_CLEAR),)


def parse_app_version(output: str) -> str | None:
    match = re.search(r"\d+\.\d+\.\d+", output)
    return match.group(0) if match else None


def herdr_app_executable(platform_os: str) -> Path | None:
    if platform_os == "macos":
        # shortcut: PATH may find a shadowing binary; upgrade when the Mac cask layout is verified.
        found = shutil.which("herdr-app")
        return Path(found) if found else None
    executable = Path.home() / HERDR_APP_BIN_DIR.removeprefix("~/") / "herdr-app"
    return executable if executable.is_file() else None


def herdr_app_version(platform_os: str) -> str | None:
    """The version seam that tests replace in tests/conftest.py."""
    executable = herdr_app_executable(platform_os)
    if executable is None:
        return None
    try:
        return parse_app_version(run_output([str(executable), "--version"], timeout=20))
    except (CommandError, OSError):
        return None


def herdr_app_seed(platform_os: str) -> str:
    installed = herdr_app_version(platform_os)
    if installed == HERDR_APP_DEFAULTS_VERSION:
        return vendor_default(platform_os)
    raise TerminalShellError(
        f"partial: the installed herdr-app is {installed or 'unknown'} but the keys default "
        f"pinned here is for {HERDR_APP_DEFAULTS_VERSION}; keys.json was not created "
        "(the app writes its own default on first run)"
    )


def parse_chord(chord: str, platform_os: str) -> tuple[frozenset[str], str] | None:
    """Follow the app's Keystroke::parse; it accepts neither option nor platform as modifiers."""
    strokes = chord.split()
    if not strokes:
        return None
    stroke = strokes[0]
    if stroke == "-":
        parts = ["-"]
    elif stroke.endswith("--"):
        parts = [*stroke[:-2].split("-"), "-"]
    elif stroke.endswith("-"):
        return None
    else:
        parts = stroke.split("-")
    key = parts[-1]
    modifiers: set[str] = set()
    for part in parts[:-1]:
        modifier = part.lower()
        if modifier in {"cmd", "super", "win"}:
            modifier = "cmd"
        elif modifier == "secondary":
            modifier = "cmd" if platform_os == "macos" else "ctrl"
        elif modifier not in {"ctrl", "alt", "shift", "fn"}:
            return None
        modifiers.add(modifier)
    if len(key) == 1 and "A" <= key <= "Z":
        modifiers.add("shift")
    return frozenset(modifiers), key.lower()


def herdr_app_taken(
    platform_os: str,
    document: Mapping[str, object],
    key: tuple[tuple[str, str], str],
    recorded: tuple[tuple[tuple[str, str], str], ...],
) -> str | None:
    (section, chord), value = key
    ours = parse_chord(chord, platform_os)
    if ours is None:
        return None
    vendor = cast(dict[str, object], json.loads(vendor_default(platform_os)))
    for name, entries in document.items():
        if not isinstance(entries, dict):
            continue
        default_entries = vendor.get(name)
        defaults = (
            cast(dict[str, object], default_entries) if isinstance(default_entries, dict) else {}
        )
        for entry, current in cast(dict[object, object], entries).items():
            if not isinstance(entry, str) or parse_chord(entry, platform_os) != ours:
                continue
            if name == section:
                owned = entry == chord and (
                    same_value(current, value)
                    or any(
                        path == (section, chord) and same_value(current, old)
                        for path, old in recorded
                    )
                )
            else:
                owned = any(
                    parse_chord(default_chord, platform_os) == ours
                    and same_value(current, default_value)
                    for default_chord, default_value in defaults.items()
                )
            if not owned:
                return f"herdr-app: partial: you already bind {chord.replace('-', '+')}"
    return None


def validate_herdr_app(text: str) -> None:
    try:
        document: object = json.loads(text)
    except ValueError as exc:
        raise TerminalShellError(f"the keys file does not parse ({first_line(exc)})") from exc
    if not isinstance(document, dict):
        raise TerminalShellError(
            "the keys file must hold objects only: the top level is not an object"
        )
    for name, value in cast(dict[str, object], document).items():
        if not isinstance(value, dict):
            raise TerminalShellError(
                f"the keys file must hold objects only: {name} is not an object"
            )
