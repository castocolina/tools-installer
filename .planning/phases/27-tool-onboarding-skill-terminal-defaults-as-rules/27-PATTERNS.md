# Phase 27: Tool-onboarding skill: terminal defaults as rules - Pattern Map

**Mapped:** 2026-11-19
**Files analyzed:** 8 (2 new Python, 1 new data file set, 5 modified)
**Analogs found:** 8 / 8 (all analogs verified git-tracked: `git ls-files` printed the skill files; test and devtools files are in-repo sources)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/skill_verdicts.py` (new) | utility (test helper) | transform | `tests/test_catalog_audit_skill.py:251-336` (the code being moved) | exact (pure move) |
| `tests/test_catalog_audit_skill.py` (modify) | test | transform | itself; imports the moved names | exact |
| `tests/test_tool_onboarding_skill.py` (new) | test | transform / file-I/O (read-only) | `tests/test_catalog_audit_skill.py` | exact |
| `.claude/skills/tool-onboarding/SKILL.md` (modify) | skill doc | n/a | same file (step 7 at :178-215, Common Mistakes :247-260) | exact |
| `.claude/skills/catalog-audit/SKILL.md` (modify, one line, :80) | skill doc | n/a | quote check at `tests/test_catalog_audit_skill.py:82-109` | exact |
| `devtools/docs_only.py` `TEST_READ` (modify) | config | request-response (classifier) | its own 24.3 entry at :28 | exact |
| `tests/test_docs_only.py` `LEDGER` (modify) | test config | transform | 24.3 rows at :205-222 | exact |
| `27-SKILLJUDGE-before.md`, `27-SKILLJUDGE-after.md` (new, in phase dir) | data | file-I/O | `.planning/milestones/v0.50.0-phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-FINAL.md` (format; read by RESEARCH) | exact |

## Pattern Assignments

### `tests/skill_verdicts.py` (utility, transform)

**Analog:** `tests/test_catalog_audit_skill.py:251-315` (move) plus `:318-336` (`_verdict` fixture builder, stays in the old file).

Move these names; drop the leading underscore on every name that crosses the module (strict pyright rejects private imports): `_VERDICT_KEYS` (:252-266), `_GRADE_FLOORS` (:267), `_PASS_PERCENT` (:268), `_DIMENSIONS` (:269), `_RUBRIC_MAX` (:270), `_grade` (:273-274), `_parse_verdict` (:277-315).

**Core pattern** (:277-290, :308-315):
```python
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
    ...
    percent = round(verdict["total"] / verdict["max_total"] * 100, 1)
    if verdict["percent"] != percent:
        raise ValueError(f"percent is {verdict['percent']}, rounding gives {percent}")
    if verdict["grade"] != _grade(percent):
        raise ValueError(f"grade {verdict['grade']} does not match {percent}")
    if final and percent < _PASS_PERCENT:
        raise ValueError(f"final percent {percent} is below {_PASS_PERCENT}")
    return verdict
```
Imports needed: `json`, `from typing import Any, cast`. No `.md` literal, so `markdown_literals()` adds nothing. The old file keeps `_verdict()` (hardcodes `"skill": "catalog-audit"`) and imports `DIMENSIONS`, `RUBRIC_MAX`, `grade`, `parse_verdict` from `tests.skill_verdicts`. Its tests (`test_verdict_parser_accepts_and_refuses` :339-378) must pass with no assertion edits. The return type `dict[str, object]` forces a `cast`/`float()` problem at the new call site; return `dict[str, Any]` instead.

---

### `tests/test_tool_onboarding_skill.py` (test, transform / read-only file I/O)

**Analog:** `tests/test_catalog_audit_skill.py`

**Header and path constants** (:1-17, :82):
```python
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, cast
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "catalog-audit"
SKILL = SKILL_DIR / "SKILL.md"
TOOL_ONBOARDING = REPO_ROOT / ".claude" / "skills" / "tool-onboarding" / "SKILL.md"
```
Build paths with the `/` operator so few `.md` literals appear (each one needs a `LEDGER` row).

**Pipe-row parser** (:84, :93-95):
```python
_SEPARATOR_ROW_RE = re.compile(r"\|[-|: ]+\|")

def _table_rows(text: str) -> set[str]:
    rows = {line.strip() for line in text.splitlines() if line.startswith("|")}
    return {r for r in rows if not _SEPARATOR_ROW_RE.fullmatch(r) and r != _GRAMMAR_HEADER}
```
Adapt: return an ordered list (not a set) so duplicates survive; slice from the table's `#### ` heading to the next `#### `/`### `; assert the header row's first cell is a fixed word; first cell fullmatch `` `([a-z0-9][a-z0-9._-]*)` `` (a Cyrillic lookalike fails); rule cells `re.match(r"(vendor|written|planned \(phase \d+\)|n/a|unverified)\b", cell)`.

