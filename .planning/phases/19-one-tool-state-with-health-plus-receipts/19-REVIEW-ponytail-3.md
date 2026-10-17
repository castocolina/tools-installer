# Phase 19 — ponytail review, round 3 (gap closure 19-32..19-37)

Scope: `git diff 8cea513 HEAD -- installer setup.py scripts tests` (29 files, +1459 / -284;
plans 19-32..19-37 plus the test-only fix 24d91d6).
Load assumed: one person running the TUI on their own machine, about 89 catalog tools,
a few worker threads. Same as rounds 1 and 2.

**Severity counts:** High 0 · Medium 1 · Low 6

## What this change does

It applies binding design L-19-31. A `dir` receipt artifact is now proven by the sha256
of one key file inside it: the archive member the bin link points to, or
`Contents/Info.plist` for an `.app`. Device and inode numbers are gone. Dir drift reads
as unproven (not removable), never BROKEN and never update-refused. File and link
drift stay BROKEN. A directory removal renames the tree to an exclusive quarantine
sibling, re-hashes the key file inside the captured tree, and only then deletes it. A
mismatch or a failed `rmtree` puts the tree back.

Around that: the execute screen refuses a BROKEN tool before the run (19-36). The skill,
shim and terminal-config reads go through the non-blocking capped reader (19-35). The
default `is_installed` lookup looks through the installer's own pnpm shim (19-34). A
failed skill-cache write still settles the packs and warns. Each pack keeps the scan of
the pass that published it. An ambiguous Claude listing no longer gets a second install
step (19-37). The test sandbox clears inherited manager/XDG overrides and stubs the
puppeteer launch seam (24d91d6).

## Round-2 findings

| # | Finding | Status | Where |
|---|---------|--------|-------|
| P2-1 | self-updating macOS app turns red and nothing clears it (Medium) | Closed (19-32, L-19-31) | `receipts.py:45` (`APP_KEY_FILE`), `receipts.py:418-456` (key-file dir fingerprint), `version_status.py:1270-1275` (dir drift -> `UNPROVEN_NOTE`, not BROKEN), `update.py:514-518` (dir drift never refuses). Tests `test_dir_drift_is_unproven_not_broken`, `test_dir_drift_does_not_block_an_update`. Accepted consequence: a vendor-updated bundle stays not removable until a reinstall (Phase 20 `r`), as L-19-31 decides. |
| P2-2 | one unreadable runtime hides another runtime's "empty" report | Closed (19-35) | `skill_lifecycle.py:587` uses the suggested condition, and the dead `targets = []` branch is gone. Test `test_unreadable_runtime_never_hides_another_runtimes_empty_install`. |
| P2-3 | `CatalogScreen._health_of` has no production caller | Closed (19-36, f9203a2) | Deleted. No references are left in `installer/` or `tests/`. |
| P2-4 | `remove_proven` checks the same set twice | Closed (19-33) | `uninstall.py:502-503`. |
| P2-5 | no-op alias in `_skill_state` | Closed | `version_status.py:1233-1238` uses `hosts` directly. |

## Must fix

