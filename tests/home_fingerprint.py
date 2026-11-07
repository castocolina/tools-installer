"""Metadata-only snapshot of a home directory: the net under the test suite.

Existence, directory listings (`os.listdir`) and mtimes (`os.lstat` / `os.stat`) only.
No file is opened, read or hashed: the watched agent and toolchain dirs hold credentials.
"""

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

GUARDED_DOTFILES: tuple[str, ...] = (
    ".myshellrc",
    ".shellrc",
    ".bashrc",
    ".zshrc",
    ".zshenv",
    ".profile",
)

# Home-relative directories and entries: the SPEC R9 agent, service and bin dirs,
# then the three installer listings (receipts, environment.d, config ledger).
WATCHED_DIRS: tuple[str, ...] = (
    ".claude/gsd-core",
    ".claude/.gsd-source",
    ".claude/gsd-file-manifest.json",
    ".claude/agents",
    ".claude/commands",
    ".claude/hooks",
    ".gsd",
    ".agents",
    ".codex",
    ".cursor",
    ".config/opencode",
    ".local/bin",
    ".local/opt",
    ".config/systemd/user",
    ".oh-my-zsh",
    ".local/state/tools-installer/receipts",
    ".config/environment.d",
    ".local/state/tools-installer/config",
)

BACKUP_SUFFIX = ".tools-installer.old"
BACKUP_LABEL = f"~/*{BACKUP_SUFFIX}"


@dataclass(frozen=True)
class PathState:
    # Directory listing as raw names; None for a non-directory or an unreadable directory.
    entries: frozenset[str] | None
    mtime_ns: int
    # Set for the rc dotfiles only, which are compared by size as well.
    size: int | None = None


def toolchain_dirs(home: Path, overrides: Mapping[str, str | None]) -> tuple[Path, Path, Path]:
    """uv tools, pnpm global and Volta tools dirs, from the import-time overrides when set."""
    uv = overrides.get("UV_TOOL_DIR")
    pnpm = overrides.get("PNPM_HOME")
    volta = overrides.get("VOLTA_HOME")
    return (
        Path(uv) if uv else home / ".local" / "share" / "uv" / "tools",
        Path(pnpm) if pnpm else home / ".local" / "share" / "pnpm",
        Path(volta) / "tools" if volta else home / ".volta" / "tools",
    )


def _label(home: Path, path: Path) -> str:
    if path.is_relative_to(home):
        return f"~/{path.relative_to(home).as_posix()}"
    return str(path)


def watched_paths(home: Path, overrides: Mapping[str, str | None]) -> dict[str, Path]:
    """Label -> path for every watched directory and entry (dotfiles are added by `fingerprint`).

    A path reached twice (an override pointing at a watched dir) is one key.
    """
    paths = [*(home / rel for rel in WATCHED_DIRS), *toolchain_dirs(home, overrides)]
    watched: dict[str, Path] = {}
    for path in paths:
        normal = Path(os.path.normpath(path))
        watched[_label(home, normal)] = normal
    return watched


def _dotfile(path: Path) -> PathState | None:
    # `stat` follows a symlinked rc, as the old fingerprint did.
    try:
        info = os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    return PathState(entries=None, mtime_ns=info.st_mtime_ns, size=info.st_size)


def _entry(path: Path) -> PathState | None:
    # `lstat` so a symlink is compared as itself, never as its target's listing.
    try:
        info = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    if not stat.S_ISDIR(info.st_mode):
        return PathState(entries=None, mtime_ns=info.st_mtime_ns)
    try:
        names: frozenset[str] | None = frozenset(os.listdir(path))
    except PermissionError:
        names = None
    return PathState(entries=names, mtime_ns=info.st_mtime_ns)


def _backups(home: Path) -> PathState | None:
    # Only the names count: the home's own mtime moves with every write in it.
    try:
        names = os.listdir(home)
    except (FileNotFoundError, NotADirectoryError):
        return None
    backups = frozenset(name for name in names if name.endswith(BACKUP_SUFFIX))
    return PathState(entries=backups, mtime_ns=0)


def fingerprint(home: Path, overrides: Mapping[str, str | None]) -> dict[str, PathState | None]:
    """Label -> state for the dotfiles, the watched paths and the backup names; None when absent."""
    state: dict[str, PathState | None] = {
        f"~/{name}": _dotfile(home / name) for name in GUARDED_DOTFILES
    }
    for label, path in watched_paths(home, overrides).items():
        state[label] = _entry(path)
    state[BACKUP_LABEL] = _backups(home)
    return state


def fingerprint_diff(
    before: Mapping[str, PathState | None], after: Mapping[str, PathState | None]
) -> list[str]:
    """One line per changed label, in sorted order; empty when nothing changed."""
    lines: list[str] = []
    for label in sorted(before.keys() | after.keys()):
        old = before.get(label)
        new = after.get(label)
        if old == new:
            continue
        if old is None:
            lines.append(f"{label}: created")
        elif new is None:
            lines.append(f"{label}: removed")
        elif old.entries is not None and new.entries is not None and old.entries != new.entries:
            added = sorted(new.entries - old.entries)
            removed = sorted(old.entries - new.entries)
            lines.append(f"{label}: added {added!r}, removed {removed!r}")
        else:
            lines.append(f"{label}: changed (mtime or size only)")
    return lines
