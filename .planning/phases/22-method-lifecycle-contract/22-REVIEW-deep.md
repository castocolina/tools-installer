---
phase: 22
lane: deep
reviewed_at: 2026-11-04T12:00:00Z
base: 6fcaa7f
head: e8c1590
depth: deep
files_reviewed: 27
files_reviewed_list:
  - installer/app.py
  - installer/catalog_tui.py
  - installer/download.py
  - installer/engine.py
  - installer/executors.py
  - installer/manager_versions.py
  - installer/model.py
  - installer/ownership.py
  - installer/pnpm_globals.py
  - installer/receipts.py
  - installer/registry.toml
  - installer/render.py
  - installer/session.py
  - installer/skill_lifecycle.py
  - installer/tool_browser.py
  - installer/ui_common.py
  - installer/uninstall.py
  - installer/update.py
  - installer/verify_registry.py
  - installer/version_cache.py
  - installer/version_status.py
  - installer/wizard_app.py
  - setup.py
  - scripts/container-e2e-verify.sh
  - scripts/e2e-residue-allowlist.txt
  - tests/test_executors.py
  - tests/test_container_e2e_receipts.py
findings:
  blocker: 0
  high: 3
  medium: 9
  low: 5
  total: 17
status: issues_found
---

# Phase 22: Deep code review (lane deep)

**Range:** `git diff 6fcaa7f..e8c1590 -- installer setup.py scripts tests`
**Method:** read every changed source module, traced the removal chain
(`removal_plan` → `plan_removal` → `_receipt_proof` → `remove_tool` → `remove_paths`/`_remove_dir`
→ `receipts.delete`), the install chain (`build_plan.install_row` → `engine.install_tool` →
`needs_manual` / `_package_already_there` / `receipts.record`), the update chain
(`update_refusal` → `_perform` → `_update_installer_owned`) and the e2e harness. Three findings
were reproduced in a scratch `HOME` under the session scratchpad with fake runners (nothing ran
on the host): CR-01, CR-02 and CR-06/CR-08/CR-09 (validator and inventory checks).

No BLOCKER. No executor argv starts with `sudo`/`pkexec`/`doas`; the remaining elevation paths
are vendor/manager-internal (CR-10) or unguarded registry data (CR-08). Dead code: none found
(`vulture --min-confidence 60` reports nothing on the new names).

## HIGH

### CR-01 — HIGH — A failed userspace method that falls through to a native method ends as `manual`, its error dropped, exit 0

**File:** `installer/engine.py:245-253`, `:345`; `installer/session.py:224-233` (`_FAILURE`), `:464`
**Problem:** The ladder returns `MANUAL_REQUIRED` as soon as it reaches a native method, without
the `errors` the earlier methods appended. `_INSTALL_RESULT` maps that to `manual`, which is not
in `_FAILURE`, so `exit_code` is 0. The plan-time check (`session.install_row`) only looks at
`methods[0]`, so the review promised an install.
**Failure scenario:** Fedora, kitty (`[script, dnf]`) or rg (`[github_release, dnf, brew]`):
the download fails (network, checksum-free failure, vendor script error). Reproduced with a
raising fake runner: `kitty manual-required errors=() sudo dnf install kitty`,
`rg manual-required errors=() sudo dnf install ripgrep`. The row reads `manual — you run: sudo dnf
install kitty`, the real error is never shown or logged, `--all --yes` exits 0, and for rg the
applicable brew method is never tried.
**Fix:** When `errors` is non-empty at the native step, return `FAILED` with the errors (and the
handoff as a hint), or keep `MANUAL_REQUIRED` but carry `errors` and count it as a failure:
```python
manual = executors.needs_manual(method, writable=executors.prefix_writable)
if manual is not None:
    if errors:
        return InstallOutcome(tool.id, InstallStatus.FAILED, errors=tuple(errors),
                              handoff=(manual.command,), manual_command=manual.command)
    return InstallOutcome(tool.id, InstallStatus.MANUAL_REQUIRED, ...)
```
Add an engine test: first method raises `CommandError`, second is `dnf` → `FAILED`, error kept.

