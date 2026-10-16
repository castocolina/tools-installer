---
phase: 19-one-tool-state-with-health-plus-receipts
reviewed: 2026-10-16T22:47:19Z
depth: deep
diff_base: e833961cdc53b9cb263a5e8778c4206d6191d8c1
reviewed_head: 8cea513
files_reviewed: 26
files_reviewed_list:
  - installer/atomic.py
  - installer/catalog_tui.py
  - installer/engine.py
  - installer/host_setup.py
  - installer/receipts.py
  - installer/skill_lifecycle.py
  - installer/status.py
  - installer/uninstall.py
  - installer/update.py
  - installer/version_status.py
  - scripts/container-e2e-verify.sh
  - tests/conftest.py
  - tests/test_atomic.py
  - tests/test_catalog_tui.py
  - tests/test_container_e2e_receipts.py
  - tests/test_engine.py
  - tests/test_execute_screen.py
  - tests/test_host_setup.py
  - tests/test_locations.py
  - tests/test_receipts.py
  - tests/test_skill_lifecycle.py
  - tests/test_status.py
  - tests/test_tool_health.py
  - tests/test_uninstall.py
  - tests/test_update.py
  - tests/test_version_status.py
findings:
  critical: 1
  warning: 3
  info: 4
  total: 8
prior_closed: 18
prior_partial: 2
prior_open: 1
status: issues_found
---

# Phase 19: Code Review Report (re-review 2: gap closure 19-22..19-31)

**Reviewed:** 2026-10-16T22:47:19Z
**Depth:** deep
**Files Reviewed:** 26
**Status:** issues_found

## Summary

Scope: `git diff e833961..8cea513` over the 26 listed files (plans 19-22..19-31).
HEAD moved to 65d9f1d during the review, but those two commits add only other
lanes' review docs, so the reviewed source is the same. I read every changed
hunk and followed it across modules: receipts -> uninstall/update/version_status,
the skill worker against the pass, the catalog rebuild, `is_installed` against
its CLI callers. I ran the touched test modules (`test_receipts`,
`test_uninstall`, `test_update`, `test_atomic`, `test_status`,
`test_skill_lifecycle`, `test_tool_health`, `test_host_setup`,
`test_version_status`, `test_catalog_tui`, `test_execute_screen`,
`test_locations`, `test_container_e2e_receipts`, `test_engine`). All pass. I
reproduced three of the new defects in scratch scripts under a scratch HOME.
Load assumed: one person running the TUI or CLI on their own machine.

Most fixes are correct and tested. Of the 21 Critical/Warning-level items
across 19-REVIEW.md and the three cross-lane reports (after dedupe), 18 are
closed, 2 are partial and 1 is still open by decision (WR-03).

The fixes also brought in new defects. They come from the new directory
identity (G2) combined with the new update gate (G3), from the shim fix (G13)
going too far, and from G8 interacting with an existing cache-write path:

- A directory receipt compares `st_dev`. On btrfs, NFS and ZFS that number is
  handed out at mount time. On this developer's own Bazzite host, the home
  subvolume's number was assigned in the middle of the boot mounts. A reboot
  can turn every archive tool BROKEN, block every update and stop uninstall
  from removing anything (CR2-01).
- A real pnpm that sits behind the installer's own pnpm redirect shim now
  reads as not installed on the headless CLI route (WR2-01).
- A macOS app that updates itself becomes BROKEN for good, and no installer
  action can clear it (WR2-02).
- If writing the skill cache fails, every probed skill pack shows "checking"
  for the rest of the session (WR2-03).

## Prior findings disposition (19-REVIEW.md)

