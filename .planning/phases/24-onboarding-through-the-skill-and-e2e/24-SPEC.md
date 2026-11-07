# Phase 24: Onboarding through the skill and e2e — Specification

**Created:** 2026-10-13
**Amended:** 2026-11-07 (Phase 24 discuss update, D-18..D-26: TUNE-04 install tuning, container-only real build, image ownership; dated markup inline)
**Ambiguity score:** 0.17 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

herdr and Alacritty prove the v0.50.0 contract end to end, onboarded through the tool-onboarding skill. A container run on three distros, plus one UAT on the real host, then show that the full lifecycle leaves nothing behind except documented config.

## Background

Scouted 2026-10-13:
- **Alacritty.** It has only `dnf`/`apt`/`pacman` methods (`installer/registry.toml:2655`).
  - The comment above the entry records why: no Linux release asset, the macOS cask is disabled, and "Distrobox is not a method kind".
  - On immutable Bazzite it is unavailable, because native kinds are skipped there.
  - The user overrode TA O5 and §9.1 on 2026-10-13. The decision: a cargo build in a throwaway Distrobox, measured at a 35 s build and a 12 MB binary with host libs resolving.
  - This host has `/usr/bin/distrobox`.
- **Script kind.** It only runs `curl URL | sh` (`executors.py:355`), so it cannot express a container build.
- **herdr.** It is not in the registry yet (999.11). Phase 23 defines its hook pair (`herdr integration install/uninstall`, `status`). *(amended 2026-11-07, 24 D-21: the pair has landed as `_HERDR_TARGETS` + `_herdr_register`/`_herdr_unregister` in `installer/postinstall.py:151-210`; herdr upstream is now v0.9.5, the host still runs 0.9.3)*
- **Onboarding skill.** It lives at `.claude/skills/tool-onboarding/` and predates the Phase 22 params (`paths`, `remove`, `update`, `writable_prefix`, `config_paths`) (999.5).
- **e2e.** Phase 22 adds the leftover listing and one Fedora run. Debian and Arch, the rerun-all-skipped pass, and the real-host UAT (999.7) are still missing.

## Requirements

1. **herdr (ONB-01)**: herdr is a user-tier binary tool whose integrations hook registers for present agent hosts using the Phase 23 pair.
   - Current: Absent.
   - Target:
     - No skill pack (user, 2026-11-02: the installer does not install skill packs).
     - Only the workspace agent separator and the current indicators are reused from herdr-setup.
     - Uninstall unregisters the recorded hosts.
   - Acceptance:
     - In a container, install leaves the integrations registered for the present hosts, and the receipt records them.
     - After uninstall, `herdr integration status` reports nothing installed.
     - No skill files are written.

