"""Receipt round-trips and the suite-wide receipts sandbox (plan 19-01, Task 1)."""

import hashlib
import io
import json
import os
import threading
from pathlib import Path
from typing import ClassVar, Literal

import pytest

from installer import model, receipts
from installer.model import Method, Tool
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
    directory_artifact = receipts.fingerprint(directory, "dir")
    assert directory_artifact is not None
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
            directory_artifact,
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


# --- Task 2: the reader fails closed ------------------------------------------


class _CountingReader(io.BufferedReader):
    """Reader that records every bounded read size the module asks for."""

    sizes: ClassVar[list[int]] = []

    def read(self, size: int | None = -1) -> bytes:
        _CountingReader.sizes.append(-1 if size is None else size)
        return super().read(size)


def test_read_fails_closed_on_a_file_that_grew_after_the_size_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review C2-M1: the 64 KiB cap is the read itself, not the lstat. A file
    that grows (or is swapped) after the size check is still rejected, and at
    most 65537 bytes are ever read from the opened file."""
    path = receipt_path("yq")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x" * 10 + json.dumps({"v": 1, "tool": "yq"}) + " " * 66000, encoding="utf-8")
    real_lstat = Path.lstat

    def fake_lstat(self: Path) -> os.stat_result:
        stat = real_lstat(self)
        if self == path:
            # Report a small regular file: what the size check saw before the
            # file quietly grew to 66+ KiB.
            fields = [int(value) for value in tuple(stat)]
            fields[6] = 100
            fields[0] = (fields[0] & ~0o170000) | 0o100000
            return os.stat_result((*fields,))
        return stat

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    real_open = Path.open
    _CountingReader.sizes = []

    def fake_open(self: Path, mode: str = "r", buffering: int = -1) -> io.BufferedReader:
        assert mode == "rb"
        return _CountingReader(io.FileIO(self, mode))

    monkeypatch.setattr(Path, "open", fake_open)
    assert receipts.read("yq") is None
    assert _CountingReader.sizes == [65537]
    del real_open


def _malformed(tmp_path: Path, content: str | bytes) -> None:
    path = receipt_path("yq")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = content.encode("utf-8") if isinstance(content, str) else content
    path.write_bytes(payload)


def _valid_receipt() -> str:
    return json.dumps(
        {
            "v": 1,
            "tool": "yq",
            "at": "2026-10-16T12:00:00+00:00",
            "method": {"kind": "github_release", "key": "a" * 64},
            "package": None,
            "artifacts": [],
            "smoke": None,
            "hooks": {},
        }
    )


def _variant(**changes: object) -> str:
    payload = json.loads(_valid_receipt())
    for key, value in changes.items():
        if value is ...:
            payload.pop(key)
        else:
            payload[key] = value
    return json.dumps(payload)


def _artifact_variant(**changes: object) -> str:
    payload = json.loads(_valid_receipt())
    artifact: dict[str, object] = {
        "path": "/tmp/x/yq",
        "type": "file",
        "sha256": "b" * 64,
        "size": 3,
        "mtime_ns": 1,
    }
    for key, value in changes.items():
        if value is ...:
            artifact.pop(key)
        else:
            artifact[key] = value
    payload["artifacts"] = [artifact]
    return json.dumps(payload)


@pytest.mark.parametrize(
    ("label", "content"),
    [
        ("missing file", None),
        ("over the cap", "[" * 65537),
        ("malformed json", "{"),
        ("not utf-8", b"\xff\xfe"),
        ("deep nesting", "[" * 60000),
        ("v 2", '{"v": 2, "tool": "yq"}'),
        ("v missing", '{"tool": "yq"}'),
        ("v true", '{"v": true, "tool": "yq"}'),
        ("wrong tool", _variant(tool="other")),
        ("artifact type socket", _variant(artifacts=[{"path": "/x", "type": "socket"}])),
        (
            "relative artifact path",
            _variant(artifacts=[{"path": "relative/yq", "type": "dir", "dev": 1, "ino": 1}]),
        ),
        ("artifacts not a list", _variant(artifacts="x")),
        ("size is a string", _artifact_variant(size="3")),
        ("size is true", _artifact_variant(size=True)),
        ("hooks is a list", _variant(hooks=[])),
        ("top-level array", "[]"),
        ("file without sha256", _artifact_variant(sha256=...)),
        ("sha256 not 64 hex", _artifact_variant(sha256="XYZ")),
        ("file without size", _artifact_variant(size=...)),
        ("file without mtime_ns", _artifact_variant(mtime_ns=...)),
        ("link without target", _variant(artifacts=[{"path": "/x/yq", "type": "link"}])),
    ],
)
def test_read_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, label: str, content: str | bytes | None
) -> None:
    if content is None:
        pass
    else:
        _malformed(tmp_path, content)
    assert receipts.read("yq") is None


def test_read_fails_closed_on_recursion_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deterministic RecursionError branch coverage: patch json.loads as seen by
    receipts.read so it raises RecursionError, write a small valid-looking
    receipt file, and assert read returns None."""
    payload = json.dumps(
        {
            "v": 1,
            "tool": "yq",
            "at": "2026-10-16T12:00:00+00:00",
            "method": {"kind": "github_release", "key": "a" * 64},
            "package": None,
            "artifacts": [],
            "smoke": None,
            "hooks": {},
        }
    )
    _malformed(tmp_path, payload)

    def raiser(_s: str) -> object:
        raise RecursionError("deep nesting")

    monkeypatch.setattr(receipts.json, "loads", raiser)
    assert receipts.read("yq") is None


