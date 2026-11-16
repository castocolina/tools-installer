---
phase: 26-commit-and-push-quality-hooks
reviewed: 2026-11-16T18:45:30Z
depth: deep
files_reviewed: 37
files_reviewed_list:
  - devtools/push_gate.py
  - devtools/hooks.py
  - devtools/docs_only.py
  - devtools/__init__.py
  - scripts/hooks-e2e.sh
  - Makefile
  - .pre-commit-config.yaml
  - .github/workflows/ci.yml
  - pyproject.toml
  - setup.py
  - installer/compose.py
  - installer/guidance.py
  - tests/test_push_gate.py
  - tests/test_hooks_install.py
  - tests/test_hook_wiring.py
  - tests/test_docs_only.py
  - tests/test_ci_workflow.py
  - tests/test_makefile.py
  - tests/test_docs.py
  - tests/test_guidance.py
  - tests/test_screen_family.py
  - tests/test_wizard_app.py
  - tests/test_tool_browser.py
  - tests/test_setup.py
  - tests/test_render.py
  - tests/test_app.py
  - tests/test_schedules_handover.py
  - tests/test_catalog_audit_skill.py
  - tests/e2e_landing_driver.py
  - .claude/dev-environment.md
  - .claude/git-workflow.md
  - .claude/python-tooling.md
  - AGENTS.md
  - README.md
  - docs/PUBLISHING.md
  - .graphifyignore
  - .claude/skills/catalog-audit/SKILL.md
findings:
  critical: 1
  warning: 3
  info: 5
  total: 9
  necessity: 0
status: issues_found
---

# Phase 26: Code Review Report

**Reviewed:** 2026-11-16T18:45:30Z
**Depth:** deep
**Files Reviewed:** 37
**Status:** issues_found

## Summary

I reviewed the whole range ae9b99b0..HEAD. Most of the time went to the plans that had no per-plan review: `devtools/push_gate.py` (26-04), `devtools/hooks.py` (26-05), the Makefile and `.pre-commit-config.yaml` wiring (26-01) and the `make run` rename (26-02). I also checked the code the gate relies on: pre-commit 4.x `staged_files_only.py` and `git.py` in `.venv`, and how `git rev-parse` treats flags it does not know. I tested the claims about git behavior in throwaway repos under the session scratchpad, never in this checkout.

Parts that hold up:
- Stdin parsing fails closed on bad input. Deletions are detected by an all-zero sha, so SHA-256 repos work too.
- A tag is peeled to its commit before the HEAD comparison.
- Signal forwarding handles the window while the child is being spawned, sends SIGINT once and never exits 0 after a signal.
- The hook installer checks symlinks, hard links, a foreign `pre-push`, an existing `pre-commit.legacy` and `core.hooksPath` before it writes anything.
- The rename is complete in `installer/`, `setup.py`, `install.sh`, the tests and the current docs. Only older plan documents under `docs/superpowers/` still say `make setup`.
- The wiring, gate, installer and docs-only tests all pass (`uv run pytest tests/test_push_gate.py tests/test_hooks_install.py tests/test_hook_wiring.py tests/test_docs_only.py`, scratch HOME).

The main problem: the push gate promises that the tested tree is the pushed commit, but local git index states break that promise. Intent-to-add entries and skip-worktree or assume-unchanged edits pass all five refusals, and pre-commit then runs the gates over that content (CR-01). Two smaller gaps let local state into the tested tree: ignored files under `.claude/`, which tests read (WR-01), and the uv environment, which follows unstaged `pyproject.toml`/`uv.lock` edits (WR-02). The hook installer also fails open on git older than 2.31 (WR-03). For each of these, CI is still the backstop before `main`.

Not covered: `scripts/hooks-e2e.sh` and the docs-only CI plan (26-06..26-08) got only a skim, because their per-plan reviews already ran. I did not check uv's own signal forwarding inside `uv run`.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Intent-to-add and skip-worktree/assume-unchanged entries bypass every refusal, so the gate tests a tree that is not HEAD

**File:** `devtools/push_gate.py:163-188`
**Issue:** The gate's whole job is to make the tested tree equal HEAD (SPEC R3, the `refusal` docstring: "None when the tested tree is the pushed commit"). The checks are:

```python
            ["diff", "--name-only", "--diff-filter=U", "-z"],
...
            ["diff", "--cached", "--name-only", "-z"],
...
                for name in _names(_query(git, ["ls-files", "--others", "--exclude-standard", "-z"]))
...
    edited = _names(_query(git, ["diff", "--name-only", "-z", "--", ".pre-commit-config.yaml"]))
```

Two index states pass all of them while the gates still see content that is not in HEAD:

1. **Intent-to-add (`git add -N`).** I checked this in a scratch repo. After `git add -N tests/test_new.py`, `diff --cached` is empty, `--diff-filter=U` is empty, `ls-files --others` is empty and the gate-read query is empty. pre-commit then calls `_intent_to_add_cleared()` (`.venv/.../pre_commit/staged_files_only.py:36-45`). That runs `git rm --cached` on those paths for the whole run, so the files stay on disk as untracked files that every gate reads. Example: `installer/helper.py` is intent-to-add and a committed module imports it. The push gate passes `make test` locally, and CI on the pushed commit fails with `ModuleNotFoundError`.
2. **`git update-index --skip-worktree` / `--assume-unchanged`.** I checked this in a scratch repo too. After editing a skip-worktree file, pre-commit's own stash probe (`git diff-index ... <write-tree>`) exits 0, so nothing is set aside, and the gates test the edited bytes. None of the refusals look at these index flags either.

Both states are local-only, git does not show them in normal views, and the gate's message claims the opposite. Neither is covered by `tests/test_push_gate.py` or `scripts/hooks-e2e.sh`.
**Fix:** Add two refusals next to the staged check, before the untracked check:

```python
        (
            # intent-to-add entries: pre-commit un-adds them for the run and the gates still read them
            ["diff", "--name-only", "--diff-filter=A", "-z"],
            "intent-to-add files are not committed:",
            "commit them, or drop the intent (git rm --cached <file>), then push again.",
        ),
```

and, after the loop:

```python
    hidden = [
        line[2:]
        for line in os.fsdecode(_query(git, ["ls-files", "-v", "-z"])).split("\0")
        if line[:1].islower() or line[:1] == "S"  # assume-unchanged (lowercase) or skip-worktree (S)
    ]
    if hidden:
        return "push refused: " + _part(
            "these files are marked assume-unchanged or skip-worktree, so the gates may test edits git hides:",
            hidden,
            "clear the flag (git update-index --no-assume-unchanged / --no-skip-worktree <file>), then push again.",
        )
```

Add one fake-runner test for each refusal, plus one `hooks-e2e` case for `git add -N`.

## Warnings

### WR-01: Ignored files under `.claude/` are read by tests but are not in `GATE_READ_PATHSPECS`

**File:** `devtools/push_gate.py:36-64` (with `.gitignore:55`, `tests/test_catalog_audit_skill.py:78-79`)
**Issue:** `.gitignore` ignores all of `.claude/`. The tracked rule docs and skills under it were force-added. So a new file under `.claude/` stays untracked and ignored: a plain `git add` refuses it and `git add -A` skips it without a word. The first untracked check uses `--exclude-standard`, so it never lists these files, and `GATE_READ_PATHSPECS` has no `.claude` entry. Yet tests read that tree. One example asserts that every repo path cited in the skill exists:

```python
        for target in _REPO_PATH_RE.findall(text):
            assert (REPO_ROOT / target).exists(), f"{doc.name}: {target}"
```

Example: SKILL.md (tracked) cites a new `references/foo.md`, and that file was never force-added. The local push gate passes, and CI fails on the pushed commit. The same applies to `_skill_files()` (`rglob`) and to the fixed `.claude/*.md` paths in `tests/test_docs.py:17-28`. `devtools/docs_only.py:23` already lists `.claude/*` as test-read, so the two lists disagree about which files tests read.
**Fix:** Add the test-read `.claude` trees to the list (a bounded literal directory, so git does not walk `.venv`):

```python
    ".claude/*.md",
    ".claude/skills/**",
```

Then update `test_the_gate_read_pathspecs_are_pinned_and_bounded`.

### WR-02: The push environment follows unstaged `pyproject.toml`/`uv.lock` edits and keeps extra packages

**File:** `devtools/hooks.py:26`, `devtools/push_gate.py:182`
**Issue:** The shim runs `exec uv run python -m devtools.push_gate "$@"`. This happens before pre-commit sets the unstaged edits aside, so `uv run` syncs `.venv` from the working-tree `pyproject.toml`/`uv.lock`. After the stash, every gate runs `uv run ...` again. `uv run` syncs inexactly by default, so packages that the HEAD lock does not list stay installed. Refusal 4 covers only `.pre-commit-config.yaml`:

```python
    edited = _names(_query(git, ["diff", "--name-only", "-z", "--", ".pre-commit-config.yaml"]))
```

Example: `uv add requests` (pyproject and lock now edited but unstaged), then `git add installer/x.py && git commit`, then push. The gate passes, because the import resolves in the local `.venv`. CI runs `uv sync`, which is an exact sync, and fails at import. The tested environment is not the pushed commit's environment.
**Fix:** Refuse unstaged edits to the files that define the environment, in the same way as the config:

```python
    edited = _names(_query(git, ["diff", "--name-only", "-z", "--", ".pre-commit-config.yaml", "pyproject.toml", "uv.lock"]))
```

Also make the shim sync exactly against the committed lock: `exec uv run --locked --exact python -m devtools.push_gate "$@"`. Update the refusal header wording and the pinned shim test.

### WR-03: The hook installer fails open on git older than 2.31 (writes the push gate into a junk directory and reports success)

**File:** `devtools/hooks.py:109-119, 140-151`
**Issue:**

```python
    common = run([git, "rev-parse", "--path-format=absolute", "--git-common-dir"])
...
    common_dir = Path(common.stdout.strip())
```

