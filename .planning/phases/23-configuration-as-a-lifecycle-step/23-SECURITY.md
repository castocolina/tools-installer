---
phase: "23"
slug: configuration-as-a-lifecycle-step
status: verified
verdict: SECURED
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_total: 63
mitigated: 61
accepted: 2
open: 0
threats_open: 0
threats_open_nonblocking: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
audited_head: a30bb2f
created: "2026-11-07"
---

# Phase 23 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Where the register comes from:** the `<threat_model>` blocks of 23-01..23-16-PLAN.md. They hold
T-23-01..T-23-62 with no gaps. T-23-SC appears in every plan and counts once. That is 63 threats.

- Severity: 0 critical, 25 high, 26 medium, 12 low.
- Disposition: 61 mitigate, 2 accept (T-23-57, T-23-SC), 0 transfer.

**Method:** ASVS L1 (the mitigation is in the cited code) plus a passing test for each one. The
code was read at `a30bb2f` (last code commit `8276273`). The checks were read-only:
- `uv run pytest <107 node ids> --no-cov -n 4` covers every test the register names plus every
  review-fix test in 23-REVIEW-FIX.md: 137 passed (with parametrized cases), 0 failed.
- `tests/test_agent_settings.py`, `test_postinstall.py`, `test_terminal_shell.py`,
  `test_tweaks.py`, `test_env_redirect.py`, `test_sandbox.py` and the two zero-sudo tests in
  `test_executors.py`: 249 passed.
- `make validate`: exit 0 (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).

No install, removal, `make setup`/`fix`/`uninstall` or `make e2e` was run by the audit.

**Test-name drift (not gaps):**
- T-23-04 names `test_a_toml_splice_into_an_array_is_refused`. C-21 (24e739a) replaced it with
  `test_a_toml_splice_never_lands_inside_an_array` (`tests/test_agent_settings.py:289`). The
  behaviour moved from "refuse" to "try each `[` line and keep the first one the guard accepts"
  (`installer/agent_settings.py:337-354`). It is still behind `_guarded`.
- T-23-59 names `test_which_with_brew_finds_a_brew_binary_off_path`. The test is
  `test_which_with_brew_finds_a_linuxbrew_binary_shutil_which_cannot_see`
  (`tests/test_postinstall.py:449`), as 23-10-SUMMARY records.
- T-23-25 names `test_omz_install_keeps_a_user_theme`. That test exists, but the sanitizing is
  covered by `test_a_user_theme_name_is_sanitized_in_the_handoff`
  (`tests/test_post_install.py:385`).
- "Byte-exact revert" is not what the code does. A revert cuts the recorded fragment when it
  occurs once. Otherwise it cuts the located member. Both go through the re-parse and
  deep-compare guard (`installer/agent_settings.py:401-424`). When the user edited around the
  key, the result is not byte-identical, by design (C-01, C-19).

## Threat Verification

