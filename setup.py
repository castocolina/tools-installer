"""Entry point for the tools-installer wizard. Run via `make run` (uv run setup.py).

This is the composition root: it performs the real terminal IO (questionary) and
wires the pure, fully-tested installer package together. It deliberately lives
outside the `installer/` package so the untyped questionary boundary is isolated
from the strict-typed, fully-covered core.
"""

import sys
from pathlib import Path

import questionary
from rich.console import Console

from installer.app import run_wizard
from installer.cli import parse_args
from installer.model import load_tools
from installer.platform import detect
from installer.prompt import CallbackPrompter
from installer.selection import Choice

_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"


def _ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
    answer = questionary.checkbox(
        message,
        choices=[questionary.Choice(title=c.label, value=c.id, checked=c.checked) for c in choices],
    ).ask()
    return list(answer) if answer else []


def _ask_confirm(message: str) -> bool:
    return bool(questionary.confirm(message, default=True).ask())


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    console = Console()
    can_proceed = options.all or bool(options.categories) or sys.stdin.isatty()
    if not can_proceed:
        console.print(
            "No TTY detected. Re-run with --all or --categories A,B (and --yes) for "
            "non-interactive use."
        )
        return 2
    tools = load_tools(_REGISTRY)
    prompter = CallbackPrompter(ask_checkbox=_ask_checkbox, ask_confirm=_ask_confirm)
    summary = run_wizard(tools, detect(), prompter, console, options)
    if summary is None:
        console.print("Aborted.")
        return 0
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
