# Phase 28: Shared terminal-keys mechanism - Context

**Gathered:** 2026-11-19 (assumptions mode, after 28-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

Move Alacritty's owned keys region out of `installer/terminal_shell.py` into a shared mechanism keyed by registry tool id (apply, check, re-apply, strip), make the three dispatch sites table-driven, add the managed zsh Ctrl+L clear widget, and add the completeness and same-directory tests. Alacritty's bytes and existing tests stay unchanged; its clear action flips in phase 29.
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**5 requirements are locked.** See `28-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `28-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** `installer/terminal_keys.py` and the table-driven dispatch in `post_install.py`, `version_status.py`, `app.py`; the managed zsh Ctrl+L widget and its byte-level test; the completeness and same-directory-declaration tests. *Amended 2026-11-19 (28 D-05, D-12):* also a lower module for the shared region primitives and the four in-function import lines of `tests/test_terminal_shell.py`.
**Out of scope (from SPEC.md):** Alacritty's clear flip (phase 29); kitty, WezTerm, Konsole, herdr rows (29); Ghostty, iTerm2, Herdr app (30-31); real-Mac checks; changing the wording of `≈ apply install tuning`.

</spec_lock>

<decisions>
## Implementation Decisions

### Mechanism design
- **D-01: `TERMINAL_KEYS: dict[str, KeysRow]` keyed by registry tool id**, the row not repeating the id. The record path comes from the key, so the record keeps today's names (`terminal-tuning-alacritty`, `terminal-alacritty-created`; `installer/terminal_shell.py:475-476,500-506`). Generic `apply_terminal_keys(row, platform_os, home, environ, *, skip_recorded)`, `terminal_keys_pending(...)` and `strip_terminal_keys(...)` are today's Alacritty bodies with the row's fields substituted. Evidence: a scratch-HOME capture with today's code wrote those two names. Changing them would make every existing Alacritty install read `≈` again.
- **D-02: Today's success and refusal text stays.** The refusal becomes `f"{tool.name} keys not changed: {refused}"` (`tool.name` is `"Alacritty"`, `installer/registry.toml:3154`); the success line is a row field `summary`. `_apply_terminal_tuning` stops discarding `tool` and `platform`. `tests/test_post_install.py:1129-1141` asserts the exact refusal line, so it must pass unedited.
- **D-03: Row fields:** `ownership` (a typed union with one variant now, `OwnedRegion(region, comment)`, so a `WholeFile(proof)` variant can be added in phase 31 without a rewrite), `config_path(platform_os, home, environ)` *(amended 2026-11-19, 30 D-13: takes `platform_os`, because Ghostty's file differs per OS)*, `plan(platform_os, file_text) -> KeysPlan` (body, conflicts, refusal), `validate` (the TOML re-parse), `summary`, `sibling_regions` (`("alacritty",)`: stripped with the tool, left out of the "outside" text), `created_record`, `same_directory` (required), `clear` (default "send Ctrl+L", Alacritty overrides it with `ClearHistory`) *(amended 2026-11-19, 29 D-11: plus a `placement` field (end, top, before `return config`) and a per-row `validate`)*. `tests/test_terminal_shell.py:1153-1205,1540-1595` need strip and created-file deletion per row.
  - **Own reasoning** (jev flat_fields_plus_flag low 0.50; first rung low 0.42): the typed union is the analyzer's best and phase 31's JSON mode is the evidence. Ledger.
- **D-04: The dispatch sites** become `post_install._tune_terminal` → `TERMINAL_KEYS[tool.id]`; `version_status._terminal_tuning_fact(tool)` → `TERMINAL_KEYS.get(tool.id)` (no row, no fact); `app._after_removal` → `strip_terminal_keys` when a row exists. `KEYS_PENDING` moves with the mechanism; `version_status` keeps its own `TUNING_PENDING` (same text). `_TERMINAL_ROWS["alacritty"]` (`version_status.py:738`) is shell-sync drift, not key handling, and stays; the SPEC's `rg 'alacritty'` check needs a reviewer's reading of that one line.
- **D-05: Import direction is `terminal_shell` → `terminal_keys`** (contradicting `.planning/research/ARCHITECTURE.md:24,51`). The shell sync must keep reporting the keys conflicts (`tests/test_terminal_shell.py:1230-1234` asserts `"alacritty: partial: you already bind Alt+Left"` in the sync result), and pyright is strict (`pyproject.toml:44`), so cross-module private names are `reportPrivateUsage` errors. The shared primitives move **down** into a small lower module, `installer/terminal_regions.py`, with public names: `_replace_owned_region`, `_marker`, `TerminalShellError`, `_xdg_config_home`, `_xdg_data_home`, `_snapshot_text`, `_first_line`, the compare-before-commit strip helper, `_commit_alacritty` with the created marker, `_imports_files`, `alacritty_config_path`, `_keys_plan`/`_user_document`. `terminal_shell` imports them under their current local names so Konsole, kitty, WezTerm and herdr bodies stay byte-unchanged; `_read_text`, `_write_if_changed`, `_shell_plan` and `_sync_alacritty` stay in `terminal_shell`.
  - **Own reasoning** (jev third_module_aliased low 0.77; first rung low 0.63): the strict-pyright and test-assertion evidence decides. Ledger.
- **D-12: Existing tests stay unedited except four in-function import lines** (`tests/test_terminal_shell.py:1220,1254,1323,1648`: `from installer.terminal_shell import apply_alacritty_keys` becomes `from installer.terminal_keys import ...`). No re-export is left in `terminal_shell`. Monkeypatches on `terminal_shell.read_settings`, `atomic_write_text` and `ensure_zshrc_template` (`:184-196,1276-1283`) target shell-side code that stays, so `_read_text` and `_write_if_changed` must not move. jev first rung none_of_these 0.95 contradicted the evidence; second opinion update_imports low 0.67. **jev overridden / Own reasoning**, ledger.

### Drift and pending semantics (amends KEYS-02)
- **D-06: "Pending" means no record and no region (today's meaning); "drifted" means a region is present and its bytes differ from the current render; a reconfigure rewrites a present, stale region; a region the user deleted after a recorded install stays the user's choice.** Evidence: `alacritty_keys_pending` (`terminal_shell.py:710-723`) returns None whenever the record or a region exists, and `tests/test_version_status.py:7054` and `tests/test_post_install.py:1114-1126` pin the user-deleted doctrine; phase 29's TERM-03 changes `ClearHistory` and could never reach existing installs through reconfigure, because `skip_recorded=True` returns early at `:679-680`, unless drift is detected. This amends KEYS-02 / SPEC R2 / ROADMAP criterion 2 ("deleting ... makes its row read `≈`" is true only without a record). **Flagged: needs confirmation** (the amendment narrows owner-listed behavior "a missing region shows `≈`"). jev drifted_rewrite 0.90 (TypeSafe). Ledger.

### The zsh Ctrl+L widget
- **D-07: The widget is a shell-init bundle owned by the `zsh` registry tool.** `"zsh"` is added to `SHELL_INIT_TOOLS` (`installer/tweaks.py:90`), a `_shell_init("zsh", ...)` bundle to `BUNDLES`, and zsh's registry entry (`installer/registry.toml:562`) gets `post_install = ["source_shell_init"]`. This reuses the marker block in `~/.myshellrc`, the record, the `≈` fact (`version_status.py:781,787-799`), reconfigure (`post_install.py:280-305`) and strip on removal (`app.py:633-637`), and is not a Policies row (`compose.py:713` filters `SHELL_INIT_TOOLS`). Caveat: zsh is `system` tier, so the installer never installs it; the widget is written through the zsh row's `≈` then reconfigure, and the block goes when zsh itself is removed. jev zsh_entry_tuning 0.81 (TypeSafe).
- **D-08: The widget text** is guarded for bash (`~/.myshellrc` is also sourced by bash, `shellrc.py:380-390`) and binds the key in `emacs`, `viins` and `vicmd`: `tools_installer_clear_all` prints `\033[H\033[2J`, runs `zle .reset-prompt` and `zle -R`, then prints `\033[3J`, all to the terminal. Live-verified by the analyzer in zsh 5.9.2 under a pty in a scratch HOME (buffer kept, order 2J then 3J); explicit keymaps matter because Oh-My-Zsh runs `bindkey -e` (`lib/key-bindings.zsh:19`) and the neovim bundle exports `EDITOR=nvim` (`tweaks.py:113`). **Own reasoning** (jev explicit_bytes_all_keymaps low 0.62; first rung low 0.34). Ledger.
- **D-09: The widget test has two layers.** Always: a pty-free bytes check on the rendered block asserting `ESC[H ESC[2J` comes before `ESC[3J`, the bash guard, the bindings, and that apply then strip returns a scratch rc file to identical bytes. Backstop: `zsh -n` and an optional pty probe, skipped when zsh is absent (`tests/test_tweaks.py:373`; `skipif(shutil.which("zsh") is None)` as in `tests/test_shellrc.py:708`). `.github/workflows/ci.yml` installs no zsh, so a pty-only test could skip silently. **Own reasoning** (jev bytes_plus_optional_shell low 0.74). Ledger.

### Tests
- **D-10: Golden bytes land in a commit before the move.** A new `tests/test_terminal_keys.py` pins the bytes through the public routes only (`run_post_install`, `sync_terminal_shells`, `app._after_removal`), so it passes on pre-move code and after it. Cases: created file, user content, adjacent user binding, shell and keys regions together, strip. Today's created-file bytes (captured live): `# >>> tools-installer terminal-shell alacritty-keys >>>\n[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "\\u001bb"\n\n[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "\\u001bf"\n\n[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\naction = "ClearHistory"\n# <<< tools-installer terminal-shell alacritty-keys <<<\n`.
- **D-11: The completeness test is a pure helper over id sets:** `{t.id for t in tools if "apply_terminal_tuning" in t.post_install} - set(TERMINAL_KEYS)`, run on `load_tools(REGISTRY)` and on a tmp fixture registry with an extra tool (must fail); it also checks the reverse and that no key is `konsole`. It is not enforced at runtime in `model.py` (that would invert layering).
- **D-13: The fixture rows for KEYS-03 and KEYS-04 live only in the new test file:** one proves the generic clear chord resolves to Ctrl+L (`\x0c`) per OS (`cmd+k` macOS, `ctrl+shift+k` Linux, as a format-neutral chord); a pair proves vendor vs installer-writes for the same-directory setting. Alacritty's own row keeps `ClearHistory` until phase 29.
- **D-14: `same_directory` is a required field with no default**, a typed value: vendor (nothing written), writes (carries the setting), not-applicable. The test asserts the dataclass field has no default and every row holds a valid value. **Own reasoning** (jev typed_with_setting low 0.55; first rung none_of_these 0.71 contradicted the evidence). Ledger.
- **D-15: Alacritty's row declares `vendor`** with a dated note. Evidence (2026-11-19, upstream `CHANGELOG.md` read via the GitHub API, lines 715-724): `SpawnNewInstance` uses the working directory of the terminal foreground process on Unix and macOS; `CreateNewWindow`'s behavior is not stated there and stays `unverified` in the note. Either way the installer writes nothing for Alacritty, so the golden bytes cannot change. **Own reasoning** (jev vendor_does_it none; unverified low 0.46). Ledger.

### Claude's Discretion
- Names of the lower module's public functions, the `KeysPlan` field names, and the widget function name.

### Folded Todos
None.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/28-shared-terminal-keys-mechanism/28-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-CONTEXT.md` (rows, D-14 WezTerm clear fact)
- `installer/terminal_shell.py`, `installer/post_install.py`, `installer/version_status.py`, `installer/app.py`, `installer/tweaks.py`, `installer/shellrc.py`, `installer/model.py`
- `tests/test_terminal_shell.py`, `tests/test_post_install.py`, `tests/test_version_status.py`, `tests/test_tweaks.py`
- `.planning/research/ARCHITECTURE.md` (its import direction is overridden by D-05), `.planning/REQUIREMENTS.md` (KEYS-01..04)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_replace_owned_region`, `_write_if_changed`, `FileSnapshot`, record and created-marker files, `KEYS_PENDING`; the shell-init bundle machinery (`tweak_block`, `SHELL_INIT_TOOLS`).

### Established Patterns
- Install tuning: a named action in `post_install`, `≈ apply install tuning` while pending, reverted with the tool; a user-deleted recorded block is the user's.

### Integration Points
- `post_install.py:385-396,445`, `version_status.py:783,821-834`, `app.py:630-631`; zsh's registry entry at `registry.toml:562`.
</code_context>

<specifics>
## Specific Ideas

Coupling handed to phase 29: the drift rule (D-06) is what lets TERM-03's `ClearHistory` to Ctrl+L change reach existing Alacritty installs; phase 29 must rely on it rather than add its own migration.
</specifics>

<deferred>
## Deferred Ideas

- Whether `ubuntu-latest` and `macos-latest` runners ship zsh (decides whether the zsh backstops run in CI), whether `zle .reset-prompt` plus `zle -R` redraws multi-line starship prompts correctly, and whether macOS Terminal.app and iTerm2 push the screen into scrollback on `ESC[2J`: checked in planning or the owner's Mac UAT.

### Reviewed Todos (not folded)
None matched.
</deferred>
