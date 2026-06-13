"""Pure guidance: map each PATH/guard finding type to a meaning + an exact next step.

No IO, no rich/Textual imports — both the console renderer and the Textual views
consume the same Guidance list, so each finding's wording lives in exactly one
place. `severity` drives color-coding downstream.
"""

from dataclasses import dataclass
from typing import Literal

from installer.doctor import DoctorReport, has_problems

Severity = Literal["ok", "warn", "error"]


@dataclass(frozen=True)
class Guidance:
    title: str
    meaning: str
    next_step: str  # empty only for the healthy/ok case
    severity: Severity


_HEALTHY = Guidance(
    title="PATH looks healthy",
    meaning="All bin dirs are present, on PATH, and unique.",
    next_step="",
    severity="ok",
)


def doctor_guidance(report: DoctorReport) -> list[Guidance]:
    """One Guidance per finding; a single healthy item when there are no problems."""
    if not has_problems(report):
        return [_HEALTHY]
    items: list[Guidance] = []
    for directory in report.broken:
        items.append(
            Guidance(
                title=f"{directory} does not exist",
                meaning=f"{directory} is declared but does not exist yet.",
                next_step="It is created when a tool installs there — nothing to do now.",
                severity="error",
            )
        )
    for directory in report.missing:
        items.append(
            Guidance(
                title=f"{directory} not on PATH",
                meaning=f"{directory} is not on your PATH.",
                next_step="Run `make fix`, then open a new terminal (or `source ~/.myshellrc`).",
                severity="warn",
            )
        )
    for directory in report.duplicated:
        items.append(
            Guidance(
                title=f"{directory} duplicated on PATH",
                meaning=f"{directory} appears more than once on PATH.",
                next_step="Harmless — transient duplicates clear when you open a new shell.",
                severity="warn",
            )
        )
    return items


def guard_guidance(status: dict[str, bool], warning: str | None) -> list[Guidance]:
    """pip/npm-ban + PATH-order guidance; empty when nothing is active and no warning."""
    items: list[Guidance] = []
    active = [name for name, installed in status.items() if installed]
    if active:
        items.append(
            Guidance(
                title="pip/npm ban active",
                meaning=f"{', '.join(active)} are shimmed to their replacements.",
                next_step="Open a new shell or run `hash -r` so cached command paths refresh.",
                severity="ok",
            )
        )
    if warning:
        items.append(
            Guidance(
                title="PATH order warning",
                meaning=warning,
                next_step=(
                    "Put the shim dir ahead of the real binary on PATH, then reopen the shell."
                ),
                severity="warn",
            )
        )
    return items
