---
phase: 25-lean
plan: "04"
subsystem: installer-dead-code
tags: [vulture, dead-code, lean, reachability, test-seams, testing]

# Dependency graph
requires:
  - phase: 25-01
    provides: tests/test_reachability.py import-graph guard; no dispatch table or module was deleted here, so its rows are unchanged
provides:
  - Eight caller-less or test-only symbols removed, one commit each, plus one test-helper relocation
  - Vulture-60 triage of every candidate against the live tree (tables below)
affects: [LEAN-01 closure, 25-lean later plans]

# Actuals (#2632): chars/4 over the realized diff, the same scale the estimate used
actuals:
  tokens: 7154    # 28616 diff characters / 4; whole-file basis over the 13 changed files is 176840
  tasks: 2
  commits: 8

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One commit per deleted symbol, each green on make validate && make test"
    - "A consumer that is only a test counts as no production caller; its tests go with it"
    - "A helper used only by one test module moves into that module under the same name"

key-files:
  created:
    - .planning/phases/25-lean/25-04-SUMMARY.md
    - .planning/phases/25-lean/deferred-items.md
  modified:
    - installer/run.py
    - installer/version_cache.py
    - installer/verify_registry.py
    - installer/wizard_app.py
    - installer/shellrc.py
    - installer/omz.py
    - installer/agent_env.py
    - installer/deps.py
    - tests/test_shellrc.py
    - tests/test_omz.py
    - tests/test_agent_env.py
    - tests/test_deps.py
    - tests/test_registry.py

key-decisions:
  - "Deletion rule applied as the must_haves state it: no production caller in installer/, setup.py or scripts/ means delete; a test-only consumer counts as no caller."
  - "Test seams whose removal would change other tests' assertions are kept and listed (the plan's own precedent: CatalogScreen.status_text, CatalogScreen.recommends_text, UnifiedApp.catalog_for). The same rule kept omz_present, DETAIL_PHRASE_COLLISIONS and disk_probing; see Deviations, item 1."
  - "requires_integrity_errors moved into tests/test_registry.py under its own name instead of being deleted, so test_shipped_registry_requires_all_resolve keeps every assertion."
  - "encode_manager_snapshot stays: installer/version_status.py still calls it after save_manager_snapshot went."
  - "_SourceInspection stays: the production inspector uses it after classify_source_line went."

patterns-established:
  - "A candidate the AST reference scan finds only in comments, docstrings or string literals of a wrapper is not a caller; check with an AST walk, not a word grep."

requirements-completed: [LEAN-01]

coverage:
  - id: D1
    description: "Caller-less symbols deleted: run_interactive_command, save_manager_snapshot, the verify_registry release_tag field with its two tag assignments, and wizard_app._BodyStatic"
    requirement: LEAN-01
    verification:
      - kind: unit
        ref: "make test at commits 2538a134, 454ac5b8, 5556bd8a, 20dc1e34 (7672 passed, 6 skipped)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Test-only helpers removed from production: shellrc.classify_source_line, omz.disable_plugins, agent_env.PermissionMode and AgentAdapter.instruction_path / permission_mode"
    requirement: LEAN-01
    verification:
      - kind: unit
        ref: "make test at commits 4f5c4982, 2e18300a, 70364a29 (7633, 7631, 7629 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "requires_integrity_errors relocated into tests/test_registry.py; the shipped-registry integrity guard keeps its assertions"
    requirement: LEAN-01
    verification:
      - kind: unit
        ref: "make test at commit 56532e6b (7629 passed, 6 skipped)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Vulture-60 triage: every candidate classified as framework-dispatched, live with a production caller, or kept test seam, in this SUMMARY"
    requirement: LEAN-01
    verification: []
    human_judgment: true
    rationale: "Three test-only guard consumers (omz_present, DETAIL_PHRASE_COLLISIONS, disk_probing) meet the deletion rule on their face but are kept under the plan's test-seam precedent; the orchestrator must confirm."
---

# Phase 25 Plan 04: Vulture-60 triage and test-only deletions Summary

**Eight caller-less or test-only symbols removed in green commits, one test-only helper relocated, and all 249 vulture-60 rows at the plan's start classified against the live tree (240 rows remain after the deletions)**

## Performance

