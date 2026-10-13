---
phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins
reviewed: 2026-09-14T09:25:54Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - installer/execute_screen.py
  - installer/settings.py
  - installer/wizard_app.py
  - installer/policy.py
  - installer/run.py
  - installer/session.py
  - installer/catalog_tui.py
  - installer/ui_common.py
  - setup.py
  - .claude/architecture.md
  - docs/prds/unified-ui-redesign-v1.0-prd.md
  - tests/test_execute_screen.py
  - tests/test_settings.py
  - tests/test_wizard_app.py
  - tests/test_policy.py
  - tests/test_policy_tweaks.py
  - tests/test_run.py
  - tests/test_session.py
  - tests/test_setup.py
  - tests/test_ui_common.py
  - tests/test_docs.py
findings:
  critical: 1
  warning: 6
  info: 10
  total: 17
status: "issues_found — blocking: CR-01 (unsanitized child-process output bypasses sanitize_log_line on the failure-report path)"
---

# Phase 13: Code Review Report

**Reviewed:** 2026-09-14T09:25:54Z
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Phase 13 moves install execution inside the running Textual app (`ExecuteScreen`),
adds an incremental `StreamingRunner`, a between-tools weak cancel, and a persisted
`link_mode` settings envelope. The core seams are well chosen: attribution rides the
existing `Install` parameter rather than an optional argument, the worker-to-modal
mechanism was spiked and is covered end-to-end against a real app, `should_continue`
is genuinely checked only between tools, and `StreamingRunner` drains-then-reaps
rather than signalling the child. Test depth is unusually good (1067 lines for the
execute screen alone).

The defects concentrate where Phase 13 changed the *lifetime* of the app. Every
previous flow ended when the catalog was accepted; now the app survives an install
and the user comes back to it. Three of the six warnings are consequences of that
(stale catalog, silently discarded selection, stale Doctor preview), and none is
covered by a test. The one Critical is a bypass of the phase's own declared security
control: `sanitize_log_line` guards the streaming path, but the failure-report path
writes the same untrusted child output to the terminal unsanitized.

The `Residual scope` section of `13-VALIDATION.md` was checked; none of the findings
below is an already-recorded deferral.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Unsanitized child-process output reaches the terminal on the failure path

**File:** `installer/run.py:178`, `installer/execute_screen.py:80-88,512-520`, `installer/render.py:84-85`

**Issue:** `sanitize_log_line` exists because, in its own words, "An install script's
escape sequences must not be able to reposition the cursor or recolour the running
frame." It is applied in exactly one place — `on_install_log_line`
(`execute_screen.py:478`) — and every raw line also reaches the terminal by a second
route that never touches it:

1. `StreamingRunner.__call__` keeps the last 20 raw lines in `tail` and raises
   `CommandError(cmd, returncode, detail="\n".join(tail))` (`run.py:153,178`) — the
   lines are stored verbatim, before any sanitization.
2. `CommandError.__init__` folds `detail` into the exception message
   (`run.py:33`: `f"{message}\n{detail}"`).
3. `engine.install_tool` attaches the exception to `InstallOutcome.errors`
   (`engine.py:135,162`).
4. `ExecuteScreen.on_install_run_finished` calls `render_failure_details`
   (`execute_screen.py:514`), which prints `str(outcome.errors[-1])`
   (`render.py:84-85`).
5. The captured string is written straight into the `RichLog`
   (`execute_screen.py:520`).

`render.py` applies `rich.markup.escape`, which escapes `[` only — it does not remove
ANSI. The capture `Console` uses `no_color=True`, which suppresses *Rich's own* colour
and has no effect on bytes already in the payload. Rich's `strip_control_codes` strips
only BEL/BS/VT/FF/CR; `ESC` (0x1B) survives. So the CSI sequences of any failing
third-party install script are rendered into a live TUI frame: cursor repositioning,
screen clear, scroll-region changes, and (on terminals with them enabled) title/clipboard
OSC sequences.

