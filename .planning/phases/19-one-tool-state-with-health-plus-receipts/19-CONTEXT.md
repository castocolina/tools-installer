# Phase 19: One tool state with health plus receipts - Context

**Gathered:** 2026-10-14 (assumptions mode, `--analyze --all --batch`, jev screening, best-over-easy)
**Status:** Ready for planning

<domain>
## Phase Boundary

Every catalog view reads one `ToolState` per tool: present, health, owner, version and removability with proof. Install, update and repair each leave an atomic receipt, and that receipt is the proof used for removal.

The WHAT is locked in `19-SPEC.md` (R1–R10). R5 was amended in this session: adoption compares against the cached release digest, not a "registry pinned checksum", which does not exist. This file locks the HOW.

Out of scope:
- Dispositions and the install plan (20).
- The Uninstall screen redesign, Policies and the Doctor lifecycle (21).
- Script `paths`/`remove`/`update` and level-3 recipes (22).
- Hook receipts and hook-based misconfiguration (23).

**Prerequisite:** Phase 17 must be executed first: the archive-layout removal predicate (17 D-04), `atomic_write_text` (17 D-05) and `replace_symlink` on the install path (17 D-01). As of 2026-10-14, 17 and 18 have context only; their code has not landed. The receipt's `smoke` field and the release digests depend on Phase 18 (D-06, D-05). Until 18 lands, `smoke` is `null` and adoption finds no digest, so tools stay unproven. That fails closed.
</domain>

<decisions>
## Implementation Decisions

**Decision rule (user, 2026-10-13):** choose the best design, not the easiest. The analyzer's "easy" alternatives were rejected wherever they left a second source of truth, a race, a duplicated probe or a false `✓`.

### State and one-swap publication (R1, R2)
- **D-01:** `Health` (StrEnum; declaration order is the precedence), `ToolState` (frozen dataclass) and the pure `tool_health(ev) -> (Health, reasons)` live in `installer/version_status.py`, as described in target-architecture §1–§2.
  - `Evidence` is a local dataclass built in the refresh loop and never stored.
- **D-02:** `VersionRefreshService.refresh` (`version_status.py:677-771`) builds one `dict[str, ToolState]` and publishes it with one assignment under `self._lock`.
  - A pass whose `started_epoch != self._epoch` publishes **nothing**. This deletes the raced `self._statuses.update` at `:751`, which still merges today (see the comment at `:727-751`), and the separate `:761`/`:768` updates.
  - Saving the cache happens after the swap and is best-effort: a failure produces a warning.
- **D-03:** `state_of(id) -> ToolState | None` replaces `statuses` (`:503`), `ownership_of` (`:510-529`) and `skill_status_of` (`:531`).
  - It follows `ownership_of`'s existing fail-closed read order, and returns `None` when the map's generation is not the current one; readers render `None` as `…`.
  - The barrier test drives two overlapping passes deterministically.
- **D-04 (best, not easy):** Delete `set_installed`, the per-tier `_installed`/`_version_statuses` copies and `_BROKEN_MARK` (`catalog_tui.py:227-228, 339, 349, 383-402, 479-517`).
  - Every tier renders from `state_of`. There is no forwarding shim; there is one caller.
  - `deps.py:111` and `engine.py:132` take a presence predicate fed by `state_of`.

### Receipts (R4, R5)
- **D-05:** `installer/receipts.py` is the only new module. It provides `read`, `write` and `matches`.
  - The path is `~/.local/state/tools-installer/receipts/<id>.json`. The schema has `"v": 1`; an unknown `v`, malformed JSON or an unreadable file means no proof, never a crash.
  - Writes use `atomic_write_text`.
  - Fields follow target-architecture §5: `tool`, `at`, `method{kind,key}`, `package`, `artifacts[]`, `smoke` and `hooks`. `hooks` stays empty until Phase 23.
- **D-06:** The single write point is `engine.install_tool`, after the method succeeds and the handoff early-return (`engine.py:155-161`), and before `run_postinstall` (`:168`).
  - A crash before the write leaves the tool present but unproven (SPEC AC9).
  - A failed update raises before this point, so the old receipt is kept.
  - Native, skill and `host_setup` tools write none.
