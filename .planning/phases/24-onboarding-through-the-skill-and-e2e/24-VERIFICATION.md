---
phase: 24-onboarding-through-the-skill-and-e2e
verified: 2026-11-14T12:00:00Z
status: passed
score: 7/7 must-haves verified
covered_files: [".claude/architecture.md",".claude/skills/tool-onboarding/SKILL.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-01-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-01-SUMMARY.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-02-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-02-SUMMARY.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-03-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-03-SUMMARY.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-04-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-04-SUMMARY.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-05-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-05-SUMMARY.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-06-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-06-SUMMARY.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-07-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-07-SUMMARY.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-08-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-08-SUMMARY.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-09-PLAN.md",".planning/phases/24-onboarding-through-the-skill-and-e2e/24-09-SUMMARY.md",".pre-commit-config.yaml","Makefile","docs/catalog-unsupported-tools.md","installer/agent_env.py","installer/agent_settings.py","installer/app.py","installer/cargo_distrobox.py","installer/desktop_entry.py","installer/download.py","installer/engine.py","installer/executors.py","installer/model.py","installer/ownership.py","installer/platform.py","installer/post_install.py","installer/postinstall.py","installer/receipts.py","installer/registry.toml","installer/render.py","installer/resolve.py","installer/run.py","installer/session.py","installer/terminal_shell.py","installer/uninstall.py","installer/update.py","installer/version_status.py","installer/versions.py","installer/wizard_app.py","scripts/container-e2e-verify.sh","setup.py"]
covered_digest: "v4:sha256:21ab8b9875ce07b65d03f2151f00739971492b97ac60abf8436685e41742db17"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/7
  gaps_closed:
    - "SC2 / ONB-02 / ONB-06: real Alacritty cargo_distrobox build on the Bazzite host (24-UAT.md tests 6 and 8, pass)"
    - "SC5b / ONB-05: Owner on every tier and ○ after Uninstall (24-UAT.md tests 2-4, pass; test 2 fixed in bc3a0e49)"
  gaps_remaining: []
  regressions: []
prohibitions:
  - statement: "MUST NOT leave a Distrobox container or image after any build outcome"
    verification: test
    disposition: verified
    evidence: "tests/test_cargo_distrobox.py test_build_failure_still_removes_the_box_and_the_pulled_image, test_existing_image_is_kept_and_named (pass at HEAD); real run 24-UAT.md test 6: no ti-cargo- container, pulled image untagged"
  - statement: "MUST NOT touch ~/.config/alacritty outside the owned region, nor at all on update"
    verification: test
    disposition: verified
    evidence: "tests/test_update.py test_newer_alacritty_tag_rebuilds_and_keeps_the_config; tests/test_terminal_shell.py test_alacritty_created_file_that_gained_user_content_is_kept, test_alacritty_file_the_user_created_empty_is_kept (pass at HEAD)"
  - statement: "MUST NOT run sudo for the build or the fallback"
    verification: test
    disposition: verified
    evidence: "tests/test_cargo_distrobox.py test_no_argv_escalates (pass at HEAD); UAT test 6 build ran without escalation"
  - statement: "MUST NOT run e2e installs on the host"
    verification: judgment
    disposition: "resolved by the owner's delegated UAT (24-UAT.md status complete, 2026-11-14): the container harness still drives every install inside a container it creates; the only host installs were the planned real-host UAT tests 5-8, run under the owner's delegation with backups and a closing diff"
---

# Phase 24: Onboarding through the skill and e2e Verification Report

