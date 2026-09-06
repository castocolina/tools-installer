---
phase: 6
reviewers: [opencode-plan-review]
reviewed_at: 2026-09-06T03:23:30Z
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
consensus to synthesize — the sections below report that single reviewer's findings
at full weight (it ran source-grounded, with `file:line` citations verified against
the live repo, and carries no evidence-quality discount marker).

### Agreed Strengths
N/A — single reviewer this cycle.

### Agreed Concerns
N/A — single reviewer this cycle.

### Divergent Views
N/A — single reviewer this cycle.

## OpenCode Review (opencode-plan-review)

# Plan Review — 06-01-PLAN.md (Phase 6: SDKMAN Hardening & Registry-Authoring Guidelines)

Verified against the live repo: `.planning/phases/06-sdkman-hardening-registry-authoring-guidelines/06-01-PLAN.md` exists on disk; every file/line reference below was opened and checked.

## Summary

A tight, well-grounded documentation-and-verification plan that does exactly what Phase 6 asks and nothing more: reproduce the Tier-3 `sdk install java` evidence fresh, record the SC#2 no-pin resolution as registry comments guarded by a test, and write the two locked guidelines (D-01/D-02) into `.claude/architecture.md` plus three decision rows into `.planning/PROJECT.md`. Every line citation I checked is accurate against the current tree, the scope boundary (no changes to `model.py`/`executors.py`/`resolve.py`/`status.py`) is correctly enforced, and the TDD ordering for the guard test follows the project's own convention. The only substantive reservation is an interpretation gap on SC#1's "all five JVM tools" wording, which the plan satisfies via unit tests for four of the five and a live e2e for `java` only — defensible per the research's own recommendation, but worth making explicit.

## Strengths

