---
phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
reviewed: 2026-11-20T05:52:41Z
depth: deep
files_reviewed: 10
files_reviewed_list:
  - .claude/git-workflow.md
  - .claude/skills/catalog-audit/SKILL.md
  - .claude/skills/tool-onboarding/SKILL.md
  - .claude/testing.md
  - AGENTS.md
  - devtools/docs_only.py
  - tests/skill_verdicts.py
  - tests/test_catalog_audit_skill.py
  - tests/test_docs_only.py
  - tests/test_tool_onboarding_skill.py
findings:
  critical: 0
  warning: 8
  info: 8
  total: 16
  necessity: 1
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-11-20T05:52:41Z
**Depth:** deep
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Scope: the tool-onboarding skill rewrite and its new test module, the shared skill-judge verdict parser, the docs-only classifier change and its ledger, and the rewritten test-running rules in AGENTS.md, `.claude/testing.md` and `.claude/git-workflow.md`. Cross-checked against `.pre-commit-config.yaml`, `devtools/push_gate.py`, `.github/workflows/ci.yml`, `installer/compose.py`, `installer/terminal_shell.py`, `installer/model.py`, `installer/registry.toml` and `scripts/detect-container-runtime.sh`. No test or make target was run.

The Python is sound. The verdict parser moved over unchanged, the classifier change errs toward a full CI run, and the ledger matches the files the tests read. Every fact the skill states about code (the cask `--appdir`, `ditto -x -k`, the `cli_name` reader, the cask params, kitty's `/Applications` script, herdr's reload, vscode's `defaultProfile`) checks out against the source.

Most defects are in the rules. Phase 27 rewrote the test-running rules, and that rewrite left three problems:
- the catalog-audit skill still runs `make validate` then `make test` per approved change, and a test pins that wording;
- git-workflow says the push gate tests every commit's tree, but it tests only the tip;
- AGENTS.md points agents to a file that does not list what the rule says it lists.

The skill also has three gaps:
- it says every terminal default is a `post_install` action, but rule (a) is a lifecycle-wide synchronizer;
- it requires a container for every real install, and macOS installs cannot run in one;
- two config paths in the table are wrong.

External lane (opencode referee-one): I re-read the code behind each of its five claims. Claims 1, 2, 4 and 5 are confirmed, and appear as WR-04, WR-07, WR-05 and WR-08. I downgraded claims 1 and 2 from "must fix" to Warning: CI still runs on the committed tree, and nothing is lost. I rejected claim 3, that the targeted-test rule misses indirect callers. Targeted runs are a working-time subset by design: AGENTS.md:53-54 requires `make test` after every plan, and the push gate runs the full suite. The real defect in that sentence is WR-03.

## Warnings

### WR-01: catalog-audit still runs `make validate` then `make test` per approved change, against the new AGENTS rule

**File:** `.claude/skills/catalog-audit/SKILL.md:158-162` (pinned by `tests/test_catalog_audit_skill.py:192-194` and `.claude/skills/catalog-audit/evals/evals.json:82`)
**Issue:** AGENTS.md:46-49 now says "never run `make validate` or a single static gate by hand per commit, and never chain `make validate && make test` at a commit". Catalog-audit step 7 still says "For each approved change, in this order: ... 3. `make validate`, then `make test`". Each approved change becomes one commit (`disposition = "commit:0123abc"`). Phase 27 edited this skill (line 80) but left step 7 alone. The `make validate` and `make test` needles in `test_skill_precision_and_approval_rules` lock the stale wording in. Concrete case: an agent applying five approved drift fixes runs the static gates and the full suite five times, about 91 s each (`.claude/dev-environment.md:114`). That is exactly what the new rule forbids.
**Fix:** Reword step 7.3 to match AGENTS.md, and update the needle and the eval assertion to match:
```markdown
3. the targeted tests for the edited entry (`uv run pytest <those files> --no-cov -q`);
   after the last approved change, `make validate` and `make test` once each;
```

### WR-02: git-workflow says the push gate tests every commit's tree; it tests only the tip

**File:** `.claude/git-workflow.md:11-12`
**Issue:** "One commit = one self-contained logical change that the commit hook accepts and whose tree the push gate's `make test` passes." The push gate refuses unless the pushed sha is HEAD (`devtools/push_gate.py:225-236`). It then runs `pre-commit run --hook-stage pre-push --from-ref HEAD --to-ref HEAD` (lines 22-31), so it tests one tree: the tip. AGENTS.md:46-55 now forbids running tests per commit. Together, these mean nothing tests the tree of a commit in the middle of a multi-commit push. The rule names a mechanism that cannot check what it promises. Concrete case: a plan pushes commits A, B, C. If B leaves a test red and C fixes it, the push gate and CI both pass, and B is a knowingly broken tree that no gate saw.
**Fix:** State what really happens, for example: "...that the commit hook accepts. The push gate and CI test only the pushed tip, so keep each commit's tests green with the targeted run (AGENTS.md) before you commit it." Alternatively, accept tip-only testing and drop the per-commit claim.

### WR-03: AGENTS.md says `devtools/docs_only.py` lists the tests that read a non-Python file; it does not

**File:** `AGENTS.md:50-52`
**Issue:** "...and the tests that read an edited non-Python file (`devtools/docs_only.py` lists those)". `TEST_READ` (`devtools/docs_only.py:20-30`) is a list of path globs. It names no test, and it only matters for Markdown and `.planning/` paths (`is_docs_path`, line 34). Non-Markdown files that tests read appear nowhere: `installer/registry.toml`, `Makefile`, `.pre-commit-config.yaml`, the shell scripts. Concrete case: an agent edits `installer/registry.toml`. There is no module name, nothing imports a TOML file, and docs_only does not mention it, so the rule selects no test. The table-drift test in `tests/test_tool_onboarding_skill.py:595-598`, the registry tests and the catalog-audit tests then fail only at the push gate.
**Fix:** Point to a search, not to the classifier: "the tests that read an edited non-Python file (find them with `rg -l '<file name>' tests/`)".

### WR-04: The push gate ignores untracked `.planning/` files, but two tests now read `.planning/` files (external: opencode-referee-one)

**File:** `devtools/push_gate.py:129-144`, `tests/test_tool_onboarding_skill.py:545-549`, `tests/test_tool_onboarding_skill.py:584-592`
**Issue:** `_untracked_message` drops every untracked name under `.planning/` (line 134), and `GATE_READ_PATHSPECS` (lines 38-69) has no `.planning` entry. Phase 27 added a second `.planning/` reader (`_phase_dir` and `test_verdict_files_before_and_after`) and widened `TEST_READ` for it, but left the push gate's list alone. Concrete case: `27-SKILLJUDGE-after.md` exists in the working tree but was never committed. The local push gate's `make test` reads it and passes. CI checks out the commit without it and fails. That breaks the gate's own promise ("refuse a push whose tested tree is not the pushed commit", line 1). The 24.3 reader had the same hole; this phase widened it.
**Fix:** Add a pathspec that starts with the literal directory, so git never walks `.venv/`. Then update the pinned tuple and the count in `tests/test_push_gate.py:400-431`:
```python
    ".claude/skills/**",
    ".planning/**/*-SKILLJUDGE-*",
)
```

### WR-05: The CI check accepts a Test step that skips macOS (external: opencode-referee-one)

**File:** `tests/test_tool_onboarding_skill.py:69-73`
**Issue:** The `if:` guard checks two substrings, `"steps.scope.outputs.full" in test_if` and `"!= 'false'" in test_if`. The value `steps.scope.outputs.full != 'false' && runner.os != 'macOS'` passes both, yet it turns off `make test` on macOS. The skill claims macOS CI coverage at `.claude/skills/tool-onboarding/SKILL.md:230`, and this check exists to keep that claim true. The pressure to make this edit is real: the ci.yml comment says the macOS runner "timed out at 96% three times". The mutation test (lines 421-437) covers only `== 'false'`.
**Fix:** Compare the whole expression (shorter and strict), and add the macOS-exclusion case to the mutation test:
```python
    if test.get("if") != "steps.scope.outputs.full != 'false'":
        problems.append("Test step if is not exactly steps.scope.outputs.full != 'false'")
```

### WR-06: The skill calls every terminal default a `post_install` action, but rule (a) is not one

**File:** `.claude/skills/tool-onboarding/SKILL.md:190`, `.claude/skills/tool-onboarding/SKILL.md:194`
**Issue:** The text says "each is the entry's install tuning (a `post_install` action)". Rule (a), the zsh shell, comes from `sync_terminal_shells`, called by `compose._sync_terminals` (`installer/compose.py:347-374`) on every lifecycle route. It is not a per-entry action. kitty, wezterm and herdr have no `post_install` in `installer/registry.toml`; only alacritty (line 3164) and vscode (`apply_agent_tuning`) have one. Yet the table marks (a) `written` for all of them. The skill's own rule is "land on a mechanism that exists in code today ... Name the file". Concrete case: an author onboarding a new terminal follows line 194 and adds a new `post_install` action for the shell. The real mechanism is a new branch in `installer/terminal_shell.py:sync_terminal_shells`, so the shell gets written twice, by two owners.
**Fix:** Name both mechanisms: "each is install tuning, never a Policies row: rule (a) is the lifecycle-wide zsh terminal sync (`installer/terminal_shell.py`, run by `installer/compose.py:_sync_terminals`), and the others are the entry's `post_install` actions."

### WR-07: "Sandbox every real install in a disposable container" cannot cover macOS methods (external: opencode-referee-one)

**File:** `.claude/skills/tool-onboarding/SKILL.md:123`, `.claude/skills/tool-onboarding/SKILL.md:286`
**Issue:** Phase 27 made the rule absolute: "sandbox every real install in a disposable container ... never run it on the host". It also added a macOS-apps subsection (lines 102-110) that asks for the facts of a cask, an `app` kind and a macOS vendor script. `scripts/detect-container-runtime.sh` picks podman or docker, or colima plus docker on macOS. All of these run Linux containers, so none can run `brew install --cask`, `ditto` or kitty's macOS `installer.sh` (`installer/registry.toml:3041-3047`). For a macOS-only method, the author must either break the host rule or claim a check the container could not run. Line 231 already has the right answer for terminal behavior (a UAT line deferred to the owner's Mac), but step 4b and step 9 do not apply it to installs.
**Fix:** Extend the sentence on line 286: "A macOS-only method cannot run in a container: record its install and removal facts from vendor docs in `# Verified`, and add a UAT line deferred to the owner's Mac; no agent marks it passed."

