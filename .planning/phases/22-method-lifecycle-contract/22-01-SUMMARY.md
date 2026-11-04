---
phase: 22-method-lifecycle-contract
plan: "01"
subsystem: registry
tags: [registry, load-validation, harness-denylist, script-recipes, dead-code]
commits: 3
plan_head_before: 6fcaa7fe52d9c25bdb0efecbd4d93b388f2f0d25
plan_head_after: c2012ad07b8baa2a415fc3e7d8d0ab97e5faf574

requires: []
provides:
  - "Tool.config_paths: declared ~/ config entries validated at load (harness-dir, HOME, two-level, and cross-tool overlap refusals)"
  - "HARNESS_MARKER_DIRS: the one harness denylist, read by config_paths and by skill_lifecycle.HARNESS_PRESENCE"
  - "Script method keys paths, remove, update and writable_prefix, with the closed SCRIPT_ROOTS set"
  - "Removed dead Tool.source, Tool.owner, Tool.uninstall and four dead post-install names"
affects: [22-03, 22-04, 22-05, 22-06, 22-08, 22-09]

actuals:
  tokens: 7125      # chars/4 over the realized diff (28502 bytes of `git diff 6fcaa7f..HEAD`)
  tasks: 3
  commits: 3        # MEASURED: git rev-list --count 6fcaa7f..HEAD

tech-stack:
  added: []
  patterns:
    - "Load-time closed-set validation: refuse unknown placeholders and out-of-HOME paths before any path is deleted or argv built"
    - "One constant (HARNESS_MARKER_DIRS) feeds both the config denylist and skill harness detection"
    - "One traversal rule (_relative_parts) shared by config_paths and script paths"

key-files:
  created: []
  modified:
    - installer/model.py
    - installer/skill_lifecycle.py
    - installer/registry.toml
    - tests/test_model.py
    - tests/test_skill_lifecycle.py
    - tests/test_registry.py

key-decisions:
  - "config_paths is validated at load; an entry under, equal to, or containing any HARNESS_MARKER_DIRS marker is refused (the 'contains' case covers ~/.local/share, which holds ~/.local/share/cursor-agent)"
  - "Cross-tool overlap is refused only when one tool's entry is a proper ancestor of another tool's; exact sharing stays legal so 22-09 can match shared paths by equality"
  - "SCRIPT_ROOTS is the closed set {omz_root}; a token may use ~ or {root} only, never a shell"
  - "config_paths is appended last in Tool.__init__ so no positional caller shifts"

requirements-completed: [LIFE-04]
# LIFE-01 and LIFE-07 are only partly delivered here (their schema half). The runtime
# resolver, removal and writable-prefix behaviour arrive in later plans, so they are not listed.

coverage:
  - id: D1
    description: "Tool.config_paths parsed in declared order; harness-dir, out-of-HOME, two-level, type and cross-tool overlap entries refused at load"
    requirement: "LIFE-04"
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_config_paths_rejects_a_harness_dir"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_config_paths_refuse_an_overlap_across_tools"
        status: pass
    human_judgment: false
  - id: D2
    description: "Script methods accept paths, remove, update and writable_prefix; tokens limited to ~ and SCRIPT_ROOTS; unknown placeholders refused"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_script_lifecycle_keys_load"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_script_tokens_reject_an_unknown_placeholder"
        status: pass
    human_judgment: false
  - id: D3
    description: "Dead Tool.source/owner/uninstall and four dead post-install names removed; registry rows cleaned"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_registry_rows_carry_no_dead_attribution_keys"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_tool_has_no_dead_attribution_fields"
        status: pass
    human_judgment: false

duration: not recorded (start timestamp was not captured in this run)
completed: 2026-11-04
status: complete
---

# Phase 22 Plan 01: Registry lifecycle keys and the harness denylist Summary

**Registry validates `config_paths` against one harness denylist, script methods gain closed-root lifecycle keys, and the dead Tool attribution fields are gone.**

## Performance

- **Duration:** not recorded (start timestamp was not captured in this run)
- **Tasks:** 3 of 3 completed
- **Files modified:** 6 (no new files)

## Accomplishments

