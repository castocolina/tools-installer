"""Background maintenance daemon mechanism: Linux systemd user-timer + oneshot
service unit generation/parsing, `systemctl --user` invocation through an
injectable run seam, the wrapper-executable install/remove mechanism (reused
from installer.daemon), and the "has any decision ever been recorded for this
policy" ownership marker -- the Linux mirror of installer/daemon.py's macOS
launchd mechanism (D-01).

Parallel to installer/daemon.py's mechanism-tier role: this module is
pure-enough plumbing that installer/policy.py's linux_daemon_policy factory
composes into an actual Policy. Nothing here reads argv, prompts, or renders
UI. Every external call goes through the injected Runner/OutputRunner seams
from installer/run.py -- this module never imports subprocess.
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from installer.atomic import atomic_write_bytes
from installer.daemon import (
    DEFAULT_CAP_BYTES,
    WRAPPER_COMMAND,
    DaemonScheduleError,
    ensure_log_path,
    install_wrapper,
    last_run_summary,
    remove_wrapper,
    wrapper_present,
)
from installer.enums import DaemonState
from installer.run import CommandError, OutputRunner, Runner, run_captured, run_query
from installer.shellrc import apply_block, strip_block

# Re-exported (imported, never re-declared -- installer/policy.py's Linux
# factory needs these same names, exactly like it already imports
# installer.daemon's WRAPPER_COMMAND/install_wrapper/etc. rather than
# re-declaring a parallel copy).
__all__ = [
    "DEFAULT_AGE_MINUTES",
    "DEFAULT_BOOT_DELAY",
    "DEFAULT_CAP_BYTES",
    "DEFAULT_INTERVAL",
    "SERVICE_NAME",
    "STATE_CACHE_TTL",
    "SYSTEMCTL_QUERY_TIMEOUT",
    "TIMER_NAME",
    "TimerStateCache",
    "UNIT_BASENAME",
    "WRAPPER_COMMAND",
    "bootout",
    "bootstrap",
    "clear_decided",
    "daemon_reload",
    "decided",
    "ensure_log_path",
    "install_wrapper",
    "last_run_summary",
    "probe_timer_state",
    "query_systemctl",
    "record_decided",
    "remove_units",
    "remove_wrapper",
    "render_service",
    "render_timer",
    "systemd_available",
    "timer_state",
    "unit_paths",
    "units_present",
    "user_unit_dir",
    "wrapper_present",
    "write_units",
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
    search path, so this read belongs to this module rather than a shared
    helper. A RELATIVE XDG_CONFIG_HOME is ignored rather than honoured: the
    XDG base-directory spec says a non-absolute value must be ignored, and
    honouring one here would resolve every unit path against whatever cwd
    the process happens to have (review LOW 15.7-01 / 15.7-04).
    """
    raw = environ.get("XDG_CONFIG_HOME", "")
    base = Path(raw) if raw and Path(raw).is_absolute() else home / ".config"
    return base / "systemd" / "user"


def systemd_available(*, which: Callable[[str], str | None] = shutil.which) -> bool:
    """True when `systemctl` resolves on PATH -- the D-01b gate.

    Injected rather than probed directly so the composition root's own tests
    are deterministic on any host. Resolves a NAME; never spawns a process.
    """
    return which("systemctl") is not None


_REJECTED_CHARS = ('"', "\\", "%", "\n", "\r")


def _quote(value: str) -> str:
    """Validate one rendered value and return it wrapped in double quotes.

    Raises DaemonScheduleError for a value containing a double quote, a
    backslash, a percent sign, a newline, or a carriage return -- percent is
    rejected because systemd expands %-specifiers inside unit values, the
    rest because they break or inject into the unit grammar. Mirrors
    installer/daemon.py::render_plist's fail-closed validation ordering:
    every value is validated before anything is returned.
    """
    for char in _REJECTED_CHARS:
        if char in value:
            raise DaemonScheduleError(f"value must not contain {char!r}: {value!r}")
    return f'"{value}"'


