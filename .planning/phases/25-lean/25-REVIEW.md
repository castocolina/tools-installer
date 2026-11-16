---
phase: 25-lean
reviewed: 2026-11-15T00:00:00Z
depth: deep
range: d0d88257..ecb19a58
files_reviewed: 22
files_reviewed_list:
  - installer/compose.py
  - setup.py
  - installer/wizard_app.py
  - installer/doctor_screen.py
  - installer/doctor_messages.py
  - installer/uninstall_screen.py
  - installer/uninstall_review.py
  - installer/policies_screen.py
  - installer/schedules_screen.py
  - installer/modals.py
  - installer/mutation_lock.py
  - installer/app_messages.py
  - installer/execute_screen.py
  - installer/engine.py
  - installer/update.py
  - installer/ownership.py
  - installer/install_ownership.py
  - installer/model.py
  - installer/post_install.py
  - tests/test_reachability.py
  - tests/compose_patch.py
  - tests/test_shellrc.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 25: Code Review Report

**Reviewed:** 2026-11-15
**Depth:** deep
**Files Reviewed:** 22 (production moves, deletions and the guards; tests read where they pin behaviour)
**Status:** issues_found

## Summary

Behaviour preservation of the move is sound. I checked it mechanically:

- Every top-level class, function and constant of the pre-phase `wizard_app.py` was compared by AST (docstrings dropped) against its new home. The only differences are the planned ones:
  - `_BodyStatic` became `Static`.
  - Underscore renames to public names.
  - `UninstallScreen` methods became module functions in `uninstall_review.py`. I diffed their bodies; they are identical.
  - Messages, `DEFAULT_CSS`, `BINDINGS` and ids are byte-identical, so Textual handler names and CSS selectors are unchanged.
- Old `setup.py` against `compose.py` plus the new `setup.py`:
  - Every route function (`_run_doctor`, `_run_fix`, `_run_uninstall`, `_teardown_cli`, `_run_schedule`, `main`) is AST-identical.
  - The only edits to composition code are the `_REGISTRY` and `checkout` path adjustments for the new file depth, which are correct, and the `Unpack[_InstallOptions]` typing.
- No monkeypatch target silently patches nothing. `patch_composition` raises when neither module binds a name. The direct `setup.*` patches that remain target names only `setup` reads, or are global module-object patches.
- `ruff check --select F` is clean. `test_reachability`, `test_setup` and `test_execute_screen` pass (`-n 0 --no-cov`).
- The run-log bound is correct against Textual 8.2.7:
  - `_start_line` counts trimmed strips.
  - Deferred writes replay through the overridden `write`.
  - A new screen is built per run, so the stale `_reported_dropped` after `clear()` never occurs.
- The host_setup and sensitive-action deletions leave no production reference. Old receipts were never written for the kind (it was receiptless), and the pins cover the rest.

Two guards are weaker than their names claim, and the phase quietly lost direct coverage of a live security-relevant classifier.

## Warnings

### WR-01: A dead module that carries a `__main__` guard is never reported by the reachability guard

**File:** `tests/test_reachability.py:132-134, 305-315` (`_entry_points`, `_entry_modules`, `test_makefile_and_install_sh_name_only_discovered_entry_points`)

**Issue:**
- Every `installer/` module with a top-level `if __name__ == "__main__"` is treated as an entry point, so it is reachable by definition.
- The Makefile test only asserts `named <= discovered`. It never asserts `discovered <= named`.
- Failure scenario: someone adds `installer/old_tool.py` with a `main()` and a main guard, and nothing imports it. LEAN-01's guard stays green. vulture at confidence 80 is silent and at 60 is already noisy.
- Verified with the repo's own helper against a scratch tree (`setup.py` imports `installer.a`; `installer/dead.py` has a main guard):

```
unreachable: []
```

- Only `catalog_audit` and `verify_registry` are real script entries today. Both are named in the Makefile.

**Fix:** Make the Makefile and `install.sh` the sole source of extra entry points, and fail on an undeclared guard.

```python
def test_every_main_guard_module_is_a_declared_entry_point() -> None:
    guarded = {n for n, p in _installer_modules(_ROOT).items() if _has_main_guard(p)}
    assert guarded == _python_m_modules(_ROOT)
```

Then drop the "has a main guard" auto-discovery from `_entry_points`, or keep it but only after this assertion.

### WR-02: Plan 25-04 deleted the only direct tests of the live source-line classifier, and the full suite no longer kills a mutant of it

**File:** `tests/test_shellrc.py` (deleted around old lines 1582-1664, 2768-2776, 2835-2843, 3229-3244; the assertions removed from `test_sources_file_is_broader_than_the_rewriter` and `test_sources_file_answers_no_for_every_none_shape`); production code at `installer/shellrc.py:588-617` (`_single_quoted_literal`, `_resolves_to`)

**Issue:**
- `classify_source_line` was a one-line test-only wrapper around the live `_inspect_source_line`, and it was correctly deleted as having no caller.
- Its ~17 tests were deleted with it, but they were the verdict-level tests of live production logic. That logic decides whether consolidation comments out a line, refuses, or ignores it.
- The deleted cases included:
  - the `rewritable` forms (`. ~/.myshellrc`, `${HOME}`);
  - the 17 `ambiguous` shapes;
  - the `none` over-detection mirrors (`time make build`, `echo hi > /tmp/x`);
  - the aliased-home real-path case;
  - the single-quote case `. '$HOME/.myshellrc'` → `none`. That one guards against commenting out a working command that sources a different file (a content mutation).
