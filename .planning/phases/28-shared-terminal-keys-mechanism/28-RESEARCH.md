# Phase 28: Shared terminal-keys mechanism - Research

**Researched:** 2026-11-20
**Domain:** Python refactor (uv, pyright strict, pytest) of an installer-owned config-region lifecycle, plus one managed zsh widget
**Confidence:** HIGH (every code claim below was read this session; the few unverified items are in the Assumptions Log)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01**: `TERMINAL_KEYS: dict[str, KeysRow]` keyed by registry tool id, the row not repeating the id. The record path comes from the key, so the record keeps today's names (`terminal-tuning-alacritty`, `terminal-alacritty-created`). Generic `apply_terminal_keys(row, platform_os, home, environ, *, skip_recorded)`, `terminal_keys_pending(...)` and `strip_terminal_keys(...)` are today's Alacritty bodies with the row's fields substituted. Changing the record names would make every existing Alacritty install read `≈` again.
- **D-02**: Today's success and refusal text stays. The refusal becomes `f"{tool.name} keys not changed: {refused}"` (`tool.name` is `"Alacritty"`); the success line is a row field `summary`. `_apply_terminal_tuning` stops discarding `tool` and `platform`. `tests/test_post_install.py:1129-1141` asserts the exact refusal line, so it must pass unedited.
- **D-03**: Row fields: `ownership` (typed union, one variant now, `OwnedRegion(region, comment)`; a `WholeFile(proof)` variant and a per-key variant are added in phase 31 without a rewrite), `config_path(platform_os, home, environ)`, `plan(platform_os, file_text) -> KeysPlan` (body, conflicts, refusal), `validate` (the TOML re-parse), `summary`, `sibling_regions` (`("alacritty",)`: stripped with the tool, left out of the "outside" text), `created_record`, `same_directory` (required), `clear` (default "send Ctrl+L", Alacritty overrides it with `ClearHistory`; phase 29 adds `placement` and a per-row `validate`).
- **D-04**: Dispatch sites: `post_install._tune_terminal` -> `TERMINAL_KEYS[tool.id]`; `version_status._terminal_tuning_fact(tool)` -> `TERMINAL_KEYS.get(tool.id)` (no row, no fact); `app._after_removal` -> `strip_terminal_keys` when a row exists. `KEYS_PENDING` moves with the mechanism; `version_status` keeps its own `TUNING_PENDING` (same text). `_TERMINAL_ROWS["alacritty"]` (`version_status.py:738`) is shell-sync drift and stays.
- **D-05**: Import direction is `terminal_shell` -> `terminal_keys`. The shared primitives move down into a small lower module `installer/terminal_regions.py` with public names (`_replace_owned_region`, `_marker`, `TerminalShellError`, `_xdg_config_home`, `_xdg_data_home`, `_snapshot_text`, `_first_line`, the compare-before-commit strip helper, `_commit_alacritty` with the created marker, `_imports_files`, `alacritty_config_path`, `_keys_plan`/`_user_document`). `terminal_shell` imports them under their current local names so Konsole, kitty, WezTerm and herdr bodies stay byte-unchanged; `_read_text`, `_write_if_changed`, `_shell_plan`, `_sync_alacritty` stay in `terminal_shell`.
- **D-06 (FLAGGED, needs confirmation)**: "Pending" means no record and no region; "drifted" means a region is present and its bytes differ from the current render; a reconfigure rewrites a present, stale region; a region the user deleted after a recorded install stays the user's choice. Amends KEYS-02 / SPEC R2 / ROADMAP criterion 2. Provisional: research it, do not override it.
- **D-07**: The Ctrl+L widget is a shell-init bundle owned by the `zsh` registry tool: `"zsh"` added to `SHELL_INIT_TOOLS` (`installer/tweaks.py:90`), a `_shell_init("zsh", ...)` bundle in `BUNDLES`, zsh's registry entry gets `post_install = ["source_shell_init"]`. Not a Policies row.
- **D-08**: Widget text guarded for bash, binds in `emacs`, `viins` and `vicmd`: `tools_installer_clear_all` prints `\033[H\033[2J`, runs `zle .reset-prompt` and `zle -R`, then prints `\033[3J`, all to the terminal.
- **D-09**: Widget test has two layers: always a pty-free bytes check on the rendered block (`ESC[H ESC[2J` before `ESC[3J`, bash guard, bindings, apply then strip returns a scratch rc file to identical bytes); backstop `zsh -n` and an optional pty probe, skipped when zsh is absent.
- **D-10**: Golden bytes land in a commit before the move. A new `tests/test_terminal_keys.py` pins the bytes through public routes only (`run_post_install`, `sync_terminal_shells`, `app._after_removal`).
- **D-11**: The completeness test is a pure helper over id sets, run on `load_tools(REGISTRY)` and on a tmp fixture registry with an extra tool (must fail); also checks the reverse and that no key is `konsole`. Not enforced at runtime in `model.py`.
- **D-12**: Existing tests stay unedited except four in-function import lines (`tests/test_terminal_shell.py:1220,1254,1323,1648`). No re-export is left in `terminal_shell`.
- **D-13**: Fixture rows for KEYS-03 and KEYS-04 live only in the new test file (generic clear chord resolves to Ctrl+L `\x0c` per OS: `cmd+k` macOS, `ctrl+shift+k` Linux; a vendor/writes pair for same-directory). Alacritty keeps `ClearHistory` until phase 29.
- **D-14**: `same_directory` is a required field with no default, a typed value: vendor (nothing written), writes (carries the setting), not-applicable.
- **D-15**: Alacritty's row declares `vendor` with a dated note (`SpawnNewInstance` uses the foreground process cwd on Unix and macOS; `CreateNewWindow` stays `unverified` in the note).

### Claude's Discretion
- Names of the lower module's public functions, the `KeysPlan` field names, and the widget function name.

### Deferred Ideas (OUT OF SCOPE)
- Whether `ubuntu-latest` and `macos-latest` runners ship zsh (decides whether the zsh backstops run in CI), whether `zle .reset-prompt` plus `zle -R` redraws multi-line starship prompts correctly, and whether macOS Terminal.app and iTerm2 push the screen into scrollback on `ESC[2J`: checked in planning or the owner's Mac UAT.
- Out of scope (SPEC): Alacritty's clear flip (phase 29); kitty, WezTerm, Konsole, herdr rows (29); Ghostty, iTerm2, Herdr app (30-31); real-Mac checks; changing the wording of `≈ apply install tuning`.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KEYS-01 | One shared mechanism keyed by registry tool id applies/checks/strips each terminal's owned keys region; Alacritty moves in first, behavior and tests unchanged | Code inventory (Section "Where the Alacritty keys region lives today"), golden bytes captured live, D-05 module split and the two extra pins found (Pitfalls 1, 2) |
| KEYS-02 | Missing or drifted region reads `≈ apply install tuning`, reconfigure re-applies, uninstall strips; completeness test | D-06 algorithm in "Pending, drift and re-apply", dispatch sites, completeness helper |
| KEYS-03 | Clear chord = Ctrl+L on every row; managed zsh makes Ctrl+L clear screen and scrollback | Widget probe output (live), shell-init bundle machinery, the one existing test that pins BUNDLES order |
| KEYS-04 | Every row declares the vendor same-directory behavior; installer writes only where it does not | Required typed field, dataclass-fields test, fixture pair |
</phase_requirements>

## Summary

