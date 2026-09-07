"""Background maintenance daemon mechanism: LaunchAgent plist generation/parsing via
plistlib, launchctl bootstrap/bootout invocation through an injectable run seam, the
wrapper-executable install/remove mechanism, and the "has any decision ever been
recorded for this policy" ownership marker.

Parallel to installer/omz.py's mechanism-tier role for the omz-plugins policy: this
module is pure-enough plumbing that installer/policy.py's daemon_policy factory (a
later plan) composes into an actual Policy. Nothing here reads argv, prompts, or
renders UI.
"""

import contextlib
import os
import plistlib
import shutil
from pathlib import Path
from typing import cast

from installer.run import CommandError, Runner, run_captured

LABEL = "com.tools-installer.prune-tmpdir"
DEFAULT_HOUR = 3
DEFAULT_MINUTE = 0
DEFAULT_DAYS = 3
DEFAULT_CAP_BYTES = 256 * 1024

# Live-verified this session (see 11-01-PLAN.md Task 1 <read_first>): a real
# `launchctl bootout` against a nonexistent label on this machine exits 3, and
# `launchctl error 3` decodes it as "3: No such process" (Darwin's ESRCH).
_ALREADY_UNLOADED_EXIT_CODE = 3


class DaemonScheduleError(OSError):
    """A plist/schedule input is invalid: an empty/relative path, TMPDIR, or HOME,
    an unresolved `uv`, or an out-of-range hour/minute/days.

    Subclasses OSError so installer/ui_common.py::run_live -- which already catches
    OSError by design -- surfaces a rejected apply/reschedule on the Policies status
    line with zero new except clauses anywhere, mirroring
    installer/omz.py::OmzPluginsError's exact precedent.
    """


def _atomic_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
    """Replace path's content atomically, creating it when it does not exist yet.

    Mirrors installer/omz.py::_atomic_write's crash-safety shape (sibling temp file
    in the same directory, then os.replace) but adds an explicit `mode` parameter
    (11-REVIEWS.md cycle 3 finding #4): the plist this module writes and the
    ~/.myshellrc "decided" marker it also writes have genuinely different
    permission requirements, so one hardcoded policy cannot serve both callers.
    When `mode` is given, the temp file is chmod'd to exactly that value before the
    replace -- an explicit, umask-independent permission (write_plist's own forced
    0o644 for a LaunchAgent config nobody else should be able to edit). When `mode`
    is None (the default), this mirrors installer/omz.py::_atomic_write exactly:
    shutil.copymode(target, tmp) when target already exists, no explicit chmod
    otherwise (record_decided's mode-PRESERVING write against ~/.myshellrc, the
    same file omz.py's own _atomic_write already protects).

    When path is itself a symlink, os.replace(tmp, path) would rename OVER the
    symlink rather than through it; resolving to the real target first means the
    symlink itself is never touched.
    """
    target = path.resolve() if path.is_symlink() else path
    tmp = target.with_name(f"{target.name}.tools-installer.tmp")
    try:
        tmp.write_bytes(data)
        if mode is not None:
            tmp.chmod(mode)
        elif target.exists():
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except OSError:
        # The original is still intact; drop the partial temp rather than leaving
        # a half-written file beside it.
        tmp.unlink(missing_ok=True)
        raise


