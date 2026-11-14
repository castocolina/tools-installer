"""Read-only fact gatherer and validated report writer for the catalog-audit skill.

``status`` names the next registry entry without a complete report (resume needs no state
file), ``facts ID`` prints what the registry and the upstreams say about one entry, and
``write ID`` validates an agent-authored report on stdin and stores it. The tool changes
nothing outside its run directory ``.planning/audits/catalog/<date>/``: it never edits the
registry, code or scripts, and it never installs, updates or removes anything.

A report is complete when its last line is the footer this tool appends after the atomic
write, so an interrupted write is never counted. ``status`` is not a reservation: two
sessions can pick the same entry and date and both pass the completeness check; if they
race, ``os.replace`` keeps whichever whole report lands last. The loop hands entries out
one at a time, and nothing here claims to prevent that race.

Exit codes: 0 ok; 64 usage error; 70 internal error; 73 report refused.
"""

from __future__ import annotations

import argparse
import functools
import http.client
import json
import platform
import re
import shutil
import sys
import tomllib
import traceback
import urllib.parse
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NoReturn, cast

from installer import versions
from installer.agent_settings import DYNAMIC_KEYS, TUNING_GROUPS, setting_keys
from installer.atomic import atomic_write_text
from installer.locations import ensure_dir
from installer.model import Method, Tool, load_tools, method_package
from installer.ownership import ManagerOwnership
from installer.platform import detect_os
from installer.postinstall import POSTINSTALL_HOOKS
from installer.run import run_output
from installer.verify_registry import github_token
from installer.version_status import probed_version
from installer.versions import (
    Fetch,
    VersionError,
    parse_version,
    resolve_github_release,
    resolve_npm_latest,
)

REGISTRY = Path(__file__).with_name("registry.toml")
RUN_ROOT = Path(__file__).resolve().parents[1] / ".planning" / "audits" / "catalog"
FOOTER = "<!-- catalog-audit:complete -->"
CHECKS = (
    "install method",
    "update argv",
    "removal recipe and paths",
    "tuning keys",
    "postinstall hook",
)
STATUSES = ("ok", "drift", "unknown", "n/a")

EXIT_USAGE = 64
EXIT_INTERNAL = 70
EXIT_REFUSED = 73

# Files a run directory holds that are not one entry's report.
_NON_ENTRY_STEMS = frozenset({"SUMMARY", "verify-registry", "scripts"})
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SECTIONS = ("Versions", "Changelog", "Checks", "Proposed changes")
_TITLE_RE = re.compile(r"# (?P<id>\S+) - catalog audit (?P<day>\S+)")
_VERSION_LINE_RE = re.compile(r"- (?P<key>pinned|verified|installed|latest|note): (?P<value>\S.*)")
_CITATION_RE = re.compile(r"(?:installer|scripts|tests|\.claude)/\S+:\d+")
_SPAN_RE = re.compile(r"`[^`]+`")
_CHANGE_RE = re.compile(r"- \S.*; risk: (?:low|medium|high); evidence: \S.*")
# A committed report must hold no credential: refuse anything shaped like one.
_SECRET_RES = tuple(
    re.compile(pattern)
    for pattern in (
        r"ghp_[A-Za-z0-9]{36}",
        r"github_pat_[A-Za-z0-9_]{22,}",
        r"\bsk-[A-Za-z0-9_-]{32,}",
        r"xox[abprs]-[A-Za-z0-9-]{10,}",
        r"AKIA[0-9A-Z]{16}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"Bearer [A-Za-z0-9._~+/=-]{24,}",
    )
)


class UsageError(Exception):
    """A bad argument; exit 64 before anything is written."""


