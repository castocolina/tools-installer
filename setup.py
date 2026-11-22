"""Entry point for the tools-installer wizard.

Run via `make run` (`uv run --isolated --no-dev setup.py`).

This is the entrypoint: it parses arguments, owns the real terminal IO (the Textual
catalog screen for selection; questionary for confirms and choices) and calls the
composition root in `installer/compose.py`. It deliberately lives outside the
`installer/` package so the untyped questionary boundary is isolated from the
strict-typed, fully-covered core.
"""

import contextlib
import io
import os
import selectors
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import questionary
from prompt_toolkit.input import Input, create_input
from prompt_toolkit.output import Output, create_output
from rich.console import Console

from installer import (
    cursor_shim,
    post_install,
    runlock,
    schedules,
    systemd_daemon,
)
from installer.app import (
    clean_rc_duplicates,
    configure_path,
    run_doctor,
    run_uninstall,
    run_wizard,
)
from installer.cli import Options, parse_args
from installer.compose import (
    _DEFAULT_BIN_DIR,
    _MYSHELLRC,
    _RC_PATHS,
    _REGISTRY,
    _SHELL,
    _SHELLRC,
    _WARN_CONSOLE,
    _ZSHRC,
    _build_app,
    _build_services,
    _cache_redirect_policies,
    _competitor_probe,
    _desktop_shell_policies,
    _disk_pressure_probe,
    _launch_repairs,
    _reconcile_headless,
    _schedule_context,
    _schedule_removed_lines,
    _split_sourced_from,
    _sync_terminals,
    _sync_terminals_and_report,
    _timer_state_cache,
)
from installer.locations import (
    drop_project_venv_from_path,
    rc_paths_for_mode,
)
from installer.model import Tool, load_tools
from installer.notify import notifier_for
from installer.platform import Platform, detect
from installer.prompt import CallbackPrompter
from installer.receipts import scan_retired
from installer.render import render_troubleshooting
from installer.run import (
    Runner,
    apply_child_env,
    run_captured,
    run_captured_in_group,
    run_git_isolated,
)
from installer.schedule_run import RunDeps, run_schedule, update_all_runner, update_all_stdin_closed
from installer.schedules import SCHEDULE_DEFAULT_WAIT_SECONDS, ScheduleDefaultWarnings
from installer.session import exit_code, ran_anything
from installer.settings import (
    SettingsStore,
    default_settings_path,
    link_mode_needs_choice,
    load_settings,
    resolve_link_mode,
)
from installer.shellrc import collect_bin_dirs
from installer.status import is_installed
from installer.tweaks import (
    BUNDLES,
    LegacyStrip,
)
from installer.ui_common import run_live
from installer.update_check import git_for_check
from installer.version_status import probed_version
from installer.versions import probe_version_output
from installer.wizard_app import UnifiedApp

_STYLE = questionary.Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "bold"),
        ("selected", "fg:green"),
        ("instruction", "fg:#858585"),
        ("description", "fg:#858585 italic"),
    ]
)


def _has_controlling_tty() -> bool:
    """True when a real terminal is reachable for this run.

    `curl -fsSL ... | sh` pipes the script itself onto stdin, so
    `sys.stdin.isatty()` is always False there even when the user is sitting
    at a real terminal. sys.stdin.isatty() stays the primary check (a direct
    terminal run, and every existing test mocking sys.stdin, resolve here
    without ever touching the filesystem); only when it says False do we
    probe /dev/tty -- the controlling terminal -- before concluding this is a
    genuinely headless run (CI, a cron job, an IDE task runner). Mirrors
    ../ai-kit's setup.py open_tty()/is_interactive() pattern.
    """
    if sys.stdin.isatty():
        return True
    try:
        fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    except OSError:
        return False
    os.close(fd)
    return True


