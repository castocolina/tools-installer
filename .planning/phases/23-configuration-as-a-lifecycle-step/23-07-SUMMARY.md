---
phase: 23-configuration-as-a-lifecycle-step
plan: "07"
subsystem: installer
tags: [hooks, receipts, zshenv, zsh, settings, ledger, reconfigure, drift, run-report, tdd]
status: complete

requires:
  - phase: 23-01
    provides: present_hosts, register_hooks, receipt.hooks (recorded per hook name)
  - phase: 23-04
    provides: TerminalShellResult.zsh and .paths, the managed ~/.zshenv block
  - phase: 23-05
    provides: host_labels, hook_method
  - phase: 23-06
    provides: agent_settings.setting_state and SettingsUnreadable, receipts.read_ledger, CONFIG_AGENTS
provides:
  - ConfigStepKind hook_register and zshenv_shell; ConfigStep.report
  - hook drift (≈ and RECONFIGURE) for a present, supported host the receipt does not record
  - .zshenv drift on the zsh row (≈ and RECONFIGURE exporting SHELL)
  - O7 catalog row: an unparsable settings file the ledger manages blocks its row with the reason
  - end-of-run sweep that registers installed hook tools for a newly installed agent host
  - run report sections Agent-host hooks and Shell, and multi-line RECONFIGURE done notes
affects: [23-08 (removal), 23-10 (run options), 23-11 (Policies rows), 23-15 (removal reverts), 23-16 (end-to-end)]

# Actuals (#2632): chars/4 over the realized diff (git diff 6f2c6e6..HEAD, 50555 chars)
actuals:
  tokens: 12639
  tasks: 3
  commits: 3

# Measured commit ledger (#3968): rev-list count from the plan base, taken before this SUMMARY commit
commits: 3
plan_head_before: 6f2c6e6d3dd6736105b5ed10782fdd1ac4a51fb6
plan_head_after: 683076d90682720f7e9384a3c62bd3c25c2d0734

tech-stack:
  added: []
  patterns:
    - "One host list per pass: present_harnesses is called once; the hook fact is computed from the receipt the tool loop already holds"
    - "A RECONFIGURE step's done note is a detail; its indented lines are paths printed under the note above"
    - "A failed sweep or presence read is an unchecked note or a row warning, never a failed pass or a failed row"

key-files:
  created:
    - .planning/phases/23-configuration-as-a-lifecycle-step/23-07-SUMMARY.md
  modified:
    - installer/model.py
    - installer/postinstall.py
    - installer/version_status.py
    - installer/session.py
    - installer/render.py
    - tests/test_model.py
    - tests/test_version_status.py
    - tests/test_session.py
    - tests/test_render.py

key-decisions:
  - "Hosts come from postinstall.present_hosts() only (no RunContext.harnesses); tests patch that one seam (23-REUSE 07-1)"
  - "The hook fact is computed inside the existing tool loop from the trusted receipt (no second receipts.read); present_harnesses is hoisted to one call per pass (23-REUSE 07-2)"
  - "The sweep registers only for receipts that record hooks (D-03), and only after a done install of an agent host (catalog ids of HOST_CATALOG_IDS)"
  - "A hook_register step with nothing left to register fails the row with a reason, never an empty done (review R1-34)"
  - "terminal_sync steps carry their done note as ConfigStep.report; the path line comes from locations.display_path (23-REUSE 07-3, no private tilde)"
  - "O7: the producer reads only ledger-recorded files; no ledger means no fact; one reason per file (review R1-04)"
  - "codegraph's registration warning is the first line of the command's detail, so a row failure shows the vendor's error line (see Deviation 1)"

patterns-established:
  - "RED evidence in the SUMMARY only: each task's failing run was pasted, then the tests and code were committed together as one green feat(23-07) commit"

requirements-completed: [CONF-01, CONF-02, CONF-05]  # as listed in the plan frontmatter; the phase verifier confirms against the requirement text

# Metrics
duration: unmeasured (no start timestamp recorded for this run; worktree base 6f2c6e6)
completed: 2026-11-07
---

# Phase 23 Plan 07: Hook drift, .zshenv drift, new-host sweep, and run report Summary

**A hook host the receipt misses and a missing `.zshenv` block both read `≈` with a RECONFIGURE step that fixes them; installing a new agent host registers the installed hook tools for it at the end of the run; the report lists what was registered, which terminals were reconfigured, and that `SHELL` is now exported.**

