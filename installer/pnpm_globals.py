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
selected. The registry contributes three things: the command name a package
installs (which is what makes a still-tracked global checkable at all), how
packages must be grouped and build-allowed when they are put back, and what
version range they are pinned to.

The reinstall still replays pnpm's own live set, for the same reason an argv
built from the registry would silently discard every global the user added by
hand. Under pnpm v11's isolation model each package or comma-joined group is
its own hash-keyed install and supersedes nothing else, so the replay puts
each live name back rather than replacing the whole global set in one go.

LIMITATIONS of a name-only snapshot:

- `parse_global_packages` flattens pnpm's JSON to bare package NAMES, so the
  replay knows neither the version a package was at nor which live group it
  belonged to. A package the registry does not know is therefore reinstalled
  at whatever the registry's dist-tag resolves to now, ungrouped — its
  previous version and any hand-created group are not reconstructible from
  the snapshot.
- Consequently a hand-made group of packages this catalog does not declare is
  replayed as separate isolated installs, which can break a peer relationship
  the user set up themselves. This is a known limitation of replaying a
  name-only snapshot, not an oversight; reconstructing it would require
  reading pnpm's per-group project structure, which is out of this phase's
  scope.
- pnpm removes a whole comma group when either member is removed with
  `pnpm remove -g`, so a group this replay creates is also a coupling the
  user inherits.
"""

import json
import shlex
import shutil
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import cast

from installer.executors import run_smoke_check
from installer.guards import real_pnpm
from installer.model import Method, Tool
from installer.run import CommandError, OutputRunner, Runner, run_captured, run_output
from installer.versions import (
    PNPM_ALLOW_BUILD_MIN,
    PNPM_CO_INSTALL_MIN,
    meets_minimum,
    probe_version,
)

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
    """A catalog tool that declares a kind="node" install method.

    `smoke` is the name of the post-install check the method declares, if any.
    It travels with the entry because the check is the only evidence this
    project has that an installed tool still WORKS — `cmd` on PATH proves a
    package manager ran, and nothing more.
    """

    tool_id: str
    npm_pkg: str
    cmd: str
    smoke: str | None = None


@dataclass(frozen=True)
class NodeInstallPolicy:
    """How the registry says node packages must be installed together.

    A declaration, not an installation: intersected with pnpm's live set before
    it affects any argv. `versions` is a tuple of pairs rather than a dict so
    the whole value stays frozen, hashable and order-deterministic.
    """

    groups: tuple[tuple[str, ...], ...] = ()
    allow_build: tuple[str, ...] = ()
    versions: tuple[tuple[str, str], ...] = ()


_EMPTY_POLICY = NodeInstallPolicy()


@dataclass(frozen=True)
class IncompleteGroup:
    """A declared install group pnpm holds only part of.

    `present` are the members pnpm manages globally; `missing` are the ones it
    does not manage at all. This is NOT a split: pnpm is holding nothing apart,
    the peer was never installed globally in the first place.
    """

    present: tuple[str, ...]
    missing: tuple[str, ...]


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

    `split_groups` names declared install groups pnpm is holding apart, and
    `incomplete_groups` names declared groups pnpm holds only part of. Both are
    CONDITIONS, not counts, and both are empty when the state is healthy and
    when nothing could be learned. They are separate fields because they are
    separate machine states with separate remedies to explain: a split group
    has every member installed and pnpm keeping them apart; an incomplete
    group has a member pnpm never installed at all.

    `unhealthy` pairs a tool id with why its declared smoke check failed just
    now. `missing` answers "is the command there"; this answers "does the tool
    work", which a command on PATH has never been evidence of.
    """

    entries: tuple[NodeGlobal, ...]
    missing: tuple[str, ...]
    managed: tuple[str, ...]
    known: bool = True
    split_groups: tuple[tuple[str, ...], ...] = ()
    incomplete_groups: tuple["IncompleteGroup", ...] = ()
    unhealthy: tuple[tuple[str, str], ...] = ()


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
        smoke = method.params.get("smoke")
        found.append(
            NodeGlobal(
                tool_id=tool.id,
                npm_pkg=pkg,
                cmd=tool.cmd,
                smoke=smoke if isinstance(smoke, str) and smoke else None,
            )
        )
    return tuple(found)


