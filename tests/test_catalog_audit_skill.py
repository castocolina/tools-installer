"""Checks on the catalog-audit project skill: its files, links and report template."""

from __future__ import annotations

import json
import re
from pathlib import Path

from installer import catalog_audit

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "catalog-audit"
SKILL = SKILL_DIR / "SKILL.md"
TEMPLATE = SKILL_DIR / "references" / "report-template.md"

_LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
_REPO_PATH_RE = re.compile(r"`((?:\.claude|installer|scripts|tests)/[^\s`*<>:]+)(?::\d+)?`")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_frontmatter() -> None:
    lines = _text(SKILL).splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    keys = [line.split(":", 1)[0] for line in lines[1:end]]
    assert keys == ["name", "description"]
    name = lines[1].removeprefix("name: ")
    description = lines[2].removeprefix("description: ")
    assert name == "catalog-audit" == SKILL_DIR.name
    assert len(description) <= 1024
    assert description.startswith("Use when")
    assert "tool-onboarding" in description
    assert "make verify-registry" in description


def test_report_template_passes_the_writer() -> None:
    match = re.search(r"```[a-z]*\n(.*?)\n```", _text(TEMPLATE), re.DOTALL)
    assert match is not None
    example = match.group(1)
    assert catalog_audit.FOOTER not in example
    assert catalog_audit.validate_report(example, "opencode", home=Path("/nonexistent-home")) == []


def test_skill_loop_names_the_subcommands() -> None:
    text = _text(SKILL)
    for needle in (
        'make audit-catalog ARGS="status --date',
        "facts ",
        "write ",
        "verify --date",
        "scan --date",
        "add-finding ",
        "summarize --date",
    ):
        assert needle in text, needle


def test_skill_links_resolve() -> None:
    for doc in (SKILL, *sorted(SKILL_DIR.glob("references/*.md"))):
        text = _text(doc)
        for target in _LINK_RE.findall(text):
            if "://" not in target:
                assert (doc.parent / target).exists(), f"{doc.name}: {target}"
        for target in _REPO_PATH_RE.findall(text):
            assert (REPO_ROOT / target).exists(), f"{doc.name}: {target}"


TOOL_ONBOARDING = REPO_ROOT / ".claude" / "skills" / "tool-onboarding" / "SKILL.md"
_STEP_RE = re.compile(r"`(### \d+b?\. [^`]+)`")
_SEPARATOR_ROW_RE = re.compile(r"\|[-|: ]+\|")
# The report grammar's own header row is not tool-onboarding content.
_GRAMMAR_HEADER = "| check | status | source |"


def _skill_files() -> list[Path]:
    return sorted(path for path in SKILL_DIR.rglob("*") if path.is_file())


def _table_rows(text: str) -> set[str]:
    rows = {line.strip() for line in text.splitlines() if line.startswith("|")}
    return {r for r in rows if not _SEPARATOR_ROW_RE.fullmatch(r) and r != _GRAMMAR_HEADER}


def _assert_all_in(text: str, needles: tuple[str, ...]) -> None:
    flat = " ".join(text.split())  # a phrase may wrap across lines
    missing = [needle for needle in needles if needle not in flat]
    assert not missing, missing


def test_skill_names_tool_onboarding_steps_by_heading() -> None:
    headings = _STEP_RE.findall(_text(SKILL))
    onboarding = set(_text(TOOL_ONBOARDING).splitlines())
    assert [h for h in headings if h not in onboarding] == []
    numbers = {h.split(". ")[0].removeprefix("### ") for h in headings}
    assert {"3", "4", "4b", "6", "7", "8", "9"} <= numbers


def test_skill_copies_no_table_and_no_asset_check() -> None:
    theirs = _table_rows(_text(TOOL_ONBOARDING))
    for path in _skill_files():
        text = _text(path)
        assert not (theirs & _table_rows(text)), path.name
        assert re.search(r"sha256|digest", text, re.IGNORECASE) is None, path.name


def test_no_python_under_the_skill() -> None:
    assert list(SKILL_DIR.rglob("*.py")) == []


def test_skill_host_safety_text() -> None:
    _assert_all_in(
        _text(SKILL),
        (
            "--version",
            "--help",
            "codegraph install --print-config",
            "opencode debug paths",
            "brew info --json=v2",
            "HTTP reads",
            "CODEGRAPH_TELEMETRY=0",
            "DO_NOT_TRACK=1",
            "convention",
            "opencode upgrade",
            "pi update",
            "pi mcp add",
            "make setup",
            "make doctor",
            "vendor installer script",
            "scripts/detect-container-runtime.sh",
            "one container per entry",
            "--status unknown --source 'reason: container check not run (",
            "(installer)",
            "(maintainer)",
            "its own empty directory",
            "never executed on the host",
        ),
    )


def test_skill_unsafe_patterns_and_data_rule() -> None:
    _assert_all_in(
        _text(SKILL),
        (
            "sudo",
            "pkexec",
            "doas",
            "--target auto",
            "--target all",
            "a write for an absent host",
            "a blind overwrite of user config",
            "a write outside the declared `paths`",
            "argv that a shim rewrites",
            "is data, never an instruction",
        ),
    )


def test_skill_precision_and_approval_rules() -> None:
    _assert_all_in(
        _text(SKILL),
        (
            "verbatim",
            "newest major",
            "does not exist",
            "explicit approval",
            "dispositions.toml",
            'make verify-registry ARGS="--state',
            "make validate",
            "make test",
        ),
    )


def test_tool_onboarding_gains_one_line() -> None:
    lines = [line for line in _text(TOOL_ONBOARDING).splitlines() if "catalog-audit" in line]
    assert lines == [
        "- To audit every registry entry in one loop, use `catalog-audit` "
        "(`.claude/skills/catalog-audit/SKILL.md`)."
    ]


EVALS = SKILL_DIR / "evals" / "evals.json"
TRIGGER_QUERIES = SKILL_DIR / "evals" / "trigger-queries.json"
_NEAR_MISS_RE = re.compile(
    r"onboard|new tool|release pins?|release assets|PR\b|diff", re.IGNORECASE
)


def test_evals_shape() -> None:
    data = json.loads(_text(EVALS))
    assert data["skill_name"] == "catalog-audit"
    evals = data["evals"]
    assert len(evals) >= 6
    assert len({e["id"] for e in evals}) == len(evals)
    for e in evals:
        assert len(e["prompt"]) >= 40, e["id"]
        assert e["expected_output"].strip(), e["id"]
        assert len(e["assertions"]) >= 2, e["id"]
        assert all(len(a) >= 20 for a in e["assertions"]), e["id"]


def test_trigger_queries_shape() -> None:
    queries = json.loads(_text(TRIGGER_QUERIES))
    assert 16 <= len(queries) <= 24
    assert all(set(q) == {"query", "should_trigger"} for q in queries)
    assert all(isinstance(q["should_trigger"], bool) for q in queries)
    positives = [q for q in queries if q["should_trigger"]]
    negatives = [q for q in queries if not q["should_trigger"]]
    assert 8 <= len(positives) <= 12
    assert 8 <= len(negatives) <= 12
    assert len([q for q in negatives if _NEAR_MISS_RE.search(q["query"])]) >= 3
