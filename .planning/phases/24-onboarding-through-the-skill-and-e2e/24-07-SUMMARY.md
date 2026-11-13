---
phase: 24-onboarding-through-the-skill-and-e2e
plan: "07"
subsystem: postinstall-hooks
tags: [herdr, registry, postinstall, hooks, uninstall, tdd]
requires:
  - phase: 24-02
    provides: herdr ledger agent (apply_setting sidebar group, CONFIG_AGENTS)
  - phase: 24-06
    provides: herdr default_shell through the terminal synchronizer
provides:
  - "herdr catalog row: user tier, audience both, terminal category, raw github_release per OS/arch verified by API digest"
  - "HookPair.standalone and HookPair.settled; herdr_query; has_python3"
  - "herdr integration registration for 13 shared hosts under the status-based ownership rule"
  - "sidebar-markers standalone target: pinned plugin install, ledgered rows, best-effort reload, plugin undo"
  - "TUI delete-config ledger drop (_drop_deleted_ledgers)"
affects: [24-08 container e2e, 24-09 UAT]
tech-stack:
  added: []
  patterns:
    - "standalone hook target: recorded and undone like a host, never printed as one (host_labels drops non-harness ids, every host sentence guards on empty labels)"
    - "hook-owned read-only status (settled) subtracted by the drift fact, probed only when something is pending"
key-files:
  created: []
  modified:
    - installer/registry.toml
    - installer/postinstall.py
    - installer/version_status.py
    - installer/app.py
    - installer/render.py
    - installer/session.py
    - installer/wizard_app.py
    - tests/test_postinstall.py
    - tests/test_registry.py
    - tests/test_download.py
    - tests/test_app.py
    - tests/test_render.py
    - tests/test_session.py
    - tests/test_version_status.py
key-decisions:
  - "has_python3 is a public module-level seam in postinstall (tests replace it) instead of patching shutil.which globally"
  - "An unreadable plugin list sets the sidebar up as nothing (no install, no keys, a warning), the same conservative rule as an unreadable integration status"
  - "A host herdr reports `current` or does not list is skipped with a warning naming it as yours, not silently"
  - "The tracer ships the whole sidebar happy path plus install-failure containment; Task 3 adds the python3, plugin-list and token-hint refusals test-first"
requirements-completed: [ONB-01]
metrics:
  duration: "~1h50m"
  completed: "2026-11-13"
status: complete
actuals:
  tokens: 16500
  tasks: 3
  commits: 3
plan_head_before: 891b5c61e72a4ceec6cde22654d2424e67ff5366
plan_head_after: d4add86cf0c0921206c38ee02cf37f32190277be
commits: 3
---

# Phase 24 Plan 07: herdr onboarding Summary

herdr installs as a user-tier raw binary verified by its API digest, registers `herdr integration` only for present shared hosts it does not already serve (status-based ownership), adds the pinned workspace-separator plugin and its ledgered sidebar rows as a standalone `sidebar-markers` target that is never named an agent host, and removes exactly what it recorded, integration first, before the binary goes.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | herdr installs, registers claude and the sidebar, and removes them, end to end (tracer) | 203a0a4 |
| 2 | every shared host, the user-owned rule and a drift fact that agrees with it | 9730d57 |
| 3 | the sidebar's refusals, the uninstall order and the config-delete cleanup | d4add86 |

## What was built

