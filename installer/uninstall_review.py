"""The Uninstall view's inputs and the pure helpers that build its review rows and confirm text."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text

from installer.app import (
    UninstallDecision,
)
from installer.enums import UninstallState
from installer.model import Tool
from installer.render import fold_reason
from installer.uninstall import (
    RemovalPlan,
    SweepResult,
    config_targets,
)
from installer.version_status import (
    ToolState,
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