The test suite confirms the gap rather than closing it: `tests/test_execute_screen.py:139`
seeds `"fd line 3\x1b[31m"` and asserts `"\x1b" not in log` — but only on the *success*
path, and via a stub `install` that never raises. The failure test at
`tests/test_execute_screen.py:982` uses `RuntimeError("disk exploded")`, which carries
no control characters. The one attacker-reachable path is untested.

**Fix:** Sanitize at the boundary where untrusted text enters a widget, not only in the
log-line handler. Minimal version — sanitize the tail before it becomes a
`CommandError`, and defensively sanitize the whole captured report:

```python
# installer/run.py
from installer.execute_screen import sanitize_log_line  # or move it to a shared module

            line = raw.rstrip("\n")
            self._emit(self._current(), line)
            tail.append(sanitize_log_line(line))
```

```python
# installer/execute_screen.py
    def _render_captured(self, render: Callable[[Console], None]) -> str:
        buffer = io.StringIO()
        render(Console(file=buffer, width=80, no_color=True))
        return sanitize_log_line(buffer.getvalue())
```

`sanitize_log_line` preserves `\n` today (only chars in `range(32) - {9}` are dropped —
`\n` is 10, so it *is* dropped). Applying it to a multi-line report therefore needs the
newline kept:

```python
_C0_KEEP = frozenset({9, 10})  # tab, newline

def sanitize_log_line(line: str) -> str:
    return "".join(ch for ch in line if ord(ch) != _DEL and (ord(ch) >= 32 or ord(ch) in _C0_KEEP))
```

Move `sanitize_log_line` to `installer/ui_common.py` (or a new `installer/sanitize.py`)
so `run.py` can import it without `run.py` -> `execute_screen.py` -> `run.py` circularity.
Add a regression test that drives a *failing* stub install whose `CommandError.detail`
contains `\x1b[2J` and asserts the escape never reaches `_log_text(screen)`.

## Warnings

### WR-01: An out-of-contract worker exception is reported to the user as a successful, empty run

**File:** `installer/execute_screen.py:392-456`

**Issue:** `_execute_worker` initialises `error: str | None = None` and posts
`InstallRunFinished` from a bare `finally`. `run_live` catches only
`(OSError, CommandError)` (`ui_common.py:49`). Any other exception — a `ValueError`
from a malformed registry entry, a `KeyError` from `catalog=self._by_id`, a `RuntimeError`
from `StreamingRunner._current()` if a future refactor drops the `set_tool` call, a
`RuntimeError` from `call_from_thread` during teardown — propagates out of `run_live`,
skips the `else` branch, and lands in the `finally` with the initial values still bound:
`summary = summarize([])`, `outcomes = []`, `error = None`.

The screen then reports (`execute_screen.py:533-536`):
- `render_summary(summarize([]))` — all zeroes,
- no error line, because `message.error` is `None`,
- status `"Done. enter or esc returns to the catalog."` in the **ok** style.

`UnifiedApp.on_install_run_finished` merges that empty summary, so
`_run_interactive_wizard` (`setup.py:696-708`) sees `summary.failed == ()` and the
process **exits 0**. A crashed install run is indistinguishable from a clean one, to
both the human and to CI. The docstring's claim ("a screen stuck on 'Installing...'
forever is the worst failure mode") picks the wrong worst case: a false green is worse.

**Fix:** Catch the residual exception explicitly and carry it into the message.

```python
        try:
            ...
        except Exception as exc:  # noqa: BLE001 — the worker must not report a false success
            if error is None:
                error = f"the install run stopped unexpectedly: {exc!r}"
            raise
        finally:
            self.post_message(InstallRunFinished(...))
```

and in `on_install_run_finished`, choose the status severity from `message.error`
rather than unconditionally `"ok"`:

```python
        if message.error:
            self.status.set(f"Run ended with an error. {message.error}", "error")
        else:
            self.status.set("Done. enter or esc returns to the catalog.", "ok")
```

