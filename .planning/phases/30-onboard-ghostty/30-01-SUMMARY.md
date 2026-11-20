# Phase 30 Plan 01 Summary

- **Task 1 — catalog tracer:** committed as `6b7fb319`.
  - RED: the new Ghostty tests and catalog pins failed because the entry did not exist.
  - GREEN: targeted six-file pytest command exited 0, reaching `[100%]`.
- **Task 2 — loader validation and checksum guards:** committed as `6748eee2`.
  - RED: invalid archive, note and desktop values were accepted; the checksum-mismatch guards passed.
  - GREEN: targeted four-file pytest command exited 0, reaching `[100%]`.

## Final gates

- `make validate`: **passed** — lint, format-check, typecheck, security, dead-code and shellcheck.
- `make test`: **failed** — `1 failed, 8081 passed, 6 skipped`; coverage was 96.27%, above the 90% requirement.
- The failing doctor test passed in isolation. It was not established whether the failure is related to this change.

## Existing test pins edited

- `tests/test_registry.py:281,304,1215,1270` — added Ghostty to the human-tool set and updated audience, catalog and tier counts.
- `tests/test_registry.py` owner-probe table — added Ghostty’s pacman probe and updated the row-count comment.
- `tests/test_resolve.py` four `_FIRST_METHOD` tables — added Ghostty’s cask or tarball route for each fixture.

## Decisions and deviations

- D-01, D-02, D-04 and D-05: one Ghostty entry, the specified pins and platform routes, and the community-build label and download note.
- D-06: no `smoke_argv`; the default `--version` is used.
- Orchestrator decision 1: `desktop` is the only new desktop-related method key; menu placement is deferred to plan 30-02.
- Orchestrator decision 5: rebuild tags such as `v1.4.0+1` require a manual pin edit.
- Orchestrator decision 6: plan 30-05 uses `fedora:latest` for the container target.
- Orchestrator decision 7: phases 27–29 are prerequisites already present; no prerequisite work was added.
- The skill table’s shell and clear cells remain `planned (phase 30)`.
- Review decision L1: the registry comment describes menu placement and shortcut removal as planned work.
- Both commits passed their hooks after formatting and lint corrections.
- Every test run directory was removed by its exit trap. The pre-existing untracked goals file was left untouched.

## Provisional decisions (need confirmation)

30 D-03: macOS cask with --appdir into ~/Applications, no CLI link promised (cask has no binary stanza; SKILL-04 platform gap); needs confirmation

30 D-08: a user `command` in any default file writes no shell region; needs confirmation.

30 D-10: included config files are not followed; write with a partial warning; needs confirmation.

30 D-17: residue verification is scoped to installer-owned temporary files; needs confirmation.

SPEC R4 amendment: a region deleted after a recorded install stays deleted and quiet, following 28 D-06; needs confirmation.

## Orchestrator verification

Checked 2026-11-20 20:25 by the orchestrator, independently of the executor's report (pi, router-env/my-coding, 20:12:06 to 20:20:18, exit 0).

- The executor's first line was `BLOCKED: make test failed in tests/test_doctor.py::test_run_doctor_reports_broken_links_and_changes_nothing`. The orchestrator re-ran the full suite on the committed tree: `make test` exit 0, 8082 passed, 6 skipped, coverage 96.27%. The one failure was a flake (the test passes alone and in the full run; another session writes to `~/.local/bin` on this host), so the BLOCKED line is dropped. Executors keep the rule to run `make test` once more before reporting a failure.
- Commits since `63ffc8a1`: `6b7fb319`, `6748eee2`; each passed the commit hook. Plan verifies 1 and 2 re-run by the orchestrator (`run_plan_verifies.py 30-01`): both exit 0.
- Production diff read: the ghostty registry entry with both pins as in D-02, `raw`, `note` and `desktop` on `tarball` with their loader checks (note one plain line, desktop id without consecutive dots and only with `raw = true`), the engine surfacing a method note, the skill table row with `planned (phase 30)` cells.
- Existing test edits read: only the listed pins (human-tool set and counts, owner-probe table, the four `_FIRST_METHOD` tables).

ghostty-container: not run

Python 3.12 was used locally; Python 3.15 is reserved for CI. No real Ghostty AppImage, container, GUI or live pin verification was run.
