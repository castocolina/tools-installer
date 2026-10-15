---
phase: 18-registry-truth-and-drift-guard
plan: "15"
subsystem: registry
tags: [registry, verify-registry, pinned-url, drawio, sublime, gh-cli]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: verify_registry --write, per-member checks, pin bump flow (plans 18-12, 18-13, 18-17)
provides:
  - Five templated app/tarball pins with shared version + sha256
  - Live bump of drawio-desktop and sublime with refreshed verified dates
  - Invariant tests for pinned-url shape and app-pin bump member matching
affects: [18-18]

actuals:
  tokens: 55000
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "app/tarball pins use {ver} + version + sha256; pinned_url renders upstream asset names"
    - "Sublime bumps via --candidate; draw.io via GitHub latest in --write"
    - "_pinned_finding_member aligns bump edits with app/cli member paths"

key-files:
  created: []
  modified:
    - installer/registry.toml
    - tests/test_registry.py
    - installer/verify_registry.py
    - tests/test_verify_registry.py

key-decisions:
  - "Sublime stable build 4215 from stable_update_check (2026-10-15); explicit --candidate sublime=4215"
  - "gh macOS zip uses strip=0 so member gh_{ver}_macOS_{arch}/bin/gh matches zip layout (write-run-2 drift fix)"

patterns-established:
  - "Registry pin invariants enforced by test_no_pinned_url_carries_a_literal_version and render tests"

requirements-completed: [REG-02, REG-03, REG-04, REG-09]

coverage:
  - id: D1
    description: "Five pinned methods templated with {ver}, version, sha256; no literal versions in pin URLs"
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_no_pinned_url_carries_a_literal_version
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_pinned_methods_render_their_upstream_asset_names
        status: pass
    human_judgment: false
  - id: D2
    description: "Live verify-registry --write bumped drawio and sublime; read-only final check clean"
    requirement: REG-02
    verification:
      - kind: other
        ref: ".e2e-artifacts/verify-registry/final-check.exit (EXIT 0); no 'newer stable release' in final-check.log"
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py (11-test precondition + github_app_pin regression)
        status: pass
    human_judgment: false
  - id: D3
    description: "ROADMAP SC3 measured unverified github_release set is gron + jless only"
    requirement: REG-09
    verification:
      - kind: other
        ref: final-check.log Unverified at install section
        status: pass
    human_judgment: false

duration: 120min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 15: Registry truth and drift guard (live pins)

**Shipped registry pins are templated, bumped to current stable assets, and pass a read-only verify-registry run with no newer-stable drift on checkable entries.**

## Performance

- **Duration:** ~120 min (includes live network verify)
- **Tasks:** 2 (+ 1 checker fix commit between write attempts)
- **Commits:** 4 (feat, fix, chore, docs)

## Task Commits

1. **Task 1: template five literal pins** — `595756a`
2. **Checker fix: app pin bump member matching** — `c30d277`
3. **Task 2: live --write + gh strip fix** — `429b383`
4. **Plan metadata** — (this commit) `docs(18-15): plan summary`

## TDD RED evidence (Task 1)

Before registry templating, `uv run pytest tests/test_registry.py -q --no-cov -k "pinned or literal_version or sublime_is_single_universal"` failed on:

- `test_no_pinned_url_carries_a_literal_version` — 5 violations (drawio v31.0.2 literals; sublime build 4200 literals)
- `test_pinned_methods_render_their_upstream_asset_names` — `KeyError: 'version'` on drawio methods
- `test_sublime_is_single_universal_app_with_cask_fallback` — url lacked `{ver}`

## Task 2 precondition (11 passed)

```
uv run pytest tests/test_verify_registry.py -q --no-cov -k "shared_url_with_different_members or ..."
...........  [100%]
```

## Live run evidence (gitignored logs)

| Artifact | Exit | Notes |
|----------|------|-------|
| `write-run-1.log` / `.exit` | 1 | `RegistryWriteError: missing candidate hash for drawio-desktop` (app pin bump looked up wrong member); fixed in `c30d277`, retried |
| `write-run-2.log` / `.exit` | 1 | Bumps applied; residual **Drift** on gh macOS zip members (`strip = 1` stripped path prefix); fixed `strip = 0` in registry, read-only gate passes |
| `final-check.log` / `.exit` | 0 | No `newer stable release` lines |

