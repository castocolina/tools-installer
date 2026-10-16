"""Typed install, status, update, and removal behavior for skill packs."""

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from installer.model import (
    SKILL_HARNESSES,
    ConfigStep,
    SkillLifecycle,
    SkillOperation,
    SkillStatusProbe,
    Tool,
)
from installer.run import Runner

LifecycleAction = Literal["install", "update", "removal"]
LifecycleStatus = Literal["completed", "manual-required", "present", "absent", "unknown"]
HarnessStatus = Literal["present", "absent", "unknown"]
ProbeRunner = Callable[[list[str]], str]
_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# A Claude plugin id is `<plugin>@<marketplace>`; the leading alphanumeric keeps
# `-s`-style values out of a later argv.
_CLAUDE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*@[A-Za-z0-9][A-Za-z0-9._-]*")
CLAUDE_SCOPES = ("user", "project", "local")
_CLAUDE_OUTPUT_CAP = 1 << 20
_INSTALLED_PLUGINS_CAP = 64 << 10


@dataclass(frozen=True)
class LifecycleOutcome:
    status: LifecycleStatus
    instructions: tuple[str, ...] = ()


@dataclass(frozen=True)
class HarnessCli:
    argv: tuple[str, ...]
    matches: Callable[[str, str], bool | None]  # None: the answer is unreadable


@dataclass(frozen=True)
class ClaudeEntry:
    id: str
    plugin: str
    marketplace: str
    scope: str
    enabled: bool
    version: str


