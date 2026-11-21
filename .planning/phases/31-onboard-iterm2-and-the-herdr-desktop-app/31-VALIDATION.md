---
phase: "31"
slug: "onboard-iterm2-and-the-herdr-desktop-app"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-21"
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 31-RESEARCH.md "Validation Architecture"; the per-task rows below were filled by the planner from plans 31-01 to 31-08 (real plan, wave and task ids).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); autouse seams and the HOME sandbox in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> --no-cov -q` |
| **Full suite command** | `make test` (once, after the last task of each plan) |
| **Static gates** | `make validate` (the six commit-stage gates; once per plan, after the last task) |
| **Container proof** | `scripts/container-e2e-verify.sh herdr-app` (orchestrator only, disposable container, never on the host) |
| **Estimated runtime** | ~30 seconds per targeted run (to confirm in the first plan) |

Files the quick command draws from: `tests/test_terminal_ownership.py`, `tests/test_iterm2_profile.py`, `tests/test_iterm2_row.py`, `tests/test_herdr_app_keys.py`, `tests/test_herdr_app_row.py`, `tests/test_terminal_json_catalog.py`, `tests/test_terminal_keys.py`, `tests/test_registry.py`, `tests/test_resolve.py`, `tests/test_tool_onboarding_skill.py`, `tests/test_version_status.py`, `tests/test_container_e2e_herdr_app.py`.

Baseline: `tests/test_terminal_keys.py`, `tests/test_tool_onboarding_skill.py` and `tests/test_resolve.py` pass on this tree (31-RESEARCH.md, `--no-cov`).

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green and `scripts/container-e2e-verify.sh herdr-app` PASS
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

Task ids are `31-<plan>-<task>`. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row). The container run is an orchestrator step after plan 31-07 and before plan 31-08. Review round 1 (8fee75b7) changed the rows below it touches: the ownership and hook contract (31-01, 31-02), the explicit context and removal outcomes (31-03), the chord rule and record-aware detector (31-04), the real-row reconfigure and receipt cases (31-05), the reverse scenario and fake-driven orchestrator (31-06), the nested filter (31-07) and the evidence wording (31-08); 31-04 now also depends on 31-03. Review round 2 (dca972cd) changed the rows it touches: the record bound to the resolved keys path, the symlink rule, the partial line for a changed held value and the seed refusal (31-01), the one first-switch rule and the shared reinstall sequence (31-02), the pre-removal point and the refusal of an unconfirmed restore moved into the entry commit with both uninstall routes tested (31-03), the version-checked seed and `hashlib` (31-04), the two-collection-plus-path golden, the existing-file path change and the version mismatch (31-05), the narrowed isolation claims with `_UNPROVEN`, the stop-or-continue policy, the purge of a failed install and `transcript_problem` (31-06), the comment-preserving filter and its failure propagation (31-07) and the transcript check of the gate (31-08). Review round 3 (fbe1f7ce) changed the rows it touches: `OwnedKeys.pinned` (strip never calls the seed) and one path-change precedence (31-01), the lost-record and retryable-switch rules of the restore (31-02), the same two rules and the production decision field through both uninstall routes (31-03), the pinned default that never runs the version seam (31-04), the real removal route after the executable is gone, the sidecar test and the herdr-app config choice (31-05), `KEYS_UNPROVEN`, prefix matching, per-install baselines and the transcript digest (31-06), the generic-skip test assertion and the digest in the PASS line (31-07) and the digest check of the gate (31-08). Review round 4 (fdeaaaf5) changed the rows it touches: the sidecar-mismatch order of the owned-keys strip (31-01, 31-05), the non-final restore confirmed only when its record update succeeded and a failed capture that inhibits the switch (31-02), the compound-failure production-route test (31-03), the probe of the installed method's own executable (31-04, 31-05), the exact target-local allowlist, one path identity and the baseline-bound purge (31-06), the gate function and the contract tie (31-07) and the exact 12-character gate with explicit inputs (31-08).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | NTERM-02, NTERM-03 | T-31-01, T-31-02, T-31-03 | `WholeFile` apply, drift, deleted-file rule, hooks (also on an unchanged recorded reconfigure), strip with marker AND proof (a not-confirmed restore keeps the file and records), explicit home and environment, the recorded-row error contract; a foreign or symlinked file is refused byte for byte; the four region rows pinned by id only; `before_removal_terminal_keys` returns the hook's `Restored` so the removal flow can refuse | unit (tracer) | `uv run pytest tests/test_terminal_ownership.py tests/test_terminal_keys.py tests/test_post_install.py tests/test_version_status.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-01-02 | 01 | 1 | NTERM-02, NTERM-03 | T-31-03, T-31-06, T-31-17 | `OwnedKeys` seed, insert, kept-yours, tombstones that survive two reconfigures, recorded ownership resolved before the user-binding check, drift rewrite and owned-only strip on a fixture row; an unparseable file is refused; a created file equal to the seed is deleted; the record is bound to the resolved keys path (a changed path never inherits the old ledger, an initially existing file included); a symlink at the keys path fails closed in apply, pending and strip; a user-changed held value is reported; a seed that raises is a refusal; strip compares against the pure `pinned` default and never calls the seed; one ledger-path warning for a path change, a created file included; a created marker bound to another path warns and leaves the file and every record untouched (round 4 M1) | unit | `uv run pytest tests/test_terminal_ownership.py tests/test_terminal_keys.py tests/test_post_install.py tests/test_version_status.py tests/test_app.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-02-01 | 02 | 2 | NTERM-02 | T-31-05 | Profile goldens G1 and G2 (no `Option Key Sends`, `Custom Directory` iff `Writes`), the masked keystroke merge, proof and validate, the state record | unit / golden | `uv run pytest tests/test_iterm2_profile.py tests/test_terminal_keys.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-02-02 | 02 | 2 | NTERM-02 | T-31-04, T-31-10 | Default-profile G3 over four starting states with complete argv lists (reads included), restore by recorded GUID with `confirmed` (a failed restore keeps the record), the first switch and the retry both write only while the preference is still the previous default, the reinstall sequence the golden and the hooks share, fault injection at each transition, custom-folder and non-GUID skips, a tampered record never reaches `defaults`, a lost or corrupt record while the preference still names the profile is an unconfirmed restore, a restore before the removal leaves a retryable switch and is unconfirmed when its record update fails (round 4 R4), a failed capture inhibits the switch even with an old record (round 4 R5), the autouse stub | unit (fake seam) | `uv run pytest tests/test_iterm2_profile.py tests/test_terminal_keys.py tests/test_terminal_ownership.py tests/test_post_install.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-03-01 | 03 | 3 | NTERM-02 | T-31-01, T-31-02, T-31-10 | `iterm2` resolves only on macOS 13 or later and is in `MACOS_ONLY`; the row reads its state from the explicit home and environment, writes the golden profile, refuses a foreign file, reads drift, a broken default and a pending switch as `≈` (status-pass tests, review W3); forced pins move by the id; in the same commit `remove_tool` restores the previous default before the cask command, an unconfirmed restore REFUSES the removal (cask and receipt kept), and the hook lines reach every later outcome (round 2 H5, M2); a lost record while the default names the profile is unconfirmed too (round 3 H4) | unit | `uv run pytest tests/test_iterm2_row.py tests/test_registry.py tests/test_resolve.py tests/test_tool_onboarding_skill.py tests/test_terminal_keys.py tests/test_post_install.py tests/test_version_status.py tests/test_app.py tests/test_uninstall.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-03-02 | 03 | 3 | NTERM-02 | T-31-10 | End to end through the production functions and both uninstall routes (`perform_uninstall` and `run_uninstall`): install then uninstall leaves the preference and HOME as they were; a restore that cannot be confirmed blocks the uninstall until the user picks another default and the retry then removes it and deletes the profile; a failed strip restore keeps the file and the records until a later strip confirms; a lost or garbage record refuses the uninstall through both routes until the user picks a default; a failed cask command leaves a pending switch that a reconfigure retries; a config choice (`UninstallDecision.config`) never deletes the iTerm2 folder (round 3 H4, H5, H6); a failed record update after the restore refuses the removal before the cask and both retries recover (round 4 R6) | unit (production functions) | `uv run pytest tests/test_iterm2_row.py tests/test_app.py tests/test_uninstall.py tests/test_terminal_keys.py tests/test_terminal_ownership.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-04-01 | 04 | 4 | NTERM-03 | T-31-07 | The two vendor defaults match their pinned sha256 (checked with `hashlib`), the seed is written only when the installed app version equals the pinned one through one injected seam (a partial refusal naming both versions otherwise), the keys path follows the app's folder rules, the owned key per OS, insert then remove restores the vendor bytes, the pinned default never runs the version seam (round 3 H1); the version seam probes the installed method's own executable by full path (a shadowing executable, a missing PATH entry and a missing link tested, round 4 M2) | unit | `uv run pytest tests/test_herdr_app_keys.py tests/test_terminal_ownership.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-04-02 | 04 | 4 | NTERM-03 | T-31-05, T-31-12 | The app's chord grammar with one uppercase rule (cmd/super/win/secondary; option and platform rejected) and the record-aware detector keep a user binding in any spelling, treat a recorded old value as ours and tell the vendor's `global` picker from the user's | unit | `uv run pytest tests/test_herdr_app_keys.py tests/test_terminal_ownership.py tests/test_terminal_keys.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-05-01 | 05 | 5 | NTERM-03 | T-31-13 | `herdr-app` is its own entry (script on Linux, cask on Apple Silicon), unavailable on Intel macOS (`NO_MACOS_INTEL`), never colliding with `herdr`; row, skill row and forced pins | unit | `uv run pytest tests/test_herdr_app_row.py tests/test_herdr_app_keys.py tests/test_terminal_keys.py tests/test_registry.py tests/test_resolve.py tests/test_tool_onboarding_skill.py tests/test_post_install.py tests/test_version_status.py tests/test_iterm2_row.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-05-02 | 05 | 5 | NTERM-03 | T-31-03, T-31-06, T-31-12, T-31-13 | Keys goldens G4 and G5 on both CI OSes; a user binding kept with `herdr-app: partial: you already bind ...`; the displaced picker note; two reconfigures after a user delete, the old-ledger drift rewrite through the production detector, changed value, bound created path, owned-only strip; the golden asserts the full record (empty tombstones, keys, path); a changed keys folder never inherits the old ledger for an initially existing file; a user-changed owned value is reported on the first reconfigure; a version difference fails closed; a custom `XDG_DATA_HOME` leaves a partial receipt; the config folder is kept or deleted by choice through `UninstallDecision.config` with the strip before the delete; the real removal route deletes a created file after the executable is gone (pinned default); a created marker for another file warns and leaves that file untouched (round 3 M2, round 4 M1); the script method's `bin_dir` equals the probe's directory; the multiplexer's files untouched (round 3 H1, H6, M2) | unit | `uv run pytest tests/test_herdr_app_row.py tests/test_herdr_app_keys.py tests/test_terminal_ownership.py tests/test_terminal_keys.py tests/test_post_install.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-06-01 | 06 | 6 | NTERM-03 | T-31-13, T-31-20 | Driver verdicts: install, keys against the unit golden for the pinned version only (a version difference is `KEYS_UNPROVEN`, never OK, round 3 H8), isolation claims taken with the other tool present (an absent before-state is `_UNPROVEN`), removal residue with the target-local allowance, the `SweepResult` reading, the purge paths of a failed install, `transcript_problem` over the shared prefix list `EXPECTED_LINES` (`startswith`), `transcript_digest`, seed, digest and record helpers; the nested core install is allowed by exact path only (a descendant and a lookalike are reported, round 4 R7) and never by the shared allowlist; declared, receipt and listing paths share one identity (a tree receipt against a trailing-slash listing, round 4 R8) | unit | `uv run pytest tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_container_e2e_herdr_keys.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-06-02 | 06 | 6 | NTERM-03 | T-31-08, T-31-14, T-31-20 | `run_order` driven by fakes in both orders (call sequence with digests around the events where the other tool is present, verdict lines, a changed digest named at its point, the stop-or-continue policy, cleanup in a `finally` with inspected results, a failed install without a receipt reported and purged, only of the known paths new since the baseline taken right before that install, first, second or reinstall, both orders, preexisting paths surviving); the driver refuses outside the container and captures output through files | unit | `uv run pytest tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_container_e2e_landing.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-07-01 | 07 | 7 | NTERM-03 | T-31-08 | The `herdr-app` target: PID-named box, root stage installs only libxcb and libxkbcommon, one lifecycle step, teardown by exact name even when the step fails, never privileged, no prune or reset; the usage names every verdict of `EXPECTED_LINES` and the exact-path allowance; the pure `gate_problem` (exactly 12 lowercase hex, one line, calendar date, transcript rules, digest) names each defect of the recorded PASS line (round 4 R10) | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_container_e2e_herdr_keys.py tests/test_container_e2e_landing.py tests/test_container_e2e_receipts.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-07-02 | 07 | 7 | NTERM-03 | T-31-15 | `herdr-app` is excluded from the generic all-pass and from the nested target by a registry-copy filter (the real awk run on the real registry, every retained block compared with its preceding comment byte for byte, the dropped herdr-app block asserted absent as a whole block rather than by a date prefix the iterm2 block shares; a failing filter stops the bootstrap and the sync; the call sits after the workspace copy in `cmd_bootstrap`, `cmd_resync` and `nested_prepare`); landing targets and the production registry keep it | host | `uv run pytest tests/test_container_e2e_herdr_app.py tests/test_registry.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-07-ORCH | 07 | 7 | NTERM-03 | T-31-09, T-31-13 | In a disposable container: both orders print `INSTALL_OK` and `KEYS_OK` (the seeded file read back at the pinned version; a version difference prints `KEYS_UNPROVEN`, which is not a pass and is retried after a pin bump); `herdr-first` prints `ISOLATION_OK` at the install and removal points (the existing multiplexer binary and a seeded `~/.config/herdr` byte-identical) and `REMOVE_OK` (only allowlisted residue, `herdr-core` and `hc` by the driver's own list); `app-first` prints `REVERSE_OK` at the install point; both orders print `REVERSE_OK` at the removal point (the app's binary, paths and config byte-identical); the transcript ends with `TRACER_LANDING_TEARDOWN_OK`, and the PASS line recorded in the 31-07 SUMMARY carries `transcript <12 hex>` (its `transcript_digest`) | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh herdr-app` | ✅ exists | ✅ green |
| 31-08-01 | 08 | 8 | NTERM-03 | T-31-11 | Behind the recorded `herdr-app-container: PASS` line AND a passing transcript only (the pure `gate_problem` of plan 31-07 run on explicit paths: exactly 12 hex characters, calendar date, `transcript_problem`, the digest equal to the one in the PASS line; six negative samples run against the same command): the registry comment and the skill row state the container evidence in the verdict names the driver prints, pinned by tests | unit | `uv run pytest tests/test_herdr_app_row.py tests/test_tool_onboarding_skill.py tests/test_registry.py -n auto -q --no-cov` | ✅ exists | ✅ green |
| 31-08-02 | 08 | 8 | NTERM-02, NTERM-03 | T-31-16 | Catalog guards: ownership variant per row id, config folder and paths of the two entries, no rejected key spelling, record names; completeness and `same_directory` tests pass with both rows | unit | `uv run pytest tests/test_terminal_json_catalog.py tests/test_terminal_keys.py tests/test_terminal_ownership.py tests/test_iterm2_row.py tests/test_herdr_app_row.py tests/test_tool_onboarding_skill.py tests/test_registry.py tests/test_resolve.py -n auto -q --no-cov` | ✅ exists | ✅ green |

Note: the research's suggested router test ("a `herdr-app:` warning is never routed to the `herdr` row") is replaced by a source assertion in plan 31-05 (`test_the_shell_sync_names_neither_new_terminal`): the shell-sync router reads only shell-sync warnings, which never carry these ids.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] iTerm2 tests (profile goldens, default-profile states, foreign/drift/strip/pending) — `tests/test_iterm2_profile.py` (plan 31-02) and `tests/test_iterm2_row.py` (plan 31-03) (NTERM-02)
- [x] herdr-app keys tests and chord grammar — `tests/test_herdr_app_keys.py` (plan 31-04) and `tests/test_herdr_app_row.py` (plan 31-05) (NTERM-03); the generic mechanisms in `tests/test_terminal_ownership.py` (plan 31-01)
- [x] autouse `defaults` seam stub in `tests/conftest.py` (plan 31-02) and the autouse `pinned_herdr_app_version` stub (plan 31-04)
- [x] `tests/e2e_herdr_app_driver.py` and `tests/test_container_e2e_herdr_app.py` (plan 31-06), plus the `herdr-app` target in `scripts/container-e2e-verify.sh` and the evidence-gate function `gate_problem` in the driver (plan 31-07)
- [x] fixture plist for `defaults export` (inline string in the test, plan 31-02)

*No framework install needed. Every other task writes its failing test first inside its own commit (`.claude/testing.md`).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| iTerm2 loads the Dynamic Profile live and it becomes the default profile | NTERM-02 | Real Mac with iTerm2; no macOS host here (D-19) | Owner's Mac: install through the wizard with iTerm2 running; the profile appears without a restart and a new window uses it |
| Cmd+K sends 0x0c (clears the screen and scrollback) | NTERM-02 | Real Mac keyboard and iTerm2 key handling | Owner's Mac: in a zsh prompt press Cmd+K; the screen clears (for example `cat` then Cmd+K shows the byte as `^L`) |
| Option+Left and Option+Right move by word; the Spanish `@` still types | NTERM-02 | Real Mac keyboard and Spanish layout | Owner's Mac with the Spanish layout: Option+Left and Option+Right move the cursor by word; Option+2 (or the layout's `@` chord) still types `@` |
| Colors in light and dark mode | NTERM-02 | Real Mac appearance switching | Owner's Mac: switch System Settings between Light and Dark; the profile colors stay readable in both |
| `Recycle` behavior for tabs, windows and split panes | NTERM-02 | Real Mac GUI | Owner's Mac: `cd` to a known directory, open a new tab, a new window and a split pane; each shows the same `pwd` |
| Uninstall restores the previous default profile, including the uninstall-from-inside-iTerm2 case | NTERM-02 | Real Mac; `defaults` and the running app | Owner's Mac: note the default profile before install; uninstall from a Terminal.app window and again from inside an iTerm2 window running the installer; the previous default (or "none set") is back and the profile file is gone |
| herdr app installs and launches on Apple Silicon macOS | NTERM-03 | Real Apple Silicon Mac | Owner's Mac: install through the wizard; the app lands, launches, and the owned key bindings work; `~/.config/herdr` is untouched |
| herdr app installs and launches on a Linux desktop session | NTERM-03 | Needs a live Linux desktop session (the container proves files only) | UAT on Bazzite: install through the wizard, launch the app from the menu, check the owned key bindings; uninstall and confirm no residue |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-11-21 (Nyquist audit)

---

## Validation Audit 2026-11-21

Targeted run of the ten phase test files (`--no-cov`): all pass. No test added; no production code touched.

| Item | Verdict | Evidence |
|------|---------|----------|
| R1 iTerm2 profile golden, Linux unavailable | COVERED | `tests/test_iterm2_row.py` (golden install), `tests/test_iterm2_profile.py` (G1/G2) |
| R2 default-profile set/restore, "none set", by identity | COVERED | `tests/test_iterm2_profile.py` (G3 four states, fault injection), `tests/test_iterm2_row.py` (both uninstall routes) |
| R3 distinct ids, Intel unavailable | COVERED | `tests/test_herdr_app_row.py`, `tests/test_registry.py` |
| R3 isolation both orders in a container | COVERED | orchestrator evidence: `herdr-app-container: PASS (2026-11-21; transcript 34591570ed07)` in 31-07-SUMMARY.md, plus `tests/test_container_e2e_herdr_app.py` for the driver and gate |
| R4 keys goldens, kept yours, displaced picker note | COVERED | `tests/test_herdr_app_row.py:230` and the chord tests in `tests/test_herdr_app_keys.py` |
| R5 drift, reconfigure, owned-only strip | COVERED | `tests/test_terminal_ownership.py`, both row test files |
| Phase 28 undeclared-row test with both rows | COVERED | `tests/test_terminal_json_catalog.py`, `tests/test_tool_onboarding_skill.py`, `tests/test_registry.py` |
| Per-task map rows 31-01-01 to 31-08-02 (16 rows) | COVERED | the ten test files above pass; 31-07-ORCH covered by the PASS line |
| Concurrency backstop (interleaved applies, R1/R3/R4/R5) | PARTIAL | no test interleaves two applies; correctness rests on the shared atomic write (`installer/atomic.py`) tested elsewhere |
| Manual-only rows (7: real iTerm2 and herdr app on macOS and Linux desktop) | PARTIAL by design | owner UAT; not automatable here |

Totals: COVERED 23, PARTIAL 2 (concurrency backstop, manual UAT), MISSING 0.
