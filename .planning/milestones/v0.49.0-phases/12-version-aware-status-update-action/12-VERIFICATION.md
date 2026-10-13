---
phase: 12-version-aware-status-update-action
verified: 2026-09-07T00:00:00Z
status: passed
score: 21/21 must-haves verified
behavior_unverified: 0
overrides_applied: 0
closure_note: |
  The single item this verification originally routed to `human_needed` (see the
  "Human verification (closed)" section below for the original request) was a
  pure test-coverage gap, not a behavior requiring a real machine mutation to
  confirm: `installer/catalog_tui.py`'s
  `_update_tool_worker`/`on_tool_updated` had zero direct test coverage on the
  worker body and outcome-formatting branches. It has since been closed with
  Textual Pilot-driven tests added to `tests/test_catalog_tui.py` that press the
  real `u` binding on a `CatalogScreen` mounted inside a `UnifiedApp`, wired to a
  real `UpdateService` with injected fakes for the runner/manager-query seams
  (never a real subprocess) — exercising the actual keypress -> `UpdateService.run()`
  -> `post_message(ToolUpdated)` -> `on_tool_updated` -> status-line pipeline:
    - `test_update_success_renders_new_version_on_status_line` — `status="updated"`.
    - `test_update_success_reports_replay_cleanup_and_postinstall_warnings` —
      `status="updated"` with `replayed_globals`, `cleanup_warnings`, and
      `postinstall_warning` all populated in one run (pnpm-id tool; download and
      postinstall-hook seams faked via monkeypatch, no real subprocess or network).
    - `test_update_failure_renders_status_line` — `status="failed"` (runner raises
      `CommandError`).
    - `test_update_unknown_owner_refusal_from_fresh_reresolution` — `status="unknown-owner"`
      surfaced through `on_tool_updated`'s outcome-formatting path specifically (a
      fresh re-resolution at mutation time disagreeing with the cached pre-flight
      ownership), distinct from the pre-flight gate's own unknown-owner refusal
      (already covered before this closure).
    - `test_second_update_press_shows_already_in_flight` — pressing `u` twice in
      quick succession (deterministically, via a blocking-runner `Event` rather
      than a timing-dependent race) shows the "update already in flight" message
      on the second press instead of starting a second update.
  `installer/catalog_tui.py` coverage went from 77% (worker/message-handler
  entirely unexercised, 65 missed statements) to 93% (14 missed statements, all
  remaining defensive guard branches not part of the four required outcome
  shapes) per `pytest --cov=installer.catalog_tui`. `make validate && make test`
  both pass clean on the resulting tree (1700 passed, 1 skipped, 96.49% total
  coverage). No human check was needed after all — this was closable entirely
  with injected fakes, the same pattern already used throughout this project's
  other worker tests.
---

# Phase 12: Version-Aware Status & Update Action Verification Report

**Phase Goal:** The catalog can answer "what's out of date" and act on it through the tool's own real manager, not just "is it installed".
**Verified:** 2026-09-07
**Status:** passed (see `closure_note` above — the sole `human_needed` item was a closable test-coverage gap, now closed)
**Re-verification:** No — initial verification (this phase has no prior VERIFICATION.md)

### Human verification (closed)

The original verification pass routed one item to `human_needed`:

> **Test:** Press `u` on a disposable/test tool in a sandboxed environment (VM/container, or a throwaway registry entry pointed at a scratch `~/Applications`/`~/.local/bin`/PATH — never a real installed tool on this machine) and observe the full pipeline: `action_update_tool` → `UpdateService.begin` → `_update_tool_worker` → `UpdateService.run` → `post_message(ToolUpdated)` → `on_tool_updated`.
> **Expected:** The status line renders correctly for each `UpdateOutcome.status` branch — `updated` (with `replayed_globals`, `cleanup_warnings`, and `postinstall_warning` populated in at least one run each), `failed`, and `unknown-owner` — with no `AttributeError`/`KeyError` from the f-string formatting, and the in-flight guard message ("update already in flight for …") appears when `u` is pressed a second time before the first run completes.
> **Why human (at the time):** 12-REVIEW.md's own WR-01 finding — the worker body and outcome-formatting branches had 0% test coverage, and this verification pass was barred from exercising the mutating action live against this machine.

