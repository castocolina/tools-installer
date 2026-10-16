import contextlib
import os
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from installer.atomic import (
    NEW_SUFFIX,
    OLD_SUFFIX,
    atomic_write_bytes,
    atomic_write_text,
    read_capped,
    recover_update_remnants,
    staged_sibling,
)


def test_atomic_write_bytes_replaces_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")
    atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"new"
    assert list(tmp_path.glob("*.tools-installer.tmp")) == []


def test_atomic_write_bytes_creates_a_file_that_does_not_exist_yet(tmp_path: Path) -> None:
    target = tmp_path / "fresh.bin"
    atomic_write_bytes(target, b"hello")
    assert target.read_bytes() == b"hello"
    assert target.exists()


def test_atomic_write_bytes_copies_mode_from_an_existing_target_when_mode_is_none(
    tmp_path: Path,
) -> None:
    target = tmp_path / "owned.txt"
    target.write_bytes(b"old")
    target.chmod(0o600)
    atomic_write_bytes(target, b"new")
    assert target.stat().st_mode & 0o777 == 0o600


def test_atomic_write_bytes_forces_explicit_mode_on_a_brand_new_file(tmp_path: Path) -> None:
    target = tmp_path / "plist"
    atomic_write_bytes(target, b"payload", mode=0o644)
    assert target.stat().st_mode & 0o777 == 0o644


def test_atomic_write_bytes_rewrites_a_symlink_target_and_leaves_the_symlink(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real.txt"
    real.write_text("old")
    link = tmp_path / "link.txt"
    link.symlink_to(real)
    atomic_write_text(link, "new")
    assert link.is_symlink()
    assert real.read_text() == "new"
    assert link.read_text() == "new"


def test_atomic_write_bytes_oserror_leaves_the_original_and_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "keep.txt"
    target.write_text("original")

    def boom(src: str | Path, dst: str | Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError, match="disk full"):
        atomic_write_text(target, "partial")
    assert target.read_text() == "original"
    assert list(tmp_path.glob("*.tools-installer.tmp")) == []


def test_rc_reader_never_sees_a_partial_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrency edge: the target holds the old bytes until os.replace and
    the new bytes after it, so a concurrent reader can never observe a
    partially written rc. Proven once here on atomic_write_text, which every
    rc and shim writer routes through."""
    target = tmp_path / ".zshrc"
    target.write_text("old-bytes")
    observed_before: list[str] = []

    real_replace = os.replace

    def spy_replace(src: str | Path, dst: str | Path) -> None:
        observed_before.append(Path(dst).read_text())
        real_replace(src, dst)

    monkeypatch.setattr("os.replace", spy_replace)
    atomic_write_text(target, "new-bytes")

    assert observed_before == ["old-bytes"]
    assert target.read_text() == "new-bytes"


def test_recover_update_remnants_never_deletes_old_when_live_also_exists(
    tmp_path: Path,
) -> None:
    """C4 regression (12-REVIEW.md, codex-sol-high): simulate a crash after
    `.new` was swapped into `live` but before validation/relinking/cleanup
    completed. Both `live` (unvalidated, possibly-broken new content) and
    `.old` (the last known-good tree) exist. Recovery must restore `.old`
    over `live`, never delete `.old` on the assumption that `live` existing
    proves it was validated.
    """
    live = tmp_path / "rg"
    live.mkdir()
    (live / "rg").write_text("unvalidated-new-content")
    old = staged_sibling(live, OLD_SUFFIX)
    old.mkdir()
    (old / "rg").write_text("known-good-content")

    recover_update_remnants(live)

    assert not old.exists()
    assert live.exists()
    assert (live / "rg").read_text() == "known-good-content"


def test_recover_update_remnants_restores_old_when_live_is_missing(tmp_path: Path) -> None:
    live = tmp_path / "rg"
    old = staged_sibling(live, OLD_SUFFIX)
    old.mkdir()
    (old / "rg").write_text("known-good-content")

    recover_update_remnants(live)

    assert not old.exists()
    assert (live / "rg").read_text() == "known-good-content"


def test_recover_update_remnants_discards_stale_new(tmp_path: Path) -> None:
    live = tmp_path / "rg"
    live.mkdir()
    new = staged_sibling(live, NEW_SUFFIX)
    new.mkdir()
    (new / "stale").write_text("stale")

    recover_update_remnants(live)

    assert not new.exists()
    assert live.exists()


def test_two_writes_to_the_same_target_produce_different_temp_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "cache.json"
    captured: list[Path] = []
    real_write = Path.write_bytes

    def capturing(self: Path, data: bytes) -> int | None:
        captured.append(self)
        return real_write(self, data)

    monkeypatch.setattr(Path, "write_bytes", capturing)
    atomic_write_text(target, "one")
    atomic_write_text(target, "two")
    assert len(captured) == 2
    assert captured[0] != captured[1]
    assert all(path.name.endswith(".tools-installer.tmp") for path in captured)
    assert target.read_text() == "two"


def _bounded(call: Callable[[], bytes | None]) -> tuple[threading.Thread, list[bytes | None]]:
    """Run `call` on a daemon thread and refuse to wait more than five seconds.

    A FIFO with no writer used to block `open` forever. The caller releases any
    reader the old code left waiting, then joins again so the thread is gone.
    """
    box: list[bytes | None] = []

    def run() -> None:
        box.append(call())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=5)
    return thread, box


def test_read_capped_reads_a_regular_file(tmp_path: Path) -> None:
    small = tmp_path / "small.bin"
    small.write_bytes(b"abc")
    exact = tmp_path / "exact.bin"
    exact.write_bytes(b"x" * 8)

    assert read_capped(small, 8, follow_symlinks=False) == b"abc"
    assert read_capped(exact, 8, follow_symlinks=True) == b"x" * 8


def test_read_capped_refuses_an_oversize_file(tmp_path: Path) -> None:
    path = tmp_path / "big.bin"
    path.write_bytes(b"x" * 9)

    assert read_capped(path, 8, follow_symlinks=False) is None


def test_read_capped_never_blocks_on_a_fifo(tmp_path: Path) -> None:
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    thread = threading.Thread()
    try:
        for follow in (False, True):
            thread, box = _bounded(
                lambda follow=follow: read_capped(fifo, 8, follow_symlinks=follow)
            )
            assert not thread.is_alive()
            assert box == [None]
    finally:
        with contextlib.suppress(OSError):
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        thread.join(timeout=5)


def test_read_capped_refuses_a_symlink_unless_following(tmp_path: Path) -> None:
    target = tmp_path / "real.bin"
    target.write_bytes(b"payload")
    link = tmp_path / "link.bin"
    link.symlink_to(target)
    directory = tmp_path / "dir"
    directory.mkdir()

    with pytest.raises(OSError):
        read_capped(link, 64, follow_symlinks=False)
    assert read_capped(link, 64, follow_symlinks=True) == b"payload"
    assert read_capped(directory, 64, follow_symlinks=False) is None