class ReportRefused(Exception):
    """A report the writer will not store; carries every reason."""

    def __init__(self, reasons: Sequence[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


@dataclass(frozen=True)
class Seams:
    """Every side effect of the gatherer, injected so tests run offline."""

    fetch: Fetch
    probe: Callable[[list[str]], str | None]
    which: Callable[[str], str | None]
    home: Path
    platform_os: str


def default_seams(gh: Callable[[list[str]], str]) -> Seams:
    """Production seams; `gh auth token` is the one read-only exec besides `--version`."""
    return Seams(
        fetch=functools.partial(versions.urlopen_fetch, token=github_token(gh)),
        probe=versions.probe_version_output,
        which=_which,
        home=Path.home(),
        platform_os=_detect_os(),
    )


def _which(name: str) -> str | None:
    return shutil.which(name)


def _detect_os() -> str:
    """The installer's OS key, or "" when this host is none of them (no per-OS filtering)."""
    try:
        return detect_os(platform.system(), lambda name: _which(name) is not None)
    except RuntimeError:
        return ""


def run_dir(root: Path, day: str) -> Path:
    """The run directory for `day`; refuses a bad date, a missing `.planning` or a symlink."""
    if _DATE_RE.fullmatch(day) is None:
        raise UsageError(f"--date must be YYYY-MM-DD, got {day!r}")
    try:
        date.fromisoformat(day)
    except ValueError:
        raise UsageError(f"--date is not a real date: {day!r}") from None
    if not any(p.name == ".planning" and p.is_dir() for p in (root, *root.parents)):
        raise UsageError(f"{root} is not under an existing .planning directory")
    run = root / day
    for path in (root, run):
        if path.is_symlink():
            raise UsageError(f"{path} is a symlink")
    return run


@dataclass(frozen=True)
class Status:
    next_id: str | None
    complete: int
    total: int
    orphans: tuple[str, ...]


def _is_complete(path: Path) -> bool:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError):
        return False
    return bool(lines) and lines[-1].strip() == FOOTER


def status(tools: Sequence[Tool], run: Path) -> Status:
    ids = [tool.id for tool in tools]
    done = {tool_id for tool_id in ids if _is_complete(run / f"{tool_id}.md")}
    orphans = sorted(
        path.stem
        for path in run.glob("*.md")
        if path.stem not in ids and path.stem not in _NON_ENTRY_STEMS
    )
    return Status(
        next_id=next((tool_id for tool_id in ids if tool_id not in done), None),
        complete=len(done),
        total=len(ids),
        orphans=tuple(orphans),
    )


def _check_rows(lines: list[str], problems: list[str]) -> dict[str, str]:
    states: dict[str, str] = {}
    if lines[:2] != ["| check | status | source |", "|---|---|---|"]:
        problems.append(
            "Checks: the table starts with '| check | status | source |' then '|---|---|---|'"
        )
    rows = lines[2:]
    if len(rows) != len(CHECKS):
        problems.append(f"Checks: expected {len(CHECKS)} rows, found {len(rows)}")
    for want, row in zip(CHECKS, rows, strict=False):
        cells = [cell.strip() for cell in row.strip("|").split("|", 2)]
        if not (row.startswith("|") and row.endswith("|")) or len(cells) != 3:
            problems.append(f"Checks row {row!r}: not a '| check | status | source |' row")
            continue
        name, state, source = cells
        states[name] = state
        if name != want:
            problems.append(f"Checks row {row!r}: expected the {want!r} row here")
        elif state not in STATUSES:
            problems.append(f"Checks row {row!r}: status must be one of {', '.join(STATUSES)}")
        elif not source:
            problems.append(f"Checks row {row!r}: the source is empty")
        elif state == "n/a" and not source.startswith("reason: "):
            problems.append(f"Checks row {row!r}: an n/a source starts with 'reason: '")
        elif state in ("ok", "drift") and not (
            "https://" in source or _SPAN_RE.search(source) or _CITATION_RE.search(source)
        ):
            problems.append(
                f"Checks row {row!r}: an {state} source needs a URL, a `command` or a "
                "repo citation (path:line)"
            )
    return states


def _hygiene(text: str, home: Path) -> list[str]:
    homes = {str(home), str(home.resolve())} - {"", "/"}
    problems: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        if any(pattern.search(line) for pattern in _SECRET_RES):
            problems.append(f"line {n}: a secret-shaped token (never put a credential in a report)")
        if any(h in line for h in homes):
            problems.append(f"line {n}: the absolute home path (write ~/... instead)")
        if FOOTER in line:
            problems.append(f"line {n}: the footer is appended by the tool, remove it")
    return problems


def validate_report(text: str, entry_id: str, *, home: Path) -> list[str]:
    """Every way `text` breaks the report grammar; an empty list means it is valid."""
    problems = _hygiene(text, home)
    body = [(n, line.rstrip()) for n, line in enumerate(text.splitlines(), 1) if line.strip()]
    title = _TITLE_RE.fullmatch(body[0][1]) if body else None
    if title is None or title["id"] != entry_id:
        problems.append(f"the first line must be '# {entry_id} - catalog audit YYYY-MM-DD'")
    elif _DATE_RE.fullmatch(title["day"]) is None:
        problems.append(f"the title date {title['day']!r} is not YYYY-MM-DD")
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current: list[str] | None = None
    for n, line in body[1:]:
        if line.startswith("## "):
            name = line[3:].strip()
            order.append(name)
            current = sections.setdefault(name, [])
        elif current is None:
            problems.append(f"line {n}: text before the first section")
        else:
            current.append(line)
    if order != list(_SECTIONS):
        problems.append("the sections are exactly " + ", ".join(f"## {s}" for s in _SECTIONS))
    counts: Counter[str] = Counter()
    latest: list[str] = []
    for line in sections.get("Versions", []):
        match = _VERSION_LINE_RE.fullmatch(line)
        if match is None:
            problems.append(f"Versions: unrecognised line {line!r}")
            continue
        counts[match["key"]] += 1
        if match["key"] == "latest":
            latest.append(match["value"])
    for key in ("pinned", "verified", "installed"):
        if counts[key] != 1:
            problems.append(f"Versions: need exactly one '- {key}: ' line, found {counts[key]}")
    if not latest:
        problems.append("Versions: need at least one '- latest: ' line")
    changelog = sections.get("Changelog", [])
    if not changelog or any(not line.startswith("- ") for line in changelog):
        problems.append("Changelog: one or more '- ' lines")
    states = _check_rows(sections.get("Checks", []), problems)
    changes = sections.get("Proposed changes", [])
    unreachable = bool(latest) and all(value.startswith("unknown:") for value in latest)
    if unreachable and "ok" in (states.get(CHECKS[0]), states.get(CHECKS[1])):
        problems.append("an install method or update argv row is ok while every latest is unknown")
    if changes != ["- none"] and (not changes or not all(_CHANGE_RE.fullmatch(c) for c in changes)):
        problems.append(
            "Proposed changes: '- none' or '- <change>; risk: low|medium|high; evidence: <source>'"
        )
    return problems


def _refuse_symlink_leaf(path: Path) -> None:
    """Refuse to write through a symlink at the output leaf (shared by every writer)."""
    if path.is_symlink():
        raise ReportRefused([f"{path.name} is a symlink"])


def write_report(run: Path, entry_id: str, text: str, *, home: Path) -> Path:
    """Store a valid report whole and append the footer; a complete report is never rewritten.

    Findings that arrive after an entry's report go to the run's `findings.toml`, never here.
    """
    problems = validate_report(text, entry_id, home=home)
    title = next((line for line in text.splitlines() if line.strip()), "")
    if not title.endswith(f" - catalog audit {run.name}"):
        problems.append(f"the title date must be this run's date, {run.name}")
    target = run / f"{entry_id}.md"
    _refuse_symlink_leaf(target)
    if _is_complete(target):
        problems.append(f"{entry_id}.md is already complete; a new date starts a new run")
    if problems:
        raise ReportRefused(problems)
    ensure_dir(run)
    atomic_write_text(target, text.rstrip("\n") + "\n\n" + FOOTER + "\n")
    return target


@dataclass(frozen=True)
class _Source:
    """One upstream the gatherer reads a latest version from; `url` is "" when none is read."""

    label: str
    url: str
    read: Callable[[Fetch], str]


_URLS = {
    "formula": "https://formulae.brew.sh/api/formula/{}.json",
    "cask": "https://formulae.brew.sh/api/cask/{}.json",
    "arch": "https://archlinux.org/packages/search/json/?name={}",
    "fedora": "https://mdapi.fedoraproject.org/rawhide/pkg/{}",
    "debian": "https://sources.debian.org/api/src/{}/",
    "pypi": "https://pypi.org/pypi/{}/json",
}


def _url(key: str, name: str) -> str:
    return _URLS[key].format(urllib.parse.quote(name, safe=""))


def _json_object(url: str, fetch: Fetch) -> dict[str, object]:
    """A JSON object body; a transport failure, a non-JSON body or an error body raises."""
    try:
        data = json.loads(fetch(url))
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise VersionError(f"could not read {url}") from exc
    if not isinstance(data, dict):
        raise VersionError("the answer is not a JSON object")
    body = cast(dict[str, object], data)
    if "error" in body:
        # An error body behind HTTP 200 (sources.debian.org answers {"error": 404}).
        raise VersionError(f"the answer is an error body: {str(body['error'])[:80]}")
    return body


def _dig(node: object, *path: str) -> str:
    """The non-empty string at `path` inside nested JSON objects."""
    for key in path:
        node = cast(dict[str, object], node).get(key) if isinstance(node, dict) else None
    if isinstance(node, str) and node:
        return node
    raise VersionError(f"no {'.'.join(path)} in the answer")


def _github_latest(repo: str, fetch: Fetch) -> str:
    return resolve_github_release(repo, fetch).tag


def _brew_formula_latest(name: str, fetch: Fetch) -> str:
    return _dig(_json_object(_url("formula", name), fetch), "versions", "stable")


def _brew_cask_latest(name: str, fetch: Fetch) -> str:
    return _dig(_json_object(_url("cask", name), fetch), "version")


def _arch_latest(name: str, fetch: Fetch) -> str:
    results = _json_object(_url("arch", name), fetch).get("results")
    for row in cast(list[object], results) if isinstance(results, list) else []:
        if isinstance(row, dict):
            row = cast(dict[str, object], row)
        else:
            continue
        if row.get("pkgname") == name:
            return f"{_dig(row, 'pkgver')}-{_dig(row, 'pkgrel')} ({_dig(row, 'repo')})"
    raise VersionError(f"no exact pkgname match for {name!r}")


def _fedora_latest(name: str, fetch: Fetch) -> str:
    body = _json_object(_url("fedora", name), fetch)
    return f"{_dig(body, 'version')}-{_dig(body, 'release')} (Fedora rawhide)"


def _debian_latest(name: str, fetch: Fetch) -> str:
    rows = _json_object(_url("debian", name), fetch).get("versions")
    if not isinstance(rows, list) or not rows:
        raise VersionError("no versions in the answer")
    return _dig(cast(list[object], rows)[0], "version")


def _pypi_latest(name: str, fetch: Fetch) -> str:
    return _dig(_json_object(_url("pypi", name), fetch), "info", "version")


# kind -> (label, URL key, reader) for the kinds whose latest version is one JSON read by name.
_NAMED_READERS: dict[str, tuple[str, str, Callable[[str, Fetch], str]]] = {
    "brew": ("brew", "formula", _brew_formula_latest),
    "cask": ("cask", "cask", _brew_cask_latest),
    "pacman": ("pacman", "arch", _arch_latest),
    "dnf": ("dnf", "fedora", _fedora_latest),
    "apt": ("apt", "debian", _debian_latest),
    "uv-tool": ("pypi", "pypi", _pypi_latest),
}


def _unread(label: str, why: str) -> _Source:
    def read(_fetch: Fetch) -> str:
        raise VersionError(why)

    return _Source(label, "", read)


def _param(method: Method, key: str) -> str | None:
    value = method.params.get(key)
    return value if isinstance(value, str) and value else None


def _method_source(method: Method) -> _Source | None:
    kind = method.kind
    repo = _param(method, "repo")
    if kind in ("github_release", "cargo_distrobox") and repo:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        return _Source("github", url, functools.partial(_github_latest, repo))
    package = _param(method, "npm_pkg") or _param(method, "latest_npm")
    if package:
        quoted = urllib.parse.quote(package, safe="@")
        url = f"https://registry.npmjs.org/-/package/{quoted}/dist-tags"
        return _Source("npm", url, functools.partial(resolve_npm_latest, package))
    name = method_package(method)
    if kind in _NAMED_READERS and name:
        label, url_key, reader = _NAMED_READERS[kind]
        if kind == "brew" and "/" in name:
            return _unread(label, "tap formula, not on formulae.brew.sh")
        return _Source(label, _url(url_key, name), functools.partial(reader, name))
    if kind in ("app", "tarball"):
        return _Source(kind, "", lambda _fetch: f"see verify-registry.md ({kind})")
    if kind in ("sdkman", "host_setup", "rpm_ostree"):
        return _unread(kind, f"not read by the gatherer ({kind})")
    return None


def _sources(tool: Tool) -> list[_Source]:
    found: dict[tuple[str, str], _Source] = {}
    for method in tool.methods:
        source = _method_source(method)
        if source is not None:
            found.setdefault((source.label, source.url), source)
    return list(found.values())


def _reason(exc: VersionError) -> str:
    """One line naming the failure: the transport error's class and text, else the message."""
    cause = exc.__cause__
    text = f"{type(cause).__name__}: {cause}".rstrip(": ") if cause is not None else str(exc)
    lines = text.splitlines()
    return (lines[0] if lines else type(exc).__name__)[:160]


def _latest_lines(tool: Tool, fetch: Fetch) -> list[str]:
    lines: list[str] = []
    resolved: list[tuple[str, str]] = []
    for source in _sources(tool):
        try:
            value = source.read(fetch)
            resolved.append((source.label, value))
        except VersionError as exc:
            value = f"unknown: {_reason(exc)}"
        lines.append(f"- latest: {value}" + (f" ({source.url})" if source.url else ""))
    if not lines:
        lines.append("- latest: unknown: no latest source declared")
    majors = {parsed[0] for _, value in resolved if (parsed := parse_version(value))}
    if len(majors) > 1:
        shown = " vs ".join(
            f"{value} ({label})" for label, value in resolved if parse_version(value)
        )
        lines.append(f"- note: major split: {shown}")
    return lines


def _method_pins(method: Method) -> list[str]:
    version = _param(method, "version")
    if method.kind in ("app", "tarball", "sdkman") and version:
        return [f"{version} ({method.kind} version param)"]
    pinned = method.params.get("versions")
    if method.kind == "node" and isinstance(pinned, dict):
        pairs = cast(dict[str, object], pinned)
        return [f"{name} {spec} (node versions param)" for name, spec in pairs.items()]
    return []


def _pinned_line(tool: Tool) -> str:
    pins = [pin for method in tool.methods for pin in _method_pins(method)]
    loose = list(dict.fromkeys(m.kind for m in tool.methods if not _method_pins(m)))
    return "; ".join([*pins, *([f"unpinned ({', '.join(loose)})"] if loose else [])])


def _installed_line(tool: Tool, seams: Seams) -> str:
    here = [m for m in tool.methods if not m.os or seams.platform_os in m.os] or list(tool.methods)
    target = next((m for m in here if m.params.get("version_file")), here[0])
    ownership = ManagerOwnership(
        tool_id=tool.id,
        owner="installer",
        method=target,
        package=None,
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    calls: list[tuple[list[str], str | None]] = []

    def probe(argv: list[str]) -> str | None:
        output = seams.probe(argv)
        calls.append((argv, output))
        return output

    found = probed_version(tool, ownership, probe, unresolved=seams.which(tool.cmd))
    if not calls:  # a version_file answered (or was missing) before any exec
        version_file = _param(target, "version_file") or ""
        if found:
            return f"{found} ({version_file})"
        if version_file and Path(version_file).expanduser().exists():
            return f"unknown: no version in {version_file}"
        return "not installed"
    argv, output = calls[0]
    if output is None:
        return "not installed"
    if found is None:
        return "unknown: no version in the --version output"
    return f"{found} ({' '.join(argv)}; bin_dir first, then the PATH hit)"


def _method_line(method: Method) -> str:
    params = " ".join(
        f"{key}={json.dumps(value)}"
        for key, value in method.params.items()
        if key not in ("paths", "update", "remove")
    )
    where = f"os: {', '.join(method.os) or 'all'}, arch: {', '.join(method.arch) or 'all'}"
    return f"  - {method.kind} ({where}) {params}".rstrip()


def _argvs(tool: Tool, key: str) -> list[str]:
    found: list[str] = []
    for method in tool.methods:
        argv = method.params.get(key)
        if isinstance(argv, list):
            found.append(" ".join(str(token) for token in cast(list[object], argv)))
    return list(dict.fromkeys(found))


def _hook_line(name: str | None) -> str:
    hook = POSTINSTALL_HOOKS.get(name or "")
    if name is None:
        return "none"
    if hook is None:
        return f"{name} (not in POSTINSTALL_HOOKS)"
    if hook.targets is None:
        return f"{name} (host-independent)"
    return f"{name} (targets: {', '.join(hook.targets)})"


def _tuning_line(tool: Tool, platform_os: str) -> str:
    groups = [
        f"{group}: "
        + ", ".join(".".join(k.path) for k in setting_keys(tool.id, group, platform_os))
        for group in TUNING_GROUPS.get(tool.id, ())
    ]
    groups += [
        f"{setting}: {', '.join('.'.join(path) for path in paths)}"
        for (agent, setting), paths in DYNAMIC_KEYS.items()
        if agent == tool.id
    ]
    return "; ".join(groups) or "none"


def _repos(tool: Tool) -> set[str]:
    return {
        r
        for m in tool.methods
        if m.kind in ("github_release", "cargo_distrobox")
        if (r := _param(m, "repo"))
    }


def _tilde(text: str, home: Path) -> str:
    """Show the home prefix as `~`, so a committed report holds no absolute home path."""
    for prefix in sorted({str(home), str(home.resolve())} - {"", "/"}, key=len, reverse=True):
        text = text.replace(prefix, "~")
    return text


def entry_facts(
    tool: Tool,
    tools: Sequence[Tool],
    seams: Seams,
    *,
    verified: Mapping[str, str] | None = None,
) -> str:
    """The read-only fact block for one entry; it runs only `[<binary>, "--version"]`."""
    paths = [str(p) for m in tool.methods for p in cast(list[object], m.params.get("paths") or [])]
    updates = _argvs(tool, "update")
    removes = _argvs(tool, "remove")
    lines = [f"# facts: {tool.id}", f"- cmd: {tool.cmd}", "- methods:"]
    lines.extend(_method_line(method) for method in tool.methods)
    lines += [
        f"- pinned: {_pinned_line(tool)}",
        f"- verified: {(verified or {}).get(tool.id, 'unknown')}",
        f"- paths: {', '.join(dict.fromkeys(paths)) or 'none'}",
        f"- update: {'; '.join(updates) or 'none (the installer re-runs the method)'}",
        f"- remove: {'; '.join(removes) or 'none'}",
        f"- postinstall: {_hook_line(tool.postinstall)}",
        f"- post_install: {', '.join(tool.post_install) or 'none'}",
        f"- tuning: {_tuning_line(tool, seams.platform_os)}",
        f"- installed: {_installed_line(tool, seams)}",
        *_latest_lines(tool, seams.fetch),
    ]
    mine = _repos(tool)
    lines.extend(
        f"- see also: {other.id}"
        for other in tools
        if other.id != tool.id and (other.cmd == tool.cmd or mine & _repos(other))
    )
    runtime = next((name for name in ("podman", "docker") if seams.which(name)), None)
    none = '- container: none (rows that need a container read "unknown: container check not run")'
    lines.append(f"- container: {runtime}" if runtime else none)
    return _tilde("\n".join(lines) + "\n", seams.home)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Catalog audit fact gatherer and report writer.")
    parser.add_argument("--registry", type=Path, default=None, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("status", "write"):
        cmd = sub.add_parser(name)
        if name == "write":
            cmd.add_argument("id")
        cmd.add_argument("--date", required=True)
        cmd.add_argument("--root", type=Path, default=None)
    sub.add_parser("facts").add_argument("id")
    return parser


def _verified_dates(registry: Path) -> dict[str, str]:
    with registry.open("rb") as handle:
        rows = cast(list[dict[str, object]], tomllib.load(handle).get("tool", []))
    return {str(row["id"]): str(row["verified"]) for row in rows if "verified" in row}


def _find(tools: Sequence[Tool], entry_id: str) -> Tool:
    for tool in tools:
        if tool.id == entry_id:
            return tool
    raise UsageError(f"unknown registry id {entry_id!r}")


def _run(
    argv: Sequence[str] | None,
    registry: Path,
    seams: Seams | None,
    root: Path | None,
    gh: Callable[[list[str]], str] | None,
) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    registry_path = args.registry if args.registry is not None else registry
    tools = load_tools(registry_path)
    home = seams.home if seams is not None else Path.home()
    if args.cmd == "facts":
        active = seams or default_seams(gh or functools.partial(run_output, timeout=60))
        facts = entry_facts(
            _find(tools, args.id), tools, active, verified=_verified_dates(registry_path)
        )
        print(facts, end="")
        return 0
    run = run_dir(args.root or root or RUN_ROOT, args.date)
    if args.cmd == "status":
        state = status(tools, run)
        print(f"next {state.next_id}" if state.next_id else "done")
        print(f"complete {state.complete}/{state.total}")
        for orphan in state.orphans:
            print(f"orphan {orphan}")
        return 0
    tool = _find(tools, args.id)
    write_report(run, tool.id, sys.stdin.read(), home=home)
    print(f"wrote {tool.id}.md")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    registry: Path = REGISTRY,
    seams: Seams | None = None,
    root: Path | None = None,
    gh: Callable[[list[str]], str] | None = None,
) -> int:
    try:
        return _run(argv, registry, seams, root, gh)
    except UsageError as exc:
        print(f"catalog-audit: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ReportRefused as exc:
        for reason in exc.reasons:
            print(f"refused: {reason}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as exc:
        print(f"catalog-audit: internal error: {exc!r}", file=sys.stderr)
        traceback.print_exc()
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
