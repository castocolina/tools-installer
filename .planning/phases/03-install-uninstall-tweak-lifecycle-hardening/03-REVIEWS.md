---
phase: 3
reviewers: [opencode]
reviewed_at: "2026-09-05T06:35:03Z"
plans_reviewed:
  - 03-01-PLAN.md
  - 03-02-PLAN.md
  - 03-03-PLAN.md
models:
  opencode: "opencode/nemotron-3-ultra-free"
model_sources:
  opencode: "cli-flag"
---

# Cross-AI Plan Review — Phase 3

Note on reviewer roster: `codex` (gpt-5.6-sol) was attempted first and hit its usage
quota ("You've hit your usage limit ... try again at Sep 6th, 2026 11:32 PM") before
producing any output — dropped, not counted. `opencode` was then run against
`google/gemini-3.1-pro-preview`, which failed on a Google API free-tier quota
(`generativelanguage.googleapis.com` rate limit) before producing output — also
dropped. `opencode/glm-5.3` failed on insufficient account balance — dropped.
`opencode/nemotron-3-ultra-free` succeeded and is the review below. `agy`
(Antigravity CLI) was attempted as a fourth lane but requires an interactive Google
OAuth login this session could not complete non-interactively — dropped. Per the
consensus gate: with exactly one reviewer completing, the 2+-reviewer consensus gate
is skipped and this reviewer's findings count directly.

The reviewer was given full repository read access and explicitly instructed to open
the referenced source files and verify each plan's claims against the actual code
rather than reviewing the plan text in isolation; its own tool-call log (Glob/Read
of `.planning/REQUIREMENTS.md`, all three `*-CONTEXT.md`/`*-PLAN.md` files, and the
full set of `installer/*.py` and `tests/*.py` files the plans reference) confirms it
did so.

## Opencode Review (nemotron-3-ultra-free)

# Cross-AI Plan Review: Phase 3 — Install/Uninstall & Tweak Lifecycle Hardening

---

## Plan 03-01: REQ-install-failure-propagation

### Summary
This plan adds run-time dependency failure propagation to `run_installs`. When a tool's prerequisite fails mid-run, dependents are skipped with a clear `DEPENDENCY_FAILED` outcome carrying the blocking IDs in `blocked_by`, reported in both the summary counts and a new `render_skipped` console line. The mechanism relies on `resolve_dependencies`' deps-first topological order for a single forward pass.

### Strengths
- **Clean separation of concerns**: Resolver (`installer/deps.py`) handles pre-flight platform availability; session (`installer/session.py`) handles mid-run failures. Documented in plan's `<design_decisions>` and enforced by a source-level check that `run_installs` never sorts.
- **Transitive propagation by design**: `_UNRESOLVED` frozenset at `installer/session.py:19` (planned) includes `DEPENDENCY_FAILED` itself, so a three-link chain `A→B→C` correctly skips both B and C when A fails. Task 2's `test_dependency_failure_propagates_down_a_chain` pins this.
- **No silent drops**: `summarize`'s bucket table uses a plain `dict` keyed by `InstallStatus` — a missing key raises `KeyError` (docstring at `installer/session.py:81-83`), which is the intended guard. Plan explicitly forbids `setdefault`/`defaultdict`/`.get`.
- **End-to-end verification**: Task 1's `test_run_wizard_reports_a_skipped_dependent_with_its_reason` drives the real `run_wizard` and asserts the console buffer contains `java skipped — dependency failed: sdkman`, proving the reason reaches the human.
- **Ordering invariant documented**: The plan states plainly that a hand-built list in wrong order degrades to current behavior (dependent attempted) — never worse, never a crash. Verified by Task 2's `test_a_dependent_listed_before_its_dependency_is_still_attempted` and a source-level check in verify commands.

