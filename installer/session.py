"""Orchestrate installs for a selection of tools and bucket the outcomes."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal, Protocol

from installer.engine import ChecksumPolicy, InstallOutcome, install_tool
from installer.enums import InstallStatus, Priority
from installer.model import Tool
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.run import Runner, run_command
from installer.update import UpdateOutcome
from installer.versions import TagResolver, resolve_github_tag

# The user's answer to a checksum mismatch: retry the download, skip the
# tool, or fall back to the remaining methods (brew/native).
MismatchChoice = Literal["retry", "skip", "fallback"]
OnMismatch = Callable[[str], MismatchChoice]

_PRIORITY_RANK = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2, Priority.P3: 3}
# Statuses meaning this tool is not on the machine after this run.
# DEPENDENCY_FAILED is a member of its own set on purpose: that membership,
# and nothing else, is what carries a failure down a multi-link requires chain.
# MANUAL_REQUIRED belongs here too: the tool only got as far as reviewed
# handoff instructions (host_setup / skill_pack), not an actual install, so a
# dependent naming it in `requires` must be blocked the same as any other
# not-actually-installed status.
_UNRESOLVED: frozenset[InstallStatus] = frozenset(
    {
        InstallStatus.FAILED,
        InstallStatus.NO_METHOD,
        InstallStatus.CHECKSUM_MISMATCH,
        InstallStatus.DEPENDENCY_FAILED,
        InstallStatus.MANUAL_REQUIRED,
    }
)


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
        tools: Mapping[str, Tool] | None = ...,
    ) -> InstallOutcome: ...


class SensitiveInstall(Protocol):
    """An install callable that also accepts a sensitive-action confirmation."""

    def __call__(
        self,
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = ...,
        tools: Mapping[str, Tool] | None = ...,
        confirm_sensitive_action: ConfirmSensitiveAction | None = ...,
    ) -> InstallOutcome: ...


def with_sensitive_confirm(
    confirm: ConfirmSensitiveAction | None,
    install: SensitiveInstall = install_tool,
) -> Install:
    """Bind a confirmation onto an install without widening ``Install``.

    Adding ``confirm_sensitive_action`` to the shared ``Install`` protocol
    would force a mechanical edit into every fake install in the suite and
    into ``attributed_install``. Binding at a composition point instead
    leaves that protocol byte-identical. Callers: ``run_wizard`` (plan
    14-04) and the in-TUI execute path (plan 14-05).
    """

    def bound(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        return install(
            tool,
            platform,
            runner,
            resolve_tag,
            checksum_policy=checksum_policy,
            tools=tools,
            confirm_sensitive_action=confirm,
        )

    return bound


@dataclass(frozen=True)
class Summary:
    installed: tuple[str, ...]
    already: tuple[str, ...]
    failed: tuple[str, ...]
    no_method: tuple[str, ...]
    mismatched: tuple[str, ...] = ()
    dependency_failed: tuple[str, ...] = ()
    manual_required: tuple[str, ...] = ()
    not_attempted: tuple[str, ...] = ()
    update_failed: tuple[str, ...] = ()
    crash_error: str | None = None

    @property
    def has_failure(self) -> bool:
        """Whether this run reported a failure the exit code must surface.

        manual_required and no_method do not count: a handoff the user must
        run themselves, and a tool that was never installable on this
        platform, are not errors (the pre-existing setup.py rule, D-08).
        """
        return bool(
            self.failed
            or self.mismatched
            or self.dependency_failed
            or self.not_attempted
            or self.update_failed
            or self.crash_error is not None
        )


def fold_run(
    summary: Summary,
    *,
    not_attempted: Sequence[str],
    update_outcomes: Sequence[UpdateOutcome],
    update_errors: Sequence[tuple[str, str]],
    error: str | None,
) -> Summary:
    """Fold one run's worker-reported outcome collections into a Summary.

    The single pure fold both ExecuteScreen (status colour) and UnifiedApp
    (session accumulation) call, so the two cannot disagree about what counts
    as a failure (D-08). update_failed keeps outcome order first, then error
    order, duplicates dropped. unknown-owner/unsupported outcomes and skips
    are not failures (RESEARCH Pattern 3).
    """
    ids: list[str] = [o.tool_id for o in update_outcomes if o.status == "failed"]
    ids.extend(tool_id for tool_id, _message in update_errors)
    return replace(
        summary,
        not_attempted=tuple(not_attempted),
        update_failed=tuple(dict.fromkeys(ids)),
        crash_error=error,
    )


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
    catalog: Mapping[str, Tool] | None = None,
    *,
    should_continue: Callable[[], bool] | None = None,
) -> list[InstallOutcome]:
    """Install each tool in turn, collecting one outcome per tool.

    On a checksum mismatch, consult on_mismatch (when given): retry re-runs
    the install once, fallback re-runs it letting the ladder continue past
    the mismatch, skip keeps the mismatch outcome. No callback = unattended
    mode: the hard-fail outcome stands.

    A tool whose requires names anything unresolved earlier in THIS call is
    reported dependency-failed and never attempted. This is a single forward
    pass, correct because the caller is expected to pass the
    deps-first topological order resolve_dependencies produces, so a
    dependency is always visited before anything requiring it. run_installs
    does not sort and must not start sorting — requires plus
    resolve_dependencies remains the only ordering mechanism. When that
    invariant is violated, dependents of failed tools are
    attempted rather than skipped, which is the behaviour this function had
    before this change and is never a crash.

    `catalog`, when given, is threaded into every `install(...)` call as its
    `tools` keyword — this is how a postinstall hook's host-presence check
    reaches the full loaded catalog without run_installs needing to know
    anything about postinstall itself.

    `should_continue`, when given, is checked between tools and never during
    one. Returning False stops queuing the remainder and returns the
    outcomes gathered so far; tools never reached are absent from that list
    rather than given a new status. This is a weak cancel: an in-flight
    child is allowed to finish, because killing a half-written install is
    worse than waiting.
    """
    outcomes: list[InstallOutcome] = []
    unresolved: set[str] = set()
    for tool in tools:
        if should_continue is not None and not should_continue():
            break
        blocked = tuple(dep_id for dep_id in dict.fromkeys(tool.requires) if dep_id in unresolved)
        if blocked:
            outcome = InstallOutcome(tool.id, InstallStatus.DEPENDENCY_FAILED, blocked_by=blocked)
        else:
            outcome = install(tool, platform, runner, resolve_tag, tools=catalog)
            if outcome.status == InstallStatus.CHECKSUM_MISMATCH and on_mismatch is not None:
                choice = on_mismatch(tool.id)
                if choice == "retry":
                    outcome = install(tool, platform, runner, resolve_tag, tools=catalog)
                elif choice == "fallback":
                    outcome = install(
                        tool,
                        platform,
                        runner,
                        resolve_tag,
                        checksum_policy="continue",
                        tools=catalog,
                    )
        if outcome.status in _UNRESOLVED:
            unresolved.add(tool.id)
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
        InstallStatus.DEPENDENCY_FAILED: [],
        InstallStatus.MANUAL_REQUIRED: [],
    }
    for outcome in outcomes:
        buckets[outcome.status].append(outcome.tool_id)
    return Summary(
        installed=tuple(buckets[InstallStatus.INSTALLED]),
        already=tuple(buckets[InstallStatus.ALREADY_INSTALLED]),
        failed=tuple(buckets[InstallStatus.FAILED]),
        no_method=tuple(buckets[InstallStatus.NO_METHOD]),
        mismatched=tuple(buckets[InstallStatus.CHECKSUM_MISMATCH]),
        dependency_failed=tuple(buckets[InstallStatus.DEPENDENCY_FAILED]),
        manual_required=tuple(buckets[InstallStatus.MANUAL_REQUIRED]),
    )
