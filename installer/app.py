"""The interactive wizard flow: select -> audit -> confirm -> install -> summarize."""

import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from rich.console import Console

from installer.audit import audit
from installer.cli import Options
from installer.doctor import DoctorReport, audit_path
from installer.engine import install_tool
from installer.guards import (
    guard_path_warning,
    install_shims,
    remove_ban_aliases,
    remove_shims,
    write_ban_aliases,
)
from installer.model import Tool
from installer.platform import Platform
from installer.prompt import Prompter
from installer.rcclean import find_duplicate_path_lines, strip_lines
from installer.render import (
    render_audit,
    render_doctor,
    render_guard,
    render_rc_duplicates,
    render_summary,
    render_uninstall,
    render_verification,
)
from installer.run import Runner, run_command
from installer.selection import category_choices, select_tools, tool_choices
from installer.session import (
    Install,
    OnMismatch,
    Summary,
    order_for_install,
    run_installs,
    summarize,
)
from installer.shellrc import (
    collect_bin_dirs,
    ensure_source,
    remove_managed_block,
    write_managed_path,
    write_myshellrc,
)
from installer.status import is_installed
from installer.uninstall import plan_uninstall, remove_paths
from installer.versions import TagResolver, resolve_github_tag

# Catalog selection seam: given the full catalog (platform applicability is
# resolved at install time), return the chosen ids (the Textual screen in
# production), or None when the user aborted.
SelectCatalog = Callable[[list[Tool]], list[str] | None]


def _choose_tools(
    tools: list[Tool],
    prompter: Prompter,
    options: Options,
    installed: Callable[[Tool], bool],
    category_blurbs: dict[str, str] | None = None,
    select_catalog: SelectCatalog | None = None,
) -> list[Tool] | None:
    """The tools to install, or None when the user aborted the selection screen."""
    if options.all:
        return tools
    if options.categories:  # flags always win over the interactive seam
        return [tool for tool in tools if tool.category in options.categories]
    if select_catalog is not None:
        chosen_ids = select_catalog(tools)
        if chosen_ids is None:
            return None
        return select_tools(tools, chosen_ids)
    chosen_categories = prompter.select_categories(category_choices(tools, category_blurbs))
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
    on_mismatch: OnMismatch | None = None,
    category_blurbs: dict[str, str] | None = None,
    select_catalog: SelectCatalog | None = None,
) -> Summary | None:
    """Drive the full wizard. Returns the install summary, or None if the user declined.

    None (aborted) is distinct from an empty Summary (ran, but nothing to install).
    --yes implies unattended: the mismatch prompt is suppressed and a checksum
    mismatch hard-fails that tool.
    category_blurbs feeds the category menu's hover descriptions.
    select_catalog, when given, replaces the whole two-step category->tool
    selection (including its intermediate audit) with the single catalog
    screen; its None return (user aborted) aborts the wizard.
    """
    selected = _choose_tools(tools, prompter, options, installed, category_blurbs, select_catalog)
    if selected is None:
        return None
    statuses = audit(selected, installed)
    render_audit(statuses, console)
    if not options.yes and not prompter.confirm("Install the selected tools?"):
        return None
    ordered = order_for_install(selected)
    outcomes = run_installs(
        ordered,
        platform,
        runner,
        resolve_tag,
        install,
        on_mismatch=None if options.yes else on_mismatch,
    )
    summary = summarize(outcomes)
    render_summary(summary, console)
    render_verification(outcomes, console)
    return summary


def configure_path(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
    link_mode: str = "centralized",
    exists: Callable[[Path], bool] = Path.is_dir,
) -> None:
    """Wire the managed PATH into the shells per `link_mode`.

    centralized/single: write ~/.myshellrc and `source` it from each rc path (the
    caller passes one rc for single, both for centralized). split: write the managed
    PATH block directly into each rc path, with no ~/.myshellrc indirection.
    Only bin dirs that pass `exists` are managed (the default always is).
    """
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir, exists)
    if link_mode == "split":
        for rc_path in rc_paths:
            write_managed_path(rc_path, bin_dirs)
        targets = ", ".join(str(rc_path) for rc_path in rc_paths)
        console.print(f"PATH written into {targets} (restart your shell).")
        return
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
    hint: str,
) -> DoctorReport:
    """Audit the PATH (read-only) and render the report; `hint` is the next-step line.

    Fixing is a separate explicit action (configure_path, reached via --fix):
    a diagnosis that silently rewrites shell config is what this split removes.
    """
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir, exists)
    report = audit_path(bin_dirs, path_value, exists)
    render_doctor(report, console, hint)
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
    indices_by_file: dict[Path, list[int]] = {}
    for rc_path in rc_paths:
        if not rc_path.exists():
            continue
        text = rc_path.read_text()
        indices = find_duplicate_path_lines(text, managed_dirs, env)
        if indices:
            lines = text.split("\n")
            found[rc_path] = [lines[index] for index in indices]
            indices_by_file[rc_path] = indices
    render_rc_duplicates(found, console)
    if not found:
        return {}
    if not confirm("Remove these duplicate PATH lines?"):
        return {}
    for rc_path, indices in indices_by_file.items():
        rc_path.write_text(strip_lines(rc_path.read_text(), indices))
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
    if not confirm(f"{verb} the pip/npm ban (shims in {shim_dir} + aliases in {targets})?"):
        return False
    if remove:
        actions = remove_shims(shim_dir)
        for rc_path in rc_paths:
            remove_ban_aliases(rc_path)
        render_guard(actions, None, console, removing=True)
        return True
    actions = install_shims(shim_dir)
    for rc_path in rc_paths:
        write_ban_aliases(rc_path)
    render_guard(actions, guard_path_warning(shim_dir, path_value, which), console, removing=False)
    return True


def run_uninstall(
    tools: list[Tool],
    console: Console,
    *,
    default_bin_dir: Path,
    myshellrc_path: Path,
    confirm: Callable[[str], bool],
) -> list[Path]:
    """Preview userspace artifacts, confirm, then remove them and strip the PATH block.

    Returns the removed paths ([] if there was nothing to remove or the user declined).
    """
    paths = plan_uninstall(tools, default_bin_dir)
    render_uninstall(paths, console)
    if not paths:
        return []
    if not confirm("Remove these artifacts?"):
        return []
    remove_paths(paths)
    remove_managed_block(myshellrc_path)
    return paths