### CR-02 — HIGH — L1 manager removal trusts a manager receipt forever: stale receipts fail the CLI teardown permanently and can uninstall the user's own package

**File:** `installer/uninstall.py:228-239` (`_manager_argv`), `installer/receipts.py:394-400`
(`all_gone` never retires an artifact-less receipt), `installer/app.py:655`, `:738-755`
(`run_uninstall` filters only `level == "none"`), `installer/version_status.py:1968-1980`
**Problem:** A brew/cask/uv/pnpm receipt has no artifacts, so nothing ever re-checks that the
package is still the one this installer put there, and the pass never retires it. The CLI
removes every catalog tool whose plan level is not `none`, with no presence or inventory check;
the TUI hides MISSING tools, so the two front ends disagree.
**Failure scenario:** (a) Reproduced in a scratch HOME: a `jq` brew receipt, the user ran
`brew uninstall jq` by hand → `removal_plan` is `manager ('brew','uninstall','jq')`, the run
fails with `No such keg`, the receipt stays. Every later `setup.py --uninstall --yes` prints
`jq: remove failed` and exits 1; the TUI shows jq as not installed, so nothing in the product
can clear it. (b) Same, but the user then runs `brew install jq` themselves: the receipt still
"proves" it, the TUI labels it `installed by this installer through Homebrew: receipt matches`
and both front ends uninstall the user's own package (SPEC R4: only "when a receipt proves that
the installer put that package there").
**Fix:** In the refresh pass, retire a manager-kind receipt when a readable inventory
(`ManagerInventory` the pass already holds) lacks its package — the manager-kind twin of G10.
In `run_uninstall`, skip an L1 tool whose package is absent from a fresh readable inventory
(treat it as already removed and delete the receipt). Optionally record the manager's install
time/version in the receipt and require it to match.

### CR-03 — HIGH — The phase's own e2e gate fails at HEAD: removals leave undeclared sibling launchers and report `removed`

**File:** `installer/registry.toml:2166` (bun), `:2195`/`:2203` (pnpm), `:2252` (volta);
`scripts/container-e2e-verify.sh:787-789`; evidence `22-13-SUMMARY.md` "D-2"
**Problem:** SPEC R11 acceptance ("passes on a clean run; one Fedora podman run recorded") is not
met: the recorded `make e2e` at `4190481` stops at `assert_no_leftovers` with 27 roots, and HEAD
`e8c1590` adds only ledger rows. The removal-side defect is real: each method's `paths` names
only the main binary, so `~/.bun/bin/bunx`, `~/.local/share/pnpm/bin/{pn,pnpx,pnx}` and volta's
`~/.volta/bin/{node,npm,npx,pnpm,yarn}` shims survive while the row reads `removed`.
**Failure scenario:** `--uninstall --yes` exits 0, reports bun/pnpm/volta removed, and leaves
launchers for the deleted binaries in directories user rc files still put on PATH; `make e2e`
exits non-zero, so the phase cannot close on its own gate.
**Fix:** Declare the sibling launchers as `leaf` paths (verified against each install script),
decide each residue class from D-2 (declare as `config_paths` or allowlist with a reason), and
record a passing Fedora run before marking R2/R11 done.

## MEDIUM

### CR-04 — MEDIUM — `ERR_PNPM_GLOBAL_PKG_NOT_FOUND` is accepted as proof of removal from whichever pnpm PATH resolves now

**File:** `installer/app.py:575-597`
**Problem:** Any pnpm "not found" on a `pnpm remove --global` is read as "already gone" and the
receipt is deleted. Nothing checks that an earlier removal in this run took the package's group,
or that `real_pnpm()` (resolved at removal time, while the preview printed bare `pnpm`) is the
pnpm/global dir that installed it.
**Failure scenario:** The package was installed under one pnpm (standalone `~/.local/share/pnpm`)
and the removal runs with another pnpm first on PATH (Volta's or brew's, different global dir).
That pnpm says not found, the row reads `removed`, the receipt goes, and the package stays
installed with no proof left, so the installer can never remove it again.
**Fix:** Accept "not found" only when another member of the same declared co-install group was
removed earlier in this run, or re-query `pnpm_global_packages()` and accept only when a readable
listing lacks the package; otherwise report `remove_failed`.

