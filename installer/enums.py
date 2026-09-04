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


class InstallStatus(StrEnum):
    """Outcomes produced by the install engine."""

    ALREADY_INSTALLED = "already-installed"
    INSTALLED = "installed"
    NO_METHOD = "no-method"
    FAILED = "failed"
    CHECKSUM_MISMATCH = "checksum-mismatch"


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