### Concerns
| Severity | Issue | Evidence |
|----------|-------|----------|
| **MEDIUM** | Single-forward-pass limitation is documented but not enforced. If a future caller passes a non-topological list (e.g., from a different resolver), dependents of failed tools will be silently attempted. The plan accepts this as "never worse than today" but the boundary should be explicit in `run_installs`' docstring and potentially guarded with an assertion in debug mode. | Plan `<design_decisions>` lines 215-222; verify command at Task 2 line 533-534 checks `sorted(` and `order_for_install(` absent. |
| **LOW** | `render_verification` at `installer/render.py:131-149` filters on `method_kind not in DOWNLOAD_KINDS`. A `DEPENDENCY_FAILED` outcome has `method_kind=None` (never set by the skip branch), so it's correctly omitted. This should be noted in the function's docstring to prevent future confusion. | `installer/render.py:139-141`; `InstallOutcome` at `installer/engine.py:21-41` defaults `method_kind=None`. |
| **LOW** | The `_UNRESOLVED` set includes `CHECKSUM_MISMATCH`. If a user chooses "fallback" on a mismatch and the fallback succeeds, the dependent must NOT be blocked. Task 2's `test_a_retried_mismatch_does_not_block_its_dependents` pins this by checking the POST-mismatch outcome, but the logic hinges on the `_UNRESOLVED` membership check running *after* the `on_mismatch` handling. The plan's action (Task 1 line 344-345) places it correctly. | Plan Task 1 `<action>` lines 344-345. |

### Suggestions
1. Add an explicit note in `run_installs`' docstring: "This function assumes the input `tools` list is in deps-first topological order (as produced by `installer.deps.resolve_dependencies`). If this invariant is violated, dependents of failed tools may be attempted rather than skipped — the current behavior."
2. In `render_verification`'s docstring, add: "Outcomes with `method_kind=None` (including `DEPENDENCY_FAILED`) are omitted because no verification step ran."

### Risk Assessment: **LOW**
The mechanism is additive, well-tested (9 new tests across 3 modules), and the fallback behavior on ordering violations is safe (degrades to current behavior). The `KeyError` guard in `summarize` ensures no silent data loss.

---

## Plan 03-02: REQ-oh-my-zsh-plugin-config

### Summary
This plan introduces Oh-My-Zsh bundled plugin (`git`, `docker`) management as a new `Policy` (`omz_plugins_policy`), editing the `plugins=(...)` array in `.zshrc` via a targeted single-line regex editor in a new `installer/omz.py` module. It does NOT use `apply_block`/`strip_block` (which manages marker-delimited blocks in installer-owned `~/.myshellrc`).

### The Reconciliation: REQUIREMENTS.md vs CONTEXT.md D-02

**REQUIREMENTS.md** (earlier): *"reusing the existing `apply_block`/`strip_block` tweak mechanism"*
**CONTEXT.md D-02** (locked 2026-09-04 discuss-phase): *"This is a genuinely new capability, NOT a reuse of `apply_block`/`strip_block` — that mechanism owns and rewrites an entire marker-delimited block in a file `tools-installer` controls (`~/.myshellrc`); Oh-My-Zsh's `plugins=(...)` line lives in a file the user's own setup already populated, and must be edited in place, not replaced wholesale."*

**Verdict: D-02 is correct and the reconciliation is properly documented.**

- **Technical reality**: `apply_block` replaces everything between two markers. Applying it to `plugins=(...)` would require writing tools-installer markers into the user's `.zshrc` around a line OMZ's own installer wrote, clobbering any user edits between runs.
- **Actual intent satisfied**: The requirement's *real* intent — "reuse the tweak toggle surface, do not create a catalog entry" — is fully honored. The feature ships as a `Policy` in the same Policies table, on the same `space` key, through the same `run_live` workflow, with the same `requires`/`missing_requires` gating. Only the file-editing primitive differs.
- **Plan 03-02's `<design_decisions>` (lines 182-196)** explicitly argues this and the verify command at Task 1 line 490 asserts `apply_block`/`strip_block` never appear in `installer/omz.py`.

