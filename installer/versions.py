"""Resolve the latest release tag of a GitHub repository."""

import json
import re
import urllib.request
from collections.abc import Callable

from installer.run import CommandError, run_output

# Resolve a repo ("owner/name") to its latest release tag, verbatim. The leading-'v'
# convention varies per project (fd: "v10.4.2"; ripgrep: "15.1.0"), and the raw tag is
# exactly what the release *download path* uses, so it must NOT be stripped here.
TagResolver = Callable[[str], str]

# Fetch raw bytes at a URL. Injected in tests; defaults to urllib.
Fetch = Callable[[str], bytes]


class VersionError(RuntimeError):
    """Raised when a GitHub release tag cannot be resolved."""


_DECLARED_VERSION = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$")

# The first whitespace-delimited token of a --version line, as semver reads it:
# an optional `v`, a dotted all-numeric core, an optional `-prerelease`, and an
# optional `+build`. A core component that is not a number makes the WHOLE token
# unparseable, which is the point — see parse_version.
_OBSERVED_VERSION = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")

# Rank of a final release, and of the prereleases that precede it. Semver orders
# `11.0.0-rc.1` BELOW `11.0.0`, and this installer needs that order for a real
# reason rather than a formal one: every caller is gating on a FEATURE, and an
# rc build of the release that introduces it has not necessarily shipped it.
_RELEASE = 1
_PRERELEASE = 0

# (major, minor, patch, release rank). The rank is what lets a prerelease
# compare below the release it precedes with a plain tuple comparison.
Version = tuple[int, int, int, int]


