"""The installer side of the cross-process run lock.

One `flock` helper serves two jobs: short blocking sections (the state file's
load-change-save) and, from `try_acquire`, the non-blocking run lock a scheduled
run and an installer mutation contend for.
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from installer.locations import ensure_dir


def _open_lock_file(path: Path) -> int:
    """Open (creating) a lock file without truncating it, never through a symlink."""
    ensure_dir(path.parent)
    return os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)


@contextmanager
def hold(path: Path) -> Generator[None]:
    """Hold a blocking exclusive lock on `path` for a short critical section."""
    descriptor = _open_lock_file(path)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)  # closing the descriptor drops the flock
