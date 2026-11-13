"""Background maintenance mechanism for Linux: systemd user-timer + oneshot service unit
generation/parsing, `systemctl --user` invocation through an injectable run seam, the removal of
the previous installer's wrapper executable (reused from installer.daemon), and the "has any
decision ever been recorded" ownership marker -- the Linux mirror of installer/daemon.py's macOS
launchd mechanism.

Pure-enough plumbing that installer/schedules.py composes into the schedule engine. Nothing here
reads argv, prompts, or renders UI. Every external call goes through the injected
Runner/OutputRunner seams from installer/run.py -- this module never imports subprocess.
"""

from __future__ import annotations

import re
import shutil
import threading
import time
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from installer.atomic import atomic_write_bytes
from installer.daemon import (
    ENVIRONMENT_KEYS,
    DaemonScheduleError,
    ensure_log_path,
    remove_wrapper,
    wrapper_present,
)
from installer.enums import DaemonState
from installer.locations import xdg_config_base
from installer.run import CommandError, OutputRunner, Runner, run_captured, run_query
from installer.shellrc import apply_block, strip_block

# Re-exported (imported, never re-declared -- the schedule engine needs these same names
# rather than a parallel copy).
__all__ = [
    "COMPETING_UNITS",
    "DEFAULT_AGE_MINUTES",
    "DEFAULT_BOOT_DELAY",
    "DEFAULT_INTERVAL",
    "ENABLED_STATES",
    "INERT_STATES",
    "SCOPE_SYSTEM",
    "SCOPE_USER",
    "SERVICE_NAME",
    "STATE_CACHE_TTL",
    "SYSTEMCTL_QUERY_TIMEOUT",
    "TIMER_NAME",
    "COMPETITOR_CACHE_TTL",
    "CompetingUnit",
    "CompetitorCache",
    "TimerStateCache",
    "UNIT_BASENAME",
    "bootout",
    "bootstrap",
    "clean_timer_state",
    "clear_decided",
    "daemon_reload",
    "decided",
    "detect_competing",
    "disable_competing",
    "disable_timer",
    "ensure_log_path",
    "footprint_present",
    "parse_unit_files",
    "probe_timer_state",
    "query_systemctl",
    "record_decided",
    "remove_units",
    "remove_wrapper",
    "render_exec_service",
    "render_timer",
    "system_scope_warning",
    "systemd_available",
    "takeover_disclosure",
    "timer_state",
    "unit_paths",
    "units_present",
    "user_manager_reachable",
    "user_scope_failure_warning",
    "user_unit_dir",
    "wants_link_path",
    "wrapper_present",
    "write_unit_pair",
]

# Mirrors installer/daemon.py's LABEL -- a stable per-project unit basename,
# unlikely to collide with anything else the user's systemd user manager
# schedules.
UNIT_BASENAME = "tools-installer-prune-tmp"
SERVICE_NAME = f"{UNIT_BASENAME}.service"
TIMER_NAME = f"{UNIT_BASENAME}.timer"

# The confirmed-working ai-kit baseline cadence the source todo names
# explicitly ("a systemd user oneshot service run every 10 minutes") -- see
# the source todo and 15.7-RESEARCH.md. A boot delay so the very first run
# does not race a fresh login, then a steady 10-minute interval.
DEFAULT_BOOT_DELAY = "2min"
DEFAULT_INTERVAL = "10min"
DEFAULT_AGE_MINUTES = 10

# The "has any decision ever been recorded for this policy" ownership marker,
# mirroring installer/daemon.py's own _DECIDED_BEGIN/_DECIDED_END -- but with
# its OWN sentinel pair (15.7-RESEARCH.md Pattern 3), written into the SAME
# ~/.myshellrc state file, so recording a decision for this (Linux) daemon
# can never be mistaken for recording one for installer.daemon's own (macOS)
# policy, and the two are independently toggleable should both ever coexist
# in the codebase (they never run in the same process today -- OS-exclusive
# construction -- but the sentinel independence costs nothing to keep now).
_DECIDED_BEGIN = "# >>> tools-installer daemon-linux:decided >>>"
_DECIDED_END = "# <<< tools-installer daemon-linux:decided <<<"

# D-01c: every systemd QUERY this phase issues is bounded, so a wedged
# `systemctl` can never hang a policy apply or a Doctor entry. Short relative
# to run.QUERY_TIMEOUT's 20s default -- a `systemctl --user is-active` on a
# healthy user manager answers in milliseconds; a few seconds is generous
# headroom without ever approaching the point a synchronous caller would
# consider "the app looks frozen".
SYSTEMCTL_QUERY_TIMEOUT = 5.0

# D-01c: how long a memoized runtime-state answer is trusted before the next
# read() re-probes. Short enough that a toggle notices quickly even without
# invalidate(), long enough that a row-highlight-driven read() burst (e.g. a
# user holding an arrow key) collapses to one real probe.
STATE_CACHE_TTL = 5.0


