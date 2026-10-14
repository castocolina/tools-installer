---
phase: 17-stop-the-bleeding
plan: "05"
subsystem: installer
tags: [registry, postinstall, graphify, sublime, codex, symlink-safety, non-interactive]

requires:
  - phase: 12.4
    provides: the rtk/graphify postinstall hooks this plan deletes
provides:
  - graphify installs and updates with zero host-registration side effects (no cwd writes)
  - Sublime Linux tarball members name the real binary, not the archive directory
  - codex's install script never prompts (CODEX_NON_INTERACTIVE=1 via the registry env table)
affects: [17-registry-data-fixes, 18-verified-key, phase-19-receipts]

actuals:
  tokens: 18400
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "cwd-writes probe: disposable-container probe of a vendor hook's per-form filesystem side effects, recorded verbatim in the SUMMARY"

key-files:
  created: []
  modified:
    - installer/registry.toml
    - installer/postinstall.py
    - installer/model.py
    - .claude/architecture.md
    - tests/test_postinstall.py
    - tests/test_update.py
    - tests/test_registry.py

key-decisions:
  - "D-03 removal branch taken: the container probe proved three of four graphify registration forms write into the cwd, so the postinstall key was removed rather than kept with a pinned cwd"
  - "Update path also disabled by the same key removal (update.py:309 dispatches tool.postinstall too — the plan's RESEARCH correction)"

patterns-established:
  - "Call-list acceptance: install/update tests assert the exact runner argv list and an empty scratch cwd, not merely 'no exception'"

requirements-completed: [SAFE-02, SAFE-01, SAFE-07]

duration: 55min
completed: 2026-10-14
status: complete

coverage:
  - id: D1
    description: "Installing and updating graphify runs exactly one uv command and leaves the working directory empty; no graphify host-registration hook exists anywhere"
    requirement: SAFE-02
    verification:
      - kind: unit
        ref: "tests/test_postinstall.py#test_installing_graphify_runs_no_host_registration"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_updating_graphify_runs_no_host_registration"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_only_codegraph_and_rtk_declare_a_postinstall_hook"
        status: pass
    human_judgment: false
  - id: D2
    description: "Sublime's two Linux tarball methods link sublime_text/sublime_text (the binary), with a Verified 2026-10-14 comment"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_sublime_linux_tarballs_link_the_binary_inside_the_archive_dir"
        status: pass
    human_judgment: false
  - id: D3
    description: "codex's script method sets CODEX_NON_INTERACTIVE=1 through the registry env table, rendered as a shell prefix"
    requirement: SAFE-07
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_codex_script_runs_non_interactive"
        status: pass
    human_judgment: false
  - id: D4
    description: "Disposable-container graphify probe result recorded (which forms write into the cwd)"
    verification:
      - kind: manual_procedural
        ref: "podman run --rm python:3.12-slim probe (output recorded below)"
        status: pass
    human_judgment: true
    rationale: "The probe runs against the live vendor package in a disposable container; its output is recorded here verbatim for human confirmation."
---

# Phase 17 Plan 05 Summary

**graphify's cwd-writing postinstall hook removed end to end; Sublime's Linux member fixed to the binary; codex's install script made non-interactive**

## Performance

- **Duration:** 55 min
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- graphify's `postinstall = "graphify-register"` removed from the registry; install and update of graphify now run exactly `uv tool install/upgrade graphifyy` and nothing else — the dead hook code (`_graphify_register`, `_GRAPHIFY_HOST_SUBCOMMANDS`, the `POSTINSTALL_HOOKS` entry, the `POSTINSTALL_HOOK_NAMES` name) and its tests are deleted, and `.claude/architecture.md` records the removal
- Sublime's two Linux tarball methods now set `member = "sublime_text/sublime_text"` with `bin_name = "subl"`, strip 0 default, and a dated `# Verified 2026-10-14` comment
- codex's script method declares `env = { CODEX_NON_INTERACTIVE = "1" }`, rendered by the existing `_env_prefix` mechanism as a shell prefix; no code change needed

## Task Commits

1. **Task 1: graphify hook removed end to end (SAFE-02/D-03)** — `01e5629` (fix)
2. **Task 2: Sublime member + codex non-interactive (SAFE-01/D-02, SAFE-07/D-10)** — `f1f6f89` (fix)

## Container probe (D-03, recorded verbatim)

`python:3.12-slim`, `pip install -q graphifyy==0.9.54`, per-form scratch HOME and scratch cwd:

```
claude install: cwd=[.claude CLAUDE.md ]
install --platform claude: cwd=[]
install --platform opencode: cwd=[.opencode ]
install --platform cursor: cwd=[.cursor ]
```

Three of four forms write into the cwd, so D-03's removal branch was taken (RUN-LEDGER Q1). The container was `--rm` and removed; nothing was installed on the host; `pyproject.toml`/`uv.lock` untouched.

## TDD RED evidence (trimmed)

