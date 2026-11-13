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
and never spawns an interactive child. This follows
`installer/host_setup.py`'s documented doctrine: setup that needs a real
terminal is displayed, never launched from the installer's worker thread.

The shell-init action (`source_shell_init`) and the Oh-My-Zsh theme and plugin writes
keep that rule: they write only the installer-owned `~/.myshellrc` block (and,
in split mode, the rc `source` line) through the Policies tweak writer, and the
`.zshrc` theme and plugin lines through the Oh-My-Zsh writers. They never spawn a child process.

A tuning action (`apply_agent_tuning`, `set_omz_plugins`, `source_shell_init`) writes the
tool's own settings (each agent key recorded in its config-write ledger), never spawns a
child, asks nothing and runs on every route. `set_login_shell` only prints the reviewed
command, or why there is none.

A tool the installer detects as already present is a SKIP on the review and
does not reach this table. Pressing `r` marks it REINSTALL and sends it through
the install ladder, so a successful reinstall dispatches actions once more. A
tool whose installer refuses to run over an existing install is not re-run;
the reinstall dispatches its actions directly. No path re-applies post-install
actions on their own (D-06). No action asks a question (23.2 D-13).

`clone_nvim_starter` is the one action that spawns a child at all: it runs non-interactive
git (no terminal, `GIT_TERMINAL_PROMPT=0`, a timeout) through the runner the composition
root injects with `use_git_runner`; with no runner wired it refuses (24.1 D-15, D-17).
"""

import os
import shlex
import shutil
import tempfile
import time
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
from installer.locations import display_path, xdg_config_base, zshrc_path
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
from installer.run import CommandError, OutputRunner, command_error_line
from installer.sanitize import sanitize_log_line
from installer.status import command_stub_reason
from installer.terminal_shell import apply_alacritty_keys
from installer.tweaks import (
    forget_shell_init,
    record_shell_init,
    shell_init_bundle,
    shell_init_record,
    strip_tweak_block,
    user_export,
)

ConfirmSensitiveAction = Callable[[str, str], bool]


@dataclass(frozen=True)
class PostInstallOutput:
    """What the dispatched actions produced: reviewed lines, and the settings writes they made."""

    lines: tuple[str, ...] = ()
    settings: tuple[FileResult, ...] = ()
    warning: str | None = None  # one crashed action's reason per entry, joined; never fatal
    refused: str | None = None  # why an install-tuning write was refused (RECONFIGURE fails on it)


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


# No action asks (23.2 D-13), so this machinery has no user and Phase 25 sweeps it (24.1 D-21).
# `{tool}` is the tool id and `{effect}` the shell-init bundle's description in a prompt.
SENSITIVE_PROMPTS: dict[str, SensitivePrompt] = {}


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


_KICKSTART_URL = "https://github.com/nvim-lua/kickstart.nvim.git"
_KICKSTART_PIN = "8e35dbedb7966e3a95e1f26f9fc1179ab6c68db4"
_KICKSTART_PATCH = Path(__file__).parent / "patches" / "kickstart-no-lsp.patch"


def _no_git(argv: list[str]) -> str:
    raise CommandError(argv, 127, detail="no git runner is wired")


# The starter's git runs only through the composition root, which injects it once.
_git: OutputRunner = _no_git


def use_git_runner(runner: OutputRunner) -> None:
    """Inject the non-interactive git runner that `clone_nvim_starter` runs through."""
    global _git
    _git = runner


_NVIM_STARTER_TARGET = "~/.config/nvim"

_NVIM_LSP_HINT = "For one session with a server, run :lsp enable <name> inside nvim."
_NVIM_HINTS: tuple[str, ...] = (
    "Neovim runs no language server: check the open file with :!pre-commit run --files %",
    _NVIM_LSP_HINT,
)
# D-19: a config of the user's own gets the same two commands without the no-server claim.
_NVIM_OWN_CONFIG_HINTS: tuple[str, ...] = (
    "Check the open file with :!pre-commit run --files %",
    _NVIM_LSP_HINT,
)


def _by_hand() -> tuple[str, ...]:
    return (
        "To add it by hand:",
        f"git clone {_KICKSTART_URL} {_NVIM_STARTER_TARGET}",
        f"git -C {_NVIM_STARTER_TARGET} checkout -B master {_KICKSTART_PIN}",
        f"git -C {_NVIM_STARTER_TARGET} apply {shlex.quote(str(_KICKSTART_PATCH))}",
    )


# The line the patch adds to init.lua: what tells the installer's starter from the user's config.
_STARTER_MARKER = "tools-installer: no language servers"


def _holds_starter(target: Path) -> bool:
    try:
        return _STARTER_MARKER in (target / "init.lua").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def _absent_or_empty(path: Path) -> bool:
    """True for a missing path or an empty directory; a link, a file or any entry is the user's."""
    try:
        if path.is_symlink():
            return False
        return not path.exists() or (path.is_dir() and not any(path.iterdir()))
    except OSError:
        return False


