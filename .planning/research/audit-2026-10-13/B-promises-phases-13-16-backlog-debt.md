# Audit B — promised vs delivered: Phases 13–16, backlog 999.1–999.11, debt harvest

**Auditor:** B (of 7) · **Date:** 2026-10-13 · **HEAD:** `7861ced` (branch `gsd/phase-16-detection-version-and-ownership-must-answer-is-it-on-this-di`) · **Mode:** read-only (this file is the only write)

## Header

**Read:** ROADMAP.md (Overview, Phases list, Progress, Phase Details 13–16, Backlog 999.1–999.11); CONTEXT (decisions + deferred), VERIFICATION (frontmatter, gaps, human_verification), REVIEW / REVIEW-FIX / REVIEW-DISPOSITION, SECURITY, threat-register rows in every PLAN for phases 13, 14, 15, 15.1–15.8, 16; 16-UAT, 15.1-UAT, 15.4-GAP-CLOSURE-VSCODE, 15.6-GAP-CLOSURE; `.planning/todos/{pending,completed}`; STATE.md; RUN-REPORT.md; both 2026-10-11 audits (to avoid re-reporting). Source read at the cited lines in `installer/*.py`, `setup.py`, `installer/registry.toml`, `scripts/`, `.github/workflows/ci.yml`, `pyproject.toml`.

