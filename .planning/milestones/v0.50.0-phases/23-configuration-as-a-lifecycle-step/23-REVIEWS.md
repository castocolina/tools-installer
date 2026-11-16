---
phase: 23
reviewers: [opencode-referee-two, opencode-referee-three]
reviewed_at: 2026-11-07T01:25:01Z
cycle: 1
plans_reviewed: [23-01-PLAN.md, 23-02-PLAN.md, 23-03-PLAN.md, 23-04-PLAN.md, 23-05-PLAN.md, 23-06-PLAN.md, 23-07-PLAN.md, 23-08-PLAN.md, 23-09-PLAN.md, 23-10-PLAN.md, 23-11-PLAN.md, 23-12-PLAN.md, 23-13-PLAN.md, 23-14-PLAN.md, 23-15-PLAN.md, 23-16-PLAN.md]
models:
  opencode-referee-two: "router-env/my-referee-two"
  opencode-referee-three: "router-env/my-referee-three"
model_sources:
  opencode-referee-two: "pinned (added 2026-11-06, full scope)"
  opencode-referee-three: "pinned (auto-failover from referee-one; split into 23-01..08 and 23-09..16 halves after a full-scope timeout)"
---

# Cross-AI Plan Review — Phase 23

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## Cycle 1 — reviewed at HEAD 4ca7775

Three lanes ran in parallel against HEAD `4ca7775`. Raw output is under `.review-diagnostics/20261107T012501Z-plan-review-cycle1/` (gitignored):

- `opencode-referee-two/lane.out` (rc 0, 19.9 KB): all 16 plans. Every code anchor checked with codegraph; it omits plans with no finding (23-01, 23-05, 23-12, 23-16).
- `opencode-referee-three-a/lane.out` (rc 0, 16.2 KB): 23-01..23-08. One local experiment (zsh 5.9 `ZDOTDIR` startup behaviour, in `/tmp/opencode`); no repo edits.
- `opencode-referee-three-b/lane.out` (rc 0, 14.7 KB): 23-09..23-16. No edits.
- The earlier full-scope referee-three lane (`opencode-referee-three/`) timed out (rc 124) with no output; it is not a review.

Two reviewers ran (referee-two and referee-three, the latter in two halves), so the consensus gate applies to single-reviewer HIGHs. None carried a discount marker; every HIGH below is either corroborated or independently confirmed against source here.

## opencode-referee-two Review

Condensed; every concern kept with its severity. Paths are relative to the phase directory unless they name a repo file.

### 23-02
- **LOW — the re-parse guard is specified per function** (`23-02-PLAN.md:90`); binding REUSE 02-1 wants one private `_guarded(new_text, fmt, expected)`.

### 23-03
- **HIGH — `apply_theme` records after the write, stranding the claim** (`:83`). A failed record write after the `.zshrc` write leaves the installer's `robbyrussell` reading `yours` forever, so starship can never replace it. `write_plugins` (omz.py:439-477) implements the only fail-safe order; REUSE 03-2 mandates it plus a failure test; 23-REUSE.md is not in the plan's reading list.
- **MEDIUM — a second closed-block record reader** (`:81`) beside `omz._record` (omz.py:277-319); REUSE 03-1 wants `_record`/`_record_owned`/`_clear_owned` parameterized.

