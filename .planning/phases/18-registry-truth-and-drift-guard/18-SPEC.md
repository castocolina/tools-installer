# Phase 18: Registry truth and drift guard — Specification

**Created:** 2026-10-13
**Ambiguity score:** 0.15 (gate: ≤ 0.20)
**Requirements:** 11 locked

## Goal

Every registry entry matches its upstream release and this host. Pinned versions are bumped to the latest stable release, checksummed and dated. A weekly check opens a GitHub issue when upstream drifts, before a user hits the drift.

## Background

Scouted 2026-10-13:
- `installer/registry.toml` has 90 `[[tool]]` entries. Only 34 carry `# Verified`.
- There are 89 `github_release` methods but only 39 checksum lines.
- `model.py:668` keeps every non-structural key as an opaque param, so unknown keys such as draw.io's `cli_name` are accepted and ignored.
- The `managed-download` owner probe still exists: `install_ownership.py:83`, `model.py:57`, and the registry at lines 2721 and 2770.
- `make` targets launch the app with `uv run setup.py`, which puts the dev venv on PATH, so a dev-only ruff shadows the real one (D C1).
- `/usr/bin/java` on macOS counts as installed (C G1).
- `versions.py` fabricates versions from outputs like `-1` (B 15 WR-02).
- Audits C/D/E/F list 35 data-only fixes (9 + 7 + 11 + 8), and `drawio-cli` shares its `drawio` binary with `drawio-desktop`.
- There is no smoke run after an install, so a glibc-floor binary links "successfully" and then fails at runtime (D C6).

## Requirements

1. **Closed method keys (REG-01)**: Loading the registry rejects any method key outside that kind's closed key set, and draw.io's `cli_name` is honored.
   - Current: Unknown keys are kept as opaque params and silently ignored.
   - Target: Each kind has a closed key set (`METHOD_PARAMS`), and `load_tools` raises on any other key. `cli_name` is used when linking draw.io's CLI.
   - Acceptance: A fixture with `formula` on a `github_release` method fails to load with the tool id and key in the message. A method with only `kind` loads when the kind allows it. On macOS, draw.io's CLI link is named by its `cli_name`.

2. **Dated verification (REG-02)**: Every `[[tool]]` carries a `# Verified YYYY-MM-DD` line inside its own block, written when `make verify-registry` passes for that entry.
   - Current: 34 of 90 entries are dated.
   - Target: All entries are dated. A test enforces presence, a valid date and placement inside the block.
   - Acceptance: The test fails for a missing line, a future or malformed date, or a line placed between two blocks, and it passes on the shipped registry.

3. **Drift check (REG-03)**: `make verify-registry` checks each pinned `github_release`, `tarball` and `app` entry: the asset URL resolves, the archive member exists, the checksum matches, and a newer stable release is reported.
   - Current: Does not exist.
   - Target: It is a read-only command with a weekly scheduled CI job outside the PR gate. On drift, the job fails and opens or updates one GitHub issue listing the drifted entries. Kinds it cannot check (script, brew, native) are listed as "not checkable". With no network or under a rate limit, the run is "inconclusive" and opens no issue.
   - Acceptance: A fixture of the pre-fix difftastic asset template is reported as drifted. A second drift run updates the existing open issue instead of creating a new one. A network-failure fixture yields "inconclusive" with no issue call.

4. **Checksum or digest (REG-04)**: A release download is verified against the pinned checksum, otherwise against the GitHub API sha256 digest.
   - Current: 50 of 89 release downloads have no verification.
   - Target: Verification uses the pinned checksum, then the API digest. When neither is available, the install proceeds and the row and summary say "unverified" with the reason. A mismatch always fails the install.
   - Acceptance: A digest-match fixture installs. A digest-mismatch fixture fails with nothing linked. A no-digest fixture installs and is flagged "unverified".

5. **Smoke run (REG-05)**: A freshly installed binary is run once. An OSError, exit 126 or 127, or a loader error (e.g. `GLIBC_`) fails that method, and the ladder falls through to the next one.
   - Current: There is no smoke run.
   - Target: The default probe is `--version`, and an entry can declare its own smoke argv. When no method remains, the install fails without leaving a linked binary.
   - Acceptance: A fake binary that exits 127 falls through to the next method. With a single method, the install fails and `~/.local/bin/<bin>` does not exist.

