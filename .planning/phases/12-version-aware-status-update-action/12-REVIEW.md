---
phase: 12-version-aware-status-update-action
reviewed: 2026-09-07T17:06:33Z
depth: deep
files_reviewed: 20
files_reviewed_list:
  - installer/ownership.py
  - installer/update.py
  - installer/manager_versions.py
  - installer/version_cache.py
  - installer/version_status.py
  - installer/atomic.py
  - installer/versions.py
  - installer/catalog_tui.py
  - installer/download.py
  - installer/apps.py
  - installer/run.py
  - setup.py
  - tests/test_ownership.py
  - tests/test_update.py
  - tests/test_manager_versions.py
  - tests/test_version_cache.py
  - tests/test_version_status.py
  - tests/test_versions.py
  - tests/test_download.py
  - tests/test_apps.py
  - tests/test_catalog_tui.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-09-07T17:06:33Z
**Depth:** deep
**Files Reviewed:** 20 (12 source, 8 test)
**Status:** issues_found

## Summary

This review traced `installer/ownership.py::resolve_ownership` and `installer/update.py`
directly (not via tests) against the three properties the task called out as
safety-critical, and all three hold up under adversarial tracing:

1. **Fail-closed ownership evidence.** `resolve_ownership` checks `active_path is not None`
   and rejects (returns `unknown`) whenever the live PATH binary does not attribute to
   *exactly one* ownership candidate — this check runs BEFORE the by-elimination branch
   (`ownership.py:296-308`), so a stale installer artifact plus an unreadable brew
   inventory plus a live `/opt/homebrew/bin/<cmd>` cannot be misattributed, even in the
   double-failure case where `brew --prefix` itself also failed (traced by hand; matches
   `tests/test_ownership.py::test_unattributable_active_binary_is_unknown`).
2. **Fresh mutation-time re-resolution.** `UpdateService.run()` calls
   `self._reresolve_ownership(target.tool)` first (`update.py:368`) and authorises/dispatches
   on that `fresh` result via a rebuilt `fresh_target`, never on the caller-supplied
   `target.ownership`. `setup.py`'s production `_reresolve_ownership` calls
   `read_inventory(has_brew=...)` and `shutil.which` directly (no cache), confirmed by
   reading the wiring in `setup.py:396-406`. `tests/test_update.py::test_update_service_fresh_ownership_overrides_cached`
   asserts on call order, not just presence.
3. **Pnpm snapshot-before-mutate ordering.** `UpdateService.run()` captures
   `self._managed_packages()` (lines 379-384) strictly before calling `perform_update`
   (line 385), and only replays after `outcome.status == "updated"` (line 399). Verified
   against `test_update_service_precaptures_pnpm_globals_before_mutate`, which asserts
   `order.index("managed") < order.index("mutate") < order.index("replay")`.

