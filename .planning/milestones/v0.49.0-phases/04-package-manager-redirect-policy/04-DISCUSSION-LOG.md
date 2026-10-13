# Phase 4: Package Manager Redirect Policy - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-04
**Phase:** 4-package-manager-redirect-policy (originally scoped as npm/npx-ban-extension-redirect-policy — renamed mid-discussion, see below)
**Areas discussed:** Shim architecture, npx redirect target, doctor/guard status reporting, Phase 4 scope (pip/pip3, Volta)

---

## Shim design

| Option | Description | Selected |
|--------|-------------|----------|
| New REDIRECTED mechanism, parallel to BANNED | npx gets its own dict + shim template that execs into pnpm dlx; BANNED stays a pure hard-block | ✓ |
| Generalize BANNED to support a redirect target per entry | One unified mechanism, more code reuse but complicates the simple hard-block case | |

**User's choice:** New REDIRECTED mechanism (recommended). The user's own free-text answer here ("¿Acaso todos los redirects son iguales?... cada uno merece atención particular") reinforced this — a parallel mechanism leaves room for per-tool differences rather than forcing a uniform shape.

---

## npx redirect target

| Option | Description | Selected |
|--------|-------------|----------|
| `pnpm dlx "$@"` | Explicit, always available wherever pnpm is | ✓ |
| `pnpx "$@"` | Shorter, but itself a pnpm-provided shortcut for dlx | |

**User's choice:** `pnpm dlx "$@"` (recommended).

---

## Doctor/guard status reporting

| Option | Description | Selected |
|--------|-------------|----------|
| Same boolean status, label text notes the difference | guard_status()'s shape stays a plain bool; doctor UI's label text says "redirected" vs "blocked" | ✓ |
| New status enum distinguishing redirected vs blocked | More expressive but ripples into doctor.py/render.py call sites assuming a plain bool | |

**User's choice:** Same boolean status (recommended).

---

## Phase 4 scope (raised by the user mid-discussion, not a pre-planned gray area)

The user's free-text answer to the shim-design question raised a bigger question: should npm/pip/pip3 also become redirects, with per-tool research into each one's common use cases, rather than assuming npx alone gets this treatment?

This was **not scope creep in the "new capability" sense** — pip/pip3's redirect question and the Volta global-install split were already recorded as open, unresolved notes in REQUIREMENTS.md against this exact `installer/guards.py` mechanism (raised 2026-09-04 at an earlier batch-2 merge gate). The user was asking to resolve open questions already attached to this phase's boundary, not invent new ones. Presented as an explicit scope decision:

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Phase 4 as npx-only | pip/pip3/npm-global questions become a separate later phase | |
| Expand Phase 4 to research redirect targets for all four | Bigger phase, resolves the open questions where they already live | ✓ |

**User's choice:** Expand Phase 4.

Follow-up decisions, once expansion was chosen:
- **pip/pip3 implementation timing:** "Implement now if research says safe" (recommended) — chosen over "research only, implement later."
- **Volta scope:** initially framed as a yes/no on including Volta research in Phase 4. The user's answer explained their motivation (Volta as a `pnpm -g` replacement without npm's security problems, fixing pnpm's real global-package-loss bug) without literally picking an option — interpreted as "yes, include it" given the strength of the rationale, then explicitly confirmed in the next question.
- **REQ-pnpm-global-reinstall-mitigation re-pointing:** presented as "pull it forward to Phase 4" vs. "keep it at Phase 5+, just research Volta here." The user asked for clarification first — whether the *other* redirects (npm/pip) were also originally tied to that Phase 5/after-Phase-12 sequencing. Clarified: no, only `REQ-pnpm-global-reinstall-mitigation` itself carried that placeholder sequencing; the npm-allowlist and pip/pip3 questions weren't phase-assigned at all yet. User then deferred to the assistant's recommendation ("cualquier cosa que recomiendes esta bien") — recommendation applied: re-point the requirement to Phase 4, since the Volta redirect resolves its root cause directly.

**Documentation updated as a result:** ROADMAP.md's Phase 4 section (goal, requirements list, 6 success criteria, renamed from "npm/npx Ban Extension & Redirect Policy" to "Package Manager Redirect Policy" for a cleaner phase-directory slug), Phase 5's and Phase 12's sections (removed/updated their `REQ-pnpm-global-reinstall-mitigation` cross-references), and REQUIREMENTS.md (expanded REQ-npm-npx-redirect-policy's text, added REQ-npm-global-volta-redirect, updated REQ-pnpm-global-reinstall-mitigation's status and the traceability table).

## Claude's Discretion

- Exact doctor UI label text for redirected vs. blocked tools.
- Whether the REDIRECTED mechanism's code lives in guards.py or a sibling module.
- Exact pip/pip3 argv-translation shape — left to the research this phase's plan must do.

## Deferred Ideas

- npm's own subcommand-allowlist decision (non-global) — explicitly out of this phase.
- Generalizing the "does a safe redirect exist" research question to future banned commands beyond this phase's four — a principle noted, not an action item here.
