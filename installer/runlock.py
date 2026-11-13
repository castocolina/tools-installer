"""The installer side of the cross-process run lock.

One `flock` helper serves two jobs: short blocking sections (`hold`, the state file's
load-change-save) and the non-blocking run lock (`try_acquire`) that a scheduled run and an
installer mutation contend for. The lock file also carries a holder line, `<job> <pid> <iso>`,
which `holder` reads so a view can tell who runs without probing the lock: a probe from the
view could make a starting runner see `busy` (24.2 RESEARCH Pitfall 5).
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from installer.atomic import read_capped
from installer.locations import ensure_dir

INSTALLER_JOB = "installer"
_HOLDER_READ_CAP = 4096


def run_lock_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "run.lock"


def _open_lock_file(path: Path) -> int:
    """Open (creating) a lock file without truncating it, never through a symlink."""
    ensure_dir(path.parent)
    return os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)


class RunLock:
    """A held run lock; `release` clears the holder line and drops the lock."""

    def __init__(self, descriptor: int) -> None:
        self._descriptor = descriptor

    def release(self) -> None:
        if self._descriptor < 0:
            return
        try:
            os.ftruncate(self._descriptor, 0)
            fcntl.flock(self._descriptor, fcntl.LOCK_UN)
        finally:
            os.close(self._descriptor)
            self._descriptor = -1


def try_acquire(path: Path, job: str) -> RunLock | None:
    """Take the run lock without waiting, or None when another open file description holds it."""
    descriptor = _open_lock_file(path)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(descriptor)
        return None
    except BaseException:
        os.close(descriptor)
        raise
    since = datetime.now().astimezone().isoformat(timespec="seconds")
    os.ftruncate(descriptor, 0)
    os.pwrite(descriptor, f"{job} {os.getpid()} {since}\n".encode(), 0)
    return RunLock(descriptor)


@dataclass(frozen=True)
class Holder:
    job: str
    pid: int
    since: str


def holder(path: Path) -> Holder | None:
    """Who the holder line names, when that process is alive; never a lock probe."""
    try:
        raw = read_capped(path, _HOLDER_READ_CAP, follow_symlinks=False)
    except OSError:
        return None
    fields = (raw or b"").decode("utf-8", errors="replace").split()
    if len(fields) != 3 or not fields[1].isascii() or not fields[1].isdigit():
        return None
    job, pid, since = fields[0], int(fields[1]), fields[2]
    if pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except PermissionError:
        pass  # alive, owned by another user
    except (ProcessLookupError, OverflowError):
        return None
    return Holder(job, pid, since)


@contextmanager
def hold(path: Path) -> Generator[None]:
    """Hold a blocking exclusive lock on `path` for a short critical section."""
    descriptor = _open_lock_file(path)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)  # closing the descriptor drops the flock
