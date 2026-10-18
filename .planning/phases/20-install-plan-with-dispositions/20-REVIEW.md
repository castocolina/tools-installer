---
phase: 20-install-plan-with-dispositions
reviewed: 2026-10-18T08:51:04Z
depth: deep
files_reviewed: 35
files_reviewed_list:
  - installer/app.py
  - installer/audit.py
  - installer/catalog_tui.py
  - installer/deps.py
  - installer/engine.py
  - installer/execute_screen.py
  - installer/post_install.py
  - installer/prompt.py
  - installer/render.py
  - installer/selection.py
  - installer/session.py
  - installer/update.py
  - installer/version_status.py
  - installer/wizard_app.py
  - scripts/container-e2e-verify.sh
  - setup.py
  - tests/state_doubles.py
  - tests/test_app.py
  - tests/test_audit.py
  - tests/test_catalog_tui.py
  - tests/test_deps.py
  - tests/test_docs.py
  - tests/test_engine.py
  - tests/test_execute_screen.py
  - tests/test_plan.py
  - tests/test_post_install.py
  - tests/test_prompt.py
  - tests/test_render.py
  - tests/test_selection.py
  - tests/test_session.py
  - tests/test_setup.py
  - tests/test_update.py
  - tests/test_version_status.py
  - tests/test_versions.py
  - tests/test_wizard_app.py
findings:
  critical: 5
  warning: 9
  info: 9
  total: 23
status: issues_found
---

# Phase 20: Code Review Report

**Reviewed:** 2026-10-18T08:51:04Z
**Depth:** deep
**Files Reviewed:** 35 (`git diff 9e35fb9 HEAD -- installer setup.py scripts tests`)
**Status:** issues_found

## Summary

I reviewed the plan model (`build_plan`, `_row`, blocked propagation), the engine (`execute_plan`, `_run_step`), the vocabulary and renderers (`render.py`), the TUI adapter (`ExecuteScreen` wait, run, finish), the headless route (`run_wizard`, `setup.main`), the app-level retention and exit code (`UnifiedApp`), and the e2e parser. I traced the code across modules and checked it against 20-SPEC, 20-UI-SPEC and 20-CONTEXT. The phase test modules pass (`test_plan`, `test_render`, `test_session`, `test_execute_screen`, `test_app`). I confirmed five findings with throwaway probes. The probes ran from the session scratchpad with the suite's `tests.conftest` guards (scratch HOME, no host binaries), and nothing in the repo was changed.

Main concerns:
- **The headless route cannot run on the real catalog.** Skill packs stay `checking…` after its one synchronous pass, so `--all` marks every row "not attempted" and exits 1 (CR-01).
- **The e2e gate would report that as clean** (CR-02).
- **The 20-10 rewrite silently dropped the update extras** from the run report (CR-03).
- **Plan defects:** a present dependency that is blocked for its own reasons blocks its selected dependents (CR-04), and a dragged dependency of a blocked tool is still installed (WR-04).
- **The state wait** hangs on any non-OSError refresh failure (CR-05). A late settle repaints the review over a running or finished run (WR-01).

The single engine, the retained selection (`intersection_update(retained(...))`), the exit code (`exit_code`/`run_errors`), the latch, the drift→repair path and the `r` toggle hold up as specified. `r` is accepted only on `can_reinstall` rows (direct, OK, `owner == "installer"`). Dragged and foreign rows refuse it.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Headless `--all` never runs anything — skill packs stay `checking…` because `refresh_skills` is never called

