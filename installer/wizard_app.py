"""Unified Textual shell hosting the wizard views behind one app.

The app owns navigation and the screen stack. Catalog, doctor, fix, uninstall,
and policies are all functional views. Execution stays behind the pure
`installer/` core invoked from `setup.py`, with one deliberate exception: the
fix, uninstall, and policies views apply their changes live through injected
closures. The app's run value stays the catalog decision (`list[str] | None`).

The catalog is the base screen (`get_default_screen`); it cannot be switched
out. Navigation is therefore a stack with the catalog at the bottom: the stack
is always `[catalog]` or `[catalog, <one other view>]`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.coordinate import Coordinate
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from installer.app import UninstallDecision
from installer.catalog_tui import CatalogScreen
from installer.doctor import DoctorReport
from installer.guidance import Guidance, doctor_guidance, guard_guidance
from installer.model import Tool
from installer.policy import Policy, PolicyResult
from installer.render import guidance_text
from installer.tool_browser import BrowserAdapter, Section, ToolBrowser
from installer.ui_common import AppScreen, mark, multiline_summary
from installer.uninstall import ToolRow

# Navigation order shared by every route, so the palette and the direct 1..N key
# bindings expose exactly the same views in the same order.
VIEW_ORDER: tuple[str, ...] = ("catalog", "doctor", "fix", "uninstall", "policies")
_PALETTE_LABEL = {
    "catalog": "Catalog — pick tools to install",
    "doctor": "Doctor — audit your PATH",
    "fix": "Fix — wire PATH into your shells",
    "uninstall": "Uninstall — remove installed tools",
    "policies": "Policies — pip/npm ban and env tweaks",
}


@dataclass(frozen=True)
class UninstallInputs:
    """Everything the UninstallScreen needs: every classified tool (catalog
    parity, not just the removable ones), the active ban names, whether a managed
    PATH block exists, and the live removal closure bound by the composition root."""

    rows: list[ToolRow]
    ban_names: list[str]
    has_path_block: bool
    remove: Callable[[UninstallDecision], None]


@dataclass(frozen=True)
class PolicyInputs:
    """The policies the PoliciesScreen renders, each carrying its own bound
    apply/remove closures. The composition root builds these from the pure core."""

    policies: list[Policy]


class DoctorScreen(AppScreen):
    """Read-only PATH audit + guidance, color-coded by severity."""

    DEFAULT_CSS = """
    DoctorScreen #doctor-body { padding: 1 4; }
    """

    def __init__(
        self,
        report: DoctorReport,
        guard_status: dict[str, bool],
        guard_warning: str | None,
    ) -> None:
        super().__init__(view="doctor")
        self._report = report
        self._guard_status = guard_status
        self._guard_warning = guard_warning
        self.guidance: list[Guidance] = []  # public test seam

    def compose_body(self) -> ComposeResult:
        yield Static(id="doctor-body")

    def on_mount(self) -> None:
        self.guidance = doctor_guidance(self._report) + guard_guidance(
            self._guard_status, self._guard_warning
        )
        self.query_one("#doctor-body", Static).update(guidance_text(self.guidance))


class FixScreen(AppScreen):
    """Preview the PATH wiring + reload guidance; Apply runs it live, in place."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "apply", "apply", show=True),
    ]
    DEFAULT_CSS = """
    FixScreen #fix-body { padding: 1 4; }
    """

    def __init__(self, preview: str, fix: Callable[[], None]) -> None:
        super().__init__(view="fix")
        self._preview = preview
        self._fix = fix
        self.applied = False  # public test seam
        self.error: str | None = None  # public test seam; set when an apply fails

    def compose_body(self) -> ComposeResult:
        yield Static(id="fix-body")

    def on_mount(self) -> None:
        self._refresh_body()

    # NB: not named `_render` — that collides with Textual's internal
    # Widget._render(), which the compositor calls to produce the visual.
    def _refresh_body(self) -> None:
        body = self.query_one("#fix-body", Static)
        text = Text()
        if self.applied:
            text.append("PATH wired.", style="green")
            text.append("\n  → Restart your shell or run `source ~/.myshellrc` to apply.")
        elif self.error is not None:
            text.append("Fix failed.", style="red")
            text.append(f"\n  {self.error}")
            text.append("\n  → Check the target is writable, then press 'a' to retry.")
        else:
            text.append("Press 'a' to wire the managed PATH into your shells.", style="yellow")
            text.append(f"\n\n{self._preview}")
            text.append("\n\nAfter applying, restart your shell or `source ~/.myshellrc`.")
        body.update(text)

    def action_apply(self) -> None:
        if self.applied:
            return
        try:
            self._fix()
        except OSError as exc:
            # Surface the failure in place (PRD: a failed core action is shown,
            # never a silent crash); `applied` stays False so 'a' retries.
            self.error = str(exc)
            self._refresh_body()
            return
        self.error = None
        self.applied = True
        self._refresh_body()


