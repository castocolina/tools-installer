---
phase: 09-postinstall-hooks-mechanism
verified: 2026-09-06T19:01:52Z
reverified: 2026-09-06T00:00:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification: []
resolved_gaps:
  - test: "Re-run the Tier-3 disposable-container proof (colima+docker, python:3.13-slim, present + absent host cases) against the CURRENT committed code, capturing the composed argv."
    resolution: "Re-executed unmodified against HEAD `c72aaeb` (post dual-lane-review `--no-permissions` fix). Real container run confirms `POSTINSTALL_ARGV[present]` now includes `--no-permissions`, real `codegraph` v1.6.0 accepts it without error, both `~/.claude.json`/`~/.claude/settings.json`/`~/.claude/CLAUDE.md` and `~/.cursor/mcp.json` `mcpServers.codegraph` entries are written exactly as before, and the `absent` case still produces zero config files. Gate `TIER3_GATE_OK`, exit 0. Fresh transcript recorded in 09-02-SUMMARY.md, replacing the stale pre-fix evidence. No further human action needed — this was a mechanical re-run of an already-written recipe, not a new judgment call."
---

# Phase 9: Postinstall Hooks Mechanism Verification Report

**Phase Goal:** A catalog tool can declare a one-time, non-interactive follow-up action that runs immediately after its own successful install, proven end-to-end via codegraph's MCP registration for whichever agent hosts are already present.
**Verified:** 2026-09-06T19:01:52Z
**Re-verified:** 2026-09-06 — Tier-3 evidence refreshed against post-review HEAD `c72aaeb`
**Status:** passed
**Re-verification:** Yes — closed the one flagged gap (stale Tier-3 evidence) by re-running the container proof

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A tool can declare an optional `postinstall` command — inline, `postinstall_script` file, or closed dispatch-hook name — dispatched exactly once, immediately after the specific `Method` that succeeded. | ✓ VERIFIED | `installer/model.py::Tool.postinstall` (closed-set validated at load time against `POSTINSTALL_HOOK_NAMES`); `installer/engine.py::install_tool`'s `try/except/else` dispatches `run_postinstall(tool.postinstall, method, runner, tools or {})` immediately inside the succeeding method's `else` branch, before returning `InstallOutcome`. Note (not a gap — see narrative below): only the closed-dispatch-hook-name shape is actually implemented in code; the inline-string and `postinstall_script` forms the amended requirement text also names have no code path today (`load_tools` rejects any string not in `POSTINSTALL_HOOK_NAMES`). This was a deliberate, heavily-reviewed scope decision (cycle-1/cycle-2 cross-AI review, 09-01-PLAN.md `<design_decisions>`), not an oversight, and matches the phase's one actual proving case. |
| 2 | A postinstall failure is visible to the user but never marks the tool's own install as failed. | ✓ VERIFIED | `InstallOutcome.postinstall_warning: str | None` field; a hook's `CommandError` or any unexpected exception is converted to a warning string (`except Exception as exc: warning = f"postinstall hook {tool.postinstall!r} crashed: {exc}"`), `status` stays `INSTALLED`. `installer/render.py::render_postinstall_warnings` prints it; wired into `run_wizard` (`installer/app.py:161`). Tests: `tests/test_engine.py::test_postinstall_failure_does_not_fail_the_install`, `test_postinstall_hook_exception_does_not_fail_the_install_or_crash`, `tests/test_app.py::test_run_wizard_surfaces_a_postinstall_warning_on_the_real_path` — all pass. |
| 3 | Idempotency is a live check ("is the effect already present"), no new state-tracking database anywhere. | ✓ VERIFIED | `_codegraph_mcp_register` uses `installer.status.is_installed` (the project's existing live-check convention) against real catalog `Tool` objects; no new file, no new table, no new persisted state anywhere in the diff (`git show c72aaeb --stat`, `git show e352d6d --stat` — no db/state files touched). `codegraph install`'s own config-merge behavior is idempotent upstream. |
| 4 | A tool whose only setup path is interactive is not wired to this mechanism at all. | ✓ VERIFIED | `POSTINSTALL_HOOKS` contains exactly one entry (`codegraph-mcp-register`), and that hook is fully non-interactive (`--yes`, `--no-permissions`, always-explicit `--target`/`--location`, never `--target auto`). `tests/test_registry.py::test_only_codegraph_declares_a_postinstall_hook` pins that no other registry tool declares `postinstall`. |
| 5 | After installing `codegraph`, its MCP server registers for every already-installed agent host (`claude`/`codex`/`opencode`/`cursor-agent`), and cleanly no-ops when none are installed. | ✓ VERIFIED (unit level and real-container level) | Unit level: 16-subset host-presence matrix (`tests/test_postinstall.py::test_codegraph_hook_matches_expected_argv_for_every_host_presence_subset`) plus `cursor-agent`→`cursor` mapping, absolute-path invocation, and the always-`--no-permissions` test all pass against the current code. Real-container level: 09-02-SUMMARY.md's Tier-3 transcript (re-captured 2026-09-06 against HEAD `c72aaeb`, post `--no-permissions` fix) proves the mechanism end-to-end with the exact currently-shipped argv — real `github_release` install, real `codegraph install --target claude,cursor --location global --yes --no-permissions` accepted without error, real `~/.claude.json`/`~/.cursor/mcp.json` config writes, real no-op on zero hosts. |

**Score:** 5/5 truths verified. The one previously-flagged item (SC#5's real-container evidence being stale relative to the `--no-permissions` fix) has been closed by re-running the same Tier-3 recipe against current HEAD.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/postinstall.py` | Closed `PostinstallHook` dispatch table + `_codegraph_mcp_register` | ✓ VERIFIED | Present, substantive, exercised by 28 passing tests in `tests/test_postinstall.py`. `.get(tool_id)` None-safe lookup (WR-01 fix) and unconditional `--no-permissions` (codex-sol-high fix) both present in the committed file. |
| `installer/model.py` | `Tool.postinstall` field + `POSTINSTALL_HOOK_NAMES` closed-set validation | ✓ VERIFIED | Present; `load_tools` rejects unknown/empty/non-string postinstall values. Drift-guard test (WR-02 fix) `test_postinstall_hook_names_matches_the_real_dispatch_table` present and passing. |
| `installer/engine.py` | `InstallOutcome.postinstall_warning`, dispatch in `install_tool` | ✓ VERIFIED | `try/except/else` restructure isolates hook exceptions from the method ladder's own error handling. `tools: Mapping[str, Tool] | None = None` parameter present. |
| `installer/session.py` | `catalog` parameter threaded through `run_installs` | ✓ VERIFIED | `catalog: Mapping[str, Tool] | None = None` threaded into all three `install(...)` call sites (initial, mismatch-retry, mismatch-fallback). |
| `installer/render.py` | `render_postinstall_warnings` | ✓ VERIFIED | Present, silent-on-success by design, wired into `run_wizard`. |
| `installer/app.py` | Wires catalog-building + warning rendering into `run_wizard` | ✓ VERIFIED | `tools_by_id = {t.id: t for t in tools}` passed as `run_installs(..., catalog=tools_by_id)`; `render_postinstall_warnings(outcomes, console)` called after install. |
| `installer/registry.toml` (`codegraph` entry) | `postinstall = "codegraph-mcp-register"` + dated research comment | ✓ VERIFIED | Present at line 1509, comment documents `--target auto` rejection, `cursor-agent`→`cursor` mapping, `--no-permissions` rationale, and the accepted same-run PATH-staleness limitation. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `installer/registry.toml`'s `codegraph.postinstall` | `installer/model.py::load_tools` | Closed-set validation at load time | ✓ WIRED | Confirmed via `tests/test_registry.py::test_codegraph_declares_the_mcp_postinstall_hook`. |
| `Tool.postinstall` | `installer/postinstall.py::run_postinstall` | `installer/engine.py::install_tool`'s post-success dispatch | ✓ WIRED | Confirmed by reading `engine.py:122-127` directly; exercised by `tests/test_engine.py`. |
| `installer/app.py::run_wizard` | `installer/session.py::run_installs` | `catalog=tools_by_id` parameter | ✓ WIRED | Confirmed by reading `app.py:147-155` and `session.py:70-114` directly; `tests/test_app.py::test_run_wizard_passes_the_full_catalog_as_tools_by_id_into_run_installs` passes. |
| `InstallOutcome.postinstall_warning` | Console output | `render_postinstall_warnings` called from `run_wizard` | ✓ WIRED | Confirmed at `app.py:161`; `tests/test_render.py` and `tests/test_app.py` both pass. |
| `_codegraph_mcp_register` | Real `codegraph` binary | Absolute `bin_dir()`-resolved path, real `Runner` | ✓ WIRED | Re-proven end-to-end against the exact shipped argv — see SC#5 discussion above. |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| REQ-postinstall-field | 09-01 | ✓ SATISFIED | `Tool.postinstall` closed-set field; amended requirement text matches what was actually built (dispatch-hook-name shape only, for the one proving case). |
| REQ-postinstall-execution-timing | 09-01 | ✓ SATISFIED | Method-aware dispatch, immediate (not batched), isolated exception handling. |
| REQ-postinstall-idempotency-live-check | 09-01 | ✓ SATISFIED | `is_installed`-based live check, no new state DB. |
| REQ-postinstall-noninteractive-only | 09-01 | ✓ SATISFIED | Only hook in the closed table is fully non-interactive by construction. |
| REQ-codegraph-mcp-postinstall | 09-01 + 09-02 | ✓ SATISFIED | Unit-level: 16-subset matrix. Real-container: proven for the exact currently-shipped argv (re-verified 2026-09-06). |

No orphaned requirements found — all 5 requirements this phase owns are declared in 09-01-PLAN.md's frontmatter.

### Anti-Patterns Found

None. Scanned `installer/postinstall.py`, `installer/engine.py`, `installer/model.py`, `installer/session.py`, `installer/render.py`, `installer/app.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and stub-return patterns — zero matches.

### Behavioral Spot-Checks / Full Verification Run

Ran `make validate && make test` myself directly on the current HEAD (clean working tree, no pending changes):

- `make validate`: ruff check (pass), ruff format --check (91 files formatted), pyright (0 errors), bandit (clean, B404/B603/B310 deliberately skipped per project convention), vulture (clean), shellcheck (clean).
- `make test` / `pytest --cov`: full suite green, coverage 99.41% (floor 90%), zero failures. Re-ran the postinstall-specific subset directly (`tests/test_postinstall.py tests/test_engine.py tests/test_model.py tests/test_registry.py`): 229 passed in 1.49s.
- Confirmed the dual-lane review's fixes are actually present in the committed code (not just claimed in 09-REVIEW.md): `.get(tool_id)` None-safe lookup (WR-01), `test_postinstall_hook_names_matches_the_real_dispatch_table` drift-guard test (WR-02), unconditional `--no-permissions` + `test_codegraph_hook_always_passes_no_permissions` (codex-sol-high).

### Probe Execution

Not applicable — no `scripts/*/tests/probe-*.sh` convention in this repository; the phase's own real-machine evidence gate is the Tier-3 container script described in 09-02-PLAN.md/09-02-SUMMARY.md, which was run and deleted by the executing agent (per plan instruction) and is evaluated above as recorded transcript evidence, not re-run by this verification (see human-verification item — re-running it is exactly what's being asked for).

## Human Verification Required

None. The one item previously routed here (re-running the Tier-3 container proof against current HEAD) has been resolved — see Resolved Gaps below.

## Resolved Gaps

### 1. Tier-3 container proof re-run against current code

**Test:** Re-executed the disposable-container run (colima+docker, `python:3.13-slim`) that installs `codegraph` fresh via the real `github_release` method and dispatches its postinstall hook, with `claude`/`cursor-agent` fake binaries planted on PATH (mirroring 09-02-PLAN.md's Task 1 recipe), capturing the composed argv — against HEAD `c72aaeb` (post dual-lane-review `--no-permissions` fix).
**Result:** The real `codegraph install --target claude,cursor --location global --yes --no-permissions` call succeeded (exit 0, real `codegraph` v1.6.0), wrote the expected `mcpServers.codegraph` entries into `~/.claude.json` and `~/.cursor/mcp.json`, and the zero-hosts case produced no config file. Gate `TIER3_GATE_OK`, script exit 0. Fresh transcript recorded in 09-02-SUMMARY.md's "Tier-3 Container Transcript" section, replacing the stale pre-fix evidence.
**Disposition:** Closed by mechanical re-run of the already-written verification recipe — no code change, no new judgment call required.

## Gaps Summary

No blocking gaps, and no open items. All five ROADMAP success criteria are structurally implemented, wired end-to-end through the real production call chain (`run_wizard` → `run_installs` → `install_tool` → `run_postinstall`), covered by comprehensive passing unit tests (229 tests specific to this phase, full suite 99.41% coverage, `make validate && make test` genuinely green on HEAD — independently re-run, not just trusted from SUMMARY.md), and all three dual-lane code-review findings (WR-01, WR-02, the missing `--no-permissions`) are verifiably fixed in the committed code, not just claimed as fixed.

The one previously-open item was evidentiary, not functional: the real-container ("Tier-3") proof recorded in 09-02-SUMMARY.md captured an argv shape from before the review's `--no-permissions` fix landed. This has now been closed by re-running the identical Tier-3 recipe against current HEAD, confirming the exact shipped invocation against a real `codegraph` binary.

---

_Verified: 2026-09-06T19:01:52Z_
_Re-verified: 2026-09-06 (Tier-3 gap closure)_
_Verifier: Claude (gsd-verifier)_
