"""Entry point for the tools-installer wizard. Run via `make setup` (uv run setup.py).

This is the composition root: it performs the real terminal IO (the Textual
catalog screen for selection; questionary for confirms and choices) and the
real home-path wiring, and composes the pure, fully-tested installer package.
It deliberately lives outside the `installer/` package so the untyped
questionary boundary is isolated from the strict-typed, fully-covered core.
"""

import io
import os
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

import questionary
from rich.console import Console

from installer import pnpm_globals
from installer.app import (
    UninstallDecision,
    clean_rc_duplicates,
    configure_path,
    doctor_data,
    guard_state,
    perform_uninstall,
    run_doctor,
    run_guard,
    run_uninstall,
    run_wizard,
)
from installer.cli import parse_args
from installer.locations import all_ban_rc_paths, ban_rc_paths, rc_paths_for_mode, zshrc_path
from installer.model import Tool, load_categories, load_tools
from installer.omz import omz_present
from installer.platform import Platform, detect
from installer.policy import ban_policy, omz_plugins_policy, tweak_policy
from installer.prompt import CallbackPrompter
from installer.render import render_troubleshooting
from installer.resolve import platform_could_support
from installer.selection import Choice
from installer.shellrc import collect_bin_dirs, has_managed_block
from installer.status import is_installed
from installer.tweaks import BUNDLES, applicable_bundles
from installer.ui_common import BASE_VIEW
from installer.uninstall import (
    SweepResult,
    active_tweak_ids,
    classify_tools,
    reverse_dependencies,
)
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs

_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
# $ZDOTDIR-aware, so the file the installer edits is the one zsh actually reads
# and agrees with omz_present's own environment-aware detection.
_ZSHRC = zshrc_path(Path.home(), os.environ)
_RC_PATHS = [_ZSHRC, Path.home() / ".bashrc"]
_SHELL = os.environ.get("SHELL", "")

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


