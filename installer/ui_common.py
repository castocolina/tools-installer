"""Shared UI primitives reused across the wizard screens: a single severity
color map, the checkbox mark, the multi-line summary join, and the
highlighted-row lookup. These replace the per-screen copies in wizard_app.py;
catalog_tui.py adopts them when its browser is extracted into a shared widget
(Phase 3).
"""

from abc import abstractmethod
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

SEVERITY_STYLE: dict[str, str] = {"ok": "green", "warn": "yellow", "error": "red"}


def severity_style(level: str) -> str:
    return SEVERITY_STYLE[level]


def mark(chosen: bool) -> Text:
    """The [x]/[ ] selection cell shared by the catalog and uninstall tables."""
    return Text("[x]" if chosen else "[ ]", style="green" if chosen else "")


def multiline_summary(parts: list[str]) -> str:
    """One line per outcome. A single joined line overflows terminal width and
    truncates trailing reload guidance, so outcomes are newline-separated."""
    return "\n".join(parts)


def highlighted_key(table: DataTable[Any]) -> str | None:
    """The row-key value under the cursor, or None on an empty table."""
    if table.row_count == 0:
        return None
    cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
    return cell_key.row_key.value


class StatusLine(Static):
    """A docked status line. Neutral by default; each set() colors by severity.
    Replaces the three near-identical _set_status/_clear_status pairs (and the
    divergent `color: $warning` defaults) in catalog/uninstall/policies."""

    DEFAULT_CSS = "StatusLine { height: auto; padding: 0 1; }"

    def __init__(self) -> None:
        super().__init__("")
        self.text = ""  # public test seam

    def set(self, text: str, severity: str) -> None:
        self.text = text
        self.update(Text(text, style=severity_style(severity)))

    def clear(self) -> None:
        self.text = ""
        self.update("")


# The five views in navigation order with their short header labels. The Ctrl+P
# palette is a separate concern: it keys off VIEW_ORDER and its own richer
# descriptions (in wizard_app), so this tuple drives the WayfindingHeader only.
VIEW_LABELS: tuple[tuple[str, str], ...] = (
    ("catalog", "Catalog"),
    ("doctor", "Doctor"),
    ("fix", "Fix"),
    ("uninstall", "Uninstall"),
    ("policies", "Policies"),
)


class WayfindingHeader(Static):
    """Docked-top breadcrumb of the five views; the active one is accent-bold,
    the rest dim. Accent recolors per screen (e.g. destructive red on uninstall)."""

    DEFAULT_CSS = "WayfindingHeader { height: 1; padding: 0 1; }"

    def __init__(self, *, active: str, accent: str = "$accent") -> None:
        super().__init__()
        self._active = active
        self._accent = accent

    def render_markup(self) -> str:
        # Textual content markup (not a Rich Text): markup resolves the `$accent`
        # theme variable, which Rich's own style parser rejects. The accent color —
        # not literal brackets — marks the active view. Public seam so tests assert
        # on exactly the string on_mount renders.
        parts = [
            f"[bold {self._accent}]{label}[/]" if key == self._active else f"[dim]{label}[/]"
            for key, label in VIEW_LABELS
        ]
        return "[dim]tools-installer · [/]" + "  ".join(parts)

    def on_mount(self) -> None:
        self.update(self.render_markup())


class AppScreen(Screen[None]):
    """Base scaffold: WayfindingHeader + the subclass body + StatusLine + Footer.
    Subclasses implement compose_body(); the chrome is guaranteed so a screen can
    never again ship without nav (the Phase-1 footer fix made structural)."""

    def __init__(self, *, view: str, accent: str = "$accent") -> None:
        super().__init__()
        self._view = view
        self._accent = accent
        self.status = StatusLine()

    @abstractmethod
    def compose_body(self) -> ComposeResult: ...

    def compose(self) -> ComposeResult:
        yield WayfindingHeader(active=self._view, accent=self._accent)
        yield from self.compose_body()
        yield self.status
        yield Footer()
