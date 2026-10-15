"""Offline tests for installer.verify_registry (registry drift guard)."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import date
from email.message import Message
from pathlib import Path
from shutil import copyfile
from urllib.error import HTTPError, URLError

import pytest

from installer.model import load_tools
from installer.run import CommandError
from installer.verify_registry import (
    EXIT_USAGE,
    Finding,
    Probe,
    RegistryEdit,
    RegistryWriteError,
    Release,
    Report,
    apply_registry_edits,
    check_registry,
    code_span,
    format_report,
    main,
    state_key,
)
from installer.versions import VersionError, urlopen_fetch

_REPO = "Wilfred/difftastic"
_TAG = "0.71.0"


def _release(
    tag: str = _TAG,
    assets: dict[str, str] | None = None,
) -> Release:
    digests = assets or {}
    return Release(tag=tag, digests=digests)


def _difft_tar_bytes() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = b"x"
        info = tarfile.TarInfo("difft")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _write_difft_tar(dest: Path) -> None:
    dest.write_bytes(_difft_tar_bytes())


def _canned_difftastic_assets() -> dict[str, str]:
    digest = hashlib.sha256(_difft_tar_bytes()).hexdigest()
    return {
        f"difft-{_TAG}-x86_64-unknown-linux-gnu.tar.gz": digest,
        f"difft-{_TAG}-aarch64-unknown-linux-gnu.tar.gz": digest,
        f"difft-{_TAG}-x86_64-apple-darwin.tar.gz": digest,
        f"difft-{_TAG}-aarch64-apple-darwin.tar.gz": digest,
    }


def _difftastic_registry(
    tmp_path: Path,
    *,
    prefix_template: bool,
    linux_os: list[str] | None = None,
    seed_verified: bool = True,
) -> Path:
    linux_asset = (
        "difft-{arch.machine}-unknown-linux-gnu.tar.gz"
        if prefix_template
        else "difft-{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
    )
    mac_asset = (
        "difft-{arch.machine}-apple-darwin.tar.gz"
        if prefix_template
        else "difft-{ver}-{arch.machine}-apple-darwin.tar.gz"
    )
    os_line = ""
    if linux_os is not None:
        quoted = ", ".join(f'"{o}"' for o in linux_os)
        os_line = f"os = [{quoted}]\n"
    content = f"""
[[tool]]
id = "difftastic"
name = "difftastic"
category = "git"
cmd = "difft"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-13
desc = "structural diff"
[[tool.method]]
kind = "github_release"
{os_line}repo = "{_REPO}"
asset = "{linux_asset}"
member = "difft"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "{_REPO}"
asset = "{mac_asset}"
member = "difft"
strip = 0
"""
    p = tmp_path / "registry.toml"
    if not seed_verified:
        content = content.replace("verified = 2026-10-13\n", "")
    p.write_text(content)
    return p


def _release_urls(release: Release, assets: dict[str, str]) -> set[str]:
    urls: set[str] = set()
    for name in assets:
        urls.add(f"https://github.com/{_REPO}/releases/download/{release.tag}/{name}")
    return urls


def _head_for_release(release: Release, assets: dict[str, str]) -> Callable[[str], str]:
    known = _release_urls(release, assets)

    def head(url: str) -> str:
        if url not in known:
            raise HTTPError(url, 404, "Not Found", Message(), fp=io.BytesIO())
        return 'etag:"release"'

    return head


def _difftastic_download(url: str, dest: Path) -> None:
    if url.endswith(".tar.gz"):
        _write_difft_tar(dest)
    else:
        dest.write_bytes(b"")


def _probe(
    release: Release,
    assets: dict[str, str],
    *,
    head: Callable[[str], str] | None = None,
    download: Callable[[str, Path], None] | None = None,
) -> Probe:
    return Probe(
        release=lambda repo: release if repo == _REPO else Release(tag="0.0.0", digests={}),
        head=head or _head_for_release(release, assets),
        download=download or _difftastic_download,
    )


def test_prefix_difftastic_template_is_reported_as_drift(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=True)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    tools = load_tools(registry)
    report = check_registry(tools, _probe(release, assets), state={})
    difft_findings = [f for f in report.findings if f.tool_id == "difftastic"]
    assert difft_findings
    assert all(f.status == "drift" for f in difft_findings)
    assert all(f.reason.startswith("asset missing") for f in difft_findings)
    assert report.exit_code == 1


def test_fixed_template_is_ok(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    tools = load_tools(registry)
    report = check_registry(tools, _probe(release, assets), state={})
    assert report.findings
    assert all(f.status == "ok" for f in report.findings)
    assert report.exit_code == 0


def test_urls_are_checked_once_per_rendered_url(tmp_path: Path) -> None:
    registry = _difftastic_registry(
        tmp_path, prefix_template=False, linux_os=["debian", "arch", "fedora"]
    )
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    head_calls: list[str] = []

    def head(url: str) -> str:
        head_calls.append(url)
        if url not in _release_urls(release, assets):
            raise HTTPError(url, 404, "Not Found", Message(), fp=io.BytesIO())
        return 'etag:"x"'

    tools = load_tools(registry)
    report = check_registry(tools, _probe(release, assets, head=head), state={})
    linux_findings = [
        f for f in report.findings if f.tool_id == "difftastic" and "unknown-linux-gnu" in f.url
    ]
    assert len(linux_findings) == 2
    linux_urls = {f.url for f in linux_findings}
    assert len(linux_urls) == 2
    assert len(head_calls) == len(set(head_calls))
    assert len([u for u in head_calls if "unknown-linux-gnu" in u]) == 2


def test_main_prints_the_report_and_returns_the_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    registry = _difftastic_registry(tmp_path, prefix_template=True)
    state_path = tmp_path / "state.json"
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    code = main(
        ["--registry", str(registry), "--state", str(state_path)],
        probe=_probe(release, assets),
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "difftastic" in out
    assert "difft-" in out


def test_check_run_leaves_the_registry_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    before = registry.read_bytes()
    state_path = tmp_path / "state.json"
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    main(
        ["--registry", str(registry), "--state", str(state_path)],
        probe=_probe(release, assets),
    )
    assert registry.read_bytes() == before
    assert state_path.is_file()


def test_head_failure_other_than_not_found_is_inconclusive(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    urls = sorted(_release_urls(release, assets))
    bad_url = urls[0]

    def head(url: str) -> str:
        if url == bad_url:
            raise HTTPError(url, 503, "Unavailable", Message(), fp=io.BytesIO())
        return 'etag:"ok"'

    tools = load_tools(registry)
    report = check_registry(tools, _probe(release, assets, head=head), state={})
    bad = [f for f in report.findings if f.url == bad_url]
    assert len(bad) == 1
    assert bad[0].status == "inconclusive"
    assert "503" in bad[0].reason
    assert report.exit_code == 2


def test_report_lists_every_passed_target_with_its_platforms(tmp_path: Path) -> None:
    registry = _difftastic_registry(
        tmp_path, prefix_template=False, linux_os=["debian", "arch", "fedora"]
    )
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    tools = load_tools(registry)
    report = check_registry(tools, _probe(release, assets), state={})
    linux_ok = [f for f in report.findings if f.status == "ok" and "unknown-linux-gnu" in f.url]
    for finding in linux_ok:
        assert finding.platforms == ("arch/amd64", "debian/amd64", "fedora/amd64") or (
            finding.platforms == ("arch/arm64", "debian/arm64", "fedora/arm64")
        )
    text = format_report(report)
    assert "## Passed" in text
    assert "`difftastic`" in text
    assert format_report(report, include_passed=False).count("Passed") == 0


def _write_registry(tmp_path: Path, content: str) -> Path:
    if "verified" not in content:
        content = content.replace('tier = "user"', 'tier = "user"\nverified = 2026-10-13')
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "registry.toml"
    p.write_text(content)
    return p


def _gz_tar_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _xz_tar_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _map_probe(
    release: Release,
    *,
    assets: dict[str, str] | None = None,
    payloads: dict[str, bytes] | None = None,
    head: Callable[[str], str] | None = None,
) -> tuple[Probe, dict[str, int]]:
    downloads: dict[str, int] = defaultdict(int)
    _ = assets
    bodies = payloads or {}

    def release_fn(repo: str) -> Release:
        return release

    def head_fn(url: str) -> str:
        if head is not None:
            return head(url)
        return 'etag:"1"'

    def download_fn(url: str, dest: Path) -> None:
        downloads[url] += 1
        if url in bodies:
            dest.write_bytes(bodies[url])
            return
        name = url.rsplit("/", 1)[-1]
        if name in bodies:
            dest.write_bytes(bodies[name])
            return
        dest.write_bytes(b"")

    return Probe(release=release_fn, head=head_fn, download=download_fn), downloads


def test_member_missing_from_archive_is_drift(tmp_path: Path) -> None:
    content = """
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/missing"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    tar = _gz_tar_bytes({"other": b"x"})
    digest = hashlib.sha256(tar).hexdigest()
    release = _release(tag="1.0.0", assets={"a-1.0.0.tar.gz": digest})
    probe, _ = _map_probe(release, payloads={"a-1.0.0.tar.gz": tar})
    report = check_registry(load_tools(registry), probe, state={})
    assert report.findings[0].status == "drift"
    assert "member bin/missing missing" in report.findings[0].reason