def _build_app(
    tools: list[Tool],
    platform: Platform,
    *,
    initial_view: str = BASE_VIEW,
    link_mode: str = "centralized",
) -> UnifiedApp:
    installed = {tool.id: is_installed(tool) for tool in tools}
    unavailable = {tool.id: not platform_could_support(tool, platform) for tool in tools}
    report, _status, _warning = doctor_data(
        tools,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
    )

    def _guard_state() -> tuple[dict[str, bool], str | None]:
        # Re-read, never a snapshot: the Policies view installs and removes the
        # pip/npm ban live in this same process, and both the Doctor report and
        # the Uninstall row describe exactly that state. One closure so the two
        # views can never disagree about it.
        return guard_state(_DEFAULT_BIN_DIR, os.environ.get("PATH", ""))

    rc_paths = rc_paths_for_mode(link_mode, _SHELL)
    rows = classify_tools(
        tools,
        _DEFAULT_BIN_DIR,
        installed=installed,
        platform=platform,
        reverse_deps=reverse_dependencies(tools),
    )
    # The Policies view offers what applies HERE; the teardown sweeps every
    # bundle. A bundle whose `platforms` tuple changed between installer
    # versions, or an rc file carried between machines, would otherwise leave a
    # block and a helper on disk with nothing reporting them.
    # tweak_present/tweak_executables_present already answer False for anything
    # not on disk, so the total sweep costs nothing.
    bundles = applicable_bundles(platform)

    def _do_uninstall(decision: UninstallDecision) -> SweepResult:
        # Runs live inside the UninstallScreen. rc_paths is the standard set so the
        # ban aliases are cleaned wherever they were written, regardless of mode.
        # The sweep result is returned so the view reports what came off.
        return perform_uninstall(
            decision,
            bin_dir=_DEFAULT_BIN_DIR,
            myshellrc_path=_MYSHELLRC,
            rc_paths=_RC_PATHS,
            bundles=BUNDLES,
            zshrc_path=_ZSHRC,
        )

    # Every environment row is a predicate, not its result: the Policies and
    # Doctor views mutate all three live in this same session, so the Uninstall
    # view re-evaluates them on entry (see UninstallInputs).
    uninstall_inputs = UninstallInputs(
        rows=rows,
        ban_names=lambda: [name for name, active in _guard_state()[0].items() if active],
        has_path_block=lambda: has_managed_block(_MYSHELLRC),
        remove=_do_uninstall,
        tweak_ids=lambda: active_tweak_ids(
            BUNDLES, rc_path=_MYSHELLRC, bin_dir=_DEFAULT_BIN_DIR, zshrc_path=_ZSHRC
        ),
    )
    policy_inputs = PolicyInputs(
        policies=[
            ban_policy(
                shim_dir=_DEFAULT_BIN_DIR,
                apply_rc_paths=ban_rc_paths(link_mode, _SHELL),
                remove_rc_paths=all_ban_rc_paths(),
                path_value=os.environ.get("PATH", ""),
                which=shutil.which,
            ),
            *(
                tweak_policy(
                    bundle,
                    rc_path=_MYSHELLRC,
                    bin_dir=_DEFAULT_BIN_DIR,
                    installed_tools=installed,
                    ensure_sourced_from=tuple(rc_paths) if link_mode == "split" else (),
                )
                for bundle in bundles
            ),
            omz_plugins_policy(
                zshrc_path=_ZSHRC,
                state_path=_MYSHELLRC,
                present=omz_present(Path.home(), os.environ),
            ),
        ]
    )

    def _apply_fix() -> None:
        # Runs live inside the DoctorScreen. A quiet console keeps configure_path's
        # own prints from corrupting the running TUI; the screen renders its own
        # result. Link mode is resolved before the app opens (never prompted while
        # the TUI is live).
        configure_path(
            tools,
            Console(file=io.StringIO()),
            platform=platform,
            default_bin_dir=_DEFAULT_BIN_DIR,
            myshellrc_path=_MYSHELLRC,
            rc_paths=rc_paths,
            link_mode=link_mode,
        )

    preview = (
        f"Will wire the managed bin dirs into "
        f"{', '.join(str(p) for p in rc_paths)} (mode: {link_mode}).\n"
        'For a different layout, run `make fix ARGS="--link-mode=centralized|single|split"`.'
    )

    # The audit asks the real pnpm what it manages globally, so it spawns a
    # process. DoctorScreen calls this only from a thread worker and holds the
    # answer itself, which is why there is no cache here any more: the cache
    # existed because every render re-read the report, and a cell written by the
    # reinstall worker and read by the event loop was a race waiting to be lost.
    # Preview and reinstall must receive the SAME policy object: the module's
    # preview-equals-effect guarantee rests on both paths reaching one argv
    # builder with one set of inputs.
    policy = pnpm_globals.node_install_policy(tools)

    def _node_globals_report() -> pnpm_globals.NodeGlobalsReport:
        return pnpm_globals.audit_node_globals(tools, policy=policy)

    def _globals_preview(report: pnpm_globals.NodeGlobalsReport) -> str:
        # Takes the audited report rather than fetching one: fetching would put
        # `pnpm list -g --json` back on whatever thread renders. `known` travels
        # with the set, so an unreadable global set has no preview and must not
        # borrow the empty set's "nothing to reinstall".
        return pnpm_globals.reinstall_preview(report.managed, known=report.known, policy=policy)

    def _reinstall_globals(packages: Sequence[str]) -> tuple[str, ...]:
        # The set to replay is the one the user saw and consented to, passed in
        # by the screen — not one re-derived here behind their back.
        return pnpm_globals.reinstall_node_globals(packages, policy=policy)

    return UnifiedApp(
        tools,
        installed,
        load_categories(_REGISTRY),
        report=report,
        guard_state=_guard_state,
        fix_preview=preview,
        fix=_apply_fix,
        uninstall=uninstall_inputs,
        policies=policy_inputs,
        node_globals=_node_globals_report,
        globals_preview=_globals_preview,
        reinstall_globals=_reinstall_globals,
        unavailable=unavailable,
        initial_view=initial_view,
    )


