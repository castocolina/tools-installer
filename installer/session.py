"""Build and execute tool-install plans with one vocabulary and one run engine.

The Phase 20 model (`Disposition`, `PlanRow`, `WORDS`, and `build_plan`) and
its executor (`execute_plan`) live together here.
"""

import os
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, get_args

from installer import executors, postinstall, receipts
from installer.agent_settings import (
    AGENT_FORMATS,
    FORMAT_NAMES,
    FileResult,
    apply_setting,
    file_problem,
    setting_keys,
    settings_file,
)
from installer.deps import Blocked, resolve_dependencies
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import InstallStatus, Priority
from installer.env_redirect import (
    DESKTOP_SHELL_CONF,
    environment_d_dir,
    shell_redirect,
    write_linux_redirect,
)
from installer.locations import display_path
from installer.model import ConfigStep, ConfigStepKind, Tool
from installer.ownership import (
    UNMANAGEABLE_OWNERS,
    ManagerOwnership,
    declared_manager_label,
    owner_label,
)
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.postinstall import hook_method, host_labels, register_hooks
from installer.receipts import CHANGED_SINCE_INSTALL, CONFIG_AGENTS
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner
from installer.selection import select_tools
from installer.update import UpdateOutcome, UpdateService, UpdateTarget, update_refusal
from installer.version_status import Health, ToolState
from installer.versions import TagResolver, VersionError

# The user's answer to a checksum mismatch: retry the download, skip the
# tool, or fall back to the remaining methods (brew/native).
MismatchChoice = Literal["retry", "skip", "fallback"]
OnMismatch = Callable[[str], MismatchChoice]

_PRIORITY_RANK = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2, Priority.P3: 3}
# Statuses meaning this tool is not on the machine after an install/repair row.
# DEPENDENCY_FAILED is a member of its own set on purpose: that membership,
# and nothing else, is what carries a failure down a multi-link requires chain.
# MANUAL_REQUIRED belongs here too: the tool only got as far as reviewed
# handoff instructions (host_setup), not an actual install, so a
# dependent naming it in `requires` must be blocked the same as any other
# not-actually-installed status.
# A row that starts from an installed tool loses it only when a reinstall ran and failed.
_PRESENT_TOOL_LOST: frozenset[InstallStatus] = frozenset(
    {InstallStatus.FAILED, InstallStatus.CHECKSUM_MISMATCH}
)

_UNRESOLVED: frozenset[InstallStatus] = frozenset(
    {
        InstallStatus.FAILED,
        InstallStatus.NO_METHOD,
        InstallStatus.CHECKSUM_MISMATCH,
        InstallStatus.DEPENDENCY_FAILED,
        InstallStatus.MANUAL_REQUIRED,
    }
)


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
        confirm_sensitive_action: ConfirmSensitiveAction | None = ...,
    ) -> InstallOutcome: ...


def order_for_install(tools: list[Tool]) -> list[Tool]:
    """Stable sort by priority (P0 first); ties keep catalog order."""
    return sorted(tools, key=lambda tool: _PRIORITY_RANK.get(tool.priority, 99))


class Disposition(StrEnum):
    """What the plan will do to one row. Declaration order is the review order."""

    WAIT = "wait"
    INSTALL = "install"
    UPDATE = "update"
    REPAIR = "repair"
    RECONFIGURE = "reconfigure"
    REINSTALL = "reinstall"
    SKIP = "skip"
    BLOCKED = "blocked"
    MANUAL = "manual"
    REMOVE = "remove"


Result = Literal[
    "done",
    "failed",
    "mismatch",
    "dependency_failed",
    "not_attempted",
    "crashed",
    "skipped",
    "blocked",
    "manual",
    "remove_failed",
]

# The dispositions an engine runs; SKIP, BLOCKED and WAIT never reach one.
RUNNABLE: frozenset[Disposition] = frozenset(
    {
        Disposition.INSTALL,
        Disposition.UPDATE,
        Disposition.REPAIR,
        Disposition.RECONFIGURE,
        Disposition.REINSTALL,
    }
)


@dataclass(frozen=True)
class Words:
    """One disposition's review word, done word (None for WAIT) and colors."""

    review: str
    done: str | None
    style: str
    done_style: str = "green"


