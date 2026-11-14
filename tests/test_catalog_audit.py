"""Offline tests for installer.catalog_audit (fact gatherer and report writer)."""

from __future__ import annotations

import io
import json
import os
import sys
import tomllib
from collections.abc import Callable, Mapping
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from installer import catalog_audit, verify_registry
from installer.catalog_audit import FOOTER, Seams, entry_facts, main
from installer.model import Method, Tool, load_tools
from tests.home_fingerprint import fingerprint, fingerprint_diff

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
    targets = "claude, codex, opencode, cursor, copilot, pi"
    assert f"- postinstall: codegraph-mcp-register (targets: {targets})" in text
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


# ---- Task 3: the writer's guards, resume edges, confinement and host safety ----


def _write_argv(entry_id: str, root: Path, day: str = DAY) -> list[str]:
    return ["write", entry_id, "--date", day, "--root", str(root)]


def _secret_cases() -> list[tuple[str, str]]:
    return [
        ("ghp", "ghp_" + "a" * 36),
        ("github_pat", "github_pat_" + "A1" * 15),
        ("sk", "sk-" + "a" * 32),
        ("xoxb", "xoxb-" + "1234567890-abcdef"),
        ("akia", "AKIA" + "A" * 16),
        ("private key", "-----BEGIN OPENSSH PRIVATE KEY-----"),
        ("bearer", "Bearer " + "a" * 24),
        ("gho", "gho_" + "a" * 36),
        ("ghs", "ghs_" + "a" * 36),
        ("ghu", "ghu_" + "a" * 36),
        ("ghr", "ghr_" + "a" * 36),
        ("npm", "npm_" + "a" * 36),
        ("gitlab", "glpat-" + "a" * 20),
        ("google", "AIza" + "a" * 35),
        ("authorization", "Authorization: token " + "a1b2c3d4" * 3),
    ]


def _refusal_reports() -> list[tuple[str, str]]:
    rows = _CHECK_ROWS
    swapped = (rows[1], rows[0], *rows[2:])
    cases = {
        "sixth row": _report(rows=(*rows, "| extra | ok | `x` |")),
        "missing row": _report(rows=rows[:4]),
        "rows out of order": _report(rows=swapped),
        "status fine": _report(rows=(rows[0].replace("| ok |", "| fine |"), *rows[1:])),
        "n/a without reason": _report(
            rows=(*rows[:3], "| tuning keys | n/a | no tuning |", rows[4])
        ),
        "ok with prose": _report(rows=("| install method | ok | it just works |", *rows[1:])),
        "all latest unknown": _report(latest="- latest: unknown: HTTPError: HTTP Error 403"),
        "home path": _report().replace("nothing relevant", "see <HOME>/x"),
        "footer present": _report(extra=FOOTER + "\n"),
        "wrong title id": _report("beta"),
        "wrong title date": _report(day="2026-11-12"),
        "unknown section": _report().replace("## Changelog", "## Notes"),
    }
    for name, secret in _secret_cases():
        cases[f"secret {name}"] = _report().replace("nothing relevant", f"token {secret}")
    return list(cases.items())


