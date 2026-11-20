---
phase: 28
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-20T12:38:00Z
plans_reviewed: [28-01-PLAN.md, 28-02-PLAN.md, 28-03-PLAN.md, 28-04-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 28

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log (convergence cycle 2, plans at ecd3d9af)

Reviewer selection: `review.default_reviewers = ["opencode-referee-one"]` (router-env/my-referee-one), the owner-required first lane. Failover order if it failed: opencode-referee-two, then opencode-referee-three. Every opencode child ran with stdin closed (`< /dev/null`) under a timeout.

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 09:26 | opencode-referee-one | one-shot probe (`Reply with the single word OK.`, 120 s timeout) | OK: answered `OK`, exit 0, 6 s |
| 09:26 to 09:30 | opencode-referee-one | real review through `gsd-tools query review-lane invoke --slug opencode --model router-env/my-referee-one --as opencode-referee-one`, background, 2700 s timeout, stdin closed; the 221,769-byte prompt (plans, CONTEXT, SPEC, VALIDATION, the cycle 1 finding list, instructions) was sent whole | SUCCEEDED: 11,639 bytes, all four plan ids have their own `##` section, empty `.err`, no stub |

Failures this cycle: none. `opencode-referee-two` and `opencode-referee-three` were not needed. No other model was used. (The cycle 1 lane failures, referee-one and referee-two `ECONNREFUSED`, referee-three HTTP 429, are recorded in this file's version at commit 3d14599b.)

The review below is referee-one's, unedited. Its output opens with one stray bullet (its first HIGH, on zsh binding order) before its own `### Document Type` heading; it is kept as returned. Exactly one reviewer ran, so the multi-reviewer consensus gate does not engage. The orchestrating reviewer therefore verified every referee-one HIGH against repository source before counting it, re-judged every cycle 1 finding against the current plans, and ran an independent pass for defects the revision introduced (scratch copy of the tree under the scratchpad, never the repository: plan 28-01 Task 2 applied by script, plan 28-04 Task 1 applied by script, ruff, ruff format, pyright, vulture, the targeted pytest files; real `shellrc` round trips in scratch HOMEs).

## OpenCode Review (opencode-referee-one)

Using the plan-review checklist to assess the revised plans against the current source and the cycle 1 findings.
- **HIGH — zsh widget execution order is untested:** `.planning/phases/28-shared-terminal-keys-mechanism/28-04-PLAN.md:103-115` binds Ctrl+L when `.myshellrc` is sourced, but `installer/omz.py:411-420` can put Oh-My-Zsh’s key bindings later in `.zshrc`. The planned syntax and source-text tests do not check which binding wins after full startup.
### Document Type

GSD · implementation plans. **Status: Issues found — revise and re-review.**

The cycle 1 fixes are largely incorporated. Two new review findings need attention before execution: the widget test checks escape *spellings*, not the exact emitted bytes required by the SPEC; and a plan 28-04 acceptance grep contradicts its own required comment. The latter is mechanical, but it would prevent the task from meeting its stated acceptance criteria.

For brevity below, plan references use `.planning/phases/28-shared-terminal-keys-mechanism/` as their common prefix.

## 28-01

### 1. Summary

Captures Alacritty’s pre-move bytes, then moves shared region primitives into a lower module before the table-driven work.

### 2. Cycle 1 findings status

- **H1 / A1 — resolved.** `28-01-PLAN.md:156-157` explicitly renames references and changes the conflicting loop-local to `text_line`. The collision is real in the original function: `installer/terminal_shell.py:106-118`.
- **A2 — resolved for the current source.** The revised guard at `28-01-PLAN.md:170-177` compares the remaining functions. A local AST count found **48 function definitions, 48 unique names, and 16 exclusions**; therefore 32 comparisons is correct for this source.
- **A5, compare-before-commit wording — resolved as a disclosure.** `28-01-PLAN.md:215` accurately describes the separate check and replacement at `installer/agent_settings.py:562-569` and `installer/atomic.py:44-52`. It does not claim the race is closed.
- **A3 — routed to 28-04**, discussed there.
- The cycle 1 **H2** clarity issue is resolved by the explicit reference-renaming list at `28-01-PLAN.md:156`.

### 3. Strengths

- `28-01-PLAN.md:103-139` puts the golden characterization tests in a commit **before** the production move.
- The moved primitives retain the malformed-marker refusal and compare-before-write behavior visible at `installer/terminal_shell.py:102-138,604-630`.

### 4. Concerns

- **LOW — AST guard is not a robust automated exit gate.** `28-01-PLAN.md:176-177` prints `STALE`, `CHANGED`, or `NOT-MOVED` but exits zero for those conditions; the executor must inspect output. The current 48 unique names avoid the dictionary-collision concern, but a future duplicate function name would be overwritten in the dictionary.

### 5. Suggestions

Make the AST check exit nonzero on any mismatch and key definitions by qualified location, or explicitly assert unique names before comparing.

### 6. Risk Assessment

**Low to medium.** The move is well characterized, but the actual edited code and commit hooks have not yet been run.

## 28-02

### 1. Summary

Moves the Alacritty keys lifecycle behind a tool-id table and adds registry/table completeness and missing-row tests.

### 2. Cycle 1 findings status

- **A4 — resolved.** `28-02-PLAN.md:187,213` adds the `ghost` reverse-direction fixture, so an always-empty `extra_rows` fails.
- **A5, moved apply route — resolved as disclosed, not as race coverage.** `28-02-PLAN.md:235` says the existing race test only covers sync; that matches `tests/test_terminal_shell.py:1271-1289`.
- **H1 follow-up — resolved in the specified import arrangement.** `28-02-PLAN.md:134,145` does not import `marker` where `_drop_created_config` keeps a parameter of that name.
- **Task 2 RED concern — acknowledged.** `28-02-PLAN.md:188-194` admits the missing-row backstop test may already pass because its code lands in Task 1.
- **H7 — conditionally resolved by isolation.** `.planning/config.json:46` enables worktrees; this relies on the execution workflow actually honoring that setting.

### 3. Strengths

- The plan preserves the existing record names and tests both directions of table completeness (`28-02-PLAN.md:140-144,182-188`).
- The no-row branch avoids a reconfigure crash at the existing dispatch seam, which currently has no enclosing handler in `installer/post_install.py:426-449`.

### 4. Concerns

- **MEDIUM — explicit deviation from locked D-12.** `28-02-PLAN.md:72,133` changes the four imports to a helper in another test module. `28-CONTEXT.md:35` explicitly names `installer.terminal_keys` as their destination. The plan explains its architecture rationale, but it does not record an owner amendment to that locked instruction.

### 5. Suggestions

Record the test-helper destination as an authorized D-12 amendment, or use the locked destination. Keep the existing assertions unchanged either way.

### 6. Risk Assessment

**Medium.** The dispatch and preservation strategy is concrete; the remaining issue is authorization of a documented contract deviation.

## 28-03

### 1. Summary

Implements the provisional D-06 drift semantics and adds fixture-proven clear-chord and same-directory declarations.

### 2. Cycle 1 findings status

- **H3 / A5 — resolved as wording and scope.** `28-03-PLAN.md:35-38,153-154` now calls the tests sequential proxies and leaves true races held out. The pre-existing check/replace window remains, as shown in `installer/agent_settings.py:562-569` and `installer/atomic.py:44-52`.
- **Broad `-k` selector — disposition accepted with a residual test-selection limitation.** `28-03-PLAN.md:170-176` supplements the count with named-source checks.
- **Orphan `clear_binding` — still present by explicit plan decision.** `28-03-PLAN.md:76,211` acknowledges no production caller until phase 29. It conflicts with the literal rule at `.claude/architecture.md:24-26`, although the plan records the rationale.
- **D-06 provisional status — retained as requested**, not reopened (`28-03-PLAN.md:73-74,259-261`).

### 3. Strengths

- The decision tables distinguish a deleted recorded region from a present stale region (`28-03-PLAN.md:103-123`), consistent with the existing deleted-region test at `tests/test_version_status.py:7054-7063`.
- The planned conflict test protects a user binding added outside the owned region (`28-03-PLAN.md:149`).

### 4. Concerns

- **LOW — held-out concurrency claims remain unverified.** Sequential tests at `28-03-PLAN.md:153-154` cannot establish the interleavings described in `28-SPEC.md:89,94`. The plan now says so; this is a residual risk, not a claim that the revision failed to disclose it.

### 5. Suggestions

Carry the untested race and the orphan-helper exception into phase verification rather than presenting either as independently proven.

### 6. Risk Assessment

**Medium.** The behavior matrix is specific, but reconfigure newly rewrites recorded files and relies on the existing non-atomic compare-before-commit boundary.

## 28-04

### 1. Summary

Adds a zsh-owned shell-init widget and updates the onboarding skill’s rule and conflict attribution.

### 2. Cycle 1 findings status

- **H4 — resolved for the sandbox failure.** The interactive `pty.fork`/`execve` test is removed (`28-04-PLAN.md:74,83,144`). The existing `zsh -n` route is compatible with the no-exec branch in `tests/sandbox.py:464-499` and is parametrized over shell-init tools at `tests/test_tweaks.py:373-381`. See the separate emitted-byte concern below.
- **H6 — resolved against the expressly provisional amended SPEC.** I ran all eight `apply_block` → `strip_block` pairs from `28-04-PLAN.md:143`; all matched. The underlying behavior follows `installer/shellrc.py:217-220,234-244`. Owner confirmation remains flagged as requested.
- **A3 — resolved in the plan.** `28-04-PLAN.md:195` updates the attribution while retaining the phrase pinned at `tests/test_tool_onboarding_skill.py:367-381`.
- **A6 / H5 — resolved for the new widget.** `${ZSH_VERSION-}` is specified at `28-04-PLAN.md:105,142`; older guards remain unchanged at `installer/tweaks.py:93-98`.
- **A7 — resolved.** All three omitted test files appear in `28-04-PLAN.md:158`.
- The removal-test limitation is documented by the existing running-shell warning at `installer/policy.py:41-54`.

### 3. Strengths

- The widget reuses the existing install-tuning and removal lifecycle at `installer/post_install.py:280-304` and `installer/app.py:632-637`.
- The revised round-trip cases include empty, newline-only, missing-final-newline, and excess-blank-line inputs.

### 4. Concerns

- **HIGH — the planned test does not verify the SPEC’s emitted bytes.** `28-SPEC.md:98` calls for the exact ESC bytes, whereas `28-04-PLAN.md:142` asserts literal `\033` spellings and explicitly asserts that no ESC byte is present in the rendered block. Syntax checks at `tests/test_tweaks.py:359-381` do not execute the widget. The recorded one-off probe at `28-04-PLAN.md:119` is useful evidence, but it is not a regression test of the implemented widget. Require a safe automated emitted-byte check, or an explicit SPEC amendment that accepts source-spelling-only verification.
- **LOW — acceptance grep contradicts the required comment.** `28-04-PLAN.md:153` requires the source comment to contain `${ZSH_VERSION-}`, as well as the widget body at `:105`; `:171` expects exactly one matching line. Following both instructions gives at least two. Update the count or omit the spelling from the comment.
- **LOW — “system tier means never installs” is inaccurate.** `28-04-PLAN.md:76` makes that inference, but `.claude/architecture.md:28-40` defines tier as a browsing label, and `installer/registry.toml:562-583` provides zsh install methods. This does not negate the existing-host reconfigure path.

### 5. Suggestions

Add a sandbox-compatible behavioral check for the emitted byte sequence and startup binding order, without weakening the launch guard. Keep the owner’s real-Mac and multi-line-prompt UAT items in `28-VALIDATION.md:65-70`.

### 6. Risk Assessment

**Medium to high until emitted-byte verification is settled.** Source and parse checks cannot alone establish what the running widget emits or whether a later shell initialization changes its binding.

## Cross-plan comparison

- **Validation-map mismatch:** `28-VALIDATION.md:32` says targeted tests run *after* each task commit, while the plans run them before each commit, e.g. `28-01-PLAN.md:66-67` and `28-04-PLAN.md:80-81`. `28-VALIDATION.md:34` also says to push after each wave, while every plan says never push, e.g. `28-04-PLAN.md:84`. Reconcile the execution owner and timing; do not infer push consent.
- **Cycle 1 status:** H1, H4’s sandbox defect, H6 under the provisional amendment, and A1–A7 are addressed as described above. H2 is clarified; H3 is disclosed rather than fixed; H5 is fixed for the new block; H7 depends on actual worktree isolation. The explicitly deferred test-selector, orphan-helper, running-shell-removal, and older-guard points remain disclosed.
- **Commit-hook feasibility:** I inspected the prescribed changes and the strict-tool configuration at `pyproject.toml:39-45,62-64`; I did **not** implement the plans or run their commit hooks, targeted suites, `make validate`, or `make test`. Apart from the specific issues above, hook feasibility remains unproven.

**Skipped / risk:** No production files were changed and no host-mutating command was run. Real terminal behavior and concurrent write interleavings remain outside this review’s verification.

---

## Consensus Summary

One grounded reviewer ran (`opencode-referee-one`; its section cites `file:line` throughout and carries no evidence-discount marker), so nothing is corroborated by a second lane and there are no "Agreed" items. Everything below is the orchestrating reviewer's own verification.

### Cycle 1 findings: status against the current plans

| ID | Cycle 1 | Status now | Evidence |
|---|---|---|---|
| H1 | 28-01: `_marker` to `marker` plus the loop-local `marker` gives `UnboundLocalError` | **Resolved** | 28-01-PLAN.md:157 renames the loop-local to `text_line` (assignment and both comparisons); acceptance 28-01-PLAN.md:193. Scratch copy: plan 28-01 Task 2 applied by script, then `ruff check`, `ruff format --check`, `pyright` strict on `installer/terminal_regions.py` and `installer/terminal_shell.py`, and `vulture` are clean once the F401 imports the plan names are removed; `tests/test_terminal_shell.py`, `tests/test_post_install.py`, `tests/test_version_status.py`, `tests/test_setup.py`, `tests/test_reachability.py` and the onboarding tests pass, except `test_verdict_files_before_and_after` (it needs the repository's `.planning` tree, which the scratch copy lacks) and `test_conflicts_names_the_real_partial_lines` (it reads the moved literal and fails until the plan's one-line path edit is applied, then passes). No other local or parameter of a moved body collides with a new public name. |
| H4 | 28-04: pty probe `os.execve(zsh -f -i)` refused by the launch guard | **Resolved** | 28-04-PLAN.md:74,83,144: the pty probe is dropped. `tests/sandbox.py:464-505` returns early for an `-n` cluster; in the scratch copy with zsh added to `SHELL_INIT_TOOLS` the parametrized `bash -n` and `zsh -n` tests ran 17 passed (the 16 parse cases plus the id-list test), none skipped. Dropping the probe was one of the two options named in cycle 1; see A8 for the residual wording gap. |
| H6 | 28-04: stated round-trip limit false, locked SPEC unmet | **Resolved** against the provisional amendment | The SPEC R3 rows were amended (a7a3a9c8, corrected in ecd3d9af, flagged "needs confirmation", backlog 999.27); the plan implements them as written and does not reopen them. Measured in scratch HOMEs through `write_tweak` then `remove_tweak` with the neovim and the zsh bundle: all eight pinned pairs match exactly (`""`, `"\n"`, `"\n\n"` to `""`; `"a"`, `"a\n"`, `"a\n\n"`, `"a\n\n\n"` to `"a\n\n"`; `"a\nb\n"` to `"a\nb\n\n"`), and so do `"\na\n"`, `"a\n \n"`, `" \n"`, `"a  "` and `"a\n\n\n\nb\n\n\n"` for the stated rule (original with trailing newlines removed, then one blank line if anything is left, else empty). CRLF files are normalized by `read_text` before the rule applies; that is pre-existing shared `shellrc` behavior outside this phase and not in the eight pairs. |
| A1 | say every reference in a moved body is renamed, rename the loop-local | **Resolved** | same evidence as H1; the reference list at 28-01-PLAN.md:156 matches the names the moved bodies actually use (checked by the scratch build). |
| A2 | AST check narrower than its claim | **Resolved** | 28-01-PLAN.md:176-177. Re-ran the check logic against HEAD: 48 `FunctionDef` nodes, 48 unique names, 0 async, 16 exclusions (14 moved plus `_sync_alacritty`, `apply_alacritty_keys`), `BODIES-UNCHANGED 32`, no `STALE` and no `CHANGED` line; in the scratch copy after the move it prints `BODIES-UNCHANGED 32` with no `STALE`, `CHANGED` or `NOT-MOVED` line. The check exits 0 on a mismatch, but `fails_when` names the lines to look for, so nothing is invisible to the executor. |
| A3 | skill Conflicts attribution stale | **Resolved** | 28-04-PLAN.md:195. Applied in the scratch copy: `tests/test_tool_onboarding_skill.py` (rule (c) needle and both Conflicts pins) passes; the replaced sentence boundaries ("Today that result is the" to "exact wording.") exist exactly once at SKILL.md:224. |
| A4 | reverse completeness guard has no failing fixture | **Resolved** | 28-02-PLAN.md:187,213: `{**TERMINAL_KEYS, "ghost": ...}` gives `extra_rows == {"ghost"}`. |
| A5 | concurrency backstops overstated | **Resolved** | 28-01-PLAN.md:215, 28-02-PLAN.md:235, 28-03-PLAN.md:35-38,77: both rows stay held-out backstops, the two tests are named and described as sequential proxies, and the real guarantee is stated with the verified lines (`installer/agent_settings.py:562-569` check, `installer/atomic.py:44-52` separate replace). |
| A6 | `$ZSH_VERSION` under bash `set -u` | **Resolved** (one acceptance slip, A10) | 28-04-PLAN.md:105,142: `${ZSH_VERSION-}`. The scratch body sources cleanly under `bash -eu`; the older `_guarded_init` spelling (`installer/tweaks.py:96`) is deliberately left alone (28-04-PLAN.md:274). |
| A7 | verify omitted three test files | **Resolved** | 28-04-PLAN.md:158 lists them; all 13 files pass in the scratch copy (the zsh bundle and registry edit applied). |

Cycle 1 H2, H3, H5 and H7 were downgraded in cycle 1 and stay closed (H2 by A1, H3 and A5 as wording, H5 by A6, H7 as workflow isolation: `files_modified` of 28-02 and 28-04 stay disjoint and `workflow.use_worktrees` is true).

### Disposition of referee-one's findings (verified against source)

| # | Plan | Referee-one claim | Verified evidence | Disposition |
|---|---|---|---|---|
| R1 | 28-04 | HIGH (stray opening bullet): the zsh widget execution order is untested, because Oh-My-Zsh's bindings can come later in `.zshrc` (`installer/omz.py:411-420`) | `installer/omz.py:411-420` does append `source $ZSH/oh-my-zsh.sh` to the end of a `.zshrc` that lacks it, so OMZ can load after `~/.myshellrc`. But OMZ's only key-bindings action is `bindkey -e` (`~/.oh-my-zsh/lib/key-bindings.zsh:19`), which relinks the main keymap to `emacs` and rebinds no key; no file under OMZ's `lib/` or the `vi-mode`, `fzf` and `zsh-interactive-cd` plugins mentions `^L`, and no `bindkey` line in any OMZ plugin does. The widget binds `emacs`, `viins` and `vicmd` explicitly for exactly this reason (28-CONTEXT.md:42, D-08). A later `bindkey -e` therefore does not undo the binding. What remains is the visual-redraw UAT already listed at 28-VALIDATION.md:70, which cannot run in the sandbox. | **Downgraded to LOW, not counted** (claimed mechanism does not hold; residual risk is the recorded manual UAT) |
| R2 | 28-04 | HIGH: the planned test checks escape spellings, not the exact emitted bytes the SPEC calls for (28-SPEC.md:98) | Partly true. 28-CONTEXT.md:43 (D-09) defines the always-on layer as a pty-free bytes check on the rendered block and calls the pty probe an optional backstop, and the plan implements that layer and records why the file can hold only the spelling (28-04-PLAN.md:27). But ROADMAP.md:105 (success criterion 3) says "byte-level test of the emitted sequences" and 28-SPEC.md:98 says "exact escape bytes ... as bytes, not rendered text", and with the probe dropped no test observes what zsh emits. A sandbox-compatible check exists and was verified: in the scratch copy, `subprocess.run(["zsh", "-f", "-c", r"print -n '\033[H\033[2J'"])` passed the autouse guard (`tests/sandbox.py:464-505`: a `-c` script of one builtin is checked by `check_script`) and returned `b"\x1b[H\x1b[2J"`. It is not a pty and not an interactive shell. | **Downgraded to MEDIUM, counted as actionable A8** (no hard defect: the SPEC acceptance at 28-SPEC.md:75 says "widget text carries", D-09 is met, and the owner's UAT stands; but the roadmap wording is only met at the spelling level) |
| R3 | 28-02 | MEDIUM: explicit deviation from locked D-12 (the four imports point at a test module, not `installer.terminal_keys`) | True: 28-CONTEXT.md:35 names `installer.terminal_keys`; 28-02-PLAN.md:72,133 point the four lines at `tests.test_terminal_keys`, with a sound reason (a production wrapper would be an orphan helper, `.claude/architecture.md:24-26`; `tests/test_docs_only.py` already imports from `tests.test_docs`). The plan records the reason but not that a locked decision was changed, or that the owner must see it. | **LOW, counted as actionable A11** (flag the deviation for owner confirmation like the D-06 flag) |
| R4 | 28-01 | LOW: the AST guard exits 0 on a mismatch and keys by name | Verified: it prints lines and exits 0; names are unique today (48 of 48). `fails_when` already tells the executor to fail on the lines. | **Not actionable** |
| R5 | 28-04 | LOW: the `${ZSH_VERSION-}` acceptance grep contradicts the required source comment | Verified: 28-04-PLAN.md:153 makes the comment carry the spelling and the body carries it too; in the scratch copy `grep -cF '${ZSH_VERSION-}' installer/tweaks.py` prints 2, while 28-04-PLAN.md:171 expects exactly 1. | **LOW, counted as actionable A10** |
| R6 | 28-04 | LOW: "system tier means the installer never installs zsh" is inaccurate | Verified: `.claude/architecture.md:28-40` defines tier as a browsing label and `installer/registry.toml:562-583` gives zsh dnf, apt, pacman and brew methods. The sentence is inherited from locked D-07 (28-CONTEXT.md) and no task depends on it. | **Not counted** (prose only) |
| R7 | cross-plan | VALIDATION.md:32 says the targeted tests run after each task commit and :34 says push per wave, while the plans run them before the commit and say never push | The per-task map rows now match the plans (same file lists: 28-01 Task 2, 28-02, 28-03 and 28-04 Task 1 with the 13 files). The cadence lines describe the orchestrator (a hook runs the static gates at commit, the orchestrator pushes per wave), not the executor, who sees only the plan. | **Not counted** (wording of a validation cadence) |
| R8 | 28-02 | H7 conditionally resolved by worktree isolation | Same as cycle 1 H7. | **Not counted** |
| R9 | 28-03 | LOW: held-out concurrency claims remain unverified; `clear_binding` has no production caller | Both are disclosed with rationale (28-03-PLAN.md:35-38,76-77); SPEC R3 and 28 D-13 require the proof on a fixture row. | **Not counted** (explicit rationale) |

### New defects the revision introduced (orchestrating reviewer's own pass)

- **28-01 acceptance count cannot hold (MEDIUM, actionable A9).** 28-01-PLAN.md:190 expects `grep -c 'from installer.terminal_regions import' installer/terminal_shell.py` to print 1. The plan imports thirteen names under old local aliases (28-01-PLAN.md:168), and the project's ruff config selects `I` (`pyproject.toml:40`) with isort's default of one statement per `as` import: a `from installer.terminal_regions import (IMPORTS as _IMPORTS, ...)` block is rewritten into separate statements (checked with `ruff check --select I --diff`). In the scratch copy the count is 14. The executor must pass the commit hook, so the criterion fails or tempts a combined import the hook rejects.
- **28-04 acceptance count cannot hold (LOW, actionable A10)**: see R5.
- **28-04 emitted-sequence wording (MEDIUM, actionable A8)**: see R2.
- **28-02 locked D-12 deviation unflagged (LOW, actionable A11)**: see R3.
- Checked and found sound: the eight round-trip pairs; the `text_line` rename and every other moved body (no remaining local or parameter collision; `_drop_created_config`'s parameter `marker` stays safe because `terminal_keys` does not import `marker`); the AST check counts (48, 16, 32); the golden facts (re-run in a scratch HOME on the current code: region bytes, `terminal-tuning-alacritty` = `written\n`, `terminal-alacritty-created` = `created\n~/.config\n~/.config/alacritty\n`, strip leaves nothing); the `-k` count gates (28-02 `-k "completeness or without_a_row"` gives six tests; 28-03 `-k "same_directory or clear or declared_set"` gives seven; 28-04 `-k "zsh_clear or zsh_removal or stable_ids"` gives eleven; the 28-04 parse command gives 16 with zsh, 8 plus 8 skipped without); the `SHELL_INIT_TOOLS` tuple stays on one line under ruff format (91 characters); the registry `awk` range finds `post_install` once; the `tests/test_terminal_shell.py` monkeypatches (`atomic_write_text` at :195, `read_settings` at :1283) keep their targets because `terminal_shell` still uses both names; vulture runs at `min_confidence = 80` over `installer` and `devtools` only, so a function used only by tests (`clear_binding`) is not reported; `${ZSH_VERSION-}` sources cleanly under `bash -eu`.

### Agreed Strengths

Single reviewer, confirmed by the orchestrating reviewer's reading and runs: golden characterization precedes the move; the loop-local rename and the explicit rename list make the move compile and type-check; the AST check now covers every kept body; the pty probe is gone and the `zsh -n` route works under the launch guard; the eight pinned pairs are exact; the dispositions ledgers in each plan map to the cycle 1 findings with line references.

### Agreed Concerns

None corroborated by a second lane (one reviewer ran).

### Divergent Views

None. D-06 and the R3 amendment stay provisional as instructed; this review did not reopen them and the plans implement them as written (28-03-PLAN.md:22-24,73-74; 28-04-PLAN.md:30,73).

### Cycle 2 counts

- HIGH, counted: 0 (referee-one's two HIGHs were verified: R1 downgraded to LOW, R2 downgraded to MEDIUM; all three cycle 1 HIGHs, H1, H4 and H6, are resolved).
- Actionable non-HIGH: 4.

| ID | Sev | Plan | Change still needed in PLAN.md |
|---|---|---|---|
| A8 | MEDIUM | 28-04 (Task 1) | ROADMAP.md:105 and 28-SPEC.md:98 ask for a byte-level test of the emitted sequences, and no test observes what zsh emits. Add one skipif-no-zsh test that extracts the two `print -n '...'` arguments from `_ZSH_CLEAR_BODY` and runs each through `subprocess.run(["zsh", "-f", "-c", ...])`, asserting the exact bytes `b"\x1b[H\x1b[2J"` and `b"\x1b[3J"` (verified to pass the autouse guard), keeping the always-on spelling test for hosts without zsh; amend the executor rule at 28-04-PLAN.md:83 and T-28-11 (28-04-PLAN.md:236) so a non-interactive `zsh -f -c` of builtins is allowed while pty and interactive shells stay banned; or record in the plan, the SUMMARY and 28-SPEC.md that spelling-level proof plus the owner's Mac UAT is the accepted reading of "emitted sequences". |
| A9 | MEDIUM | 28-01 (Task 2) | Change 28-01-PLAN.md:190, `grep -c 'from installer.terminal_regions import' installer/terminal_shell.py` [EXPECT==1], to a count the isort-formatted file can meet (for example `[EXPECT>=2]`, or `grep -c 'terminal_regions import'` with `EXPECT>=1`), and note that ruff's isort keeps each `as` import on its own statement. |
| A10 | LOW | 28-04 (Task 1) | Change the 28-04-PLAN.md:171 acceptance `grep -cF '${ZSH_VERSION-}' installer/tweaks.py` [EXPECT==1] to `EXPECT>=1` (the comment at :153 and the body both carry the spelling), or drop the spelling from the comment at :153; keep the "only in the zsh widget body" intent by grepping the body line instead. |
| A11 | LOW | 28-02 (decision record) | Record the change of locked D-12 (the four imports target `tests.test_terminal_keys`, not `installer.terminal_keys`) as an owner-visible deviation: add it to the executor's SUMMARY requirements and the ledger with a "needs owner confirmation" flag, as is done for D-06, or note that the owner approved it (28-02-PLAN.md:72,85). |

---

## Verification coverage

Source-grounding pass (`plan_review.source_grounding: true`). Effective authority from `drift-guard authority` is `intel` (`intel.enabled: true`; `plan_review.source_grounding_authority` is `grep`). The intel adapter analyzes JavaScript only, so every Python symbol was resolved with grep and a read of the source (adapter `grep`). Symbols the plans create (`installer/terminal_regions.py`, `installer/terminal_keys.py`, `tests/test_terminal_keys.py` and everything under each plan's "Artifacts this phase produces") were excluded.

Verdict counts this cycle: 95 VERIFIED, 0 MISSING, 0 AMBIGUOUS. One search came back empty on purpose: `.github/workflows/ci.yml` has no `zsh` mention (28-CONTEXT.md D-09 says so). One search of mine had a bad pattern (`snapshot_matches`, found at `installer/atomic.py:113` by a direct search, not cited by a plan). No `hardBlock`, no needs-acknowledgement symbol. Every `file:line` the plans cite for existing code was spot-checked at the cited line this cycle: `installer/agent_settings.py:562-569`, `installer/atomic.py:44-52`, `tests/conftest.py:137-150`, `tests/sandbox.py:464-505,539-552`, `installer/shellrc.py:203-239`, `installer/terminal_shell.py:98-138,470-757`, `tests/test_terminal_shell.py:195,1283`, `tests/test_tool_onboarding_skill.py:225,367-381`, `.claude/skills/tool-onboarding/SKILL.md:198,224`, `installer/policy.py:41-54`, `.claude/architecture.md:24-26`.

VERIFIED (first declaration found; full run in the scratchpad `c2/ground2.out`):

```
VERIFIED  replace_owned_region -> installer/terminal_shell.py:102
VERIFIED  _commit_alacritty -> installer/terminal_shell.py:604
VERIFIED  _keys_plan -> installer/terminal_shell.py:583
VERIFIED  _user_document -> installer/terminal_shell.py:528
VERIFIED  _snapshot_text -> installer/terminal_shell.py:519
VERIFIED  _imports_files -> installer/terminal_shell.py:547
VERIFIED  _table -> installer/terminal_shell.py:539
VERIFIED  _strip_alacritty_region -> installer/terminal_shell.py:659
VERIFIED  apply_alacritty_keys -> installer/terminal_shell.py:671
VERIFIED  alacritty_keys_pending -> installer/terminal_shell.py:710
VERIFIED  strip_alacritty -> installer/terminal_shell.py:726
VERIFIED  _drop_created_config -> installer/terminal_shell.py:742
VERIFIED  KEYS_PENDING -> installer/terminal_shell.py:474
VERIFIED  _sync_alacritty -> installer/terminal_shell.py:633
VERIFIED  sync_terminal_shells -> installer/terminal_shell.py:893
VERIFIED  _tune_terminal -> installer/post_install.py:385
VERIFIED  _apply_terminal_tuning -> installer/post_install.py:393
VERIFIED  apply_install_tuning -> installer/post_install.py:426
VERIFIED  run_post_install -> installer/post_install.py:452
VERIFIED  _tune_shell_init -> installer/post_install.py:280
VERIFIED  _set_login_shell -> installer/post_install.py:273
VERIFIED  _terminal_tuning_fact -> installer/version_status.py:821
VERIFIED  _tuning_fact -> installer/version_status.py:777
VERIFIED  TUNING_PENDING -> installer/version_status.py:773
VERIFIED  _TERMINAL_ROWS -> installer/version_status.py:734
VERIFIED  _after_removal -> installer/app.py:611
VERIFIED  SHELL_INIT_TOOLS -> installer/tweaks.py:90
VERIFIED  tweak_block -> installer/tweaks.py:265
VERIFIED  write_tweak -> installer/tweaks.py:271
VERIFIED  remove_tweak -> installer/tweaks.py:238
VERIFIED  shell_init_bundle -> installer/tweaks.py:506
VERIFIED  shell_init_record -> installer/tweaks.py:408
VERIFIED  forget_shell_init -> installer/tweaks.py:439
VERIFIED  _shell_init -> installer/tweaks.py:116
VERIFIED  _NVIM_EDITOR_BODY -> installer/tweaks.py:113
VERIFIED  _DOCKER_BODY -> installer/tweaks.py:55
VERIFIED  shellrc.apply_block -> installer/shellrc.py:203
VERIFIED  shellrc.strip_block -> installer/shellrc.py:223
VERIFIED  missing_dirs -> installer/agent_settings.py:584
VERIFIED  read_settings -> installer/agent_settings.py:556
VERIFIED  write_if_unchanged -> installer/agent_settings.py:562
VERIFIED  remove_created_dirs -> installer/agent_settings.py:594
VERIFIED  atomic_write_text -> installer/atomic.py:76
VERIFIED  FileSnapshot -> installer/atomic.py:82
VERIFIED  POST_INSTALL_ACTIONS -> installer/model.py:130
VERIFIED  load_tools -> installer/model.py:584
VERIFIED  compose.SHELL_INIT_TOOLS -> installer/compose.py:77
VERIFIED  schedules -> installer/schedules.py:43
VERIFIED  _alacritty_tool -> tests/test_terminal_shell.py:1118
VERIFIED  _alacritty_toml -> tests/test_terminal_shell.py:1122
VERIFIED  test -> tests/test_terminal_shell.py:1130
VERIFIED  _remove_alacritty -> tests/test_terminal_shell.py:1140
VERIFIED  changed_before_commit -> tests/test_terminal_shell.py:1271
VERIFIED  would_not_reparse -> tests/test_terminal_shell.py:1292
VERIFIED  test_bundles_have_stable_ids_and_order -> tests/test_tweaks.py:47
VERIFIED  guarded -> tests/test_tweaks.py:360
VERIFIED  _tool_block -> tests/test_model.py:1369
VERIFIED  docs_only -> tests/test_docs_only.py:209
VERIFIED  house -> tests/test_docs_only.py:331
VERIFIED  skipif -> tests/test_shellrc.py:708
VERIFIED  autouse -> tests/conftest.py:4
VERIFIED  make -> Makefile:27
VERIFIED  make -> Makefile:60
VERIFIED  make -> Makefile:66
VERIFIED  SKILL -> .claude/skills/tool-onboarding/SKILL.md:198
VERIFIED  conflicts -> tests/test_tool_onboarding_skill.py:367
VERIFIED  _alacritty_shipped -> tests/test_version_status.py:6996
VERIFIED  _settled_states -> tests/test_version_status.py:4621
VERIFIED  refusal -> tests/test_post_install.py:1129
VERIFIED  tests/test_setup.py -> tests/test_setup.py:5054
VERIFIED  sandbox.check_shell_args -> tests/sandbox.py:464
VERIFIED  sandbox.guarded_os_call -> tests/sandbox.py:700
VERIFIED  conftest.no_unchecked_os_exec -> tests/conftest.py:138
VERIFIED  strip_tweak_block -> installer/tweaks.py:280
VERIFIED  record_shell_init -> installer/tweaks.py:432
VERIFIED  applicable_bundles -> installer/tweaks.py:456
VERIFIED  _guarded_init -> installer/tweaks.py:93
VERIFIED  omz.ensure_zshrc_template -> installer/omz.py:424
VERIFIED  shellrc.ensure_source -> installer/shellrc.py:380
VERIFIED  policy.py -> installer/policy.py:114
VERIFIED  backlog -> .planning/ROADMAP.md:646
VERIFIED  architecture -> .claude/architecture.md:24
VERIFIED  SKILL -> .claude/skills/tool-onboarding/SKILL.md:224
VERIFIED  SKILL -> .claude/skills/tool-onboarding/SKILL.md:198
VERIFIED  rule -> tests/test_tool_onboarding_skill.py:225
VERIFIED  shell_source -> tests/test_tool_onboarding_skill.py:378
VERIFIED  bundles -> tests/test_tweaks.py:353
VERIFIED  zsh -> tests/test_tweaks.py:375
VERIFIED  test_pending_tuning_shell_init -> tests/test_version_status.py:6753
VERIFIED  untuned -> tests/test_version_status.py:7066
VERIFIED  refusal -> tests/test_post_install.py:1138
VERIFIED  install -> tests/test_docs.py:301
VERIFIED  schedules -> installer/schedules.py:24
VERIFIED  compose -> installer/compose.py:77
```

UNCHECKABLE (never treated as verified or missing):

- Function signatures of every cited callable (the `grep` and `intel` adapters cannot assert signatures). The plans' new signatures (`commit_region`, `apply_terminal_keys`, `terminal_keys_pending`, `strip_terminal_keys`, `_tune_terminal`, `_terminal_tuning_fact`, `clear_binding`, `_render`) were checked only by reading the old bodies and by the scratch build of plan 28-01 (pyright strict on the moved module); plans 28-02 and 28-03 were not built.
- Counts asserted from the executor's future tree for plans 28-02 and 28-03 ("13 passed", "6 passed", "15 passed", "7 passed", the `^def test_drift_` count of 9): recomputed by reading the plans' own test lists, all consistent. The 28-01 and 28-04 Task 1 counts were reproduced in the scratch copy (`BODIES-UNCHANGED 32`; 17 passed for the id-list plus parse selection).
- The zsh widget's runtime behavior under a real pty (research probed it once by hand, 28-04-PLAN.md:119; no test observes it, see A8) and its binding order after full shell startup (R1 shows no OMZ file rebinds `^L`, but a third-party plugin could).
- Whether `ubuntu-latest` and `macos-latest` CI runners ship zsh: no workflow mention, so CI may run the spelling test only (the `zsh -n` tests skip with a reason).
- macOS-specific behavior (Terminal.app, iTerm2, `ESC[3J`): out of scope here and deferred to the owner's Mac UAT.

Cross-artifact fact-drift pass (advisory; adds nothing to the counts):

- Phase status (`drift-guard phase-status --phase 28`): verdict `uncheckable`. `.planning/STATE.md` still reports `current_phase: 27` with `status: verifying` ("Phase complete — ready for verification") while ROADMAP.md lists Phase 28 as "Not started"; the seam could not match a state to phase 28. Recorded, not read as consistent. Authority for status is STATE.md, which has not been advanced to phase 28 (same as cycle 1).
- Success criteria (ROADMAP.md:101-106 vs PLAN `must_haves.truths`): criterion 1 (byte-identical region, no Alacritty-id branch) matches 28-01 and 28-02, with the one `_TERMINAL_ROWS` shell-sync row kept by 28 D-04; criterion 2's amended reading (28 D-06) matches 28-03; criterion 4 matches 28-03 (KEYS-04). Criterion 3 says "byte-level test of the emitted sequences" while 28-04's truths at :27 and :38 prove the rendered block's escape spelling and the `zsh -n` parse, not emission; the plan adds no contradicting truth but proves less than the wording. Reported as A8, advisory only.
- Requirement IDs (ROADMAP.md `**Requirements:** KEYS-01, KEYS-02, KEYS-03, KEYS-04` vs PLAN `requirements:`): 28-01 KEYS-01, 28-02 KEYS-01 and KEYS-02, 28-03 KEYS-02, KEYS-03 and KEYS-04, 28-04 KEYS-03: all four covered, none undefined. No drift.
- Glossary (CONTEXT.md decisions vs plan usage): D-01 through D-15 match except three recorded deviations: D-04's `TERMINAL_KEYS[tool.id]` becomes `.get` plus a refusal (owner rule 5), D-12's import target becomes `tests.test_terminal_keys` (A11: not flagged as a deviation), and D-09's optional pty probe is dropped (allowed: D-09 calls it optional).
- SPEC vs plan (outside the four judgment pairs): SPEC R3 adjacency and prohibition as amended in a7a3a9c8 and ecd3d9af match 28-04's rule and its eight pairs (measured). VALIDATION.md rows match the revised plans (the `BODIES-UNCHANGED 32` text, the ghost fixture, the no-pty wording, the 13-file command); the cadence lines at VALIDATION.md:32,34 describe the orchestrator and are not a contradiction.
- Plan-Revision Conflicts block: no entries existed; the begin/end delimiters and the block between them were carried over byte-for-byte from the previous file.
