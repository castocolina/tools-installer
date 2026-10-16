---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "16"
subsystem: state
tags: [tool-state, health, misconfigured, terminal-shell, pnpm, skill-packs, opengsd]

requires:
  - phase: 19-06
    provides: sync_terminal_shells(write=False) drift, incomplete_install_groups, node_install_policy
  - phase: 19-07
    provides: ConfigStep, inspect_skill_reports, partial_harnesses, partial_steps, present_harnesses
  - phase: 19-11
    provides: inspect_project_pack leftovers and unchecked paths
  - phase: 19-21
    provides: ProjectPackReport.repos and per-repo project_pack_install steps
  - phase: 19-14
    provides: receipt evidence in the pass (unchanged here)
provides:
  - terminal_drift seam on VersionRefreshService, wired in setup.py to a dry-run sync
  - pnpm co-install group facts and empty-argv pnpm_group_install steps
  - SkillHostStatus.reasons/steps and one _skill_state for pass and refresh_skills rebuild
  - project-pack presence ("installed in N repos"), leftovers and repo steps in the pack state
  - "… not checked" notes for every failed or inconclusive secondary check
affects: [19-15 catalog detail rendering, phase 20 RECONFIGURE step dispatch]

actuals:
  tokens: 13100
  tasks: 3
  commits: 4
plan_head_before: b4f41b96470e1f5531eb87612d4a8f48ff95eb18
plan_head_after: d9a8164

tech-stack:
  added: []
  patterns:
    - "_ConfigFacts per row: misconfigured facts, steps and present-only 'not checked' notes merged from independent secondary checks"
    - "_PackScan: pack inputs read once per pass outside the service lock, consumed by one _skill_state under it"

key-files:
  created: []
  modified:
    - installer/version_status.py
    - setup.py
    - tests/test_version_status.py
    - tests/test_setup.py

key-decisions:
  - "A harness whose D-18 fix already has a step (claude enable/install) is not also reported as partial, so the 4-install pack never gets a second, conflicting 'install superpowers for Claude Code' step"
  - "Pack scan (present_harnesses + inspect_project_pack) runs outside _lock in both the pass and refresh_skills, so the HOME walk never blocks invalidate or a commit"
  - "A project pack whose inspect_project_pack raised falls back to the host-answer path plus the not-checked note instead of guessing presence"
  - "'installed in N repos' is added only when N > 0; a leftover-only pack is present without that note"
  - "Terminal and pnpm 'not checked' notes go on present rows only; skill 'not checked' notes go on the pack whatever its presence"

requirements-completed: [STATE-02, STATE-06, STATE-07]

duration: 55min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 16: Misconfiguration evidence in the pass Summary

**Terminal drift from a dry-run sync, incomplete pnpm co-install groups, Claude duplicate/disabled copies, partial skill packs and opengsd project-pack gaps now turn installed-but-unwired tools into `≈` rows with the exact reason and a validated fix step, and every failed or unreadable check leaves a "not checked" note instead of a false `✓`.**

## What was built

### Task 1: terminal drift (commit ab66b0e)
- `VersionRefreshService(terminal_drift=...)`: called once per pass with the pass's live platform. `_TERMINAL_ROWS` maps `kitty`/`wezterm` to their rows and `konsole` to the `zsh` row (L-19-10). Each drifted terminal gives `{Terminal} does not start zsh` plus `ConfigStep("point {Terminal} at zsh", "terminal_sync")`.
- If the seam raises, the pass still completes. Each present kitty/wezterm/zsh row gets `terminal shell not checked: {error}`. The note never changes health (review M11).
- `setup.py` wires `sync_terminal_shells(home=Path.home(), environ=os.environ, platform=live, lookup=_which_with_brew, write=False)`.
- `test_terminal_drift_pass_writes_nothing` runs the real `main()` wiring with a scratch HOME (stale kitty.conf, kitty/zsh stubs on a scratch PATH, version cache moved out of HOME, XDG vars cleared, native probe stubbed). The kitty row reads MISCONFIGURED, and a fingerprint of every path under HOME (mode, size, mtime_ns) is unchanged (T-19-47).

