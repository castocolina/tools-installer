"""Install receipts: one receipt per tool at ~/.local/state/tools-installer/receipts/<id>.json.

A receipt is the proof a later removal uses: it records what a successful
install actually created (artifacts with absolute paths, per-type fingerprints)
plus the method that created them. A directory is proven by the sha256 of one
key file inside it: the archive member its bin link points to, or
Contents/Info.plist for an .app, which is only read, never written, because
writing inside a bundle breaks its code signature. The key file must resolve
inside the directory it proves (RR3-01). A re-created directory
whose key file has the same bytes is the same software and matches. Device
and inode numbers are never recorded: the device number is assigned at mount
time on btrfs, NFS and ZFS and can change on reboot, and ext4 and XFS reuse
inode numbers. A corrupt, unreadable or tampered receipt means NO PROOF,
never a crash and never a removal. A key file is hashed once per session until
its size or mtime changes.
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
from pathlib import Path, PurePosixPath
from typing import Literal, TypeGuard, cast

from installer import locations
from installer.atomic import atomic_write_text, read_capped
from installer.checksums import sha256_file
from installer.download import artifact_paths
from installer.locations import ensure_dir
from installer.model import TOOL_ID_RE, Method, Tool

# The OS package manager or the agent harness owns these installs; a receipt
# would claim files this installer did not create.
RECEIPTLESS_KINDS = frozenset({"dnf", "apt", "pacman", "rpm_ostree", "skill_pack", "host_setup"})

# 19-UI-SPEC locked copy (D-08). One owner: version_status and the update gate both read it.
CHANGED_SINCE_INSTALL = "changed since install"

# L-19-31: an .app is proven by this file, only ever read.
APP_KEY_FILE = "Contents/Info.plist"

_MAX_RECEIPT_BYTES = 64 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}")

_WRITE_LOCK = threading.Lock()

# Re-hash memo: (str(path), size, mtime_ns) -> the OBSERVED sha256. A hit is
# always compared with the receipt's own digest, so a cached success can never
# vouch for a different expected digest (G6). Its own lock, never _WRITE_LOCK,
# so no code path nests the two (review H1).
_MEMO_LOCK = threading.Lock()
_REHASH_MEMO: dict[tuple[str, int, int], str] = {}


@dataclass(frozen=True)
class ReceiptArtifact:
    path: Path
    type: Literal["dir", "link", "file"]
    target: str | None = None
    sha256: str | None = None
    size: int | None = None
    mtime_ns: int | None = None
    key: str | None = None


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
                "key": artifact.key,
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

    Fail-closed: a missing file, a non-regular file (a FIFO or a device is
    refused without blocking), a symlink at the receipt path, a file over
    64 KiB (the cap is the READ itself, so a file that grows or is swapped
    after any earlier stat is still rejected), malformed JSON, non-UTF-8
    bytes, deep nesting (RecursionError), an unknown version, a tool-id
    mismatch, any wrong-typed field or any artifact violating its type's
    required fields returns None. A bad tool id still raises ValueError:
    that is a programming error, not an untrusted-input case."""
    path = receipt_path(tool_id)
    try:
        raw_bytes = read_capped(path, _MAX_RECEIPT_BYTES, follow_symlinks=False)
        if raw_bytes is None:
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
    not create is dropped, including a dir whose key file is missing, so it is
    never receipt-proven. A dir is keyed by Contents/Info.plist for an app,
    else by the member its bin link points to. Script and manager kinds get
    none. When the write fails over an existing receipt, that receipt is deleted
    (best effort) so it never claims bytes it did not fingerprint, and the raised
    OSError says
    what happened to it."""
    if method.kind in RECEIPTLESS_KINDS:
        return None
    base = default_bin_dir or locations.bin_dir(None)
    created = artifact_paths(method, base)
    link = next((a.path for a in created if a.kind == "link"), None)

    artifacts = tuple(
        artifact
        for entry in created
        if (
            artifact := fingerprint(
                entry.path,
                entry.kind,
                key=_dir_key(method, entry.path, link) if entry.kind == "dir" else None,
                rehash=True,
            )
        )
        is not None
    )
    receipt = _build_receipt(tool, method, artifacts, package=package, smoke=smoke)
    existed = receipt_exists(tool.id)
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


def adopt(
    tool: Tool,
    method: Method,
    artifact: ReceiptArtifact,
    *,
    package: str | None,
    write: bool = True,
) -> Receipt | None:
    """Write a receipt for a file installed before receipts existed (D-09).

    `artifact` is the fingerprint the caller compared with the release digest.
    Under the write lock it is refused when a receipt (or a link in its place)
    appeared, or when ONE fresh fingerprint read from the bytes, never the memo,
    differs from it; the receipt then records that verified fingerprint, so
    bytes swapped after it read as drift, never as proof (review C2-H1). It
    writes through `_write_unlocked`: the
    lock is not reentrant and `write` would hang here (review H1). With
    `write=False`, returns a validated candidate without persisting it; callers
    must not treat that candidate as an on-disk receipt.
    """
    with _WRITE_LOCK:
        if receipt_exists(tool.id):
            return None
        fresh = fingerprint(artifact.path, artifact.type, rehash=True)
        if fresh is None or fresh != artifact:
            return None
        receipt = _build_receipt(tool, method, (fresh,), package=package, smoke=None)
        if write:
            _write_unlocked(receipt)
        return receipt


def delete(tool_id: str) -> None:
    """Remove the receipt for `tool_id` when it exists."""
    receipt_path(tool_id).unlink(missing_ok=True)


def receipt_exists(tool_id: str) -> bool:
    """Whether a receipt is there, counting one that cannot be looked at.

    A missing file (or a missing receipts dir) is False. Any other failure to
    look — an inaccessible receipts dir — is True: the receipt is
    present-but-untrusted, so it is never adopted and it gets no archive-layout
    proof (G23). `lstat` keeps a dangling link counted, and it raises the same
    way on Python 3.12 and 3.14 (Path.exists does not)."""
    try:
        receipt_path(tool_id).lstat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return True
    return True


def all_gone(receipt: Receipt) -> bool:
    """True only when every artifact is conclusively absent.

    A receipt with no artifacts is never gone: there is nothing to prove it
    no longer protects. An artifact whose `lstat` fails for any other reason
    (or a path `lstat` refuses) is not proven gone, so the receipt stays."""
    if not receipt.artifacts:
        return False
    for artifact in receipt.artifacts:
        try:
            os.lstat(artifact.path)
        except (FileNotFoundError, NotADirectoryError):
            continue
        except (OSError, ValueError):
            return False
        return False
    return True


def retire(tool_id: str, receipt: Receipt) -> bool:
    """Delete `receipt` once a re-read shows it is still the same and all gone.

    The pass's twin of `remove_proven`'s rule (D-08): a receipt goes once every
    path it proved is gone. The re-read runs under the write lock, so a receipt
    written meanwhile is kept. An OSError from the delete returns False and the
    receipt stays, still reading as drift."""
    with _WRITE_LOCK:
        current = read(tool_id)
        if current != receipt or not all_gone(receipt):
            return False
        try:
            delete(tool_id)
        except OSError:
            return False
    return True


def _safe_key(key: object) -> TypeGuard[str]:
    """True only for a relative key that cannot leave its directory.

    Absolute, empty, `.` or `..`-containing keys, a NUL and a string the
    filesystem cannot encode are all refused. `_safe_key` bounds the key's
    text and `_key_file` then requires the key to resolve inside the directory,
    so neither the text nor a symlink on the way out can make the matcher hash
    a file outside it (RR3-01)."""
    if not isinstance(key, str) or not key or "\x00" in key:
        return False
    try:
        os.fsencode(key)
    except UnicodeEncodeError:
        return False
    path = PurePosixPath(key)
    return not path.is_absolute() and len(path.parts) >= 1 and ".." not in path.parts


def _key_file(directory: Path, key: str) -> Path | None:
    """Resolve a key only when it stays inside the directory it proves (RR3-01).

    An intermediate symlink that stays inside the tree is followed; one that
    leaves it, a dangling component or a loop is no key file. The final
    component is still checked by the file rule, so a symlink there never
    matches.
    """
    target = directory / key
    try:
        if target.resolve(strict=True).is_relative_to(directory.resolve(strict=True)):
            return target
    except (OSError, RuntimeError, ValueError):
        return None
    return None


def link_key(directory: Path, link: Path) -> str | None:
    """The key file of an archive dir: the member its bin link points to.

    Resolution mirrors `download.is_still_proven`: a strict resolve of both,
    then the member's path relative to the directory. None when either resolve
    fails, the member is outside the directory, or the relative path is empty."""
    try:
        relative = link.resolve(strict=True).relative_to(directory.resolve(strict=True))
    except (OSError, RuntimeError, ValueError):
        return None
    if not relative.parts:
        return None
    return relative.as_posix()


def _dir_key(method: Method, directory: Path, link: Path | None) -> str | None:
    """The key file a method's dir records: Info.plist for an app, else the member."""
    if method.kind == "app":
        return APP_KEY_FILE
    if link is None:
        return None
    return link_key(directory, link)


