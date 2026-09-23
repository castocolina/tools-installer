"""Manage ~/.myshellrc as one marker-delimited PATH block, and wire `source` into rc files.

Every write is idempotent: only the marked block is ever rewritten, user content is
preserved, and entries are never duplicated across runs. Every write in this module
goes through installer/atomic.py, because a truncated rc file is unrecoverable and
these files are edited read-modify-write.
"""

import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from installer.atomic import OLD_SUFFIX, atomic_write_bytes, atomic_write_text, staged_sibling
from installer.model import Tool
from installer.platform import Platform
from installer.resolve import resolve_methods

_PATH_BEGIN = "# >>> tools-installer path >>>"
_PATH_END = "# <<< tools-installer path <<<"
_SOURCE_BEGIN = "# >>> tools-installer source >>>"
_SOURCE_END = "# <<< tools-installer source <<<"
_SHELLRC_BEGIN = "# >>> tools-installer consolidated shellrc >>>"
_SHELLRC_END = "# <<< tools-installer consolidated shellrc <<<"
_STUB_BEGIN = "# >>> tools-installer shellrc stub >>>"
_STUB_END = "# <<< tools-installer shellrc stub <<<"


def _resolve_home(path: Path, home: Path) -> Path:
    """Resolve only the current-user tilde against an injected home directory."""
    raw = str(path)
    if raw == "~":
        return home
    if raw.startswith("~/"):
        return home / raw[2:]
    return path


def collect_bin_dirs(
    tools: list[Tool],
    platform: Platform,
    default: Path,
    exists: Callable[[Path], bool] = Path.is_dir,
    *,
    home: Path | None = None,
) -> list[Path]:
    """The default bin dir plus each platform-applicable method's existing bin_dir.

    The default is always managed. A declared bin_dir is managed only when the
    directory exists on disk: a missing dir means the tool was never installed,
    and wiring it into PATH (or reporting it broken) is noise. Disk presence —
    not PATH probing — avoids the bootstrap chicken-and-egg: right after
    installing brew, `brew` is not on PATH yet but /opt/homebrew/bin exists.

    `home`, when given, is used only to resolve a bare `~` or `~/...` default —
    letting a caller inject a non-default home for tests, while every other
    path is unaffected.
    """
    resolved_home = Path.home() if home is None else home
    dirs: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path, *, require_exists: bool) -> None:
        resolved = _resolve_home(path, resolved_home)
        if resolved in seen or (require_exists and not exists(resolved)):
            return
        seen.add(resolved)
        dirs.append(resolved)

    add(default, require_exists=False)
    for tool in tools:
        for method in resolve_methods(tool, platform):
            raw = method.params.get("bin_dir")
            if isinstance(raw, str) and raw:
                add(Path(raw), require_exists=True)
    return dirs


def path_export_guard(directory: Path) -> str:
    """Emit a self-deduping PATH line that adds directory at most once per shell.

    Re-sourcing this line in a nested or child shell (or in the same shell
    multiple times) adds the directory to PATH at most once. This is achieved
    through a case-guarded self-deduping idiom that pnpm uses and that
    `installer/rcclean.py::find_duplicate_path_lines` already documents as
    safe to leave alone (the scanner does not flag lines starting with `case`).

    Paths are double-quoted but not otherwise escaped: they come only from the
    trusted registry and Path.home(), never from user input. Do not feed
    user-supplied paths here without shell-quoting first.

    When the directory has a second spelling (e.g. /home -> /var/home on
    Fedora, or /var -> /private/var on macOS), the guard matches both spellings
    to detect if the directory is already on PATH under either name. However,
    the VALUE prepended onto PATH is always the DECLARED spelling (never
    canonicalized), so that `installer/doctor.py::audit_path` and
    `installer/rcclean.py` -- which both compare raw PATH entries against
    declared directory strings -- continue to recognize what this project writes.

    The conditional expansion `${PATH:+:$PATH}` is security-critical: an empty
    PATH component (the trailing empty string after a colon-join) resolves to
    the current working directory in every POSIX shell. An empty starting PATH
    becomes exactly the managed directory with no empty component, so the
    managed shell cannot execute a same-named script out of the user's cwd.

    The guard reads PATH through `${PATH-}` (default-applying expansion), not
    bare `$PATH`, so the line does not abort a shell running under `set -u`
    with PATH unset.
    """
    declared = str(directory)
    try:
        resolved = str(directory.resolve())
    except OSError:
        resolved = declared

    if resolved == declared:
        pattern = f":{declared}:"
        guard_pattern = f'*"{pattern}"*'
    else:
        pattern1 = f":{declared}:"
        pattern2 = f":{resolved}:"
        guard_pattern = f'*"{pattern1}"*|*"{pattern2}"*'

    value = f"{declared}${{PATH:+:$PATH}}"
    return f'case ":${{PATH-}}:" in {guard_pattern}) ;; *) export PATH="{value}";;esac'


