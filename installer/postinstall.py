"""Closed, code-owned postinstall-hook dispatch table.

Mirrors installer.executors's `smoke` pattern: a registry `postinstall` field
names an action from this closed set and can never carry a literal command.
Every hook runs through the same `Runner` seam every other executor uses
(installer/run.py). A hook never raises -- it returns `None` on success or a
documented no-op, or a short string describing what went wrong, and
installer/engine.py::install_tool treats that string as a non-fatal warning
that never marks the tool's own install as failed, because the binary the
succeeding method just installed is on PATH and usable regardless.
"""

import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from installer.locations import bin_dir, ensure_dir
from installer.model import Method, Tool
from installer.run import CommandError, Runner
from installer.status import is_installed

# The four canonical agent-host catalog ids every postinstall hook that needs
# host-presence detection shares -- extracted from _codegraph_mcp_register's
# original inline loop (D-03) so _rtk_register and any future per-host hook
# read presence from one place instead of each re-deriving it.
_AGENT_HOST_IDS: tuple[str, ...] = ("claude", "codex", "opencode", "cursor-agent")


def present_agent_hosts(tools: Mapping[str, Tool]) -> frozenset[str]:
    """Which of the four canonical agent-host catalog ids are actually installed.

    A host id absent from `tools` entirely behaves exactly like a present-but-
    not-installed host: excluded from the result, never a KeyError.

    This is PATH-probe-based (`installer.status.is_installed` -> `shutil.which`),
    so a host installed EARLIER IN THE SAME wizard run may not yet be reflected
    if its own bin dir was not prepended to this process's PATH before this
    check runs (the same same-run detection-lag caveat originally documented
    on codegraph's registry comment -- now shared by every hook that calls
    this function).
    """
    return frozenset(
        host_id
        for host_id in _AGENT_HOST_IDS
        if (tool := tools.get(host_id)) is not None and is_installed(tool)
    )


def _resolve_bin_override(method: Method) -> str | None:
    """A method's declared `bin_dir` param, or None to fall back to the default."""
    raw = method.params.get("bin_dir")
    return raw if isinstance(raw, str) and raw else None


# Every hook receives the succeeded Method, the Runner, and a `tools` mapping
# of catalog id -> Tool for the hosts it may need to check presence for
# (cycle-1 review HIGH 1/HIGH 2: Method-awareness and is_installed-based
# detection are both part of the hook's own signature, not merely available
# in the caller's lexical scope).
PostinstallHook = Callable[[Method, Runner, Mapping[str, Tool]], str | None]

# codegraph's own --target id for Cursor is "cursor", not this project's catalog id
# "cursor-agent" -- a real id mismatch confirmed live against codegraph v1.2.0's own
# installer/targets/registry.js source (09-RESEARCH.md), not a naming preference.
# Declared in this order so a deterministic, declared-order CSV comes out of the
# host-presence filter below with zero extra sorting.
_CODEGRAPH_TARGETS: dict[str, str] = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor-agent": "cursor",
}


