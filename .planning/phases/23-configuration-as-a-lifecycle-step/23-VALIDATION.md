---
phase: "23"
slug: "configuration-as-a-lifecycle-step"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-11-06"
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from
> `23-RESEARCH.md` § Validation Architecture and `23-UI-SPEC.md` § Acceptance items
> (amended 2026-11-06: no automatic alias migration).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-xdist + coverage (`fail_under = 90`); Textual pilot for screens |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]`; `tests/conftest.py` (scratch HOME, sandboxed receipts and bin dir, host-presence stub and the extended real-HOME guard from 23-01) |
| **Quick run command** | `uv run pytest tests/test_<module>.py -x` |
| **Full suite command** | `make validate && make test` |
| **E2E** | `make e2e` (`scripts/container-e2e-verify.sh all`, disposable Fedora container; 23-16 adds the hook and settings probes) |
| **Estimated runtime** | ~110 s full suite locally (10 workers); ~9 min on the macOS CI runner |

---

## Sampling Rate

- **After every task commit:** the task's own `<automated>` commands (targeted modules with `-n auto`, then the `-k` RED/GREEN filter with `-n 0`)
- **After every plan wave:** `make validate && make test`
- **Before `/gsd-verify-work`:** full suite green, plus the recorded `make e2e` run of 23-16 Task 3
- **Max feedback latency:** 120 seconds (faulthandler dumps stacks on a stalled test)

---

## Wave Map

| Wave | Plans |
|------|-------|
| 1 | 23-01 hook register path and one host list · 23-02 settings splice engine · 23-03 Oh-My-Zsh `$ZSH` and theme writer · 23-04 `.zshenv` SHELL block, terminal SHELL lines, environment.d value |
| 2 | 23-05 unregister builders, herdr pair, tealdeer cache · 23-06 settings API and ledger |
| 3 | 23-07 hook and `.zshenv` drift, RECONFIGURE, new-host re-sync · 23-08 removal unregister core |
| 4 | 23-09 shell-init bundles, keyed prompt table, theme and lean-tip handoffs, SC4 copy · 23-10 run options core and shared review helpers |
| 5 | 23-11 Policies settings rows · 23-12 TUI review options and keyed modal · 23-13 headless prompts |
| 6 | 23-14 legacy alias strip and app composition · 23-15 removal reverts settings and shell init, uninstall UI |
| 7 | 23-16 container e2e |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 23-01-T1, 23-01-T2 | 23-01 | 1 | CONF-01 (register), CONF-03 | T-23-02, T-23-03 | hosts come from `present_harnesses` only (no second host table); register only present ∩ supported − recorded; receipt records hosts and every re-record keeps them; pi in no map; rtk hook gone; no install or update entry point takes the catalog; no test reads the developer's hosts | unit (fake runner) | `uv run pytest tests/test_postinstall.py tests/test_engine.py tests/test_receipts.py tests/test_update.py tests/test_session.py tests/test_registry.py tests/test_model.py tests/test_catalog_tui.py tests/test_execute_screen.py tests/test_wizard_app.py -n auto -q --no-cov` | ✅ files, tests written with their code | ⬜ pending |
| 23-05-T1 | 23-05 | 2 | CONF-01 (unregister builders) | T-23-01 | unregister argv from recorded hosts only, filtered through the closed map, never `all`/`auto`; `hook_method` and catalog-id `host_labels` | unit | `uv run pytest tests/test_postinstall.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-05-T2 | 23-05 | 2 | CONF-06 | T-23-46 | `tldr --update` once after install and once after `u`; failure is a warning, never a row failure; cache dirs in `config_paths`; herdr pair defined, unwired | unit | `uv run pytest tests/test_postinstall.py tests/test_run.py tests/test_update.py tests/test_registry.py tests/test_model.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-02-T1, 23-02-T2, 23-02-T3 | 23-02 | 1 | CONF-08, CONF-09, CONF-12 (engine) | T-23-04, T-23-05, T-23-06 | guarded splice + re-parse for JSON, JSONC, TOML; byte-identical revert; comments and unrelated keys kept; invalid file refused with line/column; compare-before-commit refuses a file changed mid-write; symlinked file edited through its target | unit | `uv run pytest tests/test_agent_settings.py tests/test_atomic.py tests/test_shellrc.py -n auto -q --no-cov` | ❌ Wave 0: `tests/test_agent_settings.py` created by 23-02 T1 | ⬜ pending |
| 23-03-T1 | 23-03 | 1 | CONF-07 | T-23-08 | `ZSH=/custom/omz` → the template exports the custom root; nothing created under `~/.oh-my-zsh` | unit + policy | `uv run pytest tests/test_omz.py tests/test_policy_omz.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-03-T2, 23-09-T1, 23-09-T3 | 23-03, 23-09 | 1, 4 | CONF-11 | T-23-07, T-23-25 | `robbyrussell` before the source line only when no theme; `agnoster` unchanged; starship writes `""`; starship replaces only the installer's recorded default; OMZ handoff names `omz theme use/set` | unit | `uv run pytest tests/test_omz.py tests/test_tweaks.py tests/test_post_install.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-04-T1, 23-04-T2, 23-07-T2 | 23-04, 23-07 | 1, 3 | CONF-05 (SHELL, terminals, drift) | T-23-09, T-23-10, T-23-17 | real zsh in a scratch HOME prints the zsh path; user `SHELL=` line kept; kitty/WezTerm regions carry SHELL; WezTerm user env table kept; absent terminal no drift; `.zshenv` drift is `≈` on the zsh row; RECONFIGURE done notes name the file; Shell section | unit (+ one real-zsh subprocess, skipped without zsh) | `uv run pytest tests/test_terminal_shell.py tests/test_locations.py tests/test_version_status.py tests/test_session.py tests/test_render.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-04-T3, 23-10-T3, 23-11-T3 | 23-04, 23-10, 23-11 | 1, 4, 5 | CONF-05 (environment.d, asked) | T-23-11, T-23-28, T-23-32 | one environment.d writer carries the absolute zsh path; Bun redirect byte-identical; desktop option writes only when chosen, Linux only; Policies row writes/removes it; its `owned` footprint is swept by uninstall | unit + pilot | `uv run pytest tests/test_env_redirect.py tests/test_policy_env_redirect.py tests/test_session.py tests/test_policies_e2e.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-06-T1, 23-06-T2, 23-06-T3 | 23-06 | 2 | CONF-08, CONF-09, CONF-12 (API + ledger) | T-23-12, T-23-13, T-23-14, T-23-15 | keys only when absent; `acceptEdits` stays "set by you"; opt-out byte-identical; created file deleted; invalid JSON/JSONC/TOML untouched; drift repair; retry-once CAS; tampered ledger never removes a user key; opencode `.jsonc` pick; Claude attribution `""` strings; cursor default replaced and restored only while ours; VS Code lean keys per OS, no Linux `update.mode` | unit (scratch HOME) | `uv run pytest tests/test_agent_settings.py tests/test_receipts.py tests/test_agent_env.py tests/test_agent_policy.py -n auto -q --no-cov` | ✅ (after 23-02) | ⬜ pending |
| 23-07-T1 | 23-07 | 3 | CONF-01 (drift, RECONFIGURE) | T-23-16, T-23-17 | unrecorded present supported host reads `≈` with `register {tool} for {hosts}`; RECONFIGURE registers it and records it; a failed register fails the row with the step text | unit | `uv run pytest tests/test_version_status.py tests/test_session.py tests/test_render.py -k "unrecorded_present_host or ignores_absent_unsupported or registers_the_missing_host or failed_register_step or hook_reconfigure_prints or each_config_step_kind_dispatches" -q --no-cov -n 0` | ✅ | ⬜ pending |
| 23-07-T3 | 23-07 | 3 | CONF-02 | T-23-16, T-23-17, T-23-18 | installing codex re-runs codegraph's register for codex only; claude never re-run; hosts recomputed after the rows; failure is a warning; report section lines | unit | `uv run pytest tests/test_session.py tests/test_render.py -k "resyncs_codegraph_for_codex_only or without_a_host_install or reads_hosts_after_the_rows or failed_resync_is_a_warning or agent_host_hooks_section" -q --no-cov -n 0` | ✅ | ⬜ pending |
| 23-08-T1, 23-08-T2, 23-08-T3, 23-15-T3 | 23-08, 23-15 | 3, 6 | CONF-01 (unregister on removal) | T-23-19, T-23-20, T-23-21, T-23-22 | removal runs `codegraph uninstall --target <recorded> … --keep-cli` before any delete, never a present unrecorded host; changed unregister refuses; failed unregister keeps paths and receipt; CLI and ConfirmUninstall list the unregister line first; detail bar names the hosts | unit + integration + pilot | `uv run pytest tests/test_uninstall.py tests/test_uninstall_e2e.py tests/test_app.py tests/test_wizard_app.py tests/test_version_status.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-09-T1, 23-09-T2, 23-12-T2, 23-13-T2, 23-15-T2 | 23-09, 23-12, 23-13, 23-15 | 4, 5, 6 | CONF-04 | T-23-23, T-23-24, T-23-40, T-23-47, T-23-48 | six bundles guarded and parsing in bash/zsh; yes → ON + handoff line; no/esc → nothing, no health state; headless and TUI `--yes` never ask; keyed prompt per tool, default no headless; removal turns off only that tool's bundle | unit + pilot | `uv run pytest tests/test_post_install.py tests/test_tweaks.py tests/test_execute_screen.py tests/test_app.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-09-T3 | 23-09 | 4 | ROADMAP SC4, CONF-12 (summary) | — | chsh-absent line names the sync that runs and the old promise is gone from `installer/`; VS Code lean tips | unit/grep | `uv run pytest tests/test_post_install.py tests/test_registry.py -k "names_the_sync_that_runs or returns_the_lean_tips or declare_their_actions" -q --no-cov -n 0` | ✅ | ⬜ pending |
| 23-10-T1, 23-10-T2, 23-10-T3, 23-12-T1, 23-13-T1, 23-13-T2 | 23-10, 23-12, 23-13 | 4, 5 | CONF-08, CONF-09, CONF-12 (run options, D-09) | T-23-26, T-23-27, T-23-33, T-23-34, T-23-35, T-23-47, T-23-48 | options off by default, never remembered, `--yes` never turns them on; shown only for runnable rows; applied to every covered done row; a default run writes nothing; space refused after enter; headless questions default to no; report one key per line ≤ 78 cells; no new CLI flag | unit + pilot | `uv run pytest tests/test_session.py tests/test_render.py tests/test_execute_screen.py tests/test_app.py tests/test_prompt.py tests/test_setup.py tests/test_cli.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-11-T1, 23-11-T2, 23-11-T3 | 23-11 | 5 | CONF-08, CONF-09, CONF-12 (Policies rows) | T-23-29, T-23-30, T-23-31 | one row per documented setting with the verbatim copy table; `● [on]`/`● [yours]`/`○ [off]`/`! [drift]`; unreadable only with a ledger record; YOURS writes nothing; exact toggle results; details ≤ 9 lines at 80x20; values render literally | pilot + unit | `uv run pytest tests/test_policies_e2e.py tests/test_policy_settings.py tests/test_agent_settings.py tests/test_layout_80x20.py tests/test_wizard_app.py -n auto -q --no-cov` | ❌ Wave 0: `tests/test_policy_settings.py` created by 23-11 T1 | ⬜ pending |
| 23-14-T1, 23-14-T2, 23-14-T3 | 23-14 | 6 | CONF-10 (as amended 2026-11-06) | T-23-36, T-23-37, T-23-38 | an enabled `claude-skip` rc ends with no alias and NO settings file written; the notice points at the auto-approve Policies row; second launch prints nothing; cursor wrapper removed with nothing written; a block that cannot be edited is kept with a warning; uninstall strips legacy blocks; Policies lists none of the four bundles; app composes the settings rows | unit + setup | `uv run pytest tests/test_tweaks.py tests/test_policy_tweaks.py tests/test_setup.py tests/test_policies_e2e.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-15-T1, 23-15-T2 | 23-15 | 6 | CONF-08, CONF-09, CONF-12 (removal revert) | T-23-39, T-23-41, T-23-42 | removing an agent reverts only keys still ours; changed keys kept and named; unparsable file is a warning; failed removal reverts nothing; pseudo-row and CLI revert every written key; `c` supersedes the revert | unit + integration + pilot | `uv run pytest tests/test_app.py tests/test_uninstall_e2e.py tests/test_wizard_app.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 23-16-T1, 23-16-T2, 23-16-T3 | 23-16 | 7 | CONF-01, CONF-08 (real container) | T-23-43, T-23-44, T-23-45 | probes fail on a planted survivor and pass clean (self-tests); one Fedora run records `TRACER_HOOKS_UNREGISTERED_OK`, `TRACER_SETTINGS_REVERT_OK`, `TRACER_LEFTOVER_OK`, container removed; only `.zshenv` may be allowlisted, every other survivor is a finding | script test + container e2e | `uv run pytest tests/test_container_e2e_receipts.py -n auto -q --no-cov`; `make e2e` | written by 23-16; the recorded run is manual evidence | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_agent_settings.py` with per-format fixtures (Claude strict JSON, cursor JSON with CLI defaults, opencode `.jsonc` and `.json`, VS Code JSONC with both comment styles, trailing commas and `//` inside a string, Codex TOML with `[features]`/`[projects."…"]`, an invalid file per format, a missing file) — 23-02 Tasks 1-3, extended by 23-06
- [ ] `tests/conftest.py`: the `no_host_presence` stub and `real_present_hosts` restore fixture; `.zshenv` in the real-HOME guard plus listing fingerprints for `~/.config/environment.d` and the config-write ledger dir, never a live agent settings file (research Pitfall 12) — 23-01 Task 1
- [ ] `tests/test_policy_settings.py` for the settings Policy factories — 23-11 Task 1
- [ ] Container probe seam: the hook and settings probes print parseable `H/F/W/E/D/L/K` lines so the bash logic is self-tested with a stubbed `exec_tester` — 23-16 Tasks 1-2
- [ ] The fake runner that records argv per hook already exists in `tests/test_postinstall.py`; reused, not rebuilt

