---
phase: 24-onboarding-through-the-skill-and-e2e
plan: "01"
subsystem: installer
tags: [cargo_distrobox, alacritty, resolver, receipts, node-floor, desktop-entry]
requires:
  - phase: 23.2
    provides: per-row post_install dispatcher, receipts and removal_plan contract
provides:
  - "cargo_distrobox method kind: build a release tag in a throwaway Distrobox, stage, smoke, swap, record, remove"
  - "installer/desktop_entry.render for .desktop text"
  - "Platform.has_distrobox, has_podman, node_version re-read on every version pass"
  - "Node floor (min_node) as a resolver clause with an actionable reason; ownership resolves with the floor open"
  - "Alacritty entry that installs on immutable Linux with distrobox and podman"
affects: [24-05 update by rebuild, 24-06 terminal tuning, 24-08 container e2e]
tech-stack:
  added: []
  patterns:
    - "module-level replaceable seam (image_exists) for a tri-state query"
    - "executor raises ExecutorError after its cleanups; the engine's existing ladder ends the row FAILED"
key-files:
  created:
    - installer/cargo_distrobox.py
    - installer/desktop_entry.py
    - tests/test_cargo_distrobox.py
    - tests/test_desktop_entry.py
  modified:
    - installer/model.py
    - installer/resolve.py
    - installer/platform.py
    - installer/download.py
    - installer/engine.py
    - installer/uninstall.py
    - installer/ownership.py
    - installer/version_status.py
    - installer/registry.toml
    - tests/test_engine.py
    - tests/test_model.py
    - tests/test_registry.py
    - tests/test_resolve.py
    - tests/test_platform.py
    - tests/test_uninstall.py
    - tests/test_uninstall_e2e.py
    - tests/test_ownership.py
    - tests/test_version_status.py
    - tests/test_catalog_tui.py
key-decisions:
  - "TryExec and Icon are written verbatim (plain desktop-entry strings); only the Exec program is double-quoted, with the spec's two-level escaping (a quote, dollar or backtick takes two backslashes, a backslash four) and % doubled"
  - "Pre-existing leaf proof uses receipts.recorded_elsewhere(\"\") (any readable receipt), because install(method, ctx) has no tool id and _perform's signature stays stable"
  - "The pass snapshots evidence under the lock BEFORE re-reading the platform, so the node probe cannot leak evidence recorded during it into the same pass"
  - "RUN_ROOT is built as Path('/') / 'tmp' so no bare '/tmp' literal trips bandit B108 (no nosec added)"
requirements-completed: [ONB-02, ONB-06, ONB-04]
duration: ~3h
completed: 2026-11-13
status: complete
actuals:
  tokens: 18000
  tasks: 3
  commits: 3
commits: 3
plan_head_before: 9e2ff7b1716b5d34b7f959f682d0bf15e0c74e25
plan_head_after: d2ec3e8591b69aeb3eaea79c55d271673ceff88e
---

# Phase 24 Plan 01: the cargo_distrobox kind, Alacritty on immutable hosts and the Node floor Summary

**Alacritty builds from its release tag with cargo in a throwaway Distrobox (box, pulled image and temp dir always removed), places five receipt-recorded files, and the resolver's one switch now knows distrobox, podman and the system node, per pass.**

## What was built

