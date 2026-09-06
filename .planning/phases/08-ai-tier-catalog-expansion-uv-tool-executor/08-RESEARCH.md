# Phase 8: AI Tier Catalog Expansion & uv-tool Executor - Research

**Researched:** 2026-09-06
**Domain:** Registry-driven CLI tool installation (Python/uv packaging, GitHub Releases, vendor curl\|bash scripts), AI-agent-host companion tooling
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Recommends wiring scope**
- **D-01:** Not a uniform `recommends = ["codegraph", "graphify", "rtk"]` blanket-applied to all five agent hosts. Per the user: research which of codegraph/graphify/rtk actually applies to which host CLI — "no all apply for every host agent cli." `antigravity` is excluded from this phase's recommends wiring for now ("You can deio [dejo/leave out] antigravity for now") — antigravity still gets its catalog entry (install method, D-02 below) but does NOT get a `recommends` list populated in this phase; that can be revisited later once antigravity's own tool ecosystem is better understood.
- **How to apply:** the remaining four hosts (`claude`, `opencode`, `codex`, `cursor-agent`) each get a `recommends` list, but the *members* of that list are a per-host research question, not a fixed constant — e.g. determine whether `rtk` (a git/token-cost tool) makes sense as a recommendation on every one of the four, or only some.

**Antigravity/cursor-agent install-method verification bar**
- **D-02:** If research finds the only official install method for `antigravity` or `cursor-agent` is a vendor-provided curl\|bash-style script (not brew, not a package manager), that is acceptable and should be used — do not hold out for a stronger alternative or omit the tool. This matches the project's existing convention of trusting a tool's own official install script (e.g. `oh-my-zsh`'s official script, Phase 7) over inventing a substitute. Confirm and record the live-verified current script/method rather than assuming.

### Claude's Discretion
- Exact `recommends` membership per host (`claude`/`opencode`/`codex`/`cursor-agent`) among `codegraph`/`graphify`/`rtk` — a research call at planning/implementation time per D-01, informed by what each tool actually does and whether it fits that host's typical workflow.
- Whether antigravity's install script needs any safety review beyond "official vendor source, non-interactive" — same bar as other `kind="script"` entries in this codebase, no special-casing needed per D-02.

### Deferred Ideas (OUT OF SCOPE)
- Antigravity's own `recommends` wiring — deferred, not dropped; revisit once antigravity's typical companion-tool usage is better understood (not blocking Phase 8's other success criteria).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-uv-tool-executor | New `installer/executors.py` `kind="uv-tool"`, mirroring `"node"`'s shape (`uv tool install <pypi_pkg>` instead of `pnpm add -g <npm_pkg>`); `graphify`'s entry uses it (`kind="uv-tool"`, package `graphifyy`, `requires = ["uv"]`). | Live-fetched `graphify`'s own README confirms `uv tool install graphifyy` as the vendor-recommended install command and that the resulting CLI command is `graphify` (double-y is PyPI-only). Executor design mirrors `_node` in `installer/executors.py` but is simpler — `uv` carries none of pnpm's wrapper/redirect complications (see Architecture Patterns, Pattern 1). |
| REQ-agent-host-entries | `antigravity`, `cursor-agent` as ai-tier entries via their verified official install method (not assumed); `codegraph` via `kind="github_release"` (inherited, not re-verified). | `codegraph` already exists in `registry.toml` (landed in Phase 5, `REQ-codegraph-github-release` — verified there, not re-verified here, per D-02/canonical-refs). Live-fetched both vendor install scripts this session for `antigravity` (`curl -fsSL https://antigravity.google/cli/install.sh \| bash`) and `cursor-agent` (`curl https://cursor.com/install -fsS \| bash`) — see Code Examples. Both are the *only* official method; no brew/native-package path exists for either CLI. |
| REQ-rtk-github-release | `rtk` registry entry, `kind="github_release"` from `rtk-ai/rtk`, checksum-verified against `checksums.txt`. | Live GitHub Releases API call confirms asset names, `checksums.txt` presence/format, and default branch `develop`. A previously-unknown-to-CONTEXT.md Homebrew formula `rtk` was also found live and is recommended as an additional fallback method (not a replacement for the locked `github_release` requirement) — see Standard Stack. |
| REQ-recommends-wiring-agent-hosts | Instantiate `Tool.recommends` with real per-host data for `claude`/`opencode`/`codex`/`cursor-agent` (antigravity excluded, D-01). | Live research into what `codegraph`, `graphify`, and `rtk` each document as supported integration hosts (README/PyPI metadata) — see Architecture Patterns, Pattern 3 and Common Pitfalls. |
</phase_requirements>

## Summary

This phase adds one new executor kind and four registry entries to an already-mature,
convention-heavy `registry.toml`/`installer/executors.py` pair. `codegraph` (the fifth
tool named in the phase description) is **already in the registry** — it landed in
Phase 5 (`REQ-codegraph-github-release`) and needs no new work here; the only remaining
gap for it is being named in the new `recommends` lists.

The new `kind="uv-tool"` executor is structurally the simplest executor in the file:
unlike `_node`, which must resolve `pnpm`'s real absolute path to route around this
project's own argv-conditional wrapper, `uv` carries no ban/redirect entry in
`installer/guards.py` and needs no such indirection — `runner(["uv", "tool", "install",
pypi_pkg])` is the whole body. `graphify`'s own README (live-fetched this session)
names `uv tool install graphifyy` as its officially recommended install path and
confirms the resulting command is `graphify` (the double-y is a PyPI-namespace
workaround, not a CLI rename) — this exactly matches what CONTEXT.md already asserted,
now independently verified against the vendor's own install instructions rather than
taken on faith.

`antigravity` and `cursor-agent` both install through vendor-hosted curl\|bash scripts
with no brew, cask, or native-package alternative — confirmed by fetching both install
scripts live this session (not merely reading about them). Per D-02 this is the
accepted, expected outcome and mirrors this registry's existing `codex`/`claude`
pattern (script + macOS cask, except neither `antigravity` nor `cursor-agent` has a
matching CLI-shipping cask — the one Homebrew cask that does exist for each vendor,
`cursor` and `antigravity`, installs the **GUI IDE app**, a different product from the
terminal CLI this phase catalogs). `cursor-agent`'s own install script creates two
symlinks to the same binary — `agent` (primary) and `cursor-agent` (legacy) — which is
why `cmd = "cursor-agent"` (matching this project's and Phase 10's existing framing) is
a real, vendor-created entry point, not an invented one.

`rtk` gets a checksum-verified `github_release` entry from `rtk-ai/rtk`, confirmed live
against the GitHub Releases API (tag `v0.48.0` at research time, `checksums.txt`
present in the standard `<sha256>  <filename>` multi-line format this project's parser
already handles, default branch `develop`). Research also surfaced a genuine Homebrew
formula `rtk` (bare name, homebrew-core) not mentioned in CONTEXT.md — verified via
`formulae.brew.sh` to be the same project (matching homepage, description, and exact
version `0.48.0`) rather than a name collision. Recommendation: add it as an
**additional fallback method** after the locked `github_release` method, matching this
registry's dominant convention (36 of the file's ~50 `github_release` entries pair with
a `brew` fallback) and the Phase 6 brew-preference guideline — this does not contradict
REQ-rtk-github-release, which mandates that a checksum-verified `github_release` method
exists, not that it be the only one.

For `recommends` wiring (REQ-recommends-wiring-agent-hosts), direct research into each
tool's own documentation — rather than assuming the ROADMAP's original illustrative
uniform list — found that `codegraph` (an MCP server, host-agnostic by design),
`graphify` (whose own PyPI description and GitHub README explicitly list Claude Code,
OpenCode, Codex, and Cursor among its supported hosts), and `rtk` (whose README
documents dedicated hook/plugin integrations named `--agent claude`, `--opencode`,
`--codex`, and `--agent cursor`) each have a **real, vendor-documented** integration
path for all four of `claude`/`opencode`/`codex`/`cursor-agent`. The honest per-host
finding is that the fit is uniform across these four — not because it was assumed, but
because each tool's own documentation says so once actually read (D-01's directive was
to verify this rather than default to it, and verification confirmed it) — with one
caveat worth recording: rtk's Codex integration is documentation-based (`AGENTS.md` +
`RTK.md` instructions the model must voluntarily follow) rather than a native
`PreToolUse`-style hook, a materially weaker mechanism than its Claude/Cursor/OpenCode
integrations.