- **D-07 (best, not easy):** One `download.artifact_paths(method)` is the only formula for "what this method creates" (opt dir, link, raw file, app bundle, cli link; `bin_name` honored).
  - `install_download`/`install_app` place files at those paths.
  - The receipt writer stats them after success.
  - `plan_uninstall` (`uninstall.py:56-97`) becomes a call to it.
  - Executors do not return their own path lists: that would leave removal computing paths separately again, which is the F7 drift. jev: TypeSafe 0.87.
- **D-08 (user):** Drift is checked with a stat fingerprint.
  - File artifacts record `sha256`, `size` and `mtime_ns`. Link artifacts record `target`. Dir artifacts record only the type.
  - Each pass runs `readlink` on links, `is_dir`/not-symlink on dirs, and `stat` on files.
  - A file is re-hashed only when its size or mtime differs. A confirmed change or a missing artifact makes the tool BROKEN and not removable, with the reason "changed since install".
  - Removal re-verifies the sha256 right before deleting.
  - This rejects existence-only checks (a file overwritten in place would show a false `✓` until removal) and hashing every pass (AppImages are about 150 MB, on the single worker). jev: TypeSafe 0.93.
- **D-09 (user; SPEC R5 amended):** Adoption by checksum compares against the cached release digest.
  - With 18 D-05, `resolve_github_release` returns asset digests from the same capped `/releases/latest` fetch the pass already makes (`MAX_FETCHES_PER_REFRESH`), and the version cache stores them next to `latest_version`. No new network call.
  - A present raw-binary tool with no receipt (yq, direnv, shfmt, fx, dasel, tealdeer, the WezTerm and draw.io AppImages) is adopted when the sha256 of its file equals the cached digest of its rendered asset. Adoption writes a receipt during the pass and adds a reason.
  - To avoid re-hashing every pass, a non-match is remembered by `(path, size, mtime_ns)` for the session.
  - Archive kinds are adopted by the 17 D-04 layout proof, because an archive's checksum never equals the extracted binary.
  - Everything else shows "reinstall with r to adopt". jev: TypeSafe 0.99.

### Removal proof (R6)
- **D-10:** `removal_plan(tool, state) -> RemovalPlan` (target-architecture §4.3) is computed in the pass, stored in `ToolState.removable`, and is the only gate.
  - The CLI `--yes` path (`app.py:548` inside `run_uninstall`, reached from `setup.py:1364`) and the TUI (`classify_tools` via `setup.py:860`) both read it.
  - Proof comes only from a receipt match, adoption, or the 17 D-04 layout proof.
  - `artifact_paths` is evidence, never authority.
  - Unproven tools are listed as "remove it yourself" in both paths. `--yes` never removes from evidence alone.

### Owners and live managers (R7, R8)
- **D-11 (best, not easy):** The native probe is **one batched call per OS family per pass**.
  - First, collect every path that still needs a native answer after the tracked/brew/pnpm/uv checks.
  - Then issue a single `rpm -qf`, `dpkg -S` or `pacman -Qo` call with an output format that names each path, so an unowned path cannot shift the positional output.
  - Finish attribution with dict lookups.
  - A per-path memo was rejected: it still makes N calls for N distinct paths, which fails SPEC AC "one `rpm -qf` per pass". jev: Laya 0.78, TypeSafe 0.99.
- **D-12:** The uv owner dir comes from `uv tool dir --bin`, run once per pass and only when uv is present. *(Superseded in part by Ledger L-19-01: use `uv tool dir`, not `--bin`.)*
  - This replaces the `UV_TOOL_BIN_DIR`-or-`~/.local/bin` guess (`ownership.py:456-457`). That guess collides with `managed_bin_dir` (`:445`), so graphify comes out unknown today.
- **D-13:** Volta, including pnpm reached through Volta, resolves to `volta`.
  - Redirect shims are followed to the real owner.
  - The implicit `~/.local/bin/<bin>` counts as presence for download kinds (`status.py:40-52`).
  - `host_setup` keeps its owner probe and probes the unresolved `which` path.
