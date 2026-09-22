from collections.abc import Callable
from pathlib import Path

import pytest

from installer.diskusage import (
    DISK_FREE_WARN_PERCENT,
    TMP_USED_WARN_PERCENT,
    DiskPressure,
    probe_disk_pressure,
)
from installer.enums import DaemonState

ROOT = Path("/")
TMP = Path("/tmp")


def _usage(
    root_free_percent: float, tmp_used_percent: float
) -> Callable[[Path], tuple[int, int, int]]:
    """A recording-free fake `usage` callable: total is always 1000, and the
    two paths are keyed by literal `ROOT`/`TMP` so a test only has to state
    percentages, not raw byte triples."""

    def fake(path: Path) -> tuple[int, int, int]:
        total = 1000
        if path == ROOT:
            free = int(total * root_free_percent / 100)
            return (total, total - free, free)
        if path == TMP:
            used = int(total * tmp_used_percent / 100)
            return (total, used, total - used)
        raise AssertionError(f"unexpected path probed: {path}")

    return fake


def test_disk_free_warn_percent_is_15() -> None:
    assert DISK_FREE_WARN_PERCENT == 15


def test_tmp_used_warn_percent_is_70() -> None:
    assert TMP_USED_WARN_PERCENT == 70


def test_low_disk_false_when_plenty_free() -> None:
    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=_usage(90, 0))
    assert pressure.low_disk is False


def test_low_disk_false_at_exact_threshold() -> None:
    # "below 15%", not "at or below" -- exactly 15% free must not warn.
    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=_usage(15, 0))
    assert pressure.low_disk is False


def test_low_disk_true_just_under_threshold() -> None:
    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=_usage(14.9, 0))
    assert pressure.low_disk is True


def test_high_tmp_measured_but_not_thresholded_when_tmp_threshold_is_false() -> None:
    # D-03d: the macOS case. The number is still measured and available for
    # display; only the threshold rule is gated off.
    pressure = probe_disk_pressure(DaemonState.INACTIVE, False, ROOT, TMP, usage=_usage(90, 95))
    assert pressure.high_tmp is False
    assert pressure.tmp_used_percent == 95.0


def test_high_tmp_false_at_exact_threshold_with_tmp_threshold_true() -> None:
    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=_usage(90, 70))
    assert pressure.high_tmp is False


def test_high_tmp_true_just_over_threshold_with_tmp_threshold_true() -> None:
    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=_usage(90, 70.1))
    assert pressure.high_tmp is True


def test_temp_mount_is_sampled_on_both_settings_of_tmp_threshold() -> None:
    # A future "optimisation" that skips the read when tmp_threshold is False
    # must fail here, not silently blank the macOS Policies row.
    for tmp_threshold in (True, False):
        sampled: list[Path] = []
        recording = _recording_usage(sampled)
        probe_disk_pressure(DaemonState.INACTIVE, tmp_threshold, ROOT, TMP, usage=recording)
        assert TMP in sampled


def _recording_usage(sampled: list[Path]) -> Callable[[Path], tuple[int, int, int]]:
    def recording(path: Path) -> tuple[int, int, int]:
        sampled.append(path)
        return (1000, 500, 500)

    return recording


def test_unreadable_root_mount_yields_none_percent_and_false_low_disk() -> None:
    def raising(path: Path) -> tuple[int, int, int]:
        if path == ROOT:
            raise OSError("permission denied")
        return (1000, 500, 500)

    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=raising)
    assert pressure.root_free_percent is None
    assert pressure.low_disk is False


def test_unreadable_tmp_mount_yields_none_percent_and_false_high_tmp_independently() -> None:
    def raising(path: Path) -> tuple[int, int, int]:
        if path == TMP:
            raise OSError("permission denied")
        return (1000, 100, 900)

    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=raising)
    assert pressure.tmp_used_percent is None
    assert pressure.high_tmp is False
    # The root read is unaffected by the tmp mount's own failure.
    assert pressure.root_free_percent == 90.0


def test_at_risk_true_only_when_daemon_is_inactive_under_pressure() -> None:
    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=_usage(5, 0))
    assert pressure.under_pressure is True
    assert pressure.at_risk is True


def test_at_risk_false_when_daemon_active_under_the_same_pressure() -> None:
    pressure = probe_disk_pressure(DaemonState.ACTIVE, True, ROOT, TMP, usage=_usage(5, 0))
    assert pressure.under_pressure is True
    assert pressure.at_risk is False


def test_at_risk_false_when_daemon_unavailable_under_the_same_pressure() -> None:
    pressure = probe_disk_pressure(DaemonState.UNAVAILABLE, True, ROOT, TMP, usage=_usage(5, 0))
    assert pressure.under_pressure is True
    assert pressure.at_risk is False


def test_zero_total_filesystem_yields_none_rather_than_a_division_error() -> None:
    def degenerate(path: Path) -> tuple[int, int, int]:
        return (0, 0, 0)

    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=degenerate)
    assert pressure.root_free_percent is None
    assert pressure.tmp_used_percent is None
    assert pressure.low_disk is False
    assert pressure.high_tmp is False


@pytest.mark.parametrize(
    "exc", [OSError("boom"), PermissionError("nope"), ValueError("bad"), TypeError("bad type")]
)
def test_probe_is_total_over_mount_read_failure(exc: Exception) -> None:
    def raising(path: Path) -> tuple[int, int, int]:
        raise exc

    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=raising)
    assert pressure.root_free_percent is None
    assert pressure.tmp_used_percent is None


def test_probe_is_total_over_a_malformed_non_numeric_triple() -> None:
    def malformed(path: Path) -> tuple[int, int, int]:
        return ("not", "a", "number")  # type: ignore[return-value]

    pressure = probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=malformed)
    assert pressure.root_free_percent is None
    assert pressure.tmp_used_percent is None


def test_probe_propagates_a_programming_error_rather_than_swallowing_it() -> None:
    def broken(path: Path) -> tuple[int, int, int]:
        raise RuntimeError("a genuine bug inside this module's caller")

    with pytest.raises(RuntimeError, match="genuine bug"):
        probe_disk_pressure(DaemonState.INACTIVE, True, ROOT, TMP, usage=broken)


def test_disk_pressure_is_frozen() -> None:
    pressure = DiskPressure(
        root_free_percent=50.0, tmp_used_percent=10.0, daemon=DaemonState.ACTIVE, tmp_threshold=True
    )
    with pytest.raises(AttributeError):
        pressure.root_free_percent = 0.0  # type: ignore[misc]