WORDS: dict[Disposition, Words] = {
    Disposition.WAIT: Words("checking…", None, "dim", done_style="dim"),
    Disposition.INSTALL: Words("will install", "installed", "green"),
    Disposition.UPDATE: Words("will update", "updated", "yellow"),
    Disposition.REPAIR: Words("will repair", "repaired", "yellow"),
    Disposition.RECONFIGURE: Words("will reconfigure", "reconfigured", "yellow"),
    Disposition.REINSTALL: Words("will be reinstalled", "reinstalled", "yellow"),
    Disposition.SKIP: Words("skipped", "skipped", "dim", done_style="dim"),
    Disposition.BLOCKED: Words("blocked", "blocked", "red", done_style="red"),
    Disposition.MANUAL: Words("manual", "manual", "yellow", done_style="yellow"),
    Disposition.REMOVE: Words("will remove", "removed", "red", done_style="green"),
}

# Every non-done result. `done` has no entry: its word is the disposition's done word.
RESULT_WORDS: dict[Result, tuple[str, str]] = {
    "failed": ("failed", "red"),
    "mismatch": ("checksum mismatch", "red"),
    "dependency_failed": ("dependency failed", "red"),
    "not_attempted": ("not attempted", "red"),
    "crashed": ("crashed", "red"),
    "manual": ("manual", "yellow"),
    "skipped": ("skipped", "dim"),
    "blocked": ("blocked", "red"),
    "remove_failed": ("remove failed", "red"),
}


@dataclass(frozen=True)
class PlanRow:
    """One row of the install plan. `health` None means the state is still checking."""

    tool_id: str
    disposition: Disposition
    reason: str
    requested_by: str | None = None
    health: Health | None = None
    can_reinstall: bool = False
    steps: tuple[ConfigStep, ...] = ()
    ownership: ManagerOwnership | None = None
    # Only on MANUAL: the exact command the user runs, from executors.needs_manual.
    manual_command: str | None = None


@dataclass(frozen=True)
class RowOutcome:
    row: PlanRow
    result: Result
    install: InstallOutcome | None = None
    update: UpdateOutcome | None = None
    detail: str = ""
    # The end-of-run sweep's answer for a new agent host: (tool id, harness ids registered).
    resynced: tuple[tuple[str, tuple[str, ...]], ...] = ()
    resync_warnings: tuple[tuple[str, str], ...] = ()
    # The tuning writes this row made to its settings file, and whether an option skipped it.
    settings: tuple[FileResult, ...] = ()
    settings_skipped: bool = False
    # The desktop SHELL conf: (display path, zsh path) when written, (display path, error) when not.
    desktop_shell: tuple[str, str] | None = None
    desktop_shell_error: tuple[str, str] | None = None


@dataclass(frozen=True)
class RunContext:
    catalog: Mapping[str, Tool]
    platform: Platform
    runner: Runner
    resolve_tag: TagResolver
    install: SensitiveInstall
    updates: UpdateService | None = None
    terminal_sync: Callable[[], str | None] | None = None
    on_mismatch: OnMismatch | None = None
    confirm_sensitive: ConfirmSensitiveAction | None = None
    should_continue: Callable[[], bool] | None = None
    on_row_started: Callable[[PlanRow], None] | None = None
    on_outcome: Callable[[RowOutcome], None] | None = None
    # The run options the user switched on; empty by default, so a run writes no setting (D-09).
    options: frozenset[str] = frozenset()


_REVIEW_ORDER: tuple[Disposition, ...] = (
    *(d for d in Disposition if d is not Disposition.WAIT),
    Disposition.WAIT,
)


def _count_line(words: Iterable[str], order: Sequence[str]) -> str:
    """Non-zero counts of `words` in `order`, comma-joined; `nothing selected` when empty."""
    counts = Counter(words)
    parts = [f"{counts[word]} {word}" for word in order if counts[word]]
    return ", ".join(parts) or "nothing selected"


def review_counts(rows: Sequence[PlanRow]) -> str:
    """The plan head's counts over review words, e.g. `2 will install, 1 skipped`."""
    order = [WORDS[d].review for d in _REVIEW_ORDER]
    return _count_line((WORDS[row.disposition].review for row in rows), order)


_FAILURE = frozenset(
    {"failed", "mismatch", "dependency_failed", "not_attempted", "crashed", "remove_failed"}
)
_KEEP = _FAILURE | {"blocked", "manual"}
# These results represent executed work.
_RAN = frozenset({"done", "failed", "mismatch", "crashed"})


def exit_code(outcomes: Iterable[RowOutcome]) -> int:
    return int(any(outcome.result in _FAILURE for outcome in outcomes))


def retained(outcomes: Sequence[RowOutcome]) -> set[str]:
    return {outcome.row.tool_id for outcome in outcomes if outcome.result in _KEEP}


def ran_anything(outcomes: Sequence[RowOutcome]) -> bool:
    return any(outcome.result in _RAN for outcome in outcomes)


