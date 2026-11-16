---
phase: 19-one-tool-state-with-health-plus-receipts
reviewed: 2026-10-17T02:26:10Z
depth: deep
diff_base: 8cea513
reviewed_head: 23d832e
files_reviewed: 29
files_reviewed_list:
  - installer/catalog_tui.py
  - installer/execute_screen.py
  - installer/guards.py
  - installer/receipts.py
  - installer/skill_lifecycle.py
  - installer/status.py
  - installer/terminal_shell.py
  - installer/uninstall.py
  - installer/update.py
  - installer/version_status.py
  - scripts/container-e2e-verify.sh
  - tests/conftest.py
  - tests/test_catalog_tui.py
  - tests/test_container_e2e_receipts.py
  - tests/test_docs.py
  - tests/test_engine.py
  - tests/test_execute_screen.py
  - tests/test_executors.py
  - tests/test_guards.py
  - tests/test_locations.py
  - tests/test_pnpm_globals.py
  - tests/test_receipts.py
  - tests/test_shell_scripts_path.py
  - tests/test_skill_lifecycle.py
  - tests/test_status.py
  - tests/test_terminal_shell.py
  - tests/test_uninstall.py
  - tests/test_update.py
  - tests/test_version_status.py
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
prior_closed: 24
prior_partial: 0
prior_open: 0
status: issues_found
---

# Phase 19: Code Review Report (re-review 3: gap round 2, plans 19-32..19-37)

**Reviewed:** 2026-10-17T02:26:10Z
**Depth:** deep
**Files Reviewed:** 29
**Status:** issues_found

## Summary

Scope: `git diff 8cea513..23d832e -- installer setup.py scripts tests` (29 files,
+1459 / -284): plans 19-32..19-37 plus the test-only fix 24d91d6. I read every
changed hunk and followed it into the code it calls: `receipts.fingerprint` /
`matches` / `_read_artifact` into `plan_removal`, `remove_proven`, the update
gate and `_receipt_evidence`; `_remove_dir` against `recover_update_remnants`;
the shim look-through into `guards.real_binary`; the skill worker against the
pass's publication; the conftest stub against `executors.py`'s seam. I ran the
17 touched test modules under `-n auto` (green, rc=0) and one scratch script
under a scratch HOME. Read-only host checks: `stat`/`du` of `~/.local/opt` and
the receipts dir, `$HOME` vs `$PATH` spelling; no install, no write under the
real HOME. Load assumed: one person running the TUI or CLI on their own machine.

Every round-2 item is closed (24 of 24 after dedupe; the accepted/deferred
set G15, G21/WR-03, IN-02/03/06 and the P19-07 residual was not re-raised).
The binding decision L-19-31 is implemented as written: a dir is proven by the
sha256 of one key file, dir drift is unproven and never BROKEN or
update-refused, file/link drift stays BROKEN, and a dir is removed by rename
to a quarantine sibling, re-hash inside the captured tree, then delete.

One new defect comes with the key-file design: the refresh pass now hashes
every layout-proven archive member on every pass (477 MB on this host, where
no receipt exists yet), where 19-22 did one `lstat` (WR3-01). The rest are
informational.

## Closure table (round 2)

Every row was re-checked against the current source at 23d832e. H/M/L ids are
the dispositions table of 19-32..19-37-PLAN.md.

### 19-REVIEW-2.md (my previous report)

