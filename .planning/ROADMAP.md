# Roadmap: tools-installer

## Milestones

- ✅ **v0.49.0 Tiered Catalog** — Phases 1–16 incl. 12.1–12.4 and 15.1–15.8 (shipped 2026-10-13, override closeout; see [archive](milestones/v0.49.0-ROADMAP.md) and [audit](research/audit-2026-10-13/SYNTHESIS-AND-PLAN.md))
- ✅ **v0.50.0 Truthful lifecycle** — Phases 17–26 incl. 23.1–23.2 and 24.1–24.5 (shipped 2026-11-16; see [archive](milestones/v0.50.0-ROADMAP.md) and [audit](milestones/v0.50.0-MILESTONE-AUDIT.md))

## Phases

<details>
<summary>✅ v0.49.0 Tiered Catalog (Phases 1–16) — SHIPPED 2026-10-13</summary>

28 phases, 110 plans, 244 tasks. Tier-scoped catalog, dependency drag-in, postinstall hooks, background maintenance daemon, version-aware status and updates, live in-TUI install execution, ownership attribution and the Owner column, terminal default shell on immutable hosts, self-deduping PATH, filesystem-based detection. Full phase details: [milestones/v0.49.0-ROADMAP.md](milestones/v0.49.0-ROADMAP.md); phase directories: `milestones/v0.49.0-phases/`.

</details>

<details>
<summary>✅ v0.50.0 Truthful lifecycle (Phases 17–26) — SHIPPED 2026-11-16</summary>

17 phases, 276 plans, 438 tasks, 121/121 requirements. Every screen tells the truth about each tool on this host (present, healthy, whose, which version, removable with proof), and install, update, removal and configuration follow one per-method contract with install receipts as removal proof. Full phase details: [milestones/v0.50.0-ROADMAP.md](milestones/v0.50.0-ROADMAP.md); phase directories: `milestones/v0.50.0-phases/`.

- [x] Phase 17: Stop the bleeding (21 plans) — completed 2026-11-15
- [x] Phase 18: Registry truth and drift guard (28 plans) — completed 2026-11-15
- [x] Phase 19: One tool state with health plus receipts (46 plans) — completed 2026-11-15
- [x] Phase 20: Install plan with dispositions (31 plans) — completed 2026-11-07
- [x] Phase 21: One screen family (21 plans) — completed 2026-11-15
- [x] Phase 22: Method lifecycle contract (13 plans) — completed 2026-11-15
- [x] Phase 23: Configuration as a lifecycle step (16 plans) — completed 2026-11-15
- [x] Phase 23.1: Host safety: drop the skill-pack catalog entries, sandboxed tests, container-only e2e (18 plans) — completed 2026-11-07
- [x] Phase 23.2: Install-time tuning instead of Policies knobs (8 plans) — completed 2026-11-13
- [x] Phase 24: Onboarding through the skill and e2e (9 plans) — completed 2026-11-14
- [x] Phase 24.1: Onboard Neovim through the tool-onboarding skill (5 plans) — completed 2026-11-14
- [x] Phase 24.2: Schedules view (13 plans) — completed 2026-11-14
- [x] Phase 24.3: Catalog audit skill (11 plans) — completed 2026-11-14
- [x] Phase 24.4: Retire the npx, npm and pip guard aliases and redirects (7 plans) — completed 2026-11-14
- [x] Phase 24.5: JavaScript install priority brew then bun then volta (9 plans) — completed 2026-11-15
- [x] Phase 25: Lean (11 plans) — completed 2026-11-15
- [x] Phase 26: Commit and push quality hooks (9 plans) — completed 2026-11-16

</details>

## Backlog

### Phase 999.1: Install selection lifecycle: show every direct selection in the Install review with an explicit disposition (will install / already installed / unavailable / blocked), keep each dragged dependency tied to the dependent that pulled it in, and after an install keep only the selections that still need action (clear succeeded/already-satisfied, retain failed/skipped/cancelled/unavailable/blocked) (BACKLOG)

**Status (2026-11-16):** completed by Phases 20 and 21 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 20-VERIFICATION PLAN-01..05 and 21-VERIFICATION UI-08; tests/test_session.py::test_remove_failed_is_retained_and_removed_is_not passes at HEAD.

**Goal:** [Captured for future planning]
**Source:** abandoned branch `feat/catalog-reliability-scope-reduction` (tip d8a3123, Jul 2026); plan text preserved in `999.1-*/source/`. HEAD already has the SDKMAN-only JVM methods, the cached version status and Phase 14's explicit "outdated tool is not silently skipped" behavior; the dispositions model (`PlanDisposition` in the branch's `install_plan.py`) and retained-selection semantics have no equivalent in HEAD (`rg PlanDisposition` = 0 hits).
**Also covers (2026-10-10 real-host audit, NOT fixed):** (a) a staged selection survives an Uninstall — `UnifiedApp._staged` is cleared only in `_install_closed` (`installer/wizard_app.py`), so a tool removed in Uninstall comes back to the catalog still selected for install; (b) an "already current" tool (wezterm) is selectable but there is no way to reinstall/repair it from the catalog — the run reports "already" and does nothing, and the terminal sync does not re-run (see 999.4).
**Also (ponytail audit F4, probe-confirmed, must fix):** inside Uninstall a removed tool stays selected and is counted again — the next confirm says "Removed 2 tool(s)" for one, a miscount on a destructive confirm. See `.planning/research/2026-10-11-ponytail-audit.md`.
**Cross-review (GPT-6.1-sol AR-09/AR-10):** selection is a set of ids, not a reviewed action plan; make it a plan with per-tool dispositions and outcomes, reconciled after every mutation (install AND uninstall), and trigger configuration follow-ups (terminal sync) from the plan, not from incidental `installed` outcomes.
**Before planning:** run /gsd-discuss-phase first to confirm what Phase 14 already covers and drop the overlap; the preserved plans assume pre-Phase-12 architecture (`status_coordinator`, `updates.py`), so treat them as intent, not as an executable plan.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 20 and 21 (v0.50.0)