@pytest.mark.parametrize("tool_id", ["../x", "A", "", "a/b"])
def test_read_rejects_an_unsafe_id(tool_id: str) -> None:
    with pytest.raises(ValueError):
        receipts.read(tool_id)


@pytest.mark.parametrize("tool_id", ["../x", "A", "", "a/b"])
def test_write_rejects_an_unsafe_id(tool_id: str) -> None:
    receipt = Receipt(
        tool=tool_id,
        at="t",
        method=ReceiptMethod(kind="script", key="k"),
        package=None,
        artifacts=(),
        smoke=None,
        hooks={},
    )
    with pytest.raises(ValueError):
        write(receipt)


def test_write_refuses_a_symlinked_receipt(tmp_path: Path) -> None:
    victim = tmp_path / "victim.json"
    victim.write_text("keep me\n", encoding="utf-8")
    receipt_path("yq").parent.mkdir(parents=True, exist_ok=True)
    receipt_path("yq").symlink_to(victim)
    receipt = Receipt(
        tool="yq",
        at="t",
        method=ReceiptMethod(kind="script", key="k"),
        package=None,
        artifacts=(),
        smoke=None,
        hooks={},
    )
    with pytest.raises(OSError):
        write(receipt)
    assert victim.read_text(encoding="utf-8") == "keep me\n"
    assert receipt_path("yq").is_symlink()


def test_write_rejects_a_relative_artifact_path(tmp_path: Path) -> None:
    receipt = Receipt(
        tool="yq",
        at="t",
        method=ReceiptMethod(kind="script", key="k"),
        package=None,
        artifacts=(ReceiptArtifact(path=Path("relative/yq"), type="dir"),),
        smoke=None,
        hooks={},
    )
    with pytest.raises(ValueError):
        write(receipt)
    assert not receipt_path("yq").exists()


# --- Task 3: stat-fingerprint matching, re-hash memo and the drift list -------


def _write_receipt(artifacts: tuple[ReceiptArtifact, ...]) -> Receipt:
    return Receipt(
        tool="yq",
        at="t",
        method=ReceiptMethod(kind="github_release", key="k"),
        package=None,
        artifacts=artifacts,
        smoke=None,
        hooks={},
    )


