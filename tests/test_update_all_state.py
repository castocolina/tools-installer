"""The update record rejects hostile files and never follows a planted link."""

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from installer import schedules
from installer import update_all_state as store

DAY = date(2026, 11, 22)


def body(entry: object, key: str = "brew") -> bytes:
    return json.dumps({"version": 1, "updated": {key: entry}}).encode()


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b"[]",
        b'"text"',
        b'{"version":2,"updated":{}}',
        b'{"version":true,"updated":{}}',
        b'{"version":"1","updated":{}}',
        b'{"version":1,"updated":[]}',
        *[
            body({"date": d, "by": "update-all"})
            for d in ("2026-13-45", "20261122", "2026-1-5", "2026-11-22T00:00:00")
        ],
        body({"date": "2026-11-22", "by": "evil"}),
        body({"date": "2026-11-22"}),
        body({"date": "2026-11-22", "by": "update-all", "extra": 1}),
        body([]),
        body({"date": "2026-11-22", "by": "update-all"}, "Bad ID"),
        body({"date": "2026-11-22", "by": "update-all"}, "bad/id"),
        b"[" * 10000,
        b'{"version":1,"updated":{"ok":{"date":"2026-11-22","by":"update-all"},"bad":{}}}',
    ],
)
def test_the_reader_is_strict(tmp_path: Path, raw: bytes) -> None:
    path = tmp_path / "state"
    assert store.read_updated(path) == ({}, True)
    path.write_bytes(body({"date": "2026-11-22", "by": "update-all"}))
    assert store.read_updated(path) == ({"brew": store.UpdatedEntry(DAY, "update-all")}, True)
    path.write_bytes(raw)
    assert store.read_updated(path) == ({}, False)


def test_reader_handles_overflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "state"
    path.write_bytes(b"{}")

    def overflow(*_args: object, **_kwargs: object) -> object:
        raise OverflowError()

    monkeypatch.setattr(store.json, "loads", overflow)
    assert store.read_updated(path) == ({}, False)


@pytest.mark.parametrize("field", ["date", "by"])
@pytest.mark.parametrize("value", [[], {}, 4, True, None])
def test_by_and_date_are_type_checked_before_use(tmp_path: Path, field: str, value: object) -> None:
    entry: dict[str, object] = {"date": "2026-11-22", "by": "update-all"}
    entry[field] = value
    path = tmp_path / "state"
    path.write_bytes(body(entry))
    assert store.read_updated(path) == ({}, False)


def test_the_reader_leaves_odd_files_alone(tmp_path: Path) -> None:
    path = tmp_path / "state"
    path.mkdir()
    (path / "keep").write_bytes(b"keep")
    assert store.read_updated(path) == ({}, False)
    assert (path / "keep").read_bytes() == b"keep"
    (path / "keep").unlink()
    path.rmdir()
    os.mkfifo(path)
    assert store.read_updated(path) == ({}, False)
    assert path.is_fifo()
    path.unlink()
    data = b" " * (store.STORE_CAP + 1)
    path.write_bytes(data)
    assert store.read_updated(path) == ({}, False)
    assert path.read_bytes() == data
    path.unlink()
    target = tmp_path / "target"
    target.write_bytes(body({"date": "2026-11-22", "by": "update-all"}))
    path.symlink_to(target)
    assert store.read_updated(path) == ({}, False)
    assert path.is_symlink() and target.read_bytes() == body(
        {"date": "2026-11-22", "by": "update-all"}
    )


def test_updated_on_keeps_only_today() -> None:
    entries = {
        "a": store.UpdatedEntry(DAY, "update-all"),
        "b": store.UpdatedEntry(DAY - timedelta(days=1), "update-claude"),
        "c": store.UpdatedEntry(DAY + timedelta(days=1), "update-all"),
    }
    assert store.updated_on(entries, DAY) == {"a": "update-all"}


def test_record_updated_writes_the_closed_body(tmp_path: Path) -> None:
    path = tmp_path / "parent" / "state"
    store.record_updated(path, "brew", today=DAY, by="update-all")
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.read_bytes().endswith(b"\n")
    assert json.loads(path.read_bytes()) == {
        "version": 1,
        "updated": {"brew": {"date": "2026-11-22", "by": "update-all"}},
    }
    store.record_updated(path, "uv", today=DAY, by="update-claude")
    store.record_updated(path, "brew", today=DAY, by="update-opencode")
    assert store.read_updated(path) == (
        {
            "brew": store.UpdatedEntry(DAY, "update-opencode"),
            "uv": store.UpdatedEntry(DAY, "update-claude"),
        },
        True,
    )
    store.record_updated(path, "pi", today=DAY + timedelta(days=1), by="update-all")
    assert store.read_updated(path) == (
        {"pi": store.UpdatedEntry(DAY + timedelta(days=1), "update-all")},
        True,
    )
    prior = path.read_bytes()
    for tool, by in [("bad/id", "update-all"), ("brew", "evil")]:
        with pytest.raises(ValueError):
            store.record_updated(path, tool, today=DAY, by=by)
    assert path.read_bytes() == prior


