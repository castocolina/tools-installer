# Phase 22: Method lifecycle contract - Context

**Gathered:** 2026-10-14 (assumptions mode, `--analyze --all --batch`, jev ladder, best-over-easy)
**Status:** Ready for planning

<domain>
## Phase Boundary

Update and removal follow one contract per method kind:
- Nothing is removed without proof.
- No executor runs sudo.
- Config is kept unless the user asks for it, per tool.

The WHAT is locked in `22-SPEC.md` (R1–R12). R8's OMZ acceptance was clarified in this session: the OMZ root is resolved, with no shell. This file locks the HOW.

Out of scope:
- Hook unregister/registration (23; the `RemovalPlan.argv` slot for hooks stays unused).
- `cargo_distrobox` (24).
- Debian/Arch e2e runs (24).
- Migrating off-policy tools.

**Prerequisites:**
- 17: D-04 layout proof, D-05 atomic writes.
- 18: D-01 `METHOD_PARAMS`, D-02 `verified`, D-09 guarded registry writes.
- 19: D-05..D-10 receipts, `artifact_paths`, `removal_plan`.
- 20: D-04, D-08 `WORDS`/`RowOutcome`.
- 21: D-07, D-08, D-11 Uninstall projection, removal worker, removal words.

None of these has landed as of 2026-10-14.
</domain>

<decisions>
## Implementation Decisions

**Decision rule:** best over easy. jev ladder: Laya is accepted when its own confidence is high. Otherwise TypeSafe, and if that's unsure too, full-model reasoning.

### Schema and registry data (R1, R5)
- **D-01:** `config_paths` is a **tool-level** field, parsed in `Tool` beside `requires`/`uninstall` (`model.py:324-370`). `paths`, `remove`, `update` and `writable_prefix` are **method-level** keys added to `METHOD_PARAMS["script"]` (18 D-01).
  - The tool level keeps one config list per tool, whichever fallback method installed it (brew `:162`/`:169`, pnpm `:1965`/`:1971`).
- **D-02 (best, not easy):** The `config_paths` denylist comes from **one** source.
  - The marker-directory tuples move out of `skill_lifecycle.HARNESS_PRESENCE` (`skill_lifecycle.py:174`) into `model.py`, beside `SKILL_HARNESSES`.
  - `skill_lifecycle` builds `HARNESS_PRESENCE` from them plus its command names. The validator reads the same constant.
  - The import direction stays `skill_lifecycle → model`, so there is no cycle.
  - Rules: an entry must be under `~` and at depth ≥ 2, and must not be under any harness marker dir. Errors name the tool and the key.
  - jev: Laya literal_denylist 0.61, needs fallback; TypeSafe relocate_dirs 0.87.
- **D-03 (full-model, combining both jev answers):** Script `paths`/`remove`/`update` tokens get `~` expansion plus a **closed set of named roots** resolved in Python by existing resolvers, following the existing `{ver}`/`{arch.*}` closed templating precedent (`assets.py:33`). There is no `sh -c` and no general `$VAR` expansion.
  - The first root is `{omz_root}`, resolved by `omz.omz_root(home, environ)` (`omz.py:~540`; `$ZSH`-aware, default `~/.oh-my-zsh`).
  - OMZ `update = ["{omz_root}/tools/upgrade.sh"]`.
  - An unknown placeholder is rejected at load.
  - Rationale: Laya preferred honoring `$ZSH` via a shell (0.85, own confidence 0.39). TypeSafe preferred a plain `~` path (0.96). The project already fixed a bug where `$ZSH` was ignored (`omz.py:396-423`, CONF-07), so a resolver keeps `$ZSH` truth without adding shell-injection surface to the executor.
- **D-04:** The 16 `kind = "script"` stanzas cover 14 tool ids: `uv`, `brew` ×2, `oh-my-zsh`, `codex`, `claude`, `opencode`, `cursor-agent`, `antigravity`, `sdkman`, `bun`, `pnpm` ×2, `volta`, `fnm`, `kitty`.
  - `pi` is a `host_setup` tool (`registry.toml:2691-2706`). It gets a `verified` key but no script keys; its removal stays an L1 hint through its real owner.
  - SPEC R1's "16 script tools … plus pi" is read as these 16 stanzas plus pi's `verified` key.
- **D-05 (research needed):** Each script tool's `paths`/`remove`/`update` data must be verified against the vendor's current uninstall/update docs or install script. Each gets a `verified` date (18 D-02).
  - Even the SPEC's anchor, `opencode uninstall --keep-config --keep-data`, is not yet cited to a source. The phase researcher must confirm it.
  - A tool with no documented vendor uninstall gets no `remove`: removal is then just its receipt-proven `paths`, plus "remove it yourself" for the rest.