**Whitespace-flattening needle assert** (:98-101), copy verbatim for SKILL-01/03/04/05 pins:
```python
def _assert_all_in(text: str, needles: tuple[str, ...]) -> None:
    flat = " ".join(text.split())  # a phrase may wrap across lines
    missing = [needle for needle in needles if needle not in flat]
    assert not missing, missing
```

**Local section helper** (do NOT import `_skill_section` from `tests/test_docs.py`; strict pyright). The logic to mirror is `tests/test_docs.py:318-324`:
```python
start = re.search(rf"^### {re.escape(number)}\. ", text, re.MULTILINE)
nxt = re.search(r"^### \d+b?\. ", text[start.end() :], re.MULTILINE)
return text[start.start() : start.end() + nxt.start()] if nxt else text[start.start() :]
```

**Registry side** (RESEARCH Pattern 3/4; `installer/model.py:584` `load_tools(manifest_path, *, today=None)`, `installer/enums.py:49,51`): `{t.id for t in load_tools(REGISTRY) if t.category in {Category.TERMINAL, Category.EDITOR}}`. `tmp_path` registry fixture shape from `tests/test_registry.py:1217-1233`:
```python
manifest = tmp_path / "registry.toml"
manifest.write_text(
    """
[[tool]]
id = "demo"
category = "dev"
tier = "user"
verified = 2026-10-13
[[tool.method]]
kind = "brew"
formula = "demo"
"""
)
```
Use `category = "terminal"`, append to the real registry text (copy `installer/registry.toml`), assert `table_drift(...) == ["no row for demo-term"]`. Unverified assumption (RESEARCH A1): terminal needs no extra key; run once.

**Verdict test** (analog :400-405, but with D-06 differences):
```python
verdicts = sorted(PHASE_DIR.glob("24.3-SKILLJUDGE-*.md"))
assert len(verdicts) == 3, PHASE_DIR  # a moved phase dir must fail, never pass on zero files
for path in verdicts:
    verdict = _parse_verdict(_text(path), final=path.stem.endswith("-FINAL"))
```
For phase 27: find the phase dir by `.planning/phases/27-*` and `.planning/milestones/*-phases/27-*`, require exactly one; count `27-SKILLJUDGE-*.md` excluding names containing `ROUND`, assert 2; select `27-SKILLJUDGE-before.md` / `27-SKILLJUDGE-after.md` by exact name; `final=False` (no 80% floor); compare `rubric_version`, `spec_sha`, and `float(after["percent"]) >= float(before["percent"])`. Boundary fixtures (equal passes, one point lower fails) reuse the `_verdict` fixture style (:318-336).

**Heading-quote coupling** (:104-109) is the existing guard the SKILL.md rename must satisfy:
```python
headings = _STEP_RE.findall(_text(SKILL))
onboarding = set(_text(TOOL_ONBOARDING).splitlines())
assert [h for h in headings if h not in onboarding] == []
```

---

### `.claude/skills/tool-onboarding/SKILL.md` (skill doc)

**Analog:** itself. Edit points (all read):
- Heading `### 7. Postinstall and customizations — ask the user, do not assume` at :178; new heading must be mirrored byte-for-byte in `catalog-audit/SKILL.md:80`.
- Old terminal bullet :185-191 replaced by the four rules; multiplexer/shell/LLM bullets :192-195 stay as questions.
- :209-210 "The onboarding author still asks the developer which customizations to build" and :241-242 "which customizations were offered" narrowed; Common Mistakes bullet :256-257 narrowed to non-terminal items.
- `#### macOS apps` goes at the end of step 4 (before `### 4b.` at :99); `#### Conflicts`, `#### Testing macOS behavior` and the closed table are `####` under step 7 so `_skill_section("7")` still returns them.
- Step 9 (:234-245) gets a literal `# Verified` example.

**Phrases pinned by tests, keep word for word on single lines** (`tests/test_docs.py:292-298, 339-342, 358-363`; current text at SKILL.md:200, :213-215, :190-191): `install-time tuning`, `no runtime question`, `reverted with the tool`, `outside any install`, `never becomes a Policies knob by default`, `A Policies row is only for something outside any install`, `zsh terminal sync`, `install tuning`, `never a Policies row`.
```
A Policies row is only for something outside any install (an installer-wide
guard, a background job, a host environment redirect), and a new requirement
never becomes a Policies knob by default.
```
Forbidden strings anywhere in the skill: `skill pack`/`skill_pack`/`skill_lifecycle`, `--no-verify`, `SKILL=`-style `SKIP=`, `present_agent_hosts`; the name `catalog-audit` appears on exactly one line (the When-to-Use bullet, `tests/test_catalog_audit_skill.py:211-216`); every line with `Policies` is ASCII; no table row copied into the audit skill (:112-117); no literal `|` inside a table cell.

