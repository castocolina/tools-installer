---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
verified: 2026-10-10T18:30:00Z
status: human_needed
score: 6/7 must-haves verified
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
covered_digest: "v3:sha256:d0fd00227fa6225ae6d902c13825c9083975e77170ffe0679ca4963d097f74d0"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Walkthrough (1): `uv run python setup.py`, find groovy/gradle/maven/java. Press `u` only on a row whose Ver cell shows current."
    expected: "Owner reads `Homebrew ≠ policy` (dim tag); detail names SDKMAN as the declared manager; `u` on a current row says `<id> is already current — Homebrew owns this copy; the catalog installs it via SDKMAN, and moving it there is not available yet`."
    why_human: "Rendered Owner cell styling and status line in the live TUI. Data verified headless (owner=brew, off_policy=True for all four)."
  - test: "Walkthrough (2): find springbootcli and sdkman in the catalog. Browse only."
    expected: "Ver shows 4.1.0 and 5.23.0, never `no version`."
    why_human: "Rendered Ver cell. Data verified headless via resolve_status."
  - test: "Walkthrough (3): open the app (System view), wait a few seconds, switch to the AI view. Find superpowers, ponytail, softaworks-agent-toolkit, opengsd."
    expected: "Inst is ✓, Owner lists hosts (e.g. `Claude Code, Pi`, or `Claude Code +3` for opengsd); detail shows `installed in: ...`."
    why_human: "Background worker landing and repaint in the live TUI. Probe data verified headless."
  - test: "Walkthrough (4): find kitty and alacritty. Browse only."
    expected: "kitty is selectable with Owner `own installer`; alacritty is dim with `(not available: immutable host)` and the full sentence in detail."
    why_human: "Dim styling and detail sentence rendered in the TUI."
  - test: "Walkthrough (5): select wezterm (or another current tool), open the execute screen, read the on-mount preflight, leave with esc. Do NOT press enter."
    expected: "Preflight reads `wezterm already current — nothing to do.`; progress shows `wezterm [already current]`. Never `Install 0 tools`."
    why_human: "Defect (5) was not driven on the host (enter runs configure_path against real rc files). Only unit tests cover it."
  - test: "Walkthrough (6): find mmdc. Browse only."
    expected: "Red `!` only if the shim is dangling. On this host mmdc reads owner=brew, broken=False, so a plain ✓ with `Homebrew ≠ policy` is the correct answer."
    why_human: "The dangling-shim repro no longer exists on this host; D-18 is proven only by fixture tests."
  - test: "Walkthrough (7): open Doctor, read guidance, leave with esc. Do NOT press enter."
    expected: "Guidance names the `my-kitty PATH` block in ~/.bashrc as another tool's block (not offered) and offers to guard the other foreign lines."
    why_human: "Rendered guidance text; enter (apply) would edit real rc files."
  - test: "Review the 11 judgment-tier plan prohibitions (listed under 'Prohibitions' in the body). The verifier's verdict on each is non-authoritative."
    expected: "Human agrees each must-NOT held (verifier found no violation)."
    why_human: "Judgment-tier prohibitions need explicit human resolution; none has a fail-first test."
---

# Phase 16: Catalog truth (detection, version, ownership) Verification Report

**Phase Goal:** Every catalog row tells the truth about a tool that is on the disk: it is reported installed whether or not the current process can run it, it shows a version when one is knowable, it names whichever manager actually owns it, and when it cannot be installed or updated the row says why instead of going silent. Proven against the real defects below on a host that reproduces each one.
**Verified:** 2026-10-10T18:30:00Z
**Status:** human_needed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths

