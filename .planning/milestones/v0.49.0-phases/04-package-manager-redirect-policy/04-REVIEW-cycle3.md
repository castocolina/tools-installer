---
phase: 04-package-manager-redirect-policy
reviewed: 2026-09-05T00:00:00Z
depth: deep
cycle: 3
diff_base: 328aa47
files_reviewed: 9
files_reviewed_list:
  - installer/guards.py
  - installer/pnpm_globals.py
  - installer/wizard_app.py
  - installer/run.py
  - setup.py
  - tests/test_guards.py
  - tests/test_pnpm_globals.py
  - tests/test_wizard_app.py
  - tests/test_run.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 4: Code Review Report — Cycle 3 (final)

**Reviewed:** 2026-09-05
**Depth:** deep (cross-file, plus live execution of the generated shim and live Textual probes)
**Files Reviewed:** 9
**Status:** issues_found — 1 BLOCKER, 4 WARNING, 2 INFO

## Summary

Verdict up front, because the orchestrator needs a clean signal:

- **BL-01 (boolean-option whitelist / nopt explicit-value form): CLOSED.** Verified by executing the real generated shim, not by reading it. Zero leaks across a 23-option × 2-form sweep and every exploit string from cycle 2.
- **Dependency-confusion warning (`--registry=<url>` silently dropped): CLOSED.** Verified by execution.
- **False-zero-packages warning (unknown vs. genuinely empty): CLOSED at every layer**, including what the Doctor screen actually renders.
- **BL-02 (audit on the event loop): the thread-worker move is real, the timeout is real and correctly scoped to the audit only, and there is a genuine responsiveness regression test.** But the refactor that carried it introduced a **new, concretely reproduced defect** in the interaction between the two now-separate workers (CR-01 below). This is the only blocker.

CR-01 was reproduced by running the app: after a successful reinstall the Doctor renders
`pnpm-managed global set is incomplete … mmdc … no longer resolves on PATH` **directly above**
`pnpm globals reinstalled.` — the exact rendering `on_globals_reinstalled` and
`test_doctor_r_clears_the_stale_missing_globals_warning` exist to prevent. The existing test passes
only because its timing never produces the overlapping interleaving.

Fix is small (one guard + one stale-result check). Everything else in the second fix pass holds up.

### Verification evidence

**BL-01 — executed, not inferred.** Generated the real `npm`/`pnpm` bodies via
`guards.global_redirect_shim_script`, pointed them at instrumented `volta`/`pnpm` stand-ins, and ran
them under `/bin/sh`:

| argv | result |
| --- | --- |
| `npm i -g --ignore-scripts typescript` | hard block (degrades) ✓ |
| `npm i -g --ignore-scripts false typescript` | hard block ✓ |
| `npm i -g --save-dev true` | hard block ✓ |
| `npm i -g --force / --offline / --prefer-offline typescript` | hard block ✓ |
| `npm i -g --registry=https://evil.example.com typescript` | hard block ✓ |
| `npm i -g --prefix=/tmp/x typescript` | hard block ✓ |
| `npm i --global=true typescript` / `--global=false` | hard block ✓ |
| `npm i -g typescript` | `volta install typescript` ✓ |
| `npm install -g typescript` / `npm add -g typescript` | `volta install typescript` ✓ |
| `npm i -g --silent typescript` / `--verbose` / `--save-exact` / `--no-save` / `--save` / `--save-dev` / `--save-prod` / `--save-optional` / `--recursive` / `--workspace-root` | `volta install typescript` ✓ |
| `npm i -gD / -gE / -gP / -gO / -gS / -gB / -gDE typescript` | `volta install typescript` ✓ |
| `npm i -gw / -gC / -gF / -gr / -gx typescript` | hard block ✓ (value-carrying or unknown cluster letters) |
| `npm i -g typescript prettier` | `volta install typescript prettier` ✓ (multi-package intact) |
| `npm i -g --silent=true typescript` | `volta install typescript` ✓ (whitelisted name, attached form) |
| `npm i -g` | `a global install needs a package name`, exit 127 ✓ |
| `pnpm add -g typescript` | `volta install typescript` ✓ |
| `pnpm add -g --registry=… mypkg` | passthrough **with `--registry` intact** ✓ |
| `pnpm -Cmy-gadget add -g x` | passthrough, `-g` never flips ✓ |

