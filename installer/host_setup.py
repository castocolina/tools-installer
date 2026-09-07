"""Closed registry of reviewed console handoffs for interactive host setup.

Registry TOML names one ``setup_id``; it never supplies shell text or argv.
These setup flows need a terminal or a user-selected project. The installer
therefore displays reviewed commands to run after leaving Textual and never
launches them from its worker thread.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HostProbe:
    argv: tuple[str, ...]
    contains: str | None


@dataclass(frozen=True)
class HostSetup:
    handoff: tuple[str, ...]
    probes: tuple[HostProbe, ...]
    owner: str
    approval_disclosures: tuple[str, ...] = ()
    requires_project_target: bool = False


HOST_SETUPS: dict[str, HostSetup] = {
    "pi": HostSetup(
        handoff=(
            "After leaving the installer, run these Pi setup commands in a console:",
            "pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent",
            "pi",
        ),
        probes=(
            HostProbe(
                ("pnpm", "list", "--global", "--depth", "0", "--json"),
                "@earendil-works/pi-coding-agent",
            ),
        ),
        owner="pnpm",
    ),
}

HOST_SETUP_IDS = tuple(HOST_SETUPS)