`raise` after the `finally` keeps `exit_on_error=False`'s Worker-level diagnosis intact.

### WR-02: The catalog is never repainted after a run — stale check marks and a stale "installed" column

**File:** `installer/wizard_app.py:1816-1819`, `installer/catalog_tui.py:225,264-266`, `installer/tool_browser.py:116,235-245`

**Issue:** `ToolBrowser.__init__` stores the passed set **by reference**
(`tool_browser.py:116`: `self.selected = selected`), and all three tier
`CatalogScreen`s are constructed with the app's shared `self._staged`
(`wizard_app.py:1568`). `_install_closed` does `self._staged.clear()`
(`wizard_app.py:1819`), which silently empties every browser's `selected` set —
but nothing repaints the `"sel"` cells. `ToolBrowser` has a mark-refresh loop
(`tool_browser.py:235-245`) that is only reached via `reload()`, and the only caller
after a pop is `CatalogScreen.on_version_status_refreshed`, which fires only if a
version refresh happens to be running. `CatalogScreen.enter_view`
(`catalog_tui.py:264-266`) is not called at all when a modal is popped — it is a
`show_view` hook, and returning from `ExecuteScreen` is a `pop_screen`, not a view
change.

Consequences, both reachable in a normal session:
1. The user returns to a catalog showing ✓ against every tool they just installed,
   while `selected_ids()` returns `[]`. Staging one new tool and pressing enter
   installs one tool while the screen displays five ticks.
2. `CatalogScreen._installed` is a snapshot taken at app construction
   (`catalog_tui.py:225`, `dict(installed)`). Nothing re-derives it after a run, so
   just-installed tools keep rendering as not installed, and
   `_ver_cell`/`group_tools`/the recommends logic all read the stale map. Before
   Phase 13 this was impossible — the app exited on accept.

`tests/test_wizard_app.py:4141` asserts `app.catalog.selected == set()`, i.e. the
*set*, never the rendered cells, so the test passes while the screen lies.

**Fix:** Make `_install_closed` a real post-run refresh rather than a set mutation.

```python
    def _install_closed(self, _result: None) -> None:
        self._staged.clear()
        for screen in self._catalogs.values():
            screen.refresh_after_install()
```

and in `CatalogScreen`:

```python
    def refresh_after_install(self) -> None:
        """Re-derive installed state and repaint marks after an in-app run."""
        self._installed = {tool.id: is_installed(tool) for tool in self._catalog}
        self._browser.reload(self._adapter())
        self._start_version_refresh()
```

`is_installed` is a filesystem probe; if that is too costly on the event loop, route it
through the existing thread-worker + `post_message` shape already used by
`_refresh_versions_worker`. Add a test that stages a tool, completes a run, and asserts
the rendered `"sel"` cell is unticked and the installed column updated.

### WR-03: Escaping the confirm screen silently discards the whole staged selection

**File:** `installer/execute_screen.py:541-549`, `installer/wizard_app.py:1816-1819`

**Issue:** `ExecuteScreen` doubles as the confirmation step — its head renders
`"Install N tools? enter start · esc cancel"` (`execute_screen.py:354`). Pressing
`esc` before starting takes `action_close`'s `not self.started` branch and calls
`self.dismiss()`, which invokes `_install_closed` and wipes `self._staged`. The label
says "cancel", the user reads it as "go back", and the selection they just spent time
building is gone with no confirmation and no undo. `_install_closed` cannot tell a
"backed out before starting" dismissal from a "run completed" dismissal because both
call the same zero-argument `dismiss()`.

**Fix:** Carry the outcome in the dismiss value and only clear on a real run.

```python
class ExecuteScreen(ModalScreen[bool]):   # True == a run actually happened
    ...
    def action_close(self) -> None:
        if self.finished:
            self.dismiss(True)
            return
        if not self.started:
            self.dismiss(False)
            return
        self.status.set(...)
```

```python
    def _install_closed(self, ran: bool | None) -> None:
        if ran:
            self._staged.clear()
            ...  # WR-02's refresh
```

