# Phase 30 Review Fix

Three pi runs on router-env/my-coding (22:27 to 22:44), reports of each part below, then the orchestrator's verification.

## Part 1

| ID | Status | Commit SHA | Note |
|---|---|---|---|
| WR-01 | blocked | `b0933169` (reverted by `88c75006`) | Pre-phase-30 tests require missing script leaves to remain broken; the requested rule would change those assertions. |
| Lane review #2 | fixed | `adbeed31` | macOS keys report unfollowed includes; Linux keys do not duplicate the shell warning. |
| Security audit: chord prefixes | fixed | `9ade6530` | Chord matching recognizes `physical:` and `unicode:` key prefixes. |

### Verification tails

- **Targeted tests:** completed at 100%, exit 0.
- **`make validate`:** all six gates passed, exit 0.
- **`make test`:** `8265 passed, 6 skipped in 65.68s`; coverage 96.31%, exit 0.

### Deviation and remaining risk

The first full test run failed on `tests/test_app.py::test_an_interrupt_after_the_vendor_remove_keeps_the_receipt` and `tests/test_version_status.py::test_an_interrupted_recipe_removal_is_never_removable_on_the_next_pass`. Both predate phase 30 and pin missing leaves as broken, so WR-01 was reverted without editing their assertions. Deleted Ghostty menu leaves can therefore still strand removal and updates.

No other review items were changed. Owned scratch directories were removed.

## Part 2

| Item | Status | Commit | Note |
|---|---|---|---|
| WR-03 | fixed | `2e729f97` | Directory snapshots now detect newly created directories left after removal. |
| Lane review #4 | fixed | `2e729f97` | A failed `/tmp` inspection produces a removal failure; name filtering remains narrowed. |
| IN-03 | fixed | `2e729f97` | Cleanup `CommandError` becomes a removal failure line. |
| IN-04 | fixed | `b6640b11` | Corrected test names and the `_perform` docstring in `installer/engine.py`. |
| IN-05 | fixed | `b6640b11` | Registry proof names the command and result without the ignored transcript path. |
| IN-01 | fixed | `b6640b11` | Engine test documents and asserts the stub’s nonfatal menu warning. |

**Targeted tests:** Requested seven-file pytest command exited 0; output ended at `100%`.

**Final gates:**
- `make validate`: all six gates passed.
- `make test`: `8268 passed, 6 skipped`; coverage `96.31%`.

**Deviations:** The `_perform` docstring is in `installer/engine.py`, not `installer/download.py`. No container or real Ghostty run was performed. Owned scratch directories were removed; the ignored `.coverage` file remains because its prior ownership was not established.

## Part 3

| ID | Status | Commit | Note |
|---|---|---|---|
| WR-01 | fixed | `e2d9b5da` | Missing menu leaves no longer void removal proof; missing executable leaves and wrong-type menu paths remain drift. |

**Targeted tests:** Passed, exit 0.

**`make validate`:** All six gates passed, exit 0.

**`make test`:** 8273 passed, 6 skipped; coverage 96.31%, exit 0.

**Deviation:** The fix also changes `installer/uninstall.py` so removal plans omit already-missing paths and can retire the receipt. The first commit attempt failed on an overlong comment; the corrected commit passed all hooks.

Scratch directories and the generated coverage file were removed. Python 3.15 was not tested locally.

## Orchestrator verification

Checked 2026-11-20 22:55 by the orchestrator.

- Commits since `e943090f`: `b0933169` (reverted by `88c75006`: it skipped every missing leaf and broke two older tests that pin a missing script leaf as broken), `adbeed31`, `9ade6530`, `2e729f97`, `b6640b11`, `e2d9b5da`; each passed the commit hook. Part 3 narrows the WR-01 fix to menu files (a `.desktop` under `applications` or a `.png` under `icons/hicolor`, under the user's data home) and also lets the removal plan omit already-missing paths; the two older tests pass unchanged.
- `make test` re-run by the orchestrator on the final tree: exit 0, 8273 passed, 6 skipped, coverage 96.31%. The first run failed once on `tests/test_execute_screen.py::test_update_marker_establishes_the_silence_indicator` (a TUI timing flake: it passes alone and in the rerun). The touched test files also pass under Python 3.15 (`uv run --python 3.15 --isolated`).