@pytest.mark.parametrize(("name", "report"), _refusal_reports(), ids=lambda v: v[:24])
def test_write_refusals(
    name: str,
    report: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _root(tmp_path)
    _stdin(monkeypatch, report.replace("<HOME>", str(Path.home())))
    code, _, err = _run(_write_argv("alpha", root), _two_entry_registry(tmp_path), _seams(), capsys)
    assert code == catalog_audit.EXIT_REFUSED, name
    assert err.startswith("refused: ")
    assert not (root / DAY / "alpha.md").exists()
    for _, secret in _secret_cases():
        assert secret not in err


def test_write_never_rewrites_a_complete_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    _stdin(monkeypatch, _report())
    assert _run(_write_argv("alpha", root), registry, _seams(), capsys)[0] == 0
    target = root / DAY / "alpha.md"
    before = (target.read_bytes(), target.stat().st_mtime_ns)
    _stdin(monkeypatch, _report().replace("nothing relevant", "something else"))
    code, _, err = _run(_write_argv("alpha", root), registry, _seams(), capsys)
    assert code == catalog_audit.EXIT_REFUSED
    assert "already complete" in err
    assert (target.read_bytes(), target.stat().st_mtime_ns) == before


def test_write_refuses_a_symlinked_leaf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    (root / DAY).mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere.md"
    (root / DAY / "alpha.md").symlink_to(elsewhere)
    _stdin(monkeypatch, _report())
    code, _, err = _run(_write_argv("alpha", root), _two_entry_registry(tmp_path), _seams(), capsys)
    assert code == catalog_audit.EXIT_REFUSED
    assert "symlink" in err
    assert not elsewhere.exists()


def _numbered_registry(tmp_path: Path, count: int) -> Path:
    return _registry(tmp_path, *(_tool_toml(f"t{n}", _BETA_METHOD) for n in range(1, count + 1)))


def test_resume_after_entry_k(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _numbered_registry(tmp_path, 5)
    root = _root(tmp_path)
    status = ["status", "--date", DAY, "--root", str(root)]
    for n in (1, 2, 3):
        _stdin(monkeypatch, _report(f"t{n}"))
        assert _run(_write_argv(f"t{n}", root), registry, _seams(), capsys)[0] == 0
    out = _run(status, registry, _seams(), capsys)[1]
    assert out.splitlines()[:2] == ["next t4", "complete 3/5"]
    frozen = {n: (root / DAY / f"t{n}.md").read_bytes() for n in (1, 2, 3)}
    for n in (4, 5):
        _stdin(monkeypatch, _report(f"t{n}"))
        assert _run(_write_argv(f"t{n}", root), registry, _seams(), capsys)[0] == 0
    assert {n: (root / DAY / f"t{n}.md").read_bytes() for n in (1, 2, 3)} == frozen
    assert _run(status, registry, _seams(), capsys)[1].splitlines()[:2] == ["done", "complete 5/5"]


def test_interrupted_write_is_not_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)

    def boom(_src: object, _dst: object) -> None:
        raise OSError("disk went away")

    _stdin(monkeypatch, _report())
    with monkeypatch.context() as patched:
        patched.setattr(os, "replace", boom)
        code, _, _ = _run(_write_argv("alpha", root), registry, _seams(), capsys)
    assert code == catalog_audit.EXIT_INTERNAL
    assert not (root / DAY / "alpha.md").exists()
    (root / DAY / "alpha.md.1.abc.tools-installer.tmp").write_text("half", encoding="utf-8")
    out = _run(["status", "--date", DAY, "--root", str(root)], registry, _seams(), capsys)[1]
    assert out.splitlines() == ["next alpha", "complete 0/2"]


def test_two_writers_same_date(tmp_path: Path) -> None:
    root = _root(tmp_path)
    run = root / DAY
    home = Path.home()
    alpha = catalog_audit.write_report(run, "alpha", _report("alpha"), home=home)
    beta = catalog_audit.write_report(run, "beta", _report("beta"), home=home)
    assert alpha.read_text(encoding="utf-8").endswith(FOOTER + "\n")
    assert beta.read_text(encoding="utf-8").endswith(FOOTER + "\n")
    before = alpha.read_bytes()
    with pytest.raises(catalog_audit.ReportRefused, match="already complete"):
        catalog_audit.write_report(run, "alpha", _report("alpha"), home=home)
    assert alpha.read_bytes() == before


def test_orphan_report_is_listed_not_deleted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    run = root / DAY
    run.mkdir(parents=True)
    (run / "gone.md").write_text("# gone\n\n" + FOOTER + "\n", encoding="utf-8")
    (run / "SUMMARY.md").write_text("summary\n", encoding="utf-8")
    out = _run(["status", "--date", DAY, "--root", str(root)], registry, _seams(), capsys)[1]
    assert out.splitlines() == ["next alpha", "complete 0/2", "orphan gone"]
    assert (run / "gone.md").exists()


def _usage_cases(tmp_path: Path) -> list[tuple[list[str], Path]]:
    root = _root(tmp_path)
    linked = tmp_path / "linked" / ".planning" / "audits"
    linked.mkdir(parents=True)
    (linked / "catalog").symlink_to(tmp_path / "real")
    run_linked = tmp_path / "rl" / ".planning" / "audits" / "catalog"
    (run_linked).mkdir(parents=True)
    (run_linked / DAY).symlink_to(tmp_path / "real")
    (tmp_path / "real").mkdir()
    bare = tmp_path / "bare" / "audits" / "catalog"
    status = ["status", "--date"]
    return [
        ([*status, "2026-13-01", "--root", str(root)], root),
        ([*status, "../x", "--root", str(root)], root),
        ([*status, "2026-1-1", "--root", str(root)], root),
        (_write_argv("nope", root), root),
        (["facts", "nope"], root),
        (["facts", "a/b"], root),
        (_write_argv("alpha", linked / "catalog"), linked / "catalog"),
        (_write_argv("alpha", run_linked), run_linked),
        (_write_argv("alpha", bare), bare),
        (["frobnicate"], root),
    ]


def _snapshot(base: Path) -> dict[str, int]:
    return {
        str(path): path.lstat().st_mtime_ns
        for path in [base, *base.rglob("*")]
        if path.exists() or path.is_symlink()
    }


def test_usage_refusals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    cases = _usage_cases(tmp_path)
    for argv, _ in cases:
        _stdin(monkeypatch, _report())
        before = _snapshot(tmp_path)
        code, _, err = _run(argv, registry, _seams(), capsys)
        assert code == catalog_audit.EXIT_USAGE, argv
        assert err.startswith("catalog-audit: "), argv
        assert _snapshot(tmp_path) == before, argv


def test_cli_confined_to_the_run_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    seams = _seams({_ALPHA_URL: b'{"tag_name": "v1"}'})
    root.mkdir()
    before = _snapshot(tmp_path)
    _run(["status", "--date", DAY, "--root", str(root)], registry, seams, capsys)
    _run(["facts", "alpha"], registry, seams, capsys)
    for entry in ("alpha", "beta"):
        _stdin(monkeypatch, _report(entry))
        assert _run(_write_argv(entry, root), registry, seams, capsys)[0] == 0
    after = _snapshot(tmp_path)
    run = root / DAY
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    assert changed
    for path in changed:
        assert Path(path) == root or Path(path).is_relative_to(run), path


def test_facts_hostsafe_fingerprint_and_probe_allowlist(tmp_path: Path) -> None:
    home = Path.home()
    config = home / ".config" / "opencode" / "opencode.jsonc"
    config.parent.mkdir(parents=True)
    canary = "canary-value-9f3a"
    config.write_text(json.dumps({"token": canary}), encoding="utf-8")
    (home / ".local" / "state" / "tools-installer" / "receipts").mkdir(parents=True)
    recorded: list[list[str]] = []

    def probe(argv: list[str]) -> str | None:
        recorded.append(argv)
        return None

    tools = load_tools(catalog_audit.REGISTRY)
    before = fingerprint(home, {})
    blocks = [entry_facts(tool, tools, _seams(probe=probe)) for tool in tools]
    assert fingerprint_diff(before, fingerprint(home, {})) == []
    assert recorded
    assert all(len(argv) == 2 and argv[-1] == "--version" for argv in recorded)
    text = "".join(blocks)
    assert canary not in text
    assert str(home) not in text


def test_main_never_prints_the_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from installer import versions

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    tokens: list[str | None] = []

    def fake_fetch(url: str, *, token: str | None = None) -> bytes:
        tokens.append(token)
        return b'{"tag_name": "v1"}'

    monkeypatch.setattr(versions, "urlopen_fetch", fake_fetch)

    def no_probe(_argv: list[str]) -> str | None:
        return None

    monkeypatch.setattr(versions, "probe_version_output", no_probe)
    gh_calls: list[list[str]] = []

    def gh(argv: list[str]) -> str:
        gh_calls.append(argv)
        return "secret-token-value"

    code = main(["facts", "alpha"], registry=_two_entry_registry(tmp_path), gh=gh)
    captured = capsys.readouterr()
    assert code == 0
    assert gh_calls == [["gh", "auth", "token"]]
    assert tokens == ["secret-token-value"]
    assert "secret-token-value" not in captured.out + captured.err


# ---- 24.3-03 Task 1: verify record, script scan, summary ----


def _main(
    argv: list[str],
    registry: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    verify_main: Callable[[list[str]], int] | None = None,
) -> tuple[int, str, str]:
    code = main(argv, registry=registry, seams=_seams(), verify_main=verify_main)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _verify_fake(
    calls: list[list[str]], *, code: int = 1, report: str = "## Drift\n- alpha: newer stable\n"
) -> Callable[[list[str]], int]:
    def fake(argv: list[str]) -> int:
        calls.append(list(argv))
        print(report, end="")
        return code

    return fake


def _store(root: Path, entry_id: str, text: str) -> None:
    catalog_audit.write_report(root / DAY, entry_id, text, home=Path.home())


_DRIFT_ROWS = (
    "| install method | drift | https://example.invalid/x |",
    *_CHECK_ROWS[1:],
)


def _repo(tmp_path: Path, files: Mapping[str, str] | None = None) -> Path:
    repo = tmp_path / "repo"
    for name, body in (files or {"scripts/x.sh": "echo hi\n"}).items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(body, encoding="utf-8")
    return repo


def test_verify_scan_summarize_round_trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    _store(root, "alpha", _report("alpha", rows=_DRIFT_ROWS))
    _store(root, "beta", _report("beta"))
    repo = _repo(tmp_path)
    calls: list[list[str]] = []
    state = tmp_path / "p243e03-state.json"

    code, _, _ = _main(
        ["verify", "--date", DAY, "--root", str(root), "--state", str(state)],
        registry,
        capsys,
        verify_main=_verify_fake(calls),
    )
    assert code == 0
    assert calls == [["--state", str(state)]]
    record = (root / DAY / "verify-registry.md").read_text(encoding="utf-8")
    assert record.startswith(f"# verify-registry - {DAY}\nexit: 1\n")
    assert "## Drift\n- alpha: newer stable\n" in record

    argv = ["scan", "--date", DAY, "--root", str(root), "--repo", str(repo)]
    assert _main(argv, registry, capsys)[0] == 0
    scripts = (root / DAY / "scripts.md").read_text(encoding="utf-8")
    assert "| scripts/x.sh | (maintainer) | ok |" in scripts

    argv = ["summarize", "--date", DAY, "--root", str(root), "--repo", str(repo)]
    assert _main(argv, registry, capsys)[0] == 0
    summary = (root / DAY / "SUMMARY.md").read_text(encoding="utf-8")
    assert "alpha | install method | drift | https://example.invalid/x | proposed" in summary
    assert "exit: 1" in summary
    assert "- alpha: newer stable" in summary
    assert "scripts/x.sh (maintainer): ok" in summary
    assert "no proposed changes" in summary


def _verify_cases(tmp_path: Path) -> dict[str, list[str]]:
    default = verify_registry.default_state_path()
    link = tmp_path / "p243e03-link.json"
    link.symlink_to(default)
    in_repo = Path(catalog_audit.__file__).resolve().parents[1] / "p243e03-state.json"
    not_json = tmp_path / "p243e03-notjson.json"
    not_json.write_text("not json", encoding="utf-8")
    return {
        "missing": [],
        "default": ["--state", str(default)],
        "symlink": ["--state", str(link)],
        "in-repo": ["--state", str(in_repo)],
        "non-json": ["--state", str(not_json)],
    }


@pytest.mark.parametrize("kind", ["missing", "default", "symlink", "in-repo", "non-json"])
def test_verify_requires_a_scratch_state(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    state_argv = _verify_cases(tmp_path)[kind]
    calls: list[list[str]] = []
    code, _, err = _main(
        ["verify", "--date", DAY, "--root", str(root), *state_argv],
        registry,
        capsys,
        verify_main=_verify_fake(calls),
    )
    assert code == catalog_audit.EXIT_USAGE, err
    assert calls == []
    assert not (root / DAY / "verify-registry.md").exists()


def test_verify_copies_the_warm_state_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    warm = verify_registry.default_state_path()
    warm.parent.mkdir(parents=True)
    warm.write_text('{"warm": true}', encoding="utf-8")
    os.utime(warm, ns=(1_000_000_000, 1_000_000_000))
    before = (warm.read_bytes(), warm.stat().st_mtime_ns)
    state = tmp_path / "scratch" / "p243e03-state.json"
    seen: list[bytes] = []

    def fake(argv: list[str]) -> int:
        seen.append(Path(argv[1]).read_bytes())
        return 0

    code, _, _ = _main(
        ["verify", "--date", DAY, "--root", str(root), "--state", str(state)],
        registry,
        capsys,
        verify_main=fake,
    )
    assert code == 0
    assert seen == [before[0]]
    assert (warm.read_bytes(), warm.stat().st_mtime_ns) == before


# ---- 24.3-03 Task 2: the script scan's mechanical checks and stale citations ----

_INSTALLER = Path(catalog_audit.__file__).resolve().parent
_NO_SCHEMAS: Mapping[str, Mapping[str, object]] = {}


def _scan_rows(
    tmp_path: Path,
    files: Mapping[str, str],
    *,
    tools: tuple[Tool, ...] = (),
    schemas: Mapping[str, Mapping[str, object]] = _NO_SCHEMAS,
) -> list[catalog_audit.ScanRow]:
    return catalog_audit.scan(_repo(tmp_path, files), tools, schemas)


def _found(rows: list[catalog_audit.ScanRow]) -> list[tuple[str, int]]:
    return [(row.path, row.line) for row in rows if row.status == "finding"]


def test_scan_elevation_heads(tmp_path: Path) -> None:
    python = (
        'A = ["sudo", "dnf"]\n'
        'B = ("doas", "x")\n'
        'C = ["/usr/bin/pkexec", "x"]\n'
        'print("run sudo dnf install x")\n'
        'print(f"sudo dnf install {A}")\n'
        'D = ["dnf", "sudo"]\n'
    )
    shell = (
        "sudo rm x\n"
        "a; sudo rm x\n"
        "a && sudo rm x\n"
        "a || sudo rm x\n"
        "a | sudo rm x\n"
        "y=$(sudo rm x)\n"
        "# sudo x\n"
        'echo "run sudo x"\n'
        "printf 'sudo x\\n'\n"
        "echo sudo\n"
    )
    rows = _scan_rows(tmp_path, {"installer/guards.py": python, "scripts/a.sh": shell})
    assert _found(rows) == [
        ("installer/guards.py", 1),
        ("installer/guards.py", 2),
        ("installer/guards.py", 3),
        ("scripts/a.sh", 1),
        ("scripts/a.sh", 2),
        ("scripts/a.sh", 3),
        ("scripts/a.sh", 4),
        ("scripts/a.sh", 5),
        ("scripts/a.sh", 6),
    ]
    assert rows[0].pattern.startswith("`sudo`")


def test_scan_target_auto_or_all(tmp_path: Path) -> None:
    python = (
        'A = ["--target", "auto"]\n'
        'B = ["--target", "all"]\n'
        'C = "x --target=auto"\n'
        'D = ["--target", csv]\n'
        'E = ["--target", "claude,codex"]\n'
        'F = "--target auto"\n'
    )
    rows = _scan_rows(tmp_path, {"installer/guards.py": python})
    assert _found(rows) == [("installer/guards.py", n) for n in (1, 2, 3, 6)]
    assert rows[0].pattern.startswith("`--target`")
    assert rows[2].pattern.startswith("`--target=auto`")


_MAPS = (
    '_CODEGRAPH_TARGETS = {"claude": "claude", "ghost-host": "ghost"}\n'
    'POSTINSTALL_HOOKS = {"codegraph-mcp-register": HookPair(targets=_CODEGRAPH_TARGETS)}\n'
)


def test_scan_hook_target_keys_outside_presence(tmp_path: Path) -> None:
    hooked = _tool("codegraph", postinstall="codegraph-mcp-register")
    rows = _scan_rows(tmp_path, {"installer/postinstall.py": _MAPS}, tools=(hooked,))
    assert [(r.line, r.entry) for r in rows if r.status == "finding"] == [(1, "codegraph")]
    assert "`ghost-host`" in rows[0].pattern
    shipped = (_INSTALLER / "postinstall.py").read_text(encoding="utf-8")
    clean = _scan_rows(tmp_path / "shipped", {"installer/postinstall.py": shipped})
    assert [r for r in clean if r.status == "finding"] == []


@pytest.mark.parametrize(
    ("exec_line", "clean"),
    [
        ('exec "$real" "$@"', True),
        ('exec pnpm dlx "$@"', False),
        ('exec "$real" --model x "$@"', False),
        ('exec "$real"', False),
    ],
)
def test_scan_shim_exec_rewrites(tmp_path: Path, exec_line: str, clean: bool) -> None:
    source = f"SHIM = '''#!/bin/sh\n{exec_line}\n'''\n"
    rows = _scan_rows(tmp_path, {"installer/env_redirect.py": source})
    if clean:
        assert _found(rows) == []
    else:
        assert _found(rows) == [("installer/env_redirect.py", 2)]
        assert exec_line in rows[0].pattern


def test_scan_reads_f_string_shims_offline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    guards = (_INSTALLER / "guards.py").read_text(encoding="utf-8")
    cursor = (_INSTALLER / "cursor_shim.py").read_text(encoding="utf-8")
    files = {"installer/guards.py": guards, "installer/cursor_shim.py": cursor}
    repo = _repo(tmp_path, files)
    rows = catalog_audit.scan(repo, (), _NO_SCHEMAS)

    def at(text: str, needle: str) -> int:
        return next(n for n, line in enumerate(text.splitlines(), 1) if needle in line)

    npx = ("installer/guards.py", at(guards, 'exec {shlex.quote(target_path)} {quoted_args} "$@"'))
    shim = ("installer/cursor_shim.py", at(cursor, 'exec "$target" {flag}'))
    mid = ("installer/cursor_shim.py", at(cursor, 'exec "$target" "$@";;'))
    assert npx in _found(rows)
    assert shim in _found(rows)
    assert mid not in _found(rows)
    assert next(r for r in rows if (r.path, r.line) == npx).pattern.startswith("`exec `")
    assert next(r for r in rows if (r.path, r.line) == shim).pattern.startswith('`exec "$target" `')

    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    run = root / DAY
    run.mkdir(parents=True)
    (run / "scripts.md").write_text(catalog_audit.scan_text(DAY, rows), encoding="utf-8")
    code, _, err = _main(
        ["summarize", "--date", DAY, "--root", str(root), "--repo", str(repo)], registry, capsys
    )
    assert code == 0, err
    summary = (run / "SUMMARY.md").read_text(encoding="utf-8")
    for path, line in (npx, shim):
        assert _script_row(summary, f"{path}:{line}")[4] == "current"


def _script_row(summary: str, location: str) -> list[str]:
    row = next(line for line in summary.splitlines() if line.startswith(f"| {location} |"))
    return [cell.strip() for cell in row.strip("|").split("|")]


_OPENCODE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "permission": {"$ref": "#/$defs/PermissionConfig", "deprecated": True},
        "permissions": {"type": "array"},
    },
    "$defs": {"PermissionConfig": {}},
}