def _codegraph_mcp_register(
    method: Method, runner: Runner, tools: Mapping[str, Tool]
) -> str | None:
    """Register codegraph's MCP server for every already-installed agent host.

    D-02's host-presence-aware composition: this NEVER passes `--target auto`
    -- 09-RESEARCH.md found codegraph's own `installer/targets/registry.js
    ::resolveTargetFlag` silently falls back to registering `claude` when it
    detects ZERO installed hosts, which would be a machine-visible,
    unrequested config write on a host that was never selected. Instead, an
    explicit `--target` CSV is composed from a live `installer.status
    ::is_installed` host-presence check over `claude`/`codex`/`opencode`/
    `cursor-agent`, mapping `cursor-agent` to codegraph's own `cursor` id.
    When zero hosts are present, this returns `None` without ever invoking
    `codegraph install` -- a documented no-op, not a call with an empty or
    `none` target.

    The binary is invoked by its resolved absolute path
    (installer.locations.bin_dir(...) / "codegraph"), never a bare
    `"codegraph"` relying on the current process's PATH: a fresh
    ~/.local/bin install is not guaranteed to be on PATH yet (PATH wiring is
    a separate, later configure_path/`make fix` step).

    REQ-postinstall-idempotency-live-check is satisfied by this function's
    own live is_installed-based host-presence check (never re-registering an
    absent host) plus codegraph's own idempotent config-merge behavior
    (`codegraph install` merges into each target's own config file rather
    than duplicating an entry) -- neither side needs a new state-tracking
    database.

    REQ-postinstall-noninteractive-only: `--yes` plus always passing explicit
    `--target`/`--location` values guarantees this call never reaches an
    interactive prompt (codegraph's own `--yes` help text -- "Non-interactive:
    defaults to --location=global --target=auto" -- only applies its OWN
    defaults for a flag NOT otherwise given, and both are always given here).
    `--no-permissions` is always passed too: codegraph's own `--yes` help text
    documents that flag as ALSO enabling a Claude Code auto-allow permissions
    list and a `UserPromptSubmit` hook, not merely skipping interactive
    prompts -- a broader behavior change than REQ-codegraph-mcp-postinstall's
    literal scope ("run its global MCP-registration step"). `--no-permissions`
    is documented as Claude-only and a no-op for any other target, so passing
    it unconditionally keeps this call scoped to registration only, for every
    target, without needing to special-case Claude's presence in the CSV.
    """
    present_hosts = present_agent_hosts(tools)
    present = [target for tool_id, target in _CODEGRAPH_TARGETS.items() if tool_id in present_hosts]
    if not present:
        return None
    csv = ",".join(present)
    codegraph_bin = str(bin_dir(_resolve_bin_override(method)) / "codegraph")
    try:
        runner(
            [
                codegraph_bin,
                "install",
                "--target",
                csv,
                "--location",
                "global",
                "--yes",
                "--no-permissions",
            ]
        )
    except CommandError as exc:
        return f"codegraph MCP registration failed: {exc}"
    return None


# rtk's per-host `rtk init` argv, live-verified against v0.49.0 (2026-09-11,
# see installer/registry.toml's rtk entry for the dated comment) in an
# isolated scratch $HOME -- never this argv table run against the current
# process's real $HOME. `codex` never receives --auto-patch: `--codex`
# mode never patches settings.json, and rtk rejects the combination outright
# (`rtk: --codex cannot be combined with --auto-patch`, confirmed live).
_RTK_HOST_ARGS: dict[str, tuple[str, ...]] = {
    "claude": ("-g", "--auto-patch"),
    "opencode": ("-g", "--opencode", "--auto-patch"),
    "codex": ("-g", "--codex"),
    "cursor-agent": ("-g", "--agent", "cursor", "--auto-patch"),
}

# Live-verified (2026-09-11, v0.49.0): `rtk init -g --auto-patch` fails with
# exit 1 ("Failed to write RTK.md ... No such file or directory") when
# ~/.claude/ does not already exist -- it never creates the directory
# itself. In practice Claude Code creates this directory on first run, so a
# host where is_installed("claude") is true almost always already has it;
# ensure_dir is a cheap, non-destructive guard against the rare case it does
# not. Same finding for `--agent cursor` and ~/.cursor/ (Pitfall 3).
_RTK_HOST_CONFIG_DIR: dict[str, str] = {
    "claude": ".claude",
    "cursor-agent": ".cursor",
}


# Well-known Homebrew prefixes, checked by disk presence rather than PATH
# probing -- the same "bootstrap chicken-and-egg" reasoning
# installer/shellrc.py::collect_bin_dirs already documents: right after a
# brew install, `brew`'s own bin dir may not yet be on THIS process's PATH,
# but the directory itself already exists on disk. `bin_dir(None)`
# (~/.local/bin) is this project's own userspace install location for
# github_release-installed tools -- a brew install never writes there, so
# falling back to it when shutil.which misses would resolve to a path
# guaranteed not to contain the binary.
_BREW_BIN_DIRS: tuple[Path, ...] = (
    Path("/opt/homebrew/bin"),  # Apple Silicon
    Path("/usr/local/bin"),  # Intel macOS
    Path("/home/linuxbrew/.linuxbrew/bin"),  # Linuxbrew
)


def _resolve_rtk_binary(method: Method) -> str:
    """Resolve rtk's absolute binary path: `shutil.which` for a brew install
    already on PATH, else a well-known brew prefix checked by disk presence,
    else the method's declared/default bin_dir (mirrors
    _codegraph_mcp_register's own github_release resolution -- only reached
    for a github_release method, which brew never uses)."""
    if method.kind == "brew":
        found = shutil.which("rtk")
        if found:
            return found
        for brew_dir in _BREW_BIN_DIRS:
            candidate = brew_dir / "rtk"
            if candidate.exists():
                return str(candidate)
    return str(bin_dir(_resolve_bin_override(method)) / "rtk")