The ROADMAP has no `success_criteria` list for this inserted phase, so the truths come from the goal and its five live defects plus the in-scope foreign-PATH work. The 16 plans' ~95 frontmatter truths are folded under these.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Skill packs present on disk read installed (defect 1) | ✓ VERIFIED | `skill_lifecycle.inspect_skill_packs` with closed `HARNESS_CLI_STATUS` (`claude plugin list`, `codex plugin list`, `pi list`) plus skills-lock / install-state disk sources. Wired: `VersionRefreshService.refresh_skills` (version_status.py:544), `catalog_tui._refresh_skills_worker` passes `self._catalog` (:444), `_present`/`_inst_cell`/`_skill_owner_cell` render it. setup.py:897 wires `run_query`, :899 seeds the cache. Independent host run: ponytail, superpowers, softaworks-agent-toolkit, opengsd have `present` hosts. Tests `test_shipped_packs_report_per_host_status`, `test_one_cli_call_per_harness_across_packs`, `test_skill_probe_covers_packs_when_system_view_mounts_first`, `test_skill_inst_cell_shows_persisted_answer_with_stale_mark` pass. |
| 2 | A tool on disk reads installed whether or not this process can run it | ✓ VERIFIED | `is_installed` honors a method's `bin_dir`; `resolve_ownership` attributes by location proof (`_location_proof`, ownership.py:896) and by-elimination when off PATH; `_version_argv` (version_status.py:225) probes the declared `<bin_dir>/<cmd>` when `active_path` is None. Tests `test_probe_uses_declared_bin_dir_when_active_path_is_absent`, `test_kitty_declared_location_counts_as_installed` pass. |
| 3 | A version shows when one is knowable (defect 2) | ✓ VERIFIED | `_sdkman_current_version` reads the `current` symlink target (version_status.py:268); `_version_file` reads `version_file` (registry.toml:1753 for sdkman). Independent host run: springbootcli `4.1.0` (source sdkman), sdkman `5.23.0`, groovy `5.0.7`. Tests `test_sdkman_current_symlink_is_the_installed_version_without_a_probe`, `test_sdkman_dangling_current_has_no_installed_version`, `test_version_file_is_read_without_a_subprocess_probe`, `test_sdkman_version_through_real_resolve_ownership` pass. |
| 4 | The Owner names the manager that actually owns the tool (defect 3, D-01..D-08) | ✓ VERIFIED | `_undeclared_brew_candidate` (ownership.py:521) proves brew from Cellar path + inventory; `off_policy` set at :615/:702; sdkman owner and `own installer` label (:1172). Catalog renders `≠ policy` (catalog_tui.py:608-609), off-policy detail (:728-735), `also_installed_note` (:737), `active_path_note` (:749). Independent host run: groovy/gradle/maven/java `owner=brew label=Homebrew off_policy=True` (java package `openjdk`), springbootcli `SDKMAN`, kitty and bun `own installer`. Tests `test_undeclared_brew_cellar_groovy`, `test_own_installer_location_proof_resolves_bun_when_brew_does_not_list_it`, `test_off_policy_owner_cell_and_detail_name_the_declared_manager`, `test_detail_names_also_installed_via_the_shadowed_manager`, `test_unknown_detail_names_the_active_binary` pass. |
| 5 | A row that cannot install or update says why (defects 4 and 5, broken shim) | ✓ VERIFIED | `unavailable_reason` (resolve.py), built in setup.py:784, rendered at catalog_tui.py:617-621 (row) and :671-672 (detail). kitty gained its real `script` method (`launch=n`, registry.toml:2552-2557). `u` on current/broken/unknown never returns silently (catalog_tui.py:909-944). Execute preflight `<ids> already current — nothing to do.` (execute_screen.py:1013-1015); broken routes to `repair=True` (:615, engine.py:132); explicit-selection post_install re-apply (:633-641). Host: alacritty `immutable host`, gnu-bash/container `fedora not supported`, kitty None. Tests `test_unavailable_reason_renders_in_row_and_detail`, `test_update_on_current_tool_says_already_current`, `test_current_only_selection_says_already_current_not_install_zero`, `test_outdated_selected_tool_stays_an_update_target`, `test_broken_selection_is_installed_with_repair`, `test_broken_row_marks_inst_red_and_explains_repair`, `test_dangling_pnpm_shim_reads_broken`, `test_explicit_current_selection_reapplies_post_install_once`, `test_installed_drag_in_is_not_reapplied` pass. |
| 6 | Doctor can guard a foreign unguarded PATH line in place, with backup, per-file opt-in, never inside another tool's block (D-21..D-24) | ✓ VERIFIED | `guard_path_writers` (shellrc.py:1144) rewrites by index, re-checks bytes, `backup_precondition` then `_create_backup` then re-snapshot before `atomic_write_text`. `block_owner` refusal for foreign marker blocks. Wired into DoctorScreen via `guard_file`/`rescan_writer_lines` (wizard_app.py:313-325, :638-702). Host scan recorded in 16-16-SUMMARY (g), not re-run by the verifier: ~/.bashrc line 70 refused as `my-kitty PATH` block, six other lines guardable. Tests `test_guard_in_place_rewrites_one_foreign_bashrc_line`, `test_marker_block_kitty_names_the_owner`, `test_doctor_guard_chain_confirms_files_in_record_order`, `test_doctor_guard_no_skips_without_calling_guard_file` pass. |
| 7 | Proven on a host that reproduces each defect | ? UNCERTAIN | Headless production-composition proof re-run independently for defects 1-4 (output matches 16-16-SUMMARY). Defect 5's preflight was not driven on the host (enter rewrites rc files), and the mmdc dangling-shim repro no longer exists on this host (`broken=False`, owner brew). Rendered TUI states are the 7 pending walkthrough rows. Routed to human verification. |

