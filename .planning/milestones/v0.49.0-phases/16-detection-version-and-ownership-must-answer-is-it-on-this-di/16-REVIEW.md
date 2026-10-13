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
  warning: 4
  info: 18
  total: 22
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

## Second lane (opencode-go/glm-5.2; codex unavailable: expired login)

**Lane:** `opencode run --model opencode-go/glm-5.2 --agent plan` (read-only plan agent), four calls over the production diff `2eaae39..HEAD` grouped as ownership, versions/TUI, rc/guard, engine/skills/registry. Each prompt carried the diff, AGENTS.md, 16-CONTEXT.md and the first lane's findings (to skip). The tree stayed clean (`git status --short` empty) after the run.
**Result:** 12 new findings, all re-checked against the source (rc scanner claims reproduced by calling the pure functions; ownership claim verified by reading, no test run). Every finding below was raised by this lane; none duplicates WR-01 or IN-01..IN-09. Severity mapping: lane High/Medium become `WR-`, Low becomes `IN-`; two lane Medium findings were lowered to Low after checking impact. No claim was rejected as false.

### Warnings

#### WR-02: `then`/`do` body line is a strip candidate; stripping it breaks the rc file

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** High (lane rating; rare trigger, severe effect).
**File:** `installer/rcclean.py:245`
**Issue:** `_command_text` removes a leading `then `/`do ` so `find_duplicate_path_lines` treats `then PATH="$HOME/.local/bin:$PATH"` (column 0) as a plain strip candidate (`installer/rcclean.py:406-412`). Verified by calling the pure functions: input `if [ -d "$HOME/.local/bin" ]\nthen PATH=...\nfi` returns `[1]`, and `until false\ndo PATH=...\ndone` returns `[1]`. `strip_lines` then deletes the `then`/`do` line, leaving `if ...` followed by `fi`, a bash syntax error on every shell start. The guard flow already refuses the same line ('shares its line with other commands', `_guard_refusal`), so the two flows disagree. Base 2eaae39 matched raw lines and never saw these.
**Fix:** Mark records whose original segment started with `then`/`do` as non-simple (or compare against the raw line start) so `find_duplicate_path_lines` skips them.

#### WR-03: Skill packs with no `status_probes` (openspec, spec-kit) render as missing with an empty Ver cell

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Medium.
**File:** `installer/catalog_tui.py:479`
**Issue:** `_present` returns `None` when `SkillHostStatus.hosts` is empty. `openspec` and `spec-kit` declare zero `status_probes` (checked by parsing registry.toml), so `inspect_skill_packs` gives `hosts={}` for them forever. `_ver_cell` (line 517) then blanks the Ver cell and `_presence`/`_groups` (line 645) put the row in the missing group, while `_inst_cell` (line 499) falls back to the PATH answer and draws a green check. The row contradicts itself and loses the version the pre-phase code showed.
**Fix:** In `_present`, fall back to `self._installed[tool.id]` when the pack declares no `status_probes`.

#### WR-04: by_harness install handoff drops the framing text and ships unattributed, ambiguous lines

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Medium.
**File:** `installer/skill_lifecycle.py:270`
**Issue:** `perform_action` returns only `_filtered_install_lines(...)` for a `by_harness` install, so `operation.instructions` is never shown. For `superpowers` (installer/registry.toml, `[tool.skill_lifecycle.install.by_harness]`), a Codex-only host sees just `/plugins` and `superpowers` with no verb or host name, and a Claude-only host sees three lines that read as one sequence although the official-marketplace line and the obra marketplace pair are alternative sources. Nothing mutates, but this is the flagship handoff of the phase and D-15 wants filtered, understandable instructions.
**Fix:** Prefix each host's lines with the host name and a verb, and mark alternatives (`or`) in the registry; render `operation.instructions` or a short header once.

### Info

#### IN-10: A location-proven candidate that is not the live binary blocks native and OS-package attribution

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low (lane rated Medium; verified by reading, not by a test run).
**File:** `installer/ownership.py:948`
**Issue:** `_collect_candidates` creates a sdkman or installer candidate from bare presence at the method's `bin_dir`. `_native_owner` (line 770) and `_os_package_owner` (line 867) return `None` whenever `candidates` is non-empty, and only the undeclared-brew candidate is stripped by the D-06 `gated` step in `resolve_ownership`. With kitty at `~/.local/kitty.app/bin/kitty` plus a dnf copy active at `/usr/bin/kitty`, or java at `~/.sdkman/candidates/java/current/bin/java` plus a distro `/usr/bin/java`, the Owner cell becomes `unknown` where the base commit attributed the OS package. Mutations still refuse, so only the label is wrong, and only on hosts with two copies.
**Fix:** Treat a non-active location candidate like the shadow brew candidate: exclude it from the gate and attach it as a shadow.

