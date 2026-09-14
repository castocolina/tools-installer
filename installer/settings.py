"""Persisted wizard-settings file.

Shape and write path deliberately mirror installer.version_cache because that
module already established this project's JSON-state convention (Phase 12), so
there is exactly one persistence mechanism to reason about.

load_settings has two outcomes and only two. Missing or JSON null is the
valid, expected encoding of "never chosen" and returns Settings(). Present
but not a LINK_MODES member is a defect (tampered or hand-edited) and also
returns Settings(). Both land on Settings(); only one of them is a problem.

The closed-set check is the mitigation for a tampered or hand-edited state
file: without it an arbitrary string reaches
installer.locations.rc_paths_for_mode and ban_rc_paths, which select which of
the user's shell rc files get written.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from installer.atomic import atomic_write_text
from installer.locations import ensure_dir

LINK_MODES: Final[tuple[str, str, str]] = ("centralized", "single", "split")
DEFAULT_LINK_MODE = "centralized"


@dataclass(frozen=True)
class Settings:
    # None is "never chosen", not DEFAULT_LINK_MODE: "never chosen" drives the
    # one-time in-TUI prompt in plan 13-06; collapsing it into "chose
    # centralized" would either re-prompt forever or never prompt at all.
    link_mode: str | None = None


def default_settings_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "settings.json"


def load_settings(path: Path) -> Settings:
    """Read the settings envelope.

    Two outcomes only: missing or null → Settings() ("never chosen"); present
    but not a LINK_MODES member → Settings() (rejected). JSON null is the
    valid encoding of "the user has never chosen"; a number, a list, a nested
    object or an arbitrary string is a defect. Both land on Settings(); only
    one of them is a problem.
    """
    try:
        raw_decoded: object = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return Settings()
    if not isinstance(raw_decoded, dict):
        return Settings()
    data = cast(dict[str, object], raw_decoded)
    raw = data.get("link_mode")
    if raw is None:
        return Settings()
    if not isinstance(raw, str) or raw not in LINK_MODES:
        return Settings()
    return Settings(raw)


def save_settings(path: Path, settings: Settings) -> None:
    payload = {"version": 1, "link_mode": settings.link_mode}
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")
