# Phase 26: Commit and push quality hooks — Specification

**Created:** 2026-11-16
**Ambiguity score:** 0.14 (gate: ≤ 0.20)
**Requirements:** 6 locked

## Goal

Every commit runs the `make validate` checks. Every push runs `make validate` and then the full `make test` suite on
a tree that equals the pushed commit. `make install` installs both hooks. GitHub accepts a commit on `main`, from
anyone including admins, only after both CI checks pass on that commit.

## Background

Measured at HEAD `ae9b99b0` on 2026-11-16:

- **Hooks.** `.pre-commit-config.yaml` defines six local commit-stage hooks: ruff check, ruff format --check, pyright,
  bandit, vulture and shellcheck. No hook runs tests and no hook has a `pre-push` stage.
  `default_install_hook_types` is not set.
- **Installation.** `make install` runs only `uv sync`. The repo's `.git/hooks/pre-commit` was installed by hand, and
  `.git/hooks` has no `pre-push`. `pre-commit>=3.8` is a dev dependency; version 4.6.0 is installed.
- **`make validate`** runs the same six commands directly and does not call pre-commit. AGENTS.md:20 and
  `.claude/dev-environment.md:35` say it "runs pre-commit hooks", which is false. The two command lists are kept in
  step by hand; only comments say "same file set".
- **CI.** `.github/workflows/ci.yml` runs `make install`, `make validate` and then `make test` on ubuntu-latest and
  macos-latest. It triggers on pushes to `main` and on pull requests; a push to any other branch runs no CI.
- **Branch protection.** Protection on `main` (applied 2026-11-15, read back 2026-11-16) requires the contexts
  `validate & test on ubuntu-latest` and `validate & test on macos-latest`. `enforce_admins` is false, so the owner's
  direct pushes to `main` bypass it ("Bypassed rule violations"). The GSD merge helpers push straight to `main` this
  way.
- **Timings on this host.** `make test` takes 62.3 s wall (pytest 59.1 s: 7662 passed, 6 skipped, coverage 96.20%
  against `fail_under = 90`) using 40% of the host's threads. `make validate` takes 12.1 s.
- **pre-commit behaviour** (`pre_commit/commands/run.py:344-421`, version 4.6.0). On a run with refs, the pre-push
  stage included, unstaged tracked edits are stashed, so hooks see the index. The exception is a new branch's first
  push, which runs with `all_files` and stashes nothing (`hook_impl.py:157`). Untracked files are never stashed.
  *(amended 2026-11-16, 26 D-01: `all_files` applies only to a root push, when the remote has none of the history.
  A new branch on an existing remote is stashed. pre-commit's pre-push entry also reads only the first pushed ref
  with something to push (`hook_impl.py:119-174`), so the gate reads the refs itself.)*

## Requirements

1. **Commit stage**: A commit runs the six `make validate` checks on the same file set as `make validate`, and runs no
   tests.
   - Current: true only where someone installed the hook by hand. The two command lists can drift without any check
     failing.
   - Target: the commit-stage hooks and the `make validate` commands are pinned to each other by a test: same tools,
     same arguments, same file sets.
   - Acceptance: a test fails when a commit-stage hook or a `make validate` command is added, removed or given
     different arguments or files without the matching change on the other side. No commit-stage hook runs pytest.
   - *Amended 2026-11-16 (26 D-03, D-04):* Each gate is a `make` target (`lint`, `format-check`, `typecheck`, `security`,
     `dead-code`, `shellcheck`, `test`), and each hook entry calls its target, so the command exists once. `make validate`
     runs `pre-commit run --all-files` without listing the gates. The drift test becomes a wiring test. It checks that
     each commit-stage hook calls an existing target, that each gate target except `test` has a commit-stage hook, and
     that `make validate` is exactly `pre-commit run --all-files`.

