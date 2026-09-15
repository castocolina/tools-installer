"""Verified package-manager ownership probes.

Ownership is intentionally not inferred from a resolved executable path. A
manager is reported only after its declared probe returns manager-specific
evidence through the injected command runner.

Probe stdout is untrusted input. The binaries are resolved through the user's
`PATH`, which this installer prepends a managed bin dir to by design, so a
planted or merely corrupted `rpm-ostree`/`pnpm` can put arbitrary bytes on
stdout. Every probe therefore fails CLOSED -- returning `None`, never raising
-- and the JSON guards catch `RecursionError` alongside `TypeError`/
`ValueError`: deeply nested input exhausts the interpreter stack inside
`json.loads` (and, for pnpm, inside the recursive `_pnpm_packages` walk),
and `RecursionError` is neither of the other two. `detect_owner` runs on the
catalog refresh worker, so an escaping exception there is a crashed refresh
rather than an unattributed tool.
"""

import json
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal, cast

from installer.host_setup import HOST_SETUPS
from installer.model import Tool

ProbeRunner = Callable[[list[str]], str]


@dataclass(frozen=True)
class Ownership:
    manager: str | None
    confidence: Literal["verified", "unknown"]
    detail: str


_UNKNOWN = Ownership(None, "unknown", "no verified manager")


def run_probe(command: list[str]) -> str:
    """Run a read-only ownership probe without inheriting the caller's terminal."""
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        stdin=subprocess.DEVNULL,
        timeout=5,
    ).stdout


def _method_values(tool: Tool, kinds: set[str], key: str) -> tuple[str, ...]:
    return tuple(
        value
        for method in tool.methods
        if method.kind in kinds
        if isinstance(value := method.params.get(key), str) and value
    )


def _lines(output: str) -> set[str]:
    return {line.strip() for line in output.splitlines() if line.strip()}


def _run(probe: ProbeRunner, command: list[str]) -> str | None:
    try:
        return probe(command)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return None


