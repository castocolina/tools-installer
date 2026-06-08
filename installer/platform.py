"""OS, architecture, and immutability detection for install-strategy selection."""

import platform as stdlib_platform
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_ARCH_MAP = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}

_OSTREE_MARKER = Path("/run/ostree-booted")


@dataclass(frozen=True)
class Platform:
    os: str  # "debian" | "arch" | "fedora" | "macos"
    arch: str  # "amd64" | "arm64" | raw machine string
    immutable: bool  # atomic/ostree filesystem (Bazzite, Silverblue)
    has_brew: bool


def normalize_arch(machine: str) -> str:
    return _ARCH_MAP.get(machine, machine)


def detect_os(system: str, available: Callable[[str], bool]) -> str:
    """Map (platform.system(), command-availability) to a supported OS key.

    Fedora is probed before debian/arch because immutable Fedora (Bazzite) may
    expose rpm-ostree rather than a usable dnf.
    """
    if system == "Darwin":
        return "macos"
    if available("dnf") or available("rpm-ostree"):
        return "fedora"
    if available("apt-get"):
        return "debian"
    if available("pacman"):
        return "arch"
    raise RuntimeError("Unsupported OS: need macOS, or one of dnf/rpm-ostree, apt-get, pacman")


def detect_immutable(marker: Path = _OSTREE_MARKER) -> bool:
    """True on ostree/atomic systems, detected via the booted marker file."""
    return marker.exists()


def detect() -> Platform:
    """Detect the real platform using live system probes."""

    def available(cmd: str) -> bool:
        return shutil.which(cmd) is not None

    return Platform(
        os=detect_os(stdlib_platform.system(), available),
        arch=normalize_arch(stdlib_platform.machine()),
        immutable=detect_immutable(),
        has_brew=available("brew"),
    )