**Primary recommendation:** Add `kind="uv-tool"` to `installer/executors.py` and
`METHOD_KINDS` mirroring `_node`'s dispatch shape but without `real_pnpm()`-style
absolute-path resolution (not needed for `uv`); add `graphify` (`uv-tool`,
`graphifyy`), `cursor-agent` (`script`, `cursor.com/install`), `antigravity` (`script`,
`antigravity.google/cli/install.sh`), and `rtk` (`github_release` from `rtk-ai/rtk` +
`brew` fallback) to `registry.toml`; set `recommends = ["codegraph", "graphify",
"rtk"]` on `claude`, `opencode`, `codex`, and the new `cursor-agent` entry (not on
`antigravity`, per D-01).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `uv-tool` executor dispatch | API / Backend (installer engine) | — | `installer/executors.py` is this project's command-construction layer; a new method `kind` is a pure backend concern, no UI surface changes |
| `graphify`/`cursor-agent`/`antigravity`/`rtk` catalog entries | Database / Storage (declarative config) | API / Backend | `registry.toml` is this project's single declarative source of truth (its own top-of-file comment); the entries themselves are inert data, resolved and executed by the backend |
| `recommends` per-host data | Database / Storage (declarative config) | Browser / Client (TUI prompt surface) | The `Tool.recommends` field (Phase 2) is populated as data here; the one-action, non-blocking prompt that *renders* it already exists in `installer/wizard_app.py`/catalog TUI code from Phase 2 and needs no changes |
| Checksum verification for `rtk` | API / Backend (`installer/checksums.py`, `installer/download.py`) | — | Existing, untouched mechanism; this phase only supplies data (`checksum = "checksums.txt"`) that the existing verified-download path already knows how to consume |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `uv` | 0.12.5 (installed locally; project already trusts `uv` as its own toolchain owner) | Runs `uv tool install <pkg>` for the new executor kind | Already the project's own env/dependency manager (CLAUDE.md: "uv owns the environment... never pip/poetry/conda"); `uv tool install` is uv's own documented mechanism for installing standalone Python CLI applications into an isolated venv with a shim on `~/.local/bin` `[CITED: docs.astral.sh/uv/reference/storage — "uv places command-line tools installed via `uv tool install` in ~/.local/bin"]` |
| `graphifyy` (PyPI) | 0.9.55 at research time, 223 releases since 2026-04-04 | The `graphify` CLI/skill — turns a codebase (plus docs/SQL/configs/PDFs) into a queryable local knowledge graph | `[VERIFIED: PyPI registry — pypi.org/pypi/graphifyy/json fetched live this session]`. Vendor's own README (`raw.githubusercontent.com/Graphify-Labs/graphify/.../README.md`, fetched live) states verbatim: *"Official package: The PyPI package is `graphifyy` (double-y). Other `graphify*` packages on PyPI are not affiliated. The CLI command is still `graphify`."* and gives `uv tool install graphifyy` as the first recommended install command. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `cursor-agent` (vendor binary, not a package-registry artifact) | `2026.09.02-c22c1a3` at research time (embedded in the fetched install script's own paths) | Cursor's terminal coding agent | Installed via `curl https://cursor.com/install -fsS \| bash`; no brew/cask CLI equivalent exists (the only Homebrew artifact, cask `cursor`, installs the GUI IDE, a different product — confirmed via `formulae.brew.sh/api/cask/cursor.json`, desc: "Write, edit, and chat about your code with AI") |
| `antigravity` CLI (`agy`, vendor binary) | Resolved per-platform at install time via the script's own manifest fetch (`antigravity-cli-auto-updater-...run.app/manifests/<platform>.json`); no static version pinned by this project | Google's terminal-based Antigravity agent CLI | Installed via `curl -fsSL https://antigravity.google/cli/install.sh \| bash`; the one Homebrew cask that does exist, token `antigravity` (confirmed live via `formulae.brew.sh/api/cask/antigravity.json`, version `2.12.2`, homepage `antigravity.google/product/antigravity-2`), installs the GUI IDE `.dmg`, not the CLI — same GUI/CLI split as Cursor above |
| `rtk` (Rust binary) | `v0.48.0` at research time | "Rust Token Killer" — CLI proxy that reduces LLM-visible token consumption 60-90% on common dev commands (git/docker/pytest/etc.) by rewriting/compressing their output | `[VERIFIED: GitHub Releases API — api.github.com/repos/rtk-ai/rtk/releases/latest fetched live this session]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `kind="github_release"` for `rtk` only | `kind="brew"` only (formula exists, `brew install rtk`) | REQ-rtk-github-release explicitly locks `kind="github_release"` with checksum verification; a brew-only entry would satisfy neither the locked requirement's letter nor its checksum-verification intent (brew already verifies its own bottle hashes, but that is a different trust chain than this project's own `checksums.txt` mechanism the requirement names). Recommendation below keeps `github_release` as the primary/first-resolved method and adds `brew` as a fallback, matching this file's dominant pattern rather than replacing the locked choice. |
| `antigravity`/`cursor-agent` as `kind="cask"` pointing at the GUI app | `kind="script"` for the CLI binary | The cask installs a different product (the IDE), confirmed live for both vendors above. A cask entry here would satisfy REQ-agent-host-entries' letter ("a" verified official install method exists) while installing the wrong artifact for an "agent-facing terminal tool" catalog — rejected. |
| `uv-tool` executor resolving `uv`'s absolute path (mirroring `real_pnpm()`) | Bare `"uv"` in the argv | `installer/guards.py`'s `BANNED`/`REDIRECTED`/`GLOBAL_REDIRECTED` dicts contain no entry for `uv` — there is no installer-managed `uv` wrapper on PATH to route around, unlike pnpm (which this project itself wraps for the npm-global-redirect policy, Phase 4). Bare `"uv"` is correct and simpler; inventing a `real_uv()` seam would be unmotivated complexity for a problem that does not exist for this binary. |

**Installation:**
```bash
uv tool install graphifyy   # produces the `graphify` command (installer/executors.py's new uv-tool kind)
curl https://cursor.com/install -fsS | bash              # cursor-agent (existing script kind)
curl -fsSL https://antigravity.google/cli/install.sh | bash  # antigravity (existing script kind)
# rtk: github_release kind resolves and downloads the checksum-verified tarball automatically
```

**Version verification:** All versions above were confirmed live this session:
```bash
curl -fsS "https://pypi.org/pypi/graphifyy/json" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['info']['version'])"
# -> 0.9.55

