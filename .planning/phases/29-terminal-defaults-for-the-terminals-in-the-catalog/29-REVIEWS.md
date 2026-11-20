---
phase: 29
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-20T15:16:00Z
plans_reviewed: [29-01-PLAN.md, 29-02-PLAN.md, 29-03-PLAN.md, 29-04-PLAN.md, 29-05-PLAN.md, 29-06-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 29

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log (convergence cycle 1, plans at 88529ca5)

Reviewer selection: `review.default_reviewers = ["opencode-referee-one"]` (router-env/my-referee-one), the owner-required first lane. Failover (referee-two, then referee-three) only on a real failure.

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 12:13 | opencode-referee-one | one-shot probe (`Reply with exactly: OK`, 120 s timeout) | OK, exit 0 |
| 12:14 to 12:16 | opencode-referee-one | real review through `gsd-tools query review-lane invoke --slug opencode --model router-env/my-referee-one --as opencode-referee-one`, background, 2700 s timeout, stdin `/dev/null` | exit 0, 13 KB, stderr empty |

Failures this cycle: none. No other lane or model was used.

The review below is referee-one's, unedited. Exactly one reviewer ran, so the multi-reviewer consensus gate does not engage; the orchestrator verified every HIGH against repository source before counting it.

## Orchestrator verification of the HIGH concerns

| Id | Claim | Verified against | Judgment |
|---|---|---|---|
| H1 (29-02) | A recorded install hides a later `clear_all_shortcuts yes` refusal | `installer/terminal_keys.py:175-180` (recorded refusal returns quietly) and `:213-224` (a present region whose plan refuses reads None) | Real contract gap: the plan promises a visible reason, the phase 28 drift rule (28 D-06, provisional) keeps a recorded install quiet. Decision: keep the 28 D-06 rule, state it in the plan, add a test that pins it; the first apply and an unrecorded file still show the reason. |
| H2 (29-03) | The WezTerm cwd declaration is locked before the live check D-07 requires | 29-CONTEXT.md D-07: verify in a disposable container before the declaration is locked; otherwise the row switches to `writes` | Real. Xvfb is not on this host. Decision: the declaration stays `Vendor` but provisional; the orchestrator runs the container check after 29-03 and before 29-06, records the result in the 29-03 SUMMARY, and a failure stops the run for a replan to `writes`. |
| H3 (29-03) | A later user `config.keys = {...}` between the region and `return config` makes the region ineffective with no drift | `installer/terminal_regions.py:57-62` (in-place replace keeps position) and the validator in the plan | Real but narrower than stated (a user edit after install). Decision: `validate_wezterm` also refuses a text where a `config.keys =` assignment sits between the end marker and `return config`, on every write; the residual case (an edit after a quiet install) is a stated limit. |
| H4 (29-05) | CSI-u arrow forms are claimed but never sent | 29-05-PLAN.md:131 and :234; kitty keyboard protocol keeps arrows as `CSI 1;mod D/C` (there is no separate CSI-u arrow form) | Real wording defect: the claim over-states. Decision: state it exactly (raw ESC b/f, arrows as CSI 1;3D and 1;3C, CSI-u for Alt+B, Alt+F and Ctrl+L) and add the CSI 1;5-style cases only where the bytes differ. |

Counted after verification: `CYCLE_SUMMARY: current_high=4 current_actionable=9` (the actionable items: 29-01 placement validation on every rewrite; 29-02 bounded glob and reported incomplete scan; 29-02 self-verifying kitty check; 29-03 subprocess guard across every test module (this host has wezterm); 29-03 read-back must report unverified; 29-04 unknown versus stock; 29-05 remove the standalone `make shellcheck`; 29-06 herdr cells only after the target passes; the SPEC acceptance text that still says a removed key gets one binding).

## OpenCode Review (opencode-referee-one)

Using the plan-review checklist to check all six plans against the repository and their stated contracts.
I found several cross-plan edge cases in status reporting and validation; I’m checking them against the existing lifecycle code before finalizing the review.
# Phase 29 plan review

### Document type
GSD · implementation plans

### Status: Issues Found — revise and re-review

The plans are well grounded in the existing terminal-key mechanism, but several acceptance paths can report success without proving the requested behavior. The most consequential issues are the kitty refusal/status mismatch, unverified WezTerm cwd declaration, and gaps in the herdr byte proof.

## 29-01

**Summary.** Changes Alacritty’s clear bytes, extends the shared row interface, and fixes WezTerm shell-region detection.

**Findings status.** Cycle 1; no previous findings supplied.

**Strengths.**
- The planned Alacritty change matches the current single binding tuple in `installer/terminal_regions.py:139-143`; the drift test exercises the existing recorded-region lifecycle in `installer/terminal_keys.py:156-180`.
- Exact-line ownership detection builds on the existing marker parser in `installer/terminal_regions.py:26-62`, rather than another substring check.

**Concerns.**
- **MEDIUM — Existing regions bypass placement validation.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-01-PLAN.md:173-195` explicitly replaces an existing region in place even when multiple `return config` lines exist. The shared primitive’s current replacement branch (`installer/terminal_regions.py:57-62`) has no placement check. This becomes material for WezTerm if a user subsequently moves an assignment or return around the region: a successful reapply need not leave the region effective. See also 29-03.

**Suggestions.** Specify whether callers must validate placement on every rewrite, including existing regions, and test moved or unreachable regions.

**Risk assessment.** Moderate; the Alacritty tracer is narrowly scoped, but placement becomes a shared contract for later plans.

## 29-02

**Summary.** Adds kitty key tuning, scans user mappings and includes, shares the config resolver, and removes the macOS script method.

**Findings status.** Cycle 1; no previous findings supplied.

**Strengths.**
- A top-of-file region plus conflict scanning follows the stated last-wins model; the existing region writer preserves surrounding text (`installer/terminal_regions.py:26-62`).
- The cask route uses the existing user-app-directory mechanism in `installer/executors.py:699-704`; the current system-path script is visible in `installer/registry.toml:3040-3049`.

**Concerns.**
- **HIGH — A recorded install can silently hide the `clear_all_shortcuts` refusal.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md:31` promises a reason in status, and lines 277-284 implement the refusal only in the kitty planner. But `installer/terminal_keys.py:175-180` suppresses a recorded refusal on reconfigure, while `installer/terminal_keys.py:213-224` returns `None` for a present region whose plan refuses. Thus, if a user adds `clear_all_shortcuts yes` after installation, status can appear healthy even though kitty clears the installed shortcuts. The specified test covers only an unrecorded file.
- **MEDIUM — Include traversal is not bounded as claimed.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md:276-283` silently stops at the depth/file cap and calls `glob.glob` before applying that cap. Large glob expansions can still consume substantial time or memory, and a mapping or `clear_all_shortcuts` beyond the limit is neither checked nor reported. This contradicts the plan’s “every chord” claim at line 30.
- **MEDIUM — The real-kitty probe is not self-verifying.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md:153-175` prints subprocess output but does not check the return code or assert the expected mappings. Line 286 relies on a human or executor interpreting it; the generated test maps other than the two goldens also are not parsed, despite the locked “all test maps” decision recorded in `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-RESEARCH.md:14-16`.

**Suggestions.** Add a recorded-install refusal/status test and an actionable status path; report incomplete scans and bound glob enumeration; make the real-kitty check exit nonzero on missing mappings or failed execution.

**Risk assessment.** High: the main user-facing risk is a healthy-looking configuration whose clear key no longer works.

## 29-03

**Summary.** Adds the WezTerm Lua region, a guarded extension of `config.keys`, read-back, and created-file cleanup.

**Findings status.** Cycle 1; no previous findings supplied.

**Strengths.**
- The Lua guard at `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:112-138` addresses modifier ordering, aliases, and the uppercase-key/Shift collision; it also imports its own `wezterm` local.
- Cleanup retains the existing ownership-marker principle in `installer/terminal_keys.py:227-257` and adds explicit seed handling.

**Concerns.**
- **HIGH — The cwd decision is locked before the required live check.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:77-81` declares `Vendor` and allows the GUI check to remain a UAT line. The locked D-07 decision in `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-RESEARCH.md:23` requires verifying SpawnTab and SpawnWindow *before* locking the declaration, with explicit callbacks if the check fails. Source inspection is useful evidence but does not implement that decision.
- **HIGH — A later user assignment can make the region ineffective without drift.** The plan requires insertion immediately before `return config` (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:25-32`), but its validator at lines 224-228 only checks that a return follows the region. The shared replacement rule preserves an existing region’s position (`installer/terminal_regions.py:57-62`). If a user later inserts `config.keys = {...}` between the region and the return, that assignment replaces the additions at load time; the current drift comparison in `installer/terminal_keys.py:213-224` can still report no drift.
- **MEDIUM — The test subprocess guard is scoped to one test module.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:269-270` patches `which` only for `tests/test_terminal_keys.py`, while other targeted and full-suite tests can exercise post-install dispatch (`installer/post_install.py:385-398`). On a host where `wezterm` is visible, those paths can reach a real executable and be rejected by the suite’s guard (`tests/sandbox.py:515-570`).
- **MEDIUM — Read-back treats missing or unparsable rows as success.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:283-288` says an absent chord adds nothing. Changed `show-keys` formatting or an omitted effective binding therefore produces neither a conflict nor an unchecked warning.

