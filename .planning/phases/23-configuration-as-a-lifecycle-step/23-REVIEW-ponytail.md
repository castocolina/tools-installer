---
phase: 23
lane: ponytail
base: 97b9e0b
head: 4085e79
scope: git diff 97b9e0b..4085e79 -- installer setup.py scripts tests
counts: { high: 1, medium: 3, low: 5 }
---

# Phase 23 — ponytail code review lane

**What this change does:** Phase 23 makes configuration part of each tool's lifecycle.
Agent-host hooks (codegraph, herdr) record the hosts they registered and undo exactly those
on removal. Six shell-init bundles are offered at install, default off. zsh is exported as
`SHELL` through `~/.zshenv` and the terminal configs. Auto-approval, attribution and VS Code
lean-mode keys go into each agent's own settings file through a new text splice
(`installer/agent_settings.py`) with a per-agent ledger, so a revert removes only the
installer's keys.

**Load assumed:** one person running the installer on their own machine, one process at a
time. VS Code, Claude Code or codex may rewrite the same settings file between the
installer's read and its write.

**Method:** I read the diff and the connected code: `agent_settings.py` in full, the ledger
in `receipts.py`, `atomic.py`, `postinstall.py`, `session.py` (run options and resync),
`app.py` (removal and revert), `uninstall.py`, `omz.py` theme, `post_install.py`,
`policy.py` (settings and tweak rows), `terminal_shell.py`, `env_redirect.py`, the conftest
sandbox and the e2e probes. I probed the splice scanner by running it in a scratch HOME
(`uv run python` against the real module): strings with braces, `//` and `/*`, escaped
quotes, nested objects, created parents, CRLF, BOM, trailing commas, empty and
whitespace-only files, TOML arrays and multi-line strings, and a full
`apply_setting` → user edit → `revert_setting` round trip. Each finding below was reproduced
that way, or confirmed by reading the code.

The splice holds up well overall. Every edit is re-parsed and compared with the expected
document (`_guarded`), so no probe changed a value the installer did not mean to change. The
failures I found are refusals that should not happen, and comments the guard cannot see.

## Must fix

### PT-01 — HIGH — Exact revert is refused after VS Code adds a setting to a file the installer created

- **File:line:** `installer/agent_settings.py:288-290` (empty-object insert leaves a fragment
  with no comma), `installer/agent_settings.py:383-392` (fragment fast path, no fallback when
  the guard refuses)
- **Problem:** When the target object is empty (`{}`, which is also the content of every
  settings file the installer creates), the first key is inserted as `\n  "key": value`, with
  no comma. Later keys go above it, so this key ends up as the last member. When VS Code
  changes a setting from its UI, it appends `,\n  "editor.fontSize": 14` after that member.
  The recorded fragment is still in the text exactly once, so `remove_key` cuts it. That
  leaves `false,,` and invalid JSON behind. `_guarded` then refuses the edit, and nothing
  falls back to the located-member cut (`_cut_member`), even though that cut handles this
  text correctly.
- **Failure scenario:** Reproduced in a scratch HOME. Install VS Code with lean mode on a
  machine with no `settings.json` (the normal case right after a VS Code install). The
  installer creates the file. The user then changes any setting in VS Code. Every later
  opt-out, the Policies row, VS Code removal and `--uninstall` now report
  `could not revert ~/.config/Code/User/settings.json — the edit broke the file`. The ledger
  and all lean keys stay for good, and the row keeps reading `on`. The same failure happens
  for a hand-edited Claude `settings.json` that the installer created (created-parent case).
  This breaks the phase promise "reversed with its tool" on the most common VS Code path, and
  the message blames a file that is valid.
- **Fix:** In `remove_key`, try the fragment cut first. If `_guarded` refuses it, fall back to
  `_cut_member` and guard that result instead. Then delete the `stranded` special case
  (lines 383-387): the fallback covers it. That is about 4 lines changed and 5 deleted. Add one
  test: create the file, append a key after the last member, revert, and check the file
  returns to `{}`-equivalent text with the user key kept. As an optional extra, make the
  empty-object insert put the closing `}` on its own line. Today a created file reads
  `"telemetry.telemetryLevel": "off"}`.

## Should fix

### PT-02 — MEDIUM — Valid JSONC with two block comments is read as invalid

- **File:line:** `installer/agent_settings.py:33-38` (`_JSONC_TOKEN`, trailing-comma
  lookahead)
- **Problem:** The trailing-comma lookahead uses `/\*.*?\*/` with `re.DOTALL`. When the
  shortest comment match fails, the regex backtracks and extends `.*?` past the first `*/`,
  over real JSON, to a later `*/` that sits just before a `}` or `]`. A comma in the middle of
  the object then counts as a trailing comma and is blanked.
