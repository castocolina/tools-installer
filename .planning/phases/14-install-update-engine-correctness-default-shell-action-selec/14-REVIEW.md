---
phase: 14-install-update-engine-correctness-default-shell-action-selec
reviewed: 2026-09-14T18:18:39Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - installer/app.py
  - installer/engine.py
  - installer/execute_screen.py
  - installer/post_install.py
  - installer/registry.toml
  - installer/render.py
  - installer/session.py
  - setup.py
  - tests/test_app.py
  - tests/test_deps.py
  - tests/test_docs.py
  - tests/test_engine.py
  - tests/test_execute_screen.py
  - tests/test_post_install.py
  - tests/test_registry.py
  - tests/test_render.py
  - tests/test_session.py
  - tests/test_setup.py
  - tests/test_wizard_app.py
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: "clean — WR-01/WR-02/WR-03 fixed in 67b9d66 (corroborated by independent cross-AI review, 14-REVIEW-cross-ai.md); IN-01 left as documented, consistent pre-existing asymmetry"
---

## Disposition (post-review fix pass)

WR-01, WR-02, and WR-03 were independently corroborated by a parallel cross-AI
review pass (`14-REVIEW-cross-ai.md`) and fixed in commit `67b9d66`:

- WR-01: the missing-ownership `refresh.refresh([tool])` call is now wrapped
  in `run_live`; a failure is recorded as an update error rather than
  escaping the worker unhandled. A regression test
  (`test_refresh_failure_on_missing_ownership_reports_error_not_a_clean_run`)
  covers the case neither review found tested.
- WR-02: `self.update_skips` (the worker-thread attribute bypassing
  `post_message`) was deleted; the one test that read it now asserts against
  the rendered log, matching the message-based pattern every other assertion
  in this file already uses.
- WR-03: a still-None ownership after refresh now records a skip instead of
  a silent `continue`.

IN-01 (explicit "no" leaves no log line) was left as-is — it mirrors existing,
accepted asymmetry with `_ask_mismatch` and both reviewers treated it as
informational only, not a defect.

`make validate && make test` re-run clean after the fix (2073 passed, 1
skipped, 95.34% coverage).

# Phase 14: Code Review Report

**Reviewed:** 2026-09-14T18:18:39Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 14 fixes both reported bugs on the production path. D-01/D-02 (the
select+enter update dispatch) is correctly wired: `ExecuteScreen._to_update`
is computed from the same eligibility predicate `action_update_tool` already
uses, `_ordered` and `_to_update` are structurally disjoint (the resolver
still excludes installed tools, so there is no double-processing), and the
mutation-grade gate is enforced where it actually matters —
`UpdateService.run` re-resolves ownership fresh and refuses low-confidence
owners regardless of which call site reached it, so the batch path's absence
of `action_update_tool`'s own pre-check is not a security gap. D-04/D-05 (the
`set_login_shell` guard) is also correct and conservatively ordered:
`installer/post_install.py::_set_login_shell` checks `platform.immutable`
unconditionally *before* ever consulting the confirmation callback, on both
the console (`run_wizard`) and in-app (`SensitiveActionScreen`) call sites,
and a registry `default_enabled_sensitive_actions` declaration cannot bypass
it (the action never reads that field) — confirmed by
`test_immutable_host_cannot_bypass_login_shell_guard_via_default_enabled`.
The two post-install dispatch tables (`POST_INSTALL_HOOKS` /
`POSTINSTALL_HOOK_NAMES`) are proven disjoint and oh-my-zsh is the sole
declarer. Test coverage across both fixes is genuinely thorough, including
negative cases (already-installed, manual-required, raising confirm
callback, escape/dismiss, unattended `--yes`).

