"""Closed, code-owned post-install action dispatch table.

A registry `post_install` field selects a NAME from this closed, code-owned
table and can never carry command text, so a registry edit alone cannot
introduce arbitrary post-install execution.

This plural `Tool.post_install` mechanism is a different thing from the
similarly-named singular hook module (`installer/postinstall.py`). The two
closed name sets (`POST_INSTALL_ACTIONS` versus `POSTINSTALL_HOOK_NAMES`)
are disjoint by design and must stay that way.

An action in this table returns reviewed instruction lines for the user to
run themselves (or a `PostInstallOutput` that also carries the settings it wrote)
and never spawns a child process. This follows
`installer/host_setup.py`'s documented doctrine: setup that needs a real
terminal is displayed, never launched from the installer's worker thread.

The shell-init action (`source_shell_init`) and the Oh-My-Zsh theme writes
keep that rule: they write only the installer-owned `~/.myshellrc` block (and,
in split mode, the rc `source` line) through the Policies tweak writer, and the
`.zshrc` theme line through the theme writer. They never spawn a child process.

A tuning action (`apply_agent_tuning`) writes the tool's own user-scope settings
through `agent_settings` (each key recorded in the agent's config-write ledger),
never spawns a child, asks nothing and runs on every route.

A tool the installer detects as already present is a SKIP on the review and
does not reach this table. Pressing `r` marks it REINSTALL and sends it through
the install ladder, so a successful reinstall dispatches actions once more. A
tool whose installer refuses to run over an existing install is not re-run;
the reinstall dispatches its actions directly. No path re-applies post-install
actions on their own (D-06); sensitive actions still ask.
"""

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from installer.agent_settings import (
    AGENT_FORMATS,
    TUNING_GROUPS,
    FileResult,
    apply_setting,
    settings_file,
)
from installer.locations import zshrc_path
from installer.model import Tool
from installer.omz import (
    MANAGED_PLUGINS,
    apply_theme,
    default_theme,
    ensure_zshrc_template,
    omz_root,
    plugins_owned,
    write_plugins,
)
from installer.platform import Platform
from installer.policy import tweak_policy
from installer.sanitize import sanitize_log_line
from installer.tweaks import shell_init_bundle

ConfirmSensitiveAction = Callable[[str, str], bool]


@dataclass(frozen=True)
class PostInstallOutput:
    """What the dispatched actions produced: reviewed lines, and the settings writes they made."""

    lines: tuple[str, ...] = ()
    settings: tuple[FileResult, ...] = ()


PostInstallAction = Callable[
    [Tool, Platform, ConfirmSensitiveAction | None], tuple[str, ...] | PostInstallOutput
]


@dataclass(frozen=True)
class SensitivePrompt:
    """The consent question one sensitive action asks, with its own choices and headless default."""

    prompt: str
    yes: str
    no: str
    default: bool


# `{tool}` is the tool id and `{effect}` the shell-init bundle's description.
SENSITIVE_PROMPTS: dict[str, SensitivePrompt] = {
    "set_login_shell": SensitivePrompt(
        "Show a reviewed command to change the login shell to zsh for {tool}, "
        "which you run in your own terminal after the installer exits?",
        "Yes, show the reviewed command",
        "No, skip this",
        True,
    ),
    "source_shell_init": SensitivePrompt(
        "Turn on {tool} shell init? It adds one guarded block to ~/.myshellrc that {effect}. "
        "It stays off unless you choose yes; Policies can change it later.",
        "Yes, turn it on",
        "No, leave it off",
        False,
    ),
}


def sensitive_prompt(tool_id: str, action: str) -> SensitivePrompt:
    """The prompt for a sensitive action. An action with no entry raises KeyError."""
    entry = SENSITIVE_PROMPTS[action]
    bundle = shell_init_bundle(tool_id)
    effect = "" if bundle is None else bundle.description
    return replace(entry, prompt=entry.prompt.format(tool=tool_id, effect=effect))


def _no_shell_init_sourcing() -> tuple[Path, ...]:
    return ()


# Split link mode sources ~/.myshellrc from the rc files only through the composition
# root. The action has no RunContext, so the root injects this reader once.
_shell_init_sourced_from: Callable[[], tuple[Path, ...]] = _no_shell_init_sourcing


def use_shell_init_sourcing(reader: Callable[[], tuple[Path, ...]]) -> None:
    """Inject the split-mode rc reader that `source_shell_init` wires through."""
    global _shell_init_sourced_from
    _shell_init_sourced_from = reader


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
    "This installer points Konsole, kitty and WezTerm at zsh when this run ends.",
)

_OMZ_HANDOFF: tuple[str, ...] = (
    "Try a theme in this shell: omz theme use <name>",
    "Keep it: omz theme set <name>",
)

