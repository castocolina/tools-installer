---
phase: 25
slug: lean
status: secured
asvs_level: 1
block_on: high
threats_total: 30
threats_closed: 29
threats_open: 0
threats_open_nonblocking: 0
audited_at: 2026-11-15
audited_head: efbb30db
---

# Phase 25: Security Audit

Retroactive verification of the eleven PLAN `<threat_model>` registers (T-25-01..T-25-29 and the
shared T-25-SC) against the code at HEAD `efbb30db` (phase range `d0d88257..efbb30db`, 66 commits,
including the post-review commits `1d2a9faf..efbb30db` that ran after the 25-11 gate). Config:
ASVS L1, block_on high; the four focus areas (deletions, composition move, run-log bound, zero
sudo) were read at L2 depth. Source stayed read-only; no installer, container or `make` target
ran. Independent checks (scratchpad scripts, `python3 -I`, AST only):

- `setup.py` old vs new: every remaining route function (`main`, `_run_doctor`, `_run_fix`,
  `_run_uninstall`, `_teardown_cli`, `_run_schedule`, `_verify_and_clean`, `_run_interactive_wizard`)
  is AST-identical to `d0d88257` (one docstring id removed).
- The 18 functions moved to `installer/compose.py` are AST-identical to the pre-phase `setup.py`
  except: `_schedule_context` checkout is `parent.parent` (correct for `installer/`), `_DiskProbe`
  loses the write-only `_unit_dir`, `_build_services` types `**options` as `Unpack[_InstallOptions]`.
- 38 of 41 top-level nodes of the pre-phase `wizard_app.py` are AST-identical in their new modules
  (`ConfirmUninstall`, `MutationLock`, `GlobalsAudited` among them); `DoctorScreen` differs only by
  the deleted test seam `_BodyStatic` -> `Static`; `UninstallScreen` differs only by the 25-10
  helper extraction, and all 14 helpers in `installer/uninstall_review.py` match the old method
  bodies after the `self._x` -> parameter rename.
- Comment-only commits `02702536`, `a6c441fd`, `8d76128f`, `1bb31e00`: every production `.py`
  file AST-identical (docstrings ignored) to its parent.
- Test patches: 0 `setattr(setup, "<name>")` on a name `compose.py` reads; 0 leftover
  `vars(wizard_app)`.
- Suppressions over the whole phase diff: `noqa`/`type: ignore`/`nosec`/`pragma: no cover` +0/-0,
  `pyright: ignore` +4/-5 (each a `setup._execute_inputs` -> `compose._execute_inputs` pair).
  `tests/test_cli.py` and `tests/test_install_sh.py` byte-identical. `pyproject.toml`, `uv.lock`
  unchanged.
- Pytest sandbox (`uv run pytest -n 8 --no-cov`): sandbox, reachability, model, update, receipts,
  version_cache, execute_screen, registry, uninstall_e2e, post_install, engine, setup, cli
  (1604 passed) and policy*, schedule*, doctor, uninstall, wizard_app (1328 passed); exit 0, so
  the session `real_home_untouched` fingerprint was unchanged.

## Verdict

**SECURED** - 29/30 closed (26 `mitigate` verified in code, 2 `accept` logged below), 1 open
below the `high` threshold (T-25-02, low, non-blocking), 0 unregistered flags. `threats_open: 0`.

## Focus areas

