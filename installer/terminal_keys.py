"""One terminal keys mechanism keyed by registry tool id (28 D-01): apply, check, re-apply,
and strip a terminal's owned keys region the same way for every row."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Final, cast

from installer.agent_settings import (
    ABSENT,
    SettingsEditRefused,
    SettingsParseError,
    delete_if_unchanged,
    insert_key,
    key_held,
    lookup,
    parse_settings,
    read_settings,
    remove_created_dirs,
    remove_key,
    replace_value,
    same_value,
    write_if_unchanged,
)
from installer.atomic import atomic_write_text
from installer.herdr_app_keys import (
    HERDR_APP_CREATED,
    herdr_app_keys_path,
    herdr_app_owned_keys,
    herdr_app_seed,
    herdr_app_taken,
    validate_herdr_app,
    vendor_default,
)
from installer.iterm2_profile import (
    ITERM2_CREATED,
    ProfileState,
    hook_after_write,
    hook_before_write,
    hook_restore,
    hook_still_named,
    hook_switch_pending,
    iterm2_profile_text,
    iterm2_proof,
    locale_needs_pin,
    merge_rows,
    profile_path,
    read_state,
    validate_iterm2,
)
from installer.run import CommandError, run_output
from installer.terminal_regions import (
    ALACRITTY,
    ALACRITTY_CREATED,
    ALACRITTY_KEYS,
    GHOSTTY,
    GHOSTTY_CREATED,
    GHOSTTY_INCLUDE_REPORT,
    GHOSTTY_KEYS,
    KITTY,
    KITTY_CREATED,
    KITTY_KEYS,
    WEZTERM,
    WEZTERM_CREATED,
    WEZTERM_KEYS,
    WEZTERM_SKELETON,
    WEZTERM_UNVERIFIED,
    KeysPlan,
    Placement,
    Restored,
    TerminalShellError,
    alacritty_config_path,
    alacritty_keys_plan,
    commit_region,
    created_path_record,
    first_line,
    ghostty_chord,
    ghostty_config_path,
    ghostty_default_files,
    kitty_config_path,
    kitty_maps,
    replace_owned_region,
    scan_ghostty,
    scan_kitty,
    snapshot_text,
    strip_region,
    user_document,
    validate_ghostty,
    validate_kitty,
    validate_toml,
    validate_wezterm,
    wezterm_config_path,
    wezterm_disabled_chords,
    wezterm_keys_body,
    wezterm_readback,
    xdg_data_home,
)

KEYS_PENDING = "install tuning not applied"
CTRL_L: Final = "\x0c"  # The shared clear chord sends Ctrl+L (KEYS-03).


@dataclass(frozen=True)
class Vendor:
    """The vendor opens new tabs, windows or panes in the current directory; nothing is written."""

    note: str


@dataclass(frozen=True)
class Writes:
    """A fixed setting or a function returning lines, conflicts and notes."""

    snippet: str | Callable[[str, str, Path], KeysPlan]


@dataclass(frozen=True)
class NotApplicable:
    """The terminal has no tabs, windows or panes to open."""

    reason: str


SameDirectory = Vendor | Writes | NotApplicable


@dataclass(frozen=True)
class OwnedRegion:
    """A marker-delimited region owned by the installer."""

    region: str  # Marker name.
    comment: str = "#"  # Marker comment prefix.
    placement: Placement = Placement.END  # Where a new region goes.


@dataclass(frozen=True)
class DefaultProfile:
    before_write: Callable[[str, Path, Mapping[str, str], bool], tuple[str, ...]]
    after_write: Callable[[str, Path, Mapping[str, str], bool], tuple[str, ...]]
    restore: Callable[[str, Path, Mapping[str, str], bool], Restored]
    still_named: Callable[[str, Path, Mapping[str, str]], bool]
    switch_pending: Callable[[str, Path, Mapping[str, str]], bool]


@dataclass(frozen=True)
class WholeFile:
    proof: Callable[[str], bool]
    plan: Callable[[str, str, Path, Path, Mapping[str, str]], KeysPlan]
    hook: DefaultProfile | None = None


OwnedKey = tuple[tuple[str, str], str]


@dataclass(frozen=True)
class OwnedKeys:
    """Two-level keys in an application-owned JSON file; seed may refuse, pinned is pure."""

    seed: Callable[[str], str]
    pinned: Callable[[str], str]
    keys: Callable[[str, Path, Mapping[str, str]], tuple[OwnedKey, ...]]
    taken: Callable[[str, Mapping[str, object], OwnedKey, tuple[OwnedKey, ...]], str | None]


Ownership = OwnedRegion | WholeFile | OwnedKeys


def variant_plan(platform_os: str, text: str, path: Path) -> KeysPlan:
    """A whole-file row uses this no-op for the region renderer's plan field."""
    del platform_os, text, path
    return KeysPlan(None)