def test_record_updated_heals_a_corrupt_file_and_is_link_safe(tmp_path: Path) -> None:
    path = tmp_path / "state"
    path.write_bytes(b"bad")
    store.record_updated(path, "brew", today=DAY, by="update-all")
    assert store.read_updated(path)[1]
    path.unlink()
    target = tmp_path / "target"
    target.write_bytes(b"keep")
    path.symlink_to(target)
    store.record_updated(path, "brew", today=DAY, by="update-all")
    assert not path.is_symlink() and target.read_bytes() == b"keep"
    path.unlink()
    path.mkdir()
    (path / "keep").write_bytes(b"keep")
    with pytest.raises(OSError):
        store.record_updated(path, "brew", today=DAY, by="update-all")
    assert (path / "keep").read_bytes() == b"keep"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state", "target"]


def test_the_writer_never_saves_what_its_reader_would_reject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "state"
    store.record_updated(path, "brew", today=DAY, by="update-all")
    prior = path.read_bytes()
    monkeypatch.setitem(vars(store), "STORE_CAP", len(prior) + 1)
    with pytest.raises(OSError):
        store.record_updated(path, "uv", today=DAY, by="update-all")
    assert path.read_bytes() == prior
    assert store.read_updated(path) == ({"brew": store.UpdatedEntry(DAY, "update-all")}, True)
    monkeypatch.setitem(vars(store), "STORE_CAP", 1024)
    store.record_updated(path, "uv", today=DAY, by="update-all")
    assert store.read_updated(path)[1]


def test_the_by_set_is_the_update_rows() -> None:
    assert {*schedules.UPDATE_SCHEDULE_IDS, "update-all"} == store.UPDATE_BY


def test_the_run_log_is_truncated_and_appended_link_safely(tmp_path: Path) -> None:
    path = tmp_path / "parent" / "log"
    store.start_run_log(path)
    assert path.read_bytes() == b""
    assert path.stat().st_mode & 0o777 == 0o600
    for line in ("one", "two", "three"):
        store.append_run_log(path, line)
    assert path.read_text() == "one\ntwo\nthree\n"
    store.start_run_log(path)
    assert path.read_bytes() == b""
    target = tmp_path / "target"
    target.write_bytes(b"keep")
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(OSError):
        store.append_run_log(path, "bad")
    assert target.read_bytes() == b"keep"
    store.start_run_log(path)
    assert not path.is_symlink() and path.read_bytes() == b""
    assert target.read_bytes() == b"keep"
    path.unlink()
    path.mkdir()
    (path / "keep").write_bytes(b"keep")
    with pytest.raises(OSError):
        store.append_run_log(path, "bad")
    with pytest.raises(OSError):
        store.start_run_log(path)
    assert (path / "keep").read_bytes() == b"keep"


def test_the_append_never_blocks_on_a_fifo_and_refuses_it(tmp_path: Path) -> None:
    path = tmp_path / "log"
    os.mkfifo(path)
    with pytest.raises(OSError):
        store.append_run_log(path, "bad")
    reader = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        with pytest.raises(OSError):
            store.append_run_log(path, "bad")
        assert os.read(reader, 100) == b""
    finally:
        os.close(reader)
    store.start_run_log(path)
    assert path.is_file() and not path.is_fifo() and path.read_bytes() == b""


def test_the_append_completes_short_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "log"
    original_write = os.write

    def short_write(fd: int, data: bytes) -> int:
        return original_write(fd, data[:5])

    monkeypatch.setattr(os, "write", short_write)
    store.append_run_log(path, "a long line with unicode: café")
    assert path.read_text() == "a long line with unicode: café\n"

    def no_progress(_fd: int, _data: bytes) -> int:
        return 0

    monkeypatch.setattr(os, "write", no_progress)
    with pytest.raises(OSError):
        store.append_run_log(path, "no progress")


def test_log_line_format_and_bounds() -> None:
    now = datetime(2026, 11, 22, 3, 0, 4, tzinfo=UTC)
    assert store.log_line(now, "brew", "ok: up to date") == (
        "2026-11-22T03:00:04+00:00 brew ok: up to date"
    )
    assert store.log_line(now, "brew", "a\x1b[31mred\x1b[0m\t b\x01\x85\n c") == (
        "2026-11-22T03:00:04+00:00 brew ared b c"
    )
    assert store.log_line(now, "brew", "x" * 500) == ("2026-11-22T03:00:04+00:00 brew " + "x" * 300)
    with pytest.raises(ValueError):
        store.log_line(now, "bad/id", "text")