def _node_method(tool: Tool) -> Method | None:
    return next((method for method in tool.methods if method.kind == "node"), None)


def _param_pkg_list(method: Method, key: str) -> tuple[str, ...]:
    raw = method.params.get(key)
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in cast(list[object], raw) if isinstance(item, str) and item)


def _param_versions(method: Method) -> tuple[tuple[str, str], ...]:
    raw = method.params.get("versions")
    if not isinstance(raw, dict):
        return ()
    pairs: list[tuple[str, str]] = []
    for name, range_ in cast(dict[object, object], raw).items():
        if isinstance(name, str) and isinstance(range_, str) and name and range_:
            pairs.append((name, range_))
    return tuple(pairs)


def node_install_policy(tools: Iterable[Tool]) -> NodeInstallPolicy:
    """How the catalog DECLARES node packages must be installed together.

    A declaration, not an installation: intersected with pnpm's live set before
    it affects any argv. Walks the first kind="node" method per tool, the same
    way `node_globals` does.

    A group is the method's own `npm_pkg` followed by its `co_install` names,
    emitted only when `co_install` is non-empty. Allowances and version pins
    are concatenated across methods and de-duplicated with `dict.fromkeys`;
    the first pin in catalog order wins. A registry integrity test is what
    keeps a conflicting second declaration from ever reaching this function,
    so it never silently arbitrates a real disagreement.
    """
    groups: list[tuple[str, ...]] = []
    allowances: list[str] = []
    pins: list[tuple[str, str]] = []
    seen_pins: dict[str, str] = {}
    for tool in tools:
        method = _node_method(tool)
        if method is None:
            continue
        pkg = method.params.get("npm_pkg")
        if not isinstance(pkg, str) or not pkg:
            continue
        co_install = _param_pkg_list(method, "co_install")
        if co_install:
            groups.append(tuple(dict.fromkeys([pkg, *co_install])))
        allowances.extend(_param_pkg_list(method, "allow_build"))
        for name, range_ in _param_versions(method):
            if name in seen_pins:
                continue
            seen_pins[name] = range_
            pins.append((name, range_))
    return NodeInstallPolicy(
        groups=tuple(groups),
        allow_build=tuple(dict.fromkeys(allowances)),
        versions=tuple(pins),
    )


def _load_projects(raw: str) -> list[object] | None:
    try:
        data: object = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, (list, dict)):
        return None
    return cast(list[object], data) if isinstance(data, list) else [cast(object, data)]


def _iter_dependencies(projects: list[object]) -> list[tuple[str, object]] | None:
    items: list[tuple[str, object]] = []
    for project in projects:
        if not isinstance(project, dict):
            return None
        groups = cast(dict[str, object], project)
        for group in _DEPENDENCY_GROUPS:
            if group not in groups:
                continue
            block = groups[group]
            if not isinstance(block, dict):
                return None
            items.extend(cast(dict[str, object], block).items())
    return items


def parse_global_packages(raw: str) -> tuple[str, ...] | None:
    """Package names in `pnpm list -g --json` output; None when it is unreadable.

    pnpm prints an array of project objects (one global root), each carrying
    its dependency groups as name -> details maps.
    """
    projects = _load_projects(raw)
    if projects is None:
        return None
    items = _iter_dependencies(projects)
    if items is None:
        return None
    return tuple(dict.fromkeys(name for name, _details in items))


def _install_group_key(details: object) -> str | None:
    """Which pnpm install this package belongs to, or None when pnpm did not say.

    None is NOT "its own group". A package pnpm listed without a `path` is a
    package whose membership was never read, and an unread membership must
    never become a finding — the same rule `NodeGlobalsReport.known` enforces
    for the query as a whole. The previous fallback was a per-package-unique
    sentinel, which made "we could not tell" byte-identical to "this package is
    alone", and `split_install_groups` then reported a healthy machine as split.
    """
    if isinstance(details, dict):
        path = cast(dict[str, object], details).get("path")
        if isinstance(path, str) and path:
            marker = "/node_modules/"
            index = path.find(marker)
            return path[:index] if index != -1 else path
    return None


