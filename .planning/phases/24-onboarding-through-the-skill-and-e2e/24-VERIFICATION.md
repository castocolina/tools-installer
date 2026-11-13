---
phase: 24-onboarding-through-the-skill-and-e2e
verified: 2026-11-13T00:00:00Z
status: human_needed
score: 5/7 must-haves verified
covered_files: [".claude/architecture.md", ".claude/skills/tool-onboarding/SKILL.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-01-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-01-SUMMARY.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-02-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-02-SUMMARY.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-03-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-03-SUMMARY.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-04-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-04-SUMMARY.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-05-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-05-SUMMARY.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-06-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-06-SUMMARY.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-07-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-07-SUMMARY.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-08-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-08-SUMMARY.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-09-PLAN.md", ".planning/phases/24-onboarding-through-the-skill-and-e2e/24-09-SUMMARY.md", ".pre-commit-config.yaml", "Makefile", "docs/catalog-unsupported-tools.md", "installer/agent_env.py", "installer/agent_settings.py", "installer/app.py", "installer/cargo_distrobox.py", "installer/desktop_entry.py", "installer/download.py", "installer/engine.py", "installer/executors.py", "installer/model.py", "installer/ownership.py", "installer/platform.py", "installer/post_install.py", "installer/postinstall.py", "installer/receipts.py", "installer/registry.toml", "installer/render.py", "installer/resolve.py", "installer/run.py", "installer/session.py", "installer/terminal_shell.py", "installer/uninstall.py", "installer/update.py", "installer/version_status.py", "installer/versions.py", "installer/wizard_app.py", "scripts/container-e2e-verify.sh", "setup.py"]
covered_digest: "v4:sha256:57b52bc5b32bf64baec91ee58f603b87d085af0e0707488e973f87f4f0a414fe"
behavior_unverified: 1
overrides_applied: 0
behavior_unverified_items:
  - truth: "SC2 / ONB-02 / ONB-06: on immutable Bazzite Alacritty is built by cargo in a throwaway Distrobox; the binary, desktop entry, icon and terminfo land under ~/.local and ~/.terminfo, recorded; the box and the pulled image are gone; uninstall removes every recorded path"
    test: "24-UAT.md tests 6 and 8 (REQUIRED): install Alacritty from the catalog on the real host, then uninstall it"
    expected: "No ti-cargo- container; the image is gone if the run pulled it (kept and named otherwise); the five paths exist, desktop-file-validate is silent, infocmp alacritty resolves; after uninstall every path is gone, infocmp fails, both owned regions are removed and the user's keys are unchanged"
    why_human: "The real podman/distrobox build never ran in automation: the nested container run recorded TRACER_NESTED_INFEASIBLE step=distrobox-create (rootless inner podman cannot set a hostname in the host UTS namespace). Only fake-runner tests exercise the argv, cleanup and placement"
prohibitions:
  - statement: "MUST NOT leave a Distrobox container or image after any build outcome"
    verification: test
    disposition: verified
    evidence: "tests/test_cargo_distrobox.py test_build_failure_still_removes_the_box_and_the_pulled_image, test_interrupt_still_removes_the_box, test_existing_image_is_kept_and_named (fake runner); real-run proof pending UAT test 6"
  - statement: "MUST NOT touch ~/.config/alacritty outside the owned region, nor at all on update"
    verification: test
    disposition: verified
    evidence: "tests/test_update.py test_newer_alacritty_tag_rebuilds_and_keeps_the_config (config digest unchanged); tests/test_setup.py test_update_route_repairs_only_a_drifted_alacritty_shell_region"
  - statement: "MUST NOT run sudo for the build or the fallback"
    verification: test
    disposition: verified
    evidence: "tests/test_cargo_distrobox.py test_no_argv_escalates; native fallback is a manual handoff (resolve.py, D-25)"
  - statement: "MUST NOT run e2e installs on the host"
    verification: judgment
    disposition: "unverified-prohibition — human review recommended (non-authoritative LLM verdict: holds; scripts/container-e2e-verify.sh drives every install through exec_root in a container it creates, and the real Alacritty build is left to the user's own UAT)"
