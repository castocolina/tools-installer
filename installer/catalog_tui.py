"""Textual catalog selection screen: one screen, switchable grouping views.

The wizard's interactive selection step (uzkit-parity F1): tools grouped by
category, priority, audience, install status, or shown as a flat sortable
table. Pure grouping/sorting helpers live alongside the app so they can be
unit-tested without a terminal. The browsable-list mechanics live in the
reusable `ToolBrowser` widget; this screen wires the catalog's data into it.
"""

from collections.abc import Callable, Mapping
from typing import ClassVar, Literal

from rich.markup import escape
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.widgets import DataTable

from installer.deps import missing_requires
from installer.enums import Audience, Priority
from installer.model import Tool
from installer.ownership import (
    MUTATION_GRADE,
    OWNER_LABELS,
    active_path_note,
    declared_manager_label,
    owner_label,
)
from installer.resolve import UnavailableReason
from installer.selection import select_tools, unstaged_recommends
from installer.skill_lifecycle import SKILL_HARNESS_LABELS
from installer.status import is_default_shell
from installer.tool_browser import BrowserAdapter, Section, ToolBrowser
from installer.ui_common import VIEW_BY_NAME, VIEW_ORDER, AppScreen, StatusLine, mark, run_live
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_status import (
    Health,
    SkillHostStatus,
    ToolState,
    VersionRefreshService,
)

TableSortKey = Literal["id", "category", "priority", "audience", "health"]

PRIORITY_LABEL = {
    Priority.P0: "essential",
    Priority.P1: "recommended",
    Priority.P2: "nice-to-have",
    Priority.P3: "niche",
}
AUDIENCE_LABEL = {Audience.AI: "AI", Audience.HUMAN: "human", Audience.BOTH: "both"}


HealthOf = Callable[[Tool], Health | None]
# Declaration order IS precedence (Health's own docstring); a StrEnum sorts by value.
_HEALTH_RANK = {health: rank for rank, health in enumerate(Health)}


def _health(health_of: HealthOf, tool: Tool) -> Health:
    """No state yet reads as CHECKING."""
    return health_of(tool) or Health.CHECKING


def sort_for_table(tools: list[Tool], health_of: HealthOf, key: TableSortKey) -> list[Tool]:
    """Flat-table order: by `key`, then priority, then id (deterministic)."""
    if key == "health":
        return sorted(tools, key=lambda t: (_HEALTH_RANK[_health(health_of, t)], t.priority, t.id))
    return sorted(tools, key=lambda t: (getattr(t, key), t.priority, t.id))


def _category_title(category: str, blurbs: Mapping[str, str]) -> str:
    blurb = blurbs.get(category, "")
    return f"{category} — {blurb}" if blurb else category


def group_tools(
    tools: list[Tool],
    health_of: HealthOf,
    view: str,
    blurbs: Mapping[str, str],
) -> list[tuple[str, str, list[Tool]]]:
    """(short title, detail line, members) per grouped view; empty groups dropped.

    The short title is what the section row shows in the table — it must stay
    narrow because it lives in the first column and auto-width would otherwise
    inflate it. The detail line (e.g. the category blurb) goes to the detail
    bar when the section row is highlighted. Members are priority-then-id.
    The status view reads each tool's health once, so a publication mid-grouping
    cannot place a tool twice.
    """
    ordered = sorted(tools, key=lambda t: (t.priority, t.id))
    if view == "priority":
        groups = [
            (p.value, f"{p} · {PRIORITY_LABEL[p]}", [t for t in ordered if t.priority == p])
            for p in Priority
        ]
    elif view == "audience":
        titles = {
            a: f"for {AUDIENCE_LABEL[a]}" for a in (Audience.AI, Audience.BOTH, Audience.HUMAN)
        }
        groups = [
            (title, title, [t for t in ordered if t.audience == a]) for a, title in titles.items()
        ]
    elif view == "status":
        healths = {t.id: _health(health_of, t) for t in ordered}
        groups = [
            (
                f"{_HEALTH_CELL[health][0]} {_HEALTH_WORD[health]}",
                _HEALTH_DETAIL[health],
                [t for t in ordered if healths[t.id] is health],
            )
            for health in Health
        ]
    elif view == "category":
        categories = sorted({t.category for t in ordered})
        groups = [
            (c, _category_title(c, blurbs), [t for t in ordered if t.category == c])
            for c in categories
        ]
    else:  # "table" is routed by the app before grouping; anything else is a bug
        raise ValueError(f"unknown view: {view!r}")
    return [(title, detail, members) for title, detail, members in groups if members]