Every Wave 0 item is written by the task named above and committed together with its code, its RED output recorded in the SUMMARY (review R1-01, ledger row 31). No plan uses the MISSING sentinel.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One real Fedora container lifecycle with codegraph registered for real hosts and unregistered on removal, and an agent setting written and reverted by the uninstall | CONF-01, CONF-08 | needs podman and network; recorded evidence | `make e2e` (23-16 Task 3); record the tracer lines and the container-gone check |
| NO_COLOR 80x20 look of the run-option rows, the keyed shell-init modal, the Policies settings states and ConfirmUninstall | CONF-04, CONF-08, CONF-12 / UI-SPEC | real-terminal rendering; pilot tests assert text, not look | tmux 80x20 with `NO_COLOR=1` in a disposable container: toggle an option with `space`, answer the starship prompt, visit a Policies settings row in each state, open ConfirmUninstall for codegraph |
| starship actually draws the prompt after "yes" and Oh-My-Zsh draws none | CONF-04, CONF-11 | needs a real interactive zsh with starship and Oh-My-Zsh | in the container, install oh-my-zsh and starship attended, answer yes, open a new terminal |
| The Cursor CLI still ignores the commit attribution opt-out (UI caveat, research A3) | CONF-09 | live vendor behaviour | in a container with cursor-agent, make a commit with attribution off and inspect the trailer |
| VS Code lean mode on macOS (paths, `update.mode`, `defaultProfile.osx`) | CONF-12 | needs a real macOS host | on macOS: run lean mode on a commented settings.json, then opt out |
| The first launch after the upgrade on the developer's own host strips its enabled `claude-skip` alias block and writes no settings | CONF-10 (amended) | agents never run the installer on the host | the user launches `make setup` themselves, reads `Removed the claude-skip alias; turn on claude auto-approve in Policies.`, and confirms `~/.claude/settings.json` is unchanged until they turn the row on |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (43/43 tasks across 23-01..23-16)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (no plan uses the MISSING sentinel)
- [x] No watch-mode flags
- [x] Feedback latency < 120s (per-task commands are targeted pytest runs; `make e2e` is the recorded manual-evidence run, not a per-task sample)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
