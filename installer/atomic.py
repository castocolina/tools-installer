"""Atomic sibling-temp-plus-os.replace writes for installer-owned files.

A truncated .zshrc, a truncated ownership record, a truncated LaunchAgent plist,
or a truncated version cache is unrecoverable: the original must survive a crash,
a full disk, or a SIGKILL mid-write. Write a sibling temp file in the same
directory (so the rename cannot cross a filesystem), apply an explicit mode when
given else shutil.copymode from an existing target, then os.replace — which is
atomic on POSIX.

When path is itself a symlink (a dotfile-manager setup that symlinks ~/.zshrc to
a repo elsewhere is common), os.replace(tmp, path) would rename OVER the symlink,
deleting it and leaving a plain file in its place. Resolving to the real target
first means the rename replaces the file the symlink points to, and the symlink
itself is never touched.

The sibling temp name is unique per writer (pid + uuid4) so two concurrent
writers racing on the same target cannot destroy each other's in-progress temp
file. The `.tools-installer.tmp` suffix is preserved so existing failed-write
assertions that glob on it still match.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path


def _temp_path(target: Path) -> Path:
    return target.with_name(f"{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tools-installer.tmp")


def atomic_write_bytes(path: Path, data: bytes, *, mode: int | None = None) -> None:
    """Replace path's content atomically, creating it when it does not exist yet.

    When `mode` is given, the temp file is chmod'd to exactly that value before
    the replace — an explicit, umask-independent permission. When `mode` is None
    (the default), shutil.copymode copies the existing target's mode, and a
    brand-new file keeps whatever umask produced.
    """
    target = path.resolve() if path.is_symlink() else path
    tmp = _temp_path(target)
    try:
        tmp.write_bytes(data)
        if mode is not None:
            tmp.chmod(mode)
        elif target.exists():
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str, *, mode: int | None = None) -> None:
    """UTF-8 text entry point over atomic_write_bytes."""
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)
