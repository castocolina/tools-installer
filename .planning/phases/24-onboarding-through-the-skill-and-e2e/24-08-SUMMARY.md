---
phase: 24-onboarding-through-the-skill-and-e2e
plan: "08"
subsystem: e2e-and-uat
tags: [uat, container-e2e, nested-podman, merged-tree-gate, checkpoint]
status: in-progress
requires:
  - phase: 24-01
    provides: cargo_distrobox kind, Alacritty entry, Node floor
  - phase: 24-02
    provides: herdr ledgered settings, herdr config adapter
  - phase: 24-03
    provides: onboarding skill, Alacritty terminfo path amendment
  - phase: 24-04
    provides: container-e2e-verify.sh (all, nested), rerun gate, herdr probes
  - phase: 24-05
    provides: Alacritty update by rebuild
  - phase: 24-06
    provides: Alacritty terminal regions, herdr default_shell synchronizer
  - phase: 24-07
    provides: herdr catalog row, integration and sidebar standalone target
  - phase: 24-09
    provides: script download fails closed, recorded release reads current
provides:
  - "merged-tree gate: make validate and make test green on the 24-08 base"
  - "24-UAT.md: the user's nine-test real-host acceptance script"
affects: [24-08 Task 2 (orchestrator nested run), 24-08 Task 3 (orchestrator distro runs), ONB-04, ONB-05]
tech-stack:
  added: []
  patterns: []
key-files:
  created:
    - .planning/phases/24-onboarding-through-the-skill-and-e2e/24-UAT.md
  modified: []
key-decisions:
  - "UAT test 6 carries the marker rule: CONFIRM unless the nested run recorded TRACER_NESTED_INFEASIBLE, then REQUIRED; the orchestrator sets the marker after the nested run"
  - "UAT test 5 checks herdr's default_shell is untouched, no default-shell ledger entry in ~/.local/state/tools-installer/config/herdr.json, and a new pane runs zsh (D-29); the write itself is proven only in the nested container run"
  - "UAT test 6 names the exact Alacritty paths from registry.toml (icon at ~/.local/share/icons/hicolor/scalable/apps/Alacritty.svg, terminfo at ~/.terminfo/a/)"
  - "UAT test 8 checks the installer regions by the marker text `tools-installer terminal-shell alacritty`, which matches both the shell and the keys region"
  - "UAT test 9 asks the D-19 question with the shipped behaviour as the default answer"
requirements-completed: []
metrics:
  duration: "Task 1 only"
  completed: "2026-11-13"
status_detail: "Task 1 done; Tasks 2 and 3 are orchestrator container runs and remain pending"
commits: 1
plan_head_before: 2c48c82b15258315834e0e99c2c3d31d174360b5
plan_head_after: 24eaa92
actuals:
  tokens: 0
  tasks: 1
  commits: 1
---

# Phase 24 Plan 08: merged-tree gate and the real-host UAT (Task 1 of 3) Summary

**The merged phase tree is green (`make validate` exit 0, `make test` exit 0, 6293 passed) and the user has a nine-test real-host UAT script (`24-UAT.md`); the two container checkpoints (nested run, three distro runs) are the orchestrator's and are still pending.**

## Status

- Task 1 (merged-tree gate and UAT): done, commit `24eaa92`.
- Task 2 (ORCHESTRATOR, nested-podman run): PENDING. Not started by the executor (checkpoint, by design).
- Task 3 (ORCHESTRATOR, three distro runs): PENDING. Not started by the executor (checkpoint, by design).
- This SUMMARY is `status: in-progress`. Per the plan (R2-15) the plan closes only after the orchestrator's runs, three passing distro runs and the user's recorded UAT results. ONB-04 and ONB-05 stay open.
- STATE.md and ROADMAP.md were not updated, per the orchestrator's instruction.

## Task 1: merged-tree gate

| Check | Result |
| ----- | ------ |
| `make validate` | exit 0 (ruff check, ruff format, pyright 0/0, bandit, vulture, shellcheck on install.sh and the scripts) |
| `make test` | exit 0: 6293 passed, 6 skipped, coverage 96.19% (floor 90%) |

Both were run on the worktree tree that contains the UAT, before the Task 1 commit.

## Task 1: the UAT (`24-UAT.md`)

Written in the 23.2-UAT format (frontmatter, Before you start, Results table, one `###` block per test with Expected, Result and Notes, Summary block). Nine tests:

1. Run order and concurrency (R9 ordering and concurrency).
2. Owner on every tier after install (ONB-05, R9 adjacency: a tool owned elsewhere shows its owner).
3. A tier with nothing installed shows `○` (R9 empty).
4. Uninstall one installer-owned tool, its row shows `○` (ONB-05).
5. herdr (D-29): user `default_shell` untouched, no `≈`, `~/.local/state/tools-installer/config/herdr.json` holds no `default-shell` entry, a new pane runs zsh with Oh My Zsh plugins.
6. Alacritty built on this host through the catalog: no `ti-cargo-` box, image removed if this run pulled it or kept and named if it was already there, `~/.local/bin/alacritty`, the desktop entry, the icon, `~/.terminfo/a/alacritty{,-direct}`, menu and search entry, `desktop-file-validate` silent with exit 0, `infocmp alacritty` succeeds. Carries the `fedora-toolbox:44` pull notice. Marker: CONFIRM unless the nested run recorded `TRACER_NESTED_INFEASIBLE`, then REQUIRED (set by the orchestrator).
7. Alacritty: zsh shell, Alt+Left and Alt+Right by word, Ctrl+Shift+K clears scrollback (the RESEARCH A3 byte sequences are checked here).
8. Uninstall Alacritty: every test-6 path gone, `infocmp` fails, the installer regions gone, the user's own keys unchanged.
9. D-19: keep an image the user already had (shipped) or remove it (needs a new plan).

Acceptance greps (plan Task 1): `^### ` count 9 (need at least 9); `TRACER_NESTED_INFEASIBLE` count 1 (need 1); `fedora-toolbox:44` count 4 (need at least 1); `local/state/tools-installer/config/herdr.json` count 1 (need at least 1); `local/share/tools-installer` count 0 (need 0).

The UAT's facts were taken from the nine SUMMARY files: terminfo under `~/.terminfo` (24-01, 24-03 amendment), the herdr ledger under `~/.local/state/tools-installer/config/` (24-02, `receipts.config_ledger_dir`), the Alacritty paths and icon from `installer/registry.toml`, and the Alacritty region marker from `installer/terminal_shell.py`.

## Carried into the UAT as observations (not failures)

- 23.2-UAT O-8: claude may read `owner unknown` after its native installer. Test 2 tells the user to record that as an issue.
- The herdr sidebar workspace marker (24-07 standalone target) is not checked by the UAT; only `default_shell` is (per the plan).
- The Alt+arrow byte sequences (24-06, RESEARCH A3) are assumptions the UAT test 7 checks.

## Orchestrator: what remains (Tasks 2 and 3)

These are not executed by this executor. Per the plan, the orchestrator records in this SUMMARY:

- Task 2: `scripts/container-e2e-verify.sh nested` once, within 90 minutes. Record runtime, exit code, every `TRACER_NESTED_*` line (the four build lines, or `TRACER_NESTED_INFEASIBLE`, plus `TRACER_NESTED_HERDR_SHELL_OK` and `TRACER_NESTED_HERDR_REVERT_OK`), and the `podman ps -a` check. If infeasible, set UAT test 6 to REQUIRED.
- Task 3: `all --distro fedora`, then `debian`, then `arch`, one at a time. For each: runtime, exit code, the listed tracer lines (`DISTRO_RELEASE=`, `TRACER_HARNESS_READY_OK`, `TRACER_CLEAN_INSTALL_OK`, `TRACER_HERDR_INSTALLED_OK`, `TRACER_SETTINGS_INSTALLED_OK`, `TRACER_COPILOT_VERSION_OK`, `TRACER_RERUN_OK` with no `TRACER_RERUN_UNEXPECTED`, `TRACER_GSD_ABSENT_OK`, `TRACER_UNINSTALL_OK`, `TRACER_LEFTOVER_OK`, `TRACER_SETTINGS_REVERT_OK`, `TRACER_HOOKS_UNREGISTERED_OK`, `TRACER_HERDR_STATUS_CLEAN_OK`, `TRACER_HERDR_REVERT_OK`, `TRACER_REINSTALL_OK`, `TRACER_CONTAINER_TEARDOWN_OK`), Debian's `TRACER_DISTRO_BLOCKED` lines for mmdc and puppeteer, and the post-run `podman ps -a` check.
- Failure routing and the stop budget are as written in 24-08-PLAN.md Tasks 2 and 3 (network retries, two product-fix rounds per distro, 12 hours in all, forward `fix(24-NN)` commits after a push).
- If a budget is spent, set `status: blocked` and keep ONB-04 open (R2-15).

## Deviations from Plan

None for Task 1. The plan's Task 1 steps were followed as written: merged-tree gate, UAT in the 23.2 format with the nine tests, one commit with the plan's message.

## Known Stubs

None.

## Threat Flags

None. Task 1 adds one Markdown file and runs no container, no host installer command, and no podman/docker/distrobox command (the executor rules).

## Self-Check: PASSED

- FOUND: .planning/phases/24-onboarding-through-the-skill-and-e2e/24-UAT.md
- FOUND commit: 24eaa92 (ancestor of HEAD)
- `make validate` exit 0, `make test` exit 0 (6293 passed, 6 skipped) on the tree with the UAT
