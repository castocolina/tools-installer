"""Closed value sets shared by the catalog model and UI state."""

from enum import StrEnum


class Priority(StrEnum):
    """Catalog install priority."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Audience(StrEnum):
    """Who primarily benefits from a catalog tool."""

    AI = "ai"
    BOTH = "both"
    HUMAN = "human"


class Tier(StrEnum):
    """Bootstrap-order / top-level view a tool belongs to."""

    SYSTEM = "system"
    USER = "user"
    AI = "ai"


class Category(StrEnum):
    """Registry category ids declared in registry.toml."""

    PACKAGE_MANAGER = "pkg-mgr"
    SEARCH = "search"
    DATA = "data"
    VIEW = "view"
    TEXT = "text"
    GIT = "git"
    NAVIGATION = "nav"
    SHELL = "shell"
    DEVELOPMENT = "dev"
    SYSTEM_INFO = "sysinfo"
    NETWORK = "net"
    CONTAINER = "docker"
    AI = "ai"
    RUNTIME = "runtime"
    SECURITY = "security"
    EDITOR = "editor"
    DIAGRAM = "diagram"
    TERMINAL = "terminal"


class InstallStatus(StrEnum):
    """Outcomes produced by the install engine."""

    ALREADY_INSTALLED = "already-installed"
    INSTALLED = "installed"
    NO_METHOD = "no-method"
    FAILED = "failed"
    CHECKSUM_MISMATCH = "checksum-mismatch"
    # A method (host_setup or skill_pack) that hands the user reviewed console
    # instructions to run after the installer releases the terminal, rather
    # than performing the install itself.
    MANUAL_REQUIRED = "manual-required"
    # Not attempted: a required tool did not resolve earlier in this run.
    # Distinct from FAILED, which means it WAS attempted and every method lost.
    DEPENDENCY_FAILED = "dependency-failed"


class UninstallState(StrEnum):
    """Removability states shown by the uninstall view."""

    REMOVABLE = "removable"
    MANAGED = "managed"
    ABSENT = "absent"
    UNAVAILABLE = "unavailable"


class Severity(StrEnum):
    """Guidance and status-line severity."""

    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class DaemonState(StrEnum):
    """Runtime-truthful answer to "is the managed background cleanup running".

    Closed three-member vocabulary shared by installer/systemd_daemon.py (this
    phase) and installer/diskusage.py (plan 15.7-02) so both consume the same
    fact rather than each declaring their own -- it lives here, not in the
    Linux-only backend module, because a Doctor-facing disk-pressure probe
    must never import a Linux-only backend module just to get this vocabulary.

    UNAVAILABLE means "this machine has no managed background cleanup we can
    confirm" -- a host with no systemd, or one whose state query could not be
    answered -- and is deliberately NOT the same fact as INACTIVE, because the
    two want different user advice (plan 15.7-02 D-03c): INACTIVE says "you
    have this capability and it is off", UNAVAILABLE says "this machine has
    nothing to turn on".
    """

    ACTIVE = "active"
    INACTIVE = "inactive"
    UNAVAILABLE = "unavailable"
