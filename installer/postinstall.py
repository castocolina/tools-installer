"""Closed, code-owned postinstall-hook dispatch table.

Mirrors installer.executors's `smoke` pattern: a registry `postinstall` field
names a hook from this closed set and can never carry a literal command. Every
hook runs through the same `Runner` seam every other executor uses
(installer/run.py). A hook never raises: it returns a `HookOutcome`, and
installer/engine.py::install_tool treats a warning as non-fatal, because the
binary the succeeding method just installed is usable regardless.

Hosts come from one list, `present_harnesses` in this module (CONF-03). A hook
registers for the present, supported hosts its receipt does not record yet, and
records what it registered in `receipt.hooks`, so removal can undo exactly that.
"""

import os
import shutil
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from installer import agent_settings, receipts
from installer.locations import bin_dir
from installer.model import HARNESS_MARKER_DIRS, Method, Tool
from installer.run import CommandError, NotingRunner, Runner, command_error_line, run_query

# (harness ids registered, warning). A warning never fails the install.
HookOutcome = tuple[tuple[str, ...], str | None]

# Harness id -> catalog id, for display only (UI-SPEC U10). Receipts store harness ids.
HOST_CATALOG_IDS: dict[str, str] = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor": "cursor-agent",
}


# Command names verified on this host 2026-10-09, plus binaries named in
# https://github.com/obra/superpowers/blob/main/README.md (agy, devin, grok,
# qwen, hermes, muse). factory-droid `.factory` and gemini-cli `.gemini` are
# the global roots in https://github.com/vercel-labs/skills/blob/main/README.md
# (Droid ~/.factory/skills, Gemini CLI ~/.gemini/skills). antigravity, windsurf,
# kilo, and kimi dirs are the opengsd resolver defaults in
# .claude/gsd-core/references/gsd-run-resolver.md. Devin/Grok/Qwen/Hermes/Muse
# docs disagree on a config dir, so those disk tuples stay empty.
_HARNESS_COMMANDS: dict[str, tuple[str, ...]] = {
    "antigravity": ("agy",),
    "claude": ("claude",),
    "codex": ("codex",),
    "copilot": ("copilot",),
    "cursor": ("cursor-agent", "cursor"),
    "devin": ("devin",),
    "factory-droid": ("droid",),
    "gemini-cli": ("gemini",),
    "grok": ("grok",),
    "hermes": ("hermes",),
    "kilo": (),
    "kimi": (),
    "muse": ("muse",),
    "opencode": ("opencode",),
    "pi": ("pi",),
    "qwen": ("qwen",),
    "windsurf": (),
}
# Marker dirs come from model.HARNESS_MARKER_DIRS, the same denylist config_paths uses.
HARNESS_PRESENCE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    harness: (commands, HARNESS_MARKER_DIRS[harness])
    for harness, commands in _HARNESS_COMMANDS.items()
}


def present_harnesses(home: Path, which: Callable[[str], str | None]) -> frozenset[str]:
    """Hosts detectable from PATH or a closed home-relative marker."""
    found: set[str] = set()
    for harness, (commands, markers) in HARNESS_PRESENCE.items():
        if any(which(command) for command in commands) or any(
            (home / marker).exists() for marker in markers
        ):
            found.add(harness)
    return frozenset(found)


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


def which_with_brew(name: str) -> str | None:
    """Resolve an executable like `shutil.which`, falling back to well-known
    Homebrew prefixes checked by disk presence.

    CR-04: on an immutable host -- Bazzite, the only host class this phase
    targets -- registry.toml's zsh entry has no rpm-ostree method and
    installs via the brew method (`formula = "zsh"`). `engine.py` only calls
    `prepend_path` for a method whose params include `bin_dir`, and the brew
    method declares none, so `/home/linuxbrew/.linuxbrew/bin` is never added
    to THIS process's own PATH. Immediately after the install this phase
    exists to react to, a bare `shutil.which("zsh")` still returned `None` in
    that same process, and the synchronizer took its revert branch instead of
    configuring anything -- silently, on the exact host this phase was built
    for. Reuses the fix pattern this project already has for the identical
    chicken-and-egg problem (`_resolve_binary`, `BREW_BIN_DIRS`).
    """
    found = shutil.which(name)
    if found:
        return found
    for brew_dir in BREW_BIN_DIRS:
        candidate = brew_dir / name
        if candidate.exists():
            return str(candidate)
    return None


def _resolve_binary(method: Method, cmd: str) -> str:
    """Absolute path of a hook's binary: `which_with_brew` for a brew install, else the
    method's bin_dir (only reached for a non-brew method, which never reaches the brew branch)."""
    if method.kind == "brew":
        found = which_with_brew(cmd)
        if found:
            return found
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
    unrequested write. `--no-permissions` skips codegraph's Claude auto-allow list
    only: for claude it still writes a UserPromptSubmit hook into settings.json and
    creates ~/.claude/CLAUDE.md, and has no flag to skip them (CLAUDE_EXTRAS).
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
        return (), f"codegraph MCP registration failed: {command_error_line(exc)}"
    return tuple(sorted(harnesses)), None


