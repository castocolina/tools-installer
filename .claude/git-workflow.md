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

### The review cycle — do NOT stack fix commits
- When the user reviews and requests changes, **amend or fixup** the relevant commit so
  the final history is clean. Do **not** add a trail of `fix review`, `address comment`,
  `oops typo` commits.
  - Single original commit → `git commit --amend`.
  - Multi-commit branch → `git commit --fixup=<sha>` then `git rebase -i --autosquash`,
    so each fix folds into the commit it belongs to.
- Only after amending/squashing do you re-run `make validate && make test` and (if the
  branch was pushed) force-push with lease: `git push --force-with-lease`.

### When to commit
- Commit only when the user asks, or when a logical unit is complete and validated.
- Never commit secrets, generated artifacts, or `.venv`.
- If on the default branch and starting new work, create a branch first.

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
