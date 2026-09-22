"""Entry point for the tools-installer wizard. Run via `make setup` (uv run setup.py).

This is the composition root: it performs the real terminal IO (the Textual
catalog screen for selection; questionary for confirms and choices) and the
real home-path wiring, and composes the pure, fully-tested installer package.
It deliberately lives outside the `installer/` package so the untyped
questionary boundary is isolated from the strict-typed, fully-covered core.
"""

import contextlib
import io
import os
import selectors
import shutil
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import questionary
from prompt_toolkit.input import Input, create_input
from prompt_toolkit.output import Output, create_output
from rich.console import Console

from installer import daemon, diskusage, env_redirect, pnpm_globals, systemd_daemon
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
from installer.cli import Options, parse_args
from installer.diskusage import DiskPressure
from installer.enums import DaemonState
from installer.execute_screen import ExecuteInputs
from installer.install_ownership import run_probe
from installer.locations import all_ban_rc_paths, ban_rc_paths, rc_paths_for_mode, zshrc_path
from installer.model import Tool, load_categories, load_tools
from installer.omz import omz_present
from installer.ownership import (
    ManagerOwnership,
    read_inventory,
    removal_hint,
    removal_label,
    resolve_ownership,
)
from installer.platform import Platform, detect
from installer.policy import (
    DAEMON_DEFAULT_WAIT_SECONDS,
    DaemonDefaultWarnings,
    Policy,
    ban_policy,
    cache_redirect_policy,
    daemon_policy,
    ensure_daemon_default,
    linux_daemon_policy,
    omz_plugins_policy,
    tweak_policy,
)
from installer.postinstall import BREW_BIN_DIRS
from installer.prompt import CallbackPrompter
from installer.render import render_troubleshooting
from installer.resolve import platform_could_support
from installer.run import OutputRunner, Runner, run_captured
from installer.selection import Choice
from installer.settings import (
    SettingsStore,
    default_settings_path,
    link_mode_needs_choice,
    load_settings,
    resolve_link_mode,
)
from installer.shellrc import collect_bin_dirs, has_managed_block
from installer.status import is_installed
from installer.terminal_shell import sync_terminal_shells, terminal_sync_warning
from installer.tweaks import BUNDLES, applicable_bundles
from installer.ui_common import BASE_VIEW
from installer.uninstall import (
    SweepResult,
    ToolRow,
    active_tweak_ids,
    classify_tools,
    plan_uninstall,
    reverse_dependencies,
)
from installer.update import UpdateService
from installer.version_cache import default_cache_path
from installer.version_status import VersionRefreshService
from installer.versions import probe_version_output, resolve_github_tag
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs

_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
# $ZDOTDIR-aware, so the file the installer edits is the one zsh actually reads
# and agrees with omz_present's own environment-aware detection.
_ZSHRC = zshrc_path(Path.home(), os.environ)
_RC_PATHS = [_ZSHRC, Path.home() / ".bashrc"]
_SHELL = os.environ.get("SHELL", "")
# The daemon's own artifacts, computed exactly like _MYSHELLRC (Path.home()-derived
# at import time): the LaunchAgent plist, its log file, the wrapper script it
# invokes, and the "decided" ownership record. _DAEMON_STATE_PATH deliberately
# reuses _MYSHELLRC directly rather than introducing a new state file -- the
# daemon's ownership record lives in the SAME ~/.myshellrc omz_plugins_policy
# already uses for its own record (11-RESEARCH.md's "reuse ~/.myshellrc").
_DAEMON_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{daemon.LABEL}.plist"
_DAEMON_LOG_PATH = Path.home() / "Library" / "Logs" / "tools-installer" / "prune-daemon.log"
_DAEMON_SCRIPT_PATH = Path(__file__).parent / "scripts" / "prune-user-tmpdir.sh"
_DAEMON_STATE_PATH = _MYSHELLRC
# The Linux (systemd) daemon's own artifacts, mirroring the macOS constants
# immediately above: the systemd user unit search dir, its log file, and the
# cleanup script it invokes. _DAEMON_STATE_PATH is reused unchanged -- the
# Linux "decided" marker lives in the SAME ~/.myshellrc, under its OWN
# sentinel pair (installer.systemd_daemon's, independent of installer.daemon's).
_LINUX_DAEMON_UNIT_DIR = systemd_daemon.user_unit_dir(Path.home(), os.environ)
_LINUX_DAEMON_LOG_PATH = Path.home() / ".local" / "state" / "tools-installer" / "prune-daemon.log"
_LINUX_DAEMON_SCRIPT_PATH = Path(__file__).parent / "scripts" / "prune-tmp-linux.sh"
_ENVIRONMENT_D_DIR = Path.home() / ".config" / "environment.d"

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
    then calls _ask_confirm in the same run, and each library owns fd 0
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
    # See _questionary_tty_io()'s docstring for why questionary prompts get a
    # dedicated /dev/tty Input/Output pair instead of _stdin_on_tty()'s fd 0
    # redirect. Every ask_* helper needs this, not just the Textual .run()
    # call sites: _run_uninstall opens the uninstall TUI and then calls
    # _ask_confirm in the same run, and _run_guard does the same.
    with _questionary_tty_io() as io_pair, _darwin_select_based_asyncio():
        kwargs = {"input": io_pair[0], "output": io_pair[1]} if io_pair else {}
        answer = questionary.checkbox(
            message,
            choices=[
                questionary.Choice(
                    title=_title(c),
                    value=c.id,
                    checked=c.checked,
                    description=c.description or None,
                )
                for c in choices
            ],
            instruction=_CHECKBOX_KEYS,
            style=_STYLE,
            **kwargs,
        ).ask()
    if answer is None:  # questionary returns None on Ctrl+C / Ctrl+D at the prompt
        raise KeyboardInterrupt
    return list(answer)


