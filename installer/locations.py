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
