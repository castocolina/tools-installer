"""The interactive wizard flow: select -> audit -> confirm -> install -> summarize."""

from collections.abc import Callable

from rich.console import Console

from installer.audit import audit
from installer.cli import Options
from installer.engine import install_tool
from installer.model import Tool
from installer.platform import Platform
from installer.prompt import Prompter
from installer.render import render_audit, render_summary
from installer.run import Runner, run_command
from installer.selection import category_choices, select_tools, tool_choices
from installer.session import Install, Summary, order_for_install, run_installs, summarize
from installer.status import is_installed
from installer.versions import VersionResolver, resolve_github_version


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
    resolve_version: VersionResolver = resolve_github_version,
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
    outcomes = run_installs(ordered, platform, runner, resolve_version, install)
    summary = summarize(outcomes)
    render_summary(summary, console)
    return summary