def _ask_confirm(message: str) -> bool:
    with _questionary_tty_io() as io_pair, _darwin_select_based_asyncio():
        kwargs = {"input": io_pair[0], "output": io_pair[1]} if io_pair else {}
        answer = questionary.confirm(message, default=True, style=_STYLE, **kwargs).ask()
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


def _timer_state_cache(
    platform: Platform,
    *,
    which: Callable[[str], str | None],
    read_output: OutputRunner,
) -> systemd_daemon.TimerStateCache | None:
    """THE construction point for a TimerStateCache (D-01e): returns None for
    a macOS platform and None when this Linux host has no `systemctl` -- the
    SAME D-01b condition `_build_daemon_policy` gates on, so exactly one
    place in the codebase decides "this host has no systemd". Otherwise
    returns ONE cache over `timer_state(unit_dir, read_output=read_output)`
    built from the module-level unit-dir constant.

    Nothing else in this file may construct a TimerStateCache. Plan 15.7-06
    calls this same helper once per route and hands the result to both
    `_disk_pressure_probe` and `_build_daemon_policy`, which is what makes
    the cross-plan "SAME instance" invariant true by construction instead of
    by convention (review HIGH cycle 3).

    Never issues a query of its own: constructing the cache is a cheap
    object creation, and probing at construction would put a bounded-but-
    real subprocess on every route including ones that never read it.
    """
    if platform.os == "macos" or not systemd_daemon.systemd_available(which=which):
        return None
    return systemd_daemon.TimerStateCache(
        lambda: systemd_daemon.timer_state(_LINUX_DAEMON_UNIT_DIR, read_output=read_output)
    )


class _DiskProbe:
    """Zero-argument disk probe with a blocking switch for the render path.

    The default is the blocking read: a `make doctor` run that reported a
    stale daemon state to avoid a short wait would trade correctness for
    nothing. The same wait on the Textual event loop is a frozen UI, so the
    row-highlight path passes blocking=False and reads TimerStateCache.peek,
    which never probes. A None peek omits the daemon-dependent half by
    answering UNAVAILABLE — ordinary warning wording, never a red finding.
    """

    def __init__(
        self,
        *,
        platform: Platform,
        timer_cache: systemd_daemon.TimerStateCache | None,
        plist_path: Path,
        unit_dir: Path,
    ) -> None:
        self._platform = platform
        self._timer_cache = timer_cache
        self._plist_path = plist_path
        self._unit_dir = unit_dir

    def _daemon(self, *, blocking: bool) -> DaemonState:
        if self._platform.os == "macos":
            return DaemonState.ACTIVE if self._plist_path.exists() else DaemonState.INACTIVE
        cache = self._timer_cache
        if cache is None:
            return DaemonState.UNAVAILABLE
        if not blocking:
            peeked = cache.peek()
            return DaemonState.UNAVAILABLE if peeked is None else peeked
        return cache.read()

    def __call__(self, *, blocking: bool = True) -> DiskPressure:
        tmp = os.environ.get("TMPDIR", "") or str(Path(os.sep) / "tmp")
        return diskusage.probe_disk_pressure(
            self._daemon(blocking=blocking),
            self._platform.os != "macos",
            Path("/"),
            Path(tmp),
        )


def _disk_pressure_probe(
    platform: Platform,
    *,
    timer_cache: systemd_daemon.TimerStateCache | None,
) -> _DiskProbe:
    """THE construction point for a disk-pressure probe.

    Resolves daemon state from the platform and the module-level artifact
    paths plus the INJECTED cache — never from a Policy, and never by
    constructing a TimerStateCache of its own. `timer_cache` is required
    because a default would silently build a second cache; None is a
    meaningful value (macOS, or Linux without systemctl) meaning
    DaemonState.UNAVAILABLE on Linux.
    """
    return _DiskProbe(
        platform=platform,
        timer_cache=timer_cache,
        plist_path=_DAEMON_PLIST_PATH,
        unit_dir=_LINUX_DAEMON_UNIT_DIR,
    )


