# Phase 29: Terminal defaults for the terminals in the catalog - Pattern Map

**Mapped:** 2026-11-20
**Files analyzed:** 14 new/modified
**Analogs found:** 14 / 14 (herdr container target and Konsole detector are role-match only)

All analog paths below are git-tracked source (checked with `git ls-files` on the core files).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/terminal_keys.py` (kitty + wezterm rows, `OwnedRegion.placement`, `Writes` callable, `plan` 3rd arg, `KeysPlan.notes`) | config table / service | file-I/O | same file, `TERMINAL_KEYS["alacritty"]` (lines 116-134) | exact |
| `installer/terminal_regions.py` (`Placement`, `replace_owned_region(placement=)`, `kitty_config_path`, kitty scan, Lua skeleton constant) | utility | file-I/O, transform | same file: `replace_owned_region` (26-62), `alacritty_config_path` (80-91), `alacritty_keys_plan` (153-171) | exact |
| Alacritty clear-row change (`_KEY_BINDINGS` tuple, drop `clear="ClearHistory"`) | config | transform | `terminal_regions.py:139-143` Alt rows (`chars = "\\u001bb"`) | exact |
| `installer/terminal_shell.py` (`_kitty_config_path` delegate, `_wezterm_content` via placement, Konsole read-only helper, `TerminalShellResult.notes`) | service | file-I/O | `_wezterm_content` (136-163), `_sync_konsole` (315), `sync_message` (755) | exact |
| `installer/registry.toml` (drop kitty macOS `script`, add `post_install` to kitty/wezterm) | config | n/a | wezterm cask-only macOS route; alacritty `post_install = ["apply_terminal_tuning"]` (~3165) | exact |
| `tests/test_terminal_keys.py` (golden files, drift, scratch HOME) | test | file-I/O | same file: `_KEYS_REGION` goldens (33-50), `_FIXTURE_ROW` (487-501), `test_row_fields_...` (504) | exact |
| `tests/test_terminal_shell.py:1169` (clear assert flips) | test | file-I/O | same lines 1155-1172 | exact |
| `tests/test_registry.py` (kitty macOS pins) | test | n/a | lines named in RESEARCH 325-338 | exact |
| `scripts/container-e2e-verify.sh` (`herdr-keys` verb, `cmd_herdr_keys`) | script / container target | event-driven | `cmd_bun_lifecycle` (2859-2890) | exact |
| `tests/e2e_herdr_keys_driver.py` (pure `herdr_keys_verdict`) | utility | transform | `tests/e2e_bun_driver.py` verdict functions (`brew_bun_verdict` 98, `floor_verdict` 271) | exact |
| `tests/test_container_e2e_herdr_keys.py` (host test, stubbed `ct`) | test | request-response | `tests/test_container_e2e_bun.py` (1-140) | exact |
| Konsole detector (regex over `sessionui.rc`) | utility | transform | RESEARCH "Konsole detector" excerpt; `terminal_sync_warning` never-raise rule (terminal_shell.py:58-84) | role-match |
| `.claude/skills/tool-onboarding/SKILL.md` (D-12 cells) | docs / table | n/a | the table at lines 209-218 | exact |
| `tests/test_tool_onboarding_skill.py` (pins) | test | n/a | `STATUS_RE` line 36; tests at 341-381 | exact |

## Pattern Assignments

### `installer/terminal_keys.py` (kitty and wezterm rows)

**Analog:** the alacritty row, `installer/terminal_keys.py:116-134`.

Row shape to copy (new rows add `OwnedRegion(region, comment, Placement.X)`):
```python
"alacritty": KeysRow(
    ownership=OwnedRegion(ALACRITTY_KEYS),
    config_path=_alacritty_path,
    plan=_alacritty_plan,
    validate=validate_toml,
    summary="Alacritty keys: ...",
    created_record=ALACRITTY_CREATED,
    same_directory=Vendor("2026-11-19, upstream CHANGELOG: ... The installer writes nothing."),
    sibling_regions=(ALACRITTY,),
    clear="ClearHistory",   # phase 29: delete this line (and comment at line 77)
)
```
Path wrapper pattern (lines 80-82): `def _alacritty_path(platform_os, home, environ): del platform_os; return alacritty_config_path(home, environ)`. kitty's `_kitty_path` passes `platform_os` through instead.

Chord and bytes come from `clear_binding(row, platform_os)` (98-103), which returns `("cmd+k" | "ctrl+shift+k", row.clear)`; both new rows keep the default `clear`.

Four call sites pass the region primitive (166-171, 210, 218): add `placement=row.ownership.placement` to each (apply x2, pending x2). The `body=None` probes need no placement.

`_render` (106-113) currently appends a constant `Writes.snippet`. For kitty, generalise to `str | Callable[[str, str], KeysPlan]` and merge body and conflicts; keep `str` valid so `test_same_directory_vendor_writes_nothing_and_writes_writes_it_once` stays untouched.

`plan` gets the config path as 3rd arg (kitty includes resolve relative to the config file): update `_alacritty_plan` (93-95, `del` the arg) and `_fixture_plan` (tests/test_terminal_keys.py:487) in the same commit.

Error handling is unchanged: refusals come back as `KeysPlan(None, refusal=...)`, `TerminalShellError` is an `OSError` so `apply_terminal_keys` (173-174) turns it into a one-line refusal.

---

### `installer/terminal_regions.py` (placement, kitty resolver, scan)

**Analog 1 (placement):** `replace_owned_region`, lines 51-62. Only the "region absent" branch changes:
```python
region = f"{begin}\n{body}\n{end}\n"
if complete is None:
    prefix = content if not content or content.endswith(("\n", "\r")) else f"{content}\n"
    return f"{prefix}{region}"
