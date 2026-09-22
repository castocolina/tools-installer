"""Manage ~/.myshellrc as one marker-delimited PATH block, and wire `source` into rc files.

Every write is idempotent: only the marked block is ever rewritten, user content is
preserved, and entries are never duplicated across runs. Every write in this module
goes through installer/atomic.py, because a truncated rc file is unrecoverable and
these files are edited read-modify-write.
"""

from collections.abc import Callable
from pathlib import Path

from installer.model import Tool
from installer.platform import Platform
from installer.resolve import resolve_methods

_PATH_BEGIN = "# >>> tools-installer path >>>"
_PATH_END = "# <<< tools-installer path <<<"
_SOURCE_BEGIN = "# >>> tools-installer source >>>"
_SOURCE_END = "# <<< tools-installer source <<<"


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
        path.write_text(stripped)


def has_managed_block(path: Path) -> bool:
    """True when `path` exists and contains the managed PATH block begin marker."""
    if not path.exists():
        return False
    lines = path.read_text().split("\n")
    return _PATH_BEGIN in lines


def write_myshellrc(bin_dirs: list[Path], path: Path) -> None:
    """Idempotently write the managed PATH block into ~/.myshellrc, preserving the rest."""
    existing = path.read_text() if path.exists() else ""
    path.write_text(apply_block(existing, managed_block(bin_dirs)))


def write_managed_path(rc_path: Path, bin_dirs: list[Path]) -> None:
    """Write the managed PATH block directly into an rc file (split-inline mode).

    Idempotent: only the marked block is rewritten, surrounding user content is
    preserved. Used when the user opts out of the ~/.myshellrc indirection.
    """
    existing = rc_path.read_text() if rc_path.exists() else ""
    rc_path.write_text(apply_block(existing, managed_block(bin_dirs)))


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
    rc_path.write_text(apply_block(existing, block, begin=_SOURCE_BEGIN, end=_SOURCE_END))

