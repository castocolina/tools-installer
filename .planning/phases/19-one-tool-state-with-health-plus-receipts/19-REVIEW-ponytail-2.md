# Phase 19 — ponytail review, round 2 (gap closure 19-22..19-31)

Scope: `git diff e833961 HEAD -- installer setup.py scripts tests` (26 files, +2284 / -389).
Load assumed: one person running the TUI on their own machine, about 89 catalog tools,
a few worker threads. Same as round 1.

**Severity counts:** High 0 · Medium 1 · Low 4

## What this change does

It closes the round-1 and opencode/deep-review gaps. A `dir` receipt artifact is now
proven by its directory identity (`st_dev`, `st_ino`), the remover deletes by each
artifact's authorized type after a last re-check, and the pass retires a receipt whose
files are all gone. Skill packs stay "checking" only until the current probe answers,
receipts and hook configs are read through one non-blocking capped reader, the catalog
paints from one state snapshot per rebuild, and the update service refuses an
installer-owned update over a drifted receipt.

## Round-1 findings

| # | Finding | Status | Where |
|---|---------|--------|-------|
| P1 | skill pack "checking" forever when no host answers | Closed (19-27, G8) | `version_status.py:1192-1229`: stale or no answers is CHECKING; a fresh all-unknown probe is MISSING with its notes. Test `test_all_unknown_after_the_probe_is_missing_with_a_note`. |
| P2 | all-gone receipt marks a tool BROKEN forever | Closed (19-29, G10) | `receipts.all_gone` + `receipts.retire` (re-read under the write lock), called from `_receipt_evidence`. Artifact-less receipts are never retired. Tests `test_receipt_with_every_artifact_gone_is_retired`, `test_artifactless_receipt_is_never_retired`, `test_retire_refuses_a_replaced_receipt`. |
| P3 | every tab switch re-probes the catalog | Accepted (G15) | 19-25 records the decision: STATE-01 says a tier switch runs one full pass, so host changes made outside the app are seen. A decision, not a finding. |
| P4 | `inspect_skill_packs` has no caller | Closed (19-23, G16) | Deleted; `inspect_status` reads `inspect_skill_reports(...)[id].hosts`. |
| P5 | re-hash memo key misses the digest | Closed (19-22, G6) | The memo now stores the observed sha256 and each call compares it with its own receipt's digest (`receipts.py:430-437`). Better than the round-1 fix. |
| P6 | `tool_health` picks the winner by tuple identity | Closed (19-27, G17) | Compares `state is not winner[0]`. |
| P7 | receipt reader keeps unused fields | Closed (19-22, G18) | Each type builds only its own fields; `_artifact_str` is gone. |

## Must fix