def test_zip_and_app_members_are_listed_not_extracted(tmp_path: Path) -> None:
    zip_body = _zip_bytes({"My.app/Contents/MacOS/cli": b"x"})
    digest = hashlib.sha256(zip_body).hexdigest()
    content = """
[[tool]]
id = "zipper"
name = "zipper"
category = "git"
cmd = "z"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "o/r"
asset = "z-{ver}.zip"
member = "My.app/Contents/MacOS/cli"
archive = "zip"
strip = 0
[[tool]]
id = "apper"
name = "apper"
category = "git"
cmd = "a"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "app"
os = ["macos"]
url = "https://example.test/app-{ver}.zip"
version = "2.0.0"
app = "My.app"
cli = "Contents/MacOS/cli"
sha256 = "PLACEHOLDER"
"""
    sha = hashlib.sha256(zip_body).hexdigest()
    content = content.replace("PLACEHOLDER", sha)
    registry = _write_registry(tmp_path, content)
    release = _release(tag="2.0.0", assets={"z-2.0.0.zip": digest})
    probe, _ = _map_probe(
        release,
        payloads={
            "z-2.0.0.zip": zip_body,
            "https://example.test/app-2.0.0.zip": zip_body,
        },
    )
    report = check_registry(load_tools(registry), probe, state={})
    assert all(f.status == "ok" for f in report.findings)
    assert not any(p.is_dir() and p.name == "My.app" for p in tmp_path.iterdir())


def test_checksum_file_without_the_asset_is_drift(tmp_path: Path) -> None:
    tar = _gz_tar_bytes({"bin/x": b"x"})
    digest = hashlib.sha256(tar).hexdigest()
    content = """
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/x"
checksum = "SHA256SUMS"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.0.0", assets={"a-1.0.0.tar.gz": digest})
    checksum_text = "deadbeef\n"
    probe, _ = _map_probe(
        release,
        payloads={
            "a-1.0.0.tar.gz": tar,
            "SHA256SUMS": checksum_text.encode(),
        },
    )
    report = check_registry(load_tools(registry), probe, state={})
    assert report.findings[0].status == "drift"
    assert "checksum file missing entry" in report.findings[0].reason


def test_checksum_file_disagreeing_with_the_digest_is_drift(tmp_path: Path) -> None:
    tar = _gz_tar_bytes({"bin/x": b"x"})
    digest = hashlib.sha256(tar).hexdigest()
    content = """
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/x"
checksum = "SHA256SUMS"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.0.0", assets={"a-1.0.0.tar.gz": digest})
    wrong = "f" * 64
    checksum_text = f"{wrong}  a-1.0.0.tar.gz\n"
    probe, _ = _map_probe(
        release,
        payloads={
            "a-1.0.0.tar.gz": tar,
            "SHA256SUMS": checksum_text.encode(),
        },
    )
    report = check_registry(load_tools(registry), probe, state={})
    assert report.findings[0].status == "drift"
    assert "checksum file disagrees" in report.findings[0].reason


def test_downloaded_hash_mismatch_is_drift(tmp_path: Path) -> None:
    tar = _gz_tar_bytes({"bin/x": b"x"})
    content = """
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/x"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.0.0", assets={"a-1.0.0.tar.gz": "b" * 64})
    probe, _ = _map_probe(release, payloads={"a-1.0.0.tar.gz": tar})
    report = check_registry(load_tools(registry), probe, state={})
    assert report.findings[0].status == "drift"
    assert report.findings[0].reason == "checksum mismatch"


@pytest.mark.parametrize("state", [{}, {"cached": "sha256:dead"}])
def test_pinned_sha256_differing_from_the_github_digest_is_drift(
    tmp_path: Path, state: dict[str, str]
) -> None:
    zip_body = _zip_bytes({"My.app/Contents/MacOS/cli": b"x"})
    pin = "c" * 64
    content = f"""
[[tool]]
id = "apper"
name = "apper"
category = "git"
cmd = "a"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "app"
os = ["macos"]
url = "https://github.com/o/r/releases/download/{{ver}}/app.zip"
version = "v2.0.0"
app = "My.app"
cli = "Contents/MacOS/cli"
sha256 = "{pin}"
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="v2.0.0", assets={"app.zip": "d" * 64})
    url = "https://github.com/o/r/releases/download/v2.0.0/app.zip"
    probe, _ = _map_probe(release, payloads={url: zip_body})
    seeded = dict(state)
    if state:
        seeded = {
            state_key(
                "apper",
                url,
                "My.app/Contents/MacOS/cli",
                archive="zip",
                strip=0,
                raw=False,
            ): f'sha256:{pin}|etag:"1"',
        }
    report = check_registry(load_tools(registry), probe, seeded)
    assert all(f.status == "drift" for f in report.findings)
    assert all("pinned sha256 differs" in f.reason for f in report.findings)


def test_pinned_sha256_of_an_older_tag_is_not_compared_with_the_latest_release(
    tmp_path: Path,
) -> None:
    zip_body = _zip_bytes({"My.app/Contents/MacOS/cli": b"x"})
    pin = hashlib.sha256(zip_body).hexdigest()
    content = f"""
[[tool]]
id = "apper"
name = "apper"
category = "git"
cmd = "a"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "app"
os = ["macos"]
url = "https://github.com/o/r/releases/download/{{ver}}/app.zip"
version = "v1.0.0"
app = "My.app"
cli = "Contents/MacOS/cli"
sha256 = "{pin}"
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="v2.0.0", assets={"app.zip": "e" * 64})
    rendered = "https://github.com/o/r/releases/download/v1.0.0/app.zip"
    probe, _ = _map_probe(release, payloads={rendered: zip_body})
    report = check_registry(load_tools(registry), probe, state={})
    assert not any("pinned sha256 differs" in f.reason for f in report.findings)
    assert any(
        f.status == "drift" and "newer stable release v2.0.0 (pinned v1.0.0)" in f.reason
        for f in report.findings
    )


def test_unchanged_asset_is_not_downloaded(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    tar = _difft_tar_bytes()
    payloads = {
        f"https://github.com/{_REPO}/releases/download/{_TAG}/{name}": tar for name in assets
    }
    probe, dl = _map_probe(release, assets=assets, payloads=payloads)
    tools = load_tools(registry)
    state: dict[str, str] = {}
    check_registry(tools, probe, state)
    first_total = sum(dl.values())
    assert first_total > 0
    probe2, dl2 = _map_probe(release, assets=assets, payloads=payloads)
    report = check_registry(tools, probe2, state)
    assert sum(dl2.values()) == 0
    assert all(f.status == "ok" for f in report.findings)


def test_changed_digest_triggers_a_download(tmp_path: Path) -> None:
    tar = _gz_tar_bytes({"bin/x": b"x"})
    digest = hashlib.sha256(tar).hexdigest()
    content = """
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/x"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.0.0", assets={"a-1.0.0.tar.gz": digest})
    url = "https://github.com/o/r/releases/download/1.0.0/a-1.0.0.tar.gz"
    state = {f"t1|{url}#bin/x|archive=gz|strip=0|raw=false": "sha256:old"}
    probe, dl = _map_probe(release, payloads={"a-1.0.0.tar.gz": tar})
    check_registry(load_tools(registry), probe, state)
    assert dl[url] == 1


def test_asset_without_digest_uses_the_head_fingerprint(tmp_path: Path) -> None:
    tar = _gz_tar_bytes({"bin/x": b"x"})
    content = """
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/x"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.0.0", assets={})
    url = "https://github.com/o/r/releases/download/1.0.0/a-1.0.0.tar.gz"
    heads = {"pass": 0}

    def head(u: str) -> str:
        heads["pass"] += 1
        return 'etag:"stable"'

    probe1, dl1 = _map_probe(release, payloads={"a-1.0.0.tar.gz": tar}, head=head)
    state: dict[str, str] = {}
    check_registry(load_tools(registry), probe1, state)
    assert dl1[url] == 1
    probe2, dl2 = _map_probe(release, payloads={"a-1.0.0.tar.gz": tar}, head=head)
    check_registry(load_tools(registry), probe2, state)
    assert dl2.get(url, 0) == 0


def test_shared_url_with_different_members_checks_each_member(tmp_path: Path) -> None:
    zip_body = _zip_bytes(
        {
            "x86_64-unknown-linux-gnu/broot": b"x",
            "aarch64-unknown-linux-gnu/broot": b"x",
            "aarch64-apple-darwin/broot": b"x",
        }
    )
    digest = hashlib.sha256(zip_body).hexdigest()
    content = """
[[tool]]
id = "broot"
name = "broot"
category = "git"
cmd = "broot"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "Canop/broot"
asset = "broot_{ver}.zip"
member = "{arch.machine}-unknown-linux-gnu/broot"
archive = "zip"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "Canop/broot"
asset = "broot_{ver}.zip"
member = "{arch.machine}-apple-darwin/broot"
archive = "zip"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.44.0", assets={"broot_1.44.0.zip": digest})
    url = "https://github.com/Canop/broot/releases/download/1.44.0/broot_1.44.0.zip"
    probe, dl = _map_probe(release, payloads={"broot_1.44.0.zip": zip_body})
    report = check_registry(load_tools(registry), probe, state={})
    assert dl[url] == 1
    assert sum(1 for _ in dl) == 1
    ok = [f for f in report.findings if f.status == "ok"]
    drift = [f for f in report.findings if f.status == "drift"]
    assert len(ok) == 3
    assert len(drift) == 1
    assert "x86_64-apple-darwin/broot" in drift[0].reason
    assert "broot" not in report.passed_tools()


def test_a_new_member_on_a_known_url_is_downloaded(tmp_path: Path) -> None:
    zip_body = _zip_bytes(
        {
            "x86_64-unknown-linux-gnu/broot": b"x",
            "aarch64-unknown-linux-gnu/broot": b"x",
            "aarch64-apple-darwin/broot": b"x",
        }
    )
    digest = hashlib.sha256(zip_body).hexdigest()
    linux_only = """
[[tool]]
id = "broot"
name = "broot"
category = "git"
cmd = "broot"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
os = ["debian"]
repo = "Canop/broot"
asset = "broot_{ver}.zip"
member = "{arch.machine}-unknown-linux-gnu/broot"
archive = "zip"
strip = 0
"""
    full = (
        linux_only
        + """
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "Canop/broot"
asset = "broot_{ver}.zip"
member = "{arch.machine}-apple-darwin/broot"
archive = "zip"
strip = 0
"""
    )
    reg1 = _write_registry(tmp_path, linux_only)
    release = _release(tag="1.44.0", assets={"broot_1.44.0.zip": digest})
    url = "https://github.com/Canop/broot/releases/download/1.44.0/broot_1.44.0.zip"
    probe1, _ = _map_probe(release, payloads={"broot_1.44.0.zip": zip_body})
    state: dict[str, str] = {}
    check_registry(load_tools(reg1), probe1, state)
    reg2 = _write_registry(tmp_path / "two", full)
    probe2, dl2 = _map_probe(release, payloads={"broot_1.44.0.zip": zip_body})
    check_registry(load_tools(reg2), probe2, state)
    assert dl2[url] == 1


