"""Receipt round-trips and the suite-wide receipts sandbox (plan 19-01, Task 1)."""

import json
import os
from pathlib import Path

import pytest

from installer import receipts
from installer.model import Method
from installer.receipts import (
    Receipt,
    ReceiptArtifact,
    ReceiptMethod,
    method_key,
    receipt_path,
    write,
)

_REAL_HOME = Path(os.path.expanduser("~"))


def _sample(tmp_path: Path) -> Receipt:
    target_file = tmp_path / "yq"
    target_file.write_bytes(b"abc")
    link = tmp_path / "link"
    directory = tmp_path / "dir"
    directory.mkdir()
    return Receipt(
        tool="yq",
        at="2026-10-16T12:00:00+00:00",
        method=ReceiptMethod(kind="github_release", key="a" * 64),
        package=None,
        artifacts=(
            ReceiptArtifact(
                path=target_file.resolve(), type="file", sha256="b" * 64, size=3, mtime_ns=1
            ),
            ReceiptArtifact(path=link, type="link", target="/x/y"),
            ReceiptArtifact(path=directory, type="dir"),
        ),
        smoke="ok",
        hooks={},
    )


def test_receipt_round_trips(tmp_path: Path) -> None:
    receipt = _sample(tmp_path)
    write(receipt)
    loaded = receipts.read("yq")
    assert loaded == receipt
    on_disk = json.loads(receipt_path("yq").read_text(encoding="utf-8"))
    assert on_disk["v"] == 1
    for artifact in on_disk["artifacts"]:
        assert Path(artifact["path"]).is_absolute()


def test_receipts_dir_is_next_to_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert receipts.default_receipts_dir() == (
        tmp_path / ".local" / "state" / "tools-installer" / "receipts"
    )
    assert receipt_path("yq").name == "yq.json"
    monkeypatch.setattr(receipts, "receipts_dir", receipts.default_receipts_dir)
    assert receipt_path("yq").parent == receipts.receipts_dir()


def test_suite_sandbox_redirects_receipts() -> None:
    assert not str(receipts.receipts_dir()).startswith(str(_REAL_HOME))
    write(
        Receipt(
            tool="yq",
            at="t",
            method=ReceiptMethod(kind="script", key="k"),
            package=None,
            artifacts=(),
            smoke=None,
            hooks={},
        )
    )
    assert receipt_path("yq").exists()


def test_write_creates_the_receipts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = tmp_path / "does" / "not" / "exist"
    monkeypatch.setattr(receipts, "receipts_dir", lambda: sandbox)
    write(
        Receipt(
            tool="yq",
            at="t",
            method=ReceiptMethod(kind="script", key="k"),
            package=None,
            artifacts=(),
            smoke=None,
            hooks={},
        )
    )
    assert (sandbox / "yq.json").exists()


def test_method_key_is_stable() -> None:
    first = method_key(Method(kind="github_release", params={"repo": "a/b", "asset": "x"}))
    second = method_key(Method(kind="github_release", params={"asset": "x", "repo": "a/b"}))
    third = method_key(Method(kind="github_release", params={"repo": "a/c", "asset": "x"}))
    assert len(first) == 64
    int(first, 16)
    assert first == second
    assert first != third