- **Failure scenario:** Reproduced. `{"a": 1, /* c */ "b": 2 /* d */}` and a VS Code-style
  file ending with a commented-out entry (`"a": 1, /* why */\n "b": 2\n /* "c": 3 */\n}`) both
  raise `not valid JSONC`. That affects VS Code `settings.json` and `opencode.jsonc`. The row
  shows `≈` with a false parse error, and every write and revert for that file is refused.
  The user is told to "fix" a valid file. No data is lost, because the guard refuses the edit.
  The existing tests use only one block comment per file, so they never hit this.
- **Fix:** Use a block-comment token that cannot cross `*/`, in both places in the pattern:
  `/\*(?:[^*]|\*(?!/))*\*/`. I checked that this parses all four probe inputs correctly. Add
  the two strings above to the JSONC parse test.

### PT-03 — MEDIUM — Turning starship on in Policies does not write `ZSH_THEME=""`, although the row says it does

- **File:line:** `installer/post_install.py:154-155` (only the install-time path writes the
  theme), `installer/policy.py:451-457` (`tweak_policy._apply` writes only the rc block),
  `installer/policy.py:835-839` and `installer/tweaks.py:146` (the copy that promises it)
- **Problem:** The starship bundle's description and the Policies detail both say turning it
  on "sets ZSH_THEME="" in ~/.zshrc". Only `_source_shell_init`, the install-time "yes",
  writes the theme. The Policies toggle goes through the generic `tweak_policy._apply`, which
  never calls `apply_theme`. So the same feature does different things depending on the
  entry point. The architecture rule is one apply workflow.
- **Failure scenario:** The user declines starship shell init at install, then turns it on in
  Policies. The UI reports that the theme was cleared, but `~/.zshrc` keeps
  `ZSH_THEME="robbyrussell"`. Both the Oh-My-Zsh theme and starship now load. Later, an
  unrelated OMZ-plugins apply runs `write_plugins` → `apply_theme(default_theme)` and clears
  the theme silently, so the end state depends on unrelated actions.
- **Fix:** Move the starship theme write next to the bundle apply, in one place both paths
  use. For example, `tweak_policy._apply` calls the same
  `apply_theme(zshrc, rc_path, "")` when `bundle.id == "starship"`, and `_source_shell_init`
  just applies the policy. Or drop the claim from the two copy strings. The first option
  matches the SPEC (R11).

### PT-04 — MEDIUM — A config-write ledger that fails validation is silently replaced, which forgets every recorded key

- **File:line:** `installer/receipts.py:308-330` (`read_ledger` returns None for any
  malformed entry), `installer/agent_settings.py:646` and `:737`
  (`read_ledger(agent) or ConfigLedger(agent)`)
- **Problem:** Failing closed is right for a read. But both apply and revert treat "can't
  trust the ledger" as "empty ledger". Apply then writes a new ledger over the old one. Revert
  finds no entries and reports success with nothing reverted. Neither path tells the user.
