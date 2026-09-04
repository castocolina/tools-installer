# TUI Interaction Consistency — Design

Date: 2026-06-23
Status: Approved (brainstorming)

## Problem

The unified wizard hosts five views (Catalog, Doctor, Fix, Uninstall, Policies)
switched with number keys `1`–`5`. User testing surfaced five complaints, all
confirmed against the code:

1. **`1`–`5` intermittently "stop responding."** The digit keys are global
   priority bindings (`wizard_app.py:520-523`) and should always fire. There is
   one *intended* no-op (under the `ctrl+p` nav modal, via `_navigable()` at
   `wizard_app.py:582-593`). The *intermittent* failure is a separate, real bug:
   `show_view()` runs `pop_screen()` then `push_screen()` (`wizard_app.py:569-580`),
   which Textual applies asynchronously. Rapid view switches can interleave with
   an in-flight transition and break the "stack is at most one deep" invariant.

2. **No apply-mode communication.** Four apply semantics — staged-commit
   (Catalog), staged-then-live (Uninstall), live-on-toggle (Policies),
   preview-then-apply (Fix) — are shown with three *row-level* indicators
   (`[x]/[ ]` selection, `●/○` on-off, status text). Nothing names the
   per-screen semantics, so the user cannot tell instant/destructive actions
   from reversible/staged ones.

3. **No per-view explanation.** Only the breadcrumb `WayfindingHeader`
   (`ui_common.py:75-98`) is shown. No per-view purpose or controls hint.

4. **Footer reads as undifferentiated.** The `Footer` is structural in
   `AppScreen.compose()` (`ui_common.py:119`) and renders the union of global
   nav keys (`1`–`5`, `q`, `esc`, `ctrl+p`) plus each screen's own bindings,
   with no grouping. On read-only Doctor it looks identical to action views.

5. **Toggle key is inconsistent.** `space` stages in Catalog/Uninstall
   (`tool_browser.py:91-98`), `enter` toggles-and-applies in Policies
   (`wizard_app.py:398-400`), `a` applies in Fix (`wizard_app.py:101-103`).

The underlying mental model is sound — "staged" views (mark, then commit) vs a
"live" view (each toggle is its own commit). The defects are about **legibility
of mode**, not the model. This design makes the model visible and aligns the
keys, without flattening the genuinely different apply semantics.

(Direction validated by a research-backed UX review against Nielsen's
Consistency & Standards / Visibility of System Status / Recognition over Recall
heuristics, Jakob's Law, the NN/g confirmation-dialog guidance, and WCAG 1.4.1
Use of Color.)

## The four apply modes

Each view has exactly one mode. The mode is the new first-class concept:

| Mode        | Views     | Meaning                                                    |
|-------------|-----------|------------------------------------------------------------|
| `STAGED`    | Catalog   | Mark rows; nothing changes until `enter` commits.          |
| `STAGED` *  | Uninstall | Mark rows; `enter` commits — destructive, confirmed first. |
| `LIVE`      | Policies  | Each `space` toggle applies immediately; reversible.       |
| `APPLY`     | Fix       | Preview shown; `enter` applies the single action.          |
| `READ-ONLY` | Doctor    | Audit only; nothing changes the system.                    |

\* Uninstall is `STAGED` plus a `DESTRUCTIVE` qualifier (it already renders with
the red accent via `accent="red"`).

## Decisions

### D1 — Keys: partial unification (`space` = toggle, `enter` = proceed)

Two keys, two meanings, everywhere they apply:

| View      | `space`                      | `enter`                            |
|-----------|------------------------------|------------------------------------|
| Catalog   | mark row (staged)            | commit selection → install         |
| Uninstall | mark row (staged)            | commit → remove (confirm first)    |
| Policies  | **toggle highlighted (live)**| inert (no staged batch)            |
| Fix       | —                            | **apply** (replaces `a`)           |
| Doctor    | —                            | —                                  |

