---
phase: 22-method-lifecycle-contract
plan: "13"
subsystem: testing
tags: [e2e, container, leftovers, receipts, podman, fedora, lifecycle]

requires:
  - phase: 22-06
    provides: "CLI exits 1 on a failed removal; run_uninstall returns (removed, failed); receipt proofs"
  - phase: 22-08
    provides: "script stanza paths/remove/update data, config_paths, stores kept on purpose"
provides:
  - "HOME baseline at the end of cmd_bootstrap; leftover and removable-receipt checks after the uninstall in cmd_pass2"
  - "scripts/e2e-residue-allowlist.txt (documented residue classes, one reason per entry)"
  - "widened manual-name parser for `manual — you run:` rows"
affects: [phase-22-close, 24-debian-arch-e2e]

actuals:
  tokens: 0          # not measured for this halted run
  tasks: 2           # tasks 1 and 2 completed; task 3 halted
  commits: 2         # MEASURED: git rev-list --count 892f4ff5..HEAD (before this summary commit)

commits: 2
plan_head_before: 892f4ff5a34ccf1c70afb05a8420c341cc328bbf
plan_head_after: 5cd762b
status: halted
---

# Phase 22 Plan 13: Container e2e leftover and receipt checks Summary

**The container e2e now compares the tester's HOME before install and after uninstall and checks every removable receipt is gone; both self-tests pass, but the recorded Fedora podman run halted on a pnpm group-removal defect before the new checks ran.**

## Status

- Tasks 1 and 2: complete, one green `feat(22-13)` commit each.
- Task 3 (one recorded Fedora run ending `TRACER_LEFTOVER_OK`): **not achieved**. The run reached pass 2 and stopped at `TRACER_UNINSTALL_INCOMPLETE exit=1`, caused by a removal defect (see "Removal defects found by the e2e"). Per the plan, that defect is recorded and not allowlisted. No data fix was committed. The container was removed.

## Commits

| # | Hash | Subject |
|---|------|---------|
| 1 | 14f70eb | feat(22-13): compare HOME listings before install and after uninstall |
| 2 | 5cd762b | feat(22-13): count manual handoff rows as explained blockers |

Each commit holds its tests with the implementation. Pre-commit hooks passed on both. No `--no-verify`, no attribution trailers. `make validate` and `make test` exited 0 on the tree of each commit.

## Test counts

| Point | `make validate` | `make test` |
|---|---|---|
| Baseline (ledger, after wave 6) | 0 | 5523 passed, 4 skipped |
| After Task 1 (14f70eb) | 0 | 5536 passed, 4 skipped, coverage 96.32% |
| After Task 2 (5cd762b) | 0 | 5537 passed, 4 skipped |

`tests/test_container_e2e_receipts.py`: 28 existing tests plus 13 new in Task 1 (41 total, all passing), plus 1 new in Task 2 (42 total, all passing).

## RED / GREEN evidence

### Task 1 RED (13 new tests, before any harness edit)

Command: `uv run pytest tests/test_container_e2e_receipts.py -k "planted or clean_run or as_roots or harness_dir or never_exempts or missing_baseline or baseline_is_still or manager_receipt or allowlist_gives or wired_after or home_listing or receipt_paths or host_probe" --no-cov -n 0`

```
... AssertionError: receipt_paths() is not defined in the script
... AssertionError: allowed_prefixes() is not defined in the script
13 failed, 28 deselected in 0.27s
```
Every new test failed on a missing function or file. Not committed alone.

### Task 1 GREEN

- Receipts file: `41 passed` (exit 0). `bash -n scripts/container-e2e-verify.sh` exit 0.
- `uv run shellcheck -x scripts/container-e2e-verify.sh | grep -c '^In '`: 3 before, 3 after (the same three SC2016 info notes; the count did not grow).
- `make validate`: exit 0. `make test`: `5536 passed, 4 skipped`, exit 0.

One intermediate failure, fixed before commit: the host-probe test passed the host PATH, which the conftest strips of real-home entries, so `uv` was not found. It now uses the same `uv` stub as the existing receipt tests.

### Task 2 RED (before the parser change)

Command: `uv run pytest tests/test_container_e2e_receipts.py -k you_run_rows --no-cov -n 0`

