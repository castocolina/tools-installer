---
phase: 08-ai-tier-catalog-expansion-uv-tool-executor
reviewed: 2026-09-06T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - installer/executors.py
  - installer/model.py
  - installer/resolve.py
  - installer/registry.toml
  - tests/test_catalog_tui.py
  - tests/test_executors.py
  - tests/test_model.py
  - tests/test_registry.py
  - tests/test_resolve.py
  - tests/test_status.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-09-06
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Diff range `85f02a5f4f5fa6a55e845079b8d0c75b10b5b9c8..HEAD` was read in full
(`installer/executors.py`, `installer/model.py`, `installer/resolve.py`,
`installer/registry.toml`, and the five touched test files), cross-checked
against the collaborator modules the new code actually calls at runtime
(`installer/engine.py::install_tool`, `installer/deps.py::resolve_dependencies`,
`installer/app.py::run_wizard`, `installer/status.py::is_installed`,
`installer/guards.py`, `installer/assets.py`, `installer/selection.py`), and
against the phase's own planning trail (`08-CONTEXT.md`, `08-01..04-PLAN.md`,
`08-01..04-SUMMARY.md`, `08-REVIEWS.md`) to avoid re-flagging findings the
three recorded cross-AI plan-review cycles already surfaced and fixed before
execution (e.g. the `resolve.py` `KeyError` gap, the `SIDECAR_VERIFIED` vs
`CHECKSUM_FILE_VERIFIED` misfile, the comment-locality test, the stale
`test_catalog_tui.py` fixture, the missing Tier-3 evidence, the RTK
arm64-Linux tarball claim).

Several candidate findings were investigated and **ruled out** after tracing
the actual call chain, specifically:
- `uv-tool`'s `pypi_pkg` param has no load-time validation in `model.py::load_tools`
  (unlike `node`/`sdkman`). This looked like a fail-fast regression at first,
  but `08-01-PLAN.md` (lines 183-189) shows it was a deliberate, reasoned
  decision: `dnf`/`apt`/`pacman`/`brew`/`cask`/`script` — the majority of
  existing kinds — also get no load-time validation; only `node`/`sdkman` do,
  because of their materially more complex params. `uv-tool`'s single required
  string matches the majority pattern, not a regression against it. Not a finding.
- `resolve.py`'s new `uv-tool` unconditional-True treatment relies on
  `installer/deps.py`'s `requires = ["uv"]` edge to gate real availability
  rather than re-deriving a platform fact. Traced through `installer/app.py`'s
  only call site (`resolve_dependencies(..., available=lambda tool: bool(resolve_methods(tool, platform)), is_installed=installed)`)
  and confirmed the deps-first topological order this produces does put `uv`
  before `graphify` whenever `uv` isn't already installed, mirroring the
  already-shipped `java`/`sdkman` precedent exactly. Not a finding.
- `_uv_tool`'s bare `"uv"` argv (no `real_pnpm()`-style absolute-path
  resolution) was checked against `installer/guards.py`'s `BANNED`/
  `REDIRECTED`/`GLOBAL_REDIRECTED` dicts — none carry a `uv` entry, so there is
  no shim/redirect this executor needs to route around. Not a finding.
- The RTK `aarch64-apple-darwin` (Apple Silicon macOS) tarball layout was
  never independently downloaded/inspected (only `x86_64-musl`,
  `aarch64-gnu`, and `x86_64-apple-darwin` were, per the registry's own
  "Verified" comment and `08-REVIEWS.md` cycle 3 finding #4, which states
  explicitly "no arm64 Darwin tarball was ever downloaded or needed"). This
  was a knowingly-accepted residual, not an oversight — see WR-01 below for
  why it is still worth surfacing rather than silently dropping.

No Critical/BLOCKER findings were found: no injection vectors (the new
executor builds a plain argv list, never a shell string, from
trusted-registry-only data), no hardcoded secrets, no crashes reachable
through the tested paths, and no `resolve_methods`/`_RANK` gaps (the
`KeyError` that motivated this phase's `resolve.py` fix is verifiably closed
— `"uv-tool"` is present in both `_RANK` and `_applies`'s unconditional-True
tuple, and `test_uv_tool_applies_on_every_platform_including_immutable`
exercises every OS/immutable combination). The two Warnings below are real,
narrow residual-risk items worth a maintainer's explicit sign-off rather than
silent acceptance.

## Warnings

### WR-01: RTK's macOS method is arch-unrestricted but only one of its two macOS-arch assets was ever inspected

