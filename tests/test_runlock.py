"""The run lock: one holder at a time across processes, with a holder line the view can read."""

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from installer import runlock
from installer.runlock import hold, holder, run_lock_path, try_acquire


def test_run_lock_path_follows_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert run_lock_path() == tmp_path / ".local/state/tools-installer/run.lock"


def test_second_open_is_busy(tmp_path: Path) -> None:
    path = tmp_path / "state" / "run.lock"
    first = try_acquire(path, "update-claude")
    assert first is not None
    content = path.read_text().split()
    assert content[:2] == ["update-claude", str(os.getpid())]
    assert len(content) == 3

    assert try_acquire(path, runlock.INSTALLER_JOB) is None
    # A busy attempt never clears the holder's line.
    assert path.read_text().split()[:2] == ["update-claude", str(os.getpid())]

    first.release()
    first.release()  # releasing twice is harmless
    assert path.read_text() == ""
    second = try_acquire(path, runlock.INSTALLER_JOB)
    assert second is not None
    second.release()


def test_holder_reads_a_live_pid(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    assert holder(path) is None  # missing

    lock = try_acquire(path, "update-claude")
    assert lock is not None
    found = holder(path)
    assert found is not None
    assert (found.job, found.pid) == ("update-claude", os.getpid())
    assert found.since == path.read_text().split()[2]
    lock.release()
    assert holder(path) is None  # empty after release


def _dead_pid(tmp_path: Path) -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"], cwd=tmp_path)
    child.wait()
    return child.pid


@pytest.mark.parametrize(
    "content",
    (
        "",
        "garbage",
        "update-claude",
        "update-claude abc 2026-11-13T12:00:00+01:00",
        "a 0 x",
        "a -3 x",
    ),
)
def test_holder_ignores_bad_content(tmp_path: Path, content: str) -> None:
    path = tmp_path / "run.lock"
    path.write_text(content)
    assert holder(path) is None


def test_holder_ignores_a_dead_pid(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    for pid in (_dead_pid(tmp_path), 2**22 + 1, 2**70):
        path.write_text(f"update-claude {pid} 2026-11-13T12:00:00+01:00\n")
        assert holder(path) is None


def test_holder_counts_a_pid_it_may_not_signal_as_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "run.lock"
    path.write_text("update-claude 1 2026-11-13T12:00:00+01:00\n")

    def refuse(_pid: int, _signal: int) -> None:
        raise PermissionError

    monkeypatch.setattr(os, "kill", refuse)
    found = holder(path)
    assert found is not None
    assert found.pid == 1


def test_holder_ignores_an_oversized_or_symlinked_file(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    path.write_text("update-claude 1 x\n" + "x" * 5000)
    assert holder(path) is None
    real = tmp_path / "real"
    real.write_text(f"update-claude {os.getpid()} 2026-11-13T12:00:00+01:00\n")
    link = tmp_path / "link.lock"
    link.symlink_to(real)
    assert holder(link) is None


def test_try_acquire_refuses_a_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.write_text("")
    link = tmp_path / "run.lock"
    link.symlink_to(real)
    with pytest.raises(OSError):
        try_acquire(link, "update-claude")


def test_hold_serializes_short_sections(tmp_path: Path) -> None:
    path = tmp_path / "state.lock"
    order: list[str] = []
    inside = threading.Event()
    release = threading.Event()

    def first() -> None:
        with hold(path):
            order.append("first-in")
            inside.set()
            release.wait(5)
            order.append("first-out")

    def second() -> None:
        with hold(path):
            order.append("second-in")

    worker_one = threading.Thread(target=first)
    worker_two = threading.Thread(target=second)
    worker_one.start()
    assert inside.wait(5)
    worker_two.start()
    worker_two.join(0.2)
    assert worker_two.is_alive()  # blocked behind the first holder
    release.set()
    worker_one.join(5)
    worker_two.join(5)
    assert order == ["first-in", "first-out", "second-in"]