@dataclass(frozen=True)
class KeysRow:
    ownership: Ownership  # The ownership variant: a region, a whole file or owned keys.
    config_path: Callable[[str, Path, Mapping[str, str]], Path]  # Platform, home, environment.
    plan: Callable[[str, str, Path], KeysPlan]  # Platform, whole file and resolved config path.
    validate: Callable[[str], None]  # Validate the edited whole file.
    summary: str  # Success line when this row adds keys.
    created_record: str  # Created-file marker name.
    same_directory: SameDirectory
    sibling_regions: tuple[str, ...] = ()  # Other installer regions stripped with this tool.
    clear: str = CTRL_L  # Ctrl+L clears; other values name the vendor action.
    readback: Callable[[str, Path], tuple[str, ...]] | None = None  # Lines read back after a write.
    validate_on_status: bool = False  # Also validate an unchanged region in the status pass.
    bind_created_path: bool = (
        False  # Bind cleanup proof to the created path when resolution can change.
    )
    strip_files: Callable[[str, Path, Mapping[str, str]], tuple[Path, ...]] | None = None


def _alacritty_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    del platform_os
    return alacritty_config_path(home, environ)


def alacritty_keys_plan_for_document(document: Mapping[str, object], outside: str) -> KeysPlan:
    return alacritty_keys_plan(document, outside)


def alacritty_keys_plan_for_text(text: str) -> KeysPlan:
    return alacritty_keys_plan_for_document(*user_document(text))


def _alacritty_plan(platform_os: str, text: str, path: Path) -> KeysPlan:
    del platform_os, path
    return alacritty_keys_plan_for_text(text)


def clear_binding(row: KeysRow, platform_os: str) -> tuple[str, str]:
    """Return format-neutral clear chord and send value; non-macOS ids are Linux.

    Phase 29's rows are the first production callers; SPEC R3 proves it on a fixture row.
    """
    return ("cmd+k" if platform_os == "macos" else "ctrl+shift+k", row.clear)


def _render(row: KeysRow, platform_os: str, text: str, path: Path) -> KeysPlan:
    plan = row.plan(platform_os, text, path)
    if plan.refusal is None and isinstance(row.same_directory, Writes):
        snippet = row.same_directory.snippet
        if isinstance(snippet, str):
            return KeysPlan(
                "\n\n".join(part for part in (plan.body, snippet) if part),
                plan.conflicts,
                notes=plan.notes,
            )
        extra = snippet(platform_os, text, path)
        bodies = tuple(part for part in (plan.body, extra.body) if part)
        return KeysPlan(
            "\n\n".join(bodies) or None,
            (*plan.conflicts, *extra.conflicts),
            extra.refusal,
            (*plan.notes, *extra.notes),
        )
    return plan


def _kitty_clear(platform_os: str) -> tuple[str, str]:
    chord, send = clear_binding(TERMINAL_KEYS["kitty"], platform_os)
    escaped = "".join(f"\\x{ord(character):02x}" for character in send)
    prefix = "" if platform_os == "macos" else "--allow-fallback=shifted,ascii "
    return chord, f"map {prefix}{chord} send_text all {escaped}"


def _kitty_plan(platform_os: str, text: str, path: Path) -> KeysPlan:
    scan = scan_kitty(text, path, platform_os)
    if scan.clears_all:
        return KeysPlan(
            None, refusal="you set clear_all_shortcuts yes, which would clear these keys"
        )
    rows: list[tuple[str, str]] = []
    if platform_os == "macos":
        rows.extend(
            (
                ("opt+left", "map opt+left send_text all \\x1bb"),
                ("opt+right", "map opt+right send_text all \\x1bf"),
            )
        )
    chord, clear_line = _kitty_clear(platform_os)
    rows.append((chord, clear_line))
    added, conflicts = kitty_maps(rows, scan)
    notes: list[str] = []
    if clear_line in added:
        if platform_os == "macos":
            notes.append(
                "kitty: cmd+k now clears the screen and scrollback; it was "
                "clear_terminal to_cursor."
            )
        elif scan.kitty_mod == "ctrl+shift":
            notes.append(
                "kitty: ctrl+shift+k now clears the screen and scrollback; it was "
                "scroll_line_up, and ctrl+shift+up still scrolls."
            )
    if added and not path.exists():
        notes.append(
            "kitty: restart kitty or press ctrl+cmd+, if it was running before kitty.conf existed."
            if platform_os == "macos"
            else "kitty: restart kitty or press ctrl+shift+f5 if it was running before "
            "kitty.conf existed."
        )
    return KeysPlan("\n".join(added) or None, (*scan.reports, *conflicts), notes=tuple(notes))


def _ghostty_plan(platform_os: str, text: str, path: Path) -> KeysPlan:
    del text, path
    # shortcut: plan lacks home and environment; thread them through KeysRow.plan to generalize.
    scan = scan_ghostty(platform_os, Path.home(), os.environ)
    if scan.blocked:
        return KeysPlan(None, refusal=scan.blocked[0])
    reports = scan.reports
    if scan.config_file and platform_os == "macos":
        reports = (*reports, GHOSTTY_INCLUDE_REPORT)
    if scan.clears:
        return KeysPlan(
            None, reports, refusal="you set keybind = clear, which would clear these keys"
        )
    chord, send = clear_binding(TERMINAL_KEYS["ghostty"], platform_os)
    trigger = "super+k" if chord == "cmd+k" else chord
    if ghostty_chord(f"{trigger}=x") in scan.taken:
        return KeysPlan(None, (*reports, f"ghostty: partial: you already bind {trigger}"))
    escaped = "".join(f"\\x{ord(character):02x}" for character in send)
    notes = (
        ("ghostty: cmd+k now sends Ctrl+L; it was clear_screen.",) if platform_os == "macos" else ()
    )
    return KeysPlan(f"keybind = {trigger}=text:{escaped}", reports, notes=notes)


