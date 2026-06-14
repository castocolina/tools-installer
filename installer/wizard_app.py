"""Unified Textual shell hosting the wizard views behind one app.

The app owns navigation and the screen stack. The catalog, doctor, and fix are
functional views; uninstall and policies remain placeholders until later phases.
Execution stays behind the pure `installer/` core invoked from `setup.py`, with
one deliberate exception: the fix view applies its PATH wiring live through an
injected closure. The app's run value stays the catalog decision (`list[str] | None`).

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
from textual.containers import Center, Middle
from textual.coordinate import Coordinate
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from installer.app import UninstallDecision
from installer.catalog_tui import CatalogScreen
from installer.doctor import DoctorReport
from installer.guidance import Guidance, doctor_guidance, guard_guidance
from installer.model import Tool
from installer.render import guidance_text

# Navigation order shared by every route, so the palette and the direct 1..N key
# bindings expose exactly the same views in the same order.
VIEW_ORDER: tuple[str, ...] = ("catalog", "doctor", "fix", "uninstall", "policies")
_PLACEHOLDER_TEXT = {
    "policies": "Policies — coming in Phase 4",
}
_PALETTE_LABEL = {
    "catalog": "Catalog — pick tools to install",
    "doctor": "Doctor — audit your PATH",
    "fix": "Fix — wire PATH into your shells",
    "uninstall": "Uninstall — remove installed tools",
    "policies": "Policies — pip/npm ban and env tweaks",
}


@dataclass(frozen=True)
class UninstallInputs:
    """Everything the UninstallScreen needs: the listable tools with their
    artifact paths, the active ban names, whether a managed PATH block exists,
    and the live removal closure bound by the composition root."""

    removable: list[tuple[Tool, list[Path]]]
    ban_names: list[str]
    has_path_block: bool
    remove: Callable[[UninstallDecision], None]


class PlaceholderScreen(Screen[None]):
    """A navigable stand-in for a view whose body lands in a later phase."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        yield Middle(Center(Label(self._message, id="placeholder")))


class DoctorScreen(Screen[None]):
    """Read-only PATH audit + guidance, color-coded by severity."""

    DEFAULT_CSS = """
    DoctorScreen #doctor-body { padding: 1 2; }
    """

    def __init__(
        self,
        report: DoctorReport,
        guard_status: dict[str, bool],
        guard_warning: str | None,
    ) -> None:
        super().__init__()
        self._report = report
        self._guard_status = guard_status
        self._guard_warning = guard_warning
        self.guidance: list[Guidance] = []  # public test seam

    def compose(self) -> ComposeResult:
        yield Static(id="doctor-body")

    def on_mount(self) -> None:
        self.guidance = doctor_guidance(self._report) + guard_guidance(
            self._guard_status, self._guard_warning
        )
        self.query_one("#doctor-body", Static).update(guidance_text(self.guidance))


