"""Typed install, status, update, and removal behavior for skill packs."""

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from installer.model import SKILL_HARNESSES, SkillLifecycle, SkillOperation, SkillStatusProbe, Tool
from installer.run import Runner

LifecycleAction = Literal["install", "update", "removal"]
LifecycleStatus = Literal["completed", "manual-required", "present", "absent", "unknown"]
HarnessStatus = Literal["present", "absent", "unknown"]
ProbeRunner = Callable[[list[str]], str]
_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


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

# Only claude is verified on this host. Other harness dirs stay out until checked.
SKILL_LOCK_HARNESS_DIRS: dict[str, str] = {"claude": ".claude/skills"}

# Env-var-unset defaults of opengsd's per-runtime config dirs. claude is the
# global ~/.claude, not a project .claude. kimi is KIMI_CODE_HOME (~/.kimi-code),
# not KIMI_CONFIG_DIR (~/.config/agents). Env overrides are not read.
INSTALL_STATE_HARNESS_DIRS: dict[str, str] = {
    "antigravity": ".gemini/antigravity",
    "claude": ".claude",
    "codex": ".codex",
    "copilot": ".copilot",
    "cursor": ".cursor",
    "kilo": ".config/kilo",
    "kimi": ".kimi-code",
    "opencode": ".config/opencode",
    "windsurf": ".codeium/windsurf",
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


def _skills_lock_skills(home: Path) -> dict[str, str] | None:
    path = home / ".agents" / ".skill-lock.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError):
        return None
    try:
        parsed: object = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    skills = cast(dict[object, object], parsed).get("skills")
    if not isinstance(skills, dict):
        return None
    result: dict[str, str] = {}
    for name, entry in cast(dict[object, object], skills).items():
        if (
            not isinstance(name, str)
            or name in {".", ".."}
            or _SKILL_NAME_RE.fullmatch(name) is None
        ):
            continue
        if not isinstance(entry, dict):
            continue
        source = cast(dict[object, object], entry).get("source")
        if isinstance(source, str):
            result[name] = source
    return result


def _skills_lock_status(
    status_probe: SkillStatusProbe, home: Path, skills: dict[str, str] | None
) -> HarnessStatus:
    rel = SKILL_LOCK_HARNESS_DIRS.get(status_probe.harness)
    if rel is None or skills is None:
        return "unknown"
    root = home / rel
    for name, source in skills.items():
        if source == status_probe.match and (root / name).exists():
            return "present"
    return "absent"


def _install_state_status(status_probe: SkillStatusProbe, home: Path) -> HarnessStatus:
    rel = INSTALL_STATE_HARNESS_DIRS.get(status_probe.harness)
    if rel is None:
        return "unknown"
    return "present" if (home / rel / "gsd-install-state.json").is_file() else "absent"


def _harness_status(
    status_probe: SkillStatusProbe,
    outputs: dict[tuple[str, ...], str | None],
    home: Path,
    skills: dict[str, str] | None,
) -> HarnessStatus:
    if status_probe.via == "skills-lock":
        return _skills_lock_status(status_probe, home, skills)
    if status_probe.via == "install-state":
        return _install_state_status(status_probe, home)
    cli = HARNESS_CLI_STATUS.get(status_probe.harness)
    if cli is None:
        return "unknown"
    output = outputs.get(cli.argv)
    if output is None:
        return "unknown"
    return "present" if cli.matches(output, status_probe.match) else "absent"


def _pack_status(
    lifecycle: SkillLifecycle,
    outputs: dict[tuple[str, ...], str | None],
    home: Path,
    skills: dict[str, str] | None,
) -> dict[str, HarnessStatus]:
    by_harness = {status_probe.harness: status_probe for status_probe in lifecycle.status_probes}
    return {
        harness: _harness_status(by_harness[harness], outputs, home, skills)
        for harness in SKILL_HARNESSES
        if harness in by_harness
    }


def _needs_skill_lock(tools: Sequence[Tool]) -> bool:
    return any(
        tool.skill_lifecycle is not None
        and any(probe.via == "skills-lock" for probe in tool.skill_lifecycle.status_probes)
        for tool in tools
    )


def inspect_skill_packs(
    tools: Sequence[Tool], probe: ProbeRunner, home: Path
) -> dict[str, dict[str, HarnessStatus]]:
    """Probe each distinct harness CLI once and report present, absent, or unknown."""
    outputs = _probe_outputs(_needed_argvs(tools), probe)
    skills = _skills_lock_skills(home) if _needs_skill_lock(tools) else {}
    return {
        tool.id: (
            {}
            if tool.skill_lifecycle is None
            else _pack_status(tool.skill_lifecycle, outputs, home, skills)
        )
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
