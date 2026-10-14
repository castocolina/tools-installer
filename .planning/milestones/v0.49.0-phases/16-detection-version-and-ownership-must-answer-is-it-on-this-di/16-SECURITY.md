---
phase: "16"
slug: detection-version-and-ownership-must-answer-is-it-on-this-di
status: verified
threats_open: 0
asvs_level: 1
created: "2026-10-10"
---

# Phase 16 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Block threshold: `high`. Audit was read-only (code and test evidence, no source changes).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| filesystem -> ownership/version detection | Paths under brew Cellar, sdkman, skill dirs, `skills-lock.json` are untrusted names | file and directory names |
| registry.toml -> argv/shell | Registry-supplied `args`, harness/via/match values reach subprocess and `curl \| sh` | argv strings |
| rc files -> Doctor/guard rewrite | User shell rc text is parsed and, on confirm, rewritten in place | rc file bytes |
| rc text / paths -> Textual/Rich UI | Foreign text is rendered in modals and the detail pane | display strings |
| harness CLI -> skills status | External CLIs queried for pack presence | subprocess stdout |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation (evidence) | Status |
|-----------|----------|-----------|----------|-------------|------------------------|--------|
| T-16-01 | Spoofing | `_collect_candidates` location branch | medium | mitigate | Location-derived candidates are checked against the managed set in `installer/ownership.py`; covered by plan 16-01 ownership tests | closed |
| T-16-02 | Tampering | update.py sdkman branch | medium | mitigate | sdkman version is read from a file under the sdkman dir only; no shell-out (plan 16-01 tests) | closed |
| T-16-03 | Elevation | MUTATION_GRADE reach for sdkman | low | accept | See Accepted Risks Log | closed |
| T-16-04 | Tampering | `_skills_lock_skills` path join | high | mitigate | `_SKILL_NAME_RE` at `installer/skill_lifecycle.py:19`; `.`/`..` and non-matching names rejected at `skill_lifecycle.py:335-336`; `../evil` test at `tests/test_skill_lifecycle.py:679` | closed |
| T-16-05 | Elevation | registry-supplied argv | high | mitigate | argv only in code table `HARNESS_CLI_STATUS` (`skill_lifecycle.py:125`), looked up by key at `:294`, `:377`; registry supplies only closed-set names | closed |
| T-16-06 | Spoofing | substring matching | medium | mitigate | Exact/anchored match via `_SKILL_MATCH_RE` and fullmatch in `skill_lifecycle.py` | closed |
| T-16-07 | Denial of Service | hanging harness CLI | medium | mitigate | Harness CLI runs through `run_query` with its timeout | closed |
| T-16-08 | Tampering | `find_duplicate_path_lines` strip set | high | mitigate | `_PathLine.simple` (`installer/rcclean.py:84`, set at `:330`) required by the strip filter (`:407`); compound-shape tests return `[]` | closed |
| T-16-09 | Repudiation | Doctor diagnosis | medium | mitigate | Every writer record carries `text`, `index`, `refusal`, `block_owner` (`rcclean.py:535-549`) so the diagnosis names the line and the reason | closed |
| T-16-10 | Denial of Service | `_split_unquoted` on pathological input | low | accept | See Accepted Risks Log | closed |
| T-16-11 | Information Disclosure | tests reading real HOME | medium | mitigate | `tests/conftest.py:15-29` snapshots the real HOME at import and guards against reads/writes | closed |
| T-16-12 | Denial of Service | `.bashrc.d` glob | low | mitigate | Bounded glob over a single directory (read-only scan) | closed |
| T-16-13 | Tampering | `_brew_cellar_formula` -> `brew upgrade` argv | high | mitigate | `_BREW_NAME_RE` fullmatch AND membership in `inventory.brew_formulae` (`installer/ownership.py:133`, `:514`); argv is a Python list; malformed-line tests at `tests/test_ownership.py:1137`, `:1175` | closed |
| T-16-14 | Spoofing | planted file under the brew Cellar | medium | mitigate | Same gate: a planted name must also be in `brew list` (`ownership.py:514`); left-behind Cellar test `tests/test_ownership.py:2090` | closed |
| T-16-15 | Elevation | cached off-policy record authorising mutation | medium | mitigate | Cached records only seed display; mutation re-derives ownership live (plan 16-05) | closed |
| T-16-16 | Tampering | `_sdkman_current_version`/`_version_file` | low | mitigate | Read-only reads under the sdkman candidate dir | closed |
| T-16-17 | Elevation | probing an absolute path | low | accept | See Accepted Risks Log | closed |
| T-16-18 | Tampering | by_harness instruction lines | medium | mitigate | Lines are rendered as text and never executed (`skill_lifecycle.py:248-270`) | closed |
| T-16-19 | Spoofing | host presence via a disk marker | low | accept | See Accepted Risks Log | closed |
| T-16-20 | Repudiation | unverifiable host lists | medium | mitigate | Per-host answers carry an explicit status (direct vs service match) rather than a bare list | closed |
| T-16-21 | Tampering | `guard_path_writers` rewrite | high | mitigate | Only `guardable` records chosen (`installer/shellrc.py:1145-1152`); `_guard_refusal` accepts only a single-directory prepend (`rcclean.py:465-487`); output is `path_export_guard(record.directory)` with directory from the managed set (`shellrc.py:1200`); lines never deleted; foreign-block lines refused (`rcclean.py:529-538`) | closed |
| T-16-22 | Tampering | stale scan -> write at the wrong index | high | mitigate | Per-line text re-verification (`shellrc.py:1165-1175`) plus `_snapshot_matches` after backup creation with backup rollback (`:1204-1209`) | closed |
| T-16-23 | Tampering | symlinked rc file write-through | high | mitigate | `_path_hazard` (`shellrc.py:828`) refuses symlinks and non-regular files before any read, called at `:1154` | closed |
| T-16-24 | Denial of Service | data loss without recovery | high | mitigate | `backup_precondition` (`shellrc.py:935`) and create-exclusive backup `O_EXCL` (`:989`); mode preserved on write (`:1212`); differing backup refuses the whole file | closed |
| T-16-25 | Elevation | shell injection via directory text | medium | mitigate | Directory comes from the managed-dir set, not the foreign line (`shellrc.py:1200`) | closed |
| T-16-26 | Tampering | repair path | medium | mitigate | `repair` only bypasses the `is_installed` short-circuit (`installer/engine.py:104`, `:132`); ladder, checksums, smoke checks unchanged | closed |
| T-16-27 | Spoofing | false "broken" from an unreadable inventory | medium | mitigate | `pnpm_globals is None` yields no claim (`installer/status.py:106`, `ownership.py:1017`, `version_status.py:672`) | closed |
| T-16-28 | Elevation | `_script` args injection | high | mitigate | Load-time `_SCRIPT_ARG_RE` allowlist (`installer/model.py:135`, enforced `:726-738`) plus `shlex.quote` per element (`installer/executors.py:364`); `;` rejected by `tests/test_model.py:614` | closed |
| T-16-29 | Tampering | kitty vendor script (curl \| sh) | medium | accept | See Accepted Risks Log | closed |
| T-16-30 | Denial of Service | GUI launch from worker | medium | mitigate | `args = ["launch=n"]` declared and pinned (`installer/registry.toml:2532`, `tests/test_registry.py:1418`) | closed |
| T-16-31 | Repudiation | unconfirmed edits | high | mitigate | One `ConfirmGuardFile` modal per file (`installer/wizard_app.py:666`, `:2179`); the guard runs only from its callback; pilot tests assert zero writes on `n` | closed |
| T-16-32 | Tampering | markup injection from rc text into the modal | medium | mitigate | Modal text built with `Text(...)` / `Text.assemble`, not markup (`wizard_app.py` ConfirmGuardFile) | closed |
| T-16-33 | Tampering | stale records at confirm time | high | mitigate | `guard_path_writers` re-verifies line text and snapshot at write time (`shellrc.py:1165-1209`) | closed |
| T-16-34 | Tampering | `skills` cache decode | low | mitigate | Closed vocabulary validated on load; malformed entries dropped (`installer/version_cache.py:150-160`) | closed |
| T-16-35 | Denial of Service | slow harness CLI | medium | mitigate | `run_query` timeout and a separate worker group | closed |
| T-16-36 | Information Disclosure | cache contents | low | accept | See Accepted Risks Log | closed |
| T-16-37 | Elevation | `reapply_post_install` | medium | mitigate | Only reached from explicit selection (`installer/execute_screen.py:637`); `confirm: ConfirmSensitiveAction \| None` with `None` skipping sensitive actions (`engine.py:200-210`) | closed |
| T-16-38 | Tampering | repair of a broken tool | medium | mitigate | Same as T-16-26 (`engine.py:132`) | closed |
| T-16-39 | Repudiation | silent no-op | low | mitigate | Preflight and progress name every current tool; `Install 0 tools` unreachable (plan 16-13 test) | closed |
| T-16-40 | Repudiation | reason/availability drift | low | mitigate | Parity test ties `unavailable_reason is None` to `platform_could_support` across four platforms | closed |
| T-16-41 | Tampering | markup in reason text | low | accept | See Accepted Risks Log | closed |
| T-16-42 | Tampering | markup in active_path text | low | mitigate | `rich.markup.escape` on path-bearing segments (`installer/catalog_tui.py:739`, `:743`, `:747`, `:751`); cells use `Text` | closed |
| T-16-43 | Repudiation | `u` silently doing nothing | low | mitigate | Every `u` branch sets a status line (plan 16-15 tests) | closed |
| T-16-44 | Tampering | accidental mutation during proof | high | mitigate | 16-16 used read-only probes only; host rc checksums identical before/after (`host-before.sha` vs `host-after.sha`; only the installer's own prune log changed) | closed |
| T-16-45 | Tampering | `strip_lines` on a `then`/`do` line (16-17, WR-02) | high | mitigate | `installer/rcclean.py::_judge_line` marks a then/do-prefixed segment non-`simple` (`_LEADING_THEN_DO`), so `find_duplicate_path_lines` skips it and the guard refusal agrees; `tests/test_rcclean.py::test_then_prefixed_path_line_is_not_a_strip_candidate` | closed |
| T-16-46 | Tampering | guarding heredoc data as a statement (16-17, IN-01) | medium | mitigate | `installer/rcclean.py::_path_line_targets` skips heredoc bodies (opener validated on code text via `_code_text`); `tests/test_rcclean.py::test_heredoc_body_is_not_a_path_writer` | closed |
| T-16-47 | Information Disclosure | refusal text naming paths (16-17, WR-01/IN-14) | low | accept | See Accepted Risks Log | closed |
| T-16-48 | Denial of Service | unreadable rc.d entry aborting the scan (16-17, IN-06) | low | mitigate | `installer/locations.py::path_scan_rc_paths` treats an `OSError` from `is_file()` as "not a file" and skips the entry; `tests/test_locations.py::test_path_scan_skips_an_unreadable_bashrc_d_entry` | closed |
| T-16-SC (x19) | Tampering | npm/pip/cargo installs (plans 16-01..16-19) | high | accept | See Accepted Risks Log | closed |
| T-16-49 (16-18) | Spoofing | handoff lines read as one sequence (WR-04) | medium | mitigate | `installer/skill_lifecycle.py::_filtered_install_lines` emits a framing header and a `SKILL_HARNESS_LABELS` label per host block; `tests/test_skill_lifecycle.py::test_superpowers_install_on_claude_only_host_is_framed_and_labeled` | closed |
| T-16-50 (16-18) | Spoofing | wrong or `unknown` owner label on two-copy hosts (IN-10) | low | mitigate | `installer/ownership.py::resolve_ownership` treats a non-active location-proven candidate as a shadow, so native/OS attribution still resolves; `tests/test_ownership.py::test_non_active_script_location_shadows_instead_of_blocking_os_package` | closed |
| T-16-51 (16-18) | Tampering | probe declaration silently ignored or collapsed (IN-17, IN-18) | low | mitigate | `installer/skill_lifecycle.py::_install_state_status` answers `unknown` for an unknown `match` (`INSTALL_STATE_FILES` closed table) and `installer/model.py::_parse_status_probes` raises on a repeated harness; `tests/test_skill_lifecycle.py::test_install_state_probe_honors_match`, `tests/test_model.py::test_duplicate_status_probe_harness_fails_at_load` | closed |
| T-16-52 | Repudiation | status text claims certainty on stale data (IN-15) | low | mitigate | `installer/catalog_tui.py::action_update_tool` qualifies stale-current rows with "current as of the last check"; `tests/test_catalog_tui.py::test_update_on_stale_current_qualifies_the_last_check` | closed |
| T-16-53 | Elevation of Privilege | none introduced (16-18) | low | accept | See Accepted Risks Log | closed |
| T-16-49 (16-19) | Tampering / Repudiation | `_judge_line` skip hiding a persistent writer (NR-02) | medium | mitigate | `installer/rcclean.py::_judge_line` keeps an `export PATH=...` line with a command suffix as a writer (`_EXPORT_WORD`); `tests/test_rcclean.py::test_export_path_with_extra_assignments_is_a_persistent_writer` | closed |
| T-16-50 (16-19) | Tampering | guarding or stripping an `export PATH=... EXTRA=1` line (NR-02) | medium | mitigate | Same record is non-`simple`, so `_guard_refusal` answers the compound text and `find_duplicate_path_lines` skips it; `tests/test_rcclean.py::test_export_path_with_extra_assignments_is_a_persistent_writer` | closed |
| T-16-51 (16-19) | Spoofing (misleading UI) | post-apply Doctor text (NR-01) | low | mitigate | `installer/wizard_app.py::_tui_guidance` applies the ordered `_POST_APPLY_REWRITES` built from `installer/guidance.py::GUARD_ENTER_HINT`/`SAFE_FIX_ENTER_HINT`; `tests/test_wizard_app.py::test_doctor_drops_inert_enter_hint_after_apply` | closed |

16-18 and 16-19 both numbered T-16-49..T-16-51; the plan in parentheses tells them apart.

*Status: open · closed · open — below high threshold (non-blocking)*
*Total register rows: 75 (T-16-01..T-16-53 with the 16-19 qualifiers = 56, plus one T-16-SC per plan = 19).*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-16-01 | T-16-03 | sdkman updates stay in the existing mutation grade; no new reach | plan 16-01 | 2026-10-10 |
| AR-16-02 | T-16-10 | Quoted-split on pathological rc text is bounded by file size; local single-user tool | plan 16-03 | 2026-10-10 |
| AR-16-03 | T-16-17 | Probing a registry-declared absolute path is read-only | plan 16-06 | 2026-10-10 |
| AR-16-04 | T-16-19 | A disk marker for host presence can be spoofed only by the user themself | plan 16-07 | 2026-10-10 |
| AR-16-05 | T-16-29 | kitty vendor script has the same trust model as uv, bun, volta, claude (official HTTPS channel) | plan 16-10 | 2026-10-10 |
| AR-16-06 | T-16-36 | Cache holds host names and pack ids in the user's own cache dir | plan 16-12 | 2026-10-10 |
| AR-16-07 | T-16-41 | Reason text comes from trusted registry/code constants, rendered via `Text` | plan 16-14 | 2026-10-10 |
| AR-16-08 | T-16-SC | No plan installs a package; verified `git diff` shows no change to `pyproject.toml`/lock files | plans 16-01..16-19 | 2026-10-14 |
| AR-16-09 | T-16-47 | Guard and refusal texts name only the rc path and its `.tools-installer.old` sibling the user already owns; no file content is echoed | plan 16-17 | 2026-10-14 |
| AR-16-10 | T-16-53 | No sudo, no new executors, no shell strings; the by_harness handoff lines remain display-only and execute nothing | plan 16-18 | 2026-10-14 |

Residual note (not a threat, not counted): review finding IN-01 (`installer/rcclean.py:283`) can treat a heredoc body line that looks like a plain PATH prepend as guardable. The rewrite still goes through the per-file confirm modal, the exact-text recheck, the exclusive backup and the no-delete rule, and the replacement is the managed `path_export_guard`, so the impact is a changed line inside a generated file the user confirmed, with a recoverable backup. Below the `high` block threshold. Recommend fixing with WR-01.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-10 | 60 | 60 | 0 | Claude Code (secure-phase, inline) |
| 2026-10-14 | 65 | 65 | 0 | pi (17-12 re-audit, gap plan 16-17) |
| 2026-10-14 | 75 | 75 | 0 | pi (17-12 re-audit, gap plans 16-18 and 16-19) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-10