@contextlib.contextmanager
def _stdin_on_tty() -> Iterator[None]:
    """Point fd 0 at the controlling terminal for the duration of one Textual
    app's .run() call.

    Under `curl | sh`, the process inherits the script pipe as fd 0; Textual's
    driver reads keystrokes from `sys.__stdin__.fileno()` (fd 0) directly --
    not from any handle passed to it -- so without this the full-screen
    wizard can't be driven. A no-op when fd 0 is already a TTY (a direct
    terminal run). The original fd 0 is restored on exit, even on exception.
    Only stdin is touched: Textual writes its escape sequences to stderr,
    which under `curl | sh` is still the user's terminal.

    questionary/prompt_toolkit prompts do NOT use this helper -- see
    _questionary_tty_io() for why they get their own /dev/tty handle instead.
    """
    if os.isatty(0):
        yield
        return
    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    except OSError:
        # No controlling terminal -- _has_controlling_tty() has already gated
        # every call site that reaches here, so this is unreachable in the
        # current call graph. Kept as defense-in-depth: proceed without
        # redirect rather than mask the path.
        yield
        return
    saved = os.dup(0)
    try:
        os.dup2(tty_fd, 0)
        os.close(tty_fd)
        yield
    finally:
        os.dup2(saved, 0)
        os.close(saved)


@contextlib.contextmanager
def _questionary_tty_io() -> Iterator[tuple[Input, Output] | None]:
    """Build a prompt_toolkit Input/Output pair bound directly to a freshly
    opened /dev/tty, for questionary's `input=`/`output=` kwargs.

    Under `curl | sh`, fd 0 carries the script pipe, not a terminal.
    Redirecting fd 0 itself via os.dup2() (_stdin_on_tty(), used for
    Textual) gets prompt_toolkit's VT100 input driver to *read* correctly,
    but questionary needs its own file, independent of fd 0, regardless:
    _run_uninstall opens _build_app(..., initial_view="uninstall").run() and
    then calls ask_confirm in the same run, and each library owns fd 0
    exclusively while it's driving input. See _darwin_select_based_asyncio()
    for a second, unrelated macOS-only fix this pairs with.

    Yields None when fd 0 is already a TTY (a direct terminal run -- let
    questionary use its own stdin/stdout defaults) or when there is no
    controlling terminal to open (unreachable in the current call graph;
    every call site is already gated by _has_controlling_tty()).
    """
    if os.isatty(0):
        yield None
        return
    try:
        tty_in = io.TextIOWrapper(
            io.FileIO(os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY), "r+"),
            encoding="utf-8",
        )
        tty_out = io.TextIOWrapper(
            io.FileIO(os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY), "r+"),
            encoding="utf-8",
            line_buffering=True,
        )
    except OSError:
        yield None
        return
    try:
        yield create_input(tty_in), create_output(tty_out)
    finally:
        tty_in.close()
        tty_out.close()


@contextlib.contextmanager
def _darwin_select_based_asyncio() -> Iterator[None]:
    """Force asyncio to build its event loop on select.select() instead of
    kqueue, for the duration of one questionary prompt. Darwin only; a no-op
    everywhere else.

    Reported live on macOS + Python 3.14.7 (Homebrew): prompt_toolkit's
    asyncio event loop crashes registering /dev/tty's fd for reading --
    `OSError: [Errno 22] Invalid argument` from `loop.add_reader()` ->
    `KqueueSelector.register()` -> `kqueue.control()` -- even with a brand
    new fd that was never dup2'd onto fd 0 (ruling out the fd-reuse theory
    _questionary_tty_io() was originally written to fix; see its docstring).
    ubuntu-latest CI never reproduces this, so it's a kqueue/asyncio
    incompatibility specific to this platform+Python combination, not
    something under this codebase's control. `select.select()` handles the
    same fd without issue and is plenty fast for a handful of fds driving
    one interactive prompt, so swap asyncio's selector rather than chase a
    kqueue-level root cause. `selectors.DefaultSelector` is read fresh each
    time a new event loop is created (asyncio never caches the class), so
    patching the module attribute here reliably affects the loop
    questionary's `.ask()` creates via `asyncio.run()`.
    """
    if sys.platform != "darwin":
        yield
        return
    original = selectors.DefaultSelector
    selectors.DefaultSelector = selectors.SelectSelector
    try:
        yield
    finally:
        selectors.DefaultSelector = original


