---
phase: 02-tier-scoped-catalog-views-recommends
reviewed: 2026-09-05T00:00:00Z
depth: deep
files_reviewed: 18
files_reviewed_list:
  - installer/catalog_tui.py
  - installer/deps.py
  - installer/model.py
  - installer/registry.toml
  - installer/selection.py
  - installer/tool_browser.py
  - installer/ui_common.py
  - installer/wizard_app.py
  - setup.py
  - tests/test_catalog_tui.py
  - tests/test_deps.py
  - tests/test_model.py
  - tests/test_registry.py
  - tests/test_selection.py
  - tests/test_setup.py
  - tests/test_tool_browser.py
  - tests/test_ui_common.py
  - tests/test_wizard_app.py
findings:
  critical: 0
  warning: 5
  info: 11
  total: 16
status: issues_found
fixed:
  warning: 5
  info: 0
fix_pass: 2026-09-05
fix_scope: critical_warning
re_review:
  reviewed: 2026-09-05
  depth: deep
  verified_resolved: [WR-01, WR-02, WR-03, WR-04, WR-05]
  new_findings:
    critical: 0
    warning: 2
    info: 3
    total: 5
  status: issues_found
  fixed:
    warning: 2
    info: 0
  fix_pass: 2026-09-05
  fix_scope: critical_warning
  fix_iteration: 2
re_review_final:
  reviewed: 2026-09-05
  depth: deep
  iteration: 3
  verified_resolved: [RR-01, RR-02]
  new_findings:
    critical: 0
    warning: 1
    info: 1
    total: 2
  status: issues_found
  blocking: false
  recommendation: proceed_to_verification
---

# Phase 2: Code Review Report

**Reviewed:** 2026-09-05
**Depth:** deep (cross-file: import graph, call chains, message flow, shared-state aliasing)
**Files Reviewed:** 18 (9 source + 8 test + `.claude/architecture.md` read as contract, not reviewed as source)
**Status:** issues_found

## Summary

Scope: `437776a..HEAD` (6 feature commits across plans 02-01 and 02-02). Reviewed
the flat-Catalog → System/User/AI split, the shared `set[str]` staged batch, the
new `deps.missing_requires` preview, `Tool.recommends` + `selection.unstaged_recommends`,
and the `r`/`d` recommends prompt.

Gates verified independently on the reviewed tree: `make validate` (ruff check,
ruff format, pyright strict, bandit, vulture, shellcheck) passes with 0 findings;
`make test` passes with `installer/` at ~99–100% line coverage. That is not evidence
of correctness, so the findings below come from tracing behaviour, not from the gates.

**Security:** no injection, path-traversal, credential, deserialization, or command
surface is touched by this phase. The registry path is a fixed packaged constant
(`setup.py:45`), `recommends` never reaches a subprocess, and the accept action is
explicitly keypress-gated with no executor call (`installer/catalog_tui.py:311-325`).
The one input-validation gap found is WR-04.

**Shared-mutable-state audit (the highest-risk change in the phase):** the single
`set[str]` created at `installer/wizard_app.py:691` is aliased into three
`CatalogScreen`s and three `ToolBrowser`s. I traced every writer —
`ToolBrowser.action_toggle_selected` (`symmetric_difference_update`),
`action_select_all` (`|=`), `action_invert` (`^=`), and
`CatalogScreen.action_accept_recommends` (`update`). All four mutate in place and
none rebind, so the alias holds. `action_invert`'s rewrite from
`selectable - selected` to `selected ^= selectable` is behaviour-preserving for a
browser that owns its set, because `selected ⊆ selectable` is maintained
(`action_toggle_selected` refuses non-selectable rows at
`installer/tool_browser.py:229-230`, and `action_select_all` only adds selectable
ids). No bug found here.

I also probed three failure modes empirically with throwaway tests (since removed):
an empty tier view (`a`/`i`/`enter` all behave, no crash); a base-screen re-stamp
after a cross-tier accept (works — `on_screen_resume` fires on the base screen when
a pushed screen pops); and prompt lifetime across navigation (**broken** — WR-01/WR-02).

**ONESHOT-RULES Rule 7 — verified, holds.** The claim that Phase 2 adds no new
registry method `kind`, executor, or resolver rank is true against the actual diff:
`installer/model.py::METHOD_KINDS` is unchanged, `installer/executors.py` and
`installer/resolve.py` (`_RANK`) are not in the changed-file list at all, and
`installer/registry.toml`'s entire diff is +6 lines (4 comment lines, 2 `recommends`
lines) with no new `[[tool.method]]` kind. The one resolution-adjacent addition,
`deps.missing_requires`, did ship with six matching tests in the same commit
(`676c037`: `installer/deps.py` +36 / `tests/test_deps.py` +53), so it satisfies
Rule 7's spirit as well as its letter.

No BLOCKER-tier defect was found. Five WARNINGs follow, two of them proven with a
running probe; the strongest are the prompt-lifetime pair (WR-01/WR-02), which
contradict a contract this phase itself wrote into `.claude/architecture.md`.

## Fix pass (2026-09-05)

All five WARNINGs are resolved; the eleven INFO findings were out of scope for
this pass and remain open. `make validate` and `make test` both pass on the
fixed tree (738 tests, `installer/` at 99.81% line coverage), run in the
isolated review-fix worktree with its own `uv sync`'d `.venv`, then re-checked
after the branch fast-forwarded.

| ID | Resolution | Commit |
| --- | --- | --- |
| WR-01 | Fixed — prompt/notice/pending ids cleared on view exit | `8d660ed` |
| WR-02 | Fixed — accept re-filters and names only the delta | `8d660ed` |
| WR-03 | Fixed — alias deleted, tests call `refresh_marks` | `d8a8dfa` |
| WR-04 | Fixed — element types validated at load time | `756b5f0` |
| WR-05 | Fixed — duplicate test now proves its own name | `178894c` |

Each finding's resolution is recorded under its own heading below.

## Warnings

### WR-01: The recommends prompt and the requires notice survive view switches, contradicting the phase's own "transient, no per-session state" contract

**File:** `installer/catalog_tui.py:331-339` (`on_screen_resume`), `installer/catalog_tui.py:269-284`

**Issue:** `on_screen_resume` re-stamps the DataTable marks but never clears
`self.status`, `self.recommends_line`, or `self._pending_recommends`. Those three are
only ever reset inside `on_tool_browser_selection_changed`, i.e. on a *selection*
event. Navigating away and back is not a selection event, and neither is moving the
DataTable cursor (`on_data_table_row_highlighted` in `tool_browser.py:273` does not
touch them). The prompt therefore stays armed indefinitely.

`.claude/architecture.md:68-70` — written by this phase — states: *"The prompt is
transient and keeps no per-session state; it reappears on any fresh mark that still
has unstaged, uninstalled recommendations, and accepting is what stops it recurring."*
The implementation keeps exactly that state.

Proven with a throwaway probe against `_recommends_catalog()`:

