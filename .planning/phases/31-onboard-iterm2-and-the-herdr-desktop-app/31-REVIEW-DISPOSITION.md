# Phase 31 Review Disposition

Orchestrator triage of the read-only gates of 2026-11-21 (internal deep reviewer `31-REVIEW.md`: 0 critical, 4 warnings, 2 info; security auditor `31-SECURITY.md`: SECURED, 21 of 21 threats closed; external lane `opencode-referee-one`: 5 findings, exit 0 in 90 seconds). Every item was judged against source or against the four plan-review cycles recorded in `31-REVIEWS.md`.

## Fixed (`31-REVIEW-FIX.md`)

| Source | Finding | Fix |
| ------ | ------- | --- |
| Lane 1 | A successful `defaults write` or `delete` counted as a confirmed restore without reading the preference back | The restore is confirmed only by a read-back that no longer names the installer GUID (`1b5a6c5f`) |
| Lane 3, WR-04 | A failed preference read on a reinstall overwrote a valid recovery record with a blank one; a reinstall with custom preferences on flipped `default_set` on a kept record | The prior valid record is kept when the capture fails or the custom-folder step is skipped (`1b5a6c5f`) |
| Security note | The real `iterm2_defaults` body was never executed by a test (the autouse stub always replaces it) | A unit test patches `run_output` and asserts the argv, `timeout=20` and the error mapping (`1b5a6c5f`) |
| Lane 4, WR-01 | Reconfigure re-seeded a herdr-app `keys.json` the user deleted or blanked, contradicting 28 D-06 at the file level | A recorded missing or blank file is left alone before the seed on reconfigure; a reinstall still seeds (`af220731`) |
| WR-02 | Strip left `"terminal": {}` when the installer created the section | An emptied section is removed with the key (`de812575`) |
| Lane 5 | An unreadable or malformed ownership record was treated as an empty one | Apply and strip leave the file alone and report one line; the record is kept (`de812575`) |

## Rejected, accepted or deferred, with reason

| Source | Finding | Disposition |
| ------ | ------- | ----------- |
| Lane 2 | With "load preferences from a custom folder" on, the restore guard can be bypassed when the custom preference names the installer profile | By design: the default step is skipped for a custom preferences folder (the installer never writes the default there), so a custom preference naming our profile can only be the user's own choice; recorded in the install note and the UAT list |
| WR-03 | After a keys-path change to an existing file B, the stale created marker bound to the old path A makes strip return early, so B's key can never be stripped | Accepted limit (two accepted choices combine: the 31-01 M1 early return and the single-path ledger); backlog 999.31 |
| IN-01 | A `tool_id == "herdr-app"` special case in the generic owned-keys apply duplicates `row.validate` | Deferred to backlog 999.31 (a tidy-up with no behavior change) |
| IN-02 | `Path.home()` and `HOST_SETTINGS_OS` are used in the removal hook and the herdr-app path instead of the injected values; `before_removal_terminal_keys` has an unused `tool_id` parameter | Accepted shortcut (every production caller passes the process values); backlog 999.31 |
| Security note 3 | Strip deletes the profile file on marker and GUID proof even if the user appended a second profile to it; a symlinked parent directory is not refused | Accepted: the marker and the fixed GUID prove the installer created the file and the file is installer-owned (the install note says edits do not stick); backlog 999.31 |