6. **No dev venv at launch (REG-06)**: App launch entrypoints run without the dev venv on PATH.
   - Current: `uv run setup.py` exposes dev tools, so ruff resolves to the dev venv.
   - Target: Launch targets use `uv run --no-dev`, and `install.sh` matches. `make test` and `make validate` keep dev dependencies.
   - Acceptance: In a container, `make setup` resolves ruff's owner to its real installer. A Makefile test asserts `--no-dev` on the launch targets and not on test/validate.

7. **macOS stubs are not tools (REG-07)**: `/usr/bin/java` and `/usr/bin/git` alone never count as installed when the JDK or Command Line Tools are absent.
   - Current: The stub counts as present.
   - Target: The stub path is treated as not present, with a reason; a real JDK or CLT counts.
   - Acceptance: A fixture with only the java stub → not installed, with a reason. A fixture where `/usr/libexec/java_home` reports a JDK → installed. The same applies to git with and without CLT.

8. **No fabricated versions (REG-08)**: The version parser returns `None` rather than inventing a version.
   - Current: `-1` and similar outputs produce versions.
   - Target: `-1` gives `None`. Lazygit's `version=0.44.1, …` gives `0.44.1`. Procs' quoted output is unquoted before parsing.
   - Acceptance: A parametrized test over the audit fixtures produces the expected values.

9. **Audit data fixes (REG-09)**: All 35 data-only fixes from audits C, D, E and F are applied, and the `managed-download` probe is removed from code and registry.
   - Current: The fixes are unapplied, and the probe exists in 4 places.
   - Target: The fixes are applied as written in each audit's "Registry fixes (data only)" section. Sublime's `member` is skipped because Phase 17 already fixed it. The probe and its registry references are deleted.
   - Acceptance: Each fix maps to a passing test or a verify-registry pass. `rg managed-download installer/` returns nothing.

10. **One drawio row (REG-10)**: `drawio-cli` is removed, and `drawio-desktop` has `audience = "both"`.
    - Current: Two rows share the `drawio` binary.
    - Target: One row. A stale `drawio-cli` id in settings is ignored without error.
    - Acceptance: The registry has no `drawio-cli`. Loading settings that name it raises nothing, and the existing install shows under drawio-desktop.

11. **Pins bumped and verified (new, user decision)**: Every pinned version is bumped to the latest stable release with a matching checksum and a fresh `# Verified` date.
    - Current: Several pins lag upstream (e.g. draw.io 31 vs 32).
    - Target: A version is bumped only when verify-registry passes on the new one. If an asset was renamed or removed, the old pin stays and is reported. Entries without a pin are unchanged.
    - Acceptance: verify-registry reports no "newer stable" for any entry it could check, and each bumped entry carries that day's `# Verified` date.

## Boundaries

**In scope:**
- The closed key sets and load-time rejection; `cli_name` honored
- The `# Verified` rule and its test; `make verify-registry`; the weekly job with GitHub issue reporting
- Checksum → digest → "unverified" verification order, with mismatch failing the install
- The install-time smoke run with fall-through
- `--no-dev` launch
- The macOS java/git stub rule
- Version parser fixes
- The 35 data fixes, `managed-download` removal, `drawio-cli` removal
- Pin bumps

**Out of scope:**
- Install receipts, `ToolState` and health marks — Phase 19
- New script params `paths`/`remove`/`update` and `writable_prefix` — Phase 22 (the closed key sets here gain those keys there)
- Code-level gaps listed in the audits that are not data — their phases per target-architecture §8.1
- Auto-fixing drift (bot PRs) — the user chose issue-only reporting
- A latest-version source for script/SDKMAN tools — cut (C G7)

## Constraints

- verify-registry needs network and uses `gh` when it is authenticated, falling back to unauthenticated calls (60/h). It never runs in the PR gate.
- Zero sudo. Tests use a scratch HOME. macOS behavior is verified through CI fixtures (no local macOS).
- The weekly job reports only; it never modifies the repo.

## Acceptance Criteria

- [ ] Unknown method key → load error naming the tool and key; a kind-only method loads when allowed
- [ ] draw.io's CLI link uses `cli_name` (macOS fixture)
- [ ] The `# Verified` test fails on missing, future, malformed or misplaced lines and passes on the shipped registry
- [ ] verify-registry flags the pre-fix difftastic fixture; a repeat drift updates the open issue; a network failure is "inconclusive" with no issue
- [ ] Unverifiable kinds are listed as "not checkable"
- [ ] Digest match installs; digest mismatch fails with nothing linked; no digest installs and shows "unverified"
- [ ] A smoke failure (exit 127) falls through; a single failing method leaves no linked binary
- [ ] `make setup` in a container resolves ruff's real owner; the Makefile test confirms `--no-dev` only on launch targets
- [ ] The java and git stubs alone → not installed; a real JDK or CLT → installed
- [ ] The version parser fixtures (`-1`, `version=`, quoted) produce the expected values
- [ ] All 35 data fixes are applied and each is backed by a test or a verify-registry pass; `managed-download` is absent from `installer/`
- [ ] No `drawio-cli` row; a stale settings id is ignored without error
- [ ] verify-registry reports no "newer stable" for checkable entries; bumped entries carry the new date

