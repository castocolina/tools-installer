---
phase: 29-terminal-defaults-for-the-terminals-in-the-catalog
verified: 2026-11-20T00:00:00Z
status: human_needed
score: 4/4 roadmap truths verified (5/5 requirements satisfied); real-Mac and live-Konsole items outstanding
covered_files:
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-01-PLAN.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-01-SUMMARY.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-PLAN.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-02-SUMMARY.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-PLAN.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-03-SUMMARY.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-04-PLAN.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-04-SUMMARY.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-05-PLAN.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-05-SUMMARY.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-06-PLAN.md
  - .planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-06-SUMMARY.md
  - installer/registry.toml
  - installer/terminal_keys.py
  - installer/terminal_regions.py
  - installer/terminal_shell.py
  - scripts/container-e2e-verify.sh
covered_digest: "v4:sha256:1c758a2520a727119216e1a9a0e198fbbd38327a2d38d9e5f7cd069e6c2b8a7b"
behavior_unverified: 0
gaps: []
human_verification:
  - test: "kitty on a real Mac: Option+Left/Right word moves, Cmd+K clears screen and scrollback, Cmd+T/N/Enter open in the same directory with macos_option_as_alt unset"
    expected: "Bytes 1b62 / 1b66 / 0c reach zsh; new tab and window start in the current directory"
    why_human: "Needs a real Mac (SKILL-05); only the generator and golden bytes are automated"
  - test: "WezTerm on a real Mac: OPT+Left/Right word moves, SUPER+K clear, new tab in the same directory"
    expected: "Same behavior as Linux plus the Option/Cmd rows; user config.keys chords untouched"
    why_human: "Real Mac (SKILL-05); D-07 cwd was proven on Linux only"
  - test: "kitty cask install on macOS lands in ~/Applications (--appdir) and uninstalls cleanly"
    expected: "Nothing written under /Applications"
    why_human: "Real Mac; the registry and test only prove no method names /Applications"
  - test: "Live Konsole 26.x capture in a disposable container: stock Ctrl+Shift+K is Clear Scrollback and Reset, and the sessionui.rc format Konsole writes after the user removes the key"
    expected: "Matches the Shortcut_p.h citation and the parser's expectations (<Action name=clear-history-and-reset shortcut=...>)"
    why_human: "Only the source citation stands in; no live capture was recorded (29-VALIDATION manual-only row)"
provisional_owner_decisions:
  - "28 D-06: a recorded install stays quiet on drift (deleted or edited region after an apply is not re-reported as pending)"
  - "29 D-09: Konsole report-only, never writes; SPEC R4 / ROADMAP SC3 / TERM-04 amended 2026-11-19/20, needs owner confirmation"
  - "Accepted limits in 29-REVIEW-DISPOSITION.md: resolved-config-path change between two applies (lane 3); Konsole report skipped when zsh is unavailable (lane 4); no 'could not verify' note when wezterm is absent (lane 5); herdr slicing blames later chords (WR-01); kitty region at file top pushes a modeline (IN-03); Placement coupling (IN-04); Konsole removal warning attached to the zsh row (IN-01)"
---

# Phase 29: Terminal defaults for the terminals in the catalog - Verification Report

