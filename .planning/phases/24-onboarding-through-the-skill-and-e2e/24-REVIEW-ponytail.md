# Phase 24 ponytail review

Range: `git diff 9e2ff7b..HEAD -- installer scripts setup.py Makefile tests`.
Intent read: `24-SPEC.md` and the nine `24-0N-SUMMARY.md` files. Connected code read: `engine.py`, `executors.py`, `receipts.py`, `uninstall.py`, `app.py`, `resolve.py`, `version_status.py`, `postinstall.py`, `terminal_shell.py`, `agent_settings.py`, `scripts/container-e2e-verify.sh`.
Load assumed: one person running the TUI or `setup.py` on one machine, a few times a month. No concurrent installers.

What this change does:
It adds a new install kind, `cargo_distrobox`, that builds Alacritty from its release tag inside a throwaway Distrobox and places five files. It adds Alacritty and herdr to the terminal sync (shell region, key bindings, herdr `default_shell`). It adds herdr as a catalog tool with a hook pair, a version check that trusts the receipt's recorded release, a fail-closed `curl` script download, and a three-distro container harness.

Counts: HIGH 0, MEDIUM 3, LOW 7.

I ran the touched test files with `uv run pytest -n 0` (all pass; `cargo_distrobox.py` 93%, `terminal_shell.py` 93%, `postinstall.py` 92% branch coverage). The code is careful and well tested. The findings below are the gaps that remain.

Process note: one scratch probe ran from outside `tests/`, so the sandbox HOME did not apply. It staged and deleted `~/.local/bin/alacritty.tools-installer.new` once. I checked afterwards: no leftover file, no receipt, no `/tmp/tools-installer-cargo-*`.

## Must fix

1. **MEDIUM: installing Alacritty can hide the user's whole config** (`installer/terminal_shell.py:482-491`, used by `_sync_alacritty:594` and `apply_alacritty_keys:624`)
   - **What this is:** The terminal sync and the key tuning need the path of `alacritty.toml`. `alacritty_config_path` returns the first of three paths that exists, otherwise the XDG path `~/.config/alacritty/alacritty.toml`.
   - **Problem:** Alacritty also reads `~/.alacritty.toml` (documented fourth location, after the three the code knows; I did not find the string `.alacritty.toml` anywhere in `installer/`). A user who keeps only `~/.alacritty.toml` has none of the three candidates. The installer creates `~/.config/alacritty/alacritty.toml` holding only its two regions. Alacritty now finds that file first and stops reading `~/.alacritty.toml`. Fonts, colours and every user key silently stop applying. It happens on every sync, for anyone with zsh and Alacritty on PATH, whatever installed Alacritty.
   - **Fix:** Add `home / ".alacritty.toml"` as the last candidate. Then an existing file is edited in place and nothing new is created. Also fix the docstring ("three"). Add one test: only `~/.alacritty.toml` exists, so the sync writes its region there and creates no `.config/alacritty`.
   - **If we skip it:** A user with that legacy path sees their terminal "reset" after the next `make setup`, and the cause is hard to find.

2. **MEDIUM: a failed build can lose the "your box is still there" note** (`installer/cargo_distrobox.py:253` and `:258-265`)
   - **What this is:** `install()` catches three exception types, keeps the failure, runs `_cleanup` in `finally`, and puts the cleanup notes (box not removed, image kept) into the final error.
   - **Problem:** `ExecutorError` is not in the caught tuple. It is raised by `staged_member` (an artifact path the upstream moved), by `smoke_binary` (the new binary does not run), and by "declares no usable artifacts". Those are the most likely failures after an upstream release. The `finally` still runs `_cleanup`, but its return value goes into a local that is never read. If `distrobox rm` or `podman rmi` fails in that same run, nobody is told. I verified with a scratch test: a smoke failure plus a failing `rm` gives only `smoke run failed ...`, with no "could not remove the Distrobox" text.
   - **Fix:** Add `ExecutorError` to the except tuple (the message line logic already handles it). The `from failure` chain stays. Add a test: smoke fails and `rm` fails, so the error names the box.
   - **If we skip it:** A leaked box (up to 2 GB with its image and a cargo cache in `/tmp`) stays on the machine with no message, which is the exact thing SPEC prohibition 1 exists to stop.

## Should fix

