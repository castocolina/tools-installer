# Phase 29: Terminal defaults for the terminals in the catalog - Research

**Researched:** 2026-11-20
**Domain:** Python installer (uv, pytest): terminal config owned regions (kitty.conf, WezTerm Lua, Alacritty TOML), a read-only Konsole check, a herdr byte-level container target, a kitty registry method change, skill-table cells.
**Confidence:** HIGH for the mechanism and the config formats (read in code and verified live against the installed kitty 0.49.2 and WezTerm 20240203). MEDIUM for kitty macOS behavior, WezTerm cwd on macOS and Konsole's saved-override format (source-cited, no real Mac or live Konsole capture). The Alacritty change is HIGH.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

(Copied from 29-CONTEXT.md `<decisions>`. 29 D-09 is provisional, flagged "needs confirmation": research it, do not override it.)

#### kitty (TERM-01)
- **D-01: A `kitty-keys` owned region (`OwnedRegion("kitty-keys", "#")`) in `kitty.conf`, placed at the top of the file**, next to the existing `kitty` shell region; no include file. kitty resolves a duplicate chord last-wins (verified live in a scratch HOME), and the generic region append goes to the end of the file, which would beat every user `map`. The plan scans `map` lines in `kitty.conf` and in plain `include`/`globinclude` files outside the owned regions (normalizing `kitty_mod`, `cmd`/`super`, `opt`/`alt`/`option` and modifier order) and skips taken chords with `kitty: partial: you already map ...`; `geninclude` and `envinclude` are reported as not followed. Alacritty's refuse-on-import precedent (`installer/terminal_shell.py:544-550`) would refuse most themed kitty users. jev first rung none_of_these 0.77 contradicted the evidence; second opinion top_of_file_plus_scan 0.94. **jev overridden.**
- **D-02: Map lines per OS, with literal bytes.** macOS: `opt+left` and `opt+right` send `\x1bb` and `\x1bf` (`send_text all`), `cmd+k` sends `\x0c`, `cmd+t`/`cmd+enter`/`cmd+n` map to the `*_with_cwd` actions. Linux: `ctrl+shift+k` sends `\x0c` with `--allow-fallback=shifted,ascii` (as kitty declares its default), `kitty_mod+t`/`kitty_mod+enter`/`kitty_mod+n` map to `new_tab_with_cwd`, `new_window_with_cwd`, `new_os_window_with_cwd`; no Alt rows on Linux (owner decision); `macos_option_as_alt` is never written. kitty's own docs say Option/Alt shortcuts take priority without the switch (doc-level; the real Mac stays a UAT line). All test maps parsed through `kitty.config.load_config` in the scratch HOME. The per-OS split matters: `opt+left` on Linux is `alt+left`. jev literal_bytes 0.83 (TypeSafe).
- **D-03: The install note names `scroll_line_up` and says `ctrl+shift+up` still scrolls.** kitty 0.49.2 auto-reloads only when `kitty.conf` existed at start; when the installer creates the file the note says to restart kitty or press `ctrl+shift+f5` (`ctrl+cmd+,` on macOS); the installer sends no signal.
- **D-04: The config path uses a first-existing resolver in kitty's own order** (`KITTY_CONFIG_DIRECTORY`, XDG, `~/.config/kitty`, and on macOS `~/Library/Preferences/kitty`), as Alacritty's resolver does (`terminal_shell.py:486-497`); `_kitty_config_path` (`:156-157`) is XDG only and never mattered because the sync returns at once on macOS (`:914-915`). Creating `~/.config/kitty/kitty.conf` would hide a user's Preferences config. The exact order is confirmed in planning. jev first rung none_of_these 0.91 contradicted the evidence; second opinion first_existing_in_vendor_order 0.97. **jev overridden.**
- **D-05: kitty's macOS install drops the `script` method; the existing `cask` method becomes the macOS route** (`installer/registry.toml:3058-3062`; `--appdir` to `~/Applications`, `installer/executors.py:699-704`). The script wrote `/Applications/kitty.app`, had no `paths` and no removal (audit `.planning/audits/catalog/2026-11-13/kitty.md:23,28`). The `# Verified` comment records that brew links the CLI, not `~/.local/bin` (the 27 D-10 cask gap). jev cask_user_dir 0.97 (TypeSafe).