def _select_catalog(tools: list[Tool], *, link_mode: str = "centralized") -> list[str] | None:
    return _build_app(tools, detect(), link_mode=link_mode).run()


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


def _run_doctor(console: Console) -> int:
    tools = load_tools(_REGISTRY)
    platform = detect()
    if sys.stdin.isatty():
        _build_app(tools, platform, initial_view="doctor").run()
        return 0
    run_doctor(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
    )
    return 0


def _run_fix(console: Console, *, link_mode_option: str | None) -> int:
    # No re-audit after writing: the process PATH cannot change until the shell
    # restarts, so a post-fix audit would re-show "missing" and recreate the
    # confusion the doctor/fix split removes.
    tools = load_tools(_REGISTRY)
    platform = detect()
    if sys.stdin.isatty() and link_mode_option is None:
        # Resolve the link mode once BEFORE opening the app (the TUI cannot host a
        # questionary prompt). The DoctorScreen then previews and applies live.
        link_mode = _resolve_link_mode(None)
        _build_app(tools, platform, initial_view="doctor", link_mode=link_mode).run()
        return 0
    link_mode = _resolve_link_mode(link_mode_option)
    configure_path(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=rc_paths_for_mode(link_mode, _SHELL),
        link_mode=link_mode,
    )
    return 0


def _run_uninstall(console: Console, *, assume_yes: bool) -> int:
    platform = detect()
    if sys.stdin.isatty() and not assume_yes:
        _build_app(load_tools(_REGISTRY), platform, initial_view="uninstall").run()
        return 0
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    run_uninstall(
        load_tools(_REGISTRY),
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
        confirm=confirm,
        # Every bundle, not just the ones applicable here: a teardown must be
        # total (see _build_app).
        bundles=BUNDLES,
        zshrc_path=_ZSHRC,
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
    if options.guard or options.unguard:
        if sys.stdin.isatty() and not options.yes:
            # Honor an explicit --link-mode so the ban's aliases land in the same
            # rc files as the rest of the wiring; default stays centralized.
            link_mode = options.link_mode or "centralized"
            _build_app(
                load_tools(_REGISTRY), detect(), initial_view="policies", link_mode=link_mode
            ).run()
            return 0
        if options.guard:
            return _run_guard(
                console,
                remove=False,
                rc_paths=ban_rc_paths(_resolve_link_mode(options.link_mode), _SHELL),
                assume_yes=options.yes,
            )
        # Removal needs no link-mode prompt — it sweeps every rc file.
        return _run_guard(console, remove=True, rc_paths=all_ban_rc_paths(), assume_yes=options.yes)
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
    # Resolved once, before the catalog/Policies TUI opens: that same UnifiedApp
    # instance's Policies screen is where a tweak could be toggled mid-session,
    # so link_mode must be real BEFORE _select_catalog builds it, not only
    # before the later configure_path call.
    link_mode = _resolve_link_mode(options.link_mode)
    summary = run_wizard(
        tools,
        platform,
        prompter,
        console,
        options,
        on_mismatch=_ask_mismatch,
        category_blurbs=load_categories(_REGISTRY),
        select_catalog=lambda catalog_tools: _select_catalog(catalog_tools, link_mode=link_mode),
    )
    if summary is None:
        console.print("Aborted.")
        return 0
    configure_path(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=rc_paths_for_mode(link_mode, _SHELL),
        link_mode=link_mode,
    )
    _verify_and_clean(console, tools, platform, assume_yes=options.yes)
    # dependency_failed counts as a failed run: the tool was wanted, was
    # installable on this platform, and was skipped only because something it
    # requires failed. (no_method is deliberately excluded — a tool that has no
    # method here was never installable, which is not an error.)
    if summary.failed or summary.mismatched or summary.dependency_failed:
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
