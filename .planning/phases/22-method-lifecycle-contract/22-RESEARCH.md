# Phase 22: Method lifecycle contract - Research

**Researched:** 2026-11-03
**Domain:** Python installer internals (uv, pytest, Textual): per-method update/removal contract, zero sudo, config lifecycle, container e2e
**Confidence:** MEDIUM-HIGH. The code seams are read and verified this session. Vendor data is verified for 7 of 14 script tools; the rest is tagged and needs a per-tool verification task.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Copied from `22-CONTEXT.md` (decision rule: best over easy). Where the code has moved since, see "Reality vs CONTEXT" below; the decisions still stand.

- **D-01:** `config_paths` is a tool-level field, parsed in `Tool` beside `requires`/`uninstall`. `paths`, `remove`, `update` and `writable_prefix` are method-level keys added to `METHOD_PARAMS["script"]` (18 D-01).
- **D-02:** The `config_paths` denylist comes from ONE source. The marker-directory tuples move out of `skill_lifecycle.HARNESS_PRESENCE` into `model.py`, beside `SKILL_HARNESSES`. `skill_lifecycle` builds `HARNESS_PRESENCE` from them plus its command names; the validator reads the same constant. Import direction stays `skill_lifecycle -> model`. Rules: an entry must be under `~`, at depth >= 2, and not under any harness marker dir. Errors name the tool and the key.
- **D-03:** Script `paths`/`remove`/`update` tokens get `~` expansion plus a closed set of named roots resolved in Python by existing resolvers (precedent: `{ver}`/`{arch.*}`, `assets.py:33`). No `sh -c`, no general `$VAR` expansion. First root is `{omz_root}`, resolved by `omz.omz_root(home, environ)`. OMZ `update = ["{omz_root}/tools/upgrade.sh"]`. An unknown placeholder is rejected at load.
- **D-04:** The 16 `kind = "script"` stanzas cover 14 tool ids: `uv`, `brew` x2 (actually x3 stanzas, see below), `oh-my-zsh`, `codex`, `claude`, `opencode`, `cursor-agent`, `antigravity`, `sdkman`, `bun`, `pnpm` x2, `volta`, `fnm`, `kitty`. `pi` is a `host_setup` tool: it gets a `verified` key but no script keys; its removal stays an L1 hint through its real owner.
- **D-05 (research needed):** Each script tool's `paths`/`remove`/`update` data is verified against the vendor's current docs or install script; each gets a `verified` date. A tool with no documented vendor uninstall gets no `remove`: removal is then just its receipt-proven `paths`, plus "remove it yourself" for the rest.
- **D-06:** `removal_plan(tool, state) -> RemovalPlan` (19 D-10) is extended, not redesigned. It gains the L3 branch (script `remove` plus receipt-proven `paths`). L1 gets `argv` only for brew/uv/pnpm with a receipt that proves the installer put the package there. L2 stays receipt-matched download/app artifacts. `argv`'s hook slot stays empty until Phase 23.
- **D-07:** Removal order for one tool: (1) run `remove`; non-zero exit = `remove_failed` with the vendor's error, nothing deleted, tool stays installed. (2) Delete receipt-proven `paths`/artifacts that still match their recorded type and target; other declared paths that exist are listed as "remove it yourself". (3) Delete the receipt. (4) Only when the per-row toggle is on and steps 1-3 succeeded, delete `config_paths`; a failure here is a warning and never restores the receipt.
- **D-08:** Native owners (dnf/apt/pacman/rpm-ostree) get a hint that names the package and never a command. The native entries of `_REMOVAL_COMMANDS` are deleted. Their package-less descriptions are the only phrasing. `ToolRow`, `OwnerHint`, `_manager_hint`/`_managed_hint` and the `setup.py` closures are deleted.
- **D-09:** The SDKMAN hint `sdk uninstall <candidate> <version>` takes its version from the `VersionStatus` the pass already reads (readlink of `current`). No second probe.
- **D-10:** The pnpm group warning on removal reuses `pnpm_globals` and the declared `co_install` groups. No new pnpm query.
- **D-11:** "Delete config too" is per row, off by default, offered only for tools with `config_paths`. The review lists exact paths. Config is deleted after step 3 only. CLI `--yes` never deletes config.
- **D-12:** MANUAL is decided at plan time. New `Disposition.MANUAL` shows "you run: `<exact command>`" in the review before anything runs. Applies to a native dnf/apt/pacman install method and to a script method whose `writable_prefix` is not user-writable. One shared predicate `needs_manual(method, state)`. The refresh pass records prefix writability as evidence (one stat per `writable_prefix`, no subprocess, no `sudo -n`). The engine re-checks the same predicate right before `_perform`. `RowOutcome` gains result `manual` in `WORDS`; it does not change the exit code; the row stays selected. The `_dnf`/`_apt`/`_pacman` sudo argv are deleted and a grep test bans `sudo`/`pkexec`/`doas` as first argv element. BLOCKED keeps its meaning ("nothing the installer can do"); MANUAL means "here is your command".
- **D-13:** The brew bootstrap is today's only `writable_prefix` consumer (`/opt/homebrew`, `/home/linuxbrew`). Check is `os.access(prefix, W_OK)`, or the nearest existing parent is user-owned and writable.
- **D-14:** The pinned-`app` refusal ("pinned; update outside or re-pin") is one early return in `update._perform`, parallel to the SDKMAN-candidate branch. `UpdateTarget` carries the version fact from `state_of`, so the TUI's `u` and headless UPDATE rows share the gate. `build_plan` never produces UPDATE for an app with no version source.
- **D-15:** A script `update` argv runs through `_update_installer_owned`'s script branch when declared; otherwise the vendor script re-runs. `sdkman` (the bootstrap) gets `update = ["sdk", "selfupdate"]`. SDKMAN candidates stay refused with their `sdk upgrade` hint; the two paths are never merged.
- **D-16:** Greedy casks. One batched `brew info --cask --installed --json=v2` call, cached with the existing brew inventory (6 h), gives live `auto_updates`. Only when an installed tracked cask has `auto_updates`, add one batched `brew outdated --cask --greedy --json=v2`, parsed by `parse_brew_outdated_json`. `u` runs `brew upgrade --cask --greedy <cask>` only for those casks. Linux unchanged. Researcher confirms flag shapes.
- **D-17:** Extend `cmd_pass2` in `scripts/container-e2e-verify.sh` with a HOME listing taken with no installer running: one before the first install, one after `--uninstall --yes`, both as `tester` through `exec_tester`. The run fails when a survivor is not under the union of the installed tools' `config_paths`. Transcript goes to `pass2-transcript.log`. One Fedora podman run recorded; container removed afterwards. No new subcommand.

