---
phase: 03-install-uninstall-tweak-lifecycle-hardening
verified: 2026-09-05T10:54:04Z
gap_closed: 2026-09-05
status: passed
score: 27/27 must-haves verified
behavior_unverified: 0
overrides_applied: 0
head_commit: 66dcad4
branch: gsd/phase-03-install-uninstall-tweak-lifecycle-hardening
gates:
  make_validate: pass   # ruff, ruff format, pyright (0 errors), bandit, vulture, shellcheck — re-run by verifier
  make_test: pass       # 852 passed, 99.83% coverage (floor 90%) — re-run by verifier, twice
requirements:
  REQ-install-failure-propagation: satisfied
  REQ-oh-my-zsh-plugin-config: satisfied
  REQ-uninstall-sweep-tweak-executables: satisfied
gaps: []  # The one gap below was closed same-day; see gap_closure_evidence.
gap_closure_evidence:
  - truth: "The Policies detail panel discloses the partial-state / ownership reading BEFORE the user acts on it — stated in `_policy_detail`'s `omz-plugins` copy, not left for the user to discover (03-02 must-have truth #7, 03-REVIEWS.md cycle-1 MEDIUM)."
    status: closed
    original_reason: >-
      The disclosure text existed in source but was CLIPPED OFF-SCREEN at every
      normal terminal width. `PoliciesScreen #policy-detail` was a plain `Static`
      with `height: 7` and `overflow_y: hidden` (not scrollable). The omz-plugins
      detail needed 10 rendered rows at 80 cols, 8 at 100 and 120 cols. The three
      lost rows at 80 cols were exactly the ownership disclosure the cycle-1
      MEDIUM finding demanded. This was a re-occurrence of the defect 03-02's own
      tmux check already caught once (`height: 5` -> `height: 7`, commit 1adcfe4):
      commit 3d1ee1f (the CR-01 record-ownership fix) replaced the fourth
      disclosure line with a materially longer one, and no tmux check had run
      since. The guarding e2e test asserted against `app.screen.detail_text` (the
      model string), never the rendered output, so it passed while the user
      could not read the text.
    fix_commit: "66dcad4 — fix(wizard): give the Policies detail panel enough height at 80 columns"
    fix_summary: >-
      `#policy-detail`'s CSS height raised 7 -> 11 with `overflow-y: auto` added
      as a margin against future copy growth. A new e2e test
      (`test_every_policy_detail_fits_the_panel_at_80_columns`) asserts, for
      every policy row at a real 80-column app.run_test size, that Textual's own
      `Static.get_content_height` (the true wrapped-content height at that
      width, independent of the CSS box) fits within the panel's allocated
      `size.height`. Mutation-verified: reverting the height to 7 makes this
      test fail with the exact numbers this gap reported (`tweak:countdown`
      needs 8 rows, only 7 allocated) — the model-string-only test that missed
      this the first time could not have caught it; this one does.
    tier2_reverification: "T2-1 and T2-2 below, performed after the fix landed, both confirm the fix in a real terminal — not just the test."
tier2_tmux_required:   # Per the orchestrator's directive + ONESHOT Rule 14 Tier 2: performed by the orchestrator, not deferred to a human. All checks PASSED.
  - id: T2-1
    behavior: "Policies detail panel shows the full Oh-My-Zsh disclosure after the height/scroll fix lands."
    keys: "6, then Down onto the `Oh-My-Zsh plugins` row (navigation-only; never space)"
    expect: "capture-pane contains BOTH `Disabling removes` AND `shows OFF and is left alone` at the real terminal's actual width."
    result: "PASSED — real tmux session, 80x30. capture-pane after `6` + 4x Down shows both phrases in full: \"Disabling removes only the names this enable actually added — a plugin you put in that array yourself is never touched.\" and \"Reads ON only once this installer has enabled it, so a plugins=(git docker) you wrote by hand shows OFF and is left alone.\" Gap closed."
  - id: T2-2
    behavior: "Policies `Countdown helper` detail is not clipped."
    keys: "6, then Down/Up onto `Countdown helper` (navigation-only)"
    expect: "capture-pane contains the trailing word `toolchain.` (currently the 1 clipped row at 80 cols)."
    result: "PASSED — same tmux session, navigated Up x2 from Oh-My-Zsh plugins to Countdown helper. capture-pane shows the full line \"Requires uv at runtime so the Python helper runs through the managed toolchain.\" — not clipped."
  - id: T2-3
    behavior: "Uninstall `shell tweaks` env row renders its policy-id list un-truncated."
    keys: "5 (navigation-only; never `a` and never `enter`)"
    expect: "capture-pane contains `blocks + helpers (` followed by the machine's real active ids, un-elided; agreement-check the cell against `active_tweak_ids` on the real machine."
    result: "PASSED — real tmux at 160x30 (wide enough for the full cell). capture-pane row: \"shell tweaks       env       shell config     blocks + helpers (tweak:docker, tweak:countdown, tweak:claude-skip)\". Agreement-checked against a live `active_tweak_ids(applicable_bundles(detect()), rc_path=~/.myshellrc, bin_dir=~/.local/bin, zshrc_path=~/.zshrc)` call on the same machine: returned the identical tuple `('tweak:docker', 'tweak:countdown', 'tweak:claude-skip')`. Navigation-only — no `a`, no `enter`, nothing on this dev machine was modified."
  - id: T2-4
    behavior: "Doctor view renders the CURRENT ban/PATH state on entry, not a build-time snapshot."
    keys: "4 (or ctrl+p -> doctor), navigation-only"
    expect: "capture-pane's PATH Doctor body matches the machine's real `guard_status` output at the moment of entry."
    result: "PASSED — capture-pane shows \"pip/npm ban active — npm, pip, pip3 are shimmed to their replacements.\" Agreement-checked against a live `guard_status(~/.local/bin)` call: returned `{'npm': True, 'pip': True, 'pip3': True}` — exact match. Confirms `DoctorScreen.enter_view` genuinely re-derives state on navigation, not a build-time snapshot (WR-01's underlying mechanism, applied correctly here)."