- **Task 1 (tracer, d7fe25d):** `installer/cargo_distrobox.py` (create, clone, build, tic under `timeout --kill-after=10 <s> env XDG_CACHE_HOME=<tmp>/cache`; stage `.new` siblings, smoke the staged binary, swap with rollback; `finally` removes box, the image this run pulled and the temp dir), `installer/desktop_entry.py`, the kind wired through `model`, `resolve` (rank 25, `tools` category, `needs distrobox and podman`), `platform`, `download.artifact_paths`, `engine` (4-tuple `_perform`, notes on `postinstall_warning`, no PATH smoke, `smoked_artifact`), `ownership`, `uninstall.remove_paths` (empty-parent pruning only under `~/.terminfo`, and strictly below the applications and icons roots), and the Alacritty registry entry (method, `config_paths`, dated comment, `verified = 2026-11-08`). The four pinned Alacritty tests were rewritten.
- **Task 2 (6270780):** release tag validated before any box; a failed `distrobox rm` or `podman rmi` becomes a row note (on failure the notes join the `ExecutorError` message); a user's own pre-existing non-binary file is kept and named; closed load-time validation of `cargo_distrobox` params; `plan_uninstall` reports only the binary as evidence.
- **Task 3 (d2ec3e8):** `Platform.node_version`; `version_status._live_platform` re-reads brew, distrobox, podman and node (`node --version` only through a resolved `which("node")`, whole-output `v<semver>[-pre]` match); the `node` method is gated by `min_node` in `_applies`/`_rejection` with reason `needs Node >= <floor>; this system has <v>`; `unavailable_reason` drops os-only rejections beside a method that passes the os gate and dedupes shorts; `ownership._applicable_methods` resolves with the floor open; `github_repo` accepts the kind (a newer tag reads OUTDATED); adoption stays `github_release` only.

## RED output (tests written first, pasted per the plan)

Task 1 (`tests/test_cargo_distrobox.py` could not even import; the pinned rewrites failed):

```
ImportError: cannot import name 'cargo_distrobox' from 'installer'
FAILED tests/test_registry.py::test_alacritty_builds_in_distrobox_or_uses_distro_packages
FAILED tests/test_registry.py::test_alacritty_entry_records_the_missing_linux_release_and_disabled_cask
FAILED tests/test_resolve.py::test_unavailable_reason_alacritty_names_distrobox_and_podman
FAILED tests/test_catalog_tui.py::test_unavailable_reason_renders_in_row_and_detail
  AssertionError: assert '(not available: needs distrobox and podman)' in '... (not available: immutable host)'
```

