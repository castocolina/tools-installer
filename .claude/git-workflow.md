# Git Workflow Guidelines

## Overview

History should read as a series of deliberate, valid steps — not a transcript of the
review conversation. These rules apply to every commit and to the review cycle.

## Rules

### Commits are coherent
- One commit = one self-contained logical change that builds and passes
  `make validate && make test`. Never commit a knowingly broken tree.
- Write a clear message: a concise imperative subject (Conventional Commits style —
  `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`), and a body explaining
  *why* when it isn't obvious.
- Don't bundle unrelated changes; split them into separate commits.
- Co-authorship trailer: end the message with `Co-Authored-By: Claude <noreply@anthropic.com>`.
  Do **not** pin a model name or version — it drifts and adds no value.

### The review cycle — do NOT stack fix commits
- When the user reviews and requests changes, **amend or fixup** the relevant commit so
  the final history is clean. Do **not** add a trail of `fix review`, `address comment`,
  `oops typo` commits.
  - Single original commit → `git commit --amend`.
  - Multi-commit branch → `git commit --fixup=<sha>` then `git rebase -i --autosquash`,
    so each fix folds into the commit it belongs to.
- Only after amending/squashing do you re-run `make validate && make test` and (if the
  branch was pushed) force-push with lease: `git push --force-with-lease`. That flag is for
  branches only; `main` is never force-pushed.

### When to commit
- Commit only when the user asks, or when a logical unit is complete and validated.
- Never commit secrets, generated artifacts, or `.venv`.
- If on the default branch and starting new work, create a branch first.

### The path to main

1. Work on a branch, never on `main`.
2. Push the branch with `git push origin <branch>`. The push gate runs the six static gates
   and the full suite locally; CI then runs both required checks on the branch.
3. When both checks are green, land the change with `git push origin <branch>:main`: a
   fast-forward of the exact commit CI tested. GitHub refuses anything else, an admin's
   push included.
4. If `main` moved meanwhile, update the branch (rebase or merge `main`), push it again and
   wait for green again — strict mode accepts only a commit that is up to date with `main`
   and whose checks passed.

A docs-only change (only paths under `.planning/`, or Markdown no test reads) gets both
required check names quickly through CI's fast pass; `devtools/docs_only.py` holds the list
of files tests read. CI does not run on pull requests, so an outside contributor's branch
gets CI once the maintainer pushes that branch to this repository.

### Escape hatch: CI is down

If CI cannot produce its checks, a maintainer may land an already-tested commit by turning
`enforce_admins` off for the push and straight back on. Run this block from the branch you
want to land:

```sh
branch=$(git branch --show-current)
gh api -X DELETE repos/castocolina/tools-installer/branches/main/protection/enforce_admins || echo "off command failed; the push will be rejected and protection is re-checked below"
git push origin "$branch:main" || echo "push failed; protection goes back on anyway"
gh api -X POST repos/castocolina/tools-installer/branches/main/protection/enforce_admins || echo "on command failed; read the state below, then re-run it"
gh api repos/castocolina/tools-installer/branches/main/protection --jq '{enforce_admins: .enforce_admins.enabled, strict: .required_status_checks.strict, checks: [.required_status_checks.checks[].context]}'
```

Expect `enforce_admins: true`, `strict: true` and both `validate & test on …` contexts. The
on command and the read-back always run after the push, even when the off command, the push
or the on command failed; protection is never left off by this block.

If the block was interrupted, or the read-back fails or does not show `enforce_admins: true`,
protection may still be off: re-run the on command and the read-back until it does. If
protection cannot be restored, stop every push to `main` and tell the owner at once. The
order of the lines alone does not guarantee this — the guards and the escalation do.

## Examples

### Avoid (review noise)
```
a1b2c3 feat: add PATH doctor
d4e5f6 fix review comment
7890ab fix lint
cdef01 typo
```

### Good (after autosquash)
```
a1b2c3 feat: add PATH doctor that writes idempotent ~/.myshellrc
```
