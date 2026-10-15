"""Read-only registry drift check over downloadable install methods."""

from __future__ import annotations

import argparse
import copy
import functools
import http.client
import json
import os
import re
import tarfile
import tempfile
import tomllib
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Literal, cast
from urllib.error import HTTPError, URLError

from installer.atomic import atomic_write_text
from installer.checksums import expected_sha256, sha256_file
from installer.download import (
    DownloadTarget,
    ExecContext,
    pinned_url,
    resolve_target,
)
from installer.executors import ExecutorError, require_str
from installer.locations import ensure_dir
from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.run import CommandError, run_output
from installer.versions import (
    Release,
    ReleaseResolver,
    VersionError,
    is_outdated,
    resolve_github_release,
    urlopen_fetch,
)

EXIT_USAGE = 64

EditKey = Literal["verified", "version", "sha256"]

__all__ = [
    "CHECKABLE_KINDS",
    "EXIT_USAGE",
    "Finding",
    "Probe",
    "RegistryEdit",
    "RegistryWriteError",
    "Release",
    "Report",
    "UnverifiedMethod",
    "apply_registry_edits",
    "check_registry",
    "code_span",
    "default_probe",
    "DRIFT_LABEL",
    "default_state_path",
    "format_report",
    "github_token",
    "main",
    "state_key",
    "upsert_drift_issue",
]

CHECKABLE_KINDS = ("github_release", "tarball", "app")
ALL_OS = ("debian", "arch", "fedora", "macos")
ALL_ARCH = ("amd64", "arm64")
REGISTRY = Path(__file__).with_name("registry.toml")

DRIFT_LABEL = "registry-drift"

_TRANSPORT_ERRORS = (URLError, TimeoutError, OSError, http.client.HTTPException)

FindingStatus = Literal["ok", "drift", "inconclusive"]

_GITHUB_RELEASE_PATH = re.compile(
    r"^https://github\.com/([^/]+/[^/]+)/releases/download/([^/]+)/(.+)$"
)


def default_state_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "verify-registry.json"


@dataclass(frozen=True)
class Finding:
    tool_id: str
    url: str
    status: FindingStatus
    reason: str
    member: str | None = None
    platforms: tuple[str, ...] = ()
    sha256: str | None = None


@dataclass(frozen=True)
class UnverifiedMethod:
    tool_id: str
    method_index: int
    kind: str
    assets: tuple[str, ...]


@dataclass
class Report:
    findings: tuple[Finding, ...]
    not_checkable: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    blocked: str | None = None
    unverified: tuple[UnverifiedMethod, ...] = ()

    @property
    def exit_code(self) -> int:
        """Return 1 for drift (even when blocked), else 2 when blocked or inconclusive, else 0.

        Implements D-07 per Ledger L-18-05, L-18-15 and L-18-18: a whole-run outage or
        rate limit suppresses the issue only when it confirmed no drift.
        """
        if any(f.status == "drift" for f in self.findings):
            return 1
        if self.blocked is not None or any(f.status == "inconclusive" for f in self.findings):
            return 2
        return 0

    def passed_tools(self) -> tuple[str, ...]:
        by_tool: dict[str, list[Finding]] = defaultdict(list)
        for finding in self.findings:
            by_tool[finding.tool_id].append(finding)
        passed: list[str] = []
        for tool_id, items in sorted(by_tool.items()):
            if items and all(f.status == "ok" for f in items):
                passed.append(tool_id)
        return tuple(passed)


@dataclass(frozen=True)
class Probe:
    release: ReleaseResolver
    head: Callable[[str], str]
    download: Callable[[str, Path], None]


@dataclass(frozen=True)
class _TargetIdentity:
    tool_id: str
    url: str
    member: str | None
    asset: str
    archive: str
    strip: int
    raw: bool
    platforms: tuple[str, ...]
    checksum: tuple[str, str] | None
    expected_sha256: str | None
    registry_pin: str | None
    repo: str | None
    release_tag: str | None


def _runner_never_called(cmd: list[str]) -> None:
    raise RuntimeError(f"verify_registry must not invoke install commands: {cmd!r}")


def _archive_mode(method: Method) -> str:
    if method.kind == "app":
        return "zip"
    archive = method.params.get("archive")
    if archive == "zip":
        return "zip"
    if archive == "xz":
        return "xz"
    return "gz"


def _strip_default(method: Method) -> int:
    strip = method.params.get("strip")
    if isinstance(strip, int):
        return strip
    return 0


def _is_raw(method: Method) -> bool:
    return method.params.get("raw") is True


def state_key(
    tool_id: str,
    url: str,
    member: str | None,
    *,
    archive: str,
    strip: int,
    raw: bool,
) -> str:
    member_part = member or ""
    raw_flag = "true" if raw else "false"
    return f"{tool_id}|{url}#{member_part}|archive={archive}|strip={strip}|raw={raw_flag}"


def _resolve_app_target(method: Method) -> DownloadTarget:
    url = pinned_url(method)
    app = require_str(method, "app")
    cli = method.params.get("cli")
    member = f"{app}/{cli}" if isinstance(cli, str) and cli else app
    asset = PurePosixPath(url).name
    sha256_pin = method.params.get("sha256")
    pin = sha256_pin if isinstance(sha256_pin, str) and sha256_pin else None
    return DownloadTarget(url=url, member=member, asset=asset, sha256=pin)


def _method_applies(method: Method, platform: Platform) -> bool:
    if method.os and platform.os not in method.os:
        return False
    return not (method.arch and platform.arch not in method.arch)


def _not_checkable_tool_ids(tools: Sequence[Tool]) -> tuple[str, ...]:
    out: list[str] = []
    for tool in tools:
        if not any(m.kind in CHECKABLE_KINDS for m in tool.methods):
            out.append(tool.id)
    return tuple(sorted(out))


def _header_get(headers: object, name: str) -> str | None:
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        if value is not None:
            return str(value)
        value = getter(name.lower())
        if value is not None:
            return str(value)
    return None


def _is_github_rate_limit(error: HTTPError) -> bool:
    if error.code == 429:
        return True
    if error.code != 403:
        return False
    remaining = _header_get(error.headers, "X-RateLimit-Remaining")
    if remaining == "0":
        return True
    return _header_get(error.headers, "Retry-After") is not None