tier3_container_required:
  - id: T3-1
    behavior: "Post-sweep applied summary (`_applied_summary` -> `multiline_summary`) renders every reload-guidance line without truncation."
    why_not_tmux: "Requires pressing the key that commits an uninstall, which ONESHOT Rule 5 forbids on the real machine. Route to the disposable-container tier or to a width-pinned headless render assertion instead."
known_limitations:  # Accepted, carried-forward Warning-level residuals — see Known Limitations section
  - id: WR-01
    source: "03-REVIEW.md iteration 3 (final, cap reached), Warnings section"
    summary: "PoliciesScreen has no `enter_view`; rows render stale ON after an in-app uninstall."
    disposition: accepted-carried-forward
  - id: WR-02
    source: "03-REVIEW.md iteration 3, Warnings section"
    summary: "`perform_uninstall` reads `sweep_tweaks` AFTER its own destructive steps; the preview/effect invariant holds by argument there, not by construction as it now does in `run_uninstall`."
    disposition: accepted-carried-forward
  - id: WR-03
    source: "03-REVIEW.md iteration 3, Warnings section"
    summary: "Mutation gap: freezing `setup.py`'s `tweak_ids` at build time passes the whole suite."
    disposition: accepted-carried-forward
human_verification: []   # Per the orchestrator's directive, TUI/interaction items route to tier2_tmux_required above, not to a human.
---

# Phase 3: Install/Uninstall & Tweak Lifecycle Hardening — Verification Report

**Phase Goal:** A run that hits a failed prerequisite, or a full uninstall, is honest about what happened and leaves nothing stray behind — and Oh-My-Zsh's bundled plugins turn on the same way every other shell tweak does.

**Verified:** 2026-09-05T10:54:04Z · **HEAD:** `8584980` · **Status:** `gaps_found` · **Re-verification:** No — initial verification.

**Bottom line:** All three requirements are genuinely met, proven by driving the real production callables and the real Textual screens (not by reading SUMMARY.md). One plan-level must-have — the pre-action ownership disclosure in the Policies detail panel — is FAILED for a reason not previously known: the copy exists in source but is clipped off-screen at every normal terminal width. This is a new finding, not one of the already-triaged WR-01/02/03 residuals.

---

## Gates — independently re-run by the verifier on this exact tree

| Gate | Command | Result |
|------|---------|--------|
| Lint / format / types / security / dead code / shell | `make validate` | **PASS** — ruff clean, 87 files formatted, pyright **0 errors 0 warnings**, bandit clean, vulture clean, shellcheck clean |
| Test suite + coverage floor | `make test` | **PASS** — **852 passed**, coverage **99.83%** (floor 90%) |
| Test suite re-run after verifier's mutation experiment | `make test` | **PASS** — 852 passed, 99.83%; tracked tree confirmed clean (`git status --porcelain` empty for tracked files) |

Not accepted from any prior report — both commands were executed here.

---

## Goal Achievement

### ROADMAP Success Criteria (the contract)

