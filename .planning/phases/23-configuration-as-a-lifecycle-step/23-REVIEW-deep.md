---
phase: 23
lane: deep
base: 97b9e0b
head: 4085e79
reviewed: 2026-11-07T08:13:40Z
depth: deep
scope: "git diff 97b9e0b..4085e79 -- installer setup.py scripts tests"
findings:
  blocker: 0
  high: 2
  medium: 7
  low: 6
  total: 15
status: issues_found
---

# Phase 23: Deep Code Review (configuration as a lifecycle step)

**Scope:** 73 files changed between `97b9e0b` and `4085e79` under `installer/`, `setup.py`, `scripts/`
and `tests/`. Context read: 23-SPEC, 23-REVIEWS, 23-REUSE, the 23-*-SUMMARY deviations, and the
`| 23 |` RUN-LEDGER rows. The ledger's binding decisions are treated as accepted design and are not
reported as findings: launch-time alias strip, no opt-in for `.zshenv` or the OMZ theme, `""`
attribution strings, the marker-dir host rule, the unproven-executable shortcut, and the emptied
`.zshenv` that is kept.

**Method:** every finding below was checked against the source at `4085e79`. CR-01, CR-02, CR-03
and CR-04 were reproduced against the real modules in a scratch `HOME`
(`uv run --no-sync python -I`, the scratchpad only). A splice round-trip fuzz over 17 JSON and
JSONC shapes × 4 key paths × 2 formats found no byte-identity failure when the file is left
untouched. All the splice findings need a later edit to the file.

## Summary

The splice engine, the re-parse guard and the snapshot-checked write are solid. Untouched files
round-trip byte-identically, and the guard stops every corrupting edit I tried. The weak point
is **revert after the world moved on**:
- An ordinary later edit makes the fragment path refuse the revert for good (CR-01).
- The revert looks in the settings file it resolves now, not the file the ledger recorded
  (CR-02).
- An untrusted ledger is overwritten instead of being kept (CR-03).

In all three cases a dangerous key (`bypassPermissions`, `"permission": "allow"`, `approvalMode`
or the VS Code lean keys) stays after an opt-out or uninstall. Sometimes the screen then shows it
as `● [yours]`, and Policies refuses to remove it.

Secondary issues:
- A launch-time crash on an unreadable `~/.myshellrc`.
- A Shell report that claims success after the `.zshenv` write failed.
- The CONF-02 sweep skips hook tools that recorded no host.
- The post-run sweep ignores Stop.
- The OMZ theme claim is never reversed.
- A full uninstall rewrites the `.zshenv` block.

Test isolation is sound: HOME, the XDG and ZDOTDIR variables, the `setup.py` import-time paths,
host presence and the config ledger are all sandboxed, and the real-HOME fingerprint covers the
ledger and `environment.d`. I found no path by which the suite touches the real HOME.

---

### CR-01 — HIGH — The fragment revert path removes a substring at the wrong place; the guard then refuses the revert for good

**File:** `installer/agent_settings.py:383-392` (`remove_key`), called from `_revert_pass` `:713-723`

**Problem:** The recorded fragment is cut when two checks pass:
- `text.count(fragment) == 1`;
- `located in fragment` (a substring test on strings, not on positions).

Neither check proves that the fragment still covers the member's own punctuation. A member
inserted into an empty object has a fragment with no comma (`\n  "k": v`). If anything later adds
a member after it, the text becomes `\n  "k": v,\n  "x": …`. The fragment still occurs once, but
cutting it strands the comma (`{,\n  "x": …}`). `_guarded` raises `SettingsEditRefused`, and
there is no fallback to `_cut_member`, which would handle this case correctly. Every later revert
fails the same way. `_revert_pass` refuses the whole setting, so none of its keys are reverted.

**Failure scenario (reproduced):**
1. `~/.config/Code/User/settings.json` is `{}`, VS Code's default. Turn on VS Code lean mode: 14
   keys are written, and the first one inserted (`telemetry.telemetryLevel`) ends up as the last
   member.
2. VS Code's own settings editor (jsonc-parser) appends a new setting after the last member:
   `"telemetry.telemetryLevel": "off",\n "workbench.colorTheme": …`.
