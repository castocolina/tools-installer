"""Whether a tool is already installed: command on PATH, its .app bundle
present, or a declared detect_path marker file present."""

import os
import shutil
from collections.abc import Mapping
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


def is_default_shell(tool: Tool, *, env: Mapping[str, str] | None = None) -> bool | None:
    """True/False when `tool` is a shell (category "shell") and $SHELL is set;
    None when the question doesn't apply (not a shell tool) or can't be
    answered ($SHELL unset -- e.g. a non-interactive/CI environment).

    A shell binary being on PATH (is_installed's job) says nothing about
    whether logging in actually starts it -- that's a login-shell property
    ($SHELL / the passwd entry chsh writes), not a package-presence fact.
    $SHELL is read here rather than /etc/passwd because it reflects the
    *running* session's login shell directly and needs no platform-specific
    passwd-database lookup (getpwuid differs enough between glibc and macOS's
    Directory Services to not be worth it for a display-only hint).
    """
    if tool.category != "shell":
        return None
    shell = (env if env is not None else os.environ).get("SHELL")
    if not shell:
        return None
    return Path(shell).name == tool.cmd