## Performance

- **Duration:** unmeasured (no start timestamp recorded)
- **Tasks:** 3 of 3, each test-first, one green commit each
- **Commits:** 3, measured against base `6f2c6e6` (`5606073`, `01413cc`, `683076d`)
- **Test counts (collected, per-file sum):** base 5644 (5640 passed, 4 skipped) → 5653 after Task 1 → 5661 after Task 2 → 5667 after Task 3 (5663 passed, 4 skipped). Delta +23 = 9 (Task 1: 7 test functions and 2 new dispatch cases) + 8 (Task 2) + 6 (Task 3).
- **make test:** base exit 0 (coverage 96.19%); after each commit exit 0 (coverage 96.18%, 96.17%, 96.17%). `make validate` exit 0 on each commit's tree.

## Accomplishments

- `installer/model.py`: `hook_register` and `zshenv_shell` join `ConfigStepKind` (ten kinds); `ConfigStep` gains `report: str = ""` (appended field).
- `installer/version_status.py`:
  - One wrapped `present_harnesses` call per pass (`_present_hosts`), shared by the pack scan and the hook fact.
  - `_hook_fact`: a present, supported host the receipt does not record reads `codegraph is not registered for codex` with the step `register codegraph for codex` (kind `hook_register`). Absent, unsupported and receiptless tools read nothing. A failed presence read is an `agent hosts not checked:` note on hook tools.
  - `_terminal_facts`: a `zshenv` drift becomes `~/.zshenv does not export SHELL as zsh` on the zsh row with the step `export SHELL={zsh} in ~/.zshenv`; a `zshenv:` warning lands on the zsh row only; terminal steps carry `{label} now starts zsh` plus the config path line.
  - `_settings_facts` (O7): a settings file the ledger records keys in, which does not parse, blocks its row with `{path} is not valid {format} ({where}); nothing is written until it parses` and no step.
- `installer/session.py`:
  - `_register_hook_step` runs `register_hooks` through the context runner; success reads `registered for {hosts}`; failure reads the first error line; nothing left is a failure with a reason.
  - `zshenv_shell` runs the synchronizer and reports `~/.zshenv exports SHELL`; `terminal_sync` reports its step's done note unless the synchronizer returned its own warning.
  - RECONFIGURE keeps every step's note, joined by newlines (no longer only the last).
  - `RowOutcome.resynced` and `RowOutcome.resync_warnings` (appended, defaults empty).
  - `_resync_hooks`: after the row loop, when a done INSTALL, REPAIR or REINSTALL row installed an agent host, one sweep registers each installed hook tool whose receipt records hooks for the present hosts it does not record. `register_hooks` subtracts the recorded hosts. A sweep failure is a warning; the row stays done.
- `installer/render.py`: multi-line RECONFIGURE done notes (indented lines print as paths); `render_resync_warnings`; `render_hook_lines` (`Agent-host hooks`); `render_shell_section` (`Shell`, last in the report).
- `installer/postinstall.py`: codegraph's registration warning carries the first line of the command's detail (see Deviation 1).

## Task Commits

1. **Task 1: unregistered hook hosts read ≈ and RECONFIGURE registers them** — `5606073` (feat; tests and code in one commit)
2. **Task 2: .zshenv drift reads ≈ and terminal done notes name the file** — `01413cc` (feat)
3. **Task 3: a new agent host gets the installed hook tools registered for it** — `683076d` (feat)

## Test-first evidence

### Task 1 RED

`uv run pytest tests/test_version_status.py tests/test_session.py tests/test_render.py -k "unrecorded_present_host or ignores_absent_unsupported or registers_the_missing_host or failed_register_step or hook_reconfigure_prints or nothing_left_fails_with_a_reason or calls_present_harnesses_once or each_config_step_kind_dispatches" -q --no-cov -n 0` → exit 1; log `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/red-23-07-task1.log`.

