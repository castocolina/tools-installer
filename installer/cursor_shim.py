"""The cursor-agent model shim (SPEC R7).

`~/.local/bin/cursor-agent` is a vendor symlink to the release launcher. The shim replaces
that link with a small bash script that runs the launcher, put in front of a default `--model`
when the caller gave none. The script resolves `~/.local/bin/agent` on every call, so a vendor
update that relinks `agent` is followed without a rewrite. `agent` and the launcher are never
opened for writing, and a `cursor-agent` that is a regular file without our sentinel is the
user's own and is never touched.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from installer import atomic, daemon, receipts, run, schedules
from installer.atomic import read_capped

SHIM_SENTINEL: Final = "# tools-installer-helper: cursor-agent-shim"
_SENTINEL_WINDOW: Final = 4096
_MODEL_LINE_RE: Final = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]{0,127}) - ")
_LIST_MODELS_TIMEOUT: Final = 40

ShimWrite = Literal["written", "unchanged", "kept-foreign"]
ModelCheck = Literal["listed", "not-listed", "unverified"]


@dataclass(frozen=True)
class ShimReport:
    write: ShimWrite
    check: ModelCheck
    model: str


def shim_paths(home: Path) -> tuple[Path, Path]:
    """`(cursor-agent, agent)` under `home`, computed at call time."""
    bin_dir = home / ".local" / "bin"
    return bin_dir / "cursor-agent", bin_dir / "agent"


def render_shim(agent: Path, model: str | None) -> str:
    """The shim text; `model=None` renders the pass-through shim (no `--model` injected)."""
    if model is not None:
        schedules.validate_model_id(model)
    if "'" in str(agent):
        raise daemon.DaemonScheduleError("the agent path cannot contain a single quote")
    # Bash 3.2 with `set -u`: no arrays. Never re-exec under another argv[0]: the launcher
    # resolves its own directory from `realpath "$0"`.
    flag = "" if model is None else f"--model '{model}' "
    return (
        "#!/usr/bin/env bash\n"
        f"{SHIM_SENTINEL}\n"
        "set -euo pipefail\n"
        f"agent='{agent}'\n"
        "if command -v realpath >/dev/null 2>&1; "
        'then target="$(realpath "$agent" 2>/dev/null || true)"; '
        'else target="$(readlink -f "$agent" 2>/dev/null || true)"; fi\n'
        'if [ -z "${target:-}" ] || [ ! -x "$target" ]; then '
        'echo "cursor-agent shim: $agent is missing or dangling" >&2; exit 127; fi\n'
        'for a in "$@"; do case "$a" in --model|--model=*) exec "$target" "$@";; esac; done\n'
        f'exec "$target" {flag}"$@"\n'
    )


def is_our_shim(path: Path) -> bool:
    """True for a regular file carrying the sentinel as a whole line in its first 4 KiB.

    A symlink is never ours, whatever it points at: the check never reads through a link."""
    if path.is_symlink():
        return False
    try:
        data = read_capped(path, _SENTINEL_WINDOW, follow_symlinks=False)
    except OSError:
        return False
    if data is None:
        data = b""
    return SHIM_SENTINEL in data.decode("utf-8", errors="replace").splitlines()


def check_model(model: str, models: tuple[str, ...] | None) -> ModelCheck:
    """`--list-models` never lists a bracket override verbatim, so compare the base id (D-18)."""
    if models is None:
        return "unverified"
    return "listed" if model.split("[", 1)[0] in models else "not-listed"


def refresh_shim(
    *, link: Path, agent: Path, model: str, models: tuple[str, ...] | None
) -> ShimReport:
    """Make `link` the shim for `model`, or the pass-through shim when the list lacks it."""
    check = check_model(model, models)
    if link.exists() and not link.is_symlink() and not is_our_shim(link):
        return ShimReport("kept-foreign", check, model)
    try:
        agent.resolve(strict=True)
    except OSError as exc:
        raise OSError(f"~/.local/bin/agent is missing or dangling: {agent}") from exc
    text = render_shim(agent, None if check == "not-listed" else model).encode()
    if is_our_shim(link) and link.read_bytes() == text:
        return ShimReport("unchanged", check, model)
    atomic.atomic_replace_entry(link, text, mode=0o755)
    # False is normal: no receipt on this host, and the sentinel alone proves ownership (D-19).
    receipts.refingerprint_leaf("cursor-agent", link)
    return ShimReport("written", check, model)


def restore_link(*, link: Path, agent: Path) -> bool:
    """Turn our shim back into a symlink to `agent`'s target; a foreign regular file stays."""
    if not (link.is_symlink() or is_our_shim(link)):
        return False
    atomic.replace_symlink(link, os.readlink(agent))
    receipts.refingerprint_leaf("cursor-agent", link)
    return True


def remove_shim(link: Path) -> bool:
    """Delete `link` only when it is our shim; True when it was removed."""
    if not is_our_shim(link):
        return False
    link.unlink()
    return True


def parse_models(stdout: str) -> tuple[str, ...]:
    """The ids of `<id> - <label>` lines; the header, the tip and blank lines carry none."""
    matches = (_MODEL_LINE_RE.match(line.replace("\u200b", "")) for line in stdout.splitlines())
    return tuple(match.group(1) for match in matches if match)


def _run_list_models(cmd: list[str]) -> str:
    return run.run_output(cmd, timeout=_LIST_MODELS_TIMEOUT)  # stdin closed, new session


def read_models(
    agent: Path, *, run_output: Callable[[list[str]], str] = _run_list_models
) -> tuple[str, ...] | None:
    """`cursor-agent --list-models` ids, or None when the list cannot be read (D-20)."""
    try:
        models = parse_models(run_output([str(agent), "--list-models"]))
    except (run.CommandError, OSError):
        return None
    return models or None