def _kitty_cwd(platform_os: str, text: str, path: Path) -> KeysPlan:
    scan = scan_kitty(text, path, platform_os)
    prefix = "cmd" if platform_os == "macos" else "kitty_mod"
    rows = (
        (f"{prefix}+t", f"map --allow-fallback=shifted,ascii {prefix}+t new_tab_with_cwd"),
        (f"{prefix}+enter", f"map {prefix}+enter new_window_with_cwd"),
        (f"{prefix}+n", f"map --allow-fallback=shifted,ascii {prefix}+n new_os_window_with_cwd"),
    )
    added, conflicts = kitty_maps(rows, scan)
    notes = (
        (
            "kitty: new_tab_with_cwd, new_window_with_cwd and new_os_window_with_cwd "
            "replace new_tab, new_window and new_os_window on those chords.",
        )
        if added
        else ()
    )
    return KeysPlan("\n".join(added) or None, conflicts, notes=notes)


def _wezterm_rows(platform_os: str) -> tuple[tuple[str, str, str], ...]:
    chord, send = clear_binding(TERMINAL_KEYS[WEZTERM], platform_os)
    clear = ("k", "SUPER", send) if chord == "cmd+k" else ("k", "CTRL|SHIFT", send)
    return (
        (("LeftArrow", "OPT", "\x1bb"), ("RightArrow", "OPT", "\x1bf"), clear)
        if platform_os == "macos"
        else (clear,)
    )


def _wezterm_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    del platform_os
    return wezterm_config_path(home, environ)


def _wezterm_plan(platform_os: str, text: str, path: Path) -> KeysPlan:
    del path
    rows = _wezterm_rows(platform_os)
    disabled = wezterm_disabled_chords(text, rows)
    return KeysPlan(wezterm_keys_body(rows), tuple(line for _, line in disabled))


def wezterm_show_keys(path: Path) -> str | None:
    """The read-back seam that tests replace in tests/conftest.py."""
    binary = which("wezterm")
    return (
        run_output([binary, "--config-file", str(path), "show-keys", "--lua"], timeout=20)
        if binary
        else None
    )


def _wezterm_readback(platform_os: str, path: Path) -> tuple[str, ...]:
    try:
        output = wezterm_show_keys(path)
    except CommandError:
        return (WEZTERM_UNVERIFIED,)
    if output is None:
        return ()
    rows = _wezterm_rows(platform_os)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    reported = (chord for chord, _ in wezterm_disabled_chords(text, rows))
    return wezterm_readback(output, rows, frozenset(reported))


def _iterm2_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    del platform_os, environ
    return profile_path(home)


def _iterm2_plan(
    platform_os: str, text: str, path: Path, home: Path, environ: Mapping[str, str]
) -> KeysPlan:
    del platform_os, text, path
    state = read_state(home, environ) or ProfileState(None, None, False, False, merge_rows({})[0])
    pin = locale_needs_pin()
    return KeysPlan(
        iterm2_profile_text(
            state,
            recycle=isinstance(TERMINAL_KEYS["iterm2"].same_directory, Writes),
            pin_locale=pin,
        ),
        notes=(
            *(
                (
                    "iterm2: your system region has no UNIX locale, so the profile sets LANG to "
                    "en_US.UTF-8 instead of asking in a dialog.",
                )
                if pin
                else ()
            ),
            "iterm2: changes made in the iTerm2 settings window do not stick (a Dynamic Profile).",
            "iterm2: iTerm2 skips a Dynamic Profiles file it cannot parse and reports it.",
            "iterm2: iTerm2 quits when it is removed; uninstall it from another terminal "
            "so the profile file is deleted with it.",
        ),
    )


def _herdr_app_keys(
    platform_os: str, home: Path, environ: Mapping[str, str]
) -> tuple[OwnedKey, ...]:
    del home, environ
    return herdr_app_owned_keys(platform_os)


def _herdr_app_plan(platform_os: str, text: str, path: Path) -> KeysPlan:
    del text, path
    note = (
        "herdr-app: cmd+k now sends Ctrl+L in terminals."
        if platform_os == "macos"
        else "herdr-app: ctrl+shift+k now clears the screen and scrollback in terminals; "
        "it was the picker (mod.open:picker), which stays in the palette (ctrl+shift+p) "
        "and outside terminals."
    )
    return KeysPlan(
        None,
        notes=(
            note,
            "herdr-app: the app stops adding new default shortcuts to a "
            "keys.json that was edited; add new vendor defaults by hand after an update.",
        ),
    )


