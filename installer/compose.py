"""The composition root: builds the app and its services from the real environment.

`setup.py` parses arguments, owns the questionary and tty plumbing, and calls in here.
Everything in this module is strict-typed and counted by the coverage gate; it never
imports questionary or prompt_toolkit, so any prompt reaches it only as a parameter.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TypedDict, Unpack

from rich.console import Console

from installer import (
    cursor_shim,
    daemon,
    diskusage,
    env_redirect,
    pnpm_globals,
    schedules,
    systemd_daemon,
)
from installer.diskusage import DiskPressure
from installer.engine import ChecksumPolicy, InstallOutcome, install_tool
from installer.enums import DaemonState
from installer.install_ownership import run_probe
from installer.legacy_guard import remove_ban_blocks, remove_guard_shims
from installer.locations import (
    all_ban_rc_paths,
    rc_paths_for_mode,
    zshrc_path,
)
from installer.model import Tool
from installer.ownership import read_inventory
from installer.platform import Platform
from installer.policy import (
    Policy,
    cache_redirect_policy,
    desktop_shell_policy,
)
from installer.postinstall import which_with_brew
from installer.run import (
    OutputRunner,
    Runner,
    run_captured,
)
from installer.status import is_installed
from installer.terminal_shell import sync_message, sync_terminal_shells, terminal_sync_warning
from installer.tweaks import (
    LegacyStrip,
    strip_legacy_aliases,
)
from installer.update import UpdateService
from installer.version_cache import default_cache_path
from installer.version_status import VersionRefreshService
from installer.versions import TagResolver, probe_version_output, resolve_github_tag

# The private names setup.py imports back keep their names (D-05); listing them here is what
# tells pyright they are this module's surface and not unused private functions.
__all__ = [
    "_build_services",
    "_cache_redirect_policies",
    "_competitor_probe",
    "_desktop_shell_policies",
    "_disk_pressure_probe",
    "_invalidating",
    "_launch_repairs",
    "_reconcile_headless",
    "_schedule_context",
    "_schedule_removed_lines",
    "_split_sourced_from",
    "_sync_terminals",
    "_sync_terminals_and_report",
    "_timer_state_cache",
]

_REGISTRY = Path(__file__).parent / "registry.toml"
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
# The generic, FOREIGN ~/.shellrc some machines carry -- NOT a second file this
# project writes freely. It is only ever read, backed up, and replaced by a stub
# during D-04 consolidation, and only when that is provably safe.
_SHELLRC = Path.home() / ".shellrc"
# $ZDOTDIR-aware, so the file the installer edits is the one zsh actually reads
# and agrees with omz_present's own environment-aware detection.
_ZSHRC = zshrc_path(Path.home(), os.environ)
_RC_PATHS = [_ZSHRC, Path.home() / ".bashrc"]
_SHELL = os.environ.get("SHELL", "")
Install = Callable[..., InstallOutcome]
# WR-05: a dedicated stderr console, separate from the monkeypatch-able
# `Console` the routes build, so headless routes can announce the settings
# warning without a test double rerouting it.
_WARN_CONSOLE = Console(stderr=True)
# The disk-pressure probe and the Doctor's timer-state cache read the tmp cleanup's own
# artifacts, computed exactly like _MYSHELLRC (Path.home()-derived at import time): the
# LaunchAgent plist and the systemd user unit search dir.
_DAEMON_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{daemon.LABEL}.plist"
_LINUX_DAEMON_UNIT_DIR = systemd_daemon.user_unit_dir(Path.home(), os.environ)
# systemd's user environment generator reads $XDG_CONFIG_HOME/environment.d,
# so this honours XDG_CONFIG_HOME exactly like _LINUX_DAEMON_UNIT_DIR (WR-04).
_ENVIRONMENT_D_DIR = env_redirect.environment_d_dir(Path.home(), os.environ)


def _timer_state_cache(
    platform: Platform,
    *,
    which: Callable[[str], str | None],
    read_output: OutputRunner,
) -> systemd_daemon.TimerStateCache | None:
    """THE construction point for a TimerStateCache (D-01e): returns None for
    a macOS platform and None when this Linux host has no `systemctl` (the
    same host `schedules.manager_reachable` calls unavailable). Otherwise
    returns ONE cache over `timer_state(unit_dir, read_output=read_output)`
    built from the module-level unit-dir constant.

    Nothing else in this file may construct a TimerStateCache. Plan 15.7-06
    calls this same helper once per route and hands the result to the
    `_disk_pressure_probe` and to the schedule context's run seam, which
    invalidates it after every timer change.

    Never issues a query of its own: constructing the cache is a cheap
    object creation, and probing at construction would put a bounded-but-
    real subprocess on every route including ones that never read it.
    """
    if platform.os == "macos" or not systemd_daemon.systemd_available(which=which):
        return None
    return systemd_daemon.TimerStateCache(
        lambda: systemd_daemon.timer_state(_LINUX_DAEMON_UNIT_DIR, read_output=read_output)
    )


class _CompetitorProbe:
    """Zero-argument competing-mechanism probe with the same blocking switch
    as _DiskProbe (WR-10).

    blocking=True issues the bounded, READ-ONLY `systemctl list-unit-files`
    queries through the shared memo; blocking=False peeks and never spawns,
    which is the only verb a Textual render path may use. A cold peek answers
    "nothing detected", so a screen says nothing rather than guessing. This
    probe reaches no mutation verb in either scope: a system-scope competitor
    is disclosed and never touched (D-02a).
    """

    def __init__(self, cache: systemd_daemon.CompetitorCache | None) -> None:
        self._cache = cache

    def __call__(self, *, blocking: bool = True) -> tuple[systemd_daemon.CompetingUnit, ...]:
        cache = self._cache
        if cache is None:
            return ()
        if not blocking:
            peeked = cache.peek()
            return () if peeked is None else peeked
        return cache.read()


def _competitor_probe(
    platform: Platform,
    *,
    which: Callable[[str], str | None],
    read_output: OutputRunner,
) -> _CompetitorProbe:
    """THE construction point for a competing-mechanism probe (WR-10).

    Gated on exactly the D-01b condition `_timer_state_cache` uses, so one
    place in this file decides "this host has no systemd"; on macOS or a
    Linux host without systemctl the probe is inert and answers ().
    """
    if platform.os == "macos" or not systemd_daemon.systemd_available(which=which):
        return _CompetitorProbe(None)
    return _CompetitorProbe(
        systemd_daemon.CompetitorCache(
            lambda: systemd_daemon.detect_competing(read_output=read_output),
            ttl=systemd_daemon.COMPETITOR_CACHE_TTL,
        )
    )


class _DiskProbe:
    """Zero-argument disk probe with a blocking switch for the render path.

    The default is the blocking read: a `make doctor` run that reported a
    stale daemon state to avoid a short wait would trade correctness for
    nothing. The same wait on the Textual event loop is a frozen UI, so the
    row-highlight path passes blocking=False and reads TimerStateCache.peek,
    which never probes. A None peek omits the daemon-dependent half by
    answering UNAVAILABLE — ordinary warning wording, never a red finding.

    WHICH filesystem the free-space half measures is this class's other
    decision, and it is `Path.home()`'s — the filesystem holding the user's
    home directory — never `/`. `/` is not a portable stand-in for "the
    user's disk": on an ostree/composefs host (Bazzite, Silverblue) it is a
    ~45 MB read-only overlay that is 100% used and 0 bytes free by
    construction, so measuring it made `make doctor` print a permanent red
    "free disk space is low" on a machine with 400 GB free — the exact
    false positive D-03's conservative 15%/70% thresholds exist to avoid.
    macOS has the same shape in milder form (a read-only signed system
    volume with the user's data on `/System/Volumes/Data`).

    Resolving from home rather than branching on `Platform.immutable` is the
    more robust of the two: it needs no hardcoded `/var` that may not be a
    separate mount, it needs no marker-file detection to be right, it is the
    SAME measurement as before on a stock single-root host (home is under
    `/`), and it is additionally correct on a host with a separate `/home`
    partition, where `/` can be roomy while the user's disk is full. It also
    measures the filesystem this installer actually fills: every artifact it
    writes — `~/.local/opt`, `~/.local/bin`, `~/.cache` — lives under home.

    `Path.home()` is the same notion of home every other path constant in
    this file is built from (`_MYSHELLRC`, `_DAEMON_PLIST_PATH`, …), all of
    which resolve it at import time, so by the time this runs it is already
    known to resolve; no local fallback rule is invented here.
    """

    def __init__(
        self,
        *,
        platform: Platform,
        timer_cache: systemd_daemon.TimerStateCache | None,
        plist_path: Path,
        unit_dir: Path,
        usage: diskusage.UsageProbe = shutil.disk_usage,
    ) -> None:
        self._platform = platform
        self._timer_cache = timer_cache
        self._plist_path = plist_path
        self._unit_dir = unit_dir
        self._usage = usage

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
        # IN-03: a RELATIVE TMPDIR is ignored rather than measured against
        # whatever cwd this process happens to have, matching
        # systemd_daemon.user_unit_dir's own XDG rule.
        raw_tmp = os.environ.get("TMPDIR", "")
        tmp = raw_tmp if raw_tmp and Path(raw_tmp).is_absolute() else str(Path(os.sep) / "tmp")
        return diskusage.probe_disk_pressure(
            self._daemon(blocking=blocking),
            self._platform.os != "macos",
            Path.home(),
            Path(tmp),
            self._usage,
        )


def _disk_pressure_probe(
    platform: Platform,
    *,
    timer_cache: systemd_daemon.TimerStateCache | None,
    usage: diskusage.UsageProbe = shutil.disk_usage,
) -> _DiskProbe:
    """THE construction point for a disk-pressure probe.

    Resolves daemon state from the platform and the module-level artifact
    paths plus the INJECTED cache — never from a Policy, and never by
    constructing a TimerStateCache of its own. `timer_cache` is required
    because a default would silently build a second cache; None is a
    meaningful value (macOS, or Linux without systemctl) meaning
    DaemonState.UNAVAILABLE on Linux.

    `usage` is a real-defaulted injected seam (`shutil.disk_usage`), the same
    convention the schedule context's `which`/`run`/`read_output` follow, so
    this file's own tests can pin WHICH mount the probe measures against a
    fake mount table instead of against whatever the developer's machine
    happens to be partitioned like.
    """
    return _DiskProbe(
        platform=platform,
        timer_cache=timer_cache,
        plist_path=_DAEMON_PLIST_PATH,
        unit_dir=_LINUX_DAEMON_UNIT_DIR,
        usage=usage,
    )


def _cache_redirect_policies(
    platform: Platform,
    *,
    ensure_sourced_from: tuple[Path, ...] | Callable[[], tuple[Path, ...]] = (),
) -> tuple[Policy, ...]:
    """One cache-redirect Policy per declared redirect, for this platform.

    Built once and shared: the Policies list, the uninstall preview and the
    uninstall sweep must act on the same objects. The per-platform branch
    lives inside ``cache_redirect_policy``.

    ``ensure_sourced_from`` is ``_build_app``'s link-mode-aware closure
    (WR-07): in split mode no rc file sources ``~/.myshellrc``, so a macOS
    redirect written only there would never reach Bun. The CLI uninstall
    route keeps the ``()`` default, because removal needs no sourcing.
    """
    return tuple(
        cache_redirect_policy(
            redirect,
            platform_os=platform.os,
            conf_dir=_ENVIRONMENT_D_DIR,
            rc_path=_MYSHELLRC,
            home=Path.home(),
            ensure_sourced_from=ensure_sourced_from,
            system_conf_dirs=env_redirect.SYSTEM_ENVIRONMENT_D_DIRS,
        )
        for redirect in env_redirect.REDIRECTS
    )


def _sync_terminals(
    platform: Platform, *, report_changes: bool = False, strip_only: bool = False
) -> str | None:
    """The single Phase 15.6 terminal-shell synchronizer every lifecycle route
    reuses (D-01): Policies' OMZ-plugin apply, the direct `u` update,
    interactive ExecuteScreen close, unattended installation, the
    command-line uninstall route, and interactive Uninstall removal all call
    this exact closure, so a stale terminal shell configuration from any one
    path is corrected the same way. `_build_app` binds a zero-argument
    wrapper closing over its own resolved `platform` (`_sync_omz_terminals`);
    the two CLI-only lifecycle routes in `main`/`_run_uninstall` call this
    directly since neither builds a `UnifiedApp`.

    CR-04: `lookup` is `which_with_brew`, not a bare `shutil.which`, so a
    zsh that a brew install just placed on disk in this same process is
    still found. IN-01/CR-04: a revert is also surfaced now -- previously
    only `result.warnings` was ever read, so a full revert (zsh no longer
    discoverable) produced no message at all.
    """
    result = sync_terminal_shells(
        home=Path.home(),
        environ=os.environ,
        platform=platform,
        lookup=which_with_brew,
        strip_only=strip_only,
        runner=run_captured,  # herdr's reload; captured, so it never prints into the TUI
    )
    return sync_message(result, report_changes=report_changes)


def _sync_terminals_and_report(
    console: Console, platform: Platform, *, strip_only: bool = False
) -> None:
    """Run the shared terminal synchronizer and print any nonfatal warning to
    the console (D-01/15.6-06 Task 2) -- both non-interactive CLI lifecycle
    routes (`main`'s unattended install, `_run_uninstall`'s command-line
    teardown) call this after their own primary completion, so a raised
    exception is reported truthfully without ever flipping an already-determined
    exit code. WR-03: the catch and the message live in the one shared
    `terminal_sync_warning` contract, never in a try/except copied to this
    site."""
    warning = terminal_sync_warning(
        lambda: _sync_terminals(platform, report_changes=not strip_only, strip_only=strip_only)
    )
    if warning:
        console.print(warning)


class _InstallOptions(TypedDict, total=False):
    """The keyword options `install_tool` keeps; an omitted key stays omitted (R3-03)."""

    checksum_policy: ChecksumPolicy
    repair: bool


def _build_services(
    tools: list[Tool], platform: Platform, *, runner: Runner = run_captured
) -> tuple[VersionRefreshService, UpdateService, pnpm_globals.NodeInstallPolicy, Install]:
    """The one refresh service, the one update service and the one node-globals
    policy that every route shares (Phase 20 D-12, RESEARCH Pitfall 7): the TUI
    composition root and the headless `--all --yes` route both build their
    services here, so neither can act on a second epoch or a second policy.
    The policy is returned rather than recomputed so `_build_app`'s preview
    closures and the replay closure below hold the same object."""
    version_refresh = VersionRefreshService(
        platform=platform,
        cache_path=default_cache_path(),
        resolve_tag=resolve_github_tag,
        probe_output=probe_version_output,
        managed_bin_dir=_DEFAULT_BIN_DIR,
        native_probe=run_probe,
        # D-16, T-19-47: the pass only reads drift; it never writes a terminal config.
        terminal_drift=lambda live: sync_terminal_shells(
            home=Path.home(),
            environ=os.environ,
            platform=live,
            lookup=which_with_brew,
            write=False,
        ),
    )

    # Preview and reinstall must receive the SAME policy object: the module's
    # preview-equals-effect guarantee rests on both paths reaching one argv
    # builder with one set of inputs. Returned to `_build_app` for the preview.
    policy = pnpm_globals.node_install_policy(tools)

    def _reinstall_globals(packages: Sequence[str]) -> tuple[str, ...]:
        # The set to replay is the one the user saw and consented to, passed in
        # by the screen — not one re-derived here behind their back.
        return pnpm_globals.reinstall_node_globals(packages, policy=policy)

    def _terminal_follow_up() -> str | None:
        # D-01/15.6-05: the SAME terminal synchronizer every lifecycle route
        # reuses (`_sync_terminals`), bound to this composition's platform. A write is
        # named in the update's detail (X-01).
        return _sync_terminals(platform, report_changes=True)

    updates = UpdateService(
        platform=platform,
        # D-14, checker W2: the platform the last pass saw, read at update time.
        live_platform=lambda: version_refresh.platform,
        runner=runner,
        resolve_tag=resolve_github_tag,
        managed_packages=pnpm_globals.pnpm_global_packages,
        replay_globals=_reinstall_globals,
        # The pass's own evidence, freshly gathered (live platform, a fresh
        # inventory, `uv tool dir`, shim look-through, native probe).
        reresolve_ownership=version_refresh.resolve_owner,
        invalidate=version_refresh.invalidate,
        # D-01/15.6-05: a direct `u` update and a committed OMZ plugin edit both
        # end in the one shared synchronizer, never two.
        terminal_follow_up=_terminal_follow_up,
        # LIFE-10: `u` upgrades the casks that auto-update with the greedy flag.
        greedy_casks=version_refresh.greedy_casks,
    )

    def _install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        **options: Unpack[_InstallOptions],
    ) -> InstallOutcome:
        # D-04: the engine's already-installed short-circuit reads the same
        # published state that build_plan used to choose the row disposition.
        return install_tool(
            tool,
            platform,
            runner,
            resolve_tag,
            present=version_refresh.is_present,
            read_inventory_fn=read_inventory,
            **options,
        )

    return version_refresh, updates, policy, _install


def _split_sourced_from(link_mode: str) -> tuple[Path, ...]:
    """The rc files that source ~/.myshellrc under `link_mode`: split mode only."""
    if link_mode != "split":
        return ()
    return tuple(rc_paths_for_mode(link_mode, _SHELL))


def _desktop_shell_policies(platform: Platform) -> tuple[Policy, ...]:
    """The desktop SHELL row, Linux only: macOS has no environment.d desktop session."""
    if platform.os == "macos":
        return ()
    return (
        desktop_shell_policy(
            zsh_path=which_with_brew("zsh"), conf_dir=_ENVIRONMENT_D_DIR, home=Path.home()
        ),
    )


def _launch_repairs() -> tuple[LegacyStrip, tuple[tuple[str, str], ...]]:
    """The one repair step every route runs before anything else (D-15).

    Strips legacy alias blocks and removes the retired guard: the ban block from every rc file
    a guard could have written to, and the sentinel-marked shims in the managed bin dir. Each
    part never raises and never adds a file or a block.
    """
    return strip_legacy_aliases(_MYSHELLRC), (
        *remove_ban_blocks(all_ban_rc_paths()),
        *remove_guard_shims(_DEFAULT_BIN_DIR),
    )


def _schedule_context(
    platform: Platform, present: Callable[[str], bool]
) -> schedules.ScheduleContext:
    """The one context builder: the view, the reconciles and the sweep share these seams."""
    return schedules.context_for(
        platform.os,
        checkout=Path(__file__).resolve().parent.parent,
        which=shutil.which,
        present=present,
        read_models=cursor_shim.read_models,
    )


def _invalidating(
    ctx: schedules.ScheduleContext, cache: systemd_daemon.TimerStateCache | None
) -> schedules.ScheduleContext:
    """A timer change leaves the Doctor's cached timer state stale, whether it succeeded or not."""
    if cache is None:
        return ctx
    run = ctx.run

    def invalidate_after(cmd: list[str]) -> None:
        try:
            run(cmd)
        finally:
            cache.invalidate()

    return replace(ctx, run=invalidate_after)


def _schedule_removed_lines(ctx: schedules.ScheduleContext, tool_id: str) -> tuple[str, ...]:
    """A removed tool takes its timers with it and says so (D-09 amended by F3)."""
    report = schedules.after_target_removed(ctx, tool_id)
    return tuple(text for text, _severity in schedules.reconcile_lines(report))


def _reconcile_headless(
    console: Console, tools: list[Tool], platform: Platform, refresh: VersionRefreshService
) -> None:
    """Turn on the schedules nobody has decided about, after an install run (SPEC R3)."""
    launch = {tool.id: is_installed(tool) for tool in tools}
    ctx = _schedule_context(platform, refresh.installed_or(launch))
    for text, _severity in schedules.reconcile_lines(schedules.ensure_schedule_defaults(ctx)):
        console.print(text, markup=False, soft_wrap=True)