### WR-04: The first-run link-mode pick leaves the Doctor's fix preview describing the old mode

**File:** `installer/wizard_app.py:1781-1810`, `installer/wizard_app.py:304-311`, `setup.py:747-758`

**Issue:** `make fix` on a fresh machine calls `_build_app(..., initial_view="doctor",
prompt_link_mode=needs_choice)` (`setup.py:748-757`). `UnifiedApp.on_mount` awaits
`show_view("doctor")` — which mounts `DoctorScreen` and runs `_refresh_body()`, rendering
`self._fix_preview()` for the *pre-pick* mode — and only then pushes `LinkModeScreen`
(`wizard_app.py:1643-1656`). `_first_link_mode_picked` (`wizard_app.py:1781-1810`)
persists the new mode and writes a status line, but never re-renders the target screen.

Phase 13 deliberately turned `preview` into a callable so it could be re-read
(`setup.py:602-610`), and `_apply_fix` re-reads `_current_link_mode()`
(`setup.py:~596`) — but the one screen showing that preview is not told to ask again.
Result: the body still says e.g. `"Will wire the managed bin dirs into
/home/u/.zshrc, /home/u/.bashrc (mode: centralized)"` while pressing `enter`
applies `single` and writes only `~/.zshrc`. Preview and apply disagree on exactly the
first run the picker exists to serve.

The equivalent path from the Policies view is correct — `show_view` calls
`DoctorScreen.enter_view()`, which re-runs `_refresh_body()` (`wizard_app.py:270-273`)
— so this is a gap only in the first-run seam, and no test covers it.

**Fix:** Refresh the target after a successful save.

```python
        target.status.set(f"Link mode saved: {value}.", "ok")
        doctor = self._views.get("doctor")
        if isinstance(doctor, DoctorScreen) and doctor.is_mounted:
            doctor._refresh_body()
        policies = self._views.get("policies")
        if isinstance(policies, PoliciesScreen) and policies.is_mounted:
            policies._refresh_link_mode_line()
```

Better: give `AppScreen` a `link_mode_changed()` no-op hook, override it in the two
screens that render the mode, and call it here — that keeps the refresh on the public
seam instead of reaching into private methods.

### WR-05: Changing link mode mid-session does not re-wire policies that are already applied

**File:** `installer/policy.py:228-270,326-365`, `installer/wizard_app.py:1325-1340`, `.claude/architecture.md` ("nothing sources")

**Issue:** `ban_policy`/`tweak_policy` now re-read their rc targets **at apply time**,
and `architecture.md` records why: "A ban enabled after switching to split mode would
otherwise write aliases into a `~/.myshellrc` nothing sources." That closes one
ordering. Phase 13 opens the mirror-image ordering and leaves it open:

1. User enables the pip/npm ban in `centralized` mode → aliases written to
   `~/.myshellrc`.
2. User presses `m` on the *same screen* and switches to `split`.
3. `_link_mode_picked` (`wizard_app.py:1325-1340`) saves the mode, updates
   `#link-mode-line`, and reports `"Link mode saved: split."` in the **ok** style.
4. Nothing re-applies the ban. Split mode never sources `~/.myshellrc`, so the ban
   silently stops working — the exact "silent no-op the user has no way to notice"
   that both `policy.py` docstrings name as the hazard. The Policies table still
   renders the row as `● [on]`.

The same holds for every enabled `tweak:*` (its `ensure_source` wiring) and for the
managed PATH block itself, which the user must separately remember to re-apply from the
Doctor view. The picker is *on the Policies screen*, so this ordering is at least as
likely as the one that was fixed.

**Fix:** At minimum, make the cost visible rather than reporting an unqualified success:

```python
        self.status.set(
            f"Link mode saved: {value}. Re-apply any enabled policy (space) and the "
            f"PATH wiring (Doctor, enter) so they land in the files {value} mode sources.",
            "warn",
        )
```