def _build_daemon_policy(
    platform: Platform,
    installed: Mapping[str, bool],
    *,
    which: Callable[[str], str | None] | None = None,
    run: Runner = run_captured,
    read_output: OutputRunner = systemd_daemon.query_systemctl,
    timer_cache: systemd_daemon.TimerStateCache | None = None,
) -> Policy | None:
    """The background tmpdir-prune daemon as a Policy -- the single, shared
    construction point both `_build_app` (the Policies list) and
    `_run_uninstall`'s non-interactive CLI teardown sweep call, so the two
    paths' state reads can never silently diverge.

    Dispatches on `platform.os`: a launchd policy on macOS, a systemd policy
    on a Linux host that has `systemctl` (D-01b), and None on a Linux host
    without it -- ROADMAP SC#2's "invisible/inert on Linux" is deliberately
    SUPERSEDED by this phase (D-01a): the Linux row is on by default from the
    interactive wizard's own `apply_daemon_default` allowlist, exactly like
    macOS.

    `which` defaults to None rather than being bound directly to
    `shutil.which`, so the RESOLUTION happens inside this function body at
    call time -- a dynamic `shutil.which(...)` lookup, not a value captured
    once when this module was imported -- keeping
    `test_build_daemon_policy_is_fail_closed_not_fail_hidden_for_a_bad_environment`'s
    existing `monkeypatch.setattr(setup.shutil, "which", ...)` technique
    working unchanged. It resolves BOTH the systemd-availability gate and
    the apply-time `uv` executable -- one injected lookup, matching
    `doctor_data`'s own `which` convention. `run`/`read_output` are
    real-defaulted injected seams so the composition root's own tests never
    touch the host's real systemctl/launchctl (review MEDIUM 15.7-03).
    `timer_cache`, when None, means "build your own" -- kept for
    `_run_uninstall`'s existing call site, which renders no probe, so
    identity is moot there.

    On macOS, resolves the real per-user TMPDIR/HOME and the apply-time `uv`
    executable into named locals: installer.daemon's own DaemonScheduleError
    is the fail-closed backstop for an empty/unresolvable value here
    (11-REVIEWS.md cycle 1 finding #19, extended to HOME by cycle 2 finding
    #1's composition-root half) -- this call site only resolves and names
    each value, it never re-validates it itself. `path_value` extends the
    real interactive PATH (never the raw, unmodified value alone) with both
    Homebrew prefixes and this project's own managed bin dir, since a bare
    LaunchAgent's own default environment PATH has neither (11-RESEARCH.md
    Pitfall 3).
    """
    resolved_which = which if which is not None else shutil.which
    if platform.os == "macos":
        tmpdir_value = os.environ.get("TMPDIR", "")  # DaemonScheduleError rejects empty/relative
        home_value = os.environ.get("HOME", "")  # DaemonScheduleError rejects empty/relative
        uv_path = Path(resolved_which("uv") or "")  # rejects a non-absolute path
        path_value = os.pathsep.join(
            (
                os.environ.get("PATH", ""),
                str(_DEFAULT_BIN_DIR),
                "/usr/local/bin",
                "/opt/homebrew/bin",
            )
        )
        return daemon_policy(
            plist_path=_DAEMON_PLIST_PATH,
            log_path=_DAEMON_LOG_PATH,
            wrapper_bin_dir=_DEFAULT_BIN_DIR,
            script_path=_DAEMON_SCRIPT_PATH,
            state_path=_DAEMON_STATE_PATH,
            installed_tools=installed,
            path_value=path_value,
            tmpdir_value=tmpdir_value,
            home_value=home_value,
            uv_path=uv_path,
            uid=os.getuid(),
            run=run,
        )
    # D-01b: the systemd-availability gate goes FIRST, before resolving any
    # path or constructing anything -- a container, a WSL image without
    # systemd, or a musl/openrc host degrades to exactly the behavior Linux
    # had before this phase (no row, no argv, no artifacts).
    if not systemd_daemon.systemd_available(which=resolved_which):
        return None
    tmpdir_value = os.environ.get("TMPDIR", "") or "/tmp"
    home_value = os.environ.get("HOME", "")  # DaemonScheduleError rejects empty/relative
    uv_path = Path(resolved_which("uv") or "")  # rejects a non-absolute path
    path_value = os.pathsep.join(
        (
            os.environ.get("PATH", ""),
            str(_DEFAULT_BIN_DIR),
            *(str(brew_dir) for brew_dir in BREW_BIN_DIRS),
        )
    )
    return linux_daemon_policy(
        unit_dir=_LINUX_DAEMON_UNIT_DIR,
        log_path=_LINUX_DAEMON_LOG_PATH,
        wrapper_bin_dir=_DEFAULT_BIN_DIR,
        script_path=_LINUX_DAEMON_SCRIPT_PATH,
        state_path=_DAEMON_STATE_PATH,
        installed_tools=installed,
        path_value=path_value,
        tmpdir_value=tmpdir_value,
        home_value=home_value,
        uv_path=uv_path,
        run=run,
        read_output=read_output,
        timer_cache=timer_cache,
    )


def _cache_redirect_policies(platform: Platform) -> tuple[Policy, ...]:
    """One cache-redirect Policy per declared redirect, for this platform.

    Built once and shared: the Policies list, the uninstall preview and the
    uninstall sweep must act on the same objects. The per-platform branch
    lives inside ``cache_redirect_policy``.
    """
    return tuple(
        cache_redirect_policy(
            redirect,
            platform_os=platform.os,
            conf_dir=_ENVIRONMENT_D_DIR,
            rc_path=_MYSHELLRC,
            home=Path.home(),
            ensure_sourced_from=(),
        )
        for redirect in env_redirect.REDIRECTS
    )