No BLOCKER/Critical-tier defect was found in the mutation-authorisation logic itself.
The remaining findings are test-coverage gaps in the safety-relevant rollback/wiring code
and a handful of code-quality nits. `make validate`-equivalent checks (ruff, pyright,
bandit with the project's own `--skip B404,B603,B310`, vulture) all pass clean on every
file in scope; the one pre-existing pyright error cluster in `setup.py` (lines 374, 507-559,
610) predates this phase (confirmed via `git diff e3404e0..712df7c -- setup.py`, which
shows only additive changes) and is out of scope for this review.

## Warnings

### WR-01: The update action's worker-and-message wiring in `catalog_tui.py` is essentially untested end-to-end

**File:** `installer/catalog_tui.py:563-568` (in-flight guard message), `:570-595` (`_update_tool_worker`), `:597-623` (`on_tool_updated`)
**Issue:** All three existing `action_update_tool` tests (`test_action_update_tool_skips_confirmed_current`,
`test_action_update_tool_refuses_non_mutation_grade`, `test_action_update_tool_starts_worker_when_outdated_is_none`)
monkeypatch `screen._update_tool_worker` into a no-op recorder before calling `action_update_tool()`,
so none of them ever runs the worker body. A full-suite coverage run confirms 0% coverage on:
the "update already in flight for …" warning line (563-566), the entire worker body that
constructs `UpdateTarget`, calls `service.run(target)` via `run_live`, re-refreshes the single
tool on success, and posts `ToolUpdated` (570-595), and the whole `on_tool_updated` handler that
formats the "updated …", "replayed …", "cleanup warnings …", "postinstall …" and failure/refusal
status lines (597-623: lines 603-604, 606-607, 610-618 all show as missed). This is the only
code path that actually drives the no-confirmation mutating action from a keypress through to
`UpdateService.run()` and back to the visible status line — a wiring regression here (wrong
`UpdateTarget` field, a dropped `epoch`, a `KeyError`/`AttributeError` in the f-string formatting
when `outcome.cleanup_warnings`/`postinstall_warning` are populated) would not be caught today,
even though `UpdateService.run()` itself is well unit-tested in isolation.
**Fix:** Add at least one test that lets `_update_tool_worker` run against a fake `UpdateService`
(e.g. one whose `run()` returns a fixed `UpdateOutcome`) and asserts `on_tool_updated` renders
the expected status text for `status="updated"` (with `replayed_globals`/`cleanup_warnings`/
`postinstall_warning` populated) and for `status="failed"`. Add a second test that calls
`action_update_tool()` twice in a row (or pre-seeds `updates.begin(other_tool)`) and asserts the
"update already in flight for …" message is set.

### WR-02: `apps.py`'s update rollback state machine has materially thinner coverage than `download.py`'s equivalent

**File:** `installer/apps.py:144`, `:154-159`, `:186-194`, `:200-208`
**Issue:** `download.py` has a dedicated `test_archive_update_swap_failure_restores_original`
test (and a symlink-failure-restore test) for its `_replace_archive` rollback state machine.
`apps.py`'s `update_app` implements the identical state machine (aside-move, swap, relink,
validate, undo) but has no analogous test for: the `os.replace(new, live)` swap itself failing
(lines 154-159, restore-from-`old`), `_validate_app` raising because the updated bundle or CLI
is missing/not executable (lines 186-194 — the exact condition `_undo_app_swap` exists to
recover from), or the "extracted zip did not contain '<app>'" guard (line 144). Full-suite
coverage confirms these lines, plus `_undo_app_swap`'s internal branches (200→202, 202→204,
204→206, 208), are never executed.
**Fix:** Port `test_archive_update_swap_failure_restores_original` and a validation-failure test
from `test_download.py` to `test_apps.py`, monkeypatching `os.replace` to fail on the swap step
and making the extracted `.app`'s CLI missing/non-executable respectively, asserting the original
bundle and CLI symlink are restored.

### WR-03: `UpdateService.run()`'s "pnpm globals replay failed" branch is untested

**File:** `installer/update.py:399-404`
**Issue:** The `except Exception as extra: # noqa: BLE001 -- secondary mutation, never downgrades updated`
branch — reached when `self._replay_globals(snapshot)` itself raises after a successful pnpm
update — has no test. This is precisely the residual-risk case the module's own docstring is
worried about (losing pnpm's global packages on a pnpm self-update); the "capture ordering"
property is well tested, but the "replay raised" outcome-shape (does `status` really stay
`"updated"`, does `detail` really carry the failure text) is unverified.
**Fix:** Add a test where `replay_globals` raises and assert `outcome.status == "updated"` with
the replay failure text appended to `outcome.detail`.

### WR-04: One unguarded `os.replace`/extraction call breaks the "prior installation intact/restored" messaging contract the rest of the function follows

**File:** `installer/apps.py:147` (`os.replace(staged_bundle, new)`); `installer/download.py:286` (`_extract_into(...)` call site inside `_replace_archive`)
**Issue:** Every other fallible step in `update_app`/`_replace_archive` is wrapped in
`try/except OSError` and re-raised as an `ExecutorError` with an explicit "prior installation
intact"/"prior installation restored" message (e.g. `apps.py:148-153`, `:154-159`;
`download.py:288-292`, `:293-298`, `:299-304`). The bundle-move (`apps.py:147`) and the archive
extraction (`download.py:286`, inside `_extract_into`) are not wrapped. Functionally this is
safe today — neither call happens after the live tree has been touched, so a failure here still
leaves the original installation untouched — but a failure surfaces as a bare, unlabelled
`OSError`/`CommandError` instead of the consistent, reassuring messaging every other step in the
same rollback machine provides, which matters for a phase whose explicit design goal is precise
failure communication for a no-confirmation mutating action.
**Fix:** Wrap `os.replace(staged_bundle, new)` in `apps.py` and the `_extract_into(...)` call in
`download.py`'s `_replace_archive` the same way the surrounding steps are wrapped.

