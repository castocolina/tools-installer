"""Render install plans, run summaries, and reports to a Console."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from rich.cells import cell_len
from rich.console import Console
from rich.markup import escape
from rich.text import Text

from installer.apps import APP_KINDS
from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport
from installer.download import DOWNLOAD_KINDS
from installer.engine import InstallOutcome
from installer.enums import InstallStatus
from installer.guidance import (
    Guidance,
    competing_mechanism_guidance,
    disk_pressure_guidance,
    doctor_guidance,
    guard_guidance,
    node_globals_guidance,
)
from installer.links import TROUBLESHOOTING_URL
from installer.pnpm_globals import NodeGlobalsReport
from installer.sanitize import sanitize_log_line
from installer.session import (
    RESULT_WORDS,
    WORDS,
    Disposition,
    PlanRow,
    RowOutcome,
    review_counts,
    summary_counts,
)
from installer.systemd_daemon import CompetingUnit
from installer.ui_common import SEVERITY_STYLE
from installer.version_status import HEALTH_MARKS, Health


def id_width(rows: Sequence[PlanRow]) -> int:
    """Cell width reserved for the longest id, capped to the plan's id budget."""
    widths = (cell_len(row.tool_id) + (2 if row.requested_by else 0) for row in rows)
    return min(26, max(widths, default=0))


def display_order(rows: Sequence[PlanRow]) -> list[PlanRow]:
    """Place each dragged row beneath its first requester, preserving plan order."""
    result: list[PlanRow] = []
    emitted: set[int] = set()
    for row in rows:
        if row.requested_by is not None or id(row) in emitted:
            continue
        result.append(row)
        emitted.add(id(row))
        for dependency in rows:
            if dependency.requested_by == row.tool_id and id(dependency) not in emitted:
                result.append(dependency)
                emitted.add(id(dependency))
    result.extend(row for row in rows if row.requested_by is not None and id(row) not in emitted)
    return result


def fold_reason(prefix: Text, body: str, column: int, width: int) -> Text:
    """Append folded body lines with a hanging indent at ``column``."""
    first_line = prefix.plain.rsplit("\n", 1)[-1]
    first_room = max(1, width - cell_len(first_line))
    continuation_room = max(1, width - column)
    room = min(first_room, continuation_room)
    chunks = [line.plain for line in Text(body).wrap(Console(width=room), room)]
    if not chunks:
        return prefix
    prefix.append(chunks[0])
    for chunk in chunks[1:]:
        prefix.append("\n" + " " * column + chunk)
    return prefix


def plan_row_text(row: PlanRow, idw: int, width: int, *, hint: bool) -> Text:
    """Build one sanitized, styled plan row without invoking Rich markup."""
    health = row.health or Health.CHECKING
    glyph, glyph_style = HEALTH_MARKS[health]
    glyph_width = cell_len(glyph)
    dragged = row.requested_by is not None
    indent = 2 if dragged else 0
    text = Text()
    text.append(glyph, style=glyph_style)
    text.append(" ")
    if dragged:
        text.append("  ")
    text.append(row.tool_id.ljust(max(0, idw - indent)), style="bold")
    text.append("  ")
    words = WORDS[row.disposition]
    text.append(words.review, style=words.style)
    column = glyph_width + 1 + idw + 2
    reason = sanitize_log_line(row.reason) if row.disposition is not Disposition.WAIT else ""
    if hint and row.can_reinstall:
        reason += " (r: reinstall)"
    if reason:
        fold_reason(text, " — " + reason, column, width)
    if row.disposition is Disposition.RECONFIGURE and row.steps:
        step_text = "; ".join(sanitize_log_line(step.text) for step in row.steps)
        text.append("\n" + " " * column)
        fold_reason(text, "to configure: " + step_text, column, width)
    return text