- A tool may declare `config_paths`; `load_tools` refuses any entry under, equal to, or containing a harness marker dir, outside `~/`, less than two levels under `~`, holding `.`/`..`/empty parts, or overlapping another tool's entry. `~/.config/gh` is accepted.
- `HARNESS_MARKER_DIRS` is the single source for the harness marker dirs; `skill_lifecycle.HARNESS_PRESENCE` is derived from it with the same 17 keys and the same tuples (import direction `skill_lifecycle -> model` kept).
- `METHOD_PARAMS["script"]` accepts `paths`, `remove`, `update`, `writable_prefix`. Tokens are literal argv elements, optionally led by `~` or a named root from `SCRIPT_ROOTS`; any other `{placeholder}` is refused at load naming the tool and key. Unknown keys are still rejected.
- `Tool.source`, `Tool.owner`, `Tool.uninstall` deleted with their three registry rows' keys (graphify, pi, drawio-desktop). `POST_INSTALL_ACTIONS` is exactly `("configure_path", "set_login_shell")`.

## Task Commits

1. **Task 1: a tool declares config_paths, and a harness-dir entry is refused at load** - `c768499` (feat)
2. **Task 2: script methods accept paths, remove, update and writable_prefix with closed roots** - `7839c90` (feat)
3. **Task 3: the dead Tool fields and post-install names are gone** - `c2012ad` (feat)

Each commit was made after `make validate && make test` exited 0 on that exact tree. Pre-commit hooks (ruff, format, pyright, bandit, vulture) passed on each commit. No `--no-verify`. The RED runs were not committed; they are recorded below.

## Files Created/Modified

- `installer/model.py` - `HARNESS_MARKER_DIRS`, `SCRIPT_ROOTS`, `Tool.config_paths` (field and `__init__` keyword), `_relative_parts`, `_config_path_flaw`, `_parse_config_paths`, `_refuse_config_overlap`, `_script_token_ok`, `_is_argv` (extracted from the `smoke_argv` check, same error text), `_script_refusal`, `_script_paths_refusal`; deleted `Tool.source/owner/uninstall`; `POST_INSTALL_ACTIONS` trimmed to two names
- `installer/skill_lifecycle.py` - private `_HARNESS_COMMANDS`; `HARNESS_PRESENCE` derived from `HARNESS_MARKER_DIRS`
- `installer/registry.toml` - `uninstall` removed from graphify; `source`, `owner`, `uninstall` removed from pi and drawio-desktop; every comment and other key unchanged
- `tests/test_model.py` - 42 new test cases (config_paths, script keys, dead fields, post-install)
- `tests/test_skill_lifecycle.py` - `test_harness_presence_markers_come_from_the_model`
- `tests/test_registry.py` - `test_registry_rows_carry_no_dead_attribution_keys`; three existing tests changed (see Deviations)

## Decisions Made

- The denylist refuses an entry that is an ancestor of a marker (not only inside one), per the plan's D-02 reading: `~/.local/share` is refused because it holds `~/.local/share/cursor-agent`.
- Cross-tool overlap is an ancestor/descendant check on path parts, so `~/.config/shared` beside `~/.config/shared/plugin` is refused in either declaration order, and exact equality stays legal.
- Config entries are validated by path parts, not string prefix, so `~/.cursorx/y` does not match the `.cursor` marker.

## TDD Gate Compliance

Plan type is `tdd`. The RED output below is recorded here only (not committed alone). Each feat commit contains its tests with the implementation.

### RED (Task 1), `uv run pytest tests/test_model.py tests/test_skill_lifecycle.py -k "config_paths or harness_presence_markers" -q --no-cov -n 0`

Exit 1. 21 selected tests failed:

