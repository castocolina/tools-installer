---
phase: 23-configuration-as-a-lifecycle-step
plan: "09"
subsystem: installer
tags: [shell-init, post-install, tweaks, tdd, blocked]
status: blocked
requirements-completed: []

# Actuals (#2632): no plan code reached the branch; the Task 1 work is saved as a patch (see Saved work)
actuals:
  tokens: 0
  tasks: 0
  commits: 0

# Measured commit ledger (#3968): rev-list count from the plan base, taken before this SUMMARY commit
commits: 0
plan_head_before: 58fe43485d5a573da08956a70eac6b75a66d4c57
plan_head_after: 58fe43485d5a573da08956a70eac6b75a66d4c57
---

# Phase 23 Plan 09: Shell-init bundles and install handoffs — Summary (BLOCKED at Task 1)

**Stopped at Task 1 before any commit. The plan's volta shell-init body writes a PATH prepend, which the repo's PATH-accumulation invariant forbids. No code from this plan is on the branch. The Task 1 work is saved as a patch outside the repo.**

## Status by task

| Task | Status |
| ---- | ------ |
| 1 | RED run and GREEN implementation done. `make test` fails on one invariant test. Not committed. Code restored to base. |
| 2 | Not started. It depends on the Task 1 bundles. |
| 3 | Not started. |

## Blocker (plan contract vs. repo invariant)

- **Plan:** Task 1 adds six shell-init bundles. Ledger Q4 (locked) and D-11 give volta a body that exports `VOLTA_HOME` and then prepends its bin dir with `case ":$PATH:" in *":$VOLTA_HOME/bin:"*) ;; *) export PATH="$VOLTA_HOME/bin:$PATH" ;; esac`.
- **Source:** `tests/test_shellrc.py::test_no_accumulating_path_build_under_installer_or_setup` scans `installer/*.py` and `setup.py` for any assignment to `PATH` whose value references `$PATH`. Its only exemption is the `rcclean.py` docstring. The exact failure:
  ```
  AssertionError: Found 1 accumulating PATH assignment(s) outside exemptions:
  installer/tweaks.py:0 in module: __TOOLS_INSTALLER_BIN_DIR__docker-ps() ...
  ...ME:-$HOME/.volta}"\n  case ":$PATH:" in *":$VOLTA_HOME/bin:"*) ;; *) export PATH="$VOLTA_HOME/bin:$PATH" ;; esac\nfi
  ```
  The one hit is the volta body. Every other bundle body passes.
- **Why no small faithful fix exists:**
  - Any PATH prepend in a body string matches the needle. The `case` guard does not change the shape the scanner matches.
  - Hiding the line from the scan, or adding an exemption, silences a check. The rules forbid that, and a module-level exemption would be blanket.
  - Building the line through `shellrc.path_export_guard` at write time needs a render-time directory, so the body would stop honouring `VOLTA_HOME`. That is a design change.
- **Option for the orchestrator (recommended):** drop the `export PATH=` line from the volta body and keep the `VOLTA_HOME` export. The standard layout already puts `~/.volta/bin` on PATH. The volta registry method declares `bin_dir = "~/.volta/bin"`, and `collect_bin_dirs` wires it into the managed PATH block when the directory exists. A first install writes the PATH block above shell init (R1-06, Task 2). Only a custom `VOLTA_HOME` would then go unhandled. That changes ledger Q4, which is locked, so this needs an orchestrator decision.

## Task 1 evidence

RED, run before the implementation, using the plan's command. It failed at collection on the missing API, so no test ran:
```
ImportError: cannot import name 'SENSITIVE_PROMPTS' from 'installer.post_install'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
exit=2
```

RED, the model test, run alone:
```
FAILED tests/test_model.py::test_post_install_action_names_include_the_new_actions
E       AssertionError: assert ('configure_p..._login_shell') == ('configure_p...ow_lean_tips')
exit=1
```

GREEN, targeted (six new post-install tests, the renamed model test, and the disjoint-table test): `8 passed`, exit 0.