@dataclass(frozen=True)
class GlobalGroups:
    """pnpm's live install groups, plus the packages whose membership was unreadable.

    `groups` carries every package pnpm listed, so the flat set the replay
    needs is still a projection of it. A package in `unknown` is present in
    `groups` too — in a placeholder group of its own, which keeps the flat
    projection and its order exactly what pnpm printed — but no consumer may
    read that placement as evidence of anything. `unknown` is the marker that
    says so, and it is why placement and verdict are two different fields
    rather than one.
    """

    groups: tuple[tuple[str, ...], ...] = ()
    unknown: tuple[str, ...] = ()

    @property
    def packages(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(name for group in self.groups for name in group))


def parse_global_groups(raw: str) -> GlobalGroups | None:
    """Install groups in `pnpm list -g --json`; None when unreadable.

    pnpm v11 gives each global install invocation its own hash-keyed project
    directory, so the project objects ARE the install groups on some pnpm
    versions. On the pnpm this phase targets, `pnpm list -g --json` emits ONE
    project object holding every global; group membership is the per-package
    `path` hash (the directory above `node_modules`). That is the membership
    `parse_global_packages` deliberately discards, and the reason that
    function is not changed — its callers, including
    `installer/app.py::run_doctor`, want the flat set.

    A package pnpm lists without that `path` is recorded in `unknown` rather
    than being invented into a group of its own.
    """
    projects = _load_projects(raw)
    if projects is None:
        return None
    items = _iter_dependencies(projects)
    if items is None:
        return None
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    unknown: list[str] = []
    for name, details in items:
        key = _install_group_key(details)
        if key is None:
            unknown.append(name)
            # A placeholder key, never a claim: the name still has to reach the
            # flat set the replay puts back, and `unknown` is what stops any
            # consumer reading this placement as a group.
            key = f"unread-membership:{name}"
        members = grouped.get(key)
        if members is None:
            grouped[key] = [name]
            order.append(key)
        elif name not in members:
            members.append(name)
    return GlobalGroups(
        groups=tuple(tuple(grouped[key]) for key in order),
        unknown=tuple(dict.fromkeys(unknown)),
    )


LIST_TIMEOUT_SECONDS = 20.0


def _run_list(argv: list[str]) -> str:
    """The default OutputRunner for the global-set query, bounded in time.

    `pnpm list -g --json` is a QUERY, so waiting forever is never the right
    answer — and pnpm can block indefinitely on store-lock contention. The one
    caller that matters runs inside a Textual thread worker whose result the
    event loop is waiting on, so an unbounded child would leave the Doctor
    "checking pnpm's global set..." with nothing to end it. A timeout surfaces
    as CommandError, which pnpm_global_packages already reads as "unknown".
    """
    return run_output(argv, timeout=LIST_TIMEOUT_SECONDS)


def pnpm_global_packages(
    *,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
    runner_out: OutputRunner = _run_list,
) -> tuple[str, ...] | None:
    """Packages pnpm currently manages globally, or None when pnpm cannot be asked.

    None means "unknown", not "empty". A report built from an unknown set claims
    nothing; one built from an assumed-empty set would claim the user has no
    globals, which is the same kind of guess this module exists to stop making.
    A query that times out is one more way of not being able to ask.
    """
    pnpm = resolve_pnpm()
    if pnpm is None:
        return None
    try:
        raw = runner_out([pnpm, "list", "-g", "--json"])
    except (OSError, CommandError):
        return None
    return parse_global_packages(raw)


def pnpm_global_groups(
    *,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
    runner_out: OutputRunner = _run_list,
) -> GlobalGroups | None:
    """Install groups pnpm currently manages globally, or None when it cannot be asked.

    Same bounded `pnpm list -g --json` query as `pnpm_global_packages`, parsed
    with `parse_global_groups`.
    """
    pnpm = resolve_pnpm()
    if pnpm is None:
        return None
    try:
        raw = runner_out([pnpm, "list", "-g", "--json"])
    except (OSError, CommandError):
        return None
    return parse_global_groups(raw)