```
FAILED tests/test_version_status.py::test_an_unrecorded_present_host_reads_misconfigured
    AssertionError: assert <Health.OK: 'ok'> is <Health.MISCONFIGURED: 'misconfigured'>
FAILED tests/test_session.py::test_reconfigure_registers_the_missing_host
    assert 0 == 1  (no register argv: the hook_register branch did not exist)
FAILED tests/test_session.py::test_a_failed_register_step_fails_the_row
    AssertionError: assert 'register cod...has no branch' == 'register cod... failed: boom'
FAILED tests/test_session.py::test_a_register_step_with_nothing_left_fails_with_a_reason
    AssertionError: ... 'step kind has no branch'
FAILED tests/test_session.py::test_each_config_step_kind_dispatches[*]  (10 cases; the set-equality assertion fails: 'hook_register' and 'zshenv_shell' are not in the model)
PASSED tests/test_version_status.py::test_hook_drift_ignores_absent_unsupported_and_receiptless_tools   (regression guard, not RED)
PASSED tests/test_version_status.py::test_the_pass_calls_present_harnesses_once                        (regression guard, not RED)
PASSED tests/test_render.py::test_a_hook_reconfigure_prints_its_done_note                             (regression guard, not RED)
14 failed, 3 passed
```

Task 1 GREEN: the same selection → 17 passed (exit 0). Related files (`test_version_status`, `test_session`, `test_render`, `test_postinstall`, `test_engine`, `test_update`) `-n auto` → all passed. `make validate` exit 0 and `make test` exit 0 on the committed tree (5649 passed, 4 skipped).

### Task 2 RED

`uv run pytest tests/test_version_status.py tests/test_session.py -k "missing_zshenv_block or carry_their_done_note or zshenv_warning_lands_on_the_zsh_row or unparsable_managed_settings_file or unparsable_unmanaged_settings_file or konsole_and_zshenv" -q --no-cov -n 0` → exit 1; log `…/scratchpad/red-23-07-task2.log`.

```
FAILED tests/test_version_status.py::test_a_missing_zshenv_block_reads_misconfigured_on_the_zsh_row
    AssertionError: assert <Health.OK: 'ok'> is <Health.MISCONFIGURED: 'misconfigured'>
FAILED tests/test_version_status.py::test_terminal_steps_carry_their_done_note
    assert (ConfigStep(t..., report=''),) == (ConfigStep(t...kitty.conf'),)
FAILED tests/test_version_status.py::test_a_zshenv_warning_lands_on_the_zsh_row_only
    assert 'terminal shell not checked: zshenv: not valid UTF-8' not in (... 'terminal shell not checked: zshenv: not valid UTF-8')
FAILED tests/test_version_status.py::test_an_unparsable_managed_settings_file_reads_blocked
    AssertionError: assert <Health.OK: 'ok'> is <Health.MISCONFIGURED: 'misconfigured'>
FAILED tests/test_session.py::test_a_zsh_reconfigure_reports_konsole_and_zshenv
    assert [] == ['zsh reconfi...xports SHELL']
PASSED tests/test_version_status.py::test_an_unparsable_unmanaged_settings_file_reads_nothing   (regression guard, not RED)
5 failed, 1 passed (version status + session)
ERROR tests/test_render.py: ImportError: cannot import name 'render_shell_section' from 'installer.render'
```

The two render tests could not be collected until `render_shell_section` existed: the ImportError is the missing-API RED for them (the same shape as the 23-02 and 23-06 RED runs).

Task 2 GREEN: the focused selection → 18 passed (exit 0). Related files → all passed. `make validate` exit 0 and `make test` exit 0 (5657 passed, 4 skipped).

### Task 3 RED

`uv run pytest tests/test_session.py -k "resyncs_codegraph_for_codex_only or without_a_host_install or reads_hosts_after_the_rows or without_recorded_hooks_is_not_swept or failed_resync_is_a_warning" -q --no-cov -n 0` → exit 1; log `…/scratchpad/red-23-07-task3.log`.

```
FAILED tests/test_session.py::test_installing_codex_resyncs_codegraph_for_codex_only
    AttributeError: 'RowOutcome' object has no attribute 'resynced'
FAILED tests/test_session.py::test_the_sweep_reads_hosts_after_the_rows
    assert [] == [1]   (the sweep did not exist, so the hosts were never read)
FAILED tests/test_session.py::test_a_receipt_without_recorded_hooks_is_not_swept
    AttributeError: 'RowOutcome' object has no attribute 'resynced'
FAILED tests/test_session.py::test_a_failed_resync_is_a_warning_and_the_row_stays_done
    AttributeError: 'RowOutcome' object has no attribute 'resync_warnings'
PASSED tests/test_session.py::test_a_run_without_a_host_install_runs_no_sweep   (regression guard, not RED)
```

