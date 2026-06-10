"""The interactive wizard flow: select -> audit -> confirm -> install -> summarize."""

from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from installer.audit import audit
from installer.cli import Options
from installer.doctor import DoctorReport, audit_path
from installer.engine import install_tool
from installer.model import Tool
from installer.platform import Platform
from installer.prompt import Prompter
from installer.render import render_audit, render_doctor, render_summary
from installer.run import Runner, run_command
from installer.selection import category_choices, select_tools, tool_choices
from installer.session import Install, Summary, order_for_install, run_installs, summarize
from installer.shellrc import collect_bin_dirs, ensure_source, write_myshellrc
from installer.status import is_installed
from installer.versions import TagResolver, resolve_github_tag


def _choose_tools(
    tools: list[Tool],
    prompter: Prompter,
    options: Options,
    installed: Callable[[Tool], bool],
) -> list[Tool]:
    if options.all:
        return tools
    if options.categories:
        return [tool for tool in tools if tool.category in options.categories]
    chosen_categories = prompter.select_categories(category_choices(tools))
    wanted = set(chosen_categories)
    in_categories = [tool for tool in tools if tool.category in wanted]
    statuses = audit(in_categories, installed)
    chosen_ids = prompter.select_tools(tool_choices(statuses))
    return select_tools(in_categories, chosen_ids)


def run_wizard(
    tools: list[Tool],
    platform: Platform,
    prompter: Prompter,
    console: Console,
    options: Options,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: Install = install_tool,
    installed: Callable[[Tool], bool] = is_installed,
) -> Summary | None:
    """Drive the full wizard. Returns the install summary, or None if the user declined.

    None (aborted) is distinct from an empty Summary (ran, but nothing to install).
    """
    selected = _choose_tools(tools, prompter, options, installed)
    statuses = audit(selected, installed)
    render_audit(statuses, console)
    if not options.yes and not prompter.confirm("Install the selected tools?"):
        return None
    ordered = order_for_install(selected)
    outcomes = run_installs(ordered, platform, runner, resolve_tag, install)
    summary = summarize(outcomes)
    render_summary(summary, console)
    return summary


def configure_path(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
) -> None:
    """Write the managed PATH block and wire `source` into every rc path.

    Each rc file is wired idempotently; an absent rc file is created so the PATH
    block is sourced even on a fresh machine with no shell rc yet.
    """
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir)
    write_myshellrc(bin_dirs, myshellrc_path)
    for rc_path in rc_paths:
        ensure_source(rc_path, myshellrc_path)
    console.print(f"PATH configured in {myshellrc_path} (restart your shell or source it).")


def run_doctor(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    path_value: str,
    exists: Callable[[Path], bool],
    myshellrc_path: Path,
    rc_paths: list[Path],
    fix: bool,
) -> DoctorReport:
    """Audit the PATH, render the report, and (if fix) write the managed config."""
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir)
    report = audit_path(bin_dirs, path_value, exists)
    render_doctor(report, console)
    if fix:
        configure_path(
            tools,
            console,
            platform=platform,
            default_bin_dir=default_bin_dir,
            myshellrc_path=myshellrc_path,
            rc_paths=rc_paths,
        )
    return report
