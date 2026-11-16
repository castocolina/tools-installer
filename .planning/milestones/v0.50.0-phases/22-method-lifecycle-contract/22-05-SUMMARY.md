---
phase: 22-method-lifecycle-contract
plan: "05"
subsystem: update
tags: [update, script-update, sdkman, oh-my-zsh, pinned-release, refusal, receipts, tdd]
commits: 3
plan_head_before: 853b1afed4ef6e2ed9919508053f4995bb9d2af7
plan_head_after: 69cc9d84dda15d38e59cf1114d7e437daac00cb1

requires:
  - phase: 22-01
    provides: "script method keys paths/remove/update/writable_prefix, SCRIPT_ROOTS"
  - phase: 22-03
    provides: "download.expand_script_token ($ZSH-first {omz_root}), tree/leaf artifacts, receipts.record(preexisting=), preexisting_paths, script candidate keeps its method (R2-01)"
  - phase: 22-04
    provides: "prefix_writable and the wave-2 preflight (no update-path dependency beyond the wave order)"
provides:
  - "update._update_installer_owned: a script that declares update runs that argv through the runner (no shell); a token that cannot expand raises UpdateError naming the tool and the token"
  - "update._perform: preexisting snapshot taken before the owner branch and passed to receipts.record (R1-05, update half)"
  - "executors.sdk_pipeline(argv): the one sourced sdk invocation, used by _sdkman and by the update branch"
  - "download.pinned_method (moved unchanged from verify_registry._is_pinned_method) and update.PINNED_DETAIL"
  - "update_refusal pinned branch; catalog action_update_tool refuses a pinned method before the lock, the re-resolve and the worker"
affects: [22-06, 22-08, 22-09, 22-11, 22-13]

actuals:
  tokens: 7230      # chars/4 over the realized diff (28919 bytes of `git diff 853b1af..HEAD`)
  tasks: 3
  commits: 3        # MEASURED: git rev-list --count 853b1af..HEAD

tech-stack:
  added: []
  patterns:
    - "A declared script update is the vendor's own argv: closed-root token expansion, literal argv, no shell"
    - "One sourced sdk invocation (sdk_pipeline) shared by candidate installs and the bootstrap update"
    - "One pinned predicate (download.pinned_method) read by update_refusal, verify_registry and the catalog key"
    - "The pre-update snapshot is taken before the owner branch runs anything, so a receipt records only what the update created"

key-files:
  created: []
  modified:
    - installer/update.py
    - installer/executors.py
    - installer/download.py
    - installer/verify_registry.py
    - installer/catalog_tui.py
    - tests/test_update.py
    - tests/test_executors.py
    - tests/test_catalog_tui.py
    - tests/test_session.py

key-decisions:
  - "A declared script update runs its expanded argv directly through the runner; an sdk-led argv goes through executors.sdk_pipeline (D-15, ledger UI-SPEC note: sdk is a shell function)"
  - "An unresolvable {omz_root} raises UpdateError(\"cannot resolve {token} for the {tool_id} update\"); perform_update turns it into status failed (review R1-07)"
  - "The pinned gate is method-derived (pinned_method: app or tarball, url holds {ver}, version and sha256 set); no UpdateTarget field (D-14, ledger Q4)"
  - "The catalog's pinned refusal runs after the unknown-owner check and before self._updates.begin, so no lock, re-resolve or worker starts (UI-SPEC A10)"
  - "The pinned refusal detail is exactly 'pinned; update outside or re-pin' and the catalog line is 'cannot update {id}: pinned; update outside or re-pin' (warn), with one RefreshRequested"

requirements-completed: [LIFE-05]
# LIFE-05: the pinned refusal is delivered and proven (engine, review and catalog share one predicate).
# LIFE-06: the update behaviour (declared argv, OMZ root, SDKMAN sourced invocation) is delivered and
# proven with fixture methods only. The registry `update` data for oh-my-zsh and sdkman lands in 22-08,
# so LIFE-06 is not marked complete by this plan.