curl -fsS "https://api.github.com/repos/rtk-ai/rtk/releases/latest" | python3 -c "import json,sys;print(json.load(sys.stdin)['tag_name'])"
# -> v0.48.0

curl -fsS "https://formulae.brew.sh/api/formula/rtk.json" | python3 -c "import json,sys;print(json.load(sys.stdin)['versions']['stable'])"
# -> 0.48.0  (confirms the brew formula tracks the same upstream project, not a namesake)
```

## Package Legitimacy Audit

> Two of the four new entries (`cursor-agent`, `antigravity`) are vendor-hosted curl\|bash
> scripts, not package-registry artifacts — the npm/pip/cargo-specific legitimacy seam
> does not apply to them the way it applies to `graphifyy`. They are audited below using
> the equivalent live evidence (domain ownership, script content, absence of destructive
> actions) this project's own convention already applies to `codex`/`claude`/`opencode`'s
> identical script-kind entries.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|--------------|---------|-------------|
| `graphifyy` | PyPI | First upload 2026-04-04 (223 releases through 2026-09-05); GitHub repo `Graphify-Labs/graphify` created 2026-04-03 | Not reported by PyPI JSON (no download-count field); GitHub repo has 115,198 stars / 11,183 forks | `github.com/Graphify-Labs/graphify` (Apache-2.0, live-confirmed) | **[SUS]** — automated check flagged `too-new`/`unknown-downloads` | **Flagged, but refuted by direct evidence** — see below |
| `rtk` (release binary) | GitHub Releases (not a package registry ecosystem the seam covers) | Repo created 2026-01-22; 141+ tagged releases through v0.48.0 (2026-09-04) | GitHub repo has 79,019 stars; release asset `download_count` in the thousands per asset (e.g. `rtk-aarch64-apple-darwin.tar.gz`: 6,633) | `github.com/rtk-ai/rtk` (release-bot-signed assets, `rtk-release-bot[bot]`) | OK (manual GitHub-API audit; ecosystem outside the automated seam's npm/pip/crates scope) | Approved |
| `cursor-agent` install script | Vendor script, `cursor.com` (not a package registry) | N/A — official first-party domain of Cursor/Anysphere | N/A | Closed-source vendor product; script fetched and read verbatim this session, contains no destructive/exfiltrating actions beyond the documented download+symlink | OK (script-trust convention, matches `codex`/`claude`) | Approved |
| `antigravity` install script | Vendor script, `antigravity.google` (not a package registry) | N/A — official first-party Google domain | N/A | Closed-source vendor product; script fetched and read verbatim this session (SHA-512-checks its own download against a signed manifest before installing) | OK (script-trust convention) | Approved |

**Refutation of the `graphifyy` [SUS] verdict:** The automated `package-legitimacy check`
seam reported `too-new`/`unknown-downloads`, but its `publishedAt` signal reflects only
the **latest** release's upload timestamp (2026-09-05), not the package's first release.
A direct query of the full PyPI release history (`releases` map in the registry JSON,
223 entries) shows the first upload was **2026-04-04**, and the GitHub source repo
(`Graphify-Labs/graphify`) was created one day earlier (2026-04-03) — five months of
near-daily releases (0.1.1 → 0.9.55), 115K GitHub stars, 11K forks, and an active issue
tracker (1,249 open issues at research time). This is the opposite profile of a
freshly-published or typosquatted package. Per this project's own protocol, the `[SUS]`
tag is still recorded here rather than silently dropped — the planner should still gate
the `graphifyy` install behind a `checkpoint:human-verify` task, but the accompanying
evidence above should travel with that checkpoint so the reviewer is not starting from
zero.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** `graphifyy` — planner must add a
`checkpoint:human-verify` task before the `graphify` install method ships, carrying the
refutation evidence above.

## Architecture Patterns

### System Architecture Diagram

```
 registry.toml (declarative catalog, single source of truth)
        |
        v
 installer/model.py :: load_tools()
        |  parses [[tool]] / [[tool.method]] rows, validates enums (tier/priority/
        |  audience), validates recommends/requires id-lists
        v
 installer/resolve.py :: resolve_methods(tool, platform)
        |  filters methods by os/arch/immutable-Linux/min_os_version,
        |  orders by the priority ladder (script -> download -> native pkg mgr -> brew)
        v
 installer/engine.py :: install_tool(tool, ...)
        |  is_installed() short-circuits ALREADY_INSTALLED (shutil.which(tool.cmd)
        |  or detect_path) BEFORE any executor runs
        |
        +--> installer/executors.py :: execute(method, runner)      [script/node/uv-tool/sdkman/brew/cask/pkg-mgr kinds]
        |         |
        |         +--> NEW: _uv_tool(method, runner)
        |                    runner(["uv", "tool", "install", pypi_pkg])
        |
        +--> installer/download.py :: install_download(method, ctx) [github_release/tarball kinds]
                  |
                  +--> _resolve_target(): renders {arch.*} tokens into asset/checksum
                  |    names, resolves the release tag via GitHub API (releases/latest)
                  +--> installer/checksums.py :: expected_sha256() / sha256_file()
                       verifies the download against checksums.txt before placing the
                       binary in ~/.local/bin (or ~/.local/opt/<bin>/ for archives)

 installer/model.py :: Tool.recommends (Phase 2, unchanged this phase)
        |
        v
 TUI catalog view (installer/catalog_tui.py / wizard_app.py, unchanged this phase)
        |  selecting claude/opencode/codex/cursor-agent surfaces a one-action,
        v  non-blocking prompt naming recommends — never auto-installs
 (no new UI code needed — this phase supplies DATA into an existing mechanism)
```

### Recommended Project Structure

No new files. Changes land in three existing files:
```
installer/
├── model.py         # METHOD_KINDS gains "uv-tool"
├── executors.py      # new _uv_tool() function + EXECUTORS["uv-tool"] entry
└── registry.toml      # 4 new/edited [[tool]] blocks: graphify, cursor-agent,
                        # antigravity, rtk; recommends= edits on claude/opencode/codex