### Task 2: pnpm co-install groups (commit 88bd025)
- `_pnpm_group_facts(tools, inventory.pnpm_globals)` calls `incomplete_install_groups(node_install_policy(tools), ...)` once per pass on the cached inventory, with no new query. It maps each group to the tool whose first `node` method's `npm_pkg` is `group.present[0]` (checker I6).
- Reason: `pnpm group incomplete: missing {a}, {b}`. Step: `ConfigStep("install {a}, {b} with pnpm", "pnpm_group_install")` with an EMPTY argv. Its contract, stated in a comment: Phase 20 runs `executors.execute` on the declaring tool's first node method (review H10). `test_group_step_repair_runs_the_grouped_node_install` checks that contract against the real registry mmdc: one argv `/fake/pnpm add -g --allow-build=puppeteer @mermaid-js/mermaid-cli,puppeteer@^25`, built from the method params, and the smoke check runs once.
- A missing name that fails `^[A-Za-z0-9@][A-Za-z0-9@._/-]*$` keeps its reason but gets no step. An unreadable inventory (`None`) puts `pnpm group not checked: the pnpm inventory is unreadable` on present tools that declare a group.

### Task 3: skill and project-pack evidence (commit d9a8164)
- `SkillHostStatus` gained `reasons`/`steps`. `refresh_skills` now stores `inspect_skill_reports`. The cache still persists hosts only.
- `_scan_packs` runs once per pass, outside `_lock`: `present_harnesses(self._skill_home, ...)` plus `inspect_project_pack(tool, self._skill_home, present)` for each project pack. `refresh_skills` builds the same scan for its rebuild. One `_skill_state(..., scan=)` builds every pack state, so the rebuild keeps all facts (19-08 carry-forward; `_probed_state` checks rebuild == next pass).
- User packs: the D-18 reasons and steps come first, then `partial: missing on {Harness}` / `install {pack} for {Harness}`. These count only harnesses on this machine that the D-18 fix does not already cover.
- Project packs: present when a repo has a real runtime or a global leftover exists. Note `installed in N repo(s)`. The 19-11/19-21 reasons and steps pass as `misconfigured`/`unconfigured`, so an absent pack reads MISSING with them.
- Not-checked notes (review M11, C2-M3):
  - a raising helper adds `skill configuration not checked: {exc}`;
  - a non-stale `unknown` host on a harness this machine has adds `… no readable answer from {Harness}`;
  - each `ProjectPackReport.unchecked` path adds `… cannot read ~/{path}`.

## TDD RED evidence (trimmed)

Task 1:
```
E  TypeError: VersionRefreshService.__init__() got an unexpected keyword argument 'terminal_drift'   (x7)
E  AssertionError: assert <Health.OK: 'ok'> is <Health.MISCONFIGURED: 'misconfigured'>   (setup wiring)
FAILED test_kitty_drift_is_misconfigured / test_wezterm_drift_lands_on_its_own_row / test_konsole_drift_lands_on_zsh
FAILED test_no_terminals_no_drift / test_terminal_drift_seam_runs_once_per_pass / test_terminal_drift_failure_is_a_not_checked_note
FAILED test_no_terminal_drift_seam_adds_nothing / tests/test_setup.py::test_terminal_drift_pass_writes_nothing
```
Task 2:
```
E  AssertionError: assert <Health.OK: 'ok'> is <Health.MISCONFIGURED: 'misconfigured'>
E  AssertionError: assert ConfigStep(text='install puppeteer with pnpm', kind='pnpm_group_install', ...) in ()
E  AssertionError: assert 'pnpm group not checked: the pnpm inventory is unreadable' in ('the pnpm inventory could not be read', ...)
FAILED test_incomplete_pnpm_group_is_misconfigured / test_group_step_repair_runs_the_grouped_node_install
FAILED test_unreadable_pnpm_inventory_is_a_not_checked_note / test_group_check_makes_no_extra_query
FAILED test_group_step_rejects_unsafe_names / test_group_maps_to_the_declaring_tool
```
(`test_complete_group_is_quiet` passed in RED; it guards against false positives.)

