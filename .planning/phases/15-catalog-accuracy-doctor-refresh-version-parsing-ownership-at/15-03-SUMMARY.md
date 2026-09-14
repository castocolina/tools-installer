---
phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
plan: "03"
subsystem: catalog
tags: [registry, toml, tui, textual, tier-classification, tdd]

# Dependency graph
requires: []
provides:
  - "ast-grep and puppeteer reclassified from tier=\"user\" to tier=\"ai\" in installer/registry.toml (D-07, D-08)"
  - "D-09 borderline review (mmdc, gitleaks, vale, drawio-cli stay user-tier) pinned by a dedicated test instead of living only in a discussion log"
  - "The two deliberate registry tripwires (test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm renamed to ...an_ai_tier..., test_registry_tier_distribution_is_pinned's Counter) updated in the same commit as the data"
  - "The AI-tab source comment and its user-visible palette string in installer/ui_common.py rewritten to cite only tier=\"ai\" tools, guarded by a test that re-derives tier from the live registry (D-10)"
affects: [ui, catalog-browsing]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
# Same estimateTokens scale (chars/4 over the realized diff), never a harness token count.
actuals:
  tokens: 2002
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Backtick-delimited citation scanning: a comment's positive contract is read from backticked catalog-id tokens, with a length->=5 unbackticked residual sweep (minus an explicit English-word exclusion set) to catch uncited drift without false-positiving on short registry ids that are also ordinary words (just, git, bat, sd, pi, watch)"

key-files:
  created: []
  modified:
    - installer/registry.toml
    - installer/ui_common.py
    - tests/test_registry.py
    - tests/test_ui_common.py

key-decisions:
  - "D-07/D-08 implemented as pure data edits (tier field only) with inline registry comments recording the reason next to each change, per the plan's registry comment-style convention"
  - "D-09 recorded as a dedicated group-assertion test (test_d09_borderline_tools_stay_user_tier) rather than folding it into the existing test_reconciliation_tier_audit_confirms_all_11_re_added_rows, which already covers drawio-cli alone for a different historical reason and should not be overloaded with an unrelated review's scope"
  - "D-10's positive-citation gate uses backticks as the citation marker (not a hardcoded tool-name allowlist), so future edits to the comment stay honest without the test needing updates for which specific tools are cited"

patterns-established:
  - "Registry tier edits are documented inline (a # comment beside the changed field, referencing the decision ID) rather than only in a discussion log or PR description"

requirements-completed: ["D-07", "D-08", "D-09", "D-10"]

coverage:
  - id: D1
    description: "ast-grep and puppeteer moved to tier=\"ai\" with inline reason comments; category/audience/priority/cmd/requires/methods on both blocks unchanged; no block reordered"
    requirement: "D-07"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_ast_grep_tier_is_ai"
        status: pass
    human_judgment: false
  - id: D2
    description: "puppeteer moved to tier=\"ai\"; its tripwire test renamed from test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm to test_puppeteer_is_an_ai_tier_node_tool_requiring_pnpm and re-asserted, requires/recommends/method fields unchanged"
    requirement: "D-08"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_puppeteer_is_an_ai_tier_node_tool_requiring_pnpm"
        status: pass
    human_judgment: false
  - id: D3
    description: "mmdc, gitleaks, vale and drawio-cli confirmed and pinned as tier=\"user\" (the D-09 borderline review, closed rather than left in a discussion log); the whole-registry tier Counter is pinned to {system: 26, ai: 17, user: 46}, tripping on any third row moving"
    requirement: "D-09"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_d09_borderline_tools_stay_user_tier"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_registry_tier_distribution_is_pinned"
        status: pass
    human_judgment: false
  - id: D4
    description: "resolve_dependencies/install ordering unaffected by the two tier moves (tier is a browsing label, not an install-order mechanism)"
    requirement: "D-07"
    verification:
      - kind: unit
        ref: "tests/test_deps.py (full file)"
        status: pass
      - kind: unit
        ref: "tests/test_resolve.py (full file)"
        status: pass
    human_judgment: false
  - id: D5
    description: "AI-tab source comment in installer/ui_common.py rewritten to cite only tools that are tier=\"ai\" today (rg, fd, codegraph, ast-grep, all backticked), dropping the stale claude/codex framing, still explaining the Tier-vs-Audience distinction; guarded by a test that re-derives every cited id's tier from the live registry and cannot fire on ordinary English words"
    requirement: "D-10"
    verification:
      - kind: unit
        ref: "tests/test_ui_common.py#test_ai_tab_comment_only_cites_ai_tier_tools"
        status: pass
    human_judgment: false
  - id: D6
    description: "The AI row's palette string (the ctrl+p copy a user reads) rewritten from \"AI - agents you run and tools agents call\" to \"AI - tooling an agent session runs on\"; keeps the \"AI - \" prefix; name/label/mode/glyph/style/hint/actions on the row byte-identical so the nav/enum and registry-completeness tests pass unmodified"
    requirement: "D-10"
    verification:
      - kind: unit
        ref: "tests/test_ui_common.py#test_ai_tab_comment_only_cites_ai_tier_tools"
        status: pass
      - kind: unit
        ref: "tests/test_ui_common.py#test_tier_views_lead_the_nav_and_match_the_tier_enum"
        status: pass
      - kind: unit
        ref: "tests/test_ui_common.py#test_view_registry_is_complete_and_consistent"
        status: pass
    human_judgment: false

