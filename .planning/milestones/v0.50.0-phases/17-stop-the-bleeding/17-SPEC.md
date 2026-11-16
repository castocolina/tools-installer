# Phase 17: Stop the bleeding — Specification

**Created:** 2026-10-13
**Ambiguity score:** 0.15 (gate: ≤ 0.20)
**Requirements:** 13 locked

## Goal

No known host hazard (H1–H7 in `.planning/research/2026-10-13-target-architecture.md` §10) can fire on the user's machine. Every failed or crashed run reports failure and exits 1. CI is green on ubuntu-latest and macos-latest, and main requires that check.

## Background

The code under `installer/`, `setup.py` and `tests/` is unchanged since the target architecture re-confirmed every hazard on 2026-10-13 at commit `9490feb`:
- `download.py:189-190,403-404` and `apps.py:100` run `chmod +x` and `ln -sf` on an archive member without checking that it is a file. On this host `~/.local/bin/subl` already points to a directory.
- `postinstall.py:256-274` runs `graphify <host> install` with no cwd, so it writes `CLAUDE.md`, `AGENTS.md` and `.claude/settings.json` into whatever directory the installer runs from.
- `uninstall.py:56-97` treats a path that matches by name as removable. `setup.py:1358` auto-confirms under `--yes`, and `app.py:594-595` deletes.
- `guards.py:554,564` and `tweaks.py:297,308` write rc files non-atomically. `app.py:447` applies line indices computed before the confirm step.
- `execute_screen.py:593-656` has only `try/finally`, so a worker exception ends in a green "Done.". `setup.py:1275,1509` ignore `not_attempted` and update failures.
- `wizard_app.py:2179-2194` saves a new link mode without moving active policies.
- `run.py:235` starts children with no new session, so a vendor script reading `/dev/tty` blocks the TUI.
- `settings.py:55` crashes on non-UTF-8 input.
- F2: some routes accept a selection but cannot execute it.

CI run 38437178670 on main (2026-10-13) fails on both OSes, 11 tests in total:
- ubuntu: `test_shellrc[time-shells0]`, because of `time .` under `/usr/bin/sh`;
- macOS: 6 tests in `test_prune_tmp_linux_sh` (bash 3.2 has no `mapfile`), 2 in `test_app` (console width), `test_setup::test_interactive_wizard_shares_one_cache…`, and `test_catalog_tui::test_owner_cell_semantic_value…`;
- a timing-dependent race test fails intermittently.

## Requirements

1. **Link targets are files (SAFE-01)**: A download or app install whose archive member is not a regular file fails and links nothing.
   - Current: `chmod +x` and `ln -sf` run on any member; a directory member yields a link to a directory, and a reinstall writes through that link into the opt dir.
   - Target: The member is checked with `is_file()` before linking, and links are replaced atomically without shelling `ln`. The registry `member` for Sublime is corrected.
   - Acceptance: In a scratch HOME, a fixture archive whose member is a directory raises `ExecutorError` with no link created. A reinstall over an existing link-to-directory leaves every file inside that directory byte-identical.

2. **graphify never writes into the CWD (SAFE-02)**: Installing or updating graphify writes no file into the installer's working directory.
   - Current: `graphify <host> install` runs with the installer's cwd.
   - Target: The hook uses graphify's global per-host form when an isolated-HOME probe shows the working directory stays empty. Otherwise graphify's `postinstall` is removed from the registry. The per-project form is never run.
   - Acceptance: With HOME and cwd both scratch dirs, install and update of graphify leave the cwd with zero entries.

3. **Only proven artifacts are removed (SAFE-03)**: TUI Uninstall and `make uninstall --yes` delete only artifacts proven to be the installer's.
   - Current: Removability is a name match.
   - Target: Until receipts land (Phase 19), proof is the archive layout only: `~/.local/bin/<bin>` must resolve to a regular file inside that same tool's `~/.local/opt/<bin>/`. Every other match (raw single-file binaries, uv/pip files, app files, shared files) is shown as "remove it yourself" with its path and is not deleted. The CLI uses the same predicate as the TUI.
   - Acceptance: The uv-tool `ruff` symlink, a pip `yq` file and the shared `drawio` file produce 0 deletions in both TUI and `--yes`. An archive-layout tool is removed. A link into another tool's opt dir is not removed.