def user_unit_dir(home: Path, environ: Mapping[str, str]) -> Path:
    """The systemd user unit search path: $XDG_CONFIG_HOME/systemd/user, or
    home/.config/systemd/user when XDG_CONFIG_HOME is unset or relative.

    systemd documents $XDG_CONFIG_HOME/systemd/user as the per-user unit
    search path, so the "systemd/user" SUB-PATH belongs to this module. The
    base-directory rule underneath it does not: it is shared verbatim with
    env_redirect.environment_d_dir, so it lives once in
    locations.xdg_config_base (lane-2 MEDIUM-01). A RELATIVE
    XDG_CONFIG_HOME is ignored rather than honoured -- see that helper for
    why (review LOW 15.7-01 / 15.7-04).
    """
    return xdg_config_base(home, environ) / "systemd" / "user"


def systemd_available(*, which: Callable[[str], str | None] = shutil.which) -> bool:
    """True when `systemctl` resolves on PATH -- the D-01b gate.

    Injected rather than probed directly so the composition root's own tests
    are deterministic on any host. Resolves a NAME; never spawns a process.
    """
    return which("systemctl") is not None


_REJECTED_CHARS = ('"', "\\", "%", "$", "\n", "\r")


def _quote(value: str) -> str:
    """Validate one rendered value and return it wrapped in double quotes.

    Raises DaemonScheduleError for a value containing a double quote, a
    backslash, a percent sign, a dollar sign, a newline, or a carriage
    return -- percent is rejected because systemd expands %-specifiers
    inside unit values, dollar because systemd substitutes $VAR/${VAR}
    inside ExecStart= arguments even quoted ones (IN-01), the rest because
    they break or inject into the unit grammar. Mirrors
    installer/daemon.py::render_agent_plist's fail-closed validation ordering:
    every value is validated before anything is returned.
    """
    for char in _REJECTED_CHARS:
        if char in value:
            raise DaemonScheduleError(f"value must not contain {char!r}: {value!r}")
    return f'"{value}"'


_CALENDAR_RE = re.compile(r"\*-\*-\* \d{2}(,\d{2})*:\d{2}:00")


def render_exec_service(
    *, argv: Sequence[str], environment: Mapping[str, str], description: str
) -> str:
    """The systemd unit (.service) INI text for a oneshot run of any argv.

    `argv[0]` must be absolute. The environment is closed to PATH, HOME and
    TMPDIR (rendered in that order, whichever are given); HOME and TMPDIR must
    be absolute and PATH non-empty. Every token and every KEY=value goes through
    _quote, and everything is validated before anything is returned, so a bad
    value can never reach a written unit file.
    """
    if not argv or not Path(argv[0]).is_absolute():
        raise DaemonScheduleError(f"argv[0] must be an absolute path: {list(argv)[:1]!r}")
    unknown = sorted(set(environment) - set(ENVIRONMENT_KEYS))
    if unknown:
        raise DaemonScheduleError(f"environment keys must be within {ENVIRONMENT_KEYS}: {unknown}")
    if "PATH" in environment and not environment["PATH"]:
        raise DaemonScheduleError("PATH must not be empty")
    for key in ("HOME", "TMPDIR"):
        if key in environment and not Path(environment[key]).is_absolute():
            raise DaemonScheduleError(f"{key} must be an absolute path: {environment[key]!r}")
    exec_start = " ".join(_quote(token) for token in argv)
    lines = [
        "[Unit]",
        f"Description={description}",
        "",
        "[Service]",
        "Type=oneshot",
        f"ExecStart={exec_start}",
        *(
            f"Environment={_quote(f'{key}={environment[key]}')}"
            for key in ENVIRONMENT_KEYS
            if key in environment
        ),
    ]
    return "\n".join(lines) + "\n"


def render_timer(
    *,
    description: str = "tools-installer background /tmp cleanup timer",
    on_calendar: str | None = None,
    basename: str = UNIT_BASENAME,
) -> str:
    """The systemd unit (.timer) INI text.

    With no `on_calendar`: a monotonic boot-delay + interval timer, which
    deliberately declares NO Persistent= key -- that key only gives catch-up
    semantics for an OnCalendar= timer, and declaring it on a monotonic
    OnBootSec=/OnUnitActiveSec= timer buys nothing while implying a catch-up
    guarantee systemd does not provide here (review LOW 15.7-01).

    With `on_calendar` (an explicit hour list, `*-*-* HH(,HH)*:MM:00`): an
    OnCalendar= timer with Persistent=true -- the form where Persistent= gives
    catch-up, firing a run missed while the machine was off at the next start.
    """
    if on_calendar is None:
        schedule_lines = [f"OnBootSec={DEFAULT_BOOT_DELAY}", f"OnUnitActiveSec={DEFAULT_INTERVAL}"]
    elif _CALENDAR_RE.fullmatch(on_calendar):
        schedule_lines = [f"OnCalendar={on_calendar}", "Persistent=true"]
    else:
        raise DaemonScheduleError(f"on_calendar must be an explicit hour list: {on_calendar!r}")
    lines = [
        "[Unit]",
        f"Description={description}",
        "",
        "[Timer]",
        *schedule_lines,
        f"Unit={basename}.service",
        "",
        "[Install]",
        "WantedBy=timers.target",
    ]
    return "\n".join(lines) + "\n"


