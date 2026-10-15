"""Read-only registry drift check over downloadable install methods."""

from __future__ import annotations

import argparse
import functools
import json
import re
import tarfile
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
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
from installer.versions import Release, ReleaseResolver, resolve_github_release

__all__ = [
    "CHECKABLE_KINDS",
    "Finding",
    "Probe",
    "Release",
    "Report",
    "check_registry",
    "default_probe",
    "default_state_path",
    "format_report",
    "main",
    "state_key",
]

CHECKABLE_KINDS = ("github_release", "tarball", "app")
ALL_OS = ("debian", "arch", "fedora", "macos")
ALL_ARCH = ("amd64", "arm64")
REGISTRY = Path(__file__).with_name("registry.toml")

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


@dataclass
class Report:
    findings: tuple[Finding, ...]
    not_checkable: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        if any(f.status == "inconclusive" for f in self.findings):
            return 2
        if any(f.status == "drift" for f in self.findings):
            return 1
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


def _collect_targets(tools: Sequence[Tool], probe: Probe) -> list[_TargetIdentity]:
    grouped: dict[
        tuple[str, str, str | None, str, int, bool],
        _TargetIdentity,
    ] = {}

    for tool in tools:
        for method in tool.methods:
            if method.kind not in CHECKABLE_KINDS:
                continue
            for os_name in ALL_OS:
                for arch in ALL_ARCH:
                    platform = Platform(os=os_name, arch=arch, immutable=False, has_brew=False)
                    if not _method_applies(method, platform):
                        continue
                    try:
                        if method.kind == "app":
                            target = _resolve_app_target(method)
                            repo = None
                            tag = None
                        else:
                            ctx = ExecContext(
                                runner=_runner_never_called,
                                platform=platform,
                                resolve_tag=lambda repo: probe.release(repo).tag,
                                resolve_release=probe.release,
                            )
                            target = resolve_target(method, ctx)
                            repo = (
                                require_str(method, "repo")
                                if method.kind == "github_release"
                                else None
                            )
                            tag = probe.release(repo).tag if repo else None
                    except (ExecutorError, ValueError):
                        continue

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


def _member_present(names: list[str], member: str, strip: int) -> bool:
    want = PurePosixPath(member).parts
    for name in names:
        parts = PurePosixPath(name).parts
        if parts[:1] == (".",):
            parts = parts[1:]
        if strip and len(parts) > strip:
            parts = parts[strip:]
        elif strip:
            parts = ()
        if parts == want:
            return True
    return False


