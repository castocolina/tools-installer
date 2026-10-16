"""Typed install, status, update, and removal behavior for skill packs."""

import json
import os
import re
import shutil
import stat
import subprocess
from collections import deque
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

# D-21: a project-scope pack's npm package; steps pin it to the registry `version`.
PROJECT_PACK_PACKAGES: dict[str, str] = {"opengsd": "@opengsd/gsd-core"}
# GSD runtime flag per harness id where the two differ.
_GSD_RUNTIME_IDS: dict[str, str] = {"kimi": "kimi-code"}
_GLOBAL_LEFTOVER_REASON = "installed globally; this pack is project-local"

# HOME-relative dirs listed for `gsd-*` entries: D-21's skills/agents/commands/hooks
# in every harness home, plus GSD 1.16.0's other global artifact dirs
# (capability-registry.cjs artifactLayout.global, read 2026-10-16).
_GSD_GLOBAL_EXTRA_DIRS: dict[str, tuple[str, ...]] = {
    "antigravity": (".gemini/config/skills", ".gemini/config/agents"),
    "codex": (".agents/skills",),
    "kilo": (".config/kilo/command",),
}
PROJECT_GLOBAL_MACHINERY: dict[str, tuple[str, ...]] = {
    harness: tuple(f"{home_dir}/{sub}" for sub in ("skills", "agents", "commands", "hooks"))
    + _GSD_GLOBAL_EXTRA_DIRS.get(harness, ())
    for harness, home_dir in INSTALL_STATE_HARNESS_DIRS.items()
}
# Dirs GSD writes for more than one runtime: GSD 1.16.0 also probes `~/.agents` as the
# Kimi CLI `configHome` (read 2026-10-16), so the owning harness's uninstall may miss them.
PROJECT_SHARED_GLOBAL_DIRS: dict[str, str] = {".agents/skills": "Kimi CLI"}

HookConfigFormat = Literal["settings", "hooks-json", "toml"]
# HOME-relative hook configs per GSD 1.16.0 `hooksSurface` (capability-registry.cjs, read
# 2026-10-16). copilot (`copilot-inline`, no hook events), kilo and opencode (`none`) have
# no hook config, so they have no entry.
PROJECT_HOOK_CONFIGS: dict[str, tuple[tuple[str, HookConfigFormat], ...]] = {
    "antigravity": ((".gemini/antigravity/settings.json", "settings"),),
    "claude": ((".claude/settings.json", "settings"),),
    "codex": ((".codex/hooks.json", "hooks-json"), (".codex/config.toml", "toml")),
    "cursor": ((".cursor/hooks.json", "hooks-json"),),
    "kimi": ((".kimi-code/config.toml", "toml"),),
    "windsurf": ((".codeium/windsurf/hooks.json", "hooks-json"),),
}
# The scan runs on the refresh worker every pass; a hook config is never legitimately larger.
_HOOK_CONFIG_MAX_BYTES = 256 * 1024
_HOOK_WALK_MAX_NODES = 20000
_GSD_HOOK_SCRIPT_RE = re.compile(r"(?:^|[/\\\s\"'])gsd-[A-Za-z0-9._-]+\.(?:js|cjs|mjs|sh)\b")
_GSD_TOML_MARKER_RE = re.compile(r"^# GSD Hooks(?: BEGIN|\r?$)", re.MULTILINE)

# D-21: HOME-relative roots walked for GSD repos (a dir holding `.planning/config.json`).
PROJECT_ROOTS = ("git", "src", "code", "projects", "work", "dev")
# Only the project dirs verified on this host (19-RESEARCH A3): a runtime outside this map
# gets neither detection nor an install step, so Phase 20 never runs an unobservable install.
PROJECT_RUNTIME_DIRS: dict[str, str] = {"claude": ".claude", "opencode": ".opencode"}
_MAX_WALK_DEPTH = 4
# The walk runs on the refresh worker every pass; the entry cap bounds the enumeration of
# one huge directory, which the dir cap alone does not.
_MAX_WALK_DIRS = 5000
_MAX_WALK_ENTRIES = 50000