def _managed_download(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    if not any(method.kind in {"github_release", "tarball", "app"} for method in tool.methods):
        return None
    output = _run(probe, ["tools-installer-managed-download", "list", tool.id])
    if output is not None and tool.id in _lines(output):
        return Ownership("managed download", "verified", f"managed download lists {tool.id}")
    return None


def _host_setup(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    setup_ids = _method_values(tool, {"host_setup"}, "setup_id")
    for setup_id in setup_ids:
        setup = HOST_SETUPS.get(setup_id)
        if setup is None:
            continue
        for host_probe in setup.probes:
            output = _run(probe, list(host_probe.argv))
            if output is not None and (
                host_probe.contains is None or host_probe.contains in output
            ):
                return Ownership(
                    setup.owner,
                    "verified",
                    f"host setup lists {setup_id}",
                )
    return None


def _brew(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    packages = _method_values(tool, {"brew"}, "formula") + _method_values(tool, {"cask"}, "cask")
    for package in packages:
        output = _run(probe, ["brew", "list", "--versions", package])
        if output is not None and any(
            line.split(maxsplit=1)[0] == package for line in _lines(output)
        ):
            return Ownership("Homebrew", "verified", f"brew lists {package}")
    return None


def _apt(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    for package in _method_values(tool, {"apt"}, "package"):
        output = _run(probe, ["dpkg-query", "-W", "-f=${binary:Package}\\n", package])
        if output is not None and any(
            line.split(":", maxsplit=1)[0] == package for line in _lines(output)
        ):
            return Ownership("apt", "verified", f"apt lists {package}")
    return None


def _dnf(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    for package in _method_values(tool, {"dnf"}, "package"):
        output = _run(probe, ["rpm", "-q", "--qf", "%{NAME}\\n", package])
        if output is not None and package in _lines(output):
            return Ownership("dnf", "verified", f"dnf lists {package}")
    return None


def _rpm_ostree(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    """rpm-ostree/just-layering equivalent of `_dnf`.

    No registry row declares `kind = "rpm_ostree"` for INSTALL: resolve.py's
    `_applies` returns `False` for that kind unconditionally, because a
    layered package needs a reboot and breaks atomicity -- a deliberate,
    documented install-time choice with no bearing on OWNERSHIP. This probe
    answers a different question ("did the user explicitly layer this RPM on
    the booted deployment?"), so it reads the tool's declared `dnf` method's
    package name instead -- rpm-ostree layers RPMs from the same
    Fedora/Bazzite repositories dnf installs from, and inventing a second
    registry field for the same string would be an unrequested schema change.
    Only the BOOTED deployment's `requested-packages` (explicitly layered,
    not merely present in the base image) counts as evidence; a rollback
    target or an older deployment is not the system the user is running.
    """
    packages = _method_values(tool, {"dnf"}, "package")
    if not packages:
        return None
    output = _run(probe, ["rpm-ostree", "status", "--json"])
    if output is None:
        return None
    try:
        parsed = json.loads(output)
    except (TypeError, ValueError, RecursionError):
        return None
    if not isinstance(parsed, dict):
        return None
    deployments = cast(dict[str, object], parsed).get("deployments")
    if not isinstance(deployments, list):
        return None
    booted: dict[str, object] | None = None
    for entry in cast(list[object], deployments):
        if isinstance(entry, dict) and cast(dict[str, object], entry).get("booted") is True:
            booted = cast(dict[str, object], entry)
            break
    if booted is None:
        return None
    layered = booted.get("requested-packages")
    if not isinstance(layered, list):
        return None
    layered_names = cast(list[object], layered)
    for package in packages:
        if package in layered_names:
            return Ownership("rpm-ostree", "verified", f"rpm-ostree layers {package}")
    return None


def _rpm_owns_path(package: str, path: str, probe: ProbeRunner) -> bool:
    output = _run(probe, ["rpm", "-qf", "--qf", "%{NAME}\\n", path])
    return output is not None and package in _lines(output)


def _dpkg_owns_path(package: str, path: str, probe: ProbeRunner) -> bool:
    output = _run(probe, ["dpkg-query", "-S", path])
    return output is not None and any(
        line.split(":", maxsplit=1)[0] == package for line in _lines(output)
    )


def _pacman_owns_path(package: str, path: str, probe: ProbeRunner) -> bool:
    output = _run(probe, ["pacman", "-Qoq", path])
    return output is not None and package in _lines(output)


# Manager -> (the method kind declaring its package name, that manager's own
# "which package owns this file" query). rpm-ostree shares rpm's query and the
# `dnf` method's package name for the same reason `_rpm_ostree` reads that
# method: a layered or base-image RPM lives in the same rpm database.
_PATH_QUERIES: dict[str, tuple[str, Callable[[str, str, ProbeRunner], bool]]] = {
    "dnf": ("dnf", _rpm_owns_path),
    "rpm-ostree": ("dnf", _rpm_owns_path),
    "apt": ("apt", _dpkg_owns_path),
    "pacman": ("pacman", _pacman_owns_path),
}


def package_owns_path(tool: Tool, manager: str, path: str, probe: ProbeRunner) -> bool:
    """True when `manager`'s own file query says a declared package owns `path`.

    "This package is installed" and "this package put the binary the user
    actually runs there" are different claims, and the probes above only make
    the first. `rpm -q jq` succeeds while a hand-built `jq` sits earlier in
    `PATH`, so attributing the live binary to dnf on that evidence tells the
    user the wrong thing about the copy they are running. This is the second
    claim, asked in each manager's own dialect.

    Fails CLOSED in every uncertain case: an unrecognized manager, a tool that
    declares no package name for it, a query that cannot run (`rpm -qf` exits
    non-zero for a file no package owns), and a query that answers with some
    OTHER package's name all return `False`. Confirmation must be positive.
    """
    entry = _PATH_QUERIES.get(manager)
    if entry is None:
        return False
    kind, query = entry
    return any(query(package, path, probe) for package in _method_values(tool, {kind}, "package"))


def _pacman(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    for package in _method_values(tool, {"pacman"}, "package"):
        output = _run(probe, ["pacman", "-Qq", package])
        if output is not None and package in _lines(output):
            return Ownership("pacman", "verified", f"pacman lists {package}")
    return None


def _pnpm_packages(value: object) -> Iterable[str]:
    if isinstance(value, list):
        for entry in cast(list[object], value):
            yield from _pnpm_packages(entry)
    elif isinstance(value, dict):
        row = cast(dict[str, object], value)
        name = row.get("name")
        if isinstance(name, str):
            yield name
        dependencies = row.get("dependencies")
        if isinstance(dependencies, dict):
            yield from cast(dict[str, object], dependencies)


def _pnpm(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    packages = _method_values(tool, {"node"}, "npm_pkg")
    if not packages:
        return None
    output = _run(probe, ["pnpm", "list", "--global", "--depth", "0", "--json"])
    if output is None:
        return None
    try:
        listed = set(_pnpm_packages(json.loads(output)))
    except (TypeError, ValueError, RecursionError):
        return None
    for package in packages:
        if package in listed:
            return Ownership("pnpm", "verified", f"pnpm lists {package}")
    return None


def _sdkman(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    candidates = _method_values(tool, {"script"}, "sdk_candidate") or (tool.id,)
    for candidate in candidates:
        output = _run(probe, ["sdk", "current", candidate])
        if output is not None and f"Using {candidate} version " in output:
            return Ownership("SDKMAN", "verified", f"sdkman lists {candidate}")
    return None


_PROBES: dict[str, Callable[[Tool, ProbeRunner], Ownership | None]] = {
    "managed-download": _managed_download,
    "host-setup": _host_setup,
    "brew": _brew,
    "apt": _apt,
    "dnf": _dnf,
    "pacman": _pacman,
    "rpm-ostree": _rpm_ostree,
    "pnpm": _pnpm,
    "sdkman": _sdkman,
}


# D-06/CR-02: probes that can only speak for a MUTABLE host. On an ostree
# system the booted deployment's rpm database still answers `rpm -q` for every
# package in the base image (`git`, `jq`, `zsh`, `podman` on Bazzite and
# Silverblue), so `_dnf` would claim them -- and the catalog would tell the
# user to "update it through dnf", a command that does not manage that package
# there. Probe ORDERING alone does not fix this: `_rpm_ostree` reports only
# explicitly layered packages, so a base-image package falls straight through
# to `_dnf`. `resolve._applies` already returns False for all three of
# dnf/apt/pacman on an immutable host, for the same reason; attribution now
# agrees with installation. On such a host only `_rpm_ostree`'s
# explicit-layering evidence counts, and a base-image package resolves to "no
# verified manager" -- honest, because this installer cannot manage it either
# way, and a wrong remediation is worse than none.
_MUTABLE_HOST_ONLY_PROBES = frozenset({"dnf", "apt", "pacman"})


def detect_owner(tool: Tool, probe: ProbeRunner, *, immutable: bool) -> Ownership:
    """Return the first declared manager that produces ownership evidence.

    `immutable` is the host's `Platform.immutable`. It is keyword-only and has
    no default on purpose: the wrong value silently mis-attributes every
    base-image package on an atomic host, which is not a failure a caller
    should be able to fall into by omission.
    """
    for name in tool.owner_probes:
        if immutable and name in _MUTABLE_HOST_ONLY_PROBES:
            continue
        owner = _PROBES[name](tool, probe)
        if owner is not None:
            return owner
    return _UNKNOWN