- **Duration:** not measured (the start timestamp was not captured in this run)
- **Tasks:** 2 (8 commits)
- **Files modified:** 13 (installer 8, tests 5)
- **Gate:** `make validate && make test` ran green before every commit; final tree is the commit-8 tree

## Accomplishments

- Deleted `run.run_interactive_command` (its exception `InteractiveTerminalUnavailable` had no other raiser or catcher) and `version_cache.save_manager_snapshot`.
- Removed the never-read `release_tag` field of `verify_registry._TargetIdentity` along with its two `tag` assignments. The second `release(repo)` call only ever returned the memoized release that `resolve_target` had already fetched, so the `VersionError` branch and the counters are unchanged.
- Removed `wizard_app._BodyStatic`; `DoctorScreen` yields and queries a plain `Static`, which the tests already did.
- Removed test-only `shellrc.classify_source_line`, `omz.disable_plugins`, `agent_env.PermissionMode`, and `AgentAdapter.instruction_path` / `permission_mode`, together with the tests that only checked them.
- Moved `requires_integrity_errors` from `installer/deps.py` into `tests/test_registry.py`, unchanged, with its two unit tests and a verbatim copy of the `_tool` helper; `test_shipped_registry_requires_all_resolve` runs on the real registry with unchanged assertions.

## Task Commits

1. **Task 1, symbol 1: run_interactive_command** - `2538a134` (refactor)
2. **Task 1, symbol 2: save_manager_snapshot** - `454ac5b8` (refactor)
3. **Task 1, symbol 3: release_tag field and its tag assignments** - `5556bd8a` (refactor)
4. **Task 1, symbol 4: _BodyStatic** - `20dc1e34` (refactor)
5. **Task 2, symbol 1: classify_source_line** - `4f5c4982` (refactor)
6. **Task 2, symbol 2: disable_plugins** - `2e18300a` (refactor)
7. **Task 2, symbol 3: PermissionMode and the two AgentAdapter fields** - `70364a29` (refactor)
8. **Task 2, symbol 4: requires_integrity_errors relocated** - `56532e6b` (refactor)

**Plan metadata:** committed as the docs commit that carries this file and deferred-items.md.

## Vulture-60 triage (LEAN-01)

**Baseline:** `uv run vulture installer --min-confidence 60` on this worktree at the plan's start: 249 rows. After the eight commits: 240 rows. The nine rows that went are the deleted names, with `_BodyStatic.renderable` as its own row. No new row appeared, so no helper lost its last production caller (no cascade).

**Method:** a word-level scan (`rg -w`) for the first pass, then an AST reference scan over `installer/`, `setup.py` and `scripts/*.py` (comments, docstrings and string-only mentions do not count), with `tests/` counted separately and `installer/*.toml` template strings checked for `{arch.*}` and similar. A setup.py-only caller counts as live, per D-02.

### Deleted (the task list)

| Symbol | Commit | Production callers after deletion |
| ------ | ------ | -------------------------------- |
| `run.run_interactive_command` (and `InteractiveTerminalUnavailable`) | `2538a134` | none (no test referenced either) |
| `version_cache.save_manager_snapshot` | `454ac5b8` | none; `encode_manager_snapshot` kept, see below |
| `verify_registry._TargetIdentity.release_tag` + two `tag` assignments | `5556bd8a` | none |
| `wizard_app._BodyStatic` | `20dc1e34` | none |
| `shellrc.classify_source_line` | `4f5c4982` | none (wrapper of live `_inspect_source_line`; tests only) |
| `omz.disable_plugins` | `2e18300a` | none (tests only) |
| `agent_env.PermissionMode`, `AgentAdapter.instruction_path`, `AgentAdapter.permission_mode` | `70364a29` | none (tests only) |
| `deps.requires_integrity_errors` | `56532e6b` | relocated to `tests/test_registry.py` |

### Framework-dispatched (one row; never deleted)

| Category | Distinct names | Dispatch mechanism |
| -------- | -------------- | ------------------ |
| Textual hooks and class attributes (`on_*`, `action_*`, `watch_*`, `compose`, `BINDINGS`, `DEFAULT_CSS`, `ENABLE_COMMAND_PALETTE`), Textual widget attributes (`can_focus`, `cursor_type`, `no_wrap`, `overflow`, `auto_width`), enum members in `installer/enums.py`, and `__context__` set in `uninstall.py:524` | 90 | Textual calls hooks and reads class attributes by name; enum members are read by value or name; the interpreter reads `__context__` for exception chaining |