**Closed:** on further review this did not actually require a human/live-machine check — it was a pure test-coverage gap, closable the same way every other worker in this codebase is tested: a Textual Pilot driving the real keypress against a real `CatalogScreen`/`UpdateService`, with fakes only at the runner/manager-query seams. See `closure_note` in the frontmatter above for the tests added and the resulting coverage numbers.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + PLAN must-haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | Catalog shows current vs. latest per `github_release`-kind tool, reusing `resolve_github_tag` | ✓ VERIFIED | `installer/catalog_tui.py:163` adds `("Ver", "ver")` to `_COLUMNS`; `_ver_cell`/`_row_cells` (catalog_tui.py:296-371) read `self._version_statuses`, populated only from a real `VersionRefreshService.refresh()` call (see key-link trace below); `installer/version_status.py:173` calls `resolve_tag(repo)` (the unchanged `resolve_github_tag`, `installer/versions.py`) exactly once per stale `github_release` tool. |
| SC2 | Version checks cached with `checked_at`; entries >7 days stale, trigger background re-check, not full refetch | ✓ VERIFIED | `installer/version_cache.py`: `STALE_AFTER = timedelta(days=7)` (line 40), `is_stale`/`_parse_iso` (lines 61-184) gate on a timezone-aware, UTC-normalized timestamp with `FUTURE_SKEW` guard against a bogus future value; a fresh (<7d) entry reconstructs a full `VersionStatus` without a network call (`version_status.py` fresh-cache path); staleness is rendered as a trailing dim `~` marker read by `catalog_tui._row_cells`, not merely computed. `RETRY_BACKOFF`/`failed_at` (version_cache.py:41-42, 192-193) bound retries on failed lookups. |
| SC3 | Version checks run via a Textual `Worker`, never block first paint/keypresses; network failures degrade to "unknown" | ✓ VERIFIED | `@work(thread=True, exclusive=True, group="version-refresh", exit_on_error=False)` on `_refresh_versions_worker` (catalog_tui.py:272); fires from `on_mount`/`enter_view` (lines 258-263), never on the render path; `run_live` wraps the refresh call so an exception cannot crash the worker; a version this parser cannot rank/probe renders `unknown` (`versions.py::parse_status_version`/`is_outdated` return `None` on an unparseable shape, live-verified against `dasel`/`gron`/`lazygit`/`procs` per PLAN must-haves). |
| SC4 | An "update" action exists and delegates to the tool's actual owning manager, not assumed to be this installer | ✓ VERIFIED | `installer/ownership.py::resolve_ownership` (not `resolve_methods()[0]`) is the sole ownership authority; `installer/update.py::UpdateService.run` re-resolves ownership fresh at mutation time (line 368) and dispatches via `_perform`'s owner branch (`brew`/`cask`/`uv` argv, `pnpm` via the `_node` executor, `installer` via `download.update_download`/`apps.update_app`/script executor) — see full trace below. `u` is bound in `CatalogScreen.BINDINGS` (catalog_tui.py:203) AND registered in `ui_common.py`'s `VIEWS` table (`actions="... | u update"`, lines 114/124/134) per architecture rule 1. |
| SC5 | (Stretch, deferred) manager-drift alert | N/A — explicitly deferred | ROADMAP.md Phase 12 SC#5 wording amended 2026-09-07 with the structural reason (`brew outdated` cannot see an uninstalled brew alternative; zero registry rows declare both a node/uv-tool and a brew/cask method); `.planning/REQUIREMENTS.md` records the same deferral; `tests/test_ownership.py::test_abandoned_drift_helpers_are_absent` pins that no unwired `has_declared_manager_drift`/`manager_drift_alert` helper exists. This is a legitimate, documented, in-scope deferral (12-CONTEXT.md D-02's "planner's call" clause), not a missed criterion. |