### WR-08: Two config paths in the closed table disagree with the installer (external: opencode-referee-one)

**File:** `.claude/skills/tool-onboarding/SKILL.md:212-213`
**Issue:** The table says it holds real entries, not examples (line 21). The kitty row uses "`X`, else `Y`" to mean "Y when `XDG_CONFIG_HOME` is unset". Read the same way, the wezterm row says that with `XDG_CONFIG_HOME` unset the file is `~/.wezterm.lua`. The code (`installer/terminal_shell.py:165-171`) uses `~/.config/wezterm/wezterm.lua` unless only `~/.wezterm.lua` exists. The alacritty row names one path. The installer searches four, in order (`installer/terminal_shell.py:486-497`): `$XDG_CONFIG_HOME/alacritty/alacritty.toml`, `$XDG_CONFIG_HOME/alacritty.toml`, `~/.config/alacritty/alacritty.toml`, `~/.alacritty.toml`. Phase 29 writes key bindings into these files, so an author working from this table can edit a file the terminal does not read.
**Fix:** wezterm: "`$XDG_CONFIG_HOME/wezterm/wezterm.lua` (else `~/.config/...`); `~/.wezterm.lua` only when it alone exists (`_wezterm_config_path`)". alacritty: "first existing of alacritty(5)'s four user paths, else the XDG one (`alacritty_config_path`)".