### Kept test seams (no production caller; removal would change other tests)

| Location | Symbol | Test references | Basis |
| -------- | ------ | --------------- | ----- |
| `installer/catalog_tui.py:502` | `CatalogScreen.status_text` | 74 | plan's own test seam (74 test uses) |
| `installer/catalog_tui.py:506` | `CatalogScreen.recommends_text` | 13 | plan's own test seam |
| `installer/wizard_app.py:4069` | `UnifiedApp.catalog_for` | 30 | plan's own test seam |
| `installer/omz.py:696` | `omz_present` | 7 | consistency guard: `test_omz_root_agrees_with_omz_present_on_every_case`, plus the CR-01 tests; see Deviations 1 |
| `installer/ownership.py:1438` | `DETAIL_PHRASE_COLLISIONS` | 3 | the declared-collision register that `tests/test_ownership.py` enforces; see Deviations 1 |
| `installer/wizard_app.py:427` | `disk_probing` | 3 | write-only in production; read by three test wait predicates; see Deviations 1 |

### Live (production caller)

`configure_path` is also named as a post-install action string in `installer/model.py:131`; the callable's real caller is `setup.py:918`. `assets.deb / go / x64 / bits` are read only through `{arch.*}` format strings in `installer/registry.toml`, via `render_asset`.

| Location | Symbol | Production caller |
| -------- | ------ | ----------------- |
| installer/app.py:118 | run_wizard | setup.py:47 |
| installer/app.py:191 | configure_path | setup.py:918 |
| installer/app.py:336 | run_doctor | setup.py:45 |
| installer/app.py:394 | clean_rc_duplicates | setup.py:40 |
| installer/app.py:890 | run_uninstall | setup.py:46 |
| installer/app.py:1205 | perform_uninstall | setup.py:44 |
| installer/assets.py:9 | deb | installer/registry.toml (`{arch.deb}`) |
| installer/assets.py:10 | go | installer/registry.toml (`{arch.go}`) |
| installer/assets.py:12 | x64 | installer/registry.toml (`{arch.x64}`) |
| installer/assets.py:13 | bits | installer/registry.toml (`{arch.bits}`) |
| installer/diskusage.py:96 | probe_disk_pressure | setup.py:463 |
| installer/env_redirect.py:82 | REDIRECTS | setup.py:528 |
| installer/env_redirect.py:105 | environment_d_dir | setup.py:136 |
| installer/env_redirect.py:293 | SYSTEM_ENVIRONMENT_D_DIRS | setup.py:526 |
| installer/execute_screen.py:319 | wants_ascii_spinner | setup.py:53 |
| installer/legacy_guard.py:128 | remove_ban_blocks | setup.py:55 |
| installer/legacy_guard.py:170 | remove_guard_shims | setup.py:55 |
| installer/locations.py:94 | rc_paths_for_mode | setup.py:59 |
| installer/locations.py:109 | all_ban_rc_paths | setup.py:57 |
| installer/locations.py:134 | drop_project_venv_from_path | setup.py:58 |
| installer/model.py:872 | load_categories | setup.py:62 |
| installer/platform.py:65 | detect | setup.py:64 |
| installer/pnpm_globals.py:834 | reinstall_node_globals | setup.py:614 |
| installer/policy.py:413 | desktop_shell_policy | setup.py:68 |
| installer/policy.py:499 | cache_redirect_policy | setup.py:67 |
| installer/post_install.py:132 | use_shell_init_sourcing | setup.py:831 |
| installer/post_install.py:177 | use_git_runner | setup.py:832 |
| installer/prompt.py:15 | CallbackPrompter | setup.py:72 |
| installer/receipts.py:654 | scan_retired | setup.py:73 |
| installer/render.py:535 | render_troubleshooting | setup.py:74 |
| installer/run.py:53 | apply_child_env | setup.py:79 |
| installer/run.py:162 | run_git_isolated | setup.py:82 |
| installer/run.py:184 | run_captured_in_group | setup.py:81 |
| installer/schedules.py:611 | context_for | setup.py:701 |
| installer/schedules.py:1715 | ensure_schedule_defaults | setup.py:739 |
| installer/schedules.py:1724 | after_target_removed | setup.py:729 |
| installer/schedules.py:1756 | SCHEDULE_DEFAULT_WAIT_SECONDS | setup.py:85 |
| installer/schedules.py:1759 | ScheduleDefaultWarnings | setup.py:85 |
| installer/schedules.py:1778 | arm | setup.py:985 |
| installer/schedules.py:1929 | sweep_adapters | setup.py:810 |
| installer/settings.py:51 | default_settings_path | setup.py:89 |
| installer/settings.py:55 | load_settings | setup.py:91 |
| installer/settings.py:96 | resolve_link_mode | setup.py:92 |
| installer/settings.py:108 | link_mode_needs_choice | setup.py:90 |
| installer/settings.py:119 | SettingsStore | setup.py:88 |
| installer/shellrc.py:342 | has_managed_block | setup.py:94 |
| installer/systemd_daemon.py:501 | peek | setup.py:368 (`cache.peek()`) |
| installer/terminal_shell.py:893 | sync_terminal_shells | setup.py:96 |
| installer/terminal_shell.py:1035 | sync_message | setup.py:96 |
| installer/tweaks.py:317 | launch_lines | setup.py:693 |
| installer/tweaks.py:351 | uninstall_line | setup.py:1288 |
| installer/tweaks.py:360 | strip_legacy_aliases | setup.py:102 |
| installer/tweaks.py:456 | applicable_bundles | setup.py:101 |
| installer/uninstall.py:759 | active_tweak_ids | setup.py:105 |
| installer/version_cache.py:234 | default_cache_path | setup.py:107 |
| installer/version_status.py:1346 | is_present | setup.py:651 |
| installer/version_status.py:1353 | installed_or | setup.py:804 |
| installer/wizard_app.py:3731 | run_errors | setup.py:1190 |
| installer/wizard_app.py:3737 | run_in_flight | setup.py:1156 |