def managed_block(bin_dirs: list[Path]) -> str:
    """Marker-delimited block exporting each bin dir onto PATH.

    Each directory is emitted as a self-deduping case-guarded line through
    `path_export_guard`, so re-sourcing the block N times adds each directory
    at most once. Paths are double-quoted but not otherwise escaped: they come
    only from the trusted registry and Path.home(), never from user input. Do
    not feed user-supplied paths here without shell-quoting first.
    """
    lines = [_PATH_BEGIN]
    lines.extend(path_export_guard(directory) for directory in bin_dirs)
    lines.append(_PATH_END)
    return "\n".join(lines)


def apply_block(content: str, block: str, begin: str = _PATH_BEGIN, end: str = _PATH_END) -> str:
    """Replace an existing begin..end block in content, else append it. Idempotent.

    Pairs the LAST begin marker with the following end marker, so re-applying to a
    file that has an orphan begin (no end) replaces only the well-formed block and
    never eats user content between the orphan marker and the managed block.
    """
    lines = content.split("\n")
    if begin in lines:
        start = max(index for index, line in enumerate(lines) if line == begin)
        for stop in range(start, len(lines)):
            if lines[stop] == end:
                merged = lines[:start] + block.split("\n") + lines[stop + 1 :]
                return "\n".join(merged)
    base = content.rstrip("\n")
    if base:
        return f"{base}\n\n{block}\n"
    return f"{block}\n"


def strip_block(content: str, begin: str, end: str) -> str:
    """Return content with the last begin..end block removed; unchanged if absent.

    Mirrors apply_block's last-begin pairing, so an orphan begin (no matching
    end) is left untouched rather than eating the rest of the file.
    """
    lines = content.split("\n")
    if begin not in lines:
        return content
    start = max(index for index, line in enumerate(lines) if line == begin)
    for stop in range(start, len(lines)):
        if lines[stop] == end:
            return "\n".join(lines[:start] + lines[stop + 1 :])
    return content


def remove_managed_block(path: Path) -> None:
    """Strip the managed PATH block from `path`, preserving the rest. Idempotent.

    A missing file, or a file without the block, is left untouched.
    """
    if not path.exists():
        return
    original = path.read_text()
    stripped = strip_block(original, _PATH_BEGIN, _PATH_END)
    if stripped != original:
        atomic_write_text(path, stripped)


def has_managed_block(path: Path) -> bool:
    """True when `path` exists and contains the managed PATH block begin marker."""
    if not path.exists():
        return False
    lines = path.read_text().split("\n")
    return _PATH_BEGIN in lines


def write_myshellrc(bin_dirs: list[Path], path: Path) -> None:
    """Idempotently write the managed PATH block into ~/.myshellrc, preserving the rest."""
    existing = path.read_text() if path.exists() else ""
    atomic_write_text(path, apply_block(existing, managed_block(bin_dirs)))


