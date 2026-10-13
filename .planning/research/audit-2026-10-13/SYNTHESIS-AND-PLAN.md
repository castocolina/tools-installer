# Audit 2026-10-13: synthesis and plan

Inputs: seven read-only Opus audits in this directory (A, B: promised vs delivered; C, D, E, F: every registry entry per OS/arch for install, detect, uninstall and configure; G: UI health states and screen reuse, ponytail-ultra), plus `../2026-10-11-ponytail-audit.md`, `../2026-10-11-architecture-review-gpt-6.1-sol.md`, ROADMAP backlog 999.1–999.11 and `.planning/todos/`.

## Scorecard

**Promises (milestone v0.49.0, phases 1–16):**

| Phases | Checked | Delivered | Partial | Regressed | Never | Deferred and forgotten |
|---|---|---|---|---|---|---|
| 1–12.4 (A) | 105 | 88 | 5 | 0 | 1 (graphify registration) | 9 |
| 13–16 (B) | 147 | 90 | 9 | 0 | 0 | 44 (mostly low) |

Nothing regressed, but "complete" overstated the state. Some failures were invisible to the verifiers:
- graphify registration never worked.
- 53 deferred items were never revisited.
- The container end-to-end check has not run since phases 13–16 rewrote install, uninstall and detection, and it only checks exit codes.

**Registry (90 entries):**

| Tier | OK | Minor | Major | Blocker |
|---|---|---|---|---|
| system (C, 26) | 2 | 15 | 8 | 1 java |
| user part 1 (D, 23) | 11 | 7 | 3 | 2 ruff, difftastic |
| user part 2 (E, 24) | 2 | 13 | 7 | 2 sublime, jetbrains-toolbox |
| ai (F, 17) | 1 | 11 | 4 | 1 graphify |
| **Total** | **16** | **46** | **22** | **6** |

Installing binaries mostly works. Detection, ownership, removal, configuration and health are where the architecture falls short.

## Hazards on the user's host now (act before anything else)

1. **Sublime on Linux is already damaged.**
   - `~/.local/bin/subl` links to a directory, and a reinstall overwrote the real binary.
   - Do NOT reinstall it until the `ln -sfn` and `is_file` fix lands (E gap 1).
   - Cause: wrong `member` in the registry, `download.py:189,404`.
2. **graphify's postinstall writes into the installer's working directory, not `$HOME`.**
   - It writes `CLAUDE.md`, `AGENTS.md`, `.claude/settings.json` and others; confirmed by A and F independently.
   - Installing or updating graphify from `make setup` edits this repo.