```
FAILED tests/test_model.py::test_config_paths_parses_in_declared_order - AttributeError: 'Tool' object has no attribute 'config_paths'
FAILED tests/test_model.py::test_config_paths_rejects_a_harness_dir[~/.claude/x]
FAILED tests/test_model.py::test_config_paths_rejects_a_harness_dir[~/.cursor/x]
FAILED tests/test_model.py::test_config_paths_rejects_a_harness_dir[~/.gemini/x]
FAILED tests/test_model.py::test_config_paths_rejects_a_harness_dir[~/.codex/x]
FAILED tests/test_model.py::test_config_paths_rejects_a_harness_dir[~/.gemini/antigravity/x]
FAILED tests/test_model.py::test_config_paths_rejects_a_harness_dir[~/.local/share]
FAILED tests/test_model.py::test_config_paths_rejects_entries_outside_two_levels_of_home[/etc/x]  (and 7 more parametrized cases: ~, ~/, ~/.bashrc, ~/a/../b, ~/a//b, ~/./a/b, relative/x; all "DID NOT RAISE")
FAILED tests/test_model.py::test_config_paths_must_be_a_list_of_strings["~/.config/gh"]
FAILED tests/test_model.py::test_config_paths_must_be_a_list_of_strings[[1]]
FAILED tests/test_model.py::test_config_paths_refuse_an_overlap_across_tools[~/.config/shared-~/.config/shared/plugin]
FAILED tests/test_model.py::test_config_paths_refuse_an_overlap_across_tools[~/.config/shared/plugin-~/.config/shared]
FAILED tests/test_model.py::test_config_paths_allow_a_shared_entry_and_one_tools_own_nesting - AttributeError: 'Tool' object has no attribute 'config_paths'
FAILED tests/test_skill_lifecycle.py::test_harness_presence_markers_come_from_the_model - ImportError: cannot import name 'HARNESS_MARKER_DIRS' from 'installer.model'
```

### GREEN (Task 1)

- Targeted selection: 21 passed, exit 0.
- `pytest tests/test_model.py tests/test_skill_lifecycle.py tests/test_version_status.py tests/test_registry.py -n auto -q --no-cov`: exit 0.
- `make validate`: exit 2 on first run (ruff E501 on a docstring I wrote and SIM300 Yoda comparison in a test), fixed in the code and tests, then exit 0.
- `make test`: 5258 passed, 4 skipped, coverage 96.23%, exit 0.

### RED (Task 2), `uv run pytest tests/test_model.py -k "script_lifecycle or script_tokens or script_paths or script_argv or writable_prefix or unknown_script_key" -q --no-cov -n 0`

Exit 1. 16 selected tests failed on the missing validators (for example `has unknown key 'paths'` at load, and `DID NOT RAISE` for the argv and writable_prefix cases). One selected test passes at RED: `test_unknown_script_key_is_still_rejected`. It is a regression guard for the existing `has unknown key` behaviour, not a RED test.

Before GREEN, the RED matches for the new key rejections were loose (`key 'paths'` also matched the existing `has unknown key 'paths'` text). They were tightened to `method 'script' key '<key>'` so only the new validators can satisfy them. The RED run was then repeated on the tightened tests.

### GREEN (Task 2)

- Targeted selection: 17 passed (16 new behaviour tests plus the guard), exit 0.
- `pytest tests/test_model.py tests/test_registry.py -n auto -q --no-cov`: exit 0.
- Import-level check `uv run --no-sync python -c "import installer.model as m; ..."`: `METHOD_PARAMS["script"]` includes `paths`, `remove`, `update`, `writable_prefix`; `SCRIPT_ROOTS == {'omz_root'}`; exit 0.
- `make validate`: exit 2 on first run (ruff I001 import order in `model.py`), fixed with `ruff check --fix` (isort only), then exit 0.
- `make test`: 5275 passed, 4 skipped, coverage 96.22%, exit 0.

### RED (Task 3), `uv run pytest tests/test_model.py tests/test_registry.py -k "post_install_actions_are_the_live or dead_attribution or post_install_rejects_a_deleted" -q --no-cov -n 0`

Exit 1. 6 selected tests failed:

```
FAILED tests/test_model.py::test_post_install_actions_are_the_live_ones - AssertionError (tuple still has four extra names)
FAILED tests/test_model.py::test_tool_has_no_dead_attribution_fields[source]
FAILED tests/test_model.py::test_tool_has_no_dead_attribution_fields[owner]
FAILED tests/test_model.py::test_tool_has_no_dead_attribution_fields[uninstall]
FAILED tests/test_model.py::test_post_install_rejects_a_deleted_action - DID NOT RAISE (pnpm_setup still allowed)
FAILED tests/test_registry.py::test_registry_rows_carry_no_dead_attribution_keys - graphify, pi, drawio-desktop still carried keys
```