def render_service(
    *,
    uv_path: Path,
    wrapper_path: Path,
    script_path: Path,
    log_path: Path,
    tmpdir: str,
    home: str,
    path_value: str,
    cap_bytes: int = DEFAULT_CAP_BYTES,
    age_minutes: int = DEFAULT_AGE_MINUTES,
    description: str = "tools-installer background /tmp cleanup",
) -> str:
    """The systemd unit (.service) INI text for the oneshot cleanup run,
    fully validated first.

    ExecStart names, in order, the apply-time-resolved `uv` executable, then
    the installed wrapper's path as `uv run --script`'s target, then the
    cleanup script's own path -- mirroring installer/daemon.py::render_plist's
    ProgramArguments shape and installer/tweaks.py's `_COUNTDOWN_BODY`
    invocation pattern. Every token is double-quoted (D-01c/T-15.7-01) so a
    value containing a space is still one argv element and so a value cannot
    inject additional unit-file syntax.

    PATH/HOME/TMPDIR are resolved into Environment= assignments, not baked
    into ExecStart as flags -- this reaches scripts/prune-tmp-linux.sh's own
    environment reads with zero wrapper-side plumbing, since subprocess.run
    inherits the wrapper's own process environment by default. A freshly
    started systemd user manager's own default environment carries none of
    these reliably, mirroring the LaunchAgent default-environment gap
    installer/daemon.py::render_plist already documents.

    Every path/schedule argument is validated -- raising DaemonScheduleError
    the instant any is invalid -- BEFORE this function returns anything, so
    an empty TMPDIR/HOME, an unresolved `uv`, or an out-of-range age_minutes
    can never reach a written unit file or a systemctl bootstrap call.
    """
    for name, path_arg in (
        ("uv_path", uv_path),
        ("wrapper_path", wrapper_path),
        ("script_path", script_path),
        ("log_path", log_path),
    ):
        if not path_arg.is_absolute():
            raise DaemonScheduleError(f"{name} must be a non-empty absolute path: {path_arg!r}")
    if not tmpdir or not Path(tmpdir).is_absolute():
        raise DaemonScheduleError(f"tmpdir must be a non-empty absolute path: {tmpdir!r}")
    if not home or not Path(home).is_absolute():
        raise DaemonScheduleError(f"home must be a non-empty absolute path: {home!r}")
    if age_minutes < 1:
        raise DaemonScheduleError(f"age_minutes must be >= 1: {age_minutes!r}")

    exec_tokens = [
        str(uv_path),
        "run",
        "--no-project",
        "--script",
        str(wrapper_path),
        "--script",
        str(script_path),
        "--log",
        str(log_path),
        "--cap-bytes",
        str(cap_bytes),
        "--",
        "--apply",
        "--minutes",
        str(age_minutes),
    ]
    exec_start = " ".join(_quote(token) for token in exec_tokens)
    lines = [
        "[Unit]",
        f"Description={description}",
        "",
        "[Service]",
        "Type=oneshot",
        f"ExecStart={exec_start}",
        f"Environment={_quote(f'PATH={path_value}')}",
        f"Environment={_quote(f'HOME={home}')}",
        f"Environment={_quote(f'TMPDIR={tmpdir}')}",
    ]
    return "\n".join(lines) + "\n"


def render_timer(*, description: str = "tools-installer background /tmp cleanup timer") -> str:
    """The systemd unit (.timer) INI text: a monotonic boot-delay + interval
    timer, never an OnCalendar= one.

    Deliberately declares NO Persistent= key: that key only gives catch-up
    semantics for an OnCalendar= timer, and declaring it on a monotonic
    OnBootSec=/OnUnitActiveSec= timer buys nothing while implying a catch-up
    guarantee systemd does not provide here (review LOW 15.7-01).
    """
    lines = [
        "[Unit]",
        f"Description={description}",
        "",
        "[Timer]",
        f"OnBootSec={DEFAULT_BOOT_DELAY}",
        f"OnUnitActiveSec={DEFAULT_INTERVAL}",
        f"Unit={SERVICE_NAME}",
        "",
        "[Install]",
        "WantedBy=timers.target",
    ]
    return "\n".join(lines) + "\n"


def unit_paths(unit_dir: Path) -> tuple[Path, Path]:
    """(service_path, timer_path) under unit_dir -- never checks existence."""
    return unit_dir / SERVICE_NAME, unit_dir / TIMER_NAME


def units_present(unit_dir: Path) -> bool:
    """True only when BOTH unit files exist."""
    service_path, timer_path = unit_paths(unit_dir)
    return service_path.exists() and timer_path.exists()


def write_units(
    unit_dir: Path,
    *,
    uv_path: Path,
    wrapper_path: Path,
    script_path: Path,
    log_path: Path,
    tmpdir: str,
    home: str,
    path_value: str,
    cap_bytes: int = DEFAULT_CAP_BYTES,
    age_minutes: int = DEFAULT_AGE_MINUTES,
) -> None:
    """Validate and write both unit files atomically at 0o644.

    render_service/render_timer run FIRST; a DaemonScheduleError propagates
    with zero filesystem side effects (no partial/temp file, no directory
    created). Only once both renders succeed does this create unit_dir and
    write each file through installer.atomic.atomic_write_bytes with an
    explicit, forced mode=0o644 -- independent of the invoking process's
    umask or any pre-existing mode on the target file (T-15.7-02).
    """
    service_text = render_service(
        uv_path=uv_path,
        wrapper_path=wrapper_path,
        script_path=script_path,
        log_path=log_path,
        tmpdir=tmpdir,
        home=home,
        path_value=path_value,
        cap_bytes=cap_bytes,
        age_minutes=age_minutes,
    )
    timer_text = render_timer()
    service_path, timer_path = unit_paths(unit_dir)
    unit_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(service_path, service_text.encode("utf-8"), mode=0o644)
    atomic_write_bytes(timer_path, timer_text.encode("utf-8"), mode=0o644)


