# Phase 19: One tool state with health plus receipts - Research

**Researched:** 2026-10-16
**Domain:** In-process state publication (one frozen map per generation), install receipts as removal proof, ownership attribution, Textual catalog rendering
**Confidence:** HIGH for the code seams (every claim read at HEAD `fde3e68`; `git diff --stat 424b301 HEAD -- installer setup.py tests` is empty, so the code baseline equals the UI-SPEC's `424b301`). MEDIUM for D-21 project-pack detection details (roots, runtime dirs) and the Claude JSON shape for project-scope entries.

## Summary

Phase 19 adds no dependency and only one module (`installer/receipts.py`). Nearly everything else is a reshaping of existing seams. `VersionRefreshService.refresh` (`installer/version_status.py:690-784`) already walks every tool with ownership, version and inventory in hand. It becomes the one producer of a frozen `dict[str, ToolState]`, published in one assignment under `self._lock`. Every catalog tier, the Execute screen, the setup.py uninstall closures and the update action read `state_of(id)`. They no longer read the three maps `statuses` / `ownership_of` / `skill_status_of` or the per-tier `_installed` copies.

The receipt work rests on primitives Phases 17 and 18 shipped, all verified present: `atomic.atomic_write_text` (`atomic.py:56`), `download.is_still_proven` (`download.py:188-204`), the interim `RemovalPlan(removable, yourself)` (`uninstall.py:113-125`), `checksums.sha256_file` (`checksums.py:55-58`), `executors.smoke_binary`, and release digests in the version cache (`VersionCacheEntry.digests`, `version_cache.py:55-59`). The CONTEXT prerequisite paragraph ("17 and 18 have context only") is stale. Both phases have landed.

Research found seven places where a locked decision's stated mechanism does not hold against the code or the host. They are listed as **Ledger candidates** (end of this file), each with evidence. The decisions are not changed here. The most consequential:

1. `uv tool dir --bin` returns `~/.local/bin`, so D-12 as written does not fix graphify. Attribution needs `uv tool dir`.
2. D-02's epoch-only check does not discard an older pass that overlaps at the same epoch, which SPEC AC1 requires.
3. Updates never pass through `engine.install_tool`, so D-06's "single write point" cannot cover "update writes the receipt".
4. `download.artifact_paths` cannot import `apps.cli_spec` without an import cycle.

**Primary recommendation:**
- Build in this order: (1) the pure core (`Health`, `Evidence`, `tool_health`, `receipts.py`, `artifact_paths`, the batched native index), then (2) the one-swap service with a pass sequence and full-catalog passes, then (3) the write points and proof-driven removal, then (4) the misconfiguration signals, and last (5) the UI swap to `health_cell`, following `19-UI-SPEC.md`.
- The safety gate for all destructive behavior is one pure, receipt-aware `plan_removal`. Deletion is re-proven at deletion time, and only `receipt ∩ artifact_paths` is ever deleted.

## Project Constraints (from CLAUDE.md / AGENTS.md)

`./CLAUDE.md` is the configured `claude_md_path`. The repo's instructions live in `AGENTS.md` and `.claude/*.md`.

| Directive | Source | Phase 19 impact |
|---|---|---|
| uv owns the env; never pip/poetry/conda | AGENTS.md | No dependency is added. `pyproject.toml`/`uv.lock` must be unchanged (gate: `git diff --quiet fde3e68 -- pyproject.toml uv.lock`) |
| English only | AGENTS.md | All reasons, copy and identifiers are in English (copy is fixed in 19-UI-SPEC) |
| Never bypass a quality gate (`# noqa`/`# type: ignore`/skip only with a genuine-false-positive comment and approval) | AGENTS.md, python-tooling.md, testing.md | The legend tests locked by 15.1 D-03/D-04 are **replaced** by the D-15 legend. Each removed test must be named as a planned replacement in the plan (Phase 18 precedent: 18-VERIFICATION "Test Integrity") |
| `make validate && make test` green on the committed tree; coverage floor 90 (`pyproject.toml:58` `fail_under = 90`) | AGENTS.md, testing.md | Every new branch ships with a test |
| Never mutate the developer's host; tests use a scratch HOME; real installs only in disposable containers | AGENTS.md | **New risk:** receipts default to `Path.home()/.local/state/tools-installer/receipts`. Today's real-home guard (`tests/conftest.py:19` `_GUARDED_DOTFILES = (".myshellrc", ".shellrc", ".bashrc", ".zshrc", ".profile")`) does not cover that directory. Wave 0 must sandbox it (see Validation Architecture) |
| Zero sudo | AGENTS.md | The batched native probes are read-only `rpm`/`dpkg-query`/`pacman` queries; there is no new privileged path |
| Architecture rule 4: setup.py is wiring only | `.claude/architecture.md:20-22` | `plan_removal`, the native index and the terminal dry run all live in `installer/`; setup.py only binds them |
| Architecture rule 5: no orphan helpers | `.claude/architecture.md:23-25` | Deleting `ownership_of`/`statuses`/`skill_status_of`/`set_installed`/`_BROKEN_MARK` must also delete their tests, not keep them "for later" |
| pyright strict, ruff, bandit, vulture | python-tooling.md | `Health` is a `StrEnum` (precedent `installer/enums.py:3`); all receipt JSON is parsed into typed dataclasses with no `Any` |
| xdist-safe tests, ≤40% threads | testing.md | Barrier tests use `threading.Event`, never sleeps; there are no fixed paths |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Decision rule (user, 2026-10-13):** choose the best design, not the easiest. The analyzer's "easy" alternatives were rejected wherever they left a second source of truth, a race, a duplicated probe or a false `✓`.

#### State and one-swap publication (R1, R2)
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

#### Receipts (R4, R5)
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

#### Removal proof (R6)
- **D-10:** `removal_plan(tool, state) -> RemovalPlan` (target-architecture §4.3) is computed in the pass, stored in `ToolState.removable`, and is the only gate.
  - The CLI `--yes` path (`app.py:548` inside `run_uninstall`, reached from `setup.py:1364`) and the TUI (`classify_tools` via `setup.py:860`) both read it.
  - Proof comes only from a receipt match, adoption, or the 17 D-04 layout proof.
  - `artifact_paths` is evidence, never authority.
  - Unproven tools are listed as "remove it yourself" in both paths. `--yes` never removes from evidence alone.

#### Owners and live managers (R7, R8)
- **D-11 (best, not easy):** The native probe is **one batched call per OS family per pass**.
  - First, collect every path that still needs a native answer after the tracked/brew/pnpm/uv checks.
  - Then issue a single `rpm -qf`, `dpkg -S` or `pacman -Qo` call with an output format that names each path, so an unowned path cannot shift the positional output.
  - Finish attribution with dict lookups.
  - A per-path memo was rejected: it still makes N calls for N distinct paths, which fails SPEC AC "one `rpm -qf` per pass". jev: Laya 0.78, TypeSafe 0.99.
- **D-12:** The uv owner dir comes from `uv tool dir --bin`, run once per pass and only when uv is present.
  - This replaces the `UV_TOOL_BIN_DIR`-or-`~/.local/bin` guess (`ownership.py:456-457`). That guess collides with `managed_bin_dir` (`:445`), so graphify comes out unknown today.
- **D-13:** Volta, including pnpm reached through Volta, resolves to `volta`.
  - Redirect shims are followed to the real owner.
  - The implicit `~/.local/bin/<bin>` counts as presence for download kinds (`status.py:40-52`).
  - `host_setup` keeps its owner probe and probes the unresolved `which` path.
- **D-14:** At the top of each pass, `platform = replace(platform, has_brew=which("brew") is not None)`.
  - `service.platform` exposes the refreshed value, and **every** consumer reads it: `resolve.py:67,70,137,195`, `ownership.py:163,248,268` and `version_status.py:606,611,663`. Otherwise the ladder would still hide brew methods.

#### Marks, legend and misconfiguration (R3, R9, R10)
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

### Deferred Ideas (OUT OF SCOPE)
#### Reviewed Todos (not folded)
- `detect-dangling-pnpm-global-bin-shims-in-doctor` (score 0.6): Phase 21 (UI-07).
- `gsd-per-repo-local-installs` (score 0.6): tooling outside this phase's scope.
- `repair-pi-install-and-sync-models` (score 0.6): host repair, not catalog state. It is a candidate for a later registry phase.

Also out of scope (SPEC Boundaries): dispositions and the install plan (`r`, repair, reconfigure) are Phase 20; the Uninstall screen redesign, Policies and the Doctor lifecycle are Phase 21; script `paths`/`remove`/`update` and level-3 recipes are Phase 22; hook receipts and hook-based misconfiguration are Phase 23; deleting the per-screen workers beyond what one swap needs is Phase 21/25.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATE-01 | Each refresh builds one `ToolState` per tool and publishes it in one swap; a refresh overtaken by a newer one publishes nothing | Pattern 1 (one swap + pass sequence, Ledger L-19-02); Pitfall 1 (tier-subset and single-tool `refresh` callers); the existing barrier-test shape at `tests/test_version_status.py:1130-1185` |
| STATE-02 | Every catalog tier shows one health mark per tool with a legend inside the 78×3 budget | Pattern 2 (`tool_health` precedence table); `19-UI-SPEC.md` owns glyphs, legend text and layout; Pitfall 7 (the 15.1-locked legend tests are planned replacements) |
| STATE-03 | Install, update and repair write an atomic receipt per tool recording artifacts, package and hooks | Pattern 3 (`receipts.py` schema), Pattern 4 (two call sites of one writer, Ledger L-19-03), Pattern 5 (`artifact_paths`, Ledger L-19-04), Pattern 6 (adoption), Pattern 7 (proof-driven removal) |
| STATE-04 | Owner attribution correct for uv tools, Volta, redirect shims, implicit `~/.local/bin`, `host_setup`, native packages (one probe per pass) | Pattern 8 (`uv tool dir`, Ledger L-19-01; Volta owner; shim look-through; implicit bin; host_setup), Pattern 9 (batched native index, verified output formats) |
| STATE-05 | Installing brew in-session makes its methods available without restarting | Pattern 10 (`has_brew` re-read and every consumer, including `ExecuteInputs.platform`) |
| STATE-06 | The focused row shows its health reasons and missing configuration steps | `ToolState.reasons`/`unconfigured`; `19-UI-SPEC.md` "Focused-row detail"; Pattern 11 (`ConfigStep`) |
| STATE-07 | Skill packs show partial or duplicate installs per harness | Pattern 12 (partial via `present_harnesses`; duplicate/disabled via `claude plugin list --json`, Ledger L-19-09); Pattern 13 (D-21 project-scope packs) |
</phase_requirements>

## Architectural Responsibility Map

This is a single-process Python TUI/CLI. The "tiers" below are this codebase's layers, not web tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `Health`, `Evidence`, `tool_health`, `ToolState`, one-swap publication, `state_of` | State service (`installer/version_status.py`) | — | D-01. It is the only module above `ownership`, `status` and `skill_lifecycle` in the import graph (it imports `guards`, `install_ownership`, `ownership`, `skill_lifecycle`, `uninstall`, `version_cache`, `versions`) |
| Receipt read/write/match, stat fingerprint, adoption write | Persistence (`installer/receipts.py`, new) | `installer/atomic.py`, `installer/checksums.py` | D-05. It must import only `atomic`, `checksums`, `download`, `model`, `locations`, so that `engine`, `update`, `uninstall` and `version_status` can all import it without a cycle |
| "What a method creates" (`artifact_paths`) | Executors (`installer/download.py`) | `installer/apps.py` (install), `installer/uninstall.py` (evidence) | D-07. Needs `cli_spec`, which must move into `download.py` (Ledger L-19-04) |
| Receipt write after a successful method | Engine (`engine.install_tool`) + Update (`update._perform`) | `receipts.write` | Two call sites, one writer (Ledger L-19-03) |
| Removal proof | Uninstall (`installer/uninstall.py` `plan_removal`, receipt-aware) | `app.run_uninstall` (CLI), `app.perform_uninstall` (TUI), the pass fills `ToolState.removable` | One pure predicate shared by CLI, TUI and the pass (Ledger L-19-06) |
| Owner attribution fixes | Ownership (`installer/ownership.py`) | `installer/install_ownership.py` (batched native index), `installer/guards.py` (shim look-through) | Existing division; no new module |
| Terminal drift (dry run) | `installer/terminal_shell.py` | the pass, through an injected seam | D-16. The same code path as the real sync |
| Skill partial/duplicate | `installer/skill_lifecycle.py` | the pass joins it with `present_harnesses` | D-17/D-18 |
| Marks, legend, focused-row detail, grouping | TUI (`installer/catalog_tui.py`, `installer/tool_browser.py`, `installer/ui_common.py`) | — | `19-UI-SPEC.md` is the contract |
| Composition (binding the real `which`, PATH, `uv tool dir`, terminal lookup, receipts dir) | `setup.py` (wiring only) | — | Architecture rule 4 |

## Standard Stack

### Core (all already installed; nothing new)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `json`, `hashlib.file_digest`, `os.readlink`/`stat`, `threading`, `dataclasses`, `enum.StrEnum` | CPython 3.12.12 in the venv; `requires-python = ">=3.11"` | Receipt JSON, sha256, stat fingerprint, lock and sequence, frozen state, closed Health set | `[VERIFIED: uv run python --version]`, `[VERIFIED: pyproject.toml:5]`. `StrEnum` precedent at `installer/enums.py:3` |
| textual | 8.2.7 | TUI (already used) | `[VERIFIED: importlib.metadata]` |
| rich | 15.0.0 | `Text`, `cell_len` for the legend budget | `[VERIFIED: importlib.metadata]` |
| pytest | 9.0.3 (+ xdist, cov, asyncio) | Tests | `[VERIFIED: importlib.metadata]` |

### Host tools used read-only by the pass (not Python packages)

| Tool | Version seen | Used for |
|---|---|---|
| `rpm` | RPM 6.0.2 (host) | batched `rpm -qf` (D-11) |
| `dpkg-query` | Debian 13 container | batched `-S` |
| `pacman` | archlinux:latest container | batched `-Qo` |
| `uv` | 0.11.28 | `uv tool dir` (D-12) |
| `claude` | 2.1.301 | `claude plugin list --json` (D-18) |

**Installation:** none. No `pip`/`uv add`.

## Package Legitimacy Audit

This phase installs no external packages. `slopcheck`/`package-legitimacy` is not applicable.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
  view entry / install close / u / uninstall removal
                │
                ▼
  CatalogScreen worker ──refresh(full catalog)──► VersionRefreshService.refresh  (worker thread)
                                                     │ 1. started_epoch, started_seq = next(seq)
                                                     │ 2. platform = replace(platform, has_brew=which("brew"))
                                                     │ 3. manager snapshot (cached 6 h) + `uv tool dir` (once)
                                                     │ 4. per tool: presence, look-through which, ownership
                                                     │      (tracked/brew/pnpm/uv/volta) ──► collect paths
                                                     │      that still need a native answer
                                                     │ 5. ONE batched rpm -qf | dpkg-query -S | pacman -Qo
                                                     │      + rpm-ostree status (once) ──► dict lookups
                                                     │ 6. per tool: version (cache/digests), receipt read
                                                     │      + stat fingerprint, adoption (sha256 vs digest),
                                                     │      plan_removal, misconfig signals
                                                     │      (terminal dry run once, pnpm groups, skills ∩
                                                     │      present_harnesses) ──► Evidence ──► tool_health
                                                     │ 7. under _lock: epoch == started_epoch and
                                                     │      seq > published_seq ? self._state = frozen map
                                                     │      : publish nothing
                                                     │ 8. best-effort cache save (a failure is a warning)
                                                     ▼
  state_of(id) ◄── health_cell / Ver / Owner / detail (3 tiers) · ExecuteScreen · setup.py uninstall closures · u
                                                     ▲
  refresh_skills (own cadence; `codex plugin list` measured 23 s) ──► under _lock: rebuild ONLY skill rows
                                                                     in the same-generation map (one assignment)

  install_tool / update._perform ──method ok──► receipts.write (atomic) ──► postinstall
  CLI --yes / TUI Uninstall ──► plan_removal (receipt ∩ artifact_paths, or layout proof) ──► confirm
                                    ──► re-prove at deletion (sha256 / readlink) ──► delete ──► delete receipt
```

### Recommended Project Structure (delta only)

```
installer/
├── receipts.py          # NEW: Receipt/Artifact dataclasses, read, write, matches, adopt, receipts_dir()
├── version_status.py    # + Health, Evidence, tool_health, ToolState, ConfigStep, state_of, pass seq
├── download.py          # + artifact_paths(method, bin_dir) ; cli_spec moved here from apps.py
├── install_ownership.py # + NativeIndex: one batched path query per OS family + rpm-ostree once
├── ownership.py         # + "volta" Owner, uv owner dir from `uv tool dir`, NativeIndex consumer
├── uninstall.py         # plan_removal becomes receipt-aware (same RemovalPlan dataclass)
├── terminal_shell.py    # + write flag; TerminalShellResult.drifted
├── skill_lifecycle.py   # + claude JSON entries (scope/enabled/version), project-pack detection
├── catalog_tui.py       # health_cell, legend, detail; deletes _installed/_BROKEN_MARK/set_installed
tests/
├── test_receipts.py     # NEW
└── conftest.py          # + autouse receipts sandbox; real-home fingerprint covers receipts/
```

### Pattern 1: One swap per pass, discarded when overtaken (STATE-01)

**What:** A frozen map of `ToolState` tagged with the generation (epoch) of the pass that produced it. The commit rule needs **two** guards. The first is the epoch (a mutation happened). The second is a monotonic pass sequence (a newer pass started later). See Ledger L-19-02.

```python
# Source: shape derived from version_status.py:690-784 and the existing raced-pass test
# (tests/test_version_status.py:1130-1185). Names are illustrative.
def refresh(self, tools: Sequence[Tool]) -> None:
    with self._lock:
        self._seq += 1
        started_seq, started_epoch = self._seq, self._epoch
        self._platform = replace(self._platform, has_brew=self._which("brew") is not None)
    ... build states: dict[str, ToolState] ...
    with self._lock:
        if self._epoch != started_epoch or started_seq < self._published_seq:
            return                                   # overtaken: publish NOTHING
        self._state = _GenerationMap(started_epoch, MappingProxyType(states))   # ONE assignment
        self._published_seq = started_seq
    try: save_version_cache(...)                      # best-effort, AFTER the swap (D-02)
    except OSError as exc: self._last_warning = f"version cache not saved: {exc}"

def state_of(self, tool_id: str) -> ToolState | None:
    snapshot = self._state                            # ONE read: map and its generation together
    if snapshot is None or snapshot.generation != self._epoch:
        return None                                   # renders as "…"
    return snapshot.states.get(tool_id)
```

- Read order matters (keep `ownership_of`'s documented rule, `version_status.py:523-542`): read the snapshot first and the epoch second. If an `invalidate` lands between the two reads, the call fails closed and answers `None`.
- Holding the snapshot as one object, a `(generation, mapping)` pair, keeps the 15.4 Round-3 HIGH #2 "single lookup, no torn read" invariant (`version_status.py:488-500`).
- Use `started_seq < self._published_seq` (strict). A later pass at the same epoch then always wins, and an older pass that finishes late is dropped. The barrier test: A starts, B starts and commits, then A is released. Assert that the published map is B's and that `_published_seq` equals B's sequence.
- **Full catalog only.** Every production caller must pass the whole catalog (see Pitfall 1). Because each pass covers every tool, discarding an older pass never leaves a tool without a record.

### Pattern 2: `tool_health` as a pure precedence function (STATE-02)

```python
class Health(StrEnum):                 # declaration order IS precedence (D-01)
    CHECKING = "checking"; BROKEN = "broken"; MISCONFIGURED = "misconfigured"
    OUTDATED = "outdated"; OK = "ok"; MISSING = "missing"; UNAVAILABLE = "unavailable"

@dataclass(frozen=True)
class Evidence:                        # local, never stored (D-01); field names are discretion
    present: bool
    available: bool                    # unavailable_reason(tool, live_platform) is None
    checking: bool = False             # e.g. a skill pack whose hosts are all still unprobed
    broken: tuple[str, ...] = ()       # one sentence per fact: shim, receipt drift, link to dir/nothing
    misconfigured: tuple[str, ...] = ()
    outdated: str | None = None        # the sentence, e.g. "1.2.3 -> 1.3.0 available"
    notes: tuple[str, ...] = ()        # shadowed, off-policy, unknown owner, unreadable version, proof...
    absent_reason: str | None = None   # UnavailableReason.detail when not available

def tool_health(ev: Evidence) -> tuple[Health, tuple[str, ...]]:
    if not ev.present:
        return (Health.MISSING if ev.available else Health.UNAVAILABLE), ...
    facts = [(Health.CHECKING, ...), (Health.BROKEN, ev.broken), ...]
    # the winner is the first non-empty in declaration order; reasons = the winner's facts first,
    # then the other states' facts in precedence order, then the notes (19-UI-SPEC A12)
```

- The test is one `pytest.mark.parametrize` over the product present × {checking, broken, misconfigured, outdated} plus absent × available (2⁴ + 2 = 18 rows). It includes "broken + outdated → BROKEN with both reasons" (SPEC AC3).
- A macOS stub is **not present** (`status.MACOS_STUBS`, `status.py:14-17`). It becomes MISSING with the stub reason, never BROKEN (target-architecture §1).

### Pattern 3: Receipt schema and fail-closed reader (STATE-03)

```json
{"v": 1, "tool": "yq", "at": "2026-10-16T12:00:00Z",
 "method": {"kind": "github_release", "key": "<sha256 of canonical params JSON>"},
 "package": null,
 "artifacts": [{"path": "/home/u/.local/bin/yq", "type": "file",
                "sha256": "…", "size": 14180512, "mtime_ns": 1760000000000000000}],
 "smoke": "ok", "hooks": {}}
```

- **Paths are absolute** in the file. Do not store `~`-relative paths, because `HOME` is patched in tests and a relative form invites a second expansion rule. Compare with `Path(...)` equality.
- **Reader:** reject a file over 64 KiB. Catch `OSError`, `UnicodeDecodeError`, `json.JSONDecodeError` and `RecursionError`, the last following the `install_ownership.py:11-16` precedent. Reject any `v != 1`, any `tool != tool_id`, an unknown artifact `type`, and a non-absolute path. Every rejection returns `None`, meaning "no proof". It never raises (SPEC AC8, prohibition 3).
- **matches(artifact):**
  - `link`: `os.readlink(path) == target`, and `path.is_symlink()`.
  - `dir`: `path.is_dir() and not path.is_symlink()`.
  - `file`: `lstat` is a regular file. If `size` and `mtime_ns` are equal, that is a match without hashing. Otherwise re-hash with `sha256_file`, and the file matches only if the sha256 is equal (D-08). A content-equal file whose mtime was touched is still a match. Remember the re-hash result per `(path, size, mtime_ns)` for the session so a 150 MB AppImage is not re-hashed every pass.
- **receipts_dir()** is resolved at call time (`Path.home() / ".local/state/tools-installer/receipts"`, next to `settings.json` at `settings.py:52`). It is created with `mkdir(parents=True, exist_ok=True)` before writing, because `atomic_write_bytes` (`atomic.py:34-53`) creates no parent dir.
- **Tool ids are safe filenames.** All 89 registry ids fullmatch `[a-z0-9][a-z0-9._-]*` (`[VERIFIED: load_tools over installer/registry.toml]`). Assert that in `receipts.py` anyway, because the id becomes a path.
- **One in-process writer lock** in `receipts.py` serializes `write` and `adopt`. An install (Execute worker) and an adoption (refresh worker) can target the same tool concurrently. `adopt` re-checks "no receipt yet and the fingerprint is unchanged since hashing" inside that lock.

### Pattern 4: One writer, two call sites (Ledger L-19-03)

- `engine.install_tool`: inside the success `else:` branch (`engine.py:234`), after the handoff return (`:201-207`) and the manager smoke (`:211-225`) succeed, and before `run_postinstall` (`:236-240`), call `receipts.record(tool, method, ...)`. Skip the call for `skill_pack`/`host_setup` (`_HANDOFF_KINDS`, `engine.py:28`) and for the native kinds `dnf`/`apt`/`pacman`/`rpm_ostree`.
- `update._perform`: after the owner dispatch succeeds (`update.py:285-308`) and before `_run_postinstall` (`:309`), call the same `receipts.record` for installer-owned download/app/script updates (rewrite). For brew/uv/pnpm updates, call it **only when a receipt already exists**: updating a package someone else installed does not make it ours. A failed update raises inside `_perform` and never reaches the call (SPEC AC7).
- A write failure (`OSError`) never flips INSTALLED into FAILED. It becomes `postinstall_warning`/`detail` text ("install receipt not written: …"), and the tool stays present and unproven (SPEC AC9). Test it by monkeypatching `receipts.write` to raise.
- **Per kind:**
  - download/app: `artifact_paths` stat'ed after success.
  - script: method plus **no artifacts** until Phase 22 `paths`. Recording `bin_dir/cmd` would turn every vendor self-update (`uv self update`, OMZ) into a false "changed since install".
  - brew/cask/uv-tool/node: `package` = `formula`/`cask`/`pypi_pkg`/`npm_pkg`, artifacts `[]` (the manager owns health).
  - `smoke`: `"ok"` for download/app (they always smoke, `executors.method_smoke_argv` defaults to `("--version",)`, `executors.py:55-62`); for manager kinds `"ok"` when `_manager_smoke_target` found a target, else `null`.

### Pattern 5: `artifact_paths` as the one formula (D-07, Ledger L-19-04)

```python
# installer/download.py
@dataclass(frozen=True)
class Artifact:            # what the method creates; evidence only
    path: Path
    kind: Literal["dir", "link", "file"]

def artifact_paths(method: Method, default_bin_dir: Path) -> tuple[Artifact, ...]:
    # github_release/tarball, archive: (opt_dir(name), "dir"), (bin/name, "link")
    # github_release raw:               (bin/name, "file")
    # app:                              (applications_dir()/app, "dir"), (bin/cli_name, "link")
    # name = link_name(method, member) (bin_name honored); cli_name via cli_spec (now in download.py)
```

- `uninstall.plan_uninstall` (`uninstall.py:82-110`) and `_download_link` (`:56-79`) collapse into `artifact_paths` plus an existence filter. `_plan_app` (`:33-53`) goes away.
- `install_download`/`install_app` keep their placement code but read the link and opt names from the same helpers (`link_name`, `cli_spec`).
- The raw-member guard stays: a name in `("", ".", "..")` yields no artifact (today at `uninstall.py:70-74`).

### Pattern 6: Adoption against the cached digest (D-09)

- Reuse `download.resolve_target(method, ExecContext(runner=<unused>, platform=live, resolve_release=lambda _repo: Release(tag=entry.latest_version, digests=entry.digests)))` (`download.py:99-162`). The asset name then comes from the same renderer install uses, and there is no network. Compare `sha256_file(bin/name)` with `entry.digests.get(target.asset)`.
- Only raw `github_release` methods are adopted by digest (`raw = true`; host registry: yq, direnv, shfmt, tealdeer, fx, dasel, wezterm, drawio-desktop, `[VERIFIED: load_tools]`). Archives use `is_still_proven` (`download.py:188-204`).
- **Host reality (fails closed):** every relevant cache entry on this host was written 2026-10-10, before 18-10 stored digests. Examples: yq `latest_version v4.54.1, checked_at 2026-10-10…, no digests`. With `STALE_AFTER = timedelta(days=7)` (`version_cache.py:44`), the entries re-fetch from about 2026-10-17. Until then adoption finds no digest and shows "not proven: reinstall with r to adopt". A file at an older version than the cached latest never matches. Both outcomes are by design.

### Pattern 7: Proof-driven removal (R6, Ledger L-19-06)

- `plan_removal(tools, default_bin_dir)` stays the one gate and keeps the `RemovalPlan(removable, yourself)` shape (`uninstall.py:113-166`). Its proof sources:
  1. receipt artifacts that `matches()` **and** that are in `artifact_paths(method)` for the receipt's method kind;
  2. the archive layout proof (`is_still_proven`).
  Everything else matched by name goes to `yourself`.
- **Intersection is a security control:** the receipt is user-writable JSON, and a tampered receipt naming `~/.ssh/id_ed25519` must never be deleted.
- The CLI (`app.run_uninstall`, `app.py:524-640`) and the TUI rows (`classify_tools`, `uninstall.py:329-413`) call the same function. The pass stores its per-tool result in `ToolState.removable` for display and for Phase 21.
- **Deletion-time re-proof:** extend `still_removable` (`uninstall.py:128-138`, used at `app.py:619-624` and `app.py:708-714`). It re-reads the receipt and re-verifies the sha256/readlink right before `remove_paths` (D-08: "Removal re-verifies the sha256 right before deleting").
- After a tool's proven artifacts are all removed, delete its receipt. If a delete fails, keep the receipt (target-architecture §5 "Removal").

### Pattern 8: Owner fixes (STATE-04)

- **uv (Ledger L-19-01):** run `uv tool dir` (not `--bin`) once per pass when `which("uv")` is set. Use it as the `uv` owner prefix in `owner_dirs` (`ownership.py:456-457`). Measured on the host: `uv tool dir` → `/home/bazzite/.local/share/uv/tools`; `uv tool dir --bin` → `/home/bazzite/.local/bin`. `attribute_path` resolves symlinks (`ownership.py:470-472`), so `~/.local/bin/graphify` → `~/.local/share/uv/tools/graphifyy/bin/graphify` attributes `[]` with the bin dir and `['uv']` with the tool dir `[VERIFIED: probe with owner_dirs/attribute_path, real paths]`. Pass the dir in as data; `owner_dirs` stays pure.
- **Volta:** add `"volta"` to `Owner` (`ownership.py:77-90`), with `owner_dirs["volta"] = (Path(os.environ.get("VOLTA_HOME", "~/.volta")).expanduser() / "bin",)`. A live path under it yields a synthetic candidate with evidence "Volta shim". That follows the `_os_package_owner` synthetic-candidate shape (`ownership.py:862-911`). Volta has no inventory; the shim dir is the proof.
  - Every exhaustive table needs a `volta` entry: `OWNER_LABELS` (exhaustiveness test `tests/test_ownership.py:965`), `OWNER_DETAIL_LABELS`, `_REMOVAL_COMMANDS`, `_REMOVAL_DESCRIPTIONS`.
  - `update._perform` must refuse `volta` cleanly ("managed by Volta — `volta install <pkg>`"). Otherwise it reaches `raise UpdateError(f"unsupported owner {owner!r}")` (`update.py:308`) and reports "failed".
  - Host: `~/.volta/bin/pnpm -> ~/.volta/bin/volta-shim`, and the same for `codex`, `openspec`, `npm`, `node` `[VERIFIED: ls -la ~/.volta/bin]`.
- **Redirect shims:** `which pnpm` on this host is `~/.local/bin/pnpm`, our redirect shim (`# tools-installer-redirect-shim`, `guards.py:117`). It attributes to `['installer', 'uv']`, which is ambiguous and therefore unknown `[VERIFIED: probe]`. Look through with `guards.real_binary(cmd, shim_dir=managed_bin_dir, path_value=PATH)` (`guards.py:287-313`), but only when the hit is in `managed_bin_dir` **and** `is_our_shim` holds. `is_our_shim` reads the whole file (`guards.py:277` `path.read_text()`), so guard it with `lstat().st_size < 8192` first, or a 150 MB AppImage would be read into memory.
- **Implicit `~/.local/bin`:** in `status.is_installed` (`status.py:96-107` bin_dir loop), add `artifact_paths(method, bin_dir(None))` presence for download kinds with no `bin_dir`. The test case: a fixture binary in `~/.local/bin` with no `bin_dir`, PATH without it, reads present.
- **host_setup (B 15 WR-06):** `_native_owner` discards a verified non-native result (`ownership.py:793-798`). For `host_setup` tools, keep `detect_owner`'s verified `HostSetup.owner` (pi → `"pnpm"`, `host_setup.py` `HOST_SETUPS["pi"]`) as a direct candidate. Probe the version with the **unresolved** `which` path, because `_version_argv` uses the resolved `active_path` (`version_status.py:238-252`, `_resolve_active_path` resolves at `ownership.py:1042-1050`). The same unresolved-path rule applies to Volta-attributed tools: a resolved path is `volta-shim`, whose `--version` is Volta's own.

### Pattern 9: One batched native query per pass (D-11; formats verified)

The pass collects the paths that still need a native answer after the tracked checks. It then makes one call per OS family through the injected `ProbeRunner`. Each output line names its path, so missing or unowned paths cannot shift the parse.

| Family | argv | Positive line | Unowned/missing | Exit |
|---|---|---|---|---|
| fedora (rpm) | `rpm -qf --qf '[%{FILENAMES}\t%{=NAME}\n]' P1 P2 …` | `/usr/bin/git\tgit-core` (one line per **file in the owning package**; filter to the queried paths) | missing → `error: file …: No such file or directory` on **stderr only**; unowned → `file … is not owned by any package` on stdout | non-zero when any path fails (seen 2, 3) |
| debian (dpkg) | `dpkg-query -S P1 P2 …` | `coreutils: /usr/bin/ls` (multi-owner: `a, b: /p`) | stderr `dpkg-query: no path found matching pattern …` | 1 |
| arch (pacman) | `env LC_ALL=C pacman -Qo P1 P2 …` | `/usr/bin/ls is owned by coreutils 9.11-2` | stderr `error: No package owns …` | 2 |

- Sources: `[VERIFIED: rpm 6.0.2 on host; debian:13 and archlinux:latest in disposable podman containers, --rm, none left]`.
- `%{=NAME}` is required. Plain `%{NAME}` inside `[...]` fails with `error: incorrect format: array iterator used with different sized arrays` `[VERIFIED: host]`.
- The rpm form prints every file of each owning package (657 lines for five paths, 14 ms `[VERIFIED: host]`). Match exact `path + "\t"`.
- Names still pass `_PACKAGE_NAME_RE` (`install_ownership.py:239`) and must be singular (`_one_name`, `:242-248`).
- **The exit code is non-zero whenever any path fails.** `run_probe` uses `check=True` (`install_ownership.py:51-60`), and `_run` maps every failure to `None` (`:76-80`). The batch must instead catch `subprocess.CalledProcessError` and parse `exc.stdout`. Fakes in tests raise `CalledProcessError(returncode, cmd, output=...)`. No new runner is needed.
- Memoize `rpm-ostree status --json` once per pass (B 15 WR-04: `_rpm_ostree` runs it per native row, `install_ownership.py:150`).
- The declared-package checks (`rpm -q`, `dpkg-query -W`, `pacman -Qq`) can batch the same way. SPEC only pins `rpm -qf`; batching these too is recommended and cheap.
- The acceptance test: a fake probe records argvs. N native tools produce exactly one argv starting `["rpm", "-qf"]` per pass.

### Pattern 10: Live `has_brew` (STATE-05)

- Re-read at the top of the pass (Pattern 1). The consumers that must read `service.platform`, not a construction-time `Platform`:
  - `resolve.py:67,70` (`_applies`), plus `:137` and `:195`, which use `replace(platform, has_brew=True)` and are unaffected;
  - `ownership.py:268` (`_ownership_only_methods`);
  - `version_status.py:619,624,676` (inventory/outdated/partial-failure);
  - **`ExecuteScreen`**: `self._inputs.platform` at `execute_screen.py:500` (dependency availability) and `:642` (`run_installs`). `ExecuteInputs.platform` is a frozen field (`:400-415`) built in setup.py at `:1230-1236`, so read `inputs.version_refresh.platform` when a service is bound;
  - `UpdateService` (setup.py `:1131-1132`), which gets `platform` at construction.
- AC13 test: `Platform(has_brew=False)` with a `which` that returns `None` for brew, then a pass, then `which` returns a path for brew, then a second pass. `resolve_methods(colima, service.platform)` becomes non-empty, and `ExecuteScreen` resolves the dependency order with brew available. colima's only method is `kind = "brew"` `[VERIFIED: registry.toml colima entry]`.

### Pattern 11: `ConfigStep` (D-20)

```python
@dataclass(frozen=True)
class ConfigStep:
    text: str                                   # shown after " — to configure: " (19-UI-SPEC)
    kind: Literal["skill_install", "plugin_enable", "plugin_uninstall",
                  "marketplace_remove", "terminal_sync", "pnpm_group_install",
                  "project_pack_global_uninstall"]
    harness: str | None = None
    argv: tuple[str, ...] = ()                  # built + validated here, executed by Phase 20
    cwd: Path | None = None                     # project-scope plugin uninstall
```

- Every value that reaches `argv` comes from untrusted CLI or JSON output (plugin ids, marketplace names, project paths). Validate it: ids against `^[A-Za-z0-9@._/-]+$` (the `_SKILL_MATCH_RE` precedent, `model.py:180`), and `cwd` as an absolute existing directory. Anything that fails produces the reason with no step.

### Pattern 12: Skill partial / duplicate / disabled (STATE-07)

- **Cadence:** skill probes stay on `refresh_skills`'s once-per-launch cadence (`version_status.py:557-589`). On this host `codex plugin list` took 22.97 s (`claude plugin list` 0.63 s, `pi list` 0.12 s) `[VERIFIED: time on host]`. Running the probes inline would hold every row at `…` for about 25 s.
  - The pass builds skill rows from the current `self._skills` snapshot under the commit lock.
  - When `refresh_skills` commits, it rebuilds **only** the skill-pack `ToolState`s in the same-generation map, with the same `tool_health`, in one assignment.
- **Partial (D-17):** take `inspect_skill_packs` hosts (`skill_lifecycle.py:413-426`) and `present_harnesses(home, which)` (`:234-242`). If a harness is in `supported_harnesses ∩ present ∩ probed` and reports `absent` while another harness reports `present`, emit the reason `partial: missing on {Harness}` and a `skill_install` step. A pack for an absent harness gives no `≈` (SPEC AC14).
- **Duplicate/disabled (D-18):** parse Claude entries with scope, enabled and version.
  - Recommended argv: `claude plugin list --json` (Ledger L-19-09). Live output (Claude Code 2.1.301) is a JSON array of `{"id": "superpowers@claude-plugins-official", "version": "6.4.1", "scope": "user", "enabled": true, "installPath": …, "projectEnabled": false}` `[VERIFIED: host, read-only]`.
  - The text form is multi-line blocks: `❯ id@marketplace` / `Version:` / `Scope:` / `Status: ✔ enabled|✘ disabled` `[VERIFIED: host]`.
  - Present means exactly one enabled user-scope entry for the canonical id. Every other entry becomes a `duplicate:`/`disabled:` reason with the D-18 ordered steps (enable first, then uninstall copies, then marketplace remove).
  - Project-scope `cwd` comes from `~/.claude/plugins/installed_plugins.json` (`{"version": 2, "plugins": {id: [{scope, version, projectPath?}]}}`; the host currently has user scope only, so `projectPath` is `[ASSUMED]` from CONTEXT).
- The fixture reproduces the four-install superpowers state in JSON. It is not taken from the host, which was cleaned.

### Pattern 13: Project-scope packs (D-21; the riskiest scope)

- Put `scope` (closed: `"user"`/`"project"`, default `"user"`) and a pin `version` in `[tool.skill_lifecycle]`. Both are new names in `_parse_skill_lifecycle`'s `allowed_fields` (`model.py:585-597`). `METHOD_PARAMS["skill_pack"]` is `frozenset()` (`model.py:52`), so a method-level key would be rejected by the Phase 18 closed-key rule. See Ledger L-19-07.
- **Detection:**
  - Global leftovers: `~/.claude/gsd-core/`, `gsd-*` in `~/.claude/{skills,agents,commands,hooks}`, and so on → `≈` "installed globally; this pack is project-local", with step `project_pack_global_uninstall`.
  - Repos: walk a closed tuple of roots to a fixed depth, looking for `.planning/config.json`. A repo counts per runtime when `<repo>/<runtime dir>/gsd-core/VERSION` exists **and** that runtime's `skills` or `commands` dir is non-empty.
- **Host evidence:**
  - This repo: `.claude/gsd-core/VERSION` = `1.16.0`, `.claude/commands` 72 entries, `.claude/skills` 1. `.opencode/gsd-core/VERSION` present, `.opencode/{skills,commands,agents}` 72/72/64 `[VERIFIED: ls]`.
  - Global: `~/.claude/gsd-core/VERSION` exists (1.16.0, mtime 2026-10-15 18:44), 787 files under `~/.claude/gsd-core`, and 107 `gsd-*` entries in `~/.claude/{skills,agents,commands}` `[VERIFIED: find/ls, read-only]`. So the `≈` fires on this host (Ledger L-19-08).
- Project-local runtime dirs differ from the global ones. For opencode the project dir is `.opencode` while the global is `.config/opencode` (`INSTALL_STATE_HARNESS_DIRS`, `skill_lifecycle.py:206-216`). Only claude and opencode are verified; the other runtimes' project dirs are `[ASSUMED]`.

### Anti-Patterns to Avoid

- **A subset or single-tool `refresh([...])` after the one-swap change:**
  - `catalog_tui.py:431` passes `self.tools` (the tier subset);
  - `catalog_tui.py:974` passes `[target.tool]`;
  - `execute_screen.py:749` passes `[tool]`.
  With one swap, each of these publishes a map that lacks every other tool. Every production caller passes the full catalog. `setup.py:979` already does.
- **Reading `ToolState` inside `uninstall.py`:** `version_status` imports `uninstall` (`version_status.py:69`). `removal_plan(tool, state: ToolState)` inside `uninstall.py` would import back. Keep `plan_removal` evidence-based.
- **A second drift checker** for terminals (D-16 forbids it), or a second artifact formula in the receipt writer (D-07 forbids it).
- **Treating a `CalledProcessError` from the batched query as "no answer for everyone":** the stdout still holds every positive line.
- **Recording `bin_dir/cmd` for script receipts** (Pattern 4).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | a temp+rename | `atomic.atomic_write_text` (`atomic.py:56`) | Unique sibling temp, mode copy, and symlink-target resolution are already handled |
| sha256 of large files | read-all + `hashlib.sha256` | `checksums.sha256_file` (`hashlib.file_digest`, streaming) | AppImages are about 150 MB |
| Asset name for adoption | re-render templates | `download.resolve_target` with a cached `Release` | One renderer; no drift from install |
| Archive proof | new layout check | `download.is_still_proven` | Strict resolve, containment, dangling-safe |
| Shim look-through | PATH surgery | `guards.real_binary` / `is_our_shim` | Already handles the shim-finds-itself case |
| Package-name validation | ad-hoc regex | `install_ownership._PACKAGE_NAME_RE` + `_one_name` | Fail-closed, singular |
| pnpm incomplete groups | new comparison | `pnpm_globals.incomplete_install_groups` (`:489-523`), refactored to take the package-name set the pass already has (`inventory.pnpm_globals`) | It only reads `live.packages`; one function, two callers (Doctor and the pass) |
| Owned-region rewrite | a second parser | `terminal_shell._replace_owned_region` (pure) | D-16 |
| Legend width | `len()` | `rich.cells.cell_len` on markup-stripped text | 19-UI-SPEC A15 |

**Key insight:** every "new" capability in this phase already has a primitive that a previous phase hardened through review (CR-01 strict resolve, H1 deletion-time re-proof, RecursionError-safe JSON, staged swaps). New code that bypasses them re-opens closed review findings.

## Runtime State Inventory

This phase is a refactor plus a migration of proof (from the archive layout to receipts).

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `~/.local/state/tools-installer/receipts/` exists and is **empty** (created Aug 1 by an older version) `[VERIFIED: ls -la]`. `versions.json` holds `tools`/`managers`/`skills`. The relevant tool entries carry no `digests` yet (written 2026-10-10). | No migration. Receipts start empty, and pre-receipt tools are adopted (raw by digest, archive by layout) or shown "reinstall with r to adopt". The skills cache schema stores only `hosts`, so duplicate/disabled reasons are not persisted and reappear after the first `refresh_skills` |
| Live service config | None. There is no external service; Claude plugin state is read-only here | None (the D-18 fix runs in Phase 20) |
| OS-registered state | None. No systemd/launchd change; the prune daemon is untouched | None, verified by grep for `systemctl` in the phase scope |
| Secrets/env vars | `UV_TOOL_BIN_DIR` is read today (`ownership.py:456`) and is replaced by `uv tool dir`. `VOLTA_HOME` is newly read. `PATH` is read for the shim look-through | Code edit only |
| Build artifacts | None. There is no new entry point or package | None |

## Common Pitfalls

### Pitfall 1: A tier-subset or single-tool pass wipes the other tiers
**What goes wrong:** After the one-swap change, entering the user tier publishes a map containing only user-tier tools, so the system tier shows `…` again.
**Why it happens:** `CatalogScreen._refresh_versions_worker` calls `service.refresh(self.tools)` (`catalog_tui.py:431`), and two call sites refresh one tool (`catalog_tui.py:974`, `execute_screen.py:749`).
**How to avoid:** Pass the full catalog (`self._catalog`) everywhere. Delete the single-tool refresh in the update worker: the follow-up `_start_version_refresh()` at `:998` already runs a full pass. Read the status line's "now X" from `state_of` after that pass.
**Warning signs:** A test that refreshes system then user and asserts a system row is still not `…` fails.

### Pitfall 2: Receipts written into the developer's real HOME by tests
**What goes wrong:** Engine, session and Execute tests with fake runners succeed, so `install_tool` writes `~/.local/state/tools-installer/receipts/<id>.json` on the real machine.
**Why it happens:** The home guard covers dotfiles only (`tests/conftest.py:19`). `test_session.py` and `test_execute_screen.py` have zero HOME patches `[VERIFIED: grep count 0]`.
**How to avoid:** In Wave 0, add an autouse fixture that points `receipts.receipts_dir` at `tmp_path` (precedent: `sandboxed_puppeteer_cache`, `conftest.py:98`). Also add the real receipts dir's entry count and mtime to `_real_home_fingerprint`.
**Warning signs:** Files appear in the real `receipts/` after `make test`.

### Pitfall 3: The terminal "dry run" still writes
**What goes wrong:** `sync_terminal_shells(write=False)` changes files.
**Why it happens:** Several writes happen outside the `_write_if_changed` calls:
- `ensure_zshrc_template` rewrites `.zshrc` before any terminal (`terminal_shell.py:412`; `omz.py:428` `_atomic_write`);
- `_sync_konsole` writes its state file before its writes (`:307-309`);
- the zsh-absent branch reverts and unlinks (`:369-380`, `:231-239`, `:361-365`).
**How to avoid:** The `write` flag gates **all** of those (Ledger L-19-05). Add `TerminalShellResult.drifted` (the terminals whose content would change). Pin it with a test that fingerprints every file under a scratch HOME before and after the dry run.

### Pitfall 4: Batched native query parsed positionally
**What goes wrong:** A missing path emits nothing on stdout, so a positional parse assigns git-core to the wrong tool.
**How to avoid:** Use the path-named formats in Pattern 9, and pre-filter to `is_file()` paths. Under-count is impossible when you match by path.

### Pitfall 5: Adoption racing an install
**What goes wrong:** The pass hashes the old yq, the install replaces it and writes a receipt, then the pass's adoption overwrites that receipt with the old sha256. The next pass marks yq BROKEN.
**How to avoid:** The `receipts` module lock plus a re-check inside it before `adopt` writes (Pattern 3).

### Pitfall 6: A volta or host_setup version probe runs the shim
**What goes wrong:** `_version_argv` uses the resolved `active_path`, so `volta-shim --version` reports Volta's version for pnpm.
**How to avoid:** Use the unresolved `which` path for shim-managed owners (Pattern 8).

### Pitfall 7: The legend tests locked by 15.1 D-03/D-04 fail by design
**What goes wrong:** `test_legend_names_every_ver_cell_marker_and_style_token`, `test_legend_uses_explicit_line_breaks_per_group` and `test_legend_widget_paints_every_marker_at_full_width` (`tests/test_catalog_tui.py:1852-1964`) assert the four dim Ver labels that D-15 removes.
**How to avoid:** Rewrite them to the 19-UI-SPEC legend and name each one in the plan as a planned replacement, following the Phase 18 "Test Integrity" precedent. Keep the 78-cell and 3-line assertions, and add the compositor visibility check from UI-SPEC.

### Pitfall 8: A tampered receipt as an authority to delete
**What goes wrong:** Removal trusts receipt paths.
**How to avoid:** Delete only `receipt-matched ∩ artifact_paths` (Pattern 7). Test it with a receipt that lists a file outside `artifact_paths` but has a correct sha256: the plan must not include it.

### Pitfall 9: `update` of a raw file leaves the old receipt
**What goes wrong:** `update_download` replaces `~/.local/bin/yq`, the receipt still holds the old sha256, and the next pass shows "changed since install".
**How to avoid:** The update call site rewrites the receipt (Pattern 4). Test it: update succeeds, then the next pass is not BROKEN.

### Pitfall 10: Repair semantics drift into Phase 20
**What goes wrong:** Switching `ExecuteScreen._classify_selection` (`execute_screen.py:526-555`) from `ownership.broken` to `health is BROKEN` makes a "changed since install" raw file get overwritten on select. `_replace_raw` replaces whatever sits at the link (`download.py:318-328`).
**How to avoid:** In Phase 19, read only the replacement APIs (`state.ownership.broken`, `state.version`) and keep the repair predicate pnpm-shim-only. Dispositions are Phase 20.

## Code Examples

### Deterministic overtaken-pass barrier (SPEC AC1)

```python
# Source: adapted from tests/test_version_status.py:1130-1185 (existing pattern)
def test_an_older_pass_finishing_later_is_discarded(tmp_path, monkeypatch):
    a_holding, a_release = threading.Event(), threading.Event()
    calls = {"n": 0}
    def probe_output(argv):
        calls["n"] += 1
        if calls["n"] == 1:              # pass A blocks mid-loop
            a_holding.set(); assert a_release.wait(timeout=5)
            return "1.0.0"
        return "2.0.0"                   # pass B
    service = _service(tmp_path, probe_output=probe_output)
    t = threading.Thread(target=service.refresh, args=([tool],)); t.start()
    assert a_holding.wait(timeout=5)
    service.refresh([tool])              # B: same epoch, newer seq, commits
    a_release.set(); t.join(timeout=5)
    state = service.state_of(tool.id)
    assert state is not None and state.version is not None
    assert state.version.installed == "2.0.0"   # A published nothing
```

### Fake batched rpm probe

```python
def fake_probe(argv):
    calls.append(argv)
    if argv[:2] == ["rpm", "-qf"]:
        raise subprocess.CalledProcessError(2, argv,
            output="/usr/bin/git\tgit-core\n/usr/bin/jq\tjq\nfile /x is not owned by any package\n")
    raise subprocess.CalledProcessError(1, argv, output="")
# assert sum(1 for a in calls if a[:2] == ["rpm", "-qf"]) == 1
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Three maps (`_statuses`, `_ownership` epoch-tagged, `_skills`) and per-tier `_installed` | One frozen `(generation, map)` + `state_of` | this phase | Deletes the raced merge (`version_status.py:764`), `OwnershipRefreshed` needs (Phase 21 deletes the message) |
| Archive layout as the only removal proof (Phase 17 interim) | Receipt ∩ `artifact_paths`, adoption, layout | this phase | Raw binaries become removable when proven |
| `claude plugin list` text substring match (`_claude_matches`) | Structured entries with scope/enabled/version | this phase | Duplicates and disabled copies become visible |
| N native `rpm -qf` + N `rpm-ostree status --json` per pass | One path-named batch per OS family + one rpm-ostree read | this phase | Refresh no longer stalls behind `rpm-ostreed` |

**Deprecated/outdated:** `ownership_of`, `statuses`, `skill_status_of`, `set_installed`, `_BROKEN_MARK`, `_inst_cell`, `_present`, the four `_VER_*` dim labels (`catalog_tui.py:215-225`), and `UV_TOOL_BIN_DIR` attribution.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pacman -Qo` "is owned by" output is localized under non-C locales, so the batch runs under `env LC_ALL=C` | Pattern 9 | Without it, a non-English Arch host parses no owners (fails closed to unknown, not wrong) |
| A2 | `installed_plugins.json` project-scope entries carry `projectPath` (CONTEXT says so; the host has none to check) | Pattern 12 | The D-18 project-scope uninstall step has no `cwd`; emit the reason without a step |
| A3 | Project-local runtime dirs for codex/cursor/kilo/kimi/windsurf/antigravity/copilot under opengsd `--local` | Pattern 13 | Those runtimes read "not installed in repo"; claude/opencode are verified |
| A4 | Known roots for the D-21 repo walk: `~/git`, `~/src`, `~/code`, `~/projects`, `~/work`, `~/dev`, depth ≤ 4, skipping hidden dirs/`node_modules`/`.venv`, capped at about 5,000 dirs | Pattern 13 | A repo outside these roots is not counted; it is still a reason, never a false `✓` |
| A5 | The draw.io AppImage does not self-replace its file (an electron updater would make "changed since install" appear) | Pattern 4 | A false `!` on drawio-desktop until reinstall |
| A6 | The opengsd pin value is `1.16.0` (the local VERSION) | Pattern 13 | The global-uninstall step names a different version than the one installed; that command still uninstalls |

## Open Questions (RESOLVED)

1. **How does the CLI `--yes` path read `ToolState.removable` without a refresh pass?**
   - RESOLVED: it does not need to. The gate is the pure, receipt-aware `plan_removal`. The pass stores its result in `ToolState.removable`; CLI and TUI call the function, and deletion re-proves (Ledger L-19-06).
2. **Where does Konsole drift attach, given there is no `konsole` catalog row?** The registry has `zsh`, `kitty` and `wezterm` rows only `[VERIFIED: grep registry.toml]`.
   - RESOLVED: attach `≈` "Konsole does not start zsh" to the `zsh` row, whose configuration it is, and only when `konsole` is on PATH (Ledger L-19-10).
3. **Is D-21's per-repo install/update executed in Phase 19?**
   - RESOLVED (recommendation, needs orchestrator ledger): no. Phase 19 builds detection plus the validated `ConfigStep` argv (`pnpm dlx @opengsd/gsd-core@<pin> --<runtime> --local --relative-includes`, run with `cwd=<repo>`). Phase 20 RECONFIGURE executes it. Skill packs are handoff-only today (`engine.py:127-129`, `_HANDOFF_KINDS`), and SPEC Boundaries put reconfigure in Phase 20 (Ledger L-19-07).
4. **Should a cache entry without digests force a re-fetch so adoption works sooner?**
   - RESOLVED: no. SPEC Constraints forbid new network calls. Adoption converges as entries pass `STALE_AFTER` (7 days); until then it fails closed with the "reinstall with r to adopt" hint.
5. **Does an update create a receipt for a brew/uv/pnpm package that has none?**
   - RESOLVED: no. It rewrites an existing receipt only (Pattern 4). Installer-owned download/app/script updates always write, because the update's own executor placed those files.
6. **What does `ToolState` carry for skill packs before the first `refresh_skills`?**
   - RESOLVED: the stale cache seeded at launch (`seed_skills_from_cache`, setup.py `:911`) counts as evidence with a "cached" note. If no cache entry exists, the pack is CHECKING (`…`) until the skill probe commits.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | test runner, `uv tool dir` | ✓ | 0.11.28 | — |
| Python (venv) | everything | ✓ | 3.12.12 | — |
| rpm | D-11 batch (host family fedora, immutable) | ✓ | RPM 6.0.2 | tests use fakes |
| dpkg-query / pacman | D-11 batch on debian/arch | ✗ on host | — | fakes in unit tests; formats verified in `debian:13` / `archlinux:latest` containers |
| podman | `make e2e` container backstop | ✓ | images present (fedora, debian:13, archlinux, ubuntu:22.04) | — |
| claude CLI | D-18 JSON shape | ✓ | 2.1.301 | fixtures |

**Missing dependencies with no fallback:** none.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-xdist + pytest-cov + pytest-asyncio (`asyncio_mode = "auto"`, `pyproject.toml:50`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` :47, `fail_under = 90` :58) |
| Quick run command | `uv run pytest tests/<file>.py -q --no-cov` |
| Full suite command | `make validate && make test` |
| Baseline | 3959 tests collected at `fde3e68` (Phase 18 close: 3949 passed / 4 skipped) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATE-01 | Two overlapping passes at the same epoch: only the newer publishes; an older one finishing later is discarded; an invalidate-raced pass publishes nothing; `state_of` returns None for an old generation; a full-catalog caller contract | unit (threading.Event barrier) | `uv run pytest tests/test_version_status.py -q --no-cov -k "overtaken or one_swap or state_of or generation"` | ✅ file, ❌ tests |
| STATE-01 | Before the first pass every row renders `…`; a navigation refresh keeps marks; a tier-subset refresh never wipes other tiers | unit (Textual run_test) | `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "checking or first_pass or full_catalog"` | ✅ / ❌ |
| STATE-02 | `tool_health` parametrized table (18 rows) incl. broken+outdated → broken with both reasons; absent → missing/unavailable | unit | `uv run pytest tests/test_version_status.py -q --no-cov -k tool_health` | ✅ / ❌ |
| STATE-02 | Every mark on system/user/ai tiers; legend 3 lines ≤ 78 cells (`cell_len`) and visible on the compositor at 80×20 and 120×30; empty tier renders | unit (Textual) | `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "health_cell or legend or empty_tier"` | ✅ / ❌ (replaces 15.1 legend tests) |
| STATE-03 | `receipts.read/write/matches`: round-trip, `v != 1`, malformed, oversize, RecursionError, wrong tool, relative path → None; stat-fingerprint drift; link target change; dir type | unit | `uv run pytest tests/test_receipts.py -q --no-cov` | ❌ W0 |
| STATE-03 | Receipts written for download (archive+raw), app, script, brew, uv-tool, node; none for native/skill_pack/host_setup; a write failure leaves INSTALLED + warning + no receipt | unit (fake runner, scratch HOME) | `uv run pytest tests/test_engine.py -q --no-cov -k receipt` | ✅ / ❌ |
| STATE-03 | Successful update rewrites; failed update keeps the old receipt; manager update without a receipt writes none | unit | `uv run pytest tests/test_update.py -q --no-cov -k receipt` | ✅ / ❌ |
| STATE-03 (R5) | sha256 = cached digest → adopted + reason + receipt; mismatch → no receipt + "not proven: reinstall with r to adopt"; non-match remembered by (path,size,mtime_ns); no digest → unproven; adoption never overwrites a concurrent install receipt | unit | `uv run pytest tests/test_version_status.py tests/test_receipts.py -q --no-cov -k adopt` | ❌ |
| STATE-03 (R6) | `--yes` and the TUI remove a receipt-proven raw binary and refuse an unproven one; changed link target → not removable + broken; a tampered receipt path outside `artifact_paths` is never deleted; deletion re-verifies sha256; receipt deleted after removal | unit | `uv run pytest tests/test_uninstall.py tests/test_app.py -q --no-cov -k "receipt or proven or tampered"` | ✅ / ❌ |
| STATE-04 | graphify under `uv tool dir` → owner uv; Volta shim → volta (pnpm via Volta too); redirect shim → real owner; implicit `~/.local/bin/<bin>` → present; host_setup keeps its probe; update refuses volta cleanly | unit | `uv run pytest tests/test_ownership.py tests/test_status.py tests/test_update.py -q --no-cov -k "uv_tool_dir or volta or shim or implicit or host_setup"` | ✅ / ❌ |
| STATE-04 | One `rpm -qf` argv per pass for N native tools; rpm-ostree once; path-named parse of rpm/dpkg/pacman outputs incl. missing/unowned/multi-owner; CalledProcessError stdout used | unit | `uv run pytest tests/test_install_ownership.py tests/test_version_status.py -q --no-cov -k "batch or native_index or one_probe"` | ✅ / ❌ |
| STATE-05 | A fake brew appearing between passes → `service.platform.has_brew` True; colima resolves a method; ExecuteScreen uses the live platform | unit | `uv run pytest tests/test_version_status.py tests/test_execute_screen.py -q --no-cov -k "has_brew or live_platform"` | ✅ / ❌ |
| STATE-06 | Focused row lists reasons in order and "to configure:" steps; 400-char reason list stays within 3 rows | unit (Textual) | `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "detail or reasons or unconfigured"` | ✅ / ❌ |
| STATE-07 / R9 | Partial pack on a present harness → `≈`; absent harness → none; claude JSON 4-install fixture → duplicate/disabled reasons + ordered steps; project pack global leftover → `≈`; empty-dirs false positive → not installed | unit | `uv run pytest tests/test_skill_lifecycle.py tests/test_version_status.py -q --no-cov -k "partial or duplicate or disabled or project_pack"` | ✅ / ❌ |
| R9 | Terminal dry run: drifted kitty/WezTerm/Konsole → `≈`; no terminal → none; dry run writes nothing under the scratch HOME (fingerprint) | unit | `uv run pytest tests/test_terminal_shell.py -q --no-cov -k "dry_run or drift"` | ✅ / ❌ |
| R9 | Incomplete pnpm group from the cached inventory → `≈` with step | unit | `uv run pytest tests/test_pnpm_globals.py tests/test_version_status.py -q --no-cov -k incomplete` | ✅ / ❌ |
| Gate | No new dependency; architecture doc section present | grep | `git diff --quiet fde3e68 -- pyproject.toml uv.lock` | — |

### Sampling Rate
- **Per task commit:** the touched test file(s) via `uv run pytest tests/<file>.py -q --no-cov`
- **Per wave merge:** `make validate && make test`
- **Phase gate:** full suite green; `git diff --quiet fde3e68 -- pyproject.toml uv.lock`; one `make e2e` after the receipt + removal plans land (a real container install writes receipts; `make uninstall --yes` removes a receipt-proven raw binary and leaves no receipt)

### Wave 0 Gaps
- [ ] `tests/test_receipts.py`: STATE-03 reader/writer/matches/adopt
- [ ] `tests/conftest.py`: an autouse fixture redirecting `receipts.receipts_dir()` to `tmp_path`, plus the real receipts dir in `_real_home_fingerprint`
- [ ] Shared fixtures: fake batched native probe (rpm/dpkg/pacman outputs above), claude `plugin list --json` 4-install fixture plus `installed_plugins.json`, a GSD project-repo tree (VERSION + empty-dirs case)
- [ ] Planned-replacement list for the 15.1 legend tests (`tests/test_catalog_tui.py:1852-1964`) and for the `set_installed`/`ownership_of`/`statuses` tests (24 matches in `test_catalog_tui.py`, 28 in `test_version_status.py`, 3 in `test_setup.py`, 2 in `test_wizard_app.py`)

## Security Domain

`security_enforcement` is enabled (`security_asvs_level: 1`, `security_block_on: high`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes (local file deletion authority) | Removal only of `receipt-matched ∩ artifact_paths` or the layout proof; re-proof at deletion (Pattern 7) |
| V5 Input Validation | yes | Receipt JSON schema check with size cap and RecursionError catch; package names `_PACKAGE_NAME_RE`; plugin ids/marketplaces/project paths validated before any `ConfigStep.argv`; tool id filename assertion; `rich.markup.escape` on reasons |
| V6 Cryptography | yes (integrity only) | `hashlib.file_digest(..., "sha256")` via `checksums.sha256_file`; never a hand-rolled hash; digest compare uses plain equality of hex strings (not secret, so timing is irrelevant) |
| V12 Files and Resources | yes | Atomic writes (`atomic_write_text`); receipts dir created with `parents=True`; a symlinked receipt file is followed by `atomic_write_bytes` (`atomic.py:43`). Refuse to write when `receipts/<id>.json` is a symlink (LOW, defense in depth) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tampered receipt lists a foreign path with the matching sha256 | Tampering / Elevation | Intersect with `artifact_paths`; never delete from the receipt alone |
| Planted `rpm`/`dpkg-query`/`pacman`/`claude` earlier on PATH prints crafted output | Spoofing / Tampering | Fail-closed parsers, singular names, regex-validated identifiers; output never reaches a shell; argv lists only |
| Adoption accepts a file because the cached digest is attacker-controlled | Tampering | The digest came from the GitHub API over HTTPS (Phase 18); a cache tamper needs local write access (same trust boundary as the binary itself). Adoption only grants removal of that one file |
| Corrupt/oversized receipt crashes the worker | DoS | Size cap, broad parse catch, `None` result |
| TOCTOU between preview and delete | Tampering | Existing H1 re-proof extended to the sha256/readlink check |

## Ledger candidates (for the orchestrator; decisions unchanged here)

| ID | Decision | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| L-19-01 | D-12 | `uv tool dir --bin` returns the managed bin dir, so it does not fix graphify. Attribution resolves symlinks into the tool dir | `uv tool dir` → `/home/bazzite/.local/share/uv/tools`; `--bin` → `/home/bazzite/.local/bin`; probe `attribute_path(~/.local/bin/graphify)` = `[]` with the bin dir and `['uv']` with the tool dir; `ownership.py:470-472` resolves | Use `uv tool dir` (no `--bin`), as SPEC R7 and target-architecture §1.1 already say |
| L-19-02 | D-02 | An epoch-only commit check lets an older same-epoch pass finishing later overwrite a newer one, violating SPEC R1/AC1 | `refresh` captures only `self.epoch` (`version_status.py:695`); only `invalidate` bumps it (`:591-602`); three tier workers (`catalog_tui.py:423-435`) plus `setup.py:979` refresh concurrently with no invalidate | Add a monotonic pass sequence; commit iff `epoch == started_epoch and started_seq > published_seq` |
| L-19-03 | D-06 | The update path never calls `engine.install_tool`, so a single write point there cannot satisfy "update writes / a failed update keeps the old receipt" | `update.py:10-12` ("It also never imports `installer.engine`"); `_perform` `:236-317` | One writer `receipts.record`, two call sites (engine success branch; `update._perform` before `_run_postinstall` `:309`) |
| L-19-04 | D-07 | `download.artifact_paths` cannot call `apps.cli_spec`: `apps.py:27` imports `download` | `from installer.download import is_still_proven, pinned_url` (`apps.py:27`) | Move `cli_spec` into `download.py` (still the one reader of `cli_name`, keeping 18 D-04's single place); `apps`/`uninstall`/`tests/test_apps.py:11` import it from there |
| L-19-05 | D-16 precondition | The Konsole helper **does** I/O before its writes, and the sync also writes `.zshrc` | `atomic_write_text(state, …)` + `mkdir` at `terminal_shell.py:307-309`; `ensure_zshrc_template(...)` at `:412` (writes via `omz.py` `_atomic_write`); zsh-absent revert writes/unlinks (`:369-380`) | `write=False` must gate all of these, and the dry run must report `drifted` |
| L-19-06 | D-10 | The CLI `--yes` route runs no refresh pass, so "ToolState.removable is the only gate" cannot be read there | `setup.py:1385-1414` loads tools and calls `run_uninstall` directly | The gate is the pure receipt-aware `plan_removal`; the pass stores its result; CLI/TUI call the function; deletion re-proves. Also intersect with `artifact_paths` (security) |
| L-19-07 | D-21 | There is no pin and no `scope` field anywhere: the registry uses `@latest`; `METHOD_PARAMS["skill_pack"]` is `frozenset()`; skill_lifecycle `allowed_fields` lacks both. Per-repo install/update execution overlaps Phase 20 RECONFIGURE, and skill packs are handoff-only | `model.py:52`, `model.py:585-597`; registry opengsd `npx @opengsd/gsd-core@latest`; `engine.py:127-129` | Add `scope` and `version` to `[tool.skill_lifecycle]` (opengsd `scope="project"`, `version="1.16.0"`); Phase 19 detects and builds the validated `ConfigStep` argv, Phase 20 executes |
| L-19-08 | D-21 host state | "Global Claude GSD was removed" no longer holds | `~/.claude/gsd-core/VERSION` 1.16.0 (mtime 2026-10-15 18:44), 787 files; 107 `gsd-*` in `~/.claude/{skills,agents,commands}`; `~/.claude/gsd-install-state.json` | Expect `≈` "installed globally" for opengsd on this host; host cleanup is the user's choice (not done here) |
| L-19-09 | D-18 | `claude plugin list --json` exists and gives `id`/`version`/`scope`/`enabled` as structured data; the text form needs a multi-line block parser | Claude Code 2.1.301; `--json` output shown in Pattern 12 | Parse `--json` (one structured parser); keep the text fixture only if the orchestrator prefers "existing output" literally |
| L-19-10 | SPEC R9 | There is no `konsole` catalog row to carry Konsole drift | registry ids include `zsh` (:535), `kitty` (:2697), `wezterm` (:2778); no `konsole` | Attach Konsole drift to the `zsh` row, gated on `konsole` on PATH |
| L-19-11 | CONTEXT refs / prerequisite | Phases 17 and 18 have landed, and line refs drifted (e.g. `refresh` `:677-771` → `:690-784`; raced merge `:751` → `:764`; `engine.py:155-168` → `:201-240`; `uninstall.py:56-97` → `:82-110`; `status.py:40-52` → `:96-107`; `engine.py:132` → `:181`). `deps.resolve_dependencies` already takes an `is_installed` predicate | this file's citations at `fde3e68` | Refresh the refs in CONTEXT; no decision change |

## Sources

### Primary (HIGH confidence)
- Code at HEAD `fde3e68` (read this session): `installer/version_status.py`, `catalog_tui.py`, `engine.py`, `update.py`, `uninstall.py`, `app.py`, `download.py`, `apps.py`, `atomic.py`, `checksums.py`, `ownership.py`, `install_ownership.py`, `status.py`, `skill_lifecycle.py`, `terminal_shell.py`, `pnpm_globals.py`, `guards.py`, `resolve.py`, `execute_screen.py`, `wizard_app.py`, `setup.py`, `model.py`, `tests/conftest.py`, `tests/test_catalog_tui.py`, `tests/test_version_status.py`
- Host probes (read-only): `rpm -qf` formats and exit codes; `uv tool dir [--bin]`; `claude plugin list [--json]`; Volta shim layout; timings of the harness CLIs; version-cache digests and raw-file sha256
- Disposable containers (`podman run --rm`): `dpkg-query -S` (debian:13), `pacman -Qo` (archlinux:latest)
- Planning: 19-SPEC.md, 19-CONTEXT.md, 19-UI-SPEC.md (approved), ROADMAP Phase 19, REQUIREMENTS STATE-01..07, target-architecture §0-§2, §4.3, §5, §7, §8 P3, §9.2, §10; audit B (WR-04/06), C (G3, G5), F (X4, X7); 18-CONTEXT L-18-01..23; 18-VERIFICATION

### Secondary (MEDIUM confidence)
- `installed_plugins.json` v2 shape (host user-scope only; project entries per CONTEXT)

### Tertiary (LOW confidence)
- Assumptions A1-A6 above

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. No new dependency; versions read from the venv.
- Architecture: HIGH. Every seam was read at HEAD, and the Ledger findings rest on executed probes.
- Pitfalls: HIGH for 1-10. They come from code reads and host measurements.
- D-21: MEDIUM. Roots and non-claude/opencode runtime dirs are assumed.

**Research date:** 2026-10-16
**Valid until:** 2026-11-15 (code baseline stable; the Claude CLI JSON shape may move faster)
