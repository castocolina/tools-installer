"""The Uninstall view's inputs and the pure helpers that build its review rows and confirm text."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from rich.text import Text

from installer.app import (
    UninstallDecision,
    has_schedule_id,
    schedule_phrase,
)
from installer.catalog_tui import health_cell
from installer.enums import UninstallState
from installer.locations import display_path
from installer.model import Tool
from installer.render import fold_reason
from installer.sanitize import sanitize_log_line
from installer.ui_common import mark, multiline_summary
from installer.uninstall import (
    RemovalPlan,
    SweepResult,
    config_targets,
)
from installer.version_status import (
    ToolState,
    uninstall_detail,
)


@dataclass(frozen=True)
class UninstallInputs:
    """Everything the UninstallScreen needs besides the published tool state:
    whether a managed PATH block exists, the active shell-tweak ids, and the live
    removal closure bound by the composition root.

    `has_path_block`, `tweak_ids` and `retired` are PREDICATES, not their
    results, because each is mutated live by another view in the same process:
    the Policies view toggles the tweaks, and the Doctor view writes the very
    managed PATH block `has_path_block` detects. A value frozen at construction
    goes stale the moment the user does. `UninstallScreen` re-reads all three on
    every entry and on every publish. `retired` re-lists the receipts whose tool id
    left the catalog (D-09).
    The tool rows are not an input: they are a projection of the
    published state (`version_status.uninstall_group`, `uninstall_label` and
    `uninstall_detail`), so no second classification can disagree with it."""

    has_path_block: Callable[[], bool]
    remove: Callable[[UninstallDecision], SweepResult]
    tweak_ids: Callable[[], tuple[str, ...]] = tuple
    retired: Callable[[], Sequence[Tool]] = tuple
    # The one composition-root closure Policies, the direct `u` update,
    # unattended installation, the CLI uninstall route, and interactive
    # ExecuteScreen close share. Called from
    # `on_removal_finished` only after `remove` reports a sweep, so a
    # completed removal always leaves terminal shell configuration in sync
    # (or safely reverted when zsh itself was just removed).
    terminal_sync: Callable[[], str | None] | None = None
    # The platform key (`Platform.os`), which words the timer sentence on the tweaks row; only
    # "macos" is compared, every other key is Linux.
    platform_os: str = ""


@dataclass(frozen=True)
class UninstallEntry:
    """A browsable uninstall row: either a classified tool or an environment
    pseudo-row (the managed PATH block, the shell tweaks, or the settings).

    `key` is the stable id (a tool id, or "#path-block"/"#tweaks"/"#settings"). `cells`
    are the pre-rendered columns. `selectable` gates toggling (removable tools and
    the env rows are selectable; managed/absent/unavailable tools are not).
    `detail` is the detail-bar line. `paths` are the tool's removable artifacts
    (empty for env rows). `is_path_block`/`is_tweaks`/`is_settings` flag the env rows
    so a selection maps back to the UninstallDecision levers. `tool` is the
    tool for a tool row, None for an environment row. `group` is the section a
    tool row sits in (`uninstall_group`), None for an environment row."""

    key: str
    cells: list[Text]
    selectable: bool
    detail: str
    paths: tuple[Path, ...]
    is_path_block: bool
    is_tweaks: bool = False
    is_settings: bool = False
    tool: Tool | None = None
    group: UninstallState | None = None
    # The command the row's preview showed; the decision hands it back to the remover.
    argv: tuple[str, ...] = ()
    # The hook undo the row's preview showed (D-04); the decision hands it back the same way.
    unregister: tuple[tuple[str, ...], ...] = ()
    # A retired receipt's row (D-09): `tool` is set, `group` is None, there is no catalog state.
    is_retired: bool = False
    # The removal plan a retired row shows; the detail bar and the confirm review read it.
    retired_plan: RemovalPlan | None = None


# Section titles per state, in display order. The "environment" section holds the
# PATH/tweak/settings pseudo-rows.
STATE_TITLES: tuple[tuple[UninstallState, str], ...] = (
    (UninstallState.REMOVABLE, "removable here"),
    (UninstallState.MANAGED, "managed elsewhere"),
    (UninstallState.ABSENT, "nothing to do"),
    (UninstallState.UNAVAILABLE, "nothing to do"),
)
# The "What gets removed" cell has a fixed budget because left/right switch
# views, so a too-wide table can never be scrolled on the screen whose Enter
# deletes files; ConfirmUninstall still lists every path.
REMOVES_CELL_MAX = 40
NOTHING_TO_UNINSTALL = "Nothing to uninstall."
BLOCK_KEY = "#path-block"
TWEAK_KEY = "#tweaks"
SETTINGS_KEY = "#settings"
ENV_KEYS = (BLOCK_KEY, TWEAK_KEY, SETTINGS_KEY)
# (PATH block present, active tweak ids, ledgered settings files, retired receipts
# with the removal plan each one shows)
EnvState = tuple[
    bool,
    tuple[str, ...],
    tuple[Path, ...],
    tuple[tuple[Tool, RemovalPlan], ...],
]


def config_split(
    flagged: Sequence[Tool],
    catalog: Sequence[Tool],
    state_of: Callable[[Tool], ToolState | None],
) -> tuple[dict[str, tuple[Path, ...]], dict[str, tuple[str, ...]]]:
    """Which declared config each flagged tool deletes, and which it keeps (UI-SPEC A5).

    The first map is tool id -> its existing expanded config paths that every catalog
    tool declaring the path has flagged. The second maps a kept path's declared `~`
    form to the declaring tool ids that stay. Existence comes from each flagged tool's
    published state, so this never touches the filesystem on the UI thread.
    """
    flagged_ids = {tool.id for tool in flagged}
    deleted: dict[str, tuple[Path, ...]] = {}
    kept: dict[str, tuple[str, ...]] = {}
    for tool in flagged:
        state = state_of(tool)
        if state is None:
            continue
        for entry, path in config_targets(tool):
            if path not in state.removable.config:
                continue
            declaring = [other for other in catalog if path in dict(config_targets(other)).values()]
            staying = tuple(other.id for other in declaring if other.id not in flagged_ids)
            if staying:
                kept[entry] = tuple(dict.fromkeys((*kept.get(entry, ()), *staying)))
            else:
                deleted[tool.id] = (*deleted.get(tool.id, ()), path)
    return deleted, kept


_REVIEW_COLUMN = 54  # the confirm modal's text column: width 60 less the border and padding


def review_line(text: str, style: str = "") -> Text:
    """One review line, folded at the text column with a 2-cell hanging indent (UI-SPEC)."""
    line = fold_reason(Text(), text, 2, _REVIEW_COLUMN)
    line.stylize(style)
    return line


def retired_detail(tool_id: str, plan: RemovalPlan) -> str:
    """A retired row's detail bar (UI-SPEC section 2): what is proven and what the user removes."""
    head = f"retired: {tool_id} is no longer in the catalog"
    if plan.hint is not None:  # a manager kind: the user removes the package, nothing runs
        return f"{head} · {plan.hint}"
    if plan.yourself:
        leftover = f"remove it yourself: {', '.join(str(path) for path in plan.yourself)}"
        proven = " · recorded files re-checked before deletion" if plan.removable else ""
        return f"{head}{proven} · {leftover}"
    if plan.removable:
        return f"{head} · recorded files re-checked before deletion"
    return f"{head} · nothing to delete; confirming retires the receipt"