#### IN-11: Closer word inside a trailing comment or quote makes an opener look self-closing

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low (lane rated Medium).
**File:** `installer/rcclean.py:106`
**Issue:** `_has_standalone_closer` searches the whole raw line. `if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then  # keep until fi` followed by an indented `PATH=...` and `fi` pushes no frame, so the properly guarded body line is reported as unguarded and guardable (verified: record index 1, `presence_guarded=False`, refusal `None`). Confirming rewrites a correct line and burns the single `.tools-installer.old` backup slot (see WR-01).
**Fix:** Strip comments and quoted text before the closer search.

#### IN-12: Doctor keeps advertising an enter action that `applied` has made inert

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low (lane rated Medium).
**File:** `installer/wizard_app.py:622`
**Issue:** `action_apply` returns at once when `self.applied`, but `_writer_next_step` (`installer/guidance.py:86-89`) still says 'Press enter (apply) to guard it in place' whenever a guardable record remains, and `_finish_guard_chain` re-adopts the records the user declined. After enter then escape on the modal, the text stays and enter does nothing until the app restarts (pinned as intended by `test_doctor_guard_chain_does_not_restart_after_apply`).
**Fix:** Drop the enter hint once `applied` is true, or let enter restart the guard chain.

#### IN-13: One-line `if/elif` consults only the `if` condition

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low.
**File:** `installer/rcclean.py:296`
**Issue:** `if [ -x /a ]; then :; elif [[ ":$PATH:" != *":$HOME/bin:"* ]]; then PATH="$HOME/bin:$PATH"; fi` is reported as an unguarded writer with 'edit it by hand' advice (verified: refusal 'shares its line with other commands or a comment'), although the PATH line only runs when the directory is absent. The multi-line form is handled.
**Fix:** Parse `elif` conditions on the one-line form or classify the line as unknown rather than unguarded.

#### IN-14: A single-directory PATH replacement is refused as 'adds more than one directory'

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low.
**File:** `installer/rcclean.py:482`
**Issue:** `PATH=/opt/tools/bin` (no `$PATH`) falls through every check to `_REFUSE_MULTI` (verified). The refusal is right, the reason names the wrong hazard; the real one is a total PATH replacement.
**Fix:** Add a dedicated refusal text for a line that never references `$PATH`.

#### IN-15: 'Already current' is stated for rows whose status is flagged stale

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low.
**File:** `installer/catalog_tui.py:912`
**Issue:** `action_update_tool` prints '<id> is already current' whenever `status.outdated is False`. A github_release row with a failed or budget-skipped tag fetch has `outdated=False, stale=True` (`installer/version_status.py:196-198`), so the message contradicts the cached-latest marker on the same screen.
**Fix:** Gate on `not status.stale` or word it as 'current as of the last check'.

#### IN-16: alacritty comment says kitty has no applicable method on immutable Fedora

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low.
**File:** `installer/registry.toml:2652`
**Issue:** kitty now has a `script` method with `os = ["debian","arch","fedora"]` (registry.toml:2553), which `resolve._applies` allows on immutable hosts, so 'Same accepted Bazzite gap as kitty' is false and can mislead a registry editor.
**Fix:** Reword the alacritty comment to drop the kitty comparison.

#### IN-17: `install-state` status probe ignores its declared `match`

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low.
**File:** `installer/skill_lifecycle.py:360`
**Issue:** `_install_state_status` hardcodes `gsd-install-state.json`, while `installer/model.py` requires and validates a `match` for every probe. A future pack declaring `via = "install-state"` with another match passes load and is answered from GSD's state file.
**Fix:** Use `match` as the state-file stem, or reject `install-state` for non-GSD packs at load time.

#### IN-18: Duplicate-harness `status_probes` pass validation and collapse last-wins

**Source:** opencode-go/glm-5.2 lane. **Lane rating:** Low.
**File:** `installer/skill_lifecycle.py:392`
**Issue:** `_pack_status` builds `{probe.harness: probe ...}`; `_parse_status_probes` (`installer/model.py:401`) has no duplicate-harness check, unlike other list fields. Two probes for the same harness silently drop the first.
**Fix:** Raise at load time on a repeated harness.

### Rejected claims

None. Not repeated from the lane output: its 'verified clean' notes (cache locking, epoch discard, `_undeclared_brew_candidate`, `install_tool` repair flag, `executors._script` args), which are not findings.