def fingerprint(
    path: Path,
    kind: Literal["dir", "link", "file"],
    *,
    key: str | None = None,
    rehash: bool = False,
) -> ReceiptArtifact | None:
    """Record what `path` looks like now, for the given artifact type.

    `rehash=True` always reads file bytes instead of trusting the session memo.
    A file needs to be a regular file and records sha256 + size + mtime_ns; a
    link records its readlink target. A dir is proven by one key file resolved
    inside the directory (L-19-31, RR3-01): `key` must be a safe relative path,
    the dir a real directory (a symlink never is), and the key file a regular
    file, whose sha256, size and mtime_ns the artifact records. A re-created
    directory with the same key-file bytes matches. Device and inode numbers
    are never recorded.
    Anything else, or an OSError or ValueError (a path `lstat` would refuse),
    is not fingerprintable."""
    try:
        if kind == "file":
            return _file_fingerprint(path, rehash=rehash)
        if kind == "link":
            if not path.is_symlink():
                return None
            return ReceiptArtifact(path=path, type="link", target=os.readlink(path))
        if kind == "dir":
            if not _safe_key(key):
                return None
            if not stat_module.S_ISDIR(path.lstat().st_mode):
                return None
            target = _key_file(path, key)
            if target is None:
                return None
            key_file = _file_fingerprint(target, rehash=rehash)
            if key_file is None:
                return None
            return ReceiptArtifact(
                path=path,
                type="dir",
                key=key,
                sha256=key_file.sha256,
                size=key_file.size,
                mtime_ns=key_file.mtime_ns,
            )
    except (OSError, ValueError):
        return None
    return None


