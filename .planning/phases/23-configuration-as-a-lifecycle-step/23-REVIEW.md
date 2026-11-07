---
phase: 23
lanes: [deep, ponytail, external referee-two]
base: 97b9e0b
head: bb43f16
consolidated: 2026-11-07
sources:
  deep: 23-REVIEW-deep.md (CR-01..CR-15)
  ponytail: 23-REVIEW-ponytail.md (PT-01..PT-09)
  external: .review-diagnostics/20261107T080307Z-code-review/opencode-referee-two/lane.out (CR-01, CR-02 -> X-01, X-02)
findings:
  high: 3
  medium: 9
  low: 9
  total: 21
status: issues_found
---

# Phase 23: Consolidated code review

Three lanes reviewed `97b9e0b..bb43f16` (installer, setup.py, scripts, tests): the deep lane,
the ponytail lane, and the external referee-two lane (its CR-01 and CR-02 are X-01 and X-02
here). Duplicates are merged. Every HIGH and MEDIUM was re-checked against the source at
`bb43f16`. Where it was cheap, the check is a reproduction under a scratch HOME
(`uv run --no-sync python -I` in the session scratchpad) or a regression test that failed
first. The ledger's binding decisions are accepted design and are not findings. The
orchestrator's fix decisions for this loop are in 23-REVIEW-FIX.md.

## Table

| ID | Sev | Sources | Finding | Verdict |
|----|-----|---------|---------|---------|
| C-01 | HIGH | CR-01, PT-01 | Splice revert refused for good after a member is appended after ours | CONFIRMED |
| C-02 | HIGH | CR-02 | Revert, state and facts use the file resolved now, not the recorded one | CONFIRMED |
| C-03 | HIGH | X-01 | Post-run terminal sync writes ~/.zshenv and terminal regions with no report line | CONFIRMED |
| C-04 | MEDIUM | CR-03, PT-04 | An untrusted ledger is read as empty, then overwritten or deleted | CONFIRMED |
| C-05 | MEDIUM | CR-04 | Launch-time alias strip crashes on a non-UTF-8 or non-regular ~/.myshellrc | CONFIRMED |
| C-06 | MEDIUM | CR-05 | Shell section claims the export after a failed .zshenv write; it hard-codes ~/.zshenv | CONFIRMED |
| C-07 | MEDIUM | CR-06, PT-06 | New-host sweep skips hook tools whose receipt recorded no host | CONFIRMED |
| C-08 | MEDIUM | CR-07 | Hook sweep and settings writes run after Stop | CONFIRMED |
| C-09 | MEDIUM | CR-08, PT-03 | Policies starship on does not write `ZSH_THEME=""`; removing starship leaves a bare prompt | CONFIRMED |
| C-10 | MEDIUM | CR-09 | A full uninstall writes or creates the owned .zshenv block while zsh stays | CONFIRMED |
| C-11 | MEDIUM | X-02 | zsh removal strips kitty, WezTerm and Konsole after a .zshenv warning | CONFIRMED |
| C-12 | MEDIUM | PT-02 | JSONC block-comment regex spans two comments, so valid files are refused | CONFIRMED |
| C-13 | LOW | CR-10 | Receipt still lists hosts after a successful unregister when a later step fails | CONFIRMED (read) |
| C-14 | LOW | CR-11 | Hook-tool removal with no proven executable orphans its registrations silently | CONFIRMED (read), accepted shortcut |
| C-15 | LOW | CR-12 | Settings reads block on a FIFO (UI thread) and are uncapped | CONFIRMED (test hung) |
| C-16 | LOW | CR-13 | Container e2e hook probe passes when nothing was registered | CONFIRMED (read) |
| C-17 | LOW | CR-14 | Desktop SHELL row reports "removed" when nothing was removed | CONFIRMED (read) |
| C-18 | LOW | CR-15, PT-09 | Dead `platform_os` parameter and duplicate helpers | CONFIRMED (read) |
| C-19 | LOW | PT-05 | Revert can drop user comments the guard cannot see | CONFIRMED (read) |
| C-20 | LOW | PT-07 | Re-applying the installer's own theme is reported as the user's | CONFIRMED (read) |
| C-21 | LOW | PT-08 | 0-byte, BOM-prefixed and nested-array TOML settings files are refused | CONFIRMED (read) |

## Evidence (HIGH and MEDIUM)

### C-01: splice revert after an appended member (CR-01 = PT-01)

