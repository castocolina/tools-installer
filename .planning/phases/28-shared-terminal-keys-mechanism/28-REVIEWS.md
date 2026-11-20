---
phase: 28
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-20T12:02:37Z
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

## Lane Log (convergence cycle 1)

Reviewer selection: `review.default_reviewers = ["opencode-referee-one"]` (router-env/my-referee-one), the owner-required first lane. Failover order if it failed: opencode-referee-two, then opencode-referee-three. Every opencode child ran with stdin closed (`< /dev/null`) under a timeout.

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 08:18 | opencode-referee-one | one-shot probe (`Reply with the single word OK.`, 120 s) | FAILED: `ECONNREFUSED: Unable to connect` on every retry (provider backend down) |
| 08:19 | opencode-referee-two | probe (90 s) | FAILED: `ECONNREFUSED` on every retry |
| 08:21 | opencode-referee-three | probe (90 s) | FAILED: router reachable, upstream `claude/claude-sonnet-5-5-xhigh: rate limit, all credentials cooling down (HTTP 429)`; no reply within 90 s |
| 08:26 | opencode-referee-three | second probe (200 s) | FAILED: HTTP 429 again (`claude-sonnet-5-5` then `claude-opus-5-5`); exit 124 |
| 08:26 to 08:37 | opencode-referee-three | real review through `review-lane invoke` | FAILED: the lane returned the "no assistant text" stub (`Failed to drain Session`, HTTP 429); no review produced |
| 08:38 to 08:46 | referee-one, two, three | 75 s probe loop, two rounds | FAILED: all timed out; the routers answered with upstream provider outages (`codex/gpt-6.1-terra-xhigh: Provider codex circuit breaker is open (HTTP 503)`, `glm-5.3-high: all credentials cooling down`, HTTP 429) |
| 08:53 to 09:02 | opencode-referee-one | real review, retry in the same cycle (lane order one, two, three, repeat); a 170 s probe at 08:49 had shown the codex provider circuit breaker still open (HTTP 503), but the full run went through | SUCCEEDED: 11,410 bytes, all four plan ids covered |

No other model was used. The review below is referee-one's, unedited. The orchestrating reviewer verified each of its HIGH findings against repository source before counting it (see the Consensus Summary).

## OpenCode Review (opencode-referee-one)

Using the plan-review checklist and codebase graph to check all four plans against the implementation and their verification commands. This is a read-only review.
The plans have concrete lifecycle and safety tests, but I’m checking a few places where the proposed tests may not exercise the behavior they claim—particularly drift, concurrency, and the shared row contract.
### Document Type

GSD · implementation plans. **Status: Issues Found — revise before execution.**

The review covered all four plans against the current source. The proposed `terminal_regions.py` and `terminal_keys.py` do not exist yet, so findings about them trace the specified move from today’s implementation rather than an executed refactor.

## 28-01

### 1. Summary

Characterize Alacritty’s current bytes, then move shared region primitives into a lower module without changing behavior.

### 2. Strengths

- The golden tests precede the move and cover user content, adjacent bindings, records and removal (`.planning/phases/28-shared-terminal-keys-mechanism/28-01-PLAN.md:113-127`). This protects the existing ownership and output contract.
- Keeping the shell-side read and write seams preserves the existing race-test monkeypatch (`installer/terminal_shell.py:637-655`; `tests/test_terminal_shell.py:1271-1289`).

### 3. Concerns

- **HIGH — The instructed rename introduces a local-name collision.** The plan renames `_marker` to `marker` and says `replace_owned_region` calls it (`28-01-PLAN.md:155-157`). But the moved body also assigns to a local variable named `marker` (`installer/terminal_shell.py:106-113`). Following both instructions makes the initial `marker(...)` call raise `UnboundLocalError`, blocking region operations.
- **HIGH — Other moved bodies retain references to names the plan removes.** The plan asks for verbatim bodies except names (`28-01-PLAN.md:155-162`), but `alacritty_config_path` calls `_xdg_config_home`, `_user_document` calls `_replace_owned_region`, and `_keys_plan` calls `_imports_files`, `_table` and `_KeysPlan` (`installer/terminal_shell.py:486-490,528-531,583-601`). Those names need explicit aliases or rewritten references in the new module.
- **MEDIUM — The AST check is narrower than its guarantee.** The one-liner compares only the names in its fixed set and treats a name missing from *both* versions as unchanged (`28-01-PLAN.md:174-175`). It does not establish that every other function body is unchanged, as claimed at `28-01-PLAN.md:193`.
- **MEDIUM — The onboarding source attribution becomes stale.** The plan moves the partial-binding literal and changes only the test’s source path (`28-01-PLAN.md:167`), while the skill still attributes the line to `terminal_shell.py` (`.claude/skills/tool-onboarding/SKILL.md:224`; `tests/test_tool_onboarding_skill.py:367-380`).

