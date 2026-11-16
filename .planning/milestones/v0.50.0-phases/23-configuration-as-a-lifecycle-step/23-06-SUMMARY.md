---
phase: 23-configuration-as-a-lifecycle-step
plan: "06"
subsystem: settings
tags: [agent-settings, config-ledger, json, jsonc, toml, drift, vscode, cursor-agent, codex, opencode, dead-code]

# Dependency graph
requires:
  - phase: 23-01
    provides: hook hosts and receipt carry-forward (receipts.read, receipts.record_hooks)
  - phase: 23-02
    provides: installer/agent_settings.py splice engine (insert_key, remove_key, replace_value, guarded writes)
  - phase: 23-04
    provides: locations.zshenv_path and the env redirect writer (locations.py touched in wave 1)
provides:
  - installer/agent_settings.py: the settings API (table, apply_setting, revert_setting, revert_agent, setting_state, file_problem, ledger_summary, SettingsUnreadable)
  - installer/receipts.py: per-agent config-write ledger (CONFIG_AGENTS, ConfigWrite, ConfigLedger, config_ledger_dir, read_ledger, write_ledger)
  - installer/locations.py: display_path (the one helper, moved from policy._display_path)
  - installer/agent_env.py: adapters(home, platform_os) with cursor-agent and vscode
affects: [23-07, 23-10, 23-11, 23-14, 23-15]

# Actuals (#2632)
actuals:
  tokens: 26079   # chars/4 over the realized diff (git diff 703f5d6 HEAD = 104316 chars), deletions included
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reserve-then-commit: the ledger entry is written before the settings file, restored when the file write fails"
    - "Compare-before-commit with one re-read and retry; a second change is refused with CHANGED_WHILE_WRITING"
    - "Revert filters ledger entries through the code table (agent, setting, key path, value) and the current file; only values still ours are removed"
    - "Type-strict same_value for every 'still ours' and 'already set' comparison"

key-files:
  created:
    - .planning/phases/23-configuration-as-a-lifecycle-step/23-06-SUMMARY.md
  modified:
    - installer/agent_settings.py
    - installer/receipts.py
    - installer/agent_env.py
    - installer/locations.py
    - installer/policy.py
    - tests/test_agent_settings.py
    - tests/test_receipts.py
    - tests/test_agent_env.py
    - tests/test_locations.py
  deleted:
    - installer/agent_policy.py
    - installer/agent_guidance.py
    - tests/test_agent_policy.py
    - tests/test_agent_environment_policy.py
    - tests/test_agent_environment_e2e.py

key-decisions:
  - "D-08 ledger shape: one file per agent under config_ledger_dir() (default_receipts_dir().parent / 'config'); CONFIG_AGENTS is the closed id set (any other id raises ValueError)"
  - "Revert of a parent object the installer created goes with the parent when it holds only our key; the guard would otherwise refuse the empty object left behind"
  - "The settings file is written before the ledger is updated on revert; on apply the ledger is reserved before the file write"
  - "Revert deletes a file only when it is in created_files and the document is then empty (the installer-created file)"
  - "remove_key cuts (not replays the fragment) when a comma-less fragment would strand the comma before it on the last of several members"
  - "OS rule: every OS branch is platform_os == 'macos' versus everything else; no code compares against a 'linux' string (23-REUSE 06-2)"
  - "opencode: opencode.jsonc when it exists, else opencode.json; both present is a refusal naming both files"
  - "Dead chain deleted rather than rerouted (RUN-LEDGER 23 | Cycle 1 replan sign-offs (4)); agent_settings is the single writer of an agent settings file"
  - "display_path moved unchanged to locations.py; policy.py re-binds it under the old private name so its 23 call sites are untouched"

patterns-established:
  - "One settings writer: agent_env.adapters() supplies the path table; only agent_settings imports agent_env (enforced by test_opencode_json_has_a_single_writer)"

requirements-completed: [CONF-08, CONF-09, CONF-12]  # engine and API only; the user-facing rows and the removal reverts land with 23-10, 23-11, 23-15

