# Phase 8: AI Tier Catalog Expansion & uv-tool Executor - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

A new `kind="uv-tool"` executor lands in `installer/executors.py` (mirroring
the existing `"node"` kind's shape: `uv tool install <pkg>` instead of
`pnpm add -g <pkg>`), and `graphify` gets a registry entry using it (PyPI
package `graphifyy` — double-y, differs from the CLI command name).
`antigravity`, `cursor-agent` (verified official install method, unresolved
as of this ingest) and `codegraph` (`kind="github_release"`, inherited
finding) join the ai-tier catalog. `rtk` joins via
`kind="github_release"` from `rtk-ai/rtk` (default branch `develop`,
checksum-verified against `checksums.txt`). Batch 1's `recommends`
mechanism gets wired with real data on the agent-host entries.

</domain>

<decisions>
## Implementation Decisions

### Recommends wiring scope
- **D-01:** Not a uniform `recommends = ["codegraph", "graphify", "rtk"]` blanket-applied to all five agent hosts. Per the user: research which of codegraph/graphify/rtk actually applies to which host CLI — "no all apply for every host agent cli." `antigravity` is excluded from this phase's recommends wiring for now ("You can deio [dejo/leave out] antigravity for now") — antigravity still gets its catalog entry (install method, D-02 below) but does NOT get a `recommends` list populated in this phase; that can be revisited later once antigravity's own tool ecosystem is better understood.
- **How to apply:** the remaining four hosts (`claude`, `opencode`, `codex`, `cursor-agent`) each get a `recommends` list, but the *members* of that list are a per-host research question, not a fixed constant — e.g. determine whether `rtk` (a git/token-cost tool) makes sense as a recommendation on every one of the four, or only some.

### Antigravity/cursor-agent install-method verification bar
- **D-02:** If research finds the only official install method for `antigravity` or `cursor-agent` is a vendor-provided curl|bash-style script (not brew, not a package manager), that is acceptable and should be used — do not hold out for a stronger alternative or omit the tool. This matches the project's existing convention of trusting a tool's own official install script (e.g. `oh-my-zsh`'s official script, Phase 7) over inventing a substitute. Confirm and record the live-verified current script/method rather than assuming.

### Claude's Discretion
- Exact `recommends` membership per host (`claude`/`opencode`/`codex`/`cursor-agent`) among `codegraph`/`graphify`/`rtk` — a research call at planning/implementation time per D-01, informed by what each tool actually does and whether it fits that host's typical workflow.
- Whether antigravity's install script needs any safety review beyond "official vendor source, non-interactive" — same bar as other `kind="script"` entries in this codebase, no special-casing needed per D-02.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-uv-tool-executor, REQ-agent-host-entries (including Open Question 2), REQ-rtk-github-release, REQ-recommends-wiring-agent-hosts full text
- `.planning/ROADMAP.md` Phase 8 section — goal, "Depends on: Phase 1 (tier field), Phase 2 (recommends mechanism)", 3+ numbered success criteria
- Batch 1's `REQ-recommends-soft-dependency` (Phase 2) — the mechanism this phase instantiates with concrete per-host data; do not re-derive or extend the mechanism itself here, only supply data

### Existing pattern to mirror
- `installer/executors.py`'s existing `kind="node"` executor — the direct template for the new `kind="uv-tool"` executor's shape
- Whatever entry already uses `kind="github_release"` (Phase 5's `codegraph`, if landed by the time this phase is worked, or the general executor pattern) — the template for `rtk`'s entry
- Phase 7's `oh-my-zsh` entry (once landed) — the template for trusting an official vendor curl|bash script per D-02

</canonical_refs>

<specifics>
## Specific Ideas

- User's exact framing (2026-09-04) on recommends scope: "You can deio antigravity for now, and we must research where the can apply, no all apply for every host agent cli" — read as: skip antigravity's recommends wiring this phase, and treat per-host recommends membership as a research question rather than a fixed list applied uniformly.

</specifics>

<deferred>
## Deferred Ideas

- Antigravity's own `recommends` wiring — deferred, not dropped; revisit once antigravity's typical companion-tool usage is better understood (not blocking Phase 8's other success criteria).

</deferred>

---

*Phase: 8-ai-tier-catalog-expansion-uv-tool-executor*
*Context gathered: 2026-09-04*