def _keys_source(path: str) -> str:
    return (
        "from installer.agent_settings import SettingKey\n"
        f'_KEYS = {{("opencode", "auto-approve"): (SettingKey(("{path}",), "allow"),)}}\n'
    )


@pytest.mark.parametrize(
    ("key", "pattern"),
    [
        ("permission", "`permission` deprecated in the opencode schema"),
        ("nope", "`nope` not allowed in the opencode schema"),
        ("permissions", None),
    ],
)
def test_scan_schema_flags_the_opencode_permission_key(
    key: str,
    pattern: str | None,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    repo = _repo(tmp_path, {"installer/agent_settings.py": _keys_source(key)})
    schema = tmp_path / "p243e03-opencode.json"
    schema.write_text(json.dumps(_OPENCODE_SCHEMA), encoding="utf-8")
    argv = ["scan", "--date", DAY, "--root", str(root), "--repo", str(repo)]
    code, _, err = _main([*argv, "--schema", f"opencode={schema}"], registry, capsys)
    assert code == 0, err
    scripts = (root / DAY / "scripts.md").read_text(encoding="utf-8")
    if pattern is None:
        assert "| installer/agent_settings.py | (installer) | ok |" in scripts
        assert "finding" not in scripts
    else:
        assert f"| installer/agent_settings.py:2 | opencode | finding | {pattern}" in scripts


def test_scan_rejects_a_bad_schema_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    bad = tmp_path / "p243e03-bad.json"
    bad.write_text("[1]", encoding="utf-8")
    base = ["scan", "--date", DAY, "--root", str(root), "--repo", str(_repo(tmp_path))]
    for spec in ("opencode", "opencode=", f"opencode={tmp_path}/missing.json", f"opencode={bad}"):
        code, _, _ = _main([*base, "--schema", spec], registry, capsys)
        assert code == catalog_audit.EXIT_USAGE, spec


def test_scan_rows_name_their_entry(tmp_path: Path) -> None:
    hooked = _tool("codegraph", postinstall="codegraph-mcp-register")
    files = {
        "installer/agent_settings.py": _keys_source("permission"),
        "installer/postinstall.py": _MAPS,
        "installer/cursor_shim.py": 'X = ["sudo", "x"]\n',
        "installer/guards.py": 'X = ["sudo", "x"]\n',
        "scripts/a.sh": "sudo x\n",
        "scripts/lib/b.sh": "echo ok\n",
    }
    rows = _scan_rows(tmp_path, files, tools=(hooked,), schemas={"opencode": _OPENCODE_SCHEMA})
    assert {(r.path, r.entry, r.status) for r in rows} == {
        ("installer/agent_settings.py", "opencode", "finding"),
        ("installer/postinstall.py", "codegraph", "finding"),
        ("installer/cursor_shim.py", "cursor-agent", "finding"),
        ("installer/guards.py", "(installer)", "finding"),
        ("scripts/a.sh", "(maintainer)", "finding"),
        ("scripts/lib/b.sh", "(maintainer)", "ok"),
    }


def test_scan_groups_by_file_in_path_order(tmp_path: Path) -> None:
    files = {
        "scripts/z.sh": "sudo a\nsudo b\n",
        "installer/guards.py": 'X = ["sudo", "x"]\n',
        "scripts/lib/clean.sh": "echo ok\n",
        "scripts/a.sh": "echo ok\n",
    }
    rows = _scan_rows(tmp_path, files)
    assert [(r.path, r.line, r.status) for r in rows] == [
        ("installer/guards.py", 1, "finding"),
        ("scripts/a.sh", 0, "ok"),
        ("scripts/lib/clean.sh", 0, "ok"),
        ("scripts/z.sh", 1, "finding"),
        ("scripts/z.sh", 2, "finding"),
    ]


@pytest.mark.parametrize(
    ("token", "line", "state"),
    [
        ("permission", '_KEYS = (("permission",), "allow")', "current"),
        ("permission", '_KEYS = (("permissions",), "allow")', "stale"),
        ("permission", "_KEYS = ()", "stale"),
        ("--target=auto", 'A = "--target=auto"', "current"),
        ('"$@"', 'exec "$target" "$@"', "current"),
        ('exec "$target" "$@"', 'exec "$target" "$@"', "current"),
    ],
)
def test_stale_citation(
    token: str, line: str, state: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    repo = _repo(tmp_path, {"x.py": f"a\nb\n{line}\n"})
    run = root / DAY
    run.mkdir(parents=True)
    (run / "scripts.md").write_text(
        "# scripts\n\n| location | entry | status | pattern |\n|---|---|---|---|\n"
        f"| x.py:3 | alpha | finding | `{token}` was flagged |\n"
        "| x.py:9 | alpha | finding | `a` beyond the end |\n"
        "| gone.py:1 | alpha | finding | `a` file removed |\n",
        encoding="utf-8",
    )
    argv = ["summarize", "--date", DAY, "--root", str(root), "--repo", str(repo)]
    assert _main(argv, registry, capsys)[0] == 0
    summary = (run / "SUMMARY.md").read_text(encoding="utf-8")
    assert _script_row(summary, "x.py:3")[4] == state
    assert _script_row(summary, "x.py:9")[4] == "stale"
    assert _script_row(summary, "gone.py:1")[4] == "stale"


def test_scan_quotes_no_config_values(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    schema = dict(_OPENCODE_SCHEMA)
    schema["properties"] = {
        "permission": {"deprecated": True, "default": "canary-schema-default-1"},
    }
    schema_path = tmp_path / "p243e03-canary.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    source = _keys_source("permission").replace('"allow"', '"canary-key-value-2"')
    repo = _repo(
        tmp_path,
        {
            "installer/agent_settings.py": source + 'TOKEN = "canary-constant-3"\n',
            "installer/guards.py": 'NAME = "canary-constant-4"\nX = ["sudo", "canary-arg-5"]\n',
        },
    )
    argv = ["scan", "--date", DAY, "--root", str(root), "--repo", str(repo)]
    assert _main([*argv, "--schema", f"opencode={schema_path}"], registry, capsys)[0] == 0
    scripts = (root / DAY / "scripts.md").read_text(encoding="utf-8")
    assert "deprecated" in scripts
    assert "canary" not in scripts


# ---- 24.3-03 Task 3: findings, dispositions, the merge rule and the landing-set gate ----

_PROSE_OK = "https://example.com/check"
_CONTAINER_OK = "container: .e2e-artifacts/x.log"
_NOT_RUN = "reason: container check not run"


def _arrange(
    tmp_path: Path,
    *,
    alpha: str | None = None,
    beta: str | None = None,
    repo_files: Mapping[str, str] | None = None,
) -> tuple[Path, Path, Path]:
    """A two-entry registry, the stored reports, a repo tree and the run directory."""
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    for entry, text in (("alpha", alpha), ("beta", beta)):
        if text is not None:
            _store(root, entry, text)
    _repo(tmp_path, repo_files)
    (root / DAY).mkdir(parents=True, exist_ok=True)
    return registry, root, tmp_path / "repo"


def _sum(
    registry: Path,
    root: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    *extra: str,
) -> tuple[int, str]:
    argv = ["summarize", "--date", DAY, "--root", str(root), "--repo", str(repo), *extra]
    code, _, err = _main(argv, registry, capsys)
    return code, err


def _summary_text(root: Path) -> str:
    return (root / DAY / "SUMMARY.md").read_text(encoding="utf-8")


def _add(
    registry: Path,
    root: Path,
    capsys: pytest.CaptureFixture[str],
    entry: str,
    *args: str,
) -> tuple[int, str]:
    argv = ["add-finding", entry, "--date", DAY, "--root", str(root), *args]
    code, _, err = _main(argv, registry, capsys)
    return code, err


def _dispositions(root: Path, *rows: str) -> None:
    body = "".join(f"[[drift]]\n{row}\n\n" for row in rows)
    (root / DAY / "dispositions.toml").write_text(body, encoding="utf-8")


def _drift_rows(summary: str) -> list[list[str]]:
    block = summary.split("## Drift\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in block.splitlines() if line.startswith("| ")][1:]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]


def _entry_row(summary: str, entry: str, check: str) -> list[str]:
    block = summary.split(f"### {entry}\n", 1)[1].split("\n#", 1)[0]
    row = next(line for line in block.splitlines() if line.startswith(f"| {check} |"))
    return [cell.strip() for cell in row.strip("|").split("|")]


_BETA_DRIFT = (
    *_CHECK_ROWS[:3],
    "| tuning keys | drift | https://example.invalid/t |",
    _CHECK_ROWS[4],
)
_TWO_DRIFTS = (
    "| install method | drift | https://example.invalid/x |",
    "| update argv | drift | `alpha upgrade` |",
    *_CHECK_ROWS[2:],
)


def test_summary_reads_dispositions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    beta_rows = _BETA_DRIFT
    registry, root, repo = _arrange(
        tmp_path,
        alpha=_report("alpha", rows=_TWO_DRIFTS),
        beta=_report("beta", rows=beta_rows),
    )
    (root / DAY / "scripts.md").write_text(
        "| location | entry | status | pattern |\n|---|---|---|---|\n"
        "| installer/x.py:3 | alpha | finding | `foo` flagged |\n",
        encoding="utf-8",
    )
    _dispositions(
        root,
        'entry = "alpha"\ncheck = "install method"\ndisposition = "commit:0123abc"',
        'entry = "alpha"\ncheck = "update argv"\ndisposition = "backlog:999.13"\nnote = "later"',
        'entry = "alpha"\ncheck = "script"\ncite = "installer/x.py:3"\n'
        'disposition = "commit:abcdef0"',
    )
    code, err = _sum(registry, root, repo, capsys)
    assert code == 0, err
    rows = {(r[0], r[1]): r for r in _drift_rows(_summary_text(root))}
    assert rows[("alpha", "install method")][4] == "commit:0123abc"
    assert rows[("alpha", "update argv")][4] == "backlog:999.13"
    assert rows[("alpha", "script")][4] == "commit:abcdef0"
    assert rows[("beta", "tuning keys")][4] == "proposed"


_BAD_DISPOSITIONS = [
    ('entry = "alpha"\ncheck = "nope"\ndisposition = "proposed"', "check"),
    ('entry = "alpha"\ncheck = "script"\ndisposition = "proposed"', "cite"),
    ('entry = "alpha"\ncheck = "install method"\ndisposition = "done"', "disposition"),
    ('entry = "alpha"\ncheck = "install method"\ndisposition = "commit:xyz1234"', "disposition"),
    ('entry = "alpha"\ncheck = "install method"\ndisposition = "commit:abcdef"', "disposition"),
    ('entry = "alpha"\ncheck = "install method"\ndisposition = "backlog:12"', "disposition"),
    ('entry = "(installer)"\ncheck = "update argv"\ndisposition = "proposed"', "entry"),
]


@pytest.mark.parametrize(("row", "word"), _BAD_DISPOSITIONS)
def test_summary_invalid_dispositions(
    row: str, word: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha"))
    _dispositions(root, row)
    (root / DAY / "SUMMARY.md").write_text("old\n", encoding="utf-8")
    code, err = _sum(registry, root, repo, capsys)
    assert code == catalog_audit.EXIT_REFUSED
    assert word in err
    assert _summary_text(root) == "old\n"


def test_summary_refuses_broken_dispositions_and_names_every_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha"))
    (root / DAY / "dispositions.toml").write_text("[[drift\n", encoding="utf-8")
    assert _sum(registry, root, repo, capsys)[0] == catalog_audit.EXIT_REFUSED
    _dispositions(root, _BAD_DISPOSITIONS[2][0], _BAD_DISPOSITIONS[3][0])
    code, err = _sum(registry, root, repo, capsys)
    assert code == catalog_audit.EXIT_REFUSED
    assert len([line for line in err.splitlines() if line.startswith("refused: ")]) == 2
    assert not (root / DAY / "SUMMARY.md").exists()


def _tree(root: Path) -> dict[str, bytes]:
    return {str(p): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_add_finding_validates_and_appends(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, _ = _arrange(tmp_path, alpha=_report("alpha"), beta=_report("beta"))
    run = root / DAY
    reports = {n: (run / n).read_bytes() for n in ("alpha.md", "beta.md")}
    code, err = _add(
        registry,
        root,
        capsys,
        "alpha",
        *("--check", "install method", "--status", "drift", "--source", _CONTAINER_OK),
    )
    assert code == 0, err
    code, err = _add(
        registry,
        root,
        capsys,
        "beta",
        *("--check", "update argv", "--status", "unknown", "--source", _NOT_RUN),
    )
    assert code == 0, err
    rows = tomllib.loads((run / "findings.toml").read_text(encoding="utf-8"))["finding"]
    assert [(r["entry"], r["check"], r["status"]) for r in rows] == [
        ("alpha", "install method", "drift"),
        ("beta", "update argv", "unknown"),
    ]
    assert rows[0]["source"] == _CONTAINER_OK
    good = ("--check", "install method", "--status", "drift", "--source", _CONTAINER_OK)
    secret = "https://x.example/" + "ghp_" + "a" * 36
    refusals: list[tuple[str, list[str]]] = [
        ("nope", list(good)),
        ("(installer)", list(good)),
        ("alpha", ["--check", "nope", "--status", "drift", "--source", _CONTAINER_OK]),
        ("alpha", ["--check", "script", "--status", "drift", "--source", _CONTAINER_OK]),
        ("alpha", ["--check", "install method", "--status", "fine", "--source", _CONTAINER_OK]),
        ("alpha", ["--check", "install method", "--status", "ok", "--source", "looks fine"]),
        ("alpha", ["--check", "install method", "--status", "drift", "--source", secret]),
        ("alpha", ["--check", "install method", "--status", "ok", "--source", f"{Path.home()}/x"]),
        ("alpha", ["--check", "update argv", "--status", "unknown", "--source", "no reason"]),
        ("alpha", ["--check", "update argv", "--status", "ok", "--source", "https://e.x/a\nb"]),
    ]
    before = _tree(run)
    for entry, args in refusals:
        code, err = _add(registry, root, capsys, entry, *args)
        assert code == catalog_audit.EXIT_REFUSED, (entry, args, err)
    assert _tree(run) == before
    assert {n: (run / n).read_bytes() for n in reports} == reports


def test_shared_surface_finding_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    guards = (_INSTALLER / "guards.py").read_text(encoding="utf-8")
    number = next(
        n
        for n, line in enumerate(guards.splitlines(), 1)
        if 'exec {shlex.quote(target_path)} {quoted_args} "$@"' in line
    )
    cite = f"installer/guards.py:{number}"
    registry, root, repo = _arrange(
        tmp_path, alpha=_report("alpha"), repo_files={"installer/guards.py": guards}
    )
    code, err = _add(
        registry,
        root,
        capsys,
        "(installer)",
        *("--check", "script", "--cite", cite, "--status", "drift"),
        *("--source", f"`exec ` rewrites argv at {cite}"),
    )
    assert code == 0, err
    gate = ("--require-disposition", "(installer)")
    code, err = _sum(registry, root, repo, capsys, *gate)
    assert code == 1
    assert f"(installer) | script | {cite}" in err
    row = _script_row(_summary_text(root), cite)
    assert row[1] == "(installer)"
    assert row[4] == "current"
    _dispositions(
        root,
        f'entry = "(installer)"\ncheck = "script"\ncite = "{cite}"\ndisposition = "commit:1234567"',
    )
    code, err = _sum(registry, root, repo, capsys, *gate)
    assert code == 0, err
    assert _script_row(_summary_text(root), cite)[5] == "commit:1234567"


_MERGE_CASES = [
    ("unknown", [("ok", _CONTAINER_OK)], "ok", False),
    ("unknown", [("ok", _PROSE_OK)], "unknown", False),
    ("drift", [("ok", _CONTAINER_OK)], "drift", True),
    ("ok", [("unknown", _NOT_RUN)], "ok", False),
    ("unknown", [("ok", _CONTAINER_OK), ("drift", _PROSE_OK)], "drift", True),
    ("unknown", [("ok", _CONTAINER_OK), ("unknown", _NOT_RUN)], "ok", False),
    ("unknown", [("drift", _PROSE_OK)], "drift", True),
    ("drift", [("unknown", _NOT_RUN)], "drift", True),
    ("n/a", [("unknown", _NOT_RUN)], "unknown", False),
    ("n/a", [("ok", _CONTAINER_OK)], "ok", False),
    ("n/a", [("ok", _PROSE_OK)], "ok", False),
    ("n/a", [("drift", _PROSE_OK)], "drift", True),
    ("n/a", [("unknown", _NOT_RUN), ("ok", _CONTAINER_OK)], "ok", False),
]
_REPORT_ROWS = {
    "n/a": "| install method | n/a | reason: the vendor ships no installer |",
    "ok": "| install method | ok | https://example.com/install |",
    "unknown": f"| install method | unknown | {_NOT_RUN} |",
    "drift": "| install method | drift | https://example.com/install |",
}


@pytest.mark.parametrize(("reported", "findings", "effective", "gated"), _MERGE_CASES)
def test_summary_merges_findings(
    reported: str,
    findings: list[tuple[str, str]],
    effective: str,
    gated: bool,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rows = (_REPORT_ROWS[reported], *_CHECK_ROWS[1:])
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha", rows=rows))
    for status, source in findings:
        args = ("--check", "install method", "--status", status, "--source", source)
        assert _add(registry, root, capsys, "alpha", *args)[0] == 0
    code, err = _sum(registry, root, repo, capsys, "--require-disposition", "alpha")
    assert code == (1 if gated else 0), err
    row = _entry_row(_summary_text(root), "alpha", "install method")
    assert row[1] == effective
    assert row[2] == reported
    assert row[3] == "; ".join(f"{status} ({source})" for status, source in findings)


def test_summary_script_findings_and_invalid_findings_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(
        tmp_path, alpha=_report("alpha"), repo_files={"scripts/x.sh": "echo `sudo`\n"}
    )
    args = ("--check", "script", "--cite", "scripts/x.sh:1", "--status", "drift")
    assert (
        _add(registry, root, capsys, "alpha", *args, "--source", "`sudo` at scripts/x.sh:1")[0] == 0
    )
    assert _sum(registry, root, repo, capsys)[0] == 0
    row = _script_row(_summary_text(root), "scripts/x.sh:1")
    assert row[1:3] == ["alpha", "drift"]
    (root / DAY / "findings.toml").write_text(
        '[[finding]]\nentry = "alpha"\ncheck = "update argv"\nstatus = "fine"\nsource = "https://e.x/a"\n',
        encoding="utf-8",
    )
    code, err = _sum(registry, root, repo, capsys)
    assert code == catalog_audit.EXIT_REFUSED
    assert "status" in err


def test_scan_only_finding_is_gated(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry = _registry(
        tmp_path, _tool_toml("opencode", _ALPHA_METHOD), _tool_toml("beta", _BETA_METHOD)
    )
    root = _root(tmp_path)
    repo = _repo(tmp_path)
    run = root / DAY
    run.mkdir(parents=True)
    (run / "scripts.md").write_text(
        "| location | entry | status | pattern |\n|---|---|---|---|\n"
        "| installer/agent_settings.py:7 | opencode | finding | `permission` deprecated |\n",
        encoding="utf-8",
    )
    code, err = _sum(registry, root, repo, capsys, "--require-disposition", "opencode")
    assert code == 1
    assert "opencode | script | installer/agent_settings.py:7" in err
    _dispositions(
        root,
        'entry = "opencode"\ncheck = "script"\ncite = "installer/agent_settings.py:7"\n'
        'disposition = "backlog:999.4"',
    )
    assert _sum(registry, root, repo, capsys, "--require-disposition", "opencode")[0] == 0


def test_late_finding_never_clears_report_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha", rows=_DRIFT_ROWS))
    gate = ("--require-disposition", "alpha")
    for status, source in (("ok", _CONTAINER_OK), ("unknown", _NOT_RUN)):
        args = ("--check", "install method", "--status", status, "--source", source)
        assert _add(registry, root, capsys, "alpha", *args)[0] == 0
        code, err = _sum(registry, root, repo, capsys, *gate)
        assert code == 1
        assert "alpha | install method" in err
    _dispositions(root, 'entry = "alpha"\ncheck = "install method"\ndisposition = "commit:abcdef0"')
    assert _sum(registry, root, repo, capsys, *gate)[0] == 0
    shared = ("--check", "script", "--cite", "scripts/x.sh:1", "--status", "drift")
    for source in ("`sudo` at scripts/x.sh:1", "`sudo` again at scripts/x.sh:1"):
        assert _add(registry, root, capsys, "alpha", *shared, "--source", source)[0] == 0
    code, err = _sum(registry, root, repo, capsys, *gate)
    assert code == 1
    assert err.count("alpha | script | scripts/x.sh:1") == 1
    _dispositions(
        root,
        'entry = "alpha"\ncheck = "install method"\ndisposition = "commit:abcdef0"',
        'entry = "alpha"\ncheck = "script"\ncite = "scripts/x.sh:1"\ndisposition = "backlog:999.2"',
    )
    assert _sum(registry, root, repo, capsys, *gate)[0] == 0


def test_summary_require_disposition(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    beta_rows = _BETA_DRIFT
    registry, root, repo = _arrange(
        tmp_path,
        alpha=_report("alpha", rows=_DRIFT_ROWS),
        beta=_report("beta", rows=beta_rows),
    )
    both = ("--require-disposition", "alpha,beta")
    code, err = _sum(registry, root, repo, capsys, *both)
    assert code == 1
    assert "alpha | install method" in err
    assert "beta | tuning keys" in err
    _dispositions(root, 'entry = "alpha"\ncheck = "install method"\ndisposition = "proposed"')
    assert _sum(registry, root, repo, capsys, *both)[0] == 1
    _dispositions(root, 'entry = "alpha"\ncheck = "install method"\ndisposition = "commit:abcdef0"')
    code, err = _sum(registry, root, repo, capsys, *both)
    assert code == 1
    assert "alpha | install method" not in err
    assert "beta | tuning keys" in err
    only_alpha = ("--require-disposition", "alpha")
    assert _sum(registry, root, repo, capsys, *only_alpha)[0] == 0
    assert _sum(registry, root, repo, capsys, "--require-disposition", "nope")[0] == 64
    assert _sum(registry, root, repo, capsys, "--require-disposition", " , ")[0] == 64


def test_summary_is_idempotent_and_rebuilt_on_resume(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha", rows=_DRIFT_ROWS))
    assert _sum(registry, root, repo, capsys)[0] == 0
    first = _summary_text(root)
    assert _sum(registry, root, repo, capsys)[0] == 0
    assert _summary_text(root) == first
    _store(root, "beta", _report("beta"))
    assert _sum(registry, root, repo, capsys)[0] == 0
    second = _summary_text(root)
    assert second != first
    old, new = first.splitlines(), second.splitlines()
    changed = {"complete 1/2", "missing beta"}
    assert set(old) - set(new) == changed
    alpha = [text.split("### alpha\n", 1)[1].split("\n#", 1)[0].strip() for text in (first, second)]
    assert alpha[0] == alpha[1]
    assert "### beta" in second
    assert "complete 2/2" in second


def test_summary_no_proposed_changes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha"), beta=_report("beta"))
    assert _sum(registry, root, repo, capsys)[0] == 0
    assert "no proposed changes" in _summary_text(root)
    change = "- Add a flag; risk: low; evidence: https://example.com/c"
    proposal = _report("beta").replace("- none", change)
    (root / DAY / "beta.md").unlink()
    _store(root, "beta", proposal)
    assert _sum(registry, root, repo, capsys)[0] == 0
    summary = _summary_text(root)
    assert "no proposed changes" not in summary
    assert "- beta: Add a flag; risk: low; evidence: https://example.com/c" in summary


def test_summary_orders_entries_then_scripts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cited = (_CHECK_ROWS[0], "| update argv | drift | `sudo` at scripts/z.sh:1 |", *_CHECK_ROWS[2:])
    registry, root, repo = _arrange(
        tmp_path,
        alpha=_report("alpha"),
        beta=_report("beta", rows=cited),
        repo_files={
            "scripts/a.sh": "x\nsudo y\n",
            "scripts/z.sh": "sudo q\n",
            "installer/guards.py": "a\nb\nc = ['sudo']\n",
        },
    )
    (root / DAY / "scripts.md").write_text(
        "| location | entry | status | pattern |\n|---|---|---|---|\n"
        "| scripts/a.sh:2 | (maintainer) | finding | `sudo` elevation |\n"
        "| installer/guards.py:3 | (installer) | finding | `sudo` elevation |\n",
        encoding="utf-8",
    )
    assert _sum(registry, root, repo, capsys)[0] == 0
    summary = _summary_text(root)
    assert (
        summary.index("### alpha") < summary.index("### beta") < summary.index("## Script findings")
    )
    block = summary.split("## Script findings\n", 1)[1]
    where = [line.split("|")[1].strip() for line in block.splitlines() if line.startswith("| ")][1:]
    assert where == ["installer/guards.py:3", "scripts/a.sh:2", "scripts/z.sh:1"]


def test_summary_marks_resolved_stale_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(
        tmp_path, alpha=_report("alpha"), repo_files={"installer/x.py": "a\nb\nmoved = 1\n"}
    )
    (root / DAY / "scripts.md").write_text(
        "| location | entry | status | pattern |\n|---|---|---|---|\n"
        "| installer/x.py:3 | alpha | finding | `permission` flagged |\n",
        encoding="utf-8",
    )
    assert _sum(registry, root, repo, capsys)[0] == 0
    assert _script_row(_summary_text(root), "installer/x.py:3")[4] == "stale"
    _dispositions(
        root,
        'entry = "alpha"\ncheck = "script"\ncite = "installer/x.py:3"\n'
        'disposition = "commit:abc1234"',
    )
    assert _sum(registry, root, repo, capsys)[0] == 0
    row = _script_row(_summary_text(root), "installer/x.py:3")
    assert row[4] == "stale (resolved by commit:abc1234)"
    assert row[5] == "commit:abc1234"


def test_summary_lists_missing_and_orphans(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha"))
    (root / DAY / "stray.md").write_text("# stray\n", encoding="utf-8")
    assert _sum(registry, root, repo, capsys)[0] == 0
    lines = _summary_text(root).splitlines()
    assert lines[:5] == [
        f"# Catalog audit - {DAY}",
        "complete 1/2",
        "missing beta",
        "orphan stray",
        "",
    ]


# ---- 24.3 review F1, F7: the --state guard and the symlink walk ----

_STATE_KINDS = (
    "home config",
    "absent under a home dotdir",
    "nested json",
    "json list",
    "non-string values",
    "dangling symlink",
    "symlink to a valid state",
    "checkout with --repo elsewhere",
)


def _verify_argv(root: Path, state: Path, *extra: str) -> list[str]:
    return ["verify", "--date", DAY, "--root", str(root), "--state", str(state), *extra]


def _state_cases(tmp_path: Path) -> dict[str, tuple[Path, list[str]]]:
    home = Path.home()
    (home / ".claude").mkdir(parents=True)
    settings = home / ".claude" / "settings.json"
    settings.write_text('{"permissions": {"allow": ["x"]}}', encoding="utf-8")
    nested = tmp_path / "p243fA-nested.json"
    nested.write_text('{"permissions": {"allow": ["x"]}}', encoding="utf-8")
    listy = tmp_path / "p243fA-list.json"
    listy.write_text('["a"]', encoding="utf-8")
    ints = tmp_path / "p243fA-ints.json"
    ints.write_text('{"a": 1}', encoding="utf-8")
    dangling = tmp_path / "p243fA-dangling.json"
    dangling.symlink_to(tmp_path / "p243fA-nowhere.json")
    target = tmp_path / "p243fA-target.json"
    target.write_text("{}", encoding="utf-8")
    good_link = tmp_path / "p243fA-goodlink.json"
    good_link.symlink_to(target)
    checkout = Path(catalog_audit.__file__).resolve().parents[1]
    return {
        "home config": (settings, []),
        "absent under a home dotdir": (home / ".local" / "p243fA.json", []),
        "nested json": (nested, []),
        "json list": (listy, []),
        "non-string values": (ints, []),
        "dangling symlink": (dangling, []),
        "symlink to a valid state": (good_link, []),
        "checkout with --repo elsewhere": (
            checkout / "p243fA-state.json",
            ["--repo", str(tmp_path / "elsewhere")],
        ),
    }


@pytest.mark.parametrize("kind", _STATE_KINDS)
def test_verify_state_guard_refuses(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    root = _root(tmp_path)
    state, extra = _state_cases(tmp_path)[kind]
    before = state.read_bytes() if state.is_file() else None
    calls: list[list[str]] = []
    code, _, err = _main(
        _verify_argv(root, state, *extra), registry, capsys, verify_main=_verify_fake(calls)
    )
    assert code == catalog_audit.EXIT_USAGE, err
    assert calls == []
    assert (state.read_bytes() if state.is_file() else None) == before
    assert not (root / DAY / "verify-registry.md").exists()


def test_verify_state_guard_accepts_a_flat_state_and_an_absent_scratch_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _two_entry_registry(tmp_path)
    flat = tmp_path / "p243fA-flat.json"
    flat.write_text('{"tool:url": "sha"}', encoding="utf-8")
    absent = Path.home() / "p243fA-scratch.json"  # under HOME, but not under a dotdir
    for index, state in enumerate((flat, absent)):
        root = _root(tmp_path / f"r{index}")
        code, _, err = _main(
            _verify_argv(root, state), registry, capsys, verify_main=_verify_fake([])
        )
        assert code == 0, err


@pytest.mark.parametrize("linked", [".planning", "audits", "catalog", DAY])
def test_run_dir_refuses_a_symlink_at_every_component(linked: str, tmp_path: Path) -> None:
    parts = [".planning", "audits", "catalog", DAY]
    index = parts.index(linked)
    real = tmp_path / "real"
    real.joinpath(*parts[index + 1 :]).mkdir(parents=True)
    parent = (tmp_path / "repo").joinpath(*parts[:index])
    parent.mkdir(parents=True)
    (parent / linked).symlink_to(real)
    root = tmp_path / "repo" / ".planning" / "audits" / "catalog"
    with pytest.raises(catalog_audit.UsageError, match="symlink"):
        catalog_audit.run_dir(root, DAY)


# ---- 24.3 review F3: a run record is never overwritten ----


def test_scan_and_verify_never_overwrite_a_run_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha"))
    run = root / DAY
    state = tmp_path / "p243fA-state.json"
    calls: list[list[str]] = []
    scan = ["scan", "--date", DAY, "--root", str(root), "--repo", str(repo)]
    verify = _verify_argv(root, state)
    for argv, name in ((scan, "scripts.md"), (verify, "verify-registry.md")):
        assert _main(argv, registry, capsys, verify_main=_verify_fake(calls))[0] == 0
        before = (run / name).read_bytes()
        (repo / "scripts" / "x.sh").write_text("sudo rm\n", encoding="utf-8")
        code, _, err = _main(argv, registry, capsys, verify_main=_verify_fake(calls))
        assert code == catalog_audit.EXIT_REFUSED, err
        assert "new date" in err
        assert (run / name).read_bytes() == before
    assert len(calls) == 1  # the refused verify never ran verify-registry


# ---- 24.3 review F15: the /home and /var/home aliases of the home path ----


@pytest.mark.parametrize(
    ("home", "leak"),
    [
        (Path("/var/home/p243fAuser"), "/home/p243fAuser/.claude"),
        (Path("/home/p243fAuser"), "/var/home/p243fAuser/.claude"),
    ],
)
def test_home_alias_is_refused_and_tilded(home: Path, leak: str) -> None:
    report = _report().replace("nothing relevant", f"see {leak}")
    problems = catalog_audit.validate_report(report, "alpha", home=home)
    assert any("home path" in problem for problem in problems)
    assert vars(catalog_audit)["_tilde"](leak, home) == "~/.claude"


# ---- 24.3 review F8: ids are validated on add; an unknown entry read back is an orphan ----


def test_removed_entry_keeps_its_rows_as_orphans(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, root, repo = _arrange(tmp_path, alpha=_report("alpha"))
    run = root / DAY
    (run / "findings.toml").write_text(
        '[[finding]]\nentry = "gone"\ncheck = "install method"\nstatus = "drift"\n'
        'source = "https://e.x/a"\n',
        encoding="utf-8",
    )
    _dispositions(root, 'entry = "gone"\ncheck = "install method"\ndisposition = "commit:abc1234"')
    code, err = _sum(registry, root, repo, capsys, "--require-disposition", "alpha")
    assert code == 0, err
    summary = _summary_text(root)
    assert "orphan gone\n" in summary
    assert _drift_rows(summary) == [
        ["gone", "install method", "drift", "https://e.x/a", "commit:abc1234"]
    ]
    args = ("--check", "update argv", "--status", "ok", "--source", _PROSE_OK)
    assert _add(registry, root, capsys, "alpha", *args)[0] == 0
    assert _add(registry, root, capsys, "gone", *args)[0] == catalog_audit.EXIT_REFUSED