def write_managed_path(rc_path: Path, bin_dirs: list[Path]) -> None:
    """Write the managed PATH block directly into an rc file (split-inline mode).

    Idempotent: only the marked block is rewritten, surrounding user content is
    preserved. Used when the user opts out of the ~/.myshellrc indirection.
    """
    existing = rc_path.read_text() if rc_path.exists() else ""
    atomic_write_text(rc_path, apply_block(existing, managed_block(bin_dirs)))


def ensure_source(rc_path: Path, myshellrc_path: Path) -> None:
    """Ensure rc_path sources ~/.myshellrc via a marker block, without duplicating it."""
    block = "\n".join(
        [
            _SOURCE_BEGIN,
            f'[ -f "{myshellrc_path}" ] && . "{myshellrc_path}"',
            _SOURCE_END,
        ]
    )
    existing = rc_path.read_text() if rc_path.exists() else ""
    atomic_write_text(rc_path, apply_block(existing, block, begin=_SOURCE_BEGIN, end=_SOURCE_END))


def consolidation_block(body: str) -> str:
    """The foreign shellrc content wrapped in this project's own marker pair.

    Uses its own markers, never the PATH block's, so foreign content can never
    land inside the span `write_myshellrc` rewrites, and re-applying the block
    is idempotent by construction. The provenance comment carries no timestamp,
    hostname or other varying value: a repeat run must produce a byte-identical
    block or idempotency is lost.
    """
    lines = [
        _SHELLRC_BEGIN,
        "# Content consolidated from the generic ~/.shellrc by tools-installer.",
        "# The original file now sources this file; edit the content here.",
        *body.split("\n"),
        _SHELLRC_END,
    ]
    return "\n".join(lines)


def consolidation_stub(myshellrc_path: Path) -> str:
    """The marked stub that replaces ~/.shellrc and sources ~/.myshellrc.

    Mirrors `ensure_source`'s existing `[ -f ... ] && . ...` idiom. The marker
    is what makes the stub recognizable on the next run, so a completed run is
    never re-consolidated.
    """
    return "\n".join(
        [
            _STUB_BEGIN,
            "# tools-installer consolidated this file; edit ~/.myshellrc instead.",
            f'[ -f "{myshellrc_path}" ] && . "{myshellrc_path}"',
            _STUB_END,
        ]
    )


_Status = Literal["absent", "already", "refused", "consolidated"]


@dataclass(frozen=True)
class ShellrcConsolidation:
    """The outcome of one `consolidate_shellrc` call.

    `reason` is populated only by the refusal outcome. A `Literal` status keeps
    the four local values typed without adding a module-wide enum.
    """

    status: _Status
    reason: str | None = None


class ShellrcRefusal(RuntimeError):
    """A typed, catchable refusal raised by callers of `consolidate_shellrc`.

    Nothing in this module raises it: it is defined here because the reason
    strings it will carry are produced here. Plan 15.8-06 raises it from the
    Doctor apply route and widens `installer/ui_common.py::run_live` to catch
    it, so a refusal can never be reported to the user as success.
    """


@dataclass(frozen=True)
class _Snapshot:
    """One identity-bound read of ~/.shellrc.

    `data` and `(device, inode)` come from the same `O_RDONLY|O_NOFOLLOW`
    descriptor, so they describe the SAME file even if the path is replaced
    mid-call. `mode` is the `S_IMODE` the backup's own permissions copy.
    """

    data: bytes
    device: int
    inode: int
    mode: int