| # | Success Criterion | Status | Evidence |
|---|---|---|---|
| SC1 | A tool whose dependency failed earlier in the same run is reported skipped with a clear "dependency failed" reason — never silently attempted, never silently dropped from the summary | ✓ VERIFIED | Drove `run_installs` with A(fail) ← B ← C plus independent D. `attempted == ['A','D']` — B and C were **never handed to the install callable**. Outcomes: `B dependency-failed blocked_by=('A',)`, `C dependency-failed blocked_by=('B',)`. `render_summary` printed `Dependency failed: 2` **and** `dependency failed: B, C`; `render_skipped` printed `⚠ B skipped — dependency failed: A` / `⚠ C skipped — dependency failed: B`. |
| SC2 | A full uninstall removes every tweak-managed executable (e.g. `tools-installer-wait-time`), not only `Tool`-shaped artifacts | ✓ VERIFIED | Enabled the countdown bundle + omz policy on a real sandbox FS, then ran `sweep_tweaks`: bin dir went `['my-script','tools-installer-wait-time','tools-installer-wait-time.bak']` → `['my-script','tools-installer-wait-time.bak']`; rc block gone; `.zshrc` reverted. Reproduced through **both** production entry points (`run_uninstall`, `perform_uninstall`). |
| SC3 | Toggling the Oh-My-Zsh plugins tweak in Policies enables the bundled `git`/`docker` plugins by editing `plugins=(...)` in `.zshrc`, with no separate catalog entry | ✓ VERIFIED | Drove the **real `PoliciesScreen`** under a Textual pilot: row `Oh-My-Zsh plugins` present; `space` on it turned `plugins=(git zsh-users)` → `plugins=(git zsh-users docker)`; second `space` reverted to `plugins=(git zsh-users)`. `load_tools(registry.toml)` → 65 tools, **no** `oh-my-zsh`/`omz-plugins` id, no tool requiring `oh-my-zsh`; `git diff 05ad2e5^..HEAD -- installer/registry.toml` is **empty**. |

### Plan 03-01 must-have truths — REQ-install-failure-propagation

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Dependent never handed to the install callable; outcome is `DEPENDENCY_FAILED` carrying `blocked_by` | ✓ VERIFIED | `attempted == ['A','D']`; `blocked_by=('A',)` / `('B',)` observed on the outcomes. |
| 2 | Skipped tool still in the report: `Summary.dependency_failed` + `render_summary` prints count and id | ✓ VERIFIED | `summary.dependency_failed == ('B','C')`; console line carries both `Dependency failed: 2` and `dependency failed: B, C`. |
| 3 | `render_skipped` prints one line per skipped tool naming the exact failed dep ids, and `run_wizard` calls it on the real post-TUI path | ✓ VERIFIED | Output reproduced above; `installer/app.py:152` calls `render_skipped(outcomes, console)` inside `run_wizard`, between `render_summary` and `render_verification`. |
| 4 | Propagation is transitive (C→B→A) — the skip status itself counts as unresolved | ✓ VERIFIED | C reported `dependency-failed blocked_by=('B',)` although B itself was only skipped. `_UNRESOLVED` includes `DEPENDENCY_FAILED` by design (`session.py:22-31`). |
| 5 | Every non-success blocks (`no-method`, `checksum-mismatch`, `failed`); `installed`/`already-installed` never do | ✓ VERIFIED | Parameterised live: all three unresolved statuses → `B dependency-failed ('A',)`; both success statuses → B attempted and installed/already-installed. |
| 6 | A tool with no failed prerequisite is untouched; `summarize([])` returns an all-empty `Summary` | ✓ VERIFIED | D installed normally. `summarize([]) == Summary((),(),(),(),(),())`. |
| 7 | `installer/deps.py` is byte-identical after this plan | ✓ VERIFIED | `git diff 05ad2e5^..HEAD -- installer/deps.py` is empty. |
| 8 | Both boundary docstrings say the boundary out loud | ✓ VERIFIED | `run_installs.__doc__` contains `deps-first topological order` and `attempted rather than skipped`; `render_verification.__doc__` contains `method_kind=None` and `no verification step ran`. |

