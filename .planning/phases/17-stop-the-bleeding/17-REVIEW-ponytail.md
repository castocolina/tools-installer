# Phase 17 review lane: ponytail:ponytail-review

Read-only run, scope a7dba6f..0e9406c (non-.planning). Unverified input; verified per finding by gap plans 17-18..17-20.

# Phase 17 ponytail review

Scope: `git diff a7dba6f..HEAD -- . ':(exclude).planning'` (49 files). Intent read from
17-SPEC.md, 17-CONTEXT.md and the plan summaries. Load assumed: one user, one installer
process per host (the SPEC dismisses concurrency on that basis).

**What this change does:** It closes host hazards H1–H7. Archive members must be regular
files before they are linked, the graphify hook is gone, and uninstall deletes only what it
can prove by the archive layout. rc and shim writes are atomic, crashes and failures turn
the run red and exit 1, a link-mode change carries active ban/tweak blocks over, children
run in their own session, bad `settings.json` no longer crashes, every route can execute,
and Doctor reports broken `~/.local/bin` links. It also contains the CI portability fixes.

---

## 1. MEDIUM — Execute screen says "Failed" for a skipped update, but the process exits 0

- **File:** `installer/execute_screen.py:961-964` (handler `on_install_run_finished`)
- **Defect:** `_run_updates` posts no `UpdateToolFinished` on its three `continue` paths:
  refresh failure (`:739-741`), "ownership could not be resolved" (`:743-746`) and "update
  already in flight" (`:747-751`). So the row stays `"pending"`, and the handler loop appends
  the tool to `self.not_attempted`. The screen's `fold_run` then sets `has_failure` and shows
  a red "Failed." UnifiedApp folds `message.not_attempted` instead. The worker marked the
  tool in `update_attempted` (`:735`), so the tool is not in that list, and the session
  summary has no failure.
- **Concrete case:** `test_in_flight_latch_skips_outdated_update_and_keeps_the_holder`
  (`tests/test_execute_screen.py:1716`). rg's update is skipped because another update is
  in flight. The screen shows "Failed" and "Not attempted: rg". `_session_exit_code` returns
  0. `fold_run`'s docstring promises the two "cannot disagree", and it also says skips are
  not failures.
- **Consequence:** The user sees a red failure for a benign skip, and CI/scripts see success.
  The two failure signals SAFE-05 is built on contradict each other.
- **Smallest fix:** Delete the two lines that append to `self.not_attempted` (`:963-964`).
  Keep `self._progress[tool.id] = "skipped"`. The worker's `finally` (`:691-693`) already
  reports updates that never ran, so both handlers fold the same list. Add one assert on
  `screen.summary.has_failure is False` to the test above. (−2 lines)

## 2. MEDIUM — The update path still links a directory member and reports success

- **File:** `installer/download.py:332` (`_replace_archive`)
- **Defect:** SAFE-01 added the `is_file()` proof only to the install paths, via
  `link_executable`. The update path checks the swapped binary with
  `live_binary.exists() and os.access(live_binary, os.X_OK)`, and a directory passes both
  checks. The earlier `binary.chmod(0o755)` (`:315`) also succeeds on a directory.
- **Concrete case:** Take a tarball method whose `member` names a directory. This is the
  exact pre-fix Sublime data, and it is still possible for any future registry entry until
  Phase 18. `update_download` swaps the tree, calls `replace_symlink(link, <dir>)` and
  returns success. The result is `~/.local/bin/<bin>` → directory, which is the H1 state
  the phase exists to prevent. Doctor then reports it as broken.
- **Consequence:** The shared invariant ("we link only regular files") holds on install
  and is broken on update. No test covers the update side.
- **Smallest fix:** Change `not live_binary.exists()` to `not live_binary.is_file()`. The
  existing `_undo_archive_swap` rollback then restores the prior tree and link. Add one
  test that mirrors the install-side directory-member test, run through `update_download`.

## 3. LOW — A symlink loop in the bin dir crashes the Uninstall view and `make uninstall --yes`

