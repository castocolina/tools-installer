# Architecture Patterns

**Domain:** terminal key tuning (word navigation + clear shortcut, per OS) inside the existing tools-installer lifecycle
**Milestone:** v0.51.0 Onboard terminal tools
**Researched:** 2026-11-16
**Confidence:** HIGH for integration points (read from code), MEDIUM for per-terminal key syntax (not verified upstream here; flagged per phase)

## Verdict

Generalize. Do not write `apply_kitty_keys`, `apply_wezterm_keys`, ... as parallel functions.

Today Alacritty's keys are one hard-wired trio (`apply_alacritty_keys` `installer/terminal_shell.py:671`, `alacritty_keys_pending` `:710`, `strip_alacritty` `:726`) plus three dispatch edits that each hard-code the one terminal:

| Dispatch site | Hard-coded to Alacritty | Line |
|---|---|---|
| `_tune_terminal` calls `apply_alacritty_keys` (the `apply_terminal_tuning` action ignores `tool`: `del tool, platform`) | yes | `installer/post_install.py:387`, `:393-396` |
| `_terminal_tuning_fact()` takes no args, calls `alacritty_keys_pending` | yes | `installer/version_status.py:821-834`, caller `:783` |
| uninstall sweep `if tool.id == "alacritty"` | yes | `installer/app.py:630-631` |

Per-terminal functions would repeat those three edits plus the record/skip/pending/strip lifecycle once per terminal (kitty, WezTerm, Ghostty, iTerm2, Herdr IDE). A table makes them one-time edits. The formats differ (TOML, kitty.conf, Lua, Ghostty key=value, JSON), so the table generalizes the **lifecycle**, not the **body**: each row supplies a renderer and a conflict checker, the shared code does everything else.

## Recommended Architecture

New module `installer/terminal_keys.py` (terminal_shell.py is already 1055 lines; keys is install tuning, shell sync is a different mechanism that follows zsh). It imports `_replace_owned_region`, `_read_text`, `_xdg_*`, `_kitty_config_path`, `_wezterm_config_path`, `_snapshot_text`, `_first_line` from `terminal_shell` (no reverse import, so no cycle). Alacritty's keys code moves into it as the first table row.

```python
@dataclass(frozen=True)
class KeysSpec:
    region: str                      # "kitty-keys", "alacritty-keys", ...
    comment: str                     # "#" or "--" (marker comment char; JSON uses whole-file mode)
    path: Callable[[Path, Mapping[str, str]], Path]
    render: Callable[[str, str], _KeysPlan]   # (platform.os, user text outside the region) -> body/conflicts/refusal
    validate: Callable[[str], None] | None    # alacritty: tomllib re-parse before write; None elsewhere
    summary: Callable[[str], str]             # the one-line "Kitty keys: ..." message per OS

TERMINAL_KEYS: dict[str, KeysSpec] = {"alacritty": ..., "kitty": ..., "wezterm": ..., "ghostty": ...}
# keyed by REGISTRY TOOL ID, because post_install/version_status/app already hold a Tool.

def apply_terminal_keys(spec, platform_os, home, environ, *, skip_recorded) -> tuple[tuple[str, ...], str | None]
def terminal_keys_pending(spec, platform_os, home, environ) -> str | None   # None | KEYS_PENDING | refusal
def strip_terminal_keys(spec, home, environ) -> tuple[str, ...]             # warnings
```

The three shared functions are the current Alacritty bodies with `ALACRITTY_KEYS`, `alacritty_config_path`, `_keys_plan`, `_commit_alacritty` replaced by `spec.*`. Record file per terminal: `terminal-tuning-<id>` (generalizes `_KEYS_RECORD` `:475`, `_keys_record` `:500`). The "created marker" and `_drop_created_config` (`:742`) stay Alacritty-only for now (see Pitfalls): kitty and WezTerm files are already created by the shell sync with no delete-on-strip.

### Component Boundaries

