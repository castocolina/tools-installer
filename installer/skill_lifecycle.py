"""Typed install, status, update, and removal behavior for skill packs."""

import json
import re
import shutil
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

# Global skill dirs from the vercel-labs/skills Supported Agents table
# (https://github.com/vercel-labs/skills/blob/main/README.md, 2026-10-10).
# Shared ~/.agents/skills rows stay shared. Dirs the README does not name stay out.
SKILL_LOCK_HARNESS_DIRS: dict[str, str] = {
    "adal": ".adal/skills",
    "amp": ".config/agents/skills",
    "antigravity": ".gemini/antigravity/skills",
    "bob": ".bob/skills",
    "claude": ".claude/skills",
    "cline": ".agents/skills",
    "codebuddy": ".codebuddy/skills",
    "codex": ".agents/skills",
    "continue": ".continue/skills",
    "copilot": ".copilot/skills",
    "crush": ".config/crush/skills",
    "cursor": ".cursor/skills",
    "devin": ".config/devin/skills",
    "factory-droid": ".factory/skills",
    "gemini-cli": ".gemini/skills",
    "goose": ".config/goose/skills",
    "grok": ".grok/skills",
    "hermes": ".hermes/skills",
    "junie": ".junie/skills",
    "kilo": ".kilo/skills",
    "kimi": ".agents/skills",
    "kiro": ".kiro/skills",
    "openclaw": ".openclaw/skills",
    "opencode": ".config/opencode/skills",
    "pi": ".agents/skills",
    "qoder": ".qoder/skills",
    "qwen": ".qwen/skills",
    "windsurf": ".codeium/windsurf/skills",
    "zed": ".agents/skills",
}

# Command names verified on this host 2026-10-09, plus binaries named in
# https://github.com/obra/superpowers/blob/main/README.md (agy, devin, grok,
# qwen, hermes, muse). factory-droid `.factory` and gemini-cli `.gemini` are
# the global roots in https://github.com/vercel-labs/skills/blob/main/README.md
# (Droid ~/.factory/skills, Gemini CLI ~/.gemini/skills). antigravity, windsurf,
# kilo, and kimi dirs are the opengsd resolver defaults in
# .claude/gsd-core/references/gsd-run-resolver.md. Devin/Grok/Qwen/Hermes/Muse
# docs disagree on a config dir, so those disk tuples stay empty.
HARNESS_PRESENCE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "antigravity": (("agy",), (".gemini/antigravity",)),
    "claude": (("claude",), (".claude",)),
    "codex": (("codex",), (".codex",)),
    "copilot": (("copilot",), (".copilot",)),
    "cursor": (("cursor-agent", "cursor"), (".cursor", ".local/share/cursor-agent")),
    "devin": (("devin",), ()),
    "factory-droid": (("droid",), (".factory",)),
    "gemini-cli": (("gemini",), (".gemini",)),
    "grok": (("grok",), ()),
    "hermes": (("hermes",), ()),
    "kilo": ((), (".config/kilo",)),
    "kimi": ((), (".kimi-code",)),
    "muse": (("muse",), ()),
    "opencode": (("opencode",), (".config/opencode", ".opencode")),
    "pi": (("pi",), (".pi",)),
    "qwen": (("qwen",), ()),
    "windsurf": ((), (".codeium/windsurf",)),
}

_NO_HOST_HEADER = (
    "No supported agent host was detected on this machine; "
    "instructions for every supported host follow."
)


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


def present_harnesses(home: Path, which: Callable[[str], str | None]) -> frozenset[str]:
    """Hosts detectable from PATH or a closed home-relative marker."""
    found: set[str] = set()
    for harness, (commands, markers) in HARNESS_PRESENCE.items():
        if any(which(command) for command in commands) or any(
            (home / marker).exists() for marker in markers
        ):
            found.add(harness)
    return frozenset(found)


def _filtered_install_lines(
    operation: SkillOperation, present: frozenset[str], supported: tuple[str, ...]
) -> tuple[str, ...]:
    supported_set = set(supported)
    chosen = [
        harness
        for harness, _commands in operation.by_harness
        if harness in present and harness in supported_set
    ]
    pairs = dict(operation.by_harness)
    if chosen:
        return tuple(line for harness in chosen for line in pairs[harness])
    lines = [_NO_HOST_HEADER]
    lines.extend(line for _harness, commands in operation.by_harness for line in commands)
    return tuple(lines)


def perform_action(
    tool: Tool,
    action: LifecycleAction,
    runner: Runner,
    *,
    home: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> LifecycleOutcome:
    """Execute one closed lifecycle operation or return its reviewed handoff."""
    lifecycle = _lifecycle(tool)
    operation = _operation(lifecycle, action)
    if action == "install" and operation.by_harness:
        return LifecycleOutcome(
            "manual-required",
            _filtered_install_lines(
                operation,
                present_harnesses(Path.home() if home is None else home, which),
                lifecycle.supported_harnesses,
            ),
        )
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