def health_cell(state: ToolState | None) -> Text:
    """The one writer of the Health column (D-15): `…` until a state exists,
    so a pending tool never reads `✓`."""
    glyph, style = _HEALTH_CELL[Health.CHECKING if state is None else state.health]
    return Text(glyph, style=style)


class ToolUpdated(Message):
    """An update worker finished. Applied unconditionally; epoch is recorded."""

    def __init__(
        self,
        tool_id: str,
        outcome: UpdateOutcome | None,
        error: str | None,
        epoch: int,
    ) -> None:
        super().__init__()
        self.tool_id = tool_id
        self.outcome = outcome
        self.error = error
        self.epoch = epoch


class VersionStatusRefreshed(Message):
    """A version-refresh worker finished; generation and epoch both gate apply.

    `generation` discards a superseded worker within one screen (rapid tier
    navigation). `epoch` discards a pass whose view of the machine a mutation
    has since invalidated (Plan 12-03's update action calling invalidate).
    """

    def __init__(
        self,
        generation: int,
        epoch: int,
        *,
        error: str | None = None,
        warning: str | None = None,
    ) -> None:
        super().__init__()
        self.generation = generation
        self.epoch = epoch
        self.error = error
        self.warning = warning


class SkillStatusRefreshed(Message):
    """A skill-pack probe finished. `epoch` discards a pass a mutation superseded."""

    def __init__(self, generation: int, epoch: int) -> None:
        super().__init__()
        self.generation = generation
        self.epoch = epoch


class OwnershipRefreshed(Message):
    """The shared ownership map now holds a committed pass under the current
    epoch -- carries no payload; that fact is its whole meaning.

    Ownership is committed by `VersionRefreshService.refresh` inside the
    threaded worker (`_refresh_versions_worker`, below), so the only moment
    a consumer outside this screen can learn the shared map changed is the
    moment `on_version_status_refreshed` accepts a pass. Posted ONLY from
    that handler's commit path -- after both its existing early returns --
    so a superseded generation and a raced epoch each post nothing: neither
    means the shared map gained a current pass, so there is nothing for a
    consumer to repaint to (15.4-04, Round-2 review HIGH: the async window
    between an install run closing and a mounted Uninstall screen learning
    the real ownership answer arrived).
    """


VIEWS: tuple[str, ...] = ("category", "priority", "audience", "status", "table")
_TAB_LABELS = {
    "category": "Category",
    "priority": "Priority",
    "audience": "Audience",
    "status": "Status",
    "table": "Table",
}
_PRIORITY_STYLE = {
    Priority.P0: "bold red",
    Priority.P1: "bold yellow",
    Priority.P2: "blue",
    Priority.P3: "dim",
}
_AUDIENCE_STYLE = {Audience.AI: "bold cyan", Audience.HUMAN: "magenta", Audience.BOTH: ""}

# Sortable Table-view columns by column key; absent keys (sel/desc) don't sort.
_SORT_BY_COLUMN: dict[str, TableSortKey] = {
    "pri": "priority",
    "tool": "id",
    "cat": "category",
    "for": "audience",
    "health": "health",
}

_COLUMNS = (
    ("Sel", "sel"),
    ("Pri", "pri"),
    ("Tool", "tool"),
    ("Cat", "cat"),
    ("For", "for"),
    ("Health", "health"),
    ("Ver", "ver"),
    # 15.4-01/D-01: a non-sorting column, like sel/ver/desc -- _SORT_BY_COLUMN
    # above is deliberately left untouched (its own comment already documents
    # this as the default for an absent key).
    ("Owner", "owner"),
    ("What it does", "desc"),
)

