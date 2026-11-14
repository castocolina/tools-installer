"""Recognition and removal of the package-manager guard earlier versions wrote.

Earlier versions put sentinel-marked `npm`, `npx`, `pnpm`, `pip` and `pip3` PATH shims in the
managed bin dir and a `tools-installer ban` alias block in the shell rc files. Nothing in this
module writes a shim or a block: it only recognizes the leftovers and removes them, one named
line per removal, and a failure is one warning line. Neither remover raises.

Read-failure rule (GUARD-02): at a file's first read, any `OSError` other than a missing path
(ENOENT, ENOTDIR) is one warning naming the path and the permission fix, because a leftover
may stay active behind it; the warning never advises deleting a file the read could not
verify. A failure at a re-check read (the rc pre-write re-read, the shim's identity re-open)
is a silent skip with no write and no delete: the file changed under the cleanup, and the next
launch's first read warns if the problem persists.
"""

import os
import stat
from collections.abc import Sequence
from pathlib import Path

import installer.locations
from installer.atomic import atomic_write_text, read_capped, read_snapshot, snapshot_matches
from installer.sanitize import sanitize_log_line

SHIM_SENTINEL = "# tools-installer-ban-shim"
REDIRECT_SENTINEL: str = "# tools-installer-redirect-shim"
BAN_BEGIN = "# >>> tools-installer ban >>>"
BAN_END = "# <<< tools-installer ban <<<"
GUARD_NAMES: tuple[str, ...] = ("npm", "npx", "pnpm", "pip", "pip3")
_SHIM_MAX_BYTES = 8192
_RC_MAX_BYTES = 1 << 20  # the cap installer.tweaks reads an rc file with

_Line = tuple[str, str]


def _is_leftover(data: bytes) -> bool:
    """The one definition of a recognized leftover shim body.

    At most 8192 bytes, strict UTF-8, either sentinel. The remover uses it, and the PATH
    lookups that later move into this module share it, so cleanup, presence, smoke and probe
    can never disagree on what a leftover is.
    """
    if len(data) > _SHIM_MAX_BYTES:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return SHIM_SENTINEL in text or REDIRECT_SENTINEL in text


def _reason(exc: OSError) -> str:
    return sanitize_log_line(((exc.strerror or str(exc)).splitlines() or [""])[0])


def _shown(path: Path) -> str:
    return sanitize_log_line(installer.locations.display_path(path))


def _strip_ban_blocks(text: str) -> str:
    """Drop every well-formed ban block and keep every other byte as read.

    A marker line is one equal to BAN_BEGIN or BAN_END after ignoring one trailing CR, so a
    whole-file CRLF block matches. A begin line opens a candidate; a later begin replaces it
    (the earlier begin is an orphan and stays); an end line closes the open candidate and drops
    its lines, the CRLF terminators included. An end with no open candidate stays, and a
    candidate still open at the end of the file stays with everything after it.
    """
    kept: list[str] = []
    open_at: int | None = None
    for line in text.split("\n"):
        marker = line.removesuffix("\r")
        if marker == BAN_BEGIN:
            open_at = len(kept)
            kept.append(line)
        elif marker == BAN_END and open_at is not None:
            del kept[open_at:]
            open_at = None
        else:
            kept.append(line)
    return "\n".join(kept)


def _remove_ban_block(path: Path) -> _Line | None:
    try:
        data = read_capped(path, _RC_MAX_BYTES, follow_symlinks=True)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:
        return (
            f"Could not check {_shown(path)} for the retired guard alias block: {_reason(exc)}; "
            "fix its permissions, then relaunch.",
            "warn",
        )
    if data is None:
        return None
    try:
        text = data.decode("utf-8")  # never read_text: universal newlines would drop every CR
    except UnicodeDecodeError:
        return None
    stripped = _strip_ban_blocks(text)
    if stripped == text:
        return None
    try:
        again = read_capped(path, _RC_MAX_BYTES, follow_symlinks=True)
    except OSError:
        return None
    if again != data:
        return None
    shown = _shown(path)
    try:
        # shortcut: an edit landing between the re-read and atomic_write_text's replace is
        # still lost (no compare-and-swap for a path); upgrade if rc writers gain a shared lock.
        atomic_write_text(path, stripped)
    except OSError as exc:
        return (
            f"Could not remove the retired guard alias block from {shown}: {_reason(exc)}; "
            "fix its permissions, then relaunch.",
            "warn",
        )
    return (f"Removed the retired guard alias block from {shown}.", "ok")


def remove_ban_blocks(rc_paths: Sequence[Path]) -> tuple[_Line, ...]:
    """Remove every well-formed ban block from each rc file; one line per changed file."""
    lines = (_remove_ban_block(path) for path in rc_paths)
    return tuple(line for line in lines if line is not None)


def _remove_guard_shim(path: Path) -> _Line | None:
    try:
        info = os.lstat(path)
        # The size pre-check keeps read_snapshot from reading up to 16 MiB of a foreign file.
        if not stat.S_ISREG(info.st_mode) or info.st_size > _SHIM_MAX_BYTES:
            return None
        snapshot = read_snapshot(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:
        return (
            f"Could not check {_shown(path)} for the retired pip/npm guard shim: {_reason(exc)}; "
            "fix its permissions, then relaunch.",
            "warn",
        )
    if not _is_leftover(snapshot.data):
        return None
    shown = _shown(path)
    if not snapshot_matches(path, snapshot):
        return None
    try:
        # shortcut: no userspace unlink is atomic against a swap; a replacement landing between
        # snapshot_matches and os.unlink is still deleted. The re-check narrows that window to
        # two syscalls; upgrade if an identity-checked unlink (unlink-if-same-inode) exists.
        os.unlink(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return (
            f"Could not remove the retired pip/npm guard shim {shown}: {_reason(exc)}; "
            "delete it yourself or make its directory writable, then relaunch.",
            "warn",
        )
    return (f"Removed the retired pip/npm guard shim {shown}.", "ok")


def remove_guard_shims(bin_dir: Path) -> tuple[_Line, ...]:
    """Remove each sentinel-marked guard shim in bin_dir; one line per removal or failure."""
    lines = (_remove_guard_shim(bin_dir / name) for name in GUARD_NAMES)
    return tuple(line for line in lines if line is not None)
