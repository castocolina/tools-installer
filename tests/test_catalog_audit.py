"""Offline tests for installer.catalog_audit (fact gatherer and report writer)."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable, Mapping
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from installer import catalog_audit
from installer.catalog_audit import FOOTER, Seams, entry_facts, main
from installer.model import Method, Tool, load_tools

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


# ---- Task 2: the full fact block ----


def _tool(tool_id: str, *methods: Method, cmd: str | None = None, **kwargs: Any) -> Tool:
    return Tool(
        id=tool_id, name=tool_id, category="dev", cmd=cmd or tool_id, methods=methods, **kwargs
    )


def _facts(
    tool: Tool,
    *others: Tool,
    seams: Seams | None = None,
    verified: Mapping[str, str] | None = None,
) -> str:
    return entry_facts(tool, [tool, *others], seams or _seams(), verified=verified)


def test_facts_one_record_per_entry_in_registry_order() -> None:
    tools = load_tools(catalog_audit.REGISTRY)
    blocks = [entry_facts(tool, tools, _seams()) for tool in tools]
    heads = [block.splitlines()[0] for block in blocks]
    assert heads == [f"# facts: {tool.id}" for tool in tools]
    assert all("- latest: " in block and "- installed: " in block for block in blocks)


def test_facts_fields() -> None:
    home = Path.home()
    unpinned = _tool(
        "unpinned",
        Method("script", {"url": "https://example.com/i.sh", "paths": ["~/.local/bin/unpinned"]}),
        Method("pacman", {"package": "unpinned"}),
        Method("brew", {"formula": "unpinned"}),
    )
    text = _facts(unpinned, verified={"unpinned": "2026-11-01"})
    assert "- pinned: unpinned (script, pacman, brew)" in text
    assert "- verified: 2026-11-01" in text
    assert "- paths: ~/.local/bin/unpinned" in text
    assert "- update: none (the installer re-runs the method)" in text
    assert "- remove: none" in text
    assert "- postinstall: none" in text
    assert "- post_install: none" in text
    assert "  - script (os: all, arch: all)" in text

    pinned = _tool("pinned", Method("app", {"url": "https://e.com/{ver}.zip", "version": "32.6.1"}))
    assert "- pinned: 32.6.1 (app version param)" in _facts(pinned)

    scripted = _tool(
        "scripted",
        Method(
            "script",
            {
                "url": f"https://e.com/{home}/x",
                "update": ["scripted", "self", "update"],
                "remove": ["scripted", "uninstall"],
            },
            os=("macos",),
            arch=("arm64",),
        ),
        postinstall="codegraph-mcp-register",
        post_install=("apply_agent_tuning", "show_lean_tips"),
    )
    text = _facts(scripted)
    assert "- update: scripted self update" in text
    assert "- remove: scripted uninstall" in text
    assert (
        "- postinstall: codegraph-mcp-register (targets: claude, codex, opencode, cursor)" in text
    )
    assert "- post_install: apply_agent_tuning, show_lean_tips" in text
    assert "(os: macos, arch: arm64)" in text
    assert str(home) not in text

    tuned = _facts(_tool("claude", Method("script", {"url": "https://e.com/i.sh"})))
    assert "auto-approve: permissions.defaultMode, skipDangerousModePermissionPrompt" in tuned
    assert "no-attribution: attribution.commit, attribution.pr" in tuned
    assert "bypassPermissions" not in tuned


_GH_URL = "https://api.github.com/repos/o/r/releases/latest"
_NPM_URL = "https://registry.npmjs.org/-/package/@scope%2Fpkg/dist-tags"
_ARCH_BODY = {
    "results": [
        {"pkgname": "foo-git", "pkgver": "0", "pkgrel": "1", "repo": "aur"},
        {"pkgname": "foo", "pkgver": "1.2.3", "pkgrel": "2", "repo": "extra"},
    ]
}
_FORMULA_URL = "https://formulae.brew.sh/api/formula/jq.json"
_CASK_URL = "https://formulae.brew.sh/api/cask/zed.json"
_ARCH_URL = "https://archlinux.org/packages/search/json/?name=foo"
_FEDORA_URL = "https://mdapi.fedoraproject.org/rawhide/pkg/foo"
_DEBIAN_URL = "https://sources.debian.org/api/src/foo/"
_PYPI_URL = "https://pypi.org/pypi/foo/json"
_LATEST_CASES: list[tuple[Method, str, object, str]] = [
    (Method("github_release", {"repo": "o/r"}), _GH_URL, {"tag_name": "v9.9.9"}, "v9.9.9"),
    (Method("node", {"npm_pkg": "@scope/pkg"}), _NPM_URL, {"latest": "2.3.0"}, "2.3.0"),
    (
        Method("script", {"url": "u", "latest_npm": "@scope/pkg"}),
        _NPM_URL,
        {"latest": "2.3.0"},
        "2.3.0",
    ),
    (Method("brew", {"formula": "jq"}), _FORMULA_URL, {"versions": {"stable": "1.8.1"}}, "1.8.1"),
    (Method("cask", {"cask": "zed"}), _CASK_URL, {"version": "0.9.1"}, "0.9.1"),
    (Method("pacman", {"package": "foo"}), _ARCH_URL, _ARCH_BODY, "1.2.3-2 (extra)"),
    (
        Method("dnf", {"package": "foo"}),
        _FEDORA_URL,
        {"version": "1.2.3", "release": "4.fc45"},
        "1.2.3-4.fc45 (Fedora rawhide)",
    ),
    (
        Method("apt", {"package": "foo"}),
        _DEBIAN_URL,
        {"versions": [{"version": "1.2.3-1"}, {"version": "0.1"}]},
        "1.2.3-1",
    ),
    (Method("uv-tool", {"pypi_pkg": "foo"}), _PYPI_URL, {"info": {"version": "0.5.1"}}, "0.5.1"),
]


@pytest.mark.parametrize(("method", "url", "body", "value"), _LATEST_CASES)
def test_facts_latest_sources(method: Method, url: str, body: object, value: str) -> None:
    seams = _seams({url: json.dumps(body).encode()})
    assert f"- latest: {value} ({url})" in _facts(_tool("demo", method), seams=seams)


@pytest.mark.parametrize(
    ("method", "line"),
    [
        (
            Method("brew", {"formula": "a/b/c"}),
            "- latest: unknown: tap formula, not on formulae.brew.sh",
        ),
        (
            Method("sdkman", {"candidate": "java"}),
            "- latest: unknown: not read by the gatherer (sdkman)",
        ),
        (
            Method("host_setup", {"setup_id": "x"}),
            "- latest: unknown: not read by the gatherer (host_setup)",
        ),
        (Method("app", {"url": "u"}), "- latest: see verify-registry.md (app)"),
        (Method("tarball", {"url": "u"}), "- latest: see verify-registry.md (tarball)"),
        (Method("script", {"url": "u"}), "- latest: unknown: no latest source declared"),
    ],
)
def test_facts_sources_without_a_fetch(method: Method, line: str) -> None:
    assert line in _facts(_tool("demo", method)).splitlines()


def test_facts_fetches_each_url_once() -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return b'{"tag_name": "v1"}'

    seams = Seams(
        fetch=fetch,
        probe=lambda _a: None,
        which=lambda _n: None,
        home=Path.home(),
        platform_os="",
    )
    methods = (
        Method("github_release", {"repo": "o/r"}),
        Method("cargo_distrobox", {"repo": "o/r"}),
    )
    text = _facts(_tool("demo", *methods), seams=seams)
    assert calls == [_GH_URL]
    assert text.count("- latest: ") == 1


def _http(code: int, reason: str) -> HTTPError:
    return HTTPError("https://x", code, reason, Message(), None)


_GH_METHOD = Method("github_release", {"repo": "o/r"})


@pytest.mark.parametrize(
    ("method", "url", "answer", "needle"),
    [
        (_GH_METHOD, _GH_URL, _http(403, "rate limit exceeded"), "403"),
        (_GH_METHOD, _GH_URL, _http(429, "slow down"), "429"),
        (_GH_METHOD, _GH_URL, _http(500, "boom"), "500"),
        (_GH_METHOD, _GH_URL, TimeoutError(), "TimeoutError"),
        (_GH_METHOD, _GH_URL, b"not json", "JSONDecodeError"),
        (Method("apt", {"package": "foo"}), _DEBIAN_URL, b'{"error": 404}', "404"),
        (Method("pacman", {"package": "foo"}), _ARCH_URL, b'{"results": []}', "foo"),
    ],
)
def test_facts_unknown_reasons(
    method: Method, url: str, answer: bytes | Exception, needle: str
) -> None:
    text = _facts(_tool("demo", method), seams=_seams({url: answer}))
    (line,) = [ln for ln in text.splitlines() if ln.startswith("- latest: ")]
    assert line.startswith("- latest: unknown: ")
    assert needle in line


def test_facts_major_split() -> None:
    npm = "https://registry.npmjs.org/-/package/pkg/dist-tags"
    seams = _seams({_GH_URL: b'{"tag_name": "v1.19.5"}', npm: b'{"latest": "2.3.0"}'})
    tool = _tool("demo", _GH_METHOD, Method("script", {"url": "u", "latest_npm": "pkg"}))
    assert "- note: major split: v1.19.5 (github) vs 2.3.0 (npm)" in _facts(tool, seams=seams)
    same = _seams({_GH_URL: b'{"tag_name": "v2.0.0"}', npm: b'{"latest": "2.3.0"}'})
    assert "major split" not in _facts(tool, seams=same)


def test_facts_cross_reference() -> None:
    one = _tool("one", Method("github_release", {"repo": "o/r"}))
    two = _tool("two", Method("github_release", {"repo": "o/r"}))
    three = _tool("three", Method("brew", {"formula": "x"}), cmd="shared")
    four = _tool("four", Method("brew", {"formula": "y"}), cmd="shared")
    lone = _tool("lone", Method("brew", {"formula": "z"}))
    everyone = (one, two, three, four, lone)
    for tool, other in ((one, "two"), (two, "one"), (three, "four"), (four, "three")):
        assert f"- see also: {other}" in entry_facts(tool, everyone, _seams())
    assert "see also" not in entry_facts(lone, everyone, _seams())


def test_facts_installed_version() -> None:
    binary = Path.home() / ".opencode" / "bin" / "opencode"
    binary.parent.mkdir(parents=True)
    binary.touch()
    tool = _tool("opencode", Method("script", {"url": "u", "bin_dir": "~/.opencode/bin"}))
    recorded: list[list[str]] = []

    def probe(argv: list[str]) -> str | None:
        recorded.append(argv)
        return "opencode v2.0.31"

    text = _facts(tool, seams=_seams(probe=probe))
    assert recorded == [[str(binary), "--version"]]
    expected = (
        "- installed: v2.0.31 "
        "(~/.opencode/bin/opencode --version; bin_dir first, then the PATH hit)"
    )
    assert expected in text
    unparsed = _facts(tool, seams=_seams(probe=lambda _a: "no version here"))
    assert "- installed: unknown: no version in the --version output" in unparsed
    assert "- installed: not installed" in _facts(tool, seams=_seams(probe=lambda _a: None))


def test_facts_reads_the_version_file_first() -> None:
    sdkman = next(t for t in load_tools(catalog_audit.REGISTRY) if t.id == "sdkman")
    recorded: list[list[str]] = []

    def probe(argv: list[str]) -> str | None:
        recorded.append(argv)
        return "never"

    assert "- installed: not installed" in _facts(sdkman, seams=_seams(probe=probe))
    version_file = Path.home() / ".sdkman" / "var" / "version"
    version_file.parent.mkdir(parents=True)
    version_file.write_text("5.19.0\n", encoding="utf-8")
    assert "- installed: 5.19.0 (~/.sdkman/var/version)" in _facts(
        sdkman, seams=_seams(probe=probe)
    )
    assert recorded == []


@pytest.mark.parametrize(
    ("found", "line"),
    [
        ("podman", "- container: podman"),
        ("docker", "- container: docker"),
        (
            "",
            '- container: none (rows that need a container read "unknown: '
            'container check not run")',
        ),
    ],
)
def test_facts_container_runtime(found: str, line: str) -> None:
    seams = _seams(which=lambda name: f"/usr/bin/{name}" if name == found else None)
    assert line in _facts(_tool("demo", Method("brew", {"formula": "x"})), seams=seams)
