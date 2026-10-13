# Phase 10: Agent CLI Ergonomics - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Three permissive-mode/default convenience tweaks extend the existing
`TweakBundle`/`tweak_policy` mechanism (`installer/tweaks.py`), independent
of Phases 1-9: `codex-skip` (parallel to `claude-skip`), `opencode-auto`
(narrower, honestly labeled semantic), and a `cursor-agent`/`cursor`
default-model wrapper. All three are shell alias/function-based for
self-update durability, per REQ-agent-tweak-self-update-durability.

</domain>

<decisions>
## Implementation Decisions

### cursor-agent default model target
- **D-01:** The default model to inject is a high-effort "sol" family slug (`chatgpt-5.6-sol`/`gpt-5.6-sol` — exact current id confirmed live per Open Question 1), with `effort=high`. The user's initial ask was also `context=1m`, but REQUIREMENTS.md already records (from prior research) that cursor-agent's 1M context is confirmed reachable only via interactive Max Mode, not from a non-interactive/bare invocation. Per the user: re-verify this via research at implementation time; if 1M context is still confirmed unreachable non-interactively, use whatever the closest non-interactive context setting actually is for the high-effort sol slug — do not silently drop the context consideration, but do not block on unreachable 1M either.
- **How to apply:** planner/researcher must not assume the old finding is stale just because the user asked for 1M — treat it as "re-verify, don't override" per the user's own choice, and record whatever the live-verified outcome is (confirmed unreachable → closest match; found reachable now → note it as a new finding superseding the old one).

### Claude's Discretion
- Exact codex bypass-permissions flag name — Open Question 2, deferred live-verification research, not a locked decision here.
- Exact current cursor-agent model-listing command used to confirm the sol slug and its available context settings — implementation-time research, never typed from memory (per REQUIREMENTS.md's existing caution against this).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-codex-skip-tweak (Open Question 2), REQ-opencode-auto-tweak, REQ-cursor-agent-default-model-wrapper (Open Question 1, and the existing "confirmed interactive-Max-Mode-only, unreachable non-interactively" 1M-context finding), REQ-agent-tweak-self-update-durability full text
- `.planning/ROADMAP.md` Phase 10 section — goal, "Depends on: Nothing", 4 numbered success criteria

### Existing pattern to mirror
- `installer/tweaks.py`'s existing `claude-skip` tweak — the direct template for `codex-skip`
- `installer/tweaks.py`'s existing shell alias/function mechanism — required for all three tweaks per REQ-agent-tweak-self-update-durability; `cursor-agent`'s wrapper specifically needs a shell *function* (not a plain alias) to conditionally omit its `--model` injection when the user already passed one

</canonical_refs>

<specifics>
## Specific Ideas

- User's exact initial ask (2026-09-04): "chatgpt-5.6-sol[effort=high,context=1m], hacer research del modo correcto" — followed by explicit confirmation to re-verify the 1M-context claim via research rather than assume it's now possible, using the closest non-interactive match if 1M is confirmed still unreachable.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 10 scope.

</deferred>

---

*Phase: 10-agent-cli-ergonomics*
*Context gathered: 2026-09-04*