## Info

### IN-01: The skill shows two backslashes where the layout breaks one

**File:** `.claude/skills/tool-onboarding/SKILL.md:197`, `.claude/skills/tool-onboarding/SKILL.md:317`, `tests/test_tool_onboarding_skill.py:221`
**Issue:** Markdown code spans do not process escapes, so `` `\\` `` renders as `\\`. The SPEC (27-SPEC.md:134) names a single `\`. The test needle `"`\\\\`"` pins the two-character form.
**Fix:** Write `` `\` `` in both skill lines, and make the needle `"`\\`"`.

### IN-02: The "asks about a default" and "Option-as-Alt" detectors miss common phrasings

**File:** `tests/test_tool_onboarding_skill.py:29-33`, `tests/test_tool_onboarding_skill.py:132-140`
**Issue:** `\bask(?:s|ed)?\b` never matches "asking" (no word boundary between `k` and `i`). So "Asking the developer whether to set word navigation is step one." passes `test_rules_no_sentence_asks_about_a_default`. `option_as_alt_unnegated` accepts any unit that contains "not" or "never" anywhere. So "Turn on macos_option_as_alt, which does not break `@`" passes.
**Fix:** Allow `ask(?:s|ed|ing)?` and keep "without asking" as an explicit allowed phrase. For Option-as-Alt, require the negation to come before the switch name in the same unit.

### IN-03: `_phase_dir` globs directories, not the verdict files

**File:** `tests/test_tool_onboarding_skill.py:545-549`
**Issue:** `phases/27-*` matches any entry named `27-...`, including a file. A docs-only commit that adds `.planning/phases/27-notes/x.md` gets the CI fast pass (it does not match `TEST_READ`). It then turns `assert len(matches) == 1` red on the next code push, far from its cause.
**Fix:** Glob for the file itself, which `TEST_READ` already covers: `sorted(planning.glob("**/27-SKILLJUDGE-before.md"))`, then use `.parent`.

### IN-04: The shared parser does not check `max` against the rubric

**File:** `tests/skill_verdicts.py:49-63`, `tests/test_tool_onboarding_skill.py:526-531`
**Issue:** `RUBRIC_MAX` sits in the shared module, but only tool-onboarding's `verdict_regressions` compares `max` to it. A catalog-audit FINAL verdict with `"max": {"D1": 100, ...}` and inflated scores passes `final=True`. No committed verdict does this today.
**Fix:** In `parse_verdict`, after the dimension check: `if list(maxima.values()) != [maxima[d] for d in DIMENSIONS] or tuple(maxima[d] for d in DIMENSIONS) != RUBRIC_MAX: raise ValueError("max differs from the rubric")`. Then drop the duplicate check in `verdict_regressions`.

### IN-05: The verdict fixture builder is still duplicated, and the underscore aliases add four import statements

**File:** `tests/test_tool_onboarding_skill.py:503-521`, `tests/test_catalog_audit_skill.py:13-24`, `tests/test_catalog_audit_skill.py:266-284`
**Issue:** `_verdict_doc` and `_verdict` are the same 18 lines, differing only in the skill name. The refactor shared the parser but not the builder. The `X as _X` aliases make ruff's isort emit four separate `from tests.skill_verdicts import` statements.
**Fix:** Move a `verdict(skill, points=..., **overrides)` builder into `tests/skill_verdicts.py`, and import the plain names. That is about -25 lines.

### IN-06: `rule_items` repeats `_items`

**File:** `tests/test_tool_onboarding_skill.py:111-125`
**Issue:** `rule_items` copies the item-gathering loop of `_items` (lines 96-108) line for line.
**Fix:** `return {m.group(1): item for item in _items(section) if (m := re.match(r"- \(([a-d])\) ", item))}`. That is about -12 lines.

### IN-07: Already-defended-elsewhere: the `make validate` after a plan repeats the last commit hook's run

**File:** `AGENTS.md:53`, `.claude/testing.md:46-47`
**Category:** necessity
**Issue:** The commit stage runs the same six hooks `make validate` runs, each `always_run: true, pass_filenames: false` over the whole tree (`.pre-commit-config.yaml:8-49`). On a clean worktree after a plan's last commit, `make validate` repeats that run on the identical tree. The push gate runs the six gates again anyway. It only adds value on a dirty tree or a checkout without hooks, and AGENTS.md already covers the second case.
**Fix:** Keep only `make test` after a plan, or say "`make validate` only when the tree has uncommitted edits or no hooks".

### IN-08: git-workflow's docs-only definition misses the `.planning/` files tests read

**File:** `.claude/git-workflow.md:48-50`
**Issue:** "A docs-only change (only paths under `.planning/`, or Markdown no test reads)". The SKILLJUDGE verdicts under `.planning/` are test-read and run the full CI (`devtools/docs_only.py:28-29`).
**Fix:** "(only `.planning/` files and Markdown that no test reads; `devtools/docs_only.py` holds the exceptions)".

---

_Reviewed: 2026-11-20T05:52:41Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