def _which_with_brew(name: str) -> str | None:
    """Resolve an executable like `shutil.which`, falling back to well-known
    Homebrew prefixes checked by disk presence.

    CR-04: on an immutable host -- Bazzite, the only host class this phase
    targets -- registry.toml's zsh entry has no rpm-ostree method and
    installs via the brew method (`formula = "zsh"`). `engine.py` only calls
    `prepend_path` for a method whose params include `bin_dir`, and the brew
    method declares none, so `/home/linuxbrew/.linuxbrew/bin` is never added
    to THIS process's own PATH. Immediately after the install this phase
    exists to react to, a bare `shutil.which("zsh")` still returned `None` in
    that same process, and the synchronizer took its revert branch instead of
    configuring anything -- silently, on the exact host this phase was built
    for. Reuses the fix pattern this project already has for the identical
    chicken-and-egg problem (`installer/postinstall.py::_resolve_rtk_binary`,
    `BREW_BIN_DIRS`).
    """
    found = shutil.which(name)
    if found:
        return found
    for brew_dir in BREW_BIN_DIRS:
        candidate = brew_dir / name
        if candidate.exists():
            return str(candidate)
    return None


def _sync_terminals(platform: Platform) -> str | None:
    """The single Phase 15.6 terminal-shell synchronizer every lifecycle route
    reuses (D-01): Policies' OMZ-plugin apply, the direct `u` update,
    interactive ExecuteScreen close, unattended installation, the
    command-line uninstall route, and interactive Uninstall removal all call
    this exact closure, so a stale terminal shell configuration from any one
    path is corrected the same way. `_build_app` binds a zero-argument
    wrapper closing over its own resolved `platform` (`_sync_omz_terminals`);
    the two CLI-only lifecycle routes in `main`/`_run_uninstall` call this
    directly since neither builds a `UnifiedApp`.

    CR-04: `lookup` is `_which_with_brew`, not a bare `shutil.which`, so a
    zsh that a brew install just placed on disk in this same process is
    still found. IN-01/CR-04: a revert is also surfaced now -- previously
    only `result.warnings` was ever read, so a full revert (zsh no longer
    discoverable) produced no message at all.
    """
    result = sync_terminal_shells(
        home=Path.home(),
        environ=os.environ,
        platform=platform,
        lookup=_which_with_brew,
    )
    messages = list(result.warnings)
    if result.reverted:
        messages.append("zsh is no longer present; reverted " + ", ".join(result.reverted))
    if messages:
        return "Terminal shell synchronization warning: " + "; ".join(messages)
    return None


def _sync_terminals_and_report(console: Console, platform: Platform) -> None:
    """Run the shared terminal synchronizer and print any nonfatal warning to
    the console (D-01/15.6-06 Task 2) -- both non-interactive CLI lifecycle
    routes (`main`'s unattended install, `_run_uninstall`'s command-line
    teardown) call this after their own primary completion, so a raised
    exception is reported truthfully without ever flipping an already-determined
    exit code. WR-03: the catch and the message live in the one shared
    `terminal_sync_warning` contract, never in a try/except copied to this
    site."""
    warning = terminal_sync_warning(lambda: _sync_terminals(platform))
    if warning:
        console.print(warning)