_TEMP_PREFIX = ".nvim-starter."
# Longer than a run can last (five git steps, 600 s each), so a live run's directory is safe.
_STALE_AFTER_SECONDS = 2 * 60 * 60


def _sweep_stale_temp_dirs(config_dir: Path) -> None:
    """Remove the starter's own temp directories a killed run left behind."""
    cutoff = time.time() - _STALE_AFTER_SECONDS
    try:
        for entry in config_dir.glob(f"{_TEMP_PREFIX}*"):
            if entry.is_dir() and not entry.is_symlink() and entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
    except OSError:
        return  # a sweep that cannot read the directory is not worth failing the install


def _clone_nvim_starter(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del tool, confirm
    home = Path.home()
    config_dir = home / ".config"
    target = config_dir / "nvim"
    if xdg_config_base(home, os.environ).resolve() != config_dir.resolve():
        return ("Starter not added: XDG_CONFIG_HOME points elsewhere than ~/.config (left as is).",)
    if not _absent_or_empty(target):
        if _holds_starter(target):
            return (f"Starter already in {_NVIM_STARTER_TARGET} (left as is).",)
        return (f"Starter not added: {_NVIM_STARTER_TARGET} is yours (left as is).",)
    if shutil.which("git") is None:
        return ("Starter not added: git is not installed.", *_by_hand())
    # On macOS without the Command Line Tools the system git is a stub that opens an install dialog.
    stub = command_stub_reason("git", darwin=platform.os == "macos")
    if stub is not None:
        return (f"Starter not added: {sanitize_log_line(stub)}.", *_by_hand())
    tmp: Path | None = None
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        _sweep_stale_temp_dirs(config_dir)
        tmp = Path(tempfile.mkdtemp(prefix=_TEMP_PREFIX, dir=config_dir))
        work = str(tmp)
        patch = str(_KICKSTART_PATCH)
        _git(["git", "clone", "--quiet", "--no-checkout", "--", _KICKSTART_URL, work])
        _git(["git", "-C", work, "checkout", "--quiet", "-B", "master", _KICKSTART_PIN])
        head = _git(["git", "-C", work, "rev-parse", "HEAD"]).strip()
        if head != _KICKSTART_PIN:
            reason = f"the checkout is at {head[:12]}, not the pinned {_KICKSTART_PIN[:12]}"
            return (f"Starter not added: {reason}.", *_by_hand())
        _git(["git", "-C", work, "apply", "--check", patch])
        _git(["git", "-C", work, "apply", patch])
        changed = (
            f"Starter not added: {_NVIM_STARTER_TARGET} changed while the starter was prepared"
            " (left as is).",
        )
        if not _absent_or_empty(target):
            return changed
        try:
            os.rename(tmp, target)
        except OSError:
            return changed
    except CommandError as exc:
        reason = sanitize_log_line(command_error_line(exc))
        return (f"Starter not added: {reason}.", *_by_hand())
    except OSError as exc:
        return (f"Starter not added: {sanitize_log_line(str(exc))}.", *_by_hand())
    finally:
        if tmp is not None and tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return (
        f"Starter: kickstart.nvim {_KICKSTART_PIN[:7]} (no language servers) is in "
        f"{display_path(target)}.",
        "Open nvim once so the starter downloads its plugins (it asks Proceed? once).",
    )


def _set_login_shell(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del tool, platform, confirm
    if shutil.which("chsh") is None:
        return _CHSH_ABSENT_EXPLANATION
    return _SET_LOGIN_SHELL_INSTRUCTIONS


def _tune_shell_init(tool: Tool, platform: Platform, *, skip_recorded: bool) -> tuple[str, ...]:
    """Write the tool's guarded shell-init block and record it once. Nothing when the tool has
    no bundle on this OS, or (reconfigure) when the record says the installer wrote it before."""
    bundle = shell_init_bundle(tool.id)
    if bundle is None or (bundle.platforms and platform.os not in bundle.platforms):
        return ()
    rc_path = Path.home() / ".myshellrc"
    yielded = user_export(bundle.yields_to, tool.id) if bundle.yields_to else None
    if yielded is not None:
        # The user's own export wins: nothing written, recorded or pending. A block written
        # before they added it would still override an export in an earlier-read file, so it goes
        # (an unreadable startup file proves nothing, so then it stays).
        if yielded.kept:
            strip_tweak_block(tool.id, rc_path)
            forget_shell_init(rc_path, tool.id)
        return (yielded.line,)
    if skip_recorded and tool.id in (shell_init_record(rc_path) or ()):
        return ()
    tweak_policy(
        bundle,
        rc_path=rc_path,
        ensure_sourced_from=lambda: _shell_init_sourced_from(),
    ).apply()  # starship's theme rides the policy's own apply (CR-08)
    record_shell_init(rc_path, tool.id)
    return ("Shell init on: open a new terminal to use it.",)


def _source_shell_init(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del confirm
    return _tune_shell_init(tool, platform, skip_recorded=False)  # install and reinstall rewrite


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


def _tune_omz_plugins(*, skip_recorded: bool) -> PostInstallOutput:
    """Enable the bundled plugins in the user's .zshrc. A refusal is one line and `refused`."""
    home = Path.home()
    root = omz_root(home, os.environ)
    myshellrc = home / ".myshellrc"
    if root is None or (skip_recorded and plugins_owned(myshellrc)):
        return PostInstallOutput()
    try:
        added = write_plugins(zshrc_path(home, os.environ), myshellrc, root=root)
    except OSError as exc:  # OmzPluginsError is one: a refused array, or a file that changed
        lines = str(exc).splitlines()
        reason = lines[0] if lines else type(exc).__name__
        return PostInstallOutput((f"Plugins not changed: {reason}",), refused=reason)
    if added:
        return PostInstallOutput((f"Plugins: added {' '.join(added)} to ~/.zshrc.",))
    return PostInstallOutput((f"Plugins: {' and '.join(MANAGED_PLUGINS)} are on.",))


def _set_omz_plugins(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del tool, platform, confirm
    return _tune_omz_plugins(skip_recorded=False).lines  # install and reinstall rewrite


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


def _tune_terminal(*, skip_recorded: bool) -> PostInstallOutput:
    """Alacritty's keybindings region (24 D-23). A refusal is one line and `refused`."""
    lines, refused = apply_alacritty_keys(Path.home(), os.environ, skip_recorded=skip_recorded)
    if refused is not None:
        return PostInstallOutput((f"Alacritty keys not changed: {refused}",), refused=refused)
    return PostInstallOutput(lines)


def _apply_terminal_tuning(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> PostInstallOutput:
    del tool, platform, confirm
    return _tune_terminal(skip_recorded=False)  # install and reinstall rewrite


def _show_lean_tips(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del tool, platform, confirm
    return _LEAN_TIPS


def _show_nvim_hints(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None,
) -> tuple[str, ...]:
    del tool, platform, confirm
    target = Path.home() / ".config" / "nvim"
    # "Neovim runs no language server" is true of the starter or of no config, not of a config
    # of the user's own; the commands themselves help every setup (D-19).
    if not _absent_or_empty(target) and not _holds_starter(target):
        return _NVIM_OWN_CONFIG_HINTS
    return _NVIM_HINTS


POST_INSTALL_HOOKS: dict[str, PostInstallAction] = {
    "set_login_shell": _set_login_shell,
    "source_shell_init": _source_shell_init,
    "set_omz_theme": _set_omz_theme,
    "set_omz_plugins": _set_omz_plugins,
    "show_lean_tips": _show_lean_tips,
    "apply_agent_tuning": _apply_agent_tuning,
    "apply_terminal_tuning": _apply_terminal_tuning,
    "clone_nvim_starter": _clone_nvim_starter,
    "show_nvim_hints": _show_nvim_hints,
}


def apply_install_tuning(
    tool: Tool, platform: Platform, *, skip_recorded: bool
) -> PostInstallOutput:
    """The tool's install tuning, as RECONFIGURE runs it. `skip_recorded` leaves a key the
    ledger records alone, so a key the user deleted stays deleted; the install action does not."""
    lines: list[str] = []
    settings: list[FileResult] = []
    refused: str | None = None
    for name in tool.post_install:
        if name == "apply_agent_tuning":
            produced = _tune_agent(tool, platform, skip_recorded=skip_recorded)
            lines.extend(produced.lines)
            settings.extend(produced.settings)
        elif name == "set_omz_plugins":
            produced = _tune_omz_plugins(skip_recorded=skip_recorded)
            lines.extend(produced.lines)
            refused = refused or produced.refused
        elif name == "source_shell_init":
            lines.extend(_tune_shell_init(tool, platform, skip_recorded=skip_recorded))
        elif name == "apply_terminal_tuning":
            produced = _tune_terminal(skip_recorded=skip_recorded)
            lines.extend(produced.lines)
            refused = refused or produced.refused
    return PostInstallOutput(tuple(lines), tuple(settings), refused=refused)


def run_post_install(
    tool: Tool,
    platform: Platform,
    confirm: ConfirmSensitiveAction | None = None,
) -> PostInstallOutput:
    """Dispatch each declared post-install action in order; skip unknown names."""
    lines: list[str] = []
    settings: list[FileResult] = []
    crashed: list[str] = []
    for name in tool.post_install:
        action = POST_INSTALL_HOOKS.get(name)
        if action is None:
            continue
        try:
            produced = action(tool, platform, confirm)
        except Exception as exc:  # one action's crash is a warning, never the others' loss
            first = next(iter(str(exc).splitlines()), "") or type(exc).__name__
            crashed.append(f"{name} crashed: {first}")
            continue
        if isinstance(produced, PostInstallOutput):
            lines.extend(produced.lines)
            settings.extend(produced.settings)
        else:
            lines.extend(produced)
    return PostInstallOutput(tuple(lines), tuple(settings), "; ".join(crashed) or None)
