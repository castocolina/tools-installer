"""Reviewed, typed post-install actions.

Actions receive every external dependency through ``ActionContext``.  The
dispatcher accepts only the fixed handler table below; registry strings never
become shell text.
"""

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from installer.model import Tool
from installer.platform import Platform
from installer.run import (
    InteractiveTerminalUnavailable,
    Runner,
    run_command,
    run_interactive_command,
)
from installer.shellrc import (
    apply_block,
    collect_bin_dirs,
    ensure_source,
    existing_managed_bin_dirs,
    write_myshellrc,
    write_pnpm_home,
)

ActionStatus = Literal["applied", "already-applied", "manual-required", "skipped"]
Which: TypeAlias = Callable[[str], str | None]
Exists: TypeAlias = Callable[[Path], bool]
# (tool id, post-install action name) -- local to this module since the
# InstallPlan/action-key bookkeeping that used to define it belonged to
# local's own UI layer, which origin's app.py/wizard_app.py replaced outright.
ActionKey: TypeAlias = tuple[str, str]

_AGENT_REFERENCE_BEGIN = "# >>> tools-installer agent tooling >>>"
_AGENT_REFERENCE_END = "# <<< tools-installer agent tooling <<<"


@dataclass(frozen=True)
class ActionResult:
    action: str
    status: ActionStatus
    detail: str


class ActionExecutionError(RuntimeError):
    """A reviewed handler failed while applying one named action."""

    def __init__(
        self,
        action: str,
        error: Exception,
        completed: tuple[ActionResult, ...],
    ) -> None:
        self.action = action
        self.error = error
        self.completed = completed
        super().__init__(str(error))


@dataclass(frozen=True)
class ActionContext:
    """Host boundaries and destinations used by reviewed actions."""

    home: Path
    myshellrc: Path
    rc_paths: tuple[Path, ...]
    platform: Platform
    runner: Runner = run_command
    interactive_runner: Runner | None = None
    which: Which = shutil.which
    shells_file: Path = Path("/etc/shells")
    current_shell: str = os.environ.get("SHELL", "")
    agent_reference_paths: tuple[Path, ...] = ()
    exists: Exists = Path.is_dir
    approved_actions: frozenset[ActionKey] = frozenset()
    skipped_actions: frozenset[ActionKey] = frozenset()


def default_action_context(
    platform: Platform,
    runner: Runner = run_command,
    interactive_runner: Runner = run_interactive_command,
) -> ActionContext:
    """Build the production context; tests should pass temporary paths explicitly."""
    home = Path.home()
    return ActionContext(
        home=home,
        myshellrc=home / ".myshellrc",
        rc_paths=(home / ".zshrc", home / ".bashrc"),
        platform=platform,
        runner=runner,
        interactive_runner=interactive_runner,
    )


def _changed(path: Path, apply: Callable[[], None]) -> bool:
    before = path.read_text() if path.exists() else None
    apply()
    return before != path.read_text()


def _approval_required(
    tool: Tool,
    context: ActionContext,
    action: str,
) -> ActionResult | None:
    if action not in tool.post_install:
        return ActionResult(
            action,
            "manual-required",
            f"{action} is not declared for {tool.id}",
        )
    if (tool.id, action) in context.approved_actions:
        return None
    if (tool.id, action) in context.skipped_actions:
        return ActionResult(action, "skipped", "declined by user")
    return ActionResult(
        action,
        "manual-required",
        f"{action} was not approved for {tool.id}",
    )


def configure_path(tool: Tool, context: ActionContext) -> ActionResult:
    """Add one successfully installed tool to the persistent managed PATH block."""
    if unapproved := _approval_required(tool, context, "configure_path"):
        return unapproved
    current = collect_bin_dirs(
        [tool],
        context.platform,
        context.home / ".local" / "bin",
        context.exists,
        home=context.home,
    )
    prior = existing_managed_bin_dirs(context.myshellrc, context.exists)
    bin_dirs = list(dict.fromkeys((*current, *prior)))
    changed = _changed(
        context.myshellrc,
        lambda: write_myshellrc(bin_dirs, context.myshellrc),
    )
    status: ActionStatus = "applied" if changed else "already-applied"
    return ActionResult("configure_path", status, "managed PATH configured")


def source_shell_init(tool: Tool, context: ActionContext) -> ActionResult:
    """Source the managed environment from each approved shell RC path."""
    if unapproved := _approval_required(tool, context, "source_shell_init"):
        return unapproved
    changed = False
    for rc_path in context.rc_paths:
        changed = (
            _changed(rc_path, lambda rc_path=rc_path: ensure_source(rc_path, context.myshellrc))
            or changed
        )
    status: ActionStatus = "applied" if changed else "already-applied"
    return ActionResult(
        "source_shell_init",
        status,
        "shell init sources managed environment",
    )