def _file_fingerprint(path: Path, *, rehash: bool = False) -> ReceiptArtifact | None:
    """Hash a regular file once per session and stat tuple; rehash bypasses the memo.

    A key file is hashed once per session per (path, size, mtime_ns), the same
    memo `_file_matches` keeps, so the layout proof costs one lstat after its
    first pass (WR3-01, D-08). `rehash=True` always reads the bytes.
    """
    st = path.lstat()
    if not stat_module.S_ISREG(st.st_mode):
        return None
    memo_key = (str(path), st.st_size, st.st_mtime_ns)
    with _MEMO_LOCK:
        digest = None if rehash else _REHASH_MEMO.get(memo_key)
    if digest is None:
        digest = sha256_file(path)
        with _MEMO_LOCK:
            _REHASH_MEMO[memo_key] = digest
    return ReceiptArtifact(
        path=path,
        type="file",
        sha256=digest,
        size=st.st_size,
        mtime_ns=st.st_mtime_ns,
    )


def matches(artifact: ReceiptArtifact, *, rehash: bool = False) -> bool:
    """Does the on-disk artifact still equal what the receipt recorded (D-08)?

    A link matches on readlink. A dir matches while it is a real directory
    whose key file resolves inside the directory and matches by the file rule:
    the stat shortcut, or sha256 under `rehash=True`. A changed, missing or
    symlinked key file never
    matches, and a dir with no key never does. A file matches on the stat
    fingerprint, re-hashed only when the stat differs (or `rehash=True`, the
    deletion-time re-proof, which bypasses both the shortcut and the memo). A
    re-hash is remembered as the observed digest per (path, size, mtime_ns)
    and compared with each receipt's own, so an unchanged-but-touched file is
    hashed once per session and a cached success never vouches for a different
    digest. Nothing matches when the artifact is missing; OSError or
    ValueError (a path `lstat` would refuse) is False, never a raise."""
    path = artifact.path
    try:
        if artifact.type == "link":
            return path.is_symlink() and os.readlink(path) == artifact.target
        if artifact.type == "dir":
            if artifact.key is None or not stat_module.S_ISDIR(path.lstat().st_mode):
                return False
            target = _key_file(path, artifact.key)
            return target is not None and _file_matches(target, artifact, rehash=rehash)
        return _file_matches(path, artifact, rehash=rehash)
    except (OSError, ValueError):
        return False


