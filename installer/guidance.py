"""Pure guidance: map each PATH/guard finding type to a meaning + an exact next step.

No IO, no rich/Textual imports — both the console renderer and the Textual views
consume the same Guidance list, so each finding's wording lives in exactly one
place. `severity` drives color-coding downstream.
"""

from dataclasses import dataclass

from installer.doctor import DoctorReport, has_problems
from installer.enums import Severity
from installer.guards import GLOBAL_REDIRECTED, REDIRECTED, guard_label, guarded_names
from installer.pnpm_globals import NodeGlobalsReport


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
    # Either global-redirect name being installed routes global installs to
    # volta. Gating on pnpm alone missed the normal machine that has volta but
    # no pnpm — `npm i -g pnpm` is itself redirected now — where the npm wrapper
    # is written and `npm i -g <pkg>` runs volta's ungated install scripts with
    # the user told nothing.
    #
    # This reads the same bool dict guard_label does, so like guard_label it
    # describes the CONFIGURED redirect: on a machine where volta was
    # unresolvable at apply time, npm carries the hard-block body instead and
    # guard_redirect_warning says so in the warning below. That split is D-02's
    # "no status enum" cost, and the note above already cross-references it. Do
    # not read the shim bodies from here: this is the wording layer, not an IO
    # layer.
    if status.get("pnpm", False) or status.get("npm", False):
        items.append(
            Guidance(
                title="Volta global installs run npm install scripts",
                meaning=(
                    "A global install through volta runs a real `npm install --global`; "
                    "npm's install scripts are not gated the way pnpm gates them."
                ),
                next_step="Keep untrusted packages on a project-local `pnpm add`.",
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


_REINSTALL_NEXT_STEP = (
    "Run `make setup` and open the Doctor view to reinstall the globals pnpm still tracks."
)


def _join(names: tuple[str, ...]) -> str:
    """`a`, `a and b`, `a, b and c` — never `a and b and c`.

    Only two-member groups exist in the catalog today, but the wording layer is
    the one place a three-member group would read as a sentence nobody wrote.
    """
    if len(names) < 2:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def node_globals_guidance(report: NodeGlobalsReport) -> list[Guidance]:
    """Warn when a pnpm-managed global is missing or an install group is split."""
    items: list[Guidance] = []
    if report.missing:
        names = ", ".join(report.missing)
        items.append(
            Guidance(
                title="pnpm-managed global set is incomplete",
                meaning=(
                    f"pnpm still tracks {names} globally, but the command no longer "
                    "resolves on PATH. A pnpm self-update leaves the globals installed "
                    "by earlier `pnpm add -g` invocations behind in a stale directory."
                ),
                # The prefix is load-bearing: DoctorScreen._tui_guidance rewrites a
                # next_step only when it starts with a known literal prefix — today
                # `Run `make setup`` — so a step written in TUI terms ("press `r`")
                # would leak the keybinding into `make doctor`'s console output,
                # where no key can be pressed, and a step with an unrecognised
                # prefix would leak console instructions into the TUI.
                # "reinstall the globals pnpm still tracks", not "restore my global
                # set": one `pnpm add -g` replays exactly the set pnpm reports, so
                # anything pnpm has already forgotten is not coming back this way.
                next_step=_REINSTALL_NEXT_STEP,
                severity=Severity.WARN,
            )
        )
    for group in report.split_groups:
        names = _join(group)
        items.append(
            Guidance(
                title="pnpm install group is split",
                # The MEASURED condition, not an unmeasured consequence. Plan
                # 05-01's Tier-3 container recorded BROWNFIELD_BEFORE=ok for
                # exactly this shape: a standalone mmdc plus a standalone
                # allow-build puppeteer rendered successfully on pnpm 12.3.4
                # with default `autoInstallPeers`. Telling that user their tool
                # "fails when it is run" is a claim this phase's own evidence
                # contradicts. What the evidence does support is the reason
                # 05-01 gives for keeping `co_install` at all — the pair
                # survives on a user-settable pnpm option rather than on the
                # declared group.
                meaning=(
                    f"pnpm is holding {names} in separate global installs. The dependent "
                    "reaches its peer only through pnpm's user-settable "
                    "`auto-install-peers`, so this pair breaks if that setting changes; "
                    "the declared install group does not depend on it."
                ),
                # This prefix is load-bearing: DoctorScreen._tui_guidance rewrites
                # a next_step starting with `Run `make setup`` into
                # `Press r to reinstall the pnpm-managed global set`. The console
                # wording must stay runnable from a console.
                next_step=_REINSTALL_NEXT_STEP,
                severity=Severity.WARN,
            )
        )
    for tool_id, reason in report.unhealthy:
        items.append(
            Guidance(
                title=f"{tool_id} is installed but does not work",
                meaning=(
                    f"{tool_id}'s command resolves on PATH, but the check the catalog "
                    f"declares for it fails right now: {reason}"
                ),
                # Deliberately NOT one of the two rewritten prefixes: `r` replays
                # pnpm's global set, and a global set is not what is broken here.
                # A shared library the OS update removed comes back from the OS,
                # not from a reinstall, so the same sentence is the right one on
                # both surfaces.
                next_step=(
                    "Restore the tool's runtime prerequisites (see its entry in "
                    "installer/registry.toml), then reinstall it from the catalog."
                ),
                severity=Severity.WARN,
            )
        )
    for incomplete in report.incomplete_groups:
        items.append(
            Guidance(
                title="pnpm install group is incomplete",
                meaning=(
                    f"pnpm manages {_join(incomplete.present)} globally but not "
                    f"{_join(incomplete.missing)}, which the catalog declares as part of "
                    "the same install group. Nothing the missing package's own install "
                    "does on this machine has happened, and the dependent finds it at all "
                    "only if pnpm's user-settable `auto-install-peers` pulled a copy into "
                    "the dependent's own tree."
                ),
                # Same load-bearing prefix as the two items above: the reinstall
                # replay now completes a declared group rather than replaying only
                # the names pnpm already listed, so `r` really is the repair here.
                next_step=_REINSTALL_NEXT_STEP,
                severity=Severity.WARN,
            )
        )
    return items