Task 1 (before implementation):
```
FAILED tests/test_postinstall.py::test_installing_graphify_runs_no_host_registration
FAILED tests/test_update.py::test_updating_graphify_runs_no_host_registration
E       AssertionError: assert [['uv', 'tool...', 'install']] == [['uv', 'tool... 'graphifyy']]
E       Left contains 4 more items, first extra item: [.../home/.local/bin/graphify', 'claude', 'install']
E       AssertionError: graphify: unexpected postinstall hook declared
E       assert 'graphify-register' is None
```

Task 2 (before implementation):
```
FAILED tests/test_registry.py::test_sublime_linux_tarballs_link_the_binary_inside_the_archive_dir
FAILED tests/test_registry.py::test_codex_script_runs_non_interactive - KeyError: 'env'
```

## Verify results

- Task 1: `uv run pytest tests/test_postinstall.py tests/test_update.py tests/test_registry.py tests/test_model.py tests/test_post_install.py tests/test_docs.py -q --no-cov` → all pass; `-k "graphify_runs_no_host_registration or only_codegraph_and_rtk"` → 3 passed; acceptance greps: `git grep -n -e graphify-register ... -- installer tests` exit 1 (nothing), graphify block `postinstall` count 0, ≥1 `Verified 2026-10-14`
- Task 2: `uv run pytest tests/test_registry.py tests/test_executors.py -q --no-cov` → all pass; `-k "sublime_linux_tarballs or codex_script_runs_non_interactive"` → 2 passed; `member = "sublime_text/sublime_text"` count 2, `member = "sublime_text"$` count 0, `env = { CODEX_NON_INTERACTIVE = "1" }` count 1
- Final tree: `make validate` green (ruff, ruff-format, pyright, bandit, vulture, shellcheck); `make test` → 3467 passed, 4 skipped, coverage 95.87% (gate 90%)

## Files Created/Modified
- `installer/registry.toml` — graphify postinstall removed + Verified comment; 2026-09-11 comment reworded as historical; Sublime member x2 + Verified comment; codex env + Verified comment extension
- `installer/postinstall.py` — deleted `_GRAPHIFY_HOST_SUBCOMMANDS`, `_graphify_register`, and the `POSTINSTALL_HOOKS["graphify-register"]` entry
- `installer/model.py` — `POSTINSTALL_HOOK_NAMES` is now `{codegraph-mcp-register, rtk-register}`
- `.claude/architecture.md` — Phase 9 hook list records graphify-register's removal and the cwd-writes reason
- `tests/test_postinstall.py` — added `test_installing_graphify_runs_no_host_registration`; deleted the 7 graphify-register hook tests (incl. the 16-case parametrized CSV test)
- `tests/test_update.py` — added `test_updating_graphify_runs_no_host_registration`
- `tests/test_registry.py` — renamed/narrowed to `test_only_codegraph_and_rtk_declare_a_postinstall_hook`; added the Sublime and codex behavior tests

## Decisions Made
- Removed the key entirely rather than pinning cwd (D-03's rule: the probe must prove the cwd stays empty; it proved the opposite)
- The literal name `graphify-register` was kept out of test comments too, so the acceptance grep over `installer tests` is clean

## Deviations from Plan

### Auto-fixed Issues

**1. [Executor correction] Accidental truncation of the new install-path test, caught by make validate**
- **Found during:** Task 1 (deleting the old graphify tests in tests/test_postinstall.py)
- **Issue:** Deleting from the first graphify test to EOF also removed the newly appended `test_installing_graphify_runs_no_host_registration`, silently narrowing the verify run to 2 tests instead of 3
- **Fix:** Restored the test; pyright/lint failures surfaced it and the full verify re-run passed
- **Files modified:** tests/test_postinstall.py
- **Verification:** targeted `-k` run shows 3 passed; full suite green
- **Committed in:** 01e5629 (Task 1 commit)

**2. [Environment] `git add .claude/architecture.md` refused by .gitignore**
- **Found during:** Task 1 commit
- **Issue:** `.claude/` is gitignored; git add warned, though the file is tracked so the staged modification was already present
- **Fix:** Verified `git ls-files` shows it tracked and the commit includes it (`git show 01e5629 --stat` confirms)
- **Files modified:** none
- **Verification:** commit stat
- **Committed in:** 01e5629

---

**Total deviations:** 2 auto-fixed (1 self-inflicted truncation caught by quality gates, 1 gitignore friction)
**Impact on plan:** None on scope; all plan files_modified touched as specified.

## Issues Encountered
- The plan's context note said RESEARCH claimed the update path never runs the hook; confirmed in code that `update.py` does dispatch it (`_run_postinstall`), and the key removal disables both paths — the update-path test was added exactly as planned.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `POSTINSTALL_HOOK_NAMES` and `POSTINSTALL_HOOKS` now hold exactly two hooks; the parity tests in tests/test_model.py and tests/test_post_install.py needed no edits (both sets shrank together)
- Phase 18's `verified` key conversion can pick up the three new `# Verified 2026-10-14` comments
- Plan 17-02's `is_file()` guard remains the backstop for Sublime's corrected member

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