TERMINAL_KEYS: Final[dict[str, KeysRow]] = {
    "alacritty": KeysRow(
        ownership=OwnedRegion(ALACRITTY_KEYS),
        config_path=_alacritty_path,
        plan=_alacritty_plan,
        validate=validate_toml,
        summary=(
            "Alacritty keys: Alt+Left and Alt+Right move by word, "
            "Control+Shift+K clears the screen and scrollback."
        ),
        created_record=ALACRITTY_CREATED,
        same_directory=Vendor(
            "2026-11-19, upstream CHANGELOG: SpawnNewInstance opens in the foreground process's "
            "working directory on Unix and macOS; CreateNewWindow is unverified. The installer "
            "writes nothing."
        ),
        sibling_regions=(ALACRITTY,),
    ),
    "kitty": KeysRow(
        ownership=OwnedRegion(KITTY_KEYS, "#", Placement.TOP),
        config_path=kitty_config_path,
        plan=_kitty_plan,
        validate=validate_kitty,
        summary=(
            "kitty keys: the clear chord sends Ctrl+L (screen and scrollback), Option+Left and "
            "Option+Right move by word on macOS, and new tabs and windows open in the current "
            "directory."
        ),
        created_record=KITTY_CREATED,
        same_directory=Writes(_kitty_cwd),
        sibling_regions=(KITTY,),
        bind_created_path=True,
    ),
    "wezterm": KeysRow(
        ownership=OwnedRegion(WEZTERM_KEYS, "--", Placement.BEFORE_RETURN),
        config_path=_wezterm_path,
        plan=_wezterm_plan,
        validate=validate_wezterm,
        summary=(
            "WezTerm keys: the clear chord sends Ctrl+L (screen and scrollback), and Option+Left "
            "and Option+Right move by word on macOS, unless your config.keys already binds them."
        ),
        created_record=WEZTERM_CREATED,
        same_directory=Vendor(
            "2026-11-20, wezterm source at tag 20240203-110809-5046fc22 (spawn.rs, localpane.rs): "
            "SpawnTab and SpawnWindow open in the active pane's working directory (OSC 7, else "
            "the process cwd); verified live in a disposable container (29 D-07). "
            "The installer writes nothing."
        ),
        sibling_regions=(WEZTERM,),
        validate_on_status=True,
        bind_created_path=True,
        readback=_wezterm_readback,
    ),
    "ghostty": KeysRow(
        ownership=OwnedRegion(GHOSTTY_KEYS, "#", Placement.TOP),
        config_path=ghostty_config_path,
        plan=_ghostty_plan,
        validate=validate_ghostty,
        summary=(
            "Ghostty keys: the clear chord sends Ctrl+L (screen and scrollback); "
            "new tabs, windows and splits already open in the current directory."
        ),
        created_record=GHOSTTY_CREATED,
        same_directory=Vendor(
            "2026-11-20, Ghostty Config.zig v1.4.0:2086-2099: window-, tab- and "
            "split-inherit-working-directory default to true and need shell integration, "
            "which works with the installer's command; a user's shell-integration = none "
            "is theirs. "
            "The installer writes nothing."
        ),
        sibling_regions=(GHOSTTY,),
        bind_created_path=True,
        strip_files=ghostty_default_files,
    ),
    "iterm2": KeysRow(
        ownership=WholeFile(
            proof=iterm2_proof,
            plan=_iterm2_plan,
            hook=DefaultProfile(
                before_write=hook_before_write,
                after_write=hook_after_write,
                restore=hook_restore,
                still_named=hook_still_named,
                switch_pending=hook_switch_pending,
            ),
        ),
        config_path=_iterm2_path,
        plan=variant_plan,
        validate=validate_iterm2,
        summary=(
            "iTerm2 profile: tools-installer (Option+Left and Option+Right move by word with "
            "Option left Normal, iTerm2's own Cmd+K clears the screen and the scrollback, "
            "new tabs, windows and panes open in the current directory); it becomes your "
            "default profile unless a partial line says otherwise."
        ),
        created_record=ITERM2_CREATED,
        same_directory=Writes('"Custom Directory": "Recycle"'),
        clear="Clear Buffer",
    ),
    "herdr-app": KeysRow(
        ownership=OwnedKeys(
            seed=herdr_app_seed, pinned=vendor_default, keys=_herdr_app_keys, taken=herdr_app_taken
        ),
        config_path=herdr_app_keys_path,
        plan=_herdr_app_plan,
        validate=validate_herdr_app,
        summary=(
            "herdr-app keys: the clear chord (ctrl+shift+k on Linux, cmd+k on macOS) sends Ctrl+L "
            "(screen and scrollback) in terminals unless you already bind it; new tabs and splits "
            "already open in the current directory."
        ),
        created_record=HERDR_APP_CREATED,
        same_directory=Vendor(
            "2026-11-21, herdr-app v0.1.16 README and defaults/AGENTS.md: new tabs and splits "
            "open in the current directory; new windows are unverified. "
            "The installer writes nothing."
        ),
        bind_created_path=True,
    ),
}


def _record(tool_id: str, home: Path, environ: Mapping[str, str]) -> Path:
    return xdg_data_home(home, environ) / "tools-installer" / f"terminal-tuning-{tool_id}"