def unit_paths(unit_dir: Path, *, basename: str = UNIT_BASENAME) -> tuple[Path, Path]:
    """(service_path, timer_path) under unit_dir -- never checks existence."""
    return unit_dir / f"{basename}.service", unit_dir / f"{basename}.timer"


def units_present(unit_dir: Path, *, basename: str = UNIT_BASENAME) -> bool:
    """True only when BOTH unit files exist."""
    service_path, timer_path = unit_paths(unit_dir, basename=basename)
    return service_path.exists() and timer_path.exists()


def wants_link_path(unit_dir: Path, *, basename: str = UNIT_BASENAME) -> Path:
    """The enablement symlink `systemctl --user enable` creates for the timer.

    The name is this project's own timer name inside the user unit dir, so the
    path identifies it as ours without reading the link target.
    """
    return unit_dir / "timers.target.wants" / f"{basename}.timer"


def footprint_present(unit_dir: Path, *, basename: str = UNIT_BASENAME) -> bool:
    """True when ANY file this project installs into unit_dir is on disk.

    The uninstall question is "is this ours", not "is it running" (CR-01): a
    stopped-but-enabled timer, or one whose user manager cannot be reached,
    still has files that restart it at the next login. Either unit file or a
    leftover enablement symlink (even a dangling one) counts.
    """
    service_path, timer_path = unit_paths(unit_dir, basename=basename)
    link = wants_link_path(unit_dir, basename=basename)
    return service_path.exists() or timer_path.exists() or link.is_symlink()


def write_unit_pair(
    unit_dir: Path, *, basename: str, service_text: str, timer_text: str
) -> tuple[Path, Path]:
    """Write already-rendered service and timer text atomically at 0o644.

    The caller renders first, so a render error never reaches the filesystem;
    the forced mode is independent of the umask or any pre-existing mode on the
    target (T-15.7-02). Returns (service_path, timer_path).
    """
    service_path, timer_path = unit_paths(unit_dir, basename=basename)
    unit_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(service_path, service_text.encode("utf-8"), mode=0o644)
    atomic_write_bytes(timer_path, timer_text.encode("utf-8"), mode=0o644)
    return service_path, timer_path


def remove_units(unit_dir: Path, *, basename: str = UNIT_BASENAME) -> None:
    """Delete both unit files and the timer's enablement symlink.

    missing_ok throughout, so it never raises when already gone. The symlink
    is removed by hand because `systemctl --user disable` cannot run when the
    user manager is unreachable, and a link left behind points at a deleted
    unit that the manager reports as missing at every login. Only a symlink is
    unlinked: a regular file at that path is not something enable creates.
    """
    for path in unit_paths(unit_dir, basename=basename):
        path.unlink(missing_ok=True)
    link = wants_link_path(unit_dir, basename=basename)
    if link.is_symlink():
        link.unlink(missing_ok=True)


def daemon_reload(*, run: Runner = run_captured) -> None:
    """`systemctl --user daemon-reload` -- reread every unit file on disk."""
    run(["systemctl", "--user", "daemon-reload"])


def disable_timer(*, basename: str = UNIT_BASENAME, run: Runner = run_captured) -> None:
    """`systemctl --user disable <timer>` -- undo `enable`'s wants symlink.

    No `--now`: this is the first-apply rollback, which undoes only what
    `bootstrap` did before it failed (WR-01).
    """
    run(["systemctl", "--user", "disable", f"{basename}.timer"])


def bootstrap(unit_dir: Path, *, basename: str = UNIT_BASENAME, run: Runner = run_captured) -> None:
    """Idempotently (re)register the timer: daemon-reload, enable, restart.

    Restart rather than start: a re-apply that rewrote the unit content must
    actually pick it up, and restart covers both the not-running and the
    running-with-stale-config cases. `unit_dir` is accepted for signature
    symmetry with installer.daemon.bootstrap's own (uid, plist_path, ...)
    shape and as a future extension point; systemctl resolves the timer by
    NAME against its own unit search path, not by the file path this
    process wrote it to.
    """
    del unit_dir
    daemon_reload(run=run)
    run(["systemctl", "--user", "enable", f"{basename}.timer"])
    run(["systemctl", "--user", "restart", f"{basename}.timer"])