**Score:** 6/7 truths verified (0 present-but-behavior-unverified; 1 uncertain, routed to human)

### Required Artifacts

All 24 production files in the phase diff (base `2eaae39`) exist and are substantive. Spot-read: ownership.py, version_status.py, catalog_tui.py, execute_screen.py, shellrc.py, status.py, skill_lifecycle.py, registry.toml (kitty, sdkman, matt-pocock-skills), setup.py composition.

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| installer/ownership.py | sdkman/location/undeclared-brew/off_policy/broken | ✓ VERIFIED | Wired via `resolve_ownership` from VersionRefreshService and setup.py `_reresolve_ownership` |
| installer/version_status.py | disk versions, skill cache service | ✓ VERIFIED | `_version_argv`, `_version_file`, `_sdkman_current_version`, `refresh_skills` |
| installer/skill_lifecycle.py | per-harness probes, host presence | ✓ VERIFIED | Closed argv table, no npx |
| installer/catalog_tui.py | rendering of all row states | ✓ VERIFIED | `≠ policy`, `!`, reasons, host list, never-silent `u` |
| installer/execute_screen.py, engine.py, post_install.py | D-17/D-18/D-20 | ✓ VERIFIED | classification, `_with_repair`, `reapply_post_install` |
| installer/resolve.py | `unavailable_reason` | ✓ VERIFIED | used in setup.py:784 |
| installer/rcclean.py, shellrc.py, app.py, guidance.py, wizard_app.py | D-21..D-24 | ✓ VERIFIED | one scanner, guard with backup, Doctor chain |
| installer/registry.toml | kitty script method, sdkman version_file, audited harnesses | ✓ VERIFIED | `# Verified` comments present |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| setup.py | VersionRefreshService | `skill_probe=run_query`, `seed_skills_from_cache()` | WIRED |
| catalog_tui `_refresh_skills_worker` | `refresh_skills(self._catalog)` | full catalog, not tier slice | WIRED |
| `resolve_ownership` | `status.dangling_shim` | pnpm dirs + inventory | WIRED |
| execute_screen | `install_tool(repair=True)` | `_with_repair` | WIRED |
| execute_screen | `engine.reapply_post_install` | `self._reapply` loop | WIRED |
| setup.py | `unavailable_reason` | `unavailable` map to CatalogScreen | WIRED |
| wizard_app DoctorScreen | `guard_path_writers` / `path_writer_lines_for` | `guard_file`, `rescan_writer_lines` | WIRED |
| catalog_tui | `also_installed_note`, `active_path_note`, `declared_manager_label` | imports from ownership | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| Owner cell | `ManagerOwnership` | `read_inventory` (brew list) + `which` + location proof | Yes (host run) | ✓ FLOWING |
| Ver cell | `VersionStatus.installed` | symlink / version_file / resolved-path probe | Yes (host run) | ✓ FLOWING |
| Skill Inst/Owner | `SkillHostStatus.hosts` | harness CLIs via `run_query` + disk | Yes (host run) | ✓ FLOWING |
| Row reason | `UnavailableReason` | `resolve_methods` per-method rejection | Yes (host run) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite + validate | background regression log (`REGRESSION-EXIT 0`) | 3395 passed, 5 skipped, 0 failed; ruff, format, pyright 0 errors, bandit, vulture, shellcheck clean | ✓ PASS |
| 28 named decision tests (D-01..D-24) | `uv run pytest <28 node ids> --no-cov` | 28 passed | ✓ PASS |
| Version-from-disk + `u` on current + status tests | `uv run pytest <5 node ids> tests/test_status.py --no-cov` | all passed | ✓ PASS |
| Production composition on this host (read-only) | scratch `proof.py` calling `resolve_ownership`, `resolve_status(allow_fetch=False)`, `unavailable_reason`, `inspect_skill_packs` | matches 16-16 SUMMARY sections (a)-(f) | ✓ PASS |