### Claude's Discretion
- Plan and wave order. Suggested: (1) schema keys and denylist relocation, (2) zero sudo and MANUAL, (3) `removal_plan` L1/L3 extension and ordering, (4) update contract, (5) registry data after research, (6) e2e harness.
- The predicate's name, and the exact `{...}` root syntax.

### Deferred Ideas (OUT OF SCOPE)
- Reviewed todos not folded: `repair-pi-install-and-sync-models` (Phase 23), dangling pnpm shims (Phase 21), GSD per-repo and Playwright Chrome (outside the milestone).
- Out of scope per CONTEXT/SPEC: hook unregister/registration (23; `RemovalPlan.argv` hook slot unused), `cargo_distrobox` (24), Debian/Arch e2e runs and real-host UAT (24), migrating off-policy tools, any `dmg`/`distrobox`/Intel kind, running sudo in any form, Volta owner attribution (19; only its `volta uninstall` hint text belongs here).
- **rtk and skill packs are out of scope for the whole milestone (user decision 2026-11-02, RUN-LEDGER). Nothing here researches or plans them.**
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LIFE-01 | Script methods declare `paths`, `remove`, `update`; removal deletes only receipt-proven declared paths | New `artifact_paths` script branch, type-only receipt proof, vendor data table, removal order |
| LIFE-02 | Native dnf/apt/pacman installs handed off as exact command; no executor runs sudo | `Disposition.MANUAL`, `needs_manual`, handoff via existing `MANUAL_REQUIRED` path, grep test |
| LIFE-03 | brew/uv/pnpm uninstall only when a receipt proves it, else hint | `removal_plan` L1 from `receipts.read(...).method.kind/package`; delete native `_REMOVAL_COMMANDS` |
| LIFE-04 | `config_paths` with harness denylist | D-02 relocation; the `load_tools` validator |
| LIFE-05 | `u` refused for pinned `app` with no version source | `update_refusal` predicate; method-derived pinning (see Open Question 4) |
| LIFE-06 | Vendor update commands (OMZ, `sdk selfupdate`) | Script `update` argv branch; `sdk` is a shell function (Pitfall 2) |
| LIFE-07 | Unwritable prefix becomes handoff | Shared `needs_manual` predicate, pass-time stat evidence, engine re-check |
| LIFE-08 | pnpm co-install group warning on removal | Declared groups from method params (not `split_install_groups`; Pitfall 6) |
| LIFE-09 | Container e2e compares file listings | `cmd_pass2` extension; residue allowlist (Pitfall 9) |
| LIFE-10 | Greedy casks on macOS | Verified flag shapes; batched `brew info` + `brew outdated --greedy` |
| UI-04 | "Delete config too" per row | Needs `RemovalPlan.config`; modal/row toggle; `UninstallDecision` extension; needs a UI contract |
</phase_requirements>

## Summary

Phase 21 and Phase 19 landed, but not exactly as CONTEXT describes. The biggest gap: the `removal_plan(tool, state) -> RemovalPlan(level, argv, paths, config, hint)` seam does not exist. `RemovalPlan` in `installer/uninstall.py` is Phase 19's file-oriented split (`removable`, `yourself`, `by_tool`, `artifacts`), stored in `ToolState.removable` and read by `uninstall_group`, `uninstall_detail`, `run_uninstall` and `perform_uninstall`. Phase 22 must evolve that dataclass into the R2 shape while keeping those readers working. The good news: `ToolRow`, `OwnerHint`, the manager-hint helpers and the `setup.py` closures are already gone (Phase 21), and the `manual` result and `MANUAL_REQUIRED` handoff path already exist, so MANUAL is mostly a plan-time disposition over existing plumbing.

The hardest design problem is L3 proof for script-installed trees. Receipts today fingerprint files by sha256 and directories by one key file's sha256. Script trees (`~/.bun`, `~/.sdkman`, `~/.local/share/claude`, `~/.local/kitty.app`) self-update constantly, and `claude`, `antigravity`, `codex` auto-update in the background. Hash-based proof would flip them to "changed since install" and make them non-removable. The SPEC wording ("still match their recorded type and link target") already implies a type-only proof; this needs a small receipt extension (see Pitfall 1).

Three factual corrections to the locked anchors need user attention: (a) `sdk` is a shell function, so `update = ["sdk","selfupdate"]` cannot run as a bare argv; (b) the SPEC's anchor `opencode uninstall --keep-config --keep-data` is valid for OpenCode 1.x (what the registry's installer installs) but exits 1 on OpenCode 2.x, and non-interactive runs need `--force`; (c) `omz.omz_root` prefers `~/.oh-my-zsh` over `$ZSH`, the opposite of the SPEC wording.

**Primary recommendation:** Build in this order: schema + denylist, then `needs_manual`/MANUAL + sudo deletion, then the receipt type-only proof and the `removal_plan` evolution (L1/L2/L3 + config + hint), then update contract, then registry data (one verification task per tool, container-checked), then UI-04, then the e2e harness. No new packages are needed.

## Reality vs CONTEXT (verified by reading code this session)

