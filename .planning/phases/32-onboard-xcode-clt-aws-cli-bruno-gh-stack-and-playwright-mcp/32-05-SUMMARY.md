# Phase 32 Plan 05 Summary

## Tasks

- **Task 1 — `382195af`:** Added pinned Playwright MCP host registration, Claude consent handling, Bazzite-gated Chrome export, and reread behavior. The earlier executor’s RED/GREEN output was not available in this split run.
- **Task 2 — `3e1a6531`:** Added the ledger-backed removal sweep. The earlier executor’s RED/GREEN output was not available in this split run.
- **Task 3 — `308ad94a`:** Added the registry entry and tests for its shape, shared pin, drift read, and exact-pin update refusal.
  - RED: 11 failures, including all four new tests failing because the entry was absent and the catalog pins expecting it.
  - GREEN: the specified targeted suite exited 0.
  - The first commit attempt exposed test lint, format, and typing errors; those were corrected, their gates rerun successfully, and the commit hook passed.

## Final verification

- `make validate`: exit 0; lint, format-check, typecheck, security, dead-code, and shellcheck passed.
- `make test`: exit 0; **8943 passed, 6 skipped**, coverage **96.33%** against the 90% requirement.
- Run directories were removed by their traps; the generated coverage file was removed. The pre-existing untracked goals file was left untouched.

## Decisions

Each decision below is **provisional and needs owner confirmation**, except where a locked decision is identified.

- **Hosts:** Claude, Cursor, Copilot, OpenCode, and Codex are targeted when present. Pi is left to the named manual step; existing entries are kept and reported.
- **Claude consent:** The intended route is the disclosed `hook_register` reconfigure step, with an install-time, shell-quoted command hand-off. This deviates from D-15’s separate install-time-step wording; plan 32-11 supplies the confirmed step and host binding.
- **D-12/D-13:** AI-tier entry requires bun and pins `0.0.85` with a Node 18 floor. D-13’s pin is locked; `0.0.86` is the recorded Node 20 alternative. No legitimacy checkpoint was added.
- **D-14:** Removal uses the settings ledger from `_after_removal`, rather than an unregister argv; hook settled reads determine existing registrations.
- **D-15:** Chrome’s Flatpak wrapper is exported only on Bazzite when present. Claude’s settings env key is limited to the confirmed official-plugin case.
- **Command spelling:** Registration uses absolute `bunx` beside resolved bun and the method’s pinned package spec; absent executable means no registration and a warning.
- **Decision 9:** Guards and tests travel together; no production module was added. Python 3.12 was tested locally; Python 3.15 was not run.
- **Review H6:** `rereads=True` lets the hook offer deleted registrations again; the corresponding drift rule remains for plan 32-11.
- **Accepted limits:** Claude may rewrite its live config; `CLAUDE_CONFIG_DIR` is not honored; later pins are kept; a removed host may be registered again while its presence marker remains.

## Pin edits

- Registry count: 93 → 94; AI tier: 9 → 10; AI audience: 8 → 9.
- Added Playwright MCP to the postinstall declarer exception and to all four first-method tables as `bun`.

## Deviations and remaining verification

- No Task 3 named test was omitted. Earlier tasks’ RED/GREEN transcripts were unavailable for independent reporting.
- The update test exercises `update_refusal` directly with a scratch manifest rather than the complete update execution path.
- No container, GUI, real install, or live vendor binary was run. The bun manifest exact-range assumption remains for orchestrator verification; plans 32-10 and 32-11 retain the preview and consent-step work.

## Orchestrator verification

Verified by the orchestrator on 2026-11-21:

- Commits `382195af` (Task 1: hook, consent route, Bazzite-gated Flatpak seam, `bunx` resolution, hand-off, rereads; needed a second executor run because the first stopped after one test with an unjustified BLOCKED claim), `3e1a6531` (Task 2: removal sweep) and `308ad94a` (Task 3: registry entry), each through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0; every `<behavior>` test of all three tasks exists.
- `make test` on the final tree, default TMPDIR: 8943 passed, 6 skipped, coverage 96.33%. Registry count 94 (AI tier 10).
- Container check: `playwright-container` runs after plan 32-08 and is recorded in the 32-08 summary; the placeholder below stays until then.

Provisional decisions carried to the verification report (needs owner confirmation): hosts Claude, Cursor, Copilot, OpenCode, Codex when present, Pi manual note; the Claude consent route (install-time shell-quoted `claude mcp add` hand-off plus the disclosed reconfigure step; deviates from D-15's wording; plan 32-11 supplies the confirmed step and host binding); D-12/D-13 (bun required, pin 0.0.85, Node 18 floor; 0.0.86 recorded as the Node 20 alternative); D-14 (removal through the settings ledger from `_after_removal`); D-15 (Flatpak Chrome exported only on Bazzite when the wrapper exists; Claude env key only in the confirmed official-plugin case); review H6 (`rereads` so a deleted registration is offered again; the drift rule is plan 32-11); accepted limits (Claude may rewrite its live config, `CLAUDE_CONFIG_DIR` not honored, later pins kept, a removed host may be re-registered while its presence marker remains); the update test exercises `update_refusal` directly rather than the full update path.

playwright-container: not run