@dataclass(frozen=True)
class ProjectPackReport:
    """Project-scope pack facts: repos with an install, global leftovers, D-21 fixes."""

    repos: tuple[tuple[Path, tuple[str, ...]], ...] = ()
    leftovers: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    steps: tuple[ConfigStep, ...] = ()
    # HOME-relative paths whose read was inconclusive: an unchecked path may hide a
    # leftover, so consumers must say so rather than read it as clean.
    unchecked: tuple[str, ...] = ()


def _is_dir(path: Path) -> bool | None:
    """Whether `path` is a directory; a missing path is not; None: unreadable."""
    try:
        return stat.S_ISDIR(path.stat().st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return None


def _has_gsd_entry(directory: Path) -> bool | None:
    """Whether `directory` lists a `gsd-*` name; a missing dir has none; None: unlistable."""
    try:
        with os.scandir(directory) as entries:
            return any(entry.name.startswith("gsd-") for entry in entries)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return None


def _lstat_mode(path: Path) -> int:
    """The mode of `path` itself (a symlink is not followed); 0 when it cannot be read."""
    try:
        return path.lstat().st_mode
    except OSError:
        return 0


def _find_project_repos(home: Path) -> tuple[Path, ...]:
    """GSD repos under PROJECT_ROOTS, breadth-first and bounded; read-only.

    Symlinks are never followed, a symlinked root included: a repo becomes the `cwd` of a
    Phase 20 command, so it must stay under HOME. Every admission to the queue counts
    against the dir cap and every entry read against the entry cap.
    """
    queue: deque[tuple[Path, int]] = deque()
    admitted = 0
    for name in PROJECT_ROOTS:
        root = home / name
        if admitted < _MAX_WALK_DIRS and stat.S_ISDIR(_lstat_mode(root)):
            queue.append((root, 0))
            admitted += 1
    entries_left = _MAX_WALK_ENTRIES
    repos: list[Path] = []
    while queue:
        directory, depth = queue.popleft()
        if stat.S_ISREG(_lstat_mode(directory / ".planning" / "config.json")):
            repos.append(directory)  # a repo is not descended
            continue
        if depth >= _MAX_WALK_DEPTH or entries_left <= 0 or admitted >= _MAX_WALK_DIRS:
            continue
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entries_left -= 1
                    name = entry.name
                    if (
                        not name.startswith(".")  # hidden dirs, `.venv` included
                        and name != "node_modules"
                        and entry.is_dir(follow_symlinks=False)
                    ):
                        queue.append((Path(entry.path), depth + 1))
                        admitted += 1
                    if entries_left <= 0 or admitted >= _MAX_WALK_DIRS:
                        break
        except OSError:
            continue
    return tuple(repos)


def _installed_runtimes(repo: Path) -> tuple[str, ...]:
    """Runtimes with a real GSD install in `repo`: VERSION plus a `gsd-*` skill or command.

    A stale VERSION beside empty dirs or another pack's skills is not an install.
    """
    return tuple(
        runtime
        for runtime, directory in PROJECT_RUNTIME_DIRS.items()
        if stat.S_ISREG(_lstat_mode(repo / directory / "gsd-core" / "VERSION"))
        and any(_has_gsd_entry(repo / directory / sub) for sub in ("skills", "commands"))
    )


def _gsd_hook_in(value: object) -> bool | None:
    """Iterative walk: a `gsd-managed: true` entry or a GSD hook script; None past the bound."""
    stack = [value]
    for _ in range(_HOOK_WALK_MAX_NODES):
        if not stack:
            return False
        node = stack.pop()
        if isinstance(node, str):
            if _GSD_HOOK_SCRIPT_RE.search(node):
                return True
        elif isinstance(node, dict):
            row = cast(dict[object, object], node)
            if row.get("gsd-managed") is True:
                return True
            stack.extend(row.values())
        elif isinstance(node, list):
            stack.extend(cast(list[object], node))
    return False if not stack else None


def _gsd_hooks_registered(path: Path, fmt: HookConfigFormat) -> bool | None:
    """True: a GSD hook registration; False: none, or no config; None: inconclusive.

    Pure read. The size cap is enforced by the read itself, so a config that grows or is
    swapped after the stat is never read whole.
    """
    try:
        info = path.stat()  # follows a dotfiles-manager symlink
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > _HOOK_CONFIG_MAX_BYTES:
        return None
    try:
        with path.open("rb") as fh:
            data = fh.read(_HOOK_CONFIG_MAX_BYTES + 1)
        if len(data) > _HOOK_CONFIG_MAX_BYTES:
            return None
        text = data.decode("utf-8")
        if fmt == "toml":
            return _GSD_TOML_MARKER_RE.search(text) is not None
        document: object = json.loads(text)
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(document, dict):
        return None  # a top-level array or scalar is not a hook config
    root = cast(dict[object, object], document)
    return _gsd_hook_in(root.get("hooks") if fmt == "settings" else root)


def _global_uninstall_step(tool_id: str, harness: str, package: str, version: str) -> ConfigStep:
    label = SKILL_HARNESS_LABELS.get(harness, harness)
    runtime = _GSD_RUNTIME_IDS.get(harness, harness)
    argv = ("pnpm", "dlx", f"{package}@{version}", f"--{runtime}", "--global", "--uninstall")
    text = f"uninstall the global {tool_id} install for {label}"
    return ConfigStep(text, "project_pack_global_uninstall", harness, argv)


def inspect_project_pack(tool: Tool, home: Path, present: Collection[str]) -> ProjectPackReport:
    """D-21 facts of a project-scope pack: global leftovers and per-repo installs; read-only.

    A user-scope pack yields an empty report. Each leftover harness gets the pack's own
    global uninstall as its step; nothing under HOME is ever deleted here. Leftovers are
    files on disk, so they are reported whether or not their harness is in `present`
    (which scopes the per-repo install steps).
    """
    lifecycle = tool.skill_lifecycle
    package = PROJECT_PACK_PACKAGES.get(tool.id)
    version = None if lifecycle is None or lifecycle.scope != "project" else lifecycle.version
    if package is None or version is None:
        return ProjectPackReport()
    leftovers: list[str] = []
    shared: dict[str, str] = {}
    unchecked: list[str] = []
    for harness, home_dir in INSTALL_STATE_HARNESS_DIRS.items():
        answers: list[tuple[str, bool | None]] = [
            (f"{home_dir}/gsd-core", _is_dir(home / home_dir / "gsd-core"))
        ]
        answers += [(d, _has_gsd_entry(home / d)) for d in PROJECT_GLOBAL_MACHINERY[harness]]
        answers += [
            (relative, _gsd_hooks_registered(home / relative, fmt))
            for relative, fmt in PROJECT_HOOK_CONFIGS.get(harness, ())
        ]
        unchecked += [relative for relative, answer in answers if answer is None]
        hits = [relative for relative, answer in answers if answer]
        if hits:
            leftovers.append(harness)
        for directory in hits:
            if directory in PROJECT_SHARED_GLOBAL_DIRS:
                shared.setdefault(directory, harness)
    repos = tuple((repo, _installed_runtimes(repo)) for repo in _find_project_repos(home))
    if not leftovers:
        return ProjectPackReport(repos=repos, unchecked=tuple(unchecked))
    reasons = [_GLOBAL_LEFTOVER_REASON]
    for directory, harness in shared.items():
        label = SKILL_HARNESS_LABELS.get(harness, harness)
        other = PROJECT_SHARED_GLOBAL_DIRS[directory]
        reasons.append(
            f"gsd-* entries in ~/{directory}: GSD writes there for {label} and for {other}, "
            f"so the {label} uninstall may not remove them"
        )
    steps = tuple(
        _global_uninstall_step(tool.id, harness, package, version) for harness in leftovers
    )
    return ProjectPackReport(
        repos=repos,
        leftovers=tuple(leftovers),
        reasons=tuple(reasons),
        steps=steps,
        unchecked=tuple(unchecked),
    )


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