| CONTEXT/SPEC says | Reality | Impact |
|---|---|---|
| `removal_plan(tool, state)` extended (19 D-10) | Does not exist. `RemovalPlan(removable, yourself, by_tool, artifacts)` at `installer/uninstall.py:55-77`; `plan_removal(tools, bin_dir, *, verify)` at `:133`; `ToolState.removable: RemovalPlan` at `installer/version_status.py:779` | Phase 22 creates the R2 shape; 5+ consumers must move together (`uninstall_group` `:1921`, `uninstall_detail` `:1948`, `run_uninstall` `app.py:498`, `perform_uninstall` `app.py:652`, `version_status.py:1805,1815`) |
| `ToolRow`, `OwnerHint`, `_manager_hint`, `setup.py:807-868` closures to delete | Already deleted; grep finds zero hits in `installer/` and `setup.py` | Nothing to delete except what is listed next |
| Delete native entries of `_REMOVAL_COMMANDS` (`ownership.py:1378-1381`) | Now `installer/ownership.py:1486-1501`; readers: `removal_hint` (`:1618`), `method_removal_command` (`:1586`, used by `engine.py:242` for the smoke-failure leftover text), `removal_label` | Deleting native entries also changes `engine.py:242`'s leftover message for native methods; keep brew/cask/pnpm/uv/volta/sdkman templates (hint-only) |
| sudo argv at `executors.py:370-379` | Now `installer/executors.py:448-457` (`_dnf`, `_apt`, `_pacman`) | Tests assert the argv: `tests/test_engine.py:103,1010` must be rewritten |
| `Disposition.MANUAL` (20 D-01) | Not present. `Disposition` at `installer/session.py:87-98` has WAIT, INSTALL, UPDATE, REPAIR, RECONFIGURE, REINSTALL, SKIP, BLOCKED, REMOVE. Result `"manual"` already exists (`session.py:110`, L-20-02) | Add the disposition, a `WORDS` entry (dict must be exhaustive), `_REVIEW_ORDER`, `RUNNABLE` membership |
| `omz_root` honors `$ZSH` (SPEC: "`$ZSH` when set, otherwise `~/.oh-my-zsh`") | `installer/omz.py:530-543`: returns `home/.oh-my-zsh` if that dir exists, else `$ZSH` if it is a dir, else None | Resolver is default-first. Use as is (CONTEXT D-03 says use the existing resolver); the fake-runner test with `$ZSH` set and no default dir passes. Flag the SPEC wording mismatch |
| `UpdateTarget` carries the version fact | `UpdateTarget(tool, ownership)` only (`update.py:~137`) | See Open Question 4 |
| "each script tool gets a `verified` date key" | `verified` is already a required tool-level key (every `[[tool]]`, incl. `pi`: `verified: 2026-10-13`) | No new key; refresh the date as each tool's data is verified |
| Dead code to delete: 4 `POST_INSTALL_ACTIONS` names, `Tool.source`/`owner` | `source_shell_init`, `enable_corepack`, `pnpm_setup`, `write_agent_reference` have zero references in `installer/*.py` or `registry.toml`; `Tool.source`, `Tool.owner`, `Tool.uninstall` (`model.py:408-410`) are set only for `pi` and read nowhere in production | Deletion tasks (SPEC boundary, rule 5) |
| 16 script stanzas / 14 ids | The registry has 17 script stanzas: `brew` has 3 (macos arm64, macos amd64, debian/arch/fedora), `pnpm` 2, `kitty` 2 | `writable_prefix` applies to the Linux brew stanza only (`/home/linuxbrew`); the macOS stanzas use `/opt/homebrew` and `/usr/local` |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `config_paths` / script-key validation | Registry load (`model.py`) | -- | Closed-set validation at load, fail-closed |
| Removal proof and `RemovalPlan` | Core (`uninstall.py`, `receipts.py`) | Refresh pass (stores plan in `ToolState`) | Pure and computed in the pass; consumers only read |
| Removal execution (`remove` argv, deletes, order) | Core (`app.perform_uninstall` calling `uninstall`) | Worker thread (Phase 21 `uninstall-removal`) | Mutations stay off the UI thread under `MutationLock` |
| `needs_manual` predicate | Core (one module) | `build_plan` (plan time), `engine` (execute time) | One predicate so plan and executor cannot disagree |
| Prefix writability evidence | Refresh pass (one stat each) | -- | `build_plan` is pure and must not probe |
| Update argv, pinned refusal | `update.py` (`update_refusal`, `_update_installer_owned`) | `catalog_tui` `u`, `session.build_plan` | Shared refusal predicate already exists |
| Greedy cask detection | `manager_versions.py` + `version_status.resolve_status` | `update.resolve_update_argv` | Same pass that already reads brew |
| Delete-config toggle UI | `wizard_app.UninstallScreen` + `ConfirmUninstall` | `UninstallDecision` | UI collects, core decides |
| E2E leftover check | `scripts/container-e2e-verify.sh` | -- | Container-only, never the host |

## Standard Stack

No new libraries. Everything uses what the repo already has. [VERIFIED: pyproject/Makefile conventions in `AGENTS.md`]

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`os`, `pathlib`, `shutil`, `tomllib`) | project Python | Stat-based writability, path deletion, TOML | Zero-dependency; the repo already uses these |
| Textual | repo pin | Uninstall screen toggle, pilot tests | Existing UI framework (`wizard_app.py`) |
| pytest + pytest-xdist + coverage | repo pin | Tests (`make test`) | Project standard (`.claude/testing.md`) |
| podman | 5.8.9 on this host [VERIFIED: `podman --version`] | Container e2e (`make e2e`) | Existing harness |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `type="tree"` receipt artifact for script dirs | Reuse `dir` + key file | Key-file hashes drift with every vendor self-update; rejected (Pitfall 1) |
| A shell for `{omz_root}`/`$ZSH` | Python resolver | CONTEXT D-03 locks the resolver; no shell injection surface |

**Installation:** none. **Package Legitimacy Audit:** no external packages are added or removed by this phase, so the gate has nothing to audit. Packages removed due to SLOP: none. Packages flagged SUS: none.

## Architecture Patterns

### System Architecture Diagram

```
registry.toml (script keys, config_paths)
        |  load_tools (closed keys, closed {roots}, denylist)
        v
   Tool / Method
        |
 install_tool --needs_manual(method, state)?--yes--> MANUAL_REQUIRED(handoff: exact command) -> "manual" row
        |no
   _perform -> executor -> receipts.record (artifact_paths incl. script `paths`: type/link target only)
        |
 refresh pass --> ToolState{ownership, version, receipt, removal_plan, prefix evidence}
        |                         |
        |                 removal_plan(tool,state): L1 argv (receipt proves brew/uv/pnpm pkg)
        |                                           L2 receipt artifacts (download/app)
        |                                           L3 script remove argv + receipt-proven paths
        |                                           none -> hint (native, sdkman, volta, unknown)
        v
 Uninstall view / CLI  --confirm--> perform_uninstall (worker, MutationLock)
        per tool: [1 remove argv] -fail-> remove_failed, stop
                  [2 delete proven paths/artifacts; others = "remove it yourself"]
                  [3 delete receipt]
                  [4 if toggle on and 1-3 ok: delete config_paths; failure = warning]
        v
 invalidate + one refresh pass
```

`u` path: `catalog_tui.action_update_tool` -> `UpdateService.run` -> `update._perform` -> `update_refusal` (unknown owner, sdkman candidate, native, volta, **pinned app**) -> owner dispatch -> script `update` argv, else vendor script.

### Recommended Project Structure
No new top-level modules are required. Suggested placement:
```
installer/model.py        # HARNESS_MARKER_DIRS, script keys in METHOD_PARAMS, config_paths parse+validate, root placeholders
installer/skill_lifecycle.py  # builds HARNESS_PRESENCE from model markers + commands
installer/download.py     # artifact_paths gains the script branch (declared `paths`)
installer/receipts.py     # type-only artifact for script trees; L1 proof helper
installer/uninstall.py    # RemovalPlan evolves; removal_plan(); ordered executor of steps 1-4
installer/session.py      # Disposition.MANUAL, WORDS, build_plan branch
installer/engine.py       # needs_manual re-check before _perform; native handoff
installer/executors.py    # delete _dnf/_apt/_pacman sudo; native_handoff(method)
installer/update.py       # pinned-app refusal, script update argv
installer/manager_versions.py / version_status.py  # greedy cask evidence
scripts/container-e2e-verify.sh  # cmd_pass2 listings
```