def _build_app(
    tools: list[Tool],
    platform: Platform,
    *,
    initial_view: str = BASE_VIEW,
    link_mode: str = "centralized",
    apply_daemon_default: bool = False,
    execute: ExecuteInputs | None = None,
    settings: SettingsStore | None = None,
    prompt_link_mode: bool = False,
    daemon_default_warnings: DaemonDefaultWarnings | None = None,
    disk_pressure: Callable[..., DiskPressure] | None = None,
    timer_cache: systemd_daemon.TimerStateCache | None = None,
) -> UnifiedApp:
    # One resolution, not two independent fallbacks: the routes that supply
    # neither argument (_run_doctor's TTY branch, _run_fix, _run_uninstall)
    # must still share one cache between the daemon Policy and the probe.
    if timer_cache is None and disk_pressure is None:
        timer_cache = _timer_state_cache(
            platform, which=shutil.which, read_output=systemd_daemon.query_systemctl
        )
    if disk_pressure is None:
        disk_pressure = _disk_pressure_probe(platform, timer_cache=timer_cache)
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

    def _current_link_mode() -> str:
        return settings.link_mode if settings is not None else link_mode

    # The catalog tool list never changes while the app runs -- only install
    # state does -- so this is computed once, outside the rows closure below.
    reverse_deps = reverse_dependencies(tools)

    def _uninstall_owner_hint(tool: Tool) -> str | None:
        # 15.4-05/D-05: reuse the catalog's ALREADY-COMPUTED ownership map
        # rather than running a second probe pass every time this screen
        # opens -- `version_refresh` is the same `VersionRefreshService`
        # instance the catalog's Owner column reads (hoisted above
        # `uninstall_inputs` below for exactly this binding), so one
        # resolution pass now feeds two screens. `fallback_name` is the
        # tool's own cmd, a prose TOOL identifier only -- `removal_hint`
        # (task 1) never lets it stand in for a package name in a command,
        # which is exactly the split-package defect (`ripgrep`/`rg`,
        # `git-core`/`git`) the Round-3 review caught.
        #
        # Freshness has THREE sources, not one, now that plan 15.4-04 task 3
        # made the protocol real: (1) `UnifiedApp._install_closed` re-enters
        # the active catalog, whose refresh worker repopulates the map; (2)
        # `UninstallInputs.invalidate` (bound below) makes `_apply_removal`
        # invalidate this same service after a successful sweep, so every
        # pre-removal record reports as unavailable through the epoch-gated
        # `ownership_of`; and (3) a screen opened BEFORE that background
        # refresh commits renders this fallback and then the
        # `OwnershipRefreshed` completion signal repaints it in place -- this
        # closure is re-called on that repaint too, never a one-shot read.
        # `ownership_of`'s two `None` cases (no pass has covered this tool,
        # or a mutation invalidated its record) are deliberately one return
        # value here: to this caller they mean the same thing, and both
        # degrade to the platform-filtered registry phrase (task 2) rather
        # than guessing.
        owned = version_refresh.ownership_of(tool.id)
        if owned is None:
            return None
        return removal_hint(owned, tool.cmd)

    def _uninstall_owner_label(tool: Tool) -> str | None:
        # CR-03: the TERSE half of the same binding, off the SAME map and the
        # same epoch gate, so the cell and the detail bar can never disagree
        # about which record they are describing. `removal_label` is
        # `removal_hint`'s declared counterpart in `installer/ownership.py`
        # and answers `None` for exactly the records `removal_hint` is silent
        # for, so this closure needs no second condition of its own.
        owned = version_refresh.ownership_of(tool.id)
        if owned is None:
            return None
        return removal_label(owned)

    def _uninstall_rows() -> list[ToolRow]:
        """Re-read presence on every call (D-06): a construction-time
        snapshot goes stale the moment this session installs or removes a
        tool, which Phase 13's live in-TUI install execution made routine.
        The same three calls the old one-time assignment composed --
        `is_installed`, `classify_tools`, `reverse_dependencies` -- just
        re-run on demand; `reverse_deps` above is the one piece that does
        not need re-computing per call."""
        installed_now = {tool.id: is_installed(tool) for tool in tools}
        return classify_tools(
            tools,
            _DEFAULT_BIN_DIR,
            installed=installed_now,
            platform=platform,
            reverse_deps=reverse_deps,
            owner_hint=_uninstall_owner_hint,
            owner_label_hint=_uninstall_owner_label,
        )

    # The Policies view offers what applies HERE; the teardown sweeps every
    # bundle. A bundle whose `platforms` tuple changed between installer
    # versions, or an rc file carried between machines, would otherwise leave a
    # block and a helper on disk with nothing reporting them.
    # tweak_present/tweak_executables_present already answer False for anything
    # not on disk, so the total sweep costs nothing.
    bundles = applicable_bundles(platform)

    # Constructed once, here, and shared: the Policies list below, the
    # on-by-default auto-apply closure, and the Uninstall teardown closures
    # (all wired further down) must never each build their own independent
    # daemon_policy instance -- all three need to read and act on the exact
    # same object.
    daemon = _build_daemon_policy(platform, installed, timer_cache=timer_cache)
    redirects = _cache_redirect_policies(platform)

    # Hoisted above `uninstall_inputs` (Round-1 review HIGH's post-removal
    # invalidation): the Uninstall screen's seam binds to this instance, so
    # it must exist before that construction. A pure construction with no
    # dependency on anything declared between here and its old position
    # below -- this is a reordering and nothing else.
    version_refresh = VersionRefreshService(
        platform=platform,
        cache_path=default_cache_path(),
        resolve_tag=resolve_github_tag,
        probe_output=probe_version_output,
        managed_bin_dir=_DEFAULT_BIN_DIR,
        native_probe=run_probe,
    )

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
            daemon_policy=daemon,
            extra_policies=redirects,
        )

    def _ban_apply_rc_paths() -> list[Path]:
        return ban_rc_paths(_current_link_mode(), _SHELL)

    def _tweak_ensure_sourced_from() -> tuple[Path, ...]:
        mode = _current_link_mode()
        if mode != "split":
            return ()
        return tuple(rc_paths_for_mode(mode, _SHELL))

    def _sync_omz_terminals() -> str | None:
        """Apply the shared terminal writer after a committed OMZ plugin edit,
        a successful direct catalog update, an interactive close, or a
        successful interactive Uninstall removal (D-01/15.6-05/15.6-06) -- a
        zero-arg wrapper closing over this call's own resolved `platform`
        around the one composition-root closure every call site reuses
        (`_sync_terminals` above), so a stale terminal shell configuration
        from any of them is corrected the same way."""
        return _sync_terminals(platform)

    # Every field is a predicate, not its result: the Policies and Doctor
    # views mutate the three environment fields live in this same session,
    # and this screen's own removal action changes what `rows` returns next
    # -- the Uninstall view re-evaluates all four on entry (see
    # UninstallInputs). `invalidate` mirrors `UpdateService`'s own seam
    # (below): a successful removal falsifies the shared version/ownership
    # data exactly like an install or an update does, and this closure is
    # what closes that hole (D-05). `terminal_sync` is the SAME closure
    # `omz_plugins_policy` below and `UnifiedApp`'s own `terminal_sync` kwarg
    # are bound with (D-01/15.6-06 Task 3) -- defined just above this
    # construction so the reference resolves at statement-execution time,
    # not only at call time.
    uninstall_inputs = UninstallInputs(
        rows=_uninstall_rows,
        ban_names=lambda: [name for name, active in _guard_state()[0].items() if active],
        has_path_block=lambda: has_managed_block(_MYSHELLRC),
        remove=_do_uninstall,
        tweak_ids=lambda: active_tweak_ids(
            BUNDLES,
            rc_path=_MYSHELLRC,
            bin_dir=_DEFAULT_BIN_DIR,
            zshrc_path=_ZSHRC,
            daemon_policy=daemon,
            extra_policies=redirects,
        ),
        invalidate=lambda: version_refresh.invalidate(reason="uninstall run finished"),
        # WR-01: the pass that REPLACES what the invalidate above drops, off
        # the same service the catalog's own refresh worker uses, so one
        # vocabulary of ownership feeds both screens. Called on a thread
        # worker by `_apply_removal` -- it re-probes every manager.
        refresh=lambda: version_refresh.refresh(tools),
        terminal_sync=_sync_omz_terminals,
    )

    policy_inputs = PolicyInputs(
        policies=[
            ban_policy(
                shim_dir=_DEFAULT_BIN_DIR,
                apply_rc_paths=_ban_apply_rc_paths,
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
                    ensure_sourced_from=_tweak_ensure_sourced_from,
                )
                for bundle in bundles
            ),
            omz_plugins_policy(
                zshrc_path=_ZSHRC,
                state_path=_MYSHELLRC,
                present=lambda: omz_present(Path.home(), os.environ),
                terminal_sync=_sync_omz_terminals,
            ),
            *((daemon,) if daemon is not None else ()),
            *redirects,
        ],
        link_mode=_current_link_mode if settings is not None else None,
        set_link_mode=settings.set_link_mode if settings is not None else None,
        disk_pressure=disk_pressure,
    )

    def _apply_fix() -> None:
        # Runs live inside the DoctorScreen. A quiet console keeps configure_path's
        # own prints from corrupting the running TUI; the screen renders its own
        # result. Link mode is re-read here so a Policies-view change takes
        # effect without rebuilding the app.
        mode = _current_link_mode()
        configure_path(
            tools,
            Console(file=io.StringIO()),
            platform=platform,
            default_bin_dir=_DEFAULT_BIN_DIR,
            myshellrc_path=_MYSHELLRC,
            rc_paths=rc_paths_for_mode(mode, _SHELL),
            link_mode=mode,
        )

    def preview() -> str:
        mode = _current_link_mode()
        paths = rc_paths_for_mode(mode, _SHELL)
        return (
            f"Will wire the managed bin dirs into "
            f"{', '.join(str(p) for p in paths)} (mode: {mode}).\n"
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

    # An ALLOWLIST, not the initial_view != "uninstall" blocklist that would
    # wrongly auto-apply for "doctor"/"policies" too (11-REVIEWS.md cycle 2
    # finding #14) -- make doctor is documented read-only (Makefile:19), and
    # --guard/--unguard's interactive branch must not silently register a
    # background deletion LaunchAgent either. Only _run_interactive_wizard's
    # own call site (the genuine, normal interactive make setup wizard flow)
    # passes apply_daemon_default=True. The daemon Policy object itself is
    # still appended to policy_inputs.policies above regardless of this flag,
    # so it remains visible/toggleable from every entry point -- only the
    # ON-BY-DEFAULT CALLBACK is gated here.
    daemon_default = None
    daemon_default_policy_id = None
    if daemon is not None and apply_daemon_default:
        daemon_policy_instance = daemon
        if daemon_default_warnings is not None:
            daemon_default_warnings.arm()

        def daemon_default() -> bool:
            # Closes over daemon_policy_instance, never the module-level
            # daemon_default local re-bound by this very assignment, and
            # never re-constructs a second daemon_policy: the SAME instance
            # already appended to policy_inputs.policies above.
            # finish() is unconditional for the same reason the worker's own
            # finally always posts: an exception outside
            # ensure_daemon_default's caught tuple must still signal, or the
            # console waits the full timeout for a signal that never comes.
            try:
                return ensure_daemon_default(
                    daemon_policy_instance,
                    on_warning=(
                        daemon_default_warnings.append
                        if daemon_default_warnings is not None
                        else None
                    ),
                )
            finally:
                if daemon_default_warnings is not None:
                    daemon_default_warnings.finish()

        daemon_default_policy_id = daemon.id

    def _reresolve_ownership(tool: Tool) -> ManagerOwnership:
        inventory = read_inventory(has_brew=platform.has_brew)
        artifacts = plan_uninstall([tool], _DEFAULT_BIN_DIR)
        return resolve_ownership(
            tool,
            platform=platform,
            inventory=inventory,
            artifacts=artifacts,
            which=shutil.which,
            managed_bin_dir=_DEFAULT_BIN_DIR,
            native_probe=run_probe,
        )

    updates = UpdateService(
        platform=platform,
        runner=run_captured,
        resolve_tag=resolve_github_tag,
        tools={tool.id: tool for tool in tools},
        managed_packages=pnpm_globals.pnpm_global_packages,
        replay_globals=_reinstall_globals,
        reresolve_ownership=_reresolve_ownership,
        invalidate=version_refresh.invalidate,
        # D-01/15.6-05: the SAME terminal closure `omz_plugins_policy` above
        # is wired with -- a direct `u` update and a committed OMZ plugin
        # edit both end in one shared synchronizer, never two.
        terminal_follow_up=_sync_omz_terminals,
    )

    if execute is not None:
        execute = replace(execute, version_refresh=version_refresh, updates=updates)

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
        daemon_default=daemon_default,
        daemon_default_policy_id=daemon_default_policy_id,
        version_refresh=version_refresh,
        updates=updates,
        execute=execute,
        prompt_link_mode=prompt_link_mode,
        # D-01/15.6-06 Task 1: the SAME closure `omz_plugins_policy` and
        # `updates` above are wired with -- every interactive close
        # re-synchronizes terminal configuration exactly like Policies' own
        # apply and the direct `u` update already do.
        terminal_sync=_sync_omz_terminals,
    )


