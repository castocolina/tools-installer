# Audit A: promised vs delivered, Phases 1–12 and 12.1–12.4

Date: 2026-10-13. Auditor A of 7. Read-only. The only thing written is this file.
Branch: `gsd/phase-16-detection-version-and-ownership-must-answer-is-it-on-this-di` @ `7861ced`.

## Header

**What I read**
- `.planning/ROADMAP.md`: "Phases", the "Phase Details" for 1–12 and 12.1–12.4, and the 999.x backlog (only to map findings).
- For each phase dir 01–12 and 12.1–12.4: CONTEXT (locked decisions plus `<deferred>`), every PLAN's `must_haves.truths`, every PLAN threat register row marked `accept`, and the VERIFICATION frontmatter (status, human_verification, overrides). For 12.3 and 12.4 I also read RUN-REPORT.md §12.3, 12.4-AUDIT.md, 12.4-RESEARCH.md (the scope claim) and 12.4-02-SUMMARY.md (the live transcript).
- `.planning/REQUIREMENTS.md` (deferred and partial lines) and `.planning/todos/`.
- The two known reports, `.planning/research/2026-10-11-ponytail-audit.md` and `…-architecture-review-gpt-6.1-sol.md`, so I don't report their findings again as new.
- Current code, using CodeGraph (`codegraph sync`, then `codegraph explore`) plus targeted reads: `installer/{model,resolve,engine,session,postinstall,update,catalog_tui,execute_screen,ui_common,policy,omz,pnpm_globals,ownership,host_setup,apps,locations,status,guards,version_cache}.py`, `setup.py`, `installer/registry.toml`, `scripts/container-e2e-verify.sh`, `.claude/architecture.md`, `.claude/skills/tool-onboarding/SKILL.md`.

**What I ran**
- The full suite: `uv run pytest -q` (no `-n`) on Linux, 2026-10-13. About 3,400 tests, 3 skipped, **exit 0** (green locally; CI is red per 999.7).
- Headless probes, all inside `/tmp/claude-1000/auditA/` with an overridden `HOME`:
  1. Registry load: tiers, methods, recommends and hooks for 27 tools.
  2. Every method-param key in the registry against the code that reads it.
  3. `apps.cli_spec` on draw.io.
  4. `graphify <host> install` for claude/codex/opencode/cursor in a scratch project with a scratch HOME.
  5. `rtk init -g …` with a scratch HOME.
  6. `cursor-agent --list-models`, read only, to confirm the Phase 10 slug.

**What I skipped**
- Re-running Tier-3 containers, tmux real-terminal checks and anything on macOS. The host is Bazzite, and launchctl tests are opt-in.
- Line-by-line re-verification of every one of the ~290 PLAN truths. Where a truth is pinned by a named test and the suite is green, I count it DELIVERED without re-reading it.
- Phases 13–16, 15.x, the backlog and the todos (auditor B). I note them only where they replaced or broke an earlier promise.

**Classification key:** DELIVERED, PARTIAL, REGRESSED, NEVER (NEVER-DELIVERED), DF (DEFERRED-AND-FORGOTTEN: deferred or accepted and never revisited), SUPERSEDED (deliberately replaced by a later phase; not a failure).

## Per-phase table