**Ran:** `codegraph sync`; full suite `uv run pytest -q -x` on this Linux host — **green, no failure** (so 999.7's red CI is a cross-platform/determinism problem, not a local one). Headless probes in `/tmp/claude-1000/auditB/` only: `load_settings` on a non-UTF-8 file; `parse_version` on `-1`/`--2`/`-v1.2.3`/`a-1`; `is_installed(rg)` with a fake `$HOME` whose `~/.local/bin` is off `PATH`; registry statistics via `load_tools`.

**Skipped / not verified:** no TUI pilot or tmux session; macOS not run; no live host mutation; nothing that needs `systemctl` mutation (15.7 IN-08 stays unverified); 15.2's streaming liveness and 15.6's terminal behaviour are accepted on the test suite, not re-observed; ponytail F1/F3/F4/F7/F8 trusted as "probe-confirmed" by their auditor (code paths re-read, not re-probed).

**Legend:** D = DELIVERED · P = PARTIAL · R = REGRESSED · N = NEVER-DELIVERED · DF = DEFERRED-AND-FORGOTTEN (deferred in a phase artifact, still present in code, no backlog owner). "Known" = already in 999.x or the two 2026-10-11 audits.

---

## Per-phase table

| Phase | Promises checked (goal clauses + D-xx + deferred items) | D | P | R | N | DF |
|---|---|---|---|---|---|---|
| 13 Live in-TUI execution & link-mode | 16 | 8 | 2 | 0 | 0 | 6 |
| 14 Update path & set_login_shell | 11 | 6 (+D-04 superseded by 15.5) | 0 | 0 | 0 | 4 |
| 15 Catalog accuracy | 17 | 10 | 0 | 0 | 0 | 6 (+WR-07 known) |
| 15.1 Post-run refresh & legend | 9 | 4 | 0 | 0 | 0 | 3 (info) |
| 15.2 Output buffering | 15 | 12 | 0 | 0 | 0 | 3 (info) |
| 15.3 Audience audit | 6 | 2 | 0 | 0 | 0 | 4 (info, tests/comments) |
| 15.4 Ownership visibility | 12 | 6 | 2 | 0 | 0 | 4 |
| 15.5 chsh-absent explanation | 5 | 4 | 0 | 0 | 0 | 1 (doc) |
| 15.6 Terminal default shell | 10 | 4 | 2 (1 known) | 0 | 0 | 4 |
| 15.7 tmp-prune module | 9 | 6 | 0 | 0 | 0 | 3 |
| 15.8 PATH self-dedupe | 6 | 4 | 0 | 0 | 0 | 2 (paperwork) |
| 16 Catalog truth | 31 | 24 | 3 | 0 | 0 | 4 |
| **Total** | **147** | **90** | **9** | **0** | **0** | **44** |

No promise is REGRESSED or NEVER-DELIVERED in the current code. 15.4's "re-derive on entry" was PARTIAL until 9050446 and is now DELIVERED (known; not re-counted). Most DF rows are low severity; the ones that matter are ranked in "NEW gaps" below.

---

## Phase 13 — Live in-TUI install execution & persistent wizard settings

**Delivered:** D-01 push screen; D-02 log stays until a key; D-03 live `RichLog` fed by `StreamingRunner`; D-05.1/D-05.2 (per-tool attribution, `execute_screen.py:845-852`); D-05.3 first-run cancel says why (`wizard_app.py:2772-2780`); link mode persisted (`settings.py:68-71`, atomic) and adjustable from Policies (`m`); `--link-mode` overrides per run without rewriting the store (`settings.py` `resolve_link_mode`).

**Non-delivered**

| Item | Class | Evidence | Impact | Backlog |
|---|---|---|---|---|
| "Install happens inside the app" only on the default route | P (known) | `wizard_app.py:2790-2794` exits when `_execute is None` | Enter quietly exits under make doctor/fix/uninstall/guard | 999.9 F2 / AR-06 |
| "Headless-capable via --all/--categories/--yes" | P | `setup.py:1479-1487` routes `--all`/`--categories` to the console `run_wizard` (`app.py:127-197`), a second install path with no update, repair or explicit re-apply | Phase 14/16 semantics exist only in the TUI (see Phase 14 row) | **NEW** |
| WR-01: an out-of-contract worker exception | DF | `execute_screen.py:581-588` seeds `not_attempted = all`, `error=None`; `try/finally` with no `except` (`:593-672`) → "Not attempted: …" plus a green `"Done."` (`:953`); `setup.py:1275-1278` exits 0 because the summary is empty | A crashed run reads as a clean no-op and exits 0 | **NEW** |
| WR-03: `esc` before start drops the whole staged selection | DF | `action_close` → `dismiss()` (`execute_screen.py:958-961`) → `_install_closed` → `self._staged.clear()` (`wizard_app.py:2797`) | Selection lost, no undo | close to 999.1 (not named there) |
| WR-04: first-run link-mode pick leaves Doctor's fix preview on the old mode | DF | `_first_link_mode_picked` only sets status (`wizard_app.py:2781-2788`), never re-renders Doctor | Preview says `centralized`, Enter applies `single` | **NEW** |
| WR-05: changing link mode does not re-apply enabled policies | DF | `_link_mode_picked` saves the mode and reports `"ok"` (`wizard_app.py:2179-2194`); nothing re-applies the ban/tweaks/PATH block | Aliases stay in a file the new mode never sources: a silent no-op while Policies still shows `[on]` | **NEW** |
| WR-06: a non-UTF-8 `settings.json` crashes startup | DF | `settings.py:53-56` catches `(OSError, JSONDecodeError)` only; probe: `UnicodeDecodeError` raised; called on every route by `setup.py:1281-1283` | A corrupt file blocks every launch with a traceback | **NEW** |
| IN-08: run log unbounded | DF | `RichLog(...)` with no `max_lines` (`execute_screen.py:462-467`) | Memory on huge outputs (low) | none |

WR-02 (catalog not repainted) is now delivered through 15.1 and 9050446.

## Phase 14 — Install/update engine correctness & default-shell action

**Delivered:** D-01, D-02, D-03 in the TUI (`execute_screen.py:675-728`, report `:964-990`); D-05/D-06/D-07 (`post_install.py:54-69`, a closed table on oh-my-zsh only). D-04 (hard block on immutable hosts) was deliberately re-decided by 15.5 (block keyed on whether chsh exists).

| Item | Class | Evidence | Impact | Backlog |
|---|---|---|---|---|
| Cross-AI IN-01: the headless path silently skips outdated/installed selections | DF | `deps.py:109-113` puts every installed tool into `satisfied_by_install` with no warning; `run_wizard` (`app.py:154-160`) has no update branch | `--all --yes` on a machine with outdated tools updates nothing and says nothing. This contradicts the 14 goal and Phase 16 defect (5) | **NEW** (999.1's claim that HEAD "already has Phase 14's not-silently-skipped behaviour" holds for the TUI only) |
| Cross-AI IN-03: `default_enabled_sensitive_actions` is schema-only | DF | parsed and validated `model.py:315,776-783`; no reader | Dead field (rule 5) | add to 999.10 F11 |
| IN-01: an explicit "No" on the sensitive prompt leaves no log line | DF (accepted asymmetry) | `execute_screen.py:834-839` logs only on dismissal | Low | none |
| Exit code ignores update failures | DF | `update_errors` are not in `Summary`; `setup.py:1275-1278` | A failed update in an unattended TUI run exits 0 | **NEW** (with 13 WR-01) |

## Phase 15 — Catalog accuracy (Doctor refresh, version parsing, ownership, tiers)

**Delivered:** D-01/D-02 Doctor refresh + frozen-PATH note; D-03/D-04 name-prefix version fallback (jq); D-05 native-owner adapter, D-06 rpm-ostree probe; D-07..D-10 tier fixes. CR-01/CR-02/WR-05 fixed.

| Item | Class | Evidence | Impact | Backlog |
|---|---|---|---|---|
| WR-02: version prefix accepts an empty name, so a fabricated version parses | DF (in-phase regression, still shipped) | `versions.py:54` `.*[-\s](?=[vV]?\d)`; probe: `parse_version('-1') == (1,0,0,1)`, `'--2'`, `'-v1.2.3'`, `'a-1'` all parse | A usage line with `-1` can become an "installed" version and get ranked. No live trigger today | **NEW** (verifier asked for scheduling; never scheduled) |
| WR-04: native probes not memoized | DF | `install_ownership.py:159` runs `rpm-ostree status --json` per native row, per pass | Can stall a refresh behind `rpm-ostreed` | partly 999.6 F9 |
| WR-06: a verified non-native result is discarded | DF | `ownership.py` `_native_owner` (`:763ff`) | `pi` (host-setup probe) falls to by-elimination | 999.6 |
| WR-07: `_managed_download` execs a missing binary | DF (known) | `install_ownership.py:83-89`; registry `:2721,:2770` | dead + PATH-plantable | 999.10 F11 |
| WR-08/WR-09: substring/source-scrape tests | DF | `tests/test_setup.py` `count("native_probe=")`; `tests/test_ui_common.py` split scraper | tests that cannot fail | AR-11 family |
| IN-05: `_NATIVE_PACKAGE_MANAGER_KINDS` omits `rpm_ostree` | DF | `ownership.py:94` | low | none |

## Phase 15.1 — Post-update refresh & version legend

**Delivered:** D-01 (fully, only after 9050446 re-derives every tier), D-02 per-situation labels (`catalog_tui.py:519-560`), D-03/D-04 always-on legend and stale `~`. All 7 CR/WR fixed. **DF (info, untouched by the fix pass):** IN-02 two rebuilds with flicker; IN-03 a pass discarded by the epoch gate leaves rows at "no version" (same root as AR-04); IN-05 polling tests. IN-04 is moot: `_build_app` always builds the service (`setup.py:890`).

## Phase 15.2 — Output buffering & live progress

**Delivered:** D-01..D-12 (PYTHONUNBUFFERED, opt-in `stdbuf`, 2 s silence indicator); all 14 in-scope review findings fixed. Observation, not a gap: update children run through `run_captured` (`setup.py:1121`), so update output never streams; the `_UPDATE_STARTED` line (`execute_screen.py:711`) keeps the indicator honest. **DF (info):** IN-01/IN-04/IN-05. **Process:** all three `<human-check>` items (live progressive output, the update line, failure report) were closed without a human terminal session (`15.2-VERIFICATION.md:26-31`).

## Phase 15.3 — Audience audit

**Delivered:** D-01/D-02, with the pinned set and the distribution tripwire passing. **DF (info):** IN-01..IN-04 (test and comment cosmetics, `15.3-REVIEW-FIX.md:179-200`). Alacritty was added later outside any phase (999.11).

## Phase 15.4 — Ownership visibility & Uninstall attribution

**Delivered:** D-01 Owner column, D-02/D-02a vocabulary, D-03 (as the terse `removal_label`, a reviewed deviation), D-05 a shared map, D-06 re-derive on entry (after 9050446), the vscode Linux cask (`registry.toml:2195`).

| Item | Class | Evidence | Impact | Backlog |
|---|---|---|---|---|
| Goal "re-derive on entry, both directions" | P→D (known) | fixed 9050446 | — | 999.6 |
| D-04 names "volta"-owned tools; delivered as "accepted-by-design" generic text | P | `Owner` literal has no volta (`ownership.py:77-90`); `15.4-VERIFICATION.md:131-140` (codex, pnpm and pi under `~/.volta` stay generic) | Users with Volta see "managed outside this installer" | **NEW** (fits 999.6 AR-03, multiple observed installs) |
| Script installs: no truthful removal | P (known) | `uninstall.py:57-80` plans download/app only | — | 999.2 / 999.8 |
| IN-01/IN-02 `None` interpolation risk | DF | `update.py:127-130,273`; `removal_hint` typed `str \| None` (`ownership.py:1447`) | low | none |
| IN-03 an unannounced commit inside the epoch window | DF | `15.4-REVIEW-FIX.md:373-380` | self-heals | 999.6 |
| T-15.4-22: a direct `--uninstall` start shows generic attribution | DF (accepted risk) | `15.4-05-PLAN.md:472` | stays generic until a catalog visit | 999.6 |
| **Process:** the one `<human-check>` was "discharged by automated verification" (`15.4-VERIFICATION.md:141-147`) | — | — | That phase's goal was later shown half-built on the real host | 999.7 (not named there) |

## Phase 15.5 — Honest chsh-absent explanation

**Delivered:** D-01..D-04 (`post_install.py:45-65`, keyed on `shutil.which("chsh")`). **DF (doc):** the ROADMAP entry is still the template (`ROADMAP.md:596-603`: "Goal: [Urgent work - to be planned]", "- [ ] TBD") although the 15.5-01 PLAN/SUMMARY exist. Note: `_CHSH_ABSENT_EXPLANATION` blames an "ostree rebase" on any host without chsh, including a non-ostree minimal container (wording, low).

## Phase 15.6 — Terminal-emulator default shell

**Delivered:** kitty / WezTerm / Konsole configured, reversible, never touches the login shell; G-01 (ZDOTDIR) and G-02 closed (`terminal_shell.py:409-412`).

| Item | Class | Evidence | Impact | Backlog |
|---|---|---|---|---|
| D-01 "re-applied on every relevant state change": not on "already" or on an explicit re-select; `$SHELL` stays bash | P (known) | `wizard_app.py:2857-2861,2960`; `terminal_shell.py:152,422` | — | 999.4 |
| CR-01 fix half-applied: the Policies plugin route still hardcodes `$HOME/.oh-my-zsh` | P | `omz.py:450,456` call `ensure_zshrc_template(zshrc_path)` with no `root` → `:420-421` emits `export ZSH="$HOME/.oh-my-zsh"`, also when `.zshrc` exists but does not source OMZ (the docstring claims only the "no .zshrc yet" case) | With a relocated `$ZSH`, enabling plugins writes a wrong path | **NEW** (low) |
| IN-02: Konsole absence is silent | DF | `terminal_shell.py:274` `return False, None` | low | none |
| IN-04: state file written before the writes | DF | `terminal_shell.py:307-311` | low (the recorded prior default stays correct) | none |
| IN-01/IN-03 | DF | `configured`/`skipped` discarded; CRLF mixing | low | none |
| Doc: VERIFICATION frontmatter says 23/23 but the body says 21/23 | DF (doc) | `15.6-VERIFICATION.md:219` | misleading record | none |

## Phase 15.7 — Installable tmp-prune module

**Delivered:** D-01 (Linux systemd timer, on by default, runtime-truthful state), D-02a takeover/coexist, D-03 Doctor warning (15%/70%, a documented re-decision from 30/50), D-04 Bun cache redirect, D-05a disclosure sink, one shared prune core (bash 3.2-safe, no `mapfile` in `scripts/lib/prune-tmp-common.sh`).

| Item | Class | Evidence | Backlog |
|---|---|---|---|
| IN-08: a `--global`-enabled user unit may not stay disabled (unverified) | DF | `15.7-REVIEW-FIX.md:197-206` | none (needs a live host) |
| IN-02 (uninstall-summary half): a redirect-only Linux sweep says "open a new shell" | DF | `wizard_app.py:1581-1584` | none |
| MEDIUM-02 wording; a third XDG resolver copy in `terminal_shell._xdg_config_home` | DF | `15.7-REVIEW-FIX.md:340-370` | none |

## Phase 15.8 — Self-deduping PATH writes

**Delivered:** D-01..D-04 (guard idiom `shellrc.py:129`; no plain PATH export remains in `installer/` and `setup.py`; the remaining script lines are classified one-shots). **DF (paperwork):** `15.8-REVIEW-DISPOSITION.md` still lists CR-01, WR-01..05 and IN-01..03 as `open`, while 16-03/16-04 SUMMARY show them fixed (`16-03-SUMMARY.md:124-143`, `16-04-SUMMARY.md:113-115`). STATE.md "Blockers" still says these 9 findings are open. Accepted: T-15.8-18c/18d/20 (`15.8-SECURITY.md:78-80`). Known: the ubuntu CI failure `test_reserved_word_prefixed_source_forms…[time-…]` (999.7).

## Phase 16 — Catalog truth from the filesystem

**Delivered (24):** D-01/D-02 real owner and `≠ policy`; D-05 update through the real owner with a note (`update.py:285-297`); D-06..D-08; D-09..D-15 skill-pack probes, cache, `+N` hosts (`catalog_tui.py:569-579`), stale `~` on Inst (`:494-512`); D-16 reasons; D-17 already-current/update in the TUI; D-18 broken `!`; D-19 bin_dir locations; D-20..D-24 guard-in-place with per-file confirm and backup.

| Item | Class | Evidence | Impact | Backlog |
|---|---|---|---|---|
| Goal clause "reported installed whether or not the current process can run it" | P | `status.is_installed` adds only an EXPLICIT `bin_dir`/`detect_path` (`status.py:40-52`); 89 `github_release` methods use the implicit default `~/.local/bin`. Probe: `rg` present in `~/.local/bin` but off PATH → `is_installed == False` | From a shell without `~/.local/bin` (split mode unsourced, desktop launcher) installer-owned tools read ○ and are offered for install | **NEW** (fold into 999.6 ToolState) |
| Defect (5) "never Install 0 tools / silent" on the headless route | P | `deps.py:109-113`; `app.py:154-160` | see Phase 14 | **NEW** |
| D-03/D-04: "offer to migrate", with migration "deferred to its own phase" | DF | The UI promises it: "moving it there is not available yet" (`update.py:296`, `catalog_tui.py:923`); no 999.x item owns the migration | A promise with no owner | **NEW** |
| Gap plans 16-17..16-19 changed guard/backup code AFTER the security and Nyquist audits | DF | `16-SECURITY.md` commit 18168ba (14:40) predates 79f859a "guard-specific refusal when the backup slot is taken" (16:17); `16-VALIDATION.md` 48d5e51 (14:55) also predates them; SECURITY register says "plans 16-01..16-16" | T-16-21/22/24 (high) evidence lines are no longer re-verified | **NEW** (999.7 names only 9050446) |
| UAT 2-4 deferred; 9050446 not code-reviewed | DF (known) | `16-UAT.md` results skipped | — | 999.7 |
| Pending todo "dangling pnpm shim in Doctor": catalog `!` delivered (D-18), the Doctor finding never built | P | `doctor.py` has only bin-dir "broken"; the todo is still in `todos/pending`, while STATE.md says "Pending Todos: None yet" | Doctor never names the shim | **NEW** (bookkeeping) |
| Doc: ROADMAP lists 16 plans, the directory has 19 | DF (doc) | `ROADMAP.md:663-694` | — | none |

---

## Backlog accuracy

| Item | Verdict | Notes (with evidence) |
|---|---|---|
| 999.1 | **Accurate, incomplete** | `_staged` is cleared only in `_install_closed` (`wizard_app.py:2797`); 0 `PlanDisposition` hits; F4 path re-read (`wizard_app.py:1406-1478`, `applied` blocks only the same visit). Missing: (1) "HEAD already has Phase 14's explicit not-silently-skipped behaviour" is TUI-only, because the headless `--all`/`--categories` path still drops installed or outdated selections silently (`deps.py:111`); (2) Phase 13 WR-03: `esc` before start also clears the selection. |
| 999.2 | **Accurate** | `plan_uninstall` covers DOWNLOAD/APP kinds only (`uninstall.py:57-80`); 0 `ReceiptStore`; no "receipt" in 16-CONTEXT/RESEARCH. |
| 999.3 | **Mis-stated (overstated)** | "a per-platform artifact that is neither a `github_release` asset pattern nor a script has no method kind": `tarball` (per-os/arch URL + `member`/`strip`) and `app` (macOS zip `.app`, per arch) already exist and are used (`model.py:24-40`; vscode `registry.toml:2145-2175`). The real gap is narrower: no `.dmg`, no AppImage, no whole-bundle extraction into an install root (kitty.app style; `tarball` extracts one member), no checksum on those kinds. Start the inventory there. |
| 999.4 | **Accurate** | No `SHELL` env in `terminal_shell.py:152,422`; sync gated on `_install_state_changed` (`wizard_app.py:2857,2960`). |
| 999.5 | **Accurate** | Skill edited again after 41d642c (27d8bd6) and still not skill-judged. |
| 999.6 | **Accurate, minor drift** | `_own_script_install` `ownership.py:1436`; AR-04 now `version_status.py:749` (was 751). Should also absorb: implicit default-bin-dir presence (above), RUN-REPORT W1 (uv shim: `attribute_path` resolves the symlink out of `~/.local/bin`, `ownership.py:466-482`), Volta-owned tools (15.4 D-04). |
| 999.7 | **Accurate, incomplete** | CI triggers and test names verified (`ci.yml`, `tests/test_shellrc.py:2658`, `tests/test_setup.py:2764`, `tests/test_version_status.py:1212`); full suite green on this Linux host. Missing: 16-SECURITY and 16-VALIDATION predate gap plans 16-17..19; the human checks of 15.1/15.2/15.3/15.4 were discharged by automation or a subagent, not a person (`15.1-UAT.md:90`, `15.2-VERIFICATION.md:26-31`, `15.3-VERIFICATION.md:21-25`, `15.4-VERIFICATION.md:141-147`). |
| 999.8 | **Mostly accurate, numbers off** | "76 of 90 have a non-manager method": 76 only if `sdkman` counts as non-manager, yet the item's own level 1 calls sdkman a manager (71 under its definitions). "3 of 90 set `uninstall`" is true for the TOML key, but `Tool.uninstall` is populated for 10 (7 skill packs via `skill_lifecycle`) and read by nobody. Kind counts (github_release 89, script 16, app 7, tarball 5, sdkman 5, skill_pack 7, host_setup 1) and the 13 multi-kind tools match. |
| 999.9 | **Accurate** | F5 writers `app.py:447`, `guards.py:388-564`, `tweaks.py:254-308`; F2 `wizard_app.py:2790-2794`; F17 `wizard_app.py:292`. |
| 999.10 | **Accurate** | Agent modules 464 lines + the `policy.py:181-260` block ≈ 565; pyright `include = ["installer","tests"]` and coverage `source = ["installer"]` exclude `setup.py`. Add `default_enabled_sensitive_actions` (dead field). |
| 999.11 | **Accurate** | 0 herdr rows; 50 `github_release` methods without `checksum`; no TOML writer in deps; `terminal_shell.py` has no Alacritty. |

---

## Debt ledger

### `shortcut:` markers (ponytail-debt scan)

| Marker | Ceiling | Upgrade trigger | Owner (blame) | Still valid? | Proposed owner |
|---|---|---|---|---|---|
| `installer/ownership.py:538` | stats `opt/<formula>/bin/<cmd>` for every formula | "if this shows up in a profile" | 3d99721 (2026-10-10) | yes (= 16 IN-05 skipped) | 999.6 F9 |
| `installer/rcclean.py:296` | a quoted zsh array element with a space mis-splits | none stated (diagnostic only; 16-08 writer refuses arrays: holds) | 8b7bc7d | yes, **no-trigger** | none needed |
| `installer/rcclean.py:447` | first heredoc per line only; `<<5`, `<< -EOF`, quoted-space delimiters missed | "if a real rc needs either" | 2c92291 | yes (= NR-03 skipped) | none |
| `tests/test_rcclean.py:955` | quote-blind colon split in `_expanded_segments` | "when split is quote-aware" | a3e2cec | yes | none |

4 markers, 1 with no trigger. `TODO`/`FIXME`/`XXX`/`HACK` in `installer/`, `setup.py`, `scripts/`, `tests/`, `install.sh`: **0**.

### Planning-artifact debt

| Item | Where | Kind | Still valid? | Proposed owner |
|---|---|---|---|---|
| 13 WR-01, WR-03..WR-06, IN-08 | `13-VALIDATION.md:153-166`, code above | review deferred | yes (all re-checked) | **new item** (WR-05 first) |
| 14 cross-AI IN-01 (headless no update) | `14-VERIFICATION.md:130-137` | review "recorded for visibility" | yes | 999.1 or new |
| 14 cross-AI IN-03 dead field | `14-REVIEW-cross-ai.md:139` | review | yes | 999.10 |
| 14 IN-01 silent explicit "No" | `14-VERIFICATION.md:125` | accepted asymmetry | yes | none |
| 15 WR-02 / WR-04 / WR-06 / WR-08 / WR-09 / IN-05 | `15-VERIFICATION.md:31-62` | verifier warnings, "deferred by fix pass" | yes (WR-02 probe-confirmed) | WR-02 new; WR-04/06 999.6; WR-08/09 999.10 |
| 15.1 IN-02/IN-03/IN-05 | `15.1-REVIEW-FIX.md:22` | info out of scope | yes | 999.6 (IN-03) |
| 15.2 IN-01/IN-04/IN-05 | `15.2-REVIEW-FIX.md:23` | info | yes | none |
| 15.3 IN-01..IN-04 | `15.3-REVIEW-FIX.md:179-200` | info | yes | none |
| 15.4 IN-01/IN-02/IN-03; T-15.4-22 | `15.4-REVIEW-FIX.md:373-380`; `15.4-05-PLAN.md:472` | info / accepted threat | yes | 999.6 |
| 15.4 Volta limitation | `15.4-VERIFICATION.md:131-140` | accepted-by-design | yes | 999.6 |
| 15.6 IN-01..IN-04 | `15.6-REVIEW-FIX.md:254-270` | info | yes | none |
| 15.7 IN-08, IN-02 half, MEDIUM-02 | `15.7-REVIEW-FIX.md:185-206,356-370` | deferred | yes | none (IN-08 needs a live host) |
| 15.8 REVIEW-DISPOSITION 9 × `open` | `15.8-REVIEW-DISPOSITION.md:8-59` | stale disposition | **no** (fixed in 16-03/16-04) | update the file to `fixed` |
| 15.8 T-15.8-18c/18d/20 | `15.8-SECURITY.md:78-80` | accepted threat | yes, reasoned | none |
| 16 IN-03, IN-04, IN-05, IN-07, IN-08, IN-09, IN-13, NR-03 | `16-REVIEW-DISPOSITION.md` | skipped/accepted | yes | IN-04 → 999.2; IN-05 → 999.6; others none |
| 16 AR-16-01..08 accepted risks | `16-SECURITY.md:85-94` | accepted threat | yes; re-check AR/T-16-21..24 after 16-17 | 999.7 |
| 16 residual IN-01 heredoc guardable | `16-SECURITY.md:98` | residual note | **no** (fixed 2c92291) | none |
| 13 T-13-04 (token echo in log), T-13-05 (`--yes` no confirm), T-13-24 (ctrl+c orphans a child) | `13-04-PLAN.md:484-490` | accepted threat | yes, disclosed in the key hint | none |
| 15.2 T-15.2-01 (PATH-resolved `stdbuf`), T-15.2-09 (`LD_PRELOAD` inheritance) | `15.2-01-PLAN.md:450-454` | accepted threat | yes | none |
| 15 T-15-20 (probe cost) | `15-05-PLAN.md:505` | accepted, "follow-up recorded" | yes, follow-up never filed | 999.6 F9 |
| `T-*-SC` "no package installed" rows (≈40) | every PLAN | boilerplate accept | n/a | none |
| 16 UAT 2-4 | `16-UAT.md` | human verification deferred | yes | 999.7 |
| Human checks discharged by automation (15.1, 15.2 ×3, 15.3, 15.4) | see 999.7 row | verification shortcut | yes (never seen by a person) | 999.7 |
| 16 D-04 migration "own phase" | `16-CONTEXT.md` D-04; UI text | deferred decision | yes | **new item** |
| Pending todo dangling shim (Doctor half) | `todos/pending/2026-09-16-…md` | todo | partly (catalog half done) | close or narrow it |
| RUN-REPORT W1 uv shim ownership | `RUN-REPORT.md:376-382` | accepted limitation | yes (`ownership.py:466-482`) | 999.6 |
| RUN-REPORT REQ-manager-drift-alerting | `RUN-REPORT.md:143-152` | deferred with a trigger | yes; trigger not met (no tool has node/uv-tool AND brew) | none |
| RUN-REPORT "review ran at standard depth though config says deep"; "opencode --auto sandbox prompt-only"; stale `cross_ai_command` | `RUN-REPORT.md:440-454` | open questions | unanswered | user |
| STATE.md stale: "Pending Todos: None yet", 15.8 blocker, the "six companion PRDs" blocker, "Last session 2026-10-09 … Phase 16 complete" | `STATE.md:199-240` | bookkeeping | stale | /gsd-health |
| ROADMAP: the Phases list and Progress table stop at 15; 15.5 entry is a template; 16 lists 16/19 plans; no verification overrides anywhere (`overrides_applied: 0` ×12) | `ROADMAP.md:60-75,329-347,596-603,663-694` | doc drift | yes | /gsd-health |

---

## NEW gaps not in backlog (ranked)

1. **Changing link mode silently strands enabled policies** (13 WR-05). `wizard_app.py:2179-2194` saves the mode, reports success and leaves the pip/npm ban, the tweaks and the PATH block in `~/.myshellrc`, which split mode never sources. Policies still shows `[on]`. This is the exact "silent no-op" the `policy.py` docstrings name as the hazard. Fix: re-apply active policies via `run_live` on mode change, or at least warn.
2. **The headless install path is a second engine without Phase 14/16 semantics.** `--all`/`--categories` → `run_wizard` (`app.py:127-197`) → `deps.py:111` drops every installed tool, outdated included, with no notice; it has no update, repair or re-apply. The 14 goal and the 16 defect (5) hold only in the TUI. Fold into 999.1's plan model, or route headless runs through the same execute core.
3. **A crashed or failed run reports success** (13 WR-01 + the exit code). An out-of-contract worker exception ends in a green "Done." with no error (`execute_screen.py:581-588,656-672,953`), and `setup.py:1275-1278` exits 0. Failed updates are not in `Summary` either, so they also exit 0.
4. **Presence ignores the implicit default bin dir** (Phase 16 goal clause). `status.py:40-52` adds only an explicit `bin_dir`. Probe: `rg` in `~/.local/bin` off PATH → not installed. Installer-owned `github_release` tools read ○ from any shell that lacks the PATH wiring. Belongs in 999.6's ToolState.
5. **The 16 D-04 migration has no owner while the UI promises it** ("moving it there is not available yet", `update.py:296`, `catalog_tui.py:923`). File a backlog item, or reword the UI.
6. **Version parser fabricates versions** (15 WR-02, probe-confirmed): `versions.py:54` makes `-1`, `--2`, `-v1.2.3` and `a-1` parse. The verifier gave a one-line fix; it was never scheduled.
7. **A non-UTF-8 `settings.json` crashes every launch** (13 WR-06, probe-confirmed): `settings.py:53-56`; add `UnicodeDecodeError` and an explicit encoding.
8. **Gap plans 16-17..16-19 were not re-audited** by secure-phase or validate-phase, although 16-17 changed the backup/guard refusal path behind high-severity T-16-21/22/24.
9. **First-run link-mode pick leaves Doctor's preview wrong** (13 WR-04, `wizard_app.py:2781-2788`), and **`esc` before start wipes the staged selection** (13 WR-03, `wizard_app.py:2797`).
10. **Volta-installed tools are never attributed** (15.4 D-04 promised it; accepted as a limitation). `ownership.py:77-90`.
11. **Low:** the 15.6 CR-01 fix is half-applied in `omz.write_plugins` (`omz.py:420-421,450,456`); 15 IN-05; 14 IN-01/IN-03; 15.4 IN-01/IN-02; 15.6 IN-02/IN-04; 15.7 IN-02 half and IN-08; unbounded `RichLog`; chsh text blames ostree on any host.
12. **Bookkeeping:** the 15.8 disposition is stale (9 rows "open" but fixed); STATE.md stale (pending todos, blockers, session); ROADMAP Phases/Progress tables stop at 15, 15.5 is a template, 16 lists 16/19 plans; 15.6 VERIFICATION says 23/23 in the frontmatter and 21/23 in the body; the dangling-shim todo is half done but still pending.