Phase 28 is a behavior-preserving move plus two small new things. The Alacritty keys lifecycle is 4 functions and 6 constants in `installer/terminal_shell.py` (`apply_alacritty_keys` :671, `alacritty_keys_pending` :710, `strip_alacritty` :726, `_keys_plan` :583, `_commit_alacritty` :604) wired to exactly three dispatch sites (`post_install.py:387`, `version_status.py:821-833`, `app.py:630-631`). All three become a lookup in `TERMINAL_KEYS` keyed by registry tool id. I captured the current bytes live in a scratch HOME: they match the CONTEXT D-10 bytes exactly, and the record files are `written\n` and `created\n<abs dir>\n<abs dir>\n` (the created marker holds home-dependent absolute paths, so a golden test must normalize it).

The design in CONTEXT is sound and fits house patterns (closed `Final[dict]` tables, frozen dataclasses like `Schedule`, `SettingKey`). Research found four things the CONTEXT does not mention: (1) `tests/test_tool_onboarding_skill.py:378-381` reads the SOURCE of `installer/terminal_shell.py` and asserts the literal `alacritty: partial: you already bind` is in it, which the move breaks; (2) adding `zsh` to the shell-init bundles breaks exactly one existing test, `tests/test_tweaks.py:48` (`test_bundles_have_stable_ids_and_order`), verified by running the suite in a scratch copy; (3) D-06 needs a refusal/read-error policy for the "record exists and region present" path that today never reads the file; (4) a registry tool with `apply_terminal_tuning` and no row must fail closed at runtime, not raise a bare `KeyError` in `apply_install_tuning`, which has no try/except. The widget bytes were probed live in zsh 5.9.2 under a pty and the order is `ESC[H ESC[2J ... ESC[3J` as D-08 says.

**Primary recommendation:** Build in this order, each step one green commit: (a) golden-bytes test file on pre-move code (D-10); (b) `terminal_regions.py` extraction with `terminal_shell` re-importing, no behavior change; (c) `terminal_keys.py` with `KeysRow`, Alacritty row, generic apply/pending/strip plus D-06 drift and the three dispatch sites; (d) completeness, clear-chord and same-directory tests; (e) zsh widget bundle with its bytes test. Treat the two test edits found here (`test_tool_onboarding_skill.py` source-path, `test_tweaks.py:48` id list) as explicit, owner-visible exceptions to D-12.

## Architectural Responsibility Map

This is a local CLI/TUI installer, not a web app; tiers map to the installer's own layers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Keys region render, conflict check, refusal (per terminal) | `installer/terminal_keys.py` row (`plan`) | `installer/terminal_regions.py` (primitives) | Row owns format; primitives are format-neutral marker/commit code |
| Region replace/strip, compare-before-commit write, created-file marker | `installer/terminal_regions.py` (new lower module) | `installer/agent_settings.py` (`read_settings`, `write_if_unchanged`, `missing_dirs`) | Lets both `terminal_shell` (sync conflicts) and `terminal_keys` use them without a cycle (D-05) |
| Dispatch from install/reconfigure | `installer/post_install.py` | `installer/session.py` (`_install_tuning_step`) | `apply_install_tuning` is the one reconfigure entry |
| `≈ apply install tuning` fact | `installer/version_status.py` (`_tuning_fact`) | `terminal_keys.terminal_keys_pending` | Read-only secondary fact, must never fail the pass |
| Strip with the tool | `installer/app.py` (`_after_removal`) | `terminal_keys.strip_terminal_keys` | Both removal routes (`app.py:1068`, `:1269`) call `_after_removal` |
| Ctrl+L clear widget | `installer/tweaks.py` shell-init bundle in `~/.myshellrc` | `post_install._tune_shell_init`, `version_status._shell_init_tuning_fact` | Reuses marker block, record, `≈`, reconfigure, strip-on-removal |
| Completeness / same-directory / clear-chord guarantees | `tests/test_terminal_keys.py` | `installer/terminal_keys.py` (required field, public table) | Test-only enforcement per D-11 |

## Standard Stack

No new libraries. Everything is stdlib plus modules already in the repo.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses`, `tomllib`, `re`, `pathlib` | 3.11 floor (`pyproject.toml` `requires-python = ">=3.11"`, `[tool.pyright] pythonVersion = "3.11"`) | Frozen `KeysRow`, TOML re-parse, region markers | Same shape as `Schedule` (`installer/schedules.py:43-52`) and `SettingKey` (`installer/agent_settings.py:624-631`) [VERIFIED: files read] |
| `installer.agent_settings` | in repo | `read_settings`, `write_if_unchanged`, `missing_dirs`, `remove_created_dirs`, `FileSnapshot` use | Existing compare-before-commit primitives, reused as is [VERIFIED: terminal_shell.py:18-31] |
| `installer.atomic.atomic_write_text` | in repo | Record and marker writes | Single sibling-temp+`os.replace` implementation [CITED: .claude/architecture.md Phase 12] |
| pytest (+xdist, coverage) | `fail_under = 90`, `addopts = "-q"` | Tests | [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Final[dict[str, KeysRow]]` | per-terminal functions | Repeats the three dispatch edits and the record/skip/pending/strip lifecycle per terminal (`.planning/research/ARCHITECTURE.md` makes the same argument); rejected by D-01 |
| Typed union for `ownership` | flat fields plus a flag | jev low confidence 0.50 favored flat; CONTEXT chose union for phase 31's whole-file/per-key modes. Keep the union, but keep it to one tiny variant now (see Pitfall 8) |

**Installation:** none. **Package Legitimacy Audit:** no external packages are installed by this phase, so the audit table is not applicable (verified: the plan adds only repo-local modules).

## Architecture Patterns

### Where the Alacritty keys region lives today (inventory, all read this session)

Format of the region [VERIFIED: `installer/terminal_shell.py:98-99,133`]: `_marker(terminal, edge, comment="#")` returns `"# >>> tools-installer terminal-shell alacritty-keys >>>"` / `"# <<< ... <<<"`; `_replace_owned_region` writes `f"{begin}\n{body}\n{end}\n"`, appended after a newline-terminated prefix when absent, replaced in place when present, and raises `TerminalShellError("malformed {terminal} ownership region")` on a nested, orphaned or duplicate marker (:112-125).

Body [VERIFIED: `terminal_shell.py:478-482,596-601`]:
```
_KEY_BINDINGS = (
    ("Left", "Alt", 'chars = "\\u001bb"'),
    ("Right", "Alt", 'chars = "\\u001bf"'),
    ("K", "Control|Shift", 'action = "ClearHistory"'),
)
```
rendered per binding as `[[keyboard.bindings]]\nkey = "{key}"\nmods = "{mods}"\n{action}` joined by `"\n\n"`. Live capture in a scratch HOME (run_post_install on the shipped alacritty tool, fedora):
```
'# >>> tools-installer terminal-shell alacritty-keys >>>\n[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "\\u001bb"\n\n[[keyboard.bindings]]\nkey = "Right"\nmods = "Alt"\nchars = "\\u001bf"\n\n[[keyboard.bindings]]\nkey = "K"\nmods = "Control|Shift"\naction = "ClearHistory"\n# <<< tools-installer terminal-shell alacritty-keys <<<\n'
```
Files written: `.config/alacritty/alacritty.toml`, `.local/share/tools-installer/terminal-tuning-alacritty` (content `written\n`), `.local/share/tools-installer/terminal-alacritty-created` (content `created\n<abs ~/.config>\n<abs ~/.config/alacritty>\n`). The marker holds absolute scratch-HOME paths, so a golden test must compare the config bytes and `written\n` exactly and normalize or only structurally check the marker. Success line captured: `'Alacritty keys: Alt+Left and Alt+Right move by word, Control+Shift+K clears history.'` (becomes the row `summary`). Same line is at `terminal_shell.py:702-706`.

