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


NEW_SUFFIX = ".tools-installer.new"
OLD_SUFFIX = ".tools-installer.old"


def staged_sibling(path: Path, suffix: str) -> Path:
    """`<name>.tools-installer.{new,old}` next to `path`, never a suffix on the parent."""
    return path.with_name(path.name + suffix)


def capture_symlink_target(link: Path) -> str | None:
    """Read the live symlink target once. Restoration uses this value, never a later readlink."""
    try:
        return os.readlink(link)
    except OSError:
        return None


def recover_update_remnants(live: Path) -> None:
    """Discard a leftover `.new`; always restore a leftover `.old` over `live`.

    `download.py::_replace_archive` and `apps.py::update_app` both swap `.new`
    into `live` BEFORE relinking and validating, and only remove `.old` AFTER
    validation succeeds, in the SAME run that performed the swap (12-REVIEW.md
    C4). So `.old` still being on disk when this recovery runs is itself
    complete proof that the update which created it never finished: either the
    swap never happened (aside-move done, `.old` holds the original, `live` is
    whatever the aside-move left, possibly absent) or the swap happened but
    validation/relinking/cleanup did not (`.old` holds the last KNOWN-GOOD
    tree, `live` holds unvalidated new content that may be broken).

    `live` merely existing is evidence of neither case — a corrupt or
    unvalidated `live` exists exactly as much as a validated one does. So this
    function never infers validity from existence: whenever `.old` is present,
    it unconditionally wins over whatever `live` currently holds, discarding
    `live` first when necessary. The one path that is allowed to remove
    `.old` is the update flow itself, immediately after its own live-in-this-
    run validation succeeds — never this best-effort recovery step.

    Accepted residual: if that same-run cleanup's own `shutil.rmtree(old)`
    fails after a successful, validated update (surfaced to the user as a
    cleanup warning), a later recovery pass restores the older `.old` over the
    newer validated `live`. That is a downgrade to a previously-live version,
    not data loss or corruption, and is out of scope for the invariant this
    function exists to hold.
    """
    new = staged_sibling(live, NEW_SUFFIX)
    old = staged_sibling(live, OLD_SUFFIX)
    if new.exists():
        shutil.rmtree(new)
    if not old.exists():
        return
    if live.exists():
        shutil.rmtree(live)
    os.replace(old, live)


def replace_symlink(link: Path, target: str) -> None:
    """Point `link` at `target` via a sibling temp symlink plus `os.replace`.

    Never shells `ln`. The temp is in the same directory so the replace cannot
    cross a filesystem. A failure leaves `link` untouched (POSIX os.replace
    does not partially apply) and unlinks the temp.
    """
    tmp = _temp_path(link)
    try:
        os.symlink(target, tmp)
        os.replace(tmp, link)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
