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

_Reviewed: 2026-09-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
