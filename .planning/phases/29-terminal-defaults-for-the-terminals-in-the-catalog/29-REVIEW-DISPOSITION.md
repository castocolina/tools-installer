# Phase 29 Review Disposition

Orchestrator triage of the three read-only gates run on 2026-11-20 (internal deep reviewer `29-REVIEW.md`, security auditor `29-SECURITY.md`, external lane `opencode-referee-one`, 3 minutes, exit 0). Every item was judged against source; kitty items were also checked against the installed kitty (`load_config`).

## Security audit

SECURED, 25 of 25 threats closed, `threats_open: 0`. Non-blocking notes: the Konsole action regex (fixed, S1), three plan-named tests that did not exist (added, T1 to T3).

## Fixed in the review fix round (`29-REVIEW-FIX.md`)

| Source | Finding | Verification by the orchestrator | Item |
| ------ | ------- | -------------------------------- | ---- |
| Lane 1 | `clear_all_shortcuts yes` then `no` still clears every installed map | Real kitty `load_config`: `yes` then `no` leaves 0 maps, `yes` alone 0, `yes` before a map keeps it | K1 |
| Lane 2, WR-03 | `include` path is the rest of the line (spaces) and `KITTY_OS` expands; option values `--allow-fallback` and `--timeout`; `return` is `enter` | Read against the scan code and kitty's parser (the reviewer compared with kitty v0.49.2 source) | K2, K3 |
| WR-04 | A symlink loop in an include raises `RuntimeError` on Python 3.11/3.12 and crashes the install | Python's `Path.resolve()` behavior by version; the project supports `>=3.11` | K4 |
| Security note | `_KONSOLE_ACTION` backtracks quadratically (0.35 s at 80 KB) | Auditor measurement | S1 |
| WR-05 | The Konsole unknown state is not pinned by any test (one test never asserts `notes == ()`, one uses an ASCII string for the decode case) | Read the tests | W5 |
| WR-02, IN-06, IN-02 | herdr driver: fixed sleep and no `START` check (FAILED instead of UNPROVEN), `execve` failure continues in the parent, scratch dir never removed, literal backslash-n join | Read the driver | H1 to H3 |
| Security notes, IN-05 | Missing tests named by the plan (kitty resolver drift, WezTerm seed/edited strip, herdr child environment); weak tests | Read the tests | T1 to T4 |

## Rejected or accepted, with reason

| Source | Finding | Disposition |
| ------ | ------- | ----------- |
| Lane 3 | Changing the resolved config path between two applies overwrites the first created-file record | Accepted limit. The first file is no longer the one the terminal reads, so its region is inactive; no user data is lost and the second file is cleaned up. Tracking every created path is a design change for a rare environment edit. Revisit if a user hits it. |
| Lane 4 | The Konsole report is skipped when zsh is unavailable | By design (29 D-09, provisional): the warning is attached to the zsh row, which exists only when zsh does. A host with Konsole and no zsh has no shell tuning to report on. |
| Lane 5 | A missing `wezterm` executable gives no "could not verify" note | Rejected. The plan's note covers a non-zero exit, unparsable output and a missing chord; without the executable nothing was read back and the success line never claims it was. A note on every such host would be noise. |
| WR-01 | The herdr slicing by expected length blames later chords when one is lost | Accepted, diagnostic only: the verdict stays non-pass. A `# shortcut:` comment records the limit (H1). |
| IN-01 | The Konsole removal warning reaches the zsh row as a misconfiguration with no step | Planned routing; carried to the owner confirmation list with 29 D-09. |
| IN-03 | The top-of-file kitty region pushes a `# vim:` modeline out of the first five lines | Accepted: the position is the locked 29 D-01 design (user maps after it win). |
| IN-04 | `Placement` couples the generic region helper to the WezTerm skeleton | Accepted; a refactor with no behavior change, not worth a fix round. |