**Score (ROADMAP SCs):** 4/4 MVP criteria verified; SC#5 correctly and transparently deferred (not counted as a gap).

### Re-confirmed Safety Properties (the three the task specifically asked to re-verify)

These three properties had real Critical-severity bugs found by a dual-lane code review (`12-REVIEW.md`) after execution, which were then fixed with regression tests. Re-verified here **independently from current source**, not from the review's own narrative.

| # | Property | Status | Evidence |
|---|----------|--------|----------|
| 1a | `parse_brew_list_versions` fails closed on malformed/unrecognized input | ✓ VERIFIED | `installer/ownership.py:121-147`: requires the first token to match `_BREW_NAME_RE` (no stray punctuation) and every remaining token to match `_BREW_VERSION_RE` (`latest` or digit-led); any line failing either check returns `None` for the WHOLE parse, not a per-line skip. Confirmed against `parse_brew_list_versions("warning: inventory format changed\n") is None` directly, and by `tests/test_ownership.py::test_parse_brew_list_versions_warning_line_fails_closed` (a genuine assertion, not tautological). |
| 1b | `parse_uv_tool_list` fails closed on unrecognized structure | ✓ VERIFIED | `installer/ownership.py:150-177`: an indented/`- ` entry-point line is only accepted when `expect_entrypoint` was set by an immediately-preceding matched `name vX.Y` line; one with no preceding match returns `None` for the whole parse. Confirmed directly (`parse_uv_tool_list("- graphify\n") is None`) and by `tests/test_ownership.py::test_parse_uv_tool_list_entrypoint_without_preceding_match_fails_closed`. The identical pattern is independently re-verified in the sibling `installer/manager_versions.py::parse_uv_tool_outdated` (lines 127-155). |
| 1c | pnpm/uv-outdated parsers fail closed | ✓ VERIFIED | `installer/manager_versions.py::parse_brew_outdated_json`/`parse_pnpm_outdated_json`/`parse_uv_tool_outdated` all return `None` on a non-dict payload, a missing required key, a non-string/empty name or version field, or an unrecognized line shape (lines 52-155). `installer/pnpm_globals.py::_load_projects`/`_iter_dependencies` (lines 270-298) require every project object to carry at least one of `_KNOWN_PROJECT_KEYS` and every dependency value to be a `dict`, or the whole parse fails closed — confirmed directly against the C1 finding's own reproduction shapes. |
| 1d | `owner_dirs` prevents a cask-installed app from resolving `owner="installer", confidence="direct"` | ✓ VERIFIED | `installer/ownership.py::owner_dirs` (lines 231-270) deliberately lists `applications_dir()` for BOTH `"installer"` and `"cask"` (with an explanatory docstring naming exactly this failure mode). Traced `resolve_ownership` by hand for the VS-Code-shaped scenario: `attribute_path` returns `{"installer","cask"}` for a path under `~/Applications`, so `matching` has length 2, `active_candidate` stays `None`, and the function falls into the `active_path is not None` branch returning `unknown` — never the single-candidate-wins `direct` branch. Confirmed by `tests/test_ownership.py::test_cask_installed_app_never_wins_installer_direct_ownership`, which builds a real VS-Code-shaped `Tool`/bundle/symlink and asserts `not (result.owner == "installer" and result.confidence == "direct")`. |
| 2 | `UpdateService.run` REFUSES to proceed with a pnpm self-update (zero mutation) when the pre-update snapshot capture failed | ✓ VERIFIED | `installer/update.py::UpdateService.run` (lines 366-423): `should_replay_node_globals(fresh_target)` is checked BEFORE `perform_update` is called (lines 378-396); when `self._managed_packages()` returns `None`, the function returns `UpdateOutcome(status="failed", ...)` immediately and `perform_update` is never invoked — zero subprocess, zero filesystem write for the pnpm self-update itself. Confirmed directly by reading the control flow (the `return` on line 387-395 is unconditional and precedes the `perform_update` call on line 397) and by `tests/test_update.py::test_update_service_none_snapshot_refuses_to_mutate`, which asserts `perform_calls == []` (not merely `status == "failed"`) — i.e. the test proves zero mutation, not just a status string. |
| 3 | `recover_update_remnants` never deletes `.old` based merely on `live` existing; `.old`'s presence wins | ✓ VERIFIED | `installer/atomic.py::recover_update_remnants` (lines 78-114): unconditionally, `if not old.exists(): return` (i.e. `.old` absent is the ONLY early-exit); otherwise `if live.exists(): shutil.rmtree(live)` THEN `os.replace(old, live)` — `.old` always wins when present, and `live`'s mere existence is never treated as proof of validity. Confirmed directly against the C4 finding's exact scenario (both `live` and `.old` present after a crashed mid-swap update) and by `tests/test_atomic.py::test_recover_update_remnants_never_deletes_old_when_live_also_exists`, which plants unvalidated content in `live` and known-good content in `.old`, then asserts `not old.exists()` AND `(live / "rg").read_text() == "known-good-content"` — i.e. the known-good tree wins, not merely "old is gone." |