1. **P3-01: the test-suite fork bomb is guarded at one seam, and its trigger is still
   in place** — Medium (`tests/conftest.py:101-117`, `tests/conftest.py:234`,
   `installer/executors.py:506`, `installer/executors.py:340`)
   - **What this is:** b1f0ac3 (RR-05) clears `VOLTA_HOME` for every test while `HOME`
     is a scratch dir. The real `~/.volta/bin` shims stay on `PATH`. A Volta shim that
     cannot find its own home falls back to "system" `node` by searching `PATH`, finds
     itself, and recurses. 24d91d6 records the result: 17,600 processes and
     `RuntimeError: can't start new thread`.
   - **Problem:** 24d91d6 stubs only `executors.launch_puppeteer` (`conftest.py:234`).
     The same binary is still one unpatched seam away. `executors._require_minimum("node",
     ["node", "--version"], ...)` (`executors.py:506`) goes through
     `executors.probe_version`, and nothing in the sandbox stubs that. Neither does it
     stub `npm`/`npx` (the same Volta shim binary) reached through `run_output`. The new
     net test `test_the_default_smoke_check_in_the_suite_starts_no_process` covers
     only the default audit path. Today every test that reaches those seams appears to
     patch them. Under the house rule "never mutate the developer's host", though, the
     next test that forgets crashes the developer's machine. It does not just fail.
   - **Fix (smallest root fix):** in `no_shell_location_env`, next to the
     `delenv("VOLTA_HOME")`, drop the real Volta bin dir from `PATH`:
     `monkeypatch.setenv("PATH", os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep) if not Path(p).is_relative_to(_REAL_HOME / ".volta")))`.
     That is 2 lines. With no Volta shim on `PATH`, a bare `node` can no longer
     recurse. Keep the launch stub, because a browser launch is still wrong in a test.
     **Complete version:** also add an autouse tripwire on `subprocess.Popen` (every
     `subprocess.run` in `installer/run.py` goes through it). It raises when
     `Path(argv[0]).name` is in `{"node", "npm", "npx", "pnpm", "volta"}`, unless a
     test opts in. That is about 8 lines.
   - **If we skip it:** the guard depends on every future test remembering two
     consumer-side patch points (`executors.probe_version`, `pnpm_globals.probe_version`).
     Forgetting one takes the host down during `make test`.

## Should fix

2. **P3-02: the L-19-31 "which drift is BROKEN" rule is written twice, and the update
   gate re-hashes dir key files it then ignores** — Low (`installer/version_status.py:1270-1275`,
   `installer/update.py:514-518`)
   - **What this is:** Health and the mutation gate each write their own
     `any(artifact.type != "dir" for artifact in receipts.drifted(...))`.
   - **Problem:** Round 2 asked for one `receipts` predicate. The rule now lives in two
     modules, and when they disagree you get the exact split G3/IN2-03 closed (the row
     says OK while `u` refuses, or the reverse). The gate also runs
     `drifted(receipt, rehash=True)` over every artifact. So it sha256-hashes the dir key
     file (for an archive that is the binary, e.g. a ~100 MB `node`) and then throws the
     result away.
   - **Fix:** one function in `receipts`:
     `def broken_drift(receipt, *, rehash=False): return tuple(a for a in receipt.artifacts if a.type != "dir" and not matches(a, rehash=rehash))`.
     `_receipt_evidence` calls `broken_drift` and then `drifted` only for the unproven
     note. The gate calls `broken_drift(receipt, rehash=True)`. The net line change is
     about 0, the rule has one owner, and the gate does one big hash fewer.
   - **If we skip it:** two copies of a locked rule, plus a wasted hash per installer
     update.

3. **P3-03: a malformed `.skill-lock.json` can still crash the skill probe, and the
   reader rewrites a pattern its own module already has** — Low
   (`installer/skill_lifecycle.py:717-733`, compare `installer/skill_lifecycle.py:846-848`)
   - **What this is:** 19-35 moved `_skills_lock_skills` to `read_capped`. It now decodes
     the bytes by hand, then calls `json.loads` and catches only `json.JSONDecodeError`.
   - **Problem:** A 1 MiB file of `[` passes the cap and raises `RecursionError`. That
     escapes `inspect_skill_reports` (`skill_lifecycle.py:943`) and `refresh_skills`
     (`version_status.py:1016`), and `run_live` does not catch it either. The worker
     dies, `_skills_probed` is never set, and every pack stays "checking". That is the
     round-1 P1 symptom. `_installed_project_paths`, 120 lines further down, already
     does it right: `json.loads(raw)` on the capped bytes with
     `except (ValueError, RecursionError)`. `UnicodeDecodeError` is a `ValueError`.
   - **Fix:** `parsed = json.loads(raw_bytes)` under `except (ValueError, RecursionError): return None`,
     and delete the manual decode block. That is -5 lines, plus a one-line test with a
     deeply nested file. The bug was already there before this diff, but 19-35 rewrote
     exactly these lines.
   - **If we skip it:** a corrupt lock file leaves every skill pack stuck in
     "checking", with no note.

