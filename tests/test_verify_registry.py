"""Offline tests for installer.verify_registry (registry drift guard)."""

from __future__ import annotations

import io
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
)

_REPO = "Wilfred/difftastic"
_TAG = "0.71.0"


def _release(
    tag: str = _TAG,
    assets: dict[str, str] | None = None,
) -> Release:
    digests = assets or {}
    return Release(tag=tag, digests=digests)


def _canned_difftastic_assets() -> dict[str, str]:
    digest = "a" * 64
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


def _noop_download(url: str, dest: Path) -> None:
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
        download=download or _noop_download,
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
