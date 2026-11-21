# Phase 32 Review Fix

Three fix runs on router-env/my-coding (part A 11:42 to 11:47, a single-item run for WR-01 that stopped on a misread rule, part B 11:52 to 12:02) and one fix by the orchestrator, then the orchestrator's verification (`make test` after the last commit: 9082 passed, 6 skipped, coverage 96.34%).

## Part A

| ID | Status | Commit | Note |
|---|---|---|---|
| WR-02 + IN-06 | fixed | `2d7aafc8` | A hand-edited ledger no longer crashes the removal sweep: an unsupported MCP ledger or a forged `replaced_default` is refused with a note; a `created_levels` longer than `len(key_path) - 1` is rejected when the ledger is read. |
| WR-05 | fixed | `3424f7cc` | Files the MCP writer creates get mode 0600; an existing file keeps its mode. |
| IN-02 | fixed | `6bea7025` | Parity test between the hand-off names and the hand-off commands. |
| WR-01 | blocked by the executor (twice) | | Both runs stopped on tests that phase 32 itself had added or edited (my run note named only three of them); the orchestrator made the change. |

## WR-01 (orchestrator)

| ID | Status | Commit | Note |
|---|---|---|---|
| WR-01 | fixed | `8bfe5187` | `run_command` starts the child with `Popen` (stdin closed, own session) and, on any interruption or exception, stops the child's whole process group (SIGTERM, then SIGKILL after 5 s) before re-raising. The `subprocess.run` doubles of the three older tests and the phase 32 tests were rewritten for `Popen` with every behavioral assertion kept; a new test interrupts a real child whose grandchild would touch a marker and proves the grandchild is gone. Green on Python 3.12 and 3.15. |

## Part B

| Item | Status | Commit | Note |
|---|---|---|---|
| WR-03 + lane 1 | fixed | `94499ff6` | The Codex server is one ownership unit that is held only when the live table holds exactly the recorded keys; a key the user added keeps the whole server and reports `kept_changed`; the removal preview follows the same rule. Supersedes plan 32-04's sub-cases (d) and (e) (two tests edited to the new rule). |
| WR-04 | fixed | `0e23cae3` | `rereads` ignores the receipt only on the confirmed Reconfigure step and in the drift report; install, update, resync and reinstall honor it, so a deleted server is not silently re-added. |
| Lane 2 | fixed | `4c565e09` | With the official Claude plugin enabled, a Flatpak Chrome path and no env key, Claude is not settled and the hand-off is not suppressed by an existing server entry. |
| IN-05 | fixed | `81356ba4` | The pin is extracted once; the `pi` note appears only when pi is a wanted host. |
| IN-03 | fixed | `ac3b0abd` | The Bruno guards assert the registry, not their own constants. |
| IN-04 | fixed | `a716d9d6` | Stale comments, the `insert_key` docstring and the onboarding SKILL row corrected; backlog 999.32 recorded in ROADMAP. |

## Test robustness (orchestrator)

| Item | Status | Commit | Note |
|---|---|---|---|
| Load-timing flakes | fixed | `1e4f953d` | `test_the_rpc_client_talks_to_a_fake_server_through_files` gave a fake server 2 s and a hanging child 0.5 s to start Python and write a pid file, and the interruption test checked a killed grandchild with `os.kill` (true for a zombie): on a loaded host the first full `make test` after the plan verifies failed once after plans 32-09 and 32-11 (test name not captured). The deadlines are caps with room, and the pid check accepts a zombie. |