1. **A macOS app that updates itself turns red, and nothing clears it** — Medium
   (`installer/receipts.py:411-416`, `installer/version_status.py:1251`,
   `installer/catalog_tui.py:800`, `installer/update.py:509-521`)
   - **What this is:** Since 19-22, a `dir` artifact matches only while the directory
     has the same inode (the number the filesystem gives one specific directory). The
     `app` method records the `.app` bundle in `~/Applications` as a `dir` artifact.
   - **Problem:** VS Code and draw.io (Electron's Squirrel updater) and Sublime Text
     update themselves. They unpack the new bundle somewhere else and move it into
     place, so the bundle gets a new inode. On the next pass, `drifted` flags it and
     the row turns red `!` "changed since install". Then `u` refuses BROKEN in the TUI
     (`catalog_tui.py:800`), and 19-31's gate refuses it in the execute screen
     (`update.py:509`). Install says it is already installed. Uninstall gets no proof
     from a drifted receipt, and the round-1 P2 fix does not help because the bundle
     still exists. VS Code updates itself by default, so every macOS install made by
     this installer hits this within days. 19-22-PLAN chose to fail closed here
     ("reads as changed since install"). It did not see that, with the 19-31 gate,
     every exit is blocked until Phase 20 ships `r`.
   - **Fix:** Keep the identity check for deletion and drop it for health. Add one
     `receipts` predicate that ignores a drifted `dir` artifact when the path is still
     a real directory and every `link`/`file` artifact still matches. Use it in
     `_receipt_evidence` and in the update gate, not in `_receipt_proof` or
     `remove_paths`. Result: a vendor-replaced bundle reads as OK, `u` can update it,
     and the update re-records the inode. A re-created bundle still can never be
     deleted on an old receipt (G2 stays closed). About 8 lines and one test.
   - **If we skip it:** Every self-updating macOS app installed by this tool shows as
     broken, can't be updated or removed from the app, and keeps that state until
     Phase 20.

## Should fix

2. **One unreadable runtime hides another runtime's "empty" report, and the filter
   meant to prevent that never runs** — Low (`installer/skill_lifecycle.py:570-596`)
   - **What this is:** `inspect_project_pack` builds `inconclusive` (the runtimes with
     an unreadable `skills`/`commands` dir) and leaves them out of `empty`.
   - **Problem:** `empty` is read only in the `elif`/`else` branches, and those run only
     when `unreadable` is empty. When `unreadable` is empty, `inconclusive` is empty
     too. So the `inconclusive` set and its filter are dead code. And in a repo where
     `.claude/skills` is unreadable while `.opencode` has a `gsd-core/VERSION` but no
     entries, the "OpenCode install in proj is empty" reason and its reinstall step
     disappear. 19-23-PLAN said to drop only the inconclusive runtime, plus the repo's
     "not installed in" reason and install steps.
   - **Fix:** Delete the `if unreadable: targets = []` branch. Change the next
     condition to `elif not installed and not empty and not unreadable:`. The `else`
     branch then reports the conclusive empties, and `inconclusive` already keeps the
     unreadable runtime out of them. -2 lines, plus one test with one unreadable
     runtime and one empty runtime in the same repo.
   - **If we skip it:** A rare permission problem in one runtime hides a real,
     fixable empty install in another, and 6 lines stay that never run.

3. **`CatalogScreen._health_of` has no production caller** — Low
   (`installer/catalog_tui.py:485-487`)
   - **What this is:** It was the health source for grouping and sorting. 19-30
     replaced it with `painted_health` inside `_groups`.
   - **Problem:** Only `tests/test_catalog_tui.py:3702` still calls it, and that line
     needs a `pyright: ignore`.
   - **Fix:** Delete the method. In the test, pass
     `lambda t: screen._painted[t.id].health` after a rebuild, or build the health
     from `service.state_of`, the same way `painted_health` does.
   - **If we skip it:** A second health path that nothing in production uses, and
     its next reader may think it matters.

## Nice to have

4. **`remove_proven` checks the same set twice** — Low (`installer/uninstall.py:441-442`)
   - **What this is:** `kept` keeps paths that are `in proven and in fresh.artifacts`.
   - **Problem:** Both branches of `plan_removal` add every `removable` path to
     `artifacts`, so `proven` (`set(fresh.removable)`) adds nothing.
   - **Fix:** `kept = [path for path in paths if path in fresh.artifacts]` and drop the
     `proven` line.
   - **If we skip it:** One extra set a reader has to prove is the same set.

5. **A no-op alias in `_skill_state`** — Low (`installer/version_status.py:1210`)
   - **What this is:** `answered = hosts` right after the early return.
   - **Problem:** Pyright already narrows `hosts` to non-None there, so the alias only
     adds a second name for the same value.
   - **Fix:** Use `hosts` in the three lines below and delete the alias.
   - **If we skip it:** Nothing breaks.

## Checked and fine

- `remove_paths` picks `rmtree` only for an authorized `dir` artifact and re-checks
  `matches` right before each delete. Layout-proven tools are fingerprinted at plan
  time, so they get the same identity check. Receipt order (dir, then link) still
  unlinks the dangling link because `matches` compares `readlink`.
- `retire` re-reads under `_WRITE_LOCK`, so a receipt written in the meantime is kept.
  A mid-update gap (the bundle renamed away for a moment) can retire an app-only
  receipt, but the installer-owned update always records a fresh one afterwards.
- `receipt_exists` counts an inaccessible receipts dir as present: no adoption and no
  archive-layout proof. `read` still fails closed.
- `read_capped` opens with `O_NONBLOCK`, checks type and size on the opened
  descriptor, and caps the read itself. Receipts refuse symlinks; hook configs and
  `installed_plugins.json` follow them on purpose (dotfiles managers).
- The update gate applies only to the `installer` owner. That is correct because
  `artifact_paths` gives artifacts only to download and app kinds, so manager receipts
  cannot drift. A manager update rewrites only a receipt of its own kind (G4).
- `refresh_skills` rebuilds only pack states whose `seq` matches the scan that
  published them, and never re-reads the home (G9).
- The `dir` schema change (new `dev`/`ino`, required) needs no migration: 19-22
  recorded 0 receipts on the host, and an old dir artifact fails closed as unreadable.
- `_painted` is refreshed in `_groups`, and `ToolBrowser._rebuild` always calls
  `groups` before `row_cells`, so cells and grouping agree.

Verdict: fix 1 first.
Lean: -12 lines possible.
Not checked: finding 1 is reasoned from how Squirrel.Mac and Sublime replace a bundle,
not reproduced on a Mac. No real-host pass was run (adoption and retire write under
`$HOME`), and the container e2e script was only read.
