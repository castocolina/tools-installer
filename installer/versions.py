"""Resolve the latest release tag of a GitHub repository."""

import json
import os
import re
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from installer.run import CommandError, run_output

# Resolve a repo ("owner/name") to its latest release tag, verbatim. The leading-'v'
# convention varies per project (fd: "v10.4.2"; ripgrep: "15.1.0"), and the raw tag is
# exactly what the release *download path* uses, so it must NOT be stripped here.
TagResolver = Callable[[str], str]

# Fetch raw bytes at a URL. Injected in tests; defaults to urllib.
Fetch = Callable[[str], bytes]

ReleaseResolver = Callable[[str], "Release"]

_SHA256_DIGEST = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


@dataclass(frozen=True)
class Release:
    tag: str
    digests: Mapping[str, str]


class VersionError(RuntimeError):
    """Raised when a GitHub release tag cannot be resolved."""


_DECLARED_VERSION = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$")

# The first whitespace-delimited token of a --version line, as semver reads it:
# an optional `v`, a dotted all-numeric core, an optional `-prerelease`, and an
# optional `+build`. A core component that is not a number makes the WHOLE token
# unparseable, which is the point — see parse_version.
_OBSERVED_VERSION = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")

# Verified 2026-09-14: every installed registry tool's `--version` output was
# run live on a real host during this phase's research (~50 tools). `jq` was
# the ONLY tool whose output glues its own name onto the version with a
# hyphen and no separating whitespace (`jq-1.8.1`) — the exact shape the
# `_match_observed_version` fallback below exists for.
#
# Not covered: one tool fails to parse for a reason this mechanism deliberately
# leaves alone. `bash`'s extra characters follow the numeric core instead of
# preceding it (`GNU bash, version 5.3.9(1)-release (...)`), so no leading-prefix
# strip can reach them. Widening the boundary character class to catch it would
# reintroduce the free-substring-search false-positive risk this mechanism was
# chosen over instead. Procs' leading double quote on its version token is handled
# by `_normalize_version_token` (audit E line 75), not by this boundary.
#
# Finds the LAST '-' or whitespace character immediately followed by a digit
# or v/V. Greedy `.*` backtracks from the right, so it naturally prefers the
# rightmost valid split point: `jq-1.8.1` isolates at "1.8.1" (the only '-'),
# and a token with an embedded prerelease hyphen like `tool-2.3.4-rc.1` still
# isolates at "2.3.4-rc.1" (the *rc.1* hyphen's next character is a letter,
# not `[vV]?\d`, so it is never a valid split point; backtracking lands on
# the '-' before "2.3.4" instead). The glued-name prefix before that delimiter
# must start with an ASCII letter and be at least two characters (audit B WR-02:
# bare flags like `-1` and one-letter names like `a-1` must not strip).
_NAME_PREFIX_BOUNDARY = re.compile(r".*[-\s](?=[vV]?\d)")


def _normalize_version_token(token: str) -> str:
    """Strip trailing punctuation, a lazygit-style `version=` prefix, then one
    leading and one trailing quote independently (quotes need not be paired).
    """
    cleaned = token
    while cleaned and cleaned[-1] in ",;":
        cleaned = cleaned[:-1]
    if cleaned.startswith("version="):
        cleaned = cleaned[len("version=") :]
    if cleaned[:1] in {'"', "'"}:
        cleaned = cleaned[1:]
    if cleaned[-1:] in {'"', "'"}:
        cleaned = cleaned[:-1]
    return cleaned


def _strip_name_prefix(token: str) -> str:
    """Split a glued `<name>-<version>` token down to its trailing,
    version-shaped segment. `jq --version` prints `jq-1.8.1` as ONE
    whitespace-delimited token [VERIFIED: live `jq --version` this session].
    A no-op (returns `token` unchanged) when there is no such prefix, so
    callers can run this unconditionally as a fallback with no separate
    "did it match" branch.
    """
    match = _NAME_PREFIX_BOUNDARY.match(token)
    if match is None:
        return token
    prefix = token[: match.end() - 1]
    if len(prefix) < 2 or not prefix[0].isascii() or not prefix[0].isalpha():
        return token
    return token[match.end() :]