**File:** `installer/app.py:118-140` (with `installer/version_status.py:1228-1243`, `setup.py:1513`)
**Issue:** `run_wizard` makes one `refresh.refresh(tools)` pass and then treats any WAIT row as "State check failed". A skill pack that has `status_probes` builds its state as CHECKING while its host answers are missing or stale (`_skill_state`: `if hosts is None or hosts.stale: … checking=(SKILL_CHECKING_REASON,)`). Only `refresh_skills` produces fresh host answers, and the headless route never calls it. `_build_services` calls `seed_skills_from_cache()`, which seeds them as `stale=True`.
**Failure scenario:** I ran the real pass (`VersionRefreshService.refresh`) with the suite's fake probes over the shipped `registry.toml`. The WAIT rows left afterwards were `['ponytail', 'superpowers', 'softaworks-agent-toolkit', 'matt-pocock-skills']`. So `setup.py --all --yes` prints `State check failed: no state for ponytail, …`, marks every row of the 90-tool plan `not_attempted` and exits 1. The SPEC R6 acceptance case ("one outdated brew tool, `--all --yes` updates it and exits 0") cannot pass on the real catalog. The headless tests stub `_build_services`/`run_wizard`, so none of them sees this.
The TUI has a milder form of the same gap. `ExecuteScreen._wait_worker` also calls only `refresh()`. With a pack selected before the catalog's skill worker has answered (at launch, or after the post-run `invalidate` resets `_skills_probed`), Enter waits, settles, and then reports `State check failed: no state for ponytail` even though nothing failed.
**Fix:**
```python
# installer/app.py run_wizard (and ExecuteScreen._wait_worker)
try:
    refresh.refresh_skills(tools)   # host answers first; refresh_skills rebuilds pack states
    refresh.refresh(tools)
except (OSError, CommandError, ValueError) as exc:
    ...
```
Add a headless test that uses a real `VersionRefreshService` (fake probes) and a skill pack in the catalog, and asserts no WAIT rows remain after `run_wizard`'s pass.

### CR-02: The e2e acceptance gate ignores `not attempted`, `crashed` and the setup exit code — a run that installed nothing passes

**File:** `scripts/container-e2e-verify.sh:364-386, 478, 532, 571`
**Issue:** `parse_summary_line` extracts `PARSE_NOT_ATTEMPTED` and `PARSE_CRASHED`, but `accumulate_summaries` never adds them up. The pass gates check only `ACC_FAILED`, `ACC_MISMATCHED` and the dependency cross-check. `setup_status` is printed but never gated, and pass2 accepts exit 1 by design.
**Failure scenario:** CR-01's real output is `Summary — 90 not attempted` with exit 1. That parses to failed=0 and mismatched=0, so pass2 step 3 prints `TRACER_REINSTALL_OK installed=0 …` (no receipt assertion follows that step). A mid-run worker crash (`N installed, 1 crashed, M not attempted`) passes pass1 and both pass2 install steps the same way. The only real container proof of a full-catalog install can therefore report success for a run that crashed or never started.
**Fix:** Accumulate the two counters and gate on them. Also gate on the setup exit where the plan has no failure that is explained:
```bash
ACC_NOT_ATTEMPTED=$((ACC_NOT_ATTEMPTED + PARSE_NOT_ATTEMPTED))
ACC_CRASHED=$((ACC_CRASHED + PARSE_CRASHED))
...
if [[ "$ACC_FAILED" -eq 0 && "$ACC_NOT_ATTEMPTED" -eq 0 && "$ACC_CRASHED" -eq 0 \
      && "$dep_failures_ok" -eq 1 && "$ACC_MISMATCHED" -eq 0 ]]; then
```
Also treat a missing `Summary — ` line as INCOMPLETE rather than all-zero.

### CR-03: Successful-update extras are dropped — a failed pnpm-globals replay, cleanup warnings and postinstall warnings never reach the user

**File:** `installer/render.py:146-149` (with `installer/execute_screen.py:887-897`, `installer/app.py:166-173`)
**Issue:** The old screen's `_updated_line`/`_render_updates` printed `replayed_globals`, `cleanup_warnings`, `postinstall_warning` and `detail` for every update. The 20-10 rewrite routes UPDATE rows through `outcome_detail_text`, which returns `""` for `done`. Every end-of-run renderer is fed `installs` only (`outcome.install`), and an UPDATE row carries `update`, not `install`. The pin `test_successful_outdated_update_line_carries_outcome_extras` was deleted in 20-10 and was not among the c5e51a4 ports.
**Failure scenario:** A pnpm self-update succeeds, but `UpdateService.run` reports `detail="pnpm globals replay failed: …"` (the REQ-pnpm-global-reinstall-mitigation failure path). The row reads `✓ pnpm  updated`, and nothing in the TUI log or the headless output says the global packages were not restored. The same goes for an installer-owned update's `cleanup_warnings` (a leftover old version) and for `cache invalidation failed` / terminal-sync warnings folded into `detail`.
**Fix:** Render update extras for a done UPDATE row (in `outcome_detail_text`, or a small `render_update_notes(outcomes, console)` called next to the other reports in both routes), and port the deleted test:
```python
if outcome.result == "done" and outcome.update is not None:
    u = outcome.update
    parts = ([f"replayed {', '.join(u.replayed_globals)}"] if u.replayed_globals else [])
    parts += list(u.cleanup_warnings) + ([u.postinstall_warning] if u.postinstall_warning else [])
    parts += [u.detail] if u.detail else []
    return sanitize_log_line("; ".join(parts))
```

