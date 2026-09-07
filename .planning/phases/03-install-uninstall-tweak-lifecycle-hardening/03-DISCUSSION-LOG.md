# Phase 3: Install/Uninstall & Tweak Lifecycle Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-04
**Phase:** 3-install-uninstall-tweak-lifecycle-hardening
**Areas discussed:** Oh-My-Zsh plugin editing mechanism, Uninstall sweep scope, Oh-My-Zsh presence precondition

---

## Oh-My-Zsh plugin editing mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Regex-based array insert/remove | Targeted, simple, reversible; doesn't handle multi-line syntax | ✓ |
| Full multi-line-aware array editor | More robust, more code/tests | |

**User's choice:** Regex-based array insert/remove (recommended)
**Notes:** None.

---

## Uninstall sweep scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full uninstall also strips shellrc blocks for enabled tweaks | Reuses the existing disable path; avoids a dangling alias | ✓ |
| Only delete orphaned executable files | Matches literal REQ wording but leaves a broken reference | |

**User's choice:** Full uninstall also strips shellrc blocks for enabled tweaks (recommended)
**Notes:** Reinforced later by the user's free-text motivation (see below) — a full uninstall exists to support clean machine restores, so symmetric teardown is the right default.

---

## Oh-My-Zsh presence precondition

| Option | Description | Selected |
|--------|-------------|----------|
| Detect ~/.oh-my-zsh (or $ZSH) and gate the toggle on it | Mirrors existing `requires` pattern, extended to directory-existence | ✓ |
| No precondition check | Simpler, but silent no-op with no feedback | |

**User's choice:** Detect ~/.oh-my-zsh (or $ZSH) and gate the toggle on it (recommended)
**Notes:** None.

---

## Closing note (free-text)

When asked if any other gray areas remained, the user clarified the real motivation instead of raising a new decision: "Generally nobody uninstalls things like zsh or oh-my-zsh, I just want the tool to make life easier when I restore a whole machine completely, which I want to do soon." Captured in CONTEXT.md `<specifics>` — this is context, not a new gray area, and confirms the symmetric-teardown choice above rather than contradicting it.

## Claude's Discretion

- The exact `InstallStatus`-family value/label for "dependency failed."
- Whether the Oh-My-Zsh presence-check becomes a new `TweakBundle` field or a bundle-specific special case.

## Deferred Ideas

None — discussion stayed within Phase 3 scope.
