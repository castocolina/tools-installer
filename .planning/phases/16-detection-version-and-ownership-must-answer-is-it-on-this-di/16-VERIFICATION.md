---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
verified: 2026-10-11T00:37:57Z
status: passed
score: 7/7 must-haves verified
covered_files:
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-01-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-01-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-02-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-02-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-03-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-03-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-04-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-04-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-05-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-05-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-06-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-06-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-07-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-07-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-08-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-08-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-09-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-09-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-10-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-10-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-11-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-11-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-12-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-12-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-13-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-13-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-14-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-14-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-15-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-15-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-16-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-16-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-17-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-17-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-18-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-18-SUMMARY.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-19-PLAN.md
  - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-19-SUMMARY.md
  - installer/app.py
  - installer/catalog_tui.py
  - installer/engine.py
  - installer/execute_screen.py
  - installer/executors.py
  - installer/guidance.py
  - installer/install_ownership.py
  - installer/locations.py
  - installer/model.py
  - installer/ownership.py
  - installer/post_install.py
  - installer/rcclean.py
  - installer/registry.toml
  - installer/resolve.py
  - installer/selection.py
  - installer/shellrc.py
  - installer/skill_lifecycle.py
  - installer/status.py
  - installer/uninstall.py
  - installer/update.py
  - installer/version_cache.py
  - installer/version_status.py
  - installer/wizard_app.py
  - setup.py
covered_digest: "v3:sha256:5ae837abf61ec1c8ef0dc4b399c617dae719b6b627e6d43baabe47f08e7635ca"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 7/7
  gaps_closed: []
  gaps_remaining: []
  regressions: []
advisory: []
human_verification:
  - test: "Execute-screen enter on a real host: select a current tool (e.g. wezterm), open the execute screen, read the on-mount preflight, then press enter."
    expected: "Preflight `wezterm already current — nothing to do.`; enter completes without `Install 0 tools` and without rewriting rc files unexpectedly."
    why_human: "Enter runs `configure_path` against the real rc files. The preflight text is proven by the Textual pilot test `test_current_only_selection_says_already_current_not_install_zero`; only the live-host enter path is unobserved."
  - test: "Real-machine day-to-day pass: use the catalog and Doctor for a normal session on a host that has a dangling pnpm shim (puppeteer on this host currently reads `!`)."
    expected: "Rows keep telling the truth under real use: no silent `u`, no false `broken`, Doctor guard offers only lines it can safely rewrite."
    why_human: "Experience on a real machine over time. The mmdc dangling-shim repro no longer exists on this host (D-18 is fixture-proven; puppeteer is a live true positive)."
  - test: "Review the 11 judgment-tier plan prohibitions (see Prohibitions table). The verifier's verdict on each is non-authoritative."
    expected: "Human agrees each must-NOT held (verifier found no violation, including after the 16-17/16-18/16-19 edits)."
    why_human: "Judgment-tier prohibitions need explicit human resolution; none has a fail-first test."
---

# Phase 16: Catalog truth (detection, version, ownership) Verification Report

**Phase Goal:** Every catalog row tells the truth about a tool that is on the disk: it is reported installed whether or not the current process can run it, it shows a version when one is knowable, it names whichever manager actually owns it, and when it cannot be installed or updated the row says why instead of going silent. Proven against the real defects below on a host that reproduces each one.
**Verified:** 2026-10-11T00:37:57Z
**Status:** human_needed
**Re-verification:** Yes. The 2026-10-10T19:30Z report (human_needed, 7/7, no gaps) went stale when 9050446 changed `installer/wizard_app.py` and `installer/ownership.py` (41d642c is docs only). This run re-checks those two edits against truths 1, 2, 4 and 5 and regression-checks the rest. Earlier history: e91bce3, gap plans 16-17..16-19, 16-UI-CHECK.md, review dispositions.

## Goal Achievement

### Observable Truths

