# Phase 19 — ponytail review

Scope: `git diff 5e4bfa7 HEAD -- installer setup.py scripts tests` (55 files, +14497 / -2615).
Load assumed: one person running the TUI on their own machine. There is one refresh
service per app, a catalog of about 89 tools, and a few worker threads.

**Severity counts:** High 0 · Medium 2 · Low 5

## What this change does

Every view now reads one per-tool record, `ToolState`, from one refresh pass. Each
record has one Health mark (checking, broken, config, update, ok, missing,
unavailable) and the reasons behind it. The old separate installed, version and
ownership maps are gone. A successful install or update now writes a JSON receipt
under `~/.local/state/tools-installer/receipts/`. Uninstall deletes only what a
receipt (or the old archive-layout rule) still proves, and it checks the proof again
with a re-hash when it deletes. The pass also batches native ownership queries into
one call, recognizes Volta, `uv tool dir` and host-setup owners, and reports
skill-pack, project-pack (opengsd), terminal and pnpm-group misconfiguration.

## Must fix

1. **A skill pack whose hosts never answer shows "checking" forever** — Medium
   (`installer/version_status.py:1175-1178`)
   - **What this is:** `_skill_state` gives a skill pack the CHECKING health until at
     least one host answers "present" or "absent".
   - **Problem:** A finished, non-stale probe can still answer "unknown" for every
     host. That happens when the harness CLIs are not installed (the probe raises
     `FileNotFoundError`), or when `claude plugin list --json` is unreadable (for
     example, an older Claude CLI without `--json`). Then superpowers or ponytail
     keep `…` "checking which hosts have it" for the whole session. Pressing `u`
     says "its state is still being checked — try again in a moment"
     (`catalog_tui.py:773`), and trying again never helps. I reproduced this with
     the test doubles: `_pack_service(..., _unreadable_probe("raises"),
     harnesses=frozenset())` gives `Health.CHECKING` after `refresh` +
     `refresh_skills`, and again after a second pass.
   - **Fix:** Say "checking" only while no real answer has arrived:
     `if hosts is None or (hosts.stale and not answers & {"present", "absent"}):`.
     A probed all-unknown pack then reads absent (MISSING). The
     `skill configuration not checked: no readable answer from …` notes that already
     exist explain why. This is a one-line change, plus one assertion on
     `state.health` in `test_inconclusive_claude_listing_is_a_not_checked_note`.
   - **If we skip it:** Users without Claude/Codex/pi, or with an older Claude CLI,
     see packs stuck on "checking" with no way out.

2. **A receipt whose files are all gone marks a working tool broken, and nothing
   clears it** — Medium (`installer/version_status.py:1217`,
   `installer/uninstall.py:83`)
   - **What this is:** `_receipt_evidence` says BROKEN ("changed since install")
     when any receipt artifact no longer matches. A missing file also counts as "no
     longer matches".
   - **Problem:** Example: the user runs `rm ~/.local/bin/yq` (or removes
     `~/.local/opt/rg` and its link), then installs the tool with dnf or brew. The
     tool is present, so the receipt with only missing artifacts turns it red `!`
     with the reason "changed since install", next to "managed by dnf". Nothing in
     this phase can clear that mark:
     - install short-circuits to ALREADY_INSTALLED, because BROKEN counts as present,
     - repair is limited to the pnpm-shim case,
     - `u` refuses BROKEN (`catalog_tui.py:778`),
     - `_receipt_proof` proves nothing for a drifted receipt, so `remove_proven`
       never retires it.
   - **Fix:** Reuse the rule `remove_proven` already applies: once every path a
     receipt names is gone, the receipt has nothing left to protect. In
     `_receipt_evidence`, when `all(not _exists(a.path) for a in receipt.artifacts)`
     and `receipt.artifacts` is not empty, call `receipts.delete(tool.id)` and treat
     the tool as having no receipt (adoption can then run). A pass that already
     writes receipts through adoption can also retire them. Partial drift stays
     BROKEN. One test: an all-missing receipt next to a present tool gives a non-BROKEN
     state and no receipt file.
   - **If we skip it:** Removing an installer copy by hand and switching to a package
     manager leaves a permanent false "broken" until Phase 20 adds `r`.

## Should fix