### 23-04
- **HIGH — Task 3 mutates or fails on the real host.** `write_linux_redirect` ends with `target_path(...).mkdir(parents=True, exist_ok=True)` (env_redirect.py:158). With `absolute=zsh_path` that is the zsh binary: `FileExistsError` on this host (the plan's own test literal `/home/linuxbrew/.linuxbrew/bin/zsh`), or a directory created outside the scratch HOME elsewhere. REUSE 04-1 prescribes the mkdir skip and a `tmp_path` zsh.
- **LOW — `zshenv_path` re-implements the `$ZDOTDIR` resolver** (REUSE 04-2).

### 23-06
- **MEDIUM — `display_path` becomes copy #2 of `policy._display_path`** (`:107`; policy.py:96-100, 23 call sites); REUSE 06-1 moves it to `locations.py` and adds `locations.py` + `policy.py` to the plan; 23-07 adds a third copy (`tilde`).
- **MEDIUM — the agent_policy single-writer decision was never folded** (RUN-LEDGER `23 | Reuse pass decisions`); no plan touches `installer/agent_policy.py`; `_apply_opencode` still re-serializes `opencode.json` (dead code today, decision unimplemented).
- **LOW — ledger read/write should reuse `_read_json_object`/`_write_json`, and `config_ledger_dir()` should derive from `default_receipts_dir()`** (REUSE 06-3).
- Noted as correctly folded: the `platform_os == "macos"` path rule (REUSE 06-2) at `:99`.

### 23-07
- **HIGH — the O7 catalog `≈`/`blocked` row has no owner.** The ledger promises it to 23-07; no task implements UI-SPEC section 5 row 4.
- **MEDIUM — `RunContext.harnesses` is the forbidden second seam** (REUSE 07-1); the plan's own tests would exercise an injection path production never uses.
- **LOW — a private `tilde`** (REUSE 07-3).

### 23-08
- **MEDIUM — `_recipe_argv` keeps its own copy of the receipt-method rule** (uninstall.py:256-258; REUSE 05-1).
- **LOW — the proven-executable scan and the error-line pick duplicate existing code** (REUSE 08-2, 08-3).

### 23-09
- **HIGH — an install-time "yes" can be a silent no-op in split link mode.** The bare `write_tweak` (`:88`) skips the `ensure_sourced_from` wiring `tweak_policy` does; the orchestrator picked option (b) and the plan still holds option (a) without even the shortcut comment.
- **MEDIUM — `SHELL_INIT_EFFECTS` duplicates the bundle descriptions** (REUSE 09-1).

### 23-10
- **MEDIUM — the desktop `SHELL` option resolves zsh with plain `shutil.which`** (`:80-81`); REUSE 10-1 (right after a brew install zsh is not on PATH) moves `_which_with_brew` to `postinstall` and drops `RunContext.which`.
- **LOW — `AGENT_OPTION_IDS`/`ATTRIBUTION_IDS` hand-kept; truncation and display helpers** (REUSE 10-2, 10-3).

### 23-11
- **MEDIUM — `setting_state` and `setting_facts` classify twice** (REUSE 11-1).
- **LOW — `desktop_shell_policy.owned` is redundant** (REUSE 11-2).

### 23-13
- **LOW — the headless `set_login_shell` default silently flips from yes to no** (`:82`; app.py:167-171 today defaults yes); UI-SPEC mandates default-no only for the new questions.

### 23-14
- **LOW — a third read → strip → write copy** (REUSE 14-1). **LOW — the `home` parameter** (REUSE 14-2).

### 23-15
- **LOW — three revert loops** instead of REUSE 15-1's one helper.

### Cross-plan priorities (reviewer)
1. **The binding reuse/decision layer never reaches the executors**: zero `23-REUSE.md` references in any plan; all three replan folds of the ledger row are missing; 7 of 11 Important REUSE notes are contradicted by plan text.
2. Fix 23-04 Task 3 before any execution.
3. Preservation safety is otherwise solid (guarded splice, parse-or-refuse, CAS, only-keys-we-wrote).
4. Symbol hand-offs and same-wave disjointness check out.
5. Coverage gap worth a decision: CONF-08's "pi state notes when a permission extension is installed" (SPEC R8) has no task (research A7 `[ASSUMED]`); the ≥100k estimates on 23-06/07/11/15 are large.

### Not checked (reviewer)
Nothing executed; vendor facts not re-fetched; the container harness internals, conftest internals and the "~68 `UpdateService(`" count not verified; whether `_apply_opencode` is reachable today.

## opencode-referee-three Review (half A: 23-01..23-08)

### 23-01
- **MEDIUM — a registration can run with no receipt to record it.** engine.py:319-328 skips the record or turns its failure into a leftover, but the hook still runs; `record_hooks` then returns False; removal never unregisters it.
- **MEDIUM — marker directories widen which hosts get registered** (`present_harnesses` counts `~/.cursor`, `~/.claude`, `~/.config/opencode`, `~/.opencode`); the shortcut comment covers only re-registration.
- **MEDIUM — Task 1 breaks tests in files it does not list**: tests/test_session.py:175/:594/:1034 assert the catalog reaches `install(...)`; nine tests in tests/test_engine.py monkeypatch `engine.run_postinstall`.
- **LOW — `InstallOutcome` is `init=False` with a hand-written `__init__`.**

### 23-02
- **MEDIUM — moving the snapshot helpers breaks two tests/test_shellrc.py patches** (:2226, :2958).
- **LOW — the expected JSON error column is wrong**: `{"a": 1,,}` is column 9 on Python 3.12.12, not 10 (also 23-06).
- **LOW — insert indent is ambiguous for an inline object** (a created parent).

### 23-03
- **MEDIUM — `export ZSH_THEME=` (or `typeset`, or indented) is not detected**, so `robbyrussell` can override the user's theme.
- **LOW — the theme line and its record are never undone on uninstall.**
- **LOW — enabling the Oh-My-Zsh plugins row now also writes a theme; the row's detail copy does not say so.**

### 23-04
- **MEDIUM — with `$ZDOTDIR` set inside `~/.zshenv`, zsh never reads `$ZDOTDIR/.zshenv`** (zsh 5.9 experiment); `zshenv_path` (and REUSE 04-2's form) picks the unread file.
- **MEDIUM — one `.zshenv` problem takes down the whole terminal sync** (`_read_text` raises on non-UTF-8, FIFO, oversize; in the dry run every terminal row turns `unchecked`).
- **LOW — the block is left behind on uninstall while zsh stays** (signed off).

### 23-05
- **LOW — the herdr pair ships unwired** (signed off). **LOW — REUSE 05-1 wrongly says uninstall already imports postinstall** (no cycle).

### 23-06
- **MEDIUM — the orchestrator's single-writer decision has no task** (`_apply_opencode` unreachable today).
- **LOW — Python equality treats `1 == True` and `0 == False`.** **LOW — the JSON error column is off by one.**

### 23-07
- **MEDIUM — the sweep registers every present, unrecorded host, not just the new one** (SPEC R2 says new host only; every pre-phase receipt has `hooks={}`).
- **MEDIUM — `register_hooks` returning `((), None)` has no step outcome** (host gone, or refresh and run disagree on presence).
- **LOW — `_run_reconfigure` now joins all warnings; existing assertions may change.**

### 23-08
- **MEDIUM — removing a host first can make codegraph impossible to remove** if codegraph exits non-zero for an absent target (not verified).
- **MEDIUM — receipts written before Phase 23 have no hooks, so removal unregisters nothing.**
- **LOW — after `codegraph upgrade` the binary is no longer proven** (registry.toml:1708).

### Cross-plan priorities (reviewer)
1. **HIGH — the binding REUSE notes are not referenced by any plan** (03-2, 04-1, 06-2, 07-1 live only in REUSE).
2-7. The 23-03 matcher, 23-04 `ZDOTDIR` and containment, 23-01 no-receipt rule, 23-07 new-host scope and empty outcome, 23-08 absent hosts and pre-phase receipts, the missing test files.
8. Same-wave file sets disjoint in waves 1-3, including REUSE additions; symbol hand-offs match.

### Not checked (reviewer)
Plans 23-09..16; codegraph/herdr absent-target behaviour; created-file mode; pyright; vendor key semantics.

## opencode-referee-three Review (half B: 23-09..23-16)

### 23-09
- **HIGH — the shell-init block can land above the PATH block, so its `command -v` guard fails on a first install.** The action runs during the row; the PATH block is written after the run (setup.py:1460-1471; execute_screen.py:640/659); both writers use `apply_block`, which appends.
- **HIGH — the ledger's option (b) for 09-2 has no executable home**: a post-install action receives only `(tool, platform, confirm)`; the reader would need `RunContext`/engine/setup, which belong to 23-10 in the same wave.
- **MEDIUM — between 23-09 and 23-12/23-13 the shell-init question shows the login-shell text and, headless, defaults to yes** (execute_screen.py:160-167; app.py:167-171).
- **LOW — `sensitive_prompt` falls back to the login-shell entry for an unknown action.**
- **LOW — the volta body adds `$VOLTA_HOME/bin` only when volta is already on PATH; the prompt overstates it.**
- **LOW — starship yes with a user's own theme leaves two prompts, and removing starship keeps `ZSH_THEME=""`.**

### 23-10
- **MEDIUM — a desktop `SHELL` file written by this option can outlive zsh and the uninstall** (ownership via `linux_applied` matches only the current zsh path, env_redirect.py:176-189).
- **LOW — plan text conflicts with binding notes** (`RunContext.which`, the `harnesses` interface).

### 23-11
- **MEDIUM — the desktop row's ownership check is keyed to the zsh path** (same root cause).
- **LOW — the desktop row's description with `zsh_path=None` is unspecified** (`SHELL=None`).

### 23-12
- **LOW — not verified whether `OptionList` already consumes `space`.**

### 23-13
- **LOW — tests/test_prompt.py:5 and :16 build one-argument `ask_confirm` callbacks.** **LOW — `confirm_sensitive` passes `default=False` for `set_login_shell` too.**

### 23-14
- **HIGH — existing `setup.main` tests would strip the aliases in the real `~/.myshellrc`**: `setup._MYSHELLRC` is set at import from the real HOME (setup.py:97; imported at collection by tests/test_setup.py:18); about thirteen tests call `setup.main` through `_headless_main_fixture`, which does not patch it; the real file holds `tweak:claude-skip` and `tweak:cursor-agent-model`; the session guard only fails after the damage.
- **MEDIUM — files the plan must edit are missing from `files_modified`** (tests/test_policies_e2e.py:722/810/956, tests/test_policy.py:262/315/342/400/449/579).

### 23-15
- **MEDIUM — "revert_agent, skipping a FileResult under decision.config" cannot work as written** (revert_agent reverts every file before returning; order versus `_config_step` unspecified).
- **MEDIUM — the config-supersedes case has no real trigger** (only uv, gh, glow, pnpm and kitty declare `config_paths`).
- **MEDIUM — removing zsh does not remove the desktop `SHELL` file.**

### 23-16
- **LOW — `grep -rlI codegraph` over `~/.claude` and `~/.codex` may flag files codegraph never owned** (fails safe).

### Cross-plan priorities (reviewer)
1. 23-14 test isolation first. 2. 23-09 block order. 3. 23-09 option (b) seam, wired in 23-14. 4. The consent-text gap between waves. 5. Sentinel-based desktop ownership, reversing REUSE 11-2. 6. 23-15 config-supersedes. 7. Missing test files. 8. Same-wave sets disjoint in waves 4-6.

### Not checked (reviewer)
Plans 23-01..08; Textual `space` handling; codegraph's unregister; 80x20 widths; pyright on the new signatures; a line-by-line CONF comparison.

## Source-grounding adjudication

Every HIGH and MEDIUM (and every LOW) was re-checked against HEAD `3342273` (the plans' tree, identical code to `4ca7775`) with `codegraph explore` and targeted reads. Evidence for the verdicts that turn on code:

- **R1-07 (real rc):** `setup.py:97` `_MYSHELLRC = Path.home() / ".myshellrc"` (also `_SHELLRC` :101, `_ZSHRC` :104, `_RC_PATHS` :105, `_ENVIRONMENT_D_DIR` :132, the daemon paths :118-128) are computed at import; `tests/test_setup.py:18` imports `setup` at collection, before the autouse `sandboxed_home` runs; `_headless_main_fixture` (:1439-1500) stubs `configure` but never patches `_MYSHELLRC`; `tests/conftest.py` `real_home_untouched` fingerprints `.myshellrc` (size, mtime) only at session end, and its own docstring calls the redirect "opt-in". `grep` (read-only) of the real `~/.myshellrc` shows `tweak:claude-skip` (line 38) and `tweak:cursor-agent-model` (line 46). No installer module computes home paths at import (grep), so `setup` is the only module to re-root. CONFIRMED.
- **R1-06 (block order):** `shellrc.apply_block` (:147-164) replaces the last block in place, else appends; `write_tweak` (tweaks.py:293) and `write_myshellrc` (shellrc.py:226) both use it; `configure_path` (app.py:189-256) writes the PATH block after the run, and in split mode writes it inline into each rc file (where a `source` block wired during the row would precede it). CONFIRMED.
- **R1-05 (option b):** `post_install.PostInstallAction = Callable[[Tool, Platform, ConfirmSensitiveAction | None], ...]` (post_install.py:32); `tweak_policy` (policy.py:512-619) wires `ensure_source` only through `ensure_sourced_from`; the reader lives in `setup._build_app` (:882-886). Importing `installer.policy` pulls in neither `post_install` nor `engine` (checked in a fresh interpreter), so post_install can call `tweak_policy` without a cycle. CONFIRMED.
- **R1-03:** `env_redirect.write_linux_redirect` ends with `target_path(redirect, home).mkdir(parents=True, exist_ok=True)` (:157). CONFIRMED.
- **R1-02, R1-16:** `omz._record` (:277), `_record_owned` (:322), `_clear_owned` (:329) exist; the plan text said "write then record" and "read like `_record`". CONFIRMED.
- **R1-04:** no plan task produces a catalog fact from an unparsable managed settings file; `session.py:714-723` turns MISCONFIGURED without steps into BLOCKED, so the producer is all that is missing. CONFIRMED.
- **R1-08:** engine.py:319-334 runs the hook after a skipped or failed `receipts.record`. CONFIRMED.
- **R1-10:** `tests/test_session.py:175` (`actual_catalog is catalog`), :594 (`mapping is catalog`), :1034; nine `monkeypatch.setattr(engine, "run_postinstall", …)` in tests/test_engine.py (:761, :805, :825, :848, :880, :902, :924, :1868, :2038). CONFIRMED.
- **R1-12:** tests/test_shellrc.py:2226 and :2958 patch `installer.shellrc._snapshot` / `_snapshot_matches`. CONFIRMED.
- **R1-13, R1-29:** on the project interpreter `json.loads('{"a": 1,,}')` raises at `lineno=1, colno=9`; `1 == True` and `0 == False` are both True. CONFIRMED.
- **R1-21:** `terminal_shell._read_text` (:252-270) raises `TerminalShellError` for non-UTF-8, FIFO and oversize files; `_terminal_facts` (version_status.py:1567-1599) puts an unknown warning prefix on every terminal row. CONFIRMED.
- **R1-20:** zsh reads `$ZDOTDIR/.zshenv` only when `ZDOTDIR` is set before startup; an assignment inside `~/.zshenv` takes effect for later startup files only (zsh startup order; the reviewer's experiment agrees). `locations.zshrc_path` (:8-21) is correct for `.zshrc`, not for `.zshenv` in that setup. CONFIRMED.
- **R1-26:** `agent_policy._apply_opencode` (:113-122) re-serializes through `_write_json`; its only caller chain (`apply_agent_permissions` ← `policy.agent_environment_policy`) is reached only from tests. CONFIRMED (dead today, decision binding).
- **R1-33:** D-03 (CONTEXT, locked) says "for each hook tool whose receipt records hooks, register only for `present_harnesses − recorded`". The plan dropped the first condition; the wider set beyond the new host is D-03 as written. PARTIAL.
- **R1-38:** D-04 (locked) uses "exactly `receipt.hooks[name]`, never the present hosts"; O4 (orchestrator) makes a failed unregister stop the removal; codegraph's absent-target exit code is unverified. PARTIAL.
- **R1-39:** `receipts._build_receipt` writes `hooks={}`, so every pre-phase receipt records nothing; D-04 forbids widening. CONFIRMED, bounded by D-04.
- **R1-46:** `setup._which_with_brew` (:637-661) and its two `lookup=` uses (:685, :731); tests at tests/test_setup.py:853, :1757, :2014-2043. CONFIRMED.
- **R1-48:** `linux_applied` (env_redirect.py:176-189) compares the file to the CURRENT target; `policy_owned` (uninstall.py:523-534) falls back to it when `owned` is None; `remove_linux_redirect` (:162-173) checks the sentinel only. CONFIRMED.
- **R1-56:** `next(b for b in BUNDLES if b.id == "claude-skip")` at tests/test_policy.py:262, 315, 342, 400, 449, 579 and tests/test_policies_e2e.py:722, 810, 956. CONFIRMED.
- **R1-58, R1-59:** `revert_agent` (23-06 decision) reverts every file before returning; `config_paths` appear only on uv, gh, glow, pnpm and kitty (registry.toml:72, 466, 883, 2187, 2843), none of them in `CONFIG_AGENTS`. CONFIRMED.
- **R1-62:** SPEC R8 and REQUIREMENTS CONF-08 say pi's "state notes when a permission extension is installed"; the approved UI-SPEC gives only static pi notes (§1 row text, §4 report line) and no extension-detection copy; research A7 marks detection `[ASSUMED]`. PARTIAL: a coverage gap the approved design did not model; needs an orchestrator decision, not a planner guess.
- **R1-01:** zero `23-REUSE.md` references in the 16 plans at HEAD (grep), while the ledger row makes every REUSE item binding. CONFIRMED.

## Consensus Summary

Lanes: R2 = opencode-referee-two, R3a/R3b = opencode-referee-three halves. Severity is the highest any lane gave.

| ID | Plan(s) | Severity | Lanes | Verdict | Required plan change |
|---|---|---|---|---|---|
| R1-01 | all | HIGH | R2, R3a | CONFIRMED | Add 23-REUSE.md to every `<context>`; fold all 11 Important and 18 Minor items into the named plans as task text; fold the three ledger decisions (09-2 option b, agent_policy single writer, O7 row in 23-07) |
| R1-02 | 23-03 | HIGH | R2 (R3a cross-plan) | CONFIRMED | `apply_theme` reserves the record, writes `.zshrc`, rolls back on `OSError`; failure test (REUSE 03-2) |
| R1-03 | 23-04 | HIGH | R2 (R3a cross-plan) | CONFIRMED | Skip the mkdir for an absolute value; the writing test uses a `tmp_path` zsh and asserts no directory (REUSE 04-1) |
| R1-04 | 23-07 | HIGH | R2 | CONFIRMED | A task producing the O7 catalog `≈`/`blocked` fact over the ledger and the parse state; depend on 23-06 |
| R1-05 | 23-09, 23-14 | HIGH | R2, R3b | CONFIRMED | Yes enables through `tweak_policy(...).apply()` with an injected split-mode reader; the composition root wires it in both front ends (23-14 owns setup.py) |
| R1-06 | 23-09 | HIGH | R3b | CONFIRMED | A new PATH block lands above the first tweak/source block; first-install order test |
| R1-07 | 23-01, 23-14 | HIGH | R3b | CONFIRMED | Generic autouse re-rooting of every real-home `Path` constant of `setup` (wave 1) with a self-test; 23-14 proves its strip hits only a scratch rc |
| R1-08 | 23-01 | MEDIUM | R3a | CONFIRMED | No registration for a targeted pair without a receipt; test |
| R1-09 | 23-01 | MEDIUM | R3a | PARTIAL | D-01/CONF-03 lock `present_harnesses`; state the marker-dir limit in the docstring and `shortcut:` comment |
| R1-10 | 23-01 | MEDIUM | R3a | CONFIRMED | Move tests/test_session.py into Task 1 with its three assertions named; repoint the nine `engine.run_postinstall` patches |
| R1-11 | 23-01 | LOW | R3a | CONFIRMED | Name the `init=False` `__init__` edit |
| R1-12 | 23-02 | MEDIUM | R3a | CONFIRMED | Add tests/test_shellrc.py; repoint its two patches to the names shellrc imports |
| R1-13 | 23-02, 23-06 | LOW | R3a | CONFIRMED | Column 9, derived from `json.loads` in the test |
| R1-14 | 23-02 | LOW | R3a | CONFIRMED | Define the inline-object insert rule |
| R1-15 | 23-02 | LOW | R2 | CONFIRMED | One `_guarded` helper (REUSE 02-1) |
| R1-16 | 23-03 | MEDIUM | R2 | CONFIRMED | Parameterize `_record`/`_record_owned`/`_clear_owned` (REUSE 03-1) |
| R1-17 | 23-03 | MEDIUM | R3a | CONFIRMED | Theme-line matcher with optional `export`/`typeset` and indent; test |
| R1-18 | 23-03 | LOW | R3a | REJECTED | — (by design: UI-SPEC section 3; planner decision 1) |
| R1-19 | 23-03 | LOW | R3a | REJECTED | — (Policies copy is the approved UI-SPEC contract) |
| R1-20 | 23-04 | MEDIUM | R3a | CONFIRMED | `~/.zshenv` when it assigns `ZDOTDIR`, else the `zshrc_path` rule; test |
| R1-21 | 23-04, 23-07 | MEDIUM | R3a | CONFIRMED | Contain `.zshenv` `OSError` as a `zshenv:` warning; map the prefix to the zsh row |
| R1-22 | 23-04 | LOW | R2 | CONFIRMED | Build `zshenv_path` on `zshrc_path` (REUSE 04-2, amended by R1-20) |
| R1-23 | 23-04 | LOW | R3a | REJECTED | — (planner decision 5, signed off) |
| R1-24 | 23-05 | LOW | R3a | REJECTED | — (planner decision 6, signed off) |
| R1-25 | 23-05, 23-08 | LOW | R3a | CONFIRMED | Record that 23-08 adds the postinstall import |
| R1-26 | 23-06 | MEDIUM | R2, R3a | CONFIRMED | One writer for `opencode.json` (ledger decision); per the cycle 1 sign-off, delete the dead agent_policy chain instead of rerouting it |
| R1-27 | 23-06 | MEDIUM | R2 | CONFIRMED | Move `_display_path` to `locations.display_path` (REUSE 06-1) |
| R1-28 | 23-06 | LOW | R2 | CONFIRMED | Shared `_read_json_object`/`_write_json`; ledger dir from `default_receipts_dir()`; docstring (REUSE 06-3, 06-4) |
| R1-29 | 23-02, 23-06 | LOW | R3a | CONFIRMED | Type-strict `same_value` |
| R1-30 | 23-06 | MEDIUM | R3a (R2 noted the path rule folded) | PARTIAL | macOS-versus-rest for the table too; a Fedora test (REUSE 06-2) |
| R1-31 | 23-07 | MEDIUM | R2 | CONFIRMED | No `RunContext.harnesses`; tests patch `postinstall.present_hosts` (REUSE 07-1) |
| R1-32 | 23-07 | LOW | R2 | CONFIRMED | `locations.display_path`, no `tilde` (REUSE 07-3) |
| R1-33 | 23-07 | MEDIUM | R3a | PARTIAL | Add D-03's "receipt records hooks" condition; the rest is D-03 as written |
| R1-34 | 23-07 | MEDIUM | R3a | CONFIRMED | `((), None)` fails the row with a reason; test |
| R1-35 | 23-07 | LOW | R3a | CONFIRMED | Update the existing joined-detail assertions |
| R1-36 | 23-08 | MEDIUM | R2 | CONFIRMED | `_recipe_argv` uses `hook_method` (REUSE 05-1) |
| R1-37 | 23-08 | LOW | R2 | CONFIRMED | `_proven_named`, `_command_error_line` (REUSE 08-2, 08-3) |
| R1-38 | 23-08 | MEDIUM | R3a | PARTIAL | No change under D-04/O4; the 23-16 run is the evidence; orchestrator decides if codegraph fails |
| R1-39 | 23-08 | MEDIUM | R3a | CONFIRMED | `shortcut:` comment, test, manual check; remedy is 23-07's `≈` + RECONFIGURE (D-04) |
| R1-40 | 23-08 | LOW | R3a | CONFIRMED | Name the vendor self-upgrade in the `shortcut:` comment |
| R1-41 | 23-09 | MEDIUM | R2 | CONFIRMED | No `SHELL_INIT_EFFECTS`; effect from the bundle description (REUSE 09-1) |
| R1-42 | 23-09, 23-14 | MEDIUM | R3b | CONFIRMED | Move the six `source_shell_init` registry declarations to 23-14 (after 23-12 and 23-13) |
| R1-43 | 23-09 | LOW | R3b | CONFIRMED | `KeyError` for an unknown action; coverage test |
| R1-44 | 23-09 | LOW | R3b | REJECTED | — (UI-SPEC verbatim copy; the body is correct for both installs) |
| R1-45 | 23-09 | LOW | R3b | REJECTED | — (UI-SPEC section 3 accepts it) |
| R1-46 | 23-10 | MEDIUM | R2 | CONFIRMED | `postinstall.which_with_brew`; no `RunContext.which` (REUSE 10-1) |
| R1-47 | 23-10 | LOW | R2 | CONFIRMED | Derived id tuples, `Text.truncate`, `display_path` (REUSE 10-2, 10-3) |
| R1-48 | 23-04, 23-10, 23-11, 23-15 | MEDIUM | R3b (three plans) | CONFIRMED | Sentinel ownership (`conf_owned`); the desktop row owns by it; zsh's removal sweeps it (reverses REUSE 11-2) |
| R1-49 | 23-10 | LOW | R3b | CONFIRMED | Remove `RunContext.which`/`harnesses` from the plan text |
| R1-50 | 23-11 | MEDIUM | R2 | CONFIRMED | `setting_state` over `setting_facts` (REUSE 11-1) |
| R1-51 | 23-11 | LOW | R2 | REJECTED | — (superseded by R1-48: `owned` stays and becomes the sentinel check) |
| R1-52 | 23-11 | LOW | R3b | CONFIRMED | No-zsh description |
| R1-53 | 23-12 | LOW | R3b | PARTIAL | The pilot decides `priority=True`; record it |
| R1-54 | 23-09, 23-13 | LOW | R2, R3b | CONFIRMED | Per-action default in the prompt table (login shell yes, shell init no) |
| R1-55 | 23-13 | LOW | R3b | CONFIRMED | Fix the two tests/test_prompt.py callbacks |
| R1-56 | 23-14 | MEDIUM | R3b | CONFIRMED | Add tests/test_policy.py and tests/test_policies_e2e.py |
| R1-57 | 23-14 | LOW | R2 | CONFIRMED | `strip_tweak_block`; no `home` (REUSE 14-1, 14-2) |
| R1-58 | 23-15 | MEDIUM | R3b | CONFIRMED | Drop the config-supersedes skip (it cannot work as specified) |
| R1-59 | 23-15 | MEDIUM | R3b | CONFIRMED | Drop the branch with a `shortcut:` and a guard test |
| R1-60 | 23-15 | LOW | R2 | CONFIRMED | One `_revert_settings` (REUSE 15-1) |
| R1-61 | 23-16 | LOW | R3b | REJECTED | — (fails safe by design) |
| R1-62 | CONF-08 (pi) | coverage | R2 | PARTIAL | Orchestrator decision: accept the UI-SPEC's static pi notes as CONF-08's pi clause, or research A7 plus UI copy and a task; recorded as deferred in 23-10 |
| R1-63 | 23-06, 23-07, 23-11, 23-15 | advisory | R2 | REJECTED | — (estimates already accepted as advisory, ledger row 289) |

### Rejected

R1-18, R1-19, R1-23, R1-24, R1-44, R1-45, R1-51, R1-61, R1-63 (reasons in the table). None was refuted on facts; each is by design, signed off, UI-SPEC copy, superseded or already accepted.

Totals: 63 items: 7 HIGH (all CONFIRMED), 25 MEDIUM, 29 LOW, 1 coverage item, 1 advisory; 48 CONFIRMED, 6 PARTIAL, 9 REJECTED, 0 REFUTED. `current_actionable` counts the 47 non-HIGH CONFIRMED or PARTIAL items, none of which the reviewed plan text incorporated.

CYCLE_SUMMARY: current_high=7 current_actionable=47

## Cycle 1 resolution

Replanned in reviews mode at `3342273`. Plan count (16), task count (43), wave assignment (1: 01-04; 2: 05-06; 3: 07-08; 4: 09-10; 5: 11-13; 6: 14-15; 7: 16) and every plan ID are unchanged. Same-wave `files_modified` sets stay disjoint (checked mechanically after the additions). New `depends_on` edges, no wave moved: 23-07 on 23-06; 23-14 on 23-12. New files: 23-01 `tests/test_sandbox.py`; 23-02 `tests/test_shellrc.py`; 23-06 `installer/locations.py`, `installer/policy.py`, `installer/agent_policy.py`, `tests/test_locations.py`, `tests/test_agent_policy.py` (after the sign-off also `installer/agent_guidance.py`, `tests/test_agent_environment_policy.py`, `tests/test_agent_environment_e2e.py`; agent_policy.py, agent_guidance.py and the three test files are deleted); 23-09 `installer/shellrc.py`, `tests/test_shellrc.py` (registry.toml stays, for oh-my-zsh and vscode only); 23-10 `installer/postinstall.py`, `setup.py`, `tests/test_setup.py`, `tests/test_postinstall.py`; 23-14 `installer/registry.toml`, `tests/conftest.py`, `tests/test_policy.py`, `tests/test_policies_e2e.py`, `tests/test_registry.py`. Every plan's `<context>` cites 23-REUSE.md and its `## Review Dispositions Ledger` has a Round 2 table. New threats T-23-49..T-23-62. 23-VALIDATION.md updated (rows, Wave 0 conftest items, two manual checks). Test-first with one green commit per task, the `:(glob)` suppression gate against `git merge-base HEAD main`, and every task's automated verify are kept; new count gates record their HEAD baselines, and negative gates filter comment lines.

| ID | Plan(s) changed | How resolved |
|---|---|---|
| R1-01 | all 16 | 23-REUSE.md in every `<context>` with a line naming the items folded; every Important item is explicit task text (03-1, 03-2 → 23-03; 04-1 → 23-04; 05-1 → 23-05/23-08; 06-1, 06-2 → 23-06; 07-1 → 23-07; 09-1, 09-2 → 23-09/23-14; 10-1 → 23-10; 11-1 → 23-11); every Minor item is inline (01-1, 02-1, 04-2, 06-3, 06-4, 07-2, 07-3, 08-1, 08-2, 08-3, 09-3, 10-2, 10-3, 11-3, 14-1, 14-2, 15-1; 11-2 reversed by R1-48); the three ledger decisions folded (R1-04, R1-05, R1-26) |
| R1-02 | 23-03 | Reserve → write → roll back in `apply_theme`; `test_a_failed_zshrc_write_leaves_the_record_unchanged` |
| R1-03 | 23-04 | mkdir skipped for an absolute value (why comment); the writing test uses `tmp_path / "bin" / "zsh"` and asserts it stays a file; the linuxbrew literal limited to non-writing tests |
| R1-04 | 23-07 | Task 2 `_settings_facts` over 23-06's `setting_state` (one classification); MISCONFIGURED without steps → `blocked`; managed and unmanaged tests; depends on 23-06 |
| R1-05 | 23-09, 23-14 | 23-09: yes → `tweak_policy(bundle, rc_path=~/.myshellrc, ensure_sourced_from=<reader>).apply()`, reader set by `use_shell_init_sourcing`; split-mode test. 23-14: one `_split_sourced_from(link_mode)` behind `_tweak_ensure_sourced_from`, wired in the TUI composition and the headless route; `no_shell_init_sourcing` conftest reset; composition test |
| R1-06 | 23-09 | `write_myshellrc`/`write_managed_path` place a new PATH block before the first tweak or `source` block (existing blocks still replaced in place; `apply_block` untouched); two tests |
| R1-07 | 23-01, 23-14 | 23-01 Task 1: autouse `sandboxed_setup_paths` re-roots every `Path`/list/tuple attribute of `setup` that lies under the real HOME onto the scratch HOME, per test, generically; `test_no_setup_home_constant_points_at_the_real_home` (RED before the fixture). 23-14 Task 2: the self-test must be green first, `test_headless_main_strips_only_the_scratch_rc`, pasted before/after `stat` of the real rc; the session fingerprint stays the net |
| R1-08 | 23-01 | `register_hooks` returns `((), "hook not registered: no install receipt to record it in")` without running; tests at postinstall and engine level |
| R1-09 | 23-01 | Docstring and `shortcut:` comment name the marker-dir limit (D-01 locked) |
| R1-10 | 23-01 | tests/test_session.py in Task 1 with the three assertions; nine patches repointed; grep gate (baseline 9 → 0) |
| R1-11 | 23-01 | `init=False` edit named |
| R1-12 | 23-02 | tests/test_shellrc.py added; patches to `installer.shellrc.read_snapshot` / `snapshot_matches`; grep gate (baseline 2 → 0) |
| R1-13 | 23-02, 23-06 | Column 9, derived from `json.loads` |
| R1-14 | 23-02 | Inline-object rule; created-parent test inserts a second key inline |
| R1-15 | 23-02 | One `_guarded`; grep gate |
| R1-16 | 23-03 | Parameterized record helpers; `owned_theme` over `_record`; grep gate |
| R1-17 | 23-03 | Theme-line matcher; `test_an_exported_or_indented_theme_counts_as_a_theme` |
| R1-20 | 23-04 | `zshenv_path`: `~/.zshenv` when it assigns `ZDOTDIR`, else `zshrc_path(...).with_name(".zshenv")`; test extended |
| R1-21 | 23-04, 23-07 | `_sync_zshenv` contains `OSError` as `zshenv: …`; 23-07 maps the prefix to the zsh row; one test in each |
| R1-22 | 23-04 | Built on `zshrc_path` |
| R1-25 | 23-05, 23-08 | Recorded; 23-08 adds the import |
| R1-26 | 23-06 | Revised after the sign-off (RUN-LEDGER `23 | Cycle 1 replan sign-offs` (4)): Task 3 deletes the dead chain instead of rerouting it: `installer/agent_policy.py`, `installer/agent_guidance.py` (its only consumer), `policy.AgentEnvironmentPolicy` / `agent_environment_policy` / `compose_agent_environment_policy` with their imports, and tests/test_agent_policy.py, tests/test_agent_environment_policy.py, tests/test_agent_environment_e2e.py. `codegraph explore` and `rg` at `fbcbead`: agent_policy.py is imported only by policy.py (a `TYPE_CHECKING` import and two lazy imports inside the trio) and tests; the trio is called only from itself and tests; setup.py and every screen reference none of it. Proof: `test_opencode_json_has_a_single_writer` (the module is gone and only agent_settings imports the agent path table), file-existence and comment-filtered grep gates |
| R1-27 | 23-06 | `locations.display_path`; policy.py re-binds; `test_display_path_lives_in_locations`; grep gates |
| R1-28 | 23-06 | Shared private helpers; `config_ledger_dir()` from `default_receipts_dir().parent`; docstring reworded |
| R1-29 | 23-02, 23-06 | `same_value` in 23-02, used by `_guarded` and every 23-06 comparison; two tests |
| R1-30 | 23-06 | macOS-versus-rest rule for the table; `test_vscode_lean_on_fedora_writes_the_linux_profile`; `== "linux"` grep gate |
| R1-31 | 23-07 | No field; tests patch `postinstall.present_hosts`; regression grep |
| R1-32 | 23-07 | `locations.display_path`; grep gate |
| R1-33 | 23-07 | Sweep only receipts that record hooks (D-03); `test_a_receipt_without_recorded_hooks_is_not_swept`; truth states D-03's wider set |
| R1-34 | 23-07 | `failed — … no unregistered host is present any more`; test |
| R1-35 | 23-07 | Task 1 updates the existing assertions |
| R1-36 | 23-08 | `hook_method` in `_recipe_argv`; grep gate (baseline 1 → 0) |
| R1-37 | 23-08 | `_proven_named` and `_command_error_line`; grep gates |
| R1-38 | 23-08, 23-16, 23-VALIDATION | No logic change now (D-04/O4). The orchestrator's conditional decision (RUN-LEDGER `23 | Cycle 1 replan sign-offs` (3)) is in 23-16's triage rule: if the run shows codegraph's unregister failing for a host whose config is gone, it is a finding to fix by removing an uninstalled host from every receipt's `hooks` (D-04's proof rule kept), never an allowlist entry; manual check |
| R1-39 | 23-08, 23-VALIDATION | `shortcut:` comment, `test_a_pre_phase_23_receipt_unregisters_nothing`, manual check |
| R1-40 | 23-08 | `shortcut:` comment names the self-upgrade |
| R1-41 | 23-09, 23-11 | No `SHELL_INIT_EFFECTS`; prompt, Effect cell and `shell_init_detail` read the bundle description; grep gate |
| R1-42 | 23-09, 23-14, 23-12, 23-13 | Declarations moved to 23-14 Task 3 (`test_the_six_tools_declare_shell_init` moved too); 23-14 depends on 23-12 |
| R1-43 | 23-09 | `KeyError`; `test_every_sensitive_action_has_a_prompt` |
| R1-46 | 23-10, 23-11, 23-14 | `postinstall.which_with_brew` (moved, docstring along); `_resolve_binary` uses it; setup.py and tests/test_setup.py repointed; lookup tests in tests/test_postinstall.py; grep gate (baseline 12 → 0) |
| R1-47 | 23-10 | Derived tuples; `Text.truncate`; `display_path` |
| R1-48 | 23-04, 23-11, 23-15 | 23-04: `DESKTOP_SHELL_CONF`, `conf_owned`, `remove_owned_conf`; 23-11: `owned` = sentinel, remove without zsh; 23-15: zsh's removal sweeps the desktop row; three tests |
| R1-49 | 23-10, 23-12 | Stale field names removed from plan text and interfaces |
| R1-50 | 23-11 | `setting_state` re-implemented over `setting_facts`; `SettingsUnreadable` raised once (grep gate); 23-06 test is the regression gate |
| R1-52 | 23-11 | `SHELL=zsh in ~/.config/environment.d` |
| R1-53 | 23-12 | Pilot decides `priority=True`; recorded in the SUMMARY |
| R1-54 | 23-09, 23-13 | `SensitivePrompt.default` (login shell True, shell init False); `confirm_sensitive` passes it; test asserts both |
| R1-55 | 23-13 | Two callbacks named |
| R1-56 | 23-14 | Both files added; example tweak switched; grep gate (baseline 9 → 0) |
| R1-57 | 23-14 | `strip_tweak_block` (`remove_tweak` delegates); `strip_legacy_aliases(rc_path)` |
| R1-58, R1-59 | 23-15 | Config-supersedes branch dropped; `shortcut:` comment; `test_no_config_agent_declares_config_paths` guards it; `removal_change_lines` loses `config` |
| R1-60 | 23-15 | One `_revert_settings`; grep gates |
| R1-62 | 23-10 | Signed off (RUN-LEDGER `23 | Cycle 1 replan sign-offs` (2)): the UI-SPEC's static pi notes cover CONF-08's pi clause (pi stays out per D-05); no task; 23-10's ledger row records it |

### Decisions needing orchestrator sign-off

Signed off in RUN-LEDGER `23 | Cycle 1 replan sign-offs` (fbcbead): (1) 23-01 at 19 files accepted; (2) R1-62 covered by the UI-SPEC's static pi notes, no task; (3) R1-38 conditional: drop an uninstalled host from every receipt's `hooks` if the e2e shows the failure (recorded in 23-16's triage); (4) R1-26: delete the dead agent_policy chain instead of rerouting it (23-06 revised); (5) R1-48 accepted. The original questions follow for the record.

1. **23-01 grows to 19 files** (adds `tests/test_sandbox.py`, the self-test of the R1-07 guard). It extends the signed 23-01 scope override; the alternative (the guard in 23-14, wave 6) leaves waves 1-5 without prevention.
2. **R1-62 (CONF-08 pi clause):** accept the approved UI-SPEC's static pi notes as satisfying "its state notes when a permission extension is installed", or commission research on A7 (detecting a pi permission extension under `~/.pi/agent`) plus UI copy and a task.
3. **R1-38 (if the 23-16 run shows codegraph failing for an absent recorded host):** relax D-04 to unregister `recorded ∩ present` (never an unrecorded host), or prune a removed host from every `receipt.hooks` when the host tool is removed.
4. **R1-26 alternative:** the ledger decision (route `agent_policy._apply_opencode` through the settings writer) is folded as written. The `agent_environment_policy` chain that reaches it has no production caller, so deleting that dead chain (architecture rule 5) would also give one writer per file with less code; say so if that is preferred.
5. **R1-48 reverses REUSE 11-2** (the desktop row keeps `owned`, now the sentinel check). REUSE is binding, so the reversal is recorded here for sign-off.


## Cycle 2 Review (opencode-referee-two)

Reviewer: opencode `router-env/my-referee-two` (referee-one unavailable: "Combo has no executable targets"), full scope, plans at ca2a422. Raw output: `.review-diagnostics/20261107T035834Z-plan-review-cycle2/opencode-referee-two/lane.out` (gitignored).

**R1 disposition:** every cycle 1 HIGH (R1-01..R1-07) RESOLVED with evidence; MEDIUM spot-checks R1-10, R1-26, R1-30, R1-33, R1-36, R1-38, R1-46, R1-48, R1-56 RESOLVED in the plan text. Same-wave `files_modified` sets disjoint (checked mechanically); registry.toml edits in waves 4 and 6 are sequenced.

| ID | Plan | Severity | Verdict | Resolution |
|---|---|---|---|---|
| R2-01 | 23-14 | HIGH | CONFIRMED (orchestrator: `rg -n 'tweak:codex-skip' tests/test_setup.py` → 1053, 1174, 1191, 1204, 2678) | Task 1 retargets the five test_setup.py lookups to `tweak:docker`, retargets/deletes the named test_policy_tweaks.py pins, sweeps the remaining alias-id pins with rg, and adds tests/test_setup.py to the Task 1 verify run — all in the same green commit |

Not checked by the reviewer: line-by-line 23-05/23-12/23-13 beyond file lists, verbatim UI-SPEC string diff, a simulated JSON/JSONC/TOML splice, shell-check of bundle bodies, the whole e2e script.

CYCLE_SUMMARY: current_high=1 current_actionable=1 (resolved in the plan text by the orchestrator: current_high=0 after the fix)

CONVERGED: yes (cycle 2: the only new HIGH was a mechanical test retarget, fixed in 23-14; no open HIGH remains)