#### WezTerm (TERM-02)
- **D-06: A `wezterm-keys` Lua region inserted before the single `return config`**, like the shell region (the generic append lands after `return` and never runs). It does `config.keys = config.keys or {}` and adds rows only for chords the user's `config.keys` does not hold; the check runs in Lua at load time with normalized mods (`CMD`/`WIN` to `SUPER`, `OPT`/`META` to `ALT`, `CONTROL` to `CTRL`, sorted) and a lower-cased key; `{key="K", mods="CTRL"}` is the same chord as `CTRL|SHIFT k`. Conflicts are reported (`partial: kept yours`) by reading back `wezterm show-keys --lua` when wezterm is present. Live (`wezterm show-keys`): a later duplicate wins, so a plain `table.insert` would override user keys; the Lua guard kept the user's `CMD k` and still added the others. The owned-region check becomes full-line equality, reusing the exact matching of `_replace_owned_region` (`terminal_shell.py:112-123`), replacing the substring test at `:192` (the keys marker contains the shell marker's text). **Own reasoning** (jev runtime_guard_plus_readback low 0.75; first rung low 0.68). Ledger.
- **D-07: Clear is `SendString "\x0c"` on `SUPER k` (macOS) and `CTRL|SHIFT k` (Linux)**, replacing the stock `ClearScrollback(ScrollbackOnly)`; macOS also gets `OPT LeftArrow`/`OPT RightArrow` sending `\x1bb`/`\x1bf`; no Linux Alt rows. `same_directory` is `vendor` for tabs and splits (`SpawnTab(CurrentPaneDomain)`); whether `SpawnWindow` and `SpawnTab` inherit the cwd without OSC 7 is verified in a disposable container (Xvfb plus `wezterm cli spawn`) before the declaration is locked; if they do not, the row switches to `writes` with explicit cwd callbacks. jev live_check_before_lock 0.95 (TypeSafe).

#### Alacritty (TERM-03)
- **D-08: The only byte change is the Linux clear row, `action = "ClearHistory"` to `chars = "\u000c"`**, done by removing Alacritty's `clear` override so the phase 28 default applies; the two Alt rows stay byte-identical; the summary text changes; existing installs pick it up through the phase 28 D-06 drift rule (this phase adds no migration; depends on D-06, flagged needs confirmation). **Alacritty has no macOS method** (`cargo_distrobox` debian/fedora/arch, dnf, apt, pacman), so TERM-03's "Cmd+K (macOS)" is `n/a`: no macOS output, requirement reworded to "where installed". jev not_applicable_amend_spec 0.96 (TypeSafe).

#### Konsole (TERM-04)
- **D-09: Konsole is report-only; the installer never writes a binding.** The stock clear is the compiled-in action `clear-history-and-reset` ("Clear Scrollback and Reset", default Ctrl+Shift+K; strings found in `libkonsoleprivate.so.26.08.2` on the host; the chord itself is confirmed by the container check). A user change lives as `<Action name="clear-history-and-reset" shortcut="..."/>` in `$XDG_DATA_HOME/kxmlgui5/konsole/sessionui.rc`. Stock means no override entry or one whose `shortcut` contains Ctrl+Shift+K; removed means `shortcut=""` or a value without it, reported as `konsole: partial: you removed Ctrl+Shift+K; kept yours`. Detection is a line or regex read (no XML parser in `installer/`; bandit flags `xml.etree`). Reasons: SKILL-03 (a user's choice is kept), the owner decision "verify and leave alone", and KDE rewrites that file and drops comments, so ownership cannot be proven there. This **amends TERM-04 / SPEC R4 / ROADMAP criterion 3** (the "writes a binding only when the user removed it" clause is dropped); **flagged: needs confirmation**. The format and the stock chord are confirmed by a container capture on Konsole 26.x. jev first rung none_of_these 0.98 contradicted the evidence; second opinion report_only low 0.73. **jev overridden / Own reasoning**, ledger. Container capture: **Own reasoning** (jev container_capture low 0.79; first rung none_of_these 0.77), ledger.

#### herdr (TERM-05)
- **D-10: herdr 0.9.5 does not intercept the chords, so no pass-through setting is written and herdr gets no keys row.** Verified live in a disposable `fedora:44` container (`--rm --network=none`) with a pty child recording its raw input as the pane shell: the pane received byte-identical `1b62` (ESC b), `1b66` (ESC f), `1b5b313b3344` (ESC[1;3D), `1b5b313b3343` (ESC[1;3C) and `0c` (Ctrl+L); the CSI-u forms were re-encoded to `1b62`, `1b66` and `0c`; herdr's default keys are all `prefix+...` with prefix `ctrl+b`; `[terminal] new_cwd = "follow"` is the vendor default, so same-directory is `vendor`. A row would need `post_install = ["apply_terminal_tuning"]`, and under 28 D-06 a row that writes nothing would read `≈ apply install tuning` forever, so herdr stays out of the table: the phase 27 skill table records herdr as `vendor` pass-through (verified), and the SPEC boundary "herdr rows" is amended. The byte-level test is a container target in the existing harness (`scripts/container-e2e-verify.sh`, which already installs herdr on Fedora), not a pytest that skips silently in CI; its config needs `onboarding = false` (the first-run popup swallows input), `version_check` and `manifest_check` off for `--network=none`, a short HOME (a long scratch path failed with "server did not become ready"; the socket path limit is the likely cause), and scrubbed `HERDR_*` variables. Probe scripts: `.../scratchpad/p29/scripts/{drive.py,recorder.py,in_container.sh}`. jev container_e2e_target 0.98 (TypeSafe); no-row: **Own reasoning** (jev noop_entry low 0.45; first rung low 0.57). Ledger. macOS herdr is not probed (UAT).

#### Coupling with phases 27, 28 and 31
- **D-11: The phase 28 row type needs a `placement` field (end of file, top of file, before `return config`) and a per-row `validate`** (28's is a TOML re-parse; kitty needs a no-op or structural check, Lua a structural check). *(amended 2026-11-19, 29 D-11, in 28-CONTEXT D-03.)* The placement field is ownership-neutral, so phase 31's JSON rows do not conflict *(amended 2026-11-19, 31 D-04: `placement` moves into the `OwnedRegion` variant)*.
- **D-12: Phase 27's table cells move** from `planned`/`unverified` to kitty (written), WezTerm clear (written) with cwd `vendor` (unverified until D-07's container check), herdr `vendor` pass-through (verified), Konsole a note row (stock clear), per phase 27 D-13.

### Claude's Discretion
- The exact `partial:` message wording, the install-note text, and the Lua guard's helper names.

### Deferred Ideas (OUT OF SCOPE)
- To confirm in planning: kitty's config-directory order on macOS; whether the Homebrew `kitty` cask declares `binary` stanzas that resolve under `--appdir`; whether `SpawnTab`/`SpawnWindow` inherit the cwd without OSC 7 (D-07 container check); Konsole 26.x default chord and the post-removal `sessionui.rc` content (container capture); whether `$XDG_DATA_HOME/kxmlgui5/` is still the KF6 override directory.
- Reviewed Todos (not folded): none other matched.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TERM-01 | kitty: Option+Left/Right on macOS without the global switch, KEYS-03 clear on Cmd+K / Linux Ctrl+Shift+K naming `scroll_line_up`, same directory, no `/Applications` write | kitty row (path resolver, TOP placement, per-OS lines, scan), registry macOS method drop, verified `load_config` parse of the exact lines |
| TERM-02 | WezTerm Lua region extends `config.keys`, exact marker-line matching | `wezterm-keys` region before `return config`, Lua guard (verified live under wezterm, luajit and Lua 5.4), full-line marker check |
| TERM-03 | Alacritty clear = screen and scrollback; Linux Alt rows unchanged | One-line change in `_KEY_BINDINGS`; the exact tests that pin the old bytes are listed |
| TERM-04 | Konsole checked, not rewritten (report-only per 29 D-09) | Read-only detector on `sessionui.rc` (format verified in KDE kxmlgui source), report channel options |
| TERM-05 | herdr passes Option/Alt+Left/Right and the clear chord through | Container target + pure verdict function; no row |
</phase_requirements>

## Summary

Phase 28 left a small, clean mechanism: `installer/terminal_keys.py` (a `KeysRow` dataclass, `TERMINAL_KEYS` with only `alacritty`, generic `apply_terminal_keys` / `terminal_keys_pending` / `strip_terminal_keys`) over `installer/terminal_regions.py` (marker, `replace_owned_region`, `commit_region`, `strip_region`). Phase 29 adds two rows (kitty, WezTerm), flips Alacritty's clear bytes, adds a read-only Konsole check and a herdr container proof. The work is mostly declarative once the mechanism has two additions: a `placement` (top of file, before `return config`) and per-OS content that today's `Writes.snippet` cannot express.

Three findings change the plan. (1) `Writes.snippet` is one string appended unconditionally by `_render`, so it can neither vary per OS nor skip a chord the user already maps; kitty needs both for its `*_with_cwd` lines (section "Mechanism: what D-11 adds"). (2) `KeysRow.plan` receives only `(platform_os, text)`, so kitty's `include`/`globinclude` scan has no config directory to resolve relative paths against. (3) WezTerm's `K` with `CTRL` is the same chord as `k` with `CTRL|SHIFT`; the Lua guard in the scratchpad does not fold an uppercase letter into SHIFT and would let a user's `{key="K", mods="CTRL"}` be overridden (verified live: later duplicate wins). Konsole's save format is now verified from KDE source (the user override is an `<ActionProperties>` entry in `kxmlgui5/konsole/sessionui.rc`, cleared = `shortcut=""`), so D-09's detector design stands.

**Primary recommendation:** Extend `OwnedRegion` with `placement` and `replace_owned_region` with a matching argument (one change, used by the kitty row, the WezTerm row and `_wezterm_content`), generalize `Writes.snippet` and pass the config path into `plan`, then declare kitty and WezTerm as rows; keep herdr and Konsole out of `TERMINAL_KEYS`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Keys region read/write/strip/drift | `installer/terminal_keys.py` + `terminal_regions.py` | `post_install.py`, `version_status.py`, `app.py` (table-driven dispatch, unchanged) | Phase 28 D-01/D-04: one mechanism keyed by tool id |
| kitty config path | `terminal_regions.py` (new `kitty_config_path`) | `terminal_shell._kitty_config_path` delegates | Keys row and shell sync must read one file |
| kitty macOS install route | `installer/registry.toml` | `tests/test_registry.py`, `tests/test_resolve.py` pins | Catalog data, no code |
| WezTerm shell + keys regions | `terminal_regions.replace_owned_region` (placement) | `terminal_shell._wezterm_content` | One insertion implementation |
| Konsole stock-clear report | `terminal_shell.py` (read-only helper beside `_sync_konsole`) | message channel (`TerminalShellResult` / `sync_message`) | Konsole is not a catalog entry, so no row and no `post_install` |
| herdr byte proof | `scripts/container-e2e-verify.sh` target + `tests/e2e_*_driver.py` | host test of script text and pure verdicts | Needs a live pty and a herdr server, container only |
| Skill table cells | `.claude/skills/tool-onboarding/SKILL.md` | `tests/test_tool_onboarding_skill.py` | Documentation that tests pin |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`re`, `tomllib`, `pathlib`, `glob`, `dataclasses`, `enum`) | project's pinned Python | Row declarations, kitty map scan, Konsole regex, TOML validate | The repo already does all terminal work in stdlib; `xml.etree` is bandit-flagged, so the Konsole read is a regex |
| pytest (+ xdist, coverage) | repo-pinned | Tests | `make test` / `make validate` |
| Existing modules | n/a | `terminal_keys.py`, `terminal_regions.py`, `atomic.py`, `agent_settings.py` | Phase 28 mechanism |

No new third-party package is needed. [VERIFIED: codebase read, `installer/terminal_keys.py:1-30`]

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| kitty (`kitty +runpy`, `kitty.config.load_config`) | 0.49.2 on the host | Parse generated maps | A `skipif(shutil.which("kitty") is None, reason=...)` backstop test; CI has no kitty |
| wezterm (`show-keys --lua`) | 20240203-110809-5046fc22 on the host | Read back effective keys | Backstop test and conflict read-back (D-06) |
| luajit or lua 5.4 + a `wezterm` stub in `package.preload` | luajit on host, Lua 5.4.9 on host | Execute the generated Lua region without wezterm | Backstop test of the guard (verified feasible, section Code Examples) |
| podman | 6.1.3 on host | Container herdr target | Orchestrator-only, via `scripts/detect-container-runtime.sh` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex on `sessionui.rc` | `xml.etree` / `defusedxml` | bandit flags `xml.etree`; a new dependency for one attribute is not justified (D-09 already decided) |
| Own Lua syntax check | Real `luac -p` | Not on CI runners; structural check in Python is the always-run gate, `luajit -bl` the optional backstop |

**Installation:** none. **Version verification:** `kitty --version` -> `kitty 0.49.2`; `wezterm --version` -> `wezterm 20240203-110809-5046fc22`; `konsole --version` -> `konsole 26.08.2`; `herdr --version` -> `herdr 0.9.5` (all read on the host this session).

## Package Legitimacy Audit

No external package is installed by this phase (the stack is the repo's existing stdlib and pytest). Audit skipped: no package to check.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
install / reinstall / reconfigure (post_install "apply_terminal_tuning")
        |
        v
post_install._tune_terminal --> TERMINAL_KEYS[tool.id] (kitty | wezterm | alacritty)
        |                                   |
        |                                   v
        |                    row.config_path(os, home, env)  --kitty: first-existing resolver (D-04)
        |                                   |
        |                                   v
        |              read file text --> row.plan(os, text, path) --> KeysPlan(body, conflicts, notes, refusal)
        |                    (kitty: scan outside-region maps + plain includes; WezTerm: structural check;
        |                     Alacritty: TOML conflict check)           |
        |                                   |                           v
        |                                   v               refusal? -> "<Tool> keys not changed: ..."
        |              replace_owned_region(text, region, body, comment, placement)
        |                  END (alacritty) | TOP (kitty) | BEFORE_RETURN (wezterm)
        |                                   |
        |                                   v
        |              row.validate(updated) -> write_if_unchanged (compare-before-commit)
        |                                   |
        |                                   v
        |                  record file "terminal-tuning-<id>" + created marker
        v
install output lines: row.summary + plan.conflicts + plan.notes (displaced default, reload)

Refresh pass: version_status._terminal_tuning_fact -> terminal_keys_pending -> "≈ apply install tuning"
              (present region differing from its render = drift, 28 D-06)
Removal: app._after_removal -> strip_terminal_keys (sibling regions, record, created file)

Linux zsh sync (sync_terminal_shells, runs when zsh is present; macOS returns at once)
   kitty `kitty` region (END) | WezTerm `wezterm` region (BEFORE_RETURN) | Konsole profile
   + NEW read-only Konsole check -> konsole:partial / stock note
herdr: no row, no write; container target proves bytes (pty child records raw input)
```

### Recommended Project Structure
```
installer/
├── terminal_regions.py   # + Placement enum, replace_owned_region(placement=), kitty_config_path, kitty scan helpers, WEZTERM skeleton constant
├── terminal_keys.py      # + kitty and wezterm rows, OwnedRegion.placement, Writes generalization, KeysPlan.notes use
├── terminal_shell.py     # _kitty_config_path delegates, _wezterm_content uses placement, Konsole read-only check
└── registry.toml         # kitty: macOS script method removed; kitty and wezterm get post_install
scripts/container-e2e-verify.sh   # + herdr-keys target
tests/                    # extended test_terminal_keys.py; new test_container_e2e_herdr_keys.py + e2e_herdr_keys_driver.py
.claude/skills/tool-onboarding/SKILL.md   # D-12 cells
```

### Mechanism as it stands (Phase 28), with citations

- `KeysRow` fields (verbatim): `ownership: OwnedRegion`, `config_path: Callable[[str, Path, Mapping[str, str]], Path]`, `plan: Callable[[str, str], KeysPlan]`, `validate: Callable[[str], None]`, `summary: str`, `created_record: str`, `same_directory: SameDirectory`, `sibling_regions: tuple[str, ...] = ()`, `clear: str = CTRL_L`. [VERIFIED: installer/terminal_keys.py:66-77] `validate` already exists as a per-row field; D-11's "per-row validate" is therefore already done and only `placement` is new.
- `OwnedRegion` is `region: str` and `comment: str = "#"` only. [VERIFIED: installer/terminal_keys.py:58-63]
- `SameDirectory = Vendor | Writes | NotApplicable`; `Writes.snippet: str`. [VERIFIED: installer/terminal_keys.py:34-55]
- `_render` appends `row.same_directory.snippet` after `plan.body` whenever the plan has no refusal, with no per-OS or per-chord logic. [VERIFIED: installer/terminal_keys.py:106-113]
- `clear_binding(row, platform_os)` returns `("cmd+k" if platform_os == "macos" else "ctrl+shift+k", row.clear)`; its docstring says "Phase 29's rows are the first production callers". [VERIFIED: installer/terminal_keys.py:98-103]
- `TERMINAL_KEYS` holds only `"alacritty"`, with `clear="ClearHistory"` and the comment "Alacritty keeps ClearHistory until phase 29." [VERIFIED: installer/terminal_keys.py:116-134, 77]
- Apply/pending/strip call `replace_owned_region(text, row.ownership.region, body, comment=row.ownership.comment)` at four sites with no placement argument. [VERIFIED: installer/terminal_keys.py:166-171, 210-220]
- `replace_owned_region` appends a new region at the end (`prefix + region`) and replaces an existing complete region in place; markers match by full-line equality (`text_line == begin`). [VERIFIED: installer/terminal_regions.py:26-62]
- The marker text is `# >>> tools-installer terminal-shell <terminal> >>>` (comment prefix varies). [VERIFIED: installer/terminal_regions.py:22-23]
- Drift/pending semantics (28 D-06) are in code: a present, stale recorded region reads `KEYS_PENDING` and a reconfigure (`skip_recorded=True`) rewrites it; a recorded and deleted region stays deleted. [VERIFIED: installer/terminal_keys.py:179-181, 200-224]
- Dispatch is table-driven: `post_install._tune_terminal` -> `TERMINAL_KEYS.get(tool.id)`; `version_status._terminal_tuning_fact`; `app.py` strip. A registry tool declaring `apply_terminal_tuning` without a row yields `no keys row for <id>`. [VERIFIED: installer/post_install.py:385-407; installer/version_status.py:820-840; installer/app.py:630-634]
- The registry action name already exists: `POST_INSTALL_ACTIONS` contains `"apply_terminal_tuning"`; only alacritty declares it (`post_install = ["apply_terminal_tuning"]`, registry.toml:3165). kitty and wezterm declare none. [VERIFIED: installer/model.py:129-140; installer/registry.toml:3017-3029, 3105-3114, 3154-3165]

### What D-11 adds: `placement`, per-OS content, a path for the plan

**1. `placement` (31 D-04 already settles where it lives: inside `OwnedRegion`).**

```python
# installer/terminal_regions.py
class Placement(Enum):
    END = "end"                      # append (Alacritty TOML, the kitty and wezterm SHELL regions today)
    TOP = "top"                      # before every user line (kitty keys: user maps win, last wins)
    BEFORE_RETURN = "before_return"  # before the single `return config` line (WezTerm)

def replace_owned_region(content, terminal, body, *, comment="#", placement=Placement.END) -> str: ...
```

Only the "region absent and body not None" branch uses placement; an existing complete region is replaced in place for every placement. `BEFORE_RETURN` finds lines whose `strip()` equals `return config`; zero or more than one raises `TerminalShellError` (an `OSError`, so `apply_terminal_keys` already turns it into a one-line refusal), and for empty content it seeds the skeleton `local wezterm = require "wezterm"\nlocal config = {}\nreturn config\n` (today a literal inside `sync_terminal_shells`, terminal_shell.py:699-702; move it to a constant both callers import). Then `_wezterm_content` (terminal_shell.py:136-163) collapses to one `replace_owned_region(..., placement=BEFORE_RETURN)` call with its "unsupported return shape" result preserved. [VERIFIED: terminal_shell.py:136-163, 695-710 read; insertion is `"".join((*lines[:index], region, *lines[index:]))`, byte-identical to the planned behavior]

`OwnedRegion` becomes `OwnedRegion(region, comment="#", placement=Placement.END)`; the four call sites in `terminal_keys.py` pass `placement=row.ownership.placement`. The presence probes (`body=None`) need none.

**2. `test_row_fields_are_exactly_the_declared_set` pins `KeysRow` fields** (tests/test_terminal_keys.py:504-517). Putting `placement` in `OwnedRegion` leaves that list unchanged; any new `KeysRow` field (see 3 and 4) edits that one list on purpose.

**3. `Writes.snippet` cannot serve kitty.** kitty's cwd lines differ per OS (`cmd+t` vs `kitty_mod+t`) and must be skipped when the user already maps the chord (D-01). `_render` appends the snippet unconditionally. Recommended: `Writes.snippet: str | Callable[[str, str], KeysPlan]` (platform, text -> body + conflicts) that `_render` merges into the row's plan; a plain `str` stays valid so `test_same_directory_vendor_writes_nothing_and_writes_writes_it_once` (tests/test_terminal_keys.py:549-580) is untouched. WezTerm's cwd is `Vendor` (D-07), so only kitty uses the callable.

**4. `plan` does not know the config path.** kitty's `include` is "resolved with respect to the location of the current config file" [CITED: https://sw.kovidgoyal.net/kitty/conf/, fetched 2026-11-20]. Recommended: `plan: Callable[[str, str, Path], KeysPlan]` with the resolved config path as a third argument; update `_alacritty_plan` (ignores it) and the test fixture `_fixture_plan` (tests/test_terminal_keys.py:487) in the same commit. The alternative (closing over `Path.home()`) breaks the scratch-HOME rule.

**5. `KeysPlan` has no channel for the install note** (D-03: displaced `scroll_line_up`, reload hint). `apply_terminal_keys` returns `(row.summary, *plan.conflicts)` and `summary` is one constant string (terminal_keys.py:196-197), so it cannot name a macOS-only or Linux-only default. Recommended: `KeysPlan.notes: tuple[str, ...] = ()`, emitted by `apply_terminal_keys` after the summary only when the row that displaces the default was actually added (a user-taken `ctrl+shift+k` must not print the `scroll_line_up` note). `summary` stays a constant for the generic first line.

**How the rows are declared** (shape only; wording is Claude's discretion):

```python
"kitty": KeysRow(
    ownership=OwnedRegion("kitty-keys", "#", Placement.TOP),
    config_path=_kitty_path,                  # kitty_config_path(platform_os, home, environ)
    plan=_kitty_plan,                         # scan + per-OS lines (clear_binding gives chord and bytes)
    validate=_validate_kitty,                 # structural: every body line starts with "map "
    summary="kitty keys: ...",
    created_record="terminal-kitty-created",
    same_directory=Writes(_kitty_cwd_lines),  # per-OS, conflict-aware callable
    sibling_regions=("kitty",),               # the zsh shell region is stripped with the tool
),
"wezterm": KeysRow(
    ownership=OwnedRegion("wezterm-keys", "--", Placement.BEFORE_RETURN),
    config_path=_wezterm_path,                # wraps terminal_shell._wezterm_config_path
    plan=_wezterm_plan,                       # refuses a file without exactly one `return config`
    validate=_validate_wezterm,               # structural, see Pitfall 5
    summary="WezTerm keys: ...",
    created_record="terminal-wezterm-created",
    same_directory=Vendor("2026-11-20, wezterm source ...: SpawnTab and SpawnWindow resolve the current pane's cwd ..."),
    sibling_regions=("wezterm",),
),
```

`sibling_regions` mirrors Alacritty's (`ALACRITTY` shell region stripped with the tool, terminal_keys.py:131). Whether the zsh shell region should go when the tool goes is the phase 28 behavior for Alacritty; `_drop_created_config` only deletes a file that is whitespace-only afterwards (terminal_keys.py:246-260), so a WezTerm file created from the skeleton keeps the skeleton after strip (the shell sync's `_remove_if_owned` has the same property, terminal_shell.py:226-234). Recommended: treat "remaining text equals the skeleton" as ours in `_drop_created_config`. Open question O3.

`clear_binding(row, platform_os)` supplies `("cmd+k", "\x0c")` / `("ctrl+shift+k", "\x0c")` to both new rows; the `clear` field stays at its default for kitty and WezTerm and is only Alacritty's to drop.

### kitty (TERM-01)

**Config path (D-04), exact order verified from kitty's source.** `ConfigDirForName` in `tools/utils/paths.go` at tag v0.49.2: (1) if `KITTY_CONFIG_DIRECTORY` is set it is the directory (used directly); else build the list `XDG_CONFIG_HOME`, each `XDG_CONFIG_DIRS` entry, `~/.config`, and on darwin `~/Library/Preferences`, de-duplicated; (2) the first `<loc>/kitty` that contains `kitty.conf` AND is writable (`unix.Access(q, W_OK)`) wins; (3) otherwise `$XDG_CONFIG_HOME` (else `~/.config`) + `/kitty`. [VERIFIED: https://raw.githubusercontent.com/kovidgoyal/kitty/v0.49.2/tools/utils/paths.go lines 89-131, fetched and read 2026-11-20]

Consequences: on macOS `~/.config` precedes `~/Library/Preferences`, so creating `~/.config/kitty/kitty.conf` really would hide a user's Preferences config (D-04's concern is correct); `XDG_CONFIG_DIRS` is part of the order but only matters when that directory is writable, so include it for fidelity (it costs two lines). The fallback when nothing exists matches today's `_kitty_config_path`. `terminal_shell._kitty_config_path` (terminal_shell.py:117-118) should delegate to the new resolver so the shell region and the keys region land in one file; nothing changes when no kitty config exists (same fallback). The shell sync returns at once on macOS, so only the keys row exercises the macOS branch.

**Region placement and reading order.** In the same scratch run that proved `load_config` parsing, a duplicate chord is last-wins (D-01, as the discussion verified live). The `kitty-keys` region at the top means every later user `map` wins and the scan is only for reporting. `clear_all_shortcuts yes` placed after the region would wipe the installed maps (Open question O4).

**Exact lines, verified by `kitty.config.load_config` on kitty 0.49.2** (scratch run, 2026-11-20; `kitty_mod ctrl+alt` was set AFTER the region and the `kitty_mod+...` rows resolved to it, so `kitty_mod` is order-independent). The file loaded without error and produced these keymap entries:

```
macOS (opt = alt on every OS, cmd = super):
map opt+left send_text all \x1bb
map opt+right send_text all \x1bf
map cmd+k send_text all \x0c
map --allow-fallback=shifted,ascii cmd+t new_tab_with_cwd
map cmd+enter new_window_with_cwd
map --allow-fallback=shifted,ascii cmd+n new_os_window_with_cwd
Linux:
map --allow-fallback=shifted,ascii ctrl+shift+k send_text all \x0c
map --allow-fallback=shifted,ascii kitty_mod+t new_tab_with_cwd
map kitty_mod+enter new_window_with_cwd
map --allow-fallback=shifted,ascii kitty_mod+n new_os_window_with_cwd
```

A second run of exactly the ten lines above (with the `--allow-fallback` flags, no `kitty_mod` override) also loaded all ten keymap entries (`kitty_mod` = 5, ctrl+shift). Loaded definitions (printed by the scratch loader, first run): `send_text all \x1bb` (mods=2, alt), `send_text all \x1bf`, `send_text all \x0c` on `cmd+k` (mods=8) and `ctrl+shift+k` (mods=5), `new_tab_with_cwd`, `new_window_with_cwd`, `new_os_window_with_cwd`; `macos_option_as_alt` stayed `0` (`no`). The `--allow-fallback` flags on the `cwd` maps mirror kitty's own defaults (`map --allow-fallback=shifted,ascii kitty_mod+t new_tab`); D-02 only names the flag on the clear row, adding it to `t` and `n` is optional but matches the vendor defaults. [VERIFIED: scratch run against kitty 0.49.2 on the host; defaults read in the 0.49.2-generated `kitty-default.conf`: "map --allow-fallback=shifted,ascii kitty_mod+t new_tab", "map --allow-fallback=shifted,ascii cmd+t new_tab", "map --allow-fallback=shifted,ascii kitty_mod+n new_os_window", "map kitty_mod+enter new_window", "map cmd+enter new_window"]

Note: `kitty_mod+k` is kitty's default `scroll_line_up` ("map --allow-fallback=shifted,ascii kitty_mod+k scroll_line_up smooth") and `kitty_mod+up` also scrolls ("map kitty_mod+up scroll_line_up smooth"), so the `scroll_line_up` note in D-03 is correct and `ctrl+shift+up` still scrolls. If the user changed `kitty_mod`, the literal `ctrl+shift+k` row displaces nothing and `kitty_mod+k` keeps scrolling; the scan normalizes `kitty_mod`.

**macOS `cmd+k` also displaces a vendor default**: `map cmd+k clear_terminal to_cursor active` ("Clear to start"). SKILL-03 says a displaced vendor default needs an install note naming it, and D-03 names only `scroll_line_up`. Recommended: the macOS note names `clear_terminal to_cursor` (Open question O2). The `cmd+t/cmd+n/cmd+enter` rows replace `new_tab`, `new_window`, `new_os_window` with their `_with_cwd` forms (a strict improvement, one phrase in the note). [VERIFIED: kitty-default.conf generated by kitty 0.49.2, lines "map cmd+k clear_terminal to_cursor active", "map opt+cmd+k clear_terminal scrollback active"]

**`map opt+left` with `macos_option_as_alt no`.** kitty's docs for the option say "any kitty shortcuts using Option/Alt+Key will take priority, so that any such key presses will not be passed to terminal programs running inside kitty" and "kitty itself always treats Option the same as Alt". [CITED: kitty 0.49.2 option documentation, read in the generated default config] That is documentation, not an observation: whether the macOS text system lets `opt+left` reach kitty's shortcut matcher with the switch off cannot be tested on this Linux host. Option+arrow does not produce a Unicode character, which makes it likely to arrive as a normal key event, but that is reasoning, not a test (A2). It stays a manual real-Mac UAT line (SKILL-05). There is no registry pin for kitty's version (no `version` key on the entry), so "the pinned version" is the installed 0.49.2; the Homebrew cask is at 0.51.0 today (API read 2026-11-20), two minors newer; the repo's registry comment still says 0.48.2.

**Reload (D-03), confirmed:** "automatic reload works only if the kitty.conf already exists when kitty is started" [VERIFIED: kitty 0.49.2 `auto_reload_config` text in the generated default config]; reload keys `ctrl+shift+f5` / `ctrl+cmd+,` and `SIGUSR1` [CITED: https://sw.kovidgoyal.net/kitty/conf/]. The note should say "restart kitty or press ... if it was already running without a kitty.conf".

**The scan (D-01).** Inputs: text outside the `kitty` and `kitty-keys` regions (two `replace_owned_region(..., None)` calls, as `user_document` does for Alacritty, terminal_regions.py:107-115), plus files named by plain `include` / `globinclude` lines (relative to the config directory, recursion guarded by a visited set, a depth cap), `geninclude` / `envinclude` reported "not followed". For every `map` line: strip leading `--option` words, take the next token as the chord, normalize. Normalization to implement: modifier aliases (`ctrl`/`control`, `alt`/`opt`/`option`, `super`/`cmd`/`command`, `shift`), `kitty_mod` replaced by the last `kitty_mod` assignment in the scanned text (default `ctrl+shift`), modifiers sorted, key lower-cased, and a `>` sequence counts as taken when its first chord equals ours (it turns our chord into a prefix). The alias list and `~`/env expansion inside `include` are not verified here (A1). Test every normalization through the same `load_config` backstop where kitty exists.

### WezTerm (TERM-02)

**Verified live on WezTerm 20240203-110809-5046fc22 (scratch configs, `wezterm --config-file X show-keys --lua`):**
- The stock set binds `K` + `CTRL`, `K` + `SHIFT|CTRL`, `k` + `SHIFT|CTRL` and `k` + `SUPER` to `ClearScrollback 'ScrollbackOnly'`; adding `{ key = "k", mods = "CTRL|SHIFT" }` collapses all three Ctrl+Shift+K entries into one `{ key = 'K', mods = 'CTRL' }` carrying our action. [VERIFIED: show-keys output lines 66-67 and 100-101 of the default dump, and the overridden dump]
- `{ key="K", mods="CTRL" }` and `{ key="k", mods="CTRL|SHIFT" }` are the same chord; with the user's entry first and ours second ours wins, and with ours first the user's wins. A later duplicate always wins. `CMD` normalizes to `SUPER`, `OPT` to `ALT`. [VERIFIED: scratch configs b.lua/c.lua/d.lua, outputs `K CTRL OURS`, `K CTRL USER`, `k SUPER OURSC`]
- `config.keys` is nil on a `wezterm.config_builder()` config with no keys set, and `config.keys = config.keys or {}` works. [VERIFIED: scratch e.lua]

**Required guard behavior (and the bug in the scratch guard):** the scratch guard (`p29/wz/guard.lua`) normalizes `CMD/WIN -> SUPER`, `OPT/META -> ALT`, `CONTROL -> CTRL`, sorts mods and lower-cases the key, but it does NOT treat an uppercase letter key with no explicit SHIFT as shifted. A user's `{key="K", mods="CTRL"}` lowercases to `k/CTRL`, our `k/CTRL|SHIFT` does not collide, and since ours is appended later it silently overrides the user (the exact prohibition "MUST NOT replace ... user's existing key bindings"). Fix: in `norm`/key handling, when the key is a single ASCII uppercase letter A-Z, lower-case it and add `SHIFT` to the mods before sorting. Test fixture: user `K`/`CTRL` kept, ours skipped. The planner must also fold `SHIFT|CTRL` and `CTRL|SHIFT` (sorting covers it).

**Do not rely on a `wezterm` local at the call site.** The scratch guard calls `act = wezterm.action` inside the region; a user config whose module local is named otherwise (`local wez = require "wezterm"`) would raise at load. Inside the region use its own `local wezterm = require "wezterm"` (the module is cached, so it is free). The shell region uses no module at all. [A11]

**Execution proof without wezterm (verified):** a Lua stub in `package.preload["wezterm"]` (returning `action` as a metatable factory and `config_builder`) runs the region in both luajit and Lua 5.4.9 and printed the user's `k CMD ActivateTabRelative` preserved, our `k CTRL|SHIFT` added and our `k SUPER` skipped, plus `LeftArrow OPT SendString \x1bb`. [VERIFIED: scratch stub.lua, 2026-11-20]. That gives an always-meaningful pure test where `lua`/`luajit` exist (skipif with a reason elsewhere) in addition to the always-run golden bytes and structural checks.

**Shell-region marker check (D-06).** Today: `"tools-installer terminal-shell wezterm" in existing` (terminal_shell.py:148), a substring test; the keys marker `... terminal-shell wezterm-keys >>>` contains it. With a keys region present and no shell region, `_wezterm_content` takes the "owned" branch and `_replace_owned_region` appends the shell region at END, after `return config`, where it never runs. [VERIFIED: terminal_shell.py:136-163 read; `replace_owned_region` appends when no exact marker line exists, terminal_regions.py:57-60]. Replace the substring test with "an exact region exists", i.e. `_replace_owned_region(existing, "wezterm", None, comment="--") != existing`, or fold into the `placement` call above (which removes the branch entirely). A comment line such as `-- see tools-installer terminal-shell wezterm docs` is then not an owned region.

**Cwd inheritance (D-07).** Docs for `SpawnTab`/`SpawnWindow` say nothing about the working directory [fetched wezterm.org SpawnTab/SpawnWindow pages 2026-11-20: no mention]. Source, at the pinned release tag `20240203-110809-5046fc22`: `SpawnWindow => self.spawn_command(&SpawnCommand::default(), SpawnWhere::NewWindow)` (termwindow/mod.rs:2499-2500); `spawn_command_internal` derives `current_pane_id` from the source window's active tab (spawn.rs:49-51, 92); the mux passes it to `resolve_cwd`; `LocalPane::get_current_working_dir` returns the OSC 7 URL or falls back to `divine_current_working_dir` (localpane.rs:504-510, process-based). So on Linux, without OSC 7, both tab and window spawn use the active pane's process cwd. [CITED: raw.githubusercontent.com/wezterm/wezterm at the pinned tag, read 2026-11-20] The D-07 container check (Xvfb is not on this host, no GUI here) is now a confirmation, not the first evidence; a headless alternative is `wezterm-mux-server` plus `wezterm cli spawn --pane-id`, which exercises the same `resolve_cwd` path but not the GUI `SpawnWindow` key action. macOS (libproc-based divine) stays UAT (A9). Declare `Vendor` with the dated source citation and mark the live confirmation unverified until done, per D-12.

### Alacritty (TERM-03)

The change is one tuple in `_KEY_BINDINGS`: `("K", "Control|Shift", 'action = "ClearHistory"')` becomes `("K", "Control|Shift", 'chars = "\\u000c"')`. In the TOML basic string `\u000c` is the form feed (Ctrl+L), written the same way as the Alt rows (`chars = "\\u001bb"`). [VERIFIED: installer/terminal_regions.py:139-143, same escape style]. The summary changes from `... Control+Shift+K clears history.` to text naming screen and scrollback. Drop `clear="ClearHistory"` (terminal_keys.py:132) and the comment at line 77; `clear_binding` then returns `("ctrl+shift+k", "\x0c")`. There is no Cmd+K row (no macOS method, D-08), so `plan` stays Linux-shaped.

**Tests that pin the old bytes (must change, with the reason "TERM-03 flips the clear row"):**
- `tests/test_terminal_keys.py:33` `_SUMMARY` (summary text), `:38` and `:44` (`_KEYS_REGION`, `_KEYS_REGION_NO_LEFT` contain `action = "ClearHistory"`), and `:599-603` `test_alacritty_keeps_clear_history_until_phase_29` (rename and rewrite: `row.clear == CTRL_L`, `clear_binding(row, "fedora") == ("ctrl+shift+k", "\x0c")`, region holds `chars = "\\u000c"`). [VERIFIED: tests/test_terminal_keys.py read]
- `tests/test_terminal_shell.py:1169`: `assert keys_only["keyboard"]["bindings"][2]["action"] == "ClearHistory"` becomes `["chars"] == "\x0c"`. Its neighbors at `:1167-1168` (the two Alt rows) stay unchanged, which is SPEC R3's "byte-identical Alt rows". [VERIFIED: tests/test_terminal_shell.py:1163-1170]
- `rg` found no other pin of `ClearHistory`, `clears history` or `Control+Shift+K` in `tests/`, `installer/` or `scripts/`. [VERIFIED: rg over tests, installer, scripts]
- The 28 D-12 rule ("existing tests stay unedited except four import lines") bound phase 28 only; these are the same intentional flips that phase named ("Alacritty's clear action flips in phase 29").

**Existing installs (D-08 depends on 28 D-06):** a recorded present region differing from its render reads `KEYS_PENDING`, and reconfigure rewrites it; this works today because `terminal_keys_pending` and `apply_terminal_keys` compare the whole region. Add one test: install old bytes, assert `terminal_keys_pending` is `KEYS_PENDING`, reconfigure, assert the new bytes and no duplicate region. [VERIFIED: terminal_keys.py:179-181, 213-221]

### Konsole (TERM-04, report-only per D-09)

**What can be read without writing.** The format and the location are now verified from KDE sources (not only from strings in a library):
- `KXMLGUIClient::localXMLFile()` returns `QStandardPaths::writableLocation(GenericDataLocation) + "/kxmlgui5/%1/%2"` with component name and xml file, so for Konsole `$XDG_DATA_HOME/kxmlgui5/konsole/sessionui.rc` (Konsole calls `setXMLFile(QStringLiteral("sessionui.rc"))`). [CITED: invent.kde.org/frameworks/kxmlgui `src/kxmlguiclient.cpp` line ~160; invent.kde.org/utilities/konsole `src/session/SessionController.cpp`, both fetched 2026-11-20]. The installed KF6 XmlGui library on the host contains the strings `/kxmlgui5/%1/%2` and `:/kxmlgui5/`, so the directory name is still `kxmlgui5` on KF 6.31. [VERIFIED: `strings /usr/lib64/libKF6XmlGui.so.6`]. The component name `konsole` is assumed from the application name (A4).
- A user change is written by `KActionCollectionPrivate::writeKXMLGUIConfigFile`: inside the `<ActionProperties>` element, `act_elem.setAttribute("shortcut", QKeySequence::listToString(action->shortcuts()))`; when the shortcut is back at its default the attribute is removed and a bare element is dropped. A cleared shortcut serializes as the empty list, i.e. `shortcut=""`. [CITED: invent.kde.org/frameworks/kxmlgui `src/kactioncollection.cpp` `writeKXMLGUIConfigFile`, fetched 2026-11-20]. When no XML file exists for the client the same API falls back to the `[Shortcuts]` group of the app's KConfig file (`konsolerc`), where a cleared key is the string `none` and a default equal entry is deleted [CITED: same file, `writeSettings`]; reading `konsolerc` `[Shortcuts]` for `clear-history-and-reset` as a second source costs one read and covers that path (recommended, cheap).
- The stock action: `collection->addAction("clear-history-and-reset", ...)` with `setDefaultShortcut(action, Konsole::ACCEL | Qt::Key_K)`; there is also a `clear-history` action with no default shortcut. [CITED: konsole `SessionController.cpp`, fetched 2026-11-20]. `Konsole::ACCEL` is Ctrl+Shift on Linux (not read in this session, A4); the actual chord string needs the D-09 container capture or a real Konsole.
- The compiled-in label strings "Clear Scrollback" and "Clear Scrollback and Reset" are in `libkonsoleprivate.so.26.08.2` on the host. [VERIFIED: `strings`]

**Detector design (regex, no XML parser):** find `<Action ... name="clear-history-and-reset" ... />` (attributes in any order, single or double quotes); no match or no `shortcut` attribute means stock; split the value on `;`, normalize each (strip spaces, lower-case, modifiers sorted) and report stock if any equals `ctrl+shift+k`, removed otherwise (empty or lacking it). A missing file, a non-UTF-8 file or an unparsable line must read as "stock/unknown", never raise out of the sync (it is a secondary effect; `terminal_sync_warning` already guarantees it never takes the caller down, terminal_shell.py:58-84).

**Where to report.** `_sync_konsole` returns `(configured, warning, drifted)` and is "unchanged" under TERM-04; the new check is a separate read-only helper called beside it in `sync_terminal_shells`, gated the same way (konsole present, zsh present). The sync is Linux-only (`platform.os == "macos"` returns at once) and runs for every lifecycle route and every refresh dry run, and `warnings` render as "Terminal shell synchronization warning: ..." (`sync_message`, terminal_shell.py:755-775). Consequences:
- `removed` is naturally a `warnings` entry (`konsole: partial: you removed Ctrl+Shift+K; kept yours`), the same channel the Alacritty `partial:` lines use (terminal_shell.py via `_keys_plan`).
- `stock` is not a warning, and printing it on every refresh would be noise. Recommended: a new `TerminalShellResult.notes: tuple[str, ...] = ()` rendered by `sync_message(report_changes=True)` only when Konsole's profile was newly written (it is already in `drifted`), appended to the existing `Shell: konsole now starts zsh` part. This keeps the existing exact-string assertions (e.g. tests/test_terminal_shell.py:1105 `"Shell: kitty now starts zsh" in message`, tests/test_version_status.py `report="Konsole now starts zsh"`) intact, since they match on the original part. Open question O1 (the owner may prefer a different channel).
- Existing Konsole tests (75 `konsole` references in tests/test_terminal_shell.py) must pass unedited: a fixture home with no `sessionui.rc` is `stock` and adds nothing to `warnings`, `drifted` or `configured`.

**Behavior note (A5):** the vendor action is "Clear Scrollback and Reset", which resets the terminal (it clears screen and scrollback, but does not redraw the prompt the way Ctrl+L does). It meets "clears screen and scrollback"; the report line should say what the chord does rather than claim Ctrl+L parity.

### herdr (TERM-05)

**What the proof needs.** A live herdr client on a pty, a pane whose shell is a recorder that puts the pty in raw mode and logs each read as hex, then the host-terminal input sent to the client pty. The scratch probe (`p29/scripts/{drive.py,recorder.py,in_container.sh,recshell.sh}`) does exactly that: config `onboarding = false`, `[update] version_check = false`, `manifest_check = false`, `[terminal] default_shell = <recorder>`, HOME `/h`, `XDG_RUNTIME_DIR` mode 700, scrubbed environment, 12 s startup pump, then each chord with a 1.5 s pump. [VERIFIED: scratch scripts read this session]

**Evidence gap to close in the target.** The persisted scratch record `hd/rec.log` holds `START`, `1b62`, `1b66`, `1b5b313b3344`, `0c`, `30`. The drive script sends CSI-u alt+b, alt+f, `\x1b[1;3D` (Alt+Left), CSI-u ctrl+l and a keypad sequence; it never sends Alt+Right (`\x1b[1;3C`), so D-10's `1b5b313b3343` is not in the persisted log or script as they stand. [VERIFIED: rec.log and drive.py read]. The container target must send Alt+Left and Alt+Right raw and CSI-u, plus the clear chord, and assert all of `1b62`, `1b66`, `1b5b313b3344`, `1b5b313b3343`, `0c`, with the expected-versus-received comparison a pure function.

**What can be tested without a live pane.** Pytest-level, always-run: (a) a pure verdict function over a recorder log (canned logs for pass, each chord missing, intercepted and re-encoded); (b) host tests of the script text with a stubbed container call, following `tests/test_container_e2e_bun.py` (which reads the committed script, runs extracted bash functions with a stub `ct`, never starts a container, and imports the driver "for its pure verdict functions only"); (c) a registry assertion that herdr declares no `apply_terminal_tuning` and has no row (so completeness never asks for one). The live proof is orchestrator-only like `bun-lifecycle`, `schedules`, `audit-landing` and `nested`, each of which has a `cmd_*` function and a `test_container_e2e_*.py` host test (scripts/container-e2e-verify.sh:119-131, 2859-2929). The new verb prints a `TRACER_HERDR_KEYS_*` verdict, removes its container and image by exact name, and `make shellcheck` covers the script (Makefile:58).

### Registry change for kitty (D-05)

Current entry: Linux `script` method (`os = ["debian","arch","fedora"]`, `bin_dir = "~/.local/kitty.app/bin"`, `paths = ["~/.local/kitty.app/"]`), a macOS `script` method (`bin_dir = "/Applications/kitty.app/Contents/MacOS"`, no `paths`), `dnf`/`apt`/`pacman`, and `cask` (`os = ["macos"]`, `cask = "kitty"`, `app = "kitty.app"`, `min_os_version = "12"`). [VERIFIED: installer/registry.toml:3030-3066]. The change deletes the macOS `script` block and its two comment lines (3040-3049); the `cask` method stays.

**What pins the macOS script (each must change in the same commit):**
- `tests/test_registry.py:1542`: `[m.kind for m in resolve_methods(kitty, macos)] == ["cask", "script"]` -> `["cask"]`.
- `tests/test_registry.py:1613-1614` (`test_kitty_cask_blocks_a_too_old_macos_version`): macOS 11 resolves `["script"]` and macOS 12 resolves `["cask","script"]` -> macOS 11 resolves `[]` and macOS 12 `["cask"]`. This is a real behavior change: macOS older than 12 and macOS without Homebrew (the cask needs `platform.has_brew`, installer/resolve.py:82-85) have no kitty method. `platform_could_support` probes with `has_brew=True` (resolve.py:236-242), so kitty stays listed on a brew-less Mac and becomes installable once brew is present, the same position WezTerm's cask-only macOS route is in. Whether kitty 0.49+ even runs on macOS 11 is unverified (A3); the cask floor is `depends_on.macos >= 12` [VERIFIED: formulae.brew.sh/api/cask/kitty.json, fetched 2026-11-20].
- `tests/test_registry.py:2578-2600` `test_audit_fix_e8_kitty_script_covers_macos`: delete or rewrite as "kitty's macOS route is the cask and no method names `/Applications`" (this is the requested regression: iterate `kitty.methods`, assert no param value contains `/Applications`).
- `tests/test_registry.py:2763-2772` `SCRIPT_LIFECYCLE_DATA[("kitty", ("macos",), ())]`: remove the key; `_script_stanza` asserts exactly one stanza per key and would fail otherwise.
- `tests/test_registry.py:1649-1663` `test_kitty_entry_records_why_it_uses_the_vendor_script` requires the fragments `.txz`, `download.py`, `archive = "xz"`, `x86_64_linux`, `platform.os == "macos"` in the 40 lines above `id = "kitty"`; they live in the untouched comment block (registry.toml:2982-3016). Do not delete those lines; add the new `# Verified` text next to the removed block instead.
- `tests/test_resolve.py:612` has `"kitty": "cask"` (macOS first method) and 700/788/876 have `"kitty": "script"` (Linux platforms); unchanged by this edit because they select the first method per platform. [VERIFIED: sed of those lines]
- `make verify-registry` (`installer/verify_registry.py`) has no kitty-specific code (no `kitty` match; its checks iterate `CHECKABLE_KINDS`, `app`, `tarball`, `github_release`, `uv`), so it neither pins nor needs the macOS script. [VERIFIED: rg over installer/verify_registry.py; not read in full, A7]
- The registry loader has no rule requiring a macOS method per tool; removal and ownership read the method list generically. [ASSUMED from the loader read at installer/model.py:570-590 only; the executor should run `tests/test_registry.py` and `tests/test_ownership.py -k kitty` after the edit]
- `.planning/audits/catalog/2026-11-13/kitty.md:23,28` records the macOS script as a removal gap; this removal closes it and the audit file is not edited (history).

**The cask and `--appdir`:** `_cask` runs `brew install --cask --appdir=<applications_dir()> kitty` (installer/executors.py:696-704, read). The cask's artifacts (formulae.brew.sh API, 2026-11-20): `app kitty.app`, `command_wrapper kitty` with `executable $APPDIR/kitty.app/Contents/MacOS/kitty` targeting `$HOMEBREW_PREFIX/bin/kitty`, and the same for `kitten`. So under `--appdir=~/Applications` the wrapper resolves to the user location (the stanza uses `$APPDIR`), and the CLI is linked into the Homebrew prefix `bin`, not `~/.local/bin`: the cask gap the `# Verified` comment must state (SKILL-04 "or the entry says why not"). [VERIFIED: brew cask JSON read this session]. Whether the wrapper honors `--appdir` at install time was not run (no Mac here); it follows from `$APPDIR` (A12).

### Skill table cells (D-12) and the tests that pin them

Cells in `.claude/skills/tool-onboarding/SKILL.md` (table at lines 209-218, intro 207, Konsole sentence 220, conflicts 224-225): kitty (b)(c)(d) move from `planned (phase 29)` to `written`; WezTerm (b) and (c) to `written`, (d) to `vendor` (source-cited, live-unverified); Alacritty (c) to `written`, (d) stays `unverified` or becomes `vendor` per its row's dated note; herdr (b)(c) become `vendor` (verified pass-through, 29 D-10) and (d) `vendor` (`new_cwd = "follow"` is the vendor default per D-10); the Konsole sentence changes to "stock Ctrl+Shift+K clear, reported not written". Each cell must keep starting with a status word: `STATUS_RE` accepts `vendor`, `written`, `unverified`, `n/a`, `planned (phase N)` followed by `:` or end. [VERIFIED: tests/test_tool_onboarding_skill.py:36 and test_table_rule_cells_start_with_a_status_word]

Tests that pin skill text and will need an edit:
- `test_conflicts_two_clauses_with_examples` (tests/test_tool_onboarding_skill.py:341-364) requires the literal `planned for phase 29` plus `scroll_line_up` in the second conflict clause, and `kitty` absent from the first. When the example stops being "planned" (it is written now), change the phrase in both the skill and the test together.
- `test_conflicts_names_the_real_partial_lines` (`:367-381`) pins `alacritty: partial: you already bind` and source-file mentions; the kitty/konsole `partial:` wording belongs there too once written.
- Ascii/format tests (`test_rules_and_table_sections_are_ascii`, `test_conflicts_sits_in_step_7_and_is_ascii`) apply to the new text. The status-word ASCII rule means no typographic dashes or arrows in table cells.
- `tests/test_docs.py` reads the skill among rule documents (`_rule_document_paths`, lines 15-30) for link and format checks; keep links valid.

**docs-only / TEST_READ / LEDGER (checked):** `devtools/docs_only.py` marks `.claude/*`, `scripts/*`, `tests/*` as TEST_READ, so a skill edit or a script edit is never docs-only and runs the full CI; `.planning/*` is docs-only. Every file this phase touches except the planning files is code or TEST_READ, so the fast pass never applies. `tests/test_docs_only.py` has a `LEDGER` listing every Markdown-file literal in test files (`markdown_literals()`), failing on a new or stale pair: a new test that mentions a `.md` file name (for example `SKILL.md`) in a string literal needs a LEDGER entry, and a test that only calls helpers needs none. [VERIFIED: devtools/docs_only.py:20-36 and tests/test_docs_only.py:209-300 read]. Keep new tests free of `.md` literals; `tests/test_tool_onboarding_skill.py` already has its `SKILL.md` entries.

### Anti-Patterns to Avoid
- **Appending the kitty or WezTerm keys region at the end:** kitty is last-wins so the installer would beat user maps; WezTerm's append lands after `return config`. That is the whole reason for `placement`.
- **A substring test for an owned region:** the keys marker contains the shell marker. Use exact line equality (the existing primitive).
- **Normalizing WezTerm mods without the uppercase-letter rule:** silently overrides a user's `K`+`CTRL`.
- **Writing a herdr or Konsole row to "satisfy the table":** a row that writes nothing reads `≈ apply install tuning` forever (28 D-06, D-10); Konsole is not a catalog entry at all.
- **A pytest that skips silently for the herdr proof:** the repo's tests/CI have no herdr; use the container target plus pure verdict tests.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Marker-delimited owned regions | A second region parser | `terminal_regions.replace_owned_region` / `strip_region` / `commit_region` | Exact line matching, malformed-marker refusal, compare-before-commit, created-file bookkeeping |
| Atomic, compare-before-commit writes | `open(..., "w")` | `write_if_unchanged`, `atomic_write_text` | Already used by every row |
| Alacritty config path | Another resolver | `alacritty_config_path` as the model for `kitty_config_path` | Same first-existing shape |
| Parsing Konsole XML | `xml.etree` or a new dependency | A regex on one attribute | bandit flags `xml.etree`; one attribute is all that is read |
| Lua syntax validation in Python | A Lua parser | Structural check (markers, one `return config`, region before it) plus optional `luajit -bl` | A parser is a dependency for no behavior gain |
| kitty chord semantics | A custom keymap engine | Normalize the few modifier aliases and verify against `kitty.config.load_config` where kitty exists | kitty's own parser is the oracle |
| Container lifecycle | A new harness | `scripts/container-e2e-verify.sh` verb pattern (`bun-lifecycle`, `schedules`) | Detection, naming, removal-by-exact-name are already solved |

**Key insight:** every hard part (ownership, drift, atomic commit, strip, completeness) already exists; the phase's risk is in per-terminal key semantics (kitty last-wins, WezTerm shifted-key identity, KDE's saved format), not in file handling.

## Common Pitfalls

### Pitfall 1: kitty macOS cwd and clear rows displace more than `scroll_line_up`
**What goes wrong:** the note names only `scroll_line_up`; macOS `cmd+k` silently replaces `clear_terminal to_cursor`. **Why:** D-03 was written from the Linux default. **How to avoid:** the note is built per OS from the rows actually added. **Warning signs:** a macOS golden whose note text is the Linux text.

### Pitfall 2: A scan that skips only `kitty.conf`
**What goes wrong:** a themed config maps `ctrl+shift+k` in an included file and the installer reports nothing; it still loses to the include only if the include comes after the region. **Why:** `include` order. **How to avoid:** scan plain `include`/`globinclude` (D-01), guard cycles, report `geninclude`/`envinclude` as not followed. **Warning signs:** an include line above the region that maps a chord the scan did not see.

### Pitfall 3: `clear_all_shortcuts yes` after the region
**What goes wrong:** the user's own `clear_all_shortcuts yes` (later in the file) wipes the installed maps and the row reads installed but does nothing. **How to avoid:** detect the directive in the scanned text and report `kitty: partial: ...` instead of claiming success. The default is `no` ("clear_all_shortcuts no" in the 0.49.2 defaults); behavior of the directive is documented, not tested here (A6). Open question O4.

### Pitfall 4: A kitty config in `~/Library/Preferences` on macOS
**What goes wrong:** the installer creates `~/.config/kitty/kitty.conf`; kitty finds it first and ignores the user's Preferences file. **How to avoid:** the first-existing resolver (verified order above); a Preferences-only config is edited in place. **Warning signs:** a test with only `~/Library/Preferences/kitty/kitty.conf` that expects the file created under `~/.config`.

### Pitfall 5: Weak WezTerm `validate`
**What goes wrong:** `validate_toml` on a Lua file raises for every input. **How to avoid:** a Lua structural validator: exactly one `return config` line after the region's end marker, both markers exactly once and in order, and the text outside the region byte-identical to the input (that last check is what protects user keys). A syntax error inside the region cannot occur because the body is generated; the optional `luajit -bl` run is a backstop only.

### Pitfall 6: `Writes` gives kitty the wrong lines on one OS
**What goes wrong:** a single constant snippet ships macOS `cmd+t` lines to Linux. **How to avoid:** the per-OS callable (see D-11 item 3) and a golden per OS.

### Pitfall 7: WezTerm skeleton after strip
**What goes wrong:** a created-from-skeleton `wezterm.lua` keeps `local config = {} return config` after uninstall (not whitespace-only, so `_drop_created_config` keeps it). **How to avoid:** compare the remainder to the seed (Open question O3).

### Pitfall 8: Per-row `post_install` also enables the pending fact on hosts that never ran it
**What goes wrong:** giving kitty and WezTerm `post_install = ["apply_terminal_tuning"]` makes every existing install read `≈ apply install tuning` on the next refresh (no record, no region = pending, terminal_keys.py:224). **Why:** that is the intended 28 D-06 semantics, but it is a visible catalog-wide change. **How to avoid:** the plan's verification step expects it, and `tests/test_version_status.py` rows for kitty/WezTerm that assert exact config steps need to be reviewed (4644, 4657 reference `terminal_sync` steps, not tuning, so they should be unaffected; run them).

### Pitfall 9: herdr proof flakiness
**What goes wrong:** the server does not become ready (long HOME, socket path limit), the first-run popup eats input, `HERDR_*` leaks from the caller. **How to avoid:** the D-10 settings (`onboarding=false`, checks off, short HOME, scrubbed env) as committed constants in the target; a verdict that distinguishes "not ready" (infeasible) from "bytes wrong" (failed), like the other targets' `*_INFEASIBLE` lines.

## Code Examples

### kitty config directory (the kitty order, replicate)
```python
# Source: https://raw.githubusercontent.com/kovidgoyal/kitty/v0.49.2/tools/utils/paths.go (ConfigDirForName), read 2026-11-20
def kitty_config_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    override = environ.get("KITTY_CONFIG_DIRECTORY")
    if override:
        return Path(override).expanduser() / "kitty.conf"
    roots: list[Path] = []
    for raw in (environ.get("XDG_CONFIG_HOME"), *environ.get("XDG_CONFIG_DIRS", "").split(":")):
        if raw:
            roots.append(Path(raw))
    roots.append(home / ".config")
    if platform_os == "macos":
        roots.append(home / "Library" / "Preferences")
    for root in dict.fromkeys(roots):
        directory = root / "kitty"
        if (directory / "kitty.conf").exists() and os.access(directory, os.W_OK):
            return directory / "kitty.conf"
    return Path(environ.get("XDG_CONFIG_HOME") or home / ".config") / "kitty" / "kitty.conf"
```

### Placement in the region primitive
```python
# Source: shape of installer/terminal_regions.py:57-60 extended; behavior of the existing insertion at terminal_shell.py:158-163
region = f"{begin}\n{body}\n{end}\n"
if complete is None:
    if placement is Placement.TOP:
        return region + content
    if placement is Placement.BEFORE_RETURN:
        indexes = [i for i, line in enumerate(lines) if line.strip() == "return config"]
        if len(indexes) != 1:
            raise TerminalShellError("unsupported return shape")
        return "".join((*lines[: indexes[0]], region, *lines[indexes[0] :]))
    prefix = content if not content or content.endswith(("\n", "\r")) else f"{content}\n"
    return f"{prefix}{region}"
```

### WezTerm keys region (verified guard shape, with the uppercase fix and its own module local)
```lua
-- >>> tools-installer terminal-shell wezterm-keys >>>
do
  local wezterm = require "wezterm"
  local act = wezterm.action
  local function norm(key, mods)
    local set = {}
    for m in string.gmatch(string.upper(mods or ""), "[^|]+") do
      m = ({ CMD = "SUPER", WIN = "SUPER", OPT = "ALT", META = "ALT", CONTROL = "CTRL" })[m] or m
      if m ~= "NONE" then set[#set + 1] = m end
    end
    if string.match(key, "^%u$") then set[#set + 1] = "SHIFT" end  -- K alone means Shift+k
    table.sort(set)
    return string.lower(key) .. "/" .. table.concat(set, "|")
  end
  config.keys = config.keys or {}
  local taken = {}
  for _, k in ipairs(config.keys) do taken[norm(k.key, k.mods)] = true end
  for _, k in ipairs({
    { key = "k", mods = "CTRL|SHIFT", action = act.SendString "\x0c" },
    -- macOS rows (SUPER k, OPT LeftArrow \x1bb, OPT RightArrow \x1bf) are generated per OS
  }) do
    if not taken[norm(k.key, k.mods)] then table.insert(config.keys, k) end
  end
end
-- <<< tools-installer terminal-shell wezterm-keys <<<
```
Source: adapted from `p29/wz/guard.lua`, run live under `wezterm show-keys`, luajit and Lua 5.4 in this session; the uppercase rule and the module local are the two changes, both reasoned from the verified duplicate-chord behavior (the uppercase rule itself was not executed; the test fixture must).

### Konsole detector
```python
# Source: attribute shape from KXMLGUI writeKXMLGUIConfigFile (shortcut attribute on <Action name=...>), read 2026-11-20
_ACTION = re.compile(r'<Action\b[^>]*\bname\s*=\s*["\']clear-history-and-reset["\'][^>]*>')
_SHORTCUT = re.compile(r'\bshortcut\s*=\s*["\']([^"\']*)["\']')
def konsole_clear_is_stock(rc_text: str) -> bool:
    match = _ACTION.search(rc_text)
    shortcut = _SHORTCUT.search(match.group(0)) if match else None
    if shortcut is None:
        return True
    return any(
        "".join(sorted(part.lower().replace(" ", "").split("+"))) == "".join(sorted("ctrl+shift+k".split("+")))
        for part in shortcut.group(1).split(";")
    )
```

### Verdict function for the herdr target (pure, testable)
```python
# Source: byte table from 29 D-10 and the scratch rec.log (hex of each read)
EXPECTED = ("1b62", "1b66", "1b5b313b3344", "1b5b313b3343", "0c")
def herdr_keys_verdict(recorded: Sequence[str]) -> list[str]:
    return [f"missing {hexed}" for hexed in EXPECTED if hexed not in recorded]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| kitty config only in `~/.config/kitty` | `KITTY_CONFIG_DIRECTORY`, XDG, `XDG_CONFIG_DIRS`, `~/.config`, macOS Preferences, first existing and writable | v0.49.2 source | Resolver must match, or the installer hides a user's config |
| `macos_option_as_alt` for word navigation | Two `map opt+left/right send_text` rows | owner decision, SKILL-01 | No global switch; real-Mac check stays UAT |
| Alacritty `ClearHistory` (scrollback only) | `chars = "\u000c"` | this phase | Matches the shared Ctrl+L clear |
| Konsole shortcuts only in `konsolerc` `[Shortcuts]` | Saved into the XML rc (`kxmlgui5/<app>/<file>`) when the client has an XML file, else `[Shortcuts]` | kxmlgui master | Read both |

**Deprecated/outdated:** the registry's kitty macOS `script` method (writes `/Applications`, no removal); the `# Verified 2026-09-06` cask version note (0.48.2) is two minors stale (cask API reads 0.51.0).

## Runtime State Inventory

Not a rename/refactor phase, but it changes already-installed behavior; the categories answered:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Recorded Alacritty installs hold `terminal-tuning-alacritty` plus a region with `ClearHistory` under `$XDG_DATA_HOME/tools-installer/` | None to code beyond the 28 D-06 drift rule; add the old-bytes-to-new-bytes test |
| Live service config | None (no service holds these strings) | None, verified by scope |
| OS-registered state | A macOS user who installed kitty through the script has `/Applications/kitty.app` outside any record | None here; the cask route installs a second copy under `~/Applications`; the install note or UAT should say the old bundle is the user's to remove (no `paths`, never owned) |
| Secrets/env vars | None | None |
| Build artifacts | kitty/WezTerm/herdr existing installs have no `terminal-tuning-*` record, so they read `≈ apply install tuning` after the registry gains `post_install` (kitty, wezterm) | Expected catalog-wide effect; verify in the plan (Pitfall 8) |

## Common Pitfalls (continued): provenance of the tests that must move

See sections above for per-terminal test edits. Summary of test files touched: `tests/test_terminal_keys.py` (Alacritty bytes, field list if `KeysRow` changes, fixture `plan` signature), `tests/test_terminal_shell.py:1169`, `tests/test_registry.py` (1542, 1613-1614, 2578-2600, 2763-2772), `tests/test_tool_onboarding_skill.py` (conflict phrase, any table-cell pins), plus new tests below.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | kitty modifier aliases (`ctrl`/`control`, `alt`/`opt`/`option`, `super`/`cmd`/`command`, `shift`) and `~`/env-var expansion inside `include` paths | kitty scan | The scan misses a taken chord or fails to follow an include; verify through `load_config` on a fixture |
| A2 | `map opt+left` reaches kitty's shortcut matcher with `macos_option_as_alt no` (docs say Option/Alt shortcuts take priority; Option+arrow produces no character) | kitty | The two word-navigation rows do nothing on a real Mac; UAT on the owner's Mac |
| A3 | macOS older than 12 loses kitty when the script method is dropped; kitty's own floor there is unknown | Registry change | A small set of macOS 11 users cannot install kitty through the catalog; owner confirmation |
| A4 | `Konsole::ACCEL` is Ctrl+Shift on Linux and the KXMLGUI component name is `konsole` (so the rc path is `kxmlgui5/konsole/sessionui.rc`) | Konsole | The detector reads the wrong file or chord; the D-09 container capture is the check |
| A5 | "Clear Scrollback and Reset" does not redraw the prompt (differs from Ctrl+L) | Konsole | The report wording over-claims parity |
| A6 | `clear_all_shortcuts yes` after the region wipes the installed maps | kitty pitfalls | A wrongly "installed" row; low frequency |
| A7 | `installer/verify_registry.py` has no kitty-specific pin (rg showed no match; not read end to end) | Registry change | `make verify-registry` fails on a removed method; run it (network) after the edit |
| A8 | The loader and ownership layers accept a tool without a macOS method (read only the path-validation part) | Registry change | `tests/test_ownership.py`/`test_registry.py` fail; run them |
| A9 | WezTerm `SpawnTab`/`SpawnWindow` inherit the cwd on macOS (libproc-based fallback) | WezTerm | The `vendor` declaration is false on macOS; UAT |
| A10 | herdr's Alt+Right raw bytes (`1b5b313b3343`) arrive intact (D-10 states it; the persisted scratch log/script do not show it) | herdr | The proof target fails on first run; it must send and assert it |
| A11 | A user WezTerm config may name its module local differently from `wezterm` | WezTerm Lua | The region errors at load without its own `require` |
| A12 | The brew `command_wrapper` honors `--appdir` via `$APPDIR` at install time (cask JSON says `$APPDIR/kitty.app/...`; not run on a Mac) | Registry change | The CLI wrapper points to `/Applications`; UAT on the owner's Mac |

## Open Questions

1. **Where does the Konsole "stock" report appear (O1)?**
   - What we know: `warnings` renders as "Terminal shell synchronization warning" on every sync; there is no info channel.
   - What's unclear: whether the owner wants a visible line at all after the first install.
   - Recommendation: `TerminalShellResult.notes`, shown only with the newly written Konsole profile; the `removed` case is a normal `warnings` entry.
2. **Does the macOS note also name `clear_terminal to_cursor` (O2)?** SKILL-03 says displaced vendor defaults are named. Recommendation: yes, and the `*_with_cwd` replacements in one phrase.
3. **WezTerm skeleton cleanup on strip (O3)?** Recommendation: treat remainder == seed as ours in `_drop_created_config`.
4. **`clear_all_shortcuts yes` (O4):** report `partial` or ignore? Recommendation: report.
5. **`Writes` and `plan` signature changes (D-11 items 3-4):** the planner picks the exact types; the recommendation (callable `Writes.snippet`, third `plan` argument) edits two lines of the Phase 28 test file.
6. **macOS dry-run of the kitty row:** the `post_install` runs on macOS with `Path.home()`; golden tests must use a scratch HOME and both `platform_os` values (no host write).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv / pytest | all tests | yes | `tests/test_terminal_keys.py` ran green, 33 tests | none needed |
| kitty | optional `load_config` backstop | yes (host) | 0.49.2 | skipif with reason; CI has none |
| wezterm | optional `show-keys` backstop | yes (host) | 20240203-110809-5046fc22 | skipif |
| luajit / lua | optional Lua region execution | yes (host) | luajit present; Lua 5.4.9 | skipif; golden + structural tests always run |
| zsh | existing widget tests | yes | 5.9.2 | n/a |
| konsole | read-only background only | yes (host) | 26.08.2 | never launched; no live capture without a container |
| herdr | herdr container target | yes (host) | 0.9.5 | binary copied into the disposable container |
| podman | container targets | yes | 6.1.3 | `scripts/detect-container-runtime.sh` |
| Xvfb / xvfb-run | WezTerm GUI cwd check | no | none | source citation + headless `wezterm-mux-server` check; real GUI is UAT |
| alacritty | none (TOML only) | no | none | not needed |

**Missing dependencies with no fallback:** none blocking.
**Missing with fallback:** Xvfb (WezTerm GUI cwd), Konsole live capture (the KDE source citation replaces it; capture remains the planned container confirmation).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (xdist, coverage), `addopts = "-q"`, `testpaths = ["tests"]` [VERIFIED: pyproject.toml `[tool.pytest.ini_options]`] |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py -q -n 0` (targeted; no xdist) |
| Full suite command | `make validate && make test` (once after a plan; AGENTS.md) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TERM-01 | kitty golden bytes per OS (created file; user content with the region at the TOP; user-mapped chord skipped with `kitty: partial: you already map ...`; include scan; `macos_option_as_alt` absent; note names `scroll_line_up`) | unit (pure, always runs) | `uv run pytest tests/test_terminal_keys.py -k kitty -n 0` | extend tests/test_terminal_keys.py (Wave 0) |
| TERM-01 | kitty config resolver order (env, XDG, `~/.config`, macOS Preferences, existing+writable, fallback) | unit | `uv run pytest tests/test_terminal_keys.py -k kitty_path -n 0` | Wave 0 |
| TERM-01 | generated map lines load in real kitty | integration, `skipif(which("kitty") is None, reason=...)` | same file | Wave 0 |
| TERM-01 | macOS kitty route is the cask, no `/Applications` in any method; macOS 11 and no-brew resolution | unit | `uv run pytest tests/test_registry.py -k kitty -n 0` | edit existing |
| TERM-02 | WezTerm region placed before the single `return config`; user keys kept in order; apply twice = once; both regions coexist, strip each independently; marker-lookalike comment not an owned region; no/two `return config` refused | unit | `uv run pytest tests/test_terminal_keys.py -k wezterm -n 0` and `tests/test_terminal_shell.py -k wezterm -n 0` | Wave 0 |
| TERM-02 | Guard keeps user `K`+`CTRL`, `CMD k`; adds the rest | integration, `skipif(no lua/luajit)` with the stub | same | Wave 0 |
| TERM-03 | Alacritty region has `chars = "\u000c"` on the clear row; Alt rows byte-identical; recorded old-bytes install reads `KEYS_PENDING` then reconfigure rewrites | unit | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py -k alacritty -n 0` | edit existing + 1 new |
| TERM-04 | Detector: no file, no override, stock chord, `shortcut=""`, other chord, `; ` list, single/double quotes, unreadable; sync leaves Konsole files byte-identical; existing Konsole tests unedited | unit | `uv run pytest tests/test_terminal_shell.py -k konsole -n 0` | Wave 0 (new tests), existing pass |
| TERM-05 | Pure verdict function; host test of the target script text with a stubbed `ct`; herdr has no keys row and no `apply_terminal_tuning` | unit | `uv run pytest tests/test_container_e2e_herdr_keys.py -n 0` | Wave 0 (new file) |
| TERM-05 | Bytes arrive inside a live herdr pane | container (orchestrator-only) | `scripts/container-e2e-verify.sh herdr-keys` | Wave 0 (new verb) |
| D-12 | Skill cells and the conflicts phrase | unit | `uv run pytest tests/test_tool_onboarding_skill.py tests/test_docs.py -n 0` | edit existing |
| Mechanism | Completeness (every `apply_terminal_tuning` declarer has a row, no row for herdr/konsole), `KeysRow`/`OwnedRegion` field set, same-directory still required | unit | `uv run pytest tests/test_terminal_keys.py -k "completeness or fields or same_directory" -n 0` | edit existing |

### Sampling Rate
- **Per task commit:** the targeted `-k` line of the task's rows above.
- **Per wave merge:** `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_registry.py tests/test_resolve.py tests/test_tool_onboarding_skill.py tests/test_docs.py tests/test_post_install.py tests/test_version_status.py -q -n 0`.
- **Phase gate:** `make validate && make test` green on the exact tree; `make hooks-e2e` not needed; the herdr container verb and `make verify-registry` (network) once.

### Wave 0 Gaps
- [ ] `tests/test_terminal_keys.py`: kitty goldens (both OSes), resolver, scan, WezTerm region fixtures, Lua stub execution, Alacritty drift-to-new-bytes, Konsole detector, `OwnedRegion` placement tests (TOP, BEFORE_RETURN with zero, one and two `return config`).
- [ ] `tests/test_container_e2e_herdr_keys.py` and `tests/e2e_herdr_keys_driver.py`: verdict function and script-text host tests (pattern: tests/test_container_e2e_bun.py).
- [ ] `scripts/container-e2e-verify.sh`: `herdr-keys` verb with a `TRACER_HERDR_KEYS_*` verdict, usage text, `make shellcheck` clean.
- [ ] Edits to existing tests listed in the Alacritty, Registry and Skill sections (named, deliberate, each with its reason).
- [ ] No new `.md` literal in a test (LEDGER).
- [ ] Framework install: none.

Real-Mac checks that stay manual (SKILL-05, deferred UAT): kitty `opt+left`/`opt+right` bytes with `macos_option_as_alt no`; kitty `cmd+k` and `cmd+t/n/enter`; the cask wrapper under `--appdir`; kitty config in `~/Library/Preferences`; WezTerm `SUPER k`, `OPT LeftArrow`, cwd inheritance; herdr on macOS.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | yes | The config text is untrusted input: exact-marker matching, `validate` before write, UTF-8 refusal (`snapshot_text`), refuse a file the plan cannot take, bounded include recursion, regex (not XML) for Konsole |
| V6 Cryptography | no | n/a |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Overwriting or reordering a user's bindings | Tampering | Last-wins placement, scan and skip, region replaced in place, compare-before-commit write |
| Path traversal / symlink via `include` or glob in kitty.conf | Tampering, Information disclosure | Read-only scan, resolve relative to the config directory, cap depth and file count, never write to an included file |
| Malformed or hostile Lua | Tampering | Region body is generated, never interpolates user text except the already-validated zsh path via `_lua_string`; structural validate |
| Reading an unbounded or special file (FIFO) | Denial of service | Existing `read_settings` / `read_capped` bounds; the Konsole read uses the same bounded read |
| `sudo` or host mutation | Elevation | None: no path runs `sudo`; container targets only, removed by exact name (AGENTS.md rules) |
| Credential/command injection into the container verb | Tampering | Constants for the herdr config and image, no caller input interpolated, `shellcheck` gate |

`security_enforcement` is absent in `.planning/config.json` (treated as enabled); `bandit` runs as the `make security` gate and flags `xml.etree`, which is why D-09 uses a regex.

## Sources

### Primary (HIGH confidence)
- Repository files read this session: `installer/terminal_keys.py`, `installer/terminal_regions.py`, `installer/terminal_shell.py` (1-312, 560-776), `installer/post_install.py` (370-455), `installer/version_status.py` (775-845), `installer/registry.toml` (kitty, wezterm, alacritty, herdr entries), `installer/resolve.py`, `installer/executors.py`, `installer/model.py`, tests named inline, `.claude/testing.md`, `devtools/docs_only.py`, `tests/test_docs_only.py`, `.claude/skills/tool-onboarding/SKILL.md` (200-225), phase 27/28/29/31 CONTEXT and 29 SPEC.
- Live runs this session (host, scratch HOME, read-only): kitty 0.49.2 `load_config` on the exact map lines; WezTerm 20240203 `show-keys --lua` on scratch configs; luajit and Lua 5.4 stub execution of the Lua region; `uv run pytest tests/test_terminal_keys.py` (33 passed).
- https://raw.githubusercontent.com/kovidgoyal/kitty/v0.49.2/tools/utils/paths.go (config order), read 2026-11-20.
- https://formulae.brew.sh/api/cask/kitty.json (version 0.51.0, `command_wrapper` artifacts, `depends_on.macos >= 12`), fetched 2026-11-20.

### Secondary (MEDIUM confidence)
- https://sw.kovidgoyal.net/kitty/conf/ (include directives, reload keys), fetched 2026-11-20 (page truncated at 100000 characters; the options text was read from the generated 0.49.2 default config instead).
- https://invent.kde.org/frameworks/kxmlgui (`kxmlguiclient.cpp` `localXMLFile`, `kactioncollection.cpp` `writeKXMLGUIConfigFile`/`writeSettings`) and https://invent.kde.org/utilities/konsole `src/session/SessionController.cpp`, master, fetched 2026-11-20; cross-checked against strings in the installed `libKF6XmlGui.so.6` (6.31.0) and `libkonsoleprivate.so.26.08.2`.
- https://raw.githubusercontent.com/wezterm/wezterm at the tag `20240203-110809-5046fc22` (`spawn.rs`, `mux/src/lib.rs`, `localpane.rs`, `termwindow/mod.rs`), read 2026-11-20.

### Tertiary (LOW confidence)
- wezterm.org SpawnTab/SpawnWindow pages (silent on cwd), fetched 2026-11-20; not relied on.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, no new dependency, everything read in the repo.
- Architecture: HIGH for the mechanism and the three gaps (placement, `Writes`, `plan` path), found by reading the code.
- Pitfalls: HIGH for kitty last-wins, WezTerm shifted-key identity and marker substring (all reproduced); MEDIUM for `clear_all_shortcuts`, macOS behaviors and KDE's runtime file (source, not a live capture).

**Research date:** 2026-11-20
**Valid until:** 2026-12-20 (kitty and WezTerm change slowly; the Homebrew cask and the repo's `main` move faster, so re-check the cask artifacts before the registry edit).