| ID | Item | Verdict | Evidence at HEAD | Pinned by |
|----|------|---------|------------------|-----------|
| CR2-01 | dir receipts compare `st_dev` (H1) | CLOSED | `installer/receipts.py:340-395`: `fingerprint(path, "dir", key=...)` records the key file's sha256/size/mtime_ns and no device or inode; `:412-470` `matches` checks a real dir plus `_file_matches(path / key)`; `:540-582` `_read_artifact` rejects every `dev`/`ino` shape and any unsafe key. Module docstring `:5-14` states why. | `tests/test_receipts.py` `test_dir_fingerprint_records_its_key_file`, `test_dir_recreated_with_the_same_key_file_matches`, `test_old_shape_dir_artifact_is_unreadable`; `tests/test_uninstall.py` `test_dir_recreated_with_the_same_key_file_stays_removable[archive\|app]` |
| WR2-01 | real pnpm behind the redirect shim reads absent (M4) | CLOSED | `installer/status.py:118-134`: the default lookup passes the PATH hit through `guards.look_through_shim(resolved, tool.cmd, shim_dir=implicit, path_value=$PATH)`; `guards.py:331-344` resolves the real binary behind our shim; only a shim with nothing behind it falls through. Residual spelling limit in IN3-02. | `tests/test_status.py:817` `test_real_pnpm_behind_the_redirect_shim_is_presence` (both halves) |
| WR2-02 | self-updating macOS app is BROKEN for good (H1) | CLOSED | `installer/version_status.py:1270-1277`: only a non-dir drift is `CHANGED_SINCE_INSTALL`; dir-only drift returns `UNPROVEN_NOTE` with no broken fact. `installer/update.py:509-521`: the gate refuses only when a drifted artifact is not a `dir`. The duplicate-note guard at `:1609-1614` does not fire (receipt present, `broken` empty). | `tests/test_version_status.py` `test_dir_drift_is_unproven_not_broken` (note count == 1, not removable), `test_partially_gone_receipt_is_unproven_not_broken`; `tests/test_update.py` `test_dir_drift_does_not_block_an_update` (update re-records, `drifted == ()`) |
| WR2-03 | failed skill-cache write strands packs in CHECKING; `invalidate` ordering (M3) | CLOSED | `installer/version_status.py:1030-1041`: the skill save is `try/except OSError` → `_warning`, then `_skills`/`_skills_probed` are set and the packs rebuilt regardless. `:1062-1075`: `invalidate` resets `_skills_probed` and marks answers stale before the write. `installer/catalog_tui.py:431-452`: the worker carries `service.warning` on `SkillStatusRefreshed` and the screen shows it via `_show_cache_warning`. | `tests/test_version_status.py` `test_skill_cache_save_failure_still_settles_the_packs`, `test_failed_invalidate_save_still_reprobes_the_skills`; `tests/test_catalog_tui.py` `test_skill_cache_save_warning_reaches_the_status_line` |
| IN2-01 | "never inherits" does not hold under inode reuse (H1) | CLOSED (moot) | No inode is recorded; `installer/receipts.py:8-14` names the ext4/XFS reuse and btrfs/NFS/ZFS device reasons. | `test_dir_recreated_with_the_same_key_file_matches` |
| IN2-02 | FIFO-blockable reads left in the pass (M6) | CLOSED | `installer/guards.py:279-295` (`is_our_shim`), `installer/terminal_shell.py:260-286` (`_read_text`), `installer/skill_lifecycle.py:711-730` (`_skills_lock_skills`) all go through `atomic.read_capped` (`O_NONBLOCK`, `fstat` type check, cap). `TerminalShellError` is an `OSError` (`terminal_shell.py:22`), so the pass's catch at `version_status.py:1332` still covers the new refusal. | `tests/test_guards.py` `test_is_our_shim_never_blocks_on_a_fifo`; `tests/test_terminal_shell.py` `test_dry_run_never_blocks_on_a_fifo_config`; `tests/test_skill_lifecycle.py` `test_skills_lock_fifo_never_blocks` |
| IN2-03 | preview lists an update the gate refuses (M7) | CLOSED | `installer/execute_screen.py:537-566`: a receipt-BROKEN state (after the `ownership.broken` repair branch, which is the only other BROKEN source, `version_status.py:748`) lands in `_refused`, is removed from `_to_update` and from `_reapply`'s `eligible`; `:521-525` prints `"<id> is broken: <reason>"` (markup off) and `:1146-1151` paints `✖ … update [not done]` from the first frame. An empty reason is refused without indexing (`:555`). | `tests/test_execute_screen.py` `test_drifted_tool_is_refused_before_the_run_starts`, `test_classify_reads_the_state`, `test_broken_tool_with_no_reason_is_still_refused`, `test_drifted_receipt_update_is_refused_per_tool` |
| IN2-04 | `_skill_state` docstring claims agreement with `inspect_status` (L6) | CLOSED | `installer/version_status.py:1157-1165` now states the deliberate difference. | n/a (docstring) |