```

### Pattern 1: `uv-tool` executor — deliberately simpler than `node`

**What:** A new `EXECUTORS["uv-tool"]` dispatch function that runs
`uv tool install <pypi_pkg>`.
**When to use:** Any AI-tier (or future) Python-distributed CLI this project wants to
install via its own already-trusted `uv` toolchain rather than a global `pip install`
(which CLAUDE.md and `installer/guards.py`'s existing `pip`/`pip3` hard-block already
forbid as an install path for end users of this installer).
**Why simpler than `_node`:** `installer/executors.py`'s `_node()` must resolve pnpm's
**real, absolute path** via `real_pnpm()` because this project's own package-manager
redirect policy (Phase 4, `installer/guards.py`) may have placed an argv-conditional
pnpm **wrapper** earlier on PATH — using a bare `"pnpm"` string risks the install
recursing into this project's own shim. `uv` has no such entry in `guards.py`'s
`BANNED`/`REDIRECTED`/`GLOBAL_REDIRECTED` dicts `[VERIFIED: installer/guards.py:39-127
— grepped this session; no "uv" key appears in any of the three dicts]`, so there is no
wrapper to route around and a bare `"uv"` argv element is correct.
**Example:**
```python
# installer/executors.py — mirrors the existing _node() shape (require_str, EXECUTORS
# dict registration), omitting pnpm's real-path resolution because it does not apply.
def _uv_tool(method: Method, runner: Runner) -> None:
    pypi_pkg = require_str(method, "pypi_pkg")
    runner(["uv", "tool", "install", pypi_pkg])


