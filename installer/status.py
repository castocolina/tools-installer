"""Whether a tool is already installed: command on PATH, or its .app bundle present."""

import shutil
from pathlib import Path

from installer.model import Tool


def _default_app_roots() -> tuple[Path, ...]:
    # A drag-installed copy in /Applications counts as installed too — we must
    # never install a userspace duplicate of a system-wide app.
    return (Path.home() / "Applications", Path("/Applications"))


def is_installed(tool: Tool, app_roots: tuple[Path, ...] | None = None) -> bool:
    """True if the tool's command resolves on PATH, or any app/cask bundle exists."""
    if shutil.which(tool.cmd) is not None:
        return True
    roots = _default_app_roots() if app_roots is None else app_roots
    for method in tool.methods:
        if method.kind not in {"app", "cask"}:
            continue
        app = method.params.get("app")
        if not isinstance(app, str) or not app:
            continue
        # A bundle is a directory; a stale plain file must not mask a real install.
        if any((root / app).is_dir() for root in roots):
            return True
    return False