def test_fingerprint_records_each_artifact_type(tmp_path: Path) -> None:
    target_file = tmp_path / "yq"
    target_file.write_bytes(b"abc")
    link = tmp_path / "link"
    link.symlink_to("/x/y")
    directory = tmp_path / "dir"
    directory.mkdir()

    file_fp = receipts.fingerprint(target_file, "file")
    assert file_fp is not None
    assert file_fp.type == "file"
    assert file_fp.size == 3
    assert file_fp.mtime_ns == target_file.stat().st_mtime_ns
    assert file_fp.sha256 == hashlib.sha256(b"abc").hexdigest()

    link_fp = receipts.fingerprint(link, "link")
    assert link_fp is not None
    assert link_fp.type == "link"
    assert link_fp.target == os.readlink(link)

    dir_fp = receipts.fingerprint(directory, "dir")
    assert dir_fp is not None
    assert dir_fp.type == "dir"

    assert receipts.fingerprint(tmp_path / "gone", "file") is None
    assert receipts.fingerprint(target_file, "dir") is None
    assert receipts.fingerprint(link, "file") is None
    symlinked_dir = tmp_path / "sdir"
    symlinked_dir.symlink_to(directory, target_is_directory=True)
    assert receipts.fingerprint(symlinked_dir, "dir") is None


def test_matches_link_only_when_the_target_is_unchanged(tmp_path: Path) -> None:
    link = tmp_path / "yq"
    link.symlink_to("/x/y")
    artifact = ReceiptArtifact(path=link, type="link", target="/x/y")
    assert receipts.matches(artifact)
    link.unlink()
    link.symlink_to("/other")
    assert not receipts.matches(artifact)
    link.unlink()
    link.write_text("now a file", encoding="utf-8")
    assert not receipts.matches(artifact)
    link.unlink()
    assert not receipts.matches(artifact)


def test_matches_dir_only_when_it_is_a_real_directory(tmp_path: Path) -> None:
    directory = tmp_path / "dir"
    directory.mkdir()
    artifact = receipts.fingerprint(directory, "dir")
    assert artifact is not None
    assert receipts.matches(artifact)
    directory.rmdir()
    directory.symlink_to(tmp_path, target_is_directory=True)
    assert not receipts.matches(artifact)


def test_matches_file_without_hashing_when_the_stat_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "yq"
    target.write_bytes(b"abc")
    artifact = receipts.fingerprint(target, "file")
    assert artifact is not None

    def boom(path: Path) -> str:
        raise AssertionError("sha256_file must not be called for an unchanged stat")

    monkeypatch.setattr(receipts, "sha256_file", boom)
    assert receipts.matches(artifact)


def test_matches_rehashes_a_touched_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fresh memo per test: the module dict is session state.
    monkeypatch.setattr(receipts, "_REHASH_MEMO", {})
    target = tmp_path / "yq"
    target.write_bytes(b"abc")
    artifact = receipts.fingerprint(target, "file")
    assert artifact is not None
    os.utime(target, ns=(0, 12345))
    calls: list[Path] = []

    def fake_sha256(path: Path) -> str:
        calls.append(path)
        return hashlib.sha256(target.read_bytes()).hexdigest()

    monkeypatch.setattr(receipts, "sha256_file", fake_sha256)
    assert receipts.matches(artifact)
    assert receipts.matches(artifact)
    assert calls == [target] * 1


def test_matches_rejects_a_rewritten_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(receipts, "_REHASH_MEMO", {})
    target = tmp_path / "yq"
    target.write_bytes(b"abc")
    artifact = receipts.fingerprint(target, "file")
    assert artifact is not None
    target.write_bytes(b"xyz")  # same size, different bytes, new mtime
    assert not receipts.matches(artifact)


def test_rehash_true_always_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(receipts, "_REHASH_MEMO", {})
    target = tmp_path / "yq"
    target.write_bytes(b"abc")
    artifact = receipts.fingerprint(target, "file")
    assert artifact is not None
    calls: list[Path] = []

    def fake_sha256(path: Path) -> str:
        calls.append(path)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    monkeypatch.setattr(receipts, "sha256_file", fake_sha256)
    assert receipts.matches(artifact, rehash=True)
    assert receipts.matches(artifact, rehash=True)
    assert len(calls) == 2

    # Swapped in place with the mtime restored: only a re-hash can see it.
    original_stat = target.stat()
    target.write_bytes(b"xyz")
    os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert not receipts.matches(artifact, rehash=True)