| Component | Status | Responsibility | Communicates With |
|---|---|---|---|
| `installer/terminal_keys.py` | NEW | `KeysSpec`, `TERMINAL_KEYS`, shared apply/pending/strip lifecycle, per-terminal renderers | `terminal_shell` (region helper, paths), `agent_settings` (`read_settings`, `write_if_unchanged`, `missing_dirs`), `atomic` |
| `installer/terminal_shell.py` | MODIFIED | Alacritty keys code removed (`:465-768` keys half stays only as the shell region `_sync_alacritty` `:633`); `_user_document` (`:528`) strips both Alacritty regions, move that into the Alacritty spec; add Ghostty shell branch to `sync_terminal_shells` (`:893`) | `terminal_keys` does NOT import back |
| `installer/post_install.py` | MODIFIED | `_tune_terminal(tool, platform, skip_recorded)` looks up `TERMINAL_KEYS[tool.id]`; `_apply_terminal_tuning` stops `del tool, platform` (`:393-396`); `apply_install_tuning` branch at `:445` passes both | `terminal_keys` |
| `installer/version_status.py` | MODIFIED | `_terminal_tuning_fact(tool, platform)` (`:821`), caller `_tuning_fact` (`:775-785`) passes them; `_TERMINAL_ROWS` (`:735-741`) gains `ghostty` for the shell `≈` | `terminal_keys` |
| `installer/app.py` | MODIFIED | `app.py:630` becomes `if tool.id in TERMINAL_KEYS:` then `strip_terminal_keys`; Alacritty also strips its shell region as today (`strip_alacritty` keeps shell region, or its shell half moves with it) | `terminal_keys` |
| `installer/registry.toml` | MODIFIED | `post_install = ["apply_terminal_tuning"]` on kitty (`:3016`), wezterm (`:3104`); new `ghostty`, `iterm2`, `herdr-ide` entries | model validation (closed `POST_INSTALL_ACTIONS` `model.py:130-141`, no new action name needed) |
| `installer/session.py` | UNCHANGED | `_install_tuning_step` (`:351`) already calls `apply_install_tuning(skip_recorded=True)` for the `≈` RECONFIGURE step | - |
| `installer/model.py` | UNCHANGED | `ConfigStep("apply install tuning","install_tuning")` already typed (`:303-308`) | - |
| `installer/receipts.py` | UNCHANGED | terminal keys never used the ledger (grep: no terminal reference); the record file is the "installer wrote this once" proof, same as Alacritty | - |
| `.claude/skills/tool-onboarding/SKILL.md` | MODIFIED (phase 1) | Replace "ask the user" bullet (`:185-191`) with rules; states per-OS table | - |
| `.claude/architecture.md` | MODIFIED | One paragraph: terminal keys are install tuning through `TERMINAL_KEYS`; the tests/test_docs install-tuning phrase lists may need the new sentence | `tests/test_docs.py` |

### Data Flow

Apply (install, reinstall): engine success -> `run_post_install` (`post_install.py:455-472`) -> `_apply_terminal_tuning(tool, platform)` -> `TERMINAL_KEYS[tool.id]` -> `apply_terminal_keys(skip_recorded=False)` -> read config via `read_settings`, `render(platform.os, outside_text)`, `_replace_owned_region`, validate, `write_if_unchanged`, write record. No platform gate in this path, so macOS works unchanged.

Drift: refresh pass -> `_tuning_fact` (`version_status.py:775`) -> `terminal_keys_pending` -> `KEYS_PENDING` gives `≈ apply install tuning` with the typed step; a non-pending refusal is a reason with no step (`:821-834` logic, unchanged). RECONFIGURE -> `session._install_tuning_step` -> `apply_install_tuning(skip_recorded=True)` -> record exists means a user-deleted region stays deleted.

Uninstall: `app.py:625-640` sweep -> `strip_terminal_keys` strips region and record before `config_paths` deletion (the comment at `app.py:625-626` states the same ordering for herdr).

