---
phase: 22-method-lifecycle-contract
plan: "03"
subsystem: removal
tags: [receipts, script-paths, tree, leaf, quarantine, ownership, fail-closed, tdd]
commits: 3
plan_head_before: 5f242f17b9297450f597a700e90727dac185ccfa
plan_head_after: d3e7285

requires:
  - phase: 22-01
    provides: "script method keys paths/remove/update/writable_prefix, SCRIPT_ROOTS, _is_argv"
provides:
  - "download.expand_script_token and SCRIPT_ROOT_RESOLVERS ($ZSH-first omz_root)"
  - "download.artifact_paths script branch: tree (path ends in /) and leaf artifacts"
  - "receipts tree/leaf fingerprint, matches(trees=), type-only reader, record(preexisting=), preexisting_paths"
  - "uninstall.remove_paths(trees=): tree removal through the quarantine re-check, leaf unlink"
  - "ownership: the artifact candidate keeps the script method (R2-01)"
affects: [22-05, 22-06]

actuals:
  tokens: 10685    # chars/4 over the realized diff (42739 bytes of `git diff 5f242f1..d3e7285`)
  tasks: 3
  commits: 3       # MEASURED: git rev-list --count 5f242f1..d3e7285

tech-stack:
  added: []
  patterns:
    - "Type-only proof: a tree is a real directory, a leaf a regular file or a symlink with its target; no hash"
    - "Lexical containment for a leaf link against the receipt's own trees (survives a vendor self-update and a vendor remove)"
    - "Pre-install snapshot (preexisting_paths) decides what an install created; None fails closed"

key-files:
  created: []
  modified:
    - installer/download.py
    - installer/receipts.py
    - installer/uninstall.py
    - installer/ownership.py
    - tests/test_uninstall.py
    - tests/test_ownership.py
    - tests/test_receipts.py
    - tests/test_download.py

key-decisions:
  - "Ledger Q3 as bound: script paths are proven by type only, with link-target rules; no hash"
  - "Artifact kinds tree and leaf are new, so the (path, type) pair in _receipt_proof stops a receipt retyping a leaf into a recursive delete"
  - "A leaf records a target only when it is a symlink; a regular-file leaf and a tree record no target"
  - "record(..., preexisting=None) fails closed: every declared path counts as pre-existing unless a previous receipt proved it"
  - "$ZSH first for the {omz_root} token (SPEC R8, orchestrator decision 05-2); omz_root itself keeps its default-first order"
  - "The artifact candidate's method comes from _INSTALLER_KINDS (script included), not only download and app kinds"

requirements-completed: []
# LIFE-01: the proof half is delivered here (declared paths recorded type-only, removal re-proves
# them). The L3 recipe level and the production wiring of `preexisting` arrive in 22-05 and 22-06,
# so LIFE-01 is not marked complete by this plan.

coverage:
  - id: D1
    description: "A script install's declared paths are recorded type-only and removal deletes exactly those"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_a_script_install_is_removed_by_its_receipt"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_a_self_update_inside_the_tree_keeps_the_proof"
        status: pass
    human_judgment: false
  - id: D2
    description: "A foreign file at a declared path survives and is listed as remove it yourself"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_a_foreign_file_at_a_declared_path_survives"
        status: pass
    human_judgment: false
  - id: D3
    description: "A script tool found by its declared paths keeps its script method"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_a_script_tools_declared_path_keeps_its_script_method"
        status: pass
    human_judgment: false
  - id: D4
    description: "Fail-closed proof: drift, bad receipts, pre-existing paths and unresolvable roots never prove removal"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_a_declared_path_present_before_the_install_is_not_recorded"
        status: pass
      - kind: unit
        ref: "tests/test_download.py#test_expand_script_token_resolves_zsh_when_the_default_dir_is_absent"
        status: pass
    human_judgment: false
  - id: D5
    description: "A tree removal is captured in quarantine, re-checked and put back on interrupt or mismatch"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_an_interrupted_tree_removal_puts_the_tree_back"
        status: pass
    human_judgment: false