### Pattern 1: One shared predicate (plan time and execute time)
**What:** `needs_manual(method, platform_or_state) -> str | None` returns the exact command text or None. `build_plan` turns it into `Disposition.MANUAL` with the command in `reason`; `engine.install_tool` calls it again right before `_perform` and returns `MANUAL_REQUIRED` with `handoff=(command,)`, the same outcome `host_setup` already uses (`engine.py:132-135, 227-234`). The e2e parser already counts `manual — see the setup steps in the log` rows (`container-e2e-verify.sh`), so the report line stays compatible.
**When to use:** native kind (`dnf`/`apt`/`pacman`) and a script with `writable_prefix` whose evidence says unwritable.
**Command text:** `sudo dnf install -y <pkg>`, `sudo apt-get install -y <pkg>`, `sudo pacman -S --noconfirm --needed <pkg>`. These are display strings, not argv: the grep test must scan list literals whose first element is `sudo`/`pkexec`/`doas`, which keeps `systemd_daemon.py:846-848` f-strings and `guidance.py` prose legal. Existing precedent: `tests/test_plan.py:260 test_no_sudo_argv_on_the_plan_path`.

### Pattern 2: Receipt proof for script `paths` is type-only
**What:** `download.artifact_paths(method, bin_dir)` gains a branch for `kind == "script"` returning an `Artifact` per declared `paths` entry after `~`/root expansion. The type (`file`, `link`, `dir`) is declared in the registry token form or inferred at record time from the live path (record-time inference is safer against registry typos). The receipt stores `{path, type}` plus `target` for a link. Match = same lstat type; a `dir` must be a real directory (not a symlink); a `link` must still be a symlink and its target must either equal the recorded target or resolve under another proven dir of the same tool (needed for auto-updating `claude`, whose `~/.local/bin/claude` link retargets on every update [CITED: code.claude.com/docs/en/setup]). Mark this extension [ASSUMED] design, to confirm in discuss/plan.
**Deletion:** a type-only dir is deleted through the existing quarantine rename (`uninstall._remove_dir`), re-checking `is_dir and not is_symlink` inside the quarantine instead of re-hashing a key file.
**Why not hashes:** see Pitfall 1.

### Pattern 3: Removal step order (D-07), per tool, sequential
1. `remove` argv through the runner (`start_new_session`, stdin closed: `run.py` uses `stdin=DEVNULL`, `start_new_session=True`). Non-zero = `remove_failed` with the vendor's first error line; stop.
2. Delete receipt-proven artifacts (existing `remove_proven`/`remove_paths` re-proof at deletion time).
3. `receipts.delete(tool_id)`.
4. If toggle on: delete each `config_paths` entry that exists; a path already gone is skipped; a shared path across two selected tools is deleted once and only if both toggles are on (SPEC edge table). Failure = warning.

### Anti-Patterns to Avoid
- **Hashing vendor-managed trees** (breaks removal after any self-update).
- **Running `sdk ...` as a bare argv** (it is a function; see Pitfall 2).
- **Deleting config in the CLI path or on a failed removal.**
- **Reusing `split_install_groups` for the removal warning** (it reports pnpm-split groups, a different question; Pitfall 6).
- **A second probe for prefix writability inside `build_plan`** (it is pure; evidence comes from the pass).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Directory deletion with race safety | New rmtree wrapper | `uninstall._remove_dir` quarantine pattern, extended for type-only trees | Already handles interrupt/put-back/RR-01 |
| Handoff display | New "you run" channel | `InstallStatus.MANUAL_REQUIRED` + `InstallOutcome.handoff` + result `manual` | Already rendered, counted and parsed by e2e |
| OMZ location | Env/`~` guessing | `omz.omz_root(home, environ)` | CR-01 single source |
| Brew JSON parsing | New parser | `manager_versions.parse_brew_outdated_json` (`:52`) | Already returns `(formulae, casks)` maps |
| Auth for sdk | Own sourcing code | The `_sdkman` pipeline pattern (`executors.py:556-575`) | Same `. sdkman-init.sh && sdk ...` shape |
| Refusal wording | New copy per surface | `update_refusal` (one predicate for TUI and plan) | Review cannot promise what the engine refuses |
| Atomic writes | Own temp-file code | `installer/atomic.py` | Phase 17 D-05 |

**Key insight:** every new rule here is a variation of an existing seam. The risk is divergence (two predicates, two probes), not missing machinery.

## Runtime State Inventory

> This is not a rename phase, but it changes removal semantics for installed state. Included because uninstall acts on runtime state outside git.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing receipts at `~/.local/state/tools-installer/receipts/<id>.json` (schema `"v": 1`) written before this phase hold NO script `paths` artifacts (script/manager kinds record empty artifacts: `receipts.record` docstring) | Existing script installs stay unprovable for L3 until reinstall/`u` re-records; plan must say so ("remove it yourself") rather than guess. No data migration |
| Live service config | None | None |
| OS-registered state | None for this phase | None |
| Secrets/env vars | None | None |
| Build artifacts | None | None |

## Common Pitfalls

### Pitfall 1: Hash-proved script trees go "changed since install" after a vendor self-update
**What goes wrong:** `claude`, `codex`, `antigravity`, `opencode` auto-update in the background [CITED: code.claude.com/docs/en/setup; antigravity install.sh line 59, VERIFIED by curl this session]; `bun upgrade`, `sdk selfupdate` rewrite their trees. Phase 19's "one changed artifact makes the whole tool non-removable" then makes them unremovable.
**How to avoid:** type-only proof for script `paths` (Pattern 2). Extend `receipts._read_artifact`, `fingerprint`, `matches` and `_remove_dir` verification; keep schema `"v": 1` (an unknown artifact type already fails closed in older readers).
**Warning signs:** a fixture that updates a file inside a proven dir and still expects removable.

### Pitfall 2: `sdk` is a shell function, not an executable
**What goes wrong:** `update = ["sdk","selfupdate"]` (D-15) raises FileNotFoundError. [VERIFIED: on this host `command -v sdk` prints the function, and `bash -c 'command -v sdk'` returns rc=1]. `sdk help` lists `selfupdate [force]` [VERIFIED: local run].
**How to avoid:** when a script `update`/`remove` argv starts with `sdk`, run it through the same pipeline as `_sdkman`: `bash -c '. "$HOME/.sdkman/bin/sdkman-init.sh" && sdk selfupdate'`. Factor one helper used by `_sdkman` and the update branch. The fake-runner assertion then checks the pipeline string contains `sdk selfupdate`.