- **Failure scenario:** One malformed entry makes the whole ledger untrusted. Causes include
  a hand edit, a future field the old reader rejects, or a ledger over the receipt size cap
  (several agents' lean lists with fragments). The next Policies toggle overwrites the ledger
  with only the new keys. From then on, every key written earlier counts as "already this
  way" or "set by you" and is never reverted, including on `--uninstall`. Recovery by hand is
  impossible because the record is gone.
- **Fix:** Tell "missing" apart from "present but untrusted" (`_read_json_object` already
  knows). For the untrusted case, refuse the write with a one-line reason (`config ledger
  for 'vscode' is unreadable`), the same way an unreadable settings file is handled (O7). That
  is about 6 lines.

## Nice to have

### PT-05 — LOW — Revert can delete user comments that the guard cannot see

- **File:line:** `installer/agent_settings.py:357-362` (`_cut_member` eats blanked comments up
  to the newline), `installer/agent_settings.py:348-351` (comment before the comma),
  `installer/agent_settings.py:754-756` (a created file that parses empty is deleted)
- **Problem:** The guard compares documents, and comments are not part of the document. The
  located-member cut walks through blanked comment space, so a comment on the same line as
  the installer's member is removed with it. A file the installer created is deleted when it
  parses to `{}`, even if the user has since added only comments.
- **Failure scenario:** Reproduced. Two inputs: `{\n  "k": true, // keep me\n  "a": 1\n}` on
  the cut path, and `"k": true // why` as the last member. Both lose the comment on revert.
  This needs the cut path (a vendor reformat, or the PT-01 fallback) plus a comment the user
  wrote on the installer's line, so it is rare. It still breaks the "comments survive"
  constraint.
- **Fix:** In `_cut_member`, stop the end-of-line probe at the first non-space character of
  the original `text`, not of `clean`. Then a comment stays, along with its newline. Before
  deleting a created file, check that `text.strip()` is exactly `{}`, not just that it parses
  empty.

### PT-06 — LOW — The new-host resync skips a hook tool whose receipt recorded zero hosts

- **File:line:** `installer/session.py:569` (`not receipt.hooks.get(name)`),
  `installer/postinstall.py:297` (nothing is recorded when nothing registered),
  `installer/uninstall.py:299`
- **Problem:** `_resync_hooks` skips a receipt with no hooks entry, to leave pre-Phase-23
  receipts to RECONFIGURE. But a Phase-23 install of codegraph when no host was present also
  writes no entry. The two cases look the same.
- **Failure scenario:** The user installs codegraph in one run with no agent present, then
  installs claude in a later run. CONF-02 says codegraph should register for claude at the end
  of that run. Instead nothing runs, and the codegraph row shows `≈` until the user presses
  RECONFIGURE.
- **Fix:** Record an empty host list on a successful zero-host register
  (`hooks[name] = ()`), and test `name in receipt.hooks` instead of truthiness in
  `_resync_hooks`. The removal guard at `uninstall.py:299` can keep its truthiness check.

### PT-07 — LOW — Re-applying the installer's own theme is reported as the user's theme

- **File:line:** `installer/omz.py:637-642`, `installer/post_install.py:179-180`
- **Problem:** When the theme the installer recorded is already in force,
  `set_theme(..., replace=previous)` rewrites the same value. The text does not change, so
  `apply_theme` returns `outcome="yours"`.
- **Failure scenario:** Reproduced. The second `apply_theme(..., "robbyrussell")` after an
  `added` returns `ThemeResult('yours', 'robbyrussell')`. An OMZ reinstall or repair then
  prints "Theme: robbyrussell (yours; left as is)." about a line the installer wrote.
- **Fix:** Return a distinct outcome, or reuse `added`, when `previous == name` and the line
  holds it. That is one comparison before the `updated == original` branch.

### PT-08 — LOW — Some valid settings files are refused instead of edited

- **File:line:** `installer/agent_settings.py:126-127` and `:266-267` (an empty file parses as
  `{}` but insert refuses it), `:316` (first line starting with `[`), `:137-138` (BOM)
- **Problem and scenario (all reproduced, all refusals, no corruption):**
  - A 0-byte `settings.json`, for example after `touch`, reads as an empty object but refuses
    every insert with "empty file: there is no object to insert into".
  - A codex `config.toml` whose top-level array has a nested array on its own line
    (`args = [\n  ["a"],\n]`) has that line treated as a table header, so the insert lands
    inside the array and is refused. A `"""` multi-line string containing a `[` line fails
    the same way.
  - A UTF-8 BOM makes JSON, JSONC and TOML read as invalid.
- **Fix:** Treat whitespace-only text like an absent file: use `new_file_text(fmt)` as the
  base, keep `created_parent` as is, and do not add the file to `created_files`. Strip one
  leading `U+FEFF (BOM)` in `_text_of` and put it back on write. For TOML, find the first table with
  `tomllib`-confirmed positions, or accept the refusal and add a `shortcut:` comment that
  names it.

### PT-09 — LOW — Dead parameter and an unused default branch

- **File:line:** `installer/agent_settings.py:889-891` (`ledger_summary(..., platform_os)` is
  never read, which the wave-2 notes already flagged), `installer/agent_settings.py:383-387`
  (the `stranded` special case, which becomes dead once PT-01's fallback lands)
- **Problem:** Code that does nothing has to be read and kept in sync. The parameter makes
  every caller compute and pass an OS that has no effect.
- **Fix:** Drop `platform_os` from `ledger_summary` and its callers in `app.py`. Delete
  `stranded` together with PT-01.

## Checked and fine

- **Guarded splice:** every insert, remove and replace re-parses and compares with the exact
  expected document (`same_value` keeps `1` and `True` apart). No probe produced a wrong value
  that got written. Strings containing `{`, `}`, `//`, `/*`, `*/` and escaped quotes; nested
  objects; duplicate keys (last one wins, which matches `json.loads`); and JSONC trailing
  commas on removal all behave correctly.
- **Compare and swap:** `write_if_unchanged` and `delete_if_unchanged` (identity plus bytes,
  `O_NOFOLLOW` on the resolved target, symlinked dotfiles kept) retry once, then report
  `changed while being written`. The ledger is reserved before the write and restored when
  the write fails.
- **Opt-in only:** `--yes` sends `confirm_sensitive=None` and `options=frozenset()`, so no
  shell init and no settings key is written without a "yes". Install-time questions default
  to no.
- **Hook undo:** it runs only for hosts the receipt records, filtered through the code-owned
  target map. It runs before any path is removed, and a failed undo stops that tool's removal
  and keeps the receipt (O4).
- **Test isolation:** `sandboxed_setup_paths` re-roots setup.py's import-time home paths,
  `no_host_presence` stubs host detection, `.zshenv` and the config-ledger and environment.d
  listings are in the real-home fingerprint, and the e2e settings and hook probes run only
  inside the container.

**Verdict:** fix PT-01 first, then PT-02 and PT-04.
**Lean:** about 10 lines can go (the `stranded` branch and the dead `ledger_summary`
parameter).
**Not checked:** the TUI rendering changes in `render.py`, `wizard_app.py` and
`execute_screen.py` beyond their settings and removal wiring, and the real vendor behaviour of
`codegraph uninstall` and `herdr integration uninstall` (the 23-16 container run is the
evidence for those).