def pnpm_setup(tool: Tool, context: ActionContext) -> ActionResult:
    """Configure PNPM_HOME through the installer-owned RC block.

    Deliberately does not invoke ``pnpm setup`` because that command also edits
    a shell RC file outside the installer's managed markers.
    """
    if unapproved := _approval_required(tool, context, "pnpm_setup"):
        return unapproved
    pnpm_home = (
        context.home / "Library" / "pnpm"
        if context.platform.os == "macos"
        else context.home / ".local" / "share" / "pnpm"
    )
    changed = write_pnpm_home(
        context.myshellrc,
        pnpm_home,
    )
    status: ActionStatus = "applied" if changed else "already-applied"
    return ActionResult("pnpm_setup", status, "pnpm home added to managed PATH")


def enable_corepack(tool: Tool, context: ActionContext) -> ActionResult:
    """Enable Corepack through the fixed reviewed argv."""
    if unapproved := _approval_required(tool, context, "enable_corepack"):
        return unapproved
    context.runner(["corepack", "enable"])
    return ActionResult("enable_corepack", "applied", "corepack enabled")


def set_login_shell(tool: Tool, context: ActionContext) -> ActionResult:
    """Use injected ``chsh`` only when the system permits the discovered zsh."""
    if unapproved := _approval_required(tool, context, "set_login_shell"):
        return unapproved
    zsh = context.which("zsh")
    if zsh is None:
        return ActionResult("set_login_shell", "manual-required", "zsh executable not found")
    approved_shells: set[str]
    try:
        approved_shells = {
            line.strip()
            for line in context.shells_file.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except OSError:
        approved_shells = set()
    if zsh not in approved_shells:
        return ActionResult(
            "set_login_shell",
            "manual-required",
            f"{zsh} is absent from {context.shells_file}; "
            "ask an administrator to add it before changing the login shell",
        )
    if context.current_shell == zsh:
        return ActionResult("set_login_shell", "already-applied", f"login shell is already {zsh}")
    command = ["chsh", "-s", zsh]
    if context.interactive_runner is None:
        return _login_shell_terminal_handoff(zsh)
    try:
        context.interactive_runner(command)
    except InteractiveTerminalUnavailable:
        return _login_shell_terminal_handoff(zsh)
    return ActionResult("set_login_shell", "applied", f"login shell changed to {zsh}")


def _login_shell_terminal_handoff(zsh: str) -> ActionResult:
    return ActionResult(
        "set_login_shell",
        "manual-required",
        f"no interactive terminal is available; run `chsh -s {zsh}` in a terminal",
    )


def write_agent_reference(tool: Tool, context: ActionContext) -> ActionResult:
    """Add a managed pointer to the shared agent-tooling guidance."""
    if unapproved := _approval_required(tool, context, "write_agent_reference"):
        return unapproved
    if not context.agent_reference_paths:
        return ActionResult(
            "write_agent_reference",
            "manual-required",
            "no supported agent instruction file was detected",
        )
    guidance = context.home / ".agents" / "AGENTS-TOOLING.md"
    block = "\n".join(
        (
            _AGENT_REFERENCE_BEGIN,
            f"Read {guidance} for shared tool guidance.",
            _AGENT_REFERENCE_END,
        )
    )
    changed = False
    for path in context.agent_reference_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text() if path.exists() else ""
        updated = apply_block(
            existing,
            block,
            begin=_AGENT_REFERENCE_BEGIN,
            end=_AGENT_REFERENCE_END,
        )
        if updated != existing:
            path.write_text(updated)
            changed = True
    status: ActionStatus = "applied" if changed else "already-applied"
    return ActionResult("write_agent_reference", status, "agent tooling reference configured")


ActionHandler: TypeAlias = Callable[[Tool, ActionContext], ActionResult]

_HANDLERS: dict[str, ActionHandler] = {
    "configure_path": configure_path,
    "source_shell_init": source_shell_init,
    "pnpm_setup": pnpm_setup,
    "enable_corepack": enable_corepack,
    "set_login_shell": set_login_shell,
    "write_agent_reference": write_agent_reference,
}


def apply_actions(tool: Tool, context: ActionContext) -> tuple[ActionResult, ...]:
    """Apply a tool's ordered reviewed actions after validating the whole list."""
    unknown = next((action for action in tool.post_install if action not in _HANDLERS), None)
    if unknown is not None:
        raise ValueError(f"unknown post-install action: {unknown}")
    results: list[ActionResult] = []
    for action in tool.post_install:
        try:
            results.append(_HANDLERS[action](tool, context))
        except Exception as exc:
            raise ActionExecutionError(action, exc, tuple(results)) from exc
    return tuple(results)
