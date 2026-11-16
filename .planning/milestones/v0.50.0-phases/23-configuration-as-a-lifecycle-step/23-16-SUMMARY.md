---
phase: 23-configuration-as-a-lifecycle-step
plan: "16"
subsystem: testing
tags: [container-e2e, podman, fedora, codegraph, hooks, agent-settings, uninstall]

requires:
  - phase: 23-07
    provides: codegraph hook registration on the installer's receipts
  - phase: 23-10
    provides: installer-owned agent settings writes (apply_setting)
  - phase: 23-14
    provides: launch and uninstall wiring for the settings rows
  - phase: 23-15
    provides: CLI uninstall reverts every ledger key
provides:
  - "Container e2e probes codegraph's hook before and after --uninstall --yes"
  - "Container e2e writes Claude and Codex auto-approve through the installer and checks the uninstall reverts it"
  - "One recorded Fedora podman make e2e run with all gate lines OK and the container removed"
affects: [phase-23-gate, ship]

actuals:
  tokens: 4698
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Probe output parsed by bash from one exec_tester command; the installer's own Python runs inside the container"
    - "Settings revert is checked by value per written key, plus a ledger-left check"

key-files:
  created:
    - .planning/phases/23-configuration-as-a-lifecycle-step/23-16-SUMMARY.md
  modified:
    - scripts/container-e2e-verify.sh
    - tests/test_container_e2e_receipts.py

key-decisions:
  - "The hook probe reads the recorded hosts with the installer's receipts reader and greps the config files that name codegraph, before the uninstall"
  - "A file that still names codegraph after the uninstall fails the run; a missing file is clean"
  - "The settings check compares values, not bytes, because codegraph's own register and unregister also edit ~/.claude/settings.json and ~/.codex/config.toml"
  - "No allowlist entry was added: the recorded run printed TRACER_LEFTOVER_OK, so the .zshenv triage case never arose"
  - "No new subcommand: the harness keeps its 5 cmd_ functions"

patterns-established:
  - "New probes follow the receipt_paths shape: one exec_tester call, host-side parse, TRACER_* line, return 1 on failure"

requirements-completed: [CONF-01, CONF-08]

duration: not recorded
completed: 2026-11-07
status: complete
---

# Phase 23 Plan 16: Container e2e proves codegraph's hook and the settings revert Summary

**Container e2e registers codegraph's hook for four real hosts, unregisters it on `--uninstall --yes`, and reverts the Claude and Codex auto-approve keys the installer wrote, all in one recorded Fedora podman run**

## Performance

- **Duration:** not recorded (the run itself took the bulk of the time)
- **Tasks:** 3 (two committed, one run-only)
- **Files modified:** 2

## Accomplishments

- `hook_probe_before` records the hosts codegraph's receipt lists under `codegraph-mcp-register` and the config files that mention codegraph, before the uninstall
- `hook_probe_after` fails the run if any recorded file still names codegraph after the uninstall
- `settings_probe_write` snapshots the Claude and Codex auto-approve keys and writes them through `agent_settings.apply_setting`
- `settings_probe_revert` checks each written key by value after the uninstall and fails on a left ledger
- The recorded `make e2e` run (Fedora 44, podman) ended with every tracer line OK and the container removed

## Task Commits

1. **Task 1: hook register and unregister probes** - `3dc2391` (feat)
2. **Task 2: settings write and revert probes** - `9378ef7` (feat)
3. **Task 3: recorded Fedora podman run** - no commit (the allowlist was not changed, so there is nothing to commit)

## Files Created/Modified

- `scripts/container-e2e-verify.sh` - four probe functions, their wiring in `cmd_pass2`, usage text
- `tests/test_container_e2e_receipts.py` - 8 new tests: 6 from the plan, plus 2 that run the probes' embedded Python under a scratch HOME
- `.planning/phases/23-configuration-as-a-lifecycle-step/23-16-SUMMARY.md` - this file

## Test and Gate Evidence

| Measure | Before | After |
|---|---|---|
| Tests collected (`pytest --collect-only`) | 5789 (5785 passed, 4 skipped) | 5797 (5793 passed, 4 skipped) |
| `e2e` receipts file tests | 44 | 52 |
| Shellcheck findings (`uv run shellcheck -x scripts/container-e2e-verify.sh \| grep -c '^In '`) | 3 | 3 |
| `cmd_` functions in the harness | 5 | 5 |

