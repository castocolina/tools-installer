# Phase 2: Tier-Scoped Catalog Views & Recommends - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-04
**Phase:** 2-tier-scoped-catalog-views-recommends
**Areas discussed:** Nav bar ordering, Recommends demo tools, Recommends prompt trigger & accept behavior

---

## Nav bar ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Tier views first: System/User/AI/Doctor/Uninstall/Policies | Matches the fresh-machine walkthrough framing | ✓ |
| Tier views appended: Doctor/Uninstall/Policies/System/User/AI | Preserves existing 2/3/4 muscle memory | |

**User's choice:** Tier views first (recommended)
**Notes:** Number keys are auto-derived from `VIEW_ORDER` position, so this is a data-only reordering, not a binding-logic change.

---

## Recommends demo tools

| Option | Description | Selected |
|--------|-------------|----------|
| Demo with existing tools now, real wiring in Phase 8 | No dangling references to not-yet-existing catalog entries | ✓ |
| Wire claude/opencode's real recommends now | Requires tolerating an unresolvable recommended id; duplicates Phase 8 scope | |

**User's choice:** Demo with existing tools now, real wiring in Phase 8 (recommended)
**Notes:** `codegraph`/`graphify`/`rtk` don't exist in `registry.toml` until Phase 8's `REQ-recommends-wiring-agent-hosts`.

---

## Recommends prompt trigger & accept behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Fires on space-mark; accept adds to the same STAGED batch | One mental model, matches existing Catalog interaction | ✓ |
| Fires after install completes; accept installs immediately | New second install-trigger path | |

**User's choice:** Fires on space-mark; accept adds to the same STAGED batch (recommended)
**Notes:** None.

---

## Claude's Discretion

- Which specific existing-tool pair best illustrates `recommends` for the Phase 2 demo.
- Exact widget/screen mechanics for the one-action recommends prompt.
- How the three tier-scoped `CatalogScreen` instances share code (constructor already accepts an arbitrary tool list).

## Deferred Ideas

- Wiring `claude`/`opencode`/`codex`/`cursor-agent`/`antigravity`'s actual `recommends` data — deferred to Phase 8 (`REQ-recommends-wiring-agent-hosts`), already on the roadmap.