**File:** `installer/registry.toml:1556-1562`
**Issue:** The `rtk` tool's macOS `github_release` method has no `arch =
[...]` restriction, so it resolves identically on Intel (`amd64`) and Apple
Silicon (`arm64`) Macs, rendering `asset = "rtk-{arch.machine}-apple-darwin.tar.gz"`
as `rtk-x86_64-apple-darwin.tar.gz` on Intel and `rtk-aarch64-apple-darwin.tar.gz`
on Apple Silicon (`installer/assets.py`'s `arch_tokens` mapping). The entry's
own "Verified 2026-09-06" comment states the tarball layout (`member = "rtk"`,
`strip = 0`, no wrapping directory) was confirmed live by running `tar -tzf`
on exactly three tarballs — `x86_64-musl`, `aarch64-gnu`, and
`x86_64-apple-darwin`. The fourth combination this same unrestricted method
actually serves in production, `aarch64-apple-darwin` (the majority
architecture on Macs sold since 2020), was never downloaded or inspected —
`08-REVIEWS.md` cycle 3 records this explicitly ("no arm64 Darwin tarball was
ever downloaded or needed") as a considered, accepted gap rather than an
oversight, but the risk it accepted is still live in the code today: if that
specific asset's internal layout differs (e.g. wrapped in a versioned
directory, the common alternate convention this project's own `strip = 1`
entries exist to handle), every Apple Silicon Mac user hits a `member "rtk"
not found in archive`-class failure with no fallback other than `brew` (which
depends on Homebrew being present).
**Fix:** Either (a) download and `tar -tzf` the live `rtk-aarch64-apple-darwin.tar.gz`
asset once to close the gap the same way cycle 2 closed the Linux-arm64 gap,
or (b) if intentionally left as an inferred-safe assumption, say so
explicitly in the comment (e.g. "the arm64 Darwin asset was not independently
inspected; assumed to share the same flat-binary layout as the other three
verified assets based on rtk-ai's single cross-compiled release pipeline") so
a future maintainer reading "Verified 2026-09-06" doesn't read it as
covering all four asset variants this method serves.

### WR-02: The four agent-host `recommends` comment blocks are verbatim-duplicated, including the codex-specific caveat

**File:** `installer/registry.toml` (the `codex`, `claude`, `opencode`, and `cursor-agent` `[[tool]]` blocks — see e.g. lines 1321-1325, 1345-1349, 1369-1373, 1411-1415)
**Issue:** All four hosts carry the identical 5-line comment (down to the
punctuation), including the sentence "rtk (native hook integration for this
host -- see 08-RESEARCH.md's per-host table for the one exception, codex,
where rtk's integration is instructions-based rather than a runtime hook)."
That sentence is phrased as a caveat about `codex` specifically, but it
appears verbatim inside `claude`'s, `opencode`'s, and `cursor-agent`'s own
comment blocks too, not just `codex`'s. A maintainer skimming any one of the
other three hosts' comments in isolation reads a caveat about a different
tool's integration quality as if it were general per-host framing, and any
future correction to the wording (e.g. if `claude`'s own `rtk` integration
also turns out to be instructions-based, or the caveat text needs
clarifying) requires editing the same string in four places with no
mechanism (TOML has no macro/include) to keep them in sync.
**Fix:** Trim each of the three non-`codex` hosts' comment to the two facts
that are actually about that host (`codegraph` is host-agnostic; `graphify`
supports this host per its README; `rtk` has a native hook for this host),
and keep the "codex is the one exception" caveat sentence only inside
`codex`'s own comment block, where it is actually about the entry it sits above.

## Info

### IN-01: `_uv_tool` has no friendly precheck for a missing `uv` binary, unlike its `_node` sibling

**File:** `installer/executors.py:456-458`
**Issue:** `_node` (line 384-389) checks `real_pnpm() is None` and raises a
descriptive `ExecutorError` ("pnpm not found on PATH — install pnpm...")
before ever invoking the runner. `_uv_tool` calls `runner(["uv", "tool",
"install", pypi_pkg])` directly with no such precheck; if `uv` is not on
PATH, `run_command`'s `OSError` handler produces only a generic `CommandError(cmd,
127)` with no explanatory detail (`installer/run.py:29-30`, no `detail=`
passed). In the normal wizard flow this is unreachable because
`resolve_dependencies` always installs `uv` first when it's `graphify`'s
`requires` (confirmed in `installer/app.py::run_wizard`), but it is directly
reachable through `installer.engine.install_tool(graphify, platform)` called
in isolation — the exact call this phase's own Tier-3 verification used, and
a plausible future CLI/automation entry point that bypasses the wizard's
dependency resolution. This mirrors `_sdkman`'s existing (pre-Phase-8) lack
of a precheck, so it is not a new inconsistency introduced by this phase, but
worth a shared fix if one is ever done for `_sdkman`.
**Fix:** Optional: add a `shutil.which("uv") is None` precheck in `_uv_tool`
raising `ExecutorError("uv not found on PATH — install uv first, or apply this project's own uv catalog entry")`, mirroring `_node`'s pattern.

### IN-02: `graphify`'s `desc` doesn't mention it needs `uv`

**File:** `installer/registry.toml:1519`
**Issue:** Every other `requires`-carrying tool in this registry states the
dependency in its own `desc` (e.g. `oh-my-zsh`: "installs into ~/.oh-my-zsh
and edits .zshrc..." with `requires = ["zsh", "git"]` explained in the
preceding comment; `java`/`groovy`/`gradle`/`maven`: "installed... exclusively
through SDKMAN" directly in `desc`). `graphify`'s `desc` ("Turns a codebase...
into a queryable local knowledge graph for AI agents.") never mentions `uv`,
even though `requires = ["uv"]` is declared one line above it. This is purely
a catalog-browsing readability nit (the requires-notice mechanism in
`catalog_tui.py::_announce_requires` surfaces the dependency at selection
time regardless), not a functional gap.
**Fix:** Append a clause like "; installed via `uv tool install`, so `uv` is
pulled in automatically" to `desc`, matching the SDKMAN-family tools' convention.

## Second lane: codex-sol-high

Independent parallel dispatch (`codex exec -m gpt-5.6-sol`, effort high) over the identical
diff range (`85f02a5f4f5fa6a55e845079b8d0c75b10b5b9c8..HEAD`), per ONESHOT-RULES Rule 15.

**Result: 0 Critical/High findings; 1 Medium finding.**

### M-01 — `curl | sh` script executor can report a failed download as `INSTALLED`

**File:** `installer/executors.py:353-360` (`_script`), exercised by this phase's new
`cursor-agent`/`antigravity` entries.
**Issue:** `_script` builds `sh -c "curl -fsSL -- <url> | <shell>"` with no `pipefail`. POSIX
`sh -c` reports the LAST command's exit status in a pipeline — if `curl` fails (DNS/TLS/
connection error) before producing output, the downstream shell reads an empty stdin and
exits 0, so `install_tool` reports `INSTALLED` even though nothing downloaded. Reproduced
locally: a failing `curl` piped into `bash` exits 0.
**Disposition: accepted residual, not fixed in this phase.** This is a real finding, but it
is a PRE-EXISTING pattern shared by every `kind="script"` entry already in this registry
before Phase 8 — `codex`, `claude`, `opencode`, `brew`, `uv`, `sdkman`, `oh-my-zsh` all use
the identical `_script` executor and are equally exposed. Phase 8's `cursor-agent`/
`antigravity` entries did not introduce this pattern; they are two more instances of an
already-shipped, already-accepted executor. Fixing it correctly (adding `set -o pipefail` —
not universally supported by plain `sh`, so the fix likely needs a shell-capability check or
switching the pipeline construction entirely) would be a shared-executor change touching
every existing script-kind entry's behavior and test coverage, well outside this phase's
scope and REQ set. Recorded here for a future dedicated fix (e.g. a
`REQ-script-executor-pipefail-hardening`-shaped phase), not silently dropped.

## Resolution status

| Finding | Lane | Severity | Disposition |
|---|---|---|---|
| WR-01 (RTK arm64-Darwin tarball unverified) | internal | Warning | **Fixed** — registry comment now explicitly states this asset was not independently inspected and states the assumption, rather than implying all four macOS/Linux variants were checked. |
| WR-02 (codex-specific caveat duplicated verbatim across 4 hosts) | internal | Warning | **Fixed** — trimmed the codex-specific caveat sentence out of `claude`/`opencode`/`cursor-agent`'s comments; it now appears only in `codex`'s own comment, where it is actually about that entry. |
| IN-01 (`_uv_tool` has no missing-`uv` precheck) | internal | Info | Accepted — mirrors pre-existing `_sdkman` behavior, not a phase-8-specific regression; unreachable in the normal wizard flow since `resolve_dependencies` installs `uv` first. |
| IN-02 (`graphify`'s `desc` doesn't mention `uv`) | internal | Info | Accepted — cosmetic; the requires-notice mechanism (`catalog_tui.py`) already surfaces the dependency at selection time regardless. |
| M-01 (`curl\|sh` pipeline can mask a failed download as `INSTALLED`) | codex-sol-high | Medium | Accepted residual — real finding, but a pre-existing pattern shared by 7+ existing script-kind entries, not something Phase 8 introduced; fixing it is a shared-executor change out of this phase's scope. |

`make validate && make test` re-verified after the two Warning fixes: **1250 passed**, 99.40%
coverage, 0 lint/type/security findings — unchanged pass count (comment-only edits).

---

_Reviewed: 2026-09-06_
_Reviewers: Claude (gsd-code-reviewer), codex-sol-high (second lane)_
_Depth: standard_
