---
phase: 18-registry-truth-and-drift-guard
plan: "08"
subsystem: registry
tags: [registry, audit, skill-lifecycle, github-release]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: audit C/D baseline from plan 18-06
    plan: "06"
provides:
  - Audit E and F data fixes with per-fix tests
  - Complete 35-row audit fix ledger (C1–F8)
affects: [18-15, verify-registry]

actuals:
  tokens: 45000
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns: ["test_audit_fix_e* / test_audit_fix_f* pin registry drift fixes"]

key-files:
  created: []
  modified:
    - installer/registry.toml
    - tests/test_registry.py
    - tests/test_skill_lifecycle.py

key-decisions:
  - "E8 applied after read-only installer.sh confirmed macOS dest=/Applications/kitty.app"
  - "F4 pi status probe applied; loader accepted DietrichGebert/ponytail match"
  - "E9 wezterm macOS app optional-not-applied; E1/E3 already-done per plan"

patterns-established:
  - "Audit fix ledger rows E1–E11 and F1–F8 complete the phase-18 35-item table"

requirements-completed: [REG-09]

coverage:
  - id: E-F-registry
    description: Audits E and F data fixes applied or dispositioned with tests
    requirement: REG-09
    verification:
      - kind: unit
        ref: tests/test_registry.py -k audit_fix_e
        status: pass
      - kind: unit
        ref: tests/test_registry.py -k audit_fix_f
        status: pass
      - kind: unit
        ref: make test
        status: pass
    human_judgment: false

duration: 120min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 08 Summary

**Registry audits E and F: native glab fallbacks, JetBrains arm64 tarball, draw.io Linux checksums, macOS kitty script, and AI-tool comment/probe corrections with a complete 35-row ledger.**

## Performance

- **Duration:** ~120 min
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Applied audit E fixes E2, E4–E8, E10, E11 with eight `test_audit_fix_e*` tests; dispositioned E1, E3, E9 per plan.
- Applied audit F fixes F1–F8 with eight `test_audit_fix_f*` tests; F4 pi probe loaded successfully.
- Full `make validate && make test` green (3681 passed).

## Task Commits

1. **Task 1: audit E fixes 1–11** — `763cff0`
2. **Task 2: audit F fixes 1–8** — `af17ea1`

**Plan metadata:** (this commit) `docs(18-08): plan summary`

## TDD RED evidence (trimmed)

Task 1: `uv run pytest tests/test_registry.py -q --no-cov -k audit_fix_e` — 8 failed (missing arm64 tarball, opencode args, jless/broot arch, draw.io checksum, glab natives, pi uninstall text, macOS kitty script).

Task 2: `uv run pytest tests/test_registry.py -q --no-cov -k audit_fix_f` — 8 failed (graphify uninstall/CWD note, codegraph v1.6.2 facts, rtk 0.52.0 facts, ponytail claude removal/pi probe, superpowers marketplace lines, matt-pocock default, opengsd Node 24, puppeteer CfT note).

## Verify results

- Task 1: `uv run pytest tests/test_registry.py -q --no-cov -k audit_fix_e` — 8 passed; `uv run pytest tests/test_registry.py tests/test_resolve.py tests/test_model.py tests/test_ownership.py -q --no-cov` — pass.
- Task 2: `uv run pytest tests/test_registry.py -q --no-cov -k audit_fix_f` — 8 passed; `uv run pytest tests/test_registry.py tests/test_skill_lifecycle.py tests/test_model.py -q --no-cov` — pass.
- Final: `make validate && make test` — pass.

## E8 precondition (installer.sh, read-only)

```
dest='~/.local'
[ "$OS" = "macos" ] && dest="/Applications"
dest="$dest/kitty.app"
```

## Audit fix ledger