**Phase Goal:** kitty, WezTerm, Alacritty, Konsole and herdr each meet the terminal defaults on every OS they install on, without overriding a binding the user set.
**Verified:** 2026-11-20
**Status:** human_needed (all automated and recorded-live evidence passes; real-Mac and live-Konsole items remain)
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|--------------------|--------|----------|
| 1 | kitty: golden files on both OSes; opt+left/right without `macos_option_as_alt`; clear on Cmd+K / Ctrl+Shift+K naming `scroll_line_up`; cwd tabs/windows; macOS install writes nothing into `/Applications` | VERIFIED | Row `TERMINAL_KEYS["kitty"]` at `installer/terminal_keys.py:275-289`; plan `_kitty_plan` :160-196 emits `map opt+left/right send_text` only on macOS and the clear map; note names `scroll_line_up` at :184-188; cwd maps `_kitty_cwd` :199-216 (`same_directory=Writes`). Goldens `tests/test_terminal_keys.py:122-139` (`_KITTY_LINUX`, `_KITTY_MACOS`) used by tests at :398, :413; regression `test_kitty_never_writes_option_as_alt` :427. No `/Applications` in any kitty method: registry kitty block `installer/registry.toml:3017-3062` (macOS = cask with `~/Applications` appdir, vendor script dropped), asserted by `tests/test_registry.py:2590-2610`. User maps kept: `test_kitty_user_map_is_kept_and_reported` :432. Targeted pytest run (terminal_keys, terminal_shell, herdr_keys, registry, onboarding skill): all pass. |
| 2 | WezTerm Lua region meets defaults on both OSes, extends the user's `config.keys`; shell-region check matches exact marker lines | VERIFIED | `_wezterm_rows` `installer/terminal_keys.py:219-226` (OPT arrows + SUPER K on macOS, CTRL\|SHIFT K on Linux); Lua body `wezterm_keys_body` `installer/terminal_regions.py:52-93` does `config.keys = config.keys or {}` and appends only chords not already taken; placement BEFORE_RETURN :291. Tests: `test_wezterm_user_keys_are_kept_in_order` tests/test_terminal_keys.py:1042; lookalike comment not owned :1060 and tests/test_terminal_shell.py:324; both regions coexist/strip (:369 golden, sibling_regions). Live: `D-07 cwd check: PASS` (29-03-SUMMARY.md:29, SpawnTab and SpawnWindow through perform_action). |
| 3 | Alacritty clear = screen+scrollback, Linux Alt rows unchanged; Konsole stock key reported, nothing written (amended D-09); Konsole zsh sync unchanged | VERIFIED (provisional D-09) | `_KEY_BINDINGS` `installer/terminal_regions.py:507-511`: Alt+Left `\u001bb`, Alt+Right `\u001bf` unchanged, Ctrl+Shift+K now `\u000c` (was ClearHistory). Konsole: `_konsole_clear_state` `installer/terminal_shell.py:87-106` is read-only (`read_capped`), wired at :750-755 to a warning `KONSOLE_CLEAR_REMOVED` (:62) or a note `KONSOLE_CLEAR_STOCK` (:63-66); no write path to `sessionui.rc` (grep shows only reads); sync path `_sync_konsole` untouched. Regex linear (S1 fix). Fixtures: tests/test_terminal_shell.py:1737 and the byte-identical stock/removed tests. |
| 4 | herdr: Alt+Left/Right and clear chord arrive as expected bytes; setting written only if herdr intercepts | VERIFIED (recorded live) | No herdr row in `TERMINAL_KEYS` (rows: alacritty, kitty, wezterm only, :257-311), correct because herdr does not intercept (29 D-10). Container target `scripts/container-e2e-verify.sh` herdr-keys (:2910) + driver `tests/e2e_herdr_keys_driver.py` + `tests/test_container_e2e_herdr_keys.py` (pass). Orchestrator run recorded in 29-05-SUMMARY.md:38-40: `herdr-keys: PASS`, `received=1b62,1b66,1b5b313b3344,1b5b313b3343,0c`. |

**Score:** 4/4 roadmap truths verified; 0 present-but-behavior-unverified.

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| TERM-01 kitty | SATISFIED (macOS runtime deferred to Mac) | Truth 1 |
| TERM-02 WezTerm | SATISFIED | Truth 2 |
| TERM-03 Alacritty | SATISFIED | Truth 3 (Alacritty has no macOS method, 29 D-08) |
| TERM-04 Konsole | SATISFIED as amended (provisional D-09) | Truth 3 |
| TERM-05 herdr | SATISFIED as amended (D-10, live byte proof) | Truth 4 |

No orphaned requirements: REQUIREMENTS.md maps only TERM-01..05 to Phase 29, all claimed by plans.

### Prohibitions

| Prohibition | Status | Evidence |
|-------------|--------|----------|
| No global Option-as-Alt switch | verified (test tier) | Absent from kitty generation; `tests/test_terminal_keys.py:427-428`; skill-text test `tests/test_tool_onboarding_skill.py:134` |
| Never replace/reorder user bindings | verified (test tier) | kitty scan skips taken chords and reports; WezTerm guard appends only free chords, order test :1042; Alacritty conflicts reported (`terminal_regions.py:534-537`) |
| No write to host configs while verifying Konsole/herdr | judgment, verified | Konsole path is read-only; herdr run in a disposable container (PID-named, removed per 29-05-SUMMARY) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase tests | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_container_e2e_herdr_keys.py tests/test_registry.py tests/test_tool_onboarding_skill.py --no-cov -q -n 4` | exit clean, no failures | PASS |

`make validate` and `make test` were not run here (orchestrator runs them). Security: `29-SECURITY.md` `status: verified`, `threats_open: 0`. Review round: all items fixed per `29-REVIEW-FIX.md`; accepted limits listed above.

### Anti-Patterns

No unreferenced TBD/FIXME/XXX checked beyond targeted files; no stub or hollow wiring found in the reviewed paths (row table drives apply, status and strip through `apply_terminal_keys` / `terminal_keys_pending` / `strip_terminal_keys`).

### Human Verification Required

1. kitty on a real Mac: Option+Left/Right, Cmd+K, new tab/window in same directory (bytes 1b62 / 1b66 / 0c). Why human: real Mac, SKILL-05.
2. WezTerm on a real Mac: OPT arrows, SUPER+K, new tab in same directory. Why human: real Mac.
3. kitty cask install into `~/Applications` and its uninstall. Why human: real Mac.
4. Live Konsole 26.x capture of the stock Ctrl+Shift+K and the saved `sessionui.rc` format after removal. Why human: only the source citation stands in.

### Provisional owner decisions (need confirmation, not failures)

28 D-06 (recorded install stays quiet on drift); 29 D-09 (Konsole report-only, SPEC R4 amended 2026-11-20); the accepted limits in 29-REVIEW-DISPOSITION.md.

### Gaps Summary

None. All truths are backed by code and tests or by recorded live container evidence; the phase is `human_needed` only because of the deferred real-Mac and live-Konsole checks.

---

_Verified: 2026-11-20_
_Verifier: Claude (gsd-verifier)_