| ID | Sev | Disposition | Evidence (code) | Test |
|----|-----|-------------|-----------------|------|
| T-23-01 | high | mitigate | `installer/postinstall.py:207-230` `unregister_hosts`/`unregister_argvs` filter receipt ids through the code-owned target map; empty → `()`; never `all`/`auto` | `tests/test_postinstall.py:354`, `:362` |
| T-23-02 | medium | mitigate | `installer/postinstall.py:267-300` `register_hooks`: present − recorded, only supported targets (`run_postinstall` :249-264); marker-dir `shortcut:` at :277-278 | `tests/test_postinstall.py:239` (pins the recorded empty list, C-07), `tests/test_session.py:1041` |
| T-23-03 | high | mitigate | `tests/conftest.py:382` autouse `no_host_presence`; `:125-152` real-HOME fingerprint covers `.zshenv` (`:36`), `environment.d` and the config-ledger dir, as listings only (`:141`) | session fingerprint; whole suite under the autouse fixtures |
| T-23-49 | high | mitigate | `tests/conftest.py:255` `sandboxed_setup_paths` re-roots `setup`'s HOME constants | `tests/test_sandbox.py:73` |
| T-23-50 | medium | mitigate | `installer/postinstall.py:286-288` no receipt → no command | `tests/test_postinstall.py:259`, `tests/test_engine.py:1013` |
| T-23-04 | high | mitigate | `installer/agent_settings.py:252-260` `_guarded` (re-parse + `same_value` deep compare) on every insert/remove/replace (`:318`, `:351`, `:412`, `:421`, `:424`, `:441`) | `tests/test_agent_settings.py:104`, `:289` (see drift), `:948` (C-12), `:1032` (C-21) |
| T-23-05 | high | mitigate | `installer/agent_settings.py:455-470` `write_if_unchanged`/`delete_if_unchanged`; `installer/atomic.py:95-109` `snapshot_matches` (dev + inode + bytes), `:36-55` sibling temp + `os.replace` | `tests/test_agent_settings.py:304` |
| T-23-06 | high | mitigate | `installer/agent_settings.py:149-167` `parse_settings` raises `SettingsParseError`; `_apply_once` :698 returns the refusal before any write; non-UTF-8 → parse error (:618-619) | `tests/test_agent_settings.py:122` |
| T-23-07 | medium | mitigate | `installer/omz.py:111` theme regex (export/typeset/indented); `:594-615` `set_theme` inserts only when absent and rewrites only a value equal to `replace` | `tests/test_omz.py:833`, `:891`, `:851` |
| T-23-51 | medium | mitigate | `installer/omz.py:626-656` `apply_theme`: reserve the record, write, roll back on `OSError` | `tests/test_omz.py:904` |
| T-23-08 | medium | mitigate | `installer/omz.py:443-446` the real `omz_root` is written, `shlex.quote`d | `tests/test_policy_omz.py:214` |
| T-23-09 | medium | mitigate | `installer/terminal_shell.py:306-334` owned `ZSHENV_BEGIN/END` block via `apply_block`/`strip_block`; WezTerm `or {}` keeps a user table (:161-168) | `tests/test_terminal_shell.py:857`, `:993` |
| T-23-10 | medium | mitigate | `installer/terminal_shell.py:311` `shlex.quote`; `:155-158` `_lua_string`; `:122-130` `_safe_executable` (absolute, no control chars); `installer/env_redirect.py:116-130` `target_path` | `tests/test_terminal_shell.py:1019`, `tests/test_env_redirect.py:413` |
| T-23-11 | low | mitigate | `installer/env_redirect.py:99` `environment_d_dir` (user XDG dir only); no system path; zero sudo | `tests/test_env_redirect.py:389`, `tests/test_session.py:1926` |
| T-23-52 | high | mitigate | `installer/env_redirect.py:182-184` no mkdir for an absolute value | `tests/test_env_redirect.py:389` |
| T-23-53 | medium | mitigate | `installer/terminal_shell.py:331-334` an `OSError` becomes a `zshenv:` warning; C-11 stops the terminal strip on that warning | `tests/test_terminal_shell.py:929`, `:1037` |
| T-23-46 | low | mitigate | `installer/postinstall.py:171-180` `_tealdeer_cache` returns a warning | `tests/test_postinstall.py:437`, `tests/test_update.py:594` |
| T-23-12 | high | mitigate | `installer/agent_settings.py:797-804` entries filtered by (setting, file, key in table, value == ours); `:848-849` only `_agent_files` paths (C-02: adapter path, plus `opencode.jsonc`); `:85-91` + `installer/receipts.py:340-352` an untrusted ledger is kept aside and blocks (C-04); `receipts.py:288-337` strict ledger schema | `tests/test_agent_settings.py:552`, `:960`, `:979`, `:1004` |
| T-23-13 | high | mitigate | `installer/agent_settings.py:638-672` `_apply_pass`: absent-only; other value → `set_by_you`; `cli_default` replaced only when it equals the CLI default; revert restores only while ours (:752-756) | `tests/test_agent_settings.py:383`, `:701` |
| T-23-14 | high | mitigate | `apply_setting` has two callers: `installer/policy.py:649` (Policies keypress) and `installer/session.py:658` (chosen run options); the launch strip writes no settings | `tests/test_session.py:1861`, `tests/test_tweaks.py:361` |
| T-23-15 | medium | mitigate | `installer/agent_settings.py:730-735` (apply) and `:851-856` (revert): retry once, then `CHANGED_WHILE_WRITING`; ledger rolled back (:713-718) | `tests/test_agent_settings.py:584` |
| T-23-54 | medium | mitigate | `installer/agent_policy*` deleted (no file, no import) | `tests/test_agent_settings.py:884` |
| T-23-55 | low | mitigate | `installer/agent_settings.py:116-130` type-strict `same_value` | `tests/test_agent_settings.py:848` |
| T-23-16 | medium | mitigate | `installer/session.py:542-585` `_resync_hooks`: only after a done host install, only receipts with a hooks entry; `register_hooks` subtracts recorded hosts | `tests/test_session.py:991`, `:1006`, `:1081` |
| T-23-56 | medium | mitigate | `installer/version_status.py:693-712` `_settings_facts`: an unparsable managed file or an untrusted ledger blocks the row | `tests/test_version_status.py:5063`, `:5078` |
| T-23-17 | medium | mitigate | `installer/session.py:575-576` per-tool `except Exception` → warning; `register_hooks` never raises on `CommandError` | `tests/test_session.py:1090` |
| T-23-18 | low | mitigate | `installer/render.py:504-506` hook lines through `sanitize_log_line`, `markup=False` | `tests/test_render.py:1518` |
| T-23-19 | high | mitigate | `installer/uninstall.py:292-313` `_hook_undo`: hosts from `receipt.hooks` only, through `unregister_argvs` | `tests/test_uninstall_e2e.py:633`, `tests/test_uninstall.py:2516` |
| T-23-20 | medium | mitigate | `installer/app.py:780-784` a failed unregister returns before any path or receipt delete | `tests/test_app.py:5893` |
| T-23-21 | medium | mitigate | `installer/app.py:776` `unregister != fresh.unregister` refuses; `:785-786` forgets hosts after a successful unregister (C-13) | `tests/test_app.py:5959`, `:5926` |
| T-23-22 | medium | mitigate | `installer/uninstall.py:303-308` the first word is the receipt-proven `tool.cmd` artifact; none → no unregister | `tests/test_uninstall.py:2479` |
| T-23-57 | low | accept | `shortcut:` at `installer/uninstall.py:300-302`; AR-23-02 | `tests/test_uninstall.py:2492` |
| T-23-23 | high | mitigate | `installer/tweaks.py:87-104` shell-init bodies are code constants guarded by `command -v`; no registry or user string reaches them | `tests/test_tweaks.py:329` (bash -n / zsh -n) |
| T-23-24 | high | mitigate | `installer/post_install.py:146` `confirm is None` or no → nothing; `:59-79` `SENSITIVE_PROMPTS` | `tests/test_post_install.py:272`, `:304`, `:313` |
| T-23-58 | high | mitigate | PATH block above the shell-init blocks; split-mode reader injected at `installer/post_install.py:91-97,152` | `tests/test_post_install.py:333`, `:248` |
| T-23-25 | low | mitigate | `installer/post_install.py:178` `sanitize_log_line(result.theme)` | `tests/test_post_install.py:385`, `:374` |
| T-23-26 | high | mitigate | `installer/session.py:230` `options = frozenset()`; `:697-712` only done rows, others `settings_skipped` | `tests/test_session.py:1861`, `:1872` |
| T-23-27 | low | mitigate | `installer/render.py:337-339` sanitized, `markup=False` | `tests/test_render.py:1518` |
| T-23-28 | low | mitigate | `installer/session.py:680-692` `environment_d_dir` + `write_linux_redirect` (refuses a foreign file, `env_redirect.py:178-180`) | `tests/test_session.py:1926` |
| T-23-59 | medium | mitigate | `postinstall.which_with_brew` used by `installer/session.py:684`, `setup.py:662,708,780` | `tests/test_postinstall.py:449` (see drift) |
| T-23-29 | high | mitigate | `installer/policy.py:607-665` `settings_policy`: YOURS refuses, drift rewrites only absent keys; engine absent-only (T-23-13) | `tests/test_policies_e2e.py:1531`, `:1557` |
| T-23-30 | high | mitigate | parse refusal (T-23-06); unreadable only with a ledger (`installer/policy.py:636`, `:683`) | `tests/test_policies_e2e.py:1582`, `:1615` |
| T-23-31 | low | mitigate | values rendered as `Text`, JSON-escaped (`KeyResult.value` via `_dump`) | `tests/test_policies_e2e.py:1648` |
| T-23-32 | medium | mitigate | `installer/policy.py:915-916` `owned` = sentinel only (`env_redirect.conf_owned`), independent of the current zsh | `tests/test_policy_settings.py:201`, `:226` |
| T-23-33 | high | mitigate | `installer/execute_screen.py:402` options start empty on every screen; `:654` frozen at start; unattended sets none | `tests/test_execute_screen.py:5265` |
| T-23-34 | medium | mitigate | `installer/execute_screen.py:572-573` `space` refused once started; `:733` passes the frozen `_run_options` | `tests/test_execute_screen.py:5142` |
| T-23-35 | low | mitigate | `Text` + `sanitize_log_line` in review values | `tests/test_execute_screen.py:5329` |
| T-23-47 | high | mitigate | `installer/app.py:221-225` every option question `default=False`; shell-init takes its table default (no) | `tests/test_app.py:244`, `:305` |
| T-23-48 | high | mitigate | `installer/app.py:175` `--yes` → `frozenset()`, asks nothing; `:180` says so | `tests/test_app.py:278` |
| T-23-36 | high | mitigate | `installer/tweaks.py:335-360` `strip_legacy_aliases` touches only `~/.myshellrc`; launch call `setup.py:1464` | `tests/test_tweaks.py:361` |
| T-23-37 | medium | mitigate | `installer/tweaks.py:262-271` `strip_tweak_block` → `strip_block` on owned markers; failure kept with a warning (:356-358); non-UTF-8 / non-regular / >1 MiB reported, never raised (:341-349, C-05) | `tests/test_tweaks.py:388`, `:419`, `tests/test_setup.py:4285`, `:4315` |
| T-23-38 | low | mitigate | CLI uninstall strip at `setup.py:930` / `:1336` | `tests/test_setup.py:4258` |
| T-23-60 | high | mitigate | `tests/conftest.py:255` re-roots `setup._MYSHELLRC`; fingerprint `:125-152` | `tests/test_setup.py:4327`, `tests/test_sandbox.py:73` |
| T-23-61 | medium | mitigate | split-mode reader injected by the composition root in both front ends (`installer/post_install.py:91-97`) | `tests/test_setup.py:4372`, `:4384` |
| T-23-39 | high | mitigate | `installer/agent_settings.py:752-753` changed keys → `kept_changed`; `installer/app.py:672-695` names them | `tests/test_uninstall_e2e.py:734` |
| T-23-40 | medium | mitigate | `installer/app.py:716-719` per-tool `active_policies((bundle,))` + `sweep_policies`; `sweep_tweaks` only in full uninstall behind `decision.remove_tweaks` (`:1240-1241`) | `tests/test_app.py:6191` |
| T-23-62 | medium | mitigate | `installer/app.py:720-722` zsh removal sweeps the owned desktop-shell row (not on macOS) | `tests/test_app.py:6358`, `tests/test_policy_settings.py:201` (C-17) |
| T-23-41 | medium | mitigate | `installer/app.py:657-669` one `removal_change_lines` for the CLI preview and ConfirmUninstall (`installer/wizard_app.py:40`) | `tests/test_app.py:6134`, `tests/test_wizard_app.py:8956` |
| T-23-42 | low | mitigate | sanitized `Text` in the uninstall review | `tests/test_wizard_app.py:8984` |
| T-23-43 | high | mitigate | `scripts/container-e2e-verify.sh:84` `exec_tester`, `:995` `trap 'ct rm -f …' EXIT`, `:989` removal | harness self-tests in `tests/test_container_e2e_receipts.py`; live run in the audit trail |
| T-23-44 | medium | mitigate | `scripts/container-e2e-verify.sh:754` `TRACER_HOOK_FILES_MISSING`; the settings probe compares per-key values and lists left ledgers (C-16) | `tests/test_container_e2e_receipts.py:1056`, `:1030`, `:1160` |
| T-23-45 | medium | mitigate | `scripts/e2e-residue-allowlist.txt`: phase 23 added no entry (last change 4727d2f, 22-13); `.zshenv` is not allowlisted; every entry has a reason | `tests/test_container_e2e_receipts.py:853`, `:798` |
| T-23-SC | high | accept | no plan adds a package (AR-23-01) | `git diff aefd473^ HEAD -- pyproject.toml uv.lock`: only 51b0d29 (dev `pytest-xdist`/`execnet`) and 020c15f (`faulthandler_timeout`, config only) |

