---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "07"
status: complete
subsystem: skill-packs
tags: [claude-plugins, skill-lifecycle, config-step, registry, tdd, security]

requires:
  - phase: 18
    provides: inspect_skill_packs / _probe_outputs one-call-per-harness probe walk
provides:
  - "ConfigStep (frozen) + ConfigStepKind (8 closed D-20 kinds) in installer/model.py"
  - "TOOL_ID_RE enforced by load_tools: an unsafe tool id fails at registry load (checker I4)"
  - "Claude probe reads `claude plugin list --json`; present only for exactly one enabled user-scope canonical entry (D-18, L-19-09)"
  - "inspect_skill_reports -> SkillPackReport(hosts, reasons, steps) with D-18 duplicate/disabled reasons and ordered, validated fix steps"
  - "partial_harnesses / partial_steps for D-17 partial installs"
affects: [19-09 receipts (reuses TOOL_ID_RE), 19-16 skill state wiring, phase 20 RECONFIGURE]

actuals:
  tokens: 12750
  tasks: 3
  commits: 3
plan_head_before: 3d5972b0b2f0e552f7a0a384cac024447e7f1b47
plan_head_after: af3333f9667ff36ae5353768daf42df16f8c3d64

tech-stack:
  added: []
  patterns:
    - "one malformed-entry policy: any invalid entry makes the whole --json listing unknown, never skipped"
    - "inspect_skill_packs is a projection of inspect_skill_reports (one walk)"

key-files:
  created: []
  modified:
    - installer/model.py
    - installer/skill_lifecycle.py
    - installer/registry.toml
    - tests/test_skill_lifecycle.py
    - tests/test_model.py
    - tests/test_catalog_tui.py
    - tests/test_version_status.py

key-decisions:
  - "HarnessCli.matches returns bool | None; None (unreadable answer) maps to host status unknown"
  - "Non-user copies (project and local scope) get an uninstall step only with exactly one absolute, existing projectPath for the same (id, scope) in installed_plugins.json; otherwise the reason stays without a step"
  - "The install/enable step is emitted only when the pack has at least one D-18 reason; a pack simply absent on Claude gets no step here (that is partial_steps' job)"
  - "TOOL_ID_RE check runs first in the load_tools row loop, before the method checks"

requirements-completed: [STATE-06, STATE-07]
duration: 18min
completed: 2026-10-16
---

# Phase 19 Plan 07: Claude JSON probe, D-18 fix steps, ConfigStep and partial installs Summary

**The Claude probe reads `claude plugin list --json` and counts only one enabled user-scope canonical copy. The four-install superpowers state now reads absent, with one disabled and three duplicate reasons and the ordered fix steps: enable, uninstall x3, then marketplace remove. `ConfigStep` and `TOOL_ID_RE` live in model.py, and partial installs are reportable per harness.**

## Tasks

| Task | Commit | What |
|------|--------|------|
| 1 (tracer) | 5e1f8e1 | `ClaudeEntry`, `_claude_entries` (1 MiB cap, JSONDecodeError/RecursionError, id regex, `CLAUDE_SCOPES`, bool `enabled`, str `version`, any invalid entry -> None), JSON `_claude_matches` (exactly one enabled user entry with the canonical id), `--json` argv. Registry claude probes use `ponytail@ponytail`, `superpowers@claude-plugins-official`, `mattpocock-skills@claude-plugins-official`. Test fakes converted by script. |
| 2 | dd30c68 | `TOOL_ID_RE` + `load_tools` check; `ConfigStepKind`/`ConfigStep`; `SkillPackReport`, `_installed_project_paths` (64 KiB cap), `_project_dir`, `_claude_fixes`, `inspect_skill_reports`; `inspect_skill_packs` is now its hosts projection. |
| 3 | af3333f | `partial_harnesses`, `partial_steps` (pure). |

Tracer gate after Task 1: the `<verify>` re-run passed end-to-end (54+59 tests selected, 0 failed; `-k claude` in test_skill_lifecycle: 21 passed, at least 10 required), so expansion continued.

## TDD RED evidence

- **Task 1** (`uv run pytest tests/test_skill_lifecycle.py --no-cov -k claude`): `14 failed, 7 passed, 86 deselected`. The failures were `test_claude_plugin_list_marker_row_is_present`, `test_claude_probe_uses_the_json_argv`, `test_claude_enabled_user_scope_canonical_is_present`, `test_claude_unparseable_json_is_unknown[not-json|object|canonical-enabled-str|other-enabled-int|non-object-entry|version-int|over-1-mib]`, `test_claude_scope_outside_the_closed_set_is_unknown[global|-s|User]` and `test_registry_claude_plugin_probes_use_canonical_ids` (`AssertionError: ponytail / assert ('ponytail' and '')`). The four absent-state tests passed even before the change, because the text parser found no line for them.
- **Task 2** (`uv run pytest tests/test_skill_lifecycle.py tests/test_model.py -q --no-cov`): `ERROR collecting` both files, with `ImportError: cannot import name 'ConfigStep' from 'installer.model'` and `ImportError: cannot import name 'TOOL_ID_RE' from 'installer.model'`. `Interrupted: 2 errors during collection`.
- **Task 3** (`-k partial`): `ImportError: cannot import name 'partial_harnesses' from 'installer.skill_lifecycle'`, `Interrupted: 1 error during collection`.

## Scripted fake conversion counts (Task 1)

