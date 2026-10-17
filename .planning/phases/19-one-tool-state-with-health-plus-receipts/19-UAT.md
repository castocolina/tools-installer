---
status: complete
phase: 19-one-tool-state-with-health-plus-receipts
source: [19-01-SUMMARY.md, 19-02-SUMMARY.md, 19-03-SUMMARY.md, 19-04-SUMMARY.md, 19-05-SUMMARY.md, 19-06-SUMMARY.md, 19-07-SUMMARY.md, 19-08-SUMMARY.md, 19-09-SUMMARY.md, 19-10-SUMMARY.md, 19-11-SUMMARY.md, 19-12-SUMMARY.md, 19-13-SUMMARY.md, 19-14-SUMMARY.md, 19-15-SUMMARY.md, 19-16-SUMMARY.md, 19-17-SUMMARY.md, 19-18-SUMMARY.md, 19-19-SUMMARY.md, 19-20-SUMMARY.md, 19-21-SUMMARY.md, 19-22-SUMMARY.md, 19-23-SUMMARY.md, 19-24-SUMMARY.md, 19-25-SUMMARY.md, 19-26-SUMMARY.md, 19-27-SUMMARY.md, 19-28-SUMMARY.md, 19-29-SUMMARY.md, 19-30-SUMMARY.md, 19-31-SUMMARY.md, 19-32-SUMMARY.md, 19-33-SUMMARY.md, 19-34-SUMMARY.md, 19-35-SUMMARY.md, 19-36-SUMMARY.md, 19-37-SUMMARY.md, 19-38-SUMMARY.md, 19-39-SUMMARY.md, 19-40-SUMMARY.md, 19-41-SUMMARY.md, 19-42-SUMMARY.md, 19-43-SUMMARY.md, 19-44-SUMMARY.md, 19-45-SUMMARY.md, 19-46-SUMMARY.md]
started: 2026-10-17T09:44:18Z
updated: 2026-10-17T09:44:18Z
---

<!-- Autonomous run (playbook .planning/goals/2026-10-14-v0.50.0-phases-17-25.md: "never pause for UAT"):
     tests are derived from 19-VERIFICATION.md (11 truths), the 19-SPEC.md acceptance criteria and the 19-NN-SUMMARY
     files. Each was resolved by the orchestrator against HEAD 9408db7 (code = d49e7b2) with the evidence named in
     `evidence:`; nothing was answered on the user's behalf. The gsd-verifier re-ran the named tests at d49e7b2
     (make test 4641 passed / 4 skipped; CI 39019413698 green on ubuntu + macOS). The TUI check ran the real
     `uv run --isolated --no-dev setup.py` in tmux at 80x20 with NO_COLOR=1 and a scratch HOME (navigation only:
     Escape on the first-run layout dialog, tier keys 1-3, Down; no install/uninstall/repair key). Items only a human
     on the real machine can do are `skipped` with a reason and stay under human_verification in 19-VERIFICATION.md. -->

## Current Test

[testing complete]

## Tests

### 1. One health per tool with stated precedence; an overtaken pass publishes nothing
expected: tool_health returns one Health with its reasons for every present/absent/available combination, broken wins over outdated; a pass overtaken by a newer pass or an invalidate publishes no state.
result: pass
evidence: verifier truth 1 — test_broken_and_outdated_is_broken_with_both_reasons, test_overtaken_pass_publishes_nothing, test_overtaken_by_invalidate_publishes_nothing passed at d49e7b2

### 2. Every mark on every tier, legend and focused-row detail at 80x20 without colour
expected: system/user/ai tiers show the health column; ✓ ↑ ≈ ! ○ … – are distinguishable without colour; the 3-line legend and the focused row's reason line are visible at 80x20.
result: pass
evidence: tmux 80x20 NO_COLOR=1 capture — tier 1 shows ○ (colima, docker), ✓ (volta 2.0.2), ↑ (gradle 9.6.1 -> 9.8.1, Homebrew) with "↑ update available — 9.6.1 -> 9.8.1 available · managed by Homebrew"; tier 2 ✓ claude/codex/cursor-agent with "✓ ok — the active binary at …"; tier 3 ○ skill packs with "○ not installed"; legend "✓ ok · ↑ update · ≈ config · ! broken · ○ missing · … checking · – unavailable" plus the priority and Ver lines on every tier; pilot tests test_every_health_mark_renders_on_every_tier[*], test_legend_lines_fit_78_cells, test_catalog_tiers_show_all_legend_and_detail_rows_at_80x20 passed

