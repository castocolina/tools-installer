"""Receipt round-trips and the suite-wide receipts sandbox (plan 19-01, Task 1)."""

import contextlib
import errno
import hashlib
import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import pytest

from installer import atomic, model, receipts
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
    (directory / "k").write_bytes(b"k")
    directory_artifact = receipts.fingerprint(directory, "dir", key="k")
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


def test_read_fails_closed_on_a_file_that_grew_after_the_size_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review C2-M1: the 64 KiB cap is the read itself, not a stat. A file
    that grows (or is swapped) after any earlier size check is still rejected,
    and at most 65537 bytes are ever read from the opened descriptor."""
    path = receipt_path("yq")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x" * 10 + json.dumps({"v": 1, "tool": "yq"}) + " " * 66000, encoding="utf-8")
    sizes: list[int] = []
    real_read = os.read

    def counting_read(fd: int, size: int) -> bytes:
        sizes.append(size)
        return real_read(fd, size)

    monkeypatch.setattr(atomic.os, "read", counting_read)
    assert receipts.read("yq") is None
    assert sizes == [65537]


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
            _variant(
                artifacts=[
                    {
                        "path": "relative/yq",
                        "type": "dir",
                        "key": "k",
                        "sha256": "b" * 64,
                        "size": 1,
                        "mtime_ns": 1,
                    }
                ]
            ),
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
    (directory / "k").write_bytes(b"k")

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

    dir_fp = receipts.fingerprint(directory, "dir", key="k")
    assert dir_fp is not None
    assert dir_fp.type == "dir"
    assert dir_fp.key == "k"

    assert receipts.fingerprint(tmp_path / "gone", "file") is None
    assert receipts.fingerprint(target_file, "dir", key="k") is None
    assert receipts.fingerprint(link, "file") is None
    symlinked_dir = tmp_path / "sdir"
    symlinked_dir.symlink_to(directory, target_is_directory=True)
    assert receipts.fingerprint(symlinked_dir, "dir", key="k") is None


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
    (directory / "k").write_bytes(b"k")
    artifact = receipts.fingerprint(directory, "dir", key="k")
    assert artifact is not None
    assert receipts.matches(artifact)
    import shutil

    shutil.rmtree(directory)
    same = tmp_path / "same"
    same.mkdir()
    (same / "k").write_bytes(b"k")
    directory.symlink_to(same, target_is_directory=True)
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
    (bundle / "Contents").mkdir()
    (bundle / "Contents" / "Info.plist").write_bytes(b"<plist></plist>")
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
    assert written.artifacts == (receipts.fingerprint(bundle, "dir", key=receipts.APP_KEY_FILE),)


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


# --- 19-32 Task 1: a dir is proven by one key file; the reader keeps each type's fields ---


def test_dir_fingerprint_records_its_key_file(tmp_path: Path) -> None:
    """A dir artifact records one key file's digest, never a device or inode.

    The key file must be a regular file inside a real directory. A missing key,
    a regular file typed as dir, a symlink to the directory, or a symlinked key
    file fingerprints as nothing."""
    directory = tmp_path / "d"
    (directory / "bin").mkdir(parents=True)
    key_file = directory / "bin" / "tool"
    key_file.write_bytes(b"tool-bytes")
    artifact = receipts.fingerprint(directory, "dir", key="bin/tool")
    assert artifact is not None
    assert artifact.key == "bin/tool"
    assert artifact.sha256 == hashlib.sha256(b"tool-bytes").hexdigest()
    assert artifact.size == 10
    assert artifact.mtime_ns == key_file.stat().st_mtime_ns
    assert not hasattr(artifact, "ino")
    assert not hasattr(artifact, "dev")

    assert receipts.fingerprint(directory, "dir", key=None) is None
    assert receipts.fingerprint(directory, "dir", key="bin/missing") is None
    regular = tmp_path / "file"
    regular.write_bytes(b"abc")
    assert receipts.fingerprint(regular, "dir", key="bin/tool") is None
    linked = tmp_path / "linked"
    linked.symlink_to(directory, target_is_directory=True)
    assert receipts.fingerprint(linked, "dir", key="bin/tool") is None
    key_link = directory / "bin" / "link"
    key_link.symlink_to(key_file)
    assert receipts.fingerprint(directory, "dir", key="bin/link") is None


def test_dir_recreated_with_the_same_key_file_matches(tmp_path: Path) -> None:
    """A re-created directory whose key file has the same bytes is the same
    software: a reboot or a remount never drops the proof (CR2-01, IN2-01)."""
    original = tmp_path / "a"
    sibling = tmp_path / "b"
    original.mkdir()
    sibling.mkdir()
    (original / "k").write_bytes(b"same")
    (sibling / "k").write_bytes(b"same")
    artifact = receipts.fingerprint(original, "dir", key="k")
    assert artifact is not None
    import shutil

    shutil.rmtree(original)
    sibling.rename(original)
    assert receipts.matches(artifact)
    assert receipts.matches(artifact, rehash=True)


@pytest.mark.parametrize("change", ["rewritten", "removed", "symlinked"])
def test_dir_with_a_changed_or_missing_key_file_does_not_match(tmp_path: Path, change: str) -> None:
    """A changed, missing or symlinked key file never matches the receipt."""
    directory = tmp_path / "d"
    directory.mkdir()
    key_file = directory / "k"
    key_file.write_bytes(b"abc")
    artifact = receipts.fingerprint(directory, "dir", key="k")
    assert artifact is not None
    if change == "rewritten":
        key_file.write_bytes(b"abcd")
    elif change == "removed":
        key_file.unlink()
    else:
        sibling = directory / "other"
        sibling.write_bytes(b"abc")
        key_file.unlink()
        key_file.symlink_to(sibling)
    assert not receipts.matches(artifact)
    receipt = _write_receipt((artifact,))
    assert receipts.drifted(receipt) == (artifact,)


@pytest.mark.parametrize(
    "shape",
    [
        {"dev": 7, "ino": 9},
        {"sha256": "c" * 64, "size": 3, "mtime_ns": 1},
        {"key": "/etc/passwd", "sha256": "c" * 64, "size": 3, "mtime_ns": 1},
        {"key": "../x", "sha256": "c" * 64, "size": 3, "mtime_ns": 1},
        {"key": "", "sha256": "c" * 64, "size": 3, "mtime_ns": 1},
        {"key": 1, "sha256": "c" * 64, "size": 3, "mtime_ns": 1},
        {"key": "k", "size": 3, "mtime_ns": 1},
        {"key": "k", "sha256": "c" * 64, "size": "3", "mtime_ns": 1},
    ],
)
def test_old_shape_dir_artifact_is_unreadable(shape: dict[str, object]) -> None:
    """A dir artifact without a safe key and its three digest fields, including
    every 19-22 dev/ino artifact, makes the whole receipt unreadable."""
    artifact: dict[str, object] = {"path": "/tmp/x/dir", "type": "dir"}
    artifact.update(shape)
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
                    "key": "k",
                    "sha256": digest,
                    "size": 3,
                    "mtime_ns": 1,
                    "target": "/opt/x",
                    "dev": 7,
                    "ino": 9,
                },
            ]
        ),
    )
    loaded = receipts.read("yq")
    assert loaded is not None
    assert loaded.artifacts == (
        ReceiptArtifact(path=Path("/tmp/x/link"), type="link", target="/opt/x"),
        ReceiptArtifact(path=Path("/tmp/x/file"), type="file", sha256=digest, size=3, mtime_ns=1),
        ReceiptArtifact(
            path=Path("/tmp/x/dir"), type="dir", key="k", sha256=digest, size=3, mtime_ns=1
        ),
    )


# --- 19-22 Task 2: malformed paths fail closed; the memo compares each digest ---


def _raw_receipt(artifacts: list[dict[str, object]]) -> None:
    """Write one receipt JSON exactly, so a NUL survives as the escaped form."""
    path = receipt_path("yq")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(_valid_receipt())
    payload["artifacts"] = artifacts
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("bad_path", ["/tmp/x\u0000y", "/tmp/\ud800"])
def test_nul_artifact_path_is_unreadable(bad_path: str) -> None:
    """A path `os` would refuse makes the whole receipt unreadable (G5)."""
    _raw_receipt([{"path": bad_path, "type": "file", "sha256": "b" * 64, "size": 3, "mtime_ns": 1}])
    assert receipts.read("yq") is None


@pytest.mark.parametrize("kind", ["file", "link", "dir"])
def test_invalid_artifact_paths_fail_closed(kind: Literal["dir", "link", "file"]) -> None:
    """A NUL path that slips past the reader answers False/None, never raises."""
    path = Path("/tmp/x\x00")
    artifact = ReceiptArtifact(
        path=path,
        type=kind,
        target="/opt/x",
        key="k",
        sha256="b" * 64,
        size=3,
        mtime_ns=1,
    )
    assert receipts.matches(artifact) is False
    assert receipts.fingerprint(path, kind, key="k") is None


def test_rehash_memo_compares_each_receipts_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A memo hit stores the observed digest and compares each receipt's own (G6)."""
    monkeypatch.setattr(receipts, "_REHASH_MEMO", {})
    target = tmp_path / "yq"
    target.write_bytes(b"abc")
    real = hashlib.sha256(b"abc").hexdigest()
    stat = target.stat()
    right = ReceiptArtifact(
        path=target, type="file", sha256=real, size=stat.st_size + 1, mtime_ns=1
    )
    wrong = ReceiptArtifact(
        path=target, type="file", sha256="d" * 64, size=stat.st_size + 1, mtime_ns=1
    )
    calls: list[Path] = []

    def counting(path: Path) -> str:
        calls.append(path)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    monkeypatch.setattr(receipts, "sha256_file", counting)
    assert receipts.matches(right) is True
    assert receipts.matches(wrong) is False
    assert receipts.matches(right) is True
    assert calls == [target]