EXECUTORS: dict[str, Callable[[Method, Runner], None]] = {
    "script": _script,
    "node": _node,
    "uv-tool": _uv_tool,   # new
    "sdkman": _sdkman,
    "dnf": _dnf,
    "apt": _apt,
    "pacman": _pacman,
    "brew": _brew,
    "cask": _cask,
}
```
And in `installer/model.py`:
```python
METHOD_KINDS = (
    "script",
    "node",
    "uv-tool",   # new
    "sdkman",
    "github_release",
    "tarball",
    "app",
    "dnf",
    "apt",
    "pacman",
    "rpm_ostree",
    "brew",
    "cask",
)
```

### Pattern 2: registry entry for the new `uv-tool` kind — `graphify`

**What:** A `[[tool]]` block with a single `kind="uv-tool"` method.
**When to use:** Exactly this shape for any future PyPI-distributed CLI.
**Example (registry.toml addition):**
```toml
# Verified 2026-09-06: graphify's own README (raw.githubusercontent.com/
# Graphify-Labs/graphify/.../README.md, fetched live) states "The PyPI package is
# graphifyy (double-y). Other graphify* packages on PyPI are not affiliated. The CLI
# command is still graphify." and gives `uv tool install graphifyy` as its first
# recommended install command. PyPI JSON (pypi.org/pypi/graphifyy/json) confirms 223
# releases since 2026-04-04, requires_python ">=3.10" (handled internally by uv's own
# venv creation, no action needed here), and a pure-wheel distribution
# (graphifyy-0.9.55-py3-none-any.whl) — no native build step, no arbitrary
# postinstall script executes at install time (wheels do not run setup.py).
[[tool]]
id = "graphify"
name = "Graphify"
category = "dev"
cmd = "graphify"
priority = "P1"
audience = "ai"
tier = "ai"
requires = ["uv"]
desc = "Turns a codebase (plus docs, SQL schemas, configs, PDFs) into a queryable local knowledge graph for AI agents."
[[tool.method]]
kind = "uv-tool"
pypi_pkg = "graphifyy"
```

### Pattern 3: `recommends` wiring — real per-host data, not the illustrative placeholder

**What:** Replacing the Phase 2 illustrative `recommends = ["rg", "fd", "jq"]` (still
present on `claude`/`opencode` today, each with a comment explicitly deferring the real
set to this phase) with the researched real set, and adding the same set to the new
`cursor-agent` entry and to the already-existing `codex` entry.
**When to use:** Exactly this data, justified per host below.
**Per-host research finding:**

| Host | `codegraph` | `graphify` | `rtk` | Evidence |
|------|:-:|:-:|:-:|----------|
| `claude` | yes | yes | yes | `rtk`'s README documents `rtk init -g` for Claude Code with a native `PreToolUse` hook — the strongest of its integrations, and its flagship one (this project's own global CLAUDE.md/RTK.md already documents living daily use of rtk with Claude Code). `graphify`'s README/PyPI description name Claude Code first among supported hosts. `codegraph` is an MCP server — Claude Code's MCP support is well-established. |
| `opencode` | yes | yes | yes | `rtk` README: `rtk init -g --opencode` via a real "Plugin TS (`tool.execute.before`)" integration — a native hook, not an instructions file. `graphify`'s PyPI description explicitly lists OpenCode among its 16 supported hosts. `opencode` supports MCP server configuration (`opencode.json`), matching `codegraph`'s MCP delivery. |
| `codex` | yes | yes | yes (weaker mechanism) | `rtk` README: `rtk init -g --codex` — documented as `"AGENTS.md + RTK.md instructions"`, i.e. the model must read and voluntarily follow a convention file rather than a runtime-enforced hook. This is real and vendor-documented, but materially weaker than the Claude/Cursor/OpenCode hook integrations — worth surfacing to the planner as a caveat, not a reason to omit it (no stronger mechanism exists for Codex today). `graphify`'s README lists Codex among its explicitly supported skill hosts. Codex CLI supports MCP servers via `~/.codex/config.toml` `[CITED: developers.openai.com/codex/mcp]`, confirmed live via WebSearch this session. |
| `cursor-agent` | yes | yes | yes | `rtk` README: `rtk init -g --agent cursor` via a native `preToolUse` hook (`hooks.json`) — as strong as the Claude integration. `graphify`'s README/PyPI description list Cursor explicitly. Cursor CLI documents its own MCP support, auto-detecting `.cursor/mcp.json` `[CITED: cursor.com/docs/cli/mcp]`, confirmed live via WebSearch this session. |
| `antigravity` | excluded (D-01) | excluded (D-01) | excluded (D-01) | Deferred per locked decision, regardless of what research might otherwise support (rtk's README does list a Google Antigravity integration, for the record, in case this is revisited later). |

**Recommendation:** `recommends = ["codegraph", "graphify", "rtk"]` on `claude`,
`opencode`, `codex`, and the new `cursor-agent`. This is *not* the ROADMAP's original
uniform-list assumption applied blindly — it is the outcome of actually reading each
tool's own documentation per D-01's instruction, and the fit happens to be uniform
across these four hosts once verified. The one asymmetry worth carrying into the
registry as a comment is rtk's weaker, convention-based Codex integration.

**Example (registry.toml edits):**
```toml
# real companion set for this ai-tier catalog (Phase 8, REQ-recommends-wiring-agent-hosts):
# codegraph (MCP server, host-agnostic), graphify (explicitly supports this host per its
# own README), rtk (native hook integration for this host — see 08-RESEARCH.md's
# per-host table for the one exception, codex, where rtk's integration is
# instructions-based rather than a runtime hook).
recommends = ["codegraph", "graphify", "rtk"]
```

### Anti-Patterns to Avoid
- **Installing the GUI app cask when the catalog wants the CLI:** Both `cursor` and
  `antigravity` Homebrew casks exist and are real, but they install the IDE, not the
  terminal agent. Wiring either as this phase's `[[tool.method]]` would silently give
  users the wrong artifact while technically satisfying "a verified official install
  method exists."
- **Treating the seam's `[SUS]` verdict on `graphifyy` as license to silently approve or
  silently drop the package:** Neither is correct — the verdict is recorded, refuted
  with direct evidence, and still routed to a `checkpoint:human-verify` task per this
  project's own protocol.
- **Replacing `rtk`'s locked `kind="github_release"` method with `kind="brew"` because a
  formula was found:** REQ-rtk-github-release specifically names the checksum-verified
  download mechanism; brew is an *additional* fallback, ordered after it, not a
  substitute.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Installing a PyPI-distributed CLI into an isolated environment | A custom venv-creation + pip-install + shim-symlink dance | `uv tool install <pkg>` (this phase's whole `uv-tool` executor) | `uv` already does isolated-env creation, dependency resolution, and `~/.local/bin` shimming as one command — reimplementing any part of that inside this project would duplicate work `uv` already does correctly and is already this project's trusted toolchain owner |
| Checksum verification for `rtk`'s release tarball | A bespoke sha256 comparison inline in a new function | `installer/checksums.py::expected_sha256`/`sha256_file` via the existing `checksum = "checksums.txt"` param | This exact mechanism already parses the `<hash>  <filename>` multi-line format `rtk`'s `checksums.txt` uses (confirmed by downloading and reading it live this session) — no new parsing code needed, only registry data |
| Detecting whether `cursor-agent`/`antigravity`/`graphify`/`rtk` are already installed | A new detection function per tool | The existing `installer/status.py::is_installed` (`shutil.which(tool.cmd)`, falling back to `detect_path`) | All four new commands land on PATH via `~/.local/bin` shims/symlinks the vendor's own install step creates — `shutil.which` already finds them with zero new code |

**Key insight:** This phase is almost entirely a data-entry exercise against
already-built mechanisms (the executor dispatch table, the download+checksum pipeline,
the `is_installed` detector, the `recommends` prompt). The only genuinely new code is
the ~3-line `_uv_tool` function and its one-line `METHOD_KINDS`/`EXECUTORS`
registration.

## Common Pitfalls

### Pitfall 1: the tier-distribution tripwire test will fail without an update
**What goes wrong:** `tests/test_registry.py::test_registry_tier_distribution_is_pinned`
asserts an exact `Counter` of tools per tier (`"ai": 10` as of the current committed
registry). Adding `graphify`, `cursor-agent`, `antigravity`, and `rtk` (all `tier="ai"`)
without updating this count will fail the test — by design (the test's own comment:
*"Deliberate tripwire: any phase that adds or removes a registry entry... must update
these counts in the same commit"*).
**Why it happens:** The test exists specifically to force this phase (and future ones)
to notice and account for tier-count drift rather than silently changing it.
**How to avoid:** Update the `"ai"` count from 10 to 14 in the same commit that adds the
four entries.
**Warning signs:** `make test` failing on this one assertion is expected mid-phase, not
a bug to work around — it is the test doing its job.

### Pitfall 2: `test_agent_clis_use_supported_install_methods` and
`test_human_agent_clis_are_p0_human_tools` may need extending, not just leaving alone
**What goes wrong:** These two existing tests currently enumerate only
`codex`/`claude`/`opencode` by name (`tests/test_registry.py:62-68`, `167-188`). Adding
`cursor-agent` as a fourth P0 human-agent CLI with the same shape (script + optionally
no cask, since no CLI-matching cask exists) is a natural extension the planner should
consider, but it is a **planning decision**, not a research finding — this file
documents the existing test shape so the planner can decide whether `cursor-agent`
belongs in that assertion set.
**Why it happens:** These tests were written before `cursor-agent` existed in the
registry.
**How to avoid:** Read both tests before writing new registry entries so the new
entries' `[m.kind for m in tool.methods]` shape is deliberately compatible with
whatever assertion style the plan extends them with.
**Warning signs:** A green test suite that never actually asserts anything about the
new `cursor-agent`/`antigravity` entries' method shape — the existing coverage pattern
in this file is to assert exact method-kind lists per agent CLI, and silently skipping
that for the two new entries would be a coverage regression matching the file's own
established rigor bar.

### Pitfall 3: `cursor-agent`'s primary symlink is `agent`, not `cursor-agent`
**What goes wrong:** The live-fetched install script creates **two** symlinks —
`~/.local/bin/agent` (primary, shown in all of the script's own "next steps" messaging)
and `~/.local/bin/cursor-agent` (explicitly labeled "legacy" in the script's own
comment) — both pointing at the same binary. A registry entry with `cmd = "agent"`
would risk colliding with an unrelated `agent` binary from a different installed CLI on
a machine that has more than one agent tool (a real, documented collision risk per
community discussion found during research).
**Why it happens:** Cursor renamed its primary command from `cursor-agent` to `agent`
at some point but kept the old name as a compatibility symlink.
**How to avoid:** Use `cmd = "cursor-agent"` (the legacy-but-still-real, collision-safe
name), matching what CONTEXT.md, ROADMAP Phase 8/10, and REQUIREMENTS.md already
consistently call this tool.
**Warning signs:** A registry entry with `cmd = "agent"` would still resolve
`is_installed` correctly in isolation, so this would not be caught by tests unless a
test specifically asserts the command name — verify the exact string when writing the
entry rather than trusting memory of "the Cursor CLI command."

### Pitfall 4: `rtk`'s Linux release assets are asymmetric — musl on amd64, gnu on arm64
**What goes wrong:** A single `{arch.machine}-unknown-linux-{libc}.tar.gz` template
cannot cover both Linux architectures, because the upstream project publishes
`rtk-x86_64-unknown-linux-musl.tar.gz` for amd64 but
`rtk-aarch64-unknown-linux-gnu.tar.gz` for arm64 (confirmed via the live `checksums.txt`
listing) — a naive single-template method would 404 on one architecture.
**Why it happens:** Upstream's own release pipeline (visible from the sibling
`.rpm`/`.deb` assets) targets glibc distros broadly but only ships a musl (static)
build for the more common amd64 target.
**How to avoid:** Declare two separate Linux `github_release` methods, gated by
`arch = ["amd64"]` and `arch = ["arm64"]` respectively — mirroring this registry's
existing precedent for exactly this shape (`gnu-bash`'s two arch-split brew methods,
`puppeteer`'s arch-gated Linux method).
**Warning signs:** An arm64 Linux machine reporting a download 404 or checksum mismatch
that an amd64 machine does not reproduce.

### Pitfall 5: `graphifyy`'s automated legitimacy check flags it `[SUS]` on a stale signal
**What goes wrong:** Running the package-legitimacy seam against `graphifyy` returns
`too-new`/`unknown-downloads`, which — taken at face value — would suggest a fresh,
unverified package.
**Why it happens:** The seam's `publishedAt` signal reflects only the most recent
release's upload timestamp; `graphifyy` publishes very frequently (223 releases across
five months), so its *latest* release is always recent even though the *package* is
not.
**How to avoid:** Cross-check the full PyPI `releases` history (not just the latest
entry) and the GitHub repo's `created_at`/`stargazers_count` before accepting or
rejecting an automated verdict at face value — exactly what this research session did
(see Package Legitimacy Audit).
**Warning signs:** Trusting a single-field heuristic without checking whether that
field actually measures "package age" versus "latest release age" — they are not the
same thing for a fast-shipping project.

## Code Examples

### `uv-tool` executor (new, `installer/executors.py`)
```python
def _uv_tool(method: Method, runner: Runner) -> None:
    pypi_pkg = require_str(method, "pypi_pkg")
    runner(["uv", "tool", "install", pypi_pkg])
