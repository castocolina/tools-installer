---
phase: 19-one-tool-state-with-health-plus-receipts
reviewed: 2026-10-17T05:33:07Z
depth: deep
diff_base: 23d832e
reviewed_head: b714868
files_reviewed: 21
files_reviewed_list:
  - installer/catalog_tui.py
  - installer/guards.py
  - installer/receipts.py
  - installer/skill_lifecycle.py
  - installer/terminal_shell.py
  - installer/uninstall.py
  - installer/update.py
  - installer/version_status.py
  - scripts/container-e2e-verify.sh
  - tests/conftest.py
  - tests/test_catalog_tui.py
  - tests/test_container_e2e_receipts.py
  - tests/test_docs.py
  - tests/test_guards.py
  - tests/test_receipts.py
  - tests/test_sandbox.py
  - tests/test_shell_scripts_path.py
  - tests/test_skill_lifecycle.py
  - tests/test_tweaks.py
  - tests/test_uninstall.py
  - tests/test_version_status.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
prior_closed: 14
prior_partial: 1
prior_open: 0
status: issues_found
---

# Phase 19: Code Review Report (re-review 4: gap round 3, plans 19-38..19-45)

**Reviewed:** 2026-10-17T05:33:07Z
**Depth:** deep
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Scope: `git diff 23d832e..b714868 -- installer setup.py scripts tests` (21 files,
+881 / -108): plans 19-38..19-45, which close the round-3 findings (my WR3-01,
IN3-01..04; opencode RR3-01..03; ponytail P3-01..07; consolidated J1..J9). I
read every changed hunk and followed it into the code it calls: `_key_file`
into `fingerprint`/`matches` and into `_remove_dir`'s quarantine re-check; the
`_file_fingerprint` memo against `_file_matches`'s memo shape and against
`record`/`adopt`'s `rehash=True`; `broken_drift` into `_receipt_evidence` and
the update gate; the `BaseException` put-back into `remove_paths`/`remove_proven`
and `setup.py`'s `Aborted.`; `_quarantined` into `plan_removal.yourself` and
`classify_tools`; `_skills_unsaved` across `refresh_skills` and the pass's
commit (both under `self._lock`, so the RR3-03 race is closed, not narrowed);
the resolved-path shim compare into `status.is_installed` and into the pass's
`resolve_pnpm`; `GuardedPopen` against `installer/run.py`'s `subprocess.Popen`
attribute lookup (patched, not imported by name) and the PATH strip against
the `uv` stub `test_tweaks.py` needed because `~/.local/bin` is now off PATH.
I ran the 11 touched test modules (green) and the full `make test` (4637
passed, 4 skipped, 95.98 % coverage, rc=0) in a scratch HOME; CI is green
through bd4de5b (HEAD adds a docs commit). Three reproductions ran under the
scratchpad only (one bash, two Python). No install, no write under the real
HOME. `git diff --check` is clean; the diff adds no `noqa`, `type: ignore`,
`pyright: ignore`, `nosec`, skip or xfail.

Of the 15 round-3 ids, 14 are closed and one is partial (IN3-04: the
ordering half is closed as RR3-03, the cosmetic re-show half is unchanged;
table below). L-19-31 holds as written: a dir is proven by the sha256 of one
key file that now must resolve inside the directory, dir drift is unproven
and never BROKEN or update-refused, file/link drift stays BROKEN, and a dir is
removed by rename to a quarantine sibling, re-hash there, then delete, with
the tree put back on any catchable interruption and a surviving sibling listed
for the user.

Two new defects, both introduced by this round and both reproduced:
`write_tester_path` now writes `eval "$( shellenv)"` into the tester's rc
files because `${BREW_BIN}` sits inside a single-quoted `exec_tester` body
(WR4-01); and `real_binary`'s retry resolves every PATH entry with
`Path.resolve()`, which on Python 3.11/3.12 raises `RuntimeError` on a
looping entry and kills the refresh pass with no error shown (WR4-02). One
Info: the receiptless layout branch of `plan_removal` ignores `verify` (IN4-01;
refusal direction only). The other lanes' round-4 claims are verified in the
cross-lane table.

