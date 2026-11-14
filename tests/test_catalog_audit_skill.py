"""Checks on the catalog-audit project skill: its files, links and report template."""

from __future__ import annotations

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