def consolidation_precondition(shellrc_path: Path, myshellrc_path: Path) -> str | None:
    """A refusal reason, or None, when neither path is a hazard.

    Answers exactly ONE question: could a write aimed at one of these two paths
    land on a different file? This project's atomic writer resolves a symlinked
    target rather than replacing the symlink (`installer/atomic.py:42`) -- which
    is correct for a dotfile this project owns, and destructive for a foreign
    file it is about to replace.

    The backup's usability is deliberately NOT checked here: it is a separate
    helper that runs after the owned-stub check and needs a snapshot the caller
    has not taken yet. Nothing may move it back into this function.
    """
    if shellrc_path.is_symlink():
        return (
            f"{shellrc_path} is a symlink; a stub write would follow it and replace its "
            f"target because this project's atomic writer resolves a symlinked target by "
            f"design. Remove the link or consolidate by hand."
        )
    if myshellrc_path.is_symlink():
        return (
            f"{myshellrc_path} is a symlink; writing the consolidated content through it "
            f"would replace its target. Remove the link or consolidate by hand."
        )
    if shellrc_path.exists() and myshellrc_path.exists():
        try:
            same = shellrc_path.samefile(myshellrc_path)
        except OSError:
            # An unanswerable comparison is a refusal, never permission.
            return (
                f"{shellrc_path} and {myshellrc_path} could not be compared; refusing "
                f"rather than guessing whether they are one file."
            )
        if same:
            return (
                f"{shellrc_path} and {myshellrc_path} already refer to one file; there is "
                f"nothing to consolidate and a stub would make it source itself."
            )
    if os.path.realpath(shellrc_path) == os.path.realpath(myshellrc_path):
        return (
            f"{shellrc_path} and {myshellrc_path} resolve to one file; there is nothing "
            f"to consolidate and a stub would make it source itself."
        )
    return None