coverage:
  - id: D1
    description: "u on Oh-My-Zsh runs <omz root>/tools/upgrade.sh under the $ZSH-first root, with no shell"
    requirement: "LIFE-06"
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_omz_update_runs_its_upgrade_script_under_zsh"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_omz_update_prefers_zsh_when_both_roots_exist"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_omz_update_falls_back_to_the_default_dir"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_omz_update_without_a_root_fails_without_running"
        status: pass
    human_judgment: false
  - id: D2
    description: "A vendor update's exit code decides the outcome; a script without update still re-runs its installer"
    requirement: "LIFE-06"
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_a_vendor_update_exit_code_decides"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_a_script_without_update_reruns_its_installer"
        status: pass
    human_judgment: false
  - id: D3
    description: "A script tool found by its declared paths runs its declared update through production ownership (refresh -> resolve_owner -> run)"
    requirement: "LIFE-06"
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_a_script_tool_found_by_its_declared_paths_runs_its_declared_update"
        status: pass
    human_judgment: false
  - id: D4
    description: "An update never adopts a declared path that existed before it"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_an_update_never_adopts_a_path_that_existed_before_it"
        status: pass
    human_judgment: false
  - id: D5
    description: "u on the SDKMAN bootstrap runs sdk selfupdate through the shared sourced invocation; candidates stay refused"
    requirement: "LIFE-06"
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_sdkman_bootstrap_update_runs_selfupdate_sourced"
        status: pass
      - kind: unit
        ref: "tests/test_executors.py#test_sdk_pipeline_matches_the_candidate_installer"
        status: pass
    human_judgment: false
  - id: D6
    description: "u on a pinned app or tarball runs nothing, takes no lock and ends with one refresh pass; headless rows read blocked"
    requirement: "LIFE-05"
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_a_pinned_app_is_refused_by_update_refusal"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_perform_update_on_a_pinned_app_runs_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_u_on_a_pinned_app_is_refused_before_the_lock"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_a_headless_update_row_on_a_pinned_app_reads_blocked"
        status: pass
    human_judgment: false
  - id: D7
    description: "An unpinned app still updates"
    requirement: "LIFE-05"
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_an_unpinned_app_still_updates"
        status: pass
    human_judgment: false

duration: not recorded (start timestamp was not captured in this run)
completed: 2026-11-04
status: complete
---

# Phase 22 Plan 05: Declared script updates and the pinned-release refusal Summary

**`u` runs a script's own declared update argv (Oh-My-Zsh's `upgrade.sh` under the `$ZSH`-first root, SDKMAN's `sdk selfupdate` through the sourced invocation), and refuses a pinned app or tarball before anything starts, through one predicate the engine, the review and the catalog key share.**

## Performance

- **Duration:** not recorded (the start timestamp was not captured in this run)
- **Tasks:** 3 of 3 completed, one `feat(22-05)` commit each (test and implementation together)
- **Files modified:** 9 (5 source, 4 test)

## Accomplishments

- `update._update_installer_owned` takes a required `tool_id` (passed by `_perform`). A script whose `update` is a list expands each token with `download.expand_script_token`; a None token raises `UpdateError("cannot resolve {token} for the {tool_id} update")`; the argv goes to the runner as a list, with no shell. A script without `update` still goes through `executors.execute` (the re-run path).
- An `update` argv whose first token is `sdk` goes through `executors.sdk_pipeline(argv)`. `_sdkman` now calls the same `sdk_pipeline`, so candidate installs and the bootstrap update share one sourced invocation. SDKMAN candidates keep their `sdk upgrade {candidate}` refusal (D-15).
- `_perform` takes `receipts.preexisting_paths(method)` before its owner branch runs anything and passes it to `receipts.record(..., preexisting=...)`. The update half of R1-05 is wired; the install half (`engine.py`) stays with 22-06.
- `download.pinned_method` is the predicate moved unchanged from `verify_registry._is_pinned_method`, beside `pinned_url`. `verify_registry` imports it. `update.PINNED_DETAIL = "pinned; update outside or re-pin"`, and the pinned branch of `update_refusal` (after the sdkman branch) returns `unsupported` with that detail.
- `catalog_tui.action_update_tool` refuses a pinned method after the unknown-owner check and before `self._updates.begin`: a warn line `cannot update {id}: pinned; update outside or re-pin`, one `RefreshRequested`, no lock, no re-resolve, no worker.
- The headless UPDATE path (`session.execute_plan` through `UpdateService.run`) reads `blocked` with the same detail, because the refusal comes from `update_refusal`.

## Task Commits

1. **Task 1: a declared script update argv runs on `u`** - `387c3a7` (feat, tests and implementation together)
2. **Task 2: sdk commands share one sourced invocation** - `7437910` (feat, tests and implementation together)
3. **Task 3: refuse `u` on a pinned app before the lock** - `69cc9d8` (feat, tests and implementation together)

Each commit was made after `make validate` and `make test` exited 0 on that exact tree. The pre-commit hooks (ruff, format, pyright, bandit, vulture) passed on each commit. No `--no-verify`. No RED-only commit.

## RED and GREEN evidence

