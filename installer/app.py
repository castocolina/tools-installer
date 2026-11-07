"""Headless wizard planning and install lifecycle flows."""

import contextlib
import dataclasses
import os
import shlex
import shutil
import sys
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from installer import receipts, shellrc
from installer.agent_settings import ledger_preview, revert_agent
from installer.atomic import atomic_write_text
from installer.cli import Options
from installer.deps import resolve_dependencies
from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport, audit_path, scan_bin_links
from installer.engine import install_tool
from installer.guards import (
    guard_path_warning,
    guard_redirect_warning,
    guard_status,
    install_global_redirect_shims,
    install_redirect_shims,
    install_shims,
    real_pnpm,
    remove_ban_aliases,
    remove_shims,
    write_ban_aliases,
)
from installer.locations import display_path, path_scan_rc_paths
from installer.model import Tool
from installer.ownership import listed_name, manager_listing
from installer.platform import Platform
from installer.pnpm_globals import (
    audit_node_globals,
    co_install_groups,
    co_install_warnings,
    pnpm_global_packages,
)
from installer.policy import Policy, omz_removal_detail
from installer.post_install import sensitive_prompt
from installer.postinstall import host_labels
from installer.prompt import Prompter
from installer.rcclean import (
    PathWriterLine,
    find_duplicate_path_lines,
    group_writer_lines,
    scan_rc_path_writer_lines,
    strip_lines,
)
from installer.render import (
    RUN_OPTIONS_LEFT_OFF,
    render_competing_mechanisms,
    render_disk_pressure,
    render_doctor,
    render_guard,
    render_guard_status,
    render_node_globals,
    render_plan,
    render_rc_duplicates,
    render_remove_yourself,
    render_run_report,
    render_run_summary,
    render_uninstall,
    run_option_lines,
    shell_init_left_off_line,
)
from installer.run import CommandError, Runner, command_error_line, run_command
from installer.sanitize import sanitize_log_line
from installer.session import (
    RUNNABLE,
    Disposition,
    OnMismatch,
    PlanRow,
    RowOutcome,
    RunContext,
    SensitiveInstall,
    build_plan,
    execute_plan,
    first_line,
    review_problems,
    run_options,
)
from installer.shellrc import (
    collect_bin_dirs,
    ensure_source,
    remove_managed_block,
    write_managed_path,
    write_myshellrc,
)
from installer.status import is_installed
from installer.systemd_daemon import CompetingUnit
from installer.tweaks import SHELL_INIT_TOOLS, TweakBundle
from installer.uninstall import (
    MANAGER_UNINSTALL_ARGV,
    SweepResult,
    active_policies,
    config_targets,
    delete_config_path,
    policy_owned,
    removal_plan,
    remove_paths,
    remove_proven,
    sweep_policies,
    sweep_tweaks,
)
from installer.update import UpdateService
from installer.version_status import VersionRefreshService
from installer.versions import TagResolver, resolve_github_tag


def _choose_tools(tools: list[Tool], options: Options) -> list[Tool]:
    """Apply the headless selection flags to the catalog."""
    if options.all:
        return tools
    return [tool for tool in tools if tool.category in options.categories]


def run_wizard(
    tools: list[Tool],
    prompter: Prompter,
    console: Console,
    options: Options,
    *,
    refresh: VersionRefreshService,
    updates: UpdateService,
    terminal_sync: Callable[[], str | None] | None = None,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: SensitiveInstall = install_tool,
    on_mismatch: OnMismatch | None = None,
) -> list[RowOutcome] | None:
    """Print and execute a fresh plan, or return None when confirmation is declined.

    The synchronous pass covers version state and skill-pack host answers. Held
    bookkeeping writes commit only after consent, before execution starts.
    """
    selected = _choose_tools(tools, options)
    refresh.hold_writes()
    try:
        refresh.refresh(tools)
        refresh.refresh_skills(tools)
    except (OSError, CommandError, ValueError) as exc:
        lines = str(exc).splitlines()
        detail = lines[0] if lines and lines[0] else type(exc).__name__
    else:
        detail = ""

    rows = build_plan(
        [tool.id for tool in selected],
        tools,
        refresh.state_of,
        refresh.platform,
        reinstall=frozenset(),
    )
    waiting = [row.tool_id for row in rows if row.disposition is Disposition.WAIT]
    if detail or waiting:
        detail = detail or f"no state for {', '.join(waiting)}"
        console.print(f"State check failed: {detail}")
        outcomes = [RowOutcome(row, "not_attempted", detail=detail) for row in rows]
        render_run_summary(outcomes, console)
        return outcomes

    render_plan(rows, console)
    has_runnable_row = any(row.disposition in RUNNABLE for row in rows)
    if not options.yes and has_runnable_row and not prompter.confirm("Run this plan?"):
        console.print("Cancelled; nothing was changed.")
        return None
    chosen: frozenset[str] = (
        frozenset() if options.yes else _ask_run_options(rows, prompter, console, refresh)
    )
    if options.yes or has_runnable_row:
        for line in refresh.commit_writes():
            console.print(line, markup=False, highlight=False, soft_wrap=True)
    if options.yes and run_options(rows, refresh.platform.os):
        console.print(RUN_OPTIONS_LEFT_OFF, markup=False, highlight=False, soft_wrap=True)

    def confirm_sensitive(tool_id: str, action: str) -> bool:
        prompt = sensitive_prompt(tool_id, action)
        return prompter.confirm(prompt.prompt, default=prompt.default)

    context = RunContext(
        catalog={tool.id: tool for tool in tools},
        platform=refresh.platform,
        runner=runner,
        resolve_tag=resolve_tag,
        install=install,
        updates=updates,
        terminal_sync=terminal_sync,
        on_mismatch=None if options.yes else on_mismatch,
        confirm_sensitive=None if options.yes else confirm_sensitive,
        options=chosen,
    )
    outcomes = execute_plan(rows, context)
    render_run_report(outcomes, console, options=chosen)
    if options.yes:
        left_off = shell_init_left_off_line(outcomes, SHELL_INIT_TOOLS)
        if left_off is not None:
            console.print(left_off, markup=False, highlight=False, soft_wrap=True)
    return outcomes