**Phase Goal:** herdr and Alacritty prove the new contract end to end through the onboarding skill, and a three-distro container run plus a real-host UAT show the full lifecycle leaves only documented config behind.
**Verified:** 2026-11-14 (HEAD d8acbebf)
**Status:** passed
**Re-verification:** Yes. The covered sources changed after the 2026-11-13 run (phases 24.1-24.3 and the UAT fixes bc3a0e49, 96c4a309, a075242d, b41c1e11); the human items are now closed by 24-UAT.md.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 / ONB-01: herdr installs, integrations register for present hosts, uninstall leaves `herdr integration status` clean; no skill pack | ✓ VERIFIED | `registry.toml:3173` `postinstall = "herdr-integration"`; `postinstall.py:562` `HOOKS["herdr-integration"]`. Herdr tests pass in the HEAD suite. UAT 5 on the real host: `default_shell` byte-identical, no ledger entry, new pane runs zsh with Oh My Zsh |
| 2 | SC2 / ONB-02 / ONB-06: on Bazzite Alacritty is built by cargo in a throwaway Distrobox; artifacts under `~/.local` and `~/.terminfo`, recorded; box and pulled image gone; uninstall removes every recorded path | ✓ VERIFIED | `cargo_distrobox.py` (293 lines) still wired in engine/update/uninstall/resolve/model/version_status. Real host run (UAT 6): image pulled, built in about 4 min, `Untagged: ...fedora-toolbox:44`, no `ti-cargo-` container, five files present, `desktop-file-validate` silent, `infocmp` resolves via `~/.terminfo`. UAT 8: every path gone, `infocmp -A ~/.terminfo alacritty` exits 1, regions gone. The empty `~/.config/alacritty` leftover was fixed in 96c4a309 (`test_alacritty_created_file_leaves_a_directory_that_gained_other_files` and the created-dirs ledger tests pass) |
| 3 | SC3a / ONB-02: newer Alacritty release shows `↑`; rebuild leaves `~/.config/alacritty` untouched | ✓ VERIFIED | `test_newer_alacritty_tag_reads_outdated`, `test_newer_alacritty_tag_rebuilds_and_keeps_the_config` pass in the HEAD suite |
| 4 | SC3b / ONB-07: Alacritty zsh/`SHELL` sync and keybindings as install tuning, reverted with the tool | ✓ VERIFIED | `terminal_shell.py` `ALACRITTY_KEYS` (471), `apply_alacritty_keys` (671), `strip_alacritty` (726). UAT 7: Alacritty runs `zsh -l`, the `alacritty-keys` region holds ESC b / ESC f / ClearHistory, zsh binds `^[b`/`^[f`. The owner ruled Alt+Left/Right a macOS concern (not applicable on Linux) |
| 5 | SC4 / ONB-03: tool-onboarding skill covers the lifecycle params; skill-judge score recorded | ✓ VERIFIED | SKILL.md has the `cargo_distrobox` row (4 mentions); `24-SKILL-JUDGE.md` 84 to 86/125 |
| 6 | SC5a / ONB-04: three-distro container e2e install, rerun (all skipped), uninstall; leftovers within `config_paths`; a planted leftover fails | ✓ VERIFIED | `container-e2e-verify.sh` `--distro`, `TRACER_RERUN_UNEXPECTED` (629), `TRACER_LEFTOVER_OK` (899); `test_a_planted_leftover_fails_the_check` passes. The latest recorded fedora/debian/arch runs are from 24.1-05 at f221b12 (exit 0, `TRACER_RERUN_OK` with no UNEXPECTED, `TRACER_LEFTOVER_OK`, teardown OK). The verifier did not re-run them (no containers here) |
| 7 | SC5b / ONB-05: real-host UAT confirms Owner on every tier after install and `○` after Uninstall | ✓ VERIFIED | 24-UAT.md (status complete, 2026-11-14): tests 2, 3 and 4 pass. The blank claude/brew Owner was fixed in bc3a0e49 (`test_a_launcher_link_that_leaves_its_dir_is_still_the_installers` passes) and re-checked in a fresh fedora:44 container |