## Info

### IN-01: `owner_dirs` derives the installer opt-root via a placeholder-argument hack

**File:** `installer/ownership.py:217`
**Issue:** `installer_dirs = (managed_bin_dir, opt_dir("x").parent, applications_dir())` relies
on `opt_dir`'s internal shape (`Path.home() / ".local" / "opt" / name`) and a throwaway `"x"`
argument to recover the parent `~/.local/opt` directory. It works today, but is fragile: any
future change to `opt_dir`'s layout (e.g. adding a nested segment) silently breaks ownership
attribution for every archive-installed tool instead of raising, and the intent is non-obvious
without cross-referencing `installer/locations.py`.
**Fix:** Add a small `opt_root() -> Path` helper next to `opt_dir` in `installer/locations.py`
and call that directly.

### IN-02: `attribute_path`'s broken-symlink/`OSError` fallback is untested despite being a documented real-world scenario

**File:** `installer/ownership.py:238-254`
**Issue:** The `except OSError: resolved = path` fallback (used for both the active binary path
and every owner-directory prefix) has no covering test in `tests/test_ownership.py`. This
codebase's own `installer/atomic.py` docstring explicitly cites "a dotfile-manager setup that
symlinks ~/.zshrc to a repo elsewhere" as a realistic scenario, so a broken/foreign symlink on
`PATH` is a plausible real input to `resolve_ownership`.
**Fix:** Add a test where `which()` returns a path that is a symlink to a nonexistent target and
assert `resolve_ownership` still degrades to `owner="unknown"` rather than raising.

### IN-03: `github_repo(tool, platform)` is computed twice per tool per refresh pass

**File:** `installer/version_status.py:456` and `:210`
**Issue:** `VersionRefreshService.refresh()` calls `github_repo(tool, self._platform)` to compute
`would_fetch`, then `resolve_status` (called immediately after for the same tool) calls it again
internally when `owner == "installer"`. Not a correctness issue and not a performance concern in
scope for this review, but it is avoidable duplication of a non-trivial lookup across a call
boundary.
**Fix:** Compute `github_repo(...)` once in `refresh()` and pass it through to `resolve_status`.

### IN-04: Several early-returns in the update-action gating give the user no feedback at all

**File:** `installer/catalog_tui.py:545-552`, `:557-558`
**Issue:** If `self._version_refresh.ownership_of(tool_id)` returns `None` — e.g. the user
presses `u` before the initial background version-refresh pass has completed — `action_update_tool`
silently returns with no status message, unlike every other refusal branch in the same function
(which all call `self.status.set(...)`). The user has no way to tell the keypress was received.
**Fix:** Set a short status message (e.g. "version info still loading, try again shortly") for
the `ownership is None` case.

---

_Reviewed: 2026-09-07T17:06:33Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

## Second lane: codex-sol-high

**Reviewer:** codex CLI, model `gpt-5.6-sol (reasoning=high)`.
**Scope:** same diff, HEAD `712df7cfb59123501c26866dbe9efc7ff70faf96`, run independently and in
parallel with the internal lane above. Findings quoted verbatim below.