### Probe Execution

No phase-declared `scripts/*/tests/probe-*.sh`. Step 7c: not applicable.

### Requirements Coverage

No REQUIREMENTS.md IDs (inserted phase, `TBD`). The plans' `requirements:` reference D-01..D-24 from 16-CONTEXT.md. All 24 are claimed by at least one plan and mapped in 16-VALIDATION.md.

| ID | Plans | Status | Evidence |
|----|-------|--------|----------|
| D-01 | 01, 05, 06 | ✓ SATISFIED | groovy etc. Homebrew on host; sdkman owner |
| D-02 | 05, 15 | ✓ SATISFIED | `≠ policy` cell |
| D-03 | 05, 15 | ✓ SATISFIED (interim, by design) | Offer is text only ("moving it there is not available yet"); D-04 defers the migration |
| D-04 | 05 | DEFERRED by decision | Migration flow belongs to its own future phase per 16-CONTEXT.md; no code moves tools between managers (verified: no uninstall/migrate in update.py) |
| D-05 | 05, 15 | ✓ SATISFIED | `brew upgrade` via real owner with note |
| D-06 | 05, 15 | ✓ SATISFIED | `also installed via X` |
| D-07 | 01, 10 | ✓ SATISFIED | kitty/bun `own installer` on host |
| D-08 | 01, 05, 15 | ✓ SATISFIED | `active_path_note` |
| D-09 | 02, 07 | ✓ SATISFIED | audited harness lists with `# Verified` comments |
| D-10 | 02, 12 | ✓ SATISFIED | harness CLI probes, cached |
| D-11 | 02, 07 | ✓ SATISFIED | skills-lock / install-state disk fallbacks |
| D-12 | 12 | ✓ SATISFIED | persisted answer + `~` |
| D-13 | 07, 12 | ✓ SATISFIED | host list + `+N` truncation |
| D-14 | 02, 12 | ✓ SATISFIED | once per launch, one call per harness |
| D-15 | 07 | ✓ SATISFIED | `present_harnesses` from disk or PATH |
| D-16 | 10, 14 | ✓ SATISFIED | reasons in row and detail |
| D-17 | 13 | ✓ SATISFIED | already-current preflight; outdated updates |
| D-18 | 09, 13, 15 | ✓ SATISFIED (fixture-proven) | host no longer reproduces the dangling shim |
| D-19 | 01, 06, 10 | ✓ SATISFIED | existing `bin_dir` is the single location proof |
| D-20 | 13 | ✓ SATISFIED | re-apply only on explicit selection |
| D-21 | 03, 04, 08, 11 | ✓ SATISFIED | guard in place |
| D-22 | 08, 11 | ✓ SATISFIED | `my-kitty PATH` block named, not offered |
| D-23 | 08, 11 | ✓ SATISFIED | `.tools-installer.old` backup |
| D-24 | 04, 11 | ✓ SATISFIED | per-file confirmation chain |

No orphaned IDs.

### Prohibitions (judgment-tier, non-authoritative verifier verdict, flagged for human review)

| Plan | Must-NOT | Verifier verdict |
|------|----------|------------------|
| 16-01 | Claim ownership on location alone for inventory kinds | held: `_location_proof` returns early unless kind is sdkman or installer (ownership.py:903) |
| 16-02 | Run a command that can download software | held: argv table is `claude plugin list`, `codex plugin list`, `pi list`; no npx/dlx in skill_lifecycle.py |
| 16-02 | Execute registry-supplied argv/path | held: `via` selects closed code tables |
| 16-03 | Report a guarded PATH line as a writer | held per rcclean tests (see IN-01 caveat below) |
| 16-05 | Move a tool between managers | held: no uninstall/migrate path in update.py |
| 16-08 | Delete a foreign line | held: rewrite by index, every line kept |
| 16-08 | Edit inside another tool's block | held: `block_owner` makes it non-guardable |
| 16-08 | Write without byte-exact backup | held: `_create_backup` precedes `atomic_write_text`, re-snapshot between |
| 16-10 | Launch a GUI from the installer worker | held: kitty `args = ["launch=n"]` |
| 16-11 | Edit more than one file per confirmation | held per `test_doctor_guard_chain_confirms_files_in_record_order` |
| 16-13 | Re-propose a declined post-install on drag-in/re-run | held per `test_installed_drag_in_is_not_reapplied` |

