---
phase: 30-onboard-ghostty
reviewed: 2026-11-20T00:00:00Z
depth: deep
files_reviewed: 30
files_reviewed_list:
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/appimage_menu.py
  - installer/desktop_entry.py
  - installer/download.py
  - installer/engine.py
  - installer/executors.py
  - installer/model.py
  - installer/registry.toml
  - installer/terminal_keys.py
  - installer/terminal_regions.py
  - installer/terminal_shell.py
  - installer/uninstall.py
  - installer/version_status.py
  - scripts/container-e2e-verify.sh
  - tests/e2e_ghostty_driver.py
  - tests/test_appimage_menu.py
  - tests/test_container_e2e_ghostty.py
  - tests/test_desktop_entry.py
  - tests/test_download.py
  - tests/test_engine.py
  - tests/test_executors.py
  - tests/test_ghostty_catalog.py
  - tests/test_model.py
  - tests/test_registry.py
  - tests/test_resolve.py
  - tests/test_shell_scripts_path.py
  - tests/test_terminal_keys.py
  - tests/test_terminal_shell.py
  - tests/test_tool_onboarding_skill.py
  - tests/test_version_status.py
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
  necessity: 0
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-11-20
**Depth:** deep
**Files Reviewed:** 30
**Status:** issues_found

## Summary

Phase 30 adds the Ghostty catalog entry, a raw-tarball AppImage install with a menu entry and icon
(`installer/appimage_menu.py`), the Ghostty shell and keys regions, a resolver and conflict scan
over every default file, and a container target. I found no data-loss or security defect. The
adversarial passes below came back clean:

- Menu entry and icon replacement and rollback (`appimage_menu.install`): ownership is the previous
  receipt's leaves only, backups are taken before any write, a symlink swap is refused, and undo runs
  in reverse order. I read it end to end and its tests; I found nothing that loses a user file.
- Created-file deletion: bound to the recorded path in `_drop_created_config`. I reproduced the
  resolver-move case (a legacy `config` appears) and the file is left alone.
- Owned-region replace and strip across default files: reproduced with scratch homes (shell sync,
  keys apply, a user `command` in the legacy file, strip). User bytes survive.
- Loader checks (`raw`+`archive`, `note`, `desktop`): the real registry loads (87 tools) and no other
  entry combines `raw` with `archive`. The pinned digests and asset names match the live GitHub
  release (checked against the public release API).
- Extraction: the pattern cannot hold a glob character (the `desktop` regex), the read goes through
  `staged_member` and `read_capped` with a 1 MiB cap, and `TMPDIR` is the work dir that `finally` removes.
- Shell script: container and image removal use the exact name, there is no prune, and the
  `label=disable` option already has a precedent in the nested-podman target.
- Pure verdicts: positive FUSE evidence needs the device, a printed mount point found as a `fuse`
  entry in mountinfo, no fallback text and exit 0.

The three warnings are a receipt behavior the new leaves make reachable, an API-contract hole in the
Ghostty keys plan, and a residue check that cannot see the thing the registry says it proved.

Python 3.12 versus 3.15: nothing new depends on behavior that differs (`Path.is_file` is wrapped in
a `try` that catches `OSError`, so the 3.14 `os.path.isfile` change cannot matter).

## Warnings

### WR-01: Deleting the menu entry or icon makes the tool BROKEN and unremovable

**File:** `installer/download.py:313-322` (leaves), `installer/receipts.py:968-987`, `installer/uninstall.py:165-200`, `installer/update.py:664-675`
**Issue:** The two menu files are receipt `leaf` artifacts. `receipts.matches` is False for a missing
leaf (`lstat` raises, which maps to False), so `drifted` and `broken_drift` both report the receipt,
and `_receipt_proof` returns nothing when any artifact drifted. A menu entry is the one artifact
users really do delete (a desktop cleanup, "hide from menu", a stray `rm`). Reproduced in a scratch
home with the real `engine.install_tool` and the real `ghostty` entry:

```
install ghostty (stub runner)  -> INSTALLED, 3 receipt artifacts
rm ~/.local/share/applications/com.mitchellh.ghostty.desktop
receipts.broken_drift(receipt)         -> ['com.mitchellh.ghostty.desktop']
uninstall.removal_plan(..., verify=True) -> removable=(), level=none
~/.local/bin/ghostty still exists
```

Consequences: the status pass reads the tool as "changed since install", `UpdateService.run`
refuses the update (`status="unsupported"`), and uninstall proves nothing, so the 49 MB AppImage and
its receipt are stranded until a reinstall. Before this phase no tool's removable artifacts were
files a user deletes casually (cargo_distrobox leaves have the same shape but are not user-facing).
**Fix:** A leaf that no longer exists has nothing to delete, so it must not void the proof of the
other artifacts. In `receipts.drifted` and `receipts.broken_drift`, skip a `leaf` whose path is gone
(`not os.path.lexists(a.path)`); keep a leaf that exists but is the wrong type as drift. Add a test
next to `test_removal_covers_the_binary_and_both_leaves`: delete the desktop file, then assert
`removal_plan(...).removable == (binary, icon)` and `broken_drift(receipt) == ()`.

### WR-02: `_ghostty_plan` scans the process HOME and environment, not the `home` and `environ` it is called with

**File:** `installer/terminal_keys.py:209-211`
**Issue:** `KeysRow.plan` receives only `(platform_os, text, path)`, so `_ghostty_plan` calls
`scan_ghostty(platform_os, Path.home(), os.environ)` while `apply_terminal_keys`,
`terminal_keys_pending` and `strip_terminal_keys` resolve the config file from the `home` and
`environ` their callers pass. The `shortcut:` comment admits the limit, but it breaks the public
signature: the keys row reads and decides on one tree and writes another. Reproduced:

```
HOME = B, with B/.config/ghostty/config = "keybind = ctrl+shift+k=reset"
apply_terminal_keys(row, "ghostty", "linux", home=A, environ={}, skip_recorded=False)
  -> (('ghostty: partial: you already bind ctrl+shift+k',), None)   # A is clean
A/.config/ghostty/config.ghostty -> not written
```

Production passes `Path.home()` and `os.environ` everywhere, so users do not hit it today. Any test
or future caller that passes an explicit home (the shell sync `_sync_ghostty` already does) gets
silent wrong answers, and the scan reads the developer's real `~/.config/ghostty` during such a
test, which breaks the "tests use a scratch HOME" rule.
**Fix:** Thread the two values through, as the shortcut comment says. The smallest change is to give
`KeysRow.plan` a fourth `home`/`environ` pair, or to close over them in `apply_terminal_keys` and
`terminal_keys_pending` with `functools.partial` before `_render`. Add a test that calls
`apply_terminal_keys` with a home that differs from `Path.home()` and a conflict only in the other tree.

### WR-03: The residue diff skips directories, so "uninstall removed everything it placed" is not proven

**File:** `tests/e2e_ghostty_driver.py:300-312`, `tests/test_container_e2e_ghostty.py:test_home_listing_skips_empty_dirs_and_the_workspace`, `installer/registry.toml:3201-3205`
**Issue:** `home_listing` returns files and symlinks only, and a test pins that empty directories are
skipped. The residue diff, `remove_verdict`'s "still present" list and the leftover check therefore
cannot see an empty directory left behind. Install creates directories (`~/.local/share/applications`,
`~/.local/share/icons/hicolor/256x256/apps`, `~/.config/ghostty`) and uninstall removes them through
`_prune_empty_parents` and `remove_created_dirs`, which is exactly the code D-16 asks to prove. The
registry comment states "Uninstall removed everything it placed; the residue diff held only
allowlisted paths", which the check cannot support for directories. The `/tmp` check has the same
blind spot for `appimage_extracted_*` (it only matches `tools-installer-`), though every AppImage run
in the driver sets `TMPDIR` to a scratch directory, so that part is moot today.
**Fix:** List directories too (`os.walk` entries for `dirs`, minus the workspace) in `home_listing`
and treat a directory present after uninstall and absent before as residue. Seed the pre-install
home so `.config/ghostty` is a before-directory (the driver already seeds it) and expect the two menu
directories to disappear. Soften the registry comment until the check covers directories.