### Phase 999.2: Installer receipts as direct-artifact ownership proof: record what this installer wrote (artifact path + checksum/receipt) so ownership of a script/download-installed tool is proven by a receipt instead of inferred "by elimination" (BACKLOG)

**Status (2026-11-16):** completed by Phases 19 and 22 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). `installer/receipts.py`; 19-VERIFICATION STATE-03, 22-VERIFICATION LIFE-01/03; tests/test_receipts.py passes at HEAD.

**Goal:** [Captured for future planning]
**Source:** abandoned branch `feat/catalog-reliability-scope-reduction` (`installer/receipts.py` / `ReceiptStore`); plan text preserved in `999.2-*/source/`. Phase 16 resolves ownership from the filesystem and never considered receipts (no mention in 16-CONTEXT/RESEARCH); `rg ReceiptStore` = 0 hits in HEAD.
**Before planning:** decide whether Phase 16's filesystem-only attribution already makes this unnecessary; high conflict risk with `installer/ownership.py`, so evaluate after Phase 16 ships and its human UAT passes.
**Also covers (2026-10-10 real-host audit):** a `script` install is not removable from the Uninstall screen (`uninstall.plan_uninstall` plans only download/app kinds). kitty's `installer.sh` writes `~/.local/kitty.app`, the `~/.local/bin/kitty`/`kitten` symlinks and desktop files, and nothing records them. A receipt (or a registry-declared removal manifest) is the missing removal path. Until then the row says "installed by its own installer".
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 19 and 22 (v0.50.0)

### Phase 999.3: Registry can express a different artifact per OS and per arch: a `.dmg`/cask on macOS vs a vendor script or tarball on Linux, distinct per-arch assets, without bending an unrelated method kind (BACKLOG)

**Status (2026-11-16):** completed by Phase 18, narrowed with no new method kind (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 18-VERIFICATION REG-09; `app`/`tarball` take os/arch and `{ver}`; `installer/cargo_distrobox.py` shipped in Phase 24. The brew Intel macOS method is tracked in 999.15.

**Goal:** [Captured for future planning]
**Source:** 2026-10-10 real-host audit (kitty: cask on macOS, `installer.sh` on Linux; tools shipping distinct per-OS/arch artifacts not behind a script). `Method` carries `os`/`arch` params, but a per-platform artifact that is neither a `github_release` asset pattern nor a script has no method kind.
**Before planning:** inventory which of the 90 entries already fake this with multiple methods, and research vendor artifact shapes per OS/arch before designing any schema change; `.claude/skills/tool-onboarding/SKILL.md` step 3 routes such tools here.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 18 (v0.50.0)

### Phase 999.4: Terminal shell sync follow-ups: export `SHELL` to the configured zsh inside kitty/WezTerm, and re-run the terminal sync when an install run reports the terminal as "already" present (BACKLOG)

**Status (2026-11-16):** completed by Phases 20 and 23 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 23-VERIFICATION CONF-05; `installer/session.py:374` runs the `terminal_sync`/`zshenv_shell` steps; the zshenv tests pass. A real-terminal look stays a human item in 23-VERIFICATION.

**Goal:** [Captured for future planning]
**Source:** 2026-10-10 real-host audit. Inside kitty the prompt is zsh but `echo $SHELL` prints `/bin/bash`: there is no `chsh` (by design, Phase 15.6), and `installer/terminal_shell.py` sets kitty `shell`/WezTerm `default_prog` without `env SHELL=` / `set_environment_variables`. The sync runs only when `Summary.installed` is non-empty (`_install_state_changed`), so selecting an already-present wezterm never re-applies it.
**Before planning:** decide whether `SHELL` should be set at all (tools that read `$SHELL` to spawn subshells) and whether the "already" re-sync belongs to 999.1's dispositions.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 20 and 23 (v0.50.0)

### Phase 999.5: Finish the tool-onboarding skill revision with skill-judge: score `.claude/skills/tool-onboarding/SKILL.md` and apply its findings so the skill is well defined (BACKLOG)

**Status (2026-11-16):** completed by Phase 24 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 24-VERIFICATION ONB-03, `24-SKILL-JUDGE.md`, 0fcea8d3 (judge before and after). The rule to re-run skill-judge on every skill edit stays.

**Goal:** [Captured for future planning]
**Source:** user request 2026-10-10 after the skill was generalized in 41d642c (research-first, per-OS/arch artifacts, customization questions, "the skill cannot promise what the platform does not do"). The rewrite was never evaluated.
**Before planning:** run the `skill-judge` skill as the LAST step of any change to this skill (now and in future revisions); act on low-scoring dimensions (knowledge delta, NEVER list, description triggers, freedom calibration) without adding promises the platform cannot keep — anything that needs a missing capability stays routed to 999.2/999.3/999.4.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 24 (v0.50.0)

### Phase 999.6: One row-state model instead of three disagreeing classifiers, plus the earlier-phase promises the 2026-10-10 audit found unmet (BACKLOG)

**Status (2026-11-16):** completed by Phases 19 and 21 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). `ToolState` at `installer/version_status.py:1019`; 19-VERIFICATION STATE-01..07, 21-VERIFICATION UI-01..03.