```
Add `TOP` (`region + content`) and `BEFORE_RETURN` (index of lines whose `strip() == "return config"`, exactly one else `TerminalShellError`; the insertion `"".join((*lines[:i], region, *lines[i:]))` is byte-identical to `terminal_shell.py:158-163`). RESEARCH 427-441 has the full excerpt.

**Analog 2 (resolver):** `alacritty_config_path`, lines 80-91 (first existing of candidates, else first). Replicate with kitty's order per RESEARCH 406-425 (`KITTY_CONFIG_DIRECTORY`, XDG, `XDG_CONFIG_DIRS`, `~/.config`, macOS `~/Library/Preferences`; existing and writable, else XDG fallback).

**Analog 3 (scan and conflicts):** `alacritty_keys_plan`, lines 153-171.
```python
taken = {_binding_id(entry.get("key"), entry.get("mods")) for entry in ...}
for key, mods, action in _KEY_BINDINGS:
    if _binding_id(key, mods) in taken:
        conflicts.append(f"alacritty: partial: you already bind {mods.replace('|', '+')}+{key}")
    else:
        blocks.append(...)
return KeysPlan("\n\n".join(blocks) or None, tuple(conflicts))
```
Copy this loop for kitty: normalise taken chords (`_binding_id` at 147-150 is the normalise-then-compare model), emit `kitty: partial: you already map ...`, body None when all taken. Text outside owned regions comes from the two-call strip in `user_document` (107-115): `replace_owned_region(replace_owned_region(text, A, None), B, None)`; for kitty strip `kitty` and `kitty-keys` (comment `#`).

Alacritty change (D-08): in `_KEY_BINDINGS` (139-143) replace `'action = "ClearHistory"'` with `'chars = "\\u000c"'`, same escape style as the Alt rows.

Validators: `validate_toml` (174-178) is the model for raising `TerminalShellError("... nothing written")`; kitty and Lua validators raise the same type.

---

### `installer/terminal_shell.py` (wezterm region, kitty path, Konsole)

**Analog:** `_wezterm_content`, lines 136-163 (quoted above in this session). It already inserts a Lua region before the single `return config` and returns `None` for an unsupported shape. After `placement` lands, it collapses to one `_replace_owned_region(..., placement=BEFORE_RETURN)` call; remove the substring test at line 148 (`"tools-installer terminal-shell wezterm" in existing`) which also matches `wezterm-keys`. Use `_replace_owned_region(existing, "wezterm", None, comment="--") != existing` if a branch stays.