ROADMAP has no `success_criteria` list for this inserted phase; truths come from the goal, its five defects and the in-scope foreign-PATH work (D-21..D-24).

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Skill packs present on disk read installed (defect 1) | ✓ VERIFIED | Re-run on host via `inspect_skill_packs(..., run_probe, home)`: ponytail `claude+codex` present, superpowers `claude, pi`, softaworks `claude, codex`, opengsd `claude, codex, cursor, opencode`; matt-pocock-skills absent everywhere (correct). openspec/spec-kit `{}` hosts now use the PATH answer (`_present`, catalog_tui.py:482, WR-03 fix) instead of an empty-Ver "missing". tmux row 3 shows Inst `✓` and host list for all four. |
| 2 | A tool on disk reads installed whether or not this process can run it | ✓ VERIFIED | 9050446: every catalog view entry re-derives the installed map from the live `is_installed` predicate (`_rederive_installed`, wizard_app.py:2903-2918, shared with `_install_closed`). A tool removed on Uninstall no longer keeps its ✓. `test_returning_from_another_view_rederives_the_installed_map` passes (`○` after presence flips). esc also goes through `show_view` (`action_back`). `is_installed` is filesystem-only with no subprocess, so the sync re-read on navigation is cheap. kitty and bun resolve `owner=installer` / `own installer` on host via declared `bin_dir`. IN-10 edit (ownership.py:602-614) makes a non-active location candidate a shadow instead of a blocker; regression run shows kitty/bun/sdkman/wezterm unchanged. |
| 3 | A version shows when one is knowable (defect 2) | ✓ VERIFIED | Host `resolve_status(allow_fetch=False)`: springbootcli `4.1.0` (sdkman), sdkman `5.23.0` (installer), groovy `5.0.7` (brew). tmux row 2: no `no version` for the SDKMAN family. |
| 4 | The Owner names the manager that actually owns the tool (defect 3, D-01..D-08) | ✓ VERIFIED | 9050446: `show_view` now calls `enter_view()` on the base (system) catalog (wizard_app.py:2696-2698). Before, an install's global epoch bump left system-tier Owner cells blank until restart. `test_returning_to_the_base_tier_re_resolves_ownership_an_install_dropped` passes (`ownership_of("sys-tool")` is None after the install, non-None after `1`). A script-kind `installer` record now gets the removal text "installed by its own installer..." instead of "your package manager" (`_own_script_install`, ownership.py:1436-1444). That reaches the Uninstall row through `setup._uninstall_owner_hint`/`_uninstall_owner_label` into `classify_tools`' managed branch, and `test_script_kind_installer_record_names_its_own_installer_not_a_package_manager` passes. Host `resolve_ownership`: groovy, gradle, maven, java (package `openjdk`), mmdc all `brew`, `off_policy=True`; springbootcli `SDKMAN`; sdkman, kitty, bun `own installer`. tmux row 1 shows `Homebrew ≠ policy` and the declared-manager sentence for all four. |
| 5 | A row that cannot install or update says why (defects 4 and 5, broken shim) | ✓ VERIFIED | Host: alacritty `immutable host` with full detail, gnu-bash `fedora not supported`, kitty None. `u` on a current row says `already current`, or `current as of the last check` when stale (IN-15, catalog_tui.py:915). Pilot test `test_current_only_selection_says_already_current_not_install_zero` passes in the full suite; broken shim and repair paths covered by their tests. puppeteer shows `!` on this host, which is a correct D-18 positive. |
| 6 | Doctor guards a foreign unguarded PATH line in place, with backup, per-file opt-in, never inside another tool's block (D-21..D-24) | ✓ VERIFIED | Host scan via `path_writer_lines_for` re-run (read-only) after the rcclean/shellrc edits: identical to the earlier result (`.bashrc` 52 guardable, 70 refused as `my-kitty PATH` block, other six lines guardable). `guard_path_writers` still does backup then re-snapshot then atomic write; WR-01 only changes the refusal wording (`flow="guard"`). rc hashes unchanged. |
| 7 | Proven on a host that reproduces each defect | ✓ VERIFIED | Defects 1-4 and the D-22 Doctor text: headless host proof re-run here and rendered rows captured by tmux in 16-UI-CHECK.md (rows 1-4, 6, 7 pass, rc-file sha256 identical before and after). Defect 5: the pilot test drives the real execute screen. Residual live-only items are styling and enter on a real host, listed below. |