### 4. Suggestions

Explicitly map every renamed dependency, rename the local `marker` variable, and make the AST guard check the intended complete set and presence of each symbol. Update the onboarding attribution with its test.

### 5. Risk Assessment

**HIGH** — The mechanical move, as specified, can fail on the first region operation.

## 28-02

### 1. Summary

Move Alacritty’s lifecycle into an ID-keyed table, route the three dispatch sites through it, and add completeness and missing-row checks.

### 2. Strengths

- Deriving the record name from the table key preserves the existing `terminal-tuning-alacritty` contract (`28-02-PLAN.md:140-144`; `installer/terminal_shell.py:475-476,500-506`).
- The missing-row refusal avoids an uncaught lookup failure on reconfigure (`28-02-PLAN.md:147`; `installer/post_install.py:426-449`).
- The dispatch check correctly allows the remaining shell-sync Alacritty row while prohibiting key-handling references (`28-02-PLAN.md:148,153-156`; `installer/version_status.py:777-785`).

### 3. Concerns

- **MEDIUM — The reverse completeness guard has no failing fixture.** Both prescribed `extra_rows` checks expect an empty set (`28-02-PLAN.md:182-186`). An `extra_rows` implementation that always returns an empty set would pass, despite the promise that a table row without a declarer fails (`28-02-PLAN.md:214`).
- **MEDIUM — The existing race test does not cover the moved apply path.** The plan relies on the existing compare-before-commit protection (`28-02-PLAN.md:142,233`), but the cited test patches `terminal_shell.read_settings` and calls shell sync (`tests/test_terminal_shell.py:1271-1289`). After the move, keys apply reads through `terminal_keys`; the test does not exercise that route.
- **MEDIUM — Task 2’s RED sequence is not executable as described.** It instructs the executor to add the completeness helpers before writing and running their tests (`28-02-PLAN.md:188-193`); the runtime backstop already exists from Task 1. Following that order does not produce the claimed failing test run.

### 4. Suggestions

Add an extra-table-only ID fixture, a keys-apply compare-before-commit test, and a test-first order that produces meaningful RED evidence. Discover and run the other tests importing the edited modules as required by `AGENTS.md:40-49`.

### 5. Risk Assessment

**MEDIUM** — The lifecycle routing is specified, but two protective claims lack tests that prove them.

## 28-03

### 1. Summary

Implement the provisional D-06 drift semantics, then add a default clear chord and mandatory same-directory declaration to rows.

### 2. Strengths

- The decision tables distinguish recorded deletion, current regions, drift and refusal (`28-03-PLAN.md:102-122`), and preserve the existing user-deleted-region test (`tests/test_version_status.py:7054-7063`).
- The proposed `Writes` render is used for both writing and drift comparison (`28-03-PLAN.md:206-212`), avoiding a straightforward mismatch between those paths.
- The stated TOML escape is valid: a local `tomllib` check confirmed that JSON’s `"\f"` decodes to Ctrl+L (`28-03-PLAN.md:124`).

### 3. Concerns