## Review result

**Verdict: BLOCK / request changes.** The merged implementation does not satisfy two of the three
required safety properties and contains an additional crash-recovery flaw. Because `u` mutates the
machine without confirmation, these are release blockers.

Reviewed the 45-file diff at exact HEAD `712df7cfb59123501c26866dbe9efc7ff70faf96`, plus current call sites.

### Critical

#### C1 — Inventory parsing is not genuinely fail-closed

**Scenario:** A manager emits a warning, error object, or future output shape. The parser turns it into a valid mapping or empty set. Ownership then treats the manager as successfully queried and can authorize another owner by elimination.

Concrete read-only reproductions:

```text
parse_brew_list_versions("warning: inventory format changed\n")
=> {"warning:": "changed"}

parse_global_packages('{"error":"schema changed"}')
=> ()
```

A stale installer artifact plus no active PATH can consequently reach the mutation-grade branch at [ownership.py:309](/Users/ramon/git/personal/tools-installer/installer/ownership.py:309).

Evidence:

- Brew accepts every line with two or more tokens: [ownership.py:119](/Users/ramon/git/personal/tools-installer/installer/ownership.py:119)
- pnpm accepts any JSON object without requiring a recognized project shape: [pnpm_globals.py:264](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:264)
- pnpm dependency values are not validated: [pnpm_globals.py:274](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:274)
- uv silently skips every indented line, not only recognized entry-point lines: [ownership.py:136](/Users/ramon/git/personal/tools-installer/installer/ownership.py:136)
- The same permissive uv behavior exists in outdated parsing: [manager_versions.py:127](/Users/ramon/git/personal/tools-installer/installer/manager_versions.py:127)

This directly violates safety property 1(b).

#### C2 — Homebrew casks can be misclassified as installer-owned with direct confidence

**Scenario:** VS Code is installed by Homebrew into `~/Applications`. Its `code` symlink resolves into `~/Applications/Visual Studio Code.app`. The resolver sees:

- an "installer artifact" merely because that bundle exists;
- a real cask inventory candidate;
- an active path under a directory attributed only to the installer.

It therefore returns `owner="installer", confidence="direct"` and pressing `u` replaces the Homebrew-managed bundle through the direct-download app updater.

I reproduced exactly that result: `installer direct ['installer', 'cask']`.

Evidence:

- `plan_uninstall` treats any matching bundle in `~/Applications` as an installer artifact, without provenance: [uninstall.py:33](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:33), [uninstall.py:56](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:56)
- Homebrew deliberately installs casks into that same directory: [executors.py:487](/Users/ramon/git/personal/tools-installer/installer/executors.py:487)
- `~/Applications` is attributed to installer, while cask paths are only attributed to `brew --prefix`: [ownership.py:211](/Users/ramon/git/personal/tools-installer/installer/ownership.py:211)
- A single path-matching candidate immediately wins, even when other candidates exist: [ownership.py:282](/Users/ramon/git/personal/tools-installer/installer/ownership.py:282)
- VS Code declares both app and cask methods: [registry.toml:2069](/Users/ramon/git/personal/tools-installer/installer/registry.toml:2069)
- Sublime has the same configuration: [registry.toml:2114](/Users/ramon/git/personal/tools-installer/installer/registry.toml:2114)

This violates the broader fail-closed ownership requirement despite the active-path branch being correctly ordered.

#### C3 — A pnpm self-update proceeds when the pre-update snapshot failed

**Scenario:** `pnpm list -g --json` times out or returns malformed data. `_managed_packages()` returns `None`. The implementation records a warning but still updates pnpm. If that update wipes pnpm's global set, nothing can be replayed because no snapshot exists.

Evidence:

