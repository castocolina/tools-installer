"""Entry point for the tools-installer wizard. Run via `make setup` (uv run setup.py).

This is the composition root: it performs the real terminal IO (questionary) and
the real home-path wiring, and composes the pure, fully-tested installer package.
It deliberately lives outside the `installer/` package so the untyped questionary
boundary is isolated from the strict-typed, fully-covered core.
"""

import os
import sys
from pathlib import Path

import questionary
from rich.console import Console

from installer.app import clean_rc_duplicates, configure_path, run_doctor, run_uninstall, run_wizard
from installer.cli import parse_args
from installer.model import Tool, load_tools
from installer.platform import Platform, detect
from installer.prompt import CallbackPrompter
from installer.render import render_troubleshooting
from installer.selection import Choice
from installer.shellrc import collect_bin_dirs

_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
_RC_PATHS = [Path.home() / ".zshrc", Path.home() / ".bashrc"]


def _ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
    answer = questionary.checkbox(
        message,
        choices=[questionary.Choice(title=c.label, value=c.id, checked=c.checked) for c in choices],
    ).ask()
    if answer is None:  # questionary returns None on Ctrl+C / Ctrl+D at the prompt
        raise KeyboardInterrupt
    return list(answer)


def _ask_confirm(message: str) -> bool:
    answer = questionary.confirm(message, default=True).ask()
    if answer is None:  # questionary returns None on Ctrl+C / Ctrl+D at the prompt
        raise KeyboardInterrupt
    return bool(answer)


def _ask_select(message: str, choices: list[tuple[str, str]]) -> str:
    answer = questionary.select(
        message, choices=[questionary.Choice(title=title, value=value) for title, value in choices]
    ).ask()
    if answer is None:  # Ctrl+C / Ctrl+D
        raise KeyboardInterrupt
    return str(answer)


def _resolve_link_mode(link_mode_option: str | None) -> str:
    if link_mode_option is not None:
        return link_mode_option
    if not sys.stdin.isatty():
        return "centralized"
    return _ask_select(
        "How should PATH be wired into your shells?",
        [
            ("Centralized: one ~/.myshellrc, sourced from .zshrc and .bashrc", "centralized"),
            ("Single shell: source ~/.myshellrc from your current shell only", "single"),
            ("Split: write PATH directly into each rc file (no ~/.myshellrc)", "split"),
        ],
    )


def _rc_paths_for_mode(link_mode: str) -> list[Path]:
    if link_mode != "single":
        return _RC_PATHS
    shell = os.environ.get("SHELL", "")
    if shell.endswith("zsh"):
        return [Path.home() / ".zshrc"]
    if shell.endswith("bash"):
        return [Path.home() / ".bashrc"]
    return _RC_PATHS  # undetectable shell -> wire both


def _run_doctor(console: Console, *, link_mode_option: str | None) -> int:
    link_mode = _resolve_link_mode(link_mode_option)
    run_doctor(
        load_tools(_REGISTRY),
        console,
        platform=detect(),
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_rc_paths_for_mode(link_mode),
        fix=True,
        link_mode=link_mode,
    )
    return 0


def _run_uninstall(console: Console, *, assume_yes: bool) -> int:
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    run_uninstall(
        load_tools(_REGISTRY),
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        confirm=confirm,
    )
    return 0


def _verify_and_clean(
    console: Console, tools: list[Tool], platform: Platform, *, assume_yes: bool
) -> None:
    run_doctor(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
        fix=False,
    )
    managed = set(collect_bin_dirs(tools, platform, _DEFAULT_BIN_DIR))
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    clean_rc_duplicates(_RC_PATHS, managed, os.environ, console, confirm=confirm)


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    console = Console()
    if options.doctor:
        return _run_doctor(console, link_mode_option=options.link_mode)
    if options.uninstall:
        return _run_uninstall(console, assume_yes=options.yes)
    can_proceed = options.all or bool(options.categories) or sys.stdin.isatty()
    if not can_proceed:
        console.print(
            "No TTY detected. Re-run with --all or --categories A,B (and --yes) for "
            "non-interactive use, or --doctor to fix the PATH."
        )
        return 2
    tools = load_tools(_REGISTRY)
    platform = detect()
    prompter = CallbackPrompter(ask_checkbox=_ask_checkbox, ask_confirm=_ask_confirm)
    summary = run_wizard(tools, platform, prompter, console, options)
    if summary is None:
        console.print("Aborted.")
        return 0
    link_mode = _resolve_link_mode(options.link_mode)
    configure_path(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_rc_paths_for_mode(link_mode),
        link_mode=link_mode,
    )
    _verify_and_clean(console, tools, platform, assume_yes=options.yes)
    if summary.failed:
        render_troubleshooting(console)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        # Ctrl+C anywhere — at a prompt or mid-install — exits cleanly, no traceback.
        # 130 = 128 + SIGINT(2), the conventional shell code for interrupted programs.
        print("\nAborted.", file=sys.stderr)
        raise SystemExit(130) from None
