"""Update-all planning and result formatting, without starting processes."""

from __future__ import annotations

import re
from collections.abc import Sequence

RESULT_LIMIT = 300
FIRST_FAILED_LIMIT = 40
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def plain_line(text: str, limit: int = RESULT_LIMIT) -> str:
    """Remove terminal escapes and controls, then bound the resulting single line."""
    return " ".join(_CONTROLS.sub("", _ANSI.sub("", text)).split())[:limit]


def summary_line(
    *,
    updated: int,
    skipped: int,
    unchanged: int = 0,
    failed: int = 0,
    first_failed: str = "",
    clauses: Sequence[str] = (),
) -> str:
    """Format one bounded result, preserving the counts and trimming only clauses."""
    if failed:
        name = plain_line(first_failed, FIRST_FAILED_LIMIT)
        line = f"failed: {failed} failed ({name}), {updated} updated, {skipped} skipped"
    elif updated or skipped or unchanged:
        line = f"ok: {updated} updated, {skipped} skipped"
    else:
        line = "ok: 0 updated"
    if unchanged:
        line += f"; {unchanged} unchanged"
    for clause in clauses:
        value = plain_line(clause)
        room = RESULT_LIMIT - len(line) - 2
        if room <= 0:
            break
        value = value[:room].rstrip()
        if value:
            line += f"; {value}"
    return line
