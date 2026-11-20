---
phase: 28-shared-terminal-keys-mechanism
reviewed: 2026-11-20T13:54:02Z
depth: deep
files_reviewed: 14
files_reviewed_list:
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/app.py
  - installer/post_install.py
  - installer/registry.toml
  - installer/terminal_keys.py
  - installer/terminal_regions.py
  - installer/terminal_shell.py
  - installer/tweaks.py
  - installer/version_status.py
  - tests/test_terminal_keys.py
  - tests/test_terminal_shell.py
  - tests/test_tool_onboarding_skill.py
  - tests/test_tweaks.py
  - tests/test_version_status.py
findings:
  critical: 0
  warning: 2
  info: 7
  total: 9
  necessity: 2
status: issues_found
---

# Phase 28: Code Review Report

**Reviewed:** 2026-11-20T13:54:02Z
**Depth:** deep
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Scope: the base `4bf43adb` to HEAD diff of the 14 listed files. I compared the moved bodies with
`git show 4bf43adb:installer/terminal_shell.py`, followed every dispatch site (`post_install._tune_terminal`,
`apply_install_tuning`, `version_status._terminal_tuning_fact`, `app._after_removal`) to the table, and ran the
zsh widget body under `zsh -f`, `zsh -f -u`, `zsh -f -i`, `bash -u` with `set -e`, and `sh`. Assumed load: one
person running the installer on their own machine.

**The move keeps the behavior.** `_KEY_BINDINGS`, the plan, `replace_owned_region`, the created-marker write,
the strip order (`alacritty`, then `alacritty-keys`) and the warning prefixes match the base byte for byte.
For Alacritty, `_render` returns the plan unchanged because its `same_directory` is `Vendor`. The golden tests
in `tests/test_terminal_keys.py:204-275` pin the exact bytes. No import cycle: `terminal_shell` imports
`terminal_keys`, which imports `terminal_regions`, and neither imports back. No stale callers of
`apply_alacritty_keys`, `alacritty_keys_pending` or `strip_alacritty` are left in `installer/`.

**The widget's shell code is correct.** It sources cleanly in bash under `set -u` (the `${ZSH_VERSION-}` guard
holds), in plain sh, and in zsh, including a non-interactive zsh. It binds `^L` in emacs, viins and vicmd. zsh's
`print` turns `\033` into ESC. The removal path (`_after_removal`, zsh is in `SHELL_INIT_TOOLS`) strips the block
and forgets the record. The registry entry and the version_status dispatch (`source_shell_init`, then
`_shell_init_tuning_fact`) are wired correctly.

I am judging D-06 (with OQ1), the amended SPEC R3 adjacency wording and the D-12 test-import deviation as
written. Their implementation matches the decision text; I did not reopen them.

Key concerns:
1. The D-06 drift rule, at one edge, loses ownership for good. I reproduced this in a scratch HOME.
2. The widget overrides any `^L` binding the user made, against the skill's "never override" conflict rule.

External lane (opencode referee-one): I checked both of its claims against the source. Claim 2 is confirmed and
reproduced (WR-01). Claim 1 is mechanically correct but older than this phase and shared by every shell-init
bundle, so I kept it as Info (IN-01), not a blocker.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Drift re-apply removes the keys region when every chord conflicts, and the chord never comes back (external: opencode-referee-one)

**File:** `installer/terminal_keys.py:164-179`, `installer/terminal_keys.py:203-213`, `installer/terminal_regions.py:164-171`
**Issue:** `alacritty_keys_plan` returns `body=None` when the user binds all three chords. With a record and a
region present, `terminal_keys_pending` reports `KEYS_PENDING`, and RECONFIGURE (`skip_recorded=True`) commits
`replace_owned_region(text, region, None)`. That write deletes the region and rewrites the record. From then on,
"recorded and no region" reads as "the user deleted it" (`terminal_keys.py:178` and `:212`). If the user later
frees one chord, status stays OK and reconfigure does nothing. With two of three chords taken, the region
survives with one binding and a freed chord is restored, so only the all-conflicts case is broken.