2. **`cargo_distrobox` kind (ONB-02, O5)**: A new method kind with data params.
   - Current: No way to build from source.
   - Target:
     - The params are:
       - `repo` (git URL);
       - the version source (the GitHub release tag);
       - `packages` (build dependencies installed inside the box);
       - `artifacts` (box path → host path pairs).
     - The executor creates a throwaway Distrobox, builds the tag with cargo, copies the artifacts and records them in the receipt.
     - It always deletes the container and its image, on success and on failure.
     - The kind joins `METHOD_PARAMS`, the executor switch, the update path and `removal_plan` (L2 by receipt).
   - Acceptance:
     - With a fake runner, the argv sequence is create → build → copy → rm, then the image rm.
     - An injected build failure still runs both deletions and ends the row failed.
     - A real podman build of Alacritty is recorded once, with `podman ps -a` and the image list empty afterwards.
   - *Amended 2026-11-07 (24 D-19, needs confirmation):* "its image" means the image **this run pulled**. The executor checks `podman image exists <ref>` before create; an image that was already present (for example shared with the user's own distroboxes) is left in place and named in the row detail, and the image is never removed with `--force`. The fake-runner acceptance gains a case "image present before create → no image rm". The real build runs in a fresh nested container store (24 D-18), where the image is always pulled by the run, so its "image list empty" acceptance is unchanged.
   - *Amended 2026-11-07 (24 D-20):* the box is created with `--home <run temp dir>` and `--no-entry` (live `distrobox create --help`, 1.8.2.5) and removed with `distrobox rm --force --rm-home`, so cargo caches and an app-menu entry never land in the host HOME. The fake-runner argv acceptance asserts these flags.

3. **Alacritty artifacts (ONB-02, ONB-06)**: The build installs:
   - `~/.local/bin/alacritty`;
   - `~/.local/share/applications/Alacritty.desktop` (with `Exec`/`TryExec` pointing at the installed binary);
   - the icon under `~/.local/share/icons`;
   - the compiled terminfo under `~/.local/share/terminfo`.

   All of them are recorded in the receipt.
   - Current: Not installed on immutable hosts.
   - Target: The tool appears in the system menu and search. Uninstall removes every recorded path.
   - Acceptance:
     - After install, each path exists, `desktop-file-validate` passes on the entry, and `infocmp alacritty` resolves through `~/.local/share/terminfo`.
     - After uninstall, none of the paths exist.

4. **Update by rebuild (ONB-02)**: A newer Alacritty GitHub release shows `↑`, and `u` rebuilds that tag.
   - Current: No version source.
   - Target: `~/.config/alacritty` is never touched by an update.
   - Acceptance: A fake release feed with a newer tag shows `↑`. `u` rebuilds and replaces the artifacts and rewrites the receipt. A checksum of the config dir is unchanged after the update.

5. **Method precedence (decision)**: On Linux, the `cargo_distrobox` method comes first when `distrobox` and `podman` are both present.
   - Current: Native methods only.
   - Target:
     - On mutable hosts without them, the row falls back to the native package handoff (Phase 22).
     - On immutable hosts without them, the row is unavailable with the reason "needs distrobox and podman".
     - macOS stays unavailable, with the existing reason (cask disabled).
   - Acceptance: Fixtures cover immutable with distrobox → build; immutable without → unavailable with the reason; mutable without → dnf handoff; mutable with → build.

6. **Shell sync and keybindings (ONB-07)**: Alacritty joins `sync_terminal_shells` (zsh and `SHELL`, Phase 23). Its config also gets word navigation (Alt/Option + arrows) and clear scrollback.
   - Current: Not handled.
   - Target: Both are always written inside the owned region of `alacritty.toml`, can be reversed from Policies, and drift shows as `≈`. *(amended 2026-11-07, 24 D-22/D-23, TUNE-04: no Policies row — both are install tuning applied with no question and reverted with the tool. They live in two owned regions: the shell region (written by the terminal sync, follows zsh, drift shows `≈` like kitty/WezTerm/Konsole) and the keybindings region (Alacritty's own install tuning, written whether or not zsh is present; a hand-deleted keybindings region is the user's choice and raises no `≈`, 23.2 D-08). Removing Alacritty strips both regions and keeps the user's keys)*
   - Acceptance:
     - In a scratch HOME, the region holds the shell and the bindings, and user keys outside the region survive.
     - ~~Turning it off in Policies removes exactly the region.~~ *(superseded 2026-11-07, 24 D-22)* Removing Alacritty removes exactly the two owned regions; user keys outside them survive.
     - Removing the region by hand shows `≈`. *(amended 2026-11-07, 24 D-23: the shell region only; a hand-removed keybindings region shows nothing; without zsh the keybindings region is still written)*
   - **herdr (amended 2026-10-14, user request):** herdr also joins `sync_terminal_shells`. When zsh is available, new herdr panes start zsh instead of the login shell (bash on this host), so oh-my-zsh plugins load inside herdr as they do in Konsole, kitty and WezTerm.
     - Measured on herdr 0.9.3: `[terminal] default_shell` is empty by default, which means `$SHELL`, then `/bin/sh`. Here that is `/bin/bash`, and it is the root cause of omz plugins not loading in herdr.
     - Target: `default_shell = <absolute zsh path>` is written only when the key is absent. A user-set value is left alone and shows `≈` with a reason. Policies off reverts only the key the installer wrote. *(amended 2026-11-07, 24 D-22, TUNE-04: no Policies row; herdr uninstall, or zsh going away, reverts only the key the installer wrote)* After a write, `herdr server reload-config` runs; already-open panes keep their shell.
     - Acceptance: in a scratch HOME with a fake herdr and zsh on the lookup, the key is written and user keys survive. Without zsh, or with a user-set `default_shell`, nothing is written. Policies off removes exactly the key that was written. *(amended 2026-11-07, 24 D-22: herdr uninstall removes exactly the key that was written)*

7. **Onboarding skill (ONB-03)**: `tool-onboarding` documents and checks the Phase 22 params and the `cargo_distrobox` kind.
   - Current: It predates them.
   - Target: Its skill-judge score is recorded in the phase summary.
   - Acceptance:
     - The skill names every new param with an example.
     - The skill-judge report is committed, with a total ≥ the pre-change score.
   - *Amended 2026-11-07 (24 D-24, TUNE-04):* the skill also carries Phase 23.2's rule — "a new requirement is install-time tuning in the tool's postinstall unless it lies outside any install; never a Policies knob by default" — and this phase's edit keeps it verbatim; its §7 terminal bullet says the shell launch is the zsh terminal sync and keybindings are the terminal's install tuning. "Pre-change score" is a fresh skill-judge run on the skill as Phase 23.2 left it, with 23.2's after-score noted beside it. Acceptance adds: `rg -n "Policies" .claude/skills/tool-onboarding/SKILL.md` still shows the rule, and `rg -n -i "skill.pack|skill_lifecycle"` finds nothing.

8. **Three-distro e2e (ONB-04)**: The container harness runs install all → rerun all (every row skipped) → uninstall all on Fedora, Debian and Arch.
   - Current: Phase 22 runs Fedora only.
   - Target: "All" means every tool available on that distro. Leftovers after uninstall must be ⊆ the documented `config_paths`.
   - Acceptance:
     - Three recorded runs pass.
     - The rerun pass has zero non-skipped rows.
     - A planted leftover makes the run fail.
   - *Amended 2026-11-07 (24 D-25):* the installer never runs root commands, so native-kind tools (Alacritty in containers without distrobox) are handed off as `manual` on every pass. The rerun may hold only skipped or blocked rows plus `manual` rows whose tool set equals pass 1's manual set; any installed, updated, reconfigured or repaired row fails. A tool the resolver offers but that cannot run on one distro (copilot's Node floor on Debian, if its packaged nodejs is too old) is excluded through that distro's table entry and listed with its reason (24 D-26).

9. **Real-host UAT (ONB-05, manual)**: On this Bazzite host, the user confirms:
   - after install, the Owner column is filled on every tier (system, user, ai);
   - after Uninstall, the row shows `○`.

   - Current: Not done (999.7).
   - Acceptance: The UAT file records both checks as passed by the user. It is the only manual criterion.

## Boundaries

**In scope:**
- The herdr registry entry and its hook pair use (no skill pack)
- The `cargo_distrobox` kind (params, executor, update, removal); Alacritty data and artifacts; method precedence
- Alacritty in the terminal sync, and its keybinding region
- Updating the tool-onboarding skill and its skill-judge score
- Debian and Arch e2e runs; the real-host UAT

**Out of scope:**
- A persistent Distrobox or exported apps — rejected for size (2.4 GB vs 12 MB, O5)
- Other source-built tools on `cargo_distrobox` — the kind is generic, but only Alacritty is onboarded
- An Alacritty macOS build — the cask is disabled upstream, so it stays unavailable
- Neovim — Phase 24.1
- herdr workspace features beyond the separator and indicators

## Constraints

- Zero sudo. The build runs inside the box. Host writes go only to `~/.local` and `~/.config`.
- The container and image are deleted on every outcome. Nothing persists outside the recorded artifacts.
- The kind is added to Phase 18's closed `METHOD_PARAMS`. Unknown keys stay rejected.
- e2e runs only in disposable podman containers, never on the host. Only the UAT touches the host, and the user runs it.
- The real build is slow (35 s plus the image pull), so the unit tests use fake runners and the single real build is a recorded e2e step.

## Acceptance Criteria

- [ ] herdr: integrations registered for present hosts and recorded; after uninstall `herdr integration status` is clean; no skill files are written
- [ ] `cargo_distrobox` with a fake runner: create → build → copy → rm → image rm; an injected build failure still removes both and ends failed *(amended 2026-11-07, 24 D-19/D-20: image rm only when the run pulled it; `--home`/`--no-entry`/`--rm-home` asserted)*
- [ ] One real Alacritty podman build recorded; no container or image left
- [ ] The binary, desktop entry (valid), icon and terminfo are installed and recorded; `infocmp alacritty` resolves; uninstall removes all of them
- [ ] A newer release tag shows `↑`; `u` rebuilds and rewrites the receipt; the `~/.config/alacritty` checksum is unchanged
- [ ] Precedence fixtures: immutable+distrobox → build; immutable without → unavailable with the reason; mutable without → dnf handoff; mutable+distrobox → build
- [ ] The Alacritty region holds the zsh shell and the keybindings; user keys survive; Policies off removes the region; drift shows `≈` *(amended 2026-11-07, 24 D-22/D-23: two owned regions; keybindings written without zsh; removing Alacritty removes both regions; a hand-removed shell region shows `≈`, a hand-removed keybindings region does not)*
- [ ] herdr `[terminal] default_shell` is set to zsh only when zsh is available and the key is absent; a user value is untouched (`≈`); Policies off reverts only the written key *(amended 2026-11-07, 24 D-22: herdr uninstall or zsh removal reverts only the written key)*
- [ ] The tool-onboarding skill names every new param; the skill-judge report is committed with a score ≥ before *(amended 2026-11-07, 24 D-24: the TUNE-04 rule is still present; no skill-pack text)*
- [ ] Fedora, Debian and Arch e2e pass: rerun all skipped; leftovers ⊆ `config_paths`; a planted leftover fails the run *(amended 2026-11-07, 24 D-25: skipped/blocked plus pass 1's manual set)*
- [ ] UAT (manual): Owner on every tier after install, `○` after Uninstall, confirmed by the user

## Edge Coverage

**Coverage:** 29/30 applicable edges resolved · 1 unclassified (reviewed manually) *(re-derived 2026-11-07 from the edge-probe engine after the 24 D-18..D-26 amendments; the three pre-engine `unclassified` rows for R1, R2 and R6 are replaced by their categorized rows)*

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| concurrency | R1 | ✅ covered | (added 2026-11-07, engine floor) The receipt records only hosts whose `herdr integration install` succeeded; an interrupted run unregisters only recorded hosts (AC 1, 24 D-27) |
| adjacency | R2 | ✅ covered | (added 2026-11-07, engine floor) An image already present before create is the same ref as the build image: it is kept and named, never removed (AC 2, 24 D-19) |
| empty | R2 | 🧪 backstop | (added 2026-11-07, engine floor) Held-out test: an entry with an empty `artifacts` list is rejected at load; an empty `packages` list is valid (D-01) |
| ordering | R2 | ✅ covered | (added 2026-11-07, engine floor) Fixed argv order create → build → copy → rm → image rm (AC 2) |
| idempotency | R2 | ✅ covered | (added 2026-11-07, engine floor) A second install of the same tag is skipped by the receipt; each run uses a fresh collision-proof box name (AC 2, D-02, AC 9 rerun) |
| concurrency | R2 | 🧪 backstop | (added 2026-11-07, engine floor) Held-out test: an exception at any step, including an interrupt, still runs the `finally` deletions (D-02) |
| adjacency | R3 | ✅ covered | An existing `~/.local/share/terminfo/a/alacritty` from a native install is not overwritten unless the receipt records it; it is listed instead (AC 4) |
| empty | R3 | ✅ covered | No `~/.local/share/applications` dir: it is created; only files are recorded, never the dirs (AC 4) |
| ordering | R3 | ✅ covered | Artifacts are copied before the box is removed; the receipt is written after the last copy (AC 2, AC 4) |
| concurrency | R3 | ✅ covered | (added 2026-11-07, engine floor) Files are staged and placed by atomic moves; an interrupted copy leaves the old receipt and the old files (D-03, AC 4) |
| idempotency | R4 | ✅ covered | `u` with no newer tag: skipped, no build (AC 5) |
| concurrency | R4 | 🧪 backstop | An interrupted rebuild keeps the old binary until the copy swap; the old receipt stays (held-out test) |
| unclassified | R5 | ⚠ UNRESOLVED | Reviewed manually: the four precedence fixtures (AC 6) cover every host shape; the engine cannot classify it |
| adjacency | R6 | ✅ covered | (added 2026-11-07, engine floor) A user `[terminal.shell]` or `[[keyboard.bindings]]` for the same keys outside the regions: nothing is written for that region, `≈` "partial" (D-08 guard, AC 7) |
| empty | R6 | ✅ covered | (added 2026-11-07, engine floor) No `alacritty.toml` / no herdr `config.toml`: the file or `[terminal]` table is created with only the installer's lines (D-08, D-08b, AC 7) |
| ordering | R6 | ✅ covered | (added 2026-11-07, engine floor) The shell region and the keybindings region each keep their place and are replaced in place; neither writer touches the other's region (24 D-23, AC 7) |
| concurrency | R6 | 🧪 backstop | (added 2026-11-07, engine floor) Held-out test: a file changed between read and write is not overwritten (23 D-06 compare-before-commit); a failed `tomllib` re-parse rolls back |
| boundary | R7 | ✅ covered | The score is compared against the recorded pre-change score; equal passes (AC 8) |
| adjacency | R7 | ✅ covered | (added 2026-11-07, engine floor) The step 4b rewrite leaves §7's TUNE-04 rule verbatim; `rg -n Policies` still finds it (AC 8 amended, 24 D-24) |
| empty | R7 | ✅ covered | (added 2026-11-07, engine floor) The baseline is a fresh skill-judge run at the start of the phase even when 23.2 recorded a score (24 D-24) |
| encoding | R7 | ✅ covered | (added 2026-11-07, engine floor) The rule check is a plain ASCII `rg` match; the skill stays UTF-8 (AC 8) |
| ordering | R7 | ✅ covered | (added 2026-11-07, engine floor) Baseline before the first edit, final judge after the last edit (D-13) |
| precision | R7 | ✅ covered | The integer total from the skill-judge report is used; no rounding (AC 8) |
| adjacency | R8 | ✅ covered | A tool unavailable on one distro is excluded from that distro's "all" and listed (AC 9) |
| empty | R8 | ✅ covered | A distro where nothing is available fails the run as misconfigured (AC 9) |
| ordering | R8 | ✅ covered | Fixed order install → rerun → uninstall; listings taken at start and end (AC 9) |
| adjacency | R9 | ✅ covered | Tools owned elsewhere still show their owner, not blank (AC 10) |
| empty | R9 | ✅ covered | A tier with nothing installed shows `○` everywhere (AC 10) |
| ordering | R9 | ✅ covered | The UAT runs after all automated criteria pass (AC 10) |
| concurrency | R9 | ✅ covered | (added 2026-11-07, engine floor) The user runs the UAT steps one at a time with no other installer process open (24-UAT.md, AC 10) |

## Prohibitions (must-NOT)

**Coverage:** 4/4 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT leave a Distrobox container or image after any build outcome | R2 | resolved | test: the fake runner sees rm and image rm on failure; the real run lists none *(amended 2026-11-07, 24 D-19: an image the run did not pull is never removed)* |
| MUST NOT touch `~/.config/alacritty` outside the owned region, nor at all on update | R4, R6 | resolved | test: checksum and user keys unchanged |
| MUST NOT run sudo for the build or the fallback | R2, R5 | resolved | test: the Phase 22 grep stays green; the native fallback is a handoff |
| MUST NOT run e2e installs on the host | R8 | resolved | judgment: the harness refuses to run outside a container (existing guard) *(amended 2026-11-07, 24 D-18: the one real Alacritty build also runs in a disposable container, never on the host's podman)* |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.88  | 0.75 | ✓      | Two tools prove the contract; e2e + UAT |
| Boundary Clarity   | 0.80  | 0.70 | ✓      | One new kind, Alacritty only; nvim in 24.1 |
| Constraint Clarity | 0.76  | 0.65 | ✓      | Zero sudo, throwaway box, containers only |
| Acceptance Criteria| 0.84  | 0.70 | ✓      | 10 criteria, one manual |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

`--auto`: the initial ambiguity of 0.17 was under the gate, so the interview was skipped. Open decisions went to jev-fast-decision. Local Laya answered first, one call per question; all three came back at ≤0.03 confidence. TypeSafe direct (`jev-latest` → `jev-1.13.0`) then answered all three in one batch. Every answer is advisory, and the final decision is recorded below.

| Round | Perspective     | Question summary | Laya (advisory) | TypeSafe (advisory) | Decision locked |
|-------|-----------------|------------------|-----------------|---------------------|-----------------|
| auto | Researcher      | How to model the Distrobox cargo build | generic_build_kind p=0.41 (needs fallback) | generic_build_kind p=0.94 | A new `cargo_distrobox` kind with data params. The user's O5 override allows it; the script kind cannot express it |
| auto | Failure Analyst | No distrobox or podman on the host | unavailable_with_reason p=0.41 (needs fallback) | fallback_native_handoff p=0.71 | Mutable → native handoff; immutable → unavailable with the reason; the build is preferred when available (zero sudo) |
| auto | Simplifier      | Are the Alacritty keybindings asked or always applied? | always p=0.43 (needs fallback) | always p=0.87 | Always, inside the owned region; reversible from Policies *(amended 2026-11-07, 24 D-22: reverted with the tool, no Policies row)* |
| auto | Failure Analyst | Edge table and prohibitions | – | – | All resolved as covered or backstop; none dismissed |

Note: the Phase 22 SPEC lists "a distrobox kind" as out of scope for Phase 22. This phase adds it under the user's O5 decision, and it uses the Phase 22 contract (receipt, update, removal).

---

*Phase: 24-onboarding-through-the-skill-and-e2e*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 24 — implementation decisions (how to build what's specified above)*
