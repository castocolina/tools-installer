"""Checks on the catalog-audit project skill: its files, links and report template."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

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
    assert description.startswith("Audit ")
    assert "Use when" in description
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
            "newest major",
            "does not exist",
            "explicit approval",
            "dispositions.toml",
            'make verify-registry ARGS="--state',
            "make validate",
            "make test",
        ),
    )


def test_report_template_says_verbatim() -> None:
    assert "verbatim" in _text(TEMPLATE)


_MAKE_ARGS_RE = re.compile(r'make \S+ ARGS="[^"\n]*"')


def test_no_make_args_string_carries_shell_metacharacters() -> None:
    # make's recipe shell runs a backtick or $ inside ARGS="..." on the host (judge finding D8-1).
    for doc in (SKILL, TEMPLATE):
        for match in _MAKE_ARGS_RE.findall(_text(doc)):
            assert "`" not in match
            assert "$" not in match


def test_free_text_commands_skip_make() -> None:
    text = _text(SKILL)
    assert 'ARGS="add-finding' not in text
    assert 'ARGS="write' not in text
    direct = "uv run --isolated --no-dev python -m installer.catalog_audit"
    assert f"{direct} add-finding '<entry>'" in text
    assert f"{direct} write '<id>'" in text


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


PHASE_DIR = REPO_ROOT / ".planning" / "phases" / "24.3-catalog-audit-skill"
_VERDICT_KEYS = frozenset(
    {
        "skill",
        "judge",
        "rubric_version",
        "spec_sha",
        "scores",
        "max",
        "total",
        "max_total",
        "percent",
        "grade",
        "findings",
    }
)
_GRADE_FLOORS = ((90, "A"), (80, "B"), (70, "C"), (60, "D"))
_PASS_PERCENT = 80.0
_DIMENSIONS = tuple(f"D{i}" for i in range(1, 9))
_RUBRIC_MAX = (20, 15, 15, 15, 15, 15, 15, 15)


def _grade(percent: float) -> str:
    return next((grade for floor, grade in _GRADE_FLOORS if percent >= floor), "F")


def _parse_verdict(document: str, *, final: bool) -> dict[str, object]:
    """The one verdict line of a skill-judge document; ValueError names the reason."""
    candidates: list[dict[str, Any]] = []
    for line in document.splitlines():
        try:
            obj = json.loads(line.strip())
        except ValueError:
            continue
        if isinstance(obj, dict) and "scores" in obj:
            candidates.append(cast("dict[str, Any]", obj))
    if len(candidates) != 1:
        raise ValueError(f"expected one verdict line, found {len(candidates)}")
    verdict = candidates[0]
    missing = _VERDICT_KEYS - verdict.keys()
    if missing:
        raise ValueError(f"missing keys {sorted(missing)}")
    if not isinstance(verdict["scores"], dict) or not isinstance(verdict["max"], dict):
        raise ValueError("scores and max must be objects")
    scores = cast("dict[str, int]", verdict["scores"])
    maxima = cast("dict[str, int]", verdict["max"])
    if scores.keys() != maxima.keys():
        raise ValueError("scores and max name different dimensions")
    if scores.keys() != set(_DIMENSIONS):
        raise ValueError("scores must name exactly D1..D8")
    for dim, score in scores.items():
        if not 0 <= score <= maxima[dim]:
            raise ValueError(f"{dim} score {score} outside 0..{maxima[dim]}")
    if verdict["total"] != sum(scores.values()):
        raise ValueError("total is not the sum of scores")
    if verdict["max_total"] != sum(maxima.values()):
        raise ValueError("max_total is not the sum of max")
    percent = round(verdict["total"] / verdict["max_total"] * 100, 1)
    if verdict["percent"] != percent:
        raise ValueError(f"percent is {verdict['percent']}, rounding gives {percent}")
    if verdict["grade"] != _grade(percent):
        raise ValueError(f"grade {verdict['grade']} does not match {percent}")
    if final and percent < _PASS_PERCENT:
        raise ValueError(f"final percent {percent} is below {_PASS_PERCENT}")
    return verdict


def _verdict(
    points: tuple[int, ...] = (16, 12, 12, 12, 12, 12, 12, 13), **overrides: Any
) -> dict[str, Any]:
    total, max_total = sum(points), sum(_RUBRIC_MAX)
    percent = round(total / max_total * 100, 1)
    verdict: dict[str, Any] = {
        "skill": "catalog-audit",
        "judge": "fixture",
        "rubric_version": 4,
        "spec_sha": "0" * 40,
        "scores": dict(zip(_DIMENSIONS, points, strict=True)),
        "max": dict(zip(_DIMENSIONS, _RUBRIC_MAX, strict=True)),
        "total": total,
        "max_total": max_total,
        "percent": percent,
        "grade": _grade(percent),
        "findings": [],
    }
    return verdict | overrides


def test_verdict_parser_accepts_and_refuses() -> None:
    good = _verdict()
    assert (good["total"], good["max_total"], good["percent"], good["grade"]) == (
        101,
        125,
        80.8,
        "B",
    )
    assert _parse_verdict("Summary text\n\n" + json.dumps(good), final=True)["percent"] == 80.8
    no_findings = {k: v for k, v in good.items() if k != "findings"}
    no_d8_max = {k: v for k, v in good["max"].items() if k != "D8"}
    refused = {
        "percent rounding": (json.dumps(_verdict(percent=80.7)), "rounding gives 80.8"),
        "grade": (json.dumps(_verdict(grade="A")), "does not match"),
        "missing findings": (json.dumps(no_findings), "missing keys"),
        "two lines": (json.dumps(good) + "\n" + json.dumps(good), "found 2"),
        "no line": ("no verdict here", "found 0"),
        "total": (json.dumps(_verdict(total=102)), "total is not the sum"),
        "max_total": (json.dumps(_verdict(max_total=126)), "max_total is not the sum"),
        "score above max": (
            json.dumps(_verdict(scores={**good["scores"], "D1": 21})),
            "outside 0..20",
        ),
        "score below zero": (
            json.dumps(_verdict(scores={**good["scores"], "D1": -1})),
            "outside 0..20",
        ),
        "scores key missing from max": (
            json.dumps(_verdict(max=no_d8_max)),
            "different dimensions",
        ),
    }
    for name, (document, reason) in refused.items():
        with pytest.raises(ValueError, match=re.escape(reason)):
            _parse_verdict(document, final=False)
        assert name
    low = json.dumps(_verdict((14, 11, 11, 11, 11, 11, 11, 11)))
    assert _parse_verdict(low, final=False)["grade"] == "C"
    with pytest.raises(ValueError, match="below 80.0"):
        _parse_verdict(low, final=True)


def test_resume_eval_fixture_is_a_partial_run() -> None:
    evals = {e["id"]: e for e in json.loads(_text(EVALS))["evals"]}
    files = [SKILL_DIR / name for name in evals["resume-after-interruption"]["files"]]
    assert all(path.is_file() for path in files)
    assert sorted(files[0].parent.iterdir()) == sorted(files)
    registry = {tool.id for tool in catalog_audit.load_tools(catalog_audit.REGISTRY)}
    stems = {path.stem for path in files}
    assert (len(stems & registry), stems - registry) == (2, {"gone-tool"})
    for path in files:
        body = _text(path).rstrip("\n")
        assert body.endswith(catalog_audit.FOOTER), path.name
        if path.stem in registry:
            report = body.removesuffix(catalog_audit.FOOTER)
            home = Path("/nonexistent-home")
            assert catalog_audit.validate_report(report, path.stem, home=home) == [], path.name


def test_skill_judge_verdicts_are_well_formed() -> None:
    for path in sorted(PHASE_DIR.glob("24.3-SKILLJUDGE-*.md")):
        verdict = _parse_verdict(_text(path), final=path.stem.endswith("-FINAL"))
        assert "catalog-audit" in str(verdict["skill"]), path.name