def parse_version(text: str) -> Version | None:
    """Parser for versions this installer READS BACK from a --version call.

    Forgiving about SHAPE, never about MEANING. The shape of a tool's own
    --version output is not this installer's to dictate, so a trailing
    `(arm64)`, a `+build` suffix, a missing patch component and a fourth
    component (Chrome-style `140.0.7339.16`) are all read rather than refused.

    But a component that is not a number is not a shape this parser can read at
    all, and zero-filling it was a false PASS: `11.bad` parsed as `(11, 0, 0)`
    and satisfied an `11.0.0` floor, which defeats the fail-closed contract
    `meets_minimum` exists to keep. Unparseable input returns None so the caller
    refuses, exactly as it does when the command could not be run.

    A prerelease is parsed, not discarded: it returns the numeric core with
    `_PRERELEASE` as its rank, so `11.0.0-rc.1` sorts BELOW `11.0.0` while
    `12.0.0-rc.1` still clears an `11.1.0` floor. Cutting the suffix off and
    returning the bare core — what this did before — claimed an rc had shipped
    the feature set of the release it precedes.

    Unlike `parse_declared_version`, this is not the strict parser: a value the
    REGISTRY declares is a promise this project made and can fix, so it is held
    to a stricter shape there.
    """
    token = text.strip().split(maxsplit=1)
    if not token:
        return None
    match = _OBSERVED_VERSION.fullmatch(token[0])
    if match is None:
        return None
    nums = [int(part) for part in match.group(1).split(".")[:3]]
    while len(nums) < 3:
        nums.append(0)
    rank = _PRERELEASE if match.group(2) else _RELEASE
    return (nums[0], nums[1], nums[2], rank)


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

    A declared floor is always a final release — `parse_declared_version`
    rejects a prerelease outright — so it is compared at `_RELEASE` rank, which
    is what puts `11.0.0-rc.1` below an `11.0.0` floor.
    """
    got = parse_version(observed)
    need = parse_declared_version(minimum)
    if got is None or need is None:
        return False
    return got >= (*need, _RELEASE)


# Full dotted numeric core plus optional prerelease identifiers. A release is
# encoded as None in the second slot so it outranks any prerelease under a
# plain tuple comparison after the cores are zero-padded to equal length.
StatusVersion = tuple[tuple[int, ...], tuple[tuple[int, int | str], ...] | None]


def extract_observed_version(text: str) -> str | None:
    """Return the first parseable version token across ALL of `text`, verbatim.

    `parse_version` only inspects the first whitespace-delimited token of a
    single line. Tools such as eza put the version on a later line; this walks
    every token so the caller can both compare and display what was found.
    """
    for token in text.split():
        if parse_version(token) is not None:
            return token
    return None


def parse_status_version(text: str) -> StatusVersion | None:
    """Parser for "is a newer version available", not a feature-floor check.

    `parse_version` answers "does the installed version clear a declared FEATURE
    FLOOR", where three components and one collapsed prerelease rank are
    sufficient. That contract is pinned by tests/test_versions.py and depended
    on by `meets_minimum`, `executors._require_minimum`, and `pnpm_globals`.
    This parser answers "is a newer version available", where discarding a
    fourth numeric component or collapsing distinct prereleases would report a
    false `up to date`. Build metadata (`+build`) is parsed and discarded:
    semver does not include it in precedence.
    """
    match = _OBSERVED_VERSION.fullmatch(text.strip())
    if match is None:
        return None
    core = tuple(int(part) for part in match.group(1).split("."))
    raw_pre = match.group(2)
    if raw_pre is None:
        return (core, None)
    identifiers: list[tuple[int, int | str]] = []
    for ident in raw_pre.split("."):
        if ident.isdigit():
            identifiers.append((0, int(ident)))
        else:
            identifiers.append((1, ident))
    return (core, tuple(identifiers))


def is_outdated(observed: str, latest: str) -> bool | None:
    """True when `observed` is older than `latest`; None when either side cannot rank.

    Comparison goes through `parse_status_version`, never `parse_version`: a
    discarded fourth component or a collapsed prerelease is a false `up to date`.
    """
    left = parse_status_version(observed)
    right = parse_status_version(latest)
    if left is None or right is None:
        return None
    left_core, left_pre = left
    right_core, right_pre = right
    width = max(len(left_core), len(right_core))
    left_padded = left_core + (0,) * (width - len(left_core))
    right_padded = right_core + (0,) * (width - len(right_core))
    if left_padded != right_padded:
        return left_padded < right_padded
    if left_pre is None and right_pre is None:
        return False
    if left_pre is None:
        return False
    if right_pre is None:
        return True
    return left_pre < right_pre


# A bound belongs on a query, never on the side-effecting install itself
# (see installer.run.run_output).
PROBE_VERSION_TIMEOUT = 5.0

# The comma-joined group is what makes `pnpm add -g a,b` install BOTH packages
# into ONE shared install group, which is the entire mechanism this project
# relies on to let a dependent resolve its peer. pnpm shipped that grouping in
# 11.1, NOT in the 11.0 global redesign — 11.0 introduced the hash-keyed global
# layout, and the shared-install-group semantics for a comma-separated spec
# arrived in the 11.1 release. On pnpm 10 the same string is not a group at all:
# it is one package name containing a comma.
#
# The floor is therefore the version that HAS the feature, not the major it
# arrived in. A floor of 11.0.0 let a pnpm 11.0.x machine pass this preflight
# while lacking the grouping semantics behind it, which is precisely the silent
# misbehaviour `meets_minimum`'s fail-closed contract exists to prevent.
PNPM_CO_INSTALL_MIN = "11.1.0"

# --allow-build was added in pnpm 10.4.0 (pnpm add documentation); on anything
# older the flag is an unknown option.
PNPM_ALLOW_BUILD_MIN = "10.4.0"


def _default_probe_version(argv: list[str]) -> str | None:
    """The one implementation every runtime version read goes through.

    One definition, but NOT one patch point: `installer.executors` and
    `installer.pnpm_globals` each do `from installer.versions import
    probe_version`, which binds this function object at import time. Rebinding
    `installer.versions.probe_version` therefore changes nothing for either
    consumer — the name to patch is the CONSUMER's
    (`executors.probe_version`, `pnpm_globals.probe_version`), which is what
    every test in the suite already does.

    The injection discipline `real_pnpm` carries still holds: no production
    path reaches a real `--version` subprocess except through this function,
    and no test reaches one as long as it patches the binding its subject
    actually reads.
    """
    try:
        text = run_output(argv, timeout=PROBE_VERSION_TIMEOUT)
    except (CommandError, OSError):
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


probe_version: Callable[[list[str]], str | None] = _default_probe_version


def _default_probe_version_output(argv: list[str]) -> str | None:
    """Full-stdout sibling of `_default_probe_version`.

    `probe_version` is pinned to the first non-empty line; tools that put the
    version on a later line need the whole stdout so `extract_observed_version`
    can scan it. This function does not replace that contract.
    """
    try:
        text = run_output(argv, timeout=PROBE_VERSION_TIMEOUT)
    except (CommandError, OSError):
        return None
    if not text.strip():
        return None
    return text


probe_version_output: Callable[[list[str]], str | None] = _default_probe_version_output


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