## Closure table (round 3)

Every row was re-checked against the current source at b714868. "Pinned by"
names tests in the diff that I read and ran.

### 19-REVIEW-3.md (my previous report)

| ID | Item | Verdict | Evidence at HEAD | Pinned by |
|----|------|---------|------------------|-----------|
| WR3-01 | refresh pass hashes every layout-proven member on every pass (J3) | CLOSED | `installer/receipts.py:495-518`: `_file_fingerprint` reads the `(str(path), size, mtime_ns)` memo under `_MEMO_LOCK` unless `rehash=True`, and stores the digest it computes; same key shape as `_file_matches` (`:568`). `record` (`:274-286`) and `adopt` (`:318`) pass `rehash=True`, so no receipt is ever written from the memo. The layout branch of `plan_removal` (`installer/uninstall.py:182-183`) still calls `fingerprint` without `rehash`, so a pass costs one `lstat` after the first hash (D-08). | `tests/test_receipts.py` `test_fingerprint_hashes_an_unchanged_file_once_per_session`, `test_dir_key_file_is_hashed_once_per_session`, `test_record_and_adopt_never_trust_the_memo` |
| IN3-01 | `_safe_key` does not stop an intermediate-symlink escape; docstring/T-19-104 overclaim (J1) | CLOSED | `installer/receipts.py:404-418` `_key_file`: `target.resolve(strict=True).is_relative_to(directory.resolve(strict=True))`, `None` on `OSError`/`RuntimeError`/`ValueError` (dangling, loop). Used by `fingerprint` (`:476-479`) and `matches` (`:543-544`); `_remove_dir` re-checks under the quarantine root via `replace(artifact, path=quarantine)` (`uninstall.py:481`), so an absolute link to the backup tree fails there too. `_safe_key` docstring `:386-394` and the module docstring `:8-9` now state the division of labour. | `tests/test_receipts.py` `test_key_through_an_escaping_symlink_is_no_proof[abs\|rel]`, `test_key_through_a_symlink_that_stays_inside_still_proves`, `test_key_through_a_symlink_loop_never_raises`; `tests/test_uninstall.py` `test_remove_paths_refuses_a_replacement_keyed_through_an_escaping_symlink`, `test_plan_removal_never_proves_a_dir_whose_key_escapes` |
| IN3-02 | shim look-through compares PATH entries textually (J6) | CLOSED | `installer/guards.py:352-356`: `Path(found).parent.resolve() == shim_dir.resolve()`; `real_binary`'s retry (`:321-329`) drops every entry whose resolved path is the managed dir. The sentinel check (`is_our_shim`) is unchanged, so a foreign file in an aliased dir is still never looked through. The resolve the retry now performs is the source of WR4-02. | `tests/test_guards.py` `test_look_through_shim_matches_the_shim_dir_by_resolved_path`, `test_real_binary_drops_every_spelling_of_the_managed_dir` |
| IN3-03 | a crash between the quarantine rename and the delete leaves a hidden sibling nothing lists (J2) | CLOSED | `installer/uninstall.py:114-133` `_quarantined` globs `.<name>.*<_QUARANTINE_SUFFIX>` beside every dir artifact; `:185-189` feeds it into `plan_removal.yourself`, so the CLI preview and `classify_tools` (`:401-405`) name it with the existing "remove it yourself" copy. Listed only, never deleted (L-19-06): `remove_proven` deletes only `fresh.artifacts`. | `tests/test_uninstall.py` `test_a_leftover_quarantine_sibling_is_listed_to_remove_yourself` (leftover survives a later removal of the reinstalled tool) |
| IN3-04 | skill worker re-shows a pass's cache warning / can lose its own (J5) | PARTIAL | The ordering half (a later pass clears the warning while the skill answers were never persisted) is closed as RR3-03 below. The re-show half is unchanged: the version worker snapshots `service.warning` after `refresh` (`installer/catalog_tui.py:419-425`) and the skill worker snapshots it again after `refresh_skills` (`:437-441`), and `refresh_skills` neither clears `_warning` on its own successful save (`version_status.py:1043-1044` resets only `_skills_unsaved`) nor on its early return (`:1015-1016`), so the skill worker re-posts whatever the pass left. 19-40 scoped this out ("the IN3-04 ordering half is the same race"). Residual is cosmetic: identical text, nothing hidden, states published either way. Not re-raised as a finding. | `tests/test_version_status.py` `test_a_version_pass_persists_unsaved_skill_answers_before_clearing_the_warning` (ordering half) |