def summary_counts(outcomes: Sequence[RowOutcome]) -> str:
    order = [word for disposition in _REVIEW_ORDER if (word := WORDS[disposition].done) is not None]
    order.extend(
        RESULT_WORDS[result][0]
        for result in (
            "skipped",
            "blocked",
            "manual",
            "failed",
            "mismatch",
            "dependency_failed",
            "not_attempted",
            "crashed",
            "remove_failed",
        )
    )
    order = list(dict.fromkeys(order))
    words = (
        WORDS[outcome.row.disposition].done
        if outcome.result == "done"
        else RESULT_WORDS[outcome.result][0]
        for outcome in outcomes
    )
    return _count_line((word for word in words if word is not None), order)


def _with_force(
    install: Callable[..., InstallOutcome],
    force_ids: frozenset[str],
    confirm: ConfirmSensitiveAction | None,
) -> SensitiveInstall:
    """Pass repair=True only for repair and reinstall plan rows.

    Every other row calls `install` without the keyword at all, so an install
    seam that never learned about repair (every plain fake) keeps working.
    """

    def forced(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        kwargs: dict[str, object] = {
            "checksum_policy": checksum_policy,
            "confirm_sensitive_action": confirm,
        }
        if tool.id in force_ids:
            kwargs["repair"] = True
        return install(tool, platform, runner, resolve_tag, **kwargs)

    return forced


def first_line(exc: Exception) -> str:
    """The exception's first line, or its type name when it carries no message."""
    text = str(exc).splitlines()[0] if str(exc) else ""
    return text or f"{type(exc).__name__} failed"


@dataclass(frozen=True)
class _StepResult:
    """One step's answer: a refusal detail or a warning.

    `failed` means the step did not take and the row stops. `warning` means it
    ran and has something to report.
    """

    failed: str | None = None
    warning: str | None = None


# The kinds the model declares. The dispatcher below branches on every
# member and `test_each_config_step_kind_dispatches` asserts this set equals
# `get_args(ConfigStepKind)`, so a ninth kind added to the model fails there
# instead of reaching a command path no one reviewed.
_STEP_KINDS: frozenset[str] = frozenset(get_args(ConfigStepKind))


def _first_line_of(text: str) -> str:
    """The first line of a warning or refusal, for a one-line row detail."""
    return text.splitlines()[0]


def _register_hook_step(tool: Tool, ctx: RunContext) -> _StepResult:
    """Register the present hosts the hook's receipt does not record, then record them (D-02).

    `register_hooks` already subtracts the recorded hosts and writes what it registered;
    a run with nothing left to register is a failure with a reason, never an empty `done`.
    """
    receipt = receipts.read(tool.id)
    method = hook_method(tool, receipt) if receipt is not None else None
    if receipt is None or method is None:
        return _StepResult(failed="no install receipt to record the hook in")
    registered, warning = register_hooks(tool, method, ctx.runner)
    if registered:
        note = f"registered for {host_labels(registered)}"
        return _StepResult(warning=f"{note}; {_first_line_of(warning)}" if warning else note)
    if warning:
        return _StepResult(failed=_first_line_of(warning))
    return _StepResult(failed="no unregistered host is present any more")


def _run_step(step: ConfigStep, tool: Tool, ctx: RunContext) -> _StepResult:
    """Run one typed `ConfigStep` through the context's single runner seam."""
    if step.kind not in _STEP_KINDS:
        # A kind the model does not declare gets no command, not even a
        # plausible-looking argv one: its producer is unreviewed, so refusing
        # is the only answer that cannot run something nobody agreed to.
        return _StepResult(failed="step kind has no branch")
    if step.kind == "hook_register":
        return _register_hook_step(tool, ctx)
    if step.kind in {"terminal_sync", "zshenv_shell"}:
        if ctx.terminal_sync is None:
            return _StepResult(failed="no terminal synchronizer bound")
        try:
            warning = ctx.terminal_sync()
        except Exception as exc:
            return _StepResult(failed=first_line(exc))
        if step.kind == "terminal_sync":
            # The synchronizer's own warning wins; a clean run reports the step's done note.
            return _StepResult(warning=warning or step.report)
        # A .zshenv write that failed is the step failing, never a claimed export (CR-05).
        if warning and "zshenv: " in warning:
            return _StepResult(failed=warning[warning.index("zshenv: ") :].split("; ")[0])
        shown = step.report.partition("\n")[2] or "~/.zshenv"
        return _StepResult(warning=warning or f"{shown} exports SHELL")
    if step.kind == "pnpm_group_install":
        method = next((m for m in tool.methods if m.kind == "node"), None)
        if method is None:
            return _StepResult(failed="no node method declares the group")
        # L-19-28: the whole pinned group, `--allow-build`, real pnpm and the
        # smoke check — the same executor install and update already use.
        # Its refusals (no pnpm on PATH, a floor not met, a malformed pin) are
        # expected answers with a sentence the user can act on, so they read as
        # a failed step like the engine's own per-method catch, not `crashed`.
        try:
            executors.execute(method, ctx.runner)
        except (CommandError, OSError, executors.ExecutorError, VersionError) as exc:
            return _StepResult(failed=first_line(exc))
        return _StepResult()
    return _StepResult(failed="step kind has no branch")


def _run_reconfigure(row: PlanRow, tool: Tool, ctx: RunContext) -> RowOutcome:
    """Run the row's steps in order and stop at the first failure.

    The order is the fix (19 D-18): the canonical copy is enabled before the
    duplicates are removed, so continuing past a failed enable would delete
    the only working copy.
    """
    warnings: list[str] = []
    for step in row.steps:
        result = _run_step(step, tool, ctx)
        if result.failed is not None:
            return RowOutcome(row, "failed", detail=f"{step.text}: {result.failed}")
        if result.warning:
            warnings.append(result.warning)
    return RowOutcome(row, "done", detail="\n".join(warnings))


_INSTALL_RESULT: dict[InstallStatus, Result] = {
    InstallStatus.INSTALLED: "done",
    InstallStatus.ALREADY_INSTALLED: "skipped",
    InstallStatus.FAILED: "failed",
    InstallStatus.CHECKSUM_MISMATCH: "mismatch",
    InstallStatus.DEPENDENCY_FAILED: "dependency_failed",
    InstallStatus.MANUAL_REQUIRED: "manual",
    InstallStatus.NO_METHOD: "blocked",
}


# The rows whose install can add an agent host, and the catalog ids of those hosts.
_HOST_INSTALL_DISPOSITIONS: frozenset[Disposition] = frozenset(
    {Disposition.INSTALL, Disposition.REPAIR, Disposition.REINSTALL}
)
_HOST_CATALOG_IDS: frozenset[str] = frozenset(postinstall.HOST_CATALOG_IDS.values())


def _resync_hooks(outcomes: list[RowOutcome], ctx: RunContext) -> list[RowOutcome]:
    """D-03: when a run installed an agent host, register each installed hook tool for it.

    One sweep after every row, reading the present hosts once. Only a receipt with a hooks
    entry takes part, an empty one included (the tool was installed before any host, CR-06):
    a receipt written before hooks were recorded is left to RECONFIGURE,
    whose unrecorded hosts already read `≈`. `register_hooks` never re-runs a recorded host.
    shortcut: the sweep's command output is attributed to the last host row in the TUI log,
    upgrade when the log gains a run-level attribution.
    """
    installed = [
        index
        for index, outcome in enumerate(outcomes)
        if outcome.row.disposition in _HOST_INSTALL_DISPOSITIONS
        and outcome.result == "done"
        and outcome.row.tool_id in _HOST_CATALOG_IDS
    ]
    if not installed:
        return outcomes
    present = postinstall.present_hosts()
    resynced: list[tuple[str, tuple[str, ...]]] = []
    warnings: list[tuple[str, str]] = []
    for tool in ctx.catalog.values():
        name = tool.postinstall or ""
        pair = postinstall.POSTINSTALL_HOOKS.get(name)
        if pair is None or pair.targets is None:
            continue
        receipt = receipts.read(tool.id)
        method = hook_method(tool, receipt) if receipt is not None else None
        if receipt is None or method is None or name not in receipt.hooks:
            continue
        try:
            registered, warning = register_hooks(tool, method, ctx.runner, hosts=present)
        except Exception as exc:  # the sweep is never a failed row; its failure is a warning
            registered, warning = (), first_line(exc)
        if registered:
            resynced.append((tool.id, registered))
        if warning:
            warnings.append((tool.id, _first_line_of(warning)))
    last = installed[-1]
    outcomes[last] = replace(
        outcomes[last], resynced=tuple(resynced), resync_warnings=tuple(warnings)
    )
    return outcomes


# The run options, in the order the review shows them (UI-SPEC section 1).
RUN_OPTIONS: tuple[str, ...] = (
    "auto-approve",
    "no-attribution",
    "vscode-lean",
    "vscode-ai-off",
    "vscode-ext-updates-off",
    "desktop-shell",
)


def _ids_with_setting(setting: str) -> tuple[str, ...]:
    """The agents whose settings file holds this setting; the set does not depend on the OS."""
    return tuple(agent for agent in CONFIG_AGENTS if setting_keys(agent, setting, "linux"))


AGENT_OPTION_IDS: tuple[str, ...] = _ids_with_setting("auto-approve")
ATTRIBUTION_IDS: tuple[str, ...] = _ids_with_setting("no-attribution")
# Agents with no documented attribution key; pi has no ledger agent, so it stays a literal.
NO_ATTRIBUTION_KEY_IDS: tuple[str, ...] = ("codex", "opencode", "pi")
# Each option's (settings group, row ids it covers).
OPTION_COVERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "auto-approve": ("auto-approve", AGENT_OPTION_IDS),
    "no-attribution": ("no-attribution", ATTRIBUTION_IDS),
    "vscode-lean": ("vscode-lean", ("vscode",)),
    "vscode-ai-off": ("vscode-ai-off", ("vscode",)),
    "vscode-ext-updates-off": ("vscode-ext-updates-off", ("vscode",)),
}