Task 2 (38 failures, head and tail shown; the argv-order, build-failure, interrupt and kept-image tests already passed because Task 1's executor implements them):

```
FAILED tests/test_cargo_distrobox.py::test_image_exists_is_tri_state[...]      (no public podman_image_exists)
FAILED tests/test_cargo_distrobox.py::test_image_in_use_is_a_warning
FAILED tests/test_cargo_distrobox.py::test_a_failed_box_removal_names_the_box
FAILED tests/test_cargo_distrobox.py::test_tag_is_validated_before_any_box[-x|a b||v1;rm|--upload-pack=x]
FAILED tests/test_cargo_distrobox.py::test_preexisting_terminfo_leaf_is_kept_and_named
FAILED tests/test_model.py::test_cargo_distrobox_rejects_an_empty_artifact_list
FAILED tests/test_model.py::test_cargo_distrobox_rejects_a_malformed_param[... 24 cases]
FAILED tests/test_model.py::test_cargo_distrobox_rejects_a_first_artifact_outside_the_bin_dir
FAILED tests/test_uninstall.py::test_only_the_binary_is_ownership_evidence
FAILED tests/test_ownership.py::test_only_the_binary_is_ownership_evidence
  AssertionError: assert 'installer' != 'installer'
```

Task 3 (`tests/test_resolve.py` failed at collection):

```
TypeError: Platform.__init__() got an unexpected keyword argument 'node_version'
FAILED tests/test_platform.py::test_detect_sets_distrobox_and_podman
FAILED tests/test_version_status.py::test_pass_rereads_distrobox_podman_and_node
FAILED tests/test_version_status.py::test_node_floor_reads_the_probed_prerelease
FAILED tests/test_version_status.py::test_constant_probe_service_keeps_mmdc_available
FAILED tests/test_version_status.py::test_newer_alacritty_tag_reads_outdated
FAILED tests/test_ownership.py::test_node_floor_never_drops_ownership
```

## Verification

- `make validate`: exit 0 on every commit's tree (the pre-commit hooks ran ruff, pyright, bandit, vulture on each commit).
- `make test`: 6120 passed, 6 skipped, coverage 96.16% on the final tree. The session fingerprint did not fail; no re-run was needed.
- Task verify commands, the acceptance greps (registry counts 1/1/0, engine non-comment `cargo_distrobox` 5, `has_distrobox` 2, `node_version` 1, version_status 3), `precedence_fixtures` (5 passed) and the three unchanged constant-probe tests all pass. No `noqa`, `type: ignore`, `pyright: ignore` or `nosec` was added under `installer/`.
- Nothing was run on the host: no distrobox, podman, cargo, git-in-box, tic or node launch; every box step is a recording fake; the fake alacritty is a `#!/bin/sh` script under the test temp dir.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tests/test_uninstall_e2e.py` fake `_perform` returned a 3-tuple**
- **Found during:** Task 1 (`make test`, 8 failures `not enough values to unpack`)
- **Issue:** the 4-tuple `_perform` contract broke a second test double that is not in the plan's file list.
- **Fix:** the fake now returns `(False, None, (), ())`; `tests/test_engine.py::_fake_perform` was updated the same way (it was in the list).
- **Files modified:** tests/test_uninstall_e2e.py, tests/test_engine.py
- **Commit:** d7fe25d

**2. [Rule 1 - Bug] The node probe leaked evidence into the same pass**
- **Found during:** Task 3 (`test_evidence_is_read_under_the_lock_as_a_snapshot` failed once the pass probed `node --version` before its evidence snapshot)
- **Issue:** `_live_platform()` runs a probe; the pass took its evidence snapshot after it, so evidence recorded during a probe landed in the pass that should not see it.
- **Fix:** `_pass` snapshots the evidence under the lock first, then reads the platform, then publishes it.
- **Files modified:** installer/version_status.py
- **Commit:** d2ec3e8

**3. [Rule 1 - Bug] A source-substring pin named the old call**
- **Found during:** Task 3 (`test_ownership_only_methods_wired_into_both_candidate_and_competing_paths` asserted `resolve_methods(tool, platform)` appears in `resolve_ownership`)
- **Fix:** the pin now asserts `_applicable_methods(tool, platform)`, the helper every ownership resolve site now routes through (R1-11).
- **Files modified:** tests/test_ownership.py
- **Commit:** d2ec3e8

**4. [Rule 2 - Missing critical] Desktop-entry correctness beyond the plan's wording**
- The plan said to double-quote a path with a space for TryExec, Exec and Icon. Per the Desktop Entry spec only `Exec` is quoted; `TryExec` and `Icon` are plain strings and a quoted TryExec would not resolve. `Exec` also doubles `%` (a bare `%` is a field code) and uses the spec's two-level escaping. Tests pin all of it (tests/test_desktop_entry.py).
- **Commit:** d7fe25d

**5. [Rule 2 - Missing critical] Load validation went slightly past the plan's list**
- Also rejected: a repo or image leading with a dash or without a qualified registry host, control characters in `box` or `host`, and duplicate `host` paths (a duplicate would stage one file over another). **Commit:** 6270780

**6. [Rule 1 - Bug] `_stage` leaked `.new` siblings on a mid-stage failure**
- Found while writing Task 2: the staged list lived inside `_stage`, so a failed smoke or render left earlier `.new` files. The caller now owns the list and deletes every `.new` in its `finally`. **Commit:** 6270780

The pre-existing-leaf rule asks "is it in the current Alacritty receipt". `install(method, ctx)` has no tool id and `_perform`'s signature is shared with test doubles, so the executor asks `receipts.recorded_elsewhere("")` (any readable receipt records the path). Equivalent for the shipped catalog, where only Alacritty records these paths.

## Known Stubs

None.

## Threat Flags

None: every new surface (tag to git ref, registry to argv and host paths, box to HOME, podman image store, user files as ownership evidence) is in the plan's threat register and mitigated by the named tests.

## Not provable here (carried to the orchestrator's container run, 24-08, or the user's UAT)

The plan's assumptions A1, A2, A5, A10 (package names, `Cargo.lock`, step timeouts, `enter` exit codes) and distrobox's `/tmp` mount (R1-14) can only be proven by a real nested-podman build. The timeouts are unmeasured constants.

## Self-Check: PASSED

- FOUND: installer/cargo_distrobox.py, installer/desktop_entry.py, tests/test_cargo_distrobox.py, tests/test_desktop_entry.py
- FOUND commits: d7fe25d, 6270780, d2ec3e8 (ancestors of HEAD)
