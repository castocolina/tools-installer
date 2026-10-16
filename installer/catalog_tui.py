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
    also_installed_note,
    declared_manager_label,
    owner_detail,
    owner_label,
)
from installer.resolve import UnavailableReason
from installer.selection import select_tools, unstaged_recommends
from installer.skill_lifecycle import SKILL_HARNESS_LABELS
from installer.status import is_default_shell
from installer.tool_browser import BrowserAdapter, Section, ToolBrowser
from installer.ui_common import AppScreen, StatusLine, mark, run_live
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_status import (
    Health,
    SkillHostStatus,
    ToolState,
    VersionRefreshService,
    VersionStatus,
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
        groups = [
            (
                f"{_HEALTH_CELL[health][0]} {_HEALTH_WORD[health]}",
                _HEALTH_DETAIL[health],
                [t for t in ordered if _health(health_of, t) is health],
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
        status: VersionStatus | None,
        error: str | None,
        epoch: int,
    ) -> None:
        super().__init__()
        self.tool_id = tool_id
        self.outcome = outcome
        self.status = status
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
        statuses: dict[str, VersionStatus],
        generation: int,
        epoch: int,
        *,
        error: str | None = None,
        warning: str | None = None,
    ) -> None:
        super().__init__()
        self.statuses = statuses
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

# Every dim Ver cell state gets its own text (D-02) -- no two of these mean
# the same thing, and _ver_cell's six dim branches map onto exactly these
# four (the two no-readable-version branches share _VER_NO_VERSION, and the
# two nothing-to-compare branches share _VER_NO_COMPARISON; no other pair
# collides). D-03/D-04 lock a per-state legend entry for each of these four
# labels (plus the `~` suffix) -- _LEGEND (below) lists all four verbatim.
_VER_CHECKING = "checking…"
_VER_NO_VERSION = "no version"
# Named after status.source, not a conclusion about the tool: the fallthrough
# that stamps source="unknown" (installer/version_status.py:325-337) is
# reached by both a native dnf/apt/pacman/rpm-ostree package AND a tool whose
# manager inventory could not be read this pass -- VersionStatus carries
# neither the owner nor unknown_reason, so the cell cannot tell them apart.
# Follow-up: Phase 15.4's ownership column should plumb the resolved owner
# into VersionStatus so this can split into two accurate labels.
_VER_SOURCE_UNKNOWN = "(source unknown)"
_VER_NO_COMPARISON = "(no comparison)"
_VER_STALE = "~"
_BROKEN_DETAIL = "shim present, package missing — select it and press enter to reinstall and repair"
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

# D-03/D-04: the Ver: line below is appended to the one existing legend string
# (never a second widget/region -- BrowserAdapter.legend / the docked
# #browser-legend Static already renders on all three tier views, once per
# CatalogScreen). The two colored entries use the literal style tokens
# `green`/`yellow` those branches use -- never the word "orange" CONTEXT.md's
# prose uses for the update-available color, which is not a real Rich markup
# name and would either no-op or visually mismatch the cell it explains.
#
# UAT correction (2026-09-16, live user report during Phase 15.1 closure): a
# "legend" reads as a per-color/symbol KEY, not continuous prose -- soft-wrap
# at an arbitrary column loses group boundaries. Fixed with explicit \n at
# each group boundary so each of the three available rows is one
# self-contained key line -- but every rendered dim label still gets its own
# spelled-out entry (D-03/D-04 lock this; a single collapsed "self-explains"
# note was tried and rejected -- it violated the locked per-state requirement,
# see 15.1-VERIFICATION.md's second pass). The three lines are grouped by
# BUDGET, not strict semantics, because the Ver group's own content (all four
# dim labels + the two colored states + the stale marker) cannot fit in a
# single 78-column row alongside anything else: line 1 is Priorities plus the
# D-18 broken mark, placed there for budget, the same grouping-by-budget rule
# this comment already states for lines 2 and 3 (lines 2 and 3 have no room);
# line 2 is Audience/State plus the two colored Ver states (their combined
# length fits the leftover budget); line 3 is the four dim labels plus the
# stale marker. Each line is plain-text-measured (Rich markup stripped) to
# stay at or under 78 columns -- the confirmed usable width of
# #browser-legend's `dock: bottom` / `max-height: 3` box at this project's
# tested minimum terminal size (80x20; `padding: 0 1` costs 2 columns).
# Exceeding 78 on any line causes Rich to soft-wrap that line onto a 4th row,
# which `max-height: 3` then silently clips -- not reflows. See the widened
# test_legend_keeps_the_catalog_table_usable_at_the_minimum_size /
# test_legend_widget_paints_every_marker_at_full_width for the regression
# test that would now fail loudly if any line grows past this budget again.
#
# The stale marker keeps its `dim` style, matching how _ver_cell renders it.
#
# 15.4-03/D-02: the Owner column (added 15.4-01, at `_COLUMNS` index 7) gets
# NO new legend line, deliberately. The legend's job is to decode colors and
# symbols whose meaning is not already on screen -- the four dim Ver labels,
# the priority colors, the installed/missing marks -- but the Owner cell
# renders the manager's literal name (`Homebrew`, `dnf`, `GitHub release`,
# ...) with nothing to decode. There is also no budget left to spend: this
# block's own three-line/78-column limit above is already fully allocated to
# the keys that DO carry meaning that isn't visible in the cell itself, and a
# fourth line would either overflow `max-height: 3` (silently clipping a line
# that carries a real key) or force a cramped rewrite of the three that do.
_LEGEND = (
    "[bold red]P0[/] essential · [bold yellow]P1[/] recommended · [blue]P2[/] nice-to-have"
    " · [dim]P3[/] niche · [red]! broken[/]\n"
    "[bold cyan]AI[/] / [magenta]human[/] / both"
    " · [green]✓ installed[/] · [yellow]○ missing[/]"
    " · Ver: [green]up to date[/] · [yellow]update avail[/]\n"
    f"[dim]{_VER_CHECKING}[/] · [dim]{_VER_NO_VERSION}[/]"
    f" · [dim]{_VER_SOURCE_UNKNOWN}[/] · [dim]{_VER_NO_COMPARISON}[/]"
    f" · [dim]{_VER_STALE}[/] cached latest"
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
    in-flight line, then the re-probed version or the child's stderr from
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
        installed: Mapping[str, bool],
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
        self._installed = dict(installed)
        self._blurbs = dict(blurbs)
        self._catalog = list(catalog)
        self._staged = staged
        self._unavailable = dict(unavailable) if unavailable else {}
        self._by_id = {tool.id: tool for tool in self._catalog}
        # Default None matches UnifiedApp's optional-closure convention: tests
        # that construct a CatalogScreen without a service stay silent.
        self._version_refresh = version_refresh
        self._updates = updates
        self._version_statuses: dict[str, VersionStatus] = {}
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
        )

    def compose_body(self) -> ComposeResult:
        yield self._browser
        yield self.recommends_line

    def on_mount(self) -> None:
        self._start_version_refresh()

    def enter_view(self) -> None:
        if self.is_mounted:
            self._start_version_refresh()

    def set_installed(self, installed: Mapping[str, bool]) -> None:
        """Replace the installed map with a fresh reading and repaint.

        Called by `UnifiedApp._install_closed` with a map re-derived from the
        run's own live presence predicate (`installer.status.is_installed`),
        never a promotion from `VersionStatus.installed` -- presence and
        version-readability are different questions with different answers
        (`installer/status.py:18-42` accepts a PATH command OR a `detect_path`
        marker OR an app/cask bundle; the version probe answers only the
        first). No decision reads this map any more: every mark, group and
        presence check reads the tool state (plan 19-20 deletes the map). No-ops
        when nothing changed, so the common "nothing this run touched" close
        costs no rebuild.
        """
        new = dict(installed)
        if new == self._installed:
            return
        self._installed = new
        if self.is_mounted:
            self._browser.reload(self._adapter())

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
        statuses: dict[str, VersionStatus] = {}
        epoch = 0
        error: str | None = None
        warning: str | None = None
        service = self._version_refresh
        try:
            if service is not None:
                epoch = service.epoch
                # The whole catalog, never the tier: every tier asks for the same
                # set, so the service joins an in-flight pass instead of repeating it.
                result, error = run_live(lambda: service.refresh(self._catalog))
                if result is not None:
                    statuses = result
                    warning = service.warning
        finally:
            self.post_message(
                VersionStatusRefreshed(statuses, generation, epoch, error=error, warning=warning)
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
        self._version_statuses = dict(message.statuses)
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

    def _skill_status(self, tool: Tool) -> SkillHostStatus | None:
        if tool.skill_lifecycle is None:
            return None
        service = self._version_refresh
        if service is None:
            return None
        return service.skill_status_of(tool.id)

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
        if not self._is_present(tool):
            return Text("")
        status = self._version_statuses.get(tool.id)
        if status is None:
            # The screen attribute is the only thing that separates a probe
            # that has not landed yet from one that landed with nothing (a
            # crashed worker) -- without it this would claim to be checking
            # forever after a crash.
            return Text(_VER_CHECKING if self.version_refreshing else _VER_NO_VERSION, style="dim")
        if status.installed is None:
            return Text(_VER_NO_VERSION, style="dim")
        if status.latest is None:
            # A probed version with no comparison source (e.g. a dnf/apt/pacman
            # package -- ownership.py deliberately doesn't track those managers,
            # so there is no "latest" to diff against) is still real information;
            # replacing it with a bare marker would throw away a version we
            # already have. status.source == "unknown" is resolve_status's
            # final fallthrough (installer/version_status.py:325-337), reached
            # by both a native package and a manager inventory that could not
            # be read this pass -- see _VER_SOURCE_UNKNOWN's own comment.
            marker = _VER_SOURCE_UNKNOWN if status.source == "unknown" else _VER_NO_COMPARISON
            return Text.assemble((status.installed, "dim"), (f" {marker}", "dim"))
        if status.outdated is True:
            base = f"{status.installed} -> {status.latest}"
            color = "yellow"
        elif status.outdated is False:
            base = status.installed
            color = "green"
        else:
            # Both versions exist but one of them would not parse -- the
            # version is real and must survive, same reasoning as the
            # latest-is-None branch above.
            return Text.assemble((status.installed, "dim"), (f" {_VER_NO_COMPARISON}", "dim"))
        # The trailing stale suffix is scoped to these two colored branches
        # only, never appended on a dim cell (D-04 as interpreted 2026-09-16
        # -- see 15.1-CONTEXT.md's D-04 Interpretation note). It qualifies a
        # `latest` this cell rendered a claim about; a dim cell renders no
        # such claim, and resolve_status hardcodes stale=True on every path
        # that yields latest=None (installer/version_status.py:269, :290,
        # :332), so an unconditional suffix would sit on substantially every
        # dim cell and distinguish nothing. Pinned by
        # tests/test_catalog_tui.py's stale-scope test (ver_cell_dim) and the
        # pre-existing anti-regression assertion that a stale=True status
        # with installed=None renders no suffix.
        if status.stale:
            return Text.assemble((base, color), (f" {_VER_STALE}", "dim"))
        return Text(base, style=color)

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
        if tool.skill_lifecycle is not None:
            status = self._skill_status(tool)
            return self._skill_owner_cell(status) if status is not None else Text("")
        # D-02: blank means exactly "genuinely don't know" -- no service
        # wired, no ownership record produced for this tool yet, or the
        # record itself resolved to `unknown` (owner_label returns `None`
        # for that case). Deliberately NOT gated on `self._installed`, unlike
        # `_ver_cell`'s early return on a not-installed tool above: ownership
        # is resolved from the live binary path (`ownership.py`'s
        # `active_path` evidence), not from the presence predicate this
        # screen's `_installed` map reads, so a tool the predicate happens to
        # read as absent can still carry a real, useful ownership record. Do
        # not "fix" this asymmetry by adding a not-installed early return
        # here -- it would silently throw away real evidence.
        service = self._version_refresh
        ownership = service.ownership_of(tool.id) if service is not None else None
        if ownership is None:
            # CR-02 (15.4-REVIEW.md): while a pass is in flight, `None` does
            # NOT mean "genuinely don't know" -- every record in the shared
            # map is epoch-stale by construction until that pass commits, so
            # a blank here would say the wrong thing about the whole catalog
            # at once. Reuses `_ver_cell`'s own `checking…` label (already in
            # `_LEGEND`, so this needs no new legend budget) rather than
            # inventing a second word for the same state.
            return Text(_VER_CHECKING, style="dim") if self.version_refreshing else Text("")
        label = owner_label(ownership)
        if not label:
            return Text("")
        if ownership.off_policy:
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
        unavailable = self._unavailable.get(tool.id, False)
        if isinstance(unavailable, UnavailableReason):
            detail += f"  |  {unavailable.detail}"
        elif unavailable:
            detail += "  |  (not available on this machine)"
        if self._is_present(tool):
            default_shell = is_default_shell(tool)
            if default_shell is True:
                detail += "  |  this is your default shell"
            elif default_shell is False:
                detail += "  |  installed, but not your default shell"
        detail += self._version_detail(tool)
        detail += self._skill_detail(tool)
        return detail

    def _skill_detail(self, tool: Tool) -> str:
        status = self._skill_status(tool)
        if status is None:
            return ""
        present = [
            SKILL_HARNESS_LABELS.get(harness, harness)
            for harness, value in status.hosts.items()
            if value == "present"
        ]
        unknown = [
            SKILL_HARNESS_LABELS.get(harness, harness)
            for harness, value in status.hosts.items()
            if value == "unknown"
        ]
        segments: list[str] = []
        if present:
            segments.append(f"installed in: {', '.join(present)}")
        if unknown:
            segments.append(f"not probed: {', '.join(unknown)}")
        if not segments:
            return ""
        return "  |  " + "  |  ".join(segments)

    def _version_detail(self, tool: Tool) -> str:
        status = self._version_statuses.get(tool.id)
        service = self._version_refresh
        ownership = service.ownership_of(tool.id) if service is not None else None
        segments: list[str] = []
        if ownership is not None and ownership.broken:
            segments.append(_BROKEN_DETAIL)
        if ownership is not None and ownership.owner != "unknown":
            # D-05 (Round-1 review 15.4-03 HIGH/MEDIUM): the per-owner
            # explanation requirement here is now satisfied by an
            # exhaustiveness-tested table in ownership.py
            # (OWNER_DETAIL_LABELS / owner_detail) rather than by a local
            # dict a reader could quietly under-fill -- see ownership.py's
            # own module comment for the register split: OWNER_LABELS is the
            # terse COLUMN register, OWNER_DETAIL_LABELS is this PROSE
            # register, declared adjacent to it so neither can drift
            # unnoticed.
            label = owner_detail(ownership)
            if label:
                segments.append(label)
            if ownership.off_policy and service is not None:
                declared = declared_manager_label(tool, service.platform)
                real = owner_label(ownership)
                if declared is not None and real is not None:
                    segments.append(
                        f"{real} owns this copy; the catalog's policy installs "
                        f"{tool.id} via {declared}"
                    )
            if ownership.shadowed:
                note = also_installed_note(ownership)
                if note is not None and ownership.active_path is not None:
                    segments.append(escape(f"{note} — live copy at {ownership.active_path}"))
                elif note is not None:
                    segments.append(note)
                elif ownership.active_path is not None:
                    segments.append(escape(f"shadowed — live copy at {ownership.active_path}"))
                else:
                    segments.append("shadowed")
        if ownership is not None and ownership.owner == "unknown" and ownership.unknown_reason:
            segments.append(escape(ownership.unknown_reason))
        if ownership is not None:
            path_note = active_path_note(ownership)
            if path_note:
                segments.append(escape(path_note))
        if (
            status is not None
            and status.source == "installer"
            and status.outdated is None
            and (ownership is None or ownership.owner == "installer")
        ):
            segments.append(
                "latest version cannot be determined for this install method — "
                "pressing u re-runs the same install path this tool was originally installed with"
            )
        if status is not None and status.pinned_spec:
            segments.append(
                f"this project pins {status.pinned_spec} and constrains the version deliberately"
            )
        if status is not None and status.stale and status.latest is not None:
            segments.append(
                "the shown latest version came from a cache entry at or past STALE_AFTER "
                "and a re-check is pending"
            )
        if not segments:
            return ""
        return "  |  " + "  |  ".join(segments)

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
        status = self._version_statuses.get(tool_id)
        ownership = self._version_refresh.ownership_of(tool_id)
        if ownership is not None and ownership.broken:
            self.status.set(f"{tool_id}: {_BROKEN_DETAIL}", "warn")
            return
        if status is not None and status.outdated is False:
            lead = "current as of the last check" if status.stale else "already current"
            line = f"{tool_id} is {lead}"
            if ownership is not None and ownership.off_policy:
                declared = declared_manager_label(tool, self._version_refresh.platform)
                real = owner_label(ownership)
                if declared is not None and real is not None:
                    line += (
                        f" — {real} owns this copy; the catalog installs it via {declared}, "
                        "and moving it there is not available yet"
                    )
            self.status.set(line, "ok")
            return
        if ownership is None:
            # CR-02 (15.4-REVIEW.md): never a silent return. A `None` here is
            # overwhelmingly "a mutation bumped the epoch and the replacing
            # pass has not committed yet" -- a transient the user recovers
            # from by waiting, not a permanent refusal -- so it must say so.
            # The bare `return` made `u` a no-op with no feedback at all for
            # every tool in the catalog after one in-catalog update.
            self.status.set(
                f"cannot update {tool_id}: ownership data is being refreshed — "
                "try again in a moment",
                "warn",
            )
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
        self._update_tool_worker(tool_id)

    @work(thread=True, exclusive=True, group="tool-update", exit_on_error=False)
    def _update_tool_worker(self, tool_id: str) -> None:
        outcome: UpdateOutcome | None = None
        status: VersionStatus | None = None
        error: str | None = None
        epoch = 0
        try:
            tool = self._by_id.get(tool_id)
            service = self._updates
            refresh = self._version_refresh
            if tool is None or service is None or refresh is None:
                return
            cached = refresh.ownership_of(tool_id)
            if cached is None:
                return
            target = UpdateTarget(tool=tool, ownership=cached)
            result, error = run_live(lambda: service.run(target))
            outcome = result
            # No single-tool pass here: it would publish the updated row ahead
            # of the others. on_tool_updated starts the full pass instead.
            epoch = refresh.epoch
        finally:
            if self._updates is not None:
                self._updates.end()
            self.post_message(ToolUpdated(tool_id, outcome, status, error, epoch))

    def on_tool_updated(self, message: ToolUpdated) -> None:
        if message.status is not None:
            self._version_statuses[message.tool_id] = message.status
            self._browser.reload(self._adapter())
        outcome = message.outcome
        if outcome is not None and outcome.status == "updated":
            # CR-02 (15.4-REVIEW.md): `UpdateService.run` called `invalidate`,
            # which bumped the shared epoch, and `_update_tool_worker` then
            # re-refreshed ONLY the updated tool. Every OTHER tool's record is
            # therefore epoch-stale, so `ownership_of` answers `None` for the
            # whole rest of the catalog: the Owner column blanks, the detail
            # bar drops its ownership sentence, and `u` refuses on every other
            # row until the user navigates away and back. Kicking the full
            # pass here is what replaces the invalidate the update performed,
            # and it repaints through `_start_version_refresh`'s own reload so
            # the transient window renders as `checking…` rather than blank.
            self._start_version_refresh()
        if message.error is not None:
            self.status.set(f"update failed: {message.error}", "error")
            return
        if outcome is None:
            self.status.set(f"update of {message.tool_id} did not complete", "error")
            return
        if outcome.status == "updated":
            version = ""
            if message.status is not None and message.status.installed:
                version = f" now {message.status.installed}"
            line = f"updated {message.tool_id}{version}"
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