def query_systemctl(cmd: list[str]) -> str:
    """Bounded OutputRunner adapter: every read-only systemd QUERY in this
    phase goes through this function.

    installer.run.run_query with SYSTEMCTL_QUERY_TIMEOUT and an accept_codes
    set covering the documented non-zero "this is the answer" exits for the
    read-only verbs this module issues -- `is-active` exits 3 for an
    inactive unit, `is-enabled` exits 1 for disabled and 4 for a missing
    unit file. Treating those as failures would turn every ordinary "no"
    into an exception. The timeout lives here, not at each call site,
    because OutputRunner is Callable[[list[str]], str] and has nowhere to
    put one (review MEDIUM 15.7-03). This becomes `read_output`'s real
    default everywhere in this phase. A side-effecting Runner call
    (bootstrap/bootout) is deliberately NOT routed through this bound
    adapter -- run_query's own docstring records why a bounded query and an
    unbounded mutation are different contracts.
    """
    return run_query(cmd, timeout=SYSTEMCTL_QUERY_TIMEOUT, accept_codes=(0, 1, 3, 4))


def stop_timer(*, basename: str, run: Runner = run_captured) -> None:
    """`systemctl --user stop <timer>` -- `clean` refuses an active timer, so stop it first."""
    run(["systemctl", "--user", "stop", f"{basename}.timer"])


def clean_timer_state(*, basename: str, run: Runner = run_captured) -> None:
    """`systemctl --user clean --what=state <timer>` -- drop the Persistent= stamp.

    `man systemd.timer` says to use this command before uninstalling a timer
    unit: without it the stamp survives and a later timer of the same name fires
    a catch-up for a schedule that is gone or re-timed. The caller runs it while
    the unit is still loaded. systemd refuses it on an ACTIVE timer, so a caller that keeps the
    timer (a re-time) stops it first with `stop_timer` and starts it again afterwards.
    """
    run(["systemctl", "--user", "clean", "--what=state", f"{basename}.timer"])


_REACHABLE_ANSWERS = frozenset({"initializing", "starting", "running", "degraded", "maintenance"})


def user_manager_reachable(*, read_output: OutputRunner = query_systemctl) -> bool:
    """Whether a systemd user manager answers `is-system-running`.

    Live-verified: an unreachable bus prints NOTHING on stdout and exits 1, so
    the answer keys on the stdout word, never on the exit code. Only
    initializing, starting, running, degraded and maintenance read reachable;
    empty output, offline, stopping, unknown or a timeout read unreachable.
    """
    try:
        output = read_output(["systemctl", "--user", "is-system-running"])
    except (CommandError, OSError):
        return False
    return output.strip() in _REACHABLE_ANSWERS


_ACTIVE_ANSWERS = frozenset({"active", "activating", "reloading"})
_INACTIVE_ANSWERS = frozenset({"inactive", "failed", "deactivating"})


def probe_timer_state(
    *, basename: str = UNIT_BASENAME, read_output: OutputRunner = query_systemctl
) -> DaemonState:
    """The ONE place in this phase that decides what "running" means.

    Runs a read-only `systemctl --user is-active <timer>` and maps its
    answer onto DaemonState: active/activating/reloading -> ACTIVE,
    inactive/failed/deactivating -> INACTIVE, an unreadable or unrunnable
    query -> UNAVAILABLE.
    """
    try:
        output = read_output(["systemctl", "--user", "is-active", f"{basename}.timer"])
    except (CommandError, OSError):
        return DaemonState.UNAVAILABLE
    answer = output.strip()
    if answer in _ACTIVE_ANSWERS:
        return DaemonState.ACTIVE
    if answer in _INACTIVE_ANSWERS:
        return DaemonState.INACTIVE
    return DaemonState.UNAVAILABLE


def timer_state(
    unit_dir: Path, *, basename: str = UNIT_BASENAME, read_output: OutputRunner = query_systemctl
) -> DaemonState:
    """What the Policy binds. Presence is a NECESSARY condition, never a
    sufficient one -- that ordering is the whole D-01c fix: files present +
    timer disabled now reads INACTIVE (the exact case the old
    presence-only predicate got wrong), while files absent short-circuits to
    INACTIVE for free, issuing zero argv.
    """
    if not units_present(unit_dir, basename=basename):
        return DaemonState.INACTIVE
    return probe_timer_state(basename=basename, read_output=read_output)


_Probed = TypeVar("_Probed")


