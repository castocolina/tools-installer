"""Static descriptions of supported agent configuration surfaces."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PermissionMode = Literal["configurable", "audit-only", "unknown"]


@dataclass(frozen=True)
class AgentAdapter:
    """A supported agent's configuration and instruction locations."""

    id: str
    label: str
    config_path: Path
    instruction_path: Path | None
    permission_mode: PermissionMode


def adapters(
    home: Path, platform_os: str = "linux", environ: Mapping[str, str] | None = None
) -> dict[str, AgentAdapter]:
    """Return supported agent adapters rooted in ``home``.

    Only macOS differs: VS Code keeps its user settings under Library there.
    Every other OS value (linux, fedora, ...) takes the ~/.config path.
    `environ` is the caller's environment (None reads as empty): only an absolute
    COPILOT_HOME moves copilot's settings file. Nothing here reads the process environment.

    This function does not inspect or modify the filesystem; callers can use
    the returned paths for detection, audit, and later policy application.
    """
    vscode_user = (
        home / "Library" / "Application Support" / "Code" / "User"
        if platform_os == "macos"
        else home / ".config" / "Code" / "User"
    )
    # A relative COPILOT_HOME resolves against copilot's own working directory, which is
    # unknowable here, so only an absolute value is honoured.
    copilot_home = (environ or {}).get("COPILOT_HOME", "")
    copilot_root = Path(copilot_home) if Path(copilot_home).is_absolute() else home / ".copilot"
    return {
        "copilot": AgentAdapter(
            id="copilot",
            label="GitHub Copilot CLI",
            config_path=copilot_root / "settings.json",
            instruction_path=None,
            permission_mode="configurable",
        ),
        "cursor-agent": AgentAdapter(
            id="cursor-agent",
            label="Cursor Agent",
            config_path=home / ".cursor" / "cli-config.json",
            instruction_path=None,
            permission_mode="configurable",
        ),
        "vscode": AgentAdapter(
            id="vscode",
            label="VS Code",
            config_path=vscode_user / "settings.json",
            instruction_path=None,
            permission_mode="unknown",
        ),
        "claude": AgentAdapter(
            id="claude",
            label="Claude",
            config_path=home / ".claude" / "settings.json",
            instruction_path=home / ".claude" / "CLAUDE.md",
            permission_mode="unknown",
        ),
        "codex": AgentAdapter(
            id="codex",
            label="Codex",
            config_path=home / ".codex" / "config.toml",
            instruction_path=home / ".codex" / "AGENTS.md",
            permission_mode="unknown",
        ),
        "opencode": AgentAdapter(
            id="opencode",
            label="OpenCode",
            config_path=home / ".config" / "opencode" / "opencode.json",
            instruction_path=home / ".config" / "opencode" / "AGENTS.md",
            permission_mode="configurable",
        ),
        "pi": AgentAdapter(
            id="pi",
            label="Pi",
            config_path=home / ".pi",
            instruction_path=home / ".pi" / "AGENTS.md",
            permission_mode="audit-only",
        ),
        "antigravity": AgentAdapter(
            id="antigravity",
            label="Antigravity",
            config_path=home / ".gemini" / "antigravity-cli" / "settings.json",
            instruction_path=home / ".gemini" / "GEMINI.md",
            permission_mode="configurable",
        ),
    }