Shell sync is a SEPARATE flow and stays that way: `sync_terminal_shells` (`terminal_shell.py:893`), drift via `compose.py:419` `write=False`, rows via `_TERMINAL_ROWS`. Keys do not run through it.

## macOS

`sync_terminal_shells` returns `TerminalShellResult(skipped=("macos",))` at `terminal_shell.py:915-916`, before anything else. That is correct for shell sync (macOS terminals start the account login shell, zsh by default) and must not change. Keys on macOS need nothing from the sync: `_apply_terminal_tuning`, `_terminal_tuning_fact` and the uninstall sweep are platform-agnostic callers. The only change is that `render` takes `platform.os` and returns the macOS rows (Option+Left/Right word navigation, Cmd+K) versus the Linux rows (Ctrl+Shift+K). Per-OS content therefore lives in the spec's renderer, not in a new platform branch of the sync.

Consequences:
- Alacritty today writes `Alt+Left/Right` unconditionally (`_KEY_BINDINGS` `:477-481`), plus Control+Shift+K. If the owner rule is "word navigation on macOS only, clear per OS", its Linux word-nav rows are now off-rule; decide in phase 2 (keep for compatibility vs drop and migrate). Alacritty has no macOS method in the registry, so the macOS row set is dead for it.
- kitty and WezTerm have macOS methods (registry `:3045-3063`, `:3129`), so their macOS rows are live.
- Config path resolution is XDG-only (`_kitty_config_path` `:156`, `_wezterm_config_path` `:165`). kitty and WezTerm on macOS also honor these, but verify kitty's macOS precedence (`~/Library/Preferences/kitty/kitty.conf`) in phase research before writing there.

## Per-terminal notes

| Terminal | Mechanism | Region/ownership | Notes and flags |
|---|---|---|---|
| Alacritty | TOML `[[keyboard.bindings]]`, tomllib parse | `alacritty-keys` region (exists) | becomes spec row 1; keep tests green unchanged first (pure move) |
| kitty | `map` lines in kitty.conf, `#` comment region | `kitty-keys` in the same file as the existing `kitty` shell region (`terminal_shell.py:949-961`) | Conflict check by text scan of `map <combo>` outside regions (no parser; house doctrine, architecture.md 15.8). kitty ships defaults for Ctrl+Shift+K (scroll) and on macOS Cmd+K clears; MEDIUM confidence, verify before choosing to write, skip, or override. Backlog 999.19 already flags this |
| WezTerm | Lua; append via `table.insert`/`config.keys = config.keys or {}` before `return config` | `wezterm-keys` region with `--` comment, inserted by the same boundary logic as `_wezterm_content` (`:180-208`) | Lua cannot be parsed; refuse when the file has no single `return config` (same as shell region), detect user `config.keys` by text and merge by append only. WezTerm key-tables first-match semantics need verification |
| Ghostty | `~/.config/ghostty/config` key=value, `#` comments, `keybind = ...`; Linux zsh via `command = ` | `ghostty-keys` plus a `ghostty` shell region (new branch in `sync_terminal_shells`, new `_TERMINAL_ROWS` entry) | macOS path differs (`~/Library/Application Support/com.mitchellh.ghostty/config`); Ghostty has its own option-as-alt and clear defaults, so the macOS rows may reduce to a no-op: verify upstream |
| iTerm2 | Dynamic Profile JSON in `~/Library/Application Support/iTerm2/DynamicProfiles/` | Whole-file ownership (JSON has no comments): ownership proof is a fixed `Guid`/`Name` the installer wrote; strip = delete the file if the proof matches | `KeysSpec` needs a `whole_file` mode (render returns full file, strip deletes). Dynamic profile is not default by itself and iTerm2 prefs are live; making it default is a separate, risky `defaults write`: flag for phase research. Cmd+K already clears in iTerm2. The two customizations the owner has not named (todo items 4-5) block that part |
| Konsole | Profile `KeyBindings=` plus an installer-owned keytab file in the profile the installer already owns (`tools-installer-zsh.profile`, `_sync_konsole` `:359-407`) | Not a catalog tool: no `post_install` hook, no `Tool` row. Extend `_sync_konsole`/`_revert_konsole` (`:410`) and let drift ride the existing `_TERMINAL_ROWS["konsole"] -> zsh` row | Owner decision first (todo 2026-11-16-terminal-defaults-for-konsole). Konsole's own default for clear-scrollback shortcuts is unverified (LOW): may need no change. Stays out of `TERMINAL_KEYS` because the table is keyed by tool id |
| herdr (multiplexer) | Pass-through check only | none | todo `terminal-defaults-for-herdr`; verification, no code expected |
| Herdr IDE | New registry entry; shares `~/.config/herdr` with the multiplexer entry (`registry.toml:3228` `config_paths`) | decide after upstream research | Do not give it `apply_terminal_tuning` until it is confirmed to host a terminal with config files; collision with the herdr entry's ledger-owned keys must be checked (`app.py:621-624`) |

