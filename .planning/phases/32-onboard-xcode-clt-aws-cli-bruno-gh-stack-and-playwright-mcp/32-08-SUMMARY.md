# Phase 32 Plan 08 Summary

- **Task 1 — `fe2630f6`:** Added the Playwright MCP lifecycle evidence driver, JSON-RPC client, verdicts, and hermetic tests. The earlier executor’s RED and GREEN output was not available in this split run; the committed driver tests passed in Task 2’s targeted run.
- **Task 2 — `30cc2159`:** Added the orchestrator-only container verb, usage text, generic skip, and host tests. RED: the target and skip-list assertions failed before implementation. GREEN: the targeted six-file pytest command exited 0.

## Final gates

- `make validate`: all six gates passed.
- `make test`: **9011 passed, 6 skipped**; coverage **96.33%**, above the 90% threshold.
- The initial commit hook reported formatting and line-length failures; those were corrected, the affected gates rerun, and the commit hook passed.

## Decisions

Each decision below is **provisional and needs confirmation**:

- Decision 10 / D-16: Use distro Chromium via `PLAYWRIGHT_MCP_EXECUTABLE_PATH`; only a transcript-bound `playwright-container: PASS` counts. Environmental `_UNPROVEN` or infeasible results require an orchestrator retry.
- Decisions 6 and 9: Exclude Playwright MCP from the generic pass; use the dedicated target with `--no-sandbox`, file-based child output, residue baseline, standard empty directories, transcript digest, and evidence gate.
- Exercise consent through `postinstall.register_hooks` first with Cursor only, then with Claude confirmed; seed the Copilot user entry and Claude settings for preservation checks.
- Launch from the registered Claude entry, appending `--headless --no-sandbox` and setting the distro Chromium path.

## Pin edits

- Extended the exact generic skip-list pin with `playwright-mcp`.
- Moved the four classified PATH line numbers by eight; their reasons are unchanged.
- AWS and Bruno membership assertions required no edits.

## Deviations and cleanup

- No Task 2 named tests were omitted. Task 1’s original RED/GREEN output was unavailable, so it is not claimed.
- Targeted runs used the default `TMPDIR` as required by the binding run notes; their owned run directories were removed by EXIT traps. The coverage artifact created by the final suite was removed.
- The container and real browser launch were not run. Runtime proof remains for the orchestrator.

Orchestrator to run: `scripts/container-e2e-verify.sh playwright-mcp`

## Orchestrator verification

Verified by the orchestrator on 2026-11-21:

- Commits `fe2630f6` (Task 1, driver), `30cc2159` (Task 2, container target) and `d38a98f6` (a fix the real run found, below), each through the six-gate commit hook.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0; every `<behavior>` test exists. `make test` on the final tree, default TMPDIR: 9012 passed, 6 skipped, coverage 96.33%.
- Real container check, run by the orchestrator: `scripts/container-e2e-verify.sh playwright-mcp`. Run 1 (10:24): install with bun at the pinned range, registration for the codex, cursor and opencode hosts with the user's copilot entry kept, the Claude consent step and the late-host binding, and the launch smoke (25 tools listed, navigation ok) all passed; the removal verdict failed on residue that was not the installer's: bun's own empty `.bun/bin/` directory and the smoke browser's profile in `.config/chromium/`. Fixed in `d38a98f6` (the smoke's browser config goes to a scratch directory; an empty `.bun/bin/` is bun's directory and not residue; a file inside it is still reported; pinned by a test). Run 2 (10:32): all five verdicts and the teardown line, in order, once each. Transcript: `.e2e-artifacts/container-playwright-mcp/playwright-mcp-transcript.log` (git-ignored).
- No `tools-installer-e2e-*` container is left; no broad prune or reset was run.

Provisional decisions carried to the verification report (needs owner confirmation): D-16 (the launch smoke uses the distro Chromium through `PLAYWRIGHT_MCP_EXECUTABLE_PATH`, headless with `--no-sandbox`; the Bazzite Flatpak Chrome path is not exercised in the box); the late-host container case calls `register_hooks` with a confirmed set that excludes Claude, then the real consent call; the box registers the codex, cursor and opencode hosts (Claude is exercised through the consent call, Copilot's seeded entry is kept).

playwright-container: PASS (2026-11-21; transcript ee31bd6542f3)