def split_install_groups(
    policy: NodeInstallPolicy,
    live: GlobalGroups,
) -> tuple[tuple[str, ...], ...]:
    """Declared groups whose present members pnpm is holding apart.

    The registry says these packages must share one pnpm install group so the
    dependent can resolve its peer, and pnpm is holding them apart.

    Reports only what it READ. A declared group with a member in
    `live.unknown` yields nothing: pnpm listed that package but not its
    membership, and a verdict built on an unread membership is a guess, not a
    finding (`GlobalGroups.unknown`, `NodeGlobalsReport.known`).
    """
    live_sets = [set(group) for group in live.groups]
    present_anywhere = set(live.packages)
    unknown = set(live.unknown)
    found: list[tuple[str, ...]] = []
    for declared in policy.groups:
        present = tuple(name for name in declared if name in present_anywhere)
        if len(present) < 2:
            continue
        if any(name in unknown for name in present):
            continue
        present_set = set(present)
        if any(present_set <= group for group in live_sets):
            continue
        found.append(present)
    return tuple(found)


def incomplete_install_groups(
    policy: NodeInstallPolicy,
    live: GlobalGroups,
) -> tuple[IncompleteGroup, ...]:
    """Declared groups whose dependent pnpm manages while a peer is absent entirely.

    This is the brownfield state every machine that installed `mmdc` from this
    catalog BEFORE phase 5 is in: `@mermaid-js/mermaid-cli` is a global,
    `puppeteer` is not a global at all (at best `autoInstallPeers` pulled a copy
    into mmdc's own tree), and no build allowance was ever granted — so the
    browser was never downloaded and `mmdc` fails at render time.

    `split_install_groups` cannot see it. A split needs two PRESENT members to
    be held apart, and this machine has one, so the Doctor said nothing at all
    to the exact population the split detection was written for.

    Anchored on the group's FIRST member for the same reason `_formed_groups`
    is: that member is the catalog's own `npm_pkg`. A lone PEER is the
    hand-install shape, and calling it an incomplete group would push the user
    at an action that installs a catalog tool they never asked for.

    Membership is irrelevant here, so `live.unknown` is not consulted: this
    asks only whether pnpm listed the package, which it either did or did not.
    """
    present_anywhere = set(live.packages)
    found: list[IncompleteGroup] = []
    for declared in policy.groups:
        if not declared or declared[0] not in present_anywhere:
            continue
        missing = tuple(name for name in declared if name not in present_anywhere)
        if not missing:
            continue
        present = tuple(name for name in declared if name in present_anywhere)
        found.append(IncompleteGroup(present=present, missing=missing))
    return tuple(found)


def _unhealthy(
    entries: tuple[NodeGlobal, ...],
    missing: tuple[str, ...],
    smoke: Callable[[str], str | None],
) -> tuple[tuple[str, str], ...]:
    """Re-run each present entry's declared smoke check and collect the failures.

    A command on PATH is evidence a package manager ran, never evidence the
    tool works. The check fires once on the install path and then never again:
    `installer/engine.py::install_tool` short-circuits on ALREADY_INSTALLED,
    which `installer/status.py::is_installed` answers from PATH presence. So a
    browser that stopped starting after an OS update was reported as installed
    forever, silently — the exact state the check exists to catch, one run
    later. The Doctor is where an already-installed machine's state is audited,
    so the question is asked again here.

    Skips an entry already in `missing`: its command does not resolve, the
    report already warns about it, and the check would fail for that reason.
    """
    condemned: list[tuple[str, str]] = []
    for entry in entries:
        if entry.smoke is None or entry.tool_id in missing:
            continue
        reason = smoke(entry.smoke)
        if reason is not None:
            condemned.append((entry.tool_id, reason))
    return tuple(condemned)


