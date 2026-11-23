# Findings to close (inputs for the plan)

Sources: backlog 999.37 and 999.39 in `.planning/ROADMAP.md`; skill-judge on `.claude/skills/tool-onboarding/SKILL.md` (rubric v5, 125 points) by an Opus subagent (68.8%, D) and three pi referees (70.4% C, 80.0% B, 67.2% D, totals recomputed on 125). Live evidence: the owner's Intel Mac, 2026-11-23.

## A. Installer code (999.37)
1. iTerm2: its native Cmd+K already clears screen and scrollback. Our `cmd+k` row (`OWN_ROWS` in `installer/iterm2_profile.py`, Action 11 Text 0x0c) only adds a "may an escape sequence clear scrollback" permission dialog. Drop the row, its goldens and install notes (`installer/terminal_keys.py` `_iterm2_plan`, the line "iterm2: cmd+k now sends Ctrl+L ..."), keep the two option+left/right rows, and reword NTERM-02 in `.planning/REQUIREMENTS.md`. Keep the existing uninstall/strip path working for a profile that still holds the old row (a user who installed before this change): the removal must still delete the row it wrote.
2. `install_tool` reports INSTALLED for a cask whose `brew install --cask` was a no-op because a stale Caskroom entry exists while the app bundle is gone (seen live: `brew uninstall --zap iterm2` left the entry). The result must be a failure or a repair (for example `brew reinstall --cask`), never INSTALLED for an absent bundle; the post-install must not write a profile or default for an absent app.
3. WezTerm: a user config that binds then disables Super+K (`DisableDefaultAssignment`) leaves our Cmd+K dead. The keys sync must detect a shadowing `DisableDefaultAssignment` for the chord and report `partial: ...` with the reason, never claim success.
4. `installer/apps.py` quarantine docstring is wrong for brew casks: Homebrew 7 leaves `com.apple.quarantine` on cask apps, so Gatekeeper asks once per fresh install; the installer never strips it.

## B. Skill (999.39)
All four judges agree: no `evals/` (D7 is 2 of 15); the iTerm2 (c) cell says `written` for a row item A1 drops; the alacritty (b) cell says `n/a` for a platform gap; the first-run dialog paragraph (step 4) contradicts itself. Also:
- D7: add `evals/evals.json` (onboard a macOS-only cask app; add a terminal, which must add its table row; review an entry with no Linux method, which must yield a 999.x item, not a "macOS-only" label) with verifiable assertions, and `evals/trigger-queries.json` (about 20 queries, 8-10 should-trigger, 8-10 should-not with near-misses: make verify-registry, catalog-audit, "install kitty on my machine").
- D5: SKILL.md is 340 lines and over 8k tokens. Move the closed per-terminal table and the Konsole note to `references/terminal-defaults.md`, read at step 7 when the entry is a terminal or editor; repoint the table tests in `tests/test_tool_onboarding_skill.py`.
- D8: a `gap (backlog 999.x)` status word, used for alacritty (b) and the macOS half of (c), accepted by `test_table_rule_cells_start_with_a_status_word`; flip the iTerm2 (c) cell to `vendor` once A1 lands; restructure the first-run dialog paragraph into three groups (the post-install answers it / the owner answers it / expected and named in the UAT line).
- D4: rewrite the description so it triggers on onboard, support, platform-gap and terminal-default requests that never name the registry; keep it under 1024 characters and keep the "Not for" boundaries.
- Do not change `.planning/phases/27-*/27-SKILLJUDGE-*.md` (the repo test needs exactly the before and after files).

## Not in this task
999.38 (Alacritty dmg method) is a new feature with its own plan. The two pi-referee runs need the owner's Terminal. The schedule tests failing on this Mac (`tests/test_setup.py`, `tests/test_app.py`, "the suite tried to run the host's launchctl") are recorded, not fixed here.