### CR-04: Selecting a present dependency that is BLOCKED for its own reasons blocks every selected dependent ("needs X" though X is installed)

**File:** `installer/session.py:849-863` (with `:688-694`, `:647-657`)
**Issue:** Blocked propagation keys on the dependency's *row disposition* (`blocked = {row.tool_id … BLOCKED}`), not on whether the dependency can satisfy the edge. A directly selected, present tool can be BLOCKED for reasons that have nothing to do with being installed: misconfigured with no executable step (L-20-04). Its selected dependents then become `blocked — needs X`. When the same X is only dragged, it is `skipped — already present` and the dependent installs. So selecting *more* blocks more.
**Failure scenario (probe-confirmed):** pnpm is present and misconfigured with no step; mmdc is missing.
- `build_plan(["mmdc"])` gives `pnpm skip "already present; …"` and `mmdc install`.
- `build_plan(["pnpm", "mmdc"])` gives `pnpm blocked "project pack: no repo detected"` and `mmdc blocked "needs pnpm"`.
`a` on a tier and headless `--all` select everything, so they hit this whenever any tier member is misconfigured with no step.
**Fix:** Propagate only from rows whose tool will be absent after the run:
```python
unsatisfied = {
    row.tool_id for row in rows
    if row.disposition is Disposition.BLOCKED and not _settled(state_of(row.tool_id))
}
```
Use `unsatisfied` in place of `blocked` in the loop. Keep adding dependents that were newly blocked by `needs`. A broken, sudo-blocked dependency stays unsatisfied because `_settled` is False for BROKEN.

### CR-05: A non-OSError refresh failure leaves the state wait hung forever — Enter is inert and no error is shown

**File:** `installer/execute_screen.py:557-562`
**Issue:** `_wait_worker` posts `StateSettled` only when `run_live` returns, and `run_live` catches only `OSError`, `CommandError` and `ShellrcRefusal`. `VersionRefreshService.refresh` re-raises any `BaseException` from the pass to its joiners (`raise failure[0]`). The headless route itself already catches `ValueError` here. On any other exception the thread worker dies (`exit_on_error=False`), `_waiting` stays True, and `_start_requested` stays True. UI-SPEC requires "If the refresh raises … `State check failed: {error}`. enter retries".
**Failure scenario (probe-confirmed):** With `held_service(raising=ValueError("bad cache"))`, after Enter and release the status stays `Waiting for the state check; nothing starts until it finishes. esc cancels.` (`_waiting=True`). A second Enter makes no new refresh call. If the mount-time wait is the one that dies, the next Enter also hangs, because `_await_state` returns early on `_waiting`. Only `esc` recovers. `catalog_tui._refresh_versions_worker` uses `try/finally` for exactly this reason.
**Fix:**
```python
@work(thread=True, exclusive=True, group="execute-wait", exit_on_error=False)
def _wait_worker(self, token: int) -> None:
    error: str | None = "state check did not complete"
    try:
        _result, error = run_live(lambda: self._inputs.version_refresh.refresh(self._inputs.catalog))
    except Exception as exc:  # noqa: BLE001 -- the wait must always settle
        error = (str(exc).splitlines() or [type(exc).__name__])[0] or type(exc).__name__
    finally:
        self.post_message(StateSettled(token, error))
```
Add a test with a `ValueError`-raising held service.

## Warnings

### WR-01: A late `StateSettled` repaints the review over a running or finished run

