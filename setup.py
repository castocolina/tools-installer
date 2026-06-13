"""Entry point for the tools-installer wizard. Run via `make setup` (uv run setup.py).

This is the composition root: it performs the real terminal IO (the Textual
catalog screen for selection; questionary for confirms and choices) and the
real home-path wiring, and composes the pure, fully-tested installer package.
It deliberately lives outside the `installer/` package so the untyped
questionary boundary is isolated from the strict-typed, fully-covered core.
"""

import os
import sys
from pathlib import Path

import questionary
from rich.console import Console

from installer.app import (
    clean_rc_duplicates,
    configure_path,
    run_doctor,
    run_guard,
    run_uninstall,
    run_wizard,
)
from installer.cli import parse_args
from installer.model import Tool, load_categories, load_tools
from installer.platform import Platform, detect
from installer.prompt import CallbackPrompter
from installer.render import render_troubleshooting
from installer.selection import Choice
from installer.shellrc import collect_bin_dirs
from installer.status import is_installed
from installer.wizard_app import UnifiedApp

_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
_RC_PATHS = [Path.home() / ".zshrc", Path.home() / ".bashrc"]

_STYLE = questionary.Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "bold"),
        ("selected", "fg:green"),
        ("instruction", "fg:#858585"),
        ("description", "fg:#858585 italic"),
        ("tag-installed", "fg:green"),
        ("tag-missing", "fg:yellow"),
        ("tag-dim", "fg:#858585"),
    ]
)
_CHECKBOX_KEYS = "(↑/↓ move, <space> toggle, <a> all, <i> invert, <enter> confirm)"


def _tag_class(tag: str) -> str:
    if tag == "installed":
        return "tag-installed"
    if tag == "missing":
        return "tag-missing"
    return "tag-dim"


def _title(choice: Choice) -> list[tuple[str, str]]:
    segments = [("class:text", choice.label)]
    if choice.tag:
        segments.append((f"class:{_tag_class(choice.tag)}", f"  ({choice.tag})"))
    return segments


def _ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
    answer = questionary.checkbox(
        message,
        choices=[
            questionary.Choice(
                title=_title(c), value=c.id, checked=c.checked, description=c.description or None
            )
            for c in choices
        ],
        instruction=_CHECKBOX_KEYS,
        style=_STYLE,
    ).ask()
    if answer is None:  # questionary returns None on Ctrl+C / Ctrl+D at the prompt
        raise KeyboardInterrupt
    return list(answer)


def _ask_confirm(message: str) -> bool:
    answer = questionary.confirm(message, default=True, style=_STYLE).ask()
    if answer is None:  # questionary returns None on Ctrl+C / Ctrl+D at the prompt
        raise KeyboardInterrupt
    return bool(answer)


def _ask_optin(message: str) -> bool:
    answer = questionary.confirm(message, default=False, style=_STYLE).ask()
    if answer is None:  # Ctrl+C / Ctrl+D
        raise KeyboardInterrupt
    return bool(answer)


def _ban_rc_paths(link_mode: str) -> list[Path]:
    # Where to WRITE aliases, following the PATH model: centralized/single keep
    # one ~/.myshellrc; split writes into each rc file directly.
    if link_mode == "split":
        return _rc_paths_for_mode(link_mode)
    return [_MYSHELLRC]


def _all_ban_rc_paths() -> list[Path]:
    # Where to REMOVE aliases from: every file an install could have written to,
    # across all link modes. remove_ban_aliases is a no-op where the block is
    # absent, so removal needs no link-mode guess (which would otherwise strand
    # aliases when the user picks a different mode than they installed with).
    return [_MYSHELLRC, *_RC_PATHS]


def _ask_select(message: str, choices: list[tuple[str, str]]) -> str:
    answer = questionary.select(
        message,
        choices=[questionary.Choice(title=title, value=value) for title, value in choices],
        style=_STYLE,
    ).ask()
    if answer is None:  # Ctrl+C / Ctrl+D
        raise KeyboardInterrupt
    return str(answer)


def _ask_mismatch(tool_id: str) -> str:
    return _ask_select(
        f"Checksum mismatch for {tool_id} — the download may be corrupted or tampered with.",
        [
            ("Retry the download", "retry"),
            ("Skip this tool", "skip"),
            ("Fall back to another install method (brew/native)", "fallback"),
        ],
    )


def _select_catalog(tools: list[Tool]) -> list[str] | None:
    installed = {tool.id: is_installed(tool) for tool in tools}
    return UnifiedApp(tools, installed, load_categories(_REGISTRY)).run()


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


def _run_doctor(console: Console) -> int:
    run_doctor(
        load_tools(_REGISTRY),
        console,
        platform=detect(),
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        hint="Run 'make fix' to wire PATH into your shell.",
    )
    return 0


def _run_fix(console: Console, *, link_mode_option: str | None) -> int:
    # No re-audit after writing: the process PATH cannot change until the shell
    # restarts, so a post-fix audit would re-show "missing" and recreate the
    # confusion the doctor/fix split removes.
    link_mode = _resolve_link_mode(link_mode_option)
    configure_path(
        load_tools(_REGISTRY),
        console,
        platform=detect(),
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_rc_paths_for_mode(link_mode),
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
        rc_paths=_RC_PATHS,
        confirm=confirm,
    )
    return 0


def _run_guard(console: Console, *, remove: bool, rc_paths: list[Path], assume_yes: bool) -> int:
    # The caller picks rc_paths: install targets the link-mode location, removal
    # sweeps every possible location (so it never depends on a link-mode guess).
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    acted = run_guard(
        remove=remove,
        shim_dir=_DEFAULT_BIN_DIR,
        rc_paths=rc_paths,
        path_value=os.environ.get("PATH", ""),
        console=console,
        confirm=confirm,
    )
    if acted and not remove:
        console.print("Open a new shell (or run `hash -r`) so cached command paths refresh.")
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
        hint="Restart your shell (or: source ~/.myshellrc) to apply.",
    )
    managed = set(collect_bin_dirs(tools, platform, _DEFAULT_BIN_DIR))
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    clean_rc_duplicates(_RC_PATHS, managed, os.environ, console, confirm=confirm)


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    console = Console()
    if options.doctor:
        return _run_doctor(console)
    if options.fix:
        return _run_fix(console, link_mode_option=options.link_mode)
    if options.uninstall:
        return _run_uninstall(console, assume_yes=options.yes)
    if options.guard:
        return _run_guard(
            console,
            remove=False,
            rc_paths=_ban_rc_paths(_resolve_link_mode(options.link_mode)),
            assume_yes=options.yes,
        )
    if options.unguard:
        # Removal needs no link-mode prompt — it sweeps every rc file.
        return _run_guard(
            console, remove=True, rc_paths=_all_ban_rc_paths(), assume_yes=options.yes
        )
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
    summary = run_wizard(
        tools,
        platform,
        prompter,
        console,
        options,
        on_mismatch=_ask_mismatch,
        category_blurbs=load_categories(_REGISTRY),
        select_catalog=_select_catalog,
    )
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
    if (
        sys.stdin.isatty()
        and not options.yes
        and _ask_optin(
            "Enable the pip/npm ban? Blocks bare pip/npm so installs go through uv/pnpm."
        )
    ):
        # The opt-in IS the confirmation, and link_mode is already resolved above:
        # assume_yes=True so run_guard does not re-confirm.
        _run_guard(console, remove=False, rc_paths=_ban_rc_paths(link_mode), assume_yes=True)
    if summary.failed or summary.mismatched:
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