**All three requested safety properties hold under independent re-verification**, and each is backed by a non-tautological regression test that asserts the actual safety-relevant outcome (zero mutation calls, correct winning content), not just a status label.

### Deferred Items

None beyond ROADMAP SC#5, which is explicitly and correctly documented as deferred in-line (see table above) — not treated as a gap by the roadmap itself, so nothing further to defer here.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/atomic.py` | one shared atomic-write + update-remnant-recovery implementation | ✓ VERIFIED | 130 lines; `atomic_write_bytes`/`atomic_write_text` used by `installer/omz.py`, `installer/daemon.py`, `installer/version_cache.py` (grep-confirmed single implementation, three consumers); `recover_update_remnants`/`replace_symlink` substantive and tested (97% coverage). |
| `installer/version_cache.py` | timezone-validated JSON cache incl. manager-report snapshot | ✓ VERIFIED | 361 lines; `_parse_iso`, `FUTURE_SKEW`, `STALE_AFTER`, `RETRY_BACKOFF`, `MANAGER_STALE_AFTER`/`MANAGER_RETRY_BACKOFF` all present and substantive (88% coverage). |
| `installer/version_status.py` | `VersionRefreshService` with epoch, `invalidate`, fresh-cache reconstruction | ✓ VERIFIED | 559 lines; `epoch`/`invalidate` (lines 379-407), `_partial_manager_failure` fix (finding #9) present (91% coverage). |
| `installer/ownership.py` | ownership as a distinct, evidence-based concept | ✓ VERIFIED | 545 lines; `resolve_ownership`, `MUTATION_GRADE`, `ManagerOwnership` with `candidates`/`active_candidate`/`active_path`/`unknown_reason` evidence fields, all substantive (90% coverage). |
| `installer/manager_versions.py` | one batched outdated query per manager, fail-closed parsers | ✓ VERIFIED | 207 lines; `brew_outdated`/`pnpm_outdated_global`/`uv_tool_outdated`/`read_outdated`, all fail-closed on malformed input (86% coverage). |
| `installer/update.py` | ownership-gated update action, pnpm-safe, rollback-safe | ✓ VERIFIED | 422 lines; `UpdateService`, `perform_update`, `should_replay_node_globals`, full owner dispatch (91% coverage). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `setup.py::_build_app` | `VersionRefreshService`/`UpdateService` construction | real `Platform`, `resolve_tag`, `probe_version_output`, `invalidate=version_refresh.invalidate` | ✓ WIRED | `setup.py:63-65,388,408,416,436` — both services are constructed at the real composition root and threaded into `UnifiedApp`, not TUI-only. |
| `CatalogScreen.on_mount`/`enter_view` | `VersionRefreshService.refresh` | `@work(thread=True, exclusive=True, group="version-refresh", exit_on_error=False)` + `run_live` | ✓ WIRED | catalog_tui.py:258-284; `on_version_status_refreshed` (286-294) drops a message whose `generation` or `epoch` is stale before applying it to `self._version_statuses`, which `_row_cells`/`_ver_cell` read directly — real background-refresh-to-render pipeline, not a static value. |
| `CatalogScreen.action_update_tool` (`u` keypress) | `UpdateService.run` | `begin()` in-flight guard → `_update_tool_worker` (`exit_on_error=False`, `finally`-posted) → `run_live(service.run)` | ✓ WIRED (code-level; not behaviorally exercised — see Human Verification) | catalog_tui.py:543-595; field names on both sides (`UpdateTarget(tool=, ownership=)`, `UpdateOutcome.detail/replayed_globals/cleanup_warnings/postinstall_warning`, `ToolUpdated(tool_id, outcome, status, error, epoch)`) traced and confirmed to match exactly — no static defect found — but WR-01 (12-REVIEW.md) documents 0% coverage on this exact pipeline, and this verification is barred from exercising it live. |
| `ownership.MUTATION_GRADE` | `update.perform_update`'s refusal gate AND `CatalogScreen.action_update_tool`'s pre-flight refusal | imported, not restated | ✓ WIRED | `installer/update.py:214` and `installer/catalog_tui.py:559` both import and check against `ownership.MUTATION_GRADE`/`ownership.owner == "unknown"`. |
| pnpm-owned update | `installer/executors.py::execute` with the tool's own `node` method | never a raw `pnpm update -g` argv | ✓ WIRED | `installer/update.py:236-239` (`elif owner == "pnpm": executors.execute(method, runner)`), confirmed no `pnpm update` / `pnpm add --latest` argv construction exists anywhere in `update.py`. |
| `UpdateService.run` success | `VersionRefreshService.invalidate` | epoch bump + manager-snapshot drop, isolated in `try/except` (W2 fix) | ✓ WIRED | `installer/update.py:412-419`; a cache-write failure appends a warning to `detail` rather than downgrading `status` from `"updated"`, confirmed by `tests/test_update.py::test_update_service_invalidate_failure_stays_updated`. |
| tool declaring `postinstall` | `installer/postinstall.py::run_postinstall` re-dispatch after successful update | isolated try/except, carried on `UpdateOutcome.postinstall_warning` | ✓ WIRED | `installer/update.py:246,279-294`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `catalog_tui.CatalogScreen._ver_cell` | `self._version_statuses` | `VersionRefreshService.refresh(self.tools)` via the real background worker, posted through `VersionStatusRefreshed` | Yes | ✓ FLOWING |
| `catalog_tui.CatalogScreen._detail_text` (owner/unknown-reason) | `ownership.unknown_reason`/`ownership.candidates` | `VersionRefreshService.ownership_of(tool_id)`, itself populated by `resolve_ownership` against real `read_inventory`/`read_outdated` snapshots | Yes | ✓ FLOWING |
| `update.py::UpdateService.run` mutation dispatch | `fresh.owner`/`fresh.confidence` | `self._reresolve_ownership(target.tool)` — production wiring (`setup.py:396-406`) calls `read_inventory`/`shutil.which` directly, bypassing the cache, at mutation time | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `make test` (`uv run pytest --cov`) | `1695 passed, 1 skipped in 124.42s`, `Total coverage: 96.35%` (required 90.0%) — the 1 skip is `tests/test_daemon.py:288` (launchctl opt-in gate), pre-existing and unrelated to Phase 12 | ✓ PASS |
| Full quality gate passes | `make validate` (ruff check, ruff format --check, pyright, bandit, vulture, shellcheck) | ruff: all checks passed; format: 108 files already formatted; pyright: 0 errors/0 warnings; bandit: clean (project's own documented B404/B603/B310 skips); vulture: clean; shellcheck: clean | ✓ PASS |
| C1 regression: brew warning line rejected | Direct read + `pytest -k test_parse_brew_list_versions_warning_line_fails_closed` (existence confirmed by name match; full suite already run above covers execution) | `parse_brew_list_versions("warning: inventory format changed\n") is None` (traced by hand against the regex checks) | ✓ PASS |
| C2 regression: VS-Code-shaped cask/app collision | Direct trace of `resolve_ownership` against `test_cask_installed_app_never_wins_installer_direct_ownership`'s fixture | `matching` has length 2 → `active_candidate=None` → falls to `unknown`, never `installer`/`direct` | ✓ PASS |
| C3 regression: pnpm self-update refuses on unreadable snapshot | Direct trace of `UpdateService.run` control flow | `perform_update` is never called when `self._managed_packages()` returns `None`; outcome `status="failed"` | ✓ PASS |
| C4 regression: `.old` always wins over `live` | Direct trace of `recover_update_remnants` | `.old` presence is the sole gate; `live` is discarded first when both exist | ✓ PASS |
| No orphan drift-alerting helper shipped | `grep -rn "has_declared_manager_drift\|manager_drift_alert" installer/ tests/` | Zero production hits; only referenced inside the guard test's own docstring/body (`tests/test_ownership.py::test_abandoned_drift_helpers_are_absent`) | ✓ PASS |
| No debt markers in phase-touched files | `grep -n -E "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` across all 14 core Phase 12 files | Zero matches | ✓ PASS |

### Probe Execution

Not applicable — this phase has no `scripts/*/tests/probe-*.sh` convention; verification uses the project's own `make validate`/`make test` gates instead, both run above.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|--------------|--------|----------|
| REQ-version-aware-status-github | 12-01 | Resolve current version, compare to `resolve_github_tag`; unknown on unreliable check | ✓ SATISFIED | SC1 row above |
| REQ-cached-timestamped-version-state | 12-01 | Timestamped JSON cache, stale marker at 7 days, background re-check | ✓ SATISFIED | SC2 row above |
| REQ-background-version-refresh-worker | 12-01 | Textual `Worker`, non-blocking, degrades to unknown on failure | ✓ SATISFIED | SC3 row above |
| REQ-manager-version-resolution | 12-02 | Per-manager `Runner`-shaped outdated resolution, verified exact commands | ✓ SATISFIED | `installer/manager_versions.py`, live-verified `brew outdated --json=v2` command per ROADMAP replan note |
| REQ-update-action-manager-delegation | 12-03 | Manual update action delegating to actual owning manager | ✓ SATISFIED | SC4 row above; safety properties 1-3 above |
| REQ-manager-drift-alerting | 12-04 | Alert on pnpm/npm-managed tool with newer brew version | ✓ DEFERRED (documented) | ROADMAP.md, REQUIREMENTS.md, `.claude/architecture.md` all record the deferral with structural reasons; `test_abandoned_drift_helpers_are_absent` guards against a silently-shipped unwired helper |
| REQ-pnpm-global-reinstall-mitigation (automatic-trigger half) | 12-03 | Automatic post-pnpm-update snapshot/replay | ✓ SATISFIED | `should_replay_node_globals`, capture-before-mutate ordering (safety property 2 above) |

No orphaned requirements — all seven REQ-IDs mapped to Phase 12 in REQUIREMENTS.md are claimed by at least one plan and have corresponding code evidence.

**Documentation-bookkeeping gap (non-blocking, same pattern flagged in 11-VERIFICATION.md):** `.planning/REQUIREMENTS.md`'s top checklist (lines 84-89) still shows `- [ ]` and its status table (lines 154-158) still shows "Pending" for REQ-version-aware-status-github, REQ-cached-timestamped-version-state, REQ-background-version-refresh-worker, REQ-manager-version-resolution, and REQ-update-action-manager-delegation, even though the code evidence above shows all five are genuinely implemented, reviewed, and tested. Every other completed phase in this file uses "Complete"/"Done" for its requirement rows (e.g. Phase 11's three REQs). 12-04-PLAN.md's must-haves only covered the REQ-manager-drift-alerting deferral record, not marking the other five as done, so this was never in scope for any plan and is a bookkeeping omission, not a code gap. Recommend updating REQUIREMENTS.md's checkboxes and status table to "Done" for these five requirements as a small follow-up.

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/placeholder markers in any of the 14 files this phase created or substantially modified (`installer/ownership.py`, `installer/manager_versions.py`, `installer/update.py`, `installer/atomic.py`, `installer/version_cache.py`, `installer/version_status.py`, `installer/versions.py`, `installer/catalog_tui.py`, `installer/download.py`, `installer/apps.py`, `installer/run.py`, `installer/pnpm_globals.py`, `setup.py`, `installer/ui_common.py`). No orphan helpers (rule 5): `has_declared_manager_drift`/`manager_drift_alert` are confirmed absent from production code by both a grep sweep and a dedicated pinning test.

### Test Quality Audit (targeted at the three re-confirmed safety properties)

| Test | Linked Property | Active | Circular | Assertion Level | Verdict |
|------|-----------------|--------|----------|------------------|---------|
| `test_parse_brew_list_versions_warning_line_fails_closed` | 1a | Yes | No — asserts against a hand-written input string, not against the parser's own generated output | Value (`is None`) | Sufficient |
| `test_parse_uv_tool_list_entrypoint_without_preceding_match_fails_closed` | 1b | Yes | No | Value (`is None`) | Sufficient |
| `test_cask_installed_app_never_wins_installer_direct_ownership` | 1d | Yes | No — builds a real filesystem fixture and real `Tool`/`Method` objects | Behavioral (asserts the specific forbidden outcome does not occur, and confirms a real reproduction case) | Sufficient |
| `test_update_service_none_snapshot_refuses_to_mutate` | 2 | Yes | No | Behavioral (`perform_calls == []`, not just a status string) | Sufficient — this is the strongest form of test for this property, since it proves the absence of a side effect rather than a return value |
| `test_recover_update_remnants_never_deletes_old_when_live_also_exists` | 3 | Yes | No | Value/Behavioral (asserts the surviving file's actual content, not just existence) | Sufficient |

**Disabled tests on these properties:** 0. **Circular patterns:** 0. **Insufficient assertions:** 0.

### Gaps Summary

No BLOCKER-level gaps. All four MVP success criteria (SC#1-4) are genuinely implemented, wired end-to-end from `setup.py`'s composition root through to the rendered catalog row, and covered by a passing test suite (1695 passed, 96.35% coverage, `make validate` clean). SC#5 was legitimately and transparently deferred with a documented structural reason, not silently dropped.

The three safety properties this verification was specifically asked to re-confirm — fail-closed inventory parsing (including the `owner_dirs` cask/installer collision), the pnpm snapshot-before-mutation refusal, and the crash-recovery `.old`-wins invariant — all hold under independent, from-scratch re-reading of the current source, each backed by a genuine (non-tautological) regression test that asserts the actual safety-relevant outcome.

The one item originally routed to human verification — the full `u`-keypress → `UpdateService.run` → status-line rendering pipeline in `installer/catalog_tui.py` (`_update_tool_worker`/`on_tool_updated`) having zero direct test coverage on its worker body and outcome-formatting branches (12-REVIEW.md's WR-01) — has since been closed with Pilot-driven tests (see "Human verification (closed)" above and the frontmatter `closure_note`). It turned out not to require a live machine or human observation at all: a real trip through the Textual message queue, with fakes only at the runner/manager-query seams, was sufficient to exercise every required outcome shape (`updated` with all three optional fields populated, `failed`, `unknown-owner`, and the in-flight guard). No remaining gaps.

---

_Verified: 2026-09-07_
_Human-verification item closed: 2026-09-07_
_Verifier: Claude (gsd-verifier)_