def _created_marker(row: KeysRow, home: Path, environ: Mapping[str, str]) -> Path:
    return xdg_data_home(home, environ) / "tools-installer" / row.created_record


def _apply_whole_file(
    row: KeysRow,
    whole: WholeFile,
    tool_id: str,
    platform_os: str,
    home: Path,
    environ: Mapping[str, str],
    *,
    skip_recorded: bool,
) -> tuple[tuple[str, ...], str | None]:
    record = _record(tool_id, home, environ)
    recorded = skip_recorded and record.exists()
    path = row.config_path(platform_os, home, environ)
    marker = _created_marker(row, home, environ)
    # shortcut: a symlink swap after this check is possible; use O_NOFOLLOW if the folder is shared.
    if path.is_symlink():
        return ((), None) if recorded else ((), f"{path.name} is a symlink; left as it is")
    try:
        before = read_settings(path)
        text = snapshot_text(before)
        if before is not None and not (marker.exists() and whole.proof(text)):
            return (
                ((), None)
                if recorded
                else ((), f"{path.name} is not the installer's; left as it is")
            )
        if (
            recorded
            and before is None
            and not (whole.hook and whole.hook.still_named(platform_os, home, environ))
        ):
            return (), None
        plan = whole.plan(platform_os, text, path, home, environ)
    except OSError as exc:
        return ((), None) if recorded else ((), first_line(exc))
    if plan.refusal is not None:
        return ((), None) if recorded else ((), plan.refusal)
    hook = whole.hook
    before_lines = hook.before_write(platform_os, home, environ, skip_recorded) if hook else ()
    if hook:
        try:
            plan = whole.plan(platform_os, text, path, home, environ)
        except OSError as exc:
            return before_lines, first_line(exc)
        if plan.refusal is not None:
            return before_lines, plan.refusal
    changed = plan.body is not None and plan.body != text
    if changed and plan.body is not None:
        try:
            # shortcut: interrupted writes leave an unowned file; upgrade if interruptions occur.
            commit_region(
                path,
                before,
                text,
                plan.body,
                validate=row.validate,
                write=True,
                created_marker=marker,
                home=home,
                bind_path=row.bind_created_path,
            )
            record.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(record, "written\n")
        except OSError as exc:
            return (), first_line(exc)
    after_lines = hook.after_write(platform_os, home, environ, skip_recorded) if hook else ()
    lines = (row.summary, *plan.notes, *plan.conflicts) if changed else ()
    return (*lines, *before_lines, *after_lines), None


def _pending_whole_file(
    row: KeysRow,
    whole: WholeFile,
    tool_id: str,
    platform_os: str,
    home: Path,
    environ: Mapping[str, str],
) -> str | None:
    recorded = _record(tool_id, home, environ).exists()
    path = row.config_path(platform_os, home, environ)
    if path.is_symlink():
        return None if recorded else f"{path.name} is a symlink; left as it is"
    try:
        before = read_settings(path)
        text = snapshot_text(before)
        if before is None:
            if not recorded or (whole.hook and whole.hook.still_named(platform_os, home, environ)):
                return KEYS_PENDING
            return None
        if not (_created_marker(row, home, environ).exists() and whole.proof(text)):
            return None if recorded else f"{path.name} is not the installer's; left as it is"
        if not recorded:
            return KEYS_PENDING
        plan = whole.plan(platform_os, text, path, home, environ)
        if plan.refusal is None and plan.body is not None and plan.body != text:
            return KEYS_PENDING
        if whole.hook and whole.hook.switch_pending(platform_os, home, environ):
            return KEYS_PENDING
    except OSError as exc:
        return None if recorded else first_line(exc)
    return None


def _strip_whole_file(
    row: KeysRow,
    whole: WholeFile,
    tool_id: str,
    platform_os: str,
    home: Path,
    environ: Mapping[str, str],
) -> tuple[str, ...]:
    path = row.config_path(platform_os, home, environ)
    marker = _created_marker(row, home, environ)
    restored = (
        whole.hook.restore(platform_os, home, environ, True) if whole.hook else Restored((), True)
    )
    warnings = list(restored.lines)
    if not restored.confirmed:
        warnings.append(
            f"{tool_id}: {path.name} kept because the default profile was not restored; "
            "reinstall the tool and uninstall it again to retry"
        )
        return tuple(warnings)
    try:
        if path.is_symlink():
            warnings.append(f"{tool_id}: {path.name} is a symlink; left as it is")
            return tuple(warnings)
        before = read_settings(path)
        if before is not None:
            if marker.exists() and whole.proof(snapshot_text(before)):
                directories = tuple(marker.read_text(errors="replace").splitlines()[1:])
                delete_if_unchanged(path, before)
                remove_created_dirs(directories, home)
            else:
                warnings.append(f"{tool_id}: {path.name} is not the installer's; left as it is")
        _record(tool_id, home, environ).unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        created_path_record(marker).unlink(missing_ok=True)
    except OSError as exc:
        warnings.append(f"{tool_id}: {path.name}: {first_line(exc)}")
    return tuple(warnings)


