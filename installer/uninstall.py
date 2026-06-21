"""Registry-driven uninstall: remove the userspace artifacts install_download
and install_app create. Cask/brew/native-managed artifacts are left alone."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from installer.apps import APP_KINDS, cli_spec
from installer.download import DOWNLOAD_KINDS
from installer.executors import ExecutorError
from installer.locations import applications_dir, opt_dir
from installer.model import Method, Tool
from installer.platform import Platform
from installer.resolve import resolve_methods


def _exists(path: Path) -> bool:
    # is_symlink catches dangling links (exists() is False when the target is gone).
    return path.exists() or path.is_symlink()


def _plan_app(method: Method, default_bin_dir: Path, add: Callable[[Path], None]) -> None:
    """Plan the ~/Applications bundle and the cli symlink an app method created.

    Only the userspace bundle is planned — a copy in /Applications was never
    ours to manage. The cli symlink name comes from the same validator the
    installer uses (apps.cli_spec), so an invalid cli that install_app would
    have rejected — and therefore never symlinked — plans nothing.
    """
    app = method.params.get("app")
    if not isinstance(app, str) or not app:
        return
    if PurePosixPath(app).name != app or app in (".", ".."):
        return
    add(applications_dir() / app)
    try:
        spec = cli_spec(method)
    except ExecutorError:
        return
    if spec is None:
        return
    add(default_bin_dir / spec[1])


def plan_uninstall(tools: list[Tool], default_bin_dir: Path) -> list[Path]:
    """Existing artifacts the download/raw/app executors would have created.

    The registry is the manifest: every download/raw method maps to opt_dir(binname)
    and <bin_dir>/binname, where binname is the basename of the method's member;
    every app method maps to ~/Applications/<app> and <bin_dir>/<cli basename>.
    Only paths that currently exist (including dangling symlinks) are returned, in a
    stable de-duplicated order.
    """
    found: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path not in seen and _exists(path):
            seen.add(path)
            found.append(path)

    for tool in tools:
        for method in tool.methods:
            if method.kind in APP_KINDS:
                _plan_app(method, default_bin_dir, add)
                continue
            if method.kind not in DOWNLOAD_KINDS:
                continue
            member = method.params.get("member")
            if not isinstance(member, str) or not member:
                continue
            binname = PurePosixPath(member).name
            if binname in ("", ".", ".."):
                # Defensive: a traversal/empty basename would resolve opt_dir/bin
                # paths up to ~/.local and risk deleting far more than one tool.
                # Members come from the trusted registry, but this code deletes files.
                continue
            declared = method.params.get("bin_dir")
            base = (
                Path(declared).expanduser()
                if isinstance(declared, str) and declared
                else default_bin_dir
            )
            add(opt_dir(binname))
            add(base / binname)
    return found


@dataclass(frozen=True)
class ToolRow:
    """A tool annotated with its removability on this machine + platform.

    States: "removable" (userspace artifacts on disk → selectable, has paths),
    "managed" (installed but no userspace artifacts → inert, manager hint),
    "absent" (resolvable here but not installed → inert), "unavailable" (no
    method applies to this platform → inert)."""

    tool: Tool
    state: str
    paths: list[Path]
    hint: str
    selectable: bool


def _manager_name(method: Method, param: str, fallback: str) -> str:
    # brew/cask uninstall takes the formula/cask name (in the method params),
    # NOT the runnable cmd — they differ for e.g. rg/ripgrep, code/visual-studio-code.
    value = method.params.get(param)
    return value if isinstance(value, str) and value else fallback


def _manager_hint(tool: Tool) -> str:
    for method in tool.methods:
        if method.kind == "cask":
            name = _manager_name(method, "cask", tool.cmd)
            return f"managed by Homebrew — `brew uninstall --cask {name}`"
        if method.kind == "brew":
            name = _manager_name(method, "formula", tool.cmd)
            return f"managed by Homebrew — `brew uninstall {name}`"
    return "managed outside this installer — remove with your package manager"


def _managed_hint(tool: Tool, which: Callable[[str], str | None]) -> str:
    # Surface where the tool actually resolves on PATH (e.g. /opt/homebrew/bin/rg)
    # so "managed elsewhere" is concrete: the user sees it is a real, brew/system
    # install this installer did not place and should not delete.
    hint = _manager_hint(tool)
    path = which(tool.cmd)
    return f"{hint} — found at {path}" if path else hint


def classify_tools(
    tools: list[Tool],
    default_bin_dir: Path,
    *,
    installed: dict[str, bool],
    platform: Platform,
    which: Callable[[str], str | None] = shutil.which,
) -> list[ToolRow]:
    """Classify every tool by removability, one ToolRow per tool in input order.

    Reuses plan_uninstall (userspace artifacts), the installed map, the platform
    resolver, and `which` (to resolve where a managed tool lives) so the Uninstall
    view shows full catalog parity: removable-here vs managed-elsewhere vs
    not-installed vs unavailable."""
    rows: list[ToolRow] = []
    for tool in tools:
        paths = plan_uninstall([tool], default_bin_dir)
        if paths:
            rows.append(
                ToolRow(tool, "removable", paths, "installed in userspace — removable here", True)
            )
        elif installed.get(tool.id, False):
            rows.append(ToolRow(tool, "managed", [], _managed_hint(tool, which), False))
        elif resolve_methods(tool, platform):
            rows.append(ToolRow(tool, "absent", [], "not installed", False))
        else:
            rows.append(ToolRow(tool, "unavailable", [], f"not available on {platform.os}", False))
    return rows


def remove_paths(paths: list[Path]) -> None:
    """Delete each path: a symlink is unlinked (target preserved), a dir is removed
    recursively, a file is unlinked."""
    for path in paths:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