### H/M/L items from the plan dispositions (19-REVIEW-opencode-plan-review-2 RR-*, 19-REVIEW-ponytail-2 P2-*)

| Item | Source | Verdict | Evidence at HEAD | Pinned by |
|------|--------|---------|------------------|-----------|
| H1 | CR2-01, IN2-01, WR2-02, P2-1, G2 partial | CLOSED | see the four rows above; architecture record `.claude/architecture.md:1062-1071` | `tests/test_docs.py` `_PHASE_19_REQUIRED` ("Contents/Info.plist", "quarantine sibling") |
| H2 | RR-01 dir identity checked apart from the object deleted | CLOSED | `installer/uninstall.py:409-460`: `_remove_dir` makes an exclusive sibling with `mkdtemp(prefix=".<name>.", suffix=".tools-installer.rm", dir=parent)`, renames the dir over it (same filesystem; a swapped-in symlink renames as a symlink and fails the `S_ISDIR` check), re-hashes the key file inside the captured tree via `matches(replace(artifact, path=quarantine), rehash=True)`, and only then `rmtree(quarantine)`. Mismatch → `_put_back`; a failed put-back raises naming both paths and deletes nothing; a failed `rmtree` puts the remainder back. The suffix differs from `atomic.OLD_SUFFIX` (`atomic.py:63`), so `recover_update_remnants` never restores it. | `tests/test_uninstall.py` `test_remove_paths_refuses_a_dir_replaced_after_its_final_check`, `test_remove_paths_keeps_a_captured_dir_it_cannot_put_back`, `test_dir_removal_leaves_no_quarantine_behind`, `test_failed_opt_dir_delete_leaves_the_remainder_listed` (updated to the quarantine path) |
| H3 | RR-02 final check accepts restored metadata | CLOSED | `installer/uninstall.py:479` `receipts.matches(artifact, rehash=True)` before every delete; `_file_matches` with `rehash=True` bypasses the stat shortcut and the memo (`receipts.py:487-488`). | `tests/test_uninstall.py` `test_remove_proven_rehashes_a_file_swapped_after_verification` |
| M1 | RR-03 partial pass strands probed packs | CLOSED | `installer/version_status.py:929-931` `_pack_scans: dict[str, (seq, scan)]`; `:1674-1677` written per published pack under the lock at the one publication point; `:1042-1056` the rebuild uses each pack's own entry. | `tests/test_version_status.py` `test_partial_pack_pass_keeps_every_packs_scan`, `test_the_service_publishes_one_snapshot_of_tool_states` (accepts the third keyed store) |
| M2 | RR-04 duplicates regain an install step | CLOSED | `installer/version_status.py:1117-1120`: any D-18 reason keeps `claude` out of partial targets. Sound because reasons on a `SkillPackReport` come only from `_claude_fixes` (`skill_lifecycle.py:875-928`, attached at `:950-958`). | `tests/test_version_status.py` `test_ambiguous_claude_duplicates_never_get_a_partial_install_step` |
| M3 | WR2-03 | CLOSED | see WR2-03 | see WR2-03 |
| M4 | WR2-01 | CLOSED | see WR2-01 | see WR2-01 |
| M5 | RR-05 inherited manager/XDG overrides reach the real HOME | CLOSED | `tests/conftest.py:100-118`: the autouse fixture clears `PNPM_HOME`, `VOLTA_HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`. | `tests/test_locations.py` `test_inherited_location_overrides_are_cleared` (owner prefixes fall under the scratch HOME) |
| M6 | IN2-02 | CLOSED | see IN2-02 | see IN2-02 |
| M7 | IN2-03 | CLOSED | see IN2-03 | see IN2-03 |
| L1 | RR-06 spaced workspace in the nested `cd` | CLOSED | `scripts/container-e2e-verify.sh:305-306, 320`: `printf -v workspace '%q'` and `cd ${workspace}`; `exec_tester` (`:82-84`) is one `su - tester -c "$1"` parse, so one level of quoting is right. | `tests/test_container_e2e_receipts.py` `test_pre_uninstall_check_survives_a_spaced_workspace` (runs the real function with a spaced symlink and a uv stub) |
| L2 | P2-2 dead `inconclusive` filter; an unreadable runtime hides another's empty install | CLOSED | `installer/skill_lifecycle.py:587-598`: `not installed in` requires no unreadable dir; the `else` reports the conclusive empties, and `inconclusive` keeps the unreadable runtime out of them. | `tests/test_skill_lifecycle.py` `test_unreadable_runtime_never_hides_another_runtimes_empty_install` |
| L3 | P2-3 `CatalogScreen._health_of` has no production caller | CLOSED | Deleted (`installer/catalog_tui.py` diff); the test builds health from `service.state_of` (`tests/test_catalog_tui.py:3703-3712`), with no `pyright: ignore`. | n/a |
| L4 | P2-4 `remove_proven` checks the same set twice | CLOSED | `installer/uninstall.py:501-503` | existing `remove_proven` tests |
| L5 | P2-5 `answered = hosts` alias | CLOSED | `installer/version_status.py:1228-1240` | n/a |
| L6 | IN2-04 | CLOSED | see IN2-04 | n/a |
| 24d91d6 | test-only: host-node fork bomb | CLOSED | `tests/conftest.py:24-29, 210-249`: the autouse fixture stubs `executors.launch_puppeteer` (a module global read at call time, `installer/executors.py:352, 376`, so the patch takes effect) and `real_launch_probe` restores the captured original for the 12 probe tests in `tests/test_executors.py`, which still fake `run_output`. No test in the diff runs a host binary or reads the real HOME. | `tests/test_pnpm_globals.py` `test_the_default_smoke_check_in_the_suite_starts_no_process` |