- **D-14:** At the top of each pass, `platform = replace(platform, has_brew=which("brew") is not None)`.
  - `service.platform` exposes the refreshed value, and **every** consumer reads it: `resolve.py:67,70,137,195`, `ownership.py:163,248,268` and `version_status.py:606,611,663`. Otherwise the ladder would still hide brew methods.

### Marks, legend and misconfiguration (R3, R9, R10)
- **D-15:** One `health_cell(state)` and one legend serve the system, user and ai tiers.
  - The legend **replaces** today's per-version dim labels. Shadowed, off-policy, unknown owner and unreadable version become reasons.
  - It stays within the 78×3 budget pinned by `tests/test_catalog_tui.py:1878-1899`.
  - The focused row shows `reasons` and `unconfigured`.
- **D-16 (best, not easy):** Terminal drift calls `sync_terminal_shells(write=False)`.
  - A `write` flag is threaded to the kitty/WezTerm `_write_if_changed` calls and the Konsole helper, around the existing pure `_replace_owned_region` (`terminal_shell.py:72-108`), so the dry run and the real sync are the same code. There is no separate drift checker.
  - The planner must confirm the Konsole helper has no I/O before its write.
- **D-17:** A skill pack's `≈` comes from joining the existing per-harness probe outputs (`inspect_skill_packs`, `skill_lifecycle.py:413-426`, one call per harness) with `present_harnesses` (computed once per pass).
  - A pack absent on a present harness gets the reason "partial: missing on <harness>".
  - A pack for an absent harness gives no `≈`.
- **D-18 (user):** For Claude plugins, **the user (global) scope install is the one that counts** (user: "prefer user global for superpowers").
  - `_claude_matches` (`skill_lifecycle.py:34-42`) parses the scope and status from the existing `claude plugin list` output.
  - An enabled user-scope entry means present.
  - Project-scope copies, other marketplaces, other versions and disabled entries do not make the pack present. Each becomes a "duplicate" or "disabled" reason that names the marketplace, scope and version.
  - The live evidence is superpowers installed 4 times (2 marketplaces × 2 scopes, versions 6.4.1 and 6.2.0; F-registry-ai.md:40,138).
  - **Fix step (added 2026-10-14, user: "agrégalo a las phases"):** the duplicate and disabled reasons each carry a D-20 `ConfigStep`, so 20 D-06 RECONFIGURE repairs them. Detection alone is not enough.
    - **Order matters (measured on the host on 2026-10-14):** the user-scope copy was `✘ disabled` and only worked through the project copies. Removing the copies first would leave no working plugin.
    - Step 1: `claude plugin enable -s user <canonical>`, if it is disabled.
    - Step 2: `claude plugin uninstall -s <scope> <id>` for each non-canonical copy. Project scope runs with `cwd=<projectPath>` from `installed_plugins.json`.
    - Step 3: `claude plugin marketplace remove <m>` only when nothing else is installed from that marketplace.
    - Then re-probe. The row is ✓ only if exactly one enabled user-scope entry remains.
    - If the canonical copy is missing entirely, the step is "install user-scope canonical", and copies are removed only after it succeeds.
    - **Host state:** cleaned by hand on 2026-10-14, leaving the official user scope at 6.4.1, enabled. The fixture for this step reproduces the 4-install state from `installed_plugins.json` and `claude plugin list` text, not from the live host.
