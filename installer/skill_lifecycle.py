"""Typed install, status, update, and removal behavior for skill packs."""

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from installer.model import SKILL_HARNESSES, SkillLifecycle, SkillOperation, SkillStatusProbe, Tool
from installer.run import Runner

LifecycleAction = Literal["install", "update", "removal"]
LifecycleStatus = Literal["completed", "manual-required", "present", "absent", "unknown"]
HarnessStatus = Literal["present", "absent", "unknown"]
ProbeRunner = Callable[[list[str]], str]


@dataclass(frozen=True)
class LifecycleOutcome:
    status: LifecycleStatus
    instructions: tuple[str, ...] = ()


@dataclass(frozen=True)
class HarnessCli:
    argv: tuple[str, ...]
    matches: Callable[[str, str], bool]


def _claude_matches(output: str, match: str) -> bool:
    prefix = f"{match}@"
    for line in output.splitlines():
        text = line.strip()
        if text.startswith("❯"):
            text = text[1:].lstrip()
        if text.startswith(prefix):
            return True
    return False


def _codex_matches(output: str, match: str) -> bool:
    prefix = f"{match}@"
    for line in output.splitlines():
        parts = line.split(None, 1)
        if not parts:
            continue
        token = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        if token.startswith(prefix) and rest.strip().startswith("installed"):
            return True
    return False


def _pi_matches(output: str, match: str) -> bool:
    for line in output.splitlines():
        text = line.strip()
        if text == match or text.endswith(f"/{match}") or text.endswith(f":{match}"):
            return True
    return False


HARNESS_CLI_STATUS: dict[str, HarnessCli] = {
    "claude": HarnessCli(("claude", "plugin", "list"), _claude_matches),
    "codex": HarnessCli(("codex", "plugin", "list"), _codex_matches),
    "pi": HarnessCli(("pi", "list"), _pi_matches),
}


def _lifecycle(tool: Tool) -> SkillLifecycle:
    lifecycle = tool.skill_lifecycle
    if lifecycle is None:
        raise ValueError(f"tool '{tool.id}' is not a skill pack")
    return lifecycle


def _operation(lifecycle: SkillLifecycle, action: LifecycleAction) -> SkillOperation:
    if action == "install":
        return lifecycle.install
    if action == "update":
        return lifecycle.update
    return lifecycle.removal


def perform_action(tool: Tool, action: LifecycleAction, runner: Runner) -> LifecycleOutcome:
    """Execute one closed lifecycle operation or return its reviewed handoff."""
    operation = _operation(_lifecycle(tool), action)
    if operation.mode == "manual-required":
        return LifecycleOutcome("manual-required", operation.instructions)
    raise ValueError(f"no reviewed executable lifecycle operation for '{action}'")


def _needed_argvs(tools: Sequence[Tool]) -> tuple[tuple[str, ...], ...]:
    needed: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for tool in tools:
        lifecycle = tool.skill_lifecycle
        if lifecycle is None:
            continue
        for status_probe in lifecycle.status_probes:
            if status_probe.via != "plugin-cli":
                continue
            cli = HARNESS_CLI_STATUS.get(status_probe.harness)
            if cli is None or cli.argv in seen:
                continue
            seen.add(cli.argv)
            needed.append(cli.argv)
    return tuple(needed)


def _probe_outputs(
    argvs: tuple[tuple[str, ...], ...], probe: ProbeRunner
) -> dict[tuple[str, ...], str | None]:
    outputs: dict[tuple[str, ...], str | None] = {}
    for argv in argvs:
        try:
            outputs[argv] = probe(list(argv))
        except (OSError, RuntimeError, subprocess.SubprocessError):
            outputs[argv] = None
    return outputs


def _harness_status(
    status_probe: SkillStatusProbe, outputs: dict[tuple[str, ...], str | None]
) -> HarnessStatus:
    if status_probe.via != "plugin-cli":
        return "unknown"
    cli = HARNESS_CLI_STATUS.get(status_probe.harness)
    if cli is None:
        return "unknown"
    output = outputs.get(cli.argv)
    if output is None:
        return "unknown"
    return "present" if cli.matches(output, status_probe.match) else "absent"


def _pack_status(
    lifecycle: SkillLifecycle, outputs: dict[tuple[str, ...], str | None]
) -> dict[str, HarnessStatus]:
    by_harness = {status_probe.harness: status_probe for status_probe in lifecycle.status_probes}
    return {
        harness: _harness_status(by_harness[harness], outputs)
        for harness in SKILL_HARNESSES
        if harness in by_harness
    }


def inspect_skill_packs(
    tools: Sequence[Tool], probe: ProbeRunner, home: Path
) -> dict[str, dict[str, HarnessStatus]]:
    """Probe each distinct harness CLI once and report present, absent, or unknown."""
    del home
    outputs = _probe_outputs(_needed_argvs(tools), probe)
    return {
        tool.id: {} if tool.skill_lifecycle is None else _pack_status(tool.skill_lifecycle, outputs)
        for tool in tools
    }


def inspect_status(tool: Tool, probe: ProbeRunner, home: Path | None = None) -> LifecycleOutcome:
    """Probe a pack without acquiring software, or fail closed to manual status."""
    lifecycle = _lifecycle(tool)
    hosts = inspect_skill_packs((tool,), probe, Path.home() if home is None else home)[tool.id]
    if any(status == "present" for status in hosts.values()):
        return LifecycleOutcome("present")
    if not lifecycle.status_probes:
        return LifecycleOutcome("manual-required", lifecycle.status.instructions)
    if hosts and all(status == "absent" for status in hosts.values()):
        return LifecycleOutcome("absent")
    return LifecycleOutcome("unknown")