def plan_head(rows: Sequence[PlanRow]) -> str:
    """Return the plan title, review counts and conditional dependency note."""
    counts = review_counts(rows)
    suffix = (
        ". Indented rows are needed by the tool above and run first."
        if any(row.requested_by is not None for row in rows)
        else ""
    )
    return f"Install plan — {counts}{suffix}"


# The finished marks that replace a health glyph, per UI-SPEC "Marks": the mark
# states a fact about the run, so a skipped or blocked row keeps its plan-time
# health glyph and never turns green.
_DONE_MARK: tuple[str, str] = ("✓", "green")
_FAILURE_MARK: tuple[str, str] = ("✖", "red")
_RUNNING_MARK: tuple[str, str] = (">", "bold")
_FAILURE_RESULTS: frozenset[str] = frozenset({"failed", "mismatch", "crashed"})


def outcome_mark(outcome: RowOutcome) -> tuple[str, str]:
    """Return the finished row's (glyph, style) for its result."""
    if outcome.result == "done":
        return _DONE_MARK
    if outcome.result in _FAILURE_RESULTS:
        return _FAILURE_MARK
    return HEALTH_MARKS[outcome.row.health or Health.CHECKING]


def outcome_word(outcome: RowOutcome) -> tuple[str, str]:
    """Return the finished row's (word, style), read only from the vocabulary."""
    if outcome.result == "done":
        words = WORDS[outcome.row.disposition]
        return (words.done or "", words.done_style)
    return RESULT_WORDS[outcome.result]


def outcome_detail_text(outcome: RowOutcome) -> str:
    """Return the UI-SPEC text after the finished word, or empty."""
    if outcome.result in {"done", "mismatch", "not_attempted"}:
        return ""
    if outcome.result == "failed":
        errors = outcome.install.errors if outcome.install is not None else ()
        if not errors and outcome.update is not None:
            errors = outcome.update.errors
        error = str(errors[-1]).splitlines()[0] if errors else "no method succeeded"
        return sanitize_log_line(error)
    if outcome.result == "dependency_failed":
        blockers = outcome.install.blocked_by if outcome.install is not None else ()
        return ", ".join(blockers) or "an earlier failure"
    if outcome.result == "crashed":
        return outcome.detail
    if outcome.result == "manual":
        return "see the setup steps in the log"
    if outcome.result == "skipped":
        return outcome.detail or outcome.row.reason.removesuffix(" (r: reinstall)")
    if outcome.result == "blocked":
        return outcome.detail or outcome.row.reason
    return ""


def outcome_row_text(outcome: RowOutcome, idw: int, width: int) -> Text:
    """Build one finished plan row: mark, id, word and the UI-SPEC text after it."""
    glyph, glyph_style = outcome_mark(outcome)
    row = outcome.row
    dragged = row.requested_by is not None
    indent = 2 if dragged else 0
    text = Text()
    text.append(glyph, style=glyph_style)
    text.append(" ")
    if dragged:
        text.append("  ")
    text.append(row.tool_id.ljust(max(0, idw - indent)), style="bold")
    text.append("  ")
    word, word_style = outcome_word(outcome)
    text.append(word, style=word_style)
    column = cell_len(glyph) + 1 + idw + 2
    detail = outcome_detail_text(outcome)
    if detail:
        fold_reason(text, " — " + sanitize_log_line(detail), column, width)
    return text


def running_row_text(row: PlanRow, idw: int, width: int) -> Text:
    """Build the in-flight row: the `>` mark, the id and the review word."""
    dragged = row.requested_by is not None
    indent = 2 if dragged else 0
    text = Text()
    text.append(_RUNNING_MARK[0], style=_RUNNING_MARK[1])
    text.append(" ")
    if dragged:
        text.append("  ")
    text.append(row.tool_id.ljust(max(0, idw - indent)), style="bold")
    text.append("  ")
    words = WORDS[row.disposition]
    text.append(words.review, style=words.style)
    return text


def summary_head(outcomes: Sequence[RowOutcome]) -> str:
    """Return the one stable finished line: `Summary — {counts}`."""
    return f"Summary — {summary_counts(outcomes)}"


