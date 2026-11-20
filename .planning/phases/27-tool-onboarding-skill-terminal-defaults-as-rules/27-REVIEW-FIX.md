---
phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
fixed_at: 2026-11-20T06:05:00Z
review_path: .planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 27: Code Review Fix Report

**Fixed at:** 2026-11-20
**Source review:** `.planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-REVIEW.md`
**Iteration:** 1
**Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 8 minutes (02:56 to 03:04), stderr empty, four commits.

**Scope decision (orchestrator):** the 8 warnings (WR-01 to WR-08) plus IN-01 and IN-08 were fixed, because each is a factual or consistency error in text this phase wrote. The other info findings were not fixed here; see "Not fixed" below.

## Fixed Issues

| Finding | Status | Commit | What changed |
|---|---|---|---|
| WR-01 | fixed | `c955da0a` | catalog-audit step 7 item 3 runs the targeted tests per change and `make validate` and `make test` once after the last approved change; the eval assertion and `expected_output` match |
| WR-02 | fixed | `6b4de439` | git-workflow states that the push gate and CI test only the pushed tip |
| WR-03 | fixed | `6b4de439` | AGENTS.md points to `rg -l '<file name>' tests/` instead of `devtools/docs_only.py` |
| WR-04 | fixed | `24a73427` | `GATE_READ_PATHSPECS` gains `.planning/**/*-SKILLJUDGE-*` (count 29 to 30, `.planning/` added to the literal roots), with a test that an untracked verdict is refused and an untracked note is not |
| WR-05 | fixed | `54cf2674` | the CI check compares the Test step's `if` exactly; a third mutation case, `macos-excluded`, is covered |
| WR-06 | fixed | `54cf2674` | the skill names both mechanisms: the lifecycle-wide zsh terminal sync for rule (a), `post_install` actions for the others |
| WR-07 | fixed | `54cf2674` | step 9 says a macOS-only method cannot run in a Linux container: record vendor-doc facts in `# Verified` and add a UAT line deferred to the owner's Mac |
| WR-08 | fixed | `54cf2674` | the wezterm and alacritty config-path cells match `_wezterm_config_path` and `alacritty_config_path` |
| IN-01 | fixed | `54cf2674` | the skill and its test use a single backslash |
| IN-08 | fixed | `6b4de439` | git-workflow's docs-only definition names the verdict files as exceptions |

## Not fixed (out of this pass)

- **IN-02** (detector phrasings): accepted. The checks are heuristics by design ("test plus judgment", plan 27-02 ledger); widening them would flag legitimate text.
- **IN-03** (`_phase_dir` globs directories): rejected. It would reopen D-07, decided in the discuss step; the case needs an unrelated `27-*` entry.
- **IN-04** (shared parser does not check `max`): deferred to a backlog item. A stricter shared parser changes the catalog-audit tests' behaviour; `verdict_regressions` already compares the maxima for this skill.
- **IN-05, IN-06** (duplicated fixture builder, repeated item loop): deferred to the same backlog item; code tidiness only.
- **IN-07** (`make validate` after a plan repeats the last commit hook): rejected. The owner asked for `make validate` after a plan (2026-11-20).

## Verification

Reported by the executor: the targeted run (`test_tool_onboarding_skill`, `test_catalog_audit_skill`, `test_docs`, `test_docs_only`, `test_push_gate`, `test_hook_wiring`) passed; `make validate` passed all six gates; `make test` passed with 7,872 passed, 6 skipped and 96.21% coverage.

Checked by the orchestrator:
- I read all four commits' diffs against the intended wording; each matches.
- The same six test files pass on the final tree, and my acceptance scripts for plans 27-01 to 27-04 show no regression (the one known plan-check deviation, four import lines instead of one, is unchanged).
- The pinned skill phrases and the two Policies sentences are intact, and no line naming Policies is non-ASCII.
- The new push-gate test fakes git, so I tested the real pathspec in a scratch repository: with `git --glob-pathspecs`, `.planning/**/*-SKILLJUDGE-*` matches verdict files under both `phases/` and `milestones/` and does not match a note, a plan or a goals file.
- The pi run left the untracked goals file byte-identical.
- The skill text changed, so the after verdict was re-judged on the final blob (73.6%); see `27-SKILLJUDGE-after.md`.
