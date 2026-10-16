---
phase: 19-one-tool-state-with-health-plus-receipts
reviewed: 2026-10-16T19:11:21Z
depth: deep
files_reviewed: 55
files_reviewed_list:
  - installer/app.py
  - installer/apps.py
  - installer/catalog_tui.py
  - installer/download.py
  - installer/engine.py
  - installer/execute_screen.py
  - installer/guards.py
  - installer/install_ownership.py
  - installer/model.py
  - installer/ownership.py
  - installer/pnpm_globals.py
  - installer/receipts.py
  - installer/registry.toml
  - installer/skill_lifecycle.py
  - installer/status.py
  - installer/terminal_shell.py
  - installer/tool_browser.py
  - installer/ui_common.py
  - installer/uninstall.py
  - installer/update.py
  - installer/version_status.py
  - installer/wizard_app.py
  - scripts/container-e2e-verify.sh
  - setup.py
  - tests/conftest.py
  - tests/state_doubles.py
  - tests/test_app.py
  - tests/test_catalog_tui.py
  - tests/test_container_e2e_receipts.py
  - tests/test_docs.py
  - tests/test_download.py
  - tests/test_engine.py
  - tests/test_execute_screen.py
  - tests/test_guards.py
  - tests/test_install_ownership.py
  - tests/test_layout_80x20.py
  - tests/test_locations.py
  - tests/test_model.py
  - tests/test_ownership.py
  - tests/test_pnpm_globals.py
  - tests/test_policies_e2e.py
  - tests/test_receipts.py
  - tests/test_registry.py
  - tests/test_setup.py
  - tests/test_shell_scripts_path.py
  - tests/test_skill_lifecycle.py
  - tests/test_status.py
  - tests/test_terminal_shell.py
  - tests/test_tool_browser.py
  - tests/test_tool_health.py
  - tests/test_uninstall_e2e.py
  - tests/test_uninstall.py
  - tests/test_update.py
  - tests/test_version_status.py
  - tests/test_wizard_app.py
findings:
  critical: 1
  warning: 5
  info: 6
  total: 12
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-10-16T19:11:21Z
**Depth:** deep
**Files Reviewed:** 55
**Status:** issues_found

## Summary

Scope: `git diff 5e4bfa7..HEAD`. All 22 `installer/` sources, `setup.py` and
`scripts/container-e2e-verify.sh` were read in full at the changed hunks and
followed across modules: the install -> `receipts.record` -> refresh pass
(`_receipt_evidence`, `_adopt`, `plan_removal`) -> `ToolState` -> catalog,
execute and uninstall consumers -> `remove_proven` flow, plus the update path
(`UpdateService.run` -> `_perform` -> receipt rewrite). The tests were used to
check coverage of the risky paths. They were not reviewed line by line.

The receipt module itself holds up well. The reader fails closed. The
removal set is the receipt intersected with `artifact_paths` on (path, type)
pairs, so a tampered receipt cannot widen deletion. Deletion re-hashes every
file. Tool ids are validated at load. The adopt path re-checks under the
lock. No sudo/pkexec/doas paths were added. `setup.py` changes are wiring
only, and every view still goes through `VIEWS` and `show_view`.

The defects sit at the edges, where one path got a guard and a sibling path
did not:

- The execute screen's update route still overwrites a "changed since
  install" binary, even though the `u` key refuses it and 19-RESEARCH
  Pitfall 10 names this exact hazard.
- A manager update rewrites a receipt of a different method kind.
- The M9 shim fix in `is_installed` misses the PATH branch, which is where
  the shim is actually found.
- The new "reinstall with r" note points at a key the catalog already binds
  to something else.

## Critical Issues

### CR-01: Selecting a BROKEN ("changed since install") tool overwrites the changed file through the update route

**File:** `installer/execute_screen.py:564-577` (also `installer/update.py:480-487`, `installer/catalog_tui.py:778-781`)
**Issue:** The phase added drift detection: a receipt artifact that no longer
matches makes the tool BROKEN with "changed since install". The catalog `u`
key refuses a BROKEN row (`catalog_tui.py:778`). 19-RESEARCH Pitfall 10 states
the hazard: "a 'changed since install' raw file get overwritten on select ...
`_replace_raw` replaces whatever sits at the link". `_classify_selection`
avoids it for the repair route only.

`_update_targets` still sends every installed tool whose `version.outdated` is
not `False` to `UpdateService.run`. A BROKEN tool reads as present
(`ToolState.present` includes BROKEN). `UpdateService.run` re-resolves
ownership, but ownership never looks at receipts. So the drifted file at
`~/.local/bin/<cmd>` still resolves to `installer`/`direct`, and
`_update_installer_owned` -> `update_download` -> `_replace_raw` replaces it.
`_perform` then calls `receipts.record`, so the drift evidence is erased too.