def test_targets_differing_only_in_strip_are_checked_separately(tmp_path: Path) -> None:
    tar = _gz_tar_bytes({"x-1.0/bin/x": b"x"})
    digest = hashlib.sha256(tar).hexdigest()
    url_tpl = "https://example.test/x-{ver}.tar.gz"
    rendered = "https://example.test/x-1.0.tar.gz"
    content = f"""
[[tool]]
id = "a"
name = "a"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "{url_tpl}"
version = "1.0"
member = "bin/x"
strip = 1
sha256 = "{digest}"
[[tool]]
id = "b"
name = "b"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "{url_tpl}"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{digest}"
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="0", assets={})
    probe, dl = _map_probe(release, payloads={rendered: tar})
    report = check_registry(load_tools(registry), probe, state={})
    assert dl[rendered] == 1
    by_tool = {f.tool_id: f for f in report.findings}
    assert by_tool["a"].status == "ok"
    assert by_tool["b"].status == "drift"
    assert "member bin/x missing" in by_tool["b"].reason
    state_out: dict[str, str] = {}
    check_registry(load_tools(registry), probe, state_out)
    keys = list(state_out)
    assert len(keys) == 1
    assert keys[0].startswith("a|")


def test_a_strip_change_invalidates_the_cached_ok(tmp_path: Path) -> None:
    tar = _gz_tar_bytes({"x-1.0/bin/x": b"x"})
    digest = hashlib.sha256(tar).hexdigest()
    url_tpl = "https://example.test/x-{ver}.tar.gz"
    rendered = "https://example.test/x-1.0.tar.gz"
    reg1 = _write_registry(
        tmp_path,
        f"""
[[tool]]
id = "a"
name = "a"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "{url_tpl}"
version = "1.0"
member = "bin/x"
strip = 1
sha256 = "{digest}"
""",
    )
    release = _release(tag="0", assets={})
    probe1, _ = _map_probe(release, payloads={rendered: tar})
    state: dict[str, str] = {}
    check_registry(load_tools(reg1), probe1, state)
    reg2 = _write_registry(
        tmp_path / "two",
        f"""
[[tool]]
id = "a"
name = "a"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "{url_tpl}"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{digest}"
""",
    )
    probe2, dl2 = _map_probe(release, payloads={rendered: tar})
    report = check_registry(load_tools(reg2), probe2, state)
    assert dl2[rendered] == 1
    assert report.findings[0].status == "drift"


@pytest.mark.parametrize(
    ("payload", "archive", "label"),
    [
        (b"not-a-tar", "gz", "gz"),
        (b"not-a-zip", "zip", "zip"),
    ],
)
def test_corrupt_archive_is_drift(tmp_path: Path, payload: bytes, archive: str, label: str) -> None:
    content = f"""
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{{ver}}.{"zip" if archive == "zip" else "tar.gz"}"
member = "bin/x"
strip = 0
"""
    if archive == "zip":
        content += 'archive = "zip"\n'
    registry = _write_registry(tmp_path, content)
    asset_name = "a-1.0.0.zip" if archive == "zip" else "a-1.0.0.tar.gz"
    release = _release(tag="1.0.0", assets={})
    probe, _ = _map_probe(release, payloads={asset_name: payload})
    report = check_registry(load_tools(registry), probe, state={})
    assert report.findings[0].status == "drift"
    assert f"archive unreadable as {label}" in report.findings[0].reason


def test_corrupt_archive_is_drift_truncated_tar(tmp_path: Path) -> None:
    tar = _gz_tar_bytes({"bin/x": b"x"})
    payload = tar[: len(tar) // 2]
    content = """
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/x"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.0.0", assets={})
    probe, _ = _map_probe(release, payloads={"a-1.0.0.tar.gz": payload})
    report = check_registry(load_tools(registry), probe, state={})
    assert report.findings[0].status == "drift"
    assert "archive unreadable as gz" in report.findings[0].reason


def test_declared_archive_type_mismatch_is_drift(tmp_path: Path) -> None:
    tar = _xz_tar_bytes({"bin/x": b"x"})
    digest = hashlib.sha256(tar).hexdigest()
    content = """
[[tool]]
id = "t1"
name = "t1"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.xz"
member = "bin/x"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.0.0", assets={"a-1.0.0.tar.xz": digest})
    probe, _ = _map_probe(release, payloads={"a-1.0.0.tar.xz": tar})
    report = check_registry(load_tools(registry), probe, state={})
    assert report.findings[0].status == "drift"
    assert "archive unreadable as gz" in report.findings[0].reason
    content_xz = content + 'archive = "xz"\n'
    registry2 = _write_registry(tmp_path / "xz", content_xz)
    probe2, _ = _map_probe(release, payloads={"a-1.0.0.tar.xz": tar})
    report2 = check_registry(load_tools(registry2), probe2, state={})
    assert report2.findings[0].status == "ok"


@pytest.mark.parametrize("order", ["a_first", "b_first"])
def test_a_fresh_checksum_mismatch_overrides_every_cached_ok_on_the_url(
    tmp_path: Path, order: str
) -> None:
    tar = _gz_tar_bytes({"bin/a": b"a", "bin/b": b"b"})
    digest = hashlib.sha256(tar).hexdigest()
    url = "https://github.com/o/r/releases/download/1.0.0/a-1.0.0.tar.gz"
    tool_a = """
[[tool]]
id = "a"
name = "a"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/a"
strip = 0
"""
    tool_b = """
[[tool]]
id = "b"
name = "b"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "a-{ver}.tar.gz"
member = "bin/b"
strip = 0
"""
    body = tool_a + tool_b if order == "a_first" else tool_b + tool_a
    registry = _write_registry(tmp_path, body)
    release = _release(tag="1.0.0", assets={"a-1.0.0.tar.gz": digest})
    bad = _gz_tar_bytes({"bin/a": b"z", "bin/b": b"b"})
    state = {
        f"a|{url}#bin/a|archive=gz|strip=0|raw=false": f"sha256:{digest}",
    }
    probe, dl = _map_probe(release, payloads={"a-1.0.0.tar.gz": bad})
    report = check_registry(load_tools(registry), probe, state)
    assert dl[url] == 1
    assert all(f.status == "drift" and f.reason == "checksum mismatch" for f in report.findings)
    assert not any(k.startswith("a|") or k.startswith("b|") for k in state)


def test_changed_bytes_under_an_unchanged_pin_are_downloaded_again(tmp_path: Path) -> None:
    b1 = _gz_tar_bytes({"bin/x": b"one"})
    b2 = _gz_tar_bytes({"bin/x": b"two"})
    pin = hashlib.sha256(b1).hexdigest()
    url = "https://vendor.example/app-{ver}.tar.gz"
    rendered = "https://vendor.example/app-1.0.tar.gz"
    content = f"""
[[tool]]
id = "sublime"
name = "sublime"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "{url}"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{pin}"
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="0", assets={})
    heads = iter(['etag:"1"', 'etag:"2"'])

    def head(_u: str) -> str:
        return next(heads)

    probe1, dl1 = _map_probe(release, payloads={rendered: b1}, head=head)
    state: dict[str, str] = {}
    report1 = check_registry(load_tools(registry), probe1, state)
    assert report1.findings[0].status == "ok"
    assert dl1[rendered] == 1
    probe2, dl2 = _map_probe(release, payloads={rendered: b2}, head=head)
    report2 = check_registry(load_tools(registry), probe2, state)
    assert dl2[rendered] == 1
    assert report2.findings[0].status == "drift"
    assert report2.findings[0].reason == "checksum mismatch"
    assert not any(k.startswith("sublime|") for k in state)


def _http_error(
    url: str,
    code: int,
    *,
    headers: dict[str, str] | None = None,
) -> HTTPError:
    msg = Message()
    for key, value in (headers or {}).items():
        msg[key] = value
    return HTTPError(url, code, "err", msg, fp=io.BytesIO())


def _version_error_from_http(url: str, code: int, **headers: str) -> VersionError:
    err = _http_error(url, code, headers=headers)
    exc = VersionError(f"failed for {url}")
    exc.__cause__ = err
    return exc


def _version_error_from_transport(cause: BaseException) -> VersionError:
    exc = VersionError("transport")
    exc.__cause__ = cause
    return exc


def _pinned_github_tarball_registry(tmp_path: Path, *, version: str = "31.0.2") -> Path:
    pin = "a" * 64
    content = f"""
[[tool]]
id = "helm"
name = "helm"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://github.com/o/r/releases/download/{{ver}}/a-{{ver}}.tar.gz"
version = "{version}"
member = "bin/x"
strip = 0
sha256 = "{pin}"
"""
    return _write_registry(tmp_path, content)


def _vendor_tarball_registry(tmp_path: Path) -> Path:
    pin = "a" * 64
    content = f"""
[[tool]]
id = "vendor"
name = "vendor"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/pkg-{{ver}}.tar.gz"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{pin}"
"""
    return _write_registry(tmp_path, content)


def test_pinned_github_url_behind_latest_is_newer_stable_drift(tmp_path: Path) -> None:
    registry = _pinned_github_tarball_registry(tmp_path)
    tar = _gz_tar_bytes({"bin/x": b"x"})
    rendered = "https://github.com/o/r/releases/download/31.0.2/a-31.0.2.tar.gz"
    release = Release(tag="v32.4.1", digests={})

    def rel(_repo: str) -> Release:
        return release

    probe, _ = _map_probe(release, payloads={rendered: tar})
    probe = Probe(release=rel, head=probe.head, download=probe.download)
    report = check_registry(load_tools(registry), probe, state={})
    drift = [f for f in report.findings if "newer stable" in f.reason]
    assert len(drift) == 1
    assert drift[0].status == "drift"
    assert drift[0].reason == "newer stable release v32.4.1 (pinned 31.0.2)"
    assert drift[0].url == rendered
    assert report.exit_code == 1