human_verification:
  - test: "UAT 1: run order and concurrency (24-UAT.md test 1)"
    expected: "No other installer process open; tests 2-9 run one at a time, after the container runs"
    why_human: "Real-host procedure; agents never run the UAT"
  - test: "UAT 2: Owner on every tier after install (ONB-05)"
    expected: "Every installed row in system, user and ai tiers shows a non-blank owner; owned-elsewhere tools show that owner; any 'owner unknown' recorded as an issue"
    why_human: "ONB-05 is a manual criterion on the real host"
  - test: "UAT 3: a tier with nothing installed shows ○"
    expected: "Every row of that tier shows ○ (or test marked not applicable)"
    why_human: "Real-host catalog state"
  - test: "UAT 4: uninstall one installer-owned tool (ONB-05)"
    expected: "The tool is removed and its row shows ○"
    why_human: "ONB-05 is a manual criterion; mutates the real host"
  - test: "UAT 5: herdr with a user-set default_shell (D-29)"
    expected: "default_shell unchanged, no ≈ on the herdr row, no default-shell entry in ~/.local/state/tools-installer/config/herdr.json, a new herdr pane runs zsh with Oh My Zsh plugins"
    why_human: "Real herdr server and panes on the host"
  - test: "UAT 6 (REQUIRED): Alacritty built on this host (ONB-02, ONB-06)"
    expected: "See behavior_unverified_items: no ti-cargo- box, image handled per D-19, five paths present, menu/search entry, desktop-file-validate silent, infocmp alacritty succeeds"
    why_human: "The only real cargo_distrobox build; nested automation is infeasible"
  - test: "UAT 7: Alacritty zsh shell, Alt+Left/Right word moves, Ctrl+Shift+K clears scrollback (ONB-07)"
    expected: "echo $ZSH_VERSION prints a version; Alt+arrows move by word; Ctrl+Shift+K clears scrollback"
    why_human: "The Alt+arrow byte sequences are research assumptions; only a real terminal proves them"
  - test: "UAT 8: uninstall Alacritty (ONB-06, ONB-07)"
    expected: "Every test-6 path gone, infocmp fails, no 'tools-installer terminal-shell alacritty' region left, user keys unchanged, no ti-cargo- container"
    why_human: "Depends on the real build of test 6"
  - test: "UAT 9: D-19 decision on an image the user already had"
    expected: "The user records keep (shipped) or remove (new plan)"
    why_human: "A user decision flagged 'needs confirmation' in the SPEC amendments"
---

# Phase 24: Onboarding through the skill and e2e Verification Report