`remove_key` (agent_settings.py:369-392) cut the recorded fragment whenever it occurred once
and held the member, and had no fallback when the re-parse guard refused. Reproduced: with
VS Code lean on `{}`, appending `"workbench.colorTheme"` after the last member makes
`revert_setting("vscode", "vscode-lean")` return `refused="the edit broke the file"` with 0
keys reverted. The opencode `{}` + appended key and the Claude created-parent cases fail
the same way (regression test RED). One extra point: deleting the `stranded` case alone is
not enough. JSONC accepts a trailing comma, so the guard accepts a fragment cut that leaves
`false,}` (`test_vscode_ai_off_and_ext_updates_off_are_separate_settings` goes RED).

### C-02: revert by recorded path (CR-02)

`revert_setting` resolved `settings_file()` and `mine` kept only `entry.file == str(path)`.
RED tests:
- With opencode.jsonc created beside a written opencode.json, the revert refused with
  "both opencode.json and opencode.jsonc exist".
- After a json→jsonc rename, `setting_state` read `yours`.

### C-03: silent post-run sync (X-01)

`setup._sync_terminals` called `sync_terminal_shells(write=True)` from the CLI post-run
(`setup.py:1492`), the update follow-up (`:725`) and the interactive close
(`_sync_omz_terminals` → `UnifiedApp.terminal_sync`). It returned only warnings and reverts,
never what it wrote. The new route test is RED: a sync result that wrote .zshenv prints
nothing.

### C-04: untrusted ledger (CR-03 = PT-04)

Reproduced: apply claude auto-approve, set the ledger's `v` to 2, then apply
no-attribution. The ledger then holds only `attribution.commit` and `attribution.pr`, and
`bypassPermissions` became unrevertable.

### C-05: launch crash (CR-04)

`bundle_marker_present` read the file outside any handler. RED: `UnicodeDecodeError` from
`strip_legacy_aliases`, from `_build_app` (through `tweak_present` and then
`omz._record`), and from the headless route.

### C-06: Shell report (CR-05)

`_run_step` turned any synchronizer warning into a `warning` on a `done` row, and
`render_shell_section` printed on `done` alone. The step, the reason and the report
hard-coded `~/.zshenv` while `zshenv_path` honors `$ZDOTDIR`. RED: a `zshenv: Permission
denied` sync left the row `done`.

### C-07: zero-host receipts (CR-06 = PT-06)

`register_hooks` recorded nothing when it registered nothing, and `_resync_hooks` skipped
`not receipt.hooks.get(name)`. RED: a receipt with `{"codegraph-mcp-register": ()}` and
claude installed ran no register.

### C-08: Stop (CR-07)

`execute_plan` returned `_apply_run_options(_resync_hooks(...))` unconditionally. RED, in
both shapes: Stop before a later row, and Stop during the last row (should_continue is
false only after the loop).

### C-09: starship theme (CR-08 = PT-03 in part)

Only `post_install._source_shell_init` called `apply_theme(..., "")`. `tweak_policy._apply`
and `_remove` never touched the theme. RED:
- Policies on left `.zshrc` without `ZSH_THEME=""`.
- Off and removal left the installer's `""`.

### C-10: uninstall writes .zshenv (CR-09)

The CLI uninstall (`setup.py:1350`) and the interactive Uninstall (the
`UninstallInputs.terminal_sync` shared closure) ran the converging sync. RED: `--uninstall
--yes` with a system zsh created `~/.zshenv`.

### C-11: half-done zsh removal (X-02)

`_revert_terminal_shells` continued to kitty, WezTerm and Konsole after `_edit_zshenv`
returned a warning. RED: a non-UTF-8 `.zshenv` kept its block while the owned kitty region
was stripped.

### C-12: JSONC regex (PT-02)

Reproduced: `{"a": 1, /* c */ "b": 2 /* d */}` and a file ending with a commented-out
member both raise `not valid JSONC`.

## LOW notes

- **C-14:** this is planner sign-off 7 ("unproven hook exe not unregistered (shortcut)",
  R1-40). The gap left is the missing handoff line.
- **C-18:** two parts are kept by design:
  - `_first_line_of` takes text and `first_line` takes an exception.
  - `_HERDR_TARGETS` is herdr's own vendor contract, not codegraph's, even where the ids
    coincide.

_Consolidated by: Claude (gsd-code-fixer)_