- **Every code citation checks out.** `installer/registry.toml:1297-1311` (`sdkman`), `:1313-1326` (`java`, `requires = ["sdkman"]`, single `kind="sdkman"` method, no `version` — confirmed by a live `load_tools` run), `:1225-1241` (the `codegraph` `# Verified 2026-09-05` comment with named re-verify condition), `:1829-1928` (the mmdc/puppeteer comment block), `installer/executors.py:456-468` (`_sdkman` with the `?ci=true` comment and `shlex.join`), `.claude/architecture.md` exactly 157 lines ending with the Phase 3 section, `.planning/PROJECT.md:88-97` Key Decisions table with Phase 5 rows at 96-97. The plan was written against the real tree, not from memory.
- **Correct tier discipline.** The e2e check is routed to Tier-3 container evidence, never a pytest file — matching `.claude/testing.md`'s deterministic/offline rule and ONESHOT-RULES Rule 14 (verified: colima is running right now, docker server 29.5.2, so the precondition is live). The plan even pre-empts the research's Pitfall 2 (a network-dependent test) and Pitfall 3 (a "safety" version pin) with explicit prohibitions.
- **Guard test follows the proven pattern.** `test_volta_entry_records_the_npm_postinstall_finding` (tests/test_registry.py:285-288), `test_mmdc_entry_records_the_brew_rejection_finding` (:290-293), and `test_puppeteer_entry_records_the_postinstall_and_arm64_caveats` (:296-300) all do exactly `REGISTRY.read_text()` + substring asserts; the new test replicates this shape, and the plan specifies fail-first ordering consistent with PROJECT.md's "failing tests before implementation" constraint. I ran `tests/test_registry.py` directly (75 pass) — the baseline the plan must not regress is green.
- **Scope boundary is airtight.** `files_modified` (registry.toml, test_registry.py, architecture.md, PROJECT.md) matches exactly what the two tasks touch; the plan twice forbids touching the four installer modules and forbids adding a `version` param — the resolution is data/comment, not schema, which is the whole point of the research's finding.
- **Anomaly handling is correct.** Task 1 Part A explicitly treats a prompt/hang as a Rule 9 destructive anomaly (stop, don't write a contradicting comment), and forbids hardcoding the dynamic `25.0.4-tem`-style version string — both directly address the research's reproducibility note.
- **Frontmatter compliant.** `cross_ai: true` present (ONESHOT-RULES Rule 12); wave 1, no dependencies, matching the roadmap's "Depends on: Nothing".

## Concerns

- **MEDIUM — SC#1's "all five tools" is only e2e-verified for `java`.** ROADMAP SC#1 reads "java/gradle/maven/groovy/springbootcli are confirmed installing exclusively through SDKMAN with real (not just unit-level) verification". The plan's fresh container run covers `sdk install java` only; `gradle`/`maven`/`groovy`/`springbootcli` exclusivity rests on the existing unit test (`tests/test_registry.py:122-140`, which I verified asserts `["sdkman"]` for all five) plus their registry shape (`installer/registry.toml:1328-1386`, single `sdkman` method each). The research's Open Question 1 recommends exactly this (java-only comment, others covered by existing assertions), so the interpretation has backing — but the plan never states the interpretation, leaving a verifier to either flag SC#1 as partially met or accept an unstated judgment call.
- **LOW — Guard test asserts file-wide substrings, not block-scoped.** The five substrings (`sdkman_auto_answer`, `Tier-3 container`, `$CURRENT`, `no vendor prompt`, `SC#2`) are asserted against the whole `registry.toml` text (tests/test_registry.py:285-324 precedent), so a comment containing them anywhere — e.g. appended to the puppeteer block — would pass. Consistent with existing convention, but the test does not actually pin the comments to above the `sdkman`/`java` entries as the must_haves claim.
- **LOW — Non-prompt failure modes of the fresh run are under-specified.** Part A enumerates "a prompt DOES appear or the run hangs" as the anomaly condition, but not a non-zero exit from network/API failure (the research's Assumption A1/A2 territory — SDKMAN's `candidates/default/java` API is live and can change). Rule 9's "unrecoverable tool failure" would catch it in practice, but an executor following Part A's letter could treat `EXIT_CODE=1` from a download failure as "doesn't match research" without the same stop-don't-write instruction.
- **LOW — Threat-model and research cosmetic drift.** The STRIDE register says `sk_install`; SDKMAN's actual function is `__sdk_install` (per the research's own source excerpt). The research also reports docker "29.8.0" while the machine's server reports 29.5.2 — immaterial to the mechanism, but the plan inherits both strings.
- **LOW — `.planning/PROJECT.md`'s "Last updated" footer (line 100, "2026-09-04 after initial roadmap creation") is not updated by Task 2**, so the file's own freshness marker goes stale the moment three new decision rows land.

## Suggestions

- Add one sentence to Task 1 (or the plan's success-criteria mapping) stating the SC#1 interpretation explicitly: exclusivity for all five tools is proven by the existing registry-shape tests (`tests/test_registry.py:122-140`) plus the executor's shared code path, while the *real* e2e requirement is the `sdk install java` non-interactivity check SC#1 itself names — closing the verifier's judgment gap for ~zero tokens.
- In the new guard test, additionally assert locality: e.g. slice the text between the `id = "sdkman"` and `id = "java"` blocks (or assert each substring appears in the ~40 lines preceding `[[tool]]\nid = "java"`), so the comments cannot silently migrate away from the entries they document.
- Extend Part A's anomaly clause to "a prompt appears, the run hangs, OR the exit code is non-zero for any reason" — same stop-don't-write instruction, one more sentence.
- Have Task 2 also bump `.planning/PROJECT.md`'s `*Last updated:*` footer to the run date — it's already editing the file.

## Risk Assessment

**LOW.** The blast radius is two TOML comments, one substring-assertion test, one markdown section, and three table rows — no executable installer code changes, no schema changes, no new kinds (so ONESHOT-RULES Rule 7's mirror requirement is untouched, verified: sdkman tests already exist in `test_model.py:546-580`, `test_status.py:149-185`, `test_registry.py:103-140`). The one technically risky claim (SC#2, no pin needed) was already proven live against SDKMAN's own installed source, and the plan re-derives it fresh rather than trusting the research. The environment precondition (colima + docker) is confirmed running on this machine today. The only finding that could block approval is the MEDIUM SC#1-interpretation gap, and it is a documentation-of-intent fix, not a structural one.

---