`test_the_agent_host_hooks_section` (`tests/test_render.py`) was written with the session tests and was **not** run in the RED state before the implementation; it was first run after `render_hook_lines` existed, and it passed. The honest RED for it is the same missing-API ImportError as Task 2.

Task 3 GREEN: the focused selection → 6 passed (exit 0). `make validate` exit 0 and `make test` exit 0 (5663 passed, 4 skipped).

## Acceptance checks (measured)

- `grep -c '"hook_register"' installer/model.py` = 1
- `grep -c "is not registered for" installer/version_status.py` = 1
- `grep -v "^ *#" installer/session.py | grep -c "harnesses"` = 0 (no `RunContext.harnesses`)
- `grep -c "~/.zshenv does not export SHELL as zsh" installer/version_status.py` = 1
- `grep -c "def render_shell_section(" installer/render.py` = 1
- `grep -c "def _settings_facts(" installer/version_status.py` = 1; `grep -c "def tilde" installer/version_status.py` = 0
- `grep -c "def _resync_hooks(" installer/session.py` = 1; `grep -c "(new host)" installer/render.py` = 1
- `grep -c "present_harnesses(" installer/version_status.py` = 1 (one call site: `_present_hosts`)
- New suppression comments (`type: ignore`, `pyright: ignore`, `noqa`, `nosec`) added against `6f2c6e6`: 0
- Cell widths: `test_reconfigure_report_lines_fit_78_cells` and `test_the_agent_host_hooks_section` assert ≤ 78 cells for the longest fixtures.

## Changed existing tests (each, with its reason)

- `tests/test_model.py::test_config_step_is_frozen_with_closed_kinds`: the expected `ConfigStepKind` tuple gained `hook_register` and `zshenv_shell`. Reason: the plan adds the two kinds (locked).
- `tests/test_session.py::test_each_config_step_kind_dispatches`: `_ALL_KIND_STEPS` gained the two kinds; per-kind expected detail (`_DISPATCH_DETAIL`: `hook_register` → `registered for codex`, `zshenv_shell` → `~/.zshenv exports SHELL`); `zshenv_shell` counts as seam-only (no argv); the `hook_register` case runs on a codegraph tool with a receipt and a present host. The docstring's "eight" became "one per kind". Reason: the plan's done notes are details, and the kind set is closed.
- `tests/test_version_status.py::test_kitty_drift_is_misconfigured`, `test_wezterm_drift_lands_on_its_own_row`, `test_konsole_drift_lands_on_zsh`: the expected `ConfigStep` gained its `report` (`Kitty now starts zsh`, `WezTerm now starts zsh`, `Konsole now starts zsh`). Reason: plan decision, terminal steps carry their done note; the fixtures have no path, so no path line.
- No test was deleted. No assertion was weakened. No existing reconfigure assertion needed the joined-detail change (R1-35): no existing test asserted a multi-step warning.

## Deviations from Plan

### Auto-fixed and contract corrections

**1. [Rule 1 - Bug] `CommandError("boom")` is not a valid constructor; the codegraph warning carried the whole message**
- **Found during:** Task 1 test design
- **Issue:** `CommandError` takes `(cmd, returncode, *, detail)`. The plan's example `CommandError("boom")` cannot be built, and `_codegraph_register` built its warning from `{exc}`, which is the multi-line `command failed (...)` text, so a row could never show the vendor's first error line (UI-SPEC: `{first error line}`).
- **Fix:** tests use `CommandError(command, 1, detail="boom")`; `_codegraph_register` returns `codegraph MCP registration failed: {_failure_line(exc)}`, the same rule herdr and tealdeer already use (23-05). An error without detail is unchanged (its first line is the command line).
- **Visible change:** the codegraph install or update warning for a failing command with vendor output now shows that output's first line instead of the command line. The existing warning tests still pass.
- **Committed in:** `5606073`

**2. [Plan text] `_scan_packs` takes the hoisted hosts and the presence error**
- The plan said to pass `present` to `_scan_packs`. A presence failure must still reach the skill packs as their `skill configuration not checked:` note, so the signature became `_scan_packs(packs, present, presence_error)`. The packs keep their own notes.
- **Committed in:** `5606073`