---

# Phase 22 Plan 03: Type-only script proof and its removal Summary

**A script install's declared paths become type-only receipt artifacts that survive the vendor's own self-update, removal deletes only what was recorded and still matches, and an ownership candidate keeps the script method.**

## Performance

- **Duration:** not recorded (the start timestamp was not captured in this run)
- **Tasks:** 3 of 3 completed, one commit each
- **Files modified:** 8 (4 source, 4 test)

## Accomplishments

- `download.artifact_paths` gains a `script` branch: each declared `paths` entry, with `~` and `{omz_root}` expanded, is a `tree` when it ends in `/` and a `leaf` otherwise. Install, the receipt and uninstall read this one formula.
- `download.expand_script_token` resolves `{omz_root}` `$ZSH`-first (SPEC R8), falling back to `omz.omz_root(Path.home(), os.environ)`. It never runs a shell, and an unresolvable root yields None. `SCRIPT_ROOT_RESOLVERS` has the same key set as `model.SCRIPT_ROOTS`, and a test pins that.
- `receipts`: `tree` (a real directory, never a symlink) and `leaf` (a regular file, or a symlink with its readlink target) are fingerprinted type-only. `matches(..., trees=)` lets a leaf link match when its target is unchanged or lexically resolves inside one of the receipt's own trees. `drifted` and `broken_drift` pass the receipt's trees. `_read_artifact` refuses a `tree` or `leaf` that carries a non-null sha256, size, mtime_ns or key, a `tree` with a target, or a `leaf` with an empty target.
- `record(..., preexisting=)` and `preexisting_paths(method)`: a declared path is recorded only when the install created it, or the previous receipt already proved it (carry-forward). `preexisting=None` fails closed.
- `uninstall.remove_paths(..., trees=)`: a `tree` goes through `_remove_dir`'s quarantine rename and in-quarantine re-check. A `leaf` is only unlinked. `_quarantined` also lists tree siblings.
- `ownership._collect_candidates` chooses the artifact candidate's method from `_INSTALLER_KINDS` (script included), so a script-only tool found by its declared paths no longer resolves to `method=None` (R2-01).

## Task Commits

1. **Task 1: script installs record type-only paths that removal re-proves** - `8a2daac` (feat, tests and implementation together)
2. **Task 2: pin the type-only proof's fail-closed cases** - `79f5a32` (test, tests only; see Deviations 1 and 2)
3. **Task 3: pin tree artifact removal to the quarantine re-check** - `d3e7285` (test, tests only; see Deviations 1 and 2)

Each commit was made after `make validate` and `make test` exited 0 on that exact tree. Pre-commit hooks (ruff, format, pyright, bandit, vulture, shellcheck) passed on each commit. No `--no-verify`. No RED commit was made on its own.

## RED and GREEN evidence

### Task 1 RED

Command: `uv run pytest tests/test_uninstall.py tests/test_ownership.py -k "script_install_is_removed or self_update_inside or foreign_file_at_a_declared or declared_path_keeps_its_script_method" -q --no-cov -n 0`

```
FAILED tests/test_uninstall.py::test_a_script_install_is_removed_by_its_receipt
FAILED tests/test_uninstall.py::test_a_self_update_inside_the_tree_keeps_the_proof
FAILED tests/test_uninstall.py::test_a_foreign_file_at_a_declared_path_survives
FAILED tests/test_ownership.py::test_a_script_tools_declared_path_keeps_its_script_method
4 failed
E   TypeError: record() got an unexpected keyword argument 'preexisting'     (the first and third tests)
E   AssertionError: assert 'unknown' == 'installer'                          (the ownership test)
```

The self-update test calls `record(..., preexisting=...)` as well, so it fails with the same TypeError; that line was cut from the captured tail. The pytest exit status was non-zero (the run reported 4 failed); the exit code itself was not captured through the pipe.