# Metrics
duration: unmeasured (no start timestamp recorded for this run; worktree base 703f5d6)
completed: 2026-11-07
status: complete
# Measured commit ledger (#3968): base..HEAD measured before this SUMMARY commit
commits: 3
plan_head_before: 703f5d6233ee735ef6cc0f3d4101ddefa87f3f94
plan_head_after: 0b8264f8ad15570bdf2cd9447f3175d9b4270ad7
---

# Phase 23 Plan 06: Agent and editor settings API with a config-write ledger Summary

**Claude, Codex, opencode, cursor-agent and VS Code keys are written only where absent, recorded in a per-agent ledger, and reverted exactly; the dead opencode.json writer is deleted, so agent_settings is the only writer.**

## Performance

- **Duration:** unmeasured (no start timestamp recorded for this run)
- **Tasks:** 3 of 3, one green commit each
- **Files:** 9 modified, 5 deleted (3 of the deleted files are test files for the chain)

## Accomplishments

- A Claude `settings.json` gains `permissions.defaultMode` and `skipDangerousModePermissionPrompt`, keeps every other byte, and comes back byte-identical on revert. A file the installer created is deleted when it is empty again.
- A value the user set differently (`acceptEdits`, cursor `allowlist`, a VS Code `editor.minimap.enabled: true`, a cursor `attributeCommitsToAgent: 0`) is left and reported `set by you`, and never removed.
- Cursor attribution replaces the documented CLI default `true` and restores it only while the value still reads ours; the user's later `true` is kept (`kept_changed`).
- Codex TOML keys go before the first table; VS Code JSONC keeps its comments, its trailing comma and the user's own keys.
- A tampered ledger entry (a key outside the table, or another file) never removes anything.
- A file that changes between read and write is re-read and retried once, then refused with `changed while being written`; the ledger is restored.
- The dead agent_policy chain is deleted with its tests; `test_opencode_json_has_a_single_writer` proves the module is gone and only agent_settings imports `agent_env`.

## Task Commits

1. **Task 1: Claude auto-approve is written, recorded and reverted byte-identical** - `95a2fff` (feat)
2. **Task 2: the setting state reads on, yours, off or drift; races and unreadable files are safe** - `6adf7b3` (feat)
3. **Task 3: Codex, opencode, cursor-agent and VS Code settings round-trip in their own formats; dead chain deleted** - `0b8264f` (feat)

Each commit passed `make validate` (exit 0) and `make test` (exit 0) on its own tree before it was made, and passed the pre-commit hooks.

## Test-first evidence (RED, then GREEN)

### Task 1

RED, before any implementation (the four settings tests cannot be collected because `apply_setting` and `revert_setting` do not exist yet, so the file is reported as a collection error; the other three files ran alone):
```
ERROR tests/test_agent_settings.py
E   ImportError: cannot import name 'apply_setting' from 'installer.agent_settings'
Interrupted: 1 error during collection
FAILED tests/test_receipts.py::test_the_ledger_round_trips_and_fails_closed - AttributeError: module 'installer.receipts' has no attribute 'ConfigWrite'
FAILED tests/test_agent_env.py::test_adapters_define_supported_agents_with_injected_home_paths - Extra items in the right set: 'cursor-agent', 'vscode'
FAILED tests/test_agent_env.py::test_adapters_add_cursor_agent_and_vscode - KeyError: 'cursor-agent'
FAILED tests/test_locations.py::test_display_path_lives_in_locations - AttributeError: module 'installer.locations' has no attribute 'display_path'
```

GREEN, the plan's `-k` selection (7 tests): `.......` exit 0.

A first GREEN run had one failure, `test_a_missing_settings_file_is_created_and_deleted_on_revert`: the child-only revert of a created parent left `{}`, and the re-parse guard refused it (Rule 1, fixed; see Deviations).

### Task 2

RED (collection error on the new names; the behaviours below were written before the implementation but were not separately observed failing):
```
ERROR tests/test_agent_settings.py
E   ImportError: cannot import name 'SettingsUnreadable' from 'installer.agent_settings'
Interrupted: 1 error during collection
```

GREEN, the plan's `-k` selection (6 tests): `......` exit 0. The whole settings file then passed.

### Task 3