3. **MEDIUM: the real build path has never run, only a fake runner** (`installer/cargo_distrobox.py:30-37`, `:97-137`; `24-08-SUMMARY.md` and `24-UAT.md` test 6 marker `REQUIRED`)
   - **What this is:** Every unit test uses `FakeBox`. The nested podman run that was meant to do the one real build recorded `TRACER_NESTED_INFEASIBLE`, so the acceptance "a real podman build of Alacritty is recorded once" is deferred to the user's UAT.
   - **Problem:** The argv is checked only against `distrobox ... --help` (1.8.2.5: `--home`, `--no-entry`, `--yes`, `--additional-packages`, `enter --no-tty --no-workdir`, `rm --rm-home --force` all exist, which I confirmed). The timeouts are guesses (the code comment says so). The first `distrobox enter` also pulls the box up and installs nine packages inside the 900 s clone bound. On a slow link that step hits `timeout` (exit 124), the row fails, the image is removed, and the next try pulls it again.
   - **Fix:** Do not ship Phase 24 as done until UAT test 6 has run once and its wall times are recorded. Then set `CLONE_TIMEOUT` and `BUILD_TIMEOUT` from the measured times with headroom. No code change is needed if the run passes.
   - **If we skip it:** The headline feature of the phase may fail on first use on the real host.

## Nice to have

4. **LOW: the binary path is exempt from the "user's own file" guard** (`installer/cargo_distrobox.py:155`, with `:150` and `_swap:171-199`)
   - **What this is:** Non-binary files that exist and are not in any receipt are kept and named. The binary is excluded (`host != binary`) so an update can replace it.
   - **Problem:** On a first install, any existing `~/.local/bin/alacritty` (a hand-copied binary or a symlink to `/usr/bin/alacritty`) is moved aside and deleted by `_swap`. `receipts.preexisting_paths` has already marked it preexisting, so the receipt drops it. The new binary is installed but not recorded, so uninstall will not remove it. This is reachable when the file is there but PATH does not list `~/.local/bin`, or after a lost receipt.
   - **Fix:** Use the same test for the binary: `os.path.lexists(host) and host not in proven` means refuse with a clear ExecutorError (for a regular file or symlink the user owns). One line.
   - **If we skip it:** A rare silent overwrite, plus an orphan binary.

5. **LOW: the new script download needs curl 7.71 or newer** (`installer/executors.py:454`, `--retry-all-errors`)
   - **What this is:** `_script` now downloads to a temp file with `--retry 3 --retry-all-errors`.
   - **Problem:** `--retry-all-errors` is unknown before curl 7.71 (Ubuntu 20.04 ships 7.68, Debian 10 7.64). `curl` exits 2, so every `script`-kind tool (rustup, sdkman, and the rest) fails there with "option not recognized". The registry's `apt` family covers such hosts.
   - **Fix:** Drop `--retry-all-errors` (keep `--retry 3`, which covers timeouts and 5xx) or probe `curl --help all`. Dropping is the shorter change.
   - **If we skip it:** Script installs break on older Debian-family hosts that worked before.

6. **LOW: herdr claims an integration the user has marked "needs repair"** (`installer/postinstall.py:248` regex, `:350-357`)
   - **What this is:** `_herdr_register` skips a host when herdr's status says `current`, and installs for `not installed` and for `needs repair`.
   - **Problem:** A user's own stale integration (for example after they upgraded herdr by hand) is re-installed by the hook and then recorded as ours. Uninstall later runs `herdr integration uninstall` for it, which removes an integration the user had set up. The registry comment says only "the last two are installed (and recorded)", so this is by design, but it contradicts the stated aim "never claimed or removed".
   - **Fix:** Treat `needs repair` like `current` (skip and name it), or install it but do not record it. One condition.
   - **If we skip it:** An uninstall removes a user's herdr hook that the installer did not create.

7. **LOW: harmless notes show as warnings** (`installer/engine.py:354` with `installer/cargo_distrobox.py:238-241`)
   - **What this is:** `leftovers.extend(notes)` turns the notes "kept the existing image X" and "could not tell whether the image was already there" into `⚠ alacritty postinstall warning: ...`.
   - **Problem:** A user who already has `fedora-toolbox:44` (common for Distrobox users) sees a warning on every successful install and every update, though nothing is wrong.
   - **Fix:** Show only the notes that mean something is left behind (box or image kept after a failed removal); drop the "existing image" note, or print it as plain info.
   - **If we skip it:** Warning noise trains users to ignore real warnings.

