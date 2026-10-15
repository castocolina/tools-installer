"""Offline tests for installer.verify_registry (registry drift guard)."""

from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from collections import defaultdict
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

import pytest

from installer.model import load_tools
from installer.verify_registry import (
    Probe,
    Release,
    check_registry,
    format_report,
    main,
    state_key,
)

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
    assert all(f.status == "ok" for f in report.findings)


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