def _release_read_finding(tool_id: str, repo: str, exc: VersionError) -> Finding:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    cause = exc.__cause__
    if isinstance(cause, HTTPError):
        if cause.code == 404:
            return Finding(tool_id, url, "drift", "release not found")
        if _is_github_rate_limit(cause):
            return Finding(
                tool_id,
                url,
                "inconclusive",
                f"GitHub API rate limit (HTTP {cause.code})",
            )
        if cause.code == 403:
            return Finding(
                tool_id,
                url,
                "inconclusive",
                "release read forbidden (HTTP 403)",
            )
        return Finding(tool_id, url, "inconclusive", _head_error_reason(cause))
    if isinstance(cause, _TRANSPORT_ERRORS):
        return Finding(tool_id, url, "inconclusive", str(cause))
    return Finding(tool_id, url, "inconclusive", str(exc))


def _newer_stable_findings(
    tools: Sequence[Tool],
    release: ReleaseResolver,
) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    notes: list[str] = []
    for tool in tools:
        for method in tool.methods:
            if method.kind not in ("app", "tarball"):
                continue
            url_template = method.params.get("url")
            if not isinstance(url_template, str) or "{ver}" not in url_template:
                continue
            version = method.params.get("version")
            if not isinstance(version, str) or not version:
                continue
            rendered = pinned_url(method)
            match = _GITHUB_RELEASE_PATH.match(rendered)
            if match is None:
                notes.append(f"{tool.id}: newer stable: no release source")
                continue
            repo = match.group(1)
            try:
                tag = release(repo).tag
            except VersionError as exc:
                findings.append(_release_read_finding(tool.id, repo, exc))
                continue
            outdated = is_outdated(version, tag)
            if outdated is True:
                findings.append(
                    Finding(
                        tool_id=tool.id,
                        url=rendered,
                        status="drift",
                        reason=f"newer stable release {tag} (pinned {version})",
                    )
                )
            elif outdated is None:
                findings.append(
                    Finding(
                        tool_id=tool.id,
                        url=rendered,
                        status="inconclusive",
                        reason=f"latest tag {tag} cannot be compared with pin {version}",
                    )
                )
    return findings, notes


def _collect_targets(
    tools: Sequence[Tool],
    release: ReleaseResolver,
    *,
    pre_findings: list[Finding],
    unverified_assets: dict[tuple[str, int, str], set[str]],
    seen_release_errors: set[tuple[str, str]],
) -> list[_TargetIdentity]:
    grouped: dict[
        tuple[str, str, str | None, str, int, bool],
        _TargetIdentity,
    ] = {}

    for tool in tools:
        for method_index, method in enumerate(tool.methods):
            if method.kind not in CHECKABLE_KINDS:
                continue
            for os_name in ALL_OS:
                for arch in ALL_ARCH:
                    platform = Platform(os=os_name, arch=arch, immutable=False, has_brew=False)
                    if not _method_applies(method, platform):
                        continue
                    registry_pin: str | None = None
                    if method.kind in ("app", "tarball"):
                        pin_val = method.params.get("sha256")
                        if isinstance(pin_val, str) and pin_val:
                            registry_pin = pin_val.lower()
                    try:
                        if method.kind == "app":
                            target = _resolve_app_target(method)
                            repo = None
                            tag = None
                        else:
                            ctx = ExecContext(
                                runner=_runner_never_called,
                                platform=platform,
                                resolve_tag=lambda repo: release(repo).tag,
                                resolve_release=release,
                            )
                            target = resolve_target(method, ctx)
                            repo = (
                                require_str(method, "repo")
                                if method.kind == "github_release"
                                else None
                            )
                            tag = release(repo).tag if repo else None
                    except VersionError as exc:
                        if method.kind == "github_release":
                            repo = require_str(method, "repo")
                            err_key = (tool.id, repo)
                            if err_key not in seen_release_errors:
                                seen_release_errors.add(err_key)
                                pre_findings.append(_release_read_finding(tool.id, repo, exc))
                        continue
                    except ExecutorError as exc:
                        raw_url = method.params.get("url")
                        url = raw_url if isinstance(raw_url, str) and raw_url else ""
                        if not url and method.kind not in ("app", "tarball"):
                            url = f"github:{method.params.get('repo', '')}"
                        pre_findings.append(
                            Finding(
                                tool_id=tool.id,
                                url=url,
                                status="drift",
                                reason=str(exc),
                            )
                        )
                        continue

                    if target.unverified_reason or (
                        method.kind == "app"
                        and isinstance(method.params.get("url"), str)
                        and "{ver}" not in str(method.params.get("url"))
                    ):
                        key_uv = (tool.id, method_index, method.kind)
                        unverified_assets.setdefault(key_uv, set()).add(target.asset)

                    member = None if _is_raw(method) else target.member
                    key = (
                        tool.id,
                        target.url,
                        member,
                        _archive_mode(method),
                        _strip_default(method),
                        _is_raw(method),
                    )
                    plat = f"{os_name}/{arch}"
                    if key in grouped:
                        existing = grouped[key]
                        if plat not in existing.platforms:
                            grouped[key] = _TargetIdentity(
                                tool_id=existing.tool_id,
                                url=existing.url,
                                member=existing.member,
                                asset=existing.asset,
                                archive=existing.archive,
                                strip=existing.strip,
                                raw=existing.raw,
                                platforms=tuple(sorted((*existing.platforms, plat))),
                                checksum=existing.checksum,
                                expected_sha256=existing.expected_sha256,
                                registry_pin=existing.registry_pin,
                                repo=existing.repo,
                                release_tag=existing.release_tag,
                            )
                    else:
                        grouped[key] = _TargetIdentity(
                            tool_id=tool.id,
                            url=target.url,
                            member=member,
                            asset=target.asset,
                            archive=_archive_mode(method),
                            strip=_strip_default(method),
                            raw=_is_raw(method),
                            platforms=(plat,),
                            checksum=target.checksum,
                            expected_sha256=target.sha256,
                            registry_pin=registry_pin,
                            repo=repo,
                            release_tag=tag,
                        )
    return list(grouped.values())