**Goal:** [Captured for future planning]
**Source:** 2026-10-10 real-host report ("siguen los mismos vicios, es como que no se reusan los componentes") and the ponytail audit of it.
**Root cause (NOT fixed):** three independent classifiers answer "what is this tool on this host" and disagree for script-kind installs: `installer/status.py` `is_installed` (catalog ✓), `installer/ownership.py` `resolve_ownership` (Owner column) and `installer/uninstall.py` `plan_uninstall` (Uninstall, download/app kinds only). kitty via `installer.sh` reads ✓, Owner "own installer", and Uninstall MANAGED/"package manager". 9050446's `_own_script_install` only patches the wording (a special case in `removal_hint`/`removal_label`); remove it once one shared row-state answers all three screens.
**Second structural risk (mitigated, not removed):** `VersionRefreshService` has one global ownership epoch but every refresh pass is tier-scoped. Any invalidate blanks every tier; only the visible one is refilled. 9050446 makes each catalog re-resolve on entry (the base tier never did), but an Uninstall row for a tool whose tier was not revisited still shows the generic hint until then (15.4-05 calls this best-effort).
**Earlier promises found unmet, by phase:**
- 15.4 goal: "both screens re-derive on entry so an install, update or removal is never hidden" — only install→Uninstall was built and verified; removal→catalog ✓ and the base (system) tier's `enter_view` were missing since Phase 2's `show_view`. Fixed in 9050446; the 15.4 VERIFICATION passed it anyway.
- 15.4 D-04/D-05 and 16 goal ("names whichever manager owns it; when it cannot be uninstalled the row says why"): script installs had no truthful Uninstall answer. Wording fixed in 9050446; removal still impossible (999.2).
- 15.6 goal (kitty/WezTerm open into zsh): works, but `$SHELL` stays `/bin/bash` and "already" outcomes never re-sync (999.4).

**Process gap to fix with it:** verifiers checked each screen's claim, not each direction of a refresh contract, so a half-built "re-derive on entry" passed twice. Require a per-view, per-direction test (install, update, uninstall; every tier including the base) for any refresh promise.
**Deepened by the ponytail audit (`.planning/research/2026-10-11-ponytail-audit.md`):** F6 — SEVEN places answer "is it here / who owns it / can we act" and disagree (a skill pack is ✓ in the catalog and "not installed" in Uninstall). F9 — one global ownership epoch, tier-scoped passes, THREE refresh owners and duplicate manager queries. F10 — the three tier screens are already one class (`CatalogScreen`), but `UnifiedApp` treats the base tier differently in 5 places (`show_view`, `_navigable`, `get_default_screen`, `_pending_status` stash, …); target: every view pushed the same way from an empty root. Order: one `ToolState` (F6) first, then one refresh owner (F9), then one `RowsScreen` (999.10) — otherwise a base class just moves the classifiers into one file.
**Cross-review (GPT-6.1-sol, `.planning/research/2026-10-11-architecture-review-gpt-6.1-sol.md`):** AR-03 agrees with F6/F8 and deepens it: the shared state must hold multiple observed installations (shadowed copies) and per-harness skill presence, not one owner + one boolean; `installer/platform.py` treats mutable facts (manager availability) as platform constants frozen at startup (NEW). AR-04 (verified at `installer/version_status.py:751`): a refresh pass superseded by an invalidate still merges its obsolete `statuses` into `_statuses` — only ownership is discarded (NEW); also separate in-memory invalidation from cache persistence success. Disagrees with ponytail F15: worker cancellation cannot replace generation/epoch checks (cancellation and host-state supersession are different events).
**Before planning:** /gsd-discuss-phase — decide whether the shared row-state lives in `status.py` or a new owner, and how it absorbs 999.2 receipts.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 19 and 21 (v0.50.0)

### Phase 999.7: Phase 16 verification debt left open at close (BACKLOG)

**Status (2026-11-16):** partial (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). Done: CI green (17-VERIFICATION CI-01/03); CI-02 branch protection, via 26-VERIFICATION HOOK-05 and a live read-back (enforce_admins true, strict, both contexts); the owner-on-every-tier and ✓-cleared re-check (24-UAT tests 2-4). Left: 16-UAT tests 2-4 (live Execute enter on an already-current tool, a day-to-day dangling-shim session, the owner's review of the 11 prohibitions), a formal review of 9050446, and a local macOS run. Owner decision: run them, or close them on later-phase coverage.

**Goal:** [Captured for future planning]
**Source:** Phase 16 closed on 2026-10-10 by user decision with these unproven:
- 16-UAT tests 2-4 recorded as deferred follow-ups, not passes: Execute-screen enter on the real host with an already-current tool; a day-to-day catalog/Doctor session with the dangling pnpm shim (puppeteer); review of the 11 judgment-tier prohibitions.
- 9050446 (base-tier `enter_view`, installed-map re-derive on every catalog entry, script removal wording) did not get the formal `/gsd-code-review` or a Nyquist re-audit; only fail-first tests, the full suite and `make validate`.
- **`main` is RED (do first).** CI (`.github/workflows`, push to `main` only) never ran on the 599 branch commits; the first run, 38099159090 on 9a1c663, failed on both OSes. None of the failures touch 9050446's files. ubuntu: `tests/test_shellrc.py::test_reserved_word_prefixed_source_forms_execute_and_are_refused[time-shells0]` (`time .` under the runner's `/usr/bin/sh`). macOS: `tests/test_prune_tmp_linux_sh.py` x6 (bash 3.2 has no `mapfile`; the Linux-only script runs on macOS), `tests/test_app.py` x2 (long tmp paths wrapped in the console output), `tests/test_setup.py::test_interactive_wizard_shares_one_cache_with_the_daemon_policy` (StopIteration), `tests/test_version_status.py::test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record` (timing-dependent race test). Correction (GPT-6.1-sol AR-05, verified): `.github/workflows/ci.yml` triggers on push to `main` AND on `pull_request`; CI never ran because Phase 16 merged locally without a PR, and branch pushes have no trigger. Prevention: require the PR check (branch protection) or add a branch-push trigger, and make tests deterministic per platform (bash 3.2, console width, `/usr/bin/sh`, no timing races).
- macOS never run locally.
- A real-host re-check that the reported symptoms are gone (Owner on every tier after an install, ✓ cleared after Uninstall) has not been done.