Every RED run below was executed before the implementation of its task. The RED output stays in this SUMMARY only, as R1-01 requires.

### Task 1 RED

Command: `uv run pytest tests/test_update.py -k "omz_update or vendor_update_exit or without_update_reruns or never_adopts or found_by_its_declared_paths" --no-cov -n 0`

```
FAILED tests/test_update.py::test_omz_update_runs_its_upgrade_script_under_zsh
FAILED tests/test_update.py::test_omz_update_prefers_zsh_when_both_roots_exist
FAILED tests/test_update.py::test_omz_update_falls_back_to_the_default_dir
FAILED tests/test_update.py::test_omz_update_without_a_root_fails_without_running
FAILED tests/test_update.py::test_a_vendor_update_exit_code_decides
FAILED tests/test_update.py::test_an_update_never_adopts_a_path_that_existed_before_it
FAILED tests/test_update.py::test_a_script_tool_found_by_its_declared_paths_runs_its_declared_update
7 failed, 1 passed, 90 deselected
E  AssertionError: assert [['sh', '-c',...all.sh | sh']] == [['t', 'upgrade']]    (the R2-01 test)
```

`test_a_script_without_update_reruns_its_installer` passed at RED. It is a regression guard for the re-run path, not RED. The R2-01 test reached `status == "updated"` through production ownership, which shows the 22-03 `_collect_candidates` fix works; it failed only because the re-run path ran the curl pipeline instead of the declared argv.

### Task 1 GREEN

- Targeted selection (the same `-k`): `8 passed, 90 deselected`, exit 0.
- Wider verify `uv run pytest tests/test_update.py tests/test_run.py tests/test_version_status.py tests/test_ownership.py -n auto -q --no-cov`: exit 0.
- `make validate`: exit 0 (after two typed-helper fixes in the test: pyright strict rejected untyped `**_kwargs` lambdas, replaced by named functions typed like `test_version_status.py`).
- `make test`: exit 0, **5354 passed, 4 skipped**.
- Acceptance: `expand_script_token(` in update.py = 1; `tool_id=target.tool.id` = 6; `preexisting=` = 1; `sh -c` or `shell=True` = 0.

### Task 2 RED

Command: `uv run pytest tests/test_update.py tests/test_executors.py -k "sdkman_bootstrap_update or sdk_pipeline_matches or sdkman_owned" --no-cov -n 0`

```
FAILED tests/test_update.py::test_sdkman_bootstrap_update_runs_selfupdate_sourced
  AssertionError: assert ['sdk', 'selfupdate'] == ['bash', '-c']
FAILED tests/test_executors.py::test_sdk_pipeline_matches_the_candidate_installer
  AttributeError: module 'installer.executors' has no attribute 'sdk_pipeline'
2 failed, 2 passed, 184 deselected
```

The two passing tests are the existing sdkman candidate refusals (`test_sdkman_owned_is_unsupported`, `test_sdkman_owned_update_refuses_with_real_command`), kept as regression guards.

### Task 2 GREEN

- Targeted selection: `9 passed, 179 deselected`, exit 0.
- Wider `tests/test_update.py tests/test_executors.py -n auto`: exit 0.
- `make validate`: exit 0. `make test`: exit 0, **5356 passed, 4 skipped**.
- Acceptance: `def sdk_pipeline(` = 1; `sdkman-init.sh" &&` = 1.

### Task 3 RED

Command: `uv run pytest tests/test_update.py tests/test_catalog_tui.py tests/test_session.py -k "pinned_app or unpinned_app" --no-cov -n 0`

```
FAILED tests/test_update.py::test_a_pinned_app_is_refused_by_update_refusal
  E  assert None is not None
FAILED tests/test_update.py::test_perform_update_on_a_pinned_app_runs_nothing
  E  AssertionError: a pinned app must not be re-downloaded   (the guard was reached)
FAILED tests/test_catalog_tui.py::test_u_on_a_pinned_app_is_refused_before_the_lock
  E  AssertionError: condition never became true within the polling budget
FAILED tests/test_session.py::test_a_headless_update_row_on_a_pinned_app_reads_blocked
  E  assert 'crashed' == 'blocked'
4 failed, 1 passed, 423 deselected
```

`test_an_unpinned_app_still_updates` passed at RED (regression guard). Each RED test that reaches the real updater stubs `installer.apps.update_app` or `update.apps.update_app` first, so no RED run could download.

### Task 3 GREEN