Counting rule for the frontmatter `prior_*` keys: the 8 ids of 19-REVIEW-2.md
plus the 16 distinct H/M/L items after dedupe (H2, H3, M1, M2, M5, L1, L2, L3,
L4, L5 are new ids; H1, M3, M4, M6, M7, L6 collapse onto 19-REVIEW-2 rows).
Closed 24. Partial 0. Open 0.

## Narrative Findings (AI reviewer)

Fresh ids (WR3-/IN3-). Only these count in the frontmatter `findings` block.
No new `noqa`, `type: ignore`, `nosec`, `pyright: ignore`, skip or xfail in the
diff; `git diff --check` is clean.

## Warnings

### WR3-01: The refresh pass now hashes every layout-proven archive member on every pass, where 19-22 did one `lstat`

**File:** `installer/uninstall.py:150` (`plan_removal`, layout branch) → `installer/receipts.py:381-384` (`fingerprint` for `dir` calls `_file_fingerprint`) → `:398-409` (`sha256_file`, no memo). Callers on the pass: `installer/version_status.py:1597, 1607` (`plan_removal([tool], ...)` for every tool). Trigger frequency: a tier switch runs a full pass (G15, accepted).

**Issue:** The layout proof for a tool with no receipt used to be a directory
`lstat`. Since 19-32 it is a full sha256 of the member the bin link points
to, and `_file_fingerprint` does not use the `(path, size, mtime_ns)` memo
that `_file_matches` has (`receipts.py:491-498`), so nothing in the session
remembers the digest. The digest is then discarded: the pass reads only
`removable.removable` to decide the unproven note (`version_status.py:1609-1614`),
and `ToolState.removable` has no other consumer (IN-02, deferred).