# Metrics
duration: 13min
completed: 2026-09-14
status: complete
---

# Phase 15 Plan 03: Catalog Tier Fixes Summary

**ast-grep and puppeteer reclassified to the AI tab, the D-09 borderline review pinned by test, and the AI-tab comment/palette rewritten to describe the tab that exists today**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-14T22:46:26Z
- **Completed:** 2026-09-14T22:58:57Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `ast-grep` and `puppeteer` moved from `tier = "user"` to `tier = "ai"` in `installer/registry.toml`, each with an inline comment recording the reason (D-07, D-08)
- `mmdc`, `gitleaks`, `vale` and `drawio-cli` confirmed unchanged as `user`-tier, now pinned by a dedicated test (`test_d09_borderline_tools_stay_user_tier`) closing the "borderline" review the roadmap left open (D-09)
- The two deliberate registry tripwires updated in the same commits as the data they guard: `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm` renamed to `test_puppeteer_is_an_ai_tier_node_tool_requiring_pnpm` and re-asserted; `test_registry_tier_distribution_is_pinned` now reads `{system: 26, ai: 17, user: 46}`
- The AI tab's stale source comment (still naming `claude`/`codex` as examples) rewritten to cite only tools that are actually `tier = "ai"` today, backticked, with a test (`test_ai_tab_comment_only_cites_ai_tier_tools`) that re-derives every citation's tier from the live registry
- The AI row's user-visible `palette` string (the ctrl+p description) rewritten from "agents you run and tools agents call" to "tooling an agent session runs on," fixing the same untruth in the copy a human reads, not just the source comment

## Task Commits

Each task followed the RED-GREEN TDD cycle and was committed atomically:

1. **Task 1: the two misfiled rows move tabs, and every tier tripwire moves with them (D-07, D-08, D-09)**
   - RED: `5d3a391` — `test(15-03): pin ai-tier for ast-grep/puppeteer and D-09 borderline tools`
   - GREEN: `2ab0fbb` — `feat(15-03): move ast-grep and puppeteer to ai tier (D-07, D-08)`
2. **Task 2: the AI tab's comment AND its palette line describe the tab that exists today, and a test keeps them that way (D-10)**
   - RED: `9d53aba` — `test(15-03): pin the AI-tab comment and palette to cite only ai-tier tools`
   - GREEN: `303ffd4` — `feat(15-03): rewrite the AI-tab comment and palette to match the live tab (D-10)`

_No REFACTOR commits — both GREEN implementations were minimal (two-character-value data edits, one comment/palette rewrite) with no obvious cleanup opportunity._

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Status |
|------|-----|-------|----------|--------|
| Task 1 (ast-grep/puppeteer tier) | `5d3a391` | `2ab0fbb` | — | Pass |
| Task 2 (AI-tab comment/palette) | `9d53aba` | `303ffd4` | — | Pass |

Both RED-phase commits were verified by manually inspecting the pytest failure output before the GREEN edit was made: the target test(s) named in each task failed on the planned tier/citation assertion (never a collection error, fixture crash, or unrelated failure), and the unrelated tests in the same file stayed green. The `gsd_run check tdd-red-evidence` automated verb was not used to gate this — it parses Node.js `node --test` TAP output (`# tests N` / `ok N - <name>` lines), and this project has no `pytest-tap` plugin, so its parser cannot read pytest's native output. Manual verification substituted for the automated verdict; the RED evidence itself (pasted into each RED commit message) is otherwise equivalent to what the tool would have classified as `RED_EVIDENCE_OK`.

