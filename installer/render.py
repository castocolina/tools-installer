"""Render the pre-flight audit and the post-install summary to a Console."""

from pathlib import Path

from rich.console import Console
from rich.table import Table

from installer.audit import ToolStatus
from installer.doctor import DoctorReport, has_problems
from installer.links import TROUBLESHOOTING_URL
from installer.session import Summary


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
        f"No method: {len(summary.no_method)}"
    )
    for label, ids in (
        ("installed", summary.installed),
        ("already installed", summary.already),
        ("failed", summary.failed),
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


def render_doctor(report: DoctorReport, console: Console) -> None:
    """Print the PATH audit; on any problem, also print the troubleshooting link."""
    if not has_problems(report):
        console.print("PATH looks healthy: all bin dirs present, on PATH, and unique.")
        return
    for label, dirs in (
        ("missing from PATH", report.missing),
        ("does not exist", report.broken),
        ("duplicated on PATH", report.duplicated),
    ):
        for directory in dirs:
            console.print(f"  {label}: {directory}")
    render_troubleshooting(console)