### 19-REVIEW-opencode-plan-review-3.md

| ID | Item | Verdict | Evidence at HEAD | Pinned by |
|----|------|---------|------------------|-----------|
| RR3-01 | intermediate symlink lets an external key authorize deletion of a replacement dir (J1) | CLOSED | see IN3-01. The quarantine re-check runs `_key_file(quarantine, key)`, so the replacement tree's `Contents -> /…/Demo.backup.app/Contents` resolves outside the captured root and `matches` is False; `_remove_dir` puts the tree back and refuses (`uninstall.py:495-497`). | `tests/test_uninstall.py` `test_remove_paths_refuses_a_replacement_keyed_through_an_escaping_symlink` (absolute link, survives the rename) |
| RR3-02 | Ctrl+C after the capture strands an intact install under a random name (J2) | CLOSED | `installer/uninstall.py:480-494`: the re-check and `rmtree` run inside `try/except BaseException`; `_put_back` renames the remainder to its path, then the interruption is re-raised (the CLI prints `Aborted.` with the tree back in place). A failed put-back raises the `OSError` naming both paths with the interruption kept as `__context__` (`:491-493`). SIGKILL is not promised; the sibling is listed (IN3-03). `sys.exception()` is fine: `requires-python = ">=3.11"`. | `tests/test_uninstall.py` `test_remove_paths_puts_the_tree_back_when_interrupted[after_capture\|at_delete]`, `test_an_interrupted_removal_that_cannot_put_back_names_the_quarantine` |
| RR3-03 | a later version save erases the warning without saving fresh skill answers (J5) | CLOSED | `installer/version_status.py:933` `_skills_unsaved`; `refresh_skills` sets it in the save's `except`/`else` (`:1038-1044`) under `self._lock`; the pass's commit (`:1688-1702`), also under `self._lock`, passes `skills={…self._skills…}` when the flag is set and clears both the flag and `_warning` only in its `else`. Because both sides hold the same lock across the I/O, the pass cannot read a stale flag and then clear a warning set during its save. `save_version_cache(skills=None)` preserves the on-disk section (`version_cache.py:227-233`), so a flag-less save still never erases answers. | `tests/test_version_status.py` `test_a_version_pass_persists_unsaved_skill_answers_before_clearing_the_warning` |

### 19-REVIEW-ponytail-3.md