Concrete case: yq was installed by this installer (receipt written). The user
swaps in a local dev build at `~/.local/bin/yq` whose `--version` reports
"dev", so `outdated is None`. The row shows `! broken`. The user marks yq and
presses enter, and the dev build is silently replaced with the release.
`tests/test_execute_screen.py::test_classify_reads_the_state` publishes exactly
this state (`drifted`, version None) and checks only `"drifted" not in repair`.
With this code, `drifted` IS in `_to_update`, and nothing asserts against it.

**Fix:** Put the refusal in the one mutation gate, so the keypress and the
execute screen cannot disagree. Then the keypress check can stay as a fast
path or be dropped.
```python
# installer/update.py, UpdateService.run, right after the MUTATION_GRADE refusal
receipt = receipts.read(target.tool.id)
if fresh.owner == "installer" and receipt is not None and receipts.drifted(receipt, rehash=True):
    return UpdateOutcome(
        tool_id=target.tool.id,
        status="failed",  # or a dedicated "refused" status
        owner=fresh.owner,
        detail="changed since install; not updated (reinstall it explicitly)",
    )
```
Also add `assert "drifted" not in to_update` to `test_classify_reads_the_state`
(or skip BROKEN-by-receipt states in `_update_targets`).

## Warnings

### WR-01: A manager update replaces a receipt of a different method kind, orphaning the installer's own files

**File:** `installer/update.py:330-337`
**Issue:** The condition `owner == "installer" or receipts.read(id) is not None`
rewrites ANY existing receipt with the updating manager's method. Take rg: the
installer installed it via github_release, so the receipt holds the opt dir
plus the link. Later the user brew-installs ripgrep, and brew's copy becomes
the active one (owner `brew`, method = the registry brew method). Pressing `u`
runs `brew upgrade ripgrep`, then `receipts.record(rg, brew_method)` writes a
receipt with `kind: brew` and zero artifacts. `plan_removal` now sees a
receipt file. It takes the receipt-only branch with no layout fallback
(`uninstall.py:115`), so `~/.local/opt/rg` and `~/.local/bin/rg` drop to
"remove it yourself", although this installer created them. The comment's
intent ("updating someone else's package never makes it ours") also breaks
the other way: the update deletes the installer's own proof.
`test_brew_update_rewrites_only_an_existing_receipt` only seeds a brew receipt.
**Fix:** Refresh only a receipt of the same kind:
```python
existing = receipts.read(target.tool.id)
if method is not None and (
    owner == "installer" or (existing is not None and existing.method.kind == method.kind)
):
```

### WR-02: The M9 shim fix in `is_installed` misses the PATH branch, so the default call still counts the installer's own shim as the tool

**File:** `installer/status.py:117-123`
**Issue:** `_is_installer_shim` was added to the declared-`bin_dir` loop and
the implicit-bin loop ("a ban or redirect shim ... is not the tool"). The shims
live in `~/.local/bin`, which this installer puts on PATH. So in the default
call (`which=None` -> `shutil.which`), the first branch finds the shim and
returns True before either loop runs. The TUI escapes this through
`_looked_through`. The CLI paths do not: `run_wizard` uses `install_tool` with
`present=None`, and `setup.py:792`/`:1409` call `is_installed(tool)`. Concrete
case: the pnpm global-redirect shim (`GLOBAL_REDIRECTED["pnpm"]`) is on disk
and real pnpm was removed. `setup.py --all --yes` then reports pnpm
`ALREADY_INSTALLED` and its dependents fail. The new test
`test_installer_shim_is_never_presence` passes `which=_which_none`, which hides
the branch.
**Fix:** Apply the same exclusion to the PATH hit:
```python
if (
    resolved is not None
    and not _is_installer_shim(tool, Path(resolved))
    and macos_stub_reason(tool, darwin=darwin, probe=probe, which=which) is None
):
    return True
```
Add a test that passes a `which` returning the shim path.

### WR-03: The "not proven: reinstall with r to adopt" note points at a key the catalog binds to "add recommended"

**File:** `installer/version_status.py:605` (used at `:1546`); `installer/catalog_tui.py:314`
**Issue:** The catalog detail bar tells the user to press `r`. In
`CatalogScreen`, `r` is `Binding("r", "accept_recommends", ...)`. Following
the note either does nothing, or, when a recommendations prompt is pending,
stages the pending recommended tools into the batch. That is a mutation of the
selection the user did not ask for. The comment says Phase 20 adds the `r`
binding, but the key is already taken, so the instruction is wrong today and
will collide later.
**Fix:** Until a reinstall action exists, word the note without a key, for
example "not proven: reinstall it to adopt". Pick a free key in Phase 20, or
move `accept_recommends` off `r`.

### WR-04: Dir artifacts are proven by existence only, and receipts now authorize `rmtree` of `~/Applications/<App>.app`

