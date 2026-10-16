"""Install receipts: one receipt per tool at ~/.local/state/tools-installer/receipts/<id>.json.

A receipt is the proof a later removal uses: it records what a successful
install actually created (artifacts with absolute paths, per-type fingerprints)
plus the method that created them. A corrupt, unreadable or tampered receipt
means NO PROOF, never a crash and never a removal.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat as stat_module
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from installer import locations
from installer.atomic import atomic_write_text
from installer.checksums import sha256_file
from installer.download import artifact_paths
from installer.locations import ensure_dir
from installer.model import TOOL_ID_RE, Method, Tool

# The OS package manager or the agent harness owns these installs; a receipt
# would claim files this installer did not create.
RECEIPTLESS_KINDS = frozenset({"dnf", "apt", "pacman", "rpm_ostree", "skill_pack", "host_setup"})

_MAX_RECEIPT_BYTES = 64 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}")

_WRITE_LOCK = threading.Lock()

# Re-hash memo: (str(path), size, mtime_ns) -> "matches the recorded sha256".
# Its own lock, never _WRITE_LOCK, so no code path nests the two (review H1).
_MEMO_LOCK = threading.Lock()
_REHASH_MEMO: dict[tuple[str, int, int], bool] = {}


@dataclass(frozen=True)
class ReceiptArtifact:
    path: Path
    type: Literal["dir", "link", "file"]
    target: str | None = None
    sha256: str | None = None
    size: int | None = None
    mtime_ns: int | None = None


@dataclass(frozen=True)
class ReceiptMethod:
    kind: str
    key: str


@dataclass(frozen=True)
class Receipt:
    tool: str
    at: str
    method: ReceiptMethod
    package: str | None
    artifacts: tuple[ReceiptArtifact, ...]
    smoke: str | None
    hooks: Mapping[str, tuple[str, ...]]


def default_receipts_dir() -> Path:
    """The receipts directory, resolved at call time next to settings.json."""
    return Path.home() / ".local" / "state" / "tools-installer" / "receipts"


def receipts_dir() -> Path:
    """The receipts directory the module writes into (the test sandbox patches this)."""
    return default_receipts_dir()


def receipt_path(tool_id: str) -> Path:
    """The receipt file for a tool id; a non-safe id is rejected before any path."""
    if not TOOL_ID_RE.fullmatch(tool_id):
        raise ValueError(f"unsafe tool id: {tool_id!r}")
    return receipts_dir() / f"{tool_id}.json"


def method_key(method: Method) -> str:
    """Stable informational key for a method; never matched on (a pin bump changes it)."""
    payload = json.dumps(
        {"kind": method.kind, "params": method.params}, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_unlocked(receipt: Receipt) -> None:
    """Encode and atomically write one receipt. The caller must hold _WRITE_LOCK."""
    path = receipt_path(receipt.tool)
    if path.is_symlink():
        raise OSError(
            f"tool '{receipt.tool}': receipt path is a symlink; refusing to write through it"
        )
    artifacts: list[dict[str, object]] = []
    for artifact in receipt.artifacts:
        if not Path(artifact.path).is_absolute():
            raise ValueError(f"receipt artifact path must be absolute: {artifact.path}")
        artifacts.append(
            {
                "path": str(artifact.path),
                "type": artifact.type,
                "target": artifact.target,
                "sha256": artifact.sha256,
                "size": artifact.size,
                "mtime_ns": artifact.mtime_ns,
            }
        )
    payload: dict[str, object] = {
        "v": 1,
        "tool": receipt.tool,
        "at": receipt.at,
        "method": {"kind": receipt.method.kind, "key": receipt.method.key},
        "package": receipt.package,
        "artifacts": artifacts,
        "smoke": receipt.smoke,
        "hooks": {name: list(ids) for name, ids in receipt.hooks.items()},
    }
    path = receipt_path(receipt.tool)
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")


def write(receipt: Receipt) -> None:
    """Atomically write one receipt for `receipt.tool`."""
    with _WRITE_LOCK:
        _write_unlocked(receipt)


def read(tool_id: str) -> Receipt | None:
    """Read back the receipt written for `tool_id`; None when it cannot be trusted.

    Fail-closed: a missing file, a non-regular file, a file over 64 KiB (the
    cap is the READ itself, so a file that grows or is swapped after the size
    check is still rejected), malformed JSON, non-UTF-8 bytes, deep nesting
    (RecursionError), an unknown version, a tool-id mismatch, any wrong-typed
    field or any artifact violating its type's required fields returns None.
    A bad tool id still raises ValueError: that is a programming error, not
    an untrusted-input case."""
    path = receipt_path(tool_id)
    try:
        st = path.lstat()
        if not stat_module.S_ISREG(st.st_mode) or st.st_size > _MAX_RECEIPT_BYTES:
            return None
        with path.open("rb") as handle:
            raw_bytes = handle.read(_MAX_RECEIPT_BYTES + 1)
        if len(raw_bytes) > _MAX_RECEIPT_BYTES:
            return None
        raw = raw_bytes.decode("utf-8")
        raw_data = json.loads(raw)
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(raw_data, dict):
        return None
    data = cast(dict[str, object], raw_data)
    version = data.get("v")
    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
        return None
    if data.get("tool") != tool_id:
        return None
    raw_method = data.get("method")
    if not isinstance(raw_method, dict):
        return None
    method = cast(dict[str, object], raw_method)
    method_kind = method.get("kind")
    method_key_value = method.get("key")
    if not isinstance(method_kind, str) or not isinstance(method_key_value, str):
        return None
    raw_artifacts = data.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return None
    artifact_list: list[object] = list(cast(list[object], raw_artifacts))
    artifacts: list[ReceiptArtifact] = []
    for raw_artifact in artifact_list:
        artifact = _read_artifact(raw_artifact)
        if artifact is None:
            return None
        artifacts.append(artifact)
    package = data.get("package")
    if package is not None and not isinstance(package, str):
        return None
    smoke = data.get("smoke")
    if smoke is not None and not isinstance(smoke, str):
        return None
    hooks = _read_hooks(data.get("hooks"))
    if hooks is None:
        return None
    at = data.get("at")
    if not isinstance(at, str):
        return None
    return Receipt(
        tool=tool_id,
        at=at,
        method=ReceiptMethod(kind=method_kind, key=method_key_value),
        package=package,
        artifacts=tuple(artifacts),
        smoke=smoke,
        hooks=hooks,
    )


def _build_receipt(
    tool: Tool,
    method: Method,
    artifacts: tuple[ReceiptArtifact, ...],
    *,
    package: str | None,
    smoke: str | None,
) -> Receipt:
    """The one receipt constructor; callers pass fingerprints they already hold.

    Pure: it never fingerprints, hashes or stats a path, so a caller that
    verified an artifact (adoption, under its lock) records exactly that."""
    return Receipt(
        tool=tool.id,
        at=datetime.now(UTC).isoformat(timespec="microseconds"),
        method=ReceiptMethod(kind=method.kind, key=method_key(method)),
        package=package,
        artifacts=artifacts,
        smoke=smoke,
        hooks={},
    )


def record(
    tool: Tool,
    method: Method,
    *,
    package: str | None,
    smoke: str | None,
    default_bin_dir: Path | None = None,
) -> Receipt | None:
    """Write the receipt for a method that just succeeded; None for a receiptless kind.

    Artifacts are `artifact_paths` (D-07) fingerprinted now; one the method did
    not create is dropped. Script and manager kinds get none. When the write
    fails over an existing receipt, that receipt is deleted (best effort) so it
    never claims bytes it did not fingerprint, and the raised OSError says
    what happened to it."""
    if method.kind in RECEIPTLESS_KINDS:
        return None
    base = default_bin_dir or locations.bin_dir(None)
    found = (fingerprint(a.path, a.kind) for a in artifact_paths(method, base))
    artifacts = tuple(a for a in found if a is not None)
    receipt = _build_receipt(tool, method, artifacts, package=package, smoke=smoke)
    path = receipt_path(tool.id)
    existed = path.exists() or path.is_symlink()
    try:
        write(receipt)
    except OSError as exc:
        if not existed:
            raise
        try:
            delete(tool.id)
        except OSError:
            raise OSError(
                f"{exc}; the previous receipt could not be removed and may not match the new files"
            ) from exc
        raise OSError(f"{exc}; the previous receipt was removed") from exc
    return receipt


def delete(tool_id: str) -> None:
    """Remove the receipt for `tool_id` when it exists."""
    receipt_path(tool_id).unlink(missing_ok=True)


def fingerprint(path: Path, kind: Literal["dir", "link", "file"]) -> ReceiptArtifact | None:
    """Record what `path` looks like now, for the given artifact type.

    A file needs to be a regular file and records sha256 + size + mtime_ns; a
    link records its readlink target; a dir must be a real directory (never a
    symlink). Anything else, or an OSError, is not fingerprintable."""
    try:
        if kind == "file":
            st = path.lstat()
            if not stat_module.S_ISREG(st.st_mode):
                return None
            return ReceiptArtifact(
                path=path,
                type="file",
                sha256=sha256_file(path),
                size=st.st_size,
                mtime_ns=st.st_mtime_ns,
            )
        if kind == "link":
            if not path.is_symlink():
                return None
            return ReceiptArtifact(path=path, type="link", target=os.readlink(path))
        if kind == "dir":
            if not path.is_dir() or path.is_symlink():
                return None
            return ReceiptArtifact(path=path, type="dir")
    except OSError:
        return None
    return None


def matches(artifact: ReceiptArtifact, *, rehash: bool = False) -> bool:
    """Does the on-disk artifact still equal what the receipt recorded (D-08)?

    A link matches on readlink; a dir on being a real directory; a file on the
    stat fingerprint, re-hashed only when the stat differs (or `rehash=True`,
    the deletion-time re-proof, which bypasses both the shortcut and the
    memo). A re-hash result is remembered per (path, size, mtime_ns), so an
    unchanged-but-touched file is hashed once per session. Nothing matches
    when the artifact is missing; OSError is False, never a raise."""
    path = artifact.path
    try:
        if artifact.type == "link":
            return path.is_symlink() and os.readlink(path) == artifact.target
        if artifact.type == "dir":
            return path.is_dir() and not path.is_symlink()
        st = path.lstat()
        if not stat_module.S_ISREG(st.st_mode):
            return False
        unchanged = (
            artifact.size is not None
            and artifact.mtime_ns is not None
            and st.st_size == artifact.size
            and st.st_mtime_ns == artifact.mtime_ns
        )
        if rehash:
            return sha256_file(path) == artifact.sha256
        if unchanged:
            return True
        key = (str(path), st.st_size, st.st_mtime_ns)
        with _MEMO_LOCK:
            memoized = _REHASH_MEMO.get(key)
        if memoized is None:
            memoized = sha256_file(path) == artifact.sha256
            with _MEMO_LOCK:
                _REHASH_MEMO[key] = memoized
        return memoized
    except OSError:
        return False


def drifted(receipt: Receipt, *, rehash: bool = False) -> tuple[ReceiptArtifact, ...]:
    """The receipt's artifacts that no longer match, in receipt order."""
    return tuple(a for a in receipt.artifacts if not matches(a, rehash=rehash))