The stronger fix is to re-apply the active policies through `run_live` on mode change
(they are documented as idempotent and reversible), reporting per-policy outcomes —
but if that is deliberately deferred, record it under `Residual scope` in
`13-VALIDATION.md`, which currently does not mention it.

### WR-06: `load_settings` crashes on a non-UTF-8 settings file, and reads with a different encoding than it writes

**File:** `installer/settings.py:44-65`

**Issue:** The module docstring is emphatic: "`load_settings` has two outcomes and only
two. Missing or JSON null ... Present but not a `LINK_MODES` member is a defect
(tampered or hand-edited) and also returns `Settings()`." There is a third outcome. The
guard is `except (OSError, json.JSONDecodeError)`; `path.read_text()` on a file with
invalid bytes for the active encoding raises `UnicodeDecodeError`, which is a
`ValueError` but **not** a `JSONDecodeError`, so it escapes. `_settings_store` is called
on the very first line of every entry point (`setup.py:714-719`), so a corrupted or
truncated `~/.local/state/tools-installer/settings.json` is an unhandled traceback
before the wizard, doctor, fix, uninstall, guard, and policies flows can start — for a
file whose only purpose is caching one of three ASCII words.

Compounding it: `save_settings` -> `atomic_write_text` encodes UTF-8
(`atomic.py:56-58`), while `load_settings` calls `path.read_text()` with **no
`encoding=`**, which uses `locale.getpreferredencoding()`. Under `LANG=C` / POSIX these
differ. The pairing is inconsistent by construction even though today's payload happens
to be ASCII.

**Fix:**

```python
    try:
        raw_decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return Settings()
```

Add a test writing `path.write_bytes(b'{"link_mode": "\xff\xfe"}')` and asserting
`load_settings(path) == Settings()`. `installer/version_cache.py:128-129,140-141`
carries the same two defects and, since `settings.py` is explicitly modelled on it,
both should be fixed together.

## Info

### IN-01: `StreamingRunner` leaks the child's stdout fd if the drain raises

**File:** `installer/run.py:168-175`

**Issue:** In the `finally`, `for _ in stdout: pass` and `stdout.close()` share one
`try`. If the drain raises `OSError` (EIO on a vanished pty, for example), `close()`
is skipped and the pipe fd leaks for the life of the process — across a whole catalog
install, once per affected tool.

**Fix:** Put the close in its own `finally`:

```python
            try:
                if stdout is not None:
                    try:
                        for _ in stdout:
                            pass
                    finally:
                        stdout.close()
            except OSError:
                pass
```

### IN-02: `SettingsStore.__init__` accepts any string while `set_link_mode` rejects one

**File:** `installer/settings.py:100-116`

**Issue:** `set_link_mode` validates against `LINK_MODES` and raises — the module
docstring calls that check "the mitigation for a tampered or hand-edited state file".
The constructor does no such check, and `resolve_link_mode` returns `flag` verbatim
without validating it either (`settings.py:74-83`). Today the only caller is
`_settings_store`, and `argparse` pins `--link-mode` to `choices=[...]`
(`cli.py:53-58`), which is itself pinned by
`tests/test_settings.py::test_link_modes_match_cli_choices_both_ways` — so it is not
currently exploitable. It is a one-line change away from being so, in a value that
selects which rc files get written.

**Fix:** Validate once in the constructor and delegate:

```python
    def __init__(self, path: Path, *, link_mode: str) -> None:
        if link_mode not in LINK_MODES:
            raise ValueError(f"rejected link_mode {link_mode!r}")
        ...
```

### IN-03: `_render_captured` hard-codes an 80-column console

**File:** `installer/execute_screen.py:561-564`

**Issue:** The magic `width=80` wraps the head, the audit, and the whole post-run report
at 80 columns regardless of the terminal, so a wide terminal shows an artificially
narrow report and a narrow one still double-wraps.

**Fix:** Name the constant and prefer the real width where available, e.g.
`width=max(40, self.size.width - 4)` with a documented fallback for the unmounted case.