Task 3:
```
E  AssertionError: assert () == ('disabled: s...cope (6.2.0)')
E  AssertionError: assert 0 == 1   (calls.count('claude'): no present_harnesses in the pass)
E  AssertionError: assert <Health.CHECKING: 'checking'> is <Health.MISSING: 'missing'>   (opengsd)
E  AttributeError: <module 'installer.version_status'> has no attribute 'inspect_project_pack'
E  AssertionError: assert ('skill configuration not checked: no readable answer from Claude Code' in ('checking which hosts have it',)) is True
16 FAILED (partial, duplicates x2, present_harnesses, project_pack x5, seeded_skill_cache,
           skill_helper_failure x2, inconclusive_claude_listing x2, inconclusive_hook_config x2)
```

## Verify-command results

- Task 1: `pytest ... -k drift`: 9 passed (>= 6). `-k not_checked_note`: 1 passed at that commit. Truncation guard OK. `grep -c "write=False" setup.py` = 1. `grep -c terminal_drift installer/version_status.py` >= 2.
- Task 2: the `-k` selection gives 7 passed (>= 7). `grep -c "incomplete_install_groups(" installer/version_status.py` = 1. `grep -cE '"pnpm", "add"' installer/version_status.py` = 0.
- Task 3: the `-k` selection gives 21 passed (>= 16; `partial` also matches older tests). Truncation guard OK. Suppression guard 590 -> 590. `partial_harnesses(` = 1, `inspect_project_pack(` = 1, `no readable answer from` = 1, `.unchecked` = 3.
- Each commit: `make validate` exit 0 and `make test` green. Final: 4437 passed, 4 skipped, coverage 95.84%.
- `git diff fde3e68 -- pyproject.toml uv.lock`: empty. The real receipts dir is empty.

Large-file evidence (HEAD before plan -> after):
```
installer/version_status.py   1383 -> 1629   (+266 / -12 over the plan)
setup.py                      1564 -> 1572   (+8)
tests/test_version_status.py  4038 -> 4728   (test defs 117 -> 146)
tests/test_setup.py           3559 -> 3634   (test defs 120 -> 121)
git diff --stat b4f41b9 HEAD: 4 files changed, 1031 insertions(+), 12 deletions(-)
```

## Deviations from Plan

1. **[Rule 2 - correctness] No partial step for a harness the D-18 fix already covers.** With claude on the machine, the 4-install pack would otherwise get both `enable … in user scope` and `install superpowers for Claude Code`. Phase 20 would then run a second install. `test_claude_duplicates_on_a_present_pack_are_misconfigured` asserts that `unconfigured` equals the D-18 steps exactly.
2. **[Test wiring] The setup test drives `setup.main([])` with `_capture_app`, not `_build_app`.** It captures the service through a wrapper of `setup.VersionRefreshService`. Calling the private `_build_app` would have needed a new `pyright: ignore`, which the suppression guard forbids.
3. **Extra tests beyond the plan's list:**
   - `test_wezterm_drift_lands_on_its_own_row`
   - `test_no_terminal_drift_seam_adds_nothing`
   - `test_present_harnesses_failure_is_a_not_checked_note` (covers the `present_harnesses` failure branch)
   - a `None` (no settings.json) case in the hook-config parametrization
4. **Guard scripts:** the sandbox refused `bash -c '…'` and multi-command git chains. The plan's truncation and suppression guards ran as a script file in the session scratch dir (`work-19-16/guard.sh`), which was deleted afterwards.

No file outside `files_modified` was touched.

## Notes for the orchestrator

- 19-15 (parallel) owns `catalog_tui.py`. This plan adds two defaulted fields to `SkillHostStatus` and does not change the catalog. It only adds new reason, note and step strings to `ToolState`.
- The opengsd row no longer sits in CHECKING until `refresh_skills`. Its presence now comes from the per-pass project scan.
- `pnpm_group_install` and `project_pack_*` steps are built, not executed. Dispatch is Phase 20's job (L-19-28).

## Self-Check: PASSED

- installer/version_status.py, setup.py, tests/test_version_status.py, tests/test_setup.py: present and committed
- commits ab66b0e, 88bd025, d9a8164: on HEAD