**Phase Goal:** herdr and Alacritty prove the new contract end to end through the onboarding skill, and a three-distro container run plus a real-host UAT show the full lifecycle leaves only documented config behind.
**Verified:** 2026-11-13
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 / ONB-01: in a container herdr installs, its integrations register for present hosts, uninstall leaves `herdr integration status` clean; no skill pack | ✓ VERIFIED | `installer/registry.toml` herdr entry (raw github_release per OS/arch, `postinstall = "herdr-integration"`); `installer/postinstall.py` `_herdr_register`/`_herdr_unregister`, pinned sidebar plugin (separator and current indicator only); 41 herdr tests across 10 files pass. Recorded container runs (fedora, debian 13.7, arch at 46207b9, no code change since): `TRACER_HERDR_INSTALLED_OK hosts=claude,codex,copilot,cursor,opencode`, `TRACER_HERDR_STATUS_CLEAN_OK`, `TRACER_HERDR_REVERT_OK`. No skill-pack text in the skill (`rg -i "skill.pack|skill_lifecycle"` empty) |
| 2 | SC2 / ONB-02 / ONB-06: on immutable Bazzite Alacritty is built by cargo in a throwaway Distrobox, artifacts placed under `~/.local` and `~/.terminfo`, recorded; box and pulled image gone; uninstall removes every recorded path | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Code is substantive and wired: `installer/cargo_distrobox.py` (create `--no-entry --home`, clone tag, `cargo build --locked`, `tic`, stage, smoke, atomic swap, `distrobox rm --force --rm-home`, `podman rmi` only when pulled, temp dir removed in `finally`); `METHOD_PARAMS` closed set in `model.py`; engine/update/uninstall/ownership dispatch; Alacritty entry with the five artifacts. 18 fake-runner tests pass (argv order, failure and interrupt cleanup, image kept, tag validation, swap rollback, foreign binary refused, install+uninstall through the shipped entry). The real build never ran anywhere: nested run `TRACER_NESTED_INFEASIBLE step=distrobox-create`. Routed to UAT tests 6 and 8 |
| 3 | SC3a / ONB-02: a newer Alacritty release shows `↑`; selecting it rebuilds and leaves `~/.config/alacritty` untouched | ✓ VERIFIED | `version_status.py` reads the cargo_distrobox repo tag; `update.py:455` rebuilds via `cargo_distrobox.install`. Tests: `test_newer_alacritty_tag_reads_outdated`, `test_newer_alacritty_tag_rebuilds_and_keeps_the_config` (new tag cloned, receipt rewritten, config digest unchanged), `test_current_alacritty_tag_plans_skip_without_a_box`, `test_update_route_repairs_only_a_drifted_alacritty_shell_region` (R2-12) |
| 4 | SC3b / ONB-07: Alacritty gets the zsh/`SHELL` sync and the keybindings as install tuning (no question, no Policies row), reverted with the tool | ✓ VERIFIED | `terminal_shell.py` two owned regions (`alacritty`, `alacritty-keys`), `apply_alacritty_keys`, region strip on removal, alacritty(5) path order incl. `~/.alacritty.toml` (F1); `post_install = ["apply_terminal_tuning"]`; 15 terminal_shell + 5 version_status Alacritty tests (drift `≈` on the shell region only). Whether the Alt+arrow sequences work in a real terminal is UAT test 7 |
| 5 | SC4 / ONB-03: the tool-onboarding skill covers the new lifecycle params and its skill-judge score is recorded | ✓ VERIFIED | `.claude/skills/tool-onboarding/SKILL.md` step 4b: method table with a `cargo_distrobox` row, one example each for `paths`, `remove`, `update`, `writable_prefix`, `config_paths`, L1/L2/L3; TUNE-04 rule present (`rg Policies`). `24-SKILL-JUDGE.md`: baseline 84/125, final 86/125 (≥ baseline) |
| 6 | SC5a / ONB-04: container e2e install all → rerun all (all skipped) → uninstall all on Fedora, Debian, Arch; leftovers ⊆ `config_paths`; a planted leftover fails | ✓ VERIFIED | `scripts/container-e2e-verify.sh` `--distro` table, rerun gate (`TRACER_RERUN_UNEXPECTED`), leftover check, `TRACER_DISTRO_BLOCKED`; `test_a_planted_leftover_fails_the_check` passes. Recorded runs at 46207b9 (HEAD has no non-planning change since): fedora/debian/arch EXIT=0, rerun `installed=0 updated=0`, `TRACER_LEFTOVER_OK`. Not re-run by the verifier (containers forbidden here) |
| 7 | SC5b / ONB-05: a human UAT on the real host confirms Owner on every tier after install and `○` after Uninstall | ? UNCERTAIN (human) | `24-UAT.md` exists with 9 tests, all `pending`. Manual criterion by design |

