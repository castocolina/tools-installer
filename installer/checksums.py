"""Parse published sha256 checksum files and hash downloaded assets."""

import hashlib
from pathlib import Path, PurePosixPath


class ChecksumMismatch(Exception):
    """A downloaded asset's sha256 digest differs from the published one.

    Deliberately NOT an ExecutorError subclass: the engine's generic
    fall-through except must not swallow the security signal.
    """

    def __init__(self, asset: str, expected: str, actual: str) -> None:
        self.asset = asset
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"checksum mismatch for {asset}: expected {expected[:8]}…, got {actual[:8]}…"
        )


def expected_sha256(text: str, asset: str) -> str | None:
    """Find the published sha256 for `asset` in a checksum file's content.

    Handles multi-line `<hash>  <name>` files (including the `*<name>` binary
    marker and path-prefixed names), single-line sidecars, and bare-hash
    sidecar files. Returns None when the asset has no entry.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and _names_match(parts[1], asset) and _is_sha256(parts[0]):
            return parts[0].lower()
    if len(lines) == 1 and len(lines[0].split()) == 1 and _is_sha256(lines[0]):
        return lines[0].lower()
    return None


def _names_match(listed: str, asset: str) -> bool:
    name = listed.lstrip("*")
    return name == asset or PurePosixPath(name).name == asset


def _is_sha256(token: str) -> bool:
    if len(token) != 64:
        return False
    try:
        int(token, 16)
    except ValueError:
        return False
    return True


def sha256_file(path: Path) -> str:
    """Streaming sha256 hex digest of a file."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()