```
Register in `EXECUTORS` and `METHOD_KINDS` as shown in Architecture Patterns, Pattern 1.

### `graphify` registry entry (new)
See Architecture Patterns, Pattern 2 for the full annotated block.

### `cursor-agent` registry entry (new)
```toml
# Verified 2026-09-06: install script fetched live (curl -fsS https://cursor.com/install)
# and read verbatim. It self-detects OS/arch, downloads a per-platform tarball from
# downloads.cursor.com, and creates TWO symlinks to the same extracted binary:
# ~/.local/bin/agent (primary, shown in the script's own usage messaging) and
# ~/.local/bin/cursor-agent (the script's own comment labels this "legacy"). cmd here
# is the legacy-but-real, collision-safe name — see 08-RESEARCH.md Pitfall 3. No brew
# formula/cask installs this CLI: the only Homebrew artifact for this vendor, cask
# `cursor` (formulae.brew.sh/api/cask/cursor.json, confirmed live), installs the GUI
# IDE app, a different product.
[[tool]]
id = "cursor-agent"
name = "Cursor Agent CLI"
category = "ai"
cmd = "cursor-agent"
priority = "P0"
audience = "human"
tier = "ai"
recommends = ["codegraph", "graphify", "rtk"]
desc = "Cursor's terminal coding agent; installs via its own official curl|bash script, no brew/cask CLI equivalent exists."
[[tool.method]]
kind = "script"
url = "https://cursor.com/install"
shell = "bash"
bin_dir = "~/.local/bin"
```

### `antigravity` registry entry (new)
```toml
# Verified 2026-09-06: install script fetched live
# (curl -fsSL https://antigravity.google/cli/install.sh) and read verbatim. It installs
# a single binary "agy" into ~/.local/bin (default TARGET_DIR), fetches a per-platform
# manifest JSON from a Google-run Cloud Run URL, and verifies the download's SHA-512
# against that manifest before installing — a stronger self-verification than most
# script-kind entries already in this registry. If "agy" already exists at the target
# path the script no-ops with an informational message (the CLI self-updates in the
# background at runtime) rather than reinstalling — is_installed's shutil.which("agy")
# check already short-circuits before this script runs on a second pass, so this
# behavior is inert from this installer's perspective. The Homebrew cask that exists
# for this vendor, token `antigravity` (formulae.brew.sh/api/cask/antigravity.json,
# confirmed live, version 2.12.2), installs the GUI IDE .dmg, a different product from
# this CLI. No recommends per CONTEXT.md D-01 (deferred).
[[tool]]
id = "antigravity"
name = "Antigravity CLI"
category = "ai"
cmd = "agy"
priority = "P1"
audience = "human"
tier = "ai"
desc = "Google's terminal-based Antigravity agent CLI; installs via its own official curl|bash script, self-verifying the download's SHA-512 against a signed manifest."
[[tool.method]]
kind = "script"
url = "https://antigravity.google/cli/install.sh"
shell = "bash"
bin_dir = "~/.local/bin"
```

### `rtk` registry entry (new)
```toml
# Verified 2026-09-06 via the live GitHub Releases API
# (api.github.com/repos/rtk-ai/rtk/releases/latest, tag v0.48.0) and by downloading and
# reading checksums.txt directly: it is the standard multi-line "<sha256>  <filename>"
# format this project's installer/checksums.py already parses (same shape as the
# lazygit/gum/glow/duf/dive entries' shared "checksums.txt" convention above), listing
# every published asset including rtk-x86_64-apple-darwin.tar.gz,
# rtk-aarch64-apple-darwin.tar.gz, rtk-x86_64-unknown-linux-musl.tar.gz, and
# rtk-aarch64-unknown-linux-gnu.tar.gz. Each Linux tarball's top level is a bare "rtk"
# binary with no wrapping directory (confirmed by downloading and running
# `tar -tzf` on both the x86_64-musl and aarch64/x86_64-darwin tarballs this session),
# hence member = "rtk", strip = 0 for every method below — no {ver} placeholder is
# needed in the asset names (upstream's own convention omits it, unlike its sibling
# .deb/.rpm assets). Default branch is `develop`, not `main` (only matters if a future
# change references the branch directly; this project's own resolve_tag mechanism uses
# the GitHub Releases API's "latest" endpoint, never a branch checkout, so this is
# informational only — installer/versions.py:172).
# A genuine Homebrew formula also exists (bare name "rtk", homebrew-core; confirmed via
# formulae.brew.sh/api/formula/rtk.json to be the SAME project — matching homepage
# rtk-ai.app, description, and exact version 0.48.0, not a name collision). Added below
# as a fallback AFTER github_release, per this registry's dominant convention and the
# Phase 6 brew-preference guideline; it does not replace the locked
# REQ-rtk-github-release checksum-verified method.
[[tool]]
id = "rtk"
name = "RTK (Rust Token Killer)"
category = "dev"
cmd = "rtk"
priority = "P1"
audience = "ai"
tier = "ai"
recommends = []
desc = "CLI proxy that rewrites/compresses common dev-command output to cut LLM-visible token usage 60-90%."
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "rtk-ai/rtk"
asset = "rtk-{arch.machine}-apple-darwin.tar.gz"
checksum = "checksums.txt"
member = "rtk"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
arch = ["amd64"]
repo = "rtk-ai/rtk"
asset = "rtk-{arch.machine}-unknown-linux-musl.tar.gz"
checksum = "checksums.txt"
member = "rtk"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
arch = ["arm64"]
repo = "rtk-ai/rtk"
asset = "rtk-{arch.machine}-unknown-linux-gnu.tar.gz"
checksum = "checksums.txt"
member = "rtk"
strip = 0
[[tool.method]]
kind = "brew"
formula = "rtk"
```

### `recommends` edits on existing entries (`claude`, `opencode`, `codex`)
```toml
# real companion set for this ai-tier catalog (Phase 8, REQ-recommends-wiring-agent-hosts):
# codegraph (MCP server, host-agnostic), graphify (explicitly supports this host per its
# own README), rtk (native hook integration for this host — see 08-RESEARCH.md's
# per-host table for the one exception, codex, where rtk's integration is
# instructions-based rather than a runtime hook).
recommends = ["codegraph", "graphify", "rtk"]
```
Applies to `claude`, `opencode` (replacing the Phase 2 illustrative
`recommends = ["rg", "fd", "jq"]` and its now-stale deferral comment) and `codex`
(newly adding the field, which it does not currently declare).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `claude`/`opencode`'s `recommends = ["rg", "fd", "jq"]` (Phase 2 illustrative placeholder, explicitly commented as provisional) | `recommends = ["codegraph", "graphify", "rtk"]` (this phase's real data) | This phase | Matches ROADMAP Phase 2 SC#4's own amendment note: *"Phase 8's `REQ-recommends-wiring-agent-hosts` is where the real companion set lands"* |
| Cursor's primary command name `cursor-agent` | Renamed to `agent`, with `cursor-agent` kept as a compatibility symlink | Some point before this research date (exact date not published; observed via the currently-live install script) | A registry entry naming the newer `agent` command would work today but risks collision with other tools also named `agent`; `cursor-agent` remains the documented, collision-safe choice |

**Deprecated/outdated:** None found — all four new tools are actively maintained
(latest `rtk` release 2026-09-04, latest `graphifyy` release 2026-09-05, both within
two days of this research session).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `antigravity`'s and `cursor-agent`'s priority values (`P1` and `P0` respectively) are this researcher's judgment call, not a locked or vendor-stated fact | Code Examples | Low — priority is a catalog-browsing/ordering hint (`installer/architecture.md`'s own framing), not a correctness-affecting field; the planner can freely adjust without touching install logic |
| A2 | `graphify`'s `priority = "P1"` and `category = "dev"` (mirroring `codegraph`'s existing classification) are this researcher's judgment call | Code Examples | Low — same reasoning as A1 |
| A3 | The exact current version strings recorded in this document (`graphifyy` 0.9.55, `rtk` v0.48.0, Cursor CLI build `2026.09.02-c22c1a3`, Antigravity cask `2.12.2`) will drift; none are pinned in the registry entries above (matching this project's own convention of not pinning vendor-script or `latest`-tag-resolved versions elsewhere in the file) | Standard Stack, Code Examples | Low — informational only; none of the registry entries above hardcode these version strings |

**If this table is empty:** N/A — see entries above; all are low-risk, discretionary
judgment calls rather than load-bearing factual claims.

## Open Questions

1. **Should `cursor-agent`/`antigravity` be added to
   `test_human_agent_clis_are_p0_human_tools`/`test_agent_clis_use_supported_install_methods`?**
   - What we know: both existing tests enumerate `codex`/`claude`/`opencode` by name
     and assert exact method-kind lists; `cursor-agent` has the exact same
     `["script"]`-only shape (no cask), `antigravity` likewise.
   - What's unclear: whether the planner wants to extend these specific tests or add
     new ones scoped to the two new entries.
   - Recommendation: extend the existing tests' tool sets where the shape genuinely
     matches (`cursor-agent` alongside `codex`/`claude`/`opencode` for the P0/human/ai
     assertion), and add focused new assertions for anything entry-specific (the
     dual-symlink finding, the SHA-512 self-verification, the no-cask-for-CLI finding).

2. **Does `graphify install` (the vendor's own skill-registration step, run after
   `uv tool install graphifyy`) belong in this phase or in Phase 9 (postinstall
   hooks)?**
   - What we know: `graphify`'s own README documents a two-step install — package
     install, then `graphify install` to register the skill with whichever AI
     assistants are present on the machine. This is structurally identical to what
     ROADMAP Phase 9 (`REQ-codegraph-mcp-postinstall`) already plans to build generically
     for `codegraph`.
   - What's unclear: whether the planner should scope `graphify install` into this
     phase manually (a one-off, not using the not-yet-built postinstall mechanism) or
     leave it for Phase 9 to pick up once the generic mechanism exists.
   - Recommendation: leave it for Phase 9. This phase's own REQ-uv-tool-executor and
     REQ-agent-host-entries text describe only the *install* step, not skill
     registration; Phase 9 is purpose-built for exactly this "run a follow-up step
     after install" pattern and already names `codegraph` as its proving case — adding
     a second, differently-shaped mechanism here would duplicate Phase 9's own work.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | New `uv-tool` executor / `graphify` install | Yes | 0.12.5 (Homebrew build) | — |
| `brew` | `rtk`'s new fallback method | Yes | 6.0.21 | — |
| `git` | General project tooling (unrelated to this phase's new code) | Yes | 2.55.0 | — |
| Network access to `pypi.org`, `api.github.com`, `github.com`, `cursor.com`,
  `antigravity.google`, `formulae.brew.sh` | All live verification performed this
  session | Yes (all reachable during research) | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none — this phase adds no new environment
requirement beyond what the existing `uv` system-tier entry and the existing
`github_release`/`script`/`brew` executors already assume.

No Tier-3 container (colima+docker) verification was performed for this phase, unlike
Phases 5-7. This is a deliberate scope call, not a gap: this phase's success criteria
(a working `uv-tool` executor, four correctly-shaped registry entries, correct
`recommends` data) are verifiable through this project's existing unit-test style
(`tests/test_executors.py`'s monkeypatched-runner pattern for the new `_uv_tool`
function, `tests/test_registry.py`'s `resolve_methods`-against-a-fake-`Platform`
pattern for the new entries) without executing any real install. The three live
scripts/APIs (`cursor.com/install`, `antigravity.google/cli/install.sh`, the GitHub
Releases API for `rtk`) were fetched and their **content** read and verified this
session — matching this project's own "vendor script trust, not full install-and-run
verification" bar already applied to `codex`/`claude`/`opencode` — but were not
executed end-to-end against a real machine.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-cov (per `pyproject.toml`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_executors.py tests/test_registry.py tests/test_model.py -x` |
| Full suite command | `make test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-uv-tool-executor | `_uv_tool` builds `["uv", "tool", "install", pypi_pkg]` and nothing else | unit | `pytest tests/test_executors.py -k uv_tool -x` | ❌ Wave 0 — new tests, mirroring `test_node_runs_pnpm_add_global_never_bare_npm`'s shape (`_record()`/`Method(kind="uv-tool", ...)`) |
| REQ-uv-tool-executor | Missing `pypi_pkg` param raises `ExecutorError` | unit | `pytest tests/test_executors.py -k uv_tool_without_pkg -x` | ❌ Wave 0 |
| REQ-agent-host-entries | `cursor-agent`/`antigravity` resolve exactly `["script"]` on every supported platform, with the exact locked `url` | unit | `pytest tests/test_registry.py -k agent_clis -x` | ❌ Wave 0 — extend or add alongside `test_agent_clis_use_supported_install_methods` |
| REQ-rtk-github-release | `rtk` resolves `["github_release", "brew"]` on Linux/macOS, with the correct arch-split asset names and `checksum = "checksums.txt"` on every `github_release` method | unit | `pytest tests/test_registry.py -k rtk -x` | ❌ Wave 0 |
| REQ-recommends-wiring-agent-hosts | `claude`/`opencode`/`codex`/`cursor-agent` each declare `recommends == ("codegraph", "graphify", "rtk")`; `antigravity` declares `recommends == ()` | unit | `pytest tests/test_registry.py -k recommends -x` | ❌ Wave 0 |
| (regression) | Tier-distribution tripwire updated in the same commit | unit | `pytest tests/test_registry.py::test_registry_tier_distribution_is_pinned -x` | ✅ exists — value must change from `"ai": 10` to `"ai": 14` |

### Sampling Rate
- **Per task commit:** `pytest tests/test_executors.py tests/test_registry.py tests/test_model.py -x`
- **Per wave merge:** `make test`
- **Phase gate:** Full suite green (`make validate && make test`) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_executors.py` — new `_uv_tool` tests (happy path, missing-param error path)
- [ ] `tests/test_registry.py` — new/extended tests for `cursor-agent`, `antigravity`,
      `rtk`, `graphify` method shapes, and the four hosts' `recommends` tuples
