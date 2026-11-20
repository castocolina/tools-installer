# Phase 27: Tool-onboarding skill: terminal defaults as rules - Research

**Researched:** 2026-11-19
**Domain:** Markdown skill rewrite plus pytest checks that pin it (no `installer/` change, no new package)
**Confidence:** HIGH (every cited line was read this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
D-01..D-16 in `27-CONTEXT.md` are locked and are not repeated here. The ones that shape the tests:
- D-01: the closed table is a Markdown pipe table inside `SKILL.md`, under step 7 as a `####` subsection, first cell the backticked registry id.
- D-02: each rule cell starts with one of `vendor`, `written`, `planned (phase N)`, `n/a`, `unverified`; columns: config file, (a) shell, (b) word navigation, (c) clear, (d) same directory, reload.
- D-03: registry side = `load_tools(REGISTRY)` filtered to `Category.TERMINAL` and `Category.EDITOR`, compared as exact string sets.
- D-04: new `tests/test_tool_onboarding_skill.py`; `_parse_verdict` and `_grade` move into `tests/skill_verdicts.py`, imported by both test files.
- D-05: pure `table_drift(registry_ids, table_ids)`; inline string fixtures (missing, extra, duplicate, case variant, shuffled, header-only, non-ASCII lookalike) plus one `tmp_path` registry.
- D-06: verdicts from a fresh read-only subagent running user-level `skill-judge` (rubric v4); files `27-SKILLJUDGE-before.md` and `27-SKILLJUDGE-after.md`; no 80% floor; after percent >= before percent.
- D-07: phase dir found by globbing `.planning/phases/27-*` and `.planning/milestones/*-phases/27-*`, exactly one match; `TEST_READ` and `LEDGER` get entries.
- D-08: if after < before, fix and re-judge as `27-SKILLJUDGE-ROUND-n.md`; the before verdict is never re-run.
- D-09: step 7 keeps its number, gets a new heading; the four rules, the table, `#### Conflicts` and `#### Testing macOS behavior` are `####` subsections of step 7; the `catalog-audit` line 80 heading quote changes in the same commit.
- D-10: `#### macOS apps` under step 4. D-11: other text edits. D-12..D-16: wording of conflicts, Konsole, CI job, rule (c) as planned.

### Claude's Discretion
Exact heading text of the renamed step 7, the order of the four rules, the wording of the status words' legend.

### Deferred Ideas (OUT OF SCOPE)
Verifying kitty/Alacritty/herdr live behavior (phases 29-31); a dmg method kind and a cask CLI-link param; per-IDE keybindings (SKILL-07); MACAPP-01; real-Mac checks.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SKILL-01 | Four terminal rules applied without asking | Pinned-phrase list below; `rg` negative check; section is a `####` under step 7 so `_skill_section("7")` still sees it |
| SKILL-02 | Closed per-terminal table + coverage test | Parser, `table_drift`, fixtures, `tmp_path` registry (Validation Architecture) |
| SKILL-03 | Conflict rule, `partial: kept yours` | `#### Conflicts` text pins; real `partial:` producers read in code |
| SKILL-04 | macOS app rule | `#### macOS apps` under step 4; real mechanisms verified in code |
| SKILL-05 | macOS testing rule | CI job facts verified in `ci.yml`; `#### Testing macOS behavior` pins |
| SKILL-06 | skill-judge before/after | Judge procedure, verdict storage, test, docs-only ledger |
</phase_requirements>

## Summary

The phase is a text rewrite guarded by tests. Every moving part already has a pattern in the repo: pipe-row parsing and heading-quote checks (`tests/test_catalog_audit_skill.py`), a verdict parser (`:277-315`), the docs-only classifier with a markdown-literal ledger (`devtools/docs_only.py`, `tests/test_docs_only.py`), and phrase pins on step 7 (`tests/test_docs.py`). No package is added.

Three traps decide whether the plan works. (1) Any new test file that mentions a `.md` or `.planning` string literal fails `test_every_markdown_literal_in_the_tests_is_classified` until each `(test file, literal)` pair is in `LEDGER`; and `test_every_ledger_glob_reads_test_read_files_only` demands every non-None glob match at least one file today, so a two-location glob cannot be written as two separate ledger values for one literal. (2) `tests/test_docs.py` pins step 7 text and `catalog-audit` quotes step 7's heading, so the rename must keep the pinned phrases word for word. (3) pyright runs in strict mode on `tests/`, so importing the private `_skill_section` from `tests/test_docs.py` fails `reportPrivateUsage`; write a small local section helper.

**Primary recommendation:** Build in this order: shared `tests/skill_verdicts.py` (pure move, existing tests stay green), then the before verdict on the unedited skill, then the SKILL.md rewrite plus the `catalog-audit` line, then the new test file with `LEDGER` and `TEST_READ` entries, then the after verdict.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Rules, table, conflict, macOS rules | Skill document (`.claude/skills/tool-onboarding/SKILL.md`) | - | Process aid; never writes `installer/*.py` |
| Table vs registry coverage | Test (`tests/test_tool_onboarding_skill.py`) | `installer/model.py` `load_tools` | Test reads the skill and the loader; read-only |
| Verdict parsing and grading | Test helper (`tests/skill_verdicts.py`) | - | Shared by two test files |
| Docs-only CI classification of the verdict files | `devtools/docs_only.py` `TEST_READ` | `tests/test_docs_only.py` `LEDGER` | A test-read markdown file must not skip the push gate |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest (+ xdist, existing) | project pin in `pyproject.toml` | tests | `make test` runs `pytest -n auto` [VERIFIED: .claude/testing.md:21-28] |
| stdlib `re`, `json`, `pathlib`, `tomllib` | Python >=3.11 (`pyproject.toml:5`: `requires-python = ">=3.11"`) | parsers | already used by the sibling test |
| `installer.model.load_tools`, `installer.enums.Category` | in repo | registry side of the comparison | `def load_tools(manifest_path: str | Path, *, today: date | None = None) -> list[Tool]` [VERIFIED: installer/model.py:584]; `TERMINAL = "terminal"`, `EDITOR = "editor"` [VERIFIED: installer/enums.py:49,51] |

### Alternatives Considered
None: decisions are locked. No new package; Package Legitimacy Audit does not apply ("none - no external package is installed by this phase").

## Architecture Patterns

### Data flow
```
registry.toml --load_tools--> {tool.id for terminal/editor} ----\
                                                                 table_drift(reg, table) -> [] or message naming ids
SKILL.md --_section(step 7 -> "#### <table heading>")--> pipe rows -> first cell (strip backticks) -/
SKILL.md rows --first word of each rule cell--> must be in closed status list

phase dir (glob 2 locations, exactly 1) --> 27-SKILLJUDGE-{before,after}.md --_parse_verdict--> percent
   assert skill, rubric_version, spec_sha equal across both; after.percent >= before.percent
```

### Recommended structure
```
tests/skill_verdicts.py              # moved: _VERDICT_KEYS, _GRADE_FLOORS, _DIMENSIONS, _RUBRIC_MAX, grade, parse_verdict(final=)
tests/test_catalog_audit_skill.py    # imports the helpers; keeps PHASE_DIR + its 3-file test
tests/test_tool_onboarding_skill.py  # table, rules, verdict tests
```

### Pattern 1: shared helper move (D-04)
Move `_GRADE_FLOORS`, `_PASS_PERCENT`, `_DIMENSIONS`, `_RUBRIC_MAX`, `_VERDICT_KEYS`, `_grade`, `_parse_verdict` [VERIFIED: tests/test_catalog_audit_skill.py:252-315]. Drop the leading underscore on names that cross the module boundary (strict pyright rejects private imports). `test_catalog_audit_skill.py` also uses `_verdict()` (`:318-336`), `_RUBRIC_MAX` and `_DIMENSIONS` in `test_verdict_parser_accepts_and_refuses`, so those names must be imported too; keep `_verdict` in the old file (it hardcodes `"skill": "catalog-audit"`). The move is pure: the old file's tests must pass with no assertion edits. `tests/skill_verdicts.py` contains no `.md` literal, so `markdown_literals()` adds nothing for it (it scans every `tests/**/*.py`, `tests/test_docs_only.py:27-45`).

### Pattern 2: table parser
Follow `_table_rows` [VERIFIED: tests/test_catalog_audit_skill.py:93-95] and `_SEPARATOR_ROW_RE = re.compile(r"\|[-|: ]+\|")` (`:84`). Slice the text from the table's `#### ` heading to the next `#### ` or `### ` heading, take lines starting with `|`, drop the separator and the header row (the header row's first cell is a fixed word such as `tool`; assert it, so a header-only table yields zero ids and fails). First cell: `re.fullmatch(r"`([a-z0-9][a-z0-9._-]*)`", cell)`. A non-ASCII lookalike (Cyrillic `а`) fails this fullmatch, so it never produces an id and the row is reported as malformed or as the registry id missing; both fail (R2 encoding edge). The id pattern comes from `TOOL_ID_RE` use at `installer/model.py:591` (`id must match [a-z0-9][a-z0-9._-]*`).