def retired_review_lines(tool_id: str, plan: RemovalPlan) -> list[str]:
    """A selected retired row's confirm-review lines, in a catalog row's `<id>: ...` shape."""
    if plan.hint is not None:  # a manager kind: the user removes the package
        return [f"{tool_id}: {plan.hint}"]
    lines: list[str] = []
    if plan.removable:
        lines.append(f"{tool_id}: deletes {', '.join(str(path) for path in plan.removable)}")
    if plan.yourself:
        kept = ", ".join(str(path) for path in plan.yourself)
        lines.append(f"{tool_id}: remove it yourself: {kept}")
    return lines or [f"{tool_id}: nothing to delete; confirming retires the receipt"]


def config_clause(tool: Tool, state: ToolState, flagged: bool) -> str:
    """The detail clause for a removable row's declared config (UI-SPEC, How a row shows it)."""
    if not tool.config_paths:
        return ""
    existing = [entry for entry, path in config_targets(tool) if path in state.removable.config]
    where = ", ".join(existing) or "none on disk"
    if flagged:
        return f"config deleted too: {where} (c keeps it)"
    return f"config kept: {where} (c deletes it too)"


def block_entry() -> UninstallEntry:
    return UninstallEntry(
        key=BLOCK_KEY,
        cells=[
            mark(False),
            Text("PATH wiring", style="bold yellow"),
            Text(""),
            Text("env", style="yellow"),
            Text("shell config", style="dim"),
            Text("managed block in ~/.myshellrc", style="dim"),
        ],
        selectable=True,
        detail="PATH wiring — the managed block in ~/.myshellrc",
        paths=(),
        is_path_block=True,
    )