**Suggestions.** Gate the vendor cwd declaration on the D-07 live result; validate effective ordering on reapply; isolate the subprocess across every test module that can dispatch it; report incomplete read-back as unverified.

**Risk assessment.** High: generated Lua can be syntactically valid yet ineffective, while status remains quiet.

## 29-04

**Summary.** Reads Konsole’s saved shortcut override and reports a removed key without writing the shortcut file.

**Findings status.** Cycle 1; no previous findings supplied. The provisional report-only decision is reviewed as given.

**Strengths.**
- The read-only check is separate from `_sync_konsole`, preserving the existing profile-sync implementation in `installer/terminal_shell.py:315-363`.
- Existing status routing does attach a `konsole: partial:` warning to the zsh row without a remediation step (`installer/version_status.py:733-741,1601-1607`).

**Concerns.**
- **MEDIUM — “Unreadable” becomes an affirmative stock claim.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-04-PLAN.md:118-130` maps unreadable or invalid files to “not removed”; lines 169-172 then emit `KONSOLE_CLEAR_STOCK` on a profile write. `_read_text` distinguishes these failures in `installer/terminal_shell.py:240-264`, but the planned boolean discards that distinction. A user override may therefore be reported as stock when it was never checked.

**Suggestions.** Preserve an unknown result separately from stock; do not emit the affirmative stock note on read failure. Keep the check non-fatal and report-only.

**Risk assessment.** Moderate; no shortcut is overwritten, but the report can be false.

## 29-05

**Summary.** Adds an orchestrator-run herdr container proof with a pure verdict and stubbed host tests.

**Findings status.** Cycle 1; no previous findings supplied.

**Strengths.**
- The target reuses the existing exact-name teardown and failure handling in `scripts/container-e2e-verify.sh:2728-2754,2802-2819`.
- The planned verdict distinguishes a recorder that never starts from a byte mismatch (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-05-PLAN.md:114-120,136-140`).