- **HIGH — The concurrency backstops are sequential, and the underlying check is not atomic compare-and-swap.** The plan calls its cases interleaved/racing (`28-03-PLAN.md:35-38`) but specifies one operation followed by the other (`28-03-PLAN.md:152-153`). `write_if_unchanged` checks the snapshot and later performs a separate atomic replacement (`installer/agent_settings.py:562-569`; `installer/atomic.py:44-52`). An uninstall between those steps can be followed by a reconfigure write. The proposed tests cannot establish the SPEC’s race outcomes (`28-SPEC.md:89,94`).
- **MEDIUM — The focused test-count gate can pass on unrelated tests.** Its broad `-k "drift ..."` selector and “15 passed” threshold (`28-03-PLAN.md:169-170`) also select numerous existing drift tests (`tests/test_version_status.py:3927-4878,7028-7066`). The count does not prove the intended new matrix ran.
- **MEDIUM — `clear_binding` is knowingly left without a production caller.** The plan records that only fixture code calls it (`28-03-PLAN.md:73-76,192,210`), while the repository explicitly prohibits shared helpers retained solely for later use (`.claude/architecture.md:24-26`). The fixture also hard-codes `_FIXTURE_ROW`, so it does not prove that a different row’s `clear` value is consumed by generic production rendering.

### 4. Suggestions

Use controlled interleavings and state the outcomes the implementation can actually guarantee; strengthen synchronization if the SPEC’s race outcome remains required. Select the new tests by exact node IDs. Resolve the orphan-helper conflict by making the clear contract part of a real production path or obtaining an explicit rule exception.

### 5. Risk Assessment

**HIGH** — The plan overstates concurrency protection around writes to user configuration.

## 28-04

### 1. Summary

Add the managed zsh Ctrl+L widget through the existing shell-init lifecycle and update the onboarding rule.

### 2. Strengths

- The lifecycle reuses the existing shell-init writer, status and removal paths (`installer/post_install.py:280-304`; `installer/version_status.py:781-800`; `installer/app.py:632-637`).
- The plan separates an always-on rendered-text check from a live pty probe and records whether the latter runs (`28-04-PLAN.md:137-145,160-166`).

### 3. Concerns

- **HIGH — The prescribed pty launch is rejected by the test sandbox.** The test calls `os.execve` with `zsh -f -i` and no script (`28-04-PLAN.md:141`). The autouse fixture wraps `execve` (`tests/conftest.py:137-150`; `tests/sandbox.py:684-730`), and the shell argument guard rejects a shell with no script (`tests/sandbox.py:464-505,539-552`). The child therefore cannot run the specified probe under the stated fixtures.
- **HIGH — The bash guard is unsafe under nounset.** When zsh is on PATH, `[ -n "$ZSH_VERSION" ]` expands an unset variable in bash (`28-04-PLAN.md:101-103`). Sourcing the managed block from bash with `set -u` can terminate the shell; `bash -n` checks syntax, not execution. The block is intended for a file sourced by both shells (`installer/shellrc.py:380-390`).
- **HIGH — The accepted round trip contradicts the locked byte-identity criterion.** The plan knowingly permits an extra separator newline (`28-04-PLAN.md:30,73,140`), whereas the SPEC requires byte-identical restoration beside user content (`28-SPEC.md:95-96,110-113`). Moreover, `apply_block` strips *all* trailing newlines before appending (`installer/shellrc.py:217-220`), so inputs with more than two trailing newlines can lose bytes too.
- **MEDIUM — Removal testing proves future-file state, not a running shell’s state.** The plan says the widget must not remain after removal but only inspects the rc file (`28-04-PLAN.md:59-61,142`). The existing policy documents that removing a block cannot undefine functions already loaded in a running shell (`installer/policy.py:41-54`).

### 4. Suggestions

Specify a sandbox-compatible, reviewed pty test without disabling the guard. Use a nounset-safe shell guard and execute it under bash `set -u`. Either meet the byte-identity requirement for representative trailing-newline cases or obtain an explicit amendment. State the live-session limitation and verify the removal hint.

### 5. Risk Assessment

**HIGH** — The planned pty test cannot run as written, and the shell block can break a user’s nounset-enabled bash session.

## Cross-plan assessment

