"""Shared UI primitives reused across the wizard screens: a single severity
color map, the checkbox mark, the multi-line summary join, and the
highlighted-row lookup. These replace the per-screen copies in wizard_app.py;
catalog_tui.py adopts them when its browser is extracted into a shared widget
(Phase 3).
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import DataTable, Rule, Static

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


def _view_key_glyph(index: int) -> str:
    """The circled-digit nav key for the view at `index` (❶=0 … ❿=9), matching the
    1-based number key that navigates to it."""
    return chr(0x2776 + index)


@dataclass(frozen=True)
class ViewMode:
    """The apply-semantics badge for a view: a bracketed label (the load-bearing
    signal), a glyph whose fill is the colorblind-safe cue (hollow ◇ = staged,
    filled ◆ = live), a concrete color, and a plain-language controls hint."""

    label: str
    glyph: str
    style: str
    hint: str


# One mode per view. Hollow ◇ = staged (nothing changes until you commit);
# filled ◆ = live (each action applies immediately). Fix is a single-action
# apply (▸); Doctor is read-only (‹). Hints name the keys finalized for each view.
VIEW_MODES: dict[str, ViewMode] = {
    "catalog": ViewMode(
        "STAGED", "◇", "cyan", "space marks a tool · enter installs your selection"
    ),
    "doctor": ViewMode("READ-ONLY", "‹", "dim", "audit report · nothing here changes your system"),
    "fix": ViewMode("APPLY", "▸", "yellow", "enter wires the managed PATH into your shells"),
    "uninstall": ViewMode(
        "STAGED · DESTRUCTIVE",
        "◇",
        "red",
        "space marks · enter removes marked items (you'll confirm)",
    ),
    "policies": ViewMode(
        "LIVE", "◆", "yellow", "space toggles a policy and applies it now · reversible"
    ),
}


# The always-available navigation, shown dim on every view so the user learns one
# rule: the dim cluster right of the separator is global nav; everything left is
# what this screen does.
GLOBAL_NAV: str = "1–5 views · ^p nav · esc back · q quit"

# The action-zone hint per view (left of the separator). Doctor is read-only, so
# its action zone is an explicit token, not an empty gap.
FOOTER_ACTIONS: dict[str, str] = {
    "catalog": "space toggle · enter install · a all · i invert",
    "doctor": "(read-only)",
    "fix": "enter apply",
    "uninstall": "space mark · enter remove · a all · i invert",
    "policies": "space toggle",
}


class FooterBar(Static):
    """Two-zone key hints: this view's actions, a separator, then dim global nav.
    Replaces Textual's Footer, whose undifferentiated binding union read the same
    on every view (including read-only Doctor)."""

    DEFAULT_CSS = "FooterBar { dock: bottom; height: 1; padding: 0 1; background: $surface; }"

    def __init__(self, view: str) -> None:
        super().__init__()
        self._view = view

    def render_text(self) -> Text:
        text = Text()
        text.append(FOOTER_ACTIONS[self._view])
        text.append("   │   ", style="dim")
        text.append(GLOBAL_NAV, style="dim")
        return text

    def on_mount(self) -> None:
        self.update(self.render_text())


class WayfindingHeader(Static):
    """Docked-top breadcrumb of the five views; the active one is accent-bold,
    the rest dim. Accent recolors per screen (e.g. destructive red on uninstall)."""

    DEFAULT_CSS = "WayfindingHeader { height: 1; padding: 0 1; }"

    def __init__(self, *, active: str, accent: str = "$accent") -> None:
        super().__init__()
        self._active = active
        self._accent = accent

    def render_markup(self) -> str:
        # Textual content markup (not Rich Text): $accent is a Textual theme variable
        # that Rich's own style parser rejects, so markup lets Textual resolve it at render time.
        # Each view shows its circled key so the 1–5 mapping is always on screen
        # (recognition over recall). The active view is accent-bold; the rest dim.
        parts = [
            f"[bold {self._accent}]{_view_key_glyph(index)} {label}[/]"
            if key == self._active
            else f"[dim]{_view_key_glyph(index)} {label}[/]"
            for index, (key, label) in enumerate(VIEW_LABELS)
        ]
        return "    ".join(parts)

    def on_mount(self) -> None:
        self.update(self.render_markup())


class ModeBadge(Static):
    """Docked under the breadcrumb: names the view's apply semantics, redundantly
    encoded (bracketed label + glyph + color) so the cue survives a colorblind
    reader and a flattened selection highlight."""

    DEFAULT_CSS = "ModeBadge { height: 1; padding: 0 1; }"

    def __init__(self, mode: ViewMode) -> None:
        super().__init__()
        self._mode = mode

    def render_text(self) -> Text:
        # Rich Text (not markup): the [LABEL] brackets are literal, and the colors
        # are concrete, so no content-markup escaping or theme-var resolution is
        # needed. Public seam: tests assert on exactly what on_mount paints.
        text = Text()
        text.append(f"{self._mode.glyph} [{self._mode.label}]", style=self._mode.style)
        text.append(f"   {self._mode.hint}", style="dim")  # three spaces: badge token → hint gap
        return text

    def on_mount(self) -> None:
        self.update(self.render_text())


class AppScreen(Screen[None]):
    """Base scaffold: WayfindingHeader + a divider Rule + ModeBadge + the subclass
    body + StatusLine + FooterBar. The chrome is guaranteed so a screen can never
    ship without nav."""

    DEFAULT_CSS = "AppScreen > Rule { margin: 0; color: $accent; }"

    def __init__(self, *, view: str, accent: str = "$accent") -> None:
        super().__init__()
        self._view = view
        self._accent = accent
        self.status = StatusLine()

    @abstractmethod
    def compose_body(self) -> ComposeResult: ...

    def compose(self) -> ComposeResult:
        yield WayfindingHeader(active=self._view, accent=self._accent)
        yield Rule()
        yield ModeBadge(VIEW_MODES[self._view])
        yield from self.compose_body()
        yield self.status
        yield FooterBar(self._view)