4. **Atomic rc and shim writes (SAFE-04)**: rc and shim writes are atomic, and duplicate cleanup refuses a file changed since preview.
   - Current: `write_text` is used on rc files, and cleanup applies stale line indices.
   - Target: All rc and shim writers use the atomic writer. Cleanup keeps the previewed bytes and refuses when the file differs byte-for-byte at confirm. A symlinked rc is written through to its target.
   - Acceptance: An injected write failure leaves the original byte-identical. An edit between preview and confirm causes a refusal with the file unchanged. A symlinked rc is still a symlink afterwards, and its target holds the new content.

5. **Failure is reported (SAFE-05)**: A worker exception, a failed install or a failed update shows a red "Failed" status and exits 1.
   - Current: Exceptions end in a green "Done." and exit 0, and update failures are ignored in the exit code.
   - Target: The worker catches exceptions. Rows already done stay done, the rest become "not attempted", the status is red, and the exit is 1. A run with only skipped rows exits 0.
   - Acceptance: A worker raising mid-run gives a red status, the earlier rows reported done, the remaining rows not attempted, and exit 1. A failed update gives exit 1. An all-skipped run gives exit 0.

6. **Link-mode change carries active policies (SAFE-06)**: Changing the link mode moves every active policy to the new mode.
   - Current: The mode is saved and reported "ok", and active policy blocks stay in the old mode's files.
   - Target: Each active policy is removed in the old mode and applied in the new mode, with a per-policy report. If applying fails, the old block is restored. With no active policies, only the mode is saved.
   - Acceptance: With a ban and a tweak active, centralized → split leaves the blocks absent from the old file and present where the new mode sources. An injected apply failure leaves the old block in place and reports that policy as failed.

7. **No terminal prompt hangs the TUI (SAFE-07)**: An install or update child that opens `/dev/tty` fails fast.
   - Current: No new session is started, so the child can block on the controlling terminal.
   - Target: Install and update children run in a new session with stdin closed. The codex registry entry sets its non-interactive env.
   - Acceptance: A fake script that opens `/dev/tty` and reads exits non-zero within 5 s under the runner.

8. **Bad settings never crash launch (SAFE-08)**: Invalid UTF-8 or invalid JSON in `settings.json` does not crash the app.
   - Current: A `UnicodeDecodeError` is raised at `settings.py:55`.
   - Target: The app falls back to defaults, shows a warning, and does not overwrite the bad file until the user changes a setting.
   - Acceptance: Launching with invalid-UTF-8 and with invalid-JSON fixtures reaches the first screen. The fixture bytes are unchanged after launch.

9. **Execute on every route (SAFE-09)**: Enter on a catalog selection executes it on setup, doctor, fix, uninstall and guard routes.
   - Current: Some routes build the app without `execute` and exit with the ids.
   - Target: Every route wires execution. Enter with nothing selected does nothing and says so.
   - Acceptance: One test per route asserts that the selection runs. `test_accepting_the_catalog_without_execute_still_exits_with_ids` is deleted. Empty-selection Enter shows the message and runs nothing.

10. **Doctor names broken links and how to repair them (Sublime)**: Doctor reports a `~/.local/bin` link to a directory, or a dangling link, as broken and prints the exact repair steps.
    - Current: Not detected. This host has `~/.local/bin/subl` pointing to a directory.
    - Target: A Doctor finding per broken link, with copy-paste repair steps. For `subl` the steps are: remove `~/.local/opt/subl`, then reinstall from the catalog. Nothing is executed.
    - Acceptance: In a scratch HOME, a link to a directory and a dangling link each produce one finding with repair text. No filesystem change happens.

11. **CI green on both OSes (CI-01)**: The ubuntu-latest and macos-latest jobs pass.
    - Current: 11 failures across both OSes.
    - Target: `prune-tmp-linux.sh` is portable to bash 3.2 and passes its tests on macOS. Console-width tests are width-independent. The `/usr/bin/sh` `time .` case is handled. The race test is deterministic, using a barrier instead of timing.
    - Acceptance: The CI run on the phase's final commit shows both jobs `success`.

