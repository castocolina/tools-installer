---
phase: 04-package-manager-redirect-policy
verified: 2026-09-05T18:52:00Z
status: passed
score: 6/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 4: Package Manager Redirect Policy Verification Report

**Phase Goal:** Every banned command that has a safe, argv-compatible managed-toolchain equivalent transparently redirects to it instead of hard-blocking, without silently masking a real underlying failure or losing pnpm's gated-postinstall security where it matters.
**Verified:** 2026-09-05T18:52:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `npx` redirect is a new `REDIRECTED` mechanism, parallel to (not a generalization of) `BANNED`; unresolved-redirect targets fall back to the same hard-block path | ✓ VERIFIED | `installer/guards.py:39-56` — `BANNED` untouched; `REDIRECTED: dict[str, Redirect]` is a separate dict/dataclass. `install_redirect_shims` (line 366) writes `shim_script(name)` (hard-block body) when `real_binary` resolves to `None` (line 387-391). `guarded_names()`/`remove_shims`/`guard_status` iterate both dicts uniformly (same removability/opt-in/PATH-warning). Test: `tests/test_guards.py::test_install_redirect_shims_falls_back_to_hard_block_when_pnpm_missing` passes. |
| 2 | `npx <pkg>` transparently execs into `pnpm dlx "$@"`, preserving real exit code/stdout/stderr | ✓ VERIFIED | `redirect_shim_script` (line 144-148) generates `exec {pnpm} dlx "$@"`. `REDIRECTED = {"npx": Redirect(target="pnpm", args=("dlx",), ...)}` (line 55). Test `tests/test_guards.py::test_npx_redirect_shim_execs_into_pnpm_dlx_with_real_exit_code` re-run directly by this verifier — passed. |
| 3 | Research determined whether `uv pip` is a safe drop-in for pip/pip3; redirect if yes, else stay hard-blocked with the gap documented | ✓ VERIFIED | Research found a real gap (`uv pip uninstall` cascades differently; `uv pip compile` has different defaults) and pip/pip3 stay in `BANNED` (unchanged), never added to `REDIRECTED`. The gap is documented in `installer/guards.py`'s module docstring (lines 20-26), citing the uv docs and `04-RESEARCH.md` Pitfall 1 — not silently papered over. |
| 4 | Research determined whether `volta install` shells out to npm internally (losing pnpm's gated postinstall) before `npm install -g`/`npm add -g`/`pnpm add -g` redirect to `volta install <pkg>`; non-global npm/npx still redirect to plain pnpm/pnpm dlx per SC#2; residual pnpm-managed set (if any) gets the snapshot-reinstall mitigation | ✓ VERIFIED | `installer/registry.toml` volta entry (line 1487+) records the source-verified finding: `volta install` runs a real `npm install --global ... <pkg>` with no way to disable install scripts (cites Volta's own source, `run_global_install`). Redirect ships as a documented tradeoff, not an assumed-safe win — `guidance.py`'s "Volta global installs run npm install scripts" note surfaces this live in Doctor (confirmed rendering in the live tmux capture below). `installer/guards.py:104-270` implements the argv-conditional `GLOBAL_REDIRECTED`/`global_redirect_shim_script` wrapper, gated on volta resolving (`install_global_redirect_shims`, line 398). Residual set determined to be non-empty (`mmdc`, kind="node") — `installer/pnpm_globals.py` implements the full snapshot/audit/one-invocation-reinstall mechanism as an explicit Doctor-only remediation (R-03), confirmed live-rendering real data in this machine's Doctor screen ("2 package(s) in pnpm's global set... `/Users/ramon/.volta/bin/pnpm add -g @pnpm/exe pnpm`"). |
| 5 | `npm` (non-global invocations) remains hard-blocked | ✓ VERIFIED | `BANNED["npm"]` still present (line 40, hint updated to mention volta for the global case only). `global_redirect_shim_script`'s fallback for npm is `ban_body(name)` (line 191) when the subcommand isn't a recognized global install shape. Test `tests/test_guards.py::test_npm_install_without_global_is_banned` re-run — passed. Live capture on this machine shows `~/.local/bin/npm` on-disk carrying the ban body verbatim. |
| 6 | Doctor/guard status covers every tool this phase touches (npx, pip, pip3, npm-global, pnpm-global) with the unchanged `guard_status()` boolean shape; per-tool label text distinguishes "redirected to X" from "blocked" | ✓ VERIFIED | `guard_status()` signature/return type unchanged: `dict[str, bool]` (`installer/guards.py:504-506`). `guard_label()` (line 509-515) returns per-command text: `redirected to pnpm dlx` (npx), `blocked` (pip/pip3), `global installs redirected to volta install, other npm use blocked` (npm), `global adds redirected to volta install` (pnpm). `installer/guidance.py::guard_guidance` renders these per-command in one Guidance item, confirmed live in the tmux capture below (`npm: global installs redirected to volta install, other npm use blocked; pip: blocked; pip3: blocked.`). |