Note the `encode_manager_snapshot` kept after `save_manager_snapshot` went: `installer/version_status.py:1997` calls it.

## Deviations from Plan

### Items for the orchestrator to decide

**1. [Triage decision - test-seam precedent] Three candidates meet the deletion rule on their face but are kept**

- **Found during:** Task 2 triage (after the eight planned deletions)
- **Issue:** `omz_present`, `DETAIL_PHRASE_COLLISIONS` and `wizard_app.disk_probing` have no production caller (checked by AST scan of `installer/`, `setup.py` and `scripts/`) and are not in the task list. The must_haves say delete when no production caller remains, and D-02 says "delete what nothing reaches".
- **Why kept:** the plan's own precedent keeps test seams whose removal would change other tests' assertions. Each has a live consumer in its tests that encodes an invariant: `omz_present` backs the `omz_root` consistency guard (`tests/test_omz.py`, CR-01), `DETAIL_PHRASE_COLLISIONS` is the declared-exception register that `tests/test_ownership.py` checks, and `disk_probing` is read in three test wait predicates (`tests/test_wizard_app.py` 329, 479, 3750), where removing it changes timing semantics.
- **Action needed:** orchestrator to confirm keeping them, or to schedule a follow-up that deletes them with those tests. Full detail is in `deferred-items.md`.

### Auto-fixed Issues

**2. [Rule 3 - Blocking, verification flake] Intermittent failure in a test unrelated to this plan**

- **Found during:** Task 1, commit `454ac5b8` full gate
- **Issue:** `tests/test_run.py::test_streaming_runner_emits_incrementally_before_child_exits` failed once with a gap of 0.2998 s against a 0.3 s bound under `-n auto`. Rerun of the full gate passed (7672 passed), and the test passes 5 of 5 alone.
- **Fix:** none in this plan; the wall-clock bound is out of scope. Logged in `deferred-items.md`.
- **Files modified:** none
- **Commit:** n/a

### Test-side changes (within the rule that tests of a deleted symbol go with it)

**3. Whole tests removed (all test deleted symbols only)**

- `tests/test_shellrc.py`: four dedicated classifier tests with their parametrize lists, plus `test_a_reserved_word_prefix_does_not_refuse_an_unrelated_command`, `test_ordinary_redirections_are_not_refused`, `test_a_single_quoted_argument_is_not_expanded`.
- `tests/test_omz.py`: `test_disable_removes_only_the_managed_names`, `test_disable_removes_a_plugin_the_user_had_before`.
- `tests/test_agent_env.py`: `test_pi_is_an_audit_only_adapter`, `test_adapters_define_native_instruction_paths_when_supported`.
- Net effect on the suite: 7672 passed before the classifier commit, 7629 after the last deletion (43 tests, all of them tests of deleted symbols).