## Edge Coverage

**Coverage:** 22/22 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | A key valid for another kind is rejected (AC 1) |
| empty | R1 | ✅ covered | A kind-only method loads when allowed (AC 1) |
| ordering | R1 | ⛔ dismissed | TOML key order has no meaning |
| adjacency | R2 | ✅ covered | A line between blocks does not count (AC 3) |
| empty | R2 | ✅ covered | Future or malformed dates fail (AC 3) |
| ordering | R2 | ⛔ dismissed | Placement is covered by adjacency |
| adjacency | R3 | ✅ covered | script/brew/native entries listed as not checkable (AC 5) |
| empty | R3 | ✅ covered | No network → inconclusive, no issue (AC 4) |
| ordering | R3 | ✅ covered | An existing open issue is updated, not duplicated (AC 4) |
| concurrency | R4 | ⛔ dismissed | One installer process per host |
| (added) mismatch | R4 | ✅ covered | A mismatch always fails (AC 6) |
| unclassified | R5 | 🧪 backstop | A tool without `--version` uses its declared smoke argv, else an exec/loader check (held-out edge test) |
| unclassified | R6 | ✅ covered | Test/validate keep dev deps (AC 8) |
| unclassified | R7 | ✅ covered | A real JDK/CLT counts; git included (AC 9) |
| unclassified | R8 | ✅ covered | Fixture table (AC 10) |
| adjacency | R9 | ✅ covered | Fixes are applied before bumps; verify-registry passes on the final state (AC 11, 13) |
| empty | R9 | ⛔ dismissed | A fixed list of 35 has no empty case |
| ordering | R9 | ✅ covered | Sublime's member is already done in Phase 17 and skipped |
| concurrency | R9 | ⛔ dismissed | Data edits, no runtime concurrency |
| unclassified | R10 | ✅ covered | A stale id is ignored; the install shows under desktop (AC 12) |
| adjacency | R11 | ✅ covered | A renamed asset keeps the old pin and is reported (R11 target) |
| empty | R11 | ✅ covered | Unpinned entries are unchanged |
| ordering | R11 | ⛔ dismissed | Bumps are independent per entry |

## Prohibitions (must-NOT)

**Coverage:** 4/4 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT install a binary whose checksum or digest mismatches | R4 | resolved | test: the mismatch fixture fails with nothing linked |
| MUST NOT let verify-registry or the weekly job modify `registry.toml` or push commits | R3 | resolved | test: the job runs with read-only contents permission; the command leaves the working tree unchanged |
| MUST NOT run verify-registry in the PR gate | R3 | resolved | test: the workflow test asserts it runs only on `schedule`/`workflow_dispatch` |
| MUST NOT write `# Verified` for an entry verify-registry did not pass | R2, R11 | resolved | test: dates written by the tool match only passing entries |

Canon referral: keeping the `gh` token out of logs and issue bodies is canon secret handling, owned by `/gsd-secure-phase` and not minted here.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Truth, bumps, weekly drift issue |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Data-only fixes; code gaps routed to their phases |
| Constraint Clarity | 0.78  | 0.65 | ✓      | Network/rate limit, outside the PR gate, read-only job |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | 13 pass/fail criteria |
| **Ambiguity**      | 0.15  | ≤0.20| ✓      | |

## Interview Log

| Round | Perspective     | Question summary | Decision locked |
|-------|-----------------|------------------|-----------------|
| 1 | Researcher      | What does "Verified" mean for 56 undated entries? | A date written when verify-registry passes (mechanical) |
| 1 | Researcher      | No checksum and no API digest? | Install with an "unverified" flag; a mismatch always fails |
| 1 | Researcher      | What happens on weekly drift? | The job fails and opens/updates one GitHub issue |
| 2 | Simplifier      | Bump pinned versions? | Yes: latest stable, verified and dated |
| 2 | Boundary Keeper | Apply the 35 audit data fixes as written? | Yes, all of them |
| 3 | Failure Analyst | Edge table and prohibitions | Accepted as proposed |

---

*Phase: 18-registry-truth-and-drift-guard*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 18 — implementation decisions (how to build what's specified above)*
