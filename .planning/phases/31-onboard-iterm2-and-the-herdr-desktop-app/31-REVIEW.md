---
phase: 31-onboard-iterm2-and-the-herdr-desktop-app
reviewed: 2026-11-21T00:00:00Z
depth: deep
files_reviewed: 25
files_reviewed_list:
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/app.py
  - installer/herdr_app_keys.py
  - installer/iterm2_profile.py
  - installer/registry.toml
  - installer/terminal_keys.py
  - installer/terminal_regions.py
  - installer/vendor_defaults/herdr-app-0.1.16/keys.json
  - installer/vendor_defaults/herdr-app-0.1.16/keys.macos.json
  - scripts/container-e2e-verify.sh
  - tests/conftest.py
  - tests/e2e_herdr_app_driver.py
  - tests/test_container_e2e_herdr_app.py
  - tests/test_herdr_app_keys.py
  - tests/test_herdr_app_row.py
  - tests/test_iterm2_profile.py
  - tests/test_iterm2_row.py
  - tests/test_registry.py
  - tests/test_resolve.py
  - tests/test_shell_scripts_path.py
  - tests/test_terminal_json_catalog.py
  - tests/test_terminal_keys.py
  - tests/test_terminal_ownership.py
  - tests/test_tool_onboarding_skill.py
  - tests/test_version_status.py
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-11-21
**Depth:** deep
**Files Reviewed:** 25
**Status:** issues_found

## Summary

I reviewed the phase 31 diff (`b78e2062..HEAD`) against 31-CONTEXT (D-01..D-20 and the 2026-11-21
amendments), the plans, and the four review cycles. I did not reopen the decisions and accepted
limits listed in the brief. I did not find a defect that loses or corrupts user data, so there are
no critical findings. I found four warnings and two info items. I reproduced each warning in a
scratch home with the real rows or the real hook functions, and I ran no `defaults`, podman or
host-mutating command.

The following held up under adversarial reading:

- **iTerm2 whole-file apply and the default-profile hook:** capture, switch only while the
  preference equals the recorded previous default, retry, and the restore before the cask removal.
  The `_capture_failed` guard, the `switched=False` write, and the unconfirmed-restore refusal on
  both the CLI and TUI routes all work as specified.
- **Awk filter in `scripts/container-e2e-verify.sh`:** I ran the extracted program against the real
  `installer/registry.toml`. It removes exactly the `herdr-app` block plus its own preceding
  comments, and the file still parses to 88 tools. For every one of the 89 ids as `skip`, the
  remaining ids are exactly the others. Failure propagates through `rc` and `|| return 1`.
- **Transcript digest gate:** `.e2e-artifacts/container-herdr-app/herdr-app-transcript.log` hashes
  to `34591570ed07`, as the summary claims.
- **Chord grammar:** I probed `parse_chord` with 26 edge spellings. The results match the D-16
  amendment (`option` and `platform` rejected, `secondary` folded per OS, `ctrl--` handled).
- **Container driver and registry:** the exact `TARGET_ALLOWED` allowlist and the purge limited to
  baseline-new paths hold. The registry entries, the `NO_MACOS_INTEL` allowlist, and the wheel
  packaging are correct. Hatch includes the tracked `vendor_defaults/*.json`, and nothing ignores
  them.

I did not read `necessity-review.md`, so I made no necessity assessment and omit `necessity:`.

## Warnings

### WR-01: RECONFIGURE recreates a keys.json the user deleted or blanked (28 D-06 violated for the file level)

**File:** `installer/terminal_keys.py:786-838`
**Issue:** `_apply_owned_keys` has no counterpart to the guard that `_apply_whole_file` has
(`recorded and before is None and not still_named: return (), None`).

- When keys.json is missing or blank, `text = owned.seed(platform_os)` (line 788).
- For a recorded key the loop correctly takes the tombstone branch (line 816) and writes nothing.
- `commit_region(path, before, original, text, ...)` then still sees `text != original` (seed
  versus `""`), so it writes the vendor default and the created marker. The tuning record is
  rewritten and the function returns `((), None)`, so nothing is shown.