@dataclass(frozen=True)
class _OwnedRecord:
    keys: tuple[tuple[str, str, str], ...] = ()
    deleted: tuple[tuple[str, str], ...] = ()
    path: str | None = None


def _string_entry(value: object, size: int) -> bool:
    if not isinstance(value, list):
        return False
    items = cast(list[object], value)
    return len(items) == size and all(isinstance(item, str) for item in items)


def _owned_record(path: Path) -> _OwnedRecord | None:
    try:
        data: object = json.loads(path.read_text())
        if not isinstance(data, dict):
            return None
        obj = cast(dict[str, object], data)
        keys = obj.get("keys")
        deleted = obj.get("deleted")
        name = obj.get("path")
        if not isinstance(keys, list) or not isinstance(deleted, list) or not isinstance(name, str):
            return None
        key_items = cast(list[object], keys)
        deleted_items = cast(list[object], deleted)
        if not all(_string_entry(x, 3) for x in key_items):
            return None
        if not all(_string_entry(x, 2) for x in deleted_items):
            return None
        triples = [cast(list[str], x) for x in key_items]
        pairs = [cast(list[str], x) for x in deleted_items]
        return _OwnedRecord(
            tuple((x[0], x[1], x[2]) for x in triples), tuple((x[0], x[1]) for x in pairs), name
        )
    except FileNotFoundError:
        return None if path.is_symlink() else _OwnedRecord()
    except (OSError, ValueError):
        return None


# shortcut: a single-path ledger forgets old paths; use one ledger per path if moves become common.
def _write_owned_record(
    record: Path, path: Path, keys: list[tuple[str, str, str]], deleted: list[tuple[str, str]]
) -> None:
    text = (
        json.dumps(
            {
                "deleted": sorted(list(item) for item in deleted),
                "keys": sorted(list(item) for item in keys),
                "path": str(path),
            },
            sort_keys=True,
        )
        + "\n"
    )
    try:
        if record.read_text() == text:
            return
    except FileNotFoundError:
        pass
    record.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(record, text)


def _parse_owned(text: str) -> dict[str, object]:
    try:
        return parse_settings(text, "json")
    except SettingsParseError as exc:
        raise TerminalShellError("the file does not parse; left as it is") from exc


def _apply_owned_keys(
    row: KeysRow,
    owned: OwnedKeys,
    tool_id: str,
    platform_os: str,
    home: Path,
    environ: Mapping[str, str],
    *,
    skip_recorded: bool,
) -> tuple[tuple[str, ...], str | None]:
    path = row.config_path(platform_os, home, environ)
    record = _record(tool_id, home, environ)
    old = _owned_record(record)
    if old is None:
        return (f"{tool_id}: the ownership record is unreadable; left as it is",), None
    if old.path is not None and old.path != str(path):
        old = _OwnedRecord()
        recorded = False
    else:
        recorded = skip_recorded and record.exists()
    if path.is_symlink():
        return ((), None) if recorded else ((), f"{path.name} is a symlink; left as it is")
    try:
        before = read_settings(path)
        original = snapshot_text(before)
        if recorded and not original.strip():
            return (), None
        text = original if original.strip() else owned.seed(platform_os)
        if tool_id == "herdr-app":
            try:
                parsed: object = json.loads(text)
            except ValueError:
                pass
            else:
                if not isinstance(parsed, dict):
                    row.validate(text)
        document = _parse_owned(text)
        row.validate(text)
    except OSError as exc:
        return ((), None) if recorded else ((), first_line(exc))
    held = {(s, k): v for s, k, v in old.keys}
    old_entries = tuple(((s, k), v) for s, k, v in old.keys)
    written: list[tuple[str, str, str]] = []
    deleted: list[tuple[str, str]] = []
    conflicts: list[str] = []
    changed = False
    try:
        for key, value in owned.keys(platform_os, home, environ):
            current = lookup(document, key)
            prior = held.get(key)
            if prior is not None and same_value(current, prior):
                if not same_value(prior, value):
                    text = replace_value(text, "json", key, value)
                    changed = True
                written.append((*key, value))
            elif current is ABSENT and (prior is not None or key in old.deleted) and skip_recorded:
                deleted.append(key)
            else:
                line = owned.taken(platform_os, document, (key, value), old_entries)
                if line is not None:
                    conflicts.append(line)
                elif current is ABSENT:
                    text = insert_key(text, "json", key, value).text
                    written.append((*key, value))
                    changed = True
            document = _parse_owned(text)
        commit_region(
            path,
            before,
            original,
            text,
            validate=row.validate,
            write=True,
            created_marker=_created_marker(row, home, environ),
            home=home,
            bind_path=row.bind_created_path,
        )
        _write_owned_record(record, path, written, deleted)
    except (OSError, SettingsEditRefused) as exc:
        return (), first_line(exc)
    notes = row.plan(platform_os, original, path).notes if changed else ()
    return ((row.summary, *notes, *conflicts) if changed else tuple(conflicts)), None