`make validate` on the Task 1 tree: exit 0, after two ruff fixes (a long docstring and a lambda assigned to a name).

`make test` on the Task 1 tree: exit 2, `1 failed, 5681 passed, 4 skipped`. The only failure is the PATH invariant above.

## Base gate (the tree the SUMMARY commit lands on)

- `make validate`: exit 0 (log in the scratchpad).
- `make test`: exit 0, `5676 passed, 4 skipped`, coverage 96.20%.

## Test counts

- Collected at start: 5680 (per-file sum of `pytest --collect-only`). Matches the base run above.
- Task 1 tree (in the patch): 5686 collected, which is +6. The six new Task 1 tests are `test_starship_yes_turns_shell_init_on_and_empties_the_theme`, `test_a_split_mode_yes_wires_the_rc_files_to_source_myshellrc`, `test_the_default_reader_wires_no_rc_file`, `test_shell_init_is_never_turned_on_without_a_yes`, `test_the_shell_init_prompt_is_keyed_by_action` and `test_every_sensitive_action_has_a_prompt`. The plan delta for Task 1 is met.
- Committed tree: 5680, unchanged.

## Existing tests changed (in the patch, not committed)

Each change is forced by a plan decision:

- `tests/test_model.py`: `test_post_install_actions_are_the_live_ones` is renamed to `test_post_install_action_names_include_the_new_actions`. Its literal now holds the five plan names, and it also asserts the sensitive tuple and a registry row that declares `source_shell_init`. Reason: the names exist from this plan on (decisions, POST_INSTALL_ACTIONS).
- `tests/test_post_install.py`: `test_post_install_tables_are_disjoint_and_match_their_schema_sets` replaces `len(actions) == 1` and `actions <= sensitive` with `sensitive <= actions`. Reason: the plan adds a second dispatched action, and Task 3 adds non-sensitive ones.
- `tests/test_tweaks.py`: `test_bundles_have_stable_ids_and_order` gains the six shell-init ids in `SHELL_INIT_TOOLS` order. Reason: the plan puts them into `BUNDLES` after `apt-upgrade`.

No test was deleted. No assertion was weakened.

## Saved work

- Patch of the Task 1 code and tests, against base `58fe434`: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/23-09-task1-wip.patch` (418 lines). It covers `installer/tweaks.py`, `installer/post_install.py`, `installer/model.py`, `tests/test_post_install.py`, `tests/test_model.py` and `tests/test_tweaks.py`.
- The six base files were restored with `git checkout --` after the patch was saved. The worktree is clean.

## Process notes

- Worktree branch check passed: branch `worktree-agent-a49d102674b326af5`, HEAD `58fe434`.
- `codegraph init -i` ran in the worktree (gitignored). The main checkout's index had been reported as a different worktree.
- `make install` created the worktree `.venv` (gitignored).
- The harness refused compound git commands. Each was split into plain commands.
- The test-session guard did not trip on either `make test` run.
- Ledger 0c and the cwd sentinel were written before the first commit, as the protocol requires.
- AGENTS.md asks for a `Co-Authored-By` trailer on commits. The orchestrator prompt says no attribution trailers. I followed the orchestrator. The SUMMARY commit has no trailer.
- Nothing was run on the real host. No `make setup`, `make fix` or `make uninstall`. No real rc or settings file was touched. No sudo.

## Known Stubs

None in the committed tree.

## Threat Flags

None in the committed tree.

## Next steps for the orchestrator

1. Decide the volta body. The recommended option is to drop the PATH export and record that under ledger Q4.
2. Re-dispatch this plan from Task 1 with that decision. The patch above can be applied as a starting point, after the volta body is changed.
3. Tasks 2 and 3 follow Task 1 unchanged.

## Self-Check: BLOCKED

- [x] Task 1 was not committed, because `make test` was red on the Task 1 tree.
- [x] Base gate green: `make validate` exit 0, `make test` exit 0 (5676 passed, 4 skipped).
- [x] No changes to `STATE.md` or `ROADMAP.md`.
- [x] No trailers in the commit message.