### GREEN (Task 3)

- Targeted selection: exit 0.
- `pytest tests/test_model.py tests/test_registry.py tests/test_skill_lifecycle.py tests/test_post_install.py -n auto -q --no-cov`: exit 0.
- `! grep -rnE "source_shell_init|enable_corepack|pnpm_setup|write_agent_reference" installer/ setup.py`: no matches (rg exit 1), i.e. the check passes.
- `make validate`: exit 0 on first run.
- `make test`: 5280 passed, 4 skipped, coverage 96.22%, exit 0.

## Test counts (count floors: measured at task start, plus delta)

| File | Task start | After plan | Delta |
|---|---|---|---|
| tests/test_model.py | 123 | 165 | +42 (T1 +20, T2 +17, T3 +5) |
| tests/test_skill_lifecycle.py | 200 | 201 | +1 |
| tests/test_registry.py | 179 | 179 | +1 new, -1 deleted (pi) |

Full suite: 5237 passed at the ledger's last measurement; 5258 after Task 1; 5275 after Task 2; 5280 at plan end (5237 + 43 net).

## Changed or Deleted Existing Tests

| Test | Change | Reason |
|---|---|---|
| `tests/test_registry.py::test_audit_fix_e11_pi_uninstall_text_does_not_assume_pnpm` | Deleted | Asserted the pi row's `uninstall` text. Task 3 deletes `Tool.uninstall` and the pi row's `uninstall` key (SPEC Boundaries, dead code). |
| `tests/test_registry.py::test_audit_fix_f1_graphify_records_the_cwd_scope_and_uninstall` | Renamed to `..._records_the_cwd_scope`, one assertion removed | The removed assertion read `graphify.uninstall`, deleted by Task 3. The CWD-scope block assertion is kept. |
| `tests/test_registry.py::test_opengsd_handoff_text_matches_scope_and_pin` | One assertion removed (`assert opengsd.uninstall == removal[-1]`) | Read the deleted `Tool.uninstall`. The `removal[-1]` assertion on the lifecycle is kept. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lint findings in my own new code**
- **Found during:** Task 1 (E501 docstring, SIM300 Yoda comparison) and Task 2 (I001 import order)
- **Issue:** `make validate` failed on code I had just written.
- **Fix:** Shortened the docstring, swapped the comparison operands, and ran `ruff check --fix` for the import order (isort only). No suppression comments.
- **Files modified:** installer/model.py, tests/test_skill_lifecycle.py
- **Verification:** `make validate` exit 0 on each tree before commit
- **Committed in:** c768499 (Task 1), 7839c90 (Task 2)

**2. [Plan acceptance wording] Task 1 zero-count grep for `"\.claude",` in `skill_lifecycle.py`**
- **Found during:** post-commit acceptance check
- **Issue:** The plan expects `grep -c '"\.claude",' installer/skill_lifecycle.py` to be 0. It is 2. At the plan base it was 3: the `HARNESS_PRESENCE` marker (removed, as intended), `INSTALL_STATE_HARNESS_DIRS` (`"claude": ".claude",`, line 275), and `PROJECT_RUNTIME_DIRS` (line 330). The two remaining hits are unrelated tables outside `HARNESS_PRESENCE` and are unchanged.
- **Fix:** None. Changing them would widen scope beyond this plan's stated `HARNESS_PRESENCE` objective.
- **Impact:** The acceptance intent (no marker literal left in `HARNESS_PRESENCE`) is met. The grep is over-broad. Those two tables may be a follow-up candidate for the same single-source rule.

**3. [Design detail] Helpers beyond the plan's list**
- `_config_path_flaw`, `_script_refusal` and `_script_paths_refusal` are private helpers added so the validators stay readable. `_script_token_ok` returns a reason string (or None) instead of a bare placeholder name, so the error can say why the token was refused.
- `config_paths` was appended last in `Tool.__init__`, not beside `requires`, so no positional caller shifts.

### Not done (in plan scope but deferred)

