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
RULES_HEADING = "#### Terminal and IDE defaults"
EXTRAS_HEADING = "#### Extras are asked"
ASK_RE = re.compile(
    r"\bask(?:s|ed)?\b[^.]{0,80}\b(?:word navigation|clear|scrollback|"
    r"zsh terminal sync|current directory|same directory)\b",
    re.IGNORECASE,
)
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


def rule_items(section: str) -> dict[str, str]:
    lines = section.splitlines()
    starts = [index for index, line in enumerate(lines) if re.match(r"^- \(([a-d])\) ", line)]
    items: dict[str, str] = {}
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        item_lines: list[str] = []
        for line in lines[start:end]:
            if not line.strip():
                break
            item_lines.append(line)
        match = re.match(r"^- \(([a-d])\) ", lines[start])
        assert match
        items[match.group(1)] = " ".join(" ".join(item_lines).split())
    return items


def ask_sentences(text: str) -> list[str]:
    return ASK_RE.findall(" ".join(text.split()))


def option_as_alt_unnegated(text: str) -> list[str]:
    units = re.split(r"[.;|]", " ".join(text.split()))
    hits: list[str] = []
    for unit in units:
        if re.search(r"option-as-alt|macos_option_as_alt", unit, re.IGNORECASE) and not re.search(
            r"\b(?:never|not|no|without)\b", unit, re.IGNORECASE
        ):
            hits.append(unit.strip())
    return hits


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


def test_rules_are_four_separate_items() -> None:
    text = _text(SKILL)
    section = _subsection(text, RULES_HEADING)
    starts = re.findall(r"^- \(([a-d])\) ", section, re.MULTILINE)
    assert len(starts) == 4
    assert sorted(starts) == ["a", "b", "c", "d"]


def test_rules_name_their_os_and_behavior() -> None:
    items = rule_items(_subsection(_text(SKILL), RULES_HEADING))
    needles = {
        "a": ("Linux", "Bazzite", "zsh is the launched shell", "zsh terminal sync"),
        "b": (
            "macOS",
            "Option+Left",
            "Option+Right",
            "only those two chords",
            "never the global Option-as-Alt switch",
            "Spanish",
            "`@`",
            "`|`",
            "`#`",
            "`\\\\`",
        ),
        "c": (
            "Cmd+K on macOS",
            "Ctrl+Shift+K on Linux",
            "clear the screen and the scrollback",
            "sends Ctrl+L",
            "planned for phase 28",
        ),
        "d": ("current directory", "tab", "window", "pane", "vendor default"),
    }
    assert set(items) == set(needles)
    for letter, anchors in needles.items():
        assert all(anchor in items[letter] for anchor in anchors), letter


def test_rules_are_not_questions() -> None:
    section = " ".join(_subsection(_text(SKILL), RULES_HEADING).split())
    phrases = (
        "that has the capability",
        "`n/a` with the reason",
        "none of them is a question",
        "never a Policies row",
    )
    for phrase in phrases:
        assert phrase in section


def test_rules_and_table_sections_are_ascii() -> None:
    text = _text(SKILL)
    assert _subsection(text, RULES_HEADING).isascii()
    assert _subsection(text, TABLE_HEADING).isascii()


def test_rules_sit_under_step_7_before_the_table() -> None:
    text = _text(SKILL)
    step = _step(text, "7")
    assert RULES_HEADING in step
    assert TABLE_HEADING in step
    assert step.index(RULES_HEADING) < step.index(TABLE_HEADING)


def test_rules_no_sentence_asks_about_a_default() -> None:
    assert ask_sentences(_text(SKILL)) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Ask the developer whether to enable word navigation.",
            ["Ask the developer whether to enable word navigation"],
        ),
        (
            "Ask the user if Ctrl+Shift+K should clear the scrollback.",
            ["Ask the user if Ctrl+Shift+K should clear the scrollback"],
        ),
        ("Offer, ask, record.", []),
        ("These four rules apply without asking: none of them is a question.", []),
    ],
)
def test_rules_ask_detector_flags_a_question(text: str, expected: list[str]) -> None:
    assert ask_sentences(text) == expected


def test_rules_option_as_alt_is_only_named_to_forbid_it() -> None:
    assert option_as_alt_unnegated(_text(SKILL)) == []
    assert option_as_alt_unnegated("Turn on the global Option-as-Alt switch for word navigation.")
    assert option_as_alt_unnegated("Set macos_option_as_alt yes in kitty.conf.")
    assert option_as_alt_unnegated("never the global Option-as-Alt switch") == []


def test_rules_extras_stay_questions() -> None:
    text = _text(SKILL)
    section = " ".join(_subsection(text, EXTRAS_HEADING).split())
    for phrase in (
        "Multiplexers/agent workspaces",
        "Shells/prompts/editors",
        "LLM tools",
        "offer them to the developer",
        "Each accepted extra",
    ):
        assert phrase in section
    for phrase in (
        "word navigation",
        "Cmd+K",
        "Ctrl+Shift+K",
        "scrollback",
        "Option+Left",
        "current directory",
    ):
        assert phrase not in section
    headings = re.findall(r"^#### .+$", _step(text, "7"), re.MULTILINE)
    assert headings[-1] == EXTRAS_HEADING


def test_rules_common_mistakes_narrowed() -> None:
    text = _text(SKILL)
    mistakes = text[text.index("## Common Mistakes") :]
    flat = " ".join(mistakes.split())
    for phrase in (
        "Shipping a non-terminal extra nobody asked for",
        "Asking the developer about one of the four terminal defaults",
        "Never use the global Option-as-Alt switch for word navigation",
    ):
        assert phrase in flat


def test_rules_frontmatter_overview_and_step_9() -> None:
    text = _text(SKILL)
    description = next(
        line.removeprefix("description: ")
        for line in text.splitlines()
        if line.startswith("description: ")
    )
    assert "the four defaults applied as rules" in description
    assert "which extras to offer" in description
    assert len(description) <= 1024
    overview = text[text.index("## Overview") : text.index("## When to Use")]
    assert "The one exception is the closed per-terminal table under step 7" in overview
    assert "which extras were offered" in " ".join(_step(text, "9").split())


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