@pytest.mark.parametrize("latest_tag", ["v31.0.2", "v31.0.1"])
def test_older_or_equal_latest_tag_is_not_newer_stable(tmp_path: Path, latest_tag: str) -> None:
    registry = _pinned_github_tarball_registry(tmp_path)
    tar = _gz_tar_bytes({"bin/x": b"x"})
    rendered = "https://github.com/o/r/releases/download/31.0.2/a-31.0.2.tar.gz"
    release = Release(tag=latest_tag, digests={})
    probe, _ = _map_probe(release, payloads={rendered: tar})
    probe = Probe(release=lambda _r: release, head=probe.head, download=probe.download)
    report = check_registry(load_tools(registry), probe, state={})
    assert not any("newer stable release" in f.reason for f in report.findings)


def test_incomparable_latest_tag_is_reported_separately(tmp_path: Path) -> None:
    registry = _pinned_github_tarball_registry(tmp_path)
    tar = _gz_tar_bytes({"bin/x": b"x"})
    rendered = "https://github.com/o/r/releases/download/31.0.2/a-31.0.2.tar.gz"
    release = Release(tag="nightly", digests={})
    probe, _ = _map_probe(release, payloads={rendered: tar})
    probe = Probe(release=lambda _r: release, head=probe.head, download=probe.download)
    report = check_registry(load_tools(registry), probe, state={})
    inc = [f for f in report.findings if f.status == "inconclusive"]
    assert len(inc) == 1
    assert inc[0].reason == "latest tag nightly cannot be compared with pin 31.0.2"
    assert not any(f.status == "drift" and "newer stable" in f.reason for f in report.findings)


def test_pinned_url_without_a_release_source_is_noted(tmp_path: Path) -> None:
    pin = "a" * 64
    content = f"""
[[tool]]
id = "sublime"
name = "sublime"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://download.sublimetext.com/sublime_text_build_{{ver}}_mac.zip"
version = "4180"
member = "Sublime Text.app/Contents/MacOS/sublime_text"
strip = 0
sha256 = "{pin}"
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1")
    probe, _ = _map_probe(release)
    report = check_registry(load_tools(registry), probe, state={})
    assert not any("newer stable release" in f.reason for f in report.findings)
    assert any("sublime: newer stable: no release source" in n for n in report.notes)


def test_unpinned_github_release_never_reports_newer_stable(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    report = check_registry(load_tools(registry), _probe(release, assets), state={})
    assert not any("newer stable release" in f.reason for f in report.findings)


def test_kinds_that_cannot_be_checked_are_listed(tmp_path: Path) -> None:
    content = """
[[tool]]
id = "brewtool"
name = "brewtool"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "brew"
formula = "jq"
[[tool]]
id = "scripttool"
name = "scripttool"
category = "git"
cmd = "y"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "script"
url = "https://example.com/install.sh"
shell = "bash"
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1", assets={})
    probe, _ = _map_probe(release)
    report = check_registry(load_tools(registry), probe, state={})
    assert "brewtool" in report.not_checkable
    assert "scripttool" in report.not_checkable
    assert report.findings == ()


def test_missing_repo_is_drift(tmp_path: Path) -> None:
    content = """
[[tool]]
id = "gone"
name = "gone"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/missing"
asset = "a-{ver}.tar.gz"
member = "bin/x"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    api = "https://api.github.com/repos/o/missing/releases/latest"

    def rel(_repo: str) -> Release:
        raise _version_error_from_http(api, 404)

    probe = Probe(release=rel, head=lambda _u: 'etag:"1"', download=lambda _u, _d: None)
    report = check_registry(load_tools(registry), probe, state={})
    assert any(f.status == "drift" and f.reason == "release not found" for f in report.findings)
    assert report.exit_code == 1
    assert report.blocked is None


@pytest.mark.parametrize(
    "headers,code",
    [
        ({"X-RateLimit-Remaining": "0"}, 403),
        ({"Retry-After": "60"}, 403),
        ({}, 429),
    ],
)
def test_rate_limit_without_drift_blocks_the_run(
    tmp_path: Path, headers: dict[str, str], code: int
) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    api = "https://api.github.com/repos/Wilfred/difftastic/releases/latest"

    def rel(_repo: str) -> Release:
        raise _version_error_from_http(api, code, **headers)

    probe = Probe(
        release=rel,
        head=_head_for_release(_release(assets=assets), assets),
        download=_difftastic_download,
    )
    report = check_registry(load_tools(registry), probe, state={})
    assert report.blocked is not None
    assert "rate limit" in report.blocked.lower()
    assert report.exit_code == 2
    text = format_report(report)
    assert text.splitlines()[0].startswith("blocked:")
    assert "note:" not in text


@pytest.mark.parametrize(
    "case",
    [
        "rate_limit_head404",
        "transport_head410",
        "rate_limit_checksum",
        "rate_limit_member",
    ],
)
def test_blocked_run_still_reports_confirmed_drift(tmp_path: Path, case: str) -> None:
    vendor_url = "https://vendor.example/pkg-1.0.tar.gz"
    pin = hashlib.sha256(_gz_tar_bytes({"bin/x": b"x"})).hexdigest()
    content = f"""
[[tool]]
id = "api"
name = "api"
category = "git"
cmd = "a"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "x-{{ver}}.tar.gz"
member = "bin/x"
strip = 0
[[tool]]
id = "vendor"
name = "vendor"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/pkg-{{ver}}.tar.gz"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{pin}"
"""
    registry = _write_registry(tmp_path, content)
    api = "https://api.github.com/repos/o/r/releases/latest"
    tar_ok = _gz_tar_bytes({"bin/x": b"x"})
    tar_bad = _gz_tar_bytes({"other": b"x"})
    rate_headers = {"X-RateLimit-Remaining": "0"}

    def rel(_repo: str) -> Release:
        raise _version_error_from_http(api, 403, **rate_headers)

    def head(url: str) -> str:
        if case in ("rate_limit_head404", "transport_head410") and url == vendor_url:
            code = 404 if case == "rate_limit_head404" else 410
            raise _http_error(url, code)
        return 'etag:"1"'

    def download(url: str, dest: Path) -> None:
        if case == "rate_limit_checksum":
            dest.write_bytes(tar_bad if url == vendor_url else tar_ok)
        elif case == "rate_limit_member":
            dest.write_bytes(_gz_tar_bytes({"wrong": b"x"}) if url == vendor_url else tar_ok)
        else:
            dest.write_bytes(tar_ok)

    if case == "transport_head410":

        def rel_transport(_repo: str) -> Release:
            raise _version_error_from_transport(URLError("down"))

        probe = Probe(release=rel_transport, head=head, download=download)
    else:
        probe = Probe(release=rel, head=head, download=download)

    report = check_registry(load_tools(registry), probe, state={})
    assert report.blocked is not None
    assert report.exit_code == 1
    text = format_report(report)
    lines = text.splitlines()
    assert lines[0].startswith("blocked:")
    assert lines[1].startswith("note: the run was otherwise blocked")
    assert any(f.status == "drift" for f in report.findings)


def test_forbidden_without_rate_limit_evidence_does_not_block(tmp_path: Path) -> None:
    pin = "a" * 64
    content = f"""
[[tool]]
id = "api"
name = "api"
category = "git"
cmd = "a"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "x-{{ver}}.tar.gz"
member = "bin/x"
strip = 0
[[tool]]
id = "vendor"
name = "vendor"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/pkg-{{ver}}.tar.gz"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{pin}"
"""
    registry = _write_registry(tmp_path, content)
    vendor_url = "https://vendor.example/pkg-1.0.tar.gz"
    api = "https://api.github.com/repos/o/r/releases/latest"

    def rel(_repo: str) -> Release:
        raise _version_error_from_http(api, 403)

    def head(url: str) -> str:
        if url == vendor_url:
            raise _http_error(url, 404)
        return 'etag:"1"'

    probe = Probe(release=rel, head=head, download=lambda _u, _d: None)
    report = check_registry(load_tools(registry), probe, state={})
    assert report.blocked is None
    assert report.exit_code == 1
    forbidden = [
        f
        for f in report.findings
        if f.status == "inconclusive" and f.reason == "release read forbidden (HTTP 403)"
    ]
    assert forbidden
    drift = [f for f in report.findings if f.status == "drift"]
    assert drift
    assert "403" in format_report(report)


@pytest.mark.parametrize("mode", ["all404", "all503_release", "all503_head_only"])
def test_http_answers_never_block_the_run(tmp_path: Path, mode: str) -> None:
    if mode == "all503_head_only":
        registry = _vendor_tarball_registry(tmp_path)

        def rel(_repo: str) -> Release:
            raise RuntimeError("release should not be called")

        def head(url: str) -> str:
            raise _http_error(url, 503)

        probe = Probe(release=rel, head=head, download=lambda _u, _d: None)
        report = check_registry(load_tools(registry), probe, state={})
        assert report.blocked is None
        assert report.exit_code == 2
        return

    content = """
[[tool]]
id = "gone"
name = "gone"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/missing"
asset = "a-{ver}.tar.gz"
member = "bin/x"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    api = "https://api.github.com/repos/o/missing/releases/latest"
    code = 404 if mode == "all404" else 503

    def rel(_repo: str) -> Release:
        raise _version_error_from_http(api, code)

    probe = Probe(release=rel, head=lambda _u: 'etag:"1"', download=lambda _u, _d: None)
    report = check_registry(load_tools(registry), probe, state={})
    assert report.blocked is None
    if mode == "all404":
        assert report.exit_code == 1
        assert all(f.status == "drift" and f.reason == "release not found" for f in report.findings)
    else:
        assert report.exit_code == 2
        assert all(f.status == "inconclusive" for f in report.findings)


