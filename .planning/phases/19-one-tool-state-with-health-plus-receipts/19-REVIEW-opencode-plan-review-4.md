# Phase 19 re-review round 4 (opencode, router-env/my-plan-review)

## Closure of prior findings

Using `ponytail-review` to re-review `23d832e..HEAD` over `installer`, `setup.py`, `scripts` and `tests`. Load assumed: one local CLI/TUI user with concurrent refresh workers. L-19-31 is treated as binding, including acceptance of recreated directories with identical key-file bytes.

| Finding id | Status (closed/partial/open) | Evidence file:line |
|---|---|---|
| **RR3-01 — external key authorizes replacement-directory deletion** | **closed** | `_key_file` requires resolved containment: `installer/receipts.py:404–418`. Both fingerprinting and matching use it: `475–478`, `540–544`, including the quarantine recheck at `installer/uninstall.py:481`. Absolute and relative escapes are covered at `tests/test_receipts.py:890–910`; replacement-after-check coverage is at `tests/test_uninstall.py:2416–2451`. |
| **RR3-02 — cancellation strands quarantined installation** | **closed** | Verification/deletion exceptions, including catchable cancellation, restore the remainder before propagation: `installer/uninstall.py:480–494`. Failed restoration names the retained location through `443–451`. Regression coverage: `tests/test_uninstall.py:2542–2606`. |
| **RR3-03 — version save clears warning without persisting skill answers** | **closed** | Failed skill saves set `_skills_unsaved`: `installer/version_status.py:1038–1044`. A later version commit includes those answers before clearing the obligation and warning: `1690–1703`, under the publication lock at `1644`. Regression: `tests/test_version_status.py:2754–2792`. |
| **WR3-01 — unchanged layout key files hashed every refresh** | **closed** | `_file_fingerprint` now consults the `(path, size, mtime_ns)` memo: `installer/receipts.py:495–511`. Recording and adoption explicitly bypass it: `278–282`, `319`. A missed deletion-time caller is reported separately as RR4-02. |
| **IN3-01 — intermediate symlink escapes key containment** | **closed** | Containment is enforced rather than merely documented: `installer/receipts.py:404–418`, `475–478`, `540–544`. Escaping, contained and looping symlinks are covered at `tests/test_receipts.py:890–946`. |
| **IN3-02 — alternate PATH spelling prevents shim look-through** | **closed** | Managed-directory recognition and retry filtering compare resolved paths: `installer/guards.py:324–328`, `350–355`. Alias/trailing-slash regressions: `tests/test_guards.py:1105–1125`. An invalid-PATH regression introduced by this resolution is RR4-03. |
| **IN3-03 — killed removal leaves invisible quarantine sibling** | **closed** | `_quarantined` discovers matching siblings without authorizing deletion: `installer/uninstall.py:114–133`; `plan_removal` includes them in `yourself`: `188–193`. Coverage verifies visibility and preservation: `tests/test_uninstall.py:2475–2500`. |
| **IN3-04 — skill/version warning publication races** | **partial** | Unsaved-answer persistence is fixed, but workers still capture separate warning snapshots at `installer/catalog_tui.py:423–428`, `439–443`. A clean version message delayed until after a failed skill message clears the warning at `470–474` while the service still reports failure. Conversely, `453–454` can re-show an obsolete warning. This existing cosmetic residual is not counted as a new finding. |
| **P3-01 — inherited Volta shims remain executable by tests** | **closed** | The reported trigger is removed by clearing overrides and stripping resolved real-HOME and `/run/user` PATH entries: `tests/conftest.py:193–207`. Direct named toolchain launches are additionally guarded at `62–83`, `89–108`. Scratch-binary coverage: `tests/test_sandbox.py:13–47`. |
| **P3-02 — duplicated BROKEN rule and ignored directory hashes** | **closed** | `broken_drift` skips directories before matching: `installer/receipts.py:583–595`. Health and update gating both use it: `installer/version_status.py:1275–1279`; `installer/update.py:511–518`. |
| **P3-03 — deeply nested skill-lock JSON escapes the reader** | **closed** | The capped bytes are parsed under `except (ValueError, RecursionError)`: `installer/skill_lifecycle.py:716–729`. Deep-nesting and invalid-byte regressions: `tests/test_skill_lifecycle.py:821–827`. |
| **P3-04 — redundant third directory hash during removal** | **closed** | The middle check no longer forces a directory rehash: `installer/uninstall.py:515–518`; quarantine still forces one at `481`. Two-hash coverage: `tests/test_uninstall.py:2503–2527`. |
| **P3-05 — undisclosed interrupted-removal tree** | **closed** | Surviving quarantine siblings enter the manual-removal list: `installer/uninstall.py:114–133`, `188–193`; they are not made removable. Coverage: `tests/test_uninstall.py:2475–2500`. |
| **P3-06 — duplicated digest-triple parsing and key cast** | **closed** | File/directory digest fields share validation: `installer/receipts.py:636–654`; `_safe_key` is a `TypeGuard[str]` at `386–401`, eliminating the reader’s cast. |
| **P3-07 — small leftovers, including reasonless-BROKEN crash** | **closed** | Recording is inline and its docstring repaired: `installer/receipts.py:258–286`. Catalog update refusal guards empty reasons: `installer/catalog_tui.py:807–812`, matching `installer/execute_screen.py:554–556`. Terminal refusal text derives its cap at `installer/terminal_shell.py:269–271`. |