### Task 1 GREEN

- Targeted selector (the same `-k`): 4 passed.
- Verify set `tests/test_uninstall.py tests/test_receipts.py tests/test_download.py tests/test_uninstall_e2e.py tests/test_ownership.py tests/test_version_status.py tests/test_update.py -n auto -q --no-cov`: no failures (dots only; exit status not captured through the pipe).
- Two GREEN-phase fixes before the commit, both in tests or formatting, not in the rule being tested:
  - One pre-existing ownership test (`test_undeclared_script_only_by_elimination_unchanged`) and four `receipts.matches` monkeypatch stubs in `tests/test_uninstall.py` were updated, listed under Changed Tests.
  - The new tracer tests first failed with an empty `removable` list. The cause was a fixture error, not a code error: `~` in a script path expands with `os.path.expanduser`, which reads the `HOME` environment variable, not the patched `Path.home`. The tests now use `monkeypatch.setenv("HOME", ...)`.
- `make validate`: exit 0 (after one E501 docstring line was shortened and `ruff format` reflowed `installer/receipts.py`).
- `make test`: exit 0, **5312 passed, 4 skipped**, coverage 96.11% (log in the session scratchpad).

### Task 2

- The Task 2 tests were written after Task 1's implementation was already in the tree, so there is no separate RED run. The first run of the selector (`-k "retargeted_link or tree_replaced or leaf_file_replaced or hash_or_key or round_trip or present_before_the_install or carries_forward or without_a_snapshot or root_resolvers or expand_script_token"`) passed all 20 items. These are regression guards, not RED tests. No implementation change was needed.
- Verify set `tests/test_receipts.py tests/test_download.py tests/test_uninstall.py tests/test_version_status.py -n auto`: no failures.
- `make validate`: exit 0. `make test`: exit 0, **5331 passed, 4 skipped**, coverage 96.23%.

### Task 3

- The Task 3 tests were also written after Task 1's implementation; the targeted run (`-k "tree_swapped or interrupted_tree or tree_quarantine_sibling or leaf_link_into_a_deleted"`) passed all 4. These are regression guards.
- Verify set `tests/test_uninstall.py tests/test_uninstall_e2e.py tests/test_app.py -n auto`: no failures.
- `make validate`: exit 0. `make test`: exit 0, **5335 passed, 4 skipped**, coverage 96.23%.

## Test counts (measured with `--collect-only`)

| File | Start (base 5f242f1) | After Task 1 | After Task 3 | Delta |
|---|---|---|---|---|
| tests/test_uninstall.py | 96 | 99 | 103 | +7 (T1 +3, T3 +4) |
| tests/test_receipts.py | 112 | 112 | 129 | +17 (T2: 7 functions and 10 parametrized cases) |
| tests/test_download.py | 101 | 101 | 103 | +2 (T2) |
| tests/test_ownership.py | 211 | 212 | 212 | +1 (T1) |
| tests/test_uninstall_e2e.py | 5 | 5 | 5 | 0 |

Full suite: 5308 passed at the start (the wave-1 ledger figure; not re-measured at this base) → 5312 after Task 1 → 5331 after Task 2 → **5335 after Task 3** (+27 = 4 + 19 + 4). Floors: test_receipts 129 ≥ 112 + 8; test_uninstall 103 ≥ 99 + 4.

## Changed or Deleted Existing Tests

No test was deleted. Each change below is required by the plan (the `trees=` keyword and the R2-01 decision).