RED (collection error on the new names):
```
ERROR tests/test_agent_settings.py
E   ImportError: cannot import name 'ledger_summary' from 'installer.agent_settings'
```

GREEN, the first run after `revert_agent`, `ledger_summary` and the chain deletion: `.....F....` (9 pass, 1 fail). The failure was `test_vscode_ai_off_and_ext_updates_off_are_separate_settings`: the file was left as `{"extensions.autoCheckUpdates": false, "extensions.autoUpdate": false,}`, with a comma stranded before `}` (Rule 1, fixed in `remove_key`). Final: 40 passed in `tests/test_agent_settings.py` (including the 23-02 splice tests), exit 0.

## Test counts (measured)

- Baseline (measured at start, `uv run pytest --collect-only`, per-file sum): **5621** collected (5617 passed, 4 skipped, matching the wave 1 summary).
- After Task 1: **5624 passed, 4 skipped** (5628 collected), `make test` exit 0, coverage 96.12%.
- After Task 2: **5630 passed, 4 skipped** (5634 collected), exit 0, coverage 96.07%.
- After Task 3: **5613 passed, 4 skipped** (5617 collected), exit 0, coverage 96.18%.
- Arithmetic: 5621 + 7 (Task 1) + 6 (Task 2) + 10 (Task 3) - 27 (deleted with the chain: test_agent_policy 20, test_agent_environment_policy 5, test_agent_environment_e2e 2) = 5617. Matches.
- Test-count floors: the plan sets none for this plan; the deltas above are the measured base plus the plan's own additions.

## Verification (acceptance greps and gates)

- `grep -c "def apply_setting(" installer/agent_settings.py` = 1; `grep -c "def read_ledger(" installer/receipts.py` = 1.
- `grep -c "_write_json" installer/agent_settings.py` = 0; `grep -c "def display_path" installer/agent_settings.py` = 0.
- `grep -c "^def _display_path" installer/policy.py` = 0; `grep -c "^def display_path(" installer/locations.py` = 1.
- `grep -v "^ *#" installer/agent_settings.py | grep -c '== "linux"'` = 0.
- `"bypassPermissions"` = 1 and `"danger-full-access"` = 1 in `installer/agent_settings.py`.
- The five chain files are gone (`test ! -e` true for each).
- `grep -v "^ *#" installer/policy.py | grep -cE "AgentEnvironmentPolicy|agent_environment_policy|agent_policy|TYPE_CHECKING"` = 0 (baseline 14 at HEAD).
- `rg -l "installer\.agent_env|from installer import .*agent_env" installer/` lists only `installer/agent_settings.py`.
- Suppression gate: 451 `type: ignore|pyright: ignore|noqa|nosec` matches at base (`703f5d6`, `git grep -c`) and 451 now (`rg -c`). No new suppression.
- `make validate` exit 0 on each commit's tree (pyright 0 errors, bandit, vulture, ruff, shellcheck).

## Chain check (run before the deletion, per the orchestrator's instruction)

`rg` over the repo (excluding `.planning/`, `.git/`, `docs/`) listed only the chain's own files and the new single-writer test. `codegraph explore "agent_environment_policy compose_agent_environment_policy apply_agent_policy apply_agent_permissions audit_agent_policy AGENT_TOOLING_MARKDOWN"` showed callers only in `installer/agent_policy.py`, `installer/policy.py` and the three test files. Nothing outside the chain referred to it, so the deletion proceeded. The `docs/superpowers/` references are historical plan notes, not code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] A created parent object was left as `{}` on revert**
- **Found during:** Task 1 GREEN (`test_a_missing_settings_file_is_created_and_deleted_on_revert`)
- **Issue:** reverting only the child of an object the installer created left `"permissions": {}`; the re-parse guard refused the edit, so the file stayed.
- **Fix:** `_revert_pass` removes the whole created parent when it holds only our key; otherwise it removes the child only.
- **Committed in:** `95a2fff`

