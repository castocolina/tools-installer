"""Snapshot and reinstall the pnpm-managed global set.

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

The snapshot is pnpm's OWN live global list (`pnpm list -g --json`), never the
registry catalog. A catalog entry is a DECLARATION that a tool CAN be installed
this way, not evidence that it WAS: treating the catalog as the installed set
told every user who had never installed mmdc that a pnpm self-update had
destroyed their globals, and offered to "reinstall" a package they had never
selected. The registry contributes one thing — the command name a package
installs — which is what makes a still-tracked global checkable at all.

The reinstall replays pnpm's own set for the same reason. One `pnpm add -g`
invocation supersedes whatever the global set currently holds, so an argv built
from the registry would silently discard every global the user added by hand.
"""

import json
import shlex
import shutil
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import cast

from installer.guards import real_pnpm
from installer.model import Tool
from installer.run import CommandError, OutputRunner, Runner, run_captured, run_output

_EMPTY_PREVIEW = "nothing pnpm-managed to reinstall"
_UNRESOLVABLE_PREVIEW = "pnpm not found on PATH — cannot preview the reinstall."
_UNKNOWN_PREVIEW = "pnpm's global set could not be read — cannot preview the reinstall."
_DEPENDENCY_GROUPS = ("dependencies", "devDependencies", "optionalDependencies")


class PnpmUnavailable(OSError):
    """No real pnpm could be resolved, so nothing was executed.

    Subclasses OSError for the reason OmzPluginsError does: ui_common.run_live
    surfaces it under architecture rule 3 with no screen adding an except. A
    CommandError here would render as "command failed (127): pnpm add -g",
    naming a command that never ran — in the bare argv form this module exists
    to avoid.
    """


@dataclass(frozen=True)
class NodeGlobal:
    tool_id: str
    npm_pkg: str
    cmd: str


@dataclass(frozen=True)
class NodeGlobalsReport:
    """What pnpm actually manages globally, and which of it stopped working.

    `managed` is pnpm's own list and is the exact set a reinstall replays.
    `entries` is the part of it the catalog recognises — the only part whose
    command name is known and therefore checkable. `missing` names the entries
    whose command no longer resolves on PATH.

    `known` is the third state the other three fields cannot express: False
    means pnpm could not be asked, so every other field is empty because
    nothing was learned, NOT because pnpm manages nothing. Without it an
    unanswered query is byte-identical to an empty global set, and a consumer
    that renders counts states an unknown as a fact — "0 package(s) in pnpm's
    global set" on the machine whose pnpm has just replaced itself, which is
    the exact machine this module exists for.
    """

    entries: tuple[NodeGlobal, ...]
    missing: tuple[str, ...]
    managed: tuple[str, ...]
    known: bool = True


def node_globals(tools: Iterable[Tool]) -> tuple[NodeGlobal, ...]:
    """Every catalog tool that DECLARES a kind="node" install method.

    A declaration, not an installation: intersect with `pnpm_global_packages`
    before reporting anything about the user's machine.
    """
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


def parse_global_packages(raw: str) -> tuple[str, ...] | None:
    """Package names in `pnpm list -g --json` output; None when it is unreadable.

    pnpm prints an array of project objects (one global root), each carrying
    its dependency groups as name -> details maps.
    """
    try:
        data: object = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, (list, dict)):
        return None
    projects = cast(list[object], data) if isinstance(data, list) else [cast(object, data)]
    names: list[str] = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        groups = cast(dict[str, object], project)
        for group in _DEPENDENCY_GROUPS:
            block = groups.get(group)
            if isinstance(block, dict):
                names.extend(cast(dict[str, object], block))
    return tuple(dict.fromkeys(names))


def pnpm_global_packages(
    *,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
    runner_out: OutputRunner = run_output,
) -> tuple[str, ...] | None:
    """Packages pnpm currently manages globally, or None when pnpm cannot be asked.

    None means "unknown", not "empty". A report built from an unknown set claims
    nothing; one built from an assumed-empty set would claim the user has no
    globals, which is the same kind of guess this module exists to stop making.
    """
    pnpm = resolve_pnpm()
    if pnpm is None:
        return None
    try:
        raw = runner_out([pnpm, "list", "-g", "--json"])
    except (OSError, CommandError):
        return None
    return parse_global_packages(raw)


def audit_node_globals(
    tools: Iterable[Tool],
    *,
    which: Callable[[str], str | None] = shutil.which,
    managed: Callable[[], tuple[str, ...] | None] = pnpm_global_packages,
) -> NodeGlobalsReport:
    """Report pnpm's live global set, and the catalog commands in it that are broken."""
    packages = managed()
    if packages is None:
        # Carry the unknown through rather than collapsing it into an empty
        # report: the empty report is a CLAIM about the user's machine, and
        # this branch is precisely the case where nothing is known.
        return NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)
    entries = tuple(entry for entry in node_globals(tools) if entry.npm_pkg in packages)
    missing = tuple(entry.tool_id for entry in entries if which(entry.cmd) is None)
    return NodeGlobalsReport(entries=entries, missing=missing, managed=packages)


def reinstall_argv(packages: Sequence[str], *, pnpm: str) -> list[str]:
    """One invocation for the whole set: per-package calls recreate the isolation that loses them.

    `packages` is pnpm's own global list, so the invocation that supersedes the
    current global set puts back everything it held — including globals this
    installer's registry knows nothing about.

    `pnpm` is a required keyword because argv[0] must be an absolute path — a bare
    program name would be resolved by subprocess.run through a PATH whose first
    entry is this installer's own pnpm wrapper.
    """
    if not packages:
        raise ValueError(_EMPTY_PREVIEW)
    return [pnpm, "add", "-g", *dict.fromkeys(packages)]


def reinstall_node_globals(
    packages: Sequence[str],
    *,
    runner: Runner = run_captured,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
) -> tuple[str, ...]:
    """Replay pnpm's global set in one invocation.

    The runner captures by default because the only caller is the Doctor
    screen's `r` action, which runs while Textual owns the terminal: an
    inherited-stdio child writes `pnpm add -g`'s progress bars straight into
    the rendered frame.
    """
    if not packages:
        return ()
    resolved = resolve_pnpm()
    if resolved is None:
        raise PnpmUnavailable("pnpm not found on PATH — install pnpm, then retry the reinstall.")
    argv = reinstall_argv(packages, pnpm=resolved)
    runner(argv)
    return tuple(argv[3:])


def reinstall_preview(
    packages: Sequence[str],
    *,
    known: bool = True,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
) -> str:
    """The command line a reinstall would run, or why there is none to show.

    `known` is NodeGlobalsReport.known: an unknown global set has no preview and
    must not borrow the empty set's, which tells the user there is nothing to
    reinstall on the one machine where that is the open question.
    """
    if not known:
        return _UNKNOWN_PREVIEW
    if not packages:
        return _EMPTY_PREVIEW
    resolved = resolve_pnpm()
    if resolved is None:
        return _UNRESOLVABLE_PREVIEW
    return shlex.join(reinstall_argv(packages, pnpm=resolved))
