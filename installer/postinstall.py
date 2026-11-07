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
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from installer import receipts
from installer.locations import bin_dir
from installer.model import Method, Tool
from installer.run import CommandError, NotingRunner, Runner
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
        return (), f"codegraph MCP registration failed: {_failure_line(exc)}"
    return tuple(sorted(harnesses)), None


def _codegraph_unregister(binary: str, harnesses: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """codegraph's own uninstall for exactly these hosts; `--keep-cli` leaves the binary."""
    csv = ",".join(_CODEGRAPH_TARGETS[harness] for harness in harnesses)
    return ((binary, "uninstall", "--target", csv, "--location", "global", "--yes", "--keep-cli"),)


def _failure_line(exc: CommandError) -> str:
    """The first non-empty line the command printed, else of its message (app.py's rule)."""
    return next((ln for ln in exc.detail.splitlines() if ln.strip()), str(exc).splitlines()[0])


# herdr's own target ids (herdr 0.9.3: `herdr integration install <TARGET>`).
_HERDR_TARGETS: Mapping[str, str] = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor": "cursor",
}


def _herdr_register(method: Method, runner: Runner, harnesses: tuple[str, ...]) -> HookOutcome:
    """Register herdr's integration per host; one host's failure does not stop the others."""
    binary = _resolve_binary(method, "herdr")
    done: list[str] = []
    failures: list[str] = []
    for harness in harnesses:
        try:
            runner([binary, "integration", "install", _HERDR_TARGETS[harness]])
        except CommandError as exc:
            failures.append(f"{harness}: {_failure_line(exc)}")
        else:
            done.append(harness)
    return tuple(done), "; ".join(failures) or None


def _herdr_unregister(binary: str, harnesses: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    return tuple((binary, "integration", "uninstall", _HERDR_TARGETS[h]) for h in harnesses)


def _tealdeer_cache(method: Method, runner: Runner, _harnesses: tuple[str, ...]) -> HookOutcome:
    """Fill tldr's page cache after install and after `u`. A failure is a warning, never
    a row failure: the binary the method installed is usable without the cache."""
    if isinstance(runner, NotingRunner):
        runner.note("fetching the tldr page cache — tldr --update")
    try:
        runner([_resolve_binary(method, "tldr"), "--update"])
    except CommandError as exc:
        return (), f"tldr --update failed: {_failure_line(exc)}; run it yourself later"
    return (), None


@dataclass(frozen=True)
class HookPair:
    """One hook. `targets` maps a harness id to the vendor's own target id; `None`
    marks a host-independent hook. `unregister` builds the undo argvs for the hosts
    it is given; `None` when the hook has no undo."""

    targets: Mapping[str, str] | None
    register: Callable[[Method, Runner, tuple[str, ...]], HookOutcome]
    unregister: Callable[[str, tuple[str, ...]], tuple[tuple[str, ...], ...]] | None = None


POSTINSTALL_HOOKS: dict[str, HookPair] = {
    "codegraph-mcp-register": HookPair(
        targets=_CODEGRAPH_TARGETS,
        register=_codegraph_register,
        unregister=_codegraph_unregister,
    ),
    "herdr-integration": HookPair(
        targets=_HERDR_TARGETS, register=_herdr_register, unregister=_herdr_unregister
    ),
    "tealdeer-cache": HookPair(targets=None, register=_tealdeer_cache),
}


def unregister_hosts(name: str, recorded: tuple[str, ...]) -> tuple[str, ...]:
    """The recorded hosts hook `name` can undo, in target-map order (D-04).

    `recorded` comes from a receipt a user can hand-edit, so it is filtered through
    the code-owned target map: an id outside it (`all`, `auto`, a path) is dropped.
    """
    pair = POSTINSTALL_HOOKS.get(name)
    if pair is None or pair.targets is None or pair.unregister is None:
        return ()
    return tuple(harness for harness in pair.targets if harness in recorded)


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
    """Catalog ids of harness ids, sorted and comma-joined for display (UI-SPEC U10)."""
    return ", ".join(sorted(HOST_CATALOG_IDS.get(host, host) for host in hosts))


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
    # An empty entry is recorded too: "hooks known, none registered yet" is swept for the
    # next host, unlike a receipt written before hooks were recorded (CR-06).
    if registered or name not in receipt.hooks:
        try:
            receipts.record_hooks(tool.id, name, registered)
        except OSError as exc:
            note = f"hook hosts not recorded: {next(iter(str(exc).splitlines()), 'OSError')}"
            warning = f"{warning}; {note}" if warning else note
    return registered, warning
