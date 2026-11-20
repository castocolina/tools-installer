# Phase 30 Plan 04 Summary

- **Task 1 — `523cfd1a`:** Added Linux Ghostty shell synchronization, conflict-safe removal across default files, dry-run drift reporting, created-file proof, and the onboarding skill update.
- **Task 2 — `6c0c0ba7`:** Added removal and status-row guards. The generic `TERMINAL_KEYS.get(tool.id)` dispatch remains in `installer/app.py`; that file contains no Ghostty-specific code.

## Test evidence

- **Task 1 RED:** The targeted suite failed the new Ghostty behavior tests, including shell-region writing, conflict handling, resolver moves, and dry-run drift.
- **Task 1 GREEN:** `uv run pytest tests/test_terminal_shell.py tests/test_terminal_keys.py tests/test_tool_onboarding_skill.py tests/test_version_status.py -n auto -q --no-cov` exited 0; output ended at `100%`.
- **Task 2 RED mutations:** Each exited 1 with its intended test failing: zsh-gone revert, Ghostty drift row, resolver-move conflict sweep, and unreadable-target sweep. All mutations were restored.
- **Task 2 GREEN:** `uv run pytest tests/test_terminal_shell.py tests/test_version_status.py tests/test_terminal_keys.py -n auto -q --no-cov` exited 0; output ended at `100%`.
- **Final `make validate`:** Exit 0; lint, format, typecheck, security, dead-code, and shellcheck all passed.
- **Final `make test`:** Exit 0; `8195 passed, 6 skipped in 60.37s`; coverage `96.31%`, above the 90% requirement.
- Local Python was **3.12.12**. Python 3.15 is left to CI.

## Decisions recorded

- **30 D-09:** Shell and keys use the same Ghostty config resolver and path-bound created-file proof.
- **Review H5:** An unscannable earlier default file blocks the shell region and produces a partial warning.
- **Review M4:** The zsh-gone revert walks every default Ghostty file.
- **Review M2 and round 3 M3:** Conflict paths use the same all-file strip walk; the non-target sweep runs before reading the target, so target failure cannot prevent cleanup elsewhere.
- **Checker advisory 8:** Removal uses the generic terminal-keys dispatch; no Ghostty-specific application branch was added.
- **SPEC R2 unclassified edge:** Treated as an already-running Ghostty retaining its old shell. Reload semantics remain unverified; restart Ghostty if the old shell persists.

## Provisional decisions (need confirmation)

30 D-08 with orchestrator decision 2: the Linux shell region sits at the top of the file and no region is written when a user command sits in ANY default Ghostty file outside our regions (ghostty: partial: you already set command); needs confirmation

30 D-10: a user config-file include is not followed; the region is written anyway with ghostty: partial: you include other files (config-file); they are not followed; needs confirmation

30 D-03: needs owner confirmation.

30 D-17: needs owner confirmation.

SPEC R4 amendment following 28 D-06: needs owner confirmation.

## Narrowings of locked decisions

30 D-08 narrowed by orchestrator decision 2 and review H5: a user command in any default Ghostty file, or an unscannable file loaded before the target, means no shell region and a ghostty: partial: reason

## Deviations and cleanup

The first commit hook found line-length and formatting violations. They were corrected, the failing gates were rerun, and the commit hook passed. The pre-existing untracked goals file was left untouched. Every run directory created for these commands was removed by its exit trap.

## Orchestrator verification

Checked 2026-11-20 21:00 by the orchestrator, independently of the executor's report (pi, router-env/my-coding, 20:47:50 to 20:55:28, exit 0; no BLOCKED claim).

- Commits since `62a693e7`: `523cfd1a`, `6c0c0ba7`; each passed the commit hook. Plan verifies 1 and 2 re-run by the orchestrator (`run_plan_verifies.py 30-04`): both exit 0. `make test` re-run by the orchestrator on the committed tree: exit 0, 8195 passed, 6 skipped, coverage 96.31%.
- Production diff read: `_sync_ghostty` writes `command = <zsh -l>` at the top of the resolved file only when no default file holds a user `command` and none that loads before the target is unscannable; a user `command` or `config-file` adds the named `ghostty: partial:` lines; `_strip_ghostty_regions` walks every default file (owned region only, dry-run aware) and is shared by the zsh-gone revert and by the conflict and blocked paths, running before the target is read so an unreadable target cannot skip it.
- The generic removal dispatch (`TERMINAL_KEYS.get(tool.id)` in `installer/app.py`) covers Ghostty; `installer/app.py` has no Ghostty-specific code.

ghostty-container: not run

No container, GUI, or real Ghostty execution was performed; live reload behavior remains unverified.