| ID | Item | Verdict | Evidence at HEAD | Pinned by |
|----|------|---------|------------------|-----------|
| P3-01 | suite fork bomb guarded at one seam, trigger still on PATH (J4) | CLOSED | `tests/conftest.py:199-207`: every PATH entry resolving under the real HOME or `/run/user` is removed for every test; `:37-39, 49-84` `assert_not_host_toolchain` refuses a node-family or `brew` argv whose resolved binary is outside pytest's base temp; `:87-109` `GuardedPopen` replaces `subprocess.Popen` per test (installer/run.py reads `subprocess.Popen` by attribute, `run.py:269`, so the patch takes effect; `asyncio`'s transport does too). Shell strings are not inspected, as the docstring says; the PATH strip covers bare names there. The absolute host `brew` in the two extracted e2e functions became `BREW_BIN` with a stub (`tests/test_container_e2e_receipts.py:256-269, 323, 396`). The regression this introduced in a third function is WR4-01; the strip's own `Path.resolve()` shares WR4-02's loop hazard on a developer host. | `tests/test_sandbox.py` (3 tests); `tests/test_tweaks.py` `_plant_uv_stub` (needed because `~/.local/bin/uv` is now off PATH); full suite green |
| P3-02 | the BROKEN-drift rule written twice; gate re-hashes dir keys it ignores (J7) | CLOSED | `installer/receipts.py:583-594` `broken_drift` skips dirs before any hash; callers `installer/version_status.py:1275` and `installer/update.py:516`. `grep 'type != "dir"' installer/` finds only the predicate and `remove_paths`'s `rehash=` choice. | `tests/test_receipts.py` `test_broken_drift_skips_dirs_and_never_hashes_their_key_file`; existing `_receipt_evidence`/update-gate tests |
| P3-03 | a malformed `.skill-lock.json` can crash the skill probe (J8) | CLOSED | `installer/skill_lifecycle.py:725-729`: `json.loads(raw_bytes)` under `except (ValueError, RecursionError)`; `UnicodeDecodeError` and `JSONDecodeError` are `ValueError`s. | `tests/test_skill_lifecycle.py` `test_skills_lock_deep_nesting_or_bad_bytes_is_unknown` |
| P3-04 | a dir key file is hashed three times on removal (J9) | CLOSED | `installer/uninstall.py:518` `receipts.matches(artifact, rehash=artifact.type != "dir")`; a file keeps its RR-02 re-hash; a receipt-proven dir is hashed at `_receipt_proof(verify=True)` and in the quarantine (a receiptless one only in the quarantine: IN4-01). | `tests/test_uninstall.py` `test_remove_proven_hashes_a_dir_key_file_twice_not_three_times` |
| P3-05 | interrupted dir removal leaves a hidden tree nothing lists (J2) | CLOSED | see IN3-03 | see IN3-03 |
| P3-06 | reader parses the digest triple twice; `_safe_key` forces a `cast` (J9) | CLOSED | `installer/receipts.py:636-657`: one sha256/size/mtime_ns parse after the `link` return, then the `file` return, then `_safe_key(key)` as a `TypeGuard[str]` (`:386`) with no `cast`; `fingerprint` drops its `key is None` check (`:473`). `kind` is still validated first (`:617-618`). | `tests/test_receipts.py` old-shape / invalid-artifact tests (unchanged, green) |
| P3-07 | leftovers: nested `one()`, unguarded `reasons[0]` in `u`, hard-coded "1 MiB", docstring wrap (J9) | CLOSED | `receipts.py:274-286` fingerprints inline; `catalog_tui.py:807-811` `detail` is conditional, matching the execute screen; `terminal_shell.py:269-271` derives the size from `_CONFIG_MAX_BYTES`; `receipts.py:264-267` rewrapped (one odd break remains at "OSError says / what happened to it" — cosmetic). | `tests/test_catalog_tui.py` `test_u_on_a_broken_row_without_a_reason_still_refuses` |

Counting rule for the frontmatter `prior_*` keys: the 15 round-3 ids above
(WR3-01, IN3-01..04, RR3-01..03, P3-01..07), 12 distinct after dedupe
(RR3-01 = IN3-01, RR3-02 = IN3-03 = P3-05, RR3-03 = IN3-04). Closed 14.
Partial 1 (IN3-04). Open 0. The accepted/deferred set (G15, G21/WR-03,
IN-02/03/06, P19-07 residual, vendor-updated `.app` not removable until
reinstall) was not re-raised.

## Cross-lane claims (round 4), verified independently

| Lane id | Claim | Verdict | Evidence |
|---------|-------|---------|----------|
| RR4-01 / P4-01 | unexpanded `${BREW_BIN}` in the single-quoted `write_tester_path` payload | CONFIRMED = WR4-01 | `scripts/container-e2e-verify.sh:169-186` single-quoted body, `:171` and `:179` substitutions; reproduced below. Found independently before the coordinator's note. |
| RR4-02 | receiptless layout branch ignores `verify=True`, so deletion-time planning reuses the preview's cached digest | FACT CONFIRMED, NOT A DEFECT IN OUTCOME; recorded as IN4-01 | `installer/uninstall.py:182-183` passes no `rehash`. The quarantine re-hash (`:481`) still compares the captured bytes with that digest, so a swap with restored stat is refused and put back; removability of a receiptless tool is structural (`is_still_proven`, `:181`), never content-based, so no incorrect deletion is reachable. One-line alignment in IN4-01. |
| RR4-03 / P4-02 | `Path.resolve()` on a looping PATH entry raises `RuntimeError` and aborts the refresh | CONFIRMED = WR4-02 | `installer/guards.py:324-328`; uncaught through `version_status.py:1433-1437` (`except (CommandError, OSError)`), `:1446`, `:1523-1526`, `ui_common.py:54`, `catalog_tui.py:414-428`; reproduced on the venv's 3.12.12 below. |
| IN3-04 partial | separate warning snapshots in the two catalog workers | CONFIRMED | `installer/catalog_tui.py:419-425` and `:437-441`; closure row updated to PARTIAL (cosmetic residual, not a finding). |

