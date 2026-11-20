---
phase: 29-terminal-defaults-for-the-terminals-in-the-catalog
reviewed: 2026-11-20T00:00:00Z
depth: deep
files_reviewed: 14
files_reviewed_list:
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/registry.toml
  - installer/terminal_keys.py
  - installer/terminal_regions.py
  - installer/terminal_shell.py
  - scripts/container-e2e-verify.sh
  - tests/conftest.py
  - tests/e2e_herdr_keys_driver.py
  - tests/test_container_e2e_herdr_keys.py
  - tests/test_registry.py
  - tests/test_shell_scripts_path.py
  - tests/test_terminal_keys.py
  - tests/test_terminal_shell.py
  - tests/test_tool_onboarding_skill.py
findings:
  critical: 0
  warning: 5
  info: 6
  total: 11
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-11-20
**Depth:** deep (cross-file: call chains from `post_install` / `app` / `version_status` into `terminal_keys` and `terminal_regions`)
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Diff range `9adc1bb0..HEAD`. I read every changed file in full, traced the keys row through apply, status (`terminal_keys_pending`) and strip, ran the generated WezTerm Lua guard under Lua 5.4 and LuaJIT with a stub `wezterm` module (user keys with `CMD|SHIFT`, `OPT`, `META`, nil `mods`, trailing `|` were all treated as the same chord and kept), exercised kitty and WezTerm apply/strip in scratch homes under `/tmp` (CRLF files, no trailing newline, a created file, a shell region added later, a `KITTY_CONFIG_DIRECTORY` change before removal), and compared the kitty scan with kitty v0.49.2's own parser (`kitty/conf/utils.py`, `kitty/options/utils.py`, `tools/utils/paths.go`, fetched from GitHub). I ran `tests/test_container_e2e_herdr_keys.py tests/test_shell_scripts_path.py tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_tool_onboarding_skill.py`: all pass. No wezterm, kitty or container was launched, and nothing under the real home was touched.

Result: no data-loss or corruption bug found. Created-file deletion is correctly bound to the recorded path (sidecar), strip leaves user bytes identical in every scratch scenario, the owned-region replace/strip is exact-line based, the kitty config resolver matches kitty's Go source, and the container target removes only its own PID-named container and its own pulled image and never prunes. The defects are in the herdr byte-proof's diagnosis and verdict boundary (the evidence for D-10), in the kitty scan's fidelity to kitty's parser (false `partial:`-less reports and false displaced-default notes), an uncaught non-`OSError` in the scan, and test gaps that let the Konsole unknown-vs-stock distinction regress unnoticed.

Necessity review was not performed (`necessity-review.md` was not loaded for this run); no `necessity:` count is emitted.

Not flagged per the instructions: 28 D-06 and 29 D-09 as decisions, an already-moved WezTerm shell region or kitty keys region, and the glob listing a matched directory in full before the cap.

## Warnings

### WR-01: herdr byte-proof attributes bytes to the wrong chord as soon as one chord is lost or re-encoded

**File:** `tests/e2e_herdr_keys_driver.py:75-84` (`received_per_chord`), consumed at `:239-244`
**Issue:** The log is joined into one hex stream and sliced by the cumulative length of the *expected* strings. One swallowed chord shifts every later slice, so chords that herdr passed correctly are reported as failures with garbage "received" values. The docstring admits "lost/re-encoded bytes shift later slices", but `herdr_keys_verdict` and the test `test_herdr_keys_verdict_names_each_missing_chord` claim a per-chord diagnosis, and the verdict is the recorded proof for 29 D-10 (herdr passes the chords through).
Reproduced: with `alt+b raw` swallowed and the other seven chords delivered, the verdict is
`TRACER_HERDR_KEYS_FAILED detail=alt+b raw sent 1b62 received 1b66; alt+f raw sent 1b66 received 1b5b; alt+left ... received 313b33441b5b; ... ctrl+l csi-u sent 1b5b3130383b3575 received nothing`.
All eight chords are named as failing and seven of them are wrong. The overall FAILED is right, the attribution is not, so a maintainer reading it cannot tell which chord herdr intercepts.
**Fix:** Attribute by observation window, not by expected length. The send loop in `_keys` already waits per chord: after each wait, snapshot `len(log_lines)` (or have the recorder prefix every line with `time.monotonic()` and slice by send timestamps), then build `received[i] = "".join(lines[snap[i-1]:snap[i]])`. Keep the slicing function pure and change its test to feed per-chord line offsets, including a lost-chord case that must leave the other chords intact.

### WR-02: UNPROVEN vs FAILED boundary is wrong when the pane starts late or the client dies mid-run

