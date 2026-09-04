"""Orchestrate installs for a selection of tools and bucket the outcomes."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from installer.engine import ChecksumPolicy, InstallOutcome, install_tool
from installer.enums import InstallStatus, Priority
from installer.model import Tool
from installer.platform import Platform
from installer.run import Runner, run_command
from installer.versions import TagResolver, resolve_github_tag

# The user's answer to a checksum mismatch: retry the download, skip the
# tool, or fall back to the remaining methods (brew/native).
MismatchChoice = Literal["retry", "skip", "fallback"]
OnMismatch = Callable[[str], MismatchChoice]

_PRIORITY_RANK = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2, Priority.P3: 3}


class Install(Protocol):
    """Matches engine.install_tool, including the keyword-only checksum policy."""

    def __call__(
        self,
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = ...,
    ) -> InstallOutcome: ...


@dataclass(frozen=True)
class Summary:
    installed: tuple[str, ...]
    already: tuple[str, ...]
    failed: tuple[str, ...]
    no_method: tuple[str, ...]
    mismatched: tuple[str, ...] = ()


def order_for_install(tools: list[Tool]) -> list[Tool]:
    """Stable sort by priority (P0 first); ties keep catalog order."""
    return sorted(tools, key=lambda tool: _PRIORITY_RANK.get(tool.priority, 99))


def run_installs(
    tools: list[Tool],
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: Install = install_tool,
    on_mismatch: OnMismatch | None = None,
) -> list[InstallOutcome]:
    """Install each tool in turn, collecting one outcome per tool.

    On a checksum mismatch, consult on_mismatch (when given): retry re-runs
    the install once, fallback re-runs it letting the ladder continue past
    the mismatch, skip keeps the mismatch outcome. No callback = unattended
    mode: the hard-fail outcome stands.
    """
    outcomes: list[InstallOutcome] = []
    for tool in tools:
        outcome = install(tool, platform, runner, resolve_tag)
        if outcome.status == InstallStatus.CHECKSUM_MISMATCH and on_mismatch is not None:
            choice = on_mismatch(tool.id)
            if choice == "retry":
                outcome = install(tool, platform, runner, resolve_tag)
            elif choice == "fallback":
                outcome = install(tool, platform, runner, resolve_tag, checksum_policy="continue")
        outcomes.append(outcome)
    return outcomes


def summarize(outcomes: list[InstallOutcome]) -> Summary:
    """Bucket outcome tool ids by status.

    The keys mirror engine.Status (a closed Literal); an out-of-range status
    is impossible under pyright and would surface as a KeyError if one ever
    slipped through, rather than being silently dropped.
    """
    buckets: dict[InstallStatus, list[str]] = {
        InstallStatus.INSTALLED: [],
        InstallStatus.ALREADY_INSTALLED: [],
        InstallStatus.FAILED: [],
        InstallStatus.NO_METHOD: [],
        InstallStatus.CHECKSUM_MISMATCH: [],
    }
    for outcome in outcomes:
        buckets[outcome.status].append(outcome.tool_id)
    return Summary(
        installed=tuple(buckets[InstallStatus.INSTALLED]),
        already=tuple(buckets[InstallStatus.ALREADY_INSTALLED]),
        failed=tuple(buckets[InstallStatus.FAILED]),
        no_method=tuple(buckets[InstallStatus.NO_METHOD]),
        mismatched=tuple(buckets[InstallStatus.CHECKSUM_MISMATCH]),
    )
