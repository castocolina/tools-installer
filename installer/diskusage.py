"""Pure disk-pressure probe (D-03): free space on the user's own filesystem
and used /tmp space, both IO-injected so nothing here touches a real
filesystem except through the injected callable this module's tests drive.

No IO of its own: the only external call is `usage`, defaulted to
`shutil.disk_usage` (stdlib -- (total, used, free) in bytes for any mounted
filesystem including a tmpfs, no `df` parsing, no subprocess spawn). This
mirrors installer/doctor.py's own pure-audit shape (an injected `exists`
callable, a frozen report dataclass) so this module stays covered by pyright
strict mode and offline, deterministic tests the same way.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from installer.enums import DaemonState

# D-03 deliberately chose these over the source todo's original 30% / 50%:
# more conservative thresholds mean fewer false positives on a machine that
# simply has plenty of free space and where the daemon is not running yet --
# reporting nothing there is correct, not a gap.
DISK_FREE_WARN_PERCENT = 15
TMP_USED_WARN_PERCENT = 70

# usage(path) -> (total, used, free) in bytes, matching shutil.disk_usage's
# own return shape (a NamedTuple that unpacks the same way).
UsageProbe = Callable[[Path], tuple[int, int, int]]


def _percent(path: Path, usage: UsageProbe, *, of_free: bool) -> float | None:
    """One guarded mount read: None on any conversion failure, never an exception.

    Catches OSError (including PermissionError), ValueError and TypeError from
    the injected `usage` callable -- a malformed or too-short/too-long result
    unpacks as ValueError, a non-numeric result compares as TypeError -- and
    treats a zero-or-negative total (a degenerate mount) as unreadable too, so
    a caller never divides by zero. Any other exception (a genuine programming
    error) is not this function's to catch; it is not listed here, so it
    propagates uncaught.
    """
    try:
        total, _used, free = usage(path)
        if total <= 0:
            return None
        measured = free if of_free else total - free
        return (measured / total) * 100
    except (OSError, ValueError, TypeError):
        return None


@dataclass(frozen=True)
class DiskPressure:
    """One measurement pass: the free percentage of the filesystem holding the
    user's home directory, the temp mount's used percentage (both None when
    that mount could not be read), the daemon's own runtime state, and whether
    the /tmp usage rule applies on this platform (D-03d: Linux only -- the temp
    mount itself is always measured, this flag gates only the threshold)."""

    home_free_percent: float | None
    tmp_used_percent: float | None
    daemon: DaemonState
    tmp_threshold: bool

    @property
    def low_disk(self) -> bool:
        """True when the home filesystem's free space is measured and strictly
        below the threshold -- "below 15%", not "at or below"."""
        if self.home_free_percent is None:
            return False
        return self.home_free_percent < DISK_FREE_WARN_PERCENT

    @property
    def high_tmp(self) -> bool:
        """False whenever tmp_threshold is False, regardless of the measured
        number (D-03d) -- the flag gates the rule, never the measurement."""
        if not self.tmp_threshold:
            return False
        return self.tmp_used_percent is not None and self.tmp_used_percent > TMP_USED_WARN_PERCENT

    @property
    def under_pressure(self) -> bool:
        return self.low_disk or self.high_tmp

    @property
    def at_risk(self) -> bool:
        """D-03c: reserved for the one daemon state that has a control the
        user can flip. ACTIVE and UNAVAILABLE are never at_risk, even under
        the exact same measured pressure."""
        return self.under_pressure and self.daemon is DaemonState.INACTIVE


def probe_disk_pressure(
    daemon: DaemonState,
    tmp_threshold: bool,
    home_path: Path,
    tmp_path: Path,
    usage: UsageProbe = shutil.disk_usage,
) -> DiskPressure:
    """Measure `home_path`'s free percentage and `tmp_path`'s used percentage.

    `home_path` is the path whose CONTAINING FILESYSTEM is measured -- the
    caller passes the user's home directory, not a mount point, and the
    kernel resolves it to the filesystem that actually holds the user's data.
    Which path that is stays the caller's decision (this module has no
    platform knowledge); the name records that no caller may pass `/`, which
    on an ostree/composefs host is a read-only overlay permanently at 0 bytes
    free and on macOS is a read-only signed system volume.

    `probe_disk_pressure` is TOTAL over filesystem and probe-conversion
    failure. It catches `OSError` (including `PermissionError`), `ValueError`
    and `TypeError` raised by the injected usage callable, and converts a
    zero-total or non-numeric result into a `None` percentage. It raises for
    no mount-read outcome a real filesystem can produce. Any other exception
    -- a programming error inside this module -- propagates uncaught.

    The temp mount is read unconditionally, on both settings of
    `tmp_threshold` (D-03d): the flag gates only `DiskPressure.high_tmp`, so a
    macOS caller (`tmp_threshold=False`) still gets a real measured
    `tmp_used_percent` to display, never a substituted root-filesystem number.
    """
    home_free_percent = _percent(home_path, usage, of_free=True)
    tmp_used_percent = _percent(tmp_path, usage, of_free=False)
    return DiskPressure(
        home_free_percent=home_free_percent,
        tmp_used_percent=tmp_used_percent,
        daemon=daemon,
        tmp_threshold=tmp_threshold,
    )