def test_receipt_read_goes_through_read_capped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid receipt is read once, without following a symlink at the path."""
    write(_sample(tmp_path))
    seen: list[tuple[Path, int, bool]] = []
    real = receipts.read_capped

    def recording(path: Path, cap: int, *, follow_symlinks: bool) -> bytes | None:
        seen.append((path, cap, follow_symlinks))
        return real(path, cap, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(receipts, "read_capped", recording)
    loaded = receipts.read("yq")

    assert loaded is not None and loaded.tool == "yq"
    assert len(seen) == 1
    path, cap, follow = seen[0]
    assert path == receipt_path("yq")
    assert follow is False
    assert cap == 64 * 1024


def test_receipt_read_never_blocks_on_a_fifo(tmp_path: Path) -> None:
    """A FIFO planted at the receipt path is no receipt, and reading it cannot stall."""
    path = receipt_path("yq")
    path.parent.mkdir(parents=True, exist_ok=True)
    os.mkfifo(path)
    box: list[object] = []
    thread = threading.Thread(target=lambda: box.append(receipts.read("yq")), daemon=True)
    try:
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert box == [None]
    finally:
        with contextlib.suppress(OSError):
            os.close(os.open(path, os.O_WRONLY | os.O_NONBLOCK))
        thread.join(timeout=5)


# --- 19-29 Task 1: an unreadable receipts dir is present-but-untrusted (G23) ---


def deny_receipts_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every stat or open strictly inside the receipts dir raise EACCES.

    Public: other tests import this instead of chmod, which root ignores. The
    directory is captured when the helper is called, and anything outside it
    (or an int fd) still reaches the real call."""
    receipts_dir = receipts.receipts_dir()

    def inside(path: object) -> str | None:
        # str and Path are what pathlib and the callers pass; an int fd, or
        # anything else, is never a receipts-dir path.
        if isinstance(path, str):
            text = path
        elif isinstance(path, Path):
            text = str(path)
        else:
            return None
        candidate = Path(text)
        if candidate == receipts_dir or receipts_dir in candidate.parents:
            return text
        return None

    def wrap(name: str) -> None:
        original: Callable[..., object] = getattr(os, name)

        def guarded(*args: object, **kwargs: object) -> object:
            text = inside(args[0]) if args else None
            if text is not None:
                raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), text)
            return original(*args, **kwargs)

        monkeypatch.setattr(os, name, guarded)

    for call in ("stat", "lstat", "open"):
        wrap(call)