The defects found concentrate in `ExecuteScreen._run_updates`, the one method
this phase added that talks to shared, blocking, I/O-touching services
(`VersionRefreshService`, `UpdateService`) directly from the worker thread
without going through this same file's own `run_live` convention every
sibling call already uses. WR-01 is a recurrence — via a newly-added, concrete
code path — of the exact failure class Phase 13's review flagged as WR-01
("an out-of-contract worker exception is reported to the user as a
successful, empty run"); it is not covered by any test because the test
double's `refresh()` never raises. WR-02 is a thread-safety/dead-code
finding: a worker-thread attribute mutation that bypasses the file's own
`post_message` hand-off doctrine and has no production reader. Neither
blocks shipping the two fixes described in 14-CONTEXT.md, but both should be
addressed before the next round of update-service work builds on top of this
method.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: `_run_updates`'s missing-ownership refresh call is unprotected, unlike its sibling three lines away

**File:** `installer/execute_screen.py:566-571`

**Issue:** Every other core mutation this phase's worker performs is wrapped
in `run_live` so a failure is surfaced as `InstallRunFinished.error` rather
than an unhandled exception: `run_installs` (line 496), `wire_path` (520),
`verify` (527), `updates.run` (580), and even the *second* call to
`refresh.refresh` in this same method, on the success path (588,
`run_live(partial(refresh.refresh, [tool]))`). The *first* call to
`refresh.refresh` — the blocking single-tool refresh taken when no ownership
snapshot is cached yet — is not:

```python
ownership = refresh.ownership_of(tool.id)
if ownership is None:
    refresh.refresh([tool])          # <-- bare call, no run_live, no try/except
    ownership = refresh.ownership_of(tool.id)
if ownership is None:
    continue
```

`VersionRefreshService.refresh()` calls `save_version_cache`, which calls
`atomic_write_text` with no internal exception handling
(`installer/version_cache.py:154-175`) — a plausible `OSError` (disk full,
permission denied, a stale/read-only mount) propagates straight out of this
call. Because `_run_updates()` itself is invoked directly (not through
`run_live`) from `_execute_worker`'s `else` branch, an exception here
escapes the whole method, skips the assignment
`update_outcomes, update_errors, update_skips, update_versions =
self._run_updates()`, and lands in `_execute_worker`'s outer `try/finally`
with `error` still `None` and all four update fields at their empty
initial values. `on_install_run_finished` then renders a completely normal
`"Done. enter or esc returns to the catalog."` in the **ok** style — the run
looks like it finished cleanly while the actual failure (and the fact that
none of the queued updates ran) is invisible to the user. This is the same
consequence Phase 13's review already named for a different trigger
(WR-01 in `13-REVIEW.md`): "A crashed install run is indistinguishable from
a clean one, to both the human and to CI." No test exercises this: every
recording `VersionRefreshService` double used in `tests/test_execute_screen.py`
(`_RecordingRefreshService.refresh`) always succeeds.

**Fix:** Wrap the same way the success-path refresh already is:

```python
ownership = refresh.ownership_of(tool.id)
if ownership is None:
    _refreshed, refresh_fail = run_live(partial(refresh.refresh, [tool]))
    if refreshed_fail := refresh_fail:
        skip = f"could not refresh ownership for {tool.id}: {refreshed_fail}"
        skips.append(skip)
        continue
    ownership = refresh.ownership_of(tool.id)
```

and/or give `_execute_worker`'s outer `try` a catch-all `except Exception`
before the `finally` (mirroring the fix Phase 13's review proposed for its
own WR-01), so any future unprotected call in this method degrades to a
reported error instead of a silent, misleadingly-successful run.

### WR-02: A worker-thread update skip is written directly to a screen attribute, bypassing this file's own `post_message` doctrine, and has no production reader

**File:** `installer/execute_screen.py:386,576`; `tests/test_execute_screen.py:1650`

**Issue:** `ExecuteScreen.__init__` declares `self.update_skips: list[str] = []`
(line 386). It is mutated exactly once, from inside `_run_updates`, which
runs on the `@work(thread=True, exclusive=True, ...)` worker thread:

```python
if not updates.begin(tool.id):
    in_flight = updates.in_flight or "another tool"
    skip = f"update already in flight for {in_flight}"
    skips.append(skip)
    self.update_skips.append(skip)   # <-- direct cross-thread widget/screen mutation
    continue
```

This is exactly the pattern the file's own docstrings repeatedly warn
against — `InstallLogLine`'s docstring: "`post_message` is Textual's
thread-safe hand-off back to the event loop, so the worker never touches a
widget from its own thread." Every other worker→UI communication in this
class (log lines, per-tool progress, prompt-open state, the final summary)
goes through a `Message` subclass and `post_message`; this one line does
not. In practice the same string is *also* appended to the local `skips`
list in the same breath, which correctly flows through
`InstallRunFinished(update_skips=...)` → `on_install_run_finished` →
`_render_updates` — i.e. the user-visible summary never reads
`self.update_skips` at all. Grepping the whole tree, its only reader
anywhere is the test itself
(`tests/test_execute_screen.py:1650`,
`test_in_flight_latch_skips_outdated_update_and_keeps_the_holder`). This
looks like leftover state from before the `InstallRunFinished`-based
plumbing existed (per 14-02-SUMMARY.md's own description of introducing
that message) that was never deleted, and the test was written against the
attribute instead of the message payload that actually matters.

**Fix:** Delete `self.update_skips` and the direct append; change the test
to assert against `screen.summary`/the rendered log (as the sibling
`update_errors`/`update_outcomes` assertions already do), the same way
`test_blocked_update_reason_reaches_the_post_run_log` asserts through the
rendered report rather than through a raw screen attribute.

### WR-03: `_ordered`/`_to_update` progress rows for the empty case still say "Install 0 tools?" nowhere — but the update-eligibility-after-refresh silent drop has no user-facing message

**File:** `installer/execute_screen.py:566-571`

**Issue:** (Closely related to WR-01 but distinct even absent an exception.)
If `refresh.refresh([tool])` *succeeds* but genuinely still cannot resolve
ownership for a tool (`ownership_of(tool.id)` remains `None` after the
refresh), the tool is silently dropped with `continue` — no entry in
`skips`, no `InstallLogLine`, no `UpdateToolFinished` post. Compare every
other way an update can fail to reach the user in this same method: a latch
refusal appends a skip string; a `run_live`-wrapped failure appends an
`(id, reason)` error tuple; `UpdateService.run` itself always returns an
`unknown-owner` outcome with `ownership.unknown_reason` rather than raising.
This is the one silent path. Today it is effectively unreachable —
`VersionRefreshService.refresh()` unconditionally populates
`self._ownership[tool.id]` for every tool passed to it, because
`resolve_ownership` has a non-`Optional` return type and is called for each
tool regardless of outcome — but the `if ownership is None: continue` guard
exists precisely to handle the case where it doesn't, and if that invariant
is ever weakened by a future change to `refresh()`, the affected tool would
vanish from the run's final report with zero explanation, unlike every
sibling failure path in the same function.

**Fix:** Either delete the dead branch (and add an assertion/comment
documenting why `ownership_of` is guaranteed non-`None` post-refresh so a
future reader doesn't reintroduce ambiguity), or — safer — replace the
silent `continue` with the same skip-and-log pattern the latch-refusal
branch three lines below it already uses, so the invariant does not have to
hold forever for the UI to stay honest.

## Info

### IN-01: Explicit "No" on the sensitive-action prompt is silent, while dismissing it (escape) explains itself

**File:** `installer/execute_screen.py:613-624`

**Issue:** `_ask_sensitive_action` writes an `InstallLogLine` explaining what
happened only when `answer is None` (escape/dismiss): `"{tool_id}:
sensitive-action prompt dismissed; the answer was therefore no."` Choosing
"No, skip this" explicitly (`answer == "no"`) returns `False` with no log
line at all — the user gets no acknowledgement anywhere in the post-run
report that their answer was registered (`post_install_handoff` is simply
empty, and `render_post_install_handoff` stays silent for an empty tuple).
This mirrors `_ask_mismatch`'s existing asymmetry (only the dismissal case
gets a line) so it is consistent with established precedent in this file
rather than a new inconsistency, but it means a deliberate "no" to a
security-relevant confirmation leaves zero trace in the log a user might
review afterward.

**Fix:** Optional — write a lighter-weight acknowledgement line
(`"{tool_id}: login-shell change declined."`) on explicit "no" too, for
parity with the escape case and for anyone auditing the run log later.

---

_Reviewed: 2026-09-14T18:18:39Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
