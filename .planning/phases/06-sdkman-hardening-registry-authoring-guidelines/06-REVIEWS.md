---
phase: 6
reviewers: [opencode-plan-review]
reviewed_at: 2026-09-06T01:09:00Z
plans_reviewed: [06-01-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review (reasoning=high)"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 6

## Consensus Summary

Only one reviewer instance ran this cycle (`opencode-plan-review`, an OpenCode-backed
identity configured in `review.reviewer_instances`), so there is no cross-reviewer
consensus to synthesize — the section below reports that single reviewer's findings
at full weight (it ran source-grounded, with `file:line` citations verified against
the live repo, and carries no evidence-quality discount marker).

This is the plan's **third** review cycle. Cycle 2 raised five findings against an
earlier revision of `06-01-PLAN.md` (CRITICAL: false "no test enforces the SDKMAN
carve-out" claim; HIGH: fresh verification insufficient to support the source-level
prompt/`$CURRENT`-guard claims; HIGH: "permanently disables" too broad for brownfield
installs; MEDIUM: stale downstream line references; MEDIUM: phase-diff check
contradicting the required `PROJECT.md` footer edit). The plan was revised again
before this cycle. This cycle verifies each cycle-2 finding against the new revision
and surfaces new findings.

### Agreed Strengths
N/A — single reviewer this cycle.

### Agreed Concerns
N/A — single reviewer this cycle.

### Divergent Views
N/A — single reviewer this cycle.

## OpenCode Review (opencode-plan-review)

# Plan Review — Phase 6 / 06-01

## Summary

The revised plan is well-scoped and substantially improved, but two cycle-2 issues remain partially unresolved: the threat model still misclassifies the SDKMAN carve-out as documentation-only, and the fresh execution does not inspect the SDKMAN source used to support its source-level claims. Runtime blast radius is low because production logic is unchanged, but the plan should be corrected before canonical comments and guidance are recorded.

## Cycle-2 Finding Verification

| Prior finding | Status | Evidence |
|---|---|---|
| D-02 falsely says the SDKMAN carve-out is unenforced | **Partially fixed** | The implementation instructions now correctly distinguish the documented-only general brew preference from the test-enforced carve-out at `06-01-PLAN.md:73-79` and `06-01-PLAN.md:391-402`. However, the threat model still calls "the SDKMAN carve-out itself" a documented-only convention at `06-01-PLAN.md:485`, contradicting the enforcement at `tests/test_registry.py:122-140`. |
| Fresh run does not substantiate source-level prompt claims | **Partially fixed** | The plan now records `sdk version` and adds a re-verification condition at `06-01-PLAN.md:167-170` and `06-01-PLAN.md:253-256`. But Part A never inspects the freshly installed source, while Part B must claim what "that container's installed SDKMAN source" shows at `06-01-PLAN.md:239-245`; it also still says the mechanism "does not change between runs" at `06-01-PLAN.md:127`. |
| "Permanently disables" is too broad for brownfield installs | **Fixed** | The planned comments explicitly limit the guarantee to installer-managed clean bootstraps and explain the brownfield exception at `06-01-PLAN.md:210-230`. This matches `is_installed` detecting `detect_path` at `installer/status.py:26-29` and `install_tool` returning early at `installer/engine.py:80-81`. |
| Downstream `mmdc`/`puppeteer` line references become stale | **Fixed** | Task 2 now requires a stable anchor description rather than the pre-edit downstream line range at `06-01-PLAN.md:358-368`; only the unaffected CodeGraph range is retained. |
| Phase diff check contradicts the required footer replacement | **Fixed** | The phase check now explicitly permits three row additions plus one footer replacement at `06-01-PLAN.md:495`, matching Task 2's required edit at `06-01-PLAN.md:442-450`. |

## Strengths

- The plan correctly preserves the existing implementation. SDKMAN candidates are already single-method entries enforced by `tests/test_registry.py:122-140`, while command arguments are safely rendered through `shlex.join` at `installer/executors.py:462-468`.
- The Tier-3 test is appropriate and safely isolated. The project explicitly identifies `sdk install java` as a container-verification case at `.planning/ONESHOT-RULES.md:168-172`.
- Failure handling is actionable: prompt/hang anomalies stop the registry edit, while infrastructure failures receive one retry and investigation at `06-01-PLAN.md:167-194`.
- The brownfield limitation is now accurately grounded in production behavior at `installer/status.py:26-29` and `installer/engine.py:80-81`.
- The no-pin invariant is verified structurally through registry parsing at `06-01-PLAN.md:318`, rather than relying only on prose.
- Comment locality checks improve on existing whole-file substring tests such as `tests/test_registry.py:285-300`.

## Concerns

- **CRITICAL — The threat model still contains the D-02 factual error.**
  `06-01-PLAN.md:485` cites "the SDKMAN carve-out itself" as an example of a documented-only convention. The carve-out is explicitly enforced for all five JVM tools at `tests/test_registry.py:122-140`. This also contradicts the corrected Task 2 instructions at `06-01-PLAN.md:395-402`.

- **HIGH — Fresh evidence still does not establish the planned source-level claims.**
  Part A only checks configuration, version, and one installation outcome at `06-01-PLAN.md:152-176`. It does not inspect `sdkman-install.sh` or `sdkman-env-helpers.sh`, yet the resulting comment must claim that the freshly installed source contains exactly one prompt, uses the `$CURRENT` guard, and resolves the default by one HTTP call at `06-01-PLAN.md:234-256`. The research itself limits that conclusion to SDKMAN script 5.23.0 at `06-RESEARCH.md:588-591`.

- **HIGH — The plan still makes an absolute mutability claim about unpinned upstream code.**
  `06-01-PLAN.md:127` says the mechanism "does not change between runs," but the registry fetches the current unpinned installer at `installer/registry.toml:1306-1311`. The later re-verification caveat reduces the risk but does not make this earlier assertion true.

- **MEDIUM — Per-task commit gates are weaker than repository policy.**
  Task 1 runs selected tests plus `make validate` at `06-01-PLAN.md:313-325`; Task 2 runs grep checks plus `make validate` at `06-01-PLAN.md:452-463`. The full `make validate && make test` gate appears only at phase close at `06-01-PLAN.md:492-493`, while each coherent commit is required to pass both commands at `.claude/git-workflow.md:10-12` and the exact pre-commit tree must pass them per `AGENTS.md:28-29`.

- **LOW — One new hardcoded test line range can still become stale during execution.**
  Task 2 requires writing `tests/test_registry.py:122-140` into durable architecture documentation at `06-01-PLAN.md:397-399`, while Task 1 only says to place the new test "near" that function at `06-01-PLAN.md:271-274`. Inserting it before the existing function would immediately invalidate the citation.

## Suggestions

- Replace the final clause of `T-06-03` with an actually documentation-only convention, or remove the parenthetical example entirely.
- During Part A, inspect the freshly installed `sdkman-install.sh` and `sdkman-env-helpers.sh`; capture the relevant excerpts and verify the expected prompt count, `$CURRENT` guard, and default-candidate lookup before writing the comments.
- If the freshly observed SDKMAN script version differs from the researched 5.23.0, require source re-analysis before proceeding rather than merely recording a future re-verification caveat.
- Replace "does not change between runs" with "was established by the source inspected during research and must be reconfirmed against the freshly installed script."
- Run `make validate && make test` before each task commit, or explicitly make both tasks one atomic commit performed only after the phase-level gate.
- Cite `test_java_tools_install_exclusively_through_sdkman` by symbol name in durable documentation, or require the new guard test to be inserted after it and calculate the final range after editing.

## Risk Assessment

**HIGH.** Production-code risk is low, but the plan would permanently record and test source-level claims that its fresh procedure does not currently verify, while retaining one directly false enforcement statement. Correcting those issues should reduce the phase to **LOW risk**.

---
