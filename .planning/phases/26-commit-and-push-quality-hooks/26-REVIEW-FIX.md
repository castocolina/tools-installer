---
phase: 26-commit-and-push-quality-hooks
fixed_at: 2026-11-16T19:30:00Z
review_path: .planning/phases/26-commit-and-push-quality-hooks/26-REVIEW.md
iteration: 2
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 26: Code Review Fix Report

**Fixed at:** 2026-11-16
**Source review:** .planning/phases/26-commit-and-push-quality-hooks/26-REVIEW.md
**Iteration:** 2

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Intent-to-add and skip-worktree/assume-unchanged entries bypass every refusal

**Files modified:** `devtools/push_gate.py`, `tests/test_push_gate.py`, `.claude/dev-environment.md`
**Commit:** 5010fc36 (the ledger follow-up is folded in)
**Applied fix:** New refusal for intent-to-add entries (`git diff --name-only --diff-filter=A -z`), and a refusal for `git ls-files -v -z` entries tagged `S` or lowercase that exist on disk (sparse-checkout absent files pass). Both sit before the untracked check. Fix text names `git add` / `git rm --cached` and `git update-index --no-skip-worktree` / `--no-assume-unchanged`. Fake-runner tests added, including the sparse-checkout pass and ordering. Status: fixed: requires human verification (logic). No e2e case added: the e2e script registers cases beyond a few lines.

### WR-01: Ignored files under `.claude/` are not in `GATE_READ_PATHSPECS`

**Files modified:** `devtools/push_gate.py`, `tests/test_push_gate.py`, `.claude/dev-environment.md`
**Commit:** eaa2af05 (the ledger follow-up is folded in)
**Applied fix:** Added `.claude/*.md` and `.claude/skills/**`; updated the pinned-tuple test (count 29, `.claude/` literal root) and the doc.

### WR-02: Unstaged `pyproject.toml`/`uv.lock` edits are not refused

**Files modified:** `devtools/push_gate.py`, `tests/test_push_gate.py`, `.claude/dev-environment.md`
**Commit:** a038be2b
**Applied fix:** The unstaged-edit refusal now covers `.pre-commit-config.yaml`, `pyproject.toml` and `uv.lock` (new `ENV_FILES`), with adjusted header and fix text. Shim untouched. Tests and doc updated.

### WR-03: Hook installer fails open on git older than 2.31

**Files modified:** `devtools/hooks.py`, `tests/test_hooks_install.py`
**Commit:** 5718fe26
**Applied fix:** `_absolute_path` accepts only a single-line absolute path from both `rev-parse --path-format=absolute` calls; otherwise `_fail("git 2.31 or newer is required ...")` before anything is written. Test covers both queries with two-line output.

### WR-04 (iteration 2): a moved file marked intent-to-add escaped the CR-01 refusal

**Files modified:** `devtools/push_gate.py`, `tests/test_push_gate.py`, `scripts/hooks-e2e.sh`
**Commit:** 91986f98
**Applied fix:** The intent-to-add query adds `--no-renames`, so a deletion no longer pairs with an intent-to-add file as a rename. The new real-git case `renamed_intent_to_add_is_refused` in `make hooks-e2e` failed before the fix and passes after it.

### Follow-up: docs-only ledger (folded)

The ledger change (originally commit 8ee7b0fe) was split and folded into the CR-01 and WR-01 commits, so each ledger entry lands with the test literal that needs it. The tree is byte-identical to the pre-fold tip.

## Verification

Run in the main checkout (no worktree), on the final tree:
- `make validate`: passed
- `make test`: passed (7823 passed, 6 skipped, coverage 96.21%)
- `make hooks-e2e`: passed (33 cases, including renamed_intent_to_add_is_refused)

Re-run by the orchestrator on the tip after the WR-04 fix (91986f98).

---

_Fixed: 2026-11-16_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
