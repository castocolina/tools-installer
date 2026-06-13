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
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Middle
from textual.screen import ModalScreen, Screen
from textual.widgets import Label, ListItem, ListView, Static

from installer.catalog_tui import CatalogScreen
from installer.doctor import DoctorReport
from installer.guidance import Guidance, doctor_guidance, guard_guidance
from installer.model import Tool
from installer.render import guidance_text

# Navigation order shared by every route, so the palette and the direct 1..N key
# bindings expose exactly the same views in the same order.
VIEW_ORDER: tuple[str, ...] = ("catalog", "doctor", "fix", "uninstall", "policies")
_PLACEHOLDER_TEXT = {
    "uninstall": "Uninstall — coming in Phase 3",
    "policies": "Policies — coming in Phase 4",
}
_PALETTE_LABEL = {
    "catalog": "Catalog — pick tools to install",
    "doctor": "Doctor — audit your PATH",
    "fix": "Fix — wire PATH into your shells",
    "uninstall": "Uninstall — remove installed tools",
    "policies": "Policies — pip/npm ban and env tweaks",
}


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
        else:
            text.append("Press 'a' to wire the managed PATH into your shells.", style="yellow")
            text.append(f"\n\n{self._preview}")
            text.append("\n\nAfter applying, restart your shell or `source ~/.myshellrc`.")
        body.update(text)

    def action_apply(self) -> None:
        if self.applied:
            return
        self._fix()
        self.applied = True
        self._refresh_body()


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
            "uninstall": PlaceholderScreen(_PLACEHOLDER_TEXT["uninstall"]),
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
