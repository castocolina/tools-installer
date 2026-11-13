---
phase: 24-onboarding-through-the-skill-and-e2e
lane: deep
reviewed: 2026-11-13T00:00:00Z
depth: deep
range: 9e2ff7b..HEAD -- installer scripts setup.py Makefile .pre-commit-config.yaml tests
files_reviewed: 29
files_reviewed_list:
  - installer/cargo_distrobox.py
  - installer/desktop_entry.py
  - installer/agent_settings.py
  - installer/agent_env.py
  - installer/terminal_shell.py
  - installer/postinstall.py
  - installer/post_install.py
  - installer/executors.py
  - installer/download.py
  - installer/engine.py
  - installer/receipts.py
  - installer/version_status.py
  - installer/versions.py
  - installer/update.py
  - installer/uninstall.py
  - installer/app.py
  - installer/ownership.py
  - installer/resolve.py
  - installer/platform.py
  - installer/model.py
  - installer/session.py
  - installer/render.py
  - installer/wizard_app.py
  - installer/registry.toml
  - setup.py
  - Makefile
  - .pre-commit-config.yaml
  - scripts/container-e2e-verify.sh
  - tests (cargo_distrobox, terminal_shell, agent_settings, postinstall, container_e2e_receipts: coverage of the risky branches)
findings:
  critical: 0
  high: 2
  medium: 3
  low: 5
  total: 10
status: issues_found
---

# Phase 24: Code Review Report (deep lane)

**Depth:** deep (cross-module call chains traced: engine/update -> cargo_distrobox -> receipts;
terminal_shell -> agent_settings ledger; app removal -> strip/revert; version_status -> receipt release)
**Status:** issues_found

## Summary

The new kind is careful in the places the plan called out. Argv validation (repo slug, image ref,
package names, release tag, artifact roots) is closed. There is no shell anywhere in the build argv
and no sudo path. The `finally` cleanup ordering holds even on KeyboardInterrupt, and receipt
filtering of pre-existing leaves works. The guarded TOML insert and revert restores a pre-existing
herdr `config.toml` byte for byte; I probed that and it holds.

The two HIGH defects are both in the terminal shell sync, and both are confirmed by running the
real code in a scratch HOME:

- Alacritty's config locator misses one of Alacritty's own search paths. The installer then
  creates a file that hides the user's whole config, and the file stays after uninstall.
- herdr's ledgered `default_shell` is orphaned as soon as the resolved zsh path string changes.
  After that, the installer never fixes it and never reverts it.

The MEDIUM items are:

- a lost remediation note for a leaked Distrobox;
- an Alacritty keybindings region that outlives a whole-environment uninstall;
- a nested e2e classifier that reports any `distrobox create` failure as an environment problem.

Because of that last one, the real cargo build path has no automated proof. UAT test 6 is the only
check left, and it is still pending.

Verification method: every HIGH/MEDIUM below was reproduced or confirmed against the source.

- Probes ran with `env -i HOME=<scratch>` (the herdr and Alacritty probes).
- The smoke-failure probe ran through the repo conftest (`pytest -p tests.conftest`) with the
  `FakeBox` runner.
- The distrobox claim was read from `/usr/bin/distrobox-rm` (1.8.2.5) on this host.

## High

### HR-01: Alacritty config at `~/.alacritty.toml` is shadowed by an installer-created file, permanently

**File:** `installer/terminal_shell.py:482-491` (`alacritty_config_path`), used by `_sync_alacritty`, `apply_alacritty_keys`, `strip_alacritty`

**Issue:** The locator checks three candidates:

- `$XDG_CONFIG_HOME/alacritty/alacritty.toml`
- `$XDG_CONFIG_HOME/alacritty.toml`
- `~/.config/alacritty/alacritty.toml`

If none exists, it falls back to the first one. Alacritty searches a fourth user location,
`$HOME/.alacritty.toml`, and since 0.14 also `/etc/alacritty/alacritty.toml`. Alacritty loads only
the first file it finds.

**Failure scenario (reproduced in a scratch HOME):**

1. The user keeps their config in `~/.alacritty.toml` (`[font] size = 14`).
2. Install tuning (`apply_terminal_tuning`) and the shell sync create
   `~/.config/alacritty/alacritty.toml`, which holds only the installer regions.
3. Alacritty now loads that file and ignores the user's fonts, colors and keys.
4. `strip_alacritty` on uninstall rewrites the file to `''` and leaves it in place.
   The probe output was `after uninstall exists True ''`.