## Narrative Findings (AI reviewer)

Fresh ids (WR4-/IN4-). Only these count in the frontmatter `findings` block.

## Warnings

### WR4-01: `write_tester_path` substitutes `${BREW_BIN}` inside a single-quoted `exec_tester` body, so the tester's rc files get `eval "$( shellenv)"`

**File:** `scripts/container-e2e-verify.sh:171` and `:179` (inside the single-quoted argument that opens at `:169` and closes at `:186`); contrast `:320` and `:343`, where the same substitution sits in double-quoted bodies and is correct. Introduced by 1664d9d (19-39 Task 2).

**Issue:** `exec_tester` runs `su - tester -c "$1"` and its own comment
(`:82-83`) says the string is "expanded by the container shell only". The
two `write_tester_path` sites are inside `'…'`, so the host shell passes
`${BREW_BIN}` through literally and the tester's login shell expands it
against its own (reset) environment, where `BREW_BIN` is unset. The lines
appended to `~/.bash_profile` and `~/.bashrc` become `eval "$( shellenv)"`:
every login shell for `tester` then prints `shellenv: command not found` and
brew's `shellenv` never reaches PATH from the rc files, which is the one job
this function has (its comment: "PATH must live in .bash_profile"). The
dedupe guard `grep -q linuxbrew` never matches the broken line, so each run
of `write_tester_path` appends another copy. The old hard-coded path did not
have this problem because it contained no variable.

**Reproduced** with the harness's own extraction (`_function("write_tester_path")`,
`BREW_BIN=<stub>`, an `exec_tester` that runs `env -i HOME=$SCRATCH bash -c "$1"`,
two calls): `.bash_profile` reads

```
eval "$( shellenv)"
case ":${PATH-}:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin${PATH:+:$PATH}";;esac
eval "$( shellenv)"
```

and `bash -lc 'echo $PATH'` prints `shellenv: command not found` twice.
The functional passes still complete because `assert_receipt_ready_for_removal`
and `run_setup_as_tester` eval brew themselves (`:320, :343`), and
`sync_workspace` (`:203`) kept the literal path; the damage is the tester's
rc files and the stderr noise in every `exec_tester` call after bootstrap.
`test_extracted_functions_never_name_the_host_brew` covers only the two
double-quoted functions, so it did not see this.

**Fix:** give the inner shell the value by prefixing the single-quoted body
with a host-expanded assignment, and extend the test to the third function:

```bash
# scripts/container-e2e-verify.sh, write_tester_path
  exec_tester "BREW_BIN=${BREW_BIN}
"'touch ~/.bash_profile
if ! grep -q linuxbrew ~/.bash_profile 2>/dev/null; then
  printf "%s\n" "eval \"\$(${BREW_BIN} shellenv)\"" >> ~/.bash_profile
fi
…'
```

(`${BREW_BIN}` inside the body is then expanded by the tester shell from the
prefix; the dedupe `grep -q linuxbrew` matches again because the real value
contains `linuxbrew`.) In `tests/test_container_e2e_receipts.py`, add
`"write_tester_path"` to the loop in `test_extracted_functions_never_name_the_host_brew`
and add one test that runs the extracted function with the `_brew_stub` and a
scratch-HOME `exec_tester` (as the two existing run tests do) and asserts
`.bash_profile` contains `f"eval \"$({stub} shellenv)\""` and not `"$( shellenv)"`.

