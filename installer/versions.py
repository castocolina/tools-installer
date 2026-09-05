"""Resolve the latest release tag of a GitHub repository."""

import json
import re
import urllib.request
from collections.abc import Callable

# Resolve a repo ("owner/name") to its latest release tag, verbatim. The leading-'v'
# convention varies per project (fd: "v10.4.2"; ripgrep: "15.1.0"), and the raw tag is
# exactly what the release *download path* uses, so it must NOT be stripped here.
TagResolver = Callable[[str], str]

# Fetch raw bytes at a URL. Injected in tests; defaults to urllib.
Fetch = Callable[[str], bytes]


class VersionError(RuntimeError):
    """Raised when a GitHub release tag cannot be resolved."""


_DECLARED_VERSION = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$")


def parse_version(text: str) -> tuple[int, int, int] | None:
    """Tolerant parser for versions this installer READS BACK from a --version call.

    The shape of a tool's own --version output is not this installer's to dictate;
    this parser is never used for a value this project's own registry declares.
    """
    stripped = text.strip()
    if stripped[:1] in ("v", "V"):
        stripped = stripped[1:]
    cut_at = len(stripped)
    for index, char in enumerate(stripped):
        if char in "-+ \t":
            cut_at = index
            break
    stripped = stripped[:cut_at]
    if not stripped:
        return None
    nums: list[int] = []
    for part in stripped.split(".")[:3]:
        if not part.isdigit():
            if not nums:
                return None
            break
        nums.append(int(part))
    if not nums:
        return None
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def parse_declared_version(text: str) -> tuple[int, int, int] | None:
    """Strict parser for versions the REGISTRY DECLARES.

    Observed output must be forgiven; a configured value must not, because a
    configured value is a promise this project made and can fix. A single
    tolerant parser accepted `min_node = "22.bad"` as `(22, 0, 0)`, which
    silently lowered a configured floor to a number nobody wrote.
    """
    match = _DECLARED_VERSION.fullmatch(text.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0))


def meets_minimum(observed: str, minimum: str) -> bool:
    """Fail-closed on both sides, because every caller is gating a mechanism that
    silently misbehaves rather than failing when its prerequisite is absent, and
    a floor nobody can read is not a floor.
    """
    got = parse_version(observed)
    need = parse_declared_version(minimum)
    if got is None or need is None:
        return False
    return got >= need


def urlopen_fetch(url: str) -> bytes:
    """Fetch raw bytes from a URL using urllib. Default Fetch implementation."""
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read()


def resolve_github_tag(repo: str, fetch: Fetch = urlopen_fetch) -> str:
    """Return the latest release tag for owner/repo, verbatim (leading 'v' preserved)."""
    try:
        raw = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionError(f"failed to resolve tag for {repo}: {exc}") from exc
    tag = str(data.get("tag_name", ""))
    if not tag:
        raise VersionError(f"no release tag for {repo}")
    return tag