**4. Assert lines removed from mixed tests (live assertions kept)**

- `tests/test_shellrc.py`: the classifier assert in `test_a_simple_line_sourcing_myshellrc_is_disabled_not_deleted` (this removes its "no live source left behind" check; `sources_file` tests still cover the behaviour), and the classifier assert in each of `test_sources_file_is_broader_than_the_rewriter` and `test_sources_file_answers_no_for_every_none_shape`.
- `tests/test_omz.py`: the `disable_plugins` assert lines in `test_multi_line_array_is_refused_not_parsed`, `test_a_zshrc_with_no_plugins_line_raises_on_enable_and_no_ops_on_disable`, `test_commented_out_plugins_line_is_never_matched`, `test_disable_on_an_array_without_the_managed_names_changes_nothing`, `test_a_multi_line_array_after_a_single_line_one_is_refused_not_silently_edited`, `test_a_crlf_zshrc_is_edited_and_keeps_its_line_endings`, and the disable line plus its comment in `test_quoted_plugin_names_are_recognised_not_duplicated`. A comment inside `test_removal_raises_rather_than_dropping_the_record_when_the_array_is_shadowed` was reworded to stop naming the deleted function.
- `tests/test_agent_env.py`: the `instruction_path` and `permission_mode` asserts in `test_copilot_adapter_honours_an_absolute_copilot_home` and `test_herdr_adapter_path`.
- **Stale names kept (not renamed, to keep the change to assertions):** `test_a_zshrc_with_no_plugins_line_raises_on_enable_and_no_ops_on_disable` now asserts only the enable raise, and `test_a_simple_line_sourcing_myshellrc_is_disabled_not_deleted` no longer checks for a live source. A later cleanup can rename them.

**Total deviations:** 1 triage decision (item 1, needs orchestrator confirmation), 1 pre-existing flake (item 2, logged), 1 test-side set (items 3 and 4).

**Impact on plan:** the eight planned deletions and the relocation landed as specified and each commit is green. The triage gap is the main open point: three guard-style test consumers are kept under the plan's own test-seam precedent rather than deleted, and the orchestrator should confirm that choice.

## Issues Encountered

- **Sandbox guard on compound git commands:** the worktree guard refused several compound shell commands containing `git`; they were split into plain commands. The same guard refused writing the plan-commit ledger to the worktree's git directory. The ledger lives at `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/p25-04-plan-head-before.txt` instead, holding the spawn base `c6db57a771740c589040d29be2601c0f99cf00b6`. The commit count is measured from that base.
- **Codegraph and codebase-memory not used:** the plan's per-symbol `trace_path` step was replaced by `rg -w` plus the AST reference scan described under Method. No symbol was deleted without a zero-production-caller result from one of those two checks.

## Known Stubs

None.

## Threat Flags

None: this plan removes code and adds no new network, auth, file-access or schema surface.

## Next Phase Readiness

- LEAN-01 deletions are in. The open decision is item 1 above: confirm the three kept test-only guards, or schedule their deletion with their tests.
- The flaky streaming test in `deferred-items.md` should be fixed before the next full gate depends on it.

## Self-Check: PASSED

Verification commands, run after the eight commits (all passed; files and commits confirmed present):

- `rg -n -w 'classify_source_line|disable_plugins|PermissionMode|instruction_path|permission_mode|requires_integrity_errors' installer setup.py` returns 0 lines.
- `rg -n -w 'run_interactive_command|save_manager_snapshot|_BodyStatic|release_tag' installer setup.py` returns 0 lines.
- `grep -c "^def requires_integrity_errors(" tests/test_registry.py` = 1; `grep -c "^def _tool(" tests/test_registry.py` = 1; `rg -n requires_integrity_errors tests/test_deps.py` returns nothing.
- `uv run vulture installer --min-confidence 60` no longer lists the deleted names (240 rows, down from 249).
- `make validate && make test` exit 0 on each of the eight commit trees.

---
*Phase: 25-lean*
*Completed: 2026-11-15*