### WR4-02: `real_binary`'s retry resolves every PATH entry with `Path.resolve()`, which raises `RuntimeError` on a looping entry under Python 3.11/3.12 and kills the refresh pass with no error shown

**File:** `installer/guards.py:324-328` (the retry: `managed = shim_dir.resolve()`, `Path(entry).resolve() != managed`); reached from `resolve_pnpm` (`:376`) → `installer/manager_versions.py:173, 205` / `installer/pnpm_globals.py:428, 448` → the pass's `_read_outdated` at `installer/version_status.py:1433-1436`, whose catch at `:1437` is `(CommandError, OSError)` only, and again from `_partial_manager_failure` (`:1446`, `:1493`) with no catch; `refresh` re-raises (`:1523-1526`); `ui_common.run_live` catches `(OSError, CommandError, ShellrcRefusal)` (`ui_common.py:54`); the version worker's `finally` posts `VersionStatusRefreshed(error=None, warning=None)` (`installer/catalog_tui.py:414-428`). Second site with the same hazard: `tests/conftest.py:199-207` (the PATH strip, developer host only). Introduced by 2443ae0 (19-41); the previous code compared strings and made no syscall.

**Issue:** `Path.resolve(strict=False)` raises `RuntimeError("Symlink loop
from …")` on 3.11 and 3.12 (pathlib calls `stat()` after `realpath` and
converts `ELOOP`); only 3.13+ returns silently. The project supports
`>=3.11` (`pyproject.toml:5`, ruff `py311`, pyright `3.11`) and this
checkout's venv is 3.12.12. The retry runs whenever `pnpm` is absent from
PATH (`found is None`) or the installer's own shim won, so on any host
without pnpm a single looping PATH entry (a self-referential `~/bin`, a
stale dotfile link) makes the first refresh pass raise. Nothing between the
retry and the worker catches `RuntimeError`: `refresh` records the failure
and re-raises, `run_live` lets it through, and the worker's `finally` posts
a refresh-finished message with `error=None`, so the screen clears
`version_refreshing` and every row stays at its pre-pass state with no
message; the exception then dies in the Textual worker (`exit_on_error=False`).
`u` and the uninstall view, which read the published states, inherit the
same blank. The same `resolve()` in `look_through_shim` (`:354`) is safe:
`found` exists, so its parent cannot be a loop.

**Reproduced** on the venv (3.12.12): a scratch entry `loopbin -> loopbin`,
`real_binary("pnpm", shim_dir=<scratch>/bin, path_value="<loop>:/usr/bin", lookup=lambda n, p: None)`
→ `RuntimeError: Symlink loop from '…/loopbin'`; the pre-19-41 string compare
over the same PATH returns both entries; `/usr/bin/python3.14`:
`Path(loop).resolve()` → no raise. `os.path.realpath(loop)` on 3.12 returns
the path unchanged and raises nothing.

**Fix:** compare with the loop-safe `os.path.realpath` instead of
`Path.resolve()` (non-strict `realpath` never raises on a loop on 3.11-3.14;
a looping entry then simply fails to match and stays in the list, where
`which` skips it as before):

```python
# installer/guards.py, real_binary
managed = Path(os.path.realpath(shim_dir))
rest = [
    entry
    for entry in path_value.split(os.pathsep)
    if entry and Path(os.path.realpath(entry)) != managed
]
```

and, for symmetry, `Path(os.path.realpath(Path(found).parent)) == Path(os.path.realpath(shim_dir))`
in `look_through_shim`. Apply the same substitution to the two `resolve()`
calls in `tests/conftest.py:203-205`. Add
`test_real_binary_survives_a_looping_path_entry` in `tests/test_guards.py`: a
`loopbin -> loopbin` entry ahead of a fake pnpm dir, `real_binary` returns the
fake (this fails today on 3.11/3.12 with the `RuntimeError`).

## Info

### IN4-01: the receiptless layout branch of `plan_removal` ignores `verify`, so `remove_proven`'s "re-hash at deletion time" holds for receipts only

