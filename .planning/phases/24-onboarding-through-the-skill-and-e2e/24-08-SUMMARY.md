---
phase: 24-onboarding-through-the-skill-and-e2e
plan: "08"
subsystem: e2e-and-uat
tags: [uat, container-e2e, nested-podman, merged-tree-gate, checkpoint]
status: complete
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
status_detail: "Task 1 done; nested recorded infeasible (UAT test 6 REQUIRED); fedora, debian and arch pass; UAT handed to the user"
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
- This SUMMARY is `status: complete` for the agent-run work (Task 1, the nested run and three passing distro runs, ONB-04 met). ONB-05 stays open until the user records the 24-UAT.md results (R2-15).
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

## Task 2 (orchestrator): nested-podman run — INFEASIBLE, UAT test 6 REQUIRED

Two runs inside the 90-minute box (2026-11-13), outer container `quay.io/podman/stable` with
`--device /dev/fuse --security-opt label=disable`, never `--privileged`:

- Run 1 (4a10274's parent, 65 s, exit 1): harness defect, `crun: executable file 'su' not found`
  (the image ships without util-linux). Fixed forward in 24-04: `4a10274 fix(24-04): install
  util-linux in the nested box so the tester helpers can su`. Only `TRACER_NESTED_TEARDOWN_OK`.
- Run 2 (4a10274, 55 s, exit 1):
  - `TRACER_NESTED_INFEASIBLE step=podman-run detail=Trying to pull quay.io/podman/hello:latest...`
  - the installer step ran: herdr, kitty and wezterm installed; Alacritty's `distrobox create` failed
    with `Error: invalid config provided: cannot set hostname when running in the host UTS namespace`
    (the image's containers.conf runs inner containers in the host UTS namespace, which an
    unprivileged outer container cannot replace). The harness printed
    `TRACER_NESTED_BUILD_FAILED` because the Summary row wraps the reason; fixed forward in 24-04:
    `53c00ee fix(24-04): read the unwrapped failure line when classifying the nested Alacritty row`,
    so this outcome now reads `TRACER_NESTED_INFEASIBLE step=distrobox-create`.
    The pulled `fedora-toolbox:44` image was untagged and deleted on the failure path (D-19 held).
  - `TRACER_NESTED_HERDR_SHELL_OK`, `TRACER_NESTED_UNINSTALL_OK`, `TRACER_NESTED_HERDR_REVERT_OK`,
    `TRACER_NESTED_TEARDOWN_OK`
  - post-run `podman ps -a --format '{{.Names}}'`: no `tools-installer-e2e-*` container.

Outcome: infeasible environment, not a product failure, so no third run (the plan allows one
network retry only). UAT test 6 is REQUIRED. D-29's container proof of herdr's `default_shell`
write and revert IS present (the installer step ran). herdr's reload-config failed as a note
(no herdr server in the container), as 24-07 designed.

## Task 3 (orchestrator): three-distro runs — fedora, debian, arch PASS

Round 1 (53c00ee/b114c1e, sequential, 2026-11-13):
- fedora: EXIT=0 in 662 s, every listed tracer, rerun `installed=0 updated=0` (24-09's fixes hold).
- debian (13.7): EXIT=1 in 410 s, `TRACER_CLEAN_INSTALL_INCOMPLETE failed=1 dependency_failed=5`:
  SDKMAN's installer needs `unzip` ("Looking for unzip... Not found"), which debian:13 lacks; java,
  gradle, maven, groovy and springbootcli failed behind it. Product failure.
- arch: EXIT=1 in 350 s, same sdkman failure plus puppeteer's postinstall "Extraction failed: no zip
  archiver is available" (mmdc failed behind it). Product failure.
- Fixes (forward, no owning 24-NN plan, so `fix(24)`): `230deea` declares `unzip` and `zip` as
  system-tier catalog tools (dnf/apt/pacman packages plus a brew formula, like zsh) and sdkman's
  `requires = ["unzip", "zip"]`; `9069f3c` adds `unzip` to puppeteer's requires. Native managers
  outrank brew, so on debian/arch without them the rows are MANUAL sudo handoffs and sdkman,
  puppeteer and their dependents read BLOCKED "needs ..." instead of FAILED. Gate 6297 passed.

Round 2 (9069f3c, sequential; fedora re-run because the catalog changed for every distro):
- debian: EXIT=0, 571 s. `DISTRO_RELEASE=debian:13.7`, `TRACER_HARNESS_READY_OK`,
  `TRACER_CLEAN_INSTALL_OK installed=61 updated=0 skipped=4 failed=0 blocked=11 manual=9`,
  `TRACER_HERDR_INSTALLED_OK hosts=claude,codex,copilot,cursor,opencode`,
  `TRACER_SETTINGS_INSTALLED_OK agents=6 keys=29`, `TRACER_COPILOT_VERSION_OK`,
  `TRACER_RERUN_OK installed=0 updated=0 skipped=65 failed=0 dependency_failed=0 blocked=11 manual=9`
  (no `TRACER_RERUN_UNEXPECTED`), `TRACER_GSD_ABSENT_OK` x3, `TRACER_UNINSTALL_OK`,
  `TRACER_LEFTOVER_OK`, `TRACER_HOOKS_UNREGISTERED_OK count=8`, `TRACER_SETTINGS_REVERT_OK keys=29`,
  `TRACER_HERDR_STATUS_CLEAN_OK`, `TRACER_HERDR_REVERT_OK`, `TRACER_REINSTALL_OK installed=61`,
  `TRACER_CONTAINER_TEARDOWN_OK`. `TRACER_DISTRO_BLOCKED` once each for mmdc and puppeteer (Node
  floor: "needs Node 22.12.0 or newer for its install method"), and for sdkman, java, gradle, maven,
  groovy, springbootcli (needs unzip/zip), oh-my-zsh (needs zsh), gnu-bash and container (macOS only).
- arch: EXIT=0, 489 s. Same tracer set; `TRACER_CLEAN_INSTALL_OK installed=60 ... blocked=11
  manual=10`, `TRACER_RERUN_OK installed=0 updated=0 skipped=64`, `TRACER_REINSTALL_OK installed=60`;
  BLOCKED: sdkman and the JVM tools, puppeteer and mmdc (needs unzip), oh-my-zsh, gnu-bash, container.
- fedora: EXIT=0, 617 s. Same tracer set; `TRACER_CLEAN_INSTALL_OK installed=68 ... blocked=3
  manual=7`, `TRACER_RERUN_OK installed=0 updated=0 skipped=75`, `TRACER_REINSTALL_OK installed=62`.
- Every run: `TRACER_HERDR_RESIDUE agent=codex key=features.hooks` (herdr's documented residue,
  D-28) and post-run `podman ps -a --format '{{.Names}}'` listed no `tools-installer-e2e-*`.

Budget: two product-fix rounds used for debian and arch (the plan's maximum), about 1 h of the 12 h
container budget. ONB-04 is met by these three runs; ONB-05 waits for the user's 24-UAT.md.

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

## Post-review re-run (orchestrator, 2026-11-13, tree 46207b9 = code-review fixes merged)

Sequential, no container left afterwards (`POST_PS: no e2e containers`):
- nested: EXIT=0 in 66 s — `TRACER_NESTED_PODMAN_OK` (the E1 probe fix: inner rootless podman runs),
  `TRACER_NESTED_INFEASIBLE step=distrobox-create` (podman's "cannot set hostname when running in the
  host UTS namespace", read from its own `Error:` line, f484ea9), `TRACER_NESTED_HERDR_SHELL_OK`,
  `TRACER_NESTED_UNINSTALL_OK`, `TRACER_NESTED_HERDR_REVERT_OK`, `TRACER_NESTED_TEARDOWN_OK`.
  The orchestrator confirmed the limit by hand in a disposable `quay.io/podman/stable` container
  (see 24-REVIEW.md, "Nested feasibility"): UAT test 6 stays REQUIRED.
- fedora: EXIT=0, 670 s; `TRACER_CLEAN_INSTALL_OK installed=68`, `TRACER_RERUN_OK installed=0 updated=0`,
  `TRACER_REINSTALL_OK installed=62`; every listed tracer present.
- debian: EXIT=0, 546 s; `installed=61`, rerun `installed=0 updated=0`, reinstall 61; mmdc and puppeteer
  BLOCKED once each by the Node floor; sdkman and the JVM tools BLOCKED (needs unzip/zip).
- arch: EXIT=0, 487 s; `installed=60`, rerun `installed=0 updated=0`, reinstall 60.
