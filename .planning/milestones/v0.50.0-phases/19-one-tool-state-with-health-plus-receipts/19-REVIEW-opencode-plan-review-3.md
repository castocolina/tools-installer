# Phase 19 re-review round 3 (opencode, router-env/my-plan-review)

## Closure of prior findings

Reviewed `8cea513..23d832e` over `installer`, `setup.py`, `scripts` and `tests`, including `24d91d6`. L-19-31 is treated as binding: identical key-file bytes may prove a recreated directory; directory-only drift does not imply BROKEN or update refusal.

| Finding id | Status (closed/partial/open) | Evidence file:line |
|---|---|---|
| **H1 — CR2-01, IN2-01, WR2-02, ponytail #1: unstable directory identity and vendor-update dead end** | **closed** | Directory artifacts now record a key-file digest rather than device/inode identity: `installer/receipts.py:438–452`, `491–494`. Directory-only drift produces an unproven note, not BROKEN: `installer/version_status.py:1270–1275`; the update gate ignores directory-only drift: `installer/update.py:511–518`. A separate key-containment defect is RR3-01 below. |
| **H2 — RR-01: replacement directory deleted after the final check** | **closed** | The directory is renamed to quarantine, rehashed there, and restored on mismatch before recursive deletion: `installer/uninstall.py:439–459`. Deterministic replacement and restoration-failure coverage: `tests/test_uninstall.py:2373–2414`. Cancellation recovery is a separate regression, RR3-02. |
| **H3 — RR-02: changed raw bytes accepted through restored metadata** | **closed** | The final per-artifact check uses `rehash=True`: `installer/uninstall.py:475–483`, bypassing the metadata shortcut at `installer/receipts.py:514–517`. Regression coverage substitutes same-length bytes and restores mtime after planning: `tests/test_uninstall.py:2048–2072`. |
| **M1 — RR-03: partial passes strand successfully probed packs in CHECKING** | **closed** | Publication retains each pack’s sequence and scan: `installer/version_status.py:1674–1677`; the skill rebuild uses that pack’s entry: `1042–1057`. Full-then-partial-pass regression: `tests/test_version_status.py:4801–4818`. |
| **M2 — RR-04: ambiguous Claude duplicates regain a partial install step** | **closed** | D-18 reasons exclude Claude from downstream partial-install targets: `installer/version_status.py:1115–1126`. Duplicate Claude plus present Codex coverage verifies no recreated install step: `tests/test_version_status.py:4779–4798`. |
| **M3 — WR2-03: failed skill-cache writes strand state; failed invalidation skips reprobe** | **partial** | Fresh answers publish despite save failure: `installer/version_status.py:1030–1060`. Invalidation resets probing and marks held answers stale before persistence: `1071–1078`. Both original state failures are closed, but the promised warning can disappear while those answers remain unsaved; see RR3-03. |
| **M4 — WR2-01: real pnpm behind the managed shim reads absent** | **closed** | Default presence lookup now uses `look_through_shim`: `installer/status.py:125–140`. Regression covers a real pnpm behind the shim, then its removal: `tests/test_status.py:817–837`. |
| **M5 — RR-05: inherited manager directories escape scratch HOME** | **closed** | The autouse fixture clears `PNPM_HOME`, `VOLTA_HOME`, `XDG_CONFIG_HOME` and `XDG_DATA_HOME`: `tests/conftest.py:114–117`; HOME remains per-test scratch: `132–134`. Override and owner-prefix coverage: `tests/test_locations.py:56–68`. |
| **M6 — IN2-02: remaining blocking configuration reads** | **closed** | Shim, terminal configuration and skill-lock reads use the nonblocking capped reader: `installer/guards.py:285–295`, `installer/terminal_shell.py:264–275`, `installer/skill_lifecycle.py:716–728`. The reader checks the opened descriptor and bounds the read: `installer/atomic.py:128–147`. |
| **M7 — IN2-03: execute preview promises an update the gate refuses** | **closed** | BROKEN selections enter `_refused`, with empty reasons guarded, and are excluded from updates and reapplication: `installer/execute_screen.py:549–573`. Their progress rows render as not done from the outset: `1146–1151`. |

## New findings