## Files Created/Modified
- `installer/registry.toml` — `ast-grep.tier` and `puppeteer.tier` changed `user` -> `ai`, each with an inline `#` comment recording the reason; no other field touched, no block reordered
- `installer/ui_common.py` — the `View(name="ai", ...)` row's comment and `palette` string rewritten; every other field on the row (`name`, `label`, `mode`, `glyph`, `style`, `hint`, `actions`) byte-identical
- `tests/test_registry.py` — renamed `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm` -> `test_puppeteer_is_an_ai_tier_node_tool_requiring_pnpm`; updated `test_registry_tier_distribution_is_pinned`'s expected Counter; added `test_d09_borderline_tools_stay_user_tier` and `test_ast_grep_tier_is_ai`
- `tests/test_ui_common.py` — added `test_ai_tab_comment_only_cites_ai_tier_tools`

## Decisions Made
- Placed the D-09 group-assertion test as its own function (`test_d09_borderline_tools_stay_user_tier`) rather than extending `test_reconciliation_tier_audit_confirms_all_11_re_added_rows`, which already asserts `drawio-cli` alone for an unrelated historical audit (the 11 re-added rows from commit `9f6274b`) — keeping D-09's four-tool group assertion separate avoids conflating two different reviews in one test's docstring/rationale.
- Wrote the new AI-tab comment and palette avoiding any prose mention of `claude`/`codex` (even unbackticked) — both are registry ids of length >= 5 that are not in the test's English-word exclusion set, so naming them even as contrast (`"unlike claude/codex"`) would trip the unbackticked-citation sweep. Described the tab positively instead ("tooling that runs underneath an agent session, or is consumed BY an agent") rather than contrasting it against the `user` tab by name — exactly the behavior the plan's `<action>` called out ("make the contrast without naming a specific row").
- Followed the plan's TDD flow literally for each task: wrote failing tests against the unmodified registry/comment first, confirmed the RED failure was the planned assertion (not a collection or fixture error), committed test-only, then made the minimal data/comment edit and re-verified GREEN before committing feat-only.

## Deviations from Plan

None - plan executed exactly as written. One toolchain note (not a deviation from the plan's content, but worth recording): `gsd_run check tdd-red-evidence` could not be used to machine-verify the RED phases because it expects Node.js TAP-formatted test output and this is a pytest project with no TAP plugin; RED evidence was verified manually instead (see TDD Gate Compliance above).

## Issues Encountered
- The worktree this plan executed in (`worktree-agent-a95588e5b21eb4dfd`) started 132 commits behind the phase-15 branch tip (`c157844`) — a stale base that predated the phase-15 plan files entirely. Verified the worktree's branch was a clean ancestor of the phase-15 tip with no local changes, then fast-forwarded (`git merge --ff-only`) before starting any task work. No work was lost; this is noted here for phase-execution-infrastructure visibility, not as a plan deviation.
- `ruff format` flaged one line-length issue in the new `test_ai_tab_comment_only_cites_ai_tier_tools` test (the `re.findall` line); ran `ruff format` to auto-fix before the GREEN commit, then re-verified the full test suite stayed green.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Task 1 and Task 2 are independent within this plan (Task 1's `wave: 1`, `depends_on: []`) and both landed cleanly; no blockers for the rest of phase 15's plans.
- `installer/registry.toml`'s tier distribution is now `{system: 26, ai: 17, user: 46}` — any future catalog edit that changes this count without updating `test_registry_tier_distribution_is_pinned` in the same commit will fail the suite by design.
- The AI-tab comment/palette are now self-correcting: `test_ai_tab_comment_only_cites_ai_tier_tools` will fail on the next accidental drift (a tool cited that later changes tier, or a new stale claim reintroduced), rather than requiring a human to notice.

## Self-Check: PASSED

All created/modified files verified present on disk; all 4 commit hashes (`5d3a391`, `2ab0fbb`, `9d53aba`, `303ffd4`) verified present in `git log`.

---
*Phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at*
*Completed: 2026-09-14*