**3. [Judgement] The O7 producer is wrapped per agent, not as a whole**
- The plan said to wrap the producer like `_terminal_facts`. A whole-producer wrap would put `settings not checked:` on every agent row, including rows with no ledger. The wrap is per agent, so a failure marks only the agent whose ledger was read.
- **Committed in:** `01413cc`

**4. [Judgement] No `.zshenv` fact when the sync names no zsh path**
- With no zsh on the host there is nothing to export, so the fact is skipped. The comment is a shortcut: a stale block then reads nothing until zsh is installed; upgrade when the sync names a zsh path it can write.
- **Committed in:** `01413cc`

**5. [Plan text] `render_resync_warnings` is its own function**
- The plan said the resync warnings print "inside `render_postinstall_warnings`' position". They print in that position, as a separate function called right after `render_postinstall_warnings`, because that function takes `InstallOutcome`s and the resync data lives on `RowOutcome`s. No second render call.
- **Committed in:** `683076d`

**6. [Test-first process] Regression guards and a collection-error RED**
- Passed before the change (guards, not RED): `test_hook_drift_ignores_absent_unsupported_and_receiptless_tools`, `test_the_pass_calls_present_harnesses_once`, `test_a_hook_reconfigure_prints_its_done_note` (Task 1); `test_an_unparsable_unmanaged_settings_file_reads_nothing` (Task 2); `test_a_run_without_a_host_install_runs_no_sweep` (Task 3).
- The two render tests of Task 2 failed to collect (ImportError) before implementation.
- The Task 3 render test was not run before implementation (see Task 3 RED above).

### Process notes (no code impact)

- `make validate` on the first Task 1 run failed on ruff's import order in `installer/session.py` and on `tests/test_model.py` (the kind tuple). The import order was fixed with `ruff check --fix` (names only); the kind tuple was updated as listed above. No check was silenced.
- The worktree's `.codegraph/` was created by `codegraph init -i` (git-ignored); the `.venv` by `make install` (uv, in the worktree). No host install, rc edit, or real `codegraph`, `herdr` or `tldr` run.
- The Bash harness refused compound commands that name git; each was split into plain commands run from the worktree root.
- The test-session guard did not trip on either `make test` run.

## Issues Encountered

- The first Task 1 `make test` exited 1 on `tests/test_model.py::test_config_step_is_frozen_with_closed_kinds` (the kind tuple pins the eight original kinds). The tuple was updated for the two new kinds and the gate re-ran green. The rest of the gate passed on each later commit's first attempt.
- The dispatch test's `hook_register` case needed a real receipt and a patched `postinstall.present_hosts`; both are scoped to the test (no global state left behind).

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. Each plan threat has a test:

- T-23-16 (sweep registers beyond the new host): `test_installing_codex_resyncs_codegraph_for_codex_only`, `test_a_run_without_a_host_install_runs_no_sweep`, `test_a_receipt_without_recorded_hooks_is_not_swept`
- T-23-56 (writing an unparsable managed settings file): `test_an_unparsable_managed_settings_file_reads_blocked` (the row is blocked; nothing is written)
- T-23-17 (a hook or presence failure taking the pass or run down): `test_a_failed_resync_is_a_warning_and_the_row_stays_done`, and the presence wrap in `_present_hosts`
- T-23-18 (markup or ANSI in report lines): report lines are printed with markup off and `sanitize_log_line`

## Not checked

- Live hosts: no real codegraph, Claude, Codex, opencode, cursor-agent, kitty, WezTerm, Konsole or zsh was run. Every test uses fake runners, injected `which` and presence, and a scratch HOME.
- The `zshenv` drift is produced by the synchronizer's dry run; its real output shape is covered by 23-04's tests, not re-run here.
- The sweep's command output is attributed to the last host row in the TUI log (a shortcut, recorded in `_resync_hooks`).

## Self-Check

- [x] `installer/model.py`, `installer/postinstall.py`, `installer/version_status.py`, `installer/session.py`, `installer/render.py` and the six test files are committed in `5606073`, `01413cc` and `683076d`
- [x] `git merge-base --is-ancestor` confirms `5606073` and `01413cc` are ancestors of `683076d90682720f7e9384a3c62bd3c25c2d0734`
- [x] Each commit's tree passed `make validate` (exit 0) and `make test` (exit 0)
- [x] No change to `.planning/STATE.md` or `.planning/ROADMAP.md`

## Self-Check: PASSED