@pytest.mark.parametrize("transport", [URLError("net"), TimeoutError()])
def test_no_network_blocks_the_run(tmp_path: Path, transport: BaseException) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)

    def rel(_repo: str) -> Release:
        raise _version_error_from_transport(transport)

    assets = _canned_difftastic_assets()
    probe = Probe(
        release=rel,
        head=_head_for_release(_release(assets=assets), assets),
        download=_difftastic_download,
    )
    report = check_registry(load_tools(registry), probe, state={})
    assert report.exit_code == 2
    assert report.blocked is not None
    assert "no GitHub release read got an HTTP response" in report.blocked


def test_all_failed_requests_without_release_reads_block_the_run(tmp_path: Path) -> None:
    pin = "a" * 64
    content = f"""
[[tool]]
id = "vendor"
name = "vendor"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/pkg-{{ver}}.tar.gz"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{pin}"
[[tool]]
id = "latestapp"
name = "latestapp"
category = "git"
cmd = "y"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "app"
url = "https://vendor.example/app.zip"
app = "App.app"
"""
    registry = _write_registry(tmp_path, content)

    def rel(_repo: str) -> Release:
        raise RuntimeError("no release read")

    def head(_url: str) -> str:
        raise URLError("down")

    probe = Probe(release=rel, head=head, download=lambda _u, _d: None)
    report = check_registry(load_tools(registry), probe, state={})
    assert report.exit_code == 2
    assert report.blocked is not None
    assert "no HEAD or download request got an HTTP response" in report.blocked


@pytest.mark.parametrize("flaky", ["head503", "head403", "download_urlerror", "release_urlerror"])
def test_one_flaky_host_does_not_hide_drift(tmp_path: Path, flaky: str) -> None:
    content = """
[[tool]]
id = "bad"
name = "bad"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/good"
asset = "a-{ver}.tar.gz"
member = "bin/x"
strip = 0
[[tool]]
id = "good"
name = "good"
category = "git"
cmd = "y"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/bad"
asset = "b-{ver}.tar.gz"
member = "bin/y"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    good_tar = _gz_tar_bytes({"bin/x": b"x"})
    good_url = "https://github.com/o/good/releases/download/1.0.0/a-1.0.0.tar.gz"
    bad_url = "https://github.com/o/bad/releases/download/1.0.0/b-1.0.0.tar.gz"
    digest = hashlib.sha256(good_tar).hexdigest()
    release_good = Release(tag="1.0.0", digests={"a-1.0.0.tar.gz": digest})

    def rel(repo: str) -> Release:
        if flaky == "release_urlerror" and repo == "o/bad":
            raise _version_error_from_transport(URLError("api down"))
        if repo == "o/good":
            return release_good
        return Release(tag="1.0.0", digests={})

    def head(url: str) -> str:
        if flaky == "head503" and url == good_url:
            raise _http_error(url, 503)
        if flaky == "head403" and url == good_url:
            raise _http_error(url, 403)
        if flaky == "release_urlerror" and url == good_url:
            raise _http_error(url, 404)
        if flaky != "release_urlerror" and url == bad_url:
            raise _http_error(url, 404)
        return 'etag:"1"'

    def download(url: str, dest: Path) -> None:
        if flaky == "download_urlerror" and url == good_url:
            raise URLError("dl down")
        dest.write_bytes(good_tar)

    probe = Probe(release=rel, head=head, download=download)
    report = check_registry(load_tools(registry), probe, state={})
    assert report.exit_code == 1
    assert any(f.status == "drift" for f in report.findings)
    assert any(f.status == "inconclusive" for f in report.findings)
    text = format_report(report)
    assert "## Drift" in text
    assert "## Inconclusive" in text


def test_inconclusive_without_drift_exits_2(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    urls = sorted(_release_urls(_release(assets=assets), assets))
    bad = urls[0]

    def head(url: str) -> str:
        if url == bad:
            raise _http_error(url, 503)
        return 'etag:"ok"'

    release = _release(assets=assets)
    report = check_registry(load_tools(registry), _probe(release, assets, head=head), state={})
    assert report.exit_code == 2
    assert report.blocked is None


def test_report_lists_methods_that_would_install_unverified(tmp_path: Path) -> None:
    digest = hashlib.sha256(_gz_tar_bytes({"bin/x": b"x"})).hexdigest()
    content = f"""
[[tool]]
id = "mixed"
name = "mixed"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/with-digest"
asset = "a-{{ver}}.tar.gz"
member = "bin/x"
strip = 0
[[tool.method]]
kind = "github_release"
repo = "o/no-digest"
asset = "b-{{ver}}.tar.gz"
member = "bin/x"
strip = 0
[[tool.method]]
kind = "github_release"
repo = "o/checksum"
asset = "c-{{ver}}.tar.gz"
member = "bin/x"
strip = 0
checksum = "https://vendor.example/sha256sums.txt"
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/latest.tar.gz"
member = "bin/x"
strip = 0
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/pin-{{ver}}.tar.gz"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{digest}"
[[tool.method]]
kind = "app"
url = "https://vendor.example/app.zip"
app = "App.app"
"""

    registry = _write_registry(tmp_path, content)
    tar = _gz_tar_bytes({"bin/x": b"x"})

    def rel(repo: str) -> Release:
        if repo == "o/with-digest":
            return Release(tag="1.0.0", digests={"a-1.0.0.tar.gz": digest})
        if repo == "o/no-digest":
            return Release(tag="1.0.0", digests={})
        if repo == "o/checksum":
            return Release(tag="1.0.0", digests={"c-1.0.0.tar.gz": digest})
        return Release(tag="0", digests={})

    def download(url: str, dest: Path) -> None:
        if url.endswith("sha256sums.txt"):
            dest.write_text(f"{hashlib.sha256(tar).hexdigest()}  c-1.0.0.tar.gz\n")
            return
        dest.write_bytes(tar)

    probe = Probe(release=rel, head=lambda _u: 'etag:"1"', download=download)
    report = check_registry(load_tools(registry), probe, state={})
    entries = {(e.tool_id, e.method_index, e.kind) for e in report.unverified}
    assert ("mixed", 1, "github_release") in entries
    assert ("mixed", 3, "tarball") in entries
    assert ("mixed", 5, "app") in entries
    text = format_report(report)
    assert "Unverified at install (no checksum file, pinned sha256 or GitHub digest):" in text
    assert "- `mixed` method 1 (github_release):" in text


def test_unverified_section_says_none_when_everything_verifies(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    report = check_registry(load_tools(registry), _probe(release, assets), state={})
    text = format_report(report)
    assert "Unverified at install" in text
    assert "- none" in text


def test_explicit_token_is_sent_to_api_github_only(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, dict[str, str]]] = []

    class FakeResp:
        def read(self) -> bytes:
            return b"{}"

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(req: urllib.request.Request, timeout: float = 0) -> FakeResp:
        headers = {k: v for k, v in req.header_items()}
        captured.append((req.full_url, headers))
        return FakeResp()

    import urllib.request

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    urlopen_fetch("https://api.github.com/repos/o/r/releases/latest", token="t")
    urlopen_fetch("https://github.com/o/r/releases/download/v1/a.tar.gz", token="t")
    api_headers = captured[0][1]
    dl_headers = captured[1][1]
    assert api_headers.get("Authorization") == "Bearer t"
    assert "Authorization" not in dl_headers
    monkeypatch.setenv("GH_TOKEN", "from-env")
    captured.clear()
    urlopen_fetch("https://api.github.com/repos/o/r/releases/latest")
    assert captured[0][1].get("Authorization") == "Bearer from-env"


def test_github_token_prefers_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from installer.verify_registry import github_token

    monkeypatch.setenv("GITHUB_TOKEN", "env-tok")
    monkeypatch.setenv("GH_TOKEN", "gh-tok")
    called: list[list[str]] = []

    def gh(cmd: list[str]) -> str:
        called.append(cmd)
        return "nope"

    assert github_token(gh) == "env-tok"
    assert not called


def test_github_token_falls_back_to_the_gh_login(monkeypatch: pytest.MonkeyPatch) -> None:
    from installer.verify_registry import github_token

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    def gh(cmd: list[str]) -> str:
        assert cmd == ["gh", "auth", "token"]
        return f"tok{chr(10)}"

    assert github_token(gh) == "tok"


def test_github_token_is_none_without_a_gh_login(monkeypatch: pytest.MonkeyPatch) -> None:
    from installer.verify_registry import github_token

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    def gh(_cmd: list[str]) -> str:
        raise CommandError(["gh", "auth", "token"], 1)

    assert github_token(gh) is None


def test_main_never_prints_the_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from installer import verify_registry as vr

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    state_path = tmp_path / "state.json"
    recorded: list[str | None] = []

    def fake_default_probe(token: str | None = None) -> Probe:
        recorded.append(token)
        assets = _canned_difftastic_assets()
        return _probe(_release(assets=assets), assets)

    monkeypatch.setattr(vr, "default_probe", fake_default_probe)

    def gh(_cmd: list[str]) -> str:
        return "secret-token-value"

    code = vr.main(
        ["--registry", str(registry), "--state", str(state_path)],
        gh=gh,
    )
    assert code == 0
    assert recorded == ["secret-token-value"]
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert "secret-token-value" not in blob

    def gh_fail(_cmd: list[str]) -> str:
        raise CommandError(["gh", "auth", "token"], 1)

    recorded.clear()
    capsys.readouterr()
    vr.main(["--registry", str(registry), "--state", str(state_path)], gh=gh_fail)
    captured2 = capsys.readouterr()
    assert recorded == [None]
    assert "unauthenticated GitHub API (60 requests/hour)" in captured2.err


# --- plan 18-13 task 1: --write / apply_registry_edits ---

_REAL_REGISTRY = Path(__file__).resolve().parents[1] / "installer" / "registry.toml"


def _two_tool_write_fixture(tmp_path: Path) -> Path:
    tar_a = _gz_tar_bytes({"bin/a": b"x"})
    hash_a = hashlib.sha256(tar_a).hexdigest()
    pin_b = "b" * 64
    content = f"""
