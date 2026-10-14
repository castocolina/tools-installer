# Phase 22: Method lifecycle contract — Specification

**Created:** 2026-10-13
**Ambiguity score:** 0.16 (gate: ≤ 0.20)
**Requirements:** 12 locked

## Goal

Update and removal follow one contract per method kind. Nothing is removed without proof, no executor runs sudo, and config is kept unless the user asks for it per tool.

## Background

Scouted 2026-10-13:
- **sudo is still executed.** `installer/executors.py:371-379` runs `["sudo", "dnf"|"apt-get"|"pacman", …]`. This breaks the zero-sudo invariant (O1, D-I).
- **Removal authority is a name match.**
  - `plan_uninstall` (`uninstall.py:56`) feeds `remove_paths` (:342) and `run_uninstall` (`app.py:510`).
  - `_REMOVAL_COMMANDS` (`ownership.py:1368`) still carries native command templates.
  - Phase 17 narrows deletion to archive-layout proof as an interim fix. Phase 19 adds receipts and `ToolState.removable`. This phase completes the contract per kind (TA §4.1).
- **Script tools have no recipes.** 16 `kind = "script"` methods exist in `installer/registry.toml`, with no `paths`, `remove` or `update`. Updating OMZ exits 1, and updating SDKMAN does nothing (C G8).
- **Missing data and checks.**
  - No `config_paths` anywhere, and no `writable_prefix` preflight; the brew bootstrap aborts on `sudo -n` (C G2).
  - The update path has no `greedy` handling, so VS Code on macOS shows as current while outdated (LIFE-10).
  - `scripts/container-e2e-verify.sh` checks exit codes only (A #3).
- **Already handled elsewhere.** `METHOD_PARAMS` with unknown-key rejection and the `drawio-cli` removal belong to Phase 18. New params in this phase are added to that closed set.

## Requirements

1. **Script recipes (LIFE-01)**: Every script method declares `paths` (what the vendor writes), and may declare `remove` (argv) and `update` (argv).
   - Current: None are declared.
   - Target:
     - Removal runs `remove` first.
     - Removal then deletes only the declared paths that the receipt recorded at install time and that still match their recorded type and link target.
     - Any other existing declared path is listed as "remove it yourself".
     - If `remove` exits non-zero, the row ends failed with the vendor's error, nothing more is deleted, and the tool stays installed.
     - All 16 script tools get their data (TA: the 14 script tools plus pi), each with a `verified` date key.
   - Acceptance:
     - With a fake runner, `opencode` removal runs `opencode uninstall --keep-config --keep-data`.
     - A foreign file at a declared path that is not in the receipt survives removal.
     - A failing `remove` leaves every path in place and the row failed.

2. **One removal seam (TA §4.3)**: `removal_plan(tool, state) -> RemovalPlan(level, argv, paths, config, hint)` is pure and computed in the refresh pass. Levels: L1 manager, L2 receipt artifacts, L3 recipe, or none (hint only).
   - Current: `plan_uninstall` plus closures and `classify_tools`.
   - Target:
     - `plan_uninstall` becomes `download.artifact_paths(method)`, shared with `install_download` (`bin_name` honored).
     - The CLI and the TUI both read `RemovalPlan`.
     - Deleted: `ToolRow`, `OwnerHint`, `_manager_hint`/`_managed_hint`, the `setup.py:807-868` closures, and the native entries of `_REMOVAL_COMMANDS`.
   - Acceptance: For every kind, in both directions in a scratch HOME, install writes a receipt, Uninstall shows the tool as removable, and removal leaves none of the receipt's paths.

3. **Zero sudo (LIFE-02)**: Native dnf, apt and pacman installs become a MANUAL handoff showing the exact command. No executor runs sudo.
   - Current: `executors.py:371-379` runs it.
   - Target: The handoff text holds the command, and the argv path is gone.
   - Acceptance:
     - A grep test over `installer/` finds no argv list whose first element is `sudo`, `pkexec` or `doas`.
     - Selecting a native-only tool yields a handoff row with the exact command, and nothing runs.

4. **L1 manager removal by proof (LIFE-03, O3)**: `brew`, `uv` and `pnpm` uninstall run only when a receipt proves that the installer put that package there.
   - Current: Removal by name.
   - Target:
     - Without a receipt, show a hint.
     - Native owners (dnf, apt, pacman, rpm-ostree) get a hint that names the package and never a command.
     - SDKMAN gets the hint `sdk uninstall <candidate> <version>` with the version filled in.
   - Acceptance:
     - With a fake runner, a receipt-proven brew package runs `brew uninstall <pkg>`.
     - The same package without a receipt runs nothing and shows the hint.
     - A dnf-owned tool shows a package-naming hint with no argv.

5. **Config paths (LIFE-04)**: Tools may declare `config_paths`.
   - Current: None.
   - Target: `load_tools` rejects any entry that is not under `~`, sits at depth below 2, or lies under `~/.claude`, `~/.cursor`, `~/.gemini`, `~/.codex` or another harness-presence marker dir.
   - Acceptance: Fixtures with `~/.claude/x`, `~` and `/etc/x` are each rejected at load with the key named. `~/.config/gh` is accepted.

6. **Delete config too, per tool (UI-04)**: Uninstall offers a per-row "delete config too" toggle, off by default, only on tools with `config_paths`.
   - Current: No such option.
   - Target:
     - The review lists exactly which config paths will be deleted.
     - Config paths are deleted only after the tool's removal succeeds.
     - CLI `--yes` never deletes config.
   - Acceptance:
     - The toggle is absent on a tool without `config_paths`.
     - With the toggle off, config survives removal.
     - With it on, exactly the listed paths are gone.
     - `--yes` leaves config in place.
     - A failed removal leaves config untouched.

7. **Pinned app refused (LIFE-05)**: `u` on an `app` tool whose version source is none is refused with "pinned; update outside or re-pin".
   - Current: `u` reinstalls the pinned URL, which can downgrade.
   - Acceptance: `u` on draw.io (pinned) runs nothing and shows the reason.

8. **Vendor update commands (LIFE-06)**: When a script method declares `update`, `u` runs that argv. Otherwise it re-runs the vendor script.
   - Current: OMZ exits 1, and SDKMAN does nothing.
   - Acceptance: With a fake runner, `u` on OMZ runs `<omz root>/tools/upgrade.sh`, and `u` on SDKMAN runs `sdk selfupdate`. The OMZ root is `$ZSH` when set, otherwise `~/.oh-my-zsh`, resolved in Python by the existing `$ZSH`-aware resolver with no shell (clarified 2026-10-14).

9. **Writable-prefix preflight (LIFE-07)**: A script method with `writable_prefix` is checked before it runs.
   - Current: The brew bootstrap aborts on `sudo -n`.
   - Target: If the prefix is not writable by the user, the row becomes a MANUAL handoff with the vendor command, and nothing runs.
   - Acceptance: A brew bootstrap whose `/home/linuxbrew` fixture is unwritable yields a handoff and zero executions. A writable fixture proceeds.

10. **pnpm group warning (LIFE-08)**: Removing a pnpm package that belongs to a co-install group warns, naming the group and its other members.
    - Current: No warning (A #6).
    - Acceptance: Removing one member of a two-member group shows the warning. A package outside any group shows none.

11. **Leftover-checking e2e (LIFE-09)**: The container e2e harness records a file listing of HOME before install and after uninstall.
    - Current: Exit codes only.
    - Target: The leftover list must be a subset of the documented `config_paths`.
    - Acceptance: The harness fails on a planted leftover file and passes on a clean run. A run on Fedora in podman is recorded; Debian and Arch come in Phase 24.

12. **Greedy self-updating casks (LIFE-10)**: On macOS, casks with `auto_updates: true` are checked with `brew outdated --greedy` and updated with `brew upgrade --cask --greedy <cask>`.
    - Current: They show as current while outdated.
    - Target: Linux is unchanged. Other casks keep the non-greedy path.
    - Acceptance:
      - A fake brew reporting `visual-studio-code` as greedy-outdated shows `↑`.
      - `u` runs the greedy upgrade argv.
      - A non-auto-updates cask never gets `--greedy`.

## Boundaries

**In scope:**
- `paths`/`remove`/`update`/`writable_prefix` params and the data for all 16 script tools
- `RemovalPlan` and `removal_plan`; `download.artifact_paths`; the CLI and TUI on one removal path
- Removing sudo argv; native handoffs; L1 removal by receipt; hints for native and SDKMAN
- `config_paths` with its validator; the per-tool "delete config too" toggle
- Refusing `u` on a pinned `app`; vendor update argv; greedy casks on macOS
- The pnpm group warning; the leftover listing in the container e2e
- Deleting `ToolRow`, `OwnerHint`, the manager-hint helpers, the `setup.py` closures, the native `_REMOVAL_COMMANDS`, the 4 dead `POST_INSTALL_ACTIONS` names and `Tool.source`/`owner`

**Out of scope:**
- Hook unregistration and `receipt.hooks` — Phase 23 (the `RemovalPlan.argv` slot stays, unused)
- Debian and Arch e2e runs and the real-host UAT — Phase 24
- A `dmg`, `distrobox` or Intel kind (TA §4.4: not doing)
- Running sudo in any form, including "with confirmation"
- Volta owner attribution — Phase 19 (only its `volta uninstall` hint text belongs here)

## Constraints

- No new kind. The kind still selects the executor and update path, and `removal_plan` is the third and last switch on kind.
- Paths are evidence, never authority. Only receipt-recorded paths that still match are deleted.
- Zero sudo, pkexec or doas anywhere under `installer/`.
- New params join Phase 18's `METHOD_PARAMS`, and unknown keys stay rejected.
- Tests use fake runners and a scratch HOME. The e2e runs only in disposable podman containers. Nothing is installed on or removed from the host.

## Acceptance Criteria

- [ ] For each kind, install → receipt → Uninstall removable → removal leaves zero receipt paths (scratch HOME)
- [ ] `opencode` removal runs `opencode uninstall --keep-config --keep-data` (fake runner)
- [ ] A foreign file at a declared path that is not in the receipt survives removal and is listed as "remove it yourself"
- [ ] A failing `remove` argv leaves every path and the config in place and ends the row failed
- [ ] No `sudo`/`pkexec`/`doas` argv in `installer/` (grep test); a native-only tool yields a handoff with the exact command
- [ ] A receipt-proven brew package runs `brew uninstall`; without a receipt, only a hint; a dnf owner gets a package hint with no argv
- [ ] `config_paths` entries `~/.claude/x`, `~` and `/etc/x` are rejected at load; `~/.config/gh` is accepted
- [ ] "Delete config too" appears only for tools with `config_paths`, is off by default, and deletes exactly the listed paths; `--yes` never deletes config
- [ ] `u` on a pinned `app` runs nothing and shows "pinned; update outside or re-pin"
- [ ] `u` on OMZ runs `$ZSH/tools/upgrade.sh`; on SDKMAN, `sdk selfupdate` (fake runner)
- [ ] An unwritable `writable_prefix` yields a handoff with zero executions
- [ ] Removing a pnpm group member warns with the group; a non-member gives no warning
- [ ] The e2e harness fails on a planted leftover and passes clean; one Fedora podman run recorded
- [ ] A greedy-outdated auto-updates cask shows `↑` and `u` runs `brew upgrade --cask --greedy <cask>`; other casks never get `--greedy`

## Edge Coverage

**Coverage:** 21/21 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| idempotency | R1 | ✅ covered | Removing an already-removed script tool: the plan's level is none, nothing runs (AC 1) |
| concurrency | R1 | 🧪 backstop | A crash between `remove` and the path deletion leaves the receipt; the next pass shows the tool broken and not removable (held-out test) |
| unclassified | R2 | ✅ covered | Every kind in both directions (AC 1) |
| unclassified | R3 | ✅ covered | grep test plus a handoff row (AC 5) |
| unclassified | R4 | ✅ covered | brew with and without a receipt; dnf hint (AC 6) |
| unclassified | R5 | ✅ covered | Rejected and accepted fixtures (AC 7) |
| adjacency | R6 | ✅ covered | A config path shared by two selected tools is deleted once, and only if both rows toggle it (AC 8) |
| empty | R6 | ✅ covered | A tool with no `config_paths` has no toggle (AC 8) |
| ordering | R6 | ✅ covered | Config is deleted only after the tool's removal succeeds (AC 4, AC 8) |
| idempotency | R6 | ✅ covered | A config path already gone is skipped without error (AC 8) |
| concurrency | R6 | 🧪 backstop | An interrupt between removal and config deletion leaves the config; nothing half-deleted (held-out test) |
| unclassified | R7 | ✅ covered | Pinned draw.io (AC 9) |
| idempotency | R8 | ✅ covered | `u` on an up-to-date OMZ still runs the vendor argv; its exit code decides the outcome (AC 10) |
| concurrency | R8 | ✅ covered | Update children run in a new session with stdin closed (Phase 17 `start_new_session`); the fake runner asserts it (AC 10) |
| unclassified | R9 | ✅ covered | Unwritable and writable fixtures (AC 11) |
| adjacency | R10 | ✅ covered | Removing every member of a group together: one warning naming the group (AC 12) |
| empty | R10 | ✅ covered | A package outside any group: no warning (AC 12) |
| ordering | R10 | ✅ covered | The warning shows in the review, before anything runs (AC 12) |
| concurrency | R11 | ✅ covered | Listings are taken with no installer process running (harness sequencing; AC 13) |
| idempotency | R12 | ✅ covered | A greedy upgrade with nothing outdated: the row is skipped, no argv (AC 14) |
| concurrency | R12 | ✅ covered | The greedy check runs inside the single refresh pass; no extra worker (AC 14) |

## Prohibitions (must-NOT)

**Coverage:** 5/5 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT run sudo, pkexec or doas from any executor | R3, R9 | resolved | test: grep over `installer/` argv lists |
| MUST NOT delete a path that the receipt did not record or that no longer matches it | R1, R2 | resolved | test: the foreign-file fixture survives |
| MUST NOT run a manager uninstall without a receipt, nor any command for a native owner | R4 | resolved | test: the fake runner records zero calls |
| MUST NOT delete config unless that tool's toggle is on; never from the CLI | R6 | resolved | test: toggle off and `--yes` leave config intact |
| MUST NOT accept a `config_paths` entry in a shared harness dir | R5 | resolved | test: load rejects `~/.claude/x` |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | One contract per kind; proof, zero sudo, keep config |
| Boundary Clarity   | 0.82  | 0.70 | ✓      | Hooks → 23, other distros → 24, no new kinds |
| Constraint Clarity | 0.78  | 0.65 | ✓      | Paths are evidence; fake runners; containers only |
| Acceptance Criteria| 0.86  | 0.70 | ✓      | 14 pass/fail criteria |
| **Ambiguity**      | 0.16  | ≤0.20| ✓      | |

## Interview Log

`--auto`: the initial ambiguity of 0.16 was under the gate, so the interview was skipped. Open decisions went to jev-fast-decision. Local Laya (`system-one` on 127.0.0.1:8010) answered first, one call per question. All three Laya answers came back below 0.05 confidence, so each was re-asked through TypeSafe direct (`jev-latest`, which answers as `jev-1.13.0`). The first TypeSafe call was rejected by the skill's validator, because TypeSafe rounds to 2 decimals and the sum tolerance was 1e-3. The tolerance was raised to 2e-2 and the call re-run. Every answer is advisory, and the final decision is recorded below.

| Round | Perspective     | Question summary | Laya (advisory) | TypeSafe (advisory) | Decision locked |
|-------|-----------------|------------------|-----------------|---------------------|-----------------|
| auto | Failure Analyst | The vendor `remove` fails: continue or stop? | continue_report_failed p=0.41 (needs fallback) | stop_report_failed p=0.73–0.98 | Stop; delete nothing more; the row ends failed; the tool stays installed |
| auto | Researcher      | Which declared paths may be deleted? | any_existing_declared p=0.44 (needs fallback) | receipt_listed_only p=0.94 | Only receipt-recorded paths that still match; the rest are "remove it yourself" |
| auto | Boundary Keeper | How is "delete config too" offered for several tools? | confirm_each p=0.46 (needs fallback) | per_tool_toggle p=0.94–0.99 | A per-row toggle, off by default; the review lists exact paths; never from the CLI |
| auto | Failure Analyst | Edge table and prohibitions | – | – | All resolved as covered or backstop; none dismissed |

---

*Phase: 22-method-lifecycle-contract*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 22 — implementation decisions (how to build what's specified above)*