---

### `.claude/skills/catalog-audit/SKILL.md` (one-line edit, line 80)

**Analog:** the quote at :80 is `` `### 7. Postinstall and customizations — ask the user, do not assume` `` and is matched by `_STEP_RE = re.compile(r"`(### \d+b?\. [^`]+)`")` (`tests/test_catalog_audit_skill.py:83`). Change it in the same commit as the heading rename and keep it byte-identical to the new heading line. Keep true the nearby statement "tuning is install-time, never a runtime question".

---

### `devtools/docs_only.py` `TEST_READ` (config)

**Analog:** `devtools/docs_only.py:20-29`
```python
TEST_READ: tuple[str, ...] = (
    "AGENTS.md",
    ...
    "tests/*",
    ".planning/milestones/v0.50.0-phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-*",
)
```
Add one entry `.planning/*27-SKILLJUDGE-*` (`fnmatchcase`, `*` crosses `/`, so it matches both `.planning/phases/27-.../` and `.planning/milestones/<v>-phases/27-.../`; it also covers ROUND files, the safe direction per the module docstring :3-5).

---

### `tests/test_docs_only.py` `LEDGER` (test config)

**Analog:** the 24.3 rows at :205-222.
```python
(
    "tests/test_catalog_audit_skill.py",
    ".planning",
): ".planning/milestones/v0.50.0-phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-*.md",
("tests/test_catalog_audit_skill.py", "SKILL.md"): ".claude/skills/*/SKILL.md",
```
Add one row per `.md` / `.planning*` string constant in `tests/test_tool_onboarding_skill.py` (expect `"SKILL.md"` -> `.claude/skills/*/SKILL.md`, `".planning"`, `"27-SKILLJUDGE-before.md"`, `"27-SKILLJUDGE-after.md"`). The value is a single `Path.glob` string and must match a file today (`test_every_ledger_glob_reads_test_read_files_only`, :271-281) and after archive: use `.planning/**/27-tool-onboarding-skill-terminal-defaults-as-rules/27-SKILLJUDGE-*.md` (RESEARCH A2: prove the `**` zero-or-more-dir match on this host in Wave 0). Missing or stale pairs fail `test_every_markdown_literal_in_the_tests_is_classified` (:263-268); the failure message lists them. The 24.3 rows stay. Docstrings count as string constants: keep `.md` words out of them.

---

### `27-SKILLJUDGE-before.md` / `27-SKILLJUDGE-after.md` (data)

**Analog:** `.planning/milestones/v0.50.0-phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-FINAL.md` (format per RESEARCH:216): title line, `- Date:`, `- Judge:` (fresh read-only subagent, rubric v4, path and commit), `## Summary (as printed)`, `## Verdict (verbatim)` with exactly one-line JSON in a ```json fence (the parser needs exactly one dict containing `"scores"`). The before file is committed before the rewrite and never re-run; extra rounds go in `27-SKILLJUDGE-ROUND-n.md`.

## Shared Patterns

### Pin-and-ledger discipline for markdown-reading tests
**Source:** `tests/test_docs_only.py:193-281`, `devtools/docs_only.py:20-35`
**Apply to:** `tests/test_tool_onboarding_skill.py`, `tests/skill_verdicts.py` (no literals), verdict files.
Any `.md`/`.planning` string constant in a test needs a `LEDGER` row and, when it reads a repo file, a `TEST_READ` match, or a docs-only push skips the tests.

### Strict typing for tests
**Source:** `tests/test_catalog_audit_skill.py:8, :286, :295-296` (`cast("dict[str, Any]", ...)` string-quoted casts).
**Apply to:** all new test code (pyright strict applies to `tests/`; vulture covers only `installer` and `devtools`).

### Count-before-iterate
**Source:** `tests/test_catalog_audit_skill.py:401-402`: `assert len(verdicts) == 3, PHASE_DIR`.
**Apply to:** every discovered-file loop in the new test (phase dir exactly one, verdict files exactly 2, table rows greater than zero).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `table_drift()` function | utility | transform | No existing set-diff-with-names helper; use RESEARCH Pattern 3 (list-based, names missing, extra and duplicate ids, fails on empty table) |

## Metadata

**Analog search scope:** `tests/`, `devtools/`, `.claude/skills/`, `.planning/milestones/v0.50.0-phases/24.3-*`
**Files read:** CONTEXT, RESEARCH, SPEC, `tests/test_catalog_audit_skill.py`, `devtools/docs_only.py:1-60`, `tests/test_docs_only.py:185-285`, `tests/test_registry.py:1210-1239`, `tests/test_docs.py:316-325`, `.claude/skills/tool-onboarding/SKILL.md:176-267`
**Pattern extraction date:** 2026-11-19