- Targeted selection `-k "pinned_app or unpinned_app"` across the three files: first run after implementation `1 failed, 4 passed` (the catalog pilot's refresh-count assertion, see Deviations 2); after the relative count and the highlight-patch removal (Deviations 2 and 3), `5 passed`.
- Verify set `uv run pytest tests/test_update.py tests/test_catalog_tui.py tests/test_session.py tests/test_plan.py tests/test_verify_registry.py -n auto -q --no-cov`: exit 0.
- `make validate`: exit 0 (after the ruff I001 import sort on `catalog_tui.py`, two wrapped test lines, and `ruff format` on the touched files).
- `make test`: exit 0, **5361 passed, 4 skipped**.
- Acceptance: `PINNED_DETAIL = "pinned; update outside or re-pin"` = 1; in `action_update_tool`, `pinned_method(` is at line 54 and `self._updates.begin(` at line 61 and `begin_mutation(` at 63; `_is_pinned_method` remaining in verify_registry = 0.
- Suppressions added by this plan: 0 (`git diff 853b1af` added lines matching `type: ignore|pyright: ignore|noqa|nosec`: 0).

Final verify set `uv run pytest tests/test_update.py tests/test_executors.py tests/test_catalog_tui.py tests/test_session.py -n auto -q --no-cov`: exit 0. Two-test acceptance `-k "prefers_zsh_when_both_roots_exist or falls_back_to_the_default_dir"`: `2 passed`.

## Test counts (measured with `--collect-only`)

| File | Task start (base 853b1af) | After plan | Delta |
|---|---|---|---|
| tests/test_update.py | 90 | 102 | +12 (T1 +8, T2 +1, T3 +3) |
| tests/test_executors.py | 88 | 89 | +1 (T2) |
| tests/test_catalog_tui.py | 213 | 214 | +1 (T3) |
| tests/test_session.py | 111 | 112 | +1 (T3) |
| tests/test_verify_registry.py | 141 | 141 | 0 |
| tests/test_plan.py | 93 | 93 | 0 |

Full suite: 5346 passed at the wave-2 ledger figure (not re-run at the base) → 5354 after Task 1 → 5356 after Task 2 → **5361 after Task 3** (+15 = 8 + 2 + 5). Floors met: test_update 102 ≥ 90 + 12 (the plan's delta is 12 counted per test function, 8 + 1 + 3); test_executors 89 ≥ 88 + 1; test_catalog_tui 214 ≥ 213 + 1; test_session 112 ≥ 111 + 1.

## Changed or Deleted Existing Tests

No existing test was deleted or had its assertions changed. One helper annotation changed, which the plan requires for the pinned headless test:

| Location | Change | Reason |
|---|---|---|
| `tests/test_session.py::_run_context` (helper, not a test) | `updates: ScriptedUpdates \| None` became `updates: UpdateService \| None` | The new headless test passes a real `UpdateService`, so the engine refusal is what answers. `ScriptedUpdates` is a subclass, so every existing caller still type-checks. |

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 - Blocking, tooling] Typed test helpers for pyright strict**
- **Found during:** Task 1 `make validate`
- **Issue:** `lambda **_kwargs: ManagerInventory(...)` and `OutdatedReport(...)` were partially unknown to pyright strict in the new R2-01 test.
- **Fix:** Replaced with named module functions `_no_inventory(**_kwargs: object)` and `_no_outdated(**_kwargs: object)`, the same shape `tests/test_version_status.py` uses.
- **Committed in:** `387c3a7`

**2. [Rule 1 - Test assertion] Relative refresh count in the catalog pilot**
- **Found during:** Task 3 GREEN
- **Issue:** `assert refreshes == [True]` never became true, because the app also requests a refresh while mounting (the patched `request_refresh` was installed before `run_test`).
- **Fix:** Count the requests after the screen settles: `baseline = len(refreshes)`, wait for `len(refreshes) > baseline`, then assert exactly `baseline + 1`. This is the intended contract ("one refresh pass is requested by the press"). The production code is unchanged.
- **Committed in:** `69cc9d8`

**3. [Rule 1 - Lint/type] Pyright private use and line length in the pilot**
- **Found during:** Task 3 `make validate`
- **Issue:** `monkeypatch.setattr(app.catalog._browser, "highlighted_id", ...)` triggered `reportPrivateUsage`. The native pilot test passes only because its existing `type: ignore` also silences that line, and this plan may not add a suppression.
- **Fix:** Removed the patch. The catalog has one tool, so its only row is highlighted by default; the exact status line (`cannot update drawio-desktop: pinned; ...`) proves `u` acted on that row. Two over-long lines wrapped; `ruff format` and the ruff I001 import sort (`installer/catalog_tui.py`) applied as formatting only.
- **Committed in:** `69cc9d8`

### Plan deviations (recorded, not auto-fixed)

**1. Plan-head ledger and spawn sentinel stored outside the git dir.** The protocol keeps the ledger at `$(git rev-parse --git-dir)/gsd-plan-head-before-22-05`. The harness refused writes to that shared git-dir path, so the ledger lives at `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/gsd-plan-head-before-22-05` (value `853b1afed4ef6e2ed9919508053f4995bb9d2af7`). The commit count above was measured from that base with `git rev-list --count`.

**2. Pre-commit guard run as separate checks.** The harness refused the compound guard script in this worktree. Instead I ran the same checks as plain commands before each commit: `git symbolic-ref --quiet HEAD` (attached), `git rev-parse --abbrev-ref HEAD` (`worktree-agent-abfd03508743f2a97`, matches the agent namespace), `git rev-parse --show-toplevel` (equal to the worktree path). The `gsd_run query git.base-branch` protected-branch lookup was not run; the branch name is outside the protected list by the namespace rule. The orchestrator's per-commit checks (`git status`, staged files only) were run before each commit.

**3. Tasks 2 and 3 are not all RED.** Task 2's `sdkman_owned` tests and Task 3's `test_an_unpinned_app_still_updates` pass before the change; they are regression guards and are labelled as such above. The pinned-app RED tests and the Task 2 bootstrap test are real RED.

**4. Worktree-owned guards not written.** The `gsd-spawn-toplevel` sentinel was not written into the git dir (same harness refusal as Deviation 1). The drift check ran on each commit against the worktree path instead.

**5. Test-helper choice in the R2-01 test.** The plan requires building `VersionRefreshService` without an `artifacts_for` override. `tests/test_version_status.py::_owner_pass_service` defaults `artifacts_for` to an empty list, and passing `None` through it would fail pyright, so the service is constructed directly in `tests/test_update.py`.

**Total deviations:** 3 auto-fixed (tooling, test assertion, lint); 5 plan deviations recorded above (ledger location, guard checks, RED classification, sentinel, helper choice).

## Issues Encountered

- The harness refused several compound shell commands and any write into `.git/worktrees/...`. Each was split into plain commands; logs stayed in the scratchpad, not the worktree.
- `make install` created the worktree `.venv` (gitignored; never staged).
- The codegraph index belongs to the main checkout (a warning on every query). It was used only to orient; every Read and Edit targeted the worktree.
- `codegraph sync` reported `Done`, but the query output still names the main checkout, so the code excerpts were cross-checked with direct reads of the worktree files.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-22-11 (declared argv) is mitigated: literal argv, closed-root token expansion, no `sh -c` in the update path (grep count 0), `sdk` through `shlex.join` inside the one reviewed sourced invocation. T-22-12 (pinned re-download) is mitigated by the pre-lock refusal and by `update_refusal`, with zero runner calls in the tests. T-22-45 is covered by the R2-01 end-to-end test.

## Not checked / residual risk

- **No real host run.** Oh-My-Zsh and SDKMAN were exercised only through fake runners, as the rules require. The real `upgrade.sh` must be executable, because the argv runs directly; that is a registry data question for 22-08 and is not verified here.
- **Registry data.** The `update` keys on `oh-my-zsh` and `sdkman` land in 22-08. Until then, a real `u` on those tools still re-runs their installers, exactly as before this plan.
- **Pinned predicate requires `sha256`.** `download.pinned_method` treats a pinned url without `version` or `sha256` as unpinned; `model.load_tools` guarantees both for every loaded `app`/`tarball` url that holds `{ver}`, so this holds for loaded tools but is not re-checked here.
- **Install-side preexisting wiring.** `engine.install_tool` still calls `receipts.record` without `preexisting`, so a script install records no declared-path proof until 22-06 wires it.

## Self-Check

Checked after writing this file:

- Created or modified source and test files exist in the worktree (the nine files under Key Files).
- Commits `387c3a7`, `7437910` and `69cc9d8` are ancestors of HEAD.

## Next Phase Readiness

- 22-06 (install and remove) takes the same `preexisting_paths` snapshot in `engine.install_tool` and reads `MANAGER_UNINSTALL_ARGV` through `ownership.method_package`.
- 22-08 adds the `update` data for `oh-my-zsh` and `sdkman`; the behavior is in place and tested with fixtures.
- Orchestrator: STATE.md and ROADMAP.md were not modified by this plan.

---
*Phase: 22-method-lifecycle-contract*
*Completed: 2026-11-04*
