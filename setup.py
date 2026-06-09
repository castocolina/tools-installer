"""Entry point for the tools-installer wizard. Run via `make run` (uv run setup.py).

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

from installer.app import configure_path, run_doctor, run_wizard
from installer.cli import parse_args
from installer.model import load_tools
from installer.platform import detect
from installer.prompt import CallbackPrompter
from installer.render import render_troubleshooting
from installer.selection import Choice

_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
_RC_PATHS = [Path.home() / ".zshrc", Path.home() / ".bashrc"]


def _ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
    answer = questionary.checkbox(
        message,
        choices=[questionary.Choice(title=c.label, value=c.id, checked=c.checked) for c in choices],
    ).ask()
    return list(answer) if answer else []


def _ask_confirm(message: str) -> bool:
    return bool(questionary.confirm(message, default=True).ask())


def _run_doctor(console: Console) -> int:
    run_doctor(
        load_tools(_REGISTRY),
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
        fix=True,
    )
    return 0


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    console = Console()
    if options.doctor:
        return _run_doctor(console)
    can_proceed = options.all or bool(options.categories) or sys.stdin.isatty()
    if not can_proceed:
        console.print(
            "No TTY detected. Re-run with --all or --categories A,B (and --yes) for "
            "non-interactive use, or --doctor to fix the PATH."
        )
        return 2
    tools = load_tools(_REGISTRY)
    prompter = CallbackPrompter(ask_checkbox=_ask_checkbox, ask_confirm=_ask_confirm)
    summary = run_wizard(tools, detect(), prompter, console, options)
    if summary is None:
        console.print("Aborted.")
        return 0
    configure_path(
        tools,
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
    )
    if summary.failed:
        render_troubleshooting(console)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