def _github_pin_mismatch(target: _TargetIdentity, probe: Probe) -> str | None:
    if target.expected_sha256 is None or target.repo is None or target.release_tag is None:
        return None
    match = _GITHUB_RELEASE_PATH.match(target.url)
    if match is None:
        return None
    repo, url_tag, _asset = match.groups()
    if repo != target.repo:
        return None
    release = probe.release(repo)
    if url_tag != release.tag:
        return None
    digest = release.digests.get(target.asset)
    if digest is None:
        return None
    if digest.lower() != target.expected_sha256.lower():
        return (
            f"pinned sha256 differs from GitHub digest for {target.asset} "
            f"on latest release {release.tag}"
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
    probe: Probe,
    checksum_text: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Return (expected hash, checksum-file hash, release digest hash)."""
    digest_hash: str | None = None
    if target.repo is not None:
        release = probe.release(target.repo)
        digest_hash = release.digests.get(target.asset)
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
    _full_verify: bool = False,
) -> Report:
    targets = _collect_targets(tools, probe)
    findings: dict[tuple[str, str, str | None, str, int, bool], Finding] = {}
    url_head: dict[str, str | BaseException] = {}
    url_download_cache: dict[str, tuple[str, dict[str, list[str] | BaseException]]] = {}

    def identity_key(t: _TargetIdentity) -> tuple[str, str, str | None, str, int, bool]:
        return (t.tool_id, t.url, t.member, t.archive, t.strip, t.raw)

    def head_once(url: str) -> str:
        if url not in url_head:
            try:
                url_head[url] = probe.head(url)
            except BaseException as exc:
                url_head[url] = exc
        result = url_head[url]
        if isinstance(result, BaseException):
            raise result
        return result

    url_wide: dict[str, Finding] = {}
    url_mode_wide: dict[tuple[str, str], Finding] = {}

    for target in targets:
        key = identity_key(target)
        pin_drift = _github_pin_mismatch(target, probe)
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
        except (URLError, TimeoutError, OSError) as exc:
            findings[key] = Finding(
                tool_id=target.tool_id,
                url=target.url,
                status="inconclusive",
                reason=str(exc),
                member=target.member,
                platforms=target.platforms,
            )
            continue

        if not _full_verify:
            findings[key] = Finding(
                tool_id=target.tool_id,
                url=target.url,
                status="ok",
                reason="ok",
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
                    probe.download(checksum_url, sidecar)
                    checksum_text = sidecar.read_text()
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
            except (URLError, TimeoutError, OSError) as exc:
                findings[key] = Finding(
                    tool_id=target.tool_id,
                    url=target.url,
                    status="inconclusive",
                    reason=str(exc),
                    member=target.member,
                    platforms=target.platforms,
                )
                continue

        expected, checksum_hash, digest_hash = _expected_hash(target, probe, checksum_text)
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

        if target.url not in url_download_cache:
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    dest = Path(tmp) / target.asset
                    probe.download(target.url, dest)
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
            except (URLError, TimeoutError, OSError) as exc:
                findings[key] = Finding(
                    tool_id=target.tool_id,
                    url=target.url,
                    status="inconclusive",
                    reason=str(exc),
                    member=target.member,
                    platforms=target.platforms,
                )
                continue
        else:
            actual_hash, listings = url_download_cache[target.url]

        if target.url in url_wide:
            findings[key] = url_wide[target.url]
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
                findings[key] = url_mode_wide[mode_key]
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
                names, target.member, target.strip
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
        )
        state[state_k] = fingerprint

    for key, finding in list(findings.items()):
        url = finding.url
        if url in url_wide:
            findings[key] = url_wide[url]
            state.pop(
                state_key(key[0], key[1], key[2], archive=key[3], strip=key[4], raw=key[5]),
                None,
            )
        mode_key = (url, key[3])
        if mode_key in url_mode_wide:
            findings[key] = url_mode_wide[mode_key]
            state.pop(
                state_key(key[0], key[1], key[2], archive=key[3], strip=key[4], raw=key[5]),
                None,
            )

    ordered = sorted(
        findings.values(),
        key=lambda f: (f.tool_id, f.url, f.member or "", f.platforms),
    )
    return Report(findings=tuple(ordered))


def format_report(report: Report, *, include_passed: bool = True) -> str:
    lines: list[str] = []
    drift = [f for f in report.findings if f.status == "drift"]
    inconclusive = [f for f in report.findings if f.status == "inconclusive"]
    if drift:
        lines.append("## Drift")
        for f in drift:
            member = f"`{f.member}` " if f.member else ""
            lines.append(
                f"- `{f.tool_id}` {member}`{f.url}` — {f.reason} ({', '.join(f.platforms)})"
            )
    if inconclusive:
        lines.append("## Inconclusive")
        for f in inconclusive:
            member = f"`{f.member}` " if f.member else ""
            lines.append(
                f"- `{f.tool_id}` {member}`{f.url}` — {f.reason} ({', '.join(f.platforms)})"
            )
    if report.not_checkable:
        lines.append("## Not checkable")
        for note in report.not_checkable:
            lines.append(f"- {note}")
    if report.notes:
        lines.append("## Notes")
        for note in report.notes:
            lines.append(f"- {note}")
    if include_passed:
        lines.append("## Passed")
        for f in report.findings:
            if f.status != "ok":
                continue
            if f.member:
                lines.append(
                    f"- `{f.tool_id}` `{f.url}` `{f.member}` (`{'`, `'.join(f.platforms)}`)"
                )
            else:
                lines.append(f"- `{f.tool_id}` `{f.url}` (`{'`, `'.join(f.platforms)}`)")
    return "\n".join(lines) + ("\n" if lines else "")


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


def default_probe() -> Probe:
    cached_release = functools.cache(resolve_github_release)

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


def main(argv: Sequence[str] | None = None, *, probe: Probe | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify registry download targets against upstream."
    )
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--state", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)
    state_path = args.state if args.state is not None else default_state_path()
    tools = load_tools(args.registry)
    state = _load_state(state_path)
    active_probe = probe if probe is not None else default_probe()
    report = check_registry(tools, active_probe, state, _full_verify=False)
    print(format_report(report), end="")
    _save_state(state_path, state)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
