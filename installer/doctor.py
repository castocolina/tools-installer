"""Audit declared bin dirs against the live PATH: missing, broken, or duplicated."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from installer import locations


@dataclass(frozen=True)
class DoctorReport:
    missing: tuple[Path, ...]  # declared but not on PATH
    broken: tuple[Path, ...]  # does not exist on disk
    duplicated: tuple[Path, ...]  # appears more than once on PATH
    broken_links: tuple["BrokenLink", ...] = ()  # dangling or dir-pointing symlinks


@dataclass(frozen=True)
class BrokenLink:
    """One symlink in a bin dir that points to nothing or to a directory (D-13)."""

    path: Path
    target: str  # verbatim readlink text
    kind: Literal["dangling", "directory"]
    opt_dir: Path | None  # set only when the target resolves inside it


def scan_bin_links(bin_dir: Path) -> tuple[BrokenLink, ...]:
    """Scan every symlink in one bin dir for dangling or directory targets (D-13).

    Registry-independent and read-only: nothing is executed, nothing is repaired.
    """
    try:
        entries = sorted(bin_dir.iterdir(), key=lambda entry: entry.name)
    except OSError:
        return ()
    found: list[BrokenLink] = []
    for entry in entries:
        try:
            if not entry.is_symlink():
                continue
            target = os.readlink(entry)
            resolved = Path(os.path.normpath(os.path.join(entry.parent, target)))
            if resolved.is_dir():
                kind: Literal["dangling", "directory"] = "directory"
            elif not resolved.exists():
                kind = "dangling"
            else:
                continue
            expected = locations.opt_dir(entry.name)
            inside = resolved == expected or expected in resolved.parents
            found.append(
                BrokenLink(
                    path=entry,
                    target=target,
                    kind=kind,
                    opt_dir=expected if inside else None,
                )
            )
        except OSError:
            continue
    return tuple(found)


def audit_path(
    bin_dirs: list[Path], path_value: str, exists: Callable[[Path], bool]
) -> DoctorReport:
    """Classify each declared bin dir against the current PATH string and disk state."""
    counts: dict[Path, int] = {}
    for entry in path_value.split(":"):
        if entry:
            key = Path(entry)
            counts[key] = counts.get(key, 0) + 1
    missing = tuple(directory for directory in bin_dirs if directory not in counts)
    broken = tuple(directory for directory in bin_dirs if not exists(directory))
    duplicated = tuple(directory for directory in bin_dirs if counts.get(directory, 0) > 1)
    return DoctorReport(missing=missing, broken=broken, duplicated=duplicated)


def has_problems(report: DoctorReport) -> bool:
    """True if the report has any missing, broken, or duplicated bin dir."""
    return bool(report.missing or report.broken or report.duplicated or report.broken_links)