def test_receipt_exists_treats_an_unreadable_dir_as_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert receipts.receipt_exists("yq") is False
    write(_sample(tmp_path))
    assert receipts.receipt_exists("yq") is True
    receipt_path("yq").unlink()
    receipt_path("yq").symlink_to(tmp_path / "nowhere")
    assert receipts.receipt_exists("yq") is True
    deny_receipts_dir(monkeypatch)
    assert receipts.receipt_exists("yq") is True


def test_adopt_refuses_when_the_receipts_dir_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool, method, artifact = _adoptable(tmp_path)
    deny_receipts_dir(monkeypatch)
    assert receipts.adopt(tool, method, artifact, package=None) is None


# --- 19-29 Task 2: a receipt goes only when every artifact is gone (G10) -----


def _planted_receipt(tmp_path: Path) -> tuple[Receipt, Path, Path]:
    """A yq receipt naming one file and one link, both on disk."""
    target = tmp_path / "yq"
    target.write_bytes(b"abc")
    link = tmp_path / "yq-link"
    link.symlink_to(target)
    file_artifact = receipts.fingerprint(target, "file")
    link_artifact = receipts.fingerprint(link, "link")
    assert file_artifact is not None and link_artifact is not None
    receipt = _write_receipt((file_artifact, link_artifact))
    write(receipt)
    return receipt, target, link