# The rows whose settings the desktop SHELL option can export (its environment.d conf).
_DESKTOP_SHELL_IDS: frozenset[str] = frozenset({"zsh", "kitty", "wezterm"})


def run_options(rows: Sequence[PlanRow], platform_os: str) -> tuple[str, ...]:
    """The options a plan shows: each only when a runnable row triggers it (UI-SPEC O2)."""
    shown: set[str] = set()
    for row in rows:
        if row.disposition not in RUNNABLE:
            continue
        if row.tool_id in AGENT_OPTION_IDS:
            shown.add("auto-approve")
        if row.tool_id in ATTRIBUTION_IDS:
            shown.add("no-attribution")
        if row.tool_id == "vscode":
            shown.update(("vscode-lean", "vscode-ai-off", "vscode-ext-updates-off"))
        if platform_os != "macos" and row.tool_id in _DESKTOP_SHELL_IDS:
            shown.add("desktop-shell")
    return tuple(option for option in RUN_OPTIONS if option in shown)


def review_problems(
    rows: Sequence[PlanRow], *, home: Path, platform_os: str
) -> dict[str, tuple[str, str]]:
    """O7: each runnable agent whose settings file does not parse, as (file name, format name)."""
    runnable = {row.tool_id for row in rows if row.disposition in RUNNABLE}
    problems: dict[str, tuple[str, str]] = {}
    for agent in CONFIG_AGENTS:
        if agent not in runnable:
            continue
        problem = file_problem(agent, home=home, platform_os=platform_os)
        if problem is not None and problem.startswith("not valid "):
            path = settings_file(agent, home=home, platform_os=platform_os)
            problems[agent] = (path.name, FORMAT_NAMES[AGENT_FORMATS[agent]])
    return problems