3. `revert_setting("vscode", "vscode-lean")` returns `refused="the edit broke the file"`, with 0
   keys reverted. `setting_state` still reads `on`.
4. The uninstall prints `could not revert … — the edit broke the file`, and all 14 keys stay.

The same happens with opencode (`{\n  "permission": "allow"}` after the user appends a key). It
also happens with a Claude settings file the installer created: the created-parent fragment
`"permissions": {"defaultMode": "bypassPermissions"}` with a user key after it.

**Fix:** Make the fragment path positional and give it a fallback:

```python
start = text.find(fragment)
use_fragment = (
    fragment is not None and text.count(fragment) == 1
    and start <= member.key_start and member.value_end <= start + len(fragment)
)
if use_fragment and not stranded:
    try:
        return _guarded(text.replace(fragment, "", 1), fmt, _edited(doc, key_path, ABSENT))
    except SettingsEditRefused:
        pass  # fall through to the located cut
return _guarded(_cut_member(text, clean, members, member), fmt, _edited(doc, key_path, ABSENT))
```

Add a regression test for each case: VS Code append after the last member, opencode, and the
Claude created parent.

### CR-02 — HIGH — Revert and state read the settings file resolved now, not the file the ledger recorded; the preview promises a removal that never happens

**File:**
- `installer/agent_settings.py:773-786` (`revert_setting` resolves `path = settings_file(...)`);
- `:738-747` (`mine` keeps only `entry.file == str(path)`);
- `:533-539` (opencode switches to `opencode.jsonc` once that file exists);
- `:889-898` (`ledger_summary` lists every ledgered file);
- `installer/app.py:650`, `:892`.

**Problem:**
- The ledger records the absolute file each key went into. The revert, the state and the facts
  instead look at whatever `settings_file()` resolves today, and drop every entry for any other
  file without a word.
- `ledger_summary`, which feeds the CLI preview, the TUI block 3b and the Uninstall
  "agent/editor settings" row, lists the recorded file.
- So the preview says `opencode: removes permission from ~/.config/opencode/opencode.json`, and
  the effect is a no-op.
- When both files exist, `_conflict` refuses every revert. Something else creating
  `opencode.jsonc` therefore freezes the keys in `opencode.json`. The 23-16 e2e shows codegraph's
  own registration writing `.config/opencode/opencode.jsonc`.