Zero sudo: no phase-23 module builds a sudo/pkexec/doas argv.
`tests/test_executors.py:150` and `:163` (AST over `installer/` + `setup.py`) pass. The only
`sudo` text is the pre-existing `apt-upgrade` alias body (`installer/tweaks.py:72-78`). That is
a string the user runs from their own shell, never an installer argv.

## Accepted Risks

| ID | Source | Sev | Risk | Why accepted | Upgrade path |
|----|--------|-----|------|--------------|--------------|
| AR-23-01 | T-23-SC | high | supply chain of npm/pip/cargo installs | No phase-23 plan adds or installs a host package. The lockfile change in the window is the dev-only `pytest-xdist` from 51b0d29, already recorded as AR-22-01 | Register in the phase that owns 51b0d29 if audited |
| AR-23-02 | T-23-57 | low | A pre-phase-23 receipt (`hooks={}`) unregisters nothing on removal, so its host registration stays | D-04 locks "recorded hosts only". The `≈` drift and RECONFIGURE record those hosts first. `shortcut:` at `installer/uninstall.py:300-302` | Record hosts for legacy receipts during refresh |
| AR-23-03 | REVIEW-FIX C-14 (CR-11) | low | No handoff line when a hook tool's executable is unproven (vendor self-upgrade moved it); the registration stays | Planner sign-off 7 (R1-40). The removal still succeeds. `shortcut:` at `installer/uninstall.py:305-308` | Print `codegraph uninstall --target … --keep-cli` once the receipt learns the moved path |
| AR-23-04 | REVIEW-FIX C-09 residual | low | The `omz-theme` claim and the installer-written `ZSH_THEME` line survive a full uninstall | Removing the line brings back the bare `%m%# ` prompt this phase fixed. Starship on/off/removal is symmetric | Restore the pre-install theme value on uninstall |
| AR-23-05 | T-23-02 shortcut | low | A host the user removed by hand is registered again while its marker dir remains | Recorded in the SPEC. `shortcut:` at `installer/postinstall.py:277-278` | Tell a CLI from a marker dir in `present_harnesses` |
| AR-23-06 | REVIEW-FIX C-19 by-design | low | A comment on the installer's own member line is removed with that member | The comment describes our key. User comments in a created file are now kept (`tests/test_agent_settings.py:1068`) | none |
| AR-23-07 | REVIEW-FIX C-18 residual | low | `herdr-integration` per-host retry is untested; no registry tool uses it yet | Phase 24 shape. Unregister still goes through the same closed target filter (T-23-01) | Test when a tool declares it |

