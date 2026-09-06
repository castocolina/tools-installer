---
phase: 08-ai-tier-catalog-expansion-uv-tool-executor
plan: 03
subsystem: catalog
tags: [registry, github_release, checksums, rtk, arch-split]

requires:
  - phase: 08-ai-tier-catalog-expansion-uv-tool-executor
    provides: "08-02's ai-tier tripwire baseline (13)"
provides:
  - rtk as a checksum-verified tier="ai" catalog entry with a brew fallback
affects: [08-04]

actuals:
  tokens: 24000
  tasks: 2
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Arch-gated Linux github_release split (mirrors puppeteer/gnu-bash precedent): two os/arch-scoped methods instead of one unscoped asset template, when upstream ships materially different builds per Linux arch"

key-files:
  created: []
  modified:
    - installer/registry.toml
    - tests/test_registry.py

key-decisions:
  - "rtk's Linux release assets are asymmetric (musl static build for amd64, gnu dynamic build for arm64) -- declared as two separate arch-gated github_release methods rather than one template that would 404 on one architecture."
  - "The genuine Homebrew formula rtk (confirmed the same upstream project via formulae.brew.sh matching homepage/description/version 0.48.0) is an ADDITIONAL fallback after the locked github_release method, not a replacement -- REQ-rtk-github-release mandates the checksum-verified method exists, not that it be the only one."
  - "rtk added to CHECKSUM_FILE_VERIFIED, not SIDECAR_VERIFIED -- rtk's checksum value is the literal string \"checksums.txt\", which would fail SIDECAR_VERIFIED's {asset}-template substring assertion."

patterns-established: []

requirements-completed:
  - REQ-rtk-github-release

coverage:
  - id: D1
    description: "rtk appears as a tier=\"ai\" catalog entry with three github_release methods (macOS universal, Linux amd64 musl, Linux arm64 gnu) plus a brew fallback, every github_release method's repo pinned exactly to rtk-ai/rtk"
    requirement: REQ-rtk-github-release
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_rtk_installs_via_checksum_verified_github_release_with_brew_fallback"
        status: pass
    human_judgment: false
  - id: D2
    description: "the two Linux methods resolve the correct asset per architecture (musl for amd64, gnu for arm64), not merely a github_release kind match"
    requirement: REQ-rtk-github-release
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_rtk_linux_methods_are_arch_gated_by_the_real_musl_gnu_asset_split"
        status: pass
    human_judgment: false
  - id: D3
    description: "rtk resolves via github_release and brew even on immutable Linux (Bazzite) -- a download kind is never gated on immutability"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_rtk_resolves_via_download_and_brew_even_on_immutable_linux"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_rtk_macos_method_is_arch_unrestricted"
        status: pass
    human_judgment: false
  - id: D4
    description: "the registry comment records the musl/gnu split finding and the brew-formula-is-the-same-project confirmation"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_rtk_entry_records_the_musl_gnu_split_and_brew_confirmation"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-06
status: complete
---

# Phase 8 Plan 3: rtk Catalog Entry Summary

**`rtk` ("Rust Token Killer") added as a checksum-verified `tier="ai"` catalog entry with a real arch-gated musl/gnu Linux split and a confirmed-same-project brew fallback.**

## Performance

- **Duration:** 25 min
- **Completed:** 2026-09-06
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `rtk`: `id="rtk"`, `category="dev"`, `cmd="rtk"`, `priority="P1"`, `audience="ai"`, `tier="ai"`, four methods:
  1. Universal macOS `github_release`: `asset="rtk-{arch.machine}-apple-darwin.tar.gz"`.
  2. Linux amd64 `github_release` (`os=["debian","arch","fedora"]`, `arch=["amd64"]`): `asset="rtk-{arch.machine}-unknown-linux-musl.tar.gz"`.
  3. Linux arm64 `github_release` (same `os`, `arch=["arm64"]`): `asset="rtk-{arch.machine}-unknown-linux-gnu.tar.gz"`.
  4. `brew` fallback: `formula="rtk"`.
  All three `github_release` methods carry `repo="rtk-ai/rtk"`, `checksum="checksums.txt"`, `member="rtk"`, `strip=0`.
- Dated comment records the live GitHub Releases API check (tag `v0.48.0`), the musl/gnu asymmetry finding, the bare-binary tarball layout (all three tarballs personally verified live via `tar -tzf` across this phase's review cycles), the `develop`-not-`main` default-branch note, and the brew-formula-same-project confirmation (`formulae.brew.sh/api/formula/rtk.json`, version `0.48.0` match).
- Five new tests: entry-shape/kind-order/repo-pin, per-arch asset selection (not just kind membership), macOS arch-unrestricted resolution, immutable-Linux (Bazzite) resolution bonus, and comment-substring locality.
- `rtk` added to `CHECKSUM_FILE_VERIFIED` (the literal-filename checksum regression set — not `SIDECAR_VERIFIED`, whose test would fail on `rtk`'s literal `"checksums.txt"` value).
- `test_registry_includes_requested_installable_entries`'s floor-check set extended with `"rtk"`.
- `ai` tier tripwire updated from 13 to 14.
- `make validate && make test`: **1248 passed** (up from 1243), 99.40% coverage, 0 lint/type/security findings.

## Task Commits

1. **Task 1: `rtk` registry entry** + **Task 2: Extend the installable-entries floor check** — `54c40fe` (feat, single commit — Task 2 is a one-line floor-check addition that landed together with Task 1's green state)

## Files Created/Modified
- `installer/registry.toml` — `rtk`'s `[[tool]]` block (four methods) + dated comment
- `tests/test_registry.py` — five new tests, `CHECKSUM_FILE_VERIFIED` addition, floor-check extension, tier tripwire bump

## Decisions Made

- The musl/gnu Linux asset asymmetry is handled with two arch-gated methods (mirroring the existing `puppeteer`/`gnu-bash` precedent), not one unscoped template.
- `brew` is an additional fallback after the locked `github_release` ladder, never a substitute — `REQ-rtk-github-release` only mandates the checksum-verified method exists.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 9/12 — circuit breaker] Direct-execution fallback continuing the systemic cross-AI backend outage**
- **Found during:** Wave 3 (no cross-AI dispatch attempted this wave — the systemic outage was already confirmed across 08-01 and 08-02's combined 5 consecutive identical failures)
- **Issue:** Same `Error: Service temporarily unavailable due to resource pressure` pattern observed across the prior two waves.
- **Fix:** Executed both of this plan's tasks directly in this orchestrator session. No plan content was altered.
- **Verification:** `make validate && make test` both pass (1248 passed, 99.40% coverage).
- **Committed in:** `54c40fe` (task commit, fallback explicitly disclosed)

---

**Total deviations:** 1 (execution-channel fallback only; zero content deviation from the reviewed plan)
**Impact on plan:** None — the plan's own content was already finalized through three cross-AI review cycles before this ran.

## Issues Encountered

Cross-AI execution (opencode) remained unavailable (systemic backend outage, same as 08-01/08-02); resolved via the documented direct-execution fallback.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`rtk` is fully wired and tested. Wave 4 (`08-04-PLAN.md`: `recommends` wiring across the four agent hosts + Tier-3 disposable-container verification) can now proceed — `rtk`, `graphify`, and `codegraph` all exist as real catalog tools, satisfying the dependency 08-04's `recommends` wiring needs.

---
*Phase: 08-ai-tier-catalog-expansion-uv-tool-executor*
*Completed: 2026-09-06*