2. **Push stage**: A push runs `make validate` and then `make test` (the full suite with the 90% coverage gate). Any
   failure aborts the push.
   - Current: no pre-push hook exists.
   - Target: the pre-commit config defines a `pre-push` stage that runs `make validate` and then `make test`, whatever
     files the push touches.
   - Acceptance: a test pins the pre-push hook entries, their order, and that they run regardless of the changed files.
     In a scratch git repo, a push whose suite fails exits non-zero and the remote ref does not move; a green push
     moves it.
   - *Amended 2026-11-16 (26 D-05):* The push stage runs each static gate hook, which also carries the `pre-push`
     stage, and then the `make test` hook, each as its own entry. This is equivalent to `make validate` then
     `make test`, and a failure names the gate that failed.
   - *(amended 2026-11-16, 26 plan-phase D-15, D-19: `make hooks-e2e` proves the scratch-repo push cases with real
     git and pre-commit; CI runs it on ubuntu and macOS. pytest pins the hook entries and the gate logic with fake
     runners. The gate runs `pre-commit run --hook-stage pre-push --fail-fast --from-ref HEAD --to-ref HEAD`.)*

3. **Tested tree equals the pushed commit**: The push gate tests the staged tree with unstaged edits set aside, a new
   branch's first push included. It refuses the push before running any check when the tree differs from HEAD:
   staged changes that are not committed, or untracked `.py` files under `installer/` or `tests/`. It also refuses
   when a pushed commit is not HEAD (`git push origin other-branch`, `--all`, a tag), telling the user to check out
   that branch and push from it. A push that only deletes a remote ref runs no checks and is not refused.
   - Current: no push gate. pre-commit's own stash does not apply to a new branch's first push and never covers
     untracked files.
   - Target: every push either tests a tree equal to HEAD or is refused with a message that names the offending files
     and the fix (commit, stash or remove them).
   - Acceptance: in a scratch git repo, each case behaves as stated: a staged uncommitted change refuses the push; an
     untracked `tests/test_x.py` refuses it; an unstaged edit that breaks a test does not make a clean HEAD fail; the
     same holds on a new branch's first push; a clean tree passes; pushing a branch that is not checked out is
     refused; a branch deletion goes through with no checks. Each refusal lists the offending files, sorted.
   - *(amended 2026-11-16, 26 plan-phase D-18: the gate checks five refusals, first match wins: unmerged paths,
     staged changes, untracked `.py` under `installer/`, `tests/` or `devtools/`, an unstaged `.pre-commit-config.yaml`,
     then a pushed commit that is not HEAD. A tag or refspec whose commit is HEAD passes. D-15: `make hooks-e2e` runs
     the scratch-repo cases above.)*
   - *(amended 2026-11-16, 26 plan-phase D-25 (review H1): refusal 3 covers every untracked, non-ignored file
     outside `.planning/`, at any depth and the repo root included, whatever its extension. A root `conftest.py` or
     `pytest.ini` changes what pytest runs. Untracked `.py` under `installer/` or `tests/` is a subset. The target
     above is the authority for the widening.)*

4. **`make install` installs both hooks**: `make install` installs the pre-commit and pre-push hooks after `uv sync`.
   Running it again changes nothing. Outside a git checkout it skips the hook step with a one-line message and still
   succeeds. When `core.hooksPath` is set, so pre-commit cannot install, `make install` fails with the cause and
   the fix.
   - Current: `make install` runs only `uv sync`, and `default_install_hook_types` is not set.
   - Target: `.pre-commit-config.yaml` sets `default_install_hook_types: [pre-commit, pre-push]`, and `make install`
     installs both hook types.
   - Acceptance: a test pins the config key and the Makefile `install` recipe. In a scratch git repo, `make install`
     leaves `.git/hooks/pre-commit` and `.git/hooks/pre-push`; a second run leaves both files byte-identical. In a
     scratch directory that is not a git checkout, `make install` exits 0 and prints the skip message. In a scratch
     repo with `core.hooksPath` set, `make install` exits non-zero and names `core.hooksPath`.
   - *Amended 2026-11-16 (26 D-07):* The target is renamed `make dev-setup`, with no `make install` alias; CI, README
     and AGENTS.md switch to it. pre-commit installs only the commit hook (`default_install_hook_types: [pre-commit]`).
     `make dev-setup` installs the push gate of 26 D-01 as `pre-push` in the shared hooks directory. Every
     `make install` in this SPEC reads as `make dev-setup`.
   - *(amended 2026-11-16, 26 plan-phase D-15, D-22, D-24: `make hooks-e2e` runs the hook step
     `python -m devtools.hooks install` in scratch repos, and a text test pins the `dev-setup` recipe. Run from a linked
     worktree, the step warns to re-run it from the main checkout. It refuses a foreign `pre-push` file without
     touching it.)*
   - *(amended 2026-11-16, 26 plan-phase D-26 (review M12): the AGENTS.md rule that agents never run
     `make dev-setup` names its one exception, the final owner-assigned checkpoint that lists the real install.)*