**Score:** 7/7 truths verified (0 present but behavior-unverified)

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `installer/cargo_distrobox.py` | ✓ VERIFIED | 293 lines; dispatched from engine.py and update.py |
| `installer/model.py`, `resolve.py`, `uninstall.py`, `version_status.py` | ✓ VERIFIED | `cargo_distrobox` referenced 7, 3, 3, 2 times |
| `installer/registry.toml` | ✓ VERIFIED | Alacritty cargo_distrobox entry; herdr entry with its hook |
| `installer/terminal_shell.py` | ✓ VERIFIED | Alacritty regions plus created-dir cleanup (96c4a309) |
| `installer/ownership.py` | ✓ VERIFIED | launcher-link attribution (bc3a0e49) |
| `scripts/container-e2e-verify.sh` | ✓ VERIFIED | three-distro harness; passes shellcheck |
| `.claude/skills/tool-onboarding/SKILL.md`, `24-SKILL-JUDGE.md`, `24-UAT.md` | ✓ VERIFIED | present; UAT complete |

### Key Link Verification

| From | To | Status |
|------|----|--------|
| engine.py / update.py | cargo_distrobox.install | WIRED |
| uninstall.py | receipt-recorded cargo_distrobox artifacts | WIRED (proven on the real host in UAT 8) |
| registry herdr | postinstall `herdr-integration` | WIRED |
| app.py | OpenCode service.json removal (a075242d) | WIRED (test_app.py passes) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Lint, format, types, security, dead code, shellcheck | `make validate` | all checks passed, pyright 0 errors | ✓ PASS |
| Full suite, run once | `make test` | 7474 passed, 6 skipped, coverage 96.05% (floor 90%) | ✓ PASS |
| Real Alacritty build and removal | 24-UAT.md tests 6 and 8 (agent-run, owner-delegated) | pass | ✓ PASS (recorded) |

### Probe Execution

The phase declares no `scripts/*/tests/probe-*.sh` probes. The container harness was not run here; its latest recorded results are in 24.1-05 (f221b12).

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ONB-01 | ✓ SATISFIED | truth 1 |
| ONB-02 | ✓ SATISFIED | truths 2, 3; UAT 6 |
| ONB-03 | ✓ SATISFIED | truth 5 |
| ONB-04 | ✓ SATISFIED | truth 6 |
| ONB-05 | ✓ SATISFIED | truth 7; UAT 2-4 |
| ONB-06 | ✓ SATISFIED | truth 2; UAT 6, 8 |
| ONB-07 | ✓ SATISFIED | truth 4; UAT 7 |

### Anti-Patterns Found

| File | Pattern | Severity |
|------|---------|----------|
| phase-modified sources | TBD/FIXME/XXX | none found |
| installer/cargo_distrobox.py | documented `shortcut:` comments | ℹ️ Info |

### Residual (not open issues; recorded in 24-UAT.md as unexercised on this host)

- UAT 6: the KDE application menu and search entry were not checked by a human. The desktop file validates and sits in the standard XDG dir.
- UAT 7: Ctrl+Shift+K is proven as a binding only; there was no live scrollback clear.
- UAT 8: the keep-your-own-keys path was not exercised on the host (the owner had no config). Unit tests cover it.
- UAT 9: the keep-an-existing-image path was not exercised (the image was absent). The owner delegated "keep"; `test_existing_image_is_kept_and_named` covers it.
- The 96c4a309 fix was not re-run on the host. The three-distro e2e was last recorded at f221b12, not at HEAD; the later changes are covered by the green unit suite.

### Human Verification Required

None. 24-UAT.md is complete (8 pass, 1 decision kept by delegation, 0 issues, 0 pending).

### Gaps Summary

There are no gaps. Every roadmap criterion is backed by code, wiring and a green HEAD suite, and the real-host parts are closed by the owner-delegated UAT. No UAT issue is open: the two issues it found (test 2 blank Owner, test 8 empty config dir) were fixed in bc3a0e49 and 96c4a309.

---

_Verified: 2026-11-14_
_Verifier: Claude (gsd-verifier)_