| Phase | Promises checked | Delivered | Partial | Regressed | Never | Deferred-forgotten | Superseded |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 Catalog tier foundation | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| 2 Tier views and recommends | 8 | 8 | 0 | 0 | 0 | 0 | 0 |
| 3 Install/uninstall/tweak lifecycle | 8 | 7 | 0 | 0 | 0 | 0 | 1 |
| 4 Package-manager redirect | 9 | 7 | 1 | 0 | 0 | 1 | 0 |
| 5 codegraph/mmdc/puppeteer | 8 | 7 | 0 | 0 | 0 | 1 | 0 |
| 6 SDKMAN and authoring guidelines | 4 | 3 | 1 | 0 | 0 | 0 | 0 |
| 7 System/user tier expansion | 8 | 6 | 0 | 0 | 0 | 2 | 0 |
| 8 AI tier expansion, uv-tool | 6 | 5 | 0 | 0 | 0 | 1 | 0 |
| 9 Postinstall hooks | 6 | 5 | 0 | 0 | 0 | 1 | 0 |
| 10 Agent CLI ergonomics | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| 11 Background daemon (macOS) | 6 | 5 | 0 | 0 | 0 | 0 | 1 |
| 12 Version status and update | 10 | 8 | 1 | 0 | 0 | 1 | 0 |
| 12.1 Reconciliation verification | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| 12.2 install_actions / agent_policy | 4 | 3 | 0 | 0 | 0 | 1 | 0 |
| 12.3 Container e2e | 6 | 4 | 1 | 0 | 0 | 1 | 0 |
| 12.4 Onboarding skill and audit | 7 | 5 | 1 | 0 | 1 | 0 | 0 |
| **Total** | **105** | **88** | **5** | **0** | **1** | **9** | **2** |

**Headline:** Phases 1–12 are mostly what they claim to be. I found **no currently REGRESSED promise**: every change to an earlier promise is either a deliberate replacement or a defect already fixed in 9050446. The real gaps are:

- **One shipped hook that does the wrong thing.** graphify's agent registration writes project-local files into whatever directory the installer runs from (12.4).
- **Deferred decisions and accepted risks nobody revisited (9).** Two of them have since caused visible defects: the ignored draw.io `cli_name`, and no re-registration for an agent host installed later.
- **Verification evidence that went stale.** The 12.3 container e2e has never been re-run since Phases 13–16 rewrote install, uninstall and detection, and its uninstall check reads only the exit code.

## Per-phase detail (only the items that are not DELIVERED, plus notes that matter)

### Phase 1: Catalog tier foundation (5/5 delivered)
- Evidence:
  - The tier is required: `installer/model.py:651-652`.
  - The four core tools are pinned to `system`: `tests/test_registry.py:1148`.
  - The tier distribution is pinned: `tests/test_registry.py:1123` (26/17/47 today).
  - The statement exists: `.claude/architecture.md:27` "Tier is a browsing label".
- Note, not a failure: later phases reassigned several tiers. `claude`, `codex`, `cursor-agent` and `antigravity` moved ai→user; `puppeteer` user→ai and `ast-grep` user→ai (Phase 15-03). The mechanism promise holds.

### Phase 2: Tier views and recommends (8/8 delivered)
- Evidence:
  - Six views from one table: `installer/ui_common.py:115-187`.
  - Cross-tier requires notice at mark time: `installer/catalog_tui.py:839-849`.
  - Recommends prompt with `r`/`d`, re-filtered on accept: `catalog_tui.py:851-897`, bindings `:318-319`.
  - Marks repainted on resume: `catalog_tui.py:1022-1030`.
  - Grouping tabs are intact: `catalog_tui.py:171-175`.
- Note: the base-tier `enter_view` gap that 999.6 traces to Phase 2's `show_view` was fixed in 9050446. F10, the residual base-tier special-casing, stays in 999.6. The staged selection surviving an Uninstall is 999.1(a).

### Phase 3: Install/uninstall/tweak lifecycle (7 delivered, 1 superseded)
- DELIVERED:
  - Dependency-failed skip: `installer/session.py:166-169`. It is rendered in the TUI too, `installer/execute_screen.py:925-928`, and on the console, `installer/app.py:188`.
  - Tweak sweep shares one predicate: `installer/uninstall.py:447,533`, `setup.py:954`.
  - The daemon "decided" marker is cleared on full uninstall: `installer/app.py:574,631`.
- SUPERSEDED: D-03 promised that a `.zshrc` without a single-line `plugins=(...)` raises `OmzPluginsError` and the toggle stays OFF. Phase 15.6 D-04 replaced that with an ordered repair, `installer/omz.py:344-415`. The "reads ON only when both plugins are present" disclosure became ownership-record based, `installer/wizard_app.py:1790-1798`; that also retires accepted risk T-03-09. Both changes are deliberate and safer.

