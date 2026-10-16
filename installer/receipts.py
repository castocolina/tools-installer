"""Install receipts: one receipt per tool at ~/.local/state/tools-installer/receipts/<id>.json.

A receipt is the proof a later removal uses: it records what a successful
install actually created (artifacts with absolute paths, per-type fingerprints)
plus the method that created them. A corrupt, unreadable or tampered receipt
means NO PROOF, never a crash and never a removal.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from installer.atomic import atomic_write_text
from installer.locations import ensure_dir
from installer.model import Method

_TOOL_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")

_WRITE_LOCK = threading.Lock()


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
    if not _TOOL_ID_RE.fullmatch(tool_id):
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

    Fail-closed (Task 2 hardens this to cover every malformed input)."""
    try:
        raw = receipt_path(tool_id).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        raw_data = json.loads(raw)
    except ValueError:
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
        if not isinstance(raw_artifact, dict):
            return None
        artifact = cast(dict[str, object], raw_artifact)
        raw_path = artifact.get("path")
        kind = artifact.get("type")
        if not isinstance(raw_path, str) or not isinstance(kind, str):
            return None
        if kind not in ("dir", "link", "file"):
            return None
        path = Path(raw_path)
        if not path.is_absolute():
            return None
        artifacts.append(
            ReceiptArtifact(
                path=path,
                type=kind,
                target=_opt_str(artifact.get("target")),
                sha256=_opt_str(artifact.get("sha256")),
                size=_opt_int(artifact.get("size")),
                mtime_ns=_opt_int(artifact.get("mtime_ns")),
            )
        )
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


def delete(tool_id: str) -> None:
    """Remove the receipt for `tool_id` when it exists."""
    receipt_path(tool_id).unlink(missing_ok=True)


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _opt_int(value: object) -> int | None:
    """A JSON int, never a bool (True is an int subclass in Python)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


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