5. **`main` is gated behind CI on GitHub**: Branch protection on `main` has `enforce_admins` enabled and requires both
   CI contexts, so GitHub rejects any update to `main`, an admin's included, unless both checks passed on that commit.
   CI runs on the commits before they reach `main`. The commit that lands on `main` is the exact commit CI tested.
   A docs-only change gets a fast pass: CI reports both required check names quickly without running the full
   jobs. A change is docs-only when every path it changes against `main` is under `.planning/` or is a Markdown
   file that no test reads. *(amended 2026-11-16, 26 plan-phase D-16: a path under `.planning/` counts only when no
   test reads it (three `24.3-SKILLJUDGE-*` files are read). Paths come from `git diff --name-only -z --no-renames
   origin/main...HEAD`. An empty list, a git failure or a missing classifier output means the full jobs run.)*
   *(amended 2026-11-16, 26 plan-phase D-27 (review M7): a file a test reaches through a link resolved at runtime,
   such as a relative link target of README.md or docs/TROUBLESHOOTING.md, counts as "a file a test reads"; a drift
   test pins it.)*
   - Current: `enforce_admins` is false; direct pushes to `main` bypass the required checks. CI runs only on pushes to
     `main` and on pull requests.
   - Target: `enforce_admins` is true with both contexts required, and the documented flow puts every change through
     a branch whose CI is green before `main` moves.
   - Acceptance: `gh api repos/{owner}/{repo}/branches/main/protection` reads back `enforce_admins.enabled: true` and
     both contexts. The phase's last change reaches `main` through the documented flow, with green CI on its commit.
     A test pins the docs-only rule. A change touching only `.planning/` takes the fast pass. A change touching a
     `.py` file, `ci.yml`, or a Markdown file a test reads (such as `.claude/architecture.md`, read by
     `tests/test_postinstall.py:608`) runs the full jobs.

6. **Documentation**: The docs state which check runs at each stage, the measured timings, the new path to `main`, and
   the manual escape hatch.
   - Current: `.claude/dev-environment.md` says pre-commit hooks "mirror `make validate`". AGENTS.md and
     dev-environment.md say `make validate` "runs pre-commit hooks". `.claude/git-workflow.md` has no push flow.
   - Target: `.claude/dev-environment.md` has a commit / push / CI table with the measured timings.
     `.claude/git-workflow.md` documents the branch → green CI → `main` flow and the exact `gh` commands that turn
     `enforce_admins` off for a CI outage and back on. The false "runs pre-commit hooks" wording is corrected in
     AGENTS.md and dev-environment.md.
   - Acceptance: each statement above is present. `rg 'runs? pre-commit hooks'` over AGENTS.md and `.claude/` finds
     no claim that `make validate` runs pre-commit. The escape-hatch section holds both the off and the on command.
     *(amended 2026-11-16, 26 plan-phase D-23: since D-04, `make validate` does run `pre-commit run --all-files`,
     and the docs say so. The grep finds no `runs? pre-commit hooks` phrase, and no doc says the hooks "mirror"
     `make validate`.)*

## Boundaries