**Failure scenario (reproduced):**
1. Opt into opencode auto-approve: `opencode.json` gains `"permission": "allow"`.
2. The user renames `opencode.json` to `opencode.jsonc`, the usual step to add comments.
3. `setting_state` now returns `yours`. Policies shows `● [yours]` and refuses to remove it ("you
   set these keys yourself").
4. `revert_agent` returns a result with no keys and no refusal, and the file keeps
   `"permission": "allow"`.
5. `ledger_summary` still lists `opencode.json` after the revert, so every later uninstall
   preview repeats the false promise.

The key is a permission bypass, and it survives an uninstall that said it would remove it.

**Fix:**
- Drive revert from the ledger: group `mine` by `entry.file`, and revert each recorded file at
  its recorded path. `_conflict` gates only the apply direction.
- When a recorded file is gone, return a refusal that names it, so the caller can warn. Do not
  return a silent empty result.
- In `setting_facts`, classify entries against their own `entry.file`, so a written key never
  reads as `yours`.
- Add a test for the json-to-jsonc rename, and one for a both-files-present revert.

### CR-03 — MEDIUM — An untrusted ledger is treated as empty and then overwritten, orphaning every key it recorded

**File:** `installer/agent_settings.py:646`, `:655`, `:661`, `:667`; `installer/receipts.py:308-336`

**Problem:**
- `read_ledger` fails closed and returns None for a ledger it cannot trust: wrong `v`, a bad
  field, a symlink, or larger than the cap. That is right for reads.
- `_apply_once` then does `read_ledger(agent) or ConfigLedger(agent)` and writes the result back:
  - with no change, at `:655`, which deletes the file when the result is empty (`write_ledger`
    calls `unlink` at `receipts.py:336`);
  - when reserving, at `:661`;
  - when restoring, at `:667`.
- The recorded entries and `created_files` are destroyed. The keys they described stay in the
  settings file and now read as `yours` (CR-02 copy), which can never be reverted.

**Failure scenario (reproduced):**
1. Apply claude auto-approve.
2. Set the ledger's `"v"` to 2, as a newer or older installer build might.
3. Apply claude no-attribution.
4. The ledger now holds only the two attribution entries. `revert_agent` removes those, and
   `permissions.defaultMode: "bypassPermissions"` plus `skipDangerousModePermissionPrompt` stay
   for good.

**Fix:**
- Tell "missing" apart from "untrusted": add `ledger_exists(agent)` or return a sentinel.
- When the file exists but does not parse, refuse the apply with
  `"config ledger for claude is unreadable; nothing is written"` instead of rebuilding it, and
  surface it like O7.
- Never `unlink` a ledger that was not read successfully in the same call.

### CR-04 — MEDIUM — The launch-time legacy alias strip crashes the app on an unreadable or non-UTF-8 `~/.myshellrc`

**File:** `installer/tweaks.py:323-343` (`strip_legacy_aliases`, `bundle_marker_present`); called
unguarded at `setup.py:919` (`_build_app`, every TUI route), `:1325` (CLI uninstall) and `:1453`
(headless install).

**Problem:**
- `bundle_marker_present` calls `rc_path.read_text()` outside the `try`.
- Inside the `try`, only `OSError` is caught, and `strip_tweak_block`'s `read_text()` can raise
  `UnicodeDecodeError`, which is a `ValueError`.
- So a Latin-1 byte, a directory or a permission-denied `~/.myshellrc` raises out of `_build_app`
  or `main` before any screen opens.
- Before this phase, launching did not read this file unconditionally. The new strip runs at
  every launch, so one bad byte in a file users do edit locks them out of every route, uninstall
  included.

**Failure scenario (reproduced):** `~/.myshellrc` holds `# caf\xe9` plus a `claude-skip` block,
and `strip_legacy_aliases` raises `UnicodeDecodeError`. With `~/.myshellrc` as a directory, it
raises `IsADirectoryError`.

**Fix:** Read once, through the capped and checked reader that `terminal_shell._read_text` uses.
Treat any `OSError`/`UnicodeDecodeError` as one `failed` entry ("could not read …"), so it rides
`launch_lines()` as a warn and the launch goes on. Add the two cases above as tests.

### CR-05 — MEDIUM — The Shell section reports that `.zshenv` now exports SHELL even when the write failed

**File:**
- `installer/session.py:446-451` (`_run_step` for `zshenv_shell`: any synchronizer warning
  becomes `warning`, and the row still ends `done`);
- `installer/render.py:509-526` (`render_shell_section` prints on `result == "done"` plus the
  step kind alone).

**Problem:**
- `_edit_zshenv` turns a failed `.zshenv` write into a `zshenv: …` warning. It does not raise, by
  design (R1-21).
- The step therefore returns `_StepResult(warning="Terminal shell synchronization warning:
  zshenv: Permission denied")`, and the row ends `done`.
- `render_shell_section` then prints `~/.zshenv now exports SHELL; new terminals start with it.`
  and `SHELL=<zsh>`, a false success right next to the warning that contradicts it.
- The step label (`export SHELL=… in ~/.zshenv`), `_ZSHENV_DONE` and the report also hard-code
  `~/.zshenv`. `zshenv_path` writes `$ZDOTDIR/.zshenv` when ZDOTDIR is set, so the preview names
  the wrong file.

**Failure scenario:** `~/.zshenv` is read-only, or a dotfiles symlink into a read-only store. The
zsh row shows `≈`, RECONFIGURE runs, and the report shows both the warning and "now exports
SHELL", while the file is unchanged.

**Fix:**
- Have the synchronizer's result carry whether `zshenv` was configured (`"zshenv" in
  result.configured`).
- A `zshenv_shell` step whose sync carried a `zshenv:` warning returns `failed=`. At minimum,
  `render_shell_section` must skip outcomes whose detail has a `zshenv:` warning.
- Take the label path from `TerminalShellResult.paths["zshenv"]` through `display_path`.

### CR-06 — MEDIUM — The CONF-02 new-host sweep skips every hook tool whose receipt recorded no host

**File:** `installer/session.py:541-590` (`_resync_hooks`, the check `not receipt.hooks.get(name)`
at `:569`)

**Problem:**
- SPEC CONF-02 says: when a run installs an agent host, "the hooks of the already-installed hook
  tools run for the new host".
- The sweep skips any receipt with no `hooks[name]` entry, to leave pre-Phase-23 receipts to
  RECONFIGURE.
- `register_hooks` records nothing when it registered no host. So a codegraph installed while no
  agent host existed, or whose first registration failed, has the same empty `hooks`.
- It is never registered for the next host by any run. The new host only shows up as `≈`, which
  the user must notice and RECONFIGURE.

**Failure scenario:** Run 1 installs codegraph on a host with no agent host; it registers nothing
and records nothing. Run 2 installs claude. The report has no "registered for claude (new host)"
line, and codegraph is not in `~/.claude.json`.

**Fix:** Tell "pre-hooks receipt" apart from "hooks known, none registered". For example,
`register_hooks` records `hooks[name] = ()` (an empty tuple, which `_write_unlocked` already
serializes) whenever it ran with targets. The sweep then skips only receipts with no `name` key
at all. Add a test: codegraph receipt with `hooks={"codegraph-mcp-register": []}`, then claude
installed, then exactly one register for claude.

### CR-07 — MEDIUM — The post-run sweep runs vendor commands and settings writes after the user pressed Stop

**File:** `installer/session.py:749-753`, `:849` (`return _apply_run_options(_resync_hooks(outcomes,
ctx), ctx)`, called unconditionally)

**Problem:**
- Stop (`c`) promises "The current tool will finish and nothing further will start"
  (`execute_screen._CANCEL_ARMED`).
- `execute_plan` marks the remaining rows `not_attempted`, then still runs `_resync_hooks`, which
  launches `codegraph install --target …` for every hook tool, and `_apply_run_options`, which
  writes agent and VS Code settings and the environment.d conf.
- A crashed row (`halted = True` at `:838`) is treated the same.

**Failure scenario:** A plan installs claude and five other tools. The user presses `c` while the
third tool runs. After it finishes, the installer still runs `codegraph install` (a write to
`~/.claude.json` and `settings.json`) and the chosen settings writes, with output attributed to
the claude row.

**Fix:** Track `halted` in `execute_plan` and skip both sweeps when it is set, or skip only
`_resync_hooks` and record a "sweep skipped: run stopped" note. Add a test with
`should_continue` returning False after the host row.

### CR-08 — MEDIUM — The OMZ theme claim and its `ZSH_THEME` line are never reversed; removing starship leaves `ZSH_THEME=""` and no prompt

**File:** `installer/omz.py:506`, `:624-653` (`write_plugins` → `apply_theme`, `_record_theme`);
`installer/post_install.py:155`, `:172`; `installer/policy.py:836-839`

**Problem:**
- `apply_theme` writes `ZSH_THEME="robbyrussell"` (or `""` for starship) into the user's
  `.zshrc` and records a `# >>> tools-installer omz-theme >>>` claim block in `~/.myshellrc`.
- No production code ever clears that claim or reverts the line. `_clear_owned(…, THEME_BEGIN,
  THEME_END)` is reached only on a failed write. No test references the theme block on any
  removal path.
- `remove_plugins`, the omz-plugins Policies off, the full CLI and TUI uninstall, and starship's
  removal (`_after_removal` sweeps only the bundle) all leave both in place.
- With starship removed, `.zshrc` keeps `ZSH_THEME=""`, and the user is back at the bare `%m%# `
  prompt this phase set out to fix (SPEC background).
- The starship row's detail documents "turning it off leaves the theme line", but nothing
  documents the uninstall leaving an installer-owned block plus an installer-written `.zshrc`
  line.

**Fix:**
- Add `revert_theme(zshrc, state)`: if the last theme line's value still equals `owned_theme()`,
  restore the previous state (remove the inserted line, or for starship rewrite `""` back to the
  default), then clear the claim.
- Call it from `remove_plugins`/the omz sweep, and from starship's removal (re-apply
  `default_theme`).
