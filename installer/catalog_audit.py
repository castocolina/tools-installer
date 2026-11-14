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
import ast
import contextlib
import functools
import http.client
import io
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

from installer import verify_registry, versions
from installer.agent_settings import DYNAMIC_KEYS, TUNING_GROUPS, setting_keys
from installer.atomic import atomic_write_bytes, atomic_write_text
from installer.locations import ensure_dir
from installer.model import ELEVATION_COMMANDS, Method, Tool, load_tools, method_package
from installer.ownership import ManagerOwnership
from installer.platform import detect_os
from installer.postinstall import HARNESS_PRESENCE, POSTINSTALL_HOOKS
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
CHECKOUT = Path(__file__).resolve().parents[1]
RUN_ROOT = CHECKOUT / ".planning" / "audits" / "catalog"
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
        cells = _cells(row)
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


def _split_sections(
    body: list[tuple[int, str]], problems: list[str]
) -> tuple[dict[str, list[str]], list[str]]:
    """The `## ` sections of a report body (numbered non-empty lines) and their order."""
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current: list[str] | None = None
    for n, line in body:
        if line.startswith("## "):
            name = line[3:].strip()
            order.append(name)
            current = sections.setdefault(name, [])
        elif current is None:
            problems.append(f"line {n}: text before the first section")
        else:
            current.append(line)
    return sections, order


def _cells(row: str) -> list[str]:
    """The three cells of a `| check | status | source |` row (the source keeps any `|`)."""
    return [cell.strip() for cell in row.strip("|").split("|", 2)]


def validate_report(text: str, entry_id: str, *, home: Path) -> list[str]:
    """Every way `text` breaks the report grammar; an empty list means it is valid."""
    problems = _hygiene(text, home)
    body = [(n, line.rstrip()) for n, line in enumerate(text.splitlines(), 1) if line.strip()]
    title = _TITLE_RE.fullmatch(body[0][1]) if body else None
    if title is None or title["id"] != entry_id:
        problems.append(f"the first line must be '# {entry_id} - catalog audit YYYY-MM-DD'")
    elif _DATE_RE.fullmatch(title["day"]) is None:
        problems.append(f"the title date {title['day']!r} is not YYYY-MM-DD")
    sections, order = _split_sections(body[1:], problems)
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


def _write_run_file(run: Path, name: str, text: str) -> Path:
    """Write one run-directory file whole; never through a symlink at the leaf."""
    target = run / name
    _refuse_symlink_leaf(target)
    ensure_dir(run)
    atomic_write_text(target, text)
    return target


# ---- verify: the once-per-run verify-registry record (D-03) ----


def _state_refusal(state: Path, repo: Path) -> str | None:
    """Why `state` is no scratch state for verify-registry, or None.

    verify-registry persists its state during a run even without --write, so it must never
    be pointed at the default HOME state or at a file the checkout tracks.
    """
    resolved = state.resolve()
    if resolved == verify_registry.default_state_path().resolve():
        return "--state is verify-registry's default HOME state; name a scratch path"
    if resolved.is_relative_to(repo.resolve()):
        return "--state lies inside the repo checkout; name a scratch path"
    if resolved.exists():
        try:
            json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "--state names an existing file that is not JSON"
    return None


def record_verify(
    run: Path,
    state: Path,
    repo: Path,
    home: Path,
    verify_main: Callable[[list[str]], int],
) -> Path:
    """Run verify-registry once against the scratch `state` and store its report whole.

    A warm HOME state is copied to an absent scratch path first (HOME is only read). The
    recorded exit code is data; the final gate reads it, so this does not fail on drift.
    """
    problem = _state_refusal(state, repo)
    if problem is not None:
        raise UsageError(problem)
    warm = verify_registry.default_state_path()
    if not state.exists() and warm.is_file():
        ensure_dir(state.parent)
        atomic_write_bytes(state, warm.read_bytes())
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = verify_main(["--state", str(state)])
    body = _tilde(captured.getvalue(), home).rstrip("\n")
    return _write_run_file(
        run, "verify-registry.md", f"# verify-registry - {run.name}\nexit: {code}\n\n{body}\n"
    )


# ---- scan: the script surfaces and their mechanical unsafe patterns (SPEC R3) ----

_PY_SURFACES = (
    "installer/postinstall.py",
    "installer/post_install.py",
    "installer/agent_settings.py",
    "installer/guards.py",
    "installer/env_redirect.py",
    "installer/cursor_shim.py",
)
_SH_SURFACES = ("scripts/*.sh", "scripts/lib/*.sh")
INSTALLER_OWNER = "(installer)"
MAINTAINER_OWNER = "(maintainer)"


