---
phase: 6
reviewers: [opencode-plan-review]
reviewed_at: 2026-09-06T03:40:47Z
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

This is the plan's **second** review cycle. The four concerns raised in cycle 1
(`SC#1` interpretation, guard-test locality, non-zero-exit handling, `PROJECT.md`
footer bump) were confirmed as correctly incorporated in the revised plan (commit
`40c2960`). This cycle surfaces new findings against the revised plan.

### Agreed Strengths
N/A — single reviewer this cycle.

### Agreed Concerns
N/A — single reviewer this cycle.

### Divergent Views
N/A — single reviewer this cycle.

## OpenCode Review (opencode-plan-review)

# Plan Review — Phase 6 / 06-01

## Summary

The revised plan is well-scoped and executable, and all four cycle-1 concerns were incorporated: SC#1's interpretation is explicit, comment assertions are block-local, non-zero infrastructure failures are distinguished from prompt anomalies, and `PROJECT.md`'s footer is updated. However, the plan would still write one factually incorrect enforcement claim and several stronger SDKMAN guarantees than its fresh verification establishes. Revision is recommended before execution.

## Strengths

- **Cycle-1 feedback is fully represented.**
  - SC#1 interpretation is explicit in `.planning/phases/06-sdkman-hardening-registry-authoring-guidelines/06-01-PLAN.md:138-146` and `:444-450`.
  - Locality checks are required at `06-01-PLAN.md:250-262`; exact tool IDs are safe anchors because registry uniqueness is tested at `tests/test_registry.py:26-28`.
  - Infrastructure/network failures get retry, investigation, and "do not write comments while unresolved" handling at `06-01-PLAN.md:172-185`.
  - The stale `PROJECT.md` footer is explicitly updated and verified at `06-01-PLAN.md:387-407`.
- **The scope matches the phase.** Only registry comments, one guard test, architecture guidance, and project decisions change (`06-01-PLAN.md:8-17`, `:78-87`); executable installer logic is deliberately untouched.
- **Existing SDKMAN routing evidence is real and correctly identified.** All five JVM tools are guarded as single-method SDKMAN entries with expected candidate and bin directory values in `tests/test_registry.py:103-140`; the production executor safely builds the command through `shlex.join` at `installer/executors.py:456-468`.
- **The verification tier is appropriate.** A network-dependent SDKMAN install belongs in a disposable container, not pytest, because tests must remain deterministic and offline (`.claude/testing.md:24-29`), while Tier 3 explicitly names `sdk install java` as a container case (`.planning/ONESHOT-RULES.md:168-172`).
- **The recording mechanism follows existing precedent.** The detailed, dated CodeGraph verification comment is at `installer/registry.toml:1225-1241`, and committed-comment tests already use `REGISTRY.read_text()` at `tests/test_registry.py:285-300`.

## Concerns

- **CRITICAL — The planned D-02 documentation contains a false enforcement claim.** The plan requires saying the SDKMAN carve-out is enforced through "prose, not a lint rule" and that no test enforces it (`06-01-PLAN.md:340-353`). In reality, `test_java_tools_install_exclusively_through_sdkman` explicitly rejects any native/brew fallback for all five tools at `tests/test_registry.py:122-140`. The general brew preference may remain documentation-only, but the named SDKMAN exception is already test-enforced.
- **HIGH — The fresh run does not substantiate the source-level claims the comments must make.** Part A only installs with `?ci=true` and observes one successful first install (`06-01-PLAN.md:148-166`), while Part B must claim SDKMAN has exactly one prompt, describe its `$CURRENT` guard, and guarantee future upgrades cannot prompt (`:201-225`). The plan even says the mechanism "does not change between runs" (`:124`), but the registry downloads an unpinned current script from `https://get.sdkman.io?ci=true` (`installer/registry.toml:1306-1311`), and the research explicitly warns that future SDKMAN releases may add prompts (`06-RESEARCH.md:586-591`). A successful auto-answer run alone cannot prove those source-level statements.
- **HIGH — "Permanently disables" is too broad for brownfield installations.** SDKMAN is treated as installed whenever its `detect_path` exists (`installer/status.py:26-29`), and `install_tool` then skips this project's `?ci=true` bootstrap (`installer/engine.py:80-81`). Therefore, an existing SDKMAN installation may retain `sdkman_auto_answer=false`; the project cannot truthfully state that its bootstrap permanently configures every SDKMAN installation through which it installs candidates. The clean-machine no-pin conclusion remains supported, but the durable comment needs narrower scope.
- **MEDIUM — Required source line references will be stale immediately.** Task 2 mandates citing `mmdc`/`puppeteer` at `installer/registry.toml:1829-1928` (`06-01-PLAN.md:323-326`), but Task 1 first inserts two comment blocks around lines 1297 and 1313. The currently correct downstream range (`installer/registry.toml:1829-1928`) will shift before Task 2 writes the documentation.
- **MEDIUM — Phase-level diff verification contradicts the required footer edit.** Task 2 correctly requires changing the existing footer (`06-01-PLAN.md:387-395`) and its acceptance criteria allow that replacement (`:401-407`), but the phase-level check says both documentation files must show "only additions" and no altered content (`:434-441`). Those conditions cannot both be literally true for `.planning/PROJECT.md`.

## Suggestions

- Reword D-02 documentation to distinguish the two policies: the **general brew preference** is documentation-only, while the **SDKMAN Java exception** is additionally guarded by `tests/test_registry.py:122-140`.
- During the fresh container run, capture `sdk version` and inspect the installed current `sdkman-install.sh`/environment helper around the prompt and default-version branches. Record the verified SDKMAN script version and add a "re-verify when the script version changes materially" condition, matching `installer/registry.toml:1239-1241`.
- Replace "permanently disables" with wording scoped to installer-managed clean bootstraps, and explicitly acknowledge that pre-existing SDKMAN installations can have different configuration.
- Cite stable tool IDs and test names in `.claude/architecture.md`, or calculate line ranges after Task 1 instead of hardcoding pre-edit ranges.
- Change the phase-level diff criterion to: architecture is addition-only; `PROJECT.md` changes only by adding three rows and replacing its footer.

## Risk Assessment

**MEDIUM.** No executable production code changes, so runtime blast radius is low. The main risk is institutionalizing inaccurate or stale guarantees in the project's canonical authoring guidance and then pinning those claims with tests. Once the enforcement wording and SDKMAN evidence/freshness issues are corrected, the plan should be **LOW risk**.

---