8. **LOW: the build tree sits in `/tmp`, often a RAM disk** (`installer/cargo_distrobox.py:28`, `:242`)
   - **What this is:** The box's HOME (clone, cargo registry, `target/`) is created under `/tmp` because the box shares the host `/tmp`.
   - **Problem:** On Fedora and Debian 13 `/tmp` is tmpfs (half of RAM by default). An Alacritty release build plus the crate cache is hundreds of MB. I did not measure it. On a machine with 4 GB RAM the build can fail with "no space left" (not caught by a precheck) and compete with the compiler for memory.
   - **Fix:** Record the real size in the UAT run. If it exceeds about 400 MB, use `shutil.disk_usage(RUN_ROOT).free` to check first and refuse with a clear message, or allow `$XDG_RUNTIME_DIR`/an on-disk dir that the box also mounts.
   - **If we skip it:** A confusing mid-build failure on small machines.

9. **LOW: the build is not isolated from the host, only its HOME is moved** (`installer/cargo_distrobox.py:99-110`)
   - **What this is:** `--home <tmp>` keeps cargo caches out of the real HOME. The SPEC constraint says host writes go only to `~/.local` and `~/.config`.
   - **Problem:** Distrobox mounts the host filesystem at `/run/host` read-write. Any crate's `build.rs` in Alacritty's dependency tree runs with the user's rights and could write to the real HOME through that path. The tag is checked to be a safe ref, but the tag is whatever upstream tagged last.
   - **Fix:** The cheap option is to say so in the registry comment and the skill (supply-chain trust equals running upstream's code), and pin `--branch` to a tag plus verify the commit when the registry bumps. Real isolation needs `--unshare-all`-style flags and a measured build; not worth it for one tool.
   - **If we skip it:** Nothing breaks. It is a documented-trust gap, listed so it is a decision.

10. **LOW: an "infeasible" nested run exits 0** (`scripts/container-e2e-verify.sh`, `cmd_nested` L1766-1790, branch `2) ;;`)
    - **What this is:** When nested podman cannot create the box, `cmd_nested` prints `TRACER_NESTED_INFEASIBLE` and counts it as not failed.
    - **Problem:** A wrapper or CI that reads only the exit code treats a run that proved nothing as a pass. The marker is the only signal, and it is what moved the real build onto the user's UAT.
    - **Fix:** Exit with a distinct non-zero code (for example 3) for infeasible, so callers cannot confuse it with success. Two lines.
    - **If we skip it:** A silent hole in the "recorded once" evidence if the exit code is ever used as a gate.

## Checked and fine (no finding)

- Ordering and rollback of `_stage`/`_swap`: staged `.new` files are always unlinked, a failed swap restores earlier swaps, a rollback failure names the stuck files.
- Tag and image/package/host path validation (`model.py`), `--` before the git URL, no shell in any argv, `timeout` wrapper on every step.
- `distrobox rm --force --rm-home` on a box that was never created returns 0 (read in `/usr/bin/distrobox-rm`), so a failed `create` produces no false "could not remove" note.
- Alacritty regions: re-parse before write, compare-before-commit, `TerminalShellError` is an `OSError` so every caller catches it, user-bound keys and inline `keyboard.bindings` are refused rather than overwritten.
- herdr `default_shell`: absent-only write, revert only while the ledgered value is still there; the reload is best effort.
- Uninstall: both owned regions stripped on the CLI and TUI routes; `_prune_empty_parents` stays inside the three roots and never removes a non-empty directory.
- Version pass: `_live_platform` adds one `node --version` per pass (cheap); the receipt-release override is guarded by BROKEN and unproven notes.

## Lean

Little to cut. The code is already tight; the new files are all used. Possible small removals: `download.cargo_hosts` re-validates `artifacts` that `model._cargo_distrobox_refusal` already guarantees for registry methods (about 8 lines, but it also guards hand-built `Method` objects in tests, so keep unless tests change).

Verdict: fix 1 and 2 first, and run UAT test 6 (finding 3) before calling the phase done. Fix 4 to 6 if you want them closed in this phase.
Lean: -8 lines possible.
Not checked: the real `distrobox`/`podman` build, Debian and Arch container behaviour (no containers run), and the `agent_settings` TOML splice and removal code beyond its tests and a read.
