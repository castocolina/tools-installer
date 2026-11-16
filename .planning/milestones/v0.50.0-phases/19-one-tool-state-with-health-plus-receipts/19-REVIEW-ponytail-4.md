# Phase 19 — ponytail review, round 4 (gap closure 19-38..19-45)

Scope: `git diff 23d832e HEAD -- installer setup.py scripts tests` (21 files, +881 / -108;
plans 19-38..19-45).
Load assumed: one person running the TUI on their own machine, about 89 catalog tools,
a few worker threads. Same as rounds 1 to 3.
Convergence rule applied: a new finding is reported only when it is grounded and either
Medium+ or a cheap correctness/deletion fix.

**Severity counts:** High 0 · Medium 1 · Low 1

## What this change does

It closes the round-3 findings and the other round-3 gaps. A dir key file now proves
only a directory it resolves inside (`_key_file`, RR3-01). Key-file fingerprints share
the session hash memo, and `record`/`adopt` bypass it with `rehash=True`. One
`receipts.broken_drift` owns the L-19-31 "which drift is BROKEN" rule for both health and
the update gate. A corrupt `.skill-lock.json` reads as unknown. A dir removal puts the
captured tree back on any catchable interruption, and `plan_removal` lists leftover
quarantine siblings under "remove it yourself". The pre-quarantine dir check is
stat-only. The shim look-through matches the managed dir by resolved path. Skill answers
that a failed cache write left unsaved are carried by the next pass commit before the
warning clears. The test sandbox strips the developer's toolchain dirs from `PATH` and
installs a `Popen` tripwire for node-family binaries and brew. The e2e script routes its
brew calls through a `BREW_BIN` constant so the host tests can stub it.

## Round-3 findings

| # | Finding | Status | Where |
|---|---------|--------|-------|
| P3-01 | test-suite fork bomb guarded at one seam (Medium) | Closed (19-39) | `tests/conftest.py:199-207` drops every `PATH` entry under the resolved real HOME and `/run/user`. The complete version is in too: `GuardedPopen` + `assert_not_host_toolchain` (`tests/conftest.py:35-108`) refuse a host `node`/`npm`/`npx`/`pnpm`/`corepack`/`volta`/`bun`/`yarn`/`brew` before launch. Tests in `tests/test_sandbox.py`. No `installer/` module imports `Popen` directly or uses `os.exec*`/`posix_spawn`, so the patch covers every launch. |
| P3-02 | BROKEN-drift rule written twice; gate hashes dir key files | Closed (19-43) | `receipts.py:583` (`broken_drift`), `version_status.py:1275`, `update.py:516`. Test `test_broken_drift_skips_dirs_and_never_hashes_their_key_file` (`tests/test_receipts.py:113`). |
| P3-03 | malformed `.skill-lock.json` crashes the skill probe | Closed (19-42) | `skill_lifecycle.py:725-729`, with `json.loads(raw_bytes)` under `except (ValueError, RecursionError)`. Test `test_skills_lock_deep_nesting_or_bad_bytes_is_unknown` (`tests/test_skill_lifecycle.py:821`). |
| P3-04 | dir key file hashed three times on removal | Closed (19-44) | `uninstall.py:518` (`rehash=artifact.type != "dir"`). Test `test_remove_proven_hashes_a_dir_key_file_twice_not_three_times`. The layout-proof fingerprint now also hits the memo (`receipts.py:495-511`), and that fails closed: a stale memo digest only makes the quarantine re-hash refuse. |
| P3-05 | interrupted dir removal leaves an unlisted hidden tree | Closed (19-44), complete fix | `uninstall.py:114-133` (`_quarantined`), wired at `uninstall.py:190`. `_remove_dir` (`uninstall.py:454-498`) also puts the tree back on `BaseException`, so only SIGKILL leaves a sibling. Tests at `tests/test_uninstall.py:2475`, `:2542`, `:2581`. |
| P3-06 | digest triple parsed twice; `cast` on the key | Closed (19-45) | `receipts.py:603` and onward parses the triple once. `_safe_key` returns `TypeGuard[str]` (`receipts.py:386`), and the `key is None` check and the `cast` are gone. |
| P3-07 | small leftovers | Closed | `one()` inlined (`receipts.py:274-286`). The reason-less BROKEN guard now matches on both `u` paths (`catalog_tui.py:810`, `execute_screen.py:555`). The cap text follows `_CONFIG_MAX_BYTES` (`terminal_shell.py:270`). The `record` docstring wrap is still ragged (`receipts.py:264-267`). That is cosmetic, so it is not re-raised. |

## Must fix