## Info

### IN-01: `test_ghostty_installs_on_linux_x86_64_through_the_engine` passes because the menu step fails

**File:** `tests/test_engine.py:32-61`
**Issue:** The test uses `fixture_runner`, which ignores the `--appimage-extract` argv, so the menu
step fails with "cannot read extracted ..." and the receipt holds one artifact. The test asserts
`len(receipt.artifacts) == 1`, which encodes the failure; the real result is three artifacts
(`test_the_engine_places_the_menu_entry_and_records_three_receipt_paths`). The assertion would fail
the day the stub learns to extract, and it passes while the menu step is broken.
**Fix:** Assert only the binary artifact (`receipt.artifacts[0]`) and the community-build note, or
reuse `InstallRunner` from `tests/test_appimage_menu.py` and assert three artifacts.

### IN-02: A reinstall overwrites a menu entry the user edited, with no note

**File:** `installer/appimage_menu.py:41-50`
**Issue:** `proven` is every `leaf` path in the previous receipt, whether or not the file still
holds the bytes the installer wrote. A leaf matches "by type alone" (`receipts._leaf_matches`
shortcut), so a user's edit to `~/.local/share/applications/com.mitchellh.ghostty.desktop` (KDE's
menu editor writes the file in place) is replaced on the next install without a word. The data lost
is one desktop file the installer owns, so this is Info, but the existing "kept your existing" note
shows the intent to be careful.
**Fix:** Record a content hash for the two leaves, or compare against the bytes the previous install
wrote; until then say "replaced your menu entry" in the notes when the bytes differ from a fresh render.

### IN-03: Cleanup errors outside `Failed`/`OSError`/`ValueError` leave no verdict line

**File:** `tests/e2e_ghostty_driver.py:88-93`, `tests/e2e_ghostty_driver.py:516-522`
**Issue:** `uninstall_one` can raise `CommandError` (a `RuntimeError`). `run_lifecycle`'s `finally`
catches only `Failed`, `OSError` and `ValueError`, and `main` catches the same three, so a failed
uninstall ends as a traceback with exit 1 and no `TRACER_GHOSTTY_REMOVE_FAILED` line. The shell step
still fails on the exit code, so nothing passes silently, but the transcript the phase gate reads then
lacks the named verdict. `test_run_lifecycle_cleans_up_when_a_step_raises_something_unexpected` pins the propagation.
**Fix:** Catch `(OSError, ValueError, RuntimeError)` in the cleanup handler and emit the REMOVE_FAILED line.

### IN-04: Test and comment names that mislead

**File:** `tests/test_container_e2e_ghostty.py:343`, `tests/test_ghostty_catalog.py:29`, `installer/engine.py:139-143`
**Issue:** `testrun_ghostty_does_not_wait_for_a_helper_that_keeps_the_output_open` has no underscore
after `test` (pytest still collects it, since the default prefix is `test`, but it reads as a typo and
a prefix change would silently drop it). `test_both_ghostty_appimage_methods_are_pinned_github_release_methods`
tests two `tarball` methods; `github_release` takes no pins, which is the reason the phase uses `tarball`.
The `_perform` docstring now has an orphan line ("A source build is" at `engine.py:143`) from a reflow.
**Fix:** Rename to `test_run_ghostty_...` and `test_both_ghostty_appimage_methods_are_pinned_tarball_methods`; reflow the docstring.

### IN-05: The registry cites evidence that is not in the repository

**File:** `installer/registry.toml:3206`
**Issue:** The `# Verified` block ends with "Transcript: .e2e-artifacts/container-ghostty/ghostty-transcript.log".
`.e2e-artifacts` is git-ignored, so another clone, CI or a later audit cannot open it. The transcript
I read shows `TRACER_GHOSTTY_FUSE_UNPROVEN` in the FUSE pass (accepted) and OK verdicts for the extract pass.
**Fix:** Keep the verdict lines in the phase directory (for example in `30-06-SUMMARY.md`) and cite
that path, or say the transcript is local evidence.

---

_Reviewed: 2026-11-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