def _execute_inputs(
    tools: list[Tool],
    platform: Platform,
    *,
    link_mode: str | Callable[[], str],
    unattended: bool,
    disk_pressure: Callable[[], DiskPressure],
) -> ExecuteInputs:
    def current_mode() -> str:
        return link_mode() if callable(link_mode) else link_mode

    def wire_path() -> str:
        mode = current_mode()
        buffer = io.StringIO()
        configure_path(
            tools,
            Console(file=buffer),
            platform=platform,
            default_bin_dir=_DEFAULT_BIN_DIR,
            myshellrc_path=_MYSHELLRC,
            rc_paths=rc_paths_for_mode(mode, _SHELL),
            link_mode=mode,
        )
        return buffer.getvalue()

    def verify() -> str:
        buffer = io.StringIO()
        run_doctor(
            tools,
            Console(file=buffer),
            platform=platform,
            default_bin_dir=_DEFAULT_BIN_DIR,
            path_value=os.environ.get("PATH", ""),
            exists=Path.is_dir,
            disk_pressure=disk_pressure,
        )
        return buffer.getvalue()

    return ExecuteInputs(
        catalog=tools,
        platform=platform,
        wire_path=wire_path,
        verify=verify,
        unattended=unattended,
    )


def _run_interactive_wizard(
    tools: list[Tool],
    platform: Platform,
    console: Console,
    options: Options,
    *,
    settings: SettingsStore,
    prompt_link_mode: bool,
) -> int:
    warnings = DaemonDefaultWarnings()
    # Built BEFORE _build_app: execute= evaluates _execute_inputs inside that
    # call's argument list, so the only way both receive the same probe (and
    # the same cache) is to name them here and pass each in.
    cache = _timer_state_cache(
        platform, which=shutil.which, read_output=systemd_daemon.query_systemctl
    )
    probe = _disk_pressure_probe(platform, timer_cache=cache)
    with _stdin_on_tty():
        # Only the genuine interactive wizard flow auto-applies the daemon
        # default (allowlist at the _build_app call site).
        app = _build_app(
            tools,
            platform,
            link_mode=settings.link_mode,
            apply_daemon_default=True,
            execute=_execute_inputs(
                tools,
                platform,
                link_mode=lambda: settings.link_mode,
                unattended=options.yes,
                disk_pressure=probe,
            ),
            settings=settings,
            prompt_link_mode=prompt_link_mode,
            daemon_default_warnings=warnings,
            disk_pressure=probe,
            timer_cache=cache,
        )
        app.run()
    # BEFORE the abort return: an aborted wizard is still a run whose
    # on-by-default apply may already have taken over another tool's timer.
    # app.run() does not join the thread worker, so this waits on the
    # collector the closure finishes, bounded so a wedged worker delays
    # rather than hangs.
    messages, completed = warnings.wait(DAEMON_DEFAULT_WAIT_SECONDS)
    for message in messages:
        console.print(message)
    if not completed:
        console.print("The background cleanup apply had not finished.")
    summary = app.install_summary
    if summary is None:
        console.print("Aborted.")
        return 0
    # run_doctor is deliberately NOT re-run here: the app already rendered
    # the read-only audit inside the execute screen. clean_rc_duplicates
    # stays on the console per 13-RESEARCH.md assumption A1 — it is a
    # separate destructive action with a confirm, and rebuilding it as a
    # third in-app confirm surface is out of scope.
    managed = set(collect_bin_dirs(tools, platform, _DEFAULT_BIN_DIR))
    confirm = (lambda _message: True) if options.yes else _ask_confirm
    clean_rc_duplicates(_RC_PATHS, managed, os.environ, console, confirm=confirm)
    if summary.failed or summary.mismatched or summary.dependency_failed:
        render_troubleshooting(console)
        return 1
    return 0