def test_all_gone_needs_every_artifact_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, target, link = _planted_receipt(tmp_path)
    assert receipts.all_gone(receipt) is False
    target.unlink()
    assert receipts.all_gone(receipt) is False
    link.unlink()
    assert receipts.all_gone(receipt) is True
    assert receipts.all_gone(_write_receipt(())) is False

    left = tmp_path / "left"
    left.write_bytes(b"still here")
    left_artifact = receipts.fingerprint(left, "file")
    assert left_artifact is not None
    real_lstat: Callable[..., object] = os.lstat
    real_stat: Callable[..., object] = os.stat

    def as_path(path: object) -> Path | None:
        if isinstance(path, str):
            return Path(path)
        if isinstance(path, Path):
            return path
        return None

    def refusing(original: Callable[..., object]) -> Callable[..., object]:
        def guarded(*args: object, **kwargs: object) -> object:
            candidate = as_path(args[0]) if args else None
            if candidate == left:
                raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(candidate))
            return original(*args, **kwargs)

        return guarded

    monkeypatch.setattr(os, "lstat", refusing(real_lstat))
    monkeypatch.setattr(os, "stat", refusing(real_stat))
    assert receipts.all_gone(_write_receipt((left_artifact,))) is False


def test_retire_refuses_a_replaced_receipt(tmp_path: Path) -> None:
    receipt, target, _link = _planted_receipt(tmp_path)
    target.unlink()
    (tmp_path / "yq-link").unlink()
    other = Receipt(
        tool=receipt.tool,
        at="replaced",
        method=receipt.method,
        package=receipt.package,
        artifacts=receipt.artifacts,
        smoke=receipt.smoke,
        hooks=receipt.hooks,
    )
    assert receipts.retire("yq", other) is False
    assert receipt_path("yq").is_file()
    assert receipts.retire("yq", receipt) is True
    assert receipts.receipt_exists("yq") is False

    back = _planted_receipt(tmp_path)
    assert receipts.retire("yq", back[0]) is False
    assert receipts.receipt_exists("yq") is True


