"""Orchestrate installs for a selection of tools and bucket the outcomes."""

from collections.abc import Callable
from dataclasses import dataclass

from installer.engine import InstallOutcome, install_tool
from installer.model import Tool
from installer.platform import Platform
from installer.run import Runner, run_command
from installer.versions import TagResolver, resolve_github_tag

# (tool, platform, runner, resolve_tag) -> outcome. Matches engine.install_tool.
Install = Callable[[Tool, Platform, Runner, TagResolver], InstallOutcome]

_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass(frozen=True)
class Summary:
    installed: tuple[str, ...]
    already: tuple[str, ...]
    failed: tuple[str, ...]
    no_method: tuple[str, ...]


def order_for_install(tools: list[Tool]) -> list[Tool]:
    """Stable sort by priority (P0 first); ties keep catalog order."""
    return sorted(tools, key=lambda tool: _PRIORITY_RANK.get(tool.priority, 99))


def run_installs(
    tools: list[Tool],
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: Install = install_tool,
) -> list[InstallOutcome]:
    """Install each tool in turn, collecting one outcome per tool."""
    return [install(tool, platform, runner, resolve_tag) for tool in tools]


def summarize(outcomes: list[InstallOutcome]) -> Summary:
    """Bucket outcome tool ids by status.

    The keys mirror engine.Status (a closed Literal); an out-of-range status
    is impossible under pyright and would surface as a KeyError if one ever
    slipped through, rather than being silently dropped.
    """
    buckets: dict[str, list[str]] = {
        "installed": [],
        "already-installed": [],
        "failed": [],
        "no-method": [],
    }
    for outcome in outcomes:
        buckets[outcome.status].append(outcome.tool_id)
    return Summary(
        installed=tuple(buckets["installed"]),
        already=tuple(buckets["already-installed"]),
        failed=tuple(buckets["failed"]),
        no_method=tuple(buckets["no-method"]),
    )