def _apply_option(agent: str, setting: str, home: Path, platform_os: str) -> FileResult:
    """One option's write for one agent; an unexpected OS error is that file's refusal."""
    try:
        return apply_setting(agent, setting, home=home, platform_os=platform_os)
    except OSError as exc:
        path = settings_file(agent, home=home, platform_os=platform_os)
        return FileResult(agent, setting, path, AGENT_FORMATS[agent], refused=first_line(exc))


def _desktop_shell(outcomes: list[RowOutcome]) -> list[RowOutcome]:
    """SHELL for desktop apps: one environment.d conf, from the first done zsh/kitty/wezterm row.

    The zsh comes from `which_with_brew`, the lookup the terminal sync also uses.
    """
    index = next(
        (
            position
            for position, outcome in enumerate(outcomes)
            if outcome.row.tool_id in _DESKTOP_SHELL_IDS
            and outcome.row.disposition in RUNNABLE
            and outcome.result == "done"
        ),
        None,
    )
    if index is None:
        return outcomes
    home = Path.home()
    conf_dir = environment_d_dir(home, os.environ)
    shown = display_path(conf_dir / DESKTOP_SHELL_CONF)
    zsh = postinstall.which_with_brew("zsh")
    if zsh is None:
        outcomes[index] = replace(outcomes[index], desktop_shell_error=(shown, "zsh not found"))
        return outcomes
    try:
        write_linux_redirect(shell_redirect(zsh), home, conf_dir)
    except (ValueError, OSError) as exc:
        outcomes[index] = replace(outcomes[index], desktop_shell_error=(shown, first_line(exc)))
    else:
        outcomes[index] = replace(outcomes[index], desktop_shell=(shown, zsh))
    return outcomes