```
AFTER MARK:   'agent pairs well with jq - press r to add them to your selection, d to dismiss.'
(navigate to User view, manually stage jq, navigate back to AI view)
AFTER RETURN: 'agent pairs well with jq - press r to add them to your selection, d to dismiss.'
```

A second probe shows the same for the 02-01 requires notice — after the user has
already staged `pnpm` by hand in the System view, returning to the AI view still shows
`'agent also needs pnpm - added automatically at install time; …'`, a statement that
is now false.

Consequence: `r` stays armed for a tool the user marked an arbitrary number of
navigations ago, while the cursor and the detail bar describe an unrelated row. A
stray `r` adds software to the install batch. There is no test covering prompt or
notice lifetime across a view switch — every existing test asserts within one
uninterrupted screen visit.

**Fix:**

```python
def on_screen_resume(self) -> None:
    # …existing re-stamp comment…
    self._browser.refresh_marks()
    # The prompt and the requires notice describe one selection moment; leaving
    # the view ends that moment (architecture.md: "transient, keeps no
    # per-session state"). Re-marking the tool re-raises both.
    self._pending_recommends = ()
    self.recommends_line.clear()
    self.status.clear()
```

Add a regression test that marks a tool, navigates away and back, and asserts
`recommends_text == ""` and `status_text == ""`.

**Resolution (fixed, `8d660ed`):** the three clears moved into one
`CatalogScreen._clear_transient` helper, called from both
`on_tool_browser_selection_changed` and a new `on_screen_suspend`. Clearing on
*suspend* rather than the suggested `on_screen_resume` was a deliberate
deviation: `Screen.ScreenSuspend` fires on both legs of `show_view` (the
`push_screen` and the `pop_screen`), so the screen is never left holding a
prompt while inactive, instead of holding it until the user happens to come
back. `action_dismiss_recommends` deliberately keeps its narrower clear — `d`
dismisses the prompt, and a requires notice for the same mark survives it.
Regression test: `test_leaving_the_view_clears_the_prompt_and_the_requires_notice`
asserts both lines are empty after navigating away and back, then presses `r`
to prove the pending ids are disarmed and not merely blanked. Verified to fail
against the pre-fix handler. `.claude/architecture.md`'s transient-prompt
paragraph now states the view-exit rule the code enforces.

### WR-02: The accept confirmation names ids that were already in the batch

**File:** `installer/catalog_tui.py:311-325`

**Issue:** `_pending_recommends` is captured at *offer* time by `_offer_recommends`
(`catalog_tui.py:298-309`) and is never re-filtered at *accept* time.
`action_accept_recommends` calls `self._staged.update(pending)` and then reports
`f"added {', '.join(pending)} to your selection."` using the stale tuple. Any id the
user staged by hand (or via another tier view) between offer and accept is reported
as "added" although it was already there.

Proven with the same probe: after manually staging `jq` in the User view and returning
to the AI view, pressing `r` produced `'added jq to your selection.'` while the batch
was unchanged (`{'agent', 'jq'}` before and after).

This is a user-facing false statement in a screen whose whole purpose is to make the
staged batch legible, and it is the reason `--yes` users have to trust the post-TUI
`render_audit` instead. It compounds WR-01: the two share the "captured at offer time,
never revalidated" root cause.

**Fix:** revalidate at accept time and report only the delta.

```python
def action_accept_recommends(self) -> None:
    added = tuple(rec for rec in self._pending_recommends if rec not in self._staged)
    self._pending_recommends = ()
    self.recommends_line.clear()
    if not added:
        return
    self._staged.update(added)
    self._browser.refresh_marks()
    self.status.set(f"added {', '.join(added)} to your selection.", "ok")
```

**Resolution (fixed, `8d660ed`):** applied as suggested — the accept re-filters
`_pending_recommends` against the live `_staged` set, adds and names only the
delta, and returns without a status claim when the delta is empty. Two
regression tests, each proving a different branch:
`test_accept_names_only_the_ids_it_actually_added` (one of two recommendations
staged by hand while the prompt was armed, so the status names only the other)
and `test_accept_claims_nothing_when_the_recommendation_is_already_staged`
(empty delta, so no confirmation at all). Both verified to fail against the
pre-fix accept.

### WR-03: A production alias in `ToolBrowser` exists only so two tests do not have to be renamed

**File:** `installer/tool_browser.py:222-223`

**Issue:**

```python
# Isolation tests getattr the former private name; keep it bound to the public method.
_refresh_marks = refresh_marks
```

This class attribute has **zero production callers** — `grep` finds only
`tests/test_tool_browser.py:336` and `:355`, both of which reach it via
`getattr(browser, "_refresh_marks")  # noqa: B009`. `02-01-SUMMARY.md` states the
motive plainly: *"Task 1 kept `_refresh_marks = refresh_marks` so existing isolation
tests that getattr the former private name stay green without editing them."*

`.claude/architecture.md` rule 5 forbids exactly this: *"A shared helper with zero
production callers is deleted or adopted at its duplicate sites — never kept 'for
later'. Only its own test keeping it covered is the tell."* Here the test *is* the tell.
It is also a latent trap: because the alias binds the function object at class-creation
time, a subclass overriding `refresh_marks` would still get the base implementation
through `_refresh_marks`, and the two names would silently diverge.

Note vulture does not catch this (min_confidence 80, and the reference is a string
literal inside `getattr`), so the gate passing is not evidence the alias is needed.

**Fix:** delete the alias; change the two test call sites to `browser.refresh_marks`,
which also removes two now-pointless `# noqa: B009` suppressions — a net reduction in
both production code and suppressions, exactly the direction `.claude/architecture.md`
asks for.

**Resolution (fixed, `d8a8dfa`):** applied as suggested. Both test sites call
`browser.refresh_marks()` directly and the two `# noqa: B009` suppressions are
gone; the stale `_refresh_marks` mentions left in comments and docstrings in
`tests/test_tool_browser.py` and `tests/test_wizard_app.py` were renamed to the
public name so no prose points at a name that no longer exists. `grep` finds no
remaining reference to the alias in `installer/`, `tests/`, or `setup.py`, and
the two isolation tests still pass unchanged in substance.

### WR-04: `recommends` element types are never validated — a half-validation that a `tuple[str, ...]` annotation then lies about

**File:** `installer/model.py:148-151`, `installer/model.py:164`

**Issue:** `load_tools` rejects `recommends = "rg"` (the string case) but then does a
bare `tuple(raw_recommends)` at line 164. `tomllib` returns `Any`, so
`recommends = [1, 2]` or `recommends = [["rg"]]` loads without complaint and is stored
behind the declared `recommends: tuple[str, ...]` (`model.py:70`). pyright cannot see
through the `Any`, so strict mode passes on an annotation that is not enforced.

Every other registry field in this loader validates its shape at load time —
`category`, `tier`, `priority`, `audience` via `_parse_enum`; `method.kind` against
`METHOD_KINDS`; `npm_pkg` and `candidate` with explicit `isinstance(..., str)` checks.
`recommends` (and the pre-existing `requires`) are the outliers.