def _ask_run_options(
    rows: Sequence[PlanRow],
    prompter: Prompter,
    console: Console,
    refresh: VersionRefreshService,
) -> frozenset[str]:
    """D-09: one default-no question per run option the plan shows; the yes answers are the options.

    Each question follows its continuation notes (UI-SPEC section 7); `--yes` never reaches here.
    """
    platform_os = refresh.platform.os
    problems = review_problems(rows, home=Path.home(), platform_os=platform_os)
    chosen: set[str] = set()
    for option in run_options(rows, platform_os):
        first, notes = run_option_lines(option, rows, platform_os=platform_os, problems=problems)
        for note in notes:
            console.print(sanitize_log_line(note), markup=False, highlight=False, soft_wrap=True)
        if prompter.confirm(f"{first}?", default=False):
            chosen.add(option)
    return frozenset(chosen)


def configure_path(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
    link_mode: str = "centralized",
    shellrc_path: Path | None = None,
    exists: Callable[[Path], bool] = Path.is_dir,
) -> shellrc.ShellrcConsolidation | None:
    """Wire the managed PATH into the shells per `link_mode`.

    centralized/single: write ~/.myshellrc and `source` it from each rc path (the
    caller passes one rc for single, both for centralized). split: write the managed
    PATH block directly into each rc path, with no ~/.myshellrc indirection.
    When given, consolidate the foreign ~/.shellrc before writing the managed block;
    each rc then reaches ~/.myshellrc through exactly one route. Only bin dirs that
    pass `exists` are managed (the default always is).
    """
    consolidation: shellrc.ShellrcConsolidation | None = None
    # Bound to the path ONLY when ~/.shellrc really is this project's stub, so the
    # single-route check below has a non-optional path and cannot run against a
    # file consolidation refused or never touched.
    stub_shellrc: Path | None = None
    if shellrc_path is not None and link_mode != "split":
        consolidation = shellrc.consolidate_shellrc(shellrc_path, myshellrc_path, tuple(rc_paths))
        if consolidation.status in {"consolidated", "already"}:
            stub_shellrc = shellrc_path
        if consolidation.status == "consolidated":
            console.print(f"Consolidated {shellrc_path} into {myshellrc_path}.")
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir, exists)
    if link_mode == "split":
        # Split mode maintains no ~/.myshellrc; consolidating into a file nothing
        # sources would relocate foreign content while reporting a false success.
        for rc_path in rc_paths:
            write_managed_path(rc_path, bin_dirs)
        targets = ", ".join(str(rc_path) for rc_path in rc_paths)
        console.print(f"PATH written into {targets} (restart your shell).")
        return consolidation
    write_myshellrc(bin_dirs, myshellrc_path)
    for rc_path in rc_paths:
        rc_text = rc_path.read_text() if rc_path.exists() else ""
        if stub_shellrc is not None:
            # A generic ~/.shellrc exists precisely because an rc commonly sources it.
            # Skipping our block prevents the canonical file from running twice; the
            # accepted residuals are conditional source lines (detected as yes) and
            # unprovable commands, which take the ordinary route with a diagnostic.
            # `unprovable` is not `yes`: eval "$(brew shellenv)" and source
            # "$ZDOTDIR/foo" are ordinary rc content, and treating them as wired
            # would leave PATH unwired for users who need the ordinary route.
            route = shellrc.sources_file(rc_text, stub_shellrc)
            if route == "yes":
                shellrc.remove_source_block(rc_path)
                console.print(f"{rc_path} reaches {myshellrc_path} through {stub_shellrc}.")
                continue
            if route == "unprovable":
                console.print(
                    f"{rc_path} contains a source command this tool could not resolve; "
                    "the ordinary source route is retained."
                )
        ensure_source(rc_path, myshellrc_path)
    console.print(f"PATH configured in {myshellrc_path} (restart your shell or source it).")
    # Printed AFTER the writes, so its claim that the block was written is true at
    # the moment it is made: an exception above reaches the caller with no message
    # rather than with a message asserting a write that did not happen.
    refusal = consolidation_refusal_message(consolidation)
    if refusal is not None:
        console.print(refusal)
    return consolidation


def consolidation_refusal_message(
    outcome: shellrc.ShellrcConsolidation | None,
) -> str | None:
    """Build the one user-facing message for a refused shellrc consolidation.

    No `assert` narrows `reason` here: asserts vanish under `python -O`, and this
    is the one path whose entire job is making a refusal impossible to mistake
    for success. A refusal always carries a reason, but if one were ever missing
    the message must still be printed, not silently dropped.
    """
    if outcome is None or outcome.status != "refused":
        return None
    reason = outcome.reason or "no reason was recorded"
    return f"Managed PATH block was written, but ~/.shellrc consolidation was refused: {reason}"