3. **Every tab switch re-probes the whole catalog** — Low
   (`installer/catalog_tui.py:413`)
   - **What this is:** `_refresh_versions_worker` now refreshes `self._catalog`
     (about 89 tools) instead of the tier's tools, and `enter_view` starts it on
     every view entry.
   - **Problem:** One pass runs a `--version` subprocess per present tool, a native
     batch query, a terminal dry-run, `uv tool dir`, and the opengsd repo walk (up to
     5000 dirs and 50 000 entries). Before this phase, a tab switch probed only that
     tier. Now each switch repeats the full catalog, even though the current epoch's
     states are still valid. Joining only helps when two passes overlap in time.
   - **Fix:** In `_start_version_refresh`, skip the worker when every catalog tool
     already has a state at the current epoch:
     `all(service.state_of(t.id) for t in self._catalog)`. Repaint only. Mutations
     already bump the epoch, so a real change still triggers a pass.
   - **If we skip it:** Tab switches cost a full probe sweep, with the CPU and time
     that come with it. Not measured: I did not run a real pass, because adoption
     writes receipts into the real `$HOME`.

4. **`inspect_skill_packs` has no production caller** — Low
   (`installer/skill_lifecycle.py:913-920`)
   - **What this is:** It is now an 8-line projection of `inspect_skill_reports`.
   - **Problem:** Nothing in `installer/` or `setup.py` calls it. Only its own test,
     `test_inspect_skill_packs_is_the_hosts_projection`, keeps it alive.
   - **Fix:** Delete the function and that test. Tests that need hosts can read
     `inspect_skill_reports(...)[id].hosts`.
   - **If we skip it:** One more public name to keep in sync for no caller.

## Nice to have

5. **The re-hash memo forgets which digest it compared against** — Low
   (`installer/receipts.py:359-365`)
   - **What this is:** `_REHASH_MEMO` maps `(path, size, mtime_ns)` to "matches the
     recorded sha256".
   - **Problem:** The key leaves out the receipt's sha256. If a receipt is rewritten
     with a new digest while the file's size and mtime come back to a remembered
     value, the old answer is reused. This is unlikely, because the stat shortcut runs
     first, but the key is one token short of being exact.
   - **Fix:** `key = (str(path), st.st_size, st.st_mtime_ns, artifact.sha256)`.
   - **If we skip it:** A rare stale "matches" on the health mark. Deletion is not
     affected, because it uses `rehash=True`.

6. **`tool_health` picks the winner by tuple identity** — Low
   (`installer/version_status.py:235`)
   - **What this is:** `if facts is not winner[1]` skips the winner's own facts when
     it appends the other groups.
   - **Problem:** This relies on object identity. Two groups that hold the same tuple
     object would make the second one vanish. Only `dict.fromkeys` hides that today.
   - **Fix:** Compare states instead:
     `for state, facts in groups: if state is not winner[0]: reasons += facts`.
   - **If we skip it:** Nothing breaks today. The code is a trap for the next edit.

7. **The receipt reader keeps fields that no type uses** — Low
   (`installer/receipts.py:415-442`)
   - **What this is:** `_read_artifact` copies `target` onto `file` artifacts, and
     `sha256`/`size`/`mtime_ns` onto `link` and `dir` artifacts.
   - **Problem:** `matches` never reads those fields for those types, and the writer
     only fills them by accident of the shared dataclass. That is about 12 lines of
     parsing with no effect.
   - **Fix:** Build `link` with `target` only and `dir` with `path` only. Drop
     `_artifact_str` and keep `_artifact_int` for the file branch.
   - **If we skip it:** Dead parsing that a reader must still check.

## Checked and fine

- `remove_proven` and the TUI/CLI share one remover. The deletion-time re-hash
  (`verify=True`) and the `(path, type)` intersection with `artifact_paths` stop a
  user-written receipt from widening or retyping a delete.
- `receipts.read` fails closed on size, encoding, nesting, version, id and per-type
  fields.
- The `refresh` join/epoch/seq logic does not join across `invalidate`, a raced pass
  publishes nothing, and an older pass never overwrites a newer record.
- `NativeIndex` parses the batch by path and not by position, falls back to unowned
  for paths it did not collect, and has tests for rpm, dpkg and pacman.
- `_find_project_repos` never follows symlinks and is bounded by depth, dir count and
  entry count. Claude plugin ids are checked before they reach any argv.
- The `hooks` receipt field is always `{}` and `ToolState.receipt` has no reader yet.
  Both are locked by CONTEXT for Phases 20 and 23, so they are a decision and not a
  finding.

Verdict: fix 1 and 2 first.
Lean: -25 lines possible.
Not checked: real-host pass timing (adoption writes receipts, so I did not run a pass
on the real `$HOME`), and the container e2e script (`scripts/container-e2e-verify.sh`)
was only read, not executed.
