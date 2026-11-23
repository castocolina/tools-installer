"""iTerm2 Dynamic Profile and default-profile logic for the terminal keys row."""

from __future__ import annotations

import json
import plistlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Final, cast
from xml.parsers.expat import ExpatError

from installer.agent_settings import same_value
from installer.atomic import atomic_write_text
from installer.run import CommandError, run_output
from installer.terminal_regions import Restored, TerminalShellError, first_line, xdg_data_home

ITERM2_DOMAIN: Final = "com.googlecode.iterm2"
DEFAULT_GUID_KEY: Final = "Default Bookmark Guid"
CUSTOM_FOLDER_KEY: Final = "LoadPrefsFromCustomFolder"
ITERM2_GUID: Final = "6CB8584E-9B4C-4CF6-892A-D21E8AFE908C"
PROFILE_NAME: Final = "tools-installer"
PROFILE_FILE: Final = "tools-installer.json"
ITERM2_CREATED: Final = "terminal-iterm2-created"
FALLBACK_LOCALE: Final = "en_US.UTF-8"
LOCALE_ROOT: Final = Path("/usr/share/locale")
STATE_RECORD: Final = "terminal-iterm2-default"
MODIFIER_MASK: Final = 0x1E0000
OWN_ROWS: Final = (
    ("option+left", "0xf702-0x280000", {"Action": 10, "Text": "b"}),
    ("option+right", "0xf703-0x280000", {"Action": 10, "Text": "f"}),
)
# Records written before backlog 999.37 still carry this pair, so iterm2_profile_text drops it and
# a reconfigure rewrites the profile without it. A previous default that bound exactly this pair
# under exactly this key is indistinguishable from ours and is dropped too; iTerm2's own Cmd+K
# still clears.
RETIRED_ROWS: Final = (("cmd+k", "0x6b-0x100000", {"Action": 11, "Text": "0x0c"}),)


def color(red: float, green: float, blue: float) -> dict[str, object]:
    return {
        "Red Component": red,
        "Green Component": green,
        "Blue Component": blue,
        "Alpha Component": 1,
        "Color Space": "sRGB",
    }


BACKGROUND: Final = color(0.02, 0.05, 0.03)
FOREGROUND: Final = color(0.2, 0.62, 0.3)
BOLD: Final = color(0.35, 0.8, 0.45)
CURSOR: Final = color(0.35, 0.8, 0.45)
SELECTION: Final = color(0.1, 0.3, 0.15)


@dataclass(frozen=True)
class ProfileState:
    parent: str | None
    previous: str | None
    default_set: bool
    switched: bool
    rows: dict[str, object]


def profile_path(home: Path) -> Path:
    return home / "Library" / "Application Support" / "iTerm2" / "DynamicProfiles" / PROFILE_FILE


def parse_keystroke(key: str) -> tuple[int, int] | None:
    parts = key.split("-")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0], 16), int(parts[1], 16)
    except ValueError:
        return None


def keystroke_id(key: str) -> tuple[int, int] | None:
    parsed = parse_keystroke(key)
    return (parsed[0], parsed[1] & MODIFIER_MASK) if parsed else None


def merge_rows(parent: Mapping[str, object]) -> tuple[dict[str, object], tuple[str, ...]]:
    rows = dict(parent)
    clashes: list[str] = []
    for name, key, action in OWN_ROWS:
        matches = [
            value
            for parent_key, value in parent.items()
            if keystroke_id(parent_key) == keystroke_id(key)
        ]
        if not matches:
            rows[key] = action.copy()
        elif not all(same_value(value, action) for value in matches):
            clashes.append(name)
    return rows, tuple(clashes)


def parent_rows(plist_text: str, guid: str) -> dict[str, object] | None:
    try:
        document: object = plistlib.loads(plist_text.encode("utf-8"))
    except (ValueError, ExpatError):
        return None
    if not isinstance(document, dict):
        return None
    document = cast(dict[str, object], document)
    bookmarks = document.get("New Bookmarks")
    if not isinstance(bookmarks, list):
        return None
    for item in cast(list[object], bookmarks):
        if not isinstance(item, dict):
            continue
        profile = cast(dict[str, object], item)
        if profile.get("Guid") != guid:
            continue
        mapping = profile.get("Keyboard Map", {})
        if not isinstance(mapping, dict):
            return {}
        result: dict[str, object] = {}
        for key, value in cast(dict[str, object], mapping).items():
            # shortcut: plist data and dates are dropped; upgrade if a real profile needs them.
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                continue
            result[key] = value
        return result
    return None