`--path-format` arrived in git 2.31. When `git rev-parse` sees a flag it does not know, it prints the flag and exits 0. I checked this on 2.56 with a misspelled flag: `git rev-parse --path-formatx=absolute --git-common-dir` printed `--path-formatx=absolute` and `.git`, with rc=0. On older git, `common_dir` becomes the relative path `"--path-format=absolute\n.git"`. Then `_hook_problem` finds nothing there, and `pre-commit install` writes the real `.git/hooks/pre-commit`. After that, `hooks.mkdir(parents=True, exist_ok=True)` creates a directory with a newline in its name at the repo root, writes the `pre-push` shim into it, and prints `commit hook and push gate installed`. The push gate is never installed, the user is told the opposite, and a junk directory is left in the work tree. No README or doc names a minimum git version.
**Fix:** Fail closed on output that does not look like a path:

```python
    common_dir = Path(common.stdout.strip())
    if "\n" in common.stdout.strip() or not common_dir.is_absolute() or not common_dir.is_dir():
        return _fail("git 2.31 or newer is required (rev-parse --path-format)")
```

Apply the same check to `git_dir`. Add one fake-runner test that returns the two-line output.

## Info

### IN-01: The shim loads the gate from the tree being pushed; a tree without `devtools/` cannot be pushed and gets a cryptic error

**File:** `devtools/hooks.py:26`
**Issue:** `python -m devtools.push_gate` imports the module from the work tree, before any stash. A branch that predates this phase has no `devtools/` (`git ls-tree ae9b99b0 devtools` is empty), for example `origin/ci/phase-17-final`. Pushing it fails with `No module named devtools.push_gate`, and AGENTS.md forbids skipping a hook. An unstaged edit to `push_gate.py` also decides its own push.
**Fix:** In the shim, before `exec`: `[ -f devtools/push_gate.py ] || { echo "pre-push: this tree has no devtools/push_gate.py (it predates the push gate); merge or rebase on main first" >&2; exit 1; }`.

### IN-02: The refusal advice for a tag that is not at HEAD is wrong

**File:** `devtools/push_gate.py:191-199`
**Issue:** With `git push --follow-tags`, or with `push.followTags` set, an annotated tag on `HEAD~1` is refused with "check out that branch and push from it". There is no branch to check out. The refusal itself matches SPEC R3. Only the advice is wrong.
**Fix:** When `update.local_ref.startswith("refs/tags/")`, say "push the tag from a checkout of its commit, or push it after the branch".

### IN-03: An interrupted push also prints "a gate failed"

**File:** `devtools/push_gate.py:287-293`
**Issue:** After Ctrl-C, `run_forwarding_signals` prints `push interrupted: no ref was pushed.` and returns 130. `main` then adds `push refused: a gate failed. Fix the gate named on the make <target> line above`, which points the user at a gate that did not fail.
**Fix:** Skip the gate-failed line when `status == 130`.

### IN-04: A comment claims DoctorScreen recognizes a "Run `make run`" prefix

**File:** `installer/guidance.py:421`
**Issue:** The renamed comment says the "Run `make fix`"/"Run `make run`" prefixes are ones "DoctorScreen._tui_guidance already recognises". `installer/doctor_screen.py:467` matches only `"Run \`make fix\`"`, plus the disk-pressure prefix. The claim was already false with `make setup`. The rename kept it.
**Fix:** Drop "/\"Run `make run`\"" from the comment.

### IN-05: `docs_only._git_runner` ignores its `git` parameter

**File:** `devtools/docs_only.py:42-46`
**Issue:** `argv` already carries the git path (line 58), so the `git` argument of `_git_runner(git)` is never used.
**Fix:** `def _run(args): return subprocess.run(list(args), capture_output=True, check=False)`, and pass `run or _run`.

---

_Reviewed: 2026-11-16T18:45:30Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

## Orchestrator Verification

Every Critical and Warning finding was re-checked against the cited source before fixing. None was refuted.

- CR-01: verified. A scratch repository probe calling `push_gate.refusal()` returned `None` for an intent-to-add file, a skip-worktree edit and an assume-unchanged edit.
- WR-01: verified. `.gitignore:55` ignores `.claude/`, `GATE_READ_PATHSPECS` has no `.claude` entry, and `tests/test_docs.py` / `tests/test_catalog_audit_skill.py` read that tree. `git --glob-pathspecs ls-files --others -- '.claude/*.md' '.claude/skills/**'` lists nothing in this checkout today, so adding the two pathspecs does not refuse a clean push here.
- WR-02: verified. The refusal only checks `.pre-commit-config.yaml` for unstaged edits, and the shim's `uv run` syncs from the working tree. The fix extends the unstaged-edit refusal to `pyproject.toml` and `uv.lock`. The shim stays the same: changing it would make every developer reinstall the hook.
- WR-03: verified. `devtools/hooks.py:109,115` trusts the `rev-parse --path-format=absolute` stdout without checking it.
- IN-01..IN-05: out of the default fix scope (Critical + Warning).
