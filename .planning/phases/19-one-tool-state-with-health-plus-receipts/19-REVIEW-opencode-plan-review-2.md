# Phase 19 re-review (opencode, router-env/my-plan-review)

## Closure of prior findings

Reviewed `git diff e833961 HEAD -- installer setup.py scripts tests` and connected consumers. Duplicate findings across the four reports are consolidated under G1–G28. “Closed” refers to the original failure scenario; accepted or deferred findings remain open.

| Finding id | Status | Evidence file:line |
|---|---|---|
| **G1 — F1 / P19-01: file authorization escalates into recursive deletion** | **closed** | Authorized artifact types now reach deletion. Only directory artifacts enter `rmtree`; file/link artifacts use `unlink`: `installer/uninstall.py:79–101`, `405–422`, `440–443`. A different file-verification gap remains in RR-02. |
| **G2 — WR-04: replacement app bundle inherits directory proof** | **partial** | Directory fingerprints now record and compare device/inode: `installer/receipts.py:385–389`, `411–416`. This rejects an already-replaced bundle, but replacement between the final check and recursive deletion remains unsafe; see RR-01. |
| **G3 — CR-01: execute-screen update overwrites a drifted file** | **closed** | `UpdateService.run` refuses an installer-owned update when a readable, non-all-gone receipt fails forced rehashing, before dispatch: `installer/update.py:509–521`. Both catalog and execute-screen update routes use this service: `installer/catalog_tui.py:845`, `installer/execute_screen.py:778`. |
| **G4 — WR-01: manager update overwrites another method’s receipt** | **closed** | Receipt rewriting now requires installer ownership or an existing receipt of the same method kind: `installer/update.py:346–354`. |
| **G5 — F4 / P19-03: malformed receipt path aborts operations** | **closed** | Receipt decoding rejects embedded NUL and unencodable paths: `installer/receipts.py:469–476`. Fingerprinting and matching catch invalid-path `ValueError`: `390–391`, `438–439`. |
| **G6 — F5 / P19-05 / IN-01 / ponytail P5: memo confuses expected digests** | **closed** | The memo stores the observed digest, then compares it against each artifact’s expected digest. Forced verification bypasses the memo: `installer/receipts.py:426–437`. |
| **G7 — F2 / P19-02: publication during Status grouping crashes the TUI** | **closed** | Health is evaluated once per tool during grouping: `installer/catalog_tui.py:107–112`. Grouping, sorting and row cells reuse captured states: `561–606`. The reported duplicate-bucket insertion is eliminated. |
| **G8 — F3 / P19-06: stale skill answers produce fresh green marks; ponytail P1: completed unknown probes remain CHECKING** | **closed** | Missing/stale host reports return CHECKING before their configuration facts can settle health: `installer/version_status.py:1191–1208`. Fresh reports proceed without CHECKING, including all-unknown answers: `1210–1224`; unreadable present harnesses add notes at `1116–1123`. A separate partial-pass regression appears in RR-03. |
| **G9 — F6: skill worker overwrites newer project facts** | **closed** | The worker no longer performs an independent project scan; it rebuilds using the publishing pass’s scan and matching sequence: `installer/version_status.py:1037–1056`. The sequence restriction introduces RR-03. |
| **G10 — ponytail P2: all-missing artifacts leave permanent false BROKEN state** | **closed** | Refresh retires an unchanged receipt only after every artifact is conclusively absent: `installer/version_status.py:1249–1252`, `installer/receipts.py:324–358`. Empty receipts and inconclusive reads are retained. |
| **G11 — F7 / P19-08: terminal warnings disappear** | **closed** | Returned warnings become row-specific unchecked notes, without repair steps: `installer/version_status.py:1323–1329`. Terminal-to-row mapping includes Konsole → zsh: `609–613`. |
| **G12 — F8: special metadata file blocks refresh** | **closed** | The capped reader opens nonblocking, checks the opened descriptor for a regular file, and reads at most `cap + 1` bytes: `installer/atomic.py:118–147`. Receipt and skill metadata callers use it: `installer/receipts.py:164`, `installer/skill_lifecycle.py:478`, `827–831`. |
| **G13 — WR-02: PATH shim counts as installed tool** | **closed** | The PATH branch now excludes installer shims before returning presence: `installer/status.py:122–128`. |
| **G14 — WR-05: pi update hint omits `--ignore-scripts`** | **closed** | The hint uses the reviewed host-setup handoff, with an `--ignore-scripts` fallback: `installer/update.py:312–332`, `installer/host_setup.py:47–56`. |
| **G15 — ponytail P3: full refresh on every tier entry** | **open** | Explicitly accepted in `19-31-PLAN.md:218`. View entry still starts a whole-catalog refresh: `installer/catalog_tui.py:384–405`, `416–418`. |
| **G16 — ponytail P4: unused `inspect_skill_packs` projection** | **closed** | The unused projection was removed; production report collection remains at `installer/skill_lifecycle.py:929–950`. |
| **G17 — ponytail P6: precedence uses tuple identity** | **closed** | Other fact groups are now selected by Health value rather than tuple identity: `installer/version_status.py:232–239`. |
| **G18 — ponytail P7: irrelevant artifact fields retained by decoder** | **closed** | Each decoded artifact now retains only fields used for its type: `installer/receipts.py:480–498`. |
| **G19 — F9 / P19-13: generated shell paths break on spaces** | **partial** | Interpreter quoting is fixed at `tests/test_container_e2e_receipts.py:253–260`; workspace assignment is quoted at `299`. Its downstream nested `cd` remains unquoted: `scripts/container-e2e-verify.sh:315–319`; see RR-06. |
| **G20 — execute-screen suppression cleanup** | **closed** | The four private-field suppressions were removed; replacement assertions inspect rendered progress: `tests/test_execute_screen.py:4428`, `4482–4487`. No genuinely new quality-gate suppression comments were identified in the scoped diff. |
| **G21 — WR-03: adoption note names the wrong `r` action** | **open** | The note still says “reinstall with r”: `installer/version_status.py:605–606`. Catalog `r` still accepts recommendations: `installer/catalog_tui.py:316–317`, `748–772`. Acceptance in `19-31-PLAN.md:224` does not correct the current instruction. |
| **G22 — IN-01…IN-06: informational findings** | **partial** | IN-01 is closed under G6. IN-04’s smoke claim is corrected at `installer/engine.py:246–257`; IN-05 now propagates receipt-check failure explicitly at `scripts/container-e2e-verify.sh:480`. IN-02, IN-03 and IN-06 are explicitly deferred in `19-31-PLAN.md:225`, not closed. |
| **G23 — P19-04: inaccessible receipts directory aborts operations** | **closed** | Failed access counts as present-but-untrusted: `installer/receipts.py:307–321`. Removal planning suppresses fallback, and refresh emits an unreadable-receipt note: `installer/uninstall.py:127–136`, `installer/version_status.py:1243–1248`. |
| **G24 — P19-07: absent host overrides another host’s unknown result** | **partial** | The unreadable-harness explanation is preserved at `installer/version_status.py:1116–1123`, but fresh mixed absent/unknown answers still become MISSING because presence requires a `"present"` answer: `1210–1224`. The revised plan accepts this; it does not preserve the original requirement to keep inconclusive presence distinct from confirmed absence. |
| **G25 — P19-09: canonical duplicate versions lose their explanations** | **partial** | Duplicate reasons are now emitted and direct canonical repair steps suppressed: `installer/skill_lifecycle.py:879–901`. Downstream partial-harness handling can recreate an install step; see RR-04. |
| **G26 — P19-10: unreadable project install is treated as empty** | **closed** | Unreadable runtime content is retained as unchecked evidence and excluded from empty-install/reinstall classification: `installer/skill_lifecycle.py:431–448`, `569–588`. |
| **G27 — P19-11: repo detection follows intermediate `.planning` symlink** | **closed** | `.planning` itself must now be a real directory before its config is checked: `installer/skill_lifecycle.py:392–394`. |
| **G28 — P19-12: state tests inspect real HOME locations** | **partial** | The autouse fixture redirects HOME, closing ordinary `~` expansion: `tests/conftest.py:102–116`. Inherited absolute manager-home overrides remain unsandboxed; see RR-05. |