## Patterns to Follow

### Pattern 1: One lifecycle, per-terminal renderers
**What:** the table row owns format knowledge; shared code owns record, skip_recorded, dry-run pending, strip, compare-before-commit.
**When:** every terminal with a text config file and comment-safe regions.
**Example:**
```python
spec = TERMINAL_KEYS[tool.id]            # post_install.py
lines, refused = apply_terminal_keys(spec, platform.os, Path.home(), os.environ, skip_recorded=skip_recorded)
```

### Pattern 2: Detect and merge, never overwrite; refuse what is not provably simple
**What:** conflicts become `partial:` warnings (as `_keys_plan` `:583-601`), unparseable or import-using files become a refusal with no write (`_IMPORTS` `:550`).
**When:** always; this is the architecture.md D-01a / 15.8 doctrine.

### Pattern 3: Keys follow the tool, shell follows zsh
**What:** the keys region is stripped when the TOOL is removed (`app.py:630`), the shell region when ZSH is removed (`_revert_terminal_shells` `:854`). Never merge the two lifecycles.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Routing keys through `sync_terminal_shells`
**Why bad:** it is Linux-only, zsh-gated, and the `≈` it reports is the shell fact; macOS and zsh-less hosts would lose keys, and drift would conflate two facts.
**Instead:** keep the `apply_terminal_tuning` post_install path.

### Anti-Pattern 2: A second record or ledger scheme
**Why bad:** receipts/ledger are for agent settings keys (`receipts.CONFIG_AGENTS`). A new ledger for text regions duplicates the record-file proof that already works.
**Instead:** `terminal-tuning-<id>` record files under the XDG data dir.

### Anti-Pattern 3: A new `POST_INSTALL_ACTIONS` name per terminal
**Why bad:** widens the closed set (`model.py:130`) and the validation, three dispatch tables change per terminal.
**Instead:** reuse `apply_terminal_tuning`; the tool id selects the row.

### Anti-Pattern 4: Parsing Lua or kitty.conf
**Why bad:** house doctrine is detect-by-normalization and refuse; a half-parser mis-detects user bindings.
**Instead:** text scan for the specific combos, refuse on anything not simple.

## Suggested Build Order