- **HIGH — Wave 2 is not independent in a shared checkout.** Plans 28-02 and 28-04 both run in wave 2 (`28-02-PLAN.md:6-7`; `28-04-PLAN.md:6-7`). Plan 04 edits `tests/test_version_status.py` and `tests/test_tool_onboarding_skill.py` (`28-04-PLAN.md:8-14`), while Plan 02 runs those files and requires no diff in them (`28-02-PLAN.md:153,165`). Concurrent edits, commits and whole-tree gates can invalidate each other’s checks. Serialize the plans or specify isolated worktrees and integration before Plan 03.
- **D-06 remains provisional**, as directed; this review did not reopen it. The plans should continue to surface that confirmation requirement (`28-03-PLAN.md:73-74,258-260`).
- The phase has valuable golden-byte and lifecycle coverage, but the concurrency, shell execution and exact-restoration claims need stronger evidence before the plans are ready.

**Not checked:** I did not execute the plans, full test suite, commit hooks, or real-terminal UAT. No repository files were changed.


---

## Consensus Summary

One reviewer produced a review this cycle (opencode-referee-one), so the multi-reviewer consensus gate does not engage and nothing here is corroborated by a second lane. The orchestrating reviewer therefore re-read the cited source for every HIGH before counting it. Referee-one carries no evidence-discount marker: its findings cite `file:line` throughout.

### Disposition of referee-one's HIGH findings (verified against source)