### Pitfall 3: OpenCode uninstall flags differ by major version
**What goes wrong:** the registry installer (`https://opencode.ai/install`) installs OpenCode 1 only [VERIFIED: install script lines 70-79, "This installer only installs OpenCode 1"]. OpenCode 1 documents `--keep-config`, `--keep-data`, `--dry-run`, `--force` [CITED: opencode.ai/docs/cli]. This host runs OpenCode v2.0.31, whose `uninstall` accepts only `--dry-run` and `--force`, keeps config/data by default, and `opencode uninstall --keep-config --keep-data --dry-run` exits 1 [VERIFIED: local runs, rc=1 vs rc=0]. Also the runner closes stdin, so without `--force` the confirmation prompt cannot be answered (behavior on v1 [ASSUMED]; verify in the container).
**How to avoid:** `remove = ["opencode","uninstall","--keep-config","--keep-data","--force"]` (the SPEC anchor plus `--force`, because the user already confirmed in the review). A v2 install then fails closed: `remove_failed`, nothing deleted, vendor error shown. Record this in the registry comment. Open Question 1.

### Pitfall 4: A native-first ladder with a brew fallback
**What goes wrong:** `git`, `jq`, `zsh`, `watch`, `docker`, `podman`, `alacritty`, `glab` list a native method (rank 30) before brew (40) [VERIFIED: registry scan + `resolve.py _RANK`]. If a native method becomes a handoff that ends the ladder, a Fedora machine with brew present never reaches the brew fallback, and `requires`-dependents (zsh -> oh-my-zsh) become dependency-failed.
**How to avoid:** decide in discuss (Open Question 2). Either way, `build_plan` must treat a MANUAL row as unsatisfied for its dependents (today only BLOCKED feeds `unsatisfied`, `session.py` `build_plan`), so dependents read "needs zsh" at plan time. The e2e `dependency_failures_explained` already tolerates manual blockers.

### Pitfall 5: OMZ and Homebrew uninstall scripts mutate things outside their trees
**What goes wrong:** OMZ `tools/uninstall.sh` exists [VERIFIED: HTTP 200 on raw.githubusercontent.com/.../tools/uninstall.sh] but restores `~/.zshrc` and may change the login shell [ASSUMED]; deleting only `~/.oh-my-zsh` leaves `.zshrc` sourcing a missing file. Homebrew's uninstaller is a curl-piped script, `NONINTERACTIVE=1 /bin/bash -c "$(curl ... uninstall.sh)"` [CITED: github.com/Homebrew/install], not an argv, and removes the whole prefix with every package.
**How to avoid:** `oh-my-zsh`: `update` only; no `remove`, no `paths` (hint "run uninstall_oh_my_zsh yourself"). `brew`: `update` only; no `remove`. Both stay listed as "remove it yourself". This follows D-05 ("no documented vendor uninstall argv gets no remove"). The shell-tweak sweep (`omz-plugins` policy) is unchanged.