def render_run_summary(
    outcomes: Sequence[RowOutcome], console: Console, *, width: int | None = None
) -> None:
    """Print the summary head and one outcome row per outcome in display order."""
    budget = min(console.width, 100) if width is None else width
    console.print(
        summary_head(outcomes), style="bold", markup=False, highlight=False, soft_wrap=True
    )
    rows = [outcome.row for outcome in outcomes]
    idw = id_width(rows)
    by_id = {outcome.row.tool_id: outcome for outcome in outcomes}
    for row in display_order(rows):
        outcome = by_id[row.tool_id]
        console.print(
            outcome_row_text(outcome, idw, budget),
            markup=False,
            highlight=False,
            soft_wrap=True,
        )


def render_plan(
    rows: Sequence[PlanRow], console: Console, *, width: int | None = None, hint: bool = False
) -> None:
    """Print the review head and folded plan rows in display order."""
    budget = min(console.width, 100) if width is None else width
    console.print(plan_head(rows), style="bold", markup=False, highlight=False, soft_wrap=True)
    idw = id_width(rows)
    for row in display_order(rows):
        console.print(
            plan_row_text(row, idw, budget, hint=hint),
            markup=False,
            highlight=False,
            soft_wrap=True,
        )


def render_update_notes(outcomes: Sequence[RowOutcome], console: Console) -> None:
    """Print successful update details that supplement the outcome row."""
    for outcome in outcomes:
        if outcome.result != "done" or outcome.row.disposition is not Disposition.UPDATE:
            continue
        update = outcome.update
        if update is None:
            continue
        notes = (
            [f"replayed {', '.join(update.replayed_globals)}"] if update.replayed_globals else []
        )
        notes.extend(update.cleanup_warnings)
        if update.postinstall_warning:
            notes.append(update.postinstall_warning)
        if update.detail:
            notes.append(update.detail)
        if notes:
            line = sanitize_log_line(
                f"{outcome.row.tool_id} {WORDS[Disposition.UPDATE].done} — {'; '.join(notes)}"
            )
            console.print(line, markup=False, highlight=False, soft_wrap=True)


def render_run_report(outcomes: Sequence[RowOutcome], console: Console) -> None:
    """Print the summary followed by every outcome report in one fixed order."""
    render_run_summary(outcomes, console)
    installs = [outcome.install for outcome in outcomes if outcome.install is not None]
    render_failure_details(installs, console)
    render_skipped(installs, console)
    render_handoff(installs, console)
    render_post_install_handoff(installs, console)
    render_postinstall_warnings(installs, console)
    render_update_notes(outcomes, console)
    render_verification(installs, console)


def render_failure_details(outcomes: list[InstallOutcome], console: Console) -> None:
    """Print the last ladder-method error for each failed tool.

    ``render_run_summary`` reports each result; this renderer supplies the
    actual exception, mirroring the checksum detail in
    ``render_checksum_verification``. Silent when nothing failed.
    """
    for outcome in outcomes:
        if outcome.status is not InstallStatus.FAILED:
            continue
        detail = str(outcome.errors[-1]) if outcome.errors else "no method succeeded"
        console.print(f"[red]✗ {outcome.tool_id} failed: {escape(sanitize_log_line(detail))}[/]")
        for err in outcome.errors[:-1]:
            first_line = str(err).splitlines()[0]
            console.print(
                f"  [dim]earlier method failed: {escape(sanitize_log_line(first_line))}[/]"
            )


def render_skipped(outcomes: list[InstallOutcome], console: Console) -> None:
    """Name every tool the run deliberately did not attempt and why.

    Silent when no dependency failed. The run summary carries counts; reasons
    live here.
    """
    for outcome in outcomes:
        if outcome.status is not InstallStatus.DEPENDENCY_FAILED:
            continue
        blockers = ", ".join(outcome.blocked_by) or "an earlier failure"
        console.print(f"[yellow]⚠ {outcome.tool_id} skipped — dependency failed: {blockers}[/]")