def _pending_owned_keys(
    row: KeysRow,
    owned: OwnedKeys,
    tool_id: str,
    platform_os: str,
    home: Path,
    environ: Mapping[str, str],
) -> str | None:
    path = row.config_path(platform_os, home, environ)
    record = _record(tool_id, home, environ)
    old = _owned_record(record) or _OwnedRecord()
    recorded = record.exists() and (old.path is None or old.path == str(path))
    if path.is_symlink():
        return None if recorded else f"{path.name} is a symlink; left as it is"
    try:
        before = read_settings(path)
        text = snapshot_text(before)
        if not text.strip():
            return None if recorded else KEYS_PENDING
        document = _parse_owned(text)
        row.validate(text)
        if not recorded:
            return KEYS_PENDING
        wanted = dict(owned.keys(platform_os, home, environ))
        for section, chord, value in old.keys:
            key = (section, chord)
            if (
                key in wanted
                and same_value(lookup(document, key), value)
                and not same_value(value, wanted[key])
            ):
                return KEYS_PENDING
    except OSError as exc:
        return None if recorded else first_line(exc)
    return None


def _strip_owned_keys(
    row: KeysRow,
    owned: OwnedKeys,
    tool_id: str,
    platform_os: str,
    home: Path,
    environ: Mapping[str, str],
) -> tuple[str, ...]:
    path = row.config_path(platform_os, home, environ)
    record = _record(tool_id, home, environ)
    old = _owned_record(record)
    if old is None:
        return (f"{tool_id}: the ownership record is unreadable; left as it is",)
    marker = _created_marker(row, home, environ)
    sidecar = created_path_record(marker)
    if old.path is not None and old.path != str(path):
        return (
            f"{tool_id}: edited keys were recorded for {old.path}, "
            "not the file now resolved; left alone",
        )
    if path.is_symlink():
        return (f"{tool_id}: {path.name} is a symlink; left as it is",)
    try:
        if row.bind_created_path and marker.exists():
            bound = sidecar.read_text(errors="replace") if sidecar.exists() else None
            if bound != f"{path}\n":
                shown = bound.removesuffix("\n") if bound is not None else "an unrecorded path"
                return (
                    f"{tool_id}: created config at {shown} is not the file now resolved; "
                    "left alone",
                )
        before = read_settings(path)
        if before is not None:
            original = snapshot_text(before)
            text = original
            document = _parse_owned(text)
            for section, chord, value in old.keys:
                key = (section, chord)
                if key_held(lookup(document, key), value):
                    text = remove_key(text, "json", key)
                    document = _parse_owned(text)
                    if document.get(section) == {}:
                        text = remove_key(text, "json", (section,))
                        document = _parse_owned(text)
            if marker.exists() and text == owned.pinned(platform_os):
                directories = tuple(marker.read_text(errors="replace").splitlines()[1:])
                delete_if_unchanged(path, before)
                remove_created_dirs(directories, home)
            elif text != original:
                write_if_unchanged(path, before, text)
        record.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
    except (OSError, SettingsEditRefused) as exc:
        return (f"{tool_id}: {first_line(exc)}",)
    return ()


def before_removal_terminal_keys(
    row: KeysRow,
    tool_id: str,
    platform_os: str,
    home: Path,
    environ: Mapping[str, str],
) -> Restored:
    """Restore a default profile before removal; callers must refuse if unconfirmed."""
    del tool_id
    ownership = row.ownership
    if isinstance(ownership, WholeFile) and ownership.hook:
        return ownership.hook.restore(platform_os, home, environ, False)
    return Restored((), True)


def apply_terminal_keys(
    row: KeysRow,
    tool_id: str,
    platform_os: str,
    home: Path,
    environ: Mapping[str, str],
    *,
    skip_recorded: bool,
) -> tuple[tuple[str, ...], str | None]:
    """Write the terminal's keys region, then its written-once record. Returns (lines, refusal).

    `skip_recorded` (RECONFIGURE) rewrites a present, stale recorded region (28 D-06); a region
    the user deleted stays deleted. Nothing is written when the file cannot take the region."""
    ownership = row.ownership
    if isinstance(ownership, WholeFile):
        return _apply_whole_file(
            row, ownership, tool_id, platform_os, home, environ, skip_recorded=skip_recorded
        )
    if isinstance(ownership, OwnedKeys):
        return _apply_owned_keys(
            row, ownership, tool_id, platform_os, home, environ, skip_recorded=skip_recorded
        )
    record = _record(tool_id, home, environ)
    recorded = skip_recorded and record.exists()
    path = row.config_path(platform_os, home, environ)
    try:
        before = read_settings(path)
        text = snapshot_text(before)
        plan = _render(row, platform_os, text, path)
        body = "" if recorded and plan.body is None and plan.conflicts else plan.body
        updated = replace_owned_region(
            text,
            ownership.region,
            body,
            comment=ownership.comment,
            placement=ownership.placement,
        )
        region_present = (
            replace_owned_region(text, ownership.region, None, comment=ownership.comment) != text
        )
    except OSError as exc:
        return ((), None) if recorded else ((), first_line(exc))
    if plan.refusal is not None:
        if recorded:
            return (), None
        return (), plan.refusal
    if recorded and (not region_present or updated == text):
        return (), None
    try:
        commit_region(
            path,
            before,
            text,
            updated,
            validate=row.validate,
            write=True,
            created_marker=_created_marker(row, home, environ),
            home=home,
            bind_path=row.bind_created_path,
        )
        record.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(record, "written\n")
    except OSError as exc:
        return (), first_line(exc)
    readback = row.readback(platform_os, path) if row.readback is not None else ()
    added = (row.summary, *plan.notes) if plan.body is not None else ()
    return (*added, *plan.conflicts, *readback), None


