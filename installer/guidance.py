"""Pure guidance: map each PATH/guard finding type to a meaning + an exact next step.

No IO, no rich/Textual imports — both the console renderer and the Textual views
consume the same Guidance list, so each finding's wording lives in exactly one
place. `severity` drives color-coding downstream.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from installer.diskusage import DISK_FREE_WARN_PERCENT, TMP_USED_WARN_PERCENT, DiskPressure
from installer.doctor import DoctorReport, has_problems
from installer.enums import DaemonState, Severity
from installer.guards import GLOBAL_REDIRECTED, REDIRECTED, guard_label, guarded_names
from installer.pnpm_globals import NodeGlobalsReport
from installer.rcclean import PathWriterLine
from installer.systemd_daemon import SCOPE_SYSTEM, CompetingUnit, system_scope_warning


@dataclass(frozen=True, init=False)
class Guidance:
    title: str
    meaning: str
    next_step: str  # empty only for the healthy/ok case
    severity: Severity
    # D-03: extra visual weight for the daemon-inactive + low-space conjunction,
    # without a fourth Severity member -- Severity is consumed structurally as a
    # dict key in ui_common.SEVERITY_STYLE and render.py, so a new severity
    # level would need every consuming dict updated. render.guidance_text is the
    # single point that honours this flag, reaching both `make doctor` and the
    # Doctor screen from one change.
    emphasis: bool

    def __init__(
        self,
        title: str,
        meaning: str,
        next_step: str,
        severity: Severity | str,
        emphasis: bool = False,
    ) -> None:
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "meaning", meaning)
        object.__setattr__(self, "next_step", next_step)
        object.__setattr__(self, "severity", Severity(severity))
        object.__setattr__(self, "emphasis", emphasis)


_HEALTHY = Guidance(
    title="PATH looks healthy",
    meaning="All bin dirs are present, on PATH, and unique.",
    next_step="",
    severity=Severity.OK,
)


def _writer_next_step(
    named: str, adding: tuple[Path, ...], records: Sequence[PathWriterLine]
) -> str:
    """Per-directory remedy. Empty records keep the edit-it-yourself wording."""
    if len(adding) > 1:
        fallback = (
            f"Edit the PATH line in each of them ({named}) — either remove it, or guard "
            "it so it skips a directory that is already on PATH."
        )
    else:
        fallback = (
            f"Edit the PATH line in {named} — either remove it, or guard it so it skips "
            "a directory that is already on PATH."
        )
    if not records:
        return fallback
    fragments: list[str] = []
    owners: list[str] = []
    for record in records:
        if record.block_owner and record.block_owner not in owners:
            owners.append(record.block_owner)
    if owners:
        named_blocks = " and ".join(f"'{owner}'" for owner in owners)
        noun = "block" if len(owners) == 1 else "blocks"
        fragments.append(
            f"inside the {named_blocks} {noun}; fix it in that tool, "
            "because that tool may regenerate the block"
        )
    if any(record.guardable for record in records):
        fragments.append(
            "Press enter (apply) to guard it in place. A backup of the original is "
            "saved as .tools-installer.old first"
        )
    reasons: list[str] = []
    for record in records:
        if record.block_owner or record.guardable or not record.refusal:
            continue
        if record.refusal not in reasons:
            reasons.append(record.refusal)
    if reasons:
        fragments.append(f"Edit the PATH line in {named}: {'; '.join(reasons)}")
    return "; ".join(fragments) if fragments else fallback


def doctor_guidance(
    report: DoctorReport,
    duplicate_writers: Mapping[Path, tuple[Path, ...]] | None = None,
    writer_lines: Sequence[PathWriterLine] = (),
) -> list[Guidance]:
    """One Guidance per finding; a single healthy item when there are no problems.

    `duplicate_writers` maps a duplicated directory to the rc files that add it
    without checking whether it is already present (see
    `installer.rcclean.path_writer_lines`). It decides which of two opposite
    remedies a duplicate finding gets, and omitting it keeps the older,
    cause-agnostic wording rather than asserting a cause that was never checked.
    `writer_lines` chooses the per-directory next step from each line's real
    status. Omitting it keeps the edit-it-yourself wording.
    """
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
    writers = duplicate_writers or {}
    for directory in report.duplicated:
        # Two opposite causes wear the same symptom. A nested shell re-adding an
        # inherited entry clears in a fresh terminal; an rc file that prepends
        # without checking whether the directory is already present re-adds it
        # on EVERY shell, so "open a new shell" is advice that can never work
        # and the finding returns forever. Only the second case is knowable
        # from the rc files, so it is the one stated as fact -- the other stays
        # a hypothesis with the command to check it.
        adding = writers.get(directory, ())
        if adding:
            named = ", ".join(str(rc_file) for rc_file in adding)
            if len(adding) > 1:
                cause = (
                    f"{len(adding)} startup files add it without checking whether "
                    f"it is already present: {named}"
                )
            else:
                cause = f"{named} adds it without checking whether it is already present"
            records = [record for record in writer_lines if record.directory == directory]
            items.append(
                Guidance(
                    title=f"{directory} duplicated on PATH",
                    meaning=(
                        f"{directory} appears more than once on PATH, and {cause}. "
                        f"Opening a new terminal will not clear this one."
                    ),
                    next_step=_writer_next_step(named, adding, records),
                    severity=Severity.WARN,
                )
            )
            continue
        items.append(
            Guidance(
                title=f"{directory} duplicated on PATH",
                meaning=f"{directory} appears more than once on PATH.",
                next_step=(
                    "Usually a nested shell re-adding an inherited entry, which "
                    "clears when you open a new shell. To confirm, run "
                    "`env -i HOME=\"$HOME\" bash -lic 'echo $PATH'` — if it still "
                    "repeats there, an rc file is adding it on every shell."
                ),
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


# The one-off manual prune command, used verbatim only by the UNAVAILABLE
# branch below (D-03c): that host has no policy row to enable, so its next
# step names only the immediate, runnable command. The INACTIVE branch also
# names the same script (D-03's action text), but phrased inside a longer
# sentence that leads with enabling the policy -- so this exact sentence
# never appears in the INACTIVE (or ACTIVE) next_step, and a reader can tell
# the two "no action beyond a one-off" and "there is a policy to flip" cases
# apart by next_step content alone.
_MACOS_PRUNE_SCRIPT = "./scripts/prune-user-tmpdir.sh --apply"
_LINUX_PRUNE_SCRIPT = "./scripts/prune-tmp-linux.sh --apply"


def prune_command(pressure: DiskPressure) -> str:
    """The one-off cleanup command that actually works on this platform.

    WR-08: every next step named the macOS script. On Linux it defaults to
    $TMPDIR with no /tmp fallback (so it exits 1 on a stock host) and prunes
    a macOS family of files three days old, not the fresh Bun .so/.node
    orphans filling the tmpfs. `tmp_threshold` is the Linux-only flag the
    probe already carries, so no new platform argument is needed.
    """
    return _LINUX_PRUNE_SCRIPT if pressure.tmp_threshold else _MACOS_PRUNE_SCRIPT


def runnable_prune_sentence(pressure: DiskPressure) -> str:
    return f"Run `{prune_command(pressure)}` for an immediate one-off cleanup."


def _pressure_clauses(pressure: DiskPressure) -> tuple[str, ...]:
    """Human phrases for whichever threshold(s) tripped, disk before tmp so
    title/meaning wording never depends on iteration order. Reused by the
    title (names the conditions) and by the caller's own two-item cap in
    `_join` -- only low_disk and high_tmp exist, so at most two clauses."""
    clauses: list[str] = []
    if pressure.low_disk:
        clauses.append("free disk space is low")
    if pressure.high_tmp:
        # Deliberately not "/tmp usage is high": a string literal beginning
        # with "/tmp" reads to bandit's B108 as a hardcoded temp-directory
        # path, even though this is prose, never a filesystem argument.
        # IN-03: the probe measures $TMPDIR when set, else /tmp, so the
        # wording names the measured mount rather than always saying /tmp.
        clauses.append("the temp mount is nearly full")
    return tuple(clauses)


def _disk_pressure_title(pressure: DiskPressure) -> str:
    clauses = _join(_pressure_clauses(pressure))
    if pressure.daemon is DaemonState.INACTIVE:
        return f"Background cleanup is off and {clauses}"
    capitalized = clauses[0].upper() + clauses[1:]
    if pressure.daemon is DaemonState.ACTIVE:
        return f"{capitalized} even though background cleanup is active"
    return capitalized


def _disk_pressure_meaning(pressure: DiskPressure) -> str:
    parts: list[str] = []
    # The explicit `is not None` conjunct (redundant with low_disk/high_tmp's
    # own None-check) is what lets pyright narrow the percentage to `float`
    # here without an `assert` -- an assert would be stripped under
    # `python -O` and bandit (B101) flags it regardless.
    if pressure.low_disk and pressure.home_free_percent is not None:
        # Names the filesystem that was actually measured -- the one holding
        # the user's home directory, which is `/` on a stock host but the
        # separate data mount on an ostree/composefs one.
        parts.append(
            f"Free space on the filesystem holding your home directory is at "
            f"{pressure.home_free_percent:.1f}%, below the "
            f"{DISK_FREE_WARN_PERCENT}% threshold."
        )
    if pressure.high_tmp and pressure.tmp_used_percent is not None:
        # Leads with "The" rather than a literal starting "/tmp" for the same
        # bandit B108 reason as _pressure_clauses above.
        parts.append(
            f"The temp mount ($TMPDIR when set, else /tmp) is at "
            f"{pressure.tmp_used_percent:.1f}% used, above the "
            f"{TMP_USED_WARN_PERCENT}% threshold -- a full temp mount breaks unrelated "
            "system writes, not only this tool."
        )
    if pressure.daemon is DaemonState.INACTIVE:
        parts.append("The background cleanup job is not running to relieve it.")
    elif pressure.daemon is DaemonState.ACTIVE:
        parts.append(
            "The background cleanup job is currently active; this is worth watching, but "
            "not the failure scenario the emphasised finding is reserved for."
        )
    else:
        parts.append("No managed background cleanup could be confirmed on this machine.")
    return " ".join(parts)


def _disk_pressure_next_step(pressure: DiskPressure) -> str:
    command = prune_command(pressure)
    if pressure.daemon is DaemonState.INACTIVE:
        # Enable through this project's own setup flow, and name the manual
        # prune script as the immediate one-off (D-03's action text). This
        # sentence is deliberately NOT runnable_prune_sentence verbatim, and
        # plan 15.7-06 rewrites it (by its own new prefix match, distinct
        # from the existing "Run `make fix`"/"Run `make setup`" prefixes
        # DoctorScreen._tui_guidance already recognises) into a "go to the
        # Policies view" TUI instruction.
        return (
            "Enable the background cleanup policy in `make setup`'s Policies view; a "
            f"one-off `{command}` run clears space immediately in the meantime."
        )
    if pressure.daemon is DaemonState.UNAVAILABLE:
        # D-03c: no policy row exists on this host to enable, so only the
        # one-off is named -- never "enable"/"Policies"/"setup" wording.
        # IN-06: UNAVAILABLE also covers a query that timed out or hit a
        # wedged bus on a host that DOES have the row, so the wording says
        # the state could not be read rather than claiming the capability
        # does not exist here.
        return (
            f"{runnable_prune_sentence(pressure)} No managed background cleanup could be "
            "confirmed on this machine: its state could not be read."
        )
    return (
        "Nothing to do right now -- the background cleanup job is already active and "
        "should reclaim space on its own scheduled run."
    )


def disk_pressure_guidance(pressure: DiskPressure) -> list[Guidance]:
    """D-03: one Guidance item when disk pressure was measured, none otherwise.

    Decision D-03a (this plan's objective): the daemon-inactive fact and the
    low-space fact are two independently measurable conditions. Low space
    alone is an ordinary warning -- a doctor that measured a nearly-full disk
    and said nothing is worse than a warning -- and the conjunction (low
    space AND the one daemon state with a control the user can flip) is the
    emphasised red finding D-03 calls "the actual failure scenario this whole
    todo exists to prevent". An emphasis every finding earns is not an
    emphasis, so ACTIVE and UNAVAILABLE both report the same measured
    pressure at ordinary warning weight, never emphasised.
    """
    if not pressure.under_pressure:
        return []
    severity = Severity.ERROR if pressure.at_risk else Severity.WARN
    return [
        Guidance(
            title=_disk_pressure_title(pressure),
            meaning=_disk_pressure_meaning(pressure),
            next_step=_disk_pressure_next_step(pressure),
            severity=severity,
            emphasis=pressure.at_risk,
        )
    ]


def competing_mechanism_guidance(units: tuple[CompetingUnit, ...]) -> list[Guidance]:
    """WR-10: a durable, read-only disclosure of a SYSTEM-scope competitor.

    D-02a requires naming the root-owned competing cleanup unit and the
    manual command that stops it. Until now that sentence existed only inside
    the first apply's result, so it was printed once (after the TUI exits)
    and never again, because `decided()` is True on every later run. This
    item is rendered from a memoized detection on every Doctor run instead.

    User-scope competitors are deliberately absent: those are taken over by
    the apply (D-02/D-02b) and disclosed by it, so repeating them here would
    describe a mechanism that is no longer running. Nothing on this path
    mutates anything, in either scope.
    """
    sentence = system_scope_warning(units)
    if sentence is None:
        return []
    names = sorted({unit.name for unit in units if unit.scope == SCOPE_SYSTEM})
    return [
        Guidance(
            title=f"Another system-level cleanup service is installed ({', '.join(names)})",
            meaning=sentence,
            next_step=(
                "Nothing here can stop it: this installer never uses sudo. Run the command "
                "named above yourself if you want only one cleanup job on this machine."
            ),
            severity=Severity.WARN,
        )
    ]