def render_postinstall_warnings(outcomes: list[InstallOutcome], console: Console) -> None:
    """Print each tool's postinstall warning, if any.

    The tool's own install has already succeeded (status stays INSTALLED) by
    the time this fires, so this is a secondary, non-fatal warning, never the
    reason an install is reported as failed. Silent when nothing warned,
    matching render_skipped's restraint.
    """
    for outcome in outcomes:
        if outcome.postinstall_warning:
            console.print(
                f"[yellow]⚠ {outcome.tool_id} postinstall warning: {outcome.postinstall_warning}[/]"
            )


def render_handoff(outcomes: list[InstallOutcome], console: Console) -> None:
    """Print each MANUAL_REQUIRED tool's reviewed setup instructions, in full.

    This is where the actual steps the user must run after the installer
    releases the terminal live. Silent when nothing needs a handoff, matching
    render_skipped's and render_postinstall_warnings' restraint.
    """
    for outcome in outcomes:
        if outcome.status is not InstallStatus.MANUAL_REQUIRED or not outcome.handoff:
            continue
        console.print(f"[cyan]{outcome.tool_id} — manual setup required:[/]")
        for line in outcome.handoff:
            console.print(f"  {line}")


def render_post_install_handoff(outcomes: list[InstallOutcome], console: Console) -> None:
    """Print reviewed follow-up steps for a tool that installed successfully.

    Distinct from ``render_handoff``, which prints steps for a tool that did
    not install (MANUAL_REQUIRED), and from ``render_postinstall_warnings``,
    which prints problems from the singular hook mechanism. This renderer
    prints optional follow-up instructions a successful install produced.
    Instruction lines are printed with markup disabled so a reviewed shell
    command's square brackets survive as literal text.
    """
    for outcome in outcomes:
        if not outcome.post_install_handoff:
            continue
        console.print(f"[cyan]{outcome.tool_id} — after install:[/]")
        for line in outcome.post_install_handoff:
            console.print(f"  {line}", markup=False)


def render_troubleshooting(console: Console) -> None:
    """Point the user at the troubleshooting guide."""
    console.print(f"Something went wrong. Troubleshooting: {TROUBLESHOOTING_URL}")


def render_uninstall(paths: list[Path], console: Console) -> None:
    """Preview the artifacts that will be removed (dry run)."""
    if not paths:
        console.print("Nothing to uninstall: no tools-installer artifacts found.")
        return
    console.print("The following will be removed:")
    for path in paths:
        console.print(f"  {path}", soft_wrap=True, markup=False)


def render_remove_yourself(paths: Sequence[Path], console: Console) -> None:
    """Name the on-disk matches this installer cannot prove it wrote.

    They are never deleted (SAFE-03/D-04); the user decides. The wording
    names only paths — no privilege-escalation commands, ever.
    """
    if not paths:
        return
    console.print(
        "Not removed (tools-installer cannot prove it installed these); "
        "remove them yourself if you want them gone:"
    )
    for path in paths:
        console.print(f"  {path}", soft_wrap=True, markup=False)


def render_rc_duplicates(found: dict[Path, list[str]], console: Console) -> None:
    """Preview duplicate PATH lines found per rc file (dry run)."""
    if not found:
        console.print("No duplicate PATH lines found in your shell rc files.")
        return
    console.print("These PATH lines duplicate directories already managed; they can be removed:")
    for rc_path, lines in found.items():
        console.print(f"  {rc_path}:")
        for line in lines:
            console.print(f"    {line}")