**File:** `installer/execute_screen.py:564-575`
**Issue:** `on_state_settled` calls `_replan()` without checking `started`/`finished`. If the state is published before the screen's own wait message is processed (another flight published, or Enter landed between publication and delivery), Enter starts the run, and the stale-but-matching token then rebuilds `self._rows` and `_paint_review` wipes the run UI.
**Failure scenario (probe-confirmed):**
- Mid-run, the rows change from `['> rg  will install']` to `['○ rg  will install — not installed']`, and the keys change from `c stop after this tool · …` to `enter start · up/down move · esc cancel`.
- After the finish, `✓ rg  installed` / `Summary — 1 installed` becomes `Install plan — 1 will install` with `enter start` keys. The finished screen then claims nothing ran.
**Fix:** Settle the wait bookkeeping, but never repaint once a run started:
```python
self._waiting = False
if self.started or self.finished:
    return
```

### WR-02: Failed reconfigure and update rows read `failed — no method succeeded`; the real reason is shown nowhere

**File:** `installer/render.py:150-155`
**Issue:** The `failed` branch reads only `install.errors` / `update.errors` and ignores `outcome.detail`. `_run_reconfigure` puts the failure only in `detail` (`f"{step.text}: {result.failed}"`, `session.py:449`). `UpdateService.run`'s pnpm-snapshot refusal returns `status="failed"` with `errors=()` and the reason in `detail` (`update.py:546-555`). `render_failure_details` covers only `InstallOutcome`, so neither reason appears anywhere.
**Failure scenario:** A `pnpm_group_install` step fails with "pnpm not on PATH". The row and the whole report say `failed — no method succeeded`, and the user cannot act on it.
**Fix:** `error = ...; detail = outcome.detail or (first line of errors[-1] if errors else "no method succeeded")`, and add tests for a failed reconfigure and a refused update.

### WR-03: A `terminal_sync` reconfigure step that raises becomes `crashed` and halts the whole batch

**File:** `installer/session.py:388-391`
**Issue:** `_run_step` calls `ctx.terminal_sync()` raw. Both wired closures (`_sync_omz_terminals`, `_sync_terminals`) call `sync_terminal_shells`, which can raise `OSError` (EACCES on kitty.conf, the case `test_setup` already fixtures) or `UnicodeDecodeError` (CR-02 of 15.6). The exception escapes to `execute_plan`'s `except Exception`. The row becomes `crashed`, `halted = True`, and every later runnable row becomes `not_attempted`. The codebase's own total seam for this is `terminal_sync_warning`.
**Fix:** Catch at the step and fail the row, not the batch:
```python
try:
    return _StepResult(warning=ctx.terminal_sync())
except Exception as exc:  # noqa: BLE001 -- a step failure, never a batch crash
    return _StepResult(failed=_first_line(exc))
```

### WR-04: A dragged dependency of a blocked requester is still planned and installed

**File:** `installer/session.py:834-863`, `installer/deps.py:150-151`
**Issue:** `closure` keeps every non-blocked tool reached from a selection, including dependencies reached only through a requester that is itself blocked. The propagation loop only blocks downward, so those dependencies stay `will install — needed by <blocked tool>`.
**Failure scenario (probe-confirmed):** `select mmdc` with puppeteer unavailable gives `pnpm install "needed by mmdc"`, `mmdc blocked "needs puppeteer"`, `puppeteer blocked`. Enter installs pnpm for a tool that will never install, and the reason text is false.
**Fix:** After propagation, turn any non-direct runnable row into SKIP (or drop it) when every requester in its reverse-dependency set is BLOCKED. Or have `resolve_dependencies` collect requirements only from tools that are not blocked.

### WR-05: Headless uses a second presence predicate for the engine's already-installed check

