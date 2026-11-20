"""Checks that keep the tool-onboarding skill's closed table honest."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest

from installer.enums import Category
from installer.model import load_tools

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / ".claude" / "skills" / "tool-onboarding" / "SKILL.md"
REGISTRY = REPO_ROOT / "installer" / "registry.toml"
TABLE_HEADING = "#### Closed per-terminal table"
_SEPARATOR_ROW_RE = re.compile(r"\|[-|: ]+\|")
ID_CELL_RE = re.compile(r"`([a-z0-9][a-z0-9._-]*)`")
STATUS_RE = re.compile(r"(?:vendor|written|unverified|n/a|planned \(phase \d+\))(?::|$)")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _step(text: str, number: str) -> str:
    start = re.search(rf"^### {re.escape(number)}\. ", text, re.MULTILINE)
    assert start, f"missing skill step {number}"
    nxt = re.search(r"^### \d+b?\. ", text[start.end() :], re.MULTILINE)
    return text[start.start() : start.end() + nxt.start()] if nxt else text[start.start() :]


def _subsection(text: str, heading: str) -> str:
    matches = list(re.finditer(r"^" + re.escape(heading) + r"$", text, re.MULTILINE))
    assert len(matches) == 1, f"expected one {heading!r}, found {len(matches)}"
    start = matches[0]
    nxt = re.search(r"^#### |^### ", text[start.end() :], re.MULTILINE)
    return text[start.start() : start.end() + nxt.start()] if nxt else text[start.start() :]


def table_rows(section: str) -> list[list[str]]:
    lines = [line for line in section.splitlines() if line.startswith("|")]
    lines = [line for line in lines if not _SEPARATOR_ROW_RE.fullmatch(line)]
    if not lines or lines[0].split("|")[1].strip() != "tool":
        raise ValueError("table header must start with tool")
    rows = [line.split("|")[1:-1] for line in lines[1:]]
    return [[cell.strip() for cell in row] for row in rows]


def table_ids(rows: Sequence[Sequence[str]]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        cell = row[0]
        match = ID_CELL_RE.fullmatch(cell)
        ids.append(match.group(1) if match else cell)
    return ids


def registry_ids(manifest: Path) -> set[str]:
    return {
        tool.id
        for tool in load_tools(manifest)
        if tool.category in {Category.TERMINAL, Category.EDITOR}
    }


def table_drift(registry_ids: Iterable[str], table_ids: Sequence[str]) -> list[str]:
    registry = set(registry_ids)
    table = set(table_ids)
    problems = [f"no row for {tool_id}" for tool_id in sorted(registry - table)]
    problems.extend(f"row for unknown id {tool_id}" for tool_id in sorted(table - registry))
    problems.extend(
        f"duplicate row {tool_id}"
        for tool_id in sorted({tool_id for tool_id in table_ids if table_ids.count(tool_id) > 1})
    )
    if not table_ids:
        problems.append("table has no rows")
    return problems


def bad_status_cells(rows: Sequence[Sequence[str]]) -> list[str]:
    names = ("(a) shell", "(b) word navigation", "(c) clear", "(d) same directory")
    problems: list[str] = []
    for row in rows:
        tool_id = row[0].strip("`")
        if len(row) != 7:
            problems.append(f"row {tool_id} has {len(row)} cells")
            continue
        problems.extend(
            f"row {tool_id} column {name}: {cell}"
            for name, cell in zip(names, row[2:6], strict=True)
            if STATUS_RE.match(cell) is None
        )
    return problems


def test_table_matches_the_registry() -> None:
    ids = table_ids(table_rows(_subsection(_text(SKILL), TABLE_HEADING)))
    assert ids
    assert table_drift(registry_ids(REGISTRY), ids) == []


@pytest.mark.parametrize(
    ("extra_ids", "expected"),
    [([], ["no row for demo-term"]), (["demo-term"], [])],
    ids=["no-row", "with-row"],
)
def test_table_drift_new_terminal_entry(
    tmp_path: Path, extra_ids: list[str], expected: list[str]
) -> None:
    addition = """
[[tool]]
id = "demo-term"
category = "terminal"
tier = "user"
verified = 2026-10-13
[[tool.method]]
kind = "brew"
formula = "demo"
"""
    manifest = tmp_path / "registry.toml"
    manifest.write_text(REGISTRY.read_text(encoding="utf-8") + addition, encoding="utf-8")
    real_ids = table_ids(table_rows(_subsection(_text(SKILL), TABLE_HEADING)))
    assert table_drift(registry_ids(manifest), real_ids + extra_ids) == expected


def test_table_drift_names_a_row_with_no_registry_entry() -> None:
    assert table_drift({"kitty"}, ["kitty", "ghostty"]) == ["row for unknown id ghostty"]


def _fixture(*first_cells: str) -> str:
    header = (
        "| tool | config file | (a) shell | (b) word navigation | (c) clear | "
        "(d) same directory | reload |"
    )
    rows = [f"| {cell} | x | n/a | n/a | n/a | n/a | x |" for cell in first_cells]
    return "\n".join((TABLE_HEADING, header, "| --- | --- | --- | --- | --- | --- | --- |", *rows))


@pytest.mark.parametrize(
    ("first_cells", "expected"),
    [
        (("`kitty`",), ["no row for wezterm"]),
        (("`kitty`", "`wezterm`", "`ghostty`"), ["row for unknown id ghostty"]),
        (("`kitty`", "`kitty`", "`wezterm`"), ["duplicate row kitty"]),
        (("`Kitty`", "`wezterm`"), ["no row for kitty", "row for unknown id `Kitty`"]),
        (("`wezterm`", "`kitty`"), []),
        ((), ["no row for kitty", "no row for wezterm", "table has no rows"]),
        (("`k\u0456tty`", "`wezterm`"), ["no row for kitty", "row for unknown id `k\u0456tty`"]),
    ],
    ids=["missing", "extra", "duplicate", "case-variant", "shuffled", "header-only", "lookalike"],
)
def test_table_drift_fixtures(first_cells: tuple[str, ...], expected: list[str]) -> None:
    ids = table_ids(table_rows(_fixture(*first_cells)))
    assert table_drift({"kitty", "wezterm"}, ids) == expected


def test_table_rows_refuse_a_wrong_header() -> None:
    with pytest.raises(ValueError, match="table header must start with tool"):
        table_rows(_fixture("`kitty`").replace("| tool |", "| name |", 1))


def test_table_rule_cells_start_with_a_status_word() -> None:
    real_rows = table_rows(_subsection(_text(SKILL), TABLE_HEADING))
    assert bad_status_cells(real_rows) == []
    bad_rows = table_rows(_fixture("`kitty`"))
    bad_rows[0][3] = "maybe: later"
    bad_rows[0][4] = "planned: soon"
    assert bad_status_cells(bad_rows) == [
        "row kitty column (b) word navigation: maybe: later",
        "row kitty column (c) clear: planned: soon",
    ]
    bad_rows[0][3:5] = ["planned (phase 29): x", "n/a"]
    assert bad_status_cells(bad_rows) == []
    bad_rows[0].append("extra")
    assert bad_status_cells(bad_rows) == ["row kitty has 8 cells"]


def test_table_sits_under_step_7() -> None:
    assert TABLE_HEADING in _step(_text(SKILL), "7")
