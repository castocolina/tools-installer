---
status: complete
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
source: [16-VERIFICATION.md]
started: 2026-10-10T19:45:00Z
updated: 2026-10-10T23:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Alacritty row styling
expected: Open the catalog (`uv run python setup.py`), User view, move the cursor off
  alacritty and look at it. The row renders dim (SGR dim) with
  `(not available: immutable host)`.
evidence so far: 16-UI-CHECK.md row 4 (text, no `[ ]` box, detail sentence) passed via
  `tmux capture-pane`. Dim SGR is code-only (`_row_cells`); a plain-text capture cannot
  assert it and the cursor highlight overrides it on the focused row.
result: passed
  note: tmux capture -e (2026-10-10, real host): alacritty row id/category/audience/Inst/desc carry fg 38;2;161;161;161 (Textual's blended `dim`, not SGR 2), no bold; kitty/wezterm rows carry bold id and coloured audience/Inst; text ends `(not available: immutable host)`. rc checksums identical.

### 2. Execute-screen enter on a real host
expected: Select a current tool (e.g. wezterm), open the execute screen, read the on-mount
  preflight, then press enter. Preflight says `wezterm already current — nothing to do.`;
  enter completes without `Install 0 tools` and without rewriting rc files unexpectedly.
evidence so far: preflight text proven by the Textual pilot test
  `test_current_only_selection_says_already_current_not_install_zero`
  (tests/test_execute_screen.py), which passes in the full suite (3458 passed). Enter was
  deliberately not pressed on the real host (it runs `configure_path` against real rc files,
  ONESHOT Rule 5); only the live-host enter path is unobserved.
result: skipped
reason: Deferred follow-up: user chose on 2026-10-10 to close Phase 16 without this live check ("hagamos merge local el complete phase y push"); not observed, not passed.

### 3. Real-machine day-to-day pass (puppeteer live case)
expected: Use the catalog and Doctor for a normal session on a host that has a dangling pnpm
  shim (puppeteer on this host currently reads `!`). Rows keep telling the truth under real
  use: no silent `u`, no false `broken`, Doctor guard offers only lines it can safely rewrite.
evidence so far: headless host proof and tmux rows 1-4, 6, 7 pass; rc-file sha256 identical
  before and after (16-UI-CHECK.md). The mmdc dangling-shim repro no longer exists on this
  host, so D-18 is fixture-proven; puppeteer is a live true positive.
result: skipped
reason: Deferred follow-up: user chose on 2026-10-10 to close Phase 16 without this live check ("hagamos merge local el complete phase y push"); not observed, not passed.

### 4. Review of the 11 judgment-tier plan prohibitions
expected: Read the Prohibitions table in 16-VERIFICATION.md and agree each must-NOT held
  (16-01 no location-only ownership; 16-02 no download-capable command and no
  registry-supplied argv; 16-03 no guarded line reported as writer; 16-05 no manager
  migration; 16-08 no deleted foreign line, no edit inside another tool's block, no write
  without byte-exact backup; 16-10 no GUI launch from the worker; 16-11 at most one file per
  confirmation; 16-13 no re-proposed declined post-install). The verifier found no violation,
  including after the 16-17/16-18/16-19 edits; its verdict is non-authoritative.
evidence so far: verifier read of the code and tests; none of these has a fail-first test.
result: skipped
reason: Deferred follow-up: user chose on 2026-10-10 to close Phase 16 without this live check ("hagamos merge local el complete phase y push"); not observed, not passed.

## Summary

total: 4
passed: 1
issues: 0
pending: 0
skipped: 3
blocked: 0

## Notes

2026-10-10 real-host audit (outside the 4 tests): two real defects found and fixed in 9050446 with fail-first tests (base tier never re-derived on entry, so Owner stayed blank after an install from another tier; no catalog re-read presence after Uninstall, so removed tools kept their check mark), plus script-kind removal wording. Platform gaps routed to backlog 999.2 (script-install removal), 999.3 (per-OS/arch artifacts), 999.4 (terminal SHELL env / re-sync on "already").

## Gaps