# The Ver cell's suffix for a comparison against a stale cached latest.
_VER_STALE = "~"
# The Health column's glyph and style per state (19-UI-SPEC): every state has
# its own glyph, so the meaning never depends on color.
_HEALTH_CELL: dict[Health, tuple[str, str]] = {
    Health.CHECKING: ("…", "dim"),
    Health.BROKEN: ("!", "red"),
    Health.MISCONFIGURED: ("≈", "yellow"),
    Health.OUTDATED: ("↑", "yellow"),
    Health.OK: ("✓", "green"),
    Health.MISSING: ("○", ""),
    Health.UNAVAILABLE: ("–", "dim"),
}
# Two registers (19-UI-SPEC A11): the terse legend word and the prose detail label.
_HEALTH_WORD = {
    Health.CHECKING: "checking",
    Health.BROKEN: "broken",
    Health.MISCONFIGURED: "config",
    Health.OUTDATED: "update",
    Health.OK: "ok",
    Health.MISSING: "missing",
    Health.UNAVAILABLE: "unavailable",
}
_HEALTH_DETAIL = {
    Health.CHECKING: "checking…",
    Health.BROKEN: "broken",
    Health.MISCONFIGURED: "needs configuration",
    Health.OUTDATED: "update available",
    Health.OK: "ok",
    Health.MISSING: "not installed",
    Health.UNAVAILABLE: "not available on this machine",
}
# Already this wide for one owner, so a host list truncates only if it would widen the column (D-13)
_OWNER_CELL_MAX = max(len(label) for label in OWNER_LABELS.values())

# 19-UI-SPEC "Legend", verbatim: three lines of at most 78 cells (the 80-column
# minimum minus `padding: 0 1`); lines 1 and 2 have no slack, so a new entry
# replaces an old one. Each entry carries the style of the cell it decodes.
_LEGEND = (
    "[green]✓ ok[/] · [yellow]↑ update[/] · [yellow]≈ config[/] · [red]! broken[/]"
    " · ○ missing · [dim]… checking[/] · [dim]– unavailable[/]\n"
    "[bold red]P0[/] essential · [bold yellow]P1[/] recommended · [blue]P2[/] nice-to-have"
    " · [dim]P3[/] niche · [bold cyan]AI[/] / [magenta]human[/] / both\n"
    "Ver a -> b: newer release · [dim]~[/] cached latest · [dim]≠ policy[/]: other manager owns it"
)