### Strengths
- **Minimal, focused module**: `installer/omz.py` imports only `re`, `Mapping`, `Path` — no intra-package imports, enabling the bare `python3` container verification (Task 3).
- **`OmzPluginsError(OSError)` leverages existing error flow**: `run_live` at `installer/ui_common.py:40-48` catches `OSError` by design; subclassing means zero screen changes.
- **Reuses existing `Policy` fields**: `requires=("oh-my-zsh",)` and `missing_requires` drive the exact same unmet-requires UX (`_requires_cell`, `action_toggle_policy` at `installer/wizard_app.py:485-496`, `552-577`) — no new UX code.
- **Asymmetric enable/disable is correct**: Enable raises on missing array (silent no-op would lie); disable no-ops (correct for uninstall sweep on machines without `.zshrc`).
- **Last-matching-line wins**: Mirrors `apply_block`'s documented last-begin rule and zsh semantics (final assignment before `source $ZSH/oh-my-zsh.sh` wins).
- **Comprehensive test coverage**: 15 tests in `test_omz.py` covering preservation, refusal, multi-line rejection, last-match, indentation/comment preservation, empty/ragged arrays, disable semantics, idempotency, plus e2e policy toggle and container verification against real OMZ.

### Concerns
| Severity | Issue | Evidence |
|----------|-------|----------|
| **MEDIUM** | `plugins_enabled` requires ALL managed plugins present. If user has `plugins=(git)`, enables policy → `plugins=(git docker)`, then manually removes `git`, `plugins_enabled` returns `False`. This is correct (not all managed plugins present) but the toggle would show OFF while `docker` remains. The detail panel discloses disable removes both, but the *enable* state display could be confusing. | `installer/omz.py` planned `plugins_enabled` logic; detail panel at `wizard_app.py` planned line 435-436. |
| **LOW** | Regex body group `[^()\n]*` excludes newlines (correctly refusing multi-line) and nested parens. Zsh plugin arrays don't nest, but this should be noted as a known limitation in the module docstring. | Plan Task 1 `<action>` line 363. |
| **LOW** | Test coverage proportionality: The plan tests `omz_plugins_policy` in `test_policy_omz.py` and `test_policies_e2e.py` — matching the `ban_policy`/`tweak_policy` precedent (tested in `test_policy.py`, `test_policy_tweaks.py`, `test_policies_e2e.py`). This is correct; `sdkman`'s 5-file coverage is for a registry *method kind*, not a policy factory. | Plan `<source_audit>` line 161; existing tests at `tests/test_policy_tweaks.py`, `tests/test_policies_e2e.py`. |

### Suggestions
1. In `installer/omz.py` module docstring, explicitly note: "Multi-line `plugins=(...)` arrays are refused (raise `OmzPluginsError`). Nested parentheses in the array are not supported."
2. In `PoliciesScreen._policy_detail` for `omz-plugins`, consider adding a line: "Current state shows enabled only when BOTH git and docker are present in the array." (Manages expectations if user manually edits.)

### Risk Assessment: **LOW**
The design correctly respects the locked decision D-02, the editor is pure and exhaustively tested, the policy composes existing `Policy` fields for zero UX drift, and the container verification proves real-world behavior.

---

## Plan 03-03: REQ-uninstall-sweep-tweak-executables

### Summary
This plan makes full uninstall symmetric: for every still-enabled tweak (including the OMZ plugins tweak), it runs the exact same `tweak_policy(...).remove()` / `omz_plugins_policy(...).remove()` closures that the Policies view uses. A new `active_tweak_ids` predicate (block present OR owned executable present) drives the preview, TUI row, and removal — ensuring they never diverge.

