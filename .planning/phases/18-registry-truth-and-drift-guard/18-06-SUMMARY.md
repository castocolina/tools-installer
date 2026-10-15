---
phase: 18-registry-truth-and-drift-guard
plan: "06"
subsystem: registry
tags: [registry, audit, drawio, owner-probes, github-release]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: verified key and METHOD_PARAMS from plan 18-01
provides:
  - Single draw.io catalog row (drawio-desktop, audience both, 89 tools)
  - Dead managed-download owner probe removed from installer/
  - Audit C and D data fixes with per-fix tests or documented disposition
affects: [18-08, 18-15, 18-12]

actuals:
  tokens: 22000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns: ["audit fix ledger with test or reason per row"]

key-files:
  created: []
  modified:
    - installer/registry.toml
    - installer/model.py
    - installer/install_ownership.py
    - tests/test_registry.py
    - tests/test_install_ownership.py
    - tests/test_version_cache.py

key-decisions:
  - "Intel macOS podman has no install method; allowlisted in MACOS_ARM64_ONLY alongside container"
  - "ruff declares requires = [\"uv\"] so uv-tool satisfies the shipped uv-tool drift test"
  - "hyperfine Linux assets switched to musl after live tarball listing showed strip=1 member layout"

patterns-established:
  - "test_audit_fix_* pins each applied audit C/D registry change"

requirements-completed: [REG-09, REG-10]

coverage:
  - id: D1
    description: One draw.io row; drawio-desktop audience both; 89 tools
    requirement: REG-10
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_drawio_desktop_is_the_only_drawio_row
        status: pass
    human_judgment: false
  - id: D2
    description: Stale drawio-cli cache key harmless; install under drawio-desktop
    requirement: REG-10
    verification:
      - kind: unit
        ref: tests/test_version_cache.py#test_stale_drawio_cli_cache_entry_is_ignored
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_existing_drawio_install_shows_under_drawio_desktop
        status: pass
    human_judgment: false
  - id: D3
    description: managed-download owner probe removed from installer/
    requirement: REG-09
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_removed_owner_probe_is_rejected_at_load
        status: pass
      - kind: other
        ref: "rg -n managed-download installer/ (exit 1, no output)"
        status: pass
    human_judgment: false

duration: 90min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 06 Summary

**Registry truth for draw.io and audits C/D: one desktop row, no dead owner probe, sixteen audit rows applied or dispositioned with tests.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Removed `drawio-cli` and the `managed-download` owner probe; `drawio-desktop` is `audience = "both"` with 89 catalog tools.
- Applied audit C fixes C1–C6 and C8; dispositioned C7, C9; applied audit D fixes D1–D7 with registry tests.
- Full `make validate && make test` green (3652 passed).

## Task Commits

1. **Task 1: draw.io row and probe removal** — `333ec24`
2. **Task 2: audit C data fixes** — `fe8af6c`
3. **Task 3: audit D data fixes** — `55c83b3`

**Plan metadata:** (this commit) `docs(18-06): plan summary`

## TDD RED evidence (trimmed)

Task 1 (before registry/probe edits): `uv run pytest … -k "drawio or stale or owner_probe"` failed on missing `test_drawio_desktop_is_the_only_drawio_row`, stale cmd duplicate pin, and `managed-download` still in `OWNER_PROBES`.

Task 2: `uv run pytest -k audit_fix_c` failed until volta/podman/docker/uv/sdkman/colima/brew registry edits landed.

Task 3: `uv run pytest -k audit_fix_d` failed on difftastic `{ver}` templates, gh macOS zip method, gitui repo, ruff `uv-tool`, and hyperfine musl assets.

## Verify results

- Task 1: `uv run pytest tests/test_registry.py tests/test_version_cache.py tests/test_install_ownership.py -q --no-cov -k "drawio or stale or owner_probe"` — 11 passed; `rg -n managed-download installer/` — exit 1.
- Task 2: `uv run pytest tests/test_registry.py -q --no-cov -k audit_fix_c` — 7 passed.
- Task 3: `uv run pytest tests/test_registry.py -q --no-cov -k audit_fix_d` — 7 passed; `make validate && make test` — pass.

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
| D3 | applied | `test_audit_fix_d3_gh_has_a_macos_release`; live member check deferred to plan 18-15 |
| D4 | applied | `test_audit_fix_d4_gitui_uses_the_org_repo_and_ships_macos` |
| D5 | applied | `test_audit_fix_d5_tealdeer_uses_the_org_repo` |
| D6 | applied | `test_audit_fix_d6_ruff_has_a_uv_tool_method_after_its_releases` (github_release → uv-tool → brew intentional) |
| D7 | applied | `test_audit_fix_d7_hyperfine_uses_the_musl_assets`; listing `curl -fsSL …/hyperfine-v2.0.0-x86_64-unknown-linux-musl.tar.gz \| tar -tz` showed `…/hyperfine`; cite plan 18-15 live member check and plan 18-18 pass1 hyperfine row when those run |

## Deviations from Plan

- Added `podman` to `MACOS_ARM64_ONLY` so `test_every_tool_resolves_at_least_one_method_on_each_platform` matches audit C2 (no Intel Mac Homebrew podman).
- Added `requires = ["uv"]` on `ruff` so `test_shipped_uv_tool_tools_require_uv` passes after D6.
- Updated existing pins: `test_volta_resolves_*` macOS ladder, `test_gh_*` / `test_gitui_*` macOS ladders, hyperfine gnu→musl assertion, dropped `ruff` from macOS github_release-only loop test.
- Large `tests/test_registry.py` edits applied via Python script (Cursor `StrReplace` truncated the file twice); content matches plan intent.

## Issues Encountered

None blocking. Hyperfine D7 listing used release v2.0.0; tests pin rendered names at ver `1.19.0` per plan.

## User Setup Required

None.

## Next Phase Readiness

Audits E/F (plan 18-08), pin conversion and live verify-registry (18-15) can proceed on this registry baseline.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