**2. [Rule 1 - Bug] A revert stranded a comma before `}`**
- **Found during:** Task 3 GREEN (`test_vscode_ai_off_and_ext_updates_off_are_separate_settings`)
- **Issue:** the first key inserted into an empty object has no trailing comma; cutting it from the last of several members by its fragment left the previous member's comma behind. The JSONC guard accepted the result, but it was not valid JSON and not what the user had.
- **Fix:** `remove_key` takes the cut path (which removes the preceding comma) when a comma-less fragment would strand the comma on the last member.
- **Committed in:** `0b8264f`

### Process notes (no code impact)

**3. [Process] Bash guard refused compound commands**
- The worktree guard refused a few compound `git` and `sed` commands. Each was split into plain commands run from the worktree root. The branch check was then run as separate commands and passed.

**4. [Process] The codegraph index belongs to the main checkout**
- `codegraph explore` warned that its index was from `/var/home/bazzite/git/personal/tools-installer` and not this worktree. Its blast-radius output was used only as a cross-check; the authoritative check was `rg` on the worktree files.

**5. [Process] `make install` created the worktree `.venv`**
- AGENTS.md's `make install` (uv sync) was run in the worktree. No host install or rc edit happened; `make setup`, `make fix` and `make uninstall` were not run.

**6. [Process] Logs kept out of the worktree**
- `make validate` and `make test` logs were written to the session scratchpad, so no untracked file reached the worktree.

### Changes to existing tests (listed per the executor rules)

- `tests/test_agent_env.py::test_adapters_define_supported_agents_with_injected_home_paths`: the exact agent-set assertion now includes `cursor-agent` and `vscode`. **Reason:** D-06 adds those two adapters; the other assertions are unchanged.
- Deleted with the dead chain (plan Task 3, RUN-LEDGER row 4): `tests/test_agent_policy.py` (20 tests), `tests/test_agent_environment_policy.py` (5), `tests/test_agent_environment_e2e.py` (2). **Reason:** they test only the deleted modules.
- No other existing test was changed or deleted.

### Choices the plan left open

- **`tests/test_locations.py`**: the `policy._display_path is locations.display_path` check reads the name with `vars(policy)["_display_path"]`. A direct `policy._display_path` reference fails pyright's `reportPrivateUsage`; this is a plain dict read, not a suppression.
- **`ledger_summary(agent, *, home, platform_os)`** keeps the plan's signature. `home` scopes the result to files under home. `platform_os` is accepted but unused, because the ledger already names the file on whichever OS wrote it. vulture and ruff did not flag it. **Flag for 23-15**: its callers pass `platform_os`, which is harmless, but do not rely on it.
- **`SettingsUnreadable`** message for the both-files case reads `... opencode.json is both opencode.json and opencode.jsonc exist; nothing is written until it parses`. The sentence is awkward but accurate; no test pins it.

## Known Stubs

None.

## Not checked (and why)

- **Non-UTF-8 settings bytes** (`_text_of`'s `UnicodeDecodeError` branch, reported as line 1) are implemented but have no dedicated test. Coverage is above the floor.
- **Ledger and file write failure paths**: the `OSError` branches around `write_ledger` in `_apply_once`, `_revert_once` and the reserve step have no dedicated test.
- **`setting_state`'s `"unreadable"` fallback** (reached only if `_read_document` returns no document and no fragment) is unreachable as written and untested.
- **Revert ordering**: the settings file is written before the ledger on revert. If the process dies between the two, the keys are gone and the ledger still lists them; the next revert finds them absent and clears the entry. Not exercised by a test.
- **UI-SPEC section 5's catalog row** for an unparsable managed settings file (O7) is for 23-07, not this plan.
- **Live tools**: no real Claude, Codex, opencode, cursor-agent or VS Code was run. Every test uses a scratch HOME.

## Self-Check

- Created file: `.planning/phases/23-configuration-as-a-lifecycle-step/23-06-SUMMARY.md` (this file).
- Commits present on `worktree-agent-ad6b9c51cb25f1c6f` and ancestors of HEAD: `95a2fff`, `6adf7b3`, `0b8264f`.
- `git rev-list --count 703f5d6..HEAD` = 3 before this SUMMARY commit.
- No change to `.planning/STATE.md` or `.planning/ROADMAP.md`.

## Self-Check: PASSED
