---
phase: 16
status: issues_found
depth: standard
files_reviewed: 47
files_reviewed_list:
  - installer/app.py
  - installer/catalog_tui.py
  - installer/engine.py
  - installer/execute_screen.py
  - installer/executors.py
  - installer/guidance.py
  - installer/install_ownership.py
  - installer/locations.py
  - installer/model.py
  - installer/ownership.py
  - installer/post_install.py
  - installer/rcclean.py
  - installer/registry.toml
  - installer/resolve.py
  - installer/selection.py
  - installer/shellrc.py
  - installer/skill_lifecycle.py
  - installer/status.py
  - installer/uninstall.py
  - installer/update.py
  - installer/version_cache.py
  - installer/version_status.py
  - installer/wizard_app.py
  - setup.py
  - tests/ (23 files: conftest and test_* for each module above)
findings:
  critical: 0
  warning: 1
  info: 9
  total: 10
---

# Phase 16: Code Review Report

**Reviewed:** 2026-10-10
**Depth:** standard (repo config says `deep`; this run was scoped to standard by the orchestrator)
**Files reviewed:** 47 (range base `2eaae39`, HEAD `a2dc3da`)
**Status:** issues_found

## Summary

Phase 16 moves detection, version and ownership to filesystem proofs and adds the Doctor PATH-writer guard. The security-sensitive paths held up: the guard rewrite re-reads and compares each recorded line, takes a snapshot, refuses on hazards (symlink, non-UTF-8, changed file), creates the backup create-exclusive and re-checks before an atomic write that preserves the mode; skill-pack inputs are regex-validated and shell-quoted; `run_query` has a timeout and its `CommandError` is caught where skill probes run. No Critical issue was found. One Warning concerns a permanent, misleadingly worded refusal on a second guard of the same rc file. The Info items are heuristic limits in the rc scanner and ownership proofs plus a few edge cases.

The review was done inline by the fork rather than through a spawned `gsd-code-reviewer` agent, and the rc scanner was probed empirically with a scratch script (not committed). The `tests/` files were spot-checked for suppressions only (only `pyright: ignore[reportPrivateUsage]` and `type: ignore[method-assign]` on test doubles; one `noqa: BLE001` in production with a stated isolation-boundary reason).

## Warnings

### WR-01: A second PATH-writer guard of the same rc file is refused forever with a misleading message

**File:** `installer/shellrc.py:1184`
**Issue:** `guard_path_writers` calls `backup_precondition(rc_path, snapshot)` (defined at `installer/shellrc.py:935`, refusal text at line 967). After the first successful guard, `<rc>.tools-installer.old` holds the pre-guard original and the live file differs from it. Any later guard of the same file (a new writer appears, or the user guards the remaining lines after a partial selection) returns "`<backup>` already holds a different original; move or remove it if you want consolidation to proceed". The text names "consolidation", which is the other flow that shares the precondition, and the refusal stays until the user deletes the backup by hand. No data is lost and the refusal fails safe, but the Doctor guard flow dead-ends for the file with no actionable wording.
**Fix:** Give the guard its own message (name the guard, say the previous backup is kept as the pre-guard original and must be moved aside), or allow a second guard when the existing backup equals the content the previous guard wrote from, or write a numbered backup (`.tools-installer.old.1`) when the primary name is taken.

## Info

### IN-01: Heredoc body lines are treated as guardable PATH writers

**File:** `installer/rcclean.py:283`
**Issue:** `_judge_line` and `path_writer_lines` (`installer/rcclean.py:490`) work line by line with no heredoc awareness. Probed: a `PATH=...:$PATH` line inside a `cat <<EOF` body is reported with `guardable=True`, so confirming the guard would rewrite heredoc data instead of a shell statement. The per-file confirmation modal and the text-unchanged check do not catch this, because the line text matches.
**Fix:** Track heredoc openers (`<<`, `<<-`, quoted or bare delimiter) in the line walk and mark body lines as non-guardable with a reason.

