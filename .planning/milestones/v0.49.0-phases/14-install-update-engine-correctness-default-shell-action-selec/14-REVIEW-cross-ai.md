---
reviewer: opencode-cross-ai
model: router-env/my-coding
reviewed_at: 2026-09-14T18:32:25Z
status: "issues-found — WR-01/WR-02/WR-03 fixed in 67b9d66, corroborated by 14-REVIEW.md"
---

# Phase 14 cross-AI code review

Independent second pass over `9a36943..HEAD` (`installer/`, `setup.py`, `tests/`).
Read the full sources of the changed modules, not just the hunks. Did not
re-run `make validate` / `make test`.

## Critical

None. D-04 and D-05 hold on every production entry point I can reach. There
is no code path that executes `chsh` (or any other login-shell mutation)
from the installer, on immutable or mutable hosts.

## Warning

### WR-01: Pre-dispatch `refresh.refresh` is unwrapped; an `OSError` looks like a clean run and also skips PATH wiring

**File:** `installer/execute_screen.py:519,566-571`

The first-pass review (`14-REVIEW.md` WR-01) is correct and slightly
understates the blast radius.

Every sibling I/O call in `_execute_worker` / `_run_updates` goes through
`run_live` (`run_installs` at 496, `updates.run` at 580, the *success-path*
`refresh.refresh` at 588, `wire_path` at 520, `verify` at 527). The
deliberate-divergence blocking refresh for a missing ownership snapshot
does not:

```python
if ownership is None:
    refresh.refresh([tool])          # bare call
    ownership = refresh.ownership_of(tool.id)
```

`VersionRefreshService.refresh` writes the cache via
`save_version_cache` → `atomic_write_text` (`installer/version_cache.py:154-175`,
`installer/atomic.py:51-53`). That write re-raises `OSError`. `_run_updates`
is invoked *directly* from `_execute_worker`'s `else` branch (line 519), not
through `run_live`. An exception here:

1. Leaves `error` still `None` and all four update payload fields at their
   empty initial values.
2. Skips `wire_path` and `verify`, which sit *after* the `_run_updates()`
   call in the same `else`.
3. Lands in the outer `try/finally`, which still posts `InstallRunFinished`.
4. `on_install_run_finished` then paints `"Done. enter or esc returns to
   the catalog."` in the ok style (`execute_screen.py:708`).

The user sees a successful, empty update section *and* no PATH-wiring
block, after a run that may have just installed tools. Phase 13 already
named this class of failure (a crashed worker indistinguishable from a
clean one). No test covers it: every `_RecordingRefreshService.refresh`
in `tests/test_execute_screen.py` succeeds.

Wrap this call the same way line 588 already wraps the post-update probe,
and/or catch `Exception` in `_execute_worker` before `finally` so any
future bare call degrades to a reported error.

### WR-02: Worker thread mutates `self.update_skips`; the attribute has no production reader

**File:** `installer/execute_screen.py:386,576`

Agreed with first-pass WR-02. `_run_updates` runs on
`@work(thread=True, exclusive=True, group="install-execute")`. The latch-
refusal branch does:

```python
skips.append(skip)
self.update_skips.append(skip)   # worker thread, no post_message
```

The file's own doctrine (`InstallLogLine` docstring at 236-237) is that
the worker never touches screen state; every other worker→UI hand-off
goes through `post_message`. The user-visible summary already receives
the same string via `InstallRunFinished.update_skips`. The only reader
of `self.update_skips` in the tree is
`tests/test_execute_screen.py:1650`. Delete the attribute and the
append; assert through the rendered log / message payload.

CPython list append is typically atomic, so this is not a practical
data-race crash today. It is still a doctrine violation sitting next to
the one new worker method this phase added, and it is dead production
state.

### WR-03: Ownership-still-None after refresh is a silent drop

**File:** `installer/execute_screen.py:570-571`

Agreed with first-pass WR-03. After the (unwrapped) refresh, a still-None
ownership is `continue` with no skip string, no `UpdateToolFinished`, no
log line. Every other non-success in this method is visible: latch
refusal records a skip, `run_live` failures go into `update_errors`,
`UpdateService.run` always returns an `unknown-owner` outcome.

Today the branch is effectively unreachable:
`VersionRefreshService.refresh` always writes `self._ownership[tool.id]`
because `resolve_ownership` is non-optional. The guard exists anyway.
If that invariant ever weakens, a queued update vanishes from the
post-run report. Replace the silent `continue` with the same
skip-and-record pattern the latch branch uses three lines below, so the
UI stays honest without relying on an undocumented invariant.

## Info

### IN-01: `--all` / `--categories` console path still silently no-ops outdated tools

**File:** `setup.py:895-903`; `installer/app.py:140-168`

D-01 is implemented only on the in-TUI `ExecuteScreen` path
(`CatalogScreen.Decided` → `UnifiedApp.on_catalog_screen_decided` →
`ExecuteScreen`). That is the `make setup` path and the one the bug
report describes; 14-01-PLAN.md is explicit that `run_wizard` is now
CLI-flags only.

It is still true that `python setup.py --all` / `--categories` goes
through `run_wizard` → `resolve_dependencies` (which still drops
already-installed tools, `installer/deps.py:111-113`) → `run_installs`
with no `UpdateService` call site at all. Selecting an installed-but-
outdated tool on that path is the original silent no-op. Out of this
phase's stated scope, but it is the same bug on a still-supported
entry point. Record it or wire the same split beside `run_wizard`.

