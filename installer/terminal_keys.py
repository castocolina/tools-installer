"""One terminal keys mechanism keyed by registry tool id (28 D-01): apply, check, re-apply,
and strip a terminal's owned keys region the same way for every row."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Final

from installer.agent_settings import read_settings, remove_created_dirs
from installer.atomic import atomic_write_text
from installer.run import CommandError, run_output
from installer.terminal_regions import (
    ALACRITTY,
    ALACRITTY_CREATED,
    ALACRITTY_KEYS,
    GHOSTTY,
    GHOSTTY_CREATED,
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
    """A marker-delimited region owned by the installer; the sole ownership mode until phase 31."""

    region: str  # Marker name.
    comment: str = "#"  # Marker comment prefix.
    placement: Placement = Placement.END  # Where a new region goes.


@dataclass(frozen=True)
class KeysRow:
    ownership: OwnedRegion  # The region this row owns.
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
    if scan.clears:
        return KeysPlan(
            None, scan.reports, refusal="you set keybind = clear, which would clear these keys"
        )
    chord, send = clear_binding(TERMINAL_KEYS["ghostty"], platform_os)
    trigger = "super+k" if chord == "cmd+k" else chord
    if ghostty_chord(f"{trigger}=x") in scan.taken:
        return KeysPlan(None, (*scan.reports, f"ghostty: partial: you already bind {trigger}"))
    escaped = "".join(f"\\x{ord(character):02x}" for character in send)
    notes = (
        ("ghostty: cmd+k now sends Ctrl+L; it was clear_screen.",) if platform_os == "macos" else ()
    )
    return KeysPlan(f"keybind = {trigger}=text:{escaped}", scan.reports, notes=notes)


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
    del text, path
    return KeysPlan(wezterm_keys_body(_wezterm_rows(platform_os)))


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
    return () if output is None else wezterm_readback(output, _wezterm_rows(platform_os))


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
}


def _record(tool_id: str, home: Path, environ: Mapping[str, str]) -> Path:
    return xdg_data_home(home, environ) / "tools-installer" / f"terminal-tuning-{tool_id}"


def _created_marker(row: KeysRow, home: Path, environ: Mapping[str, str]) -> Path:
    return xdg_data_home(home, environ) / "tools-installer" / row.created_record


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
            row.ownership.region,
            body,
            comment=row.ownership.comment,
            placement=row.ownership.placement,
        )
        region_present = (
            replace_owned_region(text, row.ownership.region, None, comment=row.ownership.comment)
            != text
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
    recorded = _record(tool_id, home, environ).exists()
    present = False
    try:
        path = row.config_path(platform_os, home, environ)
        text = snapshot_text(read_settings(path))
        present = (
            replace_owned_region(text, row.ownership.region, None, comment=row.ownership.comment)
            != text
        )
        if recorded and not present:
            return None
        plan = _render(row, platform_os, text, path)
        if plan.refusal is not None and not recorded:
            return plan.refusal
        if (
            not present
            and row.ownership.placement is Placement.BEFORE_RETURN
            and plan.body is not None
        ):
            replace_owned_region(
                text,
                row.ownership.region,
                plan.body,
                comment=row.ownership.comment,
                placement=row.ownership.placement,
            )
        if present:
            body = "" if plan.body is None and plan.conflicts else plan.body
            updated = replace_owned_region(
                text,
                row.ownership.region,
                body,
                comment=row.ownership.comment,
                placement=row.ownership.placement,
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
        for region in (*row.sibling_regions, row.ownership.region):
            try:
                strip_region(candidate, region, comment=row.ownership.comment)
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
                seed=WEZTERM_SKELETON if row.ownership.placement is Placement.BEFORE_RETURN else "",
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
