"""Whether a tool is already installed: command on PATH, its .app bundle
present, or a declared detect_path marker file present."""

import shutil
from pathlib import Path

from installer.model import Tool


def _default_app_roots() -> tuple[Path, ...]:
    # A drag-installed copy in /Applications counts as installed too — we must
    # never install a userspace duplicate of a system-wide app.
    return (Path.home() / "Applications", Path("/Applications"))


def is_installed(tool: Tool, app_roots: tuple[Path, ...] | None = None) -> bool:
    """True if the tool's command resolves on PATH, any app/cask bundle exists,
    or a declared detect_path is present.

    detect_path exists for tools whose "is it here" marker is not an
    executable that `which` can find — e.g. SDKMAN's sdkman-init.sh is a
    sourced (non-executable) script, not a PATH binary.
    """
    if shutil.which(tool.cmd) is not None:
        return True
    for method in tool.methods:
        detect_path = method.params.get("detect_path")
        if isinstance(detect_path, str) and detect_path and Path(detect_path).expanduser().exists():
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
