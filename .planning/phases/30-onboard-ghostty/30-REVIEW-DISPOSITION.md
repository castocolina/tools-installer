# Phase 30 Review Disposition

Orchestrator triage of the read-only gates of 2026-11-20 (internal deep reviewer `30-REVIEW.md`: 0 critical, 3 warnings, 5 info; security auditor `30-SECURITY.md`: SECURED, 19 of 19 threats closed; external lane `opencode-referee-one`: 5 findings, exit 0 in 3 minutes). Every item was judged against source.

## Fixed (`30-REVIEW-FIX.md`)

| Source | Finding | Fix |
| ------ | ------- | --- |
| WR-01 | A deleted menu entry or icon makes the receipt read as drifted: the update gate refuses and uninstall removes nothing, stranding the AppImage | A missing menu leaf (path-told: `.desktop` under `applications`, `.png` under `icons/hicolor`) no longer voids the proof (`e2d9b5da`); the first, broader attempt broke two older tests and was reverted |
| Lane 2 | The keys-only route (macOS) never reports unfollowed `config-file` includes although locked D-10 requires the partial line | The keys plan reports it on macOS; no duplicate on Linux (`adbeed31`) |
| Security note | `physical:` and `unicode:` key prefixes are not normalized, so a user chord could be shadowed | Prefixes are dropped before comparing (`9ade6530`) |
| WR-03, lane 4 (second half), IN-03 | The residue diff skipped empty directories, a failed `/tmp` listing counted as clean, a cleanup `CommandError` left a traceback | Directories are compared, a failed listing is a problem line, the error becomes a `_REMOVE_FAILED` line (`2e729f97`) |
| IN-01, IN-04, IN-05 | A stub-limited engine test, misleading names, a registry comment citing a gitignored transcript | Fixed (`b6640b11`) |

## Rejected or deferred, with reason

| Source | Finding | Disposition |
| ------ | ------- | ----------- |
| Lane 1 | A symlink swapped in the microsecond after the destination check is written through | Accepted limit (the check refuses a symlink immediately before the write; a swap inside that window needs a local attacker in the user's own home); recorded as a `shortcut:` in the code and in 30-02's ledger |
| Lane 3 | After an installer-created Ghostty config becomes empty and the user later adds a legacy `config`, the resolver switches and removal leaves the created file with a mismatch warning | Deferred to backlog 999.30: it needs the user to create a legacy file after the install, and loosening the shared created-file deletion rule (phase 29 threats T-29-23 and T-29-24) in a late fix is not worth the risk |
| WR-02, lane 5 | `_ghostty_plan` scans the process `HOME` and `environ`, not the values passed to `apply_terminal_keys` | Accepted shortcut (documented in 30-03): every production caller passes the process values; changing `KeysRow.plan`'s signature would edit the phase 28 and 29 tests; backlog 999.30 |
| Lane 4 (first half) | The residue check ignores `appimage_extracted_*` leftovers | Provisional decision 30 D-17: the runtime leaves its own files in `/tmp` by design; the assertion covers installer-owned `tools-installer-*` names |
| IN-02 | A reinstall silently overwrites a menu entry the user edited | Accepted: a leaf is proven by path and type; the entry is installer-owned; backlog 999.30 |