| Concern | Today | Evidence |
|---|---|---|
| Apply | `apply_alacritty_keys(home, environ, *, skip_recorded)`; returns early `(), None` if `skip_recorded and record.exists()` before reading anything | `terminal_shell.py:671-707` (early return :679-680) |
| Pending | `alacritty_keys_pending`: `None` if record exists; reads file; `None` if region present; else `plan.refusal or KEYS_PENDING`; an `OSError` becomes `_first_line(exc)` | `terminal_shell.py:710-723` |
| Strip | `strip_alacritty` strips BOTH `ALACRITTY` (shell) and `ALACRITTY_KEYS`, unlinks the record only if no warnings, then `_drop_created_config` deletes the file the installer created once only whitespace is left, plus the directories it created | `terminal_shell.py:726-757` |
| Shell sync also uses the keys plan | `_sync_alacritty` appends `_keys_plan(document, outside).conflicts` to its warnings, and `_user_document` strips both regions before parsing | `terminal_shell.py:528-536,643` |
| Shell-region revert on zsh removal reuses the strip helper | `_revert_terminal_shells` calls `_strip_alacritty_region(path, ALACRITTY)` | `terminal_shell.py:879` |
| Created-file marker written inside the commit | `_commit_alacritty` writes `created_marker` when `before is None` | `terminal_shell.py:604-630` |
| Dispatch 1 | `_tune_terminal(*, skip_recorded)` calls `apply_alacritty_keys`, formats `f"Alacritty keys not changed: {refused}"`; `_apply_terminal_tuning` does `del tool, platform`; `apply_install_tuning` branch at `name == "apply_terminal_tuning"` | `post_install.py:385-396,445-448`; table entry :420 |
| Dispatch 2 | `_tuning_fact` -> `_terminal_tuning_fact()` (no args) -> `alacritty_keys_pending`; `KEYS_PENDING` compared; `TUNING_PENDING = "install tuning not applied"` is the same string | `version_status.py:777-785,821-833,773`, import :111 |
| Dispatch 3 | `if tool.id == "alacritty": parts.append(SweepResult(warnings=strip_alacritty(...)))`; `_after_removal` is called from two removal routes | `app.py:630-631`, callers `:1068,:1269` |
| Reconfigure entry | `session._install_tuning_step` calls `apply_install_tuning(tool, platform, skip_recorded=True)`; a non-None `output.refused` fails the step | `session.py:351-361` |
| Registry | Only alacritty declares `post_install = ["apply_terminal_tuning"]`; `POST_INSTALL_ACTIONS` is a closed tuple including it | `registry.toml:3164`; `model.py:130-141` |

Not touched and must stay so: `_TERMINAL_ROWS["alacritty"] = ("alacritty", "Alacritty")` (`version_status.py:738`) is shell-sync drift; `_sync_konsole` / `_revert_konsole` (`terminal_shell.py:359-461`) stay byte-unchanged (SPEC R5). No receipts/ownership code touches terminal keys: `installer/receipts.py` only holds the tool receipts dir (:96) and `rg terminal-tuning|terminal-alacritty` over `installer/` (excluding `terminal_shell.py`) finds nothing, so the record files are the only ownership proof, as today.

### System Architecture Diagram

```
registry.toml: post_install = ["apply_terminal_tuning"]        (closed name, no command text)
        |
        v
 install route ──> run_post_install ──> _apply_terminal_tuning(tool, platform)
 reconfigure ───> session._install_tuning_step ─> apply_install_tuning(skip_recorded=True)
                                      \                 /
                                       v               v
                              post_install._tune_terminal(tool, platform, skip_recorded)
                                               |
                          TERMINAL_KEYS.get(tool.id) ── no row ──> refused="no keys row for <id>" (fail closed)
                                               |
                                               v
 terminal_keys.apply_terminal_keys(row, platform_os, home, environ, skip_recorded)
   record exists & skip_recorded? ─ region absent ─────────────> no-op  (user deleted: theirs)
        |                         └ region present, render == text ─> no-op
        |                         └ region present, render != text ─> rewrite (D-06 drift)
        v
   read_settings(path) -> text -> user_document(outside row region + siblings) -> row.plan(os, text)
        refusal -> (lines=(), refused)          conflicts -> lines
        v
   replace_owned_region(text, region, body) -> row.validate(updated) -> commit (compare-before-commit)
        -> created-marker when the file was new -> record "written\n"

 version_status._tuning_fact ──> terminal_keys.terminal_keys_pending(row,...) ──> None | KEYS_PENDING | reason
 app._after_removal ───────────> terminal_keys.strip_terminal_keys(row,...) ──> warnings
                                  (strips row region + sibling regions, record, created file)

 ~/.myshellrc (sourced by zsh and bash)
   zsh row: source_shell_init -> tweaks BUNDLES["zsh"] block (bash-guarded Ctrl+L widget)
```

### Recommended Project Structure
```
installer/
├── terminal_regions.py   # NEW: lower module, public primitives (no import of terminal_shell/terminal_keys)
├── terminal_keys.py      # NEW: OwnedRegion, SameDirectory union, KeysRow, KeysPlan, TERMINAL_KEYS, apply/pending/strip
├── terminal_shell.py     # MODIFIED: keys code removed; imports regions + the Alacritty plan for sync conflicts
├── post_install.py       # MODIFIED: _tune_terminal(tool, platform, ...) table-driven
├── version_status.py     # MODIFIED: _terminal_tuning_fact(tool)
├── app.py                # MODIFIED: strip via TERMINAL_KEYS
└── tweaks.py             # MODIFIED: zsh in SHELL_INIT_TOOLS + bundle
tests/
└── test_terminal_keys.py # NEW
```

### Pattern 1: Closed typed table (house style)
**What:** `Final[dict[str, Row]]` of frozen dataclasses with required fields, looked up by registry id. **Example from this repo:**
```python
# Source: installer/schedules.py:43-52 and :71 (read this session)
@dataclass(frozen=True)
class Schedule:
    id: str
    label: str
    kind: JobKind
    target: str | None
    default_interval: int
    default_start: str

SCHEDULES: Final[tuple[Schedule, ...]] = ( ... )
```
and `installer/agent_settings.py:732` `TUNING_GROUPS: Final[dict[str, tuple[str, ...]]]`. No `X = A | B` dataclass union exists in `installer/` today (`rg` for the shape found nothing), so the `ownership` and `same_directory` unions are new; use plain `@dataclass(frozen=True)` variants and an alias `SameDirectory = Vendor | Writes | NotApplicable`, narrowed with `isinstance` (pyright strict handles it). `KeyKind = Literal[...]` (`agent_settings.py:610-612`) is the repo's other closed-value idiom if a variant needs only a tag.

