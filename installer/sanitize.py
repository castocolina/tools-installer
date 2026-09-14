"""Untrusted-text sanitization shared by every boundary where child-process
output can reach a live terminal or a Textual widget.

A leaf module with no `installer.*` imports of its own so `run.py` (which
captures raw child output) and `render.py` / `execute_screen.py` (which
render it) can all depend on it without a cycle.
"""

_C0_KEEP = frozenset({9, 10})  # tab, newline
_DEL = 127


def sanitize_log_line(text: str) -> str:
    """Strip ASCII control characters other than tab and newline.

    An install script's escape sequences must not be able to reposition the
    cursor, recolour the running frame, or (via OSC) rewrite the terminal
    title or clipboard. Applied at every point where child-process output —
    a streamed line or a captured multi-line failure report — first becomes
    text a widget will render, not only on the success/streaming path.
    """
    return "".join(ch for ch in text if ord(ch) != _DEL and (ord(ch) >= 32 or ord(ch) in _C0_KEEP))
