"""One terminal keys mechanism keyed by registry tool id (28 D-01): apply, check, re-apply,
and strip a terminal's owned keys region the same way for every row."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from installer.agent_settings import read_settings, remove_created_dirs
from installer.atomic import atomic_write_text
from installer.terminal_regions import (
    ALACRITTY,
    ALACRITTY_CREATED,
    ALACRITTY_KEYS,
    KeysPlan,
    alacritty_config_path,
    alacritty_keys_plan,
    commit_region,
    first_line,
    replace_owned_region,
    snapshot_text,
    strip_region,
    user_document,
    validate_toml,
    xdg_data_home,
)

KEYS_PENDING = "install tuning not applied"


@dataclass(frozen=True)
class OwnedRegion:
    """A marker-delimited region owned by the installer; the sole ownership mode until phase 31."""

    region: str  # Marker name.
    comment: str = "#"  # Marker comment prefix.


@dataclass(frozen=True)
class KeysRow:
    ownership: OwnedRegion  # The region this row owns.
    config_path: Callable[[str, Path, Mapping[str, str]], Path]  # Platform, home, environment.
    plan: Callable[[str, str], KeysPlan]  # Platform and whole file text to the planned region.
    validate: Callable[[str], None]  # Validate the edited whole file.
    summary: str  # Success line when this row adds keys.
    created_record: str  # Created-file marker name.
    sibling_regions: tuple[str, ...] = ()  # Other installer regions stripped with this tool.


def _alacritty_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    del platform_os
    return alacritty_config_path(home, environ)


def alacritty_keys_plan_for_document(document: Mapping[str, object], outside: str) -> KeysPlan:
    return alacritty_keys_plan(document, outside)


def alacritty_keys_plan_for_text(text: str) -> KeysPlan:
    return alacritty_keys_plan_for_document(*user_document(text))


def _alacritty_plan(platform_os: str, text: str) -> KeysPlan:
    del platform_os
    return alacritty_keys_plan_for_text(text)


TERMINAL_KEYS: Final[dict[str, KeysRow]] = {
    "alacritty": KeysRow(
        ownership=OwnedRegion(ALACRITTY_KEYS),
        config_path=_alacritty_path,
        plan=_alacritty_plan,
        validate=validate_toml,
        summary=(
            "Alacritty keys: Alt+Left and Alt+Right move by word, Control+Shift+K clears history."
        ),
        created_record=ALACRITTY_CREATED,
        sibling_regions=(ALACRITTY,),
    )
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

    `skip_recorded` (RECONFIGURE) leaves a recorded install alone: a region the user deleted
    stays deleted. Nothing is written when the file cannot take the region."""
    record = _record(tool_id, home, environ)
    if skip_recorded and record.exists():
        return (), None
    path = row.config_path(platform_os, home, environ)
    try:
        before = read_settings(path)
        text = snapshot_text(before)
        plan = row.plan(platform_os, text)
        if plan.refusal is not None:
            return (), plan.refusal
        updated = replace_owned_region(
            text, row.ownership.region, plan.body, comment=row.ownership.comment
        )
        commit_region(
            path,
            before,
            text,
            updated,
            validate=row.validate,
            write=True,
            created_marker=_created_marker(row, home, environ),
            home=home,
        )
        record.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(record, "written\n")
    except OSError as exc:
        return (), first_line(exc)
    added = (row.summary,) if plan.body is not None else ()
    return (*added, *plan.conflicts), None


def terminal_keys_pending(
    row: KeysRow, tool_id: str, platform_os: str, home: Path, environ: Mapping[str, str]
) -> str | None:
    """None when the keys region or its record exists; otherwise pending or the refusal reason."""
    if _record(tool_id, home, environ).exists():
        return None
    try:
        path = row.config_path(platform_os, home, environ)
        text = snapshot_text(read_settings(path))
        if (
            replace_owned_region(text, row.ownership.region, None, comment=row.ownership.comment)
            != text
        ):
            return None
        plan = row.plan(platform_os, text)
    except OSError as exc:
        return first_line(exc)
    return plan.refusal or KEYS_PENDING


def strip_terminal_keys(
    row: KeysRow, tool_id: str, platform_os: str, home: Path, environ: Mapping[str, str]
) -> tuple[str, ...]:
    """Remove the tool's owned regions and record; the config remains unless created by us."""
    path = row.config_path(platform_os, home, environ)
    warnings: list[str] = []
    for region in (*row.sibling_regions, row.ownership.region):
        try:
            strip_region(path, region, comment=row.ownership.comment)
        except OSError as exc:
            warnings.append(f"{tool_id}: {first_line(exc)}")
    if not warnings:
        _record(tool_id, home, environ).unlink(missing_ok=True)
        warnings.extend(
            _drop_created_config(path, _created_marker(row, home, environ), home, tool_id)
        )
    return tuple(warnings)


def _drop_created_config(path: Path, marker: Path, home: Path, tool_id: str) -> list[str]:
    """Delete our created config once only whitespace remains, then its created directories."""
    if not marker.exists():
        return []
    try:
        before = read_settings(path)
        if before is None or snapshot_text(before).strip():
            marker.unlink()
            return []
        path.unlink(missing_ok=True)
        remove_created_dirs(tuple(marker.read_text(errors="replace").splitlines()[1:]), home)
        marker.unlink()
    except OSError as exc:
        return [f"{tool_id}: {first_line(exc)}"]
    return []