Downstream, a non-string element reaches `', '.join(tool.recommends)` at
`catalog_tui.py:233`, which raises `TypeError` inside
`ToolBrowser.on_data_table_row_highlighted` — i.e. on cursor movement, in the message
loop. A string element containing Rich markup (`"[/]"`) reaches
`Text.from_markup(self.detail_text)` at `tool_browser.py:282` and raises `MarkupError`
the same way. The failure is a crash on an unrelated keypress rather than a clear
`ValueError` naming the offending tool.

Mitigating: the registry is a packaged constant (`setup.py:45`), not user input, and
`tests/test_registry.py::test_shipped_registry_recommends_all_resolve` would fail CI
on a non-string or markup-bearing id because it would not match a catalog id. So this
is a robustness/consistency gap, not an exploitable one.

**Fix:** validate elements where the string case is already checked, and do the same
for `requires` in the same edit:

```python
for field_name in ("requires", "recommends"):
    raw = row.get(field_name, [])
    if isinstance(raw, str) or not all(isinstance(item, str) for item in raw):
        # tuple("rg") would silently become ('r','g'); a list of ids is required.
        raise ValueError(f"tool '{row['id']}': '{field_name}' must be a list of tool ids")
```

**Resolution (fixed, `756b5f0`):** both fields now go through one
`model._parse_id_list(raw, field, context)` helper, shaped like the existing
`_parse_enum` so the two validators read alike. It rejects a non-list (which
covers the old bare-string case, with the same error text, so the two existing
string-form tests are untouched) and then every non-string element, raising the
same `ValueError` the loader already uses. The `Any` from `tomllib` is typed at
the boundary with an explicit `cast(list[object], raw)` rather than a
`# type: ignore`, so pyright strict checks the loop. Two regression tests:
`test_load_tools_rejects_a_non_string_recommends_element` (`recommends = [1, 2]`)
and `test_load_tools_rejects_a_non_string_requires_element`
(`requires = [["pnpm"]]`), both verified to fail against the pre-fix loader.

### WR-05: A new test is a byte-identical copy of the test above it and asserts nothing new

**File:** `tests/test_deps.py:159-163` and `tests/test_deps.py:176-180`

**Issue:**

```python
def test_missing_requires_names_unstaged_uninstalled_dependencies() -> None:
    pnpm = _tool("pnpm"); mmdc = _tool("mmdc", "pnpm"); empty: set[str] = set()
    assert missing_requires(mmdc, [mmdc, pnpm], staged=empty, installed={}) == ("pnpm",)

def test_missing_requires_tolerates_a_partial_installed_map() -> None:
    pnpm = _tool("pnpm"); mmdc = _tool("mmdc", "pnpm"); empty: set[str] = set()
    assert missing_requires(mmdc, [mmdc, pnpm], staged=empty, installed={}) == ("pnpm",)
```

Same fixtures, same call, same expectation. The second test's name claims coverage of
a behaviour ("tolerates a partial installed map", i.e. the `installed.get(dep_id, False)`
default at `deps.py:181`) that the first test already incidentally covers with the
identical input — so the phase's coverage table reads as two independent proofs where
there is one. `.claude/testing.md`: *"Coverage is a floor, not a goal: don't write
assertion-free tests just to touch lines."* A duplicate is the same failure mode.

**Fix:** make the second test actually distinguish a partial map from an empty one,
or delete it.

```python
def test_missing_requires_tolerates_a_partial_installed_map() -> None:
    """`installed` may omit ids entirely; a missing key means "not installed"."""
    pnpm = _tool("pnpm")
    node = _tool("node")
    mmdc = _tool("mmdc", "pnpm", "node")
    empty: set[str] = set()
    # pnpm present-and-True, node absent from the map entirely.
    assert missing_requires(
        mmdc, [mmdc, pnpm, node], staged=empty, installed={"pnpm": True}
    ) == ("node",)
```

**Resolution (fixed, `178894c`):** applied as suggested (the cited line numbers
still matched the tree). `test_missing_requires_tolerates_a_partial_installed_map`
now passes `installed={"pnpm": True}` against a tool requiring both `pnpm` and
`node`, so it distinguishes a present-and-True entry from a key absent from the
map entirely — the `installed.get(dep_id, False)` default its name claims. The
result is bound to a local before the assert to keep `ruff format` from wrapping
the call into an unreadable shape. The first test
(`test_missing_requires_names_unstaged_uninstalled_dependencies`) is unchanged.

## Info

### IN-01: `BASE_VIEW` ↔ `Tier` coupling is enforced only by a comment and a test

**File:** `installer/wizard_app.py:691-707`, `installer/ui_common.py:101-103, 171`
**Issue:** `_catalogs` is keyed by `tier.value`, then `catalog`, `get_default_screen`,
and `_navigable` all index it with `BASE_VIEW = VIEW_ORDER[0]`. If anyone reorders
`VIEWS` so a non-tier view lands first — the exact "one-row change" that
`.claude/architecture.md` rule 1 advertises as safe — the app raises `KeyError` at
startup. The invariant currently lives in a comment (`ui_common.py:102-103`) and in
`tests/test_ui_common.py::test_tier_views_lead_the_nav_and_match_the_tier_enum`.
**Fix:** derive rather than assume, e.g. `self._base_catalog = self._catalogs.get(BASE_VIEW)`
with an explicit module-level assertion in `ui_common.py` that `VIEW_ORDER[0]` is a
`Tier` value, so the failure is a named error at import time rather than a `KeyError`
in `get_default_screen`.

### IN-02: `ToolBrowser.Accepted.ids` is computed and silently discarded on the catalog path

**File:** `installer/catalog_tui.py:341-348`, `installer/tool_browser.py:261-270`
**Issue:** `action_accept` posts `Accepted(self.selected_ids())`, but `selected_ids()`
filters against `self._adapter.items` — the *tier-scoped* list — so for a tier catalog
it returns only that tier's staged ids. `CatalogScreen.on_tool_browser_accepted`
correctly ignores `event.ids` and rebuilds from `self._staged`, but nothing at the
`ToolBrowser` end documents that its payload is now wrong for this consumer. The
UninstallScreen (`wizard_app.py:368-377`) still uses `event.ids` legitimately.
**Fix:** document on `Accepted` that `ids` is browser-scoped and a host sharing a
selection set across browsers must use its own batch; or have `CatalogScreen` assert
the discrepancy is intentional in a one-line comment at the ignore site.

### IN-03: `CatalogScreen.selected` no longer means "what this screen selected"

**File:** `installer/catalog_tui.py:247-249`, `installer/tool_browser.py:116`
**Issue:** The property returns the live shared `_staged` set, so
`app.catalog_for("user").selected` includes System- and AI-tier ids. The docstring at
`catalog_tui.py:142-144` still calls it "state the tests assert on" without noting the
widened meaning, and `tests/test_catalog_tui.py::test_select_all_is_scoped_to_the_active_tier_view`
asserting `app.catalog.selected == {"pnpm", "jq"}` from the *User* view reads as a bug
on first pass. It also hands callers a mutable alias of the app's batch.
**Fix:** rename to `staged` (or add a `staged` property and keep `selected` tier-scoped),
and state the sharing in the docstring.