**File:** `tests/e2e_herdr_keys_driver.py:87-101` (`herdr_keys_verdict`), `:160-186` (`_keys`), pinned by `tests/test_container_e2e_herdr_keys.py:164-166`
**Issue:** Two scenarios turn an environment problem into a product FAILED verdict:
1. `_keys` sleeps a fixed `STARTUP_SECONDS = 12.0` and then sends chords without checking that the recorder wrote `START`. If the pane's shell starts after the 12 seconds (slow dnf-cold container, first-run herdr), the early chords go to a recorder that is not yet in raw mode and are lost; `START` appears during the chord loop, so `started` is True and the verdict is `TRACER_HERDR_KEYS_FAILED ... received nothing` for the first chords. That claims herdr swallowed them, which is exactly the claim D-10 exists to disprove.
2. `closed` (client EOF/EIO) is only used when `started` is False. If the herdr client exits after `START`, the remaining chords read "nothing" and the verdict is FAILED, blaming pass-through. The test at lines 164-166 asserts this on purpose.
**Fix:** Gate the sends on `START`: poll `rec.log` up to a deadline (for example 60 s) and, if it never appears, return UNPROVEN before sending anything. When `closed is not None` at any point after `START`, return UNPROVEN with the close reason unless every chord was already received. Update the test at 164-166 to expect `_UNPROVEN` for a partial list with `closed="EOF"`.

### WR-03: kitty include/map scan diverges from kitty's own parser, so conflicts go unreported and displaced-default notes are false

**File:** `installer/terminal_regions.py:307` (`value_options`), `:333` (`tokens[1]` path), `:277-296` (`kitty_chord` key aliases)
**Issue:** Compared with kitty v0.49.2 (`kitty/options/utils.py parse_options_for_map`, `kitty/conf/utils.py parse_line`):
- Every `--option` in `KeyMapOptions` takes a value as the next token unless written `--option=value`. The scan only knows five of them and omits `--allow-fallback` and `--timeout`. `map --allow-fallback shifted,ascii ctrl+shift+k kill_window` makes the scan record the chord `shifted,ascii` (reproduced: `taken == {'shifted,ascii'}`).
- kitty resolves key aliases (`RETURN` to `ENTER`, `ESC`, `PGUP`, and so on); `kitty_chord` does not, so `ctrl+shift+return` does not match the installer's `kitty_mod+enter`.
- `include` takes the whole remainder of the line (`val.strip()`); the scan uses `tokens[1]`, so a path with a space (`~/Library/Application Support/...`) is silently skipped (FileNotFound is swallowed, no report).
Reproduced end to end in a scratch home with `map --allow-fallback shifted,ascii ctrl+shift+k kill_window` and `map ctrl+shift+return launch`: `apply_terminal_keys` returns no `partial:` line at all and adds the note "ctrl+shift+k now clears the screen and scrollback; it was scroll_line_up" and the "replace new_window" note, both false for those chords. The user's own binding still wins because the region sits at the top and kitty is last-wins, so this is not data loss; it breaks the contract that a user binding is reported as `kitty: partial: you already map ...` and that notes name the real displaced default.
**Fix:** Mirror kitty's tokenizer: after `map`, consume `--name[=value]` tokens, taking the next token as the value when there is no `=` and the (underscored) name is in `{when_focus_on, new_mode, mode, on_unknown, on_action, timeout, allow_fallback}`; normalize key aliases for at least `return`->`enter`, `esc`->`escape`; for `include`/`globinclude` use `line.split(None, 1)[1].strip()` as the path. Add golden cases for the space-form option, `return`, and an include path with a space.

### WR-04: a symlink loop in an `include` raises `RuntimeError`, which `apply_terminal_keys` does not catch

**File:** `installer/terminal_regions.py:303` (`path.resolve()`), `:348` (`Path(target_name).resolve()`)
**Issue:** On the project's Python 3.12, `Path.resolve()` raises `RuntimeError("Symlink loop ...")`, not `OSError`. Reproduced with `include a` where `a` and `b` symlink to each other (and with `globinclude a*`): `scan_kitty` raises `RuntimeError`. `apply_terminal_keys` only catches `OSError`, so the exception escapes to `run_post_install`, which reports `apply_terminal_tuning crashed: Symlink loop ...` and skips all kitty keys for that install; the status path survives only because `_terminal_tuning_fact` catches `Exception`. A dotfiles setup with a stale loop turns into a crash instead of the planned `could not be read` report.
**Fix:** Use `os.path.realpath` (never raises on loops) or wrap both `resolve()` calls in `try/except (OSError, RuntimeError, ValueError)` and treat the target as unreadable (`kitty: partial: <name> could not be read; maps there are not checked`). Add a loop test next to `test_kitty_unreadable_include_is_reported`.

### WR-05: the Konsole "unknown" state is not protected by any test; the matching tests would pass if unknown became stock