### IN-02: Explicit "No" on the sensitive-action prompt leaves no log line

**File:** `installer/execute_screen.py:613-624`

`_ask_sensitive_action` logs only `answer is None` (escape). Choosing
"No, skip this" returns `False` with an empty `post_install_handoff` and
no acknowledgement. Same asymmetry as `_ask_mismatch`. Optional: a
one-line `"login-shell change declined"` for anyone auditing the run
log.

### IN-03: `default_enabled_sensitive_actions` remains schema-only

**File:** `installer/model.py:269,642-649`; `installer/post_install.py:40-49`

The dispatcher never reads this field. That is the right call for D-05
(a registry default cannot bypass confirmation — locked by
`test_immutable_host_cannot_bypass_login_shell_guard_via_default_enabled`).
It also means the field is still orphan schema after this phase wired
the one action that the field was invented for. Pre-existing; not a
regression. Either adopt it as a *prompt-default* (never a skip-confirm
default) or delete it.

## What I checked and found sound

**D-04, unbypassable.** `_set_login_shell` (`installer/post_install.py:45-49`)
returns `()` on `platform.immutable` *before* consulting `confirm`. The
action has no subprocess, no `runner`, no `Popen` — the closed table
returns a fixed literal instruction tuple. `CHSH=no` on the oh-my-zsh
script method is unchanged (`installer/registry.toml:542`, locked by
`tests/test_registry.py:1023,1039`).
`default_enabled_sensitive_actions` cannot punch through. `detect_immutable`
is the ostree marker (`installer/platform.py:51-54`); if that probe is
wrong the guard is wrong, but that is pre-existing platform detection,
not this phase.

**D-05, every entry point.** Console: `run_wizard` binds
`None if options.yes else confirm_sensitive` via `with_sensitive_confirm`
(`installer/app.py:165`). In-app: `_execute_worker` binds
`None if self._inputs.unattended else self._ask_sensitive_action`
(`installer/execute_screen.py:495`) through the same adapter.
`--yes` on `make setup` flows `options.yes` into `ExecuteInputs.unattended`
(`setup.py:694`). Unattended is skip, not auto-yes. Direct `install_tool`
defaults `confirm_sensitive_action=None`, so any unwrapped caller is skip.
The prompt copy is truthful ("show a reviewed command… which you run")
on both surfaces.

**D-01 / D-02, update dispatch.** Eligibility matches `action_update_tool`
(skip only when a status exists *and* `outdated is False`). Consent is
the existing enter-start gate; `_run_updates` contains no
`ask_from_worker` / `push_screen_wait` (locked structurally). Latch:
`begin` failure records a skip and does not call `end`; `end` is in
`try/finally` only after a successful `begin`. The batch path and the
`u` keybind share one `UpdateService` instance (`setup.py:604-605`), so
the latch actually serializes the two call sites. Mutation-grade
refusal is inside `UpdateService.run` (fresh re-resolve), so the batch
path not repeating `action_update_tool`'s pre-check is not a gate hole.

**Thread-safety of the worker-to-modal pattern.** `ask_from_worker` is
still the one `call_from_thread` + `push_screen_wait` helper; it is not
widened. `SensitiveActionScreen` dismisses `"yes"` / `"no"` / `None`;
conversion to bool happens in `_ask_sensitive_action` on the worker.
`PromptOpen` serializes cancel-while-prompt the same way checksum
mismatch already did. Cancel stays inert while a question is open.
No `push_screen_wait` from the UI thread.

**`deps.py` purity.** Untouched. No `VersionStatus`, no
`ManagerOwnership`, no version/ownership coupling. The install/update
split is computed in `ExecuteScreen.on_mount` beside the resolver, as
the architecture rule requires. Locked by
`tests/test_deps.py::test_resolver_source_names_neither_version_status_nor_ownership`.

**`Install` protocol.** Not widened. `with_sensitive_confirm` is the
composition-point adapter. `attributed_install` and the pre-existing
fakes keep compiling. Locked by
`tests/test_session.py::test_install_protocol_parameters_are_unchanged`.

**Post-install isolation.** A raising confirm degrades to
`postinstall_warning` and does not flip `INSTALLED` to `FAILED`
(`installer/engine.py:167-174`). Already-installed and `MANUAL_REQUIRED`
never reach the dispatcher (single-direction trigger). The two closed
tables are proven disjoint.

## Verdict

The two bugs this phase was opened for are fixed on the path the bug
reports describe, and the safety properties that actually matter — no
in-process `chsh`, immutable hosts never asked, unattended is skip,
enter-start is the only update consent, the latch is not released on a
path that did not acquire it, `deps.py` stays pure — are implemented
and tested, not merely documented. Ship is not blocked by a D-04/D-05
hole. The remaining defects are in the one new worker method that talks
to shared I/O services: an unwrapped `refresh.refresh` can make a
crashed update tail look like a clean run *and* skip PATH wiring
(WR-01), a worker-thread attribute write bypasses the file's own
message doctrine (WR-02), and a still-None ownership is a silent drop
(WR-03). Fix WR-01 before anything else builds on `_run_updates`.