**Stable build read:** `curl stable_update_check` → `latest_version` **4215** (2026-10-15).

**Write-run-2 Notes (trimmed):**

```
- sublime: newer stable: no release source  (×3 methods — expected per plan 18-17)
- bumped drawio-desktop 31.0.2 -> 32.4.1
- bumped sublime 4200 -> 4215
```

**Bumped pin hashes (registry after write):**

| Tool | version | Methods |
|------|---------|---------|
| drawio-desktop | 32.4.1 | mac arm64 sha256 `0ec4d3cd03df339cdbaac892a57bc924de8f6cbea3d5c85f1c3e8c9fca41f4ec`; mac amd64 `5587c2a5bb730195c8b967757fef0ea5db9cb12748cf71773cdce57712ab77b9` |
| sublime | 4215 | mac zip `a0263f36660f13981bb25b05e968681429ce5f67134876cd9032ffa82e1904d5`; linux x64 `c153f418d3ab26b90ecce8c02a82e4e961025ed7a65f7e25060a5457d43e88d9`; linux arm64 `d314665a4272f33551503432372a34516dbb5a9a12dce2a47042c1942f66ee79` |

**verified dates:** `--write` set `verified = 2026-10-15` on every tool that passed in write-run-2 (57 `verified` line updates in `git diff`; each tool appears under `## Passed` in `write-run-2.log` / `final-check.log`).

## Read-only pass gate

```bash
grep -qx 'EXIT 0' .e2e-artifacts/verify-registry/final-check.exit
! grep -q 'newer stable release' .e2e-artifacts/verify-registry/final-check.log
```

## Audit ledger citations (final-check `Passed`)

- **D3 gh macOS member:** `- gh .../gh_2.102.0_macOS_amd64.zip gh_2.102.0_macOS_amd64/bin/gh (macos/amd64)` and arm64 analogue
- **D4 gitui macOS assets:** `- gitui .../gitui-mac.tar.gz gitui (macos/arm64)` and `.../gitui-mac-x86.tar.gz (macos/amd64)`
- **D7 hyperfine musl member:** `- hyperfine .../hyperfine-v2.0.0-aarch64-unknown-linux-musl.tar.gz hyperfine (arch/arm64, ...)` and x86_64 musl line
- **E2 jetbrains-toolbox arm64 member:** `- jetbrains-toolbox .../download?platform=linuxARM64&code=TBA bin/jetbrains-toolbox (arch/arm64, ...)`
- **E7 draw.io checksum file (AppImage targets on v32.4.1):** `- drawio-desktop .../drawio-arm64-32.4.1.AppImage (...)` and x86_64 AppImage line (GitHub `Files-SHA256-Hashes.txt` digest path)

## Unverified at install (ROADMAP SC3)

From `final-check.log`:

```
- gron method 0/1 (github_release): four 0.7.1 tgz assets
- jless method 0/1 (github_release): three v0.9.0 zip assets
- jetbrains-toolbox / vscode: latest-style URLs (expected)
```

**github_release tools in this section:** only `gron` and `jless` (Ledger L-18-02).

## Verify commands

- Task 1: `uv run pytest tests/test_registry.py -q --no-cov -k "pinned or literal_version or sublime_is_single_universal"` — pass
- Task 2 gate: `grep -qx EXIT\ 0 final-check.exit && ! grep newer\ stable\ release final-check.log` — pass
- Full: `make validate && make test` — pass (3867 passed, coverage 95.29%)

## Deviations from Plan

- **Extra commit `c30d277`:** `_finding_for_pinned_method` must use `app`/`cli` member for `kind = app` pins (drawio bump); regression test `test_github_app_pin_bump_matches_findings_by_app_cli_member`.
- **write-run-2 exit 1:** gh macOS `strip = 1` caused false member drift; data fix `strip = 0` + `test_audit_fix_d3_gh` assertion; read-only rerun is the pass gate (exit 0).

## Issues Encountered

None blocking after the two fixes above. No token was logged or pasted.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