def _claude_entries(output: str) -> tuple[ClaudeEntry, ...] | None:
    """Every entry of `claude plugin list --json`, or None when any part is invalid.

    An invalid entry is never skipped: skipping a malformed canonical entry
    would fabricate "absent".
    """
    if len(output) > _CLAUDE_OUTPUT_CAP:
        return None
    try:
        parsed: object = json.loads(output)
    except (json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(parsed, list):
        return None
    entries: list[ClaudeEntry] = []
    for raw in cast(list[object], parsed):
        if not isinstance(raw, dict):
            return None
        row = cast(dict[object, object], raw)
        plugin_id, scope = row.get("id"), row.get("scope")
        enabled, version = row.get("enabled"), row.get("version")
        if (
            not isinstance(plugin_id, str)
            or _CLAUDE_ID_RE.fullmatch(plugin_id) is None
            or not isinstance(scope, str)
            or scope not in CLAUDE_SCOPES
            or not isinstance(enabled, bool)
            or not isinstance(version, str)
        ):
            return None
        plugin, marketplace = plugin_id.split("@")
        entries.append(ClaudeEntry(plugin_id, plugin, marketplace, scope, enabled, version))
    return tuple(entries)


def _claude_matches(output: str, match: str) -> bool | None:
    """Present only for exactly one enabled user-scope entry with the canonical id (D-18)."""
    entries = _claude_entries(output)
    if entries is None:
        return None
    hits = [e for e in entries if e.id == match and e.scope == "user" and e.enabled]
    return len(hits) == 1


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


SKILL_HARNESS_LABELS: dict[str, str] = {
    "adal": "AdaL",
    "aider": "Aider",
    "alquimia": "Alquimia",
    "amazon-q": "Amazon Q",
    "amp": "Amp",
    "antigravity": "Antigravity",
    "auggie": "Auggie",
    "bob": "IBM Bob",
    "claude": "Claude Code",
    "cline": "Cline",
    "codeartsagent": "CodeArts",
    "codeassistant": "Code Assistant",
    "codebuddy": "CodeBuddy",
    "codewhale": "CodeWhale",
    "codex": "Codex",
    "command-code": "Command Code",
    "continue": "Continue",
    "copilot": "Copilot CLI",
    "costrict": "CoStrict",
    "crush": "Crush",
    "cursor": "Cursor",
    "devin": "Devin",
    "docker-agent": "Docker Agent",
    "dsh": "DeepSeek Harness",
    "factory-droid": "Factory Droid",
    "firebender": "Firebender",
    "forge": "Forge",
    "forgecode": "ForgeCode",
    "gemini-cli": "Gemini CLI",
    "goose": "Goose",
    "grok": "Grok Build",
    "hermes": "Hermes Agent",
    "iflow": "iFlow",
    "jules": "Jules",
    "junie": "Junie",
    "kilo": "Kilo Code",
    "kimi": "Kimi Code",
    "kiro": "Kiro",
    "lingma": "Lingma",
    "minimax-code": "MiniMax Code",
    "muse": "Muse",
    "oh-my-pi": "Oh My Pi",
    "openclaw": "OpenClaw",
    "opencode": "OpenCode",
    "pi": "Pi",
    "qoder": "Qoder",
    "qwen": "Qwen Code",
    "roocode": "Zoo Code",
    "rovodev": "Rovo Dev",
    "shai": "SHAI",
    "tabnine": "Tabnine",
    "trae": "Trae",
    "vibe": "Mistral Vibe",
    "windsurf": "Windsurf",
    "zcode": "ZCode",
    "zed": "Zed",
}

HARNESS_CLI_STATUS: dict[str, HarnessCli] = {
    "claude": HarnessCli(("claude", "plugin", "list", "--json"), _claude_matches),
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
_HOST_HEADER = "Run each block inside the named host."


# Env-var-unset defaults of opengsd's per-runtime config dirs. claude is the
# global ~/.claude, not a project .claude. kimi is KIMI_CODE_HOME (~/.kimi-code),
# not KIMI_CONFIG_DIR (~/.config/agents). Env overrides are not read.
INSTALL_STATE_FILES: dict[str, str] = {"gsd-core": "gsd-install-state.json"}

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
    hosts = chosen or [harness for harness, _commands in operation.by_harness]
    lines = [_HOST_HEADER] if chosen else [_NO_HOST_HEADER]
    for harness in hosts:
        lines.append(f"{SKILL_HARNESS_LABELS.get(harness, harness)}:")
        lines.extend(pairs[harness])
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
    filename = INSTALL_STATE_FILES.get(status_probe.match)
    rel = INSTALL_STATE_HARNESS_DIRS.get(status_probe.harness)
    if filename is None or rel is None:
        return "unknown"
    return "present" if (home / rel / filename).is_file() else "absent"


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
    found = cli.matches(output, status_probe.match)
    if found is None:
        return "unknown"
    return "present" if found else "absent"


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


@dataclass(frozen=True)
class SkillPackReport:
    """Per-harness status of one pack plus its D-18 reasons and fix steps.

    A host whose status is "unknown" was not checked (its probe failed or its
    answer was unreadable), so its reasons and steps are missing, not absent;
    consumers must surface that and never read it as "absent".
    """

    hosts: dict[str, HarnessStatus]
    reasons: tuple[str, ...] = ()
    steps: tuple[ConfigStep, ...] = ()


def _installed_project_paths(home: Path) -> dict[tuple[str, str], list[object]]:
    """`projectPath` values per (id, scope) from installed_plugins.json; {} when unreadable."""
    try:
        with (home / ".claude" / "plugins" / "installed_plugins.json").open("rb") as fh:
            raw = fh.read(_INSTALLED_PLUGINS_CAP + 1)
    except OSError:
        return {}
    if len(raw) > _INSTALLED_PLUGINS_CAP:
        return {}
    try:
        parsed: object = json.loads(raw)
    except (ValueError, RecursionError):
        return {}
    plugins = (
        cast(dict[object, object], parsed).get("plugins") if isinstance(parsed, dict) else None
    )
    if not isinstance(plugins, dict):
        return {}
    paths: dict[tuple[str, str], list[object]] = {}
    for plugin_id, records in cast(dict[object, object], plugins).items():
        if not isinstance(plugin_id, str) or not isinstance(records, list):
            continue
        for record in cast(list[object], records):
            if not isinstance(record, dict):
                continue
            row = cast(dict[object, object], record)
            scope = row.get("scope")
            if isinstance(scope, str):
                paths.setdefault((plugin_id, scope), []).append(row.get("projectPath"))
    return paths


def _project_dir(entry: ClaudeEntry, paths: dict[tuple[str, str], list[object]]) -> Path | None:
    candidates = paths.get((entry.id, entry.scope), [])
    if len(candidates) != 1 or not isinstance(candidates[0], str):
        return None
    path = Path(candidates[0])
    return path if path.is_absolute() and path.is_dir() else None


def _claude_fixes(
    canonical: str,
    entries: tuple[ClaudeEntry, ...],
    paths: dict[tuple[str, str], list[object]],
) -> tuple[tuple[str, ...], tuple[ConfigStep, ...]]:
    """D-18 reasons and ordered steps: keep a working canonical, then drop the copies."""
    plugin, _, canonical_marketplace = canonical.partition("@")
    family = [entry for entry in entries if entry.plugin == plugin]
    users = [entry for entry in family if entry.id == canonical and entry.scope == "user"]
    copies = [entry for entry in family if entry not in users]
    reasons = [
        f"disabled: {entry.id} in user scope ({entry.version})"
        for entry in users
        if not entry.enabled
    ]
    reasons += [f"duplicate: {e.id} in {e.scope} scope ({e.version})" for e in copies]
    if not reasons:
        return (), ()
    steps: list[ConfigStep] = []
    if not users:
        argv = ("claude", "plugin", "install", "-s", "user", canonical)
        steps.append(
            ConfigStep(f"install {canonical} in user scope", "skill_install", "claude", argv)
        )
    elif not any(entry.enabled for entry in users):
        argv = ("claude", "plugin", "enable", "-s", "user", canonical)
        steps.append(
            ConfigStep(f"enable {canonical} in user scope", "plugin_enable", "claude", argv)
        )
    removed: list[ClaudeEntry] = []
    for entry in copies:
        cwd = None if entry.scope == "user" else _project_dir(entry, paths)
        if entry.scope != "user" and cwd is None:
            continue
        argv = ("claude", "plugin", "uninstall", "-s", entry.scope, entry.id)
        text = f"remove {entry.id} from {entry.scope} scope"
        steps.append(ConfigStep(text, "plugin_uninstall", "claude", argv, cwd))
        removed.append(entry)
    for marketplace in dict.fromkeys(entry.marketplace for entry in removed):
        if marketplace == canonical_marketplace:
            continue
        # A copy whose uninstall was suppressed keeps its marketplace (review H4).
        if all(entry in removed for entry in entries if entry.marketplace == marketplace):
            argv = ("claude", "plugin", "marketplace", "remove", marketplace)
            text = f"remove marketplace {marketplace}"
            steps.append(ConfigStep(text, "marketplace_remove", "claude", argv))
    return tuple(reasons), tuple(steps)


def _claude_canonical(lifecycle: SkillLifecycle) -> str | None:
    for status_probe in lifecycle.status_probes:
        if (status_probe.harness, status_probe.via) == ("claude", "plugin-cli"):
            return status_probe.match if _CLAUDE_ID_RE.fullmatch(status_probe.match) else None
    return None


def inspect_skill_reports(
    tools: Sequence[Tool], probe: ProbeRunner, home: Path
) -> dict[str, SkillPackReport]:
    """Probe each distinct harness CLI once; per pack, host status plus D-18 fixes."""
    outputs = _probe_outputs(_needed_argvs(tools), probe)
    skills = _skills_lock_skills(home) if _needs_skill_lock(tools) else {}
    claude_output = outputs.get(HARNESS_CLI_STATUS["claude"].argv)
    entries = None if claude_output is None else _claude_entries(claude_output)
    paths = _installed_project_paths(home) if entries else {}
    reports: dict[str, SkillPackReport] = {}
    for tool in tools:
        lifecycle = tool.skill_lifecycle
        if lifecycle is None:
            reports[tool.id] = SkillPackReport({})
            continue
        hosts = _pack_status(lifecycle, outputs, home, skills)
        canonical = _claude_canonical(lifecycle)
        if canonical is None or entries is None:
            reports[tool.id] = SkillPackReport(hosts)
            continue
        reports[tool.id] = SkillPackReport(hosts, *_claude_fixes(canonical, entries, paths))
    return reports


def inspect_skill_packs(
    tools: Sequence[Tool], probe: ProbeRunner, home: Path
) -> dict[str, dict[str, HarnessStatus]]:
    """Probe each distinct harness CLI once and report present, absent, or unknown."""
    return {
        tool_id: report.hosts
        for tool_id, report in inspect_skill_reports(tools, probe, home).items()
    }


def partial_harnesses(
    hosts: Mapping[str, HarnessStatus], supported: Collection[str], present: Collection[str]
) -> tuple[str, ...]:
    """Supported harnesses on this machine where the pack is absent while another has it (D-17)."""
    if "present" not in hosts.values():
        return ()
    return tuple(
        harness
        for harness in SKILL_HARNESSES
        if harness in supported and harness in present and hosts.get(harness) == "absent"
    )


def partial_steps(
    tool: Tool, harnesses: Sequence[str]
) -> tuple[tuple[str, ...], tuple[ConfigStep, ...]]:
    """One `partial:` reason and one reviewed-handoff install step per missing harness."""
    labels = [SKILL_HARNESS_LABELS.get(harness, harness) for harness in harnesses]
    reasons = tuple(f"partial: missing on {label}" for label in labels)
    steps = tuple(
        ConfigStep(f"install {tool.id} for {label}", "skill_install", harness)
        for harness, label in zip(harnesses, labels, strict=True)
    )
    return reasons, steps


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