12. **main requires the CI check (CI-02)**: A branch protection rule on main requires the CI check before merge.
    - Current: No protection, and phase closes push straight to main.
    - Target: Applied with `gh api` only after CI is green and the user confirms at that moment. Required status checks are the two CI jobs. `enforce_admins=false` lets the admin push directly when needed. When a direct push is refused, Claude opens a PR and merges it as soon as the check passes, without further approval.
    - Acceptance: `gh api repos/castocolina/tools-installer/branches/main/protection` shows both checks required and admin enforcement off.

13. **Phase 16 gap plans re-audited (CI-03)**: Plans 16-17, 16-18 and 16-19 get secure-phase and validate-phase records.
    - Current: Not re-audited after gap closure.
    - Target: The SECURITY and VALIDATION records are updated in `.planning/milestones/v0.49.0-phases/16-*/` and committed.
    - Acceptance: Both files exist with entries for 16-17..19 and are committed.

## Boundaries

**In scope:**
- Fixes for H1–H7, scoped to requirements 1–9
- Doctor detection and repair guidance for broken `~/.local/bin` links
- The interim archive-layout proof as the only removal proof, in the CLI and the TUI
- CI repairs: a portable prune script, deterministic tests, and the `/usr/bin/sh` case
- The branch protection rule (with confirmation) and the phase 16 re-audit records

**Out of scope:**
- Install receipts and the removal plan — Phase 19 / Phase 22
- Registry data fixes other than Sublime's `member` — Phase 18
- Exit codes derived from plan outcomes — Phase 20 replaces the interim rule in requirement 5
- Executing any repair on the user's host — the user runs the printed steps (zero host mutation)
- Native installs handed off instead of run with sudo — Phase 22 (LIFE-02)
- Real-host UAT of the phase 16 symptoms — Phase 24 (ONB-05)

## Constraints

- Zero sudo, pkexec or doas anywhere, including the repair guidance.
- Tests never touch the real `$HOME`; they use a scratch HOME (tmp_path), and shell checks run in disposable containers.
- macOS is verified only through CI (no local macOS host).
- `make validate` and the coverage gate must pass; no quality gate is bypassed.
- English for code, comments and commits.

## Acceptance Criteria

- [ ] A directory archive member raises `ExecutorError` and creates no link (scratch HOME)
- [ ] A reinstall over a link-to-directory leaves the directory's files byte-identical
- [ ] graphify install and update leave an empty scratch cwd empty
- [ ] Uninstall deletes 0 files for the uv `ruff` symlink, a pip `yq` file and the shared `drawio` file, in the TUI and with `--yes`
- [ ] An archive-layout tool is removed; a link into another tool's opt dir is not
- [ ] A second `make uninstall --yes` deletes nothing and exits 0
- [ ] An injected rc write failure leaves the original byte-identical
- [ ] A file changed between preview and confirm is refused and left unchanged; a trailing-newline change counts as changed
- [ ] A symlinked rc stays a symlink, and its target gets the content
- [ ] A worker exception gives a red status, done rows stay done, the rest are "not attempted", and exit is 1
- [ ] A failed update exits 1; an all-skipped run exits 0
- [ ] A link-mode change moves an active ban and tweak; an injected apply failure keeps the old block and reports it
- [ ] A fake `/dev/tty` reader exits non-zero within 5 s
- [ ] Invalid-UTF-8 and invalid-JSON `settings.json` launch to the first screen with the file bytes unchanged
- [ ] Enter executes the selection on setup, doctor, fix, uninstall and guard; empty Enter shows a message and runs nothing
- [ ] Doctor reports a link-to-directory and a dangling link with repair text and changes nothing
- [ ] The CI run on the final commit is `success` on ubuntu-latest and macos-latest
- [ ] Branch protection on main requires both CI checks with `enforce_admins=false`
- [ ] SECURITY and VALIDATION records for 16-17..19 exist and are committed

## Edge Coverage