- 22-REUSE finding 01-1 also noted the existing script `args` check (`model.py` `kind == "script" and "args" in params`) is a second copy of the argv rule. The plan's Task 2 asks only for `smoke_argv` to move onto `_is_argv`, so `args` was left as it was.

**Total deviations:** 1 auto-fixed lint group (Rule 1), 1 plan acceptance-grep mismatch (no code change), 3 test edits (listed above, each required by a deleted field).
**Impact on plan:** No scope creep. Every test change maps to the plan's required deletion of `Tool.uninstall`/`owner`/`source`.

## Tracer Feedback Gate

Task 1 is `type="tracer"`. It has no `gate` attribute, so no blocking-human stop applied. Before expanding into Task 2, I re-ran Task 1's `<verify>` set end-to-end (targeted tests, the touched test files, `make validate`, `make test`). All passed, so the expansion went ahead.

## Authentication Gates

None.

## Threat Model Coverage

| Threat | Disposition | Where it is handled |
|---|---|---|
| T-22-01 config_paths in a harness dir | mitigate | `_config_path_flaw` against `HARNESS_MARKER_DIRS`; test_config_paths_rejects_a_harness_dir |
| T-22-02 script token elevation | mitigate | Literal argv tokens, closed `SCRIPT_ROOTS`, no `sh -c` (count 0); test_script_tokens_reject_an_unknown_placeholder |
| T-22-03 path traversal | mitigate | `_relative_parts` refuses `.`, `..` and empty parts; paths stay under HOME; test_script_paths_stay_under_home, test_writable_prefix_is_an_absolute_path |
| T-22-32 cross-tool ancestor overlap | mitigate | `_refuse_config_overlap` at the end of `load_tools`; test_config_paths_refuse_an_overlap_across_tools |
| T-22-SC package installs | accept | No package installed or added |

## Acceptance Greps (plan's anchors, run on the final tree)

| Check | Expected | Actual |
|---|---|---|
| `^HARNESS_MARKER_DIRS: dict[str, tuple[str, ...]] = {` in installer/model.py | 1 | 1 |
| `HARNESS_MARKER_DIRS` in installer/skill_lifecycle.py | >= 2 | 3 |
| `"\.claude",` in installer/skill_lifecycle.py | 0 | 2 (pre-existing unrelated tables, see Deviation 2) |
| `^    config_paths: tuple[str, ...] = ()$` | 1 | 1 |
| `^        config_paths: tuple[str, ...] = (),$` | 1 | 1 |
| `def _refuse_config_overlap(` | 1 | 1 |
| `^SCRIPT_ROOTS: frozenset[str] = frozenset({"omz_root"})` | 1 | 1 |
| `sh -c` in installer/model.py | 0 | 0 |
| Suppression comments added by the plan diff (`type: ignore`, `pyright: ignore`, `noqa`, `nosec`) | 0 | 0 |

## Issues Encountered

- The harness refused some compound shell commands in this worktree (it cannot verify they stay in the worktree). Each was split into plain commands run from the worktree root. No git operation touched a path outside the worktree.
- The `make validate` findings above were the only gate failures.
- No `codegraph` index for this worktree: the `codegraph` CLI reported it reads the main checkout's index. I used codegraph only to understand code and Read/Edit the worktree files directly.

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, auth path, file access pattern or schema change at a trust boundary beyond what the plan's threat model covers.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 22-03, 22-04, 22-05, 22-06 and 22-08 can read `Tool.config_paths`, the script `paths`/`remove`/`update`/`writable_prefix` keys and `SCRIPT_ROOTS` from `load_tools`.
- Open follow-up outside this plan: `skill_lifecycle.INSTALL_STATE_HARNESS_DIRS` and `PROJECT_RUNTIME_DIRS` hold harness dir names outside `HARNESS_PRESENCE`. They are not derived from `HARNESS_MARKER_DIRS` and were left alone here.
- No blockers for wave 2.

## Self-Check: PASSED

Created and modified files exist. Commits `c768499`, `7839c90` and `c2012ad` are ancestors of HEAD.

---
*Phase: 22-method-lifecycle-contract*
*Completed: 2026-11-04*