**Score:** 6/6 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/guards.py` | `REDIRECTED`/`GLOBAL_REDIRECTED` mechanisms parallel to `BANNED`; exec-through shim generation; volta-gated writer; `real_pnpm`/`shell_path` absolute-path resolution; `guarded_names`/`guard_label`/`guard_redirect_warning` | ✓ VERIFIED | 693 lines, read in full. All claimed functions present, substantive, and exercised by tests (98% branch coverage, only 4 lines uncovered — defensive edge cases). |
| `installer/pnpm_globals.py` | Registry-derived residual snapshot, `pnpm list -g --json` audit, one-invocation reinstall via `real_pnpm`, three-state preview | ✓ VERIFIED | 250 lines, read in full. 100% coverage. `PnpmUnavailable`, `NodeGlobalsReport.known` tri-state, `reinstall_argv` all present and match the design rationale in the module docstring. |
| `installer/wizard_app.py` (DoctorScreen) | `r` binding wired to `action_reinstall_globals`; audit/reinstall run off the event loop (`@work(thread=True)`); generation-counter race protection (CR-01) | ✓ VERIFIED | `Binding("r", "reinstall_globals", ...)` (line 153); `_audit_globals_worker`/`_reinstall_globals_worker` both `@work(thread=True, exclusive=True, ...)` (lines 427, 438); `_globals_audit_generation` guards stale `GlobalsAudited` delivery (line 470); `action_reinstall_globals` refuses while `globals_auditing` (line 383). Confirmed live via tmux: footer advertises `r reinstall pnpm globals`, screen renders real audit data. |
| `installer/run.py` | `run_output`/`CommandError` with timeout support for the bounded audit query | ✓ VERIFIED | `run_output` accepts `timeout`, raises `CommandError` on `TimeoutExpired`/non-zero exit/`OSError`; used by `pnpm_globals._run_list` with `LIST_TIMEOUT_SECONDS = 20.0`. |
| `installer/registry.toml` (`volta` entry) | `tier="system"` catalog entry, D-07 finding recorded as a TOML comment | ✓ VERIFIED | Entry present at line 1489, confirmed live-listed in the System-tier catalog view during the tmux session. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `installer/wizard_app.py` DoctorScreen | `installer/pnpm_globals.py` | `node_globals`/`globals_preview`/`reinstall_globals` closures injected from `setup.py` | ✓ WIRED | `setup.py:257-284` builds `_node_globals_report`/`_globals_preview`/`_reinstall_globals` from `pnpm_globals.audit_node_globals`/`reinstall_preview`/`reinstall_node_globals` and passes them into `UnifiedApp(...)`. Confirmed live: Doctor screen rendered a real reinstall-argv preview sourced from this machine's actual `pnpm list -g --json` output. |
| `installer/guards.py` `install_global_redirect_shims` | `installer/policy.py` `ban_policy._apply` / `installer/app.py` `run_guard` | Third writer in a three-writer apply order | ✓ WIRED | Both call sites confirmed present per 04-03/04-05 summaries; consistent with `guarded_names()` including `pnpm` and the live Doctor capture showing npm/pnpm-derived guidance items. |
| `installer/executors.py` `_node` | `installer/guards.py` `real_pnpm` | Absolute-path pnpm resolution so the installer's own `kind="node"` installs bypass its own wrapper | ✓ WIRED | `real_pnpm()` used as the sole resolver; `ExecutorError` raised (never a bare-name fallback) when unresolved. Confirmed by reading `pnpm_globals.py`'s docstring cross-reference and `guards.py::real_pnpm`. |
| `installer/guidance.py` `guard_guidance`/`node_globals_guidance` | `installer/render.py` (console) and `installer/wizard_app.py` (TUI) | Both renderers consume the same `list[Guidance]` with no renderer-specific code | ✓ WIRED | Confirmed live: TUI Doctor screen rendered the exact wording documented in 04-04's SUMMARY, generated by the shared `guidance.py` module. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| Doctor "pnpm-managed globals" count | `report.managed`/`report.entries` | `pnpm_globals.audit_node_globals` → `pnpm_global_packages` → real `pnpm list -g --json` subprocess (via `real_pnpm`) | Yes — live capture on this machine showed the actual installed set (`@pnpm/exe`, `pnpm`), not a static/mocked value | ✓ FLOWING |
| Doctor reinstall-argv preview | `reinstall_preview(...)` | `installer.guards.real_pnpm` resolves the real binary path at render time | Yes — live capture showed the exact absolute path (`/Users/ramon/.volta/bin/pnpm add -g @pnpm/exe pnpm`) | ✓ FLOWING |
| Doctor per-command guard labels | `guard_status(shim_dir)` | Reads actual on-disk shim files (sentinel check) via `is_our_shim` | Yes — live capture correctly distinguished npm/pip/pip3 (real shims present, one stale/degraded) from npx/pnpm (no shim on disk) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| npx redirect execs into pnpm dlx with real exit code | `uv run pytest tests/test_guards.py::test_npx_redirect_shim_execs_into_pnpm_dlx_with_real_exit_code` | 1 passed | ✓ PASS |
| npm/pnpm global-install argv redirects to volta | `uv run pytest tests/test_guards.py::test_npm_global_install_redirects_to_volta tests/test_guards.py::test_pnpm_add_g_redirects_to_volta` | 2 passed | ✓ PASS |
| Non-global npm stays hard-blocked | `uv run pytest tests/test_guards.py::test_npm_install_without_global_is_banned` | passed (part of combined run above) | ✓ PASS |
| Residual pnpm-managed set derived from the live registry includes mmdc | `uv run pytest tests/test_pnpm_globals.py::test_real_registry_residual_set_contains_mmdc` | 1 passed | ✓ PASS |
| CR-01 race fix: reinstall refuses while a fresher audit is in flight; stale audit delivery discarded; stale "went missing" note cleared after reinstall | `uv run pytest tests/test_wizard_app.py::test_doctor_reinstall_refuses_a_stale_report_while_reauditing tests/test_wizard_app.py::test_doctor_stale_audit_delivery_is_discarded tests/test_wizard_app.py::test_doctor_r_clears_the_stale_missing_globals_warning` | 3 passed | ✓ PASS |
| Doctor `r` action reinstalls once and reports success / CommandError leaves screen usable | `uv run pytest tests/test_wizard_app.py::test_doctor_r_reinstalls_once_and_reports_success tests/test_wizard_app.py::test_doctor_r_commanderror_leaves_screen_usable` | 2 passed | ✓ PASS |
| Full suite / coverage gate | `make validate && make test` (re-run by this verifier) | ruff/pyright/bandit/vulture/shellcheck all clean; 1038 tests collected, all pass; TOTAL coverage 99.57% (fail_under=90 reached) | ✓ PASS |

### Structural TUI Check (Rule 14 Tier 2 — navigation only, no state-mutating keys pressed)

Ran via tmux against this real machine: `uv run setup.py` → pressed `4` to reach the Doctor view. **Did not press `r` or `enter`** (per 04-05 SUMMARY's explicit "Next Phase Readiness" caution and this task's instruction).

Captured pane confirmed:
- Footer advertises both actions: `enter apply | r reinstall pnpm globals`.
- Body renders "PATH Doctor" → "Audit" → per-command guard guidance ("npm: global installs redirected to volta install, other npm use blocked; pip: blocked; pip3: blocked...") → the volta install-scripts tradeoff note → PATH-order warning → guard-redirect degradation warning (correctly detected this machine's `npm` shim as a stale/old hard-block body predating this phase, and named the remedy) → Safe fix preview → Action → "pnpm-managed globals" section with a real live count (`2 package(s) in pnpm's global set, 0 of them catalog tool(s)`) and a real reinstall-argv preview → "Press r to reinstall the pnpm-managed global set."
- `System` catalog view (pressed before navigating to Doctor) confirmed `volta` is present as a `pkg-mgr` category, `tier=system` catalog row, installed (✓) on this machine.

