# Phase 9: Postinstall Hooks Mechanism - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

A catalog tool can declare a one-time, non-interactive `postinstall`
command/script that runs immediately after its own successful install
(not batched, not deferred). Idempotency is a live check, no new
state-tracking database. Proven end-to-end via `codegraph`: after
`codegraph` installs, its MCP-registration step runs for every
already-installed agent host (`claude`/`codex`/`opencode`/`cursor-agent`),
cleanly no-oping when none are installed.

</domain>

<decisions>
## Implementation Decisions

### Postinstall trigger scope — single-direction only
- **D-01:** Codegraph's MCP-registration postinstall is triggered ONLY from codegraph's own successful install — not re-triggered later when a new agent host (e.g. `opencode`) is installed afterward. If a user installs `codegraph` first and `opencode` later, `opencode` will NOT get auto-registered by that later install; the user would need to reinstall/re-run codegraph to pick it up. Chosen for simplicity and because it matches REQ-codegraph-mcp-postinstall's literal wording ("after codegraph installs..."). This is a real, accepted limitation, not an oversight — record it as a known gap rather than something to silently work around.

### Postinstall command must be host-presence-aware
- **D-02:** Codegraph's actual CLI takes per-host flags (per the user: "el instalador de codegraph es universal pero tiene opciones como `codegraph --claude --global --local`") — the postinstall step must build its invocation from exactly which hosts are present at that moment (e.g. `codegraph --claude --global` if only claude is installed), never unconditionally passing a flag for a host that isn't installed. This is the live-check REQ-postinstall-idempotency-live-check already requires, applied specifically to host-flag composition, not just "is the MCP entry already there."

### Claude's Discretion
- Exact codegraph CLI invocation and flag names (`--claude`/`--global`/`--local`/etc.) — Open Question 3 in REQUIREMENTS.md, deferred research at implementation time; must be confirmed live against codegraph's actual `--help` output, never assumed from this discussion's example flags.
- Exact registry field shape (`postinstall` inline string vs `postinstall_script` file reference) chosen per-tool — follows REQ-postinstall-field's own guidance (inline for short, file for multi-line), planner's call for codegraph specifically once the real invocation is known.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-postinstall-field, REQ-postinstall-execution-timing, REQ-postinstall-idempotency-live-check, REQ-postinstall-noninteractive-only, REQ-codegraph-mcp-postinstall (including Open Question 3) full text
- `.planning/ROADMAP.md` Phase 9 section — goal, "Depends on: Phase 8 (codegraph must exist in the registry)", 5 numbered success criteria

### Existing pattern to mirror
- `installer/tweaks.py`'s `ManagedExecutable`/`helper_assets/` precedent — the model for inline-vs-file postinstall script handling (REQ-postinstall-field explicitly cites this)
- This codebase's existing all-live-check convention: `status.is_installed`, `guard_status`, `has_managed_block` — the pattern D-02's host-presence check and REQ-postinstall-idempotency-live-check's "is the effect already present" check must follow
- Whatever `Runner` seam every other executor already uses for subprocess dispatch — postinstall must run through the same trusted seam, not a new one

</canonical_refs>

<specifics>
## Specific Ideas

- User's exact framing (2026-09-04) on codegraph's CLI shape: "El instalador de codegraph es universal pero tiene opciones como codegraph --claude --global --local asi que el postinstall script deberia ser aware of the cli installed, osea no le diremos configure el hook para opencode si no esta instalado" — confirms D-02's host-presence-aware flag composition.

</specifics>

<deferred>
## Deferred Ideas

- Re-triggering codegraph's registration when a new agent host is installed after the fact — explicitly declined for this phase (D-01); could be revisited in a later phase if the one-directional gap proves annoying in practice.

</deferred>

---

*Phase: 9-postinstall-hooks-mechanism*
*Context gathered: 2026-09-04*
