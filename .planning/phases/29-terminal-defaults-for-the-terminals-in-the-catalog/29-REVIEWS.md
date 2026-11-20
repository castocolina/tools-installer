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


---

## Lane Log (convergence cycle 2, plans at 3ebb9d18)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 12:40 | opencode-referee-one | one-shot probe | OK |
| 12:40 to 12:42 | opencode-referee-one | real review through `review-lane invoke --slug opencode --model router-env/my-referee-one --as opencode-referee-one`, background, stdin `/dev/null` | exit 0, 13 KB, stderr empty |

Failures this cycle: none. The review below is referee-one's, unedited.

## Orchestrator verification of the cycle 2 HIGH concerns

| Id | Claim | Judgment |
|---|---|---|
| C2-H1 (29-02) | A user who moves the kitty region below a mapping the scan cannot inspect lets the installer's map win | Rejected as a stated limit: it needs a user to move an owned block and an unscannable `geninclude` mapping (already reported as not followed); the installer owns the region's contents, not its position after a user edit; phase 28's Alacritty region has the same limit. Recorded as a `shortcut:` comment in 29-02. |
| C2-H2 (29-03) | A user's `config.keys =` after an unchanged region leaves status quiet | Real (`terminal_keys_pending` never validates an unchanged region; `commit_region` returns before validation). Fix: an opt-in `validate_on_status` row field (WezTerm True; Alacritty and kitty False, so their existing behavior is untouched); a present region whose current text fails `row.validate` reads as a pending reason with no step. |
| C2-H3 (29-05) | A failed herdr byte proof only changes the skill wording, but TERM-05 needs the bytes or a pass-through setting | Real. Fix: 29-06 requires `herdr-keys: PASS` and otherwise stops BLOCKED; a product FAIL stops the run for a replan toward the pass-through setting; an environmental UNPROVEN is retried by the orchestrator. |
| C2-H4 (29-06) | A missing or `not run` D-07 check passes through the gate | Real. Fix: 29-06 requires `D-07 cwd check: PASS` and otherwise stops BLOCKED; a FAIL replans the row to `Writes`. The two-wording alternatives are removed; the cells say `verified`. |