- Test that a full uninstall leaves no `omz-theme` block.

### CR-09 — MEDIUM — A full uninstall rewrites (or creates) the owned `.zshenv` block whenever any zsh is on the host

**File:** `setup.py:1350` (`_sync_terminals_and_report` after `run_uninstall`);
`installer/terminal_shell.py:488-507`

**Problem:**
- After the teardown, the CLI uninstall runs the write-mode synchronizer.
- With a zsh the installer never installed (the system `/usr/bin/zsh`, or a user brew zsh), the
  sync takes the configure branch. It writes `# >>> tools-installer shell >>>` into `.zshenv`,
  and creates `~/.zshenv` when none existed.
- So `--uninstall --yes` ends with a new installer-owned block in a user dotfile, and the report
  says nothing about it.
- Only the no-zsh branch strips the block. The TUI uninstall's `terminal_sync_warning` call
  (`wizard_app.py:1940`) has the same effect.
- The kitty, WezTerm and Konsole regions follow the 15.6 precedent. The `.zshenv` block is new in
  this phase, and the phase goal says configuration is "reversed together with its tool".

**Failure scenario:** Fedora/Bazzite with system zsh, after an install run that never wrote
`.zshenv`, for example a host where the user deleted the block. `--uninstall --yes` leaves
`~/.zshenv` containing `export SHELL=/usr/bin/zsh` inside the owned markers.