| Fix | Status | Evidence |
|-----|--------|----------|
| C1 | applied | `test_audit_fix_c1_volta_script_covers_macos` |
| C2 | applied | `test_audit_fix_c2_podman_brew_is_split` |
| C3 | applied | `test_audit_fix_c3_docker_dnf_installs_the_cli` |
| C4 | applied | `test_audit_fix_c4_uv_does_not_modify_path` |
| C5 | applied | `test_audit_fix_c5_sdkman_comment_records_5_23_2` |
| C6 | applied | `test_audit_fix_c6_colima_recommends_docker` |
| C7 | optional-not-applied | fnm macOS script installs under `~/Library/Application Support/fnm` (path with space); not verified without macOS host |
| C8 | applied | `test_audit_fix_c8_brew_script_is_split_by_arch` |
| C9 | superseded | `# Verified` dates enforced by `verified` key from plan 18-01 (`test_every_shipped_tool_declares_a_verified_date`) |
| D1 | applied | `test_audit_fix_d1_difftastic_asset_carries_the_version`; optional musl method not applied (glibc floor deferred to plan 18-09 smoke) |
| D2 | applied | `test_audit_fix_d2_delta_macos_release_is_arm64_only`; optional musl method not applied (same as D1) |
| D3 | applied | `test_audit_fix_d3_gh_has_a_macos_release`; verify-registry pass in 18-15 |
| D4 | applied | `test_audit_fix_d4_gitui_uses_the_org_repo_and_ships_macos` |
| D5 | applied | `test_audit_fix_d5_tealdeer_uses_the_org_repo` |
| D6 | applied | `test_audit_fix_d6_ruff_has_a_uv_tool_method_after_its_releases` (github_release → uv-tool → brew intentional) |
| D7 | applied | `test_audit_fix_d7_hyperfine_uses_the_musl_assets`; verify-registry pass in 18-15 |
| E1 | already-done | Phase 17 sublime Linux `member`/`bin_name`; live re-pin deferred to plan 18-15 |
| E2 | applied | `test_audit_fix_e2_jetbrains_toolbox_ships_linux_arm64`; verify-registry pass in 18-15 |
| E3 | already-done | codex script already declares `CODEX_NON_INTERACTIVE=1` |
| E4 | applied | `test_audit_fix_e4_opencode_script_skips_path_edits` |
| E5 | applied | `test_audit_fix_e5_jless_linux_release_is_amd64_only` |
| E6 | applied | `test_audit_fix_e6_broot_macos_release_is_arm64_only` |
| E7 | applied | `test_audit_fix_e7_drawio_linux_release_is_checksummed`; macOS re-pin in plan 18-15 |
| E8 | applied | `test_audit_fix_e8_kitty_script_covers_macos` (installer.sh macOS root quoted above) |
| E9 | optional-not-applied | cask already covers macOS; pinned `app` adds bump obligation for no new platform |
| E10 | applied | `test_audit_fix_e10_glab_has_native_fallbacks` |
| E11 | applied | `test_audit_fix_e11_pi_uninstall_text_does_not_assume_pnpm` |
| F1 | applied | `test_audit_fix_f1_graphify_records_the_cwd_scope_and_uninstall` |
| F2 | applied | `test_audit_fix_f2_codegraph_comment_records_1_6_2` |
| F3 | applied | `test_audit_fix_f3_rtk_comment_records_0_52_0` |
| F4 | applied | `test_audit_fix_f4_ponytail_probes_pi_and_documents_claude_removal` |
| F5 | applied | `test_audit_fix_f5_superpowers_has_one_claude_route` |
| F6 | applied | `test_audit_fix_f6_matt_pocock_default_is_the_plugin_route` |
| F7 | applied | `test_audit_fix_f7_opengsd_notes_node_24` |
| F8 | applied | `test_audit_fix_f8_puppeteer_records_cft_linux_arm64` |

## Deviations from Plan

- Removed `jetbrains-toolbox` from `NO_LINUX_ARM64` after E2 arm64 tarball shipped.
- Updated existing kitty ladder tests (`test_kitty_has_no_linux_download_fallback`, `test_kitty_cask_blocks_a_too_old_macos_version`, `test_kitty_linux_script_declares_vendor_bin_dir`) for the macOS script method.
- Updated superpowers registry/skill-lifecycle tests after F5 removed the obra marketplace Claude route.

## Issues Encountered

None blocking.

## User Setup Required

None.

## Next Phase Readiness

Plan 18-15 verify-registry live checks can proceed for D3, D7, E2 member, and E7 checksum assets.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
