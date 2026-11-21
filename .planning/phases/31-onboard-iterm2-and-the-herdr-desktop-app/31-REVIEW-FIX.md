# Phase 31 Review Fix

Two pi runs on router-env/my-coding (05:27 to 05:34), the reports below, then the orchestrator's verification.

## Part 1

| ID | Status | Commit SHA | Note |
|---|---|---|---|
| I1 | fixed | `1b5a6c5f` | Restore now requires a successful read-back that no longer names the installer GUID. |
| I2 | fixed | `1b5a6c5f` | Reinstall preserves the prior record on capture failure or custom-folder skip. |
| I3 | fixed | `1b5a6c5f` | Tested the real defaults wrapper’s argv, timeout, and absent-key handling. |

### Targeted test tail

`uv run pytest tests/test_iterm2_profile.py tests/test_iterm2_row.py tests/test_terminal_ownership.py tests/test_terminal_keys.py tests/test_version_status.py -n auto -q --no-cov` — **passed**, exit 0.

### Final gate tails

- `make validate` — all six gates passed, exit 0.
- `make test` — **8630 passed, 6 skipped**; coverage 96.27%, exit 0.

### Deviation

Scratch directories created for targeted tests and the commit hook were removed. The final test run left `.coverage` in the checkout; it was retained because its prior existence could not be established. No real iTerm2 installation was tested.

## Part 2

| ID | Status | Commit | Note |
|---|---|---|---|
| K1 | fixed | `af220731` | Reconfigure leaves a recorded deleted or blank keys file untouched; reinstall reseeds it. |
| K2 | fixed | `de812575` | Strip removes a section emptied by removal of the owned key, while preserving user keys. |
| K3 | fixed | `de812575` | Apply and strip preserve and report invalid or unreadable ownership records. |

### Verification tails

- **Targeted tests:** exit 0; final output `.......................... [100%]`.
- **`make validate`:** exit 0; all six static gates passed.
- **`make test`:** exit 0; `8639 passed, 6 skipped`; coverage 96.28%.

### Deviations

The first attempt at the second commit failed its formatting hooks; formatting was corrected and the hooks passed on retry. Scratch directories were removed. The ignored `.coverage` file and `.pytest_cache/` remain because their prior ownership could not be established; the unrelated untracked goal file was left untouched.

## Orchestrator verification

Checked 2026-11-21 05:40 by the orchestrator.

- Commits since `9864227d`: `1b5a6c5f` (restore read back, valid record kept on a failed capture, the real `defaults` wrapper's argv and timeout tested), `af220731` (reconfigure leaves a deleted or blanked herdr-app keys.json alone), `de812575` (strip removes the section it left empty; an unreadable ownership record is reported and preserved); each passed the commit hook.
- `make test` re-run by the orchestrator on the final tree: exit 0, 8639 passed, 6 skipped, coverage 96.28%. The new and touched test files also pass under Python 3.15 (`uv run --python 3.15 --isolated`, CI's version).
