"""Unified Textual shell hosting the wizard views behind one app.

Phase 1 of the unified-UI redesign. The app owns navigation and the screen
stack; the catalog is the only functional view. Execution stays behind the pure
`installer/` core invoked from `setup.py`; the app only collects the catalog
decision (`list[str] | None`).
"""

from collections.abc import Mapping
from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

from installer.catalog_tui import CatalogScreen
from installer.model import Tool


class UnifiedApp(App[list[str] | None]):
    """One app hosting the wizard views. run() returns the catalog selection
    (ids in catalog order) on accept, or None when aborted. `current_view` and
    `catalog` are public for headless tests."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "abort", "quit", show=False, priority=True),
    ]

    def __init__(
        self,
        tools: list[Tool],
        installed: Mapping[str, bool],
        blurbs: Mapping[str, str],
    ) -> None:
        super().__init__()
        self._catalog = CatalogScreen(tools, installed, blurbs)
        self.current_view = "catalog"

    @property
    def catalog(self) -> CatalogScreen:
        return self._catalog

    def get_default_screen(self) -> CatalogScreen:
        # The catalog is the app's base screen, so App-level queries (the tests'
        # app.query_one) resolve against it. It reports its decision via the
        # Decided message rather than dismissing the only screen on the stack.
        return self._catalog

    def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
        self.exit(message.result)

    def action_abort(self) -> None:
        self.exit(None)
