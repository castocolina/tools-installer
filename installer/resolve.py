"""Resolve which install methods apply to a platform, ordered by the priority ladder."""

from installer.model import Method, Tool
from installer.platform import Platform

# Lower rank is tried first. The default ladder:
#   1) official script  2) userspace download  3) native pkg manager  4) brew/cask
_RANK = {
    "script": 10,
    "github_release": 20,
    "tarball": 20,
    "app": 20,
    "dnf": 30,
    "apt": 30,
    "pacman": 30,
    "rpm_ostree": 35,
    "brew": 40,
    "cask": 40,
}

# Which OS each native package manager belongs to.
_NATIVE_OS = {
    "dnf": "fedora",
    "apt": "debian",
    "pacman": "arch",
}


def _applies(method: Method, platform: Platform) -> bool:
    if method.os and platform.os not in method.os:
        return False
    if method.arch and platform.arch not in method.arch:
        return False
    kind = method.kind
    if kind in ("script", "github_release", "tarball", "app"):
        return True
    if kind == "brew":
        return platform.has_brew
    if kind == "cask":
        # Casks are a macOS-only brew concept; --appdir keeps them in ~/Applications.
        return platform.os == "macos" and platform.has_brew
    if kind == "rpm_ostree":
        # Native installer for immutable Fedora, but skipped by default: it
        # requires a reboot and breaks atomicity. Userspace/brew are preferred.
        return False
    # Remaining kinds are native package managers (dnf/apt/pacman).
    if platform.immutable:
        return False  # skip the native step on immutable distros
    return _NATIVE_OS[kind] == platform.os


def resolve_methods(tool: Tool, platform: Platform) -> list[Method]:
    """Return the tool's platform-applicable methods, ordered by the priority ladder."""
    applicable = [m for m in tool.methods if _applies(m, platform)]
    return sorted(applicable, key=lambda m: _RANK[m.kind])