def _artifact_str(artifact: dict[str, object], key: str) -> str | None:
    """An optional field that, when present, must still be a str."""
    value = artifact.get(key)
    return value if isinstance(value, str) else None


def _artifact_int(artifact: dict[str, object], key: str) -> int | None:
    """An optional field that, when present, must still be a non-bool int."""
    value = artifact.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _read_artifact(raw: object) -> ReceiptArtifact | None:
    """Decode one artifact, enforcing each type's required fields.

    A `file` without a 64-hex sha256, size and mtime_ns, or a `link` without a
    non-empty target, would otherwise pass the stat shortcut on a matching
    size/mtime (review M1) or follow a hashless proof — so they are rejected
    here, at the boundary, never mid-removal."""
    if not isinstance(raw, dict):
        return None
    artifact = cast(dict[str, object], raw)
    raw_path = artifact.get("path")
    kind = artifact.get("type")
    if not isinstance(raw_path, str) or not isinstance(kind, str):
        return None
    if kind not in ("dir", "link", "file"):
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        return None
    if kind == "file":
        sha256 = artifact.get("sha256")
        size = _artifact_int(artifact, "size")
        mtime_ns = _artifact_int(artifact, "mtime_ns")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            return None
        if size is None or mtime_ns is None:
            return None
        return ReceiptArtifact(
            path=path,
            type="file",
            target=_artifact_str(artifact, "target"),
            sha256=sha256,
            size=size,
            mtime_ns=mtime_ns,
        )
    if kind == "link":
        target = _artifact_str(artifact, "target")
        if not target:
            return None
        return ReceiptArtifact(
            path=path,
            type="link",
            target=target,
            sha256=_artifact_str(artifact, "sha256"),
            size=_artifact_int(artifact, "size"),
            mtime_ns=_artifact_int(artifact, "mtime_ns"),
        )
    return ReceiptArtifact(
        path=path,
        type="dir",
        target=_artifact_str(artifact, "target"),
        sha256=_artifact_str(artifact, "sha256"),
        size=_artifact_int(artifact, "size"),
        mtime_ns=_artifact_int(artifact, "mtime_ns"),
    )


def _read_hooks(value: object) -> dict[str, tuple[str, ...]] | None:
    if not isinstance(value, dict):
        return None
    hooks: dict[str, tuple[str, ...]] = {}
    for raw_name, raw_ids in cast(dict[object, object], value).items():
        if not isinstance(raw_name, str) or not isinstance(raw_ids, list):
            return None
        ids: list[str] = []
        for raw_entry in cast(list[object], raw_ids):
            if not isinstance(raw_entry, str):
                return None
            ids.append(raw_entry)
        hooks[raw_name] = tuple(ids)
    return hooks