On this host there are 0 receipts and 22 layout-proven tools (every archive
installed before Phase 19), with 477 MB of key files: difft 125 MB, deno
96 MB, ast-grep 52 MB, gh 42 MB, gitleaks 22 MB, lazygit 19 MB, … Hashing
them warm took 0.27 s here (SHA-NI, NVMe); cold, or on an HDD, NFS or
encrypted home, it is seconds of reads per pass, on the one worker thread
every same-epoch `refresh` joins (`done.wait()` has no timeout). It grows
with the install set, and the first pass after boot is always cold.

**Reproduced** (scratch HOME, `plan_removal` on one layout-proven 8 MB rg):
three consecutive calls → three `sha256_file` calls.

Classification note: performance is out of this review's scope, but this is
new, unbounded blocking I/O on the refresh worker introduced by this round,
which the orchestrator asked to be surfaced.

**Fix:** Memo the fingerprint the way the matcher already does, so a key file
is hashed once per session until its size or mtime changes:
```python
# receipts._file_fingerprint
st = path.lstat()
if not stat_module.S_ISREG(st.st_mode):
    return None
memo_key = (str(path), st.st_size, st.st_mtime_ns)
with _MEMO_LOCK:
    digest = _REHASH_MEMO.get(memo_key)
if digest is None:
    digest = sha256_file(path)
    with _MEMO_LOCK:
        _REHASH_MEMO[memo_key] = digest
return ReceiptArtifact(path=path, type="file", sha256=digest, size=st.st_size, mtime_ns=st.st_mtime_ns)
```
`remove_proven` keeps its three `rehash=True` checks, which bypass the memo,
so deletion-time proof is unchanged. Add a test: two `plan_removal` calls on
an unchanged layout-proven tool hash once; a rewritten member hashes again.

## Info

### IN3-01: `_safe_key` does not stop a key from hashing a file outside the directory through an intermediate symlink; the docstring and T-19-104 say it does

**File:** `installer/receipts.py:300-313` (`_safe_key`), `:381` and `:466-467` (`path / key` with `lstat` on the final component only); `19-32-PLAN.md` T-19-104.
**Issue:** A key such as `lnk/x` where `<dir>/lnk` is a symlink to `/etc`
passes `_safe_key` and makes `fingerprint`/`matches` hash `/etc/x`. The
effect is a digest only: the deleted path is always `artifact.path`, and
`rmtree` does not follow symlinks, so nothing outside is removed and the
digest is never shown. The receipt is user-owned, so the threat is
self-inflicted; the claim is just wider than the code.
**Fix:** Reword the docstring and the threat register, or make the matcher
strict the way `link_key` already is at record time: resolve
`(path / key)` with `strict=True` and require `is_relative_to(path.resolve())`.

### IN3-02: The shim look-through compares PATH entries textually, so WR2-01 stays open on a host whose PATH spells the managed bin dir differently from `locations.bin_dir`

**File:** `installer/guards.py:342` (`Path(found).parent == shim_dir`), `:324` (`entry != str(shim_dir)`); consumer `installer/status.py:126-134`.
**Issue:** `shutil.which` returns the PATH entry's spelling. If PATH says
`/var/home/x/.local/bin` while `$HOME` is `/home/x` (a symlinked home), or
the entry carries a trailing slash, the parent comparison fails, the
look-through is skipped, and `_is_installer_shim` makes the real pnpm read
absent again. The comparison predates this round (D-13) and this host spells
both `/home/bazzite`, so the fix works here; the residual is inherited, not
introduced.
**Fix:** Compare resolved paths: `Path(found).parent.resolve() == shim_dir.resolve()`
in `look_through_shim`, and filter `rest` by the resolved entry in
`real_binary`. One test with a trailing-slash PATH entry.

