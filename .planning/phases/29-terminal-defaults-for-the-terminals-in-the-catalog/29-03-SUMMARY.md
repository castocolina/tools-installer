# Phase 29 Plan 03 Summary

## Commits

- `9b1cfa14` — `feat(29-03): WezTerm keys region extends config.keys before return config`
- `937cd3fd` — `feat(29-03): WezTerm keys read back the effective bindings and report the ones you kept`

## Test evidence

- **RED:** Task 1’s targeted tests initially failed because the WezTerm helpers were missing. Task 2’s focused read-back tests also failed before the parser and reporting fixes.
- **GREEN:** Task 2’s focused tests passed: `13 passed`.
- The specified broader Task 2 test set passed.
- The isolated live WezTerm check passed three cases: Linux user-binding conflict, macOS user-binding conflict, and macOS installer bindings. Output included `WEZTERM_LIVE_OK`.
- Final `make validate`: **passed**.
- Final `make test`: **8,020 passed, 6 skipped**; total coverage **96.27%**.

## Provisional decisions

- **28 D-06 drift rule:** provisional; owner confirmation remains pending.
- **29 D-07 `Vendor` cwd declaration:** provisional; owner confirmation remains pending orchestrator verification.

## Deviations and cleanup

- No plan deviations reported. The pre-existing untracked planning file was left untouched. Test and live-check scratch directories were cleaned up.
- Skipped the orchestrator-only cwd verification; live check covered WezTerm key read-back behavior, not GUI cwd behavior.

## Orchestrator verification

D-07 cwd check: PASS (2026-11-20, SpawnTab and SpawnWindow performed through perform_action)

- Run by the orchestrator in a disposable Fedora 44 container `tools-installer-d07-<pid>` (removed by exact name; no prune or reset): Xvfb `:99`, wezterm 20240203-110809-5046fc22 (the `fedora39` release rpm, sha256 `c0ca607b18b3790a4f3cd1c02886ae276960f4f9bc47b215b98a096ce25e53e7` checked against the release's `.sha256`), the reference config from the plan's `<context>` unchanged (`gui-startup` opens plain `/bin/sh` in `/known/dir`, no OSC 7; the one-shot `update-status` callback calls `window:perform_action` with `SpawnTab 'CurrentPaneDomain'` and `SpawnWindow`), scratch `HOME` and `XDG_RUNTIME_DIR`.
- Result file bytes: `tab /known/dir /known/dir\nwindow /known/dir /known/dir\n` (`cat -A` showed exactly the two expected lines). Each new pane reported `/known/dir` from `get_current_working_dir` and from its process cwd.
- The `Vendor` cwd declaration stands; plan 29-06 drops the unverified clause of its note.
- Plan verifies 1-4 re-run by the orchestrator (`run_plan_verifies.py 29-03`): all exit 0. Production diff read: wezterm Lua region before `return config`, `validate_wezterm` refusing a later plain `config.keys =`, `show-keys` read-back through the `wezterm_show_keys` seam (autouse fixture in `tests/conftest.py`), created-file cleanup bound to the recorded path.
- `make validate` and `make test` are re-run once at the end of the phase.