- **D-19:** A pnpm co-install group that is incomplete produces `≈`, from the pnpm inventory the pass already caches.
- **D-20 (added by Phase 20 D-06, 2026-10-14):** `ToolState.unconfigured` is a tuple of typed `ConfigStep`s rather than plain strings. Each step has the text shown to the user and a fix: skill install for a harness (D-17/D-18), plugin dedupe/enable for a harness (D-18 fix step), terminal sync (D-16), or install of the missing pnpm group members (D-19). Phase 20's RECONFIGURE runs exactly those steps.
- **D-21 (user rule 2026-10-14; folds todo `2026-10-13-gsd-per-repo-local-installs`):** Every `skill_pack` has a closed `scope` param: `"user"` or `"project"`.
  - `"user"` is the default and covers small, targeted packs: superpowers, ponytail and the like.
  - `"project"` is for framework packs whose machinery (hooks, agents, commands, skills) must never be installed into a harness's global dir. That means `opengsd`.
  - The package or CLI itself may still be global; this rule covers only the files a pack writes into harnesses.
  - **Detection for `project` packs:**
    - Global machinery in a harness home (`~/.claude/gsd-core`, `gsd-*` in `~/.claude/{skills,agents,commands,hooks}`, GSD hooks in `~/.claude/settings.json`, and the same set for `~/.config/opencode`, `~/.codex`, …) gives `≈` with the reason "installed globally; this pack is project-local". Its D-20 fix step is the pack's own global uninstall (`pnpm dlx @opengsd/gsd-core@<pin> --<runtime> --global --uninstall`). The installer never deletes those files itself.
    - Presence means "installed in N repos". The repos are found by walking known roots for `.planning/config.json`.
    - A repo counts as installed per runtime only when `<repo>/<runtime dir>/gsd-core/VERSION` (or the manifest) exists **and** the runtime's skills or commands dir is non-empty.
    - **Real failure case, 2026-10-14:** `.opencode/gsd-install-state.json` existed while `.opencode/{skills,commands,agents}` were empty. The current probe only checks `$HOME/<runtime>/gsd-install-state.json`, so it reported a false "present".
  - **Install and update for `project` packs:** an explicit per-repo action that runs the official installer (`--<runtime> --local --relative-includes`, pinned version) in each listed repo where `.planning/` exists. It never copies files, and it never runs `--global`.
  - **Host state on 2026-10-14:**
    - Global Claude GSD was removed by the ai-kit session's migration.
    - This repo has local GSD for claude and opencode (opencode reinstalled locally by hand: 72 skills, 72 commands, 64 agents).
    - The fixtures reproduce both the empty-dirs false positive and the global-leftover case.

### Claude's Discretion
- Plan and wave order. Suggested:
  1. `Health`/`ToolState`/`tool_health` and the one-swap publication with `state_of`.
  2. `artifact_paths`, `receipts.py` and the engine write point.
  3. `removal_plan` wired into the CLI and the TUI.
  4. The owner fixes and the `has_brew` re-read.
  5. `health_cell`, the legend and the misconfiguration signals.
- The exact `rpm`/`dpkg`/`pacman` output formats for D-11, and the names of the `Evidence` fields.

### Folded Todos
None.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/19-one-tool-state-with-health-plus-receipts/19-SPEC.md`: locked R1–R10 (R5 amended 2026-10-14)
- `.planning/research/2026-10-13-target-architecture.md`: §1 Health, §1.1 probe costs, §2 ToolState and the publication rule, §4.3 RemovalPlan, §5 receipt format, §9.2 (O2, O3, O9, O10)
- `.planning/phases/17-stop-the-bleeding/17-CONTEXT.md`: D-01 `replace_symlink`, D-04 archive-layout proof, D-05 atomic writes, D-08 Summary
- `.planning/phases/18-registry-truth-and-drift-guard/18-CONTEXT.md`: D-05 `Release` record with digests, D-06 smoke before the link swap
- `.planning/research/audit-2026-10-13/F-registry-ai.md`: X4 (uv owner), X7 (skill partial/duplicate), live superpowers duplicates at :40 and :138
- `.planning/research/audit-2026-10-13/SYNTHESIS-AND-PLAN.md`: row 3
- `.planning/REQUIREMENTS.md`: STATE-01..07
- `.claude/architecture.md`, `AGENTS.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `version_status.VersionRefreshService` (`:423`): epoch, `_lock`, the fail-closed read in `ownership_of`, `MAX_FETCHES_PER_REFRESH`
- `atomic.atomic_write_text` (`:56`), `replace_symlink`; `checksums.sha256_file` (`:55-58`)
- `uninstall.plan_uninstall` (`:56-97`), whose path logic moves into `download.artifact_paths`
- `skill_lifecycle.inspect_skill_packs` (`:413-426`), `_skills_lock_status` (`:351-361`), `_claude_matches` (`:34-42`)
- `terminal_shell._replace_owned_region` (`:72-108`, pure)
- `install_ownership._rpm_owner`/`_dpkg_owner`/`_pacman_owner` (`:260-275`), which are replaced by the batched probe