3. **Uninstall can delete files it cannot prove it wrote.** Examples: a pip or uv `yq`/`ruff` in `~/.local/bin`, and the `drawio` file shared by two entries. `make uninstall --yes` does this without asking (F1, deepened by D C2).
4. **Policies link-mode change silently strands enabled policies** (B #1).
5. **Non-atomic rc writes** (F5).
6. **A crashed run reports a green "Done." and exit 0** (B #3).

## Consensus themes (independent auditors agree)

| Theme | Evidence | Today's backlog |
|---|---|---|
| No single tool state. Seven to ten places answer "installed / owner / removable / version / healthy" differently. | ponytail F6, GPT AR-03, G R1, C G1/G4/G5, D C8, E 6–7, F X4/X7, B #4 | 999.6 |
| No health model. Only the pnpm dangling shim is "broken". Missing: macOS stubs (java, git), link-to-directory, broken symlink, glibc floor (no smoke test), venv shadowing, misconfigured hooks, MCP entries and terminals. | C G1, D C6/C12/C1, E 12, F X2, G R1 | partly 999.6 |
| The review screen does not say what will happen. There is no reinstall, repair or reconfigure, and the headless `--all` path is a second engine. | G R4 (6 of 9 probes false), B #2, D C9 | 999.1 |
| Methods describe installation only. Detect, version, owner, update, remove, configure, service and privileges are switched on kind in each subsystem or missing. Examples: update downgrades pinned apps, script re-runs are no-ops, vendor rc edits are never tracked, services never start, sudo cannot prompt. | GPT AR-07, C G2/G7/G8/G9/G10/G11, E 2/5/8, D C4 | 999.8 (removal only), 999.2 |
| Configuration is install-only and one-way. Five of six `post_install` actions are unimplemented. Agent-host hooks are never re-run for a new host or reversed on removal. Terminal drift and `SHELL` are not handled. | C G6, D C3, F X1/X3, A #2, G R1 #4 | 999.4, 999.11 (herdr only) |
| One screen family, one lifecycle. Ten forks remain in `UnifiedApp`, each view has its own refresh and status rules, and Uninstall is not a projection of the catalog. | ponytail F10, G R2/R3 | 999.10, 999.6 |
| Registry drift is never detected. Assets get renamed (difftastic), repos move (gitui, tealdeer), unknown keys are accepted (draw.io `cli_name`), `# Verified` dates are missing, and 50 of 89 release downloads have no checksum although GitHub's API exposes sha256. | D C5/C10, A #4/#5, F X5 | none |
| Verification is blind. CI is red on both OSes, the container end-to-end is stale, there are no per-direction tests, and the phase 16 gap plans were not re-audited. | 999.7, A #3, B #8 | 999.7 |

## Contradictions resolved

- **G pushes back on 999.10's new `RowsScreen` class.** Lifecycle defaults belong in the existing `AppScreen`, selection pruning in `ToolBrowser`, and state in one shared `ToolState`. This is smaller and is adopted.
- **999.3 is overstated (B).** `tarball` and `app` already vary per OS/arch. The real gaps are narrower: dmg-only macOS artifacts, the `app` kind taking no `{ver}`, a Distrobox kind (Alacritty), and Homebrew Intel Tier 3.
- **CI already triggers on `pull_request` (GPT).** The merge simply skipped the PR.
- **Interim F1 fix is insufficient (D).** Name match is the only proof even for "installer/direct" ownership. Raw single-file tools need receipts (999.2) before any removal is "proven ours".

## Recommendation: close v0.49.0 and open a new milestone

The audit shows the missing pieces are architectural, not a handful of bugs: a shared tool state with health, an install plan with dispositions, a per-method lifecycle contract with receipts, and configuration as a first-class lifecycle step. Adding phases 17+ to a milestone whose 16 phases are all marked complete would hide that. Close v0.49.0 with this audit attached as its honest closing record, then open **v0.50.0 "Truthful lifecycle"**.

Before writing requirements, run one **ponytail-ultra architecture design pass**. It turns G's state/UI target plus the method-lifecycle findings (C/D/E/F/GPT) into one target-architecture document, sized to the smallest complete change. It must specify:
- the closed `Health` set and its precedence;
- `ToolState`;
- the `Disposition` set;
- the per-method lifecycle contract (install, detect, version, owner, update, remove, configure, service, privileges);
- the receipt format;
- the configure/re-sync trigger model;
- the screen lifecycle.

Then `/gsd-new-milestone` uses that document.

### Proposed phases (each ships and tests on its own; every refresh or lifecycle promise gets per-view, per-direction tests)

| # | Phase | Absorbs | Why this order |
|---|---|---|---|
| 1 | **Stop the bleeding.** Make CI green on both OSes and gate merges on the PR check. Fix F5 atomic rc writes and stale indices. A crashed or failed run must report failure and exit non-zero. graphify hook: run the global install or disable it. Archive installs: `ln -sfn` plus an `is_file` check. Repair guidance for the damaged Sublime. Interim F1 guard: never remove an unproven artifact, and never under `--yes`. Policies link-mode strand. | 999.7, 999.9 (F5, F2), B #1/#3, A #1, E gap 1, F1 interim | Data loss and false success first; a green gate before anything else merges. |
| 2 | **Registry truth and drift guard.** Apply all data-only fixes from C/D/E/F. Reject unknown method keys at load. Require `# Verified`. Add `make verify-registry`: an asset/member probe against the latest release that can run on a schedule. Add a GitHub-digest checksum fallback and a post-install smoke test. Launch without the dev venv on PATH. Detect the macOS java/git stubs. | A #4/#5, D C1/C5/C6/C10/C12, C G1/G12, E fixes, F fixes | Cheap, high yield. It also feeds health signals to phase 3. |
| 3 | **One tool state with health** (`ToolState`/`Health`, computed once per refresh, raced passes publish nothing). Includes: uv attribution, Volta and redirect-shim owners, the implicit `~/.local/bin`, live manager availability, multiple installations, and per-harness skill state with partial/duplicate. The catalog Inst cell and legend read it. | 999.6, GPT AR-03/AR-04, C G3/G5, D C7/C8, E 6/7, F X4/X7, B #4/#10 | Everything below reads it. |
| 4 | **Install plan with dispositions.** Each selection shows install / update / repair / reconfigure / reinstall (`r`) / skipped-with-reason. Outcomes summary, retained selection, the headless `--all` path on the same plan, and exit codes from outcomes. | 999.1, G R4, B #2/#9, D C9 | Fixes the most visible false text and gives "will be reinstalled". |
| 5 | **One screen family.** Neutral root, push-all, enter-after-push, one app-level full-catalog refresh owner, status cleared on leave. Uninstall becomes a ToolState projection (proven-removable, then managed elsewhere, then nothing to do), with the selection pruned. Policies and Doctor join the same lifecycle (F3, F8, F17). | 999.10 (screens), 999.9 (F3/F8/F17), G R2/R3, ponytail F4/F9/F10 | The UI can only agree once state (3) and plan (4) exist. |
| 6 | **Method lifecycle contract and receipts.** Per method: detect, version source, update command, remove (level 1/2/3), config/data paths and policy (keep / delete / ask), vendor rc edits it makes, service start/stop, privileges. Receipts as removal proof. Privilege preflight for sudo. Per-OS/arch gaps that remain: dmg, `app {ver}`, Distrobox kind, Intel Tier 3. | 999.2, 999.8, 999.3 (narrowed), C G2/G7/G8/G9/G10/G11, E 2/5/8/9/11, D C4, F X6/X9 | The biggest change; it lands on stable state, plan and screens. |
| 7 | **Configuration as a lifecycle step.** Implement the post-install actions: shell init (starship, direnv, zoxide, fzf, fnm), git config (delta, difftastic), first-run data (tldr), completions. Agent-host hooks re-run when a host appears and reverse on removal, with config-health probes (MCP, hooks). One agent-host list. Terminal drift, `SHELL` env and keybinding customizations. Desktop entries. All behind the "ask the user" customization choices. | 999.4, C G6, D C3, E 9/10, F X1/X2/X3, A #2, G R1 #4 | Needs the lifecycle contract (6) and the RECONFIGURE disposition (4). |
| 8 | **Onboarding through the skill.** herdr (binary, integrations postinstall, skill pack) and Alacritty (no-reboot path). skill-judge the onboarding skill. Re-run the container end-to-end with leftover checks on Fedora, Debian and Arch. | 999.11, 999.5, A #3/#11 | Proves the new contract on real tools. |
| 9 | **Lean.** Delete dead code: the agent-env policy, the questionary chooser, `audit.py`, dead fields. Put `setup.py` under pyright and coverage. Split `wizard_app.py`, drop review-history comments, merge modals, and remove worker message plumbing while keeping the epoch checks. | 999.10 (lean), ponytail F11–F15, G #9 | Last, so deletions do not fight the rewrites. |

Deferred-and-forgotten items with no new phase are listed for triage at milestone start; the full lists are in the A and B reports. Examples: the version parser fabricating versions, non-UTF-8 `settings.json` crashing at launch, the npm allowlist, antigravity recommends, manager-drift alerting, and the macOS prune agent's truthfulness.

## Decisions needed from the user

1. Close v0.49.0 now and open v0.50.0 (recommended), or append phases 17+ to v0.49.0.
2. Run the ponytail-ultra architecture design pass before `/gsd-new-milestone` (recommended).
3. Phase 1 can start immediately as a quick hotfix phase, before the new milestone's planning finishes.
