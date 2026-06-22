"""Render the pre-flight audit and the post-install summary to a Console."""

from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from installer.audit import ToolStatus
from installer.doctor import DoctorReport
from installer.download import DOWNLOAD_KINDS
from installer.engine import InstallOutcome
from installer.guidance import Guidance, doctor_guidance, guard_guidance
from installer.links import TROUBLESHOOTING_URL
from installer.session import Summary
from installer.ui_common import SEVERITY_STYLE


def render_dependency_notice(
    dragged_in: tuple[str, ...],
    warnings: tuple[str, ...],
    console: Console,
) -> None:
    """Announce auto-added dependencies and any skip warnings. Silent when both
    are empty so the common no-dependency case prints nothing."""
    if dragged_in:
        console.print(
            f"[cyan]Added dependencies:[/] {', '.join(dragged_in)} (required by your selection)."
        )
    for warning in warnings:
        console.print(f"[yellow]⚠ {warning}[/]")


def render_audit(statuses: list[ToolStatus], console: Console) -> None:
    """Print a table of each selected tool, its category, and installed/missing."""
    table = Table(title="Pre-flight audit")
    table.add_column("Tool")
    table.add_column("Category")
    table.add_column("State")
    for status in statuses:
        state = "installed" if status.installed else "missing"
        table.add_row(status.tool.id, status.tool.category, state)
    console.print(table)


def render_summary(summary: Summary, console: Console) -> None:
    """Print install counts and the tool ids in each bucket."""
    console.print(
        f"Installed: {len(summary.installed)}  "
        f"Already: {len(summary.already)}  "
        f"Failed: {len(summary.failed)}  "
        f"Checksum mismatch: {len(summary.mismatched)}  "
        f"No method: {len(summary.no_method)}"
    )
    for label, ids in (
        ("installed", summary.installed),
        ("already installed", summary.already),
        ("failed", summary.failed),
        ("checksum mismatch", summary.mismatched),
        ("no method", summary.no_method),
    ):
        if ids:
            console.print(f"  {label}: {', '.join(ids)}")


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
        console.print(f"  {path}")


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
    """Render guidance items as one colored block: title (by severity), meaning, next step."""
    text = Text()
    for index, item in enumerate(items):
        if index:
            text.append("\n")
        text.append(item.title, style=SEVERITY_STYLE[item.severity])
        text.append(f"\n  {item.meaning}")
        if item.next_step:
            text.append(f"\n  → {item.next_step}")
    return text


def render_doctor(report: DoctorReport, console: Console) -> None:
    """Print each PATH finding with its meaning and exact next step (color by severity)."""
    console.print(guidance_text(doctor_guidance(report)))


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


def render_verification(outcomes: list[InstallOutcome], console: Console) -> None:
    """One line per download-based install: sha256-verified, unverified, or mismatched.

    brew/native/script installs are omitted — those channels run their own
    integrity checks, so an 'unverified' label there would mislead. Outcomes
    with other statuses (failed, already-installed) are omitted too: no
    verification step ran for them.
    """
    for outcome in outcomes:
        if outcome.method_kind not in DOWNLOAD_KINDS:
            continue
        if outcome.status == "installed":
            marker = "sha256 ✓" if outcome.verified else "unverified"
            console.print(f"  {outcome.tool_id}: {marker}")
        elif outcome.status == "checksum-mismatch":
            # The engine always carries the ChecksumMismatch in errors[0] for
            # this status; a malformed outcome should fail loudly here rather
            # than print a vague line (same philosophy as session.summarize).
            console.print(f"  {outcome.tool_id}: {outcome.errors[0]}")