**In scope:**
- The commit-stage and pre-push hooks in `.pre-commit-config.yaml`, including `default_install_hook_types`.
- The push-gate tree check from R3.
- The `make install` hook step.
- The tests that pin the hooks, the Makefile recipe and the validate parity.
- The `main` branch-protection change (`enforce_admins` on, both contexts required).
- Any `ci.yml` trigger change the branch → CI → `main` flow needs.
- Docs: AGENTS.md, `.claude/dev-environment.md`, `.claude/git-workflow.md`.
- A pending todo for the tools outside this repo that push straight to `main`.
- *(added 2026-11-16, 26 D-03, D-07, D-08, D-12)* Per-gate `make` targets. `make install` is renamed `make dev-setup`.
  `make setup` is removed and `make run` launches the wizard, with every product message, test and doc updated.
  The flaky screen-family test is fixed (50 runs under `-n auto`).

**Out of scope:**
- Updating the GSD merge helpers, the ai-kit-commit-fold unit flow and the GSD phase-complete flow. They live outside
  this repo; a todo records them (owner, 2026-11-16).
- A fast test subset or test markers for the push stage. The owner chose the full suite at push (62.3 s measured).
- Speeding up the suite or changing the CI matrix or timeouts. They are not part of the hook gate.
- pylint. ruff covers its rules (roadmap context, 2026-10-15).
- Remote pre-commit repos and `pre-commit autoupdate`. All hooks stay `repo: local` on the uv toolchain.
- An automatic bypass of the `main` gate. The escape hatch is a documented manual toggle only.
- *(added 2026-11-16, 26 D-13)* A duplicate-code gate. Backlog 999.17 covers it.

## Constraints

- The push gate costs about 75 s on this host (validate 12.1 s + test 62.3 s, measured 2026-11-16). The owner accepted
  this, although an earlier rule of theirs put a full local suite at push only under 1 minute.
- The hooks run through uv (`uv run …`, `make …`) like `make validate`. They need no tool outside the dev dependencies.
- The hooks work the same in git worktrees, which share the main checkout's hooks directory. GSD executors commit in
  worktrees.
- The `enforce_admins` change is outward-facing and applies to every later push. It is applied only after the phase's
  own direct pushes to `main` are done, so the phase does not lock itself out.
- The tests use scratch git repos and a scratch `HOME`. No test touches this repo's `.git/hooks` or GitHub.

## Acceptance Criteria