- **registry.toml:** the herdr `[[tool]]` (category terminal, P2, audience both, tier user, `config_paths` for `~/.config/herdr` and `~/.local/state/herdr`, `postinstall = "herdr-integration"`, two raw `github_release` methods `herdr-linux-{arch.machine}` / `herdr-macos-{arch.machine}`, `member = "herdr"`, no checksum so the API digest verifies) with a `# Verified` paragraph: v0.9.5 assets, the integration target list, per-host file effects (including codex `config.toml` left behind), the pinned plugin and its python3/git needs, the plugin's known limits, the never-enabled sort actions, reload needing a running server, and the `herdr update` drift.
- **postinstall.py:** `HookPair.standalone` (`{"sidebar-markers": "castocolina/herdr-setup/plugins/workspace-here"}`) and `settled`; `_HERDR_TARGETS` extended to 13 hosts (`factory-droid -> droid`; antigravity and gemini-cli left out with the reason); `HOST_CATALOG_IDS` gains pi and copilot; `herdr_query` (stdout on exit 0, captured stdout of a non-zero exit, None otherwise); the status parse and per-state rule (`current` is yours and left out, `not installed`/`needs repair` installed and recorded, unreadable registers nothing); the sidebar step (python3, plugin-list, pinned `plugin install --ref <sha> --yes`, `apply_setting("herdr","sidebar")`, best-effort `server reload-config`, token hint for user-held rows); `_herdr_settled`; the plugin undo after the integration undos; `unregister_hosts`, `run_postinstall` and `register_hooks` take targets then standalone ids; `host_labels` drops non-harness ids.
- **display guards:** `render.py`, `wizard_app.py`, `app.py`, `session.py`, `version_status.py` print their host sentence only when `host_labels` is non-empty.
- **version_status.py:** `_hook_fact` takes the resolved binary and the pass's probe, computes pending targets plus standalone ids not recorded, subtracts `pair.settled(...)` only when something is pending, and gives a pending sidebar its own sentence and step.
- **app.py:** `_drop_deleted_ledgers` (TUI route, after `_config_step`, before the final revert, only when every file the ledger records is gone); the `_after_removal` shortcut comment rewritten. `removal_order` untouched (hooks-first landed in 23.2 eb893c0; herdr's `postinstall` row is all it needs).

## TDD evidence (RED output)

Task 1, before any implementation (`uv run pytest ... -k "herdr or standalone or host_labels or sidebar_only or postinstall_hook or distribution or drawio or config_agent" -q --no-cov -n 0`):

```
FAILED tests/test_postinstall.py::test_herdr_installs_registers_and_removes_end_to_end
FAILED tests/test_postinstall.py::test_standalone_targets_are_not_hosts - Att...
FAILED tests/test_postinstall.py::test_host_labels_never_names_a_standalone_target
FAILED tests/test_registry.py::test_registry_audience_distribution_is_pinned
FAILED tests/test_registry.py::test_drawio_desktop_is_the_only_drawio_row
FAILED tests/test_registry.py::test_registry_tier_distribution_is_pinned
FAILED tests/test_registry.py::test_herdr_is_wired_to_its_integration_hook
FAILED tests/test_registry.py::test_herdr_entry_declares_no_skill_pack - KeyE...
FAILED tests/test_download.py::test_herdr_resolves_for_every_os_arch[debian-amd64-herdr-linux-x86_64] (and 3 more OS/arch ids)
FAILED tests/test_app.py::test_herdr_is_the_only_config_agent_declaring_config_paths   (declared == [] vs ['herdr'])
FAILED tests/test_render.py::test_hook_lines_skip_a_sidebar_only_registration   ('Agent-host hooks / herdr: registered for sidebar-markers')
```

Task 2, `-k "herdr or settled or copilot or pi"` before implementation:

```
FAILED tests/test_postinstall.py::test_only_herdr_maps_pi_and_targets_stay_harnesses
FAILED tests/test_postinstall.py::test_herdr_targets_are_shared_hosts
FAILED tests/test_postinstall.py::test_herdr_registers_and_unregisters_per_host
FAILED tests/test_version_status.py::test_hook_fact_ignores_settled_targets
FAILED tests/test_version_status.py::test_sidebar_without_python3_is_settled
FAILED tests/test_session.py::test_installing_copilot_registers_herdr_for_it   (argvs == [] vs the copilot install)
```

Task 3, `-k "sidebar or plugin or rows or reload or hook_tools_before or unregisters_hooks or herdr_config or dependents_first"` before implementation:

```
FAILED tests/test_postinstall.py::test_sidebar_needs_python3   (('sidebar-markers',) == ())
FAILED tests/test_postinstall.py::test_user_plugin_is_left_alone
FAILED tests/test_postinstall.py::test_unreadable_plugin_list_sets_nothing_up
FAILED tests/test_postinstall.py::test_user_rows_are_kept_and_the_tokens_named   (warning is None)
FAILED tests/test_app.py::test_deleting_herdr_config_drops_its_ledger   (ledger still lists the sidebar entries)
```

Pinning tests that passed at once, by design (the behavior already existed): `test_failed_plugin_install_writes_nothing`, `test_reload_failure_is_a_note` (the tracer's sidebar already contained install-failure containment and the best-effort reload), `test_full_uninstall_unregisters_hooks_before_agent_reverts[cli|tui]` and `test_partial_herdr_config_deletion_keeps_its_ledger` (23.2's hooks-first `removal_order` and the missing drop already satisfy them), plus `test_current_hosts_are_left_out_of_the_receipt` and the herdr_query test, which exercise code written together with the RED-failing tests of the same task. Tests were committed with their implementation, never alone.

## Deviations from Plan

**1. [Rule 1 - Bug] The R2-14 and R1-16 test scenario assumed a kept key keeps its ledger entry**
- **Found during:** Task 3
- **Issue:** the plan hand-edits `ui.sidebar.agents.row_gap` so "the revert keeps it and its ledger entry". `_revert_once` removes every entry whose recorded value matches the table (`mine`) from the ledger, including a `kept_changed` key, so the ledger was empty and the drop had nothing to test. A created config file is also deleted silently by the final revert, so that case never refuses either.
- **Fix:** the tests pre-create the user's own `config.toml` (so it is not in `created_files`) and break it with a hand edit, so the per-tool revert refuses and the ledger keeps its entries; the final revert would then refuse a missing file, which `_drop_deleted_ledgers` prevents (test RED before the drop, green after).
- **Files modified:** tests/test_app.py
- **Commit:** d4add86

**2. [Rule 1 - Bug] `has_python3` seam instead of patching `shutil.which`**
- **Found during:** Task 1 (the tracer would have replaced `shutil.which` for the whole interpreter)
- **Fix:** a public module-level `postinstall.has_python3()`, replaced in tests; `which` is not patched anywhere.
- **Files modified:** installer/postinstall.py, tests/test_postinstall.py
- **Commit:** 203a0a4, 9730d57

**3. [Rule 2 - Correctness] An unreadable plugin list, and a host herdr does not list**
- **Found during:** Tasks 2-3
- **Issue:** the plan names the unreadable-status rule but not the plugin-list and missing-target cases; installing over either could claim the user's setup.
- **Fix:** an unreadable plugin list installs nothing and writes no keys (warning); a host absent from `integration status` is skipped with a warning.
- **Files modified:** installer/postinstall.py
- **Commit:** 9730d57, d4add86

**4. [TDD ordering] Task 1's tracer carries the sidebar's install-failure containment and reload**
- The refusals the plan assigns to Task 3 that were not needed by the tracer (python3, plugin-list, token hint) landed test-first in Task 3; the failure containment and best-effort reload are small enough that the tracer commit could not be green without them, so their Task 3 tests are pinning tests (listed above).

No auth gates. No architectural changes.

## Known Stubs

None.

## Threat surface

No new surface beyond the plan's register: the plugin runs `herdr plugin install` pinned to `2b5ca2a`; the undo ids come from the code-owned target and standalone maps (T-24-30); `herdr_query` only runs read-only `integration status` and `plugin list --json`.

## Verification

`make validate && make test` exit 0 on the final tree (6272 passed, 6 skipped, coverage 96.18%). No real herdr, git, python3 or agent config was touched: the probe is the replaceable `herdr_query`, the runner a recording fake, python3 the `has_python3` seam, the HOME a scratch dir.

## Self-Check: PASSED

- installer/registry.toml herdr row, installer/postinstall.py (`HookPair.standalone`, `_herdr_settled`, `herdr_query`), installer/version_status.py (`_hook_fact`), installer/app.py (`_drop_deleted_ledgers`): FOUND
- commits 203a0a4, 9730d57, d4add86: FOUND in HEAD's history
