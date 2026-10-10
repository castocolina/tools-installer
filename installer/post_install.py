"""Closed, code-owned post-install action dispatch table.

A registry `post_install` field selects a NAME from this closed, code-owned
table and can never carry command text, so a registry edit alone cannot
introduce arbitrary post-install execution.

This plural `Tool.post_install` mechanism is a different thing from the
similarly-named singular hook module (`installer/postinstall.py`). The two
closed name sets (`POST_INSTALL_ACTIONS` versus `POSTINSTALL_HOOK_NAMES`)
are disjoint by design and must stay that way.

An action in this table returns reviewed instruction lines for the user to
run themselves and never spawns a child process. This follows
`installer/host_setup.py`'s documented doctrine: setup that needs a real
terminal is displayed, never launched from the installer's worker thread.

A tool the installer detects as already present never reaches this table at
all. Dispatch sits on the post-success path of the install ladder, and the
already-present branch returns before it. That is the intended
single-direction trigger: a re-run cannot re-propose a system mutation the
user already declined. It is not an oversight to be widened.

The single exception is a tool the user EXPLICITLY selects again while it is
installed. ExecuteScreen dispatches its actions once for that selection via
`engine.reapply_post_install`; drag-ins and plain re-runs still never reach
this table, and sensitive actions still ask.
"""

import shutil
from collections.abc import Callable

from installer.model import Tool
from installer.platform import Platform

ConfirmSensitiveAction = Callable[[str, str], bool]
PostInstallAction = Callable[[Tool, Platform, ConfirmSensitiveAction | None], tuple[str, ...]]

_SET_LOGIN_SHELL_INSTRUCTIONS: tuple[str, ...] = (
    "After leaving the installer, run this command in your own terminal "
    "to set zsh as your login shell:",
    "chsh -s $(which zsh)",
    "Then log out and back in for the change to take effect.",
)

_CHSH_ABSENT_EXPLANATION: tuple[str, ...] = (
    "This system removed chsh (the command that would change your login shell) "
    "to avoid breaking graphical login after an ostree rebase.",
    "The supported path is to set zsh in your terminal emulator "
    "(Konsole, kitty, or WezTerm), not as the system login shell.",
    "A later installer step will apply that terminal-emulator configuration automatically.",
)


def _set_login_shell(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del platform
    if shutil.which("chsh") is None:
        return _CHSH_ABSENT_EXPLANATION
    if confirm is None or not confirm(tool.id, "set_login_shell"):
        return ()
    return _SET_LOGIN_SHELL_INSTRUCTIONS


POST_INSTALL_HOOKS: dict[str, PostInstallAction] = {
    "set_login_shell": _set_login_shell,
}


def run_post_install(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None = None,
) -> tuple[str, ...]:
    """Dispatch each declared post-install action; skip unknown names."""
    lines: list[str] = []
    for name in tool.post_install:
        action = POST_INSTALL_HOOKS.get(name)
        if action is None:
            continue
        lines.extend(action(tool, platform, confirm))
    return tuple(lines)
