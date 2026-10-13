---
phase: 03-install-uninstall-tweak-lifecycle-hardening
plan: 03
subsystem: uninstall
tags: [uninstall, tweaks, sweep, sentinel, oh-my-zsh]

requires:
  - phase: 03-install-uninstall-tweak-lifecycle-hardening
    provides: omz_plugins_policy remove path; run_installs failure propagation
provides:
  - tweak_executables_present sentinel-checked predicate
  - active_tweak_ids / sweep_tweaks symmetric teardown
  - Uninstall view shell-tweaks env row
  - CLI run_uninstall tweak preview and post-confirm sweep
  - consolidated Phase 3 architecture note
affects:
  - subsequent catalog-expansion and postinstall-hooks ingest passes

actuals:
  tokens: 8000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - sweep composes Policy.remove rather than reimplementing removal
    - active = block present OR owned executable present
    - preview equals effect because sweep_tweaks calls active_tweak_ids

key-files:
  created: []
  modified:
    - installer/tweaks.py
    - installer/uninstall.py
    - installer/app.py
    - installer/wizard_app.py
    - setup.py
    - tests/test_tweaks.py
    - tests/test_uninstall.py
    - tests/test_uninstall_e2e.py
    - tests/test_app.py
    - tests/test_setup.py
    - tests/test_wizard_app.py
    - .claude/architecture.md

key-decisions:
  - "Sibling functions, not a widened plan_uninstall"
  - "sweep_tweaks composes tweak_policy/omz_plugins_policy remove closures (D-04)"
  - "Active means block present OR owned executable present"
  - "zshrc_path=None is a test affordance; production callers MUST pass the real path"

patterns-established:
  - "Uninstall env rows (#ban, #path-block, #tweaks) share _ENV_KEYS"
  - "CLI and TUI uninstall entry points read the same active_tweak_ids predicate"

requirements-completed:
  - REQ-uninstall-sweep-tweak-executables

coverage:
  - id: D1
    description: "Full uninstall via the Uninstall view sweeps helper, rc block, and Oh-My-Zsh plugins"
    requirement: REQ-uninstall-sweep-tweak-executables
    verification:
      - kind: e2e
        ref: tests/test_uninstall_e2e.py#test_uninstall_e2e_also_sweeps_tweaks_against_sandbox
        status: pass
      - kind: unit
        ref: tests/test_uninstall.py#test_sweep_tweaks_disables_every_active_tweak
        status: pass
    human_judgment: false
  - id: D2
    description: "CLI run_uninstall previews tweaks, skips the empty-state lie, and sweeps only after confirm"
    requirement: REQ-uninstall-sweep-tweak-executables
    verification:
      - kind: unit
        ref: tests/test_app.py#test_run_uninstall_previews_and_sweeps_active_tweaks
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_run_uninstall_declined_removes_nothing
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_run_uninstall_is_wired_with_bundles_and_zshrc
        status: pass
    human_judgment: false
  - id: D3
    description: "Orphaned helper without its block, and block without its helper, are each swept"
    requirement: REQ-uninstall-sweep-tweak-executables
    verification:
      - kind: unit
        ref: tests/test_uninstall.py#test_orphaned_executable_is_swept_without_its_block
        status: pass
      - kind: unit
        ref: tests/test_uninstall.py#test_block_without_its_executable_is_still_swept
        status: pass
    human_judgment: false
  - id: D4
    description: "A same-named file lacking the sentinel, and an unrelated file, survive untouched"
    requirement: REQ-uninstall-sweep-tweak-executables
    verification:
      - kind: unit
        ref: tests/test_uninstall.py#test_sweep_never_deletes_a_file_it_does_not_own
        status: pass
      - kind: other
        ref: "docker run python:3.11-alpine sweep with my-script + impostor.bak"
        status: pass
    human_judgment: false
  - id: D5
    description: "architecture.md names run_installs, omz_plugins_policy, and sweep_tweaks in one Phase 3 section"
    verification:
      - kind: other
        ref: "grep -v '^#' .claude/architecture.md | grep -c sweep_tweaks/omz_plugins_policy/run_installs"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-05
status: complete
---

# Phase 3 Plan 03: Symmetric Uninstall Teardown Summary

**A full uninstall now disables every still-enabled shell tweak through the same `Policy.remove` closures the Policies view uses, so helper executables, `~/.myshellrc` blocks, and the Oh-My-Zsh `plugins=(...)` edit leave together.**

`active_tweak_ids` is the single predicate the CLI preview, the Uninstall view's third env row, and `sweep_tweaks` all read. Ownership is the existing sentinel check, never mere existence. Task 1 landed in a prior session as `dd3e3bb`; this session executed Task 2 (CLI path, orphan case, safety boundary) and Task 3 (screen pins, architecture note, real-env gates).

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end full uninstall leaves no tweak block, helper, or plugins edit** - `dd3e3bb3a4fb2ed66955e242d36295bfb2c2906a` (feat) — completed in a prior session
2. **Task 2: The CLI path, the orphan case, and the safety boundary** - `1ceb46780ba13ecd7d41c027548b5f77c61b3612` (feat)
3. **Task 3: Real-environment gates and the consolidated Phase 3 architecture note** - `7c9205e1a7de005fdecdd3189e53c5697e7435aa` (docs)

## Deviations from Plan

None - plan executed exactly as written.

## Real-environment evidence (ONESHOT Rule 14)

**Tier 2 tmux:** Uninstall pane contains `What gets removed`. Agreement check against the real machine's `active_tweak_ids` passed (`EXPECTED=1`, `shell tweaks` present). Keys used: `5`, `q` only — never `a` and never `enter`.

**Tier 3 container:** `python:3.11-alpine` via colima/docker, repo mounted read-only.

```
before: ['my-script', 'tools-installer-wait-time', 'tools-installer-wait-time.bak']
after:  ['my-script', 'tools-installer-wait-time.bak']
sweep clean: no stray file, no orphan block, nothing else touched
```

## Self-Check: PASSED

- Task 1 prior-session commit `dd3e3bb` is on the branch
- `make validate` passed (ruff, ruff format, pyright, bandit, vulture, shellcheck)
- `make test` passed at the 90% coverage floor
- tmux agreement check and container sweep check both passed
- `.claude/architecture.md` names `run_installs`, `omz_plugins_policy`, and `sweep_tweaks`

---
*Phase: 03-install-uninstall-tweak-lifecycle-hardening*
*Completed: 2026-09-05*