## Nice to have

4. **P3-04: a dir key file is hashed three times on removal** — Low
   (`installer/uninstall.py:501`, `installer/uninstall.py:476`, `installer/uninstall.py:452`)
   - **What this is:** `remove_proven` re-proves with `plan_removal(verify=True)`.
     Then `remove_paths` checks again with `matches(artifact, rehash=True)`. Then
     `_remove_dir` re-hashes inside the quarantine.
   - **Problem:** For a `dir`, the quarantine re-check is the authoritative one
     (RR-01). The middle check only needs to confirm it is still a real directory
     with the key file stat-matching, so `os.rename` cannot raise on a non-dir. Its
     re-hash is the redundant one.
   - **Fix:** `receipts.matches(artifact, rehash=artifact.type != "dir")` at
     `uninstall.py:476`. A file keeps its RR-02 re-hash.
   - **If we skip it:** about 0.2 s more per 100 MB key file on an uninstall.

5. **P3-05: an interrupted directory removal leaves a hidden tree that nothing lists**
   — Low (`installer/uninstall.py:412`, `installer/uninstall.py:439-460`)
   - **What this is:** `_remove_dir` renames the tree to
     `.<name>.XXXX.tools-installer.rm` before `rmtree`.
   - **Problem:** If the process is killed during `rmtree` (an `.app` takes seconds),
     the hidden sibling remains in `~/Applications` or `~/.local/opt`. Nothing outside
     `_remove_dir` reads `_QUARANTINE_SUFFIX`, so it is never shown and never cleaned.
     The receipt then retires as all-gone, so no later pass mentions it. Auto-deleting
     it would be wrong: a tree whose put-back failed was never verified.
   - **Fix:** the smallest fix is a `shortcut:` comment at `uninstall.py:412` naming the
     limit (a killed removal leaves a hidden quarantine sibling; list it under "remove
     it yourself" if it shows up in practice). The complete fix is one glob for
     `*{_QUARANTINE_SUFFIX}` siblings in `plan_uninstall`, so they land in `yourself`.
   - **If we skip it:** rare, and only costs disk space, but it is invisible.

6. **P3-06: the receipt reader parses the digest triple twice, and `_safe_key` forces a
   `cast`** — Low (`installer/receipts.py:567-596`, `installer/receipts.py:378`,
   `installer/receipts.py:439`, `installer/receipts.py:593`)
   - **What this is:** The `dir` branch of `_read_artifact` repeats the `file` branch's
     sha256/size/mtime_ns parse and checks line for line. `_safe_key` returns `bool`,
     so `fingerprint` also checks `key is None` and `_read_artifact` has to
     `cast(str, artifact.get("key"))`.
   - **Fix:** parse the three fields once, before the `file`/`dir` branches, and
     reject a missing or malformed triple for both. Make `_safe_key` return
     `TypeGuard[str]`. That is about -10 lines, with no `cast` and no redundant
     `None` check.
   - **If we skip it:** two copies of a trust-boundary check that must stay identical.

7. **P3-07: small leftovers** — Low
   - `receipts.py:272-279`: the nested `one()` exists only to pass `key` for dirs.
     `fingerprint(e.path, e.kind, key=_dir_key(method, e.path, link) if e.kind == "dir" else None)`
     inline is -4 lines.
   - `execute_screen.py:555` and `execute_screen.py:521-523` guard a BROKEN state with no
     reason (88d3f3f). `tool_state` always puts the broken facts first, so production
     never builds one. Meanwhile `catalog_tui.py:809` indexes `state.reasons[0]`
     unguarded for the same state. Pick one rule: drop the guard, or guard both. The
     two `u` paths should not disagree about an impossible state.
   - `terminal_shell.py:270` hard-codes "1 MiB" next to `_CONFIG_MAX_BYTES`
     (`terminal_shell.py:249`). It goes stale the day the cap changes.
   - `receipts.py:258-260`: the `record` docstring has a broken wrap ("get\n none. When
     the write\n fails").

## Checked and fine

- `_remove_dir`: `mkdtemp` creates the quarantine exclusively in the same parent, so the
  rename never crosses a filesystem. Renaming a directory onto an empty directory is
  valid POSIX on Linux and macOS. A symlink or file swapped in after the pre-check
  makes `os.rename` raise (EISDIR/ENOTDIR). It is never followed. A mismatch puts the
  tree back. A failed put-back keeps the tree and names both paths (T-19-109). A failed
  `rmtree` puts the remainder back and re-raises. All three paths are tested
  (`test_remove_paths_refuses_a_dir_replaced_after_its_final_check`,
  `test_remove_paths_keeps_a_captured_dir_it_cannot_put_back`,
  `test_failed_opt_dir_delete_leaves_the_remainder_listed`).
- `_safe_key` refuses absolute, empty, `.`/`..`, NUL and unencodable keys. A forged
  receipt cannot point the matcher outside the directory by its own path. Intermediate
  symlinks inside the tree are followed, but only the same user can plant those.
- `link_key` uses the same strict resolve as `download.is_still_proven`. The
  archive-layout branch of `plan_removal` (`uninstall.py:150`) keys the dir the same
  way `record` does, so the layout proof and the receipt proof agree.
- Dir drift drops the whole receipt proof (`_receipt_proof`, `uninstall.py:96`), so the
  link is not removable either. Nothing is deleted halfway. The `UNPROVEN_NOTE` is
  added once: `_receipt_evidence` returns it with no broken facts, so the
  `receipt is None or broken` branch at `version_status.py:1611` skips it.
- The execute-screen refusal and the update gate agree. BROKEN comes only from a
  broken shim (sent to repair first) or non-dir receipt drift, and that is the gate's
  rule. Reasons are printed with `markup=False`.
- `_pack_scans` is bounded by the catalog, and each pack rebuilds with the scan of the
  pass that published it (RR-03).
- `invalidate` flips the in-memory flags before the cache write (WR2-03). The skill
  worker reads `service.warning` after a successful call. That may re-show the main
  pass's own warning, which is the same text, so it does no harm.
- RR-04's `fixed |= {"claude"}` holds because `SkillPackReport.reasons` come only from
  `_claude_fixes` (`skill_lifecycle.py:881-928`). If a non-Claude reason source is ever
  added, it will silently suppress Claude partials.
- `is_our_shim`, `_read_text` and `_skills_lock_skills` now open with `O_NONBLOCK`
  through `read_capped`. A FIFO no longer stalls the refresh worker. Tests cover all
  three.
- `status.is_installed` looks through the shim only on the default lookup, so the
  refresh service's `which` (which already looks through) is not unwrapped twice.
- `container-e2e-verify.sh`: `printf -v workspace '%q'` quotes the nested `cd`. It is
  covered by `test_pre_uninstall_check_survives_a_spaced_workspace`.
- `receipts.adopt` (`receipts.py:311`) calls `fingerprint` without `key`. Adoption is
  file-only (`version_status.py:1309`), so a dir adoption would fail closed, never pass.

Verdict: fix P3-01 first (2 lines). Then P3-02 and P3-03.
Lean: about -25 lines possible across P3-02..P3-07.
Not checked: the test suite was not run (P3-01 makes an unguarded run risky on this
host). The Volta recursion is reasoned from 24d91d6's own account, not reproduced. No
real-host or container pass was run, and the macOS Info.plist behaviour on vendor
self-update is assumed, not observed.