def terminal_keys_pending(
    row: KeysRow, tool_id: str, platform_os: str, home: Path, environ: Mapping[str, str]
) -> str | None:
    """Pending means never applied; a present region differing from its current render is drift."""
    ownership = row.ownership
    if isinstance(ownership, WholeFile):
        return _pending_whole_file(row, ownership, tool_id, platform_os, home, environ)
    if isinstance(ownership, OwnedKeys):
        return _pending_owned_keys(row, ownership, tool_id, platform_os, home, environ)
    recorded = _record(tool_id, home, environ).exists()
    present = False
    try:
        path = row.config_path(platform_os, home, environ)
        text = snapshot_text(read_settings(path))
        present = (
            replace_owned_region(text, ownership.region, None, comment=ownership.comment) != text
        )
        if recorded and not present:
            return None
        plan = _render(row, platform_os, text, path)
        if plan.refusal is not None and not recorded:
            return plan.refusal
        if not present and ownership.placement is Placement.BEFORE_RETURN and plan.body is not None:
            replace_owned_region(
                text,
                ownership.region,
                plan.body,
                comment=ownership.comment,
                placement=ownership.placement,
            )
        if present:
            body = "" if plan.body is None and plan.conflicts else plan.body
            updated = replace_owned_region(
                text,
                ownership.region,
                body,
                comment=ownership.comment,
                placement=ownership.placement,
            )
            if plan.refusal is None and updated != text:
                return KEYS_PENDING
            if plan.refusal is None and row.validate_on_status:
                try:
                    row.validate(text)
                except TerminalShellError as exc:
                    return first_line(exc)
            return None
    except OSError as exc:
        return None if recorded or present else first_line(exc)
    return plan.refusal or KEYS_PENDING


def strip_terminal_keys(
    row: KeysRow, tool_id: str, platform_os: str, home: Path, environ: Mapping[str, str]
) -> tuple[str, ...]:
    """Remove the tool's owned regions and record; the config remains unless created by us."""
    ownership = row.ownership
    if isinstance(ownership, WholeFile):
        return _strip_whole_file(row, ownership, tool_id, platform_os, home, environ)
    if isinstance(ownership, OwnedKeys):
        return _strip_owned_keys(row, ownership, tool_id, platform_os, home, environ)
    path = row.config_path(platform_os, home, environ)
    warnings: list[str] = []
    marker = _created_marker(row, home, environ)
    if row.strip_files is None and row.bind_created_path and marker.exists():
        sidecar = created_path_record(marker)
        recorded = sidecar.read_text(errors="replace") if sidecar.exists() else None
        if recorded != f"{path}\n":
            shown = recorded.removesuffix("\n") if recorded is not None else "an unrecorded path"
            return (
                f"{tool_id}: created config at {shown} is not the file now resolved; left alone",
            )
    paths = row.strip_files(platform_os, home, environ) if row.strip_files is not None else (path,)
    for candidate in paths:
        for region in (*row.sibling_regions, ownership.region):
            try:
                strip_region(candidate, region, comment=ownership.comment)
            except OSError as exc:
                warnings.append(f"{tool_id}: {candidate.name}: {first_line(exc)}")
    if not warnings:
        _record(tool_id, home, environ).unlink(missing_ok=True)
        warnings.extend(
            _drop_created_config(
                path,
                _created_marker(row, home, environ),
                home,
                tool_id,
                bound=row.bind_created_path,
                seed=WEZTERM_SKELETON if ownership.placement is Placement.BEFORE_RETURN else "",
            )
        )
    return tuple(warnings)


def _drop_created_config(
    path: Path, marker: Path, home: Path, tool_id: str, *, bound: bool, seed: str = ""
) -> list[str]:
    """Delete whitespace-only created configs; bound rows delete only their recorded path."""
    if not marker.exists():
        return []
    sidecar = created_path_record(marker)
    try:
        if bound:
            recorded = sidecar.read_text(errors="replace") if sidecar.exists() else None
            if recorded != f"{path}\n":
                shown = (
                    recorded.removesuffix("\n") if recorded is not None else "an unrecorded path"
                )
                return [
                    f"{tool_id}: created config at {shown} is not the file now resolved; left alone"
                ]
        before = read_settings(path)
        if before is None or (snapshot_text(before).strip() and snapshot_text(before) != seed):
            marker.unlink()
            sidecar.unlink(missing_ok=True)
            return []
        path.unlink(missing_ok=True)
        remove_created_dirs(tuple(marker.read_text(errors="replace").splitlines()[1:]), home)
        marker.unlink()
        sidecar.unlink(missing_ok=True)
    except OSError as exc:
        return [f"{tool_id}: {first_line(exc)}"]
    return []