No crash, no missing section, no static/placeholder text where live data was expected. This confirms the Doctor remediation flow's structural wiring end-to-end on a real machine, without triggering the real pnpm reinstall.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REQ-npx-ban | 04-01 | `npx` treated identically to npm/pip/pip3 ban infra (shim/alias/status/removability) | ✓ SATISFIED | `guarded_names()` unifies removal/status; `BANNED["npx"]` present as the fallback body. |
| REQ-npm-npx-redirect-policy | 04-01, 04-03, 04-04 | npx unconditional redirect; npm non-global stays blocked; parallel `REDIRECTED` mechanism; per-tool doctor labels | ✓ SATISFIED | See truths 1, 2, 5, 6 above. |
| REQ-npm-global-volta-redirect | 04-02, 04-03 | Global npm/pnpm installs redirect to volta, gated on research + volta resolving | ✓ SATISFIED | See truth 4 above. |
| REQ-pnpm-global-reinstall-mitigation | 04-05 | Mechanism + audit + manual Doctor trigger for the residual pnpm-managed set | ✓ SATISFIED (Partial per REQUIREMENTS.md's own tracking — automatic post-update trigger explicitly deferred to Phase 12, not this phase's scope) | `installer/pnpm_globals.py` + Doctor `r` action; REQUIREMENTS.md/ROADMAP.md traceability rows already read "Partial" / "Phase 4 (mechanism + manual trigger) / Phase 12 (automatic trigger)" — consistent with R-03's locked decision, not a gap. |