### Pattern 2: Row declaration sketch (names are Claude's discretion per CONTEXT)
```python
@dataclass(frozen=True)
class OwnedRegion:
    region: str          # "alacritty-keys"
    comment: str = "#"

@dataclass(frozen=True)
class Vendor:            # the vendor already opens it in the current directory; nothing is written
    note: str            # dated, e.g. "2026-11-19: SpawnNewInstance uses the foreground cwd; CreateNewWindow unverified"
@dataclass(frozen=True)
class Writes:            # installer writes it
    snippet: str         # appended to the body by the generic code (see Open Question 3)
@dataclass(frozen=True)
class NotApplicable:
    reason: str
SameDirectory = Vendor | Writes | NotApplicable

@dataclass(frozen=True)
class KeysPlan:
    body: str | None
    conflicts: tuple[str, ...] = ()
    refusal: str | None = None

@dataclass(frozen=True)
class KeysRow:
    ownership: OwnedRegion
    config_path: Callable[[str, Path, Mapping[str, str]], Path]
    plan: Callable[[str, str], KeysPlan]          # (platform_os, text outside the regions)
    validate: Callable[[str], None]               # raises TerminalShellError; Alacritty: tomllib re-parse
    summary: str
    created_record: str                           # "terminal-alacritty-created" (D-01 keeps the name)
    same_directory: SameDirectory                 # REQUIRED: no default
    sibling_regions: tuple[str, ...] = ()
    clear: ClearAction = SendCtrlL()              # Alacritty: ClearHistory until phase 29
```
Required fields must precede defaulted ones in a dataclass, so `same_directory` sits before `sibling_regions`/`clear`. Record name `terminal-tuning-<id>` derives from the dict key (D-01).

### Pattern 3: D-06 apply/pending algorithm (the only real logic change)
```python
# pseudo, replacing apply_alacritty_keys' early return (terminal_shell.py:679-680)
recorded = record.exists()
if skip_recorded and recorded:
    text = read(path)                      # new: this path used to read nothing
    if replace_owned_region(text, region, None) == text:   # region absent
        return (), None                    # the user deleted it: theirs (pinned by test_version_status.py:7054 and test_post_install.py:1114-1126)
    plan = row.plan(os, user_text_outside(text))
    if plan.refusal is not None or replace_owned_region(text, region, plan.body) == text:
        return (), None                    # cannot re-apply, or already current
    # present and stale: fall through to the normal write
```
`terminal_keys_pending` mirrors it: no record and no region -> `KEYS_PENDING` (or the refusal); record or region present -> `KEYS_PENDING` only when the region is present AND `replace_owned_region(text, region, plan.body) != text` AND the plan has no refusal; every other recorded case is `None`. Rationale for "refusal or read error with a present region is quiet (None)": today a recorded install is always quiet, and a reason-with-no-step row would newly turn MISCONFIGURED for an existing install whose file the user later edited into a refusing shape (imports, inline bindings). Alternative is to surface the reason; flagged as Open Question 1.

Edge to cover in a test: a user adds an Alt+Left binding OUTSIDE the region after the install. The recorded plan then yields a smaller `body`, so the present region is stale; reconfigure rewrites it without the conflicting binding (the user's binding wins, which is today's rule for a first apply). That is correct, but it is a visible consequence of D-06 and should be stated in the plan.