### CR-05 — MEDIUM — A native method now ends the ladder before an applicable, sudo-free brew method

**File:** `installer/engine.py:245-253`, `installer/session.py:684-698` (`install_row`),
`installer/resolve.py:13-29` (native rank 30 < brew 40)
**Problem:** SPEC R3 makes a *native-only* tool a handoff. The implementation hands off any tool
whose first applicable method is native, even when `brew` applies (`platform.has_brew`).
**Failure scenario:** Mutable Fedora with Homebrew (the e2e container): simulated ladders show
`jq, git, zsh, watch, docker, podman, glab` as `[dnf, brew]` → all become `manual: sudo dnf
install …` although `brew install` would run without elevation. Before this phase the ladder
fell through to brew when the native step failed.
**Fix:** Treat a native method as a handoff candidate only: skip it and continue the ladder; if
no later method succeeds (or none exists), end with the MANUAL handoff. Mirror the rule in
`install_row` (MANUAL only when every applicable method is native).

### CR-06 — MEDIUM — The R3-02 "already in the manager" check misses tap-qualified formulae, so an install can claim the user's package

**File:** `installer/engine.py:348-371`, `installer/ownership.py:415-420`, registry
`installer/registry.toml:1576` (`formula = "anomalyco/tap/opencode"`)
**Problem:** `brew list --versions --formula` lists short names (`opencode 1.19.5`); the check
compares the declared `anomalyco/tap/opencode`. Verified: with that listing,
`_package_already_there(...)` returns `False` ("proven absent").
**Failure scenario:** macOS, opencode already installed from the tap by the user, presence
missed (repair, or brew bin off this process's PATH — the R3-02 premise), opencode's script
method fails, the brew method "installs" (exit 0 on an existing keg) and a receipt is written.
A later Uninstall runs `brew uninstall anomalyco/tap/opencode` on the user's own package.
**Fix:** Compare on the formula's last path component (`package.rsplit("/", 1)[-1]`) for brew
kinds, or query `brew list --full-name`; add a test with a tap-qualified formula.

### CR-07 — MEDIUM — Regular-file leaves in the shared bin dir are proven by type alone

**File:** `installer/receipts.py:517-522` (`fingerprint` leaf), `:638-645` (`_leaf_matches`),
`:328-338` (`_proven_before` carries proof across updates); registry leaves `~/.local/bin/uv`,
`~/.local/bin/uvx`, `~/.local/bin/agy`
**Problem:** A `leaf` that is a regular file matches any regular file at that path. `~/.local/bin`
is shared with pip `--user`, uv tool and other installers.
**Failure scenario:** The installer installed uv by script; the user later runs
`pip install --user uv` (a regular-file console script at `~/.local/bin/uv`). The leaf still
"matches", Uninstall deletes the pip launcher, and an update re-carries the proof forever.
**Fix:** Record `sha256`/size for regular-file leaves at install and after each installer-run
update (the update path already re-records the receipt); on mismatch, drop removal proof (as a
`dir` does) rather than deleting.

### CR-08 — MEDIUM — The zero-sudo guard does not cover the new registry argv channel

**File:** `installer/model.py:561-569` (`_script_token_ok`), `:1059-1066`;
`tests/test_executors.py:146-157`
**Problem:** `remove`/`update` tokens accept `sudo`, `pkexec`, `doas` (verified:
`_script_token_ok("sudo")` returns `None`), and these argv are handed to the runner verbatim
(`update.py:449`, `app.py:582`). The AST test scans Python literals only, never `registry.toml`.
**Failure scenario:** A registry edit `update = ["sudo", "kitten", "update-self"]` loads, passes
`make validate`/`make test`, and `u` runs sudo — exactly the SPEC Prohibition "MUST NOT run sudo,
pkexec or doas from any executor".
**Fix:** Reject an elevation word (or a path whose basename is one) as the first token of
`remove`/`update` in `load_tools`, and extend the zero-sudo test to every loaded method argv.

### CR-09 — MEDIUM — `config_paths` validation accepts shared well-known directories

**File:** `installer/model.py:512-528` (`_config_path_flaw`), `:545-558` (`_refuse_config_overlap`)
**Problem:** The only rules are `~/`, depth ≥ 2 and harness markers. Verified accepted:
`~/.local/bin`, `~/Library/Preferences`, `~/.config/systemd`, `~/.ssh/id`. Overlap is checked
only between config entries, never against the managed bin dir, script `paths`, or opt dirs.
`delete_config_path` then `rmtree`s whatever was declared.
**Failure scenario:** A registry typo `config_paths = ["~/.local/bin"]` (or a macOS
`~/Library/Preferences` entry meant to be `.../pnpm`) loads cleanly; one `c` + confirm deletes
every tool's binaries or all app preferences.
**Fix:** Add a denylist of shared roots (`~/.local/bin`, `~/.local/share`, `~/.local/state`,
`~/.config` itself, `~/Library/*` at depth 2, `~/.ssh`, `~/.gnupg`, `~/.config/systemd`,
`~/.config/autostart`) and refuse any config entry that equals, contains or lies under any
tool's declared artifact (`artifact_paths` of every method, plus `locations.bin_dir`).

### CR-10 — MEDIUM — Cask L1 removal can still elevate through Homebrew (residual R3, unaddressed)

**File:** `installer/uninstall.py:99-104` (`"cask": ("brew","uninstall","--cask")`),
`installer/run.py:87-98` (`env=None`: the child inherits the whole environment)
**Problem:** Zero sudo is held only for argv this code builds. `brew uninstall --cask` runs a
cask's `uninstall` stanza, which may call sudo itself; `stdin=DEVNULL` and a new session stop a
tty prompt but not `NOPASSWD` sudo, and the inherited environment keeps `SUDO_ASKPASS` (Homebrew's
sudo wrapper uses askpass when it is set — not re-verified against upstream in this review).
**Failure scenario:** macOS user with passwordless sudo (or an askpass helper) removes a
pkg-based cask from Uninstall: Homebrew runs root deletions the user never saw in the review.
**Fix:** Run cask removals with `SUDO_ASKPASS` removed and `SUDO_PROMPT`-free env, and refuse L1
for a cask whose `brew info --cask --json=v2` uninstall artifacts include `pkgutil`/`launchctl`/
`delete` outside `~` (hint only), or document the residual in the review text the user confirms.

### CR-11 — MEDIUM — Declared `update` argv runs its first word from PATH, not from the proven leaf (residual R3)

**File:** `installer/update.py:436-449`; registry `update` rows for claude, opencode,
cursor-agent, bun, pnpm, uv
**Problem:** `remove` is bound to a receipt-proven leaf (R2-03); `update` is not. The receipt for
these tools proves `~/.local/bin/claude`, `~/.opencode/bin/opencode`, etc., but `u` runs
whichever `claude`/`opencode`/`uv` comes first on PATH.
**Failure scenario:** A second copy earlier on PATH (brew `opencode`, a pip `uv`) is the one
updated; the installer then re-records the receipt over the untouched proven copy and reports
`updated`.
**Fix:** Apply `_recipe_argv`'s binding to `update`: when the first word names a proven leaf
(by basename), replace it with that leaf's absolute path; refuse with a hint when the receipt
proves no such leaf (keep `sdk` and `{omz_root}` special cases).

### CR-12 — MEDIUM — The leftover check is blind under harness dirs and for level-`none` receipts

**File:** `scripts/container-e2e-verify.sh:586-588` (every harness marker dir is an allowed
prefix), `:563` (`removable-receipts.txt` only lists level ≠ none),
`scripts/e2e-residue-allowlist.txt:10`
**Problem:** Allowing whole marker dirs (`.codex`, `.local/share/cursor-agent`, `.opencode`, …)
means any undeclared vendor file under them passes. The allowlist comment says "a left receipt is
caught by assert_removed_receipts_gone", but level-`none` receipts are never checked
(22-13 known gap), and `.local/state/tools-installer` is allowlisted.
**Failure scenario:** codex's `install.lock` and `auto-update-version` and cursor-agent's `logs/`
and `worker.lock` survive every uninstall unflagged, contradicting 22-REVIEWS R3-03 ("22-13's
must-clear check catches what stays"). Script receipts with no artifacts (oh-my-zsh, sdkman, the
brew bootstrap) survive `--uninstall --yes` and the run still passes.
**Fix:** Allow harness dirs only for paths present in the baseline or under config entries; flag
new files under a marker that sit beside a declared tree. Check that every receipt is gone after
`--uninstall --yes` unless its tool is hint-only, and list those survivors explicitly.

## LOW

### CR-13 — LOW — The review's pnpm group warnings read live state, not the frozen decision

**File:** `installer/wizard_app.py:1600-1607` vs `:1671`
**Problem:** `decision.argv` comes from the painted rows (`_by_key`), the warnings from
`self._state_of(...)` now. A publish that has not been repainted yet makes them disagree.
**Failure scenario:** The review lists `pnpm remove --global mmdc` but omits (or adds) the group
warning for a state the user never saw.
**Fix:** Derive the packages from `decision.argv` (`argv[:-1] == MANAGER_UNINSTALL_ARGV["node"]`).

### CR-14 — LOW — "Config kept" stats the disk on the UI thread

**File:** `installer/wizard_app.py:1701-1711`
**Problem:** Acknowledged 22-11 deviation: `is_symlink()`/`exists()` per declared config path in
`on_removal_finished`.
**Failure scenario:** A HOME on a stalled network mount freezes the TUI after a removal.
**Fix:** Compute the kept set inside the removal worker (it already touches the disk) and carry it
on `RemovalFinished`.

### CR-15 — LOW — A `c` refusal during a removal is silent

**File:** `installer/wizard_app.py:1636-1639`
**Problem:** Acknowledged 22-10 deviation: the refusal text is dropped while `Removing…` holds
the status line, so the key looks broken.
**Fix:** Show it in the detail bar, or queue it until the removal ends.

### CR-16 — LOW — A malformed cached `greedy` value reads as "no auto-updating casks", not unknown

**File:** `installer/version_cache.py:343-349`
**Problem:** `_str_set(...)` returns `None` for a malformed value and `or frozenset()` turns it
into a known empty set, so `_needs_query` does not force a re-read.
**Failure scenario:** A corrupt cache hides a greedy-outdated VS Code (shows current) until the
6-hour expiry.
**Fix:** `greedy=None if greedy_raw is None else _str_set(greedy_raw)` (keep `[]` → empty set,
malformed → `None`).

### CR-17 — LOW — Two `$ZSH` resolvers with opposite precedence

**File:** `installer/download.py:250-255` (`$ZSH` first) vs `installer/omz.py:530-543`
(`~/.oh-my-zsh` first)
**Problem:** Presence and ownership use the default-first root; `u` runs `{omz_root}` from the
`$ZSH`-first root (SPEC R8 wording).
**Failure scenario:** `~/.oh-my-zsh` is the installer's copy and `$ZSH` points at a system copy
(`/usr/share/oh-my-zsh`): `u` runs the system copy's `upgrade.sh`, which fails or updates the
wrong tree, while the proven copy is untouched.
**Fix:** Resolve `{omz_root}` from the root ownership proved (the default when it holds the
receipt/`detect_path`), else `$ZSH`; one resolver for both.

---

_Reviewed: 2026-11-04_
_Reviewer: Claude (gsd-code-reviewer, lane deep)_
_Depth: deep_