def remove_units(unit_dir: Path) -> None:
    """Delete both unit files (missing_ok) -- never raises when already gone."""
    for path in unit_paths(unit_dir):
        path.unlink(missing_ok=True)


def daemon_reload(*, run: Runner = run_captured) -> None:
    """`systemctl --user daemon-reload` -- reread every unit file on disk."""
    run(["systemctl", "--user", "daemon-reload"])


def bootstrap(unit_dir: Path, *, run: Runner = run_captured) -> None:
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
    run(["systemctl", "--user", "enable", TIMER_NAME])
    run(["systemctl", "--user", "restart", TIMER_NAME])


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


_ACTIVE_ANSWERS = frozenset({"active", "activating", "reloading"})
_INACTIVE_ANSWERS = frozenset({"inactive", "failed", "deactivating"})


def probe_timer_state(*, read_output: OutputRunner = query_systemctl) -> DaemonState:
    """The ONE place in this phase that decides what "running" means.

    Runs a read-only `systemctl --user is-active <timer>` and maps its
    answer onto DaemonState: active/activating/reloading -> ACTIVE,
    inactive/failed/deactivating -> INACTIVE, an unreadable or unrunnable
    query -> UNAVAILABLE.
    """
    try:
        output = read_output(["systemctl", "--user", "is-active", TIMER_NAME])
    except (CommandError, OSError):
        return DaemonState.UNAVAILABLE
    answer = output.strip()
    if answer in _ACTIVE_ANSWERS:
        return DaemonState.ACTIVE
    if answer in _INACTIVE_ANSWERS:
        return DaemonState.INACTIVE
    return DaemonState.UNAVAILABLE


def timer_state(unit_dir: Path, *, read_output: OutputRunner = query_systemctl) -> DaemonState:
    """What the Policy binds. Presence is a NECESSARY condition, never a
    sufficient one -- that ordering is the whole D-01c fix: files present +
    timer disabled now reads INACTIVE (the exact case the old
    presence-only predicate got wrong), while files absent short-circuits to
    INACTIVE for free, issuing zero argv.
    """
    if not units_present(unit_dir):
        return DaemonState.INACTIVE
    return probe_timer_state(read_output=read_output)


class TimerStateCache:
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

    def __init__(
        self,
        probe: Callable[[], DaemonState],
        *,
        ttl: float = STATE_CACHE_TTL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._probe = probe
        self._ttl = ttl
        self._clock = clock
        self._value: DaemonState | None = None
        self._at: float | None = None

    def read(self) -> DaemonState:
        """Return the memo when fresh; otherwise issue one bounded probe and
        store the answer. MAY block for up to the probe's own timeout."""
        now = self._clock()
        if self._value is not None and self._at is not None and (now - self._at) < self._ttl:
            return self._value
        value = self._probe()
        self._value = value
        self._at = now
        return value

    def peek(self) -> DaemonState | None:
        """The last stored answer whatever its age, or None if never read.
        NEVER probes, never blocks, never spawns."""
        return self._value

    def invalidate(self) -> None:
        """Mark the stored answer STALE without discarding it: the next
        read() re-probes, while peek() can still report the last known
        answer instead of falling back to None (D-01e)."""
        self._at = None


def bootout(
    unit_dir: Path,
    *,
    run: Runner = run_captured,
    read_output: OutputRunner = query_systemctl,
) -> None:
    """Unregister the timer, distinguishing "already gone" from a real
    failure -- the systemd equivalent of installer/daemon.py::bootout.

    ATTEMPTS the user-scope disable-now call unconditionally, whether or not
    the timer unit file is on disk -- installer/daemon.py:262-279 issues
    `launchctl bootout` unconditionally for the same reason: a deleted or
    hand-corrupted unit file can coexist with a still-loaded unit, and a
    presence gate would skip the one call that fixes it.

    On CommandError it classifies: unit files present -> re-raise (this
    project wrote those units; a failure to unregister them is real); unit
    files absent -> re-probe systemd through probe_timer_state and re-raise
    only when the timer is still ACTIVE, returning normally when it is
    INACTIVE or UNAVAILABLE. Systemd has no single ESRCH-equivalent exit
    code for `disable` (a missing unit exits 1, the same code a permission
    or manager failure uses), so the classification is made on systemd's own
    post-failure answer rather than on a code table or on stderr text, which
    would be locale-dependent. Invariant: a caller can never proceed past a
    real bootout failure and treat the daemon as removed while it may still
    be loaded (review HIGH 15.7-01; T-15.7-39).
    """
    try:
        run(["systemctl", "--user", "disable", "--now", TIMER_NAME])
    except CommandError:
        if units_present(unit_dir):
            raise
        if probe_timer_state(read_output=read_output) is DaemonState.ACTIVE:
            raise


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