class CatalogScreen(AppScreen):
    """Single-screen tool picker; ←/→ or clicking the tabs switches the grouping.

    One tier-scoped instance per `Tier`; the base screen is whichever tier is
    first in `VIEW_ORDER`. Accept/abort post a `Decided` message carrying the
    whole staged batch in full-catalog order regardless of which instance posted
    it (or None on abort); the host app turns that into its run() result. State
    the tests assert on (view, table_sort, selected, detail_text, status_text)
    is delegated to the embedded `ToolBrowser` (or the screen's StatusLine) and
    exposed as public properties.

    Update output policy: the update runs through `run_captured`, so the
    child's stdout never reaches the rendered frame. The user sees an
    in-flight line, then `updated {id}` (the rows repaint when the
    follow-up pass lands) or the child's stderr from
    `CommandError.detail`. Live streaming of manager output is not built
    this phase.
    """

    class Decided(Message):
        """The user resolved the catalog: `result` is the selected ids in catalog
        order, or None when aborted. The host app forwards it to App.exit when
        `execute=` is omitted; with `execute=` set it pushes an ExecuteScreen
        instead (and still exits on abort)."""

        def __init__(self, result: list[str] | None) -> None:
            super().__init__()
            self.result = result

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("r", "accept_recommends", "add recommended", show=False),
        Binding("d", "dismiss_recommends", "dismiss", show=False),
        Binding("u", "update_tool", "update", show=True),
    ]

    def __init__(
        self,
        tools: list[Tool],
        blurbs: Mapping[str, str],
        *,
        view: str,
        catalog: list[Tool],
        staged: set[str],
        unavailable: Mapping[str, bool | UnavailableReason] | None = None,
        version_refresh: VersionRefreshService | None = None,
        updates: UpdateService | None = None,
    ) -> None:
        super().__init__(view=view)
        self.tools = list(tools)
        self.table_sort: TableSortKey = "priority"
        self._blurbs = dict(blurbs)
        self._catalog = list(catalog)
        self._staged = staged
        self._unavailable = dict(unavailable) if unavailable else {}
        self._by_id = {tool.id: tool for tool in self._catalog}
        # Default None matches UnifiedApp's optional-closure convention: tests
        # that construct a CatalogScreen without a service stay silent.
        self._version_refresh = version_refresh
        self._updates = updates
        self._version_refresh_generation = 0
        self.version_refreshing = False
        self.skill_refreshing = False
        self._browser: ToolBrowser[Tool] = ToolBrowser(self._adapter(), selected=staged)
        self.recommends_line = StatusLine()
        self._pending_recommends: tuple[str, ...] = ()
        # The refresh error or cache warning this screen last showed, so a clean
        # pass clears only its own line, never an unrelated status message.
        self._state_line: str | None = None

    def _adapter(self) -> BrowserAdapter[Tool]:
        return BrowserAdapter(
            items=self.tools,
            columns=_COLUMNS,
            item_id=lambda tool: tool.id,
            row_cells=self._row_cells,
            detail_text=self._detail_text,
            groups=self._groups,
            views=tuple((view, _TAB_LABELS[view]) for view in VIEWS),
            legend=_LEGEND,
            on_sort=self._sort,
            sortable_in_views=frozenset({"table"}),
            selectable=lambda tool: not self._is_unavailable(tool),
            empty_detail=(
                f"No tools in the {VIEW_BY_NAME[self._view].label} tier.\n"
                f"Press 1-{len(VIEW_ORDER)} or ^p to open another view."
            ),
        )

    def compose_body(self) -> ComposeResult:
        yield self._browser
        yield self.recommends_line

    def on_mount(self) -> None:
        self._start_version_refresh()

    def enter_view(self) -> None:
        if self.is_mounted:
            self._start_version_refresh()

    def _start_version_refresh(self) -> None:
        if self._version_refresh is None:
            return
        self._version_refresh_generation += 1
        self.version_refreshing = True
        self.skill_refreshing = True
        # Repaint through the same path the completion handler already uses
        # so the checking marker is something a user can actually see, not
        # only a value _ver_cell returns to a direct caller. Without this,
        # version_refreshing flips on a screen nobody repaints until the
        # worker finishes, so a rendered cell keeps its previous text for the
        # whole refresh. reload's selection-pruning line is a no-op here
        # because self.tools is unchanged between the two adapters; the
        # on_mount call site stays safe because reload guards on is_mounted.
        self._browser.reload(self._adapter())
        generation = self._version_refresh_generation
        self._refresh_versions_worker(generation)
        self._refresh_skills_worker(generation)

    @work(thread=True, exclusive=True, group="version-refresh", exit_on_error=False)
    def _refresh_versions_worker(self, generation: int) -> None:
        epoch = 0
        error: str | None = None
        warning: str | None = None
        service = self._version_refresh
        try:
            if service is not None:
                epoch = service.epoch
                # The whole catalog, never the tier: every tier asks for the same
                # set, so the service joins an in-flight pass instead of repeating it.
                _result, error = run_live(lambda: service.refresh(self._catalog))
                if error is None:
                    warning = service.warning
        finally:
            self.post_message(
                VersionStatusRefreshed(generation, epoch, error=error, warning=warning)
            )

    @work(thread=True, exclusive=True, group="skill-refresh", exit_on_error=False)
    def _refresh_skills_worker(self, generation: int) -> None:
        epoch = 0
        service = self._version_refresh
        try:
            if service is not None:
                epoch = service.epoch
                run_live(lambda: service.refresh_skills(self._catalog))
        finally:
            self.post_message(SkillStatusRefreshed(generation, epoch))

    def on_skill_status_refreshed(self, message: "SkillStatusRefreshed") -> None:
        if message.generation != self._version_refresh_generation:
            return
        self.skill_refreshing = False
        service = self._version_refresh
        if service is None or message.epoch != service.epoch:
            return
        self._browser.reload(self._adapter())

    def on_version_status_refreshed(self, message: "VersionStatusRefreshed") -> None:
        if message.generation != self._version_refresh_generation:
            return
        self.version_refreshing = False
        service = self._version_refresh
        if service is None or message.epoch != service.epoch:
            return
        self._browser.reload(self._adapter())
        if message.error is not None:
            # Nothing was published: rows stay `…`, never a stale mark.
            self._show_state_line(
                f"tool state check failed: {message.error} — leave and re-enter this view to retry"
            )
            return
        if message.warning is not None:
            self._show_state_line(
                f"{message.warning} — marks are current; the next start checks again"
            )
        elif self._state_line is not None and self.status.text == self._state_line:
            self.status.clear()
            self._state_line = None
        # Commit path only -- both early returns above already discarded a
        # superseded generation and a raced epoch, so this is the ONE point
        # where the shared ownership map is known to hold a current pass.
        self.post_message(OwnershipRefreshed())

    def _show_state_line(self, line: str) -> None:
        # Plain text through StatusLine.set, never markup (T-19-40).
        self.status.set(line, "warn")
        self._state_line = line

    def _state(self, tool: Tool) -> ToolState | None:
        service = self._version_refresh
        return service.state_of(tool.id) if service is not None else None

    def _health_of(self, tool: Tool) -> Health | None:
        state = self._state(tool)
        return state.health if state is not None else None

    def _is_present(self, tool: Tool) -> bool:
        """Known presence only: no state, or a pending one, reads as absent."""
        state = self._state(tool)
        return state is not None and state.present

    def _is_unavailable(self, tool: Tool) -> bool:
        """The state decides once one exists (brew may appear mid-session, R8);
        before the first pass, the launch-time map does."""
        state = self._state(tool)
        if state is not None:
            return state.health is Health.UNAVAILABLE
        return bool(self._unavailable.get(tool.id, False))

    def _presence_map(self) -> dict[str, bool]:
        """Presence over the full catalog, for the requires/recommends previews."""
        return {tool.id: self._is_present(tool) for tool in self._catalog}

    def _unavailable_map(self) -> dict[str, bool]:
        return {tool.id: self._is_unavailable(tool) for tool in self._catalog}

    def _ver_cell(self, tool: Tool) -> Text:
        """Version facts only (19-UI-SPEC "Ver cell"): empty unless the tool is
        present with a readable version. The text carries no color; the Health
        mark is the row's only color carrier."""
        state = self._state(tool)
        version = state.version if state is not None and state.present else None
        if version is None or version.installed is None:
            return Text("")
        text = version.installed
        if version.outdated:
            text = f"{version.installed} -> {version.latest}"
        # The stale suffix qualifies a claim about `latest`, so only a cell that
        # compared against one carries it.
        if version.stale and version.outdated is not None:
            return Text.assemble(text, (f" {_VER_STALE}", "dim"))
        return Text(text)

    # -- catalog data wiring for the browser adapter -----------------------
    def _skill_owner_cell(self, status: SkillHostStatus) -> Text:
        labels = [
            SKILL_HARNESS_LABELS.get(harness, harness)
            for harness, value in status.hosts.items()
            if value == "present"
        ]
        if not labels:
            return Text("")
        if len(labels) == 1 or len(", ".join(labels)) <= _OWNER_CELL_MAX:
            return Text(", ".join(labels))
        return Text(f"{labels[0]} +{len(labels) - 1}")

    def _owner_cell(self, tool: Tool) -> Text:
        """The owner label, or the hosts for a skill pack, from the state. Empty
        without a state (the Health `…` already says checking) and for an
        unknown owner. Not gated on presence: ownership comes from the live
        binary path, so an absent-reading tool can still carry a real owner."""
        state = self._state(tool)
        if state is None:
            return Text("")
        if tool.skill_lifecycle is not None:
            hosts = state.skill_hosts
            return self._skill_owner_cell(hosts) if hosts is not None else Text("")
        label = owner_label(state.ownership)
        if not label:
            return Text("")
        if state.ownership.off_policy:
            return Text.assemble(label, (" ≠ policy", "dim"))
        return Text(label)

    def _row_cells(self, tool: Tool) -> list[Text]:
        health = health_cell(self._state(tool))
        desc = tool.desc or tool.name
        ver = self._ver_cell(tool)
        if self._is_unavailable(tool):
            unavailable = self._unavailable.get(tool.id, False)
            if isinstance(unavailable, UnavailableReason):
                desc = f"{desc} (not available: {unavailable.short})"
            else:
                desc = f"{desc} (not available on this machine)"
            return [
                Text("", style="dim"),
                Text(tool.priority, style="dim"),
                Text(tool.id, style="dim"),
                Text(tool.category, style="dim"),
                Text(AUDIENCE_LABEL[tool.audience], style="dim"),
                Text(health.plain, style="dim"),
                Text(ver.plain, style="dim"),
                Text(self._owner_cell(tool).plain, style="dim"),
                Text(desc, style="dim"),
            ]
        return [
            mark(tool.id in self._browser.selected),
            Text(tool.priority, style=_PRIORITY_STYLE[tool.priority]),
            Text(tool.id, style="bold"),
            Text(tool.category),
            Text(AUDIENCE_LABEL[tool.audience], style=_AUDIENCE_STYLE[tool.audience]),
            health,
            ver,
            self._owner_cell(tool),
            Text(desc, style="dim"),
        ]

    def _groups(self, view: str) -> list[Section[Tool]]:
        if view == "table":
            return [("", "", sort_for_table(self.tools, self._health_of, self.table_sort))]
        return group_tools(self.tools, self._health_of, view, self._blurbs)

    def _detail_text(self, tool: Tool) -> str:
        detail = (
            f"[bold]{tool.id}[/] — {tool.desc or tool.name}  |  "
            f"[{_PRIORITY_STYLE[tool.priority]}]{tool.priority}"
            f" {PRIORITY_LABEL[tool.priority]}[/]  |  "
            f"for {AUDIENCE_LABEL[tool.audience]}"
        )
        # Dependency slot for the deps PRD: shown only when declared, so the
        # layout is unchanged for the common no-requires case.
        if tool.requires:
            detail += f"  |  requires {', '.join(tool.requires)}"
        # The detail bar describes the tool, which is a stable fact; the prompt
        # describes this moment's selection, which is not. Show the raw declared
        # list, not the filtered one — the two lists differing is correct.
        if tool.recommends:
            detail += f"  |  pairs well with {', '.join(tool.recommends)}"
        return f"{detail}\n{self._health_block(tool)}"

    def _health_block(self, tool: Tool) -> str:
        """`{glyph} {label} — {reasons} — to configure: {steps}` (19-UI-SPEC
        "Focused-row detail"). Reasons and steps carry machine text, so every
        one is escaped (T-19-45)."""
        state = self._state(tool)
        health = Health.CHECKING if state is None else state.health
        glyph, style = _HEALTH_CELL[health]
        block = f"[{style}]{glyph}[/] " if style else f"{glyph} "
        block += _HEALTH_DETAIL[health]
        reasons = list(state.reasons) if state is not None else []
        if state is None:
            # Before the first pass only the launch-time resolver knows this.
            unavailable = self._unavailable.get(tool.id, False)
            if isinstance(unavailable, UnavailableReason):
                reasons.append(unavailable.detail)
            elif unavailable:
                reasons.append("not available on this machine")
        elif state.present:
            # An environment fact read at render time, not part of the state.
            default_shell = is_default_shell(tool)
            if default_shell is True:
                reasons.append("this is your default shell")
            elif default_shell is False:
                reasons.append("installed, but not your default shell")
        if reasons:
            block += " — " + " · ".join(escape(reason) for reason in reasons)
        if state is not None and state.unconfigured:
            steps = "; ".join(escape(step.text) for step in state.unconfigured)
            block += f" — to configure: {steps}"
        return block

    def _sort(self, column_key: str) -> None:
        key = _SORT_BY_COLUMN.get(column_key)
        if key is None:
            return
        self.table_sort = key

    # -- public seams (delegated to the browser / status line) -------------
    @property
    def view(self) -> str:
        return self._browser.view

    @property
    def selected(self) -> set[str]:
        return self._browser.selected

    @property
    def detail_text(self) -> str:
        return self._browser.detail_text

    @property
    def status_text(self) -> str:
        return self.status.text

    @property
    def recommends_text(self) -> str:
        return self.recommends_line.text

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        # The catalog test drives header sort directly on the screen. Forward it
        # to the browser, which owns the table and the view-gated sort handling.
        self._browser.on_data_table_header_selected(event)

    # -- accept ------------------------------------------------------------
    def on_tool_browser_selection_changed(self, event: ToolBrowser.SelectionChanged) -> None:
        # Clear the "select at least one" warning the moment the user selects.
        event.stop()
        self.clear_transient()
        if event.item_id is None or not event.selected:
            return
        tool = self._by_id.get(event.item_id)
        if tool is None:
            return
        # Both run for the same mark and write to two different lines on purpose:
        # a tool can have both a missing prerequisite and an unstaged
        # recommendation and neither may hide the other.
        self._announce_requires(tool)
        self._offer_recommends(tool)

    def clear_transient(self) -> None:
        """End the selection moment: drop the requires notice, the recommends
        prompt and the pending ids behind it.

        Public because `UnifiedApp.show_view` — the single navigation path
        (`.claude/architecture.md` rule 2) — calls it on the screen being left.
        A `ScreenSuspend` handler cannot do this job: that event fires whenever
        the screen stops being the top of the stack, so opening and cancelling
        the nav palette would wipe state for a view the user never left.
        """
        self._pending_recommends = ()
        self.recommends_line.clear()
        self.status.clear()

    def _announce_requires(self, tool: Tool) -> None:
        missing = missing_requires(
            tool, self._catalog, staged=self._staged, installed=self._presence_map()
        )
        if missing:
            self.status.set(
                f"{tool.id} also needs {', '.join(missing)} - added automatically at "
                "install time; any not available on this platform are reported when "
                "the installer runs.",
                "ok",
            )

    def _offer_recommends(self, tool: Tool) -> None:
        pending = unstaged_recommends(
            tool,
            self._catalog,
            staged=self._staged,
            installed=self._presence_map(),
            unavailable=self._unavailable_map(),
        )
        if not pending:
            return
        self._pending_recommends = pending
        self.recommends_line.set(
            f"{tool.id} pairs well with {', '.join(pending)} - press r to add them "
            "to your selection, d to dismiss.",
            "ok",
        )

    def action_accept_recommends(self) -> None:
        # Deliberately the same mutation a space-mark performs — the shared
        # staged set, nothing else — so an accepted recommendation is
        # indistinguishable from the user marking those rows by hand (D-05).
        # Never calls resolve_dependencies, never touches an executor, and
        # never installs. The confirmation overwrites any requires notice on
        # the status line on purpose, because the accept is the newer fact.
        #
        # The pending ids were computed when the prompt was raised; the shared
        # staged set may have moved since, so they are re-filtered here and only
        # the real delta is added and named. Reporting the captured tuple would
        # claim to have added ids that were already in the batch.
        added = tuple(
            rec
            for rec in self._pending_recommends
            # Pending ids come from unstaged_recommends, which keeps only catalog ids.
            if rec not in self._staged and not self._is_unavailable(self._by_id[rec])
        )
        self._pending_recommends = ()
        self.recommends_line.clear()
        if not added:
            return
        self._staged.update(added)
        self._browser.refresh_marks()
        self.status.set(f"added {', '.join(added)} to your selection.", "ok")

    def action_dismiss_recommends(self) -> None:
        # Narrower than clear_transient on purpose: d dismisses the prompt, and
        # a requires notice for the same mark is a separate fact that survives it.
        self._pending_recommends = ()
        self.recommends_line.clear()

    def action_update_tool(self) -> None:
        """Press `u` on the highlighted row. Immediate, no confirmation (D-01)."""
        if self._updates is None or self._version_refresh is None:
            return
        tool_id = self._browser.highlighted_id()
        if tool_id is None:
            return
        tool = self._by_id.get(tool_id)
        if tool is None:
            return
        state = self._state(tool)
        if state is None or state.health is Health.CHECKING:
            # CR-02 (15.4-REVIEW.md): never a silent return. A pending state is
            # a transient the user recovers from by waiting, so it must say so.
            self.status.set(
                f"cannot update {tool_id}: its state is still being checked — "
                "try again in a moment",
                "warn",
            )
            return
        if state.health is Health.BROKEN:
            # tool_health puts the winning state's facts first.
            self.status.set(f"{tool_id} is broken: {state.reasons[0]}", "warn")
            return
        ownership, status = state.ownership, state.version
        if status is not None and status.outdated is False:
            lead = "current as of the last check" if status.stale else "already current"
            line = f"{tool_id} is {lead}"
            if ownership.off_policy:
                declared = declared_manager_label(tool, self._version_refresh.platform)
                real = owner_label(ownership)
                if declared is not None and real is not None:
                    line += (
                        f" — {real} owns this copy; the catalog installs it via {declared}, "
                        "and moving it there is not available yet"
                    )
            self.status.set(line, "ok")
            return
        if ownership.owner == "unknown" or ownership.confidence not in MUTATION_GRADE:
            reason = ownership.unknown_reason or "no manager claimed this tool"
            line = f"cannot update {tool_id}: {reason}"
            note = active_path_note(ownership)
            if note:
                line += f" — {note}"
            self.status.set(line, "warn")
            return
        if not self._updates.begin(tool_id):
            in_flight = self._updates.in_flight or "another tool"
            self.status.set(f"update already in flight for {in_flight}", "warn")
            return
        self.status.set(f"updating {tool_id}…", "ok")
        # The state's ownership gates the keypress; UpdateService.run still
        # re-resolves it before mutating (T-19-46).
        self._update_tool_worker(UpdateTarget(tool=tool, ownership=ownership))

    @work(thread=True, exclusive=True, group="tool-update", exit_on_error=False)
    def _update_tool_worker(self, target: UpdateTarget) -> None:
        outcome: UpdateOutcome | None = None
        error: str | None = None
        epoch = 0
        try:
            service = self._updates
            refresh = self._version_refresh
            if service is None or refresh is None:
                return
            result, error = run_live(lambda: service.run(target))
            outcome = result
            # No single-tool pass here: it would publish the updated row ahead
            # of the others. on_tool_updated starts the full pass instead.
            epoch = refresh.epoch
        finally:
            if self._updates is not None:
                self._updates.end()
            self.post_message(ToolUpdated(target.tool.id, outcome, error, epoch))

    def on_tool_updated(self, message: ToolUpdated) -> None:
        outcome = message.outcome
        if outcome is not None and outcome.status == "updated":
            # CR-02 (15.4-REVIEW.md): `UpdateService.run` called `invalidate`,
            # which bumped the shared epoch, so every tool's state is stale
            # and `state_of` answers `None` until a pass lands. Kicking the
            # full pass here replaces the invalidate the update performed; the
            # rows read `…` in the meantime.
            self._start_version_refresh()
        if message.error is not None:
            self.status.set(f"update failed: {message.error}", "error")
            return
        if outcome is None:
            self.status.set(f"update of {message.tool_id} did not complete", "error")
            return
        if outcome.status == "updated":
            line = f"updated {message.tool_id}"
            if outcome.replayed_globals:
                line += f" — replayed {', '.join(outcome.replayed_globals)}"
            if outcome.cleanup_warnings:
                line += f" — {'; '.join(outcome.cleanup_warnings)}"
            if outcome.postinstall_warning:
                line += f" — {outcome.postinstall_warning}"
            if outcome.detail:
                line += f" — {outcome.detail}"
            self.status.set(line, "ok")
            return
        if outcome.status == "failed":
            # opencode H3: a failed update is an error, the same severity a
            # raised worker error gets -- it must read as red, because it
            # folds into the session exit code.
            self.status.set(outcome.detail or f"update of {message.tool_id} failed", "error")
            return
        self.status.set(outcome.detail or f"update {outcome.status}", "warn")

    def on_screen_resume(self) -> None:
        # The staged set is shared by all three tier screens (plan 02-01), and
        # action_accept_recommends is the only writer that can add an id on
        # behalf of a screen that is not active; that screen's DataTable was
        # already built and stamped, so without a re-stamp on resume it would
        # show an unmarked checkbox for a tool that is genuinely in the batch.
        # refresh_marks iterates only its own rows and skips ids it does not
        # own, so this is inert for every other case.
        self._browser.refresh_marks()

    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        event.stop()
        ids = [
            tool.id
            for tool in select_tools(self._catalog, list(self._staged))
            if not self._is_unavailable(tool)
        ]
        if not ids:
            self.status.set("Select at least one tool, or press q to quit.", "warn")
            return
        self.status.clear()
        self.post_message(self.Decided(ids))