**Coverage:** 31/31 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| concurrency | R1, R2, R3, R6, R7, R8 | ⛔ dismissed | One installer process per host; installs are serialized by the engine |
| adjacency | R3 | ✅ covered | A link into another tool's opt dir is not proof (AC 5) |
| empty | R3 | ✅ covered | A tool with no matches is "nothing to remove", 0 deletions (AC 4) |
| ordering | R3 | 🧪 backstop | Opt-dir delete fails after the link is removed → the remainder is still listed (held-out edge test) |
| idempotency | R3 | ✅ covered | A second `--yes` run deletes nothing, exit 0 (AC 6) |
| boundary | R4 | 🧪 backstop | A missing rc file is created atomically (held-out edge test) |
| adjacency | R4 | ✅ covered | A symlinked rc is written through (AC 9) |
| empty | R4 | 🧪 backstop | An empty rc is written atomically (held-out edge test) |
| ordering | R4 | ✅ covered | Changed between preview and confirm → refused (AC 8) |
| precision | R4 | ✅ covered | Byte comparison; a trailing newline counts (AC 8) |
| concurrency | R4 | 🧪 backstop | A concurrent writer never yields a partial file (held-out edge test) |
| idempotency | R5 | ✅ covered | An all-skipped run exits 0 (AC 11) |
| concurrency | R5 | ✅ covered | A mid-run exception: done rows kept, rest not attempted (AC 10) |
| adjacency | R6 | ✅ covered | A failed apply restores the old block (AC 12) |
| empty | R6 | ✅ covered | No active policies → only the mode is saved (R6 target) |
| ordering | R6 | ⛔ dismissed | Covered by the adjacency restore rule |
| idempotency | R7 | ⛔ dismissed | Not applicable to a fail-fast child |
| adjacency | R9 | ✅ covered | One test per route (AC 15) |
| empty | R9 | ✅ covered | Empty Enter shows a message, runs nothing (AC 15) |
| ordering | R9 | ⛔ dismissed | Route order has no effect |
| unclassified | R10 | ✅ covered | Link-to-directory and dangling link both reported (AC 16) |
| unclassified | R11 | ✅ covered | Both jobs green on the final commit (AC 17) |
| adjacency | R12 | ✅ covered | Direct push allowed for the admin (`enforce_admins=false`); otherwise PR + merge on a green check |
| empty, ordering | R12 | ✅ covered | Applied only after CI is green and the user confirms |
| unclassified | R13 | ✅ covered | Records exist and are committed (AC 19) |
| (added) invalid JSON | R8 | ✅ covered | Defaults, a warning, and the bad file left untouched (AC 14) |

## Prohibitions (must-NOT)

**Coverage:** 5/5 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT delete under `--yes` anything the TUI would refuse to delete | R3 | resolved | test: the same fixtures run through both paths give identical deletion sets |
| MUST NOT execute any repair automatically, and no code path may run sudo, pkexec or doas | R10, all | resolved | test: Doctor fixtures leave the filesystem unchanged; an argv scan over the executors finds no sudo/pkexec/doas |
| MUST NOT replace a symlinked rc with a regular file or alter content outside managed blocks | R4, R6 | resolved | test: the symlink is preserved and foreign bytes are identical outside the markers |
| MUST NOT read or write the real `$HOME` in tests | all | resolved | test: the suite runs with HOME pointed at tmp_path; a guard fails on access to the real home |
| MUST NOT apply branch protection without the user's in-the-moment confirmation, or force-push past a failing check | R12 | resolved | judgment: confirmation is recorded in the phase log; no `--force` or bypass of a red check |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | H1–H7 plus CI, each with a test |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Interim proof only; receipts and data fixes excluded |
| Constraint Clarity | 0.75  | 0.65 | ✓      | Zero sudo, scratch HOME, macOS via CI only |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | 19 pass/fail criteria |
| **Ambiguity**      | 0.15  | ≤0.20| ✓      | |

## Interview Log

| Round | Perspective     | Question summary | Decision locked |
|-------|-----------------|------------------|-----------------|
| 1 | Researcher      | Removal proof before receipts? | Conservative: archive layout only; temporary regression accepted |
| 1 | Researcher      | Who applies branch protection? | Claude via `gh`, after green CI and user confirmation |
| 1 | Researcher      | What about the already-damaged Sublime? | Doctor detects and prints repair steps; the user runs them |
| 2 | Simplifier      | graphify outcome? | Global per-host form if proven cwd-clean, else remove the hook |
| 2 | Simplifier      | Linux-only prune tests on macOS? | Make `prune-tmp-linux.sh` portable to bash 3.2 (user choice over skipping) |
| 3 | Boundary Keeper | Protection vs direct pushes | `enforce_admins=false`; direct push if allowed, else PR merged on a green check without further approval |
| 3 | Failure Analyst | Edge table and prohibitions | Accepted as proposed |

---

*Phase: 17-stop-the-bleeding*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 17 — implementation decisions (how to build what's specified above)*