[[tool]]
id = "tool_a"
name = "tool_a"
category = "git"
cmd = "a"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-01
[[tool.method]]
kind = "tarball"
url = "https://example.com/a-{{ver}}.tar.gz"
version = "1.0.0"
member = "bin/a"
strip = 0
sha256 = "{hash_a}"

[[tool]]
id = "tool_b"
name = "tool_b"
category = "git"
cmd = "b"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-01
[[tool.method]]
kind = "tarball"
url = "https://example.com/b-{{ver}}.tar.gz"
version = "1.0.0"
member = "bin/b"
strip = 0
sha256 = "{pin_b}"
"""
    return _write_registry(tmp_path, content)


def test_write_dates_only_passing_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer import verify_registry as vr

    registry = _two_tool_write_fixture(tmp_path)
    tar_a = _gz_tar_bytes({"bin/a": b"x"})
    tar_b = _gz_tar_bytes({"bin/b": b"y"})
    url_a = "https://example.com/a-1.0.0.tar.gz"
    url_b = "https://example.com/b-1.0.0.tar.gz"
    release = Release(tag="v1.0.0", digests={})

    def head(url: str) -> str:
        if url in (url_a, url_b):
            return 'etag:"1"'
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        if url == url_a:
            dest.write_bytes(tar_a)
        elif url == url_b:
            dest.write_bytes(tar_b)
        else:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    state_path = tmp_path / "state.json"
    today = date(2026, 10, 15)
    code = vr.main(
        ["--registry", str(registry), "--state", str(state_path), "--write"],
        probe=probe,
        today=today,
    )
    text = registry.read_text()
    assert "tool_a\n" in text or 'id = "tool_a"' in text
    assert "verified = 2026-10-15" in text.split('id = "tool_a"')[1].split("[[tool]]")[0]
    assert "tool_b" in text
    b_block = text.split('id = "tool_b"')[1].split("[[tool]]")[0]
    assert "verified = 2026-10-01" in b_block
    assert code == 1


def test_writer_keeps_every_other_byte(tmp_path: Path) -> None:
    dest = tmp_path / "registry.toml"
    copyfile(_REAL_REGISTRY, dest)
    before = dest.read_text().splitlines()
    after_text = apply_registry_edits(
        dest.read_text(), [RegistryEdit("jq", None, "verified", "2026-10-20")]
    )
    after = after_text.splitlines()
    delta_before = Counter(before) - Counter(after)
    delta_after = Counter(after) - Counter(before)
    assert delta_before == Counter({"verified = 2026-10-13": 1})
    assert delta_after == Counter({"verified = 2026-10-20": 1})


def test_writer_inserts_a_missing_key_at_the_anchor(tmp_path: Path) -> None:
    content = """
[[tool]]
id = "bare"
name = "bare"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://example.com/x-{ver}.tar.gz"
version = "1"
member = "bin/x"
strip = 0
"""
    registry = tmp_path / "registry.toml"
    registry.write_text(content)
    out = apply_registry_edits(
        content,
        [
            RegistryEdit("bare", None, "verified", "2026-10-20"),
            RegistryEdit("bare", 0, "sha256", '"' + "c" * 64 + '"'),
        ],
    )
    lines = out.splitlines()
    tier_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("tier ="))
    assert lines[tier_idx + 1].strip() == "verified = 2026-10-20"
    url_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("url ="))
    assert lines[url_idx + 1].strip().startswith("sha256 =")


def test_writer_refuses_an_unintended_change(tmp_path: Path) -> None:
    content = """
# id = "ghost" only in a comment
[[tool]]
id = "real"
name = "real"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-01
[[tool.method]]
kind = "tarball"
url = "https://example.com/x.tar.gz"
member = "bin/x"
strip = 0
"""
    registry = tmp_path / "registry.toml"
    registry.write_text(content)
    with pytest.raises(RegistryWriteError):
        apply_registry_edits(content, [RegistryEdit("ghost", None, "verified", "2026-10-20")])
    with pytest.raises(RegistryWriteError):
        apply_registry_edits(content, [RegistryEdit("real", 3, "sha256", '"abc"')])
    assert registry.read_text() == content


def test_writer_ignores_keys_inside_comments(tmp_path: Path) -> None:
    content = """
[[tool]]
id = "cmt"
name = "cmt"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-01
# version = 1.0 inside a comment
[[tool.method]]
kind = "tarball"
url = "https://example.com/x-{ver}.tar.gz"
version = "2.0"
member = "bin/x"
strip = 0
sha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
"""
    out = apply_registry_edits(content, [RegistryEdit("cmt", 0, "version", '"3.0"')])
    assert "# version = 1.0 inside a comment" in out
    assert 'version = "3.0"' in out
    assert out.count("version =") == 2


def test_without_write_the_registry_is_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import verify_registry as vr

    registry = _two_tool_write_fixture(tmp_path)
    before = registry.read_bytes()
    tar_a = _gz_tar_bytes({"bin/a": b"x"})
    rendered_a = "https://github.com/o/r/releases/download/1.0.0/a-1.0.0.tar.gz"
    release = Release(tag="v1.0.0", digests={})
    probe, _ = _map_probe(release, payloads={rendered_a: tar_a})
    state_path = tmp_path / "state.json"
    vr.main(["--registry", str(registry), "--state", str(state_path)], probe=probe)
    assert registry.read_bytes() == before


# --- plan 18-13 task 2: pin bump and --candidate ---


def _github_pin_registry(tmp_path: Path, *, tool_id: str = "helm") -> Path:
    pin = "a" * 64
    content = f"""
[[tool]]
id = "{tool_id}"
name = "{tool_id}"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-01
[[tool.method]]
kind = "tarball"
url = "https://github.com/o/r/releases/download/{{ver}}/a-{{ver}}.tar.gz"
version = "31.0.2"
member = "bin/x"
strip = 0
sha256 = "{pin}"
"""
    return _write_registry(tmp_path, content)


def _sublime_two_pin_registry(tmp_path: Path) -> Path:
    tar_old = _xz_tar_bytes({"sublime_text/sublime_text": b"z"})
    pin = hashlib.sha256(tar_old).hexdigest()
    content = f"""
[[tool]]
id = "sublime"
name = "sublime"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-01
[[tool.method]]
kind = "tarball"
url = "https://download.example/sublime_text_build_{{ver}}_x64.tar.xz"
version = "4200"
member = "sublime_text/sublime_text"
strip = 0
archive = "xz"
sha256 = "{pin}"
[[tool.method]]
kind = "tarball"
url = "https://download.example/sublime_text_build_{{ver}}_arm64.tar.xz"
version = "4200"
member = "sublime_text/sublime_text"
strip = 0
archive = "xz"
sha256 = "{pin}"
"""
    return _write_registry(tmp_path, content)


def test_newer_github_pin_is_bumped_when_the_candidate_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import verify_registry as vr

    registry = _github_pin_registry(tmp_path)
    old_url = "https://github.com/o/r/releases/download/31.0.2/a-31.0.2.tar.gz"
    new_url = "https://github.com/o/r/releases/download/32.4.1/a-32.4.1.tar.gz"
    tar_old = _gz_tar_bytes({"bin/x": b"old"})
    tar_new = _gz_tar_bytes({"bin/x": b"new"})
    new_digest = hashlib.sha256(tar_new).hexdigest()
    release = Release(
        tag="v32.4.1",
        digests={"a-32.4.1.tar.gz": new_digest},
    )

    def head(url: str) -> str:
        if url in (old_url, new_url):
            return 'etag:"1"'
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        if url == old_url:
            dest.write_bytes(tar_old)
        elif url == new_url:
            dest.write_bytes(tar_new)
        else:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    today = date(2026, 10, 15)
    code = vr.main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--write"],
        probe=probe,
        today=today,
    )
    text = registry.read_text()
    assert 'version = "32.4.1"' in text
    assert new_digest in text
    assert "verified = 2026-10-15" in text
    assert code == 0


def test_candidate_flag_bumps_a_pin_without_a_release_source(tmp_path: Path) -> None:
    from installer import verify_registry as vr

    registry = _sublime_two_pin_registry(tmp_path)
    url_x64 = "https://download.example/sublime_text_build_4215_x64.tar.xz"
    url_arm = "https://download.example/sublime_text_build_4215_arm64.tar.xz"
    tar_x = _xz_tar_bytes({"sublime_text/sublime_text": b"x"})
    tar_a = _xz_tar_bytes({"sublime_text/sublime_text": b"y"})
    digest_x = hashlib.sha256(tar_x).hexdigest()
    digest_a = hashlib.sha256(tar_a).hexdigest()
    old_x = "https://download.example/sublime_text_build_4200_x64.tar.xz"
    old_a = "https://download.example/sublime_text_build_4200_arm64.tar.xz"
    tar_old = _xz_tar_bytes({"sublime_text/sublime_text": b"z"})
    release = Release(tag="1", digests={})

    def head(url: str) -> str:
        if url in (old_x, old_a, url_x64, url_arm):
            return 'etag:"1"'
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        mapping = {
            old_x: tar_old,
            old_a: tar_old,
            url_x64: tar_x,
            url_arm: tar_a,
        }
        if url in mapping:
            dest.write_bytes(mapping[url])
            return
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    today = date(2026, 10, 15)
    code = vr.main(
        [
            "--registry",
            str(registry),
            "--state",
            str(tmp_path / "s.json"),
            "--write",
            "--candidate",
            "sublime=4215",
        ],
        probe=probe,
        today=today,
    )
    text = registry.read_text()
    assert text.count('version = "4215"') == 2
    assert digest_x in text and digest_a in text
    assert "verified = 2026-10-15" in text
    assert code == 0


def test_one_failing_method_blocks_the_whole_tool_bump(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from installer import verify_registry as vr

    registry = _sublime_two_pin_registry(tmp_path)
    url_x64 = "https://download.example/sublime_text_build_4215_x64.tar.xz"
    url_arm = "https://download.example/sublime_text_build_4215_arm64.tar.xz"
    old_x = "https://download.example/sublime_text_build_4200_x64.tar.xz"
    old_a = "https://download.example/sublime_text_build_4200_arm64.tar.xz"
    tar = _xz_tar_bytes({"sublime_text/sublime_text": b"z"})
    release = Release(tag="1", digests={})

    def head(url: str) -> str:
        if url == url_arm:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())
        if url in (old_x, old_a, url_x64):
            return 'etag:"1"'
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        if url in (old_x, old_a, url_x64):
            dest.write_bytes(tar)
            return
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    code = vr.main(
        [
            "--registry",
            str(registry),
            "--state",
            str(tmp_path / "s.json"),
            "--write",
            "--candidate",
            "sublime=4215",
        ],
        probe=probe,
        today=date(2026, 10, 15),
    )
    text = registry.read_text()
    assert 'version = "4200"' in text
    assert "verified = 2026-10-01" in text
    assert code == 1
    captured = capsys.readouterr()
    assert "bump to 4215 not applied:" in captured.out
    assert "arm64" in captured.out
    assert "dated sublime" not in captured.err


def test_renamed_candidate_asset_keeps_the_old_pin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from installer import verify_registry as vr

    registry = _github_pin_registry(tmp_path)
    old_url = "https://github.com/o/r/releases/download/31.0.2/a-31.0.2.tar.gz"
    new_url = "https://github.com/o/r/releases/download/32.4.1/a-32.4.1.tar.gz"
    tar_old = _gz_tar_bytes({"bin/x": b"old"})
    release = Release(tag="v32.4.1", digests={})

    def head(url: str) -> str:
        if url == old_url:
            return 'etag:"1"'
        if url == new_url:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        if url == old_url:
            dest.write_bytes(tar_old)
            return
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    code = vr.main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--write"],
        probe=probe,
    )
    captured = capsys.readouterr()
    assert 'version = "31.0.2"' in registry.read_text()
    assert "newer stable release" in captured.out
    assert code == 1


def test_write_run_after_a_bump_reports_the_registry_as_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from installer import verify_registry as vr

    registry = _github_pin_registry(tmp_path)
    old_url = "https://github.com/o/r/releases/download/31.0.2/a-31.0.2.tar.gz"
    new_url = "https://github.com/o/r/releases/download/32.4.1/a-32.4.1.tar.gz"
    tar_old = _gz_tar_bytes({"bin/x": b"old"})
    tar_new = _gz_tar_bytes({"bin/x": b"new"})
    new_digest = hashlib.sha256(tar_new).hexdigest()
    release = Release(tag="v32.4.1", digests={"a-32.4.1.tar.gz": new_digest})

    def head(url: str) -> str:
        if url in (old_url, new_url):
            return 'etag:"1"'
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        if url == old_url:
            dest.write_bytes(tar_old)
        elif url == new_url:
            dest.write_bytes(tar_new)
        else:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    code = vr.main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--write"],
        probe=probe,
        today=date(2026, 10, 15),
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "newer stable release" not in out
    assert "bumped helm 31.0.2 -> 32.4.1" in out
    report = vr.check_registry(load_tools(registry, today=date(2026, 10, 15)), probe, {})
    assert "helm" in report.passed_tools()


def test_github_app_pin_bump_matches_findings_by_app_cli_member(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from installer import verify_registry as vr

    pin = "a" * 64
    content = f"""