5. The user's config therefore stays shadowed after the tool is gone, and the install receipt
   never recorded that file.

**Fix direction:**

- Add `home / ".alacritty.toml"` as the fourth candidate. Consider `/etc/alacritty/alacritty.toml`
  as a "do not create a user file" signal.
- Record whether this installer created the file (a record next to `_KEYS_RECORD`, like
  `ledger.created_files`). Delete it in `strip_alacritty` when only the regions were ever in it.
- Add a test beside `test_alacritty_is_created_in_the_first_existing_location_or_the_xdg_one` for
  the fourth location and for create-then-strip.

### HR-02: herdr `default_shell` is orphaned when the resolved zsh path changes, so it is never updated or reverted

**File:** `installer/terminal_shell.py:724-755` (`_sync_herdr`) together with `installer/agent_settings.py:830-844` (`_apply_pass` `set_by_you` branch) and `:844-854` (`_kept_entries`)

**Issue:**

- `apply_value` is absent-only. When the key holds a value different from the new `zsh_path`,
  `_apply_pass` classifies it as `set_by_you` and adds it to `dropped`.
- That value may be one the ledger says the installer wrote. `_kept_entries` then deletes that
  ledger entry, and the empty-diff branch writes the ledger without it.
- From then on the key is treated as the user's own value. Sync prints
  `herdr: partial: you already set terminal.default_shell` and never repairs it.
- `_revert_herdr` (zsh removed) and herdr uninstall (`_revert_settings`) find nothing to revert.

**Failure scenario (reproduced):**

1. A sync with zsh at `/usr/bin/zsh` writes the key and records it.
2. The next sync resolves zsh at `/home/linuxbrew/.linuxbrew/bin/zsh`. The probe printed:
   key still `/usr/bin/zsh`, warning `partial`, ledger `entries=()`.
3. A sync without zsh reverts zshenv only. The key `/usr/bin/zsh` stays in herdr's config.

The path can change in realistic ways:

- brew zsh vs system zsh: `which_with_brew` returns the PATH hit first and the brew prefix second;
  the installer installs zsh via brew on immutable hosts.
- `/bin/zsh` vs `/usr/bin/zsh` on merged-usr systems, depending on PATH order.