def test_drifted_lists_only_the_mismatched_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(receipts, "_REHASH_MEMO", {})
    link = tmp_path / "yq"
    link.symlink_to("/x/y")
    target = tmp_path / "file"
    target.write_bytes(b"abc")
    good_link = ReceiptArtifact(path=link, type="link", target="/x/y")
    good_file = receipts.fingerprint(target, "file")
    assert good_file is not None
    target.write_bytes(b"xyz")
    receipt = _write_receipt((good_link, good_file))
    monkeypatch.setattr(receipts, "_REHASH_MEMO", {})
    assert receipts.drifted(receipt) == (good_file,)
    assert receipts.drifted(receipt) == (good_file,)


# --- Plan 19-09: the one receipt writer ---------------------------------------


def _record_tool(tool_id: str, *methods: Method) -> Tool:
    return Tool(id=tool_id, name=tool_id, category="cli", cmd=tool_id, methods=methods)


def _raw_yq(bin_dir: Path) -> Method:
    return Method(
        kind="github_release",
        params={
            "repo": "mikefarah/yq",
            "asset": "yq_linux_{arch.deb}",
            "member": "yq_linux_amd64",
            "bin_name": "yq",
            "raw": True,
            "bin_dir": str(bin_dir),
        },
    )


def test_record_writes_download_artifacts(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "yq").write_bytes(b"yq-bytes")
    method = _raw_yq(bin_dir)
    written = receipts.record(
        _record_tool("yq", method), method, package=None, smoke="ok", default_bin_dir=bin_dir
    )
    assert written is not None
    assert written.artifacts == (receipts.fingerprint(bin_dir / "yq", "file"),)
    assert written.method.kind == "github_release"
    assert written.method.key == method_key(method)
    assert written.hooks == {}
    assert written.smoke == "ok"
    assert receipts.read("yq") == written


def test_record_skips_missing_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = tmp_path / "Applications" / "Draw.app"
    bundle.mkdir(parents=True)
    method = Method(
        kind="app",
        params={"url": "https://x/d.zip", "app": "Draw.app", "cli": "Contents/MacOS/draw"},
    )
    written = receipts.record(
        _record_tool("drawio", method),
        method,
        package=None,
        smoke="ok",
        default_bin_dir=tmp_path / "bin",
    )
    assert written is not None
    assert written.artifacts == (receipts.fingerprint(bundle, "dir"),)


@pytest.mark.parametrize(
    "method",
    [
        Method(kind="dnf", params={"package": "yq"}),
        Method(kind="apt", params={"package": "yq"}),
        Method(kind="pacman", params={"package": "yq"}),
        Method(kind="rpm_ostree", params={"package": "yq"}),
        Method(kind="skill_pack", params={}),
        Method(kind="host_setup", params={"setup_id": "pi"}),
    ],
)
def test_receiptless_kinds_write_nothing(method: Method) -> None:
    assert method.kind in receipts.RECEIPTLESS_KINDS
    assert receipts.record(_record_tool("yq", method), method, package="yq", smoke=None) is None
    sandbox = receipts.receipts_dir()
    assert not sandbox.exists() or list(sandbox.iterdir()) == []


@pytest.mark.parametrize("tool_id", ["../x", "Yq", "a/b", "-x"])
def test_receipt_ids_follow_the_registry_rule(tool_id: str) -> None:
    assert receipts.TOOL_ID_RE is model.TOOL_ID_RE
    assert model.TOOL_ID_RE.fullmatch(tool_id) is None
    with pytest.raises(ValueError, match="unsafe tool id"):
        receipt_path(tool_id)
    assert receipt_path("yq").name == "yq.json"