- [ ] A test pins the commit-stage hooks to the `make validate` commands (tools, arguments, file sets) and fails on drift in either direction.
- [ ] No commit-stage hook runs pytest.
- [ ] `.pre-commit-config.yaml` has a `pre-push` stage that runs `make validate` and then `make test`, whatever files the push touches; a test pins it.
- [ ] In a scratch repo, a push whose suite fails exits non-zero and leaves the remote ref unchanged; a green push updates it. *(amended 2026-11-16, 26 plan-phase D-15: every "in a scratch repo" line here is met by `make hooks-e2e`, with the gate logic also pinned by pytest fake-runner tests.)*
- [ ] In a scratch repo, a staged uncommitted change refuses the push, naming the file.
- [ ] In a scratch repo, an untracked `.py` file under `installer/` or `tests/` refuses the push, naming the file. *(amended 2026-11-16, 26 plan-phase D-25: so does any untracked, non-ignored file outside `.planning/`, such as a root `conftest.py` or `pytest.ini`, listed sorted.)*
- [ ] In a scratch repo, an unstaged edit that breaks a test does not fail a push of a green HEAD, on an existing branch and on a new branch's first push.
- [ ] In a scratch repo, pushing a branch that is not HEAD is refused with the check-out-first message; a branch deletion goes through with no checks.
- [ ] After a passing, failing or interrupted push gate, the unstaged edits it set aside are restored byte-identical. *(amended 2026-11-16, 26 plan-phase D-17: "interrupted" means SIGINT, SIGTERM or SIGHUP to the gate's process group; SIGKILL and a SIGTERM sent only to `git` are documented residual cases with a recovery command.)*
- [ ] Refusal messages list the offending files sorted, and a file name with a space is printed intact.
- [ ] The commit-stage parity test fails when either side has zero checks; it compares the two sides as sets, not by order.
- [ ] `.pre-commit-config.yaml` sets `default_install_hook_types: [pre-commit, pre-push]`. *(amended 2026-11-16, 26 D-07: `[pre-commit]`; the push gate is installed by `make dev-setup`, not by pre-commit.)*
- [ ] `make install` in a scratch git repo leaves both hook files; a second run leaves them byte-identical.
- [ ] `make install` outside a git checkout exits 0 and prints the skip message.
- [ ] `make install` with `core.hooksPath` set exits non-zero and names `core.hooksPath`.
- [ ] `make install` run inside a git worktree installs the hooks into the shared hooks directory.
- [ ] `gh api …/branches/main/protection` reads `enforce_admins.enabled: true` and both required contexts.
- [ ] The phase's final change reaches `main` through the documented branch → green CI → `main` flow.
- [ ] The commit on `main` is the SHA CI tested; a branch that is no longer a fast-forward of `main` must be updated and re-tested.
- [ ] A test pins the docs-only rule: `.planning/`-only takes the fast pass; a `.py` file, `ci.yml` or a Markdown file a test reads runs the full jobs.
- [ ] No Makefile target, script, hook, CI file, AGENTS.md or `.claude/` doc uses `--no-verify` or `SKIP=` to pass the gate (must-NOT, P1).
- [ ] No hook auto-fixes files: no `--fix`, and no `ruff format` without `--check` (must-NOT, P3).
- [ ] `.claude/dev-environment.md` has the commit / push / CI table with timings.
- [ ] `.claude/git-workflow.md` documents the flow and both escape-hatch `gh` commands.
- [ ] No doc claims `make validate` runs pre-commit hooks. *(amended 2026-11-16, 26 plan-phase D-23: docs state that `make validate` runs `pre-commit run --all-files`; no `runs? pre-commit hooks` phrase and no "mirror `make validate`" claim remain.)*
- [ ] A pending todo lists the outside-repo tools that push straight to `main`.
- [ ] `make validate` and `make test` pass, and CI is green on ubuntu and macOS.

## Edge Coverage

**Coverage:** 32/32 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | A hook with the same tool but different arguments or files counts as drift; the parity test fails (AC 1) |
| empty | R1 | ✅ covered | The parity test fails when either side has zero checks (AC: zero-checks line) |
| ordering | R1 | ✅ covered | Parity compares the two sides as sets; hook order does not matter (AC: zero-checks line) |
| concurrency | R1 | ⛔ dismissed | Commit-stage checks only read files; parallel commits in separate worktrees each use their own index |
| concurrency | R2 | ✅ covered | An interrupted or failing gate exits non-zero, so git aborts the push and the remote ref stays (AC: failing push); set-aside edits are restored (AC: restore line) |
| adjacency | R2 | ✅ covered | (added 2026-11-16, D-05) A static gate carries both the commit and the push stage and runs at both. The push re-runs it on purpose, to cover commits made without hooks (AC: pre-push stage line) |
| empty | R2 | ✅ covered | (added 2026-11-16, D-05) A push with no changed files still runs every gate (`always_run`) (AC: "whatever files the push touches") |
| encoding | R2 | ⛔ dismissed | (added 2026-11-16, D-05) The gates take no file names (`pass_filenames: false`), so file-name encoding never reaches them |
| ordering | R2 | ✅ covered | (added 2026-11-16, D-05) The static gates run before the `make test` gate, which is last in the config. The pin covers the order (AC: pre-push stage line) |
| adjacency | R3 | ✅ covered | Untracked `.py` files count recursively under `installer/` and `tests/`; ignored files and paths outside the two trees do not; a pushed ref that is not HEAD is refused (AC: untracked, ref lines) *(amended 2026-11-16, 26 plan-phase D-25: every untracked, non-ignored file outside `.planning/` counts, at any depth, the repo root included (a root `conftest.py`, a root `pytest.ini`); ignored files and paths under `.planning/` do not)* |
| empty | R3 | ✅ covered | A push that only deletes a remote ref runs no checks and goes through (AC: ref line) |
| encoding | R3 | 🧪 backstop | File names come from git verbatim; held-out test with a space in a file name (AC: sorted-names line) |
| ordering | R3 | ✅ covered | Refusal messages list the offending files sorted (AC: sorted-names line) |
| idempotency | R3 | ✅ covered | Running the gate leaves the tree as it was: set-aside edits come back byte-identical, so a second run sees the same tree (AC: restore line) |
| concurrency | R3 | ✅ covered | Ctrl-C during the gate restores the set-aside unstaged edits (AC: restore line; must-NOT P2) *(amended 2026-11-16, 26 plan-phase D-17: SIGINT, SIGTERM or SIGHUP to the gate's process group, forwarded once as SIGINT)* |
| adjacency | R4 | 🧪 backstop | An existing foreign hook file is kept by pre-commit as `<hook>.legacy` and still runs; held-out test that it is not lost |
| empty | R4 | ✅ covered | Outside a git checkout: skip with a message, exit 0. With `core.hooksPath` set: fail and name it (AC: skip, hooksPath lines) |
| encoding | R4 | ⛔ dismissed | The hook files are pre-commit's generated ASCII scripts; the byte-identical rerun check already covers their content |
| ordering | R4 | ⛔ dismissed | The two hook files are independent; the order they are written in has no effect |
| concurrency | R4 | ⛔ dismissed | Two concurrent `make install` runs write identical bytes to the same files; the last write leaves the same content |
| idempotency | R4 | ✅ covered | A second `make install` leaves both hook files byte-identical (AC: rerun line) *(added: the floor has no R4 idempotency row; R4 states "Running it again changes nothing")* |
| adjacency | R4 | 🧪 backstop | (added) `make install` inside a git worktree installs into the shared hooks directory (AC: worktree line) |
| adjacency | R5 | ✅ covered | The commit on `main` is the exact SHA CI tested. A non-fast-forward branch is updated and re-tested (AC: SHA line) |
| empty | R5 | ✅ covered | A docs-only change still gets both required check results, through the fast pass, so `main` never waits for a check that never comes (AC: docs-only line) |
| ordering | R5 | ✅ covered | Of two green branches, the second is no longer a fast-forward after the first lands; it is updated and re-tested (AC: SHA line) |
| encoding | R5 | 🧪 backstop | The docs-only rule matches paths as git reports them (NUL-separated, so spaces survive); the `.md` suffix match is exact and lowercase; a rename counts both its old and its new path. Held-out test with a renamed `.py` file and a path with a space |
| idempotency | R5 | ✅ covered | Applying the protection again reads back the same state (AC: `gh api` read-back line) |
| concurrency | R5 | ⛔ dismissed | ci.yml cancels a superseded run on the same ref. The superseded SHA never gets checks and cannot land, which is the intended result |
| adjacency | R5 | ✅ covered | (added) A Markdown file a test reads is not docs-only and runs the full jobs (AC: docs-only line; must-NOT P4) |
| adjacency | R6 | ⛔ dismissed | Prose docs with no merge or touch semantics; the presence and grep checks are the acceptance |
| empty | R6 | ⛔ dismissed | Each named doc section must exist and be non-empty, which the presence checks already require |
| ordering | R6 | ⛔ dismissed | The order of documentation sections has no pass/fail meaning |

## Prohibitions (must-NOT)

**Coverage:** 6/6 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| P1: MUST NOT let any Makefile target, script, hook, CI file, AGENTS.md or `.claude/` doc use `--no-verify` or `SKIP=` to get past the gate | R2, R6 | resolved | verification: test (a grep test over the named files) |
| P2: MUST NOT discard or rewrite uncommitted work. Unstaged edits set aside by the push gate come back byte-identical after a pass, a failure or an interrupt *(amended 2026-11-16, 26 plan-phase D-17: an interrupt is SIGINT, SIGTERM or SIGHUP to the gate's process group)* | R3 | resolved | verification: test (a scratch-repo test that compares bytes after each outcome) *(D-15: `make hooks-e2e`, plus a pytest child that proves the forwarding)* |
| P3: MUST NOT auto-fix files in any hook (no `--fix`, no `ruff format` without `--check`) | R1, R2 | resolved | verification: test (a test over the hook entries) |
| P4: MUST NOT let the docs-only fast pass skip the full jobs for a change that touches code, CI config or a file a test reads | R5 | resolved | verification: test (a test of the docs-only rule) |
| P5: MUST NOT let a test write this repo's `.git/hooks` or call GitHub | R2, R3, R4, R5 | resolved | verification: judgment (scratch repos and scratch `HOME` by design; checked in review) *(amended 2026-11-16, 26 plan-phase D-15: also binds `scripts/hooks-e2e.sh`, whose scratch-only markers a text test pins)* |
| P6: MUST NOT leave `enforce_admins` off after an escape. The documented off command is always followed by the on command and a read-back | R6 | resolved | verification: judgment (doc review) |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                  |
|--------------------|-------|------|--------|--------------------------------------------------------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Commit, push, install and `main` outcomes are explicit |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Outside tools, test subset and auto-bypass excluded    |
| Constraint Clarity | 0.80  | 0.65 | ✓      | Measured timings; apply-order constraint for the gate  |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | 28 pass/fail criteria, scratch-repo checks             |
| **Ambiguity**      | 0.14  | ≤0.20| ✓      |                                                        |

## Interview Log

Interactive, 4 rounds plus the gate. The owner answered every question; jev was not asked, because the interactive
path asks jev only for items the owner sends to it. Rule: the best design wins over the smallest diff (MVP mode
inactive).

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Researcher | Which tree must the push gate test? | none | Owner: run the full push stack only on the remote when the suite takes over 1 minute. This led to the timing measurement and round 2. |
| 1 | Researcher | Push runs validate + test, or test only? | none | validate + test, mirroring CI (R2) |
| 2 | Simplifier | Suite measured at 62.3 s, validate 12.1 s: what runs at push? | none | validate + full test, even though it is above 1 minute (R2, Constraints) |
| 2 | Boundary Keeper | Red commits reaching remote `main` when CI runs after the push? | none | Gate `main` behind CI (R5) |
| 3 | Boundary Keeper | Which tree? (asked again) | none | Owner asked "test only what is staged?". The pre-commit stash facts were presented in round 4. |
| 3 | Boundary Keeper | Where is the gate enforced? | none | GitHub, binding admins (R5) |
| 3 | Boundary Keeper | Update outside tools that push to `main`? | none | Repo only; document the flow; todo for the tools (Boundaries) |
| 4 | Failure Analyst | Staged tree: refuse the gaps? | none | Staged tree, refuse staged-uncommitted changes and untracked `.py` under `installer/` or `tests/` (R3) |
| 4 | Failure Analyst | Escape hatch when CI is down? | none | Documented manual `enforce_admins` toggle (R6) |
| gate | Seed Closer | Write SPEC.md at ambiguity 0.15? | none | Yes |
| edge | Failure Analyst | Pushed ref is not HEAD? | none | Refuse; check that branch out first (R3) |
| edge | Failure Analyst | `core.hooksPath` set, so pre-commit will not install? | none | `make install` fails loudly (R4) |
| edge | Failure Analyst | Docs-only changes under the `main` gate (macOS ~12 min)? | none | Fast pass for docs-only, defined as `.planning/` or Markdown no test reads (R5) |
| must-NOT | Failure Analyst | Keep which prohibitions? | none | All six, P1 to P6 |

---

*Phase: 26-commit-and-push-quality-hooks*
*Spec created: 2026-11-16*
*Next step: /gsd-discuss-phase 26 — implementation decisions (how to build what's specified above)*