**Fix:** The uninstall routes should call a revert-only path (`_revert_terminal_shells`, or a
`sync_terminal_shells(..., mode="revert")`) instead of the converging sync. Alternatively, strip
the `.zshenv` block explicitly after the sync and report "removed the SHELL export from
~/.zshenv".

### CR-10 — LOW — `receipt.hooks` is not updated after a successful unregister when a later removal step fails

**File:** `installer/app.py:782-822` (`remove_tool`)

**Problem:** The undo argvs run first. If a later step refuses (`remove_proven` refusal,
`OSError`), the tool is kept with `receipt.hooks[name]` still listing hosts that are now
unregistered. `_hook_fact` sees every host as recorded, so no `≈` appears. `register_hooks`
subtracts recorded hosts, so no RECONFIGURE or reinstall ever registers them again. The hook stays
off while the status says it is on. This is the open 23-08 note; the window is narrow for
codegraph, which is github_release only.

**Fix:** After the undo loop succeeds, clear `hooks[name]` in the receipt (a
`receipts.forget_hooks(tool_id, name)` under `_WRITE_LOCK`) before the paths are touched. A later
failure then leaves an honest `≈`.

### CR-11 — LOW — A hook-tool removal with no proven executable orphans its registrations silently

**File:** `installer/uninstall.py:299-308` (`_hook_undo` shortcut)

**Problem:** When `receipt.hooks` records hosts but no single proven `tool.cmd` artifact exists,
the plan has no undo. The removal then succeeds and deletes the receipt, which is the only record
of the registered hosts. Neither the preview nor the result says that the codegraph MCP entries
stay in `~/.claude.json` and the other host configs. The shortcut is documented (R1-40), but the
user gets a success with no handoff.

**Fix:** When `receipt.hooks.get(name)` is non-empty and `executable is None`, set
`RemovalPlan.hint`, or add a preview line: "codegraph stays registered for claude, codex: run
`codegraph uninstall --target … --keep-cli` before removing".

### CR-12 — LOW — Settings files are read without the non-blocking, capped reader, some on the UI thread

**File:** `installer/agent_settings.py:412-415` (`read_settings` → `atomic.read_snapshot`: plain
`O_RDONLY`, unbounded read); reached from `ExecuteScreen._option_prompts` → `review_problems`
(UI thread, every repaint), Policies state and detail reads, and `_settings_facts` on the refresh
worker.

**Problem:** `terminal_shell._read_text` documents why config reads use `read_capped` with
`O_NONBLOCK`: "a FIFO … cannot stall … so the dry run on the refresh worker never stalls". The
settings reader skips that rule. A FIFO, or a very large file, at a settings path blocks the
Textual event loop or the refresh pass.