**Score:** 7/7 truths verified (0 present-but-behavior-unverified)

### Regression check after gap plans

| Change | Risk | Result |
|--------|------|--------|
| 16-17 rcclean (`_code_text`, heredoc, `_has_command_suffix`, `_REFUSE_REPLACE`), `path_scan_rc_paths` OSError, shellrc guard wording | Doctor scan or guard regression | Host scan identical; tests/test_rcclean.py, test_shellrc.py, test_locations.py pass |
| 16-18 ownership shadows, skill pack `status_probes`, install handoff framing, install-state `match`, duplicate harness, stale wording, registry comments | Owner/inst regression | Host ownership table unchanged; test_ownership, test_skill_lifecycle, test_model, test_registry, test_catalog_tui pass |
| 16-19 `export PATH=... FOO=1` writer, shared enter-hint constants, post-apply Doctor text | Doctor regression | test_rcclean, test_guidance, test_wizard_app pass |
| 9050446 `show_view` re-derive plus base `enter_view`, `_own_script_install` | Navigation stack invariant, warning delivery, Uninstall hint/label pairing (CR-03) | The re-derive runs before pop/push. A failure is queued to `_pending_warnings` and flushed on the visible screen, same as T-15.6-13. `removal_label` is still None for exactly the records where `removal_hint` is None (non-script installer, unknown); the new test asserts both halves. test_ownership, test_wizard_app, test_catalog_tui and test_uninstall all pass (re-run here). |
| Whole tree | Anything else | `make validate` exit 0 (ruff, format, pyright, bandit, vulture, shellcheck); full `pytest --no-cov -x` ran to 100% with no failure. 24 production files unchanged in set vs. the previous report. |

### Required Artifacts

All 24 production files in the phase diff (base `2eaae39`) exist and are substantive and wired; the set is the same as the previous report. Edited since e91bce3: catalog_tui, guidance, locations, model, ownership, rcclean, registry, shellrc, skill_lifecycle, wizard_app (reviewed in the diff, all consumed by existing callers).

### Key Link Verification

All eight links from the previous report still WIRED (setup.py to `VersionRefreshService`, `_refresh_skills_worker` to `refresh_skills(self._catalog)`, `resolve_ownership` to `dangling_shim`, execute_screen to `repair=True` and `reapply_post_install`, setup.py to `unavailable_reason`, DoctorScreen to `guard_path_writers`, catalog_tui to ownership notes). New links: wizard_app imports `GUARD_ENTER_HINT`/`SAFE_FIX_ENTER_HINT` from guidance (NR-04), `backup_precondition(flow="guard")` called from `guard_path_writers`.

### Data-Flow Trace (Level 4)

Owner, Ver, skill Inst/Owner and row reasons all FLOW from real sources on this host (brew inventory, symlink/version_file/path probe, harness CLIs plus disk, per-method rejection); see truths 1-5.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `uv run pytest -q` | green per orchestrator at 41d642c. Not re-run here; the four affected modules were re-run below | ✓ PASS (orchestrator) |
| Affected modules at 41d642c | `uv run pytest -q --no-cov tests/test_ownership.py tests/test_wizard_app.py tests/test_catalog_tui.py tests/test_uninstall.py` | 100%, no failure | ✓ PASS |
| Three new 9050446 tests | `pytest -k "script_kind_installer or rederives_the_installed_map or re_resolves_ownership_an_install_dropped"` | 3 passed | ✓ PASS |
| Phase test modules | rcclean, shellrc, ownership, skill_lifecycle, locations, model, registry, guidance, catalog_tui, wizard_app, execute_screen, version_status, status | all pass | ✓ PASS |
| Gates | `make validate` (re-run here at 41d642c) | exit 0 | ✓ PASS |
| Host ownership/status/reasons/packs/Doctor scan | scratch read-only script using production functions | matches the table above | ✓ PASS |

