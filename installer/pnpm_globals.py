"""Snapshot and reinstall the residual pnpm-managed global set.

pnpm v11 isolates each global-install invocation into its own hash-keyed
directory, so updating pnpm itself loses the previously installed global set
(pnpm#11520, pnpm#11587, already researched in
docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md).

Phase 4's volta redirect fixes this preventively only for commands a user
types; installer/executors.py::_node installs through pnpm by design, so every
kind="node" registry tool is still a pnpm-managed global and still exposed.

Both this module and _node invoke pnpm by an absolute path resolved with
installer/guards.py::real_pnpm, because installer/run.py::run_command is
subprocess.run, which resolves a bare program name through the live PATH —
and after plan 04-03 the first pnpm on that PATH is this installer's own
argv-conditional wrapper, which would turn add -g into volta install. Naming
the binary by absolute path is what keeps the reinstall on pnpm's
gated-postinstall model.

The snapshot IS the registry, queried live for kind="node". No persisted
state file, matching this codebase's existing all-live-check convention
(status.is_installed, guard_status, has_managed_block).
"""

import shlex
import shutil
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from installer.guards import real_pnpm
from installer.model import Tool
from installer.run import CommandError, Runner, run_command

_EMPTY_PREVIEW = "nothing pnpm-managed to reinstall"
_UNRESOLVABLE_PREVIEW = "pnpm not found on PATH - cannot preview the reinstall."


@dataclass(frozen=True)
class NodeGlobal:
    tool_id: str
    npm_pkg: str
    cmd: str


@dataclass(frozen=True)
class NodeGlobalsReport:
    entries: tuple[NodeGlobal, ...]
    missing: tuple[str, ...]


def node_globals(tools: Iterable[Tool]) -> tuple[NodeGlobal, ...]:
    found: list[NodeGlobal] = []
    for tool in tools:
        method = next((m for m in tool.methods if m.kind == "node"), None)
        if method is None:
            continue
        pkg = method.params.get("npm_pkg")
        if not isinstance(pkg, str) or not pkg:
            continue
        found.append(NodeGlobal(tool_id=tool.id, npm_pkg=pkg, cmd=tool.cmd))
    return tuple(found)


def audit_node_globals(
    tools: Iterable[Tool],
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> NodeGlobalsReport:
    entries = node_globals(tools)
    missing = tuple(entry.tool_id for entry in entries if which(entry.cmd) is None)
    return NodeGlobalsReport(entries=entries, missing=missing)


def reinstall_argv(entries: Sequence[NodeGlobal], *, pnpm: str) -> list[str]:
    """One invocation for the whole set: per-package calls recreate the isolation that loses them.

    `pnpm` is a required keyword because argv[0] must be an absolute path — a bare
    program name would be resolved by subprocess.run through a PATH whose first
    entry is this installer's own pnpm wrapper.
    """
    if not entries:
        raise ValueError("nothing pnpm-managed to reinstall")
    return [pnpm, "add", "-g", *(entry.npm_pkg for entry in entries)]


def reinstall_node_globals(
    tools: Iterable[Tool],
    *,
    runner: Runner = run_command,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
) -> tuple[str, ...]:
    entries = node_globals(tools)
    if not entries:
        return ()
    resolved = resolve_pnpm()
    if resolved is None:
        raise CommandError(["pnpm", "add", "-g"], 127)
    runner(reinstall_argv(entries, pnpm=resolved))
    return tuple(entry.npm_pkg for entry in entries)


def reinstall_preview(
    entries: Sequence[NodeGlobal],
    *,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
) -> str:
    if not entries:
        return _EMPTY_PREVIEW
    resolved = resolve_pnpm()
    if resolved is None:
        return _UNRESOLVABLE_PREVIEW
    return shlex.join(reinstall_argv(entries, pnpm=resolved))