class FixScreen(Screen[None]):
    """Preview the PATH wiring + reload guidance; Apply runs it live, in place."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "apply", "apply", show=True),
    ]
    DEFAULT_CSS = """
    FixScreen #fix-body { padding: 1 2; }
    """

    def __init__(self, preview: str, fix: Callable[[], None]) -> None:
        super().__init__()
        self._preview = preview
        self._fix = fix
        self.applied = False  # public test seam
        self.error: str | None = None  # public test seam; set when an apply fails

    def compose(self) -> ComposeResult:
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


class UninstallScreen(Screen[None]):
    """Toggle tools (and the ban / PATH wiring) to remove, then apply live."""

    _BAN_KEY = "#ban"
    _BLOCK_KEY = "#path-block"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_selected", "toggle", show=True),
        Binding("a", "select_all", "all"),
        Binding("i", "invert", "invert"),
        Binding("enter", "remove", "remove selected", show=True, priority=True),
    ]
    DEFAULT_CSS = """
    UninstallScreen #uninstall-status { dock: bottom; height: 1; padding: 0 1; color: $warning; }
    UninstallScreen DataTable { height: 1fr; }
    """

    def __init__(self, inputs: UninstallInputs) -> None:
        super().__init__()
        self._removable = inputs.removable
        self._ban_names = inputs.ban_names
        self._has_path_block = inputs.has_path_block
        self._remove = inputs.remove
        self.selected: set[str] = set()
        self.remove_ban = False
        self.remove_path_block = False
        self.applied = False
        self.error: str | None = None
        self.status_text = ""

    def compose(self) -> ComposeResult:
        yield DataTable()
        yield Static("", id="uninstall-status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable[Any])
        table.cursor_type = "row"
        table.add_column("Sel", key="sel")
        table.add_column("Item", key="item")
        table.add_column("Removes", key="removes")
        for tool, paths in self._removable:
            table.add_row(
                self._mark(False),
                Text(tool.id, style="bold"),
                Text(f"{len(paths)} artifact(s)", style="dim"),
                key=tool.id,
            )
        if self._ban_names:
            table.add_row(
                self._mark(False),
                Text("pip/npm ban", style="bold yellow"),
                Text(f"shims + aliases ({', '.join(self._ban_names)})", style="dim"),
                key=self._BAN_KEY,
            )
        if self._has_path_block:
            table.add_row(
                self._mark(False),
                Text("PATH wiring", style="bold yellow"),
                Text("managed block in ~/.myshellrc", style="dim"),
                key=self._BLOCK_KEY,
            )
        if table.row_count == 0:
            self._set_status("Nothing to uninstall.", style="green")
        table.focus()

    def _mark(self, chosen: bool) -> Text:
        return Text("[x]" if chosen else "[ ]", style="green" if chosen else "")

    def _toggleable_keys(self) -> list[str]:
        keys = [tool.id for tool, _ in self._removable]
        if self._ban_names:
            keys.append(self._BAN_KEY)
        if self._has_path_block:
            keys.append(self._BLOCK_KEY)
        return keys

    def _is_chosen(self, key: str) -> bool:
        if key == self._BAN_KEY:
            return self.remove_ban
        if key == self._BLOCK_KEY:
            return self.remove_path_block
        return key in self.selected

    def _set_chosen(self, key: str, chosen: bool) -> None:
        if key == self._BAN_KEY:
            self.remove_ban = chosen
        elif key == self._BLOCK_KEY:
            self.remove_path_block = chosen
        elif chosen:
            self.selected.add(key)
        else:
            self.selected.discard(key)
        self.query_one(DataTable[Any]).update_cell(key, "sel", self._mark(chosen))

    def _highlighted_key(self) -> str | None:
        table = self.query_one(DataTable[Any])
        if table.row_count == 0:
            return None
        cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        return cell_key.row_key.value

    def _set_status(self, text: str, *, style: str) -> None:
        self.status_text = text
        self.query_one("#uninstall-status", Static).update(Text(text, style=style))

    def _nothing_chosen(self) -> bool:
        return not self.selected and not self.remove_ban and not self.remove_path_block

    def action_toggle_selected(self) -> None:
        if self.applied:
            return
        key = self._highlighted_key()
        if key is None:
            return
        self._set_chosen(key, not self._is_chosen(key))

    def action_select_all(self) -> None:
        if self.applied:
            return
        for key in self._toggleable_keys():
            self._set_chosen(key, True)

    def action_invert(self) -> None:
        if self.applied:
            return
        for key in self._toggleable_keys():
            self._set_chosen(key, not self._is_chosen(key))

    def action_remove(self) -> None:
        if self.applied or not self._toggleable_keys():
            return
        if self._nothing_chosen():
            self._set_status("Select at least one item to remove.", style="yellow")
            return
        paths: list[Path] = []
        for tool, tool_paths in self._removable:
            if tool.id in self.selected:
                paths.extend(tool_paths)
        decision = UninstallDecision(
            paths=tuple(paths), remove_ban=self.remove_ban, remove_path_block=self.remove_path_block
        )
        try:
            self._remove(decision)
        except OSError as exc:
            self.error = str(exc)
            self._set_status(
                f"Uninstall failed: {exc}. Check permissions, then press enter.",
                style="red",
            )
            return
        self.error = None
        self.applied = True
        self._set_status(self._applied_summary(len(paths)), style="green")

    def _applied_summary(self, removed: int) -> str:
        parts = [f"Removed {removed} item(s)."]
        if self.remove_ban:
            parts.append("pip/npm ban removed — open a new shell or run `hash -r`.")
        if self.remove_path_block:
            parts.append("PATH wiring removed — restart your shell to drop the managed dirs.")
        return "  ".join(parts)


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
        Binding("ctrl+c", "abort", "quit", show=False, priority=True),
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
        initial_view: str = "catalog",
    ) -> None:
        super().__init__()
        self._catalog = CatalogScreen(tools, installed, blurbs)
        # Non-catalog views, pushed by value. Doctor is real; the rest are
        # placeholders until their phases. push_screen/pop_screen stay fully
        # typed under pyright strict (unlike install_screen/switch_screen).
        self._views: dict[str, Screen[None]] = {
            "doctor": DoctorScreen(report, guard_status, guard_warning),
            "fix": FixScreen(fix_preview, fix),
            "uninstall": UninstallScreen(uninstall),
            "policies": PlaceholderScreen(_PLACEHOLDER_TEXT["policies"]),
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
        self.exit(None)