def _apply_run_options(outcomes: list[RowOutcome], ctx: RunContext) -> list[RowOutcome]:
    """D-09: each chosen option writes its settings to every runnable row that ended done.

    A row that did not end done writes nothing for its option and is marked `settings_skipped`.
    Options run in table order, so the report reads the same on every run.
    """
    home = Path.home()
    for option in RUN_OPTIONS:
        if option not in ctx.options or option not in OPTION_COVERS:
            continue
        setting, covered = OPTION_COVERS[option]
        for index, outcome in enumerate(outcomes):
            if outcome.row.disposition not in RUNNABLE or outcome.row.tool_id not in covered:
                continue
            if outcome.result != "done":
                outcomes[index] = replace(outcome, settings_skipped=True)
                continue
            written = _apply_option(outcome.row.tool_id, setting, home, ctx.platform.os)
            outcomes[index] = replace(outcome, settings=(*outcome.settings, written))
    if "desktop-shell" in ctx.options and ctx.platform.os != "macos":
        outcomes = _desktop_shell(outcomes)
    return outcomes


def execute_plan(rows: Sequence[PlanRow], ctx: RunContext) -> list[RowOutcome]:
    """Execute a settled plan and return one truthful outcome per row."""
    if any(row.disposition is Disposition.WAIT for row in rows):
        raise ValueError("cannot execute a plan while rows are still checking")
    force_ids = frozenset(
        row.tool_id
        for row in rows
        if row.disposition in {Disposition.REPAIR, Disposition.REINSTALL}
    )
    install = _with_force(ctx.install, force_ids, ctx.confirm_sensitive)
    unresolved: set[str] = set()
    halted = False
    outcomes: list[RowOutcome] = []
    for row in rows:
        if row.disposition is Disposition.SKIP:
            outcome = RowOutcome(row, "skipped", detail=row.reason)
        elif row.disposition is Disposition.BLOCKED:
            outcome = RowOutcome(row, "blocked", detail=row.reason)
        elif row.disposition is Disposition.MANUAL:
            # The handoff is the outcome: nothing runs, and dependents of this row are blocked.
            command = row.manual_command or ""
            unresolved.add(row.tool_id)
            outcome = RowOutcome(
                row,
                "manual",
                install=InstallOutcome(
                    row.tool_id,
                    InstallStatus.MANUAL_REQUIRED,
                    handoff=(command,),
                    manual_command=command,
                ),
                detail=row.reason,
            )
        elif halted or (ctx.should_continue is not None and not ctx.should_continue()):
            halted = True
            outcome = RowOutcome(row, "not_attempted", detail="run stopped before this row")
        else:
            try:
                if ctx.on_row_started is not None:
                    ctx.on_row_started(row)
                tool = ctx.catalog[row.tool_id]
                blockers = tuple(dep for dep in dict.fromkeys(tool.requires) if dep in unresolved)
                if blockers or row.disposition in {
                    Disposition.INSTALL,
                    Disposition.REPAIR,
                    Disposition.REINSTALL,
                }:
                    if blockers:
                        result = InstallOutcome(
                            tool.id, InstallStatus.DEPENDENCY_FAILED, blocked_by=blockers
                        )
                    else:
                        result = install(tool, ctx.platform, ctx.runner, ctx.resolve_tag)
                        if (
                            result.status is InstallStatus.CHECKSUM_MISMATCH
                            and ctx.on_mismatch is not None
                        ):
                            choice = ctx.on_mismatch(tool.id)
                            if choice == "retry":
                                result = install(
                                    tool,
                                    ctx.platform,
                                    ctx.runner,
                                    ctx.resolve_tag,
                                )
                            elif choice == "fallback":
                                result = install(
                                    tool,
                                    ctx.platform,
                                    ctx.runner,
                                    ctx.resolve_tag,
                                    checksum_policy="continue",
                                )
                    unresolved_statuses = (
                        _UNRESOLVED
                        if row.disposition in {Disposition.INSTALL, Disposition.REPAIR}
                        else _PRESENT_TOOL_LOST
                    )
                    if result.status in unresolved_statuses:
                        unresolved.add(tool.id)
                    mapped = _INSTALL_RESULT[result.status]
                    detail = (
                        "became present before it ran"
                        if result.status is InstallStatus.ALREADY_INSTALLED
                        else "no install method for this platform"
                        if result.status is InstallStatus.NO_METHOD
                        else ""
                    )
                    outcome = RowOutcome(
                        row, mapped, install=result, detail=detail, settings=result.settings
                    )
                elif row.disposition is Disposition.UPDATE:
                    if ctx.updates is None:
                        outcome = RowOutcome(row, "blocked", detail="no update service")
                    elif row.ownership is None:
                        outcome = RowOutcome(
                            row, "blocked", detail="ownership could not be resolved"
                        )
                    elif not ctx.updates.begin(row.tool_id):
                        in_flight = ctx.updates.in_flight or "another tool"
                        outcome = RowOutcome(
                            row,
                            "blocked",
                            detail=f"update already in flight for {in_flight}",
                        )
                    else:
                        try:
                            update = ctx.updates.run(UpdateTarget(tool, row.ownership))
                        finally:
                            ctx.updates.end()
                        mapped = (
                            "done"
                            if update.status == "updated"
                            else "failed"
                            if update.status == "failed"
                            else "blocked"
                        )
                        outcome = RowOutcome(row, mapped, update=update, detail=update.detail)
                else:
                    outcome = _run_reconfigure(row, tool, ctx)
            except Exception as exc:
                halted = True
                lines = str(exc).splitlines()
                detail = (
                    f"{type(exc).__name__}: {first_line(exc)}"
                    if lines and lines[0]
                    else first_line(exc)
                )
                outcome = RowOutcome(row, "crashed", detail=detail)
        outcomes.append(outcome)
        if ctx.on_outcome is not None:
            ctx.on_outcome(outcome)
    if halted or (ctx.should_continue is not None and not ctx.should_continue()):
        # Stop means nothing further starts: no hook sweep, no settings write (CR-07).
        return outcomes
    return _apply_run_options(_resync_hooks(outcomes, ctx), ctx)