### Plan 03-02 must-have truths — REQ-oh-my-zsh-plugin-config

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Toggle ON edits the existing line, adds only absent names, preserves every other plugin and every other line | ✓ VERIFIED | `'# comment\n  plugins=(git zsh-autosuggestions)  # my plugins\nexport X=1\n'` → added `('docker',)`, indentation and trailing comment preserved verbatim. Container run against the **real** Oh-My-Zsh installer: `plugins=(git)` → `plugins=(git docker)`, `non-plugins lines identical: True`. |
| 2 | Toggle OFF removes only `git`/`docker`, leaves the rest untouched | ✓ VERIFIED | Disable returned `('docker',)` and left `('git','zsh-autosuggestions')`. Hand-authored `git` was **not** stripped — the record-ownership model. |
| 3 | No catalog entry; `registry.toml` not modified | ✓ VERIFIED | Empty `git diff` for registry.toml over the whole phase range; `load_tools` shows no zsh/omz id. |
| 4 | Targeted in-place line edit, NOT `apply_block`/`strip_block`; no marker block ever written into `.zshrc` | ✓ VERIFIED | `omz.py` imports `apply_block`/`strip_block` **only** for the ownership record in `~/.myshellrc`. Every `.zshrc` mutation goes through `_rewrite` + `_atomic_write`. Post-enable `.zshrc` in the container contained no `tools-installer` marker. |
| 5 | Multi-line / missing array raises `OmzPluginsError` on enable; the toggle reports an error and stays OFF | ✓ VERIFIED | Real screen, `.zshrc` = `# no plugins line here`: `space` left `active_state == {'omz-plugins': False}`, status line read `Policy change failed: No single-line plugins=(...) array to edit…`, file untouched. |
| 6 | `requires=('oh-my-zsh',)` + `missing_requires` drive the existing unmet-requires UX; no new UX pattern | ✓ VERIFIED | `present=False` → row `Requires` cell reads `missing: oh-my-zsh`; `space` left `.zshrc` unchanged with status `Install required tool(s) first: oh-my-zsh. Open Catalog, install them, then retry.` `omz_present` verified across all three branches (absent / `~/.oh-my-zsh` dir / `$ZSH`). |
| 7 | **Detail panel discloses the partial-state / ownership reading BEFORE the user acts on it** | ✗ **FAILED** | Text is present in `_policy_detail` but **clipped off-screen**: `#policy-detail` is a non-scrolling `Static` (`overflow_y: hidden`) with `height: 7`, while the omz-plugins copy needs **10 rows at 80 cols**, 8 at 100 and 120. The three lost rows at 80 cols are the ownership disclosure itself. See Gaps. |
| 8 | `omz.py` module docstring names both structural limits (nested parens, newline-spanning) | ✓ VERIFIED | Docstring contains `nested parentheses` and `any array whose parentheses span a newline`. |
| 9 | Every rc-touching test runs against a sandboxed HOME; the real `~/.zshrc` is never read for a decision or written | ✓ VERIFIED | All 13 rc-touching test modules use `monkeypatch.setenv("HOME", …)`/`tmp_path`; `tests/conftest.py` adds an autouse `no_zdotdir` fixture; `test_real_home_rc_files_are_untouched` asserts every path resolves under `tmp_path`. |
| 10 | Proved against a REAL Oh-My-Zsh install in a disposable container | ✓ VERIFIED | **Re-executed by the verifier**, not taken from SUMMARY. `docker run --rm alpine:latest` + the official unattended installer: upstream wrote `73:plugins=(git)`; `write_plugins` added exactly `('docker',)`; a real interactive `zsh -i` resolved `gst='git status'` and reported `docker plugin dir loaded: 1`; `remove_plugins` returned `('docker',)` leaving `('git',)` and cleared the record. |

### Plan 03-03 must-have truths — REQ-uninstall-sweep-tweak-executables

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Full uninstall removes every tweak-managed executable, `tools-installer-wait-time` included | ✓ VERIFIED | Both entry points: `perform_uninstall(remove_tweaks=True)` → `SweepResult(swept=('tweak:countdown','omz-plugins'), failed=())`, bin dir emptied of the helper; `run_uninstall(confirm=True)` same. |
| 2 | Teardown is symmetric — it runs the SAME `Policy.remove` closures Policies uses, so the rc block goes with the executable | ✓ VERIFIED | `sweep_policies` writes no removal logic; it calls `policy.remove()` per policy. Post-sweep: `tweak_present(...) == False` **and** helper gone together. |
| 3 | A tweak whose rc block was hand-removed but whose helper is still on disk is STILL swept | ✓ VERIFIED | Block cleared by hand → `block present: False, exec present: True` → `active_tweak_ids == ('tweak:countdown',)` → sweep removed the helper. |
| 4 | The Oh-My-Zsh plugins edit is part of the same teardown, via `omz_plugins_policy(...).remove()` | ✓ VERIFIED | `swept` includes `omz-plugins`; `.zshrc` went `plugins=(git zsh-users docker)` → `plugins=(git zsh-users)` in the same sweep. |
| 5 | Only files this installer wrote are deleted — a same-named file lacking the sentinel is never removed | ✓ VERIFIED | `tools-installer-wait-time` written by hand without the sentinel → `tweak_executables_present == False`, `active_tweak_ids == ()`, file survived the sweep with content intact. Unrelated `my-script` and `tools-installer-wait-time.bak` impostor also survived a real sweep. |
| 6 | Preview and effect cannot diverge — `sweep_tweaks` removes exactly the ids `active_tweak_ids` reports, because it calls it | ✓ VERIFIED (with a documented residual on one entry point) | `active_tweak_ids` and `sweep_tweaks` both delegate to one `active_policies` call; observed `set(preview) == set(swept)`. `run_uninstall` holds one `active_policies` list across the teardown (`app.py:356-359`). `perform_uninstall` still re-reads after its destructive steps — **WR-02**, accepted residual; I confirmed no live divergence: with ALL levers selected at once it still returned `swept=('tweak:countdown','omz-plugins')` and left `active_tweak_ids == ()`. |