**File:** `installer/app.py:161`, `setup.py:1513-1524`
**Issue:** The TUI wraps `install_tool(..., present=version_refresh.is_present)` (D-04, L-20-09: "no second predicate that could disagree with the published state"). `main` passes no `install=`, so headless uses `install_tool`'s default `is_installed`. The plan comes from `refresh.state_of`, but the engine's short-circuit uses a different lookup (`shutil.which` without the service's looked-through `which` / `managed_bin_dir`). An INSTALL row can then come back `skipped — became present before it ran` in headless while the TUI installs it, which breaks "same plan, same engine" (R6).
**Fix:** In `run_wizard`, bind `install=functools.partial(install, present=refresh.is_present)` (or move `_install` from `_build_app` into `_build_services` and return it).

### WR-06: Declining `Run this plan?` has already written receipts and the version cache

**File:** `installer/app.py:118-148`
**Issue:** The headless route now runs a full refresh pass before the prompt. That pass may adopt receipts (`receipts.adopt` → `_write_unlocked`), retire receipts (`receipts.retire`), and rewrite `~/.local/state/tools-installer/versions.json`, for the whole catalog even under `--categories`. It then prints `Cancelled; nothing was changed.` The old headless audit wrote nothing. Adoption changes what `--uninstall` will later treat as removable.
**Fix:** Either word the decline honestly ("nothing was installed or updated"), or document that the refresh's bookkeeping is part of every headless run. At minimum, do not claim "nothing was changed".

### WR-07: The e2e summary parser depends on GNU sed (`\b`, `t;`) and aborts on a macOS host

**File:** `scripts/container-e2e-verify.sh:251`
**Issue:** `accumulate_summaries` runs on the host, and the architecture supports macOS hosts (colima). BSD sed has no `\b`, and it reads `t; s/.*/0/p` as a branch to the label `; s/.*/0/p` ("undefined label"). `PARSE_*` then ends up empty, and `$((ACC_INSTALLED + ))` is an arithmetic error that kills the script under `set -e`.
**Fix:** Use the bash regex the script already uses elsewhere:
```bash
if [[ "$line" =~ (^|[ ,—])([0-9]+)\ ${category}(,|$) ]]; then v="${BASH_REMATCH[2]}"; else v=0; fi
printf -v "PARSE_${name}" '%s' "$v"
```

### WR-08: A skipped row with OK health shows the same green `✓` as a done row

**File:** `installer/render.py:123, 129-135` (with `installer/version_status.py:192`)
**Issue:** `_DONE_MARK = ("✓", "green")` and `HEALTH_MARKS[Health.OK] = ("✓", "green")` are the same glyph and style. `outcome_mark` keeps the health glyph for `skipped`/`blocked`, so every `skipped — already current` row ends the run with a green check, the same mark as `installed`. This contradicts the UI-SPEC's own claims that "A skipped row never turns green" and "All eight marks are distinct glyphs". The code follows the Marks table, so the spec is inconsistent with itself.
**Fix:** Give the run-done mark a glyph that differs from OK health (for example `✔`), or show skipped rows with the dim SKIP style instead of the green OK glyph. Then record the choice in UI-SPEC.

### WR-09: Behaviour lost with `reapply_post_install` — an installed oh-my-zsh can no longer show the reviewed `chsh` handoff

**File:** `installer/engine.py` (deleted `reapply_post_install`), `installer/post_install.py:17-21`
**Issue:** Before Phase 20, re-selecting an installed tool dispatched its `post_install` actions once. That was the only way to get the `set_login_shell` handoff for `oh-my-zsh` (`registry.toml:582`) after declining it or after an install by another route. Now the row is `skipped`. `r` is either refused (when OMZ is not attributed to the installer), or it runs `install.sh` again with `repair=True`. OMZ's `install.sh` exits non-zero when `~/.oh-my-zsh` already exists, so the reinstall most likely fails before the handoff. D-06 removed the generic reapply for RECONFIGURE, but this user-facing path has no replacement and no test.
**Fix:** Either plan a direct OMZ selection as RECONFIGURE with a `post_install` step (the dispatcher already exists), or record the loss explicitly in CONTEXT and the docs so it is a decision rather than a side effect.

## Info

### IN-01: The running keys line is unpinned

**File:** `installer/execute_screen.py:88`
**Issue:** `test_execute_keys_names_escape_c_and_ctrl_c_with_distinct_meanings` was deleted in 20-10 and not ported. No test contains `c stop after this tool`. Only the esc-mid-run status copy is loosely checked (`"ctrl+c" in text`).
**Fix:** Assert `_KEYS_RUNNING` verbatim while a held install runs.

### IN-02: Competing outcome words outside `WORDS`/`RESULT_WORDS`

**File:** `installer/render.py:279`, `installer/execute_screen.py:900-902`, `installer/session.py:801`
**Issue:**
- `render_skipped` still prints `⚠ X skipped — dependency failed: Y` under a row that reads `dependency failed — Y` (red, exit 1).
- The screen adds a separate `Not attempted: …` line.
- `_blocked_row`'s fallback `blocked.reason` produces `blocked — foo is not available on this platform — skipped` when no state is published yet.
- `render_failure_details` uses `✗` (U+2717) beside the new `✖` (U+2716).
**Fix:** Reword `render_skipped` to `dependency failed`. Drop the duplicate line. Fall back to `"not available on this platform"` in `_blocked_row`.

### IN-03: `run_wizard`'s `platform` parameter is dead

**File:** `installer/app.py:102`
**Issue:** The body reads only `refresh.platform`.
**Fix:** Remove the parameter from the signature and its callers.

### IN-04: The app invalidates the epoch after a run where nothing ran

**File:** `installer/wizard_app.py:2995-2999`
**Issue:** `a` on an all-current tier, then Enter, ends with `invalidate`. That drops the manager snapshot and turns every tier to `…` for a 5 s pass, even though L-20-08/D-11 say a run where nothing ran has no side effects.
**Fix:** Gate on `ran_anything(message.outcomes)`.

### IN-05: The state-check error text can span several lines

**File:** `installer/execute_screen.py:570-572`
**Issue:** `Text.truncate` keeps embedded newlines. A multi-line `CommandError` therefore breaks the one-line, 78-cell status contract.
**Fix:** Take the first line before truncating.

### IN-06: `fold_reason` degenerates on narrow widths

**File:** `installer/render.py:67-71`
**Issue:** When the first line is already wider than `width`, `room = 1`, and the reason wraps one character per line.
**Fix:** Clamp `room` to at least, say, 20 cells, or fall back to the continuation room.

### IN-07: Long dependency-failed rows fold at 100 cells, which the e2e grep cannot read

**File:** `installer/render.py:217`, `scripts/container-e2e-verify.sh:381`
**Issue:** `render_run_summary` caps the width at `min(console.width, 100)`, so `COLUMNS=2000` no longer prevents folding. A row whose blocker list folds loses its later blockers. It can also leave a trailing comma, which `dependency_failures_explained` reads as an empty blocker, giving a false INCOMPLETE.
**Fix:** Read the blockers from `render_skipped`'s one-line form, or join continuation lines before the grep.

### IN-08: Decline wording and drift-note promises

**File:** `setup.py:1526`, `installer/version_status.py:1625-1631`
**Issue:**
- A declined headless run prints both `Cancelled; nothing was changed.` and `Aborted.`.
- `UNPROVEN_NOTE` ("press r on the review to reinstall") is also attached when the receipt is broken. That row is planned as REPAIR, and `r` refuses it.
**Fix:** Print one line on decline. Attach the note only when there is no receipt and the tool is not broken.

### IN-09: Plan-gate miscalibrations (confirmed for the verifier)

**File:** `.planning/phases/20-install-plan-with-dispositions/20-14-PLAN.md:98,107`, `20-13-PLAN.md:111`
**Issue:**
1. **20-14 Task 1 floor: confirmed miscalibrated.** It counts `def test_` lines: 71 against a floor of 95, while pytest collects 107 items (parametrized). As written, the gate fails on a suite that is fine.
2. **20-14 render.py zero gate: confirmed miscalibrated.** `render.py:126,150,159,161` hold quoted `"failed"`, `"crashed"`, `"manual"` as `RowOutcome.result` Literal discriminators, not display words (all display words come from `RESULT_WORDS`). A file-wide zero count can only be met by hiding real comparisons.
3. **20-13 `grep -c "self._reinstall ^= "`: confirmed miscalibrated.** It returns 0 under GNU grep, although `execute_screen.py:518` has the code; `grep -cF` returns 1.
**Fix:** Count collected items with `pytest --collect-only -q`. Exclude `outcome.result ==` comparisons from the word gate. Use `grep -F` for literal code checks.

---

_Reviewed: 2026-10-18T08:51:04Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