No orphaned requirements found for this phase — the four traceability rows above are the complete `Phase 4` set in `.planning/REQUIREMENTS.md`.

### Anti-Patterns Found

None. Scanned `installer/guards.py`, `installer/pnpm_globals.py`, `installer/wizard_app.py`, `installer/run.py`, `installer/guidance.py`, `installer/ui_common.py`, `installer/executors.py`, `installer/policy.py`, `installer/app.py`, `installer/registry.toml` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and stub-shaped patterns — zero matches. No debt markers, no stub returns, no hardcoded empty data flowing to rendered output (all Doctor sections trace back to live subprocess/registry reads, confirmed in the Data-Flow Trace above).

### Human Verification Required

None. All must-haves resolved to VERIFIED with either a re-run automated test or a live structural capture on the real machine; no items required subjective/visual judgment beyond what this verifier already performed directly.

### Gaps Summary

No gaps. All 6 ROADMAP success criteria and all 4 requirement IDs for Phase 4 are backed by code that this verifier read in full (not excerpted from summaries), exercised via re-run tests (10 individually re-run + full 1038-test suite), and observed live on a real machine via tmux navigation up to (not through) the state-mutating `r`/`enter` actions, per this task's explicit instruction. The two most recent commits (`6888062` CR-01 race fix, `2fa65eb` WR-02/03/04) were independently confirmed to exist and to match their claimed content and to be covered by dedicated regression tests that pass.

One item worth noting for the human record, not a gap: this specific dev machine's on-disk `npm`/`pip`/`pip3` shims are stale (dated before this phase shipped — the `npm` shim's hint text does not match the current `BANNED["npm"]` value), and the volta/pnpm redirect shims are not currently installed on disk at all. This is expected — the policy has not been re-applied on this machine since Phase 4 shipped — and the code correctly detected and surfaced this exact condition via `guard_redirect_warning`, which is itself evidence the degradation-detection mechanism works as designed rather than a defect.

---

*Verified: 2026-09-05T18:52:00Z*
*Verifier: Claude (gsd-verifier)*