def _snapshot(path: Path) -> _Snapshot:
    """Read path through one `O_RDONLY|O_NOFOLLOW` descriptor, binding bytes to identity."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        data = b""
        while chunk := os.read(fd, 65536):
            data += chunk
    finally:
        os.close(fd)
    return _Snapshot(data=data, device=st.st_dev, inode=st.st_ino, mode=stat.S_IMODE(st.st_mode))


def _snapshot_matches(path: Path, snapshot: _Snapshot) -> bool:
    """Whether path still has the snapshot's identity AND bytes.

    Any `OSError` from the re-open (removed, or became a symlink) returns False:
    an unanswerable comparison is a refusal, never permission.
    """
    try:
        current = _snapshot(path)
    except OSError:
        return False
    return (
        current.device == snapshot.device
        and current.inode == snapshot.inode
        and (current.data == snapshot.data)
    )


def backup_precondition(shellrc_path: Path, snapshot: _Snapshot) -> str | None:
    """A refusal reason, or None, for an existing backup at OLD_SUFFIX.

    Takes the STEP-3 snapshot rather than re-reading `shellrc_path`, so the bytes
    the backup is compared against and the bytes it is written from are provably
    the same bytes. It is called only AFTER the owned-stub check, so the snapshot
    it sees is guaranteed NOT to be this project's own stub: after a successful
    run the backup holds the ORIGINAL while ~/.shellrc holds the stub, and that
    expected difference must never read as a stale backup.
    """
    backup = staged_sibling(shellrc_path, OLD_SUFFIX)
    try:
        st = os.lstat(backup)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(st.st_mode):
        return (
            f"{backup} is not a plain file; it must be a regular file because it is what a "
            f"restoring `mv` will move back."
        )
    try:
        fd = os.open(backup, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return f"{backup} could not be opened safely; refusing rather than guessing what it is."
    try:
        existing = b""
        while chunk := os.read(fd, 65536):
            existing += chunk
    finally:
        os.close(fd)
    if existing != snapshot.data:
        return (
            f"{backup} already holds a different original; move or remove it if you want "
            f"consolidation to proceed."
        )
    if stat.S_IMODE(st.st_mode) != snapshot.mode:
        return (
            f"{backup} has mode {stat.S_IMODE(st.st_mode):04o} but the original had mode "
            f"{snapshot.mode:04o}; a byte-and-mode restoration cannot be promised, so this "
            f"is refused."
        )
    return None


def _is_owned_stub(text: str) -> bool:
    """True when text is a WELL-FORMED stub this project wrote.

    Both markers must be present with the begin before the end. A file carrying
    only one marker is half-written or hand-edited and deliberately does NOT
    report as already consolidated.
    """
    lines = text.split("\n")
    if _STUB_BEGIN not in lines or _STUB_END not in lines:
        return False
    return lines.index(_STUB_BEGIN) < lines.index(_STUB_END)


def consolidate_shellrc(shellrc_path: Path, myshellrc_path: Path) -> ShellrcConsolidation:
    """Consolidate a generic ~/.shellrc into ~/.myshellrc, leaving one canonical file.

    The CHECK order is FIXED and may not be re-ordered: (1) absence, (2) symlink
    / same-file hazards, (3) identity-bound snapshot and UTF-8 decode, (4) owned
    stub returning `already`, (5) backup validation against a snapshot guaranteed
    not to be a stub, then the writes. Validating the backup before step 4 breaks
    idempotency: after a successful run the backup holds the ORIGINAL while
    ~/.shellrc holds the stub, so a bytes comparison at that point always differs
    and every repeat run would refuse instead of returning `already`.

    The WRITE order is copy-forward, then backup, then stub. It is the inversion
    of omz.py's record-before-write and is deliberate: the only write that REMOVES
    a copy of the content is the stub, and it is last, so every intermediate crash
    state has the content in at least two places and the next run re-applies the
    same idempotent block. No rollback branch is needed for the crash case because
    the failure state is already the safe one.

    The backup makes D-04's recorded reversibility something the user can act on
    with a single `mv`: it holds the original's raw BYTES and mode, was created
    no-clobber, and a mismatching pre-existing backup refuses the whole operation
    rather than being preserved alongside a replacement the user cannot undo.

    ~/.shellrc is foreign by construction and is only ever read as opaque bytes --
    never sourced, evaluated, or executed, not even to inspect it. ~/.myshellrc is
    the only file this project owns and edits.
    """
    if not shellrc_path.exists():
        # `exists()` follows links, so a dangling link is not a file to consolidate.
        return ShellrcConsolidation(status="absent")

    hazard = consolidation_precondition(shellrc_path, myshellrc_path)
    if hazard is not None:
        return ShellrcConsolidation(status="refused", reason=hazard)

    try:
        snapshot = _snapshot(shellrc_path)
    except OSError as exc:
        return ShellrcConsolidation(
            status="refused", reason=f"{shellrc_path} could not be read: {exc}"
        )

    try:
        original_text = snapshot.data.decode("utf-8")
    except UnicodeDecodeError:
        return ShellrcConsolidation(
            status="refused",
            reason=(
                f"{shellrc_path} is not valid UTF-8; refusing to rewrite it. "
                f"Consolidate it by hand."
            ),
        )

    if _is_owned_stub(original_text):
        return ShellrcConsolidation(status="already")

    conflict = backup_precondition(shellrc_path, snapshot)
    if conflict is not None:
        return ShellrcConsolidation(status="refused", reason=conflict)

    pre_myshellrc_bytes = myshellrc_path.read_bytes() if myshellrc_path.exists() else None
    existing = pre_myshellrc_bytes.decode("utf-8") if pre_myshellrc_bytes is not None else ""
    merged = apply_block(
        existing,
        consolidation_block(original_text),
        begin=_SHELLRC_BEGIN,
        end=_SHELLRC_END,
    )
    atomic_write_text(myshellrc_path, merged)

    backup = staged_sibling(shellrc_path, OLD_SUFFIX)
    created_backup = False
    if not backup.exists():
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, snapshot.data)
        finally:
            os.close(fd)
        os.chmod(backup, snapshot.mode)
        created_backup = True

    if not _snapshot_matches(shellrc_path, snapshot):
        if pre_myshellrc_bytes is None:
            myshellrc_path.unlink(missing_ok=True)
        else:
            atomic_write_bytes(myshellrc_path, pre_myshellrc_bytes)
        if created_backup:
            backup.unlink(missing_ok=True)
        return ShellrcConsolidation(
            status="refused",
            reason=(
                f"{shellrc_path} changed while it was being consolidated; nothing was "
                f"replaced. Re-run once the file is settled."
            ),
        )

    atomic_write_text(shellrc_path, consolidation_stub(myshellrc_path))
    return ShellrcConsolidation(status="consolidated")
