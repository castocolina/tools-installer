# TUI Interaction Consistency — Status Report

Date: 2026-06-23
Branch: `feat/tui-interaction-consistency` (base `7acc9aa`)
Plan: `docs/superpowers/plans/2026-06-23-tui-interaction-consistency.md`

## Honest summary

- You reported **5 problems**. All five now have fixes committed.
- **Update 2026-07-02:** the "1–5 stop responding" bug was **misdiagnosed by Task 6** and only
  truly fixed now (commit `2849ccc`). Task 6 (`af3290c`) treated it as a stack-invariant race and
  serialized navigation; systematic-debugging + an independent re-review reproduced the real cause:
  an **unhandled `NoMatches` exception** from a deferred `ToolBrowser._refresh_marks` callback that
  dereferenced the Uninstall view's `DataTable` after that screen was popped, wedging Textual's
  message loop. The stack invariant was never violated (0/40 depth/mismatch across random bursts).
  The real fix guards that lookup; a standing test drives nav actions unsettled (the way the driver
  does) — `pilot.press` can't expose the bug because it drains the callback between keys.
- Separately, the circled-digit nav keys (❶❷…) rendered too small; swapped for bracketed digits
  `[1]…[5]` (commit `77237e9`).
- **Update 2026-07-02 (second round):** you still saw wrong-view landings ("press 2 for Doctor,
  land elsewhere") and dead keys. Systematic debugging traced the **architectural root cause**:
  the view screens were pushed by value but never **installed**, so Textual's
  `App._replace_screen` **destroyed** a popped screen's whole widget tree. Re-pushing the same
  instance left `screen.focused` pointing at a detached widget; the priority binding chain
  (built by walking up from the focused widget) collapsed to `['Tabs']`, the App's `1–5`
  bindings stopped matching, and fast-burst keys were **silently dropped**. Fixed in `0e67f3e`
  by installing every view screen (pops now *suspend*; tree/focus/bindings survive). Stress:
  **0/200** unsettled random bursts misbehave (previously wrong landings + dead input). The
  earlier `NoMatches` crash was this same screen destruction seen from a deferred callback;
  that guard stays as defense in depth with its own regression test.
- **Caveat still standing:** all verification is **headless** (test pilot + gates + reviewer). A
  real-terminal smoke run (`make setup`) is still owed to eyeball the badges/footer/nav and confirm
  rapid 1–5 no longer wedges.

## Table A — Your reported issues → fix → how verified

| # | Issue you reported | Task | Fix | Commit | Test that proves it | Verified how | Status |
|---|--------------------|------|-----|--------|---------------------|--------------|--------|
| 1 | `1…5` stop responding / wedge in some views | Task 6 → real fix | **Real cause:** deferred `ToolBrowser._refresh_marks` raised `NoMatches` on the popped Uninstall table, wedging the message loop. Guard the lookup (`try/except NoMatches`). Task 6's async pop/push (kept, harmless) was a misdiagnosis, not the fix. | `2849ccc` (Task 6: `af3290c`) | `test_rapid_switch_away_from_uninstall_does_not_wedge` (drives nav unsettled) | reproduced 22/40 random + 5/5 on the reported pattern; independent re-review confirmed 20/20; fix green (594 pass, 100% cov) | ✅ fixed (headless) |
| 2 | Footer shows the same options in every view | Task 4 | Replaced Textual's auto `Footer` with a curated `FooterBar`: view actions left, `│`, dim global nav right; Doctor shows `(read-only)` | `1b0ef27` | `test_footer_bar_shows_actions_then_global_nav`, `test_footer_bar_doctor_reads_as_read_only`, `test_footer_actions_cover_every_view` | TDD + `make validate && make test` (589 pass, 100% cov) + reviewer APPROVED | ✅ done (headless only) |
| 3 | Toggle key differs (space vs enter vs a) | Tasks 1 & 2 | Policies: `enter`→`space` (stays live). Fix: `a`→`enter` (`a` kept as hidden alias). Catalog/Uninstall already `space`/`enter` | `385f091`, `f1f969b` | `test_policy_enter_does_not_toggle`, `test_fix_screen_apply_legacy_a_alias_still_works` + updated toggle tests | TDD + gates (583 pass, 100% cov) + reviewer APPROVED both | ✅ done (headless only) |
| 4 | Views don't explain what they do / the difference | Task 3 | Added a per-view **mode badge** under the breadcrumb; its hint line states purpose + controls | `3787e3d` (+ fix `41e7253`) | `test_mode_badge_renders_label_glyph_and_hint`, `test_view_modes_cover_every_view` | TDD + gates (586 pass, 100% cov) + reviewer APPROVED + re-review of fix | ✅ done (headless only) |
| 5 | No signal for manual-apply vs auto-apply (color/label) | Task 3 (signal) + Task 5 (confirm) | Mode badge names the semantics: `◇ [STAGED]` / `◆ [LIVE]` / `▸ [APPLY]` / `‹ [READ-ONLY]` (glyph fill + bracket text + color, colorblind-safe). Task 5 adds a confirm modal on the one destructive commit (uninstall) | `3787e3d`/`41e7253` (badge done); Task 5 — | badge tests above; uninstall-confirm tests (planned) | Badge: done & verified headless. Confirm modal: not done | ⚠️ **PARTIAL** (badge ✅, uninstall confirm ❌ pending) |

## Gap found 2026-06-26 — view numbers not shown on screen

You spotted a real hole none of the docs covered: the `1–5` keys navigate views, but **the screen
never shows which number maps to which view**. The breadcrumb renders
`tools-installer · Catalog  Doctor  Fix  Uninstall  Policies` (no numbers), and the footer only
says a generic `1–5 views`. So the mapping is recall-only — a discoverability hole tied to
complaints #1 (number keys) and #4 (views don't explain themselves).

Proposed **Task 7** — prefix each breadcrumb entry with its key (numbers from `VIEW_ORDER`):

```
tools-installer · 1 Catalog  2 Doctor  3 Fix  4 Uninstall  5 Policies
```

Scope: `WayfindingHeader.render_markup` in `installer/ui_common.py` + its test
(`test_wayfinding_header_highlights_active_view`). Active view stays accent-bold (number included).
Status: **PENDING — awaiting your go-ahead.**

## Table B — Task execution ledger

| Task | What it does | Commit(s) | Tests after | Reviewer verdict | Findings handled |
|------|--------------|-----------|-------------|------------------|------------------|
| 1 | Policies toggle `enter`→`space` | `385f091` | 582 pass, 100% | APPROVED (spec ✅ / quality ✅) | Implementer also fixed `test_policies_e2e.py` (brief was incomplete) |
| 2 | Fix apply `a`→`enter` (+ hidden alias) | `f1f969b` | 583 pass, 100% | APPROVED | 1 Minor (stale comment) → logged for final review |
| 3 | Mode badge (`ViewMode`/`VIEW_MODES`/`ModeBadge`) | `3787e3d` + fix `41e7253` | 586 pass, 100% | APPROVED, then 1 "Important" (dup test instantiation) fixed + re-reviewed APPROVED | `Final` annotation skipped (justified: not used elsewhere) |
| 4 | Two-zone `FooterBar` replaces `Footer` | `1b0ef27` | 589 pass, 100% | reviewer running when you stopped me | — |
| 5 | Uninstall confirmation modal | — | — | — | **PENDING** |
| 6 | Async navigation race fix (issue #1) | — | — | — | **PENDING** |

## The verification method (what each "✅" actually means)

Every committed task passed, in order:
1. **TDD** — a failing test written first, then the code to pass it.
2. **`make validate`** — ruff (lint+format), **pyright strict (no suppressions allowed)**, bandit, vulture, shellcheck.
3. **`make test`** — pytest with a **100%-coverage gate on `installer/`**.
4. **Independent reviewer subagent** — fresh context, reads the diff + the task brief, judges
   spec-compliance AND code-quality. Critical/Important findings get a fix pass + re-review.

What this method does **NOT** cover (the honest gaps):
- **No real terminal run.** Tests use Textual's headless pilot. Reviewers explicitly noted "cannot
  verify live terminal rendering / visual appearance." Glyph widths, colors, `height: 1` overflow,
  and whether the badge/footer actually look right are **unverified**.
- **Issue #1 is unfixed** — the symptom you most cared about.

## Note on the pyright "import could not be resolved" warnings

You may have seen many red `Import "textual.widgets" could not be resolved` diagnostics. Those come
from the **editor's** pyright, which can't see the `uv` virtualenv. The authoritative check is
`uv run pyright` via `make validate`, which ran **clean (0 errors)** on every commit. They are false
positives from the IDE, not real errors.

## What remains and realistic effort

- **Task 5** (uninstall confirmation modal) — ~1 implementer + 1 review cycle.
- **Task 6** (the `1–5` race fix) — ~1 implementer + 1 review cycle; this is the real bug.
- **Then: a manual smoke run** (`make setup`) in a real terminal to visually confirm badges, footer,
  toggles, and that `1–5` no longer wedge — this closes the headless-only gap above.

This is **two tasks plus a manual run**, not days of work — the four done tasks took one working
session. The slow part you felt was the up-front plan review (3 iterations), which is exactly what
caught the bug-in-waiting (`call_later`) and two broken-test traps **before** any code was written.

## Update 2026-09-03 — Task 6 and Task 7 both done; scope grew beyond the plan

Recovered a large uncommitted working tree from a prior session (conversation history was lost;
this status doc was stale). Reconstructed the state from `git diff`/`git status` and committed it
as `7d7b598` on this branch. What that commit actually contains, beyond what this doc's tables
above describe:

- **Task 6** (the real `1–5` race) — already landed earlier as `2849ccc`/`af3290c` (see Table A
  above); confirmed still green.
- **Task 7** (numbered/clickable nav bar) — implemented: `WayfindingHeader` now renders a key
  number per view and is clickable (`WayfindingTab` + `Navigate` message), not just the
  circled-glyph text originally scoped in the plan doc.
- **Beyond the original plan** (found already in progress, not separately re-planned):
  - `installer/enums.py` — new `StrEnum` closed sets (`Priority`, `Audience`, `Category`,
    `InstallStatus`, `UninstallState`, `Severity`) replacing bare string literals across
    `model.py`, `uninstall.py`, `catalog_tui.py`, `guidance.py`, `render.py`, `session.py`,
    `ui_common.py`, `wizard_app.py`.
  - Policies view: a `Requires` column + detail panel; enabling a policy is now gated on its
    required tools being installed (`policy.py: requires`/`missing_requires`).
  - Countdown shell tweak rewritten from a bash busy-loop to a managed Python helper
    (`installer/helper_assets/wait_time.py`, installed into the managed bin dir via
    `ManagedExecutable`) that parses durations, compound durations, and clock times.
- Fixed two `ruff` line-length violations in `tweaks.py` that were blocking `make validate`
  (pre-existing in the uncommitted diff, unrelated to any of the above).

**Task 5** (uninstall confirmation modal, `ConfirmUninstall`) is also already done — landed in the
already-pushed history as `f8f635e` ("feat: confirm the destructive uninstall commit"), before this
recovered session. So all of Tasks 1–7 are now complete.

**Also closed later in this same 2026-09-03 session:** the real-terminal smoke run (`uv run
setup.py` in `tmux`, navigation-only to avoid mutating the real machine — Doctor/Uninstall/Policies
apply live) confirms the nav bar, mode badges, footer, and platform-gated tweaks all render
correctly and rapid view-switching doesn't wedge. Also closed the `wait_time.py` coverage gap
(31% -> 100%) with a dedicated test module. **All prior gaps in this plan are now closed.**

Full state: `make validate && make test` both pass clean (679 tests, 99.87% coverage, 90% gate, 0
pyright errors). See `.claude/handoffs/2026-09-03-tui-consistency-recovery.md` for the cross-machine
resume handoff.