| Test | Change | Reason |
|---|---|---|
| `tests/test_ownership.py::test_undeclared_script_only_by_elimination_unchanged` | `assert result.method is None` became `assert result.method == tool.methods[0]` (with an R2-01 comment). The equality implies `result.method.kind == "script"`; the form was not changed afterwards to keep Task 1's commit as it was. | R2-01: ownership now carries the script method (orchestrator note, cycle 3). Owner and confidence assertions are unchanged; production code was not changed to keep the old assertion. |
| `tests/test_uninstall.py::test_remove_paths_refuses_a_dir_replaced_after_its_final_check` (via the `_swap_dir_after_final_check` stub) | the `wrapper` stub gained `trees: Sequence[Path] = ()` and forwards it to the real `matches` | `remove_paths` now passes `trees=` to `receipts.matches` (plan decision). Assertions unchanged. |
| `tests/test_uninstall.py::test_remove_paths_refuses_a_replacement_keyed_through_an_escaping_symlink` (via `_escape_after_final_check`) | the `wrapper` stub gained `trees` and forwards it | same |
| `tests/test_uninstall.py::test_remove_paths_keeps_a_captured_dir_it_cannot_put_back` | same stub change as above (the failure came from the same `receipts.matches` stub path) | same |
| `tests/test_uninstall.py::test_remove_paths_puts_the_tree_back_when_interrupted[after_capture]` (`interrupt_recheck`) | the stub gained `trees` and forwards it | same |
| `tests/test_uninstall.py::test_an_interrupted_removal_that_cannot_put_back_names_the_quarantine` (`interrupt_and_occupy`) | the stub gained `trees` and forwards it | same |

The `Sequence` import was added to `tests/test_uninstall.py`, and `SCRIPT_ROOTS` to `tests/test_download.py`; `Sequence` was added to the `installer.uninstall` test imports in `tests/test_receipts.py`. These imports are additive.

## Review ledger (22-REVIEWS dispositions, plan Review Dispositions Ledger)

| Concern | How it is addressed in this plan's commits |
|---|---|
| R1-01 RED commits | RED output is recorded above only. Task 1 is one `feat` commit; Tasks 2 and 3 are test-only commits, with no RED commit alone. |
| R1-04 reader rejects what the writer writes | `_read_type_only` rejects only non-null sha256, size, mtime_ns and key (and a tree target). The writer is unchanged. `test_tree_and_leaf_round_trip` pins the raw JSON shape. |
| R1-05 existence after install adopts a foreign path | `record(..., preexisting=)`, `preexisting_paths`, carry-forward from the previous receipt. Tests: `test_a_declared_path_present_before_the_install_is_not_recorded`, `test_a_reinstall_carries_forward_what_the_previous_receipt_proved`, `test_record_without_a_snapshot_fails_closed`. Production wiring is still open (see Next Phase Readiness). |
| R2-01 script artifacts make ownership lose the script method | `_collect_candidates` uses `_INSTALLER_KINDS`. Test: `test_a_script_tools_declared_path_keeps_its_script_method`. The end-to-end refresh, `resolve_owner` and `UpdateService.run` test is 22-05's, as the plan states. |

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 - Test fixture bug] `~` expansion reads HOME, not Path.home**
- **Found during:** Task 1 GREEN
- **Issue:** the tracer tests planted files under `tmp_path` while `expand_script_token` expanded `~` through the sandbox `HOME` environment variable, so nothing was recorded.
- **Fix:** the new tests call `monkeypatch.setenv("HOME", str(tmp_path))`. The code is unchanged.
- **Committed in:** `8a2daac`

**2. [Rule 1 - Lint/format] E501 docstring and ruff format**
- **Found during:** Task 1 `make validate`
- **Fix:** one docstring shortened, and `ruff format installer/receipts.py` applied (formatter only).
- **Committed in:** `8a2daac`

### Plan deviations (recorded, not auto-fixed)

**1. Commit subjects for Tasks 2 and 3.** The plan named them `feat(22-03)`. Both tasks changed tests only, and the executor rules call for `test(22-03)` in that case, so they are `test(22-03)`.

**2. Tasks 2 and 3 were not RED.** The plan asks for RED first. Task 1's implementation already covered their behaviors, and reverting it to manufacture RED would have been churn, so the tests run as regression guards from their first run, as recorded above.