@dataclass(frozen=True, order=True)
class ScanRow:
    """One `scripts.md` row: `line` is 0 for an `ok` row (the whole file was read)."""

    path: str
    line: int
    entry: str
    status: str
    pattern: str


def _surfaces(repo: Path) -> list[str]:
    found = [name for name in _PY_SURFACES if (repo / name).is_file()]
    for pattern in _SH_SURFACES:
        found.extend(p.relative_to(repo).as_posix() for p in repo.glob(pattern) if p.is_file())
    return sorted(found)


def _default_entry(path: str) -> str:
    if path.startswith("scripts/"):
        return MAINTAINER_OWNER
    return "cursor-agent" if path == "installer/cursor_shim.py" else INSTALLER_OWNER


_TARGET_RE = re.compile(r"--target[= ](?:auto|all)\b")
# `exec <one command word> "$@"`: the only shim exec line that passes argv straight through.
_EXEC_CLEAN_RE = re.compile(r'exec (?:"\$\w+"|\$\w+|[\w./+-]+) "\$@"')
_PLACEHOLDER = "{…}"
_ELEVATION = "|".join(sorted(re.escape(name) for name in ELEVATION_COMMANDS))
_SHELL_ELEVATION_RE = re.compile(
    r"(?:^|[;&|`(]|\b(?:if|then|elif|else|do|while|until)\s)\s*"
    rf"(?P<cmd>(?:\S*/)?(?:{_ELEVATION}))(?![\w-])"
)
_QUOTED_RE = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'")


@dataclass(frozen=True)
class _Hit:
    """One mechanical finding; `entries` empty means the surface's own entry."""

    line: int
    pattern: str
    entries: tuple[str, ...] = ()


def _str_const(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _as_map(node: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], node) if isinstance(node, dict) else {}


