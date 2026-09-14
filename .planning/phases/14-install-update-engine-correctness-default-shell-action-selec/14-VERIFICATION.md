---
phase: 14-install-update-engine-correctness-default-shell-action-selec
verified: 2026-09-14T19:10:00Z
status: passed
score: 20/20 must-haves verified
covered_files: [".claude/architecture.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-01-PLAN.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-01-SUMMARY.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-02-PLAN.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-02-SUMMARY.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-03-PLAN.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-03-SUMMARY.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-04-PLAN.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-04-SUMMARY.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-05-PLAN.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-05-SUMMARY.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-CONTEXT.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-REVIEW-cross-ai.md", ".planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-REVIEW.md", "installer/app.py", "installer/deps.py", "installer/engine.py", "installer/execute_screen.py", "installer/post_install.py", "installer/registry.toml", "installer/render.py", "installer/session.py", "setup.py", "tests/test_app.py", "tests/test_deps.py", "tests/test_docs.py", "tests/test_engine.py", "tests/test_execute_screen.py", "tests/test_post_install.py", "tests/test_registry.py", "tests/test_render.py", "tests/test_session.py", "tests/test_setup.py", "tests/test_wizard_app.py"]
covered_digest: "v1:sha256:457acc3013500a06d9ab31a4a90a19df08c3869f2294554d71aa05ad0521be71"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 14: Install/Update Engine Correctness & Default-Shell Action Verification Report

