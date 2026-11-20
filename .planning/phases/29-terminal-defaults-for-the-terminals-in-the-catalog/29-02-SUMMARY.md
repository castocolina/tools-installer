# Phase 29 Plan 02 Summary

## Tasks

- **Task 1 — `ac6c2b59`** (`feat(29-02): kitty keys region with the shared clear, word moves and same-directory tabs`)
  - RED: test collection failed because `kitty_chord` did not exist; existing tests importing the shared test module failed as a consequence.
  - GREEN: targeted suite passed; kitty-specific selection passed (`8 passed`). Commit hook: all six static gates passed.
- **Task 2 — `ba15ff18`** (`feat(29-02): kitty keys follow plain includes and refuse clear_all_shortcuts`)
  - RED: after correcting literal-newline fixtures, the option-and-sequence case failed because option parsing advanced past the chord.
  - GREEN: Task 2 targeted suite passed; include/refusal selection passed (`15 passed`). Commit hook: all six static gates passed.
- **Task 3 — `91df65c3`** (`feat(29-02): kitty installs on macOS only through the cask into ~/Applications`)
  - RED: three registry tests showed the macOS script method still resolved, including on macOS without Homebrew and below macOS 12.
  - GREEN: registry/resolve/ownership/model tests passed; kitty selection passed (`8 passed`). Commit hook: all six static gates passed.

**Follow-up — `de2002d3`** (`fix(29-02): report kitty include scan limitations`): a regression test first failed because scan reports were not returned by the installer; the fix propagated those reports. Its targeted tests passed, and all six commit-hook gates passed.

## Kitty load_config check

Both platform configs were generated without refusal. kitty verified the expected effective map actions and `macos_option_as_alt` value.

```text
fedora None (kitty keys summary, displaced-default note, reload note, same-directory note)
macos None (kitty keys summary, displaced-default note, reload note, same-directory note)
KITTY_LOAD_OK
EXIT_STATUS=0
```

The temporary check directory was removed.

## Final verification

- `make validate`: exit 0; lint, format, typecheck, security, dead-code, and shellcheck passed.
- `make test`: exit 0; **7991 passed, 6 skipped**, 96.26% coverage.

## Decisions and flags

- 28 D-06: hosts with kitty installed but no tuning record read `≈ apply install tuning` until reconfigure. A recorded install that later gains `clear_all_shortcuts yes` stays quiet on reconfigure and status, with no rewrite. **Provisional; needs owner confirmation.**
- 29 D-09 Konsole report-only decision: **provisional; needs owner confirmation.**
- Kitty’s macOS script route was removed. **macOS older than 12 or without Homebrew now has no kitty method.**

## Existing test edits

- `tests/test_terminal_keys.py:164, 222` — completeness pins now include kitty’s new row/declarer.
- `tests/test_registry.py:1361-1362, 1369` — document and allow kitty’s reviewed tuning declaration.
- `tests/test_registry.py:1544, 1620-1621` — expect the cask-only macOS route and no method on macOS 11.
- `tests/test_registry.py:2582-2601` — replace the old `/Applications` script test with cask-only/no-system-location assertions.
- `tests/test_registry.py:2690` — remove lifecycle data for the deleted macOS script method.

## Orchestrator verification

Checked 2026-11-20 15:35 by the orchestrator, independently of the executor's report (pi, router-env/my-coding-lite, 15:09:58 to 15:29:35, exit 0).

- Commits since `0f79f0d6`: `ac6c2b59`, `ba15ff18`, `91df65c3`, `de2002d3`; each passed the commit hook.
- Plan verifies 1-6 re-run by the orchestrator (`run_plan_verifies.py 29-02`): all exit 0.
- Production diff read: kitty region at the top of `kitty.conf` with per-OS map lines, `kitty_config_path` following kitty's lookup order, bounded include scan with partial notes, `clear_all_shortcuts yes` refusal, cask-only macOS install; the row sets `bind_created_path=True`, and the generic bound-path test covers the drift case.
- Test edits read: only the listed exceptions (completeness pins, kitty registry tests, the lifecycle data of the removed script method).
- Known limits (accepted at plan review): a kitty region moved below an unscanned include stays where it is; a huge matched directory is read in full before the glob cap applies.
- `make validate` and `make test` run again once at the end of the phase.

## Deviations and limitations

- Added the follow-up commit to ensure include-scan reports reach installer output; the regression test demonstrated the gap.
- The requested final fresh-context review could not be completed: the available review subagent failed to start because no unambiguous authenticated reviewer model was available.
- Resolver tests are not exhaustive against every precedence/read-only case in the plan. No GUI, container, or live terminal checks were run.
