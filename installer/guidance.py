"""Pure guidance: map each PATH/guard finding type to a meaning + an exact next step.

No IO, no rich/Textual imports — both the console renderer and the Textual views
consume the same Guidance list, so each finding's wording lives in exactly one
place. `severity` drives color-coding downstream.
"""

from dataclasses import dataclass

from installer.doctor import DoctorReport, has_problems
from installer.enums import Severity
from installer.guards import GLOBAL_REDIRECTED, REDIRECTED, guard_label, guarded_names


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
    """Per-command guard labels + PATH-order guidance.

    Empty when nothing is active and there is no warning.
    """
    items: list[Guidance] = []
    active = [name for name in guarded_names() if status.get(name, False)]
    if active:
        meaning = "; ".join(f"{name}: {guard_label(name)}" for name in active) + "."
        # guard_label is deliberately static, so npx still reads as redirected even
        # on a machine where install_redirect_shims fell back to the hard-block body
        # because pnpm was unresolvable. That honest signal lives in
        # guard_redirect_warning, which plan 04-01 folded into guard_state's warning
        # string — a separate channel a reader could miss. This is the accepted cost
        # of D-02's "no status enum" constraint, not a defect; the cross-reference
        # is what keeps the two channels connected on the page. Do not recompute
        # redirect health here: this function takes a bool dict and a string, and
        # reading the shim bodies from it would put IO in the wording layer.
        if warning is not None and any(
            name in REDIRECTED or name in GLOBAL_REDIRECTED for name in active
        ):
            meaning += (
                " Labels describe the configured redirect; "
                "the warning below reports anything that degraded."
            )
        items.append(
            Guidance(
                title="Package manager guards active",
                meaning=meaning,
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