**Concerns.**
- **HIGH — CSI-u arrow forms are claimed but never sent.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-05-PLAN.md:131` lists CSI-u for Alt+B, Alt+F and Ctrl+L, but no CSI-u Alt+Left or Alt+Right. Nevertheless line 234 claims raw, CSI and CSI-u Option/Alt+Left/Right are proved. The research specifically calls for both arrow forms at `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-RESEARCH.md:317-321`.
- **MEDIUM — The plan manually invokes a static gate contrary to repository workflow.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-05-PLAN.md:187-195` requires `make shellcheck` in addition to the commit hook and the post-plan validation. `AGENTS.md` says not to run an individual static gate by hand per commit except to diagnose a failure or where hooks are absent.

**Suggestions.** Add explicit CSI-u arrow inputs and expected output bytes to `CHORDS` and its verdict tests, or narrow the claimed proof after resolving the requirement. Remove the unconditional standalone shellcheck invocation.

**Risk assessment.** Moderate to high: the target can pass while an explicitly claimed key encoding remains untested.

## 29-06

**Summary.** Updates the onboarding skill and adds consistency and global-option guards.

**Findings status.** Cycle 1; no previous findings supplied.

**Strengths.**
- The planned cross-row tests exercise generated files through `apply_terminal_keys`, the same entry point used by post-install (`installer/post_install.py:385-398`), rather than inspecting declarations alone.
- The plan updates the existing skill pin and runs the documentation tests (`tests/test_tool_onboarding_skill.py:466-487`).

**Concerns.**
- **MEDIUM — Documentation asserts herdr verification before the new proof runs.** `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-06-PLAN.md:98-99` says the raw ESC and arrow behavior is verified, but the mandatory new target runs only after this plan, at lines 203-204. The research says the prior scratch probe did not send Alt+Right (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-RESEARCH.md:317-321`), and 29-05 itself identifies raw ESC B/F as new evidence. If that target fails or is infeasible, the committed skill already overstates the evidence.

**Suggestions.** Qualify those cells until the target passes, or make the proof a prerequisite to committing the “verified” wording.

**Risk assessment.** Moderate: onboarding agents consume the skill as authoritative guidance.

## Cross-plan consistency

- **Ownership and sequencing are mostly coherent.** 29-01 and 29-05 list disjoint modified files and may run in parallel; 29-02 → 29-03 → 29-04 serializes the overlapping terminal modules; 29-06 depends on both branches (`29-01-PLAN.md:6-13`, `29-05-PLAN.md:6-11`, `29-06-PLAN.md:6-11`).
- **Keep the status contract consistent across plans.** 29-01 preserves the phase-28 quiet-on-recorded-refusal behavior, while 29-02 promises a visible kitty refusal. Resolve that interface conflict explicitly rather than expecting the kitty row alone to change status.
- **Reconcile remaining SPEC text.** The supplied SPEC still contains “removed key gets one binding” acceptance text despite the provisional report-only amendment. This review accepts the requested D-09 decision, but the contradictory acceptance text should be amended so execution and verification do not use opposite outcomes.

**Not checked:** I did not run the implementation tests, terminal programs, or container target; this is a source-grounded plan review, not live verification.