def _settings_store(link_mode_option: str | None) -> tuple[SettingsStore, bool]:
    path = default_settings_path()
    stored = load_settings(path).link_mode
    mode = resolve_link_mode(flag=link_mode_option, stored=stored)
    needs_choice = link_mode_needs_choice(flag=link_mode_option, stored=stored)
    return SettingsStore(path, link_mode=mode), needs_choice


def _run_doctor(console: Console) -> int:
    tools = load_tools(_REGISTRY)
    platform = detect()
    store, _needs_choice = _settings_store(None)
    if _has_controlling_tty():
        with _stdin_on_tty():
            _build_app(tools, platform, initial_view="doctor", settings=store).run()
        return 0
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
    )
    return 0


def _run_fix(console: Console, *, link_mode_option: str | None) -> int:
    # No re-audit after writing: the process PATH cannot change until the shell
    # restarts, so a post-fix audit would re-show "missing" and recreate the
    # confusion the doctor/fix split removes.
    tools = load_tools(_REGISTRY)
    platform = detect()
    store, needs_choice = _settings_store(link_mode_option)
    if _has_controlling_tty() and link_mode_option is None:
        with _stdin_on_tty():
            _build_app(
                tools,
                platform,
                initial_view="doctor",
                link_mode=store.link_mode,
                settings=store,
                prompt_link_mode=needs_choice,
            ).run()
        return 0
    configure_path(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=rc_paths_for_mode(store.link_mode, _SHELL),
        link_mode=store.link_mode,
    )
    return 0