class _ProbeCache(Generic[_Probed]):
    """Memoized value over one probe, with an injected monotonic clock.

    The read/peek/invalidate split and the locking are identical for every
    bounded systemd query this phase memoizes, so they live here once;
    TimerStateCache and CompetitorCache differ only in what they answer.
    """

    def __init__(
        self,
        probe: Callable[[], _Probed],
        *,
        ttl: float = STATE_CACHE_TTL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._probe = probe
        self._ttl = ttl
        self._clock = clock
        self._value: _Probed | None = None
        self._at: float | None = None
        # WR-03: the cache is shared by the event loop and thread workers
        # (the daemon-default apply, the Doctor probe, the execute screen's
        # verify). The lock guards the three fields; the generation, bumped
        # by every invalidate(), lets a read() whose probe started BEFORE an
        # invalidate discard its now-stale answer instead of storing it as
        # fresh. The probe itself runs outside the lock so a slow systemctl
        # never blocks peek().
        self._lock = threading.Lock()
        self._generation = 0

    def read(self) -> _Probed:
        """Return the memo when fresh; otherwise issue one bounded probe and
        store the answer. MAY block for up to the probe's own timeout.

        The answer is stored only when no invalidate() ran while the probe
        was in flight; otherwise it is returned but left unstored, so the
        next read() probes again.
        """
        with self._lock:
            now = self._clock()
            fresh = self._at is not None and (now - self._at) < self._ttl
            if self._value is not None and fresh:
                return self._value
            generation = self._generation
        value = self._probe()
        with self._lock:
            if generation == self._generation:
                self._value = value
                self._at = now
        return value

    def peek(self) -> _Probed | None:
        """The last stored answer whatever its age, or None if this cache has
        never been probed. NEVER probes, never blocks, never spawns.

        None means "never probed", NOT "the system state is unknown"
        (lane-2 LOW-01). invalidate() marks the stored answer STALE without
        discarding it (D-01e), so peek() still returns the last known value
        after an invalidate -- the next read() re-probes, but a render path
        in between keeps something to draw rather than falling back to None
        and flickering. A non-None peek() after an invalidate is therefore
        "cached, possibly stale"; only a cache that has never completed a
        read() answers None.
        """
        with self._lock:
            return self._value

    def invalidate(self) -> None:
        """Mark the stored answer STALE without discarding it: the next
        read() re-probes, while peek() can still report the last known
        answer instead of falling back to None (D-01e)."""
        with self._lock:
            self._at = None
            self._generation += 1


class TimerStateCache(_ProbeCache[DaemonState]):
    """Memoized runtime-state source over one DaemonState-returning probe,
    with an injected monotonic clock for deterministic TTL tests.

    D-01e: this is the ONE shared instance every consumer in this phase
    reads -- constructed once by setup.py::_timer_state_cache and injected
    into both the Linux daemon Policy and plan 15.7-06's disk-pressure
    probe. D-01c: the split between read()/peek() is load-bearing --
    read() may spawn one bounded probe (Policy.active/is_active, Doctor
    entry: an explicit user action or a one-per-route construction, never a
    per-keystroke path); peek() NEVER probes, never blocks, never spawns,
    and is the ONLY verb a Textual render path may call.
    """


def bootout(
    unit_dir: Path,
    *,
    basename: str = UNIT_BASENAME,
    run: Runner = run_captured,
    read_output: OutputRunner = query_systemctl,
) -> bool:
    """Unregister the timer, distinguishing "already gone" from a real
    failure -- the systemd equivalent of installer/daemon.py::bootout.

    ATTEMPTS the user-scope disable-now call unconditionally, whether or not
    the timer unit file is on disk -- installer/daemon.py:262-279 issues
    `launchctl bootout` unconditionally for the same reason: a deleted or
    hand-corrupted unit file can coexist with a still-loaded unit, and a
    presence gate would skip the one call that fixes it.

    On CommandError it re-probes systemd through probe_timer_state and
    classifies on that answer: ACTIVE -> re-raise (the timer is provably
    still running, so the failure is real); INACTIVE -> return True (the
    manager answered and nothing is running, so the caller may delete the
    files); UNAVAILABLE -> return False (the user manager could not be
    reached at all, e.g. `make uninstall` over ssh with no user bus). Systemd
    has no single ESRCH-equivalent exit code for `disable` (a missing unit
    exits 1, the same code a permission or manager failure uses), so the
    classification is made on systemd's own post-failure answer rather than
    on a code table or on stderr text, which would be locale-dependent.

    Returns whether the user manager was reached. False tells the caller to
    remove its owned files anyway and to DISCLOSE that no daemon-reload could
    run (CR-01): refusing would leave the files that restart the timer at the
    next login, which is worse. Invariant: a caller can never proceed past a
    failure while the timer is provably ACTIVE (review HIGH 15.7-01;
    T-15.7-39).
    """
    try:
        run(["systemctl", "--user", "disable", "--now", f"{basename}.timer"])
    except CommandError:
        state = probe_timer_state(basename=basename, read_output=read_output)
        if state is DaemonState.ACTIVE:
            raise
        return state is DaemonState.INACTIVE
    return True


# --- Competing-mechanism detection & takeover (D-02) -------------------------
#
# D-02a (ratified in 15.7-CONTEXT.md, 2026-09-22): "detect and disable/remove"
# applies as originally written ONLY to a USER-scope competitor -- genuinely
# detect, disable, and replace it. A SYSTEM-scope competitor is detected and
# DISCLOSED, never mutated: this project has no sudo/pkexec/doas call anywhere
# and its entire install model is userspace-only, so silently escalating
# privileges to touch a root-owned unit would be a first-ever architectural
# change nobody signed off. See the plan's <objective> for the full rationale.

# The one real, live-confirmed competing implementation (15.7-RESEARCH.md
# Pitfall 1, live-verified on the target host as SYSTEM-scope,
# /etc/systemd/system/cleanup-bun-tmp-cache.{service,timer}). Exact-name
# matching is a deliberate choice over a broader pattern-based heuristic --
# there is exactly one real, confirmed case today (15.7-RESEARCH.md Open
# Question 3).
COMPETING_UNITS: tuple[str, str] = (
    "cleanup-bun-tmp-cache.timer",
    "cleanup-bun-tmp-cache.service",
)
_COMPETING_TIMER_NAME, _COMPETING_SERVICE_NAME = COMPETING_UNITS

# The two systemd scopes a competing unit can live in. Named constants so no
# call site spells "user"/"system" by hand.
SCOPE_USER = "user"
SCOPE_SYSTEM = "system"

# D-02d: `systemctl list-unit-files` reports whether a unit FILE exists and
# how it is wired, not whether the mechanism is actually RUNNING. A unit
# whose enablement state is one of these is treated as live without a further
# probe -- the common case, one query per scope. Any other state (disabled,
# static, ...) gets ONE bounded `is-active` probe in its own scope before a
# verdict is reached; see detect_competing.
ENABLED_STATES: frozenset[str] = frozenset({"enabled", "enabled-runtime"})
# A masked unit can never be started by systemd short of unmasking it first --
# acting on it (or warning about it) would describe a mechanism that is
# structurally incapable of running, so it is dropped outright, unprobed.
INERT_STATES: frozenset[str] = frozenset({"masked", "masked-runtime"})

_LIST_UNIT_FILES_FLAGS: tuple[str, ...] = ("--no-legend", "--no-pager")


@dataclass(frozen=True)
class CompetingUnit:
    """One live (D-02d) pre-existing cleanup unit detected in either systemd
    scope -- the read-only detection result `detect_competing` returns."""

    name: str
    scope: str  # SCOPE_USER or SCOPE_SYSTEM
    state: str  # the enablement state list-unit-files reported


def parse_unit_files(output: str, names: Collection[str]) -> tuple[tuple[str, str], ...]:
    """Pure parse of a `systemctl list-unit-files` listing into (name, state)
    pairs for only the wanted unit names.

    Takes the first TWO whitespace-delimited columns of each non-empty line
    (name, enablement state); any further column -- the vendor-preset column
    this module never reads -- is ignored. A line whose first column is not
    exactly one of `names` (a summary line such as "2 unit files listed.", a
    legend line, an unrelated unit) is skipped -- the comparison is on the
    WHOLE first column, so a name that merely contains a wanted name as a
    substring never matches. A line carrying only a name and no second column
    yields that name with an empty state rather than raising -- ragged output
    degrades, never breaks a caller. Total over any input: never raises.
    """
    wanted = set(names)
    results: list[tuple[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        columns = line.split()
        name = columns[0]
        if name not in wanted:
            continue
        state = columns[1] if len(columns) > 1 else ""
        results.append((name, state))
    return tuple(results)


def _list_unit_files_cmd(*, user: bool) -> list[str]:
    prefix = ["systemctl", "--user"] if user else ["systemctl"]
    return [*prefix, "list-unit-files", *_LIST_UNIT_FILES_FLAGS, *COMPETING_UNITS]


def _is_active_cmd(name: str, *, user: bool) -> list[str]:
    prefix = ["systemctl", "--user"] if user else ["systemctl"]
    return [*prefix, "is-active", name]


def _detect_in_scope(*, user: bool, scope: str, read_output: OutputRunner) -> list[CompetingUnit]:
    try:
        listing = read_output(_list_unit_files_cmd(user=user))
    except (CommandError, OSError):
        # A machine without systemd, or one scope this process cannot read
        # (a wedged manager, a query timeout) degrades to "found nothing
        # there" -- the OTHER scope's own guard is independent, so one
        # unreadable scope never suppresses the other (T-15.7-12).
        return []
    found: list[CompetingUnit] = []
    for name, state in parse_unit_files(listing, COMPETING_UNITS):
        if state in INERT_STATES:
            continue
        if state in ENABLED_STATES:
            found.append(CompetingUnit(name=name, scope=scope, state=state))
            continue
        # D-02d: neither enabled-ish nor masked -- the listing alone cannot
        # say whether this is genuinely running (a unit started by hand while
        # `disabled`) or a dormant leftover. ONE bounded is-active probe
        # answers that, in the SAME scope the unit was found in.
        try:
            answer = read_output(_is_active_cmd(name, user=user))
        except (CommandError, OSError):
            # An unanswerable question must not manufacture a takeover of a
            # foreign unit -- degrade to "not a competitor", same as the
            # listing-probe guard above.
            continue
        if answer.strip() in _ACTIVE_ANSWERS:
            found.append(CompetingUnit(name=name, scope=scope, state=state))
    return found


def detect_competing(*, read_output: OutputRunner = query_systemctl) -> tuple[CompetingUnit, ...]:
    """Read-only, both-scope probe for a live (D-02d) pre-existing competing
    cleanup mechanism (D-02/D-02a).

    Probes the user scope and the system scope independently, each behind its
    own guard (see _detect_in_scope) -- a machine without systemd, or one
    where only one scope is unreadable, degrades to "found nothing there"
    rather than breaking a policy apply (T-15.7-12/T-15.7-42). Reading a
    system-scope unit listing needs no privilege, which is exactly why
    detection can span both scopes while mutation (disable_competing) never
    can. Every query goes through the injected `read_output`, whose real
    default is the bounded `query_systemctl` adapter -- never the unbounded
    `run_output` -- so a wedged systemd manager can never hang a policy apply
    (T-15.7-42).
    """
    found = [
        *_detect_in_scope(user=True, scope=SCOPE_USER, read_output=read_output),
        *_detect_in_scope(user=False, scope=SCOPE_SYSTEM, read_output=read_output),
    ]
    return tuple(found)


# How long a memoized competing-mechanism answer is trusted. Longer than
# STATE_CACHE_TTL: this answers "is another cleanup tool installed here",
# which only a deliberate install or a root command changes, and each read
# costs one list-unit-files per scope.
COMPETITOR_CACHE_TTL = 30.0


class CompetitorCache(_ProbeCache[tuple[CompetingUnit, ...]]):
    """Memoized read-only competing-mechanism detection (WR-10).

    The same read()/peek() contract TimerStateCache carries, for the same
    reason: read() may spawn bounded `systemctl list-unit-files`/`is-active`
    queries and so runs only on a worker or a CLI route, while a Textual
    render path may only peek(). Detection is read-only in BOTH scopes and
    this cache never reaches a mutation verb -- disclosure of a system-scope
    competitor is the whole point (D-02a).
    """


def disable_competing(
    units: Iterable[CompetingUnit], *, run: Runner = run_captured
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Disable (never delete -- D-02b) every USER-scope entry in `units`.

    Raises ValueError immediately -- before issuing a single argv -- when ANY
    entry is system-scope: a structural refusal, not a comment, so a future
    caller can never accidentally route a system-scope unit into a mutation
    path (T-15.7-10). This project has no sudo/pkexec/doas call anywhere;
    every argv this function can emit is a user-scope `systemctl` call.

    Issues one `systemctl --user disable --now <name>` call per entry, in
    NAME-SORTED order, collecting a per-entry CommandError OR OSError into
    the failed list instead of aborting the rest (D-02c, IN-07: an OSError
    partway through
    the loop used to escape and take the names already disabled, plus the
    system-scope disclosure, down with it) -- never a file-removing verb, never an unlink
    (D-02b): the competitor's unit files belong to whoever installed them,
    matching this project's own ownership discipline
    (daemon.remove_wrapper/wrapper_present's sentinel-checked
    refusal to touch a same-named artifact it did not create), and a disabled
    unit is a state the user can undo while a deleted one is not.

    The sort is load-bearing, not cosmetic (lane-2 HIGH-02): `systemctl
    list-unit-files` output order is not guaranteed stable across systemd
    versions or configurations, and detect_competing preserves whatever
    order it read. Without the sort, WHICH unit a partial failure leaves
    running -- and therefore every disclosure sentence built from the
    (disabled, failed) split -- would vary between two runs on the same
    machine. Mirrors system_scope_warning's own sorted() over the names it
    discloses. D-02c keeps the partial takeover itself: it proceeds and is
    disclosed, never rolled back by re-enabling what was already disabled.

    Returns (disabled_names, failed_names), each in that same sorted order.
    """
    units = tuple(units)
    if any(unit.scope == SCOPE_SYSTEM for unit in units):
        raise ValueError("disable_competing refuses a system-scope competing unit")
    units = tuple(sorted(units, key=lambda unit: unit.name))
    disabled: list[str] = []
    failed: list[str] = []
    for unit in units:
        try:
            run(["systemctl", "--user", "disable", "--now", unit.name])
        except (CommandError, OSError):
            failed.append(unit.name)
        else:
            disabled.append(unit.name)
    return tuple(disabled), tuple(failed)


def system_scope_warning(units: Iterable[CompetingUnit]) -> str | None:
    """A sentence disclosing every detected SYSTEM-scope competitor (D-02a),
    or None when there is none.

    Names the unit(s), states that a system-level cleanup service was found
    and will keep running alongside this app's own daemon, and quotes
    verbatim the root command(s) that stop and disable it -- this project
    never runs these commands itself (T-15.7-10); they are user-facing prose
    only. Says "stops and disables", never "removes" or "deletes" (D-02b):
    these commands leave the unit files in place.

    Lifecycle coverage (review LOW 15.7-03): quotes the timer's
    `disable --now` and, only when a system-scope SERVICE unit was ALSO
    detected, its explicit `stop` -- disabling the timer only prevents the
    NEXT trigger, a service already running from the last trigger keeps
    going, and a `.service` with no `[Install]` section cannot be disabled at
    all. A service command is never named when no service unit was found.
    """
    system_units = [unit for unit in units if unit.scope == SCOPE_SYSTEM]
    if not system_units:
        return None
    names = sorted({unit.name for unit in system_units})
    has_timer = any(unit.name == _COMPETING_TIMER_NAME for unit in system_units)
    has_service = any(unit.name == _COMPETING_SERVICE_NAME for unit in system_units)
    commands: list[str] = []
    if has_timer:
        commands.append(f"sudo systemctl disable --now {_COMPETING_TIMER_NAME}")
    if has_service:
        commands.append(f"sudo systemctl stop {_COMPETING_SERVICE_NAME}")
    return (
        f"A system-level cleanup service was found ({', '.join(names)}) and will keep running "
        "alongside this app's own daemon; this project cannot stop it without root, so it was "
        f"left untouched. Run `{'; '.join(commands)}` yourself to stop and disable it."
    )


def takeover_disclosure(disabled: Iterable[str]) -> str | None:
    """A sentence disclosing every user-scope competitor this run DID stop
    and disable (D-02, CR-02), or None when none was.

    A successful takeover changes another tool's behavior, so it is a
    disclosure, not a silent success: the on-by-default apply runs with no
    human watching, and without this line the user cannot tell why that
    tool's cleanup stopped. Says "stopped and disabled", never "removed"
    (D-02b), and quotes the user-scope command that undoes it.
    """
    names = tuple(disabled)
    if not names:
        return None
    commands = "; ".join(f"systemctl --user enable --now {name}" for name in names)
    return (
        f"Stopped and disabled {', '.join(names)}, another user-scope cleanup job, so it "
        "does not run alongside this app's own daemon; its unit files were left in place. "
        f"Run `{commands}` to re-enable it."
    )


def user_scope_failure_warning(failed: Iterable[str]) -> str | None:
    """A sentence disclosing every user-scope competitor this run could NOT
    disable (D-02c), or None when nothing failed.

    Names each unit, states that it is still running alongside this app's own
    daemon, and quotes the user-scope command the user can run themselves.
    This is what makes D-02c's "proceed and disclose" real: without it, a
    failed takeover is indistinguishable from a machine that never had a
    competitor (T-15.7-14).
    """
    names = tuple(failed)
    if not names:
        return None
    sentences = [
        f"{name} could not be stopped and disabled and is still running alongside this app's "
        f"own daemon; run `systemctl --user disable --now {name}` yourself to stop it."
        for name in names
    ]
    return " ".join(sentences)


def _decided_block() -> str:
    return "\n".join(
        (
            _DECIDED_BEGIN,
            "# This installer has made an on/off decision (auto-default or an",
            "# explicit user toggle) for the Linux background maintenance",
            "# daemon on this machine. Comments only: nothing here is executed.",
            _DECIDED_END,
        )
    )


def decided(state_path: Path) -> bool:
    """True once record_decided has written its marker block at least once.

    Own, independent sentinel pair from installer.daemon's -- recording the
    Linux marker leaves installer.daemon.decided() False on the same file,
    and vice versa. Mirrors installer/daemon.py::decided's "only a CLOSED
    begin..end block counts, last-closed-block-wins" discipline exactly.
    """
    if not state_path.exists():
        return False
    found = False
    inside = False
    for line in state_path.read_text().split("\n"):
        if line == _DECIDED_BEGIN:
            inside = True
        elif line == _DECIDED_END and inside:
            inside, found = False, True
    return found


def record_decided(state_path: Path) -> None:
    """Idempotently record that a decision has been made for this (Linux)
    policy -- reuses installer.shellrc.apply_block, then commits via a
    mode-PRESERVING atomic write (state_path is typically ~/.myshellrc)."""
    existing = state_path.read_text() if state_path.exists() else ""
    updated = apply_block(existing, _decided_block(), begin=_DECIDED_BEGIN, end=_DECIDED_END)
    atomic_write_bytes(state_path, updated.encode("utf-8"), mode=None)


def clear_decided(state_path: Path) -> None:
    """Strip the "decided" marker block; a no-op when absent or unrecorded."""
    if not state_path.exists():
        return
    original = state_path.read_text()
    stripped = strip_block(original, _DECIDED_BEGIN, _DECIDED_END)
    if stripped != original:
        atomic_write_bytes(state_path, stripped.encode("utf-8"), mode=None)