- `None` only sets `snapshot_unknown`; mutation still executes unconditionally: [update.py:377](/Users/ramon/git/personal/tools-installer/installer/update.py:377)
- The warning is constructed only after mutation: [update.py:392](/Users/ramon/git/personal/tools-installer/installer/update.py:392)
- Query and parsing failures produce `None`: [pnpm_globals.py:405](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:405)
- The test explicitly blesses an `"updated"` outcome with no snapshot: [test_update.py:670](/Users/ramon/git/personal/tools-installer/tests/test_update.py:670)

The successful-snapshot ordering is correct, but safety property 3 requires capture before mutation. An unreadable snapshot must abort the pnpm self-update.

#### C4 — Crash recovery can delete the only known-good pre-update installation

**Scenario:** The process dies after `.new` is swapped into the live location but before relinking or validation. Both live and `.old` exist. On the next run, recovery assumes live is valid and deletes `.old` before the replacement has been validated. If live is corrupt or the next download fails, the last known-good copy is irretrievably lost.

Evidence:

- Recovery deletes `.old` whenever live also exists: [atomic.py:78](/Users/ramon/git/personal/tools-installer/installer/atomic.py:78)
- Archive swap occurs before relinking and validation: [download.py:299](/Users/ramon/git/personal/tools-installer/installer/download.py:299)
- App swap likewise occurs before validation: [apps.py:154](/Users/ramon/git/personal/tools-installer/installer/apps.py:154)
- App recovery runs before even downloading the next archive: [apps.py:132](/Users/ramon/git/personal/tools-installer/installer/apps.py:132)

The remnant state does not encode whether the live copy passed validation, so "live plus old" cannot safely mean "delete old."

### Warning

#### W1 — Normal uv tool installations cannot receive direct ownership

**Scenario:** uv places a shim at `~/.local/bin/graphify` pointing into `~/.local/share/uv/tools/graphifyy/bin/graphify`. The resolver dereferences the shim, but only recognizes `~/.local/bin` as uv-owned. The resolved path becomes unattributable, so ownership is `unknown` and the advertised uv update action is unavailable.

Evidence:

- Only the shim directory is registered for uv: [ownership.py:227](/Users/ramon/git/personal/tools-installer/installer/ownership.py:227)
- The active path is dereferenced before attribution: [ownership.py:433](/Users/ramon/git/personal/tools-installer/installer/ownership.py:433)
- Any resulting unattributable active path becomes unknown: [ownership.py:297](/Users/ramon/git/personal/tools-installer/installer/ownership.py:297)
- Graphify is a real uv-only registry entry: [registry.toml:1540](/Users/ramon/git/personal/tools-installer/installer/registry.toml:1540)

This is fail-closed, but functionally breaks uv-owned updates.

#### W2 — Cache invalidation failure reports a completed mutation as failed

**Scenario:** `brew upgrade` succeeds, but writing `versions.json` fails. `UpdateService.run` raises during invalidation, discarding the already-produced successful outcome. The UI says "update failed," encouraging a duplicate retry even though the machine was changed.

Evidence:

- Invalidation happens after the successful update and is not isolated: [update.py:399](/Users/ramon/git/personal/tools-installer/installer/update.py:399)
- Invalidation performs filesystem I/O that can raise: [version_status.py:373](/Users/ramon/git/personal/tools-installer/installer/version_status.py:373)
- `run_live` converts that exception into a failure with no result: [ui_common.py:41](/Users/ramon/git/personal/tools-installer/installer/ui_common.py:41)
- The UI then reports failure: [catalog_tui.py:586](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:586)

Invalidation failure should be a post-update warning, not change the mutation's outcome.

#### W3 — Manager query failures are cached as successful six-hour snapshots

**Scenario:** One transient brew/pnpm/uv query fails. Its wrapper returns `None`, so the aggregate query does not raise. The snapshot receives `checked_at=now` and `failed_at=None`, remaining fresh for six hours. Cached unknown ownership also blocks the UI before fresh mutation-time resolution can run.

Evidence:

- Manager readers swallow command failures into `None`: [ownership.py:186](/Users/ramon/git/personal/tools-installer/installer/ownership.py:186), [manager_versions.py:151](/Users/ramon/git/personal/tools-installer/installer/manager_versions.py:151)
- The aggregate snapshot is nevertheless marked successful: [version_status.py:395](/Users/ramon/git/personal/tools-installer/installer/version_status.py:395)
- Manager freshness lasts six hours: [version_cache.py:42](/Users/ramon/git/personal/tools-installer/installer/version_cache.py:42)
- Cached unknown ownership prevents entering `UpdateService.run`: [catalog_tui.py:556](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:556)

### Info

#### I1 — Fresh mutation-time ownership re-resolution is correctly implemented

Safety property 2 passes:

- `UpdateService.run` re-resolves first and refuses non-mutation-grade results: [update.py:366](/Users/ramon/git/personal/tools-installer/installer/update.py:366)
- `perform_update` receives the fresh target: [update.py:376](/Users/ramon/git/personal/tools-installer/installer/update.py:376)
- Production re-resolution directly queries inventory and filesystem artifacts without using the version cache: [setup.py:396](/Users/ramon/git/personal/tools-installer/setup.py:396)

#### I2 — Contradictory active PATH is checked before by-elimination

The narrow ordering requirement in safety property 1(a) is structurally correct: any remaining active path returns `unknown` at [ownership.py:297](/Users/ramon/git/personal/tools-installer/installer/ownership.py:297), before by-elimination at [ownership.py:309](/Users/ramon/git/personal/tools-installer/installer/ownership.py:309). C2 shows that the attribution feeding this branch is still unsound.

#### I3 — Several safety tests provide false assurance

- The missing pnpm snapshot test explicitly expects mutation to continue: [test_update.py:670](/Users/ramon/git/personal/tools-installer/tests/test_update.py:670)
- The production freshness test patches a name that was already captured as a default argument, then accepts almost every possible result: [test_setup.py:663](/Users/ramon/git/personal/tools-installer/tests/test_setup.py:663)
- A rollback assertion is tautologically true because of `or True`: [test_download.py:767](/Users/ramon/git/personal/tools-installer/tests/test_download.py:767)

### Safety-property summary

| Property | Result |
|---|---|
| Fail-closed ownership evidence | **Fail** — malformed parsers and app/cask misattribution |
| Fresh mutation-time re-resolution | **Pass** |
| pnpm snapshot before mutation | **Fail** — ordered when available, but mutation continues when unavailable |

### Verification notes

- Read-only reproductions confirmed the brew/pnpm parser failures, VS Code app/cask misclassification, and real uv symlink misclassification.
- Ruff completed successfully with `--no-cache`.
- Pytest could not start because the managed read-only environment provides no writable temporary directory; no repository files were modified.

Overall risk is **high**: C1–C3 undermine the exact safeguards intended to make a no-confirmation mutation acceptable, while C4 can destroy the last rollback copy after interruption. Phase 12 should not ship until all four Critical findings are corrected and regression-tested.

## Resolution status

