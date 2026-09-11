"""Audit and apply narrowly scoped, read-only agent environment policy."""

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from installer.agent_env import AgentAdapter
from installer.agent_guidance import AGENT_TOOLING_MARKDOWN
from installer.policy import PolicyLayer, PolicyResult

AuditState = Literal["healthy", "fixable", "manual-required", "not-detected"]

_GUIDANCE_BEGIN = "<!-- >>> tools-installer shared agent tooling >>>"
_GUIDANCE_END = "<!-- <<< tools-installer shared agent tooling <<< -->"
_REFERENCE_BEGIN = "# >>> tools-installer agent tooling >>>"
_REFERENCE_END = "# <<< tools-installer agent tooling <<<"

_OPENCODE_READ_PATHS = (
    "~/.agents/**",
    "~/.claude/**",
    "~/.codex/**",
    "~/.config/opencode/**",
    "~/.gemini/antigravity-cli/**",
    "~/.pi/**",
    "~/git/**",
)
_HOME_READ_PATHS = (
    ".agents",
    ".claude",
    ".codex",
    ".config/opencode",
    ".gemini/antigravity-cli",
    ".pi",
    "git",
)
_UNKNOWN_DETAIL = "audit only; persistent permission format unknown"


@dataclass(frozen=True)
class AgentAudit:
    """Current policy state for one supported agent."""

    adapter: AgentAdapter
    state: AuditState
    detail: str
    guidance_pending: bool = False
    permission_pending: bool | None = None


def _resolved(path: Path) -> Path:
    """Path.resolve()'s own lexical resolution, but preceded by an explicit
    os.stat() probe for a genuine symlink loop.

    Neither Path.resolve() nor Path.exists() can be trusted for this: some
    CPython versions have resolve() raise RuntimeError instead of OSError for
    a symlink loop (a documented pathlib inconsistency, not stable across
    Python versions), and on others -- observed live on macOS CI, not just a
    hypothetical -- resolve() tolerates the loop entirely and returns a path
    with no exception at all, while exists() explicitly treats ELOOP as
    "doesn't exist" (pathlib's own _ignore_error list). A raw os.stat() call
    is the portable primitive: ELOOP detection during pathname resolution is
    kernel-level POSIX behavior, not Python's to get inconsistent about.
    FileNotFoundError/NotADirectoryError are swallowed -- the common, valid
    case for most adapter destinations before setup -- so resolve() below
    still returns a usable best-effort path for those; any other OSError
    (ELOOP in particular) propagates to the caller uncaught.
    """
    with contextlib.suppress(FileNotFoundError, NotADirectoryError):
        path.stat()
    return path.resolve()


def _validated_home(adapter: AgentAdapter, home: Path) -> Path:
    root = home.resolve()
    destinations = [adapter.config_path, home / ".agents" / "AGENTS-TOOLING.md"]
    if adapter.instruction_path is not None:
        destinations.append(adapter.instruction_path)
    if any(not _resolved(path).is_relative_to(root) for path in destinations):
        raise ValueError(f"{adapter.label} adapter path is outside injected home")
    return root


