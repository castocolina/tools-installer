# Phase 29: Terminal defaults for the terminals in the catalog - Context

**Gathered:** 2026-11-19 (assumptions mode, after 29-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

kitty, WezTerm and Alacritty meet the terminal defaults through the shared keys mechanism (phase 28) without overriding a user binding; Konsole's stock clear is verified and reported, never rewritten; herdr's key pass-through is verified and recorded, with no row.
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**5 requirements are locked.** See `29-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `29-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** kitty and WezTerm rows in the shared mechanism; Alacritty's clear change; the Konsole verify check; herdr's pass-through proof; kitty's macOS install location; golden-file tests and the container checks. *Amended 2026-11-19 (29 D-09, D-10):* Konsole is report-only and herdr has no keys row.
**Out of scope (from SPEC.md):** Alt word navigation on Linux terminals other than Alacritty; Ghostty, iTerm2 and the Herdr app; rewriting Konsole's profile; real-Mac checks; the global Option-as-Alt switch.

</spec_lock>

<decisions>
## Implementation Decisions

### kitty (TERM-01)
- **D-01: A `kitty-keys` owned region (`OwnedRegion("kitty-keys", "#")`) in `kitty.conf`, placed at the top of the file**, next to the existing `kitty` shell region; no include file. kitty resolves a duplicate chord last-wins (verified live in a scratch HOME), and the generic region append goes to the end of the file, which would beat every user `map`. The plan scans `map` lines in `kitty.conf` and in plain `include`/`globinclude` files outside the owned regions (normalizing `kitty_mod`, `cmd`/`super`, `opt`/`alt`/`option` and modifier order) and skips taken chords with `kitty: partial: you already map ...`; `geninclude` and `envinclude` are reported as not followed. Alacritty's refuse-on-import precedent (`installer/terminal_shell.py:544-550`) would refuse most themed kitty users. jev first rung none_of_these 0.77 contradicted the evidence; second opinion top_of_file_plus_scan 0.94. **jev overridden.**
- **D-02: Map lines per OS, with literal bytes.** macOS: `opt+left` and `opt+right` send `\x1bb` and `\x1bf` (`send_text all`), `cmd+k` sends `\x0c`, `cmd+t`/`cmd+enter`/`cmd+n` map to the `*_with_cwd` actions. Linux: `ctrl+shift+k` sends `\x0c` with `--allow-fallback=shifted,ascii` (as kitty declares its default), `kitty_mod+t`/`kitty_mod+enter`/`kitty_mod+n` map to `new_tab_with_cwd`, `new_window_with_cwd`, `new_os_window_with_cwd`; no Alt rows on Linux (owner decision); `macos_option_as_alt` is never written. kitty's own docs say Option/Alt shortcuts take priority without the switch (doc-level; the real Mac stays a UAT line). All test maps parsed through `kitty.config.load_config` in the scratch HOME. The per-OS split matters: `opt+left` on Linux is `alt+left`. jev literal_bytes 0.83 (TypeSafe).
- **D-03: The install note names `scroll_line_up` and says `ctrl+shift+up` still scrolls.** kitty 0.49.2 auto-reloads only when `kitty.conf` existed at start; when the installer creates the file the note says to restart kitty or press `ctrl+shift+f5` (`ctrl+cmd+,` on macOS); the installer sends no signal.
- **D-04: The config path uses a first-existing resolver in kitty's own order** (`KITTY_CONFIG_DIRECTORY`, XDG, `~/.config/kitty`, and on macOS `~/Library/Preferences/kitty`), as Alacritty's resolver does (`terminal_shell.py:486-497`); `_kitty_config_path` (`:156-157`) is XDG only and never mattered because the sync returns at once on macOS (`:914-915`). Creating `~/.config/kitty/kitty.conf` would hide a user's Preferences config. The exact order is confirmed in planning. jev first rung none_of_these 0.91 contradicted the evidence; second opinion first_existing_in_vendor_order 0.97. **jev overridden.**
- **D-05: kitty's macOS install drops the `script` method; the existing `cask` method becomes the macOS route** (`installer/registry.toml:3058-3062`; `--appdir` to `~/Applications`, `installer/executors.py:699-704`). The script wrote `/Applications/kitty.app`, had no `paths` and no removal (audit `.planning/audits/catalog/2026-11-13/kitty.md:23,28`). The `# Verified` comment records that brew links the CLI, not `~/.local/bin` (the 27 D-10 cask gap). jev cask_user_dir 0.97 (TypeSafe).

### WezTerm (TERM-02)
- **D-06: A `wezterm-keys` Lua region inserted before the single `return config`**, like the shell region (the generic append lands after `return` and never runs). It does `config.keys = config.keys or {}` and adds rows only for chords the user's `config.keys` does not hold; the check runs in Lua at load time with normalized mods (`CMD`/`WIN` to `SUPER`, `OPT`/`META` to `ALT`, `CONTROL` to `CTRL`, sorted) and a lower-cased key; `{key="K", mods="CTRL"}` is the same chord as `CTRL|SHIFT k`. Conflicts are reported (`partial: kept yours`) by reading back `wezterm show-keys --lua` when wezterm is present. Live (`wezterm show-keys`): a later duplicate wins, so a plain `table.insert` would override user keys; the Lua guard kept the user's `CMD k` and still added the others. The owned-region check becomes full-line equality, reusing the exact matching of `_replace_owned_region` (`terminal_shell.py:112-123`), replacing the substring test at `:192` (the keys marker contains the shell marker's text). **Own reasoning** (jev runtime_guard_plus_readback low 0.75; first rung low 0.68). Ledger.
- **D-07: Clear is `SendString "\x0c"` on `SUPER k` (macOS) and `CTRL|SHIFT k` (Linux)**, replacing the stock `ClearScrollback(ScrollbackOnly)`; macOS also gets `OPT LeftArrow`/`OPT RightArrow` sending `\x1bb`/`\x1bf`; no Linux Alt rows. `same_directory` is `vendor` for tabs and splits (`SpawnTab(CurrentPaneDomain)`); whether `SpawnWindow` and `SpawnTab` inherit the cwd without OSC 7 is verified in a disposable container (Xvfb plus `wezterm cli spawn`) before the declaration is locked; if they do not, the row switches to `writes` with explicit cwd callbacks. jev live_check_before_lock 0.95 (TypeSafe).

### Alacritty (TERM-03)
- **D-08: The only byte change is the Linux clear row, `action = "ClearHistory"` to `chars = "\u000c"`**, done by removing Alacritty's `clear` override so the phase 28 default applies; the two Alt rows stay byte-identical; the summary text changes; existing installs pick it up through the phase 28 D-06 drift rule (this phase adds no migration; depends on D-06, flagged needs confirmation). **Alacritty has no macOS method** (`cargo_distrobox` debian/fedora/arch, dnf, apt, pacman), so TERM-03's "Cmd+K (macOS)" is `n/a`: no macOS output, requirement reworded to "where installed". jev not_applicable_amend_spec 0.96 (TypeSafe).

### Konsole (TERM-04)
- **D-09: Konsole is report-only; the installer never writes a binding.** The stock clear is the compiled-in action `clear-history-and-reset` ("Clear Scrollback and Reset", default Ctrl+Shift+K; strings found in `libkonsoleprivate.so.26.08.2` on the host; the chord itself is confirmed by the container check). A user change lives as `<Action name="clear-history-and-reset" shortcut="..."/>` in `$XDG_DATA_HOME/kxmlgui5/konsole/sessionui.rc`. Stock means no override entry or one whose `shortcut` contains Ctrl+Shift+K; removed means `shortcut=""` or a value without it, reported as `konsole: partial: you removed Ctrl+Shift+K; kept yours`. Detection is a line or regex read (no XML parser in `installer/`; bandit flags `xml.etree`). Reasons: SKILL-03 (a user's choice is kept), the owner decision "verify and leave alone", and KDE rewrites that file and drops comments, so ownership cannot be proven there. This **amends TERM-04 / SPEC R4 / ROADMAP criterion 3** (the "writes a binding only when the user removed it" clause is dropped); **flagged: needs confirmation**. The format and the stock chord are confirmed by a container capture on Konsole 26.x. jev first rung none_of_these 0.98 contradicted the evidence; second opinion report_only low 0.73. **jev overridden / Own reasoning**, ledger. Container capture: **Own reasoning** (jev container_capture low 0.79; first rung none_of_these 0.77), ledger.

### herdr (TERM-05)
- **D-10: herdr 0.9.5 does not intercept the chords, so no pass-through setting is written and herdr gets no keys row.** Verified live in a disposable `fedora:44` container (`--rm --network=none`) with a pty child recording its raw input as the pane shell: the pane received byte-identical `1b62` (ESC b), `1b66` (ESC f), `1b5b313b3344` (ESC[1;3D), `1b5b313b3343` (ESC[1;3C) and `0c` (Ctrl+L); the CSI-u forms were re-encoded to `1b62`, `1b66` and `0c`; herdr's default keys are all `prefix+...` with prefix `ctrl+b`; `[terminal] new_cwd = "follow"` is the vendor default, so same-directory is `vendor`. A row would need `post_install = ["apply_terminal_tuning"]`, and under 28 D-06 a row that writes nothing would read `≈ apply install tuning` forever, so herdr stays out of the table: the phase 27 skill table records herdr as `vendor` pass-through (verified), and the SPEC boundary "herdr rows" is amended. The byte-level test is a container target in the existing harness (`scripts/container-e2e-verify.sh`, which already installs herdr on Fedora), not a pytest that skips silently in CI; its config needs `onboarding = false` (the first-run popup swallows input), `version_check` and `manifest_check` off for `--network=none`, a short HOME (a long scratch path failed with "server did not become ready"; the socket path limit is the likely cause), and scrubbed `HERDR_*` variables. Probe scripts: `.../scratchpad/p29/scripts/{drive.py,recorder.py,in_container.sh}`. jev container_e2e_target 0.98 (TypeSafe); no-row: **Own reasoning** (jev noop_entry low 0.45; first rung low 0.57). Ledger. macOS herdr is not probed (UAT).

### Coupling with phases 27, 28 and 31
- **D-11: The phase 28 row type needs a `placement` field (end of file, top of file, before `return config`) and a per-row `validate`** (28's is a TOML re-parse; kitty needs a no-op or structural check, Lua a structural check). *(amended 2026-11-19, 29 D-11, in 28-CONTEXT D-03.)* The placement field is ownership-neutral, so phase 31's JSON rows do not conflict.
- **D-12: Phase 27's table cells move** from `planned`/`unverified` to kitty (written), WezTerm clear (written) with cwd `vendor` (unverified until D-07's container check), herdr `vendor` pass-through (verified), Konsole a note row (stock clear), per phase 27 D-13.

### Claude's Discretion
- The exact `partial:` message wording, the install-note text, and the Lua guard's helper names.

### Folded Todos
- `.planning/todos/pending/2026-11-16-terminal-defaults-for-{kitty,wezterm,konsole,herdr}.md` (backlog 999.19's four todos).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/phases/28-shared-terminal-keys-mechanism/28-CONTEXT.md`, `.planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-CONTEXT.md`
- `installer/terminal_shell.py` (kitty/WezTerm/Konsole/herdr sync), `installer/registry.toml` (kitty, wezterm, alacritty, herdr), `installer/executors.py`
- `scripts/container-e2e-verify.sh`, `.planning/audits/catalog/2026-11-13/kitty.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_replace_owned_region` exact marker matching; `_wezterm_content` placement before `return config`; Alacritty's first-existing config resolver; the container e2e harness.

### Established Patterns
- A user's own binding is kept and reported as `<terminal>: partial: you already ...`; install notes name the displaced vendor default.

### Integration Points
- The phase 28 `TERMINAL_KEYS` table; `post_install` actions per registry entry.
</code_context>

<specifics>
## Specific Ideas

Live facts that changed the SPEC (amended in this commit): herdr needs no setting (verified); Konsole removal must not be undone (SKILL-03 and the owner decision); Alacritty has no macOS install route.
</specifics>

<deferred>
## Deferred Ideas

- To confirm in planning: kitty's config-directory order on macOS; whether the Homebrew `kitty` cask declares `binary` stanzas that resolve under `--appdir`; whether `SpawnTab`/`SpawnWindow` inherit the cwd without OSC 7 (D-07 container check); Konsole 26.x default chord and the post-removal `sessionui.rc` content (container capture); whether `$XDG_DATA_HOME/kxmlgui5/` is still the KF6 override directory.

### Reviewed Todos (not folded)
None other matched.
</deferred>