**File:** `installer/uninstall.py:182-183` (`receipts.fingerprint(opt, "dir", key=receipts.link_key(opt, link))`, no `rehash`); docstring claims at `:126-127` and `remove_proven` `:534-537`; 19-44's "hashed at the fresh proof and once more inside the quarantine".
**Issue:** Under `remove_proven`'s `plan_removal(verify=True)` a receiptless
dir's digest comes from the session memo whenever the key file's stat tuple
is unchanged, so the "fresh proof" may carry a digest from an earlier pass.
Outcome today is safe: `_remove_dir` re-hashes the captured tree against that
digest (`:481`), so bytes swapped with size and mtime restored are put back
and refused, and a receiptless tool's removability is structural
(`is_still_proven`, `:181`), never content-based, so no incorrect deletion is
reachable. The gaps are the docstrings and the refusal text ("changed since
the preview" for a change that happened before it).
**Fix:** `receipts.fingerprint(opt, "dir", key=receipts.link_key(opt, link), rehash=verify)`.
The pass still calls `plan_removal` without `verify`, so WR3-01's memo is
untouched; a layout twin of `test_remove_proven_hashes_a_dir_key_file_twice_not_three_times`
would then count two hashes as the receipt case does.

## Checked and fine

- `_remove_dir`'s `except BaseException` re-raises after a successful
  put-back, so a Ctrl+C reaches `setup.py`'s `Aborted.` with the tree at its
  path. In the TUI, SIGINT is a key binding on the main thread, not a
  `KeyboardInterrupt` on the worker, so the branch is mostly `SystemExit`/never
  there. `raise put_back_error from None` suppresses the chained display but
  keeps the interruption as `__context__` (asserted by the test); the OSError
  text names both paths.
- Receipt order for an archive is (dir, link): the dir is quarantined,
  re-hashed and deleted first; the link still matches by `readlink` and is
  unlinked. Layout order (link, dir) works too; neither proof depends on the
  other.
- `_file_fingerprint` stores the memo even under `rehash=True`, so a `record`
  refreshes the session's digest for that stat tuple; `_file_matches` under
  `rehash=True` neither reads nor writes it. Both memos share one lock.
- `_key_file` + `link_key`: receipts never carry a symlink component in a key,
  because `link_key` records the strictly resolved member path relative to the
  resolved dir; `Contents/Info.plist` is real directories in any bundle. So the
  intermediate-symlink refusal in the quarantine can only hit a forged or
  hand-edited receipt, never a shipped layout. `_key_file` itself catches the
  3.11/3.12 `RuntimeError` for loops (strict mode raises it on every version).
- `_quarantined` on a missing parent (`~/Applications` on Linux) yields nothing
  (`Path.glob` returns empty when the parent is not a directory); the glob
  matches dotfiles (pathlib, unlike the shell). A dotted tool name could list a
  sibling of `foo.bar` under `foo`; both are leftovers to remove anyway.
- `invalidate` saves with `skills=None` (preserves the on-disk section) and
  does not touch `_warning`; a later successful `refresh_skills` save resets
  `_skills_unsaved` and the next pass commit clears the warning. No path clears
  the warning while fresh answers are unsaved.
- `GuardedPopen.__init__(self, args, *pargs, **kwargs)` accepts
  `subprocess.run`'s positional `args` and a keyword `args=`; `subprocess.run`
  resolves `Popen` from its module globals, so the per-test patch applies.
  `tmp_path` is always under the worker's `getbasetemp()`, so the allowed
  root is right under xdist.
- `json.loads(bytes)` in `_skills_lock_skills` now also accepts a UTF-8 BOM
  and UTF-16/32 lock files that the manual `decode("utf-8")` refused; benign
  widening of what reads as a lock.
- `test_shell_scripts_path.py`'s three line numbers (204, 321, 344) match the
  two-line shift from the `BREW_BIN` comment and assignment; the test is green.
- `broken_drift(receipt, rehash=True)` in the update gate hashes files only;
  `_receipt_evidence` calls `broken_drift` then `drifted`, so the dir is
  stat-checked once per pass (memo), never hashed twice.
- `_read_artifact` still validates `kind` before the shared triple parse, so a
  foreign `type` can never fall through to the `dir` constructor.

---

_Reviewed: 2026-10-17T05:33:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