@dataclass(frozen=True)
class _UninstallEntry:
    """A browsable uninstall row: either a classified tool or an environment
    pseudo-row (the pip/npm ban or the managed PATH block).

    `key` is the stable id (a tool id, or "#ban"/"#path-block"). `cells` are the
    pre-rendered columns. `selectable` gates toggling (removable tools and the env
    rows are selectable; managed/absent/unavailable tools are not). `detail` is
    the detail-bar line. `paths` are the tool's removable artifacts (empty for env
    rows). `is_ban`/`is_path_block` flag the env rows so a selection maps back to
    the UninstallDecision levers."""

    key: str
    cells: list[Text]
    selectable: bool
    detail: str
    paths: tuple[Path, ...]
    is_ban: bool
    is_path_block: bool


# Section titles per state, in display order. The "environment" section holds the
# ban/PATH pseudo-rows.
_STATE_TITLES: tuple[tuple[str, str], ...] = (
    ("removable", "removable here"),
    ("managed", "managed elsewhere"),
    ("absent", "not installed"),
    ("unavailable", "not available"),
)
_BAN_KEY = "#ban"
_BLOCK_KEY = "#path-block"


class UninstallScreen(AppScreen):
    """Full catalog-parity uninstall browser. Every tool is listed with its
    removability state; only removable tools (and the env rows) toggle. Enter
    removes exactly the selected artifacts + env levers, applied live."""

    def __init__(self, inputs: UninstallInputs) -> None:
        super().__init__(view="uninstall", accent="red")
        self._rows = inputs.rows
        self._ban_names = inputs.ban_names
        self._has_path_block = inputs.has_path_block
        self._remove = inputs.remove
        self.applied = False
        self.error: str | None = None
        self._entries = self._build_entries()
        self._by_key = {entry.key: entry for entry in self._entries}
        self._browser: ToolBrowser[_UninstallEntry] = ToolBrowser(self._adapter())

    # -- entry construction ------------------------------------------------
    def _build_entries(self) -> list[_UninstallEntry]:
        entries = [self._tool_entry(row) for row in self._rows]
        if self._ban_names:
            entries.append(self._ban_entry())
        if self._has_path_block:
            entries.append(self._block_entry())
        return entries

    def _tool_entry(self, row: ToolRow) -> _UninstallEntry:
        selectable = row.state == "removable"
        style = "" if selectable else "dim"
        installed_via = {
            "removable": "userspace",
            "managed": "package manager",
            "absent": "—",
            "unavailable": "—",
        }[row.state]
        removes = (
            f"{len(row.paths)} artifact(s)"
            if selectable
            else {
                "managed": "nothing (managed elsewhere)",
                "absent": "nothing (not installed)",
                "unavailable": "nothing (unavailable)",
            }[row.state]
        )
        cells = [
            mark(False) if selectable else Text(""),
            Text(row.tool.id, style="bold" if selectable else "dim"),
            Text(row.tool.category, style=style),
            Text(installed_via, style=style),
            Text(removes, style=style),
        ]
        return _UninstallEntry(
            key=row.tool.id,
            cells=cells,
            selectable=selectable,
            detail=row.hint,
            paths=tuple(row.paths),
            is_ban=False,
            is_path_block=False,
        )

    def _ban_entry(self) -> _UninstallEntry:
        return _UninstallEntry(
            key=_BAN_KEY,
            cells=[
                mark(False),
                Text("pip/npm ban", style="bold yellow"),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text(f"shims + aliases ({', '.join(self._ban_names)})", style="dim"),
            ],
            selectable=True,
            detail=f"pip/npm ban — shims + interactive aliases ({', '.join(self._ban_names)})",
            paths=(),
            is_ban=True,
            is_path_block=False,
        )

    def _block_entry(self) -> _UninstallEntry:
        return _UninstallEntry(
            key=_BLOCK_KEY,
            cells=[
                mark(False),
                Text("PATH wiring", style="bold yellow"),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text("managed block in ~/.myshellrc", style="dim"),
            ],
            selectable=True,
            detail="PATH wiring — the managed block in ~/.myshellrc",
            paths=(),
            is_ban=False,
            is_path_block=True,
        )

    # -- browser adapter ---------------------------------------------------
    def _adapter(self) -> BrowserAdapter[_UninstallEntry]:
        return BrowserAdapter(
            items=self._entries,
            columns=(
                ("Sel", "sel"),
                ("Tool", "tool"),
                ("Cat", "cat"),
                ("Installed via", "via"),
                ("What gets removed", "removes"),
            ),
            item_id=lambda entry: entry.key,
            row_cells=lambda entry: entry.cells,
            detail_text=lambda entry: entry.detail,
            groups=self._groups,
            views=(("all", "All"),),
            detail_is_markup=False,
            selectable=lambda entry: entry.selectable,
        )

    def _groups(self, _view: str) -> list[Section[_UninstallEntry]]:
        by_state: dict[str, list[_UninstallEntry]] = {}
        for row, entry in zip(self._rows, self._entries, strict=False):
            by_state.setdefault(row.state, []).append(entry)
        sections: list[Section[_UninstallEntry]] = [
            (title, title, by_state[state]) for state, title in _STATE_TITLES if by_state.get(state)
        ]
        env = [entry for entry in self._entries if entry.is_ban or entry.is_path_block]
        if env:
            sections.append(("environment", "shell config the installer manages", env))
        return sections

    def compose_body(self) -> ComposeResult:
        yield self._browser

    def on_mount(self) -> None:
        if not self._entries:
            self.status.set("Nothing to uninstall.", "ok")

    # -- public seams the tests assert on ----------------------------------
    @property
    def selected(self) -> set[str]:
        """Selected *tool* ids (the env pseudo-rows are reported separately)."""
        return {key for key in self._browser.selected if key not in (_BAN_KEY, _BLOCK_KEY)}

    @property
    def remove_ban(self) -> bool:
        return _BAN_KEY in self._browser.selected

    @property
    def remove_path_block(self) -> bool:
        return _BLOCK_KEY in self._browser.selected

    @property
    def detail_text(self) -> str:
        return self._browser.detail_text

    # -- messages from the browser -----------------------------------------
    def on_tool_browser_selection_changed(self, event: ToolBrowser.SelectionChanged) -> None:
        event.stop()
        self.status.clear()

    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        event.stop()
        if self.applied or not self._entries:  # nothing to uninstall: keep the standing message
            return
        if not event.ids:
            self.status.set("Select at least one item to remove.", "warn")
            return
        paths: list[Path] = []
        for key in event.ids:
            paths.extend(self._by_key[key].paths)
        decision = UninstallDecision(
            paths=tuple(paths),
            remove_ban=self.remove_ban,
            remove_path_block=self.remove_path_block,
        )
        try:
            self._remove(decision)
        except OSError as exc:
            self.error = str(exc)
            self.status.set(
                f"Uninstall failed: {exc}. Check permissions, then press enter.",
                "error",
            )
            return
        self.error = None
        self.applied = True
        tool_count = sum(1 for key in event.ids if key not in (_BAN_KEY, _BLOCK_KEY))
        self.status.set(self._applied_summary(tool_count), "ok")

    def _applied_summary(self, tool_count: int) -> str:
        parts: list[str] = []
        if tool_count:
            parts.append(f"Removed {tool_count} tool(s).")
        if self.remove_ban:
            parts.append(
                "pip/npm ban removed — open a new shell or run `hash -r` so cached"
                " command paths refresh."
            )
        if self.remove_path_block:
            parts.append("PATH wiring removed — restart your shell to drop the managed dirs.")
        # One line per outcome: a single joined line overflows the terminal width and
        # truncates the reload guidance, so the "needs a new shell" steps go unseen.
        return multiline_summary(parts)