**Fix:** Have `read_snapshot` (or `read_settings`) open with `O_NONBLOCK`, check `S_ISREG` with
`fstat`, and cap the read, the way `read_capped` does. A non-regular file becomes a
`SettingsParseError`-style refusal.

### CR-13 — LOW — The container e2e hook probe passes when nothing was registered

**File:** `scripts/container-e2e-verify.sh:742`, `:747` (`hook_probe_before`)

**Problem:** With no codegraph receipt, or a receipt that records no host, the probe prints
`TRACER_HOOKS_SKIPPED` and returns 0. `hook_probe_after` then prints
`TRACER_HOOKS_UNREGISTER_SKIPPED` and also returns 0. A regression where `register_hooks` records
nothing (CR-06's shape, or a broken `record_hooks`) therefore passes the e2e. The settings probe
also writes through `apply_setting` directly, so the run-option and Policies paths (CONF-08/09
from the UI) are never exercised in the container.

**Fix:** In the hook pass, `no-receipt`/`no-hosts` should fail when the plan installed codegraph
and at least one host; gate on the pass's selection. Optionally, drive one settings write through
`setup.py` (`--yes` cannot, so use a scripted `run_wizard` with `options`) instead of the module
call.

### CR-14 — LOW — The Desktop SHELL row reports "removed" when nothing was removed

**File:** `installer/policy.py:861-867` (`desktop_shell_policy._remove`)

**Problem:** `remove_owned_conf` returns False when the conf is absent or lacks the sentinel, and
the result is ignored. The row always reports the layer `removed 52-tools-installer-desktop-shell.conf`.
The full sweep only calls it when `owned()` is true. A Policies toggle after an external delete
or edit reports a removal that did not happen.

**Fix:** `if not env_redirect.remove_owned_conf(...): return PolicyResult((), None, "… was not
ours or already gone; nothing removed", changed=False)`.

### CR-15 — LOW — Duplicate helpers and an unused parameter

**File:**
- `installer/postinstall.py:143` `_failure_line` duplicates `installer/app.py:641`
  `_command_error_line`. It is the same rule, and the docstring even says "app.py's rule". REUSE
  08-3 asked for one extraction.
- `installer/session.py:409` `_first_line_of` duplicates the existing `first_line` helper.
- `installer/postinstall.py:149` `_HERDR_TARGETS` is a byte-identical copy of `_CODEGRAPH_TARGETS`.
- `installer/agent_settings.py:889` `ledger_summary(platform_os=…)` never uses the parameter.
- `installer/postinstall.py:205` registers `herdr-integration`, but no registry tool names it
  (the Phase 24 shape). Its unregister builder emits one argv per host, so a partial failure
  re-runs earlier hosts on retry. That is untestable until a tool uses it.

**Fix:** Move the failure-line rule to one module, `installer/run.py`, beside `CommandError`, and
import it in both. Use `first_line`. Alias the shared target map once. Drop the dead parameter or
use it to filter by OS.

---

## Verified clean (no finding)

- **Settings written only on opt-in.** The run options default empty and `--yes` never sets
  them. Policies writes only on space. The alias strip writes no agent file.
- **Unregister scope.** It uses only receipt hosts, filtered through the code-owned target map,
  so `all`, `auto`, paths and pi are dropped. `remove_tool` re-proves the undo argvs against the
  fresh plan.
- **Write safety.** `write_if_unchanged` and `delete_if_unchanged` check identity and bytes.
  Symlinked settings are written through to the target. The mode is preserved.
- **Test isolation.** `sandboxed_home` and `sandboxed_setup_paths` cover HOME and the import-time
  `setup.py` paths. `no_host_presence` and the ledger and `environment.d` fingerprints are in
  place. The ZDOTDIR, ZSH and XDG variables are cleared.
- **Round-trips.** Untouched JSON, JSONC and TOML files are byte-identical through insert and
  revert, by fuzz plus the suite.

_Reviewer: Claude (gsd-code-reviewer, deep lane)_
