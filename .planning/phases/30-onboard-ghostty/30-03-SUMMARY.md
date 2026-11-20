# Phase 30 Plan 03 Summary

## Tasks and commits

- **Task 1 — `25ef173b`:** Added Ghostty config resolution, load-order scanning, chord normalization, and region validation.
  - RED tail: `ImportError: cannot import name 'ghostty_chord'`.
  - GREEN tail: `...................................................................... [100%]`
- **Task 2 — `06832ba0`:** Added the Ghostty keys row, registry declaration, status mapping, skill cell, and multi-file strip support.
  - RED tail: five expected closed-set and missing-field failures.
  - GREEN tail: `............................ [100%]`
  - **Deviation:** The behavioral tests for the row were written after the implementation; only the closed-set tests were observed failing first.
- **Task 3 — `bc83866a`:** Added drift, reconfiguration, removal, and status tests.
  - GREEN tail: `................................................ [100%]`
  - Mutation RED tails: disabling path binding failed the resolver-move guard; removing the sibling region failed both user-byte strip cases; removing `strip_files` failed both multi-file strip cases.

The implementation uses `Placement.TOP`, scans both Linux defaults and all four macOS defaults, refuses an unreadable earlier file, and reports an unreadable later file. Strip walks the default files while keeping created-file deletion bound to the recorded path. Ghostty leaves `validate_on_status` false. Its same-directory behavior is documented as vendor-provided.

## Final gates

`make validate` exited 0:

```text
make lint................................................................Passed
make format-check........................................................Passed
make typecheck...........................................................Passed
make security............................................................Passed
make dead-code...........................................................Passed
make shellcheck..........................................................Passed
```

`make test` exited 0:

```text
Required test coverage of 90.0% reached. Total coverage: 96.29%
8171 passed, 6 skipped in 65.13s
```

The six skips were existing suite results; no skip or xfail markers were added.

## Existing test changes

- `tests/test_terminal_keys.py:255,292`: added Ghostty to the closed row and declarer sets.
- `tests/test_terminal_keys.py:1690`: added Ghostty to the created-path binding pin and renamed the test.
- `tests/test_terminal_keys.py:2142`: added `strip_files` to the exact field pin.
- `tests/test_registry.py:1355`: added Ghostty to reviewed post-install declarers and updated the explanation.

## Provisional decisions (need confirmation)

- 30 D-03: macOS cask and absence of a CLI link need owner confirmation.
- 30 D-08: a user `command` in any default file writes no shell region; needs owner confirmation.
- 30 D-10: do not follow user `config-file` includes; needs owner confirmation.
- 30 D-17: scope the `/tmp` residue check to installer-owned names; needs owner confirmation.
- 30 SPEC R4 (amended 2026-11-20) vs 28 D-06: a Ghostty keys region deleted after a recorded install stays deleted and quiet and a reconfigure does not restore it (28 D-06); the SPEC's "shows apply install tuning" holds for a host with no record and for a changed region; needs confirmation

## Deviations and limits

- Some individually specified resolver and scan cases were not added as separate tests, including the regular-file symlink case and a directory at the earlier legacy path.
- Task 3 combines the Linux and macOS user-byte cleanup cases in one parametrized test rather than providing the separately named macOS test.
- Python 3.12 was tested locally; Python 3.15 remains a CI check.
- Each run directory created by the test-command prelude was removed by its exit trap. Pytest and the final gates used the default `TMPDIR` as instructed.
- The pre-existing untracked goals file was left untouched.

## Orchestrator verification

Checked 2026-11-20 20:55 by the orchestrator, independently of the executor's report (pi, router-env/my-coding, 20:37:19 to 20:47:24, exit 0).

- The executor's first line was `BLOCKED: Task 2's behavioral tests were added after its production implementation`. That is a process deviation, not a defect: the closed-set tests were seen failing first, the behavioral tests exist and pass, and Task 3 recorded three mutation proofs (path binding off, sibling region removed, `strip_files` removed), each failing the guard that covers it. The BLOCKED line is dropped and the deviation is kept in the summary.
- Commits since `6720a111`: `25ef173b`, `06832ba0`, `bc83866a`; each passed the commit hook. Plan verifies 1 to 3 re-run by the orchestrator (`run_plan_verifies.py 30-03`): all exit 0. `make test` re-run by the orchestrator on the committed tree: exit 0, 8171 passed, 6 skipped, coverage 96.29%.
- Goldens read: the Linux created file holds `keybind = ctrl+shift+k=text:\x0c` in the `ghostty-keys` region; the macOS file holds `super+k`; neither writes a global Option or Alt switch; an unscannable earlier file refuses and writes nothing; a recorded deleted region stays quiet and a reconfigure does not restore it (the SPEC R4 amendment); strip walks every default file and keeps created-file deletion bound to the recorded path.
- Open: a few individually specified resolver cases (a regular-file symlink case, a directory at the earlier legacy path) are not separate tests; the behavior sits in the resolver tests that exist.

ghostty-container: not run

Real Ghostty and real-Mac checks were not run. The remaining risk is the incomplete plan-specific test coverage and the Task 2 test-first deviation.