def _run_uninstall(console: Console, *, assume_yes: bool) -> int:
    platform = detect()
    if _has_controlling_tty() and not assume_yes:
        store, _needs_choice = _settings_store(None)
        with _stdin_on_tty():
            _build_app(
                load_tools(_REGISTRY),
                platform,
                initial_view="uninstall",
                settings=store,
            ).run()
        return 0
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    tools = load_tools(_REGISTRY)
    # Mirrors _build_app's own installed computation, so the non-interactive
    # CLI teardown path gates fd/rg-aware daemon construction on the SAME
    # real-installed-status map the interactive path would use.
    installed = {tool.id: is_installed(tool) for tool in tools}
    run_uninstall(
        tools,
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
        confirm=confirm,
        # Every bundle, not just the ones applicable here: a teardown must be
        # total (see _build_app).
        bundles=BUNDLES,
        zshrc_path=_ZSHRC,
        daemon_policy=_build_daemon_policy(platform, installed),
        extra_policies=_cache_redirect_policies(platform),
    )
    # D-01/15.6-06 Task 2: absent zsh reverts only owned terminal
    # configuration (sync_terminal_shells' own no-zsh branch), so a teardown
    # that just removed zsh corrects the terminals the same way any other
    # completion route does.
    _sync_terminals_and_report(console, platform)
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
        if _has_controlling_tty() and not options.yes:
            # Honor an explicit --link-mode so the ban's aliases land in the same
            # rc files as the rest of the wiring; default stays centralized.
            store, _needs_choice = _settings_store(options.link_mode)
            with _stdin_on_tty():
                _build_app(
                    load_tools(_REGISTRY),
                    detect(),
                    initial_view="policies",
                    link_mode=store.link_mode,
                    settings=store,
                ).run()
            return 0
        if options.guard:
            store, _needs_choice = _settings_store(options.link_mode)
            return _run_guard(
                console,
                remove=False,
                rc_paths=ban_rc_paths(store.link_mode, _SHELL),
                assume_yes=options.yes,
            )
        # Removal needs no link-mode prompt — it sweeps every rc file.
        return _run_guard(console, remove=True, rc_paths=all_ban_rc_paths(), assume_yes=options.yes)
    can_proceed = options.all or bool(options.categories) or _has_controlling_tty()
    if not can_proceed:
        console.print(
            "No TTY detected. Re-run with --all or --categories A,B (and --yes) for "
            "non-interactive use, or --doctor to fix the PATH."
        )
        return 2
    tools = load_tools(_REGISTRY)
    platform = detect()
    prompter = CallbackPrompter(ask_checkbox=_ask_checkbox, ask_confirm=_ask_confirm)
    store, needs_choice = _settings_store(options.link_mode)
    if not options.all and not options.categories:
        return _run_interactive_wizard(
            tools,
            platform,
            console,
            options,
            settings=store,
            prompt_link_mode=needs_choice,
        )
    summary = run_wizard(
        tools,
        platform,
        prompter,
        console,
        options,
        on_mismatch=_ask_mismatch,
        category_blurbs=load_categories(_REGISTRY),
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
        rc_paths=rc_paths_for_mode(store.link_mode, _SHELL),
        link_mode=store.link_mode,
    )
    _verify_and_clean(console, tools, platform, assume_yes=options.yes)
    # D-01/15.6-06 Task 2: the same shared synchronizer every other lifecycle
    # route calls, after the unattended run's own summary is final.
    _sync_terminals_and_report(console, platform)
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
