---
created: 2026-11-08
source: Phase 23.2 (plan 05 deferred issue, UAT O-7/O-8, security residuals R1-R4)
priority: low
---

# Small Phase 23.2 follow-ups

## Problem

- `.claude/skills/tool-onboarding/SKILL.md` step 4b still says per-method removal "does not exist yet";
  `installer/uninstall.py` has `plan_removal` / `remove_proven` now (23.2-05 deferred issue).
- UAT O-7: at 80x20 the first lines of the claude settings block scroll out of the run summary.
- UAT O-8: claude reads `owner unknown` after its native install in the container.
- Security R1: a BOM-only or U+00A0-only settings file reverts to `BOM{}`/`{}` instead of its exact bytes.
- Security R2: the test session's real-HOME fingerprint does not watch `~/.copilot`.
- Security R3: volta's "export lines only" rc behaviour is upstream-read, not pinned by a test.

## Solution

Fix the skill text with a skill-judge re-score; look at the summary block layout at 80x20; check claude's
native-install ownership probe; extend the blank-file rule to any whitespace-only text; add `~/.copilot` to
`tests/home_fingerprint.py` (watch-list only, a widening of what is watched, not of what is allowed); pin
volta's installer flags or add a note test.