- `_pending_owned_keys` (line 862-863) says the opposite: missing or blank plus recorded means no
  pending work.

**Scenario (reproduced):**

1. Install on Linux with the version pin satisfied. keys.json is seeded.
2. The user deletes `~/.config/herdr-app/keys.json`. This is their documented way to reset to
   defaults, and the status pass correctly shows nothing pending.
3. They run RECONFIGURE (`skip_recorded=True`). The result is `((), None)` and `keys.json`
   exists again with the vendor default, written silently by the installer. A user-truncated
   whitespace file is likewise overwritten with the default.

The user's choice to delete is not honored. The file also becomes installer-created, and a later
strip may delete it.

**Fix:** After computing `text`, return early when nothing is to be written for a recorded key
set. Mirror the whole-file guard:

```python
text = original if original.strip() else owned.seed(platform_os)
...
if recorded and not original.strip():
    return (), None  # a deleted or blanked file stays the user's choice (28 D-06)
```

Place this before the seed is called so a recorded row never even probes the binary. The
`before is None and recorded` case must still reach the seed on a reinstall (`skip_recorded=False`).

### WR-02: Strip leaves `"terminal": {}` in a keys.json that the installer only added a section to

**File:** `installer/terminal_keys.py:916-926` (record at 735-755, insert at 823)
**Issue:** `insert_key` creates the missing `terminal` parent (`created_parent=True`), but the
ownership record stores only `(section, chord, value)`. Strip calls `remove_key(text, "json", key)`
without the recorded fragment or a created-parent flag, so only the leaf goes.

**Scenario (reproduced):**

1. The user file is `{"global": {"alt-1": "space.select:1"}}`. Apply yields
   `"terminal": {"ctrl-shift-k": "send:\f"}` placed first.
2. Strip returns `()`, yet the file is
   `{\n  "terminal": {},\n  "global": {...}\n}` and not the original bytes.
3. With a file that is just `{}` it ends as `{"terminal": {}}`.

Uninstall promises to remove only the owned keys, and for a file the installer did not create it
should return the user's bytes. The residue is harmless to the app, but it is a visible leftover,
and it reintroduces a section the user never had. The container proof only covers the seeded case
(pinned equality), so this path has no evidence.

**Fix:** Record `created_parent` in the ledger and remove an empty parent after the leaf strip.
For example, after `remove_key` for a key whose section lookup is now `{}` and which was recorded
as parent-created, call `remove_key(text, "json", (section,))`. Alternatively, persist the
`Inserted.fragment` and pass `fragment=` to `remove_key`, which already cuts the whole member.

### WR-03: A stale created-marker strands the owned key after a keys-path change and reconfigure

**File:** `installer/terminal_keys.py:778-782, 903-910` (marker rewritten only at `terminal_regions.py:725-730`)
**Issue:** `commit_region` writes the created marker and path sidecar only when `before is None`.
When the keys path moves to an existing file B, the ledger is rewritten for B, but the marker and
sidecar of the earlier created file A stay.

`_strip_owned_keys` then runs the sidecar check before any edit (line 903-910) and returns
`created config at A is not the file now resolved; left alone`. It never removes the key it wrote
into B, and it keeps the record.

**Scenario (reproduced):**

1. Install with the default folder, so keys.json is created at A with a marker and a sidecar.
2. Set `HERDR_APP_HOME=B`, where B already holds a user keys.json. Reconfigure writes the key into
   B and moves the ledger to B.
3. Uninstall with the same env prints the "created config at A" warning. B keeps `"ctrl-shift-k":
   "send:\f"`.
4. Returning env to A hits `edited keys were recorded for B`. B's key is never strippable.