`make validate` exit 0 and `make test` exit 0 on the tree of each commit (`3dc2391`, `9378ef7`), with the full suite run at each.

### Task 1 RED (tests written before the probes existed, not committed alone)

```
FAILED tests/test_container_e2e_receipts.py::test_hook_probe_after_reports_a_file_still_naming_codegraph
FAILED tests/test_container_e2e_receipts.py::test_hook_probe_before_requires_config_for_recorded_hosts
FAILED tests/test_container_e2e_receipts.py::test_the_hook_probes_are_wired_around_the_uninstall_step
FAILED tests/test_container_e2e_receipts.py::test_hook_probe_before_reads_the_real_codegraph_receipt
E       AssertionError: hook_probe_before() is not defined in the script
```

### Task 1 GREEN

```
....   [100%]     (the four hook tests, after the probes were added)
```

### Task 2 RED

```
FAILED tests/test_container_e2e_receipts.py::test_settings_probe_write_fails_on_a_refusal
FAILED tests/test_container_e2e_receipts.py::test_settings_probe_revert_flags_a_key_or_ledger_left
FAILED tests/test_container_e2e_receipts.py::test_the_settings_probes_are_wired_around_the_uninstall_step
FAILED tests/test_container_e2e_receipts.py::test_the_settings_probes_drive_the_installer_and_check_the_revert
```

### Task 2 GREEN

```
....   [100%]     (the four settings tests, after the probes were added)
```

Full-suite gates: Task 1 `make test` 5789 passed, 4 skipped; Task 2 `make test` 5793 passed, 4 skipped.

## Recorded Run (Task 3)

- **Date:** 2026-11-07
- **Commit under test:** `9378ef7` (code tree; the only later commit is this SUMMARY)
- **Container runtime:** `CONTAINER_TOOL=podman`; `podman run --rm alpine echo ok` printed `ok`; `uv run --no-sync python -c "import installer"` succeeded on the host checkout
- **Command:** `make e2e` (background, output in `.e2e-artifacts/make-e2e.log`), exit 0
- **Container gone:** `podman ps -a --filter name=tools-installer-e2e --format '{{.Names}}'` printed nothing after the run

Tracer lines from `.e2e-artifacts/container/pass1-transcript.log` and `pass2-transcript.log`:

```
FEDORA_RELEASE=Fedora release 44 (Forty Four)
TRACER_HOME_BASELINE entries=8866
TRACER_HARNESS_READY_OK
PASS1_COUNTS installed=67 updated=0 skipped=5 failed=0 dependency_failed=0 mismatched=0 blocked=3 manual=14 ... setup_exit=0
TRACER_CLEAN_INSTALL_OK installed=67 updated=0 skipped=5 failed=0 blocked=3 manual=14
TRACER_RECEIPT_OK tool=yq
TRACER_RERUN_OK installed=0 updated=2 skipped=70 failed=0 dependency_failed=0 blocked=3 manual=14
TRACER_RECEIPT_PRE_UNINSTALL_OK tool=yq
TRACER_RECEIPT_PATHS_OK recorded=113 removable=61
TRACER_HOOKS_RECORDED hosts=claude,codex,cursor,opencode files=8
TRACER_SETTINGS_WRITE_OK wrote=4
TRACER_UNINSTALL_OK
TRACER_RECEIPT_REMOVAL_OK tool=yq
TRACER_RECEIPTS_GONE_OK count=61
TRACER_LEFTOVER_OK
TRACER_HOOKS_UNREGISTERED_OK count=8
TRACER_SETTINGS_REVERT_OK keys=4
TRACER_REINSTALL_OK installed=61 updated=0 skipped=11 failed=0 dependency_failed=0 blocked=3 manual=14
TRACER_CONTAINER_TEARDOWN_OK
```

`Summary —` lines:

```
Summary — 67 installed, 5 skipped, 3 blocked, 14 manual          (pass1)
Summary — 2 updated, 70 skipped, 3 blocked, 14 manual            (pass2 rerun)
Summary — 61 installed, 11 skipped, 3 blocked, 14 manual         (pass2 reinstall)
```