def _head_error_reason(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    return str(exc)


def _asset_missing_reason(code: int, asset: str) -> str:
    return f"asset missing (HTTP {code}): {asset}"


def _tar_member_names(path: Path, archive: str) -> list[str]:
    if archive == "zip":
        with zipfile.ZipFile(path) as zf:
            return zf.namelist()
    mode = "r:xz" if archive == "xz" else "r:gz"
    with tarfile.open(path, mode) as tf:
        return tf.getnames()


def _member_present(names: list[str], member: str, strip: int, archive: str) -> bool:
    """Mirror `download._extract_into`: tar `--strip-components` counts `./`; zip is exact."""
    if archive == "zip":
        return member in names
    want = PurePosixPath(member).parts
    for name in names:
        if not name:
            continue
        components = name.split("/")
        if name.startswith("/") and components[0] == "":
            components = components[1:]
        if len(components) < strip + 1:
            continue
        remainder = name
        for _ in range(strip):
            slash = remainder.find("/")
            if slash < 0:
                remainder = ""
                break
            remainder = remainder[slash + 1 :]
        remainder = remainder.lstrip("/")
        if not remainder:
            continue
        if PurePosixPath(remainder).parts == want:
            return True
    return False


def _github_pin_mismatch(target: _TargetIdentity, release: ReleaseResolver) -> str | None:
    if target.registry_pin is None:
        return None
    match = _GITHUB_RELEASE_PATH.match(target.url)
    if match is None:
        return None
    repo, url_tag, _asset = match.groups()
    rel = release(repo)
    if url_tag != rel.tag:
        return None
    digest = rel.digests.get(target.asset)
    if digest is None:
        return None
    if digest.lower() != target.registry_pin.lower():
        return (
            f"pinned sha256 differs from GitHub digest for {target.asset} "
            f"on latest release {rel.tag}"
        )
    return None


def _fingerprint_for_target(
    target: _TargetIdentity,
    head_fp: str,
    checksum_hash: str | None,
    digest_hash: str | None,
) -> str:
    if checksum_hash is not None:
        return f"sha256:{checksum_hash}"
    if digest_hash is not None:
        return f"sha256:{digest_hash}"
    pin = target.expected_sha256
    if pin is not None:
        return f"sha256:{pin}|{head_fp}"
    return head_fp


def _expected_hash(
    target: _TargetIdentity,
    release: ReleaseResolver,
    checksum_text: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Return (expected hash, checksum-file hash, release digest hash)."""
    digest_hash: str | None = None
    if target.repo is not None:
        rel = release(target.repo)
        digest_hash = rel.digests.get(target.asset)
        if digest_hash is not None:
            digest_hash = digest_hash.lower()

    checksum_hash: str | None = None
    if checksum_text is not None:
        checksum_hash = expected_sha256(checksum_text, target.asset)
        if checksum_hash is None:
            return None, None, digest_hash
        checksum_hash = checksum_hash.lower()
        if digest_hash is not None and checksum_hash != digest_hash:
            return "__disagree__", checksum_hash, digest_hash

    if checksum_hash is not None:
        return checksum_hash, checksum_hash, digest_hash
    if target.expected_sha256 is not None:
        return target.expected_sha256.lower(), None, digest_hash
    if digest_hash is not None:
        return digest_hash, None, digest_hash
    return None, None, digest_hash


def check_registry(
    tools: Sequence[Tool],
    probe: Probe,
    state: MutableMapping[str, str],
    *,
    on_verified: Callable[[Mapping[str, str]], None] | None = None,
) -> Report:
    not_checkable = _not_checkable_tool_ids(tools)
    pre_findings: list[Finding] = []
    seen_release_errors: set[tuple[str, str]] = set()
    unverified_assets: dict[tuple[str, int, str], set[str]] = {}

    release_reads_attempted = 0
    release_reads_http = 0
    rate_limit_code: int | None = None
    head_attempted = 0
    head_http = 0
    download_attempted = 0
    download_http = 0

    release_memo: dict[str, Release | VersionError] = {}

    def tracked_release(repo: str) -> Release:
        nonlocal release_reads_attempted, release_reads_http, rate_limit_code
        if repo in release_memo:
            stored = release_memo[repo]
            if isinstance(stored, VersionError):
                raise stored
            return stored
        release_reads_attempted += 1
        try:
            rel = probe.release(repo)
            release_reads_http += 1
            release_memo[repo] = rel
            return rel
        except VersionError as exc:
            cause = exc.__cause__
            if isinstance(cause, HTTPError):
                release_reads_http += 1
                if _is_github_rate_limit(cause):
                    rate_limit_code = cause.code
            release_memo[repo] = exc
            raise

    targets = _collect_targets(
        tools,
        tracked_release,
        pre_findings=pre_findings,
        unverified_assets=unverified_assets,
        seen_release_errors=seen_release_errors,
    )
    newer_findings, newer_notes = _newer_stable_findings(tools, tracked_release)

    findings: dict[tuple[str, str, str | None, str, int, bool], Finding] = {}
    url_head: dict[str, str | BaseException] = {}
    url_download_cache: dict[str, tuple[str, dict[str, list[str] | BaseException]]] = {}

    def identity_key(t: _TargetIdentity) -> tuple[str, str, str | None, str, int, bool]:
        return (t.tool_id, t.url, t.member, t.archive, t.strip, t.raw)

    def tracked_download(url: str, dest: Path) -> None:
        nonlocal download_attempted, download_http
        download_attempted += 1
        try:
            probe.download(url, dest)
            download_http += 1
        except HTTPError:
            download_http += 1
            raise

    def head_once(url: str) -> str:
        nonlocal head_attempted, head_http
        if url not in url_head:
            head_attempted += 1
            try:
                url_head[url] = probe.head(url)
                head_http += 1
            except HTTPError as exc:
                head_http += 1
                url_head[url] = exc
            except _TRANSPORT_ERRORS as exc:
                url_head[url] = exc
        result = url_head[url]
        if isinstance(result, BaseException):
            raise result
        return result

    url_wide: dict[str, Finding] = {}
    url_mode_wide: dict[tuple[str, str], Finding] = {}

    for target in targets:
        key = identity_key(target)
        try:
            pin_drift = _github_pin_mismatch(target, tracked_release)
        except VersionError:
            pin_drift = None
        if pin_drift is not None:
            findings[key] = Finding(
                tool_id=target.tool_id,
                url=target.url,
                status="drift",
                reason=pin_drift,
                member=target.member,
                platforms=target.platforms,
            )
            continue

        try:
            head_fp = head_once(target.url)
        except HTTPError as exc:
            if exc.code in (404, 410):
                findings[key] = Finding(
                    tool_id=target.tool_id,
                    url=target.url,
                    status="drift",
                    reason=_asset_missing_reason(exc.code, target.asset),
                    member=target.member,
                    platforms=target.platforms,
                )
            else:
                findings[key] = Finding(
                    tool_id=target.tool_id,
                    url=target.url,
                    status="inconclusive",
                    reason=_head_error_reason(exc),
                    member=target.member,
                    platforms=target.platforms,
                )
            continue
        except _TRANSPORT_ERRORS as exc:
            findings[key] = Finding(
                tool_id=target.tool_id,
                url=target.url,
                status="inconclusive",
                reason=str(exc),
                member=target.member,
                platforms=target.platforms,
            )
            continue

        checksum_text: str | None = None
        if target.checksum is not None:
            checksum_url, _name = target.checksum
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    sidecar = Path(tmp) / "checksum"
                    tracked_download(checksum_url, sidecar)
                    checksum_text = sidecar.read_text(encoding="utf-8", errors="replace")
            except HTTPError as exc:
                if exc.code in (404, 410):
                    findings[key] = Finding(
                        tool_id=target.tool_id,
                        url=target.url,
                        status="drift",
                        reason=_asset_missing_reason(exc.code, PurePosixPath(checksum_url).name),
                        member=target.member,
                        platforms=target.platforms,
                    )
                else:
                    findings[key] = Finding(
                        tool_id=target.tool_id,
                        url=target.url,
                        status="inconclusive",
                        reason=_head_error_reason(exc),
                        member=target.member,
                        platforms=target.platforms,
                    )
                continue
            except _TRANSPORT_ERRORS as exc:
                findings[key] = Finding(
                    tool_id=target.tool_id,
                    url=target.url,
                    status="inconclusive",
                    reason=str(exc),
                    member=target.member,
                    platforms=target.platforms,
                )
                continue

        expected, checksum_hash, digest_hash = _expected_hash(
            target, tracked_release, checksum_text
        )
        if expected == "__disagree__":
            findings[key] = Finding(
                tool_id=target.tool_id,
                url=target.url,
                status="drift",
                reason="checksum file disagrees with the GitHub digest",
                member=target.member,
                platforms=target.platforms,
            )
            continue
        if checksum_text is not None and expected is None:
            findings[key] = Finding(
                tool_id=target.tool_id,
                url=target.url,
                status="drift",
                reason=f"checksum file missing entry for {target.asset}",
                member=target.member,
                platforms=target.platforms,
            )
            continue

        fingerprint = _fingerprint_for_target(target, head_fp, checksum_hash, digest_hash)
        state_k = state_key(
            target.tool_id,
            target.url,
            target.member,
            archive=target.archive,
            strip=target.strip,
            raw=target.raw,
        )
        if state.get(state_k) == fingerprint:
            findings[key] = Finding(
                tool_id=target.tool_id,
                url=target.url,
                status="ok",
                reason="ok",
                member=target.member,
                platforms=target.platforms,
            )
            continue

        if target.url in url_wide:
            findings[key] = replace(
                url_wide[target.url],
                tool_id=target.tool_id,
                member=target.member,
                platforms=target.platforms,
                sha256=None,
            )
            continue

        if target.url not in url_download_cache:
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    dest = Path(tmp) / target.asset
                    tracked_download(target.url, dest)
                    actual_hash = sha256_file(dest)
                    listings: dict[str, list[str] | BaseException] = {}
                    if not target.raw:
                        try:
                            listings[target.archive] = _tar_member_names(dest, target.archive)
                        except (
                            tarfile.TarError,
                            EOFError,
                            zipfile.BadZipFile,
                        ) as exc:
                            listings[target.archive] = exc
                    url_download_cache[target.url] = (actual_hash, listings)
            except HTTPError as exc:
                if exc.code in (404, 410):
                    drift = Finding(
                        tool_id=target.tool_id,
                        url=target.url,
                        status="drift",
                        reason=_asset_missing_reason(exc.code, target.asset),
                        member=target.member,
                        platforms=target.platforms,
                    )
                    url_wide[target.url] = drift
                    findings[key] = drift
                else:
                    findings[key] = Finding(
                        tool_id=target.tool_id,
                        url=target.url,
                        status="inconclusive",
                        reason=_head_error_reason(exc),
                        member=target.member,
                        platforms=target.platforms,
                    )
                continue
            except _TRANSPORT_ERRORS as exc:
                findings[key] = Finding(
                    tool_id=target.tool_id,
                    url=target.url,
                    status="inconclusive",
                    reason=str(exc),
                    member=target.member,
                    platforms=target.platforms,
                )
                continue

        actual_hash, listings = url_download_cache[target.url]
        if expected is not None and actual_hash.lower() != expected.lower():
            drift = Finding(
                tool_id=target.tool_id,
                url=target.url,
                status="drift",
                reason="checksum mismatch",
                member=target.member,
                platforms=target.platforms,
            )
            url_wide[target.url] = drift
            findings[key] = drift
            continue

        if not target.raw:
            listing = listings.get(target.archive)
            mode_key = (target.url, target.archive)
            if mode_key in url_mode_wide:
                findings[key] = replace(
                    url_mode_wide[mode_key],
                    tool_id=target.tool_id,
                    member=target.member,
                    platforms=target.platforms,
                    sha256=None,
                )
                continue
            if isinstance(listing, BaseException):
                drift = Finding(
                    tool_id=target.tool_id,
                    url=target.url,
                    status="drift",
                    reason=(f"archive unreadable as {target.archive}: {target.asset} ({listing})"),
                    member=target.member,
                    platforms=target.platforms,
                )
                url_mode_wide[mode_key] = drift
                findings[key] = drift
                continue
            names = listing if isinstance(listing, list) else []
            if target.member is not None and not _member_present(
                names, target.member, target.strip, target.archive
            ):
                findings[key] = Finding(
                    tool_id=target.tool_id,
                    url=target.url,
                    status="drift",
                    reason=f"member {target.member} missing from {target.asset}",
                    member=target.member,
                    platforms=target.platforms,
                )
                continue

        findings[key] = Finding(
            tool_id=target.tool_id,
            url=target.url,
            status="ok",
            reason="ok",
            member=target.member,
            platforms=target.platforms,
            sha256=actual_hash.lower(),
        )
        state[state_k] = fingerprint
        if on_verified is not None:
            on_verified(state)

    for key, finding in list(findings.items()):
        url = finding.url
        if url in url_wide:
            findings[key] = replace(
                url_wide[url],
                tool_id=finding.tool_id,
                member=finding.member,
                platforms=finding.platforms,
                sha256=None,
            )
            state.pop(
                state_key(key[0], key[1], key[2], archive=key[3], strip=key[4], raw=key[5]),
                None,
            )
        mode_key = (url, key[3])
        if mode_key in url_mode_wide:
            findings[key] = replace(
                url_mode_wide[mode_key],
                tool_id=finding.tool_id,
                member=finding.member,
                platforms=finding.platforms,
                sha256=None,
            )
            state.pop(
                state_key(key[0], key[1], key[2], archive=key[3], strip=key[4], raw=key[5]),
                None,
            )

    merged: dict[tuple[str, str, str, str], Finding] = {}
    for finding in (*pre_findings, *newer_findings, *findings.values()):
        key = (finding.tool_id, finding.url, finding.member or "", finding.reason)
        merged[key] = finding
    ordered = sorted(
        merged.values(),
        key=lambda f: (f.tool_id, f.url, f.member or "", f.platforms),
    )

    blocked: str | None = None
    if rate_limit_code is not None:
        blocked = f"GitHub API rate limit (HTTP {rate_limit_code})"
    elif release_reads_attempted > 0 and release_reads_http == 0:
        blocked = "no GitHub release read got an HTTP response"
    elif (
        release_reads_attempted == 0
        and (head_attempted + download_attempted) > 0
        and (head_http + download_http) == 0
    ):
        blocked = "no HEAD or download request got an HTTP response"

    unverified = tuple(
        UnverifiedMethod(tool_id, idx, kind, tuple(sorted(names)))
        for (tool_id, idx, kind), names in sorted(unverified_assets.items())
    )

    return Report(
        findings=tuple(ordered),
        not_checkable=not_checkable,
        notes=tuple(newer_notes),
        blocked=blocked,
        unverified=unverified,
    )


class RegistryWriteError(RuntimeError):
    """Raised when a registry edit would change more than the intended keys."""


@dataclass(frozen=True)
class RegistryEdit:
    tool_id: str
    method_index: int | None
    key: EditKey
    value: str


_SUBTABLE_HEADER_RE = re.compile(r"^\[\[tool\.method\]\]|^\[tool\.")


def _is_subtable_header(line: str) -> bool:
    stripped = line.strip()
    if stripped == "[[tool]]":
        return False
    if _SUBTABLE_HEADER_RE.match(stripped):
        return True
    return stripped.startswith("[[") and stripped != "[[tool]]"


def _parse_edit_value(literal: str) -> object:
    parsed = tomllib.loads(f"v = {literal}")
    return parsed["v"]


def _apply_edits_to_document(
    doc: dict[str, object], edits: Sequence[RegistryEdit]
) -> dict[str, object]:
    out = copy.deepcopy(doc)
    tools = out.get("tool")
    if not isinstance(tools, list):
        raise RegistryWriteError("missing tool table")
    tool_rows = cast(list[object], tools)
    for edit in edits:
        tool_entry: dict[str, object] | None = None
        for entry in tool_rows:
            if not isinstance(entry, dict):
                continue
            row = cast(dict[str, object], entry)
            if row.get("id") == edit.tool_id:
                tool_entry = row
                break
        if tool_entry is None:
            raise RegistryWriteError(f"unknown tool {edit.tool_id!r}")
        parsed_value = _parse_edit_value(edit.value)
        if edit.method_index is None:
            if edit.key != "verified":
                raise RegistryWriteError(f"unsupported tool-level key {edit.key!r}")
            tool_entry["verified"] = parsed_value
            continue
        methods_raw = tool_entry.get("method")
        if not isinstance(methods_raw, list):
            raise RegistryWriteError("method index out of range")
        methods = cast(list[object], methods_raw)
        if edit.method_index >= len(methods):
            raise RegistryWriteError("method index out of range")
        method_entry = methods[edit.method_index]
        if not isinstance(method_entry, dict):
            raise RegistryWriteError("invalid method table")
        cast(dict[str, object], method_entry)[edit.key] = parsed_value
    return out


def _tool_blocks(lines: list[str]) -> list[tuple[int, int]]:
    starts = [index for index, line in enumerate(lines) if line.strip() == "[[tool]]"]
    blocks: list[tuple[int, int]] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        blocks.append((start, end))
    return blocks


def _tool_id_in_block(lines: list[str], start: int, end: int) -> str | None:
    index = start + 1
    while index < end:
        line = lines[index]
        if _is_subtable_header(line):
            break
        if line.lstrip().startswith("#"):
            index += 1
            continue
        match = re.match(r'^id\s*=\s*"([^"]+)"\s*$', line)
        if match:
            return match.group(1)
        index += 1
    return None


def _method_blocks(lines: list[str], tool_start: int, tool_end: int) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    index = tool_start + 1
    while index < tool_end:
        if lines[index].strip() == "[[tool.method]]":
            method_start = index
            index += 1
            while index < tool_end and not _is_subtable_header(lines[index]):
                index += 1
            blocks.append((method_start, index))
        else:
            index += 1
    return blocks


def _region_for_edit(lines: list[str], edit: RegistryEdit) -> tuple[int, int]:
    for tool_start, tool_end in _tool_blocks(lines):
        if _tool_id_in_block(lines, tool_start, tool_end) != edit.tool_id:
            continue
        if edit.method_index is None:
            region_start = tool_start + 1
            region_end = tool_end
            for index in range(tool_start + 1, tool_end):
                if _is_subtable_header(lines[index]):
                    region_end = index
                    break
            return region_start, region_end
        methods = _method_blocks(lines, tool_start, tool_end)
        if edit.method_index >= len(methods):
            raise RegistryWriteError("method index out of range")
        return methods[edit.method_index]
    raise RegistryWriteError(f"unknown tool {edit.tool_id!r}")


def _is_data_line(line: str, key: str) -> bool:
    if line.lstrip().startswith("#"):
        return False
    return line.startswith(f"{key} = ")


def _apply_one_edit(lines: list[str], edit: RegistryEdit) -> None:
    region_start, region_end = _region_for_edit(lines, edit)
    key = edit.key
    replacement = f"{key} = {edit.value}"
    for index in range(region_start, region_end):
        if _is_data_line(lines[index], key):
            lines[index] = replacement
            return
    anchor = "tier = " if edit.method_index is None else "url = "
    for index in range(region_start, region_end):
        if lines[index].lstrip().startswith("#"):
            continue
        if lines[index].startswith(anchor):
            lines.insert(index + 1, replacement)
            return
    raise RegistryWriteError(f"missing anchor {anchor!r} for {edit.tool_id}")


def apply_registry_edits(text: str, edits: Sequence[RegistryEdit]) -> str:
    if not edits:
        return text
    original_doc = tomllib.loads(text)
    expected_doc = _apply_edits_to_document(original_doc, edits)
    lines = text.splitlines()
    for edit in edits:
        _apply_one_edit(lines, edit)
    new_text = "\n".join(lines)
    if text.endswith("\n"):
        new_text += "\n"
    try:
        new_doc = tomllib.loads(new_text)
    except tomllib.TOMLDecodeError as exc:
        raise RegistryWriteError("unintended change") from exc
    if new_doc != expected_doc:
        raise RegistryWriteError("unintended change")
    return new_text


_NEWER_STABLE_RE = re.compile(r"^newer stable release (\S+) \(pinned")


def _is_pinned_method(method: Method) -> bool:
    if method.kind not in ("app", "tarball"):
        return False
    url = method.params.get("url")
    if not isinstance(url, str) or "{ver}" not in url:
        return False
    version = method.params.get("version")
    sha256 = method.params.get("sha256")
    return isinstance(version, str) and bool(version) and isinstance(sha256, str) and bool(sha256)


def _pinned_method_entries(tool: Tool) -> list[tuple[int, Method]]:
    return [
        (index, method) for index, method in enumerate(tool.methods) if _is_pinned_method(method)
    ]


def _pinned_version(tool: Tool) -> str:
    for _index, method in _pinned_method_entries(tool):
        version = method.params.get("version")
        if isinstance(version, str) and version:
            return version
    return ""


def _method_at_version(method: Method, version: str) -> Method:
    params = dict(method.params)
    params["version"] = version
    return Method(kind=method.kind, os=method.os, arch=method.arch, params=params)


def _tag_to_candidate_version(tag: str) -> str:
    if tag.startswith(("v", "V")):
        return tag[1:]
    return tag


def _old_pinned_urls(tool: Tool) -> set[str]:
    return {pinned_url(method) for _index, method in _pinned_method_entries(tool)}


def _auto_bump_candidate(
    tool_id: str, findings: Sequence[Finding]
) -> tuple[str | None, str | None, str | None]:
    tags: list[str] = []
    url_by_tag: dict[str, str] = {}
    for finding in findings:
        if finding.tool_id != tool_id or finding.status != "drift":
            continue
        match = _NEWER_STABLE_RE.match(finding.reason)
        if match is None:
            continue
        tag = match.group(1)
        tags.append(tag)
        url_by_tag[tag] = finding.url
    if not tags:
        return None, None, None
    versions = {_tag_to_candidate_version(tag): tag for tag in tags}
    if len(versions) != 1:
        first = _tag_to_candidate_version(tags[0])
        return first, url_by_tag[tags[0]], "pinned methods report different newer tags"
    return next(iter(versions)), None, None


def _candidate_tool_copy(tool: Tool, candidate: str, release: ReleaseResolver) -> Tool:
    methods: list[Method] = []
    for _index, method in _pinned_method_entries(tool):
        params = dict(method.params)
        params["version"] = candidate
        probe = _method_at_version(method, candidate)
        rendered = pinned_url(probe)
        match = _GITHUB_RELEASE_PATH.match(rendered)
        if match is not None:
            repo = match.group(1)
            asset = PurePosixPath(rendered).name
            digest: str | None = None
            try:
                digest = release(repo).digests.get(asset)
            except VersionError:
                digest = None
            if digest is not None:
                params["sha256"] = digest.lower()
            else:
                params.pop("sha256", None)
        else:
            params.pop("sha256", None)
        methods.append(Method(kind=method.kind, os=method.os, arch=method.arch, params=params))
    return replace(tool, methods=methods)


def _first_failed_finding(report: Report) -> tuple[str, str]:
    for finding in report.findings:
        if finding.status != "ok":
            return finding.url, finding.reason
    return "", "candidate check failed"


def _pinned_finding_member(method: Method) -> str | None:
    if method.kind == "app":
        app = method.params.get("app")
        if not isinstance(app, str) or not app:
            return None
        cli = method.params.get("cli")
        if isinstance(cli, str) and cli:
            return f"{app}/{cli}"
        return app
    member = method.params.get("member")
    return member if isinstance(member, str) else None


def _finding_for_pinned_method(
    report: Report, tool_id: str, method: Method, candidate: str
) -> Finding | None:
    url = pinned_url(_method_at_version(method, candidate))
    member_str = _pinned_finding_member(method)
    for finding in report.findings:
        if finding.tool_id != tool_id or finding.url != url:
            continue
        if finding.member == member_str:
            return finding
    return None


@dataclass(frozen=True)
class _BumpResult:
    tool_id: str
    applied: bool
    old_version: str
    new_version: str
    fail_url: str | None = None
    fail_reason: str | None = None
    candidate_findings: tuple[Finding, ...] = ()
    bump_edits: tuple[RegistryEdit, ...] = ()


def _build_bump_edits(
    tool: Tool, candidate: str, candidate_report: Report
) -> tuple[RegistryEdit, ...]:
    edits: list[RegistryEdit] = []
    for index, method in _pinned_method_entries(tool):
        finding = _finding_for_pinned_method(candidate_report, tool.id, method, candidate)
        if finding is None or finding.sha256 is None:
            raise RegistryWriteError(f"missing candidate hash for {tool.id}")
        edits.append(RegistryEdit(tool.id, index, "version", f'"{candidate}"'))
        edits.append(RegistryEdit(tool.id, index, "sha256", f'"{finding.sha256}"'))
    return tuple(edits)


def _finalize_report_after_bumps(
    initial: Report, tools_by_id: dict[str, Tool], bumps: Sequence[_BumpResult]
) -> Report:
    findings: list[Finding] = list(initial.findings)
    notes: list[str] = list(initial.notes)
    for bump in bumps:
        tool = tools_by_id[bump.tool_id]
        if bump.applied:
            old_urls = _old_pinned_urls(tool)
            findings = [
                finding
                for finding in findings
                if not (finding.tool_id == bump.tool_id and finding.url in old_urls)
            ]
            findings.extend(bump.candidate_findings)
            notes.append(f"bumped {bump.tool_id} {bump.old_version} -> {bump.new_version}")
            continue
        fail_url = bump.fail_url
        if fail_url is None:
            old_urls = _old_pinned_urls(tool)
            fail_url = next(iter(old_urls), "")
        reason = bump.fail_reason or "candidate check failed"
        findings.append(
            Finding(
                tool_id=bump.tool_id,
                url=fail_url,
                status="drift",
                reason=f"bump to {bump.new_version} not applied: {reason}",
            )
        )
    merged: dict[tuple[str, str, str, str], Finding] = {}
    for finding in findings:
        key = (finding.tool_id, finding.url, finding.member or "", finding.reason)
        merged[key] = finding
    ordered = sorted(
        merged.values(),
        key=lambda item: (item.tool_id, item.url, item.member or "", item.platforms),
    )
    return Report(
        findings=tuple(ordered),
        not_checkable=initial.not_checkable,
        notes=tuple(notes),
        blocked=initial.blocked,
        unverified=initial.unverified,
    )


def _parse_explicit_candidates(
    raw: Sequence[str], tools: Sequence[Tool]
) -> tuple[dict[str, str], str | None]:
    tools_by_id = {tool.id: tool for tool in tools}
    out: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            return {}, f"invalid --candidate {item!r}: expected <tool_id>=<version>"
        tool_id, version = item.split("=", 1)
        if not tool_id or not version:
            return {}, f"invalid --candidate {item!r}: expected <tool_id>=<version>"
        tool = tools_by_id.get(tool_id)
        if tool is None:
            return {}, f"unknown tool {tool_id!r} for --candidate"
        if not _pinned_method_entries(tool):
            return {}, f"tool {tool_id!r} has no pinned methods for --candidate"
        out[tool_id] = version
    return out, None


def _plan_bumps(
    tools: Sequence[Tool],
    initial: Report,
    probe: Probe,
    explicit: Mapping[str, str],
) -> list[_BumpResult]:
    tools_by_id = {tool.id: tool for tool in tools}
    results: list[_BumpResult] = []
    candidate_versions: dict[str, str] = dict(explicit)
    auto_failures: list[tuple[str, str, str, str, str]] = []
    for tool in tools:
        if tool.id in candidate_versions:
            continue
        version, fail_url, fail_reason = _auto_bump_candidate(tool.id, initial.findings)
        if fail_reason is not None:
            auto_failures.append(
                (
                    tool.id,
                    _pinned_version(tool),
                    version or "",
                    fail_url or "",
                    fail_reason,
                )
            )
            continue
        if version is not None:
            candidate_versions[tool.id] = version
    for tool_id, old_version, new_version, fail_url, fail_reason in auto_failures:
        results.append(
            _BumpResult(
                tool_id=tool_id,
                applied=False,
                old_version=old_version,
                new_version=new_version,
                fail_url=fail_url,
                fail_reason=fail_reason,
            )
        )
    for tool_id, candidate in sorted(candidate_versions.items()):
        tool = tools_by_id[tool_id]
        old_version = _pinned_version(tool)
        pinned_copy = _candidate_tool_copy(tool, candidate, probe.release)
        candidate_report = check_registry([pinned_copy], probe, {})
        if not all(finding.status == "ok" for finding in candidate_report.findings):
            fail_url, fail_reason = _first_failed_finding(candidate_report)
            results.append(
                _BumpResult(
                    tool_id=tool_id,
                    applied=False,
                    old_version=old_version,
                    new_version=candidate,
                    fail_url=fail_url,
                    fail_reason=fail_reason,
                )
            )
            continue
        bump_edits = _build_bump_edits(tool, candidate, candidate_report)
        results.append(
            _BumpResult(
                tool_id=tool_id,
                applied=True,
                old_version=old_version,
                new_version=candidate,
                candidate_findings=candidate_report.findings,
                bump_edits=bump_edits,
            )
        )
    return results


def _registry_edits_for_write(
    report: Report, bumps: Sequence[_BumpResult], write_day: date
) -> list[RegistryEdit]:
    edits: list[RegistryEdit] = []
    for bump in bumps:
        if bump.applied:
            edits.extend(bump.bump_edits)
    for tool_id in report.passed_tools():
        edits.append(RegistryEdit(tool_id, None, "verified", write_day.isoformat()))
    return edits


def code_span(value: str) -> str:
    """Return a CommonMark-safe code span for arbitrary upstream text."""
    cleaned = "".join(" " if unicodedata.category(ch).startswith("C") else ch for ch in value)
    max_run = 0
    run = 0
    for ch in cleaned:
        if ch == "`":
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    fence = "`" * (max_run + 1)
    inner = cleaned
    if cleaned.startswith("`") or cleaned.endswith("`"):
        inner = f" {inner} "
    return f"{fence}{inner}{fence}"


def format_report(report: Report, *, include_passed: bool = True) -> str:
    lines: list[str] = []
    if report.blocked:
        lines.append(f"blocked: {code_span(report.blocked)}")
    drift = [f for f in report.findings if f.status == "drift"]
    inconclusive = [f for f in report.findings if f.status == "inconclusive"]
    if report.blocked and drift:
        lines.append("note: the run was otherwise blocked; the drift listed below was confirmed")
    if drift:
        lines.append("## Drift")
        for f in drift:
            member = f"{code_span(f.member)} " if f.member else ""
            platforms = ", ".join(code_span(p) for p in f.platforms)
            lines.append(
                f"- {code_span(f.tool_id)} {member}{code_span(f.url)} — "
                f"{code_span(f.reason)} ({platforms})"
            )
    if inconclusive:
        lines.append("## Inconclusive")
        for f in inconclusive:
            member = f"{code_span(f.member)} " if f.member else ""
            platforms = ", ".join(code_span(p) for p in f.platforms)
            lines.append(
                f"- {code_span(f.tool_id)} {member}{code_span(f.url)} — "
                f"{code_span(f.reason)} ({platforms})"
            )
    lines.append("Unverified at install (no checksum file, pinned sha256 or GitHub digest):")
    if report.unverified:
        for entry in sorted(report.unverified, key=lambda u: (u.tool_id, u.method_index)):
            assets = ", ".join(code_span(name) for name in entry.assets)
            lines.append(
                f"- {code_span(entry.tool_id)} method {entry.method_index} ({entry.kind}): {assets}"
            )
    else:
        lines.append("- none")
    if report.not_checkable:
        lines.append("## Not checkable")
        for note in report.not_checkable:
            lines.append(f"- {code_span(note)}")
    if report.notes:
        lines.append("## Notes")
        for note in report.notes:
            lines.append(f"- {code_span(note)}")
    if include_passed:
        lines.append("## Passed")
        for f in report.findings:
            if f.status != "ok":
                continue
            platforms = ", ".join(code_span(p) for p in f.platforms)
            if f.member:
                lines.append(
                    f"- {code_span(f.tool_id)} {code_span(f.url)} {code_span(f.member)} "
                    f"({platforms})"
                )
            else:
                lines.append(f"- {code_span(f.tool_id)} {code_span(f.url)} ({platforms})")
    return "\n".join(lines) + ("\n" if lines else "")


def upsert_drift_issue(body: str, gh: Callable[[list[str]], str]) -> None:
    gh(
        [
            "gh",
            "label",
            "create",
            DRIFT_LABEL,
            "--force",
            "--description",
            "Upstream drift found by make verify-registry",
        ]
    )
    raw = gh(
        [
            "gh",
            "issue",
            "list",
            "--label",
            DRIFT_LABEL,
            "--state",
            "open",
            "--json",
            "number",
            "--limit",
            "1",
        ]
    )
    items = json.loads(raw)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".md") as tmp:
        tmp.write(body)
        body_path = tmp.name
    try:
        if items:
            number = items[0]["number"]
            gh(["gh", "issue", "edit", str(number), "--body-file", body_path])
        else:
            gh(
                [
                    "gh",
                    "issue",
                    "create",
                    "--title",
                    "Registry drift detected by verify-registry",
                    "--label",
                    DRIFT_LABEL,
                    "--body-file",
                    body_path,
                ]
            )
    finally:
        Path(body_path).unlink(missing_ok=True)


def _load_state(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in cast(dict[object, object], raw).items():
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out


def _save_state(path: Path, state: Mapping[str, str]) -> None:
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(dict(sorted(state.items())), indent=2) + "\n")


def github_token(gh: Callable[[list[str]], str]) -> str | None:
    """Return a GitHub API token from the environment or ``gh auth token``."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    try:
        text = gh(["gh", "auth", "token"]).strip()
    except CommandError:
        return None
    return text or None


def default_probe(token: str | None = None) -> Probe:
    fetch = functools.partial(urlopen_fetch, token=token)
    cached_release = functools.cache(functools.partial(resolve_github_release, fetch=fetch))

    def head(url: str) -> str:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=20) as resp:
            etag = resp.headers.get("ETag")
            if etag:
                return f"etag:{etag}"
            lm = resp.headers.get("Last-Modified", "")
            length = resp.headers.get("Content-Length", "")
            return f"lm:{lm}|len:{length}"

    def download(url: str, dest: Path) -> None:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=20) as resp, dest.open("wb") as handle:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)

    return Probe(release=cached_release, head=head, download=download)