[[tool]]
id = "drawio-desktop"
name = "draw.io Desktop"
category = "diagram"
cmd = "drawio"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-01
[[tool.method]]
kind = "app"
os = ["macos"]
arch = ["arm64"]
url = "https://github.com/o/r/releases/download/v{{ver}}/draw.io-arm64-{{ver}}.zip"
version = "31.0.2"
sha256 = "{pin}"
app = "draw.io.app"
cli = "Contents/MacOS/draw.io"
"""
    registry = _write_registry(tmp_path, content)
    old_url = "https://github.com/o/r/releases/download/v31.0.2/draw.io-arm64-31.0.2.zip"
    new_url = "https://github.com/o/r/releases/download/v32.4.1/draw.io-arm64-32.4.1.zip"
    zip_new = _zip_bytes({"draw.io.app/Contents/MacOS/draw.io": b"new"})
    new_digest = hashlib.sha256(zip_new).hexdigest()
    release = Release(tag="v32.4.1", digests={"draw.io-arm64-32.4.1.zip": new_digest})

    def head(url: str) -> str:
        if url == new_url:
            return 'etag:"1"'
        if url == old_url:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        if url == new_url:
            dest.write_bytes(zip_new)
            return
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    code = vr.main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--write"],
        probe=probe,
        today=date(2026, 10, 15),
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "bumped drawio-desktop 31.0.2 -> 32.4.1" in out
    assert f'sha256 = "{new_digest}"' in registry.read_text()


def test_bump_replaces_the_findings_of_the_superseded_pin_targets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from installer import verify_registry as vr

    registry = _github_pin_registry(tmp_path, tool_id="drawio")
    old_url = "https://github.com/o/r/releases/download/31.0.2/a-31.0.2.tar.gz"
    new_url = "https://github.com/o/r/releases/download/32.4.1/a-32.4.1.tar.gz"
    tar_new = _gz_tar_bytes({"bin/x": b"new"})
    new_digest = hashlib.sha256(tar_new).hexdigest()
    release = Release(tag="v32.4.1", digests={"a-32.4.1.tar.gz": new_digest})

    def head(url: str) -> str:
        if url == new_url:
            return 'etag:"1"'
        if url == old_url:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        if url == new_url:
            dest.write_bytes(tar_new)
            return
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    code = vr.main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--write"],
        probe=probe,
        today=date(2026, 10, 15),
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "asset missing" not in out
    assert "newer stable release" not in out
    assert "bumped drawio 31.0.2 -> 32.4.1" in out


def test_bump_keeps_the_findings_of_the_tools_unpinned_methods(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from installer import verify_registry as vr

    pin = "a" * 64
    content = f"""
[[tool]]
id = "combo"
name = "combo"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
verified = 2026-10-01
[[tool.method]]
kind = "tarball"
url = "https://github.com/o/r/releases/download/{{ver}}/a-{{ver}}.tar.gz"
version = "31.0.2"
member = "bin/x"
strip = 0
sha256 = "{pin}"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "side-{{ver}}.tar.gz"
member = "bin/y"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    old_url = "https://github.com/o/r/releases/download/31.0.2/a-31.0.2.tar.gz"
    new_url = "https://github.com/o/r/releases/download/32.4.1/a-32.4.1.tar.gz"
    side_url = "https://github.com/o/r/releases/download/v32.4.1/side-32.4.1.tar.gz"
    tar_old = _gz_tar_bytes({"bin/x": b"old"})
    tar_new = _gz_tar_bytes({"bin/x": b"new"})
    new_digest = hashlib.sha256(tar_new).hexdigest()
    release = Release(tag="v32.4.1", digests={"a-32.4.1.tar.gz": new_digest})

    def head(url: str) -> str:
        if url == side_url:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())
        if url in (old_url, new_url):
            return 'etag:"1"'
        raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    def download(url: str, dest: Path) -> None:
        if url == old_url:
            dest.write_bytes(tar_old)
        elif url == new_url:
            dest.write_bytes(tar_new)
        else:
            raise HTTPError(url, 404, "missing", Message(), fp=io.BytesIO())

    probe = Probe(release=lambda _r: release, head=head, download=download)
    code = vr.main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--write"],
        probe=probe,
        today=date(2026, 10, 15),
    )
    out = capsys.readouterr().out
    text = registry.read_text()
    assert 'version = "32.4.1"' in text
    assert new_digest in text
    assert "verified = 2026-10-01" in text
    assert "asset missing" in out
    assert code == 1


def test_unpinned_entries_never_gain_pin_keys(tmp_path: Path) -> None:
    from installer import verify_registry as vr

    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    probe = _probe(release, assets)
    before = registry.read_text()
    vr.main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--write"],
        probe=probe,
        today=date(2026, 10, 15),
    )
    after = registry.read_text()
    for line in after.splitlines():
        if "version =" in line and line.strip().startswith("version"):
            assert "difftastic" in before  # pinned version lines unchanged for unpinned
    assert before.count("sha256 =") == after.count("sha256 =")


def test_candidate_for_an_unknown_or_unpinned_tool_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from installer import verify_registry as vr

    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    probe = _probe(_release(assets=assets), assets)
    state = str(tmp_path / "s.json")
    before = registry.read_bytes()

    for args in (
        ["--registry", str(registry), "--state", state, "--write", "--candidate", "nope=1"],
        ["--registry", str(registry), "--state", state, "--write", "--candidate", "difftastic=1"],
        ["--registry", str(registry), "--state", state, "--write", "--candidate", "sublime"],
    ):
        capsys.readouterr()
        code = vr.main(args, probe=probe)
        err = capsys.readouterr().err
        assert code == EXIT_USAGE
        assert err.strip()
        assert registry.read_bytes() == before


class _GhRecorder:
    """Records ``gh`` argv and captures ``--body-file`` contents (offline)."""

    def __init__(self, *, list_json: str = "[]") -> None:
        self.calls: list[list[str]] = []
        self.bodies: list[str] = []
        self._list_json = list_json

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(list(cmd))
        if "--body-file" in cmd:
            path = cmd[cmd.index("--body-file") + 1]
            self.bodies.append(Path(path).read_text(encoding="utf-8"))
        if cmd[:3] == ["gh", "issue", "list"]:
            return self._list_json
        return ""


def _drift_registry(tmp_path: Path) -> Path:
    return _difftastic_registry(tmp_path, prefix_template=True)


def test_first_drift_creates_the_issue(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry = _drift_registry(tmp_path)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    gh = _GhRecorder()
    code = main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--issue"],
        probe=_probe(release, assets),
        gh=gh,
    )
    assert code == 1
    assert len(gh.bodies) == 1
    body = gh.bodies[0]
    assert "`difftastic`" in body
    assert "## Passed" not in body
    assert [c[:3] for c in gh.calls] == [
        ["gh", "label", "create"],
        ["gh", "issue", "list"],
        ["gh", "issue", "create"],
    ]
    assert "registry-drift" in gh.calls[0]
    assert capsys.readouterr().out