| # | Finding (both lanes) | Lane(s) | Severity | Disposition |
|---|---|---|---|---|
| 1 | C1: `parse_brew_list_versions` accepts any 2+-token line (e.g. a warning line) as `name version` | codex | Critical | **Fixed** — first token validated against a formula/cask-name shape (no stray punctuation), every remaining token validated as a version-like token (`latest` or digit-led); malformed input fails the whole parse closed. Regression: `test_parse_brew_list_versions_warning_line_fails_closed` |
| 2 | C1: `parse_uv_tool_list` / `parse_uv_tool_outdated` skip indented/`- ` lines unconditionally, not only recognized entry-points | codex | Critical | **Fixed** — an entry-point-shaped line is now only accepted immediately after a matched `name vX.Y` line; one with no preceding match fails the whole parse closed. Regression: `test_parse_uv_tool_list_entrypoint_without_preceding_match_fails_closed`, plus existing `test_parse_uv_tool_outdated_fail_closed_cases` re-verified |
| 3 | C1: pnpm's `_load_projects`/`_iter_dependencies` accept any JSON object as an empty project, and never validate dependency values | codex | Critical | **Fixed** — a project object must carry at least one key `pnpm list -g --json` actually emits (`_KNOWN_PROJECT_KEYS`) or the whole parse fails closed; every dependency value must be a `dict` or the parse fails closed. Regression: existing `tests/test_pnpm_globals.py` cases re-verified against the new checks (all pass unchanged) |
| 4 | C2: a tool declaring both `app` and `cask` methods, cask-installed into `~/Applications`, resolves to `owner="installer", confidence="direct"` | codex | Critical | **Fixed** — `owner_dirs` now lists `applications_dir()` for BOTH "installer" and "cask" (Homebrew installs casks there too), so a path under it attributes to both when both candidates exist for the tool, and the single-candidate-wins branch falls through to `unknown` instead of guessing. Regression: `test_cask_installed_app_never_wins_installer_direct_ownership` (VS-Code-shaped repro) |
| 5 | C3: pnpm self-update proceeds unconditionally when the pre-update snapshot capture returns `None` | codex | Critical | **Fixed** — `UpdateService.run` now returns a `status="failed"` outcome and calls `perform_update` zero times when the snapshot is unreadable, instead of proceeding with a warning. `tests/test_update.py:670`'s test rewritten to assert refusal (`test_update_service_none_snapshot_refuses_to_mutate`); matching TUI-level test renamed/rewritten (`test_none_package_snapshot_refuses_the_update`) |
| 6 | C4: `recover_update_remnants` deletes `.old` whenever `live` also exists, inferring validity from mere existence | codex | Critical | **Fixed** — recovery never deletes `.old` again; whenever `.old` is present it unconditionally restores over `live` (discarding `live` first if needed), since `.old` surviving to a recovery pass is itself proof the update that created it never finished. Documented accepted residual: a same-run cleanup failure after a successful validated update can cause a later recovery to restore an older validated tree instead — a downgrade, not data loss. Regression: `test_recover_update_remnants_never_deletes_old_when_live_also_exists`, `test_recover_update_remnants_restores_old_when_live_is_missing`, `test_recover_update_remnants_discards_stale_new` |
| 7 | W1: uv shim/symlink dereferencing means a normal uv-owned tool resolves to `unknown` rather than direct ownership | codex | Warning | **Documented-accepted-limitation** — per the task's own instruction not to fix unless trivial. This is a functionality gap (fails closed, never unsafe): the resolved shim target under `~/.local/share/uv/tools/<pkg>/bin/<cmd>` isn't recognized as uv-owned because only the shim directory (`~/.local/bin`) is registered. Fixing it correctly requires resolving the *declared* per-package uv tool directory shape rather than a single static prefix, which is a real (if small) design change, not a one-line fix — deferred as lower priority than the four Criticals |
| 8 | W2: a cache-invalidation failure after a successful update propagates and gets reported as "update failed" | codex | Warning | **Fixed** — `UpdateService.run`'s `self._invalidate(...)` call is now wrapped in `try/except Exception`, appending "cache invalidation failed: …" to `detail` on failure while keeping `status="updated"`. Regression: `test_update_service_invalidate_failure_stays_updated` |
| 9 | W3: a single manager's transient query failure is cached as a confirmed-fresh six-hour snapshot with `failed_at=None` | codex | Warning | **Fixed** — added `VersionRefreshService._partial_manager_failure`, which checks whether a manager CONFIRMED present (`has_brew`, `resolve_pnpm() is not None`, `which("uv") is not None`) came back with a `None` field despite being queried; when true, the snapshot is built the same way as an outright exception (previous data backfilled per-field via new `_merge_inventory`/`_merge_outdated` helpers, `failed_at` set) so the 30-minute `MANAGER_RETRY_BACKOFF` applies instead of the full 6-hour `MANAGER_STALE_AFTER`. Regression: `test_partial_manager_failure_is_not_cached_as_confirmed_fresh` |
| 10 | I1: fresh mutation-time ownership re-resolution is correctly implemented | codex | Info | **No-change-needed** — codex's own verdict; confirmed still true after the fixes above (re-resolution path untouched except for the new pnpm-snapshot refusal, which runs strictly after re-resolution succeeds) |
| 11 | I2: contradictory active PATH is checked before by-elimination | codex | Info | **No-change-needed** — codex's own verdict; the C2 fix corrects the attribution feeding this branch without touching the ordering itself |
| 12 | I3: `tests/test_update.py:670` blesses "proceed anyway" with no snapshot | codex | Info (listed under I3, resolved as part of Critical #5) | **Fixed** — see disposition #5; test rewritten to assert refusal |
| 13 | I3: `tests/test_setup.py:663` patches a name already captured as a default argument, then accepts almost every result | codex | Info | **Fixed** — confirmed the mock was genuinely inert (proved live: patching `installer.ownership.run_query` and calling `read_inventory()` directly still ran the real subprocess path). Rewritten to patch the actual call-time boundary (`installer.run.subprocess.run`) plus `shutil.which` for PATH-attribution hermeticity, and tightened the assertions to exact expected owners/versions instead of an "accepts almost anything" set |
| 14 | I3: `tests/test_download.py:767`'s rollback assertion is tautologically true (`... or True`) | codex | Info | **Fixed** — confirmed the equality it originally intended to check is always true for an unrelated reason (the live symlink path is textually stable across an update), so the `or True` wasn't hiding a bug but the assertion itself was meaningless; replaced with a real invariant (`len(seen) == 2` and `seen[1] == original_target`) |
| 15 | WR-01: `catalog_tui.py`'s update worker-and-message wiring (`_update_tool_worker`/`on_tool_updated`) is essentially untested end-to-end | internal | Warning | **Accepted-no-change** — a real coverage gap, but out of scope for this fix-forward pass, which is scoped to the Critical safety findings both lanes raised plus the Warning/Info items codex flagged as needing verification; no functional defect is claimed here (WR-01 is a coverage gap, not a bug) |
| 16 | WR-02: `apps.py`'s update rollback state machine has materially thinner coverage than `download.py`'s equivalent | internal | Warning | **Accepted-no-change** — same rationale as #15: a coverage gap, not a defect, and out of this pass's scope |
| 17 | WR-03: `UpdateService.run()`'s "pnpm globals replay failed" branch is untested | internal | Warning | **Accepted-no-change** — coverage gap, not a defect; out of this pass's scope |
| 18 | WR-04: one unguarded `os.replace`/extraction call breaks the "prior installation intact/restored" messaging contract | internal | Warning | **Accepted-no-change** — internal reviewer's own finding notes this is "safe today" (failure happens before the live tree is touched); a messaging-consistency nit, not a safety defect, out of this pass's scope |
| 19 | IN-01: `owner_dirs` derives the installer opt-root via a placeholder-argument hack (`opt_dir("x").parent`) | internal | Info | **Accepted-no-change** — works correctly today; a maintainability nit, out of this pass's scope |
| 20 | IN-02: `attribute_path`'s broken-symlink/`OSError` fallback is untested | internal | Info | **Accepted-no-change** — coverage gap, not a defect; out of this pass's scope |
| 21 | IN-03: `github_repo(tool, platform)` is computed twice per tool per refresh pass | internal | Info | **Accepted-no-change** — a non-trivial-but-harmless duplication, explicitly called out by the internal reviewer as "not a correctness issue and not a performance concern in scope for this review"; out of this pass's scope |
| 22 | IN-04: several early-returns in the update-action gating give the user no feedback (e.g. ownership not yet loaded) | internal | Info | **Accepted-no-change** — a UX-polish nit, not a safety defect; out of this pass's scope |

_Second lane reviewed and resolved: 2026-09-07_
