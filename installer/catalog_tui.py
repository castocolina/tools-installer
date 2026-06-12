"""Textual catalog selection screen: one screen, switchable grouping views.

The wizard's interactive selection step (uzkit-parity F1): tools grouped by
category, priority, audience, install status, or shown as a flat sortable
table. Pure grouping/sorting helpers live alongside the app so they can be
unit-tested without a terminal.
"""

from collections.abc import Mapping
from typing import Literal

from installer.model import Tool

TableSortKey = Literal["id", "category", "priority", "audience", "installed"]

PRIORITY_LABEL = {"P0": "essential", "P1": "recommended", "P2": "nice-to-have", "P3": "niche"}
AUDIENCE_LABEL = {"ai": "AI", "human": "you", "both": "both"}


def sort_for_table(
    tools: list[Tool], installed: Mapping[str, bool], key: TableSortKey
) -> list[Tool]:
    """Flat-table order: by `key`, then priority, then id (deterministic)."""
    if key == "installed":
        return sorted(tools, key=lambda t: (installed[t.id], t.priority, t.id))
    return sorted(tools, key=lambda t: (getattr(t, key), t.priority, t.id))


def _category_title(category: str, blurbs: Mapping[str, str]) -> str:
    blurb = blurbs.get(category, "")
    return f"{category} — {blurb}" if blurb else category


def group_tools(
    tools: list[Tool],
    installed: Mapping[str, bool],
    view: str,
    blurbs: Mapping[str, str],
) -> list[tuple[str, list[Tool]]]:
    """(section title, members) per grouped view; members priority-then-id; empty groups dropped."""
    ordered = sorted(tools, key=lambda t: (t.priority, t.id))
    if view == "priority":
        groups = [
            (f"{p} · {PRIORITY_LABEL[p]}", [t for t in ordered if t.priority == p])
            for p in ("P0", "P1", "P2", "P3")
        ]
    elif view == "audience":
        groups = [
            (f"for {AUDIENCE_LABEL[a]}", [t for t in ordered if t.audience == a])
            for a in ("ai", "both", "human")
        ]
    elif view == "status":
        groups = [
            ("missing", [t for t in ordered if not installed[t.id]]),
            ("installed", [t for t in ordered if installed[t.id]]),
        ]
    elif view == "category":
        categories = sorted({t.category for t in ordered})
        groups = [
            (_category_title(c, blurbs), [t for t in ordered if t.category == c])
            for c in categories
        ]
    else:  # "table" is routed by the app before grouping; anything else is a bug
        raise ValueError(f"unknown view: {view!r}")
    return [(title, members) for title, members in groups if members]