- [ ] `tests/test_registry.py::test_registry_tier_distribution_is_pinned` — count update
      (existing test, not a new file)
- [ ] Framework install: none — pytest/coverage already configured project-wide

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This phase installs CLI tools; it does not add any authentication surface to the installer itself |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes | `require_str`/`_parse_id_list`/`_parse_enum` in `installer/model.py` already validate every registry field (including the new `pypi_pkg` param, via the existing `require_str` helper `_uv_tool` reuses) at load time, rejecting malformed TOML before any executor runs |
| V6 Cryptography | Yes | `installer/checksums.py`'s sha256 verification (already-existing mechanism) covers `rtk`'s new `github_release` methods; Antigravity's own install script additionally performs its own SHA-512 verification against a signed manifest before this project's code ever runs (vendor-side, outside this project's control but confirmed present by reading the script live) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Curl\|bash install script tampering (a MITM or compromised CDN serving a malicious script) | Tampering | Already-accepted residual risk for every `kind="script"` entry in this registry (`codex`, `claude`, `opencode`, `uv`, `brew`, `pnpm`, `oh-my-zsh`, `sdkman`, `bun`, `fnm`, `volta`'s Linux path); this phase's two new script entries (`cursor-agent`, `antigravity`) inherit the exact same accepted posture per D-02 — HTTPS-only URLs, official first-party vendor domains, no new mitigation invented here |
| Typosquatted or freshly-published PyPI package masquerading as a legitimate tool | Spoofing | The Package Legitimacy Gate protocol (this document's Package Legitimacy Audit section) — `graphifyy`'s `[SUS]` automated verdict is recorded, refuted with direct release-history/repo-age evidence, and still routed to a `checkpoint:human-verify` task rather than silently trusted or silently blocked |
| Checksum-less GitHub release binary tampering | Tampering | `rtk`'s `checksum = "checksums.txt"` on every `github_release` method routes through the existing, already-tested `installer/checksums.py` verification path — `installer/engine.py`'s `checksum_policy="fail"` default halts the install on any mismatch rather than falling through silently |

## Sources

### Primary (HIGH confidence)
- `api.github.com/repos/rtk-ai/rtk/releases/latest` — fetched live this session (tag `v0.48.0`, asset list, `checksums.txt` presence)
- `api.github.com/repos/rtk-ai/rtk` — fetched live this session (`default_branch: develop`, stars, created_at)
- `github.com/rtk-ai/rtk/releases/download/v0.48.0/checksums.txt` — downloaded and read verbatim this session
- Two `rtk` release tarballs (`rtk-x86_64-unknown-linux-musl.tar.gz`, `rtk-x86_64-apple-darwin.tar.gz`) — downloaded and inspected with `tar -tzf` this session to confirm member layout (bare `rtk` file, no wrapping directory)
- `pypi.org/pypi/graphifyy/json` — fetched live this session (version, full release history, requires_python, project_urls, wheel filename)
- `raw.githubusercontent.com/rtk-ai/rtk/develop/INSTALL.md` and `.../develop/README.md` — fetched live this session
- `raw.githubusercontent.com/Graphify-Labs/graphify/.../README.md` (via the PyPI package description field) — the vendor's own install instructions, official-package disclaimer, and CLI-command confirmation
- `api.github.com/repos/Graphify-Labs/graphify` — fetched live this session (stars, forks, license, created_at)
- `curl -fsS https://cursor.com/install` — the actual, live, current install script fetched and read verbatim this session
- `curl -fsSL https://antigravity.google/cli/install.sh` — the actual, live, current install script fetched and read verbatim this session
- `formulae.brew.sh/api/cask/cursor.json`, `.../cask/antigravity.json`, `.../formula/rtk.json`, `.../cask/kitty.json` (cross-referenced from Phase 7 precedent) — fetched live this session
- `installer/executors.py`, `installer/model.py`, `installer/download.py`, `installer/guards.py`, `installer/checksums.py`, `installer/assets.py`, `installer/status.py`, `installer/versions.py`, `installer/registry.toml`, `tests/test_registry.py`, `tests/test_executors.py` — all read in full or in relevant part this session

### Secondary (MEDIUM confidence)
- `developers.openai.com/codex/mcp` (via WebSearch summary) — Codex CLI's MCP server support and `~/.codex/config.toml` location
- `cursor.com/docs/cli/mcp` (via WebSearch summary) — Cursor CLI's MCP auto-detection of `.cursor/mcp.json`
- `docs.astral.sh/uv/reference/storage` (via WebSearch summary) — `uv tool install`'s default `~/.local/bin` target

### Tertiary (LOW confidence)
- None used as load-bearing claims; every WebSearch-only finding above was either cross-checked against a live API/script fetch or explicitly marked `[CITED]` rather than `[VERIFIED]`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version/URL/asset-name claim was confirmed via a live API call, script fetch, or file download this session, not training-data recall
- Architecture: HIGH — the `uv-tool` executor design was checked directly against the existing `_node`/`guards.py` code, not assumed by analogy
- Pitfalls: HIGH — all five pitfalls trace to a specific live artifact (a fetched script, a downloaded checksums file, an existing test's exact assertion) rather than general worry

**Research date:** 2026-09-06
**Valid until:** 2026-10-06 (30 days — vendor install scripts/URLs and release tags are
the most likely things to drift; re-verify `cursor.com/install`, `antigravity.google/cli/install.sh`,
and `rtk-ai/rtk`'s latest release/checksums.txt if this phase is revisited after that date)