**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 17 and 24 (v0.50.0)

### Phase 999.8: Per-method uninstall spec: each install method declares how it is removed on its OS/arch (manager remove, vendor uninstaller/script, or the exact paths it wrote), what config/data it leaves, and the removal policy (keep config by default, delete all, or ask), replacing today's generic Uninstall (BACKLOG)

**Status (2026-11-16):** completed by Phase 22 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). `plan_removal`/`remove_proven` in `installer/uninstall.py:255,589`; 22-VERIFICATION LIFE-01/03/04, UI-04; test_a_recipe_tool_is_removed_by_its_vendor_command_first passes. Per-entry footprints are tracked in 999.14.

**Goal:** [Captured for future planning]
**Source:** user direction 2026-10-11: onboarding must know how each tool is removed per OS/arch (e.g. kitty: cask on macOS, `installer.sh` on Linux with `~/.local/kitty.app` + `~/.local/bin` links + desktop files), with a verifying removal script or a keep-config / delete-all choice, or a silent documented default — never a generic uninstall. Today `Tool.uninstall` is one free-text hint (3 of 90 tools set it) and `installer/uninstall.py` `plan_uninstall` treats download/app kinds generically.
**Evidence (2026-10-11 ponytail audit, `.planning/research/2026-10-11-ponytail-audit.md`):** F1 — Uninstall calls a tool removable when a file with the expected name exists: it would delete a `uv tool` ruff symlink; `drawio-desktop` and `drawio-cli` share one file so removing one removes the other; `make uninstall --yes` deletes them all without asking. F7 — install and uninstall compute paths with different formulas (Sublime on Linux reports "Removed" and leaves `~/.local/opt/subl`).
**Proposed design (2026-10-11, to confirm in discuss-phase):** removal lives on the METHOD, not on the tool and not as separate per-OS/arch knobs. A method is already scoped by `os`/`arch`, so its removal inherits that split for free (kitty: the macOS `cask` method and the Linux `script` method each carry their own removal). Three levels, so onboarding writes the minimum:
1. **Derived from the method kind — nothing written:** `brew`, `cask`, `apt`, `dnf`, `pacman`, `uv-tool`, `node` (manager remove), `sdkman` (`sdk uninstall <candidate>`). The skill only verifies the derivation is right for the tool.
2. **Derived from the method's own params — nothing written, but it needs one shared path formula and proof:** `github_release`, `tarball`, `app` remove exactly the path the install computed (`bin_dir` + `bin_name` / `app`). Today install and uninstall use different formulas (ponytail F7) and a name match counts as proof (F1); fix both, with a 999.2 receipt as the proof.
3. **Explicit recipe on the method — only where the kind cannot know:** `script` (vendor installers write paths we do not choose; kitty `installer.sh` → `~/.local/kitty.app`, `~/.local/bin/kitty`/`kitten`, desktop files) and `host_setup`. The recipe is the vendor uninstaller, the exact path list, or a verifying removal script.

Tool-level, shared by all its methods: config/data paths (an optional per-OS variant when they differ, e.g. `~/Library/...` on macOS) and the default config policy (`keep` default for user-edited config / `delete` / `ask`). `skill_pack` keeps its own `skill_lifecycle` removal.
**At removal time the method that ACTUALLY installed the tool decides,** not the registry's preferred one: the ownership resolver (+ 999.2 receipt) picks it. If the real owner is a manager the installer did not use (registry says `script`, user installed with brew), delegate to that manager or show its hint; never run another method's recipe.
**Registry scan (2026-10-11):** 76 of 90 tools have at least one non-manager method (github_release 89 methods, script 16, app 7, tarball 5, sdkman 5, skill_pack 7, host_setup 1) — level 3 needs explicit recipes only for the 16 `script` methods + 1 `host_setup`. 13 tools carry >2 method kinds (rg, jq, git, zsh, watch, docker, podman, opencode, vscode, sublime, kitty, wezterm, alacritty) — each method needs its removal checked. Shared-artifact case that breaks one-tool-one-path: `drawio-desktop` and `drawio-cli` share cmd/bin `drawio`; removal must refuse (or remove both, by explicit user choice) while the other is installed. Only `pi`, `drawio-desktop`, `drawio-cli` set today's free-text `uninstall` hint.
**Before planning:** /gsd-discuss-phase. Decide the schema (per-method `remove` block: kind, paths/command, config paths, default policy, prompt) together with 999.2 receipts (proof of what we wrote) and 999.3 per-OS/arch artifacts; the onboarding skill step 4b already records the researched recipe per tool until this lands. F1 is a data-loss risk: consider fixing the "a matching name is proof" check before the schema work.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 22 (v0.50.0)

### Phase 999.9: Correctness and data-safety fixes from the 2026-10-11 ponytail audit not covered by another item (BACKLOG)

**Status (2026-11-16):** completed by Phases 17 and 21 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). Shell rc and tweak writes go through `atomic_write_text` (`installer/shellrc.py:304,317`); 17-VERIFICATION SAFE-04/09; 21-VERIFICATION UI-05/06/07.