def _settled(state: ToolState | None) -> bool:
    """Installed for planning: a present, non-broken published state."""
    return state is not None and state.present and state.health is not Health.BROKEN


def _first_clause(state: ToolState) -> str:
    """The text before the first ` — ` of the state's first reason, or empty."""
    return state.reasons[0].split(" — ", 1)[0] if state.reasons else ""


def _broken_reason(state: ToolState) -> str:
    clause = _first_clause(state)
    if clause == CHANGED_SINCE_INSTALL:
        return "changed since install; the file is replaced"
    return clause


def _needs_reason(dependency: str) -> str:
    return f"needs {dependency}"


def _needs_row(row: PlanRow, dependency: str) -> PlanRow:
    return replace(row, disposition=Disposition.BLOCKED, reason=_needs_reason(dependency))


def _version_arrow(state: ToolState) -> str:
    version = state.version
    if version is None or version.installed is None or version.latest is None:
        return "update available"
    return f"{version.installed} -> {version.latest}"


def _already_present_reason(state: ToolState) -> str:
    return f"already present; {_first_clause(state)}"


def _off_policy_reason(tool: Tool, ownership: ManagerOwnership, platform: Platform) -> str:
    """Name the actual owner and, when different, the catalog's declared manager."""
    real = owner_label(ownership) or ownership.owner
    declared = declared_manager_label(tool, platform)
    reason = f"managed by {real}"
    if declared is not None and declared != real:
        reason += f"; the catalog installs it via {declared}"
    return reason


def _row(
    tool: Tool,
    state: ToolState | None,
    *,
    requester: str | None,
    direct: bool,
    platform: Platform,
    reinstall: frozenset[str],
) -> PlanRow:
    if state is None or state.health is Health.CHECKING:
        return PlanRow(tool.id, Disposition.WAIT, "", requested_by=requester)

    def make(
        disposition: Disposition,
        reason: str,
        *,
        can_reinstall: bool = False,
        steps: tuple[ConfigStep, ...] = (),
        manual_command: str | None = None,
    ) -> PlanRow:
        return PlanRow(
            tool.id,
            disposition,
            reason,
            requested_by=requester,
            health=state.health,
            ownership=state.ownership,
            can_reinstall=can_reinstall,
            steps=steps,
            manual_command=manual_command,
        )

    def install_row(
        disposition: Disposition, reason: str, *, can_reinstall: bool = False
    ) -> PlanRow:
        """An INSTALL, REPAIR or REINSTALL row; MANUAL when its first method is native."""
        methods = resolve_methods(tool, platform)
        handoff = (
            executors.needs_manual(
                methods[0], writable=lambda prefix: prefix not in state.unwritable
            )
            if methods
            else None
        )
        if handoff is None:
            return make(disposition, reason, can_reinstall=can_reinstall)
        return make(Disposition.MANUAL, handoff.reason, manual_command=handoff.command)

    if state.health is Health.MISSING:
        reason = "not installed" if requester is None else f"needed by {requester}"
        return install_row(Disposition.INSTALL, reason)
    if state.health is Health.BROKEN:
        if state.ownership.owner in UNMANAGEABLE_OWNERS:
            label = owner_label(state.ownership) or state.ownership.owner
            return make(
                Disposition.BLOCKED,
                f"{label} owns it; repair needs sudo (never run here)",
            )
        reason = _broken_reason(state)
        if requester is not None:
            reason += f"; needed by {requester}"
        return install_row(Disposition.REPAIR, reason)
    if state.health is Health.MISCONFIGURED:
        if not direct:
            return make(Disposition.SKIP, _already_present_reason(state))
        if state.unconfigured:
            return make(
                Disposition.RECONFIGURE,
                _first_clause(state),
                steps=state.unconfigured,
            )
        return make(Disposition.BLOCKED, _first_clause(state))
    if state.health is Health.OUTDATED:
        if not direct:
            return make(Disposition.SKIP, _already_present_reason(state))
        refusal = update_refusal(tool, state.ownership)
        if refusal is None:
            return make(Disposition.UPDATE, _version_arrow(state))
        if state.ownership.off_policy:
            reason = _off_policy_reason(tool, state.ownership, platform)
        else:
            label = owner_label(state.ownership)
            reason = f"managed by {label}" if label is not None else "no update source"
        return make(Disposition.SKIP, reason)
    if requester is not None and state.health is Health.OK:
        return make(Disposition.SKIP, "already present")
    if direct and state.health is Health.OK:
        ownership = state.ownership
        if ownership.off_policy:
            return make(Disposition.SKIP, _off_policy_reason(tool, ownership, platform))
        if ownership.owner == "installer":
            if tool.id in reinstall:
                return install_row(
                    Disposition.REINSTALL,
                    "reinstall requested; r again to undo",
                    can_reinstall=True,
                )
            return make(Disposition.SKIP, "already current", can_reinstall=True)
        if ownership.owner == "unknown":
            reason = "already current; owner unknown"
        else:
            reason = f"managed by {owner_label(ownership) or ownership.owner}"
        return make(Disposition.SKIP, reason)
    return make(Disposition.SKIP, _first_clause(state))