def without_retired_rows(rows: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in rows.items()
        if not any(
            key == retired and same_value(value, action) for _, retired, action in RETIRED_ROWS
        )
    }


def iterm2_profile_text(state: ProfileState, *, recycle: bool, pin_locale: bool = False) -> str:
    profile: dict[str, object] = {
        "Background Color": BACKGROUND,
        "Bold Color": BOLD,
        "Cursor Color": CURSOR,
        "Foreground Color": FOREGROUND,
        "Selection Color": SELECTION,
        "Guid": ITERM2_GUID,
        "Name": PROFILE_NAME,
        "Keyboard Map": without_retired_rows(state.rows),
        "Use Separate Colors for Light and Dark Mode": False,
    }
    if recycle:
        profile["Custom Directory"] = "Recycle"
    if pin_locale:
        # 2 is iTerm2's "custom locale"; the default asks in a dialog on every new session.
        profile["Set Local Environment Vars"] = 2
        profile["Custom Locale"] = FALLBACK_LOCALE
    if state.parent is not None:
        profile["Dynamic Profile Parent GUID"] = state.parent
    return json.dumps({"Profiles": [profile]}, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def locale_needs_pin(root: Path = LOCALE_ROOT) -> bool:
    """True when the system region has no UNIX locale (en_CL), where iTerm2 stops on a dialog."""
    try:
        region = iterm2_defaults(("read", "-g", "AppleLocale")).strip()
    except CommandError:
        return False
    return bool(region) and not (root / f"{region}.UTF-8").exists()


def iterm2_proof(text: str) -> bool:
    try:
        doc: object = json.loads(text)
    except (ValueError, RecursionError):
        return False
    if not isinstance(doc, dict):
        return False
    profiles: object = cast(dict[str, object], doc).get("Profiles")
    return isinstance(profiles, list) and any(
        isinstance(item, dict) and cast(dict[str, object], item).get("Guid") == ITERM2_GUID
        for item in cast(list[object], profiles)
    )


def validate_iterm2(text: str) -> None:
    try:
        doc: object = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise TerminalShellError("the profile does not parse") from exc
    profiles: object = (
        cast(dict[str, object], doc).get("Profiles") if isinstance(doc, dict) else None
    )
    if not isinstance(profiles, list):
        raise TerminalShellError("the profile has no Profiles list")
    entries = cast(list[object], profiles)
    if len(entries) != 1:
        raise TerminalShellError("the profile file must hold exactly one profile")
    if (
        not isinstance(entries[0], dict)
        or cast(dict[str, object], entries[0]).get("Guid") != ITERM2_GUID
    ):
        raise TerminalShellError("the profile does not carry the installer's Guid")


def state_record(home: Path, environ: Mapping[str, str]) -> Path:
    return xdg_data_home(home, environ) / "tools-installer" / STATE_RECORD


def read_state(home: Path, environ: Mapping[str, str]) -> ProfileState | None:
    try:
        data: object = json.loads(state_record(home, environ).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None
    if not isinstance(data, dict):
        return None
    record = cast(dict[str, object], data)
    parent, previous = record.get("parent"), record.get("previous")
    default_set, switched, rows = (
        record.get("default_set"),
        record.get("switched"),
        record.get("rows"),
    )
    if (
        not {"parent", "previous", "default_set", "switched", "rows"} <= record.keys()
        or not (parent is None or isinstance(parent, str))
        or not (previous is None or isinstance(previous, str))
        or not isinstance(default_set, bool)
        or not isinstance(switched, bool)
        or not isinstance(rows, dict)
    ):
        return None
    return ProfileState(parent, previous, default_set, switched, cast(dict[str, object], rows))


def write_state(home: Path, environ: Mapping[str, str], state: ProfileState) -> None:
    path = state_record(home, environ)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(asdict(state), sort_keys=True, indent=2) + "\n")


def drop_state(home: Path, environ: Mapping[str, str]) -> None:
    state_record(home, environ).unlink(missing_ok=True)


_capture_failed: set[Path] = set()


def iterm2_defaults(argv: Sequence[str]) -> str:
    """The defaults seam that tests replace in tests/conftest.py."""
    return run_output(["/usr/bin/defaults", *argv], timeout=20)


def valid_guid(text: str) -> bool:
    return re.fullmatch(r"[0-9A-Fa-f]{8}-([0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}", text) is not None


def _read_preference(key: str) -> str | None:
    try:
        return iterm2_defaults(("read", ITERM2_DOMAIN, key)).strip()
    except CommandError as exc:
        if exc.returncode == 1 and "does not exist" in str(exc):
            return None
        raise


def read_default_guid() -> str | None:
    return _read_preference(DEFAULT_GUID_KEY)


def custom_prefs_folder() -> bool:
    return (_read_preference(CUSTOM_FOLDER_KEY) or "").lower() in ("1", "true")


def install_commands(current: str | None, ours: str) -> tuple[tuple[str, ...], ...]:
    return () if current == ours else (("write", ITERM2_DOMAIN, DEFAULT_GUID_KEY, "-string", ours),)


def restore_commands(
    recorded: str | None, current: str | None, ours: str
) -> tuple[tuple[str, ...], ...]:
    if current != ours:
        return ()
    if recorded is None:
        return (("delete", ITERM2_DOMAIN, DEFAULT_GUID_KEY),)
    return (("write", ITERM2_DOMAIN, DEFAULT_GUID_KEY, "-string", recorded),)


def hook_before_write(
    platform_os: str, home: Path, environ: Mapping[str, str], reconfigure: bool
) -> tuple[str, ...]:
    del platform_os
    path = state_record(home, environ)
    _capture_failed.discard(path)
    prior = read_state(home, environ)
    if reconfigure and prior is not None:
        return ()
    rows, _ = merge_rows({})
    record = ProfileState(None, None, False, False, rows)
    lines: list[str] = []
    try:
        current = read_default_guid()
        custom = custom_prefs_folder()
        if custom and prior is not None:
            _capture_failed.add(path)
            return (
                "iterm2: partial: iTerm2 loads its preferences from a custom "
                "folder; the default profile was not changed",
            )
        if current == ITERM2_GUID and prior is not None:
            record = prior
        elif current == ITERM2_GUID:
            pass
        elif current is not None and not valid_guid(current):
            lines.append(
                "iterm2: partial: your default profile id is not a GUID; the "
                "default was not changed"
            )
        else:
            record = ProfileState(current, current, not custom, False, rows)
            if current is not None:
                try:
                    parent = parent_rows(iterm2_defaults(("export", ITERM2_DOMAIN, "-")), current)
                except CommandError:
                    parent = None
                if parent is None:
                    lines.append(
                        "iterm2: partial: your previous default is a Dynamic Profile or "
                        "could not be read; its key mappings were not merged"
                    )
                else:
                    merged, clashes = merge_rows(parent)
                    record = replace(record, rows=merged)
                    lines.extend(f"iterm2: partial: you already bind {name}" for name in clashes)
        if custom:
            record = replace(record, default_set=False)
            lines.append(
                "iterm2: partial: iTerm2 loads its preferences from a custom "
                "folder; the default profile was not changed"
            )
    except CommandError as exc:
        lines.append(
            f"iterm2: partial: could not read your default profile "
            f"({first_line(exc)}); the default was not changed"
        )
        if prior is not None:
            _capture_failed.add(path)
            return tuple(lines)
    try:
        write_state(home, environ, record)
    except OSError as exc:
        _capture_failed.add(path)
        lines.append(
            f"iterm2: partial: could not record your previous default "
            f"({first_line(exc)}); the default was not changed"
        )
    return tuple(lines)


def hook_after_write(
    platform_os: str, home: Path, environ: Mapping[str, str], reconfigure: bool
) -> tuple[str, ...]:
    del platform_os
    record = read_state(home, environ)
    if (
        state_record(home, environ) in _capture_failed
        or record is None
        or not record.default_set
        or record.switched
    ):
        return ()
    try:
        current = read_default_guid()
    except CommandError as exc:
        return (
            f"iterm2: partial: could not read your default profile "
            f"({first_line(exc)}); the default was not changed",
        )
    if current == record.previous:
        try:
            for command in install_commands(current, ITERM2_GUID):
                iterm2_defaults(command)
        except CommandError as exc:
            return (
                f"iterm2: partial: could not set your default profile "
                f"({first_line(exc)}); a later reconfigure retries while your "
                f"default is still the previous one",
            )
        updated = replace(record, switched=True)
    elif current == ITERM2_GUID:
        updated = replace(record, switched=True)
    else:
        updated = replace(record, default_set=False)
    try:
        write_state(home, environ, updated)
    except OSError as exc:
        return (f"iterm2: partial: could not record the default switch ({first_line(exc)})",)
    if not updated.default_set:
        return (
            "iterm2: partial: you changed your default profile after the "
            "install; the installer's profile was not made your default (kept yours)",
        )
    if reconfigure and current == record.previous:
        return (
            "iterm2: your default profile is now tools-installer (retried "
            "after an earlier failure)",
        )
    return ()


def hook_switch_pending(platform_os: str, home: Path, environ: Mapping[str, str]) -> bool:
    del platform_os
    record = read_state(home, environ)
    if record is None or not record.default_set or record.switched:
        return False
    try:
        return read_default_guid() == record.previous
    except CommandError:
        return False


def hook_still_named(platform_os: str, home: Path, environ: Mapping[str, str]) -> bool:
    del platform_os
    record = read_state(home, environ)
    if record is None or not record.default_set:
        return False
    try:
        return read_default_guid() == ITERM2_GUID
    except CommandError:
        return False


def hook_restore(platform_os: str, home: Path, environ: Mapping[str, str], final: bool) -> Restored:
    del platform_os
    record = read_state(home, environ)
    try:
        current = read_default_guid()
    except CommandError as exc:
        return Restored(
            (
                f"iterm2: partial: could not read your default profile "
                f"({first_line(exc)}); set it in iTerm2 > Settings > Profiles",
            ),
            False,
        )
    lines: list[str] = []
    if current != ITERM2_GUID:
        if record is not None and record.default_set and current != record.previous:
            lines.append(
                "iterm2: partial: you changed your default profile after the install; kept yours"
            )
    elif (
        record is None
        or not record.default_set
        or (record.previous is not None and not valid_guid(record.previous))
    ):
        return Restored(
            (
                "iterm2: partial: your default profile is still tools-installer "
                "and your previous default could not be recovered; choose a "
                "default profile in iTerm2 > Settings > Profiles, then uninstall "
                "again",
            ),
            False,
        )
    else:
        try:
            custom = custom_prefs_folder()
        except CommandError:
            custom = True
        if custom:
            return Restored(
                (
                    "iterm2: partial: iTerm2 loads its preferences from a custom "
                    "folder; the default profile was not restored",
                ),
                False,
            )
        try:
            for command in restore_commands(record.previous, current, ITERM2_GUID):
                iterm2_defaults(command)
            current = read_default_guid()
        except CommandError as exc:
            return Restored(
                (
                    f"iterm2: partial: could not restore your default profile "
                    f"({first_line(exc)}); set it in iTerm2 > Settings > Profiles",
                ),
                False,
            )
        if current == ITERM2_GUID:
            return Restored(
                (
                    "iterm2: partial: your default profile still names tools-installer "
                    "after restoration; set it in iTerm2 > Settings > Profiles",
                ),
                False,
            )
        if not final:
            try:
                write_state(home, environ, replace(record, switched=False))
            except OSError as exc:
                return Restored(
                    (
                        f"iterm2: partial: could not update your record "
                        f"({first_line(exc)}); your previous default is restored; "
                        f"uninstall again to retry",
                    ),
                    False,
                )
    if final:
        try:
            drop_state(home, environ)
        except OSError as exc:
            lines.append(f"iterm2: partial: could not remove your record ({first_line(exc)})")
    return Restored(tuple(lines), True)