- **Policies**: rebind the live toggle `enter` → `space`. It stays live (staging
  it would create a "looks applied but isn't" gap). Moving it to `space` makes
  "act on this row" mean the same key as the browsers, and `space`=toggle is the
  cross-tool convention users import (Jakob's Law). The prior footgun concern is
  answered by the `LIVE` badge + reversibility, not key avoidance.
- **Fix**: rebind `a` → `enter`. `a` keeps working as a **hidden alias** for one
  release (`show=False`) for muscle memory; the shown hint says `enter`.
- The number of apply *models* stays at the honest three; the *keys* stop
  contradicting each other.

### D2 — Mode badge (the centerpiece)

A new `ModeBadge(Static)` yielded by `AppScreen.compose()` immediately after
`WayfindingHeader`, so — like the footer — no screen can ship without one. It is
redundantly encoded (bracketed text + glyph + color); the bracketed word is the
load-bearing signal, the glyph fill is the colorblind-safe cue (hollow ◇ =
staged/pending, filled ◆ = live/active), color is decoration only.

Literal per-view strings (the hint clause doubles as the per-view explanation,
resolving complaint #3):

```
Catalog    ◇ [STAGED]               space marks a tool · enter installs your selection
Policies   ◆ [LIVE]                 space toggles a policy and applies it now · reversible
Uninstall  ◇ [STAGED · DESTRUCTIVE] space marks · enter removes marked items (you'll confirm)
Fix        ▸ [APPLY]                enter wires the managed PATH into your shells
Doctor     ‹ [READ-ONLY]            audit report · nothing here changes your system
```

Each view supplies a small frozen config (`label`, `glyph`, `style`, `hint`).
The existing row indicators (`[x]/[ ]` selection, `●/○` on-off) are **kept as
is** — they encode a different axis (item state) from the badge (screen
semantics), so they correctly look different.

### D3 — Footer: two zones

Within one `Footer`, render view-action keys first (left), then a `│`
separator, then the global-nav cluster dimmed (right). The user learns one rule:
"the dim cluster is always-available navigation; everything left of the bar is
what this screen does."

```
Catalog:  space toggle   enter install   a all   i invert  │  1–5 views   ^p nav   esc back   q quit
Doctor:   (read-only)                                       │  1–5 views   ^p nav   esc back   q quit
```

Doctor leads with a literal `(read-only)` token so its empty action zone reads
as intentional. Global nav is never hidden per-view (always-present-and-quiet is
the recognition affordance); it is only made visually subordinate.

### D4 — Uninstall confirmation

Uninstall's `enter` commit deletes installed artifacts — destructive and not
one-keystroke-reversible. It alone gets a confirmation step (a
`ModalScreen[bool]` summarizing the artifact count) before removal in
`UninstallScreen.on_tool_browser_accepted`. Policies does **not** get a
confirmation — it is idempotent and one-keystroke-reversible, and
over-confirming trains click-through (NN/g).

### D5 — Navigation race fix

Reproduce, then fix, the async pop/push stack-invariant race behind complaint
#1. `show_view()` must be safe under rapid or re-entrant calls so the
`[catalog]` / `[catalog, <view>]` invariant always holds and `1`–`5` never wedge
the stack. The exact fix (guard against in-flight transitions / re-entrancy) is
chosen after a failing test reproduces the race — the root cause is not asserted
as proven until then.

## Components and seams

- **`ui_common.py`**
  - Add `ModeBadge(Static)` and a `ViewMode` frozen config dataclass
    (`label`, `glyph`, `style`, `hint`).
  - `AppScreen.__init__` takes a `mode: ViewMode`; `compose()` yields
    `ModeBadge(mode)` after `WayfindingHeader`.
  - Add a `Footer` subclass (or footer-composition helper) that renders the
    two-zone layout with the dimmed global-nav cluster.
- **`wizard_app.py`**
  - Per-view `ViewMode` configs passed to each screen.
  - `PoliciesScreen`: rebind `enter` → `space` for `toggle_policy`; update hint.
  - `FixScreen`: rebind `a` → `enter` for `apply`; keep `a` as `show=False` alias.
  - `UninstallScreen`: confirmation modal before live removal.
  - `show_view()` / `action_show()`: re-entrancy-safe navigation.
- **`tool_browser.py`**
  - Footer hint `description` text and binding order for `space`/`enter`/`a`/`i`
    to fit the two-zone footer.

## Testing

All `installer/` code stays at 100% coverage; `setup.py` remains the untested,
pyright-excluded IO boundary. New behavior is driven test-first:

- `ModeBadge` renders the exact per-view string (public seam, like
  `WayfindingHeader.render_markup`); `AppScreen` guarantees a badge on every
  screen.
- Policies toggles on `space` (not `enter`); Fix applies on `enter` (and on the
  legacy `a` alias).
- Footer composition: view-action zone vs dimmed global-nav zone; Doctor shows
  `(read-only)` and no action keys.
- Uninstall: `enter` opens the confirm modal; confirm removes, cancel does not.
- Navigation race: a test driving rapid `1`→`2`→`3` switches asserts the
  one-deep stack invariant and that digit nav stays responsive — this test must
  first **reproduce** the bug (red), then pass after the fix.

## Non-goals

- Do **not** stage Policies into deferred-commit (would create a "looks applied
  but isn't" gap; the live model is correct for idempotent reversible toggles).
- Do **not** merge the `[x]/[ ]` and `●/○` glyph systems — they encode different
  axes (selection vs item-state) and must stay distinct.
- No mouse-first affordances; discoverability stays on-screen and keyboard-only.
- No new views, no registry/catalog changes, no change to the install engine.
