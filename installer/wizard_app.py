"""Unified Textual shell hosting the wizard views behind one app.

Phase 1 of the unified-UI redesign. The app owns navigation and the screen
stack; the catalog is the only functional view. Execution stays behind the pure
`installer/` core invoked from `setup.py`; the app only collects the catalog
decision (`list[str] | None`).

The catalog is the base screen (`get_default_screen`); it cannot be switched
out. Navigation is therefore a stack with the catalog at the bottom: the stack
is always `[catalog]` or `[catalog, <one other view>]`. The other views are
placeholders until later phases fill them in.
"""

from collections.abc import Mapping
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Label

from installer.catalog_tui import CatalogScreen
from installer.model import Tool

# Navigation order shared by every route, so the palette and the direct 1..N key
# bindings expose exactly the same views in the same order.
VIEW_ORDER: tuple[str, ...] = ("catalog", "doctor", "fix", "uninstall", "policies")
_PLACEHOLDER_TEXT = {
    "doctor": "Doctor — coming in Phase 2",
    "fix": "Fix — coming in Phase 2",
    "uninstall": "Uninstall — coming in Phase 3",
    "policies": "Policies — coming in Phase 4",
}


class PlaceholderScreen(Screen[None]):
    """A navigable stand-in for a view whose body lands in a later phase."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        yield Middle(Center(Label(self._message, id="placeholder")))


class UnifiedApp(App[list[str] | None]):
    """One app hosting the wizard views. run() returns the catalog selection
    (ids in catalog order) on accept, or None when aborted. `current_view` and
    `catalog` are public for headless tests."""

    ENABLE_COMMAND_PALETTE = False  # replace Textual's dead-ending default palette
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "abort", "quit", show=False, priority=True),
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
    ) -> None:
        super().__init__()
        self._catalog = CatalogScreen(tools, installed, blurbs)
        # Placeholder screens are held as instances and pushed by value. Textual
        # types `push_screen`/`pop_screen` generically (so they stay fully typed
        # under pyright strict), unlike `install_screen`/`switch_screen` whose
        # bare-`Screen` stubs leak `Unknown`.
        self._placeholders: dict[str, Screen[None]] = {
            name: PlaceholderScreen(message) for name, message in _PLACEHOLDER_TEXT.items()
        }
        self.current_view = "catalog"

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
            self.push_screen(self._placeholders[name])
        self.current_view = name

    def action_show(self, name: str) -> None:
        self.show_view(name)

    def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
        self.exit(message.result)

    def action_abort(self) -> None:
        self.exit(None)