**Phase Goal:** Selecting a tool the catalog shows as outdated and pressing enter actually updates it
through the same update service the per-row `u` keybind uses — or says, in the post-run summary and
in that keybind's own words, why it will not; and `set_login_shell` becomes a real, implemented
post-install action on `oh-my-zsh` alone: hard-blocked on immutable/atomic hosts before anyone is
asked, silent without an explicit confirmation, and producing reviewed instructions the user runs
themselves rather than a shell change launched from a worker thread.
**Verified:** 2026-09-14T19:10:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Selecting an outdated, installed, selected tool + enter reaches `UpdateService.run` (D-01) | ✓ VERIFIED | `installer/execute_screen.py:562-598` `_run_updates` builds `UpdateTarget` and calls `run_live(partial(updates.run, target))`; `tests/test_execute_screen.py -k outdated` passes (spot-run) |
| 2 | Nothing mutates before `enter`; existing confirm gate is the only consent (D-02) | ✓ VERIFIED | Exactly one `push_screen_wait(` call site in the whole file (`execute_screen.py:189`, inside `ask_from_worker`); update dispatch lives only in `_execute_worker`, reached only via `action_start`; `test_nothing_updates_before_the_confirm_keypress` passes |
| 3 | `resolve_dependencies` still excludes a selected, installed, outdated tool; resolver stays pure | ✓ VERIFIED | `installer/deps.py:111` `satisfied_by_install` unchanged; no `VersionStatus`/`ManagerOwnership` names in the file (grep confirms 0 hits) |
| 4 | A batch of only-outdated tools (zero installs) still starts and does work | ✓ VERIFIED | `_preflight_prompt` (`execute_screen.py:766-774`) renders `Update {n} tools?` when `install_n == 0`; `test_update_only_outdated_preflight_does_not_read_as_zero_work` referenced in 14-02-SUMMARY, spot-checked via `-k outdated` |
| 5 | In-flight latch refusal is named, never retried, latch never released by a taker that didn't acquire it | ✓ VERIFIED | `execute_screen.py:576-598`: `updates.begin(tool.id)` false → skip recorded, `continue`; `updates.end()` sits in a `finally` reached only after a successful `begin` inside the `try` |
| 6 | Deliberate divergence: batch path blocks on single-tool refresh when no ownership snapshot cached | ✓ VERIFIED | `execute_screen.py:565-571`, now wrapped in `run_live` after the post-review fix (67b9d66) |
| 7 | Preflight head and progress list disclose exactly `_to_update` (closes 14-01's documented gap) | ✓ VERIFIED | `_refresh_progress` (`execute_screen.py:776-793`) iterates both `self._ordered` and `self._to_update`; `_preflight_prompt` counts both |
| 8 | Dispatched set never larger than disclosed set, on every path (safety half) | ✓ VERIFIED | `_to_update` is the single source for both preflight rendering and `_run_updates`'s loop — no second eligibility computation exists |
| 9 | On an undisturbed run, disclosed set == dispatched set (Fixture A) | ✓ VERIFIED | `test_undisturbed_outdated_run_dispatches_exactly_the_disclosed_update_ids` (14-02-SUMMARY D2), part of `-k outdated` spot-run |
| 10 | Every queued update visible in post-run report; refusals use `cannot update {id}: {reason}` (D-03) | ✓ VERIFIED | `_render_updates` (`execute_screen.py:727-751`) formats exactly that string for `unknown-owner` outcomes, with `_NO_MANAGER_CLAIMED` fallback (`execute_screen.py:77`) |
| 11 | A refused/failed update never flips a successful install batch into a failure or changes exit code | ✓ VERIFIED | `_render_updates` only appends to local `lines`; nothing here touches `Summary` buckets or `error`; confirmed via source read of `on_install_run_finished` |
| 12 | No progress row left pending once run has ended (cancel/latch-refused rows swept to skipped) | ✓ VERIFIED | `not_attempted` sweep logic at `execute_screen.py:665-677`, tests `test_cancel_mid_update_tail_sweeps_unreached_outdated_row_to_skipped` and `test_latch_refused_outdated_update_row_is_swept_to_skipped` (14-02-SUMMARY) |
| 13 | `set_login_shell` is dispatched from `oh-my-zsh`'s install ladder, no longer dead schema (D-06) | ✓ VERIFIED | `installer/registry.toml:536` `post_install = ["set_login_shell"]`; `installer/engine.py:166-181` dispatches `run_post_install` post-success |
| 14 | Immutable host: action never executed, user never asked, guard runs before confirmation (D-04) | ✓ VERIFIED | `installer/post_install.py:45-46` `if platform.immutable: return ()` is the first statement, before the confirm callback is ever touched; `test_immutable_host_cannot_bypass_login_shell_guard_via_default_enabled` locks the default-enabled-can't-bypass case |
| 15 | Non-immutable host: nothing happens without explicit confirmation returning true; unattended = skip (D-05) | ✓ VERIFIED | `post_install.py:47-48`; console path `installer/app.py:165` binds `None if options.yes else confirm_sensitive`; in-app path `execute_screen.py:494` binds `None if self._inputs.unattended else self._ask_sensitive_action`; both proved by required `-k sensitive_unattended` behavioral tests (spot-run, both pass) |
| 16 | Installer never runs the shell-change command; produces reviewed instructions only | ✓ VERIFIED | `post_install.py` module imports no `subprocess`/`Runner`/`run_command`/`os`; action returns a fixed literal tuple `_SET_LOGIN_SHELL_INSTRUCTIONS` |
| 17 | Registry can only select a NAME from a closed, code-owned table; no command text in TOML | ✓ VERIFIED | `POST_INSTALL_HOOKS: dict[str, PostInstallAction]` closed dict in `post_install.py`; registry only supplies the string `"set_login_shell"` |
| 18 | Reviewed instructions reach the user (both console and in-app), using the same wording, matching renderer order | ✓ VERIFIED | `installer/render.py::render_post_install_handoff` (markup disabled) wired into both `run_wizard` (`app.py:177`) and `ExecuteScreen.on_install_run_finished` (`execute_screen.py:685`); order-match asserted by `test_post_run_log_carries_every_renderer_in_wizard_order` / `ORDER-MATCHES` gate (14-05) |
| 19 | The in-app sensitive-action prompt reuses the single `ask_from_worker` mechanism, describes the handoff truthfully | ✓ VERIFIED | `SensitiveActionScreen` (`execute_screen.py:133`) is a `ModalScreen[str \| None]` like the mismatch screen; only one `push_screen_wait` call site in the file; prompt text asserted not to claim the installer performs the change (`test_sensitive_action_screen_names_the_tool_and_the_reviewed_command`) |
| 20 | `.claude/architecture.md` records both mechanisms and the stale "no production caller" clause is corrected in place | ✓ VERIFIED | `grep -c 'zero production callers as of Phase 12.4'` = 0; `## Phase 14: update dispatch and the login-shell handoff` section present; `tests/test_docs.py` passes |

**Score:** 20/20 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/execute_screen.py` | update split, dispatch, progress/report, in-app prompt | ✓ VERIFIED | All symbols present and wired (`_to_update`, `_run_updates`, `SensitiveActionScreen`, `_ask_sensitive_action`, `_render_updates`) |
| `installer/post_install.py` | closed, execution-free dispatch table (new module) | ✓ VERIFIED | Created; one entry (`set_login_shell`); no execution seam |
| `installer/engine.py` | post-success dispatch, `InstallOutcome.post_install_handoff` | ✓ VERIFIED | `confirm_sensitive_action` keyword-only param; dispatch after singular hook, before INSTALLED outcome |
| `installer/registry.toml` | `oh-my-zsh` declares `set_login_shell`, `CHSH=no` unchanged | ✓ VERIFIED | Confirmed at lines 527-543 |
| `installer/session.py` | `SensitiveInstall`, `with_sensitive_confirm`, `Install` unchanged | ✓ VERIFIED | Adapter present; `Install` protocol parameter list unchanged (confirmed by source read) |
| `installer/render.py` | `render_post_install_handoff` | ✓ VERIFIED | Present, markup disabled on instruction lines |
| `installer/app.py` | console confirm binding, renderer wiring | ✓ VERIFIED | `with_sensitive_confirm`, `render_post_install_handoff` both referenced |
| `installer/deps.py` | byte-unchanged resolver contract | ✓ VERIFIED | No version/ownership coupling; `satisfied_by_install` logic intact |
| `.claude/architecture.md` | Phase 14 section, stale clause fixed | ✓ VERIFIED | Section present; stale clause count is 0 |
| Test files (9 files) | coverage for all above | ✓ VERIFIED | `make test`: 2073 passed, 1 skipped, 95.34% coverage (full run, this session) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `setup.py::_build_app` | `ExecuteInputs.version_refresh/updates` | `dataclasses.replace` when `execute=` passed | ✓ WIRED | Confirmed via 14-01-SUMMARY and code read of `setup.py` `_build_app` |
| `ExecuteScreen.on_mount` | update-eligibility predicate | copied verbatim from `action_update_tool` | ✓ WIRED | Same skip-when-status-exists-and-not-outdated rule |
| `ExecuteScreen._execute_worker` | `UpdateService.run` | `ui_common.run_live` wrapping `updates.run(target)` | ✓ WIRED | `execute_screen.py:583` |
| `installer/registry.toml` oh-my-zsh `post_install` | `Tool.post_install` | model.py closed-set validation (pre-existing) | ✓ WIRED | Loads via `load_tools`, confirmed field populated |
| `installer/engine.py::install_tool` post-success | `installer/post_install.py::run_post_install` | direct call, isolated | ✓ WIRED | `engine.py:166-181` |
| `Platform.immutable` | `set_login_shell`'s first guard | unconditional early return | ✓ WIRED | `post_install.py:45-46`, before confirm callback |
| `InstallOutcome.post_install_handoff` | `render_post_install_handoff` | both `run_wizard` and `ExecuteScreen` report closures | ✓ WIRED | Confirmed present in both files, order matches per `ORDER-MATCHES` |
| `ExecuteScreen._ask_sensitive_action` | `installer/session.py::with_sensitive_confirm` | bound in `_execute_worker` | ✓ WIRED | `execute_screen.py:494-503` |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|-------------|--------|----------|
| D-01 | 14-01, 14-02, 14-05 | One update mechanism, two call sites | ✓ SATISFIED | Code + tests confirmed above |
| D-02 | 14-01 | Existing confirm is the only consent for updates | ✓ SATISFIED | Single `push_screen_wait` site; no second update prompt |
| D-03 | 14-02, 14-05 | Blocked-update reason surfaces in post-run summary, reused wording | ✓ SATISFIED | `_render_updates` wording matches `action_update_tool` |
| D-04 | 14-03, 14-05 | Immutable host hard guard, unconditional, first | ✓ SATISFIED | `post_install.py:45-46` |
| D-05 | 14-03, 14-04, 14-05 | Explicit confirmation required; unattended = skip | ✓ SATISFIED | Both console and in-app entry points gated; behavioral tests pass |
| D-06 | 14-03, 14-04, 14-05 | Dispatched from oh-my-zsh install ladder only | ✓ SATISFIED | `engine.py` post-success dispatch; single declarer test |
| D-07 | 14-03 | zsh only, no shell parameter | ✓ SATISFIED | `test_only_oh_my_zsh_declares_a_post_install_action`; single-entry table |

No orphaned requirement IDs: `.planning/REQUIREMENTS.md` contains no Phase 14 entries (phase explicitly has no REQUIREMENTS.md traceability per ROADMAP.md and 14-CONTEXT.md), and all D-01..D-07 are claimed by at least one plan's frontmatter `requirements:` field.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in any of the 6 phase-modified production files | — | none |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Update-dispatch tests | `pytest tests/test_execute_screen.py -k 'outdated or confirm or blocked_update or sensitive' -q` | 32 passed | ✓ PASS |
| Post-review regression test (WR-01 fix) | `pytest tests/test_execute_screen.py -k refresh_failure_on_missing_ownership -q` | 1 passed | ✓ PASS |
| set_login_shell gate matrix | `pytest tests/test_post_install.py tests/test_engine.py -k 'login_shell or immutable or confirm' -q` | 11 passed | ✓ PASS |
| Console unattended sensitive-skip | `pytest tests/test_app.py -k sensitive_unattended -q` | 1 passed | ✓ PASS |
| In-app unattended sensitive-skip | `pytest tests/test_execute_screen.py -k sensitive_unattended -q` | 1 passed | ✓ PASS |
| Architecture doc facts test | `pytest tests/test_docs.py -q` | 3 passed | ✓ PASS |
| Full validate gate | `make validate` | ruff/pyright/bandit/vulture/shellcheck all clean | ✓ PASS |
| Full test suite (run once, this session) | `make test` | 2073 passed, 1 skipped, 95.34% coverage | ✓ PASS |

### Probe Execution

Not applicable — this phase has no `scripts/*/tests/probe-*.sh` probes; verification relies on the project's own pytest/make gates (above).

## Notes on the Dual Code Review

`14-REVIEW.md` (internal) and `14-REVIEW-cross-ai.md` (independent opencode pass) both
flagged the same three defects (WR-01 unwrapped refresh call, WR-02 dead cross-thread
attribute, WR-03 silent ownership-still-None drop) in `_run_updates`. These were fixed in
commit `67b9d66`, confirmed present in the current tree by direct source read
(`execute_screen.py:565-575` now wraps the pre-dispatch refresh in `run_live`, records a
skip on unresolved ownership, and `self.update_skips` no longer exists). `IN-01`
(explicit "no" leaves no log line, unlike escape) was left as documented, pre-existing
asymmetry with `_ask_mismatch`; both reviewers treated it as informational only, not a
defect blocking this phase's goal.

`14-REVIEW-cross-ai.md`'s `IN-01` (separate note, not to be confused with the internal
review's `IN-01`) observes that the `--all`/`--categories` console path (`run_wizard`)
still silently no-ops an outdated already-installed tool, because D-01's update-dispatch
split was only wired into `ExecuteScreen` (the real `make setup` TUI path), not into
`run_wizard`. This is explicitly out of this phase's scope per 14-01-PLAN.md ("Phase 13
rewired the interactive flow... the genuine `make setup` path goes... `ExecuteScreen`"),
and the phase goal names "the catalog shows as outdated and pressing enter" — the TUI
catalog flow — not the CLI-flags-only console path. Recorded here for visibility, not as
a gap against this phase's stated goal.

### Observation: ROADMAP.md checkbox/plan-count staleness (non-blocking)

`.planning/ROADMAP.md` still shows `**Plans:** 1/5 plans executed` and only `14-01-PLAN.md`
checked off, even though all 5 SUMMARY.md files exist, all 5 plans' commits are on this
branch, and `make validate && make test` is green on the full tree. This is expected
roadmap-bookkeeping lag (updated by the ship/complete workflow after verification), not a
functional gap — the actual code, not the roadmap checkbox, is what this report verifies.

## Gaps Summary

None. All 20 derived must-have truths (drawn from all 5 plans' `must_haves.truths`
frontmatter, cross-referenced against ROADMAP.md's Phase 14 goal) are verified against the
current codebase — not just against SUMMARY.md claims. The three defects found by the dual
code review were independently confirmed fixed by reading the current source
(`installer/execute_screen.py`), not by trusting the SUMMARY's self-report. `make validate`
and a full `make test` run (executed fresh in this verification session) both pass:
2073 passed, 1 skipped, 95.34% coverage, zero lint/type/security findings.

---

_Verified: 2026-09-14T19:10:00Z_
_Verifier: Claude (gsd-verifier)_