### Anti-Patterns to Avoid
- **Importing `terminal_shell` from `terminal_keys`** (cycle; `terminal_shell` must import the Alacritty plan for sync conflicts) and **making cross-module underscore imports** (pyright strict `reportPrivateUsage`, `pyproject.toml` `[tool.pyright] typeCheckingMode = "strict"`). Public names in `terminal_regions.py` (D-05).
- **Moving `_read_text` / `_write_if_changed`.** Tests monkeypatch `terminal_shell.atomic_write_text` and `terminal_shell.ensure_zshrc_template` (`tests/test_terminal_shell.py:184-196`) and `terminal_shell.read_settings` (:1276-1283); those names must keep resolving in `terminal_shell` for the code those tests drive (`_sync_alacritty`, kitty, wezterm). `terminal_shell.py` still uses all three itself after the move (lines 319, 404, 639, 660, 717, 748, 785 today), so the imports stay and ruff F401 stays quiet.
- **A runtime `KeyError`.** See Pitfall 4.
- **Branching on `tool.id == "alacritty"` anywhere for key handling.** The SPEC check is `rg 'alacritty'` over the three files; expected survivors are only prose, the `Alacritty keys not changed` removal, and `_TERMINAL_ROWS` (:738, reviewer judgment per D-04).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Marker region replace/strip | A second regex/marker parser | `_replace_owned_region` (moved, unchanged) | Handles nested/orphan/duplicate markers, CRLF, missing trailing newline |
| Safe write | Direct `write_text` | `read_settings` + `write_if_unchanged` (raises `SettingsChanged` "changed while being written") and `atomic_write_text` | Race backstop pinned by `test_alacritty_changed_before_commit_is_refused` (:1271) |
| Created-file cleanup | New delete logic | `_drop_created_config` + `missing_dirs`/`remove_created_dirs` (generalize `warning` prefix from `"alacritty:"` to the row's name) | Edge cases pinned by 5 tests at :1553-1612 |
| zsh clear widget persistence | A new rc writer | `tweaks.BUNDLES` + `source_shell_init` | Gives marker block, written-once record, `≈`, reconfigure, strip on removal for free (D-07) |
| TOML validity | String checks | `tomllib.loads` re-parse in `row.validate` | Existing guard, pinned by `test_alacritty_region_that_would_not_reparse_is_refused` (:1292) |
| Registry-vs-table completeness | Runtime assertion in `model.py` | A pure helper over id sets in the test (D-11) | Avoids inverting layering |

**Key insight:** every hard edge (malformed markers, symlinks, UTF-8, FIFOs, race, created-file proof) is already solved by code that moves verbatim. The refactor's risk is changed names, texts and monkeypatch targets, not new algorithms.

## Runtime State Inventory

This phase renames nothing and migrates no stored string, but it moves the owner of existing on-disk state, so the categories are answered explicitly.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Record `~/.local/share/tools-installer/terminal-tuning-alacritty` (`written\n`) and created marker `terminal-alacritty-created` (`created\n<dirs>`) exist on every install that ran the action (`terminal_shell.py:475-476,500-506`) | None if the names are kept (D-01). Test must assert the two names verbatim; changing either re-flags every install `≈` |
| Live service config | None - verified: no external service holds terminal-keys config | None |
| OS-registered state | None - verified: `rg 'terminal-shell'` over `installer/` outside `terminal_shell.py` finds nothing; no unit/plist/task embeds it | None |
| Secrets/env vars | None. `XDG_CONFIG_HOME` / `XDG_DATA_HOME` are read via `environ` params, never new vars | None |
| Build artifacts | None (pure Python, no egg-info of renamed package) | None |
| Existing `~/.myshellrc` | zsh gets a NEW block `# >>> tools-installer tweak:zsh >>>` and a `zsh` id in the shell-init record (`tweaks.py:199-203,318-352`) | Code edit only; every present zsh reads `≈ apply install tuning` until reconfigure, as every phase 23.2 shell-init tool did. Mention in the plan SUMMARY |

## Common Pitfalls

### Pitfall 1: `tests/test_tool_onboarding_skill.py` reads `terminal_shell.py` source
**What goes wrong:** `test_conflicts_names_the_real_partial_lines` does `shell_source = (REPO_ROOT / "installer" / "terminal_shell.py").read_text(...)` and asserts `"alacritty: partial: you already bind" in shell_source` (`tests/test_tool_onboarding_skill.py:378-381`). That literal lives in `_keys_plan` (`terminal_shell.py:598`), which D-05 moves down, so the test fails after the move. The SKILL prose it also checks (`"installer/terminal_shell.py"`, `"phase 28"` at :372-375) still holds because `_sync_alacritty` keeps reporting the conflicts.
**Why it happens:** D-12 lists only four import lines as permitted test edits; this source-text grep was not found during discuss.
**How to avoid:** Change that one test to read the module that now holds the literal (`terminal_regions.py` if `_keys_plan` lands there, `terminal_keys.py` if the Alacritty plan does). It asserts a source substring, not behavior, so it is a path edit, not an assertion weakening. Record it in the plan as a D-12 exception. Alternative (rejected): keep a duplicate literal in `terminal_shell.py`, which duplicates formatting at two sites.
**Warning signs:** `test_tool_onboarding_skill.py` red right after the move.

### Pitfall 2: Adding `zsh` to the shell-init bundles breaks `tests/test_tweaks.py:48`
**What goes wrong:** `test_bundles_have_stable_ids_and_order` pins the full `BUNDLES` id list (`docker, countdown, apt-upgrade, starship, direnv, zoxide, fzf, fnm, volta, neovim`). I added `zsh` to `SHELL_INIT_TOOLS`, a `_shell_init("zsh", ...)` bundle and `post_install = ["source_shell_init"]` to zsh in a scratch copy and ran `tests/test_tweaks.py tests/test_version_status.py tests/test_policy.py tests/test_session.py tests/test_uninstall.py tests/test_registry.py tests/test_post_install.py` plus (earlier run) `tests/test_app.py tests/test_setup.py tests/test_policies_e2e.py`: exactly ONE failure, `test_bundles_have_stable_ids_and_order`.
**How to avoid:** Edit that id list (one line) and note it as a second D-12 exception. Place the zsh bundle and its `SHELL_INIT_TOOLS` entry in the same position: `test_shell_init_bundles_sit_after_apt_upgrade_in_tool_order` (`tests/test_tweaks.py:354-356`) requires `BUNDLES[start:start+len(SHELL_INIT_TOOLS)] == SHELL_INIT_TOOLS` contiguously after `apt-upgrade`. The same-position, first-entry choice passed in my copy.
**Also passing unedited (verified in the copy):** `test_each_shell_init_body_is_guarded_and_parses` (bundle `requires == (tool,)`, and `body.split("\n")[0] == "if command -v zsh >/dev/null; then"`), `test_each_shell_init_body_parses_in_zsh`, `test_the_six_tools_declare_shell_init`, `test_only_reviewed_tools_declare_a_post_install_action` (uses `*SHELL_INIT_TOOLS`), `test_each_shell_init_tool_writes_one_block_and_asks_nothing`. So the zsh body MUST start with the line `if command -v zsh >/dev/null; then` (the `_guarded_init` shape) and be valid `bash -n`.

### Pitfall 3: Golden marker file contains home-dependent paths
The created marker is `created\n<abs>\n<abs>\n` (captured live). Pin config bytes and record bytes exactly; for the marker assert the first line `created` and that the listed dirs are under `Path.home()`.

### Pitfall 4: A registry tool with the action but no row
`run_post_install` wraps each action in `try/except Exception` and reports `"{name} crashed: ..."` (`post_install.py:461-466`), but `apply_install_tuning` has no guard (:426-449) and `session._install_tuning_step` would propagate a `KeyError`. Use `TERMINAL_KEYS.get(tool.id)`; on `None` return `PostInstallOutput(("<Name> keys not changed: no keys row declared for <id>",), refused=...)`. The completeness test is the real guard (D-11); this is the runtime backstop and it has its own tiny test.

### Pitfall 5: `skip_recorded` early return means reconfigure never saw a changed region
Today reconfigure of a recorded Alacritty returns before reading (`terminal_shell.py:679-680`), so phase 29's `ClearHistory` -> Ctrl+L change could never reach existing installs. D-06 is what fixes it. Test the full loop: write region with an old body (a fixture row or a hand-edited region), call `terminal_keys_pending` -> `≈`, `apply_install_tuning(skip_recorded=True)` -> region equals the current render, a second call is a no-op (idempotent, SPEC edge R2).

### Pitfall 6: SPEC criterion 2 wording vs D-06
ROADMAP/SPEC text says "deleting a terminal's keys region makes its row read `≈`". Under D-06 that is true only with no record. A test that runs `run_post_install` first (which writes the record) and then deletes the region must assert the row does NOT read `≈` (pinned today at `tests/test_version_status.py:7054-7064`). The "deleting reads `≈`" case needs a scratch HOME where the action never ran (as `test_untuned_alacritty_reads_apply_install_tuning` does, :7067+). Keep both, and say so in the test names.

### Pitfall 7: Konsole must stay out, Alacritty clear stays `ClearHistory`
`TERMINAL_KEYS` must have no `konsole` key (asserted). Do not edit `_KEY_BINDINGS` bytes: phase 29 (TERM-03) flips the clear. A "send Ctrl+L" default on the row type is exercised only by the fixture rows in the new test file (D-13).

### Pitfall 8: Over-building the unions
Only `OwnedRegion` is used in this phase; `Writes` is used only by a fixture. Under `vulture` `min_confidence = 80` (`pyproject.toml`) unused classes are not flagged, and `.claude/architecture.md` rule 5 (no orphan helpers) is about functions with zero production callers; a `Writes` variant with zero production rows is exactly the kind of thing to keep minimal (a one-field dataclass, no helper machinery) and to justify by its test and phase 29/30 consumers.

### Pitfall 9: Multi-line prompt and `ESC[2J` behavior are unverified
`zle .reset-prompt` + `zle -R` with a multi-line starship prompt, and whether macOS Terminal.app/iTerm2 move the screen into scrollback on `ESC[2J`, are deferred (CONTEXT). The byte test proves the sequence, not the visual result; do not claim more in docs.

## Pending, drift and re-apply today (what D-06 touches)

| Place | Today | Under D-06 |
|---|---|---|
| `alacritty_keys_pending` (`terminal_shell.py:710-723`) | `None` if record or region exists | becomes `terminal_keys_pending`; region-present-and-stale is `KEYS_PENDING` |
| `apply_alacritty_keys` skip path (:679-680) | return before reading | read, rewrite only a present stale region |
| `version_status._terminal_tuning_fact` (:821-833) | `None` -> no fact; `KEYS_PENDING` -> `≈ apply install tuning`; other text -> reason with no step; exceptions -> `unchecked` note `keybindings not checked: ...` | same mapping; keep the broad `except Exception` (read-only fact never fails the pass) |
| `apply_install_tuning` (:426-449) | `refused` from `_tune_terminal` fails the reconfigure step (`session.py:357-358`) | unchanged shape |
| Pinned tests that must pass UNEDITED | `tests/test_version_status.py:7054` (user-deleted is theirs), `tests/test_post_install.py:1114-1126` (reconfigure respects deletion; install rewrites), `tests/test_post_install.py:1129-1141` (exact refusal line), `tests/test_terminal_shell.py` Alacritty block :1153-1344 and :1520-1660, `tests/test_setup.py:5140-5173` (update route repairs only the shell region and leaves the keys region byte-identical) | all remain true because the keys region equals its current render in each |

The three "present region is current" cases in those tests hold because they never change the user's outside-region content in a way that alters the plan.

## The managed zsh configuration and Ctrl+L

- **Where generated:** `installer/tweaks.py`. `SHELL_INIT_TOOLS = ("starship", "direnv", "zoxide", "fzf", "fnm", "volta", "neovim")` (:90); `_shell_init(tool, description, body, *, yields_to=())` returns `TweakBundle(tool, f"{tool} shell init", description, (), body, requires=(tool,), yields_to=yields_to)` (:116-121); `_guarded_init` builds the `if command -v <tool> >/dev/null; then ... fi` shape (:93-99); markers are `# >>> tools-installer tweak:<id> >>>` / `# <<< ... <<<` (:199-203). `shell_init_bundle(tool_id)` finds a bundle only when its id is in `SHELL_INIT_TOOLS` (:507-509).
- **Existing Ctrl+L binding:** none in `installer/` (SPEC Background; `rg bindkey` over `installer/` found no other emitter). zsh's default `^L` in the emacs keymap is `clear-screen`, so the widget overrides a default.
- **Flow reused:** write: `post_install._tune_shell_init` (:280-304) writes via `tweak_policy(...).apply()`, then `record_shell_init`; reconfigure with `skip_recorded=True` skips a recorded id (:296); `≈`: `version_status._shell_init_tuning_fact` (:788-800) reads marker presence or record; strip: `app._after_removal` (:633-637) sweeps the bundle and calls `forget_shell_init`; the Policies view is excluded by `compose.py:713` (`if bundle.id not in SHELL_INIT_TOOLS`). zsh is `tier = "system"` (`registry.toml:566`), so the installer never installs it; the block is written through the `≈` then reconfigure, and goes when zsh is removed.
- **Proposed body** (passes `bash -n`, shape satisfies the existing guarded-first-line pin), probed live below:
```sh
if command -v zsh >/dev/null; then
  if [ -n "$ZSH_VERSION" ]; then
    tools_installer_clear_all() {
      print -n '\033[H\033[2J'
      zle .reset-prompt
      zle -R
      print -n '\033[3J'
    }
    zle -N tools_installer_clear_all
    for keymap in emacs viins vicmd; do bindkey -M $keymap '^L' tools_installer_clear_all; done
  fi
fi
```
Python string note: `tweaks.py` uses raw strings for backslash-bearing bodies (comment at :51-54); the `\033` must reach the file literally, as `wait_time` already does (`_COUNTDOWN_BODY`/`_APT_BODY` use `r'...'`). The test then asserts the rendered block text contains the literal four characters `\033[H`, ... in the order `[H`, `[2J` before `[3J`, which is the byte-level check D-09 asks for (the file holds the escape SPELLING that zsh's `print` expands; it does not hold raw ESC bytes, so "emitted sequences" are proven by the pty probe, and the spelling by the always-on test).
- **Live probe** (zsh 5.9.2 under a Python pty, scratch HOME, `zsh -f -i`, sourced a file holding the widget, typed `abc`, sent `\x0c`): output bytes
`b'\x1b[H\x1b[2J\r\r\x1b[0m\x1b[27m\x1b[24m\x1b[Jabc\x1b[K\x1b[3J'`. `ESC[H ESC[2J` precede the redraw (buffer `abc` kept) and `ESC[3J` comes last, matching D-08. [VERIFIED: probe run in this session; script at `/tmp/claude-1000/.../scratchpad/p28/exp/probe.py`.]
- **How to test emitted sequences at byte level:** two layers (D-09). Always-on (no zsh needed): render `tweak_block(shell_init_bundle("zsh"))`, assert order and the guards, assert apply-then-strip leaves a scratch `~/.myshellrc` byte-identical (use `write_tweak`/`strip_tweak_block`, `tweaks.py:271-290`; `apply_block` replaces the last marker span). Backstop: `@pytest.mark.skipif(shutil.which("zsh") is None, reason=...)` (the same idiom as `tests/test_tweaks.py:373` and `tests/test_shellrc.py:708`) running `zsh -n -c <body>` and a pty probe like the one above using stdlib `pty`/`select`, with a bounded read loop and `os.waitpid`/kill in a `finally` (no leaked child, per the xdist rules in `.claude/testing.md`). This host has zsh (`/home/linuxbrew/.linuxbrew/bin/zsh`) so the backstop runs locally; whether CI runners ship zsh is `[ASSUMED]` (A3), which is exactly why the always-on layer exists.
- **Zsh `≈` side effect:** every present zsh reads `≈ apply install tuning` on first launch after upgrade; this is the established 23.2 pattern, not a bug.

## KEYS-04: same-directory declaration and its test

- **Declaration:** required dataclass field with no default (D-14) whose type is `Vendor | Writes | NotApplicable`; Alacritty declares `Vendor(note=...)` with the dated D-15 note (CONTEXT quotes upstream `CHANGELOG.md` lines 715-724 read via the GitHub API on 2026-11-19; I did not re-fetch it, so that fact is `[CITED: 28-CONTEXT.md D-15]`).
- **Enforcing tests (all in `tests/test_terminal_keys.py`):**
  1. `for f in dataclasses.fields(KeysRow): f is same_directory -> f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING` (fails if someone adds a default).
  2. every `TERMINAL_KEYS` row: `isinstance(row.same_directory, (Vendor, Writes, NotApplicable))`.
  3. constructing a `KeysRow` without the argument raises `TypeError` (a real undeclared case).
  4. the D-13 pair: a fixture row with `Vendor(...)` produces a body with no setting; a fixture row with `Writes(snippet)` produces exactly one occurrence of the snippet in the written region.
- Pyright strict also rejects a missing required argument at type-check time (`make typecheck`), a second line of defense.

## Docs-only, TEST_READ and LEDGER implications

- `devtools/docs_only.py`: `is_docs_path` is true for `.planning/*` or `*.md` paths NOT matching `TEST_READ` (`AGENTS.md`, `README.md`, `.claude/*`, `.github/*`, `docs/*`, `scripts/*`, `tests/*`, two SKILLJUDGE globs) (:20-36). New `installer/*.py` and `tests/*.py` files are never docs-only, so CI runs the full jobs for this phase. Editing `.claude/architecture.md` is in `TEST_READ` (`.claude/*`), so it also forces the full run, which is correct because `tests/test_docs.py` reads it.
- `tests/test_docs_only.py` `LEDGER` (:209-291) classifies every string literal in any `tests/*.py` that ends in `.md` or equals/starts with `.planning`; `test_every_markdown_literal_in_the_tests_is_classified` fails on a new unclassified pair or a stale one (:297-301). **`tests/test_terminal_keys.py` must contain no `.md` or `.planning` string literal** (docstrings are `ast.Constant` strings too: a docstring ending in `.md` would count), so no ledger edit is needed. If Pitfall 1's test edit changes `tests/test_tool_onboarding_skill.py`, keep its `.md` literals unchanged (it already has ledger rows at :243-258).
- `.claude/skills/tool-onboarding/SKILL.md` (:194-198, :220, :224) says the zsh Ctrl+L part is "planned for phase 28 (KEYS-03) and nothing in `installer/` does it today", and `tests/test_tool_onboarding_skill.py:225` pins the phrase `"planned for phase 28"`. After Phase 28 ships the widget that sentence is stale, but changing it needs a paired test edit. Recommendation: leave both for phase 29 when the first non-Alacritty rows land and the SKILL is rewritten as a whole; flag in Open Question 4.
- `tests/test_reachability.py` (`_installer_modules`, walks runtime imports from `setup.py`): the two new modules are reachable through `post_install`/`version_status`/`app` imports, no registration needed. `tests/test_registry.py:2631,2646` and `tests/test_executors.py:168` `rglob` over `installer/*.py` for scans (PATH-accumulation AST scan, executor scan): the new modules must not build PATH assignments; the zsh bundle body has none.

## Code Examples

### Completeness helper (D-11)
```python
# pure, over id sets; runs on load_tools(REGISTRY) and on a tmp fixture registry
def missing_rows(tools: Iterable[Tool], table: Mapping[str, object]) -> set[str]:
    return {t.id for t in tools if "apply_terminal_tuning" in t.post_install} - set(table)
```
Source: D-11, `installer/model.py:138` (`apply_terminal_tuning` is a member of `POST_INSTALL_ACTIONS`). The fixture-registry case needs a TOML written to `tmp_path` and loaded with `load_tools(path)`; reuse the `_write` / `_tool_block` helpers in `tests/test_model.py:1981` style (read at :1981) rather than a new loader. The reverse check (`set(table) - declarers == set()`) and `"konsole" not in table` complete it.

### Generic clear-chord fixture (D-13)
```python
# format-neutral chord table lives in terminal_keys; the fixture row proves the resolver
CLEAR_CHORD = {"macos": "cmd+k", "linux": "ctrl+shift+k"}   # any non-macos os is Linux
assert resolve_clear(SendCtrlL(), "macos") == ("cmd+k", "\x0c")
assert resolve_clear(SendCtrlL(), "fedora") == ("ctrl+shift+k", "\x0c")
```
`Platform.os` values for Linux are distro names (`fedora`, `debian`, `arch`; see `tests/test_terminal_shell.py:_platform` and `tweaks._LINUX = ("debian", "arch", "fedora")` at `tweaks.py:85`), so "not macos" is the Linux test, not `== "linux"`. The resolver is a tiny pure function; Alacritty's own row keeps `ClearHistory` so no production row consumes it this phase (acceptable: SPEC R3 says proved on a fixture row).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Alacritty-only keys functions, three id branches | Table keyed by registry tool id | This phase | phases 29-31 add rows, not dispatch edits |
| Recorded install = never re-read | Present stale region is drift (D-06) | This phase | phase 29's TERM-03 reaches existing installs by reconfigure |

**Deprecated/outdated:** `.planning/research/ARCHITECTURE.md:24,51` says `terminal_keys` imports from `terminal_shell`; D-05 reverses that (CONTEXT says so).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A recorded install whose file later refuses (imports/inline bindings) or fails to read should stay quiet (None) rather than show a reason | Pattern 3, Open Question 1 | If the owner wants the reason shown, the row turns MISCONFIGURED with no step for such users; one-line policy change |
| A2 | `Writes` carries a text snippet the generic code appends to the body, instead of each row's `plan` handling it | Pattern 2, Open Question 3 | Phase 29/30 formats may need placement control; D-03 amendment (29 D-11) adds `placement`, so likely compatible, but unproven until a second row exists |
| A3 | `ubuntu-latest` ships zsh; `macos-latest` ships zsh (system zsh) | Zsh section, Validation | If not, the zsh backstop tests skip in CI; the always-on layer still runs. `.github/workflows/ci.yml` installs no zsh (CONTEXT) |
| A4 | Updating `.claude/skills/tool-onboarding/SKILL.md` ("planned for phase 28") is deferred to phase 29 | Docs section | If the owner wants it fixed now, add a paired test edit at `tests/test_tool_onboarding_skill.py:225` |
| A5 | Alacritty `CreateNewWindow` behavior is unverified (as D-15 notes); `SpawnNewInstance` follows foreground cwd | KEYS-04 | Only affects the note text; installer writes nothing for Alacritty either way |
| A6 | Coverage stays >= 90 (`fail_under`) with the new modules because every branch has a test | Validation | A missed branch in `terminal_regions`/`terminal_keys` lowers coverage; `make test` would show it |

## Open Questions

1. **Refusal or unreadable file when a record exists and the region is present (D-06).**
   - Known: today that case is quiet (returns before reading). Reading it newly can raise (`TerminalShellError` is an `OSError`) or hit a refusal.
   - Unclear: whether the owner wants a reason line (no step) or quiet.
   - Recommendation: quiet (None), assert it with a test, note the D-06 "needs confirmation" flag still stands.
2. **Test-edit exceptions beyond D-12.** Two found: `tests/test_tool_onboarding_skill.py:378-381` (source path of the literal) and `tests/test_tweaks.py:48` (the bundle id list). Both are non-behavioral. Recommendation: do them in the commit that causes them, list them in the plan frontmatter/SUMMARY as "D-12 exceptions found in research".
3. **How `Writes` reaches the body.** Recommendation: `Writes(snippet)` appended by generic apply with a blank-line separator when the body exists; revisit when phase 29 adds `placement`.
4. **SKILL.md "planned for phase 28" sentence.** Recommendation: leave for phase 29 (A4).
5. **Where `_keys_plan` + `_KEY_BINDINGS` physically live.** D-05 lists `_keys_plan`/`_user_document` in the lower module, yet `_sync_alacritty` (in `terminal_shell`) needs the Alacritty conflicts and the Alacritty row (in `terminal_keys`) owns the bindings. Two consistent options: (a) the Alacritty `plan` function lives in `terminal_keys` and `terminal_shell` imports it (matches "terminal_shell -> terminal_keys"); (b) it lives in `terminal_regions`. Recommendation: (a), keep `terminal_regions` free of any terminal-specific bindings, and keep the `partial: you already bind` literal next to `_KEY_BINDINGS` so Pitfall 1's edit points at `terminal_keys.py`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all commands (`uv run pytest`, `make`) | yes | 0.11.28 | none needed |
| Python venv (`.venv`) | targeted tests | yes | 3.12.12 (project floor 3.11) | uv |
| zsh | widget `zsh -n` and pty probe tests | yes | 5.9.2 (`/home/linuxbrew/.linuxbrew/bin/zsh`) | tests skip with `reason=` (CI may lack it, A3) |
| bash | `bash -n` of the bundle body (existing test pattern) | yes | `/usr/bin/bash` | none needed |
| shellcheck | `make shellcheck` gate | not probed (gate covers `*.sh` files, not Python strings) | - | n/a |
| Real Mac | macOS clear behavior | no | - | deferred UAT line (owner's Mac), per CONTEXT |

**Missing dependencies with no fallback:** none. Nothing here runs `make run/fix/doctor/uninstall/dev-setup` (forbidden by AGENTS.md); all probes used a scratch HOME.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (+ pytest-xdist, coverage); `addopts = "-q"`, `testpaths = ["tests"]`, `fail_under = 90`, pyright strict includes `tests` [VERIFIED: pyproject.toml] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`; autouse scratch-HOME fixtures in `tests/conftest.py` (HOME per test, `Path.home()` is safe) |
| Quick run command | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_tweaks.py -q` (no `-n`; targeted while working per `.claude/testing.md`) |
| Full suite command | `make validate && make test` once after the plan (`pytest -n auto`, ~40% threads) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KEYS-01 | Region/records byte-identical (created, user content, adjacent binding, shell+keys together, strip) via public routes | integration (scratch HOME) | `uv run pytest tests/test_terminal_keys.py -q` | Wave 0 (new; lands BEFORE the move, green on old code) |
| KEYS-01 | Existing Alacritty/Konsole tests unedited (four import lines + Pitfall 1 path edit) | existing | `uv run pytest tests/test_terminal_shell.py tests/test_post_install.py tests/test_version_status.py -q -k "alacritty or terminal or konsole"` | yes |
| KEYS-01 | No `alacritty` id branch in the 3 dispatch files | static | a test or reviewer `rg -n 'alacritty' installer/post_install.py installer/version_status.py installer/app.py` (only prose and `_TERMINAL_ROWS`) | reviewer step |
| KEYS-02 | Pending: no record + no region -> `≈`; record + deleted -> OK; record + edited region -> `≈`; reconfigure restores; second reconfigure no-op | integration | `uv run pytest tests/test_terminal_keys.py -q -k "pending or drift or reconfigure"` | Wave 0 |
| KEYS-02 | Uninstall strips region(s), record, created file; user content kept | existing + new row-driven | `uv run pytest tests/test_terminal_shell.py -q -k removal` | yes (:1153-1344,1553-1612) |
| KEYS-02 | Completeness: tool with `apply_terminal_tuning` and no row fails; reverse; no `konsole`; empty table fails | unit (fixture registry in `tmp_path`) | `uv run pytest tests/test_terminal_keys.py -q -k completeness` | Wave 0 |
| KEYS-02 | Runtime backstop: no row -> refusal line, not a crash | unit | `uv run pytest tests/test_terminal_keys.py -q -k no_row` | Wave 0 |
| KEYS-03 | Clear chord -> Ctrl+L (`\x0c`) per OS on a fixture row; Alacritty keeps `ClearHistory` | unit | `uv run pytest tests/test_terminal_keys.py -q -k clear` | Wave 0 |
| KEYS-03 | zsh block text: `\033[H`, `\033[2J` before `\033[3J`, bash guard, three keymaps; apply then strip returns the rc file to identical bytes | unit | `uv run pytest tests/test_tweaks.py tests/test_terminal_keys.py -q -k zsh_clear` (place in whichever file owns tweak tests; one location) | Wave 0 |
| KEYS-03 | `zsh -n` plus pty probe (order `2J` then `3J`), skipped without zsh | integration | same, `skipif(shutil.which("zsh") is None, reason=...)` | Wave 0 |
| KEYS-03 | zsh row reads `≈` before apply, not after, reconfigure writes it, removal strips it | integration | `uv run pytest tests/test_version_status.py tests/test_post_install.py -q -k zsh` | Wave 0 (extend) |
| KEYS-04 | `same_directory` has no default; every row declares a valid value; omission is a `TypeError`; vendor writes nothing, writes writes once | unit | `uv run pytest tests/test_terminal_keys.py -q -k same_directory` | Wave 0 |
| Gates | ruff, format, pyright strict, bandit, vulture, shellcheck, coverage >= 90 | static | `make validate` then `make test` | existing |

### Sampling Rate
- **Per task commit:** the targeted quick command above for the files the task touched.
- **Per wave merge:** `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_tweaks.py tests/test_version_status.py tests/test_tool_onboarding_skill.py tests/test_registry.py tests/test_docs_only.py tests/test_reachability.py -q`.
- **Phase gate:** `make validate && make test` once on the exact tree to commit (AGENTS.md), then push-per-wave and watch CI.

### Wave 0 Gaps
- [ ] `tests/test_terminal_keys.py` - golden bytes (committed before the move), pending/drift/reconfigure, completeness, clear chord, same-directory, no-row backstop, `konsole` absent.
- [ ] A fixture-registry helper (tmp TOML with an extra `apply_terminal_tuning` tool) - reuse `load_tools` and an existing `_tool_block`-style writer; no new framework.
- [ ] No framework install needed (pytest/xdist/coverage present).

## Security Domain

`security_enforcement` is not set to false in `.planning/config.json` (the key is absent from the part read), so it applies.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | - |
| V3 Session Management | no | - |
| V4 Access Control | no (single-user local files); but never write outside owned regions | marker-delimited regions + compare-before-commit |
| V5 Input Validation | yes | `tomllib` re-parse before write; the registry selects an action NAME from the closed `POST_INSTALL_ACTIONS` tuple, never a command (`.claude/architecture.md` Phase 9 and 12.4 doctrine); `_read_text`-style capped, UTF-8-checked reads |
| V6 Cryptography | no | - |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Overwriting a user's file edited between read and write | Tampering | `FileSnapshot` + `write_if_unchanged` ("changed while being written"), unchanged |
| Malformed/duplicate markers deleting user text | Tampering | `_replace_owned_region` raises on nested/orphan/duplicate markers |
| Symlinked or FIFO config read | DoS / Tampering | capped non-blocking `read_capped`, UTF-8 refusal (existing) |
| Registry text becoming shell/TOML content | Tampering / Elevation | zsh widget and Alacritty bindings are code constants, no registry string reaches them (same invariant as `tweaks.py:87-89`) |
| Widget runs outside its block or survives removal | Tampering | single marker block, `forget_shell_init` + strip on removal; test asserts apply-then-strip identity |
| Any `sudo` | Elevation | none; AGENTS.md "Zero sudo" |

## Project Constraints (from CLAUDE.md)

`CLAUDE.md` is not present in the repo; the binding rules are `AGENTS.md` and `.claude/*.md` (read). Actionable directives:
- English only everywhere (code, comments, commits).
- uv owns the environment; never pip/poetry/conda. `make test` is `pytest -n auto`; never pass a fixed `-n`.
- Never bypass a gate: no `# noqa` / `# type: ignore` / `# nosec` / vulture whitelist without the narrowest scope, a why-comment, and user approval; pyright strict; no `skip`/`xfail` except with a legitimate `reason=` (the zsh skipif is such a case, matching existing idiom).
- Never mutate the developer's host: no `make run/fix/doctor/uninstall`, no mutating `systemctl --user`, no real shell rc edits; tests use a scratch HOME (autouse in `tests/conftest.py`). Agents never run `make dev-setup`. Zero sudo.
- Coherent commits; test-first inside ONE green commit; plans are `type: execute`, not `type: tdd` (`.claude/testing.md`); keep the RED output in the plan SUMMARY.
- Validate before commit: `make validate && make test` on the exact tree, once after a plan; targeted tests while working.
- Architecture rules (`.claude/architecture.md`): setup.py is wiring only; no orphan helpers; registry selects names from closed code-owned sets, never command text; accepted tool customizations are install tuning, not Policies rows.
- Changes reach `main` by branch push, green CI, fast-forward; push per wave.

## Sources

### Primary (HIGH confidence, read this session)
- `installer/terminal_shell.py` (1-1055), `installer/post_install.py` (1-472), `installer/version_status.py` (725-900, 1925-1940), `installer/app.py` (570-670), `installer/tweaks.py` (1-520), `installer/schedules.py` (30-110), `installer/agent_settings.py` (606-742)
- `tests/test_terminal_shell.py` (17-48, 170-215, 1105-1364, 1515-1700), `tests/test_post_install.py` (640-670, 1095-1145), `tests/test_version_status.py` (7035-7085, 5140-5190), `tests/test_tweaks.py` (340-400), `tests/test_tool_onboarding_skill.py` (215-230, 360-420), `tests/test_docs_only.py`, `tests/test_reachability.py`, `tests/test_setup.py` (5140-5185), `tests/test_registry.py` (1350-1372, 2940-2952)
- `devtools/docs_only.py`, `installer/registry.toml` (zsh and alacritty entries), `pyproject.toml`, `.github/workflows/ci.yml`, `AGENTS.md`, `.claude/testing.md`, `.claude/python-tooling.md`, `.claude/architecture.md` (partial: pages 1-1005 of 1250 plus targeted greps), `.planning/research/ARCHITECTURE.md` (15-60)
- Live probes (scratch HOME and scratchpad only): golden bytes via `run_post_install`; zsh 5.9.2 pty widget probe; scratch-copy test run for the zsh bundle (copy deleted afterwards)

### Secondary (MEDIUM)
- `28-CONTEXT.md` and `28-SPEC.md` (decisions and jev advisory notes, including the upstream Alacritty CHANGELOG citation for D-15, not re-fetched)

### Tertiary (LOW)
- None used for claims; CI runner zsh availability is in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new packages, all repo-local patterns read.
- Architecture: HIGH for the move and dispatch sites (line-cited), MEDIUM for `Writes`/`placement` fit with phase 29-31 (A2).
- Pitfalls: HIGH for 1-4 (two verified by running tests in a scratch copy / by reading the asserting test), MEDIUM for 6-9.

**Research date:** 2026-11-20
**Valid until:** 2026-12-20 (stable, repo-internal; invalidated by edits to `terminal_shell.py`, `tweaks.py`, or the cited tests)
