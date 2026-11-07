"""Closed, code-owned postinstall-hook dispatch table.

Mirrors installer.executors's `smoke` pattern: a registry `postinstall` field
names a hook from this closed set and can never carry a literal command. Every
hook runs through the same `Runner` seam every other executor uses
(installer/run.py). A hook never raises: it returns a `HookOutcome`, and
installer/engine.py::install_tool treats a warning as non-fatal, because the
binary the succeeding method just installed is usable regardless.

Hosts come from one list, `skill_lifecycle.present_harnesses` (CONF-03). A hook
registers for the present, supported hosts its receipt does not record yet, and
records what it registered in `receipt.hooks`, so removal can undo exactly that.
"""

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from installer import receipts
from installer.locations import bin_dir
from installer.model import Method, Tool
from installer.run import CommandError, Runner
from installer.skill_lifecycle import present_harnesses

# (harness ids registered, warning). A warning never fails the install.
HookOutcome = tuple[tuple[str, ...], str | None]

# Harness id -> catalog id, for display only (UI-SPEC U10). Receipts store harness ids.
HOST_CATALOG_IDS: dict[str, str] = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor": "cursor-agent",
}


def present_hosts() -> frozenset[str]:
    """Harness ids present on this machine, from `present_harnesses`.

    A marker dir (~/.claude, ~/.cursor, ~/.config/opencode, ~/.opencode) counts
    even when its CLI is not on PATH (research Pitfall 6).
    """
    return present_harnesses(Path.home(), shutil.which)


def _resolve_bin_override(method: Method) -> str | None:
    """A method's declared `bin_dir` param, or None to fall back to the default."""
    raw = method.params.get("bin_dir")
    return raw if isinstance(raw, str) and raw else None


# Well-known Homebrew prefixes, checked by disk presence rather than PATH
# probing: right after a brew install, `brew`'s own bin dir may not yet be on
# THIS process's PATH, but the directory itself already exists on disk.
#
# Public (not `_`-prefixed): installer/terminal_shell.py's brew-installed zsh
# discovery (CR-04) reuses this exact fix pattern.
BREW_BIN_DIRS: tuple[Path, ...] = (
    Path("/opt/homebrew/bin"),  # Apple Silicon
    Path("/usr/local/bin"),  # Intel macOS
    Path("/home/linuxbrew/.linuxbrew/bin"),  # Linuxbrew
)


def _resolve_binary(method: Method, cmd: str) -> str:
    """Absolute path of a hook's binary: `shutil.which` for a brew install already on
    PATH, else a well-known brew prefix checked by disk presence, else the method's
    bin_dir (only reached for a non-brew method, which never reaches the brew branch)."""
    if method.kind == "brew":
        found = shutil.which(cmd)
        if found:
            return found
        for brew_dir in BREW_BIN_DIRS:
            candidate = brew_dir / cmd
            if candidate.exists():
                return str(candidate)
    return str(bin_dir(_resolve_bin_override(method)) / cmd)


# codegraph's `--target` ids, keyed by harness id. The catalog id `cursor-agent`
# is the display name of the `cursor` harness (HOST_CATALOG_IDS).
_CODEGRAPH_TARGETS: Mapping[str, str] = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor": "cursor",
}


def _codegraph_register(method: Method, runner: Runner, harnesses: tuple[str, ...]) -> HookOutcome:
    """Register codegraph's MCP server for `harnesses` in one explicit `--target` CSV.

    Never `--target auto`: codegraph registers claude when it detects no host, an
    unrequested write. `--no-permissions` keeps the call to MCP registration, since
    codegraph's `--yes` also enables a Claude auto-allow list and a UserPromptSubmit hook.
    """
    csv = ",".join(_CODEGRAPH_TARGETS[harness] for harness in harnesses)
    argv = [
        _resolve_binary(method, "codegraph"),
        "install",
        "--target",
        csv,
        "--location",
        "global",
        "--yes",
        "--no-permissions",
    ]
    try:
        runner(argv)
    except CommandError as exc:
        return (), f"codegraph MCP registration failed: {exc}"
    return tuple(sorted(harnesses)), None


@dataclass(frozen=True)
class HookPair:
    """One hook. `targets` maps a harness id to the vendor's own target id; `None`
    marks a host-independent hook. `unregister` is filled by a later plan."""

    targets: Mapping[str, str] | None
    register: Callable[[Method, Runner, tuple[str, ...]], HookOutcome]
    unregister: Callable[[str, tuple[str, ...]], tuple[tuple[str, ...], ...]] | None = None


POSTINSTALL_HOOKS: dict[str, HookPair] = {
    "codegraph-mcp-register": HookPair(targets=_CODEGRAPH_TARGETS, register=_codegraph_register),
}


def run_postinstall(
    name: str, method: Method, runner: Runner, hosts: frozenset[str]
) -> HookOutcome:
    """Run hook `name` for the harnesses in `hosts` that it supports, in target-map order.

    An unknown name, or no supported host present, runs nothing and returns ((), None).
    """
    pair = POSTINSTALL_HOOKS.get(name)
    if pair is None:
        return (), None
    if pair.targets is None:
        return pair.register(method, runner, ())
    wanted = tuple(harness for harness in pair.targets if harness in hosts)
    if not wanted:
        return (), None
    return pair.register(method, runner, wanted)


def register_hooks(
    tool: Tool, method: Method, runner: Runner, hosts: frozenset[str] | None = None
) -> HookOutcome:
    """Register the tool's hook for the present hosts its receipt does not record yet.

    `hosts=None` reads `present_hosts()` at call time, after the method's PATH
    prepend, so a host installed earlier in the same run is seen. A targeted hook
    needs a receipt to record its hosts in (removal unregisters only what the
    receipt records), so with no receipt nothing runs (review R1-08).

    shortcut: a host the user removed by hand is registered again while its marker
    dir remains; upgrade when present_harnesses tells a CLI from a marker dir.
    """
    name = tool.postinstall or ""
    pair = POSTINSTALL_HOOKS.get(name)
    if pair is None:
        return (), None
    if pair.targets is None:
        return run_postinstall(name, method, runner, frozenset())
    receipt = receipts.read(tool.id)
    if receipt is None:
        return (), "hook not registered: no install receipt to record it in"
    present = present_hosts() if hosts is None else hosts
    recorded = frozenset(receipt.hooks.get(name, ()))
    registered, warning = run_postinstall(name, method, runner, present - recorded)
    if registered:
        try:
            receipts.record_hooks(tool.id, name, registered)
        except OSError as exc:
            note = f"hook hosts not recorded: {next(iter(str(exc).splitlines()), 'OSError')}"
            warning = f"{warning}; {note}" if warning else note
    return registered, warning