def audit_node_globals(
    tools: Iterable[Tool],
    *,
    which: Callable[[str], str | None] = shutil.which,
    managed: Callable[[], tuple[str, ...] | None] = pnpm_global_packages,
    grouped: Callable[[], GlobalGroups | None] = pnpm_global_groups,
    policy: NodeInstallPolicy = _EMPTY_POLICY,
    smoke: Callable[[str], str | None] = run_smoke_check,
) -> NodeGlobalsReport:
    """Report pnpm's live global set, and the catalog commands in it that are broken."""
    if not policy.groups:
        packages = managed()
        if packages is None:
            # Carry the unknown through rather than collapsing it into an empty
            # report: the empty report is a CLAIM about the user's machine, and
            # this branch is precisely the case where nothing is known.
            return NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)
        entries = tuple(entry for entry in node_globals(tools) if entry.npm_pkg in packages)
        missing = tuple(entry.tool_id for entry in entries if which(entry.cmd) is None)
        return NodeGlobalsReport(
            entries=entries,
            missing=missing,
            managed=packages,
            unhealthy=_unhealthy(entries, missing, smoke),
        )
    # The two queries answer the same question at different resolutions, and
    # running both would double the Doctor's wait for no new information.
    live = grouped()
    if live is None:
        return NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)
    packages = live.packages
    entries = tuple(entry for entry in node_globals(tools) if entry.npm_pkg in packages)
    missing = tuple(entry.tool_id for entry in entries if which(entry.cmd) is None)
    return NodeGlobalsReport(
        entries=entries,
        missing=missing,
        managed=packages,
        split_groups=split_install_groups(policy, live),
        incomplete_groups=incomplete_install_groups(policy, live),
        unhealthy=_unhealthy(entries, missing, smoke),
    )


def _render_spec(name: str, versions: dict[str, str]) -> str:
    pinned = versions.get(name)
    return f"{name}@{pinned}" if pinned is not None else name


def _formed_groups(policy: NodeInstallPolicy, present: set[str]) -> tuple[tuple[str, ...], ...]:
    """Declared groups this replay is entitled to (re)form.

    A group is formed when its FIRST member is in pnpm's live set. That member
    is the catalog tool's own `npm_pkg` (`node_install_policy` builds a group as
    `(npm_pkg, *co_install)`), so its presence is the only provenance signal
    this module has: pnpm's flat name list carries none, and the catalog is
    what puts that dependent on a machine.

    A PEER on its own is not that signal — it is the hand-install shape. Gating
    on live presence instead re-asserted the registry's `--allow-build` for a
    `puppeteer` this installer never touched, and pnpm's own `add`
    documentation records that flag as writing the package into pnpm's build
    allowance configuration, so the package "will always be allowed to run its
    scripts in the future". That is a persistent, package-level,
    version-unbounded grant created by an action labelled "reinstall the
    pnpm-managed global set", on a machine whose user had chosen the opposite
    by never passing the flag. The version pin rode the same predicate and
    moved a hand-held package across a major line.

    RESIDUAL, accepted and bounded: a hand-installed DEPENDENT still lets the
    replay grant its declared peer. Three things bound it — the allowance names
    only a package this same invocation installs, into the group it is forming
    (T-05-09's load-time rule keeps an allowance inside its own install group);
    the Doctor has already told the user that group is split or incomplete, by
    name; and the argv carrying the flag is the preview they pressed `r` on.
    A machine that has NEITHER member is untouched, which is the population
    CR-01 was about.
    """
    return tuple(group for group in policy.groups if group and group[0] in present)


def _reinstall_parts(
    packages: Sequence[str], policy: NodeInstallPolicy
) -> tuple[list[str], list[str]]:
    unique = list(dict.fromkeys(packages))
    present = set(unique)
    versions = dict(policy.versions)
    formed = _formed_groups(policy, present)
    owner: dict[str, tuple[str, ...]] = {}
    for group in formed:
        for member in group:
            owner.setdefault(member, group)
    # Pins and allowances are group-scoped authority, not name-scoped: both
    # apply only to a member of a group this invocation is forming.
    granted = {name for group in formed for name in group}
    consumed: set[str] = set()
    specs: list[str] = []
    for package in unique:
        if package in consumed:
            continue
        group = owner.get(package)
        if group is None:
            specs.append(package)
            consumed.add(package)
            continue
        # Comma versus space is not formatting: space-separated packages in one
        # invocation each get their own isolated install (pnpm Global Packages
        # documentation), which for a peer-dependency pair means the replay
        # silently breaks the dependent.
        #
        # EVERY declared member, not just the live ones. Replaying only what
        # pnpm already listed left the brownfield machine — dependent present,
        # peer never installed — exactly as broken as it started, so the `r`
        # action the Doctor points at repaired nothing for the population it
        # was built for. It is also what keeps the allowance honest: the flag
        # below names a member of this group, and this is the invocation that
        # installs it.
        specs.append(",".join(_render_spec(name, versions) for name in group))
        consumed.update(group)
    flags = [
        f"--allow-build={name}" for name in dict.fromkeys(policy.allow_build) if name in granted
    ]
    return flags, specs