| File | `["claude","plugin","list"]` -> `--json` | text answers -> `_CLAUDE_SUPERPOWERS_JSON` | `SkillStatusProbe(..., "superpowers")` -> canonical id |
|------|-----|-----|-----|
| tests/test_catalog_tui.py | 6 | 2 | 8 |
| tests/test_version_status.py | 1 | 5 | 2 |
| tests/test_skill_lifecycle.py | 1 | 1 | 3 |

## Verification

- Task 1 verify: `-k "claude or skill or registry_claude"` across the 3 test files passed. The acceptance greps gave `--json` argv count 1, 3 canonical registry probes, and 0 old argv literals.
- Task 2 verify: test_skill_lifecycle + test_model passed. The gate selection (`config_step or four_install or marketplace or canonical or project_path or hostile or projection or unsafe_tool_id or safe_filename`) passed 28 tests, against 13 required. Acceptance greps: `class ConfigStep` 1, `def inspect_skill_reports` 1, `^TOOL_ID_RE = ` 1, `subprocess.run|Popen` 0 (unchanged from HEAD), `CLAUDE_SCOPES = (...)` 1.
- Task 3 verify: `-k partial` gave 4 passed. `def partial_harnesses|def partial_steps` count is 2. Suppressions stayed at 598, the same as at 3d5972b.
- Plan verification: `pytest tests/test_skill_lifecycle.py tests/test_model.py tests/test_catalog_tui.py tests/test_version_status.py -n auto -q --no-cov` passed. `make validate` exit 0 and `make test` passed before every commit; the last run gave `4139 passed, 4 skipped`, coverage 95.64%. No changes to `pyproject.toml` or `uv.lock` since fde3e68.
- Truncation guard (lines HEAD -> now, test functions HEAD -> now, all end in a newline):
  - Task 1: registry.toml 3602 -> 3602; test_skill_lifecycle 901 -> 1039 (46 -> 55); test_catalog_tui 3968 -> 3995 (149 -> 149); test_version_status 2028 -> 2040 (47 -> 47)
  - Task 2: model.py 969 -> 1001; test_model 1601 -> 1652 (95 -> 98); test_skill_lifecycle 1039 -> 1331 (55 -> 66)
  - Task 3: test_skill_lifecycle 1331 -> 1366 (66 -> 70, strictly grew)
- Final `wc -l`: model.py 1001, skill_lifecycle.py 652, registry.toml 3602, test_skill_lifecycle.py 1366, test_model.py 1652, test_catalog_tui.py 3995, test_version_status.py 2040.
- `git diff --stat 3d5972b HEAD` covers 7 files, +862/-62: model.py +32, registry.toml 6 +-, skill_lifecycle.py 257, test_catalog_tui.py 59, test_model.py +51, test_skill_lifecycle.py 491, test_version_status.py 28.

## Deviations from Plan

1. **[Rule 3 - Blocking] One more fake converted.** `test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual` used one shared text answer for every argv. The claude argv now returned unparseable JSON, which made matt-pocock-skills read `unknown` instead of `absent`. The fake now answers the claude argv with `"[]"`, and the test keeps its intent: the pack is absent on Claude. Fixed in 5e1f8e1.
2. **[Rule 2 - Coverage] Extra tests.** I added `test_clean_canonical_install_has_no_reasons_or_steps` (this behavior bullet had no test name in the plan), `test_unreadable_installed_plugins_keeps_the_reason_without_a_step` (7 cases: missing, over 64 KiB, not JSON, list, plugins-list, records-object, bad records) and `test_a_tool_without_a_skill_lifecycle_reports_no_hosts`. They cover the new branches; skill_lifecycle.py is at 97% for its own test file, and the uncovered lines are older code.
3. **Sandbox: guard scripts.** The worktree sandbox refused the plan's `bash -c '... git show ...'` truncation guard and the compound commands. I ran the same checks as separate plain commands: `git show HEAD:<file> > scratch/head/<file>` per file, then a git-free scratch script comparing line counts, `def test_` counts and the final newline. The suppression guard ran the same way, with `git grep -c` at 3d5972b compared to `grep -n | wc -l` now. For the same reason the `gsd-plan-head-before-19-07` ledger file was not written; `plan_head_before` is the given base 3d5972b. All scratch files were outside the repo and get deleted.
4. **`_installed_project_paths` catches `ValueError`.** That covers `json.JSONDecodeError` plus the `UnicodeDecodeError` that `json.loads` raises on bytes. It also catches `RecursionError` and `OSError`, as the plan specifies.

## Known Stubs

None. `partial_harnesses`, `partial_steps` and the `SkillPackReport` reasons/steps have no production caller yet. This is by plan: 19-16 wires them in, and Phase 20 runs the steps.

## Notes for the orchestrator

- `local`-scope copies are treated like project copies: the `-s local` uninstall step needs a single `projectPath` for that (id, scope) in `installed_plugins.json`. CONTEXT L-19-15 says `projectPath` is unverified on this host, so on the live host such copies will most likely show their reason with no step.
- No live `claude` command ran. Every Claude answer in the tests is a fixture.
- Plan 19-09 can import `installer.model.TOOL_ID_RE` for the receipt filename rule. All 89 registry ids pass (`test_every_registry_tool_id_is_a_safe_filename`).

## Self-Check: PASSED

- 5e1f8e1, dd30c68 and af3333f are ancestors of HEAD; all 7 modified files exist.