### IN-04: The confirm prompt and the key hint duplicate the key legend in different words

**File:** `installer/execute_screen.py:62-66,354`

**Issue:** `_EXECUTE_KEYS` and the literal `"Install {n} tools? enter start · esc cancel"`
both describe the same keys. They already differ (`_EXECUTE_KEYS` says esc "does not
leave or stop during a run"), and a change to one will not propagate.

**Fix:** Derive the confirm line from a shared constant, or drop the trailing key hint
from the head now that `#execute-keys` carries it.

### IN-05: `pending` and `skipped` render identically in the progress list

**File:** `installer/execute_screen.py:72-77`

**Issue:** Both map to `("○", "dim", ...)`; only the bracketed label differs
(`[pending]` vs `[not attempted]`). After a weak cancel, a glance at the column cannot
distinguish "still queued" from "never attempted".

**Fix:** Give `skipped` its own glyph (e.g. `"–"`) so the state is legible without
reading the label.

### IN-06: `"centralized"` is hard-coded instead of `DEFAULT_LINK_MODE`

**File:** `installer/wizard_app.py:1795`

**Issue:** `mode = self._read_link_mode() if self._read_link_mode is not None else
"centralized"` duplicates `settings.DEFAULT_LINK_MODE`. Changing the default would
leave this branch reporting the old one to the user.

**Fix:** Import and use `DEFAULT_LINK_MODE`.

### IN-07: `enter` during a live run is silently inert

**File:** `installer/execute_screen.py:360-368`

**Issue:** `action_start` returns with no feedback when `self.started and not
self.finished`. The footer advertises `enter start`, so a mid-run press reads as a
broken binding — the same reasoning `PoliciesScreen.action_reinstall_globals` already
applies to `r` (`wizard_app.py:418-421`).

**Fix:** Set a status line, e.g. `"Already running — c stops after the current tool."`

### IN-08: The run log is unbounded

**File:** `installer/execute_screen.py:328-333`

**Issue:** `RichLog` is created without `max_lines`. A verbose installer (Rust
toolchain, Puppeteer) can emit tens of thousands of lines, all retained for the life of
the app since `ExecuteScreen` stays mounted until dismissed.

**Fix:** `RichLog(..., max_lines=5000)` — the failure detail is already bounded
separately by `STREAM_DETAIL_LINES`, so nothing diagnostic is lost.

### IN-09: The Policies footer advertises `m` even when link mode is unwired

**File:** `installer/ui_common.py:167`, `installer/wizard_app.py:1316-1322`

**Issue:** `VIEWS` now declares `actions="space toggle | m link mode"` unconditionally.
When `PolicyInputs.set_link_mode` is `None` (the dataclass default, and every
`UnifiedApp` construction outside `setup.py`), `#link-mode-line` renders empty and `m`
answers `"Link mode cannot be changed from this entry point."` — an advertised key that
only explains why it does nothing.

**Fix:** Not reachable from any production entry point today, so low priority; if the
default is kept, note in the `PolicyInputs` docstring that the footer over-advertises.

### IN-10: `isinstance` container dispatch in `policy.py` fails loudly on a plausible wrong type

**File:** `installer/policy.py:234-240,331-337`

**Issue:** `ban_policy` branches on `isinstance(apply_rc_paths, list)` and
`tweak_policy` on `isinstance(ensure_sourced_from, tuple)`, treating anything else as a
zero-argument callable. Passing a `tuple` for `apply_rc_paths` (or a `list` for
`ensure_sourced_from`) — the obvious mistake, and a distinction pyright enforces but
runtime callers may not — is accepted at construction and raises
`TypeError: 'tuple' object is not callable` later, inside `_apply`, in the middle of a
live mutation.

**Fix:** Dispatch on `callable(...)` instead, which is the property actually being
tested:

```python
    read_apply_rc_paths = apply_rc_paths if callable(apply_rc_paths) else (lambda: list(apply_rc_paths))
```

---

_Reviewed: 2026-09-14T09:25:54Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