### RR3-01 [HIGH] An intermediate symlink lets an external key authorize deletion of a replacement directory

- **File:** `installer/receipts.py:438–443`, `491–494`, `505–515`; `installer/uninstall.py:452–456`.
- **Problem:** Only the directory root and the final key component are type-checked. `lstat(Demo.app/Contents/Info.plist)` follows a symlink at the intermediate `Contents` component. After recording a normal app, move it to `Demo.backup.app`, create a replacement `Demo.app` with `Contents` pointing to the backup’s absolute `Contents` path, and put unrelated data in the replacement. Leave the CLI link’s target string unchanged. Both the ordinary check and the quarantine recheck hash the backup’s original plist and approve recursive deletion of the replacement’s unrelated data. No forged receipt or precisely timed swap is required. This is not L-19-31’s accepted identical-key case: the matching key is outside the directory being deleted.
- **Fix:** Enforce key-file containment within the current artifact root during both fingerprinting and matching, including the quarantine recheck. Refuse escaping intermediate symlinks while retaining the final-component symlink refusal. Add a regression using an absolute intermediate symlink, so the escape remains observable after quarantine renaming.

### RR3-02 [MEDIUM] Ctrl+C can strand an intact installation under an undisclosed quarantine name

- **File:** `installer/uninstall.py:447–459`; `setup.py:1567–1573`.
- **Problem:** After capture succeeds, restoration handles a mismatching proof and `OSError` from deletion, but not `KeyboardInterrupt` during verification or `rmtree`. Pressing Ctrl+C after the rename and before deletion leaves the complete installation at `.Demo.app.<random>.tools-installer.rm`, with its original path absent. The CLI catches the interruption and prints only `Aborted.`, without identifying the retained directory. Normal artifact discovery checks registry-derived paths, not random quarantine siblings: `installer/uninstall.py:50–53`. An in-memory interruption check confirmed one capture rename and no restoration rename.
- **Fix:** Protect the post-capture verification/deletion section so catchable cancellation restores the remaining tree before propagating. If restoration fails, preserve and report the quarantine path. Add cancellation coverage immediately after capture and at deletion entry; recovery from SIGKILL need not be promised.

### RR3-03 [LOW] A later version save erases the warning without saving fresh skill answers

- **File:** `installer/version_status.py:1030–1041`, `1684–1691`; `installer/version_cache.py:228–232`; `installer/catalog_tui.py:470–474`.
- **Problem:** The version and skill workers start concurrently in separate groups: `installer/catalog_tui.py:409–412`, `431`. If the skill worker finishes first and its save fails, it publishes fresh answers and sets the warning. A slower version pass can then save successfully **without `skills=`**. That preserves the old on-disk skill answers, yet clears `_warning`; its completion message also clears the displayed warning. Current-session health remains correct, but the persistence failure becomes invisible. The new UI regression deliberately forces the opposite completion order: `tests/test_catalog_tui.py:4384–4386`.
- **Fix:** Clear a skill-save failure only after the fresh skill answers have actually been persisted—either include them in the later successful save or retain the warning separately. Cover skill-first/version-last completion with a failed skill save followed by a successful version-only save.

## Summary

| Severity | New findings |
|---|---:|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 1 |
| **Total** | **3** |

The original removal windows are closed under L-19-31, but key containment still permits deletion of an unproven replacement tree. Quarantine interruption recovery also needs correction before shipping.

No additional grounded TUI-crash regression was found. The scoped diff adds **zero suppression directives** and removes one. Commit `24d91d6` stubs the default Puppeteer launch seam while restoring explicitly mocked probe tests: `tests/conftest.py:232–244`.

One pre-existing host dependency remains in the reused shell-test harness: the new spaced-workspace test runs the extracted command locally (`tests/test_container_e2e_receipts.py:374–380`), including absolute host `brew shellenv` (`scripts/container-e2e-verify.sh:318`). The older test already does this; no host mutation or new failure was established, so it is not counted above.

Verification: scoped `git diff --check`, parsing all 28 changed Python files without imports, Bash syntax validation, and in-memory removal checks completed successfully.  
Not checked: pytest, full quality gates, containers or live macOS behavior. No files were edited or installs run; runtime safety is not established by this review.