class PoliciesScreen(AppScreen):
    """Toggle environment policies (the pip/npm ban) on/off, applied live.

    Unlike the catalog/uninstall views there is no select-then-apply step: each
    toggle is an immediate, idempotent mutation, so only `enter` is bound (not
    `space`, whose 'harmless select' meaning elsewhere would be a footgun here).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "toggle_policy", "toggle policy", show=True, priority=True),
    ]
    DEFAULT_CSS = """
    PoliciesScreen DataTable { height: 1fr; }
    """

    def __init__(self, inputs: PolicyInputs) -> None:
        super().__init__(view="policies")
        self._policies = inputs.policies
        self.active_state: dict[str, bool] = {
            policy.id: policy.active for policy in inputs.policies
        }
        self.error: str | None = None

    def compose_body(self) -> ComposeResult:
        yield DataTable()

    def on_mount(self) -> None:
        table = self.query_one(DataTable[Any])
        table.cursor_type = "row"
        table.add_column("State", key="state")
        table.add_column("Policy", key="policy")
        table.add_column("Effect", key="effect")
        for policy in self._policies:
            table.add_row(
                self._state_cell(self.active_state[policy.id]),
                Text(policy.label, style="bold yellow"),
                Text(f"shell config: {policy.description}", style="dim"),
                key=policy.id,
            )
        table.focus()

    def _state_cell(self, active: bool) -> Text:
        # A ●/○ glyph carries the state independent of color: the lone row is
        # always focused, so the selection highlight flattens the green/dim cue.
        label = "● [on]" if active else "○ [off]"
        return Text(label, style="green" if active else "dim")

    def _highlighted_policy(self) -> Policy | None:
        table = self.query_one(DataTable[Any])
        if table.row_count == 0:
            return None
        cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        policy_id = cell_key.row_key.value
        return next((policy for policy in self._policies if policy.id == policy_id), None)

    def action_toggle_policy(self) -> None:
        policy = self._highlighted_policy()
        if policy is None:
            return
        active = self.active_state[policy.id]
        try:
            result = policy.remove() if active else policy.apply()
        except OSError as exc:
            self.error = str(exc)
            self.status.set(
                f"Policy change failed: {exc}. Check permissions, then press enter.",
                "error",
            )
            return
        self.error = None
        new_active = not active
        self.active_state[policy.id] = new_active
        self.query_one(DataTable[Any]).update_cell(policy.id, "state", self._state_cell(new_active))
        verb = "enabled" if new_active else "disabled"
        self.status.set(self._summary(policy, verb, result), "ok")

    def _summary(self, policy: Policy, verb: str, result: PolicyResult) -> str:
        # One line per outcome: a single joined line overflows the terminal width
        # and truncates the reload guidance (the Phase 3 fix).
        parts = [f"{policy.label} {verb}."]
        parts.extend(f"{layer.name}: {layer.detail}" for layer in result.layers)
        if result.reload_hint:
            parts.append(result.reload_hint)
        if result.warning:
            parts.append(result.warning)
        return multiline_summary(parts)


class NavScreen(ModalScreen[str | None]):
    """Our command palette: a modal list of views, dismissing the chosen one.

    Replaces Textual's default palette (disabled on the app), whose options
    dead-end by closing the screen. Selecting an item dismisses with the view
    name; Escape dismisses with None (no navigation).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    NavScreen { align: center middle; }
    NavScreen > ListView { width: 60; height: auto; border: round $accent; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(*[ListItem(Label(_PALETTE_LABEL[name]), id=name) for name in VIEW_ORDER])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class UnifiedApp(App[list[str] | None]):
    """One app hosting the wizard views. run() returns the catalog selection
    (ids in catalog order) on accept, or None when aborted. `current_view` and
    `catalog` are public for headless tests."""

    ENABLE_COMMAND_PALETTE = False  # replace Textual's dead-ending default palette
    BINDINGS: ClassVar[list[BindingType]] = [
        # ctrl+c is the hard abort: unguarded, so it quits from anywhere — even on
        # top of the NavScreen modal. q is the soft quit: priority so it fires on
        # every view, but guarded (see action_abort) to no-op under the palette.
        Binding("ctrl+c", "hard_abort", "quit", show=False, priority=True),
        Binding("q", "abort", "quit", show=True, priority=True),
        # esc is NOT priority: NavScreen's own escape->cancel must win while the
        # palette is open; elsewhere no screen binds escape, so it bubbles to back.
        Binding("escape", "back", "back", show=True),
        Binding("ctrl+p", "open_nav", "navigate", priority=True),
        *[
            Binding(str(i + 1), f"show('{name}')", name, priority=True)
            for i, name in enumerate(VIEW_ORDER)
        ],
    ]

    def __init__(
        self,
        tools: list[Tool],
        installed: Mapping[str, bool],
        blurbs: Mapping[str, str],
        *,
        report: DoctorReport,
        guard_status: dict[str, bool],
        guard_warning: str | None,
        fix_preview: str,
        fix: Callable[[], None],
        uninstall: UninstallInputs,
        policies: PolicyInputs,
        initial_view: str = "catalog",
    ) -> None:
        super().__init__()
        self._catalog = CatalogScreen(tools, installed, blurbs)
        # Non-catalog views, pushed by value. Doctor is real; uninstall and
        # policies are live-toggle screens. push_screen/pop_screen stay fully
        # typed under pyright strict (unlike install_screen/switch_screen).
        self._views: dict[str, Screen[None]] = {
            "doctor": DoctorScreen(report, guard_status, guard_warning),
            "fix": FixScreen(fix_preview, fix),
            "uninstall": UninstallScreen(uninstall),
            "policies": PoliciesScreen(policies),
        }
        self._initial_view = initial_view
        self.current_view = "catalog"

    def on_mount(self) -> None:
        if self._initial_view != "catalog":
            self.show_view(self._initial_view)

    @property
    def catalog(self) -> CatalogScreen:
        return self._catalog

    def get_default_screen(self) -> CatalogScreen:
        # The catalog is the app's base screen, so App-level queries (the tests'
        # app.query_one) resolve against it. It reports its decision via the
        # Decided message rather than dismissing the only screen on the stack.
        return self._catalog

    def show_view(self, name: str) -> None:
        # Invariant: the stack is [catalog] or [catalog, <one other view>]. The
        # catalog is the base screen, so navigating to it pops back to it;
        # navigating to another view pops any current overlay first, then pushes
        # the target placeholder. Push/pop keep the stack one deep at most.
        if name == self.current_view:
            return
        if self.current_view != "catalog":
            self.pop_screen()
        if name != "catalog":
            self.push_screen(self._views[name])
        self.current_view = name

    def _navigable(self) -> bool:
        # ctrl+p and the number keys are priority App bindings, so they fire even
        # while a NavScreen modal is open. Navigate only when the catalog or a
        # placeholder is the active screen — never on top of the palette, which
        # would push onto a live modal and break the [catalog] / [catalog, <view>]
        # stack invariant.
        return self.screen is self._catalog or self.screen in self._views.values()

    def action_show(self, name: str) -> None:
        if not self._navigable():
            return
        self.show_view(name)

    async def action_back(self) -> None:
        # One-deep stack: from a pushed view, esc goes home to the catalog; on the
        # catalog itself there is nowhere further back, so esc is inert. async to
        # match App.action_back's signature (pyright-strict rejects a sync override).
        if self._navigable() and self.current_view != "catalog":
            self.show_view("catalog")

    def action_open_nav(self) -> None:
        if not self._navigable():
            return
        self.push_screen(NavScreen(), self._navigate)

    def _navigate(self, name: str | None) -> None:
        if name is not None:
            self.show_view(name)

    def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
        self.exit(message.result)

    def action_abort(self) -> None:
        # The soft quit (q). Guarded so a priority q binding does not quit out from
        # under the NavScreen palette; ctrl+c (action_hard_abort) stays unguarded.
        if not self._navigable():
            return
        self.exit(None)

    def action_hard_abort(self) -> None:
        # The hard quit (ctrl+c): always exits, including on top of the palette.
        self.exit(None)