def ask_confirm(message: str, default: bool = True) -> bool:
    with _questionary_tty_io() as io_pair, _darwin_select_based_asyncio():
        kwargs = {"input": io_pair[0], "output": io_pair[1]} if io_pair else {}
        answer = questionary.confirm(message, default=default, style=_STYLE, **kwargs).ask()
    if answer is None:  # questionary returns None on Ctrl+C / Ctrl+D at the prompt
        raise KeyboardInterrupt
    return bool(answer)


def _ask_select(message: str, choices: list[tuple[str, str]]) -> str:
    with _questionary_tty_io() as io_pair, _darwin_select_based_asyncio():
        kwargs = {"input": io_pair[0], "output": io_pair[1]} if io_pair else {}
        answer = questionary.select(
            message,
            choices=[questionary.Choice(title=title, value=value) for title, value in choices],
            style=_STYLE,
            **kwargs,
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


def _print_repairs(
    console: Console, legacy: LegacyStrip, repairs: tuple[tuple[str, str], ...]
) -> None:
    for text, _severity in (*legacy.launch_lines(), *repairs):
        console.print(text, markup=False, soft_wrap=True)


def _run_interactive_wizard(
    tools: list[Tool],
    platform: Platform,
    console: Console,
    options: Options,
    *,
    settings: SettingsStore,
    prompt_link_mode: bool,
) -> int:
    warnings = ScheduleDefaultWarnings()
    with _stdin_on_tty():
        # Only the genuine interactive wizard flow reconciles the schedule
        # defaults (allowlist at the _build_app call site). _build_app builds
        # execute and the one shared timer cache / disk-pressure probe itself
        # (D-12), so the wizard passes no cache, probe or execute.
        app = _build_app(
            tools,
            platform,
            link_mode=settings.link_mode,
            apply_schedule_defaults=True,
            unattended=options.yes,
            settings=settings,
            prompt_link_mode=prompt_link_mode,
            schedule_default_warnings=warnings,
        )
        app.run()
    # BEFORE the abort return: an aborted wizard is still a run whose
    # on-by-default apply may already have taken over another tool's timer.
    # app.run() does not join the thread worker, so this waits on the
    # collector the closure finishes, bounded so a wedged worker delays
    # rather than hangs.
    messages, completed = warnings.wait(SCHEDULE_DEFAULT_WAIT_SECONDS)
    for message in messages:
        console.print(message)
    if not completed:
        console.print("The background cleanup apply had not finished.")
    if app.outcomes is None:
        console.print("Aborted.")
        # A hard abort while a run was in flight interrupted a real
        # run; that is a failure, not a clean abort.
        return 1 if app.run_in_flight else 0
    # run_doctor is deliberately NOT re-run here: the app already rendered
    # the read-only audit inside the execute screen. clean_rc_duplicates
    # stays on the console per 13-RESEARCH.md assumption A1 — it is a
    # separate destructive action with a confirm, and rebuilding it as a
    # third in-app confirm surface is out of scope.
    managed = set(collect_bin_dirs(tools, platform, _DEFAULT_BIN_DIR))
    confirm = (lambda _message: True) if options.yes else ask_confirm
    clean_rc_duplicates(_RC_PATHS, managed, os.environ, console, confirm=confirm)
    code = _session_exit_code(app)
    if code:
        render_troubleshooting(console)
    return code


def _settings_store(
    link_mode_option: str | None, *, announce_warning: bool = False
) -> tuple[SettingsStore, bool]:
    path = default_settings_path()
    loaded = load_settings(path)
    # The TUI shows the warning via startup_warning; every headless
    # route announces it here instead, before it acts on the default mode.
    if announce_warning and loaded.warning:
        _WARN_CONSOLE.print(loaded.warning, style="yellow", markup=False, soft_wrap=True)
    stored = loaded.settings.link_mode
    mode = resolve_link_mode(flag=link_mode_option, stored=stored)
    needs_choice = link_mode_needs_choice(flag=link_mode_option, stored=stored)
    return SettingsStore(path, link_mode=mode, warning=loaded.warning), needs_choice


def _session_exit_code(app: UnifiedApp) -> int:
    """The one exit rule for every TUI route (SAFE-05): a failed row, a PATH or
    verify error, or a run interrupted by a hard abort mid-flight exits
    1; everything else exits 0. A route that never ran a plan has no outcomes."""
    if app.run_in_flight or app.run_errors:
        return 1
    if app.outcomes is not None:
        return exit_code(app.outcomes.values())
    return 0


def _run_doctor(console: Console) -> int:
    tools = load_tools(_REGISTRY)
    platform = detect()
    tty = _has_controlling_tty()
    store, _needs_choice = _settings_store(None, announce_warning=not tty)
    if tty:
        with _stdin_on_tty():
            app = _build_app(tools, platform, initial_view="doctor", settings=store)
            app.run()
        return _session_exit_code(app)
    _print_repairs(console, *_launch_repairs())
    cache = _timer_state_cache(
        platform, which=shutil.which, read_output=systemd_daemon.query_systemctl
    )
    run_doctor(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        disk_pressure=_disk_pressure_probe(platform, timer_cache=cache),
        competing=_competitor_probe(
            platform, which=shutil.which, read_output=systemd_daemon.query_systemctl
        ),
    )
    return 0


def _run_fix(console: Console, *, link_mode_option: str | None) -> int:
    # No re-audit after writing: the process PATH cannot change until the shell
    # restarts, so a post-fix audit would re-show "missing" and recreate the
    # confusion the doctor/fix split removes.
    tools = load_tools(_REGISTRY)
    platform = detect()
    wired_tui = _has_controlling_tty() and link_mode_option is None
    store, needs_choice = _settings_store(link_mode_option, announce_warning=not wired_tui)
    if wired_tui:
        with _stdin_on_tty():
            app = _build_app(
                tools,
                platform,
                initial_view="doctor",
                link_mode=store.link_mode,
                settings=store,
                prompt_link_mode=needs_choice,
            )
            app.run()
        return _session_exit_code(app)
    _print_repairs(console, *_launch_repairs())
    configure_path(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        shellrc_path=_SHELLRC,
        rc_paths=rc_paths_for_mode(store.link_mode, _SHELL),
        link_mode=store.link_mode,
    )
    return 0


def _run_uninstall(console: Console, *, assume_yes: bool) -> int:
    platform = detect()
    if _has_controlling_tty() and not assume_yes:
        store, _needs_choice = _settings_store(None)
        with _stdin_on_tty():
            app = _build_app(
                load_tools(_REGISTRY),
                platform,
                initial_view="uninstall",
                settings=store,
            )
            app.run()
        return _session_exit_code(app)
    # D-12: the teardown shares one hold of the run lock with nothing else; a scheduled run
    # that holds it finishes first.
    run_lock = runlock.try_acquire(runlock.run_lock_path(), runlock.INSTALLER_JOB)
    if run_lock is None:
        console.print(runlock.BUSY_MESSAGE, markup=False, soft_wrap=True)
        return 1
    try:
        return _teardown_cli(console, platform, assume_yes=assume_yes)
    finally:
        run_lock.release()


def _teardown_cli(console: Console, platform: Platform, *, assume_yes: bool) -> int:
    # The launch repairs run before any read, so no read in this teardown sees a guard file.
    legacy, repairs = _launch_repairs()
    notice = legacy.uninstall_line()
    if notice is not None:
        console.print(notice, markup=False, soft_wrap=True)
    for text in legacy.failure_lines():
        console.print(text, markup=False, soft_wrap=True)
    for text, _severity in repairs:
        console.print(text, markup=False, soft_wrap=True)
    confirm = (lambda _message: True) if assume_yes else ask_confirm
    tools = load_tools(_REGISTRY)
    # Mirrors _build_app's own installed computation, the real-installed-status map the
    # interactive path would use.
    installed = {tool.id: is_installed(tool) for tool in tools}
    schedule_ctx = _schedule_context(platform, lambda tool_id: installed.get(tool_id, False))
    # Retired receipts join the teardown only; `installed` stays catalog-only.
    scan = scan_retired(frozenset(tool.id for tool in tools))
    for text in scan.warnings:
        console.print(text, markup=False, soft_wrap=True)
    _removed, failed = run_uninstall(
        [*tools, *scan.tools],
        console,
        runner=run_captured,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        confirm=confirm,
        # Every bundle, not just the ones applicable here: a teardown must be
        # total (see _build_app).
        bundles=BUNDLES,
        zshrc_path=_ZSHRC,
        extra_policies=(
            *_cache_redirect_policies(platform),
            *_desktop_shell_policies(platform),
            *schedules.sweep_adapters(schedule_ctx),
        ),
        schedule_removed=lambda tool_id: _schedule_removed_lines(schedule_ctx, tool_id),
    )
    # D-01/15.6-06 Task 2: absent zsh reverts only owned terminal
    # configuration (sync_terminal_shells' own no-zsh branch), so a teardown
    # that just removed zsh corrects the terminals the same way any other
    # completion route does.
    _sync_terminals_and_report(console, platform, strip_only=True)
    # A removal that failed is a failed teardown, whatever else the sweep did.
    return 1 if failed else 0


def _verify_and_clean(
    console: Console, tools: list[Tool], platform: Platform, *, assume_yes: bool
) -> None:
    cache = _timer_state_cache(
        platform, which=shutil.which, read_output=systemd_daemon.query_systemctl
    )
    run_doctor(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        disk_pressure=_disk_pressure_probe(platform, timer_cache=cache),
        competing=_competitor_probe(
            platform, which=shutil.which, read_output=systemd_daemon.query_systemctl
        ),
    )
    managed = set(collect_bin_dirs(tools, platform, _DEFAULT_BIN_DIR))
    confirm = (lambda _message: True) if assume_yes else ask_confirm
    clean_rc_duplicates(_RC_PATHS, managed, os.environ, console, confirm=confirm)


def _schedule_run_deps(
    tools: list[Tool], platform: Platform, *, runner: Runner = run_captured_in_group
) -> RunDeps:
    version_refresh, updates, _policy, _install = _build_services(tools, platform, runner=runner)
    return RunDeps(
        tools=tools,
        updates=updates,
        resolve_owner=version_refresh.resolve_owner,
        probe_version=lambda tool, own: probed_version(tool, own, probe_version_output),
        context=schedules.context_for(
            platform.os,
            checkout=Path(__file__).resolve().parent,
            read_models=cursor_shim.read_models,
        ),
        notify=notifier_for(platform.os),
        refresh=version_refresh,
        git=git_for_check,
    )


def _run_schedule(options: Options) -> int:
    """The headless timer route: no TTY, no repairs, exactly one plain result line."""
    with (
        update_all_stdin_closed()
        if options.run_schedule == "update-all"
        else contextlib.nullcontext()
    ):
        tools = load_tools(_REGISTRY)
        platform = detect()
        store, _needs_choice = _settings_store(options.link_mode)
        # Post-install steps run as after a manual update (SPEC R6).
        post_install.use_shell_init_sourcing(lambda: _split_sourced_from(store.link_mode))
        post_install.use_git_runner(run_git_isolated)
        line, code = run_schedule(
            options.run_schedule or "",
            _schedule_run_deps(tools, platform, runner=update_all_runner)
            if options.run_schedule == "update-all"
            else _schedule_run_deps(tools, platform),
            parent_holds_lock=options.parent_holds_run_lock,
            lock_holder_pid=options.lock_holder_pid,
        )
        print(line)
        return code


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    if options.run_schedule:
        return _run_schedule(options)
    console = Console()
    if options.doctor:
        return _run_doctor(console)
    if options.fix:
        return _run_fix(console, link_mode_option=options.link_mode)
    if options.uninstall:
        return _run_uninstall(console, assume_yes=options.yes)
    can_proceed = options.all or bool(options.categories) or _has_controlling_tty()
    if not can_proceed:
        console.print(
            "No TTY detected. Re-run with --all or --categories A,B (and --yes) for "
            "non-interactive use, or --doctor to fix the PATH."
        )
        return 2
    tools = load_tools(_REGISTRY)
    platform = detect()
    prompter = CallbackPrompter(ask_confirm=ask_confirm)
    # --all/--categories is the headless install route (it never opens the
    # wizard); the plain-TTY route shows the warning in the TUI instead.
    store, needs_choice = _settings_store(
        options.link_mode, announce_warning=bool(options.all or options.categories)
    )
    if not options.all and not options.categories:
        return _run_interactive_wizard(
            tools,
            platform,
            console,
            options,
            settings=store,
            prompt_link_mode=needs_choice,
        )
    _print_repairs(console, *_launch_repairs())
    post_install.use_shell_init_sourcing(lambda: _split_sourced_from(store.link_mode))
    post_install.use_git_runner(run_git_isolated)
    refresh, updates, _, install = _build_services(tools, platform)
    # D-12: the install run and the reconcile that follows it share one hold of the run lock.
    run_lock = runlock.try_acquire(runlock.run_lock_path(), runlock.INSTALLER_JOB)
    if run_lock is None:
        console.print(runlock.BUSY_MESSAGE, markup=False, soft_wrap=True)
        return 1
    try:
        outcomes = run_wizard(
            tools,
            prompter,
            console,
            options,
            refresh=refresh,
            updates=updates,
            install=install,
            terminal_sync=lambda: _sync_terminals(platform),
            on_mismatch=_ask_mismatch,
        )
        if outcomes is None:
            return 0
        _reconcile_headless(console, tools, platform, refresh)
    finally:
        run_lock.release()
    path_error: str | None = None
    verify_error: str | None = None
    if ran_anything(outcomes):
        _, path_error = run_live(
            lambda: configure_path(
                tools,
                console,
                platform=platform,
                default_bin_dir=_DEFAULT_BIN_DIR,
                myshellrc_path=_MYSHELLRC,
                shellrc_path=_SHELLRC,
                rc_paths=rc_paths_for_mode(store.link_mode, _SHELL),
                link_mode=store.link_mode,
            )
        )
        if path_error:
            console.print(f"PATH wiring could not be completed: {path_error}")
        _, verify_error = run_live(
            lambda: _verify_and_clean(console, tools, platform, assume_yes=options.yes)
        )
        if verify_error:
            console.print(f"PATH audit could not be completed: {verify_error}")
        _sync_terminals_and_report(console, platform)
    code = 1 if path_error or verify_error else exit_code(outcomes)
    if code:
        render_troubleshooting(console)
    return code


if __name__ == "__main__":
    drop_project_venv_from_path(Path(__file__).resolve().parent)
    apply_child_env(os.environ)
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        # Ctrl+C anywhere — at a prompt or mid-install — exits cleanly, no traceback.
        # 130 = 128 + SIGINT(2), the conventional shell code for interrupted programs.
        print("\nAborted.", file=sys.stderr)
        raise SystemExit(130) from None
