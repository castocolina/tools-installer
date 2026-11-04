"""Headless wizard planning and install lifecycle flows."""

import contextlib
import dataclasses
import os
import shlex
import shutil
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from installer import receipts, shellrc
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
from installer.locations import path_scan_rc_paths
from installer.model import Tool
from installer.platform import Platform
from installer.pnpm_globals import audit_node_globals, co_install_warnings, pnpm_global_packages
from installer.policy import Policy, omz_removal_detail
from installer.prompt import Prompter
from installer.rcclean import (
    PathWriterLine,
    find_duplicate_path_lines,
    group_writer_lines,
    scan_rc_path_writer_lines,
    strip_lines,
)
from installer.render import (
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
)
from installer.run import CommandError, Runner, run_command
from installer.session import (
    RUNNABLE,
    Disposition,
    OnMismatch,
    RowOutcome,
    RunContext,
    SensitiveInstall,
    build_plan,
    execute_plan,
    first_line,
)
from installer.shellrc import (
    collect_bin_dirs,
    ensure_source,
    remove_managed_block,
    write_managed_path,
    write_myshellrc,
)
from installer.systemd_daemon import CompetingUnit
from installer.tweaks import TweakBundle
from installer.uninstall import (
    MANAGER_UNINSTALL_ARGV,
    RemovalPlan,
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
    if options.yes or has_runnable_row:
        for line in refresh.commit_writes():
            console.print(line, markup=False, highlight=False, soft_wrap=True)

    def confirm_sensitive(tool_id: str, _action: str) -> bool:
        return prompter.confirm(
            f"Show a reviewed command to change the login shell to zsh for {tool_id}, "
            "which you run in your own terminal after the installer exits?"
        )

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
    )
    outcomes = execute_plan(rows, context)
    render_run_report(outcomes, console)
    return outcomes


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
    """One tool's removal outcome. `detail` is its one-line reason when it was not removed."""

    tool_id: str
    removed: bool
    detail: str = ""
    refused: tuple[str, ...] = ()


def removal_runs_line(tool_id: str, argv: Sequence[str]) -> str:
    """The line the CLI and the preview print before a vendor or manager command runs."""
    return f"{tool_id}: runs {shlex.join(argv)}"


# pnpm's code for a global removal whose package is not installed (measured on pnpm 12.16.1).
PNPM_GLOBAL_PKG_NOT_FOUND = "ERR_PNPM_GLOBAL_PKG_NOT_FOUND"


def pnpm_removal_packages(plans: Iterable[RemovalPlan]) -> frozenset[str]:
    """The packages the pnpm removals in `plans` name, which the group warnings check against.
    `pnpm remove --global <pkg>` removes the whole install group `<pkg>` belongs to (22-13
    D-1, measured on pnpm 12.16.1), so a later member's removal finds it already gone."""
    prefix = MANAGER_UNINSTALL_ARGV["node"]
    return frozenset(plan.argv[-1] for plan in plans if plan.argv[:-1] == prefix)


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