**Score:** 5/7 truths verified (1 present, behavior-unverified; 1 manual)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/cargo_distrobox.py` | build/stage/swap/cleanup executor | ✓ VERIFIED | 293 lines, imported by engine.py and update.py |
| `installer/model.py` | `cargo_distrobox` in kinds and closed `METHOD_PARAMS` | ✓ VERIFIED | lines 35, 99, 494, 784 |
| `installer/resolve.py` | rank 25 (before dnf/apt/pacman), needs distrobox+podman, reason "needs distrobox and podman" | ✓ VERIFIED | `test_precedence_fixtures`, `test_unavailable_reason_alacritty_names_distrobox_and_podman` |
| `installer/registry.toml` | Alacritty cargo_distrobox entry, herdr entry | ✓ VERIFIED | lines ~3010-3100 |
| `installer/terminal_shell.py` | Alacritty regions, herdr `default_shell` | ✓ VERIFIED | wired into `setup._sync_terminals` and status |
| `installer/postinstall.py` | herdr integration hook pair + sidebar | ✓ VERIFIED | `HOOKS["herdr-integration"]` |
| `scripts/container-e2e-verify.sh` | three-distro + nested harness | ✓ VERIFIED | 1903 lines; tested by test_container_e2e_receipts.py |
| `.claude/skills/tool-onboarding/SKILL.md` | lifecycle params documented | ✓ VERIFIED | see truth 5 |
| `24-SKILL-JUDGE.md`, `24-UAT.md` | score record, UAT script | ✓ VERIFIED | present |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| engine.py / update.py | cargo_distrobox.install | `method.kind == "cargo_distrobox"` dispatch | WIRED |
| uninstall.py | receipt-recorded artifacts | L2 removal for cargo_distrobox receipts | WIRED |
| version_status.py | GitHub release tag | first github_release/cargo_distrobox repo | WIRED |
| registry herdr | postinstall `herdr-integration` | hook pair | WIRED |
| UpdateService | `setup._sync_terminals` | terminal follow-up | WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Lint, format, types, security, dead code | `make validate` | All checks passed | ✓ PASS |
| Full suite | `make test` | 6329 passed, 6 skipped, coverage 96.20% (floor 90%) | ✓ PASS |
| Real Alacritty build | containers / host | not runnable by the verifier | ? SKIP → UAT 6 |

### Probe Execution

No `scripts/*/tests/probe-*.sh` declared by the phase. The container harness was not run (forbidden for the verifier); its recorded results are in 24-08-SUMMARY.md and the tree they ran on (46207b9) is an ancestor of HEAD with no non-planning diff.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| ONB-01 | herdr user-tier binary, integrations for present hosts, no skill pack | ✓ SATISFIED | truth 1 |
| ONB-02 | Alacritty via cargo in a throwaway Distrobox; `↑` and rebuild keep the config | ? NEEDS HUMAN (real build) | truths 2, 3; UAT 6 |
| ONB-03 | skill covers lifecycle params, skill-judge scored | ✓ SATISFIED | truth 5 |
| ONB-04 | three-distro e2e | ✓ SATISFIED | truth 6 |
| ONB-05 | real-host UAT Owner / `○` | ? NEEDS HUMAN | truth 7; UAT 2-4 |
| ONB-06 | desktop entry, icon, terminfo recorded and removed | ? NEEDS HUMAN (real build) | truth 2; UAT 6, 8 |
| ONB-07 | zsh sync + keybindings | ✓ SATISFIED (code) / UAT 7 for real keys | truth 4 |

No orphaned requirements: REQUIREMENTS.md maps exactly ONB-01..07 to Phase 24.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (phase-modified sources) | - | TBD/FIXME/XXX | none found | - |
| installer/cargo_distrobox.py | 129, 190 | `shortcut:` comments (terminfo names hardcoded to Alacritty; stale `.old` restore) | ℹ️ Info | documented limits |
| 24-08-SUMMARY.md | body | "This SUMMARY is `status: in-progress`" while frontmatter says `complete` and later sections record the runs | ℹ️ Info | stale prose only |
| 24-REVIEW.md | Deferred | MR-02 (distro-owned Alacritty keeps keybindings after full uninstall), `/tmp` build size, unmeasured build time | ℹ️ Info | accepted/todo, not gaps of this phase's criteria |

### Human Verification Required

All nine tests of `24-UAT.md`, run by the user on the real host (agents never run them):

1. **Run order and concurrency** — no other installer process; tests in order.
2. **Owner on every tier (ONB-05)** — non-blank owner in system, user and ai tiers.
3. **Empty tier shows `○`** — or not applicable.
4. **Uninstall one tool (ONB-05)** — row shows `○`.
5. **herdr `default_shell` untouched (D-29)** — no `≈`, no ledger entry, new pane runs zsh.
6. **Alacritty built on this host (REQUIRED)** — the only real cargo_distrobox build.
7. **Alacritty keys** — zsh, Alt+Left/Right by word, Ctrl+Shift+K.
8. **Uninstall Alacritty** — paths and regions gone, user keys kept.
9. **D-19 decision** — keep or remove a pre-existing image.

Also flagged: the judgment-tier prohibition "MUST NOT run e2e installs on the host" (non-authoritative verdict: holds).

### Gaps Summary

No gaps. Every automated criterion is backed by code, wiring and passing tests (validate and 6329 tests green on HEAD), and the recorded three-distro runs cover ONB-04. What remains is the real-host part: the real Alacritty build (nested automation infeasible, UAT 6 REQUIRED), the real key behaviour (UAT 7) and ONB-05 (UAT 2-4).

---

_Verified: 2026-11-13_
_Verifier: Claude (gsd-verifier)_