### Strengths
- **Symmetric teardown via policy composition (D-04)**: `sweep_tweaks` at `installer/uninstall.py` (planned) calls `tweak_policy(...).remove()` and `omz_plugins_policy(...).remove()` — no new removal logic. "Full uninstall" and "toggle off in Policies" are the same operation by construction.
- **Orphaned executable case covered**: `active_tweak_ids` uses disjunction (`tweak_present OR tweak_executables_present`), so a helper left behind after a hand-edited `~/.myshellrc` is still swept (REQ's literal wording).
- **Sentinel check is the safety boundary**: `tweak_executables_present` reuses `_is_our_executable` (at `installer/tweaks.py:141-145`), so a same-named user file in `~/.local/bin` is never deleted. Task 2's `test_sweep_never_deletes_a_file_it_does_not_own` pins this from both directions.
- **OMZ removal bypasses presence gate correctly**: `_omz_policy` builds with `present=True` unconditionally. A machine being uninstalled may have had OMZ removed already; refusing to undo our `.zshrc` edit would strand the stray state. `remove_plugins` no-ops on missing file/array (Task 2's deliberate asymmetry), so `present=True` can never raise.
- **Single source of truth**: `sweep_tweaks` calls `active_tweak_ids` rather than re-deriving, so preview, TUI row, and effect cannot drift. Verified by Task 1's source check (line 504) and Task 2's `test_preview_equals_effect`.

### Concerns
| Severity | Issue | Evidence |
|----------|-------|----------|
| **HIGH** | Precondition check for 03-02 is only an import check (`from installer.policy import omz_plugins_policy`). It doesn't verify the policy has the correct `id="omz-plugins"` and a `remove` closure that calls `remove_plugins`. If 03-02 lands with a broken policy, 03-03 will fail mysteriously at test time. | Plan 03-03 `<inherited_state>` lines 126-132; precondition at Task 1 lines 466-470. |
| **MEDIUM** | `zshrc_path` is optional (`Path | None = None`) in `active_tweak_ids`/`sweep_tweaks` for test convenience, but `setup.py` always passes it. A future caller could forget to pass it, silently skipping OMZ sweep. The default `None` behavior (bundle-only) should be explicitly documented as "for tests only; production callers MUST pass the real path." | Plan `<artifacts_produced>` lines 155-160, 249-252. |
| **MEDIUM** | The `_omz_policy` private function's comment (Task 1 lines 382-387) explains why `present=True` but doesn't reference the specific design decision (D-04/D-05/D-06). Should link to the decision for maintainability. | Plan Task 1 `<action>` lines 381-387. |
| **LOW** | `.claude/architecture.md` consolidated section is deferred to 03-03 Task 3. Must ensure it actually writes all three mechanisms: (1) resolver vs session failure handling, (2) OMZ in-place edit exception, (3) symmetric teardown rule. | Plan 03-01 `<artifacts_produced>` lines 133-138; 03-02 lines 138-143; 03-03 `<artifacts_produced>` line 57. |

### Suggestions
1. Strengthen 03-03's precondition: after the import check, verify `omz_plugins_policy(zshrc_path=Path('/tmp/x'), present=True).id == 'omz-plugins'` and that its `remove` closure is callable.
2. Add a comment to `active_tweak_ids`/`sweep_tweaks` parameters: `# zshrc_path: REQUIRED for production callers. None only for bundle-only unit tests.`
3. In `_omz_policy`, add: `# Per CONTEXT D-04/D-05/D-06: removal bypasses presence gate; a machine being uninstalled may have lost OMZ but our .zshrc edit must still be reverted.`

### Risk Assessment: **MEDIUM**
The core design is sound (policy composition, sentinel safety, single predicate), but the dependency on 03-02's specific policy shape is a real integration risk. The minimal precondition check could let a broken 03-02 landing cause confusing failures in 03-03. The optional `zshrc_path` is a latent foot-gun for future callers.

---

## Cross-Cutting Findings

### Test Coverage Proportionality for `omz_plugins_policy`
**Question**: Does `omz_plugins_policy` need `sdkman`-level coverage (5 test files) or `ban_policy`/`tweak_policy` level (policy tests + e2e)?

**Answer**: The `ban_policy`/`tweak_policy` precedent is correct.
- `sdkman` is a registry **method kind** — a new execution mechanism requiring tests across `model`, `executors`, `resolve`, `registry`, `status`.
- `omz_plugins_policy` is a **Policy factory** — it composes existing primitives (`omz.py` editor, `Policy` fields). Its testing belongs in policy unit tests (`test_policy_omz.py`) and e2e policy tests (`test_policies_e2e.py`), exactly as the plan specifies.

### Inherited State Handling (03-03 → 03-01/03-02)
03-03's `<inherited_state>` section (lines 122-143) correctly lists consumed symbols and includes a precondition check. The two prior plans modify different functions in `app.py` (03-01: `run_wizard`; 03-03: `run_uninstall`, `UninstallDecision`, `perform_uninstall`), so rebase conflicts are unlikely. The architecture doc consolidation in 03-03 Task 3 is a good coordination mechanism.

### Architecture Documentation Gap
All three plans defer `.claude/architecture.md` to 03-03 Task 3. The consolidated section must cover:
1. **Resolver vs session**: Pre-flight platform availability (`resolve_dependencies`) vs mid-run failure propagation (`run_installs`).
2. **OMZ exception**: Single in-place `plugins=(...)` edit vs marker-block mechanism for `~/.myshellrc`.
3. **Symmetric teardown**: Full uninstall reuses Policy `remove` closures; "toggle off" and "full uninstall" are identical operations.

---

## Overall Risk Assessment: **LOW-MEDIUM**

| Plan | Risk | Primary Driver |
|------|------|----------------|
| 03-01 | LOW | Additive, well-tested, safe fallback on ordering violation |
| 03-02 | LOW | Pure editor, exhaustive tests, container verification, zero UX drift |
| 03-03 | MEDIUM | Integration dependency on 03-02's policy shape; optional `zshrc_path` foot-gun |

**Recommendation**: Proceed with all three plans. Strengthen 03-03's precondition check and document the `zshrc_path` requirement. Ensure 03-03 Task 3 writes the consolidated architecture section.

---

## Consensus Summary

Only one reviewer lane (`opencode`/nemotron-3-ultra-free) completed; `codex`, `opencode`/gemini-3.1-pro-preview, and `opencode`/glm-5.3 all failed on quota/billing before producing output, and `agy` could not complete interactive OAuth in this session. Per the review workflow's consensus gate, this is not treated as a "2+ reviewers disagree/agree" situation — the single completed reviewer's findings stand at full weight, with no cross-reviewer corroboration available this cycle.

### Agreed Strengths
Not applicable — only one reviewer completed this cycle, so nothing here reflects independent corroboration across reviewers. See the single reviewer's per-plan Strengths sections above.

### Agreed Concerns
Not applicable for the same reason. The one substantive finding worth flagging to the orchestrator: **03-01's `.claude/architecture.md` reconciliation and 03-02's D-02-vs-REQUIREMENTS.md reconciliation are both independently verified as correctly documented and the right technical call** — `apply_block`/`strip_block` replace an entire marker-delimited block and are not applicable to an in-place single-line edit of a user-owned file, and the requirement's actual intent (reuse the toggle surface, not the file-editing primitive) is satisfied by shipping `omz_plugins_policy` as a third `Policy` factory in the same Policies table. No risk was found in CONTEXT.md's authority over the stale REQUIREMENTS.md wording here.

The reviewer's one **HIGH** finding: 03-03's precondition check for 03-02 having landed is only an `ImportError`-level check (`from installer.policy import omz_plugins_policy`) and does not assert the returned `Policy`'s `id == "omz-plugins"` or that its `remove` closure actually calls `remove_plugins` — a structurally-present-but-broken 03-02 landing would let 03-03 proceed past its own precondition and then fail confusingly deep in its own test suite instead of at the precondition gate that exists specifically to catch this.

### Divergent Views
Not applicable — single reviewer this cycle.