_LEAN_TIPS: tuple[str, ...] = (
    "Lean tip: skip resident type-checkers (Pylance held 358 MB here).",
    "Run the project's pre-commit as an on-demand task, not on every save.",
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


def _source_shell_init(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del platform
    bundle = shell_init_bundle(tool.id)
    if bundle is None or confirm is None or not confirm(tool.id, "source_shell_init"):
        return ()
    home = Path.home()
    tweak_policy(
        bundle,
        rc_path=home / ".myshellrc",
        ensure_sourced_from=lambda: _shell_init_sourced_from(),
    ).apply()  # starship's theme rides the policy's own apply (CR-08)
    return ("Shell init on: open a new terminal to use it.",)


def _set_omz_theme(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del tool, platform, confirm
    home = Path.home()
    root = omz_root(home, os.environ)
    if root is None:
        return ()
    zshrc = zshrc_path(home, os.environ)
    myshellrc = home / ".myshellrc"
    ensure_zshrc_template(zshrc, root)
    result = apply_theme(zshrc, myshellrc, default_theme(myshellrc))
    if result.outcome == "no-source":
        return ()
    if result.theme is None:
        theme_line = "Theme: your own theme (left as is)."
    elif result.theme == "":
        theme_line = 'Theme: none (ZSH_THEME=""), so starship draws the prompt.'
    elif result.outcome == "yours":
        theme_line = f"Theme: {sanitize_log_line(result.theme)} (yours; left as is)."
    else:
        theme_line = f"Theme: {result.theme} (added because ~/.zshrc had no ZSH_THEME)."
    return (theme_line, *_OMZ_HANDOFF)


def _tune_omz_plugins(*, skip_recorded: bool) -> tuple[str, ...]:
    """Enable the bundled plugins in the user's .zshrc. A refusal is one line, never a raise."""
    home = Path.home()
    root = omz_root(home, os.environ)
    myshellrc = home / ".myshellrc"
    if root is None or (skip_recorded and plugins_owned(myshellrc)):
        return ()
    try:
        added = write_plugins(zshrc_path(home, os.environ), myshellrc, root=root)
    except OSError as exc:  # OmzPluginsError is one: a refused array, or a file that changed
        lines = str(exc).splitlines()
        return (f"Plugins not changed: {lines[0] if lines else type(exc).__name__}",)
    if added:
        return (f"Plugins: added {' '.join(added)} to ~/.zshrc.",)
    return (f"Plugins: {' and '.join(MANAGED_PLUGINS)} are on.",)


def _set_omz_plugins(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del tool, platform, confirm
    return _tune_omz_plugins(skip_recorded=False)  # install and reinstall rewrite


def _tune_agent(tool: Tool, platform: Platform, *, skip_recorded: bool) -> PostInstallOutput:
    home = Path.home()
    results: list[FileResult] = []
    for group in TUNING_GROUPS.get(tool.id, ()):
        try:
            results.append(
                apply_setting(
                    tool.id,
                    group,
                    home=home,
                    platform_os=platform.os,
                    environ=os.environ,
                    skip_recorded=skip_recorded,
                )
            )
        except OSError as exc:
            # One group's OS error is that group's refusal; the agent's other groups still run.
            path = settings_file(tool.id, home=home, platform_os=platform.os, environ=os.environ)
            lines = str(exc).splitlines()
            reason = lines[0] if lines and lines[0] else f"{type(exc).__name__} failed"
            results.append(FileResult(tool.id, group, path, AGENT_FORMATS[tool.id], refused=reason))
    return PostInstallOutput(settings=tuple(results))


def _apply_agent_tuning(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> PostInstallOutput:
    del confirm
    return _tune_agent(tool, platform, skip_recorded=False)  # install and reinstall rewrite


def _show_lean_tips(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del tool, platform, confirm
    return _LEAN_TIPS


POST_INSTALL_HOOKS: dict[str, PostInstallAction] = {
    "set_login_shell": _set_login_shell,
    "source_shell_init": _source_shell_init,
    "set_omz_theme": _set_omz_theme,
    "set_omz_plugins": _set_omz_plugins,
    "show_lean_tips": _show_lean_tips,
    "apply_agent_tuning": _apply_agent_tuning,
}


# The actions that make up a tool's install tuning, in the order a tool declares them.
TUNING_ACTIONS: tuple[str, ...] = ("apply_agent_tuning", "set_omz_plugins")


def apply_install_tuning(
    tool: Tool, platform: Platform, *, skip_recorded: bool
) -> PostInstallOutput:
    """The tool's install tuning, as RECONFIGURE runs it. `skip_recorded` leaves a key the
    ledger records alone, so a key the user deleted stays deleted; the install action does not."""
    lines: list[str] = []
    settings: list[FileResult] = []
    for name in tool.post_install:
        if name == "apply_agent_tuning":
            produced = _tune_agent(tool, platform, skip_recorded=skip_recorded)
            lines.extend(produced.lines)
            settings.extend(produced.settings)
        elif name == "set_omz_plugins":
            lines.extend(_tune_omz_plugins(skip_recorded=skip_recorded))
    return PostInstallOutput(tuple(lines), tuple(settings))


def run_post_install(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None = None,
) -> PostInstallOutput:
    """Dispatch each declared post-install action in order; skip unknown names."""
    lines: list[str] = []
    settings: list[FileResult] = []
    for name in tool.post_install:
        action = POST_INSTALL_HOOKS.get(name)
        if action is None:
            continue
        produced = action(tool, platform, confirm)
        if isinstance(produced, PostInstallOutput):
            lines.extend(produced.lines)
            settings.extend(produced.settings)
        else:
            lines.extend(produced)
    return PostInstallOutput(tuple(lines), tuple(settings))