# --- 19-32 Task 1: key files, unsafe keys, and record's key choice (L-19-31) --


@pytest.mark.parametrize("bad", ["/abs", "../k", "", ".", "a/../../k", "k\x00", "\ud800"])
def test_unsafe_dir_keys_never_fingerprint(tmp_path: Path, bad: str) -> None:
    """An absolute, parent-traversing, empty, NUL or unencodable key never fingerprints."""
    directory = tmp_path / "d"
    directory.mkdir()
    (directory / "k").write_bytes(b"k")
    assert receipts.fingerprint(directory, "dir", key=bad) is None


def test_link_key_is_the_member_inside_the_dir(tmp_path: Path) -> None:
    """The archive key is the member the bin link points to, and only that."""
    opt = tmp_path / "opt"
    (opt / "rg-x").mkdir(parents=True)
    member = opt / "rg-x" / "rg"
    member.write_bytes(b"rg")
    link = tmp_path / "rg"
    link.symlink_to(member)
    assert receipts.link_key(opt, link) == "rg-x/rg"

    outside = tmp_path / "outside"
    outside.write_bytes(b"nope")
    link.unlink()
    link.symlink_to(outside)
    assert receipts.link_key(opt, link) is None

    link.unlink()
    link.symlink_to(opt / "rg-x" / "missing")
    assert receipts.link_key(opt, link) is None

    link.unlink()
    link.symlink_to(opt)
    assert receipts.link_key(opt, link) is None


@pytest.mark.parametrize("shape", ["archive", "app", "app-without-info-plist"])
def test_record_keys_each_dir_by_its_key_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """An archive dir is keyed by the linked member; an app by Info.plist, read only."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if shape == "archive":
        opt = tmp_path / ".local" / "opt" / "rg"
        member = opt / "rg-x" / "rg"
        member.parent.mkdir(parents=True)
        member.write_bytes(b"rg-bytes")
        (bin_dir / "rg").symlink_to(member)
        method = Method(
            kind="github_release",
            params={"repo": "a/rg", "asset": "rg.tar.gz", "member": "rg-x/rg"},
        )
        written = receipts.record(
            _record_tool("rg", method), method, package=None, smoke="ok", default_bin_dir=bin_dir
        )
        assert written is not None
        assert written.artifacts[0].type == "dir"
        assert written.artifacts[0].key == "rg-x/rg"
        assert written.artifacts[0].sha256 == hashlib.sha256(b"rg-bytes").hexdigest()
        assert written.artifacts[1].type == "link"
        return

    bundle = tmp_path / "Applications" / "Draw.app"
    (bundle / "Contents" / "MacOS").mkdir(parents=True)
    (bundle / "Contents" / "MacOS" / "draw").write_bytes(b"draw")
    info = bundle / "Contents" / "Info.plist"
    if shape == "app":
        info.write_bytes(b"<plist>vendor</plist>")
    (bin_dir / "draw").symlink_to(bundle / "Contents" / "MacOS" / "draw")
    before_files = sorted(path.relative_to(bundle).as_posix() for path in bundle.rglob("*"))
    before_plist = info.read_bytes() if info.exists() else None
    method = Method(
        kind="app",
        params={"url": "https://x/d.zip", "app": "Draw.app", "cli": "Contents/MacOS/draw"},
    )
    written = receipts.record(
        _record_tool("drawio", method),
        method,
        package=None,
        smoke="ok",
        default_bin_dir=bin_dir,
    )
    assert written is not None
    after_files = sorted(path.relative_to(bundle).as_posix() for path in bundle.rglob("*"))
    assert after_files == before_files
    if shape == "app":
        assert written.artifacts[0].key == receipts.APP_KEY_FILE
        assert info.read_bytes() == before_plist
    else:
        assert [artifact.type for artifact in written.artifacts] == ["link"]
