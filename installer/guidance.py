"""Pure guidance: map each PATH/guard finding type to a meaning + an exact next step.

No IO, no rich/Textual imports — both the console renderer and the Textual views
consume the same Guidance list, so each finding's wording lives in exactly one
place. `severity` drives color-coding downstream.
"""

from dataclasses import dataclass

from installer.doctor import DoctorReport, has_problems
from installer.enums import Severity


@dataclass(frozen=True, init=False)
class Guidance:
    title: str
    meaning: str
    next_step: str  # empty only for the healthy/ok case
    severity: Severity

    def __init__(self, title: str, meaning: str, next_step: str, severity: Severity | str) -> None:
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "meaning", meaning)
        object.__setattr__(self, "next_step", next_step)
        object.__setattr__(self, "severity", Severity(severity))


_HEALTHY = Guidance(
    title="PATH looks healthy",
    meaning="All bin dirs are present, on PATH, and unique.",
    next_step="",
    severity=Severity.OK,
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
                severity=Severity.ERROR,
            )
        )
    for directory in report.missing:
        items.append(
            Guidance(
                title=f"{directory} not on PATH",
                meaning=f"{directory} is not on your PATH.",
                next_step="Run `make fix`, then open a new terminal (or `source ~/.myshellrc`).",
                severity=Severity.WARN,
            )
        )
    for directory in report.duplicated:
        items.append(
            Guidance(
                title=f"{directory} duplicated on PATH",
                meaning=f"{directory} appears more than once on PATH.",
                next_step="Harmless — transient duplicates clear when you open a new shell.",
                severity=Severity.WARN,
            )
        )
    return items


def guard_guidance(status: dict[str, bool], warning: str | None) -> list[Guidance]:
    """pip/npm-ban + PATH-order guidance; empty when nothing is active and no warning."""
    items: list[Guidance] = []
    active = [name for name, installed in status.items() if installed]
    if active:
        # Agree the verb/possessive with the count so a single active shim reads
        # "pip is shimmed to its replacement" rather than "pip are ... their".
        shimmed = (
            f"{active[0]} is shimmed to its replacement"
            if len(active) == 1
            else f"{', '.join(active)} are shimmed to their replacements"
        )
        items.append(
            Guidance(
                title="pip/npm ban active",
                meaning=f"{shimmed}.",
                next_step="Open a new shell or run `hash -r` so cached command paths refresh.",
                severity=Severity.OK,
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
                severity=Severity.WARN,
            )
        )
    return items