**File:** `tests/test_terminal_shell.py:1763-1780` (`test_konsole_unreadable_sessionui_is_unknown_and_reports_nothing`), `:1872-1884` (`test_konsole_unreadable_sessionui_has_no_stock_note`)
**Issue:** The first test only asserts that no `konsole: partial:` warning appears and the bytes are unchanged; it never asserts `result.notes == ()`. The second test does assert `notes == ()`, but its fixture is `b"\\xff\\n"`, which is the ASCII text `\xff\n` (escaped backslashes), not undecodable bytes, so it passes through the `"<gui" not in text` branch, not the `UnicodeDecodeError` branch. Mutation check by reading: change `_konsole_clear_state` to `except UnicodeDecodeError: return "stock"` (or return stock for the directory and truncated cases) and every test still passes, although the plan review (29-REVIEWS, MEDIUM "Unreadable becomes an affirmative stock claim") exists precisely to prevent that: the installer would then print "Ctrl+Shift+K is Konsole's stock ... left as it is" about a file it could not read.
**Fix:** In the loop test assert `result.notes == ()` for each of the three cases (invalid UTF-8, directory in place of the file, truncated file). Change the literal to real bytes (`b"\xff\n"`) in the second test, or delete the duplicate. Same for `b"x\\n"` at the parent-is-a-file test (harmless there, but the same typo).

## Info

### IN-01: a Konsole removal is routed to the zsh row as `MISCONFIGURED` with no step (planned, but unfixable by the user's installer action)

**File:** `installer/terminal_shell.py:753` feeding `installer/version_status.py:1601-1607`
**Issue:** `_terminal_facts` turns every `<terminal>: partial:` warning into `_ConfigFacts((warning,))`, whose first field is `misconfigured`, and `_TERMINAL_ROWS["konsole"]` is the `zsh` row. While `konsole` is on PATH and `sessionui.rc` lacks Ctrl+Shift+K, the zsh row reads `≈ needs configuration` on every refresh, with no step to clear it. This is the planned routing (29-04-PLAN T-29-16) and it matches Alacritty's partial lines, so it is not a defect against D-09; I flag it because here the "misconfiguration" is a deliberate user choice on another app and lands on a different tool's row.
**Fix:** Confirm it is wanted; if not, send the Konsole removal through `ConfigFacts.unchecked` (a note) instead, or give it its own prefix that `_terminal_facts` treats as a note.

### IN-02: `print("\\n".join(lines))` joins with a literal backslash-n

**File:** `tests/e2e_herdr_keys_driver.py:236`
**Issue:** `"\\n"` is two characters. Each handler returns exactly one line today, so output is correct, but a second line would print as `A\nB` on one line and the harness' `_FAILED`/`_UNPROVEN` grep would still match while the transcript is garbled.
**Fix:** `print("\n".join(lines))`.

### IN-03: kitty region at the top pushes a user's modeline out of the first lines

**File:** `installer/terminal_regions.py:214-215` (`Placement.TOP`)
**Issue:** kitty's stock `kitty.conf` starts with `# vim:fileencoding=utf-8:ft=conf:foldmethod=marker`. The 11-line region now sits above it, and vim only honors modelines in the first and last five lines, so a user's folding and filetype stop applying. Cosmetic; the top placement itself is required by D-01.
**Fix:** When the first line of the file starts with `# vim:`, insert the region after it (the scan and last-wins are unaffected). Or mention it in the install note.

### IN-04: generic region helper and strip are coupled to WezTerm by placement

**File:** `installer/terminal_regions.py:216-223`, `installer/terminal_keys.py:455`, `:401-412`
**Issue:** `Placement.BEFORE_RETURN` makes the generic `replace_owned_region` substitute `WEZTERM_SKELETON` for empty content, and `strip_terminal_keys` selects the WezTerm seed with `row.ownership.placement is Placement.BEFORE_RETURN`, so a second `BEFORE_RETURN` row would delete a created file that equals the WezTerm skeleton only. `terminal_keys_pending` also calls `replace_owned_region(...)` and discards the result purely to provoke the "unsupported return shape" exception, which hides intent.
**Fix:** Give `OwnedRegion` an explicit `seed: str = ""` (used by both the empty-content case and the delete check) and replace the discarded call with a named `check_placement(text, row)` helper.

### IN-05: tests with weak or duplicated bodies

**File:** `tests/test_terminal_keys.py:491`, `:538-542`, `:1007-1008`
**Issue:** `config.write_text("geninclude generated.conf\\n")` writes a literal backslash-n (no newline); it passes only because the directive is the first token. `test_kitty_include_cycle_terminates` also passes with the `visited` set deleted, because the depth cap ends the recursion and `taken` is empty either way. `test_wezterm_fresh_install_after_a_user_config_keys_assignment_is_written` just calls another test function.
**Fix:** Use `"\n"`; assert `reports == ()` (no depth cap hit) in the cycle test so only `visited` can satisfy it; delete the pass-through test.

### IN-06: herdr driver leaves its scratch directory and continues in the child if `execve` fails

**File:** `tests/e2e_herdr_keys_driver.py:118`, `:142`
**Issue:** `tempfile.mkdtemp(prefix="hk", dir="/tmp")` is never removed; it dies with the disposable container, but the project rule is cleanup on every exit path. If `os.execve` raises in the `pty.fork` child, the exception unwinds into the child's copy of `main`, which prints `ERROR` into the pty and exits 1 through the interpreter's normal path; the parent then reports UNPROVEN by EOF, which is right by accident.
**Fix:** `shutil.rmtree(home, ignore_errors=True)` in the `finally`, and wrap the child branch: `try: os.execve(...) finally: os._exit(127)`.

---

_Reviewed: 2026-11-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
