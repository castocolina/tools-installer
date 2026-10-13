# Phase 5: Registry Method Corrections (codegraph/mmdc/puppeteer) - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

`codegraph`, `mmdc`, and the puppeteer/chrome-headless-shell chain `mmdc`
depends on all get explicit, researched, correctly-recorded install methods.
This phase is a **method correction on existing/soon-to-exist registry
entries**, not a scope-expansion phase: it does not add new tools beyond
`puppeteer`/`chrome-headless-shell` (already in ROADMAP's SC#3), does not
touch `codegraph`'s postinstall/MCP-registration behavior (that is Phase 9's
`REQ-codegraph-mcp-postinstall`), and does not add `graphify` (that is Phase
8's `REQ-uv-tool-executor`/`REQ-agent-host-entries`) — both were raised and
explicitly ruled out of this phase's scope during discussion (see
`<specifics>`).

</domain>

<decisions>
## Implementation Decisions

### mmdc install method
- **D-01:** `mmdc`'s install method is **research-driven, with a soft leaning toward Homebrew** — the user's own words: "Research it, maybe I prefer brew, research it and consider stability, and security, simplicity, maintainability." This is not a hard lock-in to brew: if research finds pnpm-with-mitigation or a Phase-4-cleared Volta redirect is clearly better on those four criteria (stability, security, simplicity, maintainability), that wins instead. Reuse Phase 4's volta-internals research finding (does `volta install` shell out to npm, losing pnpm's gated-postinstall security) rather than re-deriving it — Phase 5 depends on that finding per ROADMAP's "Depends on" line.
- **D-02:** Decision criteria for mmdc, in the user's own priority framing: stability, security, simplicity, maintainability — weigh all four, not just the postinstall-script-security-vs-global-install-bug tradeoff the original PRD framed narrowly.

### puppeteer/chrome-headless-shell cross-platform handling
- **D-03:** One `puppeteer` catalog entry with platform-conditional methods (macOS vs Linux/Bazzite), mirroring how other registry entries already branch on platform — not two separate entries, not a single method assumed to work identically on both. Research determines what each platform's real install path actually is; do not assume parity.

### Claude's Discretion
- Exact registry `kind`/method shape for whichever install path research selects for mmdc (script/brew/uv-tool/etc.) — planner's call once research lands.
- Whether `chrome-headless-shell` needs its own separate registry entry from `puppeteer` or is bundled as one of puppeteer's install artifacts — a research question, not a locked decision.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-codegraph-github-release, REQ-mmdc-install-decision, REQ-puppeteer-catalog-entries full text
- `.planning/ROADMAP.md` Phase 5 section — goal, "Depends on: Phase 4's Volta-viability research", 3 numbered success criteria, the 2026-09-04 note about REQ-pnpm-global-reinstall-mitigation moving to Phase 4
- `.planning/phases/04-package-manager-redirect-policy/04-CONTEXT.md` — D-07's Volta-internals research question (does `volta install` shell out to npm?); Phase 5's mmdc decision must reuse whatever Phase 4's plan/research actually finds here, not re-ask the same question

### Existing pattern to mirror
- `installer/registry.toml` — existing platform-conditional entries (grep for `if_platform`/OS-gated methods, whatever the actual mechanism is called) as the template for D-03's single-entry-multi-platform shape
- `installer/model.py`/`installer/executors.py` — the `kind="github_release"` executor shape codegraph needs to move to (verify against whatever entry already uses this kind, e.g. `rtk` per REQ-rtk-github-release's own text, if that phase has landed by the time this one is worked — otherwise the general github_release executor pattern in `installer/executors.py`)

</canonical_refs>

<specifics>
## Specific Ideas

- Mid-discussion, the user asked whether this phase covers codegraph's postinstall (MCP registration) or adds graphify. Clarified and confirmed as OUT of Phase 5's scope: codegraph's postinstall/MCP-registration is `REQ-codegraph-mcp-postinstall` (Phase 9, "Postinstall Hooks Mechanism" — the mechanism is generic, proven via codegraph as the concrete case); graphify is `REQ-uv-tool-executor`/`REQ-agent-host-entries` (Phase 8, "AI Tier Catalog Expansion & uv-tool Executor", package `graphifyy` — double-y, differs from the CLI command name). Phase 5 is strictly a method correction on entries that already exist or are already scoped by SC#3 (puppeteer/chrome-headless-shell) — no new tools, no new mechanisms.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 5 scope; the postinstall/graphify questions were clarifications of an existing boundary, not new ideas to defer.

</deferred>

---

*Phase: 5-registry-method-corrections-codegraph-mmdc-puppeteer*
*Context gathered: 2026-09-04*