### Phase 4: Package-manager redirect (7 delivered, 1 partial, 1 DF)
- DELIVERED:
  - `REDIRECTED` parallel to `BANNED`: `installer/guards.py:39-60`.
  - pip/pip3 stay hard-blocked with the uv-pip gap recorded: `guards.py:20`.
  - volta global redirect: `guards.py:151-262`.
  - Doctor labels: `guards.py:509`.
  - The pnpm-globals replay is real-pnpm by absolute path: `installer/pnpm_globals.py:710-742`.
- PARTIAL, the residual pnpm set is "derived live from `registry.toml`'s `kind="node"` methods":
  - The Doctor's lost-globals audit only knows `kind="node"` rows, `pnpm_globals.py:555-575`.
  - `pi` (re-added in 12.1) is a pnpm global installed through `host_setup` (`installer/host_setup.py:28-42`, `pnpm add -g --ignore-scripts …`), so losing pi after a pnpm self-update is never reported.
  - The automatic replay uses the live `pnpm list -g`, so pi is replayed, but without its `--ignore-scripts`.
  - Impact: low. Backlog: NEW (close to 999.6: one shared state).
- DF: the npm non-global subcommand-allowlist decision (04-CONTEXT `<deferred>`, SC#5 "until its own decision is made separately") was never scheduled. It is not in the backlog or todos. Plain `npm run`/`npm ci` stay hard-blocked for as long as the ban is on. Impact: low or medium for npm-based projects. Backlog: NEW.

### Phase 5: codegraph/mmdc/puppeteer (7 delivered, 1 DF)
- DELIVERED:
  - codegraph is a checksummed `github_release` on both OSes: `installer/registry.toml:1514-1538`.
  - The `co_install`/`allow_build`/`versions`/`smoke` mechanism: `installer/executors.py:84-99,277-309`.
  - The split-group detection reaches the TUI Doctor: `setup.py:1048-1051`, `installer/wizard_app.py:596,625`. The `make doctor` console path is deliberately not wired, as planned.
- DF, accepted risk T-05-22 ("pnpm removes a whole comma group when either member is removed"):
  - It was accepted because "this installer never performs that removal".
  - Since 15.4 the Uninstall screen prints the command, `installer/ownership.py:1375` (`pnpm remove --global {package}`), for `mmdc` with no warning that pnpm also removes `puppeteer`. The premise of the acceptance no longer holds.
  - Impact: low or medium (silent removal of a sibling). Backlog: 999.8 (per-method removal spec).

### Phase 6: SDKMAN and authoring guidelines (3 delivered, 1 partial)
- DELIVERED:
  - SDKMAN exclusivity is test-enforced: `tests/test_registry.py:269`.
  - The java no-pin resolution is recorded above `registry.toml:1777`.
  - The brew-preference guideline: `.claude/architecture.md:350`.
- PARTIAL, SC#3 "a documented, **mandatory** per-tool per-OS verification step for future registry additions":
  - It is documented (`architecture.md:199-248`) but nothing enforces it.
  - Rows added after Phase 6 have no `# Verified` record: `drawio-desktop` (`registry.toml:2711`), `drawio-cli` (`:2759`), `pi` (`:2691`).
  - A per-OS check would have caught the macOS draw.io defect (see Phase 7 DF #1).
  - Impact: medium (it is the reason later rows ship unverified). Backlog: 999.5 / NEW (no enforcement test).

### Phase 7: System/user tier expansion (6 delivered, 2 DF)
- DELIVERED:
  - gnu-bash uses `detect_path` so `/bin/bash` cannot satisfy it: `registry.toml:581-600`.
  - Apple Containers `min_os_version` gate: `installer/resolve.py:44-48`.
  - The genuine-vs-bootstrap availability split, now `unavailable_reason`: `resolve.py:131-195`, wired at `setup.py:784`.
  - kitty and wezterm casks plus Linux paths. The kitty Bazzite gap accepted in 07-03 was later closed by a Linux `script` method.
- DF #1, accepted risk T-07-14 ("a misspelled method param key is not validated at load"):
  - It is still true: `model.py:668` keeps every key as an opaque param.
  - It has already bitten. The draw.io macOS `app` methods declare `cli_name = "drawio"` (`registry.toml:2746,2754,2795,2803`), which no code reads. `installer/apps.py:47-66` names the symlink `draw.io` (probe: `cli_spec → ('Contents/MacOS/draw.io','draw.io')`), while `cmd = "drawio"`. So on macOS the `drawio` CLI never lands on PATH.
  - Already known as GPT-6.1-sol AR-07 ("NEW: ignored cli_name"), but **no backlog item owns it**. Deepened here: the root cause is a Phase 7 accepted risk that was never revisited.
  - Impact: medium. Backlog: no owner; fits 999.3/999.8 schema work.
- DF #2, accepted risk T-07-15 ("two-run bootstrap on a fresh Bazzite: brew installed this run, zsh/oh-my-zsh resolve to nothing"): unchanged, because `has_brew` is frozen at startup. Backlog: 999.6 (AR-03, mutable facts frozen as platform constants).

### Phase 8: AI tier expansion, uv-tool (5 delivered, 1 DF)
- DELIVERED:
  - `uv-tool` executor: `installer/executors.py:528`; kind: `model.py:27`; `_applies`: `resolve.py:54-65`.
  - graphify uses `graphifyy` and requires uv: `registry.toml:1583-1607`.
  - rtk has the arch-split checksummed ladder plus a brew fallback: `registry.toml:1660-1690`.
  - The four hosts recommend codegraph/graphify/rtk: `registry.toml:1342,1377,1401,1454`.
- DF: antigravity's `recommends` was "deferred, not dropped" (08-CONTEXT D-01). It was never revisited. 12.4-AUDIT Pass 1 even calls antigravity one of "the five agent hosts", yet `installer/postinstall.py:26` registers hooks for four. Impact: low. Backlog: NEW.
- Note: `cursor-agent` and `antigravity` are now `tier="user"`. That is a deliberate later reclassification, not a regression.

### Phase 9: Postinstall hooks (5 delivered, 1 DF)
- DELIVERED:
  - Closed dispatch: `installer/postinstall.py:277-299`.
  - The hook runs only in the per-method success branch and is isolated: `installer/engine.py:165-170`.
  - The warning is shown in the TUI: `execute_screen.py:928,1002`.
  - No `--target auto`; a no-op when no host is present: `postinstall.py:119-140`.
  - The full catalog is passed for host presence: `execute_screen.py:486,620`.
- DF: 09-CONTEXT `<deferred>` lists "re-trigger codegraph's registration when an agent host is installed after the fact" (D-01).
  - Never revisited. Phase 12.4 copied the same one-shot shape to `rtk-register` and `graphify-register`.
  - Installing claude/opencode/codex/cursor-agent **after** codegraph/rtk/graphify leaves them unregistered.
  - The only re-dispatch is a `u` update of the hook's own tool (`installer/update.py:309`).
  - 999.11 notes this gap for herdr only. Impact: medium (the agent tooling silently does nothing for the new host). Backlog: NEW (one post-mutation re-sync, the same family as 999.1/999.4).

### Phase 10: Agent CLI ergonomics (5/5 delivered)
- Evidence:
  - Alias and function bodies: `installer/tweaks.py:70-136`.
  - The live-verified slug is still valid: on 2026-10-13, `cursor-agent --list-models` lists `gpt-5.6-sol-high`.
  - Split-mode `ensure_sourced_from` is a live closure that re-reads the persisted link mode: `setup.py:800-801,919-925,986`. Phase 13's settings change did not break it.

### Phase 11: Background daemon (5 delivered, 1 superseded)
- DELIVERED:
  - fd/rg are soft requirements: `installer/policy.py:868`.
  - Log, time picker and decided marker, as above.
  - The on-by-default auto-apply is restricted to the interactive wizard: `setup.py:1065-1077,1238`.
- SUPERSEDED: SC#2 "inert on Linux". It was replaced by 15.7 D-01a (the systemd timer). This is recorded in the ROADMAP itself.
- Note: the `TOOLS_INSTALLER_RUN_LAUNCHCTL_TESTS` real round-trip is opt-in and was never run since the move to Linux. macOS is unverified locally (999.7).

### Phase 12: Version status and update (8 delivered, 1 partial, 1 DF)
- DELIVERED:
  - 7-day cache, stale marker and backoff: `installer/version_cache.py:42-46`, `catalog_tui.py:226`.
  - Owner-first dispatch, with sdkman and native owners refused: `update.py:245-317`.
  - The pnpm snapshot is captured **before** the update, with an unreadable snapshot refused: `update.py:453-487`.
  - The same `UpdateService` serves both the `u` key and Phase 14's Execute path: `execute_screen.py:699-727`.
  - Postinstall re-dispatch: `update.py:309,343-358`.
  - In-flight guard: `update.py:431-440`.
  - `u` is in `VIEWS`: `ui_common.py:126`.
- PARTIAL, "every mutation this app performs calls `VersionRefreshService.invalidate`" (12 replan note):
  - Install (`wizard_app.py:2949`), uninstall (`setup.py:962`) and update (`update.py:499`) do.
  - The Doctor `r` pnpm-globals reinstall (`setup.py:1060-1063`) does not. After it, Ver/Owner can show the pre-replay state for up to the 6 h `MANAGER_STALE_AFTER`.
  - Impact: low. Backlog: NEW (one refresh owner, 999.6 F9 family).
- DF: SC#5 manager-drift alerting.
  - Deferred with a sound rationale (`REQUIREMENTS.md:90-91`) but owned by no backlog item.
  - `REQUIREMENTS.md:94` says "None deferred", which contradicts its own line 90.
  - Impact: low. Backlog: NEW.

### Phase 12.1: Reconciliation verification (5/5 delivered)
- Evidence:
  - The suite is green locally today (full run, exit 0). CI is red, which is 999.7.
  - The 11-row tier audit is a permanent test: `tests/test_registry.py:1152`.
  - The `MANUAL_REQUIRED` bucket: `session.py:34,205,216`.
- Note: the re-added-row audit was **tier-only**. Method correctness, such as draw.io's ignored `cli_name`, was never audited (see Phases 6 and 7). `agent_policy.py`/`agent_guidance.py` are still inert (ponytail F11, 999.10).

### Phase 12.2: install_actions / agent_policy (3 delivered, 1 DF)
- DELIVERED: `install_actions.py` and its test are deleted, with 0 references outside `.planning`. The suite is green.
- DF: D-02 "leave `agent_policy.py` dormant pending the `../ai-kit` migration decision". No decision was ever recorded and the module is still dead weight (~565 lines with tests). Backlog: 999.10 (ponytail F11 lean-up).

### Phase 12.3: Container e2e (4 delivered, 1 partial, 1 DF)
- DELIVERED, as point-in-time 2026-09 evidence: the detection script and the D-03 no-fallback gate, the full-catalog pass 1 (RUN-REPORT.md:156-215), the host-untouched attestation, and the decisions recorded.
- PARTIAL, plan 12.3-03 "surfaces any idempotency or uninstall bug, not just a green happy path":
  - `TRACER_UNINSTALL_OK` is printed on **exit code alone** (`scripts/container-e2e-verify.sh:426-433`: "only the exit code … is evidence here").
  - Nothing checks what the sweep left behind, so the run could not see ponytail F7 (Sublime's `~/.local/opt/subl` left after "Removed") or F1 (deleting files by name).
  - "Zero real … uninstall bugs found" (RUN-REPORT) overstates it.
  - Backlog: 999.8 for the bugs; the harness gap is NEW.
- DF:
  - 12.3-04 made `detect-container-runtime.sh`/`container-e2e-verify.sh` "the entry point future e2e phases should call" (`architecture.md:540-542`). No phase since has called it.
  - It is not in `Makefile` or CI, and the last full-catalog run predates Phases 13–16, which rewrote install execution, update dispatch, uninstall and detection.
  - Debian/Arch coverage and the Apple-Silicon question (12.3-CONTEXT `<deferred>`, "not dropped") were never revisited.
  - Backlog: NEW (999.7 covers CI and a host re-check, not container e2e).

### Phase 12.4: Onboarding skill and audit (5 delivered, 1 partial, 1 never)
- DELIVERED:
  - Shared `present_agent_hosts()`: `installer/postinstall.py:29-46`.
  - rtk per-host registration is global. A probe with a scratch HOME showed `rtk init -g …` writes only under `$HOME` (`~/.claude/*`, `~/.codex/*`, `~/.config/opencode/plugins/rtk.ts`) and nothing in the cwd.
  - The checklist: `architecture.md:249-349`. The skill: `.claude/skills/tool-onboarding/SKILL.md`. The decisions are consolidated.
- **NEVER, D-02 graphify half ("graphify's postinstall hook registers per-host"):**
  - `_graphify_register` runs `graphify <host> install` with no cwd (`postinstall.py:258-274`; `installer/run.py` never sets `cwd`).
  - Probe in `/tmp/claude-1000/auditA/gp` (graphify 0.9.54, the exact version in the registry comment) with HOME pointed at a scratch dir: the four calls wrote **only into the current directory**: `CLAUDE.md`, `.claude/settings.json` (a PreToolUse hook), `AGENTS.md`, `.codex/hooks.json`, `.opencode/opencode.json`, `.opencode/plugins/graphify.js` and `.cursor/rules/graphify.mdc`. Nothing was written under `$HOME`.
  - 12.4-RESEARCH.md:277-281's claim that bare `graphify <host> install` "is global/user-scope by design" is false. The 12.4-02 live test ran in "a throwaway scratch project" and verified merge-safety only, so nobody noticed the scope.
  - Effect: the agent hosts are not registered globally. `make setup` (cwd = repo root) appends a graphify section to the tracked `AGENTS.md`, creates `CLAUDE.md`, and installs a graphify PreToolUse hook in the repo's `.claude/settings.json`. Every `u` update of graphify repeats this in whatever directory the TUI was launched from.
  - Impact: **high** (unrequested writes into an arbitrary project, a hook that changes agent behavior there, and the advertised feature not delivered). Backlog: NEW.
- PARTIAL, D-04 "every one of the 89 entries checked … tier correctness":
  - 12.4-AUDIT.md Pass 2 (lines 33-48) checked tiers mechanically (manager `requires`) and spot-checked tier rationale on **two** entries.
  - Phase 15-03 then had to fix ast-grep's and puppeteer's tiers, and 15.3 re-tagged 63 audience values. The same audit missed the graphify scope defect and draw.io's dead param.
  - The skill has since drifted: it does not mention `owner_probes` (Phase 15) or `post_install` sensitive actions (Phase 14).
  - Backlog: 999.5 for the skill; the audit depth is NEW.

## Later phases that replaced or broke an earlier promise

- **Replaced, deliberately:**
  - 3 D-03 (refuse when there is no array) became 15.6 D-04 (repair).
  - The 3 omz ON-reading moved to ownership-record semantics.
  - 11 SC#2 (Linux inert) became 15.7 D-01a (systemd timer).
  - 12-02 "native owners resolve `unknown` by design" became the Phase 15 native-owner adapter.
  - 7 `platform_could_support` is now also behind `unavailable_reason`.
  - Several tiers changed (Phase 1 note).
- **Broken, then fixed:** the base-tier `enter_view`/installed-map re-derive (Phase 2 origin), fixed in 9050446 (999.6).
- **Eroded by a later addition:**
  - The 12.1 re-added rows bypassed the Phase 6 checklist (draw.io, pi).
  - 15.4 started printing pnpm removal commands, which voided Phase 5's T-05-22 acceptance.
  - 12.1's `pi` host_setup pnpm global sits outside Phase 4's registry-derived residual set.

## NEW gaps not in the backlog (ranked by severity)

1. **HIGH: the graphify postinstall writes project-local agent config into the installer's cwd and never registers globally** (12.4 D-02; `installer/postinstall.py:258-274`; probe above). Under `make setup` it dirties the repo's tracked `AGENTS.md` and installs a PreToolUse hook in the repo. Fix direction: the global form (`graphify install --platform <host>`, "copy skill to platform config dir"), or a pinned `cwd=$HOME` only if graphify documents that as user scope. Verify with a HOME-sandboxed probe that asserts nothing lands in the cwd.
2. **MEDIUM: agent registration is one-shot.** codegraph/rtk/graphify hooks never re-run when an agent host is installed later (Phase 9 D-01 deferral, multiplied by 12.4). Belongs with a post-mutation re-sync (999.1/999.4 family), together with herdr's identical gap (999.11).
3. **MEDIUM: container e2e is stale and blind to leftovers.**
   - It has not been re-run since Phases 13–16.
   - The uninstall pass checks only the exit code (`container-e2e-verify.sh:426-433`).
   - It is not in make or CI, and Debian/Arch/macOS are not covered.
   - Should gate the 999.8/999.6 work.
4. **MEDIUM: unvalidated registry param keys (Phase 7 T-07-14, never revisited).** draw.io's ignored `cli_name` is the live instance (known as AR-07 but **owned by no backlog item**). Add load-time rejection of unknown method keys, then fix draw.io. `cli_spec` must honor the declared name, and uninstall must derive the same name.
5. **MEDIUM: the Phase 6 "mandatory" verification step is unenforced.** draw.io-desktop, draw.io-cli and pi carry no `# Verified` record. A registry test that requires the record would have caught item 4.
6. **LOW–MEDIUM: Uninstall hands the user `pnpm remove --global @mermaid-js/mermaid-cli` with no warning that pnpm also removes `puppeteer`** (T-05-22 premise voided by 15.4; `ownership.py:1375`). Fold into 999.8.
7. **LOW–MEDIUM: the macOS prune LaunchAgent runs the script from the repo checkout and reads ON from the plist's existence alone.**
   - The script path is fixed at `setup.py:119`, and `is_active`/`active` are `plist_path.exists()` at `installer/policy.py:863,872`.
   - Moving or deleting the checkout breaks every scheduled run while Policies still shows ON; only the run log shows `(exit N)`.
   - 15.7 made the Linux state runtime-truthful (D-01c); macOS was left behind. Phase 11's own review moved the wrapper out of the checkout for this exact reason, but not the script it runs.
8. **LOW: deferred-and-forgotten decisions with no owner:** npm subcommand allowlist (Phase 4), antigravity recommends and hooks (Phase 8), manager-drift alerting (Phase 12; `REQUIREMENTS.md:94` "None deferred" contradicts line 90).
9. **LOW: Doctor `r` (pnpm-globals reinstall) skips `VersionRefreshService.invalidate`** (`setup.py:1060-1063`). Its rows can stay stale for up to 6 h.
10. **LOW: `pi`'s pnpm global is invisible to the Doctor lost-globals audit** (`pnpm_globals.py:555-575` only knows `kind="node"`). The replay also drops pi's `--ignore-scripts`.
11. **LOW: 12.4's "89/89 tier audit" was mostly mechanical**, with tier rationale spot-checked on 2 rows. Phase 15/15.3 had to redo it. Process lesson for 999.5: an audit claim needs per-row evidence.

**Not checked:** macOS behavior (Phases 7, 11 and 12 brew/cask/launchd paths), any real-terminal tmux check, and Phase 12's "a fresh session issues zero manager subprocesses" once Phase 15's per-tool native probes were added (owned by auditor B's phases).
