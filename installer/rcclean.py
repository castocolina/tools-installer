"""Find and strip duplicate PATH-export lines in shell rc files.

Detection resolves `export VAR=...` assignments declared earlier in the same file
(so installer lines like `$BUN_INSTALL/bin` expand), skips our own managed blocks,
and flags any PATH entry that resolves to a directory we already manage. Used to
clean the redundant lines bun/pnpm/fnm append to .bashrc/.zshrc.
"""

import re
from collections.abc import Mapping
from pathlib import Path

_MANAGED_BEGINS = ("# >>> tools-installer path >>>", "# >>> tools-installer source >>>")
_MANAGED_ENDS = ("# <<< tools-installer path <<<", "# <<< tools-installer source <<<")
_ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.+?)\s*$")
_PATH_EXPORT = re.compile(r"^\s*(?:export\s+)?PATH=(.+?)\s*$")
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _expand(value: str, env: Mapping[str, str]) -> str | None:
    """Expand $VAR/${VAR} and a leading ~ using env. Returns None if a var is unknown."""
    resolved = True

    def repl(match: re.Match[str]) -> str:
        nonlocal resolved
        name = match.group(1) or match.group(2)
        if name not in env:
            resolved = False
            return ""
        return env[name]

    expanded = _VAR.sub(repl, value)
    if not resolved:
        return None
    if expanded.startswith("~"):
        home = env.get("HOME", "")
        expanded = home + expanded[1:] if home else expanded
    return expanded


def _managed_line_indices(lines: list[str]) -> set[int]:
    """Indices inside any tools-installer managed/source block (markers included)."""
    blocked: set[int] = set()
    depth_start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in _MANAGED_BEGINS:
            depth_start = index
        elif stripped in _MANAGED_ENDS and depth_start is not None:
            blocked.update(range(depth_start, index + 1))
            depth_start = None
    return blocked


def find_duplicate_path_lines(
    rc_text: str, managed_dirs: set[Path], env: Mapping[str, str]
) -> list[int]:
    """Line indices whose PATH export adds a directory already in managed_dirs.

    Only plain `export PATH=...` lines are matched (this is what bun and fnm append).
    pnpm's `pnpm setup` instead emits a self-deduping `case`-guarded block
    (`*) export PATH="$PNPM_HOME:$PATH" ;;`), which is intentionally NOT flagged: it
    is not a plain assignment, and its own guard already skips adding a dir that is
    present — so there is nothing safe (or necessary) to strip.
    """
    lines = rc_text.split("\n")
    blocked = _managed_line_indices(lines)
    local: dict[str, str] = dict(env)
    targets = {str(directory) for directory in managed_dirs}
    flagged: list[int] = []
    for index, line in enumerate(lines):
        if index in blocked:
            continue
        path_match = _PATH_EXPORT.match(line)
        if path_match:
            value = _unquote(path_match.group(1))
            for segment in value.split(":"):
                if segment in ("$PATH", "${PATH}"):
                    continue
                expanded = _expand(segment, local)
                if expanded is not None and expanded in targets:
                    flagged.append(index)
                    break
            continue
        assign = _ASSIGN.match(line)
        if assign:
            expanded = _expand(_unquote(assign.group(2)), local)
            if expanded is not None:
                local[assign.group(1)] = expanded
    return flagged


def strip_lines(rc_text: str, indices: list[int]) -> str:
    """Return rc_text with the given line indices removed."""
    drop = set(indices)
    lines = rc_text.split("\n")
    return "\n".join(line for index, line in enumerate(lines) if index not in drop)