**File:** `installer/receipts.py:322-325, 344-345`; `installer/download.py:283`; `installer/uninstall.py:73-91`
**Issue:** `matches` for a `dir` artifact is `is_dir() and not is_symlink()`.
Before this phase, app bundles were never removable (always "remove it
yourself"). Now a receipt-proven app tool deletes the whole bundle. Concrete
case: the installer installed an app (receipt: bundle dir + cli link). The
user trashes the bundle and later installs the same app from the vendor DMG
into `~/Applications`. The installer's cli link still has the same target
string. The stale receipt still "matches", and `--uninstall` rmtree's the
user's own bundle. `~/Applications` is user namespace, unlike
`~/.local/opt`. D-08 chose type-only dir fingerprints, but did not weigh this
consequence for user-namespace bundles (19-10-SUMMARY notes the new
removability without discussing it).
**Fix:** Record a cheap identity for dirs at install/update time and compare
it: `(st_dev, st_ino)` from `lstat`, which changes when the bundle is deleted
and re-created. The installer's own `update_app` re-records it after its swap.
An in-place vendor self-update would then read as drift, which is the
fail-closed direction. If that trade-off is unwanted, at least keep app
bundles out of the receipt-proven set (link only).

### WR-05: The pi update hint drops `--ignore-scripts` from the reviewed host-setup handoff

**File:** `installer/update.py:312-322` (handoff at `installer/host_setup.py:31`)
**Issue:** `HOST_SETUPS["pi"]` is a reviewed handoff:
`pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent`. The new
"unsupported" update outcome tells the user to run
`pnpm add --global <package>` without `--ignore-scripts`. Following it re-adds
the package with lifecycle scripts allowed, unless pnpm's own default blocks
them. That contradicts the closed, reviewed command this project ships for the
same package.
**Fix:** Derive the hint from the handoff instead of hand-writing a second
command, or at least emit `pnpm add --global --ignore-scripts {package}`.

## Info

### IN-01: The re-hash memo key does not include the expected digest

**File:** `installer/receipts.py:359-366`
**Issue:** `_REHASH_MEMO[(path, size, mtime_ns)]` stores "matches the
recorded sha256", but the key omits which sha256 that was. After a receipt
rewrite, a file restored with preserved metadata (`cp -p` of the old version)
can hit a stale `True` and read as not drifted. Removal re-hashes
(`rehash=True`), so this affects the health mark only.
**Fix:** Add `artifact.sha256` to the key.

### IN-02: `ToolState.removable` and `ToolState.receipt` have no consumer, contrary to D-10

**File:** `installer/version_status.py:708-709`
**Issue:** D-10 says the pass's `RemovalPlan` "is the only gate" for the CLI
and the TUI. In practice, `classify_tools` (`uninstall.py:342`) and
`run_uninstall` (`app.py:563`) each call `plan_removal` themselves. The two
fields are computed on every pass (receipt read plus drift check per tool) and
read nowhere outside `version_status.py`. Rule 5 calls this kind of thing
orphaned data.
**Fix:** Drop the fields, or make the Uninstall view read
`state_of(id).removable` (deletion still re-proves via `remove_proven`).

### IN-03: Pending presence reads as absent in the requires/recommends previews

**File:** `installer/catalog_tui.py:480-495`
**Issue:** `_presence_map` maps "no state / CHECKING" to `False`. Before the
first pass lands, and after every invalidate, marking a tool says "also
needs <dep>" for deps that are already installed, and offers installed
recommendations. The old code used the launch-time presence map, so this is
a small regression in the preview.
**Fix:** Fall back to `service.is_present(tool)` (which probes when there is
no settled state) for the preview maps.

### IN-04: The receipt records `smoke: "ok"` for app installs that ran no smoke

**File:** `installer/engine.py:246-252`
**Issue:** `downloaded` is True for any `app` method, but `_stage_and_swap_app`
smokes only when `cli` is declared (`apps.py:149-155`). Nothing reads
`Receipt.smoke` yet, so it is wrong data, not wrong behavior.
**Fix:** Have `install_app`/`install_download` report whether they smoked, or
record `None` for an app without `cli`.

### IN-05: The e2e receipt check relies on errexit inside a function

**File:** `scripts/container-e2e-verify.sh:480-481`
**Issue:** `assert_receipt_present "$categories"` is followed by
`return 0`. A missing receipt fails the run only because `set -e` fires
inside `cmd_pass1`. If the function is ever called from `if`/`||`, errexit is
off there and the failure is swallowed. `cmd_pass2` already uses the explicit
form.
**Fix:** `assert_receipt_present "$categories" || return 1`.

### IN-06: Zero-artifact manager receipts are never retired and disable the layout fallback

**File:** `installer/uninstall.py:115-123, 399-422`; `installer/engine.py:246-254`
**Issue:** Every successful brew/cask/node/uv/script install writes a receipt
with no artifacts. `remove_proven` deletes a receipt only through `by_tool`,
which requires at least one proven path, so these receipts survive a full
`--uninstall` forever. While one exists, `plan_removal` skips the layout proof
and `_receipt_evidence` skips adoption for that tool.
**Fix:** Either do not write receipts for kinds whose `artifact_paths` is
empty, or let `plan_removal` fall back to the layout proof when the receipt's
kind has no artifact formula.

---

_Reviewed: 2026-10-16T19:11:21Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