# What a tool's own installer writes for claude beyond MCP registration, shown with
# the hook line; `codegraph uninstall` removes both (UAT F-2).
CLAUDE_EXTRAS: Mapping[str, str] = {
    "codegraph": "claude: codegraph also adds a prompt hook and ~/.claude/CLAUDE.md",
}


def _codegraph_unregister(binary: str, harnesses: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """codegraph's own uninstall for exactly these hosts; `--keep-cli` leaves the binary."""
    csv = ",".join(_CODEGRAPH_TARGETS[harness] for harness in harnesses)
    return ((binary, "uninstall", "--target", csv, "--location", "global", "--yes", "--keep-cli"),)


# herdr's own target ids (herdr 0.9.3: `herdr integration install <TARGET>`).
_HERDR_TARGETS: Mapping[str, str] = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor": "cursor",
}

# herdr's workspace separator and current indicator (24 D-12): the user's own plugin, pinned to a
# full commit that `herdr plugin install --ref` fetches exactly. Not an agent host: it is a
# standalone target of the herdr hook, recorded as "sidebar-markers" and undone like a host.
_SIDEBAR_ID = "sidebar-markers"
_SIDEBAR_SOURCE = "castocolina/herdr-setup/plugins/workspace-here"
_SIDEBAR_REF = "2b5ca2aedf06a5a988a5087da22e65b469ffc84d"
_SIDEBAR_PLUGIN = "herdr-setup.markers"


def _run_herdr_query(argv: list[str]) -> str | None:
    """Stdout of a read-only herdr command: its output on exit 0, the captured output of a
    non-zero exit when it holds any, None when nothing came back (launch failure, timeout)."""
    try:
        return run_query(argv)
    except CommandError as exc:
        return exc.stdout or None


# Replaceable like executors.launch_puppeteer: tests never launch the real herdr.
herdr_query: Callable[[list[str]], str | None] = _run_herdr_query


def _herdr_sidebar(binary: str, runner: Runner) -> tuple[bool, str | None]:
    """Install the pinned sidebar plugin, write its rows, reload. (recorded, warning)."""
    try:
        runner([binary, "plugin", "install", "--ref", _SIDEBAR_REF, "--yes", _SIDEBAR_SOURCE])
    except CommandError as exc:
        return False, f"sidebar markers: {command_error_line(exc)}"
    notes: list[str] = []
    # herdr's settings path does not depend on the OS: it resolves ~/.config/herdr on macOS too
    # (src/config/io.rs), so a hook, which gets no Platform, passes "linux".
    written = agent_settings.apply_setting(
        "herdr", "sidebar", home=Path.home(), platform_os="linux", environ=os.environ
    )
    if written.refused is not None:
        notes.append(f"sidebar rows not written: {written.refused.splitlines()[0]}")
    elif any(key.kind == "wrote" for key in written.keys):
        try:
            runner([binary, "server", "reload-config"])
        except CommandError as exc:
            notes.append(f"herdr reload-config failed ({command_error_line(exc)}); restart herdr")
    return True, "; ".join(notes) or None


def _herdr_register(method: Method, runner: Runner, harnesses: tuple[str, ...]) -> HookOutcome:
    """Register herdr's integration per host, then the sidebar; a failure never stops the rest."""
    binary = _resolve_binary(method, "herdr")
    done: list[str] = []
    failures: list[str] = []
    for harness in harnesses:
        if harness == _SIDEBAR_ID:
            continue
        try:
            runner([binary, "integration", "install", _HERDR_TARGETS[harness]])
        except CommandError as exc:
            failures.append(f"{harness}: {command_error_line(exc)}")
        else:
            done.append(harness)
    if _SIDEBAR_ID in harnesses:
        recorded, warning = _herdr_sidebar(binary, runner)
        if recorded:
            done.append(_SIDEBAR_ID)
        if warning:
            failures.append(warning)
    return tuple(done), "; ".join(failures) or None