The eight config files the hook probe recorded (`.e2e-artifacts/container/hook-files.txt`): `.claude.json`, `.claude/settings.json`, `.claude/CLAUDE.md`, `.codex/config.toml`, `.codex/AGENTS.md`, `.config/opencode/opencode.jsonc`, `.config/opencode/AGENTS.md`, `.cursor/mcp.json`. After the uninstall none still named codegraph (`TRACER_HOOKS_UNREGISTERED_OK count=8`).

The 3 blocked and 14 manual outcomes are the same in every pass and are accepted by the existing install-step gate; they are not new.

## Phase 23 e2e findings

None. No `TRACER_LEFTOVER path=…`, `TRACER_HOOK_LEFT`, `TRACER_HOOK_FILES_MISSING`, `TRACER_SETTINGS_WRITE_FAILED`, `TRACER_SETTINGS_REVERT_DIFF`, `TRACER_SETTINGS_LEDGER_LEFT` or `codegraph: remove failed` line appeared in the recorded run. The `.zshenv` allowlist entry was not needed and was not added. `scripts/e2e-residue-allowlist.txt` is unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Shellcheck-style PATH classifier rejected the new probe line and shifted usage lines**
- **Found during:** Task 1 (`make test`, `tests/test_shell_scripts_path.py`)
- **Issue:** The new hook probe carried an `export PATH=…$PATH` line (a new hit), and a longer usage block moved the classified lines 205/326/346/548 by two.
- **Fix:** Dropped the `export PATH` line from the probe (the tester login shell already puts `~/.local/bin` on PATH through `write_tester_path`), and reflowed the usage block to its original 8 lines so no classified line moved. `tests/test_shell_scripts_path.py` was not edited (it is outside this plan's files list).
- **Files modified:** `scripts/container-e2e-verify.sh`
- **Committed in:** `3dc2391`

**2. [Rule 3 - Blocking] `ruff check` E501 on two new test lines**
- **Found during:** Task 2 (`make validate`)
- **Fix:** `uv run ruff format tests/test_container_e2e_receipts.py`. The diff is insertions only (97 lines, 0 deleted), so no existing test text changed.
- **Committed in:** `9378ef7`

### Implementation notes (not contract changes)

- **Probe command order:** the hook probe runs its `grep` stage before the `uv run … python` call. The test stub `_uv_stub` uses `exec`, which replaces the test shell, so a command after the Python never ran in the real-Python test (`TRACER_HOOK_FILES_MISSING hosts=claude` on the first GREEN attempt). The parser does not depend on line order, and the real container's `uv` is a real binary, so the change is test-stub driven and behaviour-neutral.
- **Two tests beyond the plan's six:** `test_hook_probe_before_reads_the_real_codegraph_receipt` and `test_the_settings_probes_drive_the_installer_and_check_the_revert` run the probes' embedded Python under a scratch HOME. The stubbed tests alone never execute that Python, so this is the only pre-container check that the quoting and installer calls work.
- **No existing test was changed or deleted.**
- **Worktree-root slip (not committed):** the first RED transcript was written to the worktree root by mistake. It was moved to the scratchpad before any staging.

**Total deviations:** 2 auto-fixed (both Rule 3, both gate fixes); the implementation notes above are not contract changes.
**Impact on plan:** None on the contract. All gate lines required by the plan are present in the recorded run.

## Issues Encountered

- The probe's first GREEN attempt failed for the stub-order reason above. Fixed as described.
- The recorded run had no triage case, so the R1-38 conditional (codegraph remove failure for an absent host) did not arise. No `codegraph: remove failed` line was printed; the four recorded hosts were all still present when codegraph unregistered.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CONF-01 (register and unregister in a real container) and CONF-08 (write and revert in a real container) have real-container evidence from the run above.
- The phase gate on the full tree (this plan runs last) is the recorded run; the orchestrator updates STATE.md, ROADMAP.md and REQUIREMENTS.md after the merge, as the parallel-execution rules require.

---
*Phase: 23-configuration-as-a-lifecycle-step*
*Completed: 2026-11-07*