def _match_observed_version(token: str) -> re.Match[str] | None:
    """`_OBSERVED_VERSION.fullmatch`, with one fallback: strip a glued name
    prefix and try again. Tried second (not instead of), so an ordinary
    `1.2.3`/`v1.2.3` token — the overwhelming common case — stays on the
    direct, unambiguous path; the prefix-split fallback only ever runs once
    the direct match has already failed. Deliberately reuses
    `_OBSERVED_VERSION` itself for the retry (not a second, parallel
    pattern) so the two named capture groups (core, prerelease) every
    caller already reads by index stay exactly the same shape either way.
    """
    token = _normalize_version_token(token)
    match = _OBSERVED_VERSION.fullmatch(token)
    if match is not None:
        return match
    return _OBSERVED_VERSION.fullmatch(_strip_name_prefix(token))


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
    match = _match_observed_version(token[0])
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
    """Return the first parseable version token across ALL of `text`, normalized.

    Normalization removes one leading and one trailing quote, trailing
    punctuation, and a `version=` prefix. A glued tool name prefix is kept.

    `parse_version` only inspects the first whitespace-delimited token of a
    single line. Tools such as eza put the version on a later line; this walks
    every token so the caller can both compare and display what was found.
    """
    for token in text.split():
        normalized = _normalize_version_token(token)
        if parse_version(normalized) is not None:
            return normalized
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
    match = _match_observed_version(text.strip())
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


def urlopen_fetch(url: str, *, token: str | None = None) -> bytes:
    """Fetch raw bytes from a URL using urllib. Default Fetch implementation.

    An explicit ``token`` wins; otherwise ``GITHUB_TOKEN``/``GH_TOKEN`` is read
    from the environment. The token is sent to api.github.com only (never
    another host): the anonymous limit is 60 requests/hour, which one full-catalog
    run plus a retry exhausts.
    """
    req = urllib.request.Request(url)
    auth = (
        token if token is not None else os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    )
    if auth and urllib.parse.urlsplit(url).hostname == "api.github.com":
        req.add_header("Authorization", f"Bearer {auth}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read()


def _asset_digests_from_release(data: Mapping[str, object]) -> dict[str, str]:
    digests: dict[str, str] = {}
    assets_obj = data.get("assets")
    if not isinstance(assets_obj, list):
        return digests
    for raw_item in cast(list[object], assets_obj):
        if not isinstance(raw_item, dict):
            continue
        asset_entry = cast(dict[str, object], raw_item)
        name_obj = asset_entry.get("name")
        digest_obj = asset_entry.get("digest")
        if not isinstance(name_obj, str) or not isinstance(digest_obj, str):
            continue
        match = _SHA256_DIGEST.match(digest_obj)
        if match is None:
            continue
        digests[name_obj] = match.group(1).lower()
    return digests


def resolve_github_release(repo: str, fetch: Fetch = urlopen_fetch) -> Release:
    """Return the latest release tag and asset digests from one `/releases/latest` read."""
    try:
        raw = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionError(f"failed to resolve tag for {repo}: {exc}") from exc
    tag = str(data.get("tag_name", ""))
    if not tag:
        raise VersionError(f"no release tag for {repo}")
    return Release(tag=tag, digests=_asset_digests_from_release(data))


def resolve_github_tag(repo: str, fetch: Fetch = urlopen_fetch) -> str:
    """Return the latest release tag for owner/repo, verbatim (leading 'v' preserved)."""
    return resolve_github_release(repo, fetch).tag


def release_resolver(resolve_tag: TagResolver) -> ReleaseResolver:
    """Select the release reader for production vs test tag resolvers.

    When `resolve_tag` is the production `resolve_github_tag`, digests come from
    the same GitHub API snapshot as the tag. Any other tag resolver (a test lambda,
    a cached wrapper) still resolves tags but returns an empty digest map so digest
    verification is not silently skipped behind a non-identity tag function.
    """
    if resolve_tag is resolve_github_tag:
        return resolve_github_release
    return lambda repo: Release(resolve_tag(repo), {})
