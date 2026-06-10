"""Registry-driven uninstall: remove the userspace artifacts install_download creates."""

import shutil
from pathlib import Path, PurePosixPath

from installer.download import DOWNLOAD_KINDS
from installer.locations import opt_dir
from installer.model import Tool


def _exists(path: Path) -> bool:
    # is_symlink catches dangling links (exists() is False when the target is gone).
    return path.exists() or path.is_symlink()


def plan_uninstall(tools: list[Tool], default_bin_dir: Path) -> list[Path]:
    """Existing opt dirs and bin entries the download/raw executors would have created.

    The registry is the manifest: every download/raw method maps to opt_dir(binname)
    and <bin_dir>/binname, where binname is the basename of the method's member.
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
