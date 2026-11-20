# Phase 32: Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.18 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

Five pending tools are onboarded through the tool-onboarding skill, each with an install, detection, update and removal route that runs without sudo, without an interactive login and without damaging user data.

## Background

- None of the five has an entry in `installer/registry.toml` today (`rg 'xcode|awscli|bruno|gh-stack|playwright' installer/registry.toml` finds nothing). Their pending todos are under `.planning/todos/pending/`; the research is in `.planning/research/SUMMARY.md`.
- Live facts (2026-11-19, read-only): `@playwright/mcp@0.0.85` exists on npm and npm's latest is `0.0.86`; `github/gh-stack` exists and is not archived; Bruno's latest release is `v4.3.0` with AppImage assets `bruno_4.3.0_x86_64_linux.AppImage` and `bruno_4.3.0_arm64_linux.AppImage`, and the Homebrew cask `bruno` is at 4.3.0; Homebrew's `awscli` formula is at 2.41.1.
- Owner decisions 2026-11-16: Xcode CLT is detected and the exact command is handed off; AWS CLI uses the official user-scope script first with brew as the fallback; Playwright MCP registers the pinned server and fixes the Flatpak Chrome path; the `bru` CLI is out of scope; a write into `~/.claude/settings.json` asks for consent first (ONB-15).
- Every entry fits an existing method kind (`script`, `brew`, `cask`, `github_release` raw asset, `bun`); no new method kinds (REQUIREMENTS out of scope).
- Phase 27's skill supplies the macOS app rule (`~/Applications`, CLI in `~/.local/bin`) that Bruno's macOS route follows.
- Research flags for discuss: the AWS CLI installer's gpg prerequisite, gh-stack's extension directory under a scratch `GH_CONFIG_DIR`, and a Playwright MCP headless launch smoke in a Fedora/Bazzite container.

## Requirements

1. **Xcode CLT detect and hand off (ONB-11)**: On macOS the installer detects the Command Line Tools; when missing, the row shows them missing with the exact `xcode-select --install` command for the user to run; no executor runs it and Uninstall offers no removal.
   - Current: no entry.
   - Target: a detect-only entry gated to macOS.
   - Acceptance: a fixture host without the tools shows the row missing with the exact command text; a grep test finds no executor path that spawns `xcode-select --install`; the removal plan for the entry is empty and the Uninstall screen lists no action for it.

2. **AWS CLI v2 (ONB-12)**: AWS CLI v2 installs through the official user-scope `install.sh` with gpg verification kept and no `--system`, falls back to brew `awscli` when that route is unavailable (a narrow validated preference ranks the script before brew on every host) *(amended 2026-11-19, 32 D-04)*, updates with `aws update`, and an uninstall never touches `~/.aws`.
   - Current: no entry.
   - Target: a `script` method (Linux and macOS user scope) plus a `brew` fallback, an `update` argv and `paths` that exclude `~/.aws`.
   - Acceptance: a container install through the script leaves a runnable `aws` with gpg verification run (the install fails closed when gpg is missing and the fallback is offered); the entry's argv contains no `--system`; after an uninstall in a container a seeded `~/.aws` file is byte-identical.

3. **Bruno (ONB-13)**: Bruno installs through the cask on macOS and through a digest-verified AppImage for the host architecture on Linux; the `bru` CLI is not installed.
   - Current: no entry.
   - Target: a `cask` method (macos) following the SKILL-04 app rule and a per-architecture `tarball` raw asset method carrying `version` and `sha256` *(amended 2026-11-19, 32 D-07: `github_release` takes no pin fields; `raw` becomes an allowed key on `tarball`)*.
   - Acceptance: registry tests load the entry; the sha256 of each AppImage equals the release's GitHub digest (`make verify-registry` read-only passes); no `bru` binary or package appears in any method; the macOS method places the bundle in a user location or the entry's `# Verified` comment says why not.