Reproduced in a scratch HOME:
- install
- the user binds Alt+Left, Alt+Right and Control+Shift+K
- `pending` returns `install tuning not applied`
- reconfigure writes the file without the region
- the user removes their Alt+Left
- `pending` returns `None`, reconfigure returns `((), None)`, and Alt+Left is never managed again.

This also undercuts the phase 29 hand-off in 28-CONTEXT.md:87. TERM-03 relies on drift to reach existing
installs, and an install in this state is out of its reach.
**Fix:** Keep ownership whenever the installer itself empties the region. Write an empty marker pair instead of
removing it, so presence (and therefore drift detection) survives:
```python
# terminal_keys._render (or alacritty_keys_plan): no refusal and nothing to bind -> an empty owned region
body = plan.body if plan.body is not None else "# every chord is bound by you"
```
Then add one test that goes all-conflicts -> reconfigure -> free one chord -> `pending == KEYS_PENDING` ->
reconfigure restores that chord. The install-time all-conflicts case then writes the same empty region, which is
also correct.

### WR-02: The zsh widget overrides any Ctrl+L binding the user already made

**File:** `installer/tweaks.py:128-130`
**Issue:** The block binds `^L` without a check in all three keymaps. `shellrc.apply_block` appends the
`~/.myshellrc` source line to the end of `.zshrc` (`installer/shellrc.py:217-219`). So any
`bindkey '^L' <widget>` the user, or a plugin, sets earlier in `.zshrc` is silently replaced. The tool-onboarding
skill's conflict rule (`.claude/skills/tool-onboarding/SKILL.md:224`) says "A binding the user already defines
is never overridden", and rule (c) names this very zsh part. Nothing reports the replacement. Bundles have
`yields_to` for exports, but nothing like it exists for key bindings.
**Fix:** Replace only zsh's default binding. A few lines, no new mechanism:
```zsh
    for _ti_map in emacs viins vicmd; do
      case "$(bindkey -M $_ti_map '^L')" in
        *' clear-screen'|*' undefined-key') bindkey -M $_ti_map '^L' tools_installer_clear_all ;;
      esac
    done
    unset _ti_map
```
Also update the test in `tests/test_tweaks.py:64-77` that pins the three literal `bindkey -M` lines.

## Info

### IN-01: In single-shell bash mode the zsh row reads tuned while zsh never loads the widget (external: opencode-referee-one)

**File:** `installer/registry.toml:572`, `installer/version_status.py:788-801`, `installer/locations.py:94-105`, `installer/compose.py:646-650`
**Issue:** With `link_mode = "single"` and a detected shell of bash, `rc_paths_for_mode` wires only `.bashrc`.
`_split_sourced_from` returns `()` outside split mode, so the zsh bundle lands in a `~/.myshellrc` that zsh never
sources. `_shell_init_tuning_fact` only checks the marker and the record, so the zsh row reads OK. This is
older than this phase and applies to every shell-init bundle (and to the PATH block). The SPEC limits R3 to
"every zsh session that sources the managed config" (28-SPEC.md:133), so this is not a phase-28 defect.
**Fix:** If it matters, add a check at the shared layer: report zsh shell init as unreachable when the zsh rc is
not among the rc files that source `~/.myshellrc`. Do not special-case the zsh bundle.

### IN-02: The created-marker filename is spelled twice