### Pitfall 6: `split_install_groups` answers a different question
`pnpm_globals.split_install_groups(policy, live)` (`:470`) returns declared groups pnpm is holding **apart** (needs a live `pnpm list -g --json` query). LIFE-08 needs "this package belongs to a declared co-install group; here are its other members": that is static data from the node method (`npm_pkg` + `co_install`, `NodeInstallPolicy.groups` `pnpm_globals.py:121`). Use the declared groups; no pnpm query (this matches D-10's "no new pnpm query" intent). Warning text must show in the review before anything runs (SPEC edge "ordering").

### Pitfall 7: The registry says SDKMAN and Volta have no safe `remove` argv
`sdk uninstall <candidate> <version>` stays a hint (D-09). SDKMAN's own uninstall is manual: `rm -rf ~/.sdkman` plus removing the init snippet from shell rc [CITED: sdkman.io/install]. Receipt-proven `~/.sdkman` deletion would leave the rc snippet; the managed `source` line is not ours. Recommend `sdkman`: `update` only plus hint, no `paths` (same reasoning as OMZ). `volta`: `~/.volta` removal is documented as deleting the dir [ASSUMED, verify]; the rc PATH/`VOLTA_HOME` lines are installer-written, same hazard.

### Pitfall 8: Greedy is only meaningful where casks exist
`brew info --cask --installed --json=v2` ran on this Linux host and returned the `formulae`/`casks` object [VERIFIED: local run]; `brew outdated --greedy` and `brew upgrade --greedy` exist [VERIFIED: `brew outdated --help`, `brew upgrade --help`: `-g, --greedy`, `--greedy-auto-updates`]. Cask JSON carries `auto_updates` [CITED: docs.brew.sh Cask JSON API / `brew info --json=v2`; field name [ASSUMED] to re-check against a macOS-shaped fixture]. Prefer `--greedy-auto-updates` over `--greedy` in the argv: `--greedy` also pulls `version :latest` casks, which the SPEC says must keep the non-greedy path. This narrows D-16/SPEC wording from `--greedy` to `--greedy-auto-updates`; keep `--greedy` only if the user wants the literal AC string (Open Question 5). Linux unchanged: gate on `platform.os == "macos"`.

### Pitfall 9: The e2e residue check cannot be a literal subset of `config_paths`
`cmd_pass2` installs the whole catalog (`--all --yes`). After `--uninstall --yes` real residue includes: rc files (`.bashrc`, `.zshrc`, `~/.myshellrc` edited and left), `~/.local/state/tools-installer/` empties, caches, and harness dirs (`claude` writes `~/.claude/downloads` [VERIFIED: install.sh:39]; `~/.claude`, `~/.codex`, `~/.cursor`, `~/.gemini` can never be `config_paths`). Also RUN-LEDGER line 15 records that only ~46 of 74 installed tools were removed by the sweep before this phase, so many tools leave big trees until L3 data lands.
**How to avoid:** the check is `after - before - union(expanded config_paths) - E2E_RESIDUE_ALLOWLIST`, where the allowlist is a short, documented, committed list (rc files and their `.bak`, installer state dir, harness marker dirs from the same constant as the denylist). Fail on anything else. Include a planted-leftover self-test (the harness must fail on a planted file and pass clean). Take listings via `exec_tester 'find ~ -mindepth 1 ... | sort'` with no installer running.

### Pitfall 10: `MANUAL` is another exhaustive-dict member
`WORDS: dict[Disposition, Words]` (`session.py:136`), `_REVIEW_ORDER`, `RUNNABLE`, `render.py` (`WORDS[row.disposition]` at several sites), `exit_code`/`retained` tests all enumerate dispositions. Missing one is a KeyError in the review. A parametrized test over `Disposition` is the cheap guard.

### Pitfall 11: Existing sudo tests
`tests/test_engine.py:103,144,159,793,1010` encode the sudo argv and a "sudo" attempt ladder; they must be rewritten to assert the handoff and zero runner calls, not deleted (Never bypass a quality gate).

## Code Examples

### Existing handoff path to reuse (native becomes MANUAL_REQUIRED)
```python
# Source: installer/engine.py:225-234 (read this session)
verified, unverified_reason, handoff = _perform(tool, method, ctx)
if handoff:
    return InstallOutcome(
        tool.id,
        InstallStatus.MANUAL_REQUIRED,
        method_kind=method.kind,
        handoff=handoff,
    )
```
`needs_manual` runs just before this and returns the same outcome with `handoff=(command,)`.

### sdk pipeline pattern (reuse for `sdk selfupdate`)
```python
# Source: installer/executors.py:556-575 (read this session)
pipeline = f'{_path_prefix()}. "$HOME/.sdkman/bin/sdkman-init.sh" && {shlex.join(install)}'
runner(["bash", "-c", pipeline])
```

### Pinned-app refusal (recommended shape)
```python
# Source: pattern at installer/update.py update_refusal (read this session); new branch is a recommendation
method = ownership.method
if method is not None and method.kind in ("app",) and _is_pinned(method):
    return UpdateOutcome(
        tool_id=tool.id, status="unsupported", owner=ownership.owner,
        detail="pinned; update outside or re-pin",
    )
# _is_pinned: isinstance(url, str) and "{ver}" in url  (same test model.py:802 uses)
```

### Greedy cask commands (flag shapes verified on this host's brew)
```bash
brew info --cask --installed --json=v2          # live auto_updates truth
brew outdated --cask --greedy-auto-updates --json=v2
brew upgrade --cask --greedy-auto-updates --appdir=<applications_dir> <cask>
```

## Vendor data (D-05)

Provenance per row. Rows marked "verify" need a plan task that reads the vendor script/docs and runs in the Fedora container before the registry edit lands (the project's per-tool checklist, `.claude/architecture.md`).

| Tool | `update` | `remove` | `paths` (receipt-recorded, type-only) | Source / status |
|------|----------|----------|----------------------------------------|-----------------|
| uv | `["uv","self","update"]` | none (no vendor uninstall command) | `~/.local/bin/uv`, `~/.local/bin/uvx` | [CITED: docs.astral.sh/uv/getting-started/installation] "rm ~/.local/bin/uv ~/.local/bin/uvx"; self update only for the standalone installer. `uv tool dir`/`uv python dir` are user data, never removed |
| brew | `["brew","update"]` [ASSUMED] | none | none | Uninstall is a curl-piped script that may need privilege [CITED: github.com/Homebrew/install]; hint only. Add `HOMEBREW_NO_SUDO=1` to the stanza env as defense in depth [CITED: github.com/Homebrew/install] |
| oh-my-zsh | `["{omz_root}/tools/upgrade.sh"]` | none (Pitfall 5) | none | upgrade.sh exists, `#!/usr/bin/env zsh` [VERIFIED: raw.githubusercontent.com ... tools/upgrade.sh]. Executable bit [ASSUMED]; if it is not +x, use `["zsh","{omz_root}/tools/upgrade.sh"]` |
| claude | `["claude","update"]` | none | `~/.local/bin/claude` (link), `~/.local/share/claude` (dir) | [CITED: code.claude.com/docs/en/setup] native uninstall is `rm -f ~/.local/bin/claude; rm -rf ~/.local/share/claude`. `~/.claude`, `~/.claude.json` are config: NOT declarable (denylist) |
| codex | `["codex","update"]` | none documented | `~/.local/bin/codex`, `~/.local/bin/codex-code-mode-host`, `~/.codex/packages/standalone` | `codex update` [VERIFIED: local `codex --help`]; paths [VERIFIED: install.sh lines 16-20]. Registry `bin_dir` is `~/.codex/packages/standalone/current/bin`; reconcile in the verify task |
| opencode | `["opencode","upgrade"]` [ASSUMED for v1; v2 help lists `upgrade, update`, VERIFIED] | `["opencode","uninstall","--keep-config","--keep-data","--force"]` | `~/.opencode/bin/opencode` | Flags [CITED: opencode.ai/docs/cli]; v2 rejects them (Pitfall 3); path from the registry's verified comment |
| cursor-agent | `["cursor-agent","update"]` | none (`uninstall-shell-integration` only edits `~/.zshrc`) | `~/.local/bin/agent`, `~/.local/bin/cursor-agent` (links), `~/.local/share/cursor-agent` (dir) | [VERIFIED: install script lines 110-131; local `cursor-agent --help`]. `~/.local/share/cursor-agent` is also in the harness markers, so it is a `paths` entry, never `config_paths` |
| antigravity | re-run script (no documented command) | none | `~/.local/bin/<binary>` (verify name) | Self-updates in the background [VERIFIED: install.sh:59]; verify |
| sdkman | `["sdk","selfupdate"]` via the sourced pipeline (Pitfall 2) | none (Pitfall 7) | none | [VERIFIED: `sdk help` lists `selfupdate [force]`]; uninstall manual [CITED: sdkman.io/install] |
| bun | `["bun","upgrade"]` [VERIFIED: local `bun upgrade --help`] | none | `~/.bun` (dir) | uninstall = delete `~/.bun` [ASSUMED]; verify |
| pnpm | `["pnpm","self-update"]` [VERIFIED: local `pnpm self-update` usage] | none | `~/.local/share/pnpm` (Linux), `~/Library/pnpm` (macOS) | verify the PNPM_HOME layout and shim dir |
| volta | re-run script | `volta uninstall` removes a *tool*, not volta [VERIFIED: local `volta --help`]; none | `~/.volta` (dir) | verify; the hint text for volta-owned packages is the only in-scope piece (Phase 19 owns attribution) |
| fnm | re-run script | none (`fnm uninstall` removes a Node version) [VERIFIED: local `fnm --help`] | `~/.local/share/fnm` (dir) | verify |
| kitty | re-run installer (`launch=n`) | none | `~/.local/kitty.app` (dir; `/Applications/kitty.app` on macOS), `~/.local/bin/kitty`, `~/.local/bin/kitten` (links), `~/.local/share/applications/kitty.desktop`, `kitty-open.desktop` | [CITED: sw.kovidgoyal.net/kitty/binary] "To uninstall, simply delete that directory"; installer touches only that directory |
| pi | none | none | none | `host_setup`; only the `verified` date, hint through pnpm |

Net effect: `remove` argv ships for opencode only. Every other script tool is "receipt-proven paths + remove it yourself". That is the honest D-05 outcome, not a gap.

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Removal by name match (`plan_uninstall`) | Receipt-proven `artifact_paths` (Phase 19) | Phase 22 completes it for script and manager kinds |
| `sudo dnf/apt/pacman` in executors | Plan-time MANUAL handoff | Executors become sudo-free by construction |
| OpenCode 1 `uninstall --keep-*` | OpenCode 2 keeps config/data by default, `--dry-run`/`--force` only | Registry pins v1 installer; v2 users fail closed |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Type-only receipt proof (a new artifact shape) is acceptable to the user and compatible with 19's reader | Pattern 2, Pitfall 1 | If rejected, script L3 needs another proof; scope grows |
| A2 | `opencode uninstall` on v1 blocks on a prompt with stdin closed, so `--force` is needed | Pitfall 3 | If not needed, `--force` is harmless; if the SPEC string must match exactly, the AC test string changes |
| A3 | OMZ `tools/upgrade.sh` is executable in git | Vendor table | If not, argv must be `["zsh", path]`; the AC string changes |
| A4 | `brew update` is the right self-update for Homebrew itself | Vendor table | Wrong `update` for brew |
| A5 | Cask JSON field is `auto_updates` | Pitfall 8 | Greedy detection silently finds nothing; a macOS fixture must pin the real shape |
| A6 | OMZ `uninstall.sh` rewrites `.zshrc` and may chsh | Pitfall 5 | If harmless, an OMZ `remove` could be added |
| A7 | bun, pnpm, volta, fnm, antigravity layouts and update commands | Vendor table | Wrong `paths`/`update`; mitigated by the per-tool verify task |
| A8 | Tarball pinned (`{ver}` url) should be refused like app | Open Question 4 | SPEC only names `app` |

## Open Questions

1. **OpenCode `remove` string.** SPEC anchor is `opencode uninstall --keep-config --keep-data`; I recommend appending `--force`, and accept that OpenCode 2 installs fail closed. Alternatively declare no `remove` and rely on paths. Needs a user call (one line in discuss) or planner default = with `--force`.
2. **Native-first ladder with brew fallback** (Pitfall 4). Literal SPEC: handoff ends the ladder. Alternative: when a later userspace/brew method applies, skip the native method instead of handing off. Recommendation: follow the SPEC literally and show the dependents as blocked at plan time; confirm with the user because this changes what `git`/`jq`/`zsh` do on Fedora-with-brew.
3. **Receipt shape for script trees** (A1). Planner should confirm "type-only" and the link-target rule (recorded target, or under a proven dir of the same tool).
4. **Pinned-app gate.** CONTEXT D-14 puts the version fact on `UpdateTarget`. A method-derived predicate (`kind == "app"` and url contains `{ver}`, the same test as `model.py:800-803`) needs no new field, is pure, and is correct because a pinned URL can never upgrade; an unpinned `app` such as vscode macOS re-downloads "latest" and stays allowed. Recommend the method-derived gate inside `update_refusal` (so `build_plan` and `u` share it). Decide whether pinned `tarball` is included.
5. **Greedy flag.** `--greedy-auto-updates` (precise) vs `--greedy` (SPEC string). Recommend the precise flag.
6. **UI contract for UI-04.** `workflow.ui_phase` is true and no `22-UI-SPEC.md` exists. The per-row toggle (key on the row vs a section in `ConfirmUninstall`) and the 80x20 fit need a short UI contract before planning, or the plan must define one.
7. **OMZ/`omz_root` precedence** differs from the SPEC sentence (default dir first). Use the resolver as is.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| podman | Container e2e (R11) | yes | 5.8.9 | none; e2e is container-only |
| uv, pytest toolchain | All tests | yes | repo-pinned | -- |
| brew (Linux) | Greedy flag shape checks, local fixtures | yes | linuxbrew on this host | macOS-shaped JSON fixtures |
| macOS | Real greedy-cask behavior | no | -- | Fake brew runner and JSON fixtures; real-host check is Phase 24 UAT |
| Network (vendor scripts/docs) | Per-tool verify tasks | yes | -- | -- |

**Rules respected:** no `make setup`/`fix`/`uninstall`, no real installs or removals on this host; vendor commands were only run with `--help`/`--dry-run`. Real install/remove runs only in the disposable container.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-xdist + coverage (`pyproject.toml`), Textual pilot for screens |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`; `tests/conftest.py` (sandboxed HOME, receipts dir) |
| Quick run command | `uv run pytest tests/test_<module>.py -x` |
| Full suite command | `make validate && make test` (about 5011 tests at the end of Phase 21) |
| E2E | `make e2e` (`scripts/container-e2e-verify.sh all`, disposable Fedora container) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIFE-01 | opencode removal runs the `remove` argv (fake runner); foreign file at a declared path survives; failing `remove` keeps all paths and fails the row; type-only proof survives an in-place vendor update | unit | `uv run pytest tests/test_uninstall.py tests/test_receipts.py -x` | extend; script fixtures ❌ Wave 0 |
| R2 (all kinds) | install writes receipt, Uninstall shows removable, removal leaves no receipt path (scratch HOME, every kind) | integration | `uv run pytest tests/test_uninstall_e2e.py -x` | extend |
| LIFE-02 | grep/AST test: no list literal in `installer/` with first element `sudo`/`pkexec`/`doas`; native-only tool yields MANUAL with the exact command and zero runner calls | unit/grep | `uv run pytest tests/test_plan.py tests/test_executors.py tests/test_engine.py -x` | rewrite sudo tests |
| LIFE-03 | receipt-proven brew/uv/pnpm package runs `brew uninstall <pkg>`; no receipt = hint, zero runner calls; dnf owner = package-naming hint, no argv | unit | `uv run pytest tests/test_uninstall.py tests/test_ownership.py -x` | extend |
| LIFE-04 | `~/.claude/x`, `~`, `/etc/x` rejected with key and tool named; `~/.config/gh` accepted; denylist single-sourced from `model.py` (test that `HARNESS_PRESENCE` markers derive from it) | unit | `uv run pytest tests/test_registry.py tests/test_model.py -x` | extend |
| LIFE-05 | `u` on pinned draw.io runs nothing, shows "pinned; update outside or re-pin"; unpinned vscode still updates | unit + pilot | `uv run pytest tests/test_update.py tests/test_catalog_tui.py -x` | extend |
| LIFE-06 | `u` on OMZ runs `<omz_root>/tools/upgrade.sh` (`$ZSH` set, no default dir); `u` on SDKMAN runs the sourced `sdk selfupdate` pipeline; child gets stdin closed and a new session | unit | `uv run pytest tests/test_update.py -x` | extend |
| LIFE-07 | unwritable `/home/linuxbrew` fixture = MANUAL, zero executions; writable proceeds; engine re-check catches a prefix that became unwritable after planning | unit | `uv run pytest tests/test_session.py tests/test_engine.py -x` | extend |
| LIFE-08 | removing one member of a two-member group warns, naming group and others, in the review; non-member no warning; removing all members gives one warning | unit + pilot | `uv run pytest tests/test_uninstall.py tests/test_wizard_app.py -x` | extend |
| LIFE-09 | harness fails on a planted leftover and passes clean (shell harness self-test with a stubbed listing); one Fedora podman run recorded, container removed | script test + container e2e | `uv run pytest tests/test_container_e2e_receipts.py -x`; `make e2e` | extend; recorded run is manual evidence |
| LIFE-10 | fake brew reports `visual-studio-code` greedy-outdated = health OUTDATED (`↑`); `u` runs the greedy upgrade argv; a non-auto-updates cask never gets the flag; Linux unchanged | unit | `uv run pytest tests/test_manager_versions.py tests/test_version_status.py tests/test_update.py -x` | extend |
| UI-04 | toggle absent without `config_paths`; off = config survives; on = exactly the listed paths gone; `--yes` leaves config; failed removal leaves config; shared path deleted once only if both rows toggle; missing path skipped | pilot + unit + CLI | `uv run pytest tests/test_wizard_app.py tests/test_app.py tests/test_uninstall.py -x` | extend |
| Edge: crash backstop | interrupt between `remove` and path deletion leaves the receipt, tool reads broken not removable; interrupt between removal and config deletion leaves config | unit (held-out) | `uv run pytest tests/test_uninstall.py -x` | ❌ Wave 0 |
| Deletions | `test_the_replaced_forks_are_gone`-style test for removed names (`_dnf` sudo argv, native `_REMOVAL_COMMANDS` entries, dead `POST_INSTALL_ACTIONS`, `Tool.source/owner/uninstall`) | grep | `uv run pytest tests/test_screen_family.py::test_the_replaced_forks_are_gone -x` | extend |

### Sampling Rate
- **Per task commit:** the targeted module(s) above with `-x`
- **Per wave merge:** `make validate && make test`
- **Phase gate:** full suite green, plus one recorded `make e2e` Fedora run, before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Script-kind receipt fixtures (type-only dir/link/file, vendor-update drift case) in `tests/test_receipts.py`
- [ ] `tests/test_uninstall.py` crash-backstop and ordering fixtures (fake runner recording `remove` before deletes)
- [ ] A fake brew JSON fixture with `auto_updates` casks (macOS-shaped)
- [ ] Parametrized `Disposition` exhaustiveness test (Pitfall 10)
- [ ] E2E harness self-test seam (a stubbed listing function so the planted-leftover test runs without podman)
- [ ] Rewrite `tests/test_engine.py` sudo cases to MANUAL assertions

## Security Domain

`security_enforcement` is not disabled in config, so this applies.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2/V3 Authentication, Session | no | -- |
| V4 Access Control | yes | Zero sudo/pkexec/doas by construction; grep test; `HOMEBREW_NO_SUDO=1` |
| V5 Input Validation | yes | Registry keys are a closed set; named roots only; unknown placeholder rejected at load; `config_paths` denylist; no `sh -c` for `{omz_root}` |
| V6 Cryptography | no | Existing sha256 in receipts is unchanged |
| V12 Files | yes | Deletion only of receipt-proven paths, re-proven at delete time; quarantine rename for trees; config deletion only via the user toggle, never from the CLI, never under harness dirs |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Planted/foreign file at a declared script path | Tampering | Type-only receipt proof plus symlink checks; foreign file survives and is listed "remove it yourself" |
| Tampered receipt widens deletion | Tampering | Receipt is evidence only; intersect with registry `artifact_paths` (19 pattern); fail closed on unknown types |
| Registry edit introduces arbitrary command | Elevation | `remove`/`update` are literal argv, never a shell string; closed `{root}` set; only `sdk` gets the fixed sourced pipeline |
| Config deletion under shared harness dir | Tampering/Info loss | Load-time rejection by the single denylist constant |
| Vendor installer escalates (brew) | Elevation | Plan-time `writable_prefix` preflight plus engine re-check plus `HOMEBREW_NO_SUDO=1` |
| Path traversal in `~`/root expansion | Tampering | Expand then require absolute, no `..`, depth >= 2 for config; reject at load |

## Sources

### Primary (HIGH confidence)
- Codebase read this session: `installer/uninstall.py`, `app.py` (`run_uninstall`, `perform_uninstall`, `UninstallDecision`), `engine.py`, `executors.py`, `update.py`, `session.py`, `receipts.py`, `download.py` (`artifact_paths`), `ownership.py:1470-1657`, `omz.py:530-548`, `model.py` (`METHOD_PARAMS`), `version_status.py`, `wizard_app.py` (`UninstallScreen`, `ConfirmUninstall`), `manager_versions.py`, `pnpm_globals.py`, `scripts/container-e2e-verify.sh`, `registry.toml` (parsed with `tomllib`), `.claude/architecture.md` (Phases 19-21)
- Local read-only runs: `opencode uninstall --help/--dry-run`, `codex --help`, `cursor-agent --help`, `claude --help`, `uv self --help`, `pnpm self-update`, `bun upgrade --help`, `volta --help`, `fnm --help`, `brew outdated/upgrade/info --help`, `brew info --cask --installed --json=v2`, `sdk help`
- Vendor install scripts fetched by curl: opencode, claude, cursor, antigravity, codex; ohmyzsh `tools/upgrade.sh`

### Secondary (MEDIUM confidence, official docs via fetch)
- code.claude.com/docs/en/setup (native uninstall paths, `claude update`, auto-update)
- docs.astral.sh/uv/getting-started/installation (uninstall, self update)
- sdkman.io/install (uninstall), sw.kovidgoyal.net/kitty/binary (uninstall/update)
- github.com/Homebrew/install (uninstall script, `HOMEBREW_NO_SUDO`), opencode.ai/docs/cli (uninstall flags)

### Tertiary (LOW confidence)
- Training knowledge for bun/pnpm/volta/fnm/antigravity layouts, `brew update` semantics, OMZ uninstall side effects (tagged [ASSUMED] above)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, nothing new
- Architecture/seams: HIGH, read directly; the one structural gap (`removal_plan` shape) is explicit
- Vendor data: MEDIUM, 7 of 14 verified; the rest need the per-tool task
- Pitfalls: HIGH for 1-6, 8-11 (each tied to read code or a local run); MEDIUM for 7

**Research date:** 2026-11-03
**Valid until:** 2026-11-17 (vendor installers and CLIs change fast; re-verify before registry edits)