| # | Plan | Referee-one claim | Verified evidence | Disposition |
|---|---|---|---|---|
| H1 | 28-01 | Renaming `_marker` to `marker` makes `replace_owned_region` raise `UnboundLocalError` | `installer/terminal_shell.py:106` calls `_marker(...)` and `installer/terminal_shell.py:113` assigns a local `marker = line.rstrip("\r\n")` in the same function. Plan 28-01 Task 2 step 1 says to move `_marker` as `marker` with the body "VERBATIM except for the names" (28-01-PLAN.md:155-157). Python makes `marker` local for the whole function, so the call on line 106 is unbound. pyright strict would also flag it. | **HIGH, counts** |
| H2 | 28-01 | Other moved bodies keep references to names the plan removes | The bodies do reference the old names (`terminal_shell.py:490` `_xdg_config_home`, `:530` `_replace_owned_region`, `:584-586` `_imports_files`, `_table`, `_KeysPlan`), but the plan renames each of those in the same list (28-01-PLAN.md:155-162) and says "VERBATIM except for the names", so the references follow the renames. The plan does not say so in one sentence. | **Downgraded to MEDIUM** (clarity, actionable A1) |
| H3 | 28-03 | The concurrency backstops are sequential and the check is not an atomic compare-and-swap | Both true: `installer/agent_settings.py:562-569` checks the snapshot, then `installer/atomic.py:44-52` replaces in a separate step (a narrow time-of-check window), and 28-03-PLAN.md:152-153 specifies one call then the next while the must_haves (28-03-PLAN.md:35-38) say "interleaved". But SPEC marks both rows `backstop` / "held-out" (28-SPEC.md:89,94), the phase is behavior-preserving (the window pre-exists in the code being moved), and no real interleaving is in scope. The defect is the overstated wording, not a missing guarantee. | **Downgraded to MEDIUM** (actionable A5) |
| H4 | 28-04 | The pty probe's `os.execve` is rejected by the test sandbox | `tests/conftest.py:137-150` (autouse `no_unchecked_os_exec`) wraps `os.execve` through `guarded_os_call` (`tests/sandbox.py:685-697,700-730`). `zsh` is a shell name in the policy (`tests/sandbox.py:34,100-104`). For `["zsh", "-f", "-i"]`, `check_shell_args` (`tests/sandbox.py:464-505`) accepts `-f` and `-i`, finds no script, and raises `AssertionError("the suite tried to run a shell with no script; ...")` (`tests/sandbox.py:500-505`); the refusal is also recorded and fails the test at teardown (`tests/conftest.py:153-165`). A linuxbrew zsh on PATH is refused outright (`tests/sandbox.py:554-560`). The exception is raised in the `pty.fork()` child, which is a clone of the pytest worker and has no `os._exit` guard in the plan, so it would continue running the suite. Only `zsh -n` (no-exec) passes today (`tests/test_tweaks.py:373-382`). | **HIGH, counts** |
| H5 | 28-04 | `[ -n "$ZSH_VERSION" ]` is unsafe under bash `set -u` | True as a statement about bash, but it is the existing house idiom of every shell-init bundle (`installer/tweaks.py:96`, `_guarded_init`), so it is not new to this phase, and the guard line is pinned by the plan's own test. | **Downgraded to LOW** (actionable A6: use `${ZSH_VERSION-}` or record the precedent as an explicit rejection) |
| H6 | 28-04 | The accepted apply-then-strip round trip contradicts the locked byte-identity criterion | `28-SPEC.md:96,113` (edge row R3 adjacency and the second prohibition) require a scratch-HOME apply then strip to leave the file byte-identical. Running `shellrc.apply_block` then `strip_block` (installer/shellrc.py:203-239) over representative inputs gives: `""` same; `"a\n"` becomes `"a\n\n"`; `"a\n\n"` same; `"a\n\n\n"` becomes `"a\n\n"`; `"a"` becomes `"a\n\n"`; `"a\n\n\nb\n"` becomes `"a\n\n\nb\n\n"`; `"\n"` and `"\n\n"` become `""`. The plan states the limit as "byte-identical when it was empty or ended in a blank line" (28-04-PLAN.md:30,73,140), which is false for `"a\n\n\n"` and for the leading-newline files, and it relies on a shared function this phase does not change. The plan does flag the gap for the owner, but a locked SPEC verification is knowingly unmet and the stated limit is inaccurate. | **HIGH, counts** (resolve before execution: owner amendment of SPEC R3 adjacency wording, or a plan change that meets it; at minimum correct the stated limit and the test cases) |
| H7 | cross-plan | Wave 2 (28-02 and 28-04) is not independent in a shared checkout | `files_modified` of the two plans are disjoint (28-02-PLAN.md:8-15 vs 28-04-PLAN.md:8-14) and `.planning/config.json` sets `workflow.use_worktrees: true`; the no-diff checks use `git diff HEAD`, which ignores committed work. Plan 28-03 depends on both. The only residual risk is running them concurrently in one tree. | **Downgraded to LOW** (not actionable: wave isolation is the workflow's job) |

### Referee-one's MEDIUM findings (orchestrator judgment)

- 28-01 AST guard narrower than its claim: verified. The one-liner covers 13 named functions (all present at HEAD, so the "missing from both" case cannot occur), while 28-01-PLAN.md:193 says every other body is identical. Actionable A2.
- 28-01 skill attribution stale: verified (`.claude/skills/tool-onboarding/SKILL.md:224` names `installer/terminal_shell.py` and says "phase 28 settles the exact wording"; no plan settles it). Actionable A3.
- 28-02 reverse completeness guard has no failing fixture: verified (28-02-PLAN.md:182-186 only assert empty sets for `extra_rows`). Actionable A4.
- 28-02 existing race test does not cover the moved apply path: verified in part (`tests/test_terminal_shell.py:1271-1289` patches `terminal_shell.read_settings` and goes through `_sync_alacritty`, which stays; the keys apply path reads through `terminal_keys`). The apply path had no race test before either, so this is not a regression. Folded into A5.
- 28-02 Task 2 RED sequence: the plan itself says the backstop test "may pass at once; record that in the SUMMARY" (28-02-PLAN.md:188). Acknowledged, not actionable.
- 28-03 count gate can pass on unrelated tests: the `-k` selector is broad, but the acceptance greps (`grep -c '^def test_drift_' == 9`, the two named test greps) pin the new tests. Not actionable.
- 28-03 `clear_binding` has no production caller (architecture rule 5): the plan records the conflict and its rationale (SPEC R3 and 28 D-13 require the proof on a fixture row; phase 29 rows are the first callers; noted for the SUMMARY, 28-03-PLAN.md:73-76). That is an explicit rationale, so it is not actionable.
- 28-04 removal test checks rc bytes, not a running shell: `installer/policy.py:41-54` already documents the live-session limit. Not actionable.

### Additional findings from the orchestrating reviewer's own pass

- 28-04 Task 1 verify (28-04-PLAN.md:155) omits `tests/test_policy_tweaks.py`, `tests/test_uninstall_e2e.py` and `tests/test_schedules_lifecycle.py`, which import `BUNDLES`/tweak machinery and were outside the research's scratch run. `make test` would catch a break, but only after the task's commit. Actionable A7 (LOW).
- The `pty.fork()` child with no `os._exit` fallback (see H4) is part of the HIGH, not a separate item.

### Agreed Strengths

Single reviewer, confirmed by the orchestrating reviewer's reading: golden bytes are committed before the move (28-01); the dispatch counts in 28-02 match the code (`rg -c -i alacritty` gives 4/3/4 at HEAD in post_install.py/app.py/version_status.py and the single `_TERMINAL_ROWS` hit remains); the record names are preserved by deriving them from the dict key; the D-06 decision tables in 28-03 are consistent with the existing pins (`tests/test_post_install.py:1114-1126`, `tests/test_version_status.py:7054`); `json.dumps("\x0c")` is `"\f"`, a valid TOML escape; the zsh widget text reuses the shell-init lifecycle (register, `≈`, reconfigure, strip) with no new mechanism.

### Agreed Concerns

None corroborated by a second lane (one reviewer ran).

### Divergent Views

None. D-06 stays provisional as instructed; this review did not reopen it, and 28-03 implements it as written.

### Cycle counts

- HIGH, counted: 3 (H1, H4, H6).
- Actionable non-HIGH: 7 (A1 to A7 below).

| ID | Sev | Plan | Change still needed in PLAN.md |
|---|---|---|---|
| A1 | MEDIUM | 28-01 | Task 2 step 1: say that every reference inside a moved body is rewritten to the new public name, and rename the loop variable `marker` in `replace_owned_region` (for example to `text_line`) so the call to `marker(...)` stays bound; the AST guard does not cover these bodies, so the targeted pytest run is the check. |
| A2 | MEDIUM | 28-01 | Replace the fixed 13-name set in the AST check with: every `FunctionDef` of HEAD's terminal_shell.py except the moved or deliberately changed names (`_sync_alacritty`, the keys functions), compared by `ast.dump`; this matches the "every other body is AST-identical" claim at 28-01-PLAN.md:193. |
| A3 | LOW | 28-04 (Task 2) | `.claude/skills/tool-onboarding/SKILL.md:224` still says the `partial:` line is "written by `installer/terminal_shell.py`" and that "phase 28 settles the exact wording": update the attribution (the literal now lives in `installer/terminal_regions.py`, still reported through `installer/terminal_shell.py`'s sync) and drop or defer the wording promise, or record an explicit deferral in the plan. The pin in `tests/test_tool_onboarding_skill.py:372` requires the phrase `installer/terminal_shell.py` to stay in that section. |
| A4 | MEDIUM | 28-02 (Task 2) | Add a failing fixture for the reverse direction: a table holding a key with no declarer (for example `"ghost"`) must give `extra_rows(...) == {"ghost"}`, so an always-empty `extra_rows` cannot pass. |
| A5 | MEDIUM | 28-03 (and 28-02 T-28-03) | Reword the two `backstop` must_haves and the test names `test_two_applies_leave_one_region` and `test_reconfigure_then_uninstall_leaves_no_region` as sequential, state the real guarantee (compare-before-commit narrows but does not close the window at `agent_settings.py:562-569`), and either add one race test through the keys apply route (patching `terminal_keys.read_settings` as `tests/test_terminal_shell.py:1271-1289` does for the sync route) or record that the SPEC R1/R2 concurrency rows stay held-out backstops. |
| A6 | LOW | 28-04 (Task 1) | Use `${ZSH_VERSION-}` in the widget guard (and the pinned text in the test and must_haves), or record the `_guarded_init` precedent (`installer/tweaks.py:96`) as an explicit rejection of the nounset concern. |
| A7 | LOW | 28-04 (Task 1) | Add `tests/test_policy_tweaks.py`, `tests/test_uninstall_e2e.py` and `tests/test_schedules_lifecycle.py` to the first `<automated>` command. |

### HIGH fixes still needed in PLAN.md

- H1 (28-01): see A1; the local `marker` variable must be renamed or the function bound differently, since the plan as written produces `UnboundLocalError` and a red first test run.
- H4 (28-04 Task 1, pty test): the prescribed `os.execve(zsh, ["zsh", "-f", "-i"], ...)` cannot pass the autouse launch guard. Specify a launch the guard accepts without weakening it (for example a Python helper script under `tmp_path`, run through the already allowed `sys.executable`, that owns the `pty.fork` and the zsh exec, with `os._exit(127)` after a failed exec), or drop the live pty probe and keep the always-on bytes test plus `zsh -n` as the byte-level proof, recording that decision. Whichever is chosen, a failed exec in a forked child must never fall through into the test body.
- H6 (28-04): the locked SPEC wording (byte-identical apply then strip) is not met. Either the owner amends 28-SPEC.md R3 adjacency and the prohibition row to the real behavior of `strip_block` (recorded as a SPEC amendment, as D-06 was), or the plan meets the criterion; in both cases correct the stated limit (28-04-PLAN.md:30,73,140), which is wrong for inputs ending in more than one blank line or in no newline, and add those inputs to the parametrized cases.

---

## Verification coverage

Source-grounding pass (`plan_review.source_grounding: true`). Effective authority from `drift-guard authority` is `intel` (`intel.enabled: true`; `plan_review.source_grounding_authority` is `grep`). The intel adapter analyzes JavaScript only, so every Python symbol below was resolved with grep and a read of the source (adapter `grep`). Symbols the plans create (`installer/terminal_regions.py`, `installer/terminal_keys.py`, `tests/test_terminal_keys.py` and everything under "Artifacts this phase produces") were excluded.

Verdict counts: 70 VERIFIED, 0 MISSING, 0 AMBIGUOUS. One search came back empty on purpose: `.github/workflows/ci.yml` has no `zsh` mention, which is the claim 28-CONTEXT.md D-09 makes. No `hardBlock`, no needs-acknowledgement symbol.

VERIFIED (symbol, then the first declaration found):

```
replace_owned_region -> installer/terminal_shell.py:102
_commit_alacritty -> installer/terminal_shell.py:604
_keys_plan -> installer/terminal_shell.py:583
_user_document -> installer/terminal_shell.py:528
_snapshot_text -> installer/terminal_shell.py:519
_imports_files -> installer/terminal_shell.py:547
_table -> installer/terminal_shell.py:539
_strip_alacritty_region -> installer/terminal_shell.py:659
apply_alacritty_keys -> installer/terminal_shell.py:671
alacritty_keys_pending -> installer/terminal_shell.py:710
strip_alacritty -> installer/terminal_shell.py:726
_drop_created_config -> installer/terminal_shell.py:742
KEYS_PENDING -> installer/terminal_shell.py:474
_sync_alacritty -> installer/terminal_shell.py:633
sync_terminal_shells -> installer/terminal_shell.py:893
_tune_terminal / _apply_terminal_tuning / apply_install_tuning / run_post_install / _tune_shell_init -> installer/post_install.py (386, 391, 426, 455, 280 region)
_terminal_tuning_fact / _tuning_fact / TUNING_PENDING / _TERMINAL_ROWS -> installer/version_status.py (821, 777, 773, 733 region)
_after_removal -> installer/app.py:612 region
SHELL_INIT_TOOLS / tweak_block / write_tweak / remove_tweak / shell_init_bundle / shell_init_record / forget_shell_init / _shell_init / _NVIM_EDITOR_BODY / _DOCKER_BODY -> installer/tweaks.py
shellrc.apply_block / strip_block -> installer/shellrc.py:203-239
missing_dirs / read_settings / write_if_unchanged / remove_created_dirs -> installer/agent_settings.py
atomic_write_text / FileSnapshot -> installer/atomic.py
POST_INSTALL_ACTIONS (apply_terminal_tuning, source_shell_init closed names) -> installer/model.py:130-141
tests: _alacritty_tool, _alacritty_toml, _sync_alacritty, _remove_alacritty, test_alacritty_changed_before_commit_is_refused, test_alacritty_region_that_would_not_reparse_is_refused (tests/test_terminal_shell.py); test_bundles_have_stable_ids_and_order, test_each_shell_init_body_is_guarded_and_parses (tests/test_tweaks.py); _tool_block (tests/test_model.py:1710); _alacritty_shipped, _settled_states, _tuning_state, _reconfigure, test_alacritty_keys_region_removed_by_hand_is_the_users_choice (tests/test_version_status.py); test_apply_terminal_tuning_names_the_refusal (tests/test_post_install.py:1129); test_conflicts_names_the_real_partial_lines (tests/test_tool_onboarding_skill.py)
other citations spot-checked at the cited line: registry.toml:562 (`id = "zsh"`), registry.toml:3154 (`name = "Alacritty"`), compose.py:713, tests/test_shellrc.py:708 and tests/test_tweaks.py:373 (zsh skipif), tests/test_terminal_shell.py:1143 (pyright ignore), Makefile targets validate / verify-registry / hooks-e2e, `.claude/skills/tool-onboarding/SKILL.md:198` and `tests/test_tool_onboarding_skill.py:225` (both hold `planned for phase 28`, so the HEAD=2 count in 28-04 holds)
```

UNCHECKABLE (never treated as verified or missing):

- Function signatures of every cited callable (the `grep` and `intel` adapters cannot assert signatures). The plans' new signatures (`commit_region`, `apply_terminal_keys`, `terminal_keys_pending`, `strip_terminal_keys`, `_tune_terminal`, `_terminal_tuning_fact`) are checked only by reading the old bodies, not by an adapter.
- Counts the plans assert from the executor's future tree (`grep -c` EXPECT values after the change, "12 passed", "15 passed", "7 passed", "6 passed"): they depend on code that does not exist yet. Recomputed by reading the plans' own test lists: 12 (6 golden, 1 row, 5 completeness/backstop), 6 plus the pty test (28-04), 7 (28-03 Task 2) and at least 15 (28-03 Task 1, a floor) are all consistent. The HEAD-side counts were re-run and hold (`rg -c -i alacritty` = 4/3/4; 5 matches for the 28-02 terminal_shell grep).
- Runtime behavior of the zsh widget in zsh 5.x under a real pty: research probed it (28-04-PLAN.md:116); this review did not re-run it, and under H4 the plan's launch method cannot run in the suite as written.
- Whether `ubuntu-latest` and `macos-latest` CI runners ship zsh (28-CONTEXT.md deferred item): no workflow mention found, so CI may run the bytes test only.
- macOS-specific behavior (Terminal.app, iTerm2 and `ESC[3J`): out of scope here and deferred to the owner's Mac UAT.

Cross-artifact fact-drift pass (advisory; adds nothing to the counts):

- Phase status (`drift-guard phase-status --phase 28`): verdict `uncheckable`. `.planning/STATE.md` still reports `current_phase: 27` with `status: verifying` ("Phase complete — ready for verification") while ROADMAP.md lists Phase 28 as not started; the seam could not match a state to phase 28. Recorded, not read as consistent. Authority for status is STATE.md, which has not been advanced to phase 28.
- Success criteria (ROADMAP.md Phase 28 Success Criteria vs PLAN.md `must_haves.truths`): no contradiction found. Criterion 2's "deleting ... makes its row read `≈`" is amended in ROADMAP.md itself (28 D-06) and 28-03 implements the amended reading; criterion 1's "no Alacritty-id branch" is met except the shell-sync row `_TERMINAL_ROWS["alacritty"]`, which 28-CONTEXT.md D-04 keeps by decision.
- Requirement IDs (ROADMAP.md `**Requirements:** KEYS-01, KEYS-02, KEYS-03, KEYS-04` vs PLAN `requirements:`): 28-01 KEYS-01, 28-02 KEYS-01 and KEYS-02, 28-03 KEYS-02, KEYS-03 and KEYS-04, 28-04 KEYS-03: all four IDs are covered and none is undefined. No drift.
- Glossary (CONTEXT.md decisions vs plan usage): D-01 through D-15 match the plans except two intentional, recorded deviations: D-04's `TERMINAL_KEYS[tool.id]` becomes `.get` plus a refusal (28-02 decision record, owner rule 5), and D-12's import-line target is `tests.test_terminal_keys` instead of `installer.terminal_keys` (28-02 decision record). Both are explained in the plan, not drift.
- Spec vs plan (outside the four judgment pairs, reported under H6): SPEC R3 byte-identical strip versus 28-04's stated limit.
- Lane-status note: this cycle's REVIEWS.md is the first for Phase 28; no `Plan-Revision Conflicts` entries existed to preserve, so the begin/end block is written empty.
