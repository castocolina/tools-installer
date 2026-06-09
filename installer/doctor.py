"""Audit declared bin dirs against the live PATH: missing, broken, or duplicated."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DoctorReport:
    missing: tuple[Path, ...]  # declared but not on PATH
    broken: tuple[Path, ...]  # does not exist on disk
    duplicated: tuple[Path, ...]  # appears more than once on PATH


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
    return bool(report.missing or report.broken or report.duplicated)