### IN3-03: A crash between the quarantine rename and the delete leaves a hidden `.tools-installer.rm` sibling that nothing lists or cleans

**File:** `installer/uninstall.py:430-436` (rename), `:441-446` (delete); `plan_uninstall` (`:34`) matches by tool name; `atomic.recover_update_remnants` knows only `.old`.
**Issue:** The put-back covers every in-process failure. A SIGKILL, a crash
or a power loss after `os.rename(path, quarantine)` leaves the tool's tree at
`~/.local/opt/.<name>.XXXXXXXX.tools-installer.rm` (or the same under
`~/Applications`). The receipt stays (the link still `lstat`s), the row reads
absent plus the unproven note, `plan_removal` proves nothing (dir missing),
and the hidden sibling is never named to the user. Low likelihood, bounded
loss (the bytes are still there), but invisible.
**Fix:** In `plan_removal`, list `.tools-installer.rm` siblings of a tool's
opt dir or bundle in `yourself`, so the next preview names them; or recover
them at startup next to `recover_update_remnants`, with a test.

### IN3-04: The skill worker re-shows a pass's cache warning and can lose its own

**File:** `installer/catalog_tui.py:437-440`; `installer/version_status.py:1013-1014` (early return), `:1039` (set), `:1691` (cleared only by the pass).
**Issue:** `refresh_skills` never clears `_warning` on a successful skill
save and returns early once probed, so the worker reads whatever the last
pass left in `_warning` and posts it again on every later probe at that
epoch (the same text the pass already showed). Conversely, a pass that
finishes between the failed skill save and the worker's read clears
`_warning` (`:1691`) and the skill failure is never shown. Cosmetic: the
text is identical and the states are published either way.
**Fix:** Let `refresh_skills` own its warning: set `self._warning = None`
after a successful skill save, and have the worker read it under the same
call (return `(hosts, warning)` or a small dataclass).

## Checked and fine

- Receipt order for an archive is (dir, link). `_remove_dir` quarantines and
  deletes the dir first; the link then still matches by `readlink` and is
  unlinked. Layout-proven order is (link, dir); the dir proof does not depend
  on the link, so the capture and re-hash work either way.
- `_receipt_proof` with `verify=True` still returns nothing when any artifact
  drifted, dir included, so a dir-drifted tool is not removable at all
  (L-19-31), and `remove_proven`'s fresh plan refuses it before `remove_paths`.
- `os.rename(dir, empty_dir)` replaces the empty `mkdtemp` directory on Linux
  and macOS; EXDEV/EBUSY on a mount point removes the empty sibling and raises
  with nothing deleted.
- `record` drops a dir whose key file is missing (`app` without
  `Contents/Info.plist`; a link that does not resolve into the dir), so such a
  receipt holds only the link and retires when the link goes.
- The 19-22 `dev`/`ino` schema never shipped: `v0.49.0` (the latest tag) has no
  `installer/receipts.py`, so "every 19-22 artifact is unreadable" affects no
  user data.
- `tool_health`'s BROKEN sources are exactly `BROKEN_SHIM_REASON` and
  `CHANGED_SINCE_INSTALL` (`version_status.py:748`), so the execute screen's
  `elif state.health is Health.BROKEN` after the repair branch refuses only
  what the update gate would refuse.
- `invalidate` leaves memory consistent when the write raises; the OSError
  still reaches the caller through `run_live`.
- The remaining hash-then-`unlink`-by-name gap for `file` artifacts
  (`uninstall.py:479-487`) is the irreducible residual of unlinking by name,
  not a regression; RR-02's restored-metadata case is closed.

---

_Reviewed: 2026-10-17T02:26:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