- **Deletions.** `host_setup` is gone from `METHOD_KINDS` (`model.py:25`) and `OWNER_PROBES`
  (`model.py:142`); a row declaring it fails `unknown method kind` (`model.py:625`). The only path
  that replayed a vendor command (`update._perform`'s `host_setup_update_argv` -> `runner([pnpm, ...])`)
  was deleted, and a pnpm-owned tool with no node method is refused before any argv
  (`update.py:372`, a hint carrying `--ignore-scripts`) with a raising backstop
  (`update.py:425`). The sensitive-action machinery (`SensitiveActionScreen`,
  `SENSITIVE_PROMPTS`, `confirm_sensitive_action`) had no user: the prompt table was empty since
  23.2 and every action already did `del confirm`; `set_login_shell` only returns the `chsh` text
  (`post_install.py:111-118`, `:275-277`). The checksum prompt path is intact:
  `ChecksumMismatchScreen`, `ask_from_worker`, `PromptOpen`, `_DISMISSAL_SKIP`
  (`execute_screen.py:73-187`, `:916-937`); `checksum_policy` still flows through `InstallFn` /
  `_with_force` (`session.py`). No deleted symbol has a remaining reference (rg over installer,
  setup.py, scripts, tests).
- **Composition move.** Route guards (run lock in `_run_uninstall` and the headless install,
  `_launch_repairs` before reads, `clean_rc_duplicates` confirm, the no-TTY exit 2) are unchanged
  (AST check above). The sandbox loops over both `setup` and `installer.compose`
  (`tests/conftest.py:303-324`); every compose home constant (`_DEFAULT_BIN_DIR`, `_MYSHELLRC`,
  `_SHELLRC`, `_ZSHRC`, `_RC_PATHS`, `_DAEMON_PLIST_PATH`, `_LINUX_DAEMON_UNIT_DIR`,
  `_ENVIRONMENT_D_DIR`, `compose.py:111-135`) is a Path or list of Paths the loop re-roots;
  `test_no_compose_home_constant_points_at_the_real_home` (`tests/test_sandbox.py:286`) passes.
- **Run-log bound.** `RunLog` (`execute_screen.py:317`) passes `max_lines=RUN_LOG_MAX_LINES`
  (5000) to `RichLog`; the pre-layout queue evicts oldest entries past 5000 lines and counts them;
  `_apply` counts trims; the notice is a separate `Static` (`#execute-log-dropped`) outside the
  trimmed buffer. The only writer is `write_log` (`:512-516`). The newest lines survive: the
  completion test asserts the last line is `run crashed` (`tests/test_execute_screen.py:5513-5531`).
  Residual: one single write larger than 5000 lines is held whole in the queue until layout
  (bounded by that write).
- **Zero sudo.** No `sudo`/`pkexec`/`doas` argv in `installer/` or `setup.py`; the one added
  occurrence is moved message text (`schedules_screen.py:110`); `ELEVATION_COMMANDS`
  (`model.py:546`) unchanged.

## Threat Verification

| ID | Category | Sev | Disposition | Evidence | Verdict |
|----|----------|-----|-------------|----------|---------|
| T-25-01 | DoS | medium | mitigate | `tests/test_reachability.py:196` `test_every_installer_module_is_reachable_from_an_entry_point` (pass); deleted modules have no importer | CLOSED |
| T-25-02 | Repudiation | low | mitigate | `test_the_exemptions_are_live` (`:311`) and relative-import edge (`:270`) present; `test_every_string_keyed_callable_table_is_listed` and the dispatch-table test were deleted in `bdd0073d` after the gate | OPEN (non-blocking) |
| T-25-03 | Tampering | medium | mitigate | `model.py:25`, `:142` closed sets without the kind/probe; `tests/test_model.py:1306`, `:1323` | CLOSED |
| T-25-04 | DoS | medium | mitigate | `tests/test_receipts.py:691`, `tests/test_version_cache.py:145` (pass) | CLOSED |
| T-25-05 | Elevation | high | mitigate | `update.py:372` refusal, `:425` `UpdateError`; `tests/test_update.py:1539` asserts `calls == []` (renamed in `ecf53ecc` from `test_update_refuses_host_setup_pnpm_cleanly`, body unchanged) | CLOSED |
| T-25-06 | Elevation | medium | accept | See accepted risks; `post_install.py:275-277`, `.claude/architecture.md:773` | CLOSED |
| T-25-07 | Tampering | medium | mitigate | `model.py:600-604` retired-key `ValueError`; `tests/test_model.py:1366` | CLOSED |
| T-25-08 | DoS | medium | mitigate | `execute_screen.py:73`, `:97`, `:142`, `:187`; `tests/test_execute_screen.py:656` (pass) | CLOSED |
| T-25-09 | DoS | medium | mitigate | one commit per symbol (`2538a134`..`56532e6b`); 0 remaining references incl. strings; reachability test passes | CLOSED |
| T-25-10 | Repudiation | low | mitigate | `tests/test_registry.py:55` helper, `:2091` `test_shipped_registry_requires_all_resolve` | CLOSED |
| T-25-11 | Tampering | high | mitigate | `tests/conftest.py:303-324` loops `setup` and `installer.compose`; `tests/test_sandbox.py:286`; `real_home_untouched` `conftest.py:183` | CLOSED |
| T-25-12 | Tampering | high | mitigate | `tests/compose_patch.py:9` patches every binding module, raises on none; independent AST audit: 0 setup-only patches of compose-read names | CLOSED |
| T-25-13 | Elevation | medium | mitigate | `tests/test_reachability.py:352` `test_compose_is_prompt_free_and_nothing_imports_setup` (renamed from `test_composition_lives_in_compose_not_setup`; both declared asserts kept) | CLOSED |
| T-25-14 | Repudiation | medium | mitigate | `tests/test_cli.py`, `tests/test_install_sh.py` byte-identical over the phase; 25-11-SUMMARY D-12 guard (25 tests) | CLOSED |
| T-25-15 | DoS | medium | mitigate | `execute_screen.py:317-410` `max_lines=5000`, bounded queue; `tests/test_execute_screen.py:5393`, `:5457` | CLOSED |
| T-25-16 | Repudiation | low | mitigate | `dropped_notice` `:305`, `_report` inside `write`; tests `:5386`, `:5437`, `:5495`, `:5513` | CLOSED |
| T-25-17 | DoS | medium | mitigate | split modules import `wizard_app` only under `TYPE_CHECKING`; `tests/test_reachability.py:440` | CLOSED |
| T-25-18 | Tampering | medium | mitigate | independent AST check: `ConfirmUninstall` (`modals.py:69`), `MutationLock` (`mutation_lock.py:20`) identical to pre-phase | CLOSED |
| T-25-19 | Repudiation | medium | mitigate | `tests/test_schedules_view.py:592` `monkeypatch.setattr(schedules_screen, ...)`; 0 `vars(wizard_app)` | CLOSED |
| T-25-20 | DoS | medium | mitigate | `TYPE_CHECKING`-only imports (`policies_screen.py:23`, `schedules_screen.py:35`); `tests/test_reachability.py:440` | CLOSED |
| T-25-21 | Tampering | medium | mitigate | policies/schedules nodes AST-identical; policy*/schedule* suites pass | CLOSED |
| T-25-22 | Tampering | high | mitigate | `UninstallScreen` diff limited to the 25-10 extraction (verified equivalent); `tests/test_uninstall_e2e.py`, `tests/test_wizard_app.py` pass | CLOSED |
| T-25-23 | Tampering | medium | mitigate | `doctor_messages.py:31-45` `generation` field; `doctor_screen.py:323`, `:711` supersede check | CLOSED |
| T-25-24 | DoS | medium | mitigate | `doctor_screen.py:56`, `uninstall_screen.py:96` under `TYPE_CHECKING`; `tests/test_reachability.py:440` | CLOSED |
| T-25-25 | Tampering | medium | mitigate | `02702536`, `a6c441fd` AST-identical per production file (independent run) | CLOSED |
| T-25-26 | Repudiation | low | mitigate | Task 1 diff (`02702536`) is comment/docstring-only (AST-identical) | CLOSED |
| T-25-27 | Tampering | high | mitigate | `uninstall_review.py` 14 helpers match old bodies; `_tool_entry`, `_with_failure` stay on the class; call sites pass `self._painted.get(tool.id)` etc. | CLOSED |
| T-25-28 | Repudiation | high | mitigate | suppressions paired over the whole phase (+4/-5 `pyright: ignore`, 0 others); CLI tests byte-identical; 25-11-SUMMARY vulture multiset 194 -> 177. Post-gate `bdd0073d` deletes 8 reachability asserts in a named commit (see T-25-02) | CLOSED |
| T-25-29 | Tampering | high | mitigate | 25-11-SUMMARY lists only validate/test/git/rg; no host `make` target or sudo; `real_home_untouched` held on this audit's runs | CLOSED |
| T-25-SC | Tampering | low | accept | See accepted risks; `git diff --stat d0d88257..efbb30db -- pyproject.toml uv.lock` empty | CLOSED |

## Open Threats

### Open (non-blocking - severity below `high`)

| ID | Category | Sev | Mitigation expected | Files searched |
|----|----------|-----|---------------------|----------------|
| T-25-02 | Repudiation | low | `test_every_string_keyed_callable_table_is_listed` and the dispatch-table target test; both removed by `bdd0073d` ("the module graph already covers"). The exemption and relative-import halves remain. With no dispatch list left there is no stale entry to widen the ignore set, so the vector is largely gone, but the declared mitigation is absent | `tests/test_reachability.py` |

Suggested action: record T-25-02 as an accepted risk (the dispatch-table half) or restore the
inventory test; either closes it on re-run.

## Accepted Risks Log

| ID | Risk | Rationale | Owner |
|----|------|-----------|-------|
| T-25-06 | A future post-install action could change system state with no consent path, since the consent machinery was retired | No action has asked since 23.2; `set_login_shell` only returns the reviewed `chsh` text and never runs it (`post_install.py:111-118`, `:275-277`); `.claude/architecture.md:773` requires a future consent-needing action to add a reviewed path | phase 25 |
| T-25-SC | Package supply chain | The phase installs and adds no package; `pyproject.toml` and `uv.lock` unchanged over `d0d88257..efbb30db` | phase 25 |

## Unregistered Flags

None. All eleven SUMMARY `## Threat Flags` sections report none; the post-review commits
(`1d2a9faf..efbb30db`) add no new network, file-access or exec surface (comment edits, the
`unit_dir` dead-field drop, the `InstallFn` rename, the run-log queue fixes covered by T-25-15/16).

**threats_open:** 0

## T-25-02 disposition (orchestrator, 2026-11-16)

Accepted risk for the dispatch-table half. The two removed tests froze the names of string-keyed tables; a table
whose target module or callable is deleted already fails at import or registry load (`load_tools` rejects an
unknown method kind or owner probe, and every dispatch site is exercised by its route tests), and the module-graph
reachability test now seeds only from the launchers (WR-01 fix, 1d2a9faf). The exemption and relative-import
guards stay. Re-add a table inventory if a future table is keyed by user data rather than registry values.