def guidance_text(items: list[Guidance]) -> Text:
    """Render guidance items as one colored block: title (by severity), meaning, next step.

    D-03's extra visual weight is a render concern, not a fourth Severity
    member (Severity is consumed structurally as a dict key elsewhere): a
    bold modifier is prepended to the resolved severity style whenever the
    item's `emphasis` flag is set. An item that does not set the flag renders
    with exactly today's plain severity style.
    """
    text = Text()
    for index, item in enumerate(items):
        if index:
            text.append("\n")
        style = SEVERITY_STYLE[item.severity]
        if item.emphasis:
            style = f"bold {style}"
        text.append(item.title, style=style)
        text.append(f"\n  {item.meaning}")
        if item.next_step:
            text.append(f"\n  → {item.next_step}")
    return text


def render_doctor(
    report: DoctorReport,
    console: Console,
    duplicate_writers: Mapping[Path, tuple[Path, ...]] | None = None,
) -> None:
    """Print each PATH finding with its meaning and exact next step (color by severity)."""
    console.print(guidance_text(doctor_guidance(report, duplicate_writers)))


def render_guard(
    actions: dict[str, str], warning: str | None, console: Console, *, removing: bool
) -> None:
    """Print the per-command shim actions, then any PATH-order warning."""
    verb = "Removing" if removing else "Installing"
    console.print(f"{verb} the pip/npm ban (shims + interactive aliases):")
    for name, what in actions.items():
        console.print(f"  {what}: {name}")
    if warning:
        console.print(warning)


def render_guard_status(status: dict[str, bool], warning: str | None, console: Console) -> None:
    """Read-only doctor lines: silent unless the ban is active or PATH order is off."""
    items = guard_guidance(status, warning)
    if items:
        console.print(guidance_text(items))


def render_node_globals(report: NodeGlobalsReport, console: Console) -> None:
    """Read-only doctor lines: silent unless a pnpm-managed global is missing."""
    items = node_globals_guidance(report)
    if items:
        console.print(guidance_text(items))


def render_disk_pressure(pressure: DiskPressure, console: Console) -> None:
    """Read-only doctor lines: silent unless disk pressure was measured.

    One named function per report section, matching render_doctor,
    render_guard_status and render_node_globals. An empty guidance list
    prints nothing — not a blank line, not a header — so a healthy machine's
    `make doctor` output stays byte-identical to a run that never probed.
    """
    items = disk_pressure_guidance(pressure)
    if items:
        console.print(guidance_text(items))


def render_competing_mechanisms(units: tuple[CompetingUnit, ...], console: Console) -> None:
    """Read-only WR-10 disclosure: silent unless a system-scope competitor
    was detected. Same shape as render_disk_pressure above."""
    items = competing_mechanism_guidance(units)
    if items:
        console.print(guidance_text(items))


def render_verification(outcomes: list[InstallOutcome], console: Console) -> None:
    """One line per verified download or app zip: sha256-verified, unverified, or mismatched.

    brew/native/script installs are omitted — those channels run their own
    integrity checks, so an 'unverified' label there would mislead. Outcomes
    with other statuses (failed, already-installed) are omitted too: no
    verification step ran for them. Outcomes carrying method_kind=None,
    dependency-failed among them, are omitted because no verification step ran
    for them.
    """
    verified_kinds = DOWNLOAD_KINDS + APP_KINDS
    for outcome in outcomes:
        if outcome.method_kind not in verified_kinds:
            continue
        if outcome.status == InstallStatus.INSTALLED:
            if outcome.verified:
                console.print(f"  {outcome.tool_id}: sha256 ✓")
            elif outcome.unverified_reason:
                console.print(
                    f"  {outcome.tool_id}: unverified ({escape(outcome.unverified_reason)})"
                )
            else:
                console.print(f"  {outcome.tool_id}: unverified")
        elif outcome.status == InstallStatus.CHECKSUM_MISMATCH:
            # The engine always carries the ChecksumMismatch in errors[0] for
            # this status; a malformed outcome should fail loudly here rather
            # than print a vague line (the same fail-closed principle as the session outcome fold).
            console.print(f"  {outcome.tool_id}: {escape(str(outcome.errors[0]))}")