Plus a sweep of 23 value-taking options (`--registry --prefix --loglevel --workspace --userconfig
--globalconfig --cache --script-shell --node-options --before --omit --include --tag --dir
--store-dir --config-dir --filter --reporter --network-concurrency --package-import-method
--shamefully-hoist --strict-peer-dependencies --resolution-mode`) in **both** the separated
(`--opt VALUE`) and attached (`--opt=VALUE`) forms: **zero reached volta.**

I also audited the whitelist itself against nopt/pnpm semantics rather than trusting the comment:
all 11 entries are Boolean in both parsers, all 7 short letters (`gDEPOSB`) are Boolean in both, and
nopt's explicit-Boolean-value form accepts *only* the literal strings `true`/`false` (nopt
`parse()`: `if (la === 'true' || la === 'false')`), so the bare `true|false` arm covers that form
completely rather than only the two reported strings. No new false negative was found among the ten
legitimate global-install shapes tested; the only shapes that stopped redirecting are the four
options volta cannot honour, which is the intended, argued degradation.

**BL-02 — executed.** `_audit_globals_worker` is `@work(thread=True, exclusive=True,
group="globals-audit")` and hands its result back by `post_message`; the reinstall lives in a
separate group so `exclusive` cannot make one cancel the other. The timeout is correctly scoped:
`pnpm_globals._run_list` passes `LIST_TIMEOUT_SECONDS=20.0` to `run_output`, and it is wired only
into `pnpm_global_packages`' default `runner_out` — `reinstall_node_globals` still goes through
`run_captured` → `run_output(cmd)` with `timeout=None`, so a legitimately long `pnpm add -g` is not
killed (`tests/test_run.py::test_run_output_unbounded_by_default` locks that in).
`tests/test_wizard_app.py::test_doctor_audit_runs_off_the_event_loop` is a real regression test, not
a unit test on the pure function: it blocks the audit callable on a `threading.Event`, then asserts
from the still-live event loop that the body renders `Checking pnpm's global set` **and** that a
keypress is still handled. Run synchronously, `run_test`'s `async with` could never return.
`test_doctor_never_asks_pnpm_from_the_main_thread` additionally asserts `"MainThread" not in threads`
across entry, re-entry, and post-reinstall. I also probed app teardown while the audit thread was
blocked for 3 s: shutdown took 0.34 s, so the worker does **not** wedge exit.

**Unknown-vs-zero — executed.** Rendered the Doctor body with `known=False`: it prints
`pnpm's global set could not be read (pnpm missing, or the query failed).` and never `0 package(s)`.
Pressing `r` yields `pnpm's global set could not be read — install or repair pnpm, then retry.`, not
`Nothing to reinstall`. The genuinely-empty case still prints `0 package(s) in pnpm's global set` and
`pnpm manages no globals here`. The CLI path (`installer/app.py:266` → `render.py:148` →
`node_globals_guidance`) is silent for `known=False` because `missing` is empty, so it makes no false
claim either.

**Gates.** `make validate` (ruff, ruff format, pyright, bandit, vulture, shellcheck) passes clean;
the full suite passes, and `tests/test_wizard_app.py` passed 3/3 consecutive runs with no flakes.

---

## Critical Issues

### CR-01: A reinstall that finishes while an audit is in flight loses its re-audit and renders a stale, contradictory globals report — BLOCKER

**File:** `installer/wizard_app.py:237-243` (`_start_globals_audit`), `installer/wizard_app.py:347-371` (`action_reinstall_globals`), `installer/wizard_app.py:414-425` (`on_globals_reinstalled`)

**Issue:**

The guard between the two workers is **one-directional**. `_start_globals_audit` refuses to start an
audit while a reinstall is running, but `action_reinstall_globals` never checks `globals_auditing`.
Its only preconditions are `globals_done`/`globals_running` and a non-`None`, `known`, non-empty
`self._globals_report` — and that report survives from a *previous* audit, so `r` is fully enabled
while a *new* audit (started by `enter_view`) is still in flight.

That produces two defects at once:

1. **Two pnpm processes run concurrently on the same global store** — `pnpm list -g --json` and
   `pnpm add -g …`. Verified: an instrumented `reinstall_globals` observed the audit thread still
   inside its callable.
2. **The post-reinstall re-audit is silently dropped.** `on_globals_reinstalled` calls
   `_start_globals_audit()`, which returns early because `globals_auditing` is still `True` from the
   older audit. That older audit then lands with its **pre-reinstall snapshot** and overwrites
   `self._globals_report` / `_globals_preview_text` via `on_globals_audited`.