### Anti-Patterns Found

No TBD/FIXME/XXX/TODO/HACK added in the phase diff. Two `shortcut:` comments (ownership keg-only stat loop, rcclean array split) are documented limits.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| installer/shellrc.py | 1184 | WR-01: a second guard of the same rc file is refused while `<rc>.tools-installer.old` exists, with text that says "consolidation" | ⚠️ Warning | Fails safe, no data loss. Not goal-level: the first guard works (no backups exist on this host today), and Doctor guards every guardable line in a file per confirmation, so a second guard needs a new writer to appear later. The refusal is visible, not silent, but its wording is wrong for this flow. |
| installer/rcclean.py | 283 | IN-01: heredoc body lines can be reported guardable | ⚠️ Warning | Could rewrite heredoc data if the user confirms. The confirmation modal shows the exact before/after line, so a human sees it. Edge case, not goal-level. |
| installer/version_status.py | 225 | IN-08: installer/github owners still run `<active_path> --version` | ℹ️ Info | Matches the ROADMAP's own fix text ("probing at the resolved absolute path"). Not a gap. |
| IN-02..IN-07, IN-09 | various | Heuristic limits per 16-REVIEW.md | ℹ️ Info | No goal impact |

### Human Verification Required

#### 1. Off-policy Homebrew rows
**Test:** `uv run python setup.py`, find groovy/gradle/maven/java. Press `u` only on a current row.
**Expected:** Owner `Homebrew ≠ policy`; `u` answers already current with the SDKMAN note.
**Why human:** Rendered cell and status line.

#### 2. SDKMAN versions
**Test:** Find springbootcli and sdkman.
**Expected:** `4.1.0` and `5.23.0`, never `no version`.
**Why human:** Rendered Ver cell.

#### 3. Skill packs
**Test:** Wait on System view, switch to AI view. Find superpowers, ponytail, softaworks-agent-toolkit, opengsd.
**Expected:** ✓ with host names in Owner.
**Why human:** Background worker landing in the live TUI.

#### 4. kitty and alacritty
**Test:** Browse to both.
**Expected:** kitty selectable, `own installer`; alacritty dim with `immutable host` reason.
**Why human:** Styling.

#### 5. Already-current preflight
**Test:** Select wezterm, open execute screen, read preflight, esc. Do not press enter.
**Expected:** `wezterm already current — nothing to do.`
**Why human:** Defect 5 was not driven on the host.

#### 6. mmdc
**Test:** Find mmdc. Browse only.
**Expected:** On this host, plain ✓ with `Homebrew ≠ policy` (not broken). A red `!` would appear only for a dangling shim.
**Why human:** Repro gone; D-18 is fixture-proven only.

#### 7. Doctor guidance
**Test:** Open Doctor, read guidance, esc. Do not press enter.
**Expected:** `my-kitty PATH` block named and not offered; other foreign lines offered for guarding.
**Why human:** Rendered text; enter edits real rc files.

#### 8. Prohibitions review
**Test:** Read the Prohibitions table above.
**Expected:** Agree each must-NOT held.
**Why human:** Judgment-tier, no fail-first test.

### Gaps Summary

No blocking gaps. Every defect named in the goal is fixed in code, wired into the production composition, covered by passing named tests, and (for defects 1-4) reproduced headless on this host with the fixed answer. The full suite and `make validate` pass (3395 passed, 5 skipped).

What keeps this from `passed` is the goal's "proven on a host" clause: the rendered TUI states and defect 5's preflight have not been observed, and the mmdc dangling-shim repro no longer exists on this host. Those are the 7 pending walkthrough rows. WR-01 and IN-01 are real but fail-safe Doctor edge cases outside the catalog-row goal; track them as follow-ups, not blockers. One host note: matt-pocock-skills now reads absent on every host, which is correct (no `mattpocock` entry in `~/.agents/.skill-lock.json` and no plugin cache entry), even though the ROADMAP listed it as present on 2026-09-23.

---

_Verified: 2026-10-10T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