### Established Patterns
- Frozen dataclasses with closed `Literal`/`StrEnum` sets; error messages in the form `f"tool '{id}': ..."`.
- Fail-closed readers: an unknown or failed result is never shown as present or ok.
- The refresh runs on one worker thread and adds no new network calls (SPEC constraint).

### Integration Points
- `engine.install_tool` → `receipts.write` (after success, before postinstall)
- `VersionRefreshService.refresh` → `ToolState` map → `state_of` ← every catalog tier, `deps.py:111`, `engine.py:132`, the uninstall paths
- `removal_plan` ← `app.run_uninstall` (`--yes`) and `classify_tools` (TUI)
- The version cache ← `Release.digests` (18 D-05) → D-09 adoption
- `Platform.has_brew` refresh → `resolve.py` method gating
</code_context>

<specifics>
## Specific Ideas

- The acceptance anchor for D-18 is the live host state: superpowers installed 4 times in Claude (`@claude-plugins-official` user 6.4.1 and project 6.2.0, plus `@superpowers-marketplace` user and project 6.2.0).
- The acceptance anchor for D-12 is graphify installed with uv resolving to owner uv.
</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `detect-dangling-pnpm-global-bin-shims-in-doctor` (score 0.6): Phase 21 (UI-07).
- `gsd-per-repo-local-installs` (score 0.6): tooling outside this phase's scope.
- `repair-pi-install-and-sync-models` (score 0.6): host repair, not catalog state. It is a candidate for a later registry phase.
</deferred>

