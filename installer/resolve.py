"""Resolve which install methods apply to a platform, ordered by the priority ladder."""

from dataclasses import replace

from installer.model import Method, Tool
from installer.platform import Platform
from installer.versions import meets_minimum

# Lower rank is tried first. The default ladder:
#   1) official script  2) userspace install (download/node/sdkman)
#   3) native pkg manager  4) brew/cask
_RANK = {
    "script": 10,
    "host_setup": 15,
    "skill_pack": 15,
    "github_release": 20,
    "node": 20,
    "uv-tool": 20,
    "sdkman": 20,
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
    min_version = method.params.get("min_os_version")
    if min_version is not None and not (
        platform.os_version is not None and meets_minimum(platform.os_version, str(min_version))
    ):
        return False
    kind = method.kind
    # uv-tool is a userspace install this project's own toolchain (uv) performs,
    # gated by whether uv itself is present -- a fact installer/deps.py's
    # requires = ["uv"] edge already carries, not a platform fact this function
    # should re-derive; mirrors node's and sdkman's unconditional-True treatment.
    if kind in (
        "script",
        "node",
        "sdkman",
        "github_release",
        "tarball",
        "app",
        "uv-tool",
        "host_setup",
        "skill_pack",
    ):
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


def platform_could_support(tool: Tool, platform: Platform) -> bool:
    """True when some method would apply here once Homebrew is present.

    Distinguishes a genuine platform incompatibility (wrong os/arch, or a macOS
    version below a method's own min_os_version floor — never installable here,
    regardless of what the user does next) from a merely-not-yet-bootstrapped
    machine (Homebrew absent right now — becomes installable after the user
    installs it, via this registry's own brew catalog entry, in this run or a
    later one).

    resolve_methods itself remains a literal "applies right now" answer for the
    CLI/install-time path (install_tool's NO_METHOD, resolve_dependencies' per-run
    availability gate) — unchanged. This predicate is a browsing-time-only signal
    a UI can use to distinguish "will never work here" from "works once a
    prerequisite step runs."

    This is NOT the same expression installer/uninstall.py::classify_tools uses
    for UninstallState.UNAVAILABLE: classify_tools answers a narrower,
    Uninstall-specific question (already excludes removable/managed/installed
    tools before ever reaching a resolve_methods check). This answers "could
    this tool EVER install here, once Homebrew is present" and is deliberately
    has_brew-blind for exactly the reason classify_tools' check is not.
    Related (both call resolve_methods), not identical.
    """
    return bool(resolve_methods(tool, replace(platform, has_brew=True)))
