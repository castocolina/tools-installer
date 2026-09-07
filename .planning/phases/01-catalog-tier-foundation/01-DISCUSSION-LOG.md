# Phase 1: Catalog Tier Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-04
**Phase:** 1-catalog-tier-foundation
**Areas discussed:** Tier/Audience relationship, Tier validation strictness, Classification rule, Backfill scope, Category-default table, User-note override list

---

## Tier/Audience relationship

The user's initial free-text answer ("Creo que ya humano/ai no es necesario sino simplemente cada uno en su view como system/AI/dev-tools") suggested collapsing `audience`'s human/ai split into `tier` itself.

| Option | Description | Selected |
|--------|-------------|----------|
| Keep both axes | tier=system/user/ai stays orthogonal to audience=ai/both/human, unchanged | ✓ |
| Rename tier's "user" to "dev-tools" | Same structure, just renamed views | |
| Drop Audience, tier becomes the only axis | Loses `audience=both` (e.g. ripgrep is useful to both humans and agents) | |

**User's choice:** Keep both axes (recommended)
**Notes:** Grounded in the fact that `Audience` already drives an existing grouping view in `catalog_tui.py`, and `both` has no lossless equivalent in a 3-value tier.

---

## Tier validation strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Missing tier is a hard error | Matches ROADMAP success criterion #1's literal wording; forces every entry to be tagged deliberately | ✓ |
| Missing tier defaults silently | Mirrors priority/audience's existing fallback pattern | |

**User's choice:** Missing tier is a hard error (recommended)
**Notes:** None.

---

## Classification rule for existing entries

| Option | Description | Selected |
|--------|-------------|----------|
| Per-Category default + manual overrides | Category is a much better tier proxy than audience | ✓ |
| Audience-based heuristic | audience=both is too common, override list would grow long | |
| Fully manual, tool-by-tool pass | Most accurate, most time-consuming | |

**User's choice:** Per-Category default + manual overrides (recommended)
**Notes:** None.

---

## Backfill scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full backfill now | Consistent with tier being hard-required | ✓ |
| Four tools now, placeholder for the rest | Contradicts the hard-error decision just made | |

**User's choice:** Full backfill now (recommended)
**Notes:** None.

---

## Category-default table (system-tier categories)

| Option | Description | Selected |
|--------|-------------|----------|
| pkg-mgr + shell + container + runtime | Matches bootstrap-layer intent | ✓ |
| pkg-mgr only | Narrower default, more manual overrides | |

**User's choice:** pkg-mgr + shell + container + runtime (recommended)
**Notes:** None.

---

## Category-default table (user-tier fallback / DEVELOPMENT handling)

| Option | Description | Selected |
|--------|-------------|----------|
| All remaining categories default to user | A handful of bootstrap exceptions get explicit overrides | (superseded — see below) |
| DEVELOPMENT gets its own case-by-case pass | More accurate, more manual work | |

**User's choice:** Free-text answer superseded both listed options — user directly named the actual override list instead of picking a policy.
**Notes:** "XCode CLI is system basic tool needed to install ruby then brew, for AI specific must be tools like codegraph, graphify, rg, bat and similars, RTK, for user thinks like VS Code, Desktop Apps, Sublime, iTerm, etc." This produced two concrete named-override rules captured in CONTEXT.md D-05: Xcode Command Line Tools → tier=system; agent-optimized CLI tools (rg/bat/fd/eza/sd, codegraph, graphify, rtk) → tier=ai regardless of Category; GUI desktop apps (VS Code, Sublime, iTerm) → tier=user under the plain category default.

---

## Claude's Discretion

- Exact code shape of the per-Category default lookup (dict vs. inline conditionals) in `load_tools`.
- Whether the cross-tier resolver proof (java→sdkman) becomes a new automated test or is verified by an existing one.

## Deferred Ideas

None — discussion stayed within Phase 1 scope.
