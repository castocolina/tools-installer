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

from collections.abc import Callable, Mapping

from installer.locations import bin_dir
from installer.model import Method, Tool
from installer.run import CommandError, Runner
from installer.status import is_installed

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
    present = [
        target
        for tool_id, target in _CODEGRAPH_TARGETS.items()
        if (tool := tools.get(tool_id)) is not None and is_installed(tool)
    ]
    if not present:
        return None
    csv = ",".join(present)
    bin_dir_param = method.params.get("bin_dir")
    bin_dir_override = bin_dir_param if isinstance(bin_dir_param, str) and bin_dir_param else None
    codegraph_bin = str(bin_dir(bin_dir_override) / "codegraph")
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


POSTINSTALL_HOOKS: dict[str, PostinstallHook] = {
    "codegraph-mcp-register": _codegraph_mcp_register,
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