### Removal contract (R2, R4, R6, R10)
- **D-06:** `removal_plan(tool, state) -> RemovalPlan` (19 D-10) is extended, not redesigned.
  - It gains the L3 branch: a script `remove` plus receipt-proven `paths`.
  - L1 gets `argv` only for brew/uv/pnpm with a receipt that proves the installer put the package there.
  - L2 stays as receipt-matched download/app artifacts.
  - `argv`'s hook slot stays empty until Phase 23.
  - `plan_uninstall` is already folded into `download.artifact_paths` by 19 D-07.
- **D-07 (best, not easy):** The removal order for one tool:
  1. Run `remove`. A non-zero exit means the row is `remove_failed` with the vendor's error, nothing is deleted, and the tool stays installed.
  2. Delete the receipt-proven `paths` and artifacts that still match their recorded type and target. Other declared paths that exist are listed as "remove it yourself".
  3. **Delete the receipt.**
  4. Only when the per-row toggle is on and steps 1–3 succeeded, delete `config_paths`. A failure here is a warning and never restores the receipt.
  - Deleting the receipt last would make an interrupted removal read as BROKEN ("receipt present, artifacts gone"). jev: Laya 0.66 (needs fallback); TypeSafe receipt_before_config 0.98.
- **D-08:** Native owners (dnf/apt/pacman/rpm-ostree) get a hint that names the package and never a command.
  - The native entries of `_REMOVAL_COMMANDS` (`ownership.py:1378-1381`) are **deleted**, not just left unused. Their package-less descriptions (`:1398-1401`) are the only phrasing.
  - `ToolRow`, `OwnerHint`, `_manager_hint`/`_managed_hint` and the `setup.py:807-868` closures are deleted (19/21 already remove most of them).
- **D-09:** The SDKMAN hint `sdk uninstall <candidate> <version>` takes its version from the `VersionStatus` the pass already reads (the readlink of `current`). There is no second probe.
- **D-10:** The pnpm group warning on removal reuses `pnpm_globals.split_install_groups`/`pnpm_global_groups` (`:438-486`) and the declared `co_install` groups (`model.py:680-683`). There is no new pnpm query.
- **D-11:** The "delete config too" toggle is per row and off by default. It is offered only when the tool has `config_paths`.
  - The review lists the exact paths.
  - Config is deleted after step 3 only.
  - CLI `--yes` never deletes config.

### Zero sudo and writable prefix (R3, R9)
- **D-12 (best, not easy):** **MANUAL is decided at plan time.**
  - A new `Disposition.MANUAL` (20 D-01) shows "you run: `<exact command>`" in the review **before** anything runs.
  - It applies to a native dnf/apt/pacman install method, and to a script method whose `writable_prefix` is not user-writable.
  - Both cases use one shared predicate, `needs_manual(method, state)`.
  - The refresh pass records prefix writability as evidence: one stat per `writable_prefix`, no subprocess, no `sudo -n`.
  - The engine re-checks the same predicate right before `_perform` (`engine.py:71-85`), next to the existing `host_setup` handoff, which closes the time-of-check gap.
  - `RowOutcome` gains one result, `manual`, in `WORDS`. It doesn't change the exit code, and the row stays selected.
  - The `_dnf`/`_apt`/`_pacman` sudo argv (`executors.py:370-379`) is deleted, and a grep test bans `sudo`/`pkexec`/`doas` as the first element of an argv.
  - BLOCKED (20 D-04) keeps its meaning, "nothing the installer can do", for example repairing a dnf-owned tool. MANUAL means "here is your command".
  - jev: Laya execute_time_only 0.59 (needs fallback); TypeSafe plan_time_manual 1.00.
- **D-13:** The brew bootstrap is today's only `writable_prefix` consumer (`/opt/homebrew`, `/home/linuxbrew`). The check is `os.access(prefix, W_OK)`, or the nearest existing parent is user-owned and writable.

### Update contract (R7, R8, R12)
- **D-14:** The pinned-`app` refusal ("pinned; update outside or re-pin") is one early return in `update._perform` (`update.py:236-317`), parallel to the SDKMAN-candidate branch (`:253-260`).
  - `UpdateTarget` (`:137-148`) carries the version fact from `state_of`, so the TUI's `u` and headless UPDATE rows share the gate.
  - `build_plan` never produces UPDATE for an app with no version source, because it is never OUTDATED.
- **D-15:** A script `update` argv runs through `_update_installer_owned`'s script branch (`update.py:337-339`) when declared. Otherwise the vendor script re-runs (today's behavior).
  - `sdkman` (the bootstrap) gets `update = ["sdk", "selfupdate"]`.
  - SDKMAN **candidates** stay refused with their `sdk upgrade` hint. The two paths are never merged.