## New findings

### RR4-01 [MEDIUM] Tester shell initialization loses `BREW_BIN`

- **File:** `scripts/container-e2e-verify.sh:169–179`; shell boundary at `82–85`.
- **Problem:** `write_tester_path` sends a single-quoted command to the tester’s login shell. `${BREW_BIN}` therefore expands inside that shell, but the variable is assigned only in the host script and is not passed through `ct exec … su - tester`. A scratch reproduction produced `eval "$( shellenv)"` in both rc files. Subsequent shells report `shellenv: command not found` and do not initialize Homebrew. Re-running the writer appends another broken line because it contains no `linuxbrew` for the existing duplicate guard to recognize.
- **Fix:** Restore the literal container brew path in these two single-quoted-payload lines, or explicitly bind the selected `BREW_BIN` inside the tester command. Add a scratch-shell regression that checks the generated initialization, not only the PATH guard.

### RR4-02 [MEDIUM] Receiptless deletion-time verification reuses the preview’s cached digest

- **File:** `installer/uninstall.py:179–183`, `543–546`; memo lookup at `installer/receipts.py:505–511`.
- **Problem:** The receiptless layout branch ignores `verify=True` when fingerprinting its directory. Previewing an archive caches its key digest. Replace the binary with different, same-length bytes and preserve its mtime: deletion-time planning still returns the old digest. `remove_proven` then unlinks the CLI link first, but the authoritative quarantine rehash rejects and restores the directory. A scratch reproduction confirmed that the binary survived while its CLI link was removed. This is a partial uninstall caused by an obsolete “fresh” proof, not L-19-31’s accepted identical-key case.
- **Fix:** Pass `rehash=verify` to the directory fingerprint at `installer/uninstall.py:180`. Cover the receiptless same-size/restored-mtime replacement case.

### RR4-03 [MEDIUM] A looping PATH entry now aborts the entire refresh

- **File:** `installer/guards.py:324–328`; refresh consumer at `installer/version_status.py:982–986`, `1570–1578`.
- **Problem:** The retry now resolves **every** PATH entry without handling resolution errors. With the managed pnpm shim first, a real pnpm second, and a self-looping directory symlink anywhere later in PATH, Python 3.12 raises `RuntimeError` at line 328. The base revision successfully found the real pnpm with the same setup. A scratch service refresh reproduced the exception and published no state. The TUI’s `run_live` does not catch `RuntimeError` (`installer/ui_common.py:52–55`), so this valid earlier executable is lost because of an unrelated unusable PATH entry.
- **Fix:** Skip PATH entries whose resolution raises `OSError` or `RuntimeError`, while continuing to exclude successfully resolved aliases of the managed directory. Add a regression with a looping entry after the real binary.

## Summary

**Prior findings:** 14 closed, 1 partial, 0 open.

| Severity | New findings |
|---|---:|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 3 |
| LOW | 0 |
| **Total** | **3** |

Verification: **34 targeted tests passed** under `-n auto` with scratch HOME/PATH; all 20 changed Python files parsed; Bash syntax and scoped `git diff --check` passed. The scoped diff adds **zero suppression, skip or xfail directives**.

Not checked: full quality gates, full pytest, containers or live macOS behavior; no source edits or installs were performed.  
Remaining risk: broken tester initialization, partial receiptless removal, and refresh failure on malformed PATH entries require correction before approval.