The comment at `wizard_app.py:239-241` asserts the opposite ("A reinstall in flight re-audits when it
finishes"), and `on_globals_reinstalled`'s own comment says the re-ask exists so the screen does not
render "mmdc went missing" above "pnpm globals reinstalled." Both are false under this interleaving.

**Reproduction (executed against the real app, not reasoned about).** Sequence: enter Doctor
(audit 1 lands) → `escape` → `4` (re-enter; audit 2 starts and blocks, as a cold-cache
`pnpm list -g --json` does) → press `r` (reinstall runs and clears the missing set) → release
audit 2. Observed:

```
PROBE calls:            ['audit1', 'audit2', 'reinstall']      # no re-audit after the reinstall
PROBE guidance titles:  ['PATH looks healthy', 'pnpm-managed global set is incomplete']
PROBE reinstalled line: True
PROBE incomplete line:  True
```

Rendered body contains, simultaneously:
`pnpm-managed global set is incomplete … pnpm still tracks mmdc globally, but the command no longer
resolves on PATH` and `pnpm globals reinstalled.` — i.e. the screen tells the user the reinstall
succeeded and that it did not, and points them at `r`, which is now permanently dead
(`globals_done` short-circuits it). The stale state persists until the user leaves and re-enters the
Doctor view.

This is reachable by ordinary navigation (Doctor → escape → 4 → `r`), not by a contrived race: the
window is the whole duration of `pnpm list -g --json`, which is exactly the multi-second child this
phase moved onto a thread because it is slow.

**Fix:** close the guard in both directions *and* make a late audit yield to a newer one. Two small
changes:

```python
# 1. `r` must not start a reinstall on top of an in-flight audit: the answer on
#    screen is about to be replaced, and a concurrent `pnpm list -g` and
#    `pnpm add -g` touch the same global store.
def action_reinstall_globals(self) -> None:
    if self.globals_done or self.globals_running:
        return
    report = self._globals_report
    if self.globals_auditing or report is None or not report.known or not report.managed:
        if self.globals_auditing or report is None:
            self.globals_note = _GLOBALS_UNKNOWN_YET
        else:
            self.globals_note = _NOTHING_TO_REINSTALL if report.known else _GLOBALS_UNKNOWN
        self._refresh_body()
        return
    ...
```

```python
# 2. An audit started before a reinstall must not be allowed to land after it:
#    stamp each audit and discard a result from a superseded generation, so the
#    post-reinstall re-audit is always the one that wins.
def _start_globals_audit(self) -> None:
    if self.globals_auditing:
        return
    self.globals_auditing = True
    self._audit_generation += 1          # int, initialised to 0 in __init__
    self._audit_globals_worker(self._audit_generation)

@work(thread=True, exclusive=True, group="globals-audit")
def _audit_globals_worker(self, generation: int) -> None:
    report, error = run_live(self._node_globals)
    if report is None:
        report = _GLOBALS_UNREADABLE
    self.post_message(GlobalsAudited(report, self._globals_preview(report), error, generation))

def on_globals_audited(self, message: GlobalsAudited) -> None:
    if message.generation != self._audit_generation:
        return                            # superseded; a newer audit is authoritative
    ...
```

With (1) in place the `globals_running` half of the `_start_globals_audit` guard becomes dead and
should be dropped, which is why the snippet above removes it.

**Regression test to add** (mirrors the reproduction; must fail on today's code):

```python
async def test_doctor_reinstall_is_refused_while_an_audit_is_in_flight() -> None:
    # ... enter Doctor, leave, re-enter with a blocked audit, press "r"
    assert calls.count("reinstall") == 0
    assert "Still checking" in screen.globals_note
```

and one asserting `calls[-1] == "audit"` after a reinstall that overlaps an audit.

---

## Warnings

### WR-01: `GlobalsAudited.error` is set but never read — the audit's failure detail is discarded

**File:** `installer/wizard_app.py:118-122` (constructor stores `self.error`), `installer/wizard_app.py:404-412` (`on_globals_audited`)

**Issue:** `_audit_globals_worker` captures `error` from `run_live(self._node_globals)` and ships it
in the message, but `on_globals_audited` never touches `message.error`. When the audit fails with a
specific, actionable cause — `pnpm store is locked`, or the 20 s `CommandError` detail
`timed out after 20s` that `run_output` now produces — the user sees only the generic
`pnpm's global set could not be read (pnpm missing, or the query failed).` The whole point of
threading `known` through was to stop collapsing distinguishable states; this collapses them again
one layer up. It is also dead state that neither pyright nor vulture flags (it is an instance
attribute assigned in `__init__`).

**Fix:** either render it, or stop carrying it:

```python
def on_globals_audited(self, message: GlobalsAudited) -> None:
    self.globals_auditing = False
    self._globals_report = message.report
    self._globals_preview_text = message.preview
    self._globals_audit_error = message.error   # rendered under the count when not None
    ...
```

and in `_refresh_body`, when `report is not None and not report.known`:

```python
text.append(f"{_GLOBALS_UNKNOWN_COUNT}\n", style="yellow")
if self._globals_audit_error is not None:
    text.append(f"{self._globals_audit_error}\n", style="yellow")
```

### WR-02: the preview call inside the audit worker escapes the `run_live` seam, so an exception there panics the whole app

**File:** `installer/wizard_app.py:399-402`

**Issue:**

```python
report, error = run_live(self._node_globals)          # guarded
if report is None:
    report = _GLOBALS_UNREADABLE
self.post_message(GlobalsAudited(report, self._globals_preview(report), error))
#                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ unguarded
```

`self._globals_preview` is an injected callable that, in the composition root, resolves pnpm through
`real_pnpm` → `installer.locations.bin_dir(None)` → `Path.home()`. Anything it raises escapes the
worker body. I verified the consequence by injecting a raising `globals_preview` and running the app:
Textual re-raised `textual.worker.WorkerFailed: Worker raised exception: RuntimeError(...)` and the
app died — not an error line on the screen, a panic. That directly contradicts CLAUDE.md architecture
rule 3 / the PRD's "a failed core action is surfaced, never a silent crash", which `run_live` exists
to enforce, and it is the same reasoning that put `_node_globals` inside `run_live` two lines above.
`run_live` only catches `OSError`/`CommandError`, so even wrapping is not total — but the seam should
be the same for both calls. Not currently reachable with the production closure, which is why this is
a WARNING and not a blocker; it is one refactor away from being reachable.

**Fix:**

```python
outcome, error = run_live(lambda: (report_and_preview := self._audit_once()))
```

or, minimally, move the preview inside the guarded call:

```python
def _audit(self) -> tuple[NodeGlobalsReport, str]:
    report = self._node_globals()
    return report, self._globals_preview(report)

outcome, error = run_live(self._audit)
report, preview = outcome if outcome is not None else (_GLOBALS_UNREADABLE, _UNKNOWN_PREVIEW)
self.post_message(GlobalsAudited(report, preview, error))
```

### WR-03: the unknown-globals state prints the same sentence twice and then offers an action it will refuse

**File:** `installer/wizard_app.py:286-312` and `installer/wizard_app.py:88-91`; `installer/pnpm_globals.py:46`

**Issue:** rendered body for `known=False` (captured from the running app):

```
pnpm-managed globals
pnpm's global set could not be read (pnpm missing, or the query failed).
pnpm's global set could not be read — cannot preview the reinstall.
Press r to reinstall the pnpm-managed global set.
```

Three separate strings (`_GLOBALS_UNKNOWN_COUNT`, `pnpm_globals._UNKNOWN_PREVIEW`, and — once `r` is
pressed — `_GLOBALS_UNKNOWN`) say the same thing, two of them back to back, and the call to action in
between is guaranteed to be refused by `action_reinstall_globals`. Worse, there is **no way to retry
the audit from this screen**: `r` only sets a note, and `_start_globals_audit` is reachable only from
`on_mount`, `enter_view`, and `on_globals_reinstalled`. A user whose pnpm was momentarily locked has
to leave the Doctor view and come back.

**Fix:** collapse the duplicate line and make `r` re-run the audit when the set is unknown:

```python
else:
    text.append(f"{_GLOBALS_UNKNOWN_COUNT}\n", style="yellow")
    # the preview says the same thing; skip it in this branch
if report is None or report.known:
    text.append(self._globals_preview_text)
...
# in action_reinstall_globals, the `not report.known` arm:
self.globals_note = _GLOBALS_UNKNOWN
self._start_globals_audit()   # `r` retries the read it could not make
```

and change the trailing prompt for this branch to `Press r to retry reading pnpm's global set.`

### WR-04: comment announces "Four structural rules" and then lists five

**File:** `installer/guards.py:193` (the count) vs `installer/guards.py:221-227` (rule 5, added by this fix pass)

**Issue:** `# Four structural rules the body depends on:` is followed by items 1–5. This comment block
is the only specification of the shim's parsing contract — it is the artifact a future editor reads
before touching a security-relevant `case` ladder, and a miscount is exactly the kind of drift that
lets someone believe they have accounted for every rule when they have not.

**Fix:** `# Five structural rules the body depends on:`

---

## Info

### IN-01: `LIST_TIMEOUT_SECONDS` sits between two functions instead of with the module constants

**File:** `installer/pnpm_globals.py:135`

**Issue:** every other module constant (`_EMPTY_PREVIEW`, `_UNRESOLVABLE_PREVIEW`,
`_UNKNOWN_PREVIEW`, `_DEPENDENCY_GROUPS`) is declared at the top of the file at lines 44-47; this one
is declared after `parse_global_packages`. It is a public name (imported by
`tests/test_pnpm_globals.py`), so it is worth keeping discoverable.

**Fix:** move it up beside `_DEPENDENCY_GROUPS`.

### IN-02: the audit timeout kills only the direct child, not its process group

**File:** `installer/run.py:54-56`

**Issue:** `subprocess.run(..., timeout=…)` kills the `pnpm` process it launched, but a `pnpm` that
has already forked a node child leaves that grandchild running and holding the store lock — the very
contention `_run_list`'s docstring cites as the reason for the timeout. The 20 s bound therefore
guarantees the Doctor recovers, but not that the machine does.

**Fix:** if this proves real in practice, launch with `start_new_session=True` and
`os.killpg(os.getpgid(proc.pid), SIGTERM)` on timeout. Noted rather than required: the current
behaviour is strictly better than the unbounded wait it replaced.

---

## Cross-file / call-chain notes (deep pass)

Checked and found sound; recorded so a fourth cycle does not re-derive them:

- **`known: bool = True` threading.** Every construction site sets or correctly defaults it:
  `audit_node_globals` (both arms), `wizard_app._GLOBALS_UNREADABLE`, `reinstall_preview(known=…)`
  from both `setup.py:265` and `wizard_app.py:1084`. `installer/app.py:266` → `render.py:148` →
  `guidance.node_globals_guidance` returns `[]` for an unknown report because `missing` is empty, so
  the CLI doctor makes no claim. No caller reads `managed`/`entries` without also having `known`
  available.
- **The `cached_globals` cell is genuinely gone** from `setup.py`, and with it the last piece of
  mutable state shared between the event loop and a worker. `_globals_report` and
  `_globals_preview_text` are written only from message handlers, i.e. only on the app thread. The
  worker closures (`_node_globals`, `_globals_preview`, `_reinstall_globals`) are immutable bindings.
  CR-01 is an ordering defect, not a data race.
- **Worker grouping is correct.** `group="globals-audit"` vs `group="globals-reinstall"` means
  `exclusive=True` cannot make one cancel the other; leaving both in the default group would have.
- **App teardown does not block on a running thread worker** (measured: 0.34 s to tear down while an
  audit thread slept 3 s), so the 20 s bound is not also a 20 s quit delay.
- **`enter_view`'s "not on first entry" claim holds**: the screen is installed, not mounted, so
  `is_mounted` is False on the first entry and `on_mount` starts the only audit. No double-audit.
- **`run_output`'s except ordering is correct**: `TimeoutExpired` (a `SubprocessError`, not an
  `OSError`) is caught before `CalledProcessError` and `OSError`, so a timeout cannot be
  misreported as exit 127.
- **`_settle`'s new two-flag wait is not racy**: both `globals_running` and `globals_auditing` are
  set synchronously inside the keypress/message handler that starts the corresponding worker, and
  `on_globals_reinstalled` flips `running → False` and `auditing → True` inside one handler, so the
  helper cannot observe a gap. 3/3 clean consecutive runs of `tests/test_wizard_app.py`.
- **Pre-existing, not introduced here, not blocking:** once `globals_done` is True, `r` is dead for
  the life of the process even across view navigations (`action_reinstall_globals:350`). Unchanged by
  this cycle; flagged only so it is not mistaken for CR-01's stale-state symptom.

---

_Reviewed: 2026-09-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
_Cycle: 3 of 3_