def reinstall_argv(
    packages: Sequence[str],
    *,
    pnpm: str,
    policy: NodeInstallPolicy = _EMPTY_POLICY,
) -> list[str]:
    """One invocation for the whole set: per-package calls recreate the isolation that loses them.

    `packages` is pnpm's own global list, so the invocation puts back everything
    it held — including globals this installer's registry knows nothing about.
    `policy` contributes grouping, pins and build allowances for the packages
    the registry knows; an empty policy keeps today's space-separated argv.

    `pnpm` is a required keyword because argv[0] must be an absolute path — a bare
    program name would be resolved by subprocess.run through a PATH whose first
    entry is this installer's own pnpm wrapper.
    """
    if not packages:
        raise ValueError(_EMPTY_PREVIEW)
    flags, specs = _reinstall_parts(packages, policy)
    return [pnpm, "add", "-g", *flags, *specs]


def _applicable_floor(flags: list[str], specs: list[str]) -> str | None:
    if any("," in spec for spec in specs):
        return PNPM_CO_INSTALL_MIN
    if flags:
        return PNPM_ALLOW_BUILD_MIN
    return None


def reinstall_node_globals(
    packages: Sequence[str],
    *,
    runner: Runner = run_captured,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
    policy: NodeInstallPolicy = _EMPTY_POLICY,
) -> tuple[str, ...]:
    """Replay pnpm's global set in one invocation.

    Returns the package-spec elements that were invoked, never the
    `--allow-build=` flags. The runner captures by default because the only
    caller is the Doctor screen's `r` action, which runs while Textual owns
    the terminal: an inherited-stdio child writes `pnpm add -g`'s progress
    bars straight into the rendered frame.
    """
    if not packages:
        return ()
    resolved = resolve_pnpm()
    if resolved is None:
        raise PnpmUnavailable("pnpm not found on PATH — install pnpm, then retry the reinstall.")
    flags, specs = _reinstall_parts(packages, policy)
    floor = _applicable_floor(flags, specs)
    if floor is not None:
        observed = probe_version([resolved, "--version"])
        if observed is None or not meets_minimum(observed, floor):
            shown = observed if observed is not None else "could not be read"
            raise PnpmUnavailable(
                f"pnpm {shown} does not meet the required minimum {floor}. "
                f"Upgrade pnpm to {floor} or newer, then retry the reinstall."
            )
    argv = reinstall_argv(packages, pnpm=resolved, policy=policy)
    runner(argv)
    return tuple(specs)


def reinstall_preview(
    packages: Sequence[str],
    *,
    known: bool = True,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
    policy: NodeInstallPolicy = _EMPTY_POLICY,
) -> str:
    """The command line a reinstall would run, or why there is none to show.

    `known` is NodeGlobalsReport.known: an unknown global set has no preview and
    must not borrow the empty set's, which tells the user there is nothing to
    reinstall on the one machine where that is the open question.

    The preview shows the argv the reinstall builds and never probes pnpm: the
    version floor is a precondition of running the command, not a different
    command, so this path stays free of subprocesses.
    """
    if not known:
        return _UNKNOWN_PREVIEW
    if not packages:
        return _EMPTY_PREVIEW
    resolved = resolve_pnpm()
    if resolved is None:
        return _UNRESOLVABLE_PREVIEW
    return shlex.join(reinstall_argv(packages, pnpm=resolved, policy=policy))
