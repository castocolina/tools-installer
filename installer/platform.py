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
    # Raw major[.minor[.patch]] string (e.g. "26.0.1"), populated only on Darwin.
    # Sole consumer: a method's optional min_os_version gate in resolve._applies.
    # Comparison is installer.versions.meets_minimum; this module does no parsing.
    os_version: str | None = None
    # distrobox and podman on PATH, re-read every version pass like has_brew. The
    # cargo_distrobox kind needs both (resolve._applies); defaults keep older constructions valid.
    has_distrobox: bool = False
    has_podman: bool = False
    # The system `node` the version pass saw (e.g. "22.12.0", a prerelease keeps its suffix); None
    # when absent or unread. detect() leaves it None: no child process at start-up. Sole
    # consumer: a node method's `min_node` floor in resolve._applies.
    node_version: str | None = None


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

    system = stdlib_platform.system()
    return Platform(
        os=detect_os(system, available),
        arch=normalize_arch(stdlib_platform.machine()),
        immutable=detect_immutable(),
        has_brew=available("brew"),
        has_distrobox=available("distrobox"),
        has_podman=available("podman"),
        os_version=(stdlib_platform.mac_ver()[0] or None) if system == "Darwin" else None,
    )