The loss of A's proof is an accepted limit. The inability to ever strip B, whose proof is correct,
is a separate consequence. Plan 31-01's "safe order" decision chose the early return and the test
only covers a tampered sidecar with an equal ledger path, but it did not consider this reachable
route. This is the interaction of two accepted choices, so the owner should confirm whether to
change it.

**Fix:** The sidecar only guards deleting the created file. On mismatch, skip only the deletion and
still strip the recorded keys:

```python
may_delete = True
if row.bind_created_path and marker.exists():
    bound = sidecar.read_text(errors="replace") if sidecar.exists() else None
    may_delete = bound == f"{path}\n"
...
if may_delete and marker.exists() and text == owned.pinned(platform_os):
    ...  # delete
```

Keep the marker and sidecar when `not may_delete`, so A's proof survives. Alternatively, drop the
marker and sidecar when the ledger path changes. That also fits the single-path ledger.

### WR-04: A reinstall while "Load preferences from a custom folder" is on destroys a still-valid restore record

**File:** `installer/iterm2_profile.py:279-280, 304-305`
**Issue:** On a non-reconfigure apply with `current == ITERM2_GUID and prior is not None`, the
record is kept (`record = prior`). The following `if custom:` block then does
`replace(record, default_set=False)` and persists it, even though `previous` is still valid and
the earlier switch was ours.

**Scenario (reproduced with a fake defaults seam):**

1. Install normally: state has `previous=G`, `default_set=True`, `switched=True`.
2. The user enables `LoadPrefsFromCustomFolder`, runs the install action again (reinstall), then
   disables custom prefs.
3. The state is now `default_set=False`. `hook_restore` reports "your previous default could not
   be recovered; choose a default profile ... then uninstall again" and refuses the removal.

The recorded `previous` GUID is intact, so the restore could succeed. The user must manually
re-pick a default before they can uninstall, and the message claims the previous default is lost.

**Fix:** Do not clear `default_set` for a kept prior record. Apply the custom-folder downgrade only
to a fresh capture:

```python
if custom and record is not prior:
    record = replace(record, default_set=False)
    lines.append(...)
```

Keep the "custom folder; the default profile was not changed" line either way, because the switch
is skipped by `hook_after_write`.

## Info

### IN-01: Tool id special case in the generic owned-keys apply

**File:** `installer/terminal_keys.py:789-796`
**Issue:** `if tool_id == "herdr-app":` pre-validates a non-object top level so the refusal reads
"the keys file must hold objects only" instead of "does not parse". It is a per-tool branch in the
shared variant, and it duplicates `row.validate(text)` three lines below. No second row uses it,
and the fixture rows in `tests/test_terminal_ownership.py` use a different tool id, so the branch
is exercised only through the real row.
**Fix:** Run `row.validate(text)` before `_parse_owned(text)`. A non-object top level then gets
the row's own message for every row, and the id branch can go.

### IN-02: Home and platform seams that are not threaded through

**File:** `installer/herdr_app_keys.py:50-56`, `installer/app.py:831-835`,
`installer/terminal_keys.py:935-947`
**Issue:**
- `herdr_app_executable` uses `Path.home()`, although `apply_terminal_keys` receives an explicit
  `home` (and the ownership tests check that explicit home and environment are honored).
  `OwnedKeys.seed` takes only the platform.
- `remove_tool` has no `platform_os` parameter, so `before_removal_terminal_keys` receives
  `HOST_SETTINGS_OS`. The `platform_os=` that `perform_uninstall` and `run_uninstall` accept
  reaches only `_after_removal`.
- `before_removal_terminal_keys` deletes its `tool_id` argument.

None of this misbehaves on a real host, where both homes and both platforms coincide. A scratch-home
test of the seed reads the sandbox's `Path.home()` instead of the one passed in.
**Fix:** Optional. Give `seed` a `home` argument and give `remove_tool` a `platform_os` keyword
defaulting to `HOST_SETTINGS_OS`. Drop the unused `tool_id` parameter.

---

_Reviewed: 2026-11-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
