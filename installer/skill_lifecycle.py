"""Typed install, status, update, and removal behavior for skill packs."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from installer.model import (
    CodexPluginStatusArgs,
    PiPackageStatusArgs,
    SkillLifecycle,
    SkillOperation,
    Tool,
)
from installer.run import Runner

LifecycleAction = Literal["install", "update", "removal"]
LifecycleStatus = Literal["completed", "manual-required", "present", "absent", "unknown"]
ProbeRunner = Callable[[list[str]], str]


@dataclass(frozen=True)
class LifecycleOutcome:
    status: LifecycleStatus
    instructions: tuple[str, ...] = ()


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


def _status_probe(operation: SkillOperation) -> tuple[list[str], str]:
    if operation.operation_id == "codex_plugin_status" and isinstance(
        operation.args, CodexPluginStatusArgs
    ):
        return ["codex", "plugin", "list"], operation.args.plugin
    if operation.operation_id == "pi_package_status" and isinstance(
        operation.args, PiPackageStatusArgs
    ):
        return ["pi", "list"], operation.args.package
    raise ValueError("unreviewed skill lifecycle status operation")


def inspect_status(tool: Tool, probe: ProbeRunner) -> LifecycleOutcome:
    """Probe a pack without acquiring software, or fail closed to manual status."""
    operation = _lifecycle(tool).status
    if operation.mode == "manual-required":
        return LifecycleOutcome("manual-required", operation.instructions)
    argv, contains = _status_probe(operation)
    try:
        output = probe(argv)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return LifecycleOutcome("unknown")
    return LifecycleOutcome("present" if contains in output else "absent")