def _rtk_register(method: Method, runner: Runner, tools: Mapping[str, Tool]) -> str | None:
    """Register rtk's hook for every already-installed agent host in
    _RTK_HOST_ARGS's declared order. A CommandError on one host is captured
    as a partial warning while the loop continues to the remaining hosts --
    unlike codegraph's single CSV call, each host gets its own `rtk init`
    invocation (they are independent commands, not one composed argv).

    `cursor-agent`'s branch is gated on `claude` ALSO being present: live
    verification against v0.49.0 confirmed rtk's `--agent cursor` mode still
    unconditionally also writes Claude Code's RTK.md/settings.json as a side
    effect (Pitfall 1, unchanged from the stale v0.44.1 research) -- writing
    Claude-Code-specific scaffolding on a machine that never selected/
    installed Claude Code would be exactly the D-01a violation this phase
    exists to prevent, so this is a documented, silent narrowing rather than
    an unconditional call.
    """
    present = present_agent_hosts(tools)
    if not present:
        return None
    rtk_bin = _resolve_rtk_binary(method)
    errors: list[str] = []
    for host_id in _RTK_HOST_ARGS:
        if host_id not in present:
            continue
        if host_id == "cursor-agent" and "claude" not in present:
            continue
        config_dir = _RTK_HOST_CONFIG_DIR.get(host_id)
        if config_dir:
            ensure_dir(Path.home() / config_dir)
        try:
            runner([rtk_bin, "init", *_RTK_HOST_ARGS[host_id]])
        except CommandError as exc:
            errors.append(f"{host_id}: {exc}")
    return "; ".join(errors) if errors else None


# graphify's per-host subcommand form is `graphify <host> install`, NOT the
# `graphify install --platform <host>` form -- both shapes exist across the
# full set of hosts graphify itself supports, but claude/opencode/codex/
# cursor-agent (this project's four catalog hosts) all use the dedicated
# `<host> install` subcommand (confirmed live via `graphify --help`).
# cursor-agent's catalog id maps to graphify's own "cursor" subcommand name --
# the same id mapping _CODEGRAPH_TARGETS already uses.
_GRAPHIFY_HOST_SUBCOMMANDS: dict[str, str] = {
    "claude": "claude",
    "opencode": "opencode",
    "codex": "codex",
    "cursor-agent": "cursor",
}


def _graphify_register(method: Method, runner: Runner, tools: Mapping[str, Tool]) -> str | None:
    """Register graphify for every already-installed agent host, one
    `graphify <host> install` invocation per host (never a composed CSV --
    unlike codegraph, graphify has no multi-target flag; Pitfall 4)."""
    present = present_agent_hosts(tools)
    if not present:
        return None
    graphify_bin = str(bin_dir(_resolve_bin_override(method)) / "graphify")
    errors: list[str] = []
    for host_id, subcommand in _GRAPHIFY_HOST_SUBCOMMANDS.items():
        if host_id not in present:
            continue
        try:
            runner([graphify_bin, subcommand, "install"])
        except CommandError as exc:
            errors.append(f"{host_id}: {exc}")
    return "; ".join(errors) if errors else None


POSTINSTALL_HOOKS: dict[str, PostinstallHook] = {
    "codegraph-mcp-register": _codegraph_mcp_register,
    "rtk-register": _rtk_register,
    "graphify-register": _graphify_register,
}


def run_postinstall(
    name: str, method: Method, runner: Runner, tools: Mapping[str, Tool]
) -> str | None:
    """Dispatch a postinstall hook by name; `None` for an unknown name.

    `installer/model.py::load_tools` already rejects an unknown name at load
    time, so an unknown name reaching here should not happen in practice --
    this keeps the function correct in isolation regardless. This function
    itself does not wrap the call in a broader try/except Exception: a hook's
    own contract is to convert its OWN expected failure mode (e.g.
    CommandError) to a returned string; isolation from an UNEXPECTED
    exception is the caller's (install_tool's) responsibility.
    """
    hook = POSTINSTALL_HOOKS.get(name)
    if hook is None:
        return None
    return hook(method, runner, tools)