def remove_tool(
    tool: Tool,
    *,
    paths: tuple[Path, ...],
    argv: tuple[str, ...],
    bin_dir: Path,
    runner: Runner,
) -> ToolRemoval:
    """Remove one tool: its command, then its proven paths, then its receipt (D-07).

    `paths` and `argv` are what the user saw before the confirm. The fresh plan is
    proven again here, so the CLI and the TUI share the same post-confirm check: a
    previewed path that moved, a command that changed, or a command whose paths shrank
    refuses the whole tool before anything runs. A failed command deletes nothing and
    keeps the receipt, so a later plan still sees the tool."""
    try:
        fresh = removal_plan(tool, bin_dir, verify=True)
        named = {*fresh.removable, *fresh.yourself}
        # A command runs only on the proof it was previewed against: with a command, every
        # previewed path must still be removable, not merely named (review R2-02).
        changed = [p for p in paths if p not in named or (bool(argv) and p not in fresh.removable)]
        changed += [p for p in fresh.removable if p not in paths]
        if changed or argv != fresh.argv or not (paths or argv):
            refused = tuple(f"changed since the preview; not removed: {p}" for p in changed)
            return ToolRemoval(tool.id, False, "changed since the preview; not removed", refused)
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
                # pnpm removes a whole global group from any member (22-13 D-1), so a member an
                # earlier removal took is "not found": pnpm's own proof the package is gone.
                gone = argv[:-1] == MANAGER_UNINSTALL_ARGV["node"] and (
                    PNPM_GLOBAL_PKG_NOT_FOUND in exc.detail
                )
                if not gone:
                    line = next(
                        (ln for ln in exc.detail.splitlines() if ln.strip()), first_line(exc)
                    )
                    return ToolRemoval(tool.id, False, line)
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
        return ToolRemoval(tool.id, True)
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
    # A machine whose only tools-installer footprint is an enabled tweak must
    # not be told there is nothing to uninstall.
    if not paths and not commands and not shimmed and not tweaks:
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
    for tool_id, argv in commands:
        # Shown before the confirm: the user sees the exact command that will run.
        console.print(removal_runs_line(tool_id, argv), markup=False, soft_wrap=True)
    # LIFE-08: a co-install member's removal warns about its group before anything runs.
    pnpm_packages = pnpm_removal_packages(plan for _tool, plan in ordered)
    for line in co_install_warnings(pnpm_packages, tools):
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
    if not confirm("Remove these artifacts?"):
        return [], ()
    # H1 (17-REVIEW-opencode.md): the preview is not a permission slip. Each tool
    # re-proves itself at deletion time inside remove_tool (the remover shared with
    # the TUI): a path or command that changed since the preview is reported and
    # refused, and a failed command or delete keeps that tool's receipt.
    removed: list[Path] = []
    failed: list[str] = []
    for tool, plan in ordered:
        if plan.level == "none":
            continue
        outcome = remove_tool(
            tool,
            paths=plan.removable,
            argv=plan.argv,
            bin_dir=default_bin_dir,
            runner=runner,
        )
        for line in outcome.refused:
            console.print(line)
        if outcome.removed:
            removed.extend(plan.removable)
        else:
            console.print(f"{tool.id}: remove failed — {outcome.detail}")
            failed.append(tool.id)
    remove_managed_block(myshellrc_path)
    remove_shims(default_bin_dir)
    remove_ban_aliases(myshellrc_path)
    for rc_path in rc_paths:
        remove_ban_aliases(rc_path)
    # Report the sweep's own result, not the preview: only this knows what came
    # off, and a per-policy failure no longer aborts the rest of the teardown.
    swept = sweep_policies(policies)
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
    for warning in swept.warnings:
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
    for tool in removal_order(decision.tools):
        outcome = remove_tool(
            tool,
            paths=decision.paths.get(tool.id, ()),
            argv=decision.argv.get(tool.id, ()),
            bin_dir=bin_dir,
            runner=runner,
        )
        refused += outcome.refused
        if outcome.removed:
            removed.append(tool.id)
        else:
            remove_failed.append((tool.id, outcome.detail))
    # Step 4 runs once, after every tool's removal (D-07). A tool whose removal failed or was
    # refused keeps its config, and a failed delete is a warning that never restores a receipt.
    config_deleted, config_warnings = _config_step(decision, catalog, removed)
    config_not_deleted = tuple(
        tool.id
        for tool in decision.tools
        if decision.config.get(tool.id) and tool.id not in removed
    )
    if decision.remove_ban:
        remove_shims(bin_dir)
        remove_ban_aliases(myshellrc_path)
        for rc_path in rc_paths:
            remove_ban_aliases(rc_path)
    if decision.remove_path_block:
        remove_managed_block(myshellrc_path)
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
        return dataclasses.replace(
            swept,
            warnings=swept.warnings + refused + config_warnings,
            removed=tuple(removed),
            remove_failed=tuple(remove_failed),
            config_deleted=config_deleted,
            config_not_deleted=config_not_deleted,
        )
    # decision.remove_tweaks is False here -- either the user genuinely left
    # an ACTIVE tweaks row unselected (keep the marker, nothing to clear), or
    # there was no tweaks row to select at all because the daemon was already
    # inactive (an already-disabled daemon never appears in active_policies).
    # Only the second case should still clear the marker, mirroring
    # run_uninstall's own "nothing to sweep" early-return branch -- an
    # already-off daemon leaves no active state for a skipped selection to
    # preserve, so a full visible uninstall must still leave the machine
    # genuinely fresh (post-implementation review finding, second lane).
    if (
        daemon_policy is not None
        and daemon_policy.clear_decided is not None
        and not policy_owned(daemon_policy)
    ):
        daemon_policy.clear_decided()
    return SweepResult(
        warnings=refused + config_warnings,
        removed=tuple(removed),
        remove_failed=tuple(remove_failed),
        config_deleted=config_deleted,
        config_not_deleted=config_not_deleted,
    )