### Ledger amendments (planning, 2026-10-16; RUN-LEDGER)
- **Ledger L-19-01 (D-12, verifiable):** graphify's owner resolves through `uv tool dir` (the tools dir); `uv tool dir --bin` returns `~/.local/bin` and resolves no owner.
- **Ledger L-19-02 (D-02, verifiable):** dropping an overtaken refresh needs a monotonic pass counter in addition to the epoch; an older pass that finishes later at the same epoch must publish nothing (SPEC AC1).
- **Ledger L-19-03 (D-06, verifiable):** updates do not go through `engine.install_tool` (`update.py`); one receipt writer is called from both the install and the update paths.
- **Ledger L-19-04 (D-07, verifiable):** `download.artifact_paths` cannot import `apps.cli_spec` (apps imports download); `cli_spec` moves into `download.py`.
- **Ledger L-19-05 (D-16, verifiable):** the dry-run flag must block both the Konsole helper's state-file write and the `.zshrc` rewrite in the terminal sync.
- **Ledger L-19-06 (D-10, verifiable):** the CLI `--yes` path never refreshes, so the real removal gate is the shared receipt-aware `plan_removal`; removal deletes only paths present both in the receipt and in `artifact_paths`.
- **Ledger L-19-07 (D-21, jev):** Phase 19 adds the closed `scope` (and pin) to `[tool.skill_lifecycle]`, detects project-scope installs and builds + tests the exact per-repo install command (shown as the row's configuration step); Phase 20's plan/reconfigure executes it (Laya low conf -> TypeSafe build_in_19_run_in_20 p=0.99).
- **Ledger L-19-08 (host fact):** global Claude GSD exists again on this host (`~/.claude/gsd-core` 1.16.0), so it shows as "installed globally" (≈).
- **Ledger L-19-09 (D-18, verifiable):** parse `claude plugin list --json` (scope, enabled, version) instead of the text output.
- **Ledger L-19-10 (R9, verifiable):** the catalog has no `konsole` row; Konsole shell drift attaches to the `zsh` row.
- **Ledger L-19-11:** CONTEXT line references have drifted since Phases 17/18; plans cite current lines (19-RESEARCH), no decision changes.
- **Ledger L-19-12 (D-02, planner):** the snapshot merge is per-record newest-wins; an overtaken full pass publishes nothing, an older full pass may still fill records a newer partial pass did not cover.
- **Ledger L-19-13 (D-05, planner):** `ConfigStep` lives in `installer/model.py`; `version_status.py` would create an import cycle and D-05 forbids new modules.
- **Ledger L-19-14 (D-08/D-10, planner):** a corrupt receipt leaves the tool unproven (no layout fallback); a valid receipt beats layout proof; one changed artifact makes the whole tool non-removable.
- **Ledger L-19-15 (D-18/D-21, host check):** `claude plugin install -s user <id>` is valid (`-s, --scope user|project|local`); `projectPath` on project-scope records is unverified on this host, so without it the duplicate reason shows with no fix step.
- **Ledger L-19-16 (planner):** context-budget splits 19-13 -> 19-20 and 19-11 -> 19-21; 21 plans in 8 waves.
- **Ledger L-19-17 (D-21, verifiable):** detection surfaces follow the GSD 1.16.0 capability registry across all 9 harness homes (machinery dirs; hooks in settings.json / hooks.json / legacy config.toml / kimi hook block; copilot, kilo, opencode have no hooks); the repo walk covers claude and opencode project dirs only.
- **Ledger L-19-18 (D-18):** an absent pack keeps its configuration facts as notes, so a 4-install superpowers reads MISSING with the D-18 reasons and steps.
- **Ledger L-19-19 (D-02):** one refresh pass at a time; a request joins an in-flight pass with the same ids and epoch and never crosses an invalidate.
- **Ledger L-19-20 (D-14):** `UpdateService` takes a `live_platform` callable.
- **Ledger L-19-21:** `default_skill_home()` is sandboxed in every test by conftest.
- **Ledger L-19-22:** `model.TOOL_ID_RE` is enforced at registry load and reused for receipt file names; declared-package probes are memoized per pass; the opengsd handoff text pins `pnpm dlx @opengsd/gsd-core@1.16.0 --<runtime> --local`.
- **Ledger L-19-23 (D-18):** for an absent pack the demoted configuration facts come first in the notes; skill packs get no owner or version notes.
- **Ledger L-19-24:** `is_installed(..., default_bin_dir=)` is fed from the service's managed bin dir; an autouse `sandboxed_bin_dir` fixture (19-01) keeps tests off the real `~/.local/bin`.
- **Ledger L-19-25 (D-02):** pass order is the public `ToolState.seq` field, used by the merge rule.
- **Ledger L-19-27 (review cycle 1, 4c80be7):** all 12 HIGH + 15 MEDIUM incorporated, none rejected; threat IDs T-19-69..76. M14 tightens D-21's "non-empty" rule to "has a `gsd-*` entry" (still implies non-empty). M3/M4: any invalid Claude plugin entry (incl. an unknown scope) makes the whole listing unknown. M15: a symlinked configured repo root is skipped (symlinks are never followed).
- **Ledger L-19-28 (D-20, H10):** the pnpm group repair step `pnpm_group_install` has an empty argv; it re-runs the declaring tool's node method (whole pinned group, `--allow-build`) through `executors.execute`. Phase 20 must dispatch this step kind to the node executor.
- **Ledger L-19-29 (UI-SPEC sync):** four new reason/note strings added to the 19-UI-SPEC copy table (needs Homebrew; terminal / pnpm / skill "not checked").
- **Ledger L-19-30 (review cycle 2, cefe8a9):** `_build_receipt` is the single receipt constructor and never fingerprints; `record` fingerprints then builds, `adopt` builds from its one under-lock fingerprint (adopted receipts carry `smoke = null`). A receipt removed after a failed rewrite is a plain no-receipt case (archive layout re-proves, raw stays unproven). An `unknown` skill host is inconclusive and yields a "not checked" note only for harnesses present with a fresh report; a missing hook config means no registration. `unresolved=` is forwarded through `resolve_status` / `resolve_github_release_status` / `_probed_version`. Threat IDs T-19-77..80.