**File:** `installer/terminal_shell.py:424-426`
**Issue:** `_created_marker` hardcodes `"terminal-alacritty-created"`, while `terminal_regions.ALACRITTY_CREATED`
(used by the row's `created_record`) defines the same name. If one changes without the other, the shell sync
records a created file under a name that `strip_terminal_keys` never looks at, so the config is no longer
deleted with the tool.
**Fix:** `return _xdg_data_home(home, environ) / "tools-installer" / ALACRITTY_CREATED` (import it next to
`ALACRITTY`).

### IN-03: The plan goes through a chain of wrappers that add nothing

**File:** `installer/terminal_keys.py:85-95`
**Issue:** `_alacritty_plan` calls `alacritty_keys_plan_for_text`, which calls
`alacritty_keys_plan_for_document`, which calls `alacritty_keys_plan`. D-05/D-12 only need
`terminal_shell` to import from `terminal_keys`. `alacritty_keys_plan_for_text` has one caller and does nothing.
**Fix:** Inline it: `return alacritty_keys_plan_for_document(*user_document(text))` in `_alacritty_plan`.
That saves about 3 lines.

### IN-04: The drift check exists twice and both copies must change together

**File:** `installer/terminal_keys.py:161-171` and `installer/terminal_keys.py:205-219`
**Issue:** Both `apply_terminal_keys` and `terminal_keys_pending` read the file, render it, compute "region
present" with a `None` replace, and compute "updated". The writer and the status fact must agree exactly, or the
row reads `≈` with no way to fix it (or the reverse). Today they agree.
**Fix:** One private helper returning `(before, text, plan, updated, present)`, called by both functions.

### IN-05: Generality without instantiation — the "no keys row" branches are guarded by the completeness test

**File:** `installer/post_install.py:389-392`, `installer/version_status.py:827-829`
**Category:** necessity
**Issue:** Both branches handle a registry tool that declares `apply_terminal_tuning` with no `TERMINAL_KEYS` row.
`tests/test_terminal_keys.py:152-155` fails the push gate in exactly that state, and the registry ships inside
the package, so the state is very unlikely in a shipped build. This is judgment, not proof: someone can hand-edit
an installed registry. That makes it Info, not Warning. These branches also have their own tests
(`test_a_declarer_without_a_row_is_refused_not_crashed`,
`test_terminal_tool_without_a_keys_row_reads_no_keys_fact`), which no plan asked for.
**Fix:** Keep them as a cheap fail-safe, or drop them with their two tests and let `TERMINAL_KEYS[tool.id]` raise.
That is a scope call for the owner.

### IN-06: Impossible-state guard — `command -v zsh` inside a body that already requires a running zsh

**File:** `installer/tweaks.py:119`
**Category:** necessity
**Issue:** Everything in the block sits under `[ -n "${ZSH_VERSION-}" ]`, which is only true when zsh is the
running shell. The outer `command -v zsh` therefore never decides anything useful. It can only skip the widget
wrongly, when zsh runs from a path that is not on `PATH`. 28-04-PLAN.md:26 asks for this guard to match the other
bundles, so it is kept as Info.
**Fix:** Drop the outer `if command -v zsh` / `fi` pair. The `ZSH_VERSION` test alone is the correct guard.

### IN-07: `Writes` reports keys as added when only the snippet was written, and does not check the snippet for conflicts

**File:** `installer/terminal_keys.py:106-113`, `installer/terminal_keys.py:195`
**Issue:** No row uses `Writes` yet (generality without instantiation, planned for phase 29). When one does:
- If every chord conflicts, `_render` still returns a body (the snippet alone), so `row.summary` ("... keys: ...")
  is printed for keys that were not written.
- The snippet is not checked against the user's text. A `[window]` the user already has makes the region fail
  `validate_toml`, which refuses the whole keys region, chords included.

**Fix:** Before phase 29 adds a `Writes` row, base `added` on `plan.body` from `row.plan` (before the snippet is
appended), and check the snippet's table against the user document the way `_shell_plan` checks `env`.

---

Not checked: the widget's visual redraw under a real pty (left to the manual UAT in 28-VALIDATION.md:70).
pytest was not run, as instructed. I checked the shell semantics with one-off `zsh -f`, `bash -u` and `sh`
sourcing of the rendered body, and checked WR-01 with a scratch-HOME Python run (no repo files touched).

_Reviewed: 2026-11-20T13:54:02Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