def _read_json_object(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value: object = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _object_member(parent: dict[str, object], key: str) -> dict[str, object]:
    value = parent.setdefault(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return cast(dict[str, object], value)


def _list_member(parent: dict[str, object], key: str) -> list[object]:
    value = parent.setdefault(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a JSON array")
    return cast(list[object], value)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def _apply_opencode(adapter: AgentAdapter) -> str:
    config = _read_json_object(adapter.config_path)
    permission = _object_member(config, "permission")
    external = _object_member(permission, "external_directory")
    edit = _object_member(permission, "edit")
    for path in _OPENCODE_READ_PATHS:
        external[path] = "allow"
        edit[path] = "deny"
    _write_json(adapter.config_path, config)
    return "narrow external reads allowed; edits denied"


def _antigravity_rules(home: Path) -> tuple[str, ...]:
    return tuple(f"read_file({home / path})" for path in _HOME_READ_PATHS)


def _apply_antigravity(adapter: AgentAdapter, home: Path) -> str:
    config = _read_json_object(adapter.config_path)
    permissions = _object_member(config, "permissions")
    allow = _list_member(permissions, "allow")
    for rule in _antigravity_rules(home):
        if rule not in allow:
            allow.append(rule)
    _write_json(adapter.config_path, config)
    return "exact read_file paths allowed"


def _guidance_block() -> str:
    return "\n".join((_GUIDANCE_BEGIN, AGENT_TOOLING_MARKDOWN.rstrip(), _GUIDANCE_END))


def _reference_block(guidance: Path) -> str:
    return "\n".join(
        (
            _REFERENCE_BEGIN,
            f"Read {guidance} for shared tool guidance.",
            _REFERENCE_END,
        )
    )


def _replace_managed_blocks(content: str, block: str, begin: str, end: str) -> str:
    lines = content.split("\n")
    managed_indices: set[int] = set()
    pending_begin: int | None = None
    for index, line in enumerate(lines):
        if line == begin:
            pending_begin = index
        elif line == end and pending_begin is not None:
            managed_indices.update(range(pending_begin, index + 1))
            pending_begin = None

    kept = [
        line
        for index, line in enumerate(lines)
        if index not in managed_indices and line not in {begin, end}
    ]

    base = "\n".join(kept).rstrip("\n")
    if base:
        return f"{base}\n\n{block}\n"
    return f"{block}\n"


def _has_exact_managed_block(content: str, block: str, begin: str, end: str) -> bool:
    lines = content.split("\n")
    expected = block.split("\n")
    starts = [index for index, line in enumerate(lines) if line == begin]
    return (
        len(starts) == 1
        and lines.count(end) == 1
        and lines[starts[0] : starts[0] + len(expected)] == expected
    )


def _write_guidance_and_reference(adapter: AgentAdapter, home: Path) -> None:
    guidance = home / ".agents" / "AGENTS-TOOLING.md"
    guidance.parent.mkdir(parents=True, exist_ok=True)
    existing = guidance.read_text() if guidance.exists() else ""
    guidance.write_text(
        _replace_managed_blocks(
            existing,
            _guidance_block(),
            _GUIDANCE_BEGIN,
            _GUIDANCE_END,
        )
    )

    if adapter.instruction_path is None:
        return
    adapter.instruction_path.parent.mkdir(parents=True, exist_ok=True)
    existing = adapter.instruction_path.read_text() if adapter.instruction_path.exists() else ""
    adapter.instruction_path.write_text(
        _replace_managed_blocks(
            existing,
            _reference_block(guidance),
            _REFERENCE_BEGIN,
            _REFERENCE_END,
        )
    )


def apply_agent_guidance(adapter: AgentAdapter, home: Path) -> PolicyResult:
    """Write shared guidance and its native reference without changing permissions."""
    home = _validated_home(adapter, home)
    _write_guidance_and_reference(adapter, home)
    return PolicyResult(
        layers=(
            PolicyLayer(
                "Guidance",
                f"managed reference to {home / '.agents/AGENTS-TOOLING.md'}",
            ),
        ),
        reload_hint=None,
        warning=None,
    )


def apply_agent_permissions(adapter: AgentAdapter, home: Path) -> PolicyResult:
    """Apply only a verified read-only permission surface within ``home``."""
    home = _validated_home(adapter, home)
    try:
        if adapter.id == "opencode":
            detail = _apply_opencode(adapter)
        elif adapter.id == "antigravity":
            detail = _apply_antigravity(adapter, home)
        elif adapter.id == "pi":
            detail = "manual setup required"
        elif adapter.id in {"claude", "codex"}:
            detail = _UNKNOWN_DETAIL
        else:
            detail = "manual setup required: unsupported adapter"
    except (json.JSONDecodeError, OSError, ValueError) as error:
        detail = f"manual setup required: {error}"

    return PolicyResult(
        layers=(PolicyLayer("Permissions", detail),),
        reload_hint=None,
        warning=None,
    )


def apply_agent_policy(adapter: AgentAdapter, home: Path) -> PolicyResult:
    """Compatibility operation that applies permissions and shared guidance."""
    permissions = apply_agent_permissions(adapter, home)
    guidance = apply_agent_guidance(adapter, home)
    return PolicyResult(
        layers=permissions.layers + guidance.layers,
        reload_hint=None,
        warning=None,
    )


def _has_managed_guidance_and_reference(adapter: AgentAdapter, home: Path) -> bool:
    guidance = home / ".agents" / "AGENTS-TOOLING.md"
    if not guidance.exists() or not _has_exact_managed_block(
        guidance.read_text(),
        _guidance_block(),
        _GUIDANCE_BEGIN,
        _GUIDANCE_END,
    ):
        return False
    if adapter.instruction_path is None:
        return True
    return adapter.instruction_path.exists() and _has_exact_managed_block(
        adapter.instruction_path.read_text(),
        _reference_block(guidance),
        _REFERENCE_BEGIN,
        _REFERENCE_END,
    )


def _opencode_is_healthy(adapter: AgentAdapter) -> bool:
    config = _read_json_object(adapter.config_path)
    permission = _object_member(config, "permission")
    external = _object_member(permission, "external_directory")
    edit = _object_member(permission, "edit")
    return all(
        external.get(path) == "allow" and edit.get(path) == "deny" for path in _OPENCODE_READ_PATHS
    )


def _antigravity_is_healthy(adapter: AgentAdapter, home: Path) -> bool:
    config = _read_json_object(adapter.config_path)
    permissions = _object_member(config, "permissions")
    allow = _list_member(permissions, "allow")
    return all(rule in allow for rule in _antigravity_rules(home))


def audit_agent_policy(adapter: AgentAdapter, home: Path) -> AgentAudit:
    """Inspect one adapter without modifying its files."""
    home = _validated_home(adapter, home)
    # GEMINI.md is a shared Gemini instruction surface, not Antigravity-specific
    # installation evidence. Once Antigravity's settings exist, it remains the
    # safe native target for the managed guidance reference.
    detected = adapter.config_path.exists() or (
        adapter.id != "antigravity"
        and adapter.instruction_path is not None
        and adapter.instruction_path.exists()
    )
    if not detected:
        return AgentAudit(
            adapter,
            "not-detected",
            "agent configuration not detected",
            permission_pending=False,
        )
    try:
        guidance_pending = not _has_managed_guidance_and_reference(adapter, home)
    except (OSError, ValueError) as error:
        return AgentAudit(
            adapter,
            "manual-required",
            f"manual setup required: {error}",
            permission_pending=False,
        )
    if adapter.id == "pi":
        return AgentAudit(
            adapter,
            "manual-required",
            "manual setup required",
            guidance_pending=guidance_pending,
            permission_pending=False,
        )
    if adapter.id in {"claude", "codex"}:
        return AgentAudit(
            adapter,
            "manual-required",
            _UNKNOWN_DETAIL,
            guidance_pending=guidance_pending,
            permission_pending=False,
        )
    if adapter.id not in {"opencode", "antigravity"}:
        return AgentAudit(
            adapter,
            "manual-required",
            "manual setup required: unsupported adapter",
            guidance_pending=guidance_pending,
            permission_pending=False,
        )
    try:
        permissions_healthy = (
            _opencode_is_healthy(adapter)
            if adapter.id == "opencode"
            else _antigravity_is_healthy(adapter, home)
        )
    except (json.JSONDecodeError, OSError, ValueError) as error:
        return AgentAudit(
            adapter,
            "manual-required",
            f"manual setup required: {error}",
            guidance_pending=guidance_pending,
            permission_pending=False,
        )
    healthy = permissions_healthy and not guidance_pending
    state: AuditState = "healthy" if healthy else "fixable"
    detail = "read-only policy configured" if healthy else "read-only policy can be applied"
    return AgentAudit(
        adapter,
        state,
        detail,
        guidance_pending=guidance_pending,
        permission_pending=not permissions_healthy,
    )