def render_plist(
    *,
    uv_path: Path,
    wrapper_path: Path,
    script_path: Path,
    log_path: Path,
    hour: int,
    minute: int,
    days: int,
    tmpdir: str,
    home: str,
    path_value: str,
    label: str = LABEL,
) -> dict[str, object]:
    """The LaunchAgent plist dict for the daily prune run, fully validated first.

    ProgramArguments names the apply-time-resolved `uv` executable first, then the
    installed wrapper's path as `uv run --script`'s target, never
    scripts/prune-user-tmpdir.sh directly and never a bare python3 shebang --
    mirroring installer/tweaks.py:64's `_COUNTDOWN_BODY` invocation shape. This is
    live-verified this session: `uv run --no-project --script FILE --script /tmp/s
    ... -- --apply --days 3` forwards every trailing argument, including a literal
    `--` token, verbatim as sys.argv[1:] to FILE.

    TMPDIR and HOME are resolved into EnvironmentVariables, not baked into
    ProgramArguments as flags -- this reaches scripts/prune-user-tmpdir.sh's own
    `${TMPDIR:-}` read (line 24, hard error if empty) and its `$HOME` expansion
    under `set -u` (line 72) with zero wrapper-side plumbing, since subprocess.run
    inherits the wrapper's own process environment by default. A freshly
    bootstrapped LaunchAgent's default environment is only
    `{PATH => /usr/bin:/bin:/usr/sbin:/sbin}` (live-verified, 11-RESEARCH.md
    Pitfall 3) -- TMPDIR and HOME are equally absent otherwise.

    Every path/schedule argument is validated -- raising DaemonScheduleError the
    instant any is invalid -- BEFORE this function returns anything, so an empty
    TMPDIR/HOME (11-REVIEWS.md cycle 1 finding #5, extended to HOME by cycle 2
    finding #1), an unresolved `uv` (modeled identically: shutil.which("uv")
    returning None becomes an empty, non-absolute uv_path, the SAME validation
    rejects), or an out-of-range hour/minute/days can never reach a written plist
    or a launchctl bootstrap call.
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
    if not 0 <= hour <= 23:
        raise DaemonScheduleError(f"hour must be within 0-23: {hour!r}")
    if not 0 <= minute <= 59:
        raise DaemonScheduleError(f"minute must be within 0-59: {minute!r}")
    if days < 1:
        raise DaemonScheduleError(f"days must be >= 1: {days!r}")
    return {
        "Label": label,
        "ProgramArguments": [
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
            str(DEFAULT_CAP_BYTES),
            "--",
            "--apply",
            "--days",
            str(days),
        ],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
        "RunAtLoad": False,
        "EnvironmentVariables": {"PATH": path_value, "TMPDIR": tmpdir, "HOME": home},
    }


def write_plist(
    plist_path: Path,
    *,
    uv_path: Path,
    wrapper_path: Path,
    script_path: Path,
    log_path: Path,
    hour: int,
    minute: int,
    days: int,
    tmpdir: str,
    home: str,
    path_value: str,
    label: str = LABEL,
) -> None:
    """Validate and serialize the plist, writing it atomically at 0o644.

    render_plist runs FIRST; a DaemonScheduleError propagates with zero filesystem
    side effects (no partial/temp file left behind). Only once it returns
    successfully does this create plist_path's parent directories and write
    through the shared _atomic_write helper with an explicit, forced mode=0o644
    (RESEARCH's Tampering mitigation for group/world-writable LaunchAgent
    configs) -- independent of the invoking process's umask or any pre-existing
    mode on the target file.
    """
    plist_dict = render_plist(
        uv_path=uv_path,
        wrapper_path=wrapper_path,
        script_path=script_path,
        log_path=log_path,
        hour=hour,
        minute=minute,
        days=days,
        tmpdir=tmpdir,
        home=home,
        path_value=path_value,
        label=label,
    )
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(plist_path, plistlib.dumps(plist_dict), mode=0o644)


def read_schedule(plist_path: Path) -> tuple[int, int] | None:
    """The (hour, minute) StartCalendarInterval, or None -- total over any input.

    Returns None when the path does not exist, when plistlib.loads raises on
    genuinely invalid plist XML bytes (plistlib.InvalidFileException is a
    ValueError subclass, live-verified this session -- 11-REVIEWS.md cycle 2
    finding #3), or when StartCalendarInterval is missing/malformed. Never raises.
    """
    if not plist_path.exists():
        return None
    try:
        data: dict[str, object] = plistlib.loads(plist_path.read_bytes())
        interval = data["StartCalendarInterval"]
        if not isinstance(interval, dict):
            return None
        interval_values = cast("dict[object, object]", interval)
        hour = interval_values["Hour"]
        minute = interval_values["Minute"]
        if not isinstance(hour, int) or not isinstance(minute, int):
            return None
        return hour, minute
    except (KeyError, TypeError, ValueError):
        return None


def bootstrap(
    uid: int, plist_path: Path, *, label: str = LABEL, run: Runner = run_captured
) -> None:
    """Idempotently (re)register plist_path as the given label's LaunchAgent.

    Always attempts its own inline, unconditionally-best-effort bootout first
    (swallowing every CommandError, since this call is about to overwrite the
    label's registration regardless -- RESEARCH Pitfall 4's live-verified
    idempotent sequence), THEN unconditionally calls bootstrap. That second
    call's CommandError propagates uncaught: a real bootstrap failure is real.
    """
    with contextlib.suppress(CommandError):
        run(["launchctl", "bootout", f"gui/{uid}/{label}"])
    run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)])


def bootout(uid: int, *, label: str = LABEL, run: Runner = run_captured) -> None:
    """Unregister label's LaunchAgent, distinguishing "already not loaded" from
    a real failure.

    This is the STANDALONE function callers needing a definite outcome use (never
    bootstrap's own inline, unconditional pre-clear above). A CommandError whose
    returncode is _ALREADY_UNLOADED_EXIT_CODE (3, Darwin's ESRCH -- "No such
    process") is swallowed and this returns normally; any other CommandError
    propagates uncaught, so a caller can never proceed past a real bootout
    failure and treat the daemon as removed while it may still be loaded.
    """
    try:
        run(["launchctl", "bootout", f"gui/{uid}/{label}"])
    except CommandError as exc:
        if exc.returncode == _ALREADY_UNLOADED_EXIT_CODE:
            return
        raise


def ensure_log_path(log_path: Path) -> None:
    """Create log_path's parent directory and an empty file if absent.

    This is the AUTHORITATIVE log-path creation point, called at APPLY time
    (before write_plist/bootstrap) because launchd needs StandardOutPath's
    location to already resolve at registration time -- creating it lazily
    inside the wrapper, as originally planned, is too late (11-REVIEWS.md
    cycle 1 finding #2). Never truncates an existing log.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)