@pytest.mark.parametrize("case", ["removed", "delete_fails", "no_previous"])
def test_record_failure_removes_the_previous_receipt(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "yq").write_bytes(b"yq-bytes")
    method = _raw_yq(bin_dir)
    tool = _record_tool("yq", method)
    if case != "no_previous":
        receipts.record(tool, method, package=None, smoke="ok", default_bin_dir=bin_dir)
    path = receipt_path("yq")
    before = path.read_bytes() if path.exists() else None

    def failing_write(_receipt: Receipt) -> None:
        raise OSError("read-only")

    def failing_delete(_tool_id: str) -> None:
        raise OSError("busy")

    monkeypatch.setattr(receipts, "write", failing_write)
    if case == "delete_fails":
        monkeypatch.setattr(receipts, "delete", failing_delete)
    with pytest.raises(OSError) as raised:
        receipts.record(tool, method, package=None, smoke="ok", default_bin_dir=bin_dir)
    message = str(raised.value)
    if case == "removed":
        assert message == "read-only; the previous receipt was removed"
        assert not path.exists()
    elif case == "delete_fails":
        assert message == (
            "read-only; the previous receipt could not be removed and may not match the new files"
        )
        assert path.read_bytes() == before
    else:
        assert message == "read-only"
        assert not path.exists()


# --- 19-14 Task 2: adoption re-checks under the lock (D-09, Pitfall 5, H1, C2-H1) ---


def _adoptable(tmp_path: Path) -> tuple[Tool, Method, ReceiptArtifact]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    placed = bin_dir / "yq"
    placed.write_bytes(b"#!/bin/sh\necho yq\n")
    artifact = receipts.fingerprint(placed, "file")
    assert artifact is not None
    method = _raw_yq(bin_dir)
    return _record_tool("yq", method), method, artifact


def _rewrite_same_length(path: Path) -> None:
    """Different bytes of the same length, with a later mtime."""
    st = path.stat()
    path.write_bytes(b"X" * st.st_size)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


def test_adopt_writes_when_nothing_changed(tmp_path: Path) -> None:
    tool, method, artifact = _adoptable(tmp_path)
    adopted = receipts.adopt(tool, method, artifact, package=None)
    assert adopted is not None
    assert adopted.artifacts == (artifact,)
    assert adopted.method == ReceiptMethod(method.kind, method_key(method))
    assert adopted.package is None
    assert adopted.smoke is None
    assert adopted.hooks == {}
    assert receipts.read("yq") == adopted


def test_adopt_records_the_verified_fingerprint_without_a_second_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool, method, artifact = _adoptable(tmp_path)
    real = receipts.fingerprint
    calls: list[Path] = []

    def replaced_right_after(
        path: Path, kind: Literal["dir", "link", "file"]
    ) -> ReceiptArtifact | None:
        found = real(path, kind)
        calls.append(path)
        _rewrite_same_length(path)
        return found

    monkeypatch.setattr(receipts, "fingerprint", replaced_right_after)
    adopted = receipts.adopt(tool, method, artifact, package=None)
    assert calls == [artifact.path]
    assert adopted is not None
    assert adopted.artifacts == (artifact,)
    assert receipts.drifted(adopted) == (artifact,)


def test_adopt_refuses_when_a_receipt_appeared(tmp_path: Path) -> None:
    tool, method, artifact = _adoptable(tmp_path)
    write(
        Receipt(
            tool="yq",
            at="t",
            method=ReceiptMethod(kind="github_release", key="k"),
            package=None,
            artifacts=(),
            smoke="ok",
            hooks={},
        )
    )
    before = receipt_path("yq").read_bytes()
    assert receipts.adopt(tool, method, artifact, package=None) is None
    assert receipt_path("yq").read_bytes() == before