## New findings

The removal findings below are remaining safety holes in the closure implementation, not newly introduced recursive-delete behavior.

### RR-01 [HIGH] Directory identity is checked separately from the object recursively deleted

- **File:** `installer/uninstall.py:416–420`; `installer/receipts.py:411–416`.
- **Problem:** `matches()` validates the directory’s device/inode, then `rmtree()` independently opens the pathname. A vendor updater can rename the verified bundle aside and replace it between those operations. Recursive removal then deletes the replacement bundle, although its identity never matched the receipt. The added identity check therefore does not fully protect the removal operation.
- **Fix:** Capture the directory before recursive deletion—for example, rename it to a unique quarantine path and validate that captured directory’s identity before removing it. Preserve and report a mismatching captured tree. Add a deterministic replacement between the final match and recursive removal.

### RR-02 [HIGH] The final removal check accepts changed raw bytes with restored metadata

- **File:** `installer/uninstall.py:416–422`, `440–443`; `installer/receipts.py:420–429`.
- **Problem:** Removal initially forces hashing through `plan_removal(..., verify=True)`, but its new final check calls `matches()` without `rehash=True`. If a raw binary is replaced after planning with different bytes of the same length and its recorded modification time is restored, the final metadata shortcut returns true and the changed file is unlinked. Replacement can occur anywhere between planning and that artifact’s check, not just in the final check/delete interval.
- **Fix:** Force hashing in the final deletion check rather than downgrading authorization to size/mtime equality. Add a regression that substitutes same-length bytes and restores mtime after the verified plan has returned.