def _blocked_row(
    blocked: Blocked,
    state: ToolState | None,
    *,
    requester: str | None,
) -> PlanRow:
    if state is None or state.health is Health.CHECKING:
        return PlanRow(blocked.tool_id, Disposition.WAIT, "", requested_by=requester)
    if state.reasons and state.health is Health.UNAVAILABLE:
        reason = _first_clause(state)
    elif blocked.needs is not None:
        reason = _needs_reason(blocked.needs)
    else:
        reason = "not available on this platform"
    return PlanRow(
        blocked.tool_id,
        Disposition.BLOCKED,
        reason,
        requested_by=requester,
        health=state.health,
        ownership=state.ownership,
    )


def build_plan(
    selected: Sequence[str],
    catalog: Sequence[Tool],
    state_of: Callable[[str], ToolState | None],
    platform: Platform,
    *,
    reinstall: frozenset[str],
) -> list[PlanRow]:
    """The install plan for `selected`, computed from published state only (D-01).

    Reads `state_of` and nothing else: no probe, no network, no subprocess. Rows
    follow `Resolution.closure` (execution order, dependencies first).
    """
    by_id = {tool.id: tool for tool in catalog}
    chosen = select_tools(list(catalog), list(selected))
    direct_ids = {tool.id for tool in chosen}
    res = resolve_dependencies(
        order_for_install(chosen),
        list(catalog),
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=lambda tool: _settled(state_of(tool.id)),
    )
    rows = [
        _row(
            tool,
            state_of(tool.id),
            requester=res.requested_by.get(tool.id),
            direct=tool.id in direct_ids,
            platform=platform,
            reinstall=reinstall,
        )
        for tool in res.closure
    ]
    rows.extend(
        _blocked_row(item, state_of(item.tool_id), requester=res.requested_by.get(item.tool_id))
        for item in res.blocked
    )
    unsatisfied = {
        row.tool_id
        for row in rows
        if row.disposition in {Disposition.BLOCKED, Disposition.MANUAL}
        and not _settled(state_of(row.tool_id))
    }
    for index, row in enumerate(rows):
        if row.disposition not in RUNNABLE:
            continue
        dependency = next((dep for dep in by_id[row.tool_id].requires if dep in unsatisfied), None)
        if dependency is not None:
            rows[index] = _needs_row(row, dependency)
            if not _settled(state_of(row.tool_id)):
                unsatisfied.add(row.tool_id)
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if row.disposition not in RUNNABLE or row.requested_by is None:
            continue
        requiring_rows = [
            candidate for candidate in rows if row.tool_id in by_id[candidate.tool_id].requires
        ]
        if requiring_rows and all(
            candidate.disposition in {Disposition.BLOCKED, Disposition.MANUAL}
            or candidate.reason.startswith("not needed while ")
            for candidate in requiring_rows
        ):
            rows[index] = replace(
                row,
                disposition=Disposition.SKIP,
                reason=f"not needed while {row.requested_by} is blocked",
            )
    return rows