def _herdr_unregister(binary: str, harnesses: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Integration undos first, the plugin last."""
    undo = [
        (binary, "integration", "uninstall", _HERDR_TARGETS[h])
        for h in harnesses
        if h in _HERDR_TARGETS
    ]
    if _SIDEBAR_ID in harnesses:
        undo.append((binary, "plugin", "uninstall", _SIDEBAR_PLUGIN))
    return tuple(undo)


def _tealdeer_cache(method: Method, runner: Runner, _harnesses: tuple[str, ...]) -> HookOutcome:
    """Fill tldr's page cache after install and after `u`. A failure is a warning, never
    a row failure: the binary the method installed is usable without the cache."""
    if isinstance(runner, NotingRunner):
        runner.note("fetching the tldr page cache — tldr --update")
    try:
        runner([_resolve_binary(method, "tldr"), "--update"])
    except CommandError as exc:
        return (), f"tldr --update failed: {command_error_line(exc)}; run it yourself later"
    return (), None


@dataclass(frozen=True)
class HookPair:
    """One hook. `targets` maps a harness id to the vendor's own target id; `None`
    marks a host-independent hook. `unregister` builds the undo argvs for the hosts
    it is given; `None` when the hook has no undo. `standalone` maps ids wanted on every
    machine regardless of agent hosts to their vendor source: recorded and undone like a
    host, never a harness (`host_labels` drops them). `settled` is the hook's own read-only
    status: the ids already satisfied, so the drift fact never reads them as pending."""

    targets: Mapping[str, str] | None
    register: Callable[[Method, Runner, tuple[str, ...]], HookOutcome]
    unregister: Callable[[str, tuple[str, ...]], tuple[tuple[str, ...], ...]] | None = None
    standalone: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    settled: Callable[[str, Callable[[list[str]], str | None]], frozenset[str]] | None = None


POSTINSTALL_HOOKS: dict[str, HookPair] = {
    "codegraph-mcp-register": HookPair(
        targets=_CODEGRAPH_TARGETS,
        register=_codegraph_register,
        unregister=_codegraph_unregister,
    ),
    "herdr-integration": HookPair(
        targets=_HERDR_TARGETS,
        register=_herdr_register,
        unregister=_herdr_unregister,
        standalone={_SIDEBAR_ID: _SIDEBAR_SOURCE},
    ),
    "tealdeer-cache": HookPair(targets=None, register=_tealdeer_cache),
}


def unregister_hosts(name: str, recorded: tuple[str, ...]) -> tuple[str, ...]:
    """The recorded hosts hook `name` can undo, in target-map order (D-04).

    `recorded` comes from a receipt a user can hand-edit, so it is filtered through
    the code-owned target and standalone maps: an id outside them (`all`, `auto`, a path)
    is dropped.
    """
    pair = POSTINSTALL_HOOKS.get(name)
    if pair is None or pair.targets is None or pair.unregister is None:
        return ()
    return tuple(known for known in (*pair.targets, *pair.standalone) if known in recorded)


def unregister_argvs(
    name: str, binary: str, recorded: tuple[str, ...]
) -> tuple[tuple[str, ...], ...]:
    """The argvs that undo hook `name` for the recorded hosts only (D-04).

    Nothing left, or no undo for this hook, is `()`.
    """
    wanted = unregister_hosts(name, recorded)
    pair = POSTINSTALL_HOOKS.get(name)
    if pair is None or pair.unregister is None or not wanted:
        return ()
    return pair.unregister(binary, wanted)


def hook_method(tool: Tool, receipt: receipts.Receipt) -> Method | None:
    """The method a receipt was written for: the keyed match, else the only method of
    the receipt's kind, else None. The one rule for "which method was this receipt
    written for"; removal uses it too, so the two cannot disagree."""
    keyed = [method for method in tool.methods if receipts.method_key(method) == receipt.method.key]
    if keyed:
        return keyed[0]
    same_kind = [method for method in tool.methods if method.kind == receipt.method.kind]
    return same_kind[0] if len(same_kind) == 1 else None


def host_labels(hosts: Iterable[str]) -> str:
    """Catalog ids of harness ids, sorted and comma-joined for display (UI-SPEC U10).

    A standalone target (herdr's `sidebar-markers`) is not an agent host and is dropped, so the
    result is "" when only those are left: callers print their host sentence only when it is not.
    """
    return ", ".join(
        sorted(HOST_CATALOG_IDS.get(host, host) for host in hosts if host in HARNESS_PRESENCE)
    )


def run_postinstall(
    name: str, method: Method, runner: Runner, hosts: frozenset[str]
) -> HookOutcome:
    """Run hook `name` for the harnesses in `hosts` that it supports, in target-map order,
    then the standalone ids in `hosts`.

    An unknown name, or no supported host present, runs nothing and returns ((), None).
    """
    pair = POSTINSTALL_HOOKS.get(name)
    if pair is None:
        return (), None
    if pair.targets is None:
        return pair.register(method, runner, ())
    wanted = tuple(known for known in (*pair.targets, *pair.standalone) if known in hosts)
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
    wanted = (present | frozenset(pair.standalone)) - recorded
    registered, warning = run_postinstall(name, method, runner, wanted)
    # An empty entry is recorded too: "hooks known, none registered yet" is swept for the
    # next host, unlike a receipt written before hooks were recorded (CR-06).
    if registered or name not in receipt.hooks:
        try:
            receipts.record_hooks(tool.id, name, registered)
        except OSError as exc:
            note = f"hook hosts not recorded: {next(iter(str(exc).splitlines()), 'OSError')}"
            warning = f"{warning}; {note}" if warning else note
    return registered, warning