1. **Tool-onboarding skill rewrite (999.18).** Pure docs; carries the rules and the per-OS table the later phases implement. Run skill-judge before and after (standing rule). No code dependency. Dependent: everything else is "run through this skill".
2. **Shared mechanism, behavior-preserving.** Create `terminal_keys.py`, move Alacritty into row 1, make the three dispatch sites table-driven (`post_install.py:393`, `version_status.py:783/821`, `app.py:630`), add the registry test that every tool declaring `apply_terminal_tuning` has a `TERMINAL_KEYS` row. Existing Alacritty tests must pass without edits to assertions. This is the only phase that touches shared code, so it gates the rest.
3. **kitty and WezTerm** (Linux and macOS rows, registry `post_install`, drift, strip, tests with scratch HOME; macOS rows tested by passing `platform.os="macos"`). Konsole in this phase only if the owner decides yes; implemented in `_sync_konsole`, independent of the table, can run parallel to kitty/WezTerm. herdr pass-through is a check, parallel.
4. **New terminal entries:** Ghostty first (text config, fits the table, adds a shell branch to the sync). iTerm2 next (needs the whole-file mode in `KeysSpec`; macOS-only; owner items 4-5 unresolved). Herdr IDE last (upstream research decides if it is a terminal at all).
5. **Non-terminal onboardings** (Xcode CLT, Bruno, AWS CLI, gh-stack, Playwright MCP) go through the skill, independent of the mechanism; can run in parallel with 3-4 once phase 1 lands. Playwright MCP is `ai` tier and may need a `postinstall` hook per the architecture.md decision tree.

Why this order: phase 1 defines the rules; phase 2 removes the per-terminal cost before it is paid four times; whole-file mode (iTerm2) is added only when a row needs it, per rule 5 (no helper for later).

## Scalability Considerations

| Concern | One terminal (today) | 5-6 terminals | New terminal later |
|---|---|---|---|
| Dispatch edits | 3 sites hard-coded | 3 sites table-driven | one table row plus registry line |
| Test surface | per-terminal copy of apply/pending/strip tests | parametrized lifecycle tests plus per-row renderer tests | one renderer test |
| Drift | one `≈` fact | same fact, per tool id | same |

## Risks and Pitfalls specific to integration

- **kitty/WezTerm created-config cleanup:** the shell sync creates the files with no created-marker, so strip never deletes them. Keys regions strip cleanly; leave file deletion out of scope (shortcut: Alacritty-only created marker, upgrade if a terminal's file is keys-only).
- **Region name collisions:** `_marker` (`:98`) fixes the text `terminal-shell <name>`; region names `kitty` vs `kitty-keys` differ by exact match, so they do not collide (`_replace_owned_region` compares whole marker lines). Keep names exact.
- **WezTerm region ordering:** two regions before `return config`; the `"tools-installer terminal-shell wezterm" in existing` substring test at `:195` also matches `wezterm-keys`? It does not (`wezterm-keys` markers contain `wezterm-keys`, the substring `terminal-shell wezterm` followed by `-keys` still matches the prefix). Tighten that check to the exact marker lines when adding the keys region, or the shell sync will think its region exists when only the keys region does.
- **Existing hosts:** a kitty already shell-synced has no keys record, so it shows `≈ apply install tuning` after upgrade. This is the intended migration, not a bug, and the user's RECONFIGURE writes it.
- **macOS Alacritty rows:** dead until Alacritty gets a macOS method.
- **Docs gates:** `tests/test_docs.py` pins install-tuning phrases from architecture.md; edit both together.

## Sources

- Code read: `installer/terminal_shell.py` (`:98-139`, `:151-208`, `:359-460`, `:465-768`, `:854-1031`), `installer/post_install.py:383-472`, `installer/version_status.py:735-741, 775-834`, `installer/app.py:615-640`, `installer/compose.py:355-430`, `installer/model.py:130-141`, `installer/registry.toml:3016, 3104, 3163-3164, 3228`, `.claude/architecture.md` (install-tuning decision tree, 15.8 refuse-not-parse doctrine), `.claude/skills/tool-onboarding/SKILL.md:175-200`, ROADMAP backlog 999.18-999.22, todos `2026-11-16-terminal-defaults-for-*`, completed iTerm2 todo.
- Per-terminal key syntax and defaults (kitty `map`/default Ctrl+Shift+K, WezTerm key tables, Ghostty `keybind`, iTerm2 Dynamic Profiles, Konsole keytab): from prior knowledge, MEDIUM/LOW, not verified upstream in this pass; each phase must verify against vendor docs before writing.
