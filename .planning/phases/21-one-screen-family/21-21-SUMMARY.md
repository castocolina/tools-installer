---
phase: 21-one-screen-family
plan: "21"
subsystem: ui
tags: [textual, tests, matrix, fork-guard, docs]
requires: [21-06, 21-12, 21-13, 21-16, 21-18, 21-20]
provides:
  - UI-01 matrix (7 mutation sources x 6 views) in tests/test_screen_family.py
  - fork guard test_the_replaced_forks_are_gone (26 names)
  - Phase 21 section in .claude/architecture.md, pinned by tests/test_docs.py
key-files:
  modified:
    - tests/test_screen_family.py
    - tests/test_docs.py
    - .claude/architecture.md
metrics:
  tasks: 2
  completed: 2026-11-03
status: complete
commits: 2
plan_head_before: cddad0c0c158a5fdc63d852f03efcf38f6784716
plan_head_after: 8eb4583592a7892737afff91d5fdba05e5d04a39
actuals:
  tokens: 14000
  tasks: 2
  commits: 2
---

# Phase 21 Plan 21: UI-01 matrix, fork guard and Phase 21 doctrine Summary

42-case matrix proving every mutation reaches every view, two held-mutation repaint cases, a 26-name guard against the deleted forks, and the architecture section that pins them.

## Commits

- 326955c test(21-21): UI-01 matrix over every mutation source and view
- 8eb4583 docs(21-21): record the screen family and guard its deleted forks

## What was built

- `MATRIX_SOURCES` (7), `MATRIX_TARGETS` (6), `matrix_app` and `MatrixSeams` in `tests/test_screen_family.py`. `matrix_app` is a call to `_family_app` (REUSE 21-1); `_family_app` and `tests/screen_family.py` are untouched.
- Witnesses: `w-system`, `w-user` (node tool, carries `matrix witness note`), `w-ai`, MISSING before; the pass a source requests publishes them through `FrozenStateService.queued`, which each case arms after the launch pass settles. Extra tools: `up-system/user/ai` (outdated, brew-owned, for `u`) and `rm` (removable). A `tweak` policy reads `w-system` through `missing_requires_now`.
- Reused per source: install close -> real ExecuteScreen run (space, enter, enter, escape) with a fake install; `u` x3 -> `ScriptedUpdates` + `_open_view`; Uninstall removal -> `HeldRemover` (pre-released) + `_confirm_removal`; Policies toggle -> `_policy`/`_policy_result`; Doctor `r` -> `_managed_report` + `_open_view`. Targets reuse `_section_of`, `_doctor_text`, `_row_keys`. `settle`/`wait_until` only, no sleeps.
- Held navigation and environment-row cases as specified (same `app.catalog` / Uninstall screen object, no key press after release).
- Fork guard: `git ls-files installer` + `git ls-files --others --exclude-standard installer` + `setup.py`, pattern `(?<![\w-])NAME(?![\w-])`, reports `path:line`. Zero hits on the tree: no stale mention to rewrite; registry.toml confirmed (`_managed_hint` 0, `removed together` 1).
- `## Phase 21: one screen family` in `.claude/architecture.md` (force-added, tracked), `_PHASE_21_REQUIRED` and its test in `tests/test_docs.py`.

## RED / guard honesty

The matrix, held-navigation, environment-row and fork-guard tests all pass on today's tree: they are regression guards, not RED. The docs test was genuinely RED before the section existed (`missing load-bearing phrase: ## Phase 21: one screen family`). The only failures met while building were builder gaps (install-close waiting on `run_in_flight`, which a fast fake never holds; fixed with `settle`) and pyright strictness on a lambda; no production gap surfaced.

Proof the guards can fail:
- `_render_published` made a no-op: 6 visible-source matrix cases (install-close-system, update-system-system, update-user-user, update-ai-ai, policies-toggle-policies, uninstall-removal-uninstall), the held-navigation case and the environment-row case failed. (doctor-r-doctor still passes: the reinstall completion repaints Doctor itself.)
- `UninstallScreen.state_refreshed` without `_reread_env`: the environment-row case failed (`'#ban' not in [...]`).
- An untracked `installer/zz_scratch.py` naming `ToolRow` and `toggle_in_flight` failed those two guard cases with `path:line`.
Production files were restored byte-for-byte after each probe (not committed).

## Test counts

- tests/test_screen_family.py collected: 125 at start -> 170 after Task 1 (+42 matrix, +1 shape, +1 held, +1 env = +45) -> 196 after Task 2 (+26 guard). Measured-start-plus-delta floors met (plan floors 168/194 assumed 123).
- tests/test_docs.py: 8 -> 9.
- Full suite: 5188 passed, 4 skipped; coverage 96.21%. `make validate` exit 0, `make test` exit 0 on the final tree.

## Deviations from Plan

- [Rule 3 - naming] A pre-existing `_matrix_app` (21-16 refusal matrix) already lives in the file; the new public `matrix_app` coexists with it. Left as is rather than renaming 21-16 code.
- `matrix_app(tmp_path, ...)` returns a `MatrixSeams` dataclass (app, service, bans, witnesses) instead of a bare tuple, and takes optional `remover`, `bans`, `job_apply` for the two extra cases.
- No existing test was changed or deleted. No production file changed.

## Human verification (not blocking)

NO_COLOR tmux UAT at 80x20 in a disposable container (frontmatter entry of 21-21-PLAN.md and Task 2 human-check): confirm `! [drift]`, `● [on]`, `○ [off]`, `…`, `✓`, `!` read distinctly without color, columns align, no line passes column 78, and both held-lock refusals (`A daemon apply is running...`, `A policy toggle is running...`) fit one row, using the container-only slow `systemctl` shim.

Known gap to cover in the same check: at 80x20 the Doctor card covers the status row, so Doctor refusals and its read error are not visible (RUN-LEDGER).

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- tests/test_screen_family.py, tests/test_docs.py, .claude/architecture.md present and committed.
- Commits 326955c and 8eb4583 are ancestors of HEAD.