4. **gh-stack (ONB-14)**: gh-stack installs with `gh extension install https://github.com/github/gh-stack`, is detected as present through its installed manifest file, updates with `gh extension upgrade stack`, is removed by deleting its receipt-proven install folder, and an unauthenticated `gh` never blocks or prompts *(amended 2026-11-19, 32 D-10, D-11, needs confirmation: `gh extension list`, `upgrade` and `remove` need a login (live test); only `install` works without one)*.
   - Current: no entry.
   - Target: an entry whose install, detect, update and remove argv are exactly those commands, with `gh` in `requires`.
   - Acceptance: in a scratch `GH_CONFIG_DIR` with no login, the install, detect, update and remove steps complete or report cleanly with no prompt (the children run with stdin closed); the argv strings match the four commands exactly.

5. **Playwright MCP registration (ONB-15)**: Playwright MCP is registered in each agent host present as a server pinned to an exact `@playwright/mcp` version (`0.0.85`, 32 D-13) run through `bunx`, never overwriting an existing `playwright` server entry; on Bazzite the Flatpak Chrome path is exported when the wrapper exists; a write into `~/.claude/settings.json` asks for consent first.
   - Current: no entry; the research pinned `0.0.85`, and npm's latest is `0.0.86` as of 2026-11-19 (discuss picks the pin and records why).
   - Target: an `ai`-tier entry using the existing agent-host registration route, plus the Bazzite path export.
   - Acceptance: a scratch-HOME test with an existing `playwright` entry leaves it byte-identical and reports it kept; with none, the pinned entry is written to each present host only; the Flatpak path export appears only when the wrapper file exists; the `~/.claude/settings.json` write path asks for consent (a test with consent denied writes nothing).

## Boundaries

**In scope:**
- Five registry entries with their dated `# Verified` comments, detection, update and removal routes, and tests.
- Container checks for the AWS CLI script route and the Playwright MCP launch smoke.
- *Amended 2026-11-19 (32 D-01, D-04, D-07, D-09, D-14):* small parameter extensions to existing method kinds (a closed hand-off name and a fixed-argv install option on `script`; `raw` as an allowed key on `tarball`), the narrow AWS-script-over-brew preference, and per-host MCP config writers.

**Out of scope:**
- Running `xcode-select --install`, `softwareupdate` or `installer -target /` in any executor — zero-sudo rule.
- The `bru` CLI — owner decision 2026-11-16.
- `gh auth login` or any interactive login in an executor.
- New method kinds (`dmg`, `pkg`, `flatpak`, `snap`, `appimage`, `gh_extension`) — every tool fits an existing kind.
- Real-Mac checks — UAT lines deferred to the owner's Mac.

## Constraints

- No sudo, pkexec or doas anywhere; children run with stdin closed; no network login.
- `~/.aws`, `~/.config/gh` and existing agent-host configs are never deleted or overwritten.
- Installs and removals run only in disposable containers (`scripts/detect-container-runtime.sh`), removed afterwards.
- `make validate && make test` pass on the commit.

## Acceptance Criteria