def retired_entry(tool: Tool, plan: RemovalPlan) -> UninstallEntry:
    """A retired receipt's row (D-09, UI-SPEC section 2): removal only, no install or update."""
    selectable = plan.level != "none"
    shown = ", ".join(str(path) for path in plan.removable) or "—"
    removes = Text(sanitize_log_line(shown))
    removes.truncate(REMOVES_CELL_MAX, overflow="ellipsis")
    name = Text(sanitize_log_line(tool.id), style="bold")
    name.append(" (retired)", style="dim")
    return UninstallEntry(
        key=tool.id,
        cells=[
            mark(False) if selectable else Text(""),
            name,
            Text(""),
            Text("retired", style="dim"),
            Text(""),
            removes,
        ],
        selectable=selectable,
        detail=sanitize_log_line(retired_detail(tool.id, plan)),
        paths=plan.removable,
        is_path_block=False,
        tool=tool,
        argv=plan.argv,
        unregister=plan.unregister,
        is_retired=True,
        retired_plan=plan,
    )


def accept_summary(ids: list[str]) -> str:
    tool_count = sum(1 for key in ids if key not in ENV_KEYS)
    parts: list[str] = []
    if tool_count:
        parts.append(f"{tool_count} tool(s)")
    if BLOCK_KEY in ids:
        parts.append("the PATH wiring")
    if TWEAK_KEY in ids:
        parts.append("the shell tweaks")
    if SETTINGS_KEY in ids:
        parts.append("the agent/editor settings")
    return ", ".join(parts)


def config_lines(decision: UninstallDecision, swept: SweepResult) -> list[str]:
    """UI-SPEC Removal results: what became of each tool's config, in the order deleted,
    kept, not deleted. Kept means a removed tool whose declared config is still on disk and
    was not flagged. The check reads the disk now: the cache invalidation that follows a
    removal leaves no published state to read it from (its epoch moved on)."""
    kept = [
        tool.id
        for tool in decision.tools
        if tool.id in swept.removed
        and tool.id not in decision.config
        and any(path.is_symlink() or path.exists() for _, path in config_targets(tool))
    ]
    lines: list[str] = []
    if swept.config_deleted:
        lines.append(f"Config deleted for {', '.join(swept.config_deleted)}.")
    if kept:
        lines.append(f"Config kept for {', '.join(kept)}.")
    if swept.config_not_deleted:
        lines.append(
            f"Config not deleted for {', '.join(swept.config_not_deleted)}: the removal failed."
        )
    return [sanitize_log_line(line) for line in lines]


def unknown_entry(
    tool: Tool, state: ToolState | None, painted: UninstallEntry | None
) -> UninstallEntry:
    """A tool whose state is not known yet: what it was last painted with,
    its Health cell set to `…`; a row never painted before is an unselectable
    `nothing to do` row (T-21-18)."""
    if painted is not None:
        cells = [*painted.cells]
        cells[2] = health_cell(state)
        return replace(painted, cells=cells)
    return UninstallEntry(
        key=tool.id,
        cells=[
            Text(""),
            Text(tool.id, style="dim"),
            health_cell(state),
            Text(tool.category, style="dim"),
            Text("—", style="dim"),
            Text("—", style="dim"),
        ],
        selectable=False,
        detail=uninstall_detail(tool, state),
        paths=(),
        is_path_block=False,
        tool=tool,
        group=UninstallState.ABSENT,
    )