### IN-04: The `r`/`d` bindings are absent from the view registry's footer actions

**File:** `installer/catalog_tui.py:155-158`, `installer/ui_common.py:112, 122, 132`
**Issue:** `.claude/architecture.md` rule 1: *"Every per-view fact — … footer actions —
lives in the single `VIEWS` table."* The three tier views' `actions` strings still read
`"space toggle | enter install | a all | i invert"`; `r`/`d` are declared with
`show=False` on the screen and advertised only by the transient prompt text. A user who
misses the prompt has no way to learn the keys.
**Fix:** either add the keys to the three `actions` strings, or note in the `View`
docstring that transient, context-gated bindings are deliberately excluded.

### IN-05: Three `View` rows differ only in `name`/`label`/`palette`

**File:** `installer/ui_common.py:104-133`
**Issue:** `mode`, `glyph`, `style`, `hint`, and `actions` are copy-pasted verbatim
across the System/User/AI rows. A change to the shared hint or action zone now has to
be made in three places, which is the duplication the "one view registry" rule exists
to prevent.
**Fix:** build the three tier rows from a small comprehension over `Tier` with a
per-tier `(label, palette)` map, keeping the shared fields in one literal.

### IN-06: `GLOBAL_NAV` and the digit bindings silently break past nine views

**File:** `installer/ui_common.py:186`, `installer/wizard_app.py:670-671`, `installer/ui_common.py:180`
**Issue:** `f"1-{len(VIEWS)} views"` renders `1-12 views` at 12 views, and
`Binding(str(i + 1), …)` produces the key name `"10"`, which Textual will not match to
any keypress. The phase raised the count from 4 to 6 without noting the ceiling.
**Fix:** cap the advertised range at 9 (`min(len(VIEWS), 9)`) and only emit digit
bindings for the first nine views, or raise at import when `len(VIEWS) > 9`.

### IN-07: The unknown-`item_id` defensive branch is unreachable in tests

**File:** `installer/catalog_tui.py:277-279`
**Issue:** The coverage report flags `catalog_tui.py:279` as the only missed line in
the module. `self._by_id` is built from the full catalog and `event.item_id` always
originates from a tier subset of it, so `tool is None` is currently dead. It is
reasonable defence, but an untested dead branch will silently rot.
**Fix:** cover it by posting a synthetic `SelectionChanged("ghost", True)` to the
screen, or drop the branch and let the `KeyError` surface if the invariant ever breaks.

### IN-08: A test module imports a constant from another test module

**File:** `tests/test_catalog_tui.py:17`
**Issue:** `from tests.test_registry import REGISTRY` couples the catalog TUI tests to
`test_registry`'s import side effects and collection order.
**Fix:** move `REGISTRY` to `tests/conftest.py` (as a fixture or module constant) and
import it from there in both modules.

### IN-09: No in-TUI indicator of the total staged count across the three views

**File:** `installer/ui_common.py:104-133`, `installer/catalog_tui.py:196-198`
**Issue:** Splitting one visible list into three means the staged batch is no longer
fully visible from any single screen. A user who pressed `a` in the System view, then
navigated to AI and pressed `enter`, gets no in-TUI signal of how much is queued. The
post-TUI `render_audit` + `prompter.confirm` in `installer/app.py:126-131` covers this
for the normal path, but `--yes` skips the confirm (`app.py:131`), leaving only the
printed audit.
**Fix:** put an `N staged` token in the mode badge or status line, derived from
`len(self._staged)`.

### IN-10: Two different `VIEWS` constants are now load-bearing for the same screen

**File:** `installer/catalog_tui.py:93` vs `installer/ui_common.py:101`
**Issue:** `catalog_tui.VIEWS` is `tuple[str, ...]` of grouping tabs; `ui_common.VIEWS`
is `tuple[View, ...]` of nav views. `catalog_tui.py` imports four names from `ui_common`
(`AppScreen`, `StatusLine`, `mark`) but not `VIEWS`, so there is no runtime clash — but
`CatalogScreen` now has a `view` constructor kwarg meaning a *nav* view and a `view`
property meaning a *grouping* view (`catalog_tui.py:166` vs `:243-245`), which is a
genuine reader trap introduced by this phase.
**Fix:** rename the module-local constant to `GROUPING_VIEWS` and the property to
`grouping` (or the kwarg to `nav_view`).

### IN-11: The recommends block is duplicated verbatim across both agent hosts

**File:** `installer/registry.toml:1190-1192`, `installer/registry.toml:1211-1213`
**Issue:** The same two-line Phase-2/Phase-8 comment and the identical
`recommends = ["rg", "fd", "jq"]` appear twice. `tests/test_registry.py::test_agent_hosts_recommend_existing_catalog_tools`
deliberately avoids asserting equality so Phase 8 can diverge them — which is the right
call — but the duplicated *comment* will need editing in two places when Phase 8 lands.
**Fix:** keep the data duplicated (TOML has no other option and per-host divergence is
coming), but collapse the explanatory comment to one occurrence with a pointer, or move
it to a file-header note.

---

# Re-review (2026-09-05, deep)

**Scope:** `cc76510..0b5b29c` — the four fix commits (`8d660ed`, `d8a8dfa`,
`756b5f0`, `178894c`) plus the docs commit `0b5b29c`. Verified against live
source and a running app, not against the fix commits' own claims.

**Verdict: 0 Critical / 2 Warning / 3 Info.** All five original WARNINGs are
genuinely resolved. The fix pass introduced two new WARNINGs, both of them
collateral rather than logic defects, and neither blocks verification.