Lua helpers to copy for the keys body: `_lua_string` (lines ~130, escape `\` and `"`), and the generated-body style `"\n".join((...))`. WezTerm keys Lua body: RESEARCH 443-470 (own `local wezterm = require "wezterm"`, uppercase-letter-adds-SHIFT rule).

Path: `_kitty_config_path(home, environ)` (lines 117-118, XDG only) delegates to the new `kitty_config_path` in `terminal_regions.py`; `_wezterm_config_path` (121-127) is the path the wezterm row wraps.

Konsole report: add a read-only helper beside `_sync_konsole` (315) invoked from `sync_terminal_shells` (614, call at ~712) under the same gates. `removed` goes to `warnings` as `konsole: partial: you removed Ctrl+Shift+K; kept yours`; `stock` goes to a new `TerminalShellResult.notes` rendered by `sync_message` (755) only when Konsole is newly written. Detector regex excerpt: RESEARCH 473-487. It must never raise (missing or non-UTF-8 file reads as stock), following `terminal_sync_warning` (58-84).

---

### `installer/registry.toml` (kitty)

**Analog:** the kitty entry itself (3017-3066). Delete the macOS `script` block and its two comment lines (3040-3049); keep the `cask` method (`os = ["macos"]`, `cask = "kitty"`, `app = "kitty.app"`, `min_os_version = "12"`). Do NOT delete the comment block at 2982-3016 (`test_kitty_entry_records_why_it_uses_the_vendor_script` pins fragments there); add the new `# Verified` text next to the removed block. Add `post_install = ["apply_terminal_tuning"]` to kitty and wezterm, copying alacritty's line (~3165).

---

### `tests/test_terminal_keys.py` (golden files, drift, scratch HOME)

**Analog:** same file. Golden constants are full region texts with markers:
```python
_KEYS_REGION = (
    "# >>> tools-installer terminal-shell alacritty-keys >>>\n"
    '[[keyboard.bindings]]\nkey = "Left"\nmods = "Alt"\nchars = "\\u001bb"\n\n'
    ...
    "# <<< tools-installer terminal-shell alacritty-keys <<<\n"
)
```
Edits for Alacritty: `_SUMMARY` (33), `_KEYS_REGION` (38) and `_KEYS_REGION_NO_LEFT` (44) change `action = "ClearHistory"` to `chars = "\\u000c"`; rewrite `test_alacritty_keeps_clear_history_until_phase_29` (599-603) as `row.clear == CTRL_L` and `clear_binding(row, "fedora") == ("ctrl+shift+k", "\x0c")`. Add the drift test: install old bytes, `terminal_keys_pending == KEYS_PENDING`, reconfigure (`skip_recorded=True`), assert new bytes and a single region.

New kitty/wezterm tests copy the fixture pattern: `apply_terminal_keys(row, id, "fedora"|"macos", Path.home(), os.environ, skip_recorded=False)` against the scratch HOME (autouse HOME isolation is in `tests/conftest.py`; tests call `Path.home()`), then `read_text()` compared against a golden per OS. kitty maps additionally parsed through `kitty.config.load_config` where kitty exists (skipif with a reason), WezTerm Lua through lua/luajit where present.

`test_row_fields_are_exactly_the_declared_set` (504-517) pins `KeysRow` field names: `placement` inside `OwnedRegion` leaves it unchanged; any new `KeysRow` field edits that list on purpose.

`test_terminal_shell.py:1169`: `["action"] == "ClearHistory"` becomes `["chars"] == "\x0c"`; lines 1167-1168 (Alt rows) stay.

---

### `scripts/container-e2e-verify.sh` (`herdr-keys` verb)

**Analog:** `cmd_bun_lifecycle`, lines 2859-2890. Copy its shape: option loop with `--keep-image` and `die "unknown ... option"`; `LANDING_CONTAINER_NAME="tools-installer-e2e-herdr-$$"`; set `CONTAINER_NAME`, `IMAGE="$LANDING_IMAGE"`, `DISTRO=fedora`, `LANDING_DRIVER_MODULE=tests.e2e_herdr_keys_driver`, `PHASE_DIR`, `LANDING_TRANSCRIPT`; `trap landing_teardown EXIT`; `ensure_phase_dir`; `landing_note_image`; `landing_bootstrap`; collect each `landing_step <name> <name> || failed=1`; `return "$failed"`. Register in the `main` case (2927-2929: `bun-lifecycle) cmd_bun_lifecycle "$@" ;;`) and in `usage` (line 119 `bun-lifecycle [--keep-image]`). Probe scripts for the in-container part: `.../scratchpad/p29/scripts/{drive.py,recorder.py,in_container.sh}` (scratch, untracked; copy content, never reference the path). Constants from D-10: `onboarding = false`, `version_check`/`manifest_check` off, HOME `/h`, scrubbed `HERDR_*`, `--network=none`. Print a `TRACER_HERDR_KEYS_*` verdict with an `_INFEASIBLE` variant for "not ready".

### `tests/e2e_herdr_keys_driver.py`

**Analog:** pure verdict functions in `tests/e2e_bun_driver.py` (`floor_verdict`, `kept_peer_verdict` returning strings or lists). Use RESEARCH 489-495:
```python
EXPECTED = ("1b62", "1b66", "1b5b313b3344", "1b5b313b3343", "0c")
def herdr_keys_verdict(recorded: Sequence[str]) -> list[str]:
    return [f"missing {hexed}" for hexed in EXPECTED if hexed not in recorded]
```
The target must send Alt+Right raw and CSI-u (the persisted scratch drive script never did).

### `tests/test_container_e2e_herdr_keys.py`

**Analog:** `tests/test_container_e2e_bun.py`. Copy: module docstring stating it never starts a container; `_CT_STUB` (logs `ct %s` to `$CALLS`); helpers `_constant` (assigned vars via regex), `_function` (extract bash function by name), `_script(*names, variables=, stubs=)`, `_run(script, scratch)` with `env={"PATH": "/usr/bin:/bin", "HOME": scratch, "CALLS": ..., "LANG": "C"}`; `_LIFECYCLE_FUNCTIONS` list and `_lifecycle()` composer; registration test:
```python
assert re.search(r"^\s*bun-lifecycle\) cmd_bun_lifecycle \"\$@\" ;;$", text, re.MULTILINE)
```
adapted to the herdr verb, plus canned-log verdict tests (pass, each chord missing, re-encoded) and a registry assertion that herdr has no `apply_terminal_tuning` and no row in `TERMINAL_KEYS`. Do not write `.md` string literals (tests/test_docs_only.py LEDGER).

---

### `.claude/skills/tool-onboarding/SKILL.md` and `tests/test_tool_onboarding_skill.py`

**Analog:** the closed table (SKILL.md 209-218). Each cell begins with a status word accepted by `STATUS_RE = (?:vendor|written|unverified|n/a|planned \(phase \d+\))(?::|$)` (test file line 36); ASCII only, no typographic dashes. Target values per RESEARCH 344: kitty (b)(c)(d) `written`; wezterm (b)(c) `written`, (d) `vendor` source-cited, live-unverified; alacritty (c) `written`; herdr (b)(c)(d) `vendor`; Konsole sentence (line 220) becomes "stock Ctrl+Shift+K clear, reported not written". Conflicts section: the second clause's example ("planned for phase 29 ... `scroll_line_up`") is pinned by `test_conflicts_two_clauses_with_examples` (341-364); change phrase in skill and test together. `test_conflicts_names_the_real_partial_lines` (367-381) gains the kitty/konsole `partial:` wording.

## Shared Patterns

### Owned region, exact-line markers
**Source:** `installer/terminal_regions.py:22-62`. Marker `"{comment} {edge} tools-installer terminal-shell {terminal} {edge}"`; match by full-line equality; malformed raises `TerminalShellError`. Apply to every new region (`kitty-keys` `#`, `wezterm-keys` `--`). Never substring-test for a region.

### Conflict reporting
**Source:** `terminal_regions.py:168`: `f"alacritty: partial: you already bind {...}"`. New lines use `kitty: partial: you already map ...` and `konsole: partial: you removed Ctrl+Shift+K; kept yours`. `version_status.py` reads the `partial:` prefix.

### Apply/pending/strip lifecycle (drift, written-once record)
**Source:** `terminal_keys.py:145-243`. Reuse unchanged; kitty/wezterm get it by being table rows. A row that writes nothing (herdr, Konsole) must not exist, because it would read `apply install tuning` forever (28 D-06).

### Atomic compare-before-commit writes
**Source:** `terminal_regions.commit_region` (181-205) with `write_if_unchanged` and `atomic_write_text`. Never `open(..., "w")`.

### Scratch HOME in tests
**Source:** `tests/conftest.py` autouse fixtures (`Path.home()` is a scratch dir; subprocess and network guards). New tests never touch the real HOME.

## No Analog Found

| File / Piece | Role | Data Flow | Reason |
|---|---|---|---|
| Lua structural validator for WezTerm (`_validate_wezterm`) | utility | transform | Only TOML validator exists; follow `validate_toml`'s raise-`TerminalShellError` shape with RESEARCH Pitfall 5 checks |
| kitty scan across `include`/`globinclude` with a visited set | utility | file-I/O | Alacritty refuses on import instead; no include-following code exists |
| In-container herdr pty driver | script | event-driven | No pty-driving target exists; port from the scratch probe scripts |

## Metadata

**Analog search scope:** `installer/terminal_keys.py`, `installer/terminal_regions.py`, `installer/terminal_shell.py`, `installer/registry.toml`, `scripts/container-e2e-verify.sh`, `tests/test_terminal_keys.py`, `tests/test_terminal_shell.py`, `tests/test_container_e2e_bun.py`, `tests/e2e_bun_driver.py`, `tests/test_tool_onboarding_skill.py`, `.claude/skills/tool-onboarding/SKILL.md`
**Files scanned:** about 12 (line numbers from CONTEXT/RESEARCH were spot-checked against the files read)
**Pattern extraction date:** 2026-11-20