def tweak_entry(tweak_ids: tuple[str, ...], platform_os: str) -> UninstallEntry:
    # The label and detail only name the background jobs when a schedule: id is among the
    # offered ids.
    has_schedule = has_schedule_id(tweak_ids)
    has_redirect = any(policy_id.startswith("cache-redirect:") for policy_id in tweak_ids)
    label = "shell tweaks + background jobs" if has_schedule else "shell tweaks"
    detail = (
        "Disables every enabled shell tweak — the ~/.myshellrc blocks, "
        "the managed helper executables, and the Oh-My-Zsh plugin names "
        "this installer added to .zshrc (never ones you added yourself)"
    )
    if has_schedule and platform_os == "macos":
        detail += (
            " — and unregisters the background maintenance LaunchAgents"
            " (their plists, the runner and the schedule state)"
        )
    elif has_schedule:
        detail += (
            " — and unregisters the systemd user timers (their unit files, the runner and"
            " the schedule state)"
        )
    if has_redirect:
        detail += "; the environment cache redirect is removed too"
    return UninstallEntry(
        key=TWEAK_KEY,
        cells=[
            mark(False),
            Text(label, style="bold yellow"),
            Text(""),
            Text("env", style="yellow"),
            Text("shell config", style="dim"),
            Text(f"blocks + helpers ({', '.join(tweak_ids)})", style="dim"),
        ],
        selectable=True,
        detail=detail,
        paths=(),
        is_path_block=False,
        is_tweaks=True,
    )


def settings_entry(settings_files: tuple[Path, ...]) -> UninstallEntry:
    """The agent and editor settings row (UI-SPEC section 6, O5): one revert for every key
    the ledgers record, which never touches a key the user changed since."""
    files = ", ".join(display_path(path) for path in settings_files)
    return UninstallEntry(
        key=SETTINGS_KEY,
        cells=[
            mark(False),
            Text("agent/editor settings", style="bold yellow"),
            Text(""),
            Text("env", style="yellow"),
            Text("shell config", style="dim"),
            Text(f"keys this installer wrote in {len(settings_files)} file(s)", style="dim"),
        ],
        selectable=True,
        detail=f"reverts only keys that still hold this installer's value: {files}",
        paths=(),
        is_path_block=False,
        is_settings=True,
    )


def applied_summary(decision: UninstallDecision, swept: SweepResult, platform_os: str) -> str:
    parts: list[str] = []
    if decision.remove_path_block:
        parts.append("PATH wiring removed — restart your shell to drop the managed dirs.")
    if decision.remove_tweaks:
        # From the sweep's own result, never from the row's snapshot: the
        # snapshot describes what was offered, not what came off.
        if swept.swept:
            # When a schedule: id is among what was actually swept, name it
            # explicitly and append the shell-reload hint only if a real,
            # non-schedule tweak was ALSO swept -- a timer needs no shell
            # reload at all.
            phrase = schedule_phrase(swept.swept)
            has_schedule = bool(phrase)
            has_redirect = any(sid.startswith("cache-redirect:") for sid in swept.swept)
            has_other = any(not sid.startswith("schedule:") for sid in swept.swept)
            prefix = f"shell tweaks and {phrase}" if has_schedule else "shell tweaks"
            if has_schedule and platform_os != "macos" and has_redirect:
                reload_hint = " — log out and back in so the environment redirect is dropped."
            elif not has_schedule or has_other:
                reload_hint = " — open a new shell so functions and aliases refresh."
            else:
                reload_hint = "."
            parts.append(f"{prefix} disabled ({', '.join(swept.swept)}){reload_hint}")
        if swept.failed:
            parts.append(
                f"could not disable {', '.join(swept.failed)} — check permissions and re-run."
            )
        if not swept.swept and not swept.failed:
            parts.append("no shell tweaks were still enabled — nothing to disable.")
    # Refused paths travel here too, so they show whatever levers were chosen.
    parts.extend(f"warning: {sanitize_log_line(warning)}." for warning in swept.warnings)
    # One line per outcome: a single joined line overflows the terminal width and
    # truncates the reload guidance, so the "needs a new shell" steps go unseen.
    return multiline_summary(parts)
