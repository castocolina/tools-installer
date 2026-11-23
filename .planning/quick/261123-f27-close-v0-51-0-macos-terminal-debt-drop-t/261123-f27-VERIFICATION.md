---
phase: quick-261123-f27
verified: 2026-11-23T00:00:00Z
status: human_needed
score: 7/7 must-haves verified
covered_files:
  - .planning/quick/261123-f27-close-v0-51-0-macos-terminal-debt-drop-t/261123-f27-PLAN.md
  - .planning/quick/261123-f27-close-v0-51-0-macos-terminal-debt-drop-t/261123-f27-SUMMARY.md
  - installer/executors.py
  - installer/iterm2_profile.py
  - installer/terminal_keys.py
  - installer/terminal_regions.py
covered_digest: "v4:sha256:0392efafe45c1fea05abfbf37bf090eab391ae79fecf03891cb3e3dc91b23090"
behavior_unverified: 0
human_verification:
  - test: "iTerm2 reinstall with a stale Caskroom entry (Caskroom lists iterm2, iTerm.app gone)"
    expected: "Run restores the bundle via brew reinstall or fails naming iTerm.app; no profile or default written while absent"
    why_human: "Needs real brew and a real Mac; agents must not touch the host"
  - test: "WezTerm config that disables SUPER k, then a sync"
    expected: "A `wezterm: partial:` line naming SUPER+k and DisableDefaultAssignment"
    why_human: "Needs the owner's Mac and real wezterm"
  - test: "Pre-change iTerm2 install on an Intel Mac, then reconfigure"
    expected: "Cmd+K row dropped from the profile; iTerm2's own Cmd+K still clears"
    why_human: "Real iTerm2 behavior"
---

# Quick 261123-f27 Verification Report

**Goal:** Close the v0.51.0 macOS terminal debt (A1-A4) and lift the tool-onboarding skill (B).
**Status:** human_needed (all code-checkable truths verified; owner Mac checks deferred)

## Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Fresh iTerm2 profile has no Cmd+K row, no Ctrl+L claim (A1) | VERIFIED | `OWN_ROWS` in installer/iterm2_profile.py; no Cmd+K Ctrl+L claim left in terminal_keys.py (remaining Ctrl+L lines are other terminals); iterm2 `clear="Clear Buffer"` |
| 2 | Pre-change profile reads as drift, reconfigure rewrites, uninstall still works | VERIFIED | `RETIRED_ROWS` and `without_retired_rows` on the render path; legacy tests in tests/test_iterm2_row.py pass |
| 3 | Absent cask bundle: one reinstall, else ExecutorError, no receipt/post-install (A2) | VERIFIED | `_cask` and `_cask_bundle_present` in installer/executors.py use `locations.app_roots()`, shared with status.py; engine and executor tests pass |
| 4 | Disabled/unlisted WezTerm chord gives `wezterm: partial:` line (A3) | VERIFIED | `wezterm_disabled_chords` in terminal_regions.py, called from `_wezterm_plan` and readback; tests pass |
| 5 | apps.py quarantine docstring corrected (A4) | VERIFIED | installer/apps.py lines 8-10 |
| 6 | Skill has evals, references split, gap word, vendor iTerm2 cell, description (B) | VERIFIED | reference file with `gap (backlog 999.38)` and `vendor` iTerm2 cell; 3 eval ids; 20 trigger queries (10 positive); description 982 chars, no `catalog-audit`; SKILL.md 27220 bytes (<28500, was 34385); SKILL.md has no terminal table rows (the 4 remaining table rows are removal-param tables) |
| 7 | Skill tests green; 27-SKILLJUDGE files untouched | VERIFIED | 13 targeted test files pass (`-n 4`, no failures); `git log 9f0b58dc..HEAD -- 27-SKILLJUDGE*` is empty |

Skill-judge score (82.4, 84.0, 82.4 percent, orchestrator-run) is reported by the caller and was not re-run here.

## Notes

- Commits 3021f942, 23a167f1, f91947b4, 8003a562 plus the orchestrator's 5ea5ccb4, f77d66fd, 2fa23dfe, d6ab210c are on the branch.
- SUMMARY says no Co-Authored-By trailer was added (deviation 2); a style point, not a goal gap.
- Known host failures in tests/test_setup.py and tests/test_app.py were not run and are not this task's.

## Human verification required

The three owner-Mac checks in the frontmatter are deferred and must not be counted as passed.
