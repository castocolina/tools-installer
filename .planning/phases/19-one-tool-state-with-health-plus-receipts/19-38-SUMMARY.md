---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "38"
subsystem: persistence
tags: [python, receipts, symlinks, removal-safety]
requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: receipt-backed artifact fingerprinting and quarantined removal
provides:
  - Symlink-contained directory key-file proof
  - Regression coverage for escaping and internal symlinks, loops, and quarantined replacement trees
affects: [phase-19-receipts, uninstall-safety]
actuals:
  tokens: 1400
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns: [strict resolve-and-contain validation for receipt directory keys]
key-files:
  created: []
  modified:
    - installer/receipts.py
    - tests/test_receipts.py
    - tests/test_uninstall.py
    - .claude/architecture.md
    - tests/test_docs.py
key-decisions:
  - "Directory keys must resolve inside the artifact root; strict resolution fails closed for dangling paths and symlink loops."
  - "The same matcher enforces containment during both preview and quarantine re-check."
patterns-established:
  - "Resolve symlinked paths strictly and require containment before using a path as removal proof."
requirements-completed: [STATE-03]
duration: 30min
completed: 2026-10-17
status: complete
coverage:
  - id: D1
    description: Directory key files prove an artifact only when the resolved path remains inside that artifact directory.
    requirement: STATE-03
    verification:
      - kind: unit
        ref: tests/test_receipts.py#test_key_through_an_escaping_symlink_is_no_proof
        status: pass
      - kind: unit
        ref: tests/test_receipts.py#test_key_through_a_symlink_that_stays_inside_still_proves
        status: pass
      - kind: unit
        ref: tests/test_receipts.py#test_key_through_a_symlink_loop_never_raises
        status: pass
    human_judgment: false
  - id: D2
    description: A replacement app whose key escapes to a backup tree is refused during planning and quarantine deletion.
    requirement: STATE-03
    verification:
      - kind: unit
        ref: tests/test_uninstall.py#test_remove_paths_refuses_a_replacement_keyed_through_an_escaping_symlink
        status: pass
      - kind: unit
        ref: tests/test_uninstall.py#test_plan_removal_never_proves_a_dir_whose_key_escapes
        status: pass
    human_judgment: false
---

# Phase 19 Plan 38 Summary

**Receipt directory keys are now strict-resolved within the directory they authorize, including during quarantine re-checks.**

## Performance

- **Duration:** approximately 30 minutes
- **Tasks:** 2
- **Files modified:** 5

## Task Commits

1. **Task 1: directory key containment and receipt regressions** - `ca63624` (`fix(19-38): a dir key file proves only the directory it resolves inside`)
2. **Task 2: replacement-tree removal regression and architecture record** - `7143125` (`test(19-38): a replacement tree keyed through an escaping symlink is never deleted`)
3. **Plan summary** - committed separately after verification.

## Accomplishments

- Added `_key_file` to require strict resolution of a directory key beneath the artifact directory. Internal symlinks remain valid; escaping, dangling, and looping paths fail closed.
- Routed both `fingerprint` and `matches` through the containment check, securing ordinary proof and the existing quarantine re-check without changing `uninstall.py`.
- Added absolute and relative escape regressions, an internal-symlink positive case, and loop/dangling cases.
- Added end-to-end replacement-tree protection tests for removal planning and quarantine deletion.
- Recorded the containment rule in `.claude/architecture.md` and anchored the record in `tests/test_docs.py`.

## TDD RED Evidence

- Task 1: `uv run pytest tests/test_receipts.py -q --no-cov -k "escaping_symlink or stays_inside or symlink_loop"` — **2 failed, 2 passed**. Both `[absolute]` and `[relative]` escape cases unexpectedly fingerprinted the external `Info.plist` as a directory key.
- Task 2: `uv run pytest tests/test_uninstall.py tests/test_docs.py -q --no-cov -k "escaping_symlink or key_escapes or phase_19_mechanisms"` — **1 failed, 2 passed**. The new regression tests passed with Task 1's containment fix; the documentation anchor failed because the architecture record was not yet added.

## Verification

- Task 1 receipt suite: `uv run pytest tests/test_receipts.py -q --no-cov` — passed (108 tests).
- Task 2 touched suites: `uv run pytest tests/test_uninstall.py tests/test_docs.py -q --no-cov` — passed (121 tests).
- Targeted uninstall regressions: `uv run pytest tests/test_uninstall.py -q --no-cov -k "escaping_symlink or key_escapes"` — 2 passed.
- `make validate` — passed (ruff, format, pyright, bandit, vulture, shellcheck).
- `make test` — passed: **4618 passed, 4 skipped**, coverage **95.97%**.
- `git diff --check` — passed.
- Acceptance checks: `_key_file` definition count 1, total occurrences 3, RR3-01 references ≥2, no direct directory-key joins, one architecture phrase plus one matching docs assertion, and one `_escape_after_final_check` helper.
- Shrink guards passed. Large-file line counts: `installer/receipts.py` 639 (HEAD 613), `tests/test_receipts.py` 1280 (HEAD 1220), `tests/test_uninstall.py` 2488 (HEAD 2430), `.claude/architecture.md` 1111 (HEAD 1108). Diff stat: 5 files changed, 162 insertions, 14 deletions.

## Deviations from the Plan

None. `ruff format` was applied to the test additions after `make validate` identified formatting issues; this remained within the planned files and was committed with Task 1.

## Issues Encountered

- First `make validate` reported two line-length violations; corrected them. The next check requested formatter output; `ruff format` was run, then validation and tests passed.
- The Task 2 commit initially rejected `.claude/architecture.md` as ignored; explicitly staged that planned file with `git add -f` and committed it. No ignore configuration changed.
- Final fresh-review subagent dispatch was attempted, but the available reviewer models were ambiguous/unavailable in this session. I performed a self-review of the focused diff, checking the containment path in both call sites and the rename/re-check regression; no issues were found. This is weaker than an independent review.

## Next Phase Readiness

The directory-key proof now rejects key paths that escape through intermediate symlinks and the deletion-time quarantine path inherits the same check. No known blocker for follow-on receipt/removal work.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