```
E   AssertionError: ACC_NOT_ATTEMPTED=0 ACC_CRASHED=0 ACC_INSTALLED=2 ACC_RUNS=1 ACC_SUMMARIES=1
E   assert 1 == 0
```
The `zsh` row was not captured, so `dependency_failures_explained` rejected the explained dependency.

### Task 2 GREEN

- The first widened `sed` left the command text in the output (no end anchor). The second, anchored with `you run: .*$`, passed. The assertion was then changed to compare `splitlines()` (the fixture had no trailing newline and GNU `sed` preserves that).
- Receipts file: exit 0. `grep -c "you run: " scripts/container-e2e-verify.sh`: 1. `make validate`: exit 0. `make test`: `5537 passed, 4 skipped`, exit 0.

## Changed or deleted existing tests

| Test | Change | Reason |
|------|--------|--------|
| `tests/test_shell_scripts_path.py::test_no_unclassified_accumulating_path_line_in_any_shell_script` | The classified line numbers for `container-e2e-verify.sh` moved 324→326 and 344→346, and one entry was added at 548 (`receipt_paths`'s one-shot `export PATH=` inside `su -c`, same reason text) | The plan's required `cmd_bootstrap` baseline lines sit above those lines, and `receipt_paths` is a new `su -c` PATH prefix. The test requires exact line equality by design. No assertion was loosened. |

No other existing test was changed or deleted.

## Task 3: recorded Fedora podman run (halted)

Preconditions (all passed): `scripts/detect-container-runtime.sh` printed `CONTAINER_TOOL=podman`; `podman run --rm alpine echo ok` printed `ok`; `uv run --no-sync python -c "import installer"` printed `IMPORT_OK`; no `tools-installer-e2e` container existed.

Run: `make e2e` from the worktree, output in `.e2e-artifacts/make-e2e.log` (gitignored). Date 2026-11-04, base `892f4ff`, head `5cd762b`.

Tracer lines from `pass2-transcript.log` and the e2e log:

```
PASS1_COUNTS installed=67 updated=0 skipped=5 failed=0 dependency_failed=0 mismatched=0 blocked=3 manual=14 not_attempted=0 crashed=0 post_run_errors=0 summaries=1 runs=1 setup_exit=0
TRACER_CLEAN_INSTALL_OK installed=67 updated=0 skipped=5 failed=0 blocked=3 manual=14
TRACER_RECEIPT_OK tool=yq
TRACER_RERUN_OK installed=0 updated=1 skipped=71 failed=0 dependency_failed=0 blocked=3 manual=14
TRACER_RECEIPT_PRE_UNINSTALL_OK tool=yq
TRACER_RECEIPT_PATHS_OK recorded=103 removable=61
TRACER_UNINSTALL_INCOMPLETE exit=1
make: *** [Makefile:57: e2e] Error 1      (make exit 2)
```

Not reached: `TRACER_UNINSTALL_OK`, `assert_receipt_removed`, `assert_removed_receipts_gone`, `assert_no_leftovers`, reinstall, `TRACER_CONTAINER_TEARDOWN_OK`. So no `TRACER_LEFTOVER_OK`, `TRACER_LEFTOVER path=`, or `TRACER_RECEIPTS_GONE_OK` line exists yet.

Container check after the run: `podman ps -a --filter name=tools-installer-e2e --format '{{.Names}}'` printed nothing. The `all` trap removed the container.

### Removal defects found by the e2e

**D-1. pnpm co-install group removal breaks the second removal (not a leftover).**

Transcript lines (`pass2-transcript.log`):

```
colima: runs brew uninstall colima
graphify: runs uv tool uninstall graphifyy
mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli
puppeteer: runs pnpm remove --global puppeteer
Warning: pnpm group mmdc: all its members are removed together.
puppeteer: remove failed — Error: ERR_PNPM_GLOBAL_PKG_NOT_FOUND
TRACER_UNINSTALL_INCOMPLETE exit=1
```

Install side (`pass1-transcript.log`): `mmdc` and `puppeteer` were installed together as one pnpm global group (`+ puppeteer 25.16.0`, `+ @mermaid-js/mermaid-cli 12.2.0`), each with its own receipt.

Cause: removing `mmdc` removed its group, including `puppeteer`. The remover then runs `pnpm remove --global puppeteer` for puppeteer's own receipt, and pnpm reports the package already gone. `remove_tool` treats that as a failed removal, keeps the receipt, and the CLI exits 1 (the 22-06 contract working as designed).

Classification: removal logic in `installer/app.py` / `installer/uninstall.py` (22-06 `remove_tool`, 22-09 `pnpm_removal_packages`), not a must-clear path and not a residue class. Per the plan, it is not allowlisted. The fix would be a code change in the removal ordering or in how a co-group member's already-removed state is proven. That is outside this plan's data scope, so it is not made here. Needed next: a removal-plan fix (a member of a pnpm group already removed in the same run is proven gone by `pnpm list --global` and its receipt retired, or the group's members are removed as one step), then one more `make e2e` run.

Not run: the plan's optional second and third runs. The defect is deterministic, so a rerun would fail identically without a fix.

## Deviations from Plan

**1. [Halted - Task 3] The recorded run did not reach the leftover check.** The uninstall step failed on D-1 above. Plan rule for anything not a leftover: record and stop, not allowlist. Stopped. No registry data or allowlist entry was added for this run.

**2. [Rule 3 - Blocking] Test PATH and conftest.** The host-probe test passed the host PATH to the child shell; the conftest strips real-home entries, so `uv` was not found. Fixed by using the existing `_uv_stub()` (no test assertion weakened).

**3. [Rule 1 - Bug, Task 2] Parser regex.** The first widened `sed` had no end anchor, so it left the command text in the captured tool id. Fixed in the same commit.

**4. Extra tracer lines.** Beyond the plan's list, the harness prints `TRACER_HOME_BASELINE entries=N`, `TRACER_RECEIPT_PATHS_OK recorded=N removable=M`, `TRACER_RECEIPT_PATHS_FAILED`, and `TRACER_LEFTOVER_PROBE_FAILED` (a failed host probe fails loudly instead of being read as an empty list). All are diagnostics for the same checks.

**5. Allowlist is the initial set only.** `scripts/e2e-residue-allowlist.txt` holds the plan's initial classes, narrowed to the subtrees 22-08 named: `.local/share/pnpm/global`, `.bun/install`, `.volta/tools`, `.local/share/fnm/node-versions`, `.local/share/uv` (uv stores kept on purpose). Narrow entries keep pnpm's undeclared `dist/` and volta's default shims visible to the must-clear check. No survivor has been observed yet, so no entry was added for one.

## Known gaps (not checked by the run)

- A receipt whose removal level is `none` is not in `removable-receipts.txt`, so its absence is not checked, and `.local/state/tools-installer` is allowlisted. A drifted receipt left behind would pass both checks. This follows the plan's removable-receipt definition and the R1-11 sign-off, but it is a real hole.
- The removable check's tool list is computed with `removal_plan(tool, ~/.local/bin)` only; the probe receipt in the self-test (`removal_plan` level != none for `yq`) is covered by the probe's presence check, not by content.

## Self-Check

- Commits `14f70eb` and `5cd762b` are ancestors of HEAD (`git log --oneline`).
- The e2e container is gone (`podman ps -a` empty after the run).
- No file under `.planning/` other than this SUMMARY was modified. STATE.md and ROADMAP.md are untouched.
- Branch `worktree-agent-a61d0170e621aea3e`, HEAD not on a protected branch, sentinel matched at each commit.

## Re-run after fix

Fix for D-1: `4190481` (`fix(22): pnpm group removal treats an already-removed member as removed`). Measured first in a disposable `fedora:latest` podman container (node 22.23.1, pnpm 12.16.1, the executor's exact argv `pnpm add -g --allow-build=puppeteer puppeteer@^25`, then `pnpm add -g --allow-build=puppeteer @mermaid-js/mermaid-cli,puppeteer@^25`): after the group install `pnpm ls --global` lists one group (`@mermaid-js/mermaid-cli`, `puppeteer`). `pnpm remove --global @mermaid-js/mermaid-cli` exits 0 and the list then shows neither package. `pnpm remove --global puppeteer` then exits 1 with `Error: ERR_PNPM_GLOBAL_PKG_NOT_FOUND` / `Cannot remove 'puppeteer': not found in global packages`. Removing `puppeteer` first gives the mirror result (both gone, then `@mermaid-js/mermaid-cli` not found). So any member's removal removes the whole group. `remove_tool` now reads that code on a pnpm removal as the package already gone, and the group warning says `removing {removed} removes the whole group, {others} included.` (UI-SPEC amendment 2026-11-04, A13 superseded).

Run: `make e2e` from the main checkout, 2026-11-04 04:05–04:37, head `4190481`, log `.e2e-artifacts/make-e2e-rerun.log` (gitignored).

```
PASS1_COUNTS installed=67 updated=0 skipped=5 failed=0 dependency_failed=0 mismatched=0 blocked=3 manual=14 not_attempted=0 crashed=0 post_run_errors=0 summaries=1 runs=1 setup_exit=0
TRACER_CLEAN_INSTALL_OK installed=67 updated=0 skipped=5 failed=0 blocked=3 manual=14
TRACER_RECEIPT_OK tool=yq
TRACER_RERUN_OK installed=0 updated=1 skipped=71 failed=0 dependency_failed=0 blocked=3 manual=14
TRACER_RECEIPT_PRE_UNINSTALL_OK tool=yq
TRACER_RECEIPT_PATHS_OK recorded=103 removable=61
mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli
puppeteer: runs pnpm remove --global puppeteer
Warning: pnpm group mmdc: all its members are removed together.
TRACER_UNINSTALL_OK
TRACER_RECEIPT_REMOVAL_OK tool=yq
TRACER_RECEIPTS_GONE_OK count=61
TRACER_LEFTOVER path=...   (27 roots, listed below)
make: *** [Makefile:57: e2e] Error 1      (make exit 2)
```

D-1 is closed: no `remove failed` line, uninstall exit 0, every removable receipt gone. `TRACER_LEFTOVER_OK` did **not** appear: the run stopped at `assert_no_leftovers`, so reinstall and `TRACER_CONTAINER_TEARDOWN_OK` were not reached. Container check after the run: `podman ps -a --filter name=tools-installer-e2e` printed nothing.

### D-2. Leftovers after a clean uninstall (new, not a pnpm group defect)

27 top-most roots that are new against the HOME baseline and outside the allowlist (`home-after.txt`). None is allowlisted here. Classified from the listing:

- **Undeclared sibling executables** (real removal gaps: the method's `paths` names only the main binary): `.bun/bin` (`bunx`), `.local/share/pnpm/bin` (`pn`, `pnpx`, `pnx`), `.volta/bin` (volta's `node`, `npm`, `npx`, `pnpm`, `yarn` default shims).
- **Tool runtime state and caches written while the tools ran** (residue classes need a decision: declare or allowlist with a reason): `.claude.json`, `.codegraph`, `.config/draw.io`, `.config/glow`, `.config/google-chrome-for-testing`, `.config/rtk`, `.gradle`, `.npm`, `.local/share/opencode`, `.local/share/rtk`, `.local/share/pnpm/store`, `.local/state/claude`, `.local/state/fnm_multishells`, `.local/state/gh`, `.local/state/opencode`, `.local/state/pnpm`, `.volta/cache`, `.volta/layout.v4`, `.volta/log`, `.volta/tmp`, `.volta/volta.lock`.
- **Emptied parents or lock stubs**: `.local/opt` (empty), `.local/share/fnm/aliases` (empty), `.homebrew` (`trust.json.lock` only).

D-2 needs registry `paths` declarations for the sibling executables and a residue-class decision for the rest. That is 22-13's data scope across about 15 tools, not the D-1 remover fix, so it is recorded and not fixed here. Needed next: classify and fix D-2, then one more `make e2e`.

## D-2 closure

Fix commit `9cf3a69` (`fix(22-13): declare sibling executables and classify e2e runtime residue`), on top of base `1b10477`. One `make e2e` run from the worktree (disposable `tools-installer-e2e` Fedora container, removed afterwards). No second or third run was needed.

```
PASS1_COUNTS installed=67 updated=0 skipped=5 failed=0 dependency_failed=0 mismatched=0 blocked=3 manual=14 not_attempted=0 crashed=0 post_run_errors=0 summaries=1 runs=1 setup_exit=0
TRACER_CLEAN_INSTALL_OK installed=67 updated=0 skipped=5 failed=0 blocked=3 manual=14
TRACER_RECEIPT_OK tool=yq
TRACER_RERUN_OK installed=0 updated=1 skipped=71 failed=0 dependency_failed=0 blocked=3 manual=14
TRACER_RECEIPT_PRE_UNINSTALL_OK tool=yq
TRACER_RECEIPT_PATHS_OK recorded=113 removable=61
TRACER_UNINSTALL_OK
TRACER_RECEIPT_REMOVAL_OK tool=yq
TRACER_RECEIPTS_GONE_OK count=61
TRACER_LEFTOVER_OK
TRACER_REINSTALL_OK installed=61 updated=0 skipped=11 failed=0 dependency_failed=0 blocked=3 manual=14
TRACER_CONTAINER_TEARDOWN_OK
make e2e exit=0
```

`podman ps -a --filter name=tools-installer-e2e` is empty after the run.

### How each of the 27 roots was classified

| Root | Classification |
|------|----------------|
| `.bun/bin` | declared leaf: bun `paths` gains `~/.bun/bin/bunx` (created by the script's `completions` step); dir empty after |
| `.local/share/pnpm/bin` | declared leaves: pnpm `paths` gains `pn`, `pnpx`, `pnx`; dir empty after |
| `.volta/bin` | declared leaves: volta `paths` gains `node`, `npm`, `npx`, `pnpm`, `yarn`, `yarnpkg`; dir empty after |
| `.config/glow` | `config_paths` for glow (`glow.yml` in `XDG_CONFIG_HOME/glow`, per glow main.go) |
| `.local/opt`, `.local/share/fnm/aliases` | harness rule: `home_listing` skips empty directories (both empty after uninstall) |
| `.claude.json`, `.codegraph`, `.gradle`, `.npm` | allowlist: runtime state or cache written by tool runs |
| `.config/draw.io` | allowlist: Electron profile (caches, GPU and local storage), not clearly config |
| `.config/google-chrome-for-testing` | allowlist: browser profile and crash reports written by a browser run |
| `.config/rtk`, `.local/share/rtk` | allowlist: rtk runtime state; rtk removal is a later user phase (not declared) |
| `.homebrew` | allowlist `.homebrew/trust.json.lock` only: brew lock file |
| `.local/share/opencode`, `.local/state/claude`, `.local/state/gh`, `.local/state/opencode` | allowlist: tool runtime state |
| `.local/share/pnpm/store`, `.local/state/pnpm`, `.local/state/fnm_multishells` | allowlist: pnpm store (22-08 store roots) and runtime state |
| `.volta/cache`, `.volta/layout.v4`, `.volta/log`, `.volta/tmp`, `.volta/volta.lock` | allowlist: volta cache, layout, log, temp and lock files |

Counts: 3 declared leaf sets, 1 `config_paths`, 2 harness-rule cases, 21 allowlist entries.

### Decisions and trade-offs

- **Empty parents (harness rule, not allowlist).** Allowlisting `.local/opt` would have covered its whole subtree and hidden any undeclared install under it, which is exactly what this check exists to catch. Skipping empty directories in `home_listing` (one line) only hides directories that hold no file. Trade-off: a surviving empty must-clear or receipt-recorded directory is no longer reported. This is recorded as a shortcut in the function comment.
- **Extra leaf `yarnpkg`.** The brief listed five volta shims. The after-listing and the disposable-container run both show `yarnpkg` too, so it is declared.
- **`bunx`.** The bun install script does not write it directly. Its `$exe completions` call makes the bun binary link `bunx` beside itself, so it is declared with that cited.
- **draw.io.** Its profile directory is mostly Electron caches and storage, so it is allowlisted rather than declared as `config_paths`.
- **Allowlist header.** The header says a tool's own files belong in `paths` or `config_paths`. The runtime-state entries above are not install artifacts; they are the residue classes the brief's decision 2 names. This is noted as a deliberate reading of the header.
- **Not verified.** The macOS pnpm stanza does not get the `pn`, `pnpx`, `pnx` leaves, because those aliases were not checked on macOS. 22-08's phrase "plus any other ~/.volta/ content beyond the three leaves" is superseded for the shim leaves by this decision.

### Tests

- RED (before the change, same commit's tests): 5 failing, `test_script_lifecycle_data[bun/volta/pnpm]`, `test_glow_declares_its_documented_config_dir`, `test_home_listing_skips_empty_directories`.
- GREEN: `make validate` exit 0. `make test`: `5543 passed, 4 skipped`, coverage 96.32%, exit 0. Shellcheck notes on the harness stay at 3, and the harness line count is unchanged, so the classified PATH line numbers hold.
- A dry run of the pure `new_leftovers` check on the real 22-13 listings, with the new declarations applied, passed before the e2e (`TRACER_LEFTOVER_OK`). The same listings produced 27 roots before the change.