### 3. Every install, update and repair leaves an atomic receipt
expected: download, app, script and manager kinds write receipts/<id>.json after success; a failed update keeps the old receipt; a crash before the receipt leaves none; a changed link target makes the tool broken and not removable.
result: pass
evidence: verifier truth 3 tests passed; make e2e on d49e7b2: TRACER_RECEIPT_OK tool=yq after PASS1 installed=74 failed=0 manual_required=8

### 4. Ownership is truthful for uv, Volta, shims, ~/.local/bin, host_setup and native owners
expected: one native probe per pass; the redirect shim is looked through; brew appearing mid-session makes colima installable.
result: pass
evidence: verifier truth 4 tests passed; tmux capture shows gradle owned by Homebrew and volta resolved present

### 5. Skill packs show partial and duplicate installs per harness
expected: a pack missing on a present harness is ≈ misconfigured with the harness named; Claude duplicates reach the state; an absent harness gives no partial.
result: pass
evidence: verifier truth 5 tests passed

### 6. One remover for --yes and the TUI, re-proved at deletion time
expected: remove_proven is the only remover; it re-proves each artifact at deletion time; unproven matches are listed "remove it yourself"; a tampered receipt path is never removable.
result: pass
evidence: verifier truth 6 tests passed; make e2e TRACER_RECEIPT_PRE_UNINSTALL_OK, TRACER_UNINSTALL_OK, TRACER_RECEIPT_REMOVAL_OK tool=yq, TRACER_REINSTALL_OK installed=47 failed=0

### 7. Adoption by cached release digest, offline
expected: an installer-layout raw binary whose bytes equal the cached release digest is adopted without network; otherwise "reinstall with r to adopt".
result: pass
evidence: verifier truth 7 tests passed (test_adoption_makes_no_network_call, test_adoption_binds_the_digest_to_the_adopted_bytes)

### 8. Directory proof by key file with quarantine removal (L-19-31)
expected: a dir is proven by the sha256 of one key file inside it; dir drift is unproven, not broken, and never refuses an update; removal renames to a quarantine sibling, re-verifies, puts the tree back on mismatch or interruption, and lists leftovers.
result: pass
evidence: verifier truth 8 tests passed; re-review round 4 (19-REVIEW-4.md, 19-REVIEW-opencode-plan-review-4.md, final check of 19-46) found every round-3 item closed

### 9. Misconfiguration marks only for present tools
expected: ≈ for a missing skill on a present harness, a terminal not on zsh (dry run, HOME byte-identical) and an incomplete pnpm group; nothing for absent tools.
result: pass
evidence: verifier truth 9 tests passed

### 10. Checking before the first pass, never a stale ✓
expected: every row shows … until the first pass answers; a cached present answer is never shown as ✓ while pending.
result: pass
evidence: verifier truth 10 tests passed

### 11. Receipt reads fail closed
expected: corrupt, unreadable, FIFO or deeply nested receipts are no proof and never crash or block; an inaccessible receipts dir is not "no receipt".
result: pass
evidence: verifier truth 11 tests passed

### 12. Host adoption convergence on the real machine
expected: after the version cache refetches on this host, yq/direnv/fx/dasel show "adopted" only on an exact checksum match, otherwise "reinstall with r to adopt".
result: skipped
reason: needs the app against the real HOME, where the refresh pass would write receipts into ~/.local/state; the run never mutates the host. Covered by unit tests (item 7); stays under human_verification in 19-VERIFICATION.md.

## Summary

total: 12
passed: 11
issues: 0
pending: 0
skipped: 1

## Gaps

none