### RR-03 [MEDIUM] Partial refreshes can strand successfully probed packs in CHECKING

- **File:** `installer/version_status.py:1035–1053`, `1637–1652`.
- **Problem:** There is one `_pack_scan`, but partial passes retain states from multiple sequences. Refreshing `[superpowers, ponytail]`, then only `[ponytail]`, replaces `_pack_scan` with the second sequence. A subsequent successful skill probe rebuilds only ponytail because superpowers fails `state.seq == published[0]`. Superpowers remains CHECKING despite fresh stored answers. `_skills_probed` is already true, so another skill-worker call returns without rebuilding it (`1013–1014`, `1036`).
- **Fix:** Retain the publishing scan associated with each pack state rather than one globally replaceable scan/sequence pair. Cover a full pack pass followed by a partial pack pass before skill-probe publication.

### RR-04 [MEDIUM] Duplicate canonical plugins regain a suppressed install step downstream

- **File:** `installer/skill_lifecycle.py:879–901`, `953–975`; `installer/version_status.py:1105–1113`.
- **Problem:** Two canonical Claude plugin versions produce duplicate reasons and deliberately no canonical install/enable step. If Codex has a working copy, Claude’s `"absent"` answer also qualifies as a partial missing harness. `_user_pack_facts()` excludes only harnesses already having steps, so it generates a new Claude `skill_install` step. The published state therefore proposes installing over the ambiguous duplicate state that the fix intentionally leaves manual.
- **Fix:** Preserve “installed but ambiguous” separately from genuinely absent when generating partial-harness steps. Add a state-service regression with duplicate Claude versions and a present Codex copy.

### RR-05 [MEDIUM] Scratch HOME leaves inherited manager directories pointing into real HOME

- **File:** `tests/conftest.py:102–116`; `installer/ownership.py:474–481`, `500–506`.
- **Problem:** The new isolation fixture changes HOME but retains inherited absolute `PNPM_HOME` and `VOLTA_HOME`. A state refresh with a nonempty active path builds owner prefixes from those variables, then resolves each prefix. Consequently, tests can still inspect real-home filesystem components and obtain environment-dependent attribution despite using scratch service directories.
- **Fix:** Clear or sandbox `PNPM_HOME` and `VOLTA_HOME` in the autouse isolation fixture. Tests specifically exercising these overrides can set them explicitly. Extend isolation coverage to reject real-home resolution attempts through inherited overrides.

### RR-06 [LOW] Workspace assignment quoting does not survive the nested shell command

- **File:** `tests/test_container_e2e_receipts.py:299`; `scripts/container-e2e-verify.sh:315–319`.
- **Problem:** The generated assignment now preserves a checkout path containing spaces, but the extracted pre-uninstall function interpolates it into another shell command as `cd ${TESTER_WORKSPACE}`. A checkout such as `/a b/c` still executes `cd /a b/c` and fails with too many arguments. The new assignment-only test at `tests/test_container_e2e_receipts.py:241–248` does not exercise this consumer.
- **Fix:** Shell-quote the workspace when constructing the nested command and test the actual pre-uninstall function with a spaced workspace.

## Summary

| Severity | New or residual findings detailed above |
|---|---:|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 3 |
| LOW | 1 |
| **Total** | **6** |

The original file-to-directory deletion escalation, duplicate-row TUI crash, stale green skill marks, malformed receipt handling and digest-memo confusion are addressed. Removal still has two grounded data-loss windows. Accepted/deferred prior findings remain identified separately in the closure table.

`git diff --check` passed; the working tree remained clean. No genuinely new quality-gate suppressions were found.

Not checked: pytest, installs, containers or live-host probes; no files were edited. Runtime safety is not established by this source review, particularly for concurrent removal and replacement.