- [ ] Xcode CLT: missing row shows the exact command; grep test finds no executor spawning it; no removal action.
- [ ] AWS CLI: container install verified with gpg; no `--system` in argv; `~/.aws` unchanged after uninstall; brew fallback present.
- [ ] Bruno: AppImage and cask methods load; digests match the release; no `bru`.
- [ ] gh-stack: the four argv strings match exactly; unauthenticated `gh` never prompts.
- [ ] Playwright MCP: existing entry kept; present hosts only; Flatpak path only when the wrapper exists; consent denied writes nothing.
- [ ] `make verify-registry` (read-only) passes for every new pinned download artifact (Bruno's AppImages); the npm pin is not covered by it and is bumped by hand or by catalog-audit (32 D-13).

## Edge Coverage

**Coverage:** 21/21 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Acceptance 1: the row is OS-gated; Linux hosts show it as a dimmed `unavailable` row, never as a prompt (catalog_tui.py:208-216) |
| empty | R1 | ✅ covered | Acceptance 1: no tools installed gives missing plus the command; tools present gives present and no command |
| encoding | R1 | ✅ covered | Acceptance 1: the command string is compared byte-exact as `xcode-select --install` |
| ordering | R1 | ✅ covered | Acceptance 1: the row has a single detect result, independent of other rows |
| adjacency | R2 | ✅ covered | Acceptance: fixture or container check named in the requirement's acceptance (32 D-16) |
| empty | R2 | ✅ covered | Acceptance: fixture or container check named in the requirement's acceptance (32 D-16) |
| ordering | R2 | ✅ covered | Acceptance: fixture or container check named in the requirement's acceptance (32 D-16) |
| idempotency | R2 | ✅ covered | Acceptance 2: a second script install over an existing aws updates in place and leaves ~/.aws untouched |
| concurrency | R2 | 🧪 backstop | held-out test: interleaved runs in a scratch HOME or container leave one registration and one install, via the run lock and the atomic write |
| adjacency | R3 | ✅ covered | Acceptance 3: the AppImage name carries version and architecture, so two architectures never share a path |
| empty | R3 | ✅ covered | Acceptance 3: a host architecture with no asset reads unavailable |
| ordering | R3 | ✅ covered | Acceptance 3: asset selection is by os and arch params, never by list order |
| adjacency | R4 | ✅ covered | Acceptance 4: `gh extension list` matching is exact on the `stack` name, so a similarly named extension never reads present |
| empty | R4 | ✅ covered | Acceptance 4 (amended): no extensions installed reads absent because the manifest file is absent; an unauthenticated gh is never consulted for detection (list needs a login, live test) |
| ordering | R4 | ✅ covered | Acceptance 4: detection reads the whole list, independent of extension order |
| idempotency | R4 | ✅ covered | Acceptance 4: a second `gh extension install` of an installed extension reports already installed, never errors the row |
| concurrency | R4 | 🧪 backstop | held-out test: interleaved runs in a scratch HOME or container leave one registration and one install, via the run lock and the atomic write |
| adjacency | R5 | ✅ covered | Acceptance 5: an existing `playwright` entry beside other servers is kept byte-identical |
| empty | R5 | ✅ covered | Acceptance 5: no agent host present writes nothing; a host with no servers table gets one entry |
| ordering | R5 | ✅ covered | Acceptance 5: other servers keep their order; the new entry is added, never reordered into them |
| concurrency | R5 | 🧪 backstop | held-out test: interleaved runs in a scratch HOME or container leave one registration and one install, via the run lock and the atomic write |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| No installer code path MUST run `xcode-select --install`, sudo, pkexec or doas | 1 | resolved | test: grep over `installer/` for the spawn and the privilege tools |
| An uninstall MUST NOT delete or modify `~/.aws` | 2 | resolved | test: seeded file byte-identical after a container uninstall |
| The Playwright MCP registration MUST NOT overwrite an existing `playwright` server entry or write `~/.claude/settings.json` without consent | 5 | resolved | test: existing entry kept; consent-denied run writes nothing |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.85  | 0.75 | ✓      | Roadmap criteria and owner decisions |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | No new method kinds; explicit exclusions |
| Constraint Clarity | 0.75  | 0.65 | ✓      | gpg prerequisite and the Playwright pin settled in discuss |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | Registry, container and scratch-HOME checks |
| **Ambiguity**      | 0.18  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The requirements restate owner-locked decisions and verified facts (initial ambiguity under 0.20); the one open item is the Playwright pin, a discuss-level choice recorded below. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Researcher | Playwright MCP pin: research said 0.0.85, npm latest is 0.0.86 | none | R5 requires an exact verified pin and records the choice; discuss picks it (ledger) |

---

*Phase: 32-onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 32 — implementation decisions (how to build what's specified above)*
