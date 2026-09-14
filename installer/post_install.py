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
"""

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


def _set_login_shell(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    if platform.immutable:
        return ()
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