def test_second_drift_edits_the_open_issue(tmp_path: Path) -> None:
    registry = _drift_registry(tmp_path)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    gh = _GhRecorder(list_json='[{"number": 7}]')
    code = main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--issue"],
        probe=_probe(release, assets),
        gh=gh,
    )
    assert code == 1
    assert gh.calls[-1][:4] == ["gh", "issue", "edit", "7"]
    assert not any(c[1:3] == ["issue", "create"] for c in gh.calls)


def test_drift_beside_an_inconclusive_finding_still_updates_the_issue(
    tmp_path: Path,
) -> None:
    content = """
[[tool]]
id = "bad"
name = "bad"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/good"
asset = "a-{ver}.tar.gz"
member = "bin/x"
strip = 0
[[tool]]
id = "good"
name = "good"
category = "git"
cmd = "y"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/bad"
asset = "b-{ver}.tar.gz"
member = "bin/y"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    good_tar = _gz_tar_bytes({"bin/x": b"x"})
    good_url = "https://github.com/o/good/releases/download/1.0.0/a-1.0.0.tar.gz"
    bad_url = "https://github.com/o/bad/releases/download/1.0.0/b-1.0.0.tar.gz"
    digest = hashlib.sha256(good_tar).hexdigest()
    release_good = Release(tag="1.0.0", digests={"a-1.0.0.tar.gz": digest})

    def rel(repo: str) -> Release:
        if repo == "o/good":
            return release_good
        return Release(tag="1.0.0", digests={})

    def head(url: str) -> str:
        if url == good_url:
            raise _http_error(url, 503)
        if url == bad_url:
            raise _http_error(url, 404)
        return 'etag:"1"'

    probe = Probe(release=rel, head=head, download=lambda _u, _d: None)
    gh = _GhRecorder()
    code = main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--issue"],
        probe=probe,
        gh=gh,
    )
    assert code == 1
    assert gh.bodies
    body = gh.bodies[0]
    assert "## Drift" in body
    assert "## Inconclusive" in body


def test_inconclusive_run_makes_no_gh_call(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)

    def rel(_repo: str) -> Release:
        raise _version_error_from_transport(URLError("net"))

    assets = _canned_difftastic_assets()
    probe = Probe(
        release=rel,
        head=_head_for_release(_release(assets=assets), assets),
        download=_difftastic_download,
    )
    gh = _GhRecorder()
    code = main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--issue"],
        probe=probe,
        gh=gh,
    )
    assert code == 2
    assert gh.calls == []


def test_blocked_run_with_confirmed_drift_still_updates_the_issue(
    tmp_path: Path,
) -> None:
    vendor_url = "https://vendor.example/pkg-1.0.tar.gz"
    pin = hashlib.sha256(_gz_tar_bytes({"bin/x": b"x"})).hexdigest()
    content = f"""
[[tool]]
id = "api"
name = "api"
category = "git"
cmd = "a"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
repo = "o/r"
asset = "x-{{ver}}.tar.gz"
member = "bin/x"
strip = 0
[[tool]]
id = "vendor"
name = "vendor"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/pkg-{{ver}}.tar.gz"
version = "1.0"
member = "bin/x"
strip = 0
sha256 = "{pin}"
"""
    registry = _write_registry(tmp_path, content)
    api = "https://api.github.com/repos/o/r/releases/latest"
    rate_headers = {"X-RateLimit-Remaining": "0"}

    def rel(_repo: str) -> Release:
        raise _version_error_from_http(api, 403, **rate_headers)

    def head(url: str) -> str:
        if url == vendor_url:
            raise _http_error(url, 404)
        return 'etag:"1"'

    probe = Probe(release=rel, head=head, download=lambda _u, _d: None)
    gh = _GhRecorder()
    code = main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--issue"],
        probe=probe,
        gh=gh,
    )
    assert code == 1
    assert len(gh.calls) >= 3
    body = gh.bodies[0]
    lines = body.splitlines()
    assert lines[0].startswith("blocked:")
    assert lines[1].startswith("note: the run was otherwise blocked")
    assert "`vendor`" in body


def test_clean_run_makes_no_gh_call(tmp_path: Path) -> None:
    registry = _difftastic_registry(tmp_path, prefix_template=False)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    gh = _GhRecorder()
    code = main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--issue"],
        probe=_probe(release, assets),
        gh=gh,
    )
    assert code == 0
    assert gh.calls == []


def test_issue_body_carries_no_environment_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GH_TOKEN", "secret-value")
    registry = _drift_registry(tmp_path)
    assets = _canned_difftastic_assets()
    release = _release(assets=assets)
    gh = _GhRecorder()
    main(
        ["--registry", str(registry), "--state", str(tmp_path / "s.json"), "--issue"],
        probe=_probe(release, assets),
        gh=gh,
    )
    blob = " ".join(" ".join(c) for c in gh.calls) + "".join(gh.bodies)
    assert "secret-value" not in blob


def test_issue_code_span_picks_a_safe_delimiter() -> None:
    assert code_span("a.tar.gz") == "`a.tar.gz`"
    assert code_span("a`b") == "``a`b``"
    assert code_span("`x") == "`` `x ``"
    assert code_span("x\ny\r\tz") == "`x y  z`"


def test_issue_body_never_breaks_out_of_a_code_span() -> None:
    report = Report(
        findings=(
            Finding(
                tool_id="t",
                url="https://ex`ample.com/x",
                status="drift",
                reason="boom\n# injected heading",
                member=None,
                platforms=("debian/amd64",),
            ),
        ),
    )
    body = format_report(report, include_passed=False)
    assert not any(line.startswith("# injected") for line in body.splitlines())
    for line in body.splitlines():
        if not line:
            continue
        assert line.startswith(("blocked:", "note:", "## ", "- ", "Unverified")) or line == "- none"


class _SimulatedRunnerKill(BaseException):
    """Stand-in for the runner stopping the verify step mid-run."""


def test_state_is_saved_after_each_verified_asset(tmp_path: Path) -> None:
    tar_a = _gz_tar_bytes({"bin/a": b"a"})
    tar_b = _gz_tar_bytes({"bin/b": b"b"})
    hash_a = hashlib.sha256(tar_a).hexdigest()
    hash_b = hashlib.sha256(tar_b).hexdigest()
    url_a = "https://vendor.example/a-1.0.tar.gz"
    url_b = "https://vendor.example/b-1.0.tar.gz"
    content = f"""
[[tool]]
id = "tool_a"
name = "tool_a"
category = "git"
cmd = "a"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/a-{{ver}}.tar.gz"
version = "1.0"
member = "bin/a"
strip = 0
sha256 = "{hash_a}"
[[tool]]
id = "tool_b"
name = "tool_b"
category = "git"
cmd = "b"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "tarball"
url = "https://vendor.example/b-{{ver}}.tar.gz"
version = "1.0"
member = "bin/b"
strip = 0
sha256 = "{hash_b}"
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="0", assets={})
    key_a = state_key("tool_a", url_a, "bin/a", archive="gz", strip=0, raw=False)

    def download(url: str, dest: Path) -> None:
        if url == url_b:
            raise _SimulatedRunnerKill("stopped after first asset")
        dest.write_bytes(tar_a if url == url_a else tar_b)

    probe = Probe(release=lambda _r: release, head=lambda _u: 'etag:"1"', download=download)
    state_path = tmp_path / "state.json"
    with pytest.raises(_SimulatedRunnerKill):
        main(
            ["--registry", str(registry), "--state", str(state_path)],
            probe=probe,
        )
    saved = json.loads(state_path.read_text())
    assert key_a in saved
    assert saved[key_a]


def test_cache_miss_downloads_every_asset_once(tmp_path: Path) -> None:
    zip_body = _zip_bytes(
        {
            "x86_64-unknown-linux-gnu/bin/a": b"a",
            "aarch64-unknown-linux-gnu/bin/b": b"b",
            "x86_64-apple-darwin/bin/c": b"c",
        }
    )
    digest = hashlib.sha256(zip_body).hexdigest()
    url = "https://github.com/o/shared/releases/download/1.0.0/pkg-1.0.0.zip"
    content = """
[[tool]]
id = "one"
name = "one"
category = "git"
cmd = "x"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
os = ["debian"]
repo = "o/shared"
asset = "pkg-{ver}.zip"
member = "x86_64-unknown-linux-gnu/bin/a"
archive = "zip"
strip = 0
[[tool]]
id = "two"
name = "two"
category = "git"
cmd = "y"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
os = ["debian"]
repo = "o/shared"
asset = "pkg-{ver}.zip"
member = "aarch64-unknown-linux-gnu/bin/b"
archive = "zip"
strip = 0
[[tool]]
id = "three"
name = "three"
category = "git"
cmd = "z"
priority = "P2"
audience = "both"
tier = "user"
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "o/shared"
asset = "pkg-{ver}.zip"
member = "x86_64-apple-darwin/bin/c"
archive = "zip"
strip = 0
"""
    registry = _write_registry(tmp_path, content)
    release = _release(tag="1.0.0", assets={"pkg-1.0.0.zip": digest})
    probe, downloads = _map_probe(release, payloads={"pkg-1.0.0.zip": zip_body})
    state_path = tmp_path / "state.json"
    assert not state_path.exists()
    code = main(["--registry", str(registry), "--state", str(state_path)], probe=probe)
    assert code == 0
    assert downloads[url] == 1
    saved = json.loads(state_path.read_text())
    assert len(saved) == 3
    probe2, downloads2 = _map_probe(release, payloads={"pkg-1.0.0.zip": zip_body})
    code2 = main(["--registry", str(registry), "--state", str(state_path)], probe=probe2)
    assert code2 == 0
    assert sum(downloads2.values()) == 0