**3. Threat-register test name.** The threat table (T-22-06) names `test_tree_and_leaf_artifacts_with_extra_fields_are_rejected`, which does not exist. The rejection it describes (non-null sha256, size, mtime_ns, key and tree target) is covered by `test_tree_and_leaf_artifacts_with_a_hash_or_key_are_rejected`. The reader still ignores unrecognised extra keys for `file`, `dir` and `link`, as `test_reader_keeps_only_each_types_fields` pins; tree and leaf follow the same rule.

**4. Helper placement.** `preexisting_paths` takes `default_bin_dir` as a parameter to match `artifact_paths`. The plan's signature lists it that way too; nothing else differs.

**Total deviations:** 2 auto-fixed (both Rule 1 or lint), 4 plan deviations recorded above.

## Issues Encountered

- The harness refused several compound shell commands in this worktree ("too complex to verify"). Each was split into plain commands run from the worktree root. Multi-line commit messages were written to a scratch file and committed with `git commit -F`.
- `uv run` created `.venv` inside the worktree. It is gitignored and was not staged.
- The codegraph index belongs to the main checkout (a warning on each query). Codegraph was used only to orient; every Read and Edit targeted the worktree.
- A temporary debug test file was created under `tests/` during diagnosis. It was deleted before the first commit; `git status` showed only the intended files at every commit.
- The session guard in `tests/conftest.py` did not trip on any of the three `make test` runs.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. The new script `paths` read is covered by T-22-06, T-22-07, T-22-33, T-22-45 and T-22-08.

## Acceptance checks (plan's acceptance criteria, run on the final tree)

| Check | Expected | Actual |
|---|---|---|
| `def expand_script_token(token: str) -> str \| None` in installer/download.py | 1 | 1 |
| `sh -c` or `shell=True` in installer/download.py | 0 | 0 |
| `"v": 1` in installer/receipts.py | unchanged | 1 (schema not bumped) |
| `_INSTALLER_KINDS` in `_collect_candidates` (installer/ownership.py, line 1067) | at least 1 | 1 |
| test_receipts collected count | at least 112 + 8 | 129 |
| test_uninstall collected count | at least 99 + 4 | 103 |
| Suppression comments added (`type: ignore`, `pyright: ignore`, `noqa`, `nosec`) in the Task 1 commit and the Task 2 diff | 0 | 0 |
| `make validate` on the final code tree | exit 0 | exit 0 |
| `make test` on the final code tree | exit 0 | exit 0 (5335 passed, 4 skipped) |

## Self-Check: PASSED

Checked after writing this file:

- Created or modified source and test files exist in the worktree (the eight files under Key Files).
- Commits `8a2daac`, `79f5a32` and `d3e7285` are ancestors of HEAD.

## Next Phase Readiness

- **Production wiring is still open.** `installer/engine.py:286` (`install_tool`) and `installer/update.py:364` (`update._perform`) call `receipts.record` without `preexisting`, so `None` fails closed. Until 22-06 and 22-05 take the `preexisting_paths` snapshot before a method runs and pass it, a script install records no declared-path proof and script removal behaves as it did before this plan. Plans 22-05 and 22-06 must wire it.
- 22-05 can use `download.expand_script_token` for `update` tokens. `SCRIPT_ROOT_RESOLVERS` is the single resolver.
- 22-06 can pass the plan's trees to `remove_paths(..., trees=...)` after a vendor `remove` deletes a tree. The lexical rule already holds in that case (`test_a_leaf_link_into_a_deleted_tree_is_still_removed`).
- Not touched by this plan, as the plan requires: `STATE.md`, `ROADMAP.md`, and the other `.planning/` files. The only `.planning` change is this SUMMARY.

---
*Phase: 22-method-lifecycle-contract*
*Completed: 2026-11-04*