### Pattern 3: `table_drift`
```python
def table_drift(registry_ids: Iterable[str], table_ids: Sequence[str]) -> list[str]:
    reg, seen = set(registry_ids), list(table_ids)
    problems = [f"no row for {i}" for i in sorted(reg - set(seen))]
    problems += [f"row for unknown id {i}" for i in sorted(set(seen) - reg)]
    problems += [f"duplicate row {i}" for i in sorted({i for i in seen if seen.count(i) > 1})]
    if not seen:
        problems.append("table has no rows")
    return problems
```
`table_ids` is a list, not a set, so a duplicate and a case variant (`Kitty` vs `kitty`: not in registry, so "unknown id", plus "no row for kitty") both fail. A shuffled list returns `[]`. Fixtures are inline strings, as D-05 says.

### Pattern 4: loader filter end to end
One `tmp_path` registry: copy the real `installer/registry.toml` text and append a minimal block. Model the block on the loader fixture in `tests/test_registry.py:1217-1233`, which carries `id`, `category`, `tier`, `verified` and one `[[tool.method]]` with `kind = "brew"` and `formula`:
```toml
[[tool]]
id = "demo-term"
category = "terminal"
tier = "user"
verified = 2026-10-13
[[tool.method]]
kind = "brew"
formula = "demo"
```
Assert `table_drift(ids_from(tmp_registry), real_table_ids) == ["no row for demo-term"]`. A real-registry test asserts `== []`. Note `load_tools` also validates other fields; run the fixture once to be sure the minimal block loads (the `test_registry.py` fixture loads with only those keys, but that fixture has `category = "dev"`; confirm `terminal` needs nothing more, e.g. `cmd`). If the loader rejects it, add the smallest missing key. [ASSUMED: terminal category needs no extra key]

