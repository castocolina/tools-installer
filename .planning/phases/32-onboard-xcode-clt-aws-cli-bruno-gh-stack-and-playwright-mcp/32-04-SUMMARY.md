# Phase 32 Plan 04 Summary

- **Task 1 — `2e336f03`:** Added three-level JSON insertion, recorded created levels, and revert handling. Its RED and GREEN output was not available in the commit history.
- **Task 2 — `dc8dcbf5`:** Added the five-host MCP ledger writer, snapshot presence gate, Codex ownership-unit revert, read-only helpers, Claude environment key, and tests.

## Test output

- **Task 2 RED:** The targeted run failed in all five new host cases with `AttributeError: module 'installer.agent_settings' has no attribute 'apply_mcp_server'`.
- **Task 2 GREEN:** The targeted five-file pytest command exited 0 and reached `[100%]`.
- **`make validate`:** All six gates passed.
- **`make test`:** `8869 passed, 6 skipped in 68.93s`; coverage `96.33%`, above the 90% requirement.
- The first commit attempt failed lint and formatting; both were corrected, their targets passed, and the subsequent commit hook passed all six gates.

## Pin edits

Expanded the existing `DYNAMIC_KEYS` closed-set assertion to include the MCP and Claude environment paths.

## Decisions

- **Orchestrator decision 1 — provisional, needs confirmation:** The writer covers Claude, Cursor, Copilot, OpenCode and Codex. Host-presence selection and the Pi manual-step note belong to plan 32-05.
- **32 D-14:** The settings ledger is the file-revert mechanism; MCP and ordinary settings use separate file/key-path allow-lists.
- **Codex, research pitfall 6:** Registration uses table keys, checks the whole server inside the write snapshot, and reverts recorded keys as one ownership unit.
- **OpenCode, research pitfall 7 and review W4 — provisional, needs confirmation:** Write the v2 shape only for absent, empty or server-bearing `mcp`; retain a v1 Playwright entry and hand off other v1-shaped sections.
- **Review H4 — provisional, needs confirmation:** `created_levels` is an optional ledger field; older ledger lines retain their existing shape.
- **Orchestrator decision 9 — provisional:** Guards and tests belong in the same task; compatibility targets Python 3.12 and 3.15; executor-visible plans should remain under approximately 55 KB.
- **Accepted limits:** A running Claude can rewrite `~/.claude.json` after the retry-once write; `CLAUDE_CONFIG_DIR` is not honored; an absolute `COPILOT_HOME` moves Copilot’s file; a later pin does not replace an existing registration.
- **Consent route — provisional, needs confirmation:** Claude writes require consent; integration and the confirmed consent step are deferred to plans 32-05 and 32-11.

## Deviations and remaining risk

- The first pass left parts of the scenario matrix untested (the executor said so); the orchestrator ran a completion pass that added them (commit `fdfafa0b`, tests only, no production defect found). Only the first five-host test was observed RED before implementation; the rest were added after.
- Python 3.15 and live host integrations were not checked. No container, GUI, real install or agent configuration was touched.

## Orchestrator verification

Verified by the orchestrator on 2026-11-21:

- Commits `2e336f03` (Task 1), `dc8dcbf5` (Task 2) and `fdfafa0b` (completion pass: the executor admitted its tests did not cover every scenario the plan names, so a second run audited every `<behavior>` bullet and sub-case against the tests and added the missing ones, tests only; its coverage table maps each scenario to a test), all through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0; every plan-named test exists.
- `make test` on the final tree, default TMPDIR: 8900 passed, 6 skipped, coverage 96.33%.
- Container checks: the Playwright registration runs in a container after plan 32-08.

Provisional decisions carried to the verification report (needs owner confirmation): orchestrator decision 1 (hosts Claude, Cursor, Copilot, OpenCode, Codex through the ledger; Pi is skipped with a manual-step note by plan 32-05); OpenCode v1/v2 shapes (write only for absent, empty or `servers`-bearing `mcp`; keep a v1 `playwright` entry; skip other v1-shaped sections with a `partial:` note); review H4 (`created_levels` optional ledger field); the consent route (Claude writes need consent; integration in plans 32-05 and 32-11). Accepted limits: a running Claude can rewrite `~/.claude.json` after the retry-once write; `CLAUDE_CONFIG_DIR` is not honored; an absolute `COPILOT_HOME` moves Copilot's file; a later pin does not replace an existing registration.

orchestrator-verification: none required

orchestrator-verification: none required
