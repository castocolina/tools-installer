from pathlib import Path

import pytest

from installer.atomic import atomic_write_bytes, atomic_write_text


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