### Anti-Patterns
- Counting rows instead of comparing ids (a swapped id keeps the count).
- Reading the table with `_skill_section` imported from `tests/test_docs.py`: strict pyright forbids the private import [VERIFIED: pyproject.toml:44 `typeCheckingMode = "strict"`; no test imports a `_name` from `tests.test_docs`]. Write a local `_slice(text, heading)`.
- Putting `####` subsections after a new `### ` heading: `_skill_section("7")` at `tests/test_docs.py:318-324` ends at the next `^### \d+b?\. ` line, so anything under a differently shaped `###` heading drops out of "step 7". Keep the four rules, the table, Conflicts and Testing macOS as `####` under step 7 (D-09).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Verdict validation | a second parser | moved `parse_verdict` (D-04) | already checks keys, sums, rounding, grade |
| Registry ids | a TOML regex over `registry.toml` | `load_tools` + `Category` | validates ids, matches the catalog's own view (D-03) |
| Phase-dir lookup | hard-coded path | the two-location glob (D-07) | the dir moves on milestone archive |
| Skill scoring | self-assessment | the user-level `skill-judge` skill | the recorded rubric is the evidence |

## Common Pitfalls

### Pitfall 1: `LEDGER` and `TEST_READ` for a two-location glob
**What goes wrong:** `test_every_ledger_glob_reads_test_read_files_only` runs `ROOT.glob(glob)`, asserts the result is non-empty, and asserts every match is not a docs path [VERIFIED: tests/test_docs_only.py:271-281]. The ledger value is a single glob string per `(test file, literal)` pair [VERIFIED: tests/test_docs_only.py:193]. The phase dir is `.planning/phases/27-.../` today and `.planning/milestones/v0.51.0-phases/27-.../` after archive, so a milestones-only glob fails now and a phases-only glob fails after archive.
**How to avoid (prescriptive):** use one recursive ledger glob that resolves in both locations: `.planning/**/27-tool-onboarding-skill-terminal-defaults-as-rules/27-SKILLJUDGE-*.md`. `Path.glob` `**` matches zero or more directories, so it matches both `.planning/phases/27-.../` and `.planning/milestones/v0.51.0-phases/27-.../`. [ASSUMED: `**` zero-dir and multi-dir behavior on Python 3.11-3.15; the planner's Wave 0 must prove it with a scratch glob on this host before relying on it.] In the test, find the dir with the two globs from D-07 and assert exactly one match. For `TEST_READ` (an `fnmatchcase` list where `*` crosses `/`, `devtools/docs_only.py:18-35`) add one pattern, `.planning/*27-SKILLJUDGE-*`, which matches both locations; it also matches `27-SKILLJUDGE-ROUND-n.md`, which is correct (D-08 round files are read by nothing, but marking them test-read only forces a full run, which is safe: the classifier errs toward a full run, `docs_only.py:3-5`).
**Warning signs:** `test_every_ledger_glob_reads_test_read_files_only` fails with "resolves to no file".

### Pitfall 2: every `.md` and `.planning` literal in the new test needs a `LEDGER` row
`markdown_literals()` returns `(rel path, literal)` for each string constant ending `.md`, equal to `.planning`, or starting `.planning/` [VERIFIED: tests/test_docs_only.py:27-45]; the ledger test fails on both unclassified and stale pairs [VERIFIED: tests/test_docs_only.py:263-268]. For `tests/test_tool_onboarding_skill.py` expect rows for: `"SKILL.md"` (glob `.claude/skills/*/SKILL.md`, as the sibling does at `:214`), `".planning"` (the verdict glob), `"27-SKILLJUDGE-before.md"`, `"27-SKILLJUDGE-after.md"` (and any `"27-SKILLJUDGE-*.md"` glob literal), and `"milestones"`-style fragments only if they end `.md` (they do not). Prefer building paths with `/` operators from `ROOT / ".claude"`, so few literals appear. Run `uv run pytest tests/test_docs_only.py -q` after writing the test; its failure message lists new and stale pairs. The 24.3 rows stay (the old test still reads them). Strings inside docstrings count as constants too: keep `.md` words out of docstrings or classify them with `None`.

### Pitfall 3: step 7 pins in `tests/test_docs.py`
These must hold word for word after the rewrite:
- `_INSTALL_TUNING_RULE_PHRASES` = `"install-time tuning"`, `"no runtime question"`, `"reverted with the tool"`, `"outside any install"`, `"never becomes a Policies knob by default"` (whole file text) [VERIFIED: tests/test_docs.py:292-298]. Note `"install-time tuning"` has a hyphen; the current skill text has it at line 200 of SKILL.md ("It is install-time tuning").
- `_POLICIES_RULE_SENTENCES` = `"A Policies row is only for something outside any install"`, `"never becomes a Policies knob by default"` [VERIFIED: tests/test_docs.py:339-342]. They are matched as raw substrings with no whitespace normalisation, so a line wrap inside them fails; keep each on one line as in SKILL.md:213-215 (the first sentence sits on one line there).
- every line containing `Policies` is ASCII (`tests/test_docs.py:313-315`). The Spanish reason must not share a line with the word Policies; the Spanish characters `@ | # \` are ASCII anyway, but avoid typographic quotes and em dashes on Policies lines.
- `_skill_section("7")` must contain `"zsh terminal sync"`, `"install tuning"`, `"never a Policies row"` [VERIFIED: tests/test_docs.py:358-363]. The current sentence "never a Policies row" is at SKILL.md:190-191 ("a `post_install` action), never a Policies row"). Keep one such sentence under step 7, in the new rule text.
- no `skill_pack`, `skill_lifecycle` text and no regex `skill.pack` match (`:311-312`, `:352-355`): do not write "skill pack" anywhere in the skill, including the new rule text.
- step 4b keeps its TOML examples, `cargo_distrobox` block and params (`:327-336`, `:366-379`); step 8 contains `removal_plan` (`:382-387`). Adding `#### macOS apps` under step 4 (not 4b) does not touch them. The `_skill_section("4b")` regex `^### 4b\. ` ends at the next `^### \d+b?\. ` line (step 5), so `#### macOS apps` placed at the end of step 4, before `### 4b.`, belongs to step 4 only.
- `tests/test_hook_wiring.py:17` `_BYPASS` forbids the strings `--no-verify` and `SKIP=` in every skill file (`:108`, `:202-209`). The new text must not contain them, including as a "never do" example.
- `tests/test_postinstall.py:608-609` forbids `present_agent_hosts` in skills.
- `tests/test_catalog_audit_skill.py:211-216` requires exactly one line mentioning `catalog-audit` in the tool-onboarding skill (the "When to Use" bullet). The new text must not name `catalog-audit` anywhere else.
- `tests/test_catalog_audit_skill.py:82-109` (`_STEP_RE`, `test_skill_names_tool_onboarding_steps_by_heading`): every heading quoted as `` `### N. ...` `` in the audit skill must exist as a full line in tool-onboarding, and numbers 3, 4, 4b, 6, 7, 8, 9 must be quoted. `catalog-audit/SKILL.md:80` quotes `### 7. Postinstall and customizations — ask the user, do not assume` [VERIFIED: .claude/skills/catalog-audit/SKILL.md:79-80 area, line 80 text read this session]. Change both in one commit and keep the quoted text byte-identical to the new heading line (the heading contains an em dash today; the audit skill's quote must match whatever the new heading is). The audit skill's line 80-81 also says "Its TUNE-04 rule applies as written there: tuning is install-time, never a runtime question"; keep that statement true of the new step 7.
- `tests/test_catalog_audit_skill.py:112-117` `test_skill_copies_no_table_and_no_asset_check`: no table row of tool-onboarding may appear verbatim in any catalog-audit skill file, and the audit skill must not contain `sha256` or `digest`. The new table is only in tool-onboarding; do not copy rows into the audit skill.

### Pitfall 4: the verdict test must not use the 24.3 80% floor
The moved `parse_verdict` keeps its `final` flag; call it with `final=False` for both files (D-06). The last recorded score for this skill was 68.8% D with D7 = 0 per D-06; the skill has no `evals/` directory today [VERIFIED: `ls .claude/skills/tool-onboarding` shows only `SKILL.md`], so D7 stays low and a floor would fail.

### Pitfall 5: percent is compared as a number
Parse returns `percent` as float rounded to one decimal; compare `after >= before` directly, no rounding step (R7 precision edge). Boundary fixtures: equal passes, one point lower fails (`_verdict` style fixtures with `percent` computed). An unparseable percent must raise `ValueError` (the parser already does), not compare as zero.

## Code Examples

### Verdict test shape
```python
def _phase_dir() -> Path:
    found = [p for g in (".planning/phases/27-*", ".planning/milestones/*-phases/27-*")
             for p in ROOT.glob(g) if p.is_dir()]
    assert len(found) == 1, found
    return found[0]

def test_skill_judge_verdicts() -> None:
    folder = _phase_dir()
    assert len(list(folder.glob("27-SKILLJUDGE-*.md"))) == 2 + len(list(folder.glob("27-SKILLJUDGE-ROUND-*.md")))
    before = parse_verdict((folder / "27-SKILLJUDGE-before.md").read_text("utf-8"), final=False)
    after = parse_verdict((folder / "27-SKILLJUDGE-after.md").read_text("utf-8"), final=False)
    for v in (before, after):
        assert "tool-onboarding" in str(v["skill"])
    assert before["rubric_version"] == after["rubric_version"]
    assert before["spec_sha"] == after["spec_sha"]
    assert float(after["percent"]) >= float(before["percent"])  # numbers, never rounded again
```
D-06 says "the glob finds exactly 2"; because D-08 allows `27-SKILLJUDGE-ROUND-n.md` "outside the counted names", count with a glob that excludes `ROUND` (for example `[p for p in folder.glob("27-SKILLJUDGE-*.md") if "ROUND" not in p.name]`) and assert 2. Select before and after by exact name, never sort order (R7 ordering edge). `float(...)` on `object` values needs a `cast` under strict pyright; make `parse_verdict` return a `dict[str, Any]` or cast at the call.

### Rule pins (SKILL-01, 03, 04, 05, 06 edges)
Read the skill text, collapse whitespace (`" ".join(text.split())`, as `_assert_all_in` does at `tests/test_catalog_audit_skill.py:98-101`) and assert needles. Needles to pin, chosen from the spec acceptance lines:
- SKILL-01: the four rule anchors (for example `zsh` + `Bazzite`, `Option+Left` and `Option+Right`, `Cmd+K` and `Ctrl+Shift+K`, `current directory`), the Spanish reason (`@`, `|`, `#`, `\` with `Spanish`), and `none of them is a question`.
- SKILL-03: `partial: kept yours`; the displaced default `scroll_line_up`; `never overridden`.
- SKILL-04: `~/Applications`, `~/.local/bin`, `says why` (the spec calls it the "says why" clause), `uninstall`, `# Verified`.
- SKILL-05: `golden-file`, `validate-and-test`, `macos-latest`, `deferred to the owner's Mac` (or the exact UAT phrase the author writes; pin what is written).
- R6 negative: no line in the skill matches an ask-pattern over the four defaults. Use a regex that fails on `ask(?:s|ed)?\b[^.\n]{0,80}\b(word navigation|clear|scrollback|zsh)` limited to the step-7 subsections for the four rules, and assert no recommending sentence for `macos_option_as_alt` (the phrase may appear only in a `never`/`not` sentence): assert every line containing `macos_option_as_alt` or `Option-as-Alt` also contains `never`, `not`, or `without`. Keep this a test of the rewritten text, with a mutation fixture (a string that asks) proving the regex fails.
Assert ASCII on the rule subsections' key names (R3-R6 encoding edge): `"Cmd"`, `"Option"`, `"Ctrl"`, `"Shift"` spelled as ASCII words.

### CI job facts (verified this session)
`.github/workflows/ci.yml:15-50`: job id `validate-and-test`, `name: validate & test on ${{ matrix.os }}`, matrix `os: [ubuntu-latest, macos-latest]`; step `Classify the change` runs `python -m devtools.docs_only` and every later step has `if: steps.scope.outputs.full != 'false'`; step `Test` runs `make test` (with `PYTEST_XDIST_AUTO_NUM_WORKERS`) [VERIFIED: .github/workflows/ci.yml:10-50 read this session]. A test may pin `validate-and-test` and `macos-latest` in the skill AND check that the workflow file still contains those strings, so the skill cannot drift from CI. Reading `ci.yml` adds no `.md` literal.

### Real mechanisms the skill may name (D-10), each read this session
- cask with appdir: `runner(["brew", "install", "--cask", f"--appdir={applications_dir()}", require_str(method, "cask")])` [VERIFIED: installer/executors.py:699-704]; `applications_dir()` returns `Path.home() / "Applications"` [VERIFIED: installer/locations.py:89-91].
- `app` kind params: `"app": frozenset({"url", "app", "cli", "cli_name", "version", "sha256", "smoke_argv"})`; `cask` params `frozenset({"cask", "app", "min_os_version", "smoke_argv"})` [VERIFIED: installer/model.py:96,105]. A `.zip` is extracted with `["ditto", "-x", "-k", ...]` [VERIFIED: installer/apps.py:143]; no `dmg` string was found by the CONTEXT research and none added.
- `partial:` producers (for the Conflicts section): `f"alacritty: partial: you already bind {...}"` [VERIFIED: installer/terminal_shell.py:598]; `_HERDR_PARTIAL = "herdr: partial: you already set terminal.default_shell"` [VERIFIED: installer/terminal_shell.py:768]; consumer matches the `partial:` prefix [VERIFIED: installer/version_status.py:1598].
- vscode already meets rule (a): `keys.append(SettingKey((f"terminal.integrated.defaultProfile.{profile}",), "zsh"))` [VERIFIED: installer/agent_settings.py:746] (CONTEXT cites 740-748; the append is line 746).
- Rule (c) is planned, not present: a grep of `installer/*.py` for `bindkey` and `clear-screen` returned no match [VERIFIED: grep this session]. Alacritty is the only terminal with `post_install = ["apply_terminal_tuning"]` [VERIFIED: installer/registry.toml:3164, inside the `alacritty` block starting at :3153].
- Table ids today (the eight rows): `vscode` (:2466), `jetbrains-toolbox` (:2532), `sublime` (:2582), `neovim` (:2662), `kitty` (:3016), `wezterm` (:3104), `alacritty` (:3153), `herdr` (:3219) [VERIFIED: grep of `category = "terminal"|"editor"` with preceding id lines in registry.toml; the grep matched 8 blocks].

## skill-judge procedure (SKILL-06)

Source: `~/.claude/skills/skill-judge/SKILL.md` (78 lines, read this session).
1. **Before verdict, first, on the unedited skill.** `.claude/skills/tool-onboarding/SKILL.md` has not changed since commit `1bb31e00` (`git log -1`), HEAD is `963da166`; record the commit the judge saw. Dispatch a fresh read-only subagent (no prior context, never edits, host untouched: AGENTS.md "Never mutate the host") whose prompt says: invoke `skill-judge` on `.claude/skills/tool-onboarding/` (the directory; no `scripts/`, no `evals/`), print the summary plus the verdict as a fenced `json` block last. skill-judge itself reads `references/rubric.md` and the spec on every run and copies `rubric_version` and `spec_sha` from it (SKILL.md line 14, line 56), so both verdict files carry the same values unless the rubric changes between runs (in which case the equality check in the test fails loudly, which is the intent: scores under different rubrics are not comparable).
2. **Store as 24.3 did** [VERIFIED: 24.3-SKILLJUDGE-FINAL.md lines 1-30]: title `# Skill-judge ... verdict - tool-onboarding`; bullets `- Date:`, `- Judge:` (fresh subagent, model, rubric v4, read-only, the path and commit), then `## Summary (as printed)` with the printed table and top findings, then `## Verdict (verbatim)` with the one-line JSON in a ```json fence. The JSON must be one line (the parser tries `json.loads` per stripped line and needs exactly one dict containing `"scores"`, `tests/test_catalog_audit_skill.py:277-289`), so do not paste any other JSON object with a `scores` key into the file.
3. **Never re-run the before.** Commit it before the rewrite begins (so the commit sha in the file is the pre-rewrite commit).
4. **After verdict:** same procedure on the rewritten skill, fresh subagent that does not read the before file. If `after < before`, fix, re-judge as `27-SKILLJUDGE-ROUND-n.md` and rewrite `27-SKILLJUDGE-after.md` from the final round (D-08); the before stays.
5. Expect D7 (tests and evals) to stay at its prior low; the rewrite's measurable wins are D1 (knowledge delta: remove text the model already knows), D4/D5 (description and progressive disclosure: the table could live in a `references/` file but D-01 locks it in SKILL.md, so progressive-disclosure risk is real; keep the table compact), and D3/D6 (anti-patterns, freedom). Keep SKILL.md length close to the current 268 lines; do not let the four rules, table and three new subsections grow it past what D5 tolerates. [ASSUMED: D5 penalizes a long SKILL.md; confirm in the judge's first verdict findings]

## Table content constraints for the parser

- Pipe table, first cell backticked id, then columns: config file, (a) shell, (b) word navigation, (c) clear, (d) same directory, reload. Rule cells start with a closed word (D-02), checked by `re.match(r"(vendor|written|planned \(phase \d+\)|n/a|unverified)\b", cell)`. A cell with a `|` inside breaks the parser: never put a literal pipe in a cell (the rule (b) reason mentions `|` as a Spanish-layout key: keep that sentence outside the table, or escape and avoid it in cells).
- The config-file cell contains backticked paths such as `~/.config/kitty/kitty.conf`; `tests/test_catalog_audit_skill.py:20` has `_REPO_PATH_RE` for `.claude|installer|scripts|tests/...` repo paths only: it is applied to the audit skill, not to this one, so `~` paths are not existence-checked.
- Header and separator rows are excluded by shape; a "legend" line for the status words must not start with `|`.
- The first cell of the Konsole sentence (D-13) is prose under the table, not a row; Konsole must not appear as a table row (it would be "unknown id", which `table_drift` correctly fails).

## Runtime State Inventory

Not a rename or migration phase. Omitted. (One related fact: the `catalog-audit` skill quotes step 7's heading; that is a text coupling handled in the same commit, not runtime state.)

## State of the Art

| Old | Current | Impact |
|-----|---------|--------|
| step 7 "ask the user, do not assume" for terminals | terminal and IDE defaults are rules; extras stay questions | the old bullets and the `Common Mistakes` bullet at SKILL.md:256-257 are replaced, not extended |
| WezTerm "needs nothing" for clear | stock `SUPER k` is `ClearScrollback(ScrollbackOnly)` per CONTEXT D-14 | row (c) for wezterm is not `vendor`; coupling to phase 29 |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A minimal `category = "terminal"` block with `id`, `tier`, `verified` and a brew method loads through `load_tools` | Pattern 4 | The `tmp_path` fixture needs one more key; found on the first run |
| A2 | `Path.glob` with `**` matches the phase dir both under `.planning/phases/` and `.planning/milestones/<v>-phases/` | Pitfall 1 | Ledger glob resolves to no file; fall back to two literals only if one of them can be classified `None` |
| A3 | The judge's D5 penalizes a long SKILL.md | skill-judge procedure | Different trade-off between table placement and score; no test impact |
| A4 | The WezTerm row facts (D-14, live-verified on this host per CONTEXT) are correct | table content | `unverified` cells are allowed by D-02; not re-verified here |

## Open Questions

1. **`TEST_READ` pattern breadth.**
   - Known: `fnmatchcase` `*` crosses `/`; `.planning/*27-SKILLJUDGE-*` matches both locations.
   - Unclear: whether the owner prefers phase-specific patterns over a number-prefixed wildcard.
   - Recommendation: use the wildcard; it errs toward a full run, which the classifier's header says is the safe direction.
2. **Verdict file count with round files.** D-06 says the glob finds exactly 2 and D-08 names round files outside the counted names. Recommendation: count `27-SKILLJUDGE-*.md` excluding names containing `ROUND` and assert 2.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python / uv / pytest | tests | yes | Python 3.15.2 locally (`python3 --version`); project floor 3.11 | - |
| user-level `skill-judge` skill | SKILL-06 | yes | rubric v4 (per CONTEXT D-06; SKILL.md present at `~/.claude/skills/skill-judge/`) | - |
| `gh` / CI | confirming macOS job | not needed to plan | - | `ci.yml` read directly |

No host mutation is needed anywhere in this phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest via `uv run` (xdist `-n auto`, 40% thread cap, `tests/conftest.py`); strict pyright, ruff, bandit, vulture (paths `installer`, `devtools` only, so tests are not vulture-checked) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_tool_onboarding_skill.py tests/test_catalog_audit_skill.py tests/test_docs.py tests/test_docs_only.py tests/test_hook_wiring.py -q` |
| Full suite command | `make validate && make test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SKILL-01 | four rules present with OS scope, Spanish reason, no ask-sentence for any of the four, no recommending `Option-as-Alt` sentence | unit (text) | `uv run pytest tests/test_tool_onboarding_skill.py -k rules -q` | Wave 0 |
| SKILL-02 | table ids == registry terminal+editor ids; fixtures: missing, extra, duplicate, case variant, shuffled, header-only, non-ASCII; `tmp_path` registry; status-word check | unit | `uv run pytest tests/test_tool_onboarding_skill.py -k table -q` | Wave 0 |
| SKILL-03 | `partial: kept yours` and displaced-default example (`scroll_line_up`) present | unit (text) | `... -k conflicts -q` | Wave 0 |
| SKILL-04 | `~/Applications`, `~/.local/bin`, says-why clause in step 4; `# Verified` template names bundle location, CLI link, reason | unit (text) | `... -k macos_apps -q` | Wave 0 |
| SKILL-05 | golden-file, CI-job and deferred-UAT clauses; `validate-and-test` and `macos-latest` also present in `.github/workflows/ci.yml` | unit | `... -k macos_testing -q` | Wave 0 |
| SKILL-06 | two verdicts, exact names, count 2, parse, same skill/rubric/spec_sha, after >= before; boundary fixtures equal and one lower; unparseable percent raises | unit | `... -k verdict -q` | Wave 0 (files created by the judge runs) |
| R6 | step 7 pins still hold; audit-skill heading quote resolves | existing | `uv run pytest tests/test_docs.py tests/test_catalog_audit_skill.py -q` | yes |
| docs-only | new markdown literals classified; ledger glob resolves and is test-read | existing | `uv run pytest tests/test_docs_only.py -q` | yes (edited) |

### Sampling Rate
- Per task commit: the quick run command above.
- Per wave merge: `make validate && make test`.
- Phase gate: full suite green; both verdict files committed; CI `validate-and-test` green on both OSes.

### Wave 0 Gaps
- [ ] `tests/skill_verdicts.py`: moved helpers (existing `test_catalog_audit_skill.py` must stay green with no assertion edits).
- [ ] `tests/test_tool_onboarding_skill.py`: table, rules, verdict tests with fixtures.
- [ ] `devtools/docs_only.py` `TEST_READ` entry and `tests/test_docs_only.py` `LEDGER` rows (run `tests/test_docs_only.py` to get the exact new/stale pair list).
- [ ] `27-SKILLJUDGE-before.md` produced before the rewrite begins.
- [ ] One-line edit in `.claude/skills/catalog-audit/SKILL.md:80` in the same commit as the heading rename.

## Security Domain

ASVS applicability: V5 input validation applies only in the sense that the table parser rejects malformed ids (fullmatch on the id pattern, ASCII lookalike refused). No authentication, session, access-control or cryptography surface. Threats: a skill text that tells an author to run `sudo` or hook-bypass flags (AGENTS.md "Zero sudo"; `_BYPASS` test forbids `--no-verify` and `SKIP=`); the judge subagent must run read-only and never touch `~/.claude` or `~/.pi`. Skill rules and the macOS rule must keep naming only user-space locations (`~/Applications`, `~/.local/bin`).

## Project Constraints (from AGENTS.md)

English only; never bypass a gate (no `--no-verify`, no skipped hooks); coherent commits; validate before commit (`make validate && make test`); never mutate the host (no `make run/fix/doctor/uninstall`, no real rc edits; live checks in a scratch HOME or disposable container); agents never run `make dev-setup`; zero sudo; one gate, one target. Tests: xdist-safe, `tmp_path` for files, no `skip`/`xfail` to dodge failures, coverage floor `fail_under = 90` not lowered [VERIFIED: pyproject.toml coverage section, AGENTS.md read in the task context]. Strict pyright applies to `tests/`.

## Sources

### Primary (read this session)
- `27-CONTEXT.md`, `27-SPEC.md`, `.claude/skills/tool-onboarding/SKILL.md`, `tests/test_catalog_audit_skill.py`, `tests/test_docs.py:291-420`, `devtools/docs_only.py`, `tests/test_docs_only.py:20-60,190-345`, `tests/test_hook_wiring.py:17,102-109,202-209`, `tests/test_postinstall.py:598-610`, `.github/workflows/ci.yml:10-50`, `installer/model.py:96,105,584`, `installer/enums.py:40-56`, `installer/executors.py:697-705`, `installer/locations.py:89-91`, `installer/apps.py`, `installer/terminal_shell.py:596-599,766-769`, `installer/version_status.py:1596-1599`, `installer/agent_settings.py:738-749`, `pyproject.toml`, `~/.claude/skills/skill-judge/SKILL.md`, `24.3-SKILLJUDGE-FINAL.md`.

### Secondary / Tertiary
None; no web research was needed (no external library).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, all in-repo.
- Architecture and pitfalls: HIGH for the ledger, pins and parser; MEDIUM for the `**` ledger glob (A2, prove in Wave 0).
- Judge procedure: HIGH for mechanics, LOW for the resulting scores.

**Research date:** 2026-11-19
**Valid until:** 2026-12-19 (stable); recheck line numbers if `tests/test_docs.py` or `installer/registry.toml` change.