### Probe Execution

No phase-declared `scripts/*/tests/probe-*.sh`. Step 7c not applicable.

### Requirements Coverage

No REQUIREMENTS.md IDs (inserted phase). D-01..D-24 from 16-CONTEXT.md: all SATISFIED as in the previous report, with D-04 deferred by decision (migration flow is a future phase; D-03 is the text-only offer). D-18 is fixture-proven because the mmdc repro is gone, with puppeteer as a live true positive. No orphans.

### Review Disposition

16-REVIEW-DISPOSITION.md: 26 findings, 18 fixed, 8 accepted (IN-03, IN-04, IN-05, IN-07, IN-08, IN-09, IN-13, NR-03), 0 open. The previous report's WR-01 and IN-01 warnings are fixed (79f859a, 2c92291). Accepted items are info-level heuristic limits (fail safe or label-only); none touches a must-have.

### Deferred Items

None. Later phases not consulted because no gap exists.

### Advisory (New Scope, Unevidenced)

None.

### Prohibitions (judgment-tier, non-authoritative verifier verdict, flagged for human review)

| Plan | Must-NOT | Verifier verdict |
|------|----------|------------------|
| 16-01 | Claim ownership on location alone for inventory kinds | held; IN-10 shadow logic only affects non-active location candidates of declared location kinds |
| 16-02 | Run a command that can download software | held: closed argv table, no npx/dlx |
| 16-02 | Execute registry-supplied argv/path | held; install-state now keyed by a closed `INSTALL_STATE_FILES` table |
| 16-03 | Report a guarded PATH line as a writer | held per rcclean tests (heredoc, one-shot prefix, `export` with extra words handled) |
| 16-05 | Move a tool between managers | held: no migrate path in update.py |
| 16-08 | Delete a foreign line | held: rewrite by index, all lines kept |
| 16-08 | Edit inside another tool's block | held: `block_owner` non-guardable (host line 70) |
| 16-08 | Write without byte-exact backup | held: backup precedes atomic write; WR-01 changes wording only |
| 16-10 | Launch a GUI from the installer worker | held: kitty `launch=n` |
| 16-11 | Edit more than one file per confirmation | held per test |
| 16-13 | Re-propose a declined post-install on drag-in/re-run | held per test |

### Anti-Patterns Found

No TBD/FIXME/XXX/TODO/HACK added in the phase diff or since e91bce3. `shortcut:` comments (keg-only stat loop, rcclean heredoc/array) are documented limits and accepted dispositions. Nothing blocking.

### Human Verification Required

Resolved and removed: **Alacritty dim styling**. 16-UAT.md test 1 `result: passed`: a real-host `tmux capture -e` shows the row in Textual's blended dim fg (38;2;161;161;161) with `(not available: immutable host)`.

1. **Execute-screen enter on a real host.** Test: select a current tool, open execute, read preflight, press enter. Expected: `<tool> already current — nothing to do.`, no `Install 0 tools`. Why human: enter touches real rc files; the preflight text is pilot-test-proven.
2. **Real-machine experience.** Use catalog and Doctor in a normal session. Expected: rows stay truthful. Why human: time-on-host experience; the dangling-shim repro now exists only as puppeteer.
3. **Prohibitions review.** Read the table above. Expected: agree each must-NOT held. Why human: judgment-tier.

### Gaps Summary

No gaps. All five defects are fixed in code, wired into the production composition, proven by passing tests, reproduced on this host with the fixed answers, and the rendered rows were captured in a real TUI. The 22 review findings are closed (18 fixed, 8 accepted, 0 open) with no regression in the host proof. Status stays `human_needed` only for the three items above. The 9050446 fixes (stale ✓ after Uninstall, blank system-tier Owner after an install, script-install removal text) are each proven by a fail-first test and add no gap.

---

_Verified: 2026-10-11T00:37:57Z_
_Verifier: Claude (gsd-verifier)_
