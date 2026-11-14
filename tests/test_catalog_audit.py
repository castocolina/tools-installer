"""Offline tests for installer.catalog_audit (fact gatherer and report writer)."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from installer import catalog_audit
from installer.catalog_audit import FOOTER, Seams, main

DAY = "2026-11-13"
_ALPHA_URL = "https://api.github.com/repos/o/alpha/releases/latest"


def _tool_toml(tool_id: str, methods: str, extra: str = "") -> str:
    return f"""
[[tool]]
id = "{tool_id}"
name = "{tool_id.title()}"
category = "dev"
cmd = "{tool_id}"
tier = "user"
verified = 2026-11-01
{extra}
{methods}
"""


_ALPHA_METHOD = """
[[tool.method]]
kind = "github_release"
repo = "o/alpha"
asset = "alpha-{ver}.tar.gz"
"""
_BETA_METHOD = """
[[tool.method]]
kind = "script"
url = "https://example.com/beta.sh"
shell = "sh"
"""


def _registry(tmp_path: Path, *blocks: str) -> Path:
    path = tmp_path / "registry.toml"
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def _two_entry_registry(tmp_path: Path) -> Path:
    return _registry(
        tmp_path,
        _tool_toml("alpha", _ALPHA_METHOD),
        _tool_toml("beta", _BETA_METHOD),
    )


def _fetch_table(table: Mapping[str, bytes | Exception]) -> Callable[[str], bytes]:
    def fetch(url: str) -> bytes:
        if url not in table:
            raise OSError(f"no canned answer for {url}")
        answer = table[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    return fetch


def _seams(
    table: Mapping[str, bytes | Exception] | None = None,
    *,
    probe: Callable[[list[str]], str | None] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> Seams:
    return Seams(
        fetch=_fetch_table(table or {}),
        probe=probe or (lambda _argv: None),
        which=which or (lambda _name: None),
        home=Path.home(),
        platform_os="debian",
    )


def _root(tmp_path: Path) -> Path:
    root = tmp_path / ".planning" / "audits" / "catalog"
    root.parent.mkdir(parents=True)
    return root


_CHECK_ROWS = (
    "| install method | ok | https://example.com/install |",
    "| update argv | ok | `alpha upgrade` |",
    "| removal recipe and paths | n/a | reason: the vendor ships no uninstaller |",
    "| tuning keys | n/a | reason: no tuning |",
    "| postinstall hook | n/a | reason: no hook |",
)


def _report(
    entry_id: str = "alpha",
    *,
    day: str = DAY,
    latest: str = "- latest: v1.2.3 (https://api.github.com/repos/o/alpha/releases/latest)",
    rows: tuple[str, ...] = _CHECK_ROWS,
    extra: str = "",
) -> str:
    lines = [
        f"# {entry_id} - catalog audit {day}",
        "",
        "## Versions",
        "- pinned: unpinned (github_release)",
        "- verified: 2026-11-01",
        "- installed: not installed",
        latest,
        "",
        "## Changelog",
        "- v1.2.3: nothing relevant",
        "",
        "## Checks",
        "| check | status | source |",
        "|---|---|---|",
        *rows,
        "",
        "## Proposed changes",
        "- none",
    ]
    return "\n".join(lines) + "\n" + extra


def _stdin(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def _run(
    argv: list[str], registry: Path, seams: Seams, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    code = main(argv, registry=registry, seams=seams)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_status_facts_write_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    seams = _seams({_ALPHA_URL: json.dumps({"tag_name": "v1.2.3"}).encode()})
    status = ["status", "--date", DAY, "--root", str(root)]

    code, out, _ = _run(status, registry, seams, capsys)
    assert code == 0
    assert out.splitlines()[:2] == ["next alpha", "complete 0/2"]

    code, out, _ = _run(["facts", "alpha"], registry, seams, capsys)
    assert code == 0
    assert "installed: not installed" in out
    assert f"latest: v1.2.3 ({_ALPHA_URL})" in out

    _stdin(monkeypatch, _report("alpha"))
    code, _, _ = _run(
        ["write", "alpha", "--date", DAY, "--root", str(root)], registry, seams, capsys
    )
    assert code == 0
    written = (root / DAY / "alpha.md").read_text(encoding="utf-8")
    assert written.rstrip("\n").splitlines()[-1] == FOOTER

    code, out, _ = _run(status, registry, seams, capsys)
    assert out.splitlines()[:2] == ["next beta", "complete 1/2"]

    _stdin(monkeypatch, _report("beta"))
    code, _, _ = _run(
        ["write", "beta", "--date", DAY, "--root", str(root)], registry, seams, capsys
    )
    assert code == 0
    code, out, _ = _run(status, registry, seams, capsys)
    assert out.splitlines()[:2] == ["done", "complete 2/2"]


def test_write_refuses_a_row_without_a_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    bad_row = "| install method | ok |  |"
    rows = (bad_row, *_CHECK_ROWS[1:])
    _stdin(monkeypatch, _report("alpha", rows=rows))
    code, _, err = _run(
        ["write", "alpha", "--date", DAY, "--root", str(root)], registry, _seams(), capsys
    )
    assert code == catalog_audit.EXIT_REFUSED
    assert bad_row in err
    assert "source" in err
    assert not (root / DAY / "alpha.md").exists()