**Goal:** [Captured for future planning]
**Source:** `.planning/research/2026-10-11-ponytail-audit.md` (ponytail-audit at ultra level, Opus). Findings marked probe-confirmed were reproduced headless by the auditor; the rest come from reading code and must be re-verified when planned.
- **F5 — must fix, data loss:** `~/.zshrc`, `~/.bashrc`, `~/.myshellrc` are written non-atomically in 3 modules (bypassing the project's atomic-write helper, `installer` `atomic_write_bytes`); a full disk can leave them empty. `clean_rc_duplicates` deletes lines by indices read before the confirm prompt, so an edit in between shifts which lines are deleted.
- **F2 — must fix (probe-confirmed):** under `make doctor` / `make fix` / `make uninstall` / `make guard`, Enter in a catalog silently exits the app and installs nothing — those routes never wire `ExecuteInputs`, and a test pins the behavior. Wire execute on every route (target: execute required).
- **F3 — must fix (probe-confirmed):** Policies never re-reads state on entry: after Uninstall removes the pip/npm ban, Policies still shows it ON and the next space runs the wrong verb (re-removes). Instance of 999.6's per-view, per-direction refresh rule.
- **F8 — should fix:** policy prerequisites are frozen at startup; after installing `watch`/`uv`, Policies still refuses the tweak that needs it.
- **F16 — nice to have:** Uninstall deletes files on the event loop; a VS Code or Sublime tree freezes the UI. Move removal to a worker.
- **F17 — nice to have:** a hidden `a` binding in Doctor rewrites shell files, while `a` means "select all" on neighbouring screens. Drop or make explicit.
- **Cross-review (GPT-6.1-sol):** AR-01 rates filename-based deletion authority CRITICAL (same as F1, lives in 999.8). AR-02 agrees with F5: shell mutation has no enforced safe-write boundary; add a preview-revision check (refuse to apply a deletion computed from an older read). AR-06 agrees with F2 and adds: installed-state re-derivation is also disabled on routes without Execute; moving `_build_app` alone is not enough if it keeps optional capability defaults.

**Fix order (auditor's verdict):** F1+F5 (data loss; F1 lives in 999.8) → F2, F4 (999.1), F3 → F7 (999.8), F8 → make `main` CI green (999.7) before merging any of them.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 17 and 21 (v0.50.0)

### Phase 999.10: Screen component architecture and lean-up: one RowsScreen family for Catalog/Uninstall/Policies, dead code out, wiring under the type checker (BACKLOG)

**Status (2026-11-16):** completed by Phases 21 and 25 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 25-VERIFICATION passed 4/4: LEAN-01 dead policy/audit/host_setup code out; LEAN-02 `installer/compose.py` under pyright and coverage; LEAN-03 `wizard_app.py` split to 793 lines with no review ids. F15: 25-RESEARCH §1.3 kept the remaining Message classes by decision (the epochs stay, AR-04).

**Goal:** [Captured for future planning]
**Source:** `.planning/research/2026-10-11-ponytail-audit.md` section "Screen component architecture" + F10–F15; user direction 2026-10-11: the System/User/AI install screens must be one component, Uninstall the same family (removable-here first, then managed elsewhere, then nothing to do), Policies/Doctor built from the same blocks.
**Target (auditor's proposal, ~60 new lines in `ui_common.py`):** `AppScreen` → `RowsScreen[T]` with hooks `rows()` (read from 999.6's shared `ToolState` via `run_live`), `adapter(rows)`, `on_accept(ids)`; shared `enter_view()` after push, one app-level state-refreshed signal, selection pruned when a row stops being selectable, status cleared on leave. `CatalogScreen` (all tiers, Enter → Execute always wired), `UninstallScreen` (rows ordered: proven-ours removable → managed elsewhere with owner + removal text → not installed/unavailable; removal on a worker), `PoliciesScreen` (live `is_active`/prerequisites; ToolBrowser with activate-on-space). Doctor stays a text report but uses the same entry/refresh path. Modals: one `ChoiceModal` + one `ConfirmModal` (F14). Execute reads `ToolState` instead of re-classifying.
**Lean-up:** F11 — ~565 lines of agent-environment policy only tests use, `Tool.source`/`owner`/`uninstall` parsed but never read (note: 999.8 would give `uninstall` a real role), a probe that runs a binary that does not exist. F12 — `setup.py` `_build_app` holds the decisions behind F2/F6 but sits outside pyright and coverage. F13 — `wizard_app.py` does several jobs; ~35% is comments and 71 review IDs record review history instead of structure. F15 — seven `Message` classes + generation counters re-implement Textual's worker API.
**Estimated effect:** ≈2,100 production lines removed (≈900 of them comments), ≈150 added, ≈740 dead test lines removable, no new dependencies — estimate only.
**Cross-review (GPT-6.1-sol AR-08/AR-11/AR-12):** agrees shared chrome does not give a shared lifecycle and that tests freeze shape (source-count assertions, private-map assertions, registry prose tests) while one behavioral test pins the F2 silent exit; qualifies it — private access is fine when it protects a safety invariant; rewrite tests as contracts that survive a storage redesign. AR-12 confirms unreachable policy code and aspirational metadata (F11).
**Before planning:** depends on 999.6 (`ToolState` and one refresh owner first). Tests coupled to private attributes/source text may need rewriting with the move; keep behavior tests per view and per direction.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 21 and 25 (v0.50.0)

### Phase 999.11: Onboard herdr and re-onboard Alacritty through the tool-onboarding skill (install AND removal per OS/arch, no-reboot path on Bazzite, user customizations) (BACKLOG)

**Status (2026-11-16):** completed by Phases 23 and 24 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). registry.toml alacritty and herdr entries; 24-VERIFICATION ONB-01/02/06/07; 24-UAT tests 6-8 pass.

**Goal:** [Captured for future planning]
**Source:** user request 2026-10-13. Neither tool had a phase: herdr is absent from the registry; Alacritty entered outside any phase (commit 102c83e, 2026-10-09) before the skill gained steps 4b (removal) and 7 (customizations).
**herdr (research 2026-10-13):**
- Official: github.com/herdrdev/herdr, docs herdr.dev/docs/install. Latest v0.9.3 (2026-09-29). Release assets are raw binaries per OS/arch: `herdr-linux-x86_64`, `herdr-linux-aarch64`, `herdr-macos-x86_64`, `herdr-macos-aarch64` (+ Windows zip). NO checksum file is published (50 registry `github_release` methods already ship without one; record it in the entry's comment and `verified` key).
- Other routes: Homebrew formula `herdr` (bottled 0.9.3, linuxbrew too), vendor `curl -fsSL https://herdr.dev/install.sh | sh`, mise, Nix. Self-updates with `herdr update` (an installer-owned binary would drift from the catalog's version check — decide who owns updates).
- This host: `~/.local/bin/herdr` 0.9.3, installed by hand/vendor script (no receipt). The docs give NO uninstall instructions: removal recipe must be researched (binary, `~/.config/herdr/`, session server state, linked plugins).
- Candidate methods: `github_release` raw per os/arch into `~/.local/bin` (immutable-host friendly, no reboot) and `brew` formula; tier `user` (the human drives it), category terminal/multiplexer.
- **User customization (step 7, ask before applying) — extracted from the user's repo `castocolina/herdr-setup` (MIT, single commit 2b5ca2a, 2026-10-09, plugin v0.3.0, `min_herdr_version = "0.9.0"`, platforms linux/macos, needs `python3`):** *(amended 2026-11-07, 24 D-22, TUNE-04: the KEEP items are herdr's install tuning, applied with no question and reverted on uninstall)*
  - **KEEP — agent separator per workspace:** `plugins/workspace-here/mark.py` lists agents (`herdr agent list`), orders them by workspace number → tab number → pane id, and sets pane metadata token `rule=────────` on the first agent of each new workspace (clears it on the rest) via `herdr pane report-metadata <pane> --source herdr-setup.markers`. Rendered by config row `[{ token = "$rule", dim = true }]` as the first row of `[ui.sidebar.agents].rows`, with `row_gap = 1`.
  - **KEEP — current indicators:** token `here=◀` on the focused workspace (`herdr workspace report-metadata`) and on the focused pane (`herdr pane current`), cleared on all others; rendered bold by `{ token = "$here", bold = true }` in both `[ui.sidebar.agents].rows` (after `state_icon`, `workspace`, `tab`) and `[ui.sidebar.spaces].rows` (after `state_icon`, `workspace`). This sits beside herdr's native focus shading.
  - **KEEP — triggers:** the manifest re-runs `mark.py` on `[[startup]]` and on events `workspace.focused`, `tab.focused`, `pane.focused`, `pane.moved`, `pane.agent_detected`, plus a manual action `mark` ("Refresh markers").
  - **OPTIONAL (offer, default off) — local-first sort:** actions `sort-native` / `sort-local` persist a mode in `$HERDR_PLUGIN_CONFIG_DIR/sort_mode`; `local` adds token `rank` (0 = current tab, 1 = current workspace, 2 = rest) and sets a custom `agent.view` over the herdr socket (`agent.view.set`, label `local-first`), which REPLACES the native grouped/priority Settings menu; `native` clears it.
  - **DROP — personal preferences, not part of the feature:** `onboarding = false`, `[theme] name = "nord"`/`auto_switch = false`, `[ui.toast] delivery = "system"`, `status_indicators = "symbols"`, the second spaces row `["branch", "git_status"]`. Offer them as separate choices, never bundle them.
  - **DROP — install mechanics:** `tools/install.sh` replaces the whole `~/.config/herdr/config.toml` (with a timestamped backup) — the installer must MERGE only the two `rows` arrays and `row_gap`, never overwrite user config; the `herdr plugin unlink ramon.workspace-here` line only migrates a legacy plugin id.
  - **Known limits to fix or record:** (1) separators are placed by the plugin's own order (pane id is compared as a string, not herdr's `pane_order`); with `agent_panel_sort = "spaces"` or the local view, a mismatch puts the rule on the wrong row — set the order explicitly or sort by `pane_order`. (2) every focus event re-runs one `herdr` CLI call per workspace, per tab list and per agent (fine for a handful, slow for many). (3) `api()` ignores the socket reply, so a failed `agent.view.set` is silent. (4) It has not been run by the installer or verified here; it was only read.
  - **Platform fit:** a `postinstall` can only select a NAMED hook from `POSTINSTALL_HOOKS`; it must not run the repo's Makefile. A hook would: place the plugin from a pinned source (vendored files or the repo at a pinned commit), `herdr plugin link <dir>`, merge the `rows`/`row_gap` keys into `config.toml` (needs a TOML-preserving merge — today the project only reads TOML), `herdr server reload-config`, and record what it wrote. Removal: `herdr plugin unlink herdr-setup.markers`, remove the `$rule`/`$here` row entries it added, and `agent.view.clear` if local sort was on.
- **Classification (decided 2026-10-13):** tier `user` (the human launches and drives it, like a terminal/multiplexer — skill step 5), `audience = "both"` (agents drive it too), category terminal/multiplexer. Three separate layers:
  1. **herdr binary → its own registry entry** (methods above).
  2. **Agent integrations → a `postinstall` hook of herdr (e.g. `herdr-integrations`), NOT separate registry entries.** `herdr integration install|uninstall|status <agent>` is herdr's own idempotent, versioned installer: agents report state through hooks (instead of screen detection) and sessions survive a herdr server restart. Supported names (herdr 0.9.3): pi, omp, claude, codex, copilot, devin, droid, kimi, opencode, kilo, hermes, qodercli, qwen, letta (experimental), cursor, mastracode, antigravity-cli, grok. Each writes one file per agent, e.g. `~/.claude/hooks/herdr-agent-state.sh`, `~/.config/opencode/plugins/herdr-agent-state.js`, `~/.cursor/herdr-agent-state.sh`, `~/.pi/agent/extensions/herdr-agent-state.ts`. Same shape as `codegraph-mcp-register`/`rtk-register`: gate on `present_agent_hosts()`, install only for hosts present, detect with `herdr integration status`, remove with `herdr integration uninstall <agent>` (this IS the removal recipe 999.8 needs). Not verified yet: whether an integration also edits the agent's main config (e.g. registering the hook in `~/.claude/settings.json`) — check before shipping (merge-safety rule). Gap: a hook runs only when herdr installs; an agent installed later (pi) would need the integration step re-run from the post-mutation plan (999.1/999.4 family).
  3. **The `herdr` skill (teaches an agent to split panes, run commands without stealing focus, read other agents' output, wait/coordinate, query agent states) → its own `skill_pack` registry entry, tier `ai`, `requires = ["herdr"]`,** like ponytail/matt-pocock-skills: source `skills/herdr/SKILL.md` in herdrdev/herdr, install `npx skills add herdrdev/herdr --skill herdr -g`, status via skills-lock probes; `herdr --skill` prints the version-matched copy. It is optional per user and per harness, so it must not be bundled into herdr's install. *(void 2026-11-02/2026-11-07: skill packs are dropped and 23.1 D-02 deletes the kind; herdr ships no skill pack, 24 D-11)*
- **This host today (`herdr integration status`, 2026-10-13):** claude current (v10), opencode current (v13), cursor current (v1); **pi not installed** although pi is in use — a direct gain from layer 2.

**Alacritty — no-reboot path on Bazzite (research in `docs/research/2026-10-09-alacritty.md`, re-checked 2026-10-13):**
- Upstream ships NO Linux binary, AppImage, .deb or .rpm; no Homebrew formula (the macOS cask is disabled since 2026-09-01, Gatekeeper); `flatpak search alacritty` empty. `rpm-ostree` layering is the only native route and needs a reboot — rejected by the user.
- No-reboot options: (a) Fedora Distrobox matching the host (`dnf install alacritty` 0.17.0) + `distrobox-export --app alacritty`, with the terminal shell pointed at the host via `distrobox-host-exec` and terminfo exported; (b) build with cargo inside that Distrobox and place the binary in `~/.local/bin` (host runtime libs suffice; desktop entry, terminfo and man pages are extra post-build steps into `~/.local/share`); (c) wait for an upstream Linux AppImage/tarball with checksum and copy WezTerm's method.
- Platform gap: the installer has NO `distrobox` method kind and `cargo` builds are out of scope, so today the row correctly says "not available: immutable host". Choosing (a) or (b) means a new method kind (install + detect + version + owner + removal: `distrobox-export --app alacritty --delete`, container removal policy) — design it with 999.3/999.8, not as a special case.
- Customizations to offer (step 7): alt/option+arrow word navigation and Cmd+K / Ctrl+Shift+K clear-scrollback bindings, shell = discovered zsh (as 15.6 does for kitty/WezTerm; Alacritty is not covered by `installer/terminal_shell.py` today). *(amended 2026-11-07, 24 D-22/D-23: written at install with no question, not offered)*

**Before planning:** run `.claude/skills/tool-onboarding` end to end for each tool and then skill-judge (999.5). Depends on 999.8 (removal spec) and, for Alacritty, on a decision about a Distrobox method kind.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 23 and 24 (v0.50.0)

### Phase 999.12: Register codegraph and graphify hooks for the copilot host (BACKLOG)

**Status (2026-11-16):** completed by Phase 24.3 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). `_CODEGRAPH_TARGETS` maps copilot to `copilot-cli` (`installer/postinstall.py:219-226`); test_copilot_codegraph_round_trip passes; graphify stays unregistered by decision. codegraph itself is being retired (todo 2026-11-14).

**Goal:** When copilot (added in 23.2) is present, the codegraph and graphify postinstall hooks register for it like the other agent hosts, are recorded in `receipt.hooks`, and unregister on removal.
**Requirements:** TBD
**Evidence (live, 2026-11-07, 23.2 analyzer):** codegraph 1.6.2's target id is `copilot-cli` (writes `~/.copilot/mcp-config.json`; `copilot` is rejected); graphify accepts `install --platform copilot`.
**Why deferred (23.2 D-22):** 23.2 TUNE-06 asks only for `recommends`; adding the host to `_CODEGRAPH_TARGETS` makes codegraph read `≈` on every machine with `~/.copilot`, a behaviour change for existing installs that needs its own spec. Phase 24.3's catalog audit may pick it up. *(amended 2026-11-07, 24.3 SPEC R9: the codegraph half is absorbed by Phase 24.3 — copilot joins `_CODEGRAPH_TARGETS` as `copilot-cli`; graphify stays unregistered because its installs are project-scoped)* *(closed 2026-11-14: absorbed by Phase 24.3 — copilot joins codegraph's hook as copilot-cli (24.3-08); graphify stays unregistered, its installs being project-scoped)*

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.13: Move Pi off the host-setup handoff to a directly installed, updatable method (BACKLOG)

