"""Userspace install-location policy: binaries land under ~/.local/bin, no sudo."""

import os
from pathlib import Path


def bin_dir(declared: str | None) -> Path:
    """Resolve a method's bin dir. Defaults to ~/.local/bin; expands a leading ~."""
    if declared:
        return Path(declared).expanduser()
    return Path.home() / ".local" / "bin"


def opt_dir(name: str) -> Path:
    """Resolve the userspace opt dir for an unpacked app: ~/.local/opt/<name>."""
    return Path.home() / ".local" / "opt" / name


def applications_dir() -> Path:
    """The userspace Applications dir for macOS GUI apps: ~/Applications."""
    return Path.home() / "Applications"


def rc_paths_for_mode(link_mode: str, shell: str) -> list[Path]:
    """The shell rc files PATH wiring writes to under `link_mode`. Centralized
    and split wire both defaults; single wires only the rc of `shell` — both
    when the shell is undetectable."""
    home = Path.home()
    both = [home / ".zshrc", home / ".bashrc"]
    if link_mode != "single":
        return both
    if shell.endswith("zsh"):
        return [home / ".zshrc"]
    if shell.endswith("bash"):
        return [home / ".bashrc"]
    return both  # undetectable shell -> wire both


def ban_rc_paths(link_mode: str, shell: str) -> list[Path]:
    """Where to WRITE ban aliases, following the PATH model: centralized/single
    keep one ~/.myshellrc; split writes into each rc file directly."""
    if link_mode == "split":
        return rc_paths_for_mode(link_mode, shell)
    return [Path.home() / ".myshellrc"]


def all_ban_rc_paths() -> list[Path]:
    """Where to REMOVE aliases from: every file an install could have written to,
    across all link modes. remove_ban_aliases is a no-op where the block is
    absent, so removal needs no link-mode guess (which would otherwise strand
    aliases when the user picks a different mode than they installed with)."""
    home = Path.home()
    return [home / ".myshellrc", home / ".zshrc", home / ".bashrc"]


def ensure_dir(directory: Path) -> Path:
    """Create the directory (and parents) if missing. Returns it."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def prepend_path(directory: Path) -> None:
    """Put `directory` first on the process PATH, without duplicating it."""
    entry = str(directory)
    parts = os.environ.get("PATH", "").split(os.pathsep)
    parts = [p for p in parts if p and p != entry]
    os.environ["PATH"] = os.pathsep.join([entry, *parts])