- **File:** `installer/uninstall.py:148` (`plan_removal`)
- **Defect:** `link.resolve()` is non-strict, and on Python 3.11/3.12 it raises
  `RuntimeError("Symlink loop …")` (I checked on the repo's 3.12.12 venv). Nothing catches
  it. `classify_tools` calls `plan_removal` for every tool, and `run_uninstall` calls it once.
- **Concrete case:** `~/.local/bin/rg -> rg` (a self-loop) with `rg` in the catalog as a
  download tool. The Uninstall view build and `make uninstall --yes` die with a traceback.
  The old `plan_uninstall` did not resolve, so this crash is new. Doctor's `scan_bin_links`
  handles the same link correctly as "dangling".
- **Smallest fix:** Wrap the resolve:
  `try: resolved = link.resolve() except (OSError, RuntimeError): continue`. The link stays
  unproven and goes to "remove it yourself". Add one loop-link fixture.

## 4. LOW — A failed new-mode apply can leave a stray block while the report says "old block restored"

- **File:** `installer/policy.py:242-253` (`move_link_mode`, per-policy restore)
- **Defect:** When `policy.apply()` fails in the new mode, the restore runs
  `set_link_mode(old)`, `apply()`, `set_link_mode(new)` and never calls `remove()` first. The
  ban's `_apply` (`policy.py:407-409`) writes the alias block into each target rc in turn.
  `_rollback` (`:188-202`) does call `remove()` before `apply()` for the same reason.
- **Concrete case:** Move centralized → split with the ban active. `.bashrc` is written,
  then `.zshrc` fails (read-only symlink target). Result: the old block is back in
  `~/.myshellrc`, a ban block also stays in `.bashrc`, and the report says
  "ban (…; old block restored)".
- **Consequence:** A managed block sits in a file the reported state says it is not in.
  It is harmless duplicate aliases until the next toggle, but it is not what the report says.
- **Smallest fix:** Add `policy.remove()` before the restore `policy.apply()` (one line).
  `remove()` strips the union of rc paths, so it also clears the partial write. Extend
  `test_move_link_mode_restores_the_old_block_when_apply_fails` with a two-file partial
  apply.

## 5. LOW — Picking the current link mode removes and re-applies every active ban/tweak

- **File:** `installer/policy.py:205-256` (`move_link_mode`); callers at
  `installer/wizard_app.py:2189-2191` and `:2846-2847`
- **Defect:** There is no `new_mode == old_mode` short-circuit. `LinkModeScreen` always
  offers all three modes, and the first item (centralized) is highlighted. At the first-run
  picker the live default is already centralized, so Enter is a same-mode pick.
- **Concrete case:** First-run picker after a lost or invalid `settings.json` (the D-11
  path), with the ban active. Enter on "Centralized" runs `remove_shims`, strips the alias
  blocks, rewrites them, rewrites the shims, and reports "Moved: ban … moved from
  centralized to centralized".
- **Consequence:** rc and shim churn plus a misleading status for a no-op choice. A
  transient apply failure here would report a failed move that should never have been
  attempted.
- **Smallest fix:** At the top of `move_link_mode`, add
  `if new_mode == old_mode: set_link_mode(new_mode); return ()`. The save still clears the
  invalid-on-disk flag. Add one test.

## 6. LOW — A cancelled run followed by a successful re-run still exits 1

- **File:** `installer/wizard_app.py:3045` (UnifiedApp summary accumulation) → `setup.py`
  `_session_exit_code`
- **Defect:** `not_attempted` (and `update_failed`) are concatenated across every run in
  the session and never cleared when a later run covers those ids.
- **Concrete case:** Select 3 tools, press `c` after the first. Two are not attempted. Run
  the same 2 again and both install. The session still has `not_attempted=(a, b)`, so the
  wizard prints troubleshooting and exits 1.
- **Consequence:** A false failure exit after a normal cancel-and-retry. `failed` already
  behaved this way before Phase 17, and Phase 20 replaces the exit rule, so this is interim.
- **Smallest fix:** In the fold, drop from `existing.not_attempted` and
  `existing.update_failed` every id that appears in `incoming`'s
  installed/already/updated outcomes. Or record it as a known interim limit with a
  `shortcut:` comment that points to Phase 20.

## 7. LOW (lean) — `_rollback` takes a parameter it never uses

- **File:** `installer/policy.py:188` (`_rollback(policies, set_link_mode)`), callers `:240`, `:251`
- **Defect:** The body only loops `policy.remove(); policy.apply()`, so `set_link_mode` is
  dead. Readers will assume the rollback resets the mode, and it does not. The live mode is
  already the old one because `SettingsStore.set_link_mode` saves before it assigns.
- **Smallest fix:** Drop the parameter and the two call-site arguments (−3 tokens, 0 behaviour change).

---

Checked and found sound: `link_executable` reuse of `atomic.replace_symlink` across the
three install sites; the single `link_name` rule shared by install, update and uninstall;
`plan_removal` as the one predicate for the TUI and `--yes` (`app.py:614` and `:694` both
delete only proven paths); `clean_rc_duplicates`' byte comparison at confirm;
`atomic_write_text` at every rc/shim writer; `LoadedSettings` (one read, one parse,
`ValueError` covers both decode errors, the flag clears only after a successful save); D-12
`_build_app` always building `ExecuteInputs`; the graphify hook removed with no leftovers;
Doctor `scan_bin_links` (read-only, loop-safe through `is_dir`/`exists`); the bash-3.2
prune-script changes.

Verdict: fix 1 and 2 first. Lean: −5 lines possible.
Not checked: tests were not run (read-only review). `version_status`/`_reresolve_ownership`
still use the lenient `plan_uninstall` for ownership. That is outside this diff, but it
means update ownership still trusts name matches.

TOTAL: 7 findings