**Status (2026-11-16):** completed by Phases 24.5 and 25 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). Bun method with a pnpm fallback (80331678); host_setup kind retired (04ad08b8); the Pi registry tests pass. Nit: the pi comment at registry.toml:3285 still says the vendor-script change "waits in Backlog 999.13".

**Goal:** The catalog installs, updates and removes Pi itself instead of printing a pnpm handoff: a method the installer runs with no privilege escalation (the `node` kind through pnpm with Pi's Node floor, or Pi's own installer only if it can run without `sudo`), with `pi update` or the manager's update as the update route, a receipt, and the scheduled update from Phase 24.2 following it.
**Requirements:** TBD
**Evidence (live, 2026-11-07, 24.3 analyzer):** Pi's README now leads with `curl -fsSL https://pi.dev/install.sh | sh` ("pins all dependencies and updates Pi with `pi update`"), with `npm install -g --ignore-scripts` as the alternative; that installer mentions `sudo` six times (Node install) and writes PATH profile lines. npm `@earendil-works/pi-coding-agent` latest 1.5.0, `engines.node >=22.19.0`. The registry entry is a `host_setup` handoff (`installer/host_setup.py:28-41`) whose desc "setup remains interactive" is stale. The host's Pi 1.3.0 is a bun global install. *(amended 2026-11-14, 24.3: Pi npm latest 1.5.2; pi.dev/install.sh mentions sudo 15 times; the registry text was refreshed in 24.3-06)*
**Why deferred (24.3 D-14):** Phase 24.2 D-16 builds Pi's scheduled update around the reviewed host-setup command, and 24.3's scope applies only Pi's MCP finding; changing the method there would make 24.2's path dead code. If this is promoted before 24.2 executes, amend 24.2 D-16 first.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.14: Declare the removal footprint of catalog entries that lack it: config_paths and script paths per the first catalog audit (BACKLOG)