Actionable MEDIUMs adopted: 29-03 live Lua check asserts and exits non-zero on mismatch; 29-04 `NotADirectoryError` is unknown, not stock (do not touch `_read_text`; read the file directly in the new check); 29-05 attribute recorder bytes by cumulative expected length with split-write tests, not by timing alone; SPEC boundary text amended by the orchestrator. Rejected with reasons: 29-01 moved shell region (pre-existing sync behavior, out of this phase's scope); 29-02 `glob` directory listing (a stated limit with a `shortcut:` comment, kitty globs are small); 29-06 `/Applications` token (reviewer: no change required).

`CYCLE_SUMMARY: current_high=3 current_actionable=4`

## OpenCode Review (opencode-referee-one), cycle 2

Using the plan-review checklist to check the six current plans against the lifecycle code, tests, and phase decisions.
### Document Type

GSD · implementation plans

### Status: Issues Found — revise and re-review

The review is grounded in the current checkout. I treated the provisional phase 28 D-06 and 29 D-09 decisions as instructed, rather than reopening them.

## 29-01

**Summary.** Changes Alacritty’s clear binding, extends the shared row interface, and fixes WezTerm shell-marker detection.

**Findings status.** Cycle 1’s A1 is addressed for **changed** writes: the plan adds a validator test, and `commit_region` validates changed content (`installer/terminal_regions.py:181-196`). It does not validate an unchanged file; the resulting WezTerm risk is discussed under 29-03.

**Strengths.** The Alacritty change targets the existing single tuple and leaves the two Alt tuples intact (`installer/terminal_regions.py:139-143`). The interface changes cover the existing render, apply, and pending paths (`installer/terminal_keys.py:106-113,145-224`).

**Concerns.**

- **MEDIUM — The WezTerm shell region can remain unreachable after an existing region is moved.** The planned `_wezterm_content` accepts an owned region whenever at least one `return config` exists and replaces that region in place (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-01-PLAN.md:197,207`). An existing shell region *after* the return therefore remains after it, although the terminal never executes it. The existing replacement primitive preserves that position (`installer/terminal_regions.py:57-62`). The new tests cover insertion, not this existing-region case.

**Suggestions.** Add a moved-shell-region fixture and refuse or safely repair an unreachable region without changing user lines.

**Risk Assessment.** Moderate: the shared changes are well scoped, but the shell sync can report a configuration that WezTerm does not execute.

## 29-02

**Summary.** Adds kitty’s per-OS keys region, conflict scan and resolver, and replaces its macOS script route with the cask.

**Findings status.** A3’s golden-file probe is now self-verifying. H1 is explicitly implemented as the instructed provisional quiet-on-recorded-refusal decision. A2 is only partially addressed: stopped walks are reported, but the proposed glob operation is not actually bounded as claimed.

**Strengths.** The cask change removes the current `/Applications` script method (`installer/registry.toml:3040-3049`) and retains the existing cask (`:3059-3064`). The scan reports unreadable and unsupported includes rather than claiming they were checked (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md:319-323`).

**Concerns.**

- **HIGH — A moved kitty region can override a user binding.** The plan promises top placement but retains existing regions in place and makes `validate_kitty` check only that their lines start with `map` (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md:275,280`; `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-01-PLAN.md:197`). If a user moves the region below a mapping that the bounded scan cannot inspect—for example, one from `geninclude`—kitty’s last-wins behavior lets the installer’s later mapping win. A partial note does not preserve the binding. The underlying replacement behavior is at `installer/terminal_regions.py:57-62`.
- **MEDIUM — `islice(glob.iglob(...))` does not bound directory enumeration.** The plan asserts a real bound at `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md:30,331`. Python’s `glob` implementation on this host materializes a directory’s entries in `_listdir` before yielding matches. Thus the file-read cap and partial report work, but a huge directory can still consume substantial memory and time before the cap is applied.

**Suggestions.** Validate that an existing kitty region is still at the safe placement before any rewrite, with a moved-region fixture involving an unscanned include. Either implement genuinely bounded enumeration or state and test the remaining directory-size limitation.

**Risk Assessment.** High: the moved-region case can violate the phase’s user-binding preservation rule.

## 29-03

**Summary.** Adds WezTerm’s guarded Lua region, read-back, and created-file cleanup.

**Findings status.** H2 now has a proposed pre-29-06 container check; A4 and A5 have concrete suite-wide mocking and unverified-output handling. H3 is mitigated only when a write changes the file, not for the original post-install edit scenario.

**Strengths.** The Lua design explicitly imports WezTerm and normalizes modifiers and uppercase letters before guarding additions (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:125-153`). The read-back seam accounts for the sandbox’s refusal of host executables (`tests/sandbox.py:515-570`).

**Concerns.**

- **HIGH — The original ineffective-region status gap remains after an ordinary user edit.** The plan explicitly defers detection when the region’s own bytes remain unchanged (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:93,248`). `terminal_keys_pending` compares the rendered region to the file but does not invoke the validator (`installer/terminal_keys.py:200-224`), and `commit_region` returns before validation when content is unchanged (`installer/terminal_regions.py:192-196`). Adding `config.keys = {}` after a correctly installed region can therefore erase its effective bindings while status remains quiet. The new stale-region tests do not exercise this case.
- **MEDIUM — The live Lua check can exit successfully without proving its assertions.** The check merely prints three results (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:171-199`); the executor must interpret them manually (`:322`). A refusal, unexpected result, or missing conflict can still produce exit zero. This weakens the only planned live execution of the generated guard.

**Suggestions.** Check effective placement and later assignments during status/read-back even when no rewrite is needed, with an installed-region-then-user-edit test. Make the live check assert all three results and exit nonzero on mismatch.

**Risk Assessment.** High: a valid-looking, unchanged owned region can be ineffective without a user-visible indication.

## 29-04

**Summary.** Implements the instructed report-only Konsole check and a stock note when the profile is written.

**Findings status.** A6 is substantially addressed with stock, removed, and unknown states. The explicit SPEC acceptance now says report-only (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-SPEC.md:38-41,76`); older boundary text remains inconsistent.

**Strengths.** The design keeps shortcut detection separate from the existing Konsole profile mutation and routes `partial:` through the existing status mechanism (`installer/terminal_shell.py:712-721`; `installer/version_status.py:1601-1606`).

**Concerns.**

- **MEDIUM — A non-directory path component can still become an affirmative stock result.** The plan relies on `_read_text` to distinguish unreadable paths from missing files (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-04-PLAN.md:121-133`). But `_read_text` converts both `FileNotFoundError` **and `NotADirectoryError`** to an empty string (`installer/terminal_shell.py:252-255`). If, for example, `kxmlgui5/konsole` is a regular file, the detector treats that failed read as stock rather than unknown. The proposed directory-at-the-final-path fixture does not cover this case.

**Suggestions.** Distinguish an absent override from `NotADirectoryError`, and add a fixture with a non-directory parent component. Reconcile the stale conditional-write boundary wording in `29-SPEC.md:50-59` when the provisional decision is confirmed.

**Risk Assessment.** Moderate: the check remains read-only, but can make a false stock claim.

## 29-05

**Summary.** Adds a disposable-container herdr byte probe and host-side verdict and harness tests.

**Findings status.** H4’s claim is narrowed to the actual arrow encoding, A7 removes the standalone static gate, and A8 moves the target before the documentation wording decision.

**Strengths.** The specified verdict checks each sent chord separately and distinguishes an unstarted recorder (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-05-PLAN.md:117-125,140-143`). The existing harness removes its named container and checks that it is gone (`scripts/container-e2e-verify.sh:2734-2754`).

**Concerns.**

- **HIGH — A failed byte proof does not require the behavior required by TERM-05.** The plan says a mismatch is reported, then lets 29-06 use unverified wording (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-05-PLAN.md:234`; `29-06-PLAN.md:103-108,220-224`). But the locked acceptance requires either the bytes to arrive **or** an applied and removable pass-through setting (`29-SPEC.md:43-46,77`). A product failure can therefore leave the phase without either outcome while the final plan still completes.
- **MEDIUM — The host tests do not exercise the actual PTY/log attribution loop.** They test the pure slicing function and verdict, but the loop that records marks, sends bytes, pumps, and shuts down is specified only for the container run (`29-05-PLAN.md:123,140-143`). Delayed or split recorder writes around a mark can be attributed to the wrong chord, producing a misleading product failure.

**Suggestions.** Make a product mismatch stop phase completion and trigger investigation or a replan for the pass-through setting; keep an environmental UNPROVEN result distinct. Add a deterministic test of the driver loop or an explicit per-chord synchronization protocol.

**Risk Assessment.** High if the live probe fails: documentation qualification alone does not satisfy TERM-05.

## 29-06

**Summary.** Updates the onboarding skill and adds cross-row consistency and prohibition tests.

**Findings status.** A8’s premature **verified** claim is addressed by selecting wording from a recorded PASS. H2 is improved, but the gate permits an unrun check and the herdr failure path remains non-blocking.

**Strengths.** The table guard uses the existing seven-cell parser (`tests/test_tool_onboarding_skill.py:140-146,180-193`), and the plan separates the two evidence-dependent wordings (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-06-PLAN.md:99-108`).

**Concerns.**

- **HIGH — A missing D-07 check can pass through the supposed prerequisite gate.** The plan calls the check a gate before 29-06, but explicitly allows `not run` or a missing section to select unverified wording and proceeds (`29-06-PLAN.md:57-59,136-139,220-224`). That leaves the production row as `Vendor` even though D-07 requires the live check before locking that declaration and a `Writes` replan on failure (`29-CONTEXT.md:34-36`). A later checklist does not prevent the phase’s last plan from finishing with the decision unresolved.
- **MEDIUM — The exact target text breaks an existing skill test.** The replacement sentence at `29-06-PLAN.md:113` removes the only standalone backticked `` `/Applications` `` in the macOS-apps section: the existing sentence contains `` `/Applications/kitty.app` ``, while the required standalone token occurs in the section’s first paragraph (`.claude/skills/tool-onboarding/SKILL.md:102-110`). The plan’s target leaves that first paragraph intact, so this particular existing test remains satisfied; however, the plan should not rely on the replacement sentence itself to provide that token. **No change required if the first paragraph remains unchanged.**

**Suggestions.** Require a recorded D-07 PASS before completing the phase, or explicitly stop as blocked when the check cannot run; retain the fail-to-replan path. Keep the herdr product-failure gate consistent with 29-05.

**Risk Assessment.** High: an unverified cwd behavior can remain the shipped declaration despite the locked precondition.

## Cross-plan consistency

- **Wave overlap is appropriately bounded by declared modified files:** 29-01 and 29-05 are disjoint, while subsequent terminal-module changes are serialized (`29-01-PLAN.md:6-13`; `29-05-PLAN.md:6-11`; `29-06-PLAN.md:6-12`).
- **Cycle 1 dispositions are not all complete:** A1 and H3 cover changed rewrites, but not unchanged effective-order drift; A2 reports caps but does not bound Python glob’s directory enumeration. The instructed H1 quiet behavior is recorded rather than challenged.
- **Phase completion needs outcome gates, not only truthful documentation.** In particular, an unrun WezTerm cwd probe and a failed herdr byte probe must not be treated as equivalent to completed TERM-02 and TERM-05.

**Not checked:** I did not run the test suite, terminal programs, or containers. The glob observation was checked against the host Python implementation; no repository files were changed.


---

## Lane Log (convergence cycle 3, plans at c017dd67)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 13:12 | opencode-referee-one | one-shot probe | OK |
| 13:12 to 13:15 | opencode-referee-one | real review through `review-lane invoke --slug opencode --model router-env/my-referee-one --as opencode-referee-one`, background, stdin `/dev/null` | exit 0, 10 KB, stderr empty |

Failures this cycle: none. (The user quota on /tmp was exhausted at 13:04 by an unrelated pytest run of another session; it cleared before this run, which wrote its output normally.) The review below is referee-one's, unedited; its first lines carry two of its own HIGH bullets that restate the one 29-02 finding.

## Orchestrator verification of the cycle 3 HIGH concerns

| Id | Claim | Judgment |
|---|---|---|
| C3-H1 (29-02, also 29-03) | Cleanup resolves the config path again, but the created marker is tool-wide, so a resolver change between install and removal can delete a different, user-owned empty file | Real. `_drop_created_config` (installer/terminal_keys.py:227-255) trusts a marker that names no path; the marker bytes are pinned for Alacritty by the phase 28 golden test, so the fix is opt-in. Decision: kitty and WezTerm rows bind the created-file proof to the created path through a sidecar record; cleanup deletes only when the resolved path equals the recorded path; Alacritty's marker and tests stay byte-identical. |
| C3-H2 (29-03) | The D-07 live check uses `wezterm cli spawn`, not the `SpawnTab` and `SpawnWindow` key actions the decision concerns | Real. Decision: the orchestrator's check performs the actual actions from a Lua `window:perform_action` callback inside a disposable Xvfb session (a pane started in a known directory, no OSC 7), then asserts each new pane's cwd. A PASS means the actions, not the CLI. |

Actionable MEDIUM adopted: 29-05, a client that exits before the recorder started is UNPROVEN (nonzero exit, container removed), never a generic ERROR; FAILED stays for a recorder that started and received wrong bytes.

Cap rule (owner, convergence at cycle 3): fewer than 4 critical plus HIGH remain (2), so the orchestrator fixes and executes without a further review cycle.

`CYCLE_SUMMARY: current_high=2 current_actionable=1`

## OpenCode Review (opencode-referee-one), cycle 3

Using the plan-review checklist to assess all six plans against the current source and the previous review findings.
**HIGH — 29-02 can silently forget where it wrote kitty’s configuration.** The resolver selects an existing path only while its directory is writable, but uninstall resolves the path again; a later permissions change can redirect cleanup to another file and leave the owned region behind. I’m checking the surrounding cleanup and evidence before finalizing the finding.
**HIGH — 29-02’s path drift can also delete the wrong config.** `strip_terminal_keys` resolves the current path but uses a tool-wide created marker; if the resolver switches to a different empty file, the existing cleanup treats that file as installer-created.
### Document Type

GSD · implementation plans

### Status: Issues Found — revise and re-review

The review is grounded in the current checkout. I treated the provisional 28 D-06 and 29 D-09 decisions as instructed rather than reopening them.

## 29-01

**Summary.** Changes Alacritty’s clear binding, extends the shared row interface, and fixes exact-marker detection for the WezTerm shell region.

**Findings status.** Cycle 2’s unchanged-region status gap is addressed for opt-in rows by the proposed validator branch and fixture (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-01-PLAN.md:182,209`). The previously noted moved WezTerm shell-region case remains explicitly deferred by the orchestrator.

**Strengths.** The interface changes cover both application and status rendering. The current `commit_region` validates changed content before writing (`installer/terminal_regions.py:181-205`), and the plan adds a separate status validation path for unchanged content.

**Concerns.** No new finding identified within the instructed scope.

**Suggestions.** Keep the moved-shell-region limitation in the execution summary; exact marker detection alone does not repair an already unreachable region.

**Risk Assessment.** Moderate: the shared interface has broad reach, but the planned fixture coverage exercises its material additions.

## 29-02

**Summary.** Adds kitty’s per-OS keys region, config resolver and include scan, then replaces the macOS script method with the cask.

**Findings status.** The cycle 2 moved-region and glob-enumeration concerns are explicitly accepted as limitations (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md:468-472`). The live kitty probe is self-verifying.

**Strengths.** The existing macOS script does name `/Applications/kitty.app/Contents/MacOS`, while the cask is already present (`installer/registry.toml:3040-3064`); the plan removes the former and updates the relevant registry assertions.

**Concerns.**

- **HIGH — A changed resolver result can cause cleanup to delete a different user file.** The proposed resolver chooses the first *currently writable* existing kitty config (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md:270`). Cleanup resolves that path again, but the created-file marker is tool-wide, not bound to the path (`installer/terminal_keys.py:141-142,227-255`; `installer/terminal_regions.py:198-204`). For example, after the installer creates an XDG kitty config, a permissions or environment change can make the resolver select a pre-existing empty fallback file. Cleanup can then delete that fallback under the old marker and leave the installer-created file behind. The planned removal tests cover only a stable path (`29-02-PLAN.md:255-256`).

**Suggestions.** Bind created-file proof to the actual created path, or otherwise ensure cleanup never applies a marker to a different resolved path. Add a test that changes resolver precedence between install and removal, with an empty user-owned fallback file.

**Risk Assessment.** High: the path-change case can delete user-owned data, not merely leave stale configuration.

## 29-03

**Summary.** Adds WezTerm’s guarded Lua region, status validation, effective-key read-back and created-file cleanup.

**Findings status.** Cycle 2’s plain `config.keys =` status gap is addressed by `validate_on_status` and a post-install edit test (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md:247-253,267-272`). The live Lua check now asserts its results.

**Strengths.** The Lua guard normalizes aliases, modifier order and uppercase-letter SHIFT before appending (`29-03-PLAN.md:130-155`). The suite-wide read-back seam accounts for the existing subprocess sandbox (`tests/sandbox.py:515-570`).

**Concerns.**

- **HIGH — The D-07 gate does not test the actions whose behavior it claims to verify.** The prescribed live check uses `wezterm cli spawn` and `wezterm cli spawn --new-window` (`29-03-PLAN.md:93`), whereas the decision concerns the terminal’s `SpawnTab` and `SpawnWindow` actions invoked through its bindings. A CLI spawn can have a different cwd-selection path from a GUI key action. A PASS therefore does not establish the behavior that the plan later declares verified.

**Suggestions.** Exercise the actual tab and window actions in the disposable GUI session, with a pane in a known directory and no OSC 7; assert the cwd of each resulting pane. If that cannot be done, keep the claim provisional rather than treating the CLI result as the required proof.

**Risk Assessment.** High until the gate measures the intended actions. The Lua conflict-guard coverage itself is substantially improved.

## 29-04

**Summary.** Implements the instructed report-only Konsole check, with a warning for a removed shortcut and a stock note on profile setup.

**Findings status.** Cycle 2’s non-directory-parent concern is addressed: the proposed reader distinguishes `NotADirectoryError` from an absent file (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-04-PLAN.md:137,176`).

**Strengths.** `read_capped` propagates open errors and rejects non-regular or oversized files (`installer/atomic.py:186-215`), supporting the planned three-state detector. Existing status routing recognizes terminal `partial:` warnings (`installer/version_status.py:1601-1606`).

**Concerns.** No new finding identified while applying the provisional report-only decision as written.

**Suggestions.** Preserve the open Konsole 26.x capture and owner-confirmation items in the phase handoff.

**Risk Assessment.** Moderate: the detector remains read-only, but its live file-format and stock-chord confirmation remain outstanding.

## 29-05

**Summary.** Adds a guarded disposable-container herdr byte probe, a pure verdict and host-side harness tests.

**Findings status.** Cycle 2’s phase-completion gap is addressed by the required recorded PASS and stop/replan behavior (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-05-PLAN.md:25,241`). Cumulative-length slicing is now specified and unit-tested; the PTY loop remains a live-container check.

**Strengths.** The existing landing harness records failed steps and removes the specifically named container (`scripts/container-e2e-verify.sh:2734-2754,2802-2818`). The plan distinguishes expected bytes from an unstarted recorder.

**Concerns.**

- **MEDIUM — Some probe startup failures have no specified UNPROVEN verdict.** The driver sends to and pumps the PTY before checking whether the recorder started (`29-05-PLAN.md:150`). If the client exits and PTY I/O raises `OSError`, `main` emits a generic `ERROR` (`29-05-PLAN.md:151`), rather than `TRACER_HERDR_KEYS_UNPROVEN`. The existing harness only classifies recognized environment messages as infeasible (`scripts/container-e2e-verify.sh:2705-2725,2805-2818`), leaving the orchestrator without the plan’s stated product-versus-environment verdict.

**Suggestions.** Specify and test the client-exited-before-recorder path as UNPROVEN, including cleanup and nonzero exit; retain FAILED for a recorder that started but received wrong bytes.

**Risk Assessment.** Moderate: the hard gate prevents a false pass, but an ambiguous startup failure can stall convergence.

## 29-06

**Summary.** Requires the two recorded live-check passes, updates the onboarding skill and adds consistency guards.

**Findings status.** Cycle 2’s missing-PASS paths are addressed: both `awk` checks block edits and commits when their respective recorded results are absent or unsuccessful (`.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-06-PLAN.md:63-64,133-143`).

**Strengths.** The target table wording respects the existing seven-cell parser and status-word checks (`tests/test_tool_onboarding_skill.py:140-146,180-193`).

**Concerns.** No separate new finding in the gate mechanics. The meaning of the WezTerm PASS remains dependent on the 29-03 finding.

**Suggestions.** Update the verified cwd wording only after the revised action-level D-07 check passes.

**Risk Assessment.** Moderate: the gate now blocks missing evidence, but cannot compensate for a probe that tests a different operation.

## Cross-plan consistency

- The declared wave-1 file sets for 29-01 and 29-05 are disjoint (`29-01-PLAN.md:6-13`; `29-05-PLAN.md:6-11`); subsequent shared terminal changes are serialized.
- The created-marker/path issue in 29-02 should also be considered for WezTerm: its resolver can switch between XDG and `~/.wezterm.lua`, while 29-03 permits deleting a created file when its remainder is the skeleton (`installer/terminal_shell.py:121-127`; `29-03-PLAN.md:265,273`). A marker must prove ownership of the **selected path**, not just the tool.
- **Required before approval:** protect created-file cleanup against resolver drift and make the D-07 proof exercise the actual WezTerm actions.

**Not checked:** I did not run the test suite, terminal applications, or containers, and made no repository changes. Live macOS behavior remains deferred to the owner’s UAT.
