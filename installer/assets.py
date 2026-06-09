"""GitHub-release asset-name templating and architecture token mapping."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchTokens:
    machine: str  # x86_64 | aarch64
    deb: str  # amd64 | arm64
    go: str  # amd64 | arm64
    suffix: str  # x86_64 | arm64


_TOKENS = {
    "amd64": ArchTokens(machine="x86_64", deb="amd64", go="amd64", suffix="x86_64"),
    "arm64": ArchTokens(machine="aarch64", deb="arm64", go="arm64", suffix="arm64"),
}


def arch_tokens(normalized: str) -> ArchTokens:
    """Map a normalized arch (amd64/arm64) to release-asset token variants."""
    tokens = _TOKENS.get(normalized)
    if tokens is None:
        raise ValueError(f"unsupported architecture for downloads: {normalized}")
    return tokens


def render_asset(template: str, ver: str, arch: ArchTokens) -> str:
    """Render an asset filename: supports {ver} and {arch.machine|deb|go|suffix}."""
    try:
        return template.format(ver=ver, arch=arch)
    except (KeyError, IndexError, AttributeError) as exc:
        raise ValueError(f"bad asset template '{template}': {exc}") from exc