- Two live tests lost their classifier assertions (`verdict in {"rewritable","ambiguous"}` and `verdict == "none"`). A third (`test_a_simple_line_sourcing_myshellrc_...`) lost its "no live source remains" assertion.
- Verified by mutation in a scratch copy of HEAD (not the repo). `_resolves_to` was changed to skip `_single_quoted_literal`, so `'$HOME/.myshellrc'` now resolves to the target:

```
_resolves_to("'$HOME/.myshellrc'", target) -> (True, True)   # was (True, False)
```

- The full suite (`pytest tests -n 6`) passes with the mutant. Before the phase, `test_a_single_quoted_argument_is_not_expanded` killed it.
- The planned rule ("a consumer that is only a test counts as no production caller; its tests go with it") fits the wrapper. It does not fit tests whose subject is the still-live function the wrapper delegated to.

**Fix:** Re-home the verdict tests onto the production surface, with the same cases and assertions:

```python
from installer.shellrc import _classify_source_lines  # pyright: ignore[reportPrivateUsage]

def _verdict(line: str, target: Path) -> str:
    return _classify_source_lines(line + "\n", target)[0].verdict
```

At minimum, restore `test_a_single_quoted_argument_is_not_expanded` and the aliased-real-path test as `consolidate_shellrc` / `sources_file` behaviour tests: the line must be left untouched and `sources_file == "no"`.

### WR-03: `RunLog.dropped` depends on a private Textual attribute with no upper version pin

**File:** `installer/execute_screen.py:338-341`; `pyproject.toml:9` (`"textual>=8"`)

**Issue:**
- `dropped` returns `RichLog._start_line`, which is not public API.
- `write()` reads `self.dropped` after every log write. If a future Textual renames or removes the attribute, every `write_log` call raises `AttributeError` inside an `on_install_log_line` or `on_install_run_finished` handler. That kills the Execute screen mid-run.
- The existing tests would catch it in CI, but a user who runs `uv run` against an unpinned newer Textual would hit it first.

**Fix:** Count trimmed strips locally, so Textual internals are not read:

```python
before = len(self.lines)
super().write(...)
trimmed = before + added - len(self.lines)   # compute `added` from the strips appended
```

Alternatively, pin `textual>=8,<9` and add a test that asserts `hasattr(RichLog, "_start_line")` with a message naming this class.

## Info

### IN-01: Stale comment after the move

**File:** `installer/uninstall_screen.py:128-129`

**Issue:** The comment says "UnifiedApp is defined later in this module". It now lives in `installer/wizard_app.py` and is imported under `TYPE_CHECKING` at line 96.

**Fix:** "UnifiedApp is imported under TYPE_CHECKING from installer.wizard_app; the string annotation is resolved by pyright."

### IN-02: Names and fixtures for retired concepts remain

**File:** `installer/session.py:71, 203, 279`; `installer/app.py:67, 128`; `installer/execute_screen.py:56, 295`; `tests/test_session.py:1321, 1358, 1370`; `tests/test_update.py:1539`

**Issue:**
- The `SensitiveInstall` Protocol is the live install seam, yet it is named for the machinery 25-03 deleted. Its docstring was rewritten to hide this. It has about 40 test references, and the 25-03 summary records the choice as deliberate to avoid churn.
- Three session tests still build `Method(kind="host", params={"host_setup": True})`. That is a kind the loader rejects, so only the unused-kind code path "works" with it.
- `test_update_refuses_host_setup_pnpm_cleanly` is named for a retired kind.

**Fix:** Rename `SensitiveInstall` to `InstallSeam` in one mechanical commit. Replace the `host` sample with `Method(kind="node", ...)`. Rename the update test to `..._pnpm_owner_without_a_method_...`.

### IN-03: New `compose.py` still carries review IDs that the split-module guard does not scan

**File:** `installer/compose.py:124, 134, 168, 197, 276, 332, 363-365, 388, 399, 631, 673` (e.g. `WR-05`, `CR-04`, `R3-03`)

**Issue:**
- `compose.py` is a new 937-line module outside `_SPLIT_MODULES`, so `test_split_modules_carry_no_review_ids` never looks at it.
- `R3-03` at line 399 was added in this phase.
- SPEC R3 scopes the cleanup to the split modules, so this is not a violation. But the intent ("review-history comments are dropped") is only half-applied to the code the phase created.

**Fix:** Add `installer/compose.py` to the review-id scan (not the 800-line cap) and reword the dozen comments.

### IN-04: `compose.__all__` lists private names purely to quiet pyright

**File:** `installer/compose.py:91-108`

**Issue:** The names are not a public surface. `setup.py` and tests import underscore names, and `_invalidating` is in the list although it is only used inside `compose`. This is the opposite of the phase's "no suppression" rule: it is a suppression by another route. It also invites `from installer.compose import *`.

**Fix:** Drop `__all__` and rename the names `setup.py` imports back to public names. That is a one-time rename, and `patch_composition` already isolates the tests from the old names.

---

_Reviewed: 2026-11-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