| ID | Verdict | Evidence at HEAD | Pinned by |
|----|---------|------------------|-----------|
| CR-01 (BROKEN tool overwritten via the update route) | CLOSED | `installer/update.py:507-521`. `UpdateService.run`, the one gate for `u` and the execute screen, refuses an installer-owned update while `receipts.drifted(receipt, rehash=True)`. An all-gone receipt is let through (`update.py:513`). | `tests/test_update.py:1469` `test_update_service_refuses_a_drifted_receipt`, `:1499` `test_all_gone_receipt_does_not_block_an_update`. `tests/test_execute_screen.py:4541` `test_drifted_receipt_update_is_refused_per_tool`. See IN2-03 for the preview wording. |
| WR-01 (manager update replaces another kind's receipt) | CLOSED | `installer/update.py:346-354`: a manager update rewrites a receipt only when `existing.method.kind == method.kind`. | `tests/test_update.py:1452` `test_manager_update_keeps_an_installer_receipt` |
| WR-02 (shim on PATH counted as presence) | PARTIAL | `installer/status.py:123-128` now skips the shim on the PATH hit. That fixes the reported case (shim present, real pnpm removed). But the fix never looks behind the shim, so a real pnpm further down PATH now reads as absent. See WR2-01. | `tests/test_status.py:784` `test_installer_shim_on_path_is_never_presence` (shim-only case) |
| WR-03 ("reinstall with r" points at a bound key) | OPEN (accepted as G21, deferred to Phase 20) | `installer/version_status.py:606` `UNPROVEN_NOTE` is unchanged and still emitted at `:1585-1592`. `installer/catalog_tui.py:317` still binds `r` to `accept_recommends`. G2 makes this worse: more rows now reach this note (WR2-02). | none |
| WR-04 (dir artifacts proven by existence; rmtree of a user bundle) | CLOSED for the reported macOS case | `installer/receipts.py:385-389` (fingerprint records `(st_dev, st_ino)`), `:411-416` (match requires the same identity), `:494-498` (the reader rejects a dir without identity). On APFS a trashed and reinstalled bundle gets a new inode. The identity choice causes CR2-01 and WR2-02 and is weaker on ext4/XFS (IN2-01). | `tests/test_receipts.py:738` `test_recreated_dir_does_not_match`, `tests/test_uninstall.py:2150` `test_recreated_dir_artifact_is_not_removable[archive\|app]` |
| WR-05 (pi update hint drops `--ignore-scripts`) | CLOSED | `installer/update.py:312-333` quotes `host_setup.pnpm_add_command` (`installer/host_setup.py:47-56`). The fallback carries `--ignore-scripts`. Even through the redirect shim, `--ignore-scripts` turns off the volta branch (`guards.py` known-flag rule), so the command passes through to real pnpm. | `tests/test_update.py:1398` `test_host_setup_update_hint_is_the_reviewed_handoff`, `tests/test_host_setup.py` `test_reviewed_handoff_names_one_pnpm_add_command` |
| IN-01 (re-hash memo key omits the digest) | CLOSED | `installer/receipts.py:430-437`: the memo stores the observed digest and compares it with each receipt's digest. | `tests/test_receipts.py` `test_rehash_memo_compares_each_receipts_digest` |
| IN-02 (`ToolState.removable`/`.receipt` have no consumer) | OPEN (deferred to Phase 25) | `installer/version_status.py:709-710`. Still read only inside `version_status.py`. `app.py:564` reads a `RemovalPlan`, not the state. | none |
| IN-03 (pending presence reads absent in previews) | OPEN (deferred to Phase 25) | `installer/catalog_tui.py:489-492, 504-506` unchanged. G8 makes skill packs CHECKING more often, so they read absent there more often. | none |
| IN-04 (app receipt claims a smoke that never ran) | CLOSED | `installer/engine.py:246-257`: `smoked_artifact` is true for an app only with a `cli`, which matches the smoke at `apps.py:150-155`. Download kinds always smoke (`download.py:347, 356`). | `tests/test_engine.py` `test_app_receipt_records_smoke_only_with_a_cli[with-cli\|without-cli]` |
| IN-05 (e2e receipt check relies on errexit) | CLOSED | `scripts/container-e2e-verify.sh:480` `assert_receipt_present "$categories" \|\| return 1` | `tests/test_container_e2e_receipts.py` `test_receipt_checks_are_wired_into_the_passes` |
| IN-06 (zero-artifact manager receipts never retired; they block the layout fallback) | OPEN (deferred to Phase 25) | `installer/receipts.py:35` (`RECEIPTLESS_KINDS` unchanged) and `:330-331` (`all_gone` is False with no artifacts). `installer/uninstall.py:127-136` still skips the layout proof. | `tests/test_version_status.py:5145` `test_artifactless_receipt_is_never_retired` pins the open behavior on purpose |

## Cross-lane items disposition

Every claim below was re-checked against the current source. Items that
duplicate a 19-REVIEW.md item point to its row above.

### 19-REVIEW-opencode.md

| ID | Verdict | Evidence at HEAD | Pinned by |
|----|---------|------------------|-----------|
| F1 (a proven file becomes a recursive delete); same as P19-01 | CLOSED | `installer/uninstall.py:74-76` (`RemovalPlan.artifacts`), `:79-101` (`_receipt_proof` returns artifacts), `:405-423` (`remove_paths`: the authorized type picks the operation, `receipts.matches` re-checks right before the delete, only a `dir` reaches `rmtree`), `:442-451` (a path refused there is reported and its receipt is kept). | `tests/test_uninstall.py:2073` `test_remove_proven_refuses_a_file_replaced_by_a_dir_after_verification`, `test_remove_proven_refuses_a_dir_recreated_after_verification`, `test_remove_paths_unlinks_only_what_its_type_authorizes` |
| F2 (a publication during Status grouping duplicates a row); same as P19-02 | CLOSED | `installer/catalog_tui.py:107-113` (each health read once) and `:595-606` (one `_painted` snapshot per rebuild feeds grouping and cells, `:561-592`). | `tests/test_catalog_tui.py` `test_group_tools_reads_each_health_once`, `test_status_view_survives_a_publication_mid_rebuild` |
| F3 (stale skill-cache answers give a fresh green mark); same as P19-06 and ponytail #1 | CLOSED | `installer/version_status.py:1191-1209`: stale or missing answers are CHECKING. `:1210-1225`: a fresh all-unknown probe is MISSING. The G8 design opens a new stuck-CHECKING path when the cache write fails (WR2-03). | `tests/test_version_status.py:4951` `test_stale_cached_present_is_checking_not_ok`, `test_all_unknown_after_the_probe_is_missing_with_a_note`, `tests/test_catalog_tui.py` `test_skill_health_cell_is_missing_when_every_host_is_unknown` |
| F4 (a NUL receipt path escapes the fail-closed reader); same as P19-03 | CLOSED | `installer/receipts.py:469-476` (NUL and unencodable paths rejected), `:390` and `:438` (`ValueError` caught in `fingerprint`/`matches`), `:337` (`all_gone`). | `test_nul_artifact_path_is_unreadable`, `test_invalid_artifact_paths_fail_closed`, `test_nul_receipt_path_never_aborts_plan_removal`, `test_nul_receipt_path_never_aborts_refresh` |
| F5 (memo reuses proof for a different digest); same as P19-05, IN-01, ponytail #5 | CLOSED | see IN-01 | see IN-01 |
| F6 (the skill worker overwrites newer state) | CLOSED | `installer/version_status.py:1037-1054`: rebuilds only states whose `seq` equals the latest publishing pass, using that pass's scan, and no longer re-reads the home. Set at `:1651-1652`. | `test_skill_rebuild_never_rereads_project_facts`, `test_skill_rebuild_after_a_newer_pass_keeps_its_facts` |
| F7 (terminal warnings dropped); same as P19-08 | CLOSED | `installer/version_status.py:1323-1329`: each warning becomes a "terminal shell not checked" note on its row, an unknown prefix goes on every terminal row, and no step is offered. The prefixes match `terminal_shell.py:296, 463`. | `test_terminal_warning_is_a_not_checked_note`, `test_konsole_warning_lands_on_zsh`, `test_unknown_terminal_warning_lands_on_every_terminal_row` |
| F8 (a FIFO blocks the skill refresh) | CLOSED for the cited reads | `installer/atomic.py:118-147` (`read_capped`: O_NONBLOCK, fstat type and cap on the open descriptor), used at `installer/receipts.py:164`, `installer/skill_lifecycle.py:477-484` (hook configs) and `:826-835` (`installed_plugins.json`). The same blocking pattern remains in other reads that run in the pass (IN2-02). | `tests/test_atomic.py` `test_read_capped_never_blocks_on_a_fifo`, `tests/test_skill_lifecycle.py` `test_installed_plugins_fifo_never_blocks`, `test_hook_config_fifo_is_not_checked`, `tests/test_receipts.py` `test_receipt_read_never_blocks_on_a_fifo` |
| F9 (unquoted interpreter path in the receipt tests); same as P19-13 | CLOSED | `tests/test_container_e2e_receipts.py:224-226` (`_assign` uses `shlex.quote`), `:253`, `:299` | `test_uv_stub_survives_a_spaced_interpreter_path`, `test_assignment_survives_a_spaced_workspace` |

### 19-REVIEW-opencode-plan-review.md

| ID | Verdict | Evidence at HEAD | Pinned by |
|----|---------|------------------|-----------|
| P19-01 | CLOSED | = F1 | = F1 |
| P19-02 | CLOSED | = F2 | = F2 |
| P19-03 | CLOSED | = F4 | = F4 |
| P19-04 (`exists()` on an inaccessible receipts dir aborts refresh/uninstall) | CLOSED | `installer/receipts.py:307-321` (`receipt_exists`: only ENOENT/ENOTDIR count as absent, any other `lstat` failure counts as present but untrusted), used at `installer/uninstall.py:127`, `installer/version_status.py:1243` and `receipts.py:264, 292`. | `test_receipt_exists_treats_an_unreadable_dir_as_present`, `test_adopt_refuses_when_the_receipts_dir_is_unreadable`, `test_inaccessible_receipts_dir_never_aborts_plan_removal`, `test_inaccessible_receipts_dir_never_aborts_refresh` |
| P19-05 | CLOSED | = F5 / IN-01 | = IN-01 |
| P19-06 | CLOSED | = F3 | = F3 |
| P19-07 (one absent host overrides another host's unknown) | PARTIAL (accepted design) | `installer/version_status.py:1210-1225` and `:1116-1123`: mixed absent/unknown is still MISSING, now with a "no readable answer from <harness>" note. P19-07 asked for CHECKING until the absence is conclusive. That conflicts with ponytail #1 (CHECKING that never ends), so the team chose MISSING plus a note. The row still says "missing" for a pack that may be installed on the unreadable host. The docstring's claim that this agrees with `inspect_status` is wrong (IN2-04). | `test_mixed_absent_and_unknown_hosts_never_settle_absent` |
| P19-08 | CLOSED | = F7 | = F7 |
| P19-09 (several canonical user copies lose their duplicate reasons) | CLOSED | `installer/skill_lifecycle.py:877-901`: more than one canonical user entry gives `duplicate:` reasons, and both the install step and the enable step are suppressed. | `test_two_disabled_canonical_user_entries_get_no_enable_step` |
| P19-10 (an unreadable project install is classified as empty) | CLOSED | `installer/skill_lifecycle.py:431-448` (`_unreadable_install_dirs`) and `:569-588` (an unlistable dir is "not checked", gets no steps and no "not installed" reason). | `test_unreadable_install_dirs_are_not_checked_not_empty`, `test_conclusive_empty_install_keeps_its_reinstall_step` |
| P19-11 (repo walk follows a `.planning` symlink) | CLOSED | `installer/skill_lifecycle.py:392-394`: `.planning` itself must `lstat` as a directory. | `test_repo_walk_rejects_a_symlinked_planning_dir` |
| P19-12 (state-test helpers read the real HOME) | CLOSED | `tests/conftest.py:102-116`: an autouse per-test scratch `HOME`. No `getpwuid` or `USERPROFILE` home lookups exist in `installer/`. | `tests/test_locations.py` `test_suite_home_is_a_per_test_scratch_dir`, `test_registry_pass_reads_declared_locations_from_the_scratch_home` |
| P19-13 | CLOSED | = F9 | = F9 |

### 19-REVIEW-ponytail.md

| ID | Verdict | Evidence at HEAD | Pinned by |
|----|---------|------------------|-----------|
| #1 (a pack whose hosts never answer is CHECKING forever) | CLOSED (see WR2-03 for a new path to the same symptom) | = F3. A fresh all-unknown probe is MISSING (`version_status.py:1210-1225`). | `test_inconclusive_claude_listing_is_a_not_checked_note` now asserts `Health.MISSING` |
| #2 (a receipt whose files are all gone marks a tool broken forever) | CLOSED | `installer/receipts.py:324-358` (`all_gone`, `retire` with a re-read under the write lock), `installer/version_status.py:1249-1250`. Partial drift stays BROKEN by design. WR2-02 shows a partial-drift case that is not a real defect but still has no way out. | `tests/test_version_status.py:5104` `test_receipt_with_every_artifact_gone_is_retired`, `test_partially_drifted_receipt_stays_broken`, `tests/test_receipts.py` `test_all_gone_needs_every_artifact_gone`, `test_retire_refuses_a_replaced_receipt` |
| #3 (every tab switch re-probes the catalog) | NOT-A-DEFECT (accepted as G15; performance is out of this review's scope) | `installer/catalog_tui.py:416-418` unchanged by design (D-02 single flight, STATE-01). | n/a |
| #4 (`inspect_skill_packs` has no production caller) | CLOSED | Deleted. `inspect_status` reads `inspect_skill_reports(...)[id].hosts` (`installer/skill_lifecycle.py:982-984`). | `test_skill_hosts_are_idempotent` (helper `_hosts`) |
| #5 (memo digest) | CLOSED | = IN-01 | = IN-01 |
| #6 (`tool_health` compares tuples by identity) | CLOSED | `installer/version_status.py:234-238` compares the `Health`. | `tests/test_tool_health.py` `test_reasons_follow_precedence_when_groups_share_a_tuple` |
| #7 (the reader keeps fields no type uses) | CLOSED | `installer/receipts.py:480-498` (per-type construction; `_artifact_str` deleted) | `test_reader_keeps_only_each_types_fields` |

Counting rule for the frontmatter `prior_*` keys: the six 19-REVIEW CR/WR
items plus the 15 distinct cross-lane HIGH/MEDIUM items left after dedupe (F1,
F2, F3, F4, F5, F6, F7, F8, P19-04, P19-07, P19-09, P19-10, P19-11, P19-12,
ponytail #2). Closed 18. Partial 2 (WR-02, P19-07). Open 1 (WR-03).

## New defects introduced by the fixes

The new findings below use fresh ids (CR2-/WR2-/IN2-). Only these are counted
in the frontmatter `findings` block.

## Critical Issues

### CR2-01: Directory receipts compare `st_dev`, which can change after a reboot or remount, so every archive tool can turn BROKEN, refuse updates and stop being removable

**File:** `installer/receipts.py:385-389` (fingerprint), `:411-416` (matches), `:494-498` (reader requires `dev`). Consumers: `installer/version_status.py:1251-1252`, `installer/update.py:509-521`, `installer/uninstall.py:92-94, 127-136`.

**Issue:** G2 makes a `dir` artifact match only while
`(st_dev, st_ino)` equals what install recorded. The receipt persists across
boots, but `st_dev` is not stored on disk. On btrfs subvolumes, NFS (and
autofs), ZFS and overlayfs it is an anonymous device number that the kernel
assigns when the filesystem is mounted. On this developer's Bazzite host
(checked with read-only `stat` and `/proc/self/mountinfo`), the btrfs
superblock is `0:35`. Files report a per-subvolume number instead: `/sysroot`
is 37, `/var` is 58 and `/var/home` is 59. The tmpfs `/tmp` got 57 and
`binfmt_misc` got 60. So the home subvolume's number was handed out between
two other boot-time mounts, in systemd's parallel mount phase. A different
mount order on the next boot gives `/var/home` a different number, and then no
recorded `dev` matches.

**Scenario:** A Fedora or Bazzite user (btrfs is the default) installs rg, fd,
bat and the other ~40 archive tools. Each receipt holds the
`~/.local/opt/<name>` dir plus the bin link. They reboot, and `/var/home` comes
up as `0:58`. On the next pass:

- Every archive receipt drifts, and every row shows
  `! broken — changed since install`.
- `u` is refused (`catalog_tui.py:800-803`), and the execute screen's update
  is refused by the new gate ("rg is broken: changed since install").
- `--uninstall` / `make uninstall` proves nothing, because `_receipt_proof`
  returns `()`. L-19-14 forbids the layout fallback while a receipt exists. So
  `~/.local/opt/*` and the links all land in "remove it yourself". Before this
  phase, the layout proof removed them.
- The receipts never retire, because the files still exist. Nothing in the
  installer clears the state.

An autofs NFS home behaves the same way after each remount. The e2e probe tool
is `yq`, a raw file with no dir artifact, and the run uses one container
lifetime, so the e2e cannot see this.

Not done: an actual reboot (the host must not be mutated). To confirm on the
dev machine, compare `stat -c %d ~/.local/opt/<x>` before and after a reboot.

**Fix:** Compare the inode only. The path is fixed, so `dev` adds only
protection against another filesystem with the same inode number, which is
negligible. It does not help against inode reuse (IN2-01).
```python
# receipts.matches
if artifact.type == "dir":
    st = path.lstat()
    return stat_module.S_ISDIR(st.st_mode) and st.st_ino == artifact.ino
```
In `fingerprint` and `_read_artifact`, require only `ino`. `dev` can stay as a
written field that is never compared. Add a test that patches `lstat` to
return a different `st_dev` with the same `st_ino` and asserts
`matches(...) is True`.

## Warnings

### WR2-01: The G13 shim fix makes a real pnpm behind the installer's pnpm redirect shim read as not installed

**File:** `installer/status.py:121-128`

**Issue:** The PATH branch now skips this installer's shim but never looks
behind it, and `shutil.which` returns only the first PATH hit. The pnpm
redirect shim (`GLOBAL_REDIRECTED["pnpm"]`, pass-through) is only generated
when a real pnpm exists elsewhere on PATH: `guards.redirect_shim_script`
raises without `passthrough_path`. So on any machine that has this shim, the
real pnpm is further down PATH by construction. The checks after the PATH
branch only look at the script `bin_dir` (`~/.local/share/pnpm/bin`,
`~/Library/pnpm/bin`). A brew (`/opt/homebrew/bin/pnpm`), Volta or corepack
pnpm is never found. The TUI is not affected only because the service passes
`_looked_through`.

**Reproduced** (scratch HOME): shim at `<home>/.local/bin/pnpm`, a real
executable at `<home>/brew/bin/pnpm`, `PATH=<shim dir>:<brew dir>`.
`guards.real_binary` finds the brew pnpm, but `is_installed(pnpm)` returns
`False`.

**Scenario:** On macOS, the user ran `brew install pnpm` and enabled the
Policies "global adds redirected to volta" redirect. They then run
`make setup ARGS="--categories ... --yes"`. That headless route uses
`installed=is_installed` and `install_tool` with `present=None` (`app.py:138-139`,
`engine.py:191`). pnpm reads absent and is pulled in for mmdc, puppeteer, pi or
openspec. The engine then runs the rank-10 `script` method
(`get.pnpm.io/install.sh`), which installs a second pnpm into `~/Library/pnpm`
and runs that script's own shell rc edits. The new test
(`tests/test_status.py:784`) covers only the shim-alone case.

**Fix:** Look through the shim on the default lookup, the same way the service does:
```python
lookup: Which = shutil.which if which is None else which
resolved = lookup(tool.cmd)
if resolved is not None and _is_installer_shim(tool, Path(resolved)):
    resolved = (
        installer.guards.real_binary(
            tool.cmd, shim_dir=Path(resolved).parent, path_value=os.environ.get("PATH", "")
        )
        if which is None
        else None
    )
if resolved is not None and macos_stub_reason(...) is None:
    return True
```
Add a test with the shim first on PATH and a real pnpm later on PATH that
expects `True`.

### WR2-02: A macOS app that updates itself turns BROKEN for good, and every installer action on it is refused

**File:** `installer/receipts.py:411-416` (G2), `installer/update.py:509-521` (G3), `installer/version_status.py:1249-1252, 1585-1592`, `installer/uninstall.py:92-94`

**Issue:** An app receipt holds the bundle dir (now matched by inode) and the
CLI link. The registry's macOS app methods are VS Code, Sublime Text and
draw.io. These apps update themselves by moving a new bundle into the same
path. `19-22-PLAN.md:78` accepts that such an update "reads as changed since
install". It does not consider what happens after that:

- The row shows `! broken — changed since install`.
- `u` refuses a BROKEN row (`catalog_tui.py:800-803`).
- The execute screen's update is refused by the new gate.
- Install stops at ALREADY_INSTALLED, because BROKEN counts as present.
- Uninstall proves nothing, so the bundle and the link go to "remove it
  yourself".
- `retire` never runs, because the files exist.
- The detail bar adds "not proven: reinstall with r to adopt", and in the
  catalog `r` stages recommended tools instead (WR-03).

Before G2, a directory matched as long as it existed, so a vendor update did
not count as drift.

**Scenario:** The user installs VS Code on macOS through the installer.
VS Code's default auto-update replaces the bundle in `~/Applications` at the
next monthly release. From then on, a working editor shows as broken, and the
installer can neither update it nor remove it.

**Fix:** Keep the inode check as the proof for removal. Do not turn "a dir
whose identity changed, is still a real dir, and every link artifact still
matches" into a BROKEN fact. In `_receipt_evidence`, report it as a note, for
example "replaced outside the installer — not removable by receipt", and take
the health from current evidence. The update gate can keep refusing, because
it stops the pinned URL from overwriting a newer vendor build. Phase 20 needs
a re-adopt path for this state.

### WR2-03: When writing the skill cache fails, every probed skill pack stays CHECKING for the session (G8 regression)

**File:** `installer/version_status.py:1026-1036` (the write runs before
publication, with no `try`), `:1194-1209` (since G8, a stale answer means
CHECKING), `installer/catalog_tui.py:427-435` (the worker discards the error)

**Issue:** `refresh_skills` calls `save_version_cache` under the lock *before*
it assigns `_skills` and `_skills_probed` and rebuilds the pack states. If the
write raises an `OSError` (disk full, or `~/.local/state/tools-installer` not
writable), nothing is published and `_skills_probed` stays False. The catalog
worker drops the error silently. Before G8, the stale answers seeded from the
cache still decided presence and showed the "previous run" note. Now a stale
answer is CHECKING by design. So the pack stays on "… checking which hosts
have it", and `u` answers "try again in a moment" forever. The version pass
handles the same failure gracefully: it publishes the states and shows a
warning (`version_status.py:1659-1666`, `catalog_tui.py:460-463`).

**Reproduced** with the module's own doubles (`_pack_service`, `_superpowers`,
a Claude listing with one enabled user entry):

1. After the pass: `checking`.
2. `refresh_skills` with the write raising ENOSPC raises, and the state is
   still `checking`.
3. Another pass plus probe: still `checking`.
4. With a writable cache: `ok`.

A related bug (it existed before these fixes, same root cause): `invalidate`
(`:1062-1070`) bumps the epoch, then writes the cache, then resets
`_skills_probed` and marks the answers stale. A failed write skips the reset,
so the next probe is skipped and answers from before the mutation are
published as fresh. Reproduced: the plugin was removed, `invalidate` raised
ENOSPC, and the next pass plus probe still showed `ok` with fresh hosts.

**Fix:** Make the write best-effort, the same way `_pass` does:
```python
merged = {**self._skills, **fresh}
try:
    save_version_cache(self._cache_path, load_version_cache(self._cache_path),
                       skills={k: dict(v.hosts) for k, v in merged.items()})
except OSError as exc:
    self._warning = f"version cache not saved: {exc}"
self._skills = merged
self._skills_probed = True
```
In `invalidate`, reset `_skills_probed` and mark the answers stale before the
write (or in a `finally`). Add a test where the write raises and the pack
state is settled after `refresh_skills`.

## Info

### IN2-01: The directory-identity guarantee ("never inherits") does not hold on filesystems that reuse inode numbers

**File:** `installer/receipts.py:5-9, 365-367`; `tests/test_uninstall.py:2136-2146`, `tests/test_receipts.py:738-752`
**Issue:** The docstrings say a re-created directory "never" matches. ext4
and XFS hand a freed inode number to the next new inode, so
`rm -rf ~/.local/opt/rg` followed by extracting a hand-installed copy there
can get the same number back. The tests avoid exactly this case:
`_recreate_over` keeps both directories alive "so the replacement gets a new
inode even on a filesystem that recycles the one just freed". The impact is
low: only `~/.local/opt` on Linux is affected, and APFS (`~/Applications`)
does not reuse inode numbers.
**Fix:** Reword the docstrings to state the limit, with a
`shortcut: inode reuse on ext4/XFS, upgrade if user-namespace dirs join the
receipt set` comment. Or add `st_birthtime` where the platform has it.

### IN2-02: Reads that a FIFO can block (the F8 pattern) remain in the refresh pass

**File:** `installer/terminal_shell.py:248-263` (`_read_text`: `exists()` then
`read_bytes()`, reached from the pass through `_terminal_facts` ->
`sync_terminal_shells(write=False)`), `installer/skill_lifecycle.py:712-719`
(`_skills_lock_skills`, under `_skills_pass_lock`), `installer/guards.py:279-287`
(`is_our_shim`, now also called from `status.py:125` on every PATH hit for a
guarded name)
**Issue:** A FIFO (a named pipe) at `~/.config/kitty/kitty.conf` blocks the
version pass. Every later `refresh` at the same epoch joins that pass and
waits on `done.wait()`, which has no timeout. The trigger is contrived. Still,
19-28's statement that "one helper owns every capped config read" covers less
than it seems to.
**Fix:** Send these reads through `atomic.read_capped`.

### IN2-03: The execute screen still lists a drifted tool as an update the gate will refuse

**File:** `installer/execute_screen.py:564-577`; `tests/test_execute_screen.py:4435`
**Issue:** `_update_targets` still queues a BROKEN "changed since install"
tool. The preview shows `○ drifted update [pending]` (now pinned by
`test_classify_reads_the_state`). At run time the gate refuses it with status
`unsupported`, shown as `✖ … update [not done]`. The preview promises work
that will not happen.
**Fix:** In `_update_targets`, skip `state.health is Health.BROKEN` and list
the tool as broken. Keep the gate as the backstop.

### IN2-04: The `_skill_state` docstring claims it agrees with `inspect_status`, but it does not

**File:** `installer/version_status.py:1145-1147` vs `installer/skill_lifecycle.py:985-991`
**Issue:** For `{claude: unknown, codex: absent}` the state is MISSING, while
`inspect_status` answers `unknown`.
**Fix:** Reword the docstring. The current code behavior is the accepted
design.

---

_Reviewed: 2026-10-16T22:47:19Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