def _assignments(tree: ast.AST) -> list[tuple[str, ast.expr]]:
    found: list[tuple[str, ast.expr]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                found.append((node.targets[0].id, node.value))
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            found.append((node.target.id, node.value))
    return found


def _docstrings(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        scope = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        if isinstance(node, scope) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and _str_const(first.value) is not None:
                ids.add(id(first.value))
    return ids


def _sequence_hits(node: ast.List | ast.Tuple) -> list[_Hit]:
    hits: list[_Hit] = []
    head = _str_const(node.elts[0]) if node.elts else None
    if head is not None and head.rsplit("/", 1)[-1] in ELEVATION_COMMANDS:
        hits.append(_Hit(node.elts[0].lineno, f"`{head}` elevation command at the head of an argv"))
    for current, following in zip(node.elts, node.elts[1:], strict=False):
        value = _str_const(following)
        if _str_const(current) == "--target" and value in ("auto", "all"):
            hits.append(_Hit(current.lineno, f"`--target` argv with `{value}`"))
    return hits


def _render(node: ast.Constant | ast.JoinedStr) -> str:
    """The template text; every formatted value of an f-string shows as a placeholder."""
    if isinstance(node, ast.Constant):
        return str(node.value)
    return "".join(_str_const(part) or _PLACEHOLDER for part in node.values)


def _string_hits(node: ast.Constant | ast.JoinedStr, lines: list[str]) -> list[_Hit]:
    """Target and shim-exec findings of one string constant or f-string template."""
    hits: list[_Hit] = []
    rendered = _render(node)
    match = _TARGET_RE.search(rendered)
    if match is not None:
        line = node.lineno + rendered.count("\n", 0, match.start())
        hits.append(_Hit(line, f"`{match[0]}` registers every host"))
    span = range(node.lineno - 1, node.end_lineno or node.lineno)
    for raw in rendered.splitlines():
        text = raw.strip()
        while text.startswith(_PLACEHOLDER):  # a formatted value that ends with a newline
            text = text.removeprefix(_PLACEHOLDER).lstrip()
        if not text.startswith("exec ") or _EXEC_CLEAN_RE.fullmatch(text):
            continue
        holed = _PLACEHOLDER in text
        fragment = text.split(_PLACEHOLDER, 1)[0] if holed else text
        line = next((i + 1 for i in span if fragment + ("{" if holed else "") in lines[i]), None)
        if line is None:  # the source line escapes characters the render does not
            fragment = "exec"
            line = next((i + 1 for i in span if "exec" in lines[i]), node.lineno)
        hits.append(_Hit(line, f"`{fragment}` shim exec line rewrites argv: {text}"))
    return hits


def _target_map_hits(tree: ast.Module, tools: Sequence[Tool]) -> list[_Hit]:
    """Target-map keys outside the presence ids; the entries are the hook's tools."""
    assigned = _assignments(tree)
    hook_of: dict[str, str] = {}
    for name, value in assigned:
        if name == "POSTINSTALL_HOOKS" and isinstance(value, ast.Dict):
            for key, hook in zip(value.keys, value.values, strict=True):
                if (hook_id := _str_const(key)) and isinstance(hook, ast.Call):
                    for kw in hook.keywords:
                        if kw.arg == "targets" and isinstance(kw.value, ast.Name):
                            hook_of[kw.value.id] = hook_id
    hits: list[_Hit] = []
    for name, value in assigned:
        if not name.endswith("_TARGETS") or not isinstance(value, ast.Dict):
            continue
        hook_id = hook_of.get(name, "")
        shipped = POSTINSTALL_HOOKS.get(hook_id)
        allowed = set(HARNESS_PRESENCE) | set(shipped.standalone if shipped else ())
        owners = tuple(sorted(t.id for t in tools if hook_id and t.postinstall == hook_id))
        for key in value.keys:
            text = _str_const(key)
            if key is not None and text is not None and text not in allowed:
                hits.append(_Hit(key.lineno, f"`{text}` is not a HARNESS_PRESENCE id", owners))
    return hits


def _deref(root: Mapping[str, object], node: object) -> Mapping[str, object]:
    """`node` with local `#/...` references followed (bounded, so a cycle ends)."""
    current = _as_map(node)
    for _ in range(16):
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/"):
            break
        target: object = root
        for part in ref[2:].split("/"):
            target = _as_map(target).get(part)
        current = _as_map(target)
    return current


def _schema_verdict(schema: Mapping[str, object], path: tuple[str, ...]) -> tuple[str, str] | None:
    """(part, verdict) for the first part of `path` the schema deprecates or disallows."""
    node = _deref(schema, schema)
    for part in path:
        properties = _as_map(node.get("properties"))
        if part not in properties:
            return (part, "not allowed") if node.get("additionalProperties") is False else None
        child = _as_map(properties[part])
        node = _deref(schema, child)
        if child.get("deprecated") is True or node.get("deprecated") is True:
            return part, "deprecated"
    return None


def _schema_hits(tree: ast.Module, schemas: Mapping[str, Mapping[str, object]]) -> list[_Hit]:
    """`_KEYS` tuning key paths the agent's vendor schema deprecates or does not allow."""
    hits: list[_Hit] = []
    for name, value in _assignments(tree):
        if name != "_KEYS" or not isinstance(value, ast.Dict):
            continue
        for key, row in zip(value.keys, value.values, strict=True):
            agent = _str_const(key.elts[0]) if isinstance(key, ast.Tuple) and key.elts else None
            schema = schemas.get(agent) if agent else None
            if agent is None or schema is None:
                continue
            for call in ast.walk(row):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
                    continue
                first = call.args[0] if call.args else None
                if call.func.id != "SettingKey" or not isinstance(first, ast.Tuple):
                    continue
                path = tuple(_str_const(part) or "" for part in first.elts)
                verdict = _schema_verdict(schema, path)
                if verdict is not None:
                    where = f" (key path {'.'.join(path)})" if len(path) > 1 else ""
                    pattern = f"`{verdict[0]}` {verdict[1]} in the {agent} schema{where}"
                    hits.append(_Hit(first.lineno, pattern, (agent,)))
    return hits


def _py_hits(
    path: str,
    text: str,
    tools: Sequence[Tool],
    schemas: Mapping[str, Mapping[str, object]],
) -> list[_Hit]:
    """Findings of one Python surface, read as text by `ast` and never imported."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [_Hit(exc.lineno or 1, "`SyntaxError` the surface does not parse")]
    lines = text.splitlines()
    nested = {id(c) for j in ast.walk(tree) if isinstance(j, ast.JoinedStr) for c in ast.walk(j)}
    skip = _docstrings(tree) | nested
    hits: list[_Hit] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.List | ast.Tuple):
            hits.extend(_sequence_hits(node))
        elif isinstance(node, ast.JoinedStr) or (
            isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
        ):
            hits.extend(_string_hits(node, lines))
    if path == "installer/postinstall.py":
        hits.extend(_target_map_hits(tree, tools))
    return [*hits, *_schema_hits(tree, schemas)]


def _blank_quotes(line: str) -> str:
    """The line without quoted words (a printed hint), keeping quotes that hold `$(...)`."""

    def blank(match: re.Match[str]) -> str:
        text = match[0]
        return text if "$(" in text or "`" in text else '""'

    return _QUOTED_RE.sub(blank, line)


def _shell_hits(text: str) -> list[_Hit]:
    hits: list[_Hit] = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        found = _SHELL_ELEVATION_RE.search(_blank_quotes(line))
        if found is not None:
            hits.append(
                _Hit(number, f"`{found['cmd']}` elevation command at a shell command position")
            )
    return hits


def scan(
    repo: Path, tools: Sequence[Tool], schemas: Mapping[str, Mapping[str, object]]
) -> list[ScanRow]:
    """An `ok` row per clean surface and a `finding` row per mechanical unsafe pattern."""
    rows: set[ScanRow] = set()
    for path in _surfaces(repo):
        text = (repo / path).read_text(encoding="utf-8", errors="replace")
        hits = _shell_hits(text) if path.endswith(".sh") else _py_hits(path, text, tools, schemas)
        default = _default_entry(path)
        if not hits:
            rows.add(ScanRow(path, 0, default, "ok", ""))
        for hit in hits:
            for entry in hit.entries or (default,):
                rows.add(ScanRow(path, hit.line, entry, "finding", hit.pattern.replace("\n", " ")))
    return sorted(rows)


def read_schemas(specs: Sequence[str]) -> dict[str, Mapping[str, object]]:
    """Vendor JSON schemas the agent fetched to a scratch dir, read as data (`AGENT=PATH`)."""
    schemas: dict[str, Mapping[str, object]] = {}
    for spec in specs:
        agent, sep, where = spec.partition("=")
        if not (sep and agent and where):
            raise UsageError(f"--schema wants AGENT=PATH, got {spec!r}")
        try:
            data: object = json.loads(Path(where).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise UsageError(f"--schema {agent}: cannot read {where} as JSON") from None
        if not isinstance(data, dict):
            raise UsageError(f"--schema {agent}: {where} is not a JSON object")
        schemas[agent] = cast(dict[str, object], data)
    return schemas


def scan_text(day: str, rows: Sequence[ScanRow]) -> str:
    lines = [
        f"# scripts - {day}",
        "",
        "| location | entry | status | pattern |",
        "|---|---|---|---|",
    ]
    for row in rows:
        where = f"{row.path}:{row.line}" if row.line else row.path
        lines.append(f"| {where} | {row.entry} | {row.status} | {row.pattern} |")
    return "\n".join(lines) + "\n"


def _read_scan(run: Path) -> list[ScanRow]:
    path = run / "scripts.md"
    if not path.is_file():
        return []
    rows: list[ScanRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|", 3)]
        if not line.startswith("| ") or len(cells) != 4 or cells[2] not in ("ok", "finding"):
            continue
        name, _, number = cells[0].partition(":")
        rows.append(ScanRow(name, int(number) if number.isdigit() else 0, *cells[1:]))
    return rows


# ---- summarize: SUMMARY.md rebuilt from what is on disk (SPEC R4) ----


def _parse_report(path: Path) -> dict[str, list[str]]:
    """The sections of a complete report, without its title and footer."""
    text = path.read_text(encoding="utf-8")
    body = [
        (n, line.rstrip())
        for n, line in enumerate(text.splitlines(), 1)
        if line.strip() and line.strip() != FOOTER
    ]
    return _split_sections(body[1:], [])[0]


def _verify_lines(run: Path) -> list[str]:
    path = run / "verify-registry.md"
    if not path.is_file():
        return ["not recorded"]
    lines = path.read_text(encoding="utf-8").splitlines()
    drift: list[str] = []
    for line in lines[lines.index("## Drift") + 1 :] if "## Drift" in lines else []:
        if not line.startswith("- "):
            break
        drift.append(line)
    return [next((x for x in lines if x.startswith("exit: ")), "exit: unknown"), *drift]


def _token(text: str) -> str | None:
    """The first backticked span of `text`, without its backticks."""
    found = _SPAN_RE.search(text)
    return found[0][1:-1] if found else None


def _line_has(repo: Path, location: str, token: str) -> bool:
    """True when line N of `path:N` still holds `token` at exact token boundaries."""
    name, _, number = location.rpartition(":")
    try:
        target = (repo / name).resolve()
        if not target.is_relative_to(repo.resolve()) or int(number) < 1:
            return False
        text = target.read_text(encoding="utf-8").splitlines()[int(number) - 1]
    except (OSError, ValueError, IndexError):
        return False
    return re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text) is not None


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _script_findings(
    run: Path, reports: Mapping[str, Mapping[str, list[str]]], repo: Path
) -> list[str]:
    """Scan findings and report rows citing `path:line` with a backticked token, by path."""
    found: set[tuple[str, int, str, str]] = set()
    for row in _read_scan(run):
        if row.status == "finding":
            found.add((row.path, row.line, row.entry, row.pattern))
    for entry, sections in reports.items():
        for check in sections.get("Checks", [])[2:]:
            _, state, source = _cells(check)
            cite = _CITATION_RE.search(source)
            if state == "drift" and cite is not None and _token(source) is not None:
                name, _, number = cite[0].rpartition(":")
                found.add((name, int(number), entry, source))
    lines = ["| location | entry | status | pattern | state |", "|---|---|---|---|---|"]
    for name, number, entry, pattern in sorted(found):
        token = _token(pattern)
        fresh = token is None or _line_has(repo, f"{name}:{number}", token)
        lines.append(
            f"| {name}:{number} | {entry} | drift | {_cell(pattern)} | "
            f"{'current' if fresh else 'stale'} |"
        )
    return lines if found else ["none"]


def summarize(tools: Sequence[Tool], run: Path, *, repo: Path) -> str:
    """The audit summary: a pure function of the run directory, with no timestamp."""
    state = status(tools, run)
    reports = {
        tool.id: _parse_report(run / f"{tool.id}.md")
        for tool in tools
        if _is_complete(run / f"{tool.id}.md")
    }
    lines = [f"# Catalog audit - {run.name}", f"complete {state.complete}/{state.total}"]
    lines.extend(f"missing {tool.id}" for tool in tools if tool.id not in reports)
    lines.extend(f"orphan {orphan}" for orphan in state.orphans)
    changes = [
        f"- {entry}: {line[2:]}"
        for entry, sections in reports.items()
        for line in sections.get("Proposed changes", [])
        if line != "- none"
    ]
    drift = [
        f"| {entry} | {name} | drift | {source} | proposed |"
        for entry, sections in reports.items()
        for name, state_, source in (_cells(row) for row in sections.get("Checks", [])[2:])
        if state_ == "drift"
    ]
    lines += ["", "## Proposed changes", *(changes or ["no proposed changes"])]
    table = ["| entry | check | status | source | disposition |", "|---|---|---|---|---|"]
    lines += ["", "## Drift", *([*table, *drift] if drift else ["none"])]
    lines += ["", "## verify-registry", *_verify_lines(run)]
    scanned = [f"- {r.path} {r.entry}: ok" for r in _read_scan(run) if r.status == "ok"]
    lines += ["", "## Script scan", *(scanned or ["not recorded"])]
    lines += ["", "## Script findings", *_script_findings(run, reports, repo)]
    return "\n".join(lines) + "\n"


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Catalog audit fact gatherer and report writer.")
    parser.add_argument("--registry", type=Path, default=None, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("status", "write", "verify", "scan", "summarize"):
        cmd = sub.add_parser(name)
        if name == "write":
            cmd.add_argument("id")
        cmd.add_argument("--date", required=True)
        cmd.add_argument("--root", type=Path, default=None)
        if name in ("verify", "scan", "summarize"):
            cmd.add_argument("--repo", type=Path, default=CHECKOUT)
        if name == "verify":
            cmd.add_argument("--state", type=Path, required=True)
        if name == "scan":
            cmd.add_argument("--schema", action="append", default=[], metavar="AGENT=PATH")
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
    verify_main: Callable[[list[str]], int] | None,
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
    if args.cmd == "verify":
        record_verify(run, args.state, args.repo, home, verify_main or verify_registry.main)
        print("wrote verify-registry.md")
    elif args.cmd == "scan":
        _write_run_file(
            run,
            "scripts.md",
            scan_text(args.date, scan(args.repo, tools, read_schemas(args.schema))),
        )
        print("wrote scripts.md")
    elif args.cmd == "summarize":
        _write_run_file(run, "SUMMARY.md", summarize(tools, run, repo=args.repo))
        print("wrote SUMMARY.md")
    else:
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
    verify_main: Callable[[list[str]], int] | None = None,
) -> int:
    try:
        return _run(argv, registry, seams, root, gh, verify_main)
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