## Unregistered Flags

None blocking. Every SUMMARY `## Threat Flags` section that exists (23-01, -03..-05, -07..-15)
maps to registered IDs or says "none". 23-02, 23-06 and 23-16 have no section. Their surface
(the splice engine, the ledger, the e2e probes) is covered by T-23-04..06, T-23-12..15, T-23-54/55
and T-23-43..45.

Review-fix surface checked here:
- C-02 adds a revert-path allowlist (`_agent_files`).
- C-04 adds the untrusted-ledger quarantine. Note that `receipts.untrusted_ledger` moves the file
  even when called from the read-only refresh pass (`installer/version_status.py:700`), by design.
- C-15 adds the non-blocking `O_NOFOLLOW` capped read (`installer/atomic.py:76-92`).
- C-08 adds the Stop gate (`installer/session.py:851-853`).

These add mitigations, not surface.

Observations (no threat ID, not blocking):
- `installer/tweaks.py:367` `bundle_marker_present` uses a blocking `read_bytes()`. If
  `~/.myshellrc` is a FIFO, the launch reads in `policy.py:535,541` and `omz.py:573` can hang.
  The alias strip itself refuses it through `read_capped`. This is availability only and needs
  a self-made FIFO.
- `installer/render.py:521-527` prints the CLI "Shell" lines with `markup=False` but without
  `sanitize_log_line`. The zsh path passes `_safe_executable` (no control chars) on the
  terminal-sync path. The shown `.zshenv` path comes from `ZDOTDIR`.

## Audit Trail

| Date | Auditor | Head | Result |
|------|---------|------|--------|
| 2026-11-07 | gsd-security-auditor (Claude) | a30bb2f | SECURED: 61 mitigated, 2 accepted, 0 open; 7 accepted residuals; 137 + 249 targeted tests passed; `make validate` exit 0 |