**Status (2026-11-16):** pending (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). Only 4 of the 30 flagged ids (gh, glow, tealdeer, kitty) carry `config_paths`, all pre-dating the audit; no footprint was declared since 2026-11-13.

**Goal:** Every catalog entry the 2026-11-13 audit marked "removal recipe and paths" gets its user config, state or data directories declared (`config_paths` with the keep default, `paths` on script methods), so Uninstall lists them and a delete choice reaches them; includes the schema gaps the audit found (an absolute system path such as `/Applications/kitty.app`, a legacy `~/.wezterm.lua` one level under `~`, a per-OS `config_paths` for glow, a bun owner for a global Pi, codegraph's `~/.codegraph` after a vendor self-upgrade).
**Requirements:** TBD
**Evidence (live, 2026-11-13, first catalog audit):** `.planning/audits/catalog/2026-11-13/SUMMARY.md` Drift rows with check `removal recipe and paths` (bat, eza, zoxide, lazygit, gh, starship, oh-my-zsh, direnv, glow, xh, gitui, lazydocker, docker, colima, dive, miller, tealdeer, fx, dasel, sdkman, bun, vale, broot, vscode, kitty, wezterm, glab, graphify, pi, codegraph), each with its upstream citation and risk in `dispositions.toml`.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.15: Catalog install-method and update-route currency from the first catalog audit (BACKLOG)

**Status (2026-11-16):** pending (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). At HEAD: gron still lists github_release before brew; vale is still `errata-ai/vale`; codex has no `update`; mmdc `min_node` is still 22.12.0; the brew macOS amd64 method is still present.

**Goal:** Entries whose install method, update argv or runtime expectation drifted from the vendor's current guidance are brought current or the reason is recorded in `# Verified`: distro packages where current (eza, gum, glow, xh, difftastic, gitui, duf), a checksummed method first (gron), the vendor's apt repo or macOS pkg (docker, podman), glab's supported Linux route, the macOS Homebrew amd64 script method (brew), the `codex update` route, the vale slug, mmdc's Node floor, puppeteer's linux arm64 gate, Volta versus mise, and the daemon or machine expectation of lazydocker, docker and podman.
**Requirements:** TBD
**Evidence (live, 2026-11-13, first catalog audit):** `.planning/audits/catalog/2026-11-13/SUMMARY.md` Drift rows with checks `install method`, `update argv` and `postinstall hook` that no 24.3 commit resolved, each with its source in `dispositions.toml`.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.16: Version probe for zip reads the copyright years instead of the version (BACKLOG)

**Status (2026-11-16):** pending (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). A scratch probe at HEAD still returns `1990-2008` for zip's version output.

**Goal:** `extract_observed_version` stops reading `1990-2008` from `zip --version`'s first line and reads `Zip 3.0` from the second.
**Requirements:** TBD
**Evidence (live, 2026-11-13, first catalog audit):** script finding at `installer/versions.py:211` in `.planning/audits/catalog/2026-11-13/findings.toml`.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.17: Duplicate-code gate: pick a duplicate-code detector and add it as a quality gate with its own `make` target and pre-commit hook (BACKLOG)

**Status (2026-11-16):** pending (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). No duplicate-code target or hook exists in the Makefile or `.pre-commit-config.yaml`.

**Goal:** A commit fails when a new block duplicates existing code beyond an agreed threshold, reported by a `make duplicated-check` target that also runs as its own hook entry and through `make validate`.
**Requirements:** TBD
**Source:** owner, 2026-11-16, during the Phase 26 discussion (26 D-13). No duplicate-code gate exists: ruff does not detect duplication and pylint (which has `duplicate-code`) was ruled out on 2026-10-15.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)