def _file_matches(target: Path, artifact: ReceiptArtifact, *, rehash: bool) -> bool:
    """Whether `target` is the regular file `artifact` recorded (D-08).

    The memo is keyed on `str(target)`, so a dir's key file and a raw file at
    the same path share one observed digest."""
    st = target.lstat()
    if not stat_module.S_ISREG(st.st_mode):
        return False
    unchanged = (
        artifact.size is not None
        and artifact.mtime_ns is not None
        and st.st_size == artifact.size
        and st.st_mtime_ns == artifact.mtime_ns
    )
    if rehash:
        return sha256_file(target) == artifact.sha256
    if unchanged:
        return True
    memo_key = (str(target), st.st_size, st.st_mtime_ns)
    with _MEMO_LOCK:
        observed = _REHASH_MEMO.get(memo_key)
    if observed is None:
        observed = sha256_file(target)
        with _MEMO_LOCK:
            _REHASH_MEMO[memo_key] = observed
    return observed == artifact.sha256


def drifted(receipt: Receipt, *, rehash: bool = False) -> tuple[ReceiptArtifact, ...]:
    """The receipt's artifacts that no longer match, in receipt order."""
    return tuple(a for a in receipt.artifacts if not matches(a, rehash=rehash))


def broken_drift(receipt: Receipt, *, rehash: bool = False) -> tuple[ReceiptArtifact, ...]:
    """Return file/link drift that is BROKEN, skipping dirs before any hash.

    This owns L-19-31: changed files and links are BROKEN and refused; a
    changed dir only loses its removal proof (`drifted` reports that). The
    update gate's `rehash=True` therefore never reads a dir's key file.
    """
    return tuple(
        artifact
        for artifact in receipt.artifacts
        if artifact.type != "dir" and not matches(artifact, rehash=rehash)
    )


def _artifact_int(artifact: dict[str, object], key: str) -> int | None:
    """An optional field that, when present, must still be a non-bool int."""
    value = artifact.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _read_artifact(raw: object) -> ReceiptArtifact | None:
    """Decode one artifact, enforcing each type's required fields.

    Each type keeps only the fields it is checked on: a `file` its 64-hex
    sha256, size and mtime_ns; a `link` its non-empty target; a `dir` its safe
    relative `key` plus that key file's 64-hex sha256, size and mtime_ns.
    Anything else — every 19-22 `dev`/`ino` artifact included — returns None,
    so the receipt is unreadable and unproven."""
    if not isinstance(raw, dict):
        return None
    artifact = cast(dict[str, object], raw)
    raw_path = artifact.get("path")
    kind = artifact.get("type")
    if not isinstance(raw_path, str) or not isinstance(kind, str):
        return None
    if kind not in ("dir", "link", "file"):
        return None
    # A path `lstat` would refuse (an embedded NUL, a lone surrogate) is
    # rejected here, at the boundary, so it can never abort a pass or a removal.
    if "\x00" in raw_path:
        return None
    try:
        os.fsencode(raw_path)
    except UnicodeEncodeError:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        return None
    if kind == "link":
        target = artifact.get("target")
        if not isinstance(target, str) or not target:
            return None
        return ReceiptArtifact(path=path, type="link", target=target)
    sha256 = artifact.get("sha256")
    size = _artifact_int(artifact, "size")
    mtime_ns = _artifact_int(artifact, "mtime_ns")
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        return None
    if size is None or mtime_ns is None:
        return None
    if kind == "file":
        return ReceiptArtifact(path=path, type="file", sha256=sha256, size=size, mtime_ns=mtime_ns)
    key = artifact.get("key")
    if not _safe_key(key):
        return None
    return ReceiptArtifact(
        path=path,
        type="dir",
        key=key,
        sha256=sha256,
        size=size,
        mtime_ns=mtime_ns,
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