**Score:** 26/27 truths verified (0 present-but-behavior-unverified, 0 overrides applied).

---

## Round-3 Critical fixes — independently re-verified

Both Criticals the orchestrator fixed in `8584980` were re-derived here from scratch, not read off the commit message.

| Claim | Status | Evidence |
|---|---|---|
| A never-enabled OMZ policy leaves hand-authored plugins untouched | ✓ | `plugins=(git docker kubectl)` with no record: `plugins_owned == False`, `remove_plugins` returned `()`, file byte-identical. |
| Enable-then-disable when both names are already present is a no-op | ✓ | `added=()`, `owned=True` (record with empty name list — the deliberate `None` vs `()` distinction), disable returned `()`, file byte-identical, record cleared. |
| The real drag-in case adds and precisely reverses only what was added | ✓ | `('git','zsh-autosuggestions')` → add `docker` → remove `docker` → back to `('git','zsh-autosuggestions')`; indentation and trailing comment preserved. |
| **CR-01** — a failed `.zshrc` write during removal raises and PRESERVES the ownership record so a retry recovers | ✓ | Made the containing dir `0o500`: `remove_plugins` raised `PermissionError`, `plugins_owned` stayed **True**; after restoring perms the retry returned `('docker',)` and cleared the record. |
| **CR-01 (second arm)** — an unparseable/shadowed array on removal raises rather than clearing the record | ✓ | Record held, then a later multi-line array added to shadow: `remove_plugins` raised `OmzPluginsError` (`The last plugins=(...) array … is the multi-line form…`) and `plugins_owned` stayed **True**. |
| **CR-02** — a symlinked `~/.zshrc` is written THROUGH, not replaced | ✓ | `~/.zshrc` symlinked to `dotfiles/zshrc`: after `write_plugins`, `z.is_symlink() == True` and the repo copy contained `plugins=(git docker)`. |

---

## Data-Flow Trace (Level 4)

| Artifact | Rendered value | Source | Real data | Status |
|---|---|---|---|---|
| `UninstallScreen` `#tweaks` row | `blocks + helpers (tweak:countdown, omz-plugins)` | `inputs.tweak_ids()` → `active_tweak_ids` → `active_policies` → `tweak_present` / `tweak_executables_present` / `plugins_owned` (all read the FS) | Yes | ✓ FLOWING |
| `PoliciesScreen` row state cells | `● [on]` / `○ [off]` | `Policy.active` — `tweak_present(...)` / `plugins_owned(state_path)`, evaluated at `_build_app` time | Yes at build; **stale after an in-app mutation** | ⚠️ STATIC on re-entry (WR-01, accepted) |
| `PoliciesScreen` `#policy-detail` | omz-plugins disclosure copy | `_policy_detail` literals + `policy.missing_requires` | Yes, but 3 rows clipped at 80 cols | ✗ **not reaching the user** (gap) |
| Install summary + skip lines | counts and ids | `summarize(outcomes)` / `outcome.blocked_by` from the live run | Yes | ✓ FLOWING |
| CLI uninstall preview | `These shell tweaks will also be disabled (…)` + `omz-plugins removes docker from … .zshrc` | one held `active_policies` list + `omz_removal_detail` | Yes | ✓ FLOWING |

---

## Behavioral Spot-Checks