1. **P4-01: `write_tester_path` now writes `eval "$( shellenv)"` into the tester's rc
   files** — Medium (`scripts/container-e2e-verify.sh:171`, `scripts/container-e2e-verify.sh:179`)
   - **What this is:** 1664d9d replaced the literal brew path with `${BREW_BIN}` in four
     places. In `assert_receipt_ready_for_removal` (`:320`) and `run_setup_as_tester`
     (`:343`), the payload is double-quoted, so the host expands it correctly.
     `write_tester_path`'s payload is single-quoted (`exec_tester '...'`, `:169-186`).
     There `${BREW_BIN}` reaches the container literally, and the container's shell
     expands it to empty because `BREW_BIN` is not set there.
   - **Problem:** Reproduced by running the extracted payload under a scratch `HOME`.
     `.bash_profile` gets `eval "$( shellenv)"`. On a fresh container:
     - every `su - tester -c …` login shell prints `shellenv: command not found`;
     - brew is not on the rc-file `PATH`;
     - the line has no `linuxbrew` in it, so the `grep -q linuxbrew` guard never
       matches and every re-bootstrap appends another broken copy.

     Steps that `eval` brew explicitly still work, so the main run passes and the
     breakage is easy to miss. A container bootstrapped before 1664d9d keeps its good
     line, which hides it locally too. The e2e container is the only sanctioned
     real-install gate (AGENTS.md "Never mutate the developer's host").
     `test_shell_scripts_path.py`'s payload tests count only `.local/bin` lines.
     `test_extracted_functions_never_name_the_host_brew` checks only the two
     double-quoted functions.
   - **Fix (smallest):** put the literal `/home/linuxbrew/.linuxbrew/bin/brew` back on
     lines 171 and 179. The stub only exists for the two extracted functions. No host
     test runs brew from this payload, and `sync_workspace`/`bootstrap_homebrew_and_uv`
     keep the literal path too. That is 0 net lines. Add one assert to the existing
     payload test in `tests/test_shell_scripts_path.py` (around `:103-130`):
     `assert "/home/linuxbrew/.linuxbrew/bin/brew shellenv" in bash_profile_text`.
     That pins it.
     (The alternative of keeping the constant and splicing it out of the single
     quotes, `'"${BREW_BIN}"'`, works too, but it is harder to read for no gain.)
   - **If we skip it:** fresh e2e containers run with a broken tester shell and
     brew-less login `PATH`, and the rc files grow one bad line per bootstrap.

## Should fix

2. **P4-02: the resolved-path match raises on a symlink loop in `PATH`** — Low
   (`installer/guards.py:324-328`, same pattern in `tests/conftest.py:204-205`)
   - **What this is:** 19-41 changed the retry filter from a string compare to
     `Path(entry).resolve() != managed` for every `PATH` entry.
   - **Problem:** The project runs Python 3.12. There, non-strict `Path.resolve()` raises
     `RuntimeError("Symlink loop …")` on a looping entry (verified in a scratch dir;
     3.13 stopped raising). `real_binary` runs this loop whenever the lookup misses or
     hits our shim, for example `real_pnpm` with pnpm absent. One self-referencing
     symlink dir on a user's `PATH` then raises out of `real_binary`. The old string
     compare never raised. The trigger is rare. The fix is one call.
   - **Fix:** `os.path.realpath(entry) != os.path.realpath(shim_dir)` (realpath does not
     raise on loops in non-strict mode). Make the same swap in the conftest filter.
     That is about 0 net lines, plus one `test_guards` case with a looping `PATH` entry.
   - **If we skip it:** a looping `PATH` entry makes the shim look-through raise
     instead of answering "not found".

## Checked and fine

- `_key_file` (`receipts.py:404-418`): both sides resolve strictly, so a symlinked
  `/home -> /var/home` prefix still compares equal. It returns the unresolved
  `target`, so a symlinked final component still fails `S_ISREG` on `lstat`.
  `link_key` keys come from a fully resolved path, so no legitimate key has an
  intermediate symlink that a quarantine rename could break.
- `_file_fingerprint` memo: `record` and `adopt` pass `rehash=True`. The adoption
  pre-check at `version_status.py:1313` uses the memo, but `adopt` re-fingerprints from
  the bytes and refuses a mismatch. The layout proof's memoized digest is only the
  value the quarantine re-hash must equal. Every memo path fails closed.
- `_remove_dir`: `verified` is read only on the normal path. A `BaseException` before
  it is assigned re-raises after the put-back. Note that
  `raise put_back_error from None` drops the rename errno from the chain and keeps the
  interruption as `__context__`. A test pins that choice
  (`test_an_interrupted_removal_that_cannot_put_back_names_the_quarantine`). The
  message still names both paths, so it is left alone.
- `_quarantined` costs one glob of a small parent directory per dir artifact, per
  `plan_removal`. That is cheap at 89 tools. `.yourself` feeds only the uninstall
  hints and `render_remove_yourself`, never `tool_state`/health and never a delete.
- `_skills_unsaved` is read and written only under `self._lock`, in both
  `refresh_skills` (`version_status.py:1028-1044`) and the pass commit
  (`version_status.py:1685-1703`). That gives no lost-update window. After an
  `invalidate`, the carried host answers are the same values, just marked stale in
  memory.
- `look_through_shim` still returns `PATH`'s own spelling of the hit. Only the
  managed-dir comparison is resolved.
- Targeted suites pass: `test_receipts`, `test_uninstall`, `test_guards`,
  `test_sandbox`, `test_version_status`, `test_skill_lifecycle`, `test_catalog_tui`
  (`-n 0 --no-cov`).

Verdict: fix P4-01. It is 2 lines plus a 1-line assert, and it breaks fresh e2e
containers. P4-02 is a cheap optional hardening. With those done, the round converges.
Not checked: no container run was done, so P4-01 is reproduced from the extracted
payload under a scratch `HOME`, not inside a real container. The full `make test` and
`make validate` were not run. The macOS `Info.plist` behaviour is still assumed.