New herdr panes then try to start a shell path the installer wrote that may no longer exist. The
installer has also given up ownership of the key, which breaks SPEC R6 ("zsh going away reverts
only the key the installer wrote").

**Fix direction:**

- In `_sync_herdr`, before calling `apply_value`, check whether the ledger has a `default-shell`
  entry whose value equals the current key.
- If it does, replace the value: revert that entry, then apply. Alternatively, add a "ours, replace"
  path in `_apply_pass` for `DYNAMIC_KEYS`: a recorded value that still matches is replaced, not
  dropped.
- Never let a dynamic key's own ledger entry be dropped as `set_by_you`.
- Add a test: sync with zsh A, then sync with zsh B, then sync with no zsh. Assert the key follows
  B and is then removed.

## Medium

### MR-01: A smoke or staging failure drops the "could not remove the Distrobox" remediation note

**File:** `installer/cargo_distrobox.py:247-266`

**Issue:** `install` catches only `(CommandError, OSError, DesktopEntryError)`. Several errors
raised inside `_stage` are `ExecutorError`, which subclasses `RuntimeError`, not `OSError`:

- `smoke_binary` (staged binary fails its smoke run);
- `staged_member` (an artifact missing from the box);
- "declares no usable artifacts".

For these the `finally` still computes `cleanup_notes = _cleanup(...)`, but the exception leaves the
function from the `finally` block. The `raise ExecutorError("; ".join([line, *cleanup_notes]))` at
the end is never reached, so the notes are discarded.

**Failure scenario (reproduced with `FakeBox`):**

1. A smoke failure (exit 127) happens together with a `distrobox rm` failure.
2. The function raises `ExecutorError('smoke run failed for ... (exit 127): no output')`.
3. The steps were `create, clone, build, tic, rm, rmi`, but the message has no
   `distrobox rm --force --rm-home ti-cargo-...` line.

The user is never told that a container leaked, or how to remove it. The SPEC prohibition is
"MUST NOT leave a Distrobox container", so this note is the only signal they would get.

**Fix direction:** Catch `ExecutorError` in the same `except` tuple, or append `cleanup_notes` to
any escaping exception. Add a test that combines a smoke failure with an `rm` failure.

### MR-02: The Alacritty keybindings region and its record survive a whole-environment uninstall unless the installer itself removed Alacritty

**File:** `installer/app.py:699-700` (the only caller of `strip_alacritty`), `installer/version_status.py:691-704`, `installer/post_install.py:273-287`

**Issue:**

- `strip_alacritty` runs only from `_after_removal`, which runs only after
  `remove_tool(...).removed`.
- `_terminal_tuning_fact` offers the `apply install tuning` step for any present Alacritty,
  whatever its owner. That includes a native dnf/apt/pacman copy, which this installer never
  removes (zero-sudo handoff).
- The whole-environment uninstall reverts every agent ledger even for tools it does not remove
  (`run_uninstall` -> `_revert_settings(CONFIG_AGENTS)`). It has no equivalent for the
  `alacritty-keys` region, and the shell region stays while zsh stays.

**Failure scenario:**

1. Alacritty is installed natively. The row reads `≈ apply install tuning` and the user applies it.
2. `make uninstall` (full sweep) leaves the `alacritty-keys` region in the user's `alacritty.toml`.
3. It also leaves `~/.local/share/tools-installer/terminal-tuning-alacritty` behind.

That record is outside `config_paths`, so it is an undocumented leftover in the data dir.

**Fix direction:** Call `strip_alacritty` from the whole-environment branches as well: after the
CONFIG_AGENTS revert in `run_uninstall`, and in `perform_uninstall` under `remove_tweaks` or
`revert_settings`. Otherwise, offer the tuning only when the installer owns Alacritty.

### MR-03: The nested e2e reports every `distrobox create` failure as "infeasible" and exits 0; the real build path is unproven

**File:** `scripts/container-e2e-verify.sh:1554-1576` (`nested_classify_alacritty`), `:1539-1551` (`nested_probe_podman` always returns 0), `:1766-1790` (`cmd_nested`: build=2 does not set `failed`)

**Issue:**

- Any failed Alacritty row whose text contains `distrobox create` returns 2, and `cmd_nested`
  treats 2 as success.
- A product regression in the create argv would match too: a flag the box's distrobox lacks, a
  bad `--additional-packages` value, a wrong `--home` path. So would a broken image ref in the
  registry. Each prints `TRACER_NESTED_INFEASIBLE` and still passes.
- 24-08-SUMMARY records exactly this outcome (`step=distrobox-create`).
- The clone/build/tic/copy/rm/rmi argv against a real distrobox and podman has therefore never run
  in automation. UAT test 6 is the only remaining proof, and `24-UAT.md` is `status: pending`.
- Related observation (LR-01): distrobox 1.8.2.5 does not honour `--rm-home` together with
  `--force`, which shows the real tool's semantics are not covered by the `FakeBox` tests.

**Fix direction:**

- Classify as infeasible only on environment signatures: `podman info` / `podman run` probe
  failure, fuse or overlay errors, `newuidmap`, `cannot set up namespace`.
- Make `nested_probe_podman` failure short-circuit with a distinct non-zero exit, so a red
  environment is never reported green.
- Keep ONB-02 acceptance open until UAT 6 or a nested run passes the build.

## Low

### LR-01: `--rm-home` is a no-op with `--force`, and temp-dir cleanup failures are silent

**File:** `installer/cargo_distrobox.py:206, 220-221`

**Issue:**

- In `/usr/bin/distrobox-rm` 1.8.2.5, `--force` sets `non_interactive=1`. The custom-home prompt
  then never runs, `response_rm_home` stays `"N"`, and the home is not removed.
- The run dir is actually removed only by `shutil.rmtree(run.tmp, ignore_errors=True)`.
- If any file in it is not removable by the user (for example one created with a mapped subuid
  during box init), the build tree (cargo target, GBs) stays in `/tmp` and nothing reports it.
  That contradicts the docstring "failures are notes".

**Fix direction:**

- Drop the misleading `--rm-home`, or keep it only as a belt next to the rmtree.
- Use `rmtree(onexc=...)` to collect failures and append a note naming the path.

### LR-02: `curl --retry-all-errors` needs curl >= 7.71; older curl fails every script-kind install

**File:** `installer/executors.py:451-457`

**Issue:** The old pipeline used no post-2020 curl flags. With the new one, curl older than 7.71.0
exits 2 with "option --retry-all-errors: is unknown". The `&&` then skips the script, and every
`script` method fails. Examples are Ubuntu 20.04's curl 7.68 and, to my knowledge, macOS 11's
curl 7.64.1.

**Fix direction:** Drop `--retry-all-errors` (plain `--retry 3` with `-o` is already retry-safe),
or probe `curl --help all` once.

### LR-03: An interrupt between the two `os.replace` calls in `_swap` leaves the live path missing

**File:** `installer/cargo_distrobox.py:175-180, 255-257`

**Issue:** `_swap` only rolls back on `OSError`. Consider a KeyboardInterrupt after
`os.replace(host, old)` and before `os.replace(new, host)`:

1. The `finally` in `install` deletes every `.new`, including that one.
2. The live `~/.local/bin/alacritty` is now gone, and only `alacritty.tools-installer.old` remains.
3. Nothing calls `recover_update_remnants` for this kind.

This contradicts the SPEC edge row "an interrupted rebuild keeps the old binary". The window is
small.

**Fix direction:** Widen the rollback to `BaseException`, or restore `.old` files in the `finally`
before unlinking `.new`.

### LR-04: `herdr server reload-config` runs unbounded while the TUI owns the terminal

**File:** `installer/terminal_shell.py:696-704` called with `runner=run_captured` from `setup.py:669`

**Issue:** `run_captured` -> `run_output(timeout=None)`. The `run_output` docstring itself says that
a wedged child under Textual has no recoverable input path. A herdr server that accepts the socket
but never answers would hang the post-run follow-up on every lifecycle route.

**Fix direction:** Bound it, using `run_query`-style `timeout=QUERY_TIMEOUT`, and keep the failure a
note.

### LR-05: Building under host `/tmp` inherits its mount limits

**File:** `installer/cargo_distrobox.py:26-28, 242`

**Issue:** `RUN_ROOT` is fixed at `/tmp` and bind-mounted into the box, and bind mounts keep the
source's mount flags. On hosts with `/tmp` mounted `noexec`, cargo's `build.rs` executables under
`target/` fail to run. On a small tmpfs `/tmp` (default 50% of RAM), a release build of Alacritty
can hit ENOSPC. Both surface as an opaque cargo failure.

**Fix direction:** Detect `noexec` or low free space on `/tmp` before create and fail with a clear
reason, or let the row detail name the cause.

## Test gaps on risky branches (no separate severity; each is tied to a finding above)

- No test for the `~/.alacritty.toml` location or for create-then-strip leaving an empty file (HR-01).
- No test for a zsh path change between herdr syncs, or a revert after it (HR-02).
- No test for a smoke or `staged_member` failure combined with a failed `distrobox rm` (MR-01).
- No test for the whole-environment uninstall stripping Alacritty regions that the installer did
  not remove (MR-02).
- No test for an interrupt inside `_swap` (LR-03). The existing interrupt test covers only the
  build step.
- The nested classifier tests assert the infeasible mapping but not that a product failure is told
  apart from an environment failure (MR-03).

## Checked and found sound (no finding)

- Argv safety: `_REPO_SLUG_RE`, `_IMAGE_REF_RE` (qualified host required), `_DISTRO_PACKAGE_RE`,
  `_TAG_RE` plus `--` before the URL, artifact `box` relative with no `..`, `host` limited to
  `~/.local|~/.config|~/.terminfo`, binary under `~/.local/bin`, `staged_member` containment
  after resolve. No sudo, pkexec or doas anywhere in the new code.
- Image ownership: tri-state `image exists`, rmi only when pulled, never `--force`.
- Receipts: leaves filtered by the pre-install snapshot; a user's pre-existing desktop or terminfo
  file is kept, named, not recorded, and so never deleted. `plan_uninstall` narrows cargo evidence
  to the binary. `_prune_empty_parents` is limited to empty dirs under three roots.
- Release recording: cleared per ladder method; an invalid tag is dropped before write; the
  version_status override applies only for installer owner with an intact fingerprint.
- Guarded TOML nested insert and revert: probed against a pre-existing user `config.toml` with all
  four herdr keys; the revert is byte-identical to the original.
- Removal order: hook tools first, then each agent's revert; `_drop_deleted_ledgers` drops a ledger
  only when every recorded file is gone.
- Desktop entry: Exec quoting and escaping follow the spec's two-layer rule; control characters
  are refused.

---

_Reviewer: Claude (gsd-code-reviewer, deep lane). Not run: containers, real distrobox builds, make
targets. Probes used scratch HOMEs only._