> **Fix pass 2 (2026-09-05):** both new WARNINGs are now fixed — see
> [Fix pass 2](#fix-pass-2-2026-09-05) below. The three INFO findings
> (RI-01, RI-02, RI-03) were out of scope for that pass and remain open.

**Gates re-run on the exact committed tree** (not taken on trust from the fix
pass): `make validate` — ruff check, `ruff format --check` (83 files), pyright
strict `0 errors, 0 warnings`, bandit, vulture, shellcheck — all clean.
`make test` — 738 passed, `installer/` at 99% line coverage (3 missed
statements total: `catalog_tui.py:277`, which is the known IN-07 defensive
branch, and `model.py:34`, which predates this phase — see RI-03).

## Verification of the five fixed WARNINGs

### WR-01 — RESOLVED (verified independently, not by re-running the fix's own test)

The fix clears on `ScreenSuspend` instead of the originally suggested
`ScreenResume`. I traced the real Textual 8.2.7 event flow rather than accepting
the claim:

- `App.push_screen` (`textual/app.py:2942-2946`): `if screen_stack and
  screen_stack[-1].is_active: mode_screen.post_message(events.ScreenSuspend())`.
- `App.pop_screen` (`textual/app.py:3109-3121`) schedules `_replace_screen(previous_screen)`,
  and `_replace_screen` (`textual/app.py:2852-2870`) posts `ScreenSuspend()` to the
  popped screen before the install check that would otherwise remove it.

`UnifiedApp.show_view` (`installer/wizard_app.py:754-764`) is `pop_screen` then
`push_screen`, both awaited. Every leg therefore delivers a `ScreenSuspend` to
the screen that stops being on top:

| transition | who gets ScreenSuspend |
| --- | --- |
| base → non-base | base (push path) |
| non-base X → non-base Y | X (pop path), then base (push path) |
| non-base X → base | X (pop path) |

Messages land on the target screen's own FIFO queue, so a later `SelectionChanged`
for a fresh mark can never be processed ahead of a pending Suspend. The handler
name is correct for the event class (`ScreenSuspend` → `on_screen_suspend`), and
not calling `super()` is right: Textual dispatches the framework's `_on_*` and the
user's `on_*` independently.

Confirmed empirically with a throwaway probe (since deleted) that does **not**
reuse the fix's own test — mark `jq` on the User view, hop AI → System → User,
then press a stray `r`:

```
PROBE marked status='jq also needs pnpm - added automatically at install time; …'
PROBE marked rec   ='jq pairs well with rg - press r to add them to your selection, d to dismiss.'
PROBE returned status=''
PROBE returned rec   =''
PROBE staged after stray r={'jq'}
```

Both lines cleared and the pending ids genuinely disarmed. The deviation from the
suggested fix is the better call: clearing on the way out means the screen is
never left holding an armed prompt while inactive.

### WR-02 — RESOLVED

`action_accept_recommends` (`installer/catalog_tui.py:330-337`) now recomputes
`added` against the live `_staged` set. I checked the aliasing the filter depends
on: `ToolBrowser.__init__` (`installer/tool_browser.py:116`) stores the passed set
by reference (`self.selected = set() if selected is None else selected`) and every
writer mutates in place, so `screen.selected`, `screen._staged` and the app's
`self._staged` are one object — the delta filter reads live truth. Probe:

```
PROBE accept status='added jq to your selection.' staged={'jq', 'agent'}
```

and the empty-delta branch returns without a status claim. No false "added" text
remains.

### WR-03 — RESOLVED, with new collateral (see RR-01)

`_refresh_marks` is gone from `installer/tool_browser.py`; `grep -rn "_refresh_marks"`
over `installer/`, `tests/` and `setup.py` returns nothing (only stale
`.planning/graphs/*.json` index entries and historical plan prose). Both isolation
tests call `browser.refresh_marks()` directly and the two `# noqa: B009`
suppressions are gone. The rename, however, was applied as a blind textual
replace — see RR-01.

### WR-04 — RESOLVED

`installer/model.py:44-64` adds `_parse_id_list(raw, field, context)`, called for
both `requires` and `recommends` at `model.py:165-167`. It rejects a non-list
(subsuming the old bare-string case with identical error text, so the two existing
string-form tests still pass) and then every non-string element. The `Any` from
`tomllib` is typed at the boundary with `cast(list[object], raw)` — no
`# type: ignore` — and pyright strict reports **0 errors** on the live tree, so the
declared `tuple[str, ...]` is now enforced rather than promised. Cross-checked that
this closes the whole boundary: `grep -rn "Tool(" installer/*.py` finds exactly one
production construction site, `model.py:171`, inside `load_tools`. Both new
negative tests exist and are collected.

### WR-05 — RESOLVED

`tests/test_deps.py:176-185` now calls
`missing_requires(mmdc, [mmdc, pnpm, node], staged=empty, installed={"pnpm": True})`
against a tool requiring both ids and asserts `== ("node",)`. That distinguishes a
present-and-`True` entry from a key absent from the map — the
`installed.get(dep_id, False)` default the test name claims — and is no longer a
copy of the test above it.

## New findings

### RR-01 (WARNING): the WR-03 rename mangled three test function names

**File:** `tests/test_tool_browser.py:296`, `:324`, `:339`

**Issue:** `d8a8dfa` replaced the string `_refresh_marks` with `refresh_marks`
everywhere, including inside the test function names themselves:

```
- async def test_refresh_marks_leaves_non_selectable_cell_untouched() -> None:
+ async def testrefresh_marks_leaves_non_selectable_cell_untouched() -> None:
```

All three `test_refresh_marks_*` names lost the underscore. `grep -rnE "^(async )?def test[^_]" tests/`
returns exactly these three and nothing else, confirming they are collateral from
this commit and not a pre-existing convention.

They still run today — pytest's default `python_functions = ["test"]` is a prefix
match and the project does not override it in `pyproject.toml:46-49`, and I
confirmed collection:

```
tests/test_tool_browser.py::testrefresh_marks_leaves_non_selectable_cell_untouched
tests/test_tool_browser.py::testrefresh_marks_tolerates_a_cleared_table
tests/test_tool_browser.py::testrefresh_marks_tolerates_a_removed_table
```

That is why no gate caught it: ruff has no test-naming rule, and the suite count
is unchanged. The risk is latent rather than present — the moment anyone tightens
`python_functions` to `test_*` (a common hardening), three regression tests
silently disappear, and two of them guard a crash that actually shipped
(`"this crashed the real Uninstall view on make setup"`, `test_tool_browser.py:325-328`;
the `NoMatches`-on-popped-screen case at `:339`). Losing them without a failing
run is exactly the failure mode `.claude/testing.md` forbids.

**Fix:** restore the underscore in the three `def` lines (comments and docstrings
inside them are already correct):

```python
async def test_refresh_marks_leaves_non_selectable_cell_untouched() -> None: ...
async def test_refresh_marks_tolerates_a_cleared_table() -> None: ...
async def test_refresh_marks_tolerates_a_removed_table() -> None: ...
```

**Resolution (fixed, `e8f9aee`):** applied as suggested — the three `def`
lines got their underscore back and nothing else in the file changed, since
`refresh_marks` is still exactly what all three assert on and the comments and
docstrings inside them already read correctly. `grep -rnE "^(async )?def
test[^_]" tests/` now returns nothing, so the mangling is gone rather than
merely reduced, and the suite count is unchanged at the pre-fix 738 (the names
were being collected before and still are — this closes the latent risk, not a
present gap). No production code was touched.

### RR-02 (WARNING): clearing on `ScreenSuspend` also fires for a modal push, so opening and cancelling the nav palette silently wipes the prompt and the accept-guard warning

**File:** `installer/catalog_tui.py:345-352`, `installer/wizard_app.py:791-794`,
`.claude/architecture.md:71-73`

**Issue:** `ScreenSuspend` is not "the user left the view" — it is "this screen is
no longer the top of the stack". `UnifiedApp.action_open_nav` pushes `NavScreen`
onto the current catalog screen, which fires `ScreenSuspend` on it
(`textual/app.py:2942-2946`). Cancelling the palette with `escape` calls
`_navigate(None)`, which does nothing, so the user ends up on the same view with
the same cursor on the same row — but `_clear_transient` has already run.

Proven with a probe (since deleted); `ctrl+p` then `escape`, never leaving the AI
view:

```
PROBE nav-palette: view='ai'
PROBE before='agent pairs well with jq - press r to add them to your selection, d to dismiss.'
PROBE after =''
PROBE staged after stray r={'agent'}
```

The same probe shows the collateral I consider the worse half — the accept guard's
own message is wiped by an unrelated cancelled palette open:

```
PROBE warn before='Select at least one tool, or press q to quit.'
PROBE warn after =''
```

That warning is set by `on_tool_browser_accepted` (`catalog_tui.py:368`) precisely
to tell a user who pressed `enter` with an empty batch what to do next. Pre-fix it
survived a palette open/cancel, because `on_screen_resume` never touched
`status`; post-fix it does not. This is a behaviour regression introduced by the
fix pass, and no test covers either case.

It also makes `.claude/architecture.md:71-73` — rewritten by the same commit —
inaccurate: *"leaving the view clears both and disarms the pending ids"* under-describes
what the code does, and rule 2's "one navigation path" framing makes the palette
look like a non-event when it is not one.

**Fix:** gate the clear on an actual view change rather than on stack position, so
a cancelled palette is inert. `show_view` is already the single navigation path
(`.claude/architecture.md` rule 2), so it is the right seam:

```python
# installer/wizard_app.py
async def show_view(self, name: str) -> None:
    if name == self.current_view:
        return
    leaving = self._catalogs.get(self.current_view)
    if leaving is not None:
        leaving.clear_transient()          # rename _clear_transient -> public seam
    ...
```

If the broader `ScreenSuspend` semantics are wanted instead, keep the handler but
narrow it to the recommends prompt (`_pending_recommends` + `recommends_line`),
leave `status` alone, and correct the architecture paragraph to say "any time the
screen stops being on top", so the doc stops describing behaviour the code does
not have. Either way, add a test for `ctrl+p` → `escape`.

**Resolution (fixed, `4d285fc`):** took the first option — the trigger moved to
the real view-change seam rather than narrowing what the wrong trigger clears.
`on_screen_suspend` is deleted; `_clear_transient` is renamed to the public
`CatalogScreen.clear_transient` and is now called from
`UnifiedApp.show_view` (`installer/wizard_app.py:761-768`) on
`self._catalogs.get(self.current_view)`, after the `name == self.current_view`
early return so a no-op navigation stays a no-op. Because `show_view` is the
single navigation path (architecture rule 2), every real tier switch — number
key, wayfinding header, `escape`-to-base, palette selection, the initial-view
hop on mount — still clears, while a push that is not a view change (the nav
palette, and any future modal) is inert. The `.get` is deliberate: `show_view`
also moves to and from the doctor/uninstall/policies screens, which have no
transient state, so a non-catalog `current_view` simply has nothing to clear.
`action_dismiss_recommends` keeps its narrower clear, unchanged.

`.claude/architecture.md`'s transient-prompt paragraph now says "navigating to
another view", names `show_view` + `clear_transient` as the seam, and states
why a screen-suspend handler is the wrong one — so the doc describes the
behaviour the code has, including the palette case that motivated the change.

Two regression tests, each pinning one half of the reported damage:
`test_cancelling_the_nav_palette_keeps_the_prompt_and_the_requires_notice`
(ctrl+p → escape, then asserts both lines survive *and* that a following `r`
still stages `jq` — armed, not merely rendered) and
`test_cancelling_the_nav_palette_keeps_the_empty_selection_warning` (the
`enter`-with-empty-batch guard message survives the same round trip). Both were
verified to fail against the pre-fix `on_screen_suspend` handler — the first on
the blanked status line, the second on `assert 'Select at least one tool' in ''`.
The WR-01 test `test_leaving_the_view_clears_the_prompt_and_the_requires_notice`
is kept and still passes on the narrower trigger, confirming a genuine tier
switch clears as before; its inline fixture was extracted to
`_both_lines_catalog()` and shared with the new palette test rather than copied.

### RI-01 (INFO): the deliberate `d`-keeps-the-requires-notice asymmetry is asserted nowhere

**File:** `installer/catalog_tui.py:339-343`, `tests/test_catalog_tui.py:535-547`
**Issue:** `action_dismiss_recommends` carries a new comment stating it is
"narrower than `_clear_transient` on purpose … a requires notice for the same mark
is a separate fact that survives it". The only dismiss test is
`test_dismissing_the_prompt_leaves_the_selection_untouched`, and its fixture
`_recommends_catalog()` (`test_catalog_tui.py:526-532`) gives `agent` no
`requires` at all, so the asymmetry is unobservable there. A future edit that
swaps the narrow clear for `_clear_transient` would pass the whole suite.
**Fix:** extend the dismiss test (or add one) over a tool with both `requires` and
`recommends`, asserting `recommends_text == ""` and `status_text != ""` after `d`.

### RI-02 (INFO): `r` with an empty delta is a silent no-op

**File:** `installer/catalog_tui.py:333-334`
**Issue:** When every pending id was already staged, `action_accept_recommends`
clears the prompt line and returns with no message. The user cannot distinguish
"already in your batch" from "the prompt expired". This matches the fix the
original review suggested, so it is a deliberate choice rather than a slip, but it
is the one branch of the accept that gives no feedback.
**Fix:** set an informational status such as
`f"{', '.join(self._pending_recommends)} already staged."` before returning, or
note in the comment why silence is preferred.

### RI-03 (INFO): `_parse_id_list`'s twin, `_parse_enum`, still has an uncovered guard

**File:** `installer/model.py:33-34`
**Issue:** `model.py:34` is the only missed statement in the module. `_parse_id_list`
was explicitly "shaped like the existing `_parse_enum` so the two validators read
alike", and it ships with two negative tests; its model has none for the non-string
branch. Pre-existing — `git log -S "must be a string"` puts it in `581c097`, an
ancestor of this phase's base `437776a` — so it is out of Phase 2's scope, but the
twinning makes the gap newly visible.
**Fix:** one test writing `category = 1` in a manifest and asserting
`ValueError("'category' must be a string")`, or drop the guard and let
`_parse_enum`'s existing `enum_type(value)` raise.

## Fix pass 2 (2026-09-05)

Both new WARNINGs are resolved; the three INFO findings (RI-01, RI-02, RI-03)
were out of scope for this pass and remain open. Gates were run in an isolated
review-fix worktree with its own `uv sync`'d `.venv` — once on the RR-01-only
tree and again on the final tree, so each commit was validated as the tree it
introduces, not just the pair together.

| ID | Resolution | Commit |
| --- | --- | --- |
| RR-01 | Fixed — the three `test_refresh_marks_*` names got their underscore back | `e8f9aee` |
| RR-02 | Fixed — the transient clear moved from `ScreenSuspend` to `show_view` | `4d285fc` |

`make validate`: ruff check, `ruff format --check` (83 files), pyright strict
`0 errors, 0 warnings`, bandit, vulture, shellcheck — all clean.
`make test`: 740 passed (738 + the two new palette regressions), `installer/`
at 99.81% line coverage, the same 3 missed statements as the re-review found
(`catalog_tui.py` IN-07 defensive branch, `model.py:34` RI-03, `wizard_app.py:74`),
so no branch was newly uncovered.

Each finding's resolution is recorded under its own heading above.

**Follow-up for the next reviewer:** `CatalogScreen.clear_transient` is now
public and has exactly one out-of-class caller (`UnifiedApp.show_view`). That
is a deliberate cross-object seam, not an orphan helper under architecture
rule 5 — the rule targets helpers with *zero* production callers — but it does
mean the app now knows one thing about catalog-screen state, which is worth a
second opinion.

## Conclusion

The five WARNINGs are closed against live source and a running app, and no
Critical-tier defect exists in the phase. The two new WARNINGs are both narrow:
RR-01 is a three-line rename with no present behavioural effect, and RR-02 is a
UX regression on a cancelled-palette path that no user flow depends on for
correctness. Neither risks data loss, a wrong install batch, or a crash.

**The phase is clean enough to proceed to verification**, provided RR-01 and RR-02
are carried forward as follow-ups rather than dropped — RR-02 in particular
because the architecture doc currently describes behaviour the code does not have,
and that document is the contract later phases will read.

> **Post-fix note (fix pass 2):** rather than being carried forward, both were
> fixed in place — `e8f9aee` and `4d285fc`. The architecture doc no longer
> describes behaviour the code does not have: its transient-prompt paragraph and
> `UnifiedApp.show_view` were changed in the same commit.

---

_Reviewed: 2026-09-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep (Textual event-flow trace + running probes + independent gate re-run)_

---

# Iteration 3 (final re-review, 2026-09-05, deep)

**Scope:** `84daa42..HEAD` — the two fix-pass-2 commits (`e8f9aee`, `4d285fc`)
plus the review-bookkeeping commit `418a788`. The production surface of that
range is 36 changed lines across `installer/catalog_tui.py` (+12 / −16),
`installer/wizard_app.py` (+8 / −0) and `.claude/architecture.md` (+10 / −5),
with 62 added test lines. Verified against live on-disk source and a running
app; the fix commits' own messages and the fixer's resolution notes were treated
as claims to disprove, not as evidence.

**Verdict: 0 Critical / 1 Warning / 1 Info (new).** RR-01 and RR-02 are both
genuinely resolved. The `clear_transient` seam introduced by the RR-02 fix is
sound — no new correctness, safety or security defect. The one new WARNING is a
missing regression test, not a misbehaviour.

**Gates re-run on the exact committed tree:** `make validate` — ruff check,
`ruff format --check` (83 files), pyright strict `0 errors, 0 warnings`, bandit,
vulture, shellcheck — all clean. `make test` — **740 passed**, `installer/` at
**99.81%** line coverage, 3 missed statements (`catalog_tui.py:277` = IN-07,
`model.py:34` = RI-03, `wizard_app.py:74`) and one partial branch
(`wizard_app.py:789->exit`, the `_navigable()` false leg of
`on_wayfinding_header_navigate`, pre-existing and unrelated to this range). No
branch was newly uncovered by fix pass 2.

## Verification of RR-01 — RESOLVED

`grep -rnE "^(async )?def test[^_]" tests/` returns **nothing** (exit 1). The
three `def` lines in `tests/test_tool_browser.py` are back to
`test_refresh_marks_leaves_non_selectable_cell_untouched` (`:296`),
`test_refresh_marks_tolerates_a_cleared_table` (`:324`) and
`test_refresh_marks_tolerates_a_removed_table` (`:339`).

Checked beyond the reported symptom, because the root cause was a blind textual
replace and one grep only proves the shape it looks for:

- `git show e8f9aee` touches exactly three lines, all `def` lines, in one file —
  no production code and no other identifier changed.
- `grep -rn "testrefresh\|_refresh_marks" installer/ tests/ setup.py .claude/`
  finds no remaining concatenation and no surviving reference to the deleted
  private alias. The only `_refresh_marks` hits in the repo are two dated
  `docs/superpowers/` records of the historical bug, which are describing the
  past correctly and are outside this phase's changed-file set.
- Scanned the whole suite for name shadowing that a rename could have created:
  five duplicate test names exist repo-wide, and every pair is split across two
  different modules (`test_catalog_tui` ↔ `test_tool_browser`, `test_download` ↔
  `test_executors`), so none of them shadow. Pre-existing, not collateral.

## Verification of RR-02 — RESOLVED

**The handler is gone, not renamed.** `grep -rn "on_screen_suspend"` over
`installer/`, `tests/` and `setup.py` returns nothing. The only surviving
lifecycle handler on `CatalogScreen` is `on_screen_resume`
(`installer/catalog_tui.py:350`), which still does only the mark re-stamp it
always did.

**The trigger is at the view-change seam, correctly guarded.**
`UnifiedApp.show_view` (`installer/wizard_app.py:754-772`) reads:

```python
if name == self.current_view:
    return
leaving = self._catalogs.get(self.current_view)
if leaving is not None:
    leaving.clear_transient()
if self.current_view != BASE_VIEW:
    await self.pop_screen()
```

The early return precedes the clear, so a no-op navigation cannot wipe state;
the clear precedes the pop, so the leaving screen is still mounted when its
`StatusLine`s are cleared. `git show 4d285fc` confirms the early return is
pre-existing and the commit added exactly the eight lines above.

**`show_view` really is the only path.** `grep -rn
"push_screen\|pop_screen\|switch_screen" installer/` yields four hits: the two
inside `show_view`, `wizard_app.py:375` (the uninstall confirm modal, pushed
from `UninstallScreen`, which has no transient state) and `wizard_app.py:802`
(`NavScreen`, via the `push_screen(modal, callback)` form rule 2 mandates). So
no navigation escapes the clear, and no modal now triggers it.

**The regression tests were verified to fail against the pre-fix shape — not
taken on trust.** I re-attached the deleted handler in a throwaway module
(monkeypatching `CatalogScreen.on_screen_suspend = lambda self:
self.clear_transient()`, since deleted) and replayed both scenarios:

```
PROBE prefix status= ''
PROBE prefix rec   = ''
PROBE prefix staged after r= {'agent'}      <- r disarmed; test expects {'agent','jq'}
PROBE prefix warn after= ''                 <- test expects 'Select at least one tool'
```

Both new tests assert the exact opposite of every line above, so each genuinely
fails against the pre-fix code. They also assert the *armed* state, not merely
the rendered text (`press("r")` → `selected == {"agent", "jq"}`), which is the
right assertion for this bug class.

**Probed two paths the new tests do not cover, both hold:**

```
PROBE burst view= ai        (ctrl+p and escape sent as one unsettled burst)
PROBE burst status= 'agent also needs pnpm - added automatically at install time; …'
PROBE burst rec   = 'agent pairs well with jq - press r to add them …'

PROBE repress view= ai      (press 3 while already on the AI view)
PROBE repress status= 'agent also needs pnpm - …'
PROBE repress rec   = 'agent pairs well with jq - …'
```

The burst case matters because `pilot.press` with a `pause` between keys masks
the timing bugs this codebase has hit before; the transient lines survive
unsettled input too.

**The doc now matches the code.** `.claude/architecture.md:68-78` says
"navigating to another view clears both", names `UnifiedApp.show_view` and the
public `clear_transient` as the seam, and states why `ScreenSuspend` is the
wrong event. Read against the implementation, every clause is true.

## Assessment of the `clear_transient` cross-object seam

The fixer flagged this as deliberate-but-debatable and asked for a second
opinion. It is fine, and I could not construct a defect from it:

- **Not an orphan under rule 5.** Two production callers —
  `CatalogScreen.on_tool_browser_selection_changed` (`catalog_tui.py:272`) and
  `UnifiedApp.show_view` (`wizard_app.py:767`). Rule 5 targets helpers with
  *zero*.
- **No new coupling direction.** `UnifiedApp.__init__` already constructs every
  `CatalogScreen` and injects its `view`, `catalog` and shared `staged` set
  (`wizard_app.py:692-702`). The app already owns these objects; one more
  synchronous call on them adds no layer that did not exist.
- **No lifecycle hazard.** The call happens before the pop, so the widget tree
  is live. It also runs at mount time on the base screen when
  `initial_view != BASE_VIEW` (`wizard_app.py:736-737`); that path is exercised
  by a dozen existing tests (`initial_view="doctor" | "uninstall" | "policies"`),
  all green, so clearing a freshly-composed `StatusLine` is safe in practice as
  well as in theory.
- **No state can leak past it.** A screen's transient state is only ever written
  by its own key handlers (`on_tool_browser_selection_changed`,
  `action_accept_recommends`, `on_tool_browser_accepted`), which require it to be
  the active screen — so a screen can never acquire a prompt while inactive and
  arrive holding one.
- **Reversed direction checked too:** there is no way to leave a tier view
  without passing through `show_view`, per the `push_screen`/`pop_screen` grep
  above.

## New findings

### FR-01 (WARNING): the no-op-navigation guard the RR-02 fix depends on is asserted by no test

**File:** `installer/wizard_app.py:758-759`, `tests/test_catalog_tui.py:648-688`

**Issue:** The fix's correctness rests on two separate "this is not a view
change" paths, and only one of them is pinned by a test.

1. **Palette cancel** — `escape` on `NavScreen` → `_navigate(None)` → `show_view`
   is *never called*. Covered by
   `test_cancelling_the_nav_palette_keeps_the_prompt_and_the_requires_notice`.
2. **Navigating to the view you are already on** — pressing `3` while on the AI
   view, or picking the current view in the ctrl+p palette → `show_view` *is*
   called and the `name == self.current_view` early return is what saves the
   prompt. Covered by nothing.

Because path 2 goes through a different mechanism than path 1, the palette test
gives it no protection. I confirmed the behaviour is correct today (the
`PROBE repress` output above), and coverage shows both legs of the early-return
branch are executed by some test — but no test *asserts* the transient lines
survive it. Moving `leaving.clear_transient()` three lines up, above the early
return, reintroduces a variant of RR-02 (your own view's number key wipes your
prompt) with all 740 tests green. That is the same "no failing run to warn you"
failure mode `.claude/testing.md` forbids and the same shape as RR-01.

**Fix:** one test, alongside the two palette ones:

```python
async def test_renavigating_to_the_current_view_keeps_the_prompt() -> None:
    """`show_view` returns early when the view is unchanged, so re-pressing the
    active view's number key (or picking it in the palette) is not a view exit."""
    tools, installed = _both_lines_catalog()
    app = _unified_app(tools, installed, {})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        screen = app.catalog_for("ai")
        await pilot.press("3")  # already here: a no-op navigation
        await pilot.pause()
        assert "agent pairs well with jq" in screen.recommends_text
        await pilot.press("r")
        await pilot.pause()
        assert screen.selected == {"agent", "jq"}
```

**Blocking?** No. Present behaviour is correct and was verified empirically;
this is a durability gap in the test suite, not a defect in shipped behaviour.

### FR-02 (INFO): the clear is keyed on `_catalogs` membership, so a future screen with transient state is skipped silently

**File:** `installer/wizard_app.py:765-767`

**Issue:** `leaving = self._catalogs.get(self.current_view)` looks the leaving
screen up in the tier-catalog dict only. `self._views` also holds
`DoctorScreen`, `UninstallScreen` and `PoliciesScreen`, none of which have
transient state today — which is exactly why the `.get` is correct and is
documented as deliberate. The cost is that the rule encoded here is "clear tier
screens" rather than "clear whatever can be cleared", so the day a fourth screen
grows a transient line, `show_view` skips it with no error and no failing test.

**Fix (optional):** key on capability instead of on the dict, e.g. a tiny
`Transient` protocol or
`leaving = self.screen_for(self.current_view); getattr(leaving, "clear_transient", noop)()`;
or leave the code as is and note the invariant in the `View` registry docs so a
new screen's author meets it. Low urgency — there is no fourth candidate in the
roadmap.

## Carried-open findings (unchanged, not re-litigated)

Out of scope for both fix passes and still open: the eleven original INFOs
(IN-01 … IN-11) and the three re-review INFOs (RI-01 `d`-keeps-the-notice
asymmetry untested, RI-02 silent empty-delta accept, RI-03 `_parse_enum`'s
uncovered guard). RI-01 is the most valuable of them — it and FR-01 are the same
class of gap (a deliberate behavioural asymmetry with no test pinning it) and
would make a natural single follow-up commit.

## Final verdict

**0 Critical / 1 Warning / 1 Info.**

RR-01 and RR-02 are resolved against live source, with the RR-02 fix
independently proven to change behaviour by replaying the pre-fix handler rather
than by re-running the fixer's own tests. Fix pass 2 introduced **no** new
correctness, security, data-loss or crash risk; the `clear_transient` seam it
added is sound and consistent with the app's existing ownership of its screens.
The gates pass on the exact committed tree.

The one new WARNING (FR-01) is a missing regression test for behaviour that is
correct today and was verified by probe. It is not functional, not a safety
issue, and blocks nothing.

**Phase 2 is clean enough to close out — proceed to verification.** No further
fix iteration is warranted; FR-01 and FR-02 should be carried forward as
follow-up notes (FR-01 ideally bundled with RI-01, which is the same one-test
gap in a different place), not as blockers.

---

_Reviewed: 2026-09-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep (live-source trace + pre-fix-shape replay + unsettled-input probes + independent gate re-run)_
