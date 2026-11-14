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
import platform
import re
import shutil
import sys
import traceback
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NoReturn

from installer import versions
from installer.atomic import atomic_write_text
from installer.locations import ensure_dir
from installer.model import Tool, load_tools
from installer.platform import detect_os
from installer.run import run_output
from installer.verify_registry import github_token
from installer.versions import Fetch, resolve_github_release

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
    target = run / f"{entry_id}.md"
    _refuse_symlink_leaf(target)
    if _is_complete(target):
        problems.append(f"{entry_id}.md is already complete; a new date starts a new run")
    if problems:
        raise ReportRefused(problems)
    ensure_dir(run)
    atomic_write_text(target, text.rstrip("\n") + "\n\n" + FOOTER + "\n")
    return target


def entry_facts(tool: Tool, tools: Sequence[Tool], seams: Seams) -> str:
    """The fact block for one entry."""
    lines = [f"# facts: {tool.id}", "- methods:"]
    lines.extend(f"  - {method.kind}" for method in tool.methods)
    output = seams.probe([tool.cmd, "--version"])
    installed = versions.extract_observed_version(output) if output else None
    lines.append(f"- installed: {installed or 'not installed'}")
    for method in tool.methods:
        repo = method.params.get("repo")
        if method.kind == "github_release" and isinstance(repo, str):
            tag = resolve_github_release(repo, seams.fetch).tag
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            lines.append(f"- latest: {tag} ({url})")
    return "\n".join(lines) + "\n"


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
    tools = load_tools(args.registry if args.registry is not None else registry)
    home = seams.home if seams is not None else Path.home()
    if args.cmd == "facts":
        active = seams or default_seams(gh or functools.partial(run_output, timeout=60))
        print(entry_facts(_find(tools, args.id), tools, active), end="")
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
