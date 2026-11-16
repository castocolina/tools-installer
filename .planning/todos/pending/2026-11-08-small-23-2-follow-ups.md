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

## Status (2026-11-16)

Triage at b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`), verdict partial.

- Done:
  - Skill text: 0fcea8d3 rewrote SKILL.md step 4b to L1/L2/L3 removal, with skill-judge run before and after (`24-SKILL-JUDGE.md`).
  - O-8: bc3a0e49 fixed it, and 24-UAT test 2 passes.
- Left:
  - R1: `installer/agent_settings.py:979` uses `bytes.strip()`, which keeps a BOM or U+00A0, and the test at `tests/test_agent_settings.py:477` covers ASCII whitespace only.
  - R2: no `~/.copilot` in `tests/home_fingerprint.py`.
  - R3: no volta flag pin or note test.
  - O-7: the agent settings block in the 80x20 run summary. a8c37dc2 fixed other 80x20 views, not this one.