@pytest.mark.parametrize("change", ["size", "mtime"])
def test_adopt_refuses_when_the_file_changed(tmp_path: Path, change: str) -> None:
    tool, method, artifact = _adoptable(tmp_path)
    if change == "size":
        with artifact.path.open("ab") as handle:
            handle.write(b"# more\n")
    else:
        st = artifact.path.stat()
        os.utime(artifact.path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert receipts.adopt(tool, method, artifact, package=None) is None
    assert not receipt_path("yq").exists()


def test_adopt_completes_without_deadlock(tmp_path: Path) -> None:
    tool, method, artifact = _adoptable(tmp_path)
    results: list[Receipt | None] = []
    adopting = threading.Thread(
        target=lambda: results.append(receipts.adopt(tool, method, artifact, package=None)),
        daemon=True,
    )
    adopting.start()
    adopting.join(timeout=5)
    assert not adopting.is_alive()
    assert results and results[0] is not None
    assert receipt_path("yq").exists()
    rewritten = Receipt(
        tool="yq",
        at="t",
        method=ReceiptMethod(kind="github_release", key="k"),
        package=None,
        artifacts=(),
        smoke=None,
        hooks={},
    )
    writing = threading.Thread(target=lambda: write(rewritten), daemon=True)
    writing.start()
    writing.join(timeout=5)
    assert not writing.is_alive()
    assert receipts.read("yq") == rewritten


# --- 19-22 Task 1: a dir is proven by identity; the reader keeps each type's fields ---


def test_dir_fingerprint_records_its_identity(tmp_path: Path) -> None:
    """A dir artifact records the directory's own (st_dev, st_ino) from lstat.

    A regular file or a symlink to a directory is not a directory this installer
    created, so neither fingerprints as type dir."""
    directory = tmp_path / "dir"
    directory.mkdir()
    artifact = receipts.fingerprint(directory, "dir")
    stat = directory.lstat()
    assert artifact is not None
    assert artifact.dev == stat.st_dev
    assert artifact.ino == stat.st_ino

    regular = tmp_path / "file"
    regular.write_bytes(b"abc")
    assert receipts.fingerprint(regular, "dir") is None
    linked = tmp_path / "linked"
    linked.symlink_to(directory, target_is_directory=True)
    assert receipts.fingerprint(linked, "dir") is None


def test_recreated_dir_does_not_match(tmp_path: Path) -> None:
    """A directory deleted and re-created is a different directory: a vendor
    reinstall into ~/Applications must never inherit an old receipt's proof."""
    original = tmp_path / "a"
    sibling = tmp_path / "b"
    original.mkdir()
    sibling.mkdir()
    artifact = receipts.fingerprint(original, "dir")
    assert artifact is not None
    assert receipts.matches(artifact)
    original.rmdir()
    sibling.rename(original)
    assert not receipts.matches(artifact)
    receipt = _write_receipt((artifact,))
    assert receipts.drifted(receipt) == (artifact,)


@pytest.mark.parametrize(
    "identity",
    [
        {},
        {"dev": True, "ino": 1},
        {"dev": 1, "ino": "1"},
        {"dev": None, "ino": None},
    ],
)
def test_dir_artifact_without_identity_is_unreadable(identity: dict[str, object]) -> None:
    """A dir artifact without an int dev and ino makes the whole receipt unreadable."""
    artifact: dict[str, object] = {"path": "/tmp/x/dir", "type": "dir"}
    artifact.update(identity)
    _malformed(Path("/unused"), _variant(artifacts=[artifact]))
    assert receipts.read("yq") is None


def test_reader_keeps_only_each_types_fields() -> None:
    """The reader drops fields an artifact type is never checked on (G18)."""
    digest = "c" * 64
    _malformed(
        Path("/unused"),
        _variant(
            artifacts=[
                {
                    "path": "/tmp/x/link",
                    "type": "link",
                    "target": "/opt/x",
                    "sha256": digest,
                    "size": 3,
                    "mtime_ns": 1,
                },
                {
                    "path": "/tmp/x/file",
                    "type": "file",
                    "target": "/opt/x",
                    "sha256": digest,
                    "size": 3,
                    "mtime_ns": 1,
                },
                {
                    "path": "/tmp/x/dir",
                    "type": "dir",
                    "dev": 7,
                    "ino": 9,
                    "target": "/opt/x",
                    "sha256": digest,
                },
            ]
        ),
    )
    loaded = receipts.read("yq")
    assert loaded is not None
    assert loaded.artifacts == (
        ReceiptArtifact(path=Path("/tmp/x/link"), type="link", target="/opt/x"),
        ReceiptArtifact(path=Path("/tmp/x/file"), type="file", sha256=digest, size=3, mtime_ns=1),
        ReceiptArtifact(path=Path("/tmp/x/dir"), type="dir", dev=7, ino=9),
    )
