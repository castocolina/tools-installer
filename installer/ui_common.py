"""Shared UI primitives reused across the wizard screens: a single severity
color map, the checkbox mark, the multi-line summary join, and the
highlighted-row lookup. These replace the per-screen copies in wizard_app.py;
catalog_tui.py adopts them when its browser is extracted into a shared widget
(Phase 3).
"""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from rich.text import Text
from textual.app import ComposeResult
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import DataTable, Rule, Static

T = TypeVar("T")

SEVERITY_STYLE: dict[str, str] = {"ok": "green", "warn": "yellow", "error": "red"}


def mark(chosen: bool) -> Text:
    """The [x]/[ ] selection cell shared by the catalog and uninstall tables."""
    return Text("[x]" if chosen else "[ ]", style="green" if chosen else "")


def multiline_summary(parts: list[str]) -> str:
    """One line per outcome. A single joined line overflows terminal width and
    truncates trailing reload guidance, so outcomes are newline-separated."""
    return "\n".join(parts)


def run_live(action: Callable[[], T]) -> tuple[T | None, str | None]:
    """Run a live core mutation from a screen: (result, None) on success,
    (None, message) on OSError. The single apply workflow shared by the fix,
    uninstall, and policies screens — a failed core action is surfaced, never a
    silent crash (PRD), and no screen writes its own try/except for it."""
    try:
        return action(), None
    except OSError as exc:
        return None, str(exc)


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
        self.update(Text(text, style=SEVERITY_STYLE[severity]))

    def clear(self) -> None:
        self.text = ""
        self.update("")


@dataclass(frozen=True)
class View:
    """Everything the chrome knows about one navigable view, in one row:
    the stable name, the header label, the ctrl+p palette description, the
    apply-semantics badge (mode label + glyph + style + hint), and the footer
    action-zone hint. Every per-view UI fact derives from the VIEWS table below,
    so adding a view is a one-row change — the header, palette, badge, footer,
    and 1-N key bindings all follow.

    Badge encoding: the bracketed mode label is the load-bearing signal; the
    glyph fill is the colorblind-safe cue (hollow ◇ = staged: nothing changes
    until you commit; filled ◆ = live: each action applies immediately;
    ▸ = single-action apply; ‹ = read-only); the style is a concrete color."""

    name: str
    label: str
    palette: str
    mode: str
    glyph: str
    style: str
    hint: str
    actions: str


# The single per-view registry, in navigation order (the 1-based position is the
# number key that navigates to the view). Hints name the keys finalized per view;
# Doctor's action zone is an explicit token, not an empty gap.
VIEWS: tuple[View, ...] = (
    View(
        name="catalog",
        label="Catalog",
        palette="Catalog — pick tools to install",
        mode="STAGED",
        glyph="◇",
        style="cyan",
        hint="space marks a tool · enter installs your selection",
        actions="space toggle · enter install · a all · i invert",
    ),
    View(
        name="doctor",
        label="Doctor",
        palette="Doctor — audit your PATH",
        mode="READ-ONLY",
        glyph="‹",
        style="dim",
        hint="audit report · nothing here changes your system",
        actions="(read-only)",
    ),
    View(
        name="fix",
        label="Fix",
        palette="Fix — wire PATH into your shells",
        mode="APPLY",
        glyph="▸",
        style="yellow",
        hint="enter wires the managed PATH into your shells",
        actions="enter apply",
    ),
    View(
        name="uninstall",
        label="Uninstall",
        palette="Uninstall — remove installed tools",
        mode="STAGED · DESTRUCTIVE",
        glyph="◇",
        style="red",
        hint="space marks · enter removes marked items (you'll confirm)",
        actions="space mark · enter remove · a all · i invert",
    ),
    View(
        name="policies",
        label="Policies",
        palette="Policies — pip/npm ban and env tweaks",
        mode="LIVE",
        glyph="◆",
        style="yellow",
        hint="space toggles a policy and applies it now · reversible",
        actions="space toggle",
    ),
)

VIEW_ORDER: tuple[str, ...] = tuple(view.name for view in VIEWS)
VIEW_BY_NAME: dict[str, View] = {view.name: view for view in VIEWS}


def _view_key(index: int) -> str:
    """The bracketed nav key for the view at `index` ([1] … [5]), matching the
    1-based number key that navigates to it. Full-size digits stay legible where
    the old circled glyphs (❶❷…) rendered too small in many terminal fonts. The
    leading bracket is escaped so Textual content markup renders it literally
    instead of parsing it as a tag."""
    return f"\\[{index + 1}]"


# The always-available navigation, shown dim on every view so the user learns one
# rule: the dim cluster right of the separator is global nav; everything left is
# what this screen does.
GLOBAL_NAV: str = "1–5 views · ^p nav · esc back · q quit"


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
        text.append(VIEW_BY_NAME[self._view].actions)
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
        # Each view shows its bracketed key so the 1–5 mapping is always on screen
        # (recognition over recall). The active view is accent-bold; the rest dim.
        parts = [
            f"[bold {self._accent}]{_view_key(index)} {view.label}[/]"
            if view.name == self._active
            else f"[dim]{_view_key(index)} {view.label}[/]"
            for index, view in enumerate(VIEWS)
        ]
        return "    ".join(parts)

    def on_mount(self) -> None:
        self.update(self.render_markup())


class ModeBadge(Static):
    """Docked under the breadcrumb: names the view's apply semantics, redundantly
    encoded (bracketed mode label + glyph + color) so the cue survives a
    colorblind reader and a flattened selection highlight."""

    DEFAULT_CSS = "ModeBadge { height: 1; padding: 0 1; }"

    def __init__(self, view: View) -> None:
        super().__init__()
        self._view = view

    def render_text(self) -> Text:
        # Rich Text (not markup): the [MODE] brackets are literal, and the colors
        # are concrete, so no content-markup escaping or theme-var resolution is
        # needed. Public seam: tests assert on exactly what on_mount paints.
        text = Text()
        text.append(f"{self._view.glyph} [{self._view.mode}]", style=self._view.style)
        text.append(f"   {self._view.hint}", style="dim")  # three spaces: badge token → hint gap
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
        yield ModeBadge(VIEW_BY_NAME[self._view])
        yield from self.compose_body()
        yield self.status
        yield FooterBar(self._view)