def guard_state(
    default_bin_dir: Path,
    path_value: str,
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[dict[str, bool], str | None]:
    """The pip/npm-ban status and the PATH-order warning — the latter shown only
    when a ban is actually installed (an irrelevant warning otherwise).

    Split out of `doctor_data` because it is the half that goes STALE inside a
    running app: the Policies view installs and removes the ban live, one nav
    step from both the Doctor report that describes it and the Uninstall row
    that offers to remove it. Those two views re-read this on entry, while the
    PATH audit stays a build-time snapshot — the process PATH cannot change
    until the shell restarts, so re-auditing would only re-show "missing".
    """
    status = guard_status(default_bin_dir)
    path_warning = (
        guard_path_warning(default_bin_dir, path_value, which) if any(status.values()) else None
    )
    redirect_warning = guard_redirect_warning(default_bin_dir)
    warning = (
        f"{path_warning} {redirect_warning}"
        if path_warning and redirect_warning
        else path_warning or redirect_warning
    )
    return status, warning


def path_writer_lines_for(
    report: DoctorReport,
    *,
    rc_paths: Iterable[Path] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[PathWriterLine]:
    """Writer records for each DUPLICATED directory. Empty when nothing is duplicated.

    Scoped to `report.duplicated` rather than every managed dir: a writer only
    changes the advice for a directory that is actually reported twice, and
    scanning for the rest would read every rc file to answer a question nobody
    asked. Read-only, and total over unreadable files.
    """
    if not report.duplicated:
        return []
    paths = path_scan_rc_paths() if rc_paths is None else rc_paths
    environ = os.environ if env is None else env
    return scan_rc_path_writer_lines(paths, set(report.duplicated), environ)


def duplicate_path_writers(
    report: DoctorReport,
    *,
    rc_paths: Iterable[Path] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[Path, tuple[Path, ...]]:
    """Which rc files add each DUPLICATED directory unconditionally."""
    if not report.duplicated:
        return {}
    return group_writer_lines(path_writer_lines_for(report, rc_paths=rc_paths, env=env))


def doctor_data(
    tools: list[Tool],
    *,
    platform: Platform,
    default_bin_dir: Path,
    path_value: str,
    exists: Callable[[Path], bool],
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[DoctorReport, dict[str, bool], str | None]:
    """Assemble the doctor inputs shared by the CLI report and the TUI screen:
    the PATH audit, the pip/npm-ban status, and the PATH-order warning."""
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir, exists)
    report = audit_path(bin_dirs, path_value, exists)
    report = dataclasses.replace(report, broken_links=scan_bin_links(default_bin_dir))
    status, warning = guard_state(default_bin_dir, path_value, which)
    return report, status, warning


def run_doctor(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    path_value: str,
    exists: Callable[[Path], bool],
    which: Callable[[str], str | None] = shutil.which,
    managed_globals: Callable[[], tuple[str, ...] | None] = pnpm_global_packages,
    disk_pressure: Callable[[], DiskPressure] | None = None,
    competing: Callable[[], tuple[CompetingUnit, ...]] | None = None,
    duplicate_writers: Callable[[DoctorReport], Mapping[Path, tuple[Path, ...]]] = (
        duplicate_path_writers
    ),
) -> DoctorReport:
    """Audit the PATH (read-only) and render the report. Fixing the PATH
    remains a separate explicit action.

    `managed_globals` is injected beside `which` for the same reason: the
    pnpm-globals audit asks the real pnpm what it manages, and a test must be
    able to answer for it.

    `disk_pressure` is the same injected-seam shape. None renders exactly
    today's report, so every existing caller stays byte-identical. Plan
    15.7-02's D-03b already makes `probe_disk_pressure` total over filesystem
    and probe-conversion failure; the guard below covers the INJECTED
    closure a caller composes around it, which a caller can make fail, rather
    than re-guarding the probe itself. It is deliberately not a fourth
    `doctor_data` element: that tuple is destructured positionally.
    """
    report, status, warning = doctor_data(
        tools,
        platform=platform,
        default_bin_dir=default_bin_dir,
        path_value=path_value,
        exists=exists,
        which=which,
    )
    render_doctor(report, console, duplicate_writers(report))
    render_guard_status(status, warning, console)
    render_node_globals(audit_node_globals(tools, which=which, managed=managed_globals), console)
    if disk_pressure is not None:
        with contextlib.suppress(OSError, ValueError):
            render_disk_pressure(disk_pressure(), console)
    # WR-10: the system-scope competitor disclosure used to exist only inside
    # the first apply's result, so `make doctor` never mentioned the root-owned
    # cleanup job running beside this one. Read-only, and guarded like the
    # probe above: a detection failure must not fail the audit.
    if competing is not None:
        with contextlib.suppress(OSError, ValueError, CommandError):
            render_competing_mechanisms(competing(), console)
    return report


def clean_rc_duplicates(
    rc_paths: list[Path],
    managed_dirs: set[Path],
    env: Mapping[str, str],
    console: Console,
    *,
    confirm: Callable[[str], bool],
) -> dict[Path, list[str]]:
    """Preview duplicate PATH lines in each rc file, confirm, then strip them.

    Returns the removed lines per file ({} if none found or the user declined).
    """
    found: dict[Path, list[str]] = {}
    previewed: dict[Path, tuple[bytes, str, list[int]]] = {}
    for rc_path in rc_paths:
        if not rc_path.exists():
            continue
        before_bytes = rc_path.read_bytes()
        text = before_bytes.decode("utf-8")
        indices = find_duplicate_path_lines(text, managed_dirs, env)
        if indices:
            lines = text.split("\n")
            found[rc_path] = [lines[index] for index in indices]
            previewed[rc_path] = (before_bytes, text, indices)
    render_rc_duplicates(found, console)
    if not found:
        return {}
    if not confirm("Remove these duplicate PATH lines?"):
        return {}
    for rc_path, (before_bytes, text, indices) in previewed.items():
        try:
            after = rc_path.read_bytes()
        except OSError:
            after = None
        if after != before_bytes:
            console.print(f"{rc_path} changed since the preview; left untouched.", style="yellow")
            found.pop(rc_path, None)
            continue
        atomic_write_text(rc_path, strip_lines(text, indices))
    return found


def run_guard(
    *,
    remove: bool,
    shim_dir: Path,
    rc_paths: list[Path],
    path_value: str,
    console: Console,
    confirm: Callable[[str], bool],
    which: Callable[[str], str | None] = shutil.which,
) -> bool:
    """Install or remove the pip/npm ban (PATH shims + interactive aliases).

    Previews the targets, confirms, then acts on both layers. Returns whether it
    acted. The shim dir doubles as the managed bin dir (already on PATH).
    """
    targets = ", ".join(str(rc_path) for rc_path in rc_paths)
    verb = "Remove" if remove else "Install"
    if not remove:
        # The consent has to name what installing actually does now: it wraps
        # the user's own pnpm binary and gives up pnpm's gated postinstalls for
        # global installs (registry.toml's volta entry, D-06/D-08).
        console.print(
            "This wraps npm and pnpm so global installs run `volta install`, which runs "
            "npm's install scripts unrestricted — keep untrusted packages on a "
            "project-local `pnpm add`."
        )
    if not confirm(f"{verb} the pip/npm ban (shims in {shim_dir} + aliases in {targets})?"):
        return False
    if remove:
        actions = remove_shims(shim_dir)
        for rc_path in rc_paths:
            remove_ban_aliases(rc_path)
        render_guard(actions, None, console, removing=True)
        return True
    actions = install_shims(shim_dir)
    actions.update(install_redirect_shims(shim_dir, path_value=path_value))
    actions.update(install_global_redirect_shims(shim_dir, path_value=path_value))
    for rc_path in rc_paths:
        write_ban_aliases(rc_path)
    # The same composition the Doctor/TUI path gets from guard_state: the
    # per-name action lines never explain that npx/npm degraded to hard blocks
    # because pnpm or volta was unresolvable, so a --guard user installing on a
    # bare machine would otherwise never see it.
    _status, warning = guard_state(shim_dir, path_value, which)
    render_guard(actions, warning, console, removing=False)
    return True


def _has_daemon_id(ids: tuple[str, ...]) -> bool:
    """True when any id in ids is the background daemon's own namespaced id.

    A tiny, named predicate rather than an inline generator expression
    repeated at every daemon-aware copy call site (preview + success, CLI and
    TUI): naming it once makes the "daemon:-prefixed id" condition legible
    and keeps every call site byte-for-byte consistent with the others.
    """
    return any(policy_id.startswith("daemon:") for policy_id in ids)


@dataclass(frozen=True)
class ToolRemoval:
    """One tool's removal outcome. `detail` is its one-line reason, or `already removed`."""

    tool_id: str
    removed: bool
    detail: str = ""
    refused: tuple[str, ...] = ()
    # The hosts the unregister ran for (D-04); set only when the removal succeeded.
    unregistered: tuple[str, ...] = ()


def removal_runs_line(tool_id: str, argv: Sequence[str]) -> str:
    """The line the CLI and the preview print before a vendor or manager command runs."""
    return f"{tool_id}: runs {shlex.join(argv)}"


def unregister_runs_line(tool_id: str, argv: Sequence[str]) -> str:
    """The undo line: the executable shown by name, while the proven absolute path runs."""
    return removal_runs_line(tool_id, (Path(argv[0]).name, *argv[1:]))


ALREADY_REMOVED = "already removed"


def pnpm_removal_packages(argvs: Iterable[Sequence[str]]) -> frozenset[str]:
    """The packages the pnpm removal argvs name, which the group warnings check against.
    `pnpm remove --global <pkg>` removes the whole install group `<pkg>` belongs to (22-13
    D-1, measured on pnpm 12.16.1), so a later member's removal finds it already gone."""
    prefix = MANAGER_UNINSTALL_ARGV["node"]
    return frozenset(argv[-1] for argv in argvs if tuple(argv[:-1]) == prefix)


def retire_group_members(
    argv: Sequence[str], catalog: Sequence[Tool], skip: Collection[str]
) -> tuple[tuple[str, str], ...]:
    """22-UAT F-2: after `argv` ran a pnpm removal, retire the receipt of each other member of
    the package's declared co-install group that pnpm took along (22-13 D-1). Only a readable
    fresh listing that lacks the member proves it gone (C-02); an unreadable listing or a
    failed delete keeps the receipt. `skip` names the tools this run already handled.
    Returns (member id, group id) per retired receipt."""
    if tuple(argv[:-1]) != MANAGER_UNINSTALL_ARGV["node"]:
        return ()
    package = argv[-1]
    members = {
        tool.id: (group, receipt.package)
        for group, packages in co_install_groups(catalog)
        if package in packages
        for tool in catalog
        if tool.id not in skip
        and (receipt := receipts.read(tool.id)) is not None
        and receipt.method.kind == "node"
        and receipt.package in packages
        and receipt.package != package
    }
    listed = manager_listing("node") if members else None
    if listed is None:
        return ()
    retired: list[tuple[str, str]] = []
    for tool_id, (group, member) in members.items():
        if member in listed:
            continue
        with contextlib.suppress(OSError):
            receipts.delete(tool_id)
            retired.append((tool_id, group))
    return tuple(retired)


def removed_with_group_line(tool_id: str, group: str) -> str:
    """The line the CLI and the Uninstall view print for a member pnpm took with its group."""
    return f"{tool_id}: removed with the {group} group"


def removal_order(tools: Sequence[Tool]) -> list[Tool]:
    """Dependents first: a tool comes before every selected tool it requires (review R1-09).

    Reuses the dependency resolver on the selection as its own catalog, so nothing is
    dragged in or blocked; independents keep the order they were given."""
    selected = list(tools)
    resolution = resolve_dependencies(
        list(reversed(selected)),
        selected,
        available=lambda _tool: True,
        is_installed=lambda _tool: True,
    )
    return list(reversed(resolution.closure))


# Settings are written and reverted under the host's OS; only "macos" is compared, never "linux".
HOST_SETTINGS_OS = "macos" if sys.platform == "darwin" else "linux"


def settings_change_lines(agent_ids: Iterable[str]) -> tuple[str, ...]:
    """The settings keys a revert removes, one line per ledgered file (UI-SPEC section 6), and
    the keys it keeps because the user changed them since (F-3). A recorded file that is gone
    is named as such: the revert reports it and touches nothing."""
    lines: list[str] = []
    for agent in agent_ids:
        for path, removes, kept in ledger_preview(agent, home=Path.home()):
            if not os.path.lexists(path):
                lines.append(
                    f"{agent}: cannot remove {', '.join(removes)}: {display_path(path)} is missing"
                )
                continue
            if removes:
                lines.append(f"{agent}: removes {', '.join(removes)} from {display_path(path)}")
            if kept:
                them = "it" if len(kept) == 1 else "them"
                lines.append(
                    f"{agent}: keeps {', '.join(kept)}, changed since this installer wrote {them}"
                )
    return tuple(lines)


def removal_change_lines(
    tools: Iterable[Tool], *, active_tweaks: Collection[str]
) -> tuple[str, ...]:
    """What removing these tools changes: the settings keys a removal reverts and the shell-init
    bundle it turns off (UI-SPEC section 6, block 3b). `active_tweaks` is the policy-id list the
    sweep itself reads, so the preview and the effect cannot disagree."""
    lines: list[str] = []
    for tool in tools:
        if tool.id in receipts.CONFIG_AGENTS:
            lines.extend(settings_change_lines((tool.id,)))
        if tool.id in SHELL_INIT_TOOLS and f"tweak:{tool.id}" in active_tweaks:
            lines.append(f"{tool.id}: turns off its shell init in ~/.myshellrc")
    return tuple(lines)


def _revert_settings(
    agent_ids: Iterable[str], *, platform_os: str
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Revert each agent's ledgered keys that still hold our value (SPEC R8, D-08).

    Returns (agents with a key reverted, agents with a key the user changed since, warnings for
    a file that could not be reverted). The one revert loop for every removal route (23-REUSE 15-1).
    """
    reverted: list[str] = []
    kept: list[str] = []
    warnings: list[str] = []
    for agent in agent_ids:
        for result in revert_agent(agent, home=Path.home(), platform_os=platform_os):
            if result.refused is not None:
                warnings.append(f"could not revert {display_path(result.path)} — {result.refused}")
                continue
            if any(key.kind == "removed" for key in result.keys):
                reverted.append(agent)
            if any(key.kind == "kept_changed" for key in result.keys):
                kept.append(agent)
    return (
        tuple(dict.fromkeys(reverted)),
        tuple(dict.fromkeys(kept)),
        tuple(dict.fromkeys(warnings)),
    )


def _after_removal(
    tool: Tool,
    *,
    bundles: tuple[TweakBundle, ...],
    bin_dir: Path,
    myshellrc_path: Path,
    extra_policies: tuple[Policy, ...],
    platform_os: str,
) -> SweepResult:
    """What a successful removal takes with it: its settings keys, its shell-init bundle, and the
    desktop SHELL row when zsh goes (T-23-62). Nothing else of the tweak sweep is touched."""
    parts: list[SweepResult] = []
    if tool.id in receipts.CONFIG_AGENTS:
        # shortcut: no CONFIG_AGENTS tool declares config_paths, so a removal never deletes a
        # settings file; when one does, revert first, then delete it and drop its ledger entries.
        reverted, kept, warnings = _revert_settings((tool.id,), platform_os=platform_os)
        parts.append(SweepResult(warnings=warnings, settings_reverted=reverted, settings_kept=kept))
    bundle = next((b for b in bundles if b.id == tool.id), None)
    if tool.id in SHELL_INIT_TOOLS and bundle is not None:
        shell = sweep_policies(active_policies((bundle,), rc_path=myshellrc_path, bin_dir=bin_dir))
        parts.append(dataclasses.replace(shell, shell_init_off=(tool.id,) if shell.swept else ()))
    if tool.id == "zsh" and platform_os != "macos":
        owned = [p for p in extra_policies if p.id == "desktop-shell" and policy_owned(p)]
        parts.append(sweep_policies(owned))
    return _merge(parts)


def _merge(results: Sequence[SweepResult]) -> SweepResult:
    """One teardown's sweeps read as one result: every id and warning, in the order given."""
    return SweepResult(
        swept=tuple(x for r in results for x in r.swept),
        failed=tuple(x for r in results for x in r.failed),
        warnings=tuple(x for r in results for x in r.warnings),
        settings_reverted=tuple(x for r in results for x in r.settings_reverted),
        settings_kept=tuple(x for r in results for x in r.settings_kept),
        shell_init_off=tuple(x for r in results for x in r.shell_init_off),
    )


def removal_result_lines(result: SweepResult) -> tuple[str, ...]:
    """The settings lines a removal result reports (UI-SPEC section 6), for the CLI and the view."""
    lines: list[str] = []
    if result.settings_reverted:
        lines.append(f"Settings reverted for {', '.join(result.settings_reverted)}.")
    if result.settings_kept:
        kept = ", ".join(result.settings_kept)
        lines.append(f"Kept settings you changed since this installer wrote them: {kept}.")
    if result.shell_init_off:
        lines.append(f"Shell init turned off for {', '.join(result.shell_init_off)}.")
    return tuple(lines)


def remove_tool(
    tool: Tool,
    *,
    paths: tuple[Path, ...],
    argv: tuple[str, ...],
    bin_dir: Path,
    runner: Runner,
    unregister: tuple[tuple[str, ...], ...] = (),
) -> ToolRemoval:
    """Remove one tool: its hook undo, its command, then its proven paths, then its receipt
    (D-04, D-07).

    `paths`, `argv` and `unregister` are what the user saw before the confirm. The fresh plan
    is proven again here, so the CLI and the TUI share the same post-confirm check: a
    previewed path that moved, a command that changed, or a command whose paths shrank
    refuses the whole tool before anything runs. A manager package that a readable fresh
    listing no longer shows runs nothing and retires its receipt (`already removed`). A failed
    undo or command deletes nothing and keeps the receipt, so a later plan still sees the tool."""
    try:
        fresh = removal_plan(tool, bin_dir, verify=True)
        named = {*fresh.removable, *fresh.yourself}
        # A command runs only on the proof it was previewed against: with a command, every
        # previewed path must still be removable, not merely named (review R2-02).
        changed = [p for p in paths if p not in named or (bool(argv) and p not in fresh.removable)]
        changed += [p for p in fresh.removable if p not in paths]
        if changed or argv != fresh.argv or unregister != fresh.unregister or not (paths or argv):
            refused = tuple(f"changed since the preview; not removed: {p}" for p in changed)
            return ToolRemoval(tool.id, False, "changed since the preview; not removed", refused)
        # The undo runs while the proven executable still exists, before any path goes (SPEC R1).
        for undo in fresh.unregister:
            try:
                runner(list(undo))
            except CommandError as exc:
                return ToolRemoval(tool.id, False, f"unregister: {command_error_line(exc)}")
        if fresh.unregister and tool.postinstall:
            receipts.forget_hooks(tool.id, tool.postinstall)
        manager = next(
            (kind for kind, prefix in MANAGER_UNINSTALL_ARGV.items() if argv[:-1] == prefix), None
        )
        if fresh.level == "manager" and manager is not None:
            # A readable fresh listing that lacks the package proves it is gone (review C-02);
            # e.g. pnpm took a whole group with an earlier member (22-13 D-1). Unknown runs it.
            listed = manager_listing(manager)
            if listed is not None and listed_name(manager, argv[-1]) not in listed:
                receipts.delete(tool.id)
                return ToolRemoval(tool.id, True, ALREADY_REMOVED, unregistered=fresh.hook_hosts)
        if argv:
            command = argv
            if argv[0] == "pnpm":
                # The PATH shim may be this installer's own wrapper (see guards.real_pnpm).
                resolved = real_pnpm()
                if resolved is None:
                    return ToolRemoval(tool.id, False, "pnpm not found on PATH")
                command = (resolved, *argv[1:])
            try:
                runner(list(command))
            except CommandError as exc:
                return ToolRemoval(tool.id, False, command_error_line(exc))
            trees = tuple(p for p in fresh.removable if fresh.artifacts[p].type == "tree")
            # The vendor command may have removed part of what the receipt recorded; only
            # what is still there is re-proven, so a path it already removed is not a refusal.
            still_there = [
                fresh.artifacts[p] for p in fresh.removable if p.exists() or p.is_symlink()
            ]
            refused_paths = remove_paths(still_there, trees=trees)
            refused = tuple(f"changed since the preview; not removed: {p}" for p in refused_paths)
        else:
            _removed, refused = remove_proven([tool], list(paths), bin_dir)
        if refused:
            return ToolRemoval(tool.id, False, refused[0], refused)
        receipts.delete(tool.id)
        return ToolRemoval(tool.id, True, unregistered=fresh.hook_hosts)
    except OSError as exc:
        return ToolRemoval(tool.id, False, first_line(exc))


def run_uninstall(
    tools: list[Tool],
    console: Console,
    *,
    default_bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
    confirm: Callable[[str], bool],
    bundles: tuple[TweakBundle, ...],
    zshrc_path: Path,
    daemon_policy: Policy | None,
    extra_policies: tuple[Policy, ...],
    runner: Runner,
    platform_os: str = HOST_SETTINGS_OS,
) -> tuple[list[Path], tuple[str, ...]]:
    """Preview each tool's removal, confirm, then remove the tools in dependency order,
    the PATH block, any pip/npm-ban artifacts (shims + alias blocks), and still-enabled
    shell tweaks (the background maintenance daemon included, when active).

    Returns (the removed proven paths, the ids whose removal failed), both in removal
    order; ([], ()) when nothing is to be removed or the user declined. Each tool goes
    through `remove_tool`, the remover the TUI uses too. Only each plan's proven artifacts
    are removed; unproven name matches are listed via render_remove_yourself and left on
    disk (SAFE-03/D-04).

    `bundles`, `zshrc_path`, `daemon_policy`, and `extra_policies` are required,
    unlike on the uninstall primitives they forward to. There the defaults are
    a test affordance; here a dropped kwarg would type-check, pass the suite,
    and silently sweep nothing while reporting success — a user-visible
    data-integrity regression that nothing else can catch. `daemon_policy` is
    `None` on any platform where the daemon is never constructed, or when the
    caller genuinely has none to offer. `extra_policies` has the identical
    property: drop it and a cache-redirect file survives an uninstall that
    printed success.

    The tweak preview and the tweak sweep are one `active_policies` list, not
    two reads of it: `remove_paths`, `remove_managed_block`, `remove_shims` and
    four `remove_ban_aliases` calls sit between them, every one writing the same
    ~/.myshellrc and bin_dir the activity predicate reads. Nothing in that set
    changes the answer today — the shim names do not collide with the
    `tools-installer-` helpers and every rc rewrite is marker-scoped — but this
    is the only path that deletes the user's shell config, so the invariant is
    held by construction rather than by that argument staying true.
    """
    ordered = [(tool, removal_plan(tool, default_bin_dir)) for tool in removal_order(tools)]
    paths = list(dict.fromkeys(p for _tool, plan in ordered for p in plan.removable))
    yourself = list(
        dict.fromkeys(p for _tool, plan in ordered for p in plan.yourself if p not in paths)
    )
    commands = [(tool.id, plan.argv) for tool, plan in ordered if plan.argv]
    shimmed = [name for name, installed in guard_status(default_bin_dir).items() if installed]
    # Built once and held across the teardown: the preview below and the sweep
    # at the end act on these same objects, so nothing removed in between can
    # make the two disagree. Re-reading before the sweep would leave the
    # "a preview and its effect cannot diverge" invariant unenforced on the one
    # path that deletes the user's shell config.
    policies = active_policies(
        bundles,
        rc_path=myshellrc_path,
        bin_dir=default_bin_dir,
        zshrc_path=zshrc_path,
        daemon_policy=daemon_policy,
        extra_policies=extra_policies,
    )
    tweaks = tuple(policy.id for policy in policies)
    # Only the keys still holding our value: a key the user changed since is kept (F-3).
    settings_files = [
        (agent, path, removes)
        for agent in receipts.CONFIG_AGENTS
        for path, removes, _kept in ledger_preview(agent, home=Path.home())
    ]
    # A machine whose only tools-installer footprint is an enabled tweak or a settings key must
    # not be told there is nothing to uninstall.
    if not paths and not commands and not shimmed and not tweaks and not settings_files:
        render_uninstall([], console)  # prints the "nothing to uninstall" line
        # Even here the user learns what matched by name and was left alone.
        render_remove_yourself(yourself, console)
        # A daemon with no footprint left never appears in `tweaks`
        # (active_policies includes it only when policy_owned() is True) and
        # needs no confirm --
        # nothing destructive happens, only an internal marker resetting so a
        # later reinstall is genuinely fresh (11-REVIEWS.md cycle 3 finding
        # #13's "already disabled, nothing to sweep" case).
        if daemon_policy is not None and daemon_policy.clear_decided is not None:
            daemon_policy.clear_decided()
        return [], ()
    if paths:
        render_uninstall(paths, console)
    for tool, plan in ordered:
        # Shown before the confirm: the user sees the exact undo and command that will run.
        for undo in plan.unregister:
            console.print(unregister_runs_line(tool.id, undo), markup=False, soft_wrap=True)
        if plan.argv:
            console.print(removal_runs_line(tool.id, plan.argv), markup=False, soft_wrap=True)
    # LIFE-08: a co-install member's removal warns about its group before anything runs.
    pnpm_packages = pnpm_removal_packages(plan.argv for _tool, plan in ordered)

    # A member with no receipt is named only when it is on disk (22-UAT F-3).
    def present(tool: Tool) -> bool:
        return receipts.receipt_exists(tool.id) or is_installed(
            tool, default_bin_dir=default_bin_dir
        )

    for line in co_install_warnings(pnpm_packages, tools, present=present):
        console.print(line, markup=False, soft_wrap=True)
    render_remove_yourself(yourself, console)
    if shimmed:
        console.print(f"The pip/npm ban will also be removed ({', '.join(shimmed)}).")
    if tweaks:
        # Byte-identical to today when no daemon: id is among the offered ids
        # (Linux, or the daemon never enabled) — the tail is appended only
        # when one is present.
        tail = " and the background maintenance job" if _has_daemon_id(tweaks) else ""
        console.print(f"These shell tweaks{tail} will also be disabled ({', '.join(tweaks)}).")
        # Name the plugins and the file: .zshrc is the one file in the sweep the
        # installer does not own, so "omz-plugins" alone is not enough for the
        # user to consent to what happens to it.
        detail = omz_removal_detail(zshrc_path=zshrc_path, state_path=myshellrc_path)
        if detail is not None:
            console.print(f"  omz-plugins {detail}.")
    # SPEC R6 / UI-SPEC A11: the CLI never deletes config, and it says so before the confirm.
    kept_config = [
        entry
        for tool, plan in ordered
        if plan.level != "none"
        for entry, path in config_targets(tool)
        if path in plan.config
    ]
    if kept_config:
        console.print(
            "Config kept; only the Uninstall view deletes config (press c on a row):",
            markup=False,
            soft_wrap=True,
        )
        for entry in kept_config:
            console.print(f"  {entry}", markup=False, soft_wrap=True)
    for line in removal_change_lines(
        (tool for tool, plan in ordered if plan.level != "none"),
        active_tweaks=tweaks,
    ):
        console.print(line, markup=False, soft_wrap=True)
    if any(keys for _agent, _path, keys in settings_files):
        console.print(
            "Agent and editor settings this installer wrote (reverted):",
            markup=False,
            soft_wrap=True,
        )
        for _agent, path, keys in settings_files:
            if not keys:
                continue
            console.print(
                f"  {display_path(path)}: {', '.join(keys)}", markup=False, soft_wrap=True
            )
    if not confirm("Remove these artifacts?"):
        return [], ()
    # H1 (17-REVIEW-opencode.md): the preview is not a permission slip. Each tool
    # re-proves itself at deletion time inside remove_tool (the remover shared with
    # the TUI): a path or command that changed since the preview is reported and
    # refused, and a failed command or delete keeps that tool's receipt.
    removed: list[Path] = []
    failed: list[str] = []
    handled: set[str] = set()
    after: list[SweepResult] = []
    for tool, plan in ordered:
        if plan.level == "none" or tool.id in handled:
            continue
        handled.add(tool.id)
        outcome = remove_tool(
            tool,
            paths=plan.removable,
            argv=plan.argv,
            bin_dir=default_bin_dir,
            runner=runner,
            unregister=plan.unregister,
        )
        for line in outcome.refused:
            console.print(line)
        if outcome.removed:
            removed.extend(plan.removable)
            after.append(
                _after_removal(
                    tool,
                    bundles=bundles,
                    bin_dir=default_bin_dir,
                    myshellrc_path=myshellrc_path,
                    extra_policies=extra_policies,
                    platform_os=platform_os,
                )
            )
            if outcome.unregistered:
                console.print(
                    f"Unregistered from agent hosts: {host_labels(outcome.unregistered)}.",
                    markup=False,
                )
            if outcome.detail:
                console.print(f"{tool.id}: {outcome.detail}")
            else:
                for member, group in retire_group_members(plan.argv, tools, handled):
                    handled.add(member)
                    console.print(removed_with_group_line(member, group), markup=False)
        else:
            console.print(f"{tool.id}: remove failed — {outcome.detail}")
            failed.append(tool.id)
    # O5: the whole-environment run reverts every key the installer wrote, even for an agent
    # whose tool is not being removed; each key still goes only while it holds our value.
    reverted, kept, warnings = _revert_settings(receipts.CONFIG_AGENTS, platform_os=platform_os)
    after.append(SweepResult(warnings=warnings, settings_reverted=reverted, settings_kept=kept))
    done = _merge(after)
    remove_managed_block(myshellrc_path)
    remove_shims(default_bin_dir)
    remove_ban_aliases(myshellrc_path)
    for rc_path in rc_paths:
        remove_ban_aliases(rc_path)
    # Report the sweep's own result, not the preview: only this knows what came
    # off, and a per-policy failure no longer aborts the rest of the teardown.
    # A policy a tool's own removal already turned off is not swept (and reported) twice.
    swept = sweep_policies([policy for policy in policies if policy.id not in done.swept])
    if swept.swept:
        # Byte-identical to today ("Shell tweaks disabled: ...") when no
        # daemon: id is among what the sweep actually swept.
        prefix = (
            "Shell tweaks and the background maintenance job"
            if _has_daemon_id(swept.swept)
            else "Shell tweaks"
        )
        console.print(f"{prefix} disabled: {', '.join(swept.swept)}.")
    if swept.failed:
        console.print(
            f"Could not disable: {', '.join(swept.failed)}. Check permissions and re-run."
        )
    for line in removal_result_lines(done):
        console.print(line, markup=False)
    for warning in (*done.warnings, *swept.warnings):
        console.print(f"Warning: {warning}.")
    # Composition-root-only, and only AFTER the sweep: daemon_policy.remove()
    # itself still calls daemon.record_decided as part of that same sweep
    # call, so clearing the marker BEFORE the sweep would be immediately
    # undone by that call running moments later (11-REVIEWS.md cycle 2
    # finding #17). Cleared whenever the daemon is NOT left in a FAILED state
    # -- whether it was actively swept, or was already off and had nothing to
    # sweep at all -- so a full uninstall+reinstall is genuinely fresh in
    # both cases, while a genuine removal failure still preserves the marker
    # (11-REVIEWS.md cycle 3 finding #13).
    if (
        daemon_policy is not None
        and daemon_policy.id not in swept.failed
        and daemon_policy.clear_decided is not None
    ):
        daemon_policy.clear_decided()
    return removed, tuple(failed)


@dataclass(frozen=True)
class UninstallDecision:
    """The levers the in-app uninstall view collected: the previewed artifact
    paths of each selected tool (by tool id), plus whether to also remove the
    pip/npm ban, the managed PATH block, and the still-enabled shell tweaks.
    `tools` are the selected tools, so deletion re-proves per tool exactly like
    the CLI (L-19-06)."""

    tools: tuple[Tool, ...]
    paths: Mapping[str, tuple[Path, ...]]
    remove_ban: bool
    remove_path_block: bool
    remove_tweaks: bool = False
    # The vendor or manager command each tool's preview showed (empty when it has none).
    argv: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])
    # Per tool id: the declared config paths (expanded) the user chose to delete (D-11).
    # Empty by default, and the CLI never sets it: only the Uninstall view does.
    config: Mapping[str, tuple[Path, ...]] = field(default_factory=dict[str, tuple[Path, ...]])
    # The hook undo each tool's preview showed (D-04); empty for a tool with none.
    unregister: Mapping[str, tuple[tuple[str, ...], ...]] = field(
        default_factory=dict[str, tuple[tuple[str, ...], ...]]
    )
    # The environment row: revert every key the ledgers record, for every settings agent (O5).
    revert_settings: bool = False


def _config_step(
    decision: UninstallDecision, catalog: Sequence[Tool], removed: Sequence[str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """D-07 step 4 (SPEC R6): delete each listed config path once, after its removal.

    A path goes only when every catalog tool that declares it was removed and lists it, so
    a shared path survives while any owner stays (UI-SPEC A5). A path no catalog tool
    declares is never deleted. Returns (the ids whose listed config is gone, the warnings)."""
    deleted: list[str] = []
    warnings: list[str] = []
    for path in dict.fromkeys(p for paths in decision.config.values() for p in paths):
        owners = [
            (tool, entry)
            for tool in catalog
            for entry, expanded in config_targets(tool)
            if expanded == path
        ]
        if not owners:
            warnings.append(f"config {path} is not declared by any tool; not deleted")
            continue
        if not all(
            tool.id in removed and path in decision.config.get(tool.id, ()) for tool, _ in owners
        ):
            continue
        try:
            delete_config_path(path)
        except OSError as exc:
            warnings.append(f"could not delete config {owners[0][1]} — {first_line(exc)}")
            continue
        deleted.extend(tool.id for tool, _ in owners)
    return tuple(dict.fromkeys(deleted)), tuple(warnings)


def perform_uninstall(
    decision: UninstallDecision,
    *,
    bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
    bundles: tuple[TweakBundle, ...],
    zshrc_path: Path,
    daemon_policy: Policy | None,
    extra_policies: tuple[Policy, ...],
    runner: Runner,
    catalog: Sequence[Tool],
    platform_os: str = HOST_SETTINGS_OS,
) -> SweepResult:
    """Apply exactly the levers the view chose, composing the existing core
    removers. `catalog` is the whole registry (review R1-15): a config path is shared with
    every tool that declares it, selected or not, so the shared-owner rule cannot narrow.
    Unlike `run_uninstall`, nothing is removed all-or-nothing: a
    partial selection leaves the ban and PATH wiring untouched. Each selected
    tool is removed on its own: the result's `removed` and `remove_failed`
    name every tool's outcome, and one refusal or failed delete (`OSError`)
    never stops the next tool or the environment levers.

    Returns what the tweak sweep actually did, so the view reports its effect
    rather than the snapshot it rendered its rows from. Empty when the sweep
    lever was not selected.

    `bundles`, `zshrc_path`, `daemon_policy`, and `extra_policies` are required
    for the same reason they are on `run_uninstall`: this is a composition-root
    entry point, and a dropped kwarg here silently narrows a teardown instead
    of narrowing a test. `daemon_policy` is `None` on any platform where the
    daemon is never constructed, or when the caller genuinely has none to
    offer. Dropping `extra_policies` leaves a cache-redirect file on disk
    while the uninstall reports success."""
    # H1 (17-REVIEW-opencode.md): the same remover and deletion-time re-proof
    # as run_uninstall. A path no longer proven (its link swapped for a foreign
    # file, dangling, looping, a drifted receipt) is refused and reported
    # through SweepResult.warnings, which the UninstallScreen already renders;
    # the rest go ahead.
    # D-08: tool by tool, so one tool's refusal never stops the next. The
    # tool's current plan must still name every path its preview showed,
    # `yourself` included (a path that drifted since the preview is no longer
    # proven; the name match still ties it to its tool), and no removable path
    # the preview did not show. When it does not, the plan changed under the
    # confirm (a receipt rewritten by a reinstall), so none of the tool is
    # touched and its receipt stays.
    refused: tuple[str, ...] = ()
    removed: list[str] = []
    remove_failed: list[tuple[str, str]] = []
    with_group: list[str] = []
    unregistered: list[str] = []
    after: list[SweepResult] = []
    for tool in removal_order(decision.tools):
        if tool.id in removed:  # retired with its pnpm group earlier in this run
            continue
        argv = decision.argv.get(tool.id, ())
        outcome = remove_tool(
            tool,
            paths=decision.paths.get(tool.id, ()),
            argv=argv,
            bin_dir=bin_dir,
            runner=runner,
            unregister=decision.unregister.get(tool.id, ()),
        )
        refused += outcome.refused
        unregistered.extend(outcome.unregistered)
        if outcome.removed:
            removed.append(tool.id)
            after.append(
                _after_removal(
                    tool,
                    bundles=bundles,
                    bin_dir=bin_dir,
                    myshellrc_path=myshellrc_path,
                    extra_policies=extra_policies,
                    platform_os=platform_os,
                )
            )
        else:
            remove_failed.append((tool.id, outcome.detail))
        if outcome.removed and not outcome.detail:
            handled = {*removed, *(tool_id for tool_id, _ in remove_failed)}
            for member, group in retire_group_members(argv, catalog, handled):
                removed.append(member)
                with_group.append(removed_with_group_line(member, group))
    # Step 4 runs once, after every tool's removal (D-07). A tool whose removal failed or was
    # refused keeps its config, and a failed delete is a warning that never restores a receipt.
    config_deleted, config_warnings = _config_step(decision, catalog, removed)
    config_not_deleted = tuple(
        tool.id
        for tool in decision.tools
        if decision.config.get(tool.id) and tool.id not in removed
    )
    if decision.revert_settings:
        reverted, kept, warnings = _revert_settings(receipts.CONFIG_AGENTS, platform_os=platform_os)
        after.append(SweepResult(warnings=warnings, settings_reverted=reverted, settings_kept=kept))
    done = _merge(after)
    if decision.remove_ban:
        remove_shims(bin_dir)
        remove_ban_aliases(myshellrc_path)
        for rc_path in rc_paths:
            remove_ban_aliases(rc_path)
    if decision.remove_path_block:
        remove_managed_block(myshellrc_path)
    swept = SweepResult()
    if decision.remove_tweaks:
        swept = sweep_tweaks(
            bundles,
            rc_path=myshellrc_path,
            bin_dir=bin_dir,
            zshrc_path=zshrc_path,
            daemon_policy=daemon_policy,
            extra_policies=extra_policies,
        )
        # Same post-sweep, composition-root-only marker clear as run_uninstall
        # (see that function's own comment for the full ordering rationale).
        if (
            daemon_policy is not None
            and daemon_policy.id not in swept.failed
            and daemon_policy.clear_decided is not None
        ):
            daemon_policy.clear_decided()
    # decision.remove_tweaks is False here -- either the user genuinely left
    # an ACTIVE tweaks row unselected (keep the marker, nothing to clear), or
    # there was no tweaks row to select at all because the daemon was already
    # inactive (an already-disabled daemon never appears in active_policies).
    # Only the second case should still clear the marker, mirroring
    # run_uninstall's own "nothing to sweep" early-return branch -- an
    # already-off daemon leaves no active state for a skipped selection to
    # preserve, so a full visible uninstall must still leave the machine
    # genuinely fresh (post-implementation review finding, second lane).
    elif (
        daemon_policy is not None
        and daemon_policy.clear_decided is not None
        and not policy_owned(daemon_policy)
    ):
        daemon_policy.clear_decided()
    merged = _merge([done, swept])
    return dataclasses.replace(
        merged,
        warnings=merged.warnings + refused + config_warnings,
        removed=tuple(removed),
        remove_failed=tuple(remove_failed),
        config_deleted=config_deleted,
        config_not_deleted=config_not_deleted,
        with_group=tuple(with_group),
        unregistered=tuple(sorted(set(unregistered))),
    )