### IN-02: A one-shot `PATH=... cmd` prefix is reported as a persistent writer

**File:** `installer/rcclean.py:337`
**Issue:** `_path_line_targets` treats `PATH=/m:$PATH cmd` as a PATH writer. The assignment applies only to `cmd`'s environment, so it never reaches the session PATH. It shows up as a Doctor finding that explains nothing about a duplicate.
**Fix:** Skip assignments that are followed by a command word on the same simple command (no `export`, no bare assignment).

### IN-03: Skill-pack matches can hit a same-named entry from another source

**File:** `installer/skill_lifecycle.py:34`
**Issue:** `_claude_matches` matches `<name>@` prefixes and `_pi_matches` matches any `.../<name>` or `...:<name>` suffix, and the Claude/Pi outputs carry the marketplace or source. A plugin with the same name from a different source reads as the declared pack being installed.
**Fix:** Match the full `name@marketplace` (or source) taken from the registry entry when one is declared.

### IN-04: Ownership is attributed from bare file presence at the declared `bin_dir`

**File:** `installer/ownership.py:896`
**Issue:** `_location_proof` proves ownership when the command exists at a method's declared `bin_dir` (for example `~/.local/bin` for uv and antigravity). A hand-copied binary or another tool's shim in the same directory is attributed to the method. It fails closed when two managers claim the same directory, so the harm is a wrong label, not a wrong action.
**Fix:** Require a corroborating signal where the manager offers one (receipt, symlink target, manager list) before treating presence as proof for shared directories.

### IN-05: Keg-only brew probe stats `opt/<formula>/bin/<cmd>` for every formula

**File:** `installer/ownership.py:521`
**Issue:** `_undeclared_brew_candidate` builds one proof path per installed formula for every tool in the catalog (formulae times tools stat calls). Already noted in a `shortcut:` comment; with a few hundred formulae and a large catalog this is thousands of stats per refresh.
**Fix:** Build a cmd to formula index once per inventory.

### IN-06: `path_scan_rc_paths` can raise on an unreadable `~/.bashrc.d` entry

**File:** `installer/locations.py:128`
**Issue:** `sorted(p for p in bashrc_d.glob("*") if p.is_file())` calls `Path.is_file()`, which re-raises permission errors on some Python versions. A single unreadable snippet would take the whole Doctor PATH scan down.
**Fix:** Wrap the `is_file()` check in a small helper that returns False on `OSError`.

### IN-07: `dangling_shim` keys on package names only

**File:** `installer/status.py:98`
**Issue:** The shim counts as dangling when none of the tool's `npm_pkg` names appears in the pnpm globals. If a different pnpm package supplies the same command, the tool is reported broken and offered a repair that reinstalls the declared package. Rare, and the repair is non-destructive.
**Fix:** Optionally confirm the shim's resolved target no longer exists, in addition to the package check.

### IN-08: Version probe still executes the resolved binary with `--version`

**File:** `installer/version_status.py:225`
**Issue:** For installer-owned and github_release tools `_version_argv` runs `<active_path> --version` (the pre-existing fallback), which contradicts the phase intent of "from the filesystem, not from a binary invocation" for those owners. The run is bounded by `run_query`'s timeout, so this is a scope observation, not a defect.
**Fix:** Document the remaining binary-invocation path in the phase verification, or extend `version_file` coverage to those owners.

### IN-09: Test-only suppressions are concentrated in TUI tests

**File:** `tests/test_catalog_tui.py:1`
**Issue:** About twenty `# pyright: ignore[reportPrivateUsage]` and three `# type: ignore[method-assign]` were added to reach `_row_cells`, `_detail_text`, `_ownership` and `_update_tool_worker`. They are scoped to rules and pass the gate, but they couple the tests to private names.
**Fix:** Optional: expose a narrow public test seam on `CatalogScreen` and `VersionRefreshService`.

---

_Reviewed: 2026-10-10_
_Reviewer: Claude (gsd-code-review, inline fork run)_
_Depth: standard_