def main(
    argv: Sequence[str] | None = None,
    *,
    probe: Probe | None = None,
    gh: Callable[[list[str]], str] | None = None,
    today: date | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Verify registry download targets against upstream."
    )
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write verified dates for passing tools (maintainer only).",
    )
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        metavar="TOOL=VERSION",
        help="Bump a pinned tool to an explicit candidate version (repeatable).",
    )
    parser.add_argument(
        "--issue",
        action="store_true",
        help=("Upsert one drift issue labelled registry-drift (used by the weekly workflow)."),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    write_day = today if today is not None else date.today()
    state_path = args.state if args.state is not None else default_state_path()
    tools = load_tools(args.registry)
    state = _load_state(state_path)
    gh_runner = gh if gh is not None else functools.partial(run_output, timeout=60)
    if probe is None:
        token = github_token(gh_runner)
        if token is None:
            import sys

            print(
                "note: unauthenticated GitHub API (60 requests/hour); "
                "run gh auth login or set GH_TOKEN",
                file=sys.stderr,
            )
        active_probe = default_probe(token)
    else:
        active_probe = probe
    import sys

    def _persist_state(current: Mapping[str, str]) -> None:
        _save_state(state_path, current)

    initial_report = check_registry(tools, active_probe, state, on_verified=_persist_state)
    report = initial_report
    if args.candidate:
        explicit, err = _parse_explicit_candidates(args.candidate, tools)
        if err is not None:
            print(err, file=sys.stderr)
            return EXIT_USAGE
    else:
        explicit = {}
    if args.write:
        bumps = _plan_bumps(tools, initial_report, active_probe, explicit)
        tools_by_id = {tool.id: tool for tool in tools}
        report = _finalize_report_after_bumps(initial_report, tools_by_id, bumps)
        registry_text = args.registry.read_text()
        edits = _registry_edits_for_write(report, bumps, write_day)
        if edits:
            try:
                updated = apply_registry_edits(registry_text, edits)
            except RegistryWriteError as exc:
                print(str(exc), file=sys.stderr)
                return EXIT_USAGE
            atomic_write_text(args.registry, updated)
            for tool_id in report.passed_tools():
                print(f"dated {tool_id}", file=sys.stderr)
    elif explicit:
        print("--candidate requires --write", file=sys.stderr)
        return EXIT_USAGE
    exit_code = report.exit_code
    if args.issue and report.exit_code == 1:
        try:
            upsert_drift_issue(format_report(report, include_passed=False), gh_runner)
        except CommandError as exc:
            print(str(exc), file=sys.stderr)
            exit_code = 2
    print(format_report(report), end="")
    _save_state(state_path, state)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
