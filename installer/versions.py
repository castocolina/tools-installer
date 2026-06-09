"""Resolve the latest release version of a GitHub repository."""

import json
import urllib.request
from collections.abc import Callable

# Resolve a repo ("owner/name") to its latest version string (no leading 'v').
VersionResolver = Callable[[str], str]

# Fetch raw bytes at a URL. Injected in tests; defaults to urllib.
Fetch = Callable[[str], bytes]


class VersionError(RuntimeError):
    """Raised when a GitHub release version cannot be resolved."""


def urlopen_fetch(url: str) -> bytes:
    """Fetch raw bytes from a URL using urllib. Default Fetch implementation."""
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read()


def resolve_github_version(repo: str, fetch: Fetch = urlopen_fetch) -> str:
    """Return the latest release tag for owner/repo, without a leading 'v'."""
    try:
        raw = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionError(f"failed to resolve version for {repo}: {exc}") from exc
    tag = str(data.get("tag_name", ""))
    if not tag:
        raise VersionError(f"no release tag for {repo}")
    return tag.removeprefix("v")