- **D-16 (best, not easy):** Greedy casks.
  - The source is one batched `brew info --cask --installed --json=v2` call, cached with the existing brew inventory (6 h), which gives live `auto_updates` truth. There is no hand-kept registry flag and no per-cask call.
  - Only when an installed tracked cask has `auto_updates`, the pass adds one batched `brew outdated --cask --greedy --json=v2`, parsed by `parse_brew_outdated_json` (`manager_versions.py:52`).
  - `u` runs `brew upgrade --cask --greedy <cask>` only for those casks. Linux is unchanged.
  - The researcher must confirm the `--greedy`/`--json=v2` flag shapes against current Homebrew.
  - jev: Laya per_cask_info 0.39 (needs fallback); TypeSafe batched_live_info 0.94.

### E2E leftover check (R11)
- **D-17:** Extend `cmd_pass2` in `scripts/container-e2e-verify.sh` (`:399-458`) with a HOME listing taken with no installer running.
  - One listing is taken before the first install and one after `--uninstall --yes`, both as `tester` through `exec_tester`.
  - The run fails when a survivor is not under the union of the installed tools' `config_paths`.
  - The transcript goes to the existing `pass2-transcript.log`.
  - One Fedora podman run is recorded, and the container is removed afterwards.
  - There is no new subcommand, so the bootstrap is not duplicated.

### Claude's Discretion
- Plan and wave order. Suggested:
  1. The schema keys and the denylist relocation.
  2. Zero sudo and MANUAL.
  3. The `removal_plan` L1/L3 extension and ordering.
  4. Update contract.
  5. Registry data, after research.
  6. The e2e harness.
- The predicate's name, and the exact `{…}` root syntax.

### Folded Todos
None. `repair-pi-install-and-sync-models` (0.9) is pi host repair plus MCP registration, which belongs with Phase 23 (agent-host registration, `_AGENT_HOST_IDS`). It is reviewed there.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/22-method-lifecycle-contract/22-SPEC.md`: locked R1–R12 (R8 clarified 2026-10-14)
- `.planning/research/2026-10-13-target-architecture.md`: §4.1 contract table, §4.2 schema, §4.3 removal seam, §5 receipts, §6 keep/delete config, §9.2 O1, O3
- `.planning/phases/18-registry-truth-and-drift-guard/18-CONTEXT.md`: D-01, D-02, D-09
- `.planning/phases/19-one-tool-state-with-health-plus-receipts/19-CONTEXT.md`: D-05..D-10
- `.planning/phases/20-install-plan-with-dispositions/20-CONTEXT.md`: D-01, D-04, D-08
- `.planning/phases/21-one-screen-family/21-CONTEXT.md`: D-07, D-08, D-11
- `.planning/REQUIREMENTS.md`: LIFE-01..10, UI-04
- `.claude/architecture.md`, `AGENTS.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `omz.omz_root(home, environ)`: the `$ZSH`-aware root
- `engine._perform` handoff ladder (`:71-85`) and the `host_setup` handoff
- `update._perform` (`:236-317`), `_update_installer_owned` (`:337-339`)
- `manager_versions.parse_brew_outdated_json` (`:52`), `brew_outdated` (`:158-165`)
- `pnpm_globals.split_install_groups`/`pnpm_global_groups` (`:438-486`)
- `scripts/container-e2e-verify.sh` `cmd_pass2`, `exec_tester`, `create_tester`

### Established Patterns
- Closed templating sets (`assets.py`); `~` expansion through `Path.expanduser`.
- One shared predicate for a decision that two layers need, so the plan and the executor can't disagree.
- Registry facts carry a `verified` date. Live truth is preferred over hand-kept facts when one cheap batched call gives it.

### Integration Points
- `METHOD_PARAMS["script"]` and `Tool.config_paths` ← `load_tools` validation
- `needs_manual` ← `build_plan` (MANUAL) and `engine.install_tool` (re-check)
- `removal_plan` L1/L3 ← the Uninstall projection (21) and `app.run_uninstall`
- The greedy cask set ← the refresh pass → OUTDATED → `u`/UPDATE
</code_context>

<specifics>
## Specific Ideas

- The acceptance anchors are `opencode uninstall --keep-config --keep-data` (pending source verification), `<omz_root>/tools/upgrade.sh`, `sdk selfupdate`, the `/home/linuxbrew` unwritable fixture, and `visual-studio-code` greedy-outdated.
</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `repair-pi-install-and-sync-models` (0.9): Phase 23.
- Dangling pnpm shims (0.6): Phase 21. GSD per-repo (0.6) and Playwright Chrome (0.6): outside the milestone.
</deferred>