| Behavior | How | Result | Status |
|---|---|---|---|
| Dependency skip + transitivity + reporting | Drove `run_installs`/`summarize`/`render_summary`/`render_skipped` with a stub installer | `attempted=['A','D']`; B,C `dependency-failed` with `blocked_by`; both console renderers correct | ✓ PASS |
| OMZ enable/disable across 6 `.zshrc` shapes | Drove `write_plugins`/`remove_plugins` on real temp files | All 6 as specified, incl. both round-3 Criticals | ✓ PASS |
| Sweep removes helper + block + plugins edit; spares unowned files | Drove `sweep_tweaks` on a real sandbox FS | swept both ids; impostor and unrelated file survived; 2nd sweep empty (idempotent) | ✓ PASS |
| Orphaned-executable case (REQ's literal case) | rc block hand-cleared, helper left | `active == ('tweak:countdown',)`, swept, helper removed | ✓ PASS |
| CLI `run_uninstall` confirmed vs declined | Real function, `confirm` stub | Confirmed: swept, files gone. Declined: **nothing** removed, `.zshrc` intact | ✓ PASS |
| TUI `perform_uninstall` all levers at once | Real function via the wired `_do_uninstall` shape | `swept=('tweak:countdown','omz-plugins')`, `active_tweak_ids == ()` | ✓ PASS |
| Policies live toggle (real Textual screen) | `run_test()` pilot + `space` | `.zshrc` edited then reverted; row state flipped `○ [off]` ↔ `● [on]` | ✓ PASS |
| Presence gate + unusable `.zshrc` (real screen) | `run_test()` pilot + `space` | Both blocked, both left the file untouched, both surfaced a specific status message | ✓ PASS |
| `UninstallScreen.enter_view` live refresh, both directions | Mutated state behind the suspended screen | rows `[]` → `['#tweaks']` after enable; back to `[]` after sweep | ✓ PASS |
| Detail-panel visibility at real widths | `run_test(size=…)` + `Console.render_lines` vs `container_size.height` | **omz-plugins needs 10 rows / 7 at 80 cols** | ✗ **FAIL** — see Gaps |

## Tier-3 Container Execution (re-run, not trusted from SUMMARY)

| Check | Command | Result | Status |
|---|---|---|---|
| Real Oh-My-Zsh round trip | `docker run --rm -i -v repo:ro alpine:latest` + official unattended installer | `73:plugins=(git)` → added `('docker',)` → `('git','docker')`; other lines identical; real `zsh -i` gave `gst='git status'` and `docker plugin dir loaded: 1`; reverse removed `('docker',)`, record cleared | ✓ PASS |

---

## Requirements Coverage

| Requirement | Source plan | Status | Evidence |
|---|---|---|---|
| `REQ-install-failure-propagation` — `run_installs` tracks failed ids, skips dependents whose `requires` intersects, emits a distinct "dependency failed" outcome | 03-01 | ✓ SATISFIED | `session.py` `_UNRESOLVED` + forward-pass skip; `InstallStatus.DEPENDENCY_FAILED`; `InstallOutcome.blocked_by`; `Summary.dependency_failed`; `render_skipped` wired into `run_wizard`. Behaviorally proven end to end. |
| `REQ-oh-my-zsh-plugin-config` — enabled via a config-array edit to `plugins=(...)`, reusing the existing tweak mechanism, not a `Tool`/`Method`/`requires` catalog entry | 03-02 | ✓ SATISFIED | `installer/omz.py` + `omz_plugins_policy` (a third `Policy` factory beside `ban_policy`/`tweak_policy`), wired in `setup.py:221-225`. Zero registry change. Proven against the real upstream installer. *(The REQ's "reusing `apply_block`/`strip_block`" wording is satisfied at the mechanism level — `Policy` apply/remove — and deliberately NOT at the marker-block level for `.zshrc`, per CONTEXT D-02. `apply_block`/`strip_block` are reused for the ownership record in the installer-owned `~/.myshellrc`.)* |
| `REQ-uninstall-sweep-tweak-executables` — a full uninstall removes `ManagedExecutable` artifacts, not only `Tool`-shaped ones | 03-03 | ✓ SATISFIED | `tweak_executables_present` + `active_policies`/`active_tweak_ids`/`sweep_policies`/`sweep_tweaks`; wired into both `run_uninstall` (CLI) and `perform_uninstall` (TUI) with required `bundles`/`zshrc_path`. `tools-installer-wait-time` observed removed via both paths. |

No orphaned requirements: `REQUIREMENTS.md` maps exactly these three IDs to Phase 3, and every one is claimed by a plan.

**REQUIREMENTS.md bookkeeping (informational):** lines 23-24 still show `[ ]` and the tracking table (lines 120-121) still reads `Pending` for `REQ-install-failure-propagation` and `REQ-uninstall-sweep-tweak-executables`, though both are now satisfied. `REQ-oh-my-zsh-plugin-config` is already `[x]`/`Complete`. Not a code gap — a ledger update for phase close-out.

---

## Decision Coverage (non-blocking)

| Decision | Honored | Where |
|---|---|---|
| D-01 in-place regex edit of `plugins=(...)`, insert/remove only the managed names | ✓ | `omz._rewrite`, `_PLUGINS_LINE` |
| D-02 NOT a reuse of `apply_block`/`strip_block` for `.zshrc` | ✓ | `omz.py` module docstring + `_atomic_write` path; markers only ever land in `~/.myshellrc` |
| D-03 single-line form only; multi-line explicitly out of scope | ✓ | `_ANY_PLUGINS_OPEN` shadow detection, `_SHADOWED`/`_NO_ARRAY` refusals |
| D-04 symmetric teardown reusing the same policy remove pair | ✓ | `sweep_policies` calls `Policy.remove`; writes no removal logic |
| D-05 presence detection via `~/.oh-my-zsh` or `$ZSH` | ✓ | `omz.omz_present`, all three branches exercised |
| D-06 unmet-`requires` reuses the existing UX, no new pattern | ✓ | `missing_requires` → existing `PoliciesScreen` requires cell + status message |

6/6 honored, 0 not honored.

---

## Test Quality Audit

| Aspect | Finding |
|---|---|
| Disabled/skipped tests on requirements | **0** — no `@pytest.mark.skip`, no `xfail`, no `pytest.skip(`, no `skipif` anywhere in `tests/` |
| Circular tests (expected values generated by the SUT) | **0** — no test writes fixture files from the system under test |
| Assertion strength | Value/behavioral level throughout: on-disk file content comparisons, tuple equality on `SweepResult`/`Summary`, byte-identity checks on non-target lines |
| HOME sandboxing | Enforced in all 13 rc-touching modules + an autouse `no_zdotdir` conftest fixture + a dedicated `test_real_home_rc_files_are_untouched` guard |
| **Weakness found** | `test_policy_detail_discloses_the_partial_state_reading` asserts on the model string `app.screen.detail_text`, never on the rendered panel — it is the guard for must-have #7 and it cannot catch (and did not catch) the clipping regression. Captured in the gap's `missing` list. |
| **Weakness confirmed (WR-03)** | Verifier-run mutation: replacing `setup.py`'s `tweak_ids=lambda: active_tweak_ids(...)` with a build-time-frozen closure **passed all 852 tests**. The review's claim is accurate. Product code is correct; only the regression guard is weak. Tree restored and re-verified clean. |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | — | — | **None.** No `TBD`/`FIXME`/`XXX` debt markers in any file this phase touched. The one `PLACEHOLDER` grep hit (`installer/tweaks.py:19` `_BIN_DIR_PLACEHOLDER`) is a real template-substitution token consumed by `tweaks.py:138`, not a stub. |

---

## Known Limitations — accepted, carried-forward residuals

These are the three Warning-level findings from **`03-REVIEW.md` iteration 3 (final, cap reached)**, Warnings section. They were **not** fixed, by explicit decision: this phase ran three full deep-review + fix cycles (Round 1: 1 Critical + 8 Warnings; Round 2: 1 new Blocker; Round 3: 2 new Criticals + these 3 Warnings), and `.planning/ONESHOT-RULES.md`'s fix-and-re-review loop is capped so it cannot iterate indefinitely — Warning-level residuals at the cap are documented and carried forward rather than blocking phase completion. The two Round-3 Criticals **were** fixed (commit `8584980`) and are independently re-verified above.

I reproduced each residual myself rather than taking the review's word, and each is bounded as the review claimed.

### WR-01 — `PoliciesScreen` has no `enter_view`; rows go stale after an in-app uninstall

*Source: 03-REVIEW.md iteration 3, Warnings.* `PoliciesScreen.__init__` snapshots `{policy.id: policy.active}`, and `Policy.active` is itself evaluated once at `_build_app` time (`setup.py:203-226` builds `PolicyInputs(policies=[...])` as a **list**, not a closure). It is the only one of the three non-catalog screens without an `enter_view` override.

**Reproduced:** built the screen with both policies active, ran a sweep behind its back, called `enter_view()`, navigated back — both rows still rendered `● [on]` while the helper was gone from disk and `.zshrc` was reverted.
**Bounded:** `'enter_view' in PoliciesScreen.__dict__` is `False`; nothing is destroyed, `Policy.remove` is idempotent, and one recovery toggle restored a correct `active_state` while leaving `.zshrc` intact. Cost is one spurious keystroke.
**Fix when picked up:** make `PolicyInputs.policies` a `Callable[[], list[Policy]]` and add an `enter_view` that rebuilds the list (the whole list — `active` is captured at construction).

### WR-02 — the preview/effect invariant holds by construction on only one of the two teardown entry points

*Source: 03-REVIEW.md iteration 3, Warnings.* Commit `7a6c33b` hoisted `active_policies` in `run_uninstall` so nothing is read after the destructive steps. `perform_uninstall` (`installer/app.py:437-438`, the TUI's `remove=_do_uninstall` wire) still calls `sweep_tweaks` **after** `remove_paths` / `remove_shims` / `remove_ban_aliases` / `remove_managed_block` — and `sweep_tweaks`' own docstring says "`run_uninstall` is not such a caller and must not use it", which describes `perform_uninstall` equally well.

**Confirmed present in code** (read at `app.py:429-439`).
**Bounded:** no live divergence exists today. Driving `perform_uninstall` with **all** levers selected at once still returned `SweepResult(swept=('tweak:countdown','omz-plugins'), failed=())` and left `active_tweak_ids() == ()` — shim names do not collide with `tools-installer-` helpers and every rc rewrite is marker-scoped. The residual is that the invariant rests on that argument rather than on construction.
**Fix when picked up:** hoist `active_policies` inside `perform_uninstall` mirroring `run_uninstall`, and port `test_run_uninstall_sweeps_the_very_tweaks_it_previewed`; failing that, name `perform_uninstall` as a documented exception in `.claude/architecture.md:133-141`.

### WR-03 — mutation gap: freezing `tweak_ids` at build time passes the whole suite

*Source: 03-REVIEW.md iteration 3, Warnings.* Concerns `tests/test_setup.py:166-187` against `setup.py:199-201`.

**Independently confirmed by the verifier.** I replaced `tweak_ids=lambda: active_tweak_ids(...)` with a build-time-frozen closure and ran the suite: **852 passed**. The mutant survives. Tree restored (`git status --porcelain` clean for tracked files) and the suite re-run green.
**Bounded:** this is a *test-strength* gap, not a product defect. The runtime behavior it fails to guard is correct and I proved it directly — `UninstallScreen.enter_view` re-reads `self._tweak_ids_of()` and the row appeared and disappeared as state changed behind the suspended screen.
**Fix when picked up:** assert the live-callable contract behaviorally (mutate state, re-enter, assert the row changes) rather than asserting the composition root's shape.

---

## Gaps Summary

**One gap, newly found by this verification and not previously triaged.**

Plan 03-02's must-have #7 requires that the Policies detail panel *disclose the ownership/partial-state reading before the user acts on it* — a mitigation the cycle-1 review raised as MEDIUM precisely so a user cannot toggle without understanding what the row's ON/OFF state means. The copy is present in `_policy_detail`, but it never reaches the screen: `#policy-detail` is a plain `Static` with `height: 7` and `overflow_y: hidden` (verified non-scrollable), and the omz-plugins detail needs **10 rendered rows at 80 columns** — 8 at 100 and at 120. The three rows lost at 80 cols are the caveat line and the entire ownership disclosure:

```
LOST> Needs Oh-My-Zsh installed; only the single-line plugins=(...) form is edited.
LOST> Reads ON only once this installer has enabled it, so a plugins=(git docker)
LOST> you wrote by hand shows OFF and is left alone.
```

This is a **re-occurrence** of a defect this phase already found and fixed once. Commit `1adcfe4` raised the panel from `height: 5` to `height: 7` after 03-02's own tmux check caught the fourth line being hidden. Commit `3d1ee1f` — the CR-01 record-ownership fix — then replaced that fourth line with a materially longer one (the semantics changed from content-based to record-based ownership, which is correct and is the data-loss fix), pushing the requirement to ~10 rows. **No tmux check has been run since `3d1ee1f`**, so the regression went unseen. A secondary instance: `tweak:countdown` clips 1 row (`toolchain.`) at 80 cols.

The guarding e2e test could not catch this because it asserts on `app.screen.detail_text`, the model string, rather than on the rendered panel region. Fixing the height without also fixing the test leaves the same regression free to recur on the next copy change.

**What this gap does NOT affect:** all three phase requirements and all three ROADMAP success criteria are met. The underlying data-safety behavior is correct and independently proven — record-based ownership means hand-authored plugins are never touched, a failed write preserves the record for retry, and a symlinked `.zshrc` is written through. The gap is that the user is not shown the explanation of that behavior before acting on it.

**Not blocked by:** WR-01/WR-02/WR-03, which are the already-triaged, intentionally-deferred residuals documented above.

---

## Verification method note

Nothing in this report is taken from `03-01/02/03-SUMMARY.md`. Every truth was checked by executing the real production callables (`run_installs`, `write_plugins`, `remove_plugins`, `active_tweak_ids`, `sweep_tweaks`, `run_uninstall`, `perform_uninstall`), driving the real Textual screens (`PoliciesScreen`, `UninstallScreen`) under a pilot, re-running the Tier-3 container check against the official Oh-My-Zsh installer, and re-running `make validate` and `make test` on this exact tree. The WR-03 mutation claim and the panel-clipping finding were both produced by the verifier's own experiments.

---

_Verified: 2026-09-05T10:54:04Z_
_Verifier: Claude (gsd-verifier)_
