# Phase 5: Registry Method Corrections (codegraph/mmdc/puppeteer) - Research

**Researched:** 2026-09-05
**Domain:** Declarative registry (`installer/registry.toml`) method correctness for three Node-ecosystem-adjacent tools: a Go/Node-hybrid binary (`codegraph`), an npm CLI with a peer-dependency on a headless-browser automation library (`mmdc`), and that library itself (`puppeteer`/`chrome-headless-shell`).
**Confidence:** HIGH for codegraph's distribution mechanism and puppeteer's dependency/postinstall shape (all confirmed via GitHub API, `unpkg.com` package.json fetches, and this project's own already-shipped Phase 4 finding); MEDIUM for the mmdc method recommendation (weighs multiple CITED sources, no single canonical source states "use pnpm"); LOW/flagged-assumption for exact Fedora/Arch system-library package names (upstream itself only documents Debian/CentOS).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 (mmdc install method):** `mmdc`'s install method is **research-driven, with a soft leaning toward Homebrew** — the user's own words: "Research it, maybe I prefer brew, research it and consider stability, and security, simplicity, maintainability." This is not a hard lock-in to brew: if research finds pnpm-with-mitigation or a Phase-4-cleared Volta redirect is clearly better on those four criteria (stability, security, simplicity, maintainability), that wins instead. Reuse Phase 4's volta-internals research finding (does `volta install` shell out to npm, losing pnpm's gated-postinstall security) rather than re-deriving it — Phase 5 depends on that finding per ROADMAP's "Depends on" line.

**D-02 (decision criteria):** Decision criteria for mmdc, in the user's own priority framing: stability, security, simplicity, maintainability — weigh all four, not just the postinstall-script-security-vs-global-install-bug tradeoff the original PRD framed narrowly.

**D-03 (puppeteer cross-platform handling):** One `puppeteer` catalog entry with platform-conditional methods (macOS vs Linux/Bazzite), mirroring how other registry entries already branch on platform — not two separate entries, not a single method assumed to work identically on both. Research determines what each platform's real install path actually is; do not assume parity.

### Claude's Discretion

- Exact registry `kind`/method shape for whichever install path research selects for mmdc (script/brew/uv-tool/etc.) — planner's call once research lands.
- Whether `chrome-headless-shell` needs its own separate registry entry from `puppeteer` or is bundled as one of puppeteer's install artifacts — a research question, not a locked decision.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 5 scope; the postinstall/graphify questions raised mid-discussion were clarifications of an existing boundary (codegraph's MCP postinstall is Phase 9's `REQ-codegraph-mcp-postinstall`; `graphify` is Phase 8's `REQ-uv-tool-executor`), not new ideas to defer.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-codegraph-github-release | `codegraph`'s registry entry uses `kind="github_release"` (verified: prebuilt binary tarball, no npm involved), not `kind="node"`/`kind="script"`. | Confirmed via `gh api repos/colbymchenry/codegraph/releases/latest` (GitHub API, authoritative) and the upstream `install.sh` (fetched, read). See "Standard Stack" and "Code Examples" for the exact `registry.toml` shape, asset names, and checksum file. |
| REQ-mmdc-install-decision | Decide and record `mmdc`'s install method explicitly (pnpm with documented mitigation, or Homebrew) — weighing stability/security/simplicity/maintainability, reusing Phase 4's volta-internals finding. | See "Summary" and "Common Pitfalls" — Homebrew is upstream-deprecated for this specific tool (README states "no longer supported", GitHub issue #1122 confirms real breakage, closed not-planned); pnpm-with-mitigation is recommended over brew and over Volta. |
| REQ-puppeteer-catalog-entries | `puppeteer` and `chrome-headless-shell` become their own catalog entries; `mmdc.requires` gains `["puppeteer"]`; verify (not assume) whether the dependency applies identically on macOS and Linux. | See "Architecture Patterns" (single-entry, platform-conditional shape) and "Common Pitfalls" (the pnpm global-install isolation gotcha that governs whether `requires` actually satisfies the peer dependency at runtime, and the Linux-only shared-library requirement). `chrome-headless-shell` does NOT need its own `Tool` entry — resolved below. |

</phase_requirements>

## Summary

All three tools in this phase are Node-ecosystem-adjacent but distribute in three genuinely different ways, and the PRD-stage assumptions about two of them (`codegraph`, `mmdc`) do not survive contact with upstream's own current documentation.

**`codegraph`** (`colbymchenry/codegraph`) is straightforward and already effectively decided by prior research recorded in `.planning/intel/requirements.md`: its `install.sh` explicitly states "No Node.js, no build tools, no npm required," downloads a self-contained tarball (vendored Node runtime + app) from GitHub Releases named `codegraph-{os}-{arch}.tar.gz`, and ships a `SHA256SUMS` file. This session re-verified the exact asset names and checksum file live via the GitHub Releases API (`v1.6.0`) and confirmed the install script's exact `--strip-components=1` extraction and `bin/codegraph` binary path. **This is a straight `kind="github_release"` entry, template-identical to `rg`/`fd`/`bat`/`gum`.** `codegraph` does not currently exist in `registry.toml` — this phase adds it correctly the first time; there is no wrong entry to "correct."

**`mmdc`** is the genuinely researched decision. The PRD's "soft lean toward brew" rested on the Homebrew formula being version-current (`11.17.0`, confirmed matching npm's `11.17.0` via live `brew info` and `unpkg.com`). But upstream mermaid-cli's own README **explicitly deprecates the Homebrew install path** ("This method of installation is no longer supported"), and a live GitHub issue (#1122, closed as "not planned") documents exactly the failure mode: the formula installs cleanly but cannot find `chrome-headless-shell` at runtime, because Homebrew's formula only declares `node` as a dependency — it does nothing about mmdc's real runtime dependency on `puppeteer` and puppeteer's own Chrome download. Brew fails the **stability** criterion outright: it is a documented, currently-open breakage, not a hypothetical risk. Between the two remaining options, Volta (Phase 4's finding: `volta install` shells out to real `npm install --global` with no flag to disable install scripts) provides **no security gating at all** for anything installed through it, whereas pnpm's default posture is to block package postinstall scripts until explicitly approved (`pnpm approve-builds` / `--allow-build=<pkg>`) — a reviewable, minimal-scope allowlist rather than blanket unrestricted execution. **Recommendation: pnpm-with-mitigation for `mmdc` — mmdc itself has no postinstall script at all** (verified via `unpkg.com/@mermaid-js/mermaid-cli/package.json`), so the only postinstall-security question that actually applies here is puppeteer's, and it's cleanly addressable with a scoped `--allow-build=puppeteer` rather than Volta's all-or-nothing.

**`puppeteer`** is the deepest finding, and it's a genuine landmine for the "`mmdc.requires = ["puppeteer"]` and the resolver drags it in automatically" model this phase's requirement describes. `@mermaid-js/mermaid-cli` declares `puppeteer` as a **peerDependency** (`^23 || ^24 || ^25`), not a regular dependency — deliberately not auto-installed. Community guidance and pnpm's own official docs agree on the fix: install both packages **in the same invocation** (`pnpm add -g pkgA,pkgB` — comma-separated, no spaces) so they share one `node_modules` tree; pnpm's docs state explicitly that two separate `pnpm add -g` invocations get **separate, isolated `node_modules`/lockfiles that do not resolve peer dependencies against each other**. This project's current dependency-drag-in model (`installer/deps.py:resolve_dependencies` → `installer/engine.py:install_tool`, one independent `_perform()` call per `Tool`) would install `puppeteer` and `mmdc` as two **separate** `pnpm add -g` invocations — which, per pnpm's own documented behavior, would silently produce an `mmdc` that cannot `require('puppeteer')` at runtime. This is not a hypothetical; it is pnpm's own documented isolation model, verified by reading `installer/deps.py`/`installer/engine.py`/`installer/executors.py:_node` directly. The planner must decide how to bundle these two installs (see "Common Pitfalls" for a concrete recommendation) — this is new territory for the registry/executor model, not a drop-in use of the existing `requires` field.

On platform parity (D-03): puppeteer's own official troubleshooting docs give an **exact** Debian/Ubuntu shared-library list required for headless Chrome to even launch (`libnss3`, `libatk-bridge2.0-0`, `libgtk-3-0`, etc. — 30+ packages) but only reference "Chromium's own source" for Fedora/Arch, with no exact package names. **macOS needs none of this** — the downloaded Chrome for Testing / chrome-headless-shell bundle runs against system frameworks already present. This confirms the dependency does **not** apply identically across platforms, and the Fedora/Arch package list is a genuine unresolved gap (see "Open Questions") that should **not** be modeled as a cross-tier `requires` edge (see "Common Pitfalls" for why that specific mechanism would break puppeteer/mmdc entirely on macOS).

`chrome-headless-shell` does **not** need its own catalog `Tool` entry: puppeteer's own `postinstall` (`node install.mjs`) downloads **both** a full Chrome for Testing build and the `chrome-headless-shell` binary to `~/.cache/puppeteer` as part of installing puppeteer itself — there is no independent install path for it to model.

**Primary recommendation:** Add `codegraph` as `kind="github_release"` (template below). Decide `mmdc` stays on `pnpm add -g` (unchanged method, but record the brew-rejection reasoning on the entry, mirroring the existing `volta`-entry comment-block convention). Add `puppeteer` as a single `Tool` with `kind="node"` methods for both macOS and Linux (same npm mechanism on both — the platform difference is Linux's additional system-library prerequisite, documented but not automated pending Fedora/Arch package-name verification), require `pnpm` on it (matching the project's own `test_shipped_node_tools_require_pnpm` convention), and solve the pnpm-isolation peer-dependency gap explicitly rather than relying on `requires=["puppeteer"]` alone to make it work at runtime.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `codegraph` binary distribution | Registry/Catalog (`installer/registry.toml`, `installer/download.py`) | — | Pure declarative-data + existing `github_release` executor; no new code path needed. |
| `mmdc` package manager selection | Registry/Catalog | Guards (`installer/guards.py` redirect policy, already shipped in Phase 4) | Decision lives in `registry.toml`'s `[[tool.method]]`; the pnpm-vs-volta-vs-brew reasoning is Phase 4/5 registry-authoring concern, not new runtime code. |
| `puppeteer` install + postinstall gating | Registry/Catalog + Executor (`installer/executors.py:_node`) | Engine (`installer/engine.py`, `installer/deps.py`) | The peer-dependency/co-install problem is NOT solvable by `registry.toml` data alone — it requires either an executor-level change (bundle npm_pkg names into one pnpm invocation) or an engine-level change (detect same-manager sibling `requires` and coordinate a single install call). This is genuinely a cross-cutting concern between catalog data and install-time orchestration. |
| Linux system-library prerequisite for headless Chromium | Out of catalog scope this phase (documented, not automated) | System package managers (`apt`/`dnf`/`pacman`) | Cannot be modeled as a `requires` edge without breaking macOS resolution (see Pitfalls) — needs either a platform-scoped inline step inside puppeteer's Linux method or a documented manual/Doctor-style prerequisite; exact Fedora/Arch package names are unverified. |

## Standard Stack

### Core

| Library/Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `codegraph` (colbymchenry/codegraph) | v1.6.0 (latest as of 2026-09-05) [VERIFIED: `gh api repos/colbymchenry/codegraph/releases/latest`] | Code-intelligence knowledge-graph CLI/MCP server | Already the project's chosen tool per ROADMAP/REQUIREMENTS; ships a genuinely self-contained binary, no runtime deps |
| `@mermaid-js/mermaid-cli` (`mmdc`) | 11.17.0 [VERIFIED: `pnpm view @mermaid-js/mermaid-cli version`, matches `brew info mermaid-cli` at 11.17.0] | Render Mermaid diagrams to SVG/PNG/PDF from the CLI | Already in `registry.toml`; this phase only corrects/confirms its install method |
| `puppeteer` | 25.10.0 [VERIFIED: `pnpm view puppeteer version`, cross-checked against `unpkg.com/puppeteer/package.json`] | Headless-Chrome automation library; mmdc's actual rendering engine | mmdc's own declared peer dependency (`^23 \|\| ^24 \|\| ^25`) [VERIFIED: `unpkg.com/@mermaid-js/mermaid-cli/package.json` peerDependencies field] |
| pnpm | Already a `tier="system"` catalog entry | Global npm-package installer for `mmdc`/`puppeteer` | Already this project's default global-installer per Phase 4's redirect policy; mmdc has zero postinstall scripts of its own, so pnpm's default gating never even engages for mmdc itself |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pnpm-with-mitigation for mmdc | Homebrew | **Rejected**: upstream explicitly deprecated this path ("no longer supported"); live GitHub issue #1122 documents the exact failure (`chrome-headless-shell` not found), closed "not planned" by maintainers — fails the stability criterion outright, not a hypothetical risk |
| pnpm-with-mitigation for mmdc/puppeteer | Volta redirect | **Rejected**: Phase 4's own finding (quoted verbatim below) shows volta's `npm install --global` has no flag to disable install scripts — ALL postinstall scripts (including puppeteer's Chrome download) run completely unrestricted, a strictly worse security posture than pnpm's default-deny-with-explicit-allowlist model, for no stability gain (puppeteer's postinstall isn't the pnpm-global-loss bug's territory anyway) |
| Automated Linux system-library install | Manual/documented prerequisite | Fedora/Arch package names for the Chromium runtime deps are not published anywhere authoritative (Chromium's own docs point only at "read the source"); automating a guessed package list risks silently installing the wrong packages on a live machine — documented gap, not automated, until verified live per this project's own registry-authoring convention |

**Installation (once decided):**
```toml
# codegraph — new entry, kind="github_release" from day one (no prior wrong entry to migrate)
[[tool]]
id = "codegraph"
...
[[tool.method]]
kind = "github_release"
repo = "colbymchenry/codegraph"
asset = "codegraph-darwin-{arch.x64}.tar.gz"
checksum = "SHA256SUMS"
member = "bin/codegraph"
strip = 1
os = ["macos"]
[[tool.method]]
kind = "github_release"
repo = "colbymchenry/codegraph"
asset = "codegraph-linux-{arch.x64}.tar.gz"
checksum = "SHA256SUMS"
member = "bin/codegraph"
strip = 1
os = ["debian", "arch", "fedora"]
```

**Version verification performed this session:**
- `pnpm view puppeteer version` → `25.10.0`
- `pnpm view @mermaid-js/mermaid-cli version` → `11.17.0`
- `brew info mermaid-cli` → `stable 11.17.0` (matches npm exactly, confirming the PRD-stage "version parity" claim was accurate as of today — the freshness argument alone does not favor either manager)
- `gh api repos/colbymchenry/codegraph/releases/latest` → tag `v1.6.0`, assets: `codegraph-darwin-arm64.tar.gz`, `codegraph-darwin-x64.tar.gz`, `codegraph-linux-arm64.tar.gz`, `codegraph-linux-x64.tar.gz`, `codegraph-win32-*.zip` (not relevant), `SHA256SUMS`

## Package Legitimacy Audit

| Package | Registry | Age (latest publish) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `puppeteer` | npm | published 2026-09-03 (2 days before this research) | 11,913,591/week | `github.com/puppeteer/puppeteer` | SUS (`too-new` — publish-recency heuristic, not identity risk) | **Flagged per protocol, but recommend planner treat as a false positive**: 11.9M weekly downloads and a canonical GitHub org repo are inconsistent with slopsquatting; the "too-new" signal fires on any routine version bump. Planner should still add a `checkpoint:human-verify` per protocol, but the underlying package identity is not in question. |
| `@mermaid-js/mermaid-cli` | npm | published 2026-09-02 (3 days before this research) | 598,298/week | `github.com/mermaid-js/mermaid-cli` | SUS (`too-new`, same heuristic) | Same disposition as above — already in `registry.toml` today, unchanged by this phase; flagged for completeness only. |

**Packages removed due to `[SLOP]` verdict:** none
**Packages flagged as suspicious `[SUS]`:** `puppeteer`, `@mermaid-js/mermaid-cli` — both are `too-new`-heuristic false positives on long-established, high-download, canonically-sourced packages (see reasoning above); planner should add a `checkpoint:human-verify` per protocol but should not block the phase on re-verifying package identity that is already this well-established.

`codegraph` is not npm-distributed in this phase's method (`kind="github_release"`), so the npm package-legitimacy gate does not apply to it; its authenticity was instead verified via the GitHub Releases API directly (see Standard Stack).

## Architecture Patterns

### System Architecture Diagram

```
User selects `mmdc` in the AI/user-tier catalog view
        │
        ▼
resolve_dependencies() walks mmdc.requires = ["pnpm", "puppeteer"]
        │                                   (puppeteer.requires = ["pnpm"])
        ▼
Deps-first order: [pnpm (if needed), puppeteer, mmdc]
        │
        ▼
run_installs() iterates the order, calling install_tool() once per Tool
        │
        ├─► install_tool(puppeteer) → _node() → `pnpm add -g puppeteer`
        │        (postinstall `node install.mjs` gated by pnpm's build-script
        │         allowlist — needs an explicit approval step or it silently
        │         no-ops, leaving chrome-headless-shell undownloaded)
        │        → isolated node_modules #1
        │
        └─► install_tool(mmdc) → _node() → `pnpm add -g @mermaid-js/mermaid-cli`
                 → isolated node_modules #2  ◄── PROBLEM: separate from #1,
                                                  so mmdc's require('puppeteer')
                                                  cannot resolve at runtime
                                                  (pnpm's own documented
                                                  global-install isolation)

Fix (planner decision): coordinate puppeteer+mmdc into ONE pnpm invocation
(`pnpm add -g @mermaid-js/mermaid-cli,puppeteer`) sharing one node_modules,
OR an equivalent mechanism — see Common Pitfalls for options.
```

### Recommended Project Structure

No new files needed for the registry data itself; `registry.toml` gains three new/corrected `[[tool]]` blocks. If the pnpm co-install fix requires executor changes, they are scoped additions to the existing `_node` function in `installer/executors.py` (new optional param), not a new module.

### Pattern 1: `github_release` entry for a self-contained binary tarball

**What:** The existing pattern already used by `rg`, `fd`, `bat`, `gum`, `just`, `lazygit`, etc. — `os`-scoped methods, `{arch.x64}` (or `{arch.machine}`, `{arch.deb}`, etc.) templating, an optional `checksum` file.
**When to use:** Any tool whose upstream publishes prebuilt per-platform tarballs on GitHub Releases with no runtime dependency on this project's package managers.
**Example (verified against codegraph's actual v1.6.0 release):**
```toml
[[tool]]
id = "codegraph"
name = "CodeGraph"
category = "dev"
cmd = "codegraph"
priority = "P1"
audience = "ai"
tier = "ai"
desc = "Local code-intelligence knowledge graph CLI and MCP server"
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "colbymchenry/codegraph"
asset = "codegraph-darwin-{arch.x64}.tar.gz"
checksum = "SHA256SUMS"
member = "bin/codegraph"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "colbymchenry/codegraph"
asset = "codegraph-linux-{arch.x64}.tar.gz"
checksum = "SHA256SUMS"
member = "bin/codegraph"
strip = 1
```
Note: no brew fallback exists (no known Homebrew formula for `colbymchenry/codegraph`) — this project's `github_release`-only ladder for this tool means a checksum-mismatch or a network failure has no fallback method; this matches `eza`'s existing precedent (macOS-less entries, brew-only fallback) inverted — here there is no brew formula at all, which should be called out in the registry comment (mirroring the `# eza publishes no macOS asset` comment style already used at line 303 of `registry.toml`).

### Pattern 2: `node` entries requiring `pnpm`, per this project's own test convention

**What:** `tests/test_registry.py::test_shipped_node_tools_require_pnpm` [VERIFIED: `tests/test_registry.py:732-736`, quoted verbatim: `"if any(m.kind == \"node\" for m in tool.methods): assert \"pnpm\" in tool.requires"`] already enforces that every `kind="node"` tool declares `requires` including `"pnpm"`. `puppeteer`'s registry entry must follow this convention identically to `mmdc`'s existing entry.
**Example:**
```toml
[[tool]]
id = "puppeteer"
name = "Puppeteer"
category = "dev"
cmd = "puppeteer"   # verify: puppeteer has no meaningful standalone CLI binary; cmd/is_installed detection needs its own research at plan time (see Open Questions)
priority = "P2"
audience = "ai"
tier = "ai"
desc = "Headless-Chrome automation library; downloads chrome-headless-shell as part of its own install. Required by mmdc for diagram rendering."
requires = ["pnpm"]
[[tool.method]]
kind = "node"
npm_pkg = "puppeteer"
```

### Pattern 3: The `volta`-entry comment-block convention for recording a researched tradeoff on the registry entry itself

**What:** `registry.toml:1472-1487` already carries a multi-line comment above the `volta` tool block recording exactly how the volta-internals research finding was obtained, what it means, and when to re-verify it. **Quoted verbatim** [VERIFIED: `installer/registry.toml:1472-1487`]:
```
# volta install <pkg> runs a real `npm install --global --loglevel=warn
# --no-update-notifier --no-audit <pkg>` subprocess, with no flag that disables
# install scripts — verified by reading Volta's own source,
# crates/volta-core/src/tool/package/install.rs, function run_global_install
# (github.com/volta-cli/volta, fetched 2026-09-05).
# Consequence: anything installed through volta runs npm's preinstall/install/
# postinstall scripts unrestricted, which pnpm has gated behind an opt-in
# allowlist since pnpm v10 (pnpm.io/supply-chain-security). Routing global
# installs to volta is therefore a security-for-stability tradeoff the user
# accepted in D-06/D-08 to fix pnpm's global-package loss on self-update —
# it is not a clean win.
# Version caveat: npm v12 flips install scripts to opt-in
# (github.blog/changelog/2026-06-09-upcoming-breaking-changes-for-npm-v12/).
```
**This is the finding Phase 5 MUST reuse, not re-derive** (per ROADMAP's "Depends on" line and CONTEXT D-01). It is quoted here verbatim so the planner never has to re-fetch it.
**Recommendation:** Apply the identical comment-block pattern above `mmdc`'s (unchanged) tool block, recording the brew-rejection finding and the puppeteer-peer-dependency-isolation finding, so a future reader of `registry.toml` sees the reasoning without needing to re-open this RESEARCH.md.

### Anti-Patterns to Avoid

- **Modeling the Linux-only Chromium shared-library prerequisite as a `requires` edge on a new system-tier tool:** `installer/app.py:137` wires `resolve_dependencies`'s `available` callback as `lambda tool: bool(resolve_methods(tool, platform))` [VERIFIED: `installer/app.py:137`, quoted verbatim]. A hypothetical `chromium-linux-deps` tool with only `apt`/`dnf`/`pacman` methods would resolve `available() == False` on macOS, and `installer/deps.py`'s `is_blocked()` function [VERIFIED: `installer/deps.py:81-100`] would then mark it — and everything that transitively requires it — as blocked and skipped **on macOS**, silently removing `puppeteer` and `mmdc` from the install order entirely on the platform where they need no such prerequisite. Do not use `requires` for platform-conditional system prerequisites; keep the platform split inside the `Method`'s own `os=[...]` scoping instead.
- **Trusting `mmdc.requires = ["puppeteer"]` alone to make puppeteer resolvable at runtime under pnpm:** as detailed in Common Pitfalls, this satisfies the *catalog's* notion of "installed in the right order" but not Node's actual module resolution, because of pnpm's per-invocation global isolation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Verifying a GitHub release asset's integrity | A custom curl+sha256 script | The existing `installer/checksums.py` + `checksum` param on `kind="github_release"` methods | Already implemented, tested, and used by every other `github_release` entry; `codegraph`'s `SHA256SUMS` file is in the exact `<hash>  <filename>` format `expected_sha256()` already parses [VERIFIED: fetched `SHA256SUMS` from `github.com/colbymchenry/codegraph/releases/download/v1.6.0/SHA256SUMS`, format confirmed line-for-line against `installer/checksums.py:23-37`'s parser] |
| Gating puppeteer's postinstall Chrome download | A custom "did puppeteer already download chrome-headless-shell" idempotency check | pnpm's own `pnpm approve-builds` / `--allow-build=<pkg>` mechanism | pnpm already has a first-class allowlist mechanism for exactly this; reinventing it in this project's own code would duplicate pnpm's own security boundary and likely get the edge cases wrong (pnpm's own docs note the mechanism changed shape between v10/v11) |
| Detecting Fedora/Arch's exact headless-Chromium shared-library package names | Guessing from the Debian list and translating package names by pattern-matching | Live verification on an actual Fedora/Arch (Bazzite) machine before shipping an automated install step | Package names do not translate 1:1 across distros (e.g. `libnss3` → `nss` on Fedora is a real but non-mechanical rename) — this project's own not-yet-shipped `REQ-registry-authoring-verification-checklist` exists precisely because guessed package names have shipped broken before |

**Key insight:** Every "don't hand-roll" item in this phase is really the same insight in three guises: this project already has (or the upstream ecosystem already has) a purpose-built mechanism for the exact problem — checksums, build-script allowlisting, and per-distro package verification — and the risk in this phase is skipping past those existing mechanisms because the *tools* look unfamiliar (codegraph, puppeteer), not because the *problems* are new.

## Common Pitfalls

### Pitfall 1: `mmdc.requires = ["puppeteer"]` does not make puppeteer resolvable at runtime under pnpm's global-install model

**What goes wrong:** `puppeteer` installs successfully, `mmdc` installs successfully, `resolve_dependencies` reports the drag-in correctly, and the wizard shows both as installed — but running `mmdc` fails with a module-resolution error because `mmdc`'s code cannot `require('puppeteer')`.
**Why it happens:** pnpm's own documentation states, verbatim [CITED: pnpm.io/global-packages]: "Each globally installed package (or group of packages installed together) gets its own isolated installation directory with its own `package.json`, `node_modules/`, and lockfile," and that resolving peer dependencies across packages requires installing them together via the comma-separated syntax (`pnpm add -g pkgA,pkgB`). This project's `installer/deps.py:resolve_dependencies` → `installer/engine.py:install_tool` model installs one `Tool` at a time via one independent `_perform()` call each [VERIFIED: `installer/engine.py:49-62, 65-103`] — there is currently no mechanism to combine two `Tool`s' `kind="node"` methods into one `pnpm add -g a,b` invocation.
**How to avoid:** The planner needs an explicit design decision here — this is new territory, not a drop-in use of existing fields. Two concrete options, in order of recommendation:
  1. Add an optional `co_install` (or similarly named) list param to the `node` `Method` schema; when present, `installer/executors.py:_node` builds a single comma-joined `pnpm add -g` argv covering the tool's own `npm_pkg` plus every listed sibling, instead of the current single-package call. `mmdc`'s method would declare `co_install = ["puppeteer"]`. `puppeteer` remains its own separately-selectable `Tool` for catalog/uninstall/status purposes; only the *install invocation* is coordinated.
  2. Have the engine detect, at `run_installs` time, when two adjacent tools in the resolved order share `kind="node"` and a `requires` edge, and coordinate a combined invocation automatically. More "automatic" but a bigger, more invasive engine change for a two-tool special case.
Either way, do not ship this phase with the current one-tool-at-a-time engine and simply add `puppeteer` to `mmdc.requires` without addressing this — the requirement's own acceptance text ("so it drags in automatically") reads as satisfied by the catalog/ordering layer while silently failing at the module-resolution layer.
**Warning signs:** `mmdc <file>.mmd` (or equivalent) throwing `Cannot find module 'puppeteer'` after a clean install where both entries reported success.

### Pitfall 2: pnpm silently skips puppeteer's postinstall (Chrome download) unless explicitly approved

**What goes wrong:** `pnpm add -g puppeteer` "succeeds" (exit 0), but `chrome-headless-shell` is never downloaded, because pnpm's default posture blocks a package's build/postinstall scripts until approved.
**Why it happens:** puppeteer declares `"postinstall": "node install.mjs"` [VERIFIED: `unpkg.com/puppeteer/package.json` scripts field, cross-confirmed via `gsd-tools query package-legitimacy check` signal `"postinstall": "node install.mjs"`]. pnpm's own docs [CITED: pnpm.io/cli/approve-builds] describe an "Ignored build scripts" mechanism where unapproved packages have their lifecycle scripts blocked, with the tool printing a warning rather than failing the install — this is a real, commonly-hit issue (community reports of "Ignored build scripts: sharp" and similar for other native/download-heavy packages).
**How to avoid:** The `puppeteer` install step must explicitly allow its build script, either via `pnpm add -g --allow-build=puppeteer puppeteer` at install time, or a one-time `pnpm approve-builds -g puppeteer` run before/after. This is a small, targeted addition to the `_node` executor (or a new param), analogous in spirit to the already-approved pattern of gating specific behavior per tool rather than blanket-disabling pnpm's protection.
**Warning signs:** puppeteer "installs" in well under the ~170-280MB download's expected time; `~/.cache/puppeteer` is empty or missing after install; `mmdc` fails at runtime with a "Could not find Chrome" / "Could not find chrome-headless-shell" error — the exact error the abandoned Homebrew path also produces (see Pitfall 3), so don't conflate the two root causes.

### Pitfall 3: Believing the Homebrew formula is a safe, current alternative because its version number matches npm

**What goes wrong:** `brew info mermaid-cli` shows `stable 11.17.0`, version-identical to the npm package, which superficially looks like "brew is just as current, so it's a safe choice, especially given the user's stated preference." Installing via brew still breaks at runtime.
**Why it happens:** The Homebrew formula's only declared dependency is `node` [VERIFIED: `brew info mermaid-cli` output, `Required (1): node`] — it does nothing about mmdc's real runtime dependency on `puppeteer`/`chrome-headless-shell`. Upstream mermaid-cli's own README states the Homebrew install path is "no longer supported" and points to a discussion explaining why; a live, still-open (closed "not planned") GitHub issue #1122 documents a user hitting exactly "Could not find chrome-headless-shell" after a brew install, with the only workaround being to manually set `PUPPETEER_EXECUTABLE_PATH` to a separately, manually installed browser.
**How to avoid:** Do not select brew for `mmdc` on the basis of version-currency alone; version-currency was never the actual failure mode. Verify a tool's *documented, current* install guidance from upstream itself before trusting a package manager's formula just because its version number is fresh — a formula can be perfectly up to date and still broken for reasons the version number says nothing about.
**Warning signs:** `mmdc -i diagram.mmd -o diagram.svg` after a brew install throwing a chrome-headless-shell-not-found error identical in wording to Pitfall 2's, despite install having reported success — always check `PUPPETEER_EXECUTABLE_PATH`/postinstall logs to disambiguate the two root causes before assuming either one.

### Pitfall 4: Assuming the Linux Chromium shared-library requirement applies to macOS too, or vice versa

**What goes wrong:** Either (a) the registry entry adds Debian package installation for the Linux `puppeteer` method and assumes the same is needed on macOS (wasted no-op or, worse, a macOS `apt`/`dnf` method that can never resolve and confuses the ladder), or (b) the entry is written with zero platform distinction and Linux users hit a wall of missing `.so` errors the first time they actually try to render a diagram, well after "install" reported success.
**Why it happens:** Puppeteer's Chrome for Testing bundle statically resolves against system shared libraries on Linux (`libnss3`, `libatk-bridge2.0-0`, `libgtk-3-0`, and ~27 others per puppeteer's own troubleshooting.md) that are not present on a minimal Linux install by default; on macOS, the equivalent frameworks are part of the OS itself, so no additional install step exists or is documented anywhere for macOS.
**How to avoid:** Confirmed via CITED source: this dependency is genuinely Linux-only. Document it explicitly on the Linux `puppeteer` method (comment block, matching the `volta`/pattern-3 style above) rather than leaving it implicit; do not model it as a cross-tier `requires` edge (see Anti-Patterns above — it would break macOS resolution). The exact Fedora/Arch package names remain an open question (see Open Questions) — do not guess them from the Debian list.
**Warning signs:** `mmdc` fails at runtime on a fresh Linux/Bazzite install with dynamic-linker errors (`error while loading shared libraries: libnss3.so: cannot open shared object file`) despite `puppeteer`/`mmdc` both reporting a clean install.

## Code Examples

### `codegraph` — full `[[tool]]` block ready for `registry.toml`

```toml
[[tool]]
id = "codegraph"
name = "CodeGraph"
category = "dev"
cmd = "codegraph"
priority = "P1"
audience = "ai"
tier = "ai"
desc = "Local code-intelligence knowledge graph CLI and MCP server; no Node/npm required at runtime."
# Verified 2026-09-05 via `gh api repos/colbymchenry/codegraph/releases/latest`
# (tag v1.6.0) and the upstream install.sh (github.com/colbymchenry/codegraph),
# which states "No Node.js, no build tools, no npm required." No Homebrew
# formula exists for this tool as of this date — github_release is the only
# ladder rung; a checksum mismatch or network failure has no fallback method.
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "colbymchenry/codegraph"
asset = "codegraph-darwin-{arch.x64}.tar.gz"
checksum = "SHA256SUMS"
member = "bin/codegraph"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "colbymchenry/codegraph"
asset = "codegraph-linux-{arch.x64}.tar.gz"
checksum = "SHA256SUMS"
member = "bin/codegraph"
strip = 1
```

### `puppeteer` — full `[[tool]]` block, with the co-install gap flagged inline

```toml
[[tool]]
id = "puppeteer"
name = "Puppeteer"
category = "dev"
cmd = "puppeteer"   # OPEN QUESTION: verify is_installed()/cmd detection story — see Open Questions
priority = "P2"
audience = "ai"
tier = "ai"
desc = "Headless-Chrome automation library; downloads Chrome for Testing and chrome-headless-shell as part of its own postinstall. Required at runtime by mmdc (peerDependency, not auto-installed by mmdc's own install)."
requires = ["pnpm"]
# Verified 2026-09-05: puppeteer 25.10.0 declares postinstall="node install.mjs"
# (unpkg.com/puppeteer/package.json), which downloads ~170-280MB of Chrome +
# chrome-headless-shell to ~/.cache/puppeteer. pnpm blocks this postinstall by
# default (pnpm.io/cli/approve-builds) unless explicitly allowed — the executor
# for this entry MUST pass an allow-build flag for "puppeteer" or the install
# will silently succeed with no browser downloaded (see 05-RESEARCH.md Pitfall 2).
# On Linux, the downloaded Chrome additionally requires ~30 system shared
# libraries not present by default (puppeteer's own troubleshooting.md gives an
# exact Debian list; Fedora/Arch package names are unverified — see
# 05-RESEARCH.md Open Questions). macOS needs no equivalent step.
[[tool.method]]
kind = "node"
npm_pkg = "puppeteer"
```

### `mmdc` — unchanged method, `requires` and comment updated

```toml
[[tool]]
id = "mmdc"
name = "Mermaid CLI"
category = "diagram"
cmd = "mmdc"
priority = "P2"
audience = "both"
tier = "user"
desc = "Render Mermaid diagrams to SVG/PNG/PDF from the command line"
# Install-method decision (2026-09-05, this phase's research): stays on pnpm,
# NOT Homebrew. mermaid-cli's own README explicitly deprecates the Homebrew
# path ("no longer supported"); GitHub issue #1122 (closed "not planned")
# documents brew-installed mmdc failing at runtime with "could not find
# chrome-headless-shell" because the formula only depends on `node`, not on
# puppeteer/Chrome. NOT Volta either: mmdc itself has zero postinstall scripts
# (unpkg.com/@mermaid-js/mermaid-cli/package.json, no postinstall/preinstall/
# install script present), so Volta's unrestricted-postinstall tradeoff
# (registry.toml's own volta comment, above) buys nothing here while giving up
# pnpm's default-deny build-script gate for puppeteer's own postinstall.
requires = ["pnpm", "puppeteer"]
[[tool.method]]
kind = "node"
npm_pkg = "@mermaid-js/mermaid-cli"
```

## State of the Art

| Old Approach (PRD-stage assumption, 2026-09-04) | Current Finding (this session, 2026-09-05) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| "Brew formula is version-equal to npm (11.17.0), so the freshness tradeoff no longer favors pnpm" | Brew formula IS version-current, but upstream has separately, explicitly deprecated the Homebrew install path entirely, independent of version freshness | Confirmed live 2026-09-05 (README + issue #1122 both currently reflect this stance) | The PRD's stated reason for reconsidering brew (version parity) was accurate but irrelevant — the real blocker is a runtime dependency gap brew's formula doesn't address at all |
| "`mmdc.requires` gains `puppeteer` so `resolve_dependencies` drags it in automatically" (REQUIREMENTS.md, REQ-puppeteer-catalog-entries) | Dragging it into the install *order* is necessary but not sufficient — pnpm's per-invocation global isolation means the catalog's `requires` mechanism alone does not make puppeteer resolvable by mmdc's code at runtime | This session | The planner must add a co-install/bundling mechanism (Pitfall 1); simply adding `puppeteer` to `mmdc.requires` in the schema sense will pass registry-integrity tests but not actually fix mmdc |

**Deprecated/outdated:**
- Homebrew as an mmdc install path: upstream itself calls it unsupported, not this project's own judgment call.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cmd = "puppeteer"` is a reasonable placeholder for the registry's `cmd` field, and puppeteer's `is_installed()`/version-detection story works the same way this project's other `kind="node"` entries detect installation. | Code Examples (`puppeteer` block) | Puppeteer is a *library*, not a CLI tool with a meaningful `puppeteer --version` surface in the way `mmdc`/`aichat` are — `is_installed()` may need a different detection strategy (e.g., checking for the package directory or a marker file) than the convention used for CLI-shaped `kind="node"` tools. This needs verification against `installer/status.py:is_installed` during planning, not assumed from this research. |
| A2 | The `co_install`/bundling mechanism proposed in Pitfall 1 is the right shape for solving pnpm's global-install isolation, versus other possible designs (e.g., a completely separate "dependency group" concept in the registry schema). | Common Pitfalls, Pitfall 1 | If the planner picks a different mechanism, that's fine — this is explicitly flagged as "Claude's Discretion" territory per CONTEXT.md, but the underlying pnpm-isolation problem itself (not the specific fix) is the load-bearing, verified finding. |
| A3 | Puppeteer's `engines.node >= 22.12.0` requirement is satisfied by whatever Node version this project's pnpm/volta installs provide, on both macOS and Linux. | Standard Stack | Not verified this session — if the project's managed Node version is older than 22.12.0, `pnpm add -g puppeteer` could fail or warn at install time. Low risk (Node 22 has been current LTS-track for a while) but unverified. |

**If this table is empty:** N/A — see entries above; all core distribution/dependency claims (codegraph's binary nature, mmdc's brew deprecation, puppeteer's peerDependency status, pnpm's global-install isolation) are `[VERIFIED]`/`[CITED]`, not assumed.

## Open Questions

1. **Exact Fedora/Arch package names for headless Chromium's shared-library dependencies**
   - What we know: Puppeteer's own troubleshooting.md gives an exact, complete Debian/Ubuntu `apt` package list and a partial CentOS list; it explicitly does not give Fedora or Arch package names, only pointing at "Chromium's own dependency source."
   - What's unclear: Whether Fedora's package names (likely close to CentOS's, given both are RPM-based — e.g., `nss`, `atk`, `cups-libs`, `gtk3`) transfer cleanly to Bazzite (a Fedora Atomic image) given its immutable-OS constraints already documented elsewhere in this project (native `dnf` writes are skipped on immutable Linux per `installer/resolve.py:_applies`'s `platform.immutable` check).
   - Recommendation: Treat as a live-verification task at plan/execution time (spin up or reuse a Bazzite target, attempt to launch a downloaded chrome-headless-shell, read the actual missing-library errors) rather than guessing a translated package list. Document the gap explicitly in the entry rather than shipping a guessed `apt`/`dnf`/`pacman` method.

2. **How `puppeteer`'s `is_installed()`/status detection should work, given it has no meaningful standalone CLI**
   - What we know: Every other `kind="node"` entry in this registry (`mmdc`) corresponds to an actual CLI binary (`cmd = "mmdc"`) that `installer/status.py` can probably shell out to for a version check. Puppeteer is a library with no equivalent primary CLI surface (its own `package.json` "bin" field, if any, was not checked this session).
   - What's unclear: Whether `cmd = "puppeteer"` resolves to anything meaningful on PATH after `pnpm add -g puppeteer`, or whether status detection needs a different strategy (e.g., checking for `~/.cache/puppeteer` contents, or a `pnpm list -g puppeteer` check).
   - Recommendation: Check `installer/status.py:is_installed`'s actual mechanism (`shutil.which(tool.cmd)` or similar) against puppeteer's actual npm package "bin" field during planning before finalizing the `cmd` value.

3. **Whether the co-install/peer-dependency-isolation fix (Pitfall 1) should be scoped as its own task/plan wave, separate from the registry-data-only tasks**
   - What we know: This is a genuine executor/engine code change, not a pure `registry.toml` data edit — it's qualitatively different work from adding `codegraph`'s entry or confirming `mmdc` stays on pnpm.
   - What's unclear: Whether the planner treats this as part of Phase 5 (since REQ-puppeteer-catalog-entries' acceptance criteria implicitly require it to actually work) or flags it as a fast-follow gap explicitly recorded and deferred.
   - Recommendation: Given the requirement's own text says puppeteer must "drag in automatically" (implying it must actually work, not just be declared), recommend scoping the fix inside this phase rather than deferring — but this is the planner's call given the size tradeoff.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `pnpm` | mmdc/puppeteer install methods | ✓ (already a shipped `tier="system"` catalog entry) | per Phase 4's shipped entry | — |
| `gh` CLI (GitHub API access) | This research session's live verification | ✓ | — | — |
| Network access to `github.com`/`unpkg.com`/`pnpm`'s registry | All live verification in this research | ✓ | — | — |
| A live Fedora/Arch/Bazzite machine | Verifying Open Question 1 (exact system-library package names) | Not verified this session (no such machine available in this research environment) | — | Defer to plan/execution-time live verification per this project's own registry-authoring convention |

**Missing dependencies with no fallback:** none blocking this phase's registry-data work.
**Missing dependencies with fallback:** Fedora/Arch live verification — deferred to execution time, documented as an explicit gap rather than guessed.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x [VERIFIED: `pyproject.toml` dependency `"pytest>=8"`] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`addopts = "-q"`, `testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/test_registry.py -x` |
| Full suite command | `make test` (pytest with coverage, per CLAUDE.md) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-codegraph-github-release | `codegraph` resolves to a `kind="github_release"` method on both macOS and Linux, never `kind="node"` | unit (registry integrity) | `uv run pytest tests/test_registry.py -k codegraph -x` | ❌ Wave 0 — new test needed, following `test_agent_clis_use_supported_install_methods`'s existing pattern (`tests/test_registry.py:141`) |
| REQ-mmdc-install-decision | `mmdc` still resolves via `kind="node"`, `requires` includes both `pnpm` and `puppeteer` | unit (registry integrity) | `uv run pytest tests/test_registry.py -k mmdc -x` | ❌ Wave 0 — extend or add near `test_shipped_node_tools_require_pnpm` (`tests/test_registry.py:732`) |
| REQ-puppeteer-catalog-entries | `puppeteer` exists as its own `Tool`, resolves on both macOS and Linux, requires `pnpm`; a registry-integrity test confirms `mmdc.requires` includes `puppeteer` | unit (registry integrity) + a targeted engine-level test for the co-install fix (Pitfall 1) | `uv run pytest tests/test_registry.py -k puppeteer -x`; a new `tests/test_engine.py` (or equivalent) case asserting the coordinated pnpm invocation for the mmdc+puppeteer pair | ❌ Wave 0 — the registry-level test follows existing patterns; the engine-level co-install test is genuinely new and has no existing analog in this codebase |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_registry.py -x`
- **Per wave merge:** `make test`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_registry.py` — new assertions for `codegraph` (`kind="github_release"` on both platforms, no `kind="node"`/`kind="script"` methods), for `mmdc`'s updated `requires`, and for `puppeteer`'s existence/method-shape/`requires`.
- [ ] A new test (location TBD by planner — `tests/test_engine.py` or a new `tests/test_co_install.py`) verifying the mmdc+puppeteer pnpm-invocation coordination fix (Pitfall 1) actually produces one combined `pnpm add -g` argv rather than two separate ones — this is the one genuinely new piece of runtime behavior in this phase, not just registry data, and needs its own test coverage distinct from registry-integrity checks.
- [ ] No fixture/framework install needed — `pytest`/`pytest-cov` are already present per `pyproject.toml`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — no auth surface touched |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | no (data-only registry change; existing `load_tools` validation already covers new fields) | `installer/model.py`'s existing `_parse_enum`/`_parse_id_list` validation |
| V6 Cryptography | no | N/A |
| V10/V14 (dependency/supply-chain integrity — closest applicable ASVS spirit for this phase) | **yes** | `checksum`-verified `github_release` downloads (already this project's existing mechanism); pnpm's default-deny build-script allowlist as the control for arbitrary-code-execution-via-postinstall risk |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Arbitrary code execution via an npm package's unreviewed `postinstall` script (puppeteer's `node install.mjs`, or any future `kind="node"` entry) | Tampering / Elevation of Privilege | pnpm's default-deny build-script gate + explicit, reviewed `--allow-build=<pkg>`/`pnpm approve-builds` per package — never a blanket allow-all, and never routed through Volta (which per Phase 4's finding runs all install scripts unrestricted) |
| Unverified binary download from GitHub Releases (`codegraph`) | Tampering | `checksum = "SHA256SUMS"` — this project's existing `installer/checksums.py` verification path, already wired into `kind="github_release"`; confirmed the file's format matches the existing parser |
| Silent partial-install (pnpm "ignores" a build script with only a warning, not a failure) masking a broken tool as "successfully installed" | Repudiation / Denial of Service (of the feature, not the system) | Surfacing puppeteer's postinstall outcome distinctly (not just "pnpm add -g exited 0") is worth the planner's attention — this project's existing `InstallOutcome`/`verified` field pattern (already distinguishes checksum-verified downloads from unverified ones) is a reasonable template to extend, though this is a discretionary UX call, not a hard security requirement |

## Sources

### Primary (HIGH confidence)
- `gh api repos/colbymchenry/codegraph/releases/latest` — live GitHub Releases API call, this session: exact asset names, checksum file, tag `v1.6.0`
- `installer/registry.toml:1472-1487` — Phase 4's own already-committed, verbatim-quoted volta-internals finding (read this session)
- `installer/engine.py`, `installer/deps.py`, `installer/executors.py`, `installer/model.py`, `installer/download.py`, `installer/resolve.py`, `installer/checksums.py`, `installer/app.py` — read in full or by targeted section this session
- `tests/test_registry.py` — read for existing registry-integrity test conventions (`test_shipped_node_tools_require_pnpm`, `test_agent_clis_use_supported_install_methods`)
- `unpkg.com/@mermaid-js/mermaid-cli/package.json`, `unpkg.com/puppeteer/package.json` — live package.json fetches this session: peerDependencies, scripts/postinstall, engines
- `pnpm view puppeteer version`, `pnpm view @mermaid-js/mermaid-cli version`, `brew info mermaid-cli` — live local commands this session

### Secondary (MEDIUM confidence)
- `pnpm.io/global-packages`, `pnpm.io/cli/approve-builds` — official pnpm documentation, fetched this session
- `raw.githubusercontent.com/mermaid-js/mermaid-cli/master/README.md` — official upstream README, fetched this session (Homebrew deprecation statement)
- `github.com/mermaid-js/mermaid-cli/issues/1122` — live GitHub issue, fetched this session
- `raw.githubusercontent.com/puppeteer/puppeteer/main/docs/troubleshooting.md` — official puppeteer docs, fetched this session (Debian/CentOS shared-library lists)
- `raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh` — upstream install script, fetched this session (extraction/placement logic)

### Tertiary (LOW confidence)
- General WebSearch results on puppeteer's install.mjs Chrome-for-Testing download behavior (buildId matching, cache path) — corroborated by, but not a primary source for, the postinstall-script finding above, which rests on the primary `package.json` read instead
- General WebSearch results on Fedora/Arch community workarounds for headless-Chromium shared libraries — explicitly NOT used to populate an automated package list (see Open Questions)

## Metadata

**Confidence breakdown:**
- Standard stack (codegraph distribution, mmdc/puppeteer versions and dependency shape): HIGH — every load-bearing claim confirmed via a live API/registry/package.json fetch or a direct source-file read this session
- Architecture (pnpm co-install/peer-dependency isolation problem): HIGH on the *existence and mechanism* of the problem (pnpm's own docs are explicit and this project's engine code was read directly); MEDIUM on the *specific fix* recommended (Pitfall 1's `co_install` param is one reasonable design, explicitly flagged as within "Claude's Discretion" per CONTEXT.md, not the only possible one)
- Pitfalls: HIGH — each pitfall traces to a specific, quoted primary source (official docs, a live GitHub issue, or this project's own source code)
- Fedora/Arch system-library package names: LOW — explicitly flagged as an open gap, not guessed

**Research date:** 2026-09-05
**Valid until:** 30 days for the architectural/mechanism findings (pnpm's isolation model, puppeteer's peerDependency shape); re-verify package versions (`mmdc`/`puppeteer`/`codegraph` releases) if this research is reused after roughly 2026-10-05, given this ecosystem's release cadence.
